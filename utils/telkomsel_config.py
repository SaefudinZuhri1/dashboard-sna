"""Kontrak file dan konfigurasi preprocessing layanan Telkomsel."""

from __future__ import annotations

import re
from pathlib import Path

import pandas as pd
import streamlit as st

SERVICE_NAME = "Telkomsel"
TARGET_NODE = "telkomsel"
INDOBERT_MODEL = "mdhugol/indonesia-bert-sentiment-classification"
CANONICAL_OUTPUT_FILE = "telkomsel_sentiment.csv"
KEYWORD_FILTER = ("telkomsel", "telkom")
ALLOWED_PLATFORMS = ("twitter", "instagram", "tiktok")
OUTPUT_COLUMNS = (
    "text",
    "cleaned_text",
    "label",
    "score",
    "platform",
    "date",
    "username",
    "topic",
)

RAW_SOURCE_CANDIDATES = (
    "Telkomsel-NovemberDesember.csv",
    "Telkomsel-NovemberDesember.zip",
    "Telkomsel NovemberDesember 2025.xlsx",
    "Telkomsel-NovemberDesember.xlsx",
)

SENTIMENT_OUTPUT_CANDIDATES = (
    CANONICAL_OUTPUT_FILE,
    "telkomsel_output_sentiment.csv",
    "Telkomsel Sentiment.csv",
)

RAW_COLUMN_ALIASES = {
    "text": ("text", "content", "comment", "tweet_text", "caption"),
    "platform": (
        "platform",
        "specific_resource_type",
        "source_platform",
        "media",
        "channel",
    ),
    "date": ("date", "date_created", "created_at", "timestamp", "time"),
    "username": (
        "username",
        "from_username",
        "user",
        "screen_name",
        "author",
    ),
}

PLATFORM_ALIASES = {
    "x": "twitter",
    "twitter/x": "twitter",
    "twitter (x)": "twitter",
    "x/twitter": "twitter",
    "tweet": "twitter",
    "ig": "instagram",
    "instagram comments": "instagram",
    "tik tok": "tiktok",
    "tiktok comments": "tiktok",
}

_DATE_PATTERN = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_KEYWORD_PATTERN = re.compile(r"telkomsel|telkom", re.IGNORECASE)


def get_telkomsel_output_path(data_dir: str | Path = "data") -> Path:
    """Kembalikan path kanonik output preprocessing Telkomsel."""
    try:
        return Path(data_dir) / CANONICAL_OUTPUT_FILE
    except Exception as error:
        st.error(f"Gagal membentuk path output Telkomsel: {error}")
        return Path("data") / CANONICAL_OUTPUT_FILE


def get_telkomsel_configuration_summary() -> dict[str, object]:
    """Kembalikan ringkasan kontrak preprocessing Telkomsel."""
    try:
        return {
            "service_name": SERVICE_NAME,
            "target_node": TARGET_NODE,
            "indobert_model": INDOBERT_MODEL,
            "canonical_output_file": CANONICAL_OUTPUT_FILE,
            "keyword_filter": list(KEYWORD_FILTER),
            "allowed_platforms": list(ALLOWED_PLATFORMS),
            "output_columns": list(OUTPUT_COLUMNS),
            "raw_source_candidates": list(RAW_SOURCE_CANDIDATES),
            "sentiment_output_candidates": list(SENTIMENT_OUTPUT_CANDIDATES),
        }
    except Exception as error:
        st.error(f"Gagal membaca konfigurasi Telkomsel: {error}")
        return {}


def validate_telkomsel_preprocessing_dataframe(
    dataframe: pd.DataFrame,
) -> dict[str, object]:
    """Validasi kontrak output preprocessing sebelum tahap prediksi IndoBERT.

    Fungsi ini tidak menulis file. Label, score, dan topic memang harus kosong
    pada fase preprocessing karena ketiganya diisi pada tahap analitik lanjutan.
    """
    result: dict[str, object] = {
        "ready": False,
        "total_rows": 0,
        "columns_exact": False,
        "invalid_platform_count": 0,
        "invalid_date_count": 0,
        "missing_keyword_count": 0,
        "empty_text_count": 0,
        "empty_cleaned_text_count": 0,
        "nonempty_future_columns_count": 0,
        "message": "Output belum diperiksa.",
    }

    try:
        if not isinstance(dataframe, pd.DataFrame):
            result["message"] = "Objek yang diperiksa bukan pandas DataFrame."
            return result
        if dataframe.empty:
            result["message"] = "Output preprocessing belum memiliki baris data."
            return result

        result["total_rows"] = int(len(dataframe))
        result["columns_exact"] = dataframe.columns.tolist() == list(OUTPUT_COLUMNS)
        if not result["columns_exact"]:
            result["message"] = (
                "Urutan atau nama kolom belum identik dengan kontrak "
                "telkomsel_sentiment.csv."
            )
            return result

        platforms = dataframe["platform"].astype("string").fillna("").str.lower().str.strip()
        dates = dataframe["date"].astype("string").fillna("").str.strip()
        texts = dataframe["text"].astype("string").fillna("").str.strip()
        cleaned = dataframe["cleaned_text"].astype("string").fillna("").str.strip()

        result["invalid_platform_count"] = int(
            (~platforms.isin(ALLOWED_PLATFORMS)).sum()
        )
        result["invalid_date_count"] = int(
            (~dates.map(lambda value: bool(_DATE_PATTERN.fullmatch(str(value))))).sum()
        )
        result["missing_keyword_count"] = int(
            (~texts.map(lambda value: bool(_KEYWORD_PATTERN.search(str(value))))).sum()
        )
        result["empty_text_count"] = int(texts.eq("").sum())
        result["empty_cleaned_text_count"] = int(cleaned.eq("").sum())

        future_nonempty = 0
        for column in ("label", "score", "topic"):
            values = dataframe[column].astype("string").fillna("").str.strip()
            future_nonempty += int(values.ne("").sum())
        result["nonempty_future_columns_count"] = future_nonempty

        result["ready"] = bool(
            result["columns_exact"]
            and result["invalid_platform_count"] == 0
            and result["invalid_date_count"] == 0
            and result["missing_keyword_count"] == 0
            and result["empty_text_count"] == 0
            and result["empty_cleaned_text_count"] == 0
            and result["nonempty_future_columns_count"] == 0
        )
        result["message"] = (
            "Output preprocessing Telkomsel valid dan siap diteruskan ke tahap "
            "prediksi IndoBERT."
            if result["ready"]
            else "Output terbaca, tetapi masih ada bagian kontrak yang belum valid."
        )
        return result
    except Exception as error:
        result["message"] = f"Gagal memvalidasi output preprocessing Telkomsel: {error}"
        return result
