# pages/recommendation.py
# TAHAP 5 FASE 7 - OPTIMASI PERFORMA: cache kalkulasi influencer dari edge list SNA.
"""Halaman rekomendasi konten dan influencer untuk seluruh layanan Telkom Group.

Halaman ini menggabungkan data analisis topik, sentimen, dan jaringan sosial
untuk menyusun rekomendasi konten yang dapat langsung digunakan. Data aktual
diprioritaskan, sedangkan data fallback hanya dipakai ketika berkas sumber tidak
tersedia atau tidak dapat diolah.
"""

from __future__ import annotations

import math
import re
import time
from html import escape
from pathlib import Path
from textwrap import dedent, fill
from typing import Any

import pandas as pd
import streamlit as st
from utils.streamlit_compat import render_html_iframe

from utils.audit_logger import log_activity
from utils.gemini_client import (
    GEMINI_AVAILABLE,
    generate_content_idea,
    generate_recommendation,
    get_fallback_content_idea,
    get_gemini_runtime_status,
    init_gemini,
)
from utils.dummy_data import (
    get_demo_influencers,
    get_demo_sentiment,
    get_demo_sna,
    get_dummy_topic_data,
)
from utils.topic_classifier import summarize_topics
from utils.topic_data_service import load_enriched_topic_data
from utils.data_loader import (
    get_sentiment_file_signature,
    get_sentiment_source_name,
    get_sna_source_names,
    load_influencer_content_data,
    load_indibiz_top_kata,
    load_indibiz_topics,
    load_model_status,
    load_sna_data,
    load_topic_data,
    sentiment_file_exists,
    sna_file_exists,
)

try:
    from utils.loading_screen import (
        mulai_loading_aksi,
        mulai_loading_global,
        selesaikan_loading_aksi,
        selesaikan_loading_global,
    )
except Exception:  # pragma: no cover - fallback jika utilitas loading belum tersedia
    mulai_loading_aksi = None
    mulai_loading_global = None
    selesaikan_loading_aksi = None
    selesaikan_loading_global = None

# Fragment menjaga perubahan kontrol matriks tetap lokal. Hasil analisis utama
# baru dirender ulang setelah tombol Apply atau Reset benar-benar mengubah state.
_FRAGMENT_DECORATOR = getattr(st, "fragment", None)
if _FRAGMENT_DECORATOR is None:  # pragma: no cover - fallback Streamlit lama
    def _FRAGMENT_DECORATOR(function):
        return function

# Ringkasan Top 5 memakai service bersama tanpa mengimpor seluruh halaman
# Analisis Topik. Ini mencegah Matplotlib, WordCloud, dan pipeline visual lain
# ikut dimuat ketika pengguna hanya membuka halaman Rekomendasi.


# -----------------------------------------------------------------------------
# KONFIGURASI UMUM
# -----------------------------------------------------------------------------

LAYANAN_OPTIONS = ["IndiHome", "IndiBiz", "Telkomsel"]
ACTIVE_LAYANAN_OPTIONS = ["IndiHome", "IndiBiz", "Telkomsel"]
PLATFORM_ORDER = ["twitter", "instagram", "tiktok"]
PROJECT_ROOT = Path(__file__).resolve().parent.parent
INDIBIZ_SNA_FILE = PROJECT_ROOT / "data" / "indibiz_output_sna.csv"
INDIBIZ_TOPIC_FILE = PROJECT_ROOT / "data" / "indibiz_output_top_topic.csv"
INDIBIZ_TOP_WORD_FILE = PROJECT_ROOT / "data" / "indibiz_output_top_kata.csv"
RECOMMENDATION_ACTION_LOADING_KEY = "_recommendation_action_loading_label"
MATRIX_FILTER_DEFAULT_MIN_SCORE = 1
MATRIX_FILTER_EVENT_PREFIX = "_recommendation_matrix_filter_event_"
MATRIX_FILTER_FEEDBACK_PREFIX = "_recommendation_matrix_filter_feedback_"
MATRIX_TABLE_FILTER_EVENT_KEY = "_recommendation_matrix_table_filter_event"
MATRIX_TABLE_FILTER_FEEDBACK_KEY = "_recommendation_matrix_table_filter_feedback"
MATRIX_TABLE_FILTER_APPLIED_KEYS = {
    "keyword": "_rec_matrix_table_applied_keyword",
    "platforms": "_rec_matrix_table_applied_platforms",
    "sort_by": "_rec_matrix_table_applied_sort_by",
    "descending": "_rec_matrix_table_applied_descending",
    "row_limit": "_rec_matrix_table_applied_limit",
}
RECOMMENDATION_CACHE_RECOVERY_KEY = "_recommendation_cache_recovery_v1_1"
RECOMMENDATION_CACHE_ERROR_MARKERS = (
    "StringDtype.__init__",
    "datetime64[us]",
    "dtype('<M8[us]')",
    'dtype("<M8[us]")',
    "pickle",
    "unpickle",
)
TOPIC_AI_CONTENT_STATE_KEY = "_recommendation_topic_ai_content"
TOPIC_AI_VARIATION_STATE_KEY = "_recommendation_topic_ai_variation"
TOPIC_AI_REQUEST_STATE_KEY = "_recommendation_topic_ai_request"
# FASE12_UI_AI_STUDIO_V1_5
# FASE12_FILTER_MANUAL_V1_4
# FASE12_INFLUENCER_DETAIL_CUSTOM_LOADING_V1_9
# Nilai draft hanya mengikuti pilihan pengguna di dalam form. Nilai aktif baru
# berubah setelah tombol Terapkan Filter ditekan.
RECOMMENDATION_FILTER_DEFAULTS = {
    "layanan": "IndiHome",
    "platform": "Instagram",
    # Nilai cadangan. Saat halaman dirender, topik dinormalisasi ke daftar
    # Top 5 layanan aktif yang sudah dibuang kategori Lainnya.
    "topik": "Kecepatan Lambat",
}

MISCELLANEOUS_TOPIC_ALIASES = {
    "lainnya",
    "topik lainnya",
    "topik lain",
    "other",
    "others",
}

# Fallback dipakai hanya jika output Analisis Topik tidak dapat dibaca.
# Urutan mengikuti tampilan Top 5 terbaru setelah kategori Lainnya dikeluarkan.
SERVICE_TOPIC_OPTION_FALLBACKS: dict[str, list[dict[str, Any]]] = {
    "IndiHome": [
        {"topik": "Lainnya", "jumlah_komentar": 81568, "sentimen_dominan": "neutral"},
        {"topik": "Kecepatan Lambat", "jumlah_komentar": 4016, "sentimen_dominan": "negative"},
        {"topik": "Gangguan Jaringan", "jumlah_komentar": 3191, "sentimen_dominan": "negative"},
        {"topik": "Permintaan Bantuan", "jumlah_komentar": 2059, "sentimen_dominan": "neutral"},
        {"topik": "Harga Mahal", "jumlah_komentar": 739, "sentimen_dominan": "negative"},
    ],
    "IndiBiz": [
        {"topik": "Bisnis, UMKM & Digitalisasi", "jumlah_komentar": 1985, "sentimen_dominan": "neutral"},
        {"topik": "Topik Lainnya", "jumlah_komentar": 1984, "sentimen_dominan": "neutral"},
        {"topik": "Kecepatan & Stabilitas Internet", "jumlah_komentar": 231, "sentimen_dominan": "positive"},
        {"topik": "Layanan Pelanggan & Admin", "jumlah_komentar": 209, "sentimen_dominan": "neutral"},
        {"topik": "Harga, Tagihan & Paket", "jumlah_komentar": 125, "sentimen_dominan": "neutral"},
    ],
    "Telkomsel": [
        {"topik": "Lainnya", "jumlah_komentar": 41960, "sentimen_dominan": "neutral"},
        {"topik": "Harga Mahal", "jumlah_komentar": 2230, "sentimen_dominan": "negative"},
        {"topik": "Kecepatan Lambat", "jumlah_komentar": 1208, "sentimen_dominan": "negative"},
        {"topik": "Permintaan Bantuan", "jumlah_komentar": 897, "sentimen_dominan": "neutral"},
        {"topik": "Tanya Kuota dan Masa Aktif", "jumlah_komentar": 317, "sentimen_dominan": "neutral"},
    ],
}
RECOMMENDATION_FILTER_DRAFT_KEYS = {
    "layanan": "recommendation_filter_draft_service",
    "platform": "recommendation_filter_draft_platform",
    "topik": "recommendation_filter_draft_topic",
}
RECOMMENDATION_FILTER_ACTIVE_KEYS = {
    "layanan": "recommendation_filter_active_service",
    "platform": "recommendation_filter_active_platform",
    "topik": "recommendation_filter_active_topic",
}
RECOMMENDATION_FILTER_RESET_PENDING_KEY = "_recommendation_filter_reset_pending"
RECOMMENDATION_FILTER_FEEDBACK_KEY = "_recommendation_filter_feedback"
ACCOUNT_TYPE_FILTER_KEY = "recommendation_account_type_filter"
ACCOUNT_TYPE_CARD_TARGET = 9
PLATFORM_CARD_TARGET = 3

# Kata kunci klasifikasi akun media. Daftar manual disediakan agar peneliti
# dapat menambah pengecualian tanpa mengubah fungsi klasifikasi utama.
MEDIA_ACCOUNT_KEYWORDS = (
    "news", "media", "tv", "official", "id", "berita", "info",
    "update", "kompas", "detik", "tribun", "cnbc",
    "cnnindonesia", "tempo",
)
MEDIA_ACCOUNT_MANUAL: set[str] = set()
INFLUENCER_ACCOUNT_MANUAL: set[str] = set()
ACCOUNT_TYPE_LABELS = {
    "media": "🟦 Media",
    "influencer": "🟩 Influencer",
}


# CSS kecil untuk menyembunyikan indikator proses bawaan Streamlit pada halaman ini.
# Aksi filter tetap memakai overlay custom dari utils/loading_screen.py.
RECOMMENDATION_HIDE_NATIVE_LOADING_CSS = """
<style>
    div[data-testid="stStatusWidget"],
    div[data-testid="stSpinner"] {
        visibility: hidden !important;
        opacity: 0 !important;
        pointer-events: none !important;
        width: 0 !important;
        height: 0 !important;
        max-width: 0 !important;
        max-height: 0 !important;
        overflow: hidden !important;
    }

/* Empty state khusus saat layanan belum memiliki influencer tervalidasi.
   Tujuannya agar halaman tidak menampilkan placeholder palsu seperti
   "Data belum tersedia" atau "@influencer utama". */
.rec-empty-state-panel {
    position: relative;
    overflow: hidden;
    margin: 8px 0 18px;
    padding: 22px 24px;
    border: 1px solid rgba(29,161,242,.22);
    border-radius: 18px;
    background:
        radial-gradient(circle at 12% 12%, rgba(229,57,53,.22), transparent 30%),
        radial-gradient(circle at 86% 18%, rgba(29,161,242,.20), transparent 32%),
        linear-gradient(145deg, rgba(20,24,34,.96), rgba(13,13,13,.98));
    box-shadow: 0 22px 52px rgba(0,0,0,.34), inset 0 1px 0 rgba(255,255,255,.08);
    isolation: isolate;
}

.rec-empty-state-panel::before {
    content: '';
    position: absolute;
    inset: 0;
    background: linear-gradient(110deg, transparent 30%, rgba(255,255,255,.10) 48%, transparent 68%);
    transform: translateX(-125%);
    animation: recEmptySweep 5.2s ease-in-out infinite;
    pointer-events: none;
}

.rec-empty-state-panel::after {
    content: '';
    position: absolute;
    left: 20px;
    right: 20px;
    bottom: 0;
    height: 3px;
    border-radius: 999px 999px 0 0;
    background: linear-gradient(90deg, #E53935, #FFB020, #1DA1F2, #22C55E);
    opacity: .86;
}

.rec-empty-state-top {
    position: relative;
    z-index: 1;
    display: grid;
    grid-template-columns: 54px minmax(0, 1fr);
    align-items: center;
    gap: 15px;
    margin-bottom: 16px;
}

.rec-empty-state-icon {
    display: grid;
    place-items: center;
    width: 54px;
    height: 54px;
    border-radius: 18px;
    color: #FFFFFF;
    background: linear-gradient(145deg, #E53935, #1DA1F2);
    box-shadow: 0 0 28px rgba(229,57,53,.24), 0 0 34px rgba(29,161,242,.16);
    font-size: 22px;
    font-weight: 950;
}

.rec-empty-state-kicker {
    display: block;
    margin-bottom: 4px;
    color: #FF8A87;
    font-size: 0.75rem /* FIX: minimum 12px agar terbaca di tablet */;
    font-weight: 950;
    letter-spacing: .11em;
    text-transform: uppercase;
}

.rec-empty-state-title {
    margin: 0;
    color: #FFFFFF;
    font-family: 'Plus Jakarta Sans', sans-serif;
    font-size: clamp(18px, 2vw, 25px);
    font-weight: 850;
    letter-spacing: -.03em;
    line-height: 1.18;
}

.rec-empty-state-desc {
    position: relative;
    z-index: 1;
    max-width: 920px;
    margin: 0 0 16px;
    color: rgba(255,255,255,.76);
    font-size: 14px;
    font-weight: 650;
    line-height: 1.65;
}

.rec-empty-state-grid {
    position: relative;
    z-index: 1;
    display: grid;
    grid-template-columns: repeat(3, minmax(0, 1fr));
    gap: 10px;
}

.rec-empty-mini-card {
    min-height: 95px;
    padding: 14px;
    border: 1px solid rgba(255,255,255,.10);
    border-radius: 15px;
    background: rgba(255,255,255,.045);
    box-shadow: inset 0 1px 0 rgba(255,255,255,.06);
}

.rec-empty-mini-card span {
    display: inline-flex;
    margin-bottom: 7px;
    padding: 5px 8px;
    border-radius: 999px;
    color: #FFFFFF;
    background: rgba(229,57,53,.18);
    border: 1px solid rgba(229,57,53,.28);
    font-size: 0.75rem /* FIX: minimum 12px agar terbaca di tablet */;
    font-weight: 900;
    letter-spacing: .06em;
    text-transform: uppercase;
}

.rec-empty-mini-card:nth-child(2) span {
    background: rgba(255,176,32,.18);
    border-color: rgba(255,176,32,.30);
}

.rec-empty-mini-card:nth-child(3) span {
    background: rgba(29,161,242,.18);
    border-color: rgba(29,161,242,.30);
}

.rec-empty-mini-card p {
    margin: 0;
    color: rgba(255,255,255,.76);
    font-size: 12px;
    font-weight: 650;
    line-height: 1.55;
}

.rec-topic-pill.is-empty {
    color: #FFCC80 !important;
    border-color: rgba(255,176,32,.40) !important;
    background: rgba(255,176,32,.10) !important;
}

@keyframes recEmptySweep {
    0%, 54% { transform: translateX(-125%); opacity: 0; }
    62% { opacity: .75; }
    82%, 100% { transform: translateX(125%); opacity: 0; }
}

@media (max-width: 820px) {
    .rec-empty-state-grid { grid-template-columns: 1fr; }
    .rec-empty-state-top { grid-template-columns: 46px minmax(0, 1fr); }
    .rec-empty-state-icon { width: 46px; height: 46px; border-radius: 15px; }
}

@media (prefers-reduced-motion: reduce) {
    .rec-empty-state-panel::before { animation: none !important; }
}

</style>
"""


RECOMMENDATION_FILTER_FORM_CSS = """
<style>
/* Form utama menahan perubahan selectbox sampai pengguna menekan tombol. */
div[data-testid="stForm"] {
    margin: 0 0 8px !important;
    padding: 0 !important;
    border: 0 !important;
    background: transparent !important;
}

div[data-testid="stForm"] div[data-testid="stFormSubmitButton"] button {
    min-height: 46px !important;
    border-radius: 13px !important;
    font-family: 'Plus Jakarta Sans', sans-serif !important;
    font-size: 13px !important;
    font-weight: 850 !important;
    letter-spacing: -.01em !important;
    transition: transform .18s ease, border-color .18s ease, box-shadow .18s ease !important;
}

div[data-testid="stForm"] div[data-testid="stFormSubmitButton"] button:hover {
    transform: translateY(-1px) !important;
}

div[data-testid="stForm"] div[data-testid="stFormSubmitButton"] button[kind="primary"] {
    border: 1px solid rgba(229,57,53,.72) !important;
    background: linear-gradient(135deg, #E53935, #FF5252) !important;
    box-shadow: 0 12px 28px rgba(229,57,53,.20) !important;
    color: #FFFFFF !important;
}

div[data-testid="stForm"] div[data-testid="stFormSubmitButton"] button[kind="secondary"] {
    border: 1px solid rgba(255,255,255,.15) !important;
    background: linear-gradient(145deg, #242424, #1A1A1A) !important;
    color: rgba(255,255,255,.88) !important;
}

.rec-filter-active-note {
    margin: 3px 0 18px;
    padding: 11px 14px;
    border: 1px solid rgba(255,255,255,.09);
    border-radius: 13px;
    background: rgba(255,255,255,.035);
    color: rgba(255,255,255,.67);
    font-size: 12px;
    font-weight: 650;
    line-height: 1.55;
}

.rec-filter-active-note strong {
    color: #FFFFFF;
    font-weight: 850;
}

.rec-filter-active-note span {
    color: #FF8A87;
    font-weight: 850;
}
</style>
"""

PHASE12_AI_CSS = """
<style>
/* ========================================================================== */
/* AI CONTENT STUDIO - VISUAL INTERAKTIF                                      */
/* ========================================================================== */
.rec-ai-shell {
    position: relative;
    isolation: isolate;
    display: block !important;
    visibility: visible !important;
    opacity: 1 !important;
    overflow: hidden;
    min-height: 220px;
    margin: 18px 0 24px;
    padding: 26px;
    border: 1px solid rgba(255,255,255,.12);
    border-radius: 24px;
    background:
        radial-gradient(circle at 8% 12%, rgba(229,57,53,.26), transparent 30%),
        radial-gradient(circle at 92% 12%, rgba(29,161,242,.20), transparent 32%),
        radial-gradient(circle at 72% 100%, rgba(76,175,80,.12), transparent 30%),
        linear-gradient(145deg, rgba(25,25,30,.99), rgba(10,12,18,.99));
    box-shadow:
        0 28px 70px rgba(0,0,0,.38),
        inset 0 1px 0 rgba(255,255,255,.08);
    transition: border-color .22s ease, box-shadow .22s ease;
}
.rec-ai-shell:hover {
    border-color: rgba(255,255,255,.20);
    box-shadow:
        0 34px 82px rgba(0,0,0,.46),
        0 0 0 1px rgba(229,57,53,.06),
        inset 0 1px 0 rgba(255,255,255,.10);
}
.rec-ai-shell::before {
    content: '';
    position: absolute;
    inset: 0;
    z-index: 0;
    pointer-events: none;
    background-image:
        linear-gradient(rgba(255,255,255,.026) 1px, transparent 1px),
        linear-gradient(90deg, rgba(255,255,255,.026) 1px, transparent 1px);
    background-size: 34px 34px;
    mask-image: linear-gradient(to bottom, rgba(0,0,0,.92), transparent 92%);
    opacity: .52;
}
.rec-ai-shell::after {
    content: '';
    position: absolute;
    z-index: 1;
    left: 24px;
    right: 24px;
    bottom: 0;
    height: 3px;
    border-radius: 999px 999px 0 0;
    background: linear-gradient(90deg, #E53935, #FFB020, #1DA1F2, #8B5CF6, #4CAF50, #E53935);
    background-size: 100% 100%;
    opacity: .95;
}
.rec-ai-orb {
    position: absolute;
    z-index: 0;
    width: 260px;
    height: 260px;
    border-radius: 50%;
    opacity: .30;
    pointer-events: none;
}
.rec-ai-orb.one {
    top: -145px;
    left: 5%;
    background: radial-gradient(circle, rgba(229,57,53,.48) 0%, rgba(229,57,53,.18) 42%, rgba(229,57,53,0) 72%);
}
.rec-ai-orb.two {
    right: 2%;
    bottom: -170px;
    background: radial-gradient(circle, rgba(29,161,242,.42) 0%, rgba(29,161,242,.16) 42%, rgba(29,161,242,0) 72%);
}
.rec-ai-heading {
    position: relative;
    z-index: 1;
    display: flex;
    align-items: flex-start;
    justify-content: space-between;
    gap: 22px;
}
.rec-ai-brand {
    display: flex;
    align-items: flex-start;
    gap: 16px;
    min-width: 0;
}
.rec-ai-logo {
    position: relative;
    display: grid;
    flex: 0 0 54px;
    width: 54px;
    height: 54px;
    place-items: center;
    border: 1px solid rgba(255,255,255,.15);
    border-radius: 18px;
    color: #FFFFFF;
    background:
        linear-gradient(145deg, rgba(229,57,53,.95), rgba(139,92,246,.82) 52%, rgba(29,161,242,.90));
    box-shadow: 0 15px 34px rgba(229,57,53,.22), inset 0 1px 0 rgba(255,255,255,.30);
    font-size: 25px;
}
.rec-ai-logo::after {
    content: '';
    position: absolute;
    inset: -6px;
    border: 1px solid rgba(255,255,255,.10);
    border-radius: 22px;
    opacity: .55;
}
.rec-ai-copy {
    min-width: 0;
}
.rec-ai-eyebrow {
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    gap: 8px;
    margin-bottom: 7px;
    color: #FF918E;
    font-size: 0.75rem /* FIX: minimum 12px agar terbaca di tablet */;
    font-weight: 900;
    letter-spacing: .13em;
    text-transform: uppercase;
}
.rec-ai-eyebrow::before {
    content: '';
    width: 22px;
    height: 2px;
    border-radius: 999px;
    background: linear-gradient(90deg, #E53935, #FFB020);
}
.rec-ai-heading h2 {
    margin: 0;
    color: #FFFFFF;
    font-family: 'Plus Jakarta Sans', sans-serif;
    font-size: clamp(22px, 2.35vw, 31px);
    font-weight: 900;
    letter-spacing: -.045em;
    line-height: 1.12;
}
.rec-ai-heading p {
    max-width: 790px;
    margin: 10px 0 0;
    color: rgba(255,255,255,.69);
    font-size: 13px;
    font-weight: 600;
    line-height: 1.68;
}
.rec-ai-feature-row {
    display: flex;
    flex-wrap: wrap;
    gap: 8px;
    margin-top: 15px;
}
.rec-ai-feature-chip {
    display: inline-flex;
    align-items: center;
    gap: 7px;
    padding: 7px 10px;
    border: 1px solid rgba(255,255,255,.09);
    border-radius: 999px;
    color: rgba(255,255,255,.72);
    background: rgba(255,255,255,.045);
    font-size: 0.75rem /* FIX: minimum 12px agar terbaca di tablet */;
    font-weight: 800;
    transition: transform .2s ease, color .2s ease, border-color .2s ease, background .2s ease;
}
.rec-ai-feature-chip:hover {
    transform: translateY(-2px);
    color: #FFFFFF;
    border-color: rgba(255,255,255,.19);
    background: rgba(255,255,255,.08);
}
.rec-ai-feature-chip i {
    display: inline-block;
    width: 6px;
    height: 6px;
    border-radius: 50%;
    background: var(--chip-color, #E53935);
    box-shadow: 0 0 12px var(--chip-color, #E53935);
}
.rec-gemini-badge {
    position: relative;
    display: inline-flex;
    align-items: center;
    gap: 8px;
    flex: 0 0 auto;
    padding: 9px 12px;
    border-radius: 999px;
    font-size: 0.75rem /* FIX: minimum 12px agar terbaca di tablet */;
    font-weight: 900;
    letter-spacing: .025em;
    transition: transform .2s ease, box-shadow .2s ease;
}
.rec-gemini-badge:hover {
    transform: translateY(-2px) scale(1.02);
}
.rec-gemini-badge::before {
    content: '';
    width: 8px;
    height: 8px;
    border-radius: 50%;
    background: currentColor;
    box-shadow: 0 0 10px currentColor;
}
.rec-gemini-badge.online {
    color: #77F29A;
    border: 1px solid rgba(76,175,80,.46);
    background: rgba(29,89,55,.38);
    box-shadow: 0 10px 26px rgba(76,175,80,.10);
}
.rec-gemini-badge.offline {
    color: #FFBE63;
    border: 1px solid rgba(255,152,0,.48);
    background: rgba(93,58,13,.40);
    box-shadow: 0 10px 26px rgba(255,152,0,.10);
}

/* Tombol AI: efek shimmer, lift, dan feedback saat ditekan. */
div[data-testid="stButton"] button {
    position: relative !important;
    overflow: hidden !important;
    min-height: 46px !important;
    border-radius: 14px !important;
    font-family: 'Plus Jakarta Sans', sans-serif !important;
    font-size: 12px !important;
    font-weight: 850 !important;
    letter-spacing: -.01em !important;
    transition: transform .18s ease, box-shadow .22s ease, border-color .22s ease, filter .22s ease !important;
}
div[data-testid="stButton"] button::before {
    content: '' !important;
    position: absolute !important;
    top: 0 !important;
    left: -135% !important;
    width: 70% !important;
    height: 100% !important;
    background: linear-gradient(90deg, transparent, rgba(255,255,255,.24), transparent) !important;
    transform: skewX(-18deg) !important;
    transition: left .55s ease !important;
    pointer-events: none !important;
}
div[data-testid="stButton"] button:hover::before {
    left: 145% !important;
}
div[data-testid="stButton"] button:hover {
    transform: translateY(-2px) !important;
    filter: saturate(1.12) brightness(1.04) !important;
}
div[data-testid="stButton"] button:active {
    transform: translateY(0) scale(.985) !important;
}
div[data-testid="stButton"] button[kind="primary"] {
    border: 1px solid rgba(255,255,255,.13) !important;
    color: #FFFFFF !important;
    background: linear-gradient(110deg, #E53935 0%, #F0445B 38%, #8B5CF6 68%, #1DA1F2 100%) !important;
    background-size: 180% 100% !important;
    box-shadow: 0 15px 34px rgba(104,91,216,.20), inset 0 1px 0 rgba(255,255,255,.20) !important;
}
div[data-testid="stButton"] button[kind="primary"]:hover {
    background-position: 100% 0 !important;
    box-shadow: 0 19px 42px rgba(104,91,216,.30), 0 0 0 1px rgba(255,255,255,.07) !important;
}
div[data-testid="stButton"] button[kind="secondary"] {
    border: 1px solid rgba(229,57,53,.72) !important;
    color: #FFD2D0 !important;
    background: linear-gradient(145deg, rgba(229,57,53,.10), rgba(18,18,22,.94)) !important;
    box-shadow: inset 0 1px 0 rgba(255,255,255,.04), 0 12px 28px rgba(0,0,0,.18) !important;
}
div[data-testid="stButton"] button[kind="secondary"]:hover {
    border-color: #FF6965 !important;
    color: #FFFFFF !important;
    background: linear-gradient(145deg, rgba(229,57,53,.22), rgba(24,18,24,.98)) !important;
    box-shadow: 0 16px 34px rgba(229,57,53,.16) !important;
}

.rec-ai-refresh-notice,
.rec-ai-offline-note,
.rec-ai-fallback-note {
    position: relative;
    overflow: hidden;
    margin: 14px 0 10px;
    padding: 13px 15px 13px 44px;
    border-radius: 14px;
    font-size: 0.75rem /* FIX: minimum 12px agar terbaca di tablet */;
    font-weight: 750;
    line-height: 1.55;
    animation: recAiNoticeIn .36s ease-out both;
}
.rec-ai-refresh-notice::before,
.rec-ai-offline-note::before,
.rec-ai-fallback-note::before {
    position: absolute;
    left: 15px;
    top: 50%;
    transform: translateY(-50%);
    font-size: 16px;
}
.rec-ai-refresh-notice {
    color: #C9FBD7;
    border: 1px solid rgba(76,175,80,.30);
    background: linear-gradient(90deg, rgba(27,95,54,.44), rgba(22,54,43,.18));
    box-shadow: 0 12px 28px rgba(76,175,80,.08);
}
.rec-ai-refresh-notice::before { content: '✓'; color: #77F29A; }
.rec-ai-offline-note {
    color: #FFE0B2;
    border: 1px solid rgba(255,152,0,.30);
    background: linear-gradient(90deg, rgba(110,69,16,.42), rgba(48,35,18,.17));
}
.rec-ai-offline-note::before { content: '⚡'; }
.rec-ai-fallback-note {
    color: #FFE0B2;
    border: 1px solid rgba(255,152,0,.30);
    background: linear-gradient(90deg, rgba(110,69,16,.42), rgba(48,35,18,.17));
}
.rec-ai-fallback-note::before { content: '↻'; color: #FFBE63; }

/* Hasil ide konten */
.rec-ai-result {
    position: relative;
    isolation: isolate;
    overflow: hidden;
    margin-top: 20px;
    padding: 0;
    border: 1px solid rgba(255,255,255,.11);
    border-radius: 20px;
    background:
        radial-gradient(circle at 95% 0%, rgba(139,92,246,.12), transparent 28%),
        linear-gradient(145deg, rgba(25,25,29,.99), rgba(13,14,18,.99));
    box-shadow: inset 0 1px 0 rgba(255,255,255,.055), 0 20px 48px rgba(0,0,0,.30);
    animation: recAiResultReveal .48s cubic-bezier(.2,.8,.2,1) both;
    transition: transform .26s ease, border-color .26s ease, box-shadow .26s ease;
}
.rec-ai-result:hover {
    transform: translateY(-3px);
    border-color: rgba(139,92,246,.34);
    box-shadow: inset 0 1px 0 rgba(255,255,255,.08), 0 28px 60px rgba(0,0,0,.38);
}
.rec-ai-result::before {
    content: '';
    position: absolute;
    inset: 0 auto 0 0;
    width: 4px;
    background: linear-gradient(180deg, #E53935, #8B5CF6, #1DA1F2, #4CAF50);
}
.rec-ai-result-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 14px;
    padding: 18px 20px 15px 22px;
    border-bottom: 1px solid rgba(255,255,255,.075);
    background: linear-gradient(90deg, rgba(255,255,255,.028), transparent);
}
.rec-ai-result-title-wrap {
    display: flex;
    align-items: center;
    gap: 12px;
}
.rec-ai-result-icon {
    display: grid;
    width: 38px;
    height: 38px;
    place-items: center;
    flex: 0 0 38px;
    border: 1px solid rgba(255,255,255,.13);
    border-radius: 13px;
    background: linear-gradient(145deg, rgba(229,57,53,.88), rgba(139,92,246,.85));
    box-shadow: 0 12px 26px rgba(139,92,246,.16);
    font-size: 17px;
    transition: transform .22s ease;
}
.rec-ai-result:hover .rec-ai-result-icon {
    transform: rotate(-6deg) scale(1.08);
}
.rec-ai-result-kicker {
    display: block;
    margin: 0 0 2px;
    color: #FF918E;
    font-size: 0.75rem /* FIX: minimum 12px agar terbaca di tablet */;
    font-weight: 900;
    letter-spacing: .12em;
    text-transform: uppercase;
}
.rec-ai-result-heading {
    margin: 0;
    color: #FFFFFF;
    font-family: 'Plus Jakarta Sans', sans-serif;
    font-size: 15px;
    font-weight: 900;
    letter-spacing: -.02em;
}
.rec-ai-source-pill {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    padding: 6px 9px;
    border: 1px solid rgba(255,255,255,.10);
    border-radius: 999px;
    color: rgba(255,255,255,.72);
    background: rgba(255,255,255,.045);
    font-size: 0.75rem /* FIX: minimum 12px agar terbaca di tablet */;
    font-weight: 850;
    white-space: nowrap;
}
.rec-ai-source-pill.live { color: #93F7B0; border-color: rgba(76,175,80,.30); background: rgba(76,175,80,.08); }
.rec-ai-source-pill.fallback { color: #FFD08A; border-color: rgba(255,152,0,.30); background: rgba(255,152,0,.08); }
.rec-ai-result-body {
    padding: 18px 22px 10px;
    color: rgba(255,255,255,.88);
    font-size: 12px;
    font-weight: 600;
    line-height: 1.72;
}
.rec-ai-content-title {
    margin: 0 0 14px;
    padding: 13px 14px;
    border: 1px solid rgba(229,57,53,.18);
    border-radius: 13px;
    color: #FFFFFF;
    background: linear-gradient(90deg, rgba(229,57,53,.13), rgba(139,92,246,.055));
    font-size: 12px;
    font-weight: 850;
    line-height: 1.55;
}
.rec-ai-content-title strong {
    color: #FF918E;
    font-size: 0.75rem /* FIX: minimum 12px agar terbaca di tablet */;
    letter-spacing: .08em;
    text-transform: uppercase;
}
.rec-ai-copy-heading {
    display: flex;
    align-items: center;
    gap: 8px;
    margin: 15px 0 9px;
    color: #FFFFFF;
    font-size: 0.75rem /* FIX: minimum 12px agar terbaca di tablet */;
    font-weight: 900;
    letter-spacing: .07em;
    text-transform: uppercase;
}
.rec-ai-copy-heading::before {
    content: '';
    width: 6px;
    height: 6px;
    border-radius: 50%;
    background: #1DA1F2;
    box-shadow: 0 0 12px rgba(29,161,242,.75);
}
.rec-ai-idea-row {
    display: grid;
    grid-template-columns: 28px minmax(0, 1fr);
    gap: 10px;
    align-items: flex-start;
    margin: 8px 0;
    padding: 11px 12px;
    border: 1px solid rgba(255,255,255,.075);
    border-radius: 12px;
    background: rgba(255,255,255,.025);
    transition: transform .20s ease, border-color .20s ease, background .20s ease;
}
.rec-ai-idea-row:hover {
    transform: translateX(4px);
    border-color: rgba(29,161,242,.28);
    background: linear-gradient(90deg, rgba(29,161,242,.075), rgba(139,92,246,.025));
}
.rec-ai-idea-number {
    display: grid;
    width: 25px;
    height: 25px;
    place-items: center;
    border: 1px solid rgba(29,161,242,.24);
    border-radius: 9px;
    color: #A9DEFF;
    background: rgba(29,161,242,.09);
    font-size: 0.75rem /* FIX: minimum 12px agar terbaca di tablet */;
    font-weight: 900;
}
.rec-ai-idea-row p,
.rec-ai-copy-text {
    margin: 0;
    color: rgba(255,255,255,.79);
    font-size: 0.75rem /* FIX: minimum 12px agar terbaca di tablet */;
    font-weight: 620;
    line-height: 1.68;
}
.rec-ai-copy-text {
    margin: 8px 0;
}
.rec-ai-result-meta {
    display: flex;
    flex-wrap: wrap;
    gap: 8px;
    margin: 4px 22px 20px;
    padding-top: 14px;
    border-top: 1px solid rgba(255,255,255,.075);
}
.rec-ai-meta-chip {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    max-width: 100%;
    padding: 7px 9px;
    border: 1px solid rgba(255,255,255,.085);
    border-radius: 999px;
    color: rgba(255,255,255,.62);
    background: rgba(255,255,255,.035);
    font-size: 0.75rem /* FIX: minimum 12px agar terbaca di tablet */;
    font-weight: 780;
    transition: transform .18s ease, color .18s ease, border-color .18s ease;
}
.rec-ai-meta-chip:hover {
    transform: translateY(-2px);
    color: #FFFFFF;
    border-color: rgba(255,255,255,.18);
}

/* Expander teks siap salin dibuat seperti action drawer. */
div[data-testid="stExpander"] {
    margin-top: 10px !important;
    margin-bottom: 16px !important;
    overflow: hidden !important;
    border: 1px solid rgba(139,92,246,.20) !important;
    border-radius: 16px !important;
    background: linear-gradient(145deg, rgba(22,22,27,.99), rgba(12,13,17,.99)) !important;
    box-shadow: 0 16px 38px rgba(0,0,0,.24) !important;
    transition: transform .22s ease, border-color .22s ease, box-shadow .22s ease !important;
}
div[data-testid="stExpander"]:hover {
    transform: translateY(-2px) !important;
    border-color: rgba(139,92,246,.40) !important;
    box-shadow: 0 22px 48px rgba(0,0,0,.32) !important;
}
div[data-testid="stExpander"] summary {
    min-height: 56px !important;
    padding: 15px 18px !important;
    color: #F7F4FF !important;
    background: linear-gradient(90deg, rgba(139,92,246,.07), rgba(29,161,242,.025)) !important;
    font-weight: 850 !important;
    letter-spacing: -.01em !important;
    transition: background .2s ease, color .2s ease !important;
}
div[data-testid="stExpander"] summary:hover {
    color: #FFFFFF !important;
    background: linear-gradient(90deg, rgba(139,92,246,.14), rgba(29,161,242,.055)) !important;
}
div[data-testid="stCode"] {
    border: 1px solid rgba(255,255,255,.07) !important;
    border-radius: 12px !important;
    background: #0C0E14 !important;
    box-shadow: inset 0 1px 0 rgba(255,255,255,.035) !important;
}

/* ================================================================
   STRATEGI PER SENTIMEN — INTERACTIVE RESPONSE CARDS v1.8
   ================================================================ */
.rec-sentiment-strategy-grid {
    display: grid;
    grid-template-columns: repeat(3, minmax(0, 1fr));
    align-items: stretch;
    gap: 18px;
    margin: 18px 0 30px;
    perspective: 1200px;
}
.rec-sentiment-strategy-card {
    position: relative;
    isolation: isolate;
    display: flex;
    min-width: 0;
    min-height: 430px;
    padding: 24px;
    overflow: hidden;
    border: 1px solid rgba(var(--sentiment-rgb), .34);
    border-radius: 24px;
    outline: none;
    background:
        radial-gradient(circle at 92% 8%, rgba(var(--sentiment-rgb), .22), transparent 28%),
        radial-gradient(circle at 6% 94%, rgba(var(--sentiment-rgb), .12), transparent 32%),
        linear-gradient(145deg, rgba(var(--sentiment-rgb), .105), rgba(14,17,24,.985) 44%, rgba(8,11,17,.995));
    box-shadow:
        inset 0 1px 0 rgba(255,255,255,.075),
        0 18px 44px rgba(0,0,0,.28),
        0 0 0 1px rgba(255,255,255,.018);
    transform: translateZ(0);
    transform-style: preserve-3d;
    transition:
        transform .34s cubic-bezier(.2,.8,.2,1),
        border-color .28s ease,
        box-shadow .34s ease,
        background .34s ease;
    animation: recSentimentCardReveal .72s cubic-bezier(.2,.8,.2,1) both;
}
.rec-sentiment-strategy-card:nth-child(2) { animation-delay: .10s; }
.rec-sentiment-strategy-card:nth-child(3) { animation-delay: .20s; }
.rec-sentiment-strategy-card::before {
    content: "";
    position: absolute;
    z-index: 3;
    top: 0;
    left: 22px;
    right: 22px;
    height: 3px;
    border-radius: 0 0 999px 999px;
    background: linear-gradient(90deg, transparent, var(--sentiment-color), rgba(255,255,255,.92), var(--sentiment-color), transparent);
    background-size: 220% 100%;
    box-shadow: 0 0 18px rgba(var(--sentiment-rgb), .62);
    animation: recSentimentLineFlow 4.2s linear infinite;
}
.rec-sentiment-strategy-card::after {
    content: "";
    position: absolute;
    z-index: -1;
    width: 190px;
    height: 190px;
    right: -88px;
    bottom: -92px;
    border-radius: 50%;
    background: rgba(var(--sentiment-rgb), .12);
    filter: blur(4px);
    transition: transform .45s cubic-bezier(.2,.8,.2,1), opacity .35s ease;
}
.rec-sentiment-strategy-card:hover,
.rec-sentiment-strategy-card:focus-visible {
    z-index: 2;
    transform: translateY(-9px) rotateX(1.1deg) scale(1.012);
    border-color: rgba(var(--sentiment-rgb), .70);
    background:
        radial-gradient(circle at 92% 8%, rgba(var(--sentiment-rgb), .29), transparent 31%),
        radial-gradient(circle at 6% 94%, rgba(var(--sentiment-rgb), .17), transparent 35%),
        linear-gradient(145deg, rgba(var(--sentiment-rgb), .145), rgba(14,17,24,.99) 44%, rgba(8,11,17,.998));
    box-shadow:
        inset 0 1px 0 rgba(255,255,255,.12),
        0 28px 66px rgba(0,0,0,.40),
        0 0 34px rgba(var(--sentiment-rgb), .14);
}
.rec-sentiment-strategy-card:hover::after,
.rec-sentiment-strategy-card:focus-visible::after {
    transform: translate(-22px, -20px) scale(1.24);
    opacity: .92;
}
.rec-sentiment-strategy-inner {
    position: relative;
    z-index: 2;
    display: flex;
    flex: 1;
    flex-direction: column;
    width: 100%;
}
.rec-sentiment-strategy-head {
    display: flex;
    align-items: center;
    gap: 14px;
    margin-bottom: 20px;
}
.rec-sentiment-strategy-icon {
    position: relative;
    display: grid;
    flex: 0 0 52px;
    width: 52px;
    height: 52px;
    place-items: center;
    border: 1px solid rgba(var(--sentiment-rgb), .48);
    border-radius: 16px;
    color: #FFFFFF;
    background:
        radial-gradient(circle at 30% 24%, rgba(255,255,255,.30), transparent 24%),
        linear-gradient(145deg, rgba(var(--sentiment-rgb), .98), rgba(var(--sentiment-rgb), .46));
    box-shadow:
        0 12px 28px rgba(var(--sentiment-rgb), .20),
        inset 0 1px 0 rgba(255,255,255,.32);
    font-size: 23px;
    transition: transform .36s cubic-bezier(.2,.8,.2,1), box-shadow .30s ease;
    animation: recSentimentIconFloat 3.4s ease-in-out infinite;
}
.rec-sentiment-strategy-card:nth-child(2) .rec-sentiment-strategy-icon { animation-delay: .45s; }
.rec-sentiment-strategy-card:nth-child(3) .rec-sentiment-strategy-icon { animation-delay: .90s; }
.rec-sentiment-strategy-card:hover .rec-sentiment-strategy-icon,
.rec-sentiment-strategy-card:focus-visible .rec-sentiment-strategy-icon {
    transform: translateY(-3px) rotate(-5deg) scale(1.08);
    box-shadow:
        0 18px 36px rgba(var(--sentiment-rgb), .31),
        0 0 24px rgba(var(--sentiment-rgb), .24),
        inset 0 1px 0 rgba(255,255,255,.38);
}
.rec-sentiment-strategy-kicker {
    display: inline-flex;
    align-items: center;
    gap: 7px;
    margin: 0 0 5px;
    color: var(--sentiment-color);
    font-size: 0.75rem /* FIX: minimum 12px agar terbaca di tablet */;
    font-weight: 900;
    letter-spacing: .12em;
    line-height: 1.2;
    text-transform: uppercase;
}
.rec-sentiment-strategy-kicker::before {
    content: "";
    width: 6px;
    height: 6px;
    border-radius: 50%;
    background: var(--sentiment-color);
    box-shadow: 0 0 13px rgba(var(--sentiment-rgb), .90);
    animation: recSentimentDotPulse 1.8s ease-in-out infinite;
}
.rec-sentiment-strategy-state {
    color: rgba(255,255,255,.56);
    font-size: 0.75rem /* FIX: minimum 12px agar terbaca di tablet */;
    font-weight: 700;
    letter-spacing: .02em;
}
.rec-sentiment-strategy-card h3 {
    margin: 0 0 11px;
    color: #FFFFFF;
    font-family: 'Plus Jakarta Sans', sans-serif;
    font-size: clamp(18px, 1.45vw, 22px);
    font-weight: 850;
    letter-spacing: -.035em;
    line-height: 1.18;
}
.rec-sentiment-strategy-description {
    min-height: 52px;
    margin: 0 0 18px;
    color: rgba(255,255,255,.66);
    font-size: 0.75rem /* FIX: minimum 12px agar terbaca di tablet */;
    font-weight: 620;
    line-height: 1.65;
}
.rec-sentiment-strategy-card ul {
    display: grid;
    gap: 10px;
    margin: 0;
    padding: 0;
    color: rgba(255,255,255,.82);
    counter-reset: rec-strategy-point;
    list-style: none;
}
.rec-sentiment-strategy-card li {
    position: relative;
    display: grid;
    grid-template-columns: 28px minmax(0, 1fr);
    gap: 10px;
    align-items: start;
    min-height: 58px;
    padding: 11px 12px;
    border: 1px solid rgba(255,255,255,.065);
    border-radius: 14px;
    background: linear-gradient(110deg, rgba(255,255,255,.045), rgba(var(--sentiment-rgb), .026));
    font-size: 0.75rem /* FIX: minimum 12px agar terbaca di tablet */;
    font-weight: 650;
    line-height: 1.58;
    counter-increment: rec-strategy-point;
    transition:
        transform .26s cubic-bezier(.2,.8,.2,1),
        border-color .24s ease,
        background .24s ease,
        color .24s ease,
        box-shadow .24s ease;
}
.rec-sentiment-strategy-card li::before {
    content: counter(rec-strategy-point, decimal-leading-zero);
    display: grid;
    width: 27px;
    height: 27px;
    place-items: center;
    border: 1px solid rgba(var(--sentiment-rgb), .30);
    border-radius: 9px;
    color: var(--sentiment-color);
    background: rgba(var(--sentiment-rgb), .09);
    font-size: 0.75rem /* FIX: minimum 12px agar terbaca di tablet */;
    font-weight: 900;
    letter-spacing: .03em;
    transition: transform .24s ease, color .24s ease, background .24s ease;
}
.rec-sentiment-strategy-card li:hover {
    transform: translateX(7px);
    border-color: rgba(var(--sentiment-rgb), .34);
    color: #FFFFFF;
    background: linear-gradient(110deg, rgba(var(--sentiment-rgb), .13), rgba(255,255,255,.055));
    box-shadow: 0 10px 22px rgba(0,0,0,.20);
}
.rec-sentiment-strategy-card li:hover::before {
    transform: rotate(-7deg) scale(1.08);
    color: #0B0E13;
    background: var(--sentiment-color);
}
.rec-sentiment-strategy-footer {
    display: flex;
    align-items: center;
    gap: 9px;
    margin-top: auto;
    padding-top: 19px;
    color: rgba(255,255,255,.48);
    font-size: 0.75rem /* FIX: minimum 12px agar terbaca di tablet */;
    font-weight: 800;
    letter-spacing: .07em;
    text-transform: uppercase;
}
.rec-sentiment-strategy-footer::before {
    content: "";
    flex: 1;
    height: 1px;
    background: linear-gradient(90deg, rgba(var(--sentiment-rgb), .48), transparent);
}
.rec-sentiment-strategy-footer strong {
    color: var(--sentiment-color);
    font-size: 0.75rem /* FIX: minimum 12px agar terbaca di tablet */;
    font-weight: 900;
}
.rec-sentiment-strategy-arrow {
    display: grid;
    width: 26px;
    height: 26px;
    place-items: center;
    border: 1px solid rgba(var(--sentiment-rgb), .22);
    border-radius: 50%;
    color: var(--sentiment-color);
    background: rgba(var(--sentiment-rgb), .07);
    font-size: 12px;
    transition: transform .26s ease, background .26s ease, color .26s ease;
}
.rec-sentiment-strategy-card:hover .rec-sentiment-strategy-arrow,
.rec-sentiment-strategy-card:focus-visible .rec-sentiment-strategy-arrow {
    transform: translate(2px, -2px) rotate(12deg);
    color: #0B0E13;
    background: var(--sentiment-color);
}
@keyframes recSentimentCardReveal {
    from { opacity: 0; transform: translateY(20px) scale(.985); }
    to { opacity: 1; transform: translateY(0) scale(1); }
}
@keyframes recSentimentLineFlow {
    from { background-position: 0% 50%; }
    to { background-position: 220% 50%; }
}
@keyframes recSentimentIconFloat {
    0%, 100% { transform: translateY(0) rotate(0deg); }
    50% { transform: translateY(-4px) rotate(2deg); }
}
@keyframes recSentimentDotPulse {
    0%, 100% { opacity: .52; transform: scale(.82); }
    50% { opacity: 1; transform: scale(1.12); }
}

@keyframes recAiBorderFlow {
    0% { background-position: 0% 50%; }
    100% { background-position: 220% 50%; }
}
@keyframes recAiFloatOne {
    0%, 100% { transform: translate3d(0,0,0) scale(1); }
    50% { transform: translate3d(44px,28px,0) scale(1.14); }
}
@keyframes recAiFloatTwo {
    0%, 100% { transform: translate3d(0,0,0) scale(1); }
    50% { transform: translate3d(-36px,-22px,0) scale(1.10); }
}
@keyframes recAiLogoPulse {
    0%, 100% { transform: translateY(0) rotate(0deg); box-shadow: 0 15px 34px rgba(229,57,53,.22), inset 0 1px 0 rgba(255,255,255,.30); }
    50% { transform: translateY(-3px) rotate(3deg); box-shadow: 0 20px 42px rgba(139,92,246,.30), inset 0 1px 0 rgba(255,255,255,.34); }
}
@keyframes recAiStatusPulse {
    0%, 100% { opacity: .55; transform: scale(.82); }
    50% { opacity: 1; transform: scale(1.08); }
}
@keyframes recAiNoticeIn {
    from { opacity: 0; transform: translateY(-8px); }
    to { opacity: 1; transform: translateY(0); }
}
@keyframes recAiResultReveal {
    from { opacity: 0; transform: translateY(12px) scale(.99); }
    to { opacity: 1; transform: translateY(0) scale(1); }
}

@media (prefers-reduced-motion: reduce) {
    .rec-sentiment-strategy-card,
    .rec-sentiment-strategy-icon,
    .rec-sentiment-strategy-kicker::before,
    .rec-sentiment-strategy-card::before {
        animation: none !important;
    }
    .rec-sentiment-strategy-card,
    .rec-sentiment-strategy-card li,
    .rec-sentiment-strategy-icon,
    .rec-sentiment-strategy-arrow {
        transition-duration: .01ms !important;
    }
}

@media (max-width: 900px) {
    .rec-ai-heading { flex-direction: column; }
    .rec-gemini-badge { align-self: flex-start; }
    .rec-sentiment-strategy-grid { grid-template-columns: 1fr; }
    .rec-sentiment-strategy-card { min-height: 0; }
    .rec-sentiment-strategy-description { min-height: 0; }
}
@media (max-width: 620px) {
    .rec-ai-shell { min-height: 0; padding: 20px 17px; border-radius: 20px; }
    .rec-ai-brand { gap: 12px; }
    .rec-ai-logo { width: 46px; height: 46px; flex-basis: 46px; border-radius: 15px; }
    .rec-ai-heading h2 { font-size: 22px; }
    .rec-ai-result-header { align-items: flex-start; flex-direction: column; }
    .rec-ai-result-body { padding-left: 18px; padding-right: 18px; }
    .rec-ai-result-meta { margin-left: 18px; margin-right: 18px; }
}
@media (prefers-reduced-motion: reduce) {
    .rec-ai-shell::after,
    .rec-ai-orb,
    .rec-ai-logo,
    .rec-gemini-badge::before,
    .rec-ai-result,
    .rec-ai-refresh-notice,
    .rec-ai-offline-note,
    .rec-ai-fallback-note {
        animation: none !important;
    }
    .rec-ai-shell,
    .rec-ai-result,
    .rec-ai-feature-chip,
    .rec-ai-idea-row,
    .rec-ai-meta-chip,
    div[data-testid="stButton"] button,
    div[data-testid="stExpander"] {
        transition: none !important;
    }
}
</style>
"""

PLATFORM_META: dict[str, dict[str, str]] = {
    "twitter": {
        "label": "Twitter/X",
        "warna": "#1DA1F2",
        "ikon": "𝕏",
    },
    "instagram": {
        "label": "Instagram",
        "warna": "#833AB4",
        "ikon": "◎",
    },
    "tiktok": {
        "label": "TikTok",
        "warna": "#111111",
        "ikon": "♪",
    },
}

SERVICE_ALIASES: dict[str, tuple[str, ...]] = {
    "IndiHome": ("indihome", "myindihome", "indihomecare"),
    "IndiBiz": ("indibiz", "sobiz"),
    "Telkomsel": ("telkomsel", "tsel", "mytelkomsel"),
}

BRAND_KEYWORDS = (
    "indihome",
    "myindihome",
    "indihomecare",
    "indibiz",
    "telkomsel",
    "mytelkomsel",
    "telkom",
    "simpati",
    "byu",
    "by.u",
    "orbit",
    "duniagames",
    "smartfren",
    "indosat",
    "myxl",
    "xlaxiata",
    "biznet",
    "firstmedia",
    "myrepublic",
    "iconnet",
    "starlink",
)

NON_INFLUENCER_ACCOUNTS = {
    "grok",
    "chatgpt",
    "openai",
}

SENTIMENT_LABELS = {
    "positive": "Positif",
    "neutral": "Netral",
    "negative": "Negatif",
}

SENTIMENT_COLORS = {
    "positive": "#4CAF50",
    "neutral": "#9E9E9E",
    "negative": "#E53935",
}

# Warna badge topik dibuat berbeda agar pengguna mudah membedakan isu.
# Nilai dibuat manual supaya tetap konsisten dengan tema gelap Telkom Group.
TOPIC_BADGE_COLORS: dict[str, dict[str, str]] = {
    "gangguan_jaringan": {
        "warna": "#E53935",
        "border": "rgba(229, 57, 53, .58)",
        "background": "rgba(229, 57, 53, .13)",
    },
    "apresiasi_layanan": {
        "warna": "#4CAF50",
        "border": "rgba(76, 175, 80, .58)",
        "background": "rgba(76, 175, 80, .13)",
    },
    "perbandingan_provider": {
        "warna": "#7C4DFF",
        "border": "rgba(124, 77, 255, .58)",
        "background": "rgba(124, 77, 255, .13)",
    },
    "harga_kualitas": {
        "warna": "#FF9800",
        "border": "rgba(255, 152, 0, .60)",
        "background": "rgba(255, 152, 0, .14)",
    },
    "bantuan_admin": {
        "warna": "#00BCD4",
        "border": "rgba(0, 188, 212, .58)",
        "background": "rgba(0, 188, 212, .13)",
    },
    "default": {
        "warna": "#CFCFCF",
        "border": "rgba(207, 207, 207, .26)",
        "background": "rgba(255, 255, 255, .07)",
    },
}

# Lima topik kanonik yang digunakan pada dokumen penelitian.
TOPIC_CONFIG: list[dict[str, Any]] = [
    {
        "key": "gangguan_jaringan",
        "nama": "Gangguan Sinyal dan Jaringan Internet",
        "singkat": "Gangguan Jaringan",
        "sentimen_default": "negative",
        "keywords": (
            "gangguan", "jaringan", "sinyal", "internet mati", "wifi mati",
            "down", "putus", "lemot", "lambat", "ngelag", "lag", "buffering",
            "los merah", "tidak stabil", "no signal", "blank spot", "outage",
        ),
    },
    {
        "key": "apresiasi_layanan",
        "nama": "Apresiasi terhadap Layanan dan Brand",
        "singkat": "Apresiasi Layanan",
        "sentimen_default": "positive",
        "keywords": (
            "puas", "bagus", "mantap", "keren", "terbaik", "terima kasih",
            "makasih", "lancar", "cepat", "stabil", "ramah", "profesional",
            "recommended", "rekomendasi", "membantu", "solutif", "worth it",
        ),
    },
    {
        "key": "perbandingan_provider",
        "nama": "Perbandingan dengan Provider Lain/Starlink",
        "singkat": "Provider Lain",
        "sentimen_default": "negative",
        "keywords": (
            "starlink", "provider lain", "kompetitor", "biznet", "first media",
            "myrepublic", "iconnet", "indosat", "xl", "axis", "smartfren",
            "tri", "by.u", "versus", "dibanding", "pindah provider",
        ),
    },
    {
        "key": "harga_kualitas",
        "nama": "Harga Kuota Mahal dan Ketidakseimbangan Kualitas",
        "singkat": "Harga & Kualitas",
        "sentimen_default": "negative",
        "keywords": (
            "harga", "mahal", "kuota", "tagihan", "pulsa", "tarif", "biaya",
            "paket", "voucher", "billing", "invoice", "kuota habis", "tagihan naik",
            "tidak sebanding", "kemahalan", "boros", "kualitas",
        ),
    },
    {
        "key": "bantuan_admin",
        "nama": "Permintaan Bantuan dan Interaksi dengan Admin",
        "singkat": "Bantuan Admin",
        "sentimen_default": "neutral",
        "keywords": (
            "bantuan", "bantu", "tolong", "admin", "mimin", "cs",
            "customer service", "respon", "respons", "dm", "inbox", "lapor",
            "keluhan", "komplain", "pengaduan", "tiket", "ticket", "hubungi",
        ),
    },
]

TOPIC_BY_KEY = {item["key"]: item for item in TOPIC_CONFIG}

# Baseline penelitian yang wajib tetap tersedia ketika data aktual gagal dibaca.
SERVICE_TOPIC_FALLBACK: dict[str, dict[str, int]] = {
    "IndiHome": {
        "gangguan_jaringan": 10,
        "apresiasi_layanan": 8,
        "perbandingan_provider": 4,
        "harga_kualitas": 4,
        "bantuan_admin": 3,
    },
    "IndiBiz": {
        "gangguan_jaringan": 9,
        "apresiasi_layanan": 8,
        "perbandingan_provider": 3,
        "harga_kualitas": 6,
        "bantuan_admin": 4,
    },
    "Telkomsel": {
        "gangguan_jaringan": 12,
        "apresiasi_layanan": 7,
        "perbandingan_provider": 5,
        "harga_kualitas": 8,
        "bantuan_admin": 5,
    },
}

# Influencer baseline dari hasil penelitian. Untuk IndiHome, daftar ini selalu
# dipertahankan agar halaman konsisten dengan hasil skripsi. Nilai aktual dari
# data SNA akan memperbarui followers/centrality ketika username cocok.
BASELINE_INFLUENCERS: list[dict[str, Any]] = [
    {
        "username": "dewa_brahma",
        "platform": "twitter",
        "followers": 76,
        "degree_centrality": 0.138,
    },
    {
        "username": "bellaablee",
        "platform": "twitter",
        "followers": 174,
        "degree_centrality": 0.103,
    },
    {
        "username": "cobeyisyolkek",
        "platform": "twitter",
        "followers": 219,
        "degree_centrality": 0.103,
    },
    {
        "username": "dkdiki_",
        "platform": "instagram",
        "followers": 1588,
        "degree_centrality": 0.000,
    },
    {
        "username": "akri64",
        "platform": "instagram",
        "followers": 1110,
        "degree_centrality": 0.000,
    },
    {
        "username": "faishalfrss",
        "platform": "instagram",
        "followers": 1060,
        "degree_centrality": 0.000,
    },
    {
        "username": "sutardi.wasimin",
        "platform": "tiktok",
        "followers": 1612,
        "degree_centrality": 0.000,
    },
    {
        "username": "akakpro46",
        "platform": "tiktok",
        "followers": 620,
        "degree_centrality": 0.000,
    },
    {
        "username": "riswanda822",
        "platform": "tiktok",
        "followers": 559,
        "degree_centrality": 0.000,
    },
]

# Kesesuaian dasar platform terhadap lima topik. Nilai akhir juga memperhitungkan
# urutan influencer dan layanan sehingga matriks stabil, bukan angka acak.
PLATFORM_TOPIC_BASE = {
    "twitter": [10, 7, 10, 9, 10],
    "instagram": [7, 10, 7, 8, 7],
    "tiktok": [9, 9, 8, 9, 8],
}


# -----------------------------------------------------------------------------
# CSS HALAMAN
# -----------------------------------------------------------------------------

RECOMMENDATION_CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&family=Plus+Jakarta+Sans:wght@500;600;700;800&display=swap');

:root {
    --rec-bg-main: #0D0D0D;
    --rec-bg-card: #1A1A1A;
    --rec-bg-soft: #151515;
    --rec-bg-input: #242424;
    --rec-primary: #E53935;
    --rec-primary-hover: #FF5252;
    --rec-primary-dark: #B71C1C;
    --rec-border: #2A2A2A;
    --rec-text: #FFFFFF;
    --rec-text-secondary: #AAAAAA;
    --rec-text-muted: #666666;
}

.rec-page,
.rec-page * {
    box-sizing: border-box;
    font-family: 'Inter', sans-serif;
}

.rec-hero {
    position: relative;
    overflow: hidden;
    padding: 28px 30px;
    margin: 2px 0 20px;
    border: 1px solid var(--rec-border);
    border-radius: 18px;
    background:
        radial-gradient(circle at 88% 15%, rgba(229,57,53,.22), transparent 31%),
        linear-gradient(135deg, rgba(26,26,26,.98), rgba(13,13,13,.98));
    box-shadow: 0 18px 55px rgba(0,0,0,.28);
}

.rec-hero::before {
    content: '';
    position: absolute;
    top: 0;
    left: 0;
    right: 0;
    height: 2px;
    background: linear-gradient(90deg, transparent, #E53935, transparent);
}

.rec-eyebrow {
    display: inline-flex;
    align-items: center;
    gap: 8px;
    padding: 6px 10px;
    margin-bottom: 12px;
    border: 1px solid rgba(229,57,53,.35);
    border-radius: 999px;
    color: #FF8A87;
    background: rgba(229,57,53,.09);
    font-size: 12px;
    font-weight: 700;
    letter-spacing: .08em;
    text-transform: uppercase;
}

.rec-title {
    margin: 0;
    color: var(--rec-text);
    font-family: 'Plus Jakarta Sans', sans-serif;
    font-size: clamp(28px, 4vw, 42px);
    font-weight: 800;
    letter-spacing: -.04em;
    line-height: 1.05;
}

.rec-subtitle {
    max-width: 820px;
    margin: 11px 0 0;
    color: var(--rec-text-secondary);
    font-size: 15px;
    line-height: 1.65;
}

.rec-context-card {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 18px;
    min-height: 84px;
    padding: 18px 20px;
    margin: 8px 0 22px;
    border: 1px solid var(--rec-border);
    border-left: 3px solid var(--rec-primary);
    border-radius: 12px;
    background: var(--rec-bg-card);
}

.rec-issue-label {
    margin-bottom: 5px;
    color: var(--rec-text-muted);
    font-size: 0.75rem /* FIX: minimum 12px agar terbaca di tablet */;
    font-weight: 700;
    letter-spacing: .08em;
    text-transform: uppercase;
}

.rec-issue-value {
    color: var(--rec-text);
    font-size: 18px;
    font-weight: 700;
}

.rec-status-row {
    display: flex;
    flex-wrap: wrap;
    justify-content: flex-end;
    gap: 8px;
}

.rec-status {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    padding: 6px 10px;
    border: 1px solid var(--rec-border);
    border-radius: 999px;
    color: var(--rec-text-secondary);
    background: #111111;
    font-size: 0.75rem /* FIX: minimum 12px agar terbaca di tablet */;
    font-weight: 700;
}

.rec-status.actual {
    border-color: rgba(76,175,80,.42);
    color: #81C784;
    background: rgba(76,175,80,.08);
}

.rec-status.fallback {
    border-color: rgba(255,152,0,.42);
    color: #FFB74D;
    background: rgba(255,152,0,.08);
}

.rec-status.model {
    border-color: rgba(229,57,53,.35);
    color: #FF8A87;
    background: rgba(229,57,53,.08);
}

.rec-section-head {
    display: flex;
    align-items: flex-end;
    justify-content: space-between;
    gap: 18px;
    margin: 34px 0 16px;
}

.rec-section-kicker {
    margin-bottom: 4px;
    color: var(--rec-primary);
    font-size: 0.75rem /* FIX: minimum 12px agar terbaca di tablet */;
    font-weight: 800;
    letter-spacing: .11em;
    text-transform: uppercase;
}

.rec-section-title {
    margin: 0;
    color: var(--rec-text);
    font-family: 'Plus Jakarta Sans', sans-serif;
    font-size: 24px;
    font-weight: 750;
    letter-spacing: -.025em;
}

.rec-section-desc {
    max-width: 620px;
    margin: 5px 0 0;
    color: var(--rec-text-secondary);
    font-size: 13px;
    line-height: 1.55;
}


/* -------------------------------------------------------------------------- */
/* RADIO FILTER TIPE AKUN - KHUSUS SECTION INFLUENCER                        */
/* Streamlit 1.59 memakai data-testid stRadioOption + atribut data-selected.  */
/* Styling hanya mengubah tampilan radio, bukan logika filter.                */
/* -------------------------------------------------------------------------- */
div[data-testid="stRadio"] {
    margin-top: 4px !important;
    margin-bottom: 16px !important;
}

div[data-testid="stRadio"] > label {
    margin-bottom: 10px !important;
}

div[data-testid="stRadio"] > label p {
    color: var(--rec-text) !important;
    font-size: 12px !important;
    font-weight: 850 !important;
    letter-spacing: .06em !important;
    text-transform: uppercase !important;
}

div[data-testid="stRadioGroup"] {
    display: flex !important;
    flex-wrap: wrap !important;
    align-items: stretch !important;
    gap: 10px !important;
    min-height: 0 !important;
}

[data-testid="stRadioOption"] {
    --radio-accent: #E53935;
    --radio-rgb: 229,57,53;
    min-width: 148px !important;
    margin: 0 !important;
    padding: 11px 14px !important;
    border: 1px solid rgba(255,255,255,.10) !important;
    border-radius: 14px !important;
    background: linear-gradient(145deg, rgba(255,255,255,.055), rgba(255,255,255,.025)) !important;
    box-shadow: inset 0 1px 0 rgba(255,255,255,.05) !important;
    transition: transform .16s ease, border-color .16s ease, background .16s ease, box-shadow .16s ease !important;
}

[data-testid="stRadioOption"]:nth-child(1) {
    --radio-accent: #E53935;
    --radio-rgb: 229,57,53;
}

[data-testid="stRadioOption"]:nth-child(2) {
    --radio-accent: #43A047;
    --radio-rgb: 67,160,71;
}

[data-testid="stRadioOption"]:nth-child(3) {
    --radio-accent: #1DA1F2;
    --radio-rgb: 29,161,242;
}

[data-testid="stRadioOption"]:hover {
    transform: translateY(-1px) !important;
    border-color: rgba(var(--radio-rgb), .48) !important;
    background: linear-gradient(145deg, rgba(var(--radio-rgb), .10), rgba(255,255,255,.035)) !important;
    box-shadow: 0 10px 24px rgba(0,0,0,.16), inset 0 1px 0 rgba(255,255,255,.06) !important;
}

[data-testid="stRadioOption"][data-focus-visible] {
    outline: 2px solid rgba(var(--radio-rgb), .52) !important;
    outline-offset: 2px !important;
}

[data-testid="stRadioOption"] > div {
    width: 100% !important;
}

[data-testid="stRadioOption"] > div > div:first-child {
    display: flex !important;
    align-items: center !important;
    gap: 10px !important;
}

/* Lingkaran radio bawaan dibuat lebih presisi dan berwarna. */
[data-testid="stRadioOption"] > div > div:first-child > div:first-child {
    width: 22px !important;
    height: 22px !important;
    min-width: 22px !important;
    min-height: 22px !important;
    border: 2px solid var(--radio-accent) !important;
    border-radius: 50% !important;
    background: transparent !important;
    box-shadow: 0 0 0 4px rgba(var(--radio-rgb), .10) !important;
    transition: background .16s ease, border-color .16s ease, box-shadow .16s ease !important;
}

[data-testid="stRadioOption"] > div > div:first-child > div:first-child > div {
    width: 8px !important;
    height: 8px !important;
    border-radius: 50% !important;
    background: transparent !important;
    transition: background .16s ease, transform .16s ease !important;
}

[data-testid="stRadioOption"] [data-testid="stMarkdownContainer"] p {
    margin: 0 !important;
    color: rgba(255,255,255,.82) !important;
    font-size: 13px !important;
    font-weight: 760 !important;
    line-height: 1.2 !important;
}

/* State aktif mengikuti atribut resmi React Aria yang dipakai Streamlit. */
[data-testid="stRadioOption"][data-selected] {
    border-color: rgba(var(--radio-rgb), .62) !important;
    background: linear-gradient(135deg, rgba(var(--radio-rgb), .19), rgba(var(--radio-rgb), .07)) !important;
    box-shadow: 0 10px 26px rgba(var(--radio-rgb), .16), inset 0 1px 0 rgba(255,255,255,.08) !important;
}

[data-testid="stRadioOption"][data-selected] > div > div:first-child > div:first-child {
    border-color: var(--radio-accent) !important;
    background: var(--radio-accent) !important;
    box-shadow: 0 0 0 5px rgba(var(--radio-rgb), .14), 0 5px 13px rgba(var(--radio-rgb), .24) !important;
}

[data-testid="stRadioOption"][data-selected] > div > div:first-child > div:first-child > div {
    background: #FFFFFF !important;
    transform: scale(1) !important;
}

[data-testid="stRadioOption"][data-selected] [data-testid="stMarkdownContainer"] p {
    color: #FFFFFF !important;
    font-weight: 850 !important;
}

@media (max-width: 640px) {
    [data-testid="stRadioOption"] {
        flex: 1 1 calc(50% - 5px) !important;
        min-width: 132px !important;
    }
}


.rec-influencer-card {
    position: relative;
    display: flex;
    flex-direction: column;
    height: 500px;
    min-height: 500px;
    padding: 20px;
    margin-bottom: 8px;
    overflow: hidden;
    border: 1px solid var(--rec-border);
    border-radius: 14px;
    background: linear-gradient(160deg, rgba(28,28,28,.98), rgba(18,18,18,.98));
    transition: border-color .22s ease, transform .22s ease, box-shadow .22s ease;
}

.rec-influencer-card.rec-placeholder-card {
    align-items: center;
    justify-content: center;
    border-style: dashed;
    text-align: center;
    background: linear-gradient(160deg, rgba(24,24,24,.72), rgba(15,15,15,.72));
}

.rec-influencer-card.rec-placeholder-card:hover {
    transform: none;
    border-color: #3A3A3A;
    box-shadow: none;
}

.rec-placeholder-icon {
    display: grid;
    place-items: center;
    width: 56px;
    height: 56px;
    margin-bottom: 14px;
    border: 1px solid #333333;
    border-radius: 50%;
    color: #777777;
    background: #151515;
    font-size: 22px;
    font-weight: 800;
}

.rec-placeholder-title {
    margin: 0 0 8px;
    color: #D0D0D0;
    font-family: 'Plus Jakarta Sans', sans-serif;
    font-size: 16px;
    font-weight: 700;
}

.rec-placeholder-text {
    max-width: 245px;
    margin: 0;
    color: #777777;
    font-size: 0.75rem /* FIX: minimum 12px agar terbaca di tablet */;
    line-height: 1.55;
}

.rec-influencer-card:hover {
    transform: translateY(-3px);
    border-color: var(--rec-primary);
    box-shadow: 0 14px 38px rgba(0,0,0,.35), 0 0 22px rgba(229,57,53,.08);
}

.rec-influencer-card::after {
    content: '';
    position: absolute;
    top: -45px;
    right: -45px;
    width: 105px;
    height: 105px;
    border-radius: 50%;
    background: var(--platform-color, #E53935);
    filter: blur(32px);
    opacity: .13;
}

.rec-card-top {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 12px;
    margin-bottom: 17px;
}

.rec-avatar {
    display: grid;
    place-items: center;
    width: 50px;
    height: 50px;
    border: 1px solid rgba(255,255,255,.15);
    border-radius: 50%;
    color: #FFFFFF;
    background: var(--platform-color, #E53935);
    box-shadow: 0 8px 20px rgba(0,0,0,.25);
    font-family: 'Plus Jakarta Sans', sans-serif;
    font-size: 20px;
    font-weight: 800;
    text-transform: uppercase;
}

.rec-platform-badge,
.rec-mini-badge {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    padding: 5px 9px;
    border: 1px solid color-mix(in srgb, var(--platform-color, #E53935) 48%, transparent);
    border-radius: 999px;
    color: #FFFFFF;
    background: color-mix(in srgb, var(--platform-color, #E53935) 13%, transparent);
    font-size: 0.75rem /* FIX: minimum 12px agar terbaca di tablet */;
    font-weight: 700;
}

.rec-username {
    display: flex;
    align-items: flex-start;
    min-height: 48px;
    margin: 0 0 9px;
    color: #FFFFFF;
    font-family: 'Plus Jakarta Sans', sans-serif;
    font-size: 18px;
    font-weight: 700;
    line-height: 1.25;
    overflow-wrap: anywhere;
}

.rec-metric-row {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 9px;
    margin-bottom: 16px;
}

.rec-mini-metric {
    padding: 10px;
    border: 1px solid #292929;
    border-radius: 9px;
    background: #141414;
}

.rec-mini-label {
    display: block;
    margin-bottom: 3px;
    color: var(--rec-text-muted);
    font-size: 0.75rem /* FIX: minimum 12px agar terbaca di tablet */;
    text-transform: uppercase;
}

.rec-mini-value {
    color: #FFFFFF;
    font-size: 13px;
    font-weight: 700;
}

.rec-tags {
    display: flex;
    align-content: flex-start;
    flex-wrap: wrap;
    column-gap: 7px;
    row-gap: 8px;
    min-height: 52px;
    margin-bottom: 17px;
}

.rec-tag {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    padding: 5px 8px;
    border: 1px solid var(--tag-border, #303030);
    border-radius: 999px;
    color: var(--tag-color, #CFCFCF);
    background: var(--tag-bg, #202020);
    box-shadow: inset 0 0 0 1px rgba(255,255,255,.025);
    font-size: 0.75rem /* FIX: minimum 12px agar terbaca di tablet */;
    font-weight: 700;
}

.rec-tag::before {
    content: '';
    width: 6px;
    height: 6px;
    border-radius: 50%;
    background: var(--tag-color, #CFCFCF);
    box-shadow: 0 0 10px var(--tag-color, #CFCFCF);
}

.rec-content-preview {
    display: flex;
    flex-direction: column;
    height: 176px;
    min-height: 176px;
    margin-top: 0;
    padding: 14px 13px 13px 14px;
    overflow: hidden;
    border: 1px solid #2B2B2B;
    border-radius: 10px;
    background: #141414;
}

.rec-content-preview-head {
    display: flex;
    align-items: flex-start;
    justify-content: space-between;
    flex-wrap: wrap;
    column-gap: 10px;
    row-gap: 7px;
    margin-bottom: 10px;
}

.rec-content-preview-title {
    color: #F3F3F3;
    font-size: 0.75rem /* FIX: minimum 12px agar terbaca di tablet */;
    font-weight: 800;
    line-height: 1.35;
    letter-spacing: .055em;
    text-transform: uppercase;
}

.rec-content-source-badge {
    flex: 0 0 auto;
    margin-left: auto;
    padding: 4px 8px;
    border: 1px solid rgba(76,175,80,.35);
    border-radius: 999px;
    color: #81C784;
    background: rgba(76,175,80,.08);
    font-size: 0.75rem /* FIX: minimum 12px agar terbaca di tablet */;
    font-weight: 800;
    letter-spacing: .04em;
    text-transform: uppercase;
}

.rec-content-source-badge.network {
    border-color: rgba(255,152,0,.35);
    color: #FFB74D;
    background: rgba(255,152,0,.08);
}

.rec-content-preview-head {
    flex: 0 0 auto;
}

/*
 * Area gulir dibuat pada pembungkus tersendiri agar browser tidak lagi
 * bergantung pada perhitungan flex milik elemen <ul>. Tinggi viewport dibuat
 * tetap sehingga teks panjang dan bukti ketiga dapat digulir dengan roda mouse,
 * touchpad, maupun tombol panah ketika area memperoleh fokus.
 */
.rec-content-scroll {
    position: relative;
    margin-top: 0;
    margin-bottom: 0;
    flex: 1 1 auto;
    width: 100%;
    height: auto;
    min-height: 0;
    max-height: none;
    padding: 2px 5px 4px 0;
    overflow-x: hidden !important;
    overflow-y: scroll !important;
    overscroll-behavior: contain;
    scrollbar-gutter: stable both-edges;
    scrollbar-width: thin;
    scrollbar-color: #E53935 #202020;
    touch-action: pan-y;
    outline: none;
}

.rec-content-scroll:focus-visible {
    border-radius: 7px;
    box-shadow: 0 0 0 2px rgba(229,57,53,.28);
}

.rec-content-scroll::-webkit-scrollbar {
    width: 8px;
}

.rec-content-scroll::-webkit-scrollbar-track {
    border: 1px solid #2D2D2D;
    border-radius: 999px;
    background: #202020;
}

.rec-content-scroll::-webkit-scrollbar-thumb {
    min-height: 28px;
    border: 2px solid #202020;
    border-radius: 999px;
    background: #E53935;
}

.rec-content-scroll::-webkit-scrollbar-thumb:hover {
    background: #FF5252;
}

.rec-content-list {
    display: grid;
    gap: 11px;
    min-width: 0;
    margin: 0;
    padding: 0 2px 6px 0;
    list-style: none;
}

.rec-content-list li {
    display: grid;
    grid-template-columns: 20px minmax(0, 1fr);
    align-items: start;
    gap: 9px;
    color: #C8C8C8;
    font-size: 0.75rem /* FIX: minimum 12px agar terbaca di tablet */;
    line-height: 1.55;
}

.rec-content-list li > span:last-child {
    min-width: 0;
    overflow-wrap: anywhere;
    word-break: break-word;
    white-space: normal;
}

.rec-content-preview-meta {
    display: block;
    margin-top: 5px;
    color: #777777;
    font-size: 0.75rem /* FIX: minimum 12px agar terbaca di tablet */;
    line-height: 1.3;
}

.rec-content-index {
    display: grid;
    place-items: center;
    width: 20px;
    height: 20px;
    border: 1px solid rgba(229,57,53,.38);
    border-radius: 5px;
    color: #FF7773;
    background: rgba(229,57,53,.08);
    font-size: 0.75rem /* FIX: minimum 12px agar terbaca di tablet */;
    font-weight: 800;
}

.rec-detail-grid {
    display: grid;
    grid-template-columns: minmax(0, 1.35fr) minmax(320px, .85fr);
    align-items: stretch;
    gap: 16px;
    margin-top: 14px;
}

.rec-detail-block {
    min-width: 0;
    height: 100%;
    padding: 14px;
    border: 1px solid #2D2D2D;
    border-radius: 10px;
    background: #141414;
    box-sizing: border-box;
}

.rec-detail-block-title {
    margin-bottom: 10px;
    color: #FFFFFF;
    font-size: 12px;
    font-weight: 800;
    letter-spacing: .045em;
    text-transform: uppercase;
}

.rec-detail-content-list {
    display: grid;
    gap: 9px;
    max-height: 300px;
    padding-right: 4px;
    overflow-x: hidden;
    overflow-y: auto;
    overscroll-behavior: contain;
}

.rec-detail-content-list::-webkit-scrollbar {
    width: 6px;
}

.rec-detail-content-list::-webkit-scrollbar-track {
    border-radius: 999px;
    background: #1B1B1B;
}

.rec-detail-content-list::-webkit-scrollbar-thumb {
    border-radius: 999px;
    background: #4A4A4A;
}

.rec-detail-content-list::-webkit-scrollbar-thumb:hover {
    background: #E53935;
}

.rec-detail-content-item {
    display: grid;
    grid-template-columns: 28px minmax(0, 1fr);
    gap: 10px;
    padding: 10px;
    border: 1px solid #292929;
    border-radius: 9px;
    background: #181818;
}

.rec-detail-content-number {
    display: grid;
    place-items: center;
    width: 28px;
    height: 28px;
    border-radius: 8px;
    color: #FFFFFF;
    background: rgba(229,57,53,.16);
    font-size: 0.75rem /* FIX: minimum 12px agar terbaca di tablet */;
    font-weight: 800;
}

.rec-detail-content-text {
    margin: 0;
    color: #E1E1E1;
    font-size: 0.75rem /* FIX: minimum 12px agar terbaca di tablet */;
    line-height: 1.5;
}

.rec-detail-content-meta {
    display: flex;
    flex-wrap: wrap;
    gap: 6px;
    margin-top: 6px;
    color: #888888;
    font-size: 0.75rem /* FIX: minimum 12px agar terbaca di tablet */;
}

.rec-detail-source-link {
    display: inline-flex;
    align-items: center;
    margin-top: 7px;
    padding: 5px 8px;
    border: 1px solid rgba(229,57,53,.45);
    border-radius: 7px;
    color: #FF7773 !important;
    background: rgba(229,57,53,.08);
    font-size: 0.75rem /* FIX: minimum 12px agar terbaca di tablet */;
    font-weight: 700;
    text-decoration: none !important;
}

.rec-detail-source-link:hover {
    border-color: #FF5252;
    color: #FFFFFF !important;
    background: rgba(229,57,53,.16);
}

.rec-selection-basis {
    display: inline-flex;
    margin-top: 8px;
    padding: 4px 7px;
    border: 1px solid rgba(76,175,80,.28);
    border-radius: 999px;
    color: #81C784;
    background: rgba(76,175,80,.07);
    font-size: 0.75rem /* FIX: minimum 12px agar terbaca di tablet */;
    font-weight: 700;
}

.rec-detail-recommendation {
    margin: 0;
    color: #D2D2D2;
    font-size: 0.75rem /* FIX: minimum 12px agar terbaca di tablet */;
    line-height: 1.62;
}

.rec-detail-note {
    margin-top: 10px;
    padding: 9px 10px;
    border-left: 2px solid #FF9800;
    border-radius: 6px;
    color: #C7C7C7;
    background: rgba(255,152,0,.07);
    font-size: 0.75rem /* FIX: minimum 12px agar terbaca di tablet */;
    line-height: 1.5;
}

@media (max-width: 1100px) {
    .rec-influencer-card {
        height: 520px;
        min-height: 520px;
    }
}


/* Kurangi jarak bawaan Streamlit setelah kotak kode agar panel influencer tidak turun terlalu jauh. */
div[data-testid="stElementContainer"]:has(div[data-testid="stCode"]) {
    margin-bottom: 0 !important;
}

@media (max-width: 980px) {
    .rec-detail-grid {
        grid-template-columns: 1fr;
    }
}

@media (max-width: 760px) {
    .rec-influencer-card {
        height: auto;
        min-height: 0;
    }

    .rec-detail-grid {
        grid-template-columns: 1fr;
    }
}

.rec-detail-panel {
    width: 100%;
    max-width: none;
    padding: 20px;
    margin: 15px 0 22px;
    border: 1px solid rgba(229,57,53,.35);
    border-radius: 12px;
    background: linear-gradient(135deg, rgba(229,57,53,.08), rgba(26,26,26,.97));
    box-sizing: border-box;
}

.rec-detail-panel h4 {
    margin: 0 0 8px;
    color: #FFFFFF;
    font-family: 'Plus Jakarta Sans', sans-serif;
}

.rec-detail-panel p {
    margin: 0;
    color: #C3C3C3;
    line-height: 1.65;
}


/* ================================================================
   DETAIL REKOMENDASI INTERAKTIF
   Memperkuat hierarki visual tanpa mengubah logika data dan toggle.
   ================================================================ */
@keyframes recDetailReveal {
    0% {
        opacity: 0;
        transform: translateY(-14px) scale(.985);
        filter: blur(3px);
    }
    100% {
        opacity: 1;
        transform: translateY(0) scale(1);
        filter: blur(0);
    }
}

@keyframes recDetailPulse {
    0%, 100% {
        box-shadow: 0 0 0 0 color-mix(in srgb, var(--detail-accent, #E53935) 45%, transparent);
    }
    50% {
        box-shadow: 0 0 0 7px transparent;
    }
}

@keyframes recDetailFloat {
    0%, 100% { transform: translateY(0) rotate(0deg); }
    50% { transform: translateY(-4px) rotate(2deg); }
}

@keyframes recDetailSweep {
    0% { transform: translateX(-130%); }
    55%, 100% { transform: translateX(230%); }
}

.rec-detail-panel {
    --detail-accent: #E53935;
    position: relative;
    isolation: isolate;
    width: 100%;
    max-width: none;
    padding: 26px;
    margin: 18px 0 26px;
    overflow: hidden;
    border: 1px solid color-mix(in srgb, var(--detail-accent) 55%, #303030);
    border-radius: 20px;
    background:
        radial-gradient(circle at 7% 0%, color-mix(in srgb, var(--detail-accent) 17%, transparent), transparent 28%),
        radial-gradient(circle at 95% 100%, color-mix(in srgb, var(--detail-accent) 10%, transparent), transparent 31%),
        linear-gradient(145deg, rgba(24,20,23,.99), rgba(11,14,20,.99));
    box-shadow:
        0 24px 70px rgba(0,0,0,.34),
        inset 0 1px 0 rgba(255,255,255,.045);
    box-sizing: border-box;
    animation: recDetailReveal .48s cubic-bezier(.2,.8,.2,1) both;
}

.rec-detail-panel::before {
    content: '';
    position: absolute;
    z-index: -1;
    inset: 0 auto auto 0;
    width: 100%;
    height: 3px;
    background: linear-gradient(90deg, transparent, var(--detail-accent), #FFFFFF, var(--detail-accent), transparent);
    background-size: 42% 100%;
    background-repeat: no-repeat;
    filter: drop-shadow(0 0 8px var(--detail-accent));
    animation: recDetailSweep 4.8s ease-in-out infinite;
}

.rec-detail-panel::after {
    content: '';
    position: absolute;
    z-index: -1;
    top: -135px;
    right: -115px;
    width: 300px;
    height: 300px;
    border: 1px solid color-mix(in srgb, var(--detail-accent) 18%, transparent);
    border-radius: 50%;
    background: radial-gradient(circle, color-mix(in srgb, var(--detail-accent) 13%, transparent), transparent 66%);
    pointer-events: none;
}

.rec-detail-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 18px;
    margin-bottom: 18px;
}

.rec-detail-identity {
    display: flex;
    align-items: center;
    min-width: 0;
    gap: 14px;
}

.rec-detail-platform-icon {
    display: grid;
    place-items: center;
    width: 54px;
    height: 54px;
    flex: 0 0 auto;
    border: 1px solid color-mix(in srgb, var(--detail-accent) 60%, #FFFFFF20);
    border-radius: 17px;
    color: #FFFFFF;
    background:
        radial-gradient(circle at 32% 26%, rgba(255,255,255,.30), transparent 28%),
        color-mix(in srgb, var(--detail-accent) 24%, #101010);
    box-shadow:
        0 12px 28px color-mix(in srgb, var(--detail-accent) 17%, transparent),
        inset 0 0 0 1px rgba(255,255,255,.04);
    font-size: 23px;
    font-weight: 850;
    animation: recDetailFloat 3.5s ease-in-out infinite;
}

.rec-detail-eyebrow {
    display: block;
    margin-bottom: 5px;
    color: var(--detail-accent);
    font-family: 'Inter', sans-serif;
    font-size: 0.75rem /* FIX: minimum 12px agar terbaca di tablet */;
    font-weight: 850;
    letter-spacing: .13em;
    text-transform: uppercase;
}

.rec-detail-panel h4 {
    margin: 0;
    color: #FFFFFF;
    font-family: 'Plus Jakarta Sans', sans-serif;
    font-size: clamp(22px, 2.1vw, 32px);
    font-weight: 750;
    letter-spacing: -.035em;
    line-height: 1.08;
    overflow-wrap: anywhere;
}

.rec-detail-panel h4 strong {
    color: color-mix(in srgb, var(--detail-accent) 78%, #FFFFFF);
    font-weight: 800;
}

.rec-detail-subtitle {
    margin-top: 6px;
    color: #979797;
    font-size: 12px;
    font-weight: 650;
}

.rec-detail-live-badge {
    display: inline-flex;
    align-items: center;
    gap: 8px;
    flex: 0 0 auto;
    padding: 8px 11px;
    border: 1px solid color-mix(in srgb, var(--detail-accent) 35%, #2B2B2B);
    border-radius: 999px;
    color: #E9E9E9;
    background: rgba(12,12,12,.72);
    backdrop-filter: blur(8px);
    font-size: 0.75rem /* FIX: minimum 12px agar terbaca di tablet */;
    font-weight: 800;
    letter-spacing: .05em;
    text-transform: uppercase;
}

.rec-detail-live-badge::before {
    content: '';
    width: 7px;
    height: 7px;
    border-radius: 50%;
    background: var(--detail-accent);
    animation: recDetailPulse 1.8s ease-out infinite;
}

.rec-detail-stat-grid {
    display: grid;
    grid-template-columns: repeat(4, minmax(0, 1fr));
    gap: 10px;
    margin-bottom: 13px;
}

.rec-detail-stat-card {
    position: relative;
    min-width: 0;
    min-height: 92px;
    padding: 13px 14px;
    overflow: hidden;
    border: 1px solid #2C2C2C;
    border-radius: 14px;
    background:
        linear-gradient(145deg, rgba(255,255,255,.035), transparent 44%),
        rgba(12,13,16,.82);
    transition: transform .22s ease, border-color .22s ease, box-shadow .22s ease, background .22s ease;
}

.rec-detail-stat-card::after {
    content: '';
    position: absolute;
    inset: auto 12px 0 12px;
    height: 2px;
    border-radius: 999px;
    background: linear-gradient(90deg, var(--detail-accent), transparent);
    opacity: .62;
}

.rec-detail-stat-card:hover {
    transform: translateY(-4px);
    border-color: color-mix(in srgb, var(--detail-accent) 48%, #343434);
    background:
        linear-gradient(145deg, color-mix(in srgb, var(--detail-accent) 7%, transparent), transparent 48%),
        rgba(15,16,20,.92);
    box-shadow: 0 13px 28px rgba(0,0,0,.25);
}

.rec-detail-stat-label {
    display: block;
    margin-bottom: 8px;
    color: #929292;
    font-size: 0.75rem /* FIX: minimum 12px agar terbaca di tablet */;
    font-weight: 850;
    letter-spacing: .10em;
    text-transform: uppercase;
}

.rec-detail-stat-value {
    display: block;
    color: #FFFFFF;
    font-family: 'Inter', sans-serif;
    font-size: clamp(17px, 1.5vw, 23px);
    font-weight: 850;
    letter-spacing: -.025em;
    line-height: 1.05;
    overflow-wrap: anywhere;
}

.rec-detail-stat-note {
    display: block;
    margin-top: 7px;
    color: #767676;
    font-size: 0.75rem /* FIX: minimum 12px agar terbaca di tablet */;
    line-height: 1.3;
}

.rec-detail-topic-row {
    display: flex;
    align-items: center;
    flex-wrap: wrap;
    gap: 7px;
    margin-bottom: 16px;
    padding: 10px 12px;
    border: 1px solid #292929;
    border-radius: 12px;
    background: rgba(10,10,10,.45);
}

.rec-detail-topic-label {
    margin-right: 2px;
    color: #8D8D8D;
    font-size: 0.75rem /* FIX: minimum 12px agar terbaca di tablet */;
    font-weight: 850;
    letter-spacing: .08em;
    text-transform: uppercase;
}

.rec-detail-topic-chip {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    padding: 6px 9px;
    border: 1px solid color-mix(in srgb, var(--detail-accent) 34%, #303030);
    border-radius: 999px;
    color: #E7E7E7;
    background: color-mix(in srgb, var(--detail-accent) 8%, transparent);
    font-size: 0.75rem /* FIX: minimum 12px agar terbaca di tablet */;
    font-weight: 750;
    transition: transform .18s ease, color .18s ease, border-color .18s ease, background .18s ease;
}

.rec-detail-topic-chip::before {
    content: '';
    width: 5px;
    height: 5px;
    border-radius: 50%;
    background: var(--detail-accent);
    box-shadow: 0 0 8px var(--detail-accent);
}

.rec-detail-topic-chip:hover {
    transform: translateY(-2px);
    color: #FFFFFF;
    border-color: var(--detail-accent);
    background: color-mix(in srgb, var(--detail-accent) 15%, transparent);
}

.rec-detail-grid {
    display: grid;
    grid-template-columns: minmax(0, 1.25fr) minmax(340px, .85fr);
    align-items: stretch;
    gap: 14px;
    margin-top: 0;
}

.rec-detail-block {
    position: relative;
    min-width: 0;
    height: 100%;
    padding: 16px;
    overflow: hidden;
    border: 1px solid #303030;
    border-radius: 16px;
    background:
        linear-gradient(150deg, rgba(255,255,255,.025), transparent 46%),
        rgba(15,15,16,.90);
    box-sizing: border-box;
    transition: transform .22s ease, border-color .22s ease, box-shadow .22s ease;
}

.rec-detail-block::before {
    content: '';
    position: absolute;
    inset: 14px auto 14px 0;
    width: 3px;
    border-radius: 0 999px 999px 0;
    background: linear-gradient(180deg, var(--detail-accent), transparent);
    opacity: .75;
}

.rec-detail-block:hover,
.rec-detail-block:focus-visible {
    transform: translateY(-3px);
    border-color: color-mix(in srgb, var(--detail-accent) 46%, #353535);
    box-shadow: 0 18px 36px rgba(0,0,0,.22);
    outline: none;
}

.rec-detail-block-head {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 12px;
    margin-bottom: 13px;
}

.rec-detail-block-title-wrap {
    display: flex;
    align-items: center;
    gap: 10px;
    min-width: 0;
}

.rec-detail-block-icon {
    display: grid;
    place-items: center;
    width: 32px;
    height: 32px;
    flex: 0 0 auto;
    border: 1px solid color-mix(in srgb, var(--detail-accent) 35%, #303030);
    border-radius: 10px;
    color: #FFFFFF;
    background: color-mix(in srgb, var(--detail-accent) 12%, transparent);
    font-size: 14px;
}

.rec-detail-block-kicker {
    display: block;
    margin-bottom: 3px;
    color: var(--detail-accent);
    font-size: 0.75rem /* FIX: minimum 12px agar terbaca di tablet */;
    font-weight: 850;
    letter-spacing: .10em;
    text-transform: uppercase;
}

.rec-detail-block-title {
    margin: 0;
    color: #FFFFFF;
    font-size: 12px;
    font-weight: 850;
    letter-spacing: .035em;
    text-transform: uppercase;
}

.rec-detail-count-badge {
    display: inline-flex;
    flex: 0 0 auto;
    padding: 5px 8px;
    border: 1px solid #343434;
    border-radius: 999px;
    color: #AFAFAF;
    background: #111111;
    font-size: 0.75rem /* FIX: minimum 12px agar terbaca di tablet */;
    font-weight: 750;
}

.rec-detail-content-list {
    display: grid;
    gap: 9px;
    max-height: 310px;
    padding-right: 5px;
    overflow-x: hidden;
    overflow-y: auto;
    overscroll-behavior: contain;
    scrollbar-width: thin;
    scrollbar-color: var(--detail-accent) #1B1B1B;
}

.rec-detail-content-list::-webkit-scrollbar-thumb {
    border-radius: 999px;
    background: color-mix(in srgb, var(--detail-accent) 72%, #4A4A4A);
}

.rec-detail-content-item {
    display: grid;
    grid-template-columns: 32px minmax(0, 1fr);
    gap: 11px;
    padding: 12px;
    border: 1px solid #2A2A2A;
    border-radius: 12px;
    background: rgba(23,23,24,.92);
    transition: transform .18s ease, border-color .18s ease, background .18s ease;
}

.rec-detail-content-item:hover {
    transform: translateX(4px);
    border-color: color-mix(in srgb, var(--detail-accent) 42%, #333333);
    background: color-mix(in srgb, var(--detail-accent) 6%, #181818);
}

.rec-detail-content-number {
    display: grid;
    place-items: center;
    width: 32px;
    height: 32px;
    border: 1px solid color-mix(in srgb, var(--detail-accent) 42%, transparent);
    border-radius: 10px;
    color: #FFFFFF;
    background: color-mix(in srgb, var(--detail-accent) 18%, transparent);
    font-size: 0.75rem /* FIX: minimum 12px agar terbaca di tablet */;
    font-weight: 850;
}

.rec-detail-content-text {
    margin: 0;
    color: #E6E6E6;
    font-size: 12px;
    line-height: 1.55;
}

.rec-detail-content-meta {
    gap: 7px;
    margin-top: 7px;
    color: #919191;
    font-size: 0.75rem /* FIX: minimum 12px agar terbaca di tablet */;
}

.rec-detail-source-link {
    transition: transform .18s ease, border-color .18s ease, background .18s ease;
}

.rec-detail-source-link:hover {
    transform: translateY(-2px);
}

.rec-detail-strategy-stack {
    display: grid;
    gap: 10px;
}

.rec-detail-strategy-card {
    display: grid;
    grid-template-columns: 34px minmax(0, 1fr);
    gap: 11px;
    padding: 12px;
    border: 1px solid #2A2A2A;
    border-radius: 12px;
    background: rgba(22,22,23,.90);
    transition: transform .18s ease, border-color .18s ease, background .18s ease;
}

.rec-detail-strategy-card:hover {
    transform: translateX(4px);
    border-color: color-mix(in srgb, var(--detail-accent) 42%, #333333);
    background: color-mix(in srgb, var(--detail-accent) 6%, #171717);
}

.rec-detail-strategy-number {
    display: grid;
    place-items: center;
    width: 34px;
    height: 34px;
    border-radius: 11px;
    color: var(--detail-accent);
    background: color-mix(in srgb, var(--detail-accent) 12%, transparent);
    font-size: 0.75rem /* FIX: minimum 12px agar terbaca di tablet */;
    font-weight: 850;
}

.rec-detail-strategy-title {
    display: block;
    margin-bottom: 5px;
    color: #FFFFFF;
    font-size: 0.75rem /* FIX: minimum 12px agar terbaca di tablet */;
    font-weight: 850;
}

.rec-detail-recommendation {
    margin: 0;
    color: #CFCFCF;
    font-size: 0.75rem /* FIX: minimum 12px agar terbaca di tablet */;
    line-height: 1.62;
}

.rec-detail-basis-row {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 10px;
    margin-top: 11px;
    padding: 10px 11px;
    border: 1px dashed color-mix(in srgb, var(--detail-accent) 34%, #343434);
    border-radius: 11px;
    color: #999999;
    background: color-mix(in srgb, var(--detail-accent) 5%, transparent);
    font-size: 0.75rem /* FIX: minimum 12px agar terbaca di tablet */;
}

.rec-detail-basis-row strong {
    color: #EAEAEA;
    font-weight: 800;
    text-align: right;
}

/* FIX DETAIL REKOMENDASI: tinggi blok bukti mengikuti tinggi alami blok strategi.
   Daftar bukti memakai seluruh ruang yang tersedia terlebih dahulu dan scrollbar
   baru muncul jika seluruh bukti benar-benar lebih tinggi daripada blok strategi. */
@media (min-width: 981px) {
    .rec-detail-grid {
        align-items: stretch;
    }

    .rec-detail-block-strategy {
        height: auto;
        align-self: stretch;
    }

    .rec-detail-block-evidence {
        display: flex;
        flex-direction: column;
        height: 100%;
        min-height: 0;
        overflow: hidden;
    }

    .rec-detail-block-evidence .rec-detail-block-head {
        flex: 0 0 auto;
    }

    .rec-detail-block-evidence .rec-detail-content-list {
        flex: 1 1 0;
        min-height: 0;
        max-height: none;
        overflow-x: hidden;
        overflow-y: auto;
    }
}

@media (max-width: 980px) {
    .rec-detail-block-evidence,
    .rec-detail-block-strategy {
        height: auto;
    }

    .rec-detail-block-evidence {
        overflow: visible;
    }

    .rec-detail-block-evidence .rec-detail-content-list {
        flex: none;
        min-height: 0;
        max-height: none;
        overflow-y: visible;
    }
}

@media (max-width: 1100px) {
    .rec-detail-stat-grid {
        grid-template-columns: repeat(2, minmax(0, 1fr));
    }
}

@media (max-width: 980px) {
    .rec-detail-grid {
        grid-template-columns: 1fr;
    }
}

@media (max-width: 640px) {
    .rec-detail-panel {
        padding: 18px;
        border-radius: 16px;
    }

    .rec-detail-header {
        align-items: flex-start;
        flex-direction: column;
    }

    .rec-detail-stat-grid {
        grid-template-columns: 1fr;
    }

    .rec-detail-platform-icon {
        width: 46px;
        height: 46px;
    }
}

@media (prefers-reduced-motion: reduce) {
    .rec-detail-panel,
    .rec-detail-panel::before,
    .rec-detail-platform-icon,
    .rec-detail-live-badge::before {
        animation: none !important;
    }

    .rec-detail-stat-card,
    .rec-detail-block,
    .rec-detail-content-item,
    .rec-detail-strategy-card,
    .rec-detail-topic-chip,
    .rec-detail-source-link {
        transition: none !important;
    }
}

.rec-topic-summary {
    padding: 14px 15px;
    margin: 0 0 14px;
    border: 1px solid #292929;
    border-radius: 10px;
    background: #141414;
}

.rec-topic-meta {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 12px;
    margin-bottom: 10px;
    color: #D8D8D8;
    font-size: 12px;
}

.rec-sentiment-badge {
    display: inline-flex;
    padding: 4px 8px;
    border: 1px solid var(--sentiment-color, #9E9E9E);
    border-radius: 999px;
    color: var(--sentiment-color, #9E9E9E);
    background: color-mix(in srgb, var(--sentiment-color, #9E9E9E) 10%, transparent);
    font-size: 0.75rem /* FIX: minimum 12px agar terbaca di tablet */;
    font-weight: 800;
}

.rec-progress {
    height: 7px;
    overflow: hidden;
    border-radius: 999px;
    background: #292929;
}

.rec-progress > span {
    display: block;
    height: 100%;
    border-radius: inherit;
    background: linear-gradient(90deg, #B71C1C, #E53935, #FF6B67);
}

.rec-platform-label {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    margin: 2px 0 8px;
    color: #FFFFFF;
    font-size: 12px;
    font-weight: 800;
}

.rec-badge-list {
    display: flex;
    flex-wrap: wrap;
    gap: 7px;
    margin-top: 12px;
}

.rec-influencer-pill {
    display: inline-flex;
    padding: 6px 9px;
    border: 1px solid rgba(229,57,53,.30);
    border-radius: 999px;
    color: #FFB0AE;
    background: rgba(229,57,53,.07);
    font-size: 0.75rem /* FIX: minimum 12px agar terbaca di tablet */;
    font-weight: 700;
}

.rec-topic-pill {
    border-color: color-mix(in srgb, var(--topic-color, #E53935) 42%, transparent);
    color: #FFFFFF;
    background: var(--topic-soft, rgba(229,57,53,.10));
    box-shadow: inset 0 0 0 1px rgba(255,255,255,.025);
}

.rec-topic-hero {
    position: relative;
    overflow: hidden;
    padding: 18px;
    margin: 2px 0 16px;
    border: 1px solid color-mix(in srgb, var(--topic-color, #E53935) 34%, #2A2A2A);
    border-radius: 14px;
    background:
        radial-gradient(circle at top right, var(--topic-soft, rgba(229,57,53,.12)), transparent 34%),
        linear-gradient(145deg, rgba(24,24,24,.98), rgba(14,14,14,.98));
}

.rec-topic-hero::before {
    content: '';
    position: absolute;
    inset: 0 auto 0 0;
    width: 4px;
    background: var(--topic-color, #E53935);
    box-shadow: 0 0 22px var(--topic-color, #E53935);
}

.rec-topic-hero-top {
    display: grid;
    grid-template-columns: 42px minmax(0, 1fr);
    align-items: center;
    gap: 13px;
    margin-bottom: 17px;
}

.rec-topic-icon {
    display: grid;
    place-items: center;
    width: 42px;
    height: 42px;
    flex: 0 0 auto;
    border: 1px solid color-mix(in srgb, var(--topic-color, #E53935) 42%, transparent);
    border-radius: 13px;
    background:
        radial-gradient(circle at 38% 34%, rgba(255,255,255,.28), transparent 28%),
        var(--topic-soft, rgba(229,57,53,.12));
    box-shadow: 0 10px 24px rgba(0,0,0,.24), inset 0 0 0 1px rgba(255,255,255,.04);
    font-size: 16px;
}

.rec-topic-eyebrow {
    margin-bottom: 6px;
    color: var(--topic-color, #E53935);
    font-family: 'Inter', sans-serif;
    font-size: 0.75rem /* FIX: minimum 12px agar terbaca di tablet */;
    font-weight: 800;
    letter-spacing: .12em;
    text-transform: uppercase;
}

.rec-topic-hero h3 {
    margin: 0;
    color: #FFFFFF;
    font-family: 'Inter', sans-serif;
    font-size: clamp(20px, 2.2vw, 28px);
    font-weight: 800;
    letter-spacing: -.035em;
    line-height: 1.12;
}

.rec-topic-stat-grid {
    display: grid;
    grid-template-columns: repeat(3, minmax(0, 1fr));
    gap: 10px;
    margin-bottom: 14px;
}

.rec-topic-stat-card {
    position: relative;
    min-height: 96px;
    padding: 14px;
    overflow: hidden;
    border: 1px solid #2B2B2B;
    border-radius: 13px;
    background:
        linear-gradient(145deg, rgba(255,255,255,.035), transparent 42%),
        rgba(13,13,13,.70);
}

.rec-topic-stat-card::after {
    content: '';
    position: absolute;
    inset: auto 12px 0 12px;
    height: 2px;
    border-radius: 999px;
    background: linear-gradient(90deg, var(--topic-color, #E53935), transparent);
    opacity: .62;
}

.rec-topic-stat-top {
    display: flex;
    align-items: center;
    gap: 8px;
    margin-bottom: 10px;
}

.rec-topic-stat-icon {
    display: grid;
    place-items: center;
    width: 24px;
    height: 24px;
    border: 1px solid color-mix(in srgb, var(--topic-color, #E53935) 32%, transparent);
    border-radius: 8px;
    color: #FFFFFF;
    background: var(--topic-soft, rgba(229,57,53,.12));
    font-size: 12px;
    line-height: 1;
}

.rec-topic-stat-label {
    display: block;
    margin: 0;
    color: #B8B8B8;
    font-family: 'Inter', sans-serif;
    font-size: 0.75rem /* FIX: minimum 12px agar terbaca di tablet */;
    font-weight: 800;
    letter-spacing: .07em;
    text-transform: uppercase;
}

.rec-topic-stat-value {
    display: inline-flex;
    align-items: baseline;
    gap: 6px;
    color: #FFFFFF;
    font-family: 'Inter', sans-serif;
    font-size: 22px;
    font-weight: 800;
    letter-spacing: -.03em;
    line-height: 1;
}

.rec-topic-stat-unit {
    color: #A8A8A8;
    font-size: 0.75rem /* FIX: minimum 12px agar terbaca di tablet */;
    font-weight: 600;
    letter-spacing: 0;
}

.rec-topic-stat-note {
    display: block;
    margin-top: 8px;
    color: #8E8E8E;
    font-size: 0.75rem /* FIX: minimum 12px agar terbaca di tablet */;
    line-height: 1.35;
}

.rec-topic-sentiment-pill {
    display: inline-flex;
    align-items: center;
    gap: 7px;
    width: fit-content;
    padding: 7px 10px;
    border: 1px solid color-mix(in srgb, var(--sentiment-color, #9E9E9E) 36%, transparent);
    border-radius: 999px;
    color: #FFFFFF;
    background: color-mix(in srgb, var(--sentiment-color, #9E9E9E) 16%, transparent);
    font-family: 'Inter', sans-serif;
    font-size: 13px;
    font-weight: 800;
    line-height: 1;
}

.rec-topic-sentiment-pill::before {
    content: '';
    width: 7px;
    height: 7px;
    border-radius: 50%;
    background: var(--sentiment-color, #9E9E9E);
    box-shadow: 0 0 12px var(--sentiment-color, #9E9E9E);
}

.rec-topic-progress-row {
    padding: 13px 14px;
    border: 1px solid #2B2B2B;
    border-radius: 12px;
    background: rgba(10,10,10,.45);
}

.rec-topic-progress-info {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 12px;
    margin-bottom: 9px;
    color: #D6D6D6;
    font-size: 0.75rem /* FIX: minimum 12px agar terbaca di tablet */;
    font-weight: 800;
}

.rec-topic-progress > span {
    background: linear-gradient(90deg, var(--topic-color, #E53935), #FFFFFF22);
}

.rec-topic-insight {
    display: grid;
    grid-template-columns: 118px minmax(0, 1fr);
    gap: 12px;
    align-items: start;
    margin-top: 12px;
    padding: 12px 14px;
    border: 1px solid color-mix(in srgb, var(--topic-color, #E53935) 24%, #2A2A2A);
    border-radius: 12px;
    background: var(--topic-soft, rgba(229,57,53,.10));
}

.rec-topic-insight span {
    color: var(--topic-color, #E53935);
    font-size: 0.75rem /* FIX: minimum 12px agar terbaca di tablet */;
    font-weight: 850;
    letter-spacing: .08em;
    text-transform: uppercase;
}

.rec-topic-insight p {
    margin: 0;
    color: #E0E0E0;
    font-size: 12px;
    line-height: 1.55;
}

.rec-copy-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 12px;
    margin: 18px 0 13px;
    padding: 14px 16px;
    border: 1px solid color-mix(in srgb, var(--topic-color, #E53935) 28%, #2A2A2A);
    border-radius: 12px;
    background: linear-gradient(135deg, var(--topic-soft, rgba(229,57,53,.10)), rgba(18,18,18,.94));
}

.rec-copy-header span {
    display: block;
    margin-bottom: 2px;
    color: var(--topic-color, #E53935);
    font-size: 0.75rem /* FIX: minimum 12px agar terbaca di tablet */;
    font-weight: 850;
    letter-spacing: .09em;
    text-transform: uppercase;
}

.rec-copy-header strong {
    display: block;
    color: #FFFFFF;
    font-size: 13px;
    line-height: 1.35;
}

.rec-copy-header em {
    flex: 0 0 auto;
    padding: 6px 10px;
    border: 1px solid color-mix(in srgb, var(--topic-color, #E53935) 35%, transparent);
    border-radius: 999px;
    color: #FFFFFF;
    background: rgba(255,255,255,.04);
    font-style: normal;
    font-size: 0.75rem /* FIX: minimum 12px agar terbaca di tablet */;
    font-weight: 800;
}

.rec-platform-card-head {
    display: flex;
    align-items: center;
    gap: 10px;
    min-height: 54px;
    padding: 12px 13px;
    border: 1px solid color-mix(in srgb, var(--platform-color, #E53935) 35%, #2A2A2A);
    border-bottom: 0;
    border-radius: 12px 12px 0 0;
    background: linear-gradient(135deg, color-mix(in srgb, var(--platform-color, #E53935) 16%, transparent), rgba(18,18,18,.96));
}

.rec-platform-card-icon {
    display: grid;
    place-items: center;
    width: 30px;
    height: 30px;
    border-radius: 9px;
    color: #FFFFFF;
    background: var(--platform-color, #E53935);
    font-size: 13px;
    font-weight: 900;
}

.rec-platform-card-head span {
    display: block;
    color: #8C8C8C;
    font-size: 0.75rem /* FIX: minimum 12px agar terbaca di tablet */;
    font-weight: 850;
    letter-spacing: .08em;
    text-transform: uppercase;
}

.rec-platform-card-head strong {
    display: block;
    margin-top: 1px;
    color: #FFFFFF;
    font-size: 12px;
    font-weight: 850;
}

.rec-topic-footer {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 14px;
    margin-top: 14px;
    margin-bottom: 18px;
    padding: 12px 16px;
    border: 1px solid color-mix(in srgb, var(--topic-color, #E53935) 26%, #2A2A2A);
    border-radius: 12px;
    background: rgba(13,13,13,.65);
    transform: none;
}

.rec-topic-footer-label span {
    display: block;
    color: #FFFFFF;
    font-size: 12px;
    font-weight: 850;
}

.rec-topic-footer-label small {
    display: block;
    margin-top: 3px;
    color: #8E8E8E;
    font-size: 0.75rem /* FIX: minimum 12px agar terbaca di tablet */;
    line-height: 1.35;
}

.rec-strategy-card {
    padding: 21px;
    border: 1px solid var(--rec-border);
    border-left: 3px solid var(--rec-primary);
    border-radius: 12px;
    background: linear-gradient(140deg, #1A1A1A, #131313);
}

.rec-strategy-item {
    display: grid;
    grid-template-columns: 31px 1fr;
    gap: 12px;
    align-items: start;
    padding: 13px 0;
    border-bottom: 1px solid #292929;
}

.rec-strategy-item:last-child {
    padding-bottom: 0;
    border-bottom: 0;
}

.rec-strategy-number {
    display: grid;
    place-items: center;
    width: 29px;
    height: 29px;
    border-radius: 8px;
    color: #FFFFFF;
    background: #E53935;
    font-family: 'Plus Jakarta Sans', sans-serif;
    font-size: 12px;
    font-weight: 800;
}

.rec-strategy-text {
    color: #D3D3D3;
    font-size: 13px;
    line-height: 1.65;
}

.rec-strategy-text strong {
    color: #FFFFFF;
}



/* Panel matriks interaktif */
.rec-matrix-intro {
    display: grid;
    grid-template-columns: 52px minmax(0, 1fr);
    gap: 14px;
    align-items: center;
    margin: 4px 0 18px;
    padding: 17px 18px;
    border: 1px solid rgba(229,57,53,.30);
    border-radius: 15px;
    background:
        radial-gradient(circle at top right, rgba(229,57,53,.16), transparent 32%),
        linear-gradient(135deg, rgba(26,26,26,.96), rgba(12,12,12,.98));
    box-shadow: 0 18px 42px rgba(0,0,0,.24);
}

.rec-matrix-intro-icon {
    display: grid;
    place-items: center;
    width: 52px;
    height: 52px;
    border: 1px solid rgba(229,57,53,.42);
    border-radius: 16px;
    color: #FFFFFF;
    background: linear-gradient(145deg, rgba(229,57,53,.26), rgba(229,57,53,.08));
    box-shadow: 0 0 26px rgba(229,57,53,.18), inset 0 0 0 1px rgba(255,255,255,.05);
    font-size: 22px;
}

.rec-matrix-intro span {
    display: block;
    margin-bottom: 4px;
    color: #FF6B67;
    font-size: 0.75rem /* FIX: minimum 12px agar terbaca di tablet */;
    font-weight: 850;
    letter-spacing: .11em;
    text-transform: uppercase;
}

.rec-matrix-intro strong {
    display: block;
    color: #FFFFFF;
    font-size: 16px;
    font-weight: 850;
    line-height: 1.35;
}

.rec-matrix-intro p {
    margin: 6px 0 0;
    color: #AAAAAA;
    font-size: 12px;
    line-height: 1.55;
}

.rec-matrix-insight-grid {
    display: grid;
    grid-template-columns: repeat(4, minmax(0, 1fr));
    gap: 14px;
    margin: 16px 0 20px;
}

.rec-matrix-insight-card {
    position: relative;
    isolation: isolate;
    min-height: 136px;
    padding: 18px 18px 16px;
    overflow: hidden;
    border: 1px solid rgba(var(--rec-card-rgb, 229,57,53), .36);
    border-radius: 20px;
    background:
        radial-gradient(circle at 88% 14%, rgba(var(--rec-card-rgb, 229,57,53), .30), transparent 29%),
        radial-gradient(circle at 12% 110%, rgba(var(--rec-card-rgb, 229,57,53), .17), transparent 34%),
        linear-gradient(145deg, rgba(var(--rec-card-rgb, 229,57,53), .16), rgba(19,19,23,.96) 48%, rgba(8,8,10,.98));
    box-shadow:
        0 22px 48px rgba(0,0,0,.34),
        0 0 32px rgba(var(--rec-card-rgb, 229,57,53), .13),
        inset 0 1px 0 rgba(255,255,255,.08);
    transition: transform .22s ease, border-color .22s ease, box-shadow .22s ease, background .22s ease;
}

.rec-matrix-insight-card:hover {
    transform: translateY(-5px);
    border-color: rgba(var(--rec-card-rgb, 229,57,53), .64);
    box-shadow:
        0 28px 62px rgba(0,0,0,.44),
        0 0 42px rgba(var(--rec-card-rgb, 229,57,53), .24),
        inset 0 1px 0 rgba(255,255,255,.12);
}

.rec-matrix-insight-card::before {
    content: '';
    position: absolute;
    z-index: -1;
    width: 118px;
    height: 118px;
    right: -34px;
    top: -38px;
    border-radius: 999px;
    background: rgba(var(--rec-card-rgb, 229,57,53), .28);
    filter: blur(18px);
    opacity: .78;
}

.rec-matrix-insight-card::after {
    content: '';
    position: absolute;
    inset: auto 18px 12px 18px;
    height: 3px;
    border-radius: 999px;
    background: linear-gradient(90deg, var(--rec-card-color, #E53935), rgba(var(--rec-card-rgb, 229,57,53), .22), transparent);
    box-shadow: 0 0 18px rgba(var(--rec-card-rgb, 229,57,53), .38);
}

.rec-card-topic {
    --rec-card-color: #FF4D57;
    --rec-card-rgb: 255,77,87;
}

.rec-card-match {
    --rec-card-color: #25C2FF;
    --rec-card-rgb: 37,194,255;
}

.rec-card-score {
    --rec-card-color: #A56BFF;
    --rec-card-rgb: 165,107,255;
}

.rec-card-strong {
    --rec-card-color: #35D98B;
    --rec-card-rgb: 53,217,139;
}

.rec-matrix-card-top {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 10px;
    margin-bottom: 14px;
}

.rec-matrix-card-icon {
    display: grid;
    place-items: center;
    width: 42px;
    height: 42px;
    flex: 0 0 42px;
    border: 1px solid rgba(var(--rec-card-rgb, 229,57,53), .45);
    border-radius: 14px;
    background:
        linear-gradient(145deg, rgba(var(--rec-card-rgb, 229,57,53), .27), rgba(255,255,255,.045));
    box-shadow:
        0 0 24px rgba(var(--rec-card-rgb, 229,57,53), .20),
        inset 0 1px 0 rgba(255,255,255,.10);
    color: #FFFFFF;
    font-size: 20px;
    line-height: 1;
}

.rec-matrix-card-pulse {
    width: 9px;
    height: 9px;
    border-radius: 999px;
    background: var(--rec-card-color, #E53935);
    box-shadow: 0 0 0 6px rgba(var(--rec-card-rgb, 229,57,53), .13), 0 0 18px rgba(var(--rec-card-rgb, 229,57,53), .55);
}

.rec-matrix-insight-card span {
    display: block;
    margin-bottom: 9px;
    color: rgba(255,255,255,.68);
    font-size: 0.75rem /* FIX: minimum 12px agar terbaca di tablet */;
    font-weight: 900;
    letter-spacing: .105em;
    text-transform: uppercase;
}

.rec-matrix-insight-card strong {
    display: block;
    color: #FFFFFF;
    font-family: 'Inter', sans-serif;
    font-size: clamp(24px, 2vw, 31px);
    font-weight: 950;
    line-height: 1.05;
    letter-spacing: -.035em;
    text-shadow: 0 0 18px rgba(var(--rec-card-rgb, 229,57,53), .20);
}

.rec-matrix-insight-card small {
    display: block;
    margin-top: 10px;
    padding-right: 4px;
    color: rgba(255,255,255,.66);
    font-size: 12px;
    line-height: 1.45;
}

.rec-matrix-rank-grid {
    display: grid;
    grid-template-columns: repeat(3, minmax(0, 1fr));
    gap: 10px;
    margin: 12px 0 18px;
}

.rec-matrix-rank-card {
    display: grid;
    grid-template-columns: 40px minmax(0, 1fr) 54px;
    gap: 12px;
    align-items: center;
    min-height: 78px;
    padding: 13px 14px;
    border: 1px solid color-mix(in srgb, var(--platform-color, #E53935) 32%, #2A2A2A);
    border-radius: 14px;
    background:
        radial-gradient(circle at top right, color-mix(in srgb, var(--platform-color, #E53935) 18%, transparent), transparent 35%),
        rgba(14,14,14,.96);
}

.rec-matrix-rank-number {
    display: grid;
    place-items: center;
    width: 38px;
    height: 38px;
    border-radius: 12px;
    color: #FFFFFF;
    background: color-mix(in srgb, var(--platform-color, #E53935) 28%, #111111);
    font-size: 13px;
    font-weight: 900;
}

.rec-matrix-rank-main span {
    display: block;
    color: #FFFFFF;
    font-size: 13px;
    font-weight: 850;
    line-height: 1.25;
    overflow-wrap: anywhere;
}

.rec-matrix-rank-main small {
    display: inline-flex;
    margin-top: 5px;
    padding: 4px 7px;
    border: 1px solid color-mix(in srgb, var(--platform-color, #E53935) 36%, transparent);
    border-radius: 999px;
    color: #DCDCDC;
    background: color-mix(in srgb, var(--platform-color, #E53935) 12%, transparent);
    font-size: 0.75rem /* FIX: minimum 12px agar terbaca di tablet */;
    font-weight: 800;
}

.rec-matrix-rank-score {
    justify-self: end;
    color: #FFFFFF;
    font-family: 'Inter', sans-serif;
    font-size: 24px;
    font-weight: 900;
}

.rec-matrix-rank-score em {
    color: #8A8A8A;
    font-style: normal;
    font-size: 0.75rem /* FIX: minimum 12px agar terbaca di tablet */;
    font-weight: 700;
}

.rec-matrix-empty {
    margin: 12px 0 18px;
    padding: 15px 16px;
    border: 1px solid rgba(255,152,0,.36);
    border-radius: 13px;
    color: #FFD59B;
    background: rgba(255,152,0,.08);
    font-size: 12px;
    line-height: 1.55;
}

div[data-testid="stPlotlyChart"] {
    padding: 10px 8px 4px;
    border: 1px solid rgba(229,57,53,.18);
    border-radius: 16px;
    background:
        radial-gradient(circle at top right, rgba(229,57,53,.08), transparent 30%),
        linear-gradient(145deg, rgba(21,24,33,.86), rgba(13,13,13,.92));
    box-shadow: 0 18px 42px rgba(0,0,0,.22);
}

@media (max-width: 980px) {
    .rec-matrix-insight-grid,
    .rec-matrix-rank-grid { grid-template-columns: 1fr 1fr; }
}

@media (max-width: 720px) {
    .rec-matrix-intro { grid-template-columns: 1fr; }
    .rec-matrix-insight-grid,
    .rec-matrix-rank-grid { grid-template-columns: 1fr; }
}


/* Tabel skor detail yang lebih interaktif */
.rec-matrix-table-hero {
    position: relative;
    overflow: hidden;
    margin: 2px 0 16px;
    padding: 16px 18px;
    border: 1px solid rgba(29,161,242,.28);
    border-radius: 18px;
    background:
        radial-gradient(circle at 92% 0%, rgba(29,161,242,.18), transparent 32%),
        radial-gradient(circle at 8% 100%, rgba(229,57,53,.16), transparent 30%),
        linear-gradient(145deg, rgba(20,23,32,.96), rgba(9,9,10,.98));
    box-shadow: 0 18px 44px rgba(0,0,0,.28), inset 0 1px 0 rgba(255,255,255,.06);
    animation: recTableHeroIn .62s cubic-bezier(.22,1,.36,1) both, recTableHeroGlow 6.8s ease-in-out infinite;
}

.rec-matrix-table-hero::before {
    content: '';
    position: absolute;
    inset: -42% auto -42% -34%;
    width: 34%;
    transform: rotate(17deg);
    background: linear-gradient(90deg, transparent, rgba(255,255,255,.16), transparent);
    filter: blur(.4px);
    animation: recTableLightSweep 4.6s ease-in-out infinite;
    pointer-events: none;
}

.rec-matrix-table-hero::after {
    content: '';
    position: absolute;
    inset: auto 18px 12px 18px;
    height: 2px;
    border-radius: 999px;
    background: linear-gradient(90deg, #E53935, #1DA1F2, #35D98B, transparent);
    background-size: 220% 100%;
    opacity: .82;
    box-shadow: 0 0 18px rgba(29,161,242,.24);
    animation: recTableLineMove 3.8s ease-in-out infinite;
}

.rec-matrix-table-hero span {
    display: inline-flex;
    align-items: center;
    gap: 7px;
    margin-bottom: 7px;
    color: #7CCBFF;
    font-size: 0.75rem /* FIX: minimum 12px agar terbaca di tablet */;
    font-weight: 900;
    letter-spacing: .12em;
    text-transform: uppercase;
}

.rec-matrix-table-hero strong {
    display: block;
    color: #FFFFFF;
    font-size: 18px;
    font-weight: 950;
    line-height: 1.25;
    letter-spacing: -.025em;
}

.rec-matrix-table-hero p {
    margin: 7px 0 0;
    max-width: 820px;
    color: rgba(255,255,255,.66);
    font-size: 12px;
    line-height: 1.55;
}


.rec-matrix-table-statbar {
    display: grid;
    grid-template-columns: repeat(4, minmax(0, 1fr));
    gap: 14px;
    margin: 14px 0 18px;
}

.rec-matrix-table-stat {
    --stat-color: #1DA1F2;
    --stat-color-2: #E53935;
    position: relative;
    min-height: 108px;
    padding: 18px 18px 16px;
    overflow: hidden;
    isolation: isolate;
    border: 1px solid color-mix(in srgb, var(--stat-color) 38%, rgba(255,255,255,.12));
    border-radius: 20px;
    background:
        radial-gradient(circle at 86% 14%, color-mix(in srgb, var(--stat-color) 38%, transparent), transparent 32%),
        radial-gradient(circle at 0% 100%, color-mix(in srgb, var(--stat-color-2) 23%, transparent), transparent 38%),
        linear-gradient(145deg, rgba(26,27,34,.96), rgba(10,10,12,.96));
    box-shadow:
        0 20px 42px rgba(0,0,0,.26),
        0 0 26px color-mix(in srgb, var(--stat-color) 12%, transparent),
        inset 0 1px 0 rgba(255,255,255,.08);
    animation: recTableStatIn .62s cubic-bezier(.22,1,.36,1) both;
    transition: transform .24s ease, border-color .24s ease, box-shadow .24s ease, filter .24s ease;
}

.rec-matrix-table-stat::before {
    content: "";
    position: absolute;
    inset: 0;
    background:
        linear-gradient(115deg, transparent 0%, transparent 38%, rgba(255,255,255,.22) 48%, transparent 60%, transparent 100%);
    transform: translateX(-135%) skewX(-8deg);
    opacity: .55;
    z-index: -1;
    animation: recTableStatSweep 5.4s ease-in-out infinite;
}

.rec-matrix-table-stat::after {
    content: "";
    position: absolute;
    right: -42px;
    bottom: -48px;
    width: 124px;
    height: 124px;
    border-radius: 999px;
    background: color-mix(in srgb, var(--stat-color) 30%, transparent);
    filter: blur(10px);
    opacity: .72;
    z-index: -2;
    animation: recTableStatGlow 3.7s ease-in-out infinite alternate;
}

.rec-matrix-table-stat.stat-rows {
    --stat-color: #FF5252;
    --stat-color-2: #FF9800;
}

.rec-matrix-table-stat.stat-platform {
    --stat-color: #1DA1F2;
    --stat-color-2: #00BCD4;
}

.rec-matrix-table-stat.stat-score {
    --stat-color: #7C4DFF;
    --stat-color-2: #E040FB;
}

.rec-matrix-table-stat.stat-top {
    --stat-color: #35D98B;
    --stat-color-2: #1DA1F2;
}

.rec-matrix-table-stat:nth-child(1) { animation-delay: .03s; }
.rec-matrix-table-stat:nth-child(2) { animation-delay: .10s; }
.rec-matrix-table-stat:nth-child(3) { animation-delay: .17s; }
.rec-matrix-table-stat:nth-child(4) { animation-delay: .24s; }
.rec-matrix-table-stat:nth-child(2)::before { animation-delay: .8s; }
.rec-matrix-table-stat:nth-child(3)::before { animation-delay: 1.5s; }
.rec-matrix-table-stat:nth-child(4)::before { animation-delay: 2.2s; }

.rec-matrix-table-stat:hover {
    transform: translateY(-5px) scale(1.012);
    filter: saturate(1.12);
    border-color: color-mix(in srgb, var(--stat-color) 62%, rgba(255,255,255,.20));
    box-shadow:
        0 24px 50px rgba(0,0,0,.34),
        0 0 34px color-mix(in srgb, var(--stat-color) 23%, transparent),
        0 0 18px color-mix(in srgb, var(--stat-color-2) 14%, transparent),
        inset 0 1px 0 rgba(255,255,255,.11);
}

.rec-matrix-table-stat-topline {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 10px;
    margin-bottom: 11px;
}

.rec-matrix-table-stat span {
    display: block;
    margin: 0;
    color: rgba(255,255,255,.62);
    font-size: 0.75rem /* FIX: minimum 12px agar terbaca di tablet */;
    font-weight: 900;
    letter-spacing: .09em;
    text-transform: uppercase;
}

.rec-matrix-table-stat-icon {
    display: grid;
    place-items: center;
    width: 34px;
    height: 34px;
    flex: 0 0 auto;
    border-radius: 13px;
    color: #FFFFFF;
    background:
        linear-gradient(145deg, color-mix(in srgb, var(--stat-color) 45%, rgba(255,255,255,.10)), rgba(255,255,255,.055));
    border: 1px solid color-mix(in srgb, var(--stat-color) 48%, rgba(255,255,255,.14));
    box-shadow: 0 0 22px color-mix(in srgb, var(--stat-color) 22%, transparent);
    font-size: 15px;
    animation: recTableStatIconFloat 3.2s ease-in-out infinite;
}

.rec-matrix-table-stat strong {
    display: block;
    max-width: 100%;
    color: #FFFFFF;
    font-size: clamp(22px, 2.2vw, 30px);
    font-weight: 950;
    line-height: 1.08;
    letter-spacing: -.055em;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
    text-shadow: 0 0 18px color-mix(in srgb, var(--stat-color) 25%, transparent);
}

.rec-matrix-table-stat small {
    display: block;
    margin-top: 8px;
    color: color-mix(in srgb, var(--stat-color) 60%, rgba(255,255,255,.64));
    font-size: 0.75rem /* FIX: minimum 12px agar terbaca di tablet */;
    font-weight: 800;
    letter-spacing: .01em;
}

.rec-matrix-table-detail {
    position: relative;
    overflow: hidden;
    margin-top: 18px;
    margin-bottom: 20px;
    padding: 24px 24px 28px;
    min-height: 178px;
    border: 1px solid rgba(229,57,53,.26);
    border-radius: 20px;
    background:
        radial-gradient(circle at 100% 0%, rgba(229,57,53,.16), transparent 30%),
        radial-gradient(circle at 0% 100%, rgba(255,152,0,.08), transparent 28%),
        linear-gradient(145deg, rgba(18,18,22,.96), rgba(10,10,12,.98));
    box-shadow: 0 18px 42px rgba(0,0,0,.28);
    display: flex;
    flex-direction: column;
    justify-content: center;
    gap: 18px;
    animation: recTableDetailIn .58s cubic-bezier(.22,1,.36,1) both;
}

.rec-matrix-table-detail::after {
    content: "";
    position: absolute;
    inset: auto 28px 18px 28px;
    height: 1px;
    border-radius: 999px;
    background: linear-gradient(90deg, transparent, rgba(255,255,255,.16), transparent);
    opacity: .65;
    pointer-events: none;
}

.rec-matrix-table-detail-title {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 12px;
    margin-bottom: 0;
    position: relative;
    z-index: 1;
}

.rec-matrix-table-detail-title strong {
    color: #FFFFFF;
    font-size: 15px;
    font-weight: 950;
}

.rec-matrix-table-detail-title span {
    padding: 5px 9px;
    border: 1px solid rgba(29,161,242,.30);
    border-radius: 999px;
    color: #DFF4FF;
    background: rgba(29,161,242,.10);
    font-size: 0.75rem /* FIX: minimum 12px agar terbaca di tablet */;
    font-weight: 850;
}

.rec-matrix-table-score-pills {
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    gap: 12px 13px;
    padding-bottom: 6px;
    position: relative;
    z-index: 1;
}

.rec-matrix-table-score-pill {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    gap: 8px;
    min-height: 38px;
    padding: 10px 14px;
    border: 1px solid rgba(255,255,255,.10);
    border-radius: 999px;
    color: rgba(255,255,255,.76);
    background: rgba(255,255,255,.045);
    font-size: 0.75rem /* FIX: minimum 12px agar terbaca di tablet */;
    font-weight: 850;
    line-height: 1.15;
    animation: recScorePillPop .45s cubic-bezier(.22,1,.36,1) both;
    transition: transform .2s ease, box-shadow .2s ease;
}

.rec-matrix-table-score-pill:hover {
    transform: translateY(-2px) scale(1.015);
    box-shadow: 0 10px 22px rgba(0,0,0,.22);
}

.rec-matrix-table-score-pill b {
    color: #FFFFFF;
    font-size: 13px;
    font-weight: 950;
}

.rec-matrix-table-score-pill.is-high {
    border-color: rgba(53,217,139,.36);
    background: rgba(53,217,139,.10);
}

.rec-matrix-table-score-pill.is-mid {
    border-color: rgba(255,152,0,.34);
    background: rgba(255,152,0,.10);
}

.rec-matrix-table-score-pill.is-low {
    border-color: rgba(229,57,53,.34);
    background: rgba(229,57,53,.10);
}

@media (max-width: 720px) {
    .rec-matrix-table-detail {
        min-height: auto;
        padding: 20px 18px 24px;
        gap: 14px;
    }

    .rec-matrix-table-detail-title {
        align-items: flex-start;
        flex-direction: column;
    }

    .rec-matrix-table-score-pills {
        gap: 10px;
        padding-bottom: 8px;
    }
}

.rec-matrix-table-empty-state {
    margin: 14px 0;
    padding: 13px 14px;
    border: 1px solid rgba(255,152,0,.34);
    border-radius: 13px;
    color: #FFD59B;
    background: rgba(255,152,0,.08);
    font-size: 12px;
}

div[data-testid="stDataFrame"] {
    border: 1px solid rgba(29,161,242,.24) !important;
    border-radius: 16px !important;
    overflow: hidden !important;
    box-shadow: 0 18px 42px rgba(0,0,0,.24), 0 0 26px rgba(29,161,242,.08) !important;
    animation: recDataFrameIn .52s cubic-bezier(.22,1,.36,1) both, recDataFrameGlow 5.2s ease-in-out infinite;
}

div[data-testid="stDownloadButton"] button {
    border: 1px solid rgba(53,217,139,.42) !important;
    border-radius: 11px !important;
    color: #DFFFEF !important;
    background: linear-gradient(135deg, rgba(53,217,139,.16), rgba(29,161,242,.08)) !important;
    font-weight: 850 !important;
}

div[data-testid="stDownloadButton"] button:hover {
    border-color: rgba(53,217,139,.72) !important;
    box-shadow: 0 0 24px rgba(53,217,139,.18) !important;
}

/* Animasi dan tombol penerapan filter pada tabel interaktif */
div[data-testid="stForm"] {
    animation: recFilterPanelIn .55s cubic-bezier(.22,1,.36,1) both;
}

div[data-testid="stFormSubmitButton"] button {
    position: relative;
    overflow: hidden;
    border: 1px solid rgba(229,57,53,.58) !important;
    border-radius: 12px !important;
    color: #FFFFFF !important;
    background: linear-gradient(135deg, #E53935, #FF5C5C 48%, #1DA1F2) !important;
    font-weight: 900 !important;
    letter-spacing: .01em !important;
    box-shadow: 0 12px 28px rgba(229,57,53,.22), 0 0 24px rgba(29,161,242,.08) !important;
    transition: transform .22s ease, box-shadow .22s ease, filter .22s ease !important;
}

div[data-testid="stFormSubmitButton"] button:hover {
    transform: translateY(-2px) !important;
    filter: brightness(1.06) !important;
    box-shadow: 0 17px 34px rgba(229,57,53,.30), 0 0 30px rgba(29,161,242,.16) !important;
}

.rec-matrix-table-apply-note {
    margin: -2px 0 12px;
    padding: 9px 11px;
    border: 1px solid rgba(29,161,242,.20);
    border-radius: 12px;
    color: rgba(255,255,255,.64);
    background: rgba(29,161,242,.055);
    font-size: 0.75rem /* FIX: minimum 12px agar terbaca di tablet */;
    line-height: 1.45;
    animation: recTableNoteIn .46s ease both;
}

.rec-matrix-table-fixed-limit {
    /* Posisi info baris dibuat sedikit lebih naik agar sejajar rapi dengan area filter. */
    margin-top: 0;
    margin-bottom: -4px;
    padding: 12px 16px 13px;
    transform: translateY(-6px);
    border: 1px solid rgba(29,161,242,.26);
    border-radius: 16px;
    background:
        radial-gradient(circle at 92% 20%, rgba(29,161,242,.18), transparent 30%),
        linear-gradient(135deg, rgba(15,23,42,.82), rgba(17,17,17,.72));
    box-shadow: inset 0 1px 0 rgba(255,255,255,.05), 0 14px 34px rgba(0,0,0,.22);
    animation: recTableFilterIn .44s ease both;
}

.rec-matrix-table-fixed-limit span {
    display: block;
    margin-bottom: 4px;
    color: rgba(255,255,255,.76);
    font-size: 12px;
    font-weight: 900;
}

.rec-matrix-table-fixed-limit strong {
    display: inline-block;
    margin-right: 8px;
    color: #FFFFFF;
    font-size: 24px;
    line-height: 1;
    font-weight: 950;
}

.rec-matrix-table-fixed-limit small {
    color: rgba(255,255,255,.58);
    font-size: 0.75rem /* FIX: minimum 12px agar terbaca di tablet */;
    line-height: 1.45;
}

@keyframes recTableHeroIn {
    from { opacity: 0; transform: translateY(12px) scale(.985); }
    to { opacity: 1; transform: translateY(0) scale(1); }
}

@keyframes recTableHeroGlow {
    0%, 100% { box-shadow: 0 18px 44px rgba(0,0,0,.28), 0 0 20px rgba(29,161,242,.06), inset 0 1px 0 rgba(255,255,255,.06); }
    50% { box-shadow: 0 20px 50px rgba(0,0,0,.32), 0 0 32px rgba(229,57,53,.12), 0 0 28px rgba(29,161,242,.10), inset 0 1px 0 rgba(255,255,255,.07); }
}

@keyframes recTableLightSweep {
    0%, 38% { transform: translateX(0) rotate(17deg); opacity: 0; }
    48% { opacity: .95; }
    72%, 100% { transform: translateX(520%) rotate(17deg); opacity: 0; }
}

@keyframes recTableLineMove {
    0%, 100% { background-position: 0% 50%; opacity: .70; }
    50% { background-position: 100% 50%; opacity: 1; }
}

@keyframes recFilterPanelIn {
    from { opacity: 0; transform: translateY(10px); }
    to { opacity: 1; transform: translateY(0); }
}

@keyframes recTableStatIn {
    from { opacity: 0; transform: translateY(14px) scale(.97); }
    to { opacity: 1; transform: translateY(0) scale(1); }
}

@keyframes recTableStatSweep {
    0%, 58% { transform: translateX(-135%) skewX(-8deg); opacity: 0; }
    68% { opacity: .56; }
    82%, 100% { transform: translateX(135%) skewX(-8deg); opacity: 0; }
}

@keyframes recTableStatGlow {
    0% { transform: translate3d(0, 0, 0) scale(.92); opacity: .52; }
    100% { transform: translate3d(-12px, -11px, 0) scale(1.18); opacity: .92; }
}

@keyframes recTableStatIconFloat {
    0%, 100% { transform: translateY(0) rotate(0deg); }
    50% { transform: translateY(-3px) rotate(-2deg); }
}

@keyframes recDataFrameIn {
    from { opacity: 0; transform: translateY(12px); }
    to { opacity: 1; transform: translateY(0); }
}

@keyframes recDataFrameGlow {
    0%, 100% { box-shadow: 0 18px 42px rgba(0,0,0,.24), 0 0 26px rgba(29,161,242,.08); }
    50% { box-shadow: 0 20px 48px rgba(0,0,0,.28), 0 0 34px rgba(29,161,242,.14), 0 0 18px rgba(229,57,53,.08); }
}

@keyframes recTableDetailIn {
    from { opacity: 0; transform: translateY(12px) scale(.985); }
    to { opacity: 1; transform: translateY(0) scale(1); }
}

@keyframes recScorePillPop {
    from { opacity: 0; transform: translateY(8px) scale(.94); }
    to { opacity: 1; transform: translateY(0) scale(1); }
}

@keyframes recTableNoteIn {
    from { opacity: 0; transform: translateY(8px); }
    to { opacity: 1; transform: translateY(0); }
}

@media (prefers-reduced-motion: reduce) {
    .rec-matrix-table-hero,
    .rec-matrix-table-hero::before,
    .rec-matrix-table-hero::after,
    .rec-matrix-table-stat,
    .rec-matrix-table-stat::before,
    .rec-matrix-table-stat::after,
    .rec-matrix-table-stat-icon,
    .rec-matrix-table-detail,
    .rec-matrix-table-score-pill,
    .rec-matrix-table-apply-note,
    div[data-testid="stForm"],
    div[data-testid="stDataFrame"] {
        animation: none !important;
        transition: none !important;
    }
}

@media (max-width: 860px) {
    .rec-matrix-table-statbar { grid-template-columns: 1fr 1fr; }
}

@media (max-width: 560px) {
    .rec-matrix-table-statbar { grid-template-columns: 1fr; }
}

/* Area pemilih layanan dibuat ringkas agar fokus tetap pada layanan aktif. */
.rec-service-note {
    min-height: 56px;
    margin-top: 30px;
    padding: 12px 16px;
    display: flex;
    align-items: center;
    border-left: 2px solid rgba(229, 57, 53, .55);
    border-radius: 0 10px 10px 0;
    color: #858B96;
    background: linear-gradient(90deg, rgba(229, 57, 53, .055), rgba(229, 57, 53, 0));
    font-size: .92rem;
    line-height: 1.55;
}

@media (max-width: 768px) {
    .rec-service-note {
        min-height: auto;
        margin-top: 4px;
        padding: 10px 12px;
    }
}

/* Widget bawaan Streamlit pada halaman rekomendasi */
div[data-testid="stSelectbox"] > label {
    color: #E8E8E8 !important;
    font-weight: 700 !important;
}

div[data-testid="stSelectbox"] div[data-baseweb="select"] > div {
    border-color: #343434 !important;
    border-radius: 9px !important;
    background: #242424 !important;
}

div[data-testid="stExpander"] {
    margin-bottom: 13px;
    overflow: hidden;
    border: 1px solid #303030 !important;
    border-radius: 14px !important;
    background: linear-gradient(135deg, rgba(26,26,26,.98), rgba(14,14,14,.98)) !important;
    box-shadow: 0 12px 30px rgba(0,0,0,.22);
}

div[data-testid="stExpander"] summary {
    min-height: 56px !important;
    padding: 15px 18px !important;
    color: #F2F2F2 !important;
    font-weight: 850 !important;
    letter-spacing: -.01em !important;
}

div[data-testid="stExpander"] summary:hover {
    color: #FFFFFF !important;
    background: rgba(229,57,53,.06) !important;
}

div[data-testid="stButton"] button[kind="secondary"] {
    width: 100%;
    min-height: 36px;
    margin-bottom: 18px;
    border: 1px solid #E53935;
    border-radius: 8px;
    color: #FF7773;
    background: transparent;
    font-weight: 700;
}

div[data-testid="stButton"] button[kind="secondary"]:hover {
    border-color: #FF5252;
    color: #FFFFFF;
    background: rgba(229,57,53,.12);
}

div[data-testid="stCode"] {
    margin-top: 0 !important;
    border: 1px solid #2D2D2D;
    border-radius: 0 0 12px 12px;
    background: #151821 !important;
    box-shadow: 0 12px 26px rgba(0,0,0,.20);
    overflow: hidden !important;
    height: 150px !important;
    max-height: 150px !important;
}

div[data-testid="stCode"] pre {
    height: 150px !important;
    max-height: 150px !important;
    margin: 0 !important;
    padding: 14px 15px !important;
    overflow-x: hidden !important;
    overflow-y: auto !important;
    scrollbar-width: thin;
    scrollbar-color: rgba(229,57,53,.75) rgba(255,255,255,.08);
}

div[data-testid="stCode"] pre::-webkit-scrollbar {
    width: 8px;
}

div[data-testid="stCode"] pre::-webkit-scrollbar-track {
    background: rgba(255,255,255,.07);
    border-radius: 999px;
}

div[data-testid="stCode"] pre::-webkit-scrollbar-thumb {
    background: rgba(229,57,53,.78);
    border-radius: 999px;
}

div[data-testid="stCode"] code {
    display: block !important;
    min-height: 100% !important;
    padding: 0 !important;
    color: #FFFFFF !important;
    font-size: 0.75rem /* FIX: minimum 12px agar terbaca di tablet */ !important;
    line-height: 1.65 !important;
    white-space: pre-wrap !important;
    word-break: normal !important;
    overflow-wrap: break-word !important;
    overflow-x: hidden !important;
}


/* Kurangi jarak bawaan Streamlit setelah kotak kode agar panel influencer tidak turun terlalu jauh. */
div[data-testid="stElementContainer"]:has(div[data-testid="stCode"]) {
    margin-bottom: 0 !important;
}

@media (max-width: 760px) {
    .rec-topic-stat-grid { grid-template-columns: 1fr; }
    .rec-topic-insight { grid-template-columns: 1fr; }
    .rec-topic-footer { align-items: flex-start; flex-direction: column; }
    .rec-copy-header { align-items: flex-start; flex-direction: column; }
}

@media (max-width: 720px) {
    .rec-hero { padding: 23px 20px; }
    .rec-context-card { align-items: flex-start; flex-direction: column; }
    .rec-status-row { justify-content: flex-start; }
    .rec-section-head { align-items: flex-start; flex-direction: column; }
}

/* Fase 20: ranking Top 5 dan playbook konten bisnis IndiBiz. */
.rec-top-influencer-badge {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    width: fit-content;
    margin: 0 0 10px;
    padding: 6px 9px;
    border: 1px solid rgba(229,57,53,.45);
    border-radius: 999px;
    color: #FFFFFF;
    background: linear-gradient(135deg, rgba(229,57,53,.92), rgba(183,28,28,.92));
    box-shadow: 0 8px 22px rgba(229,57,53,.20);
    font-size: 0.75rem /* FIX: minimum 12px agar terbaca di tablet */;
    font-weight: 900;
    letter-spacing: .04em;
    text-transform: uppercase;
}

.rec-business-stack {
    display: grid;
    gap: 14px;
    margin: 4px 0 16px;
}

.rec-business-panel {
    position: relative;
    overflow: hidden;
    padding: 18px;
    border: 1px solid var(--rec-border);
    border-radius: 18px;
    background:
        radial-gradient(circle at 95% 0%, var(--sentiment-soft), transparent 34%),
        linear-gradient(145deg, rgba(26,26,26,.98), rgba(13,13,13,.98));
    box-shadow: 0 16px 38px rgba(0,0,0,.23);
}

.rec-business-panel::before {
    content: '';
    position: absolute;
    top: 0;
    bottom: 0;
    left: 0;
    width: 4px;
    background: var(--sentiment-color);
}

.rec-business-head {
    display: flex;
    justify-content: space-between;
    align-items: flex-start;
    gap: 16px;
    margin-bottom: 13px;
}

.rec-business-head-left {
    display: flex;
    align-items: center;
    gap: 12px;
}

.rec-business-icon {
    display: grid;
    place-items: center;
    width: 42px;
    height: 42px;
    border: 1px solid color-mix(in srgb, var(--sentiment-color) 55%, transparent);
    border-radius: 14px;
    color: #FFFFFF;
    background: var(--sentiment-soft);
    font-size: 20px;
}

.rec-business-head span,
.rec-business-topic-label {
    display: block;
    color: var(--rec-text-secondary);
    font-size: 0.75rem /* FIX: minimum 12px agar terbaca di tablet */;
    font-weight: 900;
    letter-spacing: .08em;
    text-transform: uppercase;
}

.rec-business-head h3 {
    margin: 3px 0 0;
    color: var(--rec-text);
    font-family: 'Plus Jakarta Sans', sans-serif;
    font-size: 18px;
    line-height: 1.2;
}

.rec-business-topic {
    max-width: 360px;
    padding: 9px 11px;
    border: 1px solid rgba(255,255,255,.09);
    border-radius: 12px;
    background: rgba(255,255,255,.04);
    color: rgba(255,255,255,.82);
    font-size: 12px;
    font-weight: 700;
    line-height: 1.4;
}

.rec-business-ideas {
    display: grid;
    grid-template-columns: repeat(3, minmax(0, 1fr));
    gap: 11px;
}

.rec-business-idea {
    min-height: 150px;
    padding: 14px;
    border: 1px solid rgba(255,255,255,.09);
    border-radius: 15px;
    background: rgba(255,255,255,.035);
    transition: transform .22s ease, border-color .22s ease, background .22s ease;
}

.rec-business-idea:hover {
    transform: translateY(-3px);
    border-color: color-mix(in srgb, var(--sentiment-color) 58%, transparent);
    background: color-mix(in srgb, var(--sentiment-color) 8%, rgba(255,255,255,.035));
}

.rec-business-number {
    display: inline-flex;
    margin-bottom: 10px;
    color: var(--sentiment-color);
    font-family: 'Plus Jakarta Sans', sans-serif;
    font-size: 12px;
    font-weight: 900;
}

.rec-business-idea p {
    margin: 0;
    color: rgba(255,255,255,.80);
    font-size: 13px;
    font-weight: 650;
    line-height: 1.58;
}

.rec-business-keywords {
    display: flex;
    flex-wrap: wrap;
    gap: 7px;
    margin-top: 13px;
}

.rec-business-keyword {
    padding: 5px 8px;
    border: 1px solid rgba(255,255,255,.09);
    border-radius: 999px;
    color: rgba(255,255,255,.72);
    background: rgba(255,255,255,.04);
    font-size: 0.75rem /* FIX: minimum 12px agar terbaca di tablet */;
    font-weight: 800;
}

@media (max-width: 980px) {
    .rec-business-ideas { grid-template-columns: 1fr; }
    .rec-business-idea { min-height: auto; }
    .rec-business-head { flex-direction: column; }
    .rec-business-topic { max-width: none; width: 100%; }
}

</style>
"""


RECOMMENDATION_LIGHT_MODE_CSS = """
<style>
/* ========================================================================== */
/* LIGHT MODE KHUSUS HALAMAN REKOMENDASI                                     */
/* Hanya mengubah warna/surface. Struktur, spacing, ukuran, animasi, dan       */
/* urutan komponen tetap mengikuti baseline UI/UX yang sudah dikunci.          */
/* ========================================================================== */

:root {
    --rec-bg-main: #F5F7FA;
    --rec-bg-card: #FFFFFF;
    --rec-bg-soft: #F8FAFC;
    --rec-bg-input: #FFFFFF;
    --rec-border: #D9E0E8;
    --rec-text: #172033;
    --rec-text-secondary: #5F6B7A;
    --rec-text-muted: #7B8797;
}

/* -------------------------------------------------------------------------- */
/* HERO, KONTEKS, FILTER, DAN STATUS                                          */
/* -------------------------------------------------------------------------- */
.rec-hero {
    border-color: #D9E0E8;
    background:
        radial-gradient(circle at 88% 15%, rgba(229,57,53,.12), transparent 31%),
        linear-gradient(135deg, rgba(255,255,255,.99), rgba(247,249,252,.99));
    box-shadow: 0 16px 40px rgba(15,23,42,.08);
}

.rec-eyebrow {
    color: #C62828;
    background: rgba(229,57,53,.07);
}

.rec-context-card {
    border-color: #D9E0E8;
    background: #FFFFFF;
    box-shadow: 0 10px 28px rgba(15,23,42,.06);
}

.rec-status {
    border-color: #D9E0E8;
    color: #5F6B7A;
    background: #F8FAFC;
}

.rec-status.actual {
    color: #2E7D32;
    background: rgba(76,175,80,.08);
}

.rec-status.fallback {
    color: #B26A00;
    background: rgba(255,152,0,.09);
}

.rec-status.model {
    color: #C62828;
    background: rgba(229,57,53,.08);
}

.rec-filter-active-note {
    border-color: #DCE3EB;
    background: #F8FAFC;
    color: #5F6B7A;
}

.rec-filter-active-note strong {
    color: #172033;
}

.rec-filter-active-note span {
    color: #C62828;
}

.rec-service-note {
    color: #687386;
    background: linear-gradient(90deg, rgba(229,57,53,.07), rgba(229,57,53,0));
}

/* -------------------------------------------------------------------------- */
/* EMPTY STATE                                                                */
/* -------------------------------------------------------------------------- */
.rec-empty-state-panel {
    border-color: rgba(29,161,242,.22);
    background:
        radial-gradient(circle at 12% 12%, rgba(229,57,53,.12), transparent 30%),
        radial-gradient(circle at 86% 18%, rgba(29,161,242,.11), transparent 32%),
        linear-gradient(145deg, #FFFFFF, #F7F9FC);
    box-shadow: 0 18px 42px rgba(15,23,42,.10), inset 0 1px 0 rgba(255,255,255,.90);
}

.rec-empty-state-panel::before {
    background: linear-gradient(110deg, transparent 30%, rgba(255,255,255,.70) 48%, transparent 68%);
}

.rec-empty-state-kicker {
    color: #C62828;
}

.rec-empty-state-title {
    color: #172033;
}

.rec-empty-state-desc,
.rec-empty-mini-card p {
    color: #5F6B7A;
}

.rec-empty-mini-card {
    border-color: #DEE5ED;
    background: rgba(255,255,255,.74);
    box-shadow: inset 0 1px 0 rgba(255,255,255,.95);
}

.rec-empty-mini-card span {
    color: #9F2020;
}

/* -------------------------------------------------------------------------- */
/* AI CONTENT STUDIO                                                          */
/* -------------------------------------------------------------------------- */
.rec-ai-shell {
    border-color: #D9E0E8;
    background:
        radial-gradient(circle at 8% 12%, rgba(229,57,53,.13), transparent 30%),
        radial-gradient(circle at 92% 12%, rgba(29,161,242,.11), transparent 32%),
        radial-gradient(circle at 72% 100%, rgba(76,175,80,.08), transparent 30%),
        linear-gradient(145deg, #FFFFFF, #F7F9FC);
    box-shadow: 0 22px 54px rgba(15,23,42,.10), inset 0 1px 0 rgba(255,255,255,.94);
}

.rec-ai-shell:hover {
    border-color: #C8D1DD;
    box-shadow: 0 28px 62px rgba(15,23,42,.13), 0 0 0 1px rgba(229,57,53,.05), inset 0 1px 0 #FFFFFF;
}

.rec-ai-shell::before {
    background-image:
        linear-gradient(rgba(36,50,74,.035) 1px, transparent 1px),
        linear-gradient(90deg, rgba(36,50,74,.035) 1px, transparent 1px);
}

.rec-ai-eyebrow,
.rec-ai-result-kicker,
.rec-ai-content-title strong {
    color: #C62828;
}

.rec-ai-heading h2,
.rec-ai-result-heading,
.rec-ai-content-title,
.rec-ai-copy-heading {
    color: #172033;
}

.rec-ai-heading p,
.rec-ai-result-body,
.rec-ai-idea-row p,
.rec-ai-copy-text {
    color: #5F6B7A;
}

.rec-ai-feature-chip,
.rec-ai-source-pill,
.rec-ai-meta-chip {
    border-color: #DCE3EB;
    color: #586577;
    background: rgba(255,255,255,.78);
}

.rec-ai-feature-chip:hover,
.rec-ai-meta-chip:hover {
    color: #172033;
    border-color: #C7D0DC;
    background: #FFFFFF;
}

.rec-gemini-badge.online {
    color: #247A3A;
    background: rgba(76,175,80,.09);
}

.rec-gemini-badge.offline {
    color: #A86100;
    background: rgba(255,152,0,.10);
}

.rec-ai-refresh-notice {
    color: #246B35;
    background: linear-gradient(90deg, rgba(76,175,80,.11), rgba(76,175,80,.04));
}

.rec-ai-offline-note,
.rec-ai-fallback-note {
    color: #8B5900;
    background: linear-gradient(90deg, rgba(255,152,0,.12), rgba(255,152,0,.04));
}

.rec-ai-result {
    border-color: #DCE3EB;
    background:
        radial-gradient(circle at 95% 0%, rgba(139,92,246,.08), transparent 28%),
        linear-gradient(145deg, #FFFFFF, #F8FAFD);
    box-shadow: inset 0 1px 0 #FFFFFF, 0 16px 38px rgba(15,23,42,.09);
}

.rec-ai-result:hover {
    border-color: rgba(139,92,246,.28);
    box-shadow: inset 0 1px 0 #FFFFFF, 0 22px 48px rgba(15,23,42,.12);
}

.rec-ai-result-header {
    border-bottom-color: #E2E7EE;
    background: linear-gradient(90deg, rgba(139,92,246,.045), transparent);
}

.rec-ai-source-pill.live {
    color: #2E7D32;
}

.rec-ai-source-pill.fallback {
    color: #A86100;
}

.rec-ai-content-title {
    border-color: rgba(229,57,53,.18);
    background: linear-gradient(90deg, rgba(229,57,53,.075), rgba(139,92,246,.04));
}

.rec-ai-idea-row {
    border-color: #E0E6ED;
    background: #FAFBFD;
}

.rec-ai-idea-row:hover {
    border-color: rgba(29,161,242,.26);
    background: linear-gradient(90deg, rgba(29,161,242,.07), rgba(139,92,246,.025));
}

.rec-ai-idea-number {
    color: #1776AD;
    background: rgba(29,161,242,.08);
}

.rec-ai-result-meta {
    border-top-color: #E2E7EE;
}

/* -------------------------------------------------------------------------- */
/* STRATEGI PER SENTIMEN                                                      */
/* -------------------------------------------------------------------------- */
.rec-sentiment-strategy-card {
    background:
        radial-gradient(circle at 92% 8%, rgba(var(--sentiment-rgb), .15), transparent 28%),
        radial-gradient(circle at 6% 94%, rgba(var(--sentiment-rgb), .08), transparent 32%),
        linear-gradient(145deg, rgba(var(--sentiment-rgb), .055), #FFFFFF 44%, #F8FAFC);
    box-shadow: inset 0 1px 0 #FFFFFF, 0 16px 36px rgba(15,23,42,.09), 0 0 0 1px rgba(15,23,42,.015);
}

.rec-sentiment-strategy-card:hover,
.rec-sentiment-strategy-card:focus-visible {
    background:
        radial-gradient(circle at 92% 8%, rgba(var(--sentiment-rgb), .20), transparent 31%),
        radial-gradient(circle at 6% 94%, rgba(var(--sentiment-rgb), .11), transparent 35%),
        linear-gradient(145deg, rgba(var(--sentiment-rgb), .08), #FFFFFF 44%, #F7F9FC);
    box-shadow: inset 0 1px 0 #FFFFFF, 0 24px 54px rgba(15,23,42,.13), 0 0 30px rgba(var(--sentiment-rgb), .10);
}

.rec-sentiment-strategy-state,
.rec-sentiment-strategy-description,
.rec-sentiment-strategy-footer {
    color: #667285;
}

.rec-sentiment-strategy-card h3 {
    color: #172033;
}

.rec-sentiment-strategy-card ul {
    color: #37465A;
}

.rec-sentiment-strategy-card li {
    border-color: #E1E7EE;
    background: linear-gradient(110deg, #FAFBFD, rgba(var(--sentiment-rgb), .035));
}

.rec-sentiment-strategy-card li:hover {
    color: #172033;
    background: linear-gradient(110deg, rgba(var(--sentiment-rgb), .09), #FFFFFF);
    box-shadow: 0 9px 20px rgba(15,23,42,.08);
}


/* -------------------------------------------------------------------------- */
/* RADIO FILTER TIPE AKUN - LIGHT MODE                                       */
/* -------------------------------------------------------------------------- */
div[data-testid="stRadio"] > label p {
    color: #4B5565 !important;
}

[data-testid="stRadioOption"] {
    border-color: #DDE3EA !important;
    background: linear-gradient(145deg, #FFFFFF, #F8FAFC) !important;
    box-shadow: 0 6px 16px rgba(15,23,42,.045), inset 0 1px 0 #FFFFFF !important;
}

[data-testid="stRadioOption"]:hover {
    border-color: rgba(var(--radio-rgb), .40) !important;
    background: linear-gradient(145deg, rgba(var(--radio-rgb), .075), #FFFFFF) !important;
    box-shadow: 0 10px 22px rgba(15,23,42,.075), inset 0 1px 0 #FFFFFF !important;
}

[data-testid="stRadioOption"] > div > div:first-child > div:first-child {
    background: #FFFFFF !important;
    box-shadow: 0 0 0 4px rgba(var(--radio-rgb), .08) !important;
}

[data-testid="stRadioOption"] [data-testid="stMarkdownContainer"] p {
    color: #344054 !important;
}

[data-testid="stRadioOption"][data-selected] {
    border-color: rgba(var(--radio-rgb), .56) !important;
    background: linear-gradient(135deg, rgba(var(--radio-rgb), .14), rgba(255,255,255,.98)) !important;
    box-shadow: 0 10px 24px rgba(var(--radio-rgb), .11), inset 0 1px 0 rgba(255,255,255,.96) !important;
}

[data-testid="stRadioOption"][data-selected] > div > div:first-child > div:first-child {
    background: var(--radio-accent) !important;
    box-shadow: 0 0 0 5px rgba(var(--radio-rgb), .12), 0 5px 12px rgba(var(--radio-rgb), .18) !important;
}

[data-testid="stRadioOption"][data-selected] [data-testid="stMarkdownContainer"] p {
    color: var(--radio-accent) !important;
    font-weight: 850 !important;
}


/* -------------------------------------------------------------------------- */
/* KARTU INFLUENCER DAN DETAIL                                                */
/* -------------------------------------------------------------------------- */
.rec-influencer-card {
    border-color: #D9E0E8;
    background: linear-gradient(160deg, #FFFFFF, #F8FAFC);
    box-shadow: 0 10px 28px rgba(15,23,42,.07);
}

.rec-influencer-card.rec-placeholder-card {
    background: linear-gradient(160deg, #FAFBFD, #F3F6F9);
}

.rec-influencer-card.rec-placeholder-card:hover {
    border-color: #CDD5E0;
}

.rec-placeholder-icon {
    border-color: #D9E0E8;
    color: #7B8797;
    background: #F4F6F9;
}

.rec-placeholder-title {
    color: #344054;
}

.rec-placeholder-text {
    color: #7B8797;
}

.rec-influencer-card:hover {
    box-shadow: 0 15px 34px rgba(15,23,42,.11), 0 0 22px rgba(229,57,53,.06);
}

.rec-avatar {
    border-color: rgba(255,255,255,.72);
    box-shadow: 0 8px 18px rgba(15,23,42,.14);
}

.rec-platform-badge,
.rec-mini-badge {
    color: var(--platform-color, #C62828);
    background: color-mix(in srgb, var(--platform-color, #E53935) 9%, #FFFFFF);
}

.rec-username,
.rec-mini-value,
.rec-content-preview-title,
.rec-detail-block-title {
    color: #172033;
}

.rec-mini-metric,
.rec-content-preview,
.rec-detail-block {
    border-color: #E0E6ED;
    background: #F8FAFC;
}

.rec-mini-label,
.rec-content-preview-meta,
.rec-detail-content-meta {
    color: #7B8797;
}

.rec-content-list li {
    color: #4B586B;
}

.rec-content-scroll {
    scrollbar-color: #E53935 #E7ECF2;
}

.rec-content-scroll::-webkit-scrollbar-track {
    border-color: #DDE4EC;
    background: #E7ECF2;
}

.rec-content-scroll::-webkit-scrollbar-thumb {
    border-color: #E7ECF2;
}

.rec-detail-content-list::-webkit-scrollbar-track {
    background: #E7ECF2;
}

.rec-detail-content-list::-webkit-scrollbar-thumb {
    background: #AAB4C2;
}

.rec-detail-content-item,
.rec-detail-strategy-card {
    border-color: #E1E7EE;
    background: #FFFFFF;
}

/* FIX LIGHT THEME: selector dibuat lebih spesifik daripada .rec-detail-panel p.
   Tanpa ini, warna #C3C3C3 dari aturan dark/base tetap menang pada elemen <p>. */
.rec-detail-panel .rec-detail-content-text,
.rec-detail-panel .rec-detail-recommendation {
    color: #445166 !important;
    -webkit-text-fill-color: #445166 !important;
}

.rec-detail-note {
    color: #5F6B7A;
    background: rgba(255,152,0,.08);
}

.rec-detail-panel {
    border-color: color-mix(in srgb, var(--detail-accent, #E53935) 38%, #D9E0E8);
    background:
        radial-gradient(circle at 7% 0%, color-mix(in srgb, var(--detail-accent, #E53935) 9%, transparent), transparent 28%),
        radial-gradient(circle at 95% 100%, color-mix(in srgb, var(--detail-accent, #E53935) 6%, transparent), transparent 31%),
        linear-gradient(145deg, #FFFFFF, #F7F9FC);
    box-shadow: 0 20px 52px rgba(15,23,42,.11), inset 0 1px 0 #FFFFFF;
}

.rec-detail-panel::before {
    background: linear-gradient(90deg, transparent, var(--detail-accent), #FFFFFF, var(--detail-accent), transparent);
}

.rec-detail-panel h4,
.rec-detail-stat-value,
.rec-detail-block-title,
.rec-detail-strategy-title,
.rec-detail-basis-row strong {
    color: #172033;
}

.rec-detail-panel h4 strong {
    color: color-mix(in srgb, var(--detail-accent) 82%, #172033);
}

.rec-detail-subtitle,
.rec-detail-stat-label,
.rec-detail-stat-note,
.rec-detail-topic-label,
.rec-detail-basis-row {
    color: #758195;
}

.rec-detail-live-badge {
    border-color: color-mix(in srgb, var(--detail-accent) 28%, #D9E0E8);
    color: #344054;
    background: rgba(255,255,255,.78);
}

.rec-detail-stat-card {
    border-color: #E1E7EE;
    background: linear-gradient(145deg, rgba(255,255,255,.92), transparent 44%), #F8FAFC;
}

.rec-detail-stat-card:hover {
    background: linear-gradient(145deg, color-mix(in srgb, var(--detail-accent) 5%, #FFFFFF), #FFFFFF);
    box-shadow: 0 12px 26px rgba(15,23,42,.09);
}

.rec-detail-topic-row {
    border-color: #E1E7EE;
    background: #F8FAFC;
}

.rec-detail-topic-chip {
    color: #344054;
    background: color-mix(in srgb, var(--detail-accent) 7%, #FFFFFF);
}

.rec-detail-topic-chip:hover {
    color: #172033;
}

.rec-detail-block {
    background: linear-gradient(150deg, rgba(255,255,255,.80), transparent 46%), #F8FAFC;
}

.rec-detail-block:hover,
.rec-detail-block:focus-visible {
    box-shadow: 0 16px 32px rgba(15,23,42,.09);
}

.rec-detail-count-badge {
    border-color: #D9E0E8;
    color: #667285;
    background: #FFFFFF;
}

.rec-detail-content-list {
    scrollbar-color: var(--detail-accent) #E7ECF2;
}

.rec-detail-content-item:hover,
.rec-detail-strategy-card:hover {
    background: color-mix(in srgb, var(--detail-accent) 5%, #FFFFFF);
}

.rec-detail-basis-row {
    background: color-mix(in srgb, var(--detail-accent) 4%, #FFFFFF);
}

/* -------------------------------------------------------------------------- */
/* RINGKASAN TOPIK DAN PLAYBOOK                                               */
/* -------------------------------------------------------------------------- */
.rec-topic-summary {
    border-color: #E0E6ED;
    background: #F8FAFC;
}

.rec-topic-meta {
    color: #455267;
}

.rec-progress {
    background: #E3E8EF;
}

.rec-platform-label {
    color: #172033;
}

.rec-influencer-pill {
    color: #B42318;
    background: rgba(229,57,53,.07);
}

.rec-topic-pill {
    color: #344054;
    background: color-mix(in srgb, var(--topic-color, #E53935) 8%, #FFFFFF);
    box-shadow: inset 0 0 0 1px rgba(15,23,42,.02);
}

.rec-topic-hero {
    border-color: color-mix(in srgb, var(--topic-color, #E53935) 28%, #D9E0E8);
    background:
        radial-gradient(circle at top right, color-mix(in srgb, var(--topic-color, #E53935) 10%, transparent), transparent 34%),
        linear-gradient(145deg, #FFFFFF, #F8FAFC);
    box-shadow: 0 14px 34px rgba(15,23,42,.08);
}

.rec-topic-icon {
    box-shadow: 0 8px 20px rgba(15,23,42,.10), inset 0 0 0 1px rgba(255,255,255,.74);
}

.rec-topic-hero h3,
.rec-topic-stat-value,
.rec-copy-header strong,
.rec-platform-card-head strong,
.rec-topic-footer-label span {
    color: #172033;
}

.rec-topic-stat-card {
    border-color: #E1E7EE;
    background: linear-gradient(145deg, rgba(255,255,255,.86), transparent 42%), #F8FAFC;
}

.rec-topic-stat-label,
.rec-topic-stat-unit,
.rec-topic-stat-note,
.rec-topic-footer-label small,
.rec-platform-card-head span {
    color: #748094;
}

.rec-topic-stat-icon {
    color: #172033;
}

.rec-topic-sentiment-pill {
    color: color-mix(in srgb, var(--sentiment-color, #667085) 82%, #172033);
    background: color-mix(in srgb, var(--sentiment-color, #9E9E9E) 9%, #FFFFFF);
}

.rec-topic-progress-row {
    border-color: #E1E7EE;
    background: #F8FAFC;
}

.rec-topic-progress-info {
    color: #455267;
}

.rec-topic-insight {
    border-color: color-mix(in srgb, var(--topic-color, #E53935) 22%, #D9E0E8);
    background: color-mix(in srgb, var(--topic-color, #E53935) 7%, #FFFFFF);
}

.rec-topic-insight p {
    color: #455267;
}

.rec-copy-header {
    border-color: color-mix(in srgb, var(--topic-color, #E53935) 24%, #D9E0E8);
    background: linear-gradient(135deg, color-mix(in srgb, var(--topic-color, #E53935) 7%, #FFFFFF), #F8FAFC);
}

.rec-copy-header em {
    color: #344054;
    background: #FFFFFF;
}

.rec-platform-card-head {
    border-color: color-mix(in srgb, var(--platform-color, #E53935) 28%, #D9E0E8);
    background: linear-gradient(135deg, color-mix(in srgb, var(--platform-color, #E53935) 9%, #FFFFFF), #F8FAFC);
}

.rec-topic-footer {
    border-color: color-mix(in srgb, var(--topic-color, #E53935) 23%, #D9E0E8);
    background: #F8FAFC;
}

/* -------------------------------------------------------------------------- */
/* MATRIKS INFLUENCER × TOPIK                                                 */
/* -------------------------------------------------------------------------- */
.rec-matrix-intro {
    border-color: rgba(229,57,53,.22);
    background:
        radial-gradient(circle at top right, rgba(229,57,53,.09), transparent 32%),
        linear-gradient(135deg, #FFFFFF, #F8FAFC);
    box-shadow: 0 14px 34px rgba(15,23,42,.08);
}

.rec-matrix-intro strong {
    color: #172033;
}

.rec-matrix-intro p {
    color: #667285;
}

.rec-matrix-insight-card {
    background:
        radial-gradient(circle at 88% 14%, rgba(var(--rec-card-rgb, 229,57,53), .18), transparent 29%),
        radial-gradient(circle at 12% 110%, rgba(var(--rec-card-rgb, 229,57,53), .09), transparent 34%),
        linear-gradient(145deg, rgba(var(--rec-card-rgb, 229,57,53), .075), #FFFFFF 48%, #F8FAFC);
    box-shadow: 0 17px 38px rgba(15,23,42,.09), 0 0 24px rgba(var(--rec-card-rgb, 229,57,53), .08), inset 0 1px 0 #FFFFFF;
}

.rec-matrix-insight-card:hover {
    box-shadow: 0 22px 48px rgba(15,23,42,.13), 0 0 32px rgba(var(--rec-card-rgb, 229,57,53), .13), inset 0 1px 0 #FFFFFF;
}

.rec-matrix-card-icon {
    background: linear-gradient(145deg, rgba(var(--rec-card-rgb, 229,57,53), .18), rgba(255,255,255,.80));
    color: #172033;
}

.rec-matrix-insight-card span,
.rec-matrix-insight-card small {
    color: #657185;
}

.rec-matrix-insight-card strong {
    color: #172033;
    text-shadow: none;
}

.rec-matrix-rank-card {
    border-color: color-mix(in srgb, var(--platform-color, #E53935) 26%, #D9E0E8);
    background:
        radial-gradient(circle at top right, color-mix(in srgb, var(--platform-color, #E53935) 10%, transparent), transparent 35%),
        #FFFFFF;
}

.rec-matrix-rank-number {
    color: #172033;
    background: color-mix(in srgb, var(--platform-color, #E53935) 13%, #FFFFFF);
}

.rec-matrix-rank-main span,
.rec-matrix-rank-score {
    color: #172033;
}

.rec-matrix-rank-main small {
    color: #4F5C70;
    background: color-mix(in srgb, var(--platform-color, #E53935) 8%, #FFFFFF);
}

.rec-matrix-rank-score em {
    color: #7B8797;
}

.rec-matrix-empty,
.rec-matrix-table-empty-state {
    color: #8B5900;
    background: rgba(255,152,0,.09);
}

div[data-testid="stPlotlyChart"] {
    border-color: #DCE3EB;
    background:
        radial-gradient(circle at top right, rgba(229,57,53,.055), transparent 30%),
        linear-gradient(145deg, #FFFFFF, #F8FAFC);
    box-shadow: 0 14px 34px rgba(15,23,42,.08);
}

.rec-matrix-table-hero {
    border-color: rgba(29,161,242,.22);
    background:
        radial-gradient(circle at 92% 0%, rgba(29,161,242,.10), transparent 32%),
        radial-gradient(circle at 8% 100%, rgba(229,57,53,.08), transparent 30%),
        linear-gradient(145deg, #FFFFFF, #F8FAFC);
    box-shadow: 0 14px 36px rgba(15,23,42,.09), inset 0 1px 0 #FFFFFF;
}

.rec-matrix-table-hero strong {
    color: #172033;
}

.rec-matrix-table-hero p {
    color: #667285;
}

.rec-matrix-table-stat {
    border-color: color-mix(in srgb, var(--stat-color) 30%, #D9E0E8);
    background:
        radial-gradient(circle at 86% 14%, color-mix(in srgb, var(--stat-color) 19%, transparent), transparent 32%),
        radial-gradient(circle at 0% 100%, color-mix(in srgb, var(--stat-color-2) 12%, transparent), transparent 38%),
        linear-gradient(145deg, #FFFFFF, #F8FAFC);
    box-shadow: 0 16px 34px rgba(15,23,42,.09), 0 0 20px color-mix(in srgb, var(--stat-color) 8%, transparent), inset 0 1px 0 #FFFFFF;
}

.rec-matrix-table-stat:hover {
    border-color: color-mix(in srgb, var(--stat-color) 52%, #D9E0E8);
    box-shadow: 0 20px 44px rgba(15,23,42,.12), 0 0 26px color-mix(in srgb, var(--stat-color) 14%, transparent), inset 0 1px 0 #FFFFFF;
}

.rec-matrix-table-stat span {
    color: #667285;
}

.rec-matrix-table-stat-icon {
    color: #172033;
    background: linear-gradient(145deg, color-mix(in srgb, var(--stat-color) 20%, #FFFFFF), #FFFFFF);
}

.rec-matrix-table-stat strong {
    color: #172033;
    text-shadow: none;
}

.rec-matrix-table-stat small {
    color: color-mix(in srgb, var(--stat-color) 70%, #455267);
}

.rec-matrix-table-detail {
    border-color: rgba(229,57,53,.20);
    background:
        radial-gradient(circle at 100% 0%, rgba(229,57,53,.09), transparent 30%),
        radial-gradient(circle at 0% 100%, rgba(255,152,0,.055), transparent 28%),
        linear-gradient(145deg, #FFFFFF, #F8FAFC);
    box-shadow: 0 14px 34px rgba(15,23,42,.08);
}

.rec-matrix-table-detail::after {
    background: linear-gradient(90deg, transparent, rgba(71,85,105,.18), transparent);
}

.rec-matrix-table-detail-title strong {
    color: #172033;
}

.rec-matrix-table-detail-title span {
    color: #176B96;
    background: rgba(29,161,242,.07);
}

.rec-matrix-table-score-pill {
    border-color: #DDE4EC;
    color: #5F6B7A;
    background: #F8FAFC;
}

.rec-matrix-table-score-pill:hover {
    box-shadow: 0 8px 18px rgba(15,23,42,.09);
}

.rec-matrix-table-score-pill b {
    color: #172033;
}

.rec-matrix-table-apply-note {
    color: #5F6B7A;
    background: rgba(29,161,242,.055);
}

.rec-matrix-table-fixed-limit {
    border-color: rgba(29,161,242,.22);
    background:
        radial-gradient(circle at 92% 20%, rgba(29,161,242,.10), transparent 30%),
        linear-gradient(135deg, #F8FAFC, #FFFFFF);
    box-shadow: inset 0 1px 0 #FFFFFF, 0 12px 28px rgba(15,23,42,.08);
}

.rec-matrix-table-fixed-limit span,
.rec-matrix-table-fixed-limit small {
    color: #667285;
}

.rec-matrix-table-fixed-limit strong {
    color: #172033;
}

div[data-testid="stDataFrame"] {
    box-shadow: 0 14px 34px rgba(15,23,42,.08), 0 0 22px rgba(29,161,242,.05) !important;
}

div[data-testid="stDownloadButton"] button {
    color: #23643B !important;
    background: linear-gradient(135deg, rgba(53,217,139,.11), rgba(29,161,242,.055)) !important;
}

/* -------------------------------------------------------------------------- */
/* RINGKASAN STRATEGIS                                                        */
/* -------------------------------------------------------------------------- */
.rec-strategy-card {
    border-color: #D9E0E8;
    background: linear-gradient(140deg, #FFFFFF, #F8FAFC);
    box-shadow: 0 12px 30px rgba(15,23,42,.07);
}

.rec-strategy-item {
    border-bottom-color: #E2E7EE;
}

.rec-strategy-text {
    color: #4B586B;
}

.rec-strategy-text strong {
    color: #172033;
}

/* -------------------------------------------------------------------------- */
/* PLAYBOOK BISNIS INDIBIZ                                                    */
/* -------------------------------------------------------------------------- */
.rec-business-panel {
    border-color: #D9E0E8;
    background:
        radial-gradient(circle at 95% 0%, var(--sentiment-soft), transparent 34%),
        linear-gradient(145deg, #FFFFFF, #F8FAFC);
    box-shadow: 0 14px 34px rgba(15,23,42,.08);
}

.rec-business-topic,
.rec-business-idea,
.rec-business-keyword {
    border-color: #E0E6ED;
    background: rgba(255,255,255,.82);
}

.rec-business-topic {
    color: #455267;
}

.rec-business-idea:hover {
    background: color-mix(in srgb, var(--sentiment-color) 6%, #FFFFFF);
}

.rec-business-idea p {
    color: #455267;
}

.rec-business-keyword {
    color: #667285;
}

/* -------------------------------------------------------------------------- */
/* WIDGET STREAMLIT KHUSUS HALAMAN REKOMENDASI                               */
/* -------------------------------------------------------------------------- */
div[data-testid="stSelectbox"] > label {
    color: #273548 !important;
}

div[data-testid="stSelectbox"] div[data-baseweb="select"] > div {
    border-color: #D5DCE5 !important;
    background: #FFFFFF !important;
    color: #273548 !important;
}

div[data-testid="stSelectbox"] div[data-baseweb="select"] * {
    color: #273548 !important;
}

div[data-testid="stForm"] div[data-testid="stFormSubmitButton"] button[kind="secondary"],
div[data-testid="stButton"] button[kind="secondary"] {
    border-color: #E53935 !important;
    color: #B42318 !important;
    background: linear-gradient(145deg, #FFFFFF, #F6F8FB) !important;
    box-shadow: 0 8px 20px rgba(15,23,42,.07) !important;
}

div[data-testid="stForm"] div[data-testid="stFormSubmitButton"] button[kind="secondary"]:hover,
div[data-testid="stButton"] button[kind="secondary"]:hover {
    border-color: #FF5252 !important;
    color: #9F1D14 !important;
    background: #FFF4F3 !important;
    box-shadow: 0 11px 24px rgba(229,57,53,.10) !important;
}


/* -------------------------------------------------------------------------- */
/* FILTER MATRIKS UTAMA — LIGHT THEME                                         */
/* Tujuan: satu ritme tinggi, tombol presisi, dan visual lebih tenang.         */
/* -------------------------------------------------------------------------- */
div[data-testid="stForm"]:has(.rec-matrix-main-form-marker) {
    margin: 4px 0 16px !important;
    padding: 16px 18px 18px !important;
    border: 1px solid #E2E8F0 !important;
    border-radius: 18px !important;
    background: linear-gradient(180deg, #FFFFFF 0%, #FAFBFD 100%) !important;
    box-shadow: 0 12px 30px rgba(15,23,42,.065) !important;
    animation: none !important;
}

.rec-matrix-main-form-marker {
    display: none !important;
}

div[data-testid="stForm"]:has(.rec-matrix-main-form-marker) div[data-testid="stHorizontalBlock"] {
    align-items: flex-end !important;
    gap: 16px !important;
}

div[data-testid="stForm"]:has(.rec-matrix-main-form-marker) label {
    margin-bottom: 7px !important;
}

div[data-testid="stForm"]:has(.rec-matrix-main-form-marker) label p {
    color: #344054 !important;
    font-size: 14px !important;
    font-weight: 760 !important;
    line-height: 1.25 !important;
    letter-spacing: -.01em !important;
}

div[data-testid="stForm"]:has(.rec-matrix-main-form-marker) div[data-testid="stSelectbox"] div[data-baseweb="select"] > div,
div[data-testid="stForm"]:has(.rec-matrix-main-form-marker) div[data-testid="stMultiSelect"] div[data-baseweb="select"] > div {
    min-height: 54px !important;
    border: 1px solid #D9E1EA !important;
    border-radius: 14px !important;
    background: #FFFFFF !important;
    box-shadow: 0 4px 12px rgba(15,23,42,.035) !important;
    transition: border-color .16s ease, box-shadow .16s ease !important;
}

div[data-testid="stForm"]:has(.rec-matrix-main-form-marker) div[data-testid="stSelectbox"] div[data-baseweb="select"] > div:hover,
div[data-testid="stForm"]:has(.rec-matrix-main-form-marker) div[data-testid="stMultiSelect"] div[data-baseweb="select"] > div:hover {
    border-color: #BCC8D6 !important;
    box-shadow: 0 5px 14px rgba(15,23,42,.055) !important;
}

/* Pilihan platform selalu satu baris. Jika viewport sempit, area tag boleh digeser
   horizontal tanpa membuat tinggi multiselect bertambah. */
div[data-testid="stForm"]:has(.rec-matrix-main-form-marker) div[data-testid="stMultiSelect"] div[data-baseweb="select"] > div {
    height: 54px !important;
    max-height: 54px !important;
    flex-wrap: nowrap !important;
    overflow: hidden !important;
}

div[data-testid="stForm"]:has(.rec-matrix-main-form-marker) div[data-testid="stMultiSelect"] div[data-baseweb="select"] > div > div:first-child {
    display: flex !important;
    flex: 1 1 auto !important;
    align-items: center !important;
    flex-wrap: nowrap !important;
    gap: 6px !important;
    min-width: 0 !important;
    max-width: 100% !important;
    overflow-x: auto !important;
    overflow-y: hidden !important;
    scrollbar-width: none !important;
    overscroll-behavior-x: contain !important;
}

div[data-testid="stForm"]:has(.rec-matrix-main-form-marker) div[data-testid="stMultiSelect"] div[data-baseweb="select"] > div > div:first-child::-webkit-scrollbar {
    display: none !important;
}

div[data-testid="stForm"]:has(.rec-matrix-main-form-marker) div[data-testid="stMultiSelect"] span[data-baseweb="tag"] {
    flex: 0 0 auto !important;
    min-height: 34px !important;
    height: 34px !important;
    max-width: none !important;
    margin: 0 !important;
    border-radius: 9px !important;
    border: 1px solid rgba(229,57,53,.14) !important;
    background: #EF3E3A !important;
    box-shadow: none !important;
    white-space: nowrap !important;
}

div[data-testid="stForm"]:has(.rec-matrix-main-form-marker) div[data-testid="stMultiSelect"] span[data-baseweb="tag"] * {
    color: #FFFFFF !important;
    -webkit-text-fill-color: #FFFFFF !important;
    font-size: 14px !important;
    font-weight: 750 !important;
    white-space: nowrap !important;
}

div[data-testid="stForm"]:has(.rec-matrix-main-form-marker) div[data-testid="stSlider"] {
    padding-bottom: 5px !important;
}

div[data-testid="stForm"]:has(.rec-matrix-main-form-marker) div[data-testid="stSlider"] [role="slider"] {
    border-color: #E53935 !important;
    background: #E53935 !important;
    box-shadow: 0 0 0 4px rgba(229,57,53,.10) !important;
}

div[data-testid="stForm"]:has(.rec-matrix-main-form-marker) .rec-matrix-filter-btn {
    min-height: 54px !important;
    height: 54px !important;
    padding: 0 18px !important;
    border-radius: 14px !important;
    font-size: 15px !important;
    font-weight: 800 !important;
    letter-spacing: -.01em !important;
    line-height: 1 !important;
    transform: none !important;
    filter: none !important;
    transition: border-color .16s ease, background .16s ease, box-shadow .16s ease !important;
}

div[data-testid="stForm"]:has(.rec-matrix-main-form-marker) .rec-matrix-btn-reset {
    border: 1.5px solid #EF4444 !important;
    color: #B42318 !important;
    -webkit-text-fill-color: #B42318 !important;
    background: #FFFFFF !important;
    box-shadow: 0 6px 16px rgba(15,23,42,.055) !important;
    opacity: 1 !important;
}

/* Streamlit dapat memberi warna pada elemen <p>/<span> di dalam button.
   Paksa seluruh isi Reset tetap terbaca, termasuk ketika tombol sedang inert. */
div[data-testid="stForm"]:has(.rec-matrix-main-form-marker) .rec-matrix-btn-reset *,
div[data-testid="stForm"]:has(.rec-matrix-main-form-marker) .rec-matrix-btn-reset.rec-matrix-btn-inert * {
    color: #B42318 !important;
    -webkit-text-fill-color: #B42318 !important;
    opacity: 1 !important;
}

div[data-testid="stForm"]:has(.rec-matrix-main-form-marker) .rec-matrix-btn-reset:not(.rec-matrix-btn-inert):hover {
    border-color: #DC2626 !important;
    color: #991B1B !important;
    background: #FFF7F6 !important;
    box-shadow: 0 8px 19px rgba(229,57,53,.10) !important;
    transform: translateY(-1px) !important;
}

div[data-testid="stForm"]:has(.rec-matrix-main-form-marker) .rec-matrix-btn-apply {
    border: 1px solid #E23C3A !important;
    color: #FFFFFF !important;
    background: linear-gradient(135deg, #EF4444 0%, #E53935 58%, #D9468F 100%) !important;
    box-shadow: 0 9px 22px rgba(229,57,53,.18) !important;
}

div[data-testid="stForm"]:has(.rec-matrix-main-form-marker) .rec-matrix-btn-apply:not(.rec-matrix-btn-inert):hover {
    background: linear-gradient(135deg, #F04A47 0%, #E53935 60%, #CE3E86 100%) !important;
    box-shadow: 0 11px 25px rgba(229,57,53,.24) !important;
    transform: translateY(-1px) !important;
}

div[data-testid="stForm"]:has(.rec-matrix-main-form-marker) .rec-matrix-btn-inert,
div[data-testid="stForm"]:has(.rec-matrix-main-form-marker) .rec-matrix-btn-inert:hover {
    cursor: default !important;
    transform: none !important;
    filter: none !important;
}

@media (max-width: 1050px) {
    div[data-testid="stForm"]:has(.rec-matrix-main-form-marker) {
        padding: 14px !important;
    }

    div[data-testid="stForm"]:has(.rec-matrix-main-form-marker) div[data-testid="stHorizontalBlock"] {
        gap: 12px !important;
    }
}

div[data-testid="stExpander"] {
    border-color: #DCE3EB !important;
    background: linear-gradient(145deg, #FFFFFF, #F8FAFC) !important;
    box-shadow: 0 12px 28px rgba(15,23,42,.08) !important;
}

div[data-testid="stExpander"]:hover {
    border-color: #CBD4DF !important;
    box-shadow: 0 16px 34px rgba(15,23,42,.10) !important;
}

div[data-testid="stExpander"] summary {
    color: #273548 !important;
    background: linear-gradient(90deg, rgba(139,92,246,.055), rgba(29,161,242,.025)) !important;
}

div[data-testid="stExpander"] summary:hover {
    color: #172033 !important;
    background: linear-gradient(90deg, rgba(139,92,246,.09), rgba(29,161,242,.04)) !important;
}

div[data-testid="stCode"] {
    border-color: #DCE3EB !important;
    background: #F7F9FC !important;
    box-shadow: inset 0 1px 0 #FFFFFF, 0 10px 24px rgba(15,23,42,.06) !important;
}

div[data-testid="stCode"] pre {
    scrollbar-color: rgba(229,57,53,.75) #E7ECF2 !important;
}

div[data-testid="stCode"] pre::-webkit-scrollbar-track {
    background: #E7ECF2 !important;
}

div[data-testid="stCode"] code {
    color: #273548 !important;
}

/* Teks caption Streamlit di akhir halaman tetap terbaca pada latar terang. */
.rec-page + div,
.rec-page ~ div {
    color: inherit;
}

</style>
"""

# -----------------------------------------------------------------------------
# UTILITAS DATA
# -----------------------------------------------------------------------------


def _normalisasi_sentimen(value: Any) -> str:
    """Normalisasi label sentimen menjadi positive, neutral, atau negative."""
    text = str(value or "").strip().lower().lstrip("'")
    mapping = {
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
    return mapping.get(text, "neutral")


def _is_brand_account(username: Any) -> bool:
    """Kembalikan True untuk akun brand, layanan resmi, atau akun otomatis."""
    normalized = str(username or "").strip().lower().lstrip("@")
    compact = re.sub(r"[^a-z0-9]+", "", normalized)
    if not normalized or normalized == "nan":
        return True
    if normalized in NON_INFLUENCER_ACCOUNTS or compact in NON_INFLUENCER_ACCOUNTS:
        return True
    return any(
        re.sub(r"[^a-z0-9]+", "", keyword.lower()) in compact
        for keyword in BRAND_KEYWORDS
    )


def _format_number(value: Any) -> str:
    """Format angka dengan pemisah ribuan gaya Indonesia."""
    try:
        number = int(float(value))
        return f"{number:,}".replace(",", ".")
    except (TypeError, ValueError):
        return "0"


def _safe_username(value: Any) -> str:
    """Bersihkan username untuk tampilan dan pembuatan key widget."""
    username = str(value or "akun_tidak_diketahui").strip().lstrip("@")
    return username or "akun_tidak_diketahui"


def _safe_key(value: Any) -> str:
    """Buat key Streamlit yang hanya berisi huruf, angka, dan underscore."""
    return re.sub(r"[^a-zA-Z0-9_]+", "_", str(value or "item"))


def _classify_account_type(username: Any, account_name: Any = "") -> str:
    """Klasifikasikan akun menjadi media atau influencer secara otomatis."""
    try:
        username_text = str(username or "").strip().lower().lstrip("@")
        account_name_text = str(account_name or "").strip().lower()
        normalized_username = re.sub(r"[^a-z0-9]+", "", username_text)
        normalized_name = re.sub(r"[^a-z0-9]+", "", account_name_text)

        manual_media = {
            re.sub(r"[^a-z0-9]+", "", item.lower().lstrip("@"))
            for item in MEDIA_ACCOUNT_MANUAL
        }
        manual_influencer = {
            re.sub(r"[^a-z0-9]+", "", item.lower().lstrip("@"))
            for item in INFLUENCER_ACCOUNT_MANUAL
        }

        if normalized_username in manual_influencer:
            return "influencer"
        if normalized_username in manual_media:
            return "media"

        searchable = f"{username_text} {account_name_text}"
        compact_searchable = f"{normalized_username} {normalized_name}"
        is_media = any(
            keyword in searchable or keyword in compact_searchable
            for keyword in MEDIA_ACCOUNT_KEYWORDS
        )
        return "media" if is_media else "influencer"
    except Exception as error:
        st.error(
            "Tipe akun belum dapat diklasifikasikan. "
            f"Detail: {type(error).__name__}."
        )
        return "influencer"


def _account_type_label(value: Any) -> str:
    """Ubah nilai tipe akun menjadi badge Bahasa Indonesia."""
    try:
        normalized = str(value or "influencer").strip().lower()
        return ACCOUNT_TYPE_LABELS.get(normalized, ACCOUNT_TYPE_LABELS["influencer"])
    except Exception as error:
        st.error(
            "Label tipe akun belum dapat disiapkan. "
            f"Detail: {type(error).__name__}."
        )
        return ACCOUNT_TYPE_LABELS["influencer"]


def _add_account_type_column(influencers: pd.DataFrame) -> pd.DataFrame:
    """Tambahkan kolom tipe_akun tanpa mengubah urutan kandidat influencer."""
    try:
        if influencers is None:
            return pd.DataFrame(columns=["tipe_akun"])

        result = influencers.copy()
        if result.empty:
            if "tipe_akun" not in result.columns:
                result["tipe_akun"] = pd.Series(dtype="object")
            return result

        name_column = next(
            (
                column
                for column in ("name", "nama", "display_name", "fullname", "full_name")
                if column in result.columns
            ),
            None,
        )
        account_names = (
            result[name_column]
            if name_column is not None
            else pd.Series("", index=result.index, dtype="object")
        )
        result["tipe_akun"] = [
            _classify_account_type(username, account_name)
            for username, account_name in zip(
                result.get("username", pd.Series("", index=result.index)),
                account_names,
            )
        ]
        return result
    except Exception as error:
        st.error(
            "Kolom tipe akun belum dapat ditambahkan. "
            f"Detail: {type(error).__name__}."
        )
        fallback = influencers.copy() if isinstance(influencers, pd.DataFrame) else pd.DataFrame()
        fallback["tipe_akun"] = "influencer"
        return fallback


def _filter_influencers_by_account_type(
    influencers: pd.DataFrame,
    selected_type: str,
) -> pd.DataFrame:
    """Filter rekomendasi berdasarkan pilihan Semua, Influencer, atau Akun Media."""
    try:
        if influencers is None or influencers.empty:
            return pd.DataFrame(columns=getattr(influencers, "columns", None))

        selection_map = {
            "Influencer": "influencer",
            "Akun Media": "media",
        }
        normalized_type = selection_map.get(str(selected_type).strip())
        if normalized_type is None:
            return influencers.copy()

        filtered = influencers[
            influencers["tipe_akun"].astype(str).str.lower().eq(normalized_type)
        ].copy()
        if filtered.empty:
            return filtered

        filtered = filtered.sort_values(
            ["recommendation_score", "degree_centrality", "followers"],
            ascending=[False, False, False],
        ).reset_index(drop=True)
        filtered["recommendation_rank"] = range(1, len(filtered) + 1)
        return filtered
    except Exception as error:
        st.error(
            "Influencer belum dapat disaring berdasarkan tipe akun. "
            f"Detail: {type(error).__name__}."
        )
        return influencers.iloc[0:0].copy()


def _select_balanced_platform_candidates(
    influencers: pd.DataFrame,
    per_platform_limit: int = PLATFORM_CARD_TARGET,
) -> pd.DataFrame:
    """Pilih kandidat lintas platform dengan target utama 3 + 3 + 3.

    Prioritas pertama tetap mengambil kandidat terbaik dari Twitter/X, Instagram,
    dan TikTok secara seimbang. Jika salah satu platform memang tidak mempunyai
    cukup akun untuk tipe yang sedang dipilih, slot kosong diisi kandidat terbaik
    berikutnya dari platform lain. Dengan cara ini grid tetap terisi tanpa membuat
    akun dummy atau mengubah tipe akun hanya demi memenuhi kuota visual.
    """
    try:
        if influencers is None or influencers.empty:
            return pd.DataFrame(columns=getattr(influencers, "columns", None))

        if "platform" not in influencers.columns:
            return influencers.iloc[0:0].copy()

        work = influencers.copy()
        work["platform"] = (
            work["platform"]
            .fillna("")
            .astype(str)
            .str.lower()
            .str.strip()
            .replace({
                "x": "twitter",
                "twitter/x": "twitter",
                "twitter (x)": "twitter",
                "ig": "instagram",
            })
        )

        sort_columns = [
            column
            for column in (
                "recommendation_score",
                "degree_centrality",
                "followers",
                "relevant_content_count",
                "content_count",
            )
            if column in work.columns
        ]
        if sort_columns:
            work = work.sort_values(
                sort_columns,
                ascending=[False] * len(sort_columns),
            )

        limit = max(int(per_platform_limit), 1)
        target_total = limit * len(PLATFORM_ORDER)
        platform_frames: dict[str, pd.DataFrame] = {}
        for platform_key in PLATFORM_ORDER:
            platform_frames[platform_key] = (
                work[work["platform"].eq(platform_key)]
                .head(limit)
                .reset_index(drop=True)
            )

        # Susunan utama tetap interleave agar setiap baris grid berusaha berisi
        # Twitter/X | Instagram | TikTok.
        ordered_rows: list[pd.DataFrame] = []
        for rank_index in range(limit):
            for platform_key in PLATFORM_ORDER:
                platform_frame = platform_frames.get(platform_key, pd.DataFrame())
                if rank_index < len(platform_frame):
                    ordered_rows.append(platform_frame.iloc[[rank_index]].copy())

        if not ordered_rows:
            return work.iloc[0:0].copy()

        result = pd.concat(ordered_rows, ignore_index=True, sort=False)
        dedupe_columns = (
            ["username_key", "platform"]
            if "username_key" in result.columns
            else ["username", "platform"]
        )
        result = result.drop_duplicates(subset=dedupe_columns, keep="first")

        # Fallback terkontrol untuk layanan/platform yang datanya belum seimbang.
        # Kandidat tambahan tetap berasal dari data aktual dan tipe akun yang sama.
        # Tidak ada placeholder ataupun perubahan label Media/Influencer.
        if len(result) < target_total:
            selected_keys = {
                tuple(str(row.get(column, "")) for column in dedupe_columns)
                for _, row in result.iterrows()
            }
            remaining_rows: list[pd.DataFrame] = []
            for _, row in work.iterrows():
                key = tuple(str(row.get(column, "")) for column in dedupe_columns)
                if key in selected_keys:
                    continue
                remaining_rows.append(row.to_frame().T)
                selected_keys.add(key)
                if len(result) + len(remaining_rows) >= target_total:
                    break

            if remaining_rows:
                result = pd.concat(
                    [result, *remaining_rows],
                    ignore_index=True,
                    sort=False,
                )

        result = result.head(target_total).reset_index(drop=True)
        result["recommendation_rank"] = range(1, len(result) + 1)
        return result
    except Exception as error:
        st.error(
            "Kandidat rekomendasi belum dapat diseimbangkan antarplatform. "
            f"Detail: {type(error).__name__}."
        )
        return influencers.iloc[0:0].copy()


def _select_balanced_account_type_candidates(
    ranked_candidates: pd.DataFrame,
    per_type_limit: int = ACCOUNT_TYPE_CARD_TARGET,
) -> pd.DataFrame:
    """Simpan kandidat terbaik per tipe agar filter dapat mengisi 9 kartu penuh.

    Kandidat tetap berasal dari pool data aktual yang sudah dihitung sebelumnya.
    Fungsi ini hanya mencegah pemotongan top-9 global terjadi terlalu awal sebelum
    akun dipisahkan menjadi kategori media dan influencer.
    """
    try:
        if ranked_candidates is None or ranked_candidates.empty:
            return pd.DataFrame(columns=getattr(ranked_candidates, "columns", None))

        work = ranked_candidates.copy()
        name_column = next(
            (
                column
                for column in ("name", "nama", "display_name", "fullname", "full_name")
                if column in work.columns
            ),
            None,
        )
        account_names = (
            work[name_column]
            if name_column is not None
            else pd.Series("", index=work.index, dtype="object")
        )
        work["_candidate_account_type"] = [
            _classify_account_type(username, account_name)
            for username, account_name in zip(
                work.get("username", pd.Series("", index=work.index)),
                account_names,
            )
        ]

        selected_frames: list[pd.DataFrame] = []
        for account_type in ("influencer", "media"):
            typed = work[
                work["_candidate_account_type"].astype(str).str.lower().eq(account_type)
            ].head(max(int(per_type_limit), 1))
            if not typed.empty:
                selected_frames.append(typed)

        # Fallback defensif: bila klasifikasi tidak menghasilkan kedua kategori,
        # pertahankan kandidat ranking teratas agar perilaku halaman tidak kosong.
        if not selected_frames:
            selected = work.head(max(int(per_type_limit), 1)).copy()
        else:
            selected = pd.concat(selected_frames, ignore_index=False, sort=False)

        selected = selected.drop_duplicates(
            subset=["username_key", "platform"],
            keep="first",
        )
        selected = selected.sort_values(
            [
                "recommendation_score", "degree_centrality", "followers",
                "relevant_content_count", "content_count", "username",
            ],
            ascending=[False, False, False, False, False, True],
        )
        return selected.drop(columns=["_candidate_account_type"], errors="ignore")
    except Exception as error:
        st.error(
            "Kandidat rekomendasi belum dapat diseimbangkan berdasarkan tipe akun. "
            f"Detail: {type(error).__name__}."
        )
        return ranked_candidates.head(max(int(per_type_limit), 1)).copy()


def _topic_regex(keywords: tuple[str, ...]) -> str:
    """Bangun pola regex aman dari daftar kata kunci topik."""
    ordered = sorted((str(item) for item in keywords), key=len, reverse=True)
    return "|".join(re.escape(item) for item in ordered)



def _pilih_kolom(frame: pd.DataFrame, kandidat: tuple[str, ...]) -> str | None:
    """Pilih nama kolom pertama yang tersedia tanpa membedakan huruf besar."""
    try:
        lookup = {
            str(column).strip().lower().lstrip("\ufeff"): str(column)
            for column in frame.columns
        }
        for name in kandidat:
            key = str(name).strip().lower().lstrip("\ufeff")
            if key in lookup:
                return lookup[key]
        return None
    except Exception:
        return None


def _pecah_kata_kunci(value: Any) -> list[str]:
    """Ubah teks kata kunci menjadi daftar pendek yang bersih dan unik."""
    try:
        items = re.split(r"[|,;/]+", str(value or ""))
        cleaned: list[str] = []
        for item in items:
            token = re.sub(r"\s+", " ", item).strip().lower()
            if token and token not in cleaned:
                cleaned.append(token)
        return cleaned[:8]
    except Exception:
        return []


def _normalisasi_output_topik_indibiz(frame: pd.DataFrame) -> pd.DataFrame:
    """Normalisasi variasi skema output topik IndiBiz menjadi kolom kanonik."""
    try:
        if frame is None or frame.empty:
            return pd.DataFrame(columns=["sentiment", "topik", "keywords", "jumlah"])
        sentiment_col = _pilih_kolom(frame, ("sentiment", "sentimen", "predicted_sentiment"))
        topic_col = _pilih_kolom(frame, ("topik", "topic", "nama_topik", "topic_name"))
        keyword_col = _pilih_kolom(frame, ("kata_kunci", "keywords", "keyword", "top_words"))
        count_col = _pilih_kolom(frame, ("jumlah_komentar", "jumlah", "frekuensi", "frequency", "count"))
        if sentiment_col is None or topic_col is None:
            raise ValueError("Kolom sentimen atau topik tidak ditemukan.")

        result = pd.DataFrame({
            "sentiment": frame[sentiment_col].map(_normalisasi_sentimen),
            "topik": frame[topic_col].fillna("Topik Bisnis").astype(str).str.strip(),
            "keywords": (
                frame[keyword_col].fillna("").astype(str)
                if keyword_col is not None
                else ""
            ),
            "jumlah": (
                pd.to_numeric(frame[count_col], errors="coerce").fillna(0)
                if count_col is not None
                else pd.Series(1, index=frame.index, dtype=float)
            ),
        })
        result = result[result["topik"].ne("")].copy()
        return result.reset_index(drop=True)
    except Exception as error:
        st.error(f"Gagal menormalisasi output topik IndiBiz: {error}")
        return pd.DataFrame(columns=["sentiment", "topik", "keywords", "jumlah"])


def _normalisasi_output_kata_indibiz(frame: pd.DataFrame) -> pd.DataFrame:
    """Normalisasi variasi skema output top-kata IndiBiz menjadi kolom kanonik."""
    try:
        if frame is None or frame.empty:
            return pd.DataFrame(columns=["sentiment", "kata", "frekuensi", "rank"])
        sentiment_col = _pilih_kolom(frame, ("sentiment", "sentimen", "predicted_sentiment"))
        word_col = _pilih_kolom(frame, ("kata", "word", "keyword", "token"))
        frequency_col = _pilih_kolom(frame, ("frekuensi", "frequency", "jumlah", "count"))
        rank_col = _pilih_kolom(frame, ("rank", "peringkat", "urutan"))
        if sentiment_col is None or word_col is None:
            raise ValueError("Kolom sentimen atau kata tidak ditemukan.")

        result = pd.DataFrame({
            "sentiment": frame[sentiment_col].map(_normalisasi_sentimen),
            "kata": frame[word_col].fillna("").astype(str).str.strip().str.lower(),
            "frekuensi": (
                pd.to_numeric(frame[frequency_col], errors="coerce").fillna(0)
                if frequency_col is not None
                else pd.Series(0, index=frame.index, dtype=float)
            ),
            "rank": (
                pd.to_numeric(frame[rank_col], errors="coerce").fillna(999)
                if rank_col is not None
                else pd.Series(range(1, len(frame) + 1), index=frame.index, dtype=float)
            ),
        })
        return result[result["kata"].ne("")].reset_index(drop=True)
    except Exception as error:
        st.error(f"Gagal menormalisasi output top kata IndiBiz: {error}")
        return pd.DataFrame(columns=["sentiment", "kata", "frekuensi", "rank"])


def _ide_konten_bisnis_indibiz(
    sentiment: str,
    topik: str,
    keywords: list[str],
) -> list[str]:
    """Bangun tiga ide konten profesional untuk segmen UMKM dan korporasi."""
    keyword_text = ", ".join(keywords[:3]) or "konektivitas bisnis"
    templates = {
        "positive": [
            f"Publikasikan studi kasus UMKM yang meningkatkan produktivitas setelah menggunakan IndiBiz pada topik {topik}. Sertakan indikator operasional yang terukur.",
            f"Buat carousel praktik baik tentang {keyword_text} untuk membantu pemilik usaha menjaga kelancaran transaksi, sistem kasir, dan komunikasi pelanggan.",
            "Produksi video testimoni pelaku usaha atau pelanggan korporasi yang menjelaskan manfaat koneksi stabil terhadap efisiensi kerja dan pertumbuhan bisnis.",
        ],
        "neutral": [
            f"Susun panduan pemilihan paket IndiBiz berdasarkan jumlah perangkat, kebutuhan bandwidth, jenis usaha, dan topik {topik}.",
            f"Terbitkan FAQ profesional yang menjelaskan {keyword_text}, proses instalasi, dukungan teknis, serta kanal eskalasi untuk pelanggan bisnis.",
            "Adakan sesi edukasi singkat untuk UMKM mengenai kesiapan jaringan, keamanan koneksi, pencadangan operasional, dan perencanaan kebutuhan internet.",
        ],
        "negative": [
            f"Publikasikan pembaruan penanganan untuk isu {topik} dengan wilayah terdampak, tahapan perbaikan, estimasi pemulihan, dan kanal bantuan resmi.",
            f"Buat konten service recovery yang menjelaskan tindakan konkret IndiBiz terhadap keluhan terkait {keyword_text}, termasuk prosedur eskalasi pelanggan bisnis.",
            "Sediakan format laporan gangguan khusus UMKM dan korporasi agar pelanggan dapat mengirim nomor layanan, lokasi, dampak operasional, serta waktu kejadian secara lengkap.",
        ],
    }
    return templates.get(sentiment, templates["neutral"])


@st.cache_data(show_spinner=False, max_entries=12)
def _build_indibiz_sentiment_recommendations() -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Muat topik dan top-kata IndiBiz lalu susun tiga ide per sentimen."""
    try:
        raw_topics = load_indibiz_topics(INDIBIZ_TOPIC_FILE)
        raw_words = load_indibiz_top_kata(INDIBIZ_TOP_WORD_FILE)
        topics = _normalisasi_output_topik_indibiz(raw_topics)
        words = _normalisasi_output_kata_indibiz(raw_words)

        rows: list[dict[str, Any]] = []
        meta_map = {
            "positive": {"label": "Positif", "icon": "✓", "color": "#4CAF50", "soft": "rgba(76,175,80,.15)"},
            "neutral": {"label": "Netral", "icon": "i", "color": "#1DA1F2", "soft": "rgba(29,161,242,.15)"},
            "negative": {"label": "Negatif", "icon": "!", "color": "#E53935", "soft": "rgba(229,57,53,.15)"},
        }

        for sentiment in ("positive", "neutral", "negative"):
            topic_group = topics[topics["sentiment"].eq(sentiment)].copy()
            if topic_group.empty:
                topik = "Konektivitas dan Operasional Bisnis"
                topic_keywords: list[str] = []
            else:
                topic_group = topic_group.sort_values(
                    ["jumlah", "topik"], ascending=[False, True]
                )
                best = topic_group.iloc[0]
                topik = str(best["topik"] or "Konektivitas dan Operasional Bisnis")
                topic_keywords = _pecah_kata_kunci(best.get("keywords", ""))

            word_group = words[words["sentiment"].eq(sentiment)].copy()
            word_group = word_group.sort_values(
                ["frekuensi", "rank", "kata"], ascending=[False, True, True]
            )
            top_words = word_group["kata"].astype(str).head(5).tolist()
            keywords = list(dict.fromkeys(topic_keywords + top_words))[:6]
            visual = meta_map[sentiment]
            rows.append({
                "sentiment": sentiment,
                "label": visual["label"],
                "icon": visual["icon"],
                "color": visual["color"],
                "soft": visual["soft"],
                "topik": topik,
                "keywords": keywords,
                "ideas": _ide_konten_bisnis_indibiz(sentiment, topik, keywords),
            })

        is_real = INDIBIZ_TOPIC_FILE.is_file() and INDIBIZ_TOP_WORD_FILE.is_file()
        source_name = (
            f"{INDIBIZ_TOPIC_FILE.name} + {INDIBIZ_TOP_WORD_FILE.name}"
            if is_real
            else "Data dummy topik dan top-kata IndiBiz"
        )
        return rows, {"is_real": is_real, "source_name": source_name}
    except Exception as error:
        st.error(f"Gagal menyusun rekomendasi konten IndiBiz: {error}")
        fallback_rows = []
        for sentiment, label, icon, color, soft in (
            ("positive", "Positif", "✓", "#4CAF50", "rgba(76,175,80,.15)"),
            ("neutral", "Netral", "i", "#1DA1F2", "rgba(29,161,242,.15)"),
            ("negative", "Negatif", "!", "#E53935", "rgba(229,57,53,.15)"),
        ):
            topik = "Konektivitas dan Operasional Bisnis"
            keywords = ["internet bisnis", "produktivitas", "dukungan teknis"]
            fallback_rows.append({
                "sentiment": sentiment,
                "label": label,
                "icon": icon,
                "color": color,
                "soft": soft,
                "topik": topik,
                "keywords": keywords,
                "ideas": _ide_konten_bisnis_indibiz(sentiment, topik, keywords),
            })
        return fallback_rows, {
            "is_real": False,
            "source_name": "Fallback rekomendasi konten bisnis IndiBiz",
        }


@st.cache_data(show_spinner=False, max_entries=12)
def _build_topic_summary(
    layanan: str,
    demo_mode: bool = False,
) -> tuple[pd.DataFrame, dict[str, Any]]:
    """Bangun ringkasan lima topik dari data aktual atau fallback."""
    try:
        if demo_mode:
            source_is_real = False
            source_name = "Mode Demo · data sample terkurasi"
            df = get_demo_sentiment(layanan).copy()
        else:
            source_is_real = sentiment_file_exists(layanan)
            source_name = get_sentiment_source_name(layanan)
            df = load_topic_data(layanan).copy()

        if df.empty or "content" not in df.columns:
            raise ValueError("Kolom komentar tidak tersedia pada sumber data.")

        if "predicted_sentiment" not in df.columns:
            df["predicted_sentiment"] = "neutral"

        work = df[["content", "predicted_sentiment"]].copy()
        work["content"] = work["content"].fillna("").astype(str).str.lower()
        work["sentiment"] = work["predicted_sentiment"].map(_normalisasi_sentimen)
        work["topic_key"] = ""

        # Prioritas urutan mengikuti TOPIC_CONFIG. Baris yang sudah terklasifikasi
        # tidak ditimpa oleh pola topik berikutnya.
        for topic in TOPIC_CONFIG:
            pattern = _topic_regex(topic["keywords"])
            mask = work["topic_key"].eq("") & work["content"].str.contains(
                pattern,
                regex=True,
                na=False,
            )
            work.loc[mask, "topic_key"] = str(topic["key"])

        total_data = max(int(len(work)), 1)
        classified = work[work["topic_key"].ne("")].copy()
        rows: list[dict[str, Any]] = []

        for topic in TOPIC_CONFIG:
            topic_key = str(topic["key"])
            group = classified[classified["topic_key"] == topic_key]
            count = int(len(group))

            if group.empty:
                dominant = str(topic["sentimen_default"])
            else:
                counts = group["sentiment"].value_counts()
                # Tie-break memprioritaskan negatif, lalu positif, lalu netral.
                priority = {"negative": 3, "positive": 2, "neutral": 1}
                dominant = max(
                    counts.index,
                    key=lambda item: (int(counts[item]), priority.get(str(item), 0)),
                )

            rows.append(
                {
                    "key": topic_key,
                    "topik": str(topic["nama"]),
                    "topik_singkat": str(topic["singkat"]),
                    "jumlah_komentar": count,
                    "persentase": round((count / total_data) * 100, 1),
                    "sentimen_dominan": dominant,
                }
            )

        result = pd.DataFrame(rows)

        # Bila tidak ada komentar yang cocok dengan lima topik penelitian,
        # gunakan baseline yang konsisten agar halaman tetap dapat didemokan.
        if int(result["jumlah_komentar"].sum()) == 0:
            raise ValueError("Tidak ada komentar yang cocok dengan kamus lima topik.")

        sentiment_counts = work["sentiment"].value_counts()
        negative_pct = round(
            int(sentiment_counts.get("negative", 0)) / total_data * 100,
            1,
        )
        dominant_row = result.sort_values(
            ["jumlah_komentar", "topik"],
            ascending=[False, True],
        ).iloc[0]

        meta = {
            "is_real": bool(source_is_real),
            "source_name": source_name,
            "negative_pct": negative_pct,
            "dominant_issue": str(dominant_row["topik_singkat"]),
            "total_rows": int(len(work)),
        }
        return result, meta
    except Exception:
        fallback = SERVICE_TOPIC_FALLBACK.get(
            layanan,
            SERVICE_TOPIC_FALLBACK["IndiHome"],
        )
        total = max(sum(fallback.values()), 1)
        rows = []
        for topic in TOPIC_CONFIG:
            count = int(fallback.get(str(topic["key"]), 0))
            rows.append(
                {
                    "key": str(topic["key"]),
                    "topik": str(topic["nama"]),
                    "topik_singkat": str(topic["singkat"]),
                    "jumlah_komentar": count,
                    "persentase": round(count / total * 100, 1),
                    "sentimen_dominan": str(topic["sentimen_default"]),
                }
            )

        result = pd.DataFrame(rows)
        dominant_row = result.sort_values("jumlah_komentar", ascending=False).iloc[0]
        negative_count = result[
            result["sentimen_dominan"].eq("negative")
        ]["jumlah_komentar"].sum()
        meta = {
            "is_real": False,
            "source_name": "Data fallback terstruktur",
            "negative_pct": round(float(negative_count) / total * 100, 1),
            "dominant_issue": str(dominant_row["topik_singkat"]),
            "total_rows": int(total),
        }
        return result, meta


def _filter_sna_by_service(df: pd.DataFrame, layanan: str) -> pd.DataFrame:
    """Filter edge SNA berdasarkan layanan dengan beberapa strategi kolom."""
    try:
        if df is None or df.empty:
            return pd.DataFrame()

        work = df.copy()
        aliases = SERVICE_ALIASES.get(layanan, (layanan.lower(),))
        aliases_pattern = "|".join(re.escape(item.lower()) for item in aliases)

        # Prioritaskan kolom layanan eksplisit bila tersedia.
        for column in ("layanan", "service", "object_group", "brand"):
            if column in work.columns:
                mask = work[column].astype(str).str.lower().str.contains(
                    aliases_pattern,
                    regex=True,
                    na=False,
                )
                if mask.any():
                    return work[mask].copy()

        # Jika tidak ada kolom layanan, cari pada source/target/relationship.
        searchable = pd.Series(False, index=work.index)
        for column in ("source", "target", "relationship"):
            if column in work.columns:
                searchable = searchable | work[column].astype(str).str.lower().str.contains(
                    aliases_pattern,
                    regex=True,
                    na=False,
                )

        if searchable.any():
            return work[searchable].copy()
        return pd.DataFrame()
    except Exception:
        return pd.DataFrame()


@st.cache_data(show_spinner=False, max_entries=12)
def _calculate_influencers_from_sna(
    df: pd.DataFrame,
    layanan: str,
) -> pd.DataFrame:
    """Hitung kandidat influencer per platform dari edge list SNA."""
    try:
        # NetworkX baru dimuat ketika kalkulasi jaringan benar-benar diperlukan.
        # Cold-open dapat mengirim komponen atas halaman lebih dahulu.
        import networkx as nx
        if df is None or df.empty:
            return pd.DataFrame()

        required = {"source", "target", "followers", "platform"}
        if not required.issubset(df.columns):
            return pd.DataFrame()

        work = df.copy()
        work["source"] = work["source"].astype(str).str.strip().str.lstrip("@")
        work["target"] = work["target"].astype(str).str.strip().str.lstrip("@")
        work["platform"] = (
            work["platform"]
            .astype(str)
            .str.lower()
            .str.strip()
            .replace({"x": "twitter", "twitter/x": "twitter", "ig": "instagram"})
        )
        work["followers"] = pd.to_numeric(
            work["followers"], errors="coerce"
        ).fillna(0)
        work = work[
            work["source"].ne("")
            & work["target"].ne("")
            & work["platform"].isin(PLATFORM_ORDER)
        ].copy()

        rows: list[dict[str, Any]] = []
        for platform in PLATFORM_ORDER:
            platform_df = work[work["platform"].eq(platform)].copy()
            if platform_df.empty:
                continue

            graph = nx.from_pandas_edgelist(
                platform_df,
                source="source",
                target="target",
                create_using=nx.DiGraph(),
            )
            if graph.number_of_nodes() == 0:
                continue

            centrality = (
                nx.degree_centrality(graph)
                if graph.number_of_nodes() > 1
                else {node: 0.0 for node in graph.nodes}
            )
            followers_map = platform_df.groupby("source")["followers"].max().to_dict()
            edge_count_map = platform_df.groupby("source").size().to_dict()

            for node in graph.nodes:
                username = _safe_username(node)
                if _is_brand_account(username):
                    continue
                rows.append(
                    {
                        "username": username,
                        "username_key": _username_lookup_key(username),
                        "platform": platform,
                        "followers": int(followers_map.get(node, 0)),
                        "degree_centrality": float(centrality.get(node, 0.0)),
                        "network_edges": int(edge_count_map.get(node, 0)),
                    }
                )

        result = pd.DataFrame(rows)
        if not result.empty:
            result["layanan"] = layanan
        return result
    except Exception:
        return pd.DataFrame()


@st.cache_data(show_spinner=False, max_entries=12)
def _build_content_author_stats(layanan: str) -> pd.DataFrame:
    """Ringkas penulis konten asli sebagai bukti kelayakan influencer."""
    columns = [
        "username", "username_key", "platform", "followers",
        "content_count", "relevant_content_count", "content_engagement",
        "dominant_topic", "content_topics",
    ]
    try:
        source_frames: list[pd.DataFrame] = []

        # Konten sentimen hanya dipakai jika file aktual tersedia. Dummy tidak
        # dipakai sebagai bukti influencer. Namun, file SNA aktual boleh menjadi
        # bukti konten jika menyimpan kolom content/text.
        if sentiment_file_exists(layanan):
            frame = load_influencer_content_data(layanan).copy()
            if not frame.empty:
                source_frames.append(frame)

        # Jika edge list menyimpan teks source, gunakan sebagai bukti tambahan.
        if sna_file_exists(layanan):
            sna_frame = _filter_sna_by_service(load_sna_data(layanan).copy(), layanan)
            content_column = next(
                (
                    column for column in (
                        "content", "text", "comment_text", "tweet_text",
                        "caption", "source_content", "post_content",
                    )
                    if column in sna_frame.columns
                ),
                None,
            )
            if (
                content_column is not None
                and "source" in sna_frame.columns
                and "platform" in sna_frame.columns
            ):
                extra = pd.DataFrame(
                    {
                        "username": sna_frame["source"],
                        "platform": sna_frame["platform"],
                        "content": sna_frame[content_column],
                        "followers": sna_frame.get("followers", 0),
                        "predicted_sentiment": sna_frame.get(
                            "predicted_sentiment", "neutral"
                        ),
                        "date": sna_frame.get(
                            "date", sna_frame.get("date_created", "")
                        ),
                        "link": sna_frame.get("link", ""),
                        "engagement": sna_frame.get("engagement", 0),
                        "specific_type": sna_frame.get("relationship", "interaksi"),
                    }
                )
                source_frames.append(extra)

        if not source_frames:
            return pd.DataFrame(columns=columns)
        frame = pd.concat(source_frames, ignore_index=True, sort=False)
        required = {"username", "platform", "content"}
        if frame.empty or not required.issubset(frame.columns):
            return pd.DataFrame(columns=columns)

        work = frame.copy()

        # Operasi pada kolom besar dibuat vectorized. Versi lama memanggil
        # fungsi Python per baris untuk username dan teks, yang terasa lambat
        # ketika dataset berisi puluhan ribu komentar.
        work["username"] = work["username"].map(_safe_username)
        work["username_key"] = (
            work["username"]
            .astype(str)
            .str.lower()
            .str.replace(r"[^a-z0-9]+", "", regex=True)
        )
        work["platform"] = (
            work["platform"]
            .fillna("")
            .astype(str)
            .str.lower()
            .str.strip()
            .replace({"x": "twitter", "twitter/x": "twitter", "ig": "instagram"})
        )
        work["content_clean"] = (
            work["content"]
            .fillna("")
            .astype(str)
            .str.replace(r"\s+", " ", regex=True)
            .str.strip()
        )
        work.loc[
            work["content_clean"].str.lower().isin(["nan", "none"]),
            "content_clean",
        ] = ""
        work["followers"] = pd.to_numeric(
            work.get("followers", 0), errors="coerce"
        ).fillna(0)

        if "engagement" in work.columns:
            work["content_engagement"] = pd.to_numeric(
                work["engagement"], errors="coerce"
            ).fillna(0)
        else:
            work["content_engagement"] = 0.0
            for column in ("like", "comment", "share", "reply_count", "retweet_count"):
                if column in work.columns:
                    work["content_engagement"] += pd.to_numeric(
                        work[column], errors="coerce"
                    ).fillna(0)

        work = work[
            work["username_key"].ne("")
            & work["platform"].isin(PLATFORM_ORDER)
            & work["content_clean"].str.len().ge(8)
        ].copy()
        work = work[~work["username"].map(_is_brand_account)].copy()
        if work.empty:
            return pd.DataFrame(columns=columns)

        service_pattern = "|".join(
            re.escape(alias.lower())
            for alias in SERVICE_ALIASES.get(layanan, (layanan.lower(),))
        )
        topic_pattern = "|".join(
            _topic_regex(tuple(topic["keywords"])) for topic in TOPIC_CONFIG
        )
        service_match = work["content_clean"].str.lower().str.contains(
            service_pattern, regex=True, na=False
        )
        topic_match = work["content_clean"].str.lower().str.contains(
            topic_pattern, regex=True, na=False
        )
        work["content_relevance"] = (
            service_match.astype(int) * 3 + topic_match.astype(int) * 2
        )
        work = work[work["content_relevance"].gt(0)].copy()
        work["content_topic"] = work["content_clean"].map(_detect_content_topic)
        work = work.drop_duplicates(
            subset=["username_key", "platform", "content_clean"],
            keep="first",
        )

        rows: list[dict[str, Any]] = []
        for (username_key, platform), group in work.groupby(
            ["username_key", "platform"], sort=False
        ):
            relevant_group = group[group["content_relevance"].gt(0)].copy()
            if relevant_group.empty:
                continue
            topic_counts = relevant_group["content_topic"].value_counts()
            top_topics = [
                topic for topic in topic_counts.head(3).index.astype(str).tolist()
                if topic != "Percakapan Layanan"
            ]
            if not top_topics:
                top_topics = ["Percakapan Layanan"]
            rows.append(
                {
                    "username": _safe_username(group.iloc[0]["username"]),
                    "username_key": str(username_key),
                    "platform": str(platform),
                    "followers": int(group["followers"].max()),
                    "content_count": int(group["content_clean"].nunique()),
                    "relevant_content_count": int(
                        relevant_group["content_clean"].nunique()
                    ),
                    "content_engagement": int(
                        relevant_group["content_engagement"].sum()
                    ),
                    "dominant_topic": top_topics[0],
                    "content_topics": "|".join(top_topics),
                }
            )

        return pd.DataFrame(rows, columns=columns)
    except Exception:
        return pd.DataFrame(columns=columns)


def _score_content_validated_candidates(
    candidates: pd.DataFrame,
    platform: str,
) -> pd.DataFrame:
    """Beri skor gabungan jaringan, jangkauan, dan bukti konten asli."""
    if candidates.empty:
        return candidates

    result = candidates.copy()
    for column in (
        "followers", "degree_centrality", "network_edges",
        "content_count", "relevant_content_count", "content_engagement",
    ):
        result[column] = pd.to_numeric(result.get(column, 0), errors="coerce").fillna(0)

    def normalize(series: pd.Series) -> pd.Series:
        values = series.astype(float).clip(lower=0)
        maximum = float(values.max()) if not values.empty else 0.0
        return values / maximum if maximum > 0 else pd.Series(0.0, index=values.index)

    follower_values = result["followers"].astype(float).clip(lower=0).map(math.log1p)
    content_values = (
        result["relevant_content_count"].astype(float).clip(lower=0) * 3.0
        + result["content_count"].astype(float).clip(lower=0) * 0.5
        + result["content_engagement"].astype(float).clip(lower=0).map(math.log1p)
    )
    degree_norm = normalize(result["degree_centrality"])
    follower_norm = follower_values / follower_values.max() if follower_values.max() > 0 else 0.0
    content_norm = content_values / content_values.max() if content_values.max() > 0 else 0.0

    if platform == "twitter":
        result["recommendation_score"] = (
            degree_norm * 0.50 + follower_norm * 0.20 + content_norm * 0.30
        )
    else:
        result["recommendation_score"] = (
            degree_norm * 0.20 + follower_norm * 0.35 + content_norm * 0.45
        )

    def selection_basis(row: pd.Series) -> str:
        has_network = (
            float(row.get("degree_centrality", 0) or 0) > 0
            or float(row.get("network_edges", 0) or 0) > 0
        )
        has_content = float(row.get("relevant_content_count", 0) or 0) > 0
        if has_network and has_content:
            return "Jaringan + konten asli"
        if has_network:
            return "Metrik SNA + jangkauan"
        return "Konten asli + jangkauan"

    result["selection_basis"] = result.apply(selection_basis, axis=1)
    return result


@st.cache_data(show_spinner=False, max_entries=12)
def _build_indibiz_influencer_data() -> tuple[pd.DataFrame, dict[str, Any]]:
    """Bangun kandidat IndiBiz dari SNA dan konten aktual lintas platform.

    SNA IndiBiz terutama menyediakan kandidat Twitter/X. Instagram dan TikTok
    dilengkapi dari penulis konten aktual pada dataset sentimen IndiBiz. Seluruh
    kandidat tetap non-brand, lalu diranking per platform tanpa membuat akun
    dummy atau placeholder.
    """
    columns = [
        "username", "username_key", "platform", "followers",
        "degree_centrality", "network_edges", "content_count",
        "relevant_content_count", "content_engagement", "dominant_topic",
        "content_topics", "recommendation_score", "recommendation_rank",
        "selection_basis", "layanan",
    ]
    try:
        # 1) Kandidat jaringan. Pada data penelitian IndiBiz, edge SNA paling
        # kuat tersedia pada Twitter/X sehingga bagian ini tidak boleh menjadi
        # satu-satunya sumber kandidat rekomendasi.
        sna_df = load_sna_data("IndiBiz").copy()
        service_df = _filter_sna_by_service(sna_df, "IndiBiz")
        network_candidates = _calculate_influencers_from_sna(
            service_df,
            "IndiBiz",
        )
        if network_candidates.empty:
            network_candidates = pd.DataFrame(
                columns=[
                    "username", "username_key", "platform", "followers",
                    "degree_centrality", "network_edges", "layanan",
                ]
            )

        # 2) Penulis konten aktual. Sumber ini menyediakan kandidat Instagram
        # dan TikTok yang sebelumnya tidak pernah masuk ke pool khusus IndiBiz.
        content_stats = _build_content_author_stats("IndiBiz")

        # 3) Gabungkan kandidat yang mempunyai bukti jaringan + konten.
        validated_pool = network_candidates.merge(
            content_stats,
            on=["username_key", "platform"],
            how="inner",
            suffixes=("_network", "_content"),
        )
        if not validated_pool.empty:
            validated_pool["username"] = validated_pool[
                "username_content"
            ].fillna(validated_pool["username_network"])
            validated_pool["followers"] = validated_pool[
                ["followers_network", "followers_content"]
            ].max(axis=1)
            validated_pool = validated_pool.drop(
                columns=[
                    "username_network", "username_content",
                    "followers_network", "followers_content",
                ],
                errors="ignore",
            )

        candidate_frames: list[pd.DataFrame] = []
        if not validated_pool.empty:
            candidate_frames.append(validated_pool)

        known_keys: set[tuple[str, str]] = set()
        if not validated_pool.empty:
            known_keys.update(
                zip(
                    validated_pool["username_key"].astype(str),
                    validated_pool["platform"].astype(str),
                )
            )

        # Kandidat jaringan yang belum mempunyai pasangan konten tetap boleh
        # tampil karena mempunyai bukti metrik SNA/followers yang nyata.
        network_extra = network_candidates.copy()
        if not network_extra.empty:
            network_mask = [
                (str(row.username_key), str(row.platform)) not in known_keys
                for row in network_extra.itertuples()
            ]
            network_extra = network_extra.loc[network_mask].copy()
            for column in (
                "content_count", "relevant_content_count", "content_engagement",
            ):
                network_extra[column] = 0
            network_extra["dominant_topic"] = ""
            network_extra["content_topics"] = ""
            if not network_extra.empty:
                candidate_frames.append(network_extra)
                known_keys.update(
                    zip(
                        network_extra["username_key"].astype(str),
                        network_extra["platform"].astype(str),
                    )
                )

        # INILAH PERBAIKAN UTAMA: penulis konten Instagram/TikTok yang valid
        # tidak lagi dibuang hanya karena tidak mempunyai edge pada file SNA.
        content_extra = content_stats.copy()
        if not content_extra.empty:
            content_mask = [
                (str(row.username_key), str(row.platform)) not in known_keys
                for row in content_extra.itertuples()
            ]
            content_extra = content_extra.loc[content_mask].copy()
            content_extra["degree_centrality"] = 0.0
            content_extra["network_edges"] = 0
            content_extra["layanan"] = "IndiBiz"
            if not content_extra.empty:
                candidate_frames.append(content_extra)

        if not candidate_frames:
            raise ValueError(
                "Tidak ada kandidat IndiBiz dari data SNA maupun konten aktual."
            )

        pool = pd.concat(candidate_frames, ignore_index=True, sort=False)
        pool = pool.drop_duplicates(
            subset=["username_key", "platform"],
            keep="first",
        )

        for column in (
            "followers", "degree_centrality", "network_edges", "content_count",
            "relevant_content_count", "content_engagement",
        ):
            if column not in pool.columns:
                pool[column] = 0
            pool[column] = pd.to_numeric(
                pool[column],
                errors="coerce",
            ).fillna(0).clip(lower=0)

        for column in ("dominant_topic", "content_topics"):
            if column not in pool.columns:
                pool[column] = ""
            pool[column] = pool[column].fillna("").astype(str)

        pool["layanan"] = "IndiBiz"

        # 4) Ranking dilakukan per platform supaya platform dengan volume data
        # besar tidak menghabiskan seluruh slot rekomendasi.
        selected_frames: list[pd.DataFrame] = []
        for platform in PLATFORM_ORDER:
            group = pool[pool["platform"].eq(platform)].copy()
            if group.empty:
                continue

            group = _score_content_validated_candidates(group, platform)
            group = group.sort_values(
                [
                    "recommendation_score", "degree_centrality", "followers",
                    "relevant_content_count", "content_count", "username",
                ],
                ascending=[False, False, False, False, False, True],
            )
            group = _select_balanced_account_type_candidates(group)
            if not group.empty:
                selected_frames.append(group)

        if not selected_frames:
            raise ValueError(
                "Tidak ada kandidat rekomendasi IndiBiz pada platform yang tersedia."
            )

        result = pd.concat(selected_frames, ignore_index=True, sort=False)
        result = result.sort_values(
            ["platform", "recommendation_score", "degree_centrality", "followers"],
            ascending=[True, False, False, False],
        ).reset_index(drop=True)
        result["recommendation_rank"] = range(1, len(result) + 1)
        result["layanan"] = "IndiBiz"

        for column in columns:
            if column not in result.columns:
                result[column] = (
                    ""
                    if column in {
                        "username", "username_key", "platform",
                        "dominant_topic", "content_topics",
                        "selection_basis", "layanan",
                    }
                    else 0
                )
        result = result[columns]

        has_real_sna = sna_file_exists("IndiBiz")
        has_real_content = sentiment_file_exists("IndiBiz")
        source_parts: list[str] = []
        if has_real_content:
            source_parts.append(get_sentiment_source_name("IndiBiz"))
        if has_real_sna:
            source_parts.append(get_sna_source_names("IndiBiz"))
        source_name = " + ".join(part for part in source_parts if part)
        if not source_name:
            source_name = "Data IndiBiz yang tersedia"

        return result, {
            "is_real": bool(has_real_sna or has_real_content),
            "source_name": source_name,
            "actual_rows": int(len(result)),
            "content_authors": int(len(content_stats)),
            "ranking_method": (
                "Degree centrality + followers + bukti konten relevan"
            ),
        }
    except Exception as error:
        st.error(f"Gagal menghitung influencer IndiBiz: {error}")
        return pd.DataFrame(columns=columns), {
            "is_real": False,
            "source_name": "Fallback kandidat IndiBiz belum dapat dihitung",
            "actual_rows": 0,
            "content_authors": 0,
            "ranking_method": (
                "Degree centrality + followers + bukti konten relevan"
            ),
        }


@st.cache_data(show_spinner=False, max_entries=12)
def _build_influencer_data(
    layanan: str,
    demo_mode: bool = False,
) -> tuple[pd.DataFrame, dict[str, Any]]:
    """Pilih maksimal sembilan influencer aktual pada setiap platform layanan."""
    if demo_mode:
        demo = get_demo_influencers(layanan).copy()
        empty_columns = [
            "username", "username_key", "platform", "followers",
            "degree_centrality", "network_edges", "content_count",
            "relevant_content_count", "content_engagement", "dominant_topic",
            "content_topics", "recommendation_score", "recommendation_rank",
            "selection_basis", "layanan",
        ]
        for column in empty_columns:
            if column not in demo.columns:
                demo[column] = 0 if column not in {
                    "username", "username_key", "platform", "dominant_topic",
                    "content_topics", "selection_basis", "layanan",
                } else ""
        return demo[empty_columns].reset_index(drop=True), {
            "is_real": False,
            "source_name": "Mode Demo · influencer sample terkurasi",
            "actual_rows": int(len(demo)),
            "content_authors": int(demo["username_key"].nunique()),
            "ranking_method": "Degree centrality + followers + konten sample",
        }

    if layanan == "IndiBiz":
        return _build_indibiz_influencer_data()

    empty_columns = [
        "username", "username_key", "platform", "followers",
        "degree_centrality", "network_edges", "content_count",
        "relevant_content_count", "content_engagement", "dominant_topic",
        "content_topics", "recommendation_score", "recommendation_rank",
        "selection_basis", "layanan",
    ]
    try:
        content_stats = _build_content_author_stats(layanan)
        sna_df = load_sna_data(layanan).copy()
        service_df = _filter_sna_by_service(sna_df, layanan)
        network_candidates = _calculate_influencers_from_sna(service_df, layanan)

        if network_candidates.empty:
            network_candidates = pd.DataFrame(
                columns=[
                    "username", "username_key", "platform", "followers",
                    "degree_centrality", "network_edges", "layanan",
                ]
            )

        baseline_candidates = pd.DataFrame(BASELINE_INFLUENCERS).copy()
        baseline_candidates["username_key"] = baseline_candidates["username"].map(
            _username_lookup_key
        )
        baseline_candidates["network_edges"] = 0
        baseline_candidates["layanan"] = layanan

        network_pool = pd.concat(
            [network_candidates, baseline_candidates],
            ignore_index=True,
            sort=False,
        ).drop_duplicates(
            subset=["username_key", "platform"],
            keep="first",
        )

        validated_pool = network_pool.merge(
            content_stats,
            on=["username_key", "platform"],
            how="inner",
            suffixes=("_network", "_content"),
        )
        if not validated_pool.empty:
            validated_pool["username"] = validated_pool["username_content"].fillna(
                validated_pool["username_network"]
            )
            validated_pool["followers"] = validated_pool[
                ["followers_network", "followers_content"]
            ].max(axis=1)
            validated_pool = validated_pool.drop(
                columns=[
                    "username_network", "username_content",
                    "followers_network", "followers_content",
                ],
                errors="ignore",
            )
            validated_pool = validated_pool[
                pd.to_numeric(
                    validated_pool["relevant_content_count"], errors="coerce"
                ).fillna(0).gt(0)
            ].copy()

        candidate_frames: list[pd.DataFrame] = []
        if not validated_pool.empty:
            candidate_frames.append(validated_pool)

        known_keys = set()
        if not validated_pool.empty:
            known_keys = set(
                zip(
                    validated_pool["username_key"].astype(str),
                    validated_pool["platform"].astype(str),
                )
            )

        network_extra = network_candidates.copy()
        if not network_extra.empty:
            mask = [
                (str(row.username_key), str(row.platform)) not in known_keys
                for row in network_extra.itertuples()
            ]
            network_extra = network_extra.loc[mask].copy()
            for column in (
                "content_count", "relevant_content_count", "content_engagement",
            ):
                network_extra[column] = 0
            network_extra["dominant_topic"] = ""
            network_extra["content_topics"] = ""
            if not network_extra.empty:
                candidate_frames.append(network_extra)
                known_keys.update(
                    zip(
                        network_extra["username_key"].astype(str),
                        network_extra["platform"].astype(str),
                    )
                )

        content_extra = content_stats.copy()
        if not content_extra.empty:
            mask = [
                (str(row.username_key), str(row.platform)) not in known_keys
                for row in content_extra.itertuples()
            ]
            content_extra = content_extra.loc[mask].copy()
            content_extra["degree_centrality"] = 0.0
            content_extra["network_edges"] = 0
            content_extra["layanan"] = layanan
            if not content_extra.empty:
                candidate_frames.append(content_extra)

        if not candidate_frames:
            return pd.DataFrame(columns=empty_columns), {
                "is_real": False,
                "source_name": f"{get_sentiment_source_name(layanan)} + {get_sna_source_names(layanan) if sna_file_exists(layanan) else 'SNA tidak tersedia'}",
                "actual_rows": 0,
                "content_authors": int(len(content_stats)),
            }

        pool = pd.concat(candidate_frames, ignore_index=True, sort=False)
        pool = pool.drop_duplicates(
            subset=["username_key", "platform"], keep="first"
        )
        for column in (
            "followers", "degree_centrality", "network_edges", "content_count",
            "relevant_content_count", "content_engagement",
        ):
            if column not in pool.columns:
                pool[column] = 0
            pool[column] = pd.to_numeric(pool[column], errors="coerce").fillna(0)
        for column in ("dominant_topic", "content_topics"):
            if column not in pool.columns:
                pool[column] = ""
            pool[column] = pool[column].fillna("").astype(str)
        if "layanan" not in pool.columns:
            pool["layanan"] = layanan
        pool["layanan"] = pool["layanan"].fillna(layanan).replace("", layanan)

        selected_frames: list[pd.DataFrame] = []
        for platform in PLATFORM_ORDER:
            group = pool[pool["platform"].eq(platform)].copy()
            if group.empty:
                continue
            group = _score_content_validated_candidates(group, platform)
            group = group.sort_values(
                [
                    "recommendation_score", "degree_centrality", "followers",
                    "relevant_content_count", "content_count", "username",
                ],
                ascending=[False, False, False, False, False, True],
            )
            group = _select_balanced_account_type_candidates(group)
            selected_frames.append(group)

        if not selected_frames:
            return pd.DataFrame(columns=empty_columns), {
                "is_real": False,
                "source_name": f"{get_sentiment_source_name(layanan)} + {get_sna_source_names(layanan) if sna_file_exists(layanan) else 'SNA tidak tersedia'}",
                "actual_rows": 0,
                "content_authors": int(len(content_stats)),
            }

        result = pd.concat(selected_frames, ignore_index=True, sort=False)
        result = result.sort_values(
            ["platform", "recommendation_score", "degree_centrality", "followers"],
            ascending=[True, False, False, False],
        ).reset_index(drop=True)
        result["recommendation_rank"] = range(1, len(result) + 1)
        for column in empty_columns:
            if column not in result.columns:
                result[column] = 0 if column not in {
                    "username", "username_key", "platform", "dominant_topic",
                    "content_topics", "selection_basis", "layanan",
                } else ""
        result["layanan"] = layanan
        result = result[empty_columns]

        meta = {
            "is_real": bool(not result.empty and (sentiment_file_exists(layanan) or sna_file_exists(layanan))),
            "source_name": (
                f"{get_sentiment_source_name(layanan)} + "
                f"{get_sna_source_names(layanan) if sna_file_exists(layanan) else 'SNA tidak tersedia'}"
            ),
            "actual_rows": int(len(result)),
            "content_authors": int(len(content_stats)),
        }
        return result, meta
    except Exception as error:
        st.error(f"Gagal menyusun influencer {layanan}: {error}")
        return pd.DataFrame(columns=empty_columns), {
            "is_real": False,
            "source_name": "Konten asli tidak berhasil divalidasi",
            "actual_rows": 0,
            "content_authors": 0,
        }


def _filter_influencers_by_active_platform(
    influencers: pd.DataFrame,
    platform_label: str,
) -> pd.DataFrame:
    """Filter influencer agar hanya berasal dari platform aktif halaman."""
    try:
        if influencers is None or influencers.empty:
            return pd.DataFrame(columns=getattr(influencers, "columns", None))

        platform_map = {
            "Twitter": "twitter",
            "Twitter/X": "twitter",
            "X": "twitter",
            "Instagram": "instagram",
            "TikTok": "tiktok",
        }
        platform_key = platform_map.get(str(platform_label).strip())
        if not platform_key:
            return influencers.copy()

        if "platform" not in influencers.columns:
            return influencers.iloc[0:0].copy()

        filtered = influencers[
            influencers["platform"].astype(str).str.strip().str.lower().eq(platform_key)
        ].copy()
        if filtered.empty:
            return filtered

        filtered = filtered.sort_values(
            ["recommendation_score", "degree_centrality", "followers"],
            ascending=[False, False, False],
        ).reset_index(drop=True)
        filtered["recommendation_rank"] = range(1, len(filtered) + 1)
        return filtered
    except Exception as error:
        st.error(
            "Influencer belum dapat disaring berdasarkan platform aktif. "
            f"Detail: {type(error).__name__}."
        )
        return influencers.iloc[0:0].copy()


def _username_lookup_key(value: Any) -> str:
    """Normalisasi username untuk pencocokan lintas sumber data."""
    return re.sub(r"[^a-z0-9]+", "", str(value or "").strip().lower().lstrip("@"))


def _clean_content_text(value: Any) -> str:
    """Bersihkan spasi dan karakter kosong pada teks konten."""
    text = re.sub(r"\s+", " ", str(value or "")).strip()
    if text.lower() in {"", "nan", "none"}:
        return ""
    return text


def _shorten_text(value: Any, limit: int = 92) -> str:
    """Potong teks tanpa memutus kata di tengah jika memungkinkan."""
    text = _clean_content_text(value)
    if len(text) <= limit:
        return text
    shortened = text[: max(limit - 1, 1)].rsplit(" ", 1)[0].strip()
    return f"{shortened or text[:limit].strip()}…"


def _format_content_date(value: Any) -> str:
    """Format tanggal konten menjadi teks ringkas Bahasa Indonesia."""
    try:
        date_text = _clean_content_text(value)
        date_text = re.sub(
            r"(\d{1,2})\.(\d{2})\.(\d{2})$",
            r"\1:\2:\3",
            date_text,
        )
        parsed = pd.to_datetime(
            date_text, errors="coerce", dayfirst=True, format="mixed"
        )
        if pd.isna(parsed):
            return "Tanggal tidak tersedia"
        month_names = {
            1: "Jan", 2: "Feb", 3: "Mar", 4: "Apr", 5: "Mei", 6: "Jun",
            7: "Jul", 8: "Agu", 9: "Sep", 10: "Okt", 11: "Nov", 12: "Des",
        }
        return f"{int(parsed.day)} {month_names[int(parsed.month)]} {int(parsed.year)}"
    except Exception:
        return "Tanggal tidak tersedia"


def _infer_content_kind(row: pd.Series, platform: str) -> str:
    """Tentukan jenis konten asli dari metadata sumber."""
    raw_values = " ".join(
        _clean_content_text(row.get(column, "")).lower()
        for column in ("specific_type", "content_type", "post_type", "resource_type")
        if column in row.index
    )
    if platform == "twitter":
        if "reply" in raw_values:
            return "Balasan Twitter/X"
        if "retweet" in raw_values:
            return "Retweet"
        return "Tweet"
    if platform == "instagram":
        if "comment" in raw_values or "komentar" in raw_values:
            return "Komentar Instagram"
        if "reel" in raw_values or "video" in raw_values:
            return "Reels/Video Instagram"
        return "Konten Instagram"
    if platform == "tiktok":
        if "comment" in raw_values or "komentar" in raw_values:
            return "Komentar TikTok"
        if "video" in raw_values:
            return "Video TikTok"
        return "Konten TikTok"
    return "Konten Media Sosial"


def _safe_external_url(value: Any) -> str:
    """Izinkan hanya URL HTTP/HTTPS untuk tautan sumber konten."""
    text = _clean_content_text(value).lstrip("'")
    if re.match(r"^https?://", text, flags=re.IGNORECASE):
        return text
    return ""


def _detect_content_topic(value: Any) -> str:
    """Tentukan topik paling relevan dari teks konten."""
    content = _clean_content_text(value).lower()
    for topic in TOPIC_CONFIG:
        pattern = _topic_regex(topic["keywords"])
        if re.search(pattern, content, flags=re.IGNORECASE):
            return str(topic["singkat"])
    return "Percakapan Layanan"


def _content_relevance_score(value: Any, layanan: str) -> int:
    """Hitung relevansi teks terhadap layanan dan lima topik penelitian."""
    content = _clean_content_text(value).lower()
    if not content:
        return 0

    score = 0
    aliases = SERVICE_ALIASES.get(layanan, (layanan.lower(),))
    if any(alias.lower() in content for alias in aliases):
        score += 3
    for topic in TOPIC_CONFIG:
        if re.search(_topic_regex(topic["keywords"]), content, flags=re.IGNORECASE):
            score += 2
            break
    return score


def _calculate_content_rank(frame: pd.DataFrame) -> pd.Series:
    """Bangun skor ringan untuk memprioritaskan konten paling representatif."""
    score = pd.Series(0.0, index=frame.index, dtype="float64")
    if "engagement" in frame.columns:
        score = score + pd.to_numeric(frame["engagement"], errors="coerce").fillna(0)
    else:
        for column in ("like", "comment", "share", "reply_count", "retweet_count"):
            if column in frame.columns:
                score = score + pd.to_numeric(frame[column], errors="coerce").fillna(0)
    if "view" in frame.columns:
        score = score + (
            pd.to_numeric(frame["view"], errors="coerce").fillna(0) * 0.01
        )
    return score


def _row_engagement_value(row: pd.Series) -> int:
    """Ambil nilai engagement yang aman dari satu baris data."""
    try:
        if "engagement" in row.index:
            return max(int(float(row.get("engagement", 0) or 0)), 0)
        total = 0
        for column in ("like", "comment", "share", "reply_count", "retweet_count"):
            total += max(int(float(row.get(column, 0) or 0)), 0)
        return total
    except (TypeError, ValueError):
        return 0


def _collect_content_items(
    frame: pd.DataFrame,
    username_column: str,
    content_column: str,
    username_keys: set[str],
    source_label: str,
    layanan: str,
) -> dict[str, list[dict[str, Any]]]:
    """Kumpulkan konten aktual per username dari satu DataFrame."""
    result: dict[str, list[dict[str, Any]]] = {key: [] for key in username_keys}
    if frame is None or frame.empty:
        return result
    if username_column not in frame.columns or content_column not in frame.columns:
        return result

    # Normalisasi username secara vectorized dan filter maksimal sembilan akun
    # sebelum pembersihan konten. Baris yang tidak pernah ditampilkan tidak lagi
    # menjalani pemrosesan teks Python satu per satu.
    username_series = (
        frame[username_column]
        .fillna("")
        .astype(str)
        .str.strip()
        .str.lower()
        .str.lstrip("@")
        .str.replace(r"[^a-z0-9]+", "", regex=True)
    )
    mask = username_series.isin(username_keys)
    if not bool(mask.any()):
        return result

    work = frame.loc[mask].copy()
    work["_username_key"] = username_series.loc[mask].to_numpy()
    work["_content_clean"] = (
        work[content_column]
        .fillna("")
        .astype(str)
        .str.replace(r"\s+", " ", regex=True)
        .str.strip()
    )
    work.loc[
        work["_content_clean"].str.lower().isin(["nan", "none"]),
        "_content_clean",
    ] = ""
    work = work[work["_content_clean"].str.len().ge(8)].copy()
    if work.empty:
        return result

    work["_relevance_score"] = work["_content_clean"].map(
        lambda text: _content_relevance_score(text, layanan)
    )
    work = work[work["_relevance_score"].gt(0)].copy()
    if work.empty:
        return result
    work["_rank_score"] = (
        _calculate_content_rank(work)
        + work["_relevance_score"].astype(float) * 1_000_000
    )
    work = work.sort_values("_rank_score", ascending=False)

    for username_key, group in work.groupby("_username_key", sort=False):
        seen: set[str] = set()
        items: list[dict[str, Any]] = []
        for _, row in group.iterrows():
            content = _clean_content_text(row.get("_content_clean", ""))
            dedupe_key = re.sub(r"\W+", "", content.lower())[:220]
            if not dedupe_key or dedupe_key in seen:
                continue
            seen.add(dedupe_key)

            platform = str(row.get("platform", "")).strip().lower()
            sentiment = _normalisasi_sentimen(row.get("predicted_sentiment", "neutral"))
            date_value = row.get("date", row.get("date_created", ""))
            items.append(
                {
                    "text": content,
                    "topic": _detect_content_topic(content),
                    "platform": platform,
                    "sentiment": sentiment,
                    "engagement": _row_engagement_value(row),
                    "link": _safe_external_url(row.get("link", "")),
                    "date_label": _format_content_date(date_value),
                    "content_kind": _infer_content_kind(row, platform),
                    "source": source_label,
                    "is_actual": True,
                }
            )
            if len(items) >= 5:
                break
        result[str(username_key)] = items

    return result


@st.cache_data(show_spinner=False, max_entries=24)
def _build_influencer_content_catalog(
    layanan: str,
    usernames: tuple[str, ...],
    demo_mode: bool = False,
) -> dict[str, dict[str, Any]]:
    """Bangun katalog konten aktual dan bukti jaringan untuk setiap influencer."""
    username_map = {
        _username_lookup_key(username): _safe_username(username)
        for username in usernames
        if _username_lookup_key(username)
    }
    username_keys = set(username_map)
    catalog: dict[str, dict[str, Any]] = {
        key: {"actual_items": [], "network_evidence": []}
        for key in username_keys
    }
    if not username_keys:
        return catalog

    try:
        sentiment_df = (
            get_demo_sentiment(layanan).copy()
            if demo_mode
            else load_influencer_content_data(layanan).copy()
        )
        sentiment_items = _collect_content_items(
            sentiment_df,
            username_column="username",
            content_column="content",
            username_keys=username_keys,
            source_label=(
                "Mode Demo · komentar sample"
                if demo_mode
                else get_sentiment_source_name(layanan)
            ),
            layanan=layanan,
        )
        for key, items in sentiment_items.items():
            catalog[key]["actual_items"].extend(items)
    except Exception:
        pass

    try:
        sna_source = (
            get_demo_sna(layanan).copy()
            if demo_mode
            else load_sna_data(layanan).copy()
        )
        sna_df = _filter_sna_by_service(sna_source, layanan)
        if not sna_df.empty and "source" in sna_df.columns:
            work = sna_df.copy()
            work["_username_key"] = work["source"].map(_username_lookup_key)
            work = work[work["_username_key"].isin(username_keys)].copy()

            # Beberapa edge list menyimpan teks asli. Jika tersedia, gunakan juga
            # sebagai bukti konten aktual tanpa mengatribusikan teks akun lain.
            content_column = next(
                (
                    column
                    for column in (
                        "content", "text", "comment_text", "tweet_text",
                        "caption", "source_content", "post_content",
                    )
                    if column in work.columns
                ),
                None,
            )
            if content_column is not None:
                sna_items = _collect_content_items(
                    work,
                    username_column="source",
                    content_column=content_column,
                    username_keys=username_keys,
                    source_label="Edge list aktual",
                    layanan=layanan,
                )
                for key, items in sna_items.items():
                    existing = {
                        re.sub(r"\W+", "", str(item.get("text", "")).lower())[:220]
                        for item in catalog[key]["actual_items"]
                    }
                    for item in items:
                        item_key = re.sub(
                            r"\W+", "", str(item.get("text", "")).lower()
                        )[:220]
                        if item_key and item_key not in existing:
                            catalog[key]["actual_items"].append(item)
                            existing.add(item_key)

            for username_key, group in work.groupby("_username_key", sort=False):
                evidence: list[str] = []
                total_edges = int(len(group))
                if total_edges > 0:
                    evidence.append(
                        f"Terlibat dalam {total_edges} hubungan interaksi pada jaringan {layanan}."
                    )

                if "relationship" in group.columns:
                    relationships = (
                        group["relationship"]
                        .fillna("interaksi")
                        .astype(str)
                        .str.strip()
                        .replace("", "interaksi")
                        .value_counts()
                        .head(3)
                    )
                    if not relationships.empty:
                        relation_text = ", ".join(
                            f"{int(count)} {str(label).lower()}"
                            for label, count in relationships.items()
                        )
                        evidence.append(f"Pola aktivitas: {relation_text}.")

                if "target" in group.columns:
                    targets = [
                        _safe_username(value)
                        for value in group["target"].dropna().astype(str).tolist()
                        if _safe_username(value)
                    ]
                    unique_targets = list(dict.fromkeys(targets))[:3]
                    if unique_targets:
                        target_text = ", ".join(f"@{item}" for item in unique_targets)
                        evidence.append(f"Berinteraksi dengan {target_text}.")

                catalog[str(username_key)]["network_evidence"] = evidence[:3]
    except Exception:
        pass

    for key in catalog:
        catalog[key]["actual_items"] = catalog[key]["actual_items"][:5]
    return catalog


def _fallback_content_evidence(
    platform: str,
    tags: list[str],
    network_evidence: list[str],
) -> list[str]:
    """Siapkan tiga bukti aktivitas ketika teks konten asli tidak tersedia."""
    evidence = [_clean_content_text(item) for item in network_evidence if _clean_content_text(item)]
    topic_text = ", ".join(tags[:2]) if tags else "isu layanan"
    platform_templates = {
        "twitter": [
            f"Percakapan cepat terkait {topic_text}.",
            "Aktivitas mention, reply, atau penyebaran informasi pada jaringan X.",
            "Interaksi publik yang relevan untuk respons layanan real-time.",
        ],
        "instagram": [
            f"Interaksi pada konten visual terkait {topic_text}.",
            "Komentar dan percakapan yang membentuk jangkauan komunitas Instagram.",
            "Aktivitas audiens yang relevan untuk konten edukatif dan carousel.",
        ],
        "tiktok": [
            f"Interaksi video pendek terkait {topic_text}.",
            "Komentar dan respons yang berpotensi menyebarkan pesan secara cepat.",
            "Aktivitas komunitas yang relevan untuk format video singkat.",
        ],
    }
    for item in platform_templates.get(platform, platform_templates["twitter"]):
        if len(evidence) >= 3:
            break
        if item not in evidence:
            evidence.append(item)
    return evidence[:3]


def _get_influencer_content_payload(
    catalog_item: dict[str, Any],
) -> dict[str, Any]:
    """Siapkan hanya konten asli yang benar-benar ditemukan pada dataset."""
    actual_items = list(catalog_item.get("actual_items", []))[:5]
    return {
        "is_actual": bool(actual_items),
        "actual_items": actual_items,
        "network_evidence": list(catalog_item.get("network_evidence", []))[:3],
        "preview_items": [
            str(item.get("text", "")) for item in actual_items[:3]
        ],
    }



def _build_recommendation_action(
    layanan: str,
    platform: str,
    tags: list[str],
) -> str:
    """Bangun arahan pemanfaatan influencer berdasarkan platform dan topik."""
    topic_text = " dan ".join(tags[:2]) if tags else "isu layanan prioritas"
    templates = {
        "twitter": (
            f"Libatkan akun ini untuk thread klarifikasi, respons cepat, dan mention terarah "
            f"mengenai {topic_text}. Sertakan tautan kanal bantuan resmi {layanan} agar "
            "percakapan dapat diarahkan menuju penyelesaian yang terukur."
        ),
        "instagram": (
            f"Kolaborasikan akun ini pada carousel edukatif, Reels singkat, dan sesi tanya "
            f"jawab mengenai {topic_text}. Gunakan visual langkah demi langkah dan CTA "
            f"menuju kanal bantuan resmi {layanan}."
        ),
        "tiktok": (
            f"Libatkan akun ini untuk video pendek berbentuk simulasi masalah-solusi, tutorial, "
            f"atau respons komentar mengenai {topic_text}. Gunakan pembuka yang langsung pada "
            f"masalah dan arahkan penonton ke kanal resmi {layanan}."
        ),
    }
    return templates.get(platform, templates["twitter"])


def _build_influencer_strategy_prompt(
    *,
    layanan: str,
    platform: str,
    username: str,
    followers: int,
    degree: float,
    rank: int,
    selection_basis: str,
    tags: list[str],
    evidence_items: list[str],
) -> str:
    """Susun prompt Gemini untuk strategi pemanfaatan satu influencer."""
    platform_label = PLATFORM_META.get(platform, PLATFORM_META["twitter"])["label"]
    topic_text = ", ".join(tags[:5]) if tags else "isu layanan prioritas"
    evidence_text = " | ".join(
        _shorten_text(_clean_content_text(item), 240)
        for item in evidence_items[:3]
        if _clean_content_text(item)
    ) or "Tidak ada kutipan konten; gunakan metrik jaringan sebagai dasar."

    return f"""
Anda adalah analis komunikasi digital Telkom Group.
Susun strategi pemanfaatan influencer berdasarkan data yang diberikan, bukan asumsi.

KONTEKS:
- Layanan: {layanan}
- Platform: {platform_label}
- Username: @{username}
- Followers: {followers}
- Degree centrality: {degree:.6f}
- Peringkat rekomendasi: {rank if rank > 0 else 'tidak tersedia'}
- Dasar pemilihan: {selection_basis}
- Topik fokus: {topic_text}
- Bukti data: {evidence_text}

ATURAN:
1. Gunakan Bahasa Indonesia yang natural, spesifik, dan profesional.
2. Jangan mengarang angka, jabatan, lokasi, karakter pribadi, atau efektivitas yang tidak ada pada data.
3. Alasan pemilihan harus menjelaskan hubungan antara metrik, bukti konten, platform, dan topik.
4. Arah aktivasi harus sesuai karakter {platform_label}, aman, realistis, dan dapat dilaksanakan.
5. Maksimal 85 kata untuk setiap bagian.
6. Keluarkan tepat dua baris berikut tanpa pembuka, Markdown, atau bullet tambahan:

ALASAN|||alasan pemilihan akun
AKTIVASI|||arah aktivasi konten
""".strip()


def _parse_influencer_strategy_response(
    raw_text: str,
    fallback_reason: str,
    fallback_action: str,
) -> tuple[str, str, bool]:
    """Parse protokol dua baris Gemini dan kembalikan fallback jika tidak valid."""
    try:
        values: dict[str, str] = {}
        for raw_line in str(raw_text or "").splitlines():
            line = raw_line.strip().replace("**", "").replace("```", "")
            if "|||" not in line:
                continue
            key, value = line.split("|||", 1)
            key = re.sub(r"[^A-Z]", "", key.upper())
            cleaned = re.sub(r"\s+", " ", value).strip(" -:|\t\r\n")
            if key in {"ALASAN", "AKTIVASI"} and cleaned:
                values[key] = cleaned

        reason = values.get("ALASAN", "")
        action = values.get("AKTIVASI", "")
        if not reason or not action:
            return fallback_reason, fallback_action, False
        return reason, action, True
    except Exception:
        return fallback_reason, fallback_action, False


def _generate_influencer_strategy(
    *,
    layanan: str,
    platform: str,
    username: str,
    followers: int,
    degree: float,
    rank: int,
    selection_basis: str,
    tags: list[str],
    evidence_items: list[str],
    fallback_reason: str,
    fallback_action: str,
) -> tuple[str, str, str]:
    """Hasilkan strategi Gemini dengan cache 300 detik dan fallback lokal."""
    if bool(st.session_state.get("demo_mode", False)):
        return fallback_reason, fallback_action, "Mode Demo · fallback lokal"
    fallback_payload = (
        f"ALASAN|||{fallback_reason}\n"
        f"AKTIVASI|||{fallback_action}"
    )
    try:
        prompt = _build_influencer_strategy_prompt(
            layanan=layanan,
            platform=platform,
            username=username,
            followers=followers,
            degree=degree,
            rank=rank,
            selection_basis=selection_basis,
            tags=tags,
            evidence_items=evidence_items,
        )
        model = init_gemini()
        raw_result = generate_recommendation(
            model,
            prompt,
            fallback_text=fallback_payload,
        )
        reason, action, valid_ai = _parse_influencer_strategy_response(
            raw_result,
            fallback_reason,
            fallback_action,
        )
        source = "Gemini AI" if model is not None and valid_ai else "Fallback lokal"
        log_activity(
            "GEMINI_STRATEGY",
            "Rekomendasi",
            f"Menyusun strategi pemanfaatan akun @{username} untuk {layanan} di {platform}.",
            status="success" if source == "Gemini AI" else "warning",
            service=layanan,
            platform=platform,
            metadata={
                "influencer": username,
                "rank": rank,
                "source": source,
                "followers": followers,
            },
        )
        return reason, action, source
    except Exception as exc:
        log_activity(
            "GEMINI_STRATEGY",
            "Rekomendasi",
            f"Strategi Gemini untuk akun @{username} gagal dan menggunakan fallback lokal.",
            status="failed",
            service=layanan,
            platform=platform,
            metadata={"influencer": username, "error": str(exc)},
        )
        return fallback_reason, fallback_action, "Fallback lokal"


def _build_score_matrix(
    influencers: pd.DataFrame,
    layanan: str,
) -> pd.DataFrame:
    """Bangun skor kesesuaian influencer × topik secara deterministik."""
    try:
        service_offset = {
            "IndiHome": 0,
            "IndiBiz": 1,
            "Telkomsel": -1,
        }.get(layanan, 0)
        rows: list[dict[str, Any]] = []

        for platform in PLATFORM_ORDER:
            group = influencers[influencers["platform"].eq(platform)].reset_index(drop=True)
            base_scores = PLATFORM_TOPIC_BASE[platform]
            for rank, influencer in group.iterrows():
                row: dict[str, Any] = {
                    "username": _safe_username(influencer["username"]),
                    "platform": platform,
                    "tipe_akun": str(
                        influencer.get("tipe_akun", "influencer")
                    ).strip().lower(),
                }
                content_topics = {
                    _clean_content_text(item)
                    for item in str(influencer.get("content_topics", "")).split("|")
                    if _clean_content_text(item)
                }
                dominant_topic = _clean_content_text(
                    influencer.get("dominant_topic", "")
                )
                for index, topic in enumerate(TOPIC_CONFIG):
                    # Influencer peringkat pertama mendapat sedikit keunggulan.
                    rank_adjustment = max(0, 2 - int(rank))
                    score = int(base_scores[index]) + rank_adjustment - 1

                    # Penyesuaian layanan dibuat kecil dan konsisten.
                    if layanan == "IndiBiz" and topic["key"] in {
                        "harga_kualitas",
                        "apresiasi_layanan",
                    }:
                        score += service_offset
                    elif layanan == "Telkomsel" and topic["key"] in {
                        "gangguan_jaringan",
                        "harga_kualitas",
                    }:
                        score += 1

                    # Konten asli yang membahas topik tersebut menaikkan kesesuaian.
                    if str(topic["singkat"]) in content_topics:
                        score += 2
                    if dominant_topic == str(topic["singkat"]):
                        score += 1

                    row[str(topic["key"])] = max(1, min(10, score))
                rows.append(row)

        return pd.DataFrame(rows)
    except Exception:
        return pd.DataFrame()


def _top_influencers_for_topic(
    score_matrix: pd.DataFrame,
    topic_key: str,
    limit: int = 3,
) -> list[str]:
    """Ambil influencer dengan skor tertinggi untuk satu topik."""
    try:
        if score_matrix.empty or topic_key not in score_matrix.columns:
            return []
        ranked = score_matrix.sort_values(
            [topic_key, "username"],
            ascending=[False, True],
        )
        return ranked["username"].head(limit).astype(str).tolist()
    except Exception:
        return []


def _get_influencer_tags(
    platform: str,
    rank: int,
    top_topics: list[str],
    content_topics: list[str] | None = None,
) -> list[str]:
    """Tentukan tag dengan memprioritaskan topik konten asli akun."""
    platform_defaults = {
        "twitter": ["Gangguan Jaringan", "Bantuan Admin", "Provider Lain"],
        "instagram": ["Apresiasi Layanan", "Harga & Kualitas", "Bantuan Admin"],
        "tiktok": ["Gangguan Jaringan", "Apresiasi Layanan", "Harga & Kualitas"],
    }
    defaults = platform_defaults.get(platform, ["Gangguan Jaringan"])
    candidates = list(content_topics or []) + top_topics + defaults
    unique: list[str] = []
    for item in candidates[rank:] + candidates[:rank]:
        cleaned = _clean_content_text(item)
        if cleaned and cleaned not in unique and cleaned != "Percakapan Layanan":
            unique.append(cleaned)
        if len(unique) == 2:
            break
    if not unique:
        unique = defaults[:2]
    return unique[:2]


def _influencer_reason(
    influencer: pd.Series,
    tags: list[str],
    layanan: str,
) -> str:
    """Bangun alasan rekomendasi berbasis konten asli dan metrik akun."""
    platform = str(influencer.get("platform", "twitter"))
    followers = int(influencer.get("followers", 0))
    degree = float(influencer.get("degree_centrality", 0.0))
    content_count = int(influencer.get("relevant_content_count", 0))
    content_engagement = int(influencer.get("content_engagement", 0))
    basis = _clean_content_text(influencer.get("selection_basis", "Konten asli"))
    topic_text = " dan ".join(tags[:2]) if tags else "isu layanan"

    network_text = (
        f"degree centrality {degree:.3f}"
        if degree > 0
        else f"jangkauan {_format_number(followers)} followers"
    )
    engagement_text = (
        f" dengan total {_format_number(content_engagement)} engagement"
        if content_engagement > 0
        else ""
    )
    return (
        f"Akun ini direkomendasikan karena memiliki {content_count} konten asli yang relevan "
        f"terkait {topic_text}{engagement_text}, didukung {network_text}. "
        f"Dasar pemilihan: {basis} pada data {layanan}."
    )


# -----------------------------------------------------------------------------
# KONTEN STRATEGI
# -----------------------------------------------------------------------------


def _wrap_content_for_display(text: str, width: int = 42) -> str:
    """Pecah contoh konten menjadi beberapa baris agar tidak perlu scroll ke samping."""
    cleaned = re.sub(r"\s+", " ", str(text or "")).strip()
    if not cleaned:
        return "Konten belum tersedia."
    return fill(
        cleaned,
        width=width,
        break_long_words=False,
        break_on_hyphens=False,
    )



def _indibiz_business_topic_examples(topic_key: str) -> dict[str, str]:
    """Kembalikan contoh konten IndiBiz yang berorientasi UMKM dan korporasi."""
    templates = {
        "gangguan_jaringan": {
            "instagram": "Informasi layanan bisnis: tim IndiBiz sedang menangani gangguan konektivitas pada wilayah terdampak. Pantau tahapan pemulihan, estimasi penyelesaian, dan kanal eskalasi pada carousel ini.",
            "tiktok": "Tiga langkah menjaga operasional UMKM saat koneksi terganggu: aktifkan prosedur cadangan, catat dampak layanan, lalu kirim laporan lengkap melalui kanal resmi IndiBiz.",
            "twitter": "[PEMBARUAN LAYANAN] Penanganan gangguan IndiBiz sedang berlangsung. Pelanggan bisnis dapat mengirim nomor layanan, lokasi, dan dampak operasional melalui DM untuk proses eskalasi.",
        },
        "apresiasi_layanan": {
            "instagram": "Studi kasus pelanggan: koneksi IndiBiz membantu UMKM menjaga transaksi digital, sistem kasir, rapat daring, dan layanan pelanggan tetap berjalan pada jam operasional.",
            "tiktok": "Satu hari operasional usaha dengan koneksi stabil. Tampilkan proses transaksi, koordinasi tim, dan layanan pelanggan yang berjalan lebih efisien bersama IndiBiz.",
            "twitter": "Terima kasih atas kepercayaan pelanggan bisnis kepada IndiBiz. Masukan mengenai stabilitas, dukungan teknis, dan kebutuhan pengembangan layanan tetap kami catat sebagai dasar peningkatan.",
        },
        "perbandingan_provider": {
            "instagram": "Sebelum memilih internet bisnis, bandingkan cakupan, kestabilan, dukungan teknis, kapasitas perangkat, kebutuhan unggah, dan risiko gangguan terhadap operasional.",
            "tiktok": "Internet bisnis tidak cukup dibandingkan dari harga. Evaluasi kebutuhan bandwidth, jam operasional, jumlah perangkat, SLA, dan dukungan teknis sebelum mengambil keputusan.",
            "twitter": "Perbandingan layanan internet bisnis perlu memakai parameter yang setara: wilayah, kapasitas, jumlah perangkat, pola penggunaan, dukungan teknis, dan total biaya operasional.",
        },
        "harga_kualitas": {
            "instagram": "Hitung kebutuhan paket IndiBiz berdasarkan jumlah perangkat, aplikasi bisnis, aktivitas cloud, sistem kasir, konferensi video, dan target produktivitas usaha.",
            "tiktok": "Paket internet bisnis terasa kurang efisien? Audit pemakaian perangkat, aktivitas unggah, jam sibuk, dan kebutuhan aplikasi sebelum menyesuaikan kapasitas layanan.",
            "twitter": "Pelanggan IndiBiz dapat meminta evaluasi paket berdasarkan profil operasional. Kirim nomor layanan dan kebutuhan bisnis melalui kanal resmi untuk memperoleh opsi yang lebih sesuai.",
        },
        "bantuan_admin": {
            "instagram": "Agar tiket pelanggan bisnis diproses lebih cepat, siapkan nomor layanan, alamat, waktu kejadian, indikator perangkat, serta dampak gangguan terhadap operasional.",
            "tiktok": "Format laporan gangguan untuk UMKM: nomor layanan, lokasi, waktu kejadian, kondisi perangkat, dan aktivitas bisnis yang terdampak. Data lengkap mempercepat eskalasi.",
            "twitter": "Tim IndiBiz siap membantu. Kirim nomor layanan, lokasi, kronologi, dan dampak operasional melalui DM. Hindari membagikan data sensitif perusahaan di ruang publik.",
        },
    }
    return templates.get(topic_key, templates["bantuan_admin"])


def _content_examples(layanan: str, topic_key: str) -> dict[str, str]:
    """Kembalikan tiga contoh konten siap pakai untuk satu topik."""
    if layanan == "IndiBiz":
        return _indibiz_business_topic_examples(topic_key)
    service_hashtag = layanan.replace(" ", "")
    templates: dict[str, dict[str, str]] = {
        "gangguan_jaringan": {
            "instagram": (
                f"Koneksi {layanan} sedang mengalami kendala? Simpan panduan ini: "
                "1) restart perangkat, 2) periksa indikator jaringan, 3) kirim detail lokasi "
                f"melalui kanal resmi. Tim kami terus memantau pemulihan. #{service_hashtag}"
            ),
            "tiktok": (
                f"POV: internet {layanan} tiba-tiba tidak stabil. Coba tiga langkah cepat ini "
                "sebelum menghubungi admin. Tulis wilayahmu di komentar agar tim dapat mengecek."
            ),
            "twitter": (
                f"[INFO] Kami sedang menindaklanjuti laporan gangguan jaringan {layanan}. "
                "Silakan kirim nomor layanan dan wilayah melalui DM. Pembaruan penanganan akan "
                "disampaikan secara berkala di thread ini."
            ),
        },
        "apresiasi_layanan": {
            "instagram": (
                f"Terima kasih sudah berbagi pengalaman bersama {layanan}. Cerita pelanggan "
                "membantu kami mempertahankan layanan yang cepat, stabil, dan lebih dekat dengan "
                f"kebutuhan Anda. Bagikan momen terbaikmu dengan #{service_hashtag}."
            ),
            "tiktok": (
                f"Satu hari produktif ditemani {layanan}: meeting lancar, belajar nyaman, hiburan "
                "tanpa jeda. Ceritakan aktivitas yang paling terbantu oleh koneksi kamu."
            ),
            "twitter": (
                f"Kami senang membaca pengalaman positif pelanggan {layanan}. Terima kasih atas "
                "kepercayaannya. Masukan Anda tetap kami tunggu agar kualitas layanan terus meningkat."
            ),
        },
        "perbandingan_provider": {
            "instagram": (
                f"Sebelum memilih layanan internet, bandingkan kebutuhan—bukan hanya angka. "
                f"Perhatikan cakupan, stabilitas, dukungan pelanggan, dan paket {layanan} yang paling sesuai."
            ),
            "tiktok": (
                f"{layanan} vs provider lain: apa saja yang perlu dibandingkan? Cakupan wilayah, "
                "stabilitas, kebutuhan perangkat, layanan bantuan, dan total biaya bulanan."
            ),
            "twitter": (
                f"Membandingkan {layanan} dengan provider lain? Pastikan perbandingan dilakukan "
                "pada wilayah, kebutuhan, paket, dan periode penggunaan yang sama agar hasilnya adil."
            ),
        },
        "harga_kualitas": {
            "instagram": (
                f"Pilih paket {layanan} berdasarkan pola pemakaian. Hitung jumlah perangkat, "
                "aktivitas utama, kebutuhan kecepatan, dan batas anggaran agar manfaat yang diterima seimbang."
            ),
            "tiktok": (
                f"Kuota atau tagihan terasa mahal? Cek kembali paket {layanan}, pemakaian harian, "
                "fitur aktif, dan kebutuhan perangkat. Paket yang tepat bisa membantu penggunaan lebih efisien."
            ),
            "twitter": (
                f"Kami memahami perhatian pelanggan terhadap harga dan kualitas {layanan}. Kirim "
                "detail paket melalui DM agar tim dapat membantu mengecek opsi yang lebih sesuai kebutuhan."
            ),
        },
        "bantuan_admin": {
            "instagram": (
                f"Butuh bantuan {layanan}? Siapkan nomor layanan, lokasi, waktu kejadian, dan foto "
                "indikator perangkat. Data yang lengkap membantu admin memberi solusi lebih cepat."
            ),
            "tiktok": (
                f"Biar laporan {layanan} cepat diproses, jangan cuma tulis 'tolong'. Sertakan nomor "
                "layanan, wilayah, waktu gangguan, dan kondisi indikator perangkat."
            ),
            "twitter": (
                f"Halo, kami siap membantu kendala {layanan}. Silakan kirim nomor layanan, wilayah, "
                "dan kronologi melalui DM. Hindari mencantumkan data pribadi di ruang publik."
            ),
        },
    }
    return templates.get(topic_key, templates["bantuan_admin"])


def _strategic_points(
    layanan: str,
    topic_summary: pd.DataFrame,
    influencers: pd.DataFrame,
) -> list[str]:
    """Bangun tiga rekomendasi utama yang dapat langsung ditindaklanjuti."""
    dominant = topic_summary.sort_values(
        ["jumlah_komentar", "topik"],
        ascending=[False, True],
    ).iloc[0]

    def top_username(platform: str) -> str | None:
        """Ambil akun terbaik per platform; None berarti belum tervalidasi."""
        if influencers is None or influencers.empty or "platform" not in influencers.columns:
            return None
        subset = influencers[influencers["platform"].eq(platform)].copy()
        if subset.empty:
            return None
        return _safe_username(subset.iloc[0].get("username", "")) or None

    visual_accounts = [
        account
        for account in (top_username("tiktok"), top_username("instagram"))
        if account
    ]
    twitter_account = top_username("twitter")

    if len(visual_accounts) >= 2:
        visual_text = (
            f"Libatkan <strong>@{escape(visual_accounts[0])}</strong> dan "
            f"<strong>@{escape(visual_accounts[1])}</strong> untuk memperluas konten visual, "
            "video pendek, serta narasi pengalaman pelanggan."
        )
    elif len(visual_accounts) == 1:
        visual_text = (
            f"Gunakan <strong>@{escape(visual_accounts[0])}</strong> sebagai kandidat visual utama, "
            "lalu lengkapi satu kandidat tambahan dari Instagram atau TikTok setelah konten aslinya tervalidasi."
        )
    else:
        visual_text = (
            f"Gunakan akun resmi {escape(layanan)} atau kreator internal sebagai pengganti sementara, "
            "sambil melengkapi validasi konten influencer Instagram/TikTok agar rekomendasi tidak memakai akun placeholder."
        )

    if twitter_account:
        twitter_text = (
            f"Gunakan Twitter/X bersama <strong>@{escape(twitter_account)}</strong> untuk "
            "respons cepat, klarifikasi berbentuk thread, dan pengalihan data pribadi pelanggan ke DM."
        )
    else:
        twitter_text = (
            f"Siapkan template respons cepat di kanal resmi {escape(layanan)} untuk klarifikasi thread, "
            "jawaban publik, dan pengalihan data pribadi pelanggan ke DM sampai kandidat Twitter/X tervalidasi."
        )

    return [
        (
            f"Prioritaskan konten edukatif dan pembaruan penanganan untuk "
            f"<strong>{escape(str(dominant['topik']))}</strong>, karena topik ini memiliki "
            f"volume percakapan tertinggi pada data {escape(layanan)}."
        ),
        visual_text,
        twitter_text,
    ]


# -----------------------------------------------------------------------------
# KOMPONEN TAMPILAN
# -----------------------------------------------------------------------------


def _render_section_header(kicker: str, title: str, description: str) -> None:
    """Tampilkan judul section yang konsisten dengan tema halaman."""
    st.markdown(
        f"""
        <div class="rec-section-head">
            <div>
                <div class="rec-section-kicker">{escape(kicker)}</div>
                <h2 class="rec-section-title">{escape(title)}</h2>
                <p class="rec-section-desc">{escape(description)}</p>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def _status_badge(label: str, status_class: str) -> str:
    """Bangun satu badge status berbentuk HTML."""
    return f'<span class="rec-status {escape(status_class)}">{escape(label)}</span>'


def _topic_visual_meta(topic_key: str) -> dict[str, str]:
    """Ambil ikon dan warna visual untuk setiap topik strategi."""
    visual = {
        "gangguan_jaringan": {"icon": "🔴", "color": "#E53935", "soft": "rgba(229,57,53,.14)"},
        "apresiasi_layanan": {"icon": "🟢", "color": "#4CAF50", "soft": "rgba(76,175,80,.14)"},
        "perbandingan_provider": {"icon": "🟣", "color": "#7C4DFF", "soft": "rgba(124,77,255,.14)"},
        "harga_kualitas": {"icon": "🟠", "color": "#FF9800", "soft": "rgba(255,152,0,.14)"},
        "bantuan_admin": {"icon": "🔵", "color": "#00BCD4", "soft": "rgba(0,188,212,.14)"},
        "bisnis_digitalisasi": {"icon": "🟣", "color": "#8B5CF6", "soft": "rgba(139,92,246,.14)"},
        "kecepatan_stabil": {"icon": "🟢", "color": "#22C55E", "soft": "rgba(34,197,94,.14)"},
        "kuota_masa_aktif": {"icon": "🔵", "color": "#1DA1F2", "soft": "rgba(29,161,242,.14)"},
    }
    return visual.get(str(topic_key), {"icon": "⚪", "color": "#BDBDBD", "soft": "rgba(189,189,189,.12)"})


def _render_context_card(
    layanan: str,
    topic_meta: dict[str, Any],
    influencer_meta: dict[str, Any],
) -> None:
    """Tampilkan badge isu dominan dan status sumber data."""
    model_status = load_model_status().get(str(layanan).lower(), "coming_soon")
    if model_status == "ready":
        model_label = "Model IndoBERT aktif"
    elif model_status == "downloadable":
        model_label = "Model siap · unduh ke folder layanan saat prediksi"
    else:
        model_label = "Data siap · model IndoBERT belum tersedia"
    sentiment_status = (
        _status_badge("● Data topik aktual", "actual")
        if topic_meta.get("is_real")
        else _status_badge("● Data topik fallback", "fallback")
    )
    sna_status = (
        _status_badge("● Influencer tervalidasi konten", "actual")
        if influencer_meta.get("is_real")
        else _status_badge("● Konten influencer belum valid", "fallback")
    )

    issue_label = (
        f"Isu Utama: {topic_meta.get('dominant_issue', 'Gangguan Jaringan')} — "
        f"{float(topic_meta.get('negative_pct', 0.0)):.1f}% Negatif"
    )

    st.markdown(
        f"""
        <div class="rec-context-card">
            <div>
                <div class="rec-issue-label">Konteks rekomendasi {escape(layanan)}</div>
                <div class="rec-issue-value">{escape(issue_label)}</div>
            </div>
            <div class="rec-status-row">
                {sentiment_status}
                {sna_status}
                {_status_badge(model_label, 'model')}
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def _topic_badge_style(tag: str) -> str:
    """Ambil CSS variable warna untuk badge topik influencer."""
    try:
        text = str(tag).lower().strip()
        if any(keyword in text for keyword in ("gangguan", "jaringan", "sinyal", "lemot", "down")):
            meta = TOPIC_BADGE_COLORS["gangguan_jaringan"]
        elif any(keyword in text for keyword in ("apresiasi", "brand", "layanan", "puas", "positif")):
            meta = TOPIC_BADGE_COLORS["apresiasi_layanan"]
        elif any(keyword in text for keyword in ("provider", "starlink", "kompetitor", "perbandingan")):
            meta = TOPIC_BADGE_COLORS["perbandingan_provider"]
        elif any(keyword in text for keyword in ("harga", "kualitas", "kuota", "tagihan", "mahal", "paket")):
            meta = TOPIC_BADGE_COLORS["harga_kualitas"]
        elif any(keyword in text for keyword in ("bantuan", "admin", "cs", "dm", "respon", "respons", "interaksi")):
            meta = TOPIC_BADGE_COLORS["bantuan_admin"]
        else:
            meta = TOPIC_BADGE_COLORS["default"]
        return (
            f"--tag-color:{meta['warna']};"
            f"--tag-border:{meta['border']};"
            f"--tag-bg:{meta['background']};"
        )
    except Exception:
        meta = TOPIC_BADGE_COLORS["default"]
        return (
            f"--tag-color:{meta['warna']};"
            f"--tag-border:{meta['border']};"
            f"--tag-bg:{meta['background']};"
        )



def _render_influencer_card(
    influencer: pd.Series,
    tags: list[str],
    content_payload: dict[str, Any],
) -> None:
    """Tampilkan kartu influencer dengan metrik akun dan bukti pendukung."""
    username = _safe_username(influencer.get("username"))
    platform = str(influencer.get("platform", "twitter")).lower()
    meta = PLATFORM_META.get(platform, PLATFORM_META["twitter"])
    followers = int(float(influencer.get("followers", 0) or 0))
    degree = float(influencer.get("degree_centrality", 0.0) or 0.0)
    layanan = str(influencer.get("layanan", ""))
    rank = int(float(influencer.get("recommendation_rank", 0) or 0))
    account_type = str(influencer.get("tipe_akun", "influencer")).strip().lower()
    account_type_label = escape(_account_type_label(account_type))
    initial = escape(username[:1].upper() or "?")
    tag_html = "".join(
        f'<span class="rec-tag" style="{_topic_badge_style(tag)}">{escape(tag)}</span>'
        for tag in tags
    )
    rank_html = (
        f'<span class="rec-top-influencer-badge">★ Top Influencer #{rank}</span>'
        if layanan == "IndiBiz" and rank > 0
        else ""
    )

    actual_items = list(content_payload.get("actual_items", []))[:3]
    if actual_items:
        preview_html = "".join(
            dedent(
                f"""
                <li>
                    <span class="rec-content-index">{index:02d}</span>
                    <span>
                        {escape(_clean_content_text(item.get('text', '')))}
                        <small class="rec-content-preview-meta">
                            {escape(str(item.get('content_kind', 'Konten asli')))} ·
                            {escape(str(item.get('date_label', 'Tanggal tidak tersedia')))}
                        </small>
                    </span>
                </li>
                """
            ).strip()
            for index, item in enumerate(actual_items, start=1)
        )
        source_label = "Bukti konten"
        preview_title = "Konten asli yang relevan"
    else:
        evidence = _fallback_content_evidence(
            platform,
            tags,
            list(content_payload.get("network_evidence", [])),
        )
        preview_html = "".join(
            f'<li><span class="rec-content-index">{index:02d}</span><span>{escape(item)}</span></li>'
            for index, item in enumerate(evidence, start=1)
        )
        source_label = "Metrik SNA"
        preview_title = "Dasar pemilihan akun"

    # Padatkan HTML menjadi satu baris agar Markdown Streamlit tidak membaca
    # bagian kartu sebagai blok kode ketika badge ranking IndiHome kosong.
    card_html = dedent(
        f"""
        <article class="rec-influencer-card" style="--platform-color:{meta['warna']};">
            <div class="rec-card-top">
                <div class="rec-avatar">{initial}</div>
                <div style="display:flex;gap:.4rem;flex-wrap:wrap;justify-content:flex-end;">
                    <span class="rec-platform-badge">
                        {escape(meta['ikon'])} {escape(meta['label'])}
                    </span>
                    <span class="rec-platform-badge">{account_type_label}</span>
                </div>
            </div>
            {rank_html}
            <h3 class="rec-username">@{escape(username)}</h3>
            <div class="rec-metric-row">
                <div class="rec-mini-metric">
                    <span class="rec-mini-label">Followers</span>
                    <span class="rec-mini-value">{_format_number(followers)}</span>
                </div>
                <div class="rec-mini-metric">
                    <span class="rec-mini-label">Degree Centrality</span>
                    <span class="rec-mini-value">{degree:.3f}</span>
                </div>
            </div>
            <div class="rec-tags">{tag_html}</div>
            <div class="rec-content-preview">
                <div class="rec-content-preview-head">
                    <span class="rec-content-preview-title">{escape(preview_title)}</span>
                    <span class="rec-content-source-badge">{escape(source_label)}</span>
                </div>
                <div
                    class="rec-content-scroll"
                    tabindex="0"
                    role="region"
                    aria-label="Bukti influencer. Gulir vertikal untuk membaca seluruh isi."
                    title="Gulir vertikal untuk membaca seluruh isi"
                >
                    <ul class="rec-content-list">{preview_html}</ul>
                </div>
            </div>
        </article>
        """
    ).strip()
    card_html = "".join(line.strip() for line in card_html.splitlines())
    st.markdown(card_html, unsafe_allow_html=True)





def _render_influencer_detail_inline(
    layanan: str,
    row: pd.Series,
    tags: list[str],
    reason: str,
    content_payload: dict[str, Any],
) -> None:
    """Tampilkan panel detail influencer yang visual, interaktif, dan responsif."""
    username = _safe_username(row.get("username", "akun"))
    platform = str(row.get("platform", "twitter")).lower()
    meta = PLATFORM_META.get(platform, PLATFORM_META["twitter"])
    detail_accent = {
        "twitter": "#1DA1F2",
        "instagram": "#C13584",
        "tiktok": "#25F4EE",
    }.get(platform, "#E53935")

    clean_tags = [
        _clean_content_text(tag)
        for tag in tags
        if _clean_content_text(tag)
    ]
    tag_text = ", ".join(clean_tags) if clean_tags else "Topik layanan"
    actual_items = list(content_payload.get("actual_items", []))[:5]
    network_evidence = _fallback_content_evidence(
        platform,
        clean_tags,
        list(content_payload.get("network_evidence", [])),
    )
    recommendation_action = _build_recommendation_action(
        layanan,
        platform,
        clean_tags,
    )

    content_parts: list[str] = []
    if actual_items:
        for index, item in enumerate(actual_items, start=1):
            link = _safe_external_url(item.get("link", ""))
            link_html = (
                f'<a class="rec-detail-source-link" href="{escape(link, quote=True)}" '
                f'target="_blank" rel="noopener noreferrer">Buka sumber asli ↗</a>'
                if link
                else ""
            )
            content_parts.append(
                dedent(
                    f"""
                    <div class="rec-detail-content-item">
                        <span class="rec-detail-content-number">{index:02d}</span>
                        <div>
                            <p class="rec-detail-content-text">{escape(_shorten_text(item.get('text', ''), 420))}</p>
                            <div class="rec-detail-content-meta">
                                <span>{escape(str(item.get('content_kind', 'Konten asli')))}</span>
                                <span>•</span>
                                <span>{escape(str(item.get('date_label', 'Tanggal tidak tersedia')))}</span>
                                <span>•</span>
                                <span>{escape(str(item.get('topic', 'Percakapan Layanan')))}</span>
                                <span>•</span>
                                <span>{escape(SENTIMENT_LABELS.get(str(item.get('sentiment', 'neutral')), 'Netral'))}</span>
                                <span>•</span>
                                <span>{_format_number(item.get('engagement', 0))} engagement</span>
                            </div>
                            {link_html}
                        </div>
                    </div>
                    """
                ).strip()
            )
        evidence_title = "Bukti konten asli dari dataset"
        evidence_kicker = "Konten tervalidasi"
        evidence_icon = "▣"
        evidence_count = len(actual_items)
        evidence_note = "Konten aktual yang relevan"
    else:
        for index, item in enumerate(network_evidence, start=1):
            content_parts.append(
                dedent(
                    f"""
                    <div class="rec-detail-content-item">
                        <span class="rec-detail-content-number">{index:02d}</span>
                        <div><p class="rec-detail-content-text">{escape(item)}</p></div>
                    </div>
                    """
                ).strip()
            )
        evidence_title = "Bukti posisi akun pada jaringan SNA"
        evidence_kicker = "Metrik jaringan"
        evidence_icon = "⌘"
        evidence_count = len(network_evidence)
        evidence_note = "Indikator struktural jaringan"

    content_html = "".join(content_parts)
    selection_basis = _clean_content_text(
        row.get("selection_basis", "Followers + degree centrality")
    )
    followers = int(float(row.get("followers", 0) or 0))
    degree = float(row.get("degree_centrality", 0.0) or 0.0)
    rank = int(float(row.get("recommendation_rank", 0) or 0))

    strategy_evidence = [
        _clean_content_text(item.get("text", ""))
        for item in actual_items[:3]
        if _clean_content_text(item.get("text", ""))
    ]
    if not strategy_evidence:
        strategy_evidence = list(network_evidence[:3])

    reason, recommendation_action, strategy_source = _generate_influencer_strategy(
        layanan=layanan,
        platform=platform,
        username=username,
        followers=followers,
        degree=degree,
        rank=rank,
        selection_basis=selection_basis,
        tags=clean_tags,
        evidence_items=strategy_evidence,
        fallback_reason=reason,
        fallback_action=recommendation_action,
    )

    primary_topic = clean_tags[0] if clean_tags else "Percakapan layanan"
    topic_chip_html = "".join(
        f'<span class="rec-detail-topic-chip">{escape(tag)}</span>'
        for tag in clean_tags[:5]
    )
    if not topic_chip_html:
        topic_chip_html = '<span class="rec-detail-topic-chip">Percakapan layanan</span>'

    rank_value = f"#{rank}" if rank > 0 else "Terpilih"
    detail_html = dedent(
        f"""
        <section class="rec-detail-panel" style="--detail-accent:{detail_accent};">
            <div class="rec-detail-header">
                <div class="rec-detail-identity">
                    <div class="rec-detail-platform-icon">{escape(meta['ikon'])}</div>
                    <div>
                        <span class="rec-detail-eyebrow">Profil influencer terpilih</span>
                        <h4>Detail rekomendasi <strong>@{escape(username)}</strong></h4>
                        <div class="rec-detail-subtitle">{escape(meta['label'])} · {escape(layanan)} · Analisis berbasis data</div>
                    </div>
                </div>
                <span class="rec-detail-live-badge">Analisis aktif</span>
            </div>

            <div class="rec-detail-stat-grid">
                <div class="rec-detail-stat-card">
                    <span class="rec-detail-stat-label">Followers</span>
                    <strong class="rec-detail-stat-value">{_format_number(followers)}</strong>
                    <span class="rec-detail-stat-note">Potensi jangkauan akun</span>
                </div>
                <div class="rec-detail-stat-card">
                    <span class="rec-detail-stat-label">Degree Centrality</span>
                    <strong class="rec-detail-stat-value">{degree:.3f}</strong>
                    <span class="rec-detail-stat-note">Kekuatan posisi jaringan</span>
                </div>
                <div class="rec-detail-stat-card">
                    <span class="rec-detail-stat-label">Bukti Analitik</span>
                    <strong class="rec-detail-stat-value">{evidence_count}</strong>
                    <span class="rec-detail-stat-note">{escape(evidence_note)}</span>
                </div>
                <div class="rec-detail-stat-card">
                    <span class="rec-detail-stat-label">Peringkat Rekomendasi</span>
                    <strong class="rec-detail-stat-value">{escape(rank_value)}</strong>
                    <span class="rec-detail-stat-note">Topik utama: {escape(primary_topic)}</span>
                </div>
            </div>

            <div class="rec-detail-topic-row">
                <span class="rec-detail-topic-label">Topik fokus</span>
                {topic_chip_html}
            </div>

            <div class="rec-detail-grid">
                <div class="rec-detail-block rec-detail-block-evidence" tabindex="0">
                    <div class="rec-detail-block-head">
                        <div class="rec-detail-block-title-wrap">
                            <span class="rec-detail-block-icon">{evidence_icon}</span>
                            <div>
                                <span class="rec-detail-block-kicker">{escape(evidence_kicker)}</span>
                                <div class="rec-detail-block-title">{escape(evidence_title)}</div>
                            </div>
                        </div>
                        <span class="rec-detail-count-badge">{evidence_count} bukti</span>
                    </div>
                    <div class="rec-detail-content-list">{content_html}</div>
                </div>

                <div class="rec-detail-block rec-detail-block-strategy" tabindex="0">
                    <div class="rec-detail-block-head">
                        <div class="rec-detail-block-title-wrap">
                            <span class="rec-detail-block-icon">✦</span>
                            <div>
                                <span class="rec-detail-block-kicker">Rekomendasi strategis</span>
                                <div class="rec-detail-block-title">Strategi pemanfaatan akun</div>
                            </div>
                        </div>
                        <span class="rec-detail-count-badge">{escape(strategy_source)}</span>
                    </div>
                    <div class="rec-detail-strategy-stack">
                        <div class="rec-detail-strategy-card">
                            <span class="rec-detail-strategy-number">01</span>
                            <div>
                                <strong class="rec-detail-strategy-title">Alasan pemilihan</strong>
                                <p class="rec-detail-recommendation">{escape(reason)}</p>
                            </div>
                        </div>
                        <div class="rec-detail-strategy-card">
                            <span class="rec-detail-strategy-number">02</span>
                            <div>
                                <strong class="rec-detail-strategy-title">Arah aktivasi konten</strong>
                                <p class="rec-detail-recommendation">{escape(recommendation_action)}</p>
                            </div>
                        </div>
                    </div>
                    <div class="rec-detail-basis-row">
                        <span>Dasar pemilihan</span>
                        <strong>{escape(selection_basis)}</strong>
                    </div>
                </div>
            </div>
        </section>
        """
    ).strip()

    # Padatkan HTML menjadi satu baris agar parser Markdown Streamlit tidak
    # membaca tag penutup sebagai blok kode yang tampil di antarmuka.
    detail_html = "".join(line.strip() for line in detail_html.splitlines())
    st.markdown(detail_html, unsafe_allow_html=True)


def _render_missing_influencer_card(platform: str) -> None:
    """Tampilkan slot kosong ketika kandidat belum memiliki konten tervalidasi."""
    meta = PLATFORM_META.get(platform, PLATFORM_META["twitter"])
    st.markdown(
        f"""
        <article class="rec-influencer-card rec-placeholder-card"
                 style="--platform-color:{meta['warna']};">
            <div class="rec-placeholder-icon">{escape(meta['ikon'])}</div>
            <h3 class="rec-placeholder-title">Belum ada kandidat tervalidasi</h3>
            <p class="rec-placeholder-text">
                Slot ini hanya diisi jika akun memiliki metrik influencer dan
                konten asli yang relevan pada dataset {escape(meta['label'])}.
            </p>
        </article>
        """,
        unsafe_allow_html=True,
    )



def _render_influencer_entry(
    layanan: str,
    row: pd.Series,
    slot: int,
    top_topics: list[str],
    content_catalog: dict[str, dict[str, Any]],
) -> dict[str, Any] | None:
    """Render kartu dan kembalikan data detail agar tampil di luar kolom."""
    username = _safe_username(row["username"])
    username_key = _username_lookup_key(username)
    content_payload = _get_influencer_content_payload(
        content_catalog.get(
            username_key,
            {"actual_items": [], "network_evidence": []},
        )
    )
    row_topics = [
        item
        for item in str(row.get("content_topics", "")).split("|")
        if _clean_content_text(item)
    ]
    item_topics = [
        str(item.get("topic", ""))
        for item in content_payload.get("actual_items", [])
        if _clean_content_text(item.get("topic", ""))
    ]
    platform = str(row.get("platform", "twitter"))
    tags = _get_influencer_tags(
        platform,
        slot,
        top_topics,
        row_topics + item_topics,
    )
    reason = _influencer_reason(row, tags, layanan)

    _render_influencer_card(row, tags, content_payload)
    # Username yang sama dapat hadir pada lebih dari satu platform (contoh:
    # @kompascom di Twitter/X dan Instagram). Identitas detail dan key widget
    # wajib menyertakan platform agar Streamlit tidak membuat key tombol ganda.
    selection_key = f"{layanan}|{platform}|{username}"
    is_selected = (
        str(st.session_state.get("rec_selected_influencer", ""))
        == selection_key
    )
    button_label = "Tutup Detail" if is_selected else "Lihat Detail"

    if st.button(
        button_label,
        key=(
            f"rec_detail_{_safe_key(layanan)}_{_safe_key(platform)}_"
            f"{_safe_key(username)}_{slot}"
        ),
        type="secondary",
        use_container_width=True,
    ):
        # Simpan label loading sebelum rerun. Pada siklus berikutnya, overlay
        # custom proyek tampil sejak awal render dan menutupi proses pembentukan
        # panel detail agar pengguna tidak melihat perubahan UI setengah jadi.
        if is_selected:
            st.session_state[RECOMMENDATION_ACTION_LOADING_KEY] = (
                f"Menutup detail influencer @{username}..."
            )
            st.session_state["rec_selected_influencer"] = ""
        else:
            st.session_state[RECOMMENDATION_ACTION_LOADING_KEY] = (
                f"Memuat detail influencer @{username}..."
            )
            st.session_state["rec_selected_influencer"] = selection_key

        st.rerun()

    if is_selected:
        return {
            "layanan": layanan,
            "row": row,
            "tags": tags,
            "reason": reason,
            "content_payload": content_payload,
        }
    return None



def _render_influencer_grid(
    layanan: str,
    influencers: pd.DataFrame,
    topic_summary: pd.DataFrame,
    influencer_meta: dict[str, Any] | None = None,
) -> None:
    """Tampilkan sembilan influencer dari platform aktif dalam grid 3 × 3."""
    if influencers is None or influencers.empty:
        _render_influencer_empty_state(layanan, influencer_meta)
        return

    top_topics = (
        topic_summary.sort_values("jumlah_komentar", ascending=False)["topik_singkat"]
        .astype(str)
        .tolist()
    )
    ranked = influencers.sort_values(
        ["recommendation_rank", "recommendation_score", "degree_centrality", "followers"],
        ascending=[True, False, False, False],
    ).head(9).reset_index(drop=True)

    usernames = tuple(ranked["username"].astype(str).tolist())
    content_catalog = _build_influencer_content_catalog(
        layanan,
        usernames,
        demo_mode=bool(st.session_state.get("demo_mode", False)),
    )

    selected_state = str(st.session_state.get("rec_selected_influencer", ""))
    if selected_state and not selected_state.startswith(f"{layanan}|"):
        st.session_state["rec_selected_influencer"] = ""

    platform = (
        str(ranked.iloc[0].get("platform", "twitter")).lower()
        if not ranked.empty
        else "twitter"
    )

    for row_start in range(0, 9, 3):
        columns = st.columns(3, gap="medium")
        selected_detail: dict[str, Any] | None = None
        for column_offset, column in enumerate(columns):
            slot = row_start + column_offset
            with column:
                if slot >= len(ranked):
                    _render_missing_influencer_card(platform)
                    st.button(
                        "Belum Tervalidasi",
                        key=(
                            f"rec_missing_{_safe_key(layanan)}_"
                            f"{_safe_key(platform)}_{slot}"
                        ),
                        disabled=True,
                        use_container_width=True,
                    )
                    continue
                detail_payload = _render_influencer_entry(
                    layanan,
                    ranked.iloc[slot],
                    slot,
                    top_topics,
                    content_catalog,
                )
                if detail_payload is not None:
                    selected_detail = detail_payload

        if selected_detail is not None:
            _render_influencer_detail_inline(**selected_detail)


def _render_topic_summary(row: pd.Series) -> None:
    """Tampilkan ringkasan topik sebagai panel visual yang lebih informatif."""
    topic_key = str(row.get("key", ""))
    topic_name = str(row.get("topik", "Topik"))
    sentiment = str(row.get("sentimen_dominan", "neutral"))
    color = SENTIMENT_COLORS.get(sentiment, SENTIMENT_COLORS["neutral"])
    label = SENTIMENT_LABELS.get(sentiment, "Netral")
    percentage = max(0.0, min(100.0, float(row.get("persentase", 0.0))))
    jumlah = int(row.get("jumlah_komentar", 0))
    visual = _topic_visual_meta(topic_key)

    insight_text = {
        "gangguan_jaringan": "Fokuskan narasi pada transparansi gangguan, estimasi pemulihan, dan edukasi penyebab kendala jaringan.",
        "apresiasi_layanan": "Gunakan topik positif ini sebagai social proof untuk memperkuat kepercayaan dan citra layanan.",
        "perbandingan_provider": "Jawab perbandingan secara tenang dengan bukti kualitas, cakupan layanan, dan keunggulan dukungan pelanggan.",
        "harga_kualitas": "Hubungkan harga dengan manfaat yang konkret, paket yang relevan, serta perbaikan kualitas yang sedang berjalan.",
        "bantuan_admin": "Dorong percakapan menuju kanal bantuan yang aman, cepat, dan tidak mengekspos data pribadi pelanggan.",
        "bisnis_digitalisasi": "Tunjukkan manfaat konektivitas terhadap produktivitas, transaksi, efisiensi operasional, dan transformasi digital UMKM.",
        "kecepatan_stabil": "Perkuat bukti kestabilan koneksi melalui studi kasus, indikator manfaat, dan pengalaman operasional pelanggan.",
        "kuota_masa_aktif": "Sajikan informasi kuota dan masa aktif secara ringkas, akurat, serta mengarahkan pelanggan ke kanal pengecekan resmi.",
    }.get(topic_key, "Gunakan topik ini sebagai dasar pesan komunikasi yang spesifik dan mudah dipahami pelanggan.")

    st.markdown(
        f"""
        <div class="rec-topic-hero" style="--topic-color:{visual['color']};--topic-soft:{visual['soft']};--sentiment-color:{color};">
            <div class="rec-topic-hero-top">
                <div class="rec-topic-icon">{visual['icon']}</div>
                <div>
                    <div class="rec-topic-eyebrow">Ringkasan topik prioritas</div>
                    <h3>{escape(topic_name)}</h3>
                </div>
            </div>
            <div class="rec-topic-stat-grid">
                <div class="rec-topic-stat-card">
                    <div class="rec-topic-stat-top">
                        <span class="rec-topic-stat-icon">💬</span>
                        <span class="rec-topic-stat-label">Volume</span>
                    </div>
                    <span class="rec-topic-stat-value">{_format_number(jumlah)} <span class="rec-topic-stat-unit">komentar</span></span>
                    <span class="rec-topic-stat-note">Jumlah percakapan pada topik ini.</span>
                </div>
                <div class="rec-topic-stat-card">
                    <div class="rec-topic-stat-top">
                        <span class="rec-topic-stat-icon">📊</span>
                        <span class="rec-topic-stat-label">Porsi Data</span>
                    </div>
                    <span class="rec-topic-stat-value">{percentage:.1f}<span class="rec-topic-stat-unit">%</span></span>
                    <span class="rec-topic-stat-note">Dibandingkan total data terfilter.</span>
                </div>
                <div class="rec-topic-stat-card">
                    <div class="rec-topic-stat-top">
                        <span class="rec-topic-stat-icon">🧭</span>
                        <span class="rec-topic-stat-label">Sentimen</span>
                    </div>
                    <span class="rec-topic-sentiment-pill">{escape(label)}</span>
                    <span class="rec-topic-stat-note">Sentimen dominan pada percakapan.</span>
                </div>
            </div>
            <div class="rec-topic-progress-row">
                <div class="rec-topic-progress-info">
                    <span>Intensitas percakapan</span>
                    <span>{percentage:.1f}%</span>
                </div>
                <div class="rec-progress rec-topic-progress">
                    <span style="width:{percentage:.1f}%;"></span>
                </div>
            </div>
            <div class="rec-topic-insight">
                <span>Insight cepat</span>
                <p>{escape(insight_text)}</p>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def _render_indibiz_sentiment_content() -> None:
    """Tampilkan sembilan ide konten IndiBiz dalam tiga kelompok sentimen."""
    try:
        recommendations, meta = _build_indibiz_sentiment_recommendations()
        panels: list[str] = []
        for item in recommendations:
            keyword_html = "".join(
                f'<span class="rec-business-keyword">{escape(keyword)}</span>'
                for keyword in item.get("keywords", [])
            )
            ideas_html = "".join(
                dedent(
                    f"""
                    <article class="rec-business-idea">
                        <span class="rec-business-number">IDE {index:02d}</span>
                        <p>{escape(str(idea))}</p>
                    </article>
                    """
                ).strip()
                for index, idea in enumerate(item.get("ideas", []), start=1)
            )
            panels.append(
                dedent(
                    f"""
                    <section class="rec-business-panel" style="--sentiment-color:{item['color']};--sentiment-soft:{item['soft']};">
                        <div class="rec-business-head">
                            <div class="rec-business-head-left">
                                <div class="rec-business-icon">{escape(str(item['icon']))}</div>
                                <div>
                                    <span>Sentimen {escape(str(item['label']))}</span>
                                    <h3>Rekomendasi Konten Bisnis</h3>
                                </div>
                            </div>
                            <div class="rec-business-topic">
                                <span class="rec-business-topic-label">Topik dominan</span>
                                {escape(str(item['topik']))}
                            </div>
                        </div>
                        <div class="rec-business-ideas">{ideas_html}</div>
                        <div class="rec-business-keywords">{keyword_html}</div>
                    </section>
                    """
                ).strip()
            )
        st.markdown(
            '<div class="rec-business-stack">' + "".join(panels) + "</div>",
            unsafe_allow_html=True,
        )
        source_status = "Data aktual" if meta.get("is_real") else "Data fallback"
        st.caption(
            f"{source_status} · Sumber rekomendasi konten: {meta.get('source_name', 'Tidak tersedia')}"
        )
    except Exception as error:
        st.error(f"Rekomendasi konten bisnis IndiBiz tidak dapat ditampilkan: {error}")


def _strategy_content_examples(
    layanan: str,
    topic_name: str,
    strategy_key: str,
) -> dict[str, str]:
    """Bangun contoh konten yang mengikuti nama topik aktual."""
    service_hashtag = layanan.replace(" ", "")

    if strategy_key == "bisnis_digitalisasi":
        return {
            "instagram": (
                "Carousel studi kasus: bagaimana konektivitas IndiBiz membantu UMKM "
                "mengelola transaksi digital, sistem kasir, komunikasi pelanggan, dan kolaborasi tim."
            ),
            "tiktok": (
                "Video singkat satu hari operasional UMKM yang sudah terdigitalisasi, "
                "mulai dari menerima pesanan sampai memantau transaksi secara daring."
            ),
            "twitter": (
                "Thread praktis transformasi digital UMKM: petakan proses usaha, pilih alat digital, "
                "siapkan koneksi stabil, lalu ukur dampaknya terhadap produktivitas."
            ),
        }

    if strategy_key == "kecepatan_stabil":
        return {
            "instagram": (
                f"Tampilkan bukti manfaat koneksi {layanan} yang stabil melalui studi kasus, "
                "indikator kecepatan, jumlah perangkat, dan aktivitas utama pelanggan."
            ),
            "tiktok": (
                f"Uji tiga aktivitas harian bersama {layanan}: rapat video, transaksi digital, "
                "dan unggah berkas. Jelaskan kondisi pengujian secara transparan."
            ),
            "twitter": (
                f"Bagikan tips menjaga performa koneksi {layanan}, termasuk penempatan perangkat, "
                "pembagian bandwidth, dan kanal bantuan ketika kualitas menurun."
            ),
        }

    if strategy_key == "kuota_masa_aktif":
        return {
            "instagram": (
                f"Buat panduan visual untuk mengecek sisa kuota, masa aktif, dan detail paket {layanan} "
                "melalui aplikasi atau kanal resmi."
            ),
            "tiktok": (
                f"Tutorial singkat: cara cek kuota dan masa aktif {layanan}, membaca masa berlaku paket, "
                "serta memilih paket lanjutan sesuai kebutuhan."
            ),
            "twitter": (
                f"Butuh informasi kuota atau masa aktif {layanan}? Gunakan kanal pengecekan resmi. "
                "Hindari membagikan nomor lengkap dan data pribadi di ruang publik."
            ),
        }

    # Gunakan template lama untuk topik yang masih memiliki padanan semantik.
    examples = _content_examples(layanan, strategy_key)
    if examples:
        return examples

    return {
        "instagram": f"Buat carousel informatif mengenai {topic_name} pada layanan {layanan} dengan fakta, langkah praktis, dan kanal bantuan resmi.",
        "tiktok": f"Produksi video singkat tentang {topic_name} dengan contoh situasi nyata dan satu tindakan yang dapat dilakukan pelanggan.",
        "twitter": f"Susun thread ringkas mengenai {topic_name} pada {layanan}, lalu sertakan pembaruan dan jalur eskalasi yang jelas.",
    }


def _topic_ai_identity(layanan: str, topic_name: str) -> str:
    """Bangun identitas stabil untuk hasil Gemini pada satu layanan dan topik."""
    return f"{_safe_key(layanan)}::{_safe_key(topic_name)}"


def _build_topic_content_gemini_prompt(
    *,
    layanan: str,
    topic_name: str,
    sentiment: str,
    jumlah_komentar: int,
    kata_kunci: str,
    contoh_komentar: str,
    variation_index: int,
) -> str:
    """Susun prompt Gemini untuk tiga konsep konten siap salin per platform."""
    keywords = re.sub(r"\s+", " ", str(kata_kunci or "")).strip()
    example = _shorten_text(_clean_content_text(contoh_komentar), 320)
    return f"""
Anda adalah content strategist Telkom Group yang menyusun konten berdasarkan hasil analisis data.
Buat tiga naskah konten yang benar-benar berbeda gaya untuk topik berikut.

KONTEKS DATA:
- Layanan: {layanan}
- Topik: {topic_name}
- Sentimen dominan: {sentiment}
- Volume percakapan: {jumlah_komentar} komentar
- Kata kunci: {keywords or 'tidak tersedia'}
- Contoh komentar: {example or 'tidak tersedia'}
- Nomor variasi: {variation_index}

ATURAN:
1. Tulis dalam Bahasa Indonesia yang natural, ringkas, dan siap disalin.
2. Buat format yang benar-benar sesuai karakter Instagram, TikTok, dan Twitter/X.
3. Setiap variasi harus memakai hook, sudut cerita, dan CTA yang berbeda dari template umum.
4. Jangan mengarang data, angka kinerja, wilayah, waktu pemulihan, promo, atau klaim teknis yang tidak tersedia.
5. Jangan menyebut bahwa teks dibuat AI atau memakai nomor variasi.
6. Maksimal 80 kata per platform.
7. Keluarkan tepat tiga baris berikut tanpa Markdown, nomor, atau pembuka tambahan:

INSTAGRAM|||naskah Instagram
TIKTOK|||naskah TikTok
TWITTER|||naskah Twitter/X
""".strip()


def _parse_topic_content_gemini_response(
    raw_text: str,
    fallback_examples: dict[str, str],
) -> tuple[dict[str, str], bool]:
    """Parse tiga naskah platform dan gunakan fallback jika respons tidak lengkap."""
    try:
        parsed: dict[str, str] = {}
        key_map = {
            "INSTAGRAM": "instagram",
            "TIKTOK": "tiktok",
            "TWITTER": "twitter",
            "TWITTERX": "twitter",
        }
        for raw_line in str(raw_text or "").splitlines():
            line = raw_line.strip().replace("**", "").replace("```", "")
            if "|||" not in line:
                continue
            raw_key, raw_value = line.split("|||", 1)
            normalised_key = re.sub(r"[^A-Z]", "", raw_key.upper())
            platform = key_map.get(normalised_key)
            value = re.sub(r"\s+", " ", raw_value).strip(" -:|\t\r\n")
            if platform and value:
                parsed[platform] = value

        if not all(platform in parsed for platform in ("instagram", "tiktok", "twitter")):
            return dict(fallback_examples), False
        return parsed, True
    except Exception:
        return dict(fallback_examples), False


def _generate_topic_content_with_gemini(
    *,
    layanan: str,
    topic_name: str,
    sentiment: str,
    jumlah_komentar: int,
    kata_kunci: str,
    contoh_komentar: str,
    variation_index: int,
    fallback_examples: dict[str, str],
) -> tuple[dict[str, str], str]:
    """Hasilkan tiga konsep konten Gemini dengan cache 300 detik dan fallback lokal."""
    if bool(st.session_state.get("demo_mode", False)):
        return dict(fallback_examples), "Mode Demo · fallback lokal"
    try:
        prompt = _build_topic_content_gemini_prompt(
            layanan=layanan,
            topic_name=topic_name,
            sentiment=sentiment,
            jumlah_komentar=jumlah_komentar,
            kata_kunci=kata_kunci,
            contoh_komentar=contoh_komentar,
            variation_index=variation_index,
        )
        fallback_payload = (
            f"INSTAGRAM|||{fallback_examples['instagram']}\n"
            f"TIKTOK|||{fallback_examples['tiktok']}\n"
            f"TWITTER|||{fallback_examples['twitter']}"
        )
        model = init_gemini()
        raw_result = generate_recommendation(
            model,
            prompt,
            fallback_text=fallback_payload,
        )
        examples, valid_ai = _parse_topic_content_gemini_response(
            raw_result,
            fallback_examples,
        )
        source = "Gemini AI" if model is not None and valid_ai else "Fallback lokal"
        return examples, source
    except Exception:
        return dict(fallback_examples), "Fallback lokal"


def _get_topic_ai_payload(identity: str) -> dict[str, Any] | None:
    """Ambil hasil Gemini yang tersimpan pada session state."""
    values = st.session_state.get(TOPIC_AI_CONTENT_STATE_KEY, {})
    if not isinstance(values, dict):
        return None
    payload = values.get(identity)
    return payload if isinstance(payload, dict) else None


def _save_topic_ai_payload(identity: str, payload: dict[str, Any]) -> None:
    """Simpan hasil Gemini tanpa menghapus hasil topik lain."""
    values = st.session_state.get(TOPIC_AI_CONTENT_STATE_KEY, {})
    if not isinstance(values, dict):
        values = {}
    values = dict(values)
    values[identity] = payload
    st.session_state[TOPIC_AI_CONTENT_STATE_KEY] = values


def _next_topic_ai_variation(identity: str) -> int:
    """Naikkan nomor variasi agar prompt Gemini menghasilkan konsep baru."""
    values = st.session_state.get(TOPIC_AI_VARIATION_STATE_KEY, {})
    if not isinstance(values, dict):
        values = {}
    values = dict(values)
    next_value = int(values.get(identity, 0) or 0) + 1
    values[identity] = next_value
    st.session_state[TOPIC_AI_VARIATION_STATE_KEY] = values
    return next_value


def _queue_topic_ai_generation(
    identity: str,
    layanan: str,
    topic_name: str,
    sentiment: str,
    jumlah_komentar: int,
    kata_kunci: str,
    contoh_komentar: str,
    fallback_examples: dict[str, str],
) -> None:
    """Antrekan request Gemini sebelum halaman mulai dirender ulang."""
    try:
        variation_index = _next_topic_ai_variation(identity)
        st.session_state[TOPIC_AI_REQUEST_STATE_KEY] = {
            "identity": identity,
            "layanan": layanan,
            "topic_name": topic_name,
            "sentiment": sentiment,
            "jumlah_komentar": int(jumlah_komentar or 0),
            "kata_kunci": str(kata_kunci or ""),
            "contoh_komentar": str(contoh_komentar or ""),
            "variation_index": variation_index,
            "fallback_examples": dict(fallback_examples or {}),
        }
        st.session_state[RECOMMENDATION_ACTION_LOADING_KEY] = (
            f"Menyusun variasi konten {topic_name} dengan Gemini AI..."
        )
    except Exception:
        return None


def _process_queued_topic_ai_request() -> None:
    """Proses request Gemini di awal siklus render agar overlay tidak flicker."""
    request = st.session_state.pop(TOPIC_AI_REQUEST_STATE_KEY, None)
    if not isinstance(request, dict):
        return

    identity = str(request.get("identity", "")).strip()
    if not identity:
        return

    fallback_examples = request.get("fallback_examples", {})
    if not isinstance(fallback_examples, dict):
        fallback_examples = {}

    generated_examples, generated_source = _generate_topic_content_with_gemini(
        layanan=str(request.get("layanan", "")),
        topic_name=str(request.get("topic_name", "Topik")),
        sentiment=str(request.get("sentiment", "Netral")),
        jumlah_komentar=int(request.get("jumlah_komentar", 0) or 0),
        kata_kunci=str(request.get("kata_kunci", "") or ""),
        contoh_komentar=str(request.get("contoh_komentar", "") or ""),
        variation_index=int(request.get("variation_index", 1) or 1),
        fallback_examples=dict(fallback_examples),
    )
    _save_topic_ai_payload(
        identity,
        {
            "examples": generated_examples,
            "source": generated_source,
            "variation": int(request.get("variation_index", 1) or 1),
        },
    )
    log_activity(
        "GEMINI_CONTENT",
        "Rekomendasi",
        f"Menyusun variasi konten topik {request.get('topic_name', 'Topik')} untuk layanan {request.get('layanan', '-')}.",
        status="success" if generated_source == "Gemini AI" else "warning",
        service=str(request.get("layanan", "")),
        metadata={
            "topic": request.get("topic_name"),
            "sentiment": request.get("sentiment"),
            "variation": int(request.get("variation_index", 1) or 1),
            "source": generated_source,
        },
    )


def _render_topic_strategies(
    layanan: str,
    topic_summary: pd.DataFrame,
    score_matrix: pd.DataFrame,
) -> Any:
    """Tampilkan strategi topik dan kembalikan handle loading Gemini yang aktif."""
    if topic_summary is None or topic_summary.empty:
        st.info("Strategi topik belum tersedia untuk layanan ini.")
        return None

    topic_ai_loading_handle = None

    for topic_index, (_, row) in enumerate(topic_summary.iterrows(), start=1):
        topic_key = str(row.get("strategy_key", row.get("key", "default")))
        topic_name = str(row.get("topik", "Topik"))
        sentiment = SENTIMENT_LABELS.get(
            str(row.get("sentimen_dominan", "neutral")),
            "Netral",
        )
        visual = _topic_visual_meta(topic_key)
        title = (
            f"{visual['icon']} {topic_index:02d} · {topic_name} · "
            f"{_format_number(int(row.get('jumlah_komentar', 0)))} komentar · {sentiment}"
        )
        with st.expander(title, expanded=(topic_index == 1)):
            _render_topic_summary(row)

            fallback_examples = _strategy_content_examples(
                layanan,
                topic_name,
                topic_key,
            )
            ai_identity = _topic_ai_identity(layanan, topic_name)
            ai_payload = _get_topic_ai_payload(ai_identity)
            examples = (
                dict(ai_payload.get("examples", fallback_examples))
                if ai_payload
                else dict(fallback_examples)
            )
            source_label = str(
                ai_payload.get("source", "Template lokal")
                if ai_payload
                else "Template lokal"
            )
            variation_label = int(
                ai_payload.get("variation", 0) or 0
                if ai_payload
                else 0
            )

            st.markdown(
                f"""
                <div class="rec-copy-header" style="--topic-color:{visual['color']};--topic-soft:{visual['soft']};">
                    <div>
                        <span>Konten siap salin</span>
                        <strong>Konsep dapat dibuat ulang oleh Gemini agar tidak monoton</strong>
                    </div>
                    <em>{escape(source_label)}</em>
                </div>
                """,
                unsafe_allow_html=True,
            )

            action_info, action_button = st.columns([4.6, 1.5], gap="medium")
            with action_info:
                if source_label == "Gemini AI":
                    st.caption(
                        f"Gemini AI aktif · Variasi #{variation_label}. "
                        "Klik tombol di kanan untuk memperoleh sudut konten baru."
                    )
                elif source_label == "Fallback lokal":
                    st.caption(
                        "Gemini belum memberikan respons valid. Template lokal tetap ditampilkan agar halaman tidak berhenti."
                    )
                else:
                    st.caption(
                        "Template awal ditampilkan. Klik tombol di kanan untuk membuat konsep khusus berdasarkan data topik ini."
                    )
            with action_button:
                button_label = (
                    "↻ Variasi Baru"
                    if source_label == "Gemini AI"
                    else "✨ Buat dengan Gemini"
                )
                st.button(
                    button_label,
                    key=f"rec_topic_ai_generate_{_safe_key(ai_identity)}",
                    help="Gemini menyusun naskah baru untuk Instagram, TikTok, dan Twitter/X berdasarkan topik ini.",
                    use_container_width=True,
                    on_click=_queue_topic_ai_generation,
                    args=(
                        ai_identity,
                        layanan,
                        topic_name,
                        sentiment,
                        int(row.get("jumlah_komentar", 0) or 0),
                        str(row.get("kata_kunci", "") or ""),
                        str(row.get("contoh_komentar", "") or ""),
                        dict(fallback_examples),
                    ),
                )

            content_columns = st.columns(3, gap="medium")
            platform_sequence = ["instagram", "tiktok", "twitter"]
            for column, platform in zip(content_columns, platform_sequence):
                meta = PLATFORM_META[platform]
                with column:
                    st.markdown(
                        f"""
                        <div class="rec-platform-card-head" style="--platform-color:{meta['warna']};">
                            <div class="rec-platform-card-icon">{escape(meta['ikon'])}</div>
                            <div>
                                <span>Format konten</span>
                                <strong>{escape(meta['label'])}</strong>
                            </div>
                        </div>
                        """,
                        unsafe_allow_html=True,
                    )
                    st.code(_wrap_content_for_display(examples[platform]), language=None)

            score_topic_key = str(row.get("score_topic_key", topic_key))
            recommended = _top_influencers_for_topic(
                score_matrix,
                score_topic_key,
                limit=3,
            )
            if recommended:
                badges = "".join(
                    f"<span class='rec-influencer-pill rec-topic-pill' style='--topic-color:{visual['color']};--topic-soft:{visual['soft']};'>@{escape(name)}</span>"
                    for name in recommended
                )
            else:
                badges = (
                    f"<span class='rec-influencer-pill rec-topic-pill is-empty' "
                    f"style='--topic-color:{visual['color']};--topic-soft:{visual['soft']};'>"
                    "Influencer belum tervalidasi</span>"
                )
            st.markdown(
                f"""
                <div class="rec-topic-footer" style="--topic-color:{visual['color']};--topic-soft:{visual['soft']};">
                    <div class="rec-topic-footer-label">
                        <span>Influencer yang disarankan</span>
                        <small>Dipilih dari skor kesesuaian influencer × topik</small>
                    </div>
                    <div class="rec-badge-list">{badges}</div>
                </div>
                """,
                unsafe_allow_html=True,
            )

    return topic_ai_loading_handle


def _matrix_score_label(score: Any) -> str:
    """Terjemahkan skor matriks menjadi keterangan yang mudah dipahami."""
    try:
        value = int(float(score))
    except (TypeError, ValueError):
        value = 0
    if value >= 9:
        return "Kecocokan sangat kuat"
    if value >= 7:
        return "Kecocokan kuat"
    if value >= 5:
        return "Kecocokan cukup"
    return "Perlu pendampingan konten"


def _matrix_platform_options() -> dict[str, str]:
    """Siapkan pilihan platform untuk kontrol matriks."""
    return {
        str(meta["label"]): platform
        for platform, meta in PLATFORM_META.items()
        if platform in PLATFORM_ORDER
    }


def _render_matrix_intro(layanan: str) -> None:
    """Tampilkan pengantar kecil sebelum kontrol matriks."""
    st.markdown(
        f"""
        <div class="rec-matrix-intro">
            <div class="rec-matrix-intro-icon">⌁</div>
            <div>
                <span>Interactive compatibility explorer</span>
                <strong>Pilih fokus topik, filter platform, lalu lihat akun yang paling cocok.</strong>
                <p>
                    Matriks ini membantu membaca prioritas kolaborasi untuk {escape(layanan)}. 
                    Semakin tinggi skor, semakin cocok influencer digunakan untuk topik tersebut.
                </p>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def _render_influencer_empty_state(layanan: str, influencer_meta: dict[str, Any] | None = None) -> None:
    """Tampilkan empty state rapi ketika influencer belum tervalidasi."""
    source_name = str((influencer_meta or {}).get("source_name", "data influencer belum tersedia"))
    st.markdown(
        f"""
        <section class="rec-empty-state-panel" aria-label="Influencer belum tervalidasi">
            <div class="rec-empty-state-top">
                <div class="rec-empty-state-icon">🧩</div>
                <div>
                    <span class="rec-empty-state-kicker">Influencer belum siap</span>
                    <h3 class="rec-empty-state-title">Belum ada akun yang lolos validasi untuk {escape(layanan)}.</h3>
                </div>
            </div>
            <p class="rec-empty-state-desc">
                Halaman tidak lagi menampilkan akun dummy atau placeholder. Kandidat influencer hanya akan muncul
                jika username memiliki metrik jaringan/followers dan konten asli yang relevan pada dataset layanan ini.
            </p>
            <div class="rec-empty-state-grid">
                <div class="rec-empty-mini-card">
                    <span>Status data</span>
                    <p>Sumber saat ini: {escape(source_name)}.</p>
                </div>
                <div class="rec-empty-mini-card">
                    <span>Penyebab umum</span>
                    <p>Username pada data konten dan edge list belum cocok, atau konten influencer belum memuat topik layanan.</p>
                </div>
                <div class="rec-empty-mini-card">
                    <span>Aksi berikutnya</span>
                    <p>Lengkapi kolom username, platform, followers, content, source-target, lalu muat ulang halaman.</p>
                </div>
            </div>
        </section>
        """,
        unsafe_allow_html=True,
    )


def _render_matrix_unavailable_state(layanan: str) -> None:
    """Tampilkan empty state matriks tanpa membuat heatmap dummy bernilai 1."""
    st.markdown(
        f"""
        <section class="rec-empty-state-panel" aria-label="Matriks belum tersedia">
            <div class="rec-empty-state-top">
                <div class="rec-empty-state-icon">📉</div>
                <div>
                    <span class="rec-empty-state-kicker">Matriks ditahan</span>
                    <h3 class="rec-empty-state-title">Skor influencer × topik belum dapat dihitung untuk {escape(layanan)}.</h3>
                </div>
            </div>
            <p class="rec-empty-state-desc">
                Heatmap tidak ditampilkan karena belum ada influencer tervalidasi. Ini mencegah tampilan menyesatkan
                seperti baris “Data belum tersedia” dengan skor 1 pada semua topik.
            </p>
            <div class="rec-empty-state-grid">
                <div class="rec-empty-mini-card">
                    <span>Yang dibutuhkan</span>
                    <p>Minimal satu akun non-brand dengan platform, followers, metrik jaringan, dan konten relevan.</p>
                </div>
                <div class="rec-empty-mini-card">
                    <span>Filter aman</span>
                    <p>Kontrol filter akan aktif kembali otomatis setelah data influencer layanan ini tersedia.</p>
                </div>
                <div class="rec-empty-mini-card">
                    <span>Output</span>
                    <p>Setelah valid, halaman akan menampilkan top match, ranking, tabel skor, dan heatmap interaktif.</p>
                </div>
            </div>
        </section>
        """,
        unsafe_allow_html=True,
    )


def _filter_matrix_for_display(
    score_matrix: pd.DataFrame,
    topic_key: str,
    selected_platforms: list[str],
    min_score: int,
) -> pd.DataFrame:
    """Filter dan urutkan matriks berdasarkan kontrol pengguna."""
    try:
        if score_matrix.empty or topic_key not in score_matrix.columns:
            return pd.DataFrame()
        work = score_matrix.copy()
        if selected_platforms:
            work = work[work["platform"].isin(selected_platforms)].copy()
        work = work[pd.to_numeric(work[topic_key], errors="coerce").fillna(0) >= int(min_score)].copy()
        if work.empty:
            return work
        topic_keys = [str(item["key"]) for item in TOPIC_CONFIG]
        work["rata_rata_skor"] = work[topic_keys].mean(axis=1).round(1)
        work = work.sort_values(
            [topic_key, "rata_rata_skor", "username"],
            ascending=[False, False, True],
        )
        return work.reset_index(drop=True)
    except Exception:
        return pd.DataFrame()


def _render_matrix_summary_cards(
    filtered_matrix: pd.DataFrame,
    topic_key: str,
    min_score: int,
) -> None:
    """Tampilkan empat ringkasan kecil dari hasil filter matriks."""
    visual = _topic_visual_meta(topic_key)
    topic_label = str(TOPIC_BY_KEY.get(topic_key, {}).get("singkat", "Topik"))
    if filtered_matrix.empty:
        st.markdown(
            """
            <div class="rec-matrix-empty">
                Tidak ada influencer yang memenuhi filter saat ini. Turunkan skor minimum atau aktifkan platform lain.
            </div>
            """,
            unsafe_allow_html=True,
        )
        return

    top_row = filtered_matrix.iloc[0]
    top_username = _safe_username(top_row.get("username", "-"))
    top_platform = PLATFORM_META.get(str(top_row.get("platform", "twitter")), PLATFORM_META["twitter"])["label"]
    top_score = int(top_row.get(topic_key, 0))
    avg_score = float(pd.to_numeric(filtered_matrix[topic_key], errors="coerce").fillna(0).mean())
    strong_count = int((pd.to_numeric(filtered_matrix[topic_key], errors="coerce").fillna(0) >= 8).sum())
    platform_count = int(filtered_matrix["platform"].nunique()) if "platform" in filtered_matrix.columns else 0

    st.markdown(
        f"""
        <div class="rec-matrix-insight-grid" style="--matrix-color:{visual['color']};">
            <div class="rec-matrix-insight-card rec-card-topic">
                <div class="rec-matrix-card-top">
                    <div class="rec-matrix-card-icon">🎯</div>
                    <div class="rec-matrix-card-pulse"></div>
                </div>
                <span>Fokus topik</span>
                <strong>{escape(topic_label)}</strong>
                <small>Kolom utama untuk mengurutkan matriks rekomendasi.</small>
            </div>
            <div class="rec-matrix-insight-card rec-card-match">
                <div class="rec-matrix-card-top">
                    <div class="rec-matrix-card-icon">🏆</div>
                    <div class="rec-matrix-card-pulse"></div>
                </div>
                <span>Top match</span>
                <strong>@{escape(top_username)}</strong>
                <small>{escape(top_platform)} · skor {top_score}/10</small>
            </div>
            <div class="rec-matrix-insight-card rec-card-score">
                <div class="rec-matrix-card-top">
                    <div class="rec-matrix-card-icon">📊</div>
                    <div class="rec-matrix-card-pulse"></div>
                </div>
                <span>Rata-rata skor</span>
                <strong>{avg_score:.1f}/10</strong>
                <small>Setelah filter skor minimum {int(min_score)}.</small>
            </div>
            <div class="rec-matrix-insight-card rec-card-strong">
                <div class="rec-matrix-card-top">
                    <div class="rec-matrix-card-icon">⭐</div>
                    <div class="rec-matrix-card-pulse"></div>
                </div>
                <span>Kandidat kuat</span>
                <strong>{strong_count}</strong>
                <small>Dari {len(filtered_matrix)} akun pada {platform_count} platform.</small>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def _render_matrix_rank_cards(
    filtered_matrix: pd.DataFrame,
    topic_key: str,
) -> None:
    """Tampilkan tiga akun teratas agar insight matriks cepat terbaca."""
    if filtered_matrix.empty:
        return

    cards: list[str] = []
    for rank, (_, row) in enumerate(filtered_matrix.head(3).iterrows(), start=1):
        platform = str(row.get("platform", "twitter"))
        meta = PLATFORM_META.get(platform, PLATFORM_META["twitter"])
        username = _safe_username(row.get("username", "-"))
        score = int(row.get(topic_key, 0))
        platform_color = escape(str(meta["warna"]))
        platform_label = escape(str(meta["label"]))
        platform_icon = escape(str(meta.get("ikon", "★")))
        account_type_label = escape(_account_type_label(row.get("tipe_akun", "influencer")))
        safe_username = escape(username)

        cards.append(
            dedent(
                f"""
                <article class="rec-rank-card" style="--platform-color:{platform_color};">
                    <div class="rec-rank-glow"></div>
                    <div class="rec-rank-number">#{rank}</div>
                    <div class="rec-rank-main">
                        <span class="rec-rank-user">@{safe_username}</span>
                        <span class="rec-rank-platform">
                            <b>{platform_icon}</b>{platform_label} · {account_type_label}
                        </span>
                    </div>
                    <div class="rec-rank-score">{score}<em>/10</em></div>
                </article>
                """
            ).strip()
        )

    # Iframe ranking memiliki dokumen CSS sendiri sehingga tidak otomatis mewarisi
    # Light/Dark Theme dari halaman Streamlit. Warna Light Theme harus disuntikkan
    # secara eksplisit agar kartu ranking tidak selalu memakai surface gelap.
    dark_mode = bool(st.session_state.get("dark_mode", False))
    rank_theme_css = ""
    if not dark_mode:
        rank_theme_css = dedent(
            """
            :root { color-scheme: light; }

            .rec-rank-card {
                --rank-accent: #F6B73C;
                border-color: color-mix(in srgb, var(--platform-color, #1DA1F2) 38%, #D9E2EC);
                background:
                    radial-gradient(circle at 92% -12%, color-mix(in srgb, var(--platform-color, #1DA1F2) 18%, transparent), transparent 42%),
                    radial-gradient(circle at 5% 115%, color-mix(in srgb, var(--rank-accent, #F6B73C) 10%, transparent), transparent 38%),
                    linear-gradient(145deg, #FFFFFF 0%, color-mix(in srgb, var(--platform-color, #1DA1F2) 5%, #F8FAFC) 100%);
                box-shadow:
                    0 14px 30px rgba(15,23,42,.10),
                    0 0 24px color-mix(in srgb, var(--platform-color, #1DA1F2) 10%, transparent),
                    inset 0 1px 0 rgba(255,255,255,.96);
            }

            .rec-rank-card:nth-child(1) { --rank-accent: #F4B942; }
            .rec-rank-card:nth-child(2) { --rank-accent: #93A1B3; }
            .rec-rank-card:nth-child(3) { --rank-accent: #C98252; }

            .rec-rank-card:hover {
                border-color: color-mix(in srgb, var(--platform-color, #1DA1F2) 62%, #C9D4E0);
                box-shadow:
                    0 21px 40px rgba(15,23,42,.15),
                    0 0 34px color-mix(in srgb, var(--platform-color, #1DA1F2) 20%, transparent),
                    inset 0 1px 0 #FFFFFF;
                filter: saturate(1.08);
            }

            .rec-rank-card::before {
                background: linear-gradient(180deg, var(--platform-color, #1DA1F2), var(--rank-accent, #F4B942));
                box-shadow: 0 0 18px color-mix(in srgb, var(--platform-color, #1DA1F2) 24%, transparent);
            }

            .rec-rank-card::after {
                background: linear-gradient(105deg, transparent 36%, rgba(255,255,255,.78) 48%, transparent 60%);
                opacity: .42;
            }

            .rec-rank-glow {
                background: color-mix(in srgb, var(--platform-color, #1DA1F2) 13%, transparent);
                opacity: .72;
            }

            .rec-rank-number {
                color: #172033;
                background:
                    linear-gradient(145deg, color-mix(in srgb, var(--rank-accent, #F4B942) 18%, #FFFFFF), color-mix(in srgb, var(--platform-color, #1DA1F2) 10%, #FFFFFF));
                border-color: color-mix(in srgb, var(--rank-accent, #F4B942) 58%, #D6DEE8);
                box-shadow:
                    0 7px 18px color-mix(in srgb, var(--rank-accent, #F4B942) 18%, transparent),
                    inset 0 1px 0 #FFFFFF;
            }

            .rec-rank-user {
                color: #172033;
                text-shadow: none;
            }

            .rec-rank-platform {
                color: #334155;
                border-color: color-mix(in srgb, var(--platform-color, #1DA1F2) 40%, #D7E0EA);
                background: color-mix(in srgb, var(--platform-color, #1DA1F2) 10%, #FFFFFF);
                box-shadow: inset 0 1px 0 rgba(255,255,255,.94);
            }

            .rec-rank-platform b {
                color: #FFFFFF;
                background: color-mix(in srgb, var(--platform-color, #1DA1F2) 82%, #334155);
                box-shadow: 0 3px 10px color-mix(in srgb, var(--platform-color, #1DA1F2) 20%, transparent);
            }

            .rec-rank-score {
                color: color-mix(in srgb, var(--platform-color, #1DA1F2) 74%, #172033);
                text-shadow: 0 5px 18px color-mix(in srgb, var(--platform-color, #1DA1F2) 16%, transparent);
            }

            .rec-rank-score em {
                color: #6B778A;
            }
            """
        ).strip()

    # Memakai iframe HTML internal agar HTML kartu benar-benar dirender sebagai UI,
    # bukan terbaca sebagai teks/kode oleh Markdown Streamlit.
    rank_html = dedent(
        f"""
        <!DOCTYPE html>
        <html lang="id">
        <head>
            <meta charset="utf-8" />
            <style>
                :root {{ color-scheme: dark; }}
                * {{ box-sizing: border-box; }}
                html, body {{
                    margin: 0;
                    padding: 0;
                    width: 100%;
                    min-height: 100%;
                    overflow: hidden;
                    background: transparent;
                    font-family: 'Inter', 'Plus Jakarta Sans', 'Segoe UI', Arial, sans-serif;
                }}
                .rec-rank-grid {{
                    display: grid;
                    grid-template-columns: repeat(3, minmax(0, 1fr));
                    gap: 12px;
                    padding: 2px 0 10px;
                }}
                .rec-rank-card {{
                    position: relative;
                    display: grid;
                    grid-template-columns: 44px minmax(0, 1fr) 64px;
                    align-items: center;
                    gap: 12px;
                    min-height: 88px;
                    padding: 14px 15px;
                    overflow: hidden;
                    border: 1px solid color-mix(in srgb, var(--platform-color, #1DA1F2) 42%, rgba(255,255,255,.12));
                    border-radius: 18px;
                    background:
                        radial-gradient(circle at 92% -12%, color-mix(in srgb, var(--platform-color, #1DA1F2) 34%, transparent), transparent 42%),
                        linear-gradient(145deg, rgba(28,30,42,.96), rgba(12,12,16,.98));
                    box-shadow:
                        0 18px 38px rgba(0,0,0,.32),
                        0 0 28px color-mix(in srgb, var(--platform-color, #1DA1F2) 18%, transparent),
                        inset 0 1px 0 rgba(255,255,255,.09);
                    isolation: isolate;
                    transform: translateY(0) scale(1);
                    transform-origin: center;
                    transition:
                        transform .28s ease,
                        border-color .28s ease,
                        box-shadow .28s ease,
                        filter .28s ease;
                    animation: recRankEnter .72s cubic-bezier(.18,.85,.28,1.18) both;
                }}
                .rec-rank-card:nth-child(1) {{ animation-delay: .02s; }}
                .rec-rank-card:nth-child(2) {{ animation-delay: .14s; }}
                .rec-rank-card:nth-child(3) {{ animation-delay: .26s; }}
                .rec-rank-card:hover {{
                    transform: translateY(-5px) scale(1.018);
                    border-color: color-mix(in srgb, var(--platform-color, #1DA1F2) 62%, rgba(255,255,255,.20));
                    box-shadow:
                        0 24px 44px rgba(0,0,0,.42),
                        0 0 38px color-mix(in srgb, var(--platform-color, #1DA1F2) 30%, transparent),
                        inset 0 1px 0 rgba(255,255,255,.14);
                    filter: saturate(1.08);
                }}
                .rec-rank-card::before {{
                    content: "";
                    position: absolute;
                    inset: 0 auto 0 0;
                    width: 4px;
                    background: linear-gradient(180deg, var(--platform-color, #1DA1F2), rgba(255,255,255,.18));
                    opacity: .95;
                    animation: recRankLinePulse 2.8s ease-in-out infinite;
                }}
                .rec-rank-card::after {{
                    content: "";
                    position: absolute;
                    inset: -45% -35%;
                    background: linear-gradient(105deg, transparent 36%, rgba(255,255,255,.20) 48%, transparent 60%);
                    transform: translateX(-125%) rotate(8deg);
                    opacity: .55;
                    pointer-events: none;
                    animation: recRankShimmer 4.8s ease-in-out infinite;
                }}
                .rec-rank-card:nth-child(2)::after {{ animation-delay: .9s; }}
                .rec-rank-card:nth-child(3)::after {{ animation-delay: 1.8s; }}
                .rec-rank-glow {{
                    position: absolute;
                    right: -32px;
                    bottom: -42px;
                    width: 112px;
                    height: 112px;
                    border-radius: 999px;
                    background: color-mix(in srgb, var(--platform-color, #1DA1F2) 22%, transparent);
                    filter: blur(6px);
                    z-index: -1;
                    animation: recRankGlow 3.4s ease-in-out infinite alternate;
                }}
                .rec-rank-number {{
                    display: grid;
                    place-items: center;
                    width: 42px;
                    height: 42px;
                    border-radius: 14px;
                    color: #FFFFFF;
                    background:
                        linear-gradient(145deg, color-mix(in srgb, var(--platform-color, #1DA1F2) 44%, #111111), rgba(255,255,255,.045));
                    border: 1px solid color-mix(in srgb, var(--platform-color, #1DA1F2) 48%, rgba(255,255,255,.16));
                    box-shadow: 0 0 22px color-mix(in srgb, var(--platform-color, #1DA1F2) 26%, transparent);
                    font-size: 13px;
                    font-weight: 950;
                    letter-spacing: -.02em;
                    animation: recRankBadgePulse 2.6s ease-in-out infinite;
                }}
                .rec-rank-main {{ min-width: 0; }}
                .rec-rank-user {{
                    display: block;
                    max-width: 100%;
                    color: #FFFFFF;
                    font-size: 14px;
                    font-weight: 900;
                    line-height: 1.25;
                    overflow: hidden;
                    text-overflow: ellipsis;
                    white-space: nowrap;
                }}
                .rec-rank-platform {{
                    display: inline-flex;
                    align-items: center;
                    gap: 6px;
                    margin-top: 7px;
                    padding: 5px 8px;
                    border: 1px solid color-mix(in srgb, var(--platform-color, #1DA1F2) 38%, rgba(255,255,255,.12));
                    border-radius: 999px;
                    color: rgba(255,255,255,.82);
                    background: color-mix(in srgb, var(--platform-color, #1DA1F2) 13%, rgba(255,255,255,.04));
                    font-size: 0.75rem /* FIX: minimum 12px agar terbaca di tablet */;
                    font-weight: 850;
                    line-height: 1;
                }}
                .rec-rank-platform b {{
                    display: grid;
                    place-items: center;
                    width: 16px;
                    height: 16px;
                    border-radius: 999px;
                    color: #FFFFFF;
                    background: color-mix(in srgb, var(--platform-color, #1DA1F2) 38%, rgba(255,255,255,.08));
                    font-size: 0.75rem /* FIX: minimum 12px agar terbaca di tablet */;
                }}
                .rec-rank-score {{
                    justify-self: end;
                    color: #FFFFFF;
                    font-size: 25px;
                    font-weight: 950;
                    letter-spacing: -.055em;
                    text-shadow: 0 0 18px color-mix(in srgb, var(--platform-color, #1DA1F2) 24%, transparent);
                    animation: recRankScorePop .78s cubic-bezier(.18,.85,.28,1.18) both;
                }}
                .rec-rank-card:nth-child(1) .rec-rank-score {{ animation-delay: .16s; }}
                .rec-rank-card:nth-child(2) .rec-rank-score {{ animation-delay: .28s; }}
                .rec-rank-card:nth-child(3) .rec-rank-score {{ animation-delay: .40s; }}
                .rec-rank-score em {{
                    margin-left: 2px;
                    color: rgba(255,255,255,.58);
                    font-style: normal;
                    font-size: 0.75rem /* FIX: minimum 12px agar terbaca di tablet */;
                    font-weight: 800;
                    letter-spacing: 0;
                }}

                {rank_theme_css}

                @keyframes recRankEnter {{
                    0% {{
                        opacity: 0;
                        transform: translateY(18px) scale(.94);
                        filter: blur(8px) saturate(.8);
                    }}
                    65% {{
                        opacity: 1;
                        transform: translateY(-3px) scale(1.012);
                        filter: blur(0) saturate(1.08);
                    }}
                    100% {{
                        opacity: 1;
                        transform: translateY(0) scale(1);
                        filter: blur(0) saturate(1);
                    }}
                }}
                @keyframes recRankShimmer {{
                    0%, 55% {{ transform: translateX(-125%) rotate(8deg); opacity: 0; }}
                    66% {{ opacity: .58; }}
                    82%, 100% {{ transform: translateX(125%) rotate(8deg); opacity: 0; }}
                }}
                @keyframes recRankGlow {{
                    0% {{ transform: translate3d(0, 0, 0) scale(.92); opacity: .50; }}
                    100% {{ transform: translate3d(-12px, -10px, 0) scale(1.18); opacity: .95; }}
                }}
                @keyframes recRankLinePulse {{
                    0%, 100% {{ opacity: .72; box-shadow: 0 0 14px color-mix(in srgb, var(--platform-color, #1DA1F2) 22%, transparent); }}
                    50% {{ opacity: 1; box-shadow: 0 0 24px color-mix(in srgb, var(--platform-color, #1DA1F2) 42%, transparent); }}
                }}
                @keyframes recRankBadgePulse {{
                    0%, 100% {{ transform: scale(1); }}
                    50% {{ transform: scale(1.045); }}
                }}
                @keyframes recRankScorePop {{
                    0% {{ opacity: 0; transform: translateX(10px) scale(.82); }}
                    72% {{ opacity: 1; transform: translateX(0) scale(1.08); }}
                    100% {{ opacity: 1; transform: translateX(0) scale(1); }}
                }}
                @media (prefers-reduced-motion: reduce) {{
                    .rec-rank-card,
                    .rec-rank-card::before,
                    .rec-rank-card::after,
                    .rec-rank-glow,
                    .rec-rank-number,
                    .rec-rank-score {{
                        animation: none !important;
                        transition: none !important;
                    }}
                    .rec-rank-card:hover {{
                        transform: none !important;
                    }}
                }}

                @media (max-width: 620px) {{
                    .rec-rank-grid {{ grid-template-columns: 1fr; }}
                    .rec-rank-card {{ grid-template-columns: 44px minmax(0, 1fr) 60px; }}
                }}
            </style>
        </head>
        <body>
            <section class="rec-rank-grid">{''.join(cards)}</section>
        </body>
        </html>
        """
    ).strip()

    render_html_iframe(rank_html, height=112, scrolling=False)



def _matrix_table_filter_defaults(
    platform_options: list[str],
    sort_options: list[str],
    available_row_count: int,
) -> tuple[str, tuple[str, ...], str, bool, int]:
    """Kembalikan nilai awal filter tabel skor detail."""
    limit_max = min(50, max(int(available_row_count), 0))
    default_limit = min(15, limit_max) if limit_max > 0 else 0
    default_sort = str(sort_options[0]) if sort_options else "Rata-rata"
    return "", tuple(str(item) for item in platform_options), default_sort, True, default_limit


def _normalise_matrix_table_platforms(
    values: Any,
    platform_options: list[str],
) -> tuple[str, ...]:
    """Normalisasi pilihan platform sesuai urutan opsi yang tersedia."""
    try:
        selected = {str(item) for item in list(values or [])}
    except Exception:
        selected = set()
    return tuple(item for item in platform_options if item in selected)


def _normalise_matrix_table_limit(value: Any, available_row_count: int) -> int:
    """Normalisasi jumlah baris agar tetap valid untuk ukuran tabel aktif."""
    limit_max = min(50, max(int(available_row_count), 0))
    if limit_max <= 5:
        return limit_max
    try:
        numeric_value = int(value)
    except (TypeError, ValueError):
        numeric_value = min(15, limit_max)
    return max(5, min(limit_max, numeric_value))


def _ensure_matrix_table_filter_state(
    platform_options: list[str],
    sort_options: list[str],
    available_row_count: int,
) -> None:
    """Pastikan state draft dan aktif filter tabel selalu valid."""
    defaults = _matrix_table_filter_defaults(
        platform_options,
        sort_options,
        available_row_count,
    )
    default_keyword, default_platforms, default_sort, default_desc, default_limit = defaults

    widget_defaults: dict[str, Any] = {
        "rec_matrix_table_keyword": default_keyword,
        "rec_matrix_table_platforms": list(default_platforms),
        "rec_matrix_table_sort_by": default_sort,
        "rec_matrix_table_descending": default_desc,
        "rec_matrix_table_limit": default_limit,
    }
    for key, value in widget_defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value

    st.session_state["rec_matrix_table_keyword"] = str(
        st.session_state.get("rec_matrix_table_keyword", default_keyword)
    )
    st.session_state["rec_matrix_table_platforms"] = list(
        _normalise_matrix_table_platforms(
            st.session_state.get("rec_matrix_table_platforms", default_platforms),
            platform_options,
        )
    )
    current_sort = str(st.session_state.get("rec_matrix_table_sort_by", default_sort))
    st.session_state["rec_matrix_table_sort_by"] = (
        current_sort if current_sort in sort_options else default_sort
    )
    st.session_state["rec_matrix_table_descending"] = bool(
        st.session_state.get("rec_matrix_table_descending", default_desc)
    )
    st.session_state["rec_matrix_table_limit"] = _normalise_matrix_table_limit(
        st.session_state.get("rec_matrix_table_limit", default_limit),
        available_row_count,
    )

    applied_defaults: dict[str, Any] = {
        MATRIX_TABLE_FILTER_APPLIED_KEYS["keyword"]: default_keyword,
        MATRIX_TABLE_FILTER_APPLIED_KEYS["platforms"]: default_platforms,
        MATRIX_TABLE_FILTER_APPLIED_KEYS["sort_by"]: default_sort,
        MATRIX_TABLE_FILTER_APPLIED_KEYS["descending"]: default_desc,
        MATRIX_TABLE_FILTER_APPLIED_KEYS["row_limit"]: default_limit,
    }
    for key, value in applied_defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value

    st.session_state[MATRIX_TABLE_FILTER_APPLIED_KEYS["keyword"]] = str(
        st.session_state.get(MATRIX_TABLE_FILTER_APPLIED_KEYS["keyword"], default_keyword)
    )
    st.session_state[MATRIX_TABLE_FILTER_APPLIED_KEYS["platforms"]] = (
        _normalise_matrix_table_platforms(
            st.session_state.get(MATRIX_TABLE_FILTER_APPLIED_KEYS["platforms"], default_platforms),
            platform_options,
        )
    )
    applied_sort = str(
        st.session_state.get(MATRIX_TABLE_FILTER_APPLIED_KEYS["sort_by"], default_sort)
    )
    st.session_state[MATRIX_TABLE_FILTER_APPLIED_KEYS["sort_by"]] = (
        applied_sort if applied_sort in sort_options else default_sort
    )
    st.session_state[MATRIX_TABLE_FILTER_APPLIED_KEYS["descending"]] = bool(
        st.session_state.get(MATRIX_TABLE_FILTER_APPLIED_KEYS["descending"], default_desc)
    )
    st.session_state[MATRIX_TABLE_FILTER_APPLIED_KEYS["row_limit"]] = (
        _normalise_matrix_table_limit(
            st.session_state.get(MATRIX_TABLE_FILTER_APPLIED_KEYS["row_limit"], default_limit),
            available_row_count,
        )
    )


def _current_matrix_table_filter_values(
    platform_options: list[str],
    sort_options: list[str],
    available_row_count: int,
) -> tuple[str, tuple[str, ...], str, bool, int]:
    """Ambil snapshot filter tabel yang sedang dipilih pengguna."""
    defaults = _matrix_table_filter_defaults(
        platform_options,
        sort_options,
        available_row_count,
    )
    return (
        str(st.session_state.get("rec_matrix_table_keyword", defaults[0])).strip(),
        _normalise_matrix_table_platforms(
            st.session_state.get("rec_matrix_table_platforms", defaults[1]),
            platform_options,
        ),
        str(st.session_state.get("rec_matrix_table_sort_by", defaults[2])),
        bool(st.session_state.get("rec_matrix_table_descending", defaults[3])),
        _normalise_matrix_table_limit(
            st.session_state.get("rec_matrix_table_limit", defaults[4]),
            available_row_count,
        ),
    )


def _applied_matrix_table_filter_values(
    platform_options: list[str],
    sort_options: list[str],
    available_row_count: int,
) -> tuple[str, tuple[str, ...], str, bool, int]:
    """Ambil snapshot filter tabel yang terakhir diterapkan."""
    defaults = _matrix_table_filter_defaults(
        platform_options,
        sort_options,
        available_row_count,
    )
    return (
        str(
            st.session_state.get(
                MATRIX_TABLE_FILTER_APPLIED_KEYS["keyword"],
                defaults[0],
            )
        ).strip(),
        _normalise_matrix_table_platforms(
            st.session_state.get(
                MATRIX_TABLE_FILTER_APPLIED_KEYS["platforms"],
                defaults[1],
            ),
            platform_options,
        ),
        str(
            st.session_state.get(
                MATRIX_TABLE_FILTER_APPLIED_KEYS["sort_by"],
                defaults[2],
            )
        ),
        bool(
            st.session_state.get(
                MATRIX_TABLE_FILTER_APPLIED_KEYS["descending"],
                defaults[3],
            )
        ),
        _normalise_matrix_table_limit(
            st.session_state.get(
                MATRIX_TABLE_FILTER_APPLIED_KEYS["row_limit"],
                defaults[4],
            ),
            available_row_count,
        ),
    )


def _apply_matrix_table_filter_state(
    platform_options: list[str],
    sort_options: list[str],
    available_row_count: int,
) -> bool:
    """Terapkan filter tabel hanya jika nilai draft benar-benar berubah."""
    current_values = _current_matrix_table_filter_values(
        platform_options,
        sort_options,
        available_row_count,
    )
    if current_values == _applied_matrix_table_filter_values(
        platform_options,
        sort_options,
        available_row_count,
    ):
        return False

    keyword, platforms, sort_by, descending, row_limit = current_values
    st.session_state[MATRIX_TABLE_FILTER_APPLIED_KEYS["keyword"]] = keyword
    st.session_state[MATRIX_TABLE_FILTER_APPLIED_KEYS["platforms"]] = platforms
    st.session_state[MATRIX_TABLE_FILTER_APPLIED_KEYS["sort_by"]] = sort_by
    st.session_state[MATRIX_TABLE_FILTER_APPLIED_KEYS["descending"]] = descending
    st.session_state[MATRIX_TABLE_FILTER_APPLIED_KEYS["row_limit"]] = row_limit
    st.session_state[MATRIX_TABLE_FILTER_FEEDBACK_KEY] = "Filter tabel berhasil diterapkan."
    st.session_state[RECOMMENDATION_ACTION_LOADING_KEY] = (
        "Menerapkan filter tabel rekomendasi..."
    )
    return True


def _reset_matrix_table_filter_state(
    platform_options: list[str],
    sort_options: list[str],
    available_row_count: int,
) -> None:
    """Kembalikan filter tabel ke nilai awal dan tandai reset valid."""
    defaults = _matrix_table_filter_defaults(
        platform_options,
        sort_options,
        available_row_count,
    )
    current_values = _current_matrix_table_filter_values(
        platform_options,
        sort_options,
        available_row_count,
    )
    applied_values = _applied_matrix_table_filter_values(
        platform_options,
        sort_options,
        available_row_count,
    )
    if current_values == defaults and applied_values == defaults:
        return

    keyword, platforms, sort_by, descending, row_limit = defaults
    st.session_state["rec_matrix_table_keyword"] = keyword
    st.session_state["rec_matrix_table_platforms"] = list(platforms)
    st.session_state["rec_matrix_table_sort_by"] = sort_by
    st.session_state["rec_matrix_table_descending"] = descending
    st.session_state["rec_matrix_table_limit"] = row_limit

    st.session_state[MATRIX_TABLE_FILTER_APPLIED_KEYS["keyword"]] = keyword
    st.session_state[MATRIX_TABLE_FILTER_APPLIED_KEYS["platforms"]] = platforms
    st.session_state[MATRIX_TABLE_FILTER_APPLIED_KEYS["sort_by"]] = sort_by
    st.session_state[MATRIX_TABLE_FILTER_APPLIED_KEYS["descending"]] = descending
    st.session_state[MATRIX_TABLE_FILTER_APPLIED_KEYS["row_limit"]] = row_limit
    st.session_state[MATRIX_TABLE_FILTER_EVENT_KEY] = "reset"
    st.session_state[MATRIX_TABLE_FILTER_FEEDBACK_KEY] = "Filter tabel dikembalikan ke nilai awal."
    st.session_state[RECOMMENDATION_ACTION_LOADING_KEY] = (
        "Mengatur ulang filter tabel rekomendasi..."
    )


@_FRAGMENT_DECORATOR
def _render_matrix_table_filter_fragment(
    platform_options: list[str],
    sort_options: list[str],
    available_row_count: int,
) -> None:
    """Render filter tabel secara lokal sampai Apply atau Reset valid."""
    try:
        _ensure_matrix_table_filter_state(
            platform_options,
            sort_options,
            available_row_count,
        )
        current_values = _current_matrix_table_filter_values(
            platform_options,
            sort_options,
            available_row_count,
        )
        applied_values = _applied_matrix_table_filter_values(
            platform_options,
            sort_options,
            available_row_count,
        )
        filter_changed = current_values != applied_values

        # Marker membatasi CSS hanya pada dua tombol di filter tabel detail.
        # Apply tetap terlihat normal, tetapi tidak menerima pointer ketika
        # belum ada perubahan filter. Guard backend tetap ada di bawah.
        inert_rule = """
            div[data-testid="stColumn"]:has(.rec-matrix-table-apply-marker)
            div[data-testid="stButton"] > button[kind="primary"] {
                cursor: default !important;
                pointer-events: none !important;
            }
        """ if not filter_changed else ""
        st.markdown(
            f"""
            <style>
                .rec-matrix-table-reset-marker,
                .rec-matrix-table-apply-marker {{ display: none; }}
                div[data-testid="stMarkdownContainer"]:has(.rec-matrix-table-reset-marker),
                div[data-testid="stMarkdownContainer"]:has(.rec-matrix-table-apply-marker) {{
                    display: none !important;
                }}
                div[data-testid="stColumn"]:has(.rec-matrix-table-reset-marker)
                div[data-testid="stButton"] > button,
                div[data-testid="stColumn"]:has(.rec-matrix-table-apply-marker)
                div[data-testid="stButton"] > button {{
                    min-height: 3.45rem !important;
                }}
                div[data-testid="stColumn"]:has(.rec-matrix-table-reset-marker)
                div[data-testid="stButton"] > button p,
                div[data-testid="stColumn"]:has(.rec-matrix-table-apply-marker)
                div[data-testid="stButton"] > button p {{
                    white-space: nowrap !important;
                }}
                {inert_rule}
            </style>
            """,
            unsafe_allow_html=True,
        )

        filter_col, platform_col, sort_col, order_col, reset_col, apply_col = st.columns(
            [1.18, 1.03, .95, .72, .76, .95],
            gap="medium",
        )
        with filter_col:
            st.text_input(
                "Cari influencer",
                placeholder="Contoh: ferindra, detikcom",
                key="rec_matrix_table_keyword",
            )
        with platform_col:
            st.multiselect(
                "Filter platform",
                options=platform_options,
                key="rec_matrix_table_platforms",
            )
        with sort_col:
            st.selectbox(
                "Urutkan berdasarkan",
                options=sort_options,
                key="rec_matrix_table_sort_by",
            )
        with order_col:
            st.toggle(
                "Tertinggi dulu",
                key="rec_matrix_table_descending",
            )
        with reset_col:
            st.markdown(
                '<span class="rec-matrix-table-reset-marker"></span>',
                unsafe_allow_html=True,
            )
            st.markdown("<div style='height: 31px;'></div>", unsafe_allow_html=True)
            st.button(
                "Reset Filter",
                key="rec_matrix_table_reset_filter",
                use_container_width=True,
                on_click=_reset_matrix_table_filter_state,
                args=(platform_options, sort_options, available_row_count),
            )
        with apply_col:
            st.markdown(
                '<span class="rec-matrix-table-apply-marker"></span>',
                unsafe_allow_html=True,
            )
            st.markdown("<div style='height: 31px;'></div>", unsafe_allow_html=True)
            apply_clicked = st.button(
                "Terapkan Filter",
                key="rec_matrix_table_apply_filter",
                use_container_width=True,
                type="primary",
            )

        limit_max = min(50, max(int(available_row_count), 0))
        if available_row_count > 5:
            st.slider(
                "Jumlah baris yang ditampilkan",
                min_value=5,
                max_value=limit_max,
                step=1,
                key="rec_matrix_table_limit",
            )
        else:
            fixed_limit = max(available_row_count, 0)
            st.markdown(
                f"""
                <div class="rec-matrix-table-fixed-limit">
                    <span>Jumlah baris yang ditampilkan</span>
                    <strong>{fixed_limit}</strong>
                    <small>Semua kandidat tersedia langsung ditampilkan, jadi slider tidak diperlukan.</small>
                </div>
                """,
                unsafe_allow_html=True,
            )

        if st.session_state.pop(MATRIX_TABLE_FILTER_EVENT_KEY, "") == "reset":
            st.rerun(scope="app")

        if apply_clicked and filter_changed and _apply_matrix_table_filter_state(
            platform_options,
            sort_options,
            available_row_count,
        ):
            st.rerun(scope="app")
    except Exception as exc:
        st.error(f"Filter tabel skor detail gagal ditampilkan: {exc}")


def _render_matrix_table(filtered_matrix: pd.DataFrame) -> None:
    """Tampilkan tabel skor dengan pencarian, filter, sorting, dan detail akun."""
    if filtered_matrix.empty:
        return

    topic_keys = [str(item["key"]) for item in TOPIC_CONFIG]
    rename_map = {str(item["key"]): str(item["singkat"]) for item in TOPIC_CONFIG}
    topic_labels = [str(item["singkat"]) for item in TOPIC_CONFIG]

    table = filtered_matrix[["username", "platform", "tipe_akun", *topic_keys]].copy()
    table["tipe_akun"] = table["tipe_akun"].map(_account_type_label)
    table["platform"] = table["platform"].map(
        lambda item: PLATFORM_META.get(str(item), PLATFORM_META["twitter"])["label"]
    )
    table = table.rename(
        columns={
            "username": "Influencer",
            "platform": "Platform",
            "tipe_akun": "Tipe Akun",
            **rename_map,
        }
    )

    for column in topic_labels:
        table[column] = pd.to_numeric(table[column], errors="coerce").fillna(0).astype(int)
    table["Rata-rata"] = table[topic_labels].mean(axis=1).round(1)
    table = table[["Influencer", "Tipe Akun", "Platform", "Rata-rata", *topic_labels]]

    with st.expander("🔎 Lihat & eksplor tabel skor detail", expanded=False):
        st.markdown(
            """
            <div class="rec-matrix-table-hero">
                <span>🧭 Tabel interaktif</span>
                <strong>Bandingkan skor influencer berdasarkan topik rekomendasi.</strong>
                <p>
                    Gunakan pencarian, filter platform, sorting, dan pilihan akun untuk membaca skor
                    dengan lebih cepat tanpa mengubah data sumber.
                </p>
            </div>
            """,
            unsafe_allow_html=True,
        )

        platform_options = sorted(table["Platform"].dropna().unique().tolist())
        sort_options = [
            "Rata-rata", *topic_labels, "Influencer", "Tipe Akun", "Platform"
        ]
        # Jumlah baris tabel bisa kecil pada layanan tertentu (misalnya hanya 1-5 kandidat).
        # Streamlit tidak mengizinkan slider ketika min_value sama dengan max_value,
        # sehingga kontrol jumlah baris dibuat adaptif agar halaman tidak gagal tampil.
        available_row_count = int(len(table))

        _render_matrix_table_filter_fragment(
            platform_options,
            sort_options,
            available_row_count,
        )
        keyword, selected_platforms, sort_by, descending, row_limit = (
            _applied_matrix_table_filter_values(
                platform_options,
                sort_options,
                available_row_count,
            )
        )

        table_filter_feedback = str(
            st.session_state.pop(MATRIX_TABLE_FILTER_FEEDBACK_KEY, "")
        ).strip()
        if table_filter_feedback:
            st.toast(table_filter_feedback, icon="✅")

        st.markdown(
            """
            <div class="rec-matrix-table-apply-note">
                Filter, pencarian, sorting, dan jumlah baris akan diterapkan setelah tombol
                <b>Terapkan Filter</b> diklik.
            </div>
            """,
            unsafe_allow_html=True,
        )

        display_table = table.copy()
        if keyword.strip():
            display_table = display_table[
                display_table["Influencer"].astype(str).str.contains(keyword.strip(), case=False, na=False)
            ].copy()
        if selected_platforms:
            display_table = display_table[display_table["Platform"].isin(selected_platforms)].copy()
        else:
            display_table = display_table.iloc[0:0].copy()

        display_table = display_table.sort_values(sort_by, ascending=not descending).head(int(row_limit)).copy()

        total_rows = len(display_table)
        best_score = float(display_table["Rata-rata"].max()) if total_rows else 0.0
        best_account = str(display_table.iloc[0]["Influencer"]) if total_rows else "-"
        platform_count = int(display_table["Platform"].nunique()) if total_rows else 0
        st.markdown(
            f"""
            <div class="rec-matrix-table-statbar">
                <div class="rec-matrix-table-stat stat-rows">
                    <div class="rec-matrix-table-stat-topline">
                        <span>Baris tampil</span>
                        <div class="rec-matrix-table-stat-icon">📋</div>
                    </div>
                    <strong>{total_rows}</strong>
                    <small>hasil setelah filter</small>
                </div>
                <div class="rec-matrix-table-stat stat-platform">
                    <div class="rec-matrix-table-stat-topline">
                        <span>Platform aktif</span>
                        <div class="rec-matrix-table-stat-icon">🌐</div>
                    </div>
                    <strong>{platform_count}</strong>
                    <small>kanal media sosial</small>
                </div>
                <div class="rec-matrix-table-stat stat-score">
                    <div class="rec-matrix-table-stat-topline">
                        <span>Skor terbaik</span>
                        <div class="rec-matrix-table-stat-icon">⚡</div>
                    </div>
                    <strong>{best_score:.1f}/10</strong>
                    <small>nilai rekomendasi tertinggi</small>
                </div>
                <div class="rec-matrix-table-stat stat-top">
                    <div class="rec-matrix-table-stat-topline">
                        <span>Akun teratas</span>
                        <div class="rec-matrix-table-stat-icon">🏆</div>
                    </div>
                    <strong>@{escape(best_account)}</strong>
                    <small>ranking sesuai sorting</small>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        if display_table.empty:
            st.markdown(
                '<div class="rec-matrix-table-empty-state">Tidak ada baris yang cocok dengan filter tabel saat ini.</div>',
                unsafe_allow_html=True,
            )
            return

        # Warna tabel mengikuti tema aktif. Sebelumnya seluruh teks body dipaksa putih,
        # sehingga pada Light Theme teks hampir tidak terlihat di atas sel berwarna terang.
        dark_mode = bool(st.session_state.get("dark_mode", False))

        if dark_mode:
            body_text_color = "#F3F6FA"
            identity_text_color = "#FFFFFF"
            body_background = "rgba(255,255,255,.015)"
            identity_background = "rgba(255,255,255,.015)"
            cell_border_color = "rgba(255,255,255,.07)"
            header_background = "linear-gradient(135deg, #1D2230, #151821)"
            header_text_color = "#DDE6F3"
            header_border_color = "rgba(29,161,242,.22)"
            high_score_color = "#FFFFFF"
            mid_score_color = "#FFFFFF"
            low_score_color = "#FFFFFF"
        else:
            body_text_color = "#344054"
            identity_text_color = "#172033"
            body_background = "#FFFFFF"
            identity_background = "rgba(29,161,242,.035)"
            cell_border_color = "#E1E7EE"
            header_background = "linear-gradient(135deg, #F8FAFC, #EEF3F8)"
            header_text_color = "#344054"
            header_border_color = "#D8E2EC"
            high_score_color = "#176B4D"
            mid_score_color = "#8A5A00"
            low_score_color = "#A3322E"

        def _score_style(value: Any) -> str:
            try:
                score = float(value)
            except (TypeError, ValueError):
                return ""
            if score >= 9:
                return (
                    "background: linear-gradient(90deg, rgba(53,217,139,.24), rgba(53,217,139,.06)); "
                    f"color: {high_score_color}; font-weight: 900; border-left: 3px solid #35D98B;"
                )
            if score >= 7:
                return (
                    "background: linear-gradient(90deg, rgba(255,152,0,.22), rgba(255,152,0,.05)); "
                    f"color: {mid_score_color}; font-weight: 850; border-left: 3px solid #FF9800;"
                )
            return (
                "background: linear-gradient(90deg, rgba(229,57,53,.20), rgba(229,57,53,.05)); "
                f"color: {low_score_color}; font-weight: 800; border-left: 3px solid #E53935;"
            )

        styled_table = (
            display_table.style
            .format({"Rata-rata": "{:.1f}"})
            .set_properties(
                **{
                    "color": body_text_color,
                    "background-color": body_background,
                    "font-size": "13px",
                }
            )
            .set_properties(
                subset=["Influencer", "Platform"],
                **{
                    "color": identity_text_color,
                    "font-weight": "850",
                    "background-color": identity_background,
                },
            )
            .map(_score_style, subset=["Rata-rata", *topic_labels])
            .set_table_styles(
                [
                    {
                        "selector": "th",
                        "props": [
                            ("background", header_background),
                            ("color", header_text_color),
                            ("font-weight", "900"),
                            ("border-color", header_border_color),
                        ],
                    },
                    {
                        "selector": "td",
                        "props": [
                            ("border-color", cell_border_color),
                            ("font-size", "13px"),
                        ],
                    },
                ]
            )
        )

        st.dataframe(
            styled_table,
            use_container_width=True,
            hide_index=True,
            height=min(520, 118 + 38 * max(4, len(display_table))),
        )

        csv_data = display_table.to_csv(index=False).encode("utf-8-sig")
        st.download_button(
            "⬇️ Unduh tabel yang sedang tampil",
            data=csv_data,
            file_name="tabel_skor_rekomendasi_terfilter.csv",
            mime="text/csv",
            use_container_width=True,
            key="rec_matrix_table_download",
            on_click="ignore",
        )

        selected_account = st.selectbox(
            "Pilih akun untuk melihat detail skor",
            options=display_table["Influencer"].astype(str).tolist(),
            index=0,
            key="rec_matrix_table_selected_account",
            on_change=_show_matrix_account_detail_loading,
        )
        selected_row = display_table[display_table["Influencer"].astype(str).eq(str(selected_account))].iloc[0]

        score_pills: list[str] = []
        for label in ["Rata-rata", *topic_labels]:
            score_value = float(selected_row[label])
            if score_value >= 9:
                css_class = "is-high"
            elif score_value >= 7:
                css_class = "is-mid"
            else:
                css_class = "is-low"
            score_pills.append(
                f'<span class="rec-matrix-table-score-pill {css_class}">{escape(label)} <b>{score_value:g}/10</b></span>'
            )

        st.markdown(
            f"""
            <div class="rec-matrix-table-detail">
                <div class="rec-matrix-table-detail-title">
                    <strong>@{escape(str(selected_row['Influencer']))}</strong>
                    <span>
                        {escape(str(selected_row['Platform']))} ·
                        {escape(str(selected_row['Tipe Akun']))}
                    </span>
                </div>
                <div class="rec-matrix-table-score-pills">{''.join(score_pills)}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )


def _build_heatmap_figure(
    score_matrix: pd.DataFrame,
    focus_topic_key: str | None = None,
) -> Any:
    """Bangun heatmap kesesuaian influencer × topik dengan Plotly."""
    # Plotly baru dimuat saat section matriks benar-benar dibangun.
    import plotly.graph_objects as go

    topic_keys = [str(item["key"]) for item in TOPIC_CONFIG]
    topic_labels = [str(item["singkat"]) for item in TOPIC_CONFIG]
    focus_label = str(
        TOPIC_BY_KEY.get(str(focus_topic_key), {}).get("singkat", "Semua Topik")
    )

    if score_matrix.empty:
        z_values = [[1 for _ in topic_keys]]
        usernames = ["Data belum tersedia"]
        customdata = [[['-', 'Data tidak tersedia', 'Data belum tersedia'] for _ in topic_keys]]
    else:
        z_values = score_matrix[topic_keys].astype(int).values.tolist()
        usernames = []
        customdata = []
        for _, row in score_matrix.iterrows():
            username = _safe_username(row.get("username", "-"))
            platform = str(row.get("platform", "twitter"))
            meta = PLATFORM_META.get(platform, PLATFORM_META["twitter"])
            usernames.append(f"{meta['ikon']} @{username}")
            custom_row = []
            for topic_key in topic_keys:
                score = int(row.get(topic_key, 0))
                custom_row.append([meta["label"], _matrix_score_label(score), f"@{username}"])
            customdata.append(custom_row)

    figure = go.Figure(
        data=go.Heatmap(
            z=z_values,
            x=topic_labels,
            y=usernames,
            customdata=customdata,
            zmin=1,
            zmax=10,
            colorscale=[
                [0.00, "#151515"],
                [0.25, "#2B1A1A"],
                [0.50, "#6F2424"],
                [0.78, "#C73030"],
                [1.00, "#FF5252"],
            ],
            text=z_values,
            texttemplate="%{text}",
            textfont={"color": "#FFFFFF", "size": 12, "family": "Inter, sans-serif"},
            hovertemplate=(
                "<b>%{customdata[2]}</b><br>"
                "Platform: %{customdata[0]}<br>"
                "Topik: %{x}<br>"
                "Skor kesesuaian: <b>%{z}/10</b><br>"
                "%{customdata[1]}<extra></extra>"
            ),
            colorbar={
                "title": {"text": "Skor", "font": {"color": "#FFFFFF", "size": 12}},
                "tickfont": {"color": "#AAAAAA"},
                "thickness": 10,
                "len": 0.70,
                "outlinecolor": "#444444",
            },
            xgap=3,
            ygap=3,
        )
    )
    figure.update_layout(
        title={
            "text": f"Matriks Kesesuaian Influencer × Topik · Fokus: {focus_label}",
            "x": 0.0,
            "xanchor": "left",
            "font": {"family": "Inter, sans-serif", "size": 20, "color": "#FFFFFF"},
        },
        height=max(455, 120 + (len(usernames) * 48)),
        margin={"l": 150, "r": 32, "t": 72, "b": 98},
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font={"family": "Inter, sans-serif", "color": "#FFFFFF"},
        xaxis={
            "title": {"text": "Topik Strategis", "font": {"color": "#AAAAAA"}},
            "tickfont": {"color": "#FFFFFF", "size": 11},
            "tickangle": -18,
            "side": "bottom",
            "showgrid": False,
            "zeroline": False,
        },
        yaxis={
            "title": {"text": "Influencer", "font": {"color": "#AAAAAA"}},
            "tickfont": {"color": "#FFFFFF", "size": 11},
            "autorange": "reversed",
            "showgrid": False,
            "zeroline": False,
        },
        hoverlabel={
            "bgcolor": "#111111",
            "bordercolor": "#E53935",
            "font": {"color": "#FFFFFF", "family": "Inter, sans-serif"},
        },
    )
    return figure


def _matrix_filter_state_keys(layanan: str) -> dict[str, str]:
    """Bangun key session filter matriks yang terpisah untuk setiap layanan."""
    service_key = _safe_key(layanan)
    return {
        "topic_widget": f"rec_matrix_topic_{service_key}",
        "platform_widget": f"rec_matrix_platform_{service_key}",
        "score_widget": f"rec_matrix_min_score_{service_key}",
        "topic_applied": f"_rec_matrix_applied_topic_{service_key}",
        "platform_applied": f"_rec_matrix_applied_platform_{service_key}",
        "score_applied": f"_rec_matrix_applied_min_score_{service_key}",
        "event": f"{MATRIX_FILTER_EVENT_PREFIX}{service_key}",
        "feedback": f"{MATRIX_FILTER_FEEDBACK_PREFIX}{service_key}",
    }


def _matrix_filter_defaults(
    topic_labels: list[str],
    platform_labels: list[str],
) -> tuple[str, tuple[str, ...], int]:
    """Kembalikan nilai awal filter matriks sesuai opsi yang tersedia."""
    default_topic = str(topic_labels[0]) if topic_labels else ""
    return (
        default_topic,
        tuple(str(label) for label in platform_labels),
        MATRIX_FILTER_DEFAULT_MIN_SCORE,
    )


def _normalise_matrix_platform_labels(
    values: Any,
    platform_labels: list[str],
) -> tuple[str, ...]:
    """Normalisasi pilihan platform dan pertahankan urutan opsi antarmuka."""
    try:
        selected = {str(value) for value in list(values or [])}
    except Exception:
        selected = set()
    return tuple(label for label in platform_labels if label in selected)


def _ensure_matrix_filter_state(
    layanan: str,
    topic_labels: list[str],
    platform_labels: list[str],
) -> None:
    """Pastikan state draft dan state aktif matriks selalu valid."""
    keys = _matrix_filter_state_keys(layanan)
    default_topic, default_platforms, default_score = _matrix_filter_defaults(
        topic_labels,
        platform_labels,
    )

    current_topic = str(st.session_state.get(keys["topic_widget"], default_topic))
    if current_topic not in topic_labels:
        st.session_state[keys["topic_widget"]] = default_topic

    current_platforms = _normalise_matrix_platform_labels(
        st.session_state.get(keys["platform_widget"], list(default_platforms)),
        platform_labels,
    )
    st.session_state[keys["platform_widget"]] = list(current_platforms)

    try:
        current_score = int(st.session_state.get(keys["score_widget"], default_score))
    except (TypeError, ValueError):
        current_score = default_score
    st.session_state[keys["score_widget"]] = min(10, max(1, current_score))

    applied_topic = str(st.session_state.get(keys["topic_applied"], default_topic))
    if applied_topic not in topic_labels:
        applied_topic = default_topic
    st.session_state[keys["topic_applied"]] = applied_topic

    applied_platforms = _normalise_matrix_platform_labels(
        st.session_state.get(keys["platform_applied"], list(default_platforms)),
        platform_labels,
    )
    st.session_state[keys["platform_applied"]] = list(applied_platforms)

    try:
        applied_score = int(st.session_state.get(keys["score_applied"], default_score))
    except (TypeError, ValueError):
        applied_score = default_score
    st.session_state[keys["score_applied"]] = min(10, max(1, applied_score))


def _current_matrix_filter_values(
    layanan: str,
    topic_labels: list[str],
    platform_labels: list[str],
) -> tuple[str, tuple[str, ...], int]:
    """Ambil nilai filter yang sedang dipilih pengguna."""
    keys = _matrix_filter_state_keys(layanan)
    default_topic, default_platforms, default_score = _matrix_filter_defaults(
        topic_labels,
        platform_labels,
    )
    topic = str(st.session_state.get(keys["topic_widget"], default_topic))
    platforms = _normalise_matrix_platform_labels(
        st.session_state.get(keys["platform_widget"], list(default_platforms)),
        platform_labels,
    )
    # Multiselect kosong berarti semua platform sesuai teks bantuan UI.
    if not platforms:
        platforms = default_platforms
    try:
        score = int(st.session_state.get(keys["score_widget"], default_score))
    except (TypeError, ValueError):
        score = default_score
    return topic, platforms, min(10, max(1, score))


def _applied_matrix_filter_values(
    layanan: str,
    topic_labels: list[str],
    platform_labels: list[str],
) -> tuple[str, tuple[str, ...], int]:
    """Ambil snapshot filter matriks yang terakhir diterapkan."""
    keys = _matrix_filter_state_keys(layanan)
    default_topic, default_platforms, default_score = _matrix_filter_defaults(
        topic_labels,
        platform_labels,
    )
    topic = str(st.session_state.get(keys["topic_applied"], default_topic))
    platforms = _normalise_matrix_platform_labels(
        st.session_state.get(keys["platform_applied"], list(default_platforms)),
        platform_labels,
    )
    # Snapshot kosong juga diperlakukan sebagai semua platform agar tidak
    # tercatat sebagai filter aktif semu.
    if not platforms:
        platforms = default_platforms
    try:
        score = int(st.session_state.get(keys["score_applied"], default_score))
    except (TypeError, ValueError):
        score = default_score
    return topic, platforms, min(10, max(1, score))


def _apply_matrix_filter_state(
    layanan: str,
    topic_labels: list[str],
    platform_labels: list[str],
) -> None:
    """Terapkan draft hanya jika berbeda dari filter matriks yang aktif."""
    try:
        current_values = _current_matrix_filter_values(
            layanan,
            topic_labels,
            platform_labels,
        )
        applied_values = _applied_matrix_filter_values(
            layanan,
            topic_labels,
            platform_labels,
        )
        if current_values == applied_values:
            return

        keys = _matrix_filter_state_keys(layanan)
        topic, platforms, score = current_values
        st.session_state[keys["topic_applied"]] = topic
        st.session_state[keys["platform_applied"]] = list(platforms)
        st.session_state[keys["score_applied"]] = score
        st.session_state[keys["feedback"]] = "apply"
        st.session_state[keys["event"]] = True
        _show_matrix_filter_loading(layanan)
    except Exception as exc:
        st.error(f"Filter matriks belum dapat diterapkan. Detail: {exc}")


def _reset_matrix_filter_state(
    layanan: str,
    topic_labels: list[str],
    platform_labels: list[str],
) -> None:
    """Reset filter matriks ke nilai awal dan langsung gunakan hasil default."""
    try:
        defaults = _matrix_filter_defaults(topic_labels, platform_labels)
        current_values = _current_matrix_filter_values(
            layanan,
            topic_labels,
            platform_labels,
        )
        applied_values = _applied_matrix_filter_values(
            layanan,
            topic_labels,
            platform_labels,
        )
        if current_values == defaults and applied_values == defaults:
            return

        keys = _matrix_filter_state_keys(layanan)
        topic, platforms, score = defaults
        st.session_state[keys["topic_widget"]] = topic
        st.session_state[keys["platform_widget"]] = list(platforms)
        st.session_state[keys["score_widget"]] = score
        st.session_state[keys["topic_applied"]] = topic
        st.session_state[keys["platform_applied"]] = list(platforms)
        st.session_state[keys["score_applied"]] = score
        st.session_state[keys["feedback"]] = "reset"
        st.session_state[keys["event"]] = True
    except Exception as exc:
        st.error(f"Filter matriks belum dapat direset. Detail: {exc}")


def _render_matrix_filter_interaction_guard(layanan: str) -> None:
    """Jaga tombol Apply/Reset tetap inert saat filter matriks belum aktif.

    Kontrol utama berada di dalam ``st.form`` sehingga perubahan selectbox,
    multiselect, dan slider hanya tersimpan di browser sampai salah satu tombol
    form ditekan. Guard ini bekerja di sisi browser untuk mempertahankan tampilan
    tombol normal (bukan disabled) sambil memblokir pointer/keyboard ketika semua
    filter masih pada nilai awal dan belum ada filter aktif yang diterapkan.
    """
    try:
        service_key = _safe_key(layanan)
        render_html_iframe(
            fr"""
            <script>
            (() => {{
                const parentWindow = window.parent;
                const doc = parentWindow.document;
                const cleanupKey = "__recMatrixMainFilterGuard_{service_key}";

                if (typeof parentWindow[cleanupKey] === "function") {{
                    parentWindow[cleanupKey]();
                }}

                const rapikan = (nilai) => String(nilai || "")
                    .replace(/\s+/g, " " )
                    .trim();

                const marker = () => doc.querySelector(
                    '.rec-matrix-main-form-marker[data-service="{service_key}"]'
                );

                const cariKontrol = (form, namaLabel, testId) => {{
                    if (!form) return null;
                    const label = Array.from(form.querySelectorAll("label"))
                        .find((item) => rapikan(item.textContent).toLowerCase() === namaLabel.toLowerCase());
                    if (!label) return null;
                    return label.closest(`[data-testid="${{testId}}"]`);
                }};

                const nilaiSelect = (kontrol) => {{
                    if (!kontrol) return "";
                    const bidang = kontrol.querySelector('[data-baseweb="select"]');
                    const input = kontrol.querySelector("input");
                    return rapikan(bidang?.innerText || bidang?.textContent || input?.value || "");
                }};

                const nilaiSlider = (kontrol) => {{
                    if (!kontrol) return NaN;
                    const slider = kontrol.querySelector('[role="slider"]');
                    const raw = slider?.getAttribute("aria-valuenow") ||
                        slider?.getAttribute("aria-valuetext") ||
                        slider?.textContent || "";
                    const found = String(raw).match(/-?\d+(?:[.,]\d+)?/);
                    return found ? Number(found[0].replace(",", ".")) : NaN;
                }};

                const ubahStatusTombol = (tombol, dibuatInert) => {{
                    if (!tombol) return;
                    tombol.dataset.recMatrixFilterInert = dibuatInert ? "true" : "false";
                    tombol.classList.toggle("rec-matrix-btn-inert", dibuatInert);
                    tombol.style.pointerEvents = dibuatInert ? "none" : "";
                    tombol.style.cursor = dibuatInert ? "default" : "";
                    tombol.tabIndex = dibuatInert ? -1 : 0;
                }};

                const sinkronkan = () => {{
                    const penanda = marker();
                    const form = penanda?.closest('[data-testid="stForm"]') || penanda?.closest("form");
                    if (!penanda || !form) return;

                    form.classList.add("rec-matrix-filter-form");

                    const tombol = Array.from(form.querySelectorAll("button"));
                    const tombolTerapkan = tombol.find((item) => rapikan(item.innerText) === "Terapkan Filter");
                    const tombolReset = tombol.find((item) => rapikan(item.innerText) === "Reset Filter");
                    if (!tombolTerapkan || !tombolReset) return;

                    tombolTerapkan.classList.add("rec-matrix-filter-btn", "rec-matrix-btn-apply");
                    tombolReset.classList.add("rec-matrix-filter-btn", "rec-matrix-btn-reset");

                    const defaultTopic = rapikan(penanda.dataset.defaultTopic);
                    const defaultPlatforms = rapikan(penanda.dataset.defaultPlatforms)
                        .split("|")
                        .map(rapikan)
                        .filter(Boolean);
                    const defaultScore = Number(penanda.dataset.defaultScore || "1");
                    const appliedActive = penanda.dataset.appliedActive === "true";

                    const topicControl = cariKontrol(form, "Fokus topik", "stSelectbox");
                    const platformControl = cariKontrol(form, "Filter platform", "stMultiSelect");
                    const scoreControl = cariKontrol(form, "Skor minimum", "stSlider");

                    const topicValue = nilaiSelect(topicControl);
                    const platformText = nilaiSelect(platformControl);
                    const scoreValue = nilaiSlider(scoreControl);

                    const topicAktif = topicValue !== defaultTopic;
                    const jumlahPlatformDefaultTerpilih = defaultPlatforms
                        .filter((label) => platformText.includes(label)).length;
                    const seluruhPlatformAwal = defaultPlatforms.length > 0 && (
                        jumlahPlatformDefaultTerpilih === defaultPlatforms.length ||
                        jumlahPlatformDefaultTerpilih === 0
                    );
                    const platformAktif = !seluruhPlatformAwal;
                    const scoreAktif = Number.isFinite(scoreValue) && scoreValue !== defaultScore;
                    const filterAktif = appliedActive || topicAktif || platformAktif || scoreAktif;

                    ubahStatusTombol(tombolTerapkan, !filterAktif);
                    ubahStatusTombol(tombolReset, !filterAktif);
                }};

                let timer = null;
                const jadwalkan = () => {{
                    window.clearTimeout(timer);
                    timer = window.setTimeout(sinkronkan, 30);
                }};

                const observer = new MutationObserver(jadwalkan);
                observer.observe(doc.body, {{
                    subtree: true,
                    childList: true,
                    characterData: true,
                    attributes: true,
                    attributeFilter: ["value", "aria-valuenow", "aria-valuetext"]
                }});

                doc.addEventListener("input", jadwalkan, true);
                doc.addEventListener("change", jadwalkan, true);
                doc.addEventListener("click", jadwalkan, true);

                parentWindow[cleanupKey] = () => {{
                    observer.disconnect();
                    doc.removeEventListener("input", jadwalkan, true);
                    doc.removeEventListener("change", jadwalkan, true);
                    doc.removeEventListener("click", jadwalkan, true);
                    window.clearTimeout(timer);
                }};

                sinkronkan();
                window.setTimeout(sinkronkan, 200);
            }})();
            </script>
            """,
            height=0,
        )
    except Exception:
        # Guard hanya peningkatan UX. Backend callback tetap memvalidasi state.
        return None


@_FRAGMENT_DECORATOR
def _render_matrix_filter_fragment(
    layanan: str,
    topic_labels: list[str],
    platform_labels: list[str],
) -> None:
    """Render filter matriks secara manual tanpa rerun saat kontrol baru diubah."""
    try:
        _ensure_matrix_filter_state(layanan, topic_labels, platform_labels)
        keys = _matrix_filter_state_keys(layanan)
        defaults = _matrix_filter_defaults(topic_labels, platform_labels)
        applied_values = _applied_matrix_filter_values(
            layanan,
            topic_labels,
            platform_labels,
        )
        applied_filter_active = applied_values != defaults
        default_topic, default_platforms, default_score = defaults
        default_platform_text = "|".join(default_platforms)
        service_key = _safe_key(layanan)

        # Form menahan seluruh perubahan widget di sisi browser. Memilih topik,
        # platform, atau skor tidak lagi mererun fragment/halaman. Nilai baru
        # baru dikirim ke Python ketika Apply atau Reset benar-benar ditekan.
        with st.form(
            key=f"rec_matrix_filter_form_{service_key}",
            clear_on_submit=False,
        ):
            st.markdown(
                (
                    '<span class="rec-matrix-main-form-marker" '
                    f'data-service="{escape(service_key)}" '
                    f'data-default-topic="{escape(default_topic)}" '
                    f'data-default-platforms="{escape(default_platform_text)}" '
                    f'data-default-score="{int(default_score)}" '
                    f'data-applied-active="{str(applied_filter_active).lower()}" '
                    'aria-hidden="true"></span>'
                ),
                unsafe_allow_html=True,
            )

            # Platform dibuat lebih lebar agar tiga pilihan utama tetap sejajar
            # horizontal dan tidak menambah tinggi form.
            control_1, control_2, control_3, control_reset, control_apply = st.columns(
                [1.00, 1.85, 0.80, 0.78, 0.95],
                gap="medium",
            )
            with control_1:
                st.selectbox(
                    "Fokus topik",
                    options=topic_labels,
                    key=keys["topic_widget"],
                    help="Kolom ini dipakai untuk mengurutkan influencer dari skor tertinggi.",
                )
            with control_2:
                st.multiselect(
                    "Filter platform",
                    options=platform_labels,
                    key=keys["platform_widget"],
                    help="Kosongkan semua pilihan untuk menampilkan semua platform.",
                )
            with control_3:
                st.slider(
                    "Skor minimum",
                    min_value=1,
                    max_value=10,
                    step=1,
                    key=keys["score_widget"],
                    help="Naikkan nilai ini untuk menyaring hanya influencer dengan kecocokan tinggi.",
                )
            with control_reset:
                st.markdown("<div style='height: 31px;'></div>", unsafe_allow_html=True)
                st.form_submit_button(
                    "Reset Filter",
                    use_container_width=True,
                    on_click=_reset_matrix_filter_state,
                    args=(layanan, topic_labels, platform_labels),
                )
            with control_apply:
                st.markdown("<div style='height: 31px;'></div>", unsafe_allow_html=True)
                st.form_submit_button(
                    "Terapkan Filter",
                    use_container_width=True,
                    type="primary",
                    on_click=_apply_matrix_filter_state,
                    args=(layanan, topic_labels, platform_labels),
                )

        # Tombol tetap terlihat seperti tombol biasa, tetapi benar-benar inert
        # saat semua kontrol masih default dan belum ada filter aktif. Guard JS
        # juga memperbarui status tombol langsung saat draft berubah di form,
        # tanpa meminta rerun ke server.
        _render_matrix_filter_interaction_guard(layanan)

        # Callback hanya mengisi event saat Apply/Reset benar-benar mengubah state.
        # Apply tanpa perubahan pada filter aktif tetap berhenti di fragment ini.
        if bool(st.session_state.pop(keys["event"], False)):
            st.rerun(scope="app")
    except Exception as exc:
        st.error(f"Kontrol filter matriks tidak dapat ditampilkan. Detail: {exc}")


def _render_interactive_matrix(score_matrix: pd.DataFrame, layanan: str) -> None:
    """Render matriks dengan kontrol interaktif Streamlit."""
    try:
        _render_matrix_intro(layanan)
        if score_matrix is None or score_matrix.empty:
            _render_matrix_unavailable_state(layanan)
            return

        topic_label_to_key = {str(item["singkat"]): str(item["key"]) for item in TOPIC_CONFIG}
        platform_label_to_key = _matrix_platform_options()
        topic_labels = list(topic_label_to_key.keys())
        platform_labels = list(platform_label_to_key.keys())

        _render_matrix_filter_fragment(
            layanan,
            topic_labels,
            platform_labels,
        )
        selected_topic_label, selected_platform_labels, min_score = (
            _applied_matrix_filter_values(
                layanan,
                topic_labels,
                platform_labels,
            )
        )

        selected_topic_key = topic_label_to_key.get(
            selected_topic_label,
            next(iter(topic_label_to_key.values())),
        )
        selected_platforms = [
            platform_label_to_key[label]
            for label in selected_platform_labels
            if label in platform_label_to_key
        ]
        if not selected_platforms:
            selected_platforms = list(PLATFORM_ORDER)

        keys = _matrix_filter_state_keys(layanan)
        feedback = str(st.session_state.pop(keys["feedback"], "")).strip()
        if feedback == "apply":
            st.toast("Filter matriks berhasil diterapkan.", icon="✅")
        elif feedback == "reset":
            st.toast("Filter matriks dikembalikan ke pengaturan awal.", icon="↩️")

        filtered_matrix = _filter_matrix_for_display(
            score_matrix,
            selected_topic_key,
            selected_platforms,
            min_score,
        )
        _render_matrix_summary_cards(filtered_matrix, selected_topic_key, min_score)
        if filtered_matrix.empty:
            return

        _render_matrix_rank_cards(filtered_matrix, selected_topic_key)

        heatmap = _build_heatmap_figure(filtered_matrix, selected_topic_key)
        if heatmap is None:
            st.warning("Grafik tidak dapat ditampilkan.")
            return
        st.plotly_chart(
            heatmap,
            use_container_width=True,
            config={
                "displaylogo": False,
                "responsive": True,
                "scrollZoom": True,
                "modeBarButtonsToRemove": ["lasso2d", "select2d"],
                "toImageButtonOptions": {
                    "format": "png",
                    "filename": f"matriks_influencer_{layanan.lower()}_{_safe_key(selected_topic_key)}",
                    "scale": 2,
                },
            },
        )
        _render_matrix_table(filtered_matrix)
    except Exception as exc:
        st.error(f"Matriks interaktif gagal ditampilkan: {exc}")


# -----------------------------------------------------------------------------
# HELPER LOADING CUSTOM
# -----------------------------------------------------------------------------


def _start_recommendation_page_loading():
    """Tampilkan loader halaman saat pengguna baru masuk ke Rekomendasi.

    Overlay dipertahankan sampai seluruh section halaman selesai dibentuk pada
    siklus render yang sama. Dengan begitu pengguna tidak melihat halaman setengah
    jadi ketika Streamlit masih mengirim kartu, tabel, grafik, dan iframe ke browser.
    """
    try:
        if callable(mulai_loading_global):
            return mulai_loading_global("Rekomendasi")
    except Exception:
        return None
    return None


def _finish_recommendation_page_loading(handle: Any) -> None:
    """Tutup loader awal halaman tanpa memengaruhi loader aksi lain."""
    try:
        if handle is not None and callable(selesaikan_loading_global):
            selesaikan_loading_global(handle)
    except Exception:
        return None


def _start_recommendation_loading(label: str):
    """Tampilkan overlay loading custom bawaan proyek untuk aksi halaman rekomendasi."""
    try:
        if callable(mulai_loading_aksi):
            handle = mulai_loading_aksi(label)
            # Jeda singkat agar animasi custom sempat terlihat,
            # terutama pada filter yang proses komputasinya sangat cepat.
            time.sleep(0.55)
            return handle
    except Exception:
        return None
    return None


def _finish_recommendation_loading(handle: Any) -> None:
    """Tutup overlay loading custom tanpa membuat halaman crash."""
    try:
        if handle is not None and callable(selesaikan_loading_aksi):
            selesaikan_loading_aksi(handle)
    except Exception:
        return None


def _show_account_type_filter_loading() -> None:
    """Aktifkan loading custom saat filter tipe akun rekomendasi diganti."""
    try:
        selected_type = str(
            st.session_state.get(ACCOUNT_TYPE_FILTER_KEY, "Semua")
        ).strip()
        loading_labels = {
            "Semua": "Menampilkan semua akun rekomendasi...",
            "Influencer": "Memfilter akun influencer...",
            "Akun Media": "Memfilter akun media...",
        }
        st.session_state[RECOMMENDATION_ACTION_LOADING_KEY] = loading_labels.get(
            selected_type,
            "Memperbarui filter tipe akun...",
        )
    except Exception:
        st.session_state[RECOMMENDATION_ACTION_LOADING_KEY] = (
            "Memperbarui filter tipe akun..."
        )


def _show_matrix_account_detail_loading() -> None:
    """Aktifkan loading custom saat akun pada tabel skor detail diganti."""
    try:
        selected_account = str(
            st.session_state.get("rec_matrix_table_selected_account", "akun terpilih")
        ).strip()
        selected_account = selected_account or "akun terpilih"
        st.session_state[RECOMMENDATION_ACTION_LOADING_KEY] = (
            f"Memuat detail skor @{selected_account}..."
        )
    except Exception:
        st.session_state[RECOMMENDATION_ACTION_LOADING_KEY] = "Memuat detail skor akun..."


def _show_matrix_table_filter_loading() -> None:
    """Aktifkan loading custom saat tombol filter tabel interaktif diklik."""
    try:
        st.session_state[RECOMMENDATION_ACTION_LOADING_KEY] = "Menerapkan filter tabel rekomendasi..."
    except Exception:
        return None


def _show_matrix_filter_loading(layanan: str = "") -> None:
    """Aktifkan loading custom saat tombol Terapkan Filter matriks utama diklik."""
    try:
        layanan_text = str(layanan or "layanan terpilih").strip()
        st.session_state[RECOMMENDATION_ACTION_LOADING_KEY] = (
            f"Menerapkan filter matriks rekomendasi {layanan_text}..."
        )
    except Exception:
        st.session_state[RECOMMENDATION_ACTION_LOADING_KEY] = "Menerapkan filter matriks rekomendasi..."


def _show_service_filter_loading() -> None:
    """Aktifkan loading custom saat filter layanan diganti."""
    try:
        layanan_text = str(
            st.session_state.get("recommendation_service_selector", "layanan terpilih")
        ).strip()
        st.session_state[RECOMMENDATION_ACTION_LOADING_KEY] = (
            f"Memuat rekomendasi untuk {layanan_text or 'layanan terpilih'}..."
        )
    except Exception:
        st.session_state[RECOMMENDATION_ACTION_LOADING_KEY] = "Memuat rekomendasi layanan..."


def _render_strategic_summary(points: list[str]) -> None:
    """Tampilkan ringkasan strategis yang responsif terhadap Light/Dark Theme.

    Komponen tetap menggunakan iframe HTML internal agar layout tiga kartu konsisten.
    Efek visual kontinu yang berat sengaja dihindari supaya scroll pertama tetap mulus.
    """
    try:
        dark_mode = bool(st.session_state.get("dark_mode", False))
    except Exception:
        dark_mode = False

    theme_class = "theme-dark" if dark_mode else "theme-light"
    color_scheme = "dark" if dark_mode else "light"

    item_meta = [
        {"ikon": "✦", "label": "Prioritas Konten", "class": "content"},
        {"ikon": "◈", "label": "Kolaborasi Akun", "class": "creator"},
        {"ikon": "↗", "label": "Respons Cepat", "class": "response"},
    ]
    items = "".join(
        f"""
        <article class="rec-strategy-item rec-strategy-item-{index} tone-{item_meta[index - 1]['class']}">
            <div class="rec-strategy-number-wrap">
                <div class="rec-strategy-icon">{item_meta[index - 1]['ikon']}</div>
                <div class="rec-strategy-number">{index}</div>
            </div>
            <div class="rec-strategy-body">
                <div class="rec-strategy-mini-label">{item_meta[index - 1]['label']}</div>
                <div class="rec-strategy-text">{point}</div>
            </div>
        </article>
        """
        for index, point in enumerate(points[:3], start=1)
    )

    html = f"""
    <!doctype html>
    <html lang="id">
    <head>
        <meta charset="utf-8" />
        <style>
            :root {{
                color-scheme: {color_scheme};
                --red: #E53935;
                --orange: #F59E0B;
                --cyan: #1DA1F2;
                --purple: #8B5CF6;
                --green: #22A55B;
            }}
            * {{ box-sizing: border-box; }}
            html, body {{
                margin: 0;
                padding: 0;
                width: 100%;
                background: transparent;
                overflow: hidden;
                font-family: 'Inter', 'Plus Jakarta Sans', system-ui, -apple-system, BlinkMacSystemFont, sans-serif;
            }}
            body {{
                padding: 0;
            }}
            .rec-strategy-showcase {{
                position: relative;
                isolation: isolate;
                width: 100%;
                padding: 22px;
                overflow: hidden;
                border-radius: 24px;
                contain: layout paint style;
            }}
            .rec-strategy-showcase::before,
            .rec-strategy-showcase::after {{
                content: "";
                position: absolute;
                pointer-events: none;
                z-index: -1;
            }}
            .rec-strategy-showcase::before {{
                inset: 0;
            }}
            .rec-strategy-showcase::after {{
                inset: 0;
                background-image:
                    linear-gradient(90deg, currentColor 1px, transparent 1px),
                    linear-gradient(0deg, currentColor 1px, transparent 1px);
                background-size: 52px 52px;
                opacity: .025;
            }}
            .rec-strategy-top {{
                position: relative;
                display: flex;
                align-items: center;
                justify-content: space-between;
                gap: 16px;
                margin-bottom: 16px;
                padding: 14px 16px;
                border-radius: 18px;
            }}
            .rec-strategy-heading {{
                display: flex;
                align-items: center;
                gap: 12px;
                min-width: 0;
            }}
            .rec-strategy-heading-icon {{
                display: grid;
                place-items: center;
                flex: 0 0 auto;
                width: 44px;
                height: 44px;
                border-radius: 15px;
                color: #FFFFFF;
                background: linear-gradient(135deg, #E53935, #FF8A36 58%, #F7B32B);
                font-size: 20px;
                box-shadow: 0 8px 20px rgba(229,57,53,.20);
            }}
            .rec-strategy-heading span {{
                display: block;
                font-size: 12px;
                font-weight: 900;
                letter-spacing: .13em;
                text-transform: uppercase;
            }}
            .rec-strategy-heading strong {{
                display: block;
                margin-top: 2px;
                font-size: 18px;
                font-weight: 950;
                line-height: 1.2;
                letter-spacing: -.03em;
            }}
            .rec-strategy-badges {{
                display: flex;
                flex-wrap: wrap;
                justify-content: flex-end;
                gap: 8px;
            }}
            .rec-badge {{
                display: inline-flex;
                align-items: center;
                gap: 6px;
                padding: 8px 11px;
                border-radius: 999px;
                font-size: 12px;
                font-weight: 900;
                white-space: nowrap;
            }}
            .rec-strategy-list {{
                position: relative;
                display: grid;
                grid-template-columns: repeat(3, minmax(0, 1fr));
                gap: 14px;
            }}
            .rec-strategy-item {{
                --tone: #E53935;
                position: relative;
                min-height: 190px;
                padding: 18px 17px 17px;
                overflow: hidden;
                border-radius: 20px;
                transition: transform .18s ease, border-color .18s ease, box-shadow .18s ease;
            }}
            .rec-strategy-item:hover {{
                transform: translateY(-3px);
            }}
            .rec-strategy-item::before {{
                content: "";
                position: absolute;
                inset: 0;
                z-index: 0;
                pointer-events: none;
            }}
            .rec-strategy-item::after {{
                content: "";
                position: absolute;
                left: 16px;
                right: 16px;
                bottom: 0;
                height: 3px;
                border-radius: 999px 999px 0 0;
                background: linear-gradient(90deg, transparent, var(--tone), transparent);
                opacity: .92;
            }}
            .tone-content {{ --tone: #E53935; }}
            .tone-creator {{ --tone: #1DA1F2; }}
            .tone-response {{ --tone: #22A55B; }}
            .rec-strategy-number-wrap {{
                position: relative;
                z-index: 1;
                display: flex;
                align-items: center;
                justify-content: space-between;
                margin-bottom: 17px;
            }}
            .rec-strategy-icon,
            .rec-strategy-number {{
                display: grid;
                place-items: center;
                color: #FFFFFF;
                background: var(--tone);
                border: 1px solid color-mix(in srgb, var(--tone) 72%, #FFFFFF);
                box-shadow: 0 7px 18px color-mix(in srgb, var(--tone) 18%, transparent);
                font-weight: 950;
            }}
            .rec-strategy-icon {{
                width: 42px;
                height: 42px;
                border-radius: 14px;
                font-size: 18px;
            }}
            .rec-strategy-number {{
                min-width: 36px;
                height: 36px;
                padding: 0 10px;
                border-radius: 999px;
                font-size: 13px;
            }}
            .rec-strategy-body {{
                position: relative;
                z-index: 1;
            }}
            .rec-strategy-mini-label {{
                display: inline-flex;
                align-items: center;
                max-width: 100%;
                margin-bottom: 10px;
                padding: 6px 10px;
                border-radius: 999px;
                font-size: 12px;
                font-weight: 950;
                letter-spacing: .08em;
                text-transform: uppercase;
            }}
            .rec-strategy-text {{
                font-size: 14px;
                font-weight: 720;
                line-height: 1.58;
                text-wrap: pretty;
            }}
            .rec-strategy-text strong {{
                font-weight: 950;
            }}
            .rec-strategy-footer {{
                position: relative;
                display: flex;
                align-items: center;
                justify-content: space-between;
                gap: 14px;
                margin-top: 14px;
                padding: 12px 14px;
                border-radius: 16px;
                font-size: 12px;
                font-weight: 750;
            }}
            .rec-footer-line {{
                flex: 1 1 auto;
                height: 2px;
                border-radius: 999px;
                background: linear-gradient(90deg, #E53935, #F59E0B, #1DA1F2, #22A55B);
            }}

            /* -------------------------------------------------------------
               LIGHT THEME — surface terang, berwarna, dan kontras tinggi.
               ------------------------------------------------------------- */
            .rec-strategy-showcase.theme-light {{
                color: #172033;
                border: 1px solid #D9E5EF;
                border-left: 5px solid #E53935;
                background:
                    linear-gradient(135deg, #FFF9F8 0%, #F7FBFF 45%, #F7FFF9 100%);
                box-shadow:
                    0 16px 36px rgba(15,23,42,.10),
                    inset 0 1px 0 rgba(255,255,255,.96);
            }}
            .rec-strategy-showcase.theme-light::before {{
                background:
                    radial-gradient(circle at 9% 8%, rgba(229,57,53,.14), transparent 27%),
                    radial-gradient(circle at 88% 8%, rgba(29,161,242,.13), transparent 29%),
                    radial-gradient(circle at 72% 94%, rgba(34,165,91,.10), transparent 30%),
                    radial-gradient(circle at 42% 72%, rgba(139,92,246,.07), transparent 34%);
            }}
            .theme-light .rec-strategy-top {{
                border: 1px solid #E2E8F0;
                background: rgba(255,255,255,.84);
                box-shadow: 0 8px 22px rgba(15,23,42,.055);
            }}
            .theme-light .rec-strategy-heading span {{ color: #8B5960; }}
            .theme-light .rec-strategy-heading strong {{ color: #172033; }}
            .theme-light .rec-badge {{
                color: #344054;
                background: #FFFFFF;
                border: 1px solid #E2E8F0;
                box-shadow: 0 4px 12px rgba(15,23,42,.05);
            }}
            .theme-light .rec-badge.red {{ color: #B42318; background: #FFF1F0; border-color: #F5B8B4; }}
            .theme-light .rec-badge.blue {{ color: #1769AA; background: #EFF8FF; border-color: #B8DCF5; }}
            .theme-light .rec-badge.green {{ color: #167044; background: #ECFDF3; border-color: #B9E6CA; }}
            .theme-light .rec-strategy-item {{
                border: 1px solid color-mix(in srgb, var(--tone) 24%, #DCE5EE);
                background:
                    linear-gradient(145deg,
                        color-mix(in srgb, var(--tone) 8%, #FFFFFF) 0%,
                        #FFFFFF 72%);
                box-shadow:
                    0 11px 24px rgba(15,23,42,.075),
                    inset 0 1px 0 #FFFFFF;
            }}
            .theme-light .rec-strategy-item:hover {{
                border-color: color-mix(in srgb, var(--tone) 48%, #CDD8E4);
                box-shadow:
                    0 16px 30px rgba(15,23,42,.11),
                    0 0 20px color-mix(in srgb, var(--tone) 10%, transparent),
                    inset 0 1px 0 #FFFFFF;
            }}
            .theme-light .rec-strategy-item::before {{
                background:
                    radial-gradient(circle at 88% 12%, color-mix(in srgb, var(--tone) 12%, transparent), transparent 38%);
            }}
            .theme-light .rec-strategy-mini-label {{
                color: color-mix(in srgb, var(--tone) 72%, #172033);
                background: color-mix(in srgb, var(--tone) 9%, #FFFFFF);
                border: 1px solid color-mix(in srgb, var(--tone) 28%, #E2E8F0);
            }}
            .theme-light .rec-strategy-text {{ color: #344054; }}
            .theme-light .rec-strategy-text strong {{ color: #172033; }}
            .theme-light .rec-strategy-footer {{
                color: #536174;
                border: 1px solid #E2E8F0;
                background: rgba(255,255,255,.82);
            }}
            .theme-light .rec-strategy-footer strong {{ color: #172033; }}

            /* -------------------------------------------------------------
               DARK THEME — mempertahankan karakter Minimalist with Deep.
               ------------------------------------------------------------- */
            .rec-strategy-showcase.theme-dark {{
                color: #FFFFFF;
                border: 1px solid rgba(255,255,255,.10);
                border-left: 5px solid #E53935;
                background:
                    radial-gradient(circle at 10% 12%, rgba(229,57,53,.24), transparent 27%),
                    radial-gradient(circle at 86% 8%, rgba(29,161,242,.18), transparent 30%),
                    linear-gradient(135deg, rgba(35,14,18,.98), rgba(10,18,25,.98) 48%, rgba(11,11,12,.99));
                box-shadow:
                    0 18px 44px rgba(0,0,0,.35),
                    inset 0 1px 0 rgba(255,255,255,.07);
            }}
            .theme-dark .rec-strategy-top {{
                border: 1px solid rgba(255,255,255,.10);
                background: rgba(255,255,255,.045);
            }}
            .theme-dark .rec-strategy-heading span {{ color: rgba(255,255,255,.56); }}
            .theme-dark .rec-strategy-heading strong {{ color: #FFFFFF; }}
            .theme-dark .rec-badge {{
                color: #FFFFFF;
                border: 1px solid rgba(255,255,255,.11);
            }}
            .theme-dark .rec-badge.red {{ background: rgba(229,57,53,.18); border-color: rgba(229,57,53,.38); }}
            .theme-dark .rec-badge.blue {{ background: rgba(29,161,242,.16); border-color: rgba(29,161,242,.36); }}
            .theme-dark .rec-badge.green {{ background: rgba(34,165,91,.16); border-color: rgba(34,165,91,.36); }}
            .theme-dark .rec-strategy-item {{
                border: 1px solid rgba(255,255,255,.10);
                background: linear-gradient(145deg, rgba(255,255,255,.075), rgba(255,255,255,.025));
                box-shadow: 0 15px 32px rgba(0,0,0,.26), inset 0 1px 0 rgba(255,255,255,.07);
            }}
            .theme-dark .rec-strategy-item:hover {{
                border-color: color-mix(in srgb, var(--tone) 58%, rgba(255,255,255,.15));
                box-shadow: 0 20px 38px rgba(0,0,0,.33), 0 0 22px color-mix(in srgb, var(--tone) 18%, transparent);
            }}
            .theme-dark .rec-strategy-item::before {{
                background:
                    radial-gradient(circle at 82% 18%, color-mix(in srgb, var(--tone) 22%, transparent), transparent 38%);
            }}
            .theme-dark .rec-strategy-mini-label {{
                color: #FFFFFF;
                background: color-mix(in srgb, var(--tone) 16%, rgba(255,255,255,.05));
                border: 1px solid color-mix(in srgb, var(--tone) 32%, rgba(255,255,255,.09));
            }}
            .theme-dark .rec-strategy-text {{ color: rgba(255,255,255,.84); }}
            .theme-dark .rec-strategy-text strong {{ color: #FFFFFF; }}
            .theme-dark .rec-strategy-footer {{
                color: rgba(255,255,255,.72);
                border: 1px solid rgba(255,255,255,.09);
                background: rgba(255,255,255,.04);
            }}
            .theme-dark .rec-strategy-footer strong {{ color: #FFFFFF; }}

            @media (max-width: 980px) {{
                .rec-strategy-showcase {{ padding: 18px; }}
                .rec-strategy-top {{ align-items: flex-start; flex-direction: column; }}
                .rec-strategy-badges {{ justify-content: flex-start; }}
                .rec-strategy-list {{ grid-template-columns: 1fr; }}
                .rec-strategy-item {{ min-height: 0; }}
            }}
            @media (max-width: 560px) {{
                .rec-strategy-showcase {{ padding: 15px; border-radius: 18px; }}
                .rec-strategy-heading-icon {{ width: 38px; height: 38px; border-radius: 13px; }}
                .rec-strategy-heading strong {{ font-size: 15px; }}
                .rec-strategy-badges {{ gap: 6px; }}
                .rec-badge {{ padding: 7px 9px; }}
                .rec-strategy-text {{ font-size: 13px; line-height: 1.52; }}
            }}
            @media (prefers-reduced-motion: reduce) {{
                .rec-strategy-item {{ transition: none !important; }}
                .rec-strategy-item:hover {{ transform: none !important; }}
            }}
        </style>
    </head>
    <body>
        <section class="rec-strategy-showcase {theme_class}" aria-label="Ringkasan strategi rekomendasi">
            <header class="rec-strategy-top">
                <div class="rec-strategy-heading">
                    <div class="rec-strategy-heading-icon">⚡</div>
                    <div>
                        <span>Strategy cockpit</span>
                        <strong>Prioritas aksi siap dipakai</strong>
                    </div>
                </div>
                <div class="rec-strategy-badges" aria-label="Fokus ringkasan">
                    <span class="rec-badge red">● Konten</span>
                    <span class="rec-badge blue">● Influencer</span>
                    <span class="rec-badge green">● Respons</span>
                </div>
            </header>

            <main class="rec-strategy-list">
                {items}
            </main>

            <footer class="rec-strategy-footer">
                <span><strong>Output:</strong> kalender konten, kolaborasi akun, dan pola respons layanan.</span>
                <span class="rec-footer-line" aria-hidden="true"></span>
            </footer>
        </section>
    </body>
    </html>
    """

    # Tinggi otomatis + tanpa nested scrollbar iframe membuat scroll halaman utama
    # lebih ringan dan menghilangkan ruang kosong gelap pada Light Theme.
    render_html_iframe(html, height="content", scrolling=False)


# -----------------------------------------------------------------------------
# TAHAP 4 | FASE 12 - CACHING DAN FALLBACK GEMINI
# -----------------------------------------------------------------------------


def _ai_topic_options(topic_summary: pd.DataFrame) -> list[str]:
    """Ambil topik dinamis dari hasil analisis dan gunakan dummy bila kosong."""
    try:
        if isinstance(topic_summary, pd.DataFrame) and not topic_summary.empty:
            values = [
                str(value).strip()
                for value in topic_summary.get("topik", pd.Series(dtype=str)).tolist()
                if str(value).strip()
            ]
            if values:
                return list(dict.fromkeys(values))
    except Exception:
        pass

    try:
        dummy = get_dummy_topic_data()
        for candidate in ("topik", "topic", "topic_name", "name"):
            if candidate in dummy.columns:
                values = [str(value).strip() for value in dummy[candidate].tolist() if str(value).strip()]
                if values:
                    return list(dict.fromkeys(values))
    except Exception:
        pass

    return [
        "Gangguan Internet",
        "Kecepatan Lambat",
        "Layanan CS",
        "Harga Paket",
        "Pemasangan Baru",
        "Tagihan",
        "Lainnya",
    ]


def _ai_topic_context(topic_summary: pd.DataFrame, selected_topic: str) -> tuple[str, list[str]]:
    """Ambil sentimen dominan dan kata kunci topik yang dipilih."""
    sentiment = "netral"
    keywords: list[str] = []
    try:
        selected = topic_summary[topic_summary["topik"].astype(str).eq(str(selected_topic))]
        if not selected.empty:
            raw_sentiment = str(selected.iloc[0].get("sentimen_dominan", "neutral"))
            sentiment = SENTIMENT_LABELS.get(raw_sentiment, raw_sentiment).casefold()
            topic_key = str(selected.iloc[0].get("key", ""))
            topic_config = next(
                (item for item in TOPIC_CONFIG if str(item.get("key")) == topic_key),
                None,
            )
            if topic_config:
                keywords = [str(item) for item in topic_config.get("keywords", ())[:10]]
    except Exception:
        pass
    return sentiment, keywords


def _generate_ai_idea_payload(
    layanan: str,
    platform: str,
    topik: str,
    sentimen: str,
    keywords: list[str],
) -> dict[str, Any]:
    """Generate ide dengan fallback penuh tanpa membiarkan halaman crash."""
    fallback = get_fallback_content_idea(layanan, platform, topik, sentimen)
    if bool(st.session_state.get("demo_mode", False)):
        return {
            "text": fallback,
            "is_fallback": True,
            "layanan": layanan,
            "platform": platform,
            "topik": topik,
            "sentimen": sentimen,
        }
    try:
        result = generate_content_idea(topik, keywords, platform, sentimen, layanan)
        clean_result = str(result or "").strip() or fallback
        return {
            "text": clean_result,
            "is_fallback": clean_result.strip() == fallback.strip(),
            "layanan": layanan,
            "platform": platform,
            "topik": topik,
            "sentimen": sentimen,
        }
    except Exception as error:
        st.error(
            "Ide konten AI tidak dapat diproses. Dashboard tetap menampilkan "
            f"ide cadangan. Detail: {type(error).__name__}."
        )
        return {
            "text": fallback,
            "is_fallback": True,
            "layanan": layanan,
            "platform": platform,
            "topik": topik,
            "sentimen": sentimen,
        }


def _format_ai_result_html(raw_text: str) -> str:
    """Ubah teks ide menjadi blok visual yang aman dan mudah dipindai."""
    lines = [line.strip() for line in str(raw_text or "").splitlines() if line.strip()]
    if not lines:
        return '<p class="rec-ai-copy-text">Ide konten belum tersedia.</p>'

    blocks: list[str] = []
    for line in lines:
        upper_line = line.upper()
        numbered = re.match(r"^(\d+)[\.)]\s*(.+)$", line)

        if "JUDUL KONTEN" in upper_line or "JUDUL IDE" in upper_line:
            label, separator, value = line.partition(":")
            if not separator:
                value = line
                label = "Judul konten"
            blocks.append(
                '<div class="rec-ai-content-title">'
                f'<strong>{escape(label.strip())}</strong><br>'
                f'{escape(value.strip())}'
                '</div>'
            )
            continue

        if numbered:
            blocks.append(
                '<div class="rec-ai-idea-row">'
                f'<span class="rec-ai-idea-number">{escape(numbered.group(1))}</span>'
                f'<p>{escape(numbered.group(2))}</p>'
                '</div>'
            )
            continue

        if (
            "IDE KONTEN" in upper_line
            or "CALL TO ACTION" in upper_line
            or upper_line.startswith("CTA")
        ):
            blocks.append(f'<div class="rec-ai-copy-heading">{escape(line)}</div>')
            continue

        blocks.append(f'<p class="rec-ai-copy-text">{escape(line)}</p>')

    return "".join(blocks)


def _render_ai_result(payload: dict[str, Any]) -> None:
    """Tampilkan hasil Gemini atau fallback dalam card interaktif."""
    if not payload:
        return

    is_fallback = bool(payload.get("is_fallback"))
    if is_fallback:
        st.markdown(
            '<div class="rec-ai-fallback-note">Gemini tidak merespons. '
            'Ide cadangan lokal ditampilkan agar alur kerja tetap berjalan.</div>',
            unsafe_allow_html=True,
        )

    raw_text = str(payload.get("text", ""))
    result_html = _format_ai_result_html(raw_text)
    source_class = "fallback" if is_fallback else "live"
    source_label = "Fallback lokal" if is_fallback else "Gemini AI"
    layanan_label = escape(str(payload.get("layanan", "")))
    platform_label = escape(str(payload.get("platform", "")))
    topik_label = escape(str(payload.get("topik", "")))
    sentimen_label = escape(str(payload.get("sentimen", "netral")).title())

    st.markdown(
        dedent(
            f"""
            <section class="rec-ai-result">
                <header class="rec-ai-result-header">
                    <div class="rec-ai-result-title-wrap">
                        <div class="rec-ai-result-icon">💡</div>
                        <div>
                            <span class="rec-ai-result-kicker">Creative output</span>
                            <h3 class="rec-ai-result-heading">Ide Konten Rekomendasi</h3>
                        </div>
                    </div>
                    <span class="rec-ai-source-pill {source_class}">● {source_label}</span>
                </header>
                <div class="rec-ai-result-body">{result_html}</div>
                <footer class="rec-ai-result-meta">
                    <span class="rec-ai-meta-chip">🏷️ {layanan_label}</span>
                    <span class="rec-ai-meta-chip">📱 {platform_label}</span>
                    <span class="rec-ai-meta-chip">💬 {topik_label}</span>
                    <span class="rec-ai-meta-chip">◉ Sentimen {sentimen_label}</span>
                </footer>
            </section>
            """
        ).strip(),
        unsafe_allow_html=True,
    )
    with st.expander("📋 Buka teks siap salin", expanded=False):
        st.code(raw_text, language=None)


def _render_ai_generator(
    layanan: str,
    platform: str,
    topik: str,
    topic_summary: pd.DataFrame,
) -> None:
    """Render studio AI, tombol interaktif, refresh cache, dan hasil ide."""
    status = get_gemini_runtime_status()
    available = bool(status.get("available") or GEMINI_AVAILABLE)
    badge_class = "online" if available else "offline"
    badge_label = "Gemini AI Aktif" if available else "Mode Offline"
    ai_theme_class = (
        "rec-ai-theme-dark"
        if bool(st.session_state.get("dark_mode", False))
        else "rec-ai-theme-light"
    )

    st.markdown(
        dedent(
            f"""
            <style>
                /* Guard lokal: dikirim bersama markup agar AI Studio tetap terlihat
                   saat Streamlit melakukan rerun/reconciliation DOM. */
                #rec-ai-content-studio {{
                    display: block !important;
                    visibility: visible !important;
                    opacity: 1 !important;
                }}
                #rec-ai-content-studio .rec-ai-heading,
                #rec-ai-content-studio .rec-ai-brand,
                #rec-ai-content-studio .rec-ai-copy {{
                    visibility: visible !important;
                    opacity: 1 !important;
                }}
                #rec-ai-content-studio.rec-ai-theme-light {{
                    border-color: #D9E0E8;
                    background:
                        radial-gradient(circle at 8% 12%, rgba(229,57,53,.13), transparent 30%),
                        radial-gradient(circle at 92% 12%, rgba(29,161,242,.11), transparent 32%),
                        radial-gradient(circle at 72% 100%, rgba(76,175,80,.08), transparent 30%),
                        linear-gradient(145deg, #FFFFFF, #F7F9FC);
                }}
                #rec-ai-content-studio.rec-ai-theme-light h2 {{ color: #172033 !important; }}
                #rec-ai-content-studio.rec-ai-theme-light p {{ color: #5F6B7A !important; }}
                #rec-ai-content-studio.rec-ai-theme-dark {{
                    border-color: rgba(255,255,255,.12);
                    background:
                        radial-gradient(circle at 8% 12%, rgba(229,57,53,.26), transparent 30%),
                        radial-gradient(circle at 92% 12%, rgba(29,161,242,.20), transparent 32%),
                        radial-gradient(circle at 72% 100%, rgba(76,175,80,.12), transparent 30%),
                        linear-gradient(145deg, rgba(25,25,30,.99), rgba(10,12,18,.99));
                }}
                #rec-ai-content-studio.rec-ai-theme-dark h2 {{ color: #FFFFFF !important; }}
                #rec-ai-content-studio.rec-ai-theme-dark p {{ color: rgba(255,255,255,.69) !important; }}
            </style>
            <section id="rec-ai-content-studio" class="rec-ai-shell {ai_theme_class}" aria-label="Generator Ide Konten Gemini">
                <div class="rec-ai-orb one"></div>
                <div class="rec-ai-orb two"></div>
                <div class="rec-ai-heading">
                    <div class="rec-ai-brand">
                        <div class="rec-ai-logo">✦</div>
                        <div class="rec-ai-copy">
                            <span class="rec-ai-eyebrow">AI Content Studio</span>
                            <h2>Generator Ide Konten Gemini</h2>
                            <p>
                                Susun ide konten berdasarkan layanan, platform, topik,
                                dan sentimen dominan. Sistem tetap aman melalui cache
                                serta fallback lokal ketika koneksi atau kuota bermasalah.
                            </p>
                            <div class="rec-ai-feature-row">
                                <span class="rec-ai-feature-chip" style="--chip-color:#E53935"><i></i>3 ide siap pakai</span>
                                <span class="rec-ai-feature-chip" style="--chip-color:#1DA1F2"><i></i>Cache 5 menit</span>
                                <span class="rec-ai-feature-chip" style="--chip-color:#8B5CF6"><i></i>Berbasis sentimen</span>
                                <span class="rec-ai-feature-chip" style="--chip-color:#4CAF50"><i></i>Fallback otomatis</span>
                            </div>
                        </div>
                    </div>
                    <div class="rec-gemini-badge {badge_class}">{badge_label}</div>
                </div>
            </section>
            """
        ).strip(),
        unsafe_allow_html=True,
    )

    if not available:
        st.markdown(
            '<div class="rec-ai-offline-note">Mode Offline aktif. '
            'Ide konten statis tetap tersedia tanpa menghentikan halaman.</div>',
            unsafe_allow_html=True,
        )

    sentimen, keywords = _ai_topic_context(topic_summary, topik)

    # Refresh hanya menerima interaksi setelah ide berhasil dibuat untuk
    # kombinasi filter yang sedang aktif. Tampilan tombol tetap normal.
    payload = st.session_state.get("recommendation_ai_payload")
    current_signature = (layanan, platform, topik)
    payload_signature = (None, None, None)
    if isinstance(payload, dict):
        payload_signature = (
            payload.get("layanan"),
            payload.get("platform"),
            payload.get("topik"),
        )
    refresh_ready = isinstance(payload, dict) and current_signature == payload_signature

    generate_col, refresh_col = st.columns([1.55, 1.0], gap="small")
    generate_clicked = generate_col.button(
        "✨ Buat Ide Konten dengan AI",
        key="recommendation_ai_generate_button",
        use_container_width=True,
        type="primary",
    )
    refresh_clicked_raw = refresh_col.button(
        "🔄 Refresh Ide",
        key="recommendation_ai_refresh_button",
        use_container_width=True,
    )

    if not refresh_ready:
        # Lapisan transparan logis: tombol tetap terlihat seperti desain AI Studio,
        # tetapi klik, hover, dan efek tekan tidak dijalankan sebelum ide tersedia.
        refresh_col.markdown(
            """
            <span class="rec-refresh-lock-marker" aria-hidden="true"></span>
            <style>
            div[data-testid="stColumn"]:has(.rec-refresh-lock-marker)
            div[data-testid="stButton"] > button {
                pointer-events: none !important;
                cursor: default !important;
            }
            div[data-testid="stColumn"]:has(.rec-refresh-lock-marker)
            div[data-testid="stButton"] > button:hover,
            div[data-testid="stColumn"]:has(.rec-refresh-lock-marker)
            div[data-testid="stButton"] > button:active {
                transform: none !important;
                box-shadow: none !important;
            }
            .rec-refresh-lock-marker {
                display: none !important;
            }
            </style>
            """,
            unsafe_allow_html=True,
        )

    # Perlindungan Python memastikan tidak ada proses refresh jika browser
    # tidak mendukung selector CSS :has().
    refresh_clicked = bool(refresh_clicked_raw and refresh_ready)

    if generate_clicked or refresh_clicked:
        loading_handle = None
        try:
            if refresh_clicked:
                # Bersihkan hanya cache ide konten Gemini. Cache CSV, model, dan
                # agregasi halaman lain tidak ikut terhapus.
                generate_content_idea.clear()
                st.markdown(
                    '<div class="rec-ai-refresh-notice">Cache berhasil dikosongkan. '
                    'Sistem sedang menyusun ide terbaru.</div>',
                    unsafe_allow_html=True,
                )

            loading_handle = _start_recommendation_loading(
                "Membuat ide konten dengan AI... Harap tunggu sebentar ⏳"
            )
            payload = _generate_ai_idea_payload(
                layanan=layanan,
                platform=platform,
                topik=topik,
                sentimen=sentimen,
                keywords=keywords,
            )
            st.session_state["recommendation_ai_payload"] = payload
            log_activity(
                "GEMINI_CONTENT",
                "Rekomendasi",
                f"Membuat ide konten AI untuk topik {topik} pada layanan {layanan}.",
                service=layanan,
                platform=platform,
                metadata={"topic": topik, "sentiment": sentimen, "refresh": refresh_clicked},
            )

            # Setelah generate pertama berhasil, jalankan ulang satu kali agar
            # status tombol Refresh Ide langsung membaca payload terbaru.
            # Tanpa rerun ini, CSS pengunci tombol masih berasal dari state
            # sebelum payload dibuat sehingga tombol baru aktif pada interaksi berikutnya.
            if generate_clicked:
                st.rerun()
        except Exception as error:
            log_activity(
                "GEMINI_CONTENT",
                "Rekomendasi",
                f"Pembuatan ide konten AI untuk topik {topik} gagal.",
                status="failed",
                service=layanan,
                platform=platform,
                metadata={"topic": topik, "error": str(error)},
            )
            st.error(
                "Terjadi kesalahan tak terduga saat membuat ide konten. "
                f"Detail: {type(error).__name__}."
            )
        finally:
            _finish_recommendation_loading(loading_handle)

    payload = st.session_state.get("recommendation_ai_payload")
    if isinstance(payload, dict):
        current_signature = (layanan, platform, topik)
        payload_signature = (
            payload.get("layanan"),
            payload.get("platform"),
            payload.get("topik"),
        )
        if current_signature == payload_signature:
            _render_ai_result(payload)


def _is_miscellaneous_topic(value: Any) -> bool:
    """Tandai label residual seperti Lainnya atau Topik Lainnya."""
    normalized = re.sub(
        r"[^a-z0-9]+",
        " ",
        str(value or "").casefold(),
    ).strip()
    return normalized in MISCELLANEOUS_TOPIC_ALIASES


def _clean_topic_label(value: Any) -> str:
    """Rapikan label topik tanpa mengubah nama yang tampil di Analisis Topik."""
    return re.sub(r"\s+", " ", str(value or "")).strip()


def _strategy_key_for_topic(topic_name: str, sentiment: str = "neutral") -> str:
    """Petakan nama topik aktual ke keluarga strategi dan visual yang relevan."""
    normalized = re.sub(
        r"[^a-z0-9]+",
        " ",
        str(topic_name or "").casefold(),
    ).strip()

    if any(token in normalized for token in ("bisnis", "umkm", "digitalisasi")):
        return "bisnis_digitalisasi"
    if "masa aktif" in normalized or ("tanya" in normalized and "kuota" in normalized):
        return "kuota_masa_aktif"
    if any(token in normalized for token in ("bantuan", "pelanggan", "admin", "customer service", "interaksi")):
        return "bantuan_admin"
    if any(token in normalized for token in ("harga", "tagihan", "paket", "kuota mahal", "mahal")):
        return "harga_kualitas"
    if any(token in normalized for token in ("provider", "starlink", "kompetitor", "perbandingan")):
        return "perbandingan_provider"
    if any(token in normalized for token in ("apresiasi", "brand", "puas", "terbaik")):
        return "apresiasi_layanan"
    if (
        "stabil" in normalized
        and "lambat" not in normalized
        and "gangguan" not in normalized
        and str(sentiment) == "positive"
    ):
        return "kecepatan_stabil"
    if any(token in normalized for token in ("gangguan", "jaringan", "sinyal", "lambat", "lemot", "kecepatan")):
        return "gangguan_jaringan"
    if str(sentiment) == "positive":
        return "apresiasi_layanan"
    if str(sentiment) == "negative":
        return "gangguan_jaringan"
    return "bantuan_admin"


def _normalise_strategy_topic_records(
    layanan: str,
    records: list[dict[str, Any]],
) -> pd.DataFrame:
    """Ubah record Analisis Topik menjadi struktur kartu Strategi per Topik."""
    clean_records: list[dict[str, Any]] = []
    seen: set[str] = set()

    # Persentase fallback dihitung terhadap lima topik asli, termasuk Lainnya,
    # agar angka pada kartu tetap konsisten dengan halaman Analisis Topik.
    denominator = max(
        sum(max(0, int(float(item.get("jumlah_komentar", 0) or 0))) for item in records),
        1,
    )

    for rank, item in enumerate(records[:5], start=1):
        topic_name = _clean_topic_label(item.get("topik", ""))
        if not topic_name or _is_miscellaneous_topic(topic_name):
            continue
        identity = topic_name.casefold()
        if identity in seen:
            continue
        seen.add(identity)

        count = max(0, int(float(item.get("jumlah_komentar", 0) or 0)))
        sentiment = str(item.get("sentimen_dominan", "neutral") or "neutral").lower()
        if sentiment not in SENTIMENT_LABELS:
            sentiment = _normalisasi_sentimen(sentiment)
        percentage_value = item.get("persentase")
        try:
            percentage = float(percentage_value)
        except (TypeError, ValueError):
            percentage = round(count / denominator * 100, 1)

        strategy_key = _strategy_key_for_topic(topic_name, sentiment)
        score_topic_key = {
            "bisnis_digitalisasi": "apresiasi_layanan",
            "kecepatan_stabil": "apresiasi_layanan",
            "kuota_masa_aktif": "bantuan_admin",
        }.get(strategy_key, strategy_key)
        clean_records.append(
            {
                "key": strategy_key,
                "strategy_key": strategy_key,
                "score_topic_key": score_topic_key,
                "topik": topic_name,
                "topik_singkat": topic_name,
                "jumlah_komentar": count,
                "persentase": max(0.0, min(100.0, percentage)),
                "sentimen_dominan": sentiment,
                "kata_kunci": str(item.get("kata_kunci", "") or ""),
                "contoh_komentar": str(item.get("contoh_komentar", "") or ""),
                "source_rank": rank,
                "layanan": layanan,
            }
        )

    return pd.DataFrame(clean_records)


def _indibiz_topic_signature() -> str:
    """Buat signature ringan agar cache berubah ketika output topik diperbarui."""
    try:
        stat = INDIBIZ_TOPIC_FILE.stat()
        return f"{INDIBIZ_TOPIC_FILE.resolve()}::{stat.st_size}::{stat.st_mtime_ns}"
    except OSError:
        return f"{INDIBIZ_TOPIC_FILE.resolve()}::missing"


@st.cache_data(show_spinner=False, max_entries=12)
def _load_indibiz_strategy_records_fast(file_signature: str) -> list[dict[str, Any]]:
    """Baca Top 5 IndiBiz tanpa mengimpor modul visual Analisis Topik."""
    del file_signature
    if not INDIBIZ_TOPIC_FILE.is_file():
        return []

    dataframe: pd.DataFrame | None = None
    for encoding in ("utf-8-sig", "utf-8", "latin-1"):
        try:
            candidate = pd.read_csv(
                INDIBIZ_TOPIC_FILE,
                encoding=encoding,
                sep=None,
                engine="python",
            )
            if not candidate.empty and len(candidate.columns) > 1:
                dataframe = candidate
                break
        except Exception:
            continue

    if dataframe is None or dataframe.empty:
        return []

    sentiment_col = _pilih_kolom(
        dataframe, ("sentiment", "sentimen", "predicted_sentiment")
    )
    topic_col = _pilih_kolom(
        dataframe, ("topik", "topic", "nama_topik", "topic_name")
    )
    if sentiment_col is None or topic_col is None:
        return []

    rank_col = _pilih_kolom(dataframe, ("topic_rank", "rank", "peringkat"))
    count_col = _pilih_kolom(
        dataframe, ("jumlah_komentar", "jumlah", "frekuensi", "count")
    )
    total_col = _pilih_kolom(dataframe, ("total_topik", "topic_total"))
    percentage_col = _pilih_kolom(
        dataframe, ("persentase_topik", "topic_percentage", "persentase")
    )
    dominant_col = _pilih_kolom(
        dataframe, ("sentimen_dominan", "dominant_sentiment")
    )
    keyword_col = _pilih_kolom(
        dataframe, ("keywords", "kata_kunci", "keyword", "top_words")
    )
    example_col = _pilih_kolom(
        dataframe, ("contoh_komentar", "example_comment", "examples")
    )

    work = pd.DataFrame(
        {
            "sentiment": dataframe[sentiment_col].map(_normalisasi_sentimen),
            "topik": dataframe[topic_col].fillna("").astype(str).str.strip(),
            "rank": (
                pd.to_numeric(dataframe[rank_col], errors="coerce")
                if rank_col is not None
                else pd.Series(float("nan"), index=dataframe.index)
            ),
            "count": (
                pd.to_numeric(dataframe[count_col], errors="coerce").fillna(0)
                if count_col is not None
                else pd.Series(0, index=dataframe.index, dtype=float)
            ),
            "total": (
                pd.to_numeric(dataframe[total_col], errors="coerce")
                if total_col is not None
                else pd.Series(float("nan"), index=dataframe.index)
            ),
            "percentage": (
                pd.to_numeric(dataframe[percentage_col], errors="coerce")
                if percentage_col is not None
                else pd.Series(float("nan"), index=dataframe.index)
            ),
            "dominant": (
                dataframe[dominant_col].map(_normalisasi_sentimen)
                if dominant_col is not None
                else pd.Series("", index=dataframe.index, dtype=str)
            ),
            "keywords": (
                dataframe[keyword_col].fillna("").astype(str)
                if keyword_col is not None
                else pd.Series("", index=dataframe.index, dtype=str)
            ),
            "examples": (
                dataframe[example_col].fillna("").astype(str)
                if example_col is not None
                else pd.Series("", index=dataframe.index, dtype=str)
            ),
        }
    )
    work = work[
        work["topik"].ne("")
        & work["sentiment"].isin(("positive", "neutral", "negative"))
    ].copy()
    if work.empty:
        return []

    topic_order = list(dict.fromkeys(work["topik"].astype(str).tolist()))
    fallback_rank = {topic: index + 1 for index, topic in enumerate(topic_order)}
    records: list[dict[str, Any]] = []

    for topic_name in topic_order:
        group = work[work["topik"].eq(topic_name)].copy()
        ranks = group["rank"].dropna()
        rank = int(ranks.min()) if not ranks.empty else fallback_rank[topic_name]

        sentiment_counts = {
            sentiment: int(
                group.loc[group["sentiment"].eq(sentiment), "count"].sum()
            )
            for sentiment in ("positive", "neutral", "negative")
        }
        count_from_rows = sum(sentiment_counts.values())
        total_values = group["total"].dropna()
        count = max(
            count_from_rows,
            int(total_values.max()) if not total_values.empty else 0,
        )

        if count_from_rows > 0:
            dominant = max(
                ("positive", "neutral", "negative"),
                key=lambda sentiment: (
                    sentiment_counts[sentiment],
                    {"negative": 2, "positive": 1, "neutral": 0}[sentiment],
                ),
            )
        else:
            dominant_values = [
                value
                for value in group["dominant"].astype(str).tolist()
                if value in ("positive", "neutral", "negative")
            ]
            dominant = (
                dominant_values[0]
                if dominant_values
                else str(group.iloc[0]["sentiment"])
            )

        keywords: list[str] = []
        for value in group["keywords"].tolist():
            for keyword in _pecah_kata_kunci(value):
                if keyword not in keywords:
                    keywords.append(keyword)

        examples = [
            item.strip()
            for value in group["examples"].tolist()
            for item in str(value).split("|||")
            if item.strip()
        ]
        percentage_values = group["percentage"].dropna()
        percentage = (
            float(percentage_values.max())
            if not percentage_values.empty
            else None
        )

        records.append(
            {
                "rank": rank,
                "topik": topic_name,
                "jumlah_komentar": count,
                "persentase": percentage,
                "sentimen_dominan": dominant,
                "kata_kunci": ", ".join(keywords[:12]),
                "contoh_komentar": " ||| ".join(examples[:3]),
            }
        )

    records.sort(
        key=lambda item: (
            int(item.get("rank", 999)),
            -int(item.get("jumlah_komentar", 0)),
            str(item.get("topik", "")).casefold(),
        )
    )
    return records[:5]


@st.cache_data(show_spinner=False, max_entries=12)
def _build_recommendation_topic_records(
    layanan: str,
    demo_mode: bool = False,
) -> pd.DataFrame:
    """Ambil Top 5 dengan agregasi ringan tanpa menghitung WordCloud dan matriks."""
    safe_service = (
        str(layanan).strip()
        if str(layanan).strip() in ACTIVE_LAYANAN_OPTIONS
        else RECOMMENDATION_FILTER_DEFAULTS["layanan"]
    )

    try:
        if demo_mode:
            summary = summarize_topics(get_demo_sentiment(safe_service), top_n=5)
            raw_records = (
                summary.head(5).to_dict("records")
                if isinstance(summary, pd.DataFrame) and not summary.empty
                else []
            )
        elif safe_service == "IndiBiz":
            raw_records = _load_indibiz_strategy_records_fast(
                _indibiz_topic_signature()
            )
        else:
            file_signature = get_sentiment_file_signature(safe_service)
            enriched = load_enriched_topic_data(safe_service, file_signature)
            summary = summarize_topics(enriched, top_n=5)
            raw_records = (
                summary.head(5).to_dict("records")
                if isinstance(summary, pd.DataFrame) and not summary.empty
                else []
            )

        result = _normalise_strategy_topic_records(safe_service, raw_records)
        if not result.empty:
            return result.reset_index(drop=True)
    except Exception:
        pass

    fallback = SERVICE_TOPIC_OPTION_FALLBACKS.get(
        safe_service,
        SERVICE_TOPIC_OPTION_FALLBACKS["IndiHome"],
    )
    return _normalise_strategy_topic_records(safe_service, fallback).reset_index(drop=True)


def _filter_topic_options(layanan: str) -> list[str]:
    """Sediakan topik layanan aktif dari sumber yang sama dengan Analisis Topik."""
    records = _build_recommendation_topic_records(
        layanan,
        bool(st.session_state.get("demo_mode", False)),
    )
    if not records.empty:
        return records["topik"].astype(str).tolist()
    return [RECOMMENDATION_FILTER_DEFAULTS["topik"]]


def _normalise_recommendation_filter_state() -> None:
    """Siapkan draft dan filter aktif sebelum widget filter dibuat."""
    service_options = list(ACTIVE_LAYANAN_OPTIONS)
    platform_options = ["Instagram", "TikTok", "Twitter"]

    if st.session_state.get("_active_service_sync_target") == "Rekomendasi":
        layanan_global = str(st.session_state.get("active_service", "IndiHome")).strip()
        if layanan_global not in service_options:
            layanan_global = RECOMMENDATION_FILTER_DEFAULTS["layanan"]
        topik_global = _filter_topic_options(layanan_global)[0]
        st.session_state[RECOMMENDATION_FILTER_ACTIVE_KEYS["layanan"]] = layanan_global
        st.session_state[RECOMMENDATION_FILTER_DRAFT_KEYS["layanan"]] = layanan_global
        st.session_state[RECOMMENDATION_FILTER_ACTIVE_KEYS["topik"]] = topik_global
        st.session_state[RECOMMENDATION_FILTER_DRAFT_KEYS["topik"]] = topik_global
        st.session_state["recommendation_service_selector"] = layanan_global
        st.session_state.pop("_active_service_sync_target", None)

    draft_service = str(
        st.session_state.get(
            RECOMMENDATION_FILTER_DRAFT_KEYS["layanan"],
            st.session_state.get(
                RECOMMENDATION_FILTER_ACTIVE_KEYS["layanan"],
                RECOMMENDATION_FILTER_DEFAULTS["layanan"],
            ),
        )
    ).strip()
    if draft_service not in service_options:
        draft_service = RECOMMENDATION_FILTER_DEFAULTS["layanan"]
    topic_options = _filter_topic_options(draft_service)
    default_topic = topic_options[0]

    if st.session_state.pop(RECOMMENDATION_FILTER_RESET_PENDING_KEY, False):
        reset_service = RECOMMENDATION_FILTER_DEFAULTS["layanan"]
        reset_topic = _filter_topic_options(reset_service)[0]
        dynamic_defaults = {
            "layanan": reset_service,
            "platform": RECOMMENDATION_FILTER_DEFAULTS["platform"],
            "topik": reset_topic,
        }
        for field, default_value in dynamic_defaults.items():
            st.session_state[RECOMMENDATION_FILTER_DRAFT_KEYS[field]] = default_value
            st.session_state[RECOMMENDATION_FILTER_ACTIVE_KEYS[field]] = default_value
        st.session_state["recommendation_service_selector"] = dynamic_defaults["layanan"]
        st.session_state["active_service"] = dynamic_defaults["layanan"]
        st.session_state["recommendation_ai_platform_selector"] = dynamic_defaults["platform"]
        st.session_state["recommendation_ai_topic_selector"] = dynamic_defaults["topik"]
        st.session_state.pop("recommendation_ai_payload", None)
        draft_service = reset_service
        topic_options = _filter_topic_options(draft_service)
        default_topic = topic_options[0]

    legacy_values = {
        "layanan": st.session_state.get(
            "recommendation_service_selector",
            RECOMMENDATION_FILTER_DEFAULTS["layanan"],
        ),
        "platform": st.session_state.get(
            "recommendation_ai_platform_selector",
            RECOMMENDATION_FILTER_DEFAULTS["platform"],
        ),
        "topik": st.session_state.get(
            "recommendation_ai_topic_selector",
            default_topic,
        ),
    }
    option_map = {
        "layanan": service_options,
        "platform": platform_options,
        "topik": topic_options,
    }
    default_map = {
        "layanan": RECOMMENDATION_FILTER_DEFAULTS["layanan"],
        "platform": RECOMMENDATION_FILTER_DEFAULTS["platform"],
        "topik": default_topic,
    }

    for field, options in option_map.items():
        active_key = RECOMMENDATION_FILTER_ACTIVE_KEYS[field]
        draft_key = RECOMMENDATION_FILTER_DRAFT_KEYS[field]
        default_value = default_map[field]
        candidate = str(legacy_values[field]).strip()
        if candidate not in options:
            candidate = default_value if default_value in options else options[0]

        if st.session_state.get(active_key) not in options:
            st.session_state[active_key] = candidate
        if st.session_state.get(draft_key) not in options:
            st.session_state[draft_key] = st.session_state[active_key]


def _sync_recommendation_topic_with_service() -> None:
    """Reset topik draft saat layanan diganti tanpa menerapkan analisis utama."""
    try:
        layanan = str(
            st.session_state.get(
                RECOMMENDATION_FILTER_DRAFT_KEYS["layanan"],
                RECOMMENDATION_FILTER_DEFAULTS["layanan"],
            )
        ).strip()
        if layanan not in ACTIVE_LAYANAN_OPTIONS:
            layanan = RECOMMENDATION_FILTER_DEFAULTS["layanan"]
            st.session_state[RECOMMENDATION_FILTER_DRAFT_KEYS["layanan"]] = layanan

        topic_options = _filter_topic_options(layanan)
        st.session_state[RECOMMENDATION_FILTER_DRAFT_KEYS["topik"]] = topic_options[0]
    except Exception as error:
        st.error(
            "Daftar topik layanan belum dapat diperbarui. "
            f"Detail: {type(error).__name__}."
        )


def _render_recommendation_filter_form() -> tuple[str, str, str]:
    """Render filter dinamis; nilai aktif berubah hanya setelah tombol diterapkan."""
    _normalise_recommendation_filter_state()

    # Widget tidak ditempatkan di dalam st.form karena pilihan layanan harus
    # langsung memicu rerun agar opsi topik selalu mengikuti layanan draft.
    # Nilai analisis tetap memakai state aktif hingga Terapkan Filter diklik.
    filter_service_col, filter_platform_col, filter_topic_col = st.columns(
        3,
        gap="medium",
    )
    with filter_service_col:
        st.selectbox(
            "Pilih Layanan",
            options=ACTIVE_LAYANAN_OPTIONS,
            key=RECOMMENDATION_FILTER_DRAFT_KEYS["layanan"],
            on_change=_sync_recommendation_topic_with_service,
            help=(
                "Mengganti layanan langsung memperbarui daftar topik, tetapi "
                "analisis belum berubah sampai tombol Terapkan Filter ditekan."
            ),
        )

    draft_service = str(
        st.session_state.get(
            RECOMMENDATION_FILTER_DRAFT_KEYS["layanan"],
            RECOMMENDATION_FILTER_DEFAULTS["layanan"],
        )
    ).strip()
    topic_options = _filter_topic_options(draft_service)
    draft_topic_key = RECOMMENDATION_FILTER_DRAFT_KEYS["topik"]
    if st.session_state.get(draft_topic_key) not in topic_options:
        st.session_state[draft_topic_key] = topic_options[0]

    with filter_platform_col:
        st.selectbox(
            "Pilih Platform",
            options=["Instagram", "TikTok", "Twitter"],
            key=RECOMMENDATION_FILTER_DRAFT_KEYS["platform"],
            help="Pilihan belum mengubah generator konten sampai tombol Terapkan Filter ditekan.",
        )

    with filter_topic_col:
        st.selectbox(
            "Pilih Topik",
            options=topic_options,
            key=draft_topic_key,
            help=(
                f"Topik hanya berasal dari Top 5 Analisis Topik {draft_service}, "
                "tanpa kategori Lainnya."
            ),
        )

    draft_values = {
        field: str(st.session_state.get(RECOMMENDATION_FILTER_DRAFT_KEYS[field], ""))
        for field in ("layanan", "platform", "topik")
    }
    active_values = {
        field: str(st.session_state.get(RECOMMENDATION_FILTER_ACTIVE_KEYS[field], ""))
        for field in ("layanan", "platform", "topik")
    }
    default_service = RECOMMENDATION_FILTER_DEFAULTS["layanan"]
    default_values = {
        "layanan": default_service,
        "platform": RECOMMENDATION_FILTER_DEFAULTS["platform"],
        "topik": _filter_topic_options(default_service)[0],
    }

    # Terapkan hanya aktif secara logis ketika draft berbeda dari filter aktif.
    # Reset hanya aktif ketika draft atau filter aktif tidak lagi berada pada nilai awal.
    apply_ready = draft_values != active_values
    reset_ready = draft_values != default_values or active_values != default_values

    apply_col, reset_col, spacer_col = st.columns([1.35, 1.35, 4.3], gap="small")
    with apply_col:
        apply_clicked_raw = st.button(
            "Terapkan Filter",
            type="primary",
            key="recommendation_main_filter_apply",
            use_container_width=True,
        )
        if not apply_ready:
            st.markdown(
                """
                <span class="rec-main-filter-apply-lock-marker" aria-hidden="true"></span>
                <style>
                div[data-testid="stColumn"]:has(.rec-main-filter-apply-lock-marker)
                div[data-testid="stButton"] > button {
                    pointer-events: none !important;
                    cursor: default !important;
                }
                div[data-testid="stColumn"]:has(.rec-main-filter-apply-lock-marker)
                div[data-testid="stButton"] > button:hover,
                div[data-testid="stColumn"]:has(.rec-main-filter-apply-lock-marker)
                div[data-testid="stButton"] > button:active {
                    transform: none !important;
                    filter: none !important;
                    box-shadow: none !important;
                }
                .rec-main-filter-apply-lock-marker { display: none !important; }
                </style>
                """,
                unsafe_allow_html=True,
            )
    with reset_col:
        reset_clicked_raw = st.button(
            "Reset Filter",
            type="secondary",
            key="recommendation_main_filter_reset",
            use_container_width=True,
        )
        if not reset_ready:
            st.markdown(
                """
                <span class="rec-main-filter-reset-lock-marker" aria-hidden="true"></span>
                <style>
                div[data-testid="stColumn"]:has(.rec-main-filter-reset-lock-marker)
                div[data-testid="stButton"] > button {
                    pointer-events: none !important;
                    cursor: default !important;
                }
                div[data-testid="stColumn"]:has(.rec-main-filter-reset-lock-marker)
                div[data-testid="stButton"] > button:hover,
                div[data-testid="stColumn"]:has(.rec-main-filter-reset-lock-marker)
                div[data-testid="stButton"] > button:active {
                    transform: none !important;
                    filter: none !important;
                    box-shadow: none !important;
                }
                .rec-main-filter-reset-lock-marker { display: none !important; }
                </style>
                """,
                unsafe_allow_html=True,
            )
    with spacer_col:
        st.empty()

    # Guard Python memastikan tidak ada aksi meskipun browser lama tidak
    # mendukung selector CSS :has(). Tampilan tombol tidak dibuat disabled.
    apply_clicked = bool(apply_clicked_raw and apply_ready)
    reset_clicked = bool(reset_clicked_raw and reset_ready)

    if reset_clicked:
        st.session_state[RECOMMENDATION_FILTER_RESET_PENDING_KEY] = True
        st.session_state[RECOMMENDATION_FILTER_FEEDBACK_KEY] = (
            "Filter berhasil direset ke nilai awal."
        )
        st.session_state[RECOMMENDATION_ACTION_LOADING_KEY] = (
            "Mengatur ulang filter halaman rekomendasi..."
        )
        st.rerun()

    if apply_clicked:
        submitted_service = str(
            st.session_state[RECOMMENDATION_FILTER_DRAFT_KEYS["layanan"]]
        )
        submitted_topic_options = _filter_topic_options(submitted_service)
        submitted_topic = str(
            st.session_state.get(RECOMMENDATION_FILTER_DRAFT_KEYS["topik"], "")
        )

        if submitted_topic not in submitted_topic_options:
            submitted_topic = submitted_topic_options[0]
            st.session_state[RECOMMENDATION_FILTER_DRAFT_KEYS["topik"]] = submitted_topic

        for field in ("layanan", "platform", "topik"):
            draft_value = st.session_state[RECOMMENDATION_FILTER_DRAFT_KEYS[field]]
            st.session_state[RECOMMENDATION_FILTER_ACTIVE_KEYS[field]] = draft_value

        st.session_state["recommendation_service_selector"] = st.session_state[
            RECOMMENDATION_FILTER_ACTIVE_KEYS["layanan"]
        ]
        st.session_state["active_service"] = st.session_state[
            RECOMMENDATION_FILTER_ACTIVE_KEYS["layanan"]
        ]
        st.session_state["recommendation_ai_platform_selector"] = st.session_state[
            RECOMMENDATION_FILTER_ACTIVE_KEYS["platform"]
        ]
        st.session_state["recommendation_ai_topic_selector"] = st.session_state[
            RECOMMENDATION_FILTER_ACTIVE_KEYS["topik"]
        ]
        st.session_state[RECOMMENDATION_FILTER_FEEDBACK_KEY] = (
            "Filter berhasil diterapkan."
        )
        st.session_state[RECOMMENDATION_ACTION_LOADING_KEY] = (
            "Menerapkan filter halaman rekomendasi..."
        )
        st.rerun()

    return (
        str(st.session_state[RECOMMENDATION_FILTER_ACTIVE_KEYS["layanan"]]),
        str(st.session_state[RECOMMENDATION_FILTER_ACTIVE_KEYS["platform"]]),
        str(st.session_state[RECOMMENDATION_FILTER_ACTIVE_KEYS["topik"]]),
    )


def _render_sentiment_strategy_cards() -> None:
    """Tampilkan strategi sentimen dalam card interaktif yang responsif."""
    # FASE12_STRATEGY_CARDS_INTERACTIVE_V1_8
    # HTML dirangkai tanpa indentasi awal agar Markdown Streamlit tidak
    # menganggap card kedua dan ketiga sebagai blok kode.
    cards = [
        {
            "label": "Positif",
            "title": "Perkuat bukti sosial",
            "icon": "✦",
            "state": "Amplifikasi kepercayaan",
            "description": (
                "Validasi pengalaman baik pelanggan, lalu ubah apresiasi menjadi "
                "bukti layanan yang kredibel dan mudah dibagikan."
            ),
            "focus": "Advokasi organik",
            "color": "#4CAF50",
            "rgb": "76,175,80",
            "points": [
                "Angkat testimoni dan pengalaman pelanggan yang dapat diverifikasi.",
                "Ubah apresiasi menjadi konten edukatif atau studi kasus singkat.",
                "Ajak komunitas membagikan pengalaman positif secara organik.",
            ],
        },
        {
            "label": "Netral",
            "title": "Perjelas informasi",
            "icon": "◎",
            "state": "Edukasi dan orientasi",
            "description": (
                "Kurangi ruang kebingungan melalui informasi yang ringkas, terukur, "
                "dan mudah dipahami pada setiap titik kontak pelanggan."
            ),
            "focus": "Kejelasan informasi",
            "color": "#FF9800",
            "rgb": "255,152,0",
            "points": [
                "Jawab pertanyaan umum melalui FAQ dan tutorial langkah demi langkah.",
                "Gunakan polling untuk memetakan kebutuhan informasi pelanggan.",
                "Jelaskan manfaat layanan tanpa klaim yang tidak terukur.",
            ],
        },
        {
            "label": "Negatif",
            "title": "Respons cepat dan empatik",
            "icon": "↯",
            "state": "Mitigasi dan pemulihan",
            "description": (
                "Redam eskalasi melalui pengakuan masalah, pembaruan transparan, "
                "dan arahan bantuan yang dapat segera ditindaklanjuti."
            ),
            "focus": "Pemulihan kepercayaan",
            "color": "#F44336",
            "rgb": "244,67,54",
            "points": [
                "Akui keluhan dan arahkan pelanggan ke kanal bantuan resmi.",
                "Berikan pembaruan transparan tanpa menjanjikan waktu yang belum pasti.",
                "Ubah pola keluhan berulang menjadi FAQ solusi dan konten pencegahan.",
            ],
        },
    ]

    card_html: list[str] = []
    for card in cards:
        points = "".join(f"<li>{escape(point)}</li>" for point in card["points"])
        card_html.append(
            f'<article class="rec-sentiment-strategy-card" tabindex="0" '
            f'aria-label="Strategi sentimen {escape(card["label"])}" '
            f'style="--sentiment-color:{card["color"]};'
            f'--sentiment-rgb:{card["rgb"]};">'
            f'<div class="rec-sentiment-strategy-inner">'
            f'<div class="rec-sentiment-strategy-head">'
            f'<div class="rec-sentiment-strategy-icon" aria-hidden="true">'
            f'{escape(card["icon"])}</div>'
            f'<div><div class="rec-sentiment-strategy-kicker">'
            f'Sentimen {escape(card["label"])}</div>'
            f'<div class="rec-sentiment-strategy-state">'
            f'{escape(card["state"])}</div></div></div>'
            f'<h3>{escape(card["title"])}</h3>'
            f'<p class="rec-sentiment-strategy-description">'
            f'{escape(card["description"])}</p>'
            f'<ul>{points}</ul>'
            f'<div class="rec-sentiment-strategy-footer">'
            f'<span>Fokus</span><strong>{escape(card["focus"])}</strong>'
            f'<span class="rec-sentiment-strategy-arrow" aria-hidden="true">↗</span>'
            f'</div></div></article>'
        )

    strategy_html = (
        '<div class="rec-sentiment-strategy-grid">'
        + "".join(card_html)
        + "</div>"
    )
    st.markdown(strategy_html, unsafe_allow_html=True)

# -----------------------------------------------------------------------------
# PEMULIHAN CACHE KOMPATIBILITAS
# -----------------------------------------------------------------------------


def _is_recommendation_cache_compatibility_error(error: Exception) -> bool:
    """Deteksi cache DataFrame lama yang tidak kompatibel dengan Pandas aktif."""
    message = str(error).casefold()
    return any(marker.casefold() in message for marker in RECOMMENDATION_CACHE_ERROR_MARKERS)


def _recover_recommendation_cache_once(error: Exception) -> bool:
    """Bersihkan cache Streamlit sekali lalu minta render ulang otomatis.

    Pemulihan dibatasi satu kali per sesi agar kesalahan data nyata tidak
    menghasilkan rerun tanpa akhir. Fungsi ini hanya menyentuh cache data
    Streamlit dan tidak mengubah atau menghapus virtual environment, dataset,
    model, database, maupun state filter pengguna.
    """
    if not _is_recommendation_cache_compatibility_error(error):
        return False
    if bool(st.session_state.get(RECOMMENDATION_CACHE_RECOVERY_KEY, False)):
        return False

    st.session_state[RECOMMENDATION_CACHE_RECOVERY_KEY] = True
    try:
        st.cache_data.clear()
    except Exception:
        # Rerun tetap dilakukan. Fungsi cache dengan schema/version key baru
        # masih dapat membangun ulang data tanpa membaca hasil lama.
        pass
    st.rerun()
    return True


# -----------------------------------------------------------------------------
# ENTRY POINT HALAMAN
# -----------------------------------------------------------------------------


def render_recommendation() -> None:
    """Render halaman Rekomendasi Konten & Influencer untuk tiga layanan."""
    action_loading_handle = None
    topic_ai_loading_handle = None
    page_loading_handle = None

    try:
        # Router memberi flag ini hanya ketika pengguna benar-benar berpindah ke
        # halaman Rekomendasi. Pada rerun tombol/filter di halaman yang sama flag
        # sudah tidak ada, sehingga loader halaman tidak muncul berulang kali.
        entering_recommendation = (
            st.session_state.get("_active_service_sync_target") == "Rekomendasi"
        )
        if entering_recommendation:
            page_loading_handle = _start_recommendation_page_loading()

        loading_label = st.session_state.pop(RECOMMENDATION_ACTION_LOADING_KEY, None)
        if loading_label:
            action_loading_handle = _start_recommendation_loading(str(loading_label))

        # Request Gemini diproses segera setelah overlay aktif dan sebelum komponen
        # halaman lain dirender. Ini mencegah halaman sempat terlihat lalu tertutup.
        _process_queued_topic_ai_request()

        # Semua aturan CSS dikirim sebagai satu delta Streamlit. Urutan aturan
        # tetap sama, jadi tampilan tidak berubah, tetapi browser tidak perlu
        # membuat beberapa blok markdown sebelum first paint halaman.
        recommendation_style_blocks = [
            RECOMMENDATION_HIDE_NATIVE_LOADING_CSS,
            RECOMMENDATION_CSS,
            PHASE12_AI_CSS,
            RECOMMENDATION_FILTER_FORM_CSS,
        ]

        # Light Mode adalah tema default dan override tetap berada paling akhir.
        if not bool(st.session_state.get("dark_mode", False)):
            recommendation_style_blocks.append(RECOMMENDATION_LIGHT_MODE_CSS)

        st.markdown(
            "\n".join(recommendation_style_blocks),
            unsafe_allow_html=True,
        )

        st.markdown('<div class="rec-page">', unsafe_allow_html=True)

        st.markdown(
            """
            <section class="rec-hero">
                <div class="rec-eyebrow">● Decision Support · Telkom Group</div>
                <h1 class="rec-title">Rekomendasi Konten & Influencer</h1>
                <p class="rec-subtitle">
                    Hubungkan isu dominan, sentimen publik, jangkauan akun, dan posisi
                    jaringan untuk menyusun strategi komunikasi yang lebih terarah pada
                    Twitter/X, Instagram, dan TikTok.
                </p>
            </section>
            """,
            unsafe_allow_html=True,
        )

        layanan, platform, topik = _render_recommendation_filter_form()
        demo_mode = bool(st.session_state.get("demo_mode", False))

        # Data berat dan seluruh kartu hanya memakai nilai aktif hasil tombol Terapkan Filter.
        topic_summary, topic_meta = _build_topic_summary(layanan, demo_mode)

        filter_feedback = str(
            st.session_state.pop(RECOMMENDATION_FILTER_FEEDBACK_KEY, "")
        ).strip()
        if not filter_feedback:
            filter_feedback = "Filter aktif sedang digunakan pada seluruh analisis halaman."

        st.markdown(
            f"""
            <div class="rec-filter-active-note">
                Filter aktif: <strong>{escape(layanan)}</strong> ·
                <strong>{escape(platform)}</strong> ·
                <strong>{escape(topik)}</strong>.
                <span>{escape(filter_feedback)}</span>
            </div>
            """,
            unsafe_allow_html=True,
        )

        _render_ai_generator(layanan, platform, topik, topic_summary)

        # Jangan tutup loader di tengah render. Halaman Rekomendasi mempunyai
        # banyak section berat di bawah Generator Ide Konten. Loader baru ditutup
        # pada blok finally setelah seluruh section selesai dibentuk agar pengguna
        # tidak melihat halaman setengah jadi atau terasa seperti loading dihentikan
        # paksa.

        _render_section_header(
            "Sentiment Response Framework",
            "Strategi Per Sentimen",
            "Gunakan tiga pola respons berikut sebagai pagar strategis sebelum konten dipublikasikan.",
        )
        _render_sentiment_strategy_cards()

        influencers, influencer_meta = _build_influencer_data(layanan, demo_mode)
        influencers = _add_account_type_column(influencers)
        influencer_meta = dict(influencer_meta or {})
        influencer_meta["actual_rows"] = int(len(influencers))
        influencer_meta["active_platform"] = platform

        _render_context_card(layanan, topic_meta, influencer_meta)

        _render_section_header(
            "01 · Recommended Influencers",
            "Influencer yang Direkomendasikan",
            (
                "Akun dipilih dari kombinasi posisi jaringan, jangkauan followers, dan "
                "konten asli yang relevan pada dataset layanan terpilih."
            ),
        )
        selected_account_type = st.radio(
            "Tampilkan:",
            options=["Semua", "Influencer", "Akun Media"],
            horizontal=True,
            key=ACCOUNT_TYPE_FILTER_KEY,
            on_change=_show_account_type_filter_loading,
        )
        influencers = _filter_influencers_by_account_type(
            influencers,
            selected_account_type,
        )
        if selected_account_type in {"Influencer", "Akun Media"}:
            influencers = _select_balanced_platform_candidates(
                influencers,
                per_platform_limit=PLATFORM_CARD_TARGET,
            )
            influencer_meta["active_platform"] = (
                "Lintas platform · 3 Twitter/X · 3 Instagram · 3 TikTok"
            )
        else:
            influencers = _filter_influencers_by_active_platform(
                influencers,
                platform,
            )
        influencer_meta["actual_rows"] = int(len(influencers))
        influencer_meta["active_account_type"] = selected_account_type
        score_matrix = _build_score_matrix(influencers, layanan)
        _render_influencer_grid(layanan, influencers, topic_summary, influencer_meta)

        if layanan == "IndiBiz":
            _render_section_header(
                "02 · Sentiment Content Playbook",
                "Rekomendasi Konten untuk UMKM & Korporasi",
                (
                    "Tiga ide konten untuk setiap sentimen disusun dari topik dominan "
                    "dan kata kunci IndiBiz dengan bahasa profesional berorientasi bisnis."
                ),
            )
            _render_indibiz_sentiment_content()
            topic_section_number = "03"
            matrix_section_number = "04"
            summary_section_number = "05"
        else:
            topic_section_number = "02"
            matrix_section_number = "03"
            summary_section_number = "04"

        strategy_topic_summary = _build_recommendation_topic_records(
            layanan, demo_mode
        )
        _render_section_header(
            f"{topic_section_number} · Topic Playbook",
            "Strategi per Topik",
            (
                "Topik mengikuti urutan Top 5 pada Analisis Topik untuk layanan aktif. "
                "Kategori Lainnya tidak ditampilkan."
            ),
        )
        topic_ai_loading_handle = _render_topic_strategies(
            layanan,
            strategy_topic_summary,
            score_matrix,
        )

        _render_section_header(
            f"{matrix_section_number} · Compatibility Matrix",
            "Matriks Influencer × Topik",
            (
                "Gunakan kontrol interaktif untuk memilih fokus topik, menyaring platform, "
                "dan menampilkan influencer dengan skor kecocokan paling kuat."
            ),
        )
        _render_interactive_matrix(score_matrix, layanan)

        _render_section_header(
            f"{summary_section_number} · Action Summary",
            "Ringkasan Strategis",
            (
                "Tiga tindakan prioritas yang dapat digunakan sebagai dasar penyusunan "
                "kalender konten dan pola respons layanan."
            ),
        )
        _render_strategic_summary(
            _strategic_points(layanan, topic_summary, influencers)
        )

        st.caption(
            f"Sumber topik: {topic_meta.get('source_name', 'Tidak tersedia')} · "
            f"Sumber influencer: {influencer_meta.get('source_name', 'Tidak tersedia')} · "
            "Rekomendasi AI dan fallback tetap memerlukan validasi manusia sebelum dipublikasikan."
        )
        st.markdown("</div>", unsafe_allow_html=True)
        st.session_state.pop(RECOMMENDATION_CACHE_RECOVERY_KEY, None)
    except Exception as exc:
        if not _recover_recommendation_cache_once(exc):
            st.session_state.pop(RECOMMENDATION_CACHE_RECOVERY_KEY, None)
            st.error(
                "Halaman rekomendasi tidak dapat ditampilkan. "
                f"Detail kesalahan: {exc}"
            )
            st.info(
                "Periksa keberadaan file data pada folder data/, kemudian muat ulang halaman."
            )
    finally:
        # Loader halaman ditutup hanya di titik akhir render. Jika terjadi error,
        # blok finally tetap memastikan overlay tidak mengunci layar.
        _finish_recommendation_page_loading(page_loading_handle)

        # Loading Gemini ditutup paling akhir setelah seluruh halaman selesai dirender.
        # Ini mencegah overlay menghilang di tengah render lalu muncul kembali (flicker).
        _finish_recommendation_loading(topic_ai_loading_handle)
        _finish_recommendation_loading(action_loading_handle)

