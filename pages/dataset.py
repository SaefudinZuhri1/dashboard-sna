# pages/dataset.py
# TAHAP 5 FASE 12 - MODEL INDOBERT HUGGINGFACE HUB TANPA BOBOT LOKAL.
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
from utils.streamlit_compat import render_html_iframe

from utils.audit_logger import log_activity
from utils.data_loader import load_indibiz_sentiment, load_indibiz_sna
from utils.indibiz_config import INDIBIZ_SENTIMENT_CANDIDATES, INDIBIZ_SNA_CANDIDATES
from utils.dummy_data import get_demo_sentiment
from utils.css_loader import render_analytics_control_style
from utils.loading_screen import (
    batalkan_layar_loading,
    mulai_layar_loading,
    mulai_loading_aksi,
    selesaikan_layar_loading,
    selesaikan_loading_aksi,
)

LOGGER = logging.getLogger(__name__)

LAYANAN_OPTIONS = ["IndiHome", "IndiBiz", "Telkomsel"]
PLATFORM_OPTIONS = ["Semua", "Twitter", "Instagram", "TikTok"]
SENTIMEN_OPTIONS = ["Semua", "Positif", "Netral", "Negatif"]
BARIS_PER_HALAMAN_OPTIONS = [10, 25, 50]
DEFAULT_BARIS_PER_HALAMAN = 10
DATASET_CACHE_VERSION = "fase22-dataset-datetime-ns-v1"  # FIX: paksa cache baru setelah perbaikan dtype tanggal
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

REQUIRED_UPLOAD_COLS = ("content", "platform", "from_username")
REQUIRED_UPLOAD_ALIASES = {
    "content": ("content", "komentar", "text", "full_text", "comment", "tweet_text", "caption"),
    "platform": ("platform", "specific_resource_type", "source_platform", "resource_type"),
    "from_username": ("from_username", "username", "user", "screen_name", "author", "account"),
}

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
STATE_FULLSCREEN_LOADING_LABEL = "dataset_v19_fullscreen_loading_label"
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
STATE_WORDCLOUD_PALETTE = "dataset_v20_wordcloud_palette"
STATE_WORDCLOUD_MAX_WORDS = "dataset_v20_wordcloud_max_words"
STATE_WORDCLOUD_SEED = "dataset_v20_wordcloud_seed"
STATE_WORDCLOUD_LOADING_LABEL = "dataset_v20_wordcloud_loading_label"
STATE_TOPIK_MODE = "dataset_v21_topik_mode"

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

def _plotly_chart_aman(figur: go.Figure | None, *args: Any, **kwargs: Any) -> Any:
    """Render Plotly hanya ketika objek figur tersedia."""
    try:
        if figur is None:
            st.warning("Grafik tidak dapat ditampilkan.")
            return None
        # FIX: Gunakan lebar container dan mode responsif tanpa mengubah figur.
        kwargs = {**_opsi_lebar_penuh(st.plotly_chart), **kwargs}
        config = dict(kwargs.pop("config", {}) or {})
        config.setdefault("responsive", True)
        kwargs["config"] = config
        return st.plotly_chart(figur, *args, **kwargs)
    except Exception as error:
        LOGGER.exception("Grafik Dataset gagal dirender: %s", error)
        st.warning("Grafik tidak dapat ditampilkan.")
        return None


def _pyplot_aman(figur: Any, *args: Any, **kwargs: Any) -> Any:
    """Render Matplotlib hanya ketika objek figur tersedia."""
    try:
        if figur is None:
            st.warning("WordCloud tidak dapat ditampilkan.")
            return None
        return st.pyplot(figur, *args, **kwargs)
    except Exception as error:
        LOGGER.exception("Visualisasi Matplotlib Dataset gagal dirender: %s", error)
        st.warning("WordCloud tidak dapat ditampilkan.")
        return None


def _dataframe_responsif(data: Any, *args: Any, **kwargs: Any) -> Any:
    """Render tabel responsif dengan tinggi maksimum yang konsisten."""
    try:
        kwargs.setdefault("height", 400)
        # FIX: Pastikan tabel mengikuti lebar container pada laptop dan tablet.
        kwargs = {**_opsi_lebar_penuh(st.dataframe), **kwargs}
        return st.dataframe(data, *args, **kwargs)
    except Exception as error:
        LOGGER.exception("Tabel Dataset gagal dirender: %s", error)
        st.warning("Tabel tidak dapat ditampilkan.")
        return None


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


def _paksa_datetime_ns(nilai: pd.Series, indeks: pd.Index | None = None) -> pd.Series:
    """Samakan seluruh tanggal ke datetime64[ns] agar aman saat digabungkan."""
    indeks_hasil = indeks if indeks is not None else nilai.index
    try:
        hasil = pd.to_datetime(nilai, errors="coerce")
        hasil = pd.Series(hasil, index=indeks_hasil)
        if isinstance(hasil.dtype, pd.DatetimeTZDtype):
            hasil = hasil.dt.tz_localize(None)
        # FIX: Pandas dapat menghasilkan datetime64[us] dari sebagian format.
        # Semua sumber dipaksa ke nanodetik sebelum operasi setitem/concat/sort.
        return hasil.astype("datetime64[ns]")
    except Exception:
        # FIX: Fallback melalui teks mencegah halaman gagal total akibat dtype lama
        # yang tersimpan di cache disk atau berasal dari file dengan unit berbeda.
        teks = pd.Series(nilai, index=indeks_hasil).astype("string")
        hasil = pd.to_datetime(teks, errors="coerce")
        return pd.Series(hasil, index=indeks_hasil).astype("datetime64[ns]")


def _parse_tanggal(series: pd.Series) -> pd.Series:
    """Ubah berbagai format tanggal menjadi datetime64[ns] secara defensif."""
    teks = series.where(series.notna(), "").astype(str).map(_bersihkan_teks)
    hasil = pd.Series(pd.NaT, index=teks.index, dtype="datetime64[ns]")

    kandidat_titik = pd.to_datetime(
        teks,
        format="%d/%m/%Y %H.%M.%S",
        errors="coerce",
    )
    kandidat_titik = _paksa_datetime_ns(kandidat_titik, teks.index)
    terbaca = kandidat_titik.notna()
    if terbaca.any():
        # FIX: RHS dan target sama-sama datetime64[ns], sehingga bug mixed-unit
        # pandas tidak terpicu saat mengisi hasil parsing bertahap.
        hasil.loc[terbaca] = kandidat_titik.loc[terbaca]

    belum_terbaca = hasil.isna() & teks.ne("")
    if belum_terbaca.any():
        kandidat_titik_dua = pd.to_datetime(
            teks.loc[belum_terbaca],
            format="%d/%m/%Y %H:%M:%S",
            errors="coerce",
        )
        kandidat_titik_dua = _paksa_datetime_ns(
            kandidat_titik_dua,
            teks.loc[belum_terbaca].index,
        )
        valid = kandidat_titik_dua.notna()
        if valid.any():
            hasil.loc[kandidat_titik_dua.index[valid]] = kandidat_titik_dua.loc[valid]

    belum_terbaca = hasil.isna() & teks.ne("")
    if belum_terbaca.any():
        kandidat_campuran = pd.to_datetime(
            teks.loc[belum_terbaca],
            format="mixed",
            errors="coerce",
            dayfirst=True,
        )
        kandidat_campuran = _paksa_datetime_ns(
            kandidat_campuran,
            teks.loc[belum_terbaca].index,
        )
        valid = kandidat_campuran.notna()
        if valid.any():
            hasil.loc[kandidat_campuran.index[valid]] = kandidat_campuran.loc[valid]

    # FIX: Kontrak keluaran selalu datetime64[ns], termasuk ketika semua nilai NaT.
    return _paksa_datetime_ns(hasil, teks.index)


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
    _dataframe_responsif(
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
        for layanan in LAYANAN_OPTIONS:
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

    for layanan in LAYANAN_OPTIONS:
        data, aktual, sumber, error = _muat_layanan(layanan)
        if not data.empty:
            data_aman = data.copy()
            if "tanggal" in data_aman.columns:
                # FIX: Hindari pd.concat mencampur datetime64[us] dan datetime64[ns]
                # dari file aktual, dummy data, atau cache lama.
                data_aman["tanggal"] = _paksa_datetime_ns(data_aman["tanggal"])
            kumpulan.append(data_aman)
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
    # FIX: Normalisasi ulang sesudah concat sebagai pengaman terakhir sebelum sort.
    gabungan["tanggal"] = _paksa_datetime_ns(gabungan["tanggal"])
    gabungan = gabungan.sort_values("tanggal", ascending=False, na_position="last")
    return gabungan.reset_index(drop=True), metadata


def _metadata_dataset_ringkas(
    layanan_aktif: str,
    metadata_aktif: dict[str, Any],
) -> list[dict[str, Any]]:
    """Susun badge semua layanan tanpa membaca seluruh isi semua CSV."""
    metadata: list[dict[str, Any]] = []
    for layanan in LAYANAN_OPTIONS:
        if layanan == layanan_aktif:
            metadata.append(dict(metadata_aktif))
            continue

        kandidat_aktual = next(
            (path for path in _kandidat_file(layanan) if path.is_file()),
            None,
        )
        metadata.append(
            {
                "layanan": layanan,
                "aktual": kandidat_aktual is not None,
                "sumber": (
                    kandidat_aktual.name
                    if kandidat_aktual is not None
                    else "Data dummy bawaan"
                ),
                # Jumlah layanan lain baru dihitung saat layanan tersebut dipilih.
                "jumlah": 0,
                "error": None,
            }
        )
    return metadata


def _muat_semua_dataset() -> tuple[pd.DataFrame, list[dict[str, Any]]]:
    """Muat hanya layanan aktif; layanan lain dibaca ketika benar-benar dipilih.

    Nama fungsi dipertahankan agar integrasi halaman tidak berubah. Optimasi ini
    menghindari pembacaan dan normalisasi tiga dataset besar sekaligus setiap
    pengguna pertama kali membuka halaman Dataset.
    """
    layanan_aktif = str(
        st.session_state.get(STATE_LAYANAN, "IndiHome")
    ).strip()
    if layanan_aktif not in LAYANAN_OPTIONS:
        layanan_aktif = "IndiHome"

    if bool(st.session_state.get("demo_mode", False)):
        try:
            data_demo = _normalisasi_dataset(
                get_demo_sentiment(layanan_aktif),
                layanan_aktif,
            )
            data_demo["tanggal"] = _paksa_datetime_ns(data_demo["tanggal"])
            data_demo = data_demo.sort_values(
                "tanggal", ascending=False, na_position="last"
            ).reset_index(drop=True)
            metadata_aktif = {
                "layanan": layanan_aktif,
                "aktual": False,
                "sumber": "Mode Demo · 500 data sample",
                "jumlah": int(len(data_demo)),
                "error": None,
            }
            return data_demo, _metadata_dataset_ringkas(
                layanan_aktif, metadata_aktif
            )
        except Exception as exc:
            LOGGER.exception("Data Mode Demo halaman Dataset gagal disiapkan")
            st.error(f"Data Mode Demo belum dapat disiapkan: {exc}")
            return pd.DataFrame(columns=KOLOM_KANONIK), []

    try:
        data, aktual, sumber, error = _muat_layanan(layanan_aktif)
        if not data.empty and "tanggal" in data.columns:
            data = data.copy()
            data["tanggal"] = _paksa_datetime_ns(data["tanggal"])
            data = data.sort_values(
                "tanggal", ascending=False, na_position="last"
            ).reset_index(drop=True)

        metadata_aktif = {
            "layanan": layanan_aktif,
            "aktual": aktual,
            "sumber": sumber,
            "jumlah": int(len(data)),
            "error": error,
        }
        return data, _metadata_dataset_ringkas(layanan_aktif, metadata_aktif)
    except Exception as exc:
        LOGGER.exception("Dataset aktif %s gagal dimuat", layanan_aktif)
        st.error(f"Dataset {layanan_aktif} belum dapat dimuat: {exc}")
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


def _sinkronkan_layanan_dataset_saat_masuk() -> None:
    """Selaraskan selector Dataset dengan layanan aktif lintas halaman."""
    try:
        if st.session_state.get("_active_service_sync_target") != "Dataset":
            return
        layanan = str(st.session_state.get("active_service", "IndiHome")).strip()
        if layanan not in LAYANAN_OPTIONS:
            layanan = "IndiHome"
        st.session_state[STATE_LAYANAN] = layanan
        st.session_state.pop("_active_service_sync_target", None)
    except Exception as error:
        LOGGER.exception("Sinkronisasi layanan Dataset gagal: %s", error)


def _reset_filter() -> None:
    """Kembalikan seluruh filter dan pagination ke kondisi awal."""
    st.session_state[STATE_LAYANAN] = "IndiHome"
    st.session_state["active_service"] = "IndiHome"
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
        # Judul chart sengaja dikosongkan. Judul section sudah ditampilkan
        # melalui komponen HTML di atas chart, sehingga Plotly tidak membuat
        # placeholder judul bernilai "undefined".
        title=dict(text=""),
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


def _tema_chart_layar_penuh() -> dict[str, str]:
    """Ambil token warna dialog chart sesuai tema aktif secara aman."""
    try:
        if bool(st.session_state.get("dark_mode", False)):
            return {
                "template": "plotly_dark",
                "text": "#F8FAFC",
                "muted": "#A7B0BF",
                "grid": "rgba(71,85,105,0.62)",
                "axis": "rgba(167,176,191,0.30)",
                "legend_bg": "rgba(21,27,38,0.94)",
                "legend_border": "#334155",
                "hover_bg": "#151B26",
                "hover_border": "rgba(229,57,53,0.38)",
            }
        return {
            "template": "plotly_white",
            "text": "#1F2937",
            "muted": "#64748B",
            "grid": "rgba(148,163,184,0.24)",
            "axis": "rgba(100,116,139,0.34)",
            "legend_bg": "rgba(255,255,255,0.96)",
            "legend_border": "#D9E1EA",
            "hover_bg": "#FFFFFF",
            "hover_border": "rgba(229,57,53,0.28)",
        }
    except Exception as exc:
        LOGGER.exception("Tema chart layar penuh gagal dibaca: %s", exc)
        st.error("Tema grafik layar penuh belum dapat dibaca.")
        return {
            "template": "plotly_white",
            "text": "#1F2937",
            "muted": "#64748B",
            "grid": "rgba(148,163,184,0.24)",
            "axis": "rgba(100,116,139,0.34)",
            "legend_bg": "rgba(255,255,255,0.96)",
            "legend_border": "#D9E1EA",
            "hover_bg": "#FFFFFF",
            "hover_border": "rgba(229,57,53,0.28)",
        }


@_DIALOG_DECORATOR(" ", width="large")
def _tampilkan_chart_layar_penuh(
    judul: str,
    figur: go.Figure,
    legenda: list[tuple[str, str]],
) -> None:
    """Tampilkan satu chart layar penuh yang mengikuti tema aktif."""
    try:
        st.markdown(
            '<span class="dataset-v19-fullscreen-marker" aria-hidden="true"></span>',
            unsafe_allow_html=True,
        )

        tema = _tema_chart_layar_penuh()
        figur_besar = go.Figure(figur)

        # Beri ruang tambahan di sisi kanan agar label nilai yang berada di luar
        # batang tidak menyentuh atau terpotong oleh batas kanvas.
        nilai_chart: list[float] = []
        for trace in figur_besar.data:
            if getattr(trace, "x", None):
                nilai_chart.extend(
                    float(nilai)
                    for nilai in trace.x
                    if nilai is not None
                )
        nilai_maksimum = max(nilai_chart, default=1.0)

        figur_besar.update_layout(
            template=tema["template"],
            # Judul dialog dan judul tambahan sengaja dihilangkan agar area
            # layar penuh hanya berfokus pada grafik.
            title=dict(text=""),
            height=560,
            autosize=True,
            margin=dict(l=104, r=150, t=94, b=118),
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
            font=dict(family="Inter, sans-serif", color=tema["text"]),
            bargap=0.38,
            legend=dict(
                orientation="h",
                yanchor="bottom",
                y=1.035,
                xanchor="center",
                x=0.5,
                bgcolor=tema["legend_bg"],
                bordercolor=tema["legend_border"],
                borderwidth=1,
                font=dict(
                    family="Inter, sans-serif",
                    color=tema["text"],
                    size=14,
                ),
                itemclick="toggle",
                itemdoubleclick=False,
                traceorder="normal",
            ),
            xaxis=dict(
                title=dict(text="Jumlah Data", standoff=14),
                automargin=True,
                gridcolor=tema["grid"],
                linecolor=tema["axis"],
                zerolinecolor=tema["axis"],
                tickfont=dict(color=tema["muted"], size=13),
                title_font=dict(color=tema["muted"], size=15),
                rangemode="tozero",
                range=[0, nilai_maksimum * 1.20],
            ),
            yaxis=dict(
                automargin=True,
                gridcolor="rgba(0,0,0,0)",
                linecolor=tema["axis"],
                tickfont=dict(color=tema["text"], size=14),
                categoryorder="trace",
            ),
            hoverlabel=dict(
                bgcolor=tema["hover_bg"],
                bordercolor=tema["hover_border"],
                font=dict(family="Inter, sans-serif", color=tema["text"]),
            ),
            transition=dict(duration=360, easing="cubic-in-out"),
        )
        _plotly_chart_aman(
            figur_besar,
            config={
                "displayModeBar": True,
                "displaylogo": False,
                "responsive": True,
                "scrollZoom": True,
                "toImageButtonOptions": {"format": "png", "scale": 2},
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
                font-size: 0.75rem /* FIX: minimum 12px agar terbaca di tablet */;
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
                font-size: 0.75rem /* FIX: minimum 12px agar terbaca di tablet */;
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
                font-size: 0.75rem /* FIX: minimum 12px agar terbaca di tablet */;
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

            .dataset-v19-fullscreen-marker {
                display: none !important;
            }

            div[data-testid="stDialog"] div[data-testid="stMarkdown"]:has(.dataset-v19-fullscreen-marker),
            div[data-baseweb="modal"] div[data-testid="stMarkdown"]:has(.dataset-v19-fullscreen-marker),
            div[data-testid="stDialog"] div[data-testid="stMarkdownContainer"]:has(.dataset-v19-fullscreen-marker),
            div[data-baseweb="modal"] div[data-testid="stMarkdownContainer"]:has(.dataset-v19-fullscreen-marker) {
                display: none !important;
                height: 0 !important;
                margin: 0 !important;
                min-height: 0 !important;
                padding: 0 !important;
            }

            div[data-testid="stDialog"] div[data-testid="stVerticalBlock"]:has(.dataset-v19-fullscreen-marker),
            div[data-baseweb="modal"] div[data-testid="stVerticalBlock"]:has(.dataset-v19-fullscreen-marker) {
                align-items: center !important;
                box-sizing: border-box !important;
                display: flex !important;
                gap: 0 !important;
                height: 100dvh !important;
                justify-content: center !important;
                margin: 0 !important;
                max-height: 100dvh !important;
                overflow: hidden !important;
                padding: clamp(46px, 6vh, 62px) clamp(54px, 7vw, 104px) !important;
                width: 100vw !important;
            }

            div[data-testid="stDialog"] [data-testid="stPlotlyChart"],
            div[data-baseweb="modal"] [data-testid="stPlotlyChart"] {
                background: #151B26 !important;
                border: 1px solid #2B3A50 !important;
                border-radius: 14px !important;
                box-sizing: border-box !important;
                height: min(70dvh, 590px) !important;
                margin: auto !important;
                max-height: 590px !important;
                max-width: 1260px !important;
                min-height: 500px !important;
                overflow: hidden !important;
                width: min(82vw, 1260px) !important;
            }

            div[data-testid="stDialog"] [data-testid="stPlotlyChart"] > div,
            div[data-testid="stDialog"] [data-testid="stPlotlyChart"] .js-plotly-plot,
            div[data-testid="stDialog"] [data-testid="stPlotlyChart"] .plot-container,
            div[data-baseweb="modal"] [data-testid="stPlotlyChart"] > div,
            div[data-baseweb="modal"] [data-testid="stPlotlyChart"] .js-plotly-plot,
            div[data-baseweb="modal"] [data-testid="stPlotlyChart"] .plot-container {
                height: 100% !important;
                width: 100% !important;
            }

            @media (max-width: 760px) {
                div[data-testid="stDialog"] div[data-testid="stVerticalBlock"]:has(.dataset-v19-fullscreen-marker),
                div[data-baseweb="modal"] div[data-testid="stVerticalBlock"]:has(.dataset-v19-fullscreen-marker) {
                    padding: 18px !important;
                }

                div[data-testid="stDialog"] [data-testid="stPlotlyChart"],
                div[data-baseweb="modal"] [data-testid="stPlotlyChart"] {
                    height: min(72dvh, 540px) !important;
                    max-height: calc(100dvh - 48px) !important;
                    min-height: 410px !important;
                    width: calc(100vw - 48px) !important;
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
                font-size: 0.75rem /* FIX: minimum 12px agar terbaca di tablet */;
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
                font-size: 0.75rem /* FIX: minimum 12px agar terbaca di tablet */;
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
                font-size: 0.75rem /* FIX: minimum 12px agar terbaca di tablet */;
                margin-top: 0.14rem;
            }

            .dataset-v16-file-status {
                background: rgba(76,175,80,0.15);
                border: 1px solid rgba(76,175,80,0.30);
                border-radius: 999px;
                color: #7EE083;
                font-size: 0.75rem /* FIX: minimum 12px agar terbaca di tablet */;
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
                font-size: 0.75rem /* FIX: minimum 12px agar terbaca di tablet */;
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
                font-size: 0.75rem /* FIX: minimum 12px agar terbaca di tablet */;
                margin-top: 0.12rem;
            }

            .dataset-v16-preview-badge {
                background: rgba(142,90,247,0.12);
                border: 1px solid rgba(142,90,247,0.26);
                border-radius: 999px;
                color: #BFA8FF;
                font-size: 0.75rem /* FIX: minimum 12px agar terbaca di tablet */;
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
                font-size: 0.75rem /* FIX: minimum 12px agar terbaca di tablet */;
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
                font-size: 0.75rem /* FIX: minimum 12px agar terbaca di tablet */;
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
                font-size: 0.75rem /* FIX: minimum 12px agar terbaca di tablet */;
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
                font-size: 0.75rem /* FIX: minimum 12px agar terbaca di tablet */;
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
                font-size: 0.75rem /* FIX: minimum 12px agar terbaca di tablet */;
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
                .dataset-v6-table { font-size: 0.75rem /* FIX: minimum 12px agar terbaca di tablet */; }
            }
        </style>
        """,
        unsafe_allow_html=True,
    )

    # Patch tema terang halaman Dataset. Seluruh selector ditempatkan setelah
    # CSS baseline agar Dark Mode tetap identik dengan versi UI/UX terkunci.
    if not bool(st.session_state.get("dark_mode", False)):
        st.markdown(
            """
            <style>
                :root {
                    --dataset-light-bg: #F6F7F9;
                    --dataset-light-card: #FFFFFF;
                    --dataset-light-soft: #F8FAFC;
                    --dataset-light-soft-2: #F1F5F9;
                    --dataset-light-border: #E2E8F0;
                    --dataset-light-border-strong: #CBD5E1;
                    --dataset-light-text: #1F2937;
                    --dataset-light-title: #111827;
                    --dataset-light-muted: #64748B;
                    --dataset-light-subtle: #94A3B8;
                    --dataset-light-shadow: 0 12px 30px rgba(15, 23, 42, 0.08);
                }

                div[data-testid="stAppViewContainer"] {
                    background: var(--dataset-light-bg) !important;
                }

                div[data-testid="stAppViewContainer"] .main .block-container {
                    color: var(--dataset-light-text) !important;
                }

                .dataset-v6-filter-title,
                .dataset-v6-section-title,
                .dataset-v6-table-title,
                .dataset-v16-upload-title,
                .dataset-v16-preview-title,
                .dataset-v16-columns-title,
                .dataset-v18-output-heading-title,
                .dataset-v18-platform-title,
                .dataset-v18-platform-name,
                .dataset-v18-sentiment-section-title,
                .dataset-v18-chart-card-title,
                .dataset-v20-wordcloud-title,
                .dataset-v20-wordcloud-canvas-title,
                .dataset-v21-topic-title,
                .dataset-v21-topic-name,
                .dataset-v21-topic-chart-title,
                .dataset-v22-title,
                .dataset-v22-card-value,
                .dataset-v22-section-title,
                .dataset-v22-sub-title {
                    color: var(--dataset-light-title) !important;
                }

                .dataset-v6-metric-label,
                .dataset-v6-metric-note,
                .dataset-v6-pagination-info,
                .dataset-v6-info-text,
                .dataset-v6-active-source-name,
                .dataset-v6-sna-note,
                .dataset-v6-sna-note-body,
                .dataset-v16-upload-subtitle,
                .dataset-v16-file-detail,
                .dataset-v16-analysis-ready-note,
                .dataset-v16-preview-note,
                .dataset-v16-metric-label,
                .dataset-v16-metric-note,
                .dataset-v18-output-heading-note,
                .dataset-v18-metric-label,
                .dataset-v18-metric-note,
                .dataset-v18-platform-subtitle,
                .dataset-v18-platform-share,
                .dataset-v18-sentiment-section-note,
                .dataset-v18-chart-card-subtitle,
                .dataset-v18-chart-card-hint,
                .dataset-v19-signal-label,
                .dataset-v19-lab-hint,
                .dataset-v20-wordcloud-subtitle,
                .dataset-v20-wordcloud-stat small,
                .dataset-v20-wordcloud-canvas-note,
                .dataset-v20-wordcloud-chip-label,
                .dataset-v21-topic-subtitle,
                .dataset-v21-topic-share,
                .dataset-v21-topic-chart-note,
                .dataset-v21-topic-hint,
                .dataset-v22-subtitle,
                .dataset-v22-card-kicker,
                .dataset-v22-card-note,
                .dataset-v22-section-note,
                .dataset-v22-sub-note {
                    color: var(--dataset-light-muted) !important;
                }

                div[data-testid="stMarkdownContainer"] h1,
                div[data-testid="stMarkdownContainer"] h2,
                div[data-testid="stMarkdownContainer"] h3,
                div[data-testid="stMarkdownContainer"] h4 {
                    color: var(--dataset-light-title) !important;
                }

                /* Hero Dataset tetap memakai identitas merah, tetapi seluruh
                   teks dan badge dibuat kontras saat Light Mode aktif. */
                .dataset-v6-hero h1 {
                    color: #FFFFFF !important;
                    text-shadow: 0 2px 10px rgba(80, 8, 8, 0.18);
                }

                .dataset-v6-hero p {
                    color: rgba(255, 255, 255, 0.96) !important;
                }

                .dataset-v6-source-badge {
                    background: rgba(255, 255, 255, 0.94) !important;
                    border-color: rgba(255, 255, 255, 0.88) !important;
                    box-shadow: 0 6px 16px rgba(80, 8, 8, 0.14);
                    color: #1F2937 !important;
                }

                .dataset-v6-source-real {
                    background: #F0FDF4 !important;
                    border-color: #86EFAC !important;
                    color: #166534 !important;
                }

                .dataset-v6-source-dummy {
                    background: #FFFBEB !important;
                    border-color: #FCD34D !important;
                    color: #92400E !important;
                }

                /* Form, selectbox, input pencarian, dan dropdown. */
                div[data-testid="stForm"] {
                    background: var(--dataset-light-card) !important;
                    border: 1px solid var(--dataset-light-border) !important;
                    box-shadow: var(--dataset-light-shadow) !important;
                }

                div[data-testid="stSelectbox"] label,
                div[data-testid="stTextInput"] label,
                div[data-testid="stNumberInput"] label,
                div[data-testid="stSlider"] label,
                div[data-testid="stRadio"] label,
                div[data-testid="stFileUploader"] label {
                    color: #475569 !important;
                }

                div[data-testid="stSelectbox"] div[data-baseweb="select"] > div,
                div[data-testid="stTextInput"] input,
                div[data-testid="stNumberInput"] input {
                    background: var(--dataset-light-card) !important;
                    border-color: var(--dataset-light-border-strong) !important;
                    color: var(--dataset-light-text) !important;
                    box-shadow: none !important;
                }

                div[data-testid="stSelectbox"] div[data-baseweb="select"] > div:hover,
                div[data-testid="stTextInput"] input:hover,
                div[data-testid="stNumberInput"] input:hover {
                    background: var(--dataset-light-soft) !important;
                    border-color: #94A3B8 !important;
                }

                div[data-testid="stTextInput"] input::placeholder,
                div[data-testid="stNumberInput"] input::placeholder {
                    color: #94A3B8 !important;
                }

                div[data-testid="stSelectbox"] svg {
                    fill: #64748B !important;
                }

                div[data-testid="stSelectbox"]:hover svg {
                    fill: #1F2937 !important;
                }

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
                [data-baseweb="menu"] > * > *,
                [role="listbox"] {
                    background: var(--dataset-light-card) !important;
                    background-color: var(--dataset-light-card) !important;
                    background-image: none !important;
                    color: var(--dataset-light-text) !important;
                }

                [data-baseweb="popover"],
                [data-testid="stSelectboxVirtualDropdown"] {
                    border-color: var(--dataset-light-border) !important;
                    box-shadow: 0 16px 40px rgba(15, 23, 42, 0.14) !important;
                }

                [data-baseweb="popover"] [role="listbox"],
                [data-testid="stSelectboxVirtualDropdown"] [role="listbox"],
                ul[role="listbox"],
                div[role="listbox"] {
                    scrollbar-color: #CBD5E1 #F8FAFC !important;
                }

                [data-baseweb="popover"] [role="option"],
                [data-testid="stSelectboxVirtualDropdown"] [role="option"],
                li[role="option"],
                div[role="option"] {
                    background: var(--dataset-light-card) !important;
                    color: var(--dataset-light-text) !important;
                }

                [data-baseweb="popover"] [role="option"]:hover,
                [data-testid="stSelectboxVirtualDropdown"] [role="option"]:hover,
                li[role="option"]:hover,
                div[role="option"]:hover {
                    background: var(--dataset-light-soft-2) !important;
                    border-color: var(--dataset-light-border) !important;
                    color: var(--dataset-light-title) !important;
                }

                [data-baseweb="popover"] [role="option"][aria-selected="true"],
                [data-testid="stSelectboxVirtualDropdown"] [role="option"][aria-selected="true"],
                li[role="option"][aria-selected="true"],
                div[role="option"][aria-selected="true"] {
                    background: linear-gradient(90deg, rgba(229,57,53,0.12), #FFF7F7 38%) !important;
                    border-color: rgba(229,57,53,0.24) !important;
                    color: #991B1B !important;
                }

                /* Tombol reset menjadi tombol netral pada latar terang. */
                div[data-testid="stColumn"]:has(.dataset-v10-reset-marker)
                div[data-testid="stFormSubmitButton"] button {
                    background: #F1F5F9 !important;
                    border-color: #CBD5E1 !important;
                    color: #1F2937 !important;
                }

                div[data-testid="stColumn"]:has(.dataset-v10-reset-marker)
                div[data-testid="stFormSubmitButton"] button p,
                div[data-testid="stColumn"]:has(.dataset-v10-reset-marker)
                div[data-testid="stFormSubmitButton"] button span {
                    color: #1F2937 !important;
                }

                div[data-testid="stColumn"]:has(.dataset-v10-reset-marker)
                div[data-testid="stFormSubmitButton"] button:hover {
                    background: #E2E8F0 !important;
                    border-color: #94A3B8 !important;
                    box-shadow: 0 8px 18px rgba(15,23,42,0.08) !important;
                }

                /* Ringkasan data. */
                .dataset-v6-metric-card,
                .dataset-v6-sna-note {
                    background: var(--dataset-light-card) !important;
                    border-color: var(--dataset-light-border) !important;
                    box-shadow: 0 10px 24px rgba(15,23,42,0.06) !important;
                }

                .dataset-v6-metric-label {
                    color: #475569 !important;
                }

                .dataset-v6-metric-note,
                .dataset-v6-sna-note-body {
                    color: #64748B !important;
                }

                .dataset-v6-sna-note-title {
                    color: var(--dataset-light-title) !important;
                }

                /* Tabel utama. */
                .dataset-v6-table-shell {
                    background: var(--dataset-light-card) !important;
                    border-color: var(--dataset-light-border) !important;
                    box-shadow: var(--dataset-light-shadow) !important;
                }

                .dataset-v6-table {
                    color: var(--dataset-light-text) !important;
                }

                .dataset-v6-table thead th {
                    background: #F1F5F9 !important;
                    border-bottom-color: #CBD5E1 !important;
                    color: #334155 !important;
                }

                .dataset-v6-table tbody td {
                    background: var(--dataset-light-card) !important;
                    border-bottom-color: #E2E8F0 !important;
                    color: #334155 !important;
                }

                .dataset-v6-table tbody tr:hover td,
                .dataset-v6-table tbody tr.dataset-v6-row-positive:hover td,
                .dataset-v6-table tbody tr.dataset-v6-row-neutral:hover td,
                .dataset-v6-table tbody tr.dataset-v6-row-negative:hover td {
                    background: #F8FAFC !important;
                }

                /*
                 * Light Mode memakai baris putih yang netral. Informasi sentimen
                 * tetap dibedakan melalui badge, sehingga tabel lebih bersih dan
                 * tidak terlihat merah atau kuning pada latar halaman terang.
                 */
                .dataset-v6-table tbody tr.dataset-v6-row-positive td,
                .dataset-v6-table tbody tr.dataset-v6-row-neutral td,
                .dataset-v6-table tbody tr.dataset-v6-row-negative td {
                    background: #FFFFFF !important;
                }

                .dataset-v6-table tbody tr.dataset-v6-row-positive:hover td,
                .dataset-v6-table tbody tr.dataset-v6-row-neutral:hover td,
                .dataset-v6-table tbody tr.dataset-v6-row-negative:hover td {
                    background: #F8FAFC !important;
                }

                .dataset-v6-confidence-cell {
                    color: #475569 !important;
                    font-weight: 600 !important;
                }

                .dataset-v6-sentiment-badge {
                    border: 1px solid transparent !important;
                    box-shadow: 0 3px 8px rgba(15, 23, 42, 0.10) !important;
                    letter-spacing: 0.01em !important;
                }

                .dataset-v6-badge-positive {
                    background: #43A047 !important;
                    border-color: #388E3C !important;
                    color: #FFFFFF !important;
                }

                .dataset-v6-badge-neutral {
                    background: #FF9800 !important;
                    border-color: #F57C00 !important;
                    color: #2B2100 !important;
                }

                .dataset-v6-badge-negative {
                    background: #EF3E3A !important;
                    border-color: #D92F2B !important;
                    color: #FFFFFF !important;
                }

                /* Ikon bantuan pada kontrol Baris per halaman mengikuti tema terang. */
                div[data-testid="stHorizontalBlock"]:has(.dataset-v6-table-title)
                div[data-testid="stSelectbox"] [data-testid="stTooltipIcon"] {
                    align-items: center !important;
                    background: #FFFFFF !important;
                    border: 1px solid #CBD5E1 !important;
                    border-radius: 999px !important;
                    box-shadow: 0 2px 6px rgba(15,23,42,0.08) !important;
                    color: #64748B !important;
                    display: inline-flex !important;
                    height: 20px !important;
                    justify-content: center !important;
                    min-height: 20px !important;
                    min-width: 20px !important;
                    padding: 0 !important;
                    width: 20px !important;
                }

                div[data-testid="stHorizontalBlock"]:has(.dataset-v6-table-title)
                div[data-testid="stSelectbox"] [data-testid="stTooltipIcon"] button,
                div[data-testid="stHorizontalBlock"]:has(.dataset-v6-table-title)
                div[data-testid="stSelectbox"] [data-testid="stTooltipHoverTarget"] {
                    background: transparent !important;
                    border: 0 !important;
                    box-shadow: none !important;
                    color: #64748B !important;
                }

                div[data-testid="stHorizontalBlock"]:has(.dataset-v6-table-title)
                div[data-testid="stSelectbox"] [data-testid="stTooltipIcon"] svg {
                    fill: #64748B !important;
                    color: #64748B !important;
                }

                div[data-testid="stHorizontalBlock"]:has(.dataset-v6-table-title)
                div[data-testid="stSelectbox"] [data-testid="stTooltipIcon"]:hover {
                    background: #FEE2E2 !important;
                    border-color: #FCA5A5 !important;
                    color: #B91C1C !important;
                }

                div[data-testid="stHorizontalBlock"]:has(.dataset-v6-table-title)
                div[data-testid="stSelectbox"] [data-testid="stTooltipIcon"]:hover svg {
                    fill: #B91C1C !important;
                    color: #B91C1C !important;
                }

                /* Hilangkan background gelap yang menempel pada ikon panah selectbox. */
                div[data-testid="stHorizontalBlock"]:has(.dataset-v6-table-title)
                div[data-testid="stSelectbox"] div[data-baseweb="select"] svg {
                    background: transparent !important;
                    border: 0 !important;
                    border-radius: 0 !important;
                    box-shadow: none !important;
                    fill: #334155 !important;
                    color: #334155 !important;
                }

                .dataset-v6-empty-row,
                .dataset-v6-pagination-info,
                .dataset-v6-info-text {
                    color: var(--dataset-light-muted) !important;
                }

                .dataset-v6-legend-item {
                    background: var(--dataset-light-card) !important;
                    border-color: var(--dataset-light-border) !important;
                }

                .dataset-v6-legend-label {
                    color: #475569 !important;
                }

                /* Tombol Layar Penuh pada Distribusi Cepat mengikuti Light Mode. */
                div[data-testid="stColumn"]:has(.dataset-v6-chart-action-marker)
                div[data-testid="stButton"] button {
                    background: #FFFFFF !important;
                    border: 1px solid #CBD5E1 !important;
                    box-shadow: 0 4px 12px rgba(15,23,42,0.08) !important;
                    color: #334155 !important;
                }

                div[data-testid="stColumn"]:has(.dataset-v6-chart-action-marker)
                div[data-testid="stButton"] button p,
                div[data-testid="stColumn"]:has(.dataset-v6-chart-action-marker)
                div[data-testid="stButton"] button span {
                    color: #334155 !important;
                }

                div[data-testid="stColumn"]:has(.dataset-v6-chart-action-marker)
                div[data-testid="stButton"] button:hover {
                    background: #FEF2F2 !important;
                    border-color: #E53935 !important;
                    box-shadow: 0 6px 16px rgba(229,57,53,0.14) !important;
                    color: #B91C1C !important;
                }

                div[data-testid="stColumn"]:has(.dataset-v6-chart-action-marker)
                div[data-testid="stButton"] button:hover p,
                div[data-testid="stColumn"]:has(.dataset-v6-chart-action-marker)
                div[data-testid="stButton"] button:hover span {
                    color: #B91C1C !important;
                }

                div[data-testid="stColumn"]:has(.dataset-v6-chart-action-marker)
                div[data-testid="stButton"] button:focus-visible {
                    border-color: #E53935 !important;
                    box-shadow: 0 0 0 3px rgba(229,57,53,0.16) !important;
                    outline: none !important;
                }

                /* Expander Dataset dan Upload Dataset. */
                [data-testid="stExpander"],
                [data-testid="stExpander"] > details,
                details[data-testid="stExpander"] {
                    background: var(--dataset-light-card) !important;
                    background-color: var(--dataset-light-card) !important;
                    border-color: var(--dataset-light-border) !important;
                    box-shadow: 0 10px 26px rgba(15,23,42,0.07) !important;
                }

                [data-testid="stExpander"] summary,
                [data-testid="stExpander"] > details > summary,
                details[data-testid="stExpander"] > summary {
                    background: var(--dataset-light-soft) !important;
                    background-color: var(--dataset-light-soft) !important;
                    border-bottom-color: var(--dataset-light-border) !important;
                    color: var(--dataset-light-title) !important;
                }

                [data-testid="stExpander"] summary:hover,
                [data-testid="stExpander"] summary:focus-visible {
                    background: var(--dataset-light-soft-2) !important;
                    background-color: var(--dataset-light-soft-2) !important;
                }

                [data-testid="stExpander"] summary [data-testid="stMarkdownContainer"],
                [data-testid="stExpander"] summary [data-testid="stMarkdownContainer"] p,
                [data-testid="stExpander"] summary [data-testid="stMarkdownContainer"] span {
                    color: var(--dataset-light-title) !important;
                }

                [data-testid="stExpander"] [data-testid="stExpanderDetails"] {
                    background: var(--dataset-light-card) !important;
                    color: var(--dataset-light-text) !important;
                }

                div[data-baseweb="popover"]:has([data-testid="stTooltipContent"]) > div,
                div[data-baseweb="popover"]:has([data-testid="stTooltipContent"]) > div > div,
                div[data-testid="stTooltipContent"],
                .stTooltipContent {
                    background: var(--dataset-light-card) !important;
                    background-color: var(--dataset-light-card) !important;
                    border-color: var(--dataset-light-border) !important;
                    color: var(--dataset-light-text) !important;
                    box-shadow: 0 12px 28px rgba(15,23,42,0.14) !important;
                }

                div[data-testid="stTooltipContent"] *,
                .stTooltipContent * {
                    color: var(--dataset-light-text) !important;
                }

                /* Upload Dataset Sendiri. */
                div[data-testid="stExpander"]:has(.dataset-v16-upload-anchor),
                div[data-testid="stExpander"]:has(.dataset-v16-upload-anchor) details > summary,
                div[data-testid="stExpander"]:has(.dataset-v16-upload-anchor)
                div[data-testid="stExpanderDetails"] {
                    background: var(--dataset-light-card) !important;
                    border-color: var(--dataset-light-border) !important;
                    color: var(--dataset-light-text) !important;
                }

                /*
                 * Judul expander Upload Dataset Sendiri.
                 * Selector ini sengaja dibuat lebih spesifik daripada aturan Dark Mode
                 * agar teks tidak tetap putih saat background Light Mode aktif.
                 */
                div[data-testid="stExpander"]:has(.dataset-v16-upload-anchor)
                details > summary [data-testid="stMarkdownContainer"],
                div[data-testid="stExpander"]:has(.dataset-v16-upload-anchor)
                details > summary [data-testid="stMarkdownContainer"] p,
                div[data-testid="stExpander"]:has(.dataset-v16-upload-anchor)
                details > summary [data-testid="stMarkdownContainer"] span,
                div[data-testid="stExpander"]:has(.dataset-v16-upload-anchor)
                details > summary p,
                div[data-testid="stExpander"]:has(.dataset-v16-upload-anchor)
                details > summary span {
                    color: var(--dataset-light-title) !important;
                    opacity: 1 !important;
                    -webkit-text-fill-color: var(--dataset-light-title) !important;
                }

                div[data-testid="stExpander"]:has(.dataset-v16-upload-anchor)
                details > summary svg {
                    color: #E53935 !important;
                    fill: currentColor !important;
                }

                div[data-testid="stExpander"]:has(.dataset-v16-upload-anchor)
                details[open] > summary svg {
                    color: #B91C1C !important;
                }

                .dataset-v16-upload-intro,
                .dataset-v16-empty-state,
                .dataset-v16-analysis-ready,
                .dataset-v16-columns-section {
                    background: var(--dataset-light-soft) !important;
                    border-color: var(--dataset-light-border) !important;
                    box-shadow: 0 10px 24px rgba(15,23,42,0.05) !important;
                }

                .dataset-v16-upload-title,
                .dataset-v16-file-name,
                .dataset-v16-analysis-ready-title,
                .dataset-v16-preview-title,
                .dataset-v16-columns-title,
                .dataset-v16-empty-state strong {
                    color: var(--dataset-light-title) !important;
                }

                .dataset-v16-upload-subtitle,
                .dataset-v16-file-detail,
                .dataset-v16-analysis-ready-note,
                .dataset-v16-preview-note,
                .dataset-v16-metric-note {
                    color: var(--dataset-light-muted) !important;
                }

                .dataset-v16-upload-chip,
                .dataset-v16-column-badge {
                    background: var(--dataset-light-card) !important;
                    border-color: var(--dataset-light-border) !important;
                    color: #475569 !important;
                }

                div[data-testid="stExpander"]:has(.dataset-v16-upload-anchor)
                [data-testid="stFileUploaderDropzone"] {
                    background: var(--dataset-light-card) !important;
                    border-color: #CBD5E1 !important;
                    color: var(--dataset-light-text) !important;
                }

                div[data-testid="stExpander"]:has(.dataset-v16-upload-anchor)
                [data-testid="stFileUploaderDropzone"] * {
                    color: #475569 !important;
                }

                .dataset-v16-file-strip,
                .dataset-v16-success {
                    background: linear-gradient(90deg, #F0FDF4, #ECFDF5) !important;
                    border-color: #BBF7D0 !important;
                    box-shadow: 0 10px 24px rgba(22,101,52,0.07) !important;
                }

                .dataset-v16-success-title {
                    color: #166534 !important;
                }

                .dataset-v16-success-note {
                    color: #4D7C5C !important;
                }

                .dataset-v16-metric-card {
                    background: var(--dataset-light-card) !important;
                    border-color: var(--dataset-light-border) !important;
                    box-shadow: 0 10px 24px rgba(15,23,42,0.06) !important;
                }

                .dataset-v16-metric-label {
                    color: #475569 !important;
                }

                /* Hasil analisis file upload. */
                .dataset-v18-metric-card,
                .dataset-v18-platform-shell,
                .dataset-v18-platform-card,
                div[data-testid="stVerticalBlockBorderWrapper"]:has(.dataset-v18-chart-card-marker),
                .dataset-v19-sentiment-lab,
                .dataset-v19-signal-card,
                .dataset-v20-wordcloud-section,
                .dataset-v20-wordcloud-stat,
                div[data-testid="stVerticalBlockBorderWrapper"]:has(.dataset-v20-wordcloud-controls-marker),
                div[data-testid="stVerticalBlockBorderWrapper"]:has(.dataset-v20-wordcloud-canvas-marker),
                .dataset-v21-topic-section,
                .dataset-v21-topic-card,
                div[data-testid="stVerticalBlockBorderWrapper"]:has(.dataset-v21-topic-chart-marker) {
                    background: var(--dataset-light-card) !important;
                    background-color: var(--dataset-light-card) !important;
                    background-image: none !important;
                    border-color: var(--dataset-light-border) !important;
                    box-shadow: 0 12px 28px rgba(15,23,42,0.07) !important;
                }

                .dataset-v18-metric-value,
                .dataset-v18-platform-name,
                .dataset-v18-sentiment-section-title,
                .dataset-v18-chart-card-title,
                .dataset-v19-signal-value,
                .dataset-v20-wordcloud-stat strong,
                .dataset-v21-topic-name,
                .dataset-v21-topic-chart-title {
                    color: var(--dataset-light-title) !important;
                }

                .dataset-v18-metric-label,
                .dataset-v18-metric-note,
                .dataset-v18-platform-subtitle,
                .dataset-v18-platform-share,
                .dataset-v18-sentiment-section-note,
                .dataset-v18-chart-card-subtitle,
                .dataset-v18-chart-card-hint,
                .dataset-v19-signal-label,
                .dataset-v19-lab-hint,
                .dataset-v20-wordcloud-subtitle,
                .dataset-v20-wordcloud-stat small,
                .dataset-v20-wordcloud-canvas-note,
                .dataset-v20-wordcloud-chip-label,
                .dataset-v21-topic-subtitle,
                .dataset-v21-topic-share,
                .dataset-v21-topic-chart-note,
                .dataset-v21-topic-hint {
                    color: var(--dataset-light-muted) !important;
                }

                .dataset-v18-platform-track,
                .dataset-v19-signal-track,
                .dataset-v20-wordcloud-chip-row,
                .dataset-v21-topic-track {
                    background-color: #E2E8F0 !important;
                    border-color: var(--dataset-light-border) !important;
                }

                .dataset-v20-wordcloud-chip {
                    background: #F8FAFC !important;
                    border-color: #CBD5E1 !important;
                    color: #334155 !important;
                }

                .dataset-v20-wordcloud-chip b {
                    color: #B91C1C !important;
                }

                div[data-testid="stVerticalBlockBorderWrapper"]:has(.dataset-v20-wordcloud-canvas-marker) img {
                    border-color: var(--dataset-light-border) !important;
                    box-shadow: 0 12px 26px rgba(15,23,42,0.08) !important;
                }

                /* Panel file nonrelevan dan warning. */
                .dataset-v22-shell,
                .dataset-v22-subsection {
                    background: linear-gradient(135deg, #FFFFFF, #F8FAFC) !important;
                    border-color: #E2E8F0 !important;
                    box-shadow: 0 14px 32px rgba(15,23,42,0.08) !important;
                }

                .dataset-v22-card {
                    background: #FFFFFF !important;
                    border-color: #E2E8F0 !important;
                    box-shadow: 0 8px 20px rgba(15,23,42,0.05) !important;
                }

                .dataset-v22-title,
                .dataset-v22-card-value,
                .dataset-v22-section-title,
                .dataset-v22-sub-title {
                    color: var(--dataset-light-title) !important;
                }

                .dataset-v22-subtitle,
                .dataset-v22-card-kicker,
                .dataset-v22-card-note,
                .dataset-v22-section-note,
                .dataset-v22-sub-note {
                    color: var(--dataset-light-muted) !important;
                }

                .dataset-v22-badge,
                .dataset-v22-sub-pill {
                    background: #F8FAFC !important;
                    border-color: #E2E8F0 !important;
                    color: #334155 !important;
                }

                .dataset-v18-warning-card {
                    background: linear-gradient(135deg, #FFFBEB, #FFF7ED) !important;
                    border-color: #FDE68A !important;
                    color: #78350F !important;
                    box-shadow: 0 12px 28px rgba(120,53,15,0.08) !important;
                }

                .dataset-v18-warning-title,
                .dataset-v18-warning-copy,
                .dataset-v18-warning-card strong {
                    color: #78350F !important;
                }

                .dataset-v18-warning-note {
                    color: #92400E !important;
                }

                /* Dialog chart dan WordCloud pada tema terang. */
                div[data-testid="stDialog"],
                div[data-baseweb="modal"] {
                    background: var(--dataset-light-bg) !important;
                    background-color: var(--dataset-light-bg) !important;
                }

                div[data-testid="stDialog"] [role="dialog"],
                div[data-baseweb="modal"] [role="dialog"] {
                    background: var(--dataset-light-bg) !important;
                    background-color: var(--dataset-light-bg) !important;
                    color: var(--dataset-light-text) !important;
                }

                div[data-testid="stDialog"] div[data-testid="stVerticalBlock"]:has(.dataset-v19-fullscreen-marker),
                div[data-baseweb="modal"] div[data-testid="stVerticalBlock"]:has(.dataset-v19-fullscreen-marker),
                div[data-testid="stDialog"] div[data-testid="stVerticalBlock"]:has(.dataset-v20-wordcloud-fullscreen-marker),
                div[data-baseweb="modal"] div[data-testid="stVerticalBlock"]:has(.dataset-v20-wordcloud-fullscreen-marker) {
                    background: var(--dataset-light-bg) !important;
                    background-color: var(--dataset-light-bg) !important;
                    color: var(--dataset-light-text) !important;
                }

                div[data-testid="stDialog"] [data-testid="stPlotlyChart"],
                div[data-baseweb="modal"] [data-testid="stPlotlyChart"] {
                    background: #FFFFFF !important;
                    background-color: #FFFFFF !important;
                    border: 1px solid var(--dataset-light-border) !important;
                    box-shadow: 0 18px 48px rgba(15,23,42,0.12) !important;
                }

                div[data-testid="stDialog"] [data-testid="stPlotlyChart"] .modebar,
                div[data-baseweb="modal"] [data-testid="stPlotlyChart"] .modebar {
                    background: rgba(255,255,255,0.96) !important;
                    border: 1px solid var(--dataset-light-border) !important;
                    border-radius: 8px !important;
                    box-shadow: 0 6px 18px rgba(15,23,42,0.10) !important;
                    padding: 3px 5px !important;
                }

                div[data-testid="stDialog"] [data-testid="stPlotlyChart"] .modebar-btn path,
                div[data-baseweb="modal"] [data-testid="stPlotlyChart"] .modebar-btn path {
                    fill: #475569 !important;
                }

                div[data-testid="stDialog"] [data-testid="stPlotlyChart"] .modebar-btn:hover path,
                div[data-baseweb="modal"] [data-testid="stPlotlyChart"] .modebar-btn:hover path {
                    fill: #E53935 !important;
                }

                div[data-testid="stDialog"] button[aria-label="Close"],
                div[data-baseweb="modal"] button[aria-label="Close"] {
                    background: #FFFFFF !important;
                    border: 1px solid var(--dataset-light-border-strong) !important;
                    box-shadow: 0 8px 20px rgba(15,23,42,0.12) !important;
                    color: #334155 !important;
                }

                div[data-testid="stDialog"] button[aria-label="Close"]:hover,
                div[data-baseweb="modal"] button[aria-label="Close"]:hover {
                    background: #FEF2F2 !important;
                    border-color: #E53935 !important;
                    color: #B91C1C !important;
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
                    "on_bad_lines": "skip",
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

    # Upload hanya mensyaratkan file valid dan memiliki baris data.
    # Nama, jumlah, dan susunan kolom bebas; relevansi diperiksa terpisah.
    return data


def _normalisasi_nama_kolom_upload(nama_kolom: Any) -> str:
    """Normalisasi nama kolom hanya untuk validasi tanpa mengubah DataFrame asli."""
    return re.sub(r"[^a-z0-9]+", "_", str(nama_kolom or "").strip().casefold()).strip("_")


def _validasi_kolom_wajib_upload(data: pd.DataFrame) -> None:
    """Kompatibilitas lama: upload tidak lagi mewajibkan nama kolom tertentu."""
    del data
    return None


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


def _memiliki_keyword_telkom(data: pd.DataFrame, kolom_pemeriksaan: list[Any]) -> bool:
    """Cari keyword Telkom pada nama kolom dan isi file tanpa syarat skema."""
    pola_keyword = "|".join(re.escape(keyword) for keyword in KEYWORD_RELEVANSI_TELKOM)

    try:
        nama_kolom = " ".join(str(kolom) for kolom in data.columns)
        if re.search(pola_keyword, nama_kolom, flags=re.IGNORECASE):
            return True
    except Exception:
        LOGGER.exception("Keyword matching gagal pada nama kolom upload")

    for kolom in kolom_pemeriksaan:
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
    """Bedakan file terkait Telkom dari header dan isi tanpa syarat nama kolom."""
    try:
        kolom_pemeriksaan = list(data.columns)
        lolos_keyword = _memiliki_keyword_telkom(data, kolom_pemeriksaan)

        # Keyword merek yang eksplisit cukup untuk menyatakan file relevan.
        if lolos_keyword:
            return True, "keyword"

        sampel_teks = _ambil_sampel_kolom_teks_terpanjang(
            data,
            kolom_pemeriksaan,
        )
        header_teks = " | ".join(str(kolom) for kolom in data.columns)
        bahan_relevansi = "\n".join(
            bagian for bagian in (header_teks, sampel_teks) if bagian.strip()
        )
        if not bahan_relevansi:
            return False, "tanpa-konten"

        # Import SDK Gemini hanya saat pengguna benar-benar menganalisis file upload.
        # Membuka halaman Dataset tidak lagi memuat dependency Google yang berat.
        from utils.gemini_client import check_data_relevance

        hasil_gemini = check_data_relevance(bahan_relevansi)
        if hasil_gemini is None:
            return False, "keyword"
        return bool(hasil_gemini), "gemini"
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


@st.cache_resource(show_spinner=False)
def _muat_model_sentimen_upload() -> dict[str, Any]:
    """Muat runtime IndoBERT terpusat untuk klasifikasi dataset upload."""
    try:
        # IndoBERT hanya dimuat ketika analisis upload membutuhkannya.
        # Ini mencegah import model ikut memperlambat perpindahan ke Dataset.
        from utils.model_loader import load_indobert

        tokenizer, model, perangkat = load_indobert()
        if tokenizer is None or model is None or perangkat is None:
            raise RuntimeError(
                "Model IndoBERT tidak tersedia dari HuggingFace Hub."
            )
        return {
            "tokenizer": tokenizer,
            "model": model,
            "device": perangkat,
        }
    except Exception as exc:
        raise RuntimeError(
            "Model IndoBERT tidak dapat dimuat. Pastikan internet aktif saat "
            "pemuatan pertama serta transformers dan torch sudah terpasang. "
            f"Detail: {exc}"
        ) from exc


def _prediksi_sentimen_batch_upload(
    teks: list[str],
    ukuran_batch: int = 32,
) -> list[str]:
    """Prediksi banyak teks upload melalui loader IndoBERT terpusat."""
    try:
        daftar_teks = [str(item or "").strip() for item in teks]
        if not daftar_teks:
            return []

        _muat_model_sentimen_upload()
        from utils.model_loader import predict_sentiment_batch

        hasil_model = predict_sentiment_batch(
            daftar_teks,
            batch_size=max(1, int(ukuran_batch)),
        )
        if len(hasil_model) != len(daftar_teks):
            raise RuntimeError(
                "Jumlah hasil prediksi tidak sesuai dengan jumlah teks upload."
            )

        hasil: list[str] = []
        for teks_asli, prediksi in zip(daftar_teks, hasil_model):
            if not teks_asli:
                hasil.append("neutral")
                continue

            label = str(prediksi.get("sentiment", "unknown")).strip().lower()
            if label not in {"positive", "neutral", "negative"}:
                raise RuntimeError(
                    "Model tidak mengembalikan label sentimen yang valid."
                )
            hasil.append(label)
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

        # Analisis sentimen/topik bersifat opsional. File tetap diterima dan
        # dipreview ketika relevan tetapi tidak mempunyai kolom teks yang cocok.
        if is_relevant and kolom_teks and kolom_teks in hasil.columns:
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

            # Klasifikator topik baru diimpor saat analisis upload dijalankan.
            from utils.topic_classifier import classify_topic

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
    """Sesuaikan chart hasil upload dengan tema aktif tanpa mengubah datanya."""
    try:
        mode_gelap = bool(st.session_state.get("dark_mode", False))
        warna_teks = "#F8FAFF" if mode_gelap else "#111827"
        warna_teks_sekunder = "#CDD2DE" if mode_gelap else "#475569"
        warna_grid = "rgba(255,255,255,0.065)" if mode_gelap else "rgba(148,163,184,0.24)"
        warna_garis = "rgba(255,255,255,0.11)" if mode_gelap else "#CBD5E1"
        warna_hover = "#151A24" if mode_gelap else "#FFFFFF"
        warna_hover_border = "rgba(255,255,255,0.14)" if mode_gelap else "#CBD5E1"
        warna_menu = "rgba(17,21,30,0.94)" if mode_gelap else "rgba(255,255,255,0.98)"
        warna_menu_border = "rgba(142,114,255,0.34)" if mode_gelap else "#CBD5E1"
        warna_menu_teks = "#F4F1FF" if mode_gelap else "#1F2937"

        figur.update_layout(
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
            font={"color": warna_teks},
            margin={"l": 20, "r": 20, "t": 50, "b": 30},
            hoverlabel={
                "bgcolor": warna_hover,
                "bordercolor": warna_hover_border,
                "font": {"color": warna_teks, "size": 12},
            },
            legend={
                "font": {"color": warna_teks_sekunder},
                "bgcolor": "rgba(0,0,0,0)",
            },
        )
        figur.update_xaxes(
            tickfont={"color": warna_teks_sekunder},
            title_font={"color": warna_teks_sekunder},
            gridcolor=warna_grid,
            linecolor=warna_garis,
            zerolinecolor=warna_garis,
        )
        figur.update_yaxes(
            tickfont={"color": warna_teks_sekunder},
            title_font={"color": warna_teks_sekunder},
            gridcolor=warna_grid,
            linecolor=warna_garis,
            zerolinecolor=warna_garis,
        )

        for menu in list(figur.layout.updatemenus or []):
            ukuran_font = 10
            try:
                ukuran_font = int(menu.font.size or 10)
            except (TypeError, ValueError):
                ukuran_font = 10
            menu.update(
                bgcolor=warna_menu,
                bordercolor=warna_menu_border,
                borderwidth=1,
                font={"color": warna_menu_teks, "size": ukuran_font},
            )

        for anotasi in list(figur.layout.annotations or []):
            teks_anotasi = str(anotasi.text or "")
            if mode_gelap:
                teks_anotasi = (
                    teks_anotasi
                    .replace("#64748B", "#8B93A2")
                    .replace("#111827", "#FFFFFF")
                )
            else:
                teks_anotasi = (
                    teks_anotasi
                    .replace("#8B93A2", "#64748B")
                    .replace("#FFFFFF", "#111827")
                )
            anotasi.text = teks_anotasi
            anotasi.font = {
                "color": warna_teks,
                "size": int(getattr(anotasi.font, "size", None) or 12),
            }

        for jejak in figur.data:
            if getattr(jejak, "type", "") == "pie":
                jejak.marker.line.color = "#111620" if mode_gelap else "#FFFFFF"
                jejak.marker.line.width = 3
            elif getattr(jejak, "type", "") in {"bar", "histogram"}:
                jejak.marker.line.color = (
                    "rgba(255,255,255,0.16)"
                    if mode_gelap
                    else "rgba(255,255,255,0.92)"
                )
                jejak.marker.line.width = 1

        return figur
    except Exception as exc:
        st.error(f"Konfigurasi tema chart upload gagal diterapkan: {exc}")
        return figur


def _render_wordcloud_upload(
    teks: pd.Series,
    max_words: int,
    colormap: str,
    random_state: int = 42,
    *,
    mode_layar_penuh: bool = False,
) -> None:
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

        lebar_wordcloud = 1900 if mode_layar_penuh else 1600
        tinggi_wordcloud = 820 if mode_layar_penuh else 680

        mode_gelap = bool(st.session_state.get("dark_mode", False))
        warna_latar_wordcloud = "#111722" if mode_gelap else "#F8FAFC"

        wordcloud = WordCloud(
            width=lebar_wordcloud,
            height=tinggi_wordcloud,
            background_color=warna_latar_wordcloud,
            max_words=max_words,
            colormap=colormap,
            collocations=False,
            random_state=max(int(random_state), 1),
            prefer_horizontal=0.92,
            margin=3,
            min_font_size=12,  # FIX: ukuran kata minimum tetap terbaca di tablet
        ).generate(gabungan_teks)

        ukuran_figur = (19, 8.2) if mode_layar_penuh else (10, 5)  # FIX: rasio WordCloud 2:1 agar stabil di tablet
        figur, axes = plt.subplots(figsize=ukuran_figur, facecolor=warna_latar_wordcloud)
        axes.imshow(wordcloud, interpolation="bilinear")
        axes.axis("off")
        figur.patch.set_facecolor(warna_latar_wordcloud)
        figur.tight_layout(pad=0.12)
        _pyplot_aman(figur, clear_figure=True, **_opsi_lebar_penuh(st.pyplot))
        plt.close(figur)
    except Exception as exc:
        LOGGER.exception("WordCloud upload gagal dibuat")
        st.error(f"WordCloud tidak dapat ditampilkan. Detail: {exc}")


@_DIALOG_DECORATOR(" ", width="large")
def _tampilkan_wordcloud_layar_penuh(
    teks: pd.Series,
    max_words: int,
    colormap: str,
    random_state: int,
) -> None:
    """Tampilkan WordCloud pada dialog yang memenuhi seluruh viewport."""
    try:
        st.markdown(
            '<span class="dataset-v20-wordcloud-fullscreen-marker" aria-hidden="true"></span>',
            unsafe_allow_html=True,
        )
        _render_wordcloud_upload(
            teks,
            max_words=max_words,
            colormap=colormap,
            random_state=random_state,
            mode_layar_penuh=True,
        )
    except Exception as exc:
        LOGGER.exception("WordCloud layar penuh gagal ditampilkan")
        st.error(
            "WordCloud belum dapat dibuka dalam layar penuh. "
            "Silakan tutup tampilan ini lalu coba kembali."
        )
        st.code(str(exc))


def _statistik_wordcloud_upload(
    teks: pd.Series,
) -> tuple[int, int, list[tuple[str, int]]]:
    """Hitung statistik ringkas untuk panel WordCloud upload."""
    try:
        gabungan = " ".join(
            teks.fillna("").astype(str).str.strip().loc[lambda nilai: nilai.ne("")].tolist()
        ).lower()
        token = re.findall(r"(?u)\b[a-zA-ZÀ-ÿ][a-zA-ZÀ-ÿ0-9_]{1,}\b", gabungan)
        if not token:
            return 0, 0, []

        frekuensi = pd.Series(token, dtype="object").value_counts()
        teratas = [(str(kata), int(jumlah)) for kata, jumlah in frekuensi.head(6).items()]
        return int(len(token)), int(frekuensi.size), teratas
    except Exception:
        LOGGER.exception("Statistik WordCloud upload gagal dihitung")
        return 0, 0, []


def _siapkan_loading_wordcloud_upload() -> None:
    """Siapkan custom loading saat kontrol WordCloud diubah."""
    st.session_state[STATE_WORDCLOUD_LOADING_LABEL] = (
        "Menyusun ulang WordCloud interaktif..."
    )


def _acak_tata_letak_wordcloud_upload() -> None:
    """Ubah random seed agar tata letak WordCloud dapat diacak ulang."""
    seed_lama = int(st.session_state.get(STATE_WORDCLOUD_SEED, 42))
    st.session_state[STATE_WORDCLOUD_SEED] = (seed_lama + 37) % 10000 or 42
    _siapkan_loading_wordcloud_upload()


def _render_wordcloud_interaktif_upload(
    teks: pd.Series,
    *,
    judul: str = "WordCloud Interaktif",
    subjudul: str = (
        "Eksplorasi kata dominan dengan palet warna, kepadatan, dan tata letak yang dapat diubah."
    ),
) -> None:
    """Render area WordCloud upload yang berwarna, animatif, dan interaktif."""
    try:
        konfigurasi_palet = {
            "Telkom Merah": {
                "colormap": "Reds",
                "accent": "#FF4D48",
                "soft": "rgba(244,67,54,0.18)",
                "border": "rgba(244,67,54,0.42)",
                "icon": "✦",
            },
            "Neon Spektrum": {
                "colormap": "plasma",
                "accent": "#B67CFF",
                "soft": "rgba(182,124,255,0.18)",
                "border": "rgba(182,124,255,0.42)",
                "icon": "◈",
            },
            "Digital Biru": {
                "colormap": "cool",
                "accent": "#38D7FF",
                "soft": "rgba(56,215,255,0.16)",
                "border": "rgba(56,215,255,0.38)",
                "icon": "◎",
            },
            "Emerald Insight": {
                "colormap": "viridis",
                "accent": "#5DE2A5",
                "soft": "rgba(93,226,165,0.16)",
                "border": "rgba(93,226,165,0.38)",
                "icon": "◇",
            },
        }

        if STATE_WORDCLOUD_SEED not in st.session_state:
            st.session_state[STATE_WORDCLOUD_SEED] = 42

        palet_aktif = str(
            st.session_state.get(STATE_WORDCLOUD_PALETTE, "Telkom Merah")
        )
        if palet_aktif not in konfigurasi_palet:
            palet_aktif = "Telkom Merah"
        max_words_aktif = int(st.session_state.get(STATE_WORDCLOUD_MAX_WORDS, 150))
        konfigurasi_aktif = konfigurasi_palet[palet_aktif]

        total_token, jumlah_unik, kata_teratas = _statistik_wordcloud_upload(teks)
        kata_dominan = kata_teratas[0][0] if kata_teratas else "Belum tersedia"
        frekuensi_dominan = kata_teratas[0][1] if kata_teratas else 0
        rasio_unik = (jumlah_unik / max(total_token, 1)) * 100

        st.markdown(
            f"""
            <section class="dataset-v20-wordcloud-section" tabindex="0"
                style="--wc-accent:{konfigurasi_aktif['accent']};
                       --wc-soft:{konfigurasi_aktif['soft']};
                       --wc-border:{konfigurasi_aktif['border']};">
                <div class="dataset-v20-wordcloud-header-left">
                    <div class="dataset-v20-wordcloud-icon">{escape(str(konfigurasi_aktif['icon']))}</div>
                    <div>
                        <div class="dataset-v20-wordcloud-title">{escape(judul)}</div>
                        <div class="dataset-v20-wordcloud-subtitle">{escape(subjudul)}</div>
                    </div>
                </div>
                <div class="dataset-v20-wordcloud-live-badge">
                    <span></span>
                    {escape(palet_aktif)} · {max_words_aktif} kata
                </div>
            </section>
            <div class="dataset-v20-wordcloud-stat-grid">
                <div class="dataset-v20-wordcloud-stat dataset-v20-wordcloud-stat-red" tabindex="0">
                    <div class="dataset-v20-wordcloud-stat-top">
                        <span>Total Token</span><b>Σ</b>
                    </div>
                    <strong>{_format_angka(total_token)}</strong>
                    <small>Seluruh kata yang terbaca</small>
                </div>
                <div class="dataset-v20-wordcloud-stat dataset-v20-wordcloud-stat-purple" tabindex="0">
                    <div class="dataset-v20-wordcloud-stat-top">
                        <span>Kata Unik</span><b>✧</b>
                    </div>
                    <strong>{_format_angka(jumlah_unik)}</strong>
                    <small>{rasio_unik:.1f}% variasi kosakata</small>
                </div>
                <div class="dataset-v20-wordcloud-stat dataset-v20-wordcloud-stat-cyan" tabindex="0">
                    <div class="dataset-v20-wordcloud-stat-top">
                        <span>Kata Dominan</span><b>↗</b>
                    </div>
                    <strong>{escape(kata_dominan)}</strong>
                    <small>Muncul {_format_angka(frekuensi_dominan)} kali</small>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        with st.container(border=True):
            st.markdown(
                '<span class="dataset-v20-wordcloud-controls-marker"></span>',
                unsafe_allow_html=True,
            )
            kolom_palet, kolom_kepadatan, kolom_acak = st.columns(
                [1.2, 1.25, 0.82], gap="medium"
            )
            with kolom_palet:
                st.selectbox(
                    "Palet warna",
                    options=list(konfigurasi_palet.keys()),
                    index=list(konfigurasi_palet.keys()).index(palet_aktif),
                    key=STATE_WORDCLOUD_PALETTE,
                    on_change=_siapkan_loading_wordcloud_upload,
                    help="Ubah warna WordCloud tanpa mengubah isi data.",
                )
            with kolom_kepadatan:
                st.slider(
                    "Jumlah kata",
                    min_value=50,
                    max_value=250,
                    value=max_words_aktif,
                    step=10,
                    key=STATE_WORDCLOUD_MAX_WORDS,
                    on_change=_siapkan_loading_wordcloud_upload,
                    help="Atur banyaknya kata maksimum yang ditampilkan.",
                )
            with kolom_acak:
                st.markdown(
                    '<div class="dataset-v20-wordcloud-action-label">Tata letak</div>',
                    unsafe_allow_html=True,
                )
                st.button(
                    "↻ Acak Ulang",
                    key="dataset_v20_wordcloud_shuffle",
                    on_click=_acak_tata_letak_wordcloud_upload,
                    help="Susun ulang posisi kata menggunakan data yang sama.",
                    **_opsi_lebar_penuh(st.button),
                )

        palet_aktif = str(st.session_state.get(STATE_WORDCLOUD_PALETTE, palet_aktif))
        max_words_aktif = int(
            st.session_state.get(STATE_WORDCLOUD_MAX_WORDS, max_words_aktif)
        )
        konfigurasi_aktif = konfigurasi_palet.get(
            palet_aktif,
            konfigurasi_palet["Telkom Merah"],
        )

        with st.container(border=True):
            st.markdown(
                '<span class="dataset-v20-wordcloud-canvas-marker"></span>',
                unsafe_allow_html=True,
            )
            kolom_judul_wordcloud, kolom_aksi_wordcloud = st.columns(
                [5.6, 1.25], gap="small"
            )
            with kolom_judul_wordcloud:
                st.markdown(
                    """
                    <div class="dataset-v20-wordcloud-canvas-head">
                        <div>
                            <div class="dataset-v20-wordcloud-canvas-title">Peta Kata Dominan</div>
                            <div class="dataset-v20-wordcloud-canvas-note">
                                Hover gambar untuk efek fokus. Gunakan kontrol di atas untuk mengubah visual.
                            </div>
                        </div>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )
            with kolom_aksi_wordcloud:
                st.markdown(
                    '<span class="dataset-v20-wordcloud-fullscreen-action-marker" '
                    'aria-hidden="true">Perbesar</span>',
                    unsafe_allow_html=True,
                )
                if st.button(
                    "⛶ Layar Penuh",
                    key="dataset_v20_wordcloud_fullscreen",
                    help="Tampilkan WordCloud pada seluruh layar.",
                    on_click=_siapkan_loading_layar_penuh,
                    args=("WordCloud",),
                    **_opsi_lebar_penuh(st.button),
                ):
                    _tampilkan_wordcloud_layar_penuh(
                        teks,
                        max_words=max_words_aktif,
                        colormap=str(konfigurasi_aktif["colormap"]),
                        random_state=int(
                            st.session_state.get(STATE_WORDCLOUD_SEED, 42)
                        ),
                    )

            _render_wordcloud_upload(
                teks,
                max_words=max_words_aktif,
                colormap=str(konfigurasi_aktif["colormap"]),
                random_state=int(st.session_state.get(STATE_WORDCLOUD_SEED, 42)),
            )

            chip_html = "".join(
                (
                    f'<button type="button" class="dataset-v20-wordcloud-chip" '
                    f'aria-label="{escape(kata)} muncul {jumlah} kali">'
                    f'<span>{escape(kata)}</span><b>{_format_angka(jumlah)}</b></button>'
                )
                for kata, jumlah in kata_teratas
            )
            if chip_html:
                st.markdown(
                    f"""
                    <div class="dataset-v20-wordcloud-chip-row">
                        <div class="dataset-v20-wordcloud-chip-label">Kata teratas</div>
                        <div class="dataset-v20-wordcloud-chip-list">{chip_html}</div>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )
    except Exception as exc:
        LOGGER.exception("WordCloud interaktif upload gagal dirender")
        st.error(f"WordCloud interaktif tidak dapat ditampilkan. Detail: {exc}")


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
                font-size: 0.75rem /* FIX: minimum 12px agar terbaca di tablet */;
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
                font-size: 0.75rem /* FIX: minimum 12px agar terbaca di tablet */;
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
                font-size: 0.75rem /* FIX: minimum 12px agar terbaca di tablet */;
                margin-top: 0.12rem;
            }

            .dataset-v18-platform-badge {
                background: rgba(142,114,255,0.12);
                border: 1px solid rgba(142,114,255,0.28);
                border-radius: 999px;
                color: #C4B6FF;
                font-size: 0.75rem /* FIX: minimum 12px agar terbaca di tablet */;
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
                font-size: 0.75rem /* FIX: minimum 12px agar terbaca di tablet */;
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
                font-size: 0.75rem /* FIX: minimum 12px agar terbaca di tablet */;
                margin-top: 0.16rem;
            }

            .dataset-v18-sentiment-dominant {
                background: rgba(229,57,53,0.10);
                border: 1px solid rgba(229,57,53,0.24);
                border-radius: 999px;
                color: #FFAAA7;
                font-size: 0.75rem /* FIX: minimum 12px agar terbaca di tablet */;
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
                font-size: 0.75rem /* FIX: minimum 12px agar terbaca di tablet */;
                margin-top: 0.1rem;
            }

            .dataset-v18-chart-card-badge {
                align-items: center;
                background: var(--v18-chart-soft);
                border: 1px solid rgba(255,255,255,0.11);
                border-radius: 999px;
                color: #D9DDE7;
                display: inline-flex;
                font-size: 0.75rem /* FIX: minimum 12px agar terbaca di tablet */;
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
                font-size: 0.75rem /* FIX: minimum 12px agar terbaca di tablet */;
                gap: 0.38rem;
                margin: -0.38rem 0 0.12rem;
                padding: 0 0.22rem;
            }

            .dataset-v18-chart-card-hint strong {
                color: #969EAD;
                font-weight: 700;
            }


            @keyframes datasetV19AuraDrift {
                0%, 100% { transform: translate3d(-8%, -6%, 0) scale(1); opacity: 0.42; }
                50% { transform: translate3d(12%, 8%, 0) scale(1.16); opacity: 0.72; }
            }

            @keyframes datasetV19BorderFlow {
                0% { background-position: 0% 50%; }
                50% { background-position: 100% 50%; }
                100% { background-position: 0% 50%; }
            }

            @keyframes datasetV19LivePulse {
                0%, 100% { box-shadow: 0 0 0 0 rgba(86,211,100,0.34); transform: scale(1); }
                50% { box-shadow: 0 0 0 8px rgba(86,211,100,0); transform: scale(1.12); }
            }

            @keyframes datasetV19SignalEnter {
                from { opacity: 0; transform: translateY(18px) scale(0.96); }
                to { opacity: 1; transform: translateY(0) scale(1); }
            }

            @keyframes datasetV19SparkDance {
                0%, 100% { transform: scaleY(0.55); opacity: 0.56; }
                50% { transform: scaleY(1); opacity: 1; }
            }

            @keyframes datasetV19TrackGlow {
                0% { transform: translateX(-110%); }
                100% { transform: translateX(210%); }
            }

            @keyframes datasetV19HintBounce {
                0%, 100% { transform: translateX(0); }
                50% { transform: translateX(4px); }
            }

            @keyframes datasetV19CardClick {
                0% { transform: translateY(-5px) scale(1.006); }
                45% { transform: translateY(-2px) scale(0.985); }
                100% { transform: translateY(-5px) scale(1.006); }
            }

            .dataset-v18-sentiment-section {
                background:
                    radial-gradient(circle at 8% 12%, rgba(142,114,255,0.15), transparent 34%),
                    radial-gradient(circle at 95% 0%, rgba(229,57,53,0.13), transparent 34%),
                    linear-gradient(135deg, rgba(24,27,36,0.96), rgba(14,17,23,0.96));
                border: 1px solid rgba(255,255,255,0.085);
                border-radius: 18px;
                box-shadow: 0 18px 42px rgba(0,0,0,0.28);
                margin: 1.65rem 0 0.9rem;
                overflow: hidden;
                padding: 1rem 1.05rem;
                position: relative;
                isolation: isolate;
                transition: border-color 0.28s ease, box-shadow 0.28s ease, transform 0.28s ease;
            }

            .dataset-v18-sentiment-section::before {
                animation: datasetV19AuraDrift 7s ease-in-out infinite;
                background: radial-gradient(circle, rgba(229,57,53,0.20), rgba(142,114,255,0.10) 42%, transparent 72%);
                border-radius: 50%;
                content: '';
                height: 170px;
                pointer-events: none;
                position: absolute;
                right: -48px;
                top: -78px;
                width: 170px;
                z-index: -1;
            }

            .dataset-v18-sentiment-section::after {
                animation: datasetV19BorderFlow 5s linear infinite;
                background: linear-gradient(90deg, #8E72FF, #E53935, #FF9800, #4CAF50, #8E72FF);
                background-size: 240% 100%;
                bottom: 0;
                content: '';
                height: 3px;
                left: 0;
                opacity: 0.9;
                position: absolute;
                right: 0;
            }

            .dataset-v18-sentiment-section:hover,
            .dataset-v18-sentiment-section:focus {
                border-color: rgba(229,57,53,0.28);
                box-shadow: 0 24px 54px rgba(0,0,0,0.34), 0 0 32px rgba(142,114,255,0.10);
                outline: none;
                transform: translateY(-2px);
            }

            .dataset-v18-sentiment-section-icon {
                animation: datasetV18IconFloat 3.1s ease-in-out infinite;
                position: relative;
            }

            .dataset-v18-sentiment-section-icon::after {
                animation: datasetV19LivePulse 2.1s ease-in-out infinite;
                background: #56D364;
                border: 2px solid #171B24;
                border-radius: 50%;
                bottom: -2px;
                content: '';
                height: 9px;
                position: absolute;
                right: -2px;
                width: 9px;
            }

            .dataset-v18-sentiment-dominant {
                align-items: center;
                backdrop-filter: blur(10px);
                display: inline-flex;
                gap: 0.42rem;
                overflow: hidden;
                position: relative;
                transition: transform 0.24s ease, box-shadow 0.24s ease, border-color 0.24s ease;
            }

            .dataset-v18-sentiment-dominant::before {
                animation: datasetV19LivePulse 1.9s ease-in-out infinite;
                background: currentColor;
                border-radius: 50%;
                content: '';
                height: 6px;
                width: 6px;
            }

            .dataset-v18-sentiment-dominant:hover,
            .dataset-v18-sentiment-dominant:focus {
                border-color: currentColor;
                box-shadow: 0 0 24px rgba(229,57,53,0.18);
                outline: none;
                transform: translateY(-2px) scale(1.03);
            }

            .dataset-v19-sentiment-lab {
                background: linear-gradient(145deg, rgba(20,24,33,0.96), rgba(13,16,22,0.98));
                border: 1px solid rgba(255,255,255,0.075);
                border-radius: 18px;
                box-shadow: 0 16px 38px rgba(0,0,0,0.25);
                margin: 0 0 1rem;
                overflow: hidden;
                padding: 0.88rem;
                position: relative;
            }

            .dataset-v19-sentiment-lab::before {
                animation: datasetV19AuraDrift 8s ease-in-out infinite reverse;
                background: radial-gradient(circle, rgba(142,114,255,0.13), transparent 68%);
                content: '';
                height: 210px;
                left: -65px;
                pointer-events: none;
                position: absolute;
                top: -92px;
                width: 210px;
            }

            .dataset-v19-signal-grid {
                display: grid;
                gap: 0.72rem;
                grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
                position: relative;
                z-index: 1;
            }

            .dataset-v19-signal-card {
                --signal-accent: #8E72FF;
                --signal-soft: rgba(142,114,255,0.16);
                --signal-border: rgba(142,114,255,0.34);
                appearance: none;
                animation: datasetV19SignalEnter 0.56s cubic-bezier(.2,.75,.25,1) both;
                background:
                    radial-gradient(circle at 100% 0%, var(--signal-soft), transparent 48%),
                    rgba(255,255,255,0.025);
                border: 1px solid rgba(255,255,255,0.07);
                border-radius: 15px;
                color: #F7F8FC;
                cursor: pointer;
                font-family: 'Plus Jakarta Sans', 'Inter', sans-serif;
                min-height: 116px;
                overflow: hidden;
                padding: 0.84rem 0.9rem 0.78rem;
                position: relative;
                text-align: left;
                transition: transform 0.25s ease, border-color 0.25s ease,
                    box-shadow 0.25s ease, background 0.25s ease;
                width: 100%;
            }

            .dataset-v19-signal-card:nth-child(2) { animation-delay: 0.08s; }
            .dataset-v19-signal-card:nth-child(3) { animation-delay: 0.16s; }

            .dataset-v19-signal-card::before {
                background: linear-gradient(90deg, transparent, rgba(255,255,255,0.16), transparent);
                content: '';
                height: 100%;
                left: -55%;
                pointer-events: none;
                position: absolute;
                top: 0;
                transform: skewX(-18deg);
                transition: left 0.72s ease;
                width: 32%;
            }

            .dataset-v19-signal-card::after {
                background: linear-gradient(90deg, var(--signal-accent), transparent 88%);
                bottom: 0;
                content: '';
                height: 3px;
                left: 0;
                position: absolute;
                width: var(--signal-pct);
            }

            .dataset-v19-signal-card:hover,
            .dataset-v19-signal-card:focus-visible {
                background:
                    radial-gradient(circle at 100% 0%, var(--signal-soft), transparent 58%),
                    rgba(255,255,255,0.045);
                border-color: var(--signal-border);
                box-shadow: 0 18px 36px rgba(0,0,0,0.30), 0 0 26px var(--signal-soft);
                outline: none;
                transform: translateY(-5px) scale(1.012);
            }

            .dataset-v19-signal-card:hover::before,
            .dataset-v19-signal-card:focus-visible::before { left: 128%; }

            .dataset-v19-signal-card:active { transform: translateY(-1px) scale(0.975); }

            .dataset-v19-signal-positive {
                --signal-accent: #56D364;
                --signal-soft: rgba(76,175,80,0.16);
                --signal-border: rgba(76,175,80,0.40);
            }

            .dataset-v19-signal-neutral {
                --signal-accent: #FFB33E;
                --signal-soft: rgba(255,152,0,0.16);
                --signal-border: rgba(255,152,0,0.40);
            }

            .dataset-v19-signal-negative {
                --signal-accent: #FF5C57;
                --signal-soft: rgba(244,67,54,0.16);
                --signal-border: rgba(244,67,54,0.40);
            }

            .dataset-v19-signal-top,
            .dataset-v19-signal-main {
                align-items: center;
                display: flex;
                justify-content: space-between;
                position: relative;
                z-index: 1;
            }

            .dataset-v19-signal-label {
                align-items: center;
                color: #C8CED9;
                display: inline-flex;
                font-size: 0.75rem /* FIX: minimum 12px agar terbaca di tablet */;
                font-weight: 800;
                gap: 0.42rem;
                letter-spacing: 0.01em;
            }

            .dataset-v19-signal-dot {
                background: var(--signal-accent);
                border-radius: 50%;
                box-shadow: 0 0 14px var(--signal-accent);
                height: 8px;
                width: 8px;
            }

            .dataset-v19-signal-pct {
                color: var(--signal-accent);
                font-size: 0.75rem /* FIX: minimum 12px agar terbaca di tablet */;
                font-weight: 900;
                text-shadow: 0 0 18px var(--signal-soft);
            }

            .dataset-v19-signal-main { margin-top: 0.55rem; }

            .dataset-v19-signal-value {
                color: #FFFFFF;
                font-size: clamp(1.45rem, 2.4vw, 2rem);
                font-weight: 900;
                letter-spacing: -0.05em;
                line-height: 1;
            }

            .dataset-v19-spark {
                align-items: flex-end;
                display: inline-flex;
                gap: 3px;
                height: 28px;
            }

            .dataset-v19-spark span {
                animation: datasetV19SparkDance 1.35s ease-in-out infinite;
                background: linear-gradient(180deg, rgba(255,255,255,0.88), var(--signal-accent));
                border-radius: 999px;
                height: 45%;
                transform-origin: bottom;
                width: 4px;
            }

            .dataset-v19-spark span:nth-child(2) { animation-delay: 0.16s; height: 72%; }
            .dataset-v19-spark span:nth-child(3) { animation-delay: 0.32s; height: 100%; }
            .dataset-v19-spark span:nth-child(4) { animation-delay: 0.48s; height: 62%; }

            .dataset-v19-signal-track {
                background: rgba(255,255,255,0.065);
                border-radius: 999px;
                height: 5px;
                margin-top: 0.68rem;
                overflow: hidden;
                position: relative;
                z-index: 1;
            }

            .dataset-v19-signal-track span {
                background: linear-gradient(90deg, var(--signal-accent), rgba(255,255,255,0.88));
                border-radius: inherit;
                display: block;
                height: 100%;
                min-width: 4px;
                position: relative;
                transition: filter 0.22s ease, box-shadow 0.22s ease;
                width: var(--signal-pct);
            }

            .dataset-v19-signal-track span::after {
                animation: datasetV19TrackGlow 2.2s ease-in-out infinite;
                background: linear-gradient(90deg, transparent, rgba(255,255,255,0.85), transparent);
                content: '';
                inset: 0;
                position: absolute;
                width: 42%;
            }

            .dataset-v19-signal-card:hover .dataset-v19-signal-track span,
            .dataset-v19-signal-card:focus-visible .dataset-v19-signal-track span {
                box-shadow: 0 0 16px var(--signal-accent);
                filter: brightness(1.18);
            }

            .dataset-v19-lab-hint {
                align-items: center;
                color: #737A88;
                display: flex;
                font-size: 0.75rem /* FIX: minimum 12px agar terbaca di tablet */;
                gap: 0.4rem;
                margin-top: 0.72rem;
                padding: 0 0.15rem;
                position: relative;
                z-index: 1;
            }

            .dataset-v19-lab-hint span:first-child {
                animation: datasetV19HintBounce 1.5s ease-in-out infinite;
                color: #AFA4FF;
                font-size: 0.76rem;
            }

            div[data-testid="stVerticalBlockBorderWrapper"]:has(.dataset-v18-chart-card-marker)::after {
                background: linear-gradient(120deg, transparent 15%, var(--v18-chart-accent), transparent 48%);
                content: '';
                inset: 0;
                opacity: 0.12;
                pointer-events: none;
                position: absolute;
                transform: translateX(-100%);
                transition: transform 0.9s ease, opacity 0.28s ease;
                z-index: 0;
            }

            div[data-testid="stVerticalBlockBorderWrapper"]:has(.dataset-v18-chart-card-marker):hover::after {
                opacity: 0.32;
                transform: translateX(100%);
            }

            div[data-testid="stVerticalBlockBorderWrapper"]:has(.dataset-v18-chart-card-marker):active {
                animation: datasetV19CardClick 0.32s ease;
            }

            div[data-testid="stVerticalBlockBorderWrapper"]:has(.dataset-v18-chart-card-marker)
            div[data-testid="stPlotlyChart"] {
                border-radius: 14px;
                overflow: hidden;
                transition: filter 0.28s ease, transform 0.28s ease;
            }

            div[data-testid="stVerticalBlockBorderWrapper"]:has(.dataset-v18-chart-card-marker):hover
            div[data-testid="stPlotlyChart"] {
                filter: saturate(1.08) brightness(1.035);
                transform: scale(1.006);
            }

            .dataset-v18-chart-card-hint span:first-child {
                animation: datasetV19HintBounce 1.45s ease-in-out infinite;
                color: var(--v18-chart-accent);
            }



            @keyframes datasetV20WordcloudAura {
                0%, 100% { background-position: 0% 50%; }
                50% { background-position: 100% 50%; }
            }

            @keyframes datasetV20WordcloudFloat {
                0%, 100% { transform: translateY(0) rotate(0deg); }
                50% { transform: translateY(-5px) rotate(-4deg); }
            }

            @keyframes datasetV20WordcloudPulse {
                0%, 100% { opacity: 0.52; transform: scale(0.82); }
                50% { opacity: 1; transform: scale(1.18); }
            }

            @keyframes datasetV20WordcloudScan {
                0% { transform: translateY(-140%); opacity: 0; }
                18% { opacity: 0.42; }
                78% { opacity: 0.16; }
                100% { transform: translateY(420%); opacity: 0; }
            }

            @keyframes datasetV20WordcloudReveal {
                from { opacity: 0; transform: translateY(16px) scale(0.985); }
                to { opacity: 1; transform: translateY(0) scale(1); }
            }

            @keyframes datasetV20WordcloudChip {
                0%, 100% { box-shadow: 0 0 0 rgba(255,255,255,0); }
                50% { box-shadow: 0 0 18px rgba(182,124,255,0.14); }
            }

            .dataset-v20-wordcloud-section {
                --wc-accent: #FF4D48;
                --wc-soft: rgba(244,67,54,0.18);
                --wc-border: rgba(244,67,54,0.42);
                align-items: center;
                animation: datasetV20WordcloudReveal 0.58s cubic-bezier(.2,.75,.25,1) both;
                background:
                    radial-gradient(circle at 7% 22%, var(--wc-soft), transparent 31%),
                    radial-gradient(circle at 94% 18%, rgba(182,124,255,0.13), transparent 32%),
                    linear-gradient(115deg, #181B24, #151923 46%, #11151D);
                border: 1px solid var(--wc-border);
                border-radius: 20px;
                box-shadow: 0 18px 42px rgba(0,0,0,0.28), 0 0 28px var(--wc-soft);
                display: flex;
                justify-content: space-between;
                margin: 1.28rem 0 0.82rem;
                min-height: 96px;
                overflow: hidden;
                padding: 1rem 1.12rem;
                position: relative;
                transition: transform 0.3s ease, border-color 0.3s ease, box-shadow 0.3s ease;
            }

            .dataset-v20-wordcloud-section::before {
                animation: datasetV20WordcloudAura 5.2s ease-in-out infinite;
                background: linear-gradient(90deg, var(--wc-accent), #B67CFF, #38D7FF, var(--wc-accent));
                background-size: 240% 100%;
                content: '';
                height: 3px;
                inset: 0 0 auto;
                position: absolute;
            }

            .dataset-v20-wordcloud-section::after {
                background: var(--wc-accent);
                border-radius: 50%;
                content: '';
                filter: blur(46px);
                height: 90px;
                opacity: 0.11;
                pointer-events: none;
                position: absolute;
                right: -26px;
                top: -30px;
                width: 90px;
            }

            .dataset-v20-wordcloud-section:hover,
            .dataset-v20-wordcloud-section:focus {
                border-color: var(--wc-accent);
                box-shadow: 0 24px 52px rgba(0,0,0,0.36), 0 0 38px var(--wc-soft);
                outline: none;
                transform: translateY(-4px);
            }

            .dataset-v20-wordcloud-header-left {
                align-items: center;
                display: flex;
                gap: 0.82rem;
                min-width: 0;
                position: relative;
                z-index: 1;
            }

            .dataset-v20-wordcloud-icon {
                align-items: center;
                animation: datasetV20WordcloudFloat 3.4s ease-in-out infinite;
                background: linear-gradient(145deg, var(--wc-soft), rgba(255,255,255,0.055));
                border: 1px solid var(--wc-border);
                border-radius: 14px;
                box-shadow: inset 0 1px 0 rgba(255,255,255,0.08), 0 12px 24px rgba(0,0,0,0.22);
                color: var(--wc-accent);
                display: flex;
                flex: 0 0 48px;
                font-size: 1.18rem;
                height: 48px;
                justify-content: center;
                text-shadow: 0 0 18px var(--wc-accent);
            }

            .dataset-v20-wordcloud-title {
                color: #FFFFFF;
                font-size: clamp(1.25rem, 2vw, 1.72rem);
                font-weight: 900;
                letter-spacing: -0.035em;
                line-height: 1.08;
            }

            .dataset-v20-wordcloud-subtitle {
                color: #8E95A3;
                font-size: 0.75rem /* FIX: minimum 12px agar terbaca di tablet */;
                line-height: 1.45;
                margin-top: 0.28rem;
                max-width: 720px;
            }

            .dataset-v20-wordcloud-live-badge {
                align-items: center;
                background: rgba(12,15,22,0.72);
                border: 1px solid var(--wc-border);
                border-radius: 999px;
                color: #DDE2EB;
                display: inline-flex;
                flex: 0 0 auto;
                font-size: 0.75rem /* FIX: minimum 12px agar terbaca di tablet */;
                font-weight: 800;
                gap: 0.42rem;
                padding: 0.54rem 0.76rem;
                position: relative;
                z-index: 1;
            }

            .dataset-v20-wordcloud-live-badge span {
                animation: datasetV20WordcloudPulse 1.65s ease-in-out infinite;
                background: var(--wc-accent);
                border-radius: 50%;
                box-shadow: 0 0 14px var(--wc-accent);
                height: 7px;
                width: 7px;
            }

            .dataset-v20-wordcloud-stat-grid {
                display: grid;
                gap: 0.72rem;
                grid-template-columns: repeat(3, minmax(0, 1fr));
                margin: 0 0 0.86rem;
            }

            .dataset-v20-wordcloud-stat {
                --wc-stat: #FF5A54;
                --wc-stat-soft: rgba(244,67,54,0.14);
                animation: datasetV20WordcloudReveal 0.52s cubic-bezier(.2,.75,.25,1) both;
                background:
                    radial-gradient(circle at 95% 5%, var(--wc-stat-soft), transparent 46%),
                    linear-gradient(145deg, #171C26, #121721);
                border: 1px solid rgba(255,255,255,0.075);
                border-radius: 16px;
                cursor: pointer;
                min-height: 112px;
                overflow: hidden;
                padding: 0.82rem 0.92rem;
                position: relative;
                transition: transform 0.25s ease, border-color 0.25s ease, box-shadow 0.25s ease;
            }

            .dataset-v20-wordcloud-stat::after {
                background: linear-gradient(90deg, var(--wc-stat), transparent);
                bottom: 0;
                content: '';
                height: 3px;
                left: 0;
                position: absolute;
                width: 58%;
            }

            .dataset-v20-wordcloud-stat:hover,
            .dataset-v20-wordcloud-stat:focus {
                border-color: var(--wc-stat);
                box-shadow: 0 18px 34px rgba(0,0,0,0.30), 0 0 24px var(--wc-stat-soft);
                outline: none;
                transform: translateY(-5px) scale(1.012);
            }

            .dataset-v20-wordcloud-stat:active { transform: translateY(-1px) scale(0.98); }
            .dataset-v20-wordcloud-stat-purple { --wc-stat: #B67CFF; --wc-stat-soft: rgba(182,124,255,0.15); }
            .dataset-v20-wordcloud-stat-cyan { --wc-stat: #38D7FF; --wc-stat-soft: rgba(56,215,255,0.14); }

            .dataset-v20-wordcloud-stat-top {
                align-items: center;
                color: #969EAC;
                display: flex;
                font-size: 0.75rem /* FIX: minimum 12px agar terbaca di tablet */;
                font-weight: 800;
                justify-content: space-between;
            }

            .dataset-v20-wordcloud-stat-top b {
                align-items: center;
                background: var(--wc-stat-soft);
                border: 1px solid color-mix(in srgb, var(--wc-stat) 42%, transparent);
                border-radius: 9px;
                color: var(--wc-stat);
                display: flex;
                height: 28px;
                justify-content: center;
                width: 28px;
            }

            .dataset-v20-wordcloud-stat strong {
                color: #FFFFFF;
                display: block;
                font-size: clamp(1.35rem, 2.1vw, 1.8rem);
                font-weight: 900;
                letter-spacing: -0.045em;
                line-height: 1;
                margin-top: 0.58rem;
                overflow: hidden;
                text-overflow: ellipsis;
                white-space: nowrap;
            }

            .dataset-v20-wordcloud-stat small {
                color: #757D8B;
                display: block;
                font-size: 0.75rem /* FIX: minimum 12px agar terbaca di tablet */;
                margin-top: 0.34rem;
            }

            div[data-testid="stVerticalBlockBorderWrapper"]:has(.dataset-v20-wordcloud-controls-marker) {
                background:
                    radial-gradient(circle at 5% 0%, rgba(244,67,54,0.10), transparent 36%),
                    linear-gradient(145deg, #171B24, #131720);
                border-color: rgba(255,255,255,0.085) !important;
                border-radius: 17px !important;
                box-shadow: 0 14px 30px rgba(0,0,0,0.22);
                margin-bottom: 0.85rem;
                overflow: hidden;
                position: relative;
                transition: border-color 0.25s ease, box-shadow 0.25s ease, transform 0.25s ease;
            }

            div[data-testid="stVerticalBlockBorderWrapper"]:has(.dataset-v20-wordcloud-controls-marker):hover {
                border-color: rgba(182,124,255,0.30) !important;
                box-shadow: 0 18px 38px rgba(0,0,0,0.28), 0 0 26px rgba(182,124,255,0.08);
                transform: translateY(-2px);
            }

            .dataset-v20-wordcloud-controls-marker,
            .dataset-v20-wordcloud-canvas-marker { display: none; }

            div[data-testid="stVerticalBlockBorderWrapper"]:has(.dataset-v20-wordcloud-controls-marker)
            label p {
                color: #C9CFDA !important;
                font-size: 0.75rem /* FIX: minimum 12px agar terbaca di tablet */ !important;
                font-weight: 800 !important;
            }

            .dataset-v20-wordcloud-action-label {
                color: #C9CFDA;
                font-size: 0.75rem /* FIX: minimum 12px agar terbaca di tablet */;
                font-weight: 800;
                margin-bottom: 0.48rem;
            }

            div[data-testid="stVerticalBlockBorderWrapper"]:has(.dataset-v20-wordcloud-controls-marker)
            button {
                background: linear-gradient(135deg, rgba(229,57,53,0.20), rgba(182,124,255,0.18)) !important;
                border: 1px solid rgba(229,57,53,0.36) !important;
                border-radius: 11px !important;
                color: #FFFFFF !important;
                font-weight: 800 !important;
                min-height: 40px;
                position: relative;
                transition: transform 0.22s ease, box-shadow 0.22s ease, border-color 0.22s ease !important;
            }

            div[data-testid="stVerticalBlockBorderWrapper"]:has(.dataset-v20-wordcloud-controls-marker)
            button:hover {
                border-color: rgba(182,124,255,0.58) !important;
                box-shadow: 0 10px 24px rgba(0,0,0,0.26), 0 0 20px rgba(182,124,255,0.14) !important;
                transform: translateY(-3px) scale(1.01);
            }

            div[data-testid="stVerticalBlockBorderWrapper"]:has(.dataset-v20-wordcloud-controls-marker)
            button:active { transform: translateY(0) scale(0.96); }

            div[data-testid="stVerticalBlockBorderWrapper"]:has(.dataset-v20-wordcloud-canvas-marker) {
                --wc-accent: #FF4D48;
                animation: datasetV20WordcloudReveal 0.62s cubic-bezier(.2,.75,.25,1) both;
                background:
                    radial-gradient(circle at 50% -20%, rgba(182,124,255,0.14), transparent 44%),
                    linear-gradient(145deg, #151A24, #10141C);
                border-color: rgba(255,255,255,0.09) !important;
                border-radius: 20px !important;
                box-shadow: 0 20px 46px rgba(0,0,0,0.30);
                overflow: hidden;
                position: relative;
                transition: border-color 0.3s ease, box-shadow 0.3s ease, transform 0.3s ease;
            }

            div[data-testid="stVerticalBlockBorderWrapper"]:has(.dataset-v20-wordcloud-canvas-marker)::before {
                animation: datasetV20WordcloudScan 5.8s linear infinite;
                background: linear-gradient(180deg, transparent, rgba(255,255,255,0.06), transparent);
                content: '';
                height: 24%;
                inset: 0;
                pointer-events: none;
                position: absolute;
                z-index: 2;
            }

            div[data-testid="stVerticalBlockBorderWrapper"]:has(.dataset-v20-wordcloud-canvas-marker):hover {
                border-color: rgba(244,67,54,0.34) !important;
                box-shadow: 0 26px 56px rgba(0,0,0,0.38), 0 0 32px rgba(244,67,54,0.10);
                transform: translateY(-4px);
            }

            .dataset-v20-wordcloud-canvas-head {
                align-items: center;
                display: flex;
                justify-content: space-between;
                margin-bottom: 0.72rem;
                position: relative;
                z-index: 3;
            }

            .dataset-v20-wordcloud-fullscreen-action-marker {
                display: none !important;
            }

            div[data-testid="stColumn"]:has(.dataset-v20-wordcloud-fullscreen-action-marker) {
                align-items: flex-start !important;
                display: flex !important;
                justify-content: flex-end !important;
            }

            div[data-testid="stColumn"]:has(.dataset-v20-wordcloud-fullscreen-action-marker)
            div[data-testid="stMarkdown"]:has(.dataset-v20-wordcloud-fullscreen-action-marker),
            div[data-testid="stColumn"]:has(.dataset-v20-wordcloud-fullscreen-action-marker)
            div[data-testid="stMarkdownContainer"]:has(.dataset-v20-wordcloud-fullscreen-action-marker) {
                display: none !important;
                height: 0 !important;
                margin: 0 !important;
                min-height: 0 !important;
                padding: 0 !important;
            }

            div[data-testid="stColumn"]:has(.dataset-v20-wordcloud-fullscreen-action-marker)
            div[data-testid="stButton"] {
                margin: 0 !important;
                padding: 0 !important;
                width: 100% !important;
            }

            div[data-testid="stColumn"]:has(.dataset-v20-wordcloud-fullscreen-action-marker)
            div[data-testid="stButton"] button {
                background: linear-gradient(135deg, rgba(229,57,53,0.20), rgba(182,124,255,0.15)) !important;
                border: 1px solid rgba(229,57,53,0.34) !important;
                border-radius: 10px !important;
                color: #FFFFFF !important;
                font-size: 0.75rem /* FIX: minimum 12px agar terbaca di tablet */ !important;
                font-weight: 800 !important;
                min-height: 38px !important;
                padding: 0.36rem 0.66rem !important;
                transition: transform 0.22s ease, box-shadow 0.22s ease, border-color 0.22s ease !important;
                white-space: nowrap !important;
                width: 100% !important;
            }

            div[data-testid="stColumn"]:has(.dataset-v20-wordcloud-fullscreen-action-marker)
            div[data-testid="stButton"] button:hover {
                border-color: rgba(182,124,255,0.56) !important;
                box-shadow: 0 10px 24px rgba(0,0,0,0.28), 0 0 22px rgba(182,124,255,0.13) !important;
                transform: translateY(-2px);
            }

            div[data-testid="stColumn"]:has(.dataset-v20-wordcloud-fullscreen-action-marker)
            div[data-testid="stButton"] button:active {
                transform: translateY(0) scale(0.96);
            }

            .dataset-v20-wordcloud-canvas-title {
                color: #FFFFFF;
                font-size: 1rem;
                font-weight: 900;
                letter-spacing: -0.025em;
            }

            .dataset-v20-wordcloud-canvas-note {
                color: #7F8795;
                font-size: 0.75rem /* FIX: minimum 12px agar terbaca di tablet */;
                margin-top: 0.2rem;
            }

            div[data-testid="stVerticalBlockBorderWrapper"]:has(.dataset-v20-wordcloud-canvas-marker)
            [data-testid="stElementToolbar"] {
                display: none !important;
            }

            div[data-testid="stVerticalBlockBorderWrapper"]:has(.dataset-v20-wordcloud-canvas-marker)
            img {
                border: 1px solid rgba(255,255,255,0.08);
                border-radius: 16px;
                box-shadow: inset 0 1px 0 rgba(255,255,255,0.04), 0 18px 32px rgba(0,0,0,0.28);
                filter: saturate(1.02) contrast(1.02);
                overflow: hidden;
                position: relative;
                transition: filter 0.32s ease, transform 0.32s ease, box-shadow 0.32s ease;
                z-index: 1;
            }

            div[data-testid="stVerticalBlockBorderWrapper"]:has(.dataset-v20-wordcloud-canvas-marker):hover
            img {
                box-shadow: 0 22px 42px rgba(0,0,0,0.36), 0 0 30px rgba(229,57,53,0.10);
                filter: saturate(1.16) contrast(1.05) brightness(1.035);
                transform: scale(1.008);
            }

            .dataset-v20-wordcloud-chip-row {
                align-items: flex-start;
                border-top: 1px solid rgba(255,255,255,0.07);
                display: flex;
                gap: 0.75rem;
                margin-bottom: 0.58rem;
                margin-top: 0.48rem;
                padding-top: 0.58rem;
                position: relative;
                transform: translateY(-3px);
                z-index: 3;
            }

            .dataset-v20-wordcloud-chip-label {
                color: #747C89;
                flex: 0 0 auto;
                font-size: 0.75rem /* FIX: minimum 12px agar terbaca di tablet */;
                font-weight: 800;
                padding-top: 0.34rem;
            }

            .dataset-v20-wordcloud-chip-list {
                display: flex;
                flex-wrap: wrap;
                gap: 0.42rem;
            }

            .dataset-v20-wordcloud-chip {
                align-items: center;
                animation: datasetV20WordcloudChip 2.8s ease-in-out infinite;
                background: rgba(255,255,255,0.045);
                border: 1px solid rgba(255,255,255,0.09);
                border-radius: 999px;
                color: #D8DDE6;
                cursor: pointer;
                display: inline-flex;
                font-family: inherit;
                font-size: 0.75rem /* FIX: minimum 12px agar terbaca di tablet */;
                gap: 0.4rem;
                padding: 0.4rem 0.58rem;
                transition: transform 0.2s ease, background 0.2s ease, border-color 0.2s ease;
            }

            .dataset-v20-wordcloud-chip:nth-child(2n) { animation-delay: 0.35s; }
            .dataset-v20-wordcloud-chip:nth-child(3n) { animation-delay: 0.7s; }

            .dataset-v20-wordcloud-chip b {
                color: #FF7A75;
                font-size: 0.75rem /* FIX: minimum 12px agar terbaca di tablet */;
            }

            .dataset-v20-wordcloud-chip:hover,
            .dataset-v20-wordcloud-chip:focus {
                background: rgba(229,57,53,0.12);
                border-color: rgba(229,57,53,0.38);
                outline: none;
                transform: translateY(-3px) scale(1.04);
            }

            .dataset-v20-wordcloud-chip:active { transform: translateY(0) scale(0.94); }

            .dataset-v20-wordcloud-fullscreen-marker {
                display: none !important;
            }

            div[data-testid="stDialog"] div[data-testid="stMarkdown"]:has(.dataset-v20-wordcloud-fullscreen-marker),
            div[data-baseweb="modal"] div[data-testid="stMarkdown"]:has(.dataset-v20-wordcloud-fullscreen-marker),
            div[data-testid="stDialog"] div[data-testid="stMarkdownContainer"]:has(.dataset-v20-wordcloud-fullscreen-marker),
            div[data-baseweb="modal"] div[data-testid="stMarkdownContainer"]:has(.dataset-v20-wordcloud-fullscreen-marker) {
                display: none !important;
                height: 0 !important;
                margin: 0 !important;
                min-height: 0 !important;
                padding: 0 !important;
            }

            div[data-testid="stDialog"] div[data-testid="stVerticalBlock"]:has(.dataset-v20-wordcloud-fullscreen-marker),
            div[data-baseweb="modal"] div[data-testid="stVerticalBlock"]:has(.dataset-v20-wordcloud-fullscreen-marker) {
                align-items: center !important;
                box-sizing: border-box !important;
                display: flex !important;
                gap: 0 !important;
                height: 100dvh !important;
                justify-content: center !important;
                margin: 0 !important;
                max-height: 100dvh !important;
                overflow: hidden !important;
                padding: clamp(54px, 7vh, 82px) clamp(58px, 7vw, 118px) !important;
                width: 100vw !important;
            }

            div[data-testid="stDialog"] div[data-testid="stVerticalBlock"]:has(.dataset-v20-wordcloud-fullscreen-marker)
            [data-testid="stElementToolbar"],
            div[data-baseweb="modal"] div[data-testid="stVerticalBlock"]:has(.dataset-v20-wordcloud-fullscreen-marker)
            [data-testid="stElementToolbar"] {
                display: none !important;
            }

            div[data-testid="stDialog"] div[data-testid="stVerticalBlock"]:has(.dataset-v20-wordcloud-fullscreen-marker)
            [data-testid="stImage"],
            div[data-testid="stDialog"] div[data-testid="stVerticalBlock"]:has(.dataset-v20-wordcloud-fullscreen-marker)
            [data-testid="stImageContainer"],
            div[data-baseweb="modal"] div[data-testid="stVerticalBlock"]:has(.dataset-v20-wordcloud-fullscreen-marker)
            [data-testid="stImage"],
            div[data-baseweb="modal"] div[data-testid="stVerticalBlock"]:has(.dataset-v20-wordcloud-fullscreen-marker)
            [data-testid="stImageContainer"] {
                align-items: center !important;
                display: flex !important;
                justify-content: center !important;
                margin: auto !important;
                max-height: 82dvh !important;
                max-width: 1500px !important;
                width: min(88vw, 1500px) !important;
            }

            div[data-testid="stDialog"] div[data-testid="stVerticalBlock"]:has(.dataset-v20-wordcloud-fullscreen-marker) img,
            div[data-baseweb="modal"] div[data-testid="stVerticalBlock"]:has(.dataset-v20-wordcloud-fullscreen-marker) img {
                background: #111722 !important;
                border: 1px solid #2B3A50 !important;
                border-radius: 16px !important;
                box-shadow: 0 26px 58px rgba(0,0,0,0.42) !important;
                display: block !important;
                height: auto !important;
                margin: auto !important;
                max-height: 80dvh !important;
                max-width: 100% !important;
                object-fit: contain !important;
                width: 100% !important;
            }



            @keyframes datasetV21TopicAura {
                0%, 100% { transform: translate3d(-8%, -10%, 0) scale(1); opacity: 0.42; }
                50% { transform: translate3d(12%, 8%, 0) scale(1.18); opacity: 0.78; }
            }

            @keyframes datasetV21TopicBorder {
                0% { background-position: 0% 50%; }
                50% { background-position: 100% 50%; }
                100% { background-position: 0% 50%; }
            }

            @keyframes datasetV21TopicEnter {
                from { opacity: 0; transform: translateY(18px) scale(0.975); }
                to { opacity: 1; transform: translateY(0) scale(1); }
            }

            @keyframes datasetV21TopicFloat {
                0%, 100% { transform: translateY(0) rotate(0deg); }
                50% { transform: translateY(-5px) rotate(-5deg); }
            }

            @keyframes datasetV21TopicPulse {
                0%, 100% { box-shadow: 0 0 0 0 color-mix(in srgb, var(--topic-accent) 34%, transparent); }
                50% { box-shadow: 0 0 0 8px color-mix(in srgb, var(--topic-accent) 0%, transparent); }
            }

            @keyframes datasetV21TopicProgress {
                from { transform: scaleX(0); }
                to { transform: scaleX(1); }
            }

            @keyframes datasetV21TopicSweep {
                0% { transform: translateX(-130%) skewX(-16deg); }
                100% { transform: translateX(430%) skewX(-16deg); }
            }

            @keyframes datasetV21TopicHint {
                0%, 100% { transform: translateX(0); }
                50% { transform: translateX(4px); }
            }

            .dataset-v21-topic-section {
                --topic-accent: #E53935;
                align-items: center;
                animation: datasetV21TopicEnter 0.58s cubic-bezier(.2,.75,.25,1) both;
                background:
                    radial-gradient(circle at 7% 18%, rgba(229,57,53,0.18), transparent 33%),
                    radial-gradient(circle at 94% 12%, rgba(142,114,255,0.16), transparent 34%),
                    linear-gradient(125deg, #191C25 0%, #141822 55%, #10141C 100%);
                border: 1px solid rgba(229,57,53,0.30);
                border-radius: 20px;
                box-shadow: 0 20px 46px rgba(0,0,0,0.30), 0 0 30px rgba(229,57,53,0.08);
                display: flex;
                justify-content: space-between;
                margin: 1.45rem 0 0.82rem;
                min-height: 98px;
                overflow: hidden;
                padding: 1rem 1.12rem;
                position: relative;
                isolation: isolate;
                transition: transform 0.28s ease, border-color 0.28s ease, box-shadow 0.28s ease;
            }

            .dataset-v21-topic-section::before {
                animation: datasetV21TopicAura 7s ease-in-out infinite;
                background: radial-gradient(circle, rgba(229,57,53,0.26), rgba(142,114,255,0.12) 42%, transparent 72%);
                border-radius: 50%;
                content: '';
                height: 190px;
                pointer-events: none;
                position: absolute;
                right: -55px;
                top: -92px;
                width: 190px;
                z-index: -1;
            }

            .dataset-v21-topic-section::after {
                animation: datasetV21TopicBorder 5.2s linear infinite;
                background: linear-gradient(90deg, #E53935, #FF9800, #8E72FF, #38D7FF, #4CAF50, #E53935);
                background-size: 260% 100%;
                bottom: 0;
                content: '';
                height: 3px;
                left: 0;
                position: absolute;
                right: 0;
            }

            .dataset-v21-topic-section:hover,
            .dataset-v21-topic-section:focus {
                border-color: rgba(229,57,53,0.52);
                box-shadow: 0 26px 58px rgba(0,0,0,0.38), 0 0 38px rgba(142,114,255,0.12);
                outline: none;
                transform: translateY(-4px);
            }

            .dataset-v21-topic-header-left {
                align-items: center;
                display: flex;
                gap: 0.82rem;
                min-width: 0;
                position: relative;
                z-index: 1;
            }

            .dataset-v21-topic-icon {
                align-items: center;
                animation: datasetV21TopicFloat 3.2s ease-in-out infinite;
                background: linear-gradient(145deg, rgba(229,57,53,0.22), rgba(142,114,255,0.16));
                border: 1px solid rgba(229,57,53,0.40);
                border-radius: 14px;
                box-shadow: inset 0 1px 0 rgba(255,255,255,0.08), 0 12px 26px rgba(0,0,0,0.24);
                color: #FF6762;
                display: flex;
                flex: 0 0 48px;
                font-size: 1.18rem;
                height: 48px;
                justify-content: center;
                text-shadow: 0 0 18px rgba(229,57,53,0.75);
            }

            .dataset-v21-topic-title {
                color: #FFFFFF;
                font-size: clamp(1.28rem, 2vw, 1.76rem);
                font-weight: 900;
                letter-spacing: -0.038em;
                line-height: 1.08;
            }

            .dataset-v21-topic-subtitle {
                color: #8C94A3;
                font-size: 0.75rem /* FIX: minimum 12px agar terbaca di tablet */;
                line-height: 1.45;
                margin-top: 0.28rem;
                max-width: 760px;
            }

            .dataset-v21-topic-badge {
                align-items: center;
                background: rgba(12,15,22,0.72);
                border: 1px solid rgba(229,57,53,0.34);
                border-radius: 999px;
                color: #E7EBF3;
                display: inline-flex;
                flex: 0 0 auto;
                font-size: 0.75rem /* FIX: minimum 12px agar terbaca di tablet */;
                font-weight: 800;
                gap: 0.44rem;
                padding: 0.55rem 0.78rem;
                position: relative;
                z-index: 1;
            }

            .dataset-v21-topic-badge::before {
                animation: datasetV21TopicPulse 1.9s ease-in-out infinite;
                background: #E53935;
                border-radius: 50%;
                box-shadow: 0 0 13px rgba(229,57,53,0.82);
                content: '';
                height: 7px;
                width: 7px;
            }

            .dataset-v21-topic-podium {
                display: grid;
                gap: 0.72rem;
                grid-template-columns: repeat(3, minmax(0, 1fr));
                margin: 0 0 0.88rem;
            }

            .dataset-v21-topic-card {
                --topic-accent: #E53935;
                --topic-soft: rgba(229,57,53,0.15);
                animation: datasetV21TopicEnter 0.54s cubic-bezier(.2,.75,.25,1) both;
                background:
                    radial-gradient(circle at 95% 0%, var(--topic-soft), transparent 48%),
                    linear-gradient(145deg, #171C26, #111620);
                border: 1px solid rgba(255,255,255,0.075);
                border-radius: 17px;
                appearance: none;
                color: inherit;
                cursor: pointer;
                font-family: inherit;
                min-height: 142px;
                overflow: hidden;
                padding: 0.86rem 0.92rem 0.82rem;
                position: relative;
                text-align: left;
                transition: transform 0.24s ease, border-color 0.24s ease, box-shadow 0.24s ease;
                width: 100%;
            }

            .dataset-v21-topic-card:nth-child(2) { animation-delay: 0.08s; }
            .dataset-v21-topic-card:nth-child(3) { animation-delay: 0.16s; }

            .dataset-v21-topic-card::before {
                background: linear-gradient(90deg, transparent, rgba(255,255,255,0.18), transparent);
                content: '';
                height: 130%;
                left: -34%;
                pointer-events: none;
                position: absolute;
                top: -15%;
                transform: translateX(-130%) skewX(-16deg);
                width: 24%;
            }

            .dataset-v21-topic-card::after {
                background: linear-gradient(90deg, var(--topic-accent), transparent);
                bottom: 0;
                content: '';
                height: 3px;
                left: 0;
                position: absolute;
                width: 64%;
            }

            .dataset-v21-topic-card:hover,
            .dataset-v21-topic-card:focus-visible {
                border-color: color-mix(in srgb, var(--topic-accent) 55%, transparent);
                box-shadow: 0 20px 42px rgba(0,0,0,0.34), 0 0 28px var(--topic-soft);
                outline: none;
                transform: translateY(-6px) scale(1.012);
            }

            .dataset-v21-topic-card:hover::before,
            .dataset-v21-topic-card:focus-visible::before {
                animation: datasetV21TopicSweep 0.92s ease;
            }

            .dataset-v21-topic-card:active { transform: translateY(-1px) scale(0.975); }

            .dataset-v21-topic-card-top {
                align-items: center;
                display: flex;
                justify-content: space-between;
            }

            .dataset-v21-topic-rank {
                align-items: center;
                animation: datasetV21TopicPulse 2.2s ease-in-out infinite;
                background: var(--topic-soft);
                border: 1px solid color-mix(in srgb, var(--topic-accent) 48%, transparent);
                border-radius: 10px;
                color: var(--topic-accent);
                display: flex;
                font-size: 0.75rem /* FIX: minimum 12px agar terbaca di tablet */;
                font-weight: 900;
                height: 30px;
                justify-content: center;
                width: 34px;
            }

            .dataset-v21-topic-count {
                color: #FFFFFF;
                font-size: 1.34rem;
                font-weight: 900;
                letter-spacing: -0.045em;
            }

            .dataset-v21-topic-name {
                color: #E9EDF5;
                display: -webkit-box;
                font-size: 0.82rem;
                font-weight: 800;
                line-height: 1.35;
                margin-top: 0.72rem;
                min-height: 2.2em;
                overflow: hidden;
                -webkit-box-orient: vertical;
                -webkit-line-clamp: 2;
            }

            .dataset-v21-topic-share {
                color: #7D8593;
                font-size: 0.75rem /* FIX: minimum 12px agar terbaca di tablet */;
                margin-top: 0.24rem;
            }

            .dataset-v21-topic-track {
                background: rgba(255,255,255,0.065);
                border-radius: 999px;
                height: 5px;
                margin-top: 0.68rem;
                overflow: hidden;
            }

            .dataset-v21-topic-track span {
                animation: datasetV21TopicProgress 0.95s 0.15s cubic-bezier(.2,.75,.25,1) both;
                background: linear-gradient(90deg, var(--topic-accent), rgba(255,255,255,0.78));
                border-radius: inherit;
                display: block;
                height: 100%;
                min-width: 5px;
                transform-origin: left center;
                width: var(--topic-share);
            }

            .dataset-v21-topic-card:hover .dataset-v21-topic-track span,
            .dataset-v21-topic-card:focus-visible .dataset-v21-topic-track span {
                box-shadow: 0 0 16px var(--topic-accent);
                filter: brightness(1.16);
            }

            .dataset-v21-topic-chart-marker { display: none; }

            div[data-testid="stVerticalBlockBorderWrapper"]:has(.dataset-v21-topic-chart-marker) {
                animation: datasetV21TopicEnter 0.64s 0.14s cubic-bezier(.2,.75,.25,1) both;
                background:
                    radial-gradient(circle at 50% -18%, rgba(142,114,255,0.15), transparent 44%),
                    radial-gradient(circle at 100% 100%, rgba(229,57,53,0.09), transparent 34%),
                    linear-gradient(145deg, #151A24, #10141C);
                border-color: rgba(255,255,255,0.09) !important;
                border-radius: 20px !important;
                box-shadow: 0 20px 46px rgba(0,0,0,0.30);
                overflow: hidden;
                position: relative;
                transition: transform 0.28s ease, border-color 0.28s ease, box-shadow 0.28s ease;
            }

            div[data-testid="stVerticalBlockBorderWrapper"]:has(.dataset-v21-topic-chart-marker)::before {
                animation: datasetV21TopicBorder 5.6s linear infinite;
                background: linear-gradient(90deg, #E53935, #FF9800, #8E72FF, #38D7FF, #4CAF50, #E53935);
                background-size: 260% 100%;
                content: '';
                height: 3px;
                left: 0;
                position: absolute;
                right: 0;
                top: 0;
                z-index: 3;
            }

            div[data-testid="stVerticalBlockBorderWrapper"]:has(.dataset-v21-topic-chart-marker)::after {
                background: linear-gradient(118deg, transparent 18%, rgba(255,255,255,0.08), transparent 48%);
                content: '';
                inset: 0;
                pointer-events: none;
                position: absolute;
                transform: translateX(-100%);
                transition: transform 0.9s ease;
                z-index: 0;
            }

            div[data-testid="stVerticalBlockBorderWrapper"]:has(.dataset-v21-topic-chart-marker):hover {
                border-color: rgba(142,114,255,0.32) !important;
                box-shadow: 0 26px 58px rgba(0,0,0,0.38), 0 0 34px rgba(142,114,255,0.10);
                transform: translateY(-4px);
            }

            div[data-testid="stVerticalBlockBorderWrapper"]:has(.dataset-v21-topic-chart-marker):hover::after {
                transform: translateX(100%);
            }

            .dataset-v21-topic-chart-head {
                align-items: center;
                display: flex;
                justify-content: space-between;
                margin: 0.12rem 0 0.08rem;
                padding: 0.12rem 0.18rem 0;
                position: relative;
                z-index: 2;
            }

            .dataset-v21-topic-chart-title-wrap {
                align-items: center;
                display: flex;
                gap: 0.62rem;
            }

            .dataset-v21-topic-chart-icon {
                align-items: center;
                background: rgba(142,114,255,0.15);
                border: 1px solid rgba(142,114,255,0.34);
                border-radius: 11px;
                color: #B9A7FF;
                display: flex;
                font-size: 0.92rem;
                height: 38px;
                justify-content: center;
                transition: transform 0.24s ease, box-shadow 0.24s ease;
                width: 38px;
            }

            div[data-testid="stVerticalBlockBorderWrapper"]:has(.dataset-v21-topic-chart-marker):hover
            .dataset-v21-topic-chart-icon {
                box-shadow: 0 0 20px rgba(142,114,255,0.24);
                transform: rotate(-8deg) scale(1.10);
            }

            .dataset-v21-topic-chart-title {
                color: #F5F7FB;
                font-size: 0.94rem;
                font-weight: 900;
                letter-spacing: -0.02em;
            }

            .dataset-v21-topic-chart-note {
                color: #7F8795;
                font-size: 0.75rem /* FIX: minimum 12px agar terbaca di tablet */;
                margin-top: 0.16rem;
            }

            .dataset-v21-topic-chart-badge {
                align-items: center;
                background: rgba(142,114,255,0.11);
                border: 1px solid rgba(142,114,255,0.27);
                border-radius: 999px;
                color: #D8D0FF;
                display: inline-flex;
                font-size: 0.75rem /* FIX: minimum 12px agar terbaca di tablet */;
                font-weight: 800;
                gap: 0.38rem;
                padding: 0.42rem 0.60rem;
            }

            .dataset-v21-topic-chart-badge::before {
                animation: datasetV21TopicPulse 2s ease-in-out infinite;
                background: #8E72FF;
                border-radius: 50%;
                content: '';
                height: 6px;
                width: 6px;
            }

            div[data-testid="stVerticalBlockBorderWrapper"]:has(.dataset-v21-topic-chart-marker)
            div[data-testid="stPlotlyChart"] {
                border: 1px solid rgba(255,255,255,0.055);
                border-radius: 16px;
                overflow: hidden;
                position: relative;
                transition: filter 0.28s ease, transform 0.28s ease, box-shadow 0.28s ease;
                z-index: 1;
            }

            div[data-testid="stVerticalBlockBorderWrapper"]:has(.dataset-v21-topic-chart-marker):hover
            div[data-testid="stPlotlyChart"] {
                box-shadow: 0 20px 38px rgba(0,0,0,0.28);
                filter: saturate(1.10) brightness(1.035);
                transform: scale(1.004);
            }

            .dataset-v21-topic-mode-row-marker,
            .dataset-v21-topic-mode-marker {
                display: none;
            }

            div[data-testid="stHorizontalBlock"]:has(.dataset-v21-topic-mode-row-marker) {
                align-items: center !important;
                justify-content: center !important;
                margin: 0.72rem auto 0.92rem !important;
                max-width: 100% !important;
                min-height: 48px !important;
                width: 100% !important;
            }

            div[data-testid="stColumn"]:has(.dataset-v21-topic-mode-marker) {
                align-items: center !important;
                display: flex !important;
                justify-content: center !important;
                min-width: 126px !important;
            }

            div[data-testid="stColumn"]:has(.dataset-v21-topic-mode-marker)
            div[data-testid="stButton"] {
                margin: 0 !important;
                width: 100% !important;
            }

            div[data-testid="stColumn"]:has(.dataset-v21-topic-mode-marker)
            div[data-testid="stButton"] > button {
                align-items: center !important;
                background: linear-gradient(135deg, #171C27, #1E2432) !important;
                border: 1px solid rgba(142,114,255,0.28) !important;
                border-radius: 12px !important;
                box-shadow: 0 8px 18px rgba(0,0,0,0.18) !important;
                color: #D9DDEA !important;
                display: flex !important;
                font-size: 0.76rem !important;
                font-weight: 800 !important;
                height: 42px !important;
                justify-content: center !important;
                line-height: 1 !important;
                margin: 0 !important;
                min-height: 42px !important;
                padding: 0 0.95rem !important;
                transition: background 180ms ease, border-color 180ms ease,
                            box-shadow 180ms ease, color 180ms ease, transform 180ms ease !important;
                width: 100% !important;
            }

            div[data-testid="stColumn"]:has(.dataset-v21-topic-mode-marker)
            div[data-testid="stButton"] > button:hover {
                background: linear-gradient(135deg, #2A2340, #342954) !important;
                border-color: #A992FF !important;
                box-shadow: 0 12px 26px rgba(108,76,255,0.28),
                            0 0 0 1px rgba(185,167,255,0.12) inset !important;
                color: #FFFFFF !important;
                transform: translateY(-2px) !important;
            }

            div[data-testid="stColumn"]:has(.dataset-v21-topic-mode-active)
            div[data-testid="stButton"] > button {
                background: linear-gradient(135deg, #6547E8, #8E72FF) !important;
                border-color: #C1B4FF !important;
                box-shadow: 0 12px 28px rgba(108,76,255,0.34),
                            0 0 0 1px rgba(255,255,255,0.13) inset !important;
                color: #FFFFFF !important;
                transform: translateY(0) !important;
            }

            div[data-testid="stColumn"]:has(.dataset-v21-topic-mode-active)
            div[data-testid="stButton"] > button:hover {
                background: linear-gradient(135deg, #7358F1, #9C85FF) !important;
                border-color: #DDD6FF !important;
                box-shadow: 0 14px 32px rgba(108,76,255,0.42),
                            0 0 0 1px rgba(255,255,255,0.18) inset !important;
            }

            div[data-testid="stColumn"]:has(.dataset-v21-topic-mode-marker)
            div[data-testid="stButton"] > button:active {
                transform: translateY(0) scale(0.975) !important;
            }

            div[data-testid="stColumn"]:has(.dataset-v21-topic-mode-marker)
            div[data-testid="stButton"] > button p,
            div[data-testid="stColumn"]:has(.dataset-v21-topic-mode-marker)
            div[data-testid="stButton"] > button span {
                color: inherit !important;
                font-size: inherit !important;
                font-weight: inherit !important;
                line-height: 1 !important;
                margin: 0 !important;
            }

            .dataset-v21-topic-hint {
                align-items: center;
                color: #717A89;
                display: flex;
                font-size: 0.75rem /* FIX: minimum 12px agar terbaca di tablet */;
                gap: 0.42rem;
                margin: -0.34rem 0 0.18rem;
                padding: 0 0.22rem;
                position: relative;
                z-index: 2;
            }

            .dataset-v21-topic-hint span:first-child {
                animation: datasetV21TopicHint 1.5s ease-in-out infinite;
                color: #B9A7FF;
                font-size: 0.78rem;
            }


            @media (max-width: 760px) {
                .dataset-v19-signal-grid { grid-template-columns: 1fr; }
                .dataset-v19-signal-card { min-height: 104px; }
                .dataset-v18-metric-card { min-height: 140px; }
                .dataset-v18-platform-header { align-items: flex-start; }
                .dataset-v18-platform-badge { display: none; }
                .dataset-v18-sentiment-section { align-items: flex-start; }
                .dataset-v18-sentiment-dominant { display: none; }
                .dataset-v18-chart-card-badge { display: none; }
                .dataset-v20-wordcloud-section { align-items: flex-start; flex-direction: column; gap: 0.78rem; }
                .dataset-v20-wordcloud-live-badge { align-self: flex-start; }
                .dataset-v20-wordcloud-stat-grid { grid-template-columns: 1fr; }
                .dataset-v20-wordcloud-canvas-head { align-items: flex-start; flex-direction: column; gap: 0.62rem; }
                .dataset-v20-wordcloud-chip-row { flex-direction: column; }
                .dataset-v21-topic-section { align-items: flex-start; flex-direction: column; gap: 0.78rem; }
                .dataset-v21-topic-badge { align-self: flex-start; }
                .dataset-v21-topic-podium { grid-template-columns: 1fr; }
                .dataset-v21-topic-chart-head { align-items: flex-start; flex-direction: column; gap: 0.62rem; }
                .dataset-v21-topic-chart-badge { align-self: flex-start; }
            }

            @media (prefers-reduced-motion: reduce) {
                .dataset-v18-output-heading-icon,
                .dataset-v18-sentiment-section::before,
                .dataset-v18-sentiment-section::after,
                .dataset-v18-sentiment-section-icon,
                .dataset-v18-sentiment-section-icon::after,
                .dataset-v18-sentiment-dominant::before,
                .dataset-v19-sentiment-lab::before,
                .dataset-v19-signal-card,
                .dataset-v19-spark span,
                .dataset-v19-signal-track span::after,
                .dataset-v19-lab-hint span:first-child,
                .dataset-v18-chart-card-hint span:first-child,
                .dataset-v18-metric-card,
                .dataset-v18-metric-progress > span,
                .dataset-v18-platform-shell,
                .dataset-v18-platform-fill,
                div[data-testid="stVerticalBlockBorderWrapper"]:has(.dataset-v18-chart-card-marker),
                .dataset-v18-chart-card-badge::before,
                .dataset-v20-wordcloud-section,
                .dataset-v20-wordcloud-section::before,
                .dataset-v20-wordcloud-icon,
                .dataset-v20-wordcloud-live-badge span,
                .dataset-v20-wordcloud-stat,
                div[data-testid="stVerticalBlockBorderWrapper"]:has(.dataset-v20-wordcloud-canvas-marker),
                div[data-testid="stVerticalBlockBorderWrapper"]:has(.dataset-v20-wordcloud-canvas-marker)::before,
                .dataset-v20-wordcloud-chip,
                .dataset-v21-topic-section,
                .dataset-v21-topic-section::before,
                .dataset-v21-topic-section::after,
                .dataset-v21-topic-icon,
                .dataset-v21-topic-badge::before,
                .dataset-v21-topic-card,
                .dataset-v21-topic-rank,
                .dataset-v21-topic-track span,
                div[data-testid="stVerticalBlockBorderWrapper"]:has(.dataset-v21-topic-chart-marker),
                div[data-testid="stVerticalBlockBorderWrapper"]:has(.dataset-v21-topic-chart-marker)::before,
                .dataset-v21-topic-chart-badge::before,
                .dataset-v21-topic-hint span:first-child {
                    animation: none !important;
                }
            }
        </style>
        """,
        unsafe_allow_html=True,
    )

    # CSS Light Mode disisipkan setelah CSS baseline output upload.
    # Urutan ini penting agar seluruh panel di dalam expander tidak kembali
    # memakai warna gelap saat hasil analisis dirender.
    if not bool(st.session_state.get("dark_mode", False)):
        st.markdown(
            """
            <style>
                .dataset-v18-output-heading-icon {
                    background: linear-gradient(135deg, #FEF2F2, #F5F3FF) !important;
                    border-color: #FECACA !important;
                    box-shadow: 0 8px 20px rgba(15,23,42,0.08) !important;
                    color: #B91C1C !important;
                }

                .dataset-v18-output-heading-title,
                .dataset-v18-metric-value,
                .dataset-v18-platform-title,
                .dataset-v18-platform-name,
                .dataset-v18-sentiment-section-title,
                .dataset-v18-chart-card-title,
                .dataset-v19-signal-value,
                .dataset-v20-wordcloud-title,
                .dataset-v20-wordcloud-stat strong,
                .dataset-v20-wordcloud-canvas-title,
                .dataset-v21-topic-title,
                .dataset-v21-topic-name,
                .dataset-v21-topic-chart-title {
                    color: #111827 !important;
                    -webkit-text-fill-color: #111827 !important;
                }

                .dataset-v18-output-heading-note,
                .dataset-v18-metric-label,
                .dataset-v18-metric-note,
                .dataset-v18-platform-subtitle,
                .dataset-v18-platform-share,
                .dataset-v18-sentiment-section-note,
                .dataset-v18-chart-card-subtitle,
                .dataset-v18-chart-card-hint,
                .dataset-v19-signal-label,
                .dataset-v19-lab-hint,
                .dataset-v20-wordcloud-subtitle,
                .dataset-v20-wordcloud-stat-top,
                .dataset-v20-wordcloud-stat small,
                .dataset-v20-wordcloud-canvas-note,
                .dataset-v20-wordcloud-chip-label,
                .dataset-v21-topic-subtitle,
                .dataset-v21-topic-share,
                .dataset-v21-topic-chart-note,
                .dataset-v21-topic-hint {
                    color: #64748B !important;
                    -webkit-text-fill-color: #64748B !important;
                }

                .dataset-v18-metric-card {
                    background:
                        radial-gradient(circle at 96% 2%, var(--v18-accent-soft), transparent 44%),
                        #FFFFFF !important;
                    border-color: #E2E8F0 !important;
                    box-shadow: 0 12px 28px rgba(15,23,42,0.07) !important;
                }

                .dataset-v18-metric-card:hover,
                .dataset-v18-metric-card:focus {
                    border-color: var(--v18-accent-border) !important;
                    box-shadow: 0 18px 36px rgba(15,23,42,0.11), 0 0 22px var(--v18-accent-glow) !important;
                }

                .dataset-v18-metric-progress,
                .dataset-v18-platform-track,
                .dataset-v19-signal-track,
                .dataset-v21-topic-track {
                    background: #E2E8F0 !important;
                }

                .dataset-v18-platform-shell {
                    background:
                        radial-gradient(circle at 96% 4%, rgba(29,161,242,0.08), transparent 36%),
                        linear-gradient(145deg, #FFFFFF, #F8FAFC) !important;
                    border-color: #E2E8F0 !important;
                    box-shadow: 0 14px 32px rgba(15,23,42,0.08) !important;
                }

                .dataset-v18-platform-card {
                    background:
                        radial-gradient(circle at 100% 0%, var(--platform-soft), transparent 50%),
                        #FFFFFF !important;
                    border-color: #E2E8F0 !important;
                    color: #111827 !important;
                    box-shadow: 0 8px 20px rgba(15,23,42,0.05) !important;
                }

                .dataset-v18-platform-card:hover,
                .dataset-v18-platform-card:focus {
                    border-color: var(--platform-border) !important;
                    box-shadow: 0 14px 28px rgba(15,23,42,0.10), 0 0 20px var(--platform-soft) !important;
                }

                .dataset-v18-platform-badge {
                    background: #F8FAFC !important;
                    border-color: #CBD5E1 !important;
                    color: #334155 !important;
                }

                .dataset-v18-sentiment-section {
                    background:
                        radial-gradient(circle at 8% 12%, rgba(142,114,255,0.10), transparent 34%),
                        radial-gradient(circle at 95% 0%, rgba(229,57,53,0.09), transparent 34%),
                        linear-gradient(135deg, #FFFFFF, #F8FAFC) !important;
                    border-color: #E2E8F0 !important;
                    box-shadow: 0 14px 34px rgba(15,23,42,0.09) !important;
                }

                .dataset-v18-sentiment-section:hover,
                .dataset-v18-sentiment-section:focus {
                    border-color: #FCA5A5 !important;
                    box-shadow: 0 18px 40px rgba(15,23,42,0.12), 0 0 24px rgba(142,114,255,0.09) !important;
                }

                .dataset-v18-sentiment-section-icon {
                    background: linear-gradient(135deg, #FEF2F2, #F5F3FF) !important;
                    border-color: #FECACA !important;
                    color: #991B1B !important;
                    box-shadow: 0 8px 18px rgba(15,23,42,0.07) !important;
                }

                .dataset-v18-sentiment-section-icon::after {
                    border-color: #FFFFFF !important;
                }

                .dataset-v18-sentiment-dominant {
                    background: #FFF1F2 !important;
                    border-color: #FDA4AF !important;
                    color: #9F1239 !important;
                    -webkit-text-fill-color: #9F1239 !important;
                    box-shadow: 0 6px 16px rgba(159,18,57,0.08) !important;
                }

                .dataset-v19-sentiment-lab {
                    background:
                        radial-gradient(circle at 0% 0%, rgba(142,114,255,0.07), transparent 42%),
                        #FFFFFF !important;
                    border-color: #E2E8F0 !important;
                    box-shadow: 0 12px 28px rgba(15,23,42,0.07) !important;
                }

                .dataset-v19-sentiment-lab::before {
                    opacity: 0.34 !important;
                }

                .dataset-v19-signal-card {
                    background:
                        radial-gradient(circle at 100% 0%, var(--signal-soft), transparent 48%),
                        #FFFFFF !important;
                    border-color: #E2E8F0 !important;
                    color: #111827 !important;
                    box-shadow: 0 7px 18px rgba(15,23,42,0.04) !important;
                }

                .dataset-v19-signal-card:hover,
                .dataset-v19-signal-card:focus-visible {
                    background:
                        radial-gradient(circle at 100% 0%, var(--signal-soft), transparent 58%),
                        #F8FAFC !important;
                    border-color: var(--signal-border) !important;
                    box-shadow: 0 14px 30px rgba(15,23,42,0.10), 0 0 20px var(--signal-soft) !important;
                }

                .dataset-v19-signal-card::before {
                    background: linear-gradient(90deg, transparent, rgba(255,255,255,0.82), transparent) !important;
                }

                .dataset-v19-signal-label,
                .dataset-v19-signal-value {
                    color: #1F2937 !important;
                    -webkit-text-fill-color: #1F2937 !important;
                }

                .dataset-v19-spark span {
                    background: linear-gradient(180deg, #FFFFFF, var(--signal-accent)) !important;
                }

                div[data-testid="stVerticalBlockBorderWrapper"]:has(.dataset-v18-chart-card-marker) {
                    background:
                        radial-gradient(circle at 100% 0%, var(--v18-chart-soft), transparent 42%),
                        #FFFFFF !important;
                    border-color: #E2E8F0 !important;
                    box-shadow: 0 14px 32px rgba(15,23,42,0.08) !important;
                }

                div[data-testid="stVerticalBlockBorderWrapper"]:has(.dataset-v18-chart-card-marker):hover {
                    border-color: var(--v18-chart-accent) !important;
                    box-shadow: 0 18px 40px rgba(15,23,42,0.12), 0 0 24px var(--v18-chart-soft) !important;
                }

                .dataset-v18-chart-card-icon {
                    background: #F8FAFC !important;
                    border-color: #CBD5E1 !important;
                }

                .dataset-v18-chart-card-badge {
                    background: #F8FAFC !important;
                    border-color: #CBD5E1 !important;
                    color: #334155 !important;
                    -webkit-text-fill-color: #334155 !important;
                }

                div[data-testid="stVerticalBlockBorderWrapper"]:has(.dataset-v18-chart-card-marker)
                div[data-testid="stPlotlyChart"],
                div[data-testid="stVerticalBlockBorderWrapper"]:has(.dataset-v21-topic-chart-marker)
                div[data-testid="stPlotlyChart"] {
                    background: #FFFFFF !important;
                    border-color: #E2E8F0 !important;
                    box-shadow: none !important;
                }

                .dataset-v20-wordcloud-section {
                    background:
                        radial-gradient(circle at 7% 22%, rgba(244,67,54,0.08), transparent 31%),
                        radial-gradient(circle at 94% 18%, rgba(182,124,255,0.08), transparent 32%),
                        linear-gradient(115deg, #FFFFFF, #F8FAFC) !important;
                    border-color: #FCA5A5 !important;
                    box-shadow: 0 14px 34px rgba(15,23,42,0.08) !important;
                }

                .dataset-v20-wordcloud-section:hover,
                .dataset-v20-wordcloud-section:focus {
                    box-shadow: 0 18px 42px rgba(15,23,42,0.12), 0 0 24px rgba(244,67,54,0.08) !important;
                }

                .dataset-v20-wordcloud-icon,
                .dataset-v21-topic-icon,
                .dataset-v21-topic-chart-icon {
                    background: #F8FAFC !important;
                    box-shadow: 0 8px 18px rgba(15,23,42,0.06) !important;
                }

                .dataset-v20-wordcloud-live-badge,
                .dataset-v21-topic-badge,
                .dataset-v21-topic-chart-badge {
                    background: #FFFFFF !important;
                    border-color: #CBD5E1 !important;
                    color: #334155 !important;
                    -webkit-text-fill-color: #334155 !important;
                }

                .dataset-v20-wordcloud-stat {
                    background:
                        radial-gradient(circle at 95% 5%, var(--wc-stat-soft), transparent 46%),
                        #FFFFFF !important;
                    border-color: #E2E8F0 !important;
                    box-shadow: 0 8px 20px rgba(15,23,42,0.05) !important;
                }

                .dataset-v20-wordcloud-stat:hover,
                .dataset-v20-wordcloud-stat:focus {
                    box-shadow: 0 14px 30px rgba(15,23,42,0.10), 0 0 20px var(--wc-stat-soft) !important;
                }

                div[data-testid="stVerticalBlockBorderWrapper"]:has(.dataset-v20-wordcloud-controls-marker),
                div[data-testid="stVerticalBlockBorderWrapper"]:has(.dataset-v20-wordcloud-canvas-marker) {
                    background: #FFFFFF !important;
                    border-color: #E2E8F0 !important;
                    box-shadow: 0 12px 28px rgba(15,23,42,0.07) !important;
                }

                .dataset-v20-wordcloud-chip-row {
                    background: #F8FAFC !important;
                    border-color: #E2E8F0 !important;
                }

                .dataset-v20-wordcloud-chip {
                    background: #FFFFFF !important;
                    border-color: #CBD5E1 !important;
                    color: #334155 !important;
                    -webkit-text-fill-color: #334155 !important;
                }

                .dataset-v21-topic-section {
                    background:
                        radial-gradient(circle at 7% 18%, rgba(229,57,53,0.08), transparent 34%),
                        radial-gradient(circle at 95% 12%, rgba(142,114,255,0.08), transparent 34%),
                        linear-gradient(135deg, #FFFFFF, #F8FAFC) !important;
                    border-color: #E2E8F0 !important;
                    box-shadow: 0 14px 34px rgba(15,23,42,0.08) !important;
                }

                .dataset-v21-topic-section:hover,
                .dataset-v21-topic-section:focus {
                    box-shadow: 0 18px 42px rgba(15,23,42,0.12) !important;
                }

                .dataset-v21-topic-card {
                    background:
                        radial-gradient(circle at 100% 0%, var(--topic-soft), transparent 48%),
                        #FFFFFF !important;
                    border-color: #E2E8F0 !important;
                    color: #111827 !important;
                    box-shadow: 0 8px 20px rgba(15,23,42,0.05) !important;
                }

                .dataset-v21-topic-card:hover,
                .dataset-v21-topic-card:focus-visible {
                    border-color: var(--topic-accent) !important;
                    box-shadow: 0 14px 30px rgba(15,23,42,0.10), 0 0 20px var(--topic-soft) !important;
                }

                .dataset-v21-topic-count,
                .dataset-v21-topic-rank {
                    color: var(--topic-accent) !important;
                    -webkit-text-fill-color: var(--topic-accent) !important;
                }

                div[data-testid="stVerticalBlockBorderWrapper"]:has(.dataset-v21-topic-chart-marker) {
                    background:
                        radial-gradient(circle at 50% -18%, rgba(142,114,255,0.08), transparent 44%),
                        #FFFFFF !important;
                    border-color: #E2E8F0 !important;
                    box-shadow: 0 14px 34px rgba(15,23,42,0.08) !important;
                }

                div[data-testid="stVerticalBlockBorderWrapper"]:has(.dataset-v21-topic-chart-marker):hover {
                    border-color: #A78BFA !important;
                    box-shadow: 0 18px 42px rgba(15,23,42,0.12), 0 0 22px rgba(142,114,255,0.08) !important;
                }

                div[data-testid="stColumn"]:has(.dataset-v21-topic-mode-marker)
                div[data-testid="stButton"] > button {
                    background: #FFFFFF !important;
                    border-color: #CBD5E1 !important;
                    box-shadow: 0 6px 16px rgba(15,23,42,0.06) !important;
                    color: #334155 !important;
                }

                div[data-testid="stColumn"]:has(.dataset-v21-topic-mode-marker)
                div[data-testid="stButton"] > button:hover {
                    background: #F5F3FF !important;
                    border-color: #8E72FF !important;
                    color: #5B21B6 !important;
                }

                div[data-testid="stColumn"]:has(.dataset-v21-topic-mode-active)
                div[data-testid="stButton"] > button {
                    background: linear-gradient(135deg, #6547E8, #8E72FF) !important;
                    border-color: #8E72FF !important;
                    color: #FFFFFF !important;
                }

                div[data-testid="stExpander"]:has(.dataset-v16-upload-anchor)
                div[data-testid="stDownloadButton"] > button {
                    background: linear-gradient(135deg, #E53935, #EF4444) !important;
                    border-color: #E53935 !important;
                    color: #FFFFFF !important;
                    box-shadow: 0 10px 24px rgba(229,57,53,0.18) !important;
                }

                div[data-testid="stExpander"]:has(.dataset-v16-upload-anchor)
                div[data-testid="stDownloadButton"] > button:hover {
                    background: linear-gradient(135deg, #C62828, #E53935) !important;
                    border-color: #C62828 !important;
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


def _render_ringkasan_interaktif_sentimen_upload(
    jumlah: pd.Series,
    total: int,
) -> None:
    """Render kartu sinyal sentimen interaktif dengan animasi visual terisolasi."""
    try:
        konfigurasi = (
            ("Positif", "dataset-v19-signal-positive"),
            ("Netral", "dataset-v19-signal-neutral"),
            ("Negatif", "dataset-v19-signal-negative"),
        )
        kartu: list[str] = []
        pembagi = max(int(total), 1)
        for label, kelas in konfigurasi:
            nilai = int(jumlah.get(label, 0))
            persentase = float(nilai / pembagi * 100)
            kartu.append(
                f"""
                <button type="button" class="dataset-v19-signal-card {kelas}"
                    style="--signal-pct:{persentase:.1f}%;"
                    aria-label="{escape(label)} {nilai} komentar atau {persentase:.1f} persen">
                    <div class="dataset-v19-signal-top">
                        <div class="dataset-v19-signal-label">
                            <span class="dataset-v19-signal-dot"></span>
                            <span>{escape(label)}</span>
                        </div>
                        <div class="dataset-v19-signal-pct">{persentase:.1f}%</div>
                    </div>
                    <div class="dataset-v19-signal-main">
                        <div class="dataset-v19-signal-value">{_format_angka(nilai)}</div>
                        <div class="dataset-v19-spark" aria-hidden="true">
                            <span></span><span></span><span></span><span></span>
                        </div>
                    </div>
                    <div class="dataset-v19-signal-track" aria-hidden="true">
                        <span></span>
                    </div>
                </button>
                """
            )

        html_kartu = "".join(kartu).replace("\n", "")
        st.markdown(
            f"""
            <div class="dataset-v19-sentiment-lab">
                <div class="dataset-v19-signal-grid">
                    {html_kartu}
                </div>
                <div class="dataset-v19-lab-hint">
                    <span>↗</span>
                    <span>Arahkan kursor atau klik kartu sentimen untuk memicu efek fokus, kilau, dan pulse.</span>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )
    except Exception as exc:
        LOGGER.exception("Ringkasan interaktif sentimen upload gagal dirender")
        st.error(f"Ringkasan sentimen interaktif tidak dapat ditampilkan. Detail: {exc}")



def _atur_mode_topik_upload(mode: str) -> None:
    """Simpan mode visualisasi Top 10 topik yang dipilih pengguna."""
    st.session_state[STATE_TOPIK_MODE] = (
        "Persentase" if str(mode).strip().lower() == "persentase" else "Jumlah"
    )


def _render_topik_interaktif_upload(data_topik: pd.Series) -> None:
    """Render Top 10 topik sebagai panel berwarna, animatif, dan interaktif."""
    try:
        if data_topik is None or data_topik.empty:
            st.info("Topik belum tersedia pada hasil analisis.")
            return

        topik_bersih = (
            data_topik
            .fillna("Topik Lainnya")
            .astype(str)
            .str.strip()
            .replace("", "Topik Lainnya")
        )
        frekuensi_semua = topik_bersih.value_counts()
        if frekuensi_semua.empty:
            st.info("Topik belum tersedia pada hasil analisis.")
            return

        topik_utama = frekuensi_semua.head(10)
        total_komentar = max(int(frekuensi_semua.sum()), 1)
        cakupan_topik = float(topik_utama.sum() / total_komentar * 100)
        topik_dominan = str(topik_utama.index[0])
        jumlah_dominan = int(topik_utama.iloc[0])
        persentase_dominan = float(jumlah_dominan / total_komentar * 100)

        st.markdown(
            f"""
            <div class="dataset-v21-topic-section" tabindex="0">
                <div class="dataset-v21-topic-header-left">
                    <div class="dataset-v21-topic-icon">◫</div>
                    <div>
                        <div class="dataset-v21-topic-title">Top 10 Topik Percakapan</div>
                        <div class="dataset-v21-topic-subtitle">
                            Temukan isu paling dominan melalui kartu peringkat, hover detail,
                            dan pergantian mode jumlah atau persentase.
                        </div>
                    </div>
                </div>
                <div class="dataset-v21-topic-badge">
                    {len(topik_utama)} topik · {cakupan_topik:.1f}% data
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        warna_peringkat = ["#E53935", "#FF8A3D", "#8E72FF"]
        kartu_html: list[str] = []
        for posisi, (nama_topik, jumlah_topik) in enumerate(topik_utama.head(3).items(), start=1):
            persentase = float(int(jumlah_topik) / total_komentar * 100)
            warna = warna_peringkat[posisi - 1]
            warna_soft = {
                1: "rgba(229,57,53,0.16)",
                2: "rgba(255,138,61,0.15)",
                3: "rgba(142,114,255,0.16)",
            }[posisi]
            kartu_html.append(
                f'<button type="button" class="dataset-v21-topic-card" '
                f'style="--topic-accent:{warna};--topic-soft:{warna_soft};--topic-share:{persentase:.2f}%;" '
                f'aria-label="Peringkat {posisi}, {escape(str(nama_topik))}, {int(jumlah_topik)} komentar">'
                f'<div class="dataset-v21-topic-card-top">'
                f'<span class="dataset-v21-topic-rank">#{posisi}</span>'
                f'<span class="dataset-v21-topic-count">{_format_angka(int(jumlah_topik))}</span>'
                f'</div>'
                f'<div class="dataset-v21-topic-name">{escape(str(nama_topik))}</div>'
                f'<div class="dataset-v21-topic-share">{persentase:.1f}% dari seluruh komentar</div>'
                f'<div class="dataset-v21-topic-track" aria-hidden="true"><span></span></div>'
                f'</button>'
            )

        st.markdown(
            f'<div class="dataset-v21-topic-podium">{"".join(kartu_html)}</div>',
            unsafe_allow_html=True,
        )

        topik_plot = topik_utama.iloc[::-1]
        label_plot = [str(label) for label in topik_plot.index.tolist()]
        nilai_plot = [int(nilai) for nilai in topik_plot.values.tolist()]
        persentase_plot = [float(nilai / total_komentar * 100) for nilai in nilai_plot]

        peta_peringkat = {str(label): posisi for posisi, label in enumerate(topik_utama.index, start=1)}
        peringkat_plot = [int(peta_peringkat[label]) for label in label_plot]
        palet = [
            "#E53935", "#FF7043", "#FF9800", "#FFC247", "#8E72FF",
            "#6C8CFF", "#38BDF8", "#25D0B1", "#4CAF50", "#9AA3B2",
        ]
        warna_plot = [palet[min(peringkat - 1, len(palet) - 1)] for peringkat in peringkat_plot]
        customdata = [
            [peringkat, nilai, persen]
            for peringkat, nilai, persen in zip(peringkat_plot, nilai_plot, persentase_plot)
        ]
        nilai_maksimum = max(max(nilai_plot), 1)
        tinggi_chart = max(410, min(640, 230 + len(label_plot) * 43))

        with st.container(border=True):
            st.markdown('<span class="dataset-v21-topic-chart-marker"></span>', unsafe_allow_html=True)
            st.markdown(
                f"""
                <div class="dataset-v21-topic-chart-head">
                    <div class="dataset-v21-topic-chart-title-wrap">
                        <div class="dataset-v21-topic-chart-icon">▤</div>
                        <div>
                            <div class="dataset-v21-topic-chart-title">Peta Frekuensi Topik</div>
                            <div class="dataset-v21-topic-chart-note">
                                Topik dominan: {escape(topik_dominan)} · {jumlah_dominan} komentar ({persentase_dominan:.1f}%)
                            </div>
                        </div>
                    </div>
                    <div class="dataset-v21-topic-chart-badge">Hover & ubah mode</div>
                </div>
                """,
                unsafe_allow_html=True,
            )

            mode_topik = str(st.session_state.get(STATE_TOPIK_MODE, "Jumlah"))
            if mode_topik not in {"Jumlah", "Persentase"}:
                mode_topik = "Jumlah"
                st.session_state[STATE_TOPIK_MODE] = mode_topik

            ruang_kiri, tombol_jumlah, tombol_persentase, ruang_kanan = st.columns(
                [3.45, 1.12, 1.12, 3.45],
                gap="small",
            )
            with ruang_kiri:
                st.markdown(
                    '<span class="dataset-v21-topic-mode-row-marker"></span>',
                    unsafe_allow_html=True,
                )
            with tombol_jumlah:
                kelas_jumlah = (
                    "dataset-v21-topic-mode-marker dataset-v21-topic-mode-active"
                    if mode_topik == "Jumlah"
                    else "dataset-v21-topic-mode-marker"
                )
                st.markdown(f'<span class="{kelas_jumlah}"></span>', unsafe_allow_html=True)
                st.button(
                    "▦ Jumlah",
                    key="dataset_v21_mode_jumlah",
                    on_click=_atur_mode_topik_upload,
                    args=("Jumlah",),
                    **_opsi_lebar_penuh(st.button),
                )
            with tombol_persentase:
                kelas_persentase = (
                    "dataset-v21-topic-mode-marker dataset-v21-topic-mode-active"
                    if mode_topik == "Persentase"
                    else "dataset-v21-topic-mode-marker"
                )
                st.markdown(f'<span class="{kelas_persentase}"></span>', unsafe_allow_html=True)
                st.button(
                    "% Persentase",
                    key="dataset_v21_mode_persentase",
                    on_click=_atur_mode_topik_upload,
                    args=("Persentase",),
                    **_opsi_lebar_penuh(st.button),
                )
            with ruang_kanan:
                st.empty()

            mode_topik = str(st.session_state.get(STATE_TOPIK_MODE, mode_topik))
            tampil_persentase = mode_topik == "Persentase"
            nilai_aktif = persentase_plot if tampil_persentase else nilai_plot
            teks_aktif = (
                [f"{persen:.1f}%" for persen in persentase_plot]
                if tampil_persentase
                else [_format_angka(nilai) for nilai in nilai_plot]
            )
            batas_aktif = (
                max(max(persentase_plot) * 1.22, 10)
                if tampil_persentase
                else nilai_maksimum * 1.18
            )

            figur_topik = go.Figure(
                data=[
                    go.Bar(
                        x=nilai_aktif,
                        y=label_plot,
                        orientation="h",
                        marker={
                            "color": warna_plot,
                            "line": {"color": "rgba(255,255,255,0.15)", "width": 1},
                        },
                        selected={"marker": {"opacity": 1.0}},
                        unselected={"marker": {"opacity": 0.42}},
                        width=0.62,
                        customdata=customdata,
                        text=teks_aktif,
                        textposition="outside",
                        textfont={"color": "#FFFFFF", "size": 12},
                        cliponaxis=False,
                        hovertemplate=(
                            "<b>%{y}</b><br>"
                            "Peringkat: #%{customdata[0]}<br>"
                            "Jumlah: %{customdata[1]:,} komentar<br>"
                            "Persentase: %{customdata[2]:.1f}%<extra></extra>"
                        ),
                    )
                ]
            )
            figur_topik.update_xaxes(
                title_text=("Persentase Data" if tampil_persentase else "Jumlah Komentar"),
                range=[0, batas_aktif],
                showgrid=True,
                gridcolor="rgba(255,255,255,0.06)",
                griddash="dot",
                zeroline=False,
                tickfont={"color": "#AEB5C2", "size": 10},
                title_font={"color": "#D6DAE3", "size": 11},
                ticksuffix=("%" if tampil_persentase else ""),
            )
            figur_topik.update_yaxes(
                title_text="",
                showgrid=False,
                tickfont={"color": "#E8EBF2", "size": 11},
                automargin=True,
            )
            figur_topik.update_layout(
                height=tinggi_chart,
                bargap=0.34,
                showlegend=False,
                clickmode="event+select",
                hovermode="closest",
                hoverlabel={
                    "bgcolor": "#151A24",
                    "bordercolor": "rgba(255,255,255,0.14)",
                    "font": {"color": "#FFFFFF", "size": 12},
                },
                transition={"duration": 520, "easing": "cubic-in-out"},
                margin={"l": 28, "r": 72, "t": 30, "b": 54},
            )
            _konfigurasi_chart_upload(figur_topik)
            figur_topik.update_layout(margin={"l": 28, "r": 72, "t": 30, "b": 54})
            _plotly_chart_aman(
                figur_topik,
                config={
                    "displayModeBar": False,
                    "displaylogo": False,
                    "responsive": True,
                },
                **_opsi_lebar_penuh(st.plotly_chart),
            )
            st.markdown(
                """
                <div class="dataset-v21-topic-hint">
                    <span>↗</span>
                    <span>Arahkan kursor untuk melihat detail, klik bar untuk fokus, lalu pilih mode Jumlah atau Persentase pada tombol di tengah.</span>
                </div>
                """,
                unsafe_allow_html=True,
            )
    except Exception as exc:
        LOGGER.exception("Topik interaktif upload gagal dirender")
        st.error(f"Visualisasi Top 10 topik tidak dapat ditampilkan. Detail: {exc}")

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
            <div class="dataset-v18-sentiment-section" tabindex="0">
                <div class="dataset-v18-sentiment-section-left">
                    <div class="dataset-v18-sentiment-section-icon">◔</div>
                    <div>
                        <div class="dataset-v18-sentiment-section-title">Distribusi Sentimen</div>
                        <div class="dataset-v18-sentiment-section-note">
                            Eksplorasi respons publik melalui hover, klik legenda, dan transisi mode grafik.
                        </div>
                    </div>
                </div>
                <div class="dataset-v18-sentiment-dominant" tabindex="0">
                    Dominan: {escape(sentimen_dominan)} · {persentase_dominan:.1f}%
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )
        _render_ringkasan_interaktif_sentimen_upload(jumlah, total)

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
                                "line": {"color": "#111620", "width": 3},
                            },
                            hole=0.56,
                            pull=[0.035 if nilai > 0 else 0 for nilai in nilai_sentimen],
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
                            "showactive": False,
                            "bgcolor": "rgba(17,21,30,0.94)",
                            "bordercolor": "rgba(142,114,255,0.34)",
                            "borderwidth": 1,
                            "pad": {"l": 4, "r": 4, "t": 3, "b": 3},
                            "font": {"color": "#F4F1FF", "size": 10},
                            "buttons": [
                                {
                                    "label": "◔ Persentase",
                                    "method": "restyle",
                                    "args": [{"texttemplate": "%{label}<br><b>%{percent}</b>"}],
                                },
                                {
                                    "label": "▦ Jumlah",
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
                _plotly_chart_aman(
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
                            width=0.60,
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
                            "showactive": False,
                            "bgcolor": "rgba(17,21,30,0.94)",
                            "bordercolor": "rgba(229,57,53,0.34)",
                            "borderwidth": 1,
                            "pad": {"l": 4, "r": 4, "t": 3, "b": 3},
                            "font": {"color": "#FFF1F0", "size": 10},
                            "buttons": [
                                {
                                    "label": "▦ Jumlah",
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
                                    "label": "% Persentase",
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
                _plotly_chart_aman(
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

        _render_wordcloud_interaktif_upload(
            data[kolom_teks],
            judul="WordCloud Interaktif",
            subjudul=(
                "Temukan kata yang paling menonjol dan ubah palet, jumlah kata, "
                "atau tata letaknya secara langsung."
            ),
        )

        if "topik" not in data.columns:
            st.error("Kolom topik belum tersedia pada hasil analisis.")
        else:
            _render_topik_interaktif_upload(data["topik"])

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


def _render_panel_tidak_relevan_upload(
    *,
    jumlah_baris: int,
    jumlah_kolom: int,
    kolom_teks: str,
    rata_panjang: float,
) -> None:
    """Render panel hero interaktif untuk data upload yang tidak relevan."""
    st.markdown(
        f"""
        <style>
            @keyframes datasetV22NebulaPulse {{
                0%, 100% {{ transform: translateY(0px) scale(1); opacity: 0.92; }}
                50% {{ transform: translateY(-6px) scale(1.03); opacity: 1; }}
            }}
            @keyframes datasetV22GlowSweep {{
                0% {{ transform: translateX(-130%) skewX(-16deg); opacity: 0; }}
                22% {{ opacity: 0.34; }}
                100% {{ transform: translateX(240%) skewX(-16deg); opacity: 0; }}
            }}
            @keyframes datasetV22SoftBeat {{
                0%, 100% {{ box-shadow: 0 0 0 0 rgba(255,167,38,0.22); }}
                50% {{ box-shadow: 0 0 0 10px rgba(255,167,38,0); }}
            }}
            .dataset-v22-shell {{
                position: relative;
                overflow: hidden;
                margin: 0.35rem 0 1.1rem;
                padding: 1.18rem 1.18rem 1rem;
                border-radius: 24px;
                border: 1px solid rgba(255,167,38,0.18);
                background:
                    radial-gradient(circle at 14% 14%, rgba(255,167,38,0.14), transparent 32%),
                    radial-gradient(circle at 88% 16%, rgba(142,90,247,0.14), transparent 26%),
                    linear-gradient(135deg, rgba(8,16,30,0.98), rgba(10,22,48,0.96));
                box-shadow: 0 20px 46px rgba(0,0,0,0.24);
            }}
            .dataset-v22-shell::after {{
                content: '';
                position: absolute;
                inset: 0;
                background: linear-gradient(120deg, transparent 0%, rgba(255,255,255,0.08) 48%, transparent 100%);
                transform: translateX(-130%) skewX(-16deg);
                animation: datasetV22GlowSweep 9s linear infinite;
                pointer-events: none;
            }}
            .dataset-v22-head {{
                display: flex;
                justify-content: space-between;
                gap: 1rem;
                align-items: flex-start;
                flex-wrap: wrap;
            }}
            .dataset-v22-head-main {{ display:flex; gap:0.95rem; align-items:flex-start; max-width: 830px; }}
            .dataset-v22-icon {{
                width: 52px; height: 52px; min-width:52px; border-radius: 18px;
                display:flex; align-items:center; justify-content:center;
                background: linear-gradient(135deg, rgba(255,167,38,0.24), rgba(229,57,53,0.18));
                border: 1px solid rgba(255,167,38,0.26);
                font-size: 1.35rem; color:#FFD180;
                animation: datasetV22NebulaPulse 3.6s ease-in-out infinite;
            }}
            .dataset-v22-title {{ color:#FFFFFF; font-size: clamp(1.35rem, 2.15vw, 1.95rem); font-weight:800; line-height:1.12; letter-spacing:-0.03em; }}
            .dataset-v22-subtitle {{ color:#C3CBDA; font-size:0.95rem; line-height:1.7; margin-top:0.34rem; }}
            .dataset-v22-badge-row {{ display:flex; gap:0.58rem; flex-wrap:wrap; margin-top:0.85rem; }}
            .dataset-v22-badge {{
                display:inline-flex; align-items:center; gap:0.42rem; padding:0.44rem 0.82rem; border-radius:999px;
                background: rgba(255,255,255,0.06); border:1px solid rgba(255,255,255,0.11);
                color:#F5F7FB; font-size:0.78rem; font-weight:700; letter-spacing:0.01em;
                transition: transform 180ms ease, box-shadow 180ms ease, border-color 180ms ease;
            }}
            .dataset-v22-badge:hover {{ transform: translateY(-2px); box-shadow: 0 12px 24px rgba(0,0,0,0.16); border-color: rgba(255,167,38,0.28); }}
            .dataset-v22-live {{
                display:inline-flex; align-items:center; gap:0.55rem; padding:0.78rem 1rem; border-radius:18px;
                background: rgba(255,167,38,0.10); border:1px solid rgba(255,167,38,0.18);
                color:#FFE1B2; font-weight:800; font-size:0.84rem; min-height: 50px;
            }}
            .dataset-v22-live span {{ width: 10px; height: 10px; border-radius:999px; background:#FFA726; animation: datasetV22SoftBeat 1.8s ease-in-out infinite; }}
            .dataset-v22-grid {{ display:grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap:0.9rem; margin-top: 1.12rem; }}
            .dataset-v22-card {{
                position:relative; overflow:hidden; min-height:128px; border-radius:20px; padding:1rem 1rem 0.95rem;
                background: linear-gradient(180deg, rgba(255,255,255,0.06), rgba(255,255,255,0.03));
                border:1px solid rgba(255,255,255,0.10);
                transition: transform 180ms ease, border-color 180ms ease, box-shadow 180ms ease;
            }}
            .dataset-v22-card:hover {{ transform: translateY(-4px); border-color: rgba(255,167,38,0.24); box-shadow: 0 18px 32px rgba(0,0,0,0.20); }}
            .dataset-v22-card::before {{ content:''; position:absolute; inset:auto -24% 0 auto; width:108px; height:108px; border-radius:999px; background: var(--panel-soft); filter: blur(12px); opacity:0.62; }}
            .dataset-v22-card-kicker {{ color:#9FA9BD; font-size:0.76rem; font-weight:700; text-transform:uppercase; letter-spacing:0.09em; }}
            .dataset-v22-card-value {{ color:#FFFFFF; font-size:1.6rem; font-weight:800; line-height:1.08; margin-top:0.36rem; }}
            .dataset-v22-card-note {{ color:#C3CBDA; font-size:0.82rem; line-height:1.55; margin-top:0.28rem; }}
            .dataset-v22-card-meter {{ margin-top:0.72rem; height:6px; border-radius:999px; background: rgba(255,255,255,0.08); overflow:hidden; }}
            .dataset-v22-card-meter > span {{ display:block; height:100%; width: var(--meter); border-radius:999px; background: linear-gradient(90deg, var(--panel-accent), rgba(255,255,255,0.94)); transform-origin:left; animation: datasetV18BarLoad 950ms ease forwards; }}
            .dataset-v22-section-title {{ color:#FFFFFF; font-size:1.04rem; font-weight:800; letter-spacing:-0.02em; margin:1rem 0 0.2rem; }}
            .dataset-v22-section-note {{ color:#98A3B7; font-size:0.85rem; margin-bottom:0.82rem; }}
            @media (max-width: 980px) {{ .dataset-v22-grid {{ grid-template-columns: repeat(2, minmax(0,1fr)); }} }}
            @media (max-width: 640px) {{ .dataset-v22-grid {{ grid-template-columns: 1fr; }} .dataset-v22-shell {{ padding: 1rem 0.95rem 0.92rem; }} }}
        </style>
        <section class="dataset-v22-shell">
            <div class="dataset-v22-head">
                <div class="dataset-v22-head-main">
                    <div class="dataset-v22-icon">✦</div>
                    <div>
                        <div class="dataset-v22-title">Eksplorasi Data Umum di Luar Konteks Telkom Group</div>
                        <div class="dataset-v22-subtitle">
                            Dataset ini belum teridentifikasi sebagai percakapan tentang IndiHome, IndiBiz, Telkomsel, atau Telkom Group.
                            Namun, dashboard tetap menampilkan visual yang aman, informatif, dan interaktif untuk membantu membaca pola umum.
                        </div>
                        <div class="dataset-v22-badge-row">
                            <span class="dataset-v22-badge">🛡️ Analisis Aman</span>
                            <span class="dataset-v22-badge">☁️ WordCloud Tetap Aktif</span>
                            <span class="dataset-v22-badge">📊 Struktur Data Terbaca</span>
                            <span class="dataset-v22-badge">✨ Visual Interaktif</span>
                        </div>
                    </div>
                </div>
                <div class="dataset-v22-live"><span></span>Mode eksplorasi umum aktif</div>
            </div>
            <div class="dataset-v22-grid">
                <div class="dataset-v22-card" tabindex="0" style="--panel-accent:#FF7043; --panel-soft:rgba(255,112,67,0.24); --meter:{min(100, max(18, round(jumlah_baris/(jumlah_baris+jumlah_kolom+1)*100)))}%;">
                    <div class="dataset-v22-card-kicker">Jumlah Baris</div>
                    <div class="dataset-v22-card-value">{_format_angka(jumlah_baris)}</div>
                    <div class="dataset-v22-card-note">Total data yang berhasil dibaca dari file upload.</div>
                    <div class="dataset-v22-card-meter"><span></span></div>
                </div>
                <div class="dataset-v22-card" tabindex="0" style="--panel-accent:#7C4DFF; --panel-soft:rgba(124,77,255,0.24); --meter:{min(100, max(18, round(jumlah_kolom/(jumlah_baris+jumlah_kolom+1)*100)))}%;">
                    <div class="dataset-v22-card-kicker">Jumlah Kolom</div>
                    <div class="dataset-v22-card-value">{_format_angka(jumlah_kolom)}</div>
                    <div class="dataset-v22-card-note">Struktur kolom yang tersedia untuk diamati lebih lanjut.</div>
                    <div class="dataset-v22-card-meter"><span></span></div>
                </div>
                <div class="dataset-v22-card" tabindex="0" style="--panel-accent:#29B6F6; --panel-soft:rgba(41,182,246,0.24); --meter:84%;">
                    <div class="dataset-v22-card-kicker">Kolom Teks Aktif</div>
                    <div class="dataset-v22-card-value">{escape(kolom_teks)}</div>
                    <div class="dataset-v22-card-note">Kolom ini dipakai untuk membaca pola kata dan WordCloud.</div>
                    <div class="dataset-v22-card-meter"><span></span></div>
                </div>
                <div class="dataset-v22-card" tabindex="0" style="--panel-accent:#66BB6A; --panel-soft:rgba(102,187,106,0.24); --meter:{min(100, max(22, round(min(rata_panjang, 180)/180*100)))}%;">
                    <div class="dataset-v22-card-kicker">Rata-rata Panjang Teks</div>
                    <div class="dataset-v22-card-value">{_format_angka(int(round(rata_panjang)))} karakter</div>
                    <div class="dataset-v22-card-note">Perkiraan panjang isi teks yang membantu membaca kepadatan narasi.</div>
                    <div class="dataset-v22-card-meter"><span></span></div>
                </div>
            </div>
        </section>
        """,
        unsafe_allow_html=True,
    )


def _render_subbagian_tidak_relevan_upload(
    judul: str,
    subjudul: str,
    ikon: str,
    accent: str = "amber",
) -> None:
    """Render heading dekoratif untuk subbagian analisis data tidak relevan."""
    st.markdown(
        f"""
        <style>
            .dataset-v22-subsection {{
                position: relative;
                overflow: hidden;
                margin: 1.05rem 0 0.8rem;
                padding: 0.9rem 1rem;
                border-radius: 20px;
                border: 1px solid rgba(255,255,255,0.08);
                background: linear-gradient(135deg, rgba(13,22,42,0.95), rgba(8,18,34,0.90));
                box-shadow: 0 16px 30px rgba(0,0,0,0.16);
                display: flex;
                align-items: center;
                justify-content: space-between;
                gap: 0.9rem;
                flex-wrap: wrap;
            }}
            .dataset-v22-subsection::before {{
                content: '';
                position: absolute;
                inset: 0;
                background: linear-gradient(110deg, transparent 0%, rgba(255,255,255,0.06) 45%, transparent 100%);
                transform: translateX(-130%) skewX(-18deg);
                animation: datasetV22GlowSweep 8s linear infinite;
                pointer-events: none;
            }}
            .dataset-v22-sub-left {{ display:flex; align-items:center; gap:0.85rem; max-width: 900px; }}
            .dataset-v22-sub-icon {{
                width: 46px; height: 46px; min-width: 46px; border-radius: 16px;
                display:flex; align-items:center; justify-content:center;
                font-size: 1.18rem; color:#fff;
                background: linear-gradient(135deg, var(--sub-accent), rgba(255,255,255,0.08));
                box-shadow: 0 10px 22px rgba(0,0,0,0.18);
                border: 1px solid rgba(255,255,255,0.12);
            }}
            .dataset-v22-sub-title {{ color:#FFFFFF; font-weight:800; font-size:1.16rem; letter-spacing:-0.02em; line-height:1.12; }}
            .dataset-v22-sub-note {{ color:#A8B3C7; font-size:0.84rem; line-height:1.6; margin-top:0.18rem; }}
            .dataset-v22-sub-pill {{
                display:inline-flex; align-items:center; gap:0.45rem; padding:0.5rem 0.85rem; border-radius:999px;
                color:#F6F8FC; font-size:0.78rem; font-weight:700;
                border:1px solid rgba(255,255,255,0.10);
                background: rgba(255,255,255,0.05);
                transition: transform 180ms ease, box-shadow 180ms ease, border-color 180ms ease;
            }}
            .dataset-v22-sub-pill:hover {{ transform: translateY(-2px); box-shadow: 0 12px 22px rgba(0,0,0,0.14); border-color: rgba(255,255,255,0.18); }}
            @media (max-width: 640px) {{
                .dataset-v22-subsection {{ padding: 0.88rem 0.92rem; }}
                .dataset-v22-sub-left {{ align-items:flex-start; }}
            }}
        </style>
        <div class="dataset-v22-subsection" style="--sub-accent:{'#FF9F43' if accent=='amber' else '#8E5AF7' if accent=='purple' else '#38D7FF'};">
            <div class="dataset-v22-sub-left">
                <div class="dataset-v22-sub-icon">{escape(ikon)}</div>
                <div>
                    <div class="dataset-v22-sub-title">{escape(judul)}</div>
                    <div class="dataset-v22-sub-note">{escape(subjudul)}</div>
                </div>
            </div>
            <div class="dataset-v22-sub-pill">✨ Interaktif & aman</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def _render_hasil_tidak_relevan_upload(
    data: pd.DataFrame,
    kolom_teks: str | None,
) -> None:
    """Render analisis terbatas untuk upload yang tidak relevan dengan Telkom Group."""
    try:
        _render_warning_banner_upload(
            "Data tidak dikenali sebagai data Telkom Group",
            "Hasil analisis mungkin tidak relevan dengan konteks penelitian. Dashboard akan menampilkan analisis terbatas agar struktur data tetap bisa dibaca secara aman, informatif, dan tetap menarik secara visual.",
            ["Analisis Terbatas", "Bukan Dataset Telkom", "WordCloud Tetap Tersedia", "Histogram Tetap Tersedia"],
            compact=False,
        )

        kolom_teks_aktif = kolom_teks or _deteksi_kolom_teks_upload(data)
        if not kolom_teks_aktif or kolom_teks_aktif not in data.columns:
            st.error(
                "Kolom teks tidak ditemukan. Tambahkan kolom komentar, content, text, "
                "caption, atau kolom teks sejenis."
            )
            return

        panjang_teks = data[kolom_teks_aktif].fillna("").astype(str).str.len()
        rata_panjang = float(panjang_teks.mean()) if len(panjang_teks) else 0.0
        _render_panel_tidak_relevan_upload(
            jumlah_baris=len(data),
            jumlah_kolom=len(data.columns),
            kolom_teks=str(kolom_teks_aktif),
            rata_panjang=rata_panjang,
        )

        _render_subbagian_tidak_relevan_upload(
            "Struktur Dataset",
            "Ringkasan struktur tetap ditampilkan agar Anda dapat memahami isi file meskipun konteksnya bukan data Telkom Group.",
            "▦",
            accent="amber",
        )
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
        _dataframe_responsif(tabel_unik, **_opsi_lebar_penuh(st.dataframe))

        _render_subbagian_tidak_relevan_upload(
            "Distribusi Panjang Teks",
            "Histogram interaktif ini membantu melihat kepadatan panjang teks dan persebaran karakter pada setiap baris data.",
            "◉",
            accent="cyan",
        )
        figur_histogram = go.Figure(
            data=[
                go.Histogram(
                    x=panjang_teks.tolist(),
                    marker={"color": "#E53935"},
                    hovertemplate="Panjang teks: %{x}<br>Jumlah data: %{y}<extra></extra>",
                )
            ]
        )
        figur_histogram.update_layout(title="Distribusi Panjang Teks", bargap=0.06)
        figur_histogram.update_xaxes(title_text="Panjang Teks (karakter)")
        figur_histogram.update_yaxes(title_text="Jumlah Data")
        _konfigurasi_chart_upload(figur_histogram)
        _plotly_chart_aman(
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
            if kolom_teks and kolom_teks in data_hasil.columns:
                _render_hasil_relevan_upload(
                    data_hasil,
                    str(kolom_teks),
                    kolom_platform,
                )
            return

        # File nonrelevan tanpa kolom teks tetap selesai dianalisis melalui
        # status relevansi, preview, metrik, dan daftar kolom yang sudah tampil.
        if kolom_teks and kolom_teks in data_hasil.columns:
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




def _render_warning_banner_upload(
    judul: str,
    deskripsi: str,
    chips: list[str] | None = None,
    compact: bool = False,
) -> None:
    """Render badge warning interaktif untuk status upload yang tidak relevan."""
    chips = chips or []
    kelas_varian = "dataset-v18-warning-compact" if compact else "dataset-v18-warning-full"
    badge_teks = "Perlu Tinjau" if compact else "Analisis Terbatas"
    chip_html = "".join(
        f'<span class="dataset-v18-warning-chip">{escape(str(chip))}</span>'
        for chip in chips
    )

    css = """
    <style>
    @keyframes datasetV18WarningIn {
        from { opacity: 0; transform: translateY(10px) scale(0.99); }
        to { opacity: 1; transform: translateY(0) scale(1); }
    }
    @keyframes datasetV18WarningPulse {
        0%, 100% { box-shadow: 0 0 0 0 rgba(255, 211, 86, 0.00); }
        50% { box-shadow: 0 0 0 9px rgba(255, 211, 86, 0.08); }
    }
    @keyframes datasetV18WarningSweep {
        from { transform: translateX(-150%); }
        to { transform: translateX(470%); }
    }
    .dataset-v18-warning-card {
        background:
            radial-gradient(circle at 7% 18%, rgba(255, 214, 102, 0.18), transparent 19%),
            radial-gradient(circle at 95% 12%, rgba(229, 57, 53, 0.10), transparent 24%),
            linear-gradient(135deg, rgba(63, 56, 8, 0.96), rgba(42, 37, 10, 0.95) 52%, rgba(25, 24, 16, 0.98));
        border: 1px solid rgba(255, 211, 86, 0.32);
        border-radius: 16px;
        box-shadow: 0 12px 28px rgba(0, 0, 0, 0.22);
        color: #FFFFFF;
        cursor: default;
        margin: 0.90rem 0 1.05rem;
        overflow: hidden;
        padding: 1rem 1.05rem;
        position: relative;
        transition: transform 220ms ease, border-color 220ms ease, box-shadow 220ms ease;
        animation: datasetV18WarningIn 480ms ease both;
    }
    .dataset-v18-warning-card::before {
        background: linear-gradient(180deg, #FFE28A, #F2C94C 52%, #D89A17);
        bottom: 0;
        content: "";
        left: 0;
        position: absolute;
        top: 0;
        width: 4px;
    }
    .dataset-v18-warning-card::after {
        background: linear-gradient(90deg, transparent, rgba(255,255,255,0.14), transparent);
        content: "";
        height: 100%;
        left: -32%;
        position: absolute;
        top: 0;
        width: 25%;
    }
    .dataset-v18-warning-card:hover,
    .dataset-v18-warning-card:focus {
        border-color: rgba(255, 226, 138, 0.62);
        box-shadow: 0 18px 38px rgba(0,0,0,0.30), 0 0 28px rgba(242,201,76,0.12);
        outline: none;
        transform: translateY(-3px);
    }
    .dataset-v18-warning-card:hover::after,
    .dataset-v18-warning-card:focus::after {
        animation: datasetV18WarningSweep 1.05s ease;
    }
    .dataset-v18-warning-inner {
        align-items: center;
        display: flex;
        gap: 0.95rem;
        position: relative;
        z-index: 2;
    }
    .dataset-v18-warning-compact .dataset-v18-warning-inner {
        align-items: flex-start;
    }
    .dataset-v18-warning-icon-wrap {
        align-items: center;
        animation: datasetV18WarningPulse 2.6s ease-in-out infinite;
        background: linear-gradient(145deg, rgba(255,226,138,0.18), rgba(216,154,23,0.14));
        border: 1px solid rgba(255,226,138,0.28);
        border-radius: 14px;
        display: flex;
        flex: 0 0 50px;
        height: 50px;
        justify-content: center;
        transition: transform 220ms ease, background 220ms ease;
        width: 50px;
    }
    .dataset-v18-warning-card:hover .dataset-v18-warning-icon-wrap,
    .dataset-v18-warning-card:focus .dataset-v18-warning-icon-wrap {
        background: linear-gradient(145deg, rgba(255,226,138,0.26), rgba(216,154,23,0.20));
        transform: rotate(-6deg) scale(1.07);
    }
    .dataset-v18-warning-icon {
        color: #FFE28A;
        font-size: 1.45rem;
        line-height: 1;
    }
    .dataset-v18-warning-copy {
        flex: 1;
        min-width: 0;
    }
    .dataset-v18-warning-topline {
        align-items: center;
        display: flex;
        gap: 0.70rem;
        justify-content: space-between;
        margin-bottom: 0.30rem;
    }
    .dataset-v18-warning-title {
        color: #FFF8D6;
        font-family: 'Plus Jakarta Sans', 'Inter', sans-serif;
        font-size: 1rem;
        font-weight: 800;
        letter-spacing: -0.02em;
        line-height: 1.28;
    }
    .dataset-v18-warning-status {
        background: rgba(255,226,138,0.11);
        border: 1px solid rgba(255,226,138,0.24);
        border-radius: 999px;
        color: #FFE28A;
        flex: 0 0 auto;
        font-size: 0.75rem /* FIX: minimum 12px agar terbaca di tablet */;
        font-weight: 800;
        line-height: 1;
        padding: 0.42rem 0.60rem;
        white-space: nowrap;
    }
    .dataset-v18-warning-note {
        color: #D8CF9A;
        font-size: 0.75rem /* FIX: minimum 12px agar terbaca di tablet */;
        line-height: 1.55;
        max-width: 930px;
    }
    .dataset-v18-warning-chips {
        display: flex;
        flex-wrap: wrap;
        gap: 0.44rem;
        margin-top: 0.65rem;
    }
    .dataset-v18-warning-chip {
        background: rgba(255,255,255,0.045);
        border: 1px solid rgba(255,226,138,0.16);
        border-radius: 999px;
        color: #F4E7A2;
        font-size: 0.75rem /* FIX: minimum 12px agar terbaca di tablet */;
        font-weight: 700;
        padding: 0.34rem 0.56rem;
        transition: transform 180ms ease, background 180ms ease, border-color 180ms ease, color 180ms ease;
    }
    .dataset-v18-warning-chip:hover {
        background: rgba(255,226,138,0.12);
        border-color: rgba(255,226,138,0.34);
        color: #FFFFFF;
        transform: translateY(-2px);
    }
    @media (max-width: 760px) {
        .dataset-v18-warning-inner { align-items: flex-start; }
        .dataset-v18-warning-topline { align-items: flex-start; flex-direction: column; }
        .dataset-v18-warning-status { margin-top: 0.15rem; }
    }
    @media (prefers-reduced-motion: reduce) {
        .dataset-v18-warning-card,
        .dataset-v18-warning-icon-wrap,
        .dataset-v18-warning-chip {
            animation: none !important;
            transition: none !important;
        }
        .dataset-v18-warning-card:hover,
        .dataset-v18-warning-card:focus,
        .dataset-v18-warning-card:hover .dataset-v18-warning-icon-wrap,
        .dataset-v18-warning-card:focus .dataset-v18-warning-icon-wrap,
        .dataset-v18-warning-chip:hover {
            transform: none !important;
        }
    }
    </style>
    """

    html = (
        f'<div class="dataset-v18-warning-card {kelas_varian}" tabindex="0">'
        '<div class="dataset-v18-warning-inner">'
        '<div class="dataset-v18-warning-icon-wrap" aria-hidden="true">'
        '<div class="dataset-v18-warning-icon">⚠</div>'
        '</div>'
        '<div class="dataset-v18-warning-copy">'
        '<div class="dataset-v18-warning-topline">'
        f'<div class="dataset-v18-warning-title">{escape(judul)}</div>'
        f'<div class="dataset-v18-warning-status">{escape(badge_teks)}</div>'
        '</div>'
        f'<div class="dataset-v18-warning-note">{escape(deskripsi)}</div>'
        f'<div class="dataset-v18-warning-chips">{chip_html}</div>'
        '</div>'
        '</div>'
        '</div>'
    )
    st.markdown(css + html, unsafe_allow_html=True)


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

            if sudah_dianalisis and isinstance(data_tersimpan, pd.DataFrame):
                log_activity(
                    "UPLOAD_ANALYSIS",
                    "Dataset",
                    f"Menganalisis file upload {nama_file_tersimpan} dengan {len(data_tersimpan)} baris.",
                    status="success",
                    metadata={
                        "file_name": nama_file_tersimpan,
                        "file_extension": ekstensi,
                        "file_size": len(file_bytes_tersimpan),
                        "rows": len(data_tersimpan),
                        "columns": len(data_tersimpan.columns),
                        "is_relevant": bool(st.session_state.get(STATE_IS_RELEVANT, False)),
                        "relevance_source": st.session_state.get(STATE_UPLOAD_RELEVANCE_SOURCE),
                    },
                )
            elif pesan_error_analisis:
                log_activity(
                    "UPLOAD_ANALYSIS",
                    "Dataset",
                    f"Analisis file upload {nama_file_tersimpan} gagal.",
                    status="failed",
                    metadata={
                        "file_name": nama_file_tersimpan,
                        "file_extension": ekstensi,
                        "file_size": len(file_bytes_tersimpan),
                        "reason": pesan_error_analisis,
                    },
                )

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
        _dataframe_responsif(
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
            _render_warning_banner_upload(
                "Data tidak dikenali sebagai data Telkom Group",
                "File tetap bisa diproses, tetapi sistem akan menampilkan analisis umum berbasis struktur file, bukan konteks penelitian Telkom Group.",
                ["Status Tidak Relevan", "Analisis Umum", "Hover untuk efek visual"],
                compact=True,
            )

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


def _filter_sedang_aktif(
    layanan: str,
    platform: str | list[str],
    sentimen: str,
    pencarian: str,
) -> bool:
    """Periksa apakah minimal satu kontrol filter berbeda dari kondisi awal."""
    platform_aktif = bool(platform) if isinstance(platform, list) else platform != "Semua"
    return any(
        (
            layanan != "IndiHome",
            platform_aktif,
            sentimen != "Semua",
            bool(str(pencarian).strip()),
        )
    )


def _filter_state_sedang_aktif() -> bool:
    """Baca status filter aktif langsung dari session state Streamlit."""
    layanan = str(st.session_state.get(STATE_LAYANAN, "IndiHome"))
    if layanan == "IndiBiz":
        platform: str | list[str] = st.session_state.get(STATE_PLATFORM_INDIBIZ, [])
        if not isinstance(platform, list):
            platform = []
    else:
        platform = str(st.session_state.get(STATE_PLATFORM, "Semua"))

    return _filter_sedang_aktif(
        layanan,
        platform,
        str(st.session_state.get(STATE_SENTIMEN, "Semua")),
        str(st.session_state.get(STATE_PENCARIAN, "")),
    )


def _siapkan_loading_terapkan_filter() -> None:
    """Aktifkan loading hanya ketika pengguna benar-benar mengatur filter."""
    if not _filter_state_sedang_aktif():
        return
    st.session_state[STATE_FILTER_LOADING_LABEL] = "Menerapkan filter dataset..."


def _reset_filter_dengan_loading() -> None:
    """Reset filter hanya ketika minimal satu kontrol sedang aktif."""
    if not _filter_state_sedang_aktif():
        return
    _reset_filter()
    st.session_state[STATE_FILTER_LOADING_LABEL] = "Mereset filter dataset..."


def _siapkan_loading_layar_penuh(judul: str) -> None:
    """Aktifkan custom loading sebelum dialog chart layar penuh dirender."""
    try:
        nama_chart = str(judul).strip() or "grafik"
        st.session_state[STATE_FULLSCREEN_LOADING_LABEL] = (
            f"Membuka layar penuh {nama_chart.lower()}..."
        )
    except Exception:
        LOGGER.exception("Loading custom layar penuh gagal disiapkan")


def _render_penjaga_interaksi_tombol_filter() -> None:
    """Buat tombol filter inert saat seluruh kontrol masih pada nilai awal.

    Tombol tidak memakai atribut ``disabled`` agar tampilan visualnya tetap sama.
    JavaScript hanya memblokir pointer dan keyboard sampai pengguna mengubah
    minimal satu kontrol filter di dalam form.
    """
    render_html_iframe(
        r"""
        <script>
        (() => {
            const parentWindow = window.parent;
            const doc = parentWindow.document;
            const cleanupKey = "__datasetFilterGuardCleanup";

            if (typeof parentWindow[cleanupKey] === "function") {
                parentWindow[cleanupKey]();
            }

            const rapikan = (nilai) => String(nilai || "")
                .replace(/\s+/g, " ")
                .trim();

            const cariTombol = (teks) => Array.from(doc.querySelectorAll("button"))
                .find((tombol) => rapikan(tombol.innerText) === teks);

            const cariKontrol = (form, namaLabel) => {
                if (!form) return null;
                const label = Array.from(form.querySelectorAll("label"))
                    .find((item) => rapikan(item.textContent).toLowerCase() === namaLabel.toLowerCase());
                if (!label) return null;
                return label.closest(
                    '[data-testid="stSelectbox"], ' +
                    '[data-testid="stMultiSelect"], ' +
                    '[data-testid="stTextInput"]'
                );
            };

            const nilaiKontrol = (kontrol) => {
                if (!kontrol) return "";
                if (kontrol.matches('[data-testid="stTextInput"]')) {
                    return rapikan(kontrol.querySelector("input")?.value);
                }
                const bidangPilih = kontrol.querySelector('[data-baseweb="select"]');
                const input = kontrol.querySelector("input");
                return rapikan(
                    bidangPilih?.innerText ||
                    bidangPilih?.textContent ||
                    input?.value ||
                    ""
                );
            };

            const ubahStatusTombol = (tombol, dibuatInert) => {
                if (!tombol) return;
                tombol.dataset.datasetFilterInert = dibuatInert ? "true" : "false";
                tombol.style.pointerEvents = dibuatInert ? "none" : "";
                tombol.style.cursor = dibuatInert ? "default" : "";
                tombol.tabIndex = dibuatInert ? -1 : 0;
            };

            const sinkronkan = () => {
                const tombolTerapkan = cariTombol("Terapkan Filter");
                const tombolReset = cariTombol("Reset Filter");
                const form = tombolTerapkan?.closest('[data-testid="stForm"]') ||
                    tombolTerapkan?.closest("form");
                if (!form || !tombolTerapkan || !tombolReset) return;

                const layanan = nilaiKontrol(cariKontrol(form, "Layanan")).toLowerCase();
                const platform = nilaiKontrol(cariKontrol(form, "Platform")).toLowerCase();
                const sentimen = nilaiKontrol(cariKontrol(form, "Sentimen")).toLowerCase();
                const pencarian = nilaiKontrol(cariKontrol(form, "Cari komentar"));

                const platformAwal = ["", "semua", "semua platform"].includes(platform);
                const filterAktif = layanan !== "indihome" ||
                    !platformAwal ||
                    sentimen !== "semua" ||
                    pencarian.length > 0;

                ubahStatusTombol(tombolTerapkan, !filterAktif);
                ubahStatusTombol(tombolReset, !filterAktif);
            };

            let timer = null;
            const jadwalkanSinkronisasi = () => {
                window.clearTimeout(timer);
                timer = window.setTimeout(sinkronkan, 30);
            };

            const observer = new MutationObserver(jadwalkanSinkronisasi);
            observer.observe(doc.body, {
                subtree: true,
                childList: true,
                characterData: true,
                attributes: true,
                attributeFilter: ["value"]
            });

            doc.addEventListener("input", jadwalkanSinkronisasi, true);
            doc.addEventListener("change", jadwalkanSinkronisasi, true);

            parentWindow[cleanupKey] = () => {
                observer.disconnect();
                doc.removeEventListener("input", jadwalkanSinkronisasi, true);
                doc.removeEventListener("change", jadwalkanSinkronisasi, true);
                window.clearTimeout(timer);
            };

            sinkronkan();
            window.setTimeout(sinkronkan, 250);
        })();
        </script>
        """,
        height=0,
    )


def render_dataset() -> None:
    """Render halaman Dataset untuk IndiHome, IndiBiz, dan Telkomsel."""
    loading_placeholder = None
    loading_filter_handle = None
    try:
        label_loading_upload = st.session_state.pop(STATE_UPLOAD_LOADING_LABEL, None)
        label_loading_filter = st.session_state.pop(STATE_FILTER_LOADING_LABEL, None)
        label_loading_fullscreen = st.session_state.pop(
            STATE_FULLSCREEN_LOADING_LABEL,
            None,
        )
        label_loading_wordcloud = st.session_state.pop(
            STATE_WORDCLOUD_LOADING_LABEL,
            None,
        )
        label_loading_aksi = (
            label_loading_upload
            or label_loading_filter
            or label_loading_fullscreen
            or label_loading_wordcloud
        )
        if label_loading_aksi:
            loading_filter_handle = mulai_loading_aksi(str(label_loading_aksi))

        _inisialisasi_state()
        _sinkronkan_layanan_dataset_saat_masuk()
        _inject_css()
        render_analytics_control_style()
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
                [1.15, 1.30, 1.0, 1.50, 1.05, 0.9],
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

        _render_penjaga_interaksi_tombol_filter()

        if tombol_terapkan:
            st.session_state["active_service"] = layanan

        if tombol_terapkan and _filter_sedang_aktif(
            layanan,
            platform,
            sentimen,
            pencarian,
        ):
            # Setiap penerapan filter kembali ke halaman tabel pertama.
            st.session_state[STATE_HALAMAN] = 1
            st.session_state[STATE_SIGNATURE] = None

        _render_badge_layanan_aktif(metadata, layanan)

        data_layanan = data_semua[data_semua["layanan"].eq(layanan)].copy()

        data_filter = _terapkan_filter(
            data_semua,
            layanan,
            platform,
            sentimen,
            pencarian,
        )
        if data_filter.empty:
            st.info("Tidak ada data untuk filter ini.")

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
        elif layanan in {"IndiHome", "Telkomsel"}:
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
                    _plotly_chart_aman(
                        figur_platform,
                        config={"displayModeBar": False, "responsive": True},
                        **_opsi_lebar_penuh(st.plotly_chart),
                    )
                with chart_kanan:
                    st.markdown(
                        '<div class="dataset-v6-section-title">Distribusi Sentimen</div>',
                        unsafe_allow_html=True,
                    )
                    _plotly_chart_aman(
                        figur_sentimen,
                        config={"displayModeBar": False, "responsive": True},
                        **_opsi_lebar_penuh(st.plotly_chart),
                    )
            _render_preview_sna_indibiz()

        elif layanan in {"IndiHome", "Telkomsel"}:
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
                                on_click=_siapkan_loading_layar_penuh,
                                args=("Distribusi Sentimen",),
                                **_opsi_lebar_penuh(st.button),
                            ):
                                _tampilkan_chart_layar_penuh(
                                    "Distribusi Sentimen",
                                    figur_sentimen,
                                    legenda_sentimen,
                                )
                        _plotly_chart_aman(
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
                                on_click=_siapkan_loading_layar_penuh,
                                args=("Distribusi Platform",),
                                **_opsi_lebar_penuh(st.button),
                            ):
                                _tampilkan_chart_layar_penuh(
                                    "Distribusi Platform",
                                    figur_platform,
                                    legenda_platform,
                                )
                        _plotly_chart_aman(
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
