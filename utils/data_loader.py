"""Pemuat, normalisasi, dan filter data CSV sentimen serta SNA."""

import os
from datetime import datetime
from pathlib import Path

import pandas as pd
import streamlit as st

from utils.dummy_data import get_dummy_sentiment_data, get_dummy_sna_data

CANONICAL_SENTIMENT_COLS = {
    "date": ["date", "date_created", "created_at", "timestamp"],
    "platform": ["platform", "specific_resource_type", "source_platform"],
    "username": ["username", "from_username", "user", "screen_name"],
    "followers": ["followers", "follower_count", "followers_count"],
    "content": ["content", "text", "comment", "tweet_text", "caption"],
    "predicted_sentiment": ["predicted_sentiment", "sentiment", "label", "final_sentiment"],
    "confidence": ["confidence", "confidence_score", "score"],
}

CANONICAL_SNA_COLS = {
    "source": ["source", "vertex1", "from_username", "user_from"],
    "target": ["target", "vertex2", "to_username", "user_to"],
    "relationship": ["relationship", "relation", "type", "edge_type"],
    "followers": ["followers", "follower_count"],
    "platform": ["platform", "specific_resource_type"],
}

DATA_FILES = {
    "IndiHome": {
        "sentiment": "data/indihome_sentiment.csv",
        "sna": "data/sna_data.csv",
    },
    "IndiBiz": {
        "sentiment": "data/indibiz_sentiment.csv",
        "sna": "data/sna_data.csv",
    },
    "Telkomsel": {
        "sentiment": "data/telkomsel_sentiment.csv",
        "sna": "data/sna_data.csv",
    },
}

REQUIRED_SENTIMENT_COLS = [
    "date", "platform", "username", "followers", "content",
    "predicted_sentiment", "confidence",
]
REQUIRED_SNA_COLS = ["source", "target", "relationship", "followers", "platform"]

SENTIMENT_MAP = {
    "label_0": "positive", "positive": "positive", "positif": "positive",
    "label_1": "neutral", "neutral": "neutral", "netral": "neutral",
    "label_2": "negative", "negative": "negative", "negatif": "negative",
}

MODEL_SERVICES = ("indihome", "indibiz", "telkomsel")


def _project_root() -> Path:
    """Kembalikan path root proyek."""
    return Path(__file__).resolve().parent.parent


def _resolve_path(rel_path: str) -> str:
    """Ubah path relatif menjadi path absolut."""
    return str(_project_root() / rel_path)


def _sentiment_csv_path(layanan: str) -> str:
    """Kembalikan path file CSV sentimen untuk layanan tertentu."""
    key = DATA_FILES.get(layanan, DATA_FILES["IndiHome"])["sentiment"]
    return _resolve_path(key)


def _sna_csv_path() -> str:
    """Kembalikan path file CSV SNA."""
    return _resolve_path("data/sna_data.csv")


def sentiment_file_exists(layanan: str) -> bool:
    """Cek apakah file CSV sentimen tersedia di disk."""
    try:
        return os.path.exists(_sentiment_csv_path(layanan))
    except Exception:
        return False


def sna_file_exists() -> bool:
    """Cek apakah file CSV SNA tersedia di disk."""
    try:
        return os.path.exists(_sna_csv_path())
    except Exception:
        return False


def _get_date_column(df: pd.DataFrame) -> str:
    """Tentukan nama kolom tanggal yang tersedia di DataFrame."""
    if "date_created" in df.columns:
        return "date_created"
    if "date" in df.columns:
        return "date"
    raise ValueError("Kolom tanggal (date_created/date) tidak ditemukan.")


def _read_csv_flexible(path: str) -> pd.DataFrame | None:
    """Baca CSV dengan beberapa delimiter dan encoding."""
    for delimiter in [",", ";", "\t"]:
        try:
            df = pd.read_csv(path, delimiter=delimiter, encoding="utf-8-sig")
            if df.shape[1] > 1:
                return df
        except Exception:
            continue
    try:
        return pd.read_csv(path, encoding="latin-1")
    except Exception:
        return None


def _normalize_columns(df: pd.DataFrame, mapping: dict) -> pd.DataFrame:
    """Normalisasi nama kolom ke nama kanonik."""
    col_lower = {c.lower().strip(): c for c in df.columns}
    rename = {}
    for canonical, aliases in mapping.items():
        for alias in aliases:
            if alias.lower() in col_lower:
                rename[col_lower[alias.lower()]] = canonical
                break
    return df.rename(columns=rename)


def _clean_string_columns(df: pd.DataFrame) -> pd.DataFrame:
    """Bersihkan leading apostrophe pada kolom string."""
    df = df.copy()
    for col in df.select_dtypes(include="object").columns:
        df[col] = df[col].astype(str).str.lstrip("'").str.strip()
    return df


def _normalize_sentiment_df(df: pd.DataFrame, layanan: str) -> pd.DataFrame:
    """Bersihkan dan normalisasi DataFrame sentimen."""
    df = _normalize_columns(df, CANONICAL_SENTIMENT_COLS)
    df = _clean_string_columns(df)

    for col in REQUIRED_SENTIMENT_COLS:
        if col not in df.columns:
            raise ValueError(f"Kolom wajib '{col}' tidak ditemukan.")

    df["followers"] = pd.to_numeric(df["followers"], errors="coerce").fillna(0).astype(int)
    df["confidence"] = pd.to_numeric(df["confidence"], errors="coerce").fillna(0.0)
    df["platform"] = df["platform"].astype(str).str.lower().str.strip()
    df["predicted_sentiment"] = (
        df["predicted_sentiment"].astype(str).str.lower().str.strip().map(SENTIMENT_MAP)
    )
    df["predicted_sentiment"] = df["predicted_sentiment"].fillna("neutral")
    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    df["date_created"] = df["date"]
    df["confidence_score"] = df["confidence"]
    if "layanan" not in df.columns:
        df["layanan"] = layanan
    return df


def _normalize_sna_df(df: pd.DataFrame) -> pd.DataFrame:
    """Bersihkan dan normalisasi DataFrame SNA."""
    df = _normalize_columns(df, CANONICAL_SNA_COLS)
    df = _clean_string_columns(df)

    for col in REQUIRED_SNA_COLS:
        if col not in df.columns:
            raise ValueError(f"Kolom wajib '{col}' tidak ditemukan.")

    df["followers"] = pd.to_numeric(df["followers"], errors="coerce").fillna(0).astype(int)
    df["platform"] = df["platform"].astype(str).str.lower().str.strip()
    df = df.dropna(subset=["source", "target"])
    df["source"] = df["source"].astype(str).str.strip()
    df["target"] = df["target"].astype(str).str.strip()
    df = df[(df["source"] != "") & (df["target"] != "")]
    df = df[(df["source"].str.lower() != "nan") & (df["target"].str.lower() != "nan")]
    return df.reset_index(drop=True)


def _fallback_sentiment_df(layanan: str) -> pd.DataFrame:
    """Muat data sentimen dummy yang sudah dinormalisasi."""
    return _normalize_sentiment_df(get_dummy_sentiment_data(layanan), layanan)


@st.cache_data
def _load_sentiment_cached(layanan: str) -> pd.DataFrame:
    """Muat data sentimen dari CSV atau dummy (internal, ter-cache)."""
    path = _sentiment_csv_path(layanan)
    if not os.path.exists(path):
        return _fallback_sentiment_df(layanan)

    df = _read_csv_flexible(path)
    if df is None or df.empty:
        return _fallback_sentiment_df(layanan)

    return _normalize_sentiment_df(df, layanan)


def load_sentiment_data(layanan: str) -> pd.DataFrame:
    """
    Muat data sentimen dari data/{layanan}_sentiment.csv.

    Jika file tidak ada atau gagal dibaca, fallback ke data dummy.
    """
    try:
        if not sentiment_file_exists(layanan):
            st.warning(
                f"File CSV sentimen untuk {layanan} tidak ditemukan. "
                "Menggunakan data dummy."
            )
        return _load_sentiment_cached(layanan)
    except Exception as e:
        st.error(f"Gagal memuat data sentimen {layanan}: {e}")
        st.warning("Menggunakan data dummy sebagai fallback.")
        return _fallback_sentiment_df(layanan)


@st.cache_data
def _load_sna_cached() -> pd.DataFrame:
    """Muat data SNA dari CSV atau dummy (internal, ter-cache)."""
    path = _sna_csv_path()
    if not os.path.exists(path):
        return get_dummy_sna_data()

    df = _read_csv_flexible(path)
    if df is None or df.empty:
        return get_dummy_sna_data()

    return _normalize_sna_df(df)


def load_sna_data() -> pd.DataFrame:
    """
    Muat data SNA dari data/sna_data.csv.

    Jika file tidak ada atau gagal dibaca, fallback ke data dummy.
    """
    try:
        if not sna_file_exists():
            st.warning("File data/sna_data.csv tidak ditemukan. Menggunakan data dummy SNA.")
        return _load_sna_cached()
    except Exception as e:
        st.error(f"Gagal memuat data SNA: {e}")
        st.warning("Menggunakan data dummy SNA sebagai fallback.")
        return get_dummy_sna_data()


def get_platform_filter(df: pd.DataFrame, platforms: list | None) -> pd.DataFrame:
    """Filter DataFrame berdasarkan daftar platform."""
    try:
        if not platforms:
            return df.copy()
        if "platform" not in df.columns:
            st.error("Kolom 'platform' tidak ditemukan pada DataFrame.")
            return df.copy()
        normalized = [p.lower().strip() for p in platforms]
        return df[df["platform"].isin(normalized)].copy()
    except Exception as e:
        st.error(f"Gagal memfilter platform: {e}")
        return df.copy()


def get_date_range_filter(
    df: pd.DataFrame,
    start_date,
    end_date,
) -> pd.DataFrame:
    """Filter DataFrame berdasarkan rentang tanggal di kolom date_created."""
    try:
        if df.empty:
            return df.copy()
        date_col = _get_date_column(df)
        result = df.copy()
        result[date_col] = pd.to_datetime(result[date_col], errors="coerce")
        start = pd.to_datetime(start_date)
        end = pd.to_datetime(end_date)
        mask = (result[date_col] >= start) & (result[date_col] <= end)
        return result[mask].copy()
    except Exception as e:
        st.error(f"Gagal memfilter rentang tanggal: {e}")
        return df.copy()


def get_sentiment_filter(df: pd.DataFrame, sentiments: list | None) -> pd.DataFrame:
    """Filter DataFrame berdasarkan daftar sentimen."""
    try:
        if not sentiments:
            return df.copy()
        if "predicted_sentiment" not in df.columns:
            st.error("Kolom 'predicted_sentiment' tidak ditemukan pada DataFrame.")
            return df.copy()
        normalized = [s.lower().strip() for s in sentiments]
        mapped = [SENTIMENT_MAP.get(s, s) for s in normalized]
        return df[df["predicted_sentiment"].isin(mapped)].copy()
    except Exception as e:
        st.error(f"Gagal memfilter sentimen: {e}")
        return df.copy()


def get_sentiment_summary(df: pd.DataFrame) -> dict:
    """Hitung ringkasan statistik sentimen dari DataFrame."""
    try:
        total = len(df)
        if total == 0:
            return {
                "total": 0,
                "positive_count": 0,
                "neutral_count": 0,
                "negative_count": 0,
                "pct_positive": 0.0,
                "pct_neutral": 0.0,
                "pct_negative": 0.0,
                "avg_confidence": 0.0,
            }

        counts = df["predicted_sentiment"].value_counts()
        pos = int(counts.get("positive", 0))
        neu = int(counts.get("neutral", 0))
        neg = int(counts.get("negative", 0))

        conf_col = "confidence_score" if "confidence_score" in df.columns else "confidence"
        avg_conf = float(pd.to_numeric(df[conf_col], errors="coerce").mean())

        return {
            "total": total,
            "positive_count": pos,
            "neutral_count": neu,
            "negative_count": neg,
            "pct_positive": round(pos / total * 100, 1),
            "pct_neutral": round(neu / total * 100, 1),
            "pct_negative": round(neg / total * 100, 1),
            "avg_confidence": round(avg_conf, 3),
        }
    except Exception as e:
        st.error(f"Gagal menghitung ringkasan sentimen: {e}")
        return {
            "total": 0,
            "positive_count": 0,
            "neutral_count": 0,
            "negative_count": 0,
            "pct_positive": 0.0,
            "pct_neutral": 0.0,
            "pct_negative": 0.0,
            "avg_confidence": 0.0,
        }


def get_platform_summary(df: pd.DataFrame) -> dict:
    """Hitung jumlah data per platform unik."""
    try:
        if df.empty or "platform" not in df.columns:
            return {}
        summary = df["platform"].value_counts().to_dict()
        return {str(k): int(v) for k, v in summary.items()}
    except Exception as e:
        st.error(f"Gagal menghitung ringkasan platform: {e}")
        return {}


def load_model_status() -> dict:
    """
    Cek status ketersediaan model di folder models/{layanan}/.

    Return status ready atau coming_soon per layanan.
    """
    try:
        models_root = _project_root() / "models"
        status = {}
        for service in MODEL_SERVICES:
            folder = models_root / service
            has_files = folder.is_dir() and any(folder.iterdir())
            status[service] = "ready" if has_files else "coming_soon"
        return status
    except Exception as e:
        st.error(f"Gagal memeriksa status model: {e}")
        return {service: "coming_soon" for service in MODEL_SERVICES}


def get_data_source_label(layanan: str) -> str:
    """Kembalikan label sumber data real atau dummy untuk layanan tertentu."""
    try:
        if sentiment_file_exists(layanan):
            return "📁 Data Real"
        return "🔧 Data Dummy"
    except Exception as e:
        st.error(f"Gagal menentukan sumber data: {e}")
        return "🔧 Data Dummy"


def filter_data(
    df: pd.DataFrame,
    layanan: list[str] = None,
    platform: list[str] = None,
    sentimen: list[str] = None,
    date_range: tuple = None,
    search_query: str = None,
) -> pd.DataFrame:
    """Filter DataFrame gabungan (kompatibilitas fase sebelumnya)."""
    try:
        result = df.copy()
        if layanan and "layanan" in result.columns:
            result = result[result["layanan"].isin(layanan)]
        if platform:
            result = get_platform_filter(result, platform)
        if sentimen:
            result = get_sentiment_filter(result, sentimen)
        if date_range:
            start, end = date_range
            result = get_date_range_filter(result, start, end)
        if search_query and "content" in result.columns:
            result = result[result["content"].str.contains(search_query, case=False, na=False)]
        return result
    except Exception as e:
        st.error(f"Gagal memfilter data: {e}")
        return df.copy()


def get_data_status(layanan: str) -> dict:
    """Kembalikan status ketersediaan file data untuk suatu layanan."""
    try:
        sent_path = _sentiment_csv_path(layanan)
        sna_path = _sna_csv_path()

        sentiment_exists = os.path.exists(sent_path)
        sna_exists = os.path.exists(sna_path)

        sentiment_rows = 0
        sna_edges = 0
        last_modified = "-"

        if sentiment_exists:
            sentiment_rows = len(load_sentiment_data(layanan))
            last_modified = datetime.fromtimestamp(os.path.getmtime(sent_path)).strftime(
                "%d-%m-%Y %H:%M"
            )
        if sna_exists:
            sna_edges = len(load_sna_data())

        return {
            "sentiment_exists": sentiment_exists,
            "sna_exists": sna_exists,
            "sentiment_rows": sentiment_rows,
            "sna_edges": sna_edges,
            "last_modified": last_modified,
        }
    except Exception as e:
        st.error(f"Gagal memeriksa status data: {e}")
        return {
            "sentiment_exists": False,
            "sna_exists": False,
            "sentiment_rows": 0,
            "sna_edges": 0,
            "last_modified": "-",
        }
