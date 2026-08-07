"""Layanan bersama untuk data terklasifikasi dan opsi Top 5 Analisis Topik.

Modul ini dipakai oleh halaman Analisis Topik dan Rekomendasi agar keduanya
membaca sumber, klasifikasi, urutan topik, dan cache yang sama.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import pandas as pd
import streamlit as st

from utils.data_loader import get_sentiment_file_signature, load_topic_data
from utils.topic_classifier import apply_indihome_topics, apply_telkomsel_topics, apply_topics, summarize_topics

PROJECT_ROOT = Path(__file__).resolve().parent.parent
INDIBIZ_TOPIC_FILE = PROJECT_ROOT / "data" / "indibiz_output_top_topic.csv"
ACTIVE_SERVICES = ("IndiHome", "IndiBiz", "Telkomsel")

MISCELLANEOUS_TOPIC_ALIASES = {
    "lainnya",
    "topik lainnya",
    "topik lain",
    "other",
    "others",
}

# Hanya digunakan bila sumber aktual tidak tersedia atau tidak valid.
SERVICE_TOPIC_OPTION_FALLBACKS: dict[str, list[str]] = {
    "IndiHome": [
        "Kecepatan Lambat",
        "Gangguan Jaringan",
        "Permintaan Bantuan",
        "Harga Mahal",
    ],
    "IndiBiz": [
        "Bisnis, UMKM & Digitalisasi",
        "Kecepatan & Stabilitas Internet",
        "Layanan Pelanggan & Admin",
        "Harga, Tagihan & Paket",
    ],
    "Telkomsel": [
        "Harga Mahal",
        "Kecepatan Lambat",
        "Permintaan Bantuan",
        "Tanya Kuota dan Masa Aktif",
    ],
}


def normalize_topic_platform(value: Any) -> str:
    """Normalisasi nama platform ke twitter, instagram, atau tiktok."""
    key = str(value or "").strip().lower().replace("'", "")
    if key in {"twitter", "x", "twitter/x"}:
        return "twitter"
    if "instagram" in key or key == "ig":
        return "instagram"
    if "tiktok" in key or key == "tik tok":
        return "tiktok"
    return key or "lainnya"


TOPIC_CACHE_SCHEMA_VERSION = "2026.08.08-indihome-telkomsel-mixed-topic-v4"


def _build_enriched_topic_data(layanan: str) -> pd.DataFrame:
    """Bangun data topik langsung dari sumber tanpa membaca cache lama."""
    source = load_topic_data(layanan)
    if source.empty:
        return source.copy()

    columns = [
        column
        for column in ["platform", "content", "predicted_sentiment", "layanan"]
        if column in source.columns
    ]
    result = source.loc[:, columns].copy()
    if "platform" not in result.columns:
        result["platform"] = "lainnya"
    if "content" not in result.columns:
        result["content"] = ""
    if "predicted_sentiment" not in result.columns:
        result["predicted_sentiment"] = "neutral"

    result["platform"] = result["platform"].map(normalize_topic_platform)
    result["content"] = result["content"].fillna("").astype(str).str.strip()
    result["predicted_sentiment"] = (
        result["predicted_sentiment"]
        .fillna("neutral")
        .astype(str)
        .str.lower()
        .str.strip()
        .str.lstrip("'")
        .replace({"positif": "positive", "netral": "neutral", "negatif": "negative"})
    )
    result = result[result["content"].ne("")].reset_index(drop=True)

    # IndiBiz membentuk topik melalui output LDA terpisah. Data mentahnya tetap
    # dikembalikan untuk kebutuhan pipeline halaman Analisis Topik.
    if layanan == "IndiBiz":
        return result
    if layanan == "IndiHome":
        return apply_indihome_topics(result, text_col="content")
    if layanan == "Telkomsel":
        return apply_telkomsel_topics(result, text_col="content")
    return apply_topics(result, text_col="content")


@st.cache_data(show_spinner=False, max_entries=6)
def _load_enriched_topic_data_cached_v2(
    layanan: str,
    file_signature: str,
    cache_schema_version: str,
) -> pd.DataFrame:
    """Cache memori dengan versi skema eksplisit agar pickle lama tidak dibaca."""
    del file_signature, cache_schema_version
    return _build_enriched_topic_data(layanan)


def load_enriched_topic_data(layanan: str, file_signature: str) -> pd.DataFrame:
    """Muat data topik dengan pemulihan langsung bila cache tidak kompatibel."""
    try:
        return _load_enriched_topic_data_cached_v2(
            layanan,
            file_signature,
            TOPIC_CACHE_SCHEMA_VERSION,
        )
    except Exception as cache_error:
        message = str(cache_error)
        cache_markers = (
            "StringDtype.__init__",
            "datetime64[us]",
            "dtype('<M8[us]')",
            "pickle",
            "unpickle",
        )
        if any(marker.casefold() in message.casefold() for marker in cache_markers):
            return _build_enriched_topic_data(layanan)
        raise


def _topic_file_signature(path: Path) -> str:
    """Buat signature ringan agar cache berubah saat CSV output diperbarui."""
    try:
        stat = path.stat()
        return f"{path.resolve()}::{stat.st_size}::{stat.st_mtime_ns}"
    except OSError:
        return f"{path.resolve()}::missing"


def _is_miscellaneous_topic(value: Any) -> bool:
    """Tandai kategori residual yang tidak dipakai sebagai rekomendasi."""
    normalized = re.sub(
        r"[^a-z0-9]+",
        " ",
        str(value or "").casefold(),
    ).strip()
    return normalized in MISCELLANEOUS_TOPIC_ALIASES


def _clean_topic_options(values: list[Any]) -> list[str]:
    """Rapikan, deduplikasi, dan buang kategori Lainnya."""
    options: list[str] = []
    seen: set[str] = set()
    for value in values:
        label = re.sub(r"\s+", " ", str(value or "")).strip()
        if not label or _is_miscellaneous_topic(label):
            continue
        identity = label.casefold()
        if identity in seen:
            continue
        seen.add(identity)
        options.append(label)
    return options


def _read_indibiz_topic_output(path: Path) -> pd.DataFrame:
    """Baca output topik IndiBiz secara defensif tanpa mengubah file sumber."""
    if not path.is_file():
        return pd.DataFrame()

    attempts = (
        {"encoding": "utf-8-sig", "sep": ","},
        {"encoding": "utf-8-sig", "sep": ";"},
        {"encoding": "utf-8-sig", "sep": "\t"},
        {"encoding": "latin-1", "sep": ","},
        {"encoding": "latin-1", "sep": ";"},
    )
    for attempt in attempts:
        try:
            dataframe = pd.read_csv(path, low_memory=False, **attempt)
            if len(dataframe.columns) > 1:
                return dataframe
        except Exception:
            continue
    return pd.DataFrame()


def _indibiz_top_five_labels(dataframe: pd.DataFrame) -> list[str]:
    """Susun urutan kartu Top 5 IndiBiz dari rank atau jumlah komentar."""
    if dataframe is None or dataframe.empty:
        return []

    lookup = {
        str(column).strip().casefold(): str(column)
        for column in dataframe.columns
    }
    topic_column = lookup.get("topik") or lookup.get("topic") or lookup.get("topic_name")
    if topic_column is None:
        return []

    work = dataframe.copy()
    work["_topic"] = work[topic_column].fillna("").astype(str).str.strip()
    work = work[work["_topic"].ne("")].copy()
    if work.empty:
        return []

    work["_appearance"] = range(len(work))
    rank_column = lookup.get("topic_rank") or lookup.get("rank") or lookup.get("peringkat")
    total_column = lookup.get("total_topik")
    count_column = lookup.get("jumlah_komentar") or lookup.get("jumlah") or lookup.get("count")

    work["_rank"] = (
        pd.to_numeric(work[rank_column], errors="coerce")
        if rank_column is not None
        else pd.Series(float("nan"), index=work.index)
    )
    if total_column is not None:
        work["_count"] = pd.to_numeric(work[total_column], errors="coerce")
        count_aggregation = "max"
    elif count_column is not None:
        work["_count"] = pd.to_numeric(work[count_column], errors="coerce")
        count_aggregation = "sum"
    else:
        work["_count"] = 0
        count_aggregation = "max"

    records: list[dict[str, Any]] = []
    for topic_name, group in work.groupby("_topic", sort=False):
        ranks = group["_rank"].dropna()
        counts = group["_count"].dropna()
        records.append(
            {
                "topik": str(topic_name),
                "rank": float(ranks.min()) if not ranks.empty else float("inf"),
                "count": (
                    float(counts.sum())
                    if count_aggregation == "sum" and not counts.empty
                    else float(counts.max()) if not counts.empty else 0.0
                ),
                "appearance": int(group["_appearance"].min()),
            }
        )

    if any(record["rank"] != float("inf") for record in records):
        records.sort(
            key=lambda item: (
                item["rank"],
                -item["count"],
                item["appearance"],
                item["topik"].casefold(),
            )
        )
    elif any(record["count"] > 0 for record in records):
        records.sort(
            key=lambda item: (
                -item["count"],
                item["appearance"],
                item["topik"].casefold(),
            )
        )
    else:
        records.sort(key=lambda item: item["appearance"])

    return [record["topik"] for record in records[:5]]


@st.cache_data(show_spinner=False, max_entries=12)
def _get_service_top_topic_options_cached_v2(
    layanan: str,
    source_signature: str,
    cache_schema_version: str,
) -> list[str]:
    """Hitung opsi berdasarkan sumber yang sama dengan Top 5 Analisis Topik."""
    del cache_schema_version
    try:
        if layanan == "IndiBiz":
            raw_values = _indibiz_top_five_labels(
                _read_indibiz_topic_output(INDIBIZ_TOPIC_FILE)
            )
        else:
            enriched = load_enriched_topic_data(layanan, source_signature)
            summary = summarize_topics(enriched, top_n=5)
            raw_values = (
                summary["topik"].astype(str).tolist()
                if "topik" in summary.columns
                else []
            )

        options = _clean_topic_options(raw_values)
        if options:
            return options
    except Exception:
        pass

    fallback = SERVICE_TOPIC_OPTION_FALLBACKS.get(
        layanan,
        SERVICE_TOPIC_OPTION_FALLBACKS["IndiHome"],
    )
    return _clean_topic_options(fallback)


def get_service_top_topic_options(layanan: str) -> list[str]:
    """Kembalikan Top 5 layanan tanpa kategori Lainnya/Topik Lainnya."""
    safe_service = layanan if layanan in ACTIVE_SERVICES else "IndiHome"
    signature = (
        _topic_file_signature(INDIBIZ_TOPIC_FILE)
        if safe_service == "IndiBiz"
        else get_sentiment_file_signature(safe_service)
    )
    try:
        options = _get_service_top_topic_options_cached_v2(
            safe_service,
            signature,
            TOPIC_CACHE_SCHEMA_VERSION,
        )
    except Exception:
        # Cache opsi bersifat pelengkap; fallback yang sudah ada tetap aman.
        options = []
    if options:
        return options
    return SERVICE_TOPIC_OPTION_FALLBACKS["IndiHome"].copy()
