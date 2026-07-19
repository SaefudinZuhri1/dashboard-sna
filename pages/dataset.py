# pages/dataset.py
"""Halaman eksplorasi dataset penelitian media sosial Telkom Group."""

from __future__ import annotations

import csv
import hashlib
import inspect
import io
import logging
import math
import re
import warnings
from html import escape
from pathlib import Path
from typing import Any

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from utils.data_loader import load_indibiz_sentiment, load_indibiz_sna
from utils.indibiz_config import INDIBIZ_SENTIMENT_CANDIDATES, INDIBIZ_SNA_CANDIDATES
from utils.gemini_client import check_data_relevance
from utils.topic_classifier import classify_topic
from utils.loading_screen import (
    batalkan_layar_loading,
    mulai_layar_loading,
    mulai_loading_aksi,
    selesaikan_layar_loading,
    selesaikan_loading_aksi,
)

LOGGER = logging.getLogger(__name__)

LAYANAN_OPTIONS = ["IndiHome", "IndiBiz"]
PLATFORM_OPTIONS = ["Semua", "Twitter", "Instagram", "TikTok"]
SENTIMEN_OPTIONS = ["Semua", "Positif", "Netral", "Negatif"]
BARIS_PER_HALAMAN_OPTIONS = [10, 25, 50]
DEFAULT_BARIS_PER_HALAMAN = 10
DATASET_CACHE_VERSION = "fase16-loading-custom-pagination-v13"
FILTER_ENGINE_LABEL = "F16.13"

KOLOM_KANONIK = [
    "tanggal",
    "layanan",
    "platform",
    "username",
    "followers",
    "komentar",
    "sentimen",
    "confidence",
]

ALIAS_KOLOM = {
    "tanggal": ["tanggal", "date_created", "date", "created_at", "timestamp", "creation_time"],
    "layanan": ["layanan", "service", "object_group", "produk"],
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
        "account",
    ],
    "followers": [
        "followers",
        "followers_count",
        "follower_count",
        "author_followers",
    ],
    "komentar": [
        "komentar",
        "content",
        "text",
        "full_text",
        "comment",
        "tweet_text",
        "caption",
    ],
    "sentimen": [
        "sentimen",
        "final_sentiment",
        "predicted_sentiment",
        "sentiment",
        "label",
    ],
    "confidence": [
        "confidence",
        "confidence_score",
        "sentiment_confidence_level",
        "score",
        "probability",
    ],
}

PETA_PLATFORM = {
    "twitter": "Twitter",
    "twitter/x": "Twitter",
    "x": "Twitter",
    "instagram": "Instagram",
    "ig": "Instagram",
    "tiktok": "TikTok",
    "tik tok": "TikTok",
}

PETA_SENTIMEN = {
    "label_0": "Positif",
    "positive": "Positif",
    "positif": "Positif",
    "label_1": "Netral",
    "neutral": "Netral",
    "netral": "Netral",
    "label_2": "Negatif",
    "negative": "Negatif",
    "negatif": "Negatif",
}

WARNA_SENTIMEN = {
    "Positif": "#4CAF50",
    "Netral": "#FF9800",
    "Negatif": "#F44336",
}

WARNA_PLATFORM = {
    "Twitter": "#E53935",
    "Instagram": "#C13584",
    "TikTok": "#8E8E93",
}

STATE_LAYANAN = "dataset_v6_layanan"
STATE_PLATFORM = "dataset_v6_platform"
STATE_PLATFORM_INDIBIZ = "dataset_v6_platform_indibiz"
STATE_SENTIMEN = "dataset_v6_sentimen"
STATE_PENCARIAN = "dataset_v6_pencarian"
STATE_HALAMAN = "dataset_v6_halaman"
STATE_BARIS_PER_HALAMAN = "dataset_v6_baris_per_halaman"
STATE_SIGNATURE = "dataset_v6_filter_signature"
STATE_LOADING_SELESAI = "dataset_v6_loading_selesai"
STATE_FILTER_LOADING_LABEL = "dataset_v10_filter_loading_label"
STATE_UPLOADED_DF = "uploaded_df"
STATE_UPLOAD_WIDGET = "dataset_v16_upload_file"
STATE_UPLOAD_CURRENT_SIGNATURE = "dataset_v16_upload_current_signature"
STATE_UPLOAD_ANALYZED_SIGNATURE = "dataset_v16_upload_analyzed_signature"
STATE_UPLOAD_ANALYSIS_REQUEST = "dataset_v16_upload_analysis_request"
STATE_UPLOAD_LOADING_LABEL = "dataset_v16_upload_loading_label"
STATE_UPLOAD_RAW_BYTES = "dataset_v16_upload_raw_bytes"
STATE_UPLOAD_FILE_NAME = "dataset_v16_upload_file_name"
STATE_UPLOAD_FILE_SIZE = "dataset_v16_upload_file_size"
STATE_UPLOAD_FILE_EXTENSION = "dataset_v16_upload_file_extension"
STATE_UPLOAD_RELEVANCE_SIGNATURE = "dataset_v17_upload_relevance_signature"
STATE_UPLOAD_RELEVANCE_SOURCE = "dataset_v17_upload_relevance_source"
STATE_IS_RELEVANT = "is_relevant"
STATE_DETECTED_TEXT_COL = "detected_text_col"
STATE_DETECTED_PLATFORM = "detected_platform"
STATE_UPLOAD_PLATFORM_COL = "dataset_v18_upload_platform_col"
STATE_UPLOAD_OUTPUT_DF = "dataset_v18_upload_output_df"
STATE_UPLOAD_OUTPUT_SIGNATURE = "dataset_v18_upload_output_signature"
STATE_UPLOAD_OUTPUT_ERROR = "dataset_v18_upload_output_error"

KEYWORD_RELEVANSI_TELKOM = ("indihome", "indibiz", "telkomsel", "telkom")

# Streamlit 1.35 masih menggunakan nama experimental_dialog, sedangkan
# versi yang lebih baru menggunakan dialog. Pemilihan ini menjaga patch
# tetap kompatibel tanpa mengubah requirements proyek.
_DIALOG_DECORATOR = getattr(st, "dialog", None)
if _DIALOG_DECORATOR is None:
    _DIALOG_DECORATOR = st.experimental_dialog


def _root_proyek() -> Path:
    """Kembalikan folder utama proyek Streamlit."""
    return Path(__file__).resolve().parent.parent


def _opsi_lebar_penuh(fungsi: Any) -> dict[str, Any]:
    """Pilih parameter lebar yang kompatibel dengan versi Streamlit aktif."""
    try:
        parameter = inspect.signature(fungsi).parameters
        if "width" in parameter:
            return {"width": "stretch"}
        if "use_container_width" in parameter:
            return {"use_container_width": True}
    except (TypeError, ValueError):
        pass
    return {}


def _bersihkan_teks(nilai: Any) -> str:
    """Bersihkan spasi dan tanda kutip pembuka atau penutup dari nilai teks."""
    if nilai is None or pd.isna(nilai):
        return ""
    teks = str(nilai).strip()
    teks = re.sub(r"^[\ufeff\s'\"]+", "", teks)
    teks = re.sub(r"[\s'\"]+$", "", teks)
    return teks.strip()


def _normalisasi_label_sentimen(nilai: Any) -> str:
    """Ubah variasi label model atau dataset menjadi label UI Bahasa Indonesia."""
    teks = _bersihkan_teks(nilai).lower()
    if not teks:
        return ""

    # Bentuk ringkas menangani spasi, tanda hubung, titik, dan tanda kurung.
    bentuk_ringkas = re.sub(r"[^a-z0-9]+", "", teks)
    peta_ringkas = {
        "label0": "Positif",
        "positive": "Positif",
        "positif": "Positif",
        "pos": "Positif",
        "label1": "Netral",
        "neutral": "Netral",
        "netral": "Netral",
        "neu": "Netral",
        "label2": "Negatif",
        "negative": "Negatif",
        "negatif": "Negatif",
        "neg": "Negatif",
    }
    if bentuk_ringkas in peta_ringkas:
        return peta_ringkas[bentuk_ringkas]

    # Beberapa file menyimpan gabungan seperti "LABEL_1 (neutral)".
    if "label0" in bentuk_ringkas or "positive" in bentuk_ringkas or "positif" in bentuk_ringkas:
        return "Positif"
    if "label1" in bentuk_ringkas or "neutral" in bentuk_ringkas or "netral" in bentuk_ringkas:
        return "Netral"
    if "label2" in bentuk_ringkas or "negative" in bentuk_ringkas or "negatif" in bentuk_ringkas:
        return "Negatif"
    return ""


def _kanonisasi_kolom_sentimen(data: pd.DataFrame) -> pd.DataFrame:
    """Pastikan kolom sentimen tetap kanonik, termasuk pada hasil cache lama."""
    if data is None:
        return pd.DataFrame(columns=KOLOM_KANONIK)

    hasil = data.copy()
    if "sentimen" not in hasil.columns:
        return hasil

    hasil["sentimen"] = hasil["sentimen"].map(_normalisasi_label_sentimen)
    return hasil


def _parse_tanggal(series: pd.Series) -> pd.Series:
    """Ubah berbagai format tanggal menjadi tipe datetime secara defensif."""
    teks = series.where(series.notna(), "").astype(str).map(_bersihkan_teks)
    hasil = pd.to_datetime(
        teks,
        format="%d/%m/%Y %H.%M.%S",
        errors="coerce",
    )

    belum_terbaca = hasil.isna() & teks.ne("")
    if belum_terbaca.any():
        hasil.loc[belum_terbaca] = pd.to_datetime(
            teks.loc[belum_terbaca],
            format="%d/%m/%Y %H:%M:%S",
            errors="coerce",
        )

    belum_terbaca = hasil.isna() & teks.ne("")
    if belum_terbaca.any():
        hasil.loc[belum_terbaca] = pd.to_datetime(
            teks.loc[belum_terbaca],
            format="mixed",
            errors="coerce",
            dayfirst=True,
        )
    return hasil


def _parse_followers(series: pd.Series) -> pd.Series:
    """Ubah jumlah followers menjadi bilangan bulat nonnegatif."""
    def konversi(nilai: Any) -> int:
        """Konversi satu nilai followers menjadi integer aman."""
        teks = _bersihkan_teks(nilai).replace(" ", "")
        if not teks or teks.lower() in {"nan", "none", "null", "-"}:
            return 0
        if re.fullmatch(r"\d{1,3}([.,]\d{3})+", teks):
            teks = teks.replace(".", "").replace(",", "")
        else:
            teks = teks.replace(",", "")
        try:
            return max(0, int(round(float(teks))))
        except (TypeError, ValueError):
            return 0

    return (
        series.map(konversi)
        .clip(lower=0, upper=2_147_483_647)
        .astype("int32")
    )


def _parse_confidence(series: pd.Series) -> pd.Series:
    """Normalisasi confidence dari skala 0–1 atau 0–100 menjadi skala 0–1."""
    teks = series.astype(str).map(_bersihkan_teks).str.replace("%", "", regex=False)
    hasil = pd.to_numeric(teks, errors="coerce")
    hasil = hasil.mask((hasil > 1) & (hasil <= 100), hasil / 100)
    hasil = hasil.mask((hasil < 0) | (hasil > 1))
    return hasil.astype("float32")


def _pilih_kolom_sumber(kolom: list[str]) -> list[str]:
    """Pilih hanya kolom CSV yang diperlukan oleh halaman Dataset."""
    indeks = {str(item).strip().lower(): item for item in kolom}
    terpilih: list[str] = []
    for daftar_alias in ALIAS_KOLOM.values():
        for alias in daftar_alias:
            sumber = indeks.get(alias.lower())
            if sumber is not None:
                terpilih.append(sumber)
                break
    return list(dict.fromkeys(terpilih))


def _normalisasi_dataset(data: pd.DataFrame, layanan_default: str) -> pd.DataFrame:
    """Normalisasi dataset mentah ke delapan kolom kanonik halaman Dataset."""
    if data is None or data.empty:
        return pd.DataFrame(columns=KOLOM_KANONIK)

    hasil = data.copy()
    indeks = {str(item).strip().lower(): item for item in hasil.columns}
    peta_rename: dict[str, str] = {}

    for kolom_tujuan, daftar_alias in ALIAS_KOLOM.items():
        for alias in daftar_alias:
            kolom_sumber = indeks.get(alias.lower())
            if kolom_sumber is not None:
                peta_rename[kolom_sumber] = kolom_tujuan
                break

    hasil = hasil.rename(columns=peta_rename)

    for kolom in KOLOM_KANONIK:
        if kolom not in hasil.columns:
            if kolom == "followers":
                hasil[kolom] = 0
            elif kolom == "confidence":
                hasil[kolom] = pd.NA
            elif kolom == "layanan":
                hasil[kolom] = layanan_default
            else:
                hasil[kolom] = ""

    hasil["tanggal"] = _parse_tanggal(hasil["tanggal"])
    hasil["layanan"] = hasil["layanan"].map(_bersihkan_teks)
    hasil.loc[hasil["layanan"].eq(""), "layanan"] = layanan_default
    hasil["layanan"] = layanan_default

    hasil["platform"] = (
        hasil["platform"]
        .map(_bersihkan_teks)
        .str.lower()
        .map(PETA_PLATFORM)
    )
    hasil["username"] = hasil["username"].map(_bersihkan_teks)
    hasil["followers"] = _parse_followers(hasil["followers"])
    hasil["komentar"] = hasil["komentar"].map(_bersihkan_teks)
    hasil["sentimen"] = hasil["sentimen"].map(_normalisasi_label_sentimen)
    hasil["confidence"] = _parse_confidence(hasil["confidence"])

    hasil = hasil[
        hasil["platform"].isin(["Twitter", "Instagram", "TikTok"])
        & hasil["sentimen"].isin(["Positif", "Netral", "Negatif"])
    ].copy()

    hasil["username"] = hasil["username"].replace("", "Tidak diketahui")
    hasil["komentar"] = hasil["komentar"].replace("", "Tidak ada isi komentar")
    hasil = hasil[KOLOM_KANONIK]
    hasil = hasil.sort_values("tanggal", ascending=False, na_position="last")
    return hasil.reset_index(drop=True)


def _kandidat_file(layanan: str) -> list[Path]:
    """Susun daftar kandidat file CSV atau CSV.GZ untuk satu layanan."""
    slug = layanan.lower().replace(" ", "")
    folder_data = _root_proyek() / "data"
    kandidat = [
        folder_data / f"{slug}_sentiment.csv.gz",
        folder_data / f"{slug}_sentiment.csv",
    ]

    if folder_data.exists():
        kandidat.extend(
            item
            for item in sorted(folder_data.glob(f"*{slug}*.csv*"))
            if "sna" not in item.name.lower()
        )

    unik: list[Path] = []
    sudah_ada: set[str] = set()
    for item in kandidat:
        kunci = str(item.resolve()) if item.exists() else str(item)
        if kunci not in sudah_ada:
            sudah_ada.add(kunci)
            unik.append(item)
    return unik


def _baca_header(path: str) -> pd.DataFrame:
    """Baca header CSV dengan beberapa encoding sebagai fallback."""
    error_terakhir: Exception | None = None
    for encoding in ("utf-8-sig", "utf-8", "latin-1"):
        try:
            return pd.read_csv(path, nrows=0, compression="infer", encoding=encoding)
        except Exception as exc:  # Pembacaan fallback memang perlu menangkap seluruh parser error.
            error_terakhir = exc
    raise ValueError("Header file dataset tidak dapat dibaca.") from error_terakhir


@st.cache_data(show_spinner=False, persist="disk", max_entries=12)
def _baca_dataset_aktual(
    path: str,
    layanan: str,
    ukuran_file: int,
    waktu_modifikasi_ns: int,
) -> pd.DataFrame:
    """Baca dan normalisasi dataset aktual dengan cache berbasis identitas file."""
    del ukuran_file, waktu_modifikasi_ns

    header = _baca_header(path)
    usecols = _pilih_kolom_sumber(list(header.columns))
    if not usecols:
        raise ValueError("Tidak ada kolom yang dikenali pada file dataset.")

    percobaan = [
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

    error_terakhir: Exception | None = None
    for opsi in percobaan:
        try:
            mentah = pd.read_csv(
                path,
                compression="infer",
                usecols=usecols,
                dtype="string",
                keep_default_na=False,
                na_filter=False,
                **opsi,
            )
            hasil = _normalisasi_dataset(mentah, layanan)
            if hasil.empty:
                raise ValueError("File terbaca, tetapi tidak menghasilkan baris valid.")
            return hasil
        except Exception as exc:  # Parser alternatif membutuhkan cakupan error luas.
            error_terakhir = exc

    raise ValueError("Isi file dataset tidak dapat dibaca.") from error_terakhir


@st.cache_data(show_spinner=False, max_entries=6)
def _buat_dummy_dataset(layanan: str, jumlah_baris: int = 120) -> pd.DataFrame:
    """Buat dummy data realistis dan deterministik minimal 100 baris."""
    komentar_positif = [
        "Layanan internet hari ini stabil dan teknisinya sangat membantu.",
        "Terima kasih admin, keluhan saya ditangani dengan cepat.",
        "Koneksi lancar untuk rapat daring dan menonton video.",
        "Paketnya sesuai kebutuhan dan proses aktivasi mudah.",
        "Pelayanan pelanggan ramah serta memberikan solusi yang jelas.",
    ]
    komentar_netral = [
        "Apakah ada informasi paket internet untuk bulan ini?",
        "Mohon cek status jaringan di wilayah Bandung.",
        "Berapa harga paket dengan kecepatan 50 Mbps?",
        "Saya ingin mengetahui cara melihat tagihan terbaru.",
        "Admin, apakah layanan tersedia di alamat saya?",
    ]
    komentar_negatif = [
        "Internet sering putus dan sangat lambat sejak tadi malam.",
        "Sinyal hilang beberapa kali, mohon segera diperbaiki.",
        "Harga paket naik tetapi kualitas jaringan menurun.",
        "Keluhan belum mendapat respons dan koneksi masih bermasalah.",
        "Jaringan tidak stabil sehingga pekerjaan saya terganggu.",
    ]

    daftar_komentar = {
        "Positif": komentar_positif,
        "Netral": komentar_netral,
        "Negatif": komentar_negatif,
    }
    urutan_sentimen = ["Negatif", "Netral", "Positif", "Negatif", "Positif", "Netral"]
    daftar_platform = ["Twitter", "Instagram", "TikTok"]
    baris: list[dict[str, Any]] = []
    tanggal_awal = pd.Timestamp("2025-11-01 08:00:00")

    for indeks in range(max(100, jumlah_baris)):
        sentimen = urutan_sentimen[indeks % len(urutan_sentimen)]
        platform = daftar_platform[indeks % len(daftar_platform)]
        komentar = daftar_komentar[sentimen][indeks % len(daftar_komentar[sentimen])]
        baris.append(
            {
                "tanggal": tanggal_awal + pd.Timedelta(hours=indeks * 11),
                "layanan": layanan,
                "platform": platform,
                "username": f"pengguna_{layanan.lower()}_{indeks + 1:03d}",
                "followers": 75 + ((indeks * 137) % 25000),
                "komentar": komentar,
                "sentimen": sentimen,
                "confidence": round(0.68 + ((indeks * 17) % 29) / 100, 2),
            }
        )

    hasil = pd.DataFrame(baris, columns=KOLOM_KANONIK)
    return hasil.sort_values("tanggal", ascending=False).reset_index(drop=True)



def _pilih_path_indibiz(daftar_nama: tuple[str, ...]) -> Path:
    """Pilih file IndiBiz aktual pertama yang tersedia atau path kandidat utama."""
    folder_data = _root_proyek() / "data"
    for nama_file in daftar_nama:
        kandidat = folder_data / nama_file
        if kandidat.is_file():
            return kandidat
    return folder_data / daftar_nama[0]


@st.cache_data(show_spinner=False, max_entries=12)
def _validasi_file_csv_sederhana(
    path_teks: str,
    ukuran_file: int,
    waktu_modifikasi_ns: int,
) -> bool:
    """Pastikan file CSV memiliki header dan dapat dibaca minimal satu baris."""
    del ukuran_file, waktu_modifikasi_ns
    try:
        path = Path(path_teks)
        if not path.is_file() or path.stat().st_size <= 0:
            return False
        sampel = pd.read_csv(path, nrows=1)
        return len(sampel.columns) > 0
    except Exception:
        return False


def _status_file_csv(path: Path) -> bool:
    """Validasi file CSV memakai cache yang otomatis berubah saat file diperbarui."""
    try:
        if not path.is_file():
            return False
        statistik = path.stat()
        return _validasi_file_csv_sederhana(
            str(path),
            statistik.st_size,
            statistik.st_mtime_ns,
        )
    except Exception:
        return False


def _batasi_dummy_indibiz_20(data: pd.DataFrame) -> pd.DataFrame:
    """Susun 20 dummy IndiBiz dengan komposisi 8 negatif, 7 positif, 5 netral."""
    if data is None or data.empty:
        return data

    hasil = data.copy()
    kolom_sentimen = next(
        (
            kolom
            for kolom in ("predicted_sentiment", "sentiment", "sentimen", "label")
            if kolom in hasil.columns
        ),
        None,
    )
    if kolom_sentimen is None:
        return hasil.head(20).copy()

    label_normal = (
        hasil[kolom_sentimen]
        .astype(str)
        .str.strip()
        .str.lower()
        .replace(
            {
                "label_0": "positive",
                "positif": "positive",
                "label_1": "neutral",
                "netral": "neutral",
                "label_2": "negative",
                "negatif": "negative",
            }
        )
    )
    hasil = hasil.assign(_sentimen_normal=label_normal)

    bagian: list[pd.DataFrame] = []
    for label, jumlah in (("negative", 8), ("positive", 7), ("neutral", 5)):
        subset = hasil[hasil["_sentimen_normal"].eq(label)].head(jumlah).copy()
        bagian.append(subset)

    gabungan = pd.concat(bagian, ignore_index=True) if bagian else hasil.head(20).copy()
    gabungan = gabungan.drop(columns=["_sentimen_normal"], errors="ignore")

    if not any(kolom in gabungan.columns for kolom in ("date_created", "date", "tanggal")):
        gabungan["date_created"] = pd.date_range(
            start="2025-11-03 08:00:00",
            periods=len(gabungan),
            freq="37h",
        )
    return gabungan.reset_index(drop=True)


def _muat_indibiz_sentiment_khusus() -> tuple[pd.DataFrame, bool, str, str | None]:
    """Muat sentimen IndiBiz memakai loader fase sebelumnya dan fallback resminya."""
    path = _pilih_path_indibiz(INDIBIZ_SENTIMENT_CANDIDATES)
    data_aktual = _status_file_csv(path)
    try:
        mentah = load_indibiz_sentiment(path)
        if not data_aktual:
            mentah = _batasi_dummy_indibiz_20(mentah)
        hasil = _normalisasi_dataset(mentah, "IndiBiz")
        if hasil.empty:
            raise ValueError("Data sentimen IndiBiz tidak menghasilkan baris valid.")
        sumber = path.name if data_aktual else "Dummy IndiBiz dari utils/dummy_data.py"
        return hasil, data_aktual, sumber, None
    except Exception as exc:
        LOGGER.exception("Gagal menyiapkan dataset sentimen IndiBiz")
        try:
            fallback = _batasi_dummy_indibiz_20(load_indibiz_sentiment(path))
            hasil = _normalisasi_dataset(fallback, "IndiBiz")
            return hasil, False, "Dummy IndiBiz dari utils/dummy_data.py", str(exc)
        except Exception as fallback_exc:
            return (
                pd.DataFrame(columns=KOLOM_KANONIK),
                False,
                "Data IndiBiz tidak tersedia",
                str(fallback_exc),
            )


def _muat_indibiz_sna_preview() -> tuple[pd.DataFrame, bool, str, str | None]:
    """Muat preview edge SNA IndiBiz dengan skema Source, Target, Relationship, Platform."""
    path = _pilih_path_indibiz(INDIBIZ_SNA_CANDIDATES)
    data_aktual = _status_file_csv(path)
    try:
        mentah = load_indibiz_sna(path)
        if mentah is None or mentah.empty:
            raise ValueError("Data SNA IndiBiz kosong.")

        hasil = mentah.copy()
        indeks = {str(kolom).strip().lower(): kolom for kolom in hasil.columns}
        peta = {}
        for tujuan, alias in {
            "source": ("source", "node_source", "from", "username"),
            "target": ("target", "node_target", "to"),
            "relationship": ("relationship", "relation", "relasi", "interaction_type"),
            "platform": ("platform", "source_platform"),
        }.items():
            for nama in alias:
                sumber = indeks.get(nama)
                if sumber is not None:
                    peta[sumber] = tujuan
                    break
        hasil = hasil.rename(columns=peta)

        for kolom in ("source", "target", "relationship", "platform"):
            if kolom not in hasil.columns:
                hasil[kolom] = ""
            hasil[kolom] = hasil[kolom].map(_bersihkan_teks)

        hasil["platform"] = (
            hasil["platform"].str.lower().map(PETA_PLATFORM).fillna(hasil["platform"])
        )
        hasil["relationship"] = hasil["relationship"].str.title().replace("", "Tidak diketahui")
        hasil["source"] = hasil["source"].replace("", "Tidak diketahui")
        hasil["target"] = hasil["target"].replace("", "indibiz")
        hasil = hasil[["source", "target", "relationship", "platform"]].reset_index(drop=True)

        sumber = path.name if data_aktual else "Dummy SNA IndiBiz dari utils/dummy_data.py"
        return hasil, data_aktual, sumber, None
    except Exception as exc:
        LOGGER.exception("Gagal menyiapkan preview SNA IndiBiz")
        return (
            pd.DataFrame(columns=["source", "target", "relationship", "platform"]),
            False,
            "Data SNA IndiBiz tidak tersedia",
            str(exc),
        )


def _render_badge_layanan_aktif(metadata: list[dict[str, Any]], layanan: str) -> None:
    """Tampilkan badge sumber data untuk layanan yang sedang dipilih."""
    item = next((baris for baris in metadata if baris.get("layanan") == layanan), None)
    if item is None:
        return
    kelas = "dataset-v6-source-real" if item.get("aktual") else "dataset-v6-source-dummy"
    label = "📁 Data Nyata" if item.get("aktual") else "🎭 Data Dummy"
    st.markdown(
        f'<div class="dataset-v6-active-source">'
        f'<span class="dataset-v6-source-badge {kelas}">{escape(layanan)} · {label}</span>'
        f'<span class="dataset-v6-active-source-name">Sumber: {escape(str(item.get("sumber", "-")))}'
        f'</span>'
        f'</div>',
        unsafe_allow_html=True,
    )


def _render_preview_sna_indibiz() -> None:
    """Tampilkan statistik node-edge dan preview tabel SNA khusus IndiBiz."""
    st.markdown(
        '<div class="dataset-v6-section-title">Preview Jaringan SNA IndiBiz</div>',
        unsafe_allow_html=True,
    )
    data_sna, aktual, sumber, error = _muat_indibiz_sna_preview()

    kelas = "dataset-v6-source-real" if aktual else "dataset-v6-source-dummy"
    label = "📁 Data Nyata" if aktual else "🎭 Data Dummy"
    st.markdown(
        f'<div class="dataset-v6-active-source">'
        f'<span class="dataset-v6-source-badge {kelas}">SNA IndiBiz · {label}</span>'
        f'<span class="dataset-v6-active-source-name">Sumber: {escape(sumber)}</span>'
        f'</div>',
        unsafe_allow_html=True,
    )

    if error:
        st.warning(
            "File SNA IndiBiz belum dapat digunakan. Dashboard menampilkan data dummy agar preview tetap tersedia."
        )
    if data_sna.empty:
        st.info("Preview SNA IndiBiz belum tersedia.")
        return

    kumpulan_node = pd.concat(
        [data_sna["source"].astype(str), data_sna["target"].astype(str)],
        ignore_index=True,
    )
    total_node = int(kumpulan_node[kumpulan_node.str.strip().ne("")].nunique())
    total_edge = int(len(data_sna))

    kol_node, kol_edge, kol_keterangan = st.columns(3, gap="medium")
    with kol_node:
        _render_metric_card("Total Node", _format_angka(total_node), "Akun unik pada jaringan IndiBiz")
    with kol_edge:
        _render_metric_card("Total Edge", _format_angka(total_edge), "Relasi interaksi pada edge list")
    with kol_keterangan:
        st.markdown(
            '<div class="dataset-v6-sna-note">'
            '<div class="dataset-v6-sna-note-title">Interpretasi singkat</div>'
            '<div class="dataset-v6-sna-note-body">'
            'Source menunjukkan akun asal interaksi. Target menunjukkan akun tujuan. '
            'Relationship menjelaskan tipe hubungan, sedangkan Platform menunjukkan sumber media sosial.'
            '</div>'
            '</div>',
            unsafe_allow_html=True,
        )

    # Beri jarak yang jelas antara baris card SNA dan tabel preview di bawahnya.
    st.markdown(
        '<div class="dataset-v6-sna-table-gap" aria-hidden="true"></div>',
        unsafe_allow_html=True,
    )

    tampilan = data_sna.rename(
        columns={
            "source": "Source",
            "target": "Target",
            "relationship": "Relationship",
            "platform": "Platform",
        }
    )
    st.dataframe(
        tampilan.head(50),
        hide_index=True,
        **_opsi_lebar_penuh(st.dataframe),
    )

def _muat_layanan(layanan: str) -> tuple[pd.DataFrame, bool, str, str | None]:
    """Muat dataset satu layanan dan gunakan dummy data ketika file gagal atau tidak ada."""
    if layanan == "IndiBiz":
        return _muat_indibiz_sentiment_khusus()
    elif layanan == "IndiHome":
        pass

    error_terakhir: str | None = None

    for kandidat in _kandidat_file(layanan):
        if not kandidat.is_file():
            continue
        try:
            statistik = kandidat.stat()
            data = _baca_dataset_aktual(
                str(kandidat),
                layanan,
                statistik.st_size,
                statistik.st_mtime_ns,
            )
            return data.copy(), True, kandidat.name, None
        except Exception as exc:
            LOGGER.exception("Gagal membaca dataset aktual %s dari %s", layanan, kandidat)
            error_terakhir = str(exc)

    try:
        data_dummy = _buat_dummy_dataset(layanan, 120)
        return data_dummy.copy(), False, "Data dummy bawaan", error_terakhir
    except Exception as exc:
        LOGGER.exception("Gagal membuat dummy data untuk %s", layanan)
        return (
            pd.DataFrame(columns=KOLOM_KANONIK),
            False,
            "Data tidak tersedia",
            str(exc),
        )


def _tanda_tangan_semua_dataset() -> str:
    """Buat signature file agar cache gabungan otomatis invalid saat data berubah."""
    try:
        bagian: list[str] = [DATASET_CACHE_VERSION]
        for layanan in ["IndiHome", "IndiBiz"]:
            ditemukan = False
            for kandidat in _kandidat_file(layanan):
                if not kandidat.is_file():
                    continue
                statistik = kandidat.stat()
                bagian.append(
                    f"{layanan}:{kandidat.name}:{statistik.st_size}:{statistik.st_mtime_ns}"
                )
                ditemukan = True
                break
            if not ditemukan:
                bagian.append(f"{layanan}:dummy")
        return "|".join(bagian)
    except Exception:
        return "dataset:unknown"


@st.cache_data(show_spinner=False, persist="disk", max_entries=6)
def _muat_semua_dataset_cached(
    file_signature: str,
) -> tuple[pd.DataFrame, list[dict[str, Any]]]:
    """Gabungkan seluruh layanan satu kali untuk setiap versi file sumber."""
    del file_signature
    kumpulan: list[pd.DataFrame] = []
    metadata: list[dict[str, Any]] = []

    for layanan in ["IndiHome", "IndiBiz"]:
        data, aktual, sumber, error = _muat_layanan(layanan)
        if not data.empty:
            kumpulan.append(data)
        metadata.append(
            {
                "layanan": layanan,
                "aktual": aktual,
                "sumber": sumber,
                "jumlah": len(data),
                "error": error,
            }
        )

    if not kumpulan:
        return pd.DataFrame(columns=KOLOM_KANONIK), metadata

    gabungan = pd.concat(kumpulan, ignore_index=True)
    gabungan = _kanonisasi_kolom_sentimen(gabungan)
    gabungan = gabungan[
        gabungan["sentimen"].isin(["Positif", "Netral", "Negatif"])
    ].copy()
    gabungan = gabungan.sort_values("tanggal", ascending=False, na_position="last")
    return gabungan.reset_index(drop=True), metadata


def _muat_semua_dataset() -> tuple[pd.DataFrame, list[dict[str, Any]]]:
    """Muat gabungan dataset melalui cache berbasis signature file."""
    try:
        return _muat_semua_dataset_cached(_tanda_tangan_semua_dataset())
    except Exception as exc:
        LOGGER.exception("Gagal memuat gabungan dataset dari cache")
        st.error(f"Gabungan dataset belum dapat dimuat: {exc}")
        return pd.DataFrame(columns=KOLOM_KANONIK), []


def _inisialisasi_state() -> None:
    """Inisialisasi seluruh session state halaman Dataset."""
    nilai_awal = {
        STATE_LAYANAN: "IndiHome",
        STATE_PLATFORM: "Semua",
        STATE_PLATFORM_INDIBIZ: [],
        STATE_SENTIMEN: "Semua",
        STATE_PENCARIAN: "",
        STATE_HALAMAN: 1,
        STATE_BARIS_PER_HALAMAN: DEFAULT_BARIS_PER_HALAMAN,
        STATE_SIGNATURE: None,
    }
    for kunci, nilai in nilai_awal.items():
        if kunci not in st.session_state:
            st.session_state[kunci] = nilai


def _reset_filter() -> None:
    """Kembalikan seluruh filter dan pagination ke kondisi awal."""
    st.session_state[STATE_LAYANAN] = "IndiHome"
    st.session_state[STATE_PLATFORM] = "Semua"
    st.session_state[STATE_PLATFORM_INDIBIZ] = []
    st.session_state[STATE_SENTIMEN] = "Semua"
    st.session_state[STATE_PENCARIAN] = ""
    st.session_state[STATE_HALAMAN] = 1
    st.session_state[STATE_SIGNATURE] = None


def _ubah_halaman(perubahan: int, total_halaman: int) -> None:
    """Pindahkan halaman tabel dan aktifkan loading custom pada rerun berikutnya."""
    halaman = int(st.session_state.get(STATE_HALAMAN, 1)) + perubahan
    st.session_state[STATE_HALAMAN] = min(max(1, halaman), max(1, total_halaman))

    if perubahan < 0:
        label_loading = "Memuat halaman sebelumnya..."
    else:
        label_loading = "Memuat halaman berikutnya..."
    st.session_state[STATE_FILTER_LOADING_LABEL] = label_loading


def _terapkan_filter(
    data: pd.DataFrame,
    layanan: str,
    platform: str | list[str],
    sentimen: str,
    pencarian: str,
) -> pd.DataFrame:
    """Terapkan semua filter menggunakan pandas boolean indexing."""
    hasil = _kanonisasi_kolom_sentimen(data)

    if layanan != "Semua":
        hasil = hasil[hasil["layanan"].eq(layanan)].copy()

    if isinstance(platform, list):
        # Pada multiselect IndiBiz, daftar kosong berarti semua platform.
        # Perilaku ini mencegah hasil menjadi 0 ketika widget tampil tanpa chip
        # pilihan setelah pengguna mengganti filter sentimen.
        platform_terpilih = [
            item for item in platform
            if item in {"Twitter", "Instagram", "TikTok"}
        ]
        if platform_terpilih:
            hasil = hasil[hasil["platform"].isin(platform_terpilih)].copy()
    elif platform != "Semua":
        hasil = hasil[hasil["platform"].eq(platform)].copy()

    if sentimen != "Semua":
        sentimen_kanonik = _normalisasi_label_sentimen(sentimen)
        hasil = hasil[hasil["sentimen"].eq(sentimen_kanonik)].copy()

    kata_kunci = pencarian.strip()
    if kata_kunci:
        mask = hasil["komentar"].str.contains(
            kata_kunci,
            case=False,
            na=False,
            regex=False,
        )
        hasil = hasil[mask].copy()

    return hasil.sort_values("tanggal", ascending=False, na_position="last").reset_index(drop=True)


def _format_angka(nilai: Any) -> str:
    """Format angka bulat dengan pemisah ribuan Indonesia."""
    try:
        return f"{int(nilai):,}".replace(",", ".")
    except (TypeError, ValueError):
        return "0"


def _format_persen(nilai: float) -> str:
    """Format persentase menggunakan satu angka desimal dan koma Indonesia."""
    return f"{nilai:.1f}%".replace(".", ",")


def _potong_komentar(teks: Any, batas: int = 80) -> str:
    """Potong komentar lebih dari 80 karakter dan tambahkan tiga titik."""
    nilai = _bersihkan_teks(teks)
    if len(nilai) <= batas:
        return nilai
    return f"{nilai[:batas].rstrip()}..."


def _buat_badge_sumber(metadata: list[dict[str, Any]]) -> str:
    """Buat HTML badge sumber data aktual atau dummy untuk setiap layanan."""
    badge: list[str] = []
    for item in metadata:
        kelas = "dataset-v6-source-real" if item["aktual"] else "dataset-v6-source-dummy"
        label_status = "📁 Data Nyata" if item["aktual"] else "🎭 Data Dummy"
        badge.append(
            f'<span class="dataset-v6-source-badge {kelas}">'
            f'{escape(item["layanan"])} · {label_status}</span>'
        )
    return "".join(badge)


def _render_metric_card(label: str, nilai: str, keterangan: str) -> None:
    """Tampilkan satu kartu metrik bergaya Minimalist with Deep."""
    st.markdown(
        f"""
        <div class="dataset-v6-metric-card">
            <div class="dataset-v6-metric-label">{escape(label)}</div>
            <div class="dataset-v6-metric-value">{escape(nilai)}</div>
            <div class="dataset-v6-metric-note">{escape(keterangan)}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def _buat_html_tabel(data: pd.DataFrame, nomor_awal: int) -> str:
    """Bangun tabel HTML aman dengan badge sentimen berwarna."""
    header = """
        <colgroup>
            <col class="dataset-v6-col-no">
            <col class="dataset-v6-col-tanggal">
            <col class="dataset-v6-col-platform">
            <col class="dataset-v6-col-username">
            <col class="dataset-v6-col-followers">
            <col class="dataset-v6-col-komentar">
            <col class="dataset-v6-col-sentimen">
            <col class="dataset-v6-col-confidence">
        </colgroup>
        <thead>
            <tr>
                <th>No</th>
                <th>Tanggal</th>
                <th>Platform</th>
                <th>Username</th>
                <th>Followers</th>
                <th>Isi Komentar</th>
                <th>Sentimen</th>
                <th>Confidence Score</th>
            </tr>
        </thead>
    """

    isi: list[str] = []
    for posisi, (_, baris) in enumerate(data.iterrows(), start=nomor_awal):
        tanggal = pd.to_datetime(baris["tanggal"], errors="coerce")
        tanggal_teks = tanggal.strftime("%d-%m-%Y %H:%M") if pd.notna(tanggal) else "-"
        sentimen = str(baris["sentimen"])
        kelas_badge = {
            "Positif": "dataset-v6-badge-positive",
            "Netral": "dataset-v6-badge-neutral",
            "Negatif": "dataset-v6-badge-negative",
        }.get(sentimen, "dataset-v6-badge-neutral")
        confidence = baris["confidence"]
        confidence_teks = f"{float(confidence) * 100:.1f}%" if pd.notna(confidence) else "N/A"

        kelas_baris = {
            "Positif": "dataset-v6-row-positive",
            "Netral": "dataset-v6-row-neutral",
            "Negatif": "dataset-v6-row-negative",
        }.get(sentimen, "")

        isi.append(
            f"<tr class='{kelas_baris}'>"
            f"<td>{posisi}</td>"
            f"<td>{escape(tanggal_teks)}</td>"
            f"<td>{escape(str(baris['platform']))}</td>"
            f"<td class='dataset-v6-username-cell' title='{escape(str(baris['username']), quote=True)}'>"
            f"{escape(str(baris['username']))}</td>"
            f"<td class='dataset-v6-number-cell'>{escape(_format_angka(baris['followers']))}</td>"
            f"<td class='dataset-v6-comment-cell' title='{escape(str(baris['komentar']), quote=True)}'>"
            f"<div class='dataset-v6-comment-text'>{escape(_potong_komentar(baris['komentar']))}</div></td>"
            f"<td class='dataset-v6-sentiment-cell'><span class='dataset-v6-sentiment-badge {kelas_badge}'>"
            f"{escape(sentimen)}</span></td>"
            f"<td class='dataset-v6-confidence-cell'>{escape(confidence_teks)}</td>"
            "</tr>"
        )

    if not isi:
        isi.append(
            "<tr><td colspan='8' class='dataset-v6-empty-row'>"
            "Tidak ada data yang sesuai dengan filter aktif.</td></tr>"
        )

    return (
        '<div class="dataset-v6-table-shell">'
        '<table class="dataset-v6-table">'
        f"{header}<tbody>{''.join(isi)}</tbody>"
        "</table></div>"
    )


def _siapkan_csv(data: pd.DataFrame) -> bytes:
    """Siapkan CSV hasil filter dalam UTF-8 BOM agar mudah dibuka di Excel."""
    ekspor = data.copy()
    ekspor["tanggal"] = pd.to_datetime(ekspor["tanggal"], errors="coerce").dt.strftime(
        "%Y-%m-%d %H:%M:%S"
    )
    ekspor = ekspor.rename(
        columns={
            "tanggal": "Tanggal",
            "layanan": "Layanan",
            "platform": "Platform",
            "username": "Username",
            "followers": "Followers",
            "komentar": "Komentar",
            "sentimen": "Sentimen",
            "confidence": "Confidence Score",
        }
    )
    return ekspor.to_csv(index=False).encode("utf-8-sig")


def _konfigurasi_chart(figur: go.Figure, judul_sumbu_x: str) -> go.Figure:
    """Terapkan tema gelap dan legenda interaktif pada chart Plotly."""
    figur.update_layout(
        height=370,
        margin=dict(l=20, r=54, t=78, b=24),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(family="Inter, sans-serif", color="#FFFFFF"),
        barmode="group",
        bargap=0.30,
        transition=dict(duration=320, easing="cubic-in-out"),
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.04,
            xanchor="left",
            x=0,
            bgcolor="rgba(26,26,26,0.92)",
            bordercolor="#343434",
            borderwidth=1,
            font=dict(family="Inter, sans-serif", color="#EAEAEA", size=12),
            itemclick="toggle",
            itemdoubleclick=False,
            traceorder="normal",
        ),
        xaxis=dict(
            title=judul_sumbu_x,
            gridcolor="#2A2A2A",
            zerolinecolor="#2A2A2A",
            tickfont=dict(color="#AAAAAA"),
            title_font=dict(color="#AAAAAA"),
            rangemode="tozero",
        ),
        yaxis=dict(
            gridcolor="rgba(0,0,0,0)",
            tickfont=dict(color="#FFFFFF"),
            categoryorder="trace",
        ),
        showlegend=True,
        hoverlabel=dict(bgcolor="#1A1A1A", font_color="#FFFFFF"),
        uirevision="dataset-v6-chart-interaktif",
    )
    return figur


def _buat_trace_batang(
    label: str,
    nilai: int,
    warna: str,
    urutan_legenda: int,
) -> go.Bar:
    """Buat satu trace batang agar setiap kategori dapat disembunyikan lewat legenda."""
    return go.Bar(
        x=[int(nilai)],
        y=[label],
        name=label,
        legendrank=urutan_legenda,
        orientation="h",
        marker=dict(color=warna, line=dict(color=warna, width=1)),
        text=[int(nilai)],
        textposition="outside",
        cliponaxis=False,
        width=0.72,
        hovertemplate=f"{label}: %{{x:,}} data<extra></extra>",
    )


def _chart_sentimen(data: pd.DataFrame) -> go.Figure:
    """Buat chart sentimen dengan kategori yang dapat ditampilkan atau disembunyikan."""
    urutan = ["Positif", "Netral", "Negatif"]
    jumlah = data["sentimen"].value_counts().reindex(urutan, fill_value=0)
    figur = go.Figure()

    for indeks, label in enumerate(urutan):
        figur.add_trace(
            _buat_trace_batang(
                label=label,
                nilai=int(jumlah[label]),
                warna=WARNA_SENTIMEN[label],
                urutan_legenda=indeks,
            )
        )

    return _konfigurasi_chart(figur, "Jumlah Data")


def _chart_platform(data: pd.DataFrame) -> go.Figure:
    """Buat chart platform dengan kategori yang dapat ditampilkan atau disembunyikan."""
    urutan = ["Twitter", "Instagram", "TikTok"]
    jumlah = data["platform"].value_counts().reindex(urutan, fill_value=0)
    figur = go.Figure()

    for indeks, label in enumerate(urutan):
        figur.add_trace(
            _buat_trace_batang(
                label=label,
                nilai=int(jumlah[label]),
                warna=WARNA_PLATFORM[label],
                urutan_legenda=indeks,
            )
        )

    return _konfigurasi_chart(figur, "Jumlah Data")


def _render_chart_legend(items: list[tuple[str, str]]) -> None:
    """Tampilkan legenda warna sederhana untuk membantu membaca chart."""
    fragmen: list[str] = []
    for label, warna in items:
        fragmen.append(
            f'<div class="dataset-v6-legend-item">'
            f'<span class="dataset-v6-legend-dot" style="background:{escape(warna)};"></span>'
            f'<span class="dataset-v6-legend-label">{escape(label)}</span>'
            f'</div>'
        )

    st.markdown(
        '<div class="dataset-v6-legend-row">' + ''.join(fragmen) + '</div>',
        unsafe_allow_html=True,
    )


@_DIALOG_DECORATOR("Tampilan Layar Penuh", width="large")
def _tampilkan_chart_layar_penuh(
    judul: str,
    figur: go.Figure,
    legenda: list[tuple[str, str]],
) -> None:
    """Tampilkan satu chart dalam dialog layar penuh dengan ikon X."""
    try:
        st.markdown(
            '<div class="dataset-v6-fullscreen-heading">'
            f'<div class="dataset-v6-fullscreen-title">{escape(judul)}</div>'
            '<div class="dataset-v6-fullscreen-hint">Klik legenda untuk menyembunyikan atau menampilkan kategori.</div>'
            '</div>',
            unsafe_allow_html=True,
        )

        figur_besar = go.Figure(figur)
        figur_besar.update_layout(
            height=820,
            autosize=True,
            margin=dict(l=36, r=90, t=86, b=58),
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
            legend=dict(
                orientation="h",
                yanchor="bottom",
                y=1.035,
                xanchor="left",
                x=0,
                bgcolor="rgba(26,26,26,0.92)",
                bordercolor="#343434",
                borderwidth=1,
                font=dict(family="Inter, sans-serif", color="#EAEAEA", size=14),
                itemclick="toggle",
                itemdoubleclick=False,
                traceorder="normal",
            ),
            transition=dict(duration=360, easing="cubic-in-out"),
        )
        st.plotly_chart(
            figur_besar,
            config={
                "displayModeBar": True,
                "displaylogo": False,
                "responsive": True,
                "scrollZoom": True,
            },
            **_opsi_lebar_penuh(st.plotly_chart),
        )
    except Exception as exc:
        LOGGER.exception("Chart layar penuh gagal ditampilkan")
        st.error(
            "Grafik belum dapat ditampilkan dalam layar penuh. "
            "Silakan tutup tampilan ini lalu coba kembali."
        )
        st.code(str(exc))


def _inject_css() -> None:
    """Sisipkan seluruh CSS halaman Dataset tanpa mengubah file tema global."""
    st.markdown(
        """
        <style>
            @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=Plus+Jakarta+Sans:wght@500;600;700;800&display=swap');

            div[data-testid="stAppViewContainer"] {
                background: #0D0D0D;
            }

            div[data-testid="stAppViewContainer"] .main .block-container {
                color: #FFFFFF;
                padding-top: 1.25rem;
                padding-bottom: 2.5rem;
            }

            .dataset-v6-page,
            .dataset-v6-page * {
                box-sizing: border-box;
                font-family: 'Inter', sans-serif;
            }

            .dataset-v6-hero {
                background:
                    radial-gradient(circle at 92% 8%, rgba(255,255,255,0.16), transparent 30%),
                    linear-gradient(135deg, #B71C1C 0%, #E53935 56%, #F05A56 100%);
                border: 1px solid rgba(255,255,255,0.12);
                border-radius: 12px;
                box-shadow: 0 14px 34px rgba(183,28,28,0.22);
                margin-bottom: 1.25rem;
                overflow: hidden;
                padding: 1.8rem 2rem;
                position: relative;
            }

            .dataset-v6-hero::after {
                background: radial-gradient(circle, rgba(255,255,255,0.16), transparent 68%);
                content: '';
                height: 250px;
                pointer-events: none;
                position: absolute;
                right: -80px;
                top: -120px;
                width: 250px;
            }

            .dataset-v6-hero h1 {
                color: #FFFFFF !important;
                font-family: 'Plus Jakarta Sans', 'Inter', sans-serif;
                font-size: clamp(1.65rem, 3vw, 2.15rem);
                font-weight: 800;
                letter-spacing: -0.03em;
                line-height: 1.15;
                margin: 0;
                position: relative;
                z-index: 1;
            }

            .dataset-v6-hero p {
                color: rgba(255,255,255,0.92) !important;
                font-size: 0.96rem;
                margin: 0.65rem 0 0.95rem;
                max-width: 860px;
                position: relative;
                z-index: 1;
            }

            .dataset-v6-source-row {
                display: flex;
                flex-wrap: wrap;
                gap: 0.45rem;
                position: relative;
                z-index: 1;
            }

            .dataset-v6-source-badge {
                backdrop-filter: blur(8px);
                border: 1px solid rgba(255,255,255,0.20);
                border-radius: 999px;
                color: #FFFFFF;
                display: inline-flex;
                font-size: 0.70rem;
                font-weight: 700;
                padding: 0.4rem 0.65rem;
            }

            .dataset-v6-source-real { background: rgba(27,94,32,0.55); }
            .dataset-v6-source-dummy { background: rgba(120,53,15,0.55); }

            .dataset-v6-filter-title,
            .dataset-v6-section-title {
                color: #FFFFFF;
                font-family: 'Plus Jakarta Sans', 'Inter', sans-serif;
                font-size: 1rem;
                font-weight: 700;
                margin: 0.4rem 0 0.65rem;
            }

            div[data-testid="stSelectbox"] label,
            div[data-testid="stTextInput"] label {
                color: #AAAAAA !important;
                font-size: 0.78rem !important;
                font-weight: 600 !important;
            }

            div[data-testid="stSelectbox"] div[data-baseweb="select"] > div,
            div[data-testid="stTextInput"] input {
                background: #242424 !important;
                border: 1px solid #343434 !important;
                border-radius: 10px !important;
                color: #FFFFFF !important;
                min-height: 42px;
                transition: border-color 0.18s ease, box-shadow 0.18s ease,
                    background-color 0.18s ease;
            }

            div[data-testid="stSelectbox"] div[data-baseweb="select"] > div:hover,
            div[data-testid="stTextInput"] input:hover {
                background: #282828 !important;
                border-color: #4A4A4A !important;
            }

            div[data-testid="stSelectbox"] div[data-baseweb="select"] > div:focus-within,
            div[data-testid="stTextInput"] input:focus {
                border-color: #E53935 !important;
                box-shadow: 0 0 0 3px rgba(229, 57, 53, 0.14) !important;
                outline: none !important;
            }

            div[data-testid="stTextInput"] input::placeholder {
                color: #777777 !important;
            }

            div[data-testid="stSelectbox"] svg {
                fill: #AAAAAA !important;
                transition: fill 0.18s ease, transform 0.18s ease;
            }

            div[data-testid="stSelectbox"]:hover svg {
                fill: #FFFFFF !important;
            }

            /*
             * Dropdown Streamlit dirender melalui portal di luar container
             * halaman. Semua lapisan wrapper portal dipaksa memakai warna
             * gelap agar tidak muncul bidang putih pada versi Streamlit yang
             * menggunakan virtual dropdown.
             */
            /*
             * Streamlit versi baru dapat merender root virtual dropdown sebagai
             * elemen <ul>, bukan <div>. Karena itu selector tidak boleh dikunci
             * pada nama tag. Aturan ini menutup root, viewport react-window,
             * spacer, dan seluruh lapisan pembungkus yang sebelumnya masih putih.
             */
            [data-testid="stSelectboxVirtualDropdown"],
            [data-testid="stSelectboxVirtualDropdown"] > *,
            [data-testid="stSelectboxVirtualDropdown"] > * > *,
            [data-testid="stSelectboxVirtualDropdown"] [style*="overflow"],
            [data-testid="stSelectboxVirtualDropdown"] [style*="height"],
            [data-baseweb="popover"],
            [data-baseweb="popover"] > *,
            [data-baseweb="popover"] > * > *,
            [data-baseweb="menu"],
            [data-baseweb="menu"] > *,
            [data-baseweb="menu"] > * > * {
                background: #1F1F1F !important;
                background-color: #1F1F1F !important;
                background-image: none !important;
                color: #FFFFFF !important;
            }

            [data-baseweb="popover"],
            [data-baseweb="popover"] > div,
            [data-baseweb="popover"] > div > div,
            [data-baseweb="popover"] [data-baseweb="menu"],
            [data-baseweb="popover"] [data-baseweb="menu"] > div,
            [data-baseweb="popover"] [role="listbox"],
            [data-baseweb="popover"] [role="listbox"] > div,
            [data-baseweb="popover"] [role="listbox"] > div > div,
            [data-testid="stSelectboxVirtualDropdown"],
            [data-testid="stSelectboxVirtualDropdown"] > div,
            [data-testid="stSelectboxVirtualDropdown"] > div > div,
            [data-testid="stSelectboxVirtualDropdown"] [data-baseweb="menu"],
            [data-testid="stSelectboxVirtualDropdown"] [data-baseweb="menu"] > div,
            [data-testid="stSelectboxVirtualDropdown"] [role="listbox"],
            [data-testid="stSelectboxVirtualDropdown"] [role="listbox"] > div,
            [data-testid="stSelectboxVirtualDropdown"] [role="listbox"] > div > div {
                background-color: #1F1F1F !important;
                background-image: none !important;
                color: #FFFFFF !important;
            }

            [data-baseweb="popover"],
            [data-testid="stSelectboxVirtualDropdown"] {
                border: 1px solid #3A3A3A !important;
                border-radius: 12px !important;
                box-shadow: 0 18px 48px rgba(0, 0, 0, 0.58),
                    0 0 0 1px rgba(255, 255, 255, 0.025) !important;
                overflow: hidden !important;
            }

            [data-baseweb="popover"] [data-baseweb="menu"],
            [data-testid="stSelectboxVirtualDropdown"] [data-baseweb="menu"],
            [data-baseweb="menu"] {
                background-color: #1F1F1F !important;
                background-image: none !important;
                border: 0 !important;
                border-radius: 12px !important;
                box-shadow: none !important;
                color: #FFFFFF !important;
                overflow: hidden !important;
                padding: 0 !important;
            }

            [data-baseweb="popover"] [role="listbox"],
            [data-testid="stSelectboxVirtualDropdown"] [role="listbox"],
            ul[role="listbox"],
            div[role="listbox"] {
                background-color: #1F1F1F !important;
                background-image: none !important;
                border: 0 !important;
                border-radius: 11px !important;
                color: #FFFFFF !important;
                margin: 0 !important;
                max-height: 280px !important;
                overflow-x: hidden !important;
                overflow-y: auto !important;
                padding: 0.38rem !important;
                scrollbar-color: #5A5A5A #1F1F1F;
                scrollbar-width: thin;
            }

            [data-baseweb="popover"] [role="listbox"]::-webkit-scrollbar,
            [data-testid="stSelectboxVirtualDropdown"] [role="listbox"]::-webkit-scrollbar,
            ul[role="listbox"]::-webkit-scrollbar,
            div[role="listbox"]::-webkit-scrollbar {
                width: 7px;
            }

            [data-baseweb="popover"] [role="listbox"]::-webkit-scrollbar-track,
            [data-testid="stSelectboxVirtualDropdown"] [role="listbox"]::-webkit-scrollbar-track,
            ul[role="listbox"]::-webkit-scrollbar-track,
            div[role="listbox"]::-webkit-scrollbar-track {
                background: #1F1F1F !important;
                border-radius: 999px;
            }

            [data-baseweb="popover"] [role="listbox"]::-webkit-scrollbar-thumb,
            [data-testid="stSelectboxVirtualDropdown"] [role="listbox"]::-webkit-scrollbar-thumb,
            ul[role="listbox"]::-webkit-scrollbar-thumb,
            div[role="listbox"]::-webkit-scrollbar-thumb {
                background: #555555 !important;
                border: 2px solid #1F1F1F;
                border-radius: 999px;
            }

            [data-baseweb="popover"] [role="listbox"]::-webkit-scrollbar-thumb:hover,
            [data-testid="stSelectboxVirtualDropdown"] [role="listbox"]::-webkit-scrollbar-thumb:hover,
            ul[role="listbox"]::-webkit-scrollbar-thumb:hover,
            div[role="listbox"]::-webkit-scrollbar-thumb:hover {
                background: #707070 !important;
            }

            [data-baseweb="popover"] [role="option"],
            [data-testid="stSelectboxVirtualDropdown"] [role="option"],
            li[role="option"],
            div[role="option"] {
                align-items: center !important;
                background-color: #1F1F1F !important;
                background-image: none !important;
                border: 1px solid transparent !important;
                border-radius: 8px !important;
                box-shadow: none !important;
                color: #EAEAEA !important;
                display: flex !important;
                font-family: 'Inter', sans-serif !important;
                font-size: 0.92rem !important;
                font-weight: 500 !important;
                line-height: 1.25 !important;
                margin: 0.12rem 0 !important;
                min-height: 42px !important;
                outline: none !important;
                padding: 0.68rem 0.82rem !important;
                transition: background-color 0.15s ease, border-color 0.15s ease,
                    color 0.15s ease, box-shadow 0.15s ease !important;
            }

            [data-baseweb="popover"] [role="option"] > div,
            [data-baseweb="popover"] [role="option"] > div > div,
            [data-testid="stSelectboxVirtualDropdown"] [role="option"] > div,
            [data-testid="stSelectboxVirtualDropdown"] [role="option"] > div > div,
            li[role="option"] > div,
            div[role="option"] > div {
                background-color: transparent !important;
                background-image: none !important;
            }

            [data-baseweb="popover"] [role="option"] *,
            [data-testid="stSelectboxVirtualDropdown"] [role="option"] *,
            li[role="option"] *,
            div[role="option"] * {
                color: inherit !important;
                font-family: 'Inter', sans-serif !important;
            }

            [data-baseweb="popover"] [role="option"]:hover,
            [data-testid="stSelectboxVirtualDropdown"] [role="option"]:hover,
            li[role="option"]:hover,
            div[role="option"]:hover {
                background-color: #2C2C2C !important;
                background-image: none !important;
                border-color: #3B3B3B !important;
                color: #FFFFFF !important;
            }

            [data-baseweb="popover"] [role="option"][aria-selected="true"],
            [data-testid="stSelectboxVirtualDropdown"] [role="option"][aria-selected="true"],
            li[role="option"][aria-selected="true"],
            div[role="option"][aria-selected="true"] {
                background-color: #34373D !important;
                background-image: linear-gradient(
                    90deg,
                    rgba(229, 57, 53, 0.24) 0,
                    #34373D 34%
                ) !important;
                border-color: #474A50 !important;
                box-shadow: inset 3px 0 0 #E53935 !important;
                color: #FFFFFF !important;
                font-weight: 600 !important;
            }

            /*
             * Baris filter diselaraskan dari sisi bawah. Dengan cara ini tombol
             * Reset memiliki baseline yang sama dengan kotak selectbox dan input,
             * tanpa spacer buatan yang dapat berubah pada tiap versi Streamlit.
             */
            div[data-testid="stHorizontalBlock"]:has(.dataset-v6-reset-marker) {
                align-items: flex-end !important;
            }

            div[data-testid="stColumn"]:has(.dataset-v6-reset-marker) {
                align-self: stretch !important;
                display: flex !important;
            }

            div[data-testid="stColumn"]:has(.dataset-v6-reset-marker) > div,
            div[data-testid="stColumn"]:has(.dataset-v6-reset-marker) div[data-testid="stVerticalBlock"] {
                display: flex !important;
                flex: 1 1 auto !important;
                flex-direction: column !important;
                justify-content: flex-end !important;
                min-height: 100% !important;
                width: 100% !important;
            }

            /*
             * Sembunyikan hanya elemen penanda alignment. Jangan menyembunyikan
             * seluruh stMarkdownContainer pada kolom tombol karena label tombol
             * Streamlit juga dapat dirender melalui container tersebut.
             */
            div[data-testid="stColumn"]:has(.dataset-v6-reset-marker)
            div[data-testid="stMarkdown"]:has(.dataset-v6-reset-marker),
            div[data-testid="stColumn"]:has(.dataset-v6-reset-marker)
            div[data-testid="stMarkdownContainer"]:has(.dataset-v6-reset-marker) {
                display: none !important;
                height: 0 !important;
                margin: 0 !important;
                min-height: 0 !important;
                padding: 0 !important;
            }

            .dataset-v6-reset-marker {
                display: none !important;
            }

            div[data-testid="stColumn"]:has(.dataset-v6-reset-marker) div[data-testid="stButton"],
            div[data-testid="stColumn"]:has(.dataset-v6-reset-marker) div[data-testid="stFormSubmitButton"] {
                margin: 0 !important;
                padding: 0 !important;
                width: 100% !important;
            }

            div[data-testid="stColumn"]:has(.dataset-v6-reset-marker) div[data-testid="stButton"] button,
            div[data-testid="stColumn"]:has(.dataset-v6-reset-marker) div[data-testid="stFormSubmitButton"] button {
                background: #E53935 !important;
                border: 1px solid #E53935 !important;
                border-radius: 10px !important;
                color: #FFFFFF !important;
                font-weight: 700 !important;
                height: 42px !important;
                margin: 0 !important;
                min-height: 42px !important;
                padding-bottom: 0 !important;
                padding-top: 0 !important;
                transition: all 0.18s ease;
                width: 100% !important;
            }

            div[data-testid="stColumn"]:has(.dataset-v6-reset-marker) div[data-testid="stButton"] button p,
            div[data-testid="stColumn"]:has(.dataset-v6-reset-marker) div[data-testid="stButton"] button span,
            div[data-testid="stColumn"]:has(.dataset-v6-reset-marker) div[data-testid="stFormSubmitButton"] button p,
            div[data-testid="stColumn"]:has(.dataset-v6-reset-marker) div[data-testid="stFormSubmitButton"] button span {
                color: #FFFFFF !important;
                display: inline !important;
                font-family: 'Inter', sans-serif !important;
                font-size: 0.95rem !important;
                font-weight: 700 !important;
                line-height: 1.2 !important;
                margin: 0 !important;
                opacity: 1 !important;
                visibility: visible !important;
            }

            div[data-testid="stColumn"]:has(.dataset-v6-reset-marker) div[data-testid="stButton"] button:hover,
            div[data-testid="stColumn"]:has(.dataset-v6-reset-marker) div[data-testid="stFormSubmitButton"] button:hover {
                background: #FF5252 !important;
                border-color: #FF5252 !important;
                box-shadow: 0 0 20px rgba(229,57,53,0.28);
            }

            /* Tombol utama tetap merah agar jelas sebagai aksi penerapan filter. */
            div[data-testid="stColumn"]:has(.dataset-v10-apply-marker)
            div[data-testid="stFormSubmitButton"] button {
                background: #E53935 !important;
                border-color: #E53935 !important;
                color: #FFFFFF !important;
            }

            div[data-testid="stColumn"]:has(.dataset-v10-apply-marker)
            div[data-testid="stFormSubmitButton"] button:hover {
                background: #FF5252 !important;
                border-color: #FF5252 !important;
                box-shadow: 0 0 20px rgba(229,57,53,0.28) !important;
            }

            /* Tombol reset memakai warna gelap netral agar tidak bersaing dengan aksi utama. */
            div[data-testid="stColumn"]:has(.dataset-v10-reset-marker)
            div[data-testid="stFormSubmitButton"] button {
                background: #24272D !important;
                border-color: #51565F !important;
                color: #F1F1F1 !important;
                box-shadow: none !important;
            }

            div[data-testid="stColumn"]:has(.dataset-v10-reset-marker)
            div[data-testid="stFormSubmitButton"] button:hover {
                background: #31353D !important;
                border-color: #737A86 !important;
                box-shadow: 0 0 18px rgba(255,255,255,0.08) !important;
            }

            .dataset-v6-metric-card {
                background: #1A1A1A;
                border: 1px solid #2A2A2A;
                border-left: 3px solid #E53935;
                border-radius: 12px;
                min-height: 205px;
                height: 205px;
                box-sizing: border-box;
                padding: 1rem 1.1rem;
                display: flex;
                flex-direction: column;
                justify-content: flex-start;
                transition: border-color 0.2s ease, box-shadow 0.2s ease, transform 0.2s ease;
            }

            .dataset-v6-metric-card:hover {
                border-color: #E53935;
                box-shadow: 0 0 22px rgba(229,57,53,0.16);
                transform: translateY(-2px);
            }

            .dataset-v6-metric-label {
                color: #AAAAAA;
                font-size: 0.78rem;
                font-weight: 600;
                margin-bottom: 0.5rem;
            }

            .dataset-v6-metric-value {
                color: #E53935;
                font-family: 'Plus Jakarta Sans', 'Inter', sans-serif;
                font-size: 2rem;
                font-weight: 800;
                line-height: 1.05;
            }

            .dataset-v6-metric-note {
                color: #666666;
                font-size: 0.72rem;
                margin-top: 0.55rem;
            }

            .dataset-v6-table-shell {
                background: #1A1A1A;
                border: 1px solid #2A2A2A;
                border-radius: 12px;
                margin-top: 0.4rem;
                margin-bottom: 1.35rem;
                max-height: 760px;
                overflow-x: auto;
                overflow-y: auto;
                scrollbar-gutter: stable;
                width: 100%;
            }

            .dataset-v6-table {
                border-collapse: separate;
                border-spacing: 0;
                color: #FFFFFF;
                font-size: 0.78rem;
                min-width: 1080px;
                table-layout: fixed;
                width: 100%;
            }

            .dataset-v6-table col.dataset-v6-col-no { width: 4.5%; }
            .dataset-v6-table col.dataset-v6-col-tanggal { width: 13%; }
            .dataset-v6-table col.dataset-v6-col-platform { width: 8.5%; }
            .dataset-v6-table col.dataset-v6-col-username { width: 13%; }
            .dataset-v6-table col.dataset-v6-col-followers { width: 9.5%; }
            .dataset-v6-table col.dataset-v6-col-komentar { width: 31.5%; }
            .dataset-v6-table col.dataset-v6-col-sentimen { width: 9%; }
            .dataset-v6-table col.dataset-v6-col-confidence { width: 11%; }

            .dataset-v6-table thead th {
                background: #242424;
                border-bottom: 1px solid #343434;
                color: #FFFFFF;
                font-weight: 700;
                line-height: 1.25;
                padding: 0.9rem 0.7rem;
                position: sticky;
                text-align: left;
                top: 0;
                vertical-align: middle;
                white-space: nowrap;
                z-index: 2;
            }

            .dataset-v6-table thead th:first-child,
            .dataset-v6-table tbody td:first-child,
            .dataset-v6-table thead th:nth-child(5),
            .dataset-v6-table tbody td:nth-child(5),
            .dataset-v6-table thead th:nth-child(7),
            .dataset-v6-table tbody td:nth-child(7),
            .dataset-v6-table thead th:nth-child(8),
            .dataset-v6-table tbody td:nth-child(8) {
                text-align: center;
            }

            .dataset-v6-table thead th:nth-child(8) {
                white-space: normal;
            }

            .dataset-v6-table tbody td {
                background: #1A1A1A;
                border-bottom: 1px solid #242424;
                color: #DADADA;
                line-height: 1.4;
                padding: 0.8rem 0.7rem;
                vertical-align: middle;
            }

            .dataset-v6-table tbody tr:hover td {
                background: #252525;
            }

            .dataset-v6-table tbody tr.dataset-v6-row-positive td {
                background: rgba(76, 175, 80, 0.075);
            }

            .dataset-v6-table tbody tr.dataset-v6-row-neutral td {
                background: rgba(255, 152, 0, 0.075);
            }

            .dataset-v6-table tbody tr.dataset-v6-row-negative td {
                background: rgba(244, 67, 54, 0.085);
            }

            .dataset-v6-table tbody tr.dataset-v6-row-positive td:first-child {
                box-shadow: inset 3px 0 0 #4CAF50;
            }

            .dataset-v6-table tbody tr.dataset-v6-row-neutral td:first-child {
                box-shadow: inset 3px 0 0 #FF9800;
            }

            .dataset-v6-table tbody tr.dataset-v6-row-negative td:first-child {
                box-shadow: inset 3px 0 0 #F44336;
            }

            .dataset-v6-table tbody tr.dataset-v6-row-positive:hover td,
            .dataset-v6-table tbody tr.dataset-v6-row-neutral:hover td,
            .dataset-v6-table tbody tr.dataset-v6-row-negative:hover td {
                background: #252525;
            }

            .dataset-v6-table tbody tr:last-child td {
                border-bottom: 0;
            }

            .dataset-v6-table tbody td:nth-child(2),
            .dataset-v6-table tbody td:nth-child(3) {
                white-space: nowrap;
            }

            .dataset-v6-username-cell {
                overflow: hidden;
                text-overflow: ellipsis;
                white-space: nowrap;
            }

            .dataset-v6-number-cell,
            .dataset-v6-confidence-cell,
            .dataset-v6-sentiment-cell {
                white-space: nowrap;
            }

            .dataset-v6-comment-cell {
                padding-left: 0.95rem !important;
                padding-right: 0.95rem !important;
                white-space: normal;
            }

            .dataset-v6-comment-text {
                display: -webkit-box;
                line-height: 1.45;
                max-width: 100%;
                overflow: hidden;
                overflow-wrap: anywhere;
                text-overflow: ellipsis;
                white-space: normal;
                -webkit-box-orient: vertical;
                -webkit-line-clamp: 2;
            }

            .dataset-v6-sentiment-badge {
                border-radius: 999px;
                color: #FFFFFF;
                display: inline-block;
                font-size: 0.70rem;
                font-weight: 700;
                min-width: 66px;
                padding: 0.34rem 0.58rem;
                text-align: center;
            }

            .dataset-v6-badge-positive { background: #4CAF50; }
            .dataset-v6-badge-neutral { background: #FF9800; }
            .dataset-v6-badge-negative { background: #F44336; }

            .dataset-v6-empty-row {
                color: #AAAAAA !important;
                padding: 2rem !important;
                text-align: center !important;
            }

            /*
             * Beri jarak vertikal antara kartu Ringkasan Data dan baris
             * judul Tabel Data beserta kontrol Baris per halaman.
             * Selector parent membuat kedua sisi tetap sejajar.
             */
            div[data-testid="stHorizontalBlock"]:has(.dataset-v6-table-title) {
                align-items: flex-end !important;
                padding-top: 1.35rem !important;
            }

            .dataset-v6-table-title {
                margin-bottom: 0.15rem;
                margin-top: 0 !important;
            }

            .dataset-v6-pagination-info {
                color: #AAAAAA;
                font-size: 0.82rem;
                line-height: 1.35;
                padding-top: 0.62rem;
                text-align: center;
            }

            .dataset-v6-info-text {
                color: #777777;
                font-size: 0.76rem;
                margin-top: 0.45rem;
            }


            .dataset-v6-legend-row {
                align-items: center;
                display: flex;
                flex-wrap: wrap;
                gap: 0.65rem 1rem;
                margin: 0.15rem 0 0.65rem;
            }

            .dataset-v6-legend-item {
                align-items: center;
                background: rgba(255,255,255,0.03);
                border: 1px solid #2A2A2A;
                border-radius: 999px;
                display: inline-flex;
                gap: 0.45rem;
                padding: 0.34rem 0.72rem;
            }

            .dataset-v6-legend-dot {
                border-radius: 999px;
                box-shadow: 0 0 0 1px rgba(255,255,255,0.06);
                display: inline-block;
                flex: 0 0 auto;
                height: 10px;
                width: 10px;
            }

            .dataset-v6-legend-label {
                color: #DADADA;
                font-family: 'Inter', sans-serif;
                font-size: 0.78rem;
                font-weight: 600;
                line-height: 1;
            }

            /* Tombol perbesar pada masing-masing chart Distribusi Cepat. */
            .dataset-v6-chart-action-marker {
                display: none !important;
            }

            div[data-testid="stColumn"]:has(.dataset-v6-chart-action-marker) {
                align-items: flex-start !important;
                display: flex !important;
                justify-content: flex-end !important;
            }

            div[data-testid="stColumn"]:has(.dataset-v6-chart-action-marker)
            div[data-testid="stMarkdown"]:has(.dataset-v6-chart-action-marker),
            div[data-testid="stColumn"]:has(.dataset-v6-chart-action-marker)
            div[data-testid="stMarkdownContainer"]:has(.dataset-v6-chart-action-marker) {
                display: none !important;
                height: 0 !important;
                margin: 0 !important;
                min-height: 0 !important;
                padding: 0 !important;
            }

            div[data-testid="stColumn"]:has(.dataset-v6-chart-action-marker)
            div[data-testid="stButton"] {
                margin: 0 !important;
                padding: 0 !important;
                width: 100% !important;
            }

            div[data-testid="stColumn"]:has(.dataset-v6-chart-action-marker)
            div[data-testid="stButton"] button {
                background: #242424 !important;
                border: 1px solid #343434 !important;
                border-radius: 9px !important;
                color: #EAEAEA !important;
                font-family: 'Inter', sans-serif !important;
                font-size: 0.76rem !important;
                font-weight: 700 !important;
                min-height: 36px !important;
                padding: 0.35rem 0.72rem !important;
                transition: background-color 0.18s ease, border-color 0.18s ease,
                    box-shadow 0.18s ease, color 0.18s ease !important;
                white-space: nowrap !important;
                width: 100% !important;
            }

            div[data-testid="stColumn"]:has(.dataset-v6-chart-action-marker)
            div[data-testid="stButton"] button:hover {
                background: #2E2E2E !important;
                border-color: #E53935 !important;
                box-shadow: 0 0 16px rgba(229,57,53,0.18) !important;
                color: #FFFFFF !important;
            }

            /*
             * Dialog Streamlit dibuat memenuhi viewport sehingga berfungsi
             * sebagai tampilan layar penuh di dalam aplikasi. Selector dibuat
             * ganda agar tetap bekerja pada struktur DOM Streamlit 1.35 dan
             * versi yang lebih baru.
             */
            div[data-baseweb="modal"],
            div[data-testid="stDialog"] {
                inset: 0 !important;
                margin: 0 !important;
                padding: 0 !important;
                position: fixed !important;
            }

            div[data-baseweb="modal"] [role="dialog"],
            div[data-testid="stDialog"] [role="dialog"] {
                background: #111111 !important;
                border: 0 !important;
                border-radius: 0 !important;
                box-shadow: none !important;
                height: 100dvh !important;
                inset: 0 !important;
                margin: 0 !important;
                max-height: 100dvh !important;
                max-width: 100vw !important;
                min-height: 100dvh !important;
                overflow: hidden !important;
                padding: 0 !important;
                position: fixed !important;
                transform: none !important;
                width: 100vw !important;
            }

            /* Judul bawaan dialog disembunyikan; ikon X tetap menjadi satu-satunya kontrol keluar. */
            div[data-testid="stDialog"] [data-testid="stDialogHeader"],
            div[data-baseweb="modal"] [data-testid="stDialogHeader"] {
                background: transparent !important;
                border: 0 !important;
                height: 0 !important;
                margin: 0 !important;
                min-height: 0 !important;
                padding: 0 !important;
                position: absolute !important;
                right: 0 !important;
                top: 0 !important;
                width: 0 !important;
                z-index: 1000 !important;
            }

            div[data-testid="stDialog"] [data-testid="stDialogHeader"] h2,
            div[data-testid="stDialog"] [data-testid="stDialogHeader"] p,
            div[data-baseweb="modal"] [data-testid="stDialogHeader"] h2,
            div[data-baseweb="modal"] [data-testid="stDialogHeader"] p {
                display: none !important;
            }

            div[data-testid="stDialog"] button[aria-label="Close"],
            div[data-baseweb="modal"] button[aria-label="Close"] {
                background: #242424 !important;
                border: 1px solid #343434 !important;
                border-radius: 9px !important;
                color: #FFFFFF !important;
                height: 38px !important;
                position: fixed !important;
                right: 14px !important;
                top: 14px !important;
                width: 38px !important;
                z-index: 1001 !important;
            }

            div[data-testid="stDialog"] div[data-testid="stVerticalBlock"]:has(.dataset-v6-fullscreen-title),
            div[data-baseweb="modal"] div[data-testid="stVerticalBlock"]:has(.dataset-v6-fullscreen-title) {
                gap: 0.45rem !important;
                height: 100dvh !important;
                margin: 0 !important;
                max-height: 100dvh !important;
                overflow: hidden !important;
                padding: 14px 18px 12px !important;
                width: 100vw !important;
            }

            .dataset-v6-fullscreen-heading {
                display: flex;
                flex: 0 0 auto;
                flex-direction: column;
                gap: 0.35rem;
                margin: 0 0 18px;
                padding-right: 52px;
            }

            .dataset-v6-fullscreen-title {
                color: #FFFFFF !important;
                font-family: 'Plus Jakarta Sans', 'Inter', sans-serif;
                font-size: clamp(1.15rem, 2vw, 1.65rem);
                font-weight: 800;
                letter-spacing: -0.02em;
                line-height: 1.15;
                margin: 0;
                padding: 0;
            }

            .dataset-v6-fullscreen-hint {
                color: #8F8F8F;
                font-family: 'Inter', sans-serif;
                font-size: 0.75rem;
                line-height: 1.35;
                margin: 0;
                padding: 0;
            }

            div[data-testid="stDialog"] [data-testid="stPlotlyChart"],
            div[data-baseweb="modal"] [data-testid="stPlotlyChart"] {
                background: #151B26 !important;
                border: 1px solid #2B3A50 !important;
                border-radius: 14px !important;
                height: calc(100dvh - 116px) !important;
                margin: 0 !important;
                min-height: 520px !important;
                overflow: hidden !important;
                width: 100% !important;
            }

            div[data-testid="stDialog"] [data-testid="stPlotlyChart"] > div,
            div[data-testid="stDialog"] [data-testid="stPlotlyChart"] .js-plotly-plot,
            div[data-testid="stDialog"] [data-testid="stPlotlyChart"] .plot-container,
            div[data-testid="stDialog"] [data-testid="stPlotlyChart"] .svg-container,
            div[data-baseweb="modal"] [data-testid="stPlotlyChart"] > div,
            div[data-baseweb="modal"] [data-testid="stPlotlyChart"] .js-plotly-plot,
            div[data-baseweb="modal"] [data-testid="stPlotlyChart"] .plot-container,
            div[data-baseweb="modal"] [data-testid="stPlotlyChart"] .svg-container {
                height: 100% !important;
                width: 100% !important;
            }

            @media (max-width: 760px) {
                div[data-testid="stDialog"] div[data-testid="stVerticalBlock"]:has(.dataset-v6-fullscreen-title),
                div[data-baseweb="modal"] div[data-testid="stVerticalBlock"]:has(.dataset-v6-fullscreen-title) {
                    padding: 10px !important;
                }

                div[data-testid="stColumn"]:has(.dataset-v6-chart-action-marker)
                div[data-testid="stButton"] button {
                    font-size: 0 !important;
                    min-width: 42px !important;
                    padding: 0.35rem !important;
                }

                div[data-testid="stColumn"]:has(.dataset-v6-chart-action-marker)
                div[data-testid="stButton"] button::after {
                    content: "⛶";
                    font-size: 1rem !important;
                }
            }

            div[data-testid="stDownloadButton"] button {
                background: #E53935 !important;
                border: 1px solid #E53935 !important;
                border-radius: 8px !important;
                color: #FFFFFF !important;
                font-weight: 700 !important;
            }

            div[data-testid="stDownloadButton"] button:hover {
                background: #FF5252 !important;
                border-color: #FF5252 !important;
            }

            /*
             * Expander Streamlit dapat dirender sebagai wrapper div atau
             * elemen details, tergantung versi Streamlit. Seluruh lapisan
             * header ditargetkan agar tidak kembali memakai warna putih.
             */
            [data-testid="stExpander"],
            [data-testid="stExpander"] > details,
            details[data-testid="stExpander"] {
                background: #1A1A1A !important;
                background-color: #1A1A1A !important;
                border: 1px solid #2A2A2A !important;
                border-radius: 12px !important;
                box-shadow: none !important;
                margin-top: 1rem;
                overflow: hidden !important;
            }

            [data-testid="stExpander"] summary,
            [data-testid="stExpander"] > details > summary,
            details[data-testid="stExpander"] > summary {
                align-items: center !important;
                background: #242424 !important;
                background-color: #242424 !important;
                background-image: none !important;
                border: 0 !important;
                border-radius: 11px !important;
                color: #FFFFFF !important;
                min-height: 54px !important;
                padding: 0.85rem 1.15rem !important;
            }

            [data-testid="stExpander"] details[open] > summary,
            details[data-testid="stExpander"][open] > summary {
                border-bottom: 1px solid #2F2F2F !important;
                border-radius: 11px 11px 0 0 !important;
            }

            [data-testid="stExpander"] summary:hover,
            [data-testid="stExpander"] summary:focus-visible {
                background: #2B2B2B !important;
                background-color: #2B2B2B !important;
            }

            /*
             * Terapkan font Inter hanya pada teks label expander.
             * Jangan menimpa seluruh elemen span karena ikon bawaan Streamlit
             * menggunakan ligature Material Symbols seperti "arrow_right".
             */
            [data-testid="stExpander"] summary [data-testid="stMarkdownContainer"],
            [data-testid="stExpander"] summary [data-testid="stMarkdownContainer"] p,
            [data-testid="stExpander"] summary [data-testid="stMarkdownContainer"] span {
                background: transparent !important;
                color: #FFFFFF !important;
                font-family: 'Inter', sans-serif !important;
                font-weight: 700 !important;
                margin: 0 !important;
            }

            /* Pulihkan font ligature ikon agar teks "arrow_right" tidak bocor. */
            [data-testid="stExpander"] summary [data-testid="stExpanderToggleIcon"],
            [data-testid="stExpander"] summary span[class*="material-symbols"] {
                background: transparent !important;
                color: #E53935 !important;
                direction: ltr !important;
                display: inline-block !important;
                flex: 0 0 auto !important;
                font-family: 'Material Symbols Rounded', 'Material Symbols Outlined' !important;
                font-feature-settings: 'liga' !important;
                font-size: 1.35rem !important;
                font-style: normal !important;
                font-variation-settings: 'FILL' 0, 'wght' 500, 'GRAD' 0, 'opsz' 24 !important;
                font-weight: 400 !important;
                letter-spacing: normal !important;
                line-height: 1 !important;
                text-transform: none !important;
                white-space: nowrap !important;
                word-wrap: normal !important;
                -webkit-font-feature-settings: 'liga' !important;
                -webkit-font-smoothing: antialiased !important;
            }

            [data-testid="stExpander"] summary svg {
                color: #E53935 !important;
                fill: #E53935 !important;
                flex: 0 0 auto !important;
            }

            [data-testid="stExpander"] [data-testid="stExpanderDetails"] {
                background: #1A1A1A !important;
                color: #FFFFFF !important;
                padding-top: 0.65rem !important;
            }

            /*
             * Tooltip bantuan Streamlit dirender melalui portal BaseWeb.
             * Lapisan Inner bawaan mengikuti secondary background tema dan
             * dapat tetap putih walaupun popover dropdown sudah dibuat gelap.
             * Selector :has() membatasi aturan ini hanya pada popover tooltip,
             * sehingga tidak mengubah tampilan menu dropdown yang sudah benar.
             */
            div[data-baseweb="popover"]:has([data-testid="stTooltipContent"]),
            div[data-baseweb="popover"]:has(.stTooltipContent) {
                background: transparent !important;
                border: 0 !important;
                box-shadow: none !important;
                max-width: min(340px, calc(100vw - 32px)) !important;
                width: max-content !important;
            }

            div[data-baseweb="popover"]:has([data-testid="stTooltipContent"]) > div,
            div[data-baseweb="popover"]:has([data-testid="stTooltipContent"]) > div > div,
            div[data-baseweb="popover"]:has(.stTooltipContent) > div,
            div[data-baseweb="popover"]:has(.stTooltipContent) > div > div {
                background: #242424 !important;
                background-color: #242424 !important;
                background-image: none !important;
                border-radius: 10px !important;
                color: #F5F5F5 !important;
            }

            div[data-testid="stTooltipContent"],
            .stTooltipContent {
                background: #242424 !important;
                background-color: #242424 !important;
                border: 1px solid #3A3A3A !important;
                border-radius: 10px !important;
                box-shadow: 0 12px 32px rgba(0, 0, 0, 0.48) !important;
                color: #F5F5F5 !important;
                font-family: 'Inter', sans-serif !important;
                font-size: 0.78rem !important;
                line-height: 1.45 !important;
                max-width: min(340px, calc(100vw - 32px)) !important;
                overflow-wrap: anywhere !important;
                padding: 0.68rem 0.82rem !important;
                white-space: normal !important;
                width: max-content !important;
            }

            div[data-testid="stTooltipContent"] *,
            .stTooltipContent * {
                background: transparent !important;
                color: #F5F5F5 !important;
                font-family: 'Inter', sans-serif !important;
                font-size: inherit !important;
                line-height: inherit !important;
                margin-bottom: 0 !important;
                margin-top: 0 !important;
                opacity: 1 !important;
            }

            .dataset-v6-active-source {
                align-items: center;
                display: flex;
                flex-wrap: wrap;
                gap: 0.65rem;
                margin: 0.35rem 0 1rem;
            }

            .dataset-v6-active-source-name {
                color: #8F8F8F;
                font-size: 0.76rem;
                overflow-wrap: anywhere;
            }

            .dataset-v6-sna-note {
                background: #1A1A1A;
                border: 1px solid #2A2A2A;
                border-left: 3px solid #E53935;
                border-radius: 12px;
                color: #AAAAAA;
                min-height: 205px;
                height: 205px;
                box-sizing: border-box;
                padding: 1rem 1.1rem;
                display: flex;
                flex-direction: column;
                justify-content: flex-start;
                gap: 0.55rem;
            }

            .dataset-v6-sna-note-title {
                color: #FFFFFF;
                font-size: 0.98rem;
                font-weight: 700;
                line-height: 1.3;
                margin: 0;
            }

            .dataset-v6-sna-note-body {
                color: #AAAAAA;
                font-size: 0.82rem;
                line-height: 1.55;
                margin: 0;
            }

            .dataset-v6-sna-table-gap {
                display: block;
                width: 100%;
                height: 28px;
                min-height: 28px;
            }

            div[data-testid="stButton"] button {
                border-radius: 8px;
            }

            /* ================================================================
             * FASE 16 v1.4 - Upload Dataset Sendiri
             * Seluruh aturan di bawah hanya aktif pada expander upload.
             * Komponen Dataset bawaan tidak ikut berubah.
             * ================================================================ */
            @keyframes datasetV16UploadGlow {
                0%, 100% {
                    box-shadow: 0 14px 34px rgba(0, 0, 0, 0.28),
                        0 0 0 1px rgba(229, 57, 53, 0.04);
                }
                50% {
                    box-shadow: 0 18px 46px rgba(0, 0, 0, 0.34),
                        0 0 32px rgba(229, 57, 53, 0.13);
                }
            }

            @keyframes datasetV16Float {
                0%, 100% { transform: translateY(0) rotate(-2deg); }
                50% { transform: translateY(-5px) rotate(2deg); }
            }

            @keyframes datasetV16Shimmer {
                0% { transform: translateX(-135%); }
                100% { transform: translateX(235%); }
            }

            @keyframes datasetV16FadeUp {
                from { opacity: 0; transform: translateY(10px); }
                to { opacity: 1; transform: translateY(0); }
            }

            div[data-testid="stExpander"]:has(.dataset-v16-upload-anchor) {
                background:
                    radial-gradient(circle at 92% -8%, rgba(229, 57, 53, 0.14), transparent 34%),
                    radial-gradient(circle at 4% 104%, rgba(108, 92, 231, 0.10), transparent 31%),
                    linear-gradient(145deg, #171717 0%, #131313 100%);
                border: 1px solid rgba(255, 255, 255, 0.10) !important;
                border-radius: 18px !important;
                box-shadow: 0 14px 34px rgba(0, 0, 0, 0.28);
                overflow: hidden;
                position: relative;
                transition: border-color 0.25s ease, box-shadow 0.25s ease,
                    transform 0.25s ease;
                animation: datasetV16UploadGlow 5s ease-in-out infinite;
            }

            div[data-testid="stExpander"]:has(.dataset-v16-upload-anchor)::before {
                background: linear-gradient(90deg, #E53935, #FF7043, #8E5AF7, #E53935);
                background-size: 240% 100%;
                content: '';
                height: 3px;
                left: 0;
                position: absolute;
                right: 0;
                top: 0;
                z-index: 3;
            }

            div[data-testid="stExpander"]:has(.dataset-v16-upload-anchor):hover {
                border-color: rgba(229, 57, 53, 0.48) !important;
                box-shadow: 0 22px 54px rgba(0, 0, 0, 0.38),
                    0 0 34px rgba(229, 57, 53, 0.12);
                transform: translateY(-2px);
            }

            div[data-testid="stExpander"]:has(.dataset-v16-upload-anchor) details > summary {
                background: linear-gradient(90deg, rgba(255,255,255,0.055), rgba(255,255,255,0.018));
                border-bottom: 1px solid rgba(255, 255, 255, 0.06);
                min-height: 78px;
                padding: 0.35rem 1.35rem !important;
                transition: background 0.22s ease, padding-left 0.22s ease;
            }

            div[data-testid="stExpander"]:has(.dataset-v16-upload-anchor) details > summary:hover {
                background: linear-gradient(90deg, rgba(229,57,53,0.10), rgba(255,255,255,0.025));
                padding-left: 1.55rem !important;
            }

            div[data-testid="stExpander"]:has(.dataset-v16-upload-anchor) details > summary p {
                color: #FFFFFF !important;
                font-family: 'Plus Jakarta Sans', 'Inter', sans-serif !important;
                font-size: 1.05rem !important;
                font-weight: 800 !important;
                letter-spacing: -0.02em;
            }

            div[data-testid="stExpander"]:has(.dataset-v16-upload-anchor) details > summary svg {
                color: #FF6B67 !important;
                transition: transform 0.25s ease, color 0.25s ease;
            }

            div[data-testid="stExpander"]:has(.dataset-v16-upload-anchor) details[open] > summary svg {
                color: #FFFFFF !important;
                transform: rotate(90deg) scale(1.08);
            }

            div[data-testid="stExpander"]:has(.dataset-v16-upload-anchor) div[data-testid="stExpanderDetails"] {
                padding: 1.35rem 1.4rem 1.55rem !important;
            }

            .dataset-v16-upload-anchor {
                display: block;
                height: 0;
                overflow: hidden;
                width: 0;
            }

            .dataset-v16-upload-intro {
                align-items: center;
                animation: datasetV16FadeUp 0.42s ease both;
                background:
                    radial-gradient(circle at 88% 15%, rgba(255,255,255,0.11), transparent 28%),
                    linear-gradient(135deg, rgba(183,28,28,0.86), rgba(229,57,53,0.72) 54%, rgba(91,52,173,0.72));
                border: 1px solid rgba(255,255,255,0.14);
                border-radius: 16px;
                display: flex;
                gap: 1rem;
                margin: 0 0 1.2rem;
                overflow: hidden;
                padding: 1.15rem 1.25rem;
                position: relative;
                transition: transform 0.25s ease, box-shadow 0.25s ease;
            }

            .dataset-v16-upload-intro::after {
                background: linear-gradient(90deg, transparent, rgba(255,255,255,0.13), transparent);
                content: '';
                height: 100%;
                left: 0;
                position: absolute;
                top: 0;
                transform: translateX(-135%);
                width: 42%;
            }

            .dataset-v16-upload-intro:hover {
                box-shadow: 0 16px 34px rgba(183,28,28,0.24);
                transform: translateY(-2px);
            }

            .dataset-v16-upload-intro:hover::after {
                animation: datasetV16Shimmer 1.15s ease;
            }

            .dataset-v16-upload-icon {
                align-items: center;
                animation: datasetV16Float 3.4s ease-in-out infinite;
                background: rgba(10,10,10,0.28);
                border: 1px solid rgba(255,255,255,0.18);
                border-radius: 14px;
                box-shadow: inset 0 1px 0 rgba(255,255,255,0.12);
                display: flex;
                flex: 0 0 54px;
                font-size: 1.7rem;
                height: 54px;
                justify-content: center;
                position: relative;
                z-index: 1;
            }

            .dataset-v16-upload-copy {
                min-width: 0;
                position: relative;
                z-index: 1;
            }

            .dataset-v16-upload-eyebrow {
                color: rgba(255,255,255,0.70);
                font-size: 0.68rem;
                font-weight: 800;
                letter-spacing: 0.13em;
                margin-bottom: 0.22rem;
                text-transform: uppercase;
            }

            .dataset-v16-upload-title {
                color: #FFFFFF;
                font-family: 'Plus Jakarta Sans', 'Inter', sans-serif;
                font-size: 1.08rem;
                font-weight: 800;
                letter-spacing: -0.025em;
                line-height: 1.25;
                margin: 0;
            }

            .dataset-v16-upload-subtitle {
                color: rgba(255,255,255,0.80);
                font-size: 0.78rem;
                line-height: 1.55;
                margin: 0.28rem 0 0;
            }

            .dataset-v16-upload-chips {
                display: flex;
                flex-wrap: wrap;
                gap: 0.42rem;
                margin-left: auto;
                position: relative;
                z-index: 1;
            }

            .dataset-v16-upload-chip {
                background: rgba(8,8,8,0.30);
                border: 1px solid rgba(255,255,255,0.16);
                border-radius: 999px;
                color: #FFFFFF;
                font-size: 0.68rem;
                font-weight: 700;
                padding: 0.42rem 0.62rem;
                transition: background 0.2s ease, transform 0.2s ease, border-color 0.2s ease;
                white-space: nowrap;
            }

            .dataset-v16-upload-chip:hover {
                background: rgba(255,255,255,0.15);
                border-color: rgba(255,255,255,0.34);
                transform: translateY(-2px);
            }

            div[data-testid="stExpander"]:has(.dataset-v16-upload-anchor) div[data-testid="stFileUploader"] {
                animation: datasetV16FadeUp 0.48s 0.05s ease both;
                margin-bottom: 1.25rem;
            }

            div[data-testid="stExpander"]:has(.dataset-v16-upload-anchor) div[data-testid="stFileUploader"] label {
                color: #F4F4F4 !important;
                font-size: 0.82rem !important;
                font-weight: 700 !important;
                margin-bottom: 0.55rem !important;
            }

            div[data-testid="stExpander"]:has(.dataset-v16-upload-anchor) [data-testid="stFileUploaderDropzone"] {
                background:
                    linear-gradient(145deg, rgba(255,255,255,0.038), rgba(255,255,255,0.014));
                border: 1px dashed rgba(229,57,53,0.56) !important;
                border-radius: 15px !important;
                min-height: 112px;
                padding: 1rem !important;
                position: relative;
                transition: background 0.24s ease, border-color 0.24s ease,
                    box-shadow 0.24s ease, transform 0.24s ease;
            }

            /* FASE 17 v1.3 - Ratakan tombol upload dan informasi batas file. */
            div[data-testid="stExpander"]:has(.dataset-v16-upload-anchor) [data-testid="stFileUploaderDropzone"] {
                align-items: center !important;
                display: flex !important;
                justify-content: center !important;
            }

            div[data-testid="stExpander"]:has(.dataset-v16-upload-anchor)
            [data-testid="stFileUploaderDropzone"] > div {
                align-items: center !important;
                display: flex !important;
                flex-direction: row !important;
                gap: 1.5rem !important;
                justify-content: center !important;
                margin: 0 auto !important;
                padding: 0 !important;
                width: auto !important;
            }

            /* FASE 17 v1.4 - Pertahankan posisi dan pulihkan teks informasi upload. */
            div[data-testid="stExpander"]:has(.dataset-v16-upload-anchor)
            [data-testid="stFileUploaderDropzoneInstructions"] {
                align-items: center !important;
                color: #A8A8AD !important;
                display: flex !important;
                flex: 0 0 auto !important;
                font-size: 1.05rem !important;
                font-weight: 500 !important;
                justify-content: center !important;
                line-height: 1.2 !important;
                margin: 0 !important;
                min-height: 0 !important;
                padding: 0 !important;
                white-space: nowrap !important;
            }

            div[data-testid="stExpander"]:has(.dataset-v16-upload-anchor)
            [data-testid="stFileUploaderDropzoneInstructions"] > * {
                display: none !important;
            }

            div[data-testid="stExpander"]:has(.dataset-v16-upload-anchor)
            [data-testid="stFileUploaderDropzoneInstructions"]::after {
                color: #A8A8AD !important;
                content: "50MB per file • CSV, XLSX";
                display: block !important;
                font-size: 1.05rem !important;
                font-weight: 500 !important;
                line-height: 1.2 !important;
                margin: 0 !important;
                padding: 0 !important;
                white-space: nowrap !important;
            }

            div[data-testid="stExpander"]:has(.dataset-v16-upload-anchor)
            [data-testid="stFileUploaderDropzone"] button {
                align-self: center !important;
                flex: 0 0 auto !important;
                margin: 0 !important;
            }

            div[data-testid="stExpander"]:has(.dataset-v16-upload-anchor) [data-testid="stFileUploaderDropzone"]::after {
                background: radial-gradient(circle, rgba(229,57,53,0.13), transparent 67%);
                content: '';
                height: 110px;
                pointer-events: none;
                position: absolute;
                right: -28px;
                top: -38px;
                width: 110px;
            }

            div[data-testid="stExpander"]:has(.dataset-v16-upload-anchor) [data-testid="stFileUploaderDropzone"]:hover {
                background: linear-gradient(145deg, rgba(229,57,53,0.085), rgba(142,90,247,0.045));
                border-color: #FF625D !important;
                box-shadow: 0 0 0 4px rgba(229,57,53,0.08),
                    0 14px 30px rgba(0,0,0,0.22);
                transform: translateY(-2px);
            }

            div[data-testid="stExpander"]:has(.dataset-v16-upload-anchor) [data-testid="stFileUploaderDropzone"] button {
                background: linear-gradient(135deg, #E53935, #FF5A52) !important;
                border: 0 !important;
                border-radius: 10px !important;
                box-shadow: 0 8px 18px rgba(229,57,53,0.22) !important;
                color: #FFFFFF !important;
                font-weight: 800 !important;
                transition: transform 0.2s ease, box-shadow 0.2s ease !important;
            }

            div[data-testid="stExpander"]:has(.dataset-v16-upload-anchor) [data-testid="stFileUploaderDropzone"] button:hover {
                box-shadow: 0 11px 24px rgba(229,57,53,0.34) !important;
                transform: translateY(-2px) scale(1.02);
            }

            .dataset-v16-empty-state {
                align-items: center;
                background: rgba(255,255,255,0.025);
                border: 1px solid rgba(255,255,255,0.065);
                border-radius: 14px;
                color: #8F8F8F;
                display: flex;
                font-size: 0.77rem;
                gap: 0.65rem;
                line-height: 1.5;
                margin: 1rem 0 1rem;
                padding: 0.85rem 1rem;
            }

            .dataset-v16-empty-state strong { color: #DADADA; }

            /* FASE 18 v1.3 - Beri white spacing pada empty state dan tombol analisis. */
            div[data-testid="stExpander"]:has(.dataset-v16-upload-anchor)
            div[data-testid="stButton"]:has(button:disabled) {
                margin: 0.65rem 0 1rem !important;
            }

            .dataset-v16-file-strip {
                align-items: center;
                animation: datasetV16FadeUp 0.44s ease both;
                background: linear-gradient(90deg, rgba(76,175,80,0.11), rgba(255,255,255,0.025));
                border: 1px solid rgba(76,175,80,0.28);
                border-radius: 13px;
                display: flex;
                gap: 0.75rem;
                margin: 0 0 1.2rem;
                padding: 0.85rem 1rem;
                transition: border-color 0.2s ease, transform 0.2s ease;
            }

            .dataset-v16-file-strip:hover {
                border-color: rgba(76,175,80,0.58);
                transform: translateX(3px);
            }

            .dataset-v16-file-icon {
                align-items: center;
                background: rgba(76,175,80,0.16);
                border: 1px solid rgba(76,175,80,0.30);
                border-radius: 10px;
                display: flex;
                flex: 0 0 40px;
                font-size: 1.15rem;
                height: 40px;
                justify-content: center;
            }

            .dataset-v16-file-meta { min-width: 0; }

            .dataset-v16-file-name {
                color: #FFFFFF;
                font-size: 0.82rem;
                font-weight: 800;
                overflow: hidden;
                text-overflow: ellipsis;
                white-space: nowrap;
            }

            .dataset-v16-file-detail {
                color: #9FA7A0;
                font-size: 0.69rem;
                margin-top: 0.14rem;
            }

            .dataset-v16-file-status {
                background: rgba(76,175,80,0.15);
                border: 1px solid rgba(76,175,80,0.30);
                border-radius: 999px;
                color: #7EE083;
                font-size: 0.67rem;
                font-weight: 800;
                margin-left: auto;
                padding: 0.38rem 0.58rem;
                white-space: nowrap;
            }

            .dataset-v16-analysis-ready {
                align-items: center;
                animation: datasetV16FadeUp 0.44s 0.04s ease both;
                background:
                    radial-gradient(circle at 92% 0%, rgba(142,90,247,0.14), transparent 34%),
                    linear-gradient(145deg, rgba(229,57,53,0.075), rgba(255,255,255,0.018));
                border: 1px solid rgba(229,57,53,0.20);
                border-radius: 14px;
                display: flex;
                gap: 0.75rem;
                margin: 0.1rem 0 0.8rem;
                padding: 0.85rem 0.95rem;
                transition: border-color 0.22s ease, box-shadow 0.22s ease, transform 0.22s ease;
            }

            .dataset-v16-analysis-ready:hover {
                border-color: rgba(229,57,53,0.42);
                box-shadow: 0 12px 28px rgba(0,0,0,0.22), 0 0 22px rgba(229,57,53,0.07);
                transform: translateY(-2px);
            }

            .dataset-v16-analysis-ready-icon {
                align-items: center;
                background: linear-gradient(145deg, rgba(229,57,53,0.20), rgba(142,90,247,0.18));
                border: 1px solid rgba(255,255,255,0.11);
                border-radius: 11px;
                display: flex;
                flex: 0 0 42px;
                font-size: 1.08rem;
                height: 42px;
                justify-content: center;
                transition: transform 0.22s ease;
            }

            .dataset-v16-analysis-ready:hover .dataset-v16-analysis-ready-icon {
                transform: rotate(-7deg) scale(1.08);
            }

            .dataset-v16-analysis-ready-title {
                color: #F5F5F5;
                font-family: 'Plus Jakarta Sans', 'Inter', sans-serif;
                font-size: 0.80rem;
                font-weight: 800;
                line-height: 1.3;
            }

            .dataset-v16-analysis-ready-note {
                color: #858585;
                font-size: 0.68rem;
                line-height: 1.5;
                margin-top: 0.14rem;
            }

            div[data-testid="stExpander"]:has(.dataset-v16-upload-anchor) div[data-testid="stButton"] {
                animation: datasetV16FadeUp 0.44s 0.08s ease both;
                margin: 0 0 1.2rem;
            }

            div[data-testid="stExpander"]:has(.dataset-v16-upload-anchor) div[data-testid="stButton"] > button {
                background: linear-gradient(100deg, #B71C1C 0%, #E53935 46%, #8E5AF7 100%) !important;
                background-size: 180% 100% !important;
                border: 1px solid rgba(255,255,255,0.17) !important;
                border-radius: 13px !important;
                box-shadow: 0 12px 28px rgba(183,28,28,0.25), 0 0 0 1px rgba(255,255,255,0.03) inset;
                color: #FFFFFF !important;
                font-family: 'Plus Jakarta Sans', 'Inter', sans-serif !important;
                font-size: 0.80rem !important;
                font-weight: 800 !important;
                min-height: 48px;
                overflow: hidden;
                position: relative;
                transition: background-position 0.32s ease, border-color 0.22s ease,
                    box-shadow 0.22s ease, transform 0.18s ease !important;
            }

            div[data-testid="stExpander"]:has(.dataset-v16-upload-anchor) div[data-testid="stButton"] > button::before {
                background: linear-gradient(90deg, transparent, rgba(255,255,255,0.24), transparent);
                content: '';
                height: 100%;
                left: 0;
                pointer-events: none;
                position: absolute;
                top: 0;
                transform: translateX(-135%);
                width: 38%;
            }

            div[data-testid="stExpander"]:has(.dataset-v16-upload-anchor) div[data-testid="stButton"] > button:hover {
                background-position: 100% 0 !important;
                border-color: rgba(255,255,255,0.34) !important;
                box-shadow: 0 16px 34px rgba(183,28,28,0.31), 0 0 28px rgba(142,90,247,0.16);
                transform: translateY(-2px) scale(1.006);
            }

            div[data-testid="stExpander"]:has(.dataset-v16-upload-anchor) div[data-testid="stButton"] > button:hover::before {
                animation: datasetV16Shimmer 1.05s ease;
            }

            div[data-testid="stExpander"]:has(.dataset-v16-upload-anchor) div[data-testid="stButton"] > button:active {
                transform: translateY(0) scale(0.99);
            }

            .dataset-v16-preview-heading {
                align-items: flex-end;
                display: flex;
                gap: 0.7rem;
                justify-content: space-between;
                margin: 0.2rem 0 0.72rem;
            }

            .dataset-v16-preview-heading-left {
                align-items: center;
                display: flex;
                gap: 0.7rem;
            }

            .dataset-v16-preview-icon {
                align-items: center;
                background: linear-gradient(135deg, rgba(229,57,53,0.24), rgba(142,90,247,0.22));
                border: 1px solid rgba(229,57,53,0.30);
                border-radius: 10px;
                display: flex;
                font-size: 1.05rem;
                height: 38px;
                justify-content: center;
                width: 38px;
            }

            .dataset-v16-preview-title {
                color: #FFFFFF;
                font-family: 'Plus Jakarta Sans', 'Inter', sans-serif;
                font-size: 1.05rem;
                font-weight: 800;
                letter-spacing: -0.02em;
                line-height: 1.25;
            }

            .dataset-v16-preview-note {
                color: #7C7C7C;
                font-size: 0.69rem;
                margin-top: 0.12rem;
            }

            .dataset-v16-preview-badge {
                background: rgba(142,90,247,0.12);
                border: 1px solid rgba(142,90,247,0.26);
                border-radius: 999px;
                color: #BFA8FF;
                font-size: 0.66rem;
                font-weight: 800;
                padding: 0.38rem 0.58rem;
                white-space: nowrap;
            }

            div[data-testid="stExpander"]:has(.dataset-v16-upload-anchor) div[data-testid="stDataFrame"] {
                animation: datasetV16FadeUp 0.48s 0.08s ease both;
                border: 1px solid rgba(255,255,255,0.09);
                border-radius: 14px;
                box-shadow: 0 12px 28px rgba(0,0,0,0.22);
                margin-bottom: 1.2rem;
                overflow: hidden;
                transition: border-color 0.22s ease, box-shadow 0.22s ease;
            }

            div[data-testid="stExpander"]:has(.dataset-v16-upload-anchor) div[data-testid="stDataFrame"]:hover {
                border-color: rgba(229,57,53,0.42);
                box-shadow: 0 15px 34px rgba(0,0,0,0.28), 0 0 24px rgba(229,57,53,0.07);
            }

            .dataset-v16-metric-card {
                align-items: center;
                animation: datasetV16FadeUp 0.46s ease both;
                background:
                    radial-gradient(circle at 94% 8%, var(--upload-accent-soft), transparent 34%),
                    linear-gradient(145deg, #1B1B1B, #151515);
                border: 1px solid rgba(255,255,255,0.075);
                border-radius: 15px;
                display: flex;
                gap: 0.9rem;
                min-height: 112px;
                overflow: hidden;
                padding: 1rem 1.05rem;
                position: relative;
                transition: border-color 0.22s ease, box-shadow 0.22s ease, transform 0.22s ease;
            }

            .dataset-v16-metric-card::before {
                background: var(--upload-accent);
                bottom: 0;
                content: '';
                left: 0;
                position: absolute;
                top: 0;
                width: 3px;
            }

            .dataset-v16-metric-card:hover {
                border-color: var(--upload-accent-border);
                box-shadow: 0 14px 30px rgba(0,0,0,0.26), 0 0 24px var(--upload-accent-glow);
                transform: translateY(-3px);
            }

            .dataset-v16-metric-icon {
                align-items: center;
                background: var(--upload-accent-soft);
                border: 1px solid var(--upload-accent-border);
                border-radius: 12px;
                display: flex;
                flex: 0 0 46px;
                font-size: 1.18rem;
                height: 46px;
                justify-content: center;
                transition: transform 0.22s ease;
            }

            .dataset-v16-metric-card:hover .dataset-v16-metric-icon {
                transform: rotate(-6deg) scale(1.08);
            }

            .dataset-v16-metric-label {
                color: #8D8D8D;
                font-size: 0.70rem;
                font-weight: 700;
                margin-bottom: 0.2rem;
            }

            .dataset-v16-metric-value {
                color: var(--upload-accent);
                font-family: 'Plus Jakarta Sans', 'Inter', sans-serif;
                font-size: 1.7rem;
                font-weight: 800;
                letter-spacing: -0.035em;
                line-height: 1;
            }

            .dataset-v16-metric-note {
                color: #686868;
                font-size: 0.67rem;
                margin-top: 0.25rem;
            }

            .dataset-v16-metric-red {
                --upload-accent: #FF5751;
                --upload-accent-soft: rgba(229,57,53,0.14);
                --upload-accent-border: rgba(229,57,53,0.34);
                --upload-accent-glow: rgba(229,57,53,0.11);
            }

            .dataset-v16-metric-purple {
                --upload-accent: #B49AFF;
                --upload-accent-soft: rgba(142,90,247,0.14);
                --upload-accent-border: rgba(142,90,247,0.34);
                --upload-accent-glow: rgba(142,90,247,0.11);
            }

            .dataset-v16-columns-section {
                animation: datasetV16FadeUp 0.5s 0.08s ease both;
                background: rgba(255,255,255,0.022);
                border: 1px solid rgba(255,255,255,0.07);
                border-radius: 15px;
                margin-top: 1.05rem;
                padding: 1rem;
            }

            .dataset-v16-columns-header {
                align-items: center;
                display: flex;
                justify-content: space-between;
                margin-bottom: 0.75rem;
            }

            .dataset-v16-columns-title {
                color: #F3F3F3;
                font-family: 'Plus Jakarta Sans', 'Inter', sans-serif;
                font-size: 0.88rem;
                font-weight: 800;
            }

            .dataset-v16-columns-count {
                background: rgba(229,57,53,0.11);
                border: 1px solid rgba(229,57,53,0.24);
                border-radius: 999px;
                color: #FF7A75;
                font-size: 0.64rem;
                font-weight: 800;
                padding: 0.32rem 0.52rem;
            }

            .dataset-v16-columns-wrap {
                display: flex;
                flex-wrap: wrap;
                gap: 0.46rem;
                max-height: 250px;
                overflow-y: auto;
                padding: 0.1rem 0.22rem 0.15rem 0;
                scrollbar-color: #4C4C4C transparent;
                scrollbar-width: thin;
            }

            .dataset-v16-column-badge {
                background: linear-gradient(145deg, #202127, #191A1F);
                border: 1px solid #30323A;
                border-radius: 8px;
                color: #D9DAE0;
                cursor: default;
                font-family: 'Inter', monospace;
                font-size: 0.68rem;
                line-height: 1;
                padding: 0.48rem 0.58rem;
                transition: background 0.18s ease, border-color 0.18s ease,
                    color 0.18s ease, transform 0.18s ease;
            }

            .dataset-v16-column-badge:hover {
                background: linear-gradient(145deg, rgba(229,57,53,0.15), rgba(142,90,247,0.11));
                border-color: rgba(229,57,53,0.40);
                color: #FFFFFF;
                transform: translateY(-2px);
            }

            .dataset-v16-success {
                align-items: center;
                animation: datasetV16FadeUp 0.48s 0.12s ease both;
                background:
                    radial-gradient(circle at 92% 10%, rgba(76,175,80,0.16), transparent 32%),
                    linear-gradient(90deg, rgba(31,82,52,0.78), rgba(25,55,39,0.64));
                border: 1px solid rgba(76,175,80,0.32);
                border-radius: 14px;
                display: flex;
                gap: 0.75rem;
                margin-top: 1rem;
                overflow: hidden;
                padding: 0.9rem 1rem;
                position: relative;
                transition: border-color 0.2s ease, transform 0.2s ease;
            }

            .dataset-v16-success::after {
                background: linear-gradient(90deg, transparent, rgba(255,255,255,0.10), transparent);
                content: '';
                height: 100%;
                left: 0;
                position: absolute;
                top: 0;
                transform: translateX(-135%);
                width: 34%;
            }

            .dataset-v16-success:hover {
                border-color: rgba(76,175,80,0.58);
                transform: translateY(-2px);
            }

            .dataset-v16-success:hover::after {
                animation: datasetV16Shimmer 1.05s ease;
            }

            .dataset-v16-success-icon {
                align-items: center;
                background: rgba(76,175,80,0.18);
                border: 1px solid rgba(126,224,131,0.25);
                border-radius: 10px;
                display: flex;
                flex: 0 0 38px;
                font-size: 1rem;
                height: 38px;
                justify-content: center;
                position: relative;
                z-index: 1;
            }

            .dataset-v16-success-copy { position: relative; z-index: 1; }

            .dataset-v16-success-title {
                color: #F2FFF4;
                font-size: 0.80rem;
                font-weight: 800;
            }

            .dataset-v16-success-note {
                color: #A8C9AD;
                font-size: 0.68rem;
                margin-top: 0.12rem;
            }

            div[data-testid="stExpander"]:has(.dataset-v16-upload-anchor) div[data-testid="stAlert"] {
                border-radius: 13px !important;
                animation: datasetV16FadeUp 0.4s ease both;
            }

            @media (max-width: 900px) {
                .dataset-v16-upload-intro {
                    align-items: flex-start;
                    flex-wrap: wrap;
                }
                .dataset-v16-upload-chips {
                    margin-left: 0;
                    width: 100%;
                }
                .dataset-v16-metric-card { min-height: 102px; }
            }

            @media (prefers-reduced-motion: reduce) {
                div[data-testid="stExpander"]:has(.dataset-v16-upload-anchor),
                .dataset-v16-upload-icon,
                .dataset-v16-upload-intro,
                .dataset-v16-file-strip,
                .dataset-v16-analysis-ready,
                .dataset-v16-metric-card,
                .dataset-v16-columns-section,
                .dataset-v16-success,
                div[data-testid="stExpander"]:has(.dataset-v16-upload-anchor) div[data-testid="stButton"] {
                    animation: none !important;
                }
                div[data-testid="stExpander"]:has(.dataset-v16-upload-anchor),
                .dataset-v16-upload-intro,
                .dataset-v16-file-strip,
                .dataset-v16-analysis-ready,
                .dataset-v16-metric-card,
                .dataset-v16-column-badge,
                .dataset-v16-success,
                div[data-testid="stExpander"]:has(.dataset-v16-upload-anchor) div[data-testid="stButton"] > button {
                    transform: none !important;
                }
            }

            @media (max-width: 900px) {
                .dataset-v6-hero { padding: 1.35rem; }
                .dataset-v6-metric-card {
                    min-height: 170px;
                    height: auto;
                }
                .dataset-v6-sna-note {
                    min-height: 170px;
                    height: auto;
                }
                .dataset-v6-sna-table-gap {
                    height: 20px;
                    min-height: 20px;
                }
                .dataset-v6-table { font-size: 0.74rem; }
            }
        </style>
        """,
        unsafe_allow_html=True,
    )



def _deteksi_pemisah_csv(file_bytes: bytes) -> tuple[str, str]:
    """Deteksi encoding dan pemisah CSV dari sampel awal file upload."""
    sampel_bytes = file_bytes[:131072]
    kandidat_encoding = ("utf-8-sig", "utf-8", "latin-1")
    kandidat_pemisah = (",", ";", "\t", "|")

    for encoding in kandidat_encoding:
        try:
            sampel_teks = sampel_bytes.decode(encoding)
        except UnicodeDecodeError:
            continue

        try:
            hasil_sniffer = csv.Sniffer().sniff(
                sampel_teks,
                delimiters="".join(kandidat_pemisah),
            )
            return encoding, hasil_sniffer.delimiter
        except csv.Error:
            baris_header = next(
                (baris for baris in sampel_teks.splitlines() if baris.strip()),
                "",
            )
            jumlah_pemisah = {
                pemisah: baris_header.count(pemisah)
                for pemisah in kandidat_pemisah
            }
            pemisah_terpilih = max(jumlah_pemisah, key=jumlah_pemisah.get)
            if jumlah_pemisah[pemisah_terpilih] > 0:
                return encoding, pemisah_terpilih
            return encoding, ","

    return "latin-1", ","


@st.cache_data(show_spinner=False)
def _baca_dataset_upload_cached(file_bytes: bytes, ekstensi: str) -> pd.DataFrame:
    """Baca file upload CSV atau Excel tanpa mengubah isi dan nama kolom."""
    ekstensi_normal = str(ekstensi).strip().lower()

    if ekstensi_normal == ".csv":
        encoding_terdeteksi, pemisah_terdeteksi = _deteksi_pemisah_csv(file_bytes)
        percobaan_csv = [
            (encoding_terdeteksi, pemisah_terdeteksi, "c"),
            ("utf-8-sig", pemisah_terdeteksi, "c"),
            ("utf-8", pemisah_terdeteksi, "c"),
            ("latin-1", pemisah_terdeteksi, "c"),
            (encoding_terdeteksi, pemisah_terdeteksi, "python"),
        ]

        data = None
        error_terakhir: Exception | None = None
        percobaan_terpakai: set[tuple[str, str, str]] = set()

        for encoding, pemisah, engine in percobaan_csv:
            identitas_percobaan = (encoding, pemisah, engine)
            if identitas_percobaan in percobaan_terpakai:
                continue
            percobaan_terpakai.add(identitas_percobaan)

            try:
                opsi_baca: dict[str, Any] = {
                    "sep": pemisah,
                    "encoding": encoding,
                    "engine": engine,
                }
                if engine == "c":
                    opsi_baca["low_memory"] = False

                data = pd.read_csv(
                    io.BytesIO(file_bytes),
                    **opsi_baca,
                )
                break
            except pd.errors.EmptyDataError:
                raise
            except (UnicodeDecodeError, pd.errors.ParserError) as exc:
                error_terakhir = exc

        if data is None:
            raise ValueError("csv_gagal_dibaca") from error_terakhir

    elif ekstensi_normal == ".xlsx":
        # Beberapa workbook hasil ekspor aplikasi pihak ketiga tidak memiliki
        # style bawaan bernama "Normal". Openpyxl tetap dapat membaca datanya,
        # tetapi menampilkan UserWarning yang tidak memengaruhi isi workbook.
        with warnings.catch_warnings():
            warnings.filterwarnings(
                "ignore",
                message=r"Workbook contains no default style.*",
                category=UserWarning,
                module=r"openpyxl\.styles\.stylesheet",
            )
            data = pd.read_excel(
                io.BytesIO(file_bytes),
                engine="openpyxl",
            )
    else:
        raise ValueError("format_tidak_didukung")

    if data.empty:
        raise ValueError("file_kosong")

    return data


def _daftar_kolom_teks(data: pd.DataFrame) -> list[Any]:
    """Ambil kolom yang dapat diperiksa sebagai teks tanpa mengubah data asli."""
    kolom_teks: list[Any] = []
    for kolom in data.columns:
        try:
            series = data[kolom]
            if pd.api.types.is_string_dtype(series.dtype) or series.dtype == object:
                kolom_teks.append(kolom)
        except Exception:
            LOGGER.exception("Kolom %s gagal diperiksa tipe datanya", kolom)
    return kolom_teks


def _memiliki_keyword_telkom(data: pd.DataFrame, kolom_teks: list[Any]) -> bool:
    """Cari keyword layanan Telkom pada seluruh nilai di seluruh kolom teks."""
    pola_keyword = "|".join(re.escape(keyword) for keyword in KEYWORD_RELEVANSI_TELKOM)

    for kolom in kolom_teks:
        try:
            series_teks = data[kolom].fillna("").astype(str)
            if series_teks.str.contains(
                pola_keyword,
                case=False,
                na=False,
                regex=True,
            ).any():
                return True
        except Exception:
            LOGGER.exception("Keyword matching gagal pada kolom %s", kolom)
    return False


def _ambil_sampel_kolom_teks_terpanjang(
    data: pd.DataFrame,
    kolom_teks: list[Any],
) -> str:
    """Ambil maksimal 10 baris dari kolom dengan rata-rata teks terpanjang."""
    kolom_terpilih: Any | None = None
    rata_rata_terpanjang = -1.0

    for kolom in kolom_teks:
        try:
            series_teks = data[kolom].fillna("").astype(str).str.strip()
            rata_rata = float(series_teks.str.len().mean() or 0.0)
            if rata_rata > rata_rata_terpanjang:
                rata_rata_terpanjang = rata_rata
                kolom_terpilih = kolom
        except Exception:
            LOGGER.exception("Panjang teks gagal dihitung pada kolom %s", kolom)

    if kolom_terpilih is None:
        return ""

    sampel = (
        data[kolom_terpilih]
        .fillna("")
        .astype(str)
        .str.strip()
        .head(10)
    )
    baris_terisi = [teks for teks in sampel.tolist() if teks]
    return "\n".join(baris_terisi)


def _deteksi_relevansi_dataset_upload(data: pd.DataFrame) -> tuple[bool, str]:
    """Deteksi relevansi melalui keyword, lalu Gemini hanya jika diperlukan."""
    try:
        kolom_teks = _daftar_kolom_teks(data)
        if _memiliki_keyword_telkom(data, kolom_teks):
            LOGGER.info("Fase 17: data upload relevan melalui keyword matching.")
            return True, "keyword"

        sampel_teks = _ambil_sampel_kolom_teks_terpanjang(data, kolom_teks)
        LOGGER.warning(
            "Fase 17: keyword Telkom tidak ditemukan. "
            "Pemeriksaan relevansi dilanjutkan melalui Gemini API."
        )
        hasil_gemini = bool(check_data_relevance(sampel_teks))
        return hasil_gemini, "gemini"
    except Exception:
        LOGGER.exception("Deteksi relevansi dataset upload gagal")
        return False, "error"



# === TAHAP 4 FASE 18: OUTPUT ANALISIS DATA UPLOAD ===
_LABEL_SENTIMEN_INGGRIS = {
    "Positif": "positive",
    "Netral": "neutral",
    "Negatif": "negative",
}


def _bersihkan_state_hasil_analisis_upload() -> None:
    """Bersihkan hasil Fase 18 tanpa mengubah file upload yang sedang dipilih."""
    st.session_state.pop(STATE_DETECTED_TEXT_COL, None)
    st.session_state.pop(STATE_DETECTED_PLATFORM, None)
    st.session_state.pop(STATE_UPLOAD_PLATFORM_COL, None)
    st.session_state.pop(STATE_UPLOAD_OUTPUT_DF, None)
    st.session_state.pop(STATE_UPLOAD_OUTPUT_SIGNATURE, None)
    st.session_state.pop(STATE_UPLOAD_OUTPUT_ERROR, None)


def _deteksi_kolom_teks_upload(data: pd.DataFrame) -> str | None:
    """Pilih kolom teks utama berdasarkan nama kolom dan isi terpanjang."""
    try:
        if data is None or data.empty:
            return None

        kolom_teks = _daftar_kolom_teks(data)
        if not kolom_teks:
            return None

        prioritas_nama = (
            "content",
            "text",
            "comment",
            "komentar",
            "caption",
            "tweet",
            "full_text",
            "content_clean",
            "cleaned_text",
            "review",
            "ulasan",
            "description",
            "body",
            "message",
        )
        peta_nama = {
            re.sub(r"[^a-z0-9]+", "_", str(kolom).strip().lower()).strip("_"): kolom
            for kolom in kolom_teks
        }
        for nama in prioritas_nama:
            if nama in peta_nama:
                return str(peta_nama[nama])

        skor_kolom: list[tuple[float, str]] = []
        for kolom in kolom_teks:
            series = data[kolom].fillna("").astype(str).str.strip()
            series_terisi = series[series.ne("")]
            if series_terisi.empty:
                skor = 0.0
            else:
                skor = float(series_terisi.str.len().mean())
            skor_kolom.append((skor, str(kolom)))

        skor_kolom.sort(key=lambda item: (item[0], item[1]), reverse=True)
        return skor_kolom[0][1] if skor_kolom else str(kolom_teks[0])
    except Exception:
        LOGGER.exception("Deteksi kolom teks upload gagal")
        return None


def _normalisasi_platform_upload(nilai: Any) -> str:
    """Normalisasi nama platform upload menjadi Twitter, Instagram, atau TikTok."""
    teks = _bersihkan_teks(nilai).lower()
    bentuk_ringkas = re.sub(r"[^a-z0-9]+", "", teks)
    if bentuk_ringkas in {"twitter", "x", "twitterx", "xcom"}:
        return "Twitter"
    if bentuk_ringkas in {"instagram", "ig", "insta"}:
        return "Instagram"
    if bentuk_ringkas in {"tiktok", "tik tok", "tt"}:
        return "TikTok"
    return _bersihkan_teks(nilai)


def _deteksi_platform_upload(data: pd.DataFrame) -> tuple[str, str | None]:
    """Deteksi kolom platform dan ringkasan platform yang terdapat pada upload."""
    try:
        if data is None or data.empty:
            return "Tidak terdeteksi", None

        kandidat_nama = (
            "platform",
            "media_sosial",
            "social_media",
            "source_platform",
            "kanal",
            "channel",
        )
        peta_nama = {
            re.sub(r"[^a-z0-9]+", "_", str(kolom).strip().lower()).strip("_"): str(kolom)
            for kolom in data.columns
        }
        kolom_platform = next(
            (peta_nama[nama] for nama in kandidat_nama if nama in peta_nama),
            None,
        )
        if kolom_platform is None:
            return "Tidak terdeteksi", None

        nilai_platform = (
            data[kolom_platform]
            .fillna("")
            .map(_normalisasi_platform_upload)
            .astype(str)
            .str.strip()
        )
        nilai_platform = nilai_platform[nilai_platform.ne("")]
        unik = list(dict.fromkeys(nilai_platform.tolist()))
        if not unik:
            return "Tidak terdeteksi", kolom_platform
        if len(unik) == 1:
            return unik[0], kolom_platform
        return "Multi-platform", kolom_platform
    except Exception:
        LOGGER.exception("Deteksi platform upload gagal")
        return "Tidak terdeteksi", None


def _deteksi_kolom_sentimen_upload(data: pd.DataFrame) -> str | None:
    """Pilih kolom sentimen dengan jumlah label valid terbanyak."""
    try:
        kandidat = (
            "final_sentiment",
            "predicted_sentiment",
            "sentiment",
            "sentimen",
            "sentiment_label",
            "hasil_sentimen",
            "prediction",
            "label",
        )
        peta_nama = {
            re.sub(r"[^a-z0-9]+", "_", str(kolom).strip().lower()).strip("_"): str(kolom)
            for kolom in data.columns
        }

        kolom_terbaik: str | None = None
        jumlah_valid_terbaik = 0

        for nama in kandidat:
            kolom = peta_nama.get(nama)
            if not kolom or kolom not in data.columns:
                continue

            jumlah_valid = int(
                data[kolom]
                .map(_normalisasi_label_sentimen)
                .astype(str)
                .str.strip()
                .ne("")
                .sum()
            )
            if jumlah_valid > jumlah_valid_terbaik:
                kolom_terbaik = kolom
                jumlah_valid_terbaik = jumlah_valid

        return kolom_terbaik
    except Exception:
        LOGGER.exception("Deteksi kolom sentimen upload gagal")
        return None


def _folder_model_upload_lengkap(folder: Path) -> bool:
    """Validasi file minimum model Transformers lokal untuk analisis upload."""
    try:
        if not folder.is_dir():
            return False
        nama_file = {item.name for item in folder.iterdir() if item.is_file()}
        ada_konfigurasi = "config.json" in nama_file
        ada_bobot = any(
            nama in nama_file
            for nama in ("pytorch_model.bin", "model.safetensors")
        ) or any(
            nama.startswith("model-") and nama.endswith(".safetensors")
            for nama in nama_file
        )
        ada_tokenizer = any(
            nama in nama_file
            for nama in (
                "tokenizer.json",
                "tokenizer_config.json",
                "vocab.txt",
                "sentencepiece.bpe.model",
            )
        )
        return bool(ada_konfigurasi and ada_bobot and ada_tokenizer)
    except Exception:
        return False


@st.cache_resource(show_spinner=False)
def _muat_model_sentimen_upload() -> dict[str, Any]:
    """Muat IndoBERT sekali untuk klasifikasi sentimen dataset upload."""
    try:
        import torch
        from transformers import AutoModelForSequenceClassification, AutoTokenizer

        repo_id = "mdhugol/indonesia-bert-sentiment-classification"
        folder_lokal = _root_proyek() / "models" / "indihome"

        if _folder_model_upload_lengkap(folder_lokal):
            tokenizer = AutoTokenizer.from_pretrained(
                str(folder_lokal),
                local_files_only=True,
                use_fast=True,
            )
            model = AutoModelForSequenceClassification.from_pretrained(
                str(folder_lokal),
                local_files_only=True,
            )
        else:
            tokenizer = AutoTokenizer.from_pretrained(repo_id, use_fast=True)
            model = AutoModelForSequenceClassification.from_pretrained(repo_id)

        perangkat = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        model.to(perangkat)
        model.eval()
        return {
            "tokenizer": tokenizer,
            "model": model,
            "torch": torch,
            "device": perangkat,
        }
    except Exception as exc:
        raise RuntimeError(
            "Model IndoBERT tidak dapat dimuat. Pastikan transformers dan torch "
            "sudah terpasang serta internet aktif saat model pertama kali diunduh. "
            f"Detail: {exc}"
        ) from exc


def _prediksi_sentimen_batch_upload(teks: list[str], ukuran_batch: int = 32) -> list[str]:
    """Prediksi banyak teks menggunakan IndoBERT dengan batch yang aman untuk CPU."""
    try:
        runtime = _muat_model_sentimen_upload()
        tokenizer = runtime["tokenizer"]
        model = runtime["model"]
        torch = runtime["torch"]
        perangkat = runtime["device"]
        id2label = getattr(model.config, "id2label", {}) or {}

        hasil: list[str] = []
        daftar_teks = [str(item or "").strip() for item in teks]
        for awal in range(0, len(daftar_teks), max(1, int(ukuran_batch))):
            batch = daftar_teks[awal : awal + max(1, int(ukuran_batch))]
            batch_aman = [item if item else "teks kosong" for item in batch]
            encoded = tokenizer(
                batch_aman,
                return_tensors="pt",
                truncation=True,
                max_length=128,
                padding=True,
            )
            encoded = {kunci: nilai.to(perangkat) for kunci, nilai in encoded.items()}
            with torch.inference_mode():
                logits = model(**encoded).logits
                indeks = logits.argmax(dim=-1).detach().cpu().tolist()

            for posisi, nomor_label in enumerate(indeks):
                if not batch[posisi]:
                    hasil.append("neutral")
                    continue
                label_mentah = id2label.get(
                    nomor_label,
                    id2label.get(str(nomor_label), f"LABEL_{nomor_label}"),
                )
                label_ui = _normalisasi_label_sentimen(label_mentah)
                hasil.append(_LABEL_SENTIMEN_INGGRIS.get(label_ui, "neutral"))
        return hasil
    except Exception as exc:
        raise RuntimeError(f"Klasifikasi sentimen upload gagal: {exc}") from exc


def _siapkan_hasil_analisis_upload(
    data: pd.DataFrame,
    is_relevant: bool,
    signature_file: str,
) -> pd.DataFrame:
    """Siapkan DataFrame hasil Fase 18 dan simpan state deteksi untuk file aktif."""
    try:
        if data is None or data.empty:
            raise ValueError("Dataset upload kosong dan tidak dapat dianalisis.")

        hasil = data.copy()
        kolom_teks = _deteksi_kolom_teks_upload(hasil)
        platform_terdeteksi, kolom_platform = _deteksi_platform_upload(hasil)
        st.session_state[STATE_DETECTED_TEXT_COL] = kolom_teks
        st.session_state[STATE_DETECTED_PLATFORM] = platform_terdeteksi
        st.session_state[STATE_UPLOAD_PLATFORM_COL] = kolom_platform

        if is_relevant:
            if not kolom_teks or kolom_teks not in hasil.columns:
                raise ValueError(
                    "Kolom teks tidak terdeteksi. Pastikan file memiliki kolom komentar, "
                    "content, text, caption, atau kolom teks sejenis."
                )

            kolom_sentimen = _deteksi_kolom_sentimen_upload(hasil)
            if kolom_sentimen:
                label_ui = hasil[kolom_sentimen].map(_normalisasi_label_sentimen)
                predicted = label_ui.map(_LABEL_SENTIMEN_INGGRIS).fillna("")
            else:
                predicted = pd.Series("", index=hasil.index, dtype="object")

            mask_kosong = predicted.astype(str).str.strip().eq("")
            if mask_kosong.any():
                teks_prediksi = (
                    hasil.loc[mask_kosong, kolom_teks]
                    .fillna("")
                    .astype(str)
                    .tolist()
                )
                predicted.loc[mask_kosong] = _prediksi_sentimen_batch_upload(teks_prediksi)

            hasil["predicted_sentiment"] = predicted.replace("", "neutral")
            hasil["topik"] = [
                classify_topic(teks, sentimen)
                for teks, sentimen in zip(
                    hasil[kolom_teks].fillna("").astype(str).tolist(),
                    hasil["predicted_sentiment"].fillna("neutral").astype(str).tolist(),
                )
            ]

        st.session_state[STATE_UPLOAD_OUTPUT_DF] = hasil.copy()
        st.session_state[STATE_UPLOAD_OUTPUT_SIGNATURE] = str(signature_file)
        st.session_state.pop(STATE_UPLOAD_OUTPUT_ERROR, None)
        return hasil
    except Exception:
        st.session_state.pop(STATE_UPLOAD_OUTPUT_DF, None)
        st.session_state.pop(STATE_UPLOAD_OUTPUT_SIGNATURE, None)
        raise


def _konfigurasi_chart_upload(figur: go.Figure) -> go.Figure:
    """Terapkan latar transparan tanpa menyentuh CSS halaman Dataset."""
    figur.update_layout(
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font={"color": "#FFFFFF"},
        margin={"l": 20, "r": 20, "t": 50, "b": 30},
    )
    return figur


def _render_wordcloud_upload(teks: pd.Series, max_words: int, colormap: str) -> None:
    """Render WordCloud upload menggunakan Matplotlib sesuai aturan proyek."""
    try:
        import matplotlib.pyplot as plt
        from wordcloud import WordCloud

        gabungan_teks = " ".join(
            teks.fillna("").astype(str).str.strip().loc[lambda nilai: nilai.ne("")].tolist()
        )
        if not gabungan_teks.strip():
            st.info("WordCloud belum dapat dibuat karena kolom teks tidak memiliki isi.")
            return

        wordcloud = WordCloud(
            width=1400,
            height=600,
            background_color="#0D0D0D",
            max_words=max_words,
            colormap=colormap,
            collocations=False,
        ).generate(gabungan_teks)

        figur, axes = plt.subplots(figsize=(14, 6), facecolor="#0D0D0D")
        axes.imshow(wordcloud, interpolation="bilinear")
        axes.axis("off")
        figur.patch.set_facecolor("#0D0D0D")
        figur.tight_layout(pad=0)
        st.pyplot(figur, clear_figure=True, **_opsi_lebar_penuh(st.pyplot))
        plt.close(figur)
    except Exception as exc:
        LOGGER.exception("WordCloud upload gagal dibuat")
        st.error(f"WordCloud tidak dapat ditampilkan. Detail: {exc}")



def _render_css_hasil_upload() -> None:
    """Sisipkan CSS terisolasi untuk output analisis file upload."""
    st.markdown(
        """
        <style>
            @keyframes datasetV18MetricEnter {
                from { opacity: 0; transform: translateY(14px) scale(0.98); }
                to { opacity: 1; transform: translateY(0) scale(1); }
            }

            @keyframes datasetV18IconFloat {
                0%, 100% { transform: translateY(0) rotate(0deg); }
                50% { transform: translateY(-4px) rotate(-4deg); }
            }

            @keyframes datasetV18BarLoad {
                from { transform: scaleX(0); }
                to { transform: scaleX(1); }
            }

            @keyframes datasetV18Shimmer {
                0% { transform: translateX(-150%) skewX(-18deg); }
                100% { transform: translateX(420%) skewX(-18deg); }
            }

            .dataset-v18-output-shell {
                margin: 0.1rem 0 1.35rem;
            }

            .dataset-v18-output-heading {
                align-items: center;
                display: flex;
                gap: 0.82rem;
                margin: 0.15rem 0 1.05rem;
            }

            .dataset-v18-output-heading-icon {
                align-items: center;
                animation: datasetV18IconFloat 3.4s ease-in-out infinite;
                background: linear-gradient(135deg, rgba(229,57,53,0.22), rgba(142,90,247,0.20));
                border: 1px solid rgba(229,57,53,0.34);
                border-radius: 13px;
                box-shadow: 0 10px 24px rgba(229,57,53,0.10);
                display: flex;
                font-size: 1.1rem;
                height: 44px;
                justify-content: center;
                width: 44px;
            }

            .dataset-v18-output-heading-title {
                color: #FFFFFF;
                font-family: 'Plus Jakarta Sans', 'Inter', sans-serif;
                font-size: clamp(1.45rem, 2.2vw, 2rem);
                font-weight: 800;
                letter-spacing: -0.035em;
                line-height: 1.1;
            }

            .dataset-v18-output-heading-note {
                color: #777D89;
                font-size: 0.73rem;
                margin-top: 0.18rem;
            }

            .dataset-v18-metric-card {
                --v18-accent: #E53935;
                --v18-accent-soft: rgba(229,57,53,0.16);
                --v18-accent-border: rgba(229,57,53,0.34);
                --v18-accent-glow: rgba(229,57,53,0.15);
                animation: datasetV18MetricEnter 0.52s cubic-bezier(.2,.75,.25,1) both;
                background:
                    radial-gradient(circle at 96% 2%, var(--v18-accent-soft), transparent 43%),
                    linear-gradient(145deg, #171C26 0%, #121721 58%, #10141C 100%);
                border: 1px solid rgba(255,255,255,0.075);
                border-radius: 18px;
                box-shadow: 0 16px 34px rgba(0,0,0,0.24);
                cursor: pointer;
                min-height: 154px;
                overflow: hidden;
                padding: 1.05rem 1.12rem 0.95rem;
                position: relative;
                transition: transform 0.25s ease, border-color 0.25s ease,
                    box-shadow 0.25s ease, background 0.25s ease;
            }

            .dataset-v18-metric-card::before {
                background: linear-gradient(90deg, transparent, rgba(255,255,255,0.16), transparent);
                content: '';
                height: 120%;
                left: -42%;
                pointer-events: none;
                position: absolute;
                top: -10%;
                transform: translateX(-150%) skewX(-18deg);
                width: 24%;
            }

            .dataset-v18-metric-card::after {
                background: linear-gradient(90deg, var(--v18-accent), transparent);
                bottom: 0;
                content: '';
                height: 3px;
                left: 0;
                opacity: 0.92;
                position: absolute;
                width: 58%;
            }

            .dataset-v18-metric-card:hover,
            .dataset-v18-metric-card:focus {
                border-color: var(--v18-accent-border);
                box-shadow: 0 22px 45px rgba(0,0,0,0.34), 0 0 30px var(--v18-accent-glow);
                outline: none;
                transform: translateY(-6px) scale(1.012);
            }

            .dataset-v18-metric-card:hover::before,
            .dataset-v18-metric-card:focus::before {
                animation: datasetV18Shimmer 0.95s ease;
            }

            .dataset-v18-metric-card:active {
                transform: translateY(-2px) scale(0.988);
            }

            .dataset-v18-metric-top {
                align-items: center;
                display: flex;
                justify-content: space-between;
                margin-bottom: 0.72rem;
            }

            .dataset-v18-metric-label {
                color: #A9B0BE;
                font-size: 0.82rem;
                font-weight: 700;
                letter-spacing: 0.01em;
            }

            .dataset-v18-metric-icon {
                align-items: center;
                background: var(--v18-accent-soft);
                border: 1px solid var(--v18-accent-border);
                border-radius: 11px;
                display: flex;
                font-size: 1rem;
                height: 38px;
                justify-content: center;
                transition: transform 0.25s ease, box-shadow 0.25s ease;
                width: 38px;
            }

            .dataset-v18-metric-card:hover .dataset-v18-metric-icon,
            .dataset-v18-metric-card:focus .dataset-v18-metric-icon {
                box-shadow: 0 0 20px var(--v18-accent-glow);
                transform: rotate(-8deg) scale(1.12);
            }

            .dataset-v18-metric-value {
                color: #F8FAFF;
                font-family: 'Plus Jakarta Sans', 'Inter', sans-serif;
                font-size: clamp(2rem, 3.4vw, 2.7rem);
                font-weight: 800;
                letter-spacing: -0.055em;
                line-height: 1;
                text-shadow: 0 0 20px var(--v18-accent-glow);
            }

            .dataset-v18-metric-note {
                color: #737A87;
                font-size: 0.68rem;
                margin-top: 0.42rem;
            }

            .dataset-v18-metric-progress {
                background: rgba(255,255,255,0.065);
                border-radius: 999px;
                height: 4px;
                margin-top: 0.78rem;
                overflow: hidden;
            }

            .dataset-v18-metric-progress > span {
                animation: datasetV18BarLoad 0.9s 0.2s cubic-bezier(.2,.75,.25,1) both;
                background: linear-gradient(90deg, var(--v18-accent), rgba(255,255,255,0.72));
                border-radius: inherit;
                display: block;
                height: 100%;
                min-width: 4px;
                transform-origin: left center;
                transition: filter 0.22s ease, box-shadow 0.22s ease;
            }

            .dataset-v18-metric-card:hover .dataset-v18-metric-progress > span,
            .dataset-v18-metric-card:focus .dataset-v18-metric-progress > span {
                box-shadow: 0 0 14px var(--v18-accent);
                filter: brightness(1.18);
            }

            .dataset-v18-metric-total {
                --v18-accent: #8E72FF;
                --v18-accent-soft: rgba(142,114,255,0.17);
                --v18-accent-border: rgba(142,114,255,0.38);
                --v18-accent-glow: rgba(142,114,255,0.17);
                animation-delay: 0.02s;
            }

            .dataset-v18-metric-positive {
                --v18-accent: #56D364;
                --v18-accent-soft: rgba(76,175,80,0.16);
                --v18-accent-border: rgba(76,175,80,0.38);
                --v18-accent-glow: rgba(76,175,80,0.17);
                animation-delay: 0.08s;
            }

            .dataset-v18-metric-neutral {
                --v18-accent: #FFB33E;
                --v18-accent-soft: rgba(255,152,0,0.16);
                --v18-accent-border: rgba(255,152,0,0.38);
                --v18-accent-glow: rgba(255,152,0,0.17);
                animation-delay: 0.14s;
            }

            .dataset-v18-metric-negative {
                --v18-accent: #FF5C57;
                --v18-accent-soft: rgba(244,67,54,0.16);
                --v18-accent-border: rgba(244,67,54,0.38);
                --v18-accent-glow: rgba(244,67,54,0.17);
                animation-delay: 0.20s;
            }

            .dataset-v18-platform-shell {
                animation: datasetV18MetricEnter 0.56s 0.18s cubic-bezier(.2,.75,.25,1) both;
                background:
                    radial-gradient(circle at 98% 0%, rgba(229,57,53,0.09), transparent 36%),
                    linear-gradient(145deg, rgba(27,29,36,0.96), rgba(16,18,23,0.96));
                border: 1px solid rgba(255,255,255,0.075);
                border-radius: 18px;
                box-shadow: 0 18px 38px rgba(0,0,0,0.25);
                margin: 1.25rem 0 1.45rem;
                overflow: hidden;
                padding: 1.15rem;
                position: relative;
            }

            .dataset-v18-platform-shell::before {
                background: linear-gradient(90deg, #E53935, #8E72FF, #C13584);
                content: '';
                height: 3px;
                left: 0;
                position: absolute;
                right: 0;
                top: 0;
            }

            .dataset-v18-platform-header {
                align-items: center;
                display: flex;
                gap: 0.72rem;
                justify-content: space-between;
                margin-bottom: 0.95rem;
            }

            .dataset-v18-platform-title-wrap {
                align-items: center;
                display: flex;
                gap: 0.68rem;
            }

            .dataset-v18-platform-title-icon {
                align-items: center;
                background: rgba(229,57,53,0.13);
                border: 1px solid rgba(229,57,53,0.28);
                border-radius: 11px;
                display: flex;
                height: 38px;
                justify-content: center;
                transition: transform 0.24s ease;
                width: 38px;
            }

            .dataset-v18-platform-shell:hover .dataset-v18-platform-title-icon {
                transform: rotate(-8deg) scale(1.08);
            }

            .dataset-v18-platform-title {
                color: #F7F8FC;
                font-family: 'Plus Jakarta Sans', 'Inter', sans-serif;
                font-size: 1.05rem;
                font-weight: 800;
                letter-spacing: -0.025em;
            }

            .dataset-v18-platform-subtitle {
                color: #777D89;
                font-size: 0.68rem;
                margin-top: 0.12rem;
            }

            .dataset-v18-platform-badge {
                background: rgba(142,114,255,0.12);
                border: 1px solid rgba(142,114,255,0.28);
                border-radius: 999px;
                color: #C4B6FF;
                font-size: 0.66rem;
                font-weight: 800;
                padding: 0.38rem 0.62rem;
                white-space: nowrap;
            }

            .dataset-v18-platform-grid {
                display: grid;
                gap: 0.72rem;
                grid-template-columns: repeat(auto-fit, minmax(230px, 1fr));
            }

            .dataset-v18-platform-card {
                --platform-accent: #E53935;
                --platform-soft: rgba(229,57,53,0.14);
                --platform-border: rgba(229,57,53,0.30);
                background: linear-gradient(145deg, rgba(30,33,41,0.94), rgba(20,22,28,0.94));
                border: 1px solid rgba(255,255,255,0.07);
                border-radius: 14px;
                cursor: pointer;
                padding: 0.88rem 0.92rem;
                position: relative;
                transition: transform 0.23s ease, border-color 0.23s ease,
                    box-shadow 0.23s ease, background 0.23s ease;
            }

            .dataset-v18-platform-card:hover,
            .dataset-v18-platform-card:focus {
                background:
                    radial-gradient(circle at 100% 0%, var(--platform-soft), transparent 48%),
                    linear-gradient(145deg, rgba(32,35,44,0.98), rgba(20,22,28,0.98));
                border-color: var(--platform-border);
                box-shadow: 0 14px 28px rgba(0,0,0,0.26), 0 0 22px var(--platform-soft);
                outline: none;
                transform: translateY(-4px);
            }

            .dataset-v18-platform-card:active {
                transform: translateY(-1px) scale(0.985);
            }

            .dataset-v18-platform-row {
                align-items: center;
                display: flex;
                justify-content: space-between;
            }

            .dataset-v18-platform-identity {
                align-items: center;
                display: flex;
                gap: 0.65rem;
            }

            .dataset-v18-platform-icon {
                align-items: center;
                background: var(--platform-soft);
                border: 1px solid var(--platform-border);
                border-radius: 10px;
                color: var(--platform-accent);
                display: flex;
                font-size: 0.95rem;
                font-weight: 900;
                height: 36px;
                justify-content: center;
                transition: transform 0.23s ease;
                width: 36px;
            }

            .dataset-v18-platform-card:hover .dataset-v18-platform-icon,
            .dataset-v18-platform-card:focus .dataset-v18-platform-icon {
                transform: rotate(-7deg) scale(1.10);
            }

            .dataset-v18-platform-name {
                color: #ECEEF5;
                font-size: 0.82rem;
                font-weight: 800;
            }

            .dataset-v18-platform-share {
                color: #777D89;
                font-size: 0.64rem;
                margin-top: 0.12rem;
            }

            .dataset-v18-platform-count {
                color: var(--platform-accent);
                font-family: 'Plus Jakarta Sans', 'Inter', sans-serif;
                font-size: 1.25rem;
                font-weight: 800;
                text-shadow: 0 0 16px var(--platform-soft);
            }

            .dataset-v18-platform-track {
                background: rgba(255,255,255,0.065);
                border-radius: 999px;
                height: 6px;
                margin-top: 0.78rem;
                overflow: hidden;
            }

            .dataset-v18-platform-fill {
                animation: datasetV18BarLoad 0.9s 0.32s cubic-bezier(.2,.75,.25,1) both;
                background: linear-gradient(90deg, var(--platform-accent), rgba(255,255,255,0.72));
                border-radius: inherit;
                display: block;
                height: 100%;
                min-width: 5px;
                transform-origin: left center;
                transition: filter 0.22s ease, box-shadow 0.22s ease;
            }

            .dataset-v18-platform-card:hover .dataset-v18-platform-fill,
            .dataset-v18-platform-card:focus .dataset-v18-platform-fill {
                box-shadow: 0 0 14px var(--platform-accent);
                filter: brightness(1.18);
            }



            @keyframes datasetV18ChartEnter {
                from { opacity: 0; transform: translateY(16px) scale(0.985); }
                to { opacity: 1; transform: translateY(0) scale(1); }
            }

            @keyframes datasetV18ChartGlow {
                0%, 100% { opacity: 0.42; transform: scale(0.92); }
                50% { opacity: 0.95; transform: scale(1.08); }
            }

            .dataset-v18-sentiment-section {
                align-items: center;
                display: flex;
                gap: 0.78rem;
                justify-content: space-between;
                margin: 1.65rem 0 0.88rem;
            }

            .dataset-v18-sentiment-section-left {
                align-items: center;
                display: flex;
                gap: 0.72rem;
            }

            .dataset-v18-sentiment-section-icon {
                align-items: center;
                background: linear-gradient(135deg, rgba(229,57,53,0.20), rgba(142,114,255,0.18));
                border: 1px solid rgba(229,57,53,0.32);
                border-radius: 12px;
                box-shadow: 0 10px 24px rgba(229,57,53,0.11);
                display: flex;
                height: 40px;
                justify-content: center;
                transition: transform 0.25s ease, box-shadow 0.25s ease;
                width: 40px;
            }

            .dataset-v18-sentiment-section:hover .dataset-v18-sentiment-section-icon {
                box-shadow: 0 0 24px rgba(229,57,53,0.20);
                transform: rotate(-8deg) scale(1.08);
            }

            .dataset-v18-sentiment-section-title {
                color: #F7F8FC;
                font-family: 'Plus Jakarta Sans', 'Inter', sans-serif;
                font-size: 1.22rem;
                font-weight: 800;
                letter-spacing: -0.03em;
                line-height: 1.1;
            }

            .dataset-v18-sentiment-section-note {
                color: #777D89;
                font-size: 0.67rem;
                margin-top: 0.16rem;
            }

            .dataset-v18-sentiment-dominant {
                background: rgba(229,57,53,0.10);
                border: 1px solid rgba(229,57,53,0.24);
                border-radius: 999px;
                color: #FFAAA7;
                font-size: 0.66rem;
                font-weight: 800;
                padding: 0.42rem 0.68rem;
                white-space: nowrap;
            }

            .dataset-v18-chart-card-marker {
                display: none;
            }

            div[data-testid="stVerticalBlockBorderWrapper"]:has(.dataset-v18-chart-card-marker) {
                --v18-chart-accent: #8E72FF;
                --v18-chart-soft: rgba(142,114,255,0.14);
                animation: datasetV18ChartEnter 0.58s cubic-bezier(.2,.75,.25,1) both;
                background:
                    radial-gradient(circle at 100% 0%, var(--v18-chart-soft), transparent 42%),
                    linear-gradient(145deg, rgba(25,29,39,0.98), rgba(15,18,25,0.98));
                border: 1px solid rgba(255,255,255,0.08) !important;
                border-radius: 19px !important;
                box-shadow: 0 18px 38px rgba(0,0,0,0.28);
                overflow: hidden;
                position: relative;
                transition: transform 0.26s ease, border-color 0.26s ease,
                    box-shadow 0.26s ease, background 0.26s ease;
            }

            div[data-testid="stVerticalBlockBorderWrapper"]:has(.dataset-v18-chart-card-marker)::before {
                background: linear-gradient(90deg, var(--v18-chart-accent), transparent 78%);
                content: '';
                height: 3px;
                left: 0;
                position: absolute;
                right: 0;
                top: 0;
                z-index: 2;
            }

            div[data-testid="stVerticalBlockBorderWrapper"]:has(.dataset-v18-chart-pie-marker) {
                --v18-chart-accent: #8E72FF;
                --v18-chart-soft: rgba(142,114,255,0.16);
                animation-delay: 0.05s;
            }

            div[data-testid="stVerticalBlockBorderWrapper"]:has(.dataset-v18-chart-bar-marker) {
                --v18-chart-accent: #E53935;
                --v18-chart-soft: rgba(229,57,53,0.15);
                animation-delay: 0.12s;
            }

            div[data-testid="stVerticalBlockBorderWrapper"]:has(.dataset-v18-chart-card-marker):hover {
                border-color: rgba(255,255,255,0.16) !important;
                box-shadow: 0 24px 48px rgba(0,0,0,0.36), 0 0 30px var(--v18-chart-soft);
                transform: translateY(-5px) scale(1.006);
            }

            div[data-testid="stVerticalBlockBorderWrapper"]:has(.dataset-v18-chart-pie-marker):hover {
                border-color: rgba(142,114,255,0.46) !important;
            }

            div[data-testid="stVerticalBlockBorderWrapper"]:has(.dataset-v18-chart-bar-marker):hover {
                border-color: rgba(229,57,53,0.46) !important;
            }

            .dataset-v18-chart-card-head {
                align-items: center;
                display: flex;
                gap: 0.64rem;
                justify-content: space-between;
                margin: 0.08rem 0 -0.15rem;
                padding: 0.16rem 0.2rem 0;
            }

            .dataset-v18-chart-card-title-wrap {
                align-items: center;
                display: flex;
                gap: 0.58rem;
            }

            .dataset-v18-chart-card-icon {
                align-items: center;
                background: var(--v18-chart-soft);
                border: 1px solid rgba(255,255,255,0.12);
                border-radius: 10px;
                color: var(--v18-chart-accent);
                display: flex;
                font-size: 0.9rem;
                font-weight: 900;
                height: 34px;
                justify-content: center;
                transition: transform 0.24s ease, box-shadow 0.24s ease;
                width: 34px;
            }

            div[data-testid="stVerticalBlockBorderWrapper"]:has(.dataset-v18-chart-card-marker):hover
            .dataset-v18-chart-card-icon {
                box-shadow: 0 0 18px var(--v18-chart-soft);
                transform: rotate(-8deg) scale(1.10);
            }

            .dataset-v18-chart-card-title {
                color: #F3F5FA;
                font-size: 0.88rem;
                font-weight: 800;
                letter-spacing: -0.015em;
            }

            .dataset-v18-chart-card-subtitle {
                color: #727986;
                font-size: 0.61rem;
                margin-top: 0.1rem;
            }

            .dataset-v18-chart-card-badge {
                align-items: center;
                background: var(--v18-chart-soft);
                border: 1px solid rgba(255,255,255,0.11);
                border-radius: 999px;
                color: #D9DDE7;
                display: inline-flex;
                font-size: 0.59rem;
                font-weight: 800;
                gap: 0.36rem;
                padding: 0.34rem 0.5rem;
                white-space: nowrap;
            }

            .dataset-v18-chart-card-badge::before {
                animation: datasetV18ChartGlow 1.8s ease-in-out infinite;
                background: var(--v18-chart-accent);
                border-radius: 50%;
                box-shadow: 0 0 10px var(--v18-chart-accent);
                content: '';
                height: 6px;
                width: 6px;
            }

            .dataset-v18-chart-card-hint {
                align-items: center;
                color: #686F7B;
                display: flex;
                font-size: 0.59rem;
                gap: 0.38rem;
                margin: -0.38rem 0 0.12rem;
                padding: 0 0.22rem;
            }

            .dataset-v18-chart-card-hint strong {
                color: #969EAD;
                font-weight: 700;
            }


            @media (max-width: 760px) {
                .dataset-v18-metric-card { min-height: 140px; }
                .dataset-v18-platform-header { align-items: flex-start; }
                .dataset-v18-platform-badge { display: none; }
                .dataset-v18-sentiment-section { align-items: flex-start; }
                .dataset-v18-sentiment-dominant { display: none; }
                .dataset-v18-chart-card-badge { display: none; }
            }

            @media (prefers-reduced-motion: reduce) {
                .dataset-v18-output-heading-icon,
                .dataset-v18-metric-card,
                .dataset-v18-metric-progress > span,
                .dataset-v18-platform-shell,
                .dataset-v18-platform-fill,
                div[data-testid="stVerticalBlockBorderWrapper"]:has(.dataset-v18-chart-card-marker),
                .dataset-v18-chart-card-badge::before {
                    animation: none !important;
                }
            }
        </style>
        """,
        unsafe_allow_html=True,
    )


def _render_metric_hasil_upload(
    label: str,
    nilai: str,
    catatan: str,
    ikon: str,
    kelas: str,
    persentase_bar: float,
) -> None:
    """Render kartu metrik upload yang berwarna dan interaktif."""
    lebar_bar = max(0.0, min(float(persentase_bar), 100.0))
    st.markdown(
        f"""
        <div class="dataset-v18-metric-card {escape(kelas)}" tabindex="0">
            <div class="dataset-v18-metric-top">
                <div class="dataset-v18-metric-label">{escape(label)}</div>
                <div class="dataset-v18-metric-icon">{escape(ikon)}</div>
            </div>
            <div class="dataset-v18-metric-value">{escape(nilai)}</div>
            <div class="dataset-v18-metric-note">{escape(catatan)}</div>
            <div class="dataset-v18-metric-progress" aria-hidden="true">
                <span style="width: {lebar_bar:.1f}%"></span>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def _render_distribusi_platform_upload(distribusi_platform: pd.DataFrame) -> None:
    """Render distribusi platform sebagai kartu dengan bar animasi."""
    try:
        if distribusi_platform is None or distribusi_platform.empty:
            st.info("Distribusi platform belum tersedia pada file upload ini.")
            return

        total_platform = max(int(distribusi_platform["Jumlah Data"].sum()), 1)
        konfigurasi_platform = {
            "Twitter": ("𝕏", "#E53935", "rgba(229,57,53,0.14)", "rgba(229,57,53,0.32)"),
            "Instagram": ("◎", "#D85DA8", "rgba(193,53,132,0.15)", "rgba(193,53,132,0.34)"),
            "TikTok": ("♪", "#25F4EE", "rgba(37,244,238,0.12)", "rgba(37,244,238,0.30)"),
            "Tidak diketahui": ("◆", "#9AA0AA", "rgba(154,160,170,0.12)", "rgba(154,160,170,0.28)"),
        }

        kartu_html: list[str] = []
        for baris in distribusi_platform.itertuples(index=False):
            platform = str(getattr(baris, "Platform", "Tidak diketahui"))
            jumlah_data = int(getattr(baris, "_1", 0))
            persentase = jumlah_data / total_platform * 100
            ikon, warna, warna_soft, warna_border = konfigurasi_platform.get(
                platform,
                konfigurasi_platform["Tidak diketahui"],
            )
            kartu_html.append(
                f"""
                <div class="dataset-v18-platform-card" tabindex="0"
                    style="--platform-accent:{warna};--platform-soft:{warna_soft};--platform-border:{warna_border};">
                    <div class="dataset-v18-platform-row">
                        <div class="dataset-v18-platform-identity">
                            <div class="dataset-v18-platform-icon">{escape(ikon)}</div>
                            <div>
                                <div class="dataset-v18-platform-name">{escape(platform)}</div>
                                <div class="dataset-v18-platform-share">{persentase:.1f}% dari seluruh data</div>
                            </div>
                        </div>
                        <div class="dataset-v18-platform-count">{_format_angka(jumlah_data)}</div>
                    </div>
                    <div class="dataset-v18-platform-track" aria-hidden="true">
                        <span class="dataset-v18-platform-fill" style="width:{persentase:.1f}%"></span>
                    </div>
                </div>
                """
            )

        kartu_html_render = "".join(kartu_html).replace("\n", "")

        st.markdown(
            f"""
            <div class="dataset-v18-platform-shell">
                <div class="dataset-v18-platform-header">
                    <div class="dataset-v18-platform-title-wrap">
                        <div class="dataset-v18-platform-title-icon">◫</div>
                        <div>
                            <div class="dataset-v18-platform-title">Distribusi Platform</div>
                            <div class="dataset-v18-platform-subtitle">
                                Arahkan kursor ke kartu untuk melihat efek interaktif.
                            </div>
                        </div>
                    </div>
                    <div class="dataset-v18-platform-badge">
                        {len(distribusi_platform)} platform terdeteksi
                    </div>
                </div>
                <div class="dataset-v18-platform-grid">
                    {kartu_html_render}
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )
    except Exception as exc:
        LOGGER.exception("Distribusi platform upload gagal dirender")
        st.error(f"Distribusi platform tidak dapat ditampilkan. Detail: {exc}")



def _render_header_kartu_chart_upload(
    judul: str,
    subjudul: str,
    ikon: str,
    badge: str,
    kelas_marker: str,
) -> None:
    """Render header kecil untuk kartu grafik sentimen upload."""
    st.markdown(
        f"""
        <span class="dataset-v18-chart-card-marker {escape(kelas_marker)}"></span>
        <div class="dataset-v18-chart-card-head">
            <div class="dataset-v18-chart-card-title-wrap">
                <div class="dataset-v18-chart-card-icon">{escape(ikon)}</div>
                <div>
                    <div class="dataset-v18-chart-card-title">{escape(judul)}</div>
                    <div class="dataset-v18-chart-card-subtitle">{escape(subjudul)}</div>
                </div>
            </div>
            <div class="dataset-v18-chart-card-badge">{escape(badge)}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def _render_hint_chart_upload(teks: str) -> None:
    """Render petunjuk interaksi ringkas di bawah grafik."""
    st.markdown(
        f"""
        <div class="dataset-v18-chart-card-hint">
            <span>↗</span>
            <span>{escape(teks)}</span>
        </div>
        """,
        unsafe_allow_html=True,
    )


def _render_hasil_relevan_upload(
    data: pd.DataFrame,
    kolom_teks: str,
    kolom_platform: str | None,
) -> None:
    """Render analisis lengkap untuk upload yang relevan dengan Telkom Group."""
    try:
        if "predicted_sentiment" not in data.columns:
            st.error("Kolom predicted_sentiment belum tersedia pada hasil analisis.")
            return

        label_ui = data["predicted_sentiment"].map(_normalisasi_label_sentimen)
        jumlah = label_ui.value_counts().reindex(["Positif", "Netral", "Negatif"], fill_value=0)
        total = max(int(len(data)), 1)

        _render_css_hasil_upload()
        st.markdown(
            """
            <div class="dataset-v18-output-shell">
                <div class="dataset-v18-output-heading">
                    <div class="dataset-v18-output-heading-icon">✦</div>
                    <div>
                        <div class="dataset-v18-output-heading-title">Hasil Analisis Data Upload</div>
                        <div class="dataset-v18-output-heading-note">
                            Ringkasan sentimen dan sebaran sumber data yang berhasil dianalisis.
                        </div>
                    </div>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        persentase_positif = jumlah["Positif"] / total * 100
        persentase_netral = jumlah["Netral"] / total * 100
        persentase_negatif = jumlah["Negatif"] / total * 100
        metrik = st.columns(4, gap="small")
        konfigurasi_metrik = (
            (
                "Total Data",
                _format_angka(len(data)),
                "Jumlah baris yang dianalisis",
                "▦",
                "dataset-v18-metric-total",
                100.0,
            ),
            (
                "Positif",
                f"{persentase_positif:.1f}%",
                "Proporsi sentimen positif",
                "▲",
                "dataset-v18-metric-positive",
                persentase_positif,
            ),
            (
                "Netral",
                f"{persentase_netral:.1f}%",
                "Proporsi sentimen netral",
                "●",
                "dataset-v18-metric-neutral",
                persentase_netral,
            ),
            (
                "Negatif",
                f"{persentase_negatif:.1f}%",
                "Proporsi sentimen negatif",
                "▼",
                "dataset-v18-metric-negative",
                persentase_negatif,
            ),
        )
        for kolom, isi_metrik in zip(metrik, konfigurasi_metrik):
            with kolom:
                _render_metric_hasil_upload(*isi_metrik)

        if kolom_platform and kolom_platform in data.columns:
            distribusi_platform = (
                data[kolom_platform]
                .fillna("Tidak diketahui")
                .map(_normalisasi_platform_upload)
                .replace("", "Tidak diketahui")
                .value_counts()
                .rename_axis("Platform")
                .reset_index(name="Jumlah Data")
            )
            _render_distribusi_platform_upload(distribusi_platform)

        sentimen_dominan = str(jumlah.idxmax())
        persentase_dominan = float(jumlah.max() / total * 100)
        st.markdown(
            f"""
            <div class="dataset-v18-sentiment-section">
                <div class="dataset-v18-sentiment-section-left">
                    <div class="dataset-v18-sentiment-section-icon">◔</div>
                    <div>
                        <div class="dataset-v18-sentiment-section-title">Distribusi Sentimen</div>
                        <div class="dataset-v18-sentiment-section-note">
                            Jelajahi komposisi sentimen melalui hover, legenda, dan tombol tampilan.
                        </div>
                    </div>
                </div>
                <div class="dataset-v18-sentiment-dominant">
                    Dominan: {escape(sentimen_dominan)} · {persentase_dominan:.1f}%
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        label_sentimen = jumlah.index.tolist()
        nilai_sentimen = jumlah.values.tolist()
        warna_sentimen = [
            WARNA_SENTIMEN["Positif"],
            WARNA_SENTIMEN["Netral"],
            WARNA_SENTIMEN["Negatif"],
        ]
        persentase_sentimen = [float(nilai / total * 100) for nilai in nilai_sentimen]
        data_hover_bar = [
            [int(nilai), float(persen)]
            for nilai, persen in zip(nilai_sentimen, persentase_sentimen)
        ]

        chart_kiri, chart_kanan = st.columns(2, gap="medium")
        with chart_kiri:
            with st.container(border=True):
                _render_header_kartu_chart_upload(
                    judul="Komposisi Sentimen",
                    subjudul="Donut interaktif berdasarkan proporsi data",
                    ikon="◉",
                    badge=f"{_format_angka(total)} komentar",
                    kelas_marker="dataset-v18-chart-pie-marker",
                )
                figur_pie = go.Figure(
                    data=[
                        go.Pie(
                            labels=label_sentimen,
                            values=nilai_sentimen,
                            customdata=nilai_sentimen,
                            marker={
                                "colors": warna_sentimen,
                                "line": {"color": "#111620", "width": 2},
                            },
                            hole=0.56,
                            pull=[0.018 if nilai > 0 else 0 for nilai in nilai_sentimen],
                            rotation=-90,
                            sort=False,
                            direction="clockwise",
                            textinfo="none",
                            texttemplate="%{label}<br><b>%{percent}</b>",
                            textfont={"color": "#F8FAFF", "size": 13},
                            hovertemplate=(
                                "<b>%{label}</b><br>"
                                "Jumlah: %{value:,}<br>"
                                "Persentase: %{percent}<extra></extra>"
                            ),
                        )
                    ]
                )
                figur_pie.update_layout(
                    height=430,
                    showlegend=True,
                    legend={
                        "orientation": "h",
                        "x": 0.5,
                        "xanchor": "center",
                        "y": -0.04,
                        "yanchor": "top",
                        "font": {"color": "#CDD2DE", "size": 11},
                        "itemclick": "toggle",
                        "itemdoubleclick": "toggleothers",
                    },
                    annotations=[
                        {
                            "text": (
                                f"<span style='font-size:12px;color:#8B93A2'>TOTAL</span><br>"
                                f"<b style='font-size:28px;color:#FFFFFF'>{_format_angka(total)}</b>"
                            ),
                            "x": 0.5,
                            "y": 0.5,
                            "showarrow": False,
                            "align": "center",
                        }
                    ],
                    updatemenus=[
                        {
                            "type": "buttons",
                            "direction": "right",
                            "x": 0.02,
                            "xanchor": "left",
                            "y": 1.11,
                            "yanchor": "top",
                            "showactive": True,
                            "bgcolor": "rgba(255,255,255,0.05)",
                            "bordercolor": "rgba(255,255,255,0.10)",
                            "font": {"color": "#D7DBE5", "size": 10},
                            "buttons": [
                                {
                                    "label": "Persentase",
                                    "method": "restyle",
                                    "args": [{"texttemplate": "%{label}<br><b>%{percent}</b>"}],
                                },
                                {
                                    "label": "Jumlah",
                                    "method": "restyle",
                                    "args": [{"texttemplate": "%{label}<br><b>%{value}</b>"}],
                                },
                            ],
                        }
                    ],
                    hoverlabel={
                        "bgcolor": "#151A24",
                        "bordercolor": "rgba(255,255,255,0.14)",
                        "font": {"color": "#FFFFFF", "size": 12},
                    },
                    transition={"duration": 450, "easing": "cubic-in-out"},
                    uniformtext={"minsize": 10, "mode": "hide"},
                    margin={"l": 18, "r": 18, "t": 82, "b": 54},
                )
                _konfigurasi_chart_upload(figur_pie)
                figur_pie.update_layout(margin={"l": 18, "r": 18, "t": 82, "b": 54})
                st.plotly_chart(
                    figur_pie,
                    config={
                        "displayModeBar": False,
                        "displaylogo": False,
                        "responsive": True,
                    },
                    **_opsi_lebar_penuh(st.plotly_chart),
                )
                _render_hint_chart_upload(
                    "Arahkan kursor ke irisan atau klik legenda untuk menyaring sentimen."
                )

        with chart_kanan:
            with st.container(border=True):
                _render_header_kartu_chart_upload(
                    judul="Perbandingan Sentimen",
                    subjudul="Bar horizontal dengan mode jumlah dan persentase",
                    ikon="▤",
                    badge="Klik mode tampilan",
                    kelas_marker="dataset-v18-chart-bar-marker",
                )
                nilai_maksimum = max(max(nilai_sentimen), 1)
                figur_bar = go.Figure(
                    data=[
                        go.Bar(
                            x=nilai_sentimen,
                            y=label_sentimen,
                            orientation="h",
                            marker={
                                "color": warna_sentimen,
                                "line": {"color": "rgba(255,255,255,0.16)", "width": 1},
                            },
                            width=0.56,
                            customdata=data_hover_bar,
                            text=[_format_angka(nilai) for nilai in nilai_sentimen],
                            textposition="inside",
                            insidetextanchor="end",
                            textfont={"color": "#FFFFFF", "size": 12},
                            hovertemplate=(
                                "<b>%{y}</b><br>"
                                "Jumlah: %{customdata[0]:,}<br>"
                                "Persentase: %{customdata[1]:.1f}%<extra></extra>"
                            ),
                            cliponaxis=False,
                        )
                    ]
                )
                figur_bar.update_xaxes(
                    title_text="Jumlah Komentar",
                    range=[0, nilai_maksimum * 1.18],
                    showgrid=True,
                    gridcolor="rgba(255,255,255,0.065)",
                    griddash="dot",
                    zeroline=False,
                    tickfont={"color": "#AEB5C2", "size": 10},
                    title_font={"color": "#D6DAE3", "size": 11},
                )
                figur_bar.update_yaxes(
                    title_text="",
                    showgrid=False,
                    tickfont={"color": "#E8EBF2", "size": 11},
                    automargin=True,
                )
                figur_bar.update_layout(
                    height=430,
                    bargap=0.38,
                    showlegend=False,
                    updatemenus=[
                        {
                            "type": "buttons",
                            "direction": "right",
                            "x": 0.02,
                            "xanchor": "left",
                            "y": 1.11,
                            "yanchor": "top",
                            "showactive": True,
                            "bgcolor": "rgba(255,255,255,0.05)",
                            "bordercolor": "rgba(255,255,255,0.10)",
                            "font": {"color": "#D7DBE5", "size": 10},
                            "buttons": [
                                {
                                    "label": "Jumlah",
                                    "method": "update",
                                    "args": [
                                        {
                                            "x": [nilai_sentimen],
                                            "text": [[_format_angka(nilai) for nilai in nilai_sentimen]],
                                        },
                                        {
                                            "xaxis": {
                                                "title": "Jumlah Komentar",
                                                "range": [0, nilai_maksimum * 1.18],
                                                "ticksuffix": "",
                                            }
                                        },
                                    ],
                                },
                                {
                                    "label": "Persentase",
                                    "method": "update",
                                    "args": [
                                        {
                                            "x": [persentase_sentimen],
                                            "text": [[f"{nilai:.1f}%" for nilai in persentase_sentimen]],
                                        },
                                        {
                                            "xaxis": {
                                                "title": "Persentase Data",
                                                "range": [0, 105],
                                                "ticksuffix": "%",
                                            }
                                        },
                                    ],
                                },
                            ],
                        }
                    ],
                    hoverlabel={
                        "bgcolor": "#151A24",
                        "bordercolor": "rgba(255,255,255,0.14)",
                        "font": {"color": "#FFFFFF", "size": 12},
                    },
                    transition={"duration": 520, "easing": "cubic-in-out"},
                    margin={"l": 18, "r": 22, "t": 82, "b": 48},
                )
                _konfigurasi_chart_upload(figur_bar)
                figur_bar.update_layout(margin={"l": 18, "r": 22, "t": 82, "b": 48})
                st.plotly_chart(
                    figur_bar,
                    config={
                        "displayModeBar": False,
                        "displaylogo": False,
                        "responsive": True,
                    },
                    **_opsi_lebar_penuh(st.plotly_chart),
                )
                _render_hint_chart_upload(
                    "Klik Jumlah atau Persentase. Bar akan berubah dengan transisi animasi."
                )

        st.markdown("#### WordCloud")
        with st.spinner("Memproses data..."):
            _render_wordcloud_upload(data[kolom_teks], max_words=150, colormap="Reds")

        st.markdown("#### Top 10 Topik")
        if "topik" not in data.columns:
            st.error("Kolom topik belum tersedia pada hasil analisis.")
        else:
            topik = data["topik"].fillna("Topik Lainnya").astype(str).value_counts().head(10)
            topik = topik.sort_values(ascending=True)
            figur_topik = go.Figure(
                data=[
                    go.Bar(
                        x=topik.values.tolist(),
                        y=topik.index.tolist(),
                        orientation="h",
                        marker={"color": "#E53935"},
                        text=topik.values.tolist(),
                        textposition="auto",
                    )
                ]
            )
            figur_topik.update_xaxes(title_text="Jumlah Komentar")
            figur_topik.update_yaxes(title_text="Nama Topik")
            _konfigurasi_chart_upload(figur_topik)
            st.plotly_chart(
                figur_topik,
                config={"displayModeBar": False, "responsive": True},
                **_opsi_lebar_penuh(st.plotly_chart),
            )

        st.download_button(
            "⬇️ Unduh Hasil Analisis (CSV)",
            data=data.to_csv(index=False).encode("utf-8-sig"),
            file_name="hasil_analisis_telkom.csv",
            mime="text/csv",
            key="dataset_v18_download_hasil_upload",
            **_opsi_lebar_penuh(st.download_button),
        )
    except Exception as exc:
        LOGGER.exception("Output analisis relevan gagal dirender")
        st.error(f"Hasil analisis data relevan tidak dapat ditampilkan. Detail: {exc}")


def _render_hasil_tidak_relevan_upload(
    data: pd.DataFrame,
    kolom_teks: str | None,
) -> None:
    """Render analisis terbatas untuk upload yang tidak relevan dengan Telkom Group."""
    try:
        st.warning(
            "⚠️ Data tidak dikenali sebagai data Telkom Group. "
            "Hasil analisis mungkin tidak relevan dengan konteks penelitian."
        )
        st.markdown("### Statistik Dasar")
        metrik_baris, metrik_kolom = st.columns(2, gap="medium")
        with metrik_baris:
            st.metric("Jumlah Baris", _format_angka(len(data)))
        with metrik_kolom:
            st.metric("Jumlah Kolom", _format_angka(len(data.columns)))

        tabel_unik = pd.DataFrame(
            {
                "Kolom": [str(kolom) for kolom in data.columns],
                "Tipe Data": [str(data[kolom].dtype) for kolom in data.columns],
                "Jumlah Nilai Unik": [
                    int(data[kolom].nunique(dropna=True)) for kolom in data.columns
                ],
                "Nilai Kosong": [int(data[kolom].isna().sum()) for kolom in data.columns],
            }
        )
        st.dataframe(tabel_unik, **_opsi_lebar_penuh(st.dataframe))

        kolom_teks_aktif = kolom_teks or _deteksi_kolom_teks_upload(data)
        if not kolom_teks_aktif or kolom_teks_aktif not in data.columns:
            st.error(
                "Kolom teks tidak ditemukan. Tambahkan kolom komentar, content, text, "
                "caption, atau kolom teks sejenis."
            )
            return

        st.markdown("#### WordCloud Tanpa Label Sentimen")
        with st.spinner("Memproses data..."):
            _render_wordcloud_upload(
                data[kolom_teks_aktif],
                max_words=100,
                colormap="Blues",
            )

        st.markdown("#### Distribusi Panjang Teks")
        panjang_teks = data[kolom_teks_aktif].fillna("").astype(str).str.len()
        figur_histogram = go.Figure(
            data=[
                go.Histogram(
                    x=panjang_teks.tolist(),
                    marker={"color": "#E53935"},
                )
            ]
        )
        figur_histogram.update_layout(title="Distribusi Panjang Teks")
        figur_histogram.update_xaxes(title_text="Panjang Teks (karakter)")
        figur_histogram.update_yaxes(title_text="Jumlah Data")
        _konfigurasi_chart_upload(figur_histogram)
        st.plotly_chart(
            figur_histogram,
            config={"displayModeBar": False, "responsive": True},
            **_opsi_lebar_penuh(st.plotly_chart),
        )
    except Exception as exc:
        LOGGER.exception("Output analisis tidak relevan gagal dirender")
        st.error(f"Analisis terbatas tidak dapat ditampilkan. Detail: {exc}")


def _render_output_analisis_upload(
    data_asli: pd.DataFrame,
    is_relevant: bool,
    signature_file: str,
) -> None:
    """Pilih Jalur A atau Jalur B berdasarkan state relevansi file aktif."""
    try:
        if data_asli is None or data_asli.empty:
            st.info("Silakan upload data terlebih dahulu di tab Upload.")
            return

        pesan_error = st.session_state.get(STATE_UPLOAD_OUTPUT_ERROR)
        if pesan_error:
            st.error(str(pesan_error))
            return

        signature_hasil = st.session_state.get(STATE_UPLOAD_OUTPUT_SIGNATURE)
        data_hasil = st.session_state.get(STATE_UPLOAD_OUTPUT_DF)
        if signature_hasil != signature_file or not isinstance(data_hasil, pd.DataFrame):
            st.info("Klik Analisis Ulang File Ini untuk menyiapkan output analisis Fase 18.")
            return

        kolom_teks = st.session_state.get(STATE_DETECTED_TEXT_COL)
        kolom_platform = st.session_state.get(STATE_UPLOAD_PLATFORM_COL)
        if is_relevant:
            if not kolom_teks or kolom_teks not in data_hasil.columns:
                st.error("Kolom teks hasil deteksi tidak tersedia pada dataset upload.")
                return
            _render_hasil_relevan_upload(data_hasil, str(kolom_teks), kolom_platform)
        else:
            _render_hasil_tidak_relevan_upload(data_hasil, kolom_teks)
    except Exception as exc:
        LOGGER.exception("Pemilihan jalur output analisis upload gagal")
        st.error(f"Output analisis upload tidak dapat ditampilkan. Detail: {exc}")
# === AKHIR TAHAP 4 FASE 18 ===

def _format_ukuran_file(jumlah_byte: int) -> str:
    """Format ukuran file upload menjadi teks ringkas yang mudah dibaca."""
    ukuran = max(0, int(jumlah_byte))
    satuan = ("B", "KB", "MB", "GB")
    nilai = float(ukuran)
    for nama_satuan in satuan:
        if nilai < 1024 or nama_satuan == satuan[-1]:
            if nama_satuan == "B":
                return f"{int(nilai):,} {nama_satuan}".replace(",", ".")
            return f"{nilai:.1f} {nama_satuan}".replace(".", ",")
        nilai /= 1024
    return f"{ukuran:,} B".replace(",", ".")


def _render_metric_upload(
    label: str,
    nilai: str,
    keterangan: str,
    ikon: str,
    kelas_warna: str,
) -> None:
    """Render metric card khusus upload agar ringkas dan terisolasi dari kartu lama."""
    st.markdown(
        f"""
        <div class="dataset-v16-metric-card {escape(kelas_warna)}">
            <div class="dataset-v16-metric-icon">{escape(ikon)}</div>
            <div>
                <div class="dataset-v16-metric-label">{escape(label)}</div>
                <div class="dataset-v16-metric-value">{escape(nilai)}</div>
                <div class="dataset-v16-metric-note">{escape(keterangan)}</div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def _buat_signature_file_upload_dari_bytes(
    nama_file: str,
    file_bytes: bytes,
) -> str:
    """Buat identitas stabil berdasarkan nama, ukuran, dan isi file upload."""
    ringkasan = hashlib.sha256(file_bytes).hexdigest()[:20]
    return f"{nama_file}|{len(file_bytes)}|{ringkasan}"


def _sinkronkan_file_upload_ke_state() -> None:
    """Simpan file uploader ke session state agar tetap tersedia setelah rerun."""
    file_upload = st.session_state.get(STATE_UPLOAD_WIDGET)
    if file_upload is None:
        file_sebelumnya_ada = bool(
            st.session_state.get(STATE_UPLOAD_CURRENT_SIGNATURE)
            or st.session_state.get(STATE_UPLOAD_RAW_BYTES)
        )
        if file_sebelumnya_ada:
            # Antrekan custom loading sebelum state file dibersihkan agar
            # proses penghapusan tidak memakai loading bawaan Streamlit.
            st.session_state[STATE_UPLOAD_LOADING_LABEL] = (
                "Menghapus file yang telah diunggah..."
            )
        _bersihkan_state_upload()
        return

    try:
        file_bytes = bytes(file_upload.getvalue())
        nama_file = str(getattr(file_upload, "name", "dataset"))
        ekstensi = Path(nama_file).suffix.lower()
        ukuran_file = int(getattr(file_upload, "size", 0) or len(file_bytes))

        st.session_state[STATE_UPLOAD_RAW_BYTES] = file_bytes
        st.session_state[STATE_UPLOAD_FILE_NAME] = nama_file
        st.session_state[STATE_UPLOAD_FILE_SIZE] = ukuran_file
        st.session_state[STATE_UPLOAD_FILE_EXTENSION] = ekstensi

        signature_baru = _buat_signature_file_upload_dari_bytes(
            nama_file,
            file_bytes,
        )
        signature_lama = st.session_state.get(STATE_UPLOAD_CURRENT_SIGNATURE)
        if signature_lama != signature_baru:
            # Callback file uploader berjalan sebelum rerun halaman dimulai.
            # Antrekan custom loading hanya untuk file baru agar tidak berulang.
            st.session_state[STATE_UPLOAD_LOADING_LABEL] = (
                "Menyiapkan file yang baru diunggah..."
            )
            st.session_state[STATE_UPLOAD_CURRENT_SIGNATURE] = signature_baru
            st.session_state[STATE_UPLOADED_DF] = None
            st.session_state.pop(STATE_UPLOAD_ANALYZED_SIGNATURE, None)
            st.session_state.pop(STATE_UPLOAD_ANALYSIS_REQUEST, None)
            st.session_state.pop(STATE_UPLOAD_RELEVANCE_SIGNATURE, None)
            st.session_state.pop(STATE_UPLOAD_RELEVANCE_SOURCE, None)
            st.session_state.pop(STATE_IS_RELEVANT, None)
            _bersihkan_state_hasil_analisis_upload()
    except Exception:
        LOGGER.exception("File uploader gagal disimpan ke session state")
        _bersihkan_state_upload()


def _siapkan_analisis_file_upload(signature_file: str) -> None:
    """Tandai file yang akan dianalisis dan aktifkan loading custom saat rerun."""
    st.session_state[STATE_UPLOAD_ANALYSIS_REQUEST] = str(signature_file)
    st.session_state[STATE_UPLOAD_LOADING_LABEL] = (
        "Mendeteksi relevansi data dan menyiapkan preview..."
    )


def _bersihkan_state_upload() -> None:
    """Bersihkan hasil analisis ketika file dihapus atau diganti."""
    st.session_state[STATE_UPLOADED_DF] = None
    st.session_state.pop(STATE_UPLOAD_CURRENT_SIGNATURE, None)
    st.session_state.pop(STATE_UPLOAD_ANALYZED_SIGNATURE, None)
    st.session_state.pop(STATE_UPLOAD_ANALYSIS_REQUEST, None)
    st.session_state.pop(STATE_UPLOAD_RAW_BYTES, None)
    st.session_state.pop(STATE_UPLOAD_FILE_NAME, None)
    st.session_state.pop(STATE_UPLOAD_FILE_SIZE, None)
    st.session_state.pop(STATE_UPLOAD_FILE_EXTENSION, None)
    st.session_state.pop(STATE_UPLOAD_RELEVANCE_SIGNATURE, None)
    st.session_state.pop(STATE_UPLOAD_RELEVANCE_SOURCE, None)
    st.session_state.pop(STATE_IS_RELEVANT, None)
    _bersihkan_state_hasil_analisis_upload()


def _render_upload_dataset_sendiri() -> None:
    """Render upload dataset pengguna tanpa memengaruhi dataset penelitian bawaan."""
    if STATE_UPLOADED_DF not in st.session_state:
        st.session_state[STATE_UPLOADED_DF] = None

    with st.expander("📤 Upload Dataset Sendiri", expanded=False):
        st.markdown(
            """
            <span class="dataset-v16-upload-anchor" aria-hidden="true"></span>
            <div class="dataset-v16-upload-intro">
                <div class="dataset-v16-upload-icon">📊</div>
                <div class="dataset-v16-upload-copy">
                    <div class="dataset-v16-upload-eyebrow">Dataset Lab</div>
                    <div class="dataset-v16-upload-title">Bawa data kamu ke dashboard</div>
                    <div class="dataset-v16-upload-subtitle">
                        Unggah satu file, lalu jalankan analisis untuk melihat struktur,
                        preview, dan ringkasan data secara aman.
                    </div>
                </div>
                <div class="dataset-v16-upload-chips">
                    <span class="dataset-v16-upload-chip">CSV</span>
                    <span class="dataset-v16-upload-chip">XLSX</span>
                    <span class="dataset-v16-upload-chip">Analisis Aman</span>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        file_upload = st.file_uploader(
            "Upload data kamu (CSV atau Excel)",
            type=["csv", "xlsx"],
            accept_multiple_files=False,
            key=STATE_UPLOAD_WIDGET,
            help="Pilih satu file CSV atau Excel berformat .xlsx.",
            on_change=_sinkronkan_file_upload_ke_state,
        )

        if file_upload is not None and not st.session_state.get(STATE_UPLOAD_RAW_BYTES):
            _sinkronkan_file_upload_ke_state()

        file_bytes_tersimpan = st.session_state.get(STATE_UPLOAD_RAW_BYTES)
        nama_file_tersimpan = st.session_state.get(STATE_UPLOAD_FILE_NAME)
        ekstensi = str(st.session_state.get(STATE_UPLOAD_FILE_EXTENSION) or "").lower()
        ukuran_byte = int(st.session_state.get(STATE_UPLOAD_FILE_SIZE) or 0)

        if not isinstance(file_bytes_tersimpan, (bytes, bytearray)) or not nama_file_tersimpan:
            st.markdown(
                """
                <div class="dataset-v16-empty-state">
                    <span>💡</span>
                    <div><strong>Belum ada file dipilih.</strong> Pilih file terlebih dahulu,
                    lalu tekan tombol analisis untuk menampilkan preview dan informasi kolom.</div>
                </div>
                """,
                unsafe_allow_html=True,
            )
            st.button(
                "✨ Analisis File Ini",
                key="dataset_v16_analyze_uploaded_file_disabled",
                type="primary",
                disabled=True,
                help="Pilih file CSV atau Excel terlebih dahulu.",
                **_opsi_lebar_penuh(st.button),
            )
            return

        file_bytes_tersimpan = bytes(file_bytes_tersimpan)
        nama_file_tersimpan = str(nama_file_tersimpan)
        if ekstensi not in {".csv", ".xlsx"}:
            _bersihkan_state_upload()
            st.error("Format file tidak didukung. Gunakan CSV atau Excel (.xlsx).")
            return

        signature_file = _buat_signature_file_upload_dari_bytes(
            nama_file_tersimpan,
            file_bytes_tersimpan,
        )
        signature_sebelumnya = st.session_state.get(STATE_UPLOAD_CURRENT_SIGNATURE)
        if signature_sebelumnya != signature_file:
            st.session_state[STATE_UPLOAD_CURRENT_SIGNATURE] = signature_file
            st.session_state[STATE_UPLOADED_DF] = None
            st.session_state.pop(STATE_UPLOAD_ANALYZED_SIGNATURE, None)
            st.session_state.pop(STATE_UPLOAD_ANALYSIS_REQUEST, None)
            st.session_state.pop(STATE_UPLOAD_RELEVANCE_SIGNATURE, None)
            st.session_state.pop(STATE_UPLOAD_RELEVANCE_SOURCE, None)
            st.session_state.pop(STATE_IS_RELEVANT, None)
            _bersihkan_state_hasil_analisis_upload()

        data_tersimpan = st.session_state.get(STATE_UPLOADED_DF)
        sudah_dianalisis = (
            st.session_state.get(STATE_UPLOAD_ANALYZED_SIGNATURE) == signature_file
            and isinstance(data_tersimpan, pd.DataFrame)
            and not data_tersimpan.empty
        )
        analisis_diminta = (
            st.session_state.get(STATE_UPLOAD_ANALYSIS_REQUEST) == signature_file
        )
        pesan_error_analisis: str | None = None

        if analisis_diminta:
            try:
                data_tersimpan = _baca_dataset_upload_cached(
                    file_bytes_tersimpan,
                    ekstensi,
                )
                is_relevant, sumber_relevansi = _deteksi_relevansi_dataset_upload(
                    data_tersimpan
                )
                st.session_state[STATE_UPLOADED_DF] = data_tersimpan.copy()
                st.session_state[STATE_UPLOAD_ANALYZED_SIGNATURE] = signature_file
                st.session_state[STATE_UPLOAD_RELEVANCE_SIGNATURE] = signature_file
                st.session_state[STATE_UPLOAD_RELEVANCE_SOURCE] = sumber_relevansi
                st.session_state[STATE_IS_RELEVANT] = bool(is_relevant)
                try:
                    with st.spinner("Memproses data..."):
                        _siapkan_hasil_analisis_upload(
                            data_tersimpan,
                            bool(is_relevant),
                            signature_file,
                        )
                except Exception as exc:
                    LOGGER.exception("Output analisis upload Fase 18 gagal disiapkan")
                    st.session_state[STATE_UPLOAD_OUTPUT_ERROR] = (
                        "Output analisis belum dapat disiapkan. "
                        f"Detail: {exc}"
                    )
                sudah_dianalisis = True
            except pd.errors.EmptyDataError:
                st.session_state[STATE_UPLOADED_DF] = None
                st.session_state.pop(STATE_UPLOAD_ANALYZED_SIGNATURE, None)
                st.session_state.pop(STATE_UPLOAD_RELEVANCE_SIGNATURE, None)
                st.session_state.pop(STATE_UPLOAD_RELEVANCE_SOURCE, None)
                st.session_state.pop(STATE_IS_RELEVANT, None)
                _bersihkan_state_hasil_analisis_upload()
                LOGGER.warning("File dataset upload tidak memiliki isi data")
                pesan_error_analisis = "File kosong, tidak ada data yang bisa dibaca."
            except ValueError as exc:
                st.session_state[STATE_UPLOADED_DF] = None
                st.session_state.pop(STATE_UPLOAD_ANALYZED_SIGNATURE, None)
                st.session_state.pop(STATE_UPLOAD_RELEVANCE_SIGNATURE, None)
                st.session_state.pop(STATE_UPLOAD_RELEVANCE_SOURCE, None)
                st.session_state.pop(STATE_IS_RELEVANT, None)
                _bersihkan_state_hasil_analisis_upload()
                if str(exc) == "file_kosong":
                    LOGGER.warning("File dataset upload hanya memiliki header atau nol baris")
                    pesan_error_analisis = "File kosong, tidak ada data yang bisa dibaca."
                elif str(exc) == "format_tidak_didukung":
                    LOGGER.warning("Ekstensi file dataset upload tidak didukung")
                    pesan_error_analisis = (
                        "Format file tidak didukung. Gunakan CSV atau Excel (.xlsx)."
                    )
                else:
                    LOGGER.exception("Dataset upload gagal divalidasi")
                    pesan_error_analisis = (
                        "Gagal membaca file. Pastikan file tidak rusak dan coba lagi."
                    )
            except Exception:
                st.session_state[STATE_UPLOADED_DF] = None
                st.session_state.pop(STATE_UPLOAD_ANALYZED_SIGNATURE, None)
                st.session_state.pop(STATE_UPLOAD_RELEVANCE_SIGNATURE, None)
                st.session_state.pop(STATE_UPLOAD_RELEVANCE_SOURCE, None)
                st.session_state.pop(STATE_IS_RELEVANT, None)
                _bersihkan_state_hasil_analisis_upload()
                LOGGER.exception("Dataset upload gagal dibaca")
                pesan_error_analisis = (
                    "Gagal membaca file. Pastikan file tidak rusak dan coba lagi."
                )
            finally:
                st.session_state.pop(STATE_UPLOAD_ANALYSIS_REQUEST, None)

        if ukuran_byte <= 0:
            ukuran_byte = len(file_bytes_tersimpan)

        nama_file_aman = escape(nama_file_tersimpan)
        ukuran_file = _format_ukuran_file(ukuran_byte)
        format_file = "CSV" if ekstensi == ".csv" else "Excel XLSX"
        status_file = "Sudah dianalisis" if sudah_dianalisis else "Siap dianalisis"
        detail_file = (
            "Preview dan ringkasan tersedia"
            if sudah_dianalisis
            else "Menunggu perintah analisis"
        )
        st.markdown(
            f"""
            <div class="dataset-v16-file-strip">
                <div class="dataset-v16-file-icon">✓</div>
                <div class="dataset-v16-file-meta">
                    <div class="dataset-v16-file-name" title="{nama_file_aman}">{nama_file_aman}</div>
                    <div class="dataset-v16-file-detail">{escape(format_file)} · {escape(ukuran_file)} · {escape(detail_file)}</div>
                </div>
                <div class="dataset-v16-file-status">{escape(status_file)}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        if sudah_dianalisis:
            judul_status = "Analisis file sudah selesai"
            catatan_status = (
                "Preview dan ringkasan di bawah berasal dari file yang sedang dipilih. "
                "Gunakan analisis ulang bila file perlu dibaca kembali."
            )
            ikon_status = "✅"
        else:
            judul_status = "File sudah siap untuk diperiksa"
            catatan_status = (
                "Tekan tombol Analisis File Ini. Loading custom akan menutupi proses "
                "pembacaan dan penyusunan hasil agar proses teknis tidak terlihat."
            )
            ikon_status = "⚡"

        st.markdown(
            f"""
            <div class="dataset-v16-analysis-ready">
                <div class="dataset-v16-analysis-ready-icon">{ikon_status}</div>
                <div>
                    <div class="dataset-v16-analysis-ready-title">{escape(judul_status)}</div>
                    <div class="dataset-v16-analysis-ready-note">{escape(catatan_status)}</div>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        label_tombol = (
            "↻ Analisis Ulang File Ini"
            if sudah_dianalisis
            else "✨ Analisis File Ini"
        )
        st.button(
            label_tombol,
            key="dataset_v16_analyze_uploaded_file",
            type="primary",
            on_click=_siapkan_analisis_file_upload,
            args=(signature_file,),
            help="Baca file menggunakan loading custom dan tampilkan hasil analisis awal.",
            **_opsi_lebar_penuh(st.button),
        )

        if pesan_error_analisis:
            st.error(pesan_error_analisis)
            return

        if not sudah_dianalisis or not isinstance(data_tersimpan, pd.DataFrame):
            return

        data_upload = data_tersimpan
        if data_upload.empty:
            return

        st.markdown(
            """
            <div class="dataset-v16-preview-heading">
                <div class="dataset-v16-preview-heading-left">
                    <div class="dataset-v16-preview-icon">🔍</div>
                    <div>
                        <div class="dataset-v16-preview-title">Preview Data</div>
                        <div class="dataset-v16-preview-note">Menampilkan 10 baris pertama tanpa mengubah data asli.</div>
                    </div>
                </div>
                <div class="dataset-v16-preview-badge">10 baris pertama</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
        st.dataframe(
            data_upload.head(10),
            **_opsi_lebar_penuh(st.dataframe),
        )

        relevansi_untuk_file = (
            st.session_state.get(STATE_UPLOAD_RELEVANCE_SIGNATURE) == signature_file
        )
        if relevansi_untuk_file and bool(
            st.session_state.get(STATE_IS_RELEVANT, False)
        ):
            st.success("✅ Data dikenali sebagai data Telkom Group")
        else:
            st.warning("⚠️ Data tidak dikenali sebagai data Telkom Group")

        kol_baris, kol_kolom = st.columns(2, gap="medium")
        with kol_baris:
            _render_metric_upload(
                "Jumlah Baris",
                _format_angka(len(data_upload)),
                "Total baris pada file upload",
                "↕",
                "dataset-v16-metric-red",
            )
        with kol_kolom:
            _render_metric_upload(
                "Jumlah Kolom",
                _format_angka(len(data_upload.columns)),
                "Total kolom pada file upload",
                "▦",
                "dataset-v16-metric-purple",
            )

        badge_kolom = "".join(
            f'<span class="dataset-v16-column-badge" title="{escape(str(kolom))}">'
            f'{escape(str(kolom))}</span>'
            for kolom in data_upload.columns
        )
        st.markdown(
            f"""
            <div class="dataset-v16-columns-section">
                <div class="dataset-v16-columns-header">
                    <div class="dataset-v16-columns-title">Nama Kolom</div>
                    <div class="dataset-v16-columns-count">{len(data_upload.columns)} kolom</div>
                </div>
                <div class="dataset-v16-columns-wrap">{badge_kolom}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        st.markdown(
            """
            <div class="dataset-v16-success">
                <div class="dataset-v16-success-icon">✅</div>
                <div class="dataset-v16-success-copy">
                    <div class="dataset-v16-success-title">Analisis awal selesai. Data siap digunakan di Fase berikutnya!</div>
                    <div class="dataset-v16-success-note">Data tersimpan sementara selama sesi dashboard masih aktif.</div>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        _render_output_analisis_upload(
            data_upload,
            bool(st.session_state.get(STATE_IS_RELEVANT, False)),
            signature_file,
        )


def _siapkan_loading_terapkan_filter() -> None:
    """Tandai aksi filter agar rerun berikutnya memakai loading custom Telkom."""
    st.session_state[STATE_FILTER_LOADING_LABEL] = "Menerapkan filter dataset..."


def _reset_filter_dengan_loading() -> None:
    """Reset seluruh filter dan tampilkan loading custom pada rerun berikutnya."""
    _reset_filter()
    st.session_state[STATE_FILTER_LOADING_LABEL] = "Mereset filter dataset..."


def render_dataset() -> None:
    """Render halaman Dataset untuk IndiHome dan IndiBiz tanpa mengubah alur IndiHome."""
    loading_placeholder = None
    loading_filter_handle = None
    try:
        label_loading_upload = st.session_state.pop(STATE_UPLOAD_LOADING_LABEL, None)
        label_loading_filter = st.session_state.pop(STATE_FILTER_LOADING_LABEL, None)
        label_loading_aksi = label_loading_upload or label_loading_filter
        if label_loading_aksi:
            loading_filter_handle = mulai_loading_aksi(str(label_loading_aksi))

        _inisialisasi_state()
        _inject_css()
        loading_placeholder = mulai_layar_loading(
            STATE_LOADING_SELESAI,
            (
                "Memuat Data Penelitian",
                "Mengambil Data Media Sosial",
                "Menyiapkan Filter Dataset",
                "Menyusun Tabel dan Ringkasan",
                "Menyiapkan Visualisasi",
            ),
        )

        data_semua, metadata = _muat_semua_dataset()

        if data_semua.empty:
            selesaikan_layar_loading(loading_placeholder, STATE_LOADING_SELESAI)
            st.error(
                "Dataset tidak dapat dimuat dan dummy data juga gagal dibuat. "
                "Periksa folder data lalu jalankan ulang aplikasi."
            )
            return

        st.markdown('<div class="dataset-v6-page">', unsafe_allow_html=True)
        st.markdown(
            f"""
            <section class="dataset-v6-hero">
                <h1>Dataset Penelitian</h1>
                <p>
                    Jelajahi percakapan layanan digital Telkom Group dari Twitter,
                    Instagram, dan TikTok. Gunakan filter untuk menemukan komentar
                    yang relevan, lalu unduh hasilnya dalam format CSV.
                </p>
                <div class="dataset-v6-source-row">{_buat_badge_sumber(metadata)}</div>
            </section>
            """,
            unsafe_allow_html=True,
        )

        st.markdown("### 📊 Dataset Bawaan Penelitian")

        for item in metadata:
            if not item["aktual"] and item["error"]:
                st.warning(
                    f"Dataset aktual {item['layanan']} tidak dapat dibaca. "
                    "Halaman menggunakan dummy data agar tetap dapat dijalankan."
                )

        st.markdown(
            '<div class="dataset-v6-filter-title">Filter Dataset</div>',
            unsafe_allow_html=True,
        )

        # Semua kontrol filter ditempatkan di dalam form. Streamlit tidak
        # menjalankan ulang halaman ketika pengguna baru memilih nilai filter.
        # Halaman hanya diproses ulang setelah tombol Terapkan Filter ditekan.
        with st.form("dataset_v9_filter_form", clear_on_submit=False):
            (
                kol_layanan,
                kol_platform,
                kol_sentimen,
                kol_cari,
                kol_terapkan,
                kol_reset,
            ) = st.columns(
                [1.0, 1.35, 1.0, 1.6, 1.05, 0.9],
                gap="small",
            )

            with kol_layanan:
                layanan = st.selectbox(
                    "Layanan",
                    LAYANAN_OPTIONS,
                    key=STATE_LAYANAN,
                )

            with kol_platform:
                if layanan == "IndiBiz":
                    nilai_platform = st.session_state.get(
                        STATE_PLATFORM_INDIBIZ,
                        [],
                    )
                    if not isinstance(nilai_platform, list):
                        st.session_state[STATE_PLATFORM_INDIBIZ] = []
                    platform: str | list[str] = st.multiselect(
                        "Platform",
                        ["Twitter", "Instagram", "TikTok"],
                        key=STATE_PLATFORM_INDIBIZ,
                        placeholder="Semua platform",
                        help="Biarkan kosong untuk menampilkan semua platform.",
                    )
                else:
                    platform = st.selectbox(
                        "Platform",
                        PLATFORM_OPTIONS,
                        key=STATE_PLATFORM,
                    )

            with kol_sentimen:
                sentimen = st.selectbox(
                    "Sentimen",
                    SENTIMEN_OPTIONS,
                    key=STATE_SENTIMEN,
                )

            with kol_cari:
                pencarian = st.text_input(
                    "Cari komentar",
                    placeholder="Ketik kata pada isi komentar...",
                    key=STATE_PENCARIAN,
                )

            with kol_terapkan:
                st.markdown(
                    '<span class="dataset-v6-reset-marker dataset-v10-apply-marker" aria-hidden="true">Aksi</span>',
                    unsafe_allow_html=True,
                )
                tombol_terapkan = st.form_submit_button(
                    "Terapkan Filter",
                    type="primary",
                    on_click=_siapkan_loading_terapkan_filter,
                    **_opsi_lebar_penuh(st.form_submit_button),
                )

            with kol_reset:
                st.markdown(
                    '<span class="dataset-v6-reset-marker dataset-v10-reset-marker" aria-hidden="true">Aksi</span>',
                    unsafe_allow_html=True,
                )
                st.form_submit_button(
                    "Reset Filter",
                    on_click=_reset_filter_dengan_loading,
                    **_opsi_lebar_penuh(st.form_submit_button),
                )

        if tombol_terapkan:
            # Setiap penerapan filter kembali ke halaman tabel pertama.
            st.session_state[STATE_HALAMAN] = 1
            st.session_state[STATE_SIGNATURE] = None

        _render_badge_layanan_aktif(metadata, layanan)

        if layanan == "IndiHome":
            data_layanan = data_semua[data_semua["layanan"].eq("IndiHome")].copy()
        elif layanan == "IndiBiz":
            data_layanan = data_semua[data_semua["layanan"].eq("IndiBiz")].copy()
        else:
            data_layanan = pd.DataFrame(columns=KOLOM_KANONIK)

        data_filter = _terapkan_filter(
            data_semua,
            layanan,
            platform,
            sentimen,
            pencarian,
        )

        total_data = len(data_layanan)
        total_tampil = len(data_filter)
        jumlah_positif = int(data_filter["sentimen"].eq("Positif").sum())
        jumlah_negatif = int(data_filter["sentimen"].eq("Negatif").sum())
        persen_positif = (jumlah_positif / total_tampil * 100) if total_tampil else 0.0
        persen_negatif = (jumlah_negatif / total_tampil * 100) if total_tampil else 0.0

        st.markdown(
            '<div class="dataset-v6-section-title">Ringkasan Data</div>',
            unsafe_allow_html=True,
        )

        if layanan == "IndiBiz":
            platform_terbanyak = (
                str(data_filter["platform"].value_counts().index[0])
                if not data_filter.empty
                else "-"
            )
            sentimen_dominan = (
                str(data_filter["sentimen"].value_counts().index[0])
                if not data_filter.empty
                else "-"
            )
            metrik_1, metrik_2, metrik_3 = st.columns(3, gap="small")
            with metrik_1:
                _render_metric_card(
                    "Total Komentar",
                    _format_angka(total_tampil),
                    f"Dari {_format_angka(total_data)} komentar IndiBiz",
                )
            with metrik_2:
                _render_metric_card(
                    "Platform Terbanyak",
                    platform_terbanyak,
                    "Platform dengan komentar terbanyak setelah filter",
                )
            with metrik_3:
                _render_metric_card(
                    "Sentimen Dominan",
                    sentimen_dominan,
                    "Kategori sentimen paling banyak setelah filter",
                )
        elif layanan == "IndiHome":
            metrik_1, metrik_2, metrik_3, metrik_4 = st.columns(4, gap="small")
            with metrik_1:
                _render_metric_card(
                    "Total Data",
                    _format_angka(total_data),
                    "Jumlah data pada layanan terpilih",
                )
            with metrik_2:
                _render_metric_card(
                    "Ditampilkan",
                    _format_angka(total_tampil),
                    "Jumlah data setelah seluruh filter",
                )
            with metrik_3:
                _render_metric_card(
                    "% Positif",
                    _format_persen(persen_positif),
                    f"{_format_angka(jumlah_positif)} komentar positif",
                )
            with metrik_4:
                _render_metric_card(
                    "% Negatif",
                    _format_persen(persen_negatif),
                    f"{_format_angka(jumlah_negatif)} komentar negatif",
                )

        judul_tabel, kontrol_baris = st.columns([4.2, 1.1])
        with judul_tabel:
            st.markdown(
                '<div class="dataset-v6-section-title dataset-v6-table-title">Tabel Data</div>',
                unsafe_allow_html=True,
            )
        with kontrol_baris:
            baris_per_halaman = int(
                st.selectbox(
                    "Baris per halaman",
                    BARIS_PER_HALAMAN_OPTIONS,
                    key=STATE_BARIS_PER_HALAMAN,
                    help="Pilih 10, 25, atau 50 baris pada setiap halaman tabel.",
                )
            )

        platform_signature = tuple(platform) if isinstance(platform, list) else platform
        signature_tabel = (
            layanan,
            platform_signature,
            sentimen,
            pencarian.strip().lower(),
            baris_per_halaman,
        )
        if st.session_state.get(STATE_SIGNATURE) != signature_tabel:
            st.session_state[STATE_SIGNATURE] = signature_tabel
            st.session_state[STATE_HALAMAN] = 1

        total_halaman = max(1, math.ceil(total_tampil / baris_per_halaman))
        halaman_saat_ini = min(
            max(1, int(st.session_state.get(STATE_HALAMAN, 1))),
            total_halaman,
        )
        st.session_state[STATE_HALAMAN] = halaman_saat_ini

        indeks_awal = (halaman_saat_ini - 1) * baris_per_halaman
        indeks_akhir = indeks_awal + baris_per_halaman
        data_halaman = data_filter.iloc[indeks_awal:indeks_akhir].copy()

        st.markdown(
            _buat_html_tabel(data_halaman, indeks_awal + 1),
            unsafe_allow_html=True,
        )

        navigasi_kiri, navigasi_tengah, navigasi_kanan = st.columns([1, 2, 1])
        with navigasi_kiri:
            st.button(
                "← Sebelumnya",
                key="dataset_v6_prev",
                disabled=halaman_saat_ini <= 1,
                on_click=_ubah_halaman,
                args=(-1, total_halaman),
                **_opsi_lebar_penuh(st.button),
            )
        with navigasi_tengah:
            st.markdown(
                f'<div class="dataset-v6-pagination-info">'
                f'Menampilkan {_format_angka(indeks_awal + 1 if total_tampil else 0)}–'
                f'{_format_angka(min(indeks_akhir, total_tampil))} dari '
                f'{_format_angka(total_tampil)} data &nbsp;•&nbsp; '
                f'Halaman {halaman_saat_ini} dari {total_halaman}'
                f'</div>',
                unsafe_allow_html=True,
            )
        with navigasi_kanan:
            st.button(
                "Berikutnya →",
                key="dataset_v6_next",
                disabled=halaman_saat_ini >= total_halaman,
                on_click=_ubah_halaman,
                args=(1, total_halaman),
                **_opsi_lebar_penuh(st.button),
            )

        area_download, area_kosong = st.columns([1.2, 3.8])
        with area_download:
            nama_layanan = layanan.lower().replace(" ", "-")
            if isinstance(platform, list):
                nama_platform = "-".join(item.lower() for item in platform) or "tanpa-platform"
            else:
                nama_platform = platform.lower().replace(" ", "-")
            st.download_button(
                "⬇ Download CSV",
                data=_siapkan_csv(data_filter),
                file_name=f"dataset-{nama_layanan}-{nama_platform}-terfilter.csv",
                mime="text/csv",
                key="dataset_v6_download",
                **_opsi_lebar_penuh(st.download_button),
            )
        with area_kosong:
            st.markdown(
                f'<div class="dataset-v6-info-text">'
                f'Menampilkan {_format_angka(total_tampil)} dari '
                f'{_format_angka(total_data)} total data'
                f'</div>',
                unsafe_allow_html=True,
            )

        legenda_sentimen = [
            ("Positif", WARNA_SENTIMEN["Positif"]),
            ("Netral", WARNA_SENTIMEN["Netral"]),
            ("Negatif", WARNA_SENTIMEN["Negatif"]),
        ]
        legenda_platform = [
            ("Twitter", WARNA_PLATFORM["Twitter"]),
            ("Instagram", WARNA_PLATFORM["Instagram"]),
            ("TikTok", WARNA_PLATFORM["TikTok"]),
        ]

        if layanan == "IndiBiz":
            st.markdown(
                '<div class="dataset-v6-section-title">Distribusi Data IndiBiz</div>',
                unsafe_allow_html=True,
            )
            if data_filter.empty:
                st.info("Chart belum dapat ditampilkan karena hasil filter kosong.")
            else:
                figur_platform = _chart_platform(data_filter)
                figur_sentimen = _chart_sentimen(data_filter)
                chart_kiri, chart_kanan = st.columns(2, gap="medium")
                with chart_kiri:
                    st.markdown(
                        '<div class="dataset-v6-section-title">Distribusi Komentar per Platform</div>',
                        unsafe_allow_html=True,
                    )
                    st.plotly_chart(
                        figur_platform,
                        config={"displayModeBar": False, "responsive": True},
                        **_opsi_lebar_penuh(st.plotly_chart),
                    )
                with chart_kanan:
                    st.markdown(
                        '<div class="dataset-v6-section-title">Distribusi Sentimen</div>',
                        unsafe_allow_html=True,
                    )
                    st.plotly_chart(
                        figur_sentimen,
                        config={"displayModeBar": False, "responsive": True},
                        **_opsi_lebar_penuh(st.plotly_chart),
                    )
            _render_preview_sna_indibiz()

        elif layanan == "IndiHome":
            with st.expander("Distribusi Cepat", expanded=False):
                if data_filter.empty:
                    st.info("Chart belum dapat ditampilkan karena hasil filter kosong.")
                else:
                    figur_sentimen = _chart_sentimen(data_filter)
                    figur_platform = _chart_platform(data_filter)

                    chart_kiri, chart_kanan = st.columns(2, gap="medium")
                    with chart_kiri:
                        judul_sentimen, aksi_sentimen = st.columns([3.5, 1.35], gap="small")
                        with judul_sentimen:
                            st.markdown(
                                '<div class="dataset-v6-section-title">Distribusi Sentimen</div>',
                                unsafe_allow_html=True,
                            )
                        with aksi_sentimen:
                            st.markdown(
                                '<span class="dataset-v6-chart-action-marker" '
                                'aria-hidden="true">Perbesar</span>',
                                unsafe_allow_html=True,
                            )
                            if st.button(
                                "⛶ Layar Penuh",
                                key="dataset_v6_fullscreen_sentimen",
                                help="Tampilkan grafik Distribusi Sentimen dalam layar penuh.",
                                **_opsi_lebar_penuh(st.button),
                            ):
                                _tampilkan_chart_layar_penuh(
                                    "Distribusi Sentimen",
                                    figur_sentimen,
                                    legenda_sentimen,
                                )
                        st.plotly_chart(
                            figur_sentimen,
                            config={"displayModeBar": False, "responsive": True},
                            **_opsi_lebar_penuh(st.plotly_chart),
                        )

                    with chart_kanan:
                        judul_platform, aksi_platform = st.columns([3.5, 1.35], gap="small")
                        with judul_platform:
                            st.markdown(
                                '<div class="dataset-v6-section-title">Distribusi Platform</div>',
                                unsafe_allow_html=True,
                            )
                        with aksi_platform:
                            st.markdown(
                                '<span class="dataset-v6-chart-action-marker" '
                                'aria-hidden="true">Perbesar</span>',
                                unsafe_allow_html=True,
                            )
                            if st.button(
                                "⛶ Layar Penuh",
                                key="dataset_v6_fullscreen_platform",
                                help="Tampilkan grafik Distribusi Platform dalam layar penuh.",
                                **_opsi_lebar_penuh(st.button),
                            ):
                                _tampilkan_chart_layar_penuh(
                                    "Distribusi Platform",
                                    figur_platform,
                                    legenda_platform,
                                )
                        st.plotly_chart(
                            figur_platform,
                            config={"displayModeBar": False, "responsive": True},
                            **_opsi_lebar_penuh(st.plotly_chart),
                        )

        st.divider()
        _render_upload_dataset_sendiri()

        st.markdown("</div>", unsafe_allow_html=True)
        selesaikan_layar_loading(loading_placeholder, STATE_LOADING_SELESAI)

    except Exception as exc:
        batalkan_layar_loading(loading_placeholder, STATE_LOADING_SELESAI)
        LOGGER.exception("Halaman Dataset gagal dirender")
        st.error(
            "Halaman Dataset mengalami kesalahan dan belum dapat ditampilkan. "
            "Silakan muat ulang aplikasi."
        )
        with st.expander("Detail teknis untuk pemeriksaan", expanded=False):
            st.code(str(exc))
    finally:
        selesaikan_loading_aksi(loading_filter_handle)
