# pages/sentiment.py
# TAHAP 5 FASE 12 - WORDCLOUD DATA AKTUAL TANPA SAMPLING DAN TANPA DUMMY.
# TAHAP 5 FASE 12 - MODEL INDOBERT HUGGINGFACE HUB TANPA BOBOT LOKAL.
# TAHAP 5 FASE 7 - OPTIMASI PERFORMA: cache PNG WordCloud dan indikator proses pemuatan data.
# PATCH FASE 7 v4.0: pulihkan visualisasi utama IndiBiz beserta filter dan chart Fase 17
# PATCH FASE 7 v3.9: tambahkan gap nyata antara tabel riwayat dan batas bawah wrapper
# PATCH FASE 7 v3.8: tambah white spacing bawah pada tabel riwayat prediksi manual
# PATCH FASE 7 v3.7: refresh visual section Prediksi Sentimen Manual
# PATCH FASE 7 v3.6: tambah white spacing jelas antara WordCloud dan tombol download pada mode Semua
# PATCH FASE 7 v3.5: rapikan white spacing pada mode fokus WordCloud
# PATCH FASE 7 v3.4: perbaiki error figure ganda dan tingkatkan WordCloud menjadi HD dengan satu figure stabil
# PATCH FASE 7 v3.2: ganti fullscreen bawaan dengan viewer custom yang benar-benar center
# PATCH FASE 7 v3.1: tampilan fullscreen WordCloud dipusatkan dengan white spacing seimbang
# PATCH FASE 7 v3.0: posisikan tombol View Fullscreen WordCloud di pojok kanan atas gambar
# PATCH FASE 7 v2.9: perbaiki TypeError download PNG dan gunakan custom loading saat rerun unduhan
# PATCH FASE 7 v2.8: klik download PNG WordCloud tidak memicu rerun halaman
# PATCH FASE 7 v2.7: tambah tombol download PNG di bawah setiap WordCloud
# PATCH FASE 7 v2.6: custom loading saat mode WordCloud berubah
# PATCH FASE 7 v2.5: perbaiki kontrol mode WordCloud agar ringkas dan tidak terkena CSS selector layanan
# PATCH FASE 7 v2.4: refresh visual section WordCloud per Sentimen agar lebih menarik, interaktif, dan eye catching
# PATCH FASE 7 v2.0: percantik section Top Komentar per Platform dengan hero, ringkasan panel, dan animasi visual halus
# PATCH FASE 7 v2.1: tambah white spacing vertikal di dalam wrapper Top Komentar per Platform
# PATCH FASE 7 v2.2: perlebar white spacing di area tabel bawah pada wrapper Top Komentar per Platform
# PATCH FASE 7 v2.3: badge Platform dan Sentimen pada tabel Telkomsel dipaksa tetap satu baris
# PATCH FASE 7 v1.8: hapus badge informatif dan catatan animasi pada header Analisis per Platform
# PATCH FASE 7 v1.7: legenda grafik tren waktu dipusatkan presisi di tengah atas
# PATCH FASE 7 v1.5: stabilisasi interaksi grafik; hapus kontrol yang memicu flicker dan nilai transisi keliru
# PATCH FASE 7 v1.4: jarak tombol lebih lega dan animasi Plotly lebih halus tanpa flicker
# PATCH FASE 7 v1.3: visualisasi utama interaktif, animatif, dan legenda tengah bawah
# PATCH FASE 7 v1.2: hapus selector layanan ganda; pertahankan satu panel aktif
# PATCH TAHAP 4 FASE 7 v1.1: perbaiki kartu Telkomsel agar aktif dan dapat diklik
# PATCH FASE 17: aktifkan analitik sentimen IndiBiz dengan filter dan tabel
# PATCH FASE 12 UI: loading custom saat mengganti layanan
# PATCH FASE 12: visualisasi distribusi sentimen IndiBiz berbasis Plotly
# PATCH FASE 11: validasi output prediksi batch IndoBERT IndiBiz
# PATCH RIWAYAT V4.1: HTML tabel tanpa indentasi Markdown
# PATCH RIWAYAT V4: tabel custom + penyimpanan persisten per akun
# PATCH TRANSISI V3: callback pending + loader paling awal + stale opacity dinonaktifkan
# PATCH LOADING V2: prediksi manual memakai overlay lokal halus
# PATCH UI: legenda warna grafik probabilitas prediksi manual
# PATCH UI: jarak hasil prediksi ke grafik probabilitas = 28px
# PATCH PERFORMA: model lokal + direct inference + max_length 128
# PATCH UI: jarak metric card ke pie chart platform = 32px
"""Halaman Analisis Sentimen — Fase 7 Tahap 2.

Halaman ini menampilkan ringkasan sentimen, visualisasi per platform,
tren waktu, contoh komentar, dan prediksi manual menggunakan IndoBERT.
"""

from __future__ import annotations

import base64
import io
import json
import time
from datetime import datetime
from html import escape
from pathlib import Path
from typing import Any

import matplotlib.pyplot as plt
import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from wordcloud import WordCloud

from utils.audit_logger import log_activity
from utils.chart_builder import SENTIMENT_COLORS, SENTIMENT_LABELS
from utils.data_loader import (
    get_data_source_label,
    get_indibiz_prediction_status,
    load_indibiz_sentiment,
    load_indihome_sentiment,
    load_telkomsel_sentiment,
)
from utils.dummy_data import (
    get_demo_prediction,
    get_demo_sentiment,
    get_dummy_sentiment_data,
)
from utils.loading_screen import mulai_loading_aksi, selesaikan_loading_aksi
from utils.model_loader import load_indobert, predict_sentiment_batch
from utils.preprocessor import STOPWORDS_ID, clean_text

# -----------------------------------------------------------------------------
# Konstanta halaman
# -----------------------------------------------------------------------------
_LAYANAN_LIST = ["IndiHome", "IndiBiz", "Telkomsel"]
_ANALYTICS_READY_SERVICES = {"IndiHome", "IndiBiz", "Telkomsel"}
_READY_SERVICES = {"IndiHome", "IndiBiz", "Telkomsel"}
_MODEL_HF_NAME = "mdhugol/indonesia-bert-sentiment-classification"
_MODEL_MAX_LENGTH = 128
_HISTORY_KEY = "sentiment_prediction_history_v7"
_HISTORY_FILE_NAME = "manual_prediction_history.json"
_MAX_HISTORY = 10

_PREDICTION_PENDING_KEY = "_sent_v7_prediction_pending"
_PREDICTION_TEXT_KEY = "_sent_v7_prediction_text"
_PREDICTION_ERROR_KEY = "_sent_v7_prediction_error"
_PREDICTION_SERVICE_KEY = "_sent_v7_prediction_service"
_SERVICE_SWITCH_LOADING_KEY = "_sent_v7_service_switch_loading"
_SERVICE_SWITCH_MIN_SECONDS = 0.55
_WORDCLOUD_VIEW_LOADING_KEY = "_sent_v7_wordcloud_view_loading"
_WORDCLOUD_VIEW_MIN_SECONDS = 0.55
_WORDCLOUD_DOWNLOAD_LOADING_KEY = "_sent_v7_wordcloud_download_loading"
_WORDCLOUD_DOWNLOAD_MIN_SECONDS = 0.45

_INDIBIZ_FILTER_DRAFT_KEY = "sent_v17_indibiz_platform_draft"
_INDIBIZ_FILTER_APPLIED_KEY = "sent_v17_indibiz_platform_applied"
_INDIBIZ_FILTER_LOADING_KEY = "_sent_v17_indibiz_filter_loading"
_INDIBIZ_FILTER_MIN_SECONDS = 0.45
_INDIBIZ_PLATFORM_OPTIONS = {
    "Semua Platform": "all",
    "Twitter/X": "twitter",
    "Instagram": "instagram",
    "TikTok": "tiktok",
}

_SENTIMENT_ORDER = ["positive", "neutral", "negative"]

# Istilah domain dipertahankan karena merupakan bagian penting dari konteks
# layanan dan tidak boleh ikut terhapus sebagai stopword WordCloud.
_WORDCLOUD_DOMAIN_TERMS = frozenset(
    {
        "admin",
        "gangguan",
        "harga",
        "indibiz",
        "indibizid",
        "indihome",
        "indihomecare",
        "internet",
        "jaringan",
        "kuota",
        "layanan",
        "mytelkomsel",
        "provider",
        "sinyal",
        "starlink",
        "telkom",
        "telkomsel",
        "wifi",
    }
)
_WORDCLOUD_STOPWORDS = frozenset(
    set(STOPWORDS_ID).difference(_WORDCLOUD_DOMAIN_TERMS)
)
_SENTIMENT_ICONS = {
    "positive": "↗",
    "neutral": "●",
    "negative": "↘",
}
_PLATFORM_LABELS = {
    "twitter": "Twitter/X",
    "x": "Twitter/X",
    "instagram": "Instagram",
    "tiktok": "TikTok",
}
_PLATFORM_ICONS = {
    "twitter": "𝕏",
    "x": "𝕏",
    "instagram": "◎",
    "tiktok": "♪",
}
_LABEL_TO_SENTIMENT = {
    "LABEL_0": "positive",
    "LABEL_1": "neutral",
    "LABEL_2": "negative",
    "label_0": "positive",
    "label_1": "neutral",
    "label_2": "negative",
    "positive": "positive",
    "positif": "positive",
    "neutral": "neutral",
    "netral": "neutral",
    "negative": "negative",
    "negatif": "negative",
}


# -----------------------------------------------------------------------------
# Helper umum
# -----------------------------------------------------------------------------
def _project_root() -> Path:
    """Kembalikan lokasi folder utama proyek."""
    return Path(__file__).resolve().parent.parent


def _is_dark_mode() -> bool:
    """Ambil status tema dari session state secara aman."""
    try:
        return bool(st.session_state.get("dark_mode", True))
    except Exception:
        return True


def _chart_theme() -> dict[str, str]:
    """Kembalikan warna chart sesuai tema yang sedang aktif."""
    if _is_dark_mode():
        return {
            "text": "#F5F5F5",
            "muted": "#AAAAAA",
            "grid": "rgba(255,255,255,0.10)",
            "hover_bg": "#171717",
            "hover_border": "#343434",
        }
    return {
        "text": "#1F2937",
        "muted": "#64748B",
        "grid": "rgba(15,23,42,0.10)",
        "hover_bg": "#FFFFFF",
        "hover_border": "#D1D5DB",
    }


def _format_number(value: int | float) -> str:
    """Format angka besar menggunakan pemisah ribuan Indonesia."""
    try:
        return f"{int(value):,}".replace(",", ".")
    except Exception:
        return "0"


def _safe_float(value: Any, default: float = 0.0) -> float:
    """Konversi nilai menjadi float tanpa menghentikan halaman."""
    try:
        result = float(value)
        if pd.isna(result):
            return default
        return result
    except Exception:
        return default


def _normalize_sentiment(value: Any) -> str:
    """Normalisasi label sentimen ke positive, neutral, atau negative."""
    key = str(value or "").strip()
    return _LABEL_TO_SENTIMENT.get(key, _LABEL_TO_SENTIMENT.get(key.lower(), "neutral"))


def _normalize_platform(value: Any) -> str:
    """Normalisasi nama platform untuk kebutuhan filter dan tampilan."""
    key = str(value or "").lower().strip().replace("'", "")
    if key in {"twitter", "x", "twitter/x"}:
        return "twitter"
    if "instagram" in key:
        return "instagram"
    if "tiktok" in key:
        return "tiktok"
    return key or "lainnya"


def _plotly_chart(fig: go.Figure | None, key: str) -> None:
    """Render Plotly secara responsif dengan validasi figur."""
    try:
        if fig is None:
            st.warning("Grafik tidak dapat ditampilkan.")
            return
        st.plotly_chart(
            fig,
            use_container_width=True,
            config={
                "displaylogo": False,
                "responsive": True,
                "modeBarButtonsToRemove": ["lasso2d", "select2d"],
            },
            key=key,
        )
    except TypeError:
        # Fallback untuk versi Streamlit yang belum mendukung parameter key.
        st.plotly_chart(
            fig,
            use_container_width=True,
            config={"displaylogo": False, "responsive": True},
        )
    except Exception as exc:
        st.error(f"Grafik belum dapat ditampilkan: {exc}")


# -----------------------------------------------------------------------------
# CSS halaman
# -----------------------------------------------------------------------------
def _inject_sentiment_css() -> None:
    """Sisipkan CSS halaman Sentimen mengikuti pola Beranda dan Dataset."""
    try:
        st.markdown(
            """
            <style>
                @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=Plus+Jakarta+Sans:wght@500;600;700;800&display=swap');

                .sent-v7-page,
                .sent-v7-page * {
                    box-sizing: border-box;
                    font-family: 'Inter', sans-serif;
                }

                .sent-v7-hero {
                    background:
                        radial-gradient(circle at 92% 8%, rgba(255,255,255,0.16), transparent 30%),
                        linear-gradient(135deg, #B71C1C 0%, #E53935 56%, #F05A56 100%);
                    border: 1px solid rgba(255,255,255,0.12);
                    border-radius: 12px;
                    box-shadow: 0 14px 34px rgba(183,28,28,0.22);
                    color: #FFFFFF;
                    margin-bottom: 1rem;
                    overflow: hidden;
                    padding: 1.8rem 2rem;
                    position: relative;
                }

                .sent-v7-hero::before {
                    background: linear-gradient(90deg, rgba(255,255,255,0.24), transparent);
                    content: '';
                    height: 1px;
                    left: 0;
                    position: absolute;
                    right: 0;
                    top: 0;
                }

                .sent-v7-hero::after {
                    background: radial-gradient(circle, rgba(255,255,255,0.16), transparent 68%);
                    content: '';
                    height: 250px;
                    pointer-events: none;
                    position: absolute;
                    right: -80px;
                    top: -120px;
                    width: 250px;
                }

                .sent-v7-hero h1 {
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

                .sent-v7-hero p {
                    color: rgba(255,255,255,0.92) !important;
                    font-size: 0.96rem;
                    margin: 0.65rem 0 0.95rem;
                    max-width: 880px;
                    position: relative;
                    z-index: 1;
                }

                .sent-v7-hero-badges {
                    align-items: center;
                    display: flex;
                    flex-wrap: wrap;
                    gap: 0.45rem;
                    position: relative;
                    z-index: 1;
                }

                .sent-v7-hero-badge {
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

                /* =========================================================
                   SELECTOR LAYANAN INTERAKTIF — FASE 12 UI POLISH
                   Header dan radio dibuat seperti satu panel terpadu.
                   ========================================================= */
                .sent-v7-selector-wrap {
                    background:
                        radial-gradient(circle at 8% 0%, rgba(229,57,53,0.18), transparent 34%),
                        radial-gradient(circle at 92% 20%, rgba(59,130,246,0.12), transparent 30%),
                        linear-gradient(135deg, #191919 0%, #141414 56%, #171717 100%);
                    border: 1px solid rgba(255,255,255,0.10);
                    border-bottom: 0;
                    border-radius: 18px 18px 0 0;
                    box-shadow: 0 18px 48px rgba(0,0,0,0.28);
                    margin: 0;
                    overflow: hidden;
                    padding: 1.15rem 1.2rem 1.7rem;
                    position: relative;
                }

                .sent-v7-selector-wrap::before {
                    animation: sent-v7-selector-orb 6s ease-in-out infinite;
                    background: rgba(229,57,53,0.16);
                    border-radius: 999px;
                    content: "";
                    filter: blur(26px);
                    height: 86px;
                    pointer-events: none;
                    position: absolute;
                    right: 8%;
                    top: -48px;
                    width: 160px;
                }

                .sent-v7-selector-wrap::after {
                    animation: sent-v7-selector-line 4.8s linear infinite;
                    background: linear-gradient(
                        90deg,
                        transparent,
                        rgba(229,57,53,0.90),
                        rgba(255,176,32,0.85),
                        rgba(59,130,246,0.80),
                        transparent
                    );
                    bottom: 0;
                    content: "";
                    height: 2px;
                    left: -45%;
                    pointer-events: none;
                    position: absolute;
                    width: 46%;
                }

                .sent-v7-selector-head {
                    align-items: center;
                    display: flex;
                    gap: 1rem;
                    justify-content: space-between;
                    position: relative;
                    z-index: 1;
                }

                .sent-v7-selector-kicker {
                    align-items: center;
                    color: #FF8A86;
                    display: inline-flex;
                    font-size: 0.75rem /* FIX: minimum 12px agar terbaca di tablet */;
                    font-weight: 800;
                    gap: 0.46rem;
                    letter-spacing: 0.13em;
                    margin-bottom: 0.48rem;
                    text-transform: uppercase;
                }

                .sent-v7-selector-live-dot {
                    animation: sent-v7-live-dot 1.8s ease-in-out infinite;
                    background: #FF5252;
                    border-radius: 50%;
                    box-shadow: 0 0 0 0 rgba(255,82,82,0.42);
                    display: inline-block;
                    height: 8px;
                    width: 8px;
                }

                .sent-v7-selector-label {
                    color: #FFFFFF;
                    font-family: 'Plus Jakarta Sans', 'Inter', sans-serif;
                    font-size: clamp(1.02rem, 2vw, 1.18rem);
                    font-weight: 800;
                    letter-spacing: -0.025em;
                    line-height: 1.22;
                    margin: 0;
                }

                .sent-v7-selector-copy {
                    color: #AFAFAF !important;
                    font-size: 0.77rem;
                    line-height: 1.55;
                    margin: 0.34rem 0 0;
                    max-width: 720px;
                }

                .sent-v7-selector-summary {
                    align-items: center;
                    display: flex;
                    flex: 0 0 auto;
                    flex-wrap: wrap;
                    gap: 0.45rem;
                    justify-content: flex-end;
                }

                .sent-v7-selector-summary-chip {
                    align-items: center;
                    backdrop-filter: blur(8px);
                    background: rgba(255,255,255,0.055);
                    border: 1px solid rgba(255,255,255,0.10);
                    border-radius: 999px;
                    color: #D8D8D8;
                    display: inline-flex;
                    font-size: 0.75rem /* FIX: minimum 12px agar terbaca di tablet */;
                    font-weight: 750;
                    gap: 0.35rem;
                    padding: 0.42rem 0.66rem;
                    white-space: nowrap;
                }

                .sent-v7-selector-summary-chip strong {
                    color: #FFFFFF;
                    font-size: 0.75rem /* FIX: minimum 12px agar terbaca di tablet */;
                }

                div[data-testid="stRadio"] {
                    background:
                        linear-gradient(180deg, rgba(19,19,19,0.98), rgba(15,15,15,0.98));
                    border: 1px solid rgba(255,255,255,0.10);
                    border-radius: 0 0 18px 18px;
                    border-top: 0;
                    box-shadow: 0 18px 48px rgba(0,0,0,0.28);
                    margin: 0 0 1.25rem !important;
                    padding: 0 1rem 1rem;
                }

                div[data-testid="stRadio"] div[role="radiogroup"] {
                    display: grid !important;
                    gap: 0.82rem !important;
                    grid-template-columns: repeat(3, minmax(0, 1fr));
                    margin-top: -0.72rem;
                    width: 100%;
                }

                div[data-testid="stRadio"] div[role="radiogroup"] > label {
                    --service-accent: #E53935;
                    --service-accent-soft: rgba(229,57,53,0.16);
                    --service-glow: rgba(229,57,53,0.22);
                    --service-border: rgba(229,57,53,0.72);
                    --service-ring: rgba(229,57,53,0.14);
                    align-items: center !important;
                    background:
                        linear-gradient(145deg, rgba(255,255,255,0.045), rgba(255,255,255,0.018)),
                        #202020 !important;
                    border: 1px solid rgba(255,255,255,0.11) !important;
                    border-radius: 14px !important;
                    color: #F1F1F1 !important;
                    cursor: pointer;
                    isolation: isolate;
                    min-height: 78px;
                    overflow: hidden;
                    padding: 1rem 7.1rem 1rem 1rem !important;
                    position: relative;
                    transform: translateY(0) scale(1);
                    transition:
                        background 0.24s ease,
                        border-color 0.24s ease,
                        box-shadow 0.24s ease,
                        color 0.24s ease,
                        transform 0.24s cubic-bezier(.2,.8,.2,1);
                }

                div[data-testid="stRadio"] div[role="radiogroup"] > label:nth-child(2) {
                    --service-accent: #FFB020;
                    --service-accent-soft: rgba(255,176,32,0.15);
                    --service-glow: rgba(255,176,32,0.20);
                    --service-border: rgba(255,176,32,0.72);
                    --service-ring: rgba(255,176,32,0.13);
                }

                div[data-testid="stRadio"] div[role="radiogroup"] > label:nth-child(3) {
                    --service-accent: #4A8DFF;
                    --service-accent-soft: rgba(74,141,255,0.14);
                    --service-glow: rgba(74,141,255,0.18);
                    --service-border: rgba(74,141,255,0.70);
                    --service-ring: rgba(74,141,255,0.12);
                }

                /* Sapuan cahaya saat kartu diarahkan kursor. */
                div[data-testid="stRadio"] div[role="radiogroup"] > label::before {
                    background: linear-gradient(
                        110deg,
                        transparent 20%,
                        rgba(255,255,255,0.17) 48%,
                        transparent 76%
                    );
                    content: "";
                    inset: 0;
                    pointer-events: none;
                    position: absolute;
                    transform: translateX(-125%);
                    transition: transform 0.68s ease;
                    z-index: -1;
                }

                /* Badge status pada kanan atas setiap kartu. */
                div[data-testid="stRadio"] div[role="radiogroup"] > label::after {
                    background: var(--service-accent-soft);
                    border: 1px solid var(--service-border);
                    border-radius: 999px;
                    color: var(--service-accent);
                    content: "AKTIF";
                    font-size: 0.75rem /* FIX: minimum 12px agar terbaca di tablet */;
                    font-weight: 850;
                    letter-spacing: 0.07em;
                    padding: 0.34rem 0.48rem;
                    position: absolute;
                    right: 0.75rem;
                    top: 0.72rem;
                    white-space: nowrap;
                }

                div[data-testid="stRadio"] div[role="radiogroup"] > label:nth-child(1)::after {
                    content: "MODEL SIAP";
                }

                div[data-testid="stRadio"] div[role="radiogroup"] > label:nth-child(2)::after {
                    content: "DATA AKTIF";
                }

                div[data-testid="stRadio"] div[role="radiogroup"] > label:nth-child(3)::after {
                    content: "MODEL SIAP";
                }

                div[data-testid="stRadio"] div[role="radiogroup"] > label > * {
                    position: relative;
                    z-index: 1;
                }

                div[data-testid="stRadio"] div[role="radiogroup"] > label p {
                    color: #F2F2F2 !important;
                    font-family: 'Plus Jakarta Sans', 'Inter', sans-serif !important;
                    font-size: 0.86rem !important;
                    font-weight: 750 !important;
                    letter-spacing: -0.015em;
                    line-height: 1.35;
                    margin: 0 !important;
                }

                div[data-testid="stRadio"] div[role="radiogroup"] > label input[type="radio"] {
                    accent-color: var(--service-accent) !important;
                }

                div[data-testid="stRadio"] div[role="radiogroup"] > label:hover {
                    background:
                        radial-gradient(circle at 10% 20%, var(--service-accent-soft), transparent 58%),
                        #252525 !important;
                    border-color: var(--service-border) !important;
                    box-shadow: 0 14px 30px var(--service-glow);
                    color: #FFFFFF !important;
                    transform: translateY(-5px) scale(1.012);
                }

                div[data-testid="stRadio"] div[role="radiogroup"] > label:hover::before {
                    transform: translateX(125%);
                }

                div[data-testid="stRadio"] div[role="radiogroup"] > label:active {
                    transform: translateY(-1px) scale(0.985);
                }

                /* Kartu terpilih menyala lembut dan tetap jelas tanpa hover. */
                div[data-testid="stRadio"] div[role="radiogroup"] > label:has(input:checked) {
                    animation: sent-v7-service-selected 2.8s ease-in-out infinite;
                    background:
                        radial-gradient(circle at 10% 16%, var(--service-accent-soft), transparent 64%),
                        linear-gradient(145deg, #292929, #202020) !important;
                    border-color: var(--service-accent) !important;
                    box-shadow:
                        0 0 0 3px var(--service-ring),
                        0 16px 36px var(--service-glow);
                    transform: translateY(-3px);
                }

                div[data-testid="stRadio"] div[role="radiogroup"] > label:has(input:checked)::after {
                    background: var(--service-accent);
                    border-color: var(--service-accent);
                    color: #101010;
                }

                div[data-testid="stRadio"] div[role="radiogroup"] > label:has(input:checked) p {
                    color: #FFFFFF !important;
                }

                /* Telkomsel aktif penuh: kartu ketiga dapat diklik seperti layanan lain. */
                div[data-testid="stRadio"] div[role="radiogroup"] > label:nth-child(3) {
                    cursor: pointer !important;
                    filter: none;
                    opacity: 1;
                    pointer-events: auto;
                }

                .sent-v17-filter-shell {
                    align-items: center;
                    background:
                        radial-gradient(circle at 90% 10%, rgba(229,57,53,0.10), transparent 34%),
                        linear-gradient(145deg, rgba(255,255,255,0.035), rgba(255,255,255,0.012)),
                        #171717;
                    border: 1px solid rgba(255,255,255,0.10);
                    border-radius: 16px;
                    display: flex;
                    gap: 1rem;
                    justify-content: space-between;
                    margin: 0.25rem 0 0.75rem;
                    padding: 1rem 1.1rem;
                }

                .sent-v17-filter-title {
                    color: #FFFFFF;
                    font-family: 'Plus Jakarta Sans', 'Inter', sans-serif;
                    font-size: 0.96rem;
                    font-weight: 750;
                    margin-bottom: 0.2rem;
                }

                .sent-v17-filter-copy,
                .sent-v17-filter-status {
                    color: #AFAFAF;
                    font-size: 0.78rem;
                    line-height: 1.5;
                }

                .sent-v17-filter-status {
                    background: rgba(229,57,53,0.10);
                    border: 1px solid rgba(229,57,53,0.28);
                    border-radius: 999px;
                    color: #FF8A86;
                    font-weight: 700;
                    padding: 0.42rem 0.68rem;
                    white-space: nowrap;
                }

                div[data-testid="stForm"] {
                    background: rgba(18,18,18,0.72);
                    border: 1px solid rgba(255,255,255,0.08);
                    border-radius: 15px;
                    margin-bottom: 1rem;
                    padding: 0.7rem 0.8rem 0.2rem;
                }

                .sent-v17-table-wrap {
                    border: 1px solid rgba(255,255,255,0.09);
                    border-radius: 16px;
                    box-shadow: 0 16px 38px rgba(0,0,0,0.22);
                    margin-top: 0.7rem;
                    overflow-x: auto;
                    width: 100%;
                }

                .sent-v17-table {
                    border-collapse: separate;
                    border-spacing: 0;
                    min-width: 980px;
                    width: 100%;
                }

                .sent-v17-table th {
                    background: #171717;
                    border-bottom: 1px solid rgba(255,255,255,0.10);
                    color: #BDBDBD;
                    font-size: 0.75rem /* FIX: minimum 12px agar terbaca di tablet */;
                    font-weight: 800;
                    letter-spacing: 0.055em;
                    padding: 0.9rem 0.8rem;
                    text-align: left;
                    text-transform: uppercase;
                    white-space: nowrap;
                }

                .sent-v17-table td {
                    border-bottom: 1px solid rgba(255,255,255,0.065);
                    color: #EEEEEE;
                    font-size: 0.82rem;
                    line-height: 1.45;
                    padding: 0.82rem 0.8rem;
                    vertical-align: middle;
                }

                .sent-v17-table tbody tr:last-child td {
                    border-bottom: 0;
                }

                .sent-v17-table tbody tr.sent-positive td {
                    background: rgba(76,175,80,0.15);
                }

                .sent-v17-table tbody tr.sent-neutral td {
                    background: rgba(255,152,0,0.15);
                }

                .sent-v17-table tbody tr.sent-negative td {
                    background: rgba(244,67,54,0.15);
                }

                .sent-v17-table tbody tr:hover td {
                    filter: brightness(1.16);
                }

                .sent-v17-comment-cell {
                    max-width: 440px;
                    min-width: 300px;
                }

                .sent-v17-confidence {
                    font-variant-numeric: tabular-nums;
                    font-weight: 800;
                }

                @keyframes sent-v7-selector-orb {
                    0%, 100% { transform: translate3d(0, 0, 0) scale(1); }
                    50% { transform: translate3d(-34px, 10px, 0) scale(1.16); }
                }

                @keyframes sent-v7-selector-line {
                    from { left: -46%; }
                    to { left: 100%; }
                }

                @keyframes sent-v7-live-dot {
                    0%, 100% { box-shadow: 0 0 0 0 rgba(255,82,82,0.42); }
                    50% { box-shadow: 0 0 0 7px rgba(255,82,82,0); }
                }

                @keyframes sent-v7-service-selected {
                    0%, 100% {
                        box-shadow:
                            0 0 0 3px var(--service-ring),
                            0 14px 30px var(--service-glow);
                    }
                    50% {
                        box-shadow:
                            0 0 0 5px var(--service-ring),
                            0 18px 40px var(--service-glow);
                    }
                }

                @media (max-width: 920px) {
                    .sent-v7-selector-head {
                        align-items: flex-start;
                        flex-direction: column;
                    }

                    .sent-v7-selector-summary {
                        justify-content: flex-start;
                    }

                    div[data-testid="stRadio"] div[role="radiogroup"] {
                        grid-template-columns: repeat(2, minmax(0, 1fr));
                    }

                    div[data-testid="stRadio"] div[role="radiogroup"] > label:nth-child(3) {
                        grid-column: 1 / -1;
                    }
                }

                @media (max-width: 620px) {
                    .sent-v7-selector-wrap {
                        padding: 1rem 0.9rem 1.55rem;
                    }

                    div[data-testid="stRadio"] {
                        padding: 0 0.75rem 0.85rem;
                    }

                    div[data-testid="stRadio"] div[role="radiogroup"] {
                        grid-template-columns: 1fr;
                    }

                    div[data-testid="stRadio"] div[role="radiogroup"] > label,
                    div[data-testid="stRadio"] div[role="radiogroup"] > label:nth-child(3) {
                        grid-column: auto;
                        min-height: 72px;
                        padding-right: 6.7rem !important;
                    }
                }

                @media (max-width: 700px) {
                    .sent-v17-filter-shell {
                        align-items: flex-start;
                        flex-direction: column;
                    }

                    .sent-v17-filter-status {
                        white-space: normal;
                    }
                }

                @media (prefers-reduced-motion: reduce) {
                    .sent-v7-selector-wrap::before,
                    .sent-v7-selector-wrap::after,
                    .sent-v7-selector-live-dot,
                    div[data-testid="stRadio"] div[role="radiogroup"] > label:has(input:checked) {
                        animation: none !important;
                    }

                    div[data-testid="stRadio"] div[role="radiogroup"] > label,
                    div[data-testid="stRadio"] div[role="radiogroup"] > label::before {
                        transition: none !important;
                    }
                }

                /*
                Streamlit menandai elemen lama sebagai stale saat tombol diklik.
                Opacity bawaan dimatikan agar halaman tidak sempat meredup
                sebelum overlay prediksi custom muncul.
                */
                [data-stale="true"],
                [data-stale="true"] * {
                    filter: none !important;
                    opacity: 1 !important;
                }

                /*
                Sembunyikan indikator loading bawaan Streamlit pada halaman ini.
                Pergantian layanan dan prediksi manual memakai overlay Telkom
                dari utils/loading_screen.py agar pengalaman pengguna konsisten.
                */
                div[data-testid="stStatusWidget"],
                div[data-testid="stSpinner"] {
                    display: none !important;
                    opacity: 0 !important;
                    pointer-events: none !important;
                    visibility: hidden !important;
                }

                .sent-v7-section-heading {
                    align-items: center;
                    display: flex;
                    gap: 0.65rem;
                    margin: 1.4rem 0 0.75rem;
                }

                .sent-v7-section-index {
                    align-items: center;
                    background: rgba(229,57,53,0.14);
                    border: 1px solid rgba(229,57,53,0.36);
                    border-radius: 8px;
                    color: #FF6B67;
                    display: inline-flex;
                    font-family: 'Plus Jakarta Sans', 'Inter', sans-serif;
                    font-size: 0.75rem /* FIX: minimum 12px agar terbaca di tablet */;
                    font-weight: 800;
                    height: 28px;
                    justify-content: center;
                    width: 34px;
                }

                .sent-v7-section-heading h2 {
                    color: #FFFFFF !important;
                    font-family: 'Plus Jakarta Sans', 'Inter', sans-serif;
                    font-size: 1.05rem;
                    font-weight: 750;
                    letter-spacing: -0.015em;
                    margin: 0;
                }

                .sent-v7-section-heading p {
                    color: #777777 !important;
                    font-size: 0.78rem;
                    margin: 0.15rem 0 0;
                }

                .sent-v7-metric-card {
                    background: linear-gradient(180deg, #1D1D1D 0%, #181818 100%);
                    border: 1px solid #2A2A2A;
                    border-left: 3px solid var(--metric-color, #E53935);
                    border-radius: 12px;
                    box-shadow: 0 8px 22px rgba(0,0,0,0.16);
                    min-height: 122px;
                    padding: 1rem 1rem 0.9rem;
                    transition: border-color 0.18s ease, box-shadow 0.18s ease,
                        transform 0.18s ease;
                }

                .sent-v7-metric-card:hover {
                    border-color: var(--metric-color, #E53935);
                    box-shadow: 0 0 0 1px color-mix(in srgb, var(--metric-color, #E53935) 30%, transparent),
                        0 13px 30px rgba(0,0,0,0.24);
                    transform: translateY(-2px);
                }

                .sent-v7-metric-label {
                    color: #AAAAAA;
                    font-size: 0.75rem /* FIX: minimum 12px agar terbaca di tablet */;
                    font-weight: 700;
                    letter-spacing: 0.045em;
                    text-transform: uppercase;
                }

                .sent-v7-metric-value {
                    color: var(--metric-color, #E53935);
                    font-family: 'Plus Jakarta Sans', 'Inter', sans-serif;
                    font-size: clamp(1.55rem, 3vw, 2rem);
                    font-weight: 800;
                    letter-spacing: -0.04em;
                    line-height: 1;
                    margin: 0.6rem 0 0.45rem;
                }
.sent-v7-metric-note {
    color: #777777;
    font-size: 0.75rem /* FIX: minimum 12px agar terbaca di tablet */;
    line-height: 1.35;
}

.sent-v7-platform-section-gap {
    height: 1.1rem;
}

.sent-v7-platform-shell {
    animation: sentV7PlatformEnter 0.58s cubic-bezier(0.22, 1, 0.36, 1) both;
    background:
        radial-gradient(circle at 12% 14%, rgba(229,57,53,0.16), transparent 28%),
        radial-gradient(circle at 88% 18%, rgba(77,141,255,0.14), transparent 26%),
        linear-gradient(180deg, rgba(25,25,25,0.98), rgba(16,16,16,0.98));
    border: 1px solid rgba(255,255,255,0.08);
    border-radius: 18px;
    box-shadow: 0 18px 42px rgba(0,0,0,0.22);
    margin: 0.25rem 0 1rem;
    overflow: hidden;
    padding: 1rem 1rem 1.05rem;
    position: relative;
}

.sent-v7-platform-shell::after {
    background: linear-gradient(90deg, rgba(229,57,53,0.42), rgba(255,152,0,0.22), rgba(77,141,255,0.22));
    content: '';
    height: 2px;
    left: 0;
    opacity: 0.9;
    position: absolute;
    right: 0;
    top: 0;
}

.sent-v7-platform-top {
    align-items: flex-start;
    display: flex;
    gap: 1rem;
    justify-content: space-between;
    position: relative;
    z-index: 1;
}

.sent-v7-platform-kicker {
    align-items: center;
    color: #FF9E99;
    display: inline-flex;
    font-size: 0.75rem /* FIX: minimum 12px agar terbaca di tablet */;
    font-weight: 800;
    gap: 0.46rem;
    letter-spacing: 0.13em;
    margin-bottom: 0.45rem;
    text-transform: uppercase;
}

.sent-v7-platform-kicker-dot {
    animation: sent-v7-live-dot 1.8s ease-in-out infinite;
    background: #FF5E57;
    border-radius: 50%;
    box-shadow: 0 0 0 0 rgba(255,94,87,0.32);
    display: inline-block;
    height: 8px;
    width: 8px;
}

.sent-v7-platform-title {
    color: #FFFFFF;
    font-family: 'Plus Jakarta Sans', 'Inter', sans-serif;
    font-size: clamp(1.02rem, 2vw, 1.22rem);
    font-weight: 800;
    letter-spacing: -0.03em;
    line-height: 1.2;
    margin: 0;
}

.sent-v7-platform-copy {
    color: #AAAAAA;
    font-size: 0.79rem;
    line-height: 1.6;
    margin: 0.36rem 0 0;
    max-width: 700px;
}

.sent-v7-platform-chip-row {
    align-items: center;
    display: flex;
    flex: 0 0 auto;
    flex-wrap: wrap;
    gap: 0.5rem;
    justify-content: flex-end;
    margin-top: 0.06rem;
}

.sent-v7-platform-chip {
    align-items: center;
    backdrop-filter: blur(10px);
    background: rgba(255,255,255,0.05);
    border: 1px solid rgba(255,255,255,0.09);
    border-radius: 999px;
    color: #F2F2F2;
    display: inline-flex;
    font-size: 0.75rem /* FIX: minimum 12px agar terbaca di tablet */;
    font-weight: 750;
    gap: 0.38rem;
    padding: 0.45rem 0.7rem;
    white-space: nowrap;
}

.sent-v7-platform-chip strong {
    color: #FFFFFF;
    font-size: 0.75rem /* FIX: minimum 12px agar terbaca di tablet */;
}

.sent-v7-platform-chip--positive {
    border-color: rgba(76,175,80,0.34);
    color: #7BE382;
}

.sent-v7-platform-chip--neutral {
    border-color: rgba(255,152,0,0.34);
    color: #FFBD5A;
}

.sent-v7-platform-chip--negative {
    border-color: rgba(244,67,54,0.34);
    color: #FF847D;
}

.sent-v7-platform-chart-card {
    animation: sentV7PlatformEnter 0.66s cubic-bezier(0.22, 1, 0.36, 1) both;
    background:
        radial-gradient(circle at 82% 0%, rgba(77,141,255,0.14), transparent 20%),
        linear-gradient(180deg, rgba(20,20,20,0.96), rgba(15,15,15,0.96));
    border: 1px solid rgba(255,255,255,0.08);
    border-radius: 16px;
    box-shadow: 0 16px 38px rgba(0,0,0,0.20);
    margin-top: 0.15rem;
    overflow: hidden;
    padding: 0.95rem 1rem 0.15rem;
    position: relative;
}

.sent-v7-platform-chart-card::before {
    background: linear-gradient(90deg, rgba(76,175,80,0.55), rgba(255,152,0,0.45), rgba(244,67,54,0.55));
    content: '';
    height: 2px;
    left: 0;
    position: absolute;
    right: 0;
    top: 0;
}

.sent-v7-platform-chart-title {
    color: #FFFFFF;
    font-family: 'Plus Jakarta Sans', 'Inter', sans-serif;
    font-size: 1rem;
    font-weight: 800;
    letter-spacing: -0.02em;
    margin: 0;
}

.sent-v7-platform-chart-copy {
    color: #9FA5AF;
    font-size: 0.77rem;
    line-height: 1.55;
    margin: 0.28rem 0 0.25rem;
}

@keyframes sentV7PlatformEnter {
    0% {
        opacity: 0;
        transform: translateY(14px) scale(0.985);
    }
    100% {
        opacity: 1;
        transform: translateY(0) scale(1);
    }
}

                .sent-v11-status-card {
                    animation: sentV11CardEnter 0.55s cubic-bezier(0.22, 1, 0.36, 1) both;
                    background:
                        radial-gradient(circle at 88% -12%, rgba(229,57,53,0.24), transparent 34%),
                        radial-gradient(circle at 8% 118%, rgba(255,152,0,0.10), transparent 32%),
                        linear-gradient(135deg, #1D1D1D 0%, #171717 55%, #15191F 100%);
                    border: 1px solid rgba(255,255,255,0.09);
                    border-radius: 18px;
                    box-shadow: 0 18px 50px rgba(0,0,0,0.30), inset 0 1px 0 rgba(255,255,255,0.035);
                    isolation: isolate;
                    margin: 1rem 0 0.35rem;
                    overflow: hidden;
                    padding: 1.45rem 1.5rem 1.35rem;
                    position: relative;
                    transition: border-color 0.28s ease, box-shadow 0.28s ease, transform 0.28s ease;
                }

                .sent-v11-status-card:hover {
                    border-color: rgba(229,57,53,0.30);
                    box-shadow: 0 24px 62px rgba(0,0,0,0.38), 0 0 34px rgba(229,57,53,0.08);
                    transform: translateY(-2px);
                }

                .sent-v11-status-card::before {
                    animation: sentV11Sweep 7s linear infinite;
                    background: linear-gradient(90deg, transparent, rgba(255,255,255,0.34), #E53935, rgba(255,152,0,0.72), transparent);
                    content: '';
                    height: 2px;
                    left: -45%;
                    position: absolute;
                    top: 0;
                    width: 45%;
                    z-index: 3;
                }

                .sent-v11-status-card::after {
                    animation: sentV11OrbFloat 6s ease-in-out infinite;
                    background: rgba(229,57,53,0.12);
                    border: 1px solid rgba(229,57,53,0.13);
                    border-radius: 999px;
                    box-shadow: 0 0 80px rgba(229,57,53,0.17);
                    content: '';
                    height: 170px;
                    pointer-events: none;
                    position: absolute;
                    right: -86px;
                    top: -92px;
                    width: 170px;
                    z-index: -1;
                }

                .sent-v11-status-head {
                    align-items: flex-start;
                    display: flex;
                    gap: 1rem;
                    justify-content: space-between;
                    margin-bottom: 1.15rem;
                    position: relative;
                    z-index: 1;
                }

                .sent-v11-status-heading {
                    min-width: 0;
                }

                .sent-v11-status-kicker {
                    align-items: center;
                    color: #FF7A76;
                    display: inline-flex;
                    font-size: 0.75rem /* FIX: minimum 12px agar terbaca di tablet */;
                    font-weight: 850;
                    gap: 0.48rem;
                    letter-spacing: 0.13em;
                    margin-bottom: 0.5rem;
                    text-transform: uppercase;
                }

                .sent-v11-status-kicker::before {
                    animation: sentV11Pulse 1.8s ease-in-out infinite;
                    background: #E53935;
                    border-radius: 999px;
                    box-shadow: 0 0 0 5px rgba(229,57,53,0.13);
                    content: '';
                    height: 8px;
                    width: 8px;
                }

                .sent-v11-status-title {
                    color: #FFFFFF;
                    font-family: 'Plus Jakarta Sans', 'Inter', sans-serif;
                    font-size: clamp(1.2rem, 2vw, 1.62rem);
                    font-weight: 800;
                    letter-spacing: -0.035em;
                    line-height: 1.15;
                    margin: 0;
                }

                .sent-v11-status-subtitle {
                    color: #A5A5A5;
                    font-size: 0.78rem;
                    line-height: 1.55;
                    margin: 0.45rem 0 0;
                    max-width: 720px;
                }

                .sent-v11-status-badge {
                    align-items: center;
                    backdrop-filter: blur(10px);
                    background: linear-gradient(135deg, rgba(76,175,80,0.17), rgba(76,175,80,0.07));
                    border: 1px solid rgba(76,175,80,0.42);
                    border-radius: 999px;
                    box-shadow: 0 8px 22px rgba(0,0,0,0.20);
                    color: #8FE294;
                    display: inline-flex;
                    flex: 0 0 auto;
                    font-size: 0.75rem /* FIX: minimum 12px agar terbaca di tablet */;
                    font-weight: 850;
                    gap: 0.42rem;
                    padding: 0.48rem 0.72rem;
                    text-transform: uppercase;
                    transition: transform 0.2s ease, box-shadow 0.2s ease;
                }

                .sent-v11-status-badge:hover {
                    box-shadow: 0 8px 26px rgba(76,175,80,0.16);
                    transform: translateY(-2px) scale(1.02);
                }

                .sent-v11-status-badge--warning {
                    background: linear-gradient(135deg, rgba(255,152,0,0.18), rgba(255,152,0,0.07));
                    border-color: rgba(255,152,0,0.42);
                    color: #FFC164;
                }

                .sent-v11-status-dot {
                    animation: sentV11StatusPulse 1.7s ease-in-out infinite;
                    background: currentColor;
                    border-radius: 999px;
                    height: 8px;
                    width: 8px;
                }

                .sent-v11-status-grid {
                    display: grid;
                    gap: 0.78rem;
                    grid-template-columns: repeat(4, minmax(0, 1fr));
                    position: relative;
                    z-index: 1;
                }

                .sent-v11-status-item {
                    background: linear-gradient(145deg, rgba(255,255,255,0.055), rgba(255,255,255,0.018));
                    border: 1px solid rgba(255,255,255,0.075);
                    border-radius: 14px;
                    min-height: 132px;
                    min-width: 0;
                    overflow: hidden;
                    padding: 0.95rem 0.95rem 0.9rem;
                    position: relative;
                    transition: border-color 0.25s ease, box-shadow 0.25s ease, transform 0.25s ease;
                }

                .sent-v11-status-item::before {
                    background: linear-gradient(90deg, var(--stat-accent, #E53935), transparent 82%);
                    content: '';
                    height: 2px;
                    left: 0;
                    opacity: 0.68;
                    position: absolute;
                    top: 0;
                    width: 100%;
                }

                .sent-v11-status-item::after {
                    background: var(--stat-accent, #E53935);
                    border-radius: 999px;
                    content: '';
                    filter: blur(24px);
                    height: 44px;
                    opacity: 0.08;
                    position: absolute;
                    right: -12px;
                    top: -14px;
                    transition: opacity 0.25s ease, transform 0.25s ease;
                    width: 44px;
                }

                .sent-v11-status-item:hover {
                    border-color: color-mix(in srgb, var(--stat-accent, #E53935) 50%, transparent);
                    box-shadow: 0 16px 30px rgba(0,0,0,0.22);
                    transform: translateY(-5px);
                }

                .sent-v11-status-item:hover::after {
                    opacity: 0.22;
                    transform: scale(1.7);
                }

                .sent-v11-status-topline {
                    align-items: center;
                    display: flex;
                    gap: 0.55rem;
                    justify-content: space-between;
                }

                .sent-v11-status-label {
                    color: #898989;
                    font-size: 0.75rem /* FIX: minimum 12px agar terbaca di tablet */;
                    font-weight: 800;
                    letter-spacing: 0.07em;
                    text-transform: uppercase;
                }

                .sent-v11-stat-icon {
                    align-items: center;
                    background: color-mix(in srgb, var(--stat-accent, #E53935) 13%, transparent);
                    border: 1px solid color-mix(in srgb, var(--stat-accent, #E53935) 28%, transparent);
                    border-radius: 8px;
                    color: var(--stat-accent, #E53935);
                    display: inline-flex;
                    font-size: 0.75rem /* FIX: minimum 12px agar terbaca di tablet */;
                    font-weight: 850;
                    height: 27px;
                    justify-content: center;
                    letter-spacing: 0.03em;
                    min-width: 31px;
                    padding: 0 0.35rem;
                    transition: transform 0.25s ease;
                }

                .sent-v11-status-item:hover .sent-v11-stat-icon {
                    transform: rotate(-4deg) scale(1.08);
                }

                .sent-v11-status-value {
                    color: #FFFFFF;
                    font-family: 'Plus Jakarta Sans', 'Inter', sans-serif;
                    font-size: clamp(1.02rem, 1.65vw, 1.32rem);
                    font-weight: 800;
                    letter-spacing: -0.025em;
                    line-height: 1.22;
                    margin-top: 0.62rem;
                    overflow-wrap: anywhere;
                }

                .sent-v11-status-note {
                    color: #7F7F7F;
                    font-size: 0.75rem /* FIX: minimum 12px agar terbaca di tablet */;
                    line-height: 1.45;
                    margin-top: 0.35rem;
                }

                .sent-v11-distribution {
                    align-items: center;
                    background: rgba(0,0,0,0.12);
                    border: 1px solid rgba(255,255,255,0.055);
                    border-radius: 13px;
                    display: flex;
                    flex-wrap: wrap;
                    gap: 0.55rem;
                    margin-top: 0.9rem;
                    padding: 0.78rem;
                    position: relative;
                    z-index: 1;
                }

                .sent-v11-distribution-label {
                    color: #8B8B8B;
                    font-size: 0.75rem /* FIX: minimum 12px agar terbaca di tablet */;
                    font-weight: 800;
                    letter-spacing: 0.07em;
                    margin: 0 0.18rem;
                    text-transform: uppercase;
                }

                .sent-v11-chip {
                    align-items: center;
                    background: linear-gradient(135deg, rgba(255,255,255,0.055), rgba(255,255,255,0.025));
                    border: 1px solid color-mix(in srgb, var(--chip-color, #FFFFFF) 24%, #2D2D2D);
                    border-radius: 999px;
                    color: #C9C9C9;
                    display: inline-flex;
                    font-size: 0.75rem /* FIX: minimum 12px agar terbaca di tablet */;
                    font-weight: 680;
                    gap: 0.34rem;
                    padding: 0.46rem 0.7rem;
                    transition: background 0.22s ease, box-shadow 0.22s ease, transform 0.22s ease;
                }

                .sent-v11-chip::before {
                    background: var(--chip-color, #FFFFFF);
                    border-radius: 999px;
                    box-shadow: 0 0 10px color-mix(in srgb, var(--chip-color, #FFFFFF) 48%, transparent);
                    content: '';
                    height: 7px;
                    width: 7px;
                }

                .sent-v11-chip:hover {
                    background: color-mix(in srgb, var(--chip-color, #FFFFFF) 10%, rgba(255,255,255,0.025));
                    box-shadow: 0 8px 20px rgba(0,0,0,0.18);
                    transform: translateY(-3px);
                }

                .sent-v11-chip strong {
                    color: var(--chip-color, #FFFFFF);
                    font-weight: 850;
                }

                @keyframes sentV11CardEnter {
                    from { opacity: 0; transform: translateY(16px) scale(0.992); }
                    to { opacity: 1; transform: translateY(0) scale(1); }
                }

                @keyframes sentV11Sweep {
                    0% { left: -45%; }
                    45%, 100% { left: 115%; }
                }

                @keyframes sentV11Pulse {
                    0%, 100% { box-shadow: 0 0 0 5px rgba(229,57,53,0.12); transform: scale(1); }
                    50% { box-shadow: 0 0 0 8px rgba(229,57,53,0.03); transform: scale(1.12); }
                }

                @keyframes sentV11StatusPulse {
                    0%, 100% { opacity: 0.75; transform: scale(0.9); }
                    50% { opacity: 1; transform: scale(1.25); }
                }

                @keyframes sentV11OrbFloat {
                    0%, 100% { transform: translate3d(0,0,0); }
                    50% { transform: translate3d(-14px,14px,0); }
                }

                @media (max-width: 900px) {
                    .sent-v11-status-grid {
                        grid-template-columns: repeat(2, minmax(0, 1fr));
                    }
                }

                @media (max-width: 620px) {
                    .sent-v11-status-card {
                        border-radius: 15px;
                        padding: 1.1rem;
                    }

                    .sent-v11-status-head {
                        flex-direction: column;
                    }

                    .sent-v11-status-grid {
                        grid-template-columns: 1fr;
                    }

                    .sent-v11-status-item {
                        min-height: 0;
                    }
                }

                @media (prefers-reduced-motion: reduce) {
                    .sent-v11-status-card,
                    .sent-v11-status-card::before,
                    .sent-v11-status-card::after,
                    .sent-v11-status-kicker::before,
                    .sent-v11-status-dot {
                        animation: none !important;
                    }

                    .sent-v11-status-card,
                    .sent-v11-status-item,
                    .sent-v11-chip,
                    .sent-v11-stat-icon,
                    .sent-v11-status-badge {
                        transition: none !important;
                    }
                }

                .sent-v7-chart-card {
                    animation: sentV7ChartHeaderReveal 0.62s cubic-bezier(0.22, 1, 0.36, 1) both;
                    background:
                        radial-gradient(circle at 8% 0%, rgba(76,175,80,0.13), transparent 30%),
                        radial-gradient(circle at 88% 8%, rgba(255,152,0,0.12), transparent 34%),
                        linear-gradient(145deg, #1D1D1D 0%, #141414 100%);
                    border: 1px solid rgba(255,255,255,0.09);
                    border-radius: 16px;
                    box-shadow: 0 14px 34px rgba(0,0,0,0.22), inset 0 1px 0 rgba(255,255,255,0.03);
                    isolation: isolate;
                    margin-bottom: 0.72rem;
                    min-height: 100%;
                    overflow: hidden;
                    padding: 1rem 1.05rem 0.9rem;
                    position: relative;
                    transition:
                        border-color 0.28s ease,
                        box-shadow 0.28s ease,
                        transform 0.28s ease;
                }

                .sent-v7-chart-card::before {
                    background: linear-gradient(90deg, #4CAF50 0%, #FF9800 50%, #F44336 100%);
                    content: '';
                    height: 3px;
                    inset: 0 0 auto 0;
                    position: absolute;
                    transform: scaleX(0.38);
                    transform-origin: left center;
                    transition: transform 0.4s cubic-bezier(0.22, 1, 0.36, 1);
                    z-index: -1;
                }

                .sent-v7-chart-card::after {
                    background: radial-gradient(circle, rgba(229,57,53,0.16), transparent 68%);
                    content: '';
                    height: 170px;
                    pointer-events: none;
                    position: absolute;
                    right: -72px;
                    top: -92px;
                    width: 170px;
                    z-index: -1;
                }

                .sent-v7-chart-card:hover {
                    border-color: rgba(229,57,53,0.58);
                    box-shadow: 0 18px 42px rgba(0,0,0,0.32), 0 0 28px rgba(229,57,53,0.10);
                    transform: none;
                }

                .sent-v7-chart-card:hover::before {
                    transform: scaleX(1);
                }

                .sent-v7-chart-kicker {
                    align-items: center;
                    color: #FF8A86;
                    display: flex;
                    font-family: 'Plus Jakarta Sans', 'Inter', sans-serif;
                    font-size: 0.75rem /* FIX: minimum 12px agar terbaca di tablet */;
                    font-weight: 800;
                    gap: 0.42rem;
                    letter-spacing: 0.115em;
                    margin-bottom: 0.5rem;
                    text-transform: uppercase;
                }

                .sent-v7-chart-kicker-dot {
                    animation: sentV7KickerPulse 1.9s ease-in-out infinite;
                    background: #E53935;
                    border-radius: 999px;
                    box-shadow: 0 0 0 5px rgba(229,57,53,0.10);
                    display: inline-block;
                    height: 0.42rem;
                    width: 0.42rem;
                }

                .sent-v7-chart-title {
                    color: #FFFFFF;
                    font-family: 'Plus Jakarta Sans', 'Inter', sans-serif;
                    font-size: 1rem;
                    font-weight: 800;
                    letter-spacing: -0.018em;
                    line-height: 1.25;
                    margin: 0;
                }

                .sent-v7-chart-subtitle {
                    color: #969696;
                    font-size: 0.75rem /* FIX: minimum 12px agar terbaca di tablet */;
                    line-height: 1.55;
                    margin: 0.32rem 0 0;
                }

                .sent-v7-chart-hint {
                    align-items: center;
                    color: #707070;
                    display: flex;
                    font-size: 0.75rem /* FIX: minimum 12px agar terbaca di tablet */;
                    gap: 0.35rem;
                    margin-top: 0.55rem;
                }

                .sent-v7-chart-hint::before {
                    color: #E53935;
                    content: '✦';
                    font-size: 0.75rem /* FIX: minimum 12px agar terbaca di tablet */;
                }

                div[data-testid="stPlotlyChart"] {
                    animation: sentV7PlotReveal 0.72s 0.08s cubic-bezier(0.22, 1, 0.36, 1) both;
                    background:
                        radial-gradient(circle at 16% 0%, rgba(76,175,80,0.055), transparent 31%),
                        radial-gradient(circle at 88% 0%, rgba(244,67,54,0.055), transparent 33%),
                        linear-gradient(180deg, rgba(22,22,22,0.98), rgba(13,17,24,0.98));
                    border: 1px solid rgba(255,255,255,0.075);
                    border-radius: 18px;
                    box-shadow: 0 18px 42px rgba(0,0,0,0.24), inset 0 1px 0 rgba(255,255,255,0.025);
                    backface-visibility: hidden;
                    overflow: hidden;
                    padding: 0.25rem;
                    transform: translateZ(0);
                    transform-origin: center top;
                    transition:
                        border-color 0.28s ease,
                        box-shadow 0.28s ease,
                        transform 0.28s ease;
                }

                div[data-testid="stPlotlyChart"]:hover {
                    border-color: rgba(229,57,53,0.42);
                    box-shadow: 0 22px 50px rgba(0,0,0,0.33), 0 0 32px rgba(229,57,53,0.075);
                    transform: translateZ(0);
                }

                @keyframes sentV7ChartHeaderReveal {
                    from { opacity: 0; transform: translateY(12px); }
                    to { opacity: 1; transform: translateY(0); }
                }

                @keyframes sentV7PlotReveal {
                    from { opacity: 0; transform: translateY(16px) scale(0.985); }
                    to { opacity: 1; transform: translateY(0) scale(1); }
                }

                @keyframes sentV7KickerPulse {
                    0%, 100% { box-shadow: 0 0 0 5px rgba(229,57,53,0.08); transform: scale(1); }
                    50% { box-shadow: 0 0 0 9px rgba(229,57,53,0.02); transform: scale(1.08); }
                }

                @media (prefers-reduced-motion: reduce) {
                    .sent-v7-chart-card,
                    .sent-v7-chart-kicker-dot,
                    div[data-testid="stPlotlyChart"] {
                        animation: none !important;
                        transition: none !important;
                    }
                }

                .sent-v7-coming-soon {
                    background:
                        radial-gradient(circle at 90% 0%, rgba(229,57,53,0.13), transparent 34%),
                        linear-gradient(180deg, #1B1B1B, #171717);
                    border: 1px solid #2A2A2A;
                    border-radius: 12px;
                    overflow: hidden;
                    padding: 1.45rem;
                    position: relative;
                }

                .sent-v7-coming-soon::before {
                    background: #E53935;
                    content: '';
                    height: 100%;
                    left: 0;
                    position: absolute;
                    top: 0;
                    width: 3px;
                }

                .sent-v7-coming-soon h3 {
                    color: #FFFFFF;
                    font-family: 'Plus Jakarta Sans', 'Inter', sans-serif;
                    font-size: 1.05rem;
                    margin: 0 0 0.45rem;
                }

                .sent-v7-coming-soon p {
                    color: #AAAAAA;
                    font-size: 0.86rem;
                    line-height: 1.55;
                    margin: 0;
                }

                .sent-v7-comment-card {
                    background: #181818;
                    border: 1px solid #2A2A2A;
                    border-radius: 10px;
                    margin-bottom: 0.65rem;
                    padding: 0.9rem;
                    transition: border-color 0.18s ease, transform 0.18s ease;
                }

                .sent-v7-comment-card:hover {
                    border-color: rgba(229,57,53,0.72);
                    transform: translateY(-1px);
                }

                .sent-v7-comment-meta {
                    align-items: center;
                    display: flex;
                    flex-wrap: wrap;
                    gap: 0.4rem;
                    margin-bottom: 0.55rem;
                }

                .sent-v7-comment-content {
                    color: #EAEAEA;
                    font-size: 0.85rem;
                    line-height: 1.58;
                    margin: 0;
                    overflow-wrap: anywhere;
                }

                .sent-v7-badge {
                    align-items: center;
                    border: 1px solid transparent;
                    border-radius: 999px;
                    display: inline-flex;
                    flex-wrap: nowrap;
                    font-size: 0.75rem /* FIX: minimum 12px agar terbaca di tablet */;
                    font-weight: 700;
                    gap: 0.25rem;
                    line-height: 1;
                    max-width: none;
                    padding: 0.38rem 0.58rem;
                    white-space: nowrap;
                    width: max-content;
                    word-break: keep-all;
                }

                .sent-v7-badge-positive {
                    background: rgba(76,175,80,0.14);
                    border-color: rgba(76,175,80,0.34);
                    color: #72D978;
                }

                .sent-v7-badge-neutral {
                    background: rgba(255,152,0,0.14);
                    border-color: rgba(255,152,0,0.34);
                    color: #FFB547;
                }

                .sent-v7-badge-negative {
                    background: rgba(244,67,54,0.14);
                    border-color: rgba(244,67,54,0.34);
                    color: #FF7770;
                }

                .sent-v7-badge-platform,
                .sent-v7-badge-confidence {
                    background: #242424;
                    border-color: #343434;
                    color: #D0D0D0;
                }

                /* Tabel riwayat prediksi manual. */
                .sent-v7-history-summary {
                    align-items: center;
                    display: flex;
                    flex-wrap: wrap;
                    gap: 0.55rem;
                    justify-content: space-between;
                    margin: 0.2rem 0 0.85rem;
                }

                .sent-v7-history-summary-text {
                    color: #AAAAAA;
                    font-size: 0.76rem;
                    line-height: 1.45;
                    margin: 0;
                }

                .sent-v7-history-counter {
                    background: rgba(229,57,53,0.12);
                    border: 1px solid rgba(229,57,53,0.32);
                    border-radius: 999px;
                    color: #FF7770;
                    font-size: 0.75rem /* FIX: minimum 12px agar terbaca di tablet */;
                    font-weight: 750;
                    padding: 0.34rem 0.58rem;
                }

                .sent-v7-history-table-wrap {
                    background: #151515;
                    border: 1px solid #2A2A2A;
                    border-radius: 12px;
                    box-shadow: 0 14px 32px rgba(0,0,0,0.18);
                    overflow-x: auto;
                    overflow-y: hidden;
                    width: 100%;
                    box-sizing: border-box;
                    margin-bottom: 1.15rem;
                }

                .sent-v7-history-bottom-gap {
                    display: block;
                    height: 0.65rem;
                    width: 100%;
                }

                .sent-v7-history-table {
                    border-collapse: separate;
                    border-spacing: 0;
                    min-width: 790px;
                    table-layout: fixed;
                    width: 100%;
                }

                .sent-v7-history-table thead th {
                    background:
                        linear-gradient(
                            180deg,
                            rgba(229,57,53,0.10),
                            rgba(229,57,53,0.035)
                        ),
                        #1E1E1E;
                    border-bottom: 1px solid #343434;
                    color: #C8C8C8;
                    font-family: 'Plus Jakarta Sans', 'Inter', sans-serif;
                    font-size: 0.75rem /* FIX: minimum 12px agar terbaca di tablet */;
                    font-weight: 750;
                    letter-spacing: 0.055em;
                    padding: 0.82rem 0.9rem;
                    text-align: left;
                    text-transform: uppercase;
                    white-space: nowrap;
                }

                .sent-v7-history-table thead th:first-child {
                    border-top-left-radius: 11px;
                    text-align: center;
                    width: 58px;
                }

                .sent-v7-history-table thead th:nth-child(2) {
                    width: 178px;
                }

                .sent-v7-history-table thead th:nth-child(4) {
                    width: 138px;
                }

                .sent-v7-history-table thead th:nth-child(5) {
                    width: 130px;
                }

                .sent-v7-history-table thead th:last-child {
                    border-top-right-radius: 11px;
                }

                .sent-v7-history-table tbody td {
                    background: #181818;
                    border-bottom: 1px solid #292929;
                    color: #E8E8E8;
                    font-size: 0.78rem;
                    line-height: 1.45;
                    padding: 0.82rem 0.9rem;
                    transition:
                        background 0.18s ease,
                        color 0.18s ease;
                    vertical-align: middle;
                }

                .sent-v7-history-table tbody tr:last-child td {
                    border-bottom: 0;
                }

                .sent-v7-history-table tbody tr:last-child td:first-child {
                    border-bottom-left-radius: 11px;
                }

                .sent-v7-history-table tbody tr:last-child td:last-child {
                    border-bottom-right-radius: 11px;
                }

                .sent-v7-history-table tbody tr:hover td {
                    background: linear-gradient(90deg, rgba(229,57,53,0.055), rgba(255,255,255,0.018));
                    color: #FFFFFF;
                }

                .sent-v7-history-number {
                    color: #777777 !important;
                    font-weight: 700;
                    text-align: center;
                }

                .sent-v7-history-time {
                    color: #B8B8B8 !important;
                    font-variant-numeric: tabular-nums;
                    white-space: nowrap;
                }

                .sent-v7-history-text {
                    color: #F1F1F1 !important;
                    overflow-wrap: anywhere;
                }

                .sent-v7-history-sentiment {
                    border: 1px solid transparent;
                    border-radius: 999px;
                    display: inline-flex;
                    font-size: 0.75rem /* FIX: minimum 12px agar terbaca di tablet */;
                    font-weight: 750;
                    line-height: 1;
                    padding: 0.4rem 0.62rem;
                    white-space: nowrap;
                }

                .sent-v7-history-sentiment.positive {
                    background: rgba(76,175,80,0.14);
                    border-color: rgba(76,175,80,0.34);
                    color: #72D978;
                }

                .sent-v7-history-sentiment.neutral {
                    background: rgba(255,152,0,0.14);
                    border-color: rgba(255,152,0,0.34);
                    color: #FFB547;
                }

                .sent-v7-history-sentiment.negative {
                    background: rgba(244,67,54,0.14);
                    border-color: rgba(244,67,54,0.34);
                    color: #FF7770;
                }

                .sent-v7-history-confidence {
                    align-items: center;
                    display: flex;
                    gap: 0.48rem;
                    min-width: 104px;
                }

                .sent-v7-history-confidence-track {
                    background: #2A2A2A;
                    border-radius: 999px;
                    display: block;
                    height: 6px;
                    overflow: hidden;
                    width: 54px;
                }

                .sent-v7-history-confidence-fill {
                    background: linear-gradient(90deg, #B71C1C, #FF5252);
                    border-radius: 999px;
                    display: block;
                    height: 100%;
                    max-width: 100%;
                    min-width: 2px;
                }

                .sent-v7-history-confidence-value {
                    color: #D8D8D8;
                    font-size: 0.75rem /* FIX: minimum 12px agar terbaca di tablet */;
                    font-variant-numeric: tabular-nums;
                    font-weight: 700;
                    white-space: nowrap;
                }

                .sent-v7-prediction-card {
                    animation: sentV7ManualHeroIn 0.56s cubic-bezier(0.22, 1, 0.36, 1) both;
                    background:
                        radial-gradient(circle at 0% 0%, rgba(229,57,53,0.16), transparent 30%),
                        radial-gradient(circle at 100% 0%, rgba(255,152,0,0.10), transparent 26%),
                        linear-gradient(135deg, rgba(28,28,28,0.98), rgba(17,17,17,0.98));
                    border: 1px solid rgba(255,255,255,0.08);
                    border-radius: 18px;
                    box-shadow: 0 18px 42px rgba(0,0,0,0.22);
                    margin-bottom: 1rem;
                    overflow: hidden;
                    padding: 1.05rem 1.1rem 1.05rem;
                    position: relative;
                }

                .sent-v7-prediction-card::before {
                    content: '';
                    position: absolute;
                    inset: 0 0 auto 0;
                    height: 3px;
                    background: linear-gradient(90deg, #E53935 0%, #FF7043 50%, #FFB300 100%);
                }

                .sent-v7-manual-kicker {
                    align-items: center;
                    color: #FF9A96;
                    display: inline-flex;
                    font-size: 0.75rem /* FIX: minimum 12px agar terbaca di tablet */;
                    font-weight: 800;
                    gap: 0.42rem;
                    letter-spacing: 0.12em;
                    margin-bottom: 0.5rem;
                    text-transform: uppercase;
                }

                .sent-v7-manual-kicker-dot {
                    width: 0.48rem;
                    height: 0.48rem;
                    border-radius: 999px;
                    background: #E53935;
                    box-shadow: 0 0 0 7px rgba(229,57,53,0.10);
                    animation: sentV7ManualPulse 2.2s ease-in-out infinite;
                }

                .sent-v7-manual-title {
                    color: #FFFFFF;
                    font-family: 'Plus Jakarta Sans', 'Inter', sans-serif;
                    font-size: 1.02rem;
                    font-weight: 800;
                    letter-spacing: -0.02em;
                    margin: 0;
                }

                .sent-v7-manual-copy {
                    color: #A8A8A8;
                    font-size: 0.76rem;
                    line-height: 1.58;
                    margin: 0.38rem 0 0;
                    max-width: 760px;
                }

                .sent-v7-manual-flow {
                    display: grid;
                    gap: 0.68rem;
                    grid-template-columns: repeat(3, minmax(0, 1fr));
                    margin-top: 0.9rem;
                }

                .sent-v7-manual-step {
                    align-items: flex-start;
                    background: rgba(255,255,255,0.035);
                    border: 1px solid rgba(255,255,255,0.07);
                    border-radius: 13px;
                    display: flex;
                    gap: 0.65rem;
                    min-height: 82px;
                    padding: 0.74rem 0.78rem;
                    transition: border-color 0.22s ease, box-shadow 0.22s ease, transform 0.22s ease, background 0.22s ease;
                }

                .sent-v7-manual-step:hover {
                    background: rgba(229,57,53,0.055);
                    border-color: rgba(229,57,53,0.32);
                    box-shadow: 0 12px 26px rgba(0,0,0,0.18), 0 0 22px rgba(229,57,53,0.08);
                    transform: translateY(-2px);
                }

                .sent-v7-manual-step-number {
                    align-items: center;
                    background: rgba(229,57,53,0.12);
                    border: 1px solid rgba(229,57,53,0.30);
                    border-radius: 10px;
                    color: #FF7770;
                    display: inline-flex;
                    flex: 0 0 32px;
                    font-size: 0.75rem /* FIX: minimum 12px agar terbaca di tablet */;
                    font-weight: 800;
                    height: 32px;
                    justify-content: center;
                }

                .sent-v7-manual-step-title {
                    color: #F4F4F4;
                    font-size: 0.76rem;
                    font-weight: 780;
                    line-height: 1.3;
                    margin: 0 0 0.2rem;
                }

                .sent-v7-manual-step-copy {
                    color: #8F8F8F;
                    font-size: 0.75rem /* FIX: minimum 12px agar terbaca di tablet */;
                    line-height: 1.45;
                    margin: 0;
                }

                .sent-v7-manual-input-label {
                    align-items: center;
                    color: #D9D9D9;
                    display: flex;
                    font-size: 0.75rem /* FIX: minimum 12px agar terbaca di tablet */;
                    font-weight: 750;
                    gap: 0.45rem;
                    margin: 0.25rem 0 0.55rem;
                }

                .sent-v7-manual-input-label::before {
                    content: '';
                    width: 7px;
                    height: 7px;
                    border-radius: 999px;
                    background: #E53935;
                    box-shadow: 0 0 0 5px rgba(229,57,53,0.08);
                }

                .sent-v7-manual-helper {
                    align-items: center;
                    color: #838383;
                    display: flex;
                    flex-wrap: wrap;
                    font-size: 0.75rem /* FIX: minimum 12px agar terbaca di tablet */;
                    gap: 0.55rem;
                    justify-content: space-between;
                    margin: 0.42rem 0 0.82rem;
                }

                .sent-v7-manual-helper strong {
                    color: #CFCFCF;
                    font-weight: 700;
                }

                .sent-v7-manual-action-note {
                    color: #7E7E7E;
                    font-size: 0.75rem /* FIX: minimum 12px agar terbaca di tablet */;
                    line-height: 1.48;
                    margin: 0.5rem 0 0.2rem;
                    text-align: center;
                }

                @keyframes sentV7ManualHeroIn {
                    from { opacity: 0; transform: translateY(14px) scale(0.986); }
                    to { opacity: 1; transform: translateY(0) scale(1); }
                }

                @keyframes sentV7ManualPulse {
                    0%,100% { transform: scale(1); box-shadow: 0 0 0 7px rgba(229,57,53,0.10); }
                    50% { transform: scale(1.08); box-shadow: 0 0 0 11px rgba(229,57,53,0.02); }
                }

                .sent-v7-result-box {
                    animation: sent-v7-result-enter 360ms cubic-bezier(0.22, 1, 0.36, 1) both;
                    background:
                        radial-gradient(circle at 50% 0%, rgba(255,255,255,0.045), transparent 34%),
                        linear-gradient(180deg, rgba(24,24,24,0.98), rgba(17,17,17,0.98));
                    border: 1px solid rgba(255,255,255,0.08);
                    border-radius: 16px;
                    box-shadow: 0 16px 34px rgba(0,0,0,0.20);
                    margin-top: 1rem;
                    overflow: hidden;
                    padding: 1.15rem;
                    position: relative;
                    text-align: center;
                }

                .sent-v7-result-box::before {
                    content: '';
                    position: absolute;
                    inset: 0 0 auto 0;
                    height: 3px;
                    background: linear-gradient(90deg, #4CAF50, #FF9800, #F44336);
                }

                @keyframes sent-v7-result-enter {
                    from {
                        opacity: 0;
                        transform: translateY(8px);
                    }

                    to {
                        opacity: 1;
                        transform: translateY(0);
                    }
                }

                .sent-v7-result-label {
                    font-family: 'Plus Jakarta Sans', 'Inter', sans-serif;
                    font-size: clamp(1.65rem, 4vw, 2.25rem);
                    font-weight: 800;
                    letter-spacing: -0.04em;
                    margin: 0.35rem 0;
                }

                .sent-v7-result-confidence {
                    color: #AAAAAA;
                    font-size: 0.82rem;
                }

                div[data-testid="stTextArea"] label,
                div[data-testid="stRadio"] > label,
                div[data-testid="stExpander"] summary,
                div[data-testid="stTabs"] button {
                    font-family: 'Inter', sans-serif !important;
                }

                div[data-testid="stTextArea"] {
                    gap: 0.72rem !important;
                }

                div[data-testid="stTextArea"] > label {
                    display: block !important;
                    margin-bottom: 0.72rem !important;
                }

                div[data-testid="stTextArea"] textarea {
                    background:
                        radial-gradient(circle at 100% 0%, rgba(229,57,53,0.055), transparent 30%),
                        #202020 !important;
                    border: 1px solid #343434 !important;
                    border-radius: 14px !important;
                    color: #FFFFFF !important;
                    min-height: 145px !important;
                    padding: 1rem !important;
                    transition: border-color 0.22s ease, box-shadow 0.22s ease, background 0.22s ease, transform 0.22s ease;
                }

                div[data-testid="stTextArea"] textarea:focus {
                    background: #242020 !important;
                    border-color: #E53935 !important;
                    box-shadow: 0 0 0 3px rgba(229,57,53,0.13), 0 14px 30px rgba(0,0,0,0.18) !important;
                    transform: translateY(-1px);
                }

                div[data-testid="stButton"] button[kind="primary"],
                div[data-testid="stButton"] button[data-testid="baseButton-primary"] {
                    background: linear-gradient(135deg, #D32F2F 0%, #F44336 52%, #FF7043 100%) !important;
                    border: 1px solid rgba(255,124,112,0.58) !important;
                    border-radius: 8px !important;
                    color: #FFFFFF !important;
                    font-family: 'Inter', sans-serif !important;
                    font-weight: 700 !important;
                    min-height: 46px;
                    box-shadow: 0 10px 24px rgba(229,57,53,0.18) !important;
                    transition: background 0.22s ease, border-color 0.22s ease,
                        box-shadow 0.22s ease, transform 0.22s ease;
                }

                div[data-testid="stButton"] button[kind="primary"]:hover,
                div[data-testid="stButton"] button[data-testid="baseButton-primary"]:hover {
                    background: linear-gradient(135deg, #E53935 0%, #FF5252 52%, #FF8A65 100%) !important;
                    border-color: rgba(255,160,150,0.72) !important;
                    box-shadow: 0 14px 30px rgba(229,57,53,0.30) !important;
                    transform: translateY(-2px);
                }

                div[data-testid="stTabs"] [data-baseweb="tab-list"] {
                    background: #171717;
                    border: 1px solid #2A2A2A;
                    border-radius: 10px;
                    gap: 0.3rem;
                    padding: 0.3rem;
                }

                div[data-testid="stTabs"] button[role="tab"] {
                    border-radius: 8px;
                    color: #AAAAAA !important;
                    font-size: 0.78rem;
                    font-weight: 700;
                    padding: 0.6rem 0.9rem;
                }

                div[data-testid="stTabs"] button[role="tab"][aria-selected="true"] {
                    background: #E53935 !important;
                    color: #FFFFFF !important;
                }

                @media (max-width: 900px) {
                    .sent-v7-platform-top {
                        flex-direction: column;
                    }

                    .sent-v7-platform-chip-row {
                        justify-content: flex-start;
                    }
                    .sent-v7-platform-section-gap {
                        height: 0.95rem;
                    }
                    .sent-v7-wordcloud-focus-stat-row {
                        grid-template-columns: 1fr;
                    }

                    .sent-v7-manual-flow {
                        grid-template-columns: 1fr;
                    }
                    .sent-v7-comments-stat-row {
                        grid-template-columns: 1fr;
                    }
                }

                /*
                Expander Contoh Komentar dibuat selalu gelap agar judul
                Positif, Netral, dan Negatif tetap terbaca tanpa perlu hover.
                */
                div[data-testid="stExpander"] {
                    background: #181818 !important;
                    border: 1px solid #2A2A2A !important;
                    border-radius: 10px !important;
                    margin-bottom: 0.75rem;
                    overflow: hidden;
                }

                div[data-testid="stExpander"] details {
                    background: #181818 !important;
                    border-radius: 10px !important;
                }

                div[data-testid="stExpander"] details > div {
                    padding-top: 0.4rem;
                    padding-bottom: 1rem;
                }

                div[data-testid="stExpander"] summary {
                    background:
                        linear-gradient(90deg, rgba(229,57,53,0.10), transparent 38%),
                        #202020 !important;
                    border-bottom: 1px solid transparent !important;
                    color: #F5F5F5 !important;
                    min-height: 56px;
                    padding: 0.85rem 1rem !important;
                    transition:
                        background 0.18s ease,
                        border-color 0.18s ease,
                        color 0.18s ease;
                }

                div[data-testid="stExpander"] summary p,
                div[data-testid="stExpander"] summary span {
                    color: #F5F5F5 !important;
                    font-size: 0.86rem !important;
                    font-weight: 750 !important;
                    opacity: 1 !important;
                }

                div[data-testid="stExpander"] summary svg {
                    color: #BDBDBD !important;
                    fill: #BDBDBD !important;
                    opacity: 1 !important;
                }

                div[data-testid="stExpander"] details[open] > summary {
                    background:
                        linear-gradient(90deg, rgba(229,57,53,0.16), transparent 42%),
                        #222222 !important;
                    border-bottom-color: #303030 !important;
                    color: #FFFFFF !important;
                }

                div[data-testid="stExpander"] summary:hover {
                    background:
                        linear-gradient(90deg, rgba(229,57,53,0.20), transparent 44%),
                        #262626 !important;
                    color: #FFFFFF !important;
                }

                div[data-testid="stExpander"] summary:hover p,
                div[data-testid="stExpander"] summary:hover span {
                    color: #FFFFFF !important;
                }

                .sent-v7-telkomsel-table-wrap {
                    background: #151515;
                    border: 1px solid #2A2A2A;
                    border-radius: 12px;
                    margin-top: 0.85rem;
                    margin-bottom: 1rem;
                    overflow-x: auto;
                    width: 100%;
                }

                .sent-v7-telkomsel-table-wrap::after {
                    content: "";
                    display: block;
                    height: 0.1rem;
                }

                .sent-v7-telkomsel-table {
                    border-collapse: separate;
                    border-spacing: 0;
                    min-width: 1020px;
                    width: 100%;
                }

                .sent-v7-telkomsel-table th:nth-child(1),
                .sent-v7-telkomsel-table td:nth-child(1) {
                    min-width: 150px;
                    white-space: nowrap;
                }

                .sent-v7-telkomsel-table th:nth-child(3),
                .sent-v7-telkomsel-table td:nth-child(3) {
                    min-width: 145px;
                    white-space: nowrap;
                }

                .sent-v7-telkomsel-table th {
                    background: linear-gradient(180deg, rgba(229,57,53,0.11), rgba(229,57,53,0.03)), #1E1E1E;
                    border-bottom: 1px solid #343434;
                    color: #CFCFCF;
                    font-family: 'Plus Jakarta Sans', 'Inter', sans-serif;
                    font-size: 0.75rem /* FIX: minimum 12px agar terbaca di tablet */;
                    font-weight: 750;
                    letter-spacing: 0.045em;
                    padding: 0.78rem 0.85rem;
                    text-align: left;
                    text-transform: uppercase;
                    white-space: nowrap;
                }

                .sent-v7-telkomsel-table td {
                    background: #181818;
                    border-bottom: 1px solid #292929;
                    color: #E8E8E8;
                    font-size: 0.78rem;
                    line-height: 1.48;
                    padding: 0.78rem 0.85rem;
                    vertical-align: top;
                }

                .sent-v7-telkomsel-table tbody tr:last-child td {
                    border-bottom: 0;
                }

                .sent-v7-telkomsel-table tbody tr:hover td {
                    background: #202020;
                }

                .sent-v7-telkomsel-comment {
                    min-width: 340px;
                    overflow-wrap: anywhere;
                }

                .sent-v7-comments-hero {
                    animation: sentV7CommentsHeroIn 0.56s cubic-bezier(0.22, 1, 0.36, 1) both;
                    background:
                        radial-gradient(circle at 12% 0%, rgba(229,57,53,0.14), transparent 28%),
                        radial-gradient(circle at 88% 0%, rgba(255,152,0,0.10), transparent 26%),
                        linear-gradient(135deg, rgba(28,28,28,0.98) 0%, rgba(18,18,18,0.98) 100%);
                    border: 1px solid rgba(255,255,255,0.08);
                    border-radius: 18px;
                    box-shadow: 0 16px 36px rgba(0,0,0,0.22);
                    margin: 0.15rem 0 1rem;
                    overflow: hidden;
                    padding: 1rem 1.05rem 1rem;
                    position: relative;
                }

                .sent-v7-comments-hero::before {
                    content: '';
                    position: absolute;
                    inset: 0 0 auto 0;
                    height: 3px;
                    background: linear-gradient(90deg, #1DA1F2 0%, #833AB4 52%, #FF0050 100%);
                }

                .sent-v7-comments-kicker {
                    align-items: center;
                    color: #FF8A86;
                    display: inline-flex;
                    font-size: 0.75rem /* FIX: minimum 12px agar terbaca di tablet */;
                    font-weight: 800;
                    gap: 0.42rem;
                    letter-spacing: 0.12em;
                    margin-bottom: 0.52rem;
                    text-transform: uppercase;
                }

                .sent-v7-comments-kicker-dot {
                    width: 0.48rem;
                    height: 0.48rem;
                    border-radius: 999px;
                    background: #E53935;
                    box-shadow: 0 0 0 7px rgba(229,57,53,0.10);
                    animation: sentV7CommentsPulse 2.1s ease-in-out infinite;
                }

                .sent-v7-comments-hero h3 {
                    color: #FFFFFF;
                    font-family: 'Plus Jakarta Sans', 'Inter', sans-serif;
                    font-size: 1rem;
                    font-weight: 800;
                    letter-spacing: -0.02em;
                    margin: 0;
                }

                .sent-v7-comments-hero p {
                    color: #A9A9A9;
                    font-size: 0.76rem;
                    line-height: 1.58;
                    margin: 0.42rem 0 0;
                    max-width: 640px;
                }

                .sent-v7-comments-chip-row {
                    display: flex;
                    flex-wrap: wrap;
                    gap: 0.55rem;
                    margin-top: 0.82rem;
                }

                .sent-v7-comments-chip {
                    align-items: center;
                    background: rgba(255,255,255,0.05);
                    border: 1px solid rgba(255,255,255,0.08);
                    border-radius: 999px;
                    color: #F1F1F1;
                    display: inline-flex;
                    font-size: 0.75rem /* FIX: minimum 12px agar terbaca di tablet */;
                    font-weight: 700;
                    gap: 0.38rem;
                    padding: 0.46rem 0.8rem;
                }

                .sent-v7-comments-chip strong {
                    color: #FFFFFF;
                    font-weight: 800;
                }

                .sent-v7-comments-chip--twitter { border-color: rgba(29,161,242,0.34); }
                .sent-v7-comments-chip--instagram { border-color: rgba(131,58,180,0.34); }
                .sent-v7-comments-chip--tiktok { border-color: rgba(255,0,80,0.34); }

                .sent-v7-comments-panel {
                    animation: sentV7CommentsPanelIn 0.34s ease both;
                    background: linear-gradient(180deg, rgba(28,28,28,0.98), rgba(20,20,20,0.98));
                    border: 1px solid rgba(255,255,255,0.06);
                    border-radius: 14px;
                    margin-top: 0.25rem;
                    margin-bottom: 1rem;
                    overflow: hidden;
                    padding: 0.95rem 0.95rem 1rem;
                }

                .sent-v7-comments-panel-head {
                    align-items: center;
                    display: flex;
                    flex-wrap: wrap;
                    gap: 0.5rem;
                    justify-content: space-between;
                    margin-bottom: 0.72rem;
                }

                .sent-v7-comments-panel-title {
                    color: #FFFFFF;
                    font-size: 0.84rem;
                    font-weight: 780;
                    letter-spacing: -0.01em;
                }

                .sent-v7-comments-panel-sub {
                    color: #8E8E8E;
                    font-size: 0.75rem /* FIX: minimum 12px agar terbaca di tablet */;
                    margin-top: 0.16rem;
                }

                .sent-v7-comments-stat-row {
                    display: grid;
                    gap: 0.65rem;
                    grid-template-columns: repeat(3, minmax(0, 1fr));
                    margin-bottom: 0.78rem;
                }

                .sent-v7-comments-stat {
                    background: rgba(255,255,255,0.03);
                    border: 1px solid rgba(255,255,255,0.06);
                    border-radius: 12px;
                    padding: 0.68rem 0.75rem;
                }

                .sent-v7-comments-stat-label {
                    color: #8D8D8D;
                    font-size: 0.75rem /* FIX: minimum 12px agar terbaca di tablet */;
                    font-weight: 700;
                    letter-spacing: 0.045em;
                    margin-bottom: 0.26rem;
                    text-transform: uppercase;
                }

                .sent-v7-comments-stat-value {
                    color: #FFFFFF;
                    font-family: 'Plus Jakarta Sans', 'Inter', sans-serif;
                    font-size: 0.98rem;
                    font-weight: 800;
                    letter-spacing: -0.02em;
                }

                .sent-v7-comments-stat-note {
                    color: #8D8D8D;
                    font-size: 0.75rem /* FIX: minimum 12px agar terbaca di tablet */;
                    margin-top: 0.22rem;
                }

                @keyframes sentV7CommentsHeroIn {
                    from { opacity: 0; transform: translateY(14px) scale(0.985); }
                    to { opacity: 1; transform: translateY(0) scale(1); }
                }

                @keyframes sentV7CommentsPanelIn {
                    from { opacity: 0; transform: translateY(10px); }
                    to { opacity: 1; transform: translateY(0); }
                }

                @keyframes sentV7CommentsPulse {
                    0%,100% { transform: scale(1); box-shadow: 0 0 0 7px rgba(229,57,53,0.10); }
                    50% { transform: scale(1.08); box-shadow: 0 0 0 11px rgba(229,57,53,0.02); }
                }

                .sent-v7-wordcloud-hero {
                    animation: sentV7WordcloudHeroIn 0.58s cubic-bezier(0.22, 1, 0.36, 1) both;
                    background:
                        radial-gradient(circle at 12% 0%, rgba(76, 175, 80, 0.13), transparent 22%),
                        radial-gradient(circle at 50% 0%, rgba(41, 121, 255, 0.12), transparent 24%),
                        radial-gradient(circle at 88% 0%, rgba(244, 67, 54, 0.13), transparent 22%),
                        linear-gradient(135deg, rgba(26,26,26,0.98) 0%, rgba(17,17,17,0.98) 100%);
                    border: 1px solid rgba(255,255,255,0.07);
                    border-radius: 18px;
                    box-shadow: 0 18px 40px rgba(0,0,0,0.20);
                    margin-bottom: 0.95rem;
                    overflow: hidden;
                    padding: 1rem 1.05rem 1rem;
                    position: relative;
                }

                .sent-v7-wordcloud-hero::before {
                    content: '';
                    position: absolute;
                    inset: 0 0 auto 0;
                    height: 3px;
                    background: linear-gradient(90deg, #4CAF50 0%, #2979FF 50%, #F44336 100%);
                }

                .sent-v7-wordcloud-kicker {
                    align-items: center;
                    color: #FF9A96;
                    display: inline-flex;
                    font-size: 0.75rem /* FIX: minimum 12px agar terbaca di tablet */;
                    font-weight: 800;
                    gap: 0.42rem;
                    letter-spacing: 0.12em;
                    margin-bottom: 0.56rem;
                    text-transform: uppercase;
                }

                .sent-v7-wordcloud-kicker-dot {
                    width: 0.48rem;
                    height: 0.48rem;
                    border-radius: 999px;
                    background: #E53935;
                    box-shadow: 0 0 0 7px rgba(229,57,53,0.10);
                    animation: sentV7WordcloudPulse 2.3s ease-in-out infinite;
                }

                .sent-v7-wordcloud-hero-title {
                    color: #FFFFFF;
                    font-family: 'Plus Jakarta Sans', 'Inter', sans-serif;
                    font-size: 1rem;
                    font-weight: 800;
                    letter-spacing: -0.02em;
                    margin: 0;
                }

                .sent-v7-wordcloud-hero-copy {
                    color: #B6B6B6;
                    font-size: 0.77rem;
                    line-height: 1.62;
                    margin: 0.5rem 0 0;
                    max-width: 760px;
                }

                .sent-v7-wordcloud-chip-row {
                    display: flex;
                    flex-wrap: wrap;
                    gap: 0.55rem;
                    margin-top: 0.85rem;
                }

                .sent-v7-wordcloud-chip {
                    align-items: center;
                    background: rgba(255,255,255,0.04);
                    border: 1px solid rgba(255,255,255,0.08);
                    border-radius: 999px;
                    color: #F4F4F4;
                    display: inline-flex;
                    font-size: 0.75rem /* FIX: minimum 12px agar terbaca di tablet */;
                    font-weight: 700;
                    gap: 0.42rem;
                    padding: 0.45rem 0.78rem;
                }

                .sent-v7-wordcloud-chip strong {
                    color: #FFFFFF;
                    font-weight: 800;
                }

                .sent-v7-wordcloud-chip--positive { border-color: rgba(76,175,80,0.35); }
                .sent-v7-wordcloud-chip--neutral { border-color: rgba(41,121,255,0.35); }
                .sent-v7-wordcloud-chip--negative { border-color: rgba(244,67,54,0.35); }

                .sent-v7-wordcloud-intro {
                    background: linear-gradient(135deg, rgba(229,57,53,0.08), rgba(29,161,242,0.04)), #171717;
                    border: 1px solid #2A2A2A;
                    border-radius: 14px;
                    color: #BDBDBD;
                    font-size: 0.78rem;
                    line-height: 1.6;
                    margin-bottom: 0.9rem;
                    padding: 0.9rem 1rem;
                }

                .sent-v7-wordcloud-mode-label {
                    color: #A0A0A0;
                    font-size: 0.75rem /* FIX: minimum 12px agar terbaca di tablet */;
                    margin: 0.1rem 0 0.35rem;
                }

                .sent-v7-wordcloud-control-head {
                    align-items: center;
                    background:
                        linear-gradient(135deg, rgba(255,255,255,0.035), rgba(255,255,255,0.012)),
                        #171717;
                    border: 1px solid rgba(255,255,255,0.08);
                    border-radius: 14px;
                    display: flex;
                    gap: 0.75rem;
                    justify-content: space-between;
                    margin: 0.1rem 0 0.5rem;
                    padding: 0.82rem 0.95rem;
                }

                .sent-v7-wordcloud-control-title {
                    color: #F5F5F5;
                    font-family: 'Plus Jakarta Sans', 'Inter', sans-serif;
                    font-size: 0.8rem;
                    font-weight: 780;
                    margin: 0;
                }

                .sent-v7-wordcloud-control-copy {
                    color: #8F8F8F;
                    font-size: 0.75rem /* FIX: minimum 12px agar terbaca di tablet */;
                    line-height: 1.45;
                    margin: 0.18rem 0 0;
                }

                .sent-v7-wordcloud-control-icon {
                    align-items: center;
                    background: rgba(229,57,53,0.10);
                    border: 1px solid rgba(229,57,53,0.26);
                    border-radius: 10px;
                    color: #FF8A86;
                    display: inline-flex;
                    flex: 0 0 auto;
                    font-size: 0.85rem;
                    height: 34px;
                    justify-content: center;
                    width: 34px;
                }

                .sent-v7-wordcloud-mode-summary {
                    align-items: center;
                    background: rgba(255,255,255,0.025);
                    border: 1px solid rgba(255,255,255,0.06);
                    border-radius: 12px;
                    color: #AFAFAF;
                    display: flex;
                    font-size: 0.75rem /* FIX: minimum 12px agar terbaca di tablet */;
                    justify-content: space-between;
                    margin: 0.5rem 0 0.85rem;
                    padding: 0.65rem 0.78rem;
                }

                .sent-v7-wordcloud-mode-summary strong {
                    color: #FFFFFF;
                    font-weight: 800;
                }

                .sent-v7-wordcloud-card {
                    animation: sentV7WordcloudCardIn 0.42s ease both;
                    background: linear-gradient(180deg, rgba(24,24,24,0.98), rgba(17,17,17,0.98));
                    border: 1px solid #2A2A2A;
                    border-radius: 16px;
                    margin-bottom: 0.58rem;
                    padding: 0.95rem 1rem 0.45rem;
                    transition: border-color 0.22s ease, box-shadow 0.22s ease, transform 0.22s ease;
                }

                .sent-v7-wordcloud-card:hover {
                    transform: translateY(-3px);
                }

                .sent-v7-wordcloud-card--positive:hover {
                    border-color: rgba(76,175,80,0.75);
                    box-shadow: 0 14px 30px rgba(76,175,80,0.14);
                }

                .sent-v7-wordcloud-card--neutral:hover {
                    border-color: rgba(41,121,255,0.75);
                    box-shadow: 0 14px 30px rgba(41,121,255,0.14);
                }

                .sent-v7-wordcloud-card--negative:hover {
                    border-color: rgba(244,67,54,0.75);
                    box-shadow: 0 14px 30px rgba(244,67,54,0.14);
                }

                .sent-v7-wordcloud-title-row {
                    align-items: center;
                    display: flex;
                    justify-content: space-between;
                    gap: 0.65rem;
                }

                .sent-v7-wordcloud-title {
                    color: #F5F5F5;
                    font-family: 'Plus Jakarta Sans', 'Inter', sans-serif;
                    font-size: 0.96rem;
                    font-weight: 780;
                    margin: 0;
                }

                .sent-v7-wordcloud-badge {
                    border-radius: 999px;
                    font-size: 0.75rem /* FIX: minimum 12px agar terbaca di tablet */;
                    font-weight: 800;
                    letter-spacing: 0.08em;
                    padding: 0.34rem 0.62rem;
                    text-transform: uppercase;
                }

                .sent-v7-wordcloud-badge--positive { background: rgba(76,175,80,0.12); border: 1px solid rgba(76,175,80,0.28); color: #A7E3AE; }
                .sent-v7-wordcloud-badge--neutral { background: rgba(41,121,255,0.12); border: 1px solid rgba(41,121,255,0.28); color: #A8C8FF; }
                .sent-v7-wordcloud-badge--negative { background: rgba(244,67,54,0.12); border: 1px solid rgba(244,67,54,0.28); color: #FFB0AA; }

                .sent-v7-wordcloud-subtitle {
                    color: #8F8F8F;
                    font-size: 0.75rem /* FIX: minimum 12px agar terbaca di tablet */;
                    line-height: 1.55;
                    margin: 0.32rem 0 0;
                    min-height: 3.1em; /* Dua baris tetap disediakan agar ketiga kartu sejajar. */
                }

                .sent-v7-wordcloud-note {
                    color: #9E9E9E;
                    font-size: 0.75rem /* FIX: minimum 12px agar terbaca di tablet */;
                    line-height: 1.55;
                    margin: 0.45rem 0 0;
                    min-height: 3.1em; /* Menjaga batas bawah kartu dan posisi WordCloud tetap sama. */
                }

                .sent-v7-wordcloud-focus-wrap {
                    animation: sentV7WordcloudCardIn 0.38s ease both;
                    background: linear-gradient(180deg, rgba(23,23,23,0.98), rgba(17,17,17,0.98));
                    border: 1px solid rgba(255,255,255,0.07);
                    border-radius: 18px;
                    margin-top: 0.2rem;
                    padding: 1rem 1rem 0.7rem;
                }

                .sent-v7-wordcloud-focus-head {
                    align-items: center;
                    display: flex;
                    flex-wrap: wrap;
                    gap: 0.7rem;
                    justify-content: space-between;
                    margin-bottom: 0.6rem;
                }

                .sent-v7-wordcloud-focus-title {
                    color: #FFFFFF;
                    font-family: 'Plus Jakarta Sans', 'Inter', sans-serif;
                    font-size: 1.02rem;
                    font-weight: 800;
                    margin: 0;
                }

                .sent-v7-wordcloud-focus-copy {
                    color: #A0A0A0;
                    font-size: 0.75rem /* FIX: minimum 12px agar terbaca di tablet */;
                    line-height: 1.55;
                    margin: 0.3rem 0 0;
                }

                .sent-v7-wordcloud-focus-stat-row {
                    display: grid;
                    gap: 0.65rem;
                    grid-template-columns: repeat(3, minmax(0, 1fr));
                    margin: 0.75rem 0 0.35rem;
                }

                .sent-v7-wordcloud-focus-stat {
                    background: rgba(255,255,255,0.03);
                    border: 1px solid rgba(255,255,255,0.07);
                    border-radius: 12px;
                    padding: 0.72rem 0.8rem;
                }

                .sent-v7-wordcloud-focus-stat-label {
                    color: #8D8D8D;
                    font-size: 0.75rem /* FIX: minimum 12px agar terbaca di tablet */;
                    font-weight: 700;
                    letter-spacing: 0.05em;
                    margin-bottom: 0.26rem;
                    text-transform: uppercase;
                }

                .sent-v7-wordcloud-focus-stat-value {
                    color: #FFFFFF;
                    font-family: 'Plus Jakarta Sans', 'Inter', sans-serif;
                    font-size: 0.96rem;
                    font-weight: 800;
                }

                .sent-v7-wordcloud-focus-stat-note {
                    color: #8D8D8D;
                    font-size: 0.75rem /* FIX: minimum 12px agar terbaca di tablet */;
                    margin-top: 0.2rem;
                }

                .sent-v7-wordcloud-focus-panel-gap {
                    height: 1.05rem;
                }

                .sent-v7-wordcloud-focus-download-gap {
                    height: 1rem;
                }

                .sent-v7-wordcloud-focus-download-bottom-gap {
                    height: 0.45rem;
                }

                .sent-v7-wordcloud-grid-download-gap {
                    height: 0.9rem;
                }

                .sent-v7-wordcloud-grid-download-bottom-gap {
                    height: 0.3rem;
                }

                @keyframes sentV7WordcloudHeroIn {
                    from { opacity: 0; transform: translateY(14px) scale(0.985); }
                    to { opacity: 1; transform: translateY(0) scale(1); }
                }

                @keyframes sentV7WordcloudCardIn {
                    from { opacity: 0; transform: translateY(10px); }
                    to { opacity: 1; transform: translateY(0); }
                }

                @keyframes sentV7WordcloudPulse {
                    0%,100% { transform: scale(1); box-shadow: 0 0 0 7px rgba(229,57,53,0.10); }
                    50% { transform: scale(1.08); box-shadow: 0 0 0 11px rgba(229,57,53,0.02); }
                }

                @media (max-width: 760px) {
                    .sent-v7-hero {
                        padding: 1.35rem;
                    }

                    .sent-v7-metric-card {
                        min-height: 108px;
                    }

                    .sent-v7-section-heading {
                        align-items: flex-start;
                    }
                }


                /* Fase 7 v3.0 — tombol fullscreen WordCloud dekat dengan gambar */
                div[data-testid="stImage"] {
                    position: relative !important;
                }

                div[data-testid="stImage"] button[title="View fullscreen"],
                div[data-testid="stImage"] button[aria-label="View fullscreen"] {
                    position: absolute !important;
                    top: 0.55rem !important;
                    right: 0.55rem !important;
                    left: auto !important;
                    bottom: auto !important;
                    width: 2.25rem !important;
                    height: 2.25rem !important;
                    min-width: 2.25rem !important;
                    min-height: 2.25rem !important;
                    border: 1px solid rgba(255,255,255,0.13) !important;
                    border-radius: 10px !important;
                    background: rgba(13,13,13,0.78) !important;
                    box-shadow: 0 8px 18px rgba(0,0,0,0.28) !important;
                    backdrop-filter: blur(8px) !important;
                    -webkit-backdrop-filter: blur(8px) !important;
                    opacity: 0 !important;
                    transform: translateY(-3px) scale(0.94) !important;
                    transition: opacity 0.18s ease, transform 0.18s ease, background 0.18s ease, border-color 0.18s ease !important;
                    z-index: 8 !important;
                }

                div[data-testid="stImage"]:hover button[title="View fullscreen"],
                div[data-testid="stImage"]:hover button[aria-label="View fullscreen"],
                div[data-testid="stImage"] button[title="View fullscreen"]:focus-visible,
                div[data-testid="stImage"] button[aria-label="View fullscreen"]:focus-visible {
                    opacity: 1 !important;
                    transform: translateY(0) scale(1) !important;
                }

                div[data-testid="stImage"] button[title="View fullscreen"]:hover,
                div[data-testid="stImage"] button[aria-label="View fullscreen"]:hover {
                    background: rgba(229,57,53,0.90) !important;
                    border-color: rgba(255,145,140,0.72) !important;
                    box-shadow: 0 10px 24px rgba(229,57,53,0.22) !important;
                }

                div[data-testid="stImage"] button[title="View fullscreen"] svg,
                div[data-testid="stImage"] button[aria-label="View fullscreen"] svg {
                    width: 1rem !important;
                    height: 1rem !important;
                    color: #FFFFFF !important;
                    fill: #FFFFFF !important;
                }


                /* Fase 7 v3.1 — dialog fullscreen WordCloud dipusatkan dan diberi white spacing seimbang */
                div[data-baseweb="modal"] {
                    display: flex !important;
                    align-items: center !important;
                    justify-content: center !important;
                    padding: 1.25rem !important;
                }

                div[data-baseweb="modal"] > div {
                    width: min(94vw, 1600px) !important;
                    max-width: 94vw !important;
                    max-height: 94vh !important;
                    margin: 0 auto !important;
                    padding: 1.15rem !important;
                    border-radius: 18px !important;
                    border: 1px solid rgba(255,255,255,0.10) !important;
                    background: rgba(5, 8, 14, 0.96) !important;
                    box-shadow: 0 24px 72px rgba(0,0,0,0.55) !important;
                    overflow: hidden !important;
                }

                div[data-baseweb="modal"] > div > div {
                    width: 100% !important;
                    max-width: 100% !important;
                    height: 100% !important;
                    max-height: calc(94vh - 2.3rem) !important;
                    padding: 0 !important;
                    display: flex !important;
                    align-items: center !important;
                    justify-content: center !important;
                }

                div[data-baseweb="modal"] [data-testid="stImage"] {
                    width: 100% !important;
                    display: flex !important;
                    align-items: center !important;
                    justify-content: center !important;
                    margin: 0 auto !important;
                    padding: 0 !important;
                }

                div[data-baseweb="modal"] [data-testid="stImage"] > div {
                    width: 100% !important;
                    display: flex !important;
                    align-items: center !important;
                    justify-content: center !important;
                }

                div[data-baseweb="modal"] [data-testid="stImage"] img {
                    display: block !important;
                    width: auto !important;
                    height: auto !important;
                    max-width: calc(94vw - 5rem) !important;
                    max-height: calc(94vh - 5rem) !important;
                    object-fit: contain !important;
                    margin: 0 auto !important;
                }

                div[data-baseweb="modal"] button[aria-label="Close"],
                div[data-baseweb="modal"] button[title="Close"] {
                    top: 0.9rem !important;
                    right: 0.9rem !important;
                    z-index: 25 !important;
                }



                /* Fase 7 v3.2 — viewer fullscreen WordCloud custom */
                .sent-v7-wc-viewer {
                    position: relative;
                    width: 100%;
                    border-radius: 14px;
                    overflow: hidden;
                    background: #0E0E0E;
                }

                .sent-v7-wc-viewer-toggle {
                    position: absolute !important;
                    opacity: 0 !important;
                    pointer-events: none !important;
                }

                .sent-v7-wc-inline-image {
                    display: block;
                    width: 100%;
                    height: auto;
                    object-fit: contain;
                    margin: 0 auto;
                }

                .sent-v7-wc-fullscreen-trigger {
                    position: absolute;
                    top: 0.6rem;
                    right: 0.6rem;
                    z-index: 5;
                    width: 2.25rem;
                    height: 2.25rem;
                    display: flex;
                    align-items: center;
                    justify-content: center;
                    border: 1px solid rgba(255,255,255,0.14);
                    border-radius: 10px;
                    background: rgba(13,13,13,0.82);
                    color: #FFFFFF;
                    cursor: pointer;
                    opacity: 0;
                    transform: translateY(-3px) scale(0.94);
                    transition: opacity 0.2s ease, transform 0.2s ease, background 0.2s ease, border-color 0.2s ease;
                    box-shadow: 0 8px 20px rgba(0,0,0,0.3);
                    backdrop-filter: blur(8px);
                    -webkit-backdrop-filter: blur(8px);
                    user-select: none;
                }

                .sent-v7-wc-viewer:hover .sent-v7-wc-fullscreen-trigger,
                .sent-v7-wc-fullscreen-trigger:focus-visible {
                    opacity: 1;
                    transform: translateY(0) scale(1);
                }

                .sent-v7-wc-fullscreen-trigger:hover {
                    background: rgba(229,57,53,0.92);
                    border-color: rgba(255,150,145,0.75);
                }

                .sent-v7-wc-overlay {
                    position: fixed;
                    inset: 0;
                    z-index: 999999;
                    display: none;
                    align-items: center;
                    justify-content: center;
                    box-sizing: border-box;
                    width: 100vw;
                    height: 100vh;
                    padding: 3rem;
                    background: rgba(5, 7, 11, 0.97);
                    backdrop-filter: blur(10px);
                    -webkit-backdrop-filter: blur(10px);
                }

                .sent-v7-wc-viewer-toggle:checked ~ .sent-v7-wc-overlay {
                    display: flex;
                    animation: sentV7WcOverlayIn 0.24s ease both;
                }

                .sent-v7-wc-overlay-image {
                    display: block;
                    width: auto;
                    height: auto;
                    max-width: calc(100vw - 6rem);
                    max-height: calc(100vh - 6rem);
                    object-fit: contain;
                    margin: auto;
                    border-radius: 12px;
                    box-shadow: 0 24px 72px rgba(0,0,0,0.52);
                }

                .sent-v7-wc-overlay-close {
                    position: fixed;
                    top: 1.15rem;
                    right: 1.15rem;
                    z-index: 1000001;
                    width: 2.6rem;
                    height: 2.6rem;
                    display: flex;
                    align-items: center;
                    justify-content: center;
                    border: 1px solid rgba(255,255,255,0.14);
                    border-radius: 12px;
                    background: rgba(20,20,20,0.9);
                    color: #FFFFFF;
                    font-size: 1.3rem;
                    line-height: 1;
                    cursor: pointer;
                    transition: background 0.18s ease, transform 0.18s ease;
                    box-shadow: 0 10px 24px rgba(0,0,0,0.35);
                    user-select: none;
                }

                .sent-v7-wc-overlay-close:hover {
                    background: #E53935;
                    transform: scale(1.04);
                }

                @keyframes sentV7WcOverlayIn {
                    from { opacity: 0; }
                    to { opacity: 1; }
                }

                @media (max-width: 768px) {
                    .sent-v7-wc-overlay {
                        padding: 1.25rem;
                    }

                    .sent-v7-wc-overlay-image {
                        max-width: calc(100vw - 2.5rem);
                        max-height: calc(100vh - 2.5rem);
                    }
                }


            </style>
            """,
            unsafe_allow_html=True,
        )
    except Exception as exc:
        st.error(f"Gaya halaman sentimen gagal dimuat: {exc}")


def _inject_sentiment_light_css() -> None:
    """Terapkan override Light Mode tanpa mengubah struktur halaman Sentimen."""
    if _is_dark_mode():
        return

    try:
        st.markdown(
            """
            <style>
                :root {
                    --sent-light-page: #F6F7F9;
                    --sent-light-card: #FFFFFF;
                    --sent-light-soft: #F8FAFC;
                    --sent-light-soft-2: #F1F5F9;
                    --sent-light-title: #111827;
                    --sent-light-text: #334155;
                    --sent-light-muted: #64748B;
                    --sent-light-border: #DCE3EC;
                    --sent-light-border-strong: #CBD5E1;
                    --sent-light-shadow: 0 12px 28px rgba(15,23,42,0.08);
                }

                /* Hero merah tetap dipertahankan sebagai identitas halaman. */
                .sent-v7-hero {
                    border-color: rgba(255,255,255,0.46) !important;
                    box-shadow: 0 14px 34px rgba(183,28,28,0.18) !important;
                }

                .sent-v7-hero h1,
                .sent-v7-hero p,
                .sent-v7-hero-badge {
                    color: #FFFFFF !important;
                    -webkit-text-fill-color: #FFFFFF !important;
                }

                .sent-v7-hero-badge {
                    background: rgba(95,18,18,0.34) !important;
                    border-color: rgba(255,255,255,0.44) !important;
                }

                /* Panel pemilihan layanan. */
                .sent-v7-selector-wrap {
                    background:
                        radial-gradient(circle at 8% 0%, rgba(229,57,53,0.10), transparent 34%),
                        radial-gradient(circle at 92% 20%, rgba(59,130,246,0.08), transparent 30%),
                        linear-gradient(135deg, #FFFFFF 0%, #F8FAFC 100%) !important;
                    border-color: var(--sent-light-border) !important;
                    box-shadow: var(--sent-light-shadow) !important;
                }

                .sent-v7-selector-label,
                .sent-v7-selector-summary-chip strong {
                    color: var(--sent-light-title) !important;
                    -webkit-text-fill-color: var(--sent-light-title) !important;
                }

                .sent-v7-selector-copy,
                .sent-v7-selector-summary-chip {
                    color: var(--sent-light-muted) !important;
                    -webkit-text-fill-color: var(--sent-light-muted) !important;
                }

                .sent-v7-selector-kicker {
                    color: #C62828 !important;
                }

                .sent-v7-selector-summary-chip {
                    background: rgba(255,255,255,0.88) !important;
                    border-color: var(--sent-light-border) !important;
                }

                div[data-testid="stRadio"] {
                    background: linear-gradient(180deg, #FFFFFF, #F8FAFC) !important;
                    border-color: var(--sent-light-border) !important;
                    box-shadow: var(--sent-light-shadow) !important;
                }

                div[data-testid="stRadio"] div[role="radiogroup"] > label {
                    background: linear-gradient(145deg, #FFFFFF, #F8FAFC) !important;
                    border-color: var(--sent-light-border) !important;
                    color: var(--sent-light-title) !important;
                    box-shadow: 0 8px 20px rgba(15,23,42,0.05) !important;
                }

                div[data-testid="stRadio"] div[role="radiogroup"] > label p {
                    color: var(--sent-light-title) !important;
                    -webkit-text-fill-color: var(--sent-light-title) !important;
                }

                div[data-testid="stRadio"] div[role="radiogroup"] > label:hover {
                    background:
                        radial-gradient(circle at 10% 20%, var(--service-accent-soft), transparent 58%),
                        #FFFFFF !important;
                    color: var(--sent-light-title) !important;
                    box-shadow: 0 14px 30px var(--service-glow) !important;
                }

                div[data-testid="stRadio"] div[role="radiogroup"] > label:has(input:checked) {
                    background:
                        radial-gradient(circle at 10% 16%, var(--service-accent-soft), transparent 64%),
                        linear-gradient(145deg, #FFFFFF, #F8FAFC) !important;
                }

                div[data-testid="stRadio"] div[role="radiogroup"] > label:has(input:checked) p {
                    color: var(--sent-light-title) !important;
                    -webkit-text-fill-color: var(--sent-light-title) !important;
                }

                /* Filter IndiBiz dan tabel hasil. */
                .sent-v17-filter-shell,
                div[data-testid="stForm"] {
                    background: var(--sent-light-card) !important;
                    border-color: var(--sent-light-border) !important;
                    box-shadow: 0 10px 24px rgba(15,23,42,0.06) !important;
                }

                .sent-v17-filter-title {
                    color: var(--sent-light-title) !important;
                }

                .sent-v17-filter-copy {
                    color: var(--sent-light-muted) !important;
                }

                .sent-v17-filter-status {
                    background: #FEF2F2 !important;
                    border-color: #FECACA !important;
                    color: #B91C1C !important;
                }

                .sent-v17-table-wrap,
                .sent-v7-telkomsel-table-wrap,
                .sent-v7-history-table-wrap {
                    background: var(--sent-light-card) !important;
                    border-color: var(--sent-light-border) !important;
                    box-shadow: var(--sent-light-shadow) !important;
                }

                .sent-v17-table th,
                .sent-v7-telkomsel-table th,
                .sent-v7-history-table thead th {
                    background: linear-gradient(180deg, #F8FAFC, #F1F5F9) !important;
                    border-color: var(--sent-light-border) !important;
                    color: #475569 !important;
                    -webkit-text-fill-color: #475569 !important;
                }

                .sent-v17-table td,
                .sent-v7-telkomsel-table td,
                .sent-v7-history-table tbody td {
                    background: #FFFFFF !important;
                    border-color: #E2E8F0 !important;
                    color: var(--sent-light-text) !important;
                    -webkit-text-fill-color: var(--sent-light-text) !important;
                }

                .sent-v17-table tbody tr.sent-positive td {
                    background: #F0FDF4 !important;
                }

                .sent-v17-table tbody tr.sent-neutral td {
                    background: #FFF7ED !important;
                }

                .sent-v17-table tbody tr.sent-negative td {
                    background: #FEF2F2 !important;
                }

                .sent-v17-table tbody tr:hover td,
                .sent-v7-telkomsel-table tbody tr:hover td,
                .sent-v7-history-table tbody tr:hover td {
                    background: #F8FAFC !important;
                    color: var(--sent-light-title) !important;
                    -webkit-text-fill-color: var(--sent-light-title) !important;
                }

                /* Heading dan kartu ringkasan. */
                .sent-v7-section-heading h2 {
                    color: var(--sent-light-title) !important;
                    -webkit-text-fill-color: var(--sent-light-title) !important;
                }

                .sent-v7-section-heading p {
                    color: var(--sent-light-muted) !important;
                    -webkit-text-fill-color: var(--sent-light-muted) !important;
                }

                .sent-v7-section-index {
                    background: #FEF2F2 !important;
                    border-color: #FECACA !important;
                    color: #C62828 !important;
                }

                .sent-v7-metric-card {
                    background: linear-gradient(180deg, #FFFFFF, #F8FAFC) !important;
                    border-color: var(--sent-light-border) !important;
                    border-left-color: var(--metric-color, #E53935) !important;
                    box-shadow: 0 10px 24px rgba(15,23,42,0.07) !important;
                }

                .sent-v7-metric-label {
                    color: #475569 !important;
                }

                .sent-v7-metric-note {
                    color: var(--sent-light-muted) !important;
                }

                /* Panel analitik dan card chart. */
                .sent-v7-platform-shell,
                .sent-v7-platform-chart-card,
                .sent-v11-status-card,
                .sent-v7-chart-card,
                .sent-v7-coming-soon,
                .sent-v7-comment-card,
                .sent-v7-comments-hero,
                .sent-v7-comments-panel,
                .sent-v7-prediction-card,
                .sent-v7-result-box,
                .sent-v7-wordcloud-hero,
                .sent-v7-wordcloud-intro,
                .sent-v7-wordcloud-control-head,
                .sent-v7-wordcloud-mode-summary,
                .sent-v7-wordcloud-card,
                .sent-v7-wordcloud-focus-wrap {
                    background-color: var(--sent-light-card) !important;
                    border-color: var(--sent-light-border) !important;
                    box-shadow: var(--sent-light-shadow) !important;
                }

                .sent-v7-platform-shell {
                    background:
                        radial-gradient(circle at 12% 14%, rgba(229,57,53,0.08), transparent 28%),
                        radial-gradient(circle at 88% 18%, rgba(77,141,255,0.07), transparent 26%),
                        linear-gradient(180deg, #FFFFFF, #F8FAFC) !important;
                }

                .sent-v7-platform-chart-card,
                .sent-v7-chart-card,
                .sent-v7-comments-hero,
                .sent-v7-comments-panel,
                .sent-v7-prediction-card,
                .sent-v7-result-box,
                .sent-v7-wordcloud-hero,
                .sent-v7-wordcloud-card,
                .sent-v7-wordcloud-focus-wrap {
                    background-image:
                        radial-gradient(circle at 92% 0%, rgba(229,57,53,0.055), transparent 30%),
                        linear-gradient(180deg, #FFFFFF, #F8FAFC) !important;
                }

                .sent-v11-status-card {
                    background:
                        radial-gradient(circle at 88% -12%, rgba(229,57,53,0.10), transparent 34%),
                        radial-gradient(circle at 8% 118%, rgba(255,152,0,0.07), transparent 32%),
                        linear-gradient(135deg, #FFFFFF 0%, #F8FAFC 100%) !important;
                }

                .sent-v7-coming-soon,
                .sent-v7-wordcloud-intro,
                .sent-v7-wordcloud-control-head,
                .sent-v7-wordcloud-mode-summary {
                    background-image: linear-gradient(135deg, #FFFFFF, #F8FAFC) !important;
                }

                .sent-v7-platform-title,
                .sent-v7-platform-chart-title,
                .sent-v11-status-title,
                .sent-v11-status-value,
                .sent-v7-chart-title,
                .sent-v7-coming-soon h3,
                .sent-v7-comment-content,
                .sent-v7-comments-hero h3,
                .sent-v7-comments-panel-title,
                .sent-v7-comments-stat-value,
                .sent-v7-manual-title,
                .sent-v7-manual-step-title,
                .sent-v7-manual-input-label,
                .sent-v7-wordcloud-hero-title,
                .sent-v7-wordcloud-control-title,
                .sent-v7-wordcloud-mode-summary strong,
                .sent-v7-wordcloud-title,
                .sent-v7-wordcloud-focus-title,
                .sent-v7-wordcloud-focus-stat-value {
                    color: var(--sent-light-title) !important;
                    -webkit-text-fill-color: var(--sent-light-title) !important;
                }

                .sent-v7-platform-copy,
                .sent-v7-platform-chart-copy,
                .sent-v11-status-subtitle,
                .sent-v11-status-note,
                .sent-v7-chart-subtitle,
                .sent-v7-chart-hint,
                .sent-v7-coming-soon p,
                .sent-v7-comments-hero p,
                .sent-v7-comments-panel-sub,
                .sent-v7-comments-stat-label,
                .sent-v7-comments-stat-note,
                .sent-v7-manual-copy,
                .sent-v7-manual-step-copy,
                .sent-v7-manual-helper,
                .sent-v7-manual-action-note,
                .sent-v7-result-confidence,
                .sent-v7-wordcloud-hero-copy,
                .sent-v7-wordcloud-intro,
                .sent-v7-wordcloud-mode-label,
                .sent-v7-wordcloud-control-copy,
                .sent-v7-wordcloud-mode-summary,
                .sent-v7-wordcloud-subtitle,
                .sent-v7-wordcloud-note,
                .sent-v7-wordcloud-focus-copy,
                .sent-v7-wordcloud-focus-stat-label,
                .sent-v7-wordcloud-focus-stat-note {
                    color: var(--sent-light-muted) !important;
                    -webkit-text-fill-color: var(--sent-light-muted) !important;
                }

                .sent-v7-platform-chip,
                .sent-v7-comments-chip,
                .sent-v7-wordcloud-chip,
                .sent-v11-chip {
                    background: #FFFFFF !important;
                    border-color: var(--sent-light-border) !important;
                    color: var(--sent-light-text) !important;
                    box-shadow: 0 5px 14px rgba(15,23,42,0.04) !important;
                }

                .sent-v7-platform-chip strong,
                .sent-v7-comments-chip strong,
                .sent-v7-wordcloud-chip strong {
                    color: var(--sent-light-title) !important;
                    -webkit-text-fill-color: var(--sent-light-title) !important;
                }

                .sent-v11-status-item,
                .sent-v11-distribution,
                .sent-v7-comments-stat,
                .sent-v7-manual-step,
                .sent-v7-wordcloud-focus-stat {
                    background: var(--sent-light-soft) !important;
                    border-color: var(--sent-light-border) !important;
                }

                .sent-v11-status-label,
                .sent-v11-status-topline,
                .sent-v11-distribution-label {
                    color: #475569 !important;
                }

                .sent-v7-manual-step:hover {
                    background: #FEF2F2 !important;
                    box-shadow: 0 12px 26px rgba(15,23,42,0.08) !important;
                }

                /* Plotly dan kontrol grafik. */
                div[data-testid="stPlotlyChart"] {
                    background: linear-gradient(180deg, #FFFFFF, #F8FAFC) !important;
                    border-color: var(--sent-light-border) !important;
                    box-shadow: var(--sent-light-shadow) !important;
                }

                div[data-testid="stPlotlyChart"]:hover {
                    box-shadow: 0 16px 34px rgba(15,23,42,0.10) !important;
                }

                div[data-testid="stPlotlyChart"] .modebar {
                    background: rgba(255,255,255,0.94) !important;
                    border: 1px solid var(--sent-light-border) !important;
                    border-radius: 8px !important;
                }

                div[data-testid="stPlotlyChart"] .modebar-btn path {
                    fill: #475569 !important;
                }

                div[data-testid="stPlotlyChart"] .modebar-btn:hover path {
                    fill: #C62828 !important;
                }

                /* Tab platform. */
                div[data-testid="stTabs"] [data-baseweb="tab-list"] {
                    background: var(--sent-light-soft) !important;
                    border-color: var(--sent-light-border) !important;
                }

                div[data-testid="stTabs"] button[role="tab"] {
                    color: var(--sent-light-muted) !important;
                    -webkit-text-fill-color: var(--sent-light-muted) !important;
                }

                div[data-testid="stTabs"] button[role="tab"][aria-selected="true"] {
                    background: #E53935 !important;
                    color: #FFFFFF !important;
                    -webkit-text-fill-color: #FFFFFF !important;
                }

                /* Komentar, badge, dan tabel riwayat. */
                .sent-v7-badge-platform,
                .sent-v7-badge-confidence {
                    background: #F1F5F9 !important;
                    border-color: #CBD5E1 !important;
                    color: #475569 !important;
                }

                .sent-v7-badge-positive,
                .sent-v7-history-sentiment.positive {
                    background: #DCFCE7 !important;
                    border-color: #86EFAC !important;
                    color: #166534 !important;
                }

                .sent-v7-badge-neutral,
                .sent-v7-history-sentiment.neutral {
                    background: #FFEDD5 !important;
                    border-color: #FDBA74 !important;
                    color: #9A3412 !important;
                }

                .sent-v7-badge-negative,
                .sent-v7-history-sentiment.negative {
                    background: #FEE2E2 !important;
                    border-color: #FCA5A5 !important;
                    color: #991B1B !important;
                }

                .sent-v7-history-summary-text,
                .sent-v7-history-number,
                .sent-v7-history-time,
                .sent-v7-history-confidence-value {
                    color: var(--sent-light-muted) !important;
                    -webkit-text-fill-color: var(--sent-light-muted) !important;
                }

                .sent-v7-history-text {
                    color: var(--sent-light-text) !important;
                    -webkit-text-fill-color: var(--sent-light-text) !important;
                }

                .sent-v7-history-confidence-track {
                    background: #E2E8F0 !important;
                }

                /* Prediksi manual dan input. */
                div[data-testid="stTextArea"] textarea {
                    background: #FFFFFF !important;
                    border-color: var(--sent-light-border-strong) !important;
                    color: var(--sent-light-title) !important;
                    -webkit-text-fill-color: var(--sent-light-title) !important;
                    caret-color: #E53935 !important;
                    box-shadow: inset 0 1px 2px rgba(15,23,42,0.04) !important;
                }

                div[data-testid="stTextArea"] textarea::placeholder {
                    color: #94A3B8 !important;
                    -webkit-text-fill-color: #94A3B8 !important;
                    opacity: 1 !important;
                }

                div[data-testid="stTextArea"] textarea:focus {
                    background: #FFFFFF !important;
                    border-color: #E53935 !important;
                    box-shadow: 0 0 0 3px rgba(229,57,53,0.12), 0 12px 24px rgba(15,23,42,0.07) !important;
                }

                /* Expander dan isi riwayat. */
                div[data-testid="stExpander"],
                div[data-testid="stExpander"] details,
                div[data-testid="stExpander"] [data-testid="stExpanderDetails"] {
                    background: var(--sent-light-card) !important;
                    border-color: var(--sent-light-border) !important;
                    color: var(--sent-light-text) !important;
                }

                div[data-testid="stExpander"] summary {
                    background: linear-gradient(90deg, #FEF2F2, #FFFFFF 42%) !important;
                    border-color: transparent !important;
                    color: var(--sent-light-title) !important;
                }

                div[data-testid="stExpander"] details[open] > summary {
                    background: linear-gradient(90deg, #FEE2E2, #FFFFFF 46%) !important;
                    border-bottom-color: var(--sent-light-border) !important;
                }

                div[data-testid="stExpander"] summary:hover {
                    background: linear-gradient(90deg, #FEE2E2, #F8FAFC 48%) !important;
                }

                div[data-testid="stExpander"] summary p,
                div[data-testid="stExpander"] summary span {
                    color: var(--sent-light-title) !important;
                    -webkit-text-fill-color: var(--sent-light-title) !important;
                }

                div[data-testid="stExpander"] summary svg {
                    color: #C62828 !important;
                    fill: currentColor !important;
                }

                /* WordCloud dan viewer fullscreen. */
                .sent-v7-wc-viewer {
                    background: #FFFFFF !important;
                    border: 1px solid var(--sent-light-border) !important;
                }

                .sent-v7-wc-fullscreen-trigger,
                div[data-testid="stImage"] button[title="View fullscreen"],
                div[data-testid="stImage"] button[aria-label="View fullscreen"] {
                    background: rgba(255,255,255,0.94) !important;
                    border-color: var(--sent-light-border-strong) !important;
                    color: #334155 !important;
                    box-shadow: 0 8px 20px rgba(15,23,42,0.12) !important;
                }

                .sent-v7-wc-fullscreen-trigger:hover,
                div[data-testid="stImage"] button[title="View fullscreen"]:hover,
                div[data-testid="stImage"] button[aria-label="View fullscreen"]:hover {
                    background: #E53935 !important;
                    border-color: #E53935 !important;
                    color: #FFFFFF !important;
                }

                div[data-testid="stImage"] button[title="View fullscreen"] svg,
                div[data-testid="stImage"] button[aria-label="View fullscreen"] svg {
                    color: currentColor !important;
                    fill: currentColor !important;
                }

                div[data-baseweb="modal"] > div {
                    background: rgba(248,250,252,0.98) !important;
                    border-color: var(--sent-light-border) !important;
                    box-shadow: 0 24px 72px rgba(15,23,42,0.22) !important;
                }

                .sent-v7-wc-overlay {
                    background: rgba(248,250,252,0.97) !important;
                }

                .sent-v7-wc-overlay-image {
                    background: #FFFFFF !important;
                    box-shadow: 0 24px 72px rgba(15,23,42,0.20) !important;
                }

                .sent-v7-wc-overlay-close {
                    background: rgba(255,255,255,0.95) !important;
                    border-color: var(--sent-light-border-strong) !important;
                    color: #334155 !important;
                    box-shadow: 0 10px 24px rgba(15,23,42,0.14) !important;
                }

                .sent-v7-wc-overlay-close:hover {
                    background: #E53935 !important;
                    color: #FFFFFF !important;
                }

                /* Teks umum Streamlit yang berada di halaman Sentimen. */
                div[data-testid="stTextArea"] label,
                div[data-testid="stCaptionContainer"],
                div[data-testid="stMarkdownContainer"] {
                    color: var(--sent-light-text);
                }
            </style>
            """,
            unsafe_allow_html=True,
        )
    except Exception as exc:
        st.error(f"Gaya Light Mode halaman sentimen gagal dimuat: {exc}")



def _section_heading(number: str, title: str, subtitle: str = "") -> None:
    """Render judul section yang konsisten."""
    try:
        subtitle_html = f"<p>{escape(subtitle)}</p>" if subtitle else ""
        st.markdown(
            f"""
            <div class="sent-v7-section-heading">
                <span class="sent-v7-section-index">{escape(number)}</span>
                <div>
                    <h2>{escape(title)}</h2>
                    {subtitle_html}
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )
    except Exception as exc:
        st.error(f"Judul bagian gagal ditampilkan: {exc}")


def _render_hero(data_source: str, layanan_aktif: str) -> None:
    """Render hero banner halaman Analisis Sentimen untuk layanan aktif."""
    try:
        source_badge = "Data Real" if "Real" in data_source else "Data Dummy"
        st.markdown(
            f"""
            <div class="sent-v7-page">
                <section class="sent-v7-hero">
                    <h1>Analisis Sentimen Publik</h1>
                    <p>
                        Memahami kecenderungan opini publik layanan Telkom Group dari
                        Twitter/X, Instagram, dan TikTok menggunakan hasil klasifikasi
                        sentimen pada dataset penelitian.
                    </p>
                    <div class="sent-v7-hero-badges">
                        <span class="sent-v7-hero-badge">IndiHome • Data & model siap</span>
                        <span class="sent-v7-hero-badge">IndiBiz • Data & model siap</span>
                        <span class="sent-v7-hero-badge">Telkomsel • Data & model siap</span>
                        <span class="sent-v7-hero-badge">{escape(layanan_aktif)} • {escape(source_badge)}</span>
                    </div>
                </section>
            </div>
            """,
            unsafe_allow_html=True,
        )
    except Exception as exc:
        st.error(f"Banner halaman gagal ditampilkan: {exc}")


# -----------------------------------------------------------------------------
# Persiapan data
# -----------------------------------------------------------------------------
def _prepare_dataframe(layanan: str) -> pd.DataFrame:
    """Muat dan rapikan DataFrame sentimen dari data loader proyek."""
    try:
        layanan_label = str(layanan).strip()
        if bool(st.session_state.get("demo_mode", False)):
            df = get_demo_sentiment(layanan_label).copy()
        elif layanan_label == "IndiHome":
            df = load_indihome_sentiment().copy()
        elif layanan_label == "IndiBiz":
            df = load_indibiz_sentiment().copy()
        elif layanan_label == "Telkomsel":
            telkomsel_path = _project_root() / "data" / "telkomsel_sentiment.csv"
            if telkomsel_path.is_file():
                df = load_telkomsel_sentiment(telkomsel_path).copy()
            else:
                st.info(
                    "Data Telkomsel sedang disiapkan. Silakan jalankan pipeline "
                    "terlebih dahulu. Untuk sementara, dashboard menampilkan "
                    "data dummy agar halaman tetap dapat dibuka."
                )
                df = get_dummy_sentiment_data("Telkomsel").copy()
        else:
            st.info("Layanan belum dikenali. Dashboard menampilkan halaman kosong secara aman.")
            return pd.DataFrame()

        if df is None or df.empty:
            # Perlindungan tingkat halaman. Jika cache atau file aktual bermasalah,
            # Analisis Sentimen tetap dirender memakai fallback lokal.
            st.warning(
                f"Data {layanan_label} tidak menghasilkan baris valid. "
                "Dashboard memakai data dummy sementara agar halaman tetap dapat dibuka."
            )
            df = get_dummy_sentiment_data(layanan_label).copy()
        if df is None or df.empty:
            return pd.DataFrame()

        required_defaults: dict[str, Any] = {
            "content": "",
            "username": "anonim",
            "platform": "lainnya",
            "predicted_sentiment": "neutral",
            "confidence": 0.0,
            "followers": 0,
        }
        for column, default in required_defaults.items():
            if column not in df.columns:
                df[column] = default

        date_column = "date_created" if "date_created" in df.columns else "date"
        if date_column not in df.columns:
            df["date_created"] = pd.NaT
        elif pd.api.types.is_datetime64_any_dtype(df[date_column]):
            df["date_created"] = pd.to_datetime(df[date_column], errors="coerce")
        else:
            df["date_created"] = pd.to_datetime(
                df[date_column], errors="coerce", dayfirst=True, format="mixed"
            )

        confidence_column = (
            "confidence_score" if "confidence_score" in df.columns else "confidence"
        )
        df["confidence_score"] = pd.to_numeric(
            df[confidence_column], errors="coerce"
        ).fillna(0.0).clip(lower=0.0, upper=1.0)

        df["predicted_sentiment"] = df["predicted_sentiment"].apply(
            _normalize_sentiment
        )
        df["platform"] = df["platform"].apply(_normalize_platform)
        df = df[df["platform"].isin(["twitter", "instagram", "tiktok"])].copy()
        df["content"] = df["content"].fillna("").astype(str)
        df["username"] = (
            df["username"].fillna("anonim").astype(str).str.replace("'", "", regex=False)
        )
        df["followers"] = pd.to_numeric(
            df["followers"], errors="coerce"
        ).fillna(0).astype(int)

        df = df[df["content"].str.strip().ne("")].copy()
        return df.reset_index(drop=True)
    except Exception as exc:
        st.error(f"Data sentimen belum dapat disiapkan: {exc}")
        return pd.DataFrame()


def _sentiment_summary(df: pd.DataFrame) -> dict[str, float | int | str]:
    """Hitung total, jumlah, persentase, dan sentimen dominan."""
    try:
        total = int(len(df))
        counts = (
            df["predicted_sentiment"].value_counts().reindex(_SENTIMENT_ORDER, fill_value=0)
            if total > 0
            else pd.Series([0, 0, 0], index=_SENTIMENT_ORDER)
        )
        dominant = str(counts.idxmax()) if total > 0 else "neutral"
        return {
            "total": total,
            "positive_count": int(counts.get("positive", 0)),
            "neutral_count": int(counts.get("neutral", 0)),
            "negative_count": int(counts.get("negative", 0)),
            "positive_pct": (float(counts.get("positive", 0)) / total * 100) if total else 0.0,
            "neutral_pct": (float(counts.get("neutral", 0)) / total * 100) if total else 0.0,
            "negative_pct": (float(counts.get("negative", 0)) / total * 100) if total else 0.0,
            "dominant": dominant,
        }
    except Exception as exc:
        st.error(f"Ringkasan sentimen gagal dihitung: {exc}")
        return {
            "total": 0,
            "positive_count": 0,
            "neutral_count": 0,
            "negative_count": 0,
            "positive_pct": 0.0,
            "neutral_pct": 0.0,
            "negative_pct": 0.0,
            "dominant": "neutral",
        }


# -----------------------------------------------------------------------------
# Komponen metric
# -----------------------------------------------------------------------------
def _metric_card(label: str, value: str, note: str, color: str) -> None:
    """Render satu metric card kustom."""
    try:
        st.markdown(
            f"""
            <div class="sent-v7-metric-card" style="--metric-color:{escape(color)};">
                <div class="sent-v7-metric-label">{escape(label)}</div>
                <div class="sent-v7-metric-value">{escape(value)}</div>
                <div class="sent-v7-metric-note">{escape(note)}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
    except Exception as exc:
        st.error(f"Kartu metrik gagal ditampilkan: {exc}")


def _render_overview_metrics(df: pd.DataFrame) -> None:
    """Render empat metric card overview."""
    try:
        summary = _sentiment_summary(df)
        columns = st.columns(4)
        metric_items = [
            (
                "Total Data",
                _format_number(summary["total"]),
                "Komentar yang dianalisis",
                "#E53935",
            ),
            (
                "% Positif",
                f"{summary['positive_pct']:.1f}%",
                f"{_format_number(summary['positive_count'])} komentar positif",
                "#4CAF50",
            ),
            (
                "% Netral",
                f"{summary['neutral_pct']:.1f}%",
                f"{_format_number(summary['neutral_count'])} komentar netral",
                "#FF9800",
            ),
            (
                "% Negatif",
                f"{summary['negative_pct']:.1f}%",
                f"{_format_number(summary['negative_count'])} komentar negatif",
                "#F44336",
            ),
        ]
        for column, item in zip(columns, metric_items):
            with column:
                _metric_card(*item)
    except Exception as exc:
        st.error(f"Metric overview gagal ditampilkan: {exc}")


# -----------------------------------------------------------------------------
# Builder chart Plotly
# -----------------------------------------------------------------------------
def _base_layout(fig: go.Figure, height: int, show_legend: bool = True) -> go.Figure:
    """Terapkan layout Plotly transparan dan konsisten."""
    try:
        theme = _chart_theme()
        fig.update_layout(
            template="plotly_dark" if _is_dark_mode() else "plotly_white",
            font={"family": "Inter, sans-serif", "color": theme["text"]},
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
            height=height,
            margin={"l": 34, "r": 18, "t": 30, "b": 38},
            hoverlabel={
                "bgcolor": theme["hover_bg"],
                "bordercolor": theme["hover_border"],
                "font": {"color": theme["text"], "family": "Inter, sans-serif"},
            },
            legend={
                "orientation": "h",
                "yanchor": "bottom",
                "y": 1.02,
                "xanchor": "right",
                "x": 1,
                "font": {"size": 11, "color": theme["text"]},
                "bgcolor": "rgba(0,0,0,0)",
                "visible": show_legend,
            },
        )
        fig.update_xaxes(
            showgrid=False,
            zeroline=False,
            color=theme["muted"],
            linecolor=theme["grid"],
            title_font={"color": theme["muted"]},
        )
        fig.update_yaxes(
            showgrid=True,
            gridcolor=theme["grid"],
            zeroline=False,
            color=theme["muted"],
            linecolor=theme["grid"],
            title_font={"color": theme["muted"]},
        )
        return fig
    except Exception as exc:
        st.error(f"Gaya grafik gagal diterapkan: {exc}")
        return fig


def _empty_figure(message: str, height: int = 360) -> go.Figure:
    """Buat figure kosong dengan pesan informatif."""
    fig = go.Figure()
    fig.add_annotation(
        text=message,
        x=0.5,
        y=0.5,
        xref="paper",
        yref="paper",
        showarrow=False,
        font={"family": "Inter, sans-serif", "size": 13, "color": "#777777"},
    )
    return _base_layout(fig, height=height, show_legend=False)


def _donut_sentiment(df: pd.DataFrame) -> go.Figure:
    """Buat donut interaktif yang stabil melalui hover dan legenda Plotly."""
    try:
        summary = _sentiment_summary(df)
        values = [
            int(summary["positive_count"]),
            int(summary["neutral_count"]),
            int(summary["negative_count"]),
        ]
        if sum(values) == 0:
            return _empty_figure("Data sentimen belum tersedia")

        dominant = str(summary["dominant"])
        dominant_pct = float(summary[f"{dominant}_pct"])
        labels = [SENTIMENT_LABELS[item] for item in _SENTIMENT_ORDER]
        colors = [SENTIMENT_COLORS[item] for item in _SENTIMENT_ORDER]
        default_pull = [0.022, 0.022, 0.022]

        fig = go.Figure(
            go.Pie(
                labels=labels,
                values=values,
                hole=0.68,
                sort=False,
                direction="clockwise",
                rotation=270,
                pull=default_pull,
                marker={
                    "colors": colors,
                    "line": {"color": "#111722", "width": 3},
                },
                textinfo="percent",
                textfont={
                    "family": "Plus Jakarta Sans, Inter, sans-serif",
                    "size": 12,
                    "color": "#FFFFFF",
                },
                insidetextorientation="horizontal",
                customdata=[
                    [SENTIMENT_LABELS[item], values[index]]
                    for index, item in enumerate(_SENTIMENT_ORDER)
                ],
                hovertemplate=(
                    "<b>%{customdata[0]}</b><br>"
                    "Jumlah komentar: %{customdata[1]:,}<br>"
                    "Proporsi: %{percent}<br>"
                    "<span style='color:#AFAFAF'>Klik legenda untuk menyaring</span>"
                    "<extra></extra>"
                ),
            )
        )
        fig.add_annotation(
            x=0.5,
            y=0.55,
            text=f"<b>{SENTIMENT_LABELS[dominant]}</b>",
            showarrow=False,
            font={
                "family": "Plus Jakarta Sans, Inter, sans-serif",
                "size": 21,
                "color": SENTIMENT_COLORS[dominant],
            },
        )
        fig.add_annotation(
            x=0.5,
            y=0.445,
            text=f"Dominan • {dominant_pct:.1f}%",
            showarrow=False,
            font={"family": "Inter, sans-serif", "size": 11, "color": "#B7BDC7"},
        )
        fig.add_annotation(
            x=0.5,
            y=0.36,
            text=f"{_format_number(sum(values))} komentar",
            showarrow=False,
            font={"family": "Inter, sans-serif", "size": 9, "color": "#666F7D"},
        )

        # Kontrol tombol animasi dihapus karena properti ``pull`` pada Pie tidak
        # bertransisi konsisten di seluruh browser. Interaksi tetap tersedia
        # melalui hover serta klik legenda tanpa memicu redraw atau flicker.

        fig = _base_layout(fig, height=440, show_legend=True)
        fig.update_traces(domain={"x": [0.04, 0.96], "y": [0.18, 0.91]})
        fig.update_layout(
            margin={"l": 18, "r": 18, "t": 74, "b": 94},
            transition={"duration": 260, "easing": "cubic-in-out"},
            clickmode="event+select",
            uirevision="sent_v7_donut_interaktif_v15",
            legend={
                "orientation": "h",
                "yanchor": "top",
                "y": -0.09,
                "xanchor": "center",
                "x": 0.5,
                "font": {"size": 11, "color": "#F3F4F6"},
                "bgcolor": "rgba(17,23,34,0.72)",
                "bordercolor": "rgba(255,255,255,0.08)",
                "borderwidth": 1,
                "itemclick": "toggle",
                "itemdoubleclick": "toggleothers",
            },
        )
        return fig
    except Exception as exc:
        st.error(f"Donut chart gagal dibuat: {exc}")
        return _empty_figure("Donut chart gagal dibuat")

def _grouped_bar_platform(df: pd.DataFrame) -> go.Figure:
    """Buat grouped bar stabil dengan hover rinci dan sorotan klik."""
    try:
        if df.empty:
            return _empty_figure("Data platform belum tersedia")

        grouped = (
            df.groupby(["platform", "predicted_sentiment"], dropna=False)
            .size()
            .unstack(fill_value=0)
        )
        platform_order = [
            platform for platform in ["twitter", "instagram", "tiktok"]
            if platform in grouped.index
        ]
        platform_order.extend(
            platform for platform in grouped.index if platform not in platform_order
        )
        grouped = grouped.reindex(platform_order)
        display_platforms = [
            _PLATFORM_LABELS.get(item, str(item).title()) for item in grouped.index
        ]
        platform_totals = grouped.sum(axis=1).replace(0, 1)

        fig = go.Figure()
        for sentiment in _SENTIMENT_ORDER:
            counts = (
                grouped[sentiment].astype(float).tolist()
                if sentiment in grouped.columns
                else [0.0] * len(grouped)
            )
            percentages = [
                (count / float(platform_totals.iloc[index])) * 100
                for index, count in enumerate(counts)
            ]
            customdata = [
                [int(counts[index]), percentages[index]]
                for index in range(len(display_platforms))
            ]
            fig.add_trace(
                go.Bar(
                    name=SENTIMENT_LABELS[sentiment],
                    x=display_platforms,
                    y=counts,
                    marker={
                        "color": SENTIMENT_COLORS[sentiment],
                        "line": {"color": "rgba(255,255,255,0.16)", "width": 1},
                        "opacity": 0.94,
                    },
                    selected={"marker": {"opacity": 1}},
                    unselected={"marker": {"opacity": 0.34}},
                    text=[_format_number(value) if value else "" for value in counts],
                    textposition="outside",
                    textfont={
                        "family": "Plus Jakarta Sans, Inter, sans-serif",
                        "size": 10,
                        "color": "#F5F5F5",
                    },
                    cliponaxis=False,
                    customdata=customdata,
                    hovertemplate=(
                        "<b>%{x}</b><br>"
                        "Sentimen: " + SENTIMENT_LABELS[sentiment] + "<br>"
                        "Jumlah: %{customdata[0]:,}<br>"
                        "Proporsi platform: %{customdata[1]:.1f}%<br>"
                        "<span style='color:#AFAFAF'>Klik batang untuk menyorot</span>"
                        "<extra></extra>"
                    ),
                )
            )

        fig.update_layout(
            barmode="group",
            bargap=0.26,
            bargroupgap=0.07,
            barcornerradius=7,
            xaxis_title="Platform",
            yaxis_title="Jumlah komentar",
        )

        # Mode pergantian jumlah/persentase dihapus. Perubahan nilai sekaligus
        # perubahan skala sumbu Y membuat Plotly menampilkan frame perantara yang
        # menyesatkan (batang sempat mendekati 100%). Grafik dipertahankan pada
        # mode jumlah; persentase tetap tersedia lengkap pada tooltip hover.

        fig = _base_layout(fig, height=440, show_legend=True)
        fig.update_layout(
            margin={"l": 58, "r": 22, "t": 74, "b": 112},
            hovermode="closest",
            clickmode="event+select",
            transition={"duration": 260, "easing": "cubic-in-out"},
            uirevision="sent_v7_bar_interaktif_v15",
            legend={
                "orientation": "h",
                "yanchor": "top",
                "y": -0.24,
                "xanchor": "center",
                "x": 0.5,
                "font": {"size": 11, "color": "#F3F4F6"},
                "bgcolor": "rgba(17,23,34,0.72)",
                "bordercolor": "rgba(255,255,255,0.08)",
                "borderwidth": 1,
                "itemclick": "toggle",
                "itemdoubleclick": "toggleothers",
            },
        )
        fig.update_xaxes(
            tickfont={"family": "Inter, sans-serif", "size": 11, "color": "#ECEFF4"},
            title_standoff=12,
        )
        fig.update_yaxes(
            tickfont={"family": "Inter, sans-serif", "size": 10, "color": "#B7BDC7"},
            title_standoff=10,
        )
        return fig
    except Exception as exc:
        st.error(f"Grouped bar chart gagal dibuat: {exc}")
        return _empty_figure("Grouped bar chart gagal dibuat")


def _apply_indibiz_platform_filter() -> None:
    """Simpan pilihan platform dan siapkan loading custom untuk tombol Terapkan."""
    try:
        selected = str(
            st.session_state.get(_INDIBIZ_FILTER_DRAFT_KEY, "Semua Platform")
        )
        if selected not in _INDIBIZ_PLATFORM_OPTIONS:
            selected = "Semua Platform"
        st.session_state[_INDIBIZ_FILTER_APPLIED_KEY] = selected
        st.session_state[_INDIBIZ_FILTER_LOADING_KEY] = (
            f"Menerapkan filter {selected} pada analisis IndiBiz..."
        )
    except Exception as exc:
        st.error(f"Filter platform belum dapat diterapkan: {exc}")


def _reset_indibiz_platform_filter() -> None:
    """Kembalikan filter platform IndiBiz ke seluruh platform."""
    try:
        st.session_state[_INDIBIZ_FILTER_DRAFT_KEY] = "Semua Platform"
        st.session_state[_INDIBIZ_FILTER_APPLIED_KEY] = "Semua Platform"
        st.session_state[_INDIBIZ_FILTER_LOADING_KEY] = (
            "Mengembalikan analisis IndiBiz ke semua platform..."
        )
    except Exception as exc:
        st.error(f"Filter platform belum dapat direset: {exc}")


def _filter_indibiz_platform(df: pd.DataFrame, selected_label: str) -> pd.DataFrame:
    """Ambil subset IndiBiz berdasarkan platform yang sudah diterapkan."""
    try:
        platform_key = _INDIBIZ_PLATFORM_OPTIONS.get(selected_label, "all")
        if platform_key == "all":
            return df.copy().reset_index(drop=True)
        return df[df["platform"] == platform_key].copy().reset_index(drop=True)
    except Exception as exc:
        st.error(f"Data IndiBiz gagal difilter berdasarkan platform: {exc}")
        return df.copy().reset_index(drop=True)


def _render_indibiz_platform_filter(df: pd.DataFrame) -> pd.DataFrame:
    """Render filter platform IndiBiz dan kembalikan data yang sudah diterapkan."""
    try:
        st.session_state.setdefault(_INDIBIZ_FILTER_DRAFT_KEY, "Semua Platform")
        st.session_state.setdefault(_INDIBIZ_FILTER_APPLIED_KEY, "Semua Platform")

        applied_label = str(
            st.session_state.get(_INDIBIZ_FILTER_APPLIED_KEY, "Semua Platform")
        )
        if applied_label not in _INDIBIZ_PLATFORM_OPTIONS:
            applied_label = "Semua Platform"
            st.session_state[_INDIBIZ_FILTER_APPLIED_KEY] = applied_label

        filtered = _filter_indibiz_platform(df, applied_label)
        st.markdown(
            f"""
            <div class="sent-v17-filter-shell">
                <div>
                    <div class="sent-v17-filter-title">Filter Platform IndiBiz</div>
                    <div class="sent-v17-filter-copy">
                        Filter ini mengubah tiga grafik dan tabel 10 komentar teratas.
                    </div>
                </div>
                <div class="sent-v17-filter-status">
                    Aktif: {escape(applied_label)} • {_format_number(len(filtered))} komentar
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        with st.form("sent_v17_indibiz_platform_form", clear_on_submit=False):
            col_select, col_apply, col_reset = st.columns([2.3, 1.0, 1.0], gap="small")
            with col_select:
                st.selectbox(
                    "Platform",
                    options=list(_INDIBIZ_PLATFORM_OPTIONS.keys()),
                    key=_INDIBIZ_FILTER_DRAFT_KEY,
                    help="Pilih platform, lalu tekan Terapkan Filter.",
                )
            with col_apply:
                st.markdown("<div style='height:28px'></div>", unsafe_allow_html=True)
                st.form_submit_button(
                    "Terapkan Filter",
                    type="primary",
                    use_container_width=True,
                    on_click=_apply_indibiz_platform_filter,
                )
            with col_reset:
                st.markdown("<div style='height:28px'></div>", unsafe_allow_html=True)
                st.form_submit_button(
                    "Reset Filter",
                    use_container_width=True,
                    on_click=_reset_indibiz_platform_filter,
                )

        return filtered
    except Exception as exc:
        st.error(f"Filter platform IndiBiz gagal ditampilkan: {exc}")
        return df.copy().reset_index(drop=True)


def _indibiz_phase17_distribution_stats(df: pd.DataFrame) -> dict[str, Any]:
    """Hitung data visualisasi Cell [15] IndiBiz tanpa mengubah DataFrame sumber."""
    try:
        source = df.copy(deep=True)
        if source.empty:
            return {
                "total": 0,
                "counts": {item: 0 for item in _SENTIMENT_ORDER},
                "percentages": {item: 0.0 for item in _SENTIMENT_ORDER},
                "average_confidence": {item: 0.0 for item in _SENTIMENT_ORDER},
            }

        if "predicted_sentiment" not in source.columns:
            source["predicted_sentiment"] = "neutral"
        if "confidence_score" not in source.columns:
            confidence_column = "confidence" if "confidence" in source.columns else None
            source["confidence_score"] = (
                source[confidence_column] if confidence_column else 0.0
            )

        source["predicted_sentiment"] = source["predicted_sentiment"].apply(
            _normalize_sentiment
        )
        source["confidence_score"] = pd.to_numeric(
            source["confidence_score"], errors="coerce"
        ).fillna(0.0).clip(lower=0.0, upper=1.0)

        counts_series = (
            source["predicted_sentiment"]
            .value_counts()
            .reindex(_SENTIMENT_ORDER, fill_value=0)
        )
        average_series = (
            source.groupby("predicted_sentiment")["confidence_score"]
            .mean()
            .reindex(_SENTIMENT_ORDER, fill_value=0.0)
            .round(4)
        )
        total = int(counts_series.sum())

        counts = {item: int(counts_series.get(item, 0)) for item in _SENTIMENT_ORDER}
        percentages = {
            item: (counts[item] / total * 100.0) if total else 0.0
            for item in _SENTIMENT_ORDER
        }
        average_confidence = {
            item: float(average_series.get(item, 0.0))
            for item in _SENTIMENT_ORDER
        }
        return {
            "total": total,
            "counts": counts,
            "percentages": percentages,
            "average_confidence": average_confidence,
        }
    except Exception as exc:
        st.error(f"Ringkasan visualisasi Fase 17 IndiBiz gagal dihitung: {exc}")
        return {
            "total": 0,
            "counts": {item: 0 for item in _SENTIMENT_ORDER},
            "percentages": {item: 0.0 for item in _SENTIMENT_ORDER},
            "average_confidence": {item: 0.0 for item in _SENTIMENT_ORDER},
        }


def _indibiz_phase17_count_bar(df: pd.DataFrame) -> go.Figure:
    """Buat bar chart jumlah komentar untuk visualisasi Fase 17 IndiBiz."""
    try:
        stats = _indibiz_phase17_distribution_stats(df)
        counts = stats["counts"]
        values = [int(counts[item]) for item in _SENTIMENT_ORDER]
        if sum(values) == 0:
            return _empty_figure("Data sentimen IndiBiz belum tersedia", height=360)

        fig = go.Figure(
            go.Bar(
                x=[SENTIMENT_LABELS[item] for item in _SENTIMENT_ORDER],
                y=values,
                marker={
                    "color": [SENTIMENT_COLORS[item] for item in _SENTIMENT_ORDER],
                    "line": {"width": 0},
                },
                text=[_format_number(value) for value in values],
                textposition="outside",
                textfont={"size": 12},
                cliponaxis=False,
                hovertemplate="%{x}<br>%{y:,} komentar<extra></extra>",
            )
        )
        fig.update_layout(
            xaxis_title="Sentimen",
            yaxis_title="Jumlah komentar",
            bargap=0.34,
        )
        max_value = max(values) if values else 0
        fig.update_yaxes(range=[0, max(1.0, max_value * 1.18)])
        return _base_layout(fig, height=360, show_legend=False)
    except Exception as exc:
        st.error(f"Bar chart jumlah sentimen IndiBiz gagal dibuat: {exc}")
        return _empty_figure("Bar chart jumlah gagal dibuat", height=360)


def _indibiz_phase17_percentage_pie(df: pd.DataFrame) -> go.Figure:
    """Buat pie chart persentase sentimen untuk visualisasi Fase 17 IndiBiz."""
    try:
        stats = _indibiz_phase17_distribution_stats(df)
        counts = stats["counts"]
        values = [int(counts[item]) for item in _SENTIMENT_ORDER]
        if sum(values) == 0:
            return _empty_figure("Data sentimen IndiBiz belum tersedia", height=360)

        fig = go.Figure(
            go.Pie(
                labels=[SENTIMENT_LABELS[item] for item in _SENTIMENT_ORDER],
                values=values,
                hole=0.4,
                sort=False,
                direction="clockwise",
                rotation=90,
                marker={
                    "colors": [SENTIMENT_COLORS[item] for item in _SENTIMENT_ORDER],
                    "line": {"color": "#171717", "width": 2},
                },
                textinfo="label+percent",
                textfont={"size": 11, "color": "#FFFFFF"},
                hovertemplate="%{label}<br>%{value:,} komentar<br>%{percent}<extra></extra>",
            )
        )
        return _base_layout(fig, height=360, show_legend=True)
    except Exception as exc:
        st.error(f"Pie chart persentase sentimen IndiBiz gagal dibuat: {exc}")
        return _empty_figure("Pie chart persentase gagal dibuat", height=360)


def _indibiz_phase17_confidence_bar(df: pd.DataFrame) -> go.Figure:
    """Buat bar chart confidence rata-rata untuk visualisasi Fase 17 IndiBiz."""
    try:
        stats = _indibiz_phase17_distribution_stats(df)
        averages = stats["average_confidence"]
        values = [float(averages[item]) for item in _SENTIMENT_ORDER]
        if int(stats["total"]) == 0:
            return _empty_figure("Data confidence IndiBiz belum tersedia", height=360)

        fig = go.Figure(
            go.Bar(
                x=[SENTIMENT_LABELS[item] for item in _SENTIMENT_ORDER],
                y=values,
                marker={
                    "color": [SENTIMENT_COLORS[item] for item in _SENTIMENT_ORDER],
                    "line": {"width": 0},
                },
                text=[f"{value:.3f}" for value in values],
                textposition="outside",
                textfont={"size": 12},
                cliponaxis=False,
                hovertemplate="%{x}<br>Confidence rata-rata: %{y:.4f}<extra></extra>",
            )
        )
        fig.update_layout(
            xaxis_title="Sentimen",
            yaxis_title="Confidence rata-rata",
            bargap=0.34,
        )
        fig.update_yaxes(range=[0, 1.0], tickformat=".1f")
        return _base_layout(fig, height=360, show_legend=False)
    except Exception as exc:
        st.error(f"Bar chart confidence IndiBiz gagal dibuat: {exc}")
        return _empty_figure("Bar chart confidence gagal dibuat", height=360)


def _render_indibiz_phase17_visualization(df: pd.DataFrame) -> pd.DataFrame:
    """Render tiga grafik utama IndiBiz dan kembalikan data hasil filter."""
    try:
        filtered_df = _render_indibiz_platform_filter(df)
        stats = _indibiz_phase17_distribution_stats(filtered_df)
        counts = stats["counts"]
        percentages = stats["percentages"]
        averages = stats["average_confidence"]

        if filtered_df.empty:
            st.warning(
                "Tidak ada komentar IndiBiz pada platform yang dipilih. "
                "Tekan Reset Filter untuk kembali ke semua platform."
            )

        st.markdown(
            """
            <div class="sent-v7-chart-card">
                <div class="sent-v7-chart-title">Distribusi Sentimen IndiBiz</div>
                <div class="sent-v7-chart-subtitle">Hasil klasifikasi IndoBERT pada data yang lolos filter platform.</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        top_left, top_right = st.columns(2, gap="medium")
        top_specs = [
            (
                top_left,
                "Jumlah Komentar per Sentimen",
                "Batang menunjukkan jumlah komentar positif, netral, dan negatif.",
                _indibiz_phase17_count_bar(filtered_df),
                "sent_v17_indibiz_count",
            ),
            (
                top_right,
                "Persentase Sentimen",
                "Donut menunjukkan proporsi tiga kelas sentimen dari total data terfilter.",
                _indibiz_phase17_percentage_pie(filtered_df),
                "sent_v17_indibiz_percentage",
            ),
        ]
        for column, title, subtitle, figure, key in top_specs:
            with column:
                st.markdown(
                    f"""
                    <div class="sent-v7-chart-card">
                        <div class="sent-v7-chart-title">{escape(title)}</div>
                        <div class="sent-v7-chart-subtitle">{escape(subtitle)}</div>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )
                _plotly_chart(figure, key)

        st.markdown(
            """
            <div class="sent-v7-chart-card">
                <div class="sent-v7-chart-title">Confidence Score Rata-rata</div>
                <div class="sent-v7-chart-subtitle">Sumbu Y menggunakan skala 0,0 sampai 1,0.</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
        _plotly_chart(
            _indibiz_phase17_confidence_bar(filtered_df),
            "sent_v17_indibiz_confidence",
        )

        summary_parts = []
        for sentiment in _SENTIMENT_ORDER:
            summary_parts.append(
                f'<span class="sent-v11-chip" style="--chip-color:{SENTIMENT_COLORS[sentiment]};">'
                f'{escape(SENTIMENT_LABELS[sentiment])} '
                f'<strong>{escape(_format_number(counts[sentiment]))}</strong> '
                f'({percentages[sentiment]:.1f}%) • conf {averages[sentiment]:.3f}</span>'
            )

        st.markdown(
            '<div class="sent-v11-distribution">'
            + "".join(summary_parts)
            + "</div>",
            unsafe_allow_html=True,
        )
        st.caption(
            "Gunakan ikon kamera pada pojok kanan atas grafik Plotly untuk menyimpan PNG."
        )
        return filtered_df
    except Exception as exc:
        st.error(f"Visualisasi sentimen IndiBiz Fase 17 gagal ditampilkan: {exc}")
        return df.copy().reset_index(drop=True)


def _timeline_sentiment(df: pd.DataFrame) -> go.Figure:
    """Buat line chart tren sentimen dari waktu ke waktu."""
    try:
        timeline_df = df.dropna(subset=["date_created"]).copy()
        if timeline_df.empty:
            return _empty_figure("Kolom tanggal belum tersedia", height=410)

        timeline_df["tanggal"] = pd.to_datetime(
            timeline_df["date_created"], errors="coerce"
        ).dt.normalize()
        daily = (
            timeline_df.groupby(["tanggal", "predicted_sentiment"])
            .size()
            .unstack(fill_value=0)
            .sort_index()
        )
        if daily.empty:
            return _empty_figure("Data tren waktu belum tersedia", height=410)

        full_range = pd.date_range(daily.index.min(), daily.index.max(), freq="D")
        daily = daily.reindex(full_range, fill_value=0)

        fig = go.Figure()
        for sentiment in _SENTIMENT_ORDER:
            values = daily[sentiment] if sentiment in daily.columns else pd.Series(0, index=daily.index)
            fig.add_trace(
                go.Scatter(
                    x=daily.index,
                    y=values,
                    name=SENTIMENT_LABELS[sentiment],
                    mode="lines+markers",
                    line={"color": SENTIMENT_COLORS[sentiment], "width": 2.6},
                    marker={
                        "size": 6,
                        "color": SENTIMENT_COLORS[sentiment],
                        "line": {"color": "#171717", "width": 1},
                    },
                    hovertemplate=(
                        "%{x|%d %b %Y}<br>"
                        + SENTIMENT_LABELS[sentiment]
                        + ": %{y:,}<extra></extra>"
                    ),
                )
            )

        fig.update_layout(
            hovermode="x unified",
            xaxis_title="Tanggal",
            yaxis_title="Jumlah komentar",
        )
        fig.update_xaxes(tickformat="%d %b", rangeslider={"visible": False})

        # Gunakan layout dasar terlebih dahulu, kemudian override khusus legenda
        # grafik tren agar presisi berada di tengah atas tanpa memengaruhi chart lain.
        fig = _base_layout(fig, height=410, show_legend=True)
        fig.update_layout(
            margin={"l": 34, "r": 18, "t": 58, "b": 38},
            legend={
                "orientation": "h",
                "yanchor": "bottom",
                "y": 1.025,
                "xanchor": "center",
                "x": 0.5,
                "font": {
                    "size": 11,
                    "color": _chart_theme()["text"],
                    "family": "Inter, sans-serif",
                },
                "bgcolor": "rgba(0,0,0,0)",
                "borderwidth": 0,
                "itemsizing": "constant",
                "traceorder": "normal",
            },
        )
        return fig
    except Exception as exc:
        st.error(f"Line chart tren waktu gagal dibuat: {exc}")
        return _empty_figure("Line chart gagal dibuat", height=410)



def _platform_pie(df: pd.DataFrame, platform: str) -> go.Figure:
    """Buat donut chart distribusi sentimen untuk satu platform."""
    try:
        subset = df[df["platform"] == platform]
        counts = (
            subset["predicted_sentiment"]
            .value_counts()
            .reindex(_SENTIMENT_ORDER, fill_value=0)
        )
        total = int(counts.sum())
        platform_label = _PLATFORM_LABELS.get(platform, platform.title())
        if total == 0:
            return _empty_figure(
                f"Belum ada data {platform_label}",
                height=390,
            )

        dominant = str(counts.idxmax())
        dominant_label = SENTIMENT_LABELS.get(dominant, dominant.title())
        dominant_pct = (float(counts.get(dominant, 0)) / total * 100) if total else 0.0

        fig = go.Figure(
            go.Pie(
                labels=[SENTIMENT_LABELS[item] for item in _SENTIMENT_ORDER],
                values=[int(counts[item]) for item in _SENTIMENT_ORDER],
                hole=0.56,
                sort=False,
                direction="clockwise",
                marker={
                    "colors": [SENTIMENT_COLORS[item] for item in _SENTIMENT_ORDER],
                    "line": {"color": "#0E1320", "width": 3},
                },
                textinfo="label+percent",
                textposition="inside",
                textfont={"size": 11, "color": "#FFFFFF"},
                insidetextorientation="horizontal",
                hovertemplate=(
                    "%{label}<br>"
                    + f"Platform: {platform_label}<br>"
                    + "%{value:,} komentar<br>%{percent}<extra></extra>"
                ),
                pull=[0.0, 0.0, 0.0],
            )
        )

        fig.add_annotation(
            x=0.5,
            y=0.52,
            xref="paper",
            yref="paper",
            showarrow=False,
            align="center",
            text=(
                f"<b style='font-size:17px;color:#FFFFFF'>{platform_label}</b>"
                f"<br><span style='font-size:12px;color:#FFB567'>Dominan · {dominant_label}</span>"
                f"<br><span style='font-size:0.75rem /* FIX: minimum 12px agar terbaca di tablet */;color:#8F8F8F'>{dominant_pct:.1f}% · {_format_number(total)} komentar</span>"
            ),
        )

        fig = _base_layout(fig, height=390, show_legend=True)
        fig.update_layout(
            margin={"l": 24, "r": 24, "t": 22, "b": 82},
            legend={
                "orientation": "h",
                "yanchor": "top",
                "y": -0.08,
                "xanchor": "center",
                "x": 0.5,
                "font": {"size": 12, "color": _chart_theme()["text"]},
                "bgcolor": "rgba(0,0,0,0)",
                "title": {"text": ""},
                "traceorder": "normal",
            },
            uniformtext_minsize=10,
            uniformtext_mode="hide",
            transition={"duration": 360, "easing": "cubic-in-out"},
            hovermode="closest",
        )
        return fig
    except Exception as exc:
        st.error(f"Pie chart platform gagal dibuat: {exc}")
        return _empty_figure("Pie chart gagal dibuat", height=390)


def _probability_bar(probabilities: dict[str, float]) -> go.Figure:
    """Buat bar horizontal probabilitas dengan legenda warna sentimen."""
    try:
        fig = go.Figure()

        # Setiap sentimen dibuat sebagai trace terpisah agar Plotly
        # dapat menampilkan legenda yang sesuai dengan warna batang.
        for sentiment in _SENTIMENT_ORDER:
            label = SENTIMENT_LABELS[sentiment]
            value = _safe_float(probabilities.get(sentiment, 0.0))

            fig.add_trace(
                go.Bar(
                    x=[value],
                    y=[label],
                    name=label,
                    orientation="h",
                    marker={
                        "color": SENTIMENT_COLORS[sentiment],
                        "line": {"width": 0},
                    },
                    text=[f"{value:.1%}"],
                    textposition="outside",
                    cliponaxis=False,
                    hovertemplate=f"{label}: %{{x:.2%}}<extra></extra>",
                    showlegend=True,
                )
            )

        fig.update_layout(
            xaxis_title="Probabilitas",
            yaxis_title="",
            barmode="overlay",
        )
        fig.update_xaxes(range=[0, 1.08], tickformat=".0%")
        fig.update_yaxes(
            autorange="reversed",
            showgrid=False,
            categoryorder="array",
            categoryarray=[
                SENTIMENT_LABELS[item]
                for item in _SENTIMENT_ORDER
            ],
        )

        fig = _base_layout(fig, height=320, show_legend=True)
        fig.update_layout(
            margin={"l": 34, "r": 18, "t": 72, "b": 38},
            legend={
                "orientation": "h",
                "yanchor": "bottom",
                "y": 1.08,
                "xanchor": "center",
                "x": 0.5,
                "font": {
                    "size": 12,
                    "color": _chart_theme()["text"],
                },
                "bgcolor": "rgba(0,0,0,0)",
                "title": {"text": ""},
            },
        )
        return fig
    except Exception as exc:
        st.error(f"Bar probabilitas gagal dibuat: {exc}")
        return _empty_figure("Bar probabilitas gagal dibuat", height=320)


def _render_indibiz_phase11_status() -> None:
    """Tampilkan status output prediksi batch IndoBERT khusus IndiBiz."""
    try:
        status = get_indibiz_prediction_status()
        ready = bool(status.get("ready", False))
        file_found = bool(status.get("file_found", False))
        source_name = str(status.get("source_name", "Tidak ditemukan"))
        total_rows = int(status.get("total_rows_dashboard", 0) or 0)
        raw_rows = int(status.get("total_rows_file", 0) or 0)
        removed_rows = int(status.get("removed_rows", 0) or 0)
        overall_confidence = _safe_float(status.get("overall_average_confidence", 0.0))
        platform_counts = status.get("platform_counts", {}) or {}
        sentiment_counts = status.get("sentiment_counts", {}) or {}
        average_confidence = status.get("average_confidence", {}) or {}

        badge_class = "sent-v11-status-badge" if ready else "sent-v11-status-badge sent-v11-status-badge--warning"
        badge_text = "Output valid" if ready else ("File perlu diperiksa" if file_found else "Menunggu file")
        row_note = (
            f"{_format_number(raw_rows)} baris di file; {_format_number(removed_rows)} tersaring"
            if raw_rows
            else "Belum ada output CSV aktual"
        )
        platform_total = sum(int(platform_counts.get(item, 0) or 0) for item in ("twitter", "instagram", "tiktok"))
        platform_note = (
            f"X {_format_number(platform_counts.get('twitter', 0))} • IG {_format_number(platform_counts.get('instagram', 0))} • TikTok {_format_number(platform_counts.get('tiktok', 0))}"
            if platform_total
            else "Twitter/X, Instagram, dan TikTok"
        )
        confidence_note = (
            f"Rentang {float(status.get('confidence_min', 0.0)):.1%}–{float(status.get('confidence_max', 0.0)):.1%}"
            if ready
            else "Nilai valid harus berada pada rentang 0–1"
        )
        file_note = "Output CSV utama" if bool(status.get("is_canonical_name")) else "Nama file perlu disesuaikan"

        st.markdown(
            f"""
            <section class="sent-v11-status-card">
                <div class="sent-v11-status-head">
                    <div class="sent-v11-status-heading">
                        <div class="sent-v11-status-kicker">IndoBERT Analytics</div>
                        <h3 class="sent-v11-status-title">Status Output IndoBERT IndiBiz</h3>
                        <p class="sent-v11-status-subtitle">
                            Ringkasan kesiapan data prediksi batch untuk analisis sentimen dan visualisasi dashboard.
                        </p>
                    </div>
                    <span class="{badge_class}"><span class="sent-v11-status-dot"></span>{escape(badge_text)}</span>
                </div>
                <div class="sent-v11-status-grid">
                    <div class="sent-v11-status-item" style="--stat-accent:#E53935;">
                        <div class="sent-v11-status-topline">
                            <div class="sent-v11-status-label">File sumber</div>
                            <span class="sent-v11-stat-icon">CSV</span>
                        </div>
                        <div class="sent-v11-status-value">{escape(source_name)}</div>
                        <div class="sent-v11-status-note">{escape(file_note)}</div>
                    </div>
                    <div class="sent-v11-status-item" style="--stat-accent:#FFB020;">
                        <div class="sent-v11-status-topline">
                            <div class="sent-v11-status-label">Data siap dashboard</div>
                            <span class="sent-v11-stat-icon">DATA</span>
                        </div>
                        <div class="sent-v11-status-value">{escape(_format_number(total_rows))}</div>
                        <div class="sent-v11-status-note">{escape(row_note)}</div>
                    </div>
                    <div class="sent-v11-status-item" style="--stat-accent:#4D8DFF;">
                        <div class="sent-v11-status-topline">
                            <div class="sent-v11-status-label">Cakupan platform</div>
                            <span class="sent-v11-stat-icon">3×</span>
                        </div>
                        <div class="sent-v11-status-value">{escape(_format_number(platform_total))}</div>
                        <div class="sent-v11-status-note">{escape(platform_note)}</div>
                    </div>
                    <div class="sent-v11-status-item" style="--stat-accent:#58C46B;">
                        <div class="sent-v11-status-topline">
                            <div class="sent-v11-status-label">Rata-rata confidence</div>
                            <span class="sent-v11-stat-icon">AI</span>
                        </div>
                        <div class="sent-v11-status-value">{overall_confidence:.1%}</div>
                        <div class="sent-v11-status-note">{escape(confidence_note)}</div>
                    </div>
                </div>
                <div class="sent-v11-distribution">
                    <span class="sent-v11-distribution-label">Distribusi sentimen</span>
                    <span class="sent-v11-chip" style="--chip-color:#4CAF50;">Positif <strong>{escape(_format_number(sentiment_counts.get('positive', 0)))}</strong> • conf {float(average_confidence.get('positive', 0.0)):.1%}</span>
                    <span class="sent-v11-chip" style="--chip-color:#FF9800;">Netral <strong>{escape(_format_number(sentiment_counts.get('neutral', 0)))}</strong> • conf {float(average_confidence.get('neutral', 0.0)):.1%}</span>
                    <span class="sent-v11-chip" style="--chip-color:#F44336;">Negatif <strong>{escape(_format_number(sentiment_counts.get('negative', 0)))}</strong> • conf {float(average_confidence.get('negative', 0.0)):.1%}</span>
                </div>
            </section>
            """,
            unsafe_allow_html=True,
        )

        if not ready:
            if file_found:
                missing = status.get("missing_columns", []) or []
                detail = f" Kolom yang belum tersedia: {', '.join(map(str, missing))}." if missing else ""
                st.warning(
                    "File IndiBiz ditemukan, tetapi belum lolos pemeriksaan output."
                    + detail
                    + " Dashboard tetap menggunakan data dummy agar halaman tidak crash."
                )
            else:
                st.info(
                    "Letakkan file hasil prediksi bernama indibiz_output_sentiment.csv "
                    "di folder data proyek, lalu restart Streamlit."
                )
    except Exception as exc:
        st.error(f"Status output prediksi batch IndiBiz gagal ditampilkan: {exc}")


# -----------------------------------------------------------------------------
# Section layanan dan coming soon
# -----------------------------------------------------------------------------
def _sinkronkan_layanan_sentimen_saat_masuk() -> None:
    """Selaraskan selector Sentimen dengan layanan aktif lintas halaman."""
    try:
        if st.session_state.get("_active_service_sync_target") != "Analisis Sentimen":
            return
        layanan = str(st.session_state.get("active_service", "IndiHome")).strip()
        if layanan not in _LAYANAN_LIST:
            layanan = "IndiHome"
        st.session_state["sent_v7_service_selector"] = layanan
        st.session_state.pop("_active_service_sync_target", None)
    except Exception as exc:
        st.error(f"Sinkronisasi layanan sentimen belum dapat dilakukan: {exc}")


def _queue_service_switch_loading() -> None:
    """Siapkan overlay custom sebelum rerun pergantian layanan dimulai."""
    try:
        layanan_baru = str(
            st.session_state.get("sent_v7_service_selector", "IndiHome")
        ).strip()
        if layanan_baru not in _LAYANAN_LIST:
            layanan_baru = "IndiHome"
            st.session_state["sent_v7_service_selector"] = "IndiHome"

        st.session_state["active_service"] = layanan_baru
        st.session_state[_SERVICE_SWITCH_LOADING_KEY] = (
            f"Memuat analisis sentimen {layanan_baru}..."
        )
    except Exception as exc:
        # Callback tidak boleh menghentikan perpindahan layanan.
        st.session_state.pop(_SERVICE_SWITCH_LOADING_KEY, None)
        st.session_state[_PREDICTION_ERROR_KEY] = (
            f"Loading pergantian layanan belum dapat disiapkan: {exc}"
        )


def _queue_wordcloud_view_loading() -> None:
    """Siapkan overlay custom sebelum mode WordCloud dirender ulang."""
    try:
        mode = str(
            st.session_state.get("sent_v7_wordcloud_view_mode", "Semua")
        ).strip() or "Semua"
        allowed_modes = {
            "Semua",
            "Fokus Positif",
            "Fokus Netral",
            "Fokus Negatif",
        }
        if mode not in allowed_modes:
            mode = "Semua"
            st.session_state["sent_v7_wordcloud_view_mode"] = mode

        loading_labels = {
            "Semua": "Menyiapkan seluruh WordCloud sentimen...",
            "Fokus Positif": "Menyiapkan WordCloud fokus positif...",
            "Fokus Netral": "Menyiapkan WordCloud fokus netral...",
            "Fokus Negatif": "Menyiapkan WordCloud fokus negatif...",
        }
        st.session_state[_WORDCLOUD_VIEW_LOADING_KEY] = loading_labels[mode]
    except Exception as exc:
        # Callback tidak boleh menghentikan perubahan mode WordCloud.
        st.session_state.pop(_WORDCLOUD_VIEW_LOADING_KEY, None)
        st.session_state[_PREDICTION_ERROR_KEY] = (
            f"Loading WordCloud belum dapat disiapkan: {exc}"
        )


def _queue_wordcloud_download_loading(sentiment_label: str) -> None:
    """Siapkan overlay custom sebelum rerun setelah tombol download diklik."""
    try:
        label = str(sentiment_label).strip() or "WordCloud"
        st.session_state[_WORDCLOUD_DOWNLOAD_LOADING_KEY] = (
            f"Menyiapkan unduhan WordCloud {label}..."
        )
    except Exception as exc:
        # Kegagalan callback tidak boleh menggagalkan proses unduhan.
        st.session_state.pop(_WORDCLOUD_DOWNLOAD_LOADING_KEY, None)
        st.session_state[_PREDICTION_ERROR_KEY] = (
            f"Loading unduhan WordCloud belum dapat disiapkan: {exc}"
        )


def _render_service_selector() -> str:
    """Render selector layanan berbentuk kartu interaktif."""
    try:
        st.markdown(
            """
            <section class="sent-v7-selector-wrap" aria-label="Panel pemilihan layanan">
                <div class="sent-v7-selector-head">
                    <div>
                        <div class="sent-v7-selector-kicker">
                            <span class="sent-v7-selector-live-dot"></span>
                            01 · Pilihan Analitik
                        </div>
                        <div class="sent-v7-selector-label">Pilih layanan yang ingin dianalisis</div>
                        <p class="sent-v7-selector-copy">
                            Klik salah satu kartu layanan. Dashboard akan memperbarui data,
                            ringkasan, dan seluruh visualisasi secara otomatis.
                        </p>
                    </div>
                    <div class="sent-v7-selector-summary" aria-label="Ringkasan ketersediaan layanan">
                        <span class="sent-v7-selector-summary-chip"><strong>3</strong> data aktif</span>
                        <span class="sent-v7-selector-summary-chip"><strong>3</strong> model siap</span>
                        <span class="sent-v7-selector-summary-chip"><strong>3</strong> platform</span>
                    </div>
                </div>
            </section>
            """,
            unsafe_allow_html=True,
        )
        return st.radio(
            "Layanan",
            options=_LAYANAN_LIST,
            index=0,
            horizontal=True,
            label_visibility="collapsed",
            key="sent_v7_service_selector",
            on_change=_queue_service_switch_loading,
            format_func=lambda item: (
                f"🏠 {item} · Data & prediksi"
                if item == "IndiHome"
                else (
                    f"📡 {item} · Data & prediksi"
                    if item == "Telkomsel"
                    else f"💼 {item} · Data & prediksi"
                )
            ),
        )
    except Exception as exc:
        st.error(f"Selector layanan gagal ditampilkan: {exc}")
        return "IndiHome"


def _render_coming_soon(layanan: str) -> None:
    """Render fallback informatif jika layanan belum memiliki data analitik."""
    try:
        st.markdown(
            f"""
            <div class="sent-v7-coming-soon">
                <h3>Prediksi manual {escape(layanan)} segera hadir</h3>
                <p>
                    Model prediksi manual untuk layanan ini belum diaktifkan.
                    Dashboard tetap menampilkan analitik data tanpa memakai model layanan lain
                    agar hasil penelitian tetap valid dan tidak menyesatkan.
                </p>
            </div>
            """,
            unsafe_allow_html=True,
        )
    except Exception as exc:
        st.error(f"Kartu fallback layanan gagal ditampilkan: {exc}")


# -----------------------------------------------------------------------------
# Section visualisasi
# -----------------------------------------------------------------------------
def _render_main_visualizations(df: pd.DataFrame) -> None:
    """Render donut dan grouped bar dalam dua kolom."""
    try:
        left, right = st.columns([0.92, 1.38], gap="medium")
        with left:
            st.markdown(
                """
                <div class="sent-v7-chart-card sent-v7-chart-card--donut">
                    <div class="sent-v7-chart-kicker">
                        <span class="sent-v7-chart-kicker-dot"></span>
                        Komposisi Sentimen
                    </div>
                    <div class="sent-v7-chart-title">Distribusi Sentimen</div>
                    <div class="sent-v7-chart-subtitle">
                        Proporsi positif, netral, dan negatif pada seluruh percakapan Telkomsel.
                    </div>
                    <div class="sent-v7-chart-hint">
                        Pilih tombol sorotan atau klik legenda untuk berinteraksi.
                    </div>
                </div>
                """,
                unsafe_allow_html=True,
            )
            _plotly_chart(_donut_sentiment(df), "sent_v7_donut_main")

        with right:
            st.markdown(
                """
                <div class="sent-v7-chart-card sent-v7-chart-card--bar">
                    <div class="sent-v7-chart-kicker">
                        <span class="sent-v7-chart-kicker-dot"></span>
                        Perbandingan Platform
                    </div>
                    <div class="sent-v7-chart-title">Sentimen per Platform</div>
                    <div class="sent-v7-chart-subtitle">
                        Bandingkan Twitter/X, Instagram, dan TikTok berdasarkan jumlah atau persentase.
                    </div>
                    <div class="sent-v7-chart-hint">
                        Ubah mode grafik, arahkan kursor, atau klik batang untuk menyorot.
                    </div>
                </div>
                """,
                unsafe_allow_html=True,
            )
            _plotly_chart(_grouped_bar_platform(df), "sent_v7_grouped_platform")
    except Exception as exc:
        st.error(f"Visualisasi utama gagal ditampilkan: {exc}")


def _render_timeline(df: pd.DataFrame) -> None:
    """Render chart tren waktu lebar penuh."""
    try:
        st.markdown(
            """
            <div class="sent-v7-chart-card">
                <div class="sent-v7-chart-title">Perubahan Sentimen dari Waktu ke Waktu</div>
                <div class="sent-v7-chart-subtitle">Arah percakapan harian selama periode penelitian</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
        _plotly_chart(_timeline_sentiment(df), "sent_v7_timeline")
    except Exception as exc:
        st.error(f"Tren waktu gagal ditampilkan: {exc}")




def _render_platform_snapshot(platform: str, summary: dict[str, Any]) -> None:
    """Render panel ringkas yang lebih hidup untuk tiap platform."""
    try:
        platform_label = _PLATFORM_LABELS.get(platform, platform.title())
        dominant = _normalize_sentiment(summary.get("dominant", "neutral"))
        dominant_label = SENTIMENT_LABELS.get(dominant, dominant.title())
        total = _format_number(summary.get("total", 0))
        st.markdown(
            f"""
            <section class="sent-v7-platform-shell">
                <div class="sent-v7-platform-top">
                    <div>
                        <div class="sent-v7-platform-kicker">
                            <span class="sent-v7-platform-kicker-dot"></span>
                            Insight Platform
                        </div>
                        <h3 class="sent-v7-platform-title">Snapshot {escape(platform_label)}</h3>
                        <p class="sent-v7-platform-copy">
                            Distribusi sentimen khusus {escape(platform_label)} dengan tampilan yang lebih fokus,
                            interaktif, dan mudah dibaca untuk membandingkan opini publik.
                        </p>
                    </div>
                    <div class="sent-v7-platform-chip-row">
                        <span class="sent-v7-platform-chip"><strong>{escape(total)}</strong> komentar</span>
                        <span class="sent-v7-platform-chip sent-v7-platform-chip--{escape(dominant)}">Dominan <strong>{escape(dominant_label)}</strong></span>
                        <span class="sent-v7-platform-chip sent-v7-platform-chip--positive">Positif <strong>{float(summary.get('positive_pct', 0.0)):.1f}%</strong></span>
                        <span class="sent-v7-platform-chip sent-v7-platform-chip--neutral">Netral <strong>{float(summary.get('neutral_pct', 0.0)):.1f}%</strong></span>
                        <span class="sent-v7-platform-chip sent-v7-platform-chip--negative">Negatif <strong>{float(summary.get('negative_pct', 0.0)):.1f}%</strong></span>
                    </div>
                </div>
            </section>
            """,
            unsafe_allow_html=True,
        )
    except Exception as exc:
        st.error(f"Snapshot platform gagal ditampilkan: {exc}")


def _render_platform_tabs(df: pd.DataFrame) -> None:
    """Render tiga tab platform berisi metric kecil dan donut chart yang lebih hidup."""
    try:
        st.markdown(
            """
            <section class="sent-v7-platform-hero">
                <div class="sent-v7-platform-hero-top">
                    <div>
                        <div class="sent-v7-platform-kicker">
                            <span class="sent-v7-platform-kicker-dot"></span>
                            Platform insight
                        </div>
                        <h3>Bandingkan suasana percakapan di tiap platform</h3>
                        <p>
                            Pindah tab untuk melihat proporsi sentimen, metrik ringkas, dan distribusi visual Twitter/X,
                            Instagram, serta TikTok secara lebih fokus.
                        </p>
                    </div>
                </div>
            </section>
            """,
            unsafe_allow_html=True,
        )

        tabs = st.tabs(["Twitter/X", "Instagram", "TikTok"])
        platform_keys = ["twitter", "instagram", "tiktok"]

        for tab, platform in zip(tabs, platform_keys):
            with tab:
                subset = df[df["platform"] == platform].copy()
                summary = _sentiment_summary(subset)
                dominant = str(summary.get("dominant", "neutral"))
                dominant_label = SENTIMENT_LABELS.get(dominant, dominant.title())
                dominant_pct = float(summary.get(f"{dominant}_pct", 0.0))
                platform_label = _PLATFORM_LABELS.get(platform, platform.title())

                metric_columns = st.columns(4)
                metric_items = [
                    (
                        "Total",
                        _format_number(summary["total"]),
                        "Komentar",
                        "#E53935",
                    ),
                    (
                        "Positif",
                        f"{summary['positive_pct']:.1f}%",
                        _format_number(summary["positive_count"]),
                        "#4CAF50",
                    ),
                    (
                        "Netral",
                        f"{summary['neutral_pct']:.1f}%",
                        _format_number(summary["neutral_count"]),
                        "#FF9800",
                    ),
                    (
                        "Negatif",
                        f"{summary['negative_pct']:.1f}%",
                        _format_number(summary["negative_count"]),
                        "#F44336",
                    ),
                ]
                for column, item in zip(metric_columns, metric_items):
                    with column:
                        _metric_card(*item)

                st.markdown(
                    '<div class="sent-v7-platform-section-gap" aria-hidden="true"></div>',
                    unsafe_allow_html=True,
                )

                st.markdown(
                    f"""
                    <section class="sent-v7-chart-card" aria-label="Distribusi {escape(platform_label)}">
                        <div class="sent-v7-chart-kicker">
                            <span class="sent-v7-chart-kicker-dot"></span>
                            Snapshot {escape(platform_label)}
                        </div>
                        <h3 class="sent-v7-chart-title">Distribusi sentimen {escape(platform_label)}</h3>
                        <p class="sent-v7-chart-subtitle">
                            Sorot irisan untuk melihat detail komentar. Sentimen dominan saat ini adalah
                            <strong>{escape(dominant_label)}</strong> dengan porsi <strong>{dominant_pct:.1f}%</strong>.
                        </p>
                        <div class="sent-v7-chart-hint">Legenda diposisikan presisi di tengah bawah dan tetap interaktif saat diklik.</div>
                    </section>
                    """,
                    unsafe_allow_html=True,
                )

                _plotly_chart(
                    _platform_pie(df, platform),
                    f"sent_v7_platform_pie_{platform}",
                )
    except Exception as exc:
        st.error(f"Tab per platform gagal ditampilkan: {exc}")


# -----------------------------------------------------------------------------
# Section contoh komentar
# -----------------------------------------------------------------------------
def _preview_comment(text: Any, limit: int = 80) -> str:
    """Potong komentar menjadi maksimal 80 karakter termasuk tanda elipsis."""
    try:
        cleaned = " ".join(str(text or "").split())
        if len(cleaned) <= limit:
            return cleaned
        return cleaned[: max(0, limit - 3)].rstrip() + "..."
    except Exception:
        return ""


def _render_indibiz_top_comments_table(df: pd.DataFrame) -> None:
    """Render 10 komentar IndiBiz dengan confidence tertinggi dan warna per sentimen."""
    try:
        if df.empty:
            st.info("Belum ada komentar yang dapat ditampilkan untuk filter aktif.")
            return

        source = df.copy()
        if "confidence_score" not in source.columns:
            source["confidence_score"] = 0.0
        if "predicted_sentiment" not in source.columns:
            source["predicted_sentiment"] = "neutral"
        source["confidence_score"] = pd.to_numeric(
            source["confidence_score"], errors="coerce"
        ).fillna(0.0).clip(0.0, 1.0)
        source["predicted_sentiment"] = source["predicted_sentiment"].apply(
            _normalize_sentiment
        )
        top_rows = source.sort_values(
            ["confidence_score"], ascending=[False], kind="stable"
        ).head(10)

        rows_html: list[str] = []
        for number, (_, row) in enumerate(top_rows.iterrows(), start=1):
            sentiment = _normalize_sentiment(row.get("predicted_sentiment"))
            platform = _normalize_platform(row.get("platform"))
            full_comment = " ".join(str(row.get("content", "")).split())
            preview = _preview_comment(full_comment, limit=80)
            confidence = _safe_float(row.get("confidence_score"), 0.0)
            rows_html.append(
                f'<tr class="sent-{escape(sentiment)}">'
                f'<td>{number}</td>'
                f'<td>{escape(str(row.get("username", "anonim")))}</td>'
                f'<td>{escape(_PLATFORM_LABELS.get(platform, platform.title()))}</td>'
                f'<td class="sent-v17-comment-cell" title="{escape(full_comment)}">{escape(preview)}</td>'
                f'<td>{_sentiment_badge_html(sentiment)}</td>'
                f'<td class="sent-v17-confidence">{confidence:.3f}</td>'
                '</tr>'
            )

        table_html = (
            '<div class="sent-v17-table-wrap">'
            '<table class="sent-v17-table">'
            '<thead><tr>'
            '<th>No</th><th>Username</th><th>Platform</th>'
            '<th>Komentar</th><th>Sentimen</th><th>Confidence</th>'
            '</tr></thead>'
            f'<tbody>{"".join(rows_html)}</tbody>'
            '</table></div>'
        )
        st.markdown(table_html, unsafe_allow_html=True)
        st.caption(
            f"Menampilkan {len(top_rows)} komentar dengan confidence tertinggi. "
            "Arahkan kursor ke komentar untuk melihat teks lengkap."
        )
    except Exception as exc:
        st.error(f"Tabel komentar IndiBiz gagal ditampilkan: {exc}")


def _sentiment_badge_html(sentiment: str) -> str:
    """Kembalikan HTML badge sentimen."""
    normalized = _normalize_sentiment(sentiment)
    return (
        f'<span class="sent-v7-badge sent-v7-badge-{normalized}">'
        f'{escape(_SENTIMENT_ICONS[normalized])} '
        f'{escape(SENTIMENT_LABELS[normalized])}</span>'
    )


def _platform_badge_html(platform: str) -> str:
    """Kembalikan HTML badge platform."""
    normalized = _normalize_platform(platform)
    icon = _PLATFORM_ICONS.get(normalized, "◉")
    label = _PLATFORM_LABELS.get(normalized, normalized.title())
    return (
        '<span class="sent-v7-badge sent-v7-badge-platform">'
        f'{escape(icon)} {escape(label)}</span>'
    )


def _render_comment_card(row: pd.Series) -> None:
    """Render satu kartu komentar yang aman dari HTML injection."""
    try:
        sentiment = _normalize_sentiment(row.get("predicted_sentiment", "neutral"))
        platform = _normalize_platform(row.get("platform", "lainnya"))
        confidence = _safe_float(row.get("confidence_score", row.get("confidence", 0.0)))
        username = str(row.get("username", "anonim")).replace("'", "").strip() or "anonim"
        content = str(row.get("content", "")).replace("'", "").strip()
        if len(content) > 650:
            content = content[:650].rstrip() + "…"

        st.markdown(
            f"""
            <article class="sent-v7-comment-card">
                <div class="sent-v7-comment-meta">
                    {_sentiment_badge_html(sentiment)}
                    {_platform_badge_html(platform)}
                    <span class="sent-v7-badge sent-v7-badge-confidence">
                        Confidence {confidence:.1%}
                    </span>
                    <span class="sent-v7-badge sent-v7-badge-confidence">
                        @{escape(username)}
                    </span>
                </div>
                <p class="sent-v7-comment-content">{escape(content)}</p>
            </article>
            """,
            unsafe_allow_html=True,
        )
    except Exception as exc:
        st.error(f"Satu contoh komentar gagal ditampilkan: {exc}")


def _render_comment_examples(df: pd.DataFrame) -> None:
    """Render lima contoh komentar untuk setiap kelas sentimen."""
    try:
        sorted_df = df.sort_values(
            ["confidence_score", "date_created"],
            ascending=[False, False],
            na_position="last",
        )
        expander_titles = {
            "positive": "🟢 Positif — 5 contoh dengan confidence tertinggi",
            "neutral": "🟠 Netral — 5 contoh dengan confidence tertinggi",
            "negative": "🔴 Negatif — 5 contoh dengan confidence tertinggi",
        }
        for index, sentiment in enumerate(_SENTIMENT_ORDER):
            subset = sorted_df[
                sorted_df["predicted_sentiment"] == sentiment
            ].head(5)
            with st.expander(expander_titles[sentiment], expanded=index == 0):
                if subset.empty:
                    st.info("Belum ada contoh komentar pada kelas sentimen ini.")
                    continue
                for _, row in subset.iterrows():
                    _render_comment_card(row)
    except Exception as exc:
        st.error(f"Contoh komentar gagal ditampilkan: {exc}")


def _render_telkomsel_top_comments_table(df: pd.DataFrame) -> None:
    """Render maksimal lima komentar per sentimen pada setiap platform Telkomsel."""
    try:
        if df.empty:
            st.info("Belum ada komentar Telkomsel yang dapat ditampilkan.")
            return

        work = df.copy()
        if "confidence_score" not in work.columns:
            work["confidence_score"] = 0.0
        work["confidence_score"] = pd.to_numeric(
            work["confidence_score"], errors="coerce"
        ).fillna(0.0).clip(0.0, 1.0)
        work["predicted_sentiment"] = work["predicted_sentiment"].apply(
            _normalize_sentiment
        )
        work["platform"] = work["platform"].apply(_normalize_platform)

        platform_counts = {
            platform: int((work["platform"] == platform).sum())
            for platform in ["twitter", "instagram", "tiktok"]
        }
        st.markdown(
            f"""
            <section class="sent-v7-comments-hero">
                <div class="sent-v7-comments-kicker">
                    <span class="sent-v7-comments-kicker-dot"></span>
                    Komentar representatif
                </div>
                <h3>Jelajahi percakapan penting dari tiap platform</h3>
                <p>
                    Buka panel Twitter/X, Instagram, atau TikTok untuk melihat komentar dengan confidence tertinggi
                    pada setiap sentimen. Setiap panel menampilkan ringkasan singkat sebelum tabel komentar.
                </p>
                <div class="sent-v7-comments-chip-row">
                    <span class="sent-v7-comments-chip sent-v7-comments-chip--twitter">𝕏 Twitter/X <strong>{_format_number(platform_counts.get('twitter', 0))}</strong></span>
                    <span class="sent-v7-comments-chip sent-v7-comments-chip--instagram">◎ Instagram <strong>{_format_number(platform_counts.get('instagram', 0))}</strong></span>
                    <span class="sent-v7-comments-chip sent-v7-comments-chip--tiktok">♪ TikTok <strong>{_format_number(platform_counts.get('tiktok', 0))}</strong></span>
                </div>
            </section>
            """,
            unsafe_allow_html=True,
        )

        for platform_index, platform in enumerate(["twitter", "instagram", "tiktok"]):
            platform_label = _PLATFORM_LABELS.get(platform, platform.title())
            platform_rows = work[work["platform"] == platform].copy()
            selected_parts: list[pd.DataFrame] = []
            for sentiment in _SENTIMENT_ORDER:
                subset = (
                    platform_rows[
                        platform_rows["predicted_sentiment"] == sentiment
                    ]
                    .sort_values(
                        ["confidence_score", "date_created"],
                        ascending=[False, False],
                        na_position="last",
                    )
                    .head(5)
                )
                if not subset.empty:
                    selected_parts.append(subset)

            selected = (
                pd.concat(selected_parts, ignore_index=True)
                if selected_parts
                else pd.DataFrame()
            )
            with st.expander(
                f"{_PLATFORM_ICONS.get(platform, '◉')} {platform_label} • "
                f"{len(selected)} komentar representatif",
                expanded=platform_index == 0,
            ):
                if selected.empty:
                    st.info(f"Belum ada komentar {platform_label} pada data aktif.")
                    continue

                dominant_counts = (
                    selected["predicted_sentiment"]
                    .value_counts()
                    .reindex(_SENTIMENT_ORDER, fill_value=0)
                )
                dominant_sentiment = str(dominant_counts.idxmax()) if int(dominant_counts.sum()) > 0 else "neutral"
                dominant_label = SENTIMENT_LABELS.get(dominant_sentiment, dominant_sentiment.title())
                avg_confidence = pd.to_numeric(selected["confidence_score"], errors="coerce").fillna(0.0).mean()
                summary_html = (
                    '<div class="sent-v7-comments-panel">'
                    '<div class="sent-v7-comments-panel-head">'
                    '<div>'
                    f'<div class="sent-v7-comments-panel-title">Ringkasan {escape(platform_label)}</div>'
                    f'<div class="sent-v7-comments-panel-sub">Komentar ditampilkan dari confidence tertinggi per sentimen.</div>'
                    '</div>'
                    f'{_platform_badge_html(platform)}'
                    '</div>'
                    '<div class="sent-v7-comments-stat-row">'
                    '<div class="sent-v7-comments-stat">'
                    '<div class="sent-v7-comments-stat-label">Komentar tampil</div>'
                    f'<div class="sent-v7-comments-stat-value">{_format_number(len(selected))}</div>'
                    '<div class="sent-v7-comments-stat-note">Maksimal 5 per sentimen</div>'
                    '</div>'
                    '<div class="sent-v7-comments-stat">'
                    '<div class="sent-v7-comments-stat-label">Sentimen dominan</div>'
                    f'<div class="sent-v7-comments-stat-value">{escape(dominant_label)}</div>'
                    f'<div class="sent-v7-comments-stat-note">{int(dominant_counts.get(dominant_sentiment, 0))} komentar dominan</div>'
                    '</div>'
                    '<div class="sent-v7-comments-stat">'
                    '<div class="sent-v7-comments-stat-label">Rata-rata confidence</div>'
                    f'<div class="sent-v7-comments-stat-value">{avg_confidence:.1%}</div>'
                    '<div class="sent-v7-comments-stat-note">Dihitung dari komentar terpilih</div>'
                    '</div>'
                    '</div>'
                )
                st.markdown(summary_html, unsafe_allow_html=True)

                rows_html: list[str] = []
                for _, row in selected.iterrows():
                    username = str(row.get("username", "anonim")).replace("'", "").strip() or "anonim"
                    content = " ".join(str(row.get("content", "")).split())
                    confidence = _safe_float(row.get("confidence_score"), 0.0)
                    platform_value = _normalize_platform(row.get("platform"))
                    sentiment_value = _normalize_sentiment(row.get("predicted_sentiment"))
                    rows_html.append(
                        "<tr>"
                        f"<td>{_platform_badge_html(platform_value)}</td>"
                        f"<td>@{escape(username)}</td>"
                        f"<td>{_sentiment_badge_html(sentiment_value)}</td>"
                        f"<td>{confidence:.1%}</td>"
                        f'<td class="sent-v7-telkomsel-comment">{escape(content)}</td>'
                        "</tr>"
                    )

                st.markdown(
                    '<div class="sent-v7-telkomsel-table-wrap">'
                    '<table class="sent-v7-telkomsel-table">'
                    "<thead><tr>"
                    "<th>Platform</th><th>Username</th><th>Sentimen</th>"
                    "<th>Confidence</th><th>Isi Komentar</th>"
                    "</tr></thead><tbody>"
                    + "".join(rows_html)
                    + "</tbody></table></div></div>",
                    unsafe_allow_html=True,
                )
    except Exception as exc:
        st.error(f"Tabel komentar Telkomsel gagal ditampilkan: {exc}")


@st.cache_data(show_spinner=False, max_entries=18)
def _prepare_wordcloud_corpus(raw_text: str) -> str:
    """Bersihkan seluruh teks aktual dan buang stopword non-domain."""
    try:
        if not str(raw_text or "").strip():
            return ""

        cleaned_text = clean_text(str(raw_text))
        tokens = [
            token
            for token in cleaned_text.split()
            if len(token) > 2 and token not in _WORDCLOUD_STOPWORDS
        ]
        return " ".join(tokens).strip()
    except Exception:
        return ""


def _wordcloud_text(df: pd.DataFrame, sentiment: str) -> str:
    """Gabungkan seluruh komentar aktual untuk satu kelas sentimen."""
    try:
        if not isinstance(df, pd.DataFrame) or df.empty:
            return ""
        if sentiment not in _SENTIMENT_ORDER:
            return ""
        if "predicted_sentiment" not in df.columns:
            return ""

        sentiment_values = (
            df["predicted_sentiment"]
            .astype("string")
            .fillna("")
            .str.lower()
            .str.strip()
        )
        subset = df.loc[sentiment_values.eq(sentiment)].copy()
        if subset.empty:
            return ""

        # Gunakan komentar asli sebagai sumber utama. content_clean hanya
        # menjadi fallback apabila kolom content tidak tersedia.
        text_column = "content" if "content" in subset.columns else "content_clean"
        if text_column not in subset.columns:
            return ""

        values = (
            subset[text_column]
            .astype("string")
            .fillna("")
            .str.strip()
        )
        values = values[values.ne("")]
        if values.empty:
            return ""

        # Tidak ada sampling/head(). Seluruh komentar pada filter aktif
        # diproses sehingga WordCloud mewakili data aktual yang sedang tampil.
        return _prepare_wordcloud_corpus("\n".join(values.tolist()))
    except Exception:
        return ""


def _create_wordcloud_figure(text: str, sentiment: str) -> plt.Figure:
    """Buat satu figure WordCloud HD untuk preview, fullscreen, dan download."""
    try:
        figure, axis = plt.subplots(figsize=(10, 5), dpi=200)  # FIX: rasio WordCloud 2:1
        figure.patch.set_alpha(0.0)
        figure.subplots_adjust(left=0, right=1, top=1, bottom=0)
        axis.set_facecolor("none")
        axis.axis("off")

        if not text.strip():
            axis.text(
                0.5,
                0.5,
                "Belum ada kata untuk sentimen ini",
                ha="center",
                va="center",
                color="#AAAAAA",
                fontsize=16,
                transform=axis.transAxes,
            )
            return figure

        colormap = {
            "positive": "Greens",
            "neutral": "Blues",
            "negative": "Reds",
        }.get(sentiment, "viridis")
        cloud = WordCloud(
            width=2200,
            height=1280,
            background_color=None,
            mode="RGBA",
            colormap=colormap,
            max_words=150,
            prefer_horizontal=0.88,
            collocations=False,
            random_state=42,
            margin=4,
            min_font_size=12,  # FIX: ukuran kata minimum tetap terbaca di tablet
        ).generate(text)
        axis.imshow(cloud, interpolation="lanczos")
        figure.tight_layout(pad=0)  # FIX: cegah ruang kosong dan potongan pada viewport kecil.
        return figure
    except Exception as exc:
        figure, axis = plt.subplots(figsize=(10, 5), dpi=200)  # FIX: rasio WordCloud 2:1
        figure.patch.set_alpha(0.0)
        figure.subplots_adjust(left=0, right=1, top=1, bottom=0)
        axis.set_facecolor("none")
        axis.axis("off")
        axis.text(
            0.5,
            0.5,
            f"WordCloud belum dapat dibuat\n{exc}",
            ha="center",
            va="center",
            color="#F44336",
            fontsize=14,
            transform=axis.transAxes,
        )
        return figure


def _figure_to_png_bytes(figure: plt.Figure) -> bytes:
    """Ubah figure WordCloud HD menjadi bytes PNG transparan."""
    buffer = io.BytesIO()
    figure.savefig(
        buffer,
        format="png",
        dpi=240,
        bbox_inches="tight",
        pad_inches=0.02,
        transparent=True,
        facecolor=(0, 0, 0, 0),
    )
    buffer.seek(0)
    return buffer.getvalue()



@st.cache_data(show_spinner=False, max_entries=12)
def _wordcloud_png_bytes_cached(text: str, sentiment: str) -> bytes:
    """Buat PNG WordCloud satu kali per kombinasi teks dan sentimen."""
    figure = _create_wordcloud_figure(text, sentiment)
    try:
        return _figure_to_png_bytes(figure)
    finally:
        plt.close(figure)

def _wordcloud_viewer_html(png_bytes: bytes, title: str, unique_id: str) -> str:
    """Buat viewer WordCloud custom dengan fullscreen yang selalu tepat di tengah."""
    image_base64 = base64.b64encode(png_bytes).decode("ascii")
    safe_id = "".join(character for character in unique_id if character.isalnum() or character in {"-", "_"})
    safe_title = escape(title)
    return f"""
    <div class="sent-v7-wc-viewer">
        <input class="sent-v7-wc-viewer-toggle" type="checkbox" id="{safe_id}">
        <label class="sent-v7-wc-fullscreen-trigger" for="{safe_id}" title="View fullscreen" aria-label="View fullscreen">⛶</label>
        <img class="sent-v7-wc-inline-image" src="data:image/png;base64,{image_base64}" alt="WordCloud {safe_title}">
        <div class="sent-v7-wc-overlay" role="dialog" aria-modal="true" aria-label="Fullscreen WordCloud {safe_title}">
            <label class="sent-v7-wc-overlay-close" for="{safe_id}" title="Tutup fullscreen" aria-label="Tutup fullscreen">×</label>
            <img class="sent-v7-wc-overlay-image" src="data:image/png;base64,{image_base64}" alt="WordCloud {safe_title} fullscreen">
        </div>
    </div>
    """


def _render_service_wordclouds(df: pd.DataFrame, layanan: str) -> None:
    """Render WordCloud per sentimen secara konsisten untuk seluruh layanan."""
    try:
        layanan_label = str(layanan or "Layanan").strip() or "Layanan"

        # Jangan menyajikan WordCloud dummy sebagai hasil penelitian aktual.
        # Mode demo tetap diperbolehkan karena memang dipilih secara eksplisit.
        if not bool(st.session_state.get("demo_mode", False)):
            source_label = get_data_source_label(layanan_label)
            if "Real" not in str(source_label):
                st.warning(
                    f"WordCloud {layanan_label} belum dibuat karena sumber data "
                    "aktual belum tersedia atau belum tervalidasi."
                )
                return

        layanan_slug = "".join(
            character.lower() if character.isalnum() else "_"
            for character in layanan_label
        ).strip("_") or "layanan"
        label_map = {
            "positive": ("Positif", "Nuansa hijau", "sent-v7-wordcloud-card--positive", "sent-v7-wordcloud-badge--positive", "sent-v7-wordcloud-chip--positive"),
            "neutral": ("Netral", "Nuansa biru", "sent-v7-wordcloud-card--neutral", "sent-v7-wordcloud-badge--neutral", "sent-v7-wordcloud-chip--neutral"),
            "negative": ("Negatif", "Nuansa merah", "sent-v7-wordcloud-card--negative", "sent-v7-wordcloud-badge--negative", "sent-v7-wordcloud-chip--negative"),
        }
        counts = (
            df["predicted_sentiment"].astype("string").fillna("").value_counts().to_dict()
            if "predicted_sentiment" in df.columns
            else {}
        )

        st.markdown(
            f"""
            <section class="sent-v7-wordcloud-hero">
                <div class="sent-v7-wordcloud-kicker">
                    <span class="sent-v7-wordcloud-kicker-dot"></span>
                    Word insight
                </div>
                <h3 class="sent-v7-wordcloud-hero-title">Jelajahi kata yang paling sering muncul pada tiap sentimen</h3>
                <p class="sent-v7-wordcloud-hero-copy">
                    WordCloud membantu membaca pola kata yang dominan dari komentar {escape(layanan_label)}. Gunakan mode fokus
                    untuk menyorot satu sentimen secara lebih jelas, atau biarkan tampilan semua kartu untuk membandingkan ketiganya sekaligus.
                </p>
                <div class="sent-v7-wordcloud-chip-row">
                    <span class="sent-v7-wordcloud-chip sent-v7-wordcloud-chip--positive">Positif <strong>{_format_number(int(counts.get('positive', 0)))}</strong></span>
                    <span class="sent-v7-wordcloud-chip sent-v7-wordcloud-chip--neutral">Netral <strong>{_format_number(int(counts.get('neutral', 0)))}</strong></span>
                    <span class="sent-v7-wordcloud-chip sent-v7-wordcloud-chip--negative">Negatif <strong>{_format_number(int(counts.get('negative', 0)))}</strong></span>
                </div>
            </section>
            """,
            unsafe_allow_html=True,
        )

        st.markdown(
            f"""
            <div class="sent-v7-wordcloud-intro">
                Ukuran kata menunjukkan frekuensi kemunculan pada komentar {escape(layanan_label)}.
                WordCloud bersifat eksploratif dan tetap perlu dibaca bersama contoh
                komentar serta konteks penelitian.
            </div>
            """,
            unsafe_allow_html=True,
        )

        st.markdown(
            """
            <div class="sent-v7-wordcloud-control-head">
                <div>
                    <p class="sent-v7-wordcloud-control-title">Mode tampilan WordCloud</p>
                    <p class="sent-v7-wordcloud-control-copy">Pilih tampilan perbandingan semua sentimen atau fokus pada satu kelas.</p>
                </div>
                <span class="sent-v7-wordcloud-control-icon">⌄</span>
            </div>
            """,
            unsafe_allow_html=True,
        )
        view_mode = st.selectbox(
            "Mode tampilan WordCloud",
            ["Semua", "Fokus Positif", "Fokus Netral", "Fokus Negatif"],
            key="sent_v7_wordcloud_view_mode",
            label_visibility="collapsed",
            on_change=_queue_wordcloud_view_loading,
        )
        st.markdown(
            f"""
            <div class="sent-v7-wordcloud-mode-summary">
                <span>Tampilan aktif</span>
                <strong>{escape(view_mode)}</strong>
            </div>
            """,
            unsafe_allow_html=True,
        )

        def _render_single_wordcloud(column: Any, sentiment: str) -> None:
            title, subtitle, card_class, badge_class, _ = label_map[sentiment]
            sample_count = int(counts.get(sentiment, 0))
            text_content = _wordcloud_text(df, sentiment)
            total_words = len([item for item in text_content.split() if item.strip()])
            with column:
                st.markdown(
                    f"""
                    <div class="sent-v7-wordcloud-card {card_class}">
                        <div class="sent-v7-wordcloud-title-row">
                            <p class="sent-v7-wordcloud-title">{escape(title)}</p>
                            <span class="sent-v7-wordcloud-badge {badge_class}">{escape(title)}</span>
                        </div>
                        <p class="sent-v7-wordcloud-subtitle">{escape(subtitle)} • Matplotlib WordCloud</p>
                        <p class="sent-v7-wordcloud-note">{_format_number(sample_count)} komentar • { _format_number(total_words) } token terhimpun</p>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )
                png_bytes = _wordcloud_png_bytes_cached(text_content, sentiment)
                st.markdown(
                    _wordcloud_viewer_html(
                        png_bytes,
                        title,
                        f"sent-v7-wc-{layanan_slug}-{sentiment}",
                    ),
                    unsafe_allow_html=True,
                )
                st.markdown('<div class="sent-v7-wordcloud-grid-download-gap"></div>', unsafe_allow_html=True)
                st.download_button(
                    label=f"⬇ Download PNG {title}",
                    data=png_bytes,
                    file_name=f"{layanan_slug}_wordcloud_{title.lower()}.png",
                    mime="image/png",
                    key=f"sent_v7_wordcloud_download_{layanan_slug}_{sentiment}",
                    on_click=_queue_wordcloud_download_loading,
                    args=(title,),
                    use_container_width=True,
                )
                st.markdown('<div class="sent-v7-wordcloud-grid-download-bottom-gap"></div>', unsafe_allow_html=True)

        if view_mode == "Semua":
            columns = st.columns(3, gap="medium")
            for column, sentiment in zip(columns, _SENTIMENT_ORDER):
                _render_single_wordcloud(column, sentiment)
        else:
            selected_sentiment = {
                "Fokus Positif": "positive",
                "Fokus Netral": "neutral",
                "Fokus Negatif": "negative",
            }.get(view_mode, "positive")
            title, subtitle, card_class, badge_class, chip_class = label_map[selected_sentiment]
            sample_count = int(counts.get(selected_sentiment, 0))
            text_content = _wordcloud_text(df, selected_sentiment)
            total_words = len([item for item in text_content.split() if item.strip()])
            st.markdown(
                f"""
                <section class="sent-v7-wordcloud-focus-wrap {card_class}">
                    <div class="sent-v7-wordcloud-focus-head">
                        <div>
                            <h4 class="sent-v7-wordcloud-focus-title">Sorotan {escape(title)}</h4>
                            <p class="sent-v7-wordcloud-focus-copy">Tampilan fokus membantu Anda membaca kata dominan pada sentimen {escape(title.lower())} dengan area visual yang lebih lega.</p>
                        </div>
                        <span class="sent-v7-wordcloud-badge {badge_class}">{escape(subtitle)}</span>
                    </div>
                    <div class="sent-v7-wordcloud-focus-stat-row">
                        <div class="sent-v7-wordcloud-focus-stat">
                            <div class="sent-v7-wordcloud-focus-stat-label">Komentar</div>
                            <div class="sent-v7-wordcloud-focus-stat-value">{_format_number(sample_count)}</div>
                            <div class="sent-v7-wordcloud-focus-stat-note">Jumlah komentar pada kelas ini</div>
                        </div>
                        <div class="sent-v7-wordcloud-focus-stat">
                            <div class="sent-v7-wordcloud-focus-stat-label">Token terhimpun</div>
                            <div class="sent-v7-wordcloud-focus-stat-value">{_format_number(total_words)}</div>
                            <div class="sent-v7-wordcloud-focus-stat-note">Gabungan kata dari komentar bersih</div>
                        </div>
                        <div class="sent-v7-wordcloud-focus-stat">
                            <div class="sent-v7-wordcloud-focus-stat-label">Mode tampil</div>
                            <div class="sent-v7-wordcloud-focus-stat-value">Fokus</div>
                            <div class="sent-v7-wordcloud-focus-stat-note">Klik pilihan lain untuk mengganti sorotan</div>
                        </div>
                    </div>
                </section>
                """,
                unsafe_allow_html=True,
            )
            st.markdown('<div class="sent-v7-wordcloud-focus-panel-gap"></div>', unsafe_allow_html=True)
            png_bytes = _wordcloud_png_bytes_cached(text_content, selected_sentiment)
            st.markdown(
                _wordcloud_viewer_html(
                    png_bytes,
                    f"Fokus {title}",
                    f"sent-v7-wc-focus-{layanan_slug}-{selected_sentiment}",
                ),
                unsafe_allow_html=True,
            )
            st.markdown('<div class="sent-v7-wordcloud-focus-download-gap"></div>', unsafe_allow_html=True)
            st.download_button(
                label=f"⬇ Download PNG {title}",
                data=png_bytes,
                file_name=f"{layanan_slug}_wordcloud_fokus_{title.lower()}.png",
                mime="image/png",
                key=f"sent_v7_wordcloud_download_focus_{layanan_slug}_{selected_sentiment}",
                on_click=_queue_wordcloud_download_loading,
                args=(title,),
                use_container_width=True,
            )
            st.markdown('<div class="sent-v7-wordcloud-focus-download-bottom-gap"></div>', unsafe_allow_html=True)
    except Exception as exc:
        st.error(f"WordCloud {layanan_label} gagal ditampilkan: {exc}")


# -----------------------------------------------------------------------------
# Model IndoBERT dan prediksi manual
# -----------------------------------------------------------------------------
@st.cache_resource(show_spinner=False)
def load_service_model(layanan: str) -> tuple[Any | None, str]:
    """Muat runtime IndoBERT terpusat dari HuggingFace Hub."""
    try:
        layanan_label = str(layanan or "IndiHome").strip() or "IndiHome"
        if layanan_label not in _READY_SERVICES:
            return None, f"Model {layanan_label} segera hadir"

        tokenizer, model, device = load_indobert()
        if tokenizer is None or model is None or device is None:
            return None, "Model gagal dimuat dari HuggingFace Hub"

        import torch

        runtime = {
            "tokenizer": tokenizer,
            "model": model,
            "torch": torch,
            "device": device,
            "layanan": layanan_label,
        }
        source_label = (
            f"Model IndoBERT HuggingFace Hub — {layanan_label} · cache runtime"
        )
        return runtime, source_label
    except Exception as exc:
        st.error(
            "Model IndoBERT belum dapat dimuat dari HuggingFace Hub. "
            "Pastikan internet aktif saat pemuatan pertama. "
            f"Detail: {exc}"
        )
        return None, "Model gagal dimuat"

def load_indihome_model() -> tuple[Any | None, str]:
    """Kompatibilitas lama: muat model untuk IndiHome."""
    return load_service_model("IndiHome")


def predict_sentiment(text: str, runtime: Any) -> dict[str, Any] | None:
    """Jalankan inferensi langsung tanpa overhead pipeline Transformers."""
    try:
        raw_text = str(text or "").strip()
        if not raw_text:
            raise ValueError("Teks komentar masih kosong.")
        if not runtime:
            raise RuntimeError("Model IndoBERT belum tersedia.")

        cleaned_text = clean_text(raw_text)
        if not cleaned_text:
            raise ValueError("Teks tidak memiliki kata yang dapat dianalisis setelah dibersihkan.")

        tokenizer = runtime["tokenizer"]
        model = runtime["model"]
        torch = runtime["torch"]
        device = runtime["device"]

        encoded = tokenizer(
            cleaned_text,
            return_tensors="pt",
            truncation=True,
            max_length=_MODEL_MAX_LENGTH,
            padding=False,
        )
        encoded = {
            key: value.to(device)
            for key, value in encoded.items()
        }

        # inference_mode lebih ringan dibanding pipeline karena autograd dimatikan.
        with torch.inference_mode():
            output = model(**encoded)
            scores = torch.softmax(output.logits, dim=-1)[0].detach().cpu().tolist()

        id2label = getattr(model.config, "id2label", {}) or {}
        probabilities = {item: 0.0 for item in _SENTIMENT_ORDER}

        for index, score in enumerate(scores):
            raw_label = id2label.get(index, id2label.get(str(index), f"LABEL_{index}"))
            label = _normalize_sentiment(raw_label)
            probabilities[label] = _safe_float(score)

        total_probability = sum(probabilities.values())
        if total_probability <= 0:
            raise RuntimeError("Model tidak mengembalikan probabilitas yang valid.")

        probabilities = {
            key: value / total_probability
            for key, value in probabilities.items()
        }
        winner = max(probabilities, key=probabilities.get)

        return {
            "label": winner,
            "label_id": SENTIMENT_LABELS[winner],
            "confidence": float(probabilities[winner]),
            "probabilities": probabilities,
            "cleaned_text": cleaned_text,
        }
    except Exception as exc:
        st.error(f"Prediksi sentimen gagal: {exc}")
        return None


def _prediction_history_path() -> Path:
    """Kembalikan lokasi file riwayat prediksi manual."""
    return _project_root() / "data" / _HISTORY_FILE_NAME


def _history_owner_key() -> str:
    """Buat identitas pemilik riwayat berdasarkan akun yang sedang login."""
    try:
        user_id = st.session_state.get("user_id")
        username = str(st.session_state.get("username") or "").strip()

        if user_id not in (None, ""):
            return f"user_id:{user_id}"
        if username:
            return f"username:{username.lower()}"
        return "session:anonymous"
    except Exception:
        return "session:anonymous"


def _read_history_store() -> dict[str, list[dict[str, Any]]]:
    """Baca seluruh riwayat prediksi dari file JSON secara aman."""
    try:
        history_path = _prediction_history_path()
        if not history_path.exists():
            return {}

        raw_data = json.loads(history_path.read_text(encoding="utf-8"))
        if not isinstance(raw_data, dict):
            return {}

        clean_data: dict[str, list[dict[str, Any]]] = {}
        for owner, items in raw_data.items():
            if isinstance(owner, str) and isinstance(items, list):
                clean_data[owner] = [
                    item for item in items
                    if isinstance(item, dict)
                ][:_MAX_HISTORY]

        return clean_data
    except Exception:
        # File rusak tidak boleh membuat halaman prediksi gagal.
        return {}


def _write_history_store(
    history_store: dict[str, list[dict[str, Any]]],
) -> None:
    """Simpan riwayat ke JSON menggunakan penulisan atomik."""
    history_path = _prediction_history_path()
    history_path.parent.mkdir(parents=True, exist_ok=True)

    temp_path = history_path.with_suffix(".tmp")
    payload = json.dumps(
        history_store,
        ensure_ascii=False,
        indent=2,
    )

    temp_path.write_text(payload, encoding="utf-8")
    temp_path.replace(history_path)


def _get_prediction_history() -> list[dict[str, Any]]:
    """Ambil maksimal sepuluh riwayat milik pengguna aktif."""
    try:
        owner_key = _history_owner_key()
        history_store = _read_history_store()
        persisted_history = history_store.get(owner_key, [])

        # Sinkronkan file lokal ke session state agar interaksi halaman tetap cepat.
        session_history = st.session_state.get(_HISTORY_KEY, [])
        if not isinstance(session_history, list):
            session_history = []

        history = persisted_history or session_history
        history = [
            item for item in history
            if isinstance(item, dict)
        ][:_MAX_HISTORY]

        st.session_state[_HISTORY_KEY] = history
        return history
    except Exception as exc:
        st.warning(f"Riwayat prediksi belum dapat dimuat: {exc}")
        return []


def _save_prediction_history(text: str, result: dict[str, Any]) -> None:
    """Simpan maksimal sepuluh hasil prediksi secara persisten per pengguna."""
    try:
        owner_key = _history_owner_key()
        history_store = _read_history_store()

        existing_history = history_store.get(owner_key, [])
        if not isinstance(existing_history, list):
            existing_history = []

        confidence_value = float(result.get("confidence", 0.0))
        item = {
            "id": datetime.now().strftime("%Y%m%d%H%M%S%f"),
            "Waktu": datetime.now().strftime("%d-%m-%Y %H:%M:%S"),
            "Teks": str(text).strip(),
            "Sentimen": str(result.get("label_id", "-")),
            "SentimentKey": str(result.get("label", "neutral")),
            "ConfidenceValue": confidence_value,
            "Confidence": f"{confidence_value:.1%}",
        }

        # Gunakan list baru, bukan mutasi insert pada objek session_state lama.
        # Setiap klik yang selesai diproses selalu menjadi satu baris riwayat.
        updated_history = [item, *existing_history][:_MAX_HISTORY]
        history_store[owner_key] = updated_history

        _write_history_store(history_store)
        st.session_state[_HISTORY_KEY] = updated_history
    except Exception as exc:
        # Fallback session memastikan riwayat tetap bertambah walaupun file
        # tidak dapat ditulis karena izin folder atau antivirus.
        try:
            existing_session = st.session_state.get(_HISTORY_KEY, [])
            if not isinstance(existing_session, list):
                existing_session = []

            confidence_value = float(result.get("confidence", 0.0))
            fallback_item = {
                "id": datetime.now().strftime("%Y%m%d%H%M%S%f"),
                "Waktu": datetime.now().strftime("%d-%m-%Y %H:%M:%S"),
                "Teks": str(text).strip(),
                "Sentimen": str(result.get("label_id", "-")),
                "SentimentKey": str(result.get("label", "neutral")),
                "ConfidenceValue": confidence_value,
                "Confidence": f"{confidence_value:.1%}",
            }
            st.session_state[_HISTORY_KEY] = [
                fallback_item,
                *existing_session,
            ][:_MAX_HISTORY]
        except Exception:
            pass

        st.warning(
            "Riwayat tersimpan sementara pada sesi ini, tetapi belum dapat "
            f"ditulis ke file lokal. Detail: {exc}"
        )


def _history_sentiment_key(item: dict[str, Any]) -> str:
    """Normalisasi sentimen riwayat untuk kebutuhan warna badge."""
    raw_key = str(item.get("SentimentKey") or "").strip().lower()
    if raw_key in _SENTIMENT_ORDER:
        return raw_key

    raw_label = str(item.get("Sentimen") or "").strip()
    return _normalize_sentiment(raw_label)


def _history_confidence_value(item: dict[str, Any]) -> float:
    """Ambil confidence numerik dari format lama maupun format terbaru."""
    try:
        raw_value = item.get("ConfidenceValue")
        if raw_value is not None:
            value = float(raw_value)
            return min(max(value, 0.0), 1.0)

        raw_text = str(item.get("Confidence") or "0").replace("%", "").strip()
        value = float(raw_text) / 100
        return min(max(value, 0.0), 1.0)
    except Exception:
        return 0.0


def _render_prediction_history(history: list[dict[str, Any]]) -> None:
    """Render tabel riwayat prediksi manual dengan HTML yang aman untuk Streamlit."""
    try:
        safe_history = [
            item for item in history
            if isinstance(item, dict)
        ][:_MAX_HISTORY]

        rows_html: list[str] = []

        for index, item in enumerate(safe_history, start=1):
            sentiment_key = _history_sentiment_key(item)
            sentiment_label = escape(str(item.get("Sentimen") or "-"))
            time_label = escape(str(item.get("Waktu") or "-"))

            full_text = str(item.get("Teks") or "-").strip()
            displayed_text = (
                full_text[:150] + "…"
                if len(full_text) > 150
                else full_text
            )

            confidence_value = _history_confidence_value(item)
            confidence_label = f"{confidence_value:.1%}"
            confidence_width = confidence_value * 100

            # HTML sengaja dibuat tanpa indentasi awal. Markdown menganggap
            # baris dengan empat spasi sebagai blok kode, meskipun
            # unsafe_allow_html=True.
            row_html = (
                "<tr>"
                f'<td class="sent-v7-history-number">{index}</td>'
                f'<td class="sent-v7-history-time">{time_label}</td>'
                f'<td class="sent-v7-history-text" '
                f'title="{escape(full_text, quote=True)}">'
                f"{escape(displayed_text)}"
                "</td>"
                "<td>"
                f'<span class="sent-v7-history-sentiment '
                f'{escape(sentiment_key)}">'
                f"{sentiment_label}"
                "</span>"
                "</td>"
                "<td>"
                '<div class="sent-v7-history-confidence">'
                '<span class="sent-v7-history-confidence-track">'
                f'<span class="sent-v7-history-confidence-fill" '
                f'style="width:{confidence_width:.1f}%;"></span>'
                "</span>"
                '<span class="sent-v7-history-confidence-value">'
                f"{confidence_label}"
                "</span>"
                "</div>"
                "</td>"
                "</tr>"
            )
            rows_html.append(row_html)

        table_html = (
            '<div class="sent-v7-history-summary">'
            '<p class="sent-v7-history-summary-text">'
            "Riwayat disimpan per akun dan tetap tersedia setelah "
            "halaman dimuat ulang atau aplikasi dijalankan kembali."
            "</p>"
            '<span class="sent-v7-history-counter">'
            f"{len(safe_history)} dari {_MAX_HISTORY}"
            "</span>"
            "</div>"
            '<div class="sent-v7-history-table-wrap">'
            '<table class="sent-v7-history-table">'
            "<thead>"
            "<tr>"
            "<th>No.</th>"
            "<th>Waktu</th>"
            "<th>Komentar</th>"
            "<th>Sentimen</th>"
            "<th>Confidence</th>"
            "</tr>"
            "</thead>"
            "<tbody>"
            f"{''.join(rows_html)}"
            "</tbody>"
            "</table>"
            "</div>"
            '<div class="sent-v7-history-bottom-gap" aria-hidden="true"></div>'
        )

        st.markdown(
            table_html,
            unsafe_allow_html=True,
        )
    except Exception as exc:
        st.error(f"Tabel riwayat prediksi gagal ditampilkan: {exc}")


def _render_prediction_result(result: dict[str, Any], model_source: str) -> None:
    """Render badge hasil, confidence, dan bar probabilitas."""
    try:
        sentiment = str(result["label"])
        color = SENTIMENT_COLORS[sentiment]
        st.markdown(
            f"""
            <div class="sent-v7-result-box">
                <span class="sent-v7-badge sent-v7-badge-{escape(sentiment)}">
                    Hasil Analisis
                </span>
                <div class="sent-v7-result-label" style="color:{escape(color)};">
                    {escape(str(result['label_id']))}
                </div>
                <div class="sent-v7-result-confidence">
                    Confidence <strong>{float(result['confidence']):.1%}</strong>
                    • {escape(model_source)}
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )
        # Beri jarak yang jelas antara kartu hasil dan grafik probabilitas.
        st.markdown(
            '<div style="display:block;height:28px;min-height:28px;width:100%;"></div>',
            unsafe_allow_html=True,
        )

        _plotly_chart(
            _probability_bar(result["probabilities"]),
            "sent_v7_manual_probability",
        )
    except Exception as exc:
        st.error(f"Hasil prediksi gagal ditampilkan: {exc}")



def _queue_manual_prediction() -> None:
    """Masukkan teks manual ke antrean prediksi sebelum halaman dirender ulang."""
    try:
        user_text = str(
            st.session_state.get("sent_v7_manual_text", "")
        ).strip()

        if not user_text:
            st.session_state[_PREDICTION_PENDING_KEY] = False
            st.session_state[_PREDICTION_TEXT_KEY] = ""
            st.session_state[_PREDICTION_ERROR_KEY] = (
                "Silakan isi komentar terlebih dahulu sebelum "
                "menekan Analisis Sentimen."
            )
            return

        st.session_state[_PREDICTION_TEXT_KEY] = user_text
        st.session_state[_PREDICTION_SERVICE_KEY] = str(
            st.session_state.get("sent_v7_service_selector", "IndiHome")
        )
        st.session_state[_PREDICTION_PENDING_KEY] = True
        st.session_state[_PREDICTION_ERROR_KEY] = ""
    except Exception as exc:
        st.session_state[_PREDICTION_PENDING_KEY] = False
        st.session_state[_PREDICTION_ERROR_KEY] = (
            f"Komentar belum dapat dimasukkan ke antrean analisis: {exc}"
        )


def _render_manual_prediction(layanan: str) -> None:
    """Render kartu prediksi manual untuk layanan terpilih."""
    try:
        st.markdown(
            f"""
            <section class="sent-v7-prediction-card">
                <div class="sent-v7-manual-kicker">
                    <span class="sent-v7-manual-kicker-dot"></span>
                    IndoBERT live inference
                </div>
                <h3 class="sent-v7-manual-title">Uji komentar baru untuk {escape(layanan)}</h3>
                <p class="sent-v7-manual-copy">
                    Masukkan satu komentar berbahasa Indonesia. Sistem akan memuat model dari cache,
                    menjalankan inferensi tiga kelas sentimen, lalu menampilkan confidence dan probabilitasnya.
                </p>
                <div class="sent-v7-manual-flow">
                    <div class="sent-v7-manual-step">
                        <span class="sent-v7-manual-step-number">01</span>
                        <div>
                            <p class="sent-v7-manual-step-title">Tulis komentar</p>
                            <p class="sent-v7-manual-step-copy">Masukkan opini singkat dan jelas tentang layanan.</p>
                        </div>
                    </div>
                    <div class="sent-v7-manual-step">
                        <span class="sent-v7-manual-step-number">02</span>
                        <div>
                            <p class="sent-v7-manual-step-title">Analisis IndoBERT</p>
                            <p class="sent-v7-manual-step-copy">Custom loading menutup proses inferensi di belakang layar.</p>
                        </div>
                    </div>
                    <div class="sent-v7-manual-step">
                        <span class="sent-v7-manual-step-number">03</span>
                        <div>
                            <p class="sent-v7-manual-step-title">Baca hasil</p>
                            <p class="sent-v7-manual-step-copy">Lihat label, confidence, probabilitas, dan riwayat.</p>
                        </div>
                    </div>
                </div>
            </section>
            <div class="sent-v7-manual-input-label">Masukkan komentar berbahasa Indonesia</div>
            """,
            unsafe_allow_html=True,
        )

        user_text = st.text_area(
            "Masukkan komentar berbahasa Indonesia",
            placeholder=(
                f"Contoh: Layanan {layanan} saya stabil dan petugasnya cepat membantu."
            ),
            height=150,
            key="sent_v7_manual_text",
            label_visibility="collapsed",
        )

        st.markdown(
            """
            <div class="sent-v7-manual-helper">
                <span><strong>Tips:</strong> gunakan kalimat utuh agar konteks sentimen lebih jelas.</span>
                <span>Output: Positif • Netral • Negatif</span>
            </div>
            """,
            unsafe_allow_html=True,
        )

        st.button(
            "Analisis Sentimen",
            type="primary",
            use_container_width=True,
            key="sent_v7_analyze_button",
            on_click=_queue_manual_prediction,
        )

        st.markdown(
            '<p class="sent-v7-manual-action-note">Model dimuat dengan <strong>@st.cache_resource</strong>; hasil baru akan masuk ke riwayat akun setelah analisis selesai.</p>',
            unsafe_allow_html=True,
        )

        prediction_error = str(
            st.session_state.get(_PREDICTION_ERROR_KEY, "")
        ).strip()
        if prediction_error:
            st.warning(prediction_error)
            st.session_state[_PREDICTION_ERROR_KEY] = ""

        if st.session_state.get(_PREDICTION_PENDING_KEY, False):
            queued_text = str(
                st.session_state.get(_PREDICTION_TEXT_KEY, user_text)
            ).strip()

            try:
                queued_service = str(
                    st.session_state.get(_PREDICTION_SERVICE_KEY, layanan)
                ).strip() or layanan
                if bool(st.session_state.get("demo_mode", False)):
                    result = get_demo_prediction(queued_text, queued_service)
                    model_source = "Mode Demo · klasifikasi lokal tanpa IndoBERT"
                else:
                    runtime, model_source = load_service_model(queued_service)
                    result = predict_sentiment(queued_text, runtime)

                if result:
                    _save_prediction_history(queued_text, result)
                    log_activity(
                        "SENTIMENT_PREDICTION",
                        "Analisis Sentimen",
                        f"Menjalankan prediksi sentimen manual untuk layanan {queued_service} dengan hasil {result.get('label_id', result.get('label', '-'))}.",
                        service=queued_service,
                        status="success",
                        metadata={
                            "sentiment": result.get("label"),
                            "confidence": float(result.get("confidence", 0.0) or 0.0),
                            "text_length": len(queued_text),
                            "model_source": model_source,
                        },
                    )
                    _render_prediction_result(result, model_source)
            finally:
                # Reset antrean setelah satu proses selesai agar prediksi
                # tidak dijalankan ulang pada interaksi berikutnya.
                st.session_state[_PREDICTION_PENDING_KEY] = False
                st.session_state[_PREDICTION_TEXT_KEY] = ""
                st.session_state[_PREDICTION_SERVICE_KEY] = ""

        history = _get_prediction_history()
        if history:
            with st.expander(
                f"Riwayat 10 prediksi terakhir • {len(history)}/{_MAX_HISTORY}",
                expanded=False,
            ):
                _render_prediction_history(history)
    except Exception as exc:
        st.error(f"Prediksi manual gagal ditampilkan: {exc}")


# -----------------------------------------------------------------------------
# Entry point halaman
# -----------------------------------------------------------------------------
def render_sentiment() -> None:
    """Render halaman Analisis Sentimen dengan Telkomsel aktif penuh."""
    loading_handle = None
    minimum_loading_seconds = 0.0

    try:
        # Callback widget mengisi label ini sebelum Streamlit melakukan rerun.
        # Overlay custom dipanggil paling awal agar menutupi proses pemuatan
        # data, ringkasan, dan visualisasi layanan yang baru dipilih.
        service_loading_label = st.session_state.pop(
            _SERVICE_SWITCH_LOADING_KEY,
            None,
        )
        filter_loading_label = st.session_state.pop(
            _INDIBIZ_FILTER_LOADING_KEY,
            None,
        )
        wordcloud_loading_label = st.session_state.pop(
            _WORDCLOUD_VIEW_LOADING_KEY,
            None,
        )
        wordcloud_download_loading_label = st.session_state.pop(
            _WORDCLOUD_DOWNLOAD_LOADING_KEY,
            None,
        )
        if service_loading_label:
            loading_handle = mulai_loading_aksi(str(service_loading_label))
            minimum_loading_seconds = _SERVICE_SWITCH_MIN_SECONDS
        elif filter_loading_label:
            loading_handle = mulai_loading_aksi(str(filter_loading_label))
            minimum_loading_seconds = _INDIBIZ_FILTER_MIN_SECONDS
        elif wordcloud_loading_label:
            loading_handle = mulai_loading_aksi(str(wordcloud_loading_label))
            minimum_loading_seconds = _WORDCLOUD_VIEW_MIN_SECONDS
        elif wordcloud_download_loading_label:
            loading_handle = mulai_loading_aksi(
                str(wordcloud_download_loading_label)
            )
            minimum_loading_seconds = _WORDCLOUD_DOWNLOAD_MIN_SECONDS
        elif st.session_state.get(_PREDICTION_PENDING_KEY, False):
            # Prediksi manual tetap memakai loader custom yang sama.
            loading_handle = mulai_loading_aksi("Menganalisis komentar")

        _sinkronkan_layanan_sentimen_saat_masuk()
        _inject_sentiment_css()
        _inject_sentiment_light_css()
        layanan_awal = str(
            st.session_state.get("sent_v7_service_selector", "IndiHome")
        ).strip()
        if layanan_awal not in _LAYANAN_LIST:
            layanan_awal = "IndiHome"
        data_source = (
            "Data Sample Demo"
            if bool(st.session_state.get("demo_mode", False))
            else get_data_source_label(layanan_awal)
        )
        _render_hero(data_source, layanan_awal)

        # Selector layanan dirender satu kali melalui panel interaktif di bawah.
        # Blok heading/selector lama sengaja dihapus agar tidak muncul duplikat.
        layanan = _render_service_selector()

        if layanan not in _ANALYTICS_READY_SERVICES:
            _render_coming_soon(layanan)
            return

        with st.spinner(f"Memuat data sentimen {layanan}..."):
            df = _prepare_dataframe(layanan)
        if df.empty:
            st.warning(
                f"Data sentimen {layanan} belum tersedia atau tidak dapat dibaca. "
                "Periksa file layanan di folder data, lalu restart Streamlit."
            )
            return

        if layanan == "IndiBiz":
            label_platform_aktif = str(
                st.session_state.get(_INDIBIZ_FILTER_APPLIED_KEY, "Semua Platform")
            )
            indibiz_filtered_df = _filter_indibiz_platform(df, label_platform_aktif)
        else:
            indibiz_filtered_df = df.copy()
        data_analisis = indibiz_filtered_df if layanan == "IndiBiz" else df

        if layanan == "IndiBiz":
            _render_indibiz_phase11_status()

        _section_heading(
            "02",
            "Ringkasan Sentimen",
            f"Empat indikator utama dari seluruh komentar {layanan}.",
        )
        _render_overview_metrics(data_analisis)

        _section_heading(
            "03",
            "Visualisasi Utama",
            (
                "Jumlah komentar, persentase sentimen, dan confidence rata-rata hasil IndoBERT IndiBiz."
                if layanan == "IndiBiz"
                else "Distribusi sentimen dan perbandingan antarplatform."
            ),
        )
        if layanan == "IndiBiz":
            indibiz_filtered_df = _render_indibiz_phase17_visualization(df)
            data_analisis = indibiz_filtered_df
        else:
            _render_main_visualizations(df)

        _section_heading(
            "04",
            "Tren Waktu",
            "Hover pada garis untuk melihat jumlah komentar setiap tanggal.",
        )
        _render_timeline(data_analisis)

        _section_heading(
            "05",
            "Analisis per Platform",
            "Klik tab untuk membandingkan profil sentimen Twitter/X, Instagram, dan TikTok.",
        )
        _render_platform_tabs(data_analisis)

        if layanan == "IndiBiz":
            _section_heading(
                "06",
                "10 Komentar Teratas",
                "Urutan berdasarkan confidence tertinggi dan mengikuti filter platform aktif.",
            )
            _render_indibiz_top_comments_table(indibiz_filtered_df)
        elif layanan == "Telkomsel":
            _section_heading(
                "06",
                "Top Komentar per Platform",
                "Maksimal lima komentar per sentimen pada Twitter/X, Instagram, dan TikTok.",
            )
            _render_telkomsel_top_comments_table(df)
        else:
            _section_heading(
                "06",
                "Contoh Komentar",
                "Lima komentar dengan confidence tertinggi untuk setiap kelas sentimen.",
            )
            _render_comment_examples(df)

        _section_heading(
            "07",
            "WordCloud per Sentimen",
            "Positif hijau, netral biru, dan negatif merah menggunakan Matplotlib WordCloud.",
        )
        _render_service_wordclouds(data_analisis, layanan)

        prediction_section_number = "08"
        _section_heading(
            prediction_section_number,
            "Prediksi Sentimen Manual",
            (
                "Masukkan satu komentar baru dan jalankan inferensi IndoBERT secara langsung."
                if layanan in _READY_SERVICES
                else "Analitik data tersedia, tetapi model prediksi manual layanan ini belum diaktifkan."
            ),
        )
        if layanan in _READY_SERVICES:
            _render_manual_prediction(layanan)
        else:
            _render_coming_soon(layanan)

    except Exception as exc:
        st.session_state[_PREDICTION_PENDING_KEY] = False
        st.error(f"Halaman Analisis Sentimen gagal dimuat: {exc}")
    finally:
        # Overlay tetap aktif selama seluruh rerun. Untuk perpindahan layanan,
        # durasi minimum singkat membuat animasi sempat terlihat tanpa
        # menahan proses data lebih lama dari yang diperlukan.
        if loading_handle is not None:
            try:
                elapsed = time.monotonic() - float(loading_handle.mulai_pada)
                remaining = minimum_loading_seconds - elapsed
                if remaining > 0:
                    time.sleep(remaining)
            except Exception:
                # Kegagalan menghitung durasi tidak boleh menahan halaman.
                pass
            selesaikan_loading_aksi(loading_handle)
