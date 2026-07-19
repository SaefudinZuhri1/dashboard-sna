"""Konfigurasi integrasi file hasil analisis IndiBiz pada website Streamlit."""

from __future__ import annotations

from pathlib import Path

import streamlit as st

# Nama layanan dipakai untuk label antarmuka dan pencarian file.
SERVICE_NAME = "IndiBiz"

# Node pusat resmi pada visualisasi jaringan IndiBiz.
TARGET_NODE = "indibiz"

# Model tetap mengikuti model IndoBERT yang digunakan dalam penelitian.
INDOBERT_MODEL = "mdhugol/indonesia-bert-sentiment-classification"

# None berarti semua baris sentimen boleh dibaca oleh website.
MAX_ROWS_SENTIMENT = None

# Warna platform mengikuti identitas platform dan aksen dashboard.
PLATFORM_COLORS = {
    "twitter": "#1DA1F2",
    "instagram": "#833AB4",
    "tiktok": "#000000",
    "indibiz": "#E53935",
}

# Nama keluaran baku dari pipeline analisis IndiBiz.
OUTPUT_FILES = {
    "sna_csv": "indibiz_output_sna.csv",
    "sna_instagram_tiktok_csv": "indibiz_output_sna_instagram_tiktok.csv",
    "sentiment_csv": "indibiz_output_sentiment.csv",
    "network_graph_png": "indibiz_output_network_graph.png",
    "sentiment_chart_png": "indibiz_output_sentiment_chart.png",
    "wordcloud_png": "indibiz_output_wordcloud.png",
    "wordcloud_positive_png": "indibiz_output_wordcloud_positive.png",
    "wordcloud_neutral_png": "indibiz_output_wordcloud_neutral.png",
    "wordcloud_negative_png": "indibiz_output_wordcloud_negative.png",
    "top_kata_png": "indibiz_output_top_kata.png",
    "top_kata_csv": "indibiz_output_top_kata.csv",
    "top_topic_png": "indibiz_output_top_topic.png",
    "top_topic_csv": "indibiz_output_top_topic.csv",
}

# Urutan kandidat penting karena file keluaran baku diprioritaskan lebih dahulu.
INDIBIZ_SENTIMENT_CANDIDATES = (
    OUTPUT_FILES["sentiment_csv"],
    "indibiz_sentiment.csv",
    "Indibiz- NovemberDesember 2025.xlsx",
    "IndiBiz- NovemberDesember 2025.xlsx",
    "Indibiz NovemberDesember 2025.xlsx",
    "Indibiz- NovemberDesember 2025.csv",
)

# File SNA baku diprioritaskan, tetapi nama lama tetap didukung.
INDIBIZ_SNA_CANDIDATES = (
    OUTPUT_FILES["sna_csv"],
    OUTPUT_FILES["sna_instagram_tiktok_csv"],
    "SNA Indibiz.csv",
    "SNA IndiBiz.csv",
    "SNA Indibiz NovemberDesember.csv",
)


def get_indibiz_output_path(output_key: str, data_dir: str | Path = "data") -> Path:
    """Kembalikan path file output IndiBiz berdasarkan kunci konfigurasi."""
    try:
        filename = OUTPUT_FILES[output_key]
        return Path(data_dir) / filename
    except KeyError:
        st.error(f"Kunci output IndiBiz tidak dikenali: {output_key}")
        return Path(data_dir) / "file_indibiz_tidak_dikenal"
    except Exception as error:
        st.error(f"Gagal membentuk path output IndiBiz: {error}")
        return Path(data_dir) / "file_indibiz_tidak_dikenal"


def get_indibiz_configuration_summary() -> dict[str, object]:
    """Kembalikan ringkasan konfigurasi untuk kebutuhan status atau pengujian."""
    try:
        return {
            "service_name": SERVICE_NAME,
            "target_node": TARGET_NODE,
            "indobert_model": INDOBERT_MODEL,
            "max_rows_sentiment": MAX_ROWS_SENTIMENT,
            "platform_colors": PLATFORM_COLORS.copy(),
            "output_files": OUTPUT_FILES.copy(),
        }
    except Exception as error:
        st.error(f"Gagal membaca konfigurasi IndiBiz: {error}")
        return {}


# Urutan resmi 12 file output Blok A IndiBiz.
BLOCK_A_OUTPUT_ORDER = (
    "sna_csv",
    "sentiment_csv",
    "network_graph_png",
    "sentiment_chart_png",
    "wordcloud_png",
    "wordcloud_positive_png",
    "wordcloud_neutral_png",
    "wordcloud_negative_png",
    "top_kata_png",
    "top_kata_csv",
    "top_topic_png",
    "top_topic_csv",
)

BLOCK_A_OUTPUT_DESCRIPTIONS = {
    "sna_csv": "Edge list SNA gabungan IndiBiz",
    "sentiment_csv": "Hasil prediksi sentimen IndoBERT IndiBiz",
    "network_graph_png": "Visualisasi jaringan SNA IndiBiz",
    "sentiment_chart_png": "Grafik distribusi sentimen IndiBiz",
    "wordcloud_png": "WordCloud gabungan tiga sentimen",
    "wordcloud_positive_png": "WordCloud sentimen positif",
    "wordcloud_neutral_png": "WordCloud sentimen netral",
    "wordcloud_negative_png": "WordCloud sentimen negatif",
    "top_kata_png": "Grafik Top 15 kata per sentimen",
    "top_kata_csv": "Tabel frekuensi Top 15 kata",
    "top_topic_png": "Visualisasi topik dominan",
    "top_topic_csv": "Tabel hasil topik dominan",
}


def get_indibiz_block_a_status(data_dir: str | Path | None = None) -> list[dict[str, object]]:
    """Periksa keberadaan dan validitas dasar 12 file output Blok A.

    Pemeriksaan PNG memakai signature file, sedangkan CSV dianggap valid bila
    file tidak kosong dan memiliki baris header. Fungsi tidak mengubah file.
    """
    try:
        root = Path(data_dir) if data_dir is not None else Path(__file__).resolve().parent.parent / "data"
        rows: list[dict[str, object]] = []
        for key in BLOCK_A_OUTPUT_ORDER:
            filename = OUTPUT_FILES[key]
            path = root / filename
            exists = path.is_file()
            size_bytes = int(path.stat().st_size) if exists else 0
            valid = False
            note = "File belum ditemukan"

            if exists and size_bytes > 0:
                if path.suffix.lower() == ".png":
                    valid = path.read_bytes()[:8] == b"\x89PNG\r\n\x1a\n"
                    note = "PNG valid" if valid else "Signature PNG tidak valid"
                elif path.suffix.lower() == ".csv":
                    with path.open("r", encoding="utf-8-sig", errors="replace") as handle:
                        header = handle.readline().strip()
                    valid = bool(header and "," in header)
                    note = "CSV memiliki header" if valid else "Header CSV belum valid"
                else:
                    valid = True
                    note = "File ditemukan"

            rows.append(
                {
                    "key": key,
                    "filename": filename,
                    "description": BLOCK_A_OUTPUT_DESCRIPTIONS.get(key, "Output IndiBiz"),
                    "exists": exists,
                    "valid": valid,
                    "size_bytes": size_bytes,
                    "note": note,
                    "path": str(path),
                }
            )
        return rows
    except Exception as error:
        st.error(f"Gagal memeriksa output Blok A IndiBiz: {error}")
        return []


def is_indibiz_block_a_complete(data_dir: str | Path | None = None) -> bool:
    """Kembalikan True bila seluruh 12 output Blok A ditemukan dan valid."""
    try:
        status = get_indibiz_block_a_status(data_dir=data_dir)
        return len(status) == len(BLOCK_A_OUTPUT_ORDER) and all(
            bool(item.get("valid")) for item in status
        )
    except Exception as error:
        st.error(f"Gagal menyimpulkan status Blok A IndiBiz: {error}")
        return False
