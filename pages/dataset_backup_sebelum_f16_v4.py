"""Halaman eksplorasi dataset penelitian media sosial Telkom Group."""

from __future__ import annotations

import inspect
import logging
import math
import re
from html import escape
from pathlib import Path
from typing import Any

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from utils.data_loader import load_indibiz_sentiment, load_indibiz_sna
from utils.indibiz_config import INDIBIZ_SENTIMENT_CANDIDATES, INDIBIZ_SNA_CANDIDATES
from utils.loading_screen import (
    batalkan_layar_loading,
    mulai_layar_loading,
    selesaikan_layar_loading,
)

LOGGER = logging.getLogger(__name__)

LAYANAN_OPTIONS = ["IndiHome", "IndiBiz"]
PLATFORM_OPTIONS = ["Semua", "Twitter", "Instagram", "TikTok"]
SENTIMEN_OPTIONS = ["Semua", "Positif", "Netral", "Negatif"]
BARIS_PER_HALAMAN_OPTIONS = [10, 25, 50]
DEFAULT_BARIS_PER_HALAMAN = 10
DATASET_CACHE_VERSION = "fase16-hotfix-filter-sentimen-v3"
FILTER_ENGINE_LABEL = "F16.3"

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
        f'{" · Mesin filter " + FILTER_ENGINE_LABEL if layanan == "IndiBiz" else ""}</span>'
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

    kol_node, kol_edge, kol_keterangan = st.columns([1, 1, 2], gap="small")
    with kol_node:
        _render_metric_card("Total Node", _format_angka(total_node), "Akun unik pada jaringan IndiBiz")
    with kol_edge:
        _render_metric_card("Total Edge", _format_angka(total_edge), "Relasi interaksi pada edge list")
    with kol_keterangan:
        st.markdown(
            '<div class="dataset-v6-sna-note">'
            '<strong>Interpretasi singkat</strong><br>'
            'Source menunjukkan akun asal interaksi. Target menunjukkan akun tujuan. '
            'Relationship menjelaskan tipe hubungan, sedangkan Platform menunjukkan sumber media sosial.'
            '</div>',
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
        STATE_PLATFORM_INDIBIZ: ["Twitter", "Instagram", "TikTok"],
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
    st.session_state[STATE_PLATFORM_INDIBIZ] = ["Twitter", "Instagram", "TikTok"]
    st.session_state[STATE_SENTIMEN] = "Semua"
    st.session_state[STATE_PENCARIAN] = ""
    st.session_state[STATE_HALAMAN] = 1
    st.session_state[STATE_SIGNATURE] = None


def _ubah_halaman(perubahan: int, total_halaman: int) -> None:
    """Pindahkan pagination satu halaman ke depan atau ke belakang."""
    halaman = int(st.session_state.get(STATE_HALAMAN, 1)) + perubahan
    st.session_state[STATE_HALAMAN] = min(max(1, halaman), max(1, total_halaman))


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
        if platform:
            hasil = hasil[hasil["platform"].isin(platform)].copy()
        else:
            hasil = hasil.iloc[0:0].copy()
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

            div[data-testid="stColumn"]:has(.dataset-v6-reset-marker) div[data-testid="stButton"] {
                margin: 0 !important;
                padding: 0 !important;
                width: 100% !important;
            }

            div[data-testid="stColumn"]:has(.dataset-v6-reset-marker) div[data-testid="stButton"] button {
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
            div[data-testid="stColumn"]:has(.dataset-v6-reset-marker) div[data-testid="stButton"] button span {
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

            div[data-testid="stColumn"]:has(.dataset-v6-reset-marker) div[data-testid="stButton"] button:hover {
                background: #FF5252 !important;
                border-color: #FF5252 !important;
                box-shadow: 0 0 20px rgba(229,57,53,0.28);
            }

            .dataset-v6-metric-card {
                background: #1A1A1A;
                border: 1px solid #2A2A2A;
                border-left: 3px solid #E53935;
                border-radius: 12px;
                min-height: 132px;
                padding: 1rem 1.1rem;
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

            .dataset-v6-table-title {
                margin-bottom: 0.15rem;
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
                background: #171717;
                border: 1px solid #2A2A2A;
                border-left: 3px solid #E53935;
                border-radius: 12px;
                color: #AAAAAA;
                min-height: 132px;
                padding: 1rem 1.1rem;
            }

            .dataset-v6-sna-note strong {
                color: #FFFFFF;
            }

            div[data-testid="stButton"] button {
                border-radius: 8px;
            }

            @media (max-width: 900px) {
                .dataset-v6-hero { padding: 1.35rem; }
                .dataset-v6-metric-card { min-height: 118px; }
                .dataset-v6-table { font-size: 0.74rem; }
            }
        </style>
        """,
        unsafe_allow_html=True,
    )


def render_dataset() -> None:
    """Render halaman Dataset untuk IndiHome dan IndiBiz tanpa mengubah alur IndiHome."""
    loading_placeholder = None
    try:
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

        kol_layanan, kol_platform, kol_sentimen, kol_cari, kol_reset = st.columns(
            [1.05, 1.45, 1.05, 1.75, 0.85],
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
                    ["Twitter", "Instagram", "TikTok"],
                )
                if not isinstance(nilai_platform, list):
                    st.session_state[STATE_PLATFORM_INDIBIZ] = [
                        "Twitter",
                        "Instagram",
                        "TikTok",
                    ]
                platform: str | list[str] = st.multiselect(
                    "Platform",
                    ["Twitter", "Instagram", "TikTok"],
                    key=STATE_PLATFORM_INDIBIZ,
                    placeholder="Pilih satu atau beberapa platform",
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
        with kol_reset:
            st.markdown(
                '<span class="dataset-v6-reset-marker" aria-hidden="true">Aksi</span>',
                unsafe_allow_html=True,
            )
            st.button(
                "Reset Filter",
                key="dataset_v6_reset_button",
                on_click=_reset_filter,
                **_opsi_lebar_penuh(st.button),
            )

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
