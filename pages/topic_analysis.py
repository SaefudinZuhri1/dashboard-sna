# pages/topic_analysis.py
"""Halaman Analisis Topik — WordCloud, kata dominan, topik, dan heatmap."""

from __future__ import annotations

from collections import Counter
from html import escape
from io import BytesIO
from pathlib import Path
import re
from typing import Any

import matplotlib.pyplot as plt
import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from PIL import Image
from wordcloud import WordCloud

from utils.audit_logger import log_activity
from utils.data_loader import (
    get_data_source_label,
    get_sentiment_file_signature,
    load_topic_data,
)
from utils.loading_screen import mulai_loading_aksi, selesaikan_loading_aksi
from utils.dummy_data import get_demo_sentiment
from utils.indibiz_topic_pipeline import (
    MIN_DOCS as INDIBIZ_LDA_MIN_DOCS,
    N_TOPICS as INDIBIZ_LDA_N_TOPICS,
    N_WORDS as INDIBIZ_LDA_N_WORDS,
    build_indibiz_topic_payload,
    build_indibiz_stable_filtered_payload,
)
from utils.preprocessor import NORMALIZATION_MAP, STOPWORDS_ID
from utils.topic_data_service import (
    load_enriched_topic_data as _load_shared_enriched_topic_data,
)
from utils.topic_classifier import (
    SENTIMENT_LABELS_ID,
    apply_topics,
    build_topic_platform_matrix,
    get_topic_keywords,
    summarize_topics,
)

LAYANAN_OPTIONS = ["IndiHome", "IndiBiz", "Telkomsel"]
PLATFORM_LABELS = {
    "twitter": "Twitter/X",
    "instagram": "Instagram",
    "tiktok": "TikTok",
}
SENTIMENT_OPTIONS = {
    "Semua": "all",
    "Positif": "positive",
    "Netral": "neutral",
    "Negatif": "negative",
}
SENTIMENT_ORDER = ["positive", "neutral", "negative"]
SENTIMENT_COLORS = {
    "positive": "#4CAF50",
    "neutral": "#FF9800",
    "negative": "#F44336",
}
SENTIMENT_ICONS = {
    "positive": "↗",
    "neutral": "●",
    "negative": "↘",
}
WORDCLOUD_STYLE = {
    "positive": {"colormap": "Greens", "background": "#F1F8E9"},
    "neutral": {"colormap": "Blues", "background": "#E3F2FD"},
    "negative": {"colormap": "Reds", "background": "#FFF3E0"},
}
BRAND_WORDS = {
    "indihome",
    "indibiz",
    "telkomsel",
    "telkom",
    "myindihome",
    "mytelkomsel",
}

WORDCLOUD_EXPORT_WIDTH = 1400
WORDCLOUD_EXPORT_HEIGHT = 875
WORDCLOUD_EXPORT_SCALE = 2
WORDCLOUD_EXPORT_DPI_EMPTY = 300

TOPIC_ACTION_LOADING_KEY = "_topic_v8_action_loading_label"

PROJECT_ROOT = Path(__file__).resolve().parents[1]
INDIBIZ_DATA_DIR = PROJECT_ROOT / "data"
INDIBIZ_WORDCLOUD_FILES = {
    "positive": INDIBIZ_DATA_DIR / "indibiz_output_wordcloud_positive.png",
    "neutral": INDIBIZ_DATA_DIR / "indibiz_output_wordcloud_neutral.png",
    "negative": INDIBIZ_DATA_DIR / "indibiz_output_wordcloud_negative.png",
}
INDIBIZ_OUTPUT_FILES = {
    "top_kata": INDIBIZ_DATA_DIR / "indibiz_output_top_kata.csv",
    "top_topic": INDIBIZ_DATA_DIR / "indibiz_output_top_topic.csv",
}
INDIBIZ_SENTIMENT_COLORS = {
    "positive": "#4CAF50",
    "neutral": "#42A5F5",
    "negative": "#F44336",
}
INDIBIZ_SENTIMENT_LABELS = {
    "positive": "Positif",
    "neutral": "Netral",
    "negative": "Negatif",
}
INDIBIZ_SENTIMENT_NORMALIZATION = {
    "positive": "positive",
    "positif": "positive",
    "neutral": "neutral",
    "netral": "neutral",
    "negative": "negative",
    "negatif": "negative",
}


def _indibiz_file_signature(path: Path) -> str:
    """Buat signature file agar cache otomatis diperbarui saat output diganti."""
    try:
        if not path.is_file():
            return "missing"
        stat = path.stat()
        return f"{path.name}:{stat.st_size}:{stat.st_mtime_ns}"
    except Exception:
        return "unreadable"


def _topic_data_source_label(layanan: str) -> str:
    """Tentukan label sumber khusus halaman Analisis Topik."""
    try:
        if bool(st.session_state.get("demo_mode", False)):
            return "🎯 Data Sample Demo"
        if layanan == "IndiBiz":
            wordcloud_ready = sum(
                path.is_file() for path in INDIBIZ_WORDCLOUD_FILES.values()
            )
            csv_ready = sum(path.is_file() for path in INDIBIZ_OUTPUT_FILES.values())
            sentiment_signature = get_sentiment_file_signature("IndiBiz")
            sentiment_ready = not sentiment_signature.endswith(":missing")

            # Dua CSV turunan dapat dibangun ulang dari output sentimen IndiBiz.
            # Karena itu, file CSV yang hilang tidak lagi membuat sumber data
            # dianggap tidak tersedia selama data sentimennya masih aktif.
            derived_ready = 2 if sentiment_ready else csv_ready
            tersedia = wordcloud_ready + derived_ready
            total_output = len(INDIBIZ_WORDCLOUD_FILES) + len(INDIBIZ_OUTPUT_FILES)
            if tersedia == total_output:
                return "📁 Data Real"
            if tersedia > 0:
                return "⚠️ Output Belum Lengkap"
            return "🔧 Data Dummy"
        return get_data_source_label(layanan)
    except Exception as exc:
        st.error(f"Status sumber data Analisis Topik belum dapat diperiksa: {exc}")
        return "ℹ️ Output Belum Tersedia"


def _change_table_page_with_loading(
    page_key: str,
    target_page: int,
    loading_label: str,
) -> None:
    """Ubah halaman tabel dan aktifkan overlay loading pada rerun berikutnya."""
    try:
        st.session_state[page_key] = max(1, int(target_page))
        st.session_state[TOPIC_ACTION_LOADING_KEY] = str(loading_label)
    except Exception as exc:
        st.error(f"Halaman tabel belum dapat diubah: {exc}")


def _show_word_detail_loading(widget_key: str) -> None:
    """Aktifkan halaman loading saat pengguna memilih detail kata."""
    try:
        selected_word = str(st.session_state.get(widget_key, "")).strip()
        if selected_word:
            label = f'Menyiapkan detail kata "{selected_word}"...'
        else:
            label = "Menyiapkan detail kata terpilih..."
        st.session_state[TOPIC_ACTION_LOADING_KEY] = label
    except Exception as exc:
        st.error(f"Detail kata belum dapat dimuat: {exc}")


def _show_filter_loading() -> None:
    """Aktifkan overlay loading saat tombol Terapkan Filter ditekan."""
    try:
        layanan = str(
            st.session_state.get(
                "topic_v8_draft_service",
                st.session_state.get("topic_v8_applied_service", "layanan terpilih"),
            )
        ).strip()
        layanan = layanan or "layanan terpilih"
        st.session_state[TOPIC_ACTION_LOADING_KEY] = (
            f"Menerapkan filter Analisis Topik untuk {layanan}..."
        )
    except Exception as exc:
        st.error(f"Filter belum dapat diterapkan: {exc}")


def _topic_is_dark_mode() -> bool:
    """Baca tema aktif tanpa mengubah state global dashboard."""
    try:
        return bool(st.session_state.get("dark_mode", False))
    except Exception as exc:
        st.error(f"Status tema Analisis Topik belum dapat dibaca: {exc}")
        return False


def _topic_plotly_tokens() -> dict[str, str]:
    """Siapkan token warna Plotly khusus halaman Analisis Topik."""
    try:
        if _topic_is_dark_mode():
            return {
                "template": "plotly_dark",
                "text": "#EDEDED",
                "muted": "#AAAAAA",
                "grid": "rgba(255,255,255,0.08)",
                "axis": "#3A3A3A",
                "hover_bg": "#171717",
                "hover_border": "#343434",
                "legend_bg": "rgba(23,23,23,0.92)",
                "menu_bg": "#17191F",
                "menu_border": "#3A3D45",
                "menu_text": "#EDEDED",
            }
        return {
            "template": "plotly_white",
            "text": "#172033",
            "muted": "#64748B",
            "grid": "rgba(100,116,139,0.16)",
            "axis": "#CBD5E1",
            "hover_bg": "#FFFFFF",
            "hover_border": "#E2E8F0",
            "legend_bg": "rgba(255,255,255,0.94)",
            "menu_bg": "#FFFFFF",
            "menu_border": "#D6DEE9",
            "menu_text": "#334155",
        }
    except Exception as exc:
        st.error(f"Token warna Analisis Topik belum dapat disiapkan: {exc}")
        return {
            "template": "plotly_white",
            "text": "#172033",
            "muted": "#64748B",
            "grid": "rgba(100,116,139,0.16)",
            "axis": "#CBD5E1",
            "hover_bg": "#FFFFFF",
            "hover_border": "#E2E8F0",
            "legend_bg": "rgba(255,255,255,0.94)",
            "menu_bg": "#FFFFFF",
            "menu_border": "#D6DEE9",
            "menu_text": "#334155",
        }


def _apply_topic_plotly_theme(figure: go.Figure | None) -> go.Figure | None:
    """Sesuaikan chart dengan tema aktif tanpa mengubah data atau struktur chart."""
    try:
        if figure is None:
            return None

        tokens = _topic_plotly_tokens()
        dark_mode = _topic_is_dark_mode()
        figure.update_layout(
            template=tokens["template"],
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
            font={"family": "Inter", "color": tokens["text"]},
            hoverlabel={
                "bgcolor": tokens["hover_bg"],
                "bordercolor": tokens["hover_border"],
                "font": {"family": "Inter", "color": tokens["text"]},
            },
            legend={
                "bgcolor": tokens["legend_bg"],
                "bordercolor": tokens["hover_border"],
                "font": {"family": "Inter", "color": tokens["text"]},
            },
        )
        figure.update_xaxes(
            color=tokens["muted"],
            gridcolor=tokens["grid"],
            linecolor=tokens["axis"],
            tickfont={"family": "Inter", "color": tokens["muted"]},
            title_font={"family": "Inter", "color": tokens["muted"]},
        )
        figure.update_yaxes(
            color=tokens["muted"],
            gridcolor=tokens["grid"],
            linecolor=tokens["axis"],
            tickfont={"family": "Inter", "color": tokens["muted"]},
            title_font={"family": "Inter", "color": tokens["muted"]},
        )

        for menu in list(figure.layout.updatemenus or []):
            menu.bgcolor = tokens["menu_bg"]
            menu.bordercolor = tokens["menu_border"]
            menu.font = {"family": "Inter", "color": tokens["menu_text"], "size": 11}

        for annotation in list(figure.layout.annotations or []):
            annotation.font = {
                "family": "Inter",
                "color": tokens["muted"],
                "size": getattr(annotation.font, "size", None) or 11,
            }

        for trace in figure.data:
            if str(getattr(trace, "type", "")).lower() != "heatmap":
                continue

            if not dark_mode:
                trace.colorscale = [
                    [0.00, "#FFF8F8"],
                    [0.08, "#FDECEC"],
                    [0.45, "#F5A3A0"],
                    [1.00, "#EF3B36"],
                ]
                if getattr(trace, "textfont", None) is not None:
                    trace.textfont.color = "#172033"

            if getattr(trace, "colorbar", None) is not None:
                trace.colorbar.tickfont = {
                    "family": "Inter",
                    "color": tokens["muted"],
                    "size": 11,
                }
                trace.colorbar.outlinecolor = tokens["axis"]
                if getattr(trace.colorbar, "title", None) is not None:
                    trace.colorbar.title.font = {
                        "family": "Inter",
                        "color": tokens["muted"],
                        "size": 11,
                    }

        return figure
    except Exception as exc:
        st.error(f"Tema chart Analisis Topik belum dapat diterapkan: {exc}")
        return figure


def _inject_topic_css() -> None:
    """Sisipkan CSS yang mengikuti halaman Beranda, Dataset, dan Sentimen."""
    try:
        st.markdown(
            """
            <style>
                @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=Plus+Jakarta+Sans:wght@500;600;700;800&display=swap');

                div[data-testid="stAppViewContainer"] { background: #0D0D0D; }
                div[data-testid="stAppViewContainer"] .main .block-container {
                    color: #FFFFFF;
                    padding-top: 1.25rem;
                    padding-bottom: 2.5rem;
                }

                .topic-v8-page,
                .topic-v8-page * { box-sizing: border-box; font-family: 'Inter', sans-serif; }

                .topic-v8-hero {
                    background:
                        radial-gradient(circle at 92% 8%, rgba(255,255,255,0.16), transparent 30%),
                        linear-gradient(135deg, #B71C1C 0%, #E53935 56%, #F05A56 100%);
                    border: 1px solid rgba(255,255,255,0.12);
                    border-radius: 12px;
                    box-shadow: 0 14px 34px rgba(183,28,28,0.22);
                    margin-bottom: 1.15rem;
                    overflow: hidden;
                    padding: 1.8rem 2rem;
                    position: relative;
                }

                .topic-v8-hero::after {
                    background: radial-gradient(circle, rgba(255,255,255,0.16), transparent 68%);
                    content: '';
                    height: 250px;
                    pointer-events: none;
                    position: absolute;
                    right: -80px;
                    top: -120px;
                    width: 250px;
                }

                .topic-v8-hero h1 {
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

                .topic-v8-hero p {
                    color: rgba(255,255,255,0.92) !important;
                    font-size: 0.96rem;
                    margin: 0.65rem 0 0.95rem;
                    max-width: 900px;
                    position: relative;
                    z-index: 1;
                }

                .topic-v8-badges {
                    display: flex;
                    flex-wrap: wrap;
                    gap: 0.45rem;
                    position: relative;
                    z-index: 1;
                }

                .topic-v8-badge {
                    backdrop-filter: blur(8px);
                    background: rgba(100,20,20,0.30);
                    border: 1px solid rgba(255,255,255,0.22);
                    border-radius: 999px;
                    color: #FFFFFF;
                    display: inline-flex;
                    font-size: 0.75rem /* FIX: minimum 12px agar terbaca di tablet */;
                    font-weight: 700;
                    padding: 0.42rem 0.68rem;
                }

                .topic-v8-card {
                    background: #1A1A1A;
                    border: 1px solid #2A2A2A;
                    border-radius: 12px;
                    box-shadow: 0 10px 28px rgba(0,0,0,0.18);
                }

                .topic-v8-control-marker,
                .topic-v8-section-marker {
                    display: none;
                }

                div[data-testid="stMarkdownContainer"]:has(.topic-v8-control-marker),
                div[data-testid="stMarkdownContainer"]:has(.topic-v8-section-marker) {
                    display: none;
                }

                div[data-testid="stVerticalBlockBorderWrapper"]:has(.topic-v8-control-marker),
                div[data-testid="stVerticalBlockBorderWrapper"]:has(.topic-v8-section-marker) {
                    background: #1A1A1A !important;
                    border: 1px solid #2A2A2A !important;
                    border-radius: 12px !important;
                    box-shadow: 0 10px 28px rgba(0,0,0,0.18);
                    padding: 1rem !important;
                }

                div[data-testid="stVerticalBlockBorderWrapper"]:has(.topic-v8-control-marker) {
                    margin-bottom: 1rem;
                }

                div[data-testid="stVerticalBlockBorderWrapper"]:has(.topic-v8-section-marker) {
                    margin: 1.2rem 0 0.75rem;
                }

                .topic-v8-section-head {
                    align-items: flex-start;
                    display: flex;
                    gap: 0.75rem;
                    justify-content: space-between;
                    margin-bottom: 0.75rem;
                }

                .topic-v8-section-title {
                    color: #FFFFFF !important;
                    font-family: 'Plus Jakarta Sans', 'Inter', sans-serif;
                    font-size: 1.05rem;
                    font-weight: 750;
                    margin: 0;
                }

                .topic-v8-section-subtitle {
                    color: #AAAAAA !important;
                    font-size: 0.78rem;
                    line-height: 1.45;
                    margin: 0.2rem 0 0;
                }

                .topic-v8-stat-row {
                    display: grid;
                    gap: 0.75rem;
                    grid-template-columns: repeat(4, minmax(0, 1fr));
                    margin: 0 0 1rem;
                }

                .topic-v8-stat {
                    background: #1A1A1A;
                    border: 1px solid #2A2A2A;
                    border-left: 3px solid #E53935;
                    border-radius: 12px;
                    min-height: 92px;
                    padding: 0.9rem 1rem;
                    transition: border-color .18s ease, box-shadow .18s ease, transform .18s ease;
                }

                .topic-v8-stat:hover,
                .topic-v8-card:hover {
                    border-color: #E53935;
                    box-shadow: 0 0 0 1px rgba(229,57,53,.12), 0 12px 34px rgba(0,0,0,.28);
                    transform: translateY(-1px);
                }

                .topic-v8-stat-label { color: #AAAAAA; font-size: 0.75rem /* FIX: minimum 12px agar terbaca di tablet */; font-weight: 650; }
                .topic-v8-stat-value {
                    color: #E53935;
                    font-family: 'Plus Jakarta Sans', 'Inter', sans-serif;
                    font-size: 1.7rem;
                    font-weight: 800;
                    line-height: 1.2;
                    margin-top: 0.22rem;
                }

                .topic-v8-topic-card {
                    background: #1A1A1A;
                    border: 1px solid #2A2A2A;
                    border-radius: 12px;
                    margin-bottom: 0.7rem;
                    overflow: hidden;
                    padding: 1rem 1.05rem;
                    position: relative;
                }

                .topic-v8-topic-card::before {
                    background: #E53935;
                    bottom: 0;
                    content: '';
                    left: 0;
                    position: absolute;
                    top: 0;
                    width: 3px;
                }

                .topic-v8-topic-head {
                    align-items: flex-start;
                    display: flex;
                    gap: 0.65rem;
                    justify-content: space-between;
                }

                .topic-v8-topic-name {
                    color: #FFFFFF;
                    font-family: 'Plus Jakarta Sans', 'Inter', sans-serif;
                    font-size: 0.95rem;
                    font-weight: 750;
                    line-height: 1.35;
                }

                .topic-v8-topic-meta { color: #AAAAAA; font-size: 0.75rem /* FIX: minimum 12px agar terbaca di tablet */; margin-top: 0.25rem; }
                .topic-v8-topic-example {
                    background: #111111;
                    border: 1px solid #292929;
                    border-radius: 9px;
                    color: #D4D4D4;
                    font-size: 0.78rem;
                    line-height: 1.5;
                    margin-top: 0.72rem;
                    padding: 0.72rem 0.8rem;
                }

                .topic-v8-chip {
                    border-radius: 999px;
                    color: #FFFFFF;
                    display: inline-flex;
                    font-size: 0.75rem /* FIX: minimum 12px agar terbaca di tablet */;
                    font-weight: 750;
                    padding: 0.3rem 0.55rem;
                    white-space: nowrap;
                }
                .topic-v8-chip-positive { background: rgba(76,175,80,.22); border: 1px solid rgba(76,175,80,.45); }
                .topic-v8-chip-neutral { background: rgba(255,152,0,.20); border: 1px solid rgba(255,152,0,.45); }
                .topic-v8-chip-negative { background: rgba(244,67,54,.20); border: 1px solid rgba(244,67,54,.45); }

                .topic-v8-topic-overview {
                    background: #151515;
                    border: 1px solid #2A2A2A;
                    border-radius: 10px;
                    margin-bottom: 0.85rem;
                    padding: 0.85rem 0.95rem;
                }

                .topic-v8-topic-overview-head {
                    align-items: flex-start;
                    display: flex;
                    gap: 0.7rem;
                    justify-content: space-between;
                }

                .topic-v8-topic-overview-title {
                    color: #FFFFFF;
                    font-family: 'Plus Jakarta Sans', 'Inter', sans-serif;
                    font-size: 0.94rem;
                    font-weight: 750;
                    line-height: 1.35;
                }

                .topic-v8-topic-overview-meta {
                    color: #AAAAAA;
                    font-size: 0.75rem;
                    line-height: 1.5;
                    margin-top: 0.22rem;
                }

                .topic-v8-sentiment-grid {
                    display: grid;
                    gap: 0.55rem;
                    grid-template-columns: repeat(3, minmax(0, 1fr));
                    margin-top: 0.8rem;
                }

                .topic-v8-sentiment-stat {
                    background: #101010;
                    border: 1px solid #292929;
                    border-radius: 9px;
                    isolation: isolate;
                    min-height: 64px;
                    overflow: hidden;
                    padding: 0.65rem 0.72rem;
                    position: relative;
                    transform: translateY(0) scale(1);
                    transition:
                        transform .24s cubic-bezier(.2,.75,.25,1),
                        border-color .24s ease,
                        background .24s ease,
                        box-shadow .24s ease;
                    will-change: transform;
                }

                .topic-v8-sentiment-stat::before {
                    background: linear-gradient(
                        110deg,
                        transparent 0%,
                        rgba(255,255,255,0.02) 35%,
                        rgba(255,255,255,0.14) 50%,
                        rgba(255,255,255,0.02) 65%,
                        transparent 100%
                    );
                    content: '';
                    inset: 0;
                    pointer-events: none;
                    position: absolute;
                    transform: translateX(-140%);
                    transition: transform .55s cubic-bezier(.2,.75,.25,1);
                    z-index: -1;
                }

                .topic-v8-sentiment-stat::after {
                    border-radius: 999px;
                    content: '';
                    height: 76px;
                    opacity: 0;
                    pointer-events: none;
                    position: absolute;
                    right: -28px;
                    top: -38px;
                    transform: scale(.72);
                    transition: opacity .24s ease, transform .24s ease;
                    width: 76px;
                    z-index: -1;
                }

                .topic-v8-sentiment-stat:hover {
                    transform: translateY(-4px) scale(1.015);
                }

                .topic-v8-sentiment-stat:hover::before {
                    transform: translateX(140%);
                }

                .topic-v8-sentiment-stat:hover::after {
                    opacity: 1;
                    transform: scale(1);
                }

                .topic-v8-sentiment-stat-negative:hover {
                    background: linear-gradient(145deg, #151010 0%, #1B1111 100%);
                    border-color: rgba(244,67,54,.78);
                    box-shadow: 0 12px 28px rgba(244,67,54,.16), 0 0 0 1px rgba(244,67,54,.08);
                }

                .topic-v8-sentiment-stat-negative::after {
                    background: radial-gradient(circle, rgba(244,67,54,.24) 0%, transparent 70%);
                }

                .topic-v8-sentiment-stat-neutral:hover {
                    background: linear-gradient(145deg, #15130E 0%, #1B160D 100%);
                    border-color: rgba(255,152,0,.78);
                    box-shadow: 0 12px 28px rgba(255,152,0,.16), 0 0 0 1px rgba(255,152,0,.08);
                }

                .topic-v8-sentiment-stat-neutral::after {
                    background: radial-gradient(circle, rgba(255,152,0,.24) 0%, transparent 70%);
                }

                .topic-v8-sentiment-stat-positive:hover {
                    background: linear-gradient(145deg, #101510 0%, #111B12 100%);
                    border-color: rgba(76,175,80,.78);
                    box-shadow: 0 12px 28px rgba(76,175,80,.16), 0 0 0 1px rgba(76,175,80,.08);
                }

                .topic-v8-sentiment-stat-positive::after {
                    background: radial-gradient(circle, rgba(76,175,80,.24) 0%, transparent 70%);
                }

                .topic-v8-sentiment-stat-label {
                    align-items: center;
                    color: #BDBDBD;
                    display: flex;
                    font-size: 0.75rem /* FIX: minimum 12px agar terbaca di tablet */;
                    font-weight: 700;
                    gap: 0.35rem;
                    position: relative;
                    transition: color .2s ease, transform .2s ease;
                    z-index: 1;
                }

                .topic-v8-dot {
                    border-radius: 999px;
                    display: inline-block;
                    height: 8px;
                    transition: box-shadow .22s ease, transform .22s ease;
                    width: 8px;
                }

                .topic-v8-sentiment-stat:hover .topic-v8-dot {
                    transform: scale(1.22);
                }

                .topic-v8-sentiment-stat-negative:hover .topic-v8-dot {
                    box-shadow: 0 0 0 4px rgba(244,67,54,.10), 0 0 12px rgba(244,67,54,.65);
                }

                .topic-v8-sentiment-stat-neutral:hover .topic-v8-dot {
                    box-shadow: 0 0 0 4px rgba(255,152,0,.10), 0 0 12px rgba(255,152,0,.65);
                }

                .topic-v8-sentiment-stat-positive:hover .topic-v8-dot {
                    box-shadow: 0 0 0 4px rgba(76,175,80,.10), 0 0 12px rgba(76,175,80,.65);
                }

                .topic-v8-sentiment-stat:hover .topic-v8-sentiment-stat-label {
                    color: #FFFFFF;
                    transform: translateX(2px);
                }

                .topic-v8-sentiment-stat-value {
                    color: #FFFFFF;
                    font-family: 'Plus Jakarta Sans', 'Inter', sans-serif;
                    font-size: 1rem;
                    font-weight: 800;
                    margin-top: 0.25rem;
                    position: relative;
                    transition: transform .22s ease, text-shadow .22s ease;
                    z-index: 1;
                }

                .topic-v8-sentiment-stat:hover .topic-v8-sentiment-stat-value {
                    text-shadow: 0 4px 18px rgba(255,255,255,.10);
                    transform: translateY(-1px) scale(1.025);
                    transform-origin: left center;
                }

                .topic-v8-sentiment-stat-sub {
                    color: #777777;
                    font-size: 0.75rem /* FIX: minimum 12px agar terbaca di tablet */;
                    margin-top: 0.08rem;
                    position: relative;
                    transition: color .2s ease;
                    z-index: 1;
                }

                .topic-v8-sentiment-stat:hover .topic-v8-sentiment-stat-sub {
                    color: #AFAFAF;
                }



                /* Ringkasan dan sumber data heatmap */
                .topic-v8-heatmap-insights {
                    display: grid;
                    gap: 0.7rem;
                    grid-template-columns: repeat(3, minmax(0, 1fr));
                    margin: 0.35rem 0 0.9rem;
                }

                .topic-v8-heatmap-insight {
                    background: linear-gradient(145deg, #171717 0%, #121212 100%);
                    border: 1px solid #2D2D2D;
                    border-radius: 11px;
                    min-height: 86px;
                    overflow: hidden;
                    padding: 0.85rem 0.95rem;
                    position: relative;
                    transition: border-color .2s ease, box-shadow .2s ease, transform .2s ease;
                }

                .topic-v8-heatmap-insight::before {
                    background: linear-gradient(180deg, #FF5A55, #B71C1C);
                    bottom: 0;
                    content: '';
                    left: 0;
                    position: absolute;
                    top: 0;
                    width: 3px;
                }

                .topic-v8-heatmap-insight::after {
                    background: radial-gradient(circle, rgba(229,57,53,.15), transparent 66%);
                    content: '';
                    height: 100px;
                    pointer-events: none;
                    position: absolute;
                    right: -38px;
                    top: -42px;
                    width: 100px;
                }

                .topic-v8-heatmap-insight:hover {
                    border-color: rgba(229,57,53,.72);
                    box-shadow: 0 12px 30px rgba(0,0,0,.28), 0 0 22px rgba(229,57,53,.08);
                    transform: translateY(-3px);
                }

                .topic-v8-heatmap-insight-label {
                    color: #8F8F8F;
                    font-size: 0.75rem /* FIX: minimum 12px agar terbaca di tablet */;
                    font-weight: 700;
                    letter-spacing: .055em;
                    position: relative;
                    text-transform: uppercase;
                    z-index: 1;
                }

                .topic-v8-heatmap-insight-value {
                    color: #FFFFFF;
                    font-family: 'Plus Jakarta Sans', 'Inter', sans-serif;
                    font-size: 1rem;
                    font-weight: 800;
                    line-height: 1.3;
                    margin-top: 0.28rem;
                    overflow-wrap: anywhere;
                    position: relative;
                    z-index: 1;
                }

                .topic-v8-heatmap-insight-note {
                    color: #777777;
                    font-size: 0.75rem /* FIX: minimum 12px agar terbaca di tablet */;
                    margin-top: 0.18rem;
                    position: relative;
                    z-index: 1;
                }

                .topic-v8-heatmap-source {
                    align-items: flex-start;
                    background: rgba(229,57,53,.055);
                    border: 1px solid rgba(229,57,53,.18);
                    border-radius: 10px;
                    color: #AFAFAF;
                    display: flex;
                    font-size: 0.75rem /* FIX: minimum 12px agar terbaca di tablet */;
                    gap: 0.55rem;
                    line-height: 1.55;
                    margin: 0.8rem 0 1.15rem;
                    padding: 0.78rem 0.88rem;
                }

                .topic-v8-heatmap-source strong { color: #F0F0F0; }

                @media (max-width: 760px) {
                    .topic-v8-heatmap-insights { grid-template-columns: 1fr; }
                }

                @media (prefers-reduced-motion: reduce) {
                    .topic-v8-sentiment-stat,
                    .topic-v8-sentiment-stat::before,
                    .topic-v8-sentiment-stat::after,
                    .topic-v8-sentiment-stat-label,
                    .topic-v8-sentiment-stat-value,
                    .topic-v8-sentiment-stat-sub,
                    .topic-v8-dot {
                        transition: none !important;
                    }

                    .topic-v8-sentiment-stat:hover {
                        transform: none;
                    }
                }

                .topic-v8-comment-card {
                    background: #111111;
                    border: 1px solid #292929;
                    border-left: 3px solid #666666;
                    border-radius: 10px;
                    margin: 0.55rem 0;
                    padding: 0.8rem 0.9rem;
                    transition: border-color .18s ease, transform .18s ease, box-shadow .18s ease;
                }

                .topic-v8-comment-card:hover {
                    border-color: #444444;
                    box-shadow: 0 8px 22px rgba(0,0,0,.22);
                    transform: translateY(-1px);
                }

                .topic-v8-comment-card-positive { border-left-color: #4CAF50; }
                .topic-v8-comment-card-neutral { border-left-color: #FF9800; }
                .topic-v8-comment-card-negative { border-left-color: #F44336; }

                .topic-v8-comment-meta {
                    align-items: center;
                    color: #888888;
                    display: flex;
                    font-size: 0.75rem /* FIX: minimum 12px agar terbaca di tablet */;
                    font-weight: 650;
                    gap: 0.45rem;
                    margin-bottom: 0.45rem;
                    text-transform: uppercase;
                }

                .topic-v8-comment-text {
                    color: #E0E0E0;
                    font-size: 0.79rem;
                    line-height: 1.58;
                    overflow-wrap: anywhere;
                    white-space: pre-wrap;
                }

                div[data-testid="stExpander"] {
                    background: #1A1A1A !important;
                    border: 1px solid #2A2A2A !important;
                    border-radius: 12px !important;
                    margin-bottom: 0.75rem !important;
                    overflow: hidden;
                }

                div[data-testid="stExpander"]:hover {
                    border-color: #E53935 !important;
                    box-shadow: 0 10px 28px rgba(0,0,0,.22);
                }

                div[data-testid="stExpander"] summary {
                    background: #1A1A1A !important;
                    color: #FFFFFF !important;
                    font-family: 'Plus Jakarta Sans', 'Inter', sans-serif !important;
                    font-weight: 750 !important;
                    min-height: 58px;
                }

                div[data-testid="stExpander"] summary:hover {
                    color: #FF6B67 !important;
                }

                /* Segmented tabs komentar per sentimen */
                div[data-baseweb="tab-list"] {
                    align-items: center;
                    background: linear-gradient(180deg, #151515 0%, #101010 100%);
                    border: 1px solid #303030;
                    border-radius: 14px;
                    box-shadow: inset 0 1px 0 rgba(255,255,255,.025), 0 8px 24px rgba(0,0,0,.18);
                    display: flex;
                    gap: 0.55rem;
                    margin: 0.95rem 0 0.8rem;
                    padding: 0.45rem;
                    width: 100%;
                }

                div[data-baseweb="tab-list"] > div {
                    display: none !important;
                }

                button[data-baseweb="tab"] {
                    align-items: center !important;
                    background: #1B1B1B !important;
                    border: 1px solid #2E2E2E !important;
                    border-radius: 10px !important;
                    color: #BDBDBD !important;
                    display: flex !important;
                    flex: 1 1 0 !important;
                    font-size: 0.78rem !important;
                    font-weight: 750 !important;
                    justify-content: center !important;
                    letter-spacing: .01em !important;
                    min-height: 44px !important;
                    padding: 0.65rem 0.75rem !important;
                    position: relative !important;
                    text-align: center !important;
                    transition: transform .18s ease, border-color .18s ease, background .18s ease, box-shadow .18s ease, color .18s ease !important;
                    width: 100% !important;
                }

                button[data-baseweb="tab"]:hover {
                    color: #FFFFFF !important;
                    transform: translateY(-2px);
                }

                button[data-baseweb="tab"]:focus-visible {
                    outline: 2px solid rgba(255,255,255,.34) !important;
                    outline-offset: 2px !important;
                }

                button[data-baseweb="tab"]:nth-of-type(1) {
                    background: rgba(244,67,54,.055) !important;
                    border-color: rgba(244,67,54,.22) !important;
                }

                button[data-baseweb="tab"]:nth-of-type(1):hover {
                    background: rgba(244,67,54,.11) !important;
                    border-color: rgba(244,67,54,.52) !important;
                    box-shadow: 0 8px 22px rgba(244,67,54,.10);
                }

                button[data-baseweb="tab"]:nth-of-type(2) {
                    background: rgba(255,152,0,.045) !important;
                    border-color: rgba(255,152,0,.20) !important;
                }

                button[data-baseweb="tab"]:nth-of-type(2):hover {
                    background: rgba(255,152,0,.10) !important;
                    border-color: rgba(255,152,0,.50) !important;
                    box-shadow: 0 8px 22px rgba(255,152,0,.09);
                }

                button[data-baseweb="tab"]:nth-of-type(3) {
                    background: rgba(76,175,80,.045) !important;
                    border-color: rgba(76,175,80,.20) !important;
                }

                button[data-baseweb="tab"]:nth-of-type(3):hover {
                    background: rgba(76,175,80,.10) !important;
                    border-color: rgba(76,175,80,.50) !important;
                    box-shadow: 0 8px 22px rgba(76,175,80,.09);
                }

                button[data-baseweb="tab"]:nth-of-type(1)[aria-selected="true"] {
                    background: linear-gradient(135deg, rgba(244,67,54,.30), rgba(183,28,28,.18)) !important;
                    border-color: #F44336 !important;
                    box-shadow: 0 0 0 1px rgba(244,67,54,.12), 0 10px 26px rgba(244,67,54,.14) !important;
                    color: #FFFFFF !important;
                    transform: translateY(-1px);
                }

                button[data-baseweb="tab"]:nth-of-type(2)[aria-selected="true"] {
                    background: linear-gradient(135deg, rgba(255,152,0,.28), rgba(230,120,0,.16)) !important;
                    border-color: #FF9800 !important;
                    box-shadow: 0 0 0 1px rgba(255,152,0,.10), 0 10px 26px rgba(255,152,0,.12) !important;
                    color: #FFFFFF !important;
                    transform: translateY(-1px);
                }

                button[data-baseweb="tab"]:nth-of-type(3)[aria-selected="true"] {
                    background: linear-gradient(135deg, rgba(76,175,80,.28), rgba(46,125,50,.16)) !important;
                    border-color: #4CAF50 !important;
                    box-shadow: 0 0 0 1px rgba(76,175,80,.10), 0 10px 26px rgba(76,175,80,.12) !important;
                    color: #FFFFFF !important;
                    transform: translateY(-1px);
                }

                div[data-baseweb="tab-panel"] {
                    animation: topicV8TabReveal .24s ease-out;
                    padding-top: 0.2rem !important;
                }

                @keyframes topicV8TabReveal {
                    from { opacity: 0; transform: translateY(5px); }
                    to { opacity: 1; transform: translateY(0); }
                }

                @media (max-width: 760px) {
                    .topic-v8-sentiment-grid { grid-template-columns: 1fr; }
                    .topic-v8-topic-overview-head { flex-direction: column; }
                }

                div[data-testid="stSelectbox"] label,
                div[data-testid="stMultiSelect"] label,
                div[data-testid="stTextInput"] label,
                div[data-testid="stSlider"] label,
                div[data-testid="stToggle"] label {
                    color: #AAAAAA !important;
                    font-size: 0.78rem !important;
                    font-weight: 650 !important;
                }

                div[data-baseweb="select"] > div,
                div[data-testid="stTextInput"] input {
                    background: #242424 !important;
                    border: 1px solid #343434 !important;
                    border-radius: 10px !important;
                    color: #FFFFFF !important;
                    min-height: 42px;
                }

                div[data-baseweb="select"] > div:focus-within,
                div[data-testid="stTextInput"] input:focus {
                    border-color: #E53935 !important;
                    box-shadow: 0 0 0 3px rgba(229,57,53,.14) !important;
                }

                div[data-testid="stDownloadButton"] button {
                    background: #E53935 !important;
                    border: 1px solid #E53935 !important;
                    border-radius: 8px !important;
                    color: #FFFFFF !important;
                    font-weight: 650 !important;
                }


                /* Tombol mode Heatmap Plotly: state nonaktif, hover, dan aktif dibedakan jelas. */
                div[data-testid="stPlotlyChart"] g.updatemenu-button rect.updatemenu-item-rect {
                    fill: #17191F !important;
                    stroke: #3A3D45 !important;
                    stroke-width: 1px !important;
                    opacity: .96;
                    rx: 7px;
                    ry: 7px;
                    filter: none;
                    transition: fill .18s ease, stroke .18s ease, filter .18s ease, opacity .18s ease;
                }

                div[data-testid="stPlotlyChart"] g.updatemenu-button text.updatemenu-item-text {
                    fill: #BEBEBE !important;
                    font-weight: 650 !important;
                    transition: fill .18s ease;
                }

                /* State aktif: Plotly menyimpan #8F1D1D sebagai rgb(143, 29, 29) pada atribut style SVG. */
                div[data-testid="stPlotlyChart"] g.updatemenu-button rect.updatemenu-item-rect[style*="143, 29, 29"],
                div[data-testid="stPlotlyChart"] g.updatemenu-button rect.updatemenu-item-rect[style*="8F1D1D"],
                div[data-testid="stPlotlyChart"] g.updatemenu-button rect.updatemenu-item-rect[style*="8f1d1d"] {
                    fill: #8F1D1D !important;
                    stroke: #FF4B47 !important;
                    stroke-width: 1.25px !important;
                    opacity: 1;
                    filter: drop-shadow(0 4px 8px rgba(229,57,53,.26));
                }

                div[data-testid="stPlotlyChart"] g.updatemenu-button rect.updatemenu-item-rect[style*="143, 29, 29"] + text.updatemenu-item-text,
                div[data-testid="stPlotlyChart"] g.updatemenu-button rect.updatemenu-item-rect[style*="8F1D1D"] + text.updatemenu-item-text,
                div[data-testid="stPlotlyChart"] g.updatemenu-button rect.updatemenu-item-rect[style*="8f1d1d"] + text.updatemenu-item-text {
                    fill: #FFFFFF !important;
                    font-weight: 750 !important;
                }

                /* State hover untuk tombol nonaktif: lebih terang tanpa menyerupai state aktif. */
                div[data-testid="stPlotlyChart"] g.updatemenu-button:hover rect.updatemenu-item-rect {
                    fill: #2D2021 !important;
                    stroke: #E53935 !important;
                    opacity: 1;
                    filter: drop-shadow(0 3px 7px rgba(229,57,53,.18));
                }

                div[data-testid="stPlotlyChart"] g.updatemenu-button:hover text.updatemenu-item-text {
                    fill: #FFFFFF !important;
                }

                /* Hover pada tombol yang sudah aktif: merah sedikit lebih cerah. */
                div[data-testid="stPlotlyChart"] g.updatemenu-button:hover rect.updatemenu-item-rect[style*="143, 29, 29"],
                div[data-testid="stPlotlyChart"] g.updatemenu-button:hover rect.updatemenu-item-rect[style*="8F1D1D"],
                div[data-testid="stPlotlyChart"] g.updatemenu-button:hover rect.updatemenu-item-rect[style*="8f1d1d"] {
                    fill: #B71C1C !important;
                    stroke: #FF6B67 !important;
                    filter: drop-shadow(0 5px 10px rgba(229,57,53,.34));
                }

                .topic-v8-table-stats {
                    display: grid;
                    gap: 0.7rem;
                    grid-template-columns: repeat(4, minmax(0, 1fr));
                    margin: 0.85rem 0 1rem;
                }

                .topic-v8-table-stat {
                    background: linear-gradient(145deg, #181818, #121212);
                    border: 1px solid #2A2A2A;
                    border-radius: 11px;
                    min-height: 82px;
                    padding: 0.78rem 0.9rem;
                    position: relative;
                    transition: transform .18s ease, border-color .18s ease, box-shadow .18s ease;
                    overflow: hidden;
                }

                .topic-v8-table-stat::after {
                    background: linear-gradient(90deg, transparent, rgba(229,57,53,.22), transparent);
                    content: '';
                    height: 1px;
                    left: 0;
                    position: absolute;
                    right: 0;
                    top: 0;
                }

                .topic-v8-table-stat:hover {
                    border-color: rgba(229,57,53,.72);
                    box-shadow: 0 10px 24px rgba(0,0,0,.25), 0 0 0 1px rgba(229,57,53,.08);
                    transform: translateY(-2px);
                }

                .topic-v8-table-stat-label {
                    color: #8F8F8F;
                    font-size: 0.75rem /* FIX: minimum 12px agar terbaca di tablet */;
                    font-weight: 650;
                    letter-spacing: .02em;
                }

                .topic-v8-table-stat-value {
                    color: #FFFFFF;
                    font-family: 'Plus Jakarta Sans', 'Inter', sans-serif;
                    font-size: 1.12rem;
                    font-weight: 800;
                    line-height: 1.25;
                    margin-top: .24rem;
                    overflow: hidden;
                    text-overflow: ellipsis;
                    white-space: nowrap;
                }

                .topic-v8-table-meta {
                    align-items: center;
                    color: #8F8F8F;
                    display: flex;
                    font-size: 0.75rem /* FIX: minimum 12px agar terbaca di tablet */;
                    justify-content: space-between;
                    margin: .8rem 0 .55rem;
                    min-height: 1.5rem;
                }

                .topic-v8-table-meta strong { color: #E6E6E6; }

                .topic-v8-table-detail {
                    background: linear-gradient(135deg, rgba(229,57,53,.08), rgba(20,20,20,.95));
                    border: 1px solid rgba(229,57,53,.28);
                    border-left: 3px solid #E53935;
                    border-radius: 11px;
                    display: grid;
                    gap: .55rem 1rem;
                    grid-template-columns: minmax(140px, 1.4fr) repeat(3, minmax(110px, .7fr));
                    margin: .7rem 0 1rem;
                    padding: .9rem 1rem;
                }

                .topic-v8-table-detail-item span {
                    color: #858585;
                    display: block;
                    font-size: 0.75rem /* FIX: minimum 12px agar terbaca di tablet */;
                    font-weight: 650;
                    margin-bottom: .18rem;
                }

                .topic-v8-table-detail-item strong {
                    color: #FFFFFF;
                    display: block;
                    font-size: .88rem;
                    overflow-wrap: anywhere;
                }

                .topic-v8-table-sentiment {
                    border-radius: 999px;
                    display: inline-flex !important;
                    font-size: 0.75rem /* FIX: minimum 12px agar terbaca di tablet */ !important;
                    padding: .24rem .58rem;
                    width: fit-content;
                }

                div[data-testid="stDataFrame"] {
                    background: #111111;
                    border: 1px solid #303030;
                    border-radius: 12px;
                    box-shadow: 0 12px 28px rgba(0,0,0,.18);
                    overflow: hidden;
                    transition: border-color .18s ease, box-shadow .18s ease;
                }

                div[data-testid="stDataFrame"]:hover {
                    border-color: rgba(229,57,53,.55);
                    box-shadow: 0 14px 30px rgba(0,0,0,.24), 0 0 0 1px rgba(229,57,53,.07);
                }

                @media (max-width: 900px) {
                    .topic-v8-table-stats { grid-template-columns: repeat(2, minmax(0, 1fr)); }
                    .topic-v8-table-detail { grid-template-columns: repeat(2, minmax(0, 1fr)); }
                }

                @media (max-width: 620px) {
                    .topic-v8-table-stats { grid-template-columns: 1fr; }
                    .topic-v8-table-detail { grid-template-columns: 1fr; }
                    .topic-v8-table-meta { align-items: flex-start; flex-direction: column; gap: .25rem; }
                }

                @media (max-width: 900px) {
                    .topic-v8-stat-row { grid-template-columns: repeat(2, minmax(0, 1fr)); }
                }
                @media (max-width: 620px) {
                    .topic-v8-hero { padding: 1.35rem 1.15rem; }
                    .topic-v8-stat-row { grid-template-columns: 1fr; }
                    .topic-v8-topic-head { align-items: flex-start; flex-direction: column; }
                }
            </style>
            """,
            unsafe_allow_html=True,
        )

        if not _topic_is_dark_mode():
            st.markdown(
                """
                <style>
                    /* Light Mode Analisis Topik. Hanya override warna, tanpa mengubah layout. */
                    div[data-testid="stAppViewContainer"] {
                        background: #F6F8FB !important;
                    }

                    div[data-testid="stAppViewContainer"] .main .block-container {
                        color: #172033 !important;
                    }

                    .topic-v8-section-title,
                    .topic-v8-topic-name,
                    .topic-v8-topic-overview-title,
                    .topic-v8-sentiment-stat-value,
                    .topic-v8-heatmap-insight-value,
                    .topic-v8-table-stat-value,
                    .topic-v8-table-detail-item strong {
                        color: #172033 !important;
                        -webkit-text-fill-color: #172033 !important;
                    }

                    .topic-v8-section-subtitle,
                    .topic-v8-topic-meta,
                    .topic-v8-topic-overview-meta,
                    .topic-v8-stat-label,
                    .topic-v8-sentiment-stat-label,
                    .topic-v8-sentiment-stat-sub,
                    .topic-v8-comment-meta,
                    .topic-v8-heatmap-insight-label,
                    .topic-v8-heatmap-insight-note,
                    .topic-v8-table-stat-label,
                    .topic-v8-table-meta,
                    .topic-v8-table-detail-item span {
                        color: #64748B !important;
                        -webkit-text-fill-color: #64748B !important;
                    }

                    .topic-v8-table-meta strong {
                        color: #334155 !important;
                    }

                    .topic-v8-card,
                    .topic-v8-stat,
                    .topic-v8-topic-card,
                    .topic-v8-topic-overview,
                    .topic-v8-sentiment-stat,
                    .topic-v8-comment-card,
                    .topic-v8-heatmap-insight,
                    .topic-v8-table-stat,
                    .topic-v8-table-detail {
                        background: #FFFFFF !important;
                        border-color: #DCE3EC !important;
                        box-shadow: 0 10px 28px rgba(15,23,42,.07) !important;
                    }

                    div[data-testid="stVerticalBlockBorderWrapper"]:has(.topic-v8-control-marker),
                    div[data-testid="stVerticalBlockBorderWrapper"]:has(.topic-v8-section-marker) {
                        background: #FFFFFF !important;
                        border-color: #DCE3EC !important;
                        box-shadow: 0 10px 28px rgba(15,23,42,.06) !important;
                    }

                    .topic-v8-topic-example {
                        background: #F8FAFC !important;
                        border-color: #E2E8F0 !important;
                        color: #334155 !important;
                    }

                    .topic-v8-comment-text {
                        color: #334155 !important;
                        -webkit-text-fill-color: #334155 !important;
                    }

                    .topic-v8-sentiment-stat-negative:hover {
                        background: #FFF5F5 !important;
                    }

                    .topic-v8-sentiment-stat-neutral:hover {
                        background: #FFF9ED !important;
                    }

                    .topic-v8-sentiment-stat-positive:hover {
                        background: #F2FBF3 !important;
                    }

                    .topic-v8-sentiment-stat:hover .topic-v8-sentiment-stat-label,
                    .topic-v8-sentiment-stat:hover .topic-v8-sentiment-stat-sub {
                        color: #334155 !important;
                        -webkit-text-fill-color: #334155 !important;
                    }

                    .topic-v8-chip-positive {
                        background: #EAF7EC !important;
                        border-color: #B7DFBD !important;
                        color: #1B6A27 !important;
                    }

                    .topic-v8-chip-neutral {
                        background: #FFF4DE !important;
                        border-color: #FFD18A !important;
                        color: #8A5200 !important;
                    }

                    .topic-v8-chip-negative {
                        background: #FFE9E8 !important;
                        border-color: #FFC0BD !important;
                        color: #A6231F !important;
                    }

                    .topic-v8-heatmap-source {
                        background: #FFF7F7 !important;
                        border-color: #F6C9C7 !important;
                        color: #64748B !important;
                    }

                    .topic-v8-heatmap-source strong {
                        color: #334155 !important;
                    }

                    div[data-testid="stExpander"] {
                        background: #FFFFFF !important;
                        border-color: #DCE3EC !important;
                        box-shadow: 0 8px 24px rgba(15,23,42,.055) !important;
                    }

                    div[data-testid="stExpander"] summary {
                        background: #FFFFFF !important;
                        color: #172033 !important;
                        -webkit-text-fill-color: #172033 !important;
                    }

                    div[data-testid="stExpander"] summary svg {
                        fill: #475569 !important;
                        color: #475569 !important;
                    }

                    div[data-baseweb="tab-list"] {
                        background: #FFFFFF !important;
                        border-color: #DCE3EC !important;
                        box-shadow: 0 8px 22px rgba(15,23,42,.055) !important;
                    }

                    button[data-baseweb="tab"] {
                        background: #F8FAFC !important;
                        border-color: #DCE3EC !important;
                        color: #475569 !important;
                        -webkit-text-fill-color: #475569 !important;
                    }

                    button[data-baseweb="tab"]:hover {
                        color: #172033 !important;
                        -webkit-text-fill-color: #172033 !important;
                    }

                    button[data-baseweb="tab"]:nth-of-type(1)[aria-selected="true"] {
                        background: #FFEDEC !important;
                        border-color: #F44336 !important;
                        color: #9F211D !important;
                        -webkit-text-fill-color: #9F211D !important;
                    }

                    button[data-baseweb="tab"]:nth-of-type(2)[aria-selected="true"] {
                        background: #FFF4DF !important;
                        border-color: #FF9800 !important;
                        color: #855000 !important;
                        -webkit-text-fill-color: #855000 !important;
                    }

                    button[data-baseweb="tab"]:nth-of-type(3)[aria-selected="true"] {
                        background: #EAF7EC !important;
                        border-color: #4CAF50 !important;
                        color: #1E6728 !important;
                        -webkit-text-fill-color: #1E6728 !important;
                    }

                    div[data-testid="stSelectbox"] label,
                    div[data-testid="stMultiSelect"] label,
                    div[data-testid="stTextInput"] label,
                    div[data-testid="stSlider"] label,
                    div[data-testid="stToggle"] label {
                        color: #475569 !important;
                        -webkit-text-fill-color: #475569 !important;
                    }

                    div[data-baseweb="select"] > div,
                    div[data-testid="stTextInput"] input {
                        background: #FFFFFF !important;
                        border-color: #D6DEE9 !important;
                        color: #172033 !important;
                        -webkit-text-fill-color: #172033 !important;
                    }

                    div[data-baseweb="select"] svg {
                        fill: #475569 !important;
                        color: #475569 !important;
                    }

                    div[data-testid="stDataFrame"] {
                        background: #FFFFFF !important;
                        border-color: #DCE3EC !important;
                        box-shadow: 0 10px 26px rgba(15,23,42,.055) !important;
                    }

                    div[data-testid="stPlotlyChart"] {
                        background: #FFFFFF !important;
                        border-radius: 10px;
                    }

                    div[data-testid="stPlotlyChart"] .modebar {
                        background: rgba(255,255,255,.94) !important;
                    }

                    div[data-testid="stPlotlyChart"] .modebar-btn path {
                        fill: #475569 !important;
                    }

                    div[data-testid="stPlotlyChart"] .modebar-btn:hover path {
                        fill: #E53935 !important;
                    }

                    div[data-testid="stPlotlyChart"] g.updatemenu-button rect.updatemenu-item-rect {
                        fill: #FFFFFF !important;
                        stroke: #D6DEE9 !important;
                    }

                    div[data-testid="stPlotlyChart"] g.updatemenu-button text.updatemenu-item-text {
                        fill: #334155 !important;
                    }

                    div[data-testid="stPlotlyChart"] g.updatemenu-button:hover rect.updatemenu-item-rect {
                        fill: #FFF1F0 !important;
                        stroke: #E53935 !important;
                    }

                    div[data-testid="stPlotlyChart"] g.updatemenu-button:hover text.updatemenu-item-text {
                        fill: #B42318 !important;
                    }

                    .topic-v8-table-detail {
                        background: linear-gradient(135deg, #FFF7F7, #FFFFFF) !important;
                        border-color: #F3C8C6 !important;
                    }

                    .topic-v8-table-stat:hover,
                    .topic-v8-stat:hover,
                    .topic-v8-card:hover,
                    .topic-v8-topic-card:hover,
                    .topic-v8-comment-card:hover,
                    .topic-v8-heatmap-insight:hover {
                        box-shadow: 0 12px 28px rgba(15,23,42,.09) !important;
                    }
                </style>
                """,
                unsafe_allow_html=True,
            )
    except Exception as exc:
        st.error(f"Gaya halaman Analisis Topik belum dapat dimuat: {exc}")


def _format_number(value: int | float) -> str:
    """Format angka menggunakan pemisah ribuan Indonesia."""
    try:
        return f"{int(value):,}".replace(",", ".")
    except Exception:
        return "0"


def _normalize_platform(value: Any) -> str:
    """Normalisasi nama platform ke twitter, instagram, atau tiktok."""
    key = str(value or "").strip().lower().replace("'", "")
    if key in {"twitter", "x", "twitter/x"}:
        return "twitter"
    if "instagram" in key or key == "ig":
        return "instagram"
    if "tiktok" in key or key == "tik tok":
        return "tiktok"
    return key or "lainnya"


def _render_hero(data_source: str, layanan: str) -> None:
    """Render hero banner dengan judul yang mengikuti layanan aktif."""
    if "Real" in data_source:
        source_badge = "Data Real"
    elif "Belum Lengkap" in data_source:
        source_badge = "Output Belum Lengkap"
    elif "Belum Tersedia" in data_source:
        source_badge = "Output Belum Tersedia"
    else:
        source_badge = "Data Dummy"

    layanan_aman = escape(str(layanan or "IndiHome"))
    st.markdown(
        f"""
        <div class="topic-v8-page">
            <section class="topic-v8-hero">
                <h1>Analisis Topik {layanan_aman}</h1>
                <p>
                    Menjelajahi kata dominan, pola topik, dan distribusi isu publik
                    untuk layanan {layanan_aman} pada Twitter/X, Instagram, dan TikTok.
                </p>
                <div class="topic-v8-badges">
                    <span class="topic-v8-badge">IndiHome • Aktif</span>
                    <span class="topic-v8-badge">IndiBiz • Aktif</span>
                    <span class="topic-v8-badge">Telkomsel • Aktif</span>
                    <span class="topic-v8-badge">{escape(source_badge)}</span>
                </div>
            </section>
        </div>
        """,
        unsafe_allow_html=True,
    )


DEFAULT_PLATFORMS = tuple(PLATFORM_LABELS.keys())


def _init_filter_state() -> None:
    """Siapkan filter draft dan filter terapan tanpa memicu analisis."""
    if st.session_state.get("_active_service_sync_target") == "Analisis Topik":
        layanan_global = str(st.session_state.get("active_service", "IndiHome")).strip()
        if layanan_global not in LAYANAN_OPTIONS:
            layanan_global = "IndiHome"
        st.session_state["topic_v8_service"] = layanan_global
        st.session_state["topic_v8_applied_service"] = layanan_global
        st.session_state["topic_v8_draft_service"] = layanan_global
        st.session_state.pop("_active_service_sync_target", None)

    legacy_service = str(st.session_state.get("topic_v8_service", "IndiHome"))
    if legacy_service not in LAYANAN_OPTIONS:
        legacy_service = "IndiHome"

    defaults = {
        "topic_v8_applied_service": legacy_service,
        "topic_v8_applied_platforms": DEFAULT_PLATFORMS,
        "topic_v8_applied_sentiment": "all",
        "topic_v8_applied_max_words": 100,
        "topic_v8_applied_show_brand": True,
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value

    draft_defaults = {
        "topic_v8_draft_service": st.session_state["topic_v8_applied_service"],
        "topic_v8_draft_platforms": [
            PLATFORM_LABELS.get(item, item.title())
            for item in st.session_state["topic_v8_applied_platforms"]
        ],
        "topic_v8_draft_sentiment": next(
            (
                label
                for label, value in SENTIMENT_OPTIONS.items()
                if value == st.session_state["topic_v8_applied_sentiment"]
            ),
            "Semua",
        ),
        "topic_v8_draft_max_words": int(st.session_state["topic_v8_applied_max_words"]),
        "topic_v8_draft_show_brand": bool(st.session_state["topic_v8_applied_show_brand"]),
    }
    for key, value in draft_defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


def _render_controls() -> tuple[str, tuple[str, ...], str, int, bool, bool]:
    """Render filter dalam form agar perubahan baru diproses setelah tombol diklik."""
    _init_filter_state()
    label_to_key = {label: key for key, label in PLATFORM_LABELS.items()}

    with st.container(border=True):
        st.markdown(
            '<span class="topic-v8-control-marker"></span>',
            unsafe_allow_html=True,
        )
        with st.form("topic_v8_filter_form", clear_on_submit=False):
            col_service, col_platform, col_sentiment = st.columns([1.05, 1.75, 1.05])

            with col_service:
                layanan_draft = st.selectbox(
                    "Layanan",
                    LAYANAN_OPTIONS,
                    key="topic_v8_draft_service",
                )

            with col_platform:
                selected_labels = st.multiselect(
                    "Platform",
                    options=list(label_to_key),
                    key="topic_v8_draft_platforms",
                )
                platforms_draft = tuple(
                    label_to_key[item] for item in selected_labels if item in label_to_key
                )

            with col_sentiment:
                sentiment_label_draft = st.selectbox(
                    "Filter sentimen",
                    options=list(SENTIMENT_OPTIONS),
                    key="topic_v8_draft_sentiment",
                )

            col_words, col_brand, col_hint, col_apply = st.columns([1.1, 1.1, 2.1, 1.15])
            with col_words:
                max_words_draft = st.slider(
                    "Maksimum kata WordCloud",
                    min_value=50,
                    max_value=200,
                    step=10,
                    key="topic_v8_draft_max_words",
                )
            with col_brand:
                show_brand_draft = st.toggle(
                    "Tampilkan nama brand",
                    key="topic_v8_draft_show_brand",
                )
            with col_hint:
                st.caption(
                    "Ubah filter terlebih dahulu, lalu klik Terapkan Filter. "
                    "Visualisasi tidak akan dimuat ulang sebelum tombol diklik."
                )
            with col_apply:
                st.markdown("<div style='height:1.55rem'></div>", unsafe_allow_html=True)
                submitted = st.form_submit_button(
                    "Terapkan Filter",
                    type="primary",
                    use_container_width=True,
                    on_click=_show_filter_loading,
                )

    if submitted:
        st.session_state["topic_v8_applied_service"] = layanan_draft
        st.session_state["active_service"] = layanan_draft
        st.session_state["topic_v8_applied_platforms"] = platforms_draft
        st.session_state["topic_v8_applied_sentiment"] = SENTIMENT_OPTIONS[
            sentiment_label_draft
        ]
        st.session_state["topic_v8_applied_max_words"] = int(max_words_draft)
        st.session_state["topic_v8_applied_show_brand"] = bool(show_brand_draft)
        log_activity(
            "TOPIC_ANALYSIS",
            "Analisis Topik",
            f"Menerapkan analisis topik untuk layanan {layanan_draft}.",
            service=layanan_draft,
            platform=", ".join(platforms_draft) if platforms_draft else "Semua Platform",
            metadata={
                "sentiment": SENTIMENT_OPTIONS[sentiment_label_draft],
                "max_words": int(max_words_draft),
                "show_brand": bool(show_brand_draft),
            },
        )

    return (
        str(st.session_state["topic_v8_applied_service"]),
        tuple(st.session_state["topic_v8_applied_platforms"]),
        str(st.session_state["topic_v8_applied_sentiment"]),
        int(st.session_state["topic_v8_applied_max_words"]),
        bool(st.session_state["topic_v8_applied_show_brand"]),
        bool(submitted),
    )


_FAST_WORD_PATTERN = re.compile(
    r"https?://\S+|www\.\S+|@\w+|<[^>]+>|[^a-z\s]+",
    re.IGNORECASE,
)


def _count_words_fast(texts: list[str], show_brand: bool, chunk_size: int = 5_000) -> Counter[str]:
    """Hitung frekuensi kata per chunk tanpa preprocessing regex per komentar."""
    counter: Counter[str] = Counter()
    if not texts:
        return counter

    for start_index in range(0, len(texts), chunk_size):
        corpus = " ".join(texts[start_index:start_index + chunk_size]).lower()
        cleaned = _FAST_WORD_PATTERN.sub(" ", corpus)
        normalized_words: list[str] = []
        for raw_word in cleaned.split():
            word = NORMALIZATION_MAP.get(raw_word, raw_word)
            if len(word) <= 2 or word in STOPWORDS_ID:
                continue
            if not show_brand and word in BRAND_WORDS:
                continue
            normalized_words.append(word)
        counter.update(normalized_words)

    return counter


def _load_enriched_topic_data(layanan: str, file_signature: str) -> pd.DataFrame:
    """Gunakan loader bersama agar Analisis Topik dan Rekomendasi konsisten."""
    if str(file_signature).startswith("demo-mode:"):
        dataframe = get_demo_sentiment(layanan).copy()
        return apply_topics(dataframe, text_col="content")
    return _load_shared_enriched_topic_data(layanan, file_signature)


@st.cache_data(show_spinner=False, max_entries=8)
def _build_analysis_payload(
    layanan: str,
    platforms: tuple[str, ...],
    sentiment_filter: str,
    show_brand: bool,
    file_signature: str,
) -> tuple[pd.DataFrame, dict[str, dict[str, int]], pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Filter data terklasifikasi lalu bangun seluruh agregasi secara cepat."""
    try:
        enriched = _load_enriched_topic_data(layanan, file_signature)
        if enriched.empty:
            empty_freq = {item: {} for item in SENTIMENT_ORDER}
            return enriched.copy(), empty_freq, pd.DataFrame(), pd.DataFrame(), pd.DataFrame()

        # Khusus IndiBiz, LDA dilatih menggunakan seluruh data layanan terlebih
        # dahulu. Filter platform/sentimen hanya menyaring hasil tampilan agar
        # model tidak berubah atau jatuh ke fallback saat pengguna memilih satu
        # platform dengan jumlah komentar yang lebih kecil.
        if layanan == "IndiBiz" and not str(file_signature).startswith("demo-mode:"):
            return build_indibiz_stable_filtered_payload(
                enriched,
                platforms=platforms,
                sentiment_filter=sentiment_filter,
                show_brand=show_brand,
            )

        if platforms:
            mask = enriched["platform"].isin(platforms)
        else:
            mask = pd.Series(False, index=enriched.index)
        if sentiment_filter != "all":
            mask &= enriched["predicted_sentiment"].eq(sentiment_filter)

        df = enriched.loc[mask].copy().reset_index(drop=True)
        if df.empty:
            empty_freq = {item: {} for item in SENTIMENT_ORDER}
            return df, empty_freq, pd.DataFrame(), pd.DataFrame(), pd.DataFrame()

        frequency_map: dict[str, Counter[str]] = {}
        for sentiment in SENTIMENT_ORDER:
            texts = df.loc[
                df["predicted_sentiment"].eq(sentiment), "content"
            ].astype(str).tolist()
            frequency_map[sentiment] = _count_words_fast(texts, show_brand=show_brand)

        summary = summarize_topics(df, top_n=5)
        matrix = build_topic_platform_matrix(df)

        combined = Counter()
        for counter in frequency_map.values():
            combined.update(counter)

        frequency_rows: list[dict[str, Any]] = []
        for rank, (word, count) in enumerate(combined.most_common(), start=1):
            sentiment_counts = {
                sentiment: frequency_map[sentiment].get(word, 0)
                for sentiment in SENTIMENT_ORDER
            }
            dominant = max(
                SENTIMENT_ORDER,
                key=lambda sentiment: (
                    sentiment_counts[sentiment],
                    {"negative": 2, "positive": 1, "neutral": 0}[sentiment],
                ),
            )
            frequency_rows.append(
                {
                    "Rank": rank,
                    "Kata": word,
                    "Frekuensi": int(count),
                    "Sentimen Dominan": SENTIMENT_LABELS_ID[dominant],
                }
            )

        return (
            df,
            {key: dict(value) for key, value in frequency_map.items()},
            summary,
            matrix,
            pd.DataFrame(frequency_rows),
        )
    except Exception as exc:
        raise RuntimeError(f"Gagal menyiapkan payload Analisis Topik: {exc}") from exc


def _section_header(title: str, subtitle: str) -> None:
    """Render judul section dengan gaya konsisten."""
    st.markdown(
        f"""
        <div class="topic-v8-section-head">
            <div>
                <div class="topic-v8-section-title">{escape(title)}</div>
                <div class="topic-v8-section-subtitle">{escape(subtitle)}</div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def _render_summary_stats(df: pd.DataFrame, summary: pd.DataFrame) -> None:
    """Render empat metrik ringkas dari hasil filter aktif."""
    total = len(df)
    platform_count = int(df["platform"].nunique()) if not df.empty else 0
    topic_count = int(df["topic"].nunique()) if not df.empty and "topic" in df.columns else 0
    dominant_topic = str(summary.iloc[0]["topik"]) if not summary.empty else "—"
    if len(dominant_topic) > 24:
        dominant_topic = dominant_topic[:22] + "…"

    st.markdown(
        f"""
        <div class="topic-v8-stat-row">
            <div class="topic-v8-stat"><div class="topic-v8-stat-label">Komentar terfilter</div><div class="topic-v8-stat-value">{_format_number(total)}</div></div>
            <div class="topic-v8-stat"><div class="topic-v8-stat-label">Platform aktif</div><div class="topic-v8-stat-value">{platform_count}</div></div>
            <div class="topic-v8-stat"><div class="topic-v8-stat-label">Topik terdeteksi</div><div class="topic-v8-stat-value">{topic_count}</div></div>
            <div class="topic-v8-stat"><div class="topic-v8-stat-label">Topik teratas</div><div class="topic-v8-stat-value" style="font-size:1rem;line-height:1.35;margin-top:.5rem;">{escape(dominant_topic)}</div></div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def _wordcloud_corpus_signature(
    frequency_items: tuple[tuple[str, int], ...],
) -> str:
    """Buat signature corpus deterministik untuk cache WordCloud."""
    try:
        return "|".join(
            f"{word}:{int(count)}"
            for word, count in frequency_items
            if str(word).strip() and int(count) > 0
        )
    except Exception:
        return ""


@st.cache_data(
    show_spinner="Memproses WordCloud Analisis Topik...",
    max_entries=24,
)
def _create_wordcloud_png(
    corpus_signature: str,
    frequency_items: tuple[tuple[str, int], ...],
    sentiment: str,
    max_words: int,
) -> bytes:
    """Buat PNG WordCloud sekali; signature corpus menjadi cache key utama."""
    del corpus_signature
    style = WORDCLOUD_STYLE[sentiment]
    buffer = BytesIO()

    if not frequency_items:
        fig, ax = plt.subplots(figsize=(10, 5))  # FIX: rasio WordCloud 2:1 agar responsif
        fig.patch.set_facecolor(style["background"])
        ax.set_facecolor(style["background"])
        ax.text(
            0.5,
            0.5,
            "Tidak ada kata pada filter aktif",
            ha="center",
            va="center",
            color="#666666",
            fontsize=13,
        )
        ax.axis("off")
        fig.tight_layout(pad=0)  # FIX: cegah gambar terpotong pada viewport kecil.
        fig.savefig(
            buffer,
            format="png",
            dpi=WORDCLOUD_EXPORT_DPI_EMPTY,
            bbox_inches="tight",
            facecolor=fig.get_facecolor(),
        )
        plt.close(fig)
        return buffer.getvalue()

    cloud = WordCloud(
        width=WORDCLOUD_EXPORT_WIDTH,
        height=WORDCLOUD_EXPORT_HEIGHT,
        background_color=style["background"],
        colormap=style["colormap"],
        max_words=max_words,
        collocations=False,
        prefer_horizontal=0.75,
        min_font_size=12,  # FIX: teks WordCloud minimum 12px
        random_state=42,
        scale=WORDCLOUD_EXPORT_SCALE,
    ).generate_from_frequencies(dict(frequency_items))
    cloud.to_image().save(buffer, format="PNG", optimize=True)
    return buffer.getvalue()


def _png_to_matplotlib_figure(png_data: bytes, sentiment: str) -> plt.Figure:
    """Bungkus PNG cache ke figure Matplotlib agar tetap dirender via st.pyplot."""
    style = WORDCLOUD_STYLE[sentiment]
    fig, ax = plt.subplots(figsize=(10, 5))  # FIX: rasio WordCloud 2:1 agar responsif
    fig.patch.set_facecolor(style["background"])
    ax.set_facecolor(style["background"])
    image = Image.open(BytesIO(png_data))
    ax.imshow(image, interpolation="bilinear")
    ax.axis("off")
    fig.tight_layout(pad=0)
    return fig


def _render_wordclouds(
    df: pd.DataFrame,
    frequency_map: dict[str, dict[str, int]],
    max_words: int,
    layanan: str,
) -> None:
    """Render tiga WordCloud per sentimen dengan hasil gambar yang di-cache."""
    with st.container(border=True):
        st.markdown(
            '<span class="topic-v8-section-marker"></span>',
            unsafe_allow_html=True,
        )
        _section_header(
            "WordCloud per Sentimen",
            "Ukuran kata menunjukkan frekuensi kemunculan setelah stopword Bahasa Indonesia dihapus.",
        )
        columns = st.columns(3)
        for index, sentiment in enumerate(SENTIMENT_ORDER):
            label = SENTIMENT_LABELS_ID[sentiment]
            count = int((df["predicted_sentiment"] == sentiment).sum()) if not df.empty else 0
            with columns[index]:
                st.markdown(
                    f"**{SENTIMENT_ICONS[sentiment]} {label}**  ·  {_format_number(count)} komentar"
                )
                frequency_items = tuple(
                    Counter(frequency_map.get(sentiment, {})).most_common(max_words)
                )
                corpus_signature = _wordcloud_corpus_signature(frequency_items)
                png = _create_wordcloud_png(
                    corpus_signature,
                    frequency_items,
                    sentiment,
                    max_words,
                )
                fig = _png_to_matplotlib_figure(png, sentiment)
                _pyplot_aman(fig, use_container_width=True)
                plt.close(fig)
                st.download_button(
                    "Unduh PNG",
                    data=png,
                    file_name=f"wordcloud_{layanan.lower()}_{sentiment}.png",
                    mime="image/png",
                    key=f"topic_v8_wc_{layanan}_{sentiment}",
                    use_container_width=True,
                )


def _top_words_figure(frequencies: dict[str, int], sentiment: str) -> go.Figure:
    """Buat horizontal bar chart Top 15 kata yang seimbang dan tanpa legenda."""
    items = Counter(frequencies).most_common(15)
    if items:
        reversed_items = list(reversed(items))
        full_words = [word for word, _ in reversed_items]
        values = [count for _, count in reversed_items]
    else:
        full_words = ["Tidak ada data"]
        values = [0]

    # Label panjang dipendekkan agar area batang tetap berada di tengah kartu.
    display_words = [
        word if len(word) <= 16 else f"{word[:15]}…"
        for word in full_words
    ]
    hover_data = [[word, value] for word, value in zip(full_words, values)]

    fig = go.Figure(
        go.Bar(
            x=values,
            y=display_words,
            orientation="h",
            marker={"color": SENTIMENT_COLORS[sentiment]},
            customdata=hover_data,
            hovertemplate=(
                "<b>%{customdata[0]}</b><br>"
                "Frekuensi: %{customdata[1]:,}<extra></extra>"
            ),
        )
    )
    fig.update_layout(
        height=420,
        # Margin kiri dan kanan dibuat seimbang agar plot tidak condong ke kanan.
        margin={"l": 92, "r": 92, "t": 18, "b": 46},
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font={"family": "Inter", "color": "#EDEDED", "size": 11},
        xaxis={
            "title": {"text": "Frekuensi", "standoff": 10},
            "gridcolor": "rgba(255,255,255,0.08)",
            "zeroline": False,
            "fixedrange": False,
        },
        yaxis={
            "title": "",
            "automargin": False,
            "tickfont": {"family": "Inter", "color": "#EDEDED", "size": 11},
            "fixedrange": True,
        },
        showlegend=False,
        bargap=0.18,
        hoverlabel={
            "bgcolor": "#171717",
            "bordercolor": "#343434",
            "font_color": "#FFFFFF",
        },
    )
    return fig


def _plotly_chart(fig: go.Figure | None, key: str) -> None:
    """Render Plotly responsif dengan validasi figur."""
    try:
        if fig is None:
            st.warning("Grafik tidak dapat ditampilkan.")
            return
        themed_figure = _apply_topic_plotly_theme(fig)
        st.plotly_chart(
            themed_figure,
            use_container_width=True,
            config={"displaylogo": False, "responsive": True},
            key=key,
        )
    except TypeError:
        st.plotly_chart(
            _apply_topic_plotly_theme(fig),
            use_container_width=True,
            config={"displaylogo": False, "responsive": True},
        )
    except Exception as exc:
        st.warning(f"Grafik tidak dapat ditampilkan: {exc}")


def _pyplot_aman(figur: Any, *args: Any, **kwargs: Any) -> Any:
    """Render Matplotlib hanya ketika objek figur tersedia."""
    try:
        if figur is None:
            st.warning("WordCloud tidak dapat ditampilkan.")
            return None
        return st.pyplot(figur, *args, **kwargs)
    except Exception as exc:
        st.warning(f"WordCloud tidak dapat ditampilkan: {exc}")
        return None


def _render_top_words(frequency_map: dict[str, dict[str, int]], layanan: str) -> None:
    """Render tiga bar chart Top 15 kata."""
    with st.container(border=True):
        st.markdown(
            '<span class="topic-v8-section-marker"></span>',
            unsafe_allow_html=True,
        )
        _section_header(
            "Top 15 Kata",
            "Arahkan kursor ke bar untuk melihat frekuensi setiap kata.",
        )
        columns = st.columns(3)
        for index, sentiment in enumerate(SENTIMENT_ORDER):
            with columns[index]:
                st.markdown(f"**{SENTIMENT_LABELS_ID[sentiment]}**")
                _plotly_chart(
                    _top_words_figure(frequency_map.get(sentiment, {}), sentiment),
                    key=f"topic_v8_words_{layanan}_{sentiment}",
                )


def _select_representative_comments(
    topic_group: pd.DataFrame,
    topic_name: str,
    sentiment: str,
    topic_keywords: str = "",
    limit: int = 3,
) -> list[dict[str, str]]:
    """Pilih komentar unik yang relevan untuk satu topik dan sentimen."""
    try:
        if topic_group is None or topic_group.empty:
            return []

        selected_columns = [
            column
            for column in ["content", "platform"]
            if column in topic_group.columns
        ]
        subset = topic_group.loc[
            topic_group["predicted_sentiment"].eq(sentiment),
            selected_columns,
        ].copy()
        if subset.empty or "content" not in subset.columns:
            return []

        subset["content"] = subset["content"].fillna("").astype(str).str.strip()
        subset = subset[subset["content"].str.len().ge(8)]
        subset = subset.drop_duplicates(subset=["content"], keep="first")
        if subset.empty:
            return []

        normalized = (
            subset["content"]
            .str.lower()
            .str.replace(r"https?://\S+|www\.\S+|@\w+", " ", regex=True)
            .str.replace(r"[^a-z0-9\s]+", " ", regex=True)
            .str.replace(r"\s+", " ", regex=True)
            .str.strip()
        )

        # LDA menyimpan kata kunci pada ringkasan topik. Untuk layanan lain,
        # tetap gunakan kamus topik lama sebagai cadangan.
        keywords = [
            item.strip().lower()
            for item in str(topic_keywords or "").split(",")
            if item.strip() and item.strip() != "—"
        ]
        if not keywords:
            keywords = get_topic_keywords(topic_name, limit=8)

        match_score = pd.Series(0, index=subset.index, dtype="int64")
        for keyword in keywords[:8]:
            keyword_normalized = re.sub(r"[^a-z0-9\s]+", " ", str(keyword).lower())
            keyword_normalized = re.sub(r"\s+", " ", keyword_normalized).strip()
            if keyword_normalized:
                match_score += normalized.str.contains(
                    re.escape(keyword_normalized),
                    regex=True,
                    na=False,
                ).astype("int64")

        lengths = subset["content"].str.len()
        readable_score = (
            lengths.between(30, 360).astype("int64") * 3
            + lengths.between(15, 520).astype("int64")
        )
        subset["_score"] = match_score * 10 + readable_score
        subset["_length_distance"] = (lengths - 170).abs()
        subset = subset.sort_values(
            ["_score", "_length_distance"],
            ascending=[False, True],
            kind="stable",
        )

        selected: list[dict[str, str]] = []
        platform_available = "platform" in subset.columns
        diverse_candidates = (
            subset.drop_duplicates(subset=["platform"], keep="first")
            if platform_available
            else subset.head(1)
        )
        for _, row in diverse_candidates.head(limit).iterrows():
            platform = str(row.get("platform", "lainnya") or "lainnya").lower()
            selected.append({"content": str(row["content"]), "platform": platform})

        if len(selected) < limit:
            selected_texts = {item["content"] for item in selected}
            remaining = subset.loc[~subset["content"].isin(selected_texts)].head(
                limit - len(selected)
            )
            for _, row in remaining.iterrows():
                platform = str(row.get("platform", "lainnya") or "lainnya").lower()
                selected.append({"content": str(row["content"]), "platform": platform})

        return selected
    except Exception:
        return []


def _sentiment_stat_html(sentiment: str, count: int, total: int) -> str:
    """Buat kartu statistik sentimen untuk ringkasan topik."""
    color = SENTIMENT_COLORS[sentiment]
    label = SENTIMENT_LABELS_ID[sentiment]
    percentage = (count / total * 100.0) if total else 0.0
    return (
        f'<div class="topic-v8-sentiment-stat topic-v8-sentiment-stat-{sentiment}">'
        '<div class="topic-v8-sentiment-stat-label">'
        f'<span class="topic-v8-dot" style="background:{color};"></span>{escape(label)}'
        '</div>'
        f'<div class="topic-v8-sentiment-stat-value">{_format_number(count)}</div>'
        f'<div class="topic-v8-sentiment-stat-sub">{percentage:.1f}% dari topik</div>'
        '</div>'
    )


def _render_sentiment_comment_tab(
    topic_group: pd.DataFrame,
    topic_name: str,
    sentiment: str,
    total_sentiment: int,
    topic_keywords: str = "",
) -> None:
    """Render maksimal tiga komentar representatif pada sentimen yang tersedia."""
    comments = _select_representative_comments(
        topic_group,
        topic_name=topic_name,
        sentiment=sentiment,
        topic_keywords=topic_keywords,
        limit=3,
    )
    label = SENTIMENT_LABELS_ID[sentiment]

    # Fungsi ini hanya dipanggil untuk sentimen yang memiliki komentar. Namun,
    # tetap sediakan pengaman agar UI tidak menampilkan panel error teknis.
    if not comments:
        st.caption(
            f"Komentar {label.lower()} tersedia, tetapi tidak ada contoh teks "
            "yang cukup terbaca untuk ditampilkan."
        )
        return

    st.caption(
        f"Menampilkan {len(comments)} contoh representatif dari "
        f"{_format_number(total_sentiment)} komentar {label.lower()}."
    )
    for comment_index, item in enumerate(comments, start=1):
        platform = PLATFORM_LABELS.get(
            str(item.get("platform", "lainnya")).lower(),
            str(item.get("platform", "Lainnya")).title(),
        )
        content = escape(str(item.get("content", "—")))
        st.markdown(
            f"""
            <article class="topic-v8-comment-card topic-v8-comment-card-{sentiment}">
                <div class="topic-v8-comment-meta">
                    <span>Contoh {comment_index}</span>
                    <span>•</span>
                    <span>{escape(platform)}</span>
                    <span>•</span>
                    <span>{escape(label)}</span>
                </div>
                <div class="topic-v8-comment-text">{content}</div>
            </article>
            """,
            unsafe_allow_html=True,
        )


def _render_topic_cards(summary: pd.DataFrame, df: pd.DataFrame, layanan: str) -> None:
    """Render maksimal lima topik total dengan komentar yang benar-benar ada."""
    with st.container(border=True):
        st.markdown(
            '<span class="topic-v8-section-marker"></span>',
            unsafe_allow_html=True,
        )
        _section_header(
            "Top 5 Topik",
            f"{layanan} menampilkan lima kelompok topik utama berdasarkan kata kunci dominan. Buka setiap kartu untuk melihat komposisi sentimen dan contoh komentarnya.",
        )

        if summary.empty or df is None or df.empty:
            st.info("Belum ada topik yang dapat ditampilkan pada kombinasi filter ini.")
            return

        # Pengaman UI: walaupun sumber ringkasan bermasalah, bagian ini tidak
        # akan pernah menampilkan lebih dari lima topik.
        visible_summary = summary.head(5).reset_index(drop=True)

        for index, row in visible_summary.iterrows():
            topic_raw = str(row.get("topik", "Topik Lainnya"))
            topic_group = df.loc[df["topic"].astype(str).eq(topic_raw)].copy()
            total = int(len(topic_group))
            if total <= 0:
                continue

            count = int(row.get("jumlah_komentar", total))
            percentage = float(row.get("persentase", 0.0))
            keywords = str(row.get("kata_kunci", "—"))
            dominant = str(row.get("sentimen_dominan", "neutral"))
            dominant_label = SENTIMENT_LABELS_ID.get(dominant, "Netral")

            sentiment_counts = {
                sentiment: int(
                    topic_group["predicted_sentiment"].eq(sentiment).sum()
                )
                for sentiment in SENTIMENT_ORDER
            }

            expander_label = (
                f"{index + 1}. {topic_raw}  ·  {_format_number(count)} komentar  ·  "
                f"Dominan {dominant_label}"
            )
            with st.expander(expander_label, expanded=(index == 0)):
                sentiment_stats = "".join(
                    _sentiment_stat_html(sentiment, sentiment_counts[sentiment], total)
                    for sentiment in ["negative", "neutral", "positive"]
                )
                st.markdown(
                    f"""
                    <div class="topic-v8-topic-overview">
                        <div class="topic-v8-topic-overview-head">
                            <div>
                                <div class="topic-v8-topic-overview-title">{index + 1}. {escape(topic_raw)}</div>
                                <div class="topic-v8-topic-overview-meta">
                                    {_format_number(count)} komentar · {percentage:.1f}% dari data terfilter<br>
                                    Kata kunci: {escape(keywords)}
                                </div>
                            </div>
                            <span class="topic-v8-chip topic-v8-chip-{dominant}">{escape(dominant_label)}</span>
                        </div>
                        <div class="topic-v8-sentiment-grid">{sentiment_stats}</div>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )

                active_sentiments = [
                    sentiment
                    for sentiment in ["negative", "neutral", "positive"]
                    if sentiment_counts[sentiment] > 0
                ]

                # Jangan membuat tab kosong. Jika topik hanya punya satu jenis
                # sentimen, komentarnya langsung ditampilkan tanpa tab tambahan.
                if len(active_sentiments) == 1:
                    only_sentiment = active_sentiments[0]
                    st.markdown(
                        f"**Contoh komentar {SENTIMENT_LABELS_ID[only_sentiment]}**"
                    )
                    _render_sentiment_comment_tab(
                        topic_group,
                        topic_name=topic_raw,
                        sentiment=only_sentiment,
                        total_sentiment=sentiment_counts[only_sentiment],
                        topic_keywords=keywords,
                    )
                elif active_sentiments:
                    tabs = st.tabs(
                        [
                            f"{SENTIMENT_LABELS_ID[sentiment]} · "
                            f"{_format_number(sentiment_counts[sentiment])}"
                            for sentiment in active_sentiments
                        ]
                    )
                    for tab, sentiment in zip(tabs, active_sentiments):
                        with tab:
                            _render_sentiment_comment_tab(
                                topic_group,
                                topic_name=topic_raw,
                                sentiment=sentiment,
                                total_sentiment=sentiment_counts[sentiment],
                                topic_keywords=keywords,
                            )

def _heatmap_figure(matrix: pd.DataFrame, top_topics: list[str]) -> go.Figure:
    """Buat heatmap interaktif dalam mode jumlah dan persentase per platform."""
    if matrix.empty:
        matrix = pd.DataFrame([[0]], index=["Tidak ada data"], columns=["Tidak ada topik"])
    elif top_topics:
        available = [item for item in top_topics if item in matrix.columns]
        if available:
            matrix = matrix[available]

    matrix = matrix.fillna(0).astype(int)
    platform_labels = [PLATFORM_LABELS.get(str(item), str(item).title()) for item in matrix.index]
    full_topics = [str(item) for item in matrix.columns]

    def _wrap_label(
        label: str,
        limit: int = 18,
        max_lines: int = 3,
    ) -> str:
        """Bungkus label sumbu-X agar nama topik tidak saling bertumpuk.

        Nama lengkap tetap dipakai pada hover dan bagian detail. Versi ringkas ini
        hanya digunakan sebagai label visual pada sumbu heatmap.
        """
        clean_label = " ".join(str(label).split())
        if not clean_label:
            return clean_label

        # Tanda pisah pada nama topik turunan dijadikan batas baris alami.
        clean_label = clean_label.replace(" — ", " | ")
        segments = [segment.strip() for segment in clean_label.split("|") if segment.strip()]

        lines: list[str] = []
        for segment in segments:
            current = ""
            for word in segment.split():
                candidate = word if not current else f"{current} {word}"
                if len(candidate) <= limit:
                    current = candidate
                else:
                    if current:
                        lines.append(current)
                    current = word
            if current:
                lines.append(current)

        if len(lines) > max_lines:
            overflow = " ".join(lines[max_lines - 1 :])
            if len(overflow) > limit:
                overflow = overflow[: max(1, limit - 1)].rstrip() + "…"
            lines = lines[: max_lines - 1] + [overflow]

        return "<br>".join(lines[:max_lines])

    display_topics = [_wrap_label(item) for item in full_topics]
    count_values = matrix.to_numpy(dtype=float)
    row_totals = matrix.sum(axis=1).replace(0, 1)
    percent_matrix = matrix.div(row_totals, axis=0).mul(100)
    percent_values = percent_matrix.to_numpy(dtype=float)

    count_text = [
        [_format_number(int(value)) for value in row]
        for row in count_values
    ]
    percent_text = [
        [f"{float(value):.1f}%" for value in row]
        for row in percent_values
    ]
    customdata = [
        [
            [full_topics[column_index], int(count_values[row_index][column_index]), float(percent_values[row_index][column_index])]
            for column_index in range(len(full_topics))
        ]
        for row_index in range(len(platform_labels))
    ]

    colorscale = [
        [0.00, "#0B0C10"],
        [0.18, "#211011"],
        [0.42, "#5A1B1D"],
        [0.72, "#B52B2D"],
        [1.00, "#FF4B47"],
    ]
    hover_template = (
        "<b>%{y}</b><br>"
        "Topik: %{customdata[0]}<br>"
        "Jumlah komentar: %{customdata[1]:,}<br>"
        "Porsi di platform: %{customdata[2]:.1f}%"
        "<extra></extra>"
    )

    count_trace = go.Heatmap(
        z=count_values,
        x=display_topics,
        y=platform_labels,
        colorscale=colorscale,
        colorbar={
            "title": {"text": "Komentar", "side": "top", "font": {"color": "#EDEDED", "size": 11}},
            "tickfont": {"color": "#AAAAAA", "size": 10},
            "thickness": 14,
            "len": 0.78,
            "outlinecolor": "#3A3A3A",
            "outlinewidth": 1,
        },
        text=count_text,
        texttemplate="%{text}",
        textfont={"color": "#FFFFFF", "size": 12},
        customdata=customdata,
        hovertemplate=hover_template,
        hoverongaps=False,
        xgap=4,
        ygap=4,
        visible=True,
        name="Jumlah",
    )

    percent_trace = go.Heatmap(
        z=percent_values,
        x=display_topics,
        y=platform_labels,
        zmin=0,
        zmax=max(float(percent_values.max()), 1.0),
        colorscale=colorscale,
        colorbar={
            "title": {"text": "Persentase", "side": "top", "font": {"color": "#EDEDED", "size": 11}},
            "ticksuffix": "%",
            "tickfont": {"color": "#AAAAAA", "size": 10},
            "thickness": 14,
            "len": 0.78,
            "outlinecolor": "#3A3A3A",
            "outlinewidth": 1,
        },
        text=percent_text,
        texttemplate="%{text}",
        textfont={"color": "#FFFFFF", "size": 12},
        customdata=customdata,
        hovertemplate=hover_template,
        hoverongaps=False,
        xgap=4,
        ygap=4,
        visible=False,
        name="Persentase",
    )

    fig = go.Figure(data=[count_trace, percent_trace])
    fig.update_layout(
        height=535,
        margin={"l": 24, "r": 30, "t": 68, "b": 145},
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font={"family": "Inter", "color": "#EDEDED", "size": 11},
        xaxis={
            "title": {"text": "Nama Topik", "standoff": 18},
            "tickangle": 0,
            "tickfont": {"size": 10, "color": "#EDEDED"},
            "ticklabelposition": "outside",
            "automargin": True,
            "showgrid": False,
            "zeroline": False,
            "fixedrange": False,
        },
        yaxis={
            "title": {"text": "Platform", "standoff": 14},
            "automargin": True,
            "showgrid": False,
            "zeroline": False,
            "fixedrange": False,
        },
        hoverlabel={
            "bgcolor": "#171717",
            "bordercolor": "#E53935",
            "font_color": "#FFFFFF",
            "font_size": 12,
        },
        updatemenus=[
            {
                "type": "buttons",
                "direction": "right",
                "showactive": False,
                "x": 0.0,
                "xanchor": "left",
                "y": 1.14,
                "yanchor": "top",
                "bgcolor": "#8F1D1D",
                "bordercolor": "#E53935",
                "borderwidth": 1,
                "font": {"color": "#FFFFFF", "size": 11},
                "pad": {"r": 0, "t": 4},
                "buttons": [
                    {
                        "label": "Jumlah komentar",
                        "method": "update",
                        "args": [
                            {"visible": [True, False]},
                            {
                                "title": {"text": "Mode: Jumlah komentar", "font": {"size": 11, "color": "#8F8F8F"}, "x": 0.99, "xanchor": "right", "y": 0.99},
                                "updatemenus[0].bgcolor": "#8F1D1D",
                                "updatemenus[0].bordercolor": "#E53935",
                                "updatemenus[1].bgcolor": "#17191F",
                                "updatemenus[1].bordercolor": "#3A3D45",
                            },
                        ],
                    }
                ],
            },
            {
                "type": "buttons",
                "direction": "right",
                "showactive": False,
                "x": 0.185,
                "xanchor": "left",
                "y": 1.14,
                "yanchor": "top",
                "bgcolor": "#17191F",
                "bordercolor": "#3A3D45",
                "borderwidth": 1,
                "font": {"color": "#FFFFFF", "size": 11},
                "pad": {"r": 0, "t": 4},
                "buttons": [
                    {
                        "label": "% per platform",
                        "method": "update",
                        "args": [
                            {"visible": [False, True]},
                            {
                                "title": {"text": "Mode: Persentase per platform", "font": {"size": 11, "color": "#8F8F8F"}, "x": 0.99, "xanchor": "right", "y": 0.99},
                                "updatemenus[0].bgcolor": "#17191F",
                                "updatemenus[0].bordercolor": "#3A3D45",
                                "updatemenus[1].bgcolor": "#8F1D1D",
                                "updatemenus[1].bordercolor": "#E53935",
                            },
                        ],
                    }
                ],
            },
        ],
        title={
            "text": "Mode: Jumlah komentar",
            "font": {"size": 11, "color": "#8F8F8F"},
            "x": 0.99,
            "xanchor": "right",
            "y": 0.99,
        },
        transition={"duration": 260, "easing": "cubic-in-out"},
    )
    return fig


def _render_heatmap(matrix: pd.DataFrame, summary: pd.DataFrame, layanan: str) -> None:
    """Render heatmap interaktif beserta ringkasan dan penjelasan sumber data."""
    with st.container(border=True):
        st.markdown(
            '<span class="topic-v8-section-marker"></span>',
            unsafe_allow_html=True,
        )
        _section_header(
            "Heatmap Topik per Platform",
            "Hover sel untuk detail, ganti mode Jumlah/Persentase, lalu gunakan toolbar Plotly untuk zoom, reset, atau unduh PNG.",
        )

        top_topics = summary["topik"].astype(str).tolist() if not summary.empty else []
        selected_matrix = matrix.copy()
        if not selected_matrix.empty and top_topics:
            available = [item for item in top_topics if item in selected_matrix.columns]
            if available:
                selected_matrix = selected_matrix[available]

        if selected_matrix.empty:
            total_comments = 0
            dominant_platform = "—"
            dominant_platform_count = 0
            hottest_topic = "—"
            hottest_topic_count = 0
        else:
            total_comments = int(selected_matrix.to_numpy().sum())
            platform_totals = selected_matrix.sum(axis=1)
            dominant_platform_key = str(platform_totals.idxmax())
            dominant_platform = PLATFORM_LABELS.get(dominant_platform_key, dominant_platform_key.title())
            dominant_platform_count = int(platform_totals.max())
            topic_totals = selected_matrix.sum(axis=0)
            hottest_topic = str(topic_totals.idxmax())
            hottest_topic_count = int(topic_totals.max())

        st.markdown(
            f"""
            <div class="topic-v8-heatmap-insights">
                <div class="topic-v8-heatmap-insight">
                    <div class="topic-v8-heatmap-insight-label">Total topik ditampilkan</div>
                    <div class="topic-v8-heatmap-insight-value">{_format_number(total_comments)} komentar</div>
                    <div class="topic-v8-heatmap-insight-note">Akumulasi topik pada platform aktif</div>
                </div>
                <div class="topic-v8-heatmap-insight">
                    <div class="topic-v8-heatmap-insight-label">Platform paling aktif</div>
                    <div class="topic-v8-heatmap-insight-value">{escape(dominant_platform)}</div>
                    <div class="topic-v8-heatmap-insight-note">{_format_number(dominant_platform_count)} komentar Top 5</div>
                </div>
                <div class="topic-v8-heatmap-insight">
                    <div class="topic-v8-heatmap-insight-label">Topik paling padat</div>
                    <div class="topic-v8-heatmap-insight-value">{escape(hottest_topic)}</div>
                    <div class="topic-v8-heatmap-insight-note">{_format_number(hottest_topic_count)} komentar lintas platform</div>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        heatmap_config = {
            "displaylogo": False,
            "responsive": True,
            "displayModeBar": True,
            "scrollZoom": False,
            "modeBarButtonsToRemove": ["lasso2d", "select2d"],
            "toImageButtonOptions": {
                "format": "png",
                "filename": f"heatmap_topik_{layanan.lower()}",
                "width": 1600,
                "height": 900,
                "scale": 2,
            },
        }
        try:
            st.plotly_chart(
                _apply_topic_plotly_theme(_heatmap_figure(matrix, top_topics)),
                use_container_width=True,
                config=heatmap_config,
                key=f"topic_v8_heatmap_{layanan}",
            )
        except TypeError:
            st.plotly_chart(
                _apply_topic_plotly_theme(_heatmap_figure(matrix, top_topics)),
                use_container_width=True,
                config=heatmap_config,
            )

        source_label = get_data_source_label(layanan)
        if layanan == "IndiBiz":
            method_note = (
                "Komentar IndiBiz dikelompokkan oleh satu model LDA global menjadi "
                f"maksimal {INDIBIZ_LDA_N_TOPICS} topik utama. Setiap topik memakai "
                f"{INDIBIZ_LDA_N_WORDS} kata kunci dan memerlukan minimal "
                f"{INDIBIZ_LDA_MIN_DOCS} dokumen bersih secara keseluruhan."
            )
        else:
            method_note = (
                "Setiap komentar dikelompokkan melalui kamus keyword di "
                "utils/topic_classifier.py."
            )
        st.markdown(
            f"""
            <div class="topic-v8-heatmap-source">
                <span>ⓘ</span>
                <div>
                    <strong>Sumber angka:</strong> {escape(source_label)} layanan {escape(layanan)} setelah filter aktif.
                    {escape(method_note)} Data kemudian dihitung dengan tabulasi silang
                    <strong>platform × topik</strong>. Heatmap menampilkan topik teratas yang tersedia pada filter aktif.
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )



def _render_frequency_table(table: pd.DataFrame, layanan: str) -> None:
    """Render tabel frekuensi yang cantik, interaktif, dapat difilter, dan diunduh."""
    with st.container(border=True):
        st.markdown(
            '<span class="topic-v8-section-marker"></span>',
            unsafe_allow_html=True,
        )
        _section_header(
            "Tabel Frekuensi Kata",
            "Cari, urutkan, buka detail kata, navigasikan halaman, lalu unduh hasil filter sebagai CSV.",
        )

        if table.empty:
            st.info("Belum ada frekuensi kata pada filter aktif.")
            return

        form_key = f"topic_v8_table_filter_form_{layanan}"
        with st.form(form_key, clear_on_submit=False):
            col_search, col_sentiment, col_sort, col_rows = st.columns([2.1, 1.15, 1.35, 0.8])
            with col_search:
                query = st.text_input(
                    "Cari kata",
                    placeholder="Contoh: jaringan, paket, layanan",
                    key=f"topic_v8_table_search_{layanan}",
                ).strip().lower()
            with col_sentiment:
                dominant_filter = st.selectbox(
                    "Sentimen dominan",
                    ["Semua", "Positif", "Netral", "Negatif"],
                    key=f"topic_v8_table_sentiment_{layanan}",
                )
            with col_sort:
                sort_mode = st.selectbox(
                    "Urutkan",
                    ["Frekuensi tertinggi", "Frekuensi terendah", "Kata A–Z", "Kata Z–A"],
                    key=f"topic_v8_table_sort_{layanan}",
                )
            with col_rows:
                rows_per_page = st.selectbox(
                    "Baris",
                    [10, 15, 25, 50],
                    index=1,
                    key=f"topic_v8_table_rows_{layanan}",
                )

            table_submitted = st.form_submit_button(
                "Terapkan Pengaturan Tabel",
                type="primary",
                use_container_width=True,
            )

        filtered = table.copy()

        # HOTFIX FASE 15 v1.3:
        # Output CSV IndiBiz dapat membawa angka sebagai teks, misalnya "15".
        # Pandas Styler.bar membandingkan nilai tersebut dengan angka nol saat
        # merender tabel. Tanpa normalisasi, Python memunculkan TypeError karena
        # teks tidak dapat dibandingkan dengan integer. Konversi ini tidak
        # mengubah tampilan atau isi data, hanya memastikan tipe numeriknya benar.
        if "Frekuensi" not in filtered.columns:
            st.error("Kolom Frekuensi tidak ditemukan pada tabel frekuensi kata.")
            return
        filtered["Frekuensi"] = (
            pd.to_numeric(filtered["Frekuensi"], errors="coerce")
            .fillna(0)
            .clip(lower=0)
            .astype("int64")
        )
        if "Rank" in filtered.columns:
            filtered["Rank"] = (
                pd.to_numeric(filtered["Rank"], errors="coerce")
                .fillna(0)
                .clip(lower=0)
                .astype("int64")
            )

        if query:
            filtered = filtered[
                filtered["Kata"].astype(str).str.lower().str.contains(query, na=False, regex=False)
            ]
        if dominant_filter != "Semua":
            filtered = filtered[filtered["Sentimen Dominan"] == dominant_filter]

        if sort_mode == "Frekuensi terendah":
            filtered = filtered.sort_values(["Frekuensi", "Kata"], ascending=[True, True])
        elif sort_mode == "Kata A–Z":
            filtered = filtered.sort_values("Kata", ascending=True, key=lambda col: col.astype(str).str.lower())
        elif sort_mode == "Kata Z–A":
            filtered = filtered.sort_values("Kata", ascending=False, key=lambda col: col.astype(str).str.lower())
        else:
            filtered = filtered.sort_values(["Frekuensi", "Kata"], ascending=[False, True])

        filtered = filtered.reset_index(drop=True)
        filtered["Rank"] = range(1, len(filtered) + 1)
        filtered = filtered[["Rank", "Kata", "Frekuensi", "Sentimen Dominan"]]

        if filtered.empty:
            st.warning("Tidak ada kata yang cocok dengan filter tabel.")
            return

        dominant_counts = filtered["Sentimen Dominan"].value_counts()
        dominant_sentiment = str(dominant_counts.index[0]) if not dominant_counts.empty else "—"
        total_frequency = int(pd.to_numeric(filtered["Frekuensi"], errors="coerce").fillna(0).sum())
        top_word = str(filtered.iloc[0]["Kata"]) if not filtered.empty else "—"

        st.markdown(
            f"""
            <div class="topic-v8-table-stats">
                <div class="topic-v8-table-stat">
                    <div class="topic-v8-table-stat-label">Kata ditemukan</div>
                    <div class="topic-v8-table-stat-value">{_format_number(len(filtered))}</div>
                </div>
                <div class="topic-v8-table-stat">
                    <div class="topic-v8-table-stat-label">Total frekuensi</div>
                    <div class="topic-v8-table-stat-value">{_format_number(total_frequency)}</div>
                </div>
                <div class="topic-v8-table-stat">
                    <div class="topic-v8-table-stat-label">Sentimen terbanyak</div>
                    <div class="topic-v8-table-stat-value">{escape(dominant_sentiment)}</div>
                </div>
                <div class="topic-v8-table-stat">
                    <div class="topic-v8-table-stat-label">Kata teratas</div>
                    <div class="topic-v8-table-stat-value">{escape(top_word)}</div>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        page_key = f"topic_v8_table_page_{layanan}"
        if page_key not in st.session_state:
            st.session_state[page_key] = 1
        if table_submitted:
            st.session_state[page_key] = 1

        total_rows = len(filtered)
        total_pages = max(1, (total_rows + int(rows_per_page) - 1) // int(rows_per_page))
        current_page = min(max(1, int(st.session_state.get(page_key, 1))), total_pages)
        st.session_state[page_key] = current_page

        start_index = (current_page - 1) * int(rows_per_page)
        end_index = min(start_index + int(rows_per_page), total_rows)
        page_df = filtered.iloc[start_index:end_index].copy()
        # Pengaman kedua tepat sebelum Pandas Styler merender bar di dalam sel.
        page_df["Rank"] = (
            pd.to_numeric(page_df["Rank"], errors="coerce")
            .fillna(0)
            .clip(lower=0)
            .astype("int64")
        )
        page_df["Frekuensi"] = (
            pd.to_numeric(page_df["Frekuensi"], errors="coerce")
            .fillna(0)
            .clip(lower=0)
            .astype("int64")
        )

        st.markdown(
            f"""
            <div class="topic-v8-table-meta">
                <span>Menampilkan <strong>{_format_number(start_index + 1)}–{_format_number(end_index)}</strong> dari <strong>{_format_number(total_rows)}</strong> kata</span>
                <span>Klik judul kolom untuk mengurutkan tampilan halaman ini.</span>
            </div>
            """,
            unsafe_allow_html=True,
        )

        table_dark_mode = _topic_is_dark_mode()
        table_background = "#111111" if table_dark_mode else "#FFFFFF"
        table_text = "#F2F2F2" if table_dark_mode else "#172033"
        table_border = "#292929" if table_dark_mode else "#E2E8F0"
        table_header_background = "#1B1E26" if table_dark_mode else "#F8FAFC"
        table_header_text = "#B7B7B7" if table_dark_mode else "#475569"
        table_header_border = "#343434" if table_dark_mode else "#DCE3EC"
        table_hover_text = "#FFFFFF" if table_dark_mode else "#172033"

        def _sentiment_style(value: Any) -> str:
            label = str(value).strip().lower()
            if label == "positif":
                if table_dark_mode:
                    return "background-color: rgba(76,175,80,.16); color: #8FE49A; font-weight: 750;"
                return "background-color: #EAF7EC; color: #1B6A27; font-weight: 750;"
            if label == "negatif":
                if table_dark_mode:
                    return "background-color: rgba(244,67,54,.16); color: #FF8A80; font-weight: 750;"
                return "background-color: #FFE9E8; color: #A6231F; font-weight: 750;"
            if table_dark_mode:
                return "background-color: rgba(255,152,0,.16); color: #FFC46B; font-weight: 750;"
            return "background-color: #FFF4DE; color: #8A5200; font-weight: 750;"

        styled_page = (
            page_df.style
            .format({"Rank": "{:,.0f}", "Frekuensi": lambda value: _format_number(value)})
            .map(_sentiment_style, subset=["Sentimen Dominan"])
            .bar(subset=["Frekuensi"], color="rgba(229,57,53,.22)", vmin=0)
            .set_properties(**{
                "background-color": table_background,
                "color": table_text,
                "border-color": table_border,
                "font-size": "14px",
            })
            .set_properties(subset=["Rank", "Frekuensi"], **{"text-align": "right"})
            .set_properties(subset=["Kata"], **{"font-weight": "650"})
            .set_table_styles([
                {
                    "selector": "thead th",
                    "props": [
                        ("background-color", table_header_background),
                        ("color", table_header_text),
                        ("font-weight", "750"),
                        ("border-color", table_header_border),
                    ],
                },
                {
                    "selector": "tbody tr:hover td",
                    "props": [
                        ("background-color", "rgba(229,57,53,.08)"),
                        ("color", table_hover_text),
                    ],
                },
            ])
        )

        st.dataframe(
            styled_page,
            use_container_width=True,
            hide_index=True,
            height=min(590, 80 + max(1, len(page_df)) * 38),
        )

        nav_left, nav_center, nav_right = st.columns([1, 1.4, 1])
        with nav_left:
            st.button(
                "← Sebelumnya",
                key=f"topic_v8_table_prev_{layanan}",
                disabled=current_page <= 1,
                use_container_width=True,
                on_click=_change_table_page_with_loading,
                args=(
                    page_key,
                    max(1, current_page - 1),
                    "Memuat halaman tabel sebelumnya...",
                ),
            )
        with nav_center:
            st.markdown(
                f"<div style='text-align:center;color:#AAAAAA;padding:.55rem 0;font-size:.78rem;'>Halaman <strong style='color:#FFFFFF'>{current_page}</strong> dari <strong style='color:#FFFFFF'>{total_pages}</strong></div>",
                unsafe_allow_html=True,
            )
        with nav_right:
            st.button(
                "Berikutnya →",
                key=f"topic_v8_table_next_{layanan}",
                disabled=current_page >= total_pages,
                use_container_width=True,
                on_click=_change_table_page_with_loading,
                args=(
                    page_key,
                    min(total_pages, current_page + 1),
                    "Memuat halaman tabel berikutnya...",
                ),
            )

        detail_words = page_df["Kata"].astype(str).tolist()
        detail_widget_key = f"topic_v8_table_detail_word_{layanan}_{current_page}"
        selected_word = st.selectbox(
            "Lihat detail kata",
            detail_words,
            key=detail_widget_key,
            help="Pilih salah satu kata pada halaman aktif untuk melihat ringkasan detailnya.",
            on_change=_show_word_detail_loading,
            args=(detail_widget_key,),
        )
        selected_row = page_df[page_df["Kata"].astype(str) == str(selected_word)].iloc[0]
        selected_frequency = int(selected_row["Frekuensi"])
        share = (selected_frequency / total_frequency * 100) if total_frequency else 0.0
        sentiment_label = str(selected_row["Sentimen Dominan"])
        sentiment_lower = sentiment_label.lower()
        sentiment_css = (
            "background:rgba(76,175,80,.18);color:#8FE49A;"
            if sentiment_lower == "positif"
            else "background:rgba(244,67,54,.18);color:#FF8A80;"
            if sentiment_lower == "negatif"
            else "background:rgba(255,152,0,.18);color:#FFC46B;"
        )

        st.markdown(
            f"""
            <div class="topic-v8-table-detail">
                <div class="topic-v8-table-detail-item">
                    <span>Kata dipilih</span>
                    <strong>{escape(str(selected_row['Kata']))}</strong>
                </div>
                <div class="topic-v8-table-detail-item">
                    <span>Rank</span>
                    <strong>#{_format_number(selected_row['Rank'])}</strong>
                </div>
                <div class="topic-v8-table-detail-item">
                    <span>Frekuensi</span>
                    <strong>{_format_number(selected_frequency)} · {share:.2f}%</strong>
                </div>
                <div class="topic-v8-table-detail-item">
                    <span>Sentimen dominan</span>
                    <strong class="topic-v8-table-sentiment" style="{sentiment_css}">{escape(sentiment_label)}</strong>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        csv_data = filtered.to_csv(index=False).encode("utf-8-sig")
        st.download_button(
            "Unduh CSV Frekuensi Terfilter",
            data=csv_data,
            file_name=f"frekuensi_kata_{layanan.lower()}.csv",
            mime="text/csv",
            key=f"topic_v8_download_table_{layanan}",
            use_container_width=True,
        )



@st.cache_data(show_spinner=False, max_entries=12)
def _load_indibiz_csv_cached(
    file_path: str,
    file_signature: str,
    required_columns: tuple[str, ...],
) -> pd.DataFrame:
    """Baca output CSV IndiBiz dengan cache dan validasi kolom wajib."""
    del file_signature
    dataframe = pd.read_csv(
        file_path,
        sep=None,
        engine="python",
        encoding="utf-8-sig",
    )
    dataframe.columns = [
        str(column).strip().lower().lstrip("\ufeff")
        for column in dataframe.columns
    ]
    missing_columns = [
        column for column in required_columns if column not in dataframe.columns
    ]
    if missing_columns:
        raise ValueError(
            "Kolom wajib tidak ditemukan: " + ", ".join(missing_columns)
        )
    return dataframe


@st.cache_data(show_spinner=False, max_entries=6)
def _load_indibiz_wordcloud_cached(file_path: str, file_signature: str) -> bytes:
    """Baca PNG WordCloud IndiBiz dan validasi bahwa file merupakan gambar."""
    del file_signature
    image_bytes = Path(file_path).read_bytes()
    with Image.open(BytesIO(image_bytes)) as image:
        image.verify()
    return image_bytes


def _normalize_indibiz_sentiment(series: pd.Series) -> pd.Series:
    """Normalisasi label sentimen output Colab ke positive, neutral, negative."""
    return (
        series.fillna("")
        .astype(str)
        .str.strip()
        .str.lower()
        .str.lstrip("'")
        .map(INDIBIZ_SENTIMENT_NORMALIZATION)
        .fillna("")
    )


@st.cache_data(show_spinner=False, max_entries=6)
def _build_indibiz_runtime_outputs_cached(
    sentiment_file_signature: str,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Bangun ulang Top 15 Kata dan Top 5 Topik dari data sentimen IndiBiz.

    CSV hasil pipeline Colab tetap menjadi sumber utama. Fungsi ini hanya menjadi
    fallback terarah ketika salah satu CSV turunan belum tersimpan di folder data.
    """
    top_word_columns = ["sentiment", "rank", "kata", "frekuensi"]
    topic_columns = [
        "sentiment",
        "topik",
        "keywords",
        "topic_rank",
        "jumlah_komentar",
        "total_topik",
        "persentase_sentimen",
        "persentase_topik",
        "sentimen_dominan",
        "contoh_komentar",
        "contoh_platform",
    ]

    try:
        source = _load_enriched_topic_data(
            "IndiBiz",
            sentiment_file_signature,
        )
        if source is None or source.empty:
            return (
                pd.DataFrame(columns=top_word_columns),
                pd.DataFrame(columns=topic_columns),
            )

        enriched, frequency_map, summary, _, _ = build_indibiz_topic_payload(
            source,
            show_brand=False,
        )

        top_word_rows: list[dict[str, Any]] = []
        for sentiment in SENTIMENT_ORDER:
            frequencies = Counter(frequency_map.get(sentiment, {}))
            for rank, (word, count) in enumerate(
                frequencies.most_common(15),
                start=1,
            ):
                top_word_rows.append(
                    {
                        "sentiment": sentiment,
                        "rank": rank,
                        "kata": str(word),
                        "frekuensi": int(count),
                    }
                )
        top_words = pd.DataFrame(top_word_rows, columns=top_word_columns)

        if enriched is None or enriched.empty or summary is None or summary.empty:
            return top_words, pd.DataFrame(columns=topic_columns)

        working = enriched.copy()
        working["predicted_sentiment"] = _normalize_indibiz_sentiment(
            working["predicted_sentiment"]
        )
        working["content"] = working["content"].fillna("").astype(str).str.strip()
        if "platform" not in working.columns:
            working["platform"] = "lainnya"
        working["platform"] = (
            working["platform"].fillna("lainnya").astype(str).str.strip().str.lower()
        )

        total_comments = max(1, len(working))
        sentiment_totals = working["predicted_sentiment"].value_counts().to_dict()
        topic_rows: list[dict[str, Any]] = []

        for fallback_rank, summary_row in summary.reset_index(drop=True).iterrows():
            topic_name = str(summary_row.get("topik", "")).strip()
            if not topic_name:
                continue

            topic_group = working[
                working["topic"].fillna("").astype(str).eq(topic_name)
            ].copy()
            if topic_group.empty:
                continue

            topic_rank = fallback_rank + 1
            topic_total = int(len(topic_group))
            topic_percentage = topic_total / total_comments * 100.0
            dominant_sentiment = str(
                summary_row.get("sentimen_dominan", "neutral")
            ).strip().lower()
            dominant_sentiment = INDIBIZ_SENTIMENT_NORMALIZATION.get(
                dominant_sentiment,
                dominant_sentiment if dominant_sentiment in SENTIMENT_ORDER else "neutral",
            )
            keywords = str(
                summary_row.get(
                    "kata_kunci",
                    summary_row.get("keywords", "—"),
                )
            ).strip() or "—"

            for sentiment in SENTIMENT_ORDER:
                sentiment_group = topic_group[
                    topic_group["predicted_sentiment"].eq(sentiment)
                ].copy()
                if sentiment_group.empty:
                    continue

                sentiment_count = int(len(sentiment_group))
                sentiment_total = max(1, int(sentiment_totals.get(sentiment, 0)))
                example_rows = (
                    sentiment_group.assign(
                        _content_length=sentiment_group["content"].str.len()
                    )
                    .sort_values("_content_length", ascending=False)
                    .head(3)
                )
                comments = [
                    str(value).strip()
                    for value in example_rows["content"].tolist()
                    if str(value).strip()
                ]
                platforms = [
                    str(value).strip().lower() or "lainnya"
                    for value in example_rows["platform"].tolist()
                ]

                topic_rows.append(
                    {
                        "sentiment": sentiment,
                        "topik": topic_name,
                        "keywords": keywords,
                        "topic_rank": topic_rank,
                        "jumlah_komentar": sentiment_count,
                        "total_topik": topic_total,
                        "persentase_sentimen": sentiment_count / sentiment_total * 100.0,
                        "persentase_topik": topic_percentage,
                        "sentimen_dominan": dominant_sentiment,
                        "contoh_komentar": "|||".join(comments),
                        "contoh_platform": "|||".join(platforms[: len(comments)]),
                    }
                )

        topics = pd.DataFrame(topic_rows, columns=topic_columns)
        return top_words, topics
    except Exception as exc:
        st.error(f"Fallback Analisis Topik IndiBiz tidak dapat dibangun: {exc}")
        return (
            pd.DataFrame(columns=top_word_columns),
            pd.DataFrame(columns=topic_columns),
        )


def _load_indibiz_runtime_outputs() -> tuple[pd.DataFrame, pd.DataFrame]:
    """Ambil fallback turunan IndiBiz berdasarkan versi file sentimen aktif."""
    try:
        top_words, topics = _build_indibiz_runtime_outputs_cached(
            get_sentiment_file_signature("IndiBiz")
        )
        return top_words.copy(), topics.copy()
    except Exception as exc:
        st.error(f"Data turunan Analisis Topik IndiBiz belum dapat disiapkan: {exc}")
        return (
            pd.DataFrame(columns=["sentiment", "rank", "kata", "frekuensi"]),
            pd.DataFrame(
                columns=[
                    "sentiment",
                    "topik",
                    "keywords",
                    "topic_rank",
                    "jumlah_komentar",
                    "total_topik",
                    "persentase_sentimen",
                    "persentase_topik",
                    "sentimen_dominan",
                    "contoh_komentar",
                    "contoh_platform",
                ]
            ),
        )


def _load_indibiz_wordcloud_output() -> dict[str, bytes | None]:
    """Muat tiga PNG WordCloud IndiBiz tanpa membuat halaman berhenti saat file hilang."""
    results: dict[str, bytes | None] = {}
    missing_labels: list[str] = []

    for sentiment in SENTIMENT_ORDER:
        path = INDIBIZ_WORDCLOUD_FILES[sentiment]
        if not path.is_file():
            results[sentiment] = None
            missing_labels.append(INDIBIZ_SENTIMENT_LABELS[sentiment])
            continue

        try:
            results[sentiment] = _load_indibiz_wordcloud_cached(
                str(path),
                _indibiz_file_signature(path),
            )
        except Exception as exc:
            st.error(
                f"Gambar WordCloud IndiBiz sentimen {INDIBIZ_SENTIMENT_LABELS[sentiment]} tidak dapat dibaca: {exc}"
            )
            results[sentiment] = None

    if len(missing_labels) == len(SENTIMENT_ORDER):
        st.info(
            "WordCloud IndiBiz belum tersedia. Jalankan dulu pipeline Colab untuk IndiBiz agar menghasilkan tiga file PNG terpisah: positif, netral, dan negatif."
        )
    elif missing_labels:
        daftar = ", ".join(missing_labels)
        st.info(
            f"Sebagian WordCloud IndiBiz belum lengkap. File PNG yang belum tersedia: {daftar}."
        )

    return results


def _load_indibiz_top_words_output() -> pd.DataFrame:
    """Muat dan rapikan output Top 15 Kata IndiBiz."""
    path = INDIBIZ_OUTPUT_FILES["top_kata"]
    if not path.is_file():
        runtime_top_words, _ = _load_indibiz_runtime_outputs()
        if not runtime_top_words.empty:
            return runtime_top_words
        st.info(
            "Data Top 15 Kata IndiBiz belum dapat dibentuk karena data sentimen "
            "IndiBiz belum tersedia."
        )
        return pd.DataFrame(columns=["sentiment", "rank", "kata", "frekuensi"])

    try:
        dataframe = _load_indibiz_csv_cached(
            str(path),
            _indibiz_file_signature(path),
            ("sentiment", "rank", "kata", "frekuensi"),
        ).copy()
        dataframe["sentiment"] = _normalize_indibiz_sentiment(
            dataframe["sentiment"]
        )
        dataframe["rank"] = pd.to_numeric(dataframe["rank"], errors="coerce")
        dataframe["frekuensi"] = pd.to_numeric(
            dataframe["frekuensi"], errors="coerce"
        )
        dataframe["kata"] = dataframe["kata"].fillna("").astype(str).str.strip()
        dataframe = dataframe[
            dataframe["sentiment"].isin(SENTIMENT_ORDER)
            & dataframe["kata"].ne("")
            & dataframe["frekuensi"].notna()
        ].copy()
        dataframe["frekuensi"] = dataframe["frekuensi"].clip(lower=0).astype(int)
        return dataframe.sort_values(
            ["sentiment", "rank", "frekuensi"],
            ascending=[True, True, False],
            na_position="last",
        ).reset_index(drop=True)
    except Exception as exc:
        st.error(f"Data Top 15 Kata IndiBiz tidak dapat dibaca: {exc}")
        return pd.DataFrame(columns=["sentiment", "rank", "kata", "frekuensi"])


def _load_indibiz_topic_output() -> pd.DataFrame:
    """Muat dan rapikan output topik IndiBiz, termasuk detail opsional untuk kartu Top 5."""
    path = INDIBIZ_OUTPUT_FILES["top_topic"]
    base_columns = [
        "sentiment",
        "topik",
        "keywords",
        "topic_rank",
        "jumlah_komentar",
        "total_topik",
        "persentase_sentimen",
        "persentase_topik",
        "sentimen_dominan",
        "contoh_komentar",
        "contoh_platform",
    ]
    if not path.is_file():
        _, runtime_topics = _load_indibiz_runtime_outputs()
        if not runtime_topics.empty:
            return runtime_topics
        st.info(
            "Data topik IndiBiz belum dapat dibentuk karena data sentimen "
            "IndiBiz belum tersedia."
        )
        return pd.DataFrame(columns=base_columns)

    try:
        dataframe = _load_indibiz_csv_cached(
            str(path),
            _indibiz_file_signature(path),
            ("sentiment", "topik", "keywords"),
        ).copy()
        dataframe["sentiment"] = _normalize_indibiz_sentiment(
            dataframe["sentiment"]
        )
        dataframe["topik"] = dataframe["topik"].fillna("").astype(str).str.strip()
        dataframe["keywords"] = (
            dataframe["keywords"].fillna("").astype(str).str.strip()
        )

        optional_text = [
            "sentimen_dominan",
            "contoh_komentar",
            "contoh_platform",
        ]
        for column in optional_text:
            if column not in dataframe.columns:
                dataframe[column] = ""
            dataframe[column] = dataframe[column].fillna("").astype(str).str.strip()

        if "sentimen_dominan" in dataframe.columns:
            dataframe["sentimen_dominan"] = _normalize_indibiz_sentiment(
                dataframe["sentimen_dominan"]
            )

        optional_numeric = [
            "topic_rank",
            "jumlah_komentar",
            "total_topik",
            "persentase_sentimen",
            "persentase_topik",
        ]
        for column in optional_numeric:
            if column not in dataframe.columns:
                dataframe[column] = pd.NA
            dataframe[column] = pd.to_numeric(dataframe[column], errors="coerce")

        dataframe = dataframe[
            dataframe["sentiment"].isin(SENTIMENT_ORDER)
            & dataframe["topik"].ne("")
        ].copy()

        # File lama hanya berisi tiga kolom. Beri urutan stabil agar kartu Top 5
        # tetap dapat ditampilkan tanpa mengarang jumlah komentar.
        if dataframe["topic_rank"].isna().all():
            topic_order = {
                topic: index + 1
                for index, topic in enumerate(
                    dict.fromkeys(dataframe["topik"].astype(str).tolist())
                )
            }
            dataframe["topic_rank"] = dataframe["topik"].map(topic_order)

        return dataframe.sort_values(
            ["topic_rank", "total_topik", "jumlah_komentar"],
            ascending=[True, False, False],
            na_position="last",
        ).reset_index(drop=True)
    except Exception as exc:
        st.error(f"Data topik IndiBiz tidak dapat dibaca: {exc}")
        return pd.DataFrame(columns=base_columns)

def _render_indibiz_output_summary(
    wordcloud_map: dict[str, bytes | None],
    top_words: pd.DataFrame,
    topics: pd.DataFrame,
) -> None:
    """Render empat kartu status output Colab IndiBiz."""
    sentiment_count = int(top_words["sentiment"].nunique()) if not top_words.empty else 0
    topic_count = int(topics["topik"].nunique()) if not topics.empty else 0
    wordcloud_ready = sum(1 for value in wordcloud_map.values() if value is not None)
    files_ready = wordcloud_ready + int(not top_words.empty) + int(not topics.empty)
    dominant_word = "—"
    if not top_words.empty:
        dominant_row = top_words.sort_values("frekuensi", ascending=False).iloc[0]
        dominant_word = str(dominant_row["kata"])
        if len(dominant_word) > 24:
            dominant_word = dominant_word[:22] + "…"

    st.markdown(
        f"""
        <div class="topic-v8-stat-row">
            <div class="topic-v8-stat"><div class="topic-v8-stat-label">Output tersedia</div><div class="topic-v8-stat-value">{files_ready}/5</div></div>
            <div class="topic-v8-stat"><div class="topic-v8-stat-label">WordCloud siap</div><div class="topic-v8-stat-value">{wordcloud_ready}/3</div></div>
            <div class="topic-v8-stat"><div class="topic-v8-stat-label">Topik LDA</div><div class="topic-v8-stat-value">{topic_count}</div></div>
            <div class="topic-v8-stat"><div class="topic-v8-stat-label">Kata teratas</div><div class="topic-v8-stat-value" style="font-size:1rem;line-height:1.35;margin-top:.5rem;">{escape(dominant_word)}</div></div>
        </div>
        """,
        unsafe_allow_html=True,
    )


@st.cache_data(show_spinner=False, max_entries=9)
def _prepare_indibiz_wordcloud_preview(image_bytes: bytes) -> bytes:
    """Optimalkan PNG WordCloud IndiBiz agar aman dirender di browser."""
    with Image.open(BytesIO(image_bytes)) as source_image:
        source_image.load()
        preview_image = source_image.convert("RGB")
        preview_image.thumbnail((1400, 900), Image.Resampling.LANCZOS)
        buffer = BytesIO()
        preview_image.save(buffer, format="PNG", optimize=True)
        return buffer.getvalue()


def _render_indibiz_wordcloud_preview(image_bytes: bytes, sentiment: str) -> bytes:
    """Render preview WordCloud IndiBiz melalui Matplotlib yang stabil."""
    del sentiment
    preview_bytes = _prepare_indibiz_wordcloud_preview(image_bytes)
    figure, axis = plt.subplots(figsize=(10, 5))  # FIX: rasio preview WordCloud 2:1
    try:
        with Image.open(BytesIO(preview_bytes)) as preview_image:
            figure.patch.set_alpha(0)
            axis.set_facecolor("none")
            axis.imshow(preview_image, interpolation="bilinear")
            axis.axis("off")
            figure.tight_layout(pad=0)
            _pyplot_aman(figure, use_container_width=True)
    finally:
        plt.close(figure)
    return preview_bytes


def _render_indibiz_wordcloud_output(wordcloud_map: dict[str, bytes | None]) -> None:
    """Render tiga WordCloud IndiBiz, satu PNG untuk setiap sentimen."""
    with st.container(border=True):
        st.markdown(
            '<span class="topic-v8-section-marker"></span>',
            unsafe_allow_html=True,
        )
        _section_header(
            "WordCloud per Sentimen IndiBiz",
            "Setiap sentimen memakai file PNG terpisah dari output final pipeline Colab, sehingga pola tampilannya konsisten dengan layanan IndiHome.",
        )

        columns = st.columns(3)
        for index, sentiment in enumerate(SENTIMENT_ORDER):
            label = INDIBIZ_SENTIMENT_LABELS[sentiment]
            with columns[index]:
                st.markdown(f"**{SENTIMENT_ICONS[sentiment]} {label}**")
                image_bytes = wordcloud_map.get(sentiment)
                if image_bytes is None:
                    st.info(
                        f"PNG WordCloud sentimen {label} belum tersedia. Jalankan pipeline Colab IndiBiz agar file ini dibuat."
                    )
                    continue

                try:
                    preview_bytes = _render_indibiz_wordcloud_preview(
                        image_bytes,
                        sentiment,
                    )
                    st.caption(
                        f"WordCloud sentimen {label} untuk percakapan IndiBiz."
                    )
                except Exception as exc:
                    st.error(
                        f"WordCloud sentimen {label} gagal dirender: {exc}"
                    )
                    continue

                st.download_button(
                    "Unduh PNG",
                    data=preview_bytes,
                    file_name=INDIBIZ_WORDCLOUD_FILES[sentiment].name,
                    mime="image/png",
                    key=f"topic_v8_indibiz_wc_{sentiment}",
                    use_container_width=True,
                )


def _indibiz_top_words_figure(
    dataframe: pd.DataFrame,
    sentiment: str,
) -> go.Figure:
    """Buat bar chart horizontal Top 15 Kata untuk satu sentimen IndiBiz."""
    subset = dataframe[dataframe["sentiment"].eq(sentiment)].copy()
    subset = subset.sort_values(
        ["rank", "frekuensi"],
        ascending=[True, False],
        na_position="last",
    ).head(15)

    if subset.empty:
        words = ["Tidak ada data"]
        frequencies = [0]
        ranks = [0]
    else:
        subset = subset.iloc[::-1]
        words = subset["kata"].astype(str).tolist()
        frequencies = subset["frekuensi"].astype(int).tolist()
        ranks = (
            subset["rank"].fillna(0).astype(int).tolist()
            if "rank" in subset.columns
            else [0] * len(subset)
        )

    customdata = [[rank, word] for rank, word in zip(ranks, words)]
    figure = go.Figure(
        go.Bar(
            x=frequencies,
            y=words,
            orientation="h",
            marker={"color": INDIBIZ_SENTIMENT_COLORS[sentiment]},
            customdata=customdata,
            hovertemplate=(
                "<b>%{customdata[1]}</b><br>"
                "Peringkat: %{customdata[0]}<br>"
                "Frekuensi: %{x:,}<extra></extra>"
            ),
        )
    )
    figure.update_layout(
        height=max(390, 34 * len(words) + 115),
        margin={"l": 100, "r": 36, "t": 24, "b": 52},
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font={"family": "Inter", "color": "#EDEDED", "size": 12},
        xaxis={
            "title": {"text": "Frekuensi", "standoff": 10},
            "gridcolor": "rgba(255,255,255,0.08)",
            "zeroline": False,
        },
        yaxis={"title": "", "automargin": True},
        showlegend=False,
        bargap=0.20,
        hoverlabel={
            "bgcolor": "#171717",
            "bordercolor": "#343434",
            "font_color": "#FFFFFF",
        },
    )
    return figure


def _render_indibiz_top_words_output(
    top_words: pd.DataFrame,
    sentiment_filter: str,
) -> None:
    """Render bar chart Top 15 Kata IndiBiz secara terpisah per sentimen."""
    with st.container(border=True):
        st.markdown(
            '<span class="topic-v8-section-marker"></span>',
            unsafe_allow_html=True,
        )
        _section_header(
            "Top 15 Kata IndiBiz",
            "Setiap tab memakai warna sentimen yang konsisten: hijau, biru, dan merah.",
        )
        if top_words.empty:
            return

        sentiments = (
            SENTIMENT_ORDER
            if sentiment_filter == "all"
            else [sentiment_filter]
        )
        tabs = st.tabs([INDIBIZ_SENTIMENT_LABELS[item] for item in sentiments])
        for tab, sentiment in zip(tabs, sentiments):
            with tab:
                _plotly_chart(
                    _indibiz_top_words_figure(top_words, sentiment),
                    key=f"topic_v8_indibiz_top_words_{sentiment}",
                )


def _split_indibiz_examples(value: Any) -> list[str]:
    """Pisahkan contoh komentar atau platform yang disimpan dengan pemisah tiga pipa."""
    text = str(value or "").strip()
    if not text:
        return []
    return [item.strip() for item in text.split("|||") if item.strip()]


def _build_indibiz_topic_cards(
    topics: pd.DataFrame,
    sentiment_filter: str,
) -> list[dict[str, Any]]:
    """Bangun maksimal lima kartu topik dari output Colab, kompatibel dengan CSV lama."""
    if topics is None or topics.empty:
        return []

    dataframe = topics.copy()
    if sentiment_filter != "all":
        dataframe = dataframe[dataframe["sentiment"].eq(sentiment_filter)].copy()
    if dataframe.empty:
        return []

    topic_order = list(dict.fromkeys(dataframe["topik"].astype(str).tolist()))
    records: list[dict[str, Any]] = []

    for fallback_rank, topic_name in enumerate(topic_order, start=1):
        group = dataframe[dataframe["topik"].astype(str).eq(topic_name)].copy()
        if group.empty:
            continue

        numeric_rank = pd.to_numeric(group.get("topic_rank"), errors="coerce")
        rank = int(numeric_rank.dropna().min()) if numeric_rank.notna().any() else fallback_rank

        sentiment_counts = {sentiment: 0 for sentiment in SENTIMENT_ORDER}
        if "jumlah_komentar" in group.columns:
            for sentiment in SENTIMENT_ORDER:
                values = pd.to_numeric(
                    group.loc[group["sentiment"].eq(sentiment), "jumlah_komentar"],
                    errors="coerce",
                ).fillna(0)
                sentiment_counts[sentiment] = int(values.sum())

        total_from_rows = sum(sentiment_counts.values())
        total_candidates = pd.to_numeric(
            group.get("total_topik"), errors="coerce"
        ).dropna()
        if sentiment_filter == "all" and not total_candidates.empty:
            total = max(total_from_rows, int(total_candidates.max()))
        else:
            total = total_from_rows

        if total_from_rows > 0:
            dominant = max(
                SENTIMENT_ORDER,
                key=lambda sentiment: sentiment_counts[sentiment],
            )
        else:
            dominant_values = [
                value
                for value in group.get("sentimen_dominan", pd.Series(dtype=str)).astype(str)
                if value in SENTIMENT_ORDER
            ]
            if dominant_values:
                dominant = dominant_values[0]
            else:
                sentiment_values = [
                    value for value in group["sentiment"].astype(str)
                    if value in SENTIMENT_ORDER
                ]
                dominant = sentiment_values[0] if sentiment_values else "neutral"

        keywords: list[str] = []
        for value in group.get("keywords", pd.Series(dtype=str)).tolist():
            for keyword in _split_indibiz_keywords(value):
                if keyword not in keywords:
                    keywords.append(keyword)

        examples: dict[str, list[dict[str, str]]] = {
            sentiment: [] for sentiment in SENTIMENT_ORDER
        }
        for _, row in group.iterrows():
            sentiment = str(row.get("sentiment", ""))
            if sentiment not in SENTIMENT_ORDER:
                continue
            comments = _split_indibiz_examples(row.get("contoh_komentar", ""))
            platforms = _split_indibiz_examples(row.get("contoh_platform", ""))
            for index, comment in enumerate(comments):
                if not comment:
                    continue
                platform = platforms[index] if index < len(platforms) else "lainnya"
                examples[sentiment].append(
                    {"content": comment, "platform": platform}
                )

        topic_percentage_values = pd.to_numeric(
            group.get("persentase_topik"), errors="coerce"
        ).dropna()
        topic_percentage = (
            float(topic_percentage_values.max())
            if not topic_percentage_values.empty
            else None
        )

        records.append(
            {
                "rank": rank,
                "topik": topic_name,
                "total": total,
                "topic_percentage": topic_percentage,
                "dominant": dominant,
                "sentiment_counts": sentiment_counts,
                "keywords": keywords[:12],
                "examples": examples,
            }
        )

    if any(record["total"] > 0 for record in records):
        records.sort(key=lambda item: (item["rank"], -item["total"], item["topik"]))
    else:
        records.sort(key=lambda item: (item["rank"], item["topik"]))
    return records[:5]


def _render_indibiz_example_comments(
    examples: list[dict[str, str]],
    sentiment: str,
) -> None:
    """Render contoh komentar IndiBiz dari file output Colab."""
    if not examples:
        st.caption(
            "Contoh komentar belum tersedia pada file output ini. "
            "Jalankan notebook generator terbaru agar detail komentar ikut disimpan."
        )
        return

    label = INDIBIZ_SENTIMENT_LABELS[sentiment]
    for index, item in enumerate(examples[:3], start=1):
        platform_raw = str(item.get("platform", "lainnya")).strip().lower()
        platform = PLATFORM_LABELS.get(platform_raw, platform_raw.title() or "Lainnya")
        content = escape(str(item.get("content", "—")))
        st.markdown(
            f"""
            <article class="topic-v8-comment-card topic-v8-comment-card-{sentiment}">
                <div class="topic-v8-comment-meta">
                    <span>Contoh {index}</span><span>•</span>
                    <span>{escape(platform)}</span><span>•</span>
                    <span>{escape(label)}</span>
                </div>
                <div class="topic-v8-comment-text">{content}</div>
            </article>
            """,
            unsafe_allow_html=True,
        )


def _render_indibiz_topic_cards_output(
    topics: pd.DataFrame,
    sentiment_filter: str,
) -> None:
    """Render bagian Top 5 Topik IndiBiz dengan expander seperti layanan IndiHome."""
    with st.container(border=True):
        st.markdown(
            '<span class="topic-v8-section-marker"></span>',
            unsafe_allow_html=True,
        )
        _section_header(
            "Top 5 Topik",
            "Lima kelompok topik teratas berasal dari output pipeline Colab IndiBiz. Buka setiap kartu untuk melihat kata kunci, komposisi sentimen, dan contoh komentar yang tersedia.",
        )

        records = _build_indibiz_topic_cards(topics, sentiment_filter)
        if not records:
            st.info("Belum ada topik IndiBiz yang dapat ditampilkan pada filter aktif.")
            return

        grand_total = sum(record["total"] for record in records)
        has_detail_counts = grand_total > 0

        for display_index, record in enumerate(records, start=1):
            topic_name = str(record["topik"])
            total = int(record["total"])
            dominant = str(record["dominant"])
            dominant_label = INDIBIZ_SENTIMENT_LABELS.get(dominant, "Netral")
            keywords = ", ".join(record["keywords"]) or "Belum tersedia"

            if total > 0:
                expander_label = (
                    f"{display_index}. {topic_name} · {_format_number(total)} komentar · "
                    f"Dominan {dominant_label}"
                )
            else:
                expander_label = (
                    f"{display_index}. {topic_name} · Dominan {dominant_label}"
                )

            with st.expander(expander_label, expanded=False):
                fallback_percentage = (total / grand_total * 100.0) if grand_total > 0 else 0.0
                percentage = (
                    float(record.get("topic_percentage"))
                    if record.get("topic_percentage") is not None
                    else fallback_percentage
                )
                percentage_label = (
                    "dari data IndiBiz"
                    if record.get("topic_percentage") is not None
                    else "dari Top 5"
                )
                total_text = (
                    f"{_format_number(total)} komentar · {percentage:.1f}% {percentage_label}"
                    if total > 0
                    else "Ringkasan berdasarkan topik dan kata kunci output Colab"
                )
                st.markdown(
                    f"""
                    <div class="topic-v8-topic-overview">
                        <div class="topic-v8-topic-overview-head">
                            <div>
                                <div class="topic-v8-topic-overview-title">{display_index}. {escape(topic_name)}</div>
                                <div class="topic-v8-topic-overview-meta">
                                    {escape(total_text)}<br>
                                    Kata kunci: {escape(keywords)}
                                </div>
                            </div>
                            <span class="topic-v8-chip topic-v8-chip-{dominant}">{escape(dominant_label)}</span>
                        </div>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )

                sentiment_counts = record["sentiment_counts"]
                if has_detail_counts and total > 0:
                    sentiment_stats = "".join(
                        _sentiment_stat_html(
                            sentiment,
                            int(sentiment_counts[sentiment]),
                            total,
                        )
                        for sentiment in ["negative", "neutral", "positive"]
                    )
                    st.markdown(
                        f'<div class="topic-v8-sentiment-grid">{sentiment_stats}</div>',
                        unsafe_allow_html=True,
                    )

                active_sentiments = [
                    sentiment
                    for sentiment in ["negative", "neutral", "positive"]
                    if record["examples"].get(sentiment)
                    or sentiment_counts.get(sentiment, 0) > 0
                ]
                if not active_sentiments:
                    st.caption(
                        "File output saat ini belum memuat jumlah dan contoh komentar. "
                        "Kartu topik tetap ditampilkan dari nama topik dan kata kuncinya."
                    )
                    continue

                if len(active_sentiments) == 1:
                    sentiment = active_sentiments[0]
                    st.markdown(
                        f"**Contoh komentar {INDIBIZ_SENTIMENT_LABELS[sentiment]}**"
                    )
                    _render_indibiz_example_comments(
                        record["examples"].get(sentiment, []),
                        sentiment,
                    )
                else:
                    tabs = st.tabs(
                        [
                            f"{INDIBIZ_SENTIMENT_LABELS[sentiment]} · "
                            f"{_format_number(int(sentiment_counts.get(sentiment, 0)))}"
                            for sentiment in active_sentiments
                        ]
                    )
                    for tab, sentiment in zip(tabs, active_sentiments):
                        with tab:
                            _render_indibiz_example_comments(
                                record["examples"].get(sentiment, []),
                                sentiment,
                            )


def _split_indibiz_keywords(value: Any) -> list[str]:
    """Pisahkan daftar keyword dari format koma, titik koma, atau karakter pipa."""
    text = str(value or "").strip()
    if not text:
        return []
    return [
        item.strip().strip("[](){}'\"")
        for item in re.split(r"[,;|]", text)
        if item.strip().strip("[](){}'\"")
    ]


def _wrap_topic_label(value: str, width: int = 22) -> str:
    """Bungkus nama topik agar label sumbu heatmap tetap terbaca."""
    words = str(value).split()
    if not words:
        return "Topik"
    lines: list[str] = []
    current = ""
    for word in words:
        candidate = f"{current} {word}".strip()
        if current and len(candidate) > width:
            lines.append(current)
            current = word
        else:
            current = candidate
    if current:
        lines.append(current)
    return "<br>".join(lines)


def _indibiz_topic_rules_for_heatmap(
    topics: pd.DataFrame,
) -> tuple[tuple[str, tuple[str, ...]], ...]:
    """Bentuk aturan topik stabil dari CSV output Colab untuk agregasi platform."""
    if topics.empty:
        return tuple()

    working = topics.copy()
    working["topik"] = working["topik"].fillna("Topik").astype(str).str.strip()
    if "topic_rank" not in working.columns:
        working["topic_rank"] = pd.NA
    working["topic_rank"] = pd.to_numeric(
        working["topic_rank"], errors="coerce"
    )

    records: list[tuple[int, str, tuple[str, ...]]] = []
    for topic_name, group in working.groupby("topik", sort=False, dropna=False):
        topic = str(topic_name).strip() or "Topik"
        ranks = group["topic_rank"].dropna()
        rank = int(ranks.min()) if not ranks.empty else 999

        keywords: list[str] = []
        for value in group.get("keywords", pd.Series(dtype=str)).tolist():
            for keyword in _split_indibiz_keywords(value):
                normalized = " ".join(str(keyword).lower().split())
                if normalized and normalized not in keywords:
                    keywords.append(normalized)
        records.append((rank, topic, tuple(keywords)))

    records.sort(
        key=lambda item: (
            item[1].strip().lower() == "topik lainnya",
            item[0],
            item[1].lower(),
        )
    )
    return tuple((topic, keywords) for _, topic, keywords in records[:5])


def _indibiz_keyword_regex(keywords: tuple[str, ...]) -> str:
    """Buat regex aman untuk mencocokkan kata atau frasa topik."""
    patterns: list[str] = []
    for keyword in keywords:
        clean_keyword = " ".join(str(keyword).lower().split())
        if not clean_keyword:
            continue
        escaped_parts = [re.escape(part) for part in clean_keyword.split()]
        phrase = r"\s+".join(escaped_parts)
        patterns.append(rf"(?<!\w){phrase}(?!\w)")
    return "|".join(patterns)


@st.cache_data(show_spinner=False, max_entries=12)
def _build_indibiz_platform_topic_matrix_cached(
    sentiment_file_signature: str,
    topic_rules: tuple[tuple[str, tuple[str, ...]], ...],
    platforms: tuple[str, ...],
    sentiment_filter: str,
) -> pd.DataFrame:
    """Bangun matriks platform x topik dari data sentimen IndiBiz yang tersedia."""
    del sentiment_file_signature
    source = load_topic_data("IndiBiz")

    topic_order = [topic for topic, _ in topic_rules]
    platform_order = list(platforms) if platforms else ["twitter", "instagram", "tiktok"]
    if source.empty or not topic_order:
        return pd.DataFrame(0, index=platform_order, columns=topic_order, dtype=int)

    working = source.copy()
    if "platform" not in working.columns:
        working["platform"] = "lainnya"
    if "content" not in working.columns:
        working["content"] = ""
    if "predicted_sentiment" not in working.columns:
        working["predicted_sentiment"] = "neutral"

    working["platform"] = working["platform"].map(_normalize_platform)
    working["content"] = (
        working["content"].fillna("").astype(str).str.lower().str.strip()
    )
    working["predicted_sentiment"] = (
        working["predicted_sentiment"]
        .fillna("neutral")
        .astype(str)
        .str.lower()
        .str.strip()
        .str.lstrip("'")
        .replace({"positif": "positive", "netral": "neutral", "negatif": "negative"})
    )
    working = working[working["content"].ne("")].copy()

    if platforms:
        working = working[working["platform"].isin(platforms)].copy()
    if sentiment_filter != "all":
        working = working[
            working["predicted_sentiment"].eq(sentiment_filter)
        ].copy()

    if working.empty:
        return pd.DataFrame(0, index=platform_order, columns=topic_order, dtype=int)

    fallback_topic = next(
        (
            topic
            for topic in topic_order
            if topic.strip().lower() == "topik lainnya"
        ),
        topic_order[-1],
    )
    scored_topics = [
        (topic, keywords)
        for topic, keywords in topic_rules
        if topic != fallback_topic and keywords
    ]

    score_columns: dict[str, pd.Series] = {}
    for topic, keywords in scored_topics:
        pattern = _indibiz_keyword_regex(keywords)
        if pattern:
            score_columns[topic] = working["content"].str.count(
                pattern,
                flags=re.IGNORECASE,
            )

    if score_columns:
        scores = pd.DataFrame(score_columns, index=working.index).fillna(0)
        best_topic = scores.idxmax(axis=1)
        best_score = scores.max(axis=1)
        working["topic_heatmap"] = best_topic.where(
            best_score.gt(0), fallback_topic
        )
    else:
        working["topic_heatmap"] = fallback_topic

    matrix = pd.crosstab(
        working["platform"],
        working["topic_heatmap"],
    )
    matrix = matrix.reindex(
        index=platform_order,
        columns=topic_order,
        fill_value=0,
    )
    return matrix.fillna(0).astype(int)


def _build_indibiz_platform_topic_matrix(
    topics: pd.DataFrame,
    platforms: tuple[str, ...],
    sentiment_filter: str,
) -> tuple[pd.DataFrame, list[str]]:
    """Siapkan matriks dan urutan topik IndiBiz untuk heatmap interaktif."""
    rules = _indibiz_topic_rules_for_heatmap(topics)
    topic_order = [topic for topic, _ in rules]
    try:
        matrix = _build_indibiz_platform_topic_matrix_cached(
            get_sentiment_file_signature("IndiBiz"),
            rules,
            tuple(platforms),
            sentiment_filter,
        )
        return matrix, topic_order
    except Exception as exc:
        st.error(f"Distribusi topik IndiBiz per platform belum dapat dihitung: {exc}")
        platform_order = list(platforms) if platforms else ["twitter", "instagram", "tiktok"]
        return (
            pd.DataFrame(0, index=platform_order, columns=topic_order, dtype=int),
            topic_order,
        )


def _indibiz_topic_heatmap_figure(dataframe: pd.DataFrame) -> go.Figure:
    """Buat heatmap sentimen x topik dengan metrik dan urutan yang konsisten."""
    working = dataframe.copy()
    working["topik"] = working["topik"].fillna("Topik").astype(str).str.strip()

    has_comment_counts = (
        "jumlah_komentar" in working.columns
        and pd.to_numeric(
            working["jumlah_komentar"], errors="coerce"
        ).fillna(0).sum() > 0
    )

    # Urutkan topik mengikuti peringkat output. Jika peringkat tidak tersedia,
    # gunakan jumlah komentar terbesar. Topik Lainnya selalu ditempatkan terakhir.
    topic_names = list(dict.fromkeys(working["topik"].tolist()))
    if "topic_rank" in working.columns:
        rank_map = (
            working.assign(
                _topic_rank=pd.to_numeric(
                    working["topic_rank"], errors="coerce"
                )
            )
            .groupby("topik", dropna=False)["_topic_rank"]
            .min()
            .to_dict()
        )
        topic_names.sort(
            key=lambda topic: (
                pd.isna(rank_map.get(topic)),
                rank_map.get(topic, float("inf")),
                topic.lower(),
            )
        )
    elif has_comment_counts:
        topic_total_map = (
            working.assign(
                _jumlah=pd.to_numeric(
                    working["jumlah_komentar"], errors="coerce"
                ).fillna(0)
            )
            .groupby("topik", dropna=False)["_jumlah"]
            .sum()
            .to_dict()
        )
        topic_names.sort(
            key=lambda topic: (-float(topic_total_map.get(topic, 0)), topic.lower())
        )

    topic_names = [
        topic for topic in topic_names
        if topic.strip().lower() != "topik lainnya"
    ] + [
        topic for topic in topic_names
        if topic.strip().lower() == "topik lainnya"
    ]

    sentiments = [
        item for item in SENTIMENT_ORDER
        if item in set(working["sentiment"])
    ]

    z_values: list[list[int]] = []
    keyword_values: list[list[str]] = []
    percentage_values: list[list[float]] = []

    grand_total = 0
    if has_comment_counts:
        grand_total = int(
            pd.to_numeric(
                working["jumlah_komentar"], errors="coerce"
            ).fillna(0).sum()
        )

    for sentiment in sentiments:
        sentiment_rows = working[working["sentiment"].eq(sentiment)]
        score_by_topic: dict[str, int] = {}
        keyword_by_topic: dict[str, str] = {}

        for _, row in sentiment_rows.iterrows():
            topic = str(row["topik"])
            keywords = _split_indibiz_keywords(row.get("keywords", ""))
            if has_comment_counts:
                raw_score = pd.to_numeric(
                    pd.Series([row.get("jumlah_komentar")]),
                    errors="coerce",
                ).fillna(0).iloc[0]
                score = max(int(raw_score), 0)
                score_by_topic[topic] = score_by_topic.get(topic, 0) + score
            else:
                score_by_topic[topic] = max(
                    score_by_topic.get(topic, 0),
                    len(keywords),
                )
            keyword_by_topic[topic] = (
                ", ".join(keywords) or "Tidak ada kata kunci"
            )

        row_values = [score_by_topic.get(topic, 0) for topic in topic_names]
        z_values.append(row_values)
        keyword_values.append([
            keyword_by_topic.get(topic, "Tidak ada pada sentimen ini")
            for topic in topic_names
        ])
        percentage_values.append([
            (value / grand_total * 100.0) if grand_total > 0 else 0.0
            for value in row_values
        ])

    max_score = max((max(row) for row in z_values if row), default=1)
    metric_label = "Jumlah komentar" if has_comment_counts else "Jumlah kata kunci"
    colorbar_title = (
        "Jumlah<br>komentar" if has_comment_counts else "Jumlah<br>kata kunci"
    )
    wrapped_topics = [_wrap_topic_label(topic, width=18) for topic in topic_names]

    customdata: list[list[list[Any]]] = []
    for sentiment_index, _ in enumerate(sentiments):
        customdata.append([
            [
                topic_names[topic_index],
                keyword_values[sentiment_index][topic_index],
                percentage_values[sentiment_index][topic_index],
            ]
            for topic_index in range(len(topic_names))
        ])

    figure = go.Figure(
        go.Heatmap(
            z=z_values,
            x=wrapped_topics,
            y=[INDIBIZ_SENTIMENT_LABELS[item] for item in sentiments],
            customdata=customdata,
            zmin=0,
            zmax=max_score,
            colorscale=[
                [0.00, "#171717"],
                [0.08, "#321819"],
                [0.45, "#8E2424"],
                [1.00, "#EF3B36"],
            ],
            colorbar={
                "title": {"text": colorbar_title, "side": "top"},
                "tickfont": {"color": "#D0D0D0", "size": 11},
                "thickness": 18,
                "len": 0.76,
                "x": 1.02,
                "outlinecolor": "rgba(255,255,255,0.18)",
                "outlinewidth": 1,
            },
            xgap=2,
            ygap=2,
            hovertemplate=(
                "<b>%{customdata[0]}</b><br>"
                "Sentimen: %{y}<br>"
                f"{metric_label}: %{{z:,}}<br>"
                "Proporsi pada heatmap aktif: %{customdata[2]:.2f}%<br>"
                "Kata kunci: %{customdata[1]}<extra></extra>"
            ),
        )
    )
    figure.update_layout(
        height=520 if len(sentiments) > 1 else 390,
        margin={"l": 92, "r": 112, "t": 32, "b": 145},
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font={"family": "Inter", "color": "#EDEDED", "size": 12},
        xaxis={
            "title": {"text": "Topik", "standoff": 16},
            "tickangle": 0,
            "side": "bottom",
            "automargin": True,
            "tickfont": {"size": 11, "color": "#E5E5E5"},
            "categoryorder": "array",
            "categoryarray": wrapped_topics,
            "gridcolor": "rgba(255,255,255,0.04)",
            "fixedrange": True,
        },
        yaxis={
            "title": {"text": "Sentimen", "standoff": 14},
            "automargin": True,
            "tickfont": {"size": 12, "color": "#E5E5E5"},
            "categoryorder": "array",
            "categoryarray": [
                INDIBIZ_SENTIMENT_LABELS[item] for item in sentiments
            ],
            "autorange": "reversed",
            "gridcolor": "rgba(255,255,255,0.04)",
            "fixedrange": True,
        },
        hoverlabel={
            "bgcolor": "#171717",
            "bordercolor": "#3A3A3A",
            "font_color": "#FFFFFF",
            "font_size": 12,
        },
    )
    return figure

@st.cache_data(show_spinner=False, max_entries=12)
def _build_indibiz_frequency_table_cached(
    sentiment_file_signature: str,
    platforms: tuple[str, ...],
    sentiment_filter: str,
    show_brand: bool,
) -> pd.DataFrame:
    """Bangun tabel frekuensi kata lengkap IndiBiz dari data sentimen terfilter."""
    del sentiment_file_signature
    source = load_topic_data("IndiBiz")
    if source.empty:
        return pd.DataFrame(
            columns=["Rank", "Kata", "Frekuensi", "Sentimen Dominan"]
        )

    working = source.copy()
    if "platform" not in working.columns:
        working["platform"] = "lainnya"
    if "content" not in working.columns:
        working["content"] = ""
    if "predicted_sentiment" not in working.columns:
        working["predicted_sentiment"] = "neutral"

    working["platform"] = working["platform"].map(_normalize_platform)
    working["content"] = (
        working["content"].fillna("").astype(str).str.strip()
    )
    working["predicted_sentiment"] = (
        working["predicted_sentiment"]
        .fillna("neutral")
        .astype(str)
        .str.lower()
        .str.strip()
        .str.lstrip("'")
        .replace(
            {"positif": "positive", "netral": "neutral", "negatif": "negative"}
        )
    )
    working = working[working["content"].ne("")].copy()

    if platforms:
        working = working[working["platform"].isin(platforms)].copy()
    if sentiment_filter != "all":
        working = working[
            working["predicted_sentiment"].eq(sentiment_filter)
        ].copy()

    if working.empty:
        return pd.DataFrame(
            columns=["Rank", "Kata", "Frekuensi", "Sentimen Dominan"]
        )

    frequency_map: dict[str, Counter[str]] = {}
    for sentiment in SENTIMENT_ORDER:
        texts = working.loc[
            working["predicted_sentiment"].eq(sentiment), "content"
        ].astype(str).tolist()
        frequency_map[sentiment] = _count_words_fast(
            texts,
            show_brand=show_brand,
        )

    combined = Counter()
    for counter in frequency_map.values():
        combined.update(counter)

    rows: list[dict[str, Any]] = []
    for rank, (word, count) in enumerate(combined.most_common(), start=1):
        sentiment_counts = {
            sentiment: int(frequency_map[sentiment].get(word, 0))
            for sentiment in SENTIMENT_ORDER
        }
        dominant = max(
            SENTIMENT_ORDER,
            key=lambda sentiment: (
                sentiment_counts[sentiment],
                {"negative": 2, "positive": 1, "neutral": 0}[sentiment],
            ),
        )
        rows.append(
            {
                "Rank": rank,
                "Kata": word,
                "Frekuensi": int(count),
                "Sentimen Dominan": SENTIMENT_LABELS_ID[dominant],
            }
        )

    return pd.DataFrame(
        rows,
        columns=["Rank", "Kata", "Frekuensi", "Sentimen Dominan"],
    )


def _build_indibiz_frequency_table(
    platforms: tuple[str, ...],
    sentiment_filter: str,
    show_brand: bool,
) -> pd.DataFrame:
    """Siapkan tabel frekuensi IndiBiz dengan cache dan fallback aman."""
    try:
        return _build_indibiz_frequency_table_cached(
            get_sentiment_file_signature("IndiBiz"),
            tuple(platforms),
            sentiment_filter,
            bool(show_brand),
        )
    except Exception as exc:
        st.error(f"Tabel Frekuensi Kata IndiBiz belum dapat dihitung: {exc}")
        return pd.DataFrame(
            columns=["Rank", "Kata", "Frekuensi", "Sentimen Dominan"]
        )


def _render_indibiz_topic_detail_output(
    topics: pd.DataFrame,
    sentiment_filter: str,
) -> None:
    """Render detail distribusi topik setelah tabel frekuensi kata IndiBiz."""
    if topics.empty:
        return

    filtered_topics = topics.copy()
    if sentiment_filter != "all":
        filtered_topics = filtered_topics[
            filtered_topics["sentiment"].eq(sentiment_filter)
        ].copy()
    if filtered_topics.empty:
        return

    detail_table = filtered_topics.rename(
        columns={
            "sentiment": "Sentimen",
            "topik": "Nama Topik",
            "keywords": "Kata Kunci",
        }
    ).copy()
    detail_table["Sentimen"] = detail_table["Sentimen"].map(
        INDIBIZ_SENTIMENT_LABELS
    )

    with st.expander("Lihat detail distribusi dan kata kunci setiap topik"):
        detail_columns = ["Sentimen", "Nama Topik"]
        if "jumlah_komentar" in filtered_topics.columns:
            detail_table["Jumlah Komentar"] = pd.to_numeric(
                filtered_topics["jumlah_komentar"], errors="coerce"
            ).fillna(0).astype(int)
            detail_columns.append("Jumlah Komentar")
        detail_columns.append("Kata Kunci")
        st.dataframe(
            detail_table[detail_columns],
            use_container_width=True,
            hide_index=True,
        )


def _render_indibiz_topic_heatmap_output(
    topics: pd.DataFrame,
    sentiment_filter: str,
    platforms: tuple[str, ...],
) -> None:
    """Render heatmap topik IndiBiz per platform dengan dua mode interaktif."""
    with st.container(border=True):
        st.markdown(
            '<span class="topic-v8-section-marker"></span>',
            unsafe_allow_html=True,
        )
        _section_header(
            "Heatmap Distribusi Topik IndiBiz",
            "Setiap sel menampilkan jumlah komentar untuk kombinasi platform dan topik. Gunakan tombol Jumlah komentar atau % per platform untuk mengganti mode tampilan.",
        )
        if topics.empty:
            return

        matrix, topic_order = _build_indibiz_platform_topic_matrix(
            topics,
            platforms=platforms,
            sentiment_filter=sentiment_filter,
        )
        if matrix.empty or not topic_order:
            st.info("Belum ada distribusi topik IndiBiz yang dapat ditampilkan.")
            return

        if int(matrix.to_numpy().sum()) <= 0:
            st.info(
                "Tidak ada komentar IndiBiz pada kombinasi platform dan sentimen yang dipilih."
            )

        heatmap_config = {
            "displaylogo": False,
            "responsive": True,
            "scrollZoom": False,
            "displayModeBar": True,
            "modeBarButtonsToRemove": [
                "select2d",
                "lasso2d",
                "autoScale2d",
            ],
            "toImageButtonOptions": {
                "format": "png",
                "filename": "heatmap_topik_indibiz",
                "height": 720,
                "width": 1400,
                "scale": 2,
            },
        }
        try:
            st.plotly_chart(
                _apply_topic_plotly_theme(_heatmap_figure(matrix, topic_order)),
                use_container_width=True,
                config=heatmap_config,
                key=f"topic_v8_indibiz_heatmap_platform_{sentiment_filter}",
            )
        except TypeError:
            st.plotly_chart(
                _apply_topic_plotly_theme(_heatmap_figure(matrix, topic_order)),
                use_container_width=True,
                config=heatmap_config,
            )



def _render_indibiz_outputs(
    sentiment_filter: str,
    platforms: tuple[str, ...],
    show_brand: bool,
) -> None:
    """Render seluruh output Analisis Topik IndiBiz secara lengkap."""
    wordcloud_map = _load_indibiz_wordcloud_output()
    top_words = _load_indibiz_top_words_output()
    topics = _load_indibiz_topic_output()
    frequency_table = _build_indibiz_frequency_table(
        platforms=platforms,
        sentiment_filter=sentiment_filter,
        show_brand=show_brand,
    )

    # Setiap bagian IndiBiz dirender secara terisolasi. Jika satu visualisasi
    # menghadapi data tidak valid, bagian lain tetap tampil dan halaman tidak
    # berubah menjadi satu kotak error besar.
    try:
        _render_indibiz_output_summary(
            wordcloud_map=wordcloud_map,
            top_words=top_words,
            topics=topics,
        )
    except Exception as exc:
        st.error(f"Ringkasan output IndiBiz belum dapat ditampilkan: {exc}")

    st.caption(
        "WordCloud IndiBiz memakai PNG output pipeline Colab. Top 15 Kata dan "
        "Top 5 Topik memakai CSV output jika tersedia; jika CSV turunan belum ada, "
        "dashboard membangunnya dari data sentimen IndiBiz yang aktif. Tabel "
        "Frekuensi Kata tetap mengikuti filter platform, sentimen, dan pengaturan "
        "nama brand."
    )

    indibiz_sections = [
        ("WordCloud", _render_indibiz_wordcloud_output, (wordcloud_map,)),
        ("Top 15 Kata", _render_indibiz_top_words_output, (top_words, sentiment_filter)),
        ("Top 5 Topik", _render_indibiz_topic_cards_output, (topics, sentiment_filter)),
        (
            "Heatmap Distribusi Topik",
            _render_indibiz_topic_heatmap_output,
            (topics, sentiment_filter, platforms),
        ),
        ("Tabel Frekuensi Kata", _render_frequency_table, (frequency_table, "IndiBiz")),
        ("Detail Distribusi Topik", _render_indibiz_topic_detail_output, (topics, sentiment_filter)),
    ]
    for section_name, render_function, arguments in indibiz_sections:
        try:
            render_function(*arguments)
        except Exception as exc:
            st.error(
                f"Bagian {section_name} IndiBiz belum dapat ditampilkan: {exc}"
            )


def render_topic_analysis() -> None:
    """Render halaman Analisis Topik lengkap."""
    action_loading_handle = None
    try:
        loading_label = st.session_state.pop(TOPIC_ACTION_LOADING_KEY, None)
        if loading_label:
            action_loading_handle = mulai_loading_aksi(str(loading_label))

        _inject_topic_css()

        _init_filter_state()
        initial_service = str(
            st.session_state.get(
                "topic_v8_draft_service",
                st.session_state["topic_v8_applied_service"],
            )
        )
        if initial_service not in LAYANAN_OPTIONS:
            initial_service = "IndiHome"
        _render_hero(_topic_data_source_label(initial_service), initial_service)

        layanan, platforms, sentiment_filter, max_words, show_brand, submitted = _render_controls()

        # Hero diperbarui secara alami pada rerun berikutnya. Badge sumber data juga
        # ditegaskan melalui caption tepat di bawah kontrol.
        data_source = _topic_data_source_label(layanan)
        st.caption(
            f"Sumber: {data_source} · Layanan: {layanan} · "
            f"Platform: {', '.join(PLATFORM_LABELS.get(item, item) for item in platforms) or 'Tidak ada'} · "
            f"Sentimen: {next((label for label, value in SENTIMENT_OPTIONS.items() if value == sentiment_filter), 'Semua')}"
        )

        if submitted:
            st.success("Filter berhasil diterapkan.", icon="✅")

        # Jangan gunakan spinner bawaan Streamlit. Semua proses filter dan
        # pembangunan visualisasi memakai overlay loading Telkom yang sama
        # dengan halaman lain agar pengalaman pengguna tetap konsisten.
        if action_loading_handle is None:
            action_loading_handle = mulai_loading_aksi(
                f"Menyiapkan analisis topik untuk {layanan}..."
            )

        # IndiBiz membaca tiga output final pipeline Colab. Jalur ini sengaja
        # dipisahkan agar dashboard tidak menghitung ulang WordCloud atau LDA.
        if layanan == "IndiBiz" and not bool(st.session_state.get("demo_mode", False)):
            _render_indibiz_outputs(
                sentiment_filter,
                tuple(platforms),
                show_brand,
            )
            return

        # Jalur IndiHome lama tetap dipertahankan tanpa perubahan analitik.
        file_signature = (
            f"demo-mode:{layanan}:v1"
            if bool(st.session_state.get("demo_mode", False))
            else get_sentiment_file_signature(layanan)
        )
        df, frequency_map, summary, matrix, frequency_table = _build_analysis_payload(
            layanan,
            tuple(platforms),
            sentiment_filter,
            show_brand,
            file_signature,
        )

        _render_summary_stats(df, summary)

        if df.empty:
            st.info("Tidak ada data untuk filter ini.")
            return

        _render_wordclouds(df, frequency_map, max_words, layanan)
        _render_top_words(frequency_map, layanan)
        _render_topic_cards(summary, df, layanan)
        _render_heatmap(matrix, summary, layanan)
        _render_frequency_table(frequency_table, layanan)

    except Exception as exc:
        st.error(f"Gagal memuat halaman Analisis Topik: {exc}")
    finally:
        selesaikan_loading_aksi(action_loading_handle)
