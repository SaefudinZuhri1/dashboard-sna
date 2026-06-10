"""Halaman eksplorasi dataset penelitian media sosial Telkom Group."""

from __future__ import annotations

import logging
import math
import re
from datetime import date, datetime
from pathlib import Path
from typing import Any

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from utils.chart_builder import (
    PLATFORM_COLORS,
    SENTIMENT_COLORS,
    bar_chart_platform,
    grouped_bar_platform_sentiment,
)
from utils.css_loader import render_page_header
from utils.dummy_data import get_dummy_sentiment_data
from utils.export_utils import export_to_csv, export_to_excel

LOGGER = logging.getLogger(__name__)

SERVICES = ["IndiHome", "IndiBiz", "Telkomsel"]
PLATFORM_ORDER = ["twitter", "instagram", "tiktok"]
PLATFORM_LABELS = {
    "twitter": "Twitter",
    "instagram": "Instagram",
    "tiktok": "TikTok",
}
PLATFORM_KEYS = {label: key for key, label in PLATFORM_LABELS.items()}
SENTIMENT_ORDER = ["positive", "neutral", "negative"]
SENTIMENT_LABELS = {
    "positive": "Positive",
    "neutral": "Neutral",
    "negative": "Negative",
}
CANONICAL_COLUMNS = [
    "date",
    "layanan",
    "platform",
    "username",
    "followers",
    "content",
    "predicted_sentiment",
    "confidence",
    "topic",
]
COLUMN_ALIASES = {
    "date": ["date", "date_created", "tanggal", "created_at", "timestamp"],
    "layanan": ["layanan", "service", "object_group"],
    "platform": [
        "platform",
        "specific_resource_type",
        "source_platform",
        "resource_type",
    ],
    "username": [
        "username",
        "from_username",
        "user",
        "screen_name",
        "author",
    ],
    "followers": [
        "followers",
        "follower_count",
        "followers_count",
        "author_followers",
    ],
    "content": [
        "content",
        "text",
        "full_text",
        "komentar",
        "comment",
        "tweet_text",
        "caption",
    ],
    "predicted_sentiment": [
        "predicted_sentiment",
        "final_sentiment",
        "sentiment",
        "sentimen",
        "label",
    ],
    "confidence": [
        "confidence",
        "confidence_score",
        "sentiment_confidence_level",
        "score",
        "probability",
    ],
    "topic": ["topic", "topik", "topic_name"],
}
SENTIMENT_MAP = {
    "label_0": "positive",
    "positif": "positive",
    "positive": "positive",
    "label_1": "neutral",
    "netral": "neutral",
    "neutral": "neutral",
    "label_2": "negative",
    "negatif": "negative",
    "negative": "negative",
}
PLATFORM_MAP = {
    "twitter": "twitter",
    "twitter/x": "twitter",
    "x": "twitter",
    "instagram": "instagram",
    "ig": "instagram",
    "tiktok": "tiktok",
    "tik tok": "tiktok",
}
MONTH_NAMES = {
    1: "Jan",
    2: "Feb",
    3: "Mar",
    4: "Apr",
    5: "Mei",
    6: "Jun",
    7: "Jul",
    8: "Agu",
    9: "Sep",
    10: "Okt",
    11: "Nov",
    12: "Des",
}

SERVICE_KEY = "dataset_filter_service_input"
PLATFORM_KEY = "dataset_filter_platform_input"
DATE_KEY = "dataset_filter_dates_input"
SENTIMENT_KEY = "dataset_filter_sentiment_input"
LAST_SERVICE_KEY = "dataset_filter_last_service"
APPLIED_KEY = "dataset_applied_filters"
PAGE_KEY = "dataset_current_page"
ROWS_KEY = "dataset_rows_per_page"


def _project_root() -> Path:
    """Kembalikan direktori root proyek secara aman."""
    return Path(__file__).resolve().parent.parent


def _clean_text_series(series: pd.Series) -> pd.Series:
    """Bersihkan apostrof pembuka dan spasi tanpa mengubah isi utama teks."""
    result = series.where(series.notna(), "").astype(str).str.strip()
    return result.str.replace(r"^[\'\"]+", "", regex=True).str.strip()


def _parse_dates(series: pd.Series) -> pd.Series:
    """Konversi beragam format tanggal menjadi datetime secara defensif."""
    if pd.api.types.is_datetime64_any_dtype(series):
        return pd.to_datetime(series, errors="coerce")

    raw = _clean_text_series(series)
    parsed = pd.to_datetime(raw, format="%d/%m/%Y %H.%M.%S", errors="coerce")
    missing = parsed.isna() & raw.ne("")
    if missing.any():
        parsed.loc[missing] = pd.to_datetime(
            raw.loc[missing],
            errors="coerce",
            dayfirst=True,
            format="mixed",
        )
    return parsed


def _parse_followers(series: pd.Series) -> pd.Series:
    """Konversi followers menjadi bilangan bulat dan ubah nilai invalid menjadi nol."""
    if pd.api.types.is_numeric_dtype(series):
        return pd.to_numeric(series, errors="coerce").fillna(0).clip(lower=0).round().astype(int)

    def parse_value(value: Any) -> int:
        text = str(value or "").strip().lstrip("'\"")
        if not text or text.lower() in {"nan", "none", "null", "-"}:
            return 0
        text = text.replace(" ", "")
        if re.fullmatch(r"\d{1,3}([.,]\d{3})+", text):
            text = text.replace(".", "").replace(",", "")
        else:
            text = text.replace(",", "")
        try:
            return max(0, int(round(float(text))))
        except (TypeError, ValueError):
            return 0

    return series.map(parse_value).astype(int)


def _parse_confidence(series: pd.Series) -> pd.Series:
    """Normalisasi confidence dari skala 0–1 atau 0–100 ke skala 0–1."""
    raw = _clean_text_series(series).str.replace("%", "", regex=False)
    numeric = pd.to_numeric(raw, errors="coerce")
    numeric = numeric.mask((numeric > 1) & (numeric <= 100), numeric / 100)
    numeric = numeric.mask((numeric < 0) | (numeric > 1))
    return numeric.astype(float)


def _normalize_dataset(df: pd.DataFrame, layanan: str) -> pd.DataFrame:
    """Normalisasi DataFrame ke kontrak kolom kanonik halaman Dataset."""
    if df is None or df.empty:
        return pd.DataFrame(columns=CANONICAL_COLUMNS)

    result = df.copy()
    lower_columns = {str(column).strip().lower(): column for column in result.columns}
    rename_map: dict[str, str] = {}
    for canonical, aliases in COLUMN_ALIASES.items():
        for alias in aliases:
            source = lower_columns.get(alias.lower())
            if source is not None:
                rename_map[source] = canonical
                break
    result = result.rename(columns=rename_map)

    for column in CANONICAL_COLUMNS:
        if column not in result.columns:
            if column in {"followers"}:
                result[column] = 0
            elif column in {"confidence"}:
                result[column] = pd.NA
            elif column == "layanan":
                result[column] = layanan
            elif column == "topic":
                result[column] = "Belum Diklasifikasikan"
            else:
                result[column] = ""

    result["date"] = _parse_dates(result["date"])
    result["layanan"] = layanan
    result["username"] = _clean_text_series(result["username"])
    result["content"] = _clean_text_series(result["content"])
    result["followers"] = _parse_followers(result["followers"])
    result["confidence"] = _parse_confidence(result["confidence"])

    platform_raw = _clean_text_series(result["platform"]).str.lower()
    result["platform"] = platform_raw.map(PLATFORM_MAP)

    sentiment_raw = _clean_text_series(result["predicted_sentiment"]).str.lower()
    result["predicted_sentiment"] = sentiment_raw.map(SENTIMENT_MAP)

    result["topic"] = _clean_text_series(result["topic"])
    result.loc[result["topic"].isin(["", "nan", "none", "null", "-"]), "topic"] = (
        "Belum Diklasifikasikan"
    )

    result = result[result["platform"].isin(PLATFORM_ORDER)].copy()
    result = result[result["predicted_sentiment"].isin(SENTIMENT_ORDER)].copy()
    result = result[CANONICAL_COLUMNS].reset_index(drop=True)
    return result


def _candidate_data_files(layanan: str) -> list[Path]:
    """Susun kandidat file data aktual CSV atau CSV.GZ untuk suatu layanan."""
    slug = layanan.lower().replace(" ", "")
    roots = [_project_root() / "data", _project_root() / "data" / "data"]
    candidates: list[Path] = []

    for data_dir in roots:
        candidates.extend(
            [
                data_dir / f"{slug}_sentiment.csv",
                data_dir / f"{slug}_sentiment.csv.gz",
            ]
        )
        if data_dir.exists():
            for file_path in sorted(data_dir.glob(f"*{slug}*.csv*")):
                if "sna" not in file_path.name.lower():
                    candidates.append(file_path)

    unique: list[Path] = []
    seen: set[str] = set()
    for candidate in candidates:
        key = str(candidate.resolve()) if candidate.exists() else str(candidate)
        if key not in seen:
            seen.add(key)
            unique.append(candidate)
    return unique


def _select_source_columns(columns: list[str]) -> list[str]:
    """Pilih hanya kolom sumber yang diperlukan agar pemuatan file lebih ringan."""
    lower_columns = {str(column).strip().lower(): column for column in columns}
    selected: list[str] = []
    for aliases in COLUMN_ALIASES.values():
        for alias in aliases:
            source = lower_columns.get(alias.lower())
            if source is not None:
                selected.append(source)
                break
    return list(dict.fromkeys(selected))


def _read_header(path: str) -> pd.DataFrame:
    """Baca header file CSV dengan fallback encoding."""
    for encoding in ("utf-8-sig", "utf-8", "latin-1"):
        try:
            return pd.read_csv(path, nrows=0, compression="infer", encoding=encoding)
        except (UnicodeDecodeError, pd.errors.ParserError):
            continue
    raise ValueError("Header file dataset tidak dapat dibaca.")


@st.cache_data(show_spinner=False)
def _read_actual_dataset(
    path: str,
    layanan: str,
    file_size: int,
    modified_ns: int,
) -> pd.DataFrame:
    """Baca dan normalisasi dataset aktual; signature file menjaga cache tetap valid."""
    del file_size, modified_ns
    header = _read_header(path)
    usecols = _select_source_columns(list(header.columns))
    if not usecols:
        raise ValueError("Tidak ada kolom dataset yang dikenali.")

    last_error: Exception | None = None
    read_attempts = [
        {
            "engine": "c",
            "encoding": "utf-8-sig",
            "low_memory": False,
            "on_bad_lines": "skip",
        },
        {
            "engine": "python",
            "encoding": "utf-8-sig",
            "on_bad_lines": "skip",
        },
        {
            "engine": "python",
            "encoding": "latin-1",
            "on_bad_lines": "skip",
        },
    ]
    for options in read_attempts:
        try:
            raw = pd.read_csv(
                path,
                compression="infer",
                usecols=usecols,
                **options,
            )
            return _normalize_dataset(raw, layanan)
        except Exception as exc:  # fallback parser memang membutuhkan cakupan luas
            last_error = exc

    raise ValueError("Isi file dataset tidak dapat dibaca.") from last_error


@st.cache_data(show_spinner=False)
def _load_dummy_dataset(layanan: str) -> pd.DataFrame:
    """Buat data dummy ter-cache agar hasil stabil pada setiap rerun."""
    return _normalize_dataset(get_dummy_sentiment_data(layanan), layanan)


def _load_service_dataset(layanan: str) -> tuple[pd.DataFrame, bool, str]:
    """Muat data aktual bila tersedia, lalu fallback ke dummy saat diperlukan."""
    for candidate in _candidate_data_files(layanan):
        if not candidate.is_file():
            continue
        try:
            stat = candidate.stat()
            dataframe = _read_actual_dataset(
                str(candidate),
                layanan,
                stat.st_size,
                stat.st_mtime_ns,
            )
            if not dataframe.empty:
                return dataframe.copy(), True, candidate.name
        except Exception:
            LOGGER.exception("Gagal membaca dataset aktual untuk %s", layanan)

    try:
        return _load_dummy_dataset(layanan).copy(), False, "Data fallback bawaan"
    except Exception:
        LOGGER.exception("Gagal membuat data dummy untuk %s", layanan)
        return pd.DataFrame(columns=CANONICAL_COLUMNS), False, "Data tidak tersedia"


def _available_platform_labels(df: pd.DataFrame) -> list[str]:
    """Kembalikan pilihan platform berurutan yang tersedia pada DataFrame."""
    if df.empty or "platform" not in df.columns:
        return []
    values = set(df["platform"].dropna().astype(str).str.lower())
    return [PLATFORM_LABELS[key] for key in PLATFORM_ORDER if key in values]


def _available_sentiments(df: pd.DataFrame) -> list[str]:
    """Kembalikan pilihan sentimen berurutan yang tersedia pada DataFrame."""
    if df.empty or "predicted_sentiment" not in df.columns:
        return []
    values = set(df["predicted_sentiment"].dropna().astype(str).str.lower())
    return [sentiment for sentiment in SENTIMENT_ORDER if sentiment in values]


def _date_limits(df: pd.DataFrame) -> tuple[date, date] | None:
    """Ambil tanggal minimum dan maksimum yang valid dari DataFrame."""
    if df.empty or "date" not in df.columns:
        return None
    valid_dates = pd.to_datetime(df["date"], errors="coerce").dropna()
    if valid_dates.empty:
        return None
    return valid_dates.min().date(), valid_dates.max().date()


def _initialize_base_state() -> None:
    """Inisialisasi state utama halaman Dataset."""
    defaults = {
        SERVICE_KEY: "IndiHome",
        LAST_SERVICE_KEY: None,
        APPLIED_KEY: None,
        PAGE_KEY: 1,
        ROWS_KEY: 10,
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


def _reset_filters_callback() -> None:
    """Kembalikan seluruh filter dan pagination ke kondisi awal."""
    for key in (PLATFORM_KEY, DATE_KEY, SENTIMENT_KEY):
        st.session_state.pop(key, None)
    st.session_state[SERVICE_KEY] = "IndiHome"
    st.session_state[LAST_SERVICE_KEY] = None
    st.session_state[APPLIED_KEY] = None
    st.session_state[PAGE_KEY] = 1
    st.session_state[ROWS_KEY] = 10


def _change_page_callback(delta: int) -> None:
    """Geser halaman tabel melalui callback agar state widget tetap aman."""
    current = int(st.session_state.get(PAGE_KEY, 1))
    st.session_state[PAGE_KEY] = max(1, current + delta)


def _reset_dependent_inputs(
    layanan: str,
    platform_options: list[str],
    sentiment_options: list[str],
    limits: tuple[date, date] | None,
) -> None:
    """Reset input turunan ketika layanan pada filter diubah."""
    st.session_state[PLATFORM_KEY] = list(platform_options)
    st.session_state[SENTIMENT_KEY] = list(sentiment_options)
    if limits:
        st.session_state[DATE_KEY] = limits
    elif DATE_KEY in st.session_state:
        del st.session_state[DATE_KEY]
    st.session_state[LAST_SERVICE_KEY] = layanan
    st.session_state[PAGE_KEY] = 1


def _current_filter_config(
    layanan: str,
    date_available: bool,
) -> dict[str, Any]:
    """Bangun konfigurasi filter dari nilai widget saat ini."""
    selected_labels = list(st.session_state.get(PLATFORM_KEY, []))
    platforms = [PLATFORM_KEYS[label] for label in selected_labels if label in PLATFORM_KEYS]
    sentiments = list(st.session_state.get(SENTIMENT_KEY, []))

    date_range: tuple[date, date] | None = None
    if date_available:
        raw_dates = st.session_state.get(DATE_KEY)
        if isinstance(raw_dates, (tuple, list)) and len(raw_dates) == 2:
            date_range = (raw_dates[0], raw_dates[1])
        elif isinstance(raw_dates, date):
            date_range = (raw_dates, raw_dates)

    return {
        "layanan": layanan,
        "platforms": platforms,
        "sentiments": sentiments,
        "date_range": date_range,
    }


def _apply_filters(df: pd.DataFrame, filters: dict[str, Any]) -> pd.DataFrame:
    """Terapkan seluruh filter aktif pada satu salinan DataFrame."""
    result = df.copy()
    try:
        platforms = filters.get("platforms", [])
        sentiments = filters.get("sentiments", [])
        date_range = filters.get("date_range")

        if platforms:
            result = result[result["platform"].isin(platforms)].copy()
        else:
            return result.iloc[0:0].copy()

        if sentiments:
            result = result[result["predicted_sentiment"].isin(sentiments)].copy()
        else:
            return result.iloc[0:0].copy()

        if date_range:
            start_date, end_date = date_range
            if start_date > end_date:
                start_date, end_date = end_date, start_date
            dates = pd.to_datetime(result["date"], errors="coerce").dt.date
            result = result[(dates >= start_date) & (dates <= end_date)].copy()

        return result.reset_index(drop=True)
    except Exception:
        LOGGER.exception("Gagal menerapkan filter dataset")
        st.error("Filter belum dapat diterapkan. Silakan atur ulang pilihan filter.")
        return df.iloc[0:0].copy()


def _format_integer(value: int | float) -> str:
    """Format angka menggunakan pemisah ribuan gaya Indonesia."""
    try:
        return f"{int(value):,}".replace(",", ".")
    except (TypeError, ValueError):
        return "0"


def _truncate_text(value: Any, max_length: int = 130) -> str:
    """Potong teks panjang khusus untuk tampilan tabel."""
    text = str(value or "").strip()
    if not text or text.lower() in {"nan", "none"}:
        return "-"
    return text if len(text) <= max_length else f"{text[: max_length - 3].rstrip()}..."


def _prepare_display_table(df: pd.DataFrame, start_number: int) -> pd.DataFrame:
    """Siapkan tabel tampilan tanpa mengubah teks asli pada DataFrame sumber."""
    table = pd.DataFrame()
    table["No"] = range(start_number, start_number + len(df))
    dates = pd.to_datetime(df["date"], errors="coerce")
    table["Tanggal"] = dates.dt.strftime("%d-%m-%Y %H:%M").fillna("-")
    table["Platform"] = df["platform"].map(PLATFORM_LABELS).fillna("-")
    table["Username"] = df["username"].map(
        lambda value: str(value).strip() if str(value).strip() else "-"
    )
    table["Followers"] = df["followers"].map(_format_integer)
    table["Content"] = df["content"].map(_truncate_text)
    table["Sentimen"] = df["predicted_sentiment"].map(SENTIMENT_LABELS).fillna("-")
    table["Confidence"] = df["confidence"].map(
        lambda value: f"{float(value) * 100:.1f}%" if pd.notna(value) else "N/A"
    )
    table["Topik"] = df["topic"].map(
        lambda value: str(value).strip() if str(value).strip() else "Belum Diklasifikasikan"
    )
    return table


def _style_sentiment(value: str) -> str:
    """Berikan highlight lembut hanya pada sel sentimen."""
    styles = {
        "Positive": "background-color:#dff3e3;color:#1b5e20;font-weight:600;",
        "Neutral": "background-color:#fff0d6;color:#8a4b00;font-weight:600;",
        "Negative": "background-color:#fde1df;color:#b71c1c;font-weight:600;",
    }
    return styles.get(str(value), "")


def _prepare_export_data(df: pd.DataFrame) -> pd.DataFrame:
    """Siapkan data kanonik penuh untuk CSV dan Excel tanpa index."""
    export_df = df[CANONICAL_COLUMNS].copy()
    export_df["date"] = pd.to_datetime(export_df["date"], errors="coerce").dt.strftime(
        "%Y-%m-%d %H:%M:%S"
    )
    export_df["date"] = export_df["date"].fillna("")
    return export_df


@st.cache_data(show_spinner=False)
def _build_export_bytes(df: pd.DataFrame) -> tuple[bytes, bytes]:
    """Bangun bytes CSV dan Excel dari subset terfilter."""
    export_df = _prepare_export_data(df)
    csv_bytes = export_to_csv(export_df, "dataset_filtered")
    excel_bytes = export_to_excel(export_df, "dataset_filtered", sheet_name="Dataset Filtered")
    return csv_bytes, excel_bytes


def _category_statistics(df: pd.DataFrame, column: str) -> pd.DataFrame:
    """Hitung jumlah dan persentase untuk satu kolom kategorikal."""
    if df.empty or column not in df.columns:
        return pd.DataFrame(columns=["Kategori", "Jumlah", "Persentase"])

    values = df[column].where(df[column].notna(), "-").astype(str).str.strip()
    values = values.replace({"": "-", "nan": "-", "None": "-"})
    counts = values.value_counts(dropna=False)
    result = counts.rename_axis("Kategori").reset_index(name="Jumlah")
    result["Persentase"] = (result["Jumlah"] / len(df) * 100).map(lambda x: f"{x:.1f}%")
    return result


def _dominant_value(series: pd.Series, labels: dict[str, str] | None = None) -> str:
    """Ambil nilai dominan dan tandai Seimbang ketika frekuensi tertinggi seri."""
    values = series.dropna().astype(str)
    if values.empty:
        return "N/A"
    counts = values.value_counts()
    top_count = counts.iloc[0]
    winners = sorted(counts[counts == top_count].index.tolist())
    if len(winners) > 1:
        return "Seimbang"
    winner = winners[0]
    return labels.get(winner, winner) if labels else winner


def _platform_pie_chart(df: pd.DataFrame) -> go.Figure:
    """Buat pie chart distribusi platform."""
    counts = (
        df["platform"]
        .value_counts()
        .reindex(PLATFORM_ORDER, fill_value=0)
        .reset_index()
    )
    counts.columns = ["platform", "jumlah"]
    counts = counts[counts["jumlah"] > 0]
    labels = counts["platform"].map(PLATFORM_LABELS)
    colors = [PLATFORM_COLORS.get(key, "#1DA1F2") for key in counts["platform"]]

    fig = go.Figure(
        go.Pie(
            labels=labels,
            values=counts["jumlah"],
            marker={"colors": colors},
            textinfo="label+percent",
            hovertemplate="%{label}: %{value} data (%{percent})<extra></extra>",
        )
    )
    fig.update_layout(
        title="Distribusi Platform",
        paper_bgcolor="rgba(0,0,0,0)",
        margin={"l": 20, "r": 20, "t": 60, "b": 20},
        legend={"orientation": "h", "yanchor": "bottom", "y": 1.02},
    )
    return fig


def _monthly_distribution_chart(df: pd.DataFrame) -> go.Figure | None:
    """Buat bar chart bulanan yang diurutkan kronologis."""
    valid_dates = pd.to_datetime(df["date"], errors="coerce")
    if valid_dates.dropna().empty:
        return None

    monthly = (
        valid_dates.dropna()
        .dt.to_period("M")
        .value_counts()
        .sort_index()
        .rename_axis("periode")
        .reset_index(name="jumlah")
    )
    monthly["label"] = monthly["periode"].map(
        lambda period: f"{MONTH_NAMES[int(period.month)]} {int(period.year)}"
    )

    fig = go.Figure(
        go.Bar(
            x=monthly["label"],
            y=monthly["jumlah"],
            marker_color="#1DA1F2",
            text=monthly["jumlah"],
            textposition="outside",
            hovertemplate="%{x}: %{y} data<extra></extra>",
        )
    )
    fig.update_layout(
        title="Distribusi Data per Bulan",
        xaxis_title="Bulan",
        yaxis_title="Jumlah Data",
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        margin={"l": 40, "r": 20, "t": 60, "b": 40},
    )
    fig.update_xaxes(showgrid=False)
    fig.update_yaxes(gridcolor="rgba(128,128,128,0.15)")
    return fig


def _render_source_status(is_real: bool, layanan: str, source_name: str) -> None:
    """Tampilkan badge sumber data dan layanan aktif."""
    badge_class = "dataset-real" if is_real else "dataset-dummy"
    badge_text = "📁 Data Nyata" if is_real else "🎭 Data Dummy"
    safe_service = layanan.replace("<", "&lt;").replace(">", "&gt;")
    safe_source = source_name.replace("<", "&lt;").replace(">", "&gt;")
    st.markdown(
        f"""
        <style>
            .dataset-status-wrap {{
                display:flex; flex-wrap:wrap; gap:0.55rem; align-items:center;
                margin:-0.25rem 0 1rem 0;
            }}
            .dataset-status-badge {{
                display:inline-flex; align-items:center; border-radius:999px;
                padding:0.38rem 0.78rem; font-weight:700; font-size:0.86rem;
                border:1px solid transparent;
            }}
            .dataset-real {{background:#e3f4e7;color:#1b5e20;border-color:#81c784;}}
            .dataset-dummy {{background:#fff0d9;color:#8a4b00;border-color:#ffb74d;}}
            .dataset-service {{
                display:inline-flex; align-items:center; border-radius:999px;
                padding:0.38rem 0.78rem; font-weight:600; font-size:0.86rem;
                background:rgba(29,161,242,0.12); border:1px solid rgba(29,161,242,0.45);
            }}
        </style>
        <div class="dataset-status-wrap">
            <span class="dataset-status-badge {badge_class}">{badge_text}</span>
            <span class="dataset-service">📡 Layanan aktif: {safe_service}</span>
            <span style="font-size:0.82rem;opacity:0.75;">Sumber: {safe_source}</span>
        </div>
        """,
        unsafe_allow_html=True,
    )


def _render_filters() -> tuple[dict[str, Any], dict[str, Any]]:
    """Render filter draft dan kembalikan filter draft serta filter aktif."""
    _initialize_base_state()

    with st.expander("🔎 Filter Dataset", expanded=True):
        service = st.selectbox(
            "Pilih Layanan",
            options=SERVICES,
            key=SERVICE_KEY,
            help="Pilih layanan yang datanya ingin dieksplorasi.",
        )

        draft_df, _, _ = _load_service_dataset(service)
        platform_options = _available_platform_labels(draft_df)
        sentiment_options = _available_sentiments(draft_df)
        limits = _date_limits(draft_df)

        if st.session_state.get(LAST_SERVICE_KEY) != service:
            _reset_dependent_inputs(
                service,
                platform_options,
                sentiment_options,
                limits,
            )

        if PLATFORM_KEY not in st.session_state:
            st.session_state[PLATFORM_KEY] = list(platform_options)
        if SENTIMENT_KEY not in st.session_state:
            st.session_state[SENTIMENT_KEY] = list(sentiment_options)
        current_platforms = list(st.session_state.get(PLATFORM_KEY, []))
        valid_platforms = [value for value in current_platforms if value in platform_options]
        if valid_platforms != current_platforms:
            st.session_state[PLATFORM_KEY] = valid_platforms

        current_sentiments = list(st.session_state.get(SENTIMENT_KEY, []))
        valid_sentiments = [value for value in current_sentiments if value in sentiment_options]
        if valid_sentiments != current_sentiments:
            st.session_state[SENTIMENT_KEY] = valid_sentiments

        if limits:
            current_dates = st.session_state.get(DATE_KEY)
            date_is_valid = (
                isinstance(current_dates, (tuple, list))
                and len(current_dates) == 2
                and limits[0] <= current_dates[0] <= limits[1]
                and limits[0] <= current_dates[1] <= limits[1]
            )
            if not date_is_valid:
                st.session_state[DATE_KEY] = limits

        col_platform, col_sentiment = st.columns(2)
        with col_platform:
            st.multiselect(
                "Pilih Platform",
                options=platform_options,
                key=PLATFORM_KEY,
                help="Kosongkan pilihan untuk menghasilkan data kosong secara sengaja.",
            )
        with col_sentiment:
            st.multiselect(
                "Filter Sentimen",
                options=sentiment_options,
                key=SENTIMENT_KEY,
                help="Urutan sentimen dijaga: positive, neutral, negative.",
            )

        if limits:
            st.date_input(
                "Rentang Tanggal",
                min_value=limits[0],
                max_value=limits[1],
                key=DATE_KEY,
                format="DD/MM/YYYY",
            )
        else:
            st.info("Filter tanggal tidak tersedia karena seluruh tanggal kosong atau tidak valid.")

        draft_filters = _current_filter_config(service, limits is not None)
        if st.session_state.get(APPLIED_KEY) is None:
            st.session_state[APPLIED_KEY] = draft_filters

        active_filters = st.session_state.get(APPLIED_KEY, draft_filters)
        if draft_filters != active_filters:
            st.caption("ℹ️ Ada perubahan filter yang belum diterapkan.")

        action_apply, action_reset, action_space = st.columns([1, 1, 4])
        with action_apply:
            if st.button(
                "Terapkan Filter",
                type="primary",
                use_container_width=True,
                key="dataset_apply_filter",
            ):
                st.session_state[APPLIED_KEY] = draft_filters
                st.session_state[PAGE_KEY] = 1
                st.rerun()
        with action_reset:
            st.button(
                "Reset",
                use_container_width=True,
                key="dataset_reset_filter",
                on_click=_reset_filters_callback,
            )

    return draft_filters, st.session_state.get(APPLIED_KEY, draft_filters)


def _render_table_tab(filtered_df: pd.DataFrame, layanan: str) -> None:
    """Render tabel data, pagination, dan tombol ekspor."""
    try:
        if filtered_df.empty:
            st.info(
                "Tidak ada data yang sesuai dengan filter yang dipilih.\n\n"
                "Silakan ubah layanan, platform, rentang tanggal, atau sentimen."
            )
            return

        control_col, info_col = st.columns([1, 3])
        with control_col:
            rows_per_page = st.selectbox(
                "Baris per halaman",
                options=[10, 25, 50],
                key=ROWS_KEY,
            )

        total_pages = max(1, math.ceil(len(filtered_df) / rows_per_page))
        current_page = int(st.session_state.get(PAGE_KEY, 1))
        current_page = min(max(current_page, 1), total_pages)
        st.session_state[PAGE_KEY] = current_page

        with info_col:
            st.markdown(
                f"<div style='text-align:right;padding-top:2rem;font-weight:600;'>"
                f"Halaman {current_page} dari {total_pages}</div>",
                unsafe_allow_html=True,
            )

        nav_prev, nav_page, nav_next = st.columns([1, 2, 1])
        with nav_prev:
            st.button(
                "← Sebelumnya",
                disabled=current_page <= 1,
                use_container_width=True,
                key="dataset_prev_page",
                on_click=_change_page_callback,
                args=(-1,),
            )
        with nav_page:
            st.number_input(
                "Pilih nomor halaman",
                min_value=1,
                max_value=total_pages,
                step=1,
                key=PAGE_KEY,
            )
        with nav_next:
            st.button(
                "Berikutnya →",
                disabled=current_page >= total_pages,
                use_container_width=True,
                key="dataset_next_page",
                on_click=_change_page_callback,
                args=(1,),
            )

        current_page = int(st.session_state.get(PAGE_KEY, 1))
        current_page = min(max(current_page, 1), total_pages)
        start_idx = (current_page - 1) * rows_per_page
        end_idx = min(start_idx + rows_per_page, len(filtered_df))
        page_df = filtered_df.iloc[start_idx:end_idx].copy()
        display_df = _prepare_display_table(page_df, start_idx + 1)
        styled = display_df.style.map(_style_sentiment, subset=["Sentimen"])

        st.dataframe(
            styled,
            use_container_width=True,
            height=min(700, 42 * len(display_df) + 42),
        )
        st.caption(f"Menampilkan baris {start_idx + 1}–{end_idx} dari {_format_integer(len(filtered_df))} data.")

        st.markdown("#### Export Data Terfilter")
        try:
            with st.spinner("Menyiapkan file CSV dan Excel..."):
                csv_bytes, excel_bytes = _build_export_bytes(filtered_df)
            today = datetime.now().strftime("%Y-%m-%d")
            safe_service = layanan.lower().replace(" ", "_")
            base_name = f"dataset_{safe_service}_filtered_{today}"
            export_csv, export_excel = st.columns(2)
            with export_csv:
                st.download_button(
                    "⬇️ Download CSV",
                    data=csv_bytes,
                    file_name=f"{base_name}.csv",
                    mime="text/csv",
                    use_container_width=True,
                    key="dataset_download_csv",
                )
            with export_excel:
                st.download_button(
                    "⬇️ Download Excel (.xlsx)",
                    data=excel_bytes,
                    file_name=f"{base_name}.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    use_container_width=True,
                    key="dataset_download_excel",
                )
        except Exception:
            LOGGER.exception("Gagal menyiapkan file export dataset")
            st.error("File ekspor belum dapat dibuat. Silakan coba lagi setelah memeriksa data.")
    except Exception:
        LOGGER.exception("Gagal merender tab tabel dataset")
        st.error("Tabel data belum dapat ditampilkan.")


def _render_summary_tab(filtered_df: pd.DataFrame) -> None:
    """Render metric, bar chart platform, dan statistik kategorikal."""
    try:
        if filtered_df.empty:
            st.info(
                "Tidak ada data yang sesuai dengan filter yang dipilih.\n\n"
                "Silakan ubah layanan, platform, rentang tanggal, atau sentimen."
            )
            return

        confidence = pd.to_numeric(filtered_df["confidence"], errors="coerce").dropna()
        avg_confidence = f"{confidence.mean() * 100:.1f}%" if not confidence.empty else "N/A"
        platform_dominant = _dominant_value(filtered_df["platform"], PLATFORM_LABELS)
        sentiment_dominant = _dominant_value(
            filtered_df["predicted_sentiment"],
            SENTIMENT_LABELS,
        )

        metric_total, metric_conf, metric_platform, metric_sentiment = st.columns(4)
        metric_total.metric("Total Data", _format_integer(len(filtered_df)))
        metric_conf.metric("Rata-rata Confidence", avg_confidence)
        metric_platform.metric("Platform Terbanyak", platform_dominant)
        metric_sentiment.metric("Sentimen Dominan", sentiment_dominant)

        st.plotly_chart(
            bar_chart_platform(filtered_df, "Distribusi Platform"),
            use_container_width=True,
            config={"displaylogo": False},
        )

        st.markdown("#### Statistik Kategorikal")
        tabs = st.tabs(["Platform", "Sentimen", "Topik"])
        category_specs = [
            ("platform", PLATFORM_LABELS),
            ("predicted_sentiment", SENTIMENT_LABELS),
            ("topic", None),
        ]
        for tab, (column, labels) in zip(tabs, category_specs):
            with tab:
                stats = _category_statistics(filtered_df, column)
                if stats.empty:
                    st.info(f"Statistik {column} belum tersedia.")
                else:
                    if labels:
                        stats["Kategori"] = stats["Kategori"].map(
                            lambda value: labels.get(value, value)
                        )
                    st.dataframe(stats, use_container_width=True, hide_index=True)
    except Exception:
        LOGGER.exception("Gagal merender ringkasan statistik")
        st.error("Ringkasan statistik belum dapat ditampilkan.")


def _render_distribution_tab(filtered_df: pd.DataFrame) -> None:
    """Render pie platform, distribusi bulanan, dan sentimen per platform."""
    try:
        if filtered_df.empty:
            st.info(
                "Tidak ada data yang sesuai dengan filter yang dipilih.\n\n"
                "Silakan ubah layanan, platform, rentang tanggal, atau sentimen."
            )
            return

        st.plotly_chart(
            _platform_pie_chart(filtered_df),
            use_container_width=True,
            config={"displaylogo": False},
        )

        monthly_fig = _monthly_distribution_chart(filtered_df)
        if monthly_fig is None:
            st.info("Distribusi bulanan tidak dapat dibuat karena tanggal tidak tersedia.")
        else:
            st.plotly_chart(
                monthly_fig,
                use_container_width=True,
                config={"displaylogo": False},
            )

        st.plotly_chart(
            grouped_bar_platform_sentiment(
                filtered_df,
                "Distribusi Sentimen per Platform",
            ),
            use_container_width=True,
            config={"displaylogo": False},
        )
    except Exception:
        LOGGER.exception("Gagal merender distribusi dataset")
        st.error("Visualisasi distribusi belum dapat ditampilkan.")


def render_dataset() -> None:
    """Render halaman Dataset lengkap dengan filter, tabel, statistik, dan ekspor."""
    try:
        render_page_header(
            "📂 Dataset Penelitian",
            "Eksplorasi, penyaringan, dan ringkasan data percakapan media sosial.",
        )

        _initialize_base_state()
        initial_active = st.session_state.get(APPLIED_KEY) or {
            "layanan": st.session_state.get(SERVICE_KEY, "IndiHome")
        }
        active_service = str(initial_active.get("layanan", "IndiHome"))

        with st.spinner(f"Memuat dataset {active_service}..."):
            source_df, is_real, source_name = _load_service_dataset(active_service)

        _render_source_status(is_real, active_service, source_name)
        _, active_filters = _render_filters()
        active_service = str(active_filters.get("layanan", active_service))

        if source_df.empty:
            st.error(
                "Data belum dapat ditampilkan. Silakan periksa file dataset atau hubungi administrator."
            )
            return

        filtered_df = _apply_filters(source_df, active_filters)
        st.info(
            f"Menampilkan **{_format_integer(len(filtered_df))}** dari "
            f"**{_format_integer(len(source_df))}** total data untuk layanan "
            f"**{active_service}**."
        )

        tab_table, tab_summary, tab_distribution = st.tabs(
            ["📋 Tabel Data", "📊 Ringkasan Statistik", "📈 Distribusi"]
        )
        with tab_table:
            _render_table_tab(filtered_df, active_service)
        with tab_summary:
            _render_summary_tab(filtered_df)
        with tab_distribution:
            _render_distribution_tab(filtered_df)
    except Exception:
        LOGGER.exception("Gagal memuat halaman Dataset")
        st.error(
            "Data belum dapat ditampilkan. Silakan periksa file dataset atau hubungi administrator."
        )
