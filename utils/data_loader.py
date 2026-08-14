# utils/data_loader.py
# TAHAP 5 FASE 12 - STATUS MODEL BERBASIS HUGGINGFACE HUB.
# TAHAP 5 FASE 7 - OPTIMASI PERFORMA: cache boundary loader publik tanpa mengubah parser atau fallback.
"""Pemuat, normalisasi, dan filter data CSV sentimen serta SNA."""

import json
import os
import zipfile
from datetime import datetime
from io import BytesIO
from pathlib import Path

import pandas as pd
import streamlit as st

from utils.dummy_data import (
    get_dummy_indibiz_sentiment,
    get_dummy_indibiz_sna,
    get_dummy_indibiz_top_kata,
    get_dummy_indibiz_topics,
    get_dummy_sentiment_data,
    get_dummy_sna_data,
    get_dummy_telkomsel_sna,
)
from utils.indibiz_config import (
    INDIBIZ_SENTIMENT_CANDIDATES,
    INDIBIZ_SNA_CANDIDATES,
    OUTPUT_FILES as INDIBIZ_OUTPUT_FILES,
)
from utils.indihome_output import (
    INDIHOME_CANONICAL_OUTPUT_NAME,
    INDIHOME_OUTPUT_CANDIDATES,
    inspect_indihome_output,
    resolve_indihome_output,
    resolve_indihome_raw_source,
)
from utils.preprocessor import (
    clean_text,
    prepare_indibiz_indobert_dataframe,
    prepare_telkomsel_sentiment_dataframe,
)

CANONICAL_SENTIMENT_COLS = {
    "date": ["date", "date_created", "created_at", "timestamp"],
    "platform": ["platform", "specific_resource_type", "source_platform"],
    "username": ["username", "from_username", "user", "screen_name"],
    "followers": ["followers", "follower_count", "followers_count"],
    "content": ["content", "text", "comment", "tweet_text", "caption"],
    "predicted_sentiment": ["predicted_sentiment", "final_sentiment", "sentiment", "label"],
    "confidence": ["confidence", "confidence_score", "score", "sentiment_confidence_level"],
    "content_clean": ["content_clean", "cleaned_text"],
}

CANONICAL_SNA_COLS = {
    "source": ["source", "vertex1", "from_username", "user_from"],
    "target": ["target", "vertex2", "to_username", "user_to"],
    "relationship": ["relationship", "relation", "type", "edge_type"],
    "followers": ["followers", "follower_count", "followers_count"],
    "platform": ["platform", "specific_resource_type", "source_platform", "media", "channel"],
    # Kolom berikut bersifat opsional. Kolom sentimen dipertahankan agar halaman
    # SNA dapat menentukan warna node berdasarkan sentimen dominan tanpa
    # mengubah kontrak minimum source-target-relationship.
    "sentiment": ["sentiment", "predicted_sentiment", "label", "sentimen"],
    "content": ["content", "text", "comment", "tweet_text", "caption"],
    "time": ["time", "date", "date_created", "timestamp", "created_at"],
}

# Path baku hasil pipeline sentimen Telkomsel untuk dashboard.
TELKOMSEL_CSV_PATH = "data/telkomsel_sentiment.csv"

DATA_FILES = {
    "IndiHome": {
        "sentiment": "data/indihome_sentiment.csv",
        "sna": "data/sna_data.csv",
    },
    "IndiBiz": {
        "sentiment": f"data/{INDIBIZ_OUTPUT_FILES['sentiment_csv']}",
        "sna": f"data/{INDIBIZ_OUTPUT_FILES['sna_csv']}",
    },
    "Telkomsel": {
        "sentiment": "data/telkomsel_sentiment.csv",
        "sna": "data/sna_data.csv",
    },
}

# Nama file alternatif yang memang digunakan pada dataset penelitian aktual.
# Urutan penting: nama standar CSV tetap diprioritaskan jika tersedia.
SENTIMENT_SOURCE_CANDIDATES = {
    # Khusus IndiHome, dashboard hanya memakai output prediksi Google Colab.
    # Dataset mentah berukuran besar tetap dapat digunakan pada halaman Dataset,
    # tetapi tidak diperlakukan sebagai hasil prediksi IndoBERT dashboard.
    "IndiHome": list(INDIHOME_OUTPUT_CANDIDATES),
    "IndiBiz": list(INDIBIZ_SENTIMENT_CANDIDATES),
    "Telkomsel": [
        "telkomsel_sentiment.csv",
        "telkomsel_sentiment.csv.gz",
        "output_sentiment.csv",
        "telkomsel_output_sentiment.csv",
        "Telkomsel Sentiment.csv",
        "Telkomsel-NovemberDesember.csv",
        "Telkomsel-NovemberDesember.zip",
        "Telkomsel NovemberDesember 2025.xlsx",
        "Telkomsel-NovemberDesember.xlsx",
    ],
}

SUPPORTED_SENTIMENT_EXTENSIONS = {".csv", ".gz", ".xlsx", ".xls", ".zip"}

# Kandidat sumber SNA aktual per layanan. File spesifik layanan ikut dibaca
# agar SNA IndiBiz/Telkomsel tidak harus digabung manual ke data/sna_data.csv.
SNA_SOURCE_CANDIDATES = {
    "IndiHome": [
        "sna_data.csv",
        "SNA Indihome November-Desember 2025 Gabungan.csv",
        "SNA Indihome November-Desember 2025 Gabungan.csv.gz",
        "SNA IndiHome November-Desember 2025 Gabungan.csv",
        "SNA Indihome.csv",
    ],
    "IndiBiz": [
        "sna_data.csv",
        *INDIBIZ_SNA_CANDIDATES,
    ],
    "Telkomsel": [
        "sna_data.csv",
        "df_edge_telkomsel.csv",
        "output_sna.csv",
        "telkomsel_sna.csv",
        "sna_telkomsel.csv",
        "SNA Telkomsel.csv",
        "SNA Telkomsel.csv.gz",
        "SNA Telkomsel NovemberDesember.csv",
    ],
}

SUPPORTED_SNA_EXTENSIONS = {".csv", ".gz", ".xlsx", ".xls", ".zip"}

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


def _data_dir() -> Path:
    """Kembalikan folder data proyek dan buat folder jika belum tersedia."""
    data_dir = _project_root() / "data"
    data_dir.mkdir(parents=True, exist_ok=True)
    return data_dir


def _resolve_sentiment_source(layanan: str) -> Path | None:
    """Cari file sentimen aktual untuk layanan dari CSV, Excel, atau ZIP."""
    try:
        service = layanan if layanan in SENTIMENT_SOURCE_CANDIDATES else "IndiHome"
        data_dir = _data_dir()

        # Output Google Colab IndiHome wajib memakai nama yang tidak ambigu.
        # Jangan memilih workbook mentah karena workbook tersebut bukan hasil
        # prediksi batch terbaru dan sangat berat dibaca pada setiap rerun.
        if service == "IndiHome":
            return resolve_indihome_output(data_dir)

        # 1) Cari berdasarkan nama kandidat resmi secara case-insensitive.
        files_by_lower = {
            path.name.lower(): path
            for path in data_dir.iterdir()
            if path.is_file()
        }
        for filename in SENTIMENT_SOURCE_CANDIDATES[service]:
            match = files_by_lower.get(filename.lower())
            if match is not None:
                return match

        # 2) Fallback pencarian otomatis untuk variasi nama file pengguna.
        service_tokens = {
            "IndiHome": ("indihome",),
            "IndiBiz": ("indibiz",),
            "Telkomsel": ("telkomsel", "tsel"),
        }[service]
        matches: list[Path] = []
        for path in data_dir.iterdir():
            if not path.is_file() or path.suffix.lower() not in SUPPORTED_SENTIMENT_EXTENSIONS:
                continue
            name_lower = path.name.lower()
            if "sna" in name_lower:
                continue
            if any(token in name_lower for token in service_tokens):
                matches.append(path)

        if not matches:
            return None

        # Prioritaskan CSV, lalu Excel, kemudian ZIP.
        extension_priority = {".csv": 0, ".xlsx": 1, ".xls": 2, ".zip": 3}
        matches.sort(key=lambda path: (extension_priority.get(path.suffix.lower(), 9), path.name.lower()))
        return matches[0]
    except Exception:
        return None


def _sentiment_csv_path(layanan: str) -> str:
    """Kembalikan path sumber sentimen aktual; nama fungsi dipertahankan untuk kompatibilitas."""
    resolved = _resolve_sentiment_source(layanan)
    if resolved is not None:
        return str(resolved)
    key = DATA_FILES.get(layanan, DATA_FILES["IndiHome"])["sentiment"]
    return _resolve_path(key)


def get_sentiment_source_name(layanan: str) -> str:
    """Kembalikan nama file sentimen aktual atau tanda bahwa file belum tersedia."""
    source = _resolve_sentiment_source(layanan)
    return source.name if source is not None else "Tidak ditemukan"


def _indihome_status_signature() -> str:
    """Buat cache key status output dan dataset mentah IndiHome."""
    try:
        parts: list[str] = []
        for source in (
            resolve_indihome_output(_data_dir()),
            resolve_indihome_raw_source(_data_dir()),
        ):
            if source is None or not source.exists():
                continue
            stat = source.stat()
            parts.append(f"{source.name}:{stat.st_size}:{stat.st_mtime_ns}")
        return "|".join(parts) if parts else "missing"
    except Exception:
        return "unknown"


# Cache DataFrame hanya di memori proses. Cache disk berbasis pickle tidak aman
# dipakai ulang setelah versi Pandas/Python pada virtual environment berubah.
@st.cache_data(show_spinner=False, max_entries=4)
def _get_indihome_prediction_status_cached(file_signature: str) -> dict[str, object]:
    """Validasi output Colab IndiHome berdasarkan versi file sumber."""
    del file_signature
    output = resolve_indihome_output(_data_dir())
    raw_source = resolve_indihome_raw_source(_data_dir())
    if output is None:
        return {
            "file_found": False,
            "source_name": "Tidak ditemukan",
            "canonical_name": INDIHOME_CANONICAL_OUTPUT_NAME,
            "raw_source_found": raw_source is not None,
            "raw_source_name": raw_source.name if raw_source is not None else "Tidak ditemukan",
            "ready": False,
            "total_rows": 0,
            "valid_rows": 0,
            "platform_counts": {},
            "sentiment_counts": {},
            "message": (
                f"Dataset mentah {raw_source.name} ditemukan, tetapi output prediksi "
                f"Google Colab belum diimpor sebagai data/{INDIHOME_CANONICAL_OUTPUT_NAME}."
                if raw_source is not None
                else f"Output prediksi Google Colab data/{INDIHOME_CANONICAL_OUTPUT_NAME} belum tersedia."
            ),
        }

    status = inspect_indihome_output(output, scan_rows=True)
    status.update(
        {
            "canonical_name": INDIHOME_CANONICAL_OUTPUT_NAME,
            "raw_source_found": raw_source is not None,
            "raw_source_name": raw_source.name if raw_source is not None else "Tidak ditemukan",
        }
    )
    return status


def get_indihome_prediction_status() -> dict[str, object]:
    """Kembalikan status output prediksi Google Colab IndiHome."""
    try:
        return _get_indihome_prediction_status_cached(_indihome_status_signature())
    except Exception as error:
        return {
            "file_found": False,
            "source_name": "Tidak ditemukan",
            "canonical_name": INDIHOME_CANONICAL_OUTPUT_NAME,
            "raw_source_found": False,
            "raw_source_name": "Tidak ditemukan",
            "ready": False,
            "total_rows": 0,
            "valid_rows": 0,
            "platform_counts": {},
            "sentiment_counts": {},
            "message": f"Status output prediksi IndiHome gagal diperiksa: {error}",
        }


def _sna_csv_path() -> str:
    """Kembalikan path file CSV SNA gabungan standar."""
    return _resolve_path("data/sna_data.csv")


def _infer_sna_service_from_name(name: str) -> str | None:
    """Tebak layanan dari nama file SNA."""
    lowered = str(name or "").lower()
    if "indibiz" in lowered or "indibiz" in lowered.replace(" ", ""):
        return "IndiBiz"
    if "indihome" in lowered or "indi home" in lowered:
        return "IndiHome"
    if "telkomsel" in lowered or "tsel" in lowered:
        return "Telkomsel"
    return None


def _infer_sna_platform_from_name(name: str) -> str:
    """Tebak platform dari nama file atau default ke Twitter/X untuk edge mention."""
    lowered = str(name or "").lower()
    if "instagram" in lowered or "ig" in lowered:
        return "instagram"
    if "tiktok" in lowered or "tik tok" in lowered:
        return "tiktok"
    if "twitter" in lowered or "x" in lowered:
        return "twitter"
    # File SNA penelitian biasanya berbentuk mention/reply Twitter/X.
    return "twitter"


def _resolve_sna_sources(layanan: str | None = None) -> list[Path]:
    """Cari file SNA aktual dari data/sna_data.csv dan file SNA per layanan."""
    try:
        data_dir = _data_dir()
        if not data_dir.exists():
            return []

        services = [layanan] if layanan in SNA_SOURCE_CANDIDATES else list(SNA_SOURCE_CANDIDATES)
        files_by_lower = {path.name.lower(): path for path in data_dir.iterdir() if path.is_file()}
        ordered: list[Path] = []

        # Nama kandidat resmi diprioritaskan.
        for service in services:
            for filename in SNA_SOURCE_CANDIDATES[service]:
                match = files_by_lower.get(filename.lower())
                if match is not None and match not in ordered:
                    ordered.append(match)

        # Fallback otomatis untuk variasi nama file pengguna.
        service_tokens = {
            "IndiHome": ("indihome", "indi home"),
            "IndiBiz": ("indibiz", "indi biz"),
            "Telkomsel": ("telkomsel", "tsel"),
        }
        wanted_tokens: tuple[str, ...] = tuple(
            token
            for service in services
            for token in service_tokens.get(service, ())
        )
        for path in data_dir.iterdir():
            if not path.is_file() or path.suffix.lower() not in SUPPORTED_SNA_EXTENSIONS:
                continue
            name_lower = path.name.lower()
            if "sna" not in name_lower:
                continue
            if layanan is None or any(token in name_lower for token in wanted_tokens):
                if path not in ordered:
                    ordered.append(path)

        extension_priority = {".csv": 0, ".xlsx": 1, ".xls": 2, ".zip": 3}
        ordered.sort(key=lambda path: (extension_priority.get(path.suffix.lower(), 9), path.name.lower()))
        return ordered
    except Exception:
        return []


def get_sna_source_names(layanan: str | None = None) -> str:
    """Kembalikan nama sumber SNA yang benar-benar dipakai dashboard."""
    sources = _select_sna_sources_for_service(layanan)
    return " + ".join(path.name for path in sources) if sources else "SNA tidak tersedia"


def sentiment_file_exists(layanan: str) -> bool:
    """Cek apakah sumber sentimen yang siap dipakai tersedia di disk."""
    try:
        source = _resolve_sentiment_source(layanan)
        if source is None:
            return False
        if str(layanan).strip() == "IndiHome":
            return bool(inspect_indihome_output(source, scan_rows=False).get("ready"))
        return True
    except Exception:
        return False


def sna_file_exists(layanan: str | None = None) -> bool:
    """Cek apakah ada sumber SNA aktual di folder data.

    Parameter layanan bersifat opsional untuk menjaga kompatibilitas kode lama.
    """
    try:
        return bool(_select_sna_sources_for_service(layanan))
    except Exception:
        return False


def _get_date_column(df: pd.DataFrame) -> str:
    """Tentukan nama kolom tanggal yang tersedia di DataFrame."""
    if "date_created" in df.columns:
        return "date_created"
    if "date" in df.columns:
        return "date"
    raise ValueError("Kolom tanggal (date_created/date) tidak ditemukan.")


def _find_source_columns(
    columns: list[str],
    schema: str,
) -> tuple[dict[str, str], list[str]]:
    """Pilih hanya kolom yang dibutuhkan untuk skema sentimen atau SNA."""
    try:
        if schema == "sna":
            aliases = CANONICAL_SNA_COLS
            required = {"source", "target", "relationship"}
        elif schema == "home_sna":
            # Beranda hanya membutuhkan struktur edge, platform, dan followers.
            # Kolom content/time/sentiment pada file SNA besar tidak dibaca.
            aliases = {
                "source": CANONICAL_SNA_COLS["source"],
                "target": CANONICAL_SNA_COLS["target"],
                "relationship": CANONICAL_SNA_COLS["relationship"],
                "followers": CANONICAL_SNA_COLS["followers"],
                "platform": CANONICAL_SNA_COLS["platform"],
            }
            required = {"source", "target", "relationship"}
        elif schema == "home_sentiment":
            # Beranda hanya membutuhkan kolom ringkas untuk KPI dan chart.
            # content tetap dibaca agar deduplikasi sama dengan loader utama,
            # tetapi preprocessing content_clean/IndoBERT tidak dijalankan.
            aliases = {
                "date": CANONICAL_SENTIMENT_COLS["date"],
                "platform": CANONICAL_SENTIMENT_COLS["platform"],
                "username": CANONICAL_SENTIMENT_COLS["username"],
                "content": CANONICAL_SENTIMENT_COLS["content"],
                "predicted_sentiment": CANONICAL_SENTIMENT_COLS["predicted_sentiment"],
            }
            required = {"platform", "content", "predicted_sentiment"}
        elif schema == "followers":
            # Pembaruan followers SNA hanya membutuhkan identitas akun dan
            # jumlah followers. File output Telkomsel Fase 2 memang tidak wajib
            # memiliki kolom confidence, sehingga jangan memaksakan skema
            # sentimen lengkap untuk kebutuhan enrichment ini.
            aliases = {
                "username": CANONICAL_SENTIMENT_COLS["username"],
                "followers": CANONICAL_SENTIMENT_COLS["followers"],
            }
            required = {"username", "followers"}
        else:
            aliases = CANONICAL_SENTIMENT_COLS
            required = set(REQUIRED_SENTIMENT_COLS)

        lookup = {str(column).strip().lower(): str(column) for column in columns}
        selected: dict[str, str] = {}
        for canonical, candidates in aliases.items():
            for alias in candidates:
                source = lookup.get(alias.lower())
                if source is not None:
                    selected[canonical] = source
                    break

        if not required.issubset(selected):
            return {}, []
        usecols = list(dict.fromkeys(selected.values()))
        return selected, usecols
    except Exception:
        return {}, []


def _is_compressed_csv_path(path: str | Path) -> bool:
    """Kembalikan True untuk file CSV biasa maupun CSV terkompresi gzip."""
    try:
        name = Path(path).name.casefold()
        return name.endswith(".csv") or name.endswith(".csv.gz")
    except Exception:
        return False


def _read_csv_flexible(path: str, schema: str = "sentiment") -> pd.DataFrame | None:
    """Baca CSV secara defensif dan hanya ambil kolom yang dipakai dashboard."""
    attempts = [
        (",", "utf-8-sig"),
        (";", "utf-8-sig"),
        ("\t", "utf-8-sig"),
        (",", "latin-1"),
        (";", "latin-1"),
    ]
    for delimiter, encoding in attempts:
        try:
            header = pd.read_csv(
                path,
                delimiter=delimiter,
                encoding=encoding,
                nrows=0,
            )
            mapping, usecols = _find_source_columns(list(header.columns), schema)
            if not usecols:
                continue

            frame = pd.read_csv(
                path,
                delimiter=delimiter,
                encoding=encoding,
                usecols=usecols,
                dtype="string",
                keep_default_na=False,
                na_filter=False,
                low_memory=True,
            )
            rename = {source: canonical for canonical, source in mapping.items()}
            return frame.rename(columns=rename)
        except Exception:
            continue
    return None


def _read_csv_bytes_flexible(raw: bytes, schema: str = "sentiment") -> pd.DataFrame | None:
    """Baca CSV dari bytes dengan usecols agar file ZIP besar tetap ringan."""
    attempts = [
        (",", "utf-8-sig"),
        (";", "utf-8-sig"),
        ("\t", "utf-8-sig"),
        (",", "latin-1"),
        (";", "latin-1"),
    ]
    for delimiter, encoding in attempts:
        try:
            header = pd.read_csv(
                BytesIO(raw),
                delimiter=delimiter,
                encoding=encoding,
                nrows=0,
            )
            mapping, usecols = _find_source_columns(list(header.columns), schema)
            if not usecols:
                continue

            frame = pd.read_csv(
                BytesIO(raw),
                delimiter=delimiter,
                encoding=encoding,
                usecols=usecols,
                dtype="string",
                keep_default_na=False,
                na_filter=False,
                low_memory=True,
            )
            rename = {source: canonical for canonical, source in mapping.items()}
            return frame.rename(columns=rename)
        except Exception:
            continue
    return None


def _read_excel_flexible(source, schema: str = "sentiment") -> pd.DataFrame | None:
    """Baca workbook secara selektif per sheet dengan usecols."""
    try:
        workbook = pd.ExcelFile(source)
        for sheet_name in workbook.sheet_names:
            try:
                header = pd.read_excel(workbook, sheet_name=sheet_name, nrows=0)
                mapping, usecols = _find_source_columns(list(header.columns), schema)
                if not usecols:
                    continue
                frame = pd.read_excel(
                    workbook,
                    sheet_name=sheet_name,
                    usecols=usecols,
                    dtype="string",
                )
                rename = {source_name: canonical for canonical, source_name in mapping.items()}
                return frame.rename(columns=rename)
            except Exception:
                continue
    except Exception:
        return None
    return None


def _read_sentiment_source_flexible(path: str) -> pd.DataFrame | None:
    """Baca sumber sentimen dari CSV, Excel, atau ZIP secara selektif."""
    source = Path(path)
    suffix = source.suffix.lower()

    if _is_compressed_csv_path(source):
        return _read_csv_flexible(str(source), schema="sentiment")

    if suffix in {".xlsx", ".xls"}:
        return _read_excel_flexible(source, schema="sentiment")

    if suffix == ".zip":
        try:
            with zipfile.ZipFile(source) as archive:
                members = [
                    name for name in archive.namelist()
                    if not name.endswith("/") and Path(name).suffix.lower() in {".csv", ".xlsx", ".xls"}
                ]
                members.sort(key=lambda name: 0 if Path(name).suffix.lower() == ".csv" else 1)
                for member in members:
                    member_suffix = Path(member).suffix.lower()
                    raw = archive.read(member)
                    if member_suffix == ".csv":
                        frame = _read_csv_bytes_flexible(raw, schema="sentiment")
                    else:
                        frame = _read_excel_flexible(BytesIO(raw), schema="sentiment")
                    if frame is not None and not frame.empty:
                        return frame
        except Exception:
            return None

    return None


def _read_home_sentiment_source_flexible(path: str) -> pd.DataFrame | None:
    """Baca proyeksi sentimen minimal khusus Beranda.

    Beranda tidak membutuhkan confidence, followers, atau content_clean. Membaca
    hanya kolom yang benar-benar dipakai mengurangi penggunaan RAM dan waktu
    normalisasi, terutama pada file Telkomsel yang berukuran besar.
    """
    source = Path(path)
    suffix = source.suffix.lower()

    if _is_compressed_csv_path(source):
        return _read_csv_flexible(str(source), schema="home_sentiment")

    if suffix in {".xlsx", ".xls"}:
        return _read_excel_flexible(source, schema="home_sentiment")

    if suffix == ".zip":
        try:
            with zipfile.ZipFile(source) as archive:
                members = [
                    name
                    for name in archive.namelist()
                    if not name.endswith("/")
                    and Path(name).suffix.lower() in {".csv", ".xlsx", ".xls"}
                ]
                members.sort(
                    key=lambda name: 0 if Path(name).suffix.lower() == ".csv" else 1
                )
                for member in members:
                    raw = archive.read(member)
                    member_suffix = Path(member).suffix.lower()
                    if member_suffix == ".csv":
                        frame = _read_csv_bytes_flexible(
                            raw,
                            schema="home_sentiment",
                        )
                    else:
                        frame = _read_excel_flexible(
                            BytesIO(raw),
                            schema="home_sentiment",
                        )
                    if frame is not None and not frame.empty:
                        return frame
        except Exception:
            return None

    return None


def _normalize_home_sentiment_df(
    dataframe: pd.DataFrame,
    layanan: str,
) -> pd.DataFrame:
    """Normalisasi data ringkas Beranda tanpa preprocessing teks IndoBERT.

    Aturan platform, sentimen, tanggal, dan deduplikasi konten tetap mengikuti
    loader utama. Tahap content_clean sengaja dilewati karena Beranda tidak pernah
    menggunakan kolom tersebut.
    """
    try:
        if dataframe is None or dataframe.empty:
            raise ValueError("Data sentimen Beranda kosong.")

        work = dataframe.copy()
        work = _normalize_columns(work, CANONICAL_SENTIMENT_COLS)
        work = _clean_string_columns(work)
        work = _repair_sentiment_platform_column(work)

        for column in ("platform", "content", "predicted_sentiment"):
            if column not in work.columns:
                raise ValueError(f"Kolom wajib '{column}' tidak ditemukan.")

        work["platform"] = _normalize_platform_series(work["platform"])
        work = work[work["platform"].isin(["twitter", "instagram", "tiktok"])].copy()

        work["content"] = work["content"].astype("string").fillna("").str.strip()
        work = work[
            work["content"].ne("")
            & work["content"].str.lower().ne("nan")
            & work["content"].str.lower().ne("none")
        ].copy()
        work.drop_duplicates(subset=["content"], keep="first", inplace=True)

        work["predicted_sentiment"] = (
            work["predicted_sentiment"]
            .astype(str)
            .str.lower()
            .str.strip()
            .map(SENTIMENT_MAP)
            .fillna("neutral")
        )

        if "username" not in work.columns:
            work["username"] = ""
        else:
            work["username"] = (
                work["username"]
                .astype("string")
                .fillna("")
                .str.strip()
                .str.lstrip("'")
                .str.lstrip("@")
            )

        if "date" not in work.columns:
            work["date"] = pd.NaT
        elif pd.api.types.is_datetime64_any_dtype(work["date"]):
            work["date"] = pd.to_datetime(work["date"], errors="coerce")
        else:
            date_text = work["date"].astype("string").fillna("").str.strip()
            date_text = date_text.str.replace(
                r"(\d{1,2})\.(\d{2})\.(\d{2})$",
                r"\1:\2:\3",
                regex=True,
            )
            work["date"] = pd.to_datetime(
                date_text,
                errors="coerce",
                dayfirst=True,
                format="mixed",
            )

        work["layanan"] = str(layanan).strip() or "IndiHome"
        return work[
            ["date", "platform", "username", "predicted_sentiment", "layanan"]
        ].reset_index(drop=True)
    except Exception as error:
        raise ValueError(
            f"Normalisasi data ringkas Beranda {layanan} gagal: {error}"
        ) from error


@st.cache_data(show_spinner=False, max_entries=12)
def _load_home_sentiment_cached(
    layanan: str,
    file_signature: str,
) -> pd.DataFrame:
    """Muat proyeksi sentimen Beranda dan cache berdasarkan versi file."""
    del file_signature
    try:
        source = _resolve_sentiment_source(layanan)
        if source is None or not source.exists():
            fallback = _fallback_sentiment_df(layanan)
            return _normalize_home_sentiment_df(fallback, layanan)

        projected = _read_home_sentiment_source_flexible(str(source))
        if projected is None or projected.empty:
            fallback = _fallback_sentiment_df(layanan)
            return _normalize_home_sentiment_df(fallback, layanan)

        normalized = _normalize_home_sentiment_df(projected, layanan)
        if normalized.empty:
            fallback = _fallback_sentiment_df(layanan)
            return _normalize_home_sentiment_df(fallback, layanan)
        return normalized
    except Exception:
        fallback = _fallback_sentiment_df(layanan)
        return _normalize_home_sentiment_df(fallback, layanan)


@st.cache_data(show_spinner=False, ttl=60, max_entries=12)
def load_home_sentiment_projection(layanan: str) -> pd.DataFrame:
    """Muat dataset ringkas untuk Beranda tanpa preprocessing teks yang berat."""
    try:
        signature = get_sentiment_file_signature(layanan)
        dataframe = _load_home_sentiment_cached(layanan, signature)
        if dataframe is None or dataframe.empty:
            fallback = _fallback_sentiment_df(layanan)
            return _normalize_home_sentiment_df(fallback, layanan)
        return dataframe
    except Exception as error:
        st.error(f"Data ringkas Beranda {layanan} gagal dimuat: {error}")
        try:
            fallback = _fallback_sentiment_df(layanan)
            return _normalize_home_sentiment_df(fallback, layanan)
        except Exception:
            return pd.DataFrame(
                columns=[
                    "date",
                    "platform",
                    "username",
                    "predicted_sentiment",
                    "layanan",
                ]
            )


def _read_followers_source_flexible(path: str) -> pd.DataFrame | None:
    """Baca hanya username dan followers dari sumber sentimen aktual.

    Fungsi ini sengaja memakai kontrak minimal karena enrichment followers SNA
    tidak membutuhkan tanggal, isi komentar, label sentimen, atau confidence.
    Pendekatan ini juga membuat file Telkomsel berukuran besar lebih ringan saat
    dibaca oleh dashboard.
    """
    source = Path(path)
    suffix = source.suffix.lower()

    if _is_compressed_csv_path(source):
        frame = _read_csv_flexible(str(source), schema="followers")
        if frame is not None and not frame.empty:
            return frame

        # Fallback parser untuk CSV yang memiliki baris teks tidak seragam.
        attempts = [
            (",", "utf-8-sig"),
            (";", "utf-8-sig"),
            ("\t", "utf-8-sig"),
            (",", "latin-1"),
            (";", "latin-1"),
        ]
        for delimiter, encoding in attempts:
            try:
                header = pd.read_csv(
                    source,
                    delimiter=delimiter,
                    encoding=encoding,
                    nrows=0,
                    engine="python",
                    on_bad_lines="skip",
                )
                mapping, usecols = _find_source_columns(
                    list(header.columns), "followers"
                )
                if not usecols:
                    continue
                frame = pd.read_csv(
                    source,
                    delimiter=delimiter,
                    encoding=encoding,
                    usecols=usecols,
                    dtype="string",
                    keep_default_na=False,
                    na_filter=False,
                    engine="python",
                    on_bad_lines="skip",
                )
                rename = {
                    source_name: canonical
                    for canonical, source_name in mapping.items()
                }
                frame = frame.rename(columns=rename)
                if not frame.empty:
                    return frame
            except Exception:
                continue
        return None

    if suffix in {".xlsx", ".xls"}:
        return _read_excel_flexible(source, schema="followers")

    if suffix == ".zip":
        try:
            with zipfile.ZipFile(source) as archive:
                members = [
                    name
                    for name in archive.namelist()
                    if not name.endswith("/")
                    and Path(name).suffix.lower() in {".csv", ".xlsx", ".xls"}
                ]
                members.sort(
                    key=lambda name: 0
                    if Path(name).suffix.lower() == ".csv"
                    else 1
                )
                for member in members:
                    member_suffix = Path(member).suffix.lower()
                    raw = archive.read(member)
                    if member_suffix == ".csv":
                        frame = _read_csv_bytes_flexible(raw, schema="followers")
                    else:
                        frame = _read_excel_flexible(
                            BytesIO(raw), schema="followers"
                        )
                    if frame is not None and not frame.empty:
                        return frame
        except Exception:
            return None

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


def _normalize_platform_series(series: pd.Series) -> pd.Series:
    """Normalisasi variasi nama platform media sosial secara defensif."""
    try:
        normalized = (
            series.astype("string")
            .fillna("")
            .str.lower()
            .str.replace("'", "", regex=False)
            .str.replace(r"[_\-]+", " ", regex=True)
            .str.replace(r"\s+", " ", regex=True)
            .str.strip()
        )

        exact_mapping = {
            "x": "twitter",
            "twitter": "twitter",
            "twitter x": "twitter",
            "twitter/x": "twitter",
            "x/twitter": "twitter",
            "twitter (x)": "twitter",
            "x.com": "twitter",
            "instagram": "instagram",
            "ig": "instagram",
            "instagram comments": "instagram",
            "instagram comment": "instagram",
            "tiktok": "tiktok",
            "tik tok": "tiktok",
            "tiktok comments": "tiktok",
            "tiktok comment": "tiktok",
        }
        normalized = normalized.replace(exact_mapping)

        twitter_mask = normalized.str.contains(
            r"(?:^|[ /])twitter(?:$|[ /])|(?:^|[ /])x(?:$|[ /])",
            regex=True,
            na=False,
        )
        instagram_mask = normalized.str.contains(
            "instagram", regex=False, na=False
        )
        tiktok_mask = (
            normalized.str.replace(" ", "", regex=False)
            .str.contains("tiktok", regex=False, na=False)
        )

        normalized = normalized.mask(twitter_mask, "twitter")
        normalized = normalized.mask(instagram_mask, "instagram")
        normalized = normalized.mask(tiktok_mask, "tiktok")
        return normalized.astype("string")
    except Exception:
        return series.astype("string").fillna("").str.lower().str.strip()


def _repair_sentiment_platform_column(df: pd.DataFrame) -> pd.DataFrame:
    """Pulihkan platform dari kolom alias jika kolom utama tidak valid."""
    try:
        result = df.copy()
        if "platform" not in result.columns:
            return result

        valid_platforms = {"twitter", "instagram", "tiktok"}
        repaired = _normalize_platform_series(result["platform"])
        valid_mask = repaired.isin(valid_platforms)

        for alias in (
            "specific_resource_type",
            "source_platform",
            "media",
            "channel",
        ):
            if alias not in result.columns or bool(valid_mask.all()):
                continue
            alias_values = _normalize_platform_series(result[alias])
            recover_mask = (~valid_mask) & alias_values.isin(valid_platforms)
            if bool(recover_mask.any()):
                repaired.loc[recover_mask] = alias_values.loc[recover_mask]
                valid_mask = repaired.isin(valid_platforms)

        result["platform"] = repaired
        return result
    except Exception:
        return df.copy()


def _normalize_sentiment_df(df: pd.DataFrame, layanan: str) -> pd.DataFrame:
    """Bersihkan dan normalisasi DataFrame sentimen."""
    df = _normalize_columns(df, CANONICAL_SENTIMENT_COLS)
    df = _clean_string_columns(df)
    df = _repair_sentiment_platform_column(df)

    for col in REQUIRED_SENTIMENT_COLS:
        if col not in df.columns:
            raise ValueError(f"Kolom wajib '{col}' tidak ditemukan.")

    df["followers"] = (
        pd.to_numeric(df["followers"], errors="coerce")
        .fillna(0)
        .clip(lower=0, upper=2_147_483_647)
        .astype("int32")
    )
    df["confidence"] = (
        pd.to_numeric(df["confidence"], errors="coerce")
        .fillna(0.0)
        .clip(lower=0.0, upper=1.0)
        .astype("float32")
    )
    df["platform"] = _normalize_platform_series(df["platform"])
    df = df[df["platform"].isin(["twitter", "instagram", "tiktok"])].copy()

    df["content"] = df["content"].astype("string").fillna("").str.strip()
    df = df[
        df["content"].ne("")
        & df["content"].str.lower().ne("nan")
        & df["content"].str.lower().ne("none")
    ].copy()
    df.drop_duplicates(subset=["content"], keep="first", inplace=True)

    # Hasil prediksi lama mungkin belum memiliki content_clean. Dashboard
    # membentuknya otomatis memakai fungsi yang sama dengan Cell [12] IndiBiz.
    if "content_clean" not in df.columns:
        df["content_clean"] = df["content"].map(clean_text)
    else:
        df["content_clean"] = (
            df["content_clean"].astype("string").fillna("").str.strip()
        )
        empty_clean = df["content_clean"].eq("")
        if empty_clean.any():
            df.loc[empty_clean, "content_clean"] = (
                df.loc[empty_clean, "content"].map(clean_text)
            )
    df = df[df["content_clean"].astype(str).str.strip().ne("")].copy()

    df["predicted_sentiment"] = (
        df["predicted_sentiment"].astype(str).str.lower().str.strip().map(SENTIMENT_MAP)
    )
    df["predicted_sentiment"] = df["predicted_sentiment"].fillna("neutral")
    # Format waktu pada dataset penelitian menggunakan tanda titik, misalnya
    # 24/11/2025 05.22.47. Normalisasi titik pada bagian jam menjadi titik dua
    # agar Pandas dapat membaca tanggal secara konsisten.
    if pd.api.types.is_datetime64_any_dtype(df["date"]):
        df["date"] = pd.to_datetime(df["date"], errors="coerce")
    else:
        date_text = df["date"].astype(str).str.strip()
        date_text = date_text.str.replace(
            r"(\d{1,2})\.(\d{2})\.(\d{2})$",
            r"\1:\2:\3",
            regex=True,
        )
        df["date"] = pd.to_datetime(
            date_text, errors="coerce", dayfirst=True, format="mixed"
        )
    df["date_created"] = df["date"]
    df["confidence_score"] = df["confidence"]
    if "layanan" not in df.columns:
        df["layanan"] = layanan
    return df.reset_index(drop=True)


def prepare_indibiz_raw_for_indobert(df_raw: pd.DataFrame) -> pd.DataFrame:
    """Jembatan dashboard menuju preprocessing Cell [12] IndiBiz.

    Fungsi publik ini disiapkan untuk fase prediksi berikutnya dan tidak membaca,
    menulis, atau mengubah notebook Google Colab.
    """
    try:
        return prepare_indibiz_indobert_dataframe(df_raw)
    except Exception as error:
        st.error(f"Gagal menyiapkan data mentah IndiBiz untuk IndoBERT: {error}")
        return pd.DataFrame()



def prepare_telkomsel_raw_for_sentiment(df_raw: pd.DataFrame) -> pd.DataFrame:
    """Jembatan dashboard menuju preprocessing data mentah Telkomsel.

    Fungsi tidak membaca, menulis, atau memodifikasi notebook Google Colab.
    Output mengikuti kontrak delapan kolom ``telkomsel_sentiment.csv``.
    """
    try:
        return prepare_telkomsel_sentiment_dataframe(df_raw)
    except Exception as error:
        st.error(f"Gagal menyiapkan data mentah Telkomsel: {error}")
        return pd.DataFrame()

def _repair_telkomsel_sna_edges(
    dataframe: pd.DataFrame,
    layanan: str | None = None,
    source_name: str = "",
) -> pd.DataFrame:
    """Perbaiki kontrak edge Telkomsel secara defensif di sisi dashboard.

    Notebook sumber lama menamai output ``output_sna.csv`` dan pada bagian
    Instagram/TikTok masih menulis target ``indihome``. Karena file tersebut
    berasal dari pipeline Telkomsel, dashboard mengarahkan komentar kedua
    platform itu ke node ``telkomsel``. Untuk ``sna_data.csv`` gabungan, hanya
    baris yang memang berlabel Telkomsel yang diperbaiki. File sumber tidak
    pernah ditulis ulang.
    """
    try:
        if dataframe is None or dataframe.empty:
            return pd.DataFrame() if dataframe is None else dataframe.copy()

        inferred_service = layanan or _infer_sna_service_from_name(source_name)
        work = dataframe.copy()

        if "layanan" in work.columns:
            service_values = work["layanan"].astype(str).str.lower().str.strip()
            telkomsel_mask = service_values.eq("telkomsel")
            # File khusus Telkomsel dapat membawa kolom layanan kosong. Dalam
            # kondisi itu, parameter loader menjadi sumber identitas layanan.
            if not telkomsel_mask.any() and str(inferred_service or "").strip().lower() == "telkomsel":
                known_services = service_values.isin({"indihome", "indibiz", "telkomsel"})
                if not known_services.any():
                    telkomsel_mask = pd.Series(True, index=work.index)
        elif str(inferred_service or "").strip().lower() == "telkomsel":
            work["layanan"] = "Telkomsel"
            telkomsel_mask = pd.Series(True, index=work.index)
        else:
            return work

        if not telkomsel_mask.any():
            return work

        work.loc[telkomsel_mask, "layanan"] = "Telkomsel"
        platforms = (
            work.get("platform", pd.Series("unknown", index=work.index))
            .astype(str)
            .str.lower()
            .str.strip()
        )
        targets = (
            work.get("target", pd.Series("", index=work.index))
            .astype(str)
            .str.lower()
            .str.strip()
        )
        wrong_brand_targets = targets.isin({"indihome", "indi home", "indibiz", "indi biz"})
        comment_platforms = platforms.isin({"instagram", "tiktok"})
        repair_mask = telkomsel_mask & wrong_brand_targets & comment_platforms
        if repair_mask.any():
            work.loc[repair_mask, "target"] = "telkomsel"

        source_values = (
            work.get("source", pd.Series("", index=work.index))
            .astype(str)
            .str.lower()
            .str.strip()
        )
        target_values = (
            work.get("target", pd.Series("", index=work.index))
            .astype(str)
            .str.lower()
            .str.strip()
        )
        self_loop_mask = telkomsel_mask & source_values.eq(target_values)
        work = work.loc[~self_loop_mask].copy()

        # Dedup hanya diterapkan pada bagian Telkomsel. Baris IndiHome dan
        # IndiBiz dalam file gabungan dipertahankan identik seperti sebelumnya.
        telkomsel_rows = work[
            work["layanan"].astype(str).str.lower().str.strip().eq("telkomsel")
        ].copy()
        other_rows = work[
            ~work["layanan"].astype(str).str.lower().str.strip().eq("telkomsel")
        ].copy()
        subset = [
            column
            for column in ["source", "target", "relationship", "followers", "platform"]
            if column in telkomsel_rows.columns
        ]
        if subset:
            telkomsel_rows = telkomsel_rows.drop_duplicates(subset=subset, keep="first")
        return pd.concat([other_rows, telkomsel_rows], ignore_index=True, sort=False)
    except Exception as error:
        st.error(f"Gagal memperbaiki edge SNA Telkomsel: {error}")
        return dataframe.copy() if isinstance(dataframe, pd.DataFrame) else pd.DataFrame()


def _normalize_sna_df(
    df: pd.DataFrame,
    layanan: str | None = None,
    source_name: str = "",
) -> pd.DataFrame:
    """Bersihkan dan normalisasi DataFrame SNA.

    File SNA aktual penelitian tidak selalu memiliki kolom followers/platform.
    Jika kolom tersebut tidak tersedia, sistem memberi nilai aman agar file tetap
    bisa dipakai untuk validasi influencer dan tidak jatuh ke dummy data.
    """
    df = _normalize_columns(df, CANONICAL_SNA_COLS)
    df = _clean_string_columns(df)

    for col in ["source", "target", "relationship"]:
        if col not in df.columns:
            raise ValueError(f"Kolom wajib '{col}' tidak ditemukan.")

    if "followers" not in df.columns:
        df["followers"] = 0
    if "platform" not in df.columns:
        df["platform"] = _infer_sna_platform_from_name(source_name)
    if "layanan" not in df.columns:
        inferred_service = layanan or _infer_sna_service_from_name(source_name)
        if inferred_service is not None:
            df["layanan"] = inferred_service

    df["followers"] = (
        pd.to_numeric(df["followers"], errors="coerce")
        .fillna(0)
        .clip(lower=0, upper=2_147_483_647)
        .astype("int32")
    )
    df["platform"] = (
        df["platform"]
        .astype(str)
        .str.lower()
        .str.strip()
        .replace({
            "x": "twitter",
            "twitter/x": "twitter",
            "twitter (x)": "twitter",
            "x/twitter": "twitter",
            "ig": "instagram",
            "instagram comments": "instagram",
            "tiktok comments": "tiktok",
        })
    )
    # Username media sosial diperlakukan tanpa membedakan huruf besar-kecil.
    # Awalan @ tetap dipertahankan di loader dan dibersihkan pada halaman SNA.
    df["source"] = (
        df["source"].astype(str).str.strip().str.lstrip("'").str.lower()
    )
    df["target"] = (
        df["target"].astype(str).str.strip().str.lstrip("'").str.lower()
    )
    df["relationship"] = df["relationship"].astype(str).str.strip().str.lower()
    if "layanan" in df.columns:
        df["layanan"] = df["layanan"].astype(str).str.strip()

    # Kolom time dari file SNA aktual disalin menjadi date agar bisa dipakai
    # sebagai bukti konten pada halaman rekomendasi.
    if "date" not in df.columns and "time" in df.columns:
        df["date"] = df["time"]
    if "predicted_sentiment" not in df.columns and "sentiment" in df.columns:
        df["predicted_sentiment"] = df["sentiment"]

    df = df.dropna(subset=["source", "target"])
    df = df[(df["source"] != "") & (df["target"] != "")]
    df = df[(df["source"].str.lower() != "nan") & (df["target"].str.lower() != "nan")]
    df = _repair_telkomsel_sna_edges(df, layanan=layanan, source_name=source_name)
    return df.reset_index(drop=True)


def _username_match_key(value: object) -> str:
    """Normalisasi username agar pencocokan SNA dan sentimen konsisten."""
    try:
        return str(value or "").strip().lstrip("'@").lower()
    except Exception:
        return ""


def _update_sna_followers_from_prediction(
    df_sna: pd.DataFrame,
    df_pred: pd.DataFrame,
    layanan: str = "IndiBiz",
) -> pd.DataFrame:
    """Perbarui followers SNA secara vectorized dari hasil prediksi sentimen.

    Nilai followers pada SNA tidak pernah diperkecil. Implementasi vectorized
    menghindari DataFrame.apply per baris yang sangat lambat pada edge list besar.
    """
    try:
        if df_sna is None or df_sna.empty:
            return pd.DataFrame() if df_sna is None else df_sna.copy()
        if df_pred is None or df_pred.empty:
            return df_sna.copy()

        missing_sna = {"source", "followers"}.difference(df_sna.columns)
        missing_pred = {"username", "followers"}.difference(df_pred.columns)
        if missing_sna or missing_pred:
            missing = sorted(missing_sna.union(missing_pred))
            st.error(
                f"Followers {layanan} belum dapat diperbarui karena kolom berikut "
                f"tidak tersedia: {', '.join(missing)}."
            )
            return df_sna.copy()

        sna_work = df_sna.copy()
        pred_work = df_pred[["username", "followers"]].copy()

        source_keys = (
            sna_work["source"]
            .astype("string")
            .fillna("")
            .str.strip()
            .str.lstrip("'@")
            .str.lower()
        )
        pred_work["_username_key"] = (
            pred_work["username"]
            .astype("string")
            .fillna("")
            .str.strip()
            .str.lstrip("'@")
            .str.lower()
        )
        pred_work["followers"] = (
            pd.to_numeric(pred_work["followers"], errors="coerce")
            .fillna(0)
            .clip(lower=0, upper=2_147_483_647)
        )

        followers_lookup = (
            pred_work.loc[pred_work["_username_key"].ne("")]
            .groupby("_username_key")["followers"]
            .max()
        )
        current_followers = (
            pd.to_numeric(sna_work["followers"], errors="coerce")
            .fillna(0)
            .clip(lower=0, upper=2_147_483_647)
        )
        predicted_followers = (
            source_keys.map(followers_lookup)
            .fillna(0)
            .astype("float64")
        )

        sna_work["followers"] = (
            current_followers.where(current_followers.ge(predicted_followers), predicted_followers)
            .clip(lower=0, upper=2_147_483_647)
            .astype("int32")
        )
        return sna_work
    except Exception as error:
        st.error(
            f"Gagal memperbarui followers SNA {layanan} dari hasil prediksi "
            f"sentimen: {error}"
        )
        return df_sna.copy() if isinstance(df_sna, pd.DataFrame) else pd.DataFrame()

def _enrich_indibiz_sna_followers(df_sna: pd.DataFrame) -> pd.DataFrame:
    """Perbarui followers IndiBiz hanya jika file sentimen aktual tersedia.

    Sebelum Fase 11 selesai, file hasil sentimen belum tersedia sehingga fungsi
    mengembalikan data SNA apa adanya. Setelah file tersedia, followers akan
    diperbarui otomatis pada pemuatan data berikutnya. Data dummy tidak pernah
    dipakai untuk memperbarui followers penelitian aktual.
    """
    try:
        source = _resolve_indibiz_output_path(
            None,
            INDIBIZ_OUTPUT_SENTIMENT_PATH,
            legacy_relative_paths=(
                "data/indibiz_sentiment.csv",
                "data/indibiz_sentiment.xlsx",
            ),
        )
        if not source.exists():
            return df_sna.copy()

        followers_source = _read_followers_source_flexible(str(source))
        if followers_source is None or followers_source.empty:
            st.error(
                "File sentimen IndiBiz ditemukan, tetapi kolom username/followers "
                "belum dapat dibaca. Followers SNA tetap memakai nilai sebelumnya."
            )
            return df_sna.copy()

        followers_source = _clean_string_columns(followers_source)
        return _update_sna_followers_from_prediction(
            df_sna,
            followers_source,
            "IndiBiz",
        )
    except Exception as error:
        st.error(
            "File sentimen IndiBiz belum dapat dipakai untuk memperbarui "
            f"followers SNA: {error}"
        )
        return df_sna.copy()


def _enrich_telkomsel_sna_followers(df_sna: pd.DataFrame) -> pd.DataFrame:
    """Perbarui followers Telkomsel dari output sentimen aktual jika tersedia."""
    try:
        source = _resolve_sentiment_source("Telkomsel")
        if source is None or not source.exists():
            return df_sna.copy()

        followers_source = _read_followers_source_flexible(str(source))
        if followers_source is None or followers_source.empty:
            # File telkomsel_sentiment.csv aktual pada proyek dapat berupa hasil
            # preprocessing delapan kolom tanpa followers. Kondisi tersebut valid
            # untuk halaman SNA karena df_edge_telkomsel.csv sudah membawa
            # followers Instagram/TikTok. Lewati enrichment tanpa pesan error.
            return df_sna.copy()

        followers_source = _clean_string_columns(followers_source)
        return _update_sna_followers_from_prediction(
            df_sna,
            followers_source,
            "Telkomsel",
        )
    except Exception as error:
        st.warning(
            "Followers Telkomsel belum dapat diperkaya dari file sentimen. "
            f"Graf tetap memakai followers dari file SNA: {error}"
        )
        return df_sna.copy()


def _enrich_sna_followers_from_recommendation_source(
    df_sna: pd.DataFrame,
    layanan: str,
) -> pd.DataFrame:
    """Perkaya followers SNA dari proyeksi sentimen yang sudah dibaca Rekomendasi.

    Jalur ini hanya dipakai saat halaman Rekomendasi meminta ``recommendation_mode``.
    Tujuannya menghindari pembacaan file sentimen besar sekali lagi hanya untuk
    dua kolom username/followers. Halaman lain tetap memakai alur lama.
    """
    try:
        shared = load_recommendation_source_data(layanan)
        if (
            shared is None
            or shared.empty
            or "username" not in shared.columns
            or "followers" not in shared.columns
        ):
            return df_sna.copy()

        followers_source = shared.loc[:, ["username", "followers"]].copy()
        followers_source = followers_source[
            followers_source["username"]
            .fillna("")
            .astype(str)
            .str.strip()
            .ne("")
        ].copy()
        if followers_source.empty:
            return df_sna.copy()
        return _update_sna_followers_from_prediction(
            df_sna,
            followers_source,
            layanan,
        )
    except Exception:
        return df_sna.copy()


def _enrich_combined_sna_followers(
    combined: pd.DataFrame,
    layanan: str | None,
) -> pd.DataFrame:
    """Perbarui followers IndiBiz dan Telkomsel dari file sentimen aktual."""
    try:
        if combined is None or combined.empty:
            return pd.DataFrame() if combined is None else combined.copy()

        enrichers = {
            "IndiBiz": _enrich_indibiz_sna_followers,
            "Telkomsel": _enrich_telkomsel_sna_followers,
        }
        if layanan in enrichers:
            return enrichers[layanan](combined)

        if layanan is None and "layanan" in combined.columns:
            result = combined.copy()
            for service, enricher in enrichers.items():
                mask = result["layanan"].astype(str).str.lower().eq(service.lower())
                if not mask.any():
                    continue
                updated = enricher(result.loc[mask].copy())
                result.loc[mask, "followers"] = updated["followers"].to_numpy()
            result["followers"] = (
                pd.to_numeric(result["followers"], errors="coerce")
                .fillna(0)
                .clip(lower=0, upper=2_147_483_647)
                .astype("int32")
            )
            return result

        return combined.copy()
    except Exception as error:
        st.error(f"Gagal menerapkan pembaruan followers gabungan: {error}")
        return combined.copy()


def _emergency_sentiment_df(layanan: str) -> pd.DataFrame:
    """Buat fallback sentimen minimum yang selalu memiliki kontrak kolom valid."""
    try:
        service = str(layanan or "IndiHome").strip() or "IndiHome"
        base_date = pd.Timestamp("2025-11-01")
        rows = [
            {
                "date": base_date,
                "platform": "twitter",
                "username": "pengguna_twitter",
                "followers": 0,
                "content": f"Layanan {service} stabil dan lancar",
                "predicted_sentiment": "positive",
                "confidence": 0.90,
            },
            {
                "date": base_date + pd.Timedelta(days=1),
                "platform": "instagram",
                "username": "pengguna_instagram",
                "followers": 0,
                "content": f"Mohon info paket {service}",
                "predicted_sentiment": "neutral",
                "confidence": 0.80,
            },
            {
                "date": base_date + pd.Timedelta(days=2),
                "platform": "tiktok",
                "username": "pengguna_tiktok",
                "followers": 0,
                "content": f"Jaringan {service} sering gangguan dan lambat",
                "predicted_sentiment": "negative",
                "confidence": 0.92,
            },
        ]
        dataframe = pd.DataFrame(rows)
        dataframe["content_clean"] = dataframe["content"].map(clean_text)
        dataframe["date_created"] = dataframe["date"]
        dataframe["confidence_score"] = dataframe["confidence"].astype("float32")
        dataframe["layanan"] = service
        return dataframe.reset_index(drop=True)
    except Exception:
        return pd.DataFrame(
            columns=[
                "date", "platform", "username", "followers", "content",
                "predicted_sentiment", "confidence", "content_clean",
                "date_created", "confidence_score", "layanan",
            ]
        )


def _fallback_sentiment_df(layanan: str) -> pd.DataFrame:
    """Muat data dummy terstruktur dan cegah fallback menghasilkan DataFrame kosong."""
    try:
        if str(layanan).strip() == "IndiBiz":
            raw = get_dummy_indibiz_sentiment()
        else:
            raw = get_dummy_sentiment_data(layanan)
        normalized = _normalize_sentiment_df(raw, layanan)
        if normalized is None or normalized.empty:
            return _emergency_sentiment_df(layanan)
        return normalized
    except Exception:
        return _emergency_sentiment_df(layanan)


def _fallback_sna_df(layanan: str | None = None) -> pd.DataFrame:
    """Muat dummy SNA yang sesuai dengan layanan agar fallback tidak tertukar."""
    try:
        service_key = str(layanan or "").strip().lower()
        if service_key == "indibiz":
            fallback = get_dummy_indibiz_sna().copy()
            fallback["layanan"] = "IndiBiz"
            return _normalize_sna_df(
                fallback,
                layanan="IndiBiz",
                source_name="dummy_indibiz_sna.csv",
            )
        if service_key == "telkomsel":
            fallback = get_dummy_telkomsel_sna().copy()
            return _normalize_sna_df(
                fallback,
                layanan="Telkomsel",
                source_name="dummy_telkomsel_sna.csv",
            )

        fallback = get_dummy_sna_data().copy()
        if layanan is not None and "layanan" in fallback.columns:
            fallback = _filter_sna_by_service_loader(fallback, layanan)
        return fallback.reset_index(drop=True)
    except Exception as error:
        st.error(f"Gagal menyiapkan dummy SNA {layanan or 'gabungan'}: {error}")
        return pd.DataFrame(columns=REQUIRED_SNA_COLS + ["layanan"])


@st.cache_data(show_spinner=False, max_entries=12)
def _load_sentiment_cached(layanan: str, file_signature: str) -> pd.DataFrame:
    """Muat data mentah sentimen dan cache berdasarkan versi file sumber."""
    del file_signature  # Dipakai sebagai cache key agar file baru langsung terdeteksi.
    try:
        path = _sentiment_csv_path(layanan)
        if not os.path.exists(path):
            return _fallback_sentiment_df(layanan)

        df = _read_sentiment_source_flexible(path)
        if df is None or df.empty:
            raise ValueError("File ditemukan, tetapi isinya tidak dapat dibaca.")

        normalized = _normalize_sentiment_df(df, layanan)
        if normalized is None or normalized.empty:
            # File dapat terbaca tetapi seluruh baris gugur saat normalisasi.
            # Kondisi ini tidak boleh membuat halaman analitik menjadi kosong.
            return _fallback_sentiment_df(layanan)
        return normalized
    except FileNotFoundError:
        return _fallback_sentiment_df(layanan)
    except Exception as exc:
        raise RuntimeError(f"Sumber sentimen {layanan} gagal diproses: {exc}") from exc


@st.cache_data(show_spinner=False, ttl=60, max_entries=12)
def load_sentiment_data(layanan: str) -> pd.DataFrame:
    """
    Muat data sentimen dari CSV, Excel, atau ZIP yang cocok dengan layanan.

    Jika seluruh sumber tidak ada atau gagal dibaca, fallback ke data dummy.
    """
    try:
        if not sentiment_file_exists(layanan):
            st.warning(
                f"File sentimen untuk {layanan} tidak ditemukan di folder data. "
                "Menggunakan data dummy."
            )
        signature = get_sentiment_file_signature(layanan)
        dataframe = _load_sentiment_cached(layanan, signature)
        if dataframe is None or dataframe.empty:
            return _fallback_sentiment_df(layanan)
        return dataframe
    except Exception as e:
        st.error(f"Gagal memuat data sentimen {layanan}: {e}")
        st.warning("Menggunakan data dummy sebagai fallback.")
        return _fallback_sentiment_df(layanan)



def get_sna_file_signature(layanan: str | None = None) -> str:
    """Ambil tanda tangan file SNA yang benar-benar dipakai untuk cache cepat."""
    try:
        sources = _select_sna_sources_for_service(layanan)
        if not sources:
            return f"{layanan or 'all'}:missing"
        parts: list[str] = []
        for path in sources:
            try:
                stat = path.stat()
                parts.append(f"{path.name}:{stat.st_size}:{stat.st_mtime_ns}")
            except Exception:
                parts.append(f"{path.name}:unknown")
        return f"{layanan or 'all'}|" + "|".join(parts)
    except Exception:
        return f"{layanan or 'all'}:unknown"


def _select_sna_sources_for_service(layanan: str | None = None) -> list[Path]:
    """Pilih sumber SNA kanonik tanpa membaca file mentah secara ganda.

    Khusus IndiBiz, dashboard memakai dua keluaran yang tidak saling tumpang
    tindih: file Twitter/X dari Fase 3 dan file Instagram–TikTok dari Fase 4.
    Layanan lain tetap memakai satu sumber prioritas seperti sebelumnya.
    """
    try:
        if layanan is None:
            selected: list[Path] = []
            for service in SNA_SOURCE_CANDIDATES:
                for source in _select_sna_sources_for_service(service):
                    if source not in selected:
                        selected.append(source)
            return selected

        sources = _resolve_sna_sources(layanan)
        if not sources:
            return []

        files_by_lower = {source.name.lower(): source for source in sources}

        if layanan == "IndiBiz":
            canonical_names = [
                INDIBIZ_OUTPUT_FILES["sna_csv"],
                INDIBIZ_OUTPUT_FILES["sna_instagram_tiktok_csv"],
            ]
            canonical_sources = [
                files_by_lower[name.lower()]
                for name in canonical_names
                if name.lower() in files_by_lower
            ]
            if canonical_sources:
                return canonical_sources

        candidate_names = list(SNA_SOURCE_CANDIDATES.get(layanan, []))
        specific_candidates = [
            filename for filename in candidate_names if filename.lower() != "sna_data.csv"
        ]
        for filename in specific_candidates:
            match = files_by_lower.get(filename.lower())
            if match is not None:
                return [match]

        generic_source = files_by_lower.get("sna_data.csv")
        if generic_source is not None:
            return [generic_source]

        service_specific = [source for source in sources if source.name.lower() != "sna_data.csv"]
        return [service_specific[0]] if service_specific else [sources[0]]
    except Exception:
        return []


def _filter_sna_by_service_loader(df: pd.DataFrame, layanan: str | None) -> pd.DataFrame:
    """Filter hasil SNA di sisi data loader agar halaman tidak memproses data besar."""
    if df is None or df.empty or layanan is None or "layanan" not in df.columns:
        return df
    return df[df["layanan"].astype(str).str.lower().eq(str(layanan).lower())].copy()


def _read_sna_source_frame(path: Path) -> pd.DataFrame | None:
    """Baca satu file SNA aktual dengan fallback CSV/Excel/ZIP."""
    suffix = path.suffix.lower()
    if _is_compressed_csv_path(path):
        return _read_csv_flexible(str(path), schema="sna")
    if suffix in {".xlsx", ".xls"}:
        return _read_excel_flexible(path, schema="sna")
    if suffix == ".zip":
        with zipfile.ZipFile(path) as archive:
            members = [
                name for name in archive.namelist()
                if not name.endswith("/") and Path(name).suffix.lower() in {".csv", ".xlsx", ".xls"}
            ]
            members.sort(key=lambda name: 0 if Path(name).suffix.lower() == ".csv" else 1)
            for member in members:
                raw = archive.read(member)
                member_suffix = Path(member).suffix.lower()
                if member_suffix == ".csv":
                    frame = _read_csv_bytes_flexible(raw, schema="sna")
                else:
                    frame = _read_excel_flexible(BytesIO(raw), schema="sna")
                if frame is not None and not frame.empty:
                    return frame
    return None


@st.cache_data(show_spinner=False, max_entries=12)
def _load_sna_cached(
    layanan: str | None,
    file_signature: str,
    followers_signature: str,
    recommendation_mode: bool = False,
) -> pd.DataFrame:
    """Muat sumber SNA aktual dengan cache per layanan.

    Parameter file_signature sengaja dipakai sebagai cache key agar perubahan
    file CSV/Excel/ZIP di folder data langsung terbaca tanpa harus clear cache.
    """
    del file_signature, followers_signature
    sources = _select_sna_sources_for_service(layanan)
    if not sources:
        return _fallback_sna_df(layanan)

    frames: list[pd.DataFrame] = []
    for path in sources:
        try:
            frame = _read_sna_source_frame(path)
            if frame is None or frame.empty:
                continue
            service = _infer_sna_service_from_name(path.name) or layanan
            normalized = _normalize_sna_df(frame, layanan=service, source_name=path.name)
            normalized = _filter_sna_by_service_loader(normalized, layanan)
            if not normalized.empty:
                frames.append(normalized)
        except Exception:
            # Satu file bermasalah tidak boleh menggagalkan semua sumber SNA.
            continue

    if not frames:
        return _fallback_sna_df(layanan)

    combined = pd.concat(frames, ignore_index=True, sort=False)
    if recommendation_mode and layanan in {"IndiBiz", "Telkomsel"}:
        combined = _enrich_sna_followers_from_recommendation_source(
            combined,
            str(layanan),
        )
    else:
        combined = _enrich_combined_sna_followers(combined, layanan)

    # Jangan menghapus edge yang tampak sama pada tahap loader. Untuk data
    # komentar Instagram/TikTok, satu akun dapat mengirim beberapa komentar
    # kepada node pusat. Edge berulang tersebut dibutuhkan agar frekuensi
    # interaksi dapat dihitung sebagai weight pada tahap analisis NetworkX.
    return combined.reset_index(drop=True)


def _read_home_sna_source_frame(path: Path) -> pd.DataFrame | None:
    """Baca edge SNA minimal khusus Beranda tanpa kolom konten dan waktu."""
    try:
        suffix = path.suffix.lower()
        if _is_compressed_csv_path(path):
            return _read_csv_flexible(str(path), schema="home_sna")
        if suffix in {".xlsx", ".xls"}:
            return _read_excel_flexible(path, schema="home_sna")
        if suffix == ".zip":
            with zipfile.ZipFile(path) as archive:
                members = [
                    name
                    for name in archive.namelist()
                    if not name.endswith("/")
                    and Path(name).suffix.lower() in {".csv", ".xlsx", ".xls"}
                ]
                members.sort(
                    key=lambda name: 0 if Path(name).suffix.lower() == ".csv" else 1
                )
                for member in members:
                    raw = archive.read(member)
                    member_suffix = Path(member).suffix.lower()
                    if member_suffix == ".csv":
                        frame = _read_csv_bytes_flexible(raw, schema="home_sna")
                    else:
                        frame = _read_excel_flexible(BytesIO(raw), schema="home_sna")
                    if frame is not None and not frame.empty:
                        return frame
        return None
    except Exception:
        return None


@st.cache_data(show_spinner=False, max_entries=6)
def _load_home_sna_cached(
    file_signature: str,
    followers_signature: str,
) -> pd.DataFrame:
    """Muat proyeksi SNA minimal Beranda berdasarkan signature file aktual."""
    del file_signature, followers_signature
    try:
        sources = _select_sna_sources_for_service(None)
        if not sources:
            return _fallback_sna_df(None)

        frames: list[pd.DataFrame] = []
        for path in sources:
            try:
                frame = _read_home_sna_source_frame(path)
                if frame is None or frame.empty:
                    continue
                service = _infer_sna_service_from_name(path.name)
                normalized = _normalize_sna_df(
                    frame,
                    layanan=service,
                    source_name=path.name,
                )
                if normalized.empty:
                    continue
                keep_columns = [
                    column
                    for column in [
                        "source",
                        "target",
                        "followers",
                        "platform",
                        "layanan",
                    ]
                    if column in normalized.columns
                ]
                frames.append(normalized[keep_columns].copy())
            except Exception:
                continue

        if not frames:
            return _fallback_sna_df(None)

        combined = pd.concat(frames, ignore_index=True, sort=False)
        combined = _enrich_combined_sna_followers(combined, None)
        return combined.reset_index(drop=True)
    except Exception:
        return _fallback_sna_df(None)


@st.cache_data(show_spinner=False, ttl=60, max_entries=6)
def load_home_sna_projection() -> pd.DataFrame:
    """Muat data SNA minimal yang dipakai tabel influencer Beranda."""
    try:
        file_signature = get_sna_file_signature(None)
        followers_signature = (
            get_sentiment_file_signature("IndiBiz")
            + "|"
            + get_sentiment_file_signature("Telkomsel")
        )
        dataframe = _load_home_sna_cached(file_signature, followers_signature)
        if dataframe is None or dataframe.empty:
            return _fallback_sna_df(None)
        return dataframe
    except Exception as error:
        st.error(f"Data SNA ringkas Beranda gagal dimuat: {error}")
        return _fallback_sna_df(None)


@st.cache_data(show_spinner=False, ttl=60, max_entries=12)
def load_sna_data(
    layanan: str | None = None,
    recommendation_mode: bool = False,
) -> pd.DataFrame:
    """
    Muat data SNA dari file yang relevan dengan layanan terpilih.

    Pemanggilan lama load_sna_data() tetap didukung. Untuk halaman Rekomendasi,
    ``recommendation_mode=True`` membuat enrichment followers memakai proyeksi
    sentimen yang sudah dicache sehingga file besar tidak dibaca ulang.
    """
    try:
        if not sna_file_exists(layanan):
            st.warning("File SNA aktual tidak ditemukan di folder data. Menggunakan data dummy SNA.")
        signature = get_sna_file_signature(layanan)
        if layanan == "IndiBiz":
            followers_signature = get_sentiment_file_signature("IndiBiz")
        elif layanan == "Telkomsel":
            followers_signature = get_sentiment_file_signature("Telkomsel")
        elif layanan is None:
            followers_signature = (
                get_sentiment_file_signature("IndiBiz")
                + "|"
                + get_sentiment_file_signature("Telkomsel")
            )
        else:
            followers_signature = "tidak-berlaku"
        return _load_sna_cached(
            layanan,
            signature,
            followers_signature,
            recommendation_mode=bool(recommendation_mode),
        )
    except Exception as e:
        st.error(f"Gagal memuat data SNA: {e}")
        st.warning("Menggunakan data dummy SNA sebagai fallback.")
        return _fallback_sna_df(layanan)


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


INFLUENCER_CONTENT_COLUMNS = {
    "username": ["username", "from_username", "user", "screen_name"],
    "platform": ["platform", "specific_resource_type", "source_platform"],
    "content": ["content", "text", "comment_text", "tweet_text", "caption"],
    "followers": ["followers", "follower_count", "followers_count"],
    "predicted_sentiment": ["predicted_sentiment", "final_sentiment", "sentiment", "label"],
    "date": ["date", "date_created", "created_at", "timestamp"],
    "link": ["link", "url", "post_url", "permalink"],
    "engagement": ["engagement", "engagement_count"],
    "like": ["like", "likes", "like_count"],
    "comment": ["comment", "comments", "comment_count"],
    "share": ["share", "shares", "share_count", "retweet_count"],
    "view": ["view", "views", "view_count", "impression"],
    "specific_type": ["specific_type", "type"],
    "content_type": ["content_type"],
    "post_type": ["post_type"],
    "resource_type": ["resource_type"],
}

INFLUENCER_CONTENT_REQUIRED = ["username", "platform", "content"]

TOPIC_REQUIRED_COLS = ["platform", "content", "predicted_sentiment"]


def _topic_fallback_df(layanan: str) -> pd.DataFrame:
    """Ambil subset ringan data dummy untuk halaman Analisis Topik."""
    fallback = _fallback_sentiment_df(layanan)
    columns = [
        column
        for column in ["platform", "content", "content_clean", "predicted_sentiment", "layanan"]
        if column in fallback.columns
    ]
    return fallback[columns].copy().reset_index(drop=True)


def _find_topic_source_columns(columns: list[str]) -> dict[str, str]:
    """Petakan kolom sumber CSV ke kolom minimal halaman Analisis Topik."""
    lookup = {str(column).strip().lower(): str(column) for column in columns}
    selected: dict[str, str] = {}
    for canonical in TOPIC_REQUIRED_COLS:
        for alias in CANONICAL_SENTIMENT_COLS[canonical]:
            source = lookup.get(alias.lower())
            if source is not None:
                selected[canonical] = source
                break
    return selected


def _read_topic_csv_bytes_flexible(raw: bytes) -> pd.DataFrame | None:
    """Baca kolom minimal Analisis Topik dari isi CSV berbentuk bytes."""
    attempts = [
        (",", "utf-8-sig"),
        (";", "utf-8-sig"),
        ("\t", "utf-8-sig"),
        (",", "latin-1"),
        (";", "latin-1"),
    ]
    for delimiter, encoding in attempts:
        try:
            header = pd.read_csv(
                BytesIO(raw),
                delimiter=delimiter,
                encoding=encoding,
                nrows=0,
            )
            mapping = _find_topic_source_columns(list(header.columns))
            if "content" not in mapping or "predicted_sentiment" not in mapping:
                continue

            usecols = list(dict.fromkeys(mapping.values()))
            frame = pd.read_csv(
                BytesIO(raw),
                delimiter=delimiter,
                encoding=encoding,
                usecols=usecols,
                dtype=str,
                keep_default_na=False,
                na_filter=False,
                low_memory=True,
            )
            rename = {source: canonical for canonical, source in mapping.items()}
            return frame.rename(columns=rename)
        except Exception:
            continue
    return None


def _read_topic_csv_flexible(path: str) -> pd.DataFrame | None:
    """Baca hanya kolom platform, komentar, dan sentimen dari CSV besar."""
    try:
        return _read_topic_csv_bytes_flexible(Path(path).read_bytes())
    except Exception:
        return None


def _read_topic_excel_flexible(source) -> pd.DataFrame | None:
    """Baca kolom minimal Analisis Topik dari workbook Excel."""
    try:
        workbook = pd.ExcelFile(source)
        for sheet_name in workbook.sheet_names:
            try:
                header = pd.read_excel(workbook, sheet_name=sheet_name, nrows=0)
                mapping = _find_topic_source_columns(list(header.columns))
                if "content" not in mapping or "predicted_sentiment" not in mapping:
                    continue
                usecols = list(dict.fromkeys(mapping.values()))
                frame = pd.read_excel(
                    workbook,
                    sheet_name=sheet_name,
                    usecols=usecols,
                    dtype=str,
                )
                rename = {source_name: canonical for canonical, source_name in mapping.items()}
                return frame.rename(columns=rename)
            except Exception:
                continue
    except Exception:
        return None
    return None


def _read_topic_source_flexible(path: str) -> pd.DataFrame | None:
    """Baca subset Analisis Topik dari CSV, Excel, atau ZIP."""
    source = Path(path)
    suffix = source.suffix.lower()

    if suffix == ".csv":
        return _read_topic_csv_flexible(str(source))
    if suffix in {".xlsx", ".xls"}:
        return _read_topic_excel_flexible(source)
    if suffix == ".zip":
        try:
            with zipfile.ZipFile(source) as archive:
                members = [
                    name for name in archive.namelist()
                    if not name.endswith("/") and Path(name).suffix.lower() in {".csv", ".xlsx", ".xls"}
                ]
                members.sort(key=lambda name: 0 if Path(name).suffix.lower() == ".csv" else 1)
                for member in members:
                    raw = archive.read(member)
                    member_suffix = Path(member).suffix.lower()
                    if member_suffix == ".csv":
                        frame = _read_topic_csv_bytes_flexible(raw)
                    else:
                        frame = _read_topic_excel_flexible(BytesIO(raw))
                    if frame is not None and not frame.empty:
                        return frame
        except Exception:
            return None
    return None


def _normalize_topic_df(df: pd.DataFrame, layanan: str) -> pd.DataFrame:
    """Normalisasi subset data khusus halaman Analisis Topik."""
    if df is None or df.empty:
        return _topic_fallback_df(layanan)

    result = df.copy()
    if "platform" not in result.columns:
        result["platform"] = "lainnya"
    if "content" not in result.columns or "predicted_sentiment" not in result.columns:
        raise ValueError("Kolom komentar atau sentimen tidak ditemukan.")

    result["platform"] = (
        result["platform"]
        .fillna("lainnya")
        .astype(str)
        .str.lower()
        .str.strip()
        .str.replace("'", "", regex=False)
    )
    result["platform"] = result["platform"].replace(
        {
            "x": "twitter",
            "twitter/x": "twitter",
            "tik tok": "tiktok",
            "ig": "instagram",
        }
    )
    result["content"] = result["content"].fillna("").astype(str).str.strip()
    result["predicted_sentiment"] = (
        result["predicted_sentiment"]
        .fillna("neutral")
        .astype(str)
        .str.lower()
        .str.strip()
        .str.lstrip("'")
        .map(SENTIMENT_MAP)
        .fillna("neutral")
    )
    result = result[result["content"].ne("")].copy()
    result["layanan"] = layanan
    return result.reset_index(drop=True)


@st.cache_data(show_spinner=False, max_entries=6)
def _load_topic_data_cached(layanan: str, file_signature: str) -> pd.DataFrame:
    """Muat subset CSV ringan dan cache berdasarkan versi file sumber."""
    del file_signature  # Dipakai sebagai bagian cache key agar data baru terdeteksi.
    source = _resolve_sentiment_source(layanan)
    if source is None:
        return _topic_fallback_df(layanan)

    frame = _read_topic_source_flexible(str(source))
    if frame is None or frame.empty:
        return _topic_fallback_df(layanan)
    return _normalize_topic_df(frame, layanan)


def get_sentiment_file_signature(layanan: str) -> str:
    """Ambil tanda tangan ukuran dan waktu ubah file sentimen."""
    try:
        path = _resolve_sentiment_source(layanan)
        if path is None or not path.exists():
            return f"{layanan}:missing"
        stat = path.stat()
        return f"{layanan}:{path.name}:{stat.st_size}:{stat.st_mtime_ns}"
    except Exception:
        return f"{layanan}:unknown"


# -----------------------------------------------------------------------------
# Fase 11 Tahap 3 — validasi hasil prediksi batch IndoBERT IndiBiz
# -----------------------------------------------------------------------------
def summarize_indibiz_prediction_dataframe(
    df_raw: pd.DataFrame,
    source_name: str = "indibiz_output_sentiment.csv",
) -> dict[str, object]:
    """Ringkas kualitas file hasil prediksi batch IndiBiz tanpa mengubah data sumber.

    Fungsi ini memeriksa struktur keluaran Cell [14] dari sisi dashboard. Notebook
    Google Colab tidak dibuka, tidak ditulis, dan tidak dimodifikasi oleh fungsi ini.
    """
    result: dict[str, object] = {
        "file_found": True,
        "source_name": str(source_name or "indibiz_output_sentiment.csv"),
        "canonical_name": "indibiz_output_sentiment.csv",
        "is_canonical_name": str(source_name or "").strip().lower()
        == "indibiz_output_sentiment.csv",
        "ready": False,
        "total_rows_file": 0,
        "total_rows_dashboard": 0,
        "removed_rows": 0,
        "missing_columns": [],
        "unknown_sentiment_count": 0,
        "invalid_confidence_count": 0,
        "platform_counts": {"twitter": 0, "instagram": 0, "tiktok": 0},
        "sentiment_counts": {"positive": 0, "neutral": 0, "negative": 0},
        "average_confidence": {"positive": 0.0, "neutral": 0.0, "negative": 0.0},
        "overall_average_confidence": 0.0,
        "confidence_min": 0.0,
        "confidence_max": 0.0,
        "message": "File belum diperiksa.",
    }

    try:
        if df_raw is None or not isinstance(df_raw, pd.DataFrame) or df_raw.empty:
            result["message"] = "File hasil prediksi ditemukan, tetapi tidak memiliki baris data."
            return result

        raw_copy = df_raw.copy(deep=True)
        result["total_rows_file"] = int(len(raw_copy))

        canonical_preview = _normalize_columns(raw_copy.copy(), CANONICAL_SENTIMENT_COLS)
        canonical_preview = _clean_string_columns(canonical_preview)
        canonical_preview = _repair_sentiment_platform_column(canonical_preview)
        # Output batch IndiBiz resmi memiliki enam kolom utama. Tanggal bersifat
        # opsional dan diisi NaT oleh dashboard untuk kompatibilitas timeline.
        if "date" not in canonical_preview.columns:
            canonical_preview["date"] = pd.NaT
        missing = [
            column for column in REQUIRED_SENTIMENT_COLS
            if column not in canonical_preview.columns
        ]
        result["missing_columns"] = missing
        if missing:
            result["message"] = (
                "File belum merupakan output prediksi Fase 11. Kolom wajib yang "
                f"belum tersedia: {', '.join(missing)}."
            )
            return result

        raw_sentiments = (
            canonical_preview["predicted_sentiment"]
            .astype(str)
            .str.strip()
            .str.lower()
        )
        mapped_sentiments = raw_sentiments.map(SENTIMENT_MAP)
        result["unknown_sentiment_count"] = int(mapped_sentiments.isna().sum())

        raw_confidence = pd.to_numeric(
            canonical_preview["confidence"], errors="coerce"
        )
        invalid_confidence = raw_confidence.isna() | raw_confidence.lt(0) | raw_confidence.gt(1)
        result["invalid_confidence_count"] = int(invalid_confidence.sum())

        normalized = _normalize_sentiment_df(canonical_preview, "IndiBiz")
        result["total_rows_dashboard"] = int(len(normalized))
        result["removed_rows"] = max(
            0, int(result["total_rows_file"]) - int(result["total_rows_dashboard"])
        )

        platform_counts = (
            normalized["platform"]
            .value_counts()
            .reindex(["twitter", "instagram", "tiktok"], fill_value=0)
        )
        result["platform_counts"] = {
            key: int(platform_counts.get(key, 0))
            for key in ("twitter", "instagram", "tiktok")
        }

        sentiment_counts = (
            normalized["predicted_sentiment"]
            .value_counts()
            .reindex(["positive", "neutral", "negative"], fill_value=0)
        )
        result["sentiment_counts"] = {
            key: int(sentiment_counts.get(key, 0))
            for key in ("positive", "neutral", "negative")
        }

        confidence_series = pd.to_numeric(
            normalized["confidence_score"], errors="coerce"
        ).fillna(0.0)
        grouped_confidence = (
            normalized.assign(_confidence=confidence_series)
            .groupby("predicted_sentiment")["_confidence"]
            .mean()
        )
        result["average_confidence"] = {
            key: round(float(grouped_confidence.get(key, 0.0)), 4)
            for key in ("positive", "neutral", "negative")
        }
        result["overall_average_confidence"] = round(
            float(confidence_series.mean()) if len(confidence_series) else 0.0, 4
        )
        result["confidence_min"] = round(
            float(confidence_series.min()) if len(confidence_series) else 0.0, 4
        )
        result["confidence_max"] = round(
            float(confidence_series.max()) if len(confidence_series) else 0.0, 4
        )

        result["ready"] = bool(
            int(result["total_rows_dashboard"]) > 0
            and int(result["unknown_sentiment_count"]) == 0
            and int(result["invalid_confidence_count"]) == 0
        )
        if result["ready"]:
            result["message"] = (
                "Output prediksi batch IndoBERT IndiBiz valid dan siap ditampilkan "
                "pada dashboard."
            )
        else:
            result["message"] = (
                "File terbaca, tetapi masih ada label sentimen atau confidence yang "
                "tidak valid."
            )
        return result
    except Exception as error:
        result["message"] = f"Gagal memvalidasi output prediksi IndiBiz: {error}"
        return result


@st.cache_data(show_spinner=False, max_entries=8)
def _get_indibiz_prediction_status_cached(file_signature: str) -> dict[str, object]:
    """Baca dan validasi output Fase 11 dengan cache berdasarkan versi file."""
    del file_signature
    try:
        source = _resolve_indibiz_output_path(
            None,
            INDIBIZ_OUTPUT_SENTIMENT_PATH,
            legacy_relative_paths=(
                "data/indibiz_sentiment.csv",
                "data/indibiz_sentiment.xlsx",
            ),
        )
        if not source.exists():
            return {
                "file_found": False,
                "source_name": "Tidak ditemukan",
                "canonical_name": "indibiz_output_sentiment.csv",
                "is_canonical_name": False,
                "ready": False,
                "total_rows_file": 0,
                "total_rows_dashboard": 0,
                "removed_rows": 0,
                "missing_columns": [],
                "unknown_sentiment_count": 0,
                "invalid_confidence_count": 0,
                "platform_counts": {"twitter": 0, "instagram": 0, "tiktok": 0},
                "sentiment_counts": {"positive": 0, "neutral": 0, "negative": 0},
                "average_confidence": {"positive": 0.0, "neutral": 0.0, "negative": 0.0},
                "overall_average_confidence": 0.0,
                "confidence_min": 0.0,
                "confidence_max": 0.0,
                "message": (
                    "File data/indibiz_output_sentiment.csv belum tersedia. "
                    "Dashboard akan tetap memakai data dummy."
                ),
            }

        try:
            raw = _baca_csv_indibiz(source)
        except Exception:
            raw = None
        if raw is None:
            return {
                **summarize_indibiz_prediction_dataframe(pd.DataFrame(), source.name),
                "file_found": True,
                "message": "File ditemukan, tetapi formatnya belum dapat dibaca.",
            }
        return summarize_indibiz_prediction_dataframe(raw, source.name)
    except Exception as error:
        return {
            **summarize_indibiz_prediction_dataframe(pd.DataFrame()),
            "file_found": False,
            "message": f"Status output prediksi IndiBiz gagal diperiksa: {error}",
        }


def get_indibiz_prediction_status() -> dict[str, object]:
    """Kembalikan status output IndoBERT IndiBiz, bukan workbook mentah."""
    try:
        source = _resolve_indibiz_output_path(
            None,
            INDIBIZ_OUTPUT_SENTIMENT_PATH,
            legacy_relative_paths=(
                "data/indibiz_sentiment.csv",
                "data/indibiz_sentiment.xlsx",
            ),
        )
        if source.exists():
            stat = source.stat()
            signature = f"{source.name}:{stat.st_size}:{stat.st_mtime_ns}"
        else:
            signature = "indibiz_output:missing"
        return _get_indibiz_prediction_status_cached(signature)
    except Exception as error:
        st.error(f"Gagal membaca status prediksi batch IndiBiz: {error}")
        return {
            **summarize_indibiz_prediction_dataframe(pd.DataFrame()),
            "file_found": False,
            "message": "Status output prediksi IndiBiz belum tersedia.",
        }


def load_topic_data(layanan: str) -> pd.DataFrame:
    """Muat data minimal Analisis Topik tanpa membaca seluruh kolom CSV."""
    try:
        if not sentiment_file_exists(layanan):
            st.warning(
                f"File sentimen untuk {layanan} tidak ditemukan di folder data. "
                "Analisis Topik menggunakan data dummy."
            )
        signature = get_sentiment_file_signature(layanan)
        return _load_topic_data_cached(layanan, signature)
    except Exception as exc:
        st.error(f"Gagal memuat data Analisis Topik {layanan}: {exc}")
        st.warning("Menggunakan data dummy sebagai fallback.")
        return _topic_fallback_df(layanan)


def _find_influencer_content_columns(columns: list[str]) -> dict[str, str]:
    """Petakan kolom sumber ke kolom bukti konten influencer."""
    lookup = {str(column).strip().lower(): str(column) for column in columns}
    selected: dict[str, str] = {}
    for canonical, aliases in INFLUENCER_CONTENT_COLUMNS.items():
        for alias in aliases:
            source = lookup.get(alias.lower())
            if source is not None:
                selected[canonical] = source
                break
    return selected


def _read_influencer_content_csv_path(path: str) -> pd.DataFrame | None:
    """Baca hanya kolom bukti konten dari CSV besar."""
    attempts = [
        (",", "utf-8-sig"),
        (";", "utf-8-sig"),
        ("\t", "utf-8-sig"),
        (",", "latin-1"),
        (";", "latin-1"),
    ]
    for delimiter, encoding in attempts:
        try:
            header = pd.read_csv(
                path,
                delimiter=delimiter,
                encoding=encoding,
                nrows=0,
            )
            mapping = _find_influencer_content_columns(list(header.columns))
            if not all(column in mapping for column in INFLUENCER_CONTENT_REQUIRED):
                continue
            usecols = list(dict.fromkeys(mapping.values()))
            frame = pd.read_csv(
                path,
                delimiter=delimiter,
                encoding=encoding,
                usecols=usecols,
                dtype=str,
                keep_default_na=False,
                na_filter=False,
                low_memory=True,
                memory_map=True,
            )
            rename = {source: canonical for canonical, source in mapping.items()}
            return frame.rename(columns=rename)
        except Exception:
            continue
    return None


def _read_influencer_content_csv_bytes(raw: bytes) -> pd.DataFrame | None:
    """Baca kolom bukti konten dari CSV di dalam ZIP."""
    attempts = [
        (",", "utf-8-sig"),
        (";", "utf-8-sig"),
        ("\t", "utf-8-sig"),
        (",", "latin-1"),
        (";", "latin-1"),
    ]
    for delimiter, encoding in attempts:
        try:
            header = pd.read_csv(
                BytesIO(raw),
                delimiter=delimiter,
                encoding=encoding,
                nrows=0,
            )
            mapping = _find_influencer_content_columns(list(header.columns))
            if not all(column in mapping for column in INFLUENCER_CONTENT_REQUIRED):
                continue
            usecols = list(dict.fromkeys(mapping.values()))
            frame = pd.read_csv(
                BytesIO(raw),
                delimiter=delimiter,
                encoding=encoding,
                usecols=usecols,
                dtype=str,
                keep_default_na=False,
                na_filter=False,
                low_memory=True,
            )
            rename = {source: canonical for canonical, source in mapping.items()}
            return frame.rename(columns=rename)
        except Exception:
            continue
    return None


def _read_influencer_content_excel(source) -> pd.DataFrame | None:
    """Baca kolom bukti konten dari workbook Excel."""
    try:
        workbook = pd.ExcelFile(source)
        for sheet_name in workbook.sheet_names:
            try:
                header = pd.read_excel(workbook, sheet_name=sheet_name, nrows=0)
                mapping = _find_influencer_content_columns(list(header.columns))
                if not all(column in mapping for column in INFLUENCER_CONTENT_REQUIRED):
                    continue
                usecols = list(dict.fromkeys(mapping.values()))
                frame = pd.read_excel(
                    workbook,
                    sheet_name=sheet_name,
                    usecols=usecols,
                    dtype=str,
                )
                rename = {source_name: canonical for canonical, source_name in mapping.items()}
                return frame.rename(columns=rename)
            except Exception:
                continue
    except Exception:
        return None
    return None


def _read_influencer_content_source(path: str) -> pd.DataFrame | None:
    """Baca bukti konten asli dari CSV, Excel, atau ZIP."""
    source = Path(path)
    suffix = source.suffix.lower()
    if suffix == ".csv":
        return _read_influencer_content_csv_path(str(source))
    if suffix in {".xlsx", ".xls"}:
        return _read_influencer_content_excel(source)
    if suffix == ".zip":
        try:
            with zipfile.ZipFile(source) as archive:
                members = [
                    name for name in archive.namelist()
                    if not name.endswith("/")
                    and Path(name).suffix.lower() in {".csv", ".xlsx", ".xls"}
                ]
                members.sort(key=lambda name: 0 if Path(name).suffix.lower() == ".csv" else 1)
                for member in members:
                    raw = archive.read(member)
                    member_suffix = Path(member).suffix.lower()
                    if member_suffix == ".csv":
                        frame = _read_influencer_content_csv_bytes(raw)
                    else:
                        frame = _read_influencer_content_excel(BytesIO(raw))
                    if frame is not None and not frame.empty:
                        return frame
        except Exception:
            return None
    return None


def _normalize_recommendation_source_df(
    frame: pd.DataFrame,
    layanan: str,
) -> pd.DataFrame:
    """Normalisasi satu proyeksi sumber untuk topik dan rekomendasi influencer.

    Berbeda dari loader influencer publik, baris tanpa username tidak dibuang
    di sini karena baris tersebut masih sah untuk agregasi topik. Filter username
    baru diterapkan ketika data dipakai sebagai bukti influencer.
    """
    canonical_columns = list(INFLUENCER_CONTENT_COLUMNS)
    if frame is None or frame.empty:
        return pd.DataFrame(columns=canonical_columns + ["layanan"])

    result = frame.copy()
    if "content" not in result.columns:
        return pd.DataFrame(columns=canonical_columns + ["layanan"])
    for column in canonical_columns:
        if column not in result.columns:
            result[column] = ""

    for column in result.select_dtypes(include="object").columns:
        result[column] = (
            result[column]
            .fillna("")
            .astype(str)
            .str.strip()
            .str.lstrip("'")
        )

    result["username"] = result["username"].str.lstrip("@").str.strip()
    result["platform"] = (
        result["platform"]
        .str.lower()
        .str.strip()
        .replace(
            {
                "x": "twitter",
                "twitter/x": "twitter",
                "tik tok": "tiktok",
                "ig": "instagram",
            }
        )
    )
    result["predicted_sentiment"] = (
        result["predicted_sentiment"]
        .str.lower()
        .str.strip()
        .map(SENTIMENT_MAP)
        .fillna("neutral")
    )
    for column in ("followers", "engagement", "like", "comment", "share", "view"):
        result[column] = pd.to_numeric(result[column], errors="coerce").fillna(0)

    result = result[
        result["content"].ne("")
        & result["platform"].isin(["twitter", "instagram", "tiktok"])
    ].copy()
    result["layanan"] = layanan
    return result[canonical_columns + ["layanan"]].reset_index(drop=True)


@st.cache_data(show_spinner=False, max_entries=6)
def _load_recommendation_source_cached(
    layanan: str,
    file_signature: str,
) -> pd.DataFrame:
    """Baca file sentimen besar satu kali untuk topik + rekomendasi.

    ``file_signature`` menjadi cache key sehingga perubahan file tetap terdeteksi.
    Cache ini sengaja menjadi boundary I/O bersama agar cold-open Rekomendasi
    tidak mengulang parsing file yang sama melalui dua loader berbeda.
    """
    del file_signature
    source = _resolve_sentiment_source(layanan)
    if source is None:
        return _normalize_recommendation_source_df(pd.DataFrame(), layanan)
    frame = _read_influencer_content_source(str(source))
    if frame is None or frame.empty:
        return _normalize_recommendation_source_df(pd.DataFrame(), layanan)
    return _normalize_recommendation_source_df(frame, layanan)


def load_recommendation_source_data(layanan: str) -> pd.DataFrame:
    """Muat proyeksi bersama khusus kebutuhan halaman Rekomendasi.

    Fungsi publik ini tidak mengubah kontrak loader lama. Seluruh error tetap
    dipetakan ke DataFrame kosong agar halaman dapat memakai fallback existing.
    """
    try:
        if not sentiment_file_exists(layanan):
            return _normalize_recommendation_source_df(pd.DataFrame(), layanan)
        signature = get_sentiment_file_signature(layanan)
        return _load_recommendation_source_cached(layanan, signature)
    except Exception as exc:
        st.error(f"Gagal memuat sumber rekomendasi {layanan}: {exc}")
        return _normalize_recommendation_source_df(pd.DataFrame(), layanan)


def _normalize_influencer_content_df(
    frame: pd.DataFrame,
    layanan: str,
) -> pd.DataFrame:
    """Normalisasi data konten asli tanpa membuat fallback palsu."""
    canonical_columns = list(INFLUENCER_CONTENT_COLUMNS)
    if frame is None or frame.empty:
        return pd.DataFrame(columns=canonical_columns + ["layanan"])

    result = frame.copy()
    for column in INFLUENCER_CONTENT_REQUIRED:
        if column not in result.columns:
            raise ValueError(f"Kolom wajib '{column}' tidak ditemukan pada sumber konten.")
    for column in canonical_columns:
        if column not in result.columns:
            result[column] = ""

    for column in result.select_dtypes(include="object").columns:
        result[column] = (
            result[column]
            .fillna("")
            .astype(str)
            .str.strip()
            .str.lstrip("'")
        )

    result["username"] = result["username"].str.lstrip("@").str.strip()
    result["platform"] = (
        result["platform"]
        .str.lower()
        .str.strip()
        .replace(
            {
                "x": "twitter",
                "twitter/x": "twitter",
                "tik tok": "tiktok",
                "ig": "instagram",
            }
        )
    )
    result["predicted_sentiment"] = (
        result["predicted_sentiment"]
        .str.lower()
        .str.strip()
        .map(SENTIMENT_MAP)
        .fillna("neutral")
    )
    for column in ("followers", "engagement", "like", "comment", "share", "view"):
        result[column] = pd.to_numeric(result[column], errors="coerce").fillna(0)

    result = result[
        result["username"].ne("")
        & result["content"].ne("")
        & result["platform"].isin(["twitter", "instagram", "tiktok"])
    ].copy()
    result["layanan"] = layanan
    return result[canonical_columns + ["layanan"]].reset_index(drop=True)


@st.cache_data(show_spinner=False, max_entries=6)
def _load_influencer_content_cached(
    layanan: str,
    file_signature: str,
) -> pd.DataFrame:
    """Ambil bukti influencer dari proyeksi sumber bersama yang sudah dicache."""
    shared = _load_recommendation_source_cached(layanan, file_signature)
    if shared is None or shared.empty:
        return _normalize_influencer_content_df(pd.DataFrame(), layanan)

    result = shared[shared["username"].fillna("").astype(str).str.strip().ne("")].copy()
    canonical_columns = list(INFLUENCER_CONTENT_COLUMNS) + ["layanan"]
    return result.loc[:, canonical_columns].reset_index(drop=True)


def load_influencer_content_data(layanan: str) -> pd.DataFrame:
    """Muat konten asli akun untuk validasi rekomendasi influencer."""
    try:
        if not sentiment_file_exists(layanan):
            return _normalize_influencer_content_df(pd.DataFrame(), layanan)
        signature = get_sentiment_file_signature(layanan)
        return _load_influencer_content_cached(layanan, signature)
    except Exception as exc:
        st.error(f"Gagal memuat konten asli influencer {layanan}: {exc}")
        return _normalize_influencer_content_df(pd.DataFrame(), layanan)


MODEL_REQUIRED_CONFIG = "config.json"
MODEL_WEIGHT_FILES = ("pytorch_model.bin", "model.safetensors", "tf_model.h5")
MODEL_TOKENIZER_FILES = (
    "tokenizer.json",
    "tokenizer_config.json",
    "vocab.txt",
    "sentencepiece.bpe.model",
)
MODEL_IGNORED_FILES = {".gitkeep", ".DS_Store"}
MODEL_SOURCE_FILE = "model_source.json"
DEFAULT_HF_MODEL_REPO = "mdhugol/indonesia-bert-sentiment-classification"


def _model_folder_has_real_files(folder: Path) -> bool:
    """Cek apakah folder model berisi file nyata, bukan hanya .gitkeep."""
    try:
        if not folder.is_dir():
            return False
        return any(
            item.is_file() and item.name not in MODEL_IGNORED_FILES
            for item in folder.iterdir()
        )
    except Exception:
        return False


def _model_folder_is_complete(folder: Path) -> bool:
    """Validasi file minimum model Transformers di folder lokal."""
    try:
        if not folder.is_dir():
            return False
        filenames = {
            item.name
            for item in folder.iterdir()
            if item.is_file() and item.name not in MODEL_IGNORED_FILES
        }
        has_config = MODEL_REQUIRED_CONFIG in filenames
        has_weight = any(name in filenames for name in MODEL_WEIGHT_FILES) or any(
            name.startswith("model-") and name.endswith(".safetensors")
            for name in filenames
        )
        has_tokenizer = any(name in filenames for name in MODEL_TOKENIZER_FILES)
        return bool(has_config and has_weight and has_tokenizer)
    except Exception:
        return False


def _model_folder_has_download_source(folder: Path) -> bool:
    """Cek apakah folder layanan punya penanda sumber download Hugging Face."""
    try:
        source_file = folder / MODEL_SOURCE_FILE
        if not source_file.is_file():
            return False
        payload = json.loads(source_file.read_text(encoding="utf-8"))
        repo_id = str(payload.get("repo_id") or payload.get("model_id") or "").strip()
        return bool(repo_id)
    except Exception:
        return False


def resolve_model_folder_for_service(layanan: str) -> tuple[Path, str]:
    """Kembalikan path kompatibilitas dan status model berbasis HuggingFace Hub.

    Path dipertahankan agar pemanggil lama tidak mengalami error. Runtime model
    tidak membaca atau menulis bobot ke path tersebut.
    """
    try:
        service = str(layanan or "").strip().lower()
        normalized = {
            "indihome": "indihome",
            "indibiz": "indibiz",
            "telkomsel": "telkomsel",
        }.get(service, service)
        model_path = _project_root() / "models" / normalized
        state = "ready" if normalized in MODEL_SERVICES else "coming_soon"
        return model_path, state
    except Exception as exc:
        st.error(f"Gagal menentukan status model {layanan}: {exc}")
        return _project_root() / "models" / "unknown", "coming_soon"


@st.cache_data(show_spinner=False, ttl=60, max_entries=4)
def load_model_status() -> dict:
    """Kembalikan status model runtime yang tersedia melalui HuggingFace Hub."""
    try:
        return {service: "ready" for service in MODEL_SERVICES}
    except Exception as exc:
        st.error(f"Gagal memeriksa status model: {exc}")
        return {service: "coming_soon" for service in MODEL_SERVICES}

def get_data_source_label(layanan: str) -> str:
    """Kembalikan label sumber data real atau dummy untuk layanan tertentu."""
    try:
        # Keberadaan data mentah saja belum cukup. IndiHome dan IndiBiz baru
        # disebut data real setelah output prediksi batch tervalidasi.
        if str(layanan).strip() == "IndiHome":
            status = get_indihome_prediction_status()
            return "📁 Data Real" if bool(status.get("ready")) else "🔧 Data Dummy"
        if str(layanan).strip() == "IndiBiz":
            status = get_indibiz_prediction_status()
            return "📁 Data Real" if bool(status.get("ready")) else "🔧 Data Dummy"
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
        sent_source = _resolve_sentiment_source(layanan)
        sent_path = str(sent_source) if sent_source is not None else _sentiment_csv_path(layanan)
        sna_sources = _resolve_sna_sources(layanan)

        sentiment_exists = sent_source is not None and sent_source.exists()
        sna_exists = bool(sna_sources)

        sentiment_rows = 0
        sna_edges = 0
        last_modified = "-"

        if sentiment_exists:
            sentiment_rows = len(load_sentiment_data(layanan))
            last_modified = datetime.fromtimestamp(os.path.getmtime(sent_path)).strftime(
                "%d-%m-%Y %H:%M"
            )
        if sna_exists:
            sna_edges = len(load_sna_data(layanan))

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

# ================================================================
# TAHAP 3 FASE 14 - LOADER KHUSUS OUTPUT INDIBIZ
# ================================================================
# Bagian ini hanya menambahkan kontrak loader IndiBiz. Loader IndiHome dan
# Telkomsel yang sudah berjalan tidak diubah.

INDIBIZ_OUTPUT_SENTIMENT_PATH = "data/indibiz_output_sentiment.csv"
INDIBIZ_OUTPUT_SNA_PATH = "data/indibiz_output_sna.csv"
INDIBIZ_OUTPUT_TOPIC_PATH = "data/indibiz_output_top_topic.csv"
INDIBIZ_OUTPUT_TOP_KATA_PATH = "data/indibiz_output_top_kata.csv"

INDIBIZ_SENTIMENT_COLUMNS = [
    "username",
    "platform",
    "content",
    "predicted_sentiment",
    "confidence_score",
    "followers",
]
INDIBIZ_SNA_COLUMNS = ["source", "target", "relationship", "followers", "platform"]
INDIBIZ_TOPIC_COLUMNS = ["sentiment", "topik", "keywords"]
INDIBIZ_TOP_KATA_COLUMNS = ["sentiment", "rank", "kata", "frekuensi"]


def _resolve_indibiz_output_path(
    file_path: str | Path | None,
    default_relative_path: str,
    legacy_relative_paths: tuple[str, ...] = (),
) -> Path:
    """Tentukan path CSV IndiBiz tanpa menulis atau mengubah file sumber."""
    if file_path is not None:
        path = Path(file_path)
        return path if path.is_absolute() else _project_root() / path

    default_path = _project_root() / default_relative_path
    if default_path.is_file():
        return default_path

    # Dukungan nama lama dipertahankan agar integrasi fase sebelumnya tidak rusak.
    for relative_path in legacy_relative_paths:
        legacy_path = _project_root() / relative_path
        if legacy_path.is_file():
            return legacy_path
    return default_path


def _baca_csv_indibiz(file_path: str | Path) -> pd.DataFrame:
    """Baca output IndiBiz dari CSV/CSV.GZ/Excel tanpa mengubah file sumber."""
    path = Path(file_path)
    if not path.is_absolute():
        path = _project_root() / path

    if not path.is_file():
        raise FileNotFoundError(f"File tidak ditemukan: {path}")

    if path.suffix.casefold() in {".xlsx", ".xls"}:
        try:
            dataframe = pd.read_excel(path)
            if dataframe.empty:
                raise ValueError(f"File Excel kosong: {path.name}")
            return dataframe
        except Exception as error:
            raise ValueError(f"Excel {path.name} tidak dapat dibaca: {error}") from error

    errors: list[str] = []
    for encoding in ("utf-8-sig", "utf-8", "latin-1"):
        try:
            dataframe = pd.read_csv(
                path,
                encoding=encoding,
                sep=None,
                engine="python",
                compression="infer",
            )
            if dataframe.empty:
                raise ValueError(f"File CSV kosong: {path.name}")
            return dataframe
        except Exception as error:
            errors.append(f"{encoding}: {error}")

    detail = " | ".join(errors[-3:])
    raise ValueError(f"CSV {path.name} tidak dapat dibaca. Detail: {detail}")


def _pastikan_kolom_indibiz(
    dataframe: pd.DataFrame,
    required_columns: list[str],
    source_name: str,
) -> pd.DataFrame:
    """Validasi kolom minimum agar halaman tidak memakai schema yang keliru."""
    missing = [column for column in required_columns if column not in dataframe.columns]
    if missing:
        raise ValueError(
            f"Kolom wajib pada {source_name} belum lengkap: {', '.join(missing)}"
        )
    return dataframe


def _indibiz_dashboard_columns(df: pd.DataFrame) -> pd.DataFrame:
    """Normalisasi output sentimen IndiBiz ke kolom halaman dashboard."""
    try:
        working = _normalize_columns(df.copy(), CANONICAL_SENTIMENT_COLS)
        working = _clean_string_columns(working)
        working = _repair_sentiment_platform_column(working)

        if "date" not in working.columns:
            working["date"] = pd.NaT
        if "content" in working.columns and "content_clean" not in working.columns:
            working["content_clean"] = working["content"].map(clean_text)

        normalized = _normalize_sentiment_df(working, "IndiBiz")
        if normalized.empty:
            raw_platforms: list[str] = []
            if "platform" in working.columns:
                raw_platforms = sorted(
                    {
                        str(value).strip()
                        for value in working["platform"].dropna().head(20).tolist()
                        if str(value).strip()
                    }
                )
            detail = ", ".join(raw_platforms[:6]) or "kosong/tidak dikenali"
            raise ValueError(
                "Tidak ada baris IndiBiz yang lolos normalisasi platform. "
                f"Contoh nilai platform: {detail}."
            )

        result = pd.DataFrame(
            {
                "date_created": normalized["date_created"],
                "platform": normalized["platform"],
                "username": normalized["username"],
                "followers": normalized["followers"],
                "content": normalized["content"],
                "content_clean": normalized["content_clean"],
                "predicted_sentiment": normalized["predicted_sentiment"],
                "confidence_score": normalized["confidence_score"],
            }
        )
        return result.reset_index(drop=True)
    except Exception:
        raise


@st.cache_data(show_spinner=False, max_entries=8)
def load_indibiz_sentiment(
    file_path: str | Path | None = None,
) -> pd.DataFrame:
    """Muat output IndoBERT IndiBiz dan gunakan dummy jika output belum valid."""
    try:
        resolved = _resolve_indibiz_output_path(
            file_path,
            INDIBIZ_OUTPUT_SENTIMENT_PATH,
            legacy_relative_paths=(
                "data/indibiz_sentiment.csv",
                "data/indibiz_sentiment.xlsx",
            ),
        )
        dataframe = _baca_csv_indibiz(resolved)
        normalized = _indibiz_dashboard_columns(dataframe)
        normalized.attrs.update(
            {
                "data_source": "real",
                "is_dummy": False,
                "source_file": resolved.name,
                "fallback_reason": "",
            }
        )
        return normalized
    except FileNotFoundError:
        message = (
            "File data/indibiz_output_sentiment.csv belum tersedia. "
            "Dashboard menggunakan 50 data dummy IndiBiz sementara."
        )
        st.warning(message)
        fallback = get_dummy_indibiz_sentiment()
        fallback.attrs.update(
            {
                "data_source": "dummy",
                "is_dummy": True,
                "source_file": "utils/dummy_data.py",
                "fallback_reason": message,
            }
        )
        return fallback
    except Exception as error:
        message = f"Output sentimen IndiBiz tidak valid: {error}"
        st.error(message)
        st.warning(
            "Dashboard menggunakan 50 data dummy IndiBiz agar analisis per platform "
            "tidak tampil kosong atau menyesatkan."
        )
        fallback = get_dummy_indibiz_sentiment()
        fallback.attrs.update(
            {
                "data_source": "dummy",
                "is_dummy": True,
                "source_file": "utils/dummy_data.py",
                "fallback_reason": message,
            }
        )
        return fallback


@st.cache_data(show_spinner=False, max_entries=8)
def load_indibiz_sna(
    file_path: str | Path | None = None,
) -> pd.DataFrame:
    """Muat indibiz_output_sna.csv atau gunakan dummy khusus IndiBiz."""
    try:
        resolved = _resolve_indibiz_output_path(
            file_path,
            INDIBIZ_OUTPUT_SNA_PATH,
            legacy_relative_paths=("data/indibiz_sna.csv",),
        )
        dataframe = _baca_csv_indibiz(resolved)
        _pastikan_kolom_indibiz(dataframe, INDIBIZ_SNA_COLUMNS, resolved.name)
        normalized = _normalize_sna_df(
            dataframe,
            layanan="IndiBiz",
            source_name=resolved.name,
        )
        if normalized.empty:
            raise ValueError("File SNA IndiBiz tidak menghasilkan edge yang valid.")
        return normalized.reset_index(drop=True)
    except FileNotFoundError:
        st.warning(
            "File data/indibiz_output_sna.csv belum tersedia. "
            "Dashboard menggunakan data dummy khusus IndiBiz sementara."
        )
        return get_dummy_indibiz_sna()
    except Exception as error:
        st.error(f"Gagal memuat data SNA IndiBiz: {error}")
        st.warning("Dashboard menggunakan data dummy khusus IndiBiz agar halaman tetap dapat dibuka.")
        return get_dummy_indibiz_sna()


@st.cache_data(show_spinner=False)
# ================================================================
# TAHAP 4 FASE 6 - LOADER KHUSUS TELKOMSEL
# ================================================================


def _dummy_telkomsel_sentiment() -> pd.DataFrame:
    """Buat fallback sentimen Telkomsel sebanyak 50 baris yang realistis."""
    try:
        dataframe = get_dummy_sentiment_data("Telkomsel").copy()
        dataframe["date_created"] = pd.to_datetime(
            dataframe["date_created"], errors="coerce"
        )
        dataframe["date"] = dataframe["date_created"]
        dataframe["platform"] = (
            dataframe["platform"].astype(str).str.lower().str.strip()
        )
        dataframe["predicted_sentiment"] = (
            dataframe["predicted_sentiment"]
            .astype(str)
            .str.lower()
            .str.strip()
            .map(SENTIMENT_MAP)
            .fillna("neutral")
        )
        dataframe["followers"] = (
            pd.to_numeric(dataframe["followers"], errors="coerce")
            .fillna(0)
            .clip(lower=0, upper=2_147_483_647)
            .astype("int32")
        )
        dataframe["confidence_score"] = (
            pd.to_numeric(dataframe["confidence_score"], errors="coerce")
            .fillna(0.0)
            .clip(lower=0.0, upper=1.0)
            .astype("float32")
        )
        dataframe["confidence"] = dataframe["confidence_score"]
        dataframe["layanan"] = "Telkomsel"
        return dataframe.reset_index(drop=True)
    except Exception as error:
        st.error(f"Gagal membuat data dummy sentimen Telkomsel: {error}")
        return pd.DataFrame(
            columns=[
                "date_created",
                "date",
                "platform",
                "username",
                "followers",
                "content",
                "content_clean",
                "predicted_sentiment",
                "confidence_score",
                "confidence",
                "layanan",
            ]
        )


def _resolve_telkomsel_sentiment_path(
    file_path: str | Path | None = None,
) -> Path | None:
    """Cari file sentimen Telkomsel dengan memprioritaskan path baku fase ini."""
    try:
        if file_path is not None:
            path = Path(file_path)
            return path if path.is_absolute() else _project_root() / path

        standard_path = _project_root() / TELKOMSEL_CSV_PATH
        if standard_path.is_file():
            return standard_path
        return _resolve_sentiment_source("Telkomsel")
    except Exception as error:
        st.error(f"Gagal mencari file sentimen Telkomsel: {error}")
        return None


def _read_telkomsel_sentiment_file(path: Path) -> pd.DataFrame:
    """Baca CSV Telkomsel dan dukung skema output pipeline Fase 5."""
    attempts = [
        (",", "utf-8-sig"),
        (";", "utf-8-sig"),
        ("\t", "utf-8-sig"),
        (",", "latin-1"),
        (";", "latin-1"),
    ]
    last_error: Exception | None = None

    for delimiter, encoding in attempts:
        try:
            dataframe = pd.read_csv(
                path,
                sep=delimiter,
                encoding=encoding,
                low_memory=False,
            )
            if len(dataframe.columns) <= 1:
                continue
            return dataframe
        except Exception as error:
            last_error = error

    detail = str(last_error) if last_error is not None else "format tidak dikenali"
    raise ValueError(f"CSV Telkomsel tidak dapat dibaca: {detail}")


def _telkomsel_dashboard_columns(dataframe: pd.DataFrame) -> pd.DataFrame:
    """Normalisasi output Telkomsel ke kolom kanonik dashboard."""
    try:
        if dataframe is None or dataframe.empty:
            raise ValueError("DataFrame Telkomsel kosong.")

        work = dataframe.copy()
        lookup = {str(column).strip().lower(): column for column in work.columns}
        aliases = {
            "date_created": ["date_created", "date", "created_at", "timestamp"],
            "platform": ["platform", "specific_resource_type", "source_platform"],
            "username": ["username", "from_username", "user", "screen_name"],
            "followers": ["followers", "follower_count", "followers_count"],
            "content": ["content", "text", "comment", "tweet_text", "caption"],
            "content_clean": ["content_clean", "cleaned_text", "clean_text"],
            "predicted_sentiment": [
                "predicted_sentiment",
                "final_sentiment",
                "sentiment",
                "label",
            ],
            "confidence_score": [
                "confidence_score",
                "confidence",
                "score",
                "sentiment_confidence_level",
            ],
            "topic": ["topic", "topik", "topic_name"],
            "layanan": ["layanan", "service"],
        }

        rename: dict[str, str] = {}
        for canonical, candidates in aliases.items():
            for candidate in candidates:
                source = lookup.get(candidate.lower())
                if source is not None:
                    rename[str(source)] = canonical
                    break
        work = work.rename(columns=rename)

        required = [
            "date_created",
            "platform",
            "username",
            "content",
            "predicted_sentiment",
            "confidence_score",
        ]
        missing = [column for column in required if column not in work.columns]
        if missing:
            raise ValueError(
                "Kolom wajib Telkomsel tidak ditemukan: " + ", ".join(missing)
            )

        if "followers" not in work.columns:
            work["followers"] = 0
        if "content_clean" not in work.columns:
            work["content_clean"] = work["content"].map(clean_text)
        if "topic" not in work.columns:
            work["topic"] = "Belum diklasifikasikan"

        # Format tanggal Telkomsel aktual menggunakan titik pada bagian jam,
        # misalnya ``30/12/2025 18.03.47``. Samakan perlakuannya dengan
        # loader IndiHome agar nilai tersebut tidak seluruhnya berubah menjadi
        # NaT dan grafik Tren Waktu tetap memperoleh tanggal penelitian.
        if pd.api.types.is_datetime64_any_dtype(work["date_created"]):
            work["date_created"] = pd.to_datetime(
                work["date_created"], errors="coerce"
            )
        else:
            telkomsel_date_text = (
                work["date_created"].astype("string").fillna("").str.strip()
            )
            telkomsel_date_text = telkomsel_date_text.str.replace(
                r"(\d{1,2})\.(\d{2})\.(\d{2})$",
                r"\1:\2:\3",
                regex=True,
            )
            work["date_created"] = pd.to_datetime(
                telkomsel_date_text,
                errors="coerce",
                dayfirst=True,
                format="mixed",
            )
        work["date"] = work["date_created"]
        work["platform"] = (
            work["platform"]
            .astype(str)
            .str.lower()
            .str.strip()
            .replace(
                {
                    "x": "twitter",
                    "twitter/x": "twitter",
                    "twitter (x)": "twitter",
                    "x/twitter": "twitter",
                    "ig": "instagram",
                }
            )
        )
        work["username"] = (
            work["username"].astype(str).str.lstrip("'").str.strip()
        )
        work["content"] = work["content"].astype("string").fillna("").str.strip()
        work["content_clean"] = (
            work["content_clean"].astype("string").fillna("").str.strip()
        )
        empty_clean = work["content_clean"].eq("")
        if empty_clean.any():
            work.loc[empty_clean, "content_clean"] = (
                work.loc[empty_clean, "content"].map(clean_text)
            )

        work["followers"] = (
            pd.to_numeric(work["followers"], errors="coerce")
            .fillna(0)
            .clip(lower=0, upper=2_147_483_647)
            .astype("int32")
        )
        work["confidence_score"] = (
            pd.to_numeric(work["confidence_score"], errors="coerce")
            .fillna(0.0)
            .clip(lower=0.0, upper=1.0)
            .astype("float32")
        )
        work["confidence"] = work["confidence_score"]
        work["predicted_sentiment"] = (
            work["predicted_sentiment"]
            .astype(str)
            .str.lower()
            .str.strip()
            .map(SENTIMENT_MAP)
            .fillna("neutral")
        )
        work = work[
            work["platform"].isin(["twitter", "instagram", "tiktok"])
        ].copy()
        work = work[
            work["content"].ne("")
            & work["content"].str.lower().ne("nan")
            & work["content"].str.lower().ne("none")
        ].copy()

        if "layanan" not in work.columns:
            work["layanan"] = "Telkomsel"
        else:
            layanan_text = work["layanan"].astype(str).str.strip()
            work["layanan"] = layanan_text.mask(
                layanan_text.eq("") | layanan_text.str.lower().isin({"nan", "none"}),
                "Telkomsel",
            )

        ordered = [
            "date_created",
            "date",
            "platform",
            "username",
            "followers",
            "content",
            "content_clean",
            "predicted_sentiment",
            "confidence_score",
            "confidence",
            "topic",
            "layanan",
        ]
        return work[ordered].reset_index(drop=True)
    except Exception as error:
        raise ValueError(f"Normalisasi data sentimen Telkomsel gagal: {error}") from error


@st.cache_data(show_spinner=False, max_entries=8)
def load_telkomsel_sentiment(
    file_path: str | Path | None = None,
) -> pd.DataFrame:
    """Muat data sentimen Telkomsel atau gunakan 50 baris dummy realistis."""
    try:
        resolved = _resolve_telkomsel_sentiment_path(file_path)
        if resolved is None or not resolved.is_file():
            st.warning(
                "File data/telkomsel_sentiment.csv belum tersedia. "
                "Dashboard menggunakan data dummy Telkomsel sementara."
            )
            return _dummy_telkomsel_sentiment()

        dataframe = _read_telkomsel_sentiment_file(resolved)
        normalized = _telkomsel_dashboard_columns(dataframe)
        if normalized.empty:
            raise ValueError("File sentimen Telkomsel tidak menghasilkan baris valid.")
        return normalized
    except FileNotFoundError:
        st.warning(
            "File sentimen Telkomsel belum tersedia. "
            "Dashboard menggunakan data dummy Telkomsel sementara."
        )
        return _dummy_telkomsel_sentiment()
    except Exception as error:
        st.error(f"Gagal memuat data sentimen Telkomsel: {error}")
        st.warning(
            "Dashboard menggunakan data dummy Telkomsel agar halaman tetap dapat dibuka."
        )
        return _dummy_telkomsel_sentiment()


@st.cache_data(show_spinner=False)
def load_telkomsel_sna(file_path: str | Path | None = None) -> pd.DataFrame:
    """Muat dan filter edge list Telkomsel atau gunakan dummy khusus Telkomsel."""
    try:
        if file_path is not None:
            resolved = Path(file_path)
            if not resolved.is_absolute():
                resolved = _project_root() / resolved
            if not resolved.is_file():
                raise FileNotFoundError(str(resolved))

            frame = _read_sna_source_frame(resolved)
            if frame is None or frame.empty:
                raise ValueError("File SNA Telkomsel kosong atau formatnya tidak terbaca.")
            dataframe = _normalize_sna_df(
                frame,
                layanan="Telkomsel",
                source_name=resolved.name,
            )
            dataframe = _enrich_telkomsel_sna_followers(dataframe)
        else:
            dataframe = load_sna_data("Telkomsel")

        if dataframe is None or dataframe.empty:
            return _fallback_sna_df("Telkomsel")

        result = dataframe.copy()
        if "layanan" in result.columns:
            result = result[
                result["layanan"]
                .astype(str)
                .str.lower()
                .str.strip()
                .eq("telkomsel")
            ].copy()
        else:
            result["layanan"] = "Telkomsel"

        if result.empty:
            st.warning(
                "Data SNA Telkomsel tidak ditemukan setelah proses filter. "
                "Dashboard menggunakan data dummy khusus Telkomsel."
            )
            return _fallback_sna_df("Telkomsel")
        return result.reset_index(drop=True)
    except FileNotFoundError:
        st.warning(
            "File SNA Telkomsel belum tersedia. Dashboard menggunakan data "
            "dummy khusus Telkomsel sementara."
        )
        return _fallback_sna_df("Telkomsel")
    except Exception as error:
        st.error(f"Gagal memuat data SNA Telkomsel: {error}")
        st.warning(
            "Dashboard menggunakan data dummy khusus Telkomsel agar halaman "
            "tetap dapat dibuka."
        )
        return _fallback_sna_df("Telkomsel")


def _zero_service_stats() -> dict:
    """Kembalikan struktur statistik layanan dengan seluruh nilai nol."""
    return {
        "total_data": 0,
        "total_positif": 0,
        "total_netral": 0,
        "total_negatif": 0,
        "pct_positif": 0.0,
        "pct_netral": 0.0,
        "pct_negatif": 0.0,
        "platform_counts": {},
    }


def _calculate_service_stats(dataframe: pd.DataFrame) -> dict:
    """Hitung statistik sentimen dengan kontrak key berbahasa Indonesia."""
    try:
        if dataframe is None or dataframe.empty:
            return _zero_service_stats()
        if "predicted_sentiment" not in dataframe.columns:
            raise ValueError("Kolom predicted_sentiment tidak ditemukan.")

        sentiment = dataframe["predicted_sentiment"].astype(str).str.lower().str.strip()
        total = int(len(dataframe))
        positif = int(sentiment.eq("positive").sum())
        netral = int(sentiment.eq("neutral").sum())
        negatif = int(sentiment.eq("negative").sum())

        if "platform" in dataframe.columns:
            platform_counts = {
                str(platform): int(count)
                for platform, count in (
                    dataframe["platform"]
                    .astype(str)
                    .str.lower()
                    .str.strip()
                    .value_counts()
                    .to_dict()
                    .items()
                )
            }
        else:
            platform_counts = {}

        return {
            "total_data": total,
            "total_positif": positif,
            "total_netral": netral,
            "total_negatif": negatif,
            "pct_positif": round((positif / total) * 100, 1) if total else 0.0,
            "pct_netral": round((netral / total) * 100, 1) if total else 0.0,
            "pct_negatif": round((negatif / total) * 100, 1) if total else 0.0,
            "platform_counts": platform_counts,
        }
    except Exception as error:
        st.error(f"Gagal menghitung statistik layanan: {error}")
        return _zero_service_stats()


@st.cache_data(show_spinner=False)
def get_telkomsel_stats() -> dict:
    """Hitung statistik sentimen Telkomsel untuk kartu ringkasan dashboard."""
    try:
        dataframe = load_telkomsel_sentiment()
        return _calculate_service_stats(dataframe)
    except Exception as error:
        st.error(f"Gagal menghitung statistik Telkomsel: {error}")
        return _zero_service_stats()


# Fungsi kompatibilitas berikut hanya meneruskan ke loader lama. Logika loader
# IndiHome dan IndiBiz tidak diubah sedikit pun.
@st.cache_data(show_spinner=False, max_entries=8)
def load_indihome_sentiment() -> pd.DataFrame:
    """Muat sentimen IndiHome melalui loader generik existing.

    Wrapper kompatibilitas ini tidak mengubah loader inti IndiHome. Jika sumber
    tersedia tetapi seluruh baris gugur saat normalisasi, fungsi mengembalikan
    dummy realistis agar kontrak data loader tetap terpenuhi.
    """
    try:
        dataframe = load_sentiment_data("IndiHome")
        if dataframe is None or dataframe.empty:
            st.warning(
                "Data sentimen IndiHome tidak menghasilkan baris valid. "
                "Dashboard menggunakan data dummy IndiHome sementara."
            )
            return _fallback_sentiment_df("IndiHome")
        return dataframe
    except Exception as error:
        st.error(f"Gagal memuat data sentimen IndiHome: {error}")
        return _fallback_sentiment_df("IndiHome")


@st.cache_data(show_spinner=False)
def load_indihome_sna() -> pd.DataFrame:
    """Muat SNA IndiHome melalui loader generik existing."""
    try:
        return load_sna_data("IndiHome")
    except Exception as error:
        st.error(f"Gagal memuat data SNA IndiHome: {error}")
        return _fallback_sna_df("IndiHome")


@st.cache_data(show_spinner=False, max_entries=8)
def get_indihome_stats() -> dict:
    """Hitung statistik IndiHome tanpa mengubah loader existing."""
    try:
        return _calculate_service_stats(load_indihome_sentiment())
    except Exception as error:
        st.error(f"Gagal menghitung statistik IndiHome: {error}")
        return _zero_service_stats()


@st.cache_data(show_spinner=False)
def get_indibiz_stats() -> dict:
    """Hitung statistik IndiBiz tanpa mengubah loader existing."""
    try:
        return _calculate_service_stats(load_indibiz_sentiment())
    except Exception as error:
        st.error(f"Gagal menghitung statistik IndiBiz: {error}")
        return _zero_service_stats()



@st.cache_data(show_spinner=False, max_entries=8)
def load_indibiz_topics(
    file_path: str | Path | None = None,
) -> pd.DataFrame:
    """Muat indibiz_output_top_topic.csv atau gunakan dummy topik IndiBiz."""
    try:
        resolved = _resolve_indibiz_output_path(file_path, INDIBIZ_OUTPUT_TOPIC_PATH)
        dataframe = _baca_csv_indibiz(resolved)
        _pastikan_kolom_indibiz(dataframe, INDIBIZ_TOPIC_COLUMNS, resolved.name)
        return dataframe[INDIBIZ_TOPIC_COLUMNS].reset_index(drop=True)
    except FileNotFoundError:
        st.warning(
            "File data/indibiz_output_top_topic.csv belum tersedia. "
            "Dashboard menggunakan data dummy topik IndiBiz sementara."
        )
        return get_dummy_indibiz_topics()
    except Exception as error:
        st.error(f"Gagal memuat data topik IndiBiz: {error}")
        return get_dummy_indibiz_topics()


@st.cache_data(show_spinner=False, max_entries=8)
def load_indibiz_top_kata(
    file_path: str | Path | None = None,
) -> pd.DataFrame:
    """Muat indibiz_output_top_kata.csv atau gunakan dummy top kata IndiBiz."""
    try:
        resolved = _resolve_indibiz_output_path(file_path, INDIBIZ_OUTPUT_TOP_KATA_PATH)
        dataframe = _baca_csv_indibiz(resolved)
        _pastikan_kolom_indibiz(dataframe, INDIBIZ_TOP_KATA_COLUMNS, resolved.name)
        result = dataframe[INDIBIZ_TOP_KATA_COLUMNS].copy()
        result["rank"] = pd.to_numeric(result["rank"], errors="raise").astype(int)
        result["frekuensi"] = pd.to_numeric(
            result["frekuensi"], errors="raise"
        ).astype(int)
        return result.reset_index(drop=True)
    except FileNotFoundError:
        st.warning(
            "File data/indibiz_output_top_kata.csv belum tersedia. "
            "Dashboard menggunakan data dummy top kata IndiBiz sementara."
        )
        return get_dummy_indibiz_top_kata()
    except Exception as error:
        st.error(f"Gagal memuat data top kata IndiBiz: {error}")
        return get_dummy_indibiz_top_kata()

    except Exception as error:
        st.error(f"Gagal memuat data top kata IndiBiz: {error}")
        return get_dummy_indibiz_top_kata()

