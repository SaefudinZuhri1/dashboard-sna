# pages/sna.py
# TAHAP 5 FASE 7 - OPTIMASI PERFORMA: lazy PyVis, cache preprocessing, dan progress indikator.
"""Halaman Social Network Analysis (SNA) dan identifikasi influencer."""

from __future__ import annotations

from html import escape
from typing import Any
from textwrap import dedent
import base64
import hashlib
import inspect
import os
import tempfile


import networkx as nx
import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
from utils.streamlit_compat import render_html_iframe

try:
    from utils.loading_screen import mulai_loading_aksi, selesaikan_loading_aksi
except Exception:  # pragma: no cover - fallback jika utilitas loading belum tersedia
    mulai_loading_aksi = None
    selesaikan_loading_aksi = None

from utils.audit_logger import log_activity
from utils.data_loader import (
    get_sna_source_names,
    load_indibiz_sna,
    load_indihome_sna,
    load_sentiment_data,
    load_sna_data,
    sentiment_file_exists,
    load_telkomsel_sna,
    sna_file_exists,
)
from utils.export_utils import export_to_csv, get_export_filename
from utils.dummy_data import get_demo_sna
from utils.indibiz_config import TARGET_NODE
from utils.indibiz_config import OUTPUT_FILES

# -----------------------------------------------------------------------------
# Konstanta halaman
# -----------------------------------------------------------------------------

SERVICE_OPTIONS = ["IndiHome", "IndiBiz", "Telkomsel"]
SERVICE_ALIASES = {
    "IndiHome": {"indihome", "indihomecare", "myindihome"},
    "IndiBiz": {"indibiz", "indibizid", "indibizcare"},
    "Telkomsel": {"telkomsel", "telkomselcare", "mytelkomsel"},
}

PLATFORM_OPTIONS = {
    "Semua Platform": "all",
    "Twitter/X": "twitter",
    "Instagram": "instagram",
    "TikTok": "tiktok",
}
PLATFORM_ORDER = ["twitter", "instagram", "tiktok"]
PLATFORM_GRAPH_COLORS = {
    "twitter": "#1DA1F2",
    "instagram": "#833AB4",
    "tiktok": "#25F4EE",
    "target": "#E53935",
    "unknown": "#64748B",
}
PLATFORM_DISPLAY = {
    "twitter": "Twitter/X",
    "instagram": "Instagram",
    "tiktok": "TikTok",
    "target": "Akun Brand",
    "unknown": "Tidak diketahui",
}

SENTIMENT_COLORS = {
    "positive": "#4CAF50",
    "neutral": "#B8C0CC",
    "negative": "#E53935",
}
SENTIMENT_DISPLAY = {
    "positive": "Positif",
    "neutral": "Netral",
    "negative": "Negatif",
    "unknown": "Belum tersedia",
}
SENTIMENT_PRIORITY = {"negative": 3, "positive": 2, "neutral": 1, "unknown": 0}

BRAND_ALIASES = set().union(*SERVICE_ALIASES.values()) | {
    "telkomindonesia",
    "telkom",
    "telkomgroup",
}

# Prefix dipakai untuk mengenali akun regional/resmi seperti indibiz_borneo,
# indibizkti, indibiz_jtdiy, indihomecare_jabar, dan variasi resmi sejenis.
BRAND_PREFIXES = ("indihome", "indibiz", "telkomsel")

# Pada visualisasi graf IndiHome, hanya akun layanan utama berikut yang boleh
# dipertahankan sebagai node brand/hub berwarna merah. Akun care, regional,
# dan turunan layanan tetap ada pada data/metrik SNA, tetapi tidak ditampilkan
# di Eksplorasi Graf SNA agar tidak terbaca sebagai aktor utama.
PRIMARY_SERVICE_GRAPH_ACCOUNTS = {"indihome", "indibiz", "telkomsel"}

# Filter ini hanya digunakan untuk tampilan ranking influencer. Node tetap
# dipertahankan di graph agar struktur hub-and-spoke tidak berubah.
EXCLUDE_ACCOUNTS = [
    "indihome",
    "telkomsel",
    "indibiz",
    "telkom",
    "tsel",
    "telkomsel_id",
    "indihome_id",
    "indibiz_id",
    "IndiHome",
    "Telkomsel",
    "IndiBiz",
]
EXCLUDE_ACCOUNTS_NORMALIZED = {
    str(account).strip().lstrip("@").lower() for account in EXCLUDE_ACCOUNTS
}
EXCLUDE_ACCOUNTS_COMPACT = {
    "".join(char for char in account if char.isalnum())
    for account in EXCLUDE_ACCOUNTS_NORMALIZED
}

# Prefix ini khusus untuk menyaring ranking/tabel influencer. Berbeda dengan
# BRAND_PREFIXES, daftar ini tidak mengubah klasifikasi atau tampilan node graph.
# Tujuannya agar akun layanan, akun care, akun regional, dan akun turunannya
# tidak dianggap sebagai influencer hanya karena memiliki koneksi tinggi.
EXCLUDE_SERVICE_PREFIXES = (
    "indihome",
    "indibiz",
    "telkomsel",
    "telkom",
    "tsel",
    "myindihome",
    "mytelkomsel",
)

REQUIRED_SNA_COLUMNS = {"source", "target", "relationship", "followers", "platform"}
SNA_ACTION_LOADING_KEY = "_sna_v9_action_loading_label"
SNA_GRAPH_RENDER_REQUEST_KEY = "_sna_v9_graph_render_request"
SNA_FILTER_APPLIED_SERVICE_KEY = "_sna_v9_applied_service_filter"
SNA_FILTER_APPLIED_PLATFORM_KEY = "_sna_v9_applied_platform_filter"
SNA_FILTER_APPLIED_NODE_LIMIT_KEY = "_sna_v9_applied_node_limit"
SNA_FILTER_EVENT_CHANGED_KEY = "_sna_v9_filter_event_changed"
SNA_FILTER_EVENT_KIND_KEY = "_sna_v9_filter_event_kind"
SNA_FILTER_DEFAULT_PLATFORM = "Semua Platform"
SNA_FILTER_DEFAULT_NODE_LIMIT = 60

SNA_INFLUENCER_APPLIED_SEARCH_KEY = "_sna_v13_influencer_applied_search"
SNA_INFLUENCER_APPLIED_PLATFORM_KEY = "_sna_v13_influencer_applied_platform"
SNA_INFLUENCER_APPLIED_ROWS_KEY = "_sna_v13_influencer_applied_rows"
SNA_INFLUENCER_APPLIED_MODE_KEY = "_sna_v13_influencer_applied_mode"
SNA_INFLUENCER_EVENT_KIND_KEY = "_sna_v13_influencer_filter_event_kind"
SNA_INFLUENCER_EVENT_CHANGED_KEY = "_sna_v13_influencer_filter_event_changed"
SNA_INFLUENCER_DEFAULT_SEARCH = ""
SNA_INFLUENCER_DEFAULT_PLATFORM = "Semua Platform"
SNA_INFLUENCER_DEFAULT_ROWS = 10
SNA_INFLUENCER_DEFAULT_MODE = "Dua Ranking"

# Ikuti pola halaman Dataset: chart layar penuh memakai dialog Streamlit,
# bukan data-URI/tab baru dan bukan iframe fullscreen custom.
_DIALOG_DECORATOR = getattr(st, "dialog", None)
if _DIALOG_DECORATOR is None:
    _DIALOG_DECORATOR = st.experimental_dialog

_FRAGMENT_DECORATOR = getattr(st, "fragment", None)
if _FRAGMENT_DECORATOR is None:  # pragma: no cover - fallback Streamlit lama
    def _FRAGMENT_DECORATOR(function):
        return function


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


# -----------------------------------------------------------------------------
# CSS halaman SNA — mengikuti pola visual Beranda, Dataset, Sentimen, Topik
# -----------------------------------------------------------------------------

def _inject_sna_css() -> None:
    """Sisipkan CSS khusus halaman SNA tanpa mengubah tema global."""
    try:
        st.markdown(
            """
            <style>
                @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&family=Plus+Jakarta+Sans:wght@500;600;700;800&display=swap');

                div[data-testid="stAppViewContainer"] { background: #0D0D0D; }
                div[data-testid="stAppViewContainer"] .main .block-container {
                    color: #FFFFFF;
                    padding-top: 1.25rem;
                    padding-bottom: 2.5rem;
                }

                .sna-v9-page,
                .sna-v9-page * {
                    box-sizing: border-box;
                    font-family: 'Inter', sans-serif;
                }

                /*
                Streamlit membuat elemen lama menjadi stale saat tombol form diklik.
                Opacity bawaan dimatikan supaya layar tidak meredup dan yang terlihat
                hanya overlay loading custom dari utils/loading_screen.py.
                */
                [data-stale="true"],
                [data-stale="true"] * {
                    filter: none !important;
                    opacity: 1 !important;
                }

                .sna-v9-hero {
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

                .sna-v9-hero::after {
                    background: radial-gradient(circle, rgba(255,255,255,0.16), transparent 68%);
                    content: '';
                    height: 250px;
                    pointer-events: none;
                    position: absolute;
                    right: -80px;
                    top: -120px;
                    width: 250px;
                }

                .sna-v9-hero h1 {
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

                .sna-v9-hero p {
                    color: rgba(255,255,255,0.92) !important;
                    font-size: 0.96rem;
                    line-height: 1.55;
                    margin: 0.65rem 0 0.95rem;
                    max-width: 920px;
                    position: relative;
                    z-index: 1;
                }

                .sna-v9-badges {
                    display: flex;
                    flex-wrap: wrap;
                    gap: 0.45rem;
                    position: relative;
                    z-index: 1;
                }

                .sna-v9-badge {
                    backdrop-filter: blur(8px);
                    border: 1px solid rgba(255,255,255,0.22);
                    border-radius: 999px;
                    color: #FFFFFF;
                    display: inline-flex;
                    font-size: 0.75rem /* FIX: minimum 12px agar terbaca di tablet */;
                    font-weight: 750;
                    padding: 0.42rem 0.68rem;
                }
                .sna-v9-badge-real { background: rgba(27,94,32,0.52); }
                .sna-v9-badge-dummy { background: rgba(120,53,15,0.55); }
                .sna-v9-badge-glass { background: rgba(100,20,20,0.30); }

                .sna-v9-card,
                div[data-testid="stVerticalBlockBorderWrapper"]:has(.sna-v9-card-marker) {
                    background: #1A1A1A !important;
                    border: 1px solid #2A2A2A !important;
                    border-radius: 12px !important;
                    box-shadow: 0 10px 28px rgba(0,0,0,0.18);
                }

                .sna-v9-card-marker,
                .sna-v9-control-marker,
                .sna-v9-section-marker,
                .sna-v9-graph-marker { display: none; }

                div[data-testid="stMarkdownContainer"]:has(.sna-v9-card-marker),
                div[data-testid="stMarkdownContainer"]:has(.sna-v9-control-marker),
                div[data-testid="stMarkdownContainer"]:has(.sna-v9-section-marker),
                div[data-testid="stMarkdownContainer"]:has(.sna-v9-graph-marker) { display: none; }

                div[data-testid="stVerticalBlockBorderWrapper"]:has(.sna-v9-control-marker),
                div[data-testid="stVerticalBlockBorderWrapper"]:has(.sna-v9-section-marker),
                div[data-testid="stVerticalBlockBorderWrapper"]:has(.sna-v9-graph-marker) {
                    background: #1A1A1A !important;
                    border: 1px solid #2A2A2A !important;
                    border-radius: 12px !important;
                    box-shadow: 0 10px 28px rgba(0,0,0,0.18);
                    padding: 1rem !important;
                }

                div[data-testid="stVerticalBlockBorderWrapper"]:has(.sna-v9-control-marker) { margin-bottom: 1rem; }

                /* Patch Fase 13: tombol aksi filter harus sejajar, teks Apply satu baris,
                   dan Apply tetap inert saat filter aktif belum berubah. */
                div[data-testid="stVerticalBlockBorderWrapper"]:has(.sna-v9-control-marker)
                div[data-testid="stButton"] > button {
                    min-height: 3.75rem !important;
                }

                div[data-testid="stVerticalBlockBorderWrapper"]:has(.sna-v9-control-marker)
                div[data-testid="stButton"] > button[kind="primary"],
                div[data-testid="stVerticalBlockBorderWrapper"]:has(.sna-v9-control-marker)
                div[data-testid="stButton"] > button[kind="primary"] p {
                    white-space: nowrap !important;
                }

                div[data-testid="stVerticalBlockBorderWrapper"]:has(.sna-v9-control-marker)
                div[data-testid="stButton"] > button[kind="primary"] {
                    min-width: 100% !important;
                }

                div[data-testid="stVerticalBlockBorderWrapper"]:has(.sna-v9-section-marker),
                div[data-testid="stVerticalBlockBorderWrapper"]:has(.sna-v9-graph-marker) { margin: 1.2rem 0 0.75rem; }

                .sna-v9-section-head {
                    align-items: flex-start;
                    display: flex;
                    gap: 0.75rem;
                    justify-content: space-between;
                    margin-bottom: 0.75rem;
                }

                .sna-v9-section-title {
                    color: #FFFFFF !important;
                    font-family: 'Plus Jakarta Sans', 'Inter', sans-serif;
                    font-size: 1.05rem;
                    font-weight: 780;
                    margin: 0;
                }

                .sna-v9-section-subtitle {
                    color: #AAAAAA !important;
                    font-size: 0.78rem;
                    line-height: 1.45;
                    margin: 0.2rem 0 0;
                }

                .sna-v9-stat-row {
                    display: grid;
                    gap: 0.75rem;
                    grid-template-columns: repeat(3, minmax(0, 1fr));
                    margin: 0 0 1rem;
                }

                .sna-v9-stat {
                    background: #1A1A1A;
                    border: 1px solid #2A2A2A;
                    border-left: 3px solid #E53935;
                    border-radius: 12px;
                    min-height: 104px;
                    overflow: hidden;
                    padding: 0.9rem 1rem;
                    position: relative;
                    transition: border-color .18s ease, box-shadow .18s ease, transform .18s ease;
                }

                .sna-v9-stat:hover,
                .sna-v9-card:hover,
                div[data-testid="stVerticalBlockBorderWrapper"]:has(.sna-v9-section-marker):hover,
                div[data-testid="stVerticalBlockBorderWrapper"]:has(.sna-v9-graph-marker):hover {
                    border-color: #E53935 !important;
                    box-shadow: 0 0 0 1px rgba(229,57,53,.12), 0 12px 34px rgba(0,0,0,.28);
                    transform: translateY(-1px);
                }

                .sna-v9-stat-label {
                    color: #AAAAAA;
                    font-size: 0.75rem /* FIX: minimum 12px agar terbaca di tablet */;
                    font-weight: 700;
                    letter-spacing: 0.01em;
                }

                .sna-v9-stat-value {
                    color: #E53935;
                    font-family: 'Plus Jakarta Sans', 'Inter', sans-serif;
                    font-size: clamp(1.15rem, 2vw, 1.72rem);
                    font-weight: 800;
                    line-height: 1.15;
                    margin-top: 0.27rem;
                    overflow-wrap: anywhere;
                }

                .sna-v9-stat.sna-v9-stat-influencer .sna-v9-stat-value {
                    font-size: clamp(1.05rem, 1.35vw, 1.35rem);
                    letter-spacing: 0.02em;
                    max-width: 100%;
                    overflow: hidden;
                    overflow-wrap: normal;
                    text-overflow: ellipsis;
                    white-space: nowrap;
                    word-break: keep-all;
                }

                .sna-v9-stat.sna-v9-stat-influencer .sna-v9-stat-note {
                    margin-top: 0.45rem;
                }

                .sna-v9-stat-note {
                    color: #777777;
                    font-size: 0.75rem /* FIX: minimum 12px agar terbaca di tablet */;
                    line-height: 1.35;
                    margin-top: 0.35rem;
                }

                .sna-v9-platform-legend {
                    display: flex;
                    flex-wrap: wrap;
                    gap: 0.55rem;
                    margin-top: 0.65rem;
                }

                .sna-v9-legend-item {
                    align-items: center;
                    background: #111111;
                    border: 1px solid #292929;
                    border-radius: 999px;
                    color: #D4D4D4;
                    display: inline-flex;
                    font-size: 0.75rem /* FIX: minimum 12px agar terbaca di tablet */;
                    font-weight: 650;
                    gap: 0.45rem;
                    padding: 0.36rem 0.62rem;
                }

                .sna-v9-dot {
                    border-radius: 50%;
                    display: inline-block;
                    height: 10px;
                    width: 10px;
                }

                .sna-v9-method-card {
                    background:
                        radial-gradient(circle at 7% 0%, rgba(229,57,53,0.22), transparent 34%),
                        radial-gradient(circle at 95% 18%, rgba(29,161,242,0.14), transparent 30%),
                        linear-gradient(135deg, rgba(17,24,39,0.96), rgba(10,10,10,0.98));
                    border: 1px solid rgba(29,161,242,.36);
                    border-radius: 18px;
                    box-shadow: 0 18px 42px rgba(0,0,0,0.24), inset 0 1px 0 rgba(255,255,255,0.04);
                    color: #D9E6F2;
                    line-height: 1.65;
                    margin-top: 1.3rem;
                    overflow: hidden;
                    padding: 1.35rem 1.45rem 1.25rem;
                    position: relative;
                }

                .sna-v9-method-card::before {
                    background: linear-gradient(180deg, #E53935, rgba(29,161,242,0.72));
                    border-radius: 999px;
                    bottom: 1.2rem;
                    content: '';
                    left: 0;
                    position: absolute;
                    top: 1.2rem;
                    width: 4px;
                }

                .sna-v9-method-card::after {
                    background: radial-gradient(circle, rgba(229,57,53,0.20), transparent 66%);
                    content: '';
                    height: 180px;
                    pointer-events: none;
                    position: absolute;
                    right: -70px;
                    top: -80px;
                    width: 180px;
                }

                .sna-v9-method-head {
                    align-items: flex-start;
                    display: flex;
                    gap: 0.9rem;
                    margin-bottom: 1rem;
                    position: relative;
                    z-index: 1;
                }

                .sna-v9-method-icon {
                    align-items: center;
                    background: linear-gradient(135deg, #E53935, #B71C1C);
                    border: 1px solid rgba(255,255,255,0.15);
                    border-radius: 16px;
                    box-shadow: 0 12px 26px rgba(229,57,53,0.22);
                    color: #FFFFFF;
                    display: inline-flex;
                    flex: 0 0 48px;
                    font-size: 1.15rem;
                    font-weight: 850;
                    height: 48px;
                    justify-content: center;
                    letter-spacing: -0.04em;
                    width: 48px;
                }

                .sna-v9-method-kicker {
                    color: #8FBDE8;
                    font-size: 0.75rem /* FIX: minimum 12px agar terbaca di tablet */;
                    font-weight: 850;
                    letter-spacing: 0.11em;
                    margin-bottom: 0.25rem;
                    text-transform: uppercase;
                }

                .sna-v9-method-card h3 {
                    color: #FFFFFF;
                    font-family: 'Plus Jakarta Sans', 'Inter', sans-serif;
                    font-size: clamp(1.12rem, 2vw, 1.42rem);
                    font-weight: 850;
                    letter-spacing: -0.035em;
                    line-height: 1.22;
                    margin: 0;
                }

                .sna-v9-method-lead {
                    border-left: 1px solid rgba(255,255,255,0.10);
                    color: #C9D6E2;
                    font-size: 0.92rem;
                    margin: 0.2rem 0 1rem;
                    padding-left: 0.9rem;
                    position: relative;
                    z-index: 1;
                }

                .sna-v9-method-grid {
                    display: grid;
                    gap: 0.75rem;
                    grid-template-columns: repeat(3, minmax(0, 1fr));
                    margin-top: 0.85rem;
                    position: relative;
                    z-index: 1;
                }

                .sna-v9-method-mini {
                    background: rgba(13,13,13,0.62);
                    border: 1px solid rgba(255,255,255,0.08);
                    border-radius: 14px;
                    min-height: 132px;
                    padding: 0.9rem;
                    transition: transform 0.18s ease, border-color 0.18s ease, box-shadow 0.18s ease;
                }

                .sna-v9-method-mini:hover {
                    border-color: rgba(229,57,53,0.62);
                    box-shadow: 0 14px 30px rgba(229,57,53,0.10);
                    transform: translateY(-2px);
                }

                .sna-v9-method-mini strong {
                    color: #FFFFFF;
                    display: block;
                    font-size: 0.88rem;
                    margin: 0.4rem 0 0.35rem;
                }

                .sna-v9-method-mini p {
                    color: #AEB8C6;
                    font-size: 0.79rem;
                    line-height: 1.55;
                    margin: 0;
                }

                .sna-v9-method-chip {
                    align-items: center;
                    background: rgba(229,57,53,0.14);
                    border: 1px solid rgba(229,57,53,0.35);
                    border-radius: 999px;
                    color: #FFB4B2;
                    display: inline-flex;
                    font-size: 0.75rem /* FIX: minimum 12px agar terbaca di tablet */;
                    font-weight: 850;
                    padding: 0.24rem 0.5rem;
                }

                .sna-v9-method-note {
                    background: linear-gradient(135deg, rgba(29,161,242,0.10), rgba(229,57,53,0.08));
                    border: 1px solid rgba(255,255,255,0.08);
                    border-radius: 14px;
                    color: #C9D6E2;
                    font-size: 0.84rem;
                    margin-top: 0.9rem;
                    padding: 0.85rem 0.95rem;
                    position: relative;
                    z-index: 1;
                }

                .sna-v9-method-note strong { color: #FFFFFF; }

                @media (max-width: 900px) {
                    .sna-v9-method-grid { grid-template-columns: 1fr; }
                    .sna-v9-method-head { align-items: center; }
                }

                .sna-v9-empty {
                    background: #151515;
                    border: 1px dashed #3A3A3A;
                    border-radius: 12px;
                    color: #AAAAAA;
                    padding: 1rem;
                }

                div[data-testid="stSelectbox"] label,
                div[data-testid="stSlider"] label,
                div[data-testid="stNumberInput"] label {
                    color: #AAAAAA !important;
                    font-size: 0.78rem !important;
                    font-weight: 650 !important;
                }

                div[data-testid="stSelectbox"] div[data-baseweb="select"] > div,
                div[data-testid="stNumberInput"] input {
                    background: #242424 !important;
                    border: 1px solid #343434 !important;
                    border-radius: 10px !important;
                    color: #FFFFFF !important;
                    min-height: 42px;
                    transition: border-color 0.18s ease, box-shadow 0.18s ease, background-color 0.18s ease;
                }

                div[data-testid="stSelectbox"] div[data-baseweb="select"] > div:hover,
                div[data-testid="stNumberInput"] input:hover {
                    background: #282828 !important;
                    border-color: #4A4A4A !important;
                }

                div[data-testid="stSelectbox"] div[data-baseweb="select"] > div:focus-within,
                div[data-testid="stNumberInput"] input:focus {
                    border-color: #E53935 !important;
                    box-shadow: 0 0 0 3px rgba(229,57,53,0.14) !important;
                    outline: none !important;
                }

                div[data-testid="stSelectbox"] svg { fill: #AAAAAA !important; }
                div[data-testid="stSelectbox"]:hover svg { fill: #FFFFFF !important; }

                [data-testid="stSelectboxVirtualDropdown"],
                [data-testid="stSelectboxVirtualDropdown"] > *,
                [data-testid="stSelectboxVirtualDropdown"] > * > *,
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
                [data-testid="stSelectboxVirtualDropdown"] {
                    border: 1px solid #3A3A3A !important;
                    border-radius: 12px !important;
                    box-shadow: 0 18px 48px rgba(0,0,0,.58) !important;
                    overflow: hidden !important;
                }

                [data-baseweb="popover"] [role="listbox"],
                [data-testid="stSelectboxVirtualDropdown"] [role="listbox"],
                ul[role="listbox"],
                div[role="listbox"] {
                    background-color: #1F1F1F !important;
                    border-radius: 11px !important;
                    color: #FFFFFF !important;
                    max-height: 280px !important;
                    overflow-y: auto !important;
                    padding: 0.38rem !important;
                    scrollbar-color: #5A5A5A #1F1F1F;
                    scrollbar-width: thin;
                }

                [data-baseweb="popover"] [role="option"],
                [data-testid="stSelectboxVirtualDropdown"] [role="option"],
                li[role="option"],
                div[role="option"] {
                    background: transparent !important;
                    border-radius: 8px !important;
                    color: #FFFFFF !important;
                    font-size: 0.86rem !important;
                    margin: 0.12rem 0 !important;
                }

                [data-baseweb="popover"] [role="option"]:hover,
                [data-testid="stSelectboxVirtualDropdown"] [role="option"]:hover,
                li[role="option"]:hover,
                div[role="option"]:hover {
                    background: rgba(229,57,53,0.20) !important;
                    color: #FFFFFF !important;
                }

                /* Penyempurnaan dropdown Filter Analisis SNA.
                   Selector dibatasi pada card filter agar komponen halaman lain tidak berubah. */
                div[data-testid="stVerticalBlockBorderWrapper"]:has(.sna-v9-control-marker)
                div[data-testid="stSelectbox"] {
                    margin: 0 !important;
                }

                div[data-testid="stVerticalBlockBorderWrapper"]:has(.sna-v9-control-marker)
                div[data-testid="stSelectbox"] label {
                    color: #F4F6FA !important;
                    display: block !important;
                    font-size: 0.84rem !important;
                    font-weight: 760 !important;
                    line-height: 1.25 !important;
                    margin: 0 0 0.58rem !important;
                    padding: 0 0.08rem !important;
                }

                div[data-testid="stVerticalBlockBorderWrapper"]:has(.sna-v9-control-marker)
                div[data-testid="stSelectbox"] div[data-baseweb="select"] {
                    width: 100% !important;
                }

                div[data-testid="stVerticalBlockBorderWrapper"]:has(.sna-v9-control-marker)
                div[data-testid="stSelectbox"] div[data-baseweb="select"] > div {
                    align-items: center !important;
                    background:
                        linear-gradient(180deg, rgba(23,23,25,0.98), rgba(13,13,14,0.98)) !important;
                    border: 1px solid rgba(255,255,255,0.13) !important;
                    border-radius: 14px !important;
                    box-shadow:
                        inset 0 1px 0 rgba(255,255,255,0.045),
                        0 9px 22px rgba(0,0,0,0.18) !important;
                    box-sizing: border-box !important;
                    color: #FFFFFF !important;
                    display: flex !important;
                    height: 56px !important;
                    min-height: 56px !important;
                    overflow: hidden !important;
                    padding: 0 0.55rem 0 1rem !important;
                    transition:
                        background 180ms ease,
                        border-color 180ms ease,
                        box-shadow 180ms ease,
                        transform 180ms ease !important;
                    width: 100% !important;
                }

                div[data-testid="stVerticalBlockBorderWrapper"]:has(.sna-v9-control-marker)
                div[data-testid="stSelectbox"] div[data-baseweb="select"] > div:hover {
                    background:
                        linear-gradient(180deg, rgba(32,32,35,0.99), rgba(18,18,20,0.99)) !important;
                    border-color: rgba(229,57,53,0.64) !important;
                    box-shadow:
                        inset 0 1px 0 rgba(255,255,255,0.06),
                        0 0 0 3px rgba(229,57,53,0.08),
                        0 12px 26px rgba(0,0,0,0.22) !important;
                    transform: translateY(-1px);
                }

                div[data-testid="stVerticalBlockBorderWrapper"]:has(.sna-v9-control-marker)
                div[data-testid="stSelectbox"] div[data-baseweb="select"] > div:focus-within {
                    background:
                        linear-gradient(180deg, rgba(35,26,28,0.99), rgba(18,15,16,0.99)) !important;
                    border-color: #F04444 !important;
                    box-shadow:
                        inset 0 1px 0 rgba(255,255,255,0.06),
                        0 0 0 4px rgba(229,57,53,0.13),
                        0 14px 30px rgba(0,0,0,0.25) !important;
                    outline: none !important;
                    transform: none;
                }

                div[data-testid="stVerticalBlockBorderWrapper"]:has(.sna-v9-control-marker)
                div[data-testid="stSelectbox"] div[data-baseweb="select"] > div > div {
                    align-items: center !important;
                    color: #FFFFFF !important;
                    display: flex !important;
                    font-size: 0.96rem !important;
                    font-weight: 690 !important;
                    line-height: 1.2 !important;
                    min-height: 54px !important;
                }

                div[data-testid="stVerticalBlockBorderWrapper"]:has(.sna-v9-control-marker)
                div[data-testid="stSelectbox"] svg {
                    fill: #B8C0CC !important;
                    height: 20px !important;
                    transition: fill 180ms ease, transform 180ms ease !important;
                    width: 20px !important;
                }

                div[data-testid="stVerticalBlockBorderWrapper"]:has(.sna-v9-control-marker)
                div[data-testid="stSelectbox"]:hover svg {
                    fill: #FFFFFF !important;
                    transform: translateY(1px);
                }

                /* Dropdown dipasang oleh BaseWeb di portal luar card, sehingga selector
                   berikut sengaja global namun hanya memengaruhi menu select yang sedang terbuka. */
                [data-baseweb="popover"] {
                    background: transparent !important;
                    border: 0 !important;
                    border-radius: 16px !important;
                    box-shadow: 0 22px 56px rgba(0,0,0,0.62) !important;
                    margin-top: 0.48rem !important;
                    overflow: hidden !important;
                }

                [data-baseweb="popover"] [role="listbox"],
                [data-testid="stSelectboxVirtualDropdown"] [role="listbox"],
                ul[role="listbox"],
                div[role="listbox"] {
                    background:
                        linear-gradient(180deg, rgba(31,31,34,0.99), rgba(20,20,22,0.99)) !important;
                    border: 1px solid rgba(255,255,255,0.13) !important;
                    border-radius: 15px !important;
                    box-shadow:
                        inset 0 1px 0 rgba(255,255,255,0.04),
                        0 18px 44px rgba(0,0,0,0.44) !important;
                    box-sizing: border-box !important;
                    max-height: 300px !important;
                    overflow-x: hidden !important;
                    overflow-y: auto !important;
                    padding: 0.46rem !important;
                }

                [data-baseweb="popover"] [role="option"],
                [data-testid="stSelectboxVirtualDropdown"] [role="option"],
                li[role="option"],
                div[role="option"] {
                    align-items: center !important;
                    background: transparent !important;
                    border: 1px solid transparent !important;
                    border-radius: 11px !important;
                    box-sizing: border-box !important;
                    color: #F3F5F8 !important;
                    display: flex !important;
                    font-size: 0.94rem !important;
                    font-weight: 650 !important;
                    line-height: 1.2 !important;
                    margin: 0.16rem 0 !important;
                    min-height: 48px !important;
                    padding: 0 0.92rem !important;
                    transition:
                        background 150ms ease,
                        border-color 150ms ease,
                        color 150ms ease,
                        transform 150ms ease !important;
                }

                [data-baseweb="popover"] [role="option"]:hover,
                [data-testid="stSelectboxVirtualDropdown"] [role="option"]:hover,
                li[role="option"]:hover,
                div[role="option"]:hover {
                    background: linear-gradient(90deg, rgba(229,57,53,0.20), rgba(229,57,53,0.08)) !important;
                    border-color: rgba(229,57,53,0.34) !important;
                    color: #FFFFFF !important;
                    transform: translateX(2px);
                }

                [data-baseweb="popover"] [role="option"][aria-selected="true"],
                [data-testid="stSelectboxVirtualDropdown"] [role="option"][aria-selected="true"],
                li[role="option"][aria-selected="true"],
                div[role="option"][aria-selected="true"] {
                    background: linear-gradient(90deg, rgba(229,57,53,0.34), rgba(229,57,53,0.15)) !important;
                    border-color: rgba(255,112,107,0.50) !important;
                    box-shadow: inset 3px 0 0 #F04444 !important;
                    color: #FFFFFF !important;
                }

                .stButton > button,
                div[data-testid="stDownloadButton"] > button {
                    background: #E53935 !important;
                    border: 1px solid #E53935 !important;
                    border-radius: 10px !important;
                    color: #FFFFFF !important;
                    font-weight: 700 !important;
                    min-height: 42px;
                }

                .stButton > button:hover,
                div[data-testid="stDownloadButton"] > button:hover {
                    background: #FF5252 !important;
                    border-color: #FF5252 !important;
                    box-shadow: 0 0 0 3px rgba(229,57,53,.16) !important;
                    color: #FFFFFF !important;
                }

                div[data-testid="stDataFrame"] {
                    background: #111111 !important;
                    border: 1px solid #2A2A2A !important;
                    border-radius: 12px !important;
                    overflow: hidden !important;
                }


                /* Tabel influencer dibuat ringan: HTML statis + kontrol Streamlit sederhana.
                   Ini mengurangi beban dibanding dua dataframe besar, tetapi tetap interaktif
                   melalui pencarian, filter platform, jumlah baris, mode ranking, dan detail akun. */
                .sna-v9-influencer-control-note {
                    background: linear-gradient(135deg, rgba(229,57,53,0.10), rgba(29,161,242,0.06));
                    border: 1px solid rgba(229,57,53,0.18);
                    border-radius: 12px;
                    color: #AAAAAA;
                    font-size: 0.75rem /* FIX: minimum 12px agar terbaca di tablet */;
                    line-height: 1.45;
                    margin: 0.25rem 0 0.85rem;
                    padding: 0.72rem 0.85rem;
                }

                .sna-v9-influencer-summary {
                    display: grid;
                    gap: 0.65rem;
                    grid-template-columns: repeat(3, minmax(0, 1fr));
                    margin: 0.2rem 0 0.9rem;
                }

                .sna-v9-influencer-mini-card {
                    background: #111111;
                    border: 1px solid #292929;
                    border-radius: 12px;
                    min-height: 82px;
                    padding: 0.72rem 0.8rem;
                    position: relative;
                    overflow: hidden;
                }

                .sna-v9-influencer-mini-card::after {
                    background: radial-gradient(circle, rgba(229,57,53,0.16), transparent 62%);
                    content: '';
                    height: 90px;
                    position: absolute;
                    right: -38px;
                    top: -42px;
                    width: 90px;
                }

                .sna-v9-influencer-mini-label {
                    color: #888888;
                    display: block;
                    font-size: 0.75rem /* FIX: minimum 12px agar terbaca di tablet */;
                    font-weight: 750;
                    letter-spacing: 0.02em;
                    text-transform: uppercase;
                }

                .sna-v9-influencer-mini-value {
                    color: #FFFFFF;
                    display: block;
                    font-family: 'Plus Jakarta Sans', 'Inter', sans-serif;
                    font-size: 1rem;
                    font-weight: 800;
                    line-height: 1.2;
                    margin-top: 0.2rem;
                    overflow: hidden;
                    position: relative;
                    text-overflow: ellipsis;
                    white-space: nowrap;
                    z-index: 1;
                }

                .sna-v9-influencer-mini-note {
                    color: #777777;
                    display: block;
                    font-size: 0.75rem /* FIX: minimum 12px agar terbaca di tablet */;
                    margin-top: 0.18rem;
                    position: relative;
                    z-index: 1;
                }

                .sna-v9-influencer-grid {
                    display: grid;
                    gap: 0.9rem;
                    grid-template-columns: repeat(2, minmax(0, 1fr));
                    margin-top: 0.45rem;
                }

                .sna-v9-influencer-table-card {
                    background: linear-gradient(180deg, #111111 0%, #0B0B0B 100%);
                    border: 1px solid #2A2A2A;
                    border-radius: 14px;
                    overflow: hidden;
                    box-shadow: 0 12px 32px rgba(0,0,0,0.22);
                }

                .sna-v9-influencer-table-head {
                    align-items: flex-start;
                    background: linear-gradient(135deg, rgba(229,57,53,0.14), rgba(255,255,255,0.02));
                    border-bottom: 1px solid #262626;
                    display: flex;
                    gap: 0.75rem;
                    justify-content: space-between;
                    padding: 0.85rem 0.95rem 0.72rem;
                }

                .sna-v9-influencer-table-title {
                    color: #FFFFFF;
                    font-family: 'Plus Jakarta Sans', 'Inter', sans-serif;
                    font-size: 0.92rem;
                    font-weight: 800;
                    margin: 0;
                }

                .sna-v9-influencer-table-subtitle {
                    color: #888888;
                    font-size: 0.75rem /* FIX: minimum 12px agar terbaca di tablet */;
                    line-height: 1.38;
                    margin-top: 0.18rem;
                }

                .sna-v9-influencer-table-badge {
                    align-items: center;
                    background: #E53935;
                    border-radius: 999px;
                    color: #FFFFFF;
                    display: inline-flex;
                    flex: 0 0 auto;
                    font-size: 0.75rem /* FIX: minimum 12px agar terbaca di tablet */;
                    font-weight: 800;
                    padding: 0.3rem 0.52rem;
                    white-space: nowrap;
                }

                .sna-v9-table-scroll {
                    overflow-x: auto;
                    scrollbar-color: #4A4A4A #111111;
                    scrollbar-width: thin;
                }

                table.sna-v9-influencer-table {
                    border-collapse: collapse;
                    color: #FFFFFF;
                    font-size: 0.76rem;
                    min-width: 680px;
                    width: 100%;
                }

                .sna-v9-influencer-table thead th {
                    background: #171A20;
                    border-bottom: 1px solid #2A2A2A;
                    color: #AAAAAA;
                    font-size: 0.75rem /* FIX: minimum 12px agar terbaca di tablet */;
                    font-weight: 800;
                    letter-spacing: 0.025em;
                    padding: 0.62rem 0.7rem;
                    text-align: left;
                    text-transform: uppercase;
                    white-space: nowrap;
                }

                .sna-v9-influencer-table tbody td {
                    border-bottom: 1px solid #202020;
                    padding: 0.58rem 0.7rem;
                    vertical-align: middle;
                    white-space: nowrap;
                }

                .sna-v9-influencer-table tbody tr {
                    transition: background .12s ease, transform .12s ease;
                }

                .sna-v9-influencer-table tbody tr:hover {
                    background: rgba(229,57,53,0.08);
                }

                .sna-v9-rank-pill {
                    align-items: center;
                    background: rgba(229,57,53,0.16);
                    border: 1px solid rgba(229,57,53,0.34);
                    border-radius: 999px;
                    color: #FFFFFF;
                    display: inline-flex;
                    font-size: 0.75rem /* FIX: minimum 12px agar terbaca di tablet */;
                    font-weight: 850;
                    height: 25px;
                    justify-content: center;
                    min-width: 32px;
                }

                .sna-v9-username-cell {
                    color: #FFFFFF;
                    display: inline-block;
                    font-weight: 800;
                    max-width: 170px;
                    overflow: hidden;
                    text-overflow: ellipsis;
                    vertical-align: middle;
                    white-space: nowrap;
                }

                .sna-v9-platform-chip {
                    align-items: center;
                    background: #161616;
                    border: 1px solid #303030;
                    border-radius: 999px;
                    color: #FFFFFF;
                    display: inline-flex;
                    font-size: 0.75rem /* FIX: minimum 12px agar terbaca di tablet */;
                    font-weight: 780;
                    gap: 0.35rem;
                    padding: 0.28rem 0.5rem;
                    white-space: nowrap;
                }

                .sna-v9-platform-chip-dot {
                    border-radius: 999px;
                    display: inline-block;
                    height: 8px;
                    width: 8px;
                }

                .sna-v9-num-cell {
                    color: #E7E7E7;
                    font-variant-numeric: tabular-nums;
                    font-weight: 750;
                    text-align: right;
                }

                .sna-v9-score-wrap {
                    align-items: center;
                    display: flex;
                    gap: 0.45rem;
                    min-width: 150px;
                }

                .sna-v9-score-text {
                    color: #E7E7E7;
                    font-variant-numeric: tabular-nums;
                    font-weight: 800;
                    min-width: 58px;
                    text-align: right;
                }

                .sna-v9-score-bar {
                    background: #242424;
                    border-radius: 999px;
                    height: 7px;
                    overflow: hidden;
                    width: 78px;
                }

                .sna-v9-score-fill {
                    background: linear-gradient(90deg, #B71C1C, #E53935, #FF5252);
                    border-radius: 999px;
                    height: 100%;
                    min-width: 4px;
                }

                /* Fase 19 — penyegaran visual tabel metrik influencer */
                .sna-v12-influencer-marker,
                .sna-v12-filter-marker { display: none; }

                div[data-testid="stMarkdownContainer"]:has(.sna-v12-influencer-marker),
                div[data-testid="stMarkdownContainer"]:has(.sna-v12-filter-marker) { display: none; }

                div[data-testid="stVerticalBlockBorderWrapper"]:has(.sna-v12-influencer-marker) {
                    background:
                        radial-gradient(circle at 0% 0%, rgba(229,57,53,0.14), transparent 24%),
                        radial-gradient(circle at 100% 0%, rgba(131,58,180,0.11), transparent 26%),
                        radial-gradient(circle at 100% 100%, rgba(29,161,242,0.09), transparent 30%),
                        linear-gradient(180deg, rgba(10,14,22,0.98), rgba(10,10,10,0.99)) !important;
                    border: 1px solid rgba(255,255,255,0.10) !important;
                    border-radius: 20px !important;
                    box-shadow: 0 26px 70px rgba(0,0,0,0.34), inset 0 1px 0 rgba(255,255,255,0.025) !important;
                    overflow: hidden !important;
                    padding: 1.25rem 1.2rem 1.35rem !important;
                    position: relative;
                    animation: snaV12Rise .62s cubic-bezier(.2,.8,.2,1) both;
                }

                div[data-testid="stVerticalBlockBorderWrapper"]:has(.sna-v12-influencer-marker)::before {
                    animation: snaV12Sweep 5.2s linear infinite;
                    background: linear-gradient(90deg, transparent, rgba(229,57,53,0.88), rgba(131,58,180,0.72), rgba(29,161,242,0.72), transparent);
                    content: '';
                    height: 2px;
                    left: 0;
                    position: absolute;
                    right: 0;
                    top: 0;
                    z-index: 2;
                }

                .sna-v12-influencer-hero {
                    align-items: flex-start;
                    display: flex;
                    gap: 1rem;
                    justify-content: space-between;
                    margin: 0 0 0.9rem;
                    padding: 0.15rem 0.15rem 0;
                }

                .sna-v12-influencer-hero .sna-v9-section-title {
                    font-size: clamp(1.55rem, 2.8vw, 2.25rem);
                    letter-spacing: -0.035em;
                    line-height: 1.08;
                }

                .sna-v12-influencer-hero .sna-v9-section-subtitle {
                    color: #B6B6B6 !important;
                    font-size: 0.82rem;
                    line-height: 1.58;
                    max-width: 890px;
                }

                .sna-v12-live-badge {
                    align-items: center;
                    background: linear-gradient(135deg, rgba(76,175,80,0.16), rgba(29,161,242,0.10));
                    border: 1px solid rgba(76,175,80,0.34);
                    border-radius: 999px;
                    color: #DDF8E0;
                    display: inline-flex;
                    flex: 0 0 auto;
                    font-size: 0.75rem /* FIX: minimum 12px agar terbaca di tablet */;
                    font-weight: 850;
                    gap: 0.42rem;
                    margin-top: 0.15rem;
                    padding: 0.42rem 0.68rem;
                    white-space: nowrap;
                }

                .sna-v12-live-dot {
                    animation: snaV12Pulse 1.8s ease-in-out infinite;
                    background: #4CAF50;
                    border-radius: 999px;
                    box-shadow: 0 0 0 0 rgba(76,175,80,0.45);
                    display: inline-flex;
                    height: 8px;
                    width: 8px;
                }

                .sna-v12-chip-row {
                    display: flex;
                    flex-wrap: wrap;
                    gap: 0.42rem;
                    margin: -0.2rem 0 1rem;
                }

                .sna-v12-chip {
                    align-items: center;
                    background: rgba(255,255,255,0.045);
                    border: 1px solid rgba(255,255,255,0.09);
                    border-radius: 999px;
                    color: #D7D7D7;
                    display: inline-flex;
                    font-size: 0.75rem /* FIX: minimum 12px agar terbaca di tablet */;
                    font-weight: 760;
                    gap: 0.38rem;
                    padding: 0.34rem 0.62rem;
                    transition: border-color .18s ease, box-shadow .18s ease, transform .18s ease;
                }

                .sna-v12-chip:hover {
                    border-color: rgba(229,57,53,0.30);
                    box-shadow: 0 10px 24px rgba(0,0,0,0.22);
                    transform: translateY(-2px);
                }

                .sna-v12-chip-dot {
                    background: var(--chip-color, #E53935);
                    border-radius: 999px;
                    display: inline-flex;
                    height: 8px;
                    width: 8px;
                }

                .sna-v9-influencer-summary {
                    gap: 0.78rem;
                    margin: 0.25rem 0 1rem;
                }

                .sna-v9-influencer-mini-card {
                    --summary-accent: #E53935;
                    background:
                        radial-gradient(circle at 96% 4%, color-mix(in srgb, var(--summary-accent) 22%, transparent), transparent 37%),
                        linear-gradient(145deg, rgba(23,23,27,0.96), rgba(13,13,13,0.98));
                    border: 1px solid rgba(255,255,255,0.09);
                    border-radius: 16px;
                    box-shadow: 0 14px 34px rgba(0,0,0,0.22);
                    cursor: default;
                    min-height: 112px;
                    padding: 0.9rem 0.95rem 0.88rem;
                    transition: border-color .18s ease, box-shadow .18s ease, transform .18s ease;
                    animation: snaV12Rise .56s cubic-bezier(.2,.8,.2,1) both;
                }

                .sna-v9-influencer-mini-card::before {
                    background: linear-gradient(90deg, var(--summary-accent), transparent);
                    content: '';
                    height: 3px;
                    left: 0;
                    position: absolute;
                    right: 0;
                    top: 0;
                }

                .sna-v9-influencer-mini-card::after {
                    background: radial-gradient(circle, color-mix(in srgb, var(--summary-accent) 28%, transparent), transparent 64%);
                    height: 128px;
                    right: -46px;
                    top: -58px;
                    width: 128px;
                }

                .sna-v9-influencer-mini-card:hover {
                    border-color: color-mix(in srgb, var(--summary-accent) 48%, rgba(255,255,255,0.12));
                    box-shadow: 0 20px 46px rgba(0,0,0,0.30), 0 0 0 1px color-mix(in srgb, var(--summary-accent) 16%, transparent);
                    transform: translateY(-4px);
                }

                .sna-v12-summary-degree { --summary-accent: #E53935; animation-delay: .02s; }
                .sna-v12-summary-reach { --summary-accent: #833AB4; animation-delay: .08s; }
                .sna-v12-summary-platform { --summary-accent: #1DA1F2; animation-delay: .14s; }

                .sna-v12-summary-top {
                    align-items: center;
                    display: flex;
                    gap: 0.52rem;
                    justify-content: space-between;
                    margin-bottom: 0.36rem;
                    position: relative;
                    z-index: 1;
                }

                .sna-v12-summary-icon {
                    align-items: center;
                    background: color-mix(in srgb, var(--summary-accent) 18%, rgba(255,255,255,0.04));
                    border: 1px solid color-mix(in srgb, var(--summary-accent) 40%, rgba(255,255,255,0.08));
                    border-radius: 10px;
                    color: var(--summary-accent);
                    display: inline-flex;
                    font-size: 0.9rem;
                    font-weight: 900;
                    height: 30px;
                    justify-content: center;
                    width: 30px;
                }

                .sna-v12-summary-tag {
                    background: rgba(255,255,255,0.045);
                    border: 1px solid rgba(255,255,255,0.08);
                    border-radius: 999px;
                    color: #BDBDBD;
                    font-size: 0.75rem /* FIX: minimum 12px agar terbaca di tablet */;
                    font-weight: 800;
                    padding: 0.25rem 0.44rem;
                    text-transform: uppercase;
                }

                .sna-v9-influencer-mini-label {
                    color: #AFAFAF;
                    font-size: 0.75rem /* FIX: minimum 12px agar terbaca di tablet */;
                    letter-spacing: 0.045em;
                }

                .sna-v9-influencer-mini-value {
                    font-size: 1.12rem;
                    letter-spacing: -0.02em;
                    margin-top: 0.25rem;
                }

                .sna-v9-influencer-mini-note {
                    color: #A2A2A2;
                    font-size: 0.75rem /* FIX: minimum 12px agar terbaca di tablet */;
                    line-height: 1.45;
                    margin-top: 0.28rem;
                }

                .sna-v9-influencer-control-note {
                    align-items: center;
                    background: linear-gradient(135deg, rgba(229,57,53,0.10), rgba(131,58,180,0.08), rgba(29,161,242,0.08));
                    border: 1px solid rgba(229,57,53,0.20);
                    border-radius: 14px;
                    color: #C4C4C4;
                    display: flex;
                    font-size: 0.76rem;
                    gap: 0.6rem;
                    line-height: 1.5;
                    margin: 0.25rem 0 0.95rem;
                    padding: 0.82rem 0.9rem;
                    transition: border-color .18s ease, box-shadow .18s ease, transform .18s ease;
                }

                .sna-v9-influencer-control-note::before {
                    align-items: center;
                    background: rgba(229,57,53,0.18);
                    border: 1px solid rgba(229,57,53,0.34);
                    border-radius: 999px;
                    color: #FF8A87;
                    content: 'FILTER';
                    display: inline-flex;
                    flex: 0 0 auto;
                    font-size: 0.75rem /* FIX: minimum 12px agar terbaca di tablet */;
                    font-weight: 900;
                    letter-spacing: 0.05em;
                    padding: 0.28rem 0.46rem;
                }

                .sna-v9-influencer-control-note:hover {
                    border-color: rgba(229,57,53,0.36);
                    box-shadow: 0 14px 30px rgba(0,0,0,0.22);
                    transform: translateY(-2px);
                }

                div[data-testid="stForm"]:has(.sna-v12-filter-marker),
                div[data-testid="stVerticalBlockBorderWrapper"]:has(.sna-v12-filter-marker) {
                    background:
                        radial-gradient(circle at 0% 0%, rgba(29,161,242,0.09), transparent 26%),
                        radial-gradient(circle at 100% 100%, rgba(229,57,53,0.09), transparent 28%),
                        linear-gradient(180deg, rgba(20,27,39,0.95), rgba(15,20,30,0.98)) !important;
                    border: 1px solid rgba(97,125,163,0.40) !important;
                    border-radius: 16px !important;
                    box-shadow: inset 0 1px 0 rgba(255,255,255,0.025), 0 14px 34px rgba(0,0,0,0.20) !important;
                    padding: 1rem 1rem 0.9rem !important;
                    transition: border-color .18s ease, box-shadow .18s ease;
                }

                div[data-testid="stForm"]:has(.sna-v12-filter-marker):focus-within,
                div[data-testid="stVerticalBlockBorderWrapper"]:has(.sna-v12-filter-marker):focus-within {
                    border-color: rgba(29,161,242,0.60) !important;
                    box-shadow: 0 0 0 3px rgba(29,161,242,0.08), 0 18px 40px rgba(0,0,0,0.26) !important;
                }

                div[data-testid="stForm"]:has(.sna-v12-filter-marker) label,
                div[data-testid="stVerticalBlockBorderWrapper"]:has(.sna-v12-filter-marker) label {
                    color: #EDEDED !important;
                    font-weight: 760 !important;
                }

                div[data-testid="stForm"]:has(.sna-v12-filter-marker) input,
                div[data-testid="stForm"]:has(.sna-v12-filter-marker) [data-baseweb="select"] > div,
                div[data-testid="stVerticalBlockBorderWrapper"]:has(.sna-v12-filter-marker) input,
                div[data-testid="stVerticalBlockBorderWrapper"]:has(.sna-v12-filter-marker) [data-baseweb="select"] > div {
                    border-radius: 11px !important;
                    transition: border-color .18s ease, box-shadow .18s ease, transform .18s ease;
                }

                div[data-testid="stForm"]:has(.sna-v12-filter-marker) input:focus,
                div[data-testid="stForm"]:has(.sna-v12-filter-marker) [data-baseweb="select"] > div:focus-within,
                div[data-testid="stVerticalBlockBorderWrapper"]:has(.sna-v12-filter-marker) input:focus,
                div[data-testid="stVerticalBlockBorderWrapper"]:has(.sna-v12-filter-marker) [data-baseweb="select"] > div:focus-within {
                    border-color: rgba(29,161,242,0.72) !important;
                    box-shadow: 0 0 0 3px rgba(29,161,242,0.09) !important;
                    transform: translateY(-1px);
                }

                div[data-testid="stForm"]:has(.sna-v12-filter-marker) button[kind="primary"],
                div[data-testid="stVerticalBlockBorderWrapper"]:has(.sna-v12-filter-marker) button[kind="primary"] {
                    background: linear-gradient(105deg, #E53935 0%, #C43868 48%, #1DA1F2 100%) !important;
                    border: 1px solid rgba(255,255,255,0.13) !important;
                    box-shadow: 0 12px 28px rgba(229,57,53,0.18) !important;
                    position: relative;
                    transition: box-shadow .18s ease, filter .18s ease, transform .18s ease !important;
                }

                div[data-testid="stForm"]:has(.sna-v12-filter-marker) button[kind="primary"]:hover,
                div[data-testid="stVerticalBlockBorderWrapper"]:has(.sna-v12-filter-marker) button[kind="primary"]:hover {
                    box-shadow: 0 16px 36px rgba(229,57,53,0.26), 0 0 0 3px rgba(29,161,242,0.08) !important;
                    filter: brightness(1.07);
                    transform: translateY(-2px);
                }

                .sna-v9-influencer-grid {
                    gap: 1rem;
                    margin-top: 0.75rem;
                }

                .sna-v9-influencer-table-card {
                    --table-accent: #E53935;
                    background:
                        radial-gradient(circle at 100% 0%, color-mix(in srgb, var(--table-accent) 15%, transparent), transparent 30%),
                        linear-gradient(180deg, rgba(17,17,19,0.99), rgba(8,8,9,0.99));
                    border: 1px solid rgba(255,255,255,0.09);
                    border-radius: 17px;
                    box-shadow: 0 18px 46px rgba(0,0,0,0.26);
                    position: relative;
                    transition: border-color .2s ease, box-shadow .2s ease, transform .2s ease;
                    animation: snaV12Rise .58s cubic-bezier(.2,.8,.2,1) both;
                }

                .sna-v9-influencer-table-card::before {
                    background: linear-gradient(90deg, var(--table-accent), transparent 78%);
                    content: '';
                    height: 3px;
                    left: 0;
                    position: absolute;
                    right: 0;
                    top: 0;
                    z-index: 2;
                }

                .sna-v9-influencer-table-card:hover {
                    border-color: color-mix(in srgb, var(--table-accent) 46%, rgba(255,255,255,0.10));
                    box-shadow: 0 24px 60px rgba(0,0,0,0.34), 0 0 0 1px color-mix(in srgb, var(--table-accent) 14%, transparent);
                    transform: translateY(-3px);
                }

                .sna-v12-table-degree { --table-accent: #E53935; animation-delay: .02s; }
                .sna-v12-table-followers { --table-accent: #833AB4; animation-delay: .10s; }

                .sna-v9-influencer-table-head {
                    background: linear-gradient(135deg, color-mix(in srgb, var(--table-accent) 17%, transparent), rgba(255,255,255,0.015));
                    border-bottom: 1px solid rgba(255,255,255,0.08);
                    padding: 1rem 1.05rem 0.82rem;
                }

                .sna-v9-influencer-table-title {
                    font-size: 0.98rem;
                    letter-spacing: -0.015em;
                }

                .sna-v9-influencer-table-subtitle {
                    color: #A0A0A0;
                    font-size: 0.75rem /* FIX: minimum 12px agar terbaca di tablet */;
                    line-height: 1.48;
                }

                .sna-v9-influencer-table-badge {
                    background: var(--table-accent);
                    border: 1px solid rgba(255,255,255,0.13);
                    box-shadow: 0 8px 20px color-mix(in srgb, var(--table-accent) 26%, transparent);
                    padding: 0.34rem 0.58rem;
                    transition: filter .18s ease, transform .18s ease;
                }

                .sna-v9-influencer-table-card:hover .sna-v9-influencer-table-badge {
                    filter: brightness(1.12);
                    transform: translateY(-1px) scale(1.03);
                }

                .sna-v9-influencer-table thead th {
                    background: rgba(25,29,38,0.96);
                    border-bottom: 1px solid rgba(255,255,255,0.09);
                    color: #B5B5B5;
                    position: sticky;
                    top: 0;
                    z-index: 1;
                }

                .sna-v9-influencer-table tbody tr {
                    position: relative;
                    transition: background .16s ease, box-shadow .16s ease, transform .16s ease;
                }

                .sna-v9-influencer-table tbody tr:hover {
                    background: color-mix(in srgb, var(--table-accent) 10%, transparent);
                    box-shadow: inset 3px 0 0 var(--table-accent);
                    transform: translateX(2px);
                }

                .sna-v12-row-top td {
                    background: linear-gradient(90deg, color-mix(in srgb, var(--table-accent) 7%, transparent), transparent 62%);
                }

                .sna-v9-rank-pill {
                    transition: box-shadow .18s ease, filter .18s ease, transform .18s ease;
                }

                .sna-v9-influencer-table tbody tr:hover .sna-v9-rank-pill {
                    filter: brightness(1.12);
                    transform: scale(1.06);
                }

                .sna-v12-rank-1 {
                    background: linear-gradient(135deg, #7A5A00, #D6A817) !important;
                    border-color: #F6D76B !important;
                    box-shadow: 0 0 16px rgba(246,215,107,0.20);
                }

                .sna-v12-rank-2 {
                    background: linear-gradient(135deg, #4C535A, #929AA4) !important;
                    border-color: #C7CDD4 !important;
                    box-shadow: 0 0 14px rgba(199,205,212,0.16);
                }

                .sna-v12-rank-3 {
                    background: linear-gradient(135deg, #6A351E, #B36A3C) !important;
                    border-color: #E1A17B !important;
                    box-shadow: 0 0 14px rgba(225,161,123,0.16);
                }

                .sna-v12-user-wrap {
                    align-items: center;
                    display: inline-flex;
                    gap: 0.52rem;
                    max-width: 210px;
                }

                .sna-v12-avatar {
                    align-items: center;
                    background: color-mix(in srgb, var(--table-accent) 18%, #161616);
                    border: 1px solid color-mix(in srgb, var(--table-accent) 42%, #303030);
                    border-radius: 10px;
                    color: #FFFFFF;
                    display: inline-flex;
                    flex: 0 0 auto;
                    font-size: 0.75rem /* FIX: minimum 12px agar terbaca di tablet */;
                    font-weight: 900;
                    height: 28px;
                    justify-content: center;
                    letter-spacing: 0.02em;
                    width: 28px;
                }

                .sna-v12-table-followers .sna-v9-score-fill {
                    background: linear-gradient(90deg, #5B2182, #833AB4, #B66DE0);
                }

                .sna-v12-table-degree .sna-v9-score-fill {
                    background: linear-gradient(90deg, #B71C1C, #E53935, #FF6B67);
                }

                .sna-v9-score-bar {
                    background: rgba(255,255,255,0.09);
                    height: 8px;
                }

                .sna-v9-score-fill {
                    box-shadow: 0 0 12px color-mix(in srgb, var(--table-accent) 32%, transparent);
                    transition: filter .18s ease;
                }

                .sna-v9-influencer-table tbody tr:hover .sna-v9-score-fill {
                    filter: brightness(1.18);
                }

                @keyframes snaV12Rise {
                    from { opacity: 0; transform: translateY(14px); }
                    to { opacity: 1; transform: translateY(0); }
                }

                @keyframes snaV12Sweep {
                    0% { transform: translateX(-45%); opacity: .12; }
                    50% { transform: translateX(0); opacity: .92; }
                    100% { transform: translateX(45%); opacity: .12; }
                }

                @keyframes snaV12Pulse {
                    0%, 100% { box-shadow: 0 0 0 0 rgba(76,175,80,0.36); }
                    50% { box-shadow: 0 0 0 7px rgba(76,175,80,0); }
                }

                @media (max-width: 760px) {
                    .sna-v12-influencer-hero {
                        align-items: flex-start;
                        flex-direction: column;
                    }
                    .sna-v12-live-badge { margin-top: 0; }
                    div[data-testid="stVerticalBlockBorderWrapper"]:has(.sna-v12-influencer-marker) {
                        padding: 1rem 0.8rem 1.1rem !important;
                    }
                }

                @media (prefers-reduced-motion: reduce) {
                    div[data-testid="stVerticalBlockBorderWrapper"]:has(.sna-v12-influencer-marker),
                    .sna-v9-influencer-mini-card,
                    .sna-v9-influencer-table-card,
                    .sna-v12-live-dot {
                        animation: none !important;
                        transition: none !important;
                    }
                    div[data-testid="stVerticalBlockBorderWrapper"]:has(.sna-v12-influencer-marker)::before {
                        animation: none !important;
                    }
                }

                .sna-v9-detail-panel {
                    background:
                        radial-gradient(circle at 10% 0%, rgba(229,57,53,0.16), transparent 32%),
                        radial-gradient(circle at 95% 10%, rgba(29,161,242,0.13), transparent 34%),
                        linear-gradient(135deg, rgba(18,18,22,0.96), rgba(9,14,20,0.96));
                    border: 1px solid rgba(229,57,53,0.24);
                    border-radius: 18px;
                    box-shadow: 0 18px 48px rgba(0,0,0,0.24), inset 0 1px 0 rgba(255,255,255,0.035);
                    margin: 1rem 0 1.35rem;
                    overflow: hidden;
                    padding: 1.05rem 1.1rem 1.15rem;
                    position: relative;
                }

                .sna-v9-detail-panel::before {
                    background: linear-gradient(90deg, #E53935, rgba(29,161,242,0.65), transparent);
                    content: "";
                    height: 2px;
                    left: 0;
                    opacity: 0.9;
                    position: absolute;
                    right: 0;
                    top: 0;
                }

                .sna-v9-detail-header {
                    align-items: flex-start;
                    display: flex;
                    gap: 0.9rem;
                    justify-content: space-between;
                    margin-bottom: 0.85rem;
                }

                .sna-v9-detail-title {
                    color: #FFFFFF;
                    font-family: 'Plus Jakarta Sans', 'Inter', sans-serif;
                    font-size: 1.08rem;
                    font-weight: 900;
                    letter-spacing: -0.02em;
                    margin: 0;
                }

                .sna-v9-detail-subtitle {
                    color: #AAAAAA;
                    font-size: 0.76rem;
                    font-weight: 650;
                    line-height: 1.5;
                    margin: 0.3rem 0 0;
                }

                .sna-v9-detail-chip {
                    background: rgba(255,255,255,0.055);
                    border: 1px solid rgba(255,255,255,0.12);
                    border-radius: 999px;
                    color: #EDEDED;
                    flex: 0 0 auto;
                    font-size: 0.75rem /* FIX: minimum 12px agar terbaca di tablet */;
                    font-weight: 850;
                    padding: 0.38rem 0.68rem;
                    white-space: nowrap;
                }

                .sna-v9-detail-grid {
                    display: grid;
                    gap: 0.7rem;
                    grid-template-columns: repeat(5, minmax(0, 1fr));
                }

                .sna-v9-detail-item {
                    --detail-accent: #E53935;
                    background: linear-gradient(145deg, rgba(17,17,17,0.88), rgba(24,24,28,0.72));
                    border: 1px solid rgba(255,255,255,0.08);
                    border-radius: 14px;
                    box-shadow: 0 10px 24px rgba(0,0,0,0.18);
                    cursor: pointer;
                    min-height: 98px;
                    overflow: hidden;
                    padding: 0.72rem 0.78rem;
                    position: relative;
                    transition: transform 180ms ease, border-color 180ms ease, box-shadow 180ms ease, background 180ms ease;
                }

                .sna-v9-detail-item::before {
                    background: linear-gradient(180deg, var(--detail-accent), transparent);
                    content: "";
                    inset: 0 auto 0 0;
                    opacity: 0.9;
                    position: absolute;
                    width: 3px;
                }

                .sna-v9-detail-item::after {
                    background: radial-gradient(circle at 85% 0%, color-mix(in srgb, var(--detail-accent) 24%, transparent), transparent 42%);
                    content: "";
                    height: 120px;
                    pointer-events: none;
                    position: absolute;
                    right: -36px;
                    top: -46px;
                    transform: rotate(18deg);
                    transition: opacity 180ms ease, transform 180ms ease;
                    width: 130px;
                    opacity: 0.68;
                }

                .sna-v9-detail-item:hover {
                    background: linear-gradient(145deg, rgba(24,24,28,0.96), rgba(30,30,34,0.82));
                    border-color: color-mix(in srgb, var(--detail-accent) 56%, rgba(255,255,255,0.12));
                    box-shadow: 0 16px 38px rgba(0,0,0,0.28), 0 0 0 1px color-mix(in srgb, var(--detail-accent) 18%, transparent);
                    transform: translateY(-3px);
                }

                .sna-v9-detail-item:hover::after {
                    opacity: 1;
                    transform: rotate(18deg) translateX(-4px);
                }

                .sna-v9-detail-item[open] {
                    border-color: color-mix(in srgb, var(--detail-accent) 68%, rgba(255,255,255,0.12));
                    box-shadow: 0 16px 40px rgba(0,0,0,0.34), 0 0 18px color-mix(in srgb, var(--detail-accent) 20%, transparent);
                }

                .sna-v9-detail-item summary {
                    list-style: none;
                    outline: none;
                    position: relative;
                    z-index: 1;
                }

                .sna-v9-detail-item summary::-webkit-details-marker {
                    display: none;
                }

                .sna-v9-detail-card-top {
                    align-items: center;
                    display: flex;
                    gap: 0.5rem;
                    justify-content: space-between;
                    margin-bottom: 0.45rem;
                }

                .sna-v9-detail-icon {
                    align-items: center;
                    background: color-mix(in srgb, var(--detail-accent) 20%, rgba(255,255,255,0.06));
                    border: 1px solid color-mix(in srgb, var(--detail-accent) 38%, rgba(255,255,255,0.08));
                    border-radius: 999px;
                    color: var(--detail-accent);
                    display: inline-flex;
                    flex: 0 0 auto;
                    font-size: 0.78rem;
                    height: 26px;
                    justify-content: center;
                    width: 26px;
                }

                .sna-v9-detail-label {
                    color: #AFAFAF;
                    display: block;
                    font-size: 0.75rem /* FIX: minimum 12px agar terbaca di tablet */;
                    font-weight: 850;
                    letter-spacing: 0.04em;
                    line-height: 1.2;
                    text-transform: uppercase;
                }

                .sna-v9-detail-value {
                    color: #FFFFFF;
                    display: block;
                    font-size: 0.94rem;
                    font-weight: 900;
                    letter-spacing: -0.01em;
                    line-height: 1.2;
                    margin-top: 0.28rem;
                    overflow: hidden;
                    position: relative;
                    text-overflow: ellipsis;
                    white-space: nowrap;
                    z-index: 1;
                }

                .sna-v9-detail-hint {
                    color: #7F7F7F;
                    display: block;
                    font-size: 0.75rem /* FIX: minimum 12px agar terbaca di tablet */;
                    font-weight: 700;
                    line-height: 1.35;
                    margin-top: 0.32rem;
                    position: relative;
                    z-index: 1;
                }

                .sna-v9-detail-more {
                    background: rgba(0,0,0,0.22);
                    border: 1px dashed color-mix(in srgb, var(--detail-accent) 44%, rgba(255,255,255,0.10));
                    border-radius: 10px;
                    color: #DADADA;
                    font-size: 0.75rem /* FIX: minimum 12px agar terbaca di tablet */;
                    font-weight: 650;
                    line-height: 1.45;
                    margin-top: 0.62rem;
                    padding: 0.48rem 0.52rem;
                    position: relative;
                    z-index: 1;
                }

                .sna-v9-detail-platform { --detail-accent: #1DA1F2; }
                .sna-v9-detail-followers { --detail-accent: #833AB4; }
                .sna-v9-detail-degree { --detail-accent: #E53935; }
                .sna-v9-detail-in { --detail-accent: #4CAF50; }
                .sna-v9-detail-out { --detail-accent: #FF9800; }

                .sna-v9-detail-export-gap {
                    height: 0.9rem;
                }

                @media (max-width: 1100px) {
                    .sna-v9-influencer-grid { grid-template-columns: 1fr; }
                    .sna-v9-influencer-summary { grid-template-columns: 1fr; }
                    .sna-v9-detail-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); }
                }

                @media (max-width: 720px) {
                    .sna-v9-detail-grid { grid-template-columns: 1fr; }
                }

                .sna-v9-chart-fullscreen-link {
                    align-items: center;
                    background: linear-gradient(135deg, rgba(229,57,53,0.96), rgba(183,28,28,0.96));
                    border: 1px solid rgba(255,255,255,0.12);
                    border-radius: 999px;
                    box-shadow: 0 10px 24px rgba(229,57,53,0.18);
                    color: #FFFFFF !important;
                    display: inline-flex;
                    font-size: 0.76rem;
                    font-weight: 850;
                    gap: 0.4rem;
                    margin: 0 0 0.55rem;
                    padding: 0.46rem 0.78rem;
                    text-decoration: none !important;
                    transition: transform 160ms ease, box-shadow 160ms ease, filter 160ms ease;
                    width: fit-content;
                }

                .sna-v9-chart-fullscreen-link:hover {
                    box-shadow: 0 14px 34px rgba(229,57,53,0.30);
                    filter: brightness(1.05);
                    transform: translateY(-1px);
                }

                .sna-v9-chart-action-marker {
                    display: none !important;
                }

                div[data-testid="stColumn"]:has(.sna-v9-chart-action-marker) div[data-testid="stButton"] button {
                    background: linear-gradient(135deg, #E53935, #B71C1C) !important;
                    border: 1px solid rgba(255,255,255,0.14) !important;
                    border-radius: 999px !important;
                    box-shadow: 0 10px 24px rgba(229,57,53,0.18) !important;
                    color: #FFFFFF !important;
                    font-family: 'Plus Jakarta Sans', 'Inter', sans-serif !important;
                    font-size: 0.76rem !important;
                    font-weight: 850 !important;
                    min-height: 38px !important;
                    padding: 0.42rem 0.72rem !important;
                    transition: transform 160ms ease, box-shadow 160ms ease, filter 160ms ease !important;
                }

                div[data-testid="stColumn"]:has(.sna-v9-chart-action-marker) div[data-testid="stButton"] button:hover {
                    box-shadow: 0 14px 34px rgba(229,57,53,0.30) !important;
                    filter: brightness(1.05) !important;
                    transform: translateY(-1px) !important;
                }

                div[data-testid="stDialog"] > div,
                div[data-baseweb="modal"] > div {
                    background: #0D0D0D !important;
                }

                div[data-testid="stDialog"] section,
                div[data-baseweb="modal"] section {
                    background: #0D0D0D !important;
                    border: 1px solid #2A2A2A !important;
                    border-radius: 0 !important;
                    box-shadow: none !important;
                    height: 100dvh !important;
                    max-height: 100dvh !important;
                    max-width: 100vw !important;
                    width: 100vw !important;
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

                div[data-testid="stDialog"] div[data-testid="stVerticalBlock"]:has(.sna-v9-fullscreen-title),
                div[data-baseweb="modal"] div[data-testid="stVerticalBlock"]:has(.sna-v9-fullscreen-title) {
                    gap: 0.45rem !important;
                    height: 100dvh !important;
                    margin: 0 !important;
                    max-height: 100dvh !important;
                    overflow: hidden !important;
                    padding: 14px 18px 12px !important;
                    width: 100vw !important;
                }

                .sna-v9-fullscreen-heading {
                    display: flex;
                    flex: 0 0 auto;
                    flex-direction: column;
                    gap: 0.35rem;
                    margin: 0 0 18px;
                    padding-right: 52px;
                }

                .sna-v9-fullscreen-title {
                    color: #FFFFFF !important;
                    font-family: 'Plus Jakarta Sans', 'Inter', sans-serif;
                    font-size: clamp(1.15rem, 2vw, 1.65rem);
                    font-weight: 800;
                    letter-spacing: -0.02em;
                    line-height: 1.15;
                    margin: 0;
                    padding: 0;
                }

                .sna-v9-fullscreen-hint {
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

                div[data-testid="stExpander"] details {
                    background: #1A1A1A !important;
                    border: 1px solid #2A2A2A !important;
                    border-radius: 12px !important;
                    box-shadow: 0 10px 28px rgba(0,0,0,0.18);
                }

                div[data-testid="stExpander"] summary {
                    color: #FFFFFF !important;
                    font-family: 'Plus Jakarta Sans', 'Inter', sans-serif !important;
                    font-weight: 750 !important;
                }

                .sna-v9-graph-kpi-grid {
                    display: grid;
                    gap: 0.85rem;
                    grid-template-columns: repeat(3, minmax(0, 1fr));
                    margin: 0.85rem 0 0.95rem;
                }

                .sna-v9-graph-kpi {
                    background:
                        radial-gradient(circle at 94% 12%, rgba(229,57,53,0.13), transparent 36%),
                        linear-gradient(145deg, #151922 0%, #111111 100%);
                    border: 1px solid #2A3442;
                    border-radius: 12px;
                    min-height: 98px;
                    overflow: hidden;
                    padding: 0.9rem 1rem;
                    position: relative;
                }

                .sna-v9-graph-kpi::before {
                    background: linear-gradient(180deg, #E53935, rgba(229,57,53,0.08));
                    border-radius: 999px;
                    content: '';
                    height: 42px;
                    left: 0;
                    position: absolute;
                    top: 1rem;
                    width: 3px;
                }

                .sna-v9-graph-kpi-label {
                    color: #AAAAAA;
                    display: block;
                    font-size: 0.75rem /* FIX: minimum 12px agar terbaca di tablet */;
                    font-weight: 700;
                    margin-bottom: 0.35rem;
                }

                .sna-v9-graph-kpi-value {
                    color: #FFFFFF;
                    display: block;
                    font-family: 'Plus Jakarta Sans', 'Inter', sans-serif;
                    font-size: clamp(1.75rem, 4vw, 2.35rem);
                    font-weight: 800;
                    letter-spacing: -0.04em;
                    line-height: 1.05;
                }

                .sna-v9-graph-kpi-note {
                    color: #777777;
                    display: block;
                    font-size: 0.75rem /* FIX: minimum 12px agar terbaca di tablet */;
                    line-height: 1.35;
                    margin-top: 0.35rem;
                }

                .sna-v9-interaction-strip {
                    align-items: center;
                    background: linear-gradient(135deg, rgba(229,57,53,0.10), rgba(29,161,242,0.08));
                    border: 1px solid rgba(229,57,53,0.24);
                    border-radius: 12px;
                    color: #D7D7D7;
                    display: flex;
                    flex-wrap: wrap;
                    gap: 0.55rem;
                    justify-content: space-between;
                    margin: 0.25rem 0 0.85rem;
                    padding: 0.75rem 0.9rem;
                }

                .sna-v9-interaction-strip strong {
                    color: #FFFFFF;
                    font-size: 0.78rem;
                }

                .sna-v9-interaction-strip span {
                    color: #AAAAAA;
                    font-size: 0.75rem /* FIX: minimum 12px agar terbaca di tablet */;
                }

                .sna-v9-interaction-pill {
                    background: #111111;
                    border: 1px solid #303030;
                    border-radius: 999px;
                    color: #D4D4D4 !important;
                    display: inline-flex;
                    font-size: 0.75rem /* FIX: minimum 12px agar terbaca di tablet */ !important;
                    font-weight: 700;
                    padding: 0.32rem 0.58rem;
                }

                /* FIX: PyVis tidak boleh keluar dari container pada lebar 768px. */
                .sna-v9-graph-frame {
                    max-width: 100% !important;
                    overflow-x: auto !important;
                    width: 100% !important;
                }

                .sna-v9-graph-frame iframe,
                [data-testid="stIFrame"] iframe {
                    border-radius: 16px !important;
                    border: 1px solid #2A2A2A !important;
                    background: #0D0D0D !important;
                    box-shadow: 0 18px 45px rgba(0,0,0,0.28);
                    display: block !important;
                    max-width: 100% !important;
                    min-width: 0 !important;
                    overflow: hidden !important;
                    width: 100% !important;
                    clip-path: inset(0 round 16px) !important;
                    -webkit-mask-image: -webkit-radial-gradient(white, black) !important;
                }

                div[data-testid="stIFrame"],
                div[data-testid="stElementContainer"]:has([data-testid="stIFrame"]) {
                    border-radius: 16px !important;
                    max-width: 100% !important;
                    overflow-x: auto !important;
                    width: 100% !important;
                }

                /* Fase 9 — visualisasi graf statis akademik IndiBiz */
                .sna-v11-academic-note {
                    align-items: flex-start;
                    background: linear-gradient(135deg, rgba(229,57,53,0.11), rgba(29,161,242,0.06));
                    border: 1px solid rgba(229,57,53,0.24);
                    border-radius: 12px;
                    color: #CFCFCF;
                    display: flex;
                    gap: 0.75rem;
                    line-height: 1.55;
                    margin: 0.15rem 0 0.85rem;
                    padding: 0.82rem 0.9rem;
                }

                .sna-v11-academic-note strong { color: #FFFFFF; }

                .sna-v11-badge {
                    background: rgba(229,57,53,0.15);
                    border: 1px solid rgba(229,57,53,0.34);
                    border-radius: 999px;
                    color: #FF8A87;
                    display: inline-flex;
                    flex: 0 0 auto;
                    font-size: 0.75rem /* FIX: minimum 12px agar terbaca di tablet */;
                    font-weight: 850;
                    letter-spacing: 0.035em;
                    padding: 0.34rem 0.58rem;
                    text-transform: uppercase;
                }

                .sna-v11-check-grid {
                    display: grid;
                    gap: 0.55rem;
                    grid-template-columns: repeat(3, minmax(0, 1fr));
                    margin: 0.75rem 0 0.9rem;
                }

                .sna-v11-check-item {
                    background: #101010;
                    border: 1px solid #292929;
                    border-radius: 10px;
                    color: #BDBDBD;
                    font-size: 0.75rem /* FIX: minimum 12px agar terbaca di tablet */;
                    line-height: 1.45;
                    padding: 0.68rem 0.72rem;
                }

                .sna-v11-check-item strong {
                    color: #FFFFFF;
                    display: block;
                    font-size: 0.75rem;
                    margin-bottom: 0.12rem;
                }

                .sna-v11-stage-shell {
                    background:
                        radial-gradient(circle at 0% 0%, rgba(229,57,53,0.14), transparent 24%),
                        radial-gradient(circle at 100% 0%, rgba(131,58,180,0.11), transparent 26%),
                        radial-gradient(circle at 100% 100%, rgba(29,161,242,0.10), transparent 28%),
                        linear-gradient(180deg, rgba(8,12,20,0.96) 0%, rgba(10,10,10,0.98) 100%);
                    border: 1px solid rgba(255,255,255,0.08);
                    border-radius: 20px;
                    box-shadow: 0 24px 60px rgba(0,0,0,0.34);
                    overflow: hidden;
                    padding: 0.15rem 0.15rem 0.35rem;
                    position: relative;
                    animation: snaV11Reveal 0.72s cubic-bezier(.2,.8,.2,1) both;
                }

                /* Fase 19 — spacing khusus header Graf Statis Akademik IndiBiz */
                .sna-v11-stage-shell > .sna-v9-section-head {
                    align-items: center;
                    margin-bottom: 0.9rem;
                    padding: 1.25rem 1.35rem 0;
                }

                .sna-v11-stage-shell > .sna-v9-section-head .sna-v9-section-title {
                    padding-left: 0.2rem;
                }

                .sna-v11-stage-shell > .sna-v9-section-head > .sna-v11-badge {
                    margin-right: 0.15rem;
                    margin-top: 0.05rem;
                }

                .sna-v11-stage-shell::before {
                    background: linear-gradient(90deg, rgba(229,57,53,0.0), rgba(229,57,53,0.88), rgba(29,161,242,0.68), rgba(131,58,180,0.72), rgba(229,57,53,0.0));
                    content: "";
                    height: 2px;
                    left: 0;
                    position: absolute;
                    right: 0;
                    top: 0;
                    animation: snaV11GlowLine 4.6s linear infinite;
                }

                .sna-v11-hero-row {
                    align-items: center;
                    display: flex;
                    flex-wrap: wrap;
                    gap: 0.55rem;
                    justify-content: space-between;
                    margin: 0.45rem 0 0.75rem;
                }

                .sna-v11-chip-row {
                    display: flex;
                    flex-wrap: wrap;
                    gap: 0.45rem;
                }

                .sna-v11-chip {
                    align-items: center;
                    background: rgba(255,255,255,0.06);
                    border: 1px solid rgba(255,255,255,0.10);
                    border-radius: 999px;
                    color: #D7D7D7;
                    display: inline-flex;
                    font-size: 0.75rem /* FIX: minimum 12px agar terbaca di tablet */;
                    font-weight: 760;
                    gap: 0.38rem;
                    padding: 0.34rem 0.62rem;
                    transition: transform .18s ease, box-shadow .18s ease, border-color .18s ease;
                }

                .sna-v11-chip:hover {
                    border-color: rgba(229,57,53,0.32);
                    box-shadow: 0 10px 22px rgba(0,0,0,0.22);
                    transform: translateY(-2px);
                }

                .sna-v11-chip-dot {
                    border-radius: 999px;
                    display: inline-flex;
                    height: 8px;
                    width: 8px;
                }

                .sna-v11-academic-note {
                    align-items: flex-start;
                    background:
                        linear-gradient(135deg, rgba(229,57,53,0.12), rgba(29,161,242,0.08)),
                        linear-gradient(180deg, rgba(20,20,20,0.9), rgba(12,12,12,0.96));
                    border: 1px solid rgba(229,57,53,0.26);
                    border-radius: 16px;
                    color: #D6D6D6;
                    display: flex;
                    gap: 0.85rem;
                    line-height: 1.6;
                    margin: 0.15rem 0 1rem;
                    overflow: hidden;
                    padding: 0.95rem 1rem;
                    position: relative;
                    transition: transform .18s ease, box-shadow .18s ease, border-color .18s ease;
                }

                .sna-v11-academic-note::after {
                    background: linear-gradient(180deg, rgba(229,57,53,0.9), rgba(29,161,242,0.45));
                    border-radius: 999px;
                    content: '';
                    height: 64px;
                    left: 0.75rem;
                    position: absolute;
                    top: 1rem;
                    width: 4px;
                }

                .sna-v11-academic-note:hover {
                    border-color: rgba(229,57,53,0.42);
                    box-shadow: 0 16px 32px rgba(0,0,0,0.26);
                    transform: translateY(-2px);
                }

                .sna-v11-academic-copy { padding-left: 0.15rem; }
                .sna-v11-academic-note strong { color: #FFFFFF; }

                .sna-v11-microcopy {
                    color: #9CA3AF;
                    font-size: 0.75rem /* FIX: minimum 12px agar terbaca di tablet */;
                    margin-top: 0.35rem;
                }

                .sna-v11-platform-grid {
                    display: grid;
                    gap: 0.7rem;
                    grid-template-columns: repeat(4, minmax(0, 1fr));
                    margin: 0.05rem 0 0.95rem;
                }

                .sna-v11-platform-card {
                    background: linear-gradient(180deg, rgba(18,18,18,0.96), rgba(12,12,12,0.96));
                    border: 1px solid rgba(255,255,255,0.08);
                    border-radius: 14px;
                    overflow: hidden;
                    padding: 0.82rem 0.88rem 0.9rem;
                    position: relative;
                    transition: transform .18s ease, border-color .18s ease, box-shadow .18s ease;
                    animation: snaV11Reveal 0.62s cubic-bezier(.2,.8,.2,1) both;
                }

                .sna-v11-platform-card:hover,
                .sna-v9-graph-kpi:hover,
                .sna-v11-check-item:hover {
                    border-color: rgba(229,57,53,0.28);
                    box-shadow: 0 16px 30px rgba(0,0,0,0.28);
                    transform: translateY(-3px);
                }

                .sna-v11-platform-card::before {
                    background: var(--platform-accent, #E53935);
                    content: '';
                    height: 3px;
                    left: 0;
                    position: absolute;
                    right: 0;
                    top: 0;
                }

                .sna-v11-platform-title {
                    align-items: center;
                    color: #FFFFFF;
                    display: flex;
                    font-size: 0.82rem;
                    font-weight: 780;
                    gap: 0.42rem;
                    justify-content: space-between;
                }

                .sna-v11-platform-count {
                    color: #FFFFFF;
                    display: block;
                    font-family: 'Plus Jakarta Sans', 'Inter', sans-serif;
                    font-size: 1.45rem;
                    font-weight: 800;
                    line-height: 1.05;
                    margin-top: 0.42rem;
                }

                .sna-v11-platform-note {
                    color: #A9A9A9;
                    display: block;
                    font-size: 0.75rem /* FIX: minimum 12px agar terbaca di tablet */;
                    margin-top: 0.18rem;
                }

                .sna-v11-platform-progress {
                    background: rgba(255,255,255,0.07);
                    border-radius: 999px;
                    height: 8px;
                    margin-top: 0.65rem;
                    overflow: hidden;
                }

                .sna-v11-platform-progress > span {
                    background: var(--platform-accent, #E53935);
                    border-radius: 999px;
                    display: block;
                    height: 100%;
                    box-shadow: 0 0 12px rgba(229,57,53,0.28);
                }

                .sna-v11-platform-share {
                    color: #D1D5DB;
                    display: block;
                    font-size: 0.75rem /* FIX: minimum 12px agar terbaca di tablet */;
                    margin-top: 0.38rem;
                }


                .sna-v9-graph-kpi {
                    transition: transform .18s ease, box-shadow .18s ease, border-color .18s ease;
                }

                .sna-v11-check-grid {
                    display: grid;
                    gap: 0.65rem;
                    grid-template-columns: repeat(3, minmax(0, 1fr));
                    margin: 0.75rem 0 0.95rem;
                }

                .sna-v11-check-item {
                    background: linear-gradient(180deg, rgba(17,17,17,0.98), rgba(11,11,11,0.98));
                    border: 1px solid rgba(255,255,255,0.08);
                    border-radius: 12px;
                    color: #C2C2C2;
                    font-size: 0.75rem /* FIX: minimum 12px agar terbaca di tablet */;
                    line-height: 1.48;
                    padding: 0.76rem 0.8rem;
                    position: relative;
                    transition: transform .18s ease, box-shadow .18s ease, border-color .18s ease;
                }

                .sna-v11-check-item::before {
                    background: linear-gradient(180deg, rgba(229,57,53,0.95), rgba(29,161,242,0.45));
                    border-radius: 999px;
                    content: '';
                    height: 34px;
                    left: 0.6rem;
                    position: absolute;
                    top: 0.78rem;
                    width: 3px;
                }

                .sna-v11-check-item strong {
                    color: #FFFFFF;
                    display: block;
                    font-size: 0.75rem;
                    margin-bottom: 0.12rem;
                    padding-left: 0.5rem;
                }

                .sna-v11-check-item span { display: block; padding-left: 0.5rem; }

                @keyframes snaV11Reveal {
                    from { opacity: 0; transform: translateY(14px); }
                    to { opacity: 1; transform: translateY(0); }
                }

                @keyframes snaV11GlowLine {
                    0% { transform: translateX(-40%); opacity: 0.15; }
                    50% { transform: translateX(0%); opacity: 0.95; }
                    100% { transform: translateX(40%); opacity: 0.15; }
                }

                @media (max-width: 1080px) {
                    .sna-v11-platform-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); }
                }

                @media (max-width: 900px) {
                    .sna-v11-check-grid,
                    .sna-v11-platform-grid { grid-template-columns: 1fr; }

                    .sna-v11-stage-shell > .sna-v9-section-head {
                        align-items: flex-start;
                        padding: 1rem 0.9rem 0;
                    }

                    .sna-v11-stage-shell > .sna-v9-section-head .sna-v9-section-title {
                        padding-left: 0;
                    }

                    .sna-v11-stage-shell > .sna-v9-section-head > .sna-v11-badge {
                        margin-right: 0;
                    }
                }

                @media (prefers-reduced-motion: reduce) {
                    .sna-v11-stage-shell,
                    .sna-v11-platform-card,
                    .sna-v9-graph-kpi,
                    .sna-v11-check-item {
                        animation: none !important;
                        transition: none !important;
                    }
                    .sna-v11-stage-shell::before { animation: none !important; }
                }

                /* Fase 19 — panel statistik IndiBiz interaktif dan beranimasi */
                .sna-v10-statistics-card {
                    background:
                        radial-gradient(circle at 7% 5%, rgba(229,57,53,0.13), transparent 24%),
                        radial-gradient(circle at 96% 94%, rgba(29,161,242,0.08), transparent 28%),
                        linear-gradient(180deg, #191919 0%, #101010 100%);
                    border: 1px solid rgba(255,255,255,0.09);
                    border-radius: 18px;
                    box-shadow: 0 24px 60px rgba(0,0,0,0.34);
                    isolation: isolate;
                    margin: 1.15rem 0;
                    overflow: hidden;
                    position: relative;
                    animation: snaV10Reveal 0.65s cubic-bezier(.2,.8,.2,1) both;
                }

                .sna-v10-statistics-card::before {
                    background: linear-gradient(90deg, transparent, rgba(229,57,53,0.76), rgba(29,161,242,0.55), transparent);
                    content: "";
                    height: 2px;
                    left: 0;
                    position: absolute;
                    right: 0;
                    top: 0;
                    z-index: 3;
                }

                .sna-v10-statistics-card::after {
                    background: radial-gradient(circle, rgba(229,57,53,0.12), transparent 68%);
                    content: "";
                    height: 240px;
                    pointer-events: none;
                    position: absolute;
                    right: -90px;
                    top: -120px;
                    width: 240px;
                    z-index: -1;
                }

                .sna-v10-statistics-head {
                    align-items: flex-start;
                    background:
                        radial-gradient(circle at 90% 15%, rgba(255,255,255,0.12), transparent 30%),
                        linear-gradient(135deg, #8E1717 0%, #B52828 48%, #D44141 100%);
                    border-bottom: 1px solid rgba(255,255,255,0.12);
                    display: flex;
                    gap: 1rem;
                    justify-content: space-between;
                    overflow: hidden;
                    padding: 1.1rem 1.2rem;
                    position: relative;
                }

                .sna-v10-statistics-head::after {
                    background: linear-gradient(105deg, transparent 30%, rgba(255,255,255,0.10) 48%, transparent 66%);
                    content: "";
                    inset: 0;
                    pointer-events: none;
                    position: absolute;
                    transform: translateX(-110%);
                    animation: snaV10HeaderSweep 5.8s ease-in-out infinite 1.2s;
                }

                .sna-v10-statistics-eyebrow {
                    align-items: center;
                    color: rgba(255,255,255,0.80);
                    display: inline-flex;
                    font-size: 0.75rem /* FIX: minimum 12px agar terbaca di tablet */;
                    font-weight: 800;
                    gap: 0.42rem;
                    letter-spacing: 0.08em;
                    margin-bottom: 0.35rem;
                    text-transform: uppercase;
                }

                .sna-v10-live-dot {
                    background: #7CFF9B;
                    border-radius: 50%;
                    box-shadow: 0 0 0 0 rgba(124,255,155,0.52);
                    display: inline-block;
                    height: 7px;
                    width: 7px;
                    animation: snaV10Pulse 2s ease-out infinite;
                }

                .sna-v10-statistics-title {
                    color: #FFFFFF;
                    font-family: 'Plus Jakarta Sans', 'Inter', sans-serif;
                    font-size: clamp(1.02rem, 2vw, 1.28rem);
                    font-weight: 900;
                    letter-spacing: -0.025em;
                    line-height: 1.15;
                    margin: 0;
                    position: relative;
                    z-index: 1;
                }

                .sna-v10-statistics-subtitle {
                    color: rgba(255,255,255,0.84);
                    font-size: 0.75rem /* FIX: minimum 12px agar terbaca di tablet */;
                    line-height: 1.55;
                    margin-top: 0.34rem;
                    max-width: 760px;
                    position: relative;
                    z-index: 1;
                }

                .sna-v10-statistics-badges {
                    align-items: flex-end;
                    display: flex;
                    flex: 0 0 auto;
                    flex-direction: column;
                    gap: 0.42rem;
                    position: relative;
                    z-index: 1;
                }

                .sna-v10-statistics-badge {
                    align-items: center;
                    backdrop-filter: blur(8px);
                    background: rgba(13,13,13,0.34);
                    border: 1px solid rgba(255,255,255,0.22);
                    border-radius: 999px;
                    color: #FFFFFF;
                    display: inline-flex;
                    font-size: 0.75rem /* FIX: minimum 12px agar terbaca di tablet */;
                    font-weight: 850;
                    gap: 0.38rem;
                    padding: 0.4rem 0.66rem;
                    white-space: nowrap;
                    transition: transform 180ms ease, background 180ms ease, border-color 180ms ease;
                }

                .sna-v10-statistics-badge:hover {
                    background: rgba(13,13,13,0.52);
                    border-color: rgba(255,255,255,0.42);
                    transform: translateY(-2px);
                }

                .sna-v10-statistics-badge--soft {
                    background: rgba(255,255,255,0.10);
                    color: rgba(255,255,255,0.84);
                    font-weight: 750;
                }

                .sna-v10-statistics-body { padding: 1.05rem; }

                .sna-v10-metric-grid {
                    display: grid;
                    gap: 0.72rem;
                    grid-template-columns: repeat(5, minmax(0, 1fr));
                    margin-bottom: 0.95rem;
                }

                .sna-v10-metric {
                    --metric-accent: #E53935;
                    --metric-glow: rgba(229,57,53,0.22);
                    background:
                        linear-gradient(145deg, rgba(255,255,255,0.035), transparent 56%),
                        #0E0E0E;
                    border: 1px solid #2B2B2B;
                    border-radius: 14px;
                    min-width: 0;
                    overflow: hidden;
                    padding: 0.78rem 0.82rem 0.72rem;
                    position: relative;
                    transform: translateY(0);
                    transition: border-color 200ms ease, box-shadow 200ms ease, transform 200ms ease;
                    animation: snaV10MetricIn 0.55s cubic-bezier(.2,.8,.2,1) both;
                    animation-delay: var(--metric-delay, 0ms);
                }

                .sna-v10-metric::before {
                    background: linear-gradient(180deg, var(--metric-accent), transparent 88%);
                    border-radius: 14px 0 0 14px;
                    bottom: 0;
                    content: "";
                    left: 0;
                    opacity: 0.92;
                    position: absolute;
                    top: 0;
                    width: 3px;
                }

                .sna-v10-metric::after {
                    background: radial-gradient(circle, var(--metric-glow), transparent 68%);
                    content: "";
                    height: 100px;
                    pointer-events: none;
                    position: absolute;
                    right: -42px;
                    top: -45px;
                    width: 100px;
                }

                .sna-v10-metric:hover {
                    border-color: color-mix(in srgb, var(--metric-accent) 48%, #2B2B2B);
                    box-shadow: 0 13px 28px var(--metric-glow);
                    transform: translateY(-5px);
                }

                .sna-v10-metric--node { --metric-accent: #1DA1F2; --metric-glow: rgba(29,161,242,0.20); }
                .sna-v10-metric--edge { --metric-accent: #E53935; --metric-glow: rgba(229,57,53,0.22); }
                .sna-v10-metric--density { --metric-accent: #FFB02E; --metric-glow: rgba(255,176,46,0.18); }
                .sna-v10-metric--in { --metric-accent: #9B5DE5; --metric-glow: rgba(155,93,229,0.20); }
                .sna-v10-metric--out { --metric-accent: #00D4C7; --metric-glow: rgba(0,212,199,0.18); }

                .sna-v10-metric-top {
                    align-items: center;
                    display: flex;
                    gap: 0.5rem;
                    justify-content: space-between;
                    position: relative;
                    z-index: 1;
                }

                .sna-v10-metric-label {
                    color: #959595;
                    display: block;
                    font-size: 0.75rem /* FIX: minimum 12px agar terbaca di tablet */;
                    font-weight: 850;
                    letter-spacing: 0.045em;
                    text-transform: uppercase;
                }

                .sna-v10-metric-icon {
                    align-items: center;
                    background: color-mix(in srgb, var(--metric-accent) 14%, transparent);
                    border: 1px solid color-mix(in srgb, var(--metric-accent) 34%, transparent);
                    border-radius: 9px;
                    color: var(--metric-accent);
                    display: inline-flex;
                    flex: 0 0 auto;
                    font-size: 0.75rem /* FIX: minimum 12px agar terbaca di tablet */;
                    font-weight: 900;
                    height: 26px;
                    justify-content: center;
                    width: 26px;
                    transition: transform 200ms ease;
                }

                .sna-v10-metric:hover .sna-v10-metric-icon { transform: rotate(-6deg) scale(1.08); }

                .sna-v10-metric-value {
                    color: #FFFFFF;
                    display: block;
                    font-family: 'Plus Jakarta Sans', 'Inter', sans-serif;
                    font-size: clamp(1.04rem, 1.8vw, 1.28rem);
                    font-weight: 900;
                    letter-spacing: -0.025em;
                    margin-top: 0.28rem;
                    overflow: hidden;
                    position: relative;
                    text-overflow: ellipsis;
                    white-space: nowrap;
                    z-index: 1;
                }

                .sna-v10-metric-hint {
                    color: #686868;
                    font-size: 0.75rem /* FIX: minimum 12px agar terbaca di tablet */;
                    line-height: 1.35;
                    margin-top: 0.14rem;
                    position: relative;
                    z-index: 1;
                }

                .sna-v10-table-grid {
                    /* Samakan tinggi kedua card berdasarkan card tertinggi pada baris ini. */
                    align-items: stretch;
                    display: grid;
                    gap: 0.9rem;
                    grid-template-columns: repeat(2, minmax(0, 1fr));
                }

                .sna-v10-table-card {
                    --table-accent: #E53935;
                    --table-glow: rgba(229,57,53,0.14);
                    background: rgba(12,12,12,0.96);
                    border: 1px solid #2A2A2A;
                    border-radius: 14px;
                    box-shadow: 0 10px 26px rgba(0,0,0,0.18);
                    overflow: hidden;
                    position: relative;
                    transition: border-color 220ms ease, box-shadow 220ms ease, transform 220ms ease;
                    animation: snaV10TableIn 0.62s cubic-bezier(.2,.8,.2,1) both;
                }

                .sna-v10-table-card--followers {
                    --table-accent: #9B5DE5;
                    --table-glow: rgba(155,93,229,0.14);
                    animation-delay: 90ms;
                }

                .sna-v10-table-card:hover {
                    border-color: color-mix(in srgb, var(--table-accent) 45%, #2A2A2A);
                    box-shadow: 0 18px 38px var(--table-glow);
                    transform: translateY(-3px);
                }

                .sna-v10-table-head {
                    align-items: flex-start;
                    background:
                        radial-gradient(circle at 98% 0%, var(--table-glow), transparent 38%),
                        linear-gradient(135deg, color-mix(in srgb, var(--table-accent) 11%, transparent), rgba(255,255,255,0.012));
                    border-bottom: 1px solid #252525;
                    display: flex;
                    gap: 0.7rem;
                    justify-content: space-between;
                    padding: 0.82rem 0.88rem;
                }

                .sna-v10-table-heading {
                    align-items: flex-start;
                    display: flex;
                    gap: 0.62rem;
                    min-width: 0;
                }

                .sna-v10-table-icon {
                    align-items: center;
                    background: color-mix(in srgb, var(--table-accent) 15%, transparent);
                    border: 1px solid color-mix(in srgb, var(--table-accent) 32%, transparent);
                    border-radius: 10px;
                    color: var(--table-accent);
                    display: inline-flex;
                    flex: 0 0 auto;
                    font-size: 0.75rem /* FIX: minimum 12px agar terbaca di tablet */;
                    font-weight: 900;
                    height: 30px;
                    justify-content: center;
                    width: 30px;
                }

                .sna-v10-table-title {
                    color: #FFFFFF;
                    font-size: 0.82rem;
                    font-weight: 850;
                    line-height: 1.25;
                }

                .sna-v10-table-note {
                    color: #858585;
                    font-size: 0.75rem /* FIX: minimum 12px agar terbaca di tablet */;
                    line-height: 1.45;
                    margin-top: 0.18rem;
                }

                .sna-v10-table-badge {
                    background: color-mix(in srgb, var(--table-accent) 12%, transparent);
                    border: 1px solid color-mix(in srgb, var(--table-accent) 30%, transparent);
                    border-radius: 999px;
                    color: color-mix(in srgb, var(--table-accent) 78%, white);
                    flex: 0 0 auto;
                    font-size: 0.75rem /* FIX: minimum 12px agar terbaca di tablet */;
                    font-weight: 850;
                    padding: 0.3rem 0.48rem;
                    text-transform: uppercase;
                    white-space: nowrap;
                }

                /*
                 * Tabel ranking IndiBiz dibuat memakai grid pada setiap baris.
                 * Ini menghindari intrinsic sizing tabel Markdown/Streamlit yang
                 * sebelumnya menyisakan ruang kosong di sisi kanan card.
                 */
                .sna-v10-table-scroll {
                    box-sizing: border-box;
                    display: block !important;
                    max-width: none !important;
                    overflow-x: auto;
                    width: 100% !important;
                }

                table.sna-v10-table {
                    border-collapse: separate;
                    border-spacing: 0;
                    box-sizing: border-box;
                    color: #FFFFFF;
                    display: block !important;
                    font-size: 0.75rem /* FIX: minimum 12px agar terbaca di tablet */;
                    max-width: none !important;
                    min-width: 0 !important;
                    table-layout: auto;
                    width: 100% !important;
                }

                .sna-v10-table thead,
                .sna-v10-table tbody {
                    display: block;
                    width: 100%;
                }

                .sna-v10-table thead tr,
                .sna-v10-table tbody tr {
                    display: grid;
                    grid-template-columns: 15% 43% 42%;
                    width: 100%;
                }

                .sna-v10-table th,
                .sna-v10-table td {
                    box-sizing: border-box;
                    min-width: 0;
                    width: auto !important;
                }

                .sna-v10-table th {
                    background: #151515;
                    border-bottom: 1px solid #292929;
                    color: #909090;
                    font-size: 0.75rem /* FIX: minimum 12px agar terbaca di tablet */;
                    font-weight: 850;
                    letter-spacing: 0.04em;
                    padding: 0.58rem 0.66rem;
                    text-align: left;
                    text-transform: uppercase;
                    white-space: nowrap;
                }

                .sna-v10-table td {
                    border-bottom: 1px solid #202020;
                    padding: 0.52rem 0.66rem;
                    position: relative;
                    white-space: nowrap;
                }

                .sna-v10-table tr:last-child td { border-bottom: 0; }

                .sna-v10-table tbody tr {
                    animation: snaV10RowIn 0.42s ease both;
                    animation-delay: var(--row-delay, 0ms);
                    transition: background 160ms ease, transform 160ms ease;
                }

                .sna-v10-table tbody tr:hover {
                    background: color-mix(in srgb, var(--table-accent) 8%, transparent);
                    transform: translateX(3px);
                }

                .sna-v10-table tbody tr:hover td:first-child::before {
                    background: var(--table-accent);
                    bottom: 5px;
                    content: "";
                    left: 0;
                    position: absolute;
                    top: 5px;
                    width: 2px;
                }

                .sna-v10-rank-chip {
                    align-items: center;
                    background: rgba(229,57,53,0.10);
                    border: 1px solid rgba(229,57,53,0.20);
                    border-radius: 8px;
                    color: #FF615E;
                    display: inline-flex;
                    font-size: 0.75rem /* FIX: minimum 12px agar terbaca di tablet */;
                    font-weight: 900;
                    justify-content: center;
                    min-width: 31px;
                    padding: 0.22rem 0.34rem;
                }

                .sna-v10-rank-row--1 .sna-v10-rank-chip {
                    background: linear-gradient(135deg, rgba(255,193,7,0.22), rgba(255,152,0,0.10));
                    border-color: rgba(255,193,7,0.38);
                    color: #FFD45A;
                    box-shadow: 0 0 16px rgba(255,193,7,0.10);
                }

                .sna-v10-rank-row--2 .sna-v10-rank-chip {
                    background: rgba(210,220,230,0.14);
                    border-color: rgba(210,220,230,0.27);
                    color: #DDE6EF;
                }

                .sna-v10-rank-row--3 .sna-v10-rank-chip {
                    background: rgba(205,127,50,0.15);
                    border-color: rgba(205,127,50,0.30);
                    color: #E5A267;
                }

                .sna-v10-table-username {
                    color: #FFFFFF;
                    font-weight: 800;
                    max-width: 220px;
                    overflow: hidden;
                    text-overflow: ellipsis;
                }

                .sna-v10-account-wrap {
                    align-items: center;
                    display: inline-flex;
                    gap: 0.48rem;
                    max-width: 100%;
                }

                .sna-v10-account-avatar {
                    align-items: center;
                    background: color-mix(in srgb, var(--table-accent) 13%, #151515);
                    border: 1px solid color-mix(in srgb, var(--table-accent) 24%, #2A2A2A);
                    border-radius: 50%;
                    color: color-mix(in srgb, var(--table-accent) 72%, white);
                    display: inline-flex;
                    flex: 0 0 auto;
                    font-size: 0.75rem /* FIX: minimum 12px agar terbaca di tablet */;
                    font-weight: 900;
                    height: 25px;
                    justify-content: center;
                    text-transform: uppercase;
                    width: 25px;
                }

                .sna-v10-table-number {
                    color: #E2E2E2;
                    font-variant-numeric: tabular-nums;
                    text-align: right;
                }

                .sna-v10-number-wrap {
                    align-items: flex-end;
                    display: flex;
                    flex-direction: column;
                    gap: 0.24rem;
                }

                .sna-v10-mini-track {
                    background: #242424;
                    border-radius: 999px;
                    height: 3px;
                    overflow: hidden;
                    width: min(92px, 100%);
                }

                .sna-v10-mini-bar {
                    background: linear-gradient(90deg, var(--table-accent), color-mix(in srgb, var(--table-accent) 55%, white));
                    border-radius: inherit;
                    display: block;
                    height: 100%;
                    transform-origin: left center;
                    width: var(--bar-width, 0%);
                    animation: snaV10BarGrow 0.9s cubic-bezier(.2,.8,.2,1) both;
                    animation-delay: calc(var(--row-delay, 0ms) + 180ms);
                }

                .sna-v10-interpretation {
                    background:
                        linear-gradient(135deg, rgba(229,57,53,0.08), rgba(29,161,242,0.04)),
                        #111111;
                    border: 1px solid rgba(229,57,53,0.24);
                    border-radius: 12px;
                    color: #BDBDBD;
                    margin-top: 0.9rem;
                    overflow: hidden;
                    transition: border-color 180ms ease, box-shadow 180ms ease;
                }

                .sna-v10-interpretation:hover {
                    border-color: rgba(229,57,53,0.42);
                    box-shadow: 0 10px 26px rgba(229,57,53,0.08);
                }

                .sna-v10-interpretation summary {
                    align-items: center;
                    cursor: pointer;
                    display: flex;
                    gap: 0.7rem;
                    justify-content: space-between;
                    list-style: none;
                    padding: 0.76rem 0.84rem;
                    user-select: none;
                }

                .sna-v10-interpretation summary::-webkit-details-marker { display: none; }

                .sna-v10-interpretation-title {
                    align-items: center;
                    color: #FFFFFF;
                    display: inline-flex;
                    font-size: 0.75rem /* FIX: minimum 12px agar terbaca di tablet */;
                    font-weight: 850;
                    gap: 0.48rem;
                }

                .sna-v10-interpretation-icon {
                    align-items: center;
                    background: rgba(229,57,53,0.14);
                    border: 1px solid rgba(229,57,53,0.28);
                    border-radius: 8px;
                    color: #FF6865;
                    display: inline-flex;
                    height: 26px;
                    justify-content: center;
                    width: 26px;
                }

                .sna-v10-interpretation-chevron {
                    color: #8F8F8F;
                    display: inline-block;
                    font-size: 0.82rem;
                    transition: transform 180ms ease;
                }

                .sna-v10-interpretation[open] .sna-v10-interpretation-chevron { transform: rotate(180deg); }

                .sna-v10-interpretation-content {
                    border-top: 1px solid rgba(255,255,255,0.06);
                    font-size: 0.75rem /* FIX: minimum 12px agar terbaca di tablet */;
                    line-height: 1.58;
                    padding: 0.72rem 0.84rem 0.82rem;
                    animation: snaV10DetailsOpen 0.28s ease both;
                }

                .sna-v10-interpretation-content p { margin: 0; }
                .sna-v10-interpretation-content strong { color: #FFFFFF; }

                .sna-v10-insight-chips {
                    display: flex;
                    flex-wrap: wrap;
                    gap: 0.42rem;
                    margin-top: 0.62rem;
                }

                .sna-v10-insight-chip {
                    background: rgba(255,255,255,0.035);
                    border: 1px solid rgba(255,255,255,0.09);
                    border-radius: 999px;
                    color: #AFAFAF;
                    font-size: 0.75rem /* FIX: minimum 12px agar terbaca di tablet */;
                    font-weight: 750;
                    padding: 0.28rem 0.48rem;
                    transition: background 160ms ease, border-color 160ms ease, color 160ms ease, transform 160ms ease;
                }

                .sna-v10-insight-chip:hover {
                    background: rgba(229,57,53,0.10);
                    border-color: rgba(229,57,53,0.28);
                    color: #FFFFFF;
                    transform: translateY(-2px);
                }

                @keyframes snaV10Reveal {
                    from { opacity: 0; transform: translateY(14px); }
                    to { opacity: 1; transform: translateY(0); }
                }

                @keyframes snaV10MetricIn {
                    from { opacity: 0; transform: translateY(13px) scale(0.985); }
                    to { opacity: 1; transform: translateY(0) scale(1); }
                }

                @keyframes snaV10TableIn {
                    from { opacity: 0; transform: translateY(16px); }
                    to { opacity: 1; transform: translateY(0); }
                }

                @keyframes snaV10RowIn {
                    from { opacity: 0; transform: translateX(-8px); }
                    to { opacity: 1; transform: translateX(0); }
                }

                @keyframes snaV10BarGrow {
                    from { transform: scaleX(0); }
                    to { transform: scaleX(1); }
                }

                @keyframes snaV10Pulse {
                    0% { box-shadow: 0 0 0 0 rgba(124,255,155,0.48); }
                    65% { box-shadow: 0 0 0 7px rgba(124,255,155,0); }
                    100% { box-shadow: 0 0 0 0 rgba(124,255,155,0); }
                }

                @keyframes snaV10HeaderSweep {
                    0%, 72% { transform: translateX(-110%); }
                    88%, 100% { transform: translateX(110%); }
                }

                @keyframes snaV10DetailsOpen {
                    from { opacity: 0; transform: translateY(-4px); }
                    to { opacity: 1; transform: translateY(0); }
                }

                @media (max-width: 1200px) {
                    .sna-v10-metric-grid { grid-template-columns: repeat(3, minmax(0, 1fr)); }
                }

                @media (max-width: 900px) {
                    .sna-v10-table-grid { grid-template-columns: 1fr; }
                }

                @media (max-width: 640px) {
                    .sna-v10-statistics-head { flex-direction: column; }
                    .sna-v10-statistics-badges { align-items: flex-start; flex-direction: row; flex-wrap: wrap; }
                    .sna-v10-metric-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); }
                    .sna-v10-table-head { flex-direction: column; }
                }

                @media (prefers-reduced-motion: reduce) {
                    .sna-v10-statistics-card,
                    .sna-v10-statistics-head::after,
                    .sna-v10-live-dot,
                    .sna-v10-metric,
                    .sna-v10-table-card,
                    .sna-v10-table tbody tr,
                    .sna-v10-mini-bar,
                    .sna-v10-interpretation-content {
                        animation: none !important;
                        transition: none !important;
                    }
                }

                @media (max-width: 1100px) {
                    .sna-v9-stat-row { grid-template-columns: repeat(2, minmax(0, 1fr)); }
                    .sna-v9-graph-kpi-grid { grid-template-columns: 1fr; }
                }

                @media (max-width: 720px) {
                    .sna-v9-hero { padding: 1.35rem 1.15rem; }
                    .sna-v9-stat-row { grid-template-columns: 1fr; }
                    .sna-v9-interaction-strip { align-items: flex-start; flex-direction: column; }
                }


                /* Fase 8 v1.3 — pemulihan visual Graf Statis Akademik IndiBiz */
                .sna-v13-indibiz-static-marker { display: none; }

                div[data-testid="stVerticalBlockBorderWrapper"]:has(.sna-v13-indibiz-static-marker) {
                    background:
                        radial-gradient(circle at 8% 4%, rgba(29,161,242,0.10), transparent 24%),
                        radial-gradient(circle at 92% 8%, rgba(131,58,180,0.10), transparent 25%),
                        radial-gradient(circle at 82% 92%, rgba(37,244,238,0.07), transparent 25%),
                        linear-gradient(180deg, #111722 0%, #0B1018 100%) !important;
                    border: 1px solid rgba(148,163,184,0.22) !important;
                    border-radius: 18px !important;
                    box-shadow: 0 22px 56px rgba(0,0,0,0.34), inset 0 1px 0 rgba(255,255,255,0.025);
                    overflow: hidden;
                    padding: 1.15rem !important;
                }

                .sna-v13-static-head {
                    align-items: flex-start;
                    display: flex;
                    gap: 1rem;
                    justify-content: space-between;
                    margin-bottom: 0.75rem;
                }

                .sna-v13-static-title {
                    color: #F8FAFC !important;
                    font-family: 'Plus Jakarta Sans', 'Inter', sans-serif;
                    font-size: clamp(1.35rem, 2.4vw, 2rem);
                    font-weight: 800;
                    letter-spacing: -0.035em;
                    line-height: 1.2;
                    margin: 0;
                }

                .sna-v13-static-subtitle {
                    color: #AEB7C5 !important;
                    font-size: 0.88rem;
                    line-height: 1.55;
                    margin: 0.5rem 0 0;
                    max-width: 880px;
                }

                .sna-v13-static-badge {
                    align-items: center;
                    background: linear-gradient(135deg, rgba(229,57,53,0.18), rgba(229,57,53,0.08));
                    border: 1px solid rgba(229,57,53,0.42);
                    border-radius: 999px;
                    color: #FFAAA7;
                    display: inline-flex;
                    flex: 0 0 auto;
                    font-size: 0.75rem /* FIX: minimum 12px agar terbaca di tablet */;
                    font-weight: 800;
                    letter-spacing: 0.055em;
                    padding: 0.42rem 0.68rem;
                    text-transform: uppercase;
                }

                .sna-v13-static-guide {
                    display: grid;
                    gap: 0.55rem;
                    grid-template-columns: repeat(3, minmax(0, 1fr));
                    margin: 0.85rem 0 0.9rem;
                }

                .sna-v13-guide-item {
                    align-items: center;
                    background: rgba(255,255,255,0.035);
                    border: 1px solid rgba(148,163,184,0.15);
                    border-radius: 11px;
                    color: #B8C1CE;
                    display: flex;
                    font-size: 0.75rem /* FIX: minimum 12px agar terbaca di tablet */;
                    gap: 0.55rem;
                    line-height: 1.4;
                    padding: 0.68rem 0.74rem;
                    transition: border-color 180ms ease, transform 180ms ease, background 180ms ease;
                }

                .sna-v13-guide-item:hover {
                    background: rgba(255,255,255,0.055);
                    border-color: rgba(229,57,53,0.35);
                    transform: translateY(-2px);
                }

                .sna-v13-guide-icon {
                    align-items: center;
                    border-radius: 8px;
                    display: inline-flex;
                    flex: 0 0 28px;
                    font-size: 0.8rem;
                    height: 28px;
                    justify-content: center;
                }

                .sna-v13-static-kpis {
                    display: grid;
                    gap: 0.55rem;
                    grid-template-columns: repeat(4, minmax(0, 1fr));
                    margin: 0.2rem 0 0.85rem;
                }

                .sna-v13-static-kpi {
                    background: rgba(6,10,17,0.62);
                    border: 1px solid rgba(148,163,184,0.14);
                    border-radius: 11px;
                    padding: 0.7rem 0.75rem;
                }

                .sna-v13-static-kpi span { display: block; }
                .sna-v13-static-kpi-label {
                    color: #7F8A9A;
                    font-size: 0.75rem /* FIX: minimum 12px agar terbaca di tablet */;
                    font-weight: 750;
                    letter-spacing: 0.05em;
                    text-transform: uppercase;
                }
                .sna-v13-static-kpi-value {
                    color: #F8FAFC;
                    font-family: 'Plus Jakarta Sans', 'Inter', sans-serif;
                    font-size: 1.05rem;
                    font-weight: 800;
                    margin-top: 0.2rem;
                    overflow: hidden;
                    text-overflow: ellipsis;
                    white-space: nowrap;
                }

                div[data-testid="stVerticalBlockBorderWrapper"]:has(.sna-v13-indibiz-static-marker)
                div[data-testid="stPlotlyChart"] {
                    background:
                        radial-gradient(circle at 50% 48%, rgba(229,57,53,0.055), transparent 22%),
                        linear-gradient(180deg, rgba(11,17,27,0.88), rgba(8,13,21,0.96));
                    border: 1px solid rgba(148,163,184,0.16);
                    border-radius: 15px;
                    overflow: hidden;
                    padding: 0.2rem;
                }

                @media (max-width: 900px) {
                    .sna-v13-static-guide { grid-template-columns: 1fr; }
                    .sna-v13-static-kpis { grid-template-columns: repeat(2, minmax(0, 1fr)); }
                    .sna-v13-static-head { flex-direction: column; }
                }

            </style>
            """,
            unsafe_allow_html=True,
        )
    except Exception as exc:
        st.error(f"Gagal menyisipkan CSS halaman SNA: {exc}")



def _inject_sna_light_mode_patch() -> None:
    """Selaraskan komponen SNA dengan light theme tanpa mengubah dark theme."""
    try:
        if bool(st.session_state.get("dark_mode", False)):
            return

        st.markdown(
            """
            <style>
                /* Patch light theme khusus halaman Social Network Analysis. */
                html body:has(.sna-v9-page) div[data-testid="stAppViewContainer"] {
                    background: #F5F7FA !important;
                }

                html body:has(.sna-v9-page) div[data-testid="stAppViewContainer"] .main .block-container {
                    color: #1F2937 !important;
                }

                /* Hero light mode: merah tetap kuat, tetapi lebih hidup dan kontras. */
                html body:has(.sna-v9-page) .sna-v9-hero {
                    background:
                        radial-gradient(circle at 88% 8%, rgba(255,255,255,0.24) 0%, rgba(255,255,255,0) 34%),
                        radial-gradient(circle at 8% 100%, rgba(255,179,153,0.16) 0%, rgba(255,179,153,0) 38%),
                        linear-gradient(120deg, #B91C1C 0%, #D92525 34%, #EF3E3E 68%, #F46B68 100%) !important;
                    border-color: rgba(185, 28, 28, 0.18) !important;
                    box-shadow: 0 16px 36px rgba(185, 28, 28, 0.17), 0 3px 10px rgba(15, 23, 42, 0.06) !important;
                }

                html body:has(.sna-v9-page) .sna-v9-hero::after {
                    background: radial-gradient(circle, rgba(255,255,255,0.20), transparent 68%) !important;
                }

                html body:has(.sna-v9-page) .sna-v9-hero h1 {
                    color: #FFFFFF !important;
                    text-shadow: 0 2px 10px rgba(90, 10, 10, 0.16);
                }

                html body:has(.sna-v9-page) .sna-v9-hero p {
                    color: rgba(255,255,255,0.96) !important;
                    text-shadow: 0 1px 5px rgba(90, 10, 10, 0.10);
                }

                html body:has(.sna-v9-page) .sna-v9-hero .sna-v9-badge {
                    color: #FFFFFF !important;
                    border-color: rgba(255,255,255,0.32) !important;
                    box-shadow: inset 0 1px 0 rgba(255,255,255,0.08);
                }

                html body:has(.sna-v9-page) .sna-v9-hero .sna-v9-badge-glass {
                    background: rgba(117, 20, 24, 0.28) !important;
                }

                html body:has(.sna-v9-page) .sna-v9-hero .sna-v9-badge-real {
                    background: rgba(22, 101, 52, 0.86) !important;
                    border-color: rgba(187, 247, 208, 0.48) !important;
                }

                html body:has(.sna-v9-page) .sna-v9-hero .sna-v9-badge-dummy {
                    background: rgba(180, 83, 9, 0.86) !important;
                    border-color: rgba(254, 215, 170, 0.50) !important;
                }

                /* Permukaan utama dan section. */
                html body:has(.sna-v9-page) .sna-v9-card,
                html body:has(.sna-v9-page) div[data-testid="stVerticalBlockBorderWrapper"]:has(.sna-v9-card-marker),
                html body:has(.sna-v9-page) div[data-testid="stVerticalBlockBorderWrapper"]:has(.sna-v9-control-marker),
                html body:has(.sna-v9-page) div[data-testid="stVerticalBlockBorderWrapper"]:has(.sna-v9-section-marker),
                html body:has(.sna-v9-page) div[data-testid="stVerticalBlockBorderWrapper"]:has(.sna-v9-graph-marker) {
                    background: #FFFFFF !important;
                    border-color: #D8E0EA !important;
                    box-shadow: 0 10px 26px rgba(15, 23, 42, 0.07) !important;
                }

                html body:has(.sna-v9-page) .sna-v9-stat {
                    background: linear-gradient(145deg, #FFFFFF, #F8FAFC) !important;
                    border-color: #D8E0EA !important;
                    border-left-color: #E53935 !important;
                    box-shadow: 0 7px 18px rgba(15, 23, 42, 0.05) !important;
                }

                html body:has(.sna-v9-page) .sna-v9-stat:hover,
                html body:has(.sna-v9-page) .sna-v9-card:hover,
                html body:has(.sna-v9-page) div[data-testid="stVerticalBlockBorderWrapper"]:has(.sna-v9-section-marker):hover,
                html body:has(.sna-v9-page) div[data-testid="stVerticalBlockBorderWrapper"]:has(.sna-v9-graph-marker):hover {
                    border-color: rgba(229,57,53,0.50) !important;
                    box-shadow: 0 12px 28px rgba(15,23,42,0.09), 0 0 0 1px rgba(229,57,53,0.08) !important;
                }

                html body:has(.sna-v9-page) .sna-v9-section-title,
                html body:has(.sna-v9-page) .sna-v9-influencer-mini-value,
                html body:has(.sna-v9-page) .sna-v9-influencer-table-title,
                html body:has(.sna-v9-page) .sna-v9-detail-title,
                html body:has(.sna-v9-page) .sna-v9-detail-value,
                html body:has(.sna-v9-page) .sna-v9-graph-kpi-value,
                html body:has(.sna-v9-page) .sna-v11-academic-note strong,
                html body:has(.sna-v9-page) .sna-v11-check-item strong,
                html body:has(.sna-v9-page) .sna-v13-static-title,
                html body:has(.sna-v9-page) .sna-v13-static-kpi-value {
                    color: #1F2937 !important;
                }

                html body:has(.sna-v9-page) .sna-v9-section-subtitle,
                html body:has(.sna-v9-page) .sna-v9-stat-label,
                html body:has(.sna-v9-page) .sna-v9-stat-note,
                html body:has(.sna-v9-page) .sna-v9-influencer-mini-label,
                html body:has(.sna-v9-page) .sna-v9-influencer-mini-note,
                html body:has(.sna-v9-page) .sna-v9-influencer-table-subtitle,
                html body:has(.sna-v9-page) .sna-v9-detail-subtitle,
                html body:has(.sna-v9-page) .sna-v9-detail-label,
                html body:has(.sna-v9-page) .sna-v9-detail-hint,
                html body:has(.sna-v9-page) .sna-v9-graph-kpi-label,
                html body:has(.sna-v9-page) .sna-v9-graph-kpi-note,
                html body:has(.sna-v9-page) .sna-v11-microcopy,
                html body:has(.sna-v9-page) .sna-v13-static-subtitle,
                html body:has(.sna-v9-page) .sna-v13-static-kpi-label {
                    color: #64748B !important;
                }

                /* Patch light mode panel Statistik Network Analysis IndiBiz. */
                html body:has(.sna-v9-page) .sna-v10-statistics-card {
                    background:
                        radial-gradient(circle at 7% 5%, rgba(229,57,53,0.06), transparent 24%),
                        radial-gradient(circle at 96% 94%, rgba(29,161,242,0.05), transparent 28%),
                        linear-gradient(180deg, #FFFFFF 0%, #F8FAFC 100%) !important;
                    border-color: #D8E0EA !important;
                    box-shadow: 0 16px 36px rgba(15,23,42,0.09) !important;
                }

                html body:has(.sna-v9-page) .sna-v10-statistics-body {
                    background: transparent !important;
                    color: #1F2937 !important;
                }

                /* Header merah dipertahankan, teks dipaksa tetap putih di light mode. */
                html body:has(.sna-v9-page) .sna-v10-statistics-head {
                    background:
                        radial-gradient(circle at 90% 15%, rgba(255,255,255,0.16), transparent 30%),
                        linear-gradient(135deg, #A71919 0%, #C52D2D 48%, #E25555 100%) !important;
                    border-bottom-color: rgba(127,29,29,0.16) !important;
                }

                html body:has(.sna-v9-page) .sna-v10-statistics-eyebrow,
                html body:has(.sna-v9-page) .sna-v10-statistics-title,
                html body:has(.sna-v9-page) .sna-v10-statistics-subtitle,
                html body:has(.sna-v9-page) .sna-v10-statistics-head h1,
                html body:has(.sna-v9-page) .sna-v10-statistics-head h2,
                html body:has(.sna-v9-page) .sna-v10-statistics-head h3,
                html body:has(.sna-v9-page) .sna-v10-statistics-head p,
                html body:has(.sna-v9-page) .sna-v10-statistics-badge,
                html body:has(.sna-v9-page) .sna-v10-statistics-badge--soft {
                    color: #FFFFFF !important;
                    -webkit-text-fill-color: #FFFFFF !important;
                }

                html body:has(.sna-v9-page) .sna-v10-statistics-badge {
                    background: rgba(92,16,18,0.34) !important;
                    border-color: rgba(255,255,255,0.32) !important;
                }

                html body:has(.sna-v9-page) .sna-v10-statistics-badge--soft {
                    background: rgba(255,255,255,0.12) !important;
                }

                /* Lima kartu KPI. */
                html body:has(.sna-v9-page) .sna-v10-metric {
                    background:
                        linear-gradient(145deg, rgba(255,255,255,0.92), rgba(248,250,252,0.94)) !important;
                    border-color: #D8E0EA !important;
                    box-shadow: 0 7px 18px rgba(15,23,42,0.05) !important;
                }

                html body:has(.sna-v9-page) .sna-v10-metric:hover {
                    border-color: color-mix(in srgb, var(--metric-accent) 46%, #CBD5E1) !important;
                    box-shadow: 0 13px 28px color-mix(in srgb, var(--metric-accent) 14%, transparent) !important;
                }

                html body:has(.sna-v9-page) .sna-v10-metric-label {
                    color: #64748B !important;
                }

                html body:has(.sna-v9-page) .sna-v10-metric-value {
                    color: #1F2937 !important;
                    -webkit-text-fill-color: #1F2937 !important;
                }

                html body:has(.sna-v9-page) .sna-v10-metric-hint {
                    color: #94A3B8 !important;
                }

                html body:has(.sna-v9-page) .sna-v10-metric-icon {
                    background: color-mix(in srgb, var(--metric-accent) 10%, #FFFFFF) !important;
                    border-color: color-mix(in srgb, var(--metric-accent) 30%, #D8E0EA) !important;
                }

                /* Dua tabel ranking IndiBiz. */
                html body:has(.sna-v9-page) .sna-v10-table-card {
                    background: #FFFFFF !important;
                    border-color: #D8E0EA !important;
                    box-shadow: 0 9px 24px rgba(15,23,42,0.06) !important;
                }

                html body:has(.sna-v9-page) .sna-v10-table-card:hover {
                    border-color: color-mix(in srgb, var(--table-accent) 38%, #CBD5E1) !important;
                    box-shadow: 0 16px 34px color-mix(in srgb, var(--table-accent) 10%, rgba(15,23,42,0.08)) !important;
                }

                html body:has(.sna-v9-page) .sna-v10-table-head {
                    background:
                        radial-gradient(circle at 98% 0%, var(--table-glow), transparent 38%),
                        linear-gradient(135deg, color-mix(in srgb, var(--table-accent) 6%, #FFFFFF), #F8FAFC) !important;
                    border-bottom-color: #E2E8F0 !important;
                }

                html body:has(.sna-v9-page) .sna-v10-table-title,
                html body:has(.sna-v9-page) .sna-v10-table-username {
                    color: #1F2937 !important;
                    -webkit-text-fill-color: #1F2937 !important;
                }

                html body:has(.sna-v9-page) .sna-v10-table-note {
                    color: #64748B !important;
                }

                html body:has(.sna-v9-page) .sna-v10-table-badge {
                    background: color-mix(in srgb, var(--table-accent) 8%, #FFFFFF) !important;
                    border-color: color-mix(in srgb, var(--table-accent) 28%, #D8E0EA) !important;
                    color: color-mix(in srgb, var(--table-accent) 84%, #1F2937) !important;
                }

                html body:has(.sna-v9-page) table.sna-v10-table {
                    background: #FFFFFF !important;
                    color: #1F2937 !important;
                }

                html body:has(.sna-v9-page) .sna-v10-table th {
                    background: #F1F5F9 !important;
                    border-bottom-color: #D8E0EA !important;
                    color: #64748B !important;
                    -webkit-text-fill-color: #64748B !important;
                }

                html body:has(.sna-v9-page) .sna-v10-table td {
                    background: transparent !important;
                    border-bottom-color: #E8EDF3 !important;
                    color: #334155 !important;
                    -webkit-text-fill-color: #334155 !important;
                }

                html body:has(.sna-v9-page) .sna-v10-table tbody tr:hover {
                    background: color-mix(in srgb, var(--table-accent) 6%, #F8FAFC) !important;
                }

                html body:has(.sna-v9-page) .sna-v10-table-number {
                    color: #334155 !important;
                    -webkit-text-fill-color: #334155 !important;
                }

                html body:has(.sna-v9-page) .sna-v10-account-avatar {
                    background: color-mix(in srgb, var(--table-accent) 9%, #FFFFFF) !important;
                    border-color: color-mix(in srgb, var(--table-accent) 24%, #D8E0EA) !important;
                }

                html body:has(.sna-v9-page) .sna-v10-mini-track {
                    background: #E2E8F0 !important;
                }

                html body:has(.sna-v9-page) .sna-v10-rank-row--2 .sna-v10-rank-chip {
                    background: #F1F5F9 !important;
                    border-color: #CBD5E1 !important;
                    color: #475569 !important;
                }

                html body:has(.sna-v9-page) .sna-v10-rank-row--3 .sna-v10-rank-chip {
                    background: #FFF7ED !important;
                    border-color: #FED7AA !important;
                    color: #9A4F12 !important;
                }

                /* Panel Cara membaca hasil analisis. */
                html body:has(.sna-v9-page) .sna-v10-interpretation {
                    background:
                        linear-gradient(135deg, rgba(229,57,53,0.045), rgba(29,161,242,0.035)),
                        #FFFFFF !important;
                    border-color: #E1CBD0 !important;
                    color: #475569 !important;
                    box-shadow: 0 6px 16px rgba(15,23,42,0.04) !important;
                }

                html body:has(.sna-v9-page) .sna-v10-interpretation:hover {
                    border-color: rgba(229,57,53,0.36) !important;
                    box-shadow: 0 10px 24px rgba(15,23,42,0.07) !important;
                }

                html body:has(.sna-v9-page) .sna-v10-interpretation-title,
                html body:has(.sna-v9-page) .sna-v10-interpretation-content strong {
                    color: #1F2937 !important;
                    -webkit-text-fill-color: #1F2937 !important;
                }

                html body:has(.sna-v9-page) .sna-v10-interpretation-content {
                    border-top-color: #E2E8F0 !important;
                    color: #475569 !important;
                }

                html body:has(.sna-v9-page) .sna-v10-interpretation-chevron {
                    color: #64748B !important;
                }

                html body:has(.sna-v9-page) .sna-v10-insight-chip {
                    background: #F8FAFC !important;
                    border-color: #D8E0EA !important;
                    color: #475569 !important;
                }

                html body:has(.sna-v9-page) .sna-v10-insight-chip:hover {
                    background: #FFF1F1 !important;
                    border-color: rgba(229,57,53,0.30) !important;
                    color: #B42318 !important;
                }

                /* Filter dan kontrol Streamlit. */
                html body:has(.sna-v9-page) div[data-testid="stVerticalBlockBorderWrapper"]:has(.sna-v9-control-marker)
                label,
                html body:has(.sna-v9-page) div[data-testid="stVerticalBlockBorderWrapper"]:has(.sna-v9-control-marker)
                label p,
                html body:has(.sna-v9-page) div[data-testid="stVerticalBlockBorderWrapper"]:has(.sna-v9-control-marker)
                [data-testid="stWidgetLabel"] p {
                    color: #334155 !important;
                }

                html body:has(.sna-v9-page) div[data-testid="stVerticalBlockBorderWrapper"]:has(.sna-v9-control-marker)
                div[data-testid="stSelectbox"] div[data-baseweb="select"] > div,
                html body:has(.sna-v9-page) div[data-testid="stVerticalBlockBorderWrapper"]:has(.sna-v12-filter-marker)
                div[data-testid="stSelectbox"] div[data-baseweb="select"] > div,
                html body:has(.sna-v9-page) div[data-testid="stVerticalBlockBorderWrapper"]:has(.sna-v12-filter-marker)
                div[data-testid="stTextInput"] input {
                    background: #FFFFFF !important;
                    background-color: #FFFFFF !important;
                    border-color: #CBD5E1 !important;
                    box-shadow: 0 4px 12px rgba(15,23,42,0.04) !important;
                    color: #1F2937 !important;
                }

                html body:has(.sna-v9-page) div[data-testid="stVerticalBlockBorderWrapper"]:has(.sna-v9-control-marker)
                div[data-testid="stSelectbox"] div[data-baseweb="select"] > div > div,
                html body:has(.sna-v9-page) div[data-testid="stVerticalBlockBorderWrapper"]:has(.sna-v12-filter-marker)
                div[data-testid="stSelectbox"] div[data-baseweb="select"] > div > div,
                html body:has(.sna-v9-page) div[data-testid="stVerticalBlockBorderWrapper"]:has(.sna-v12-filter-marker)
                div[data-testid="stTextInput"] input {
                    color: #1F2937 !important;
                    -webkit-text-fill-color: #1F2937 !important;
                }

                html body:has(.sna-v9-page) div[data-testid="stVerticalBlockBorderWrapper"]:has(.sna-v9-control-marker)
                div[data-testid="stSelectbox"] svg,
                html body:has(.sna-v9-page) div[data-testid="stVerticalBlockBorderWrapper"]:has(.sna-v12-filter-marker)
                div[data-testid="stSelectbox"] svg {
                    fill: #64748B !important;
                    color: #64748B !important;
                }

                html body:has(.sna-v9-page) div[data-baseweb="popover"]:has([role="listbox"]),
                html body:has(.sna-v9-page) [data-testid="stSelectboxVirtualDropdown"] {
                    background: #FFFFFF !important;
                    background-color: #FFFFFF !important;
                    border: 1px solid #D7DEE8 !important;
                    box-shadow: 0 14px 34px rgba(15,23,42,0.16) !important;
                    color: #24324A !important;
                }

                html body:has(.sna-v9-page) div[data-baseweb="popover"]:has([role="listbox"]) [role="listbox"],
                html body:has(.sna-v9-page) [data-testid="stSelectboxVirtualDropdown"] [role="listbox"] {
                    background: #FFFFFF !important;
                    border-color: #D7DEE8 !important;
                    box-shadow: none !important;
                }

                html body:has(.sna-v9-page) div[data-baseweb="popover"]:has([role="listbox"]) [role="option"],
                html body:has(.sna-v9-page) [data-testid="stSelectboxVirtualDropdown"] [role="option"] {
                    background: #FFFFFF !important;
                    border-color: transparent !important;
                    color: #334155 !important;
                }

                html body:has(.sna-v9-page) div[data-baseweb="popover"]:has([role="listbox"]) [role="option"] *,
                html body:has(.sna-v9-page) [data-testid="stSelectboxVirtualDropdown"] [role="option"] * {
                    color: inherit !important;
                    -webkit-text-fill-color: currentColor !important;
                }

                html body:has(.sna-v9-page) div[data-baseweb="popover"]:has([role="listbox"]) [role="option"]:hover,
                html body:has(.sna-v9-page) [data-testid="stSelectboxVirtualDropdown"] [role="option"]:hover {
                    background: #F6F8FB !important;
                    border-color: #E1E7EF !important;
                    color: #1E293B !important;
                    transform: none !important;
                }

                html body:has(.sna-v9-page) div[data-baseweb="popover"]:has([role="listbox"]) [role="option"][aria-selected="true"],
                html body:has(.sna-v9-page) [data-testid="stSelectboxVirtualDropdown"] [role="option"][aria-selected="true"] {
                    background: #FFF1F1 !important;
                    border-color: #F4C7C7 !important;
                    box-shadow: inset 3px 0 0 #E53935 !important;
                    color: #B42318 !important;
                }

                /* Legend, chips, catatan, dan ringkasan. */
                html body:has(.sna-v9-page) .sna-v9-legend-item,
                html body:has(.sna-v9-page) .sna-v9-platform-chip,
                html body:has(.sna-v9-page) .sna-v9-interaction-pill,
                html body:has(.sna-v9-page) .sna-v12-chip,
                html body:has(.sna-v9-page) .sna-v12-summary-tag,
                html body:has(.sna-v9-page) .sna-v9-detail-chip,
                html body:has(.sna-v9-page) .sna-v11-chip {
                    background: #F8FAFC !important;
                    border-color: #D8E0EA !important;
                    color: #334155 !important;
                    box-shadow: none !important;
                }

                html body:has(.sna-v9-page) .sna-v9-influencer-control-note,
                html body:has(.sna-v9-page) .sna-v9-interaction-strip,
                html body:has(.sna-v9-page) .sna-v11-academic-note {
                    background: linear-gradient(135deg, rgba(229,57,53,0.055), rgba(29,161,242,0.045)) !important;
                    border-color: #D8E0EA !important;
                    color: #475569 !important;
                    box-shadow: none !important;
                }

                html body:has(.sna-v9-page) .sna-v9-interaction-strip strong {
                    color: #1F2937 !important;
                }

                html body:has(.sna-v9-page) .sna-v9-interaction-strip span {
                    color: #64748B !important;
                }

                /* KPI graf. */
                html body:has(.sna-v9-page) .sna-v9-graph-kpi {
                    background:
                        radial-gradient(circle at 94% 12%, rgba(229,57,53,0.08), transparent 36%),
                        linear-gradient(145deg, #FFFFFF 0%, #F7F9FC 100%) !important;
                    border-color: #D8E0EA !important;
                    box-shadow: 0 8px 20px rgba(15,23,42,0.06) !important;
                }

                /* Area influencer modern. */
                html body:has(.sna-v9-page) div[data-testid="stVerticalBlockBorderWrapper"]:has(.sna-v12-influencer-marker) {
                    background:
                        radial-gradient(circle at 0% 0%, rgba(229,57,53,0.07), transparent 24%),
                        radial-gradient(circle at 100% 0%, rgba(131,58,180,0.06), transparent 26%),
                        radial-gradient(circle at 100% 100%, rgba(29,161,242,0.055), transparent 30%),
                        linear-gradient(180deg, #FFFFFF, #F8FAFC) !important;
                    border-color: #D8E0EA !important;
                    box-shadow: 0 16px 36px rgba(15,23,42,0.08), inset 0 1px 0 #FFFFFF !important;
                }

                html body:has(.sna-v9-page) .sna-v12-influencer-hero .sna-v9-section-subtitle {
                    color: #64748B !important;
                }

                html body:has(.sna-v9-page) .sna-v12-live-badge {
                    background: #ECFDF3 !important;
                    border-color: #BBE7C8 !important;
                    color: #166534 !important;
                }

                html body:has(.sna-v9-page) .sna-v9-influencer-mini-card {
                    background:
                        radial-gradient(circle at 96% 4%, color-mix(in srgb, var(--summary-accent) 10%, transparent), transparent 37%),
                        linear-gradient(145deg, #FFFFFF, #F8FAFC) !important;
                    border-color: #D8E0EA !important;
                    box-shadow: 0 8px 22px rgba(15,23,42,0.06) !important;
                }

                html body:has(.sna-v9-page) .sna-v9-influencer-mini-card:hover {
                    border-color: color-mix(in srgb, var(--summary-accent) 38%, #D8E0EA) !important;
                    box-shadow: 0 14px 30px rgba(15,23,42,0.09) !important;
                }

                html body:has(.sna-v9-page) .sna-v12-summary-icon {
                    background: color-mix(in srgb, var(--summary-accent) 10%, #FFFFFF) !important;
                    border-color: color-mix(in srgb, var(--summary-accent) 30%, #D8E0EA) !important;
                }

                /* Ranking influencer dan tabel. */
                html body:has(.sna-v9-page) .sna-v9-influencer-table-card {
                    background:
                        radial-gradient(circle at 96% 0%, color-mix(in srgb, var(--table-accent, #E53935) 7%, transparent), transparent 30%),
                        linear-gradient(180deg, #FFFFFF, #F8FAFC) !important;
                    border-color: #D8E0EA !important;
                    box-shadow: 0 10px 26px rgba(15,23,42,0.07) !important;
                }

                html body:has(.sna-v9-page) .sna-v9-influencer-table-card:hover {
                    border-color: color-mix(in srgb, var(--table-accent, #E53935) 38%, #D8E0EA) !important;
                    box-shadow: 0 16px 34px rgba(15,23,42,0.10) !important;
                }

                html body:has(.sna-v9-page) .sna-v9-influencer-table-head {
                    background: linear-gradient(135deg, color-mix(in srgb, var(--table-accent, #E53935) 7%, #FFFFFF), #FFFFFF) !important;
                    border-bottom-color: #E2E8F0 !important;
                }

                html body:has(.sna-v9-page) table.sna-v9-influencer-table {
                    color: #1F2937 !important;
                }

                html body:has(.sna-v9-page) .sna-v9-influencer-table thead th {
                    background: #F1F5F9 !important;
                    border-bottom-color: #D8E0EA !important;
                    color: #475569 !important;
                }

                html body:has(.sna-v9-page) .sna-v9-influencer-table tbody td {
                    border-bottom-color: #E8EDF3 !important;
                    color: #334155 !important;
                }

                html body:has(.sna-v9-page) .sna-v9-influencer-table tbody tr:hover {
                    background: color-mix(in srgb, var(--table-accent, #E53935) 6%, #FFFFFF) !important;
                }

                html body:has(.sna-v9-page) .sna-v9-username-cell,
                html body:has(.sna-v9-page) .sna-v9-num-cell,
                html body:has(.sna-v9-page) .sna-v9-score-text {
                    color: #1F2937 !important;
                }

                html body:has(.sna-v9-page) .sna-v9-rank-pill {
                    background: #FFF1F1;
                    border-color: #F2C1C1;
                    color: #B42318;
                }

                html body:has(.sna-v9-page) .sna-v9-score-bar {
                    background: #E5E7EB !important;
                }

                html body:has(.sna-v9-page) .sna-v12-avatar {
                    background: color-mix(in srgb, var(--table-accent, #E53935) 10%, #FFFFFF) !important;
                    border-color: color-mix(in srgb, var(--table-accent, #E53935) 28%, #D8E0EA) !important;
                    color: #334155 !important;
                }

                html body:has(.sna-v9-page) .sna-v9-table-scroll {
                    scrollbar-color: #B7C0CD #F1F5F9 !important;
                }

                /* Detail node. */
                html body:has(.sna-v9-page) .sna-v9-detail-panel {
                    background:
                        radial-gradient(circle at 10% 0%, rgba(229,57,53,0.07), transparent 32%),
                        radial-gradient(circle at 95% 10%, rgba(29,161,242,0.06), transparent 34%),
                        linear-gradient(135deg, #FFFFFF, #F8FAFC) !important;
                    border-color: #D8E0EA !important;
                    box-shadow: 0 12px 28px rgba(15,23,42,0.07) !important;
                }

                html body:has(.sna-v9-page) .sna-v9-detail-item {
                    background: linear-gradient(145deg, #FFFFFF, #F7F9FC) !important;
                    border-color: #D8E0EA !important;
                    box-shadow: 0 6px 16px rgba(15,23,42,0.05) !important;
                }

                html body:has(.sna-v9-page) .sna-v9-detail-item:hover,
                html body:has(.sna-v9-page) .sna-v9-detail-item[open] {
                    background: linear-gradient(145deg, #FFFFFF, #F2F6FA) !important;
                    border-color: color-mix(in srgb, var(--detail-accent) 42%, #D8E0EA) !important;
                    box-shadow: 0 12px 24px rgba(15,23,42,0.08) !important;
                }

                html body:has(.sna-v9-page) .sna-v9-detail-icon {
                    background: color-mix(in srgb, var(--detail-accent) 10%, #FFFFFF) !important;
                    border-color: color-mix(in srgb, var(--detail-accent) 30%, #D8E0EA) !important;
                }

                html body:has(.sna-v9-page) .sna-v9-detail-more {
                    background: #F8FAFC !important;
                    border-color: color-mix(in srgb, var(--detail-accent) 32%, #CBD5E1) !important;
                    color: #475569 !important;
                }

                /* Card penjelasan metode. */
                html body:has(.sna-v9-page) .sna-v9-method-card {
                    background:
                        radial-gradient(circle at 7% 0%, rgba(229,57,53,0.09), transparent 34%),
                        radial-gradient(circle at 95% 18%, rgba(29,161,242,0.08), transparent 30%),
                        linear-gradient(135deg, #FFFFFF, #F5F8FC) !important;
                    border-color: #CAD8E8 !important;
                    box-shadow: 0 14px 30px rgba(15,23,42,0.08), inset 0 1px 0 #FFFFFF !important;
                    color: #334155 !important;
                }

                html body:has(.sna-v9-page) .sna-v9-method-kicker {
                    color: #B42318 !important;
                }

                html body:has(.sna-v9-page) .sna-v9-method-head h3,
                html body:has(.sna-v9-page) .sna-v9-method-mini strong,
                html body:has(.sna-v9-page) .sna-v9-method-note strong {
                    color: #1F2937 !important;
                }

                html body:has(.sna-v9-page) .sna-v9-method-lead,
                html body:has(.sna-v9-page) .sna-v9-method-mini p {
                    color: #64748B !important;
                }

                html body:has(.sna-v9-page) .sna-v9-method-mini {
                    background: #FFFFFF !important;
                    border-color: #D8E0EA !important;
                    box-shadow: 0 5px 14px rgba(15,23,42,0.04) !important;
                }

                html body:has(.sna-v9-page) .sna-v9-method-note {
                    background: linear-gradient(135deg, rgba(229,57,53,0.055), rgba(29,161,242,0.045)) !important;
                    border-color: #D8E0EA !important;
                    color: #475569 !important;
                }

                /* Expander statistik. */
                html body:has(.sna-v9-page) div[data-testid="stExpander"] details,
                html body:has(.sna-v9-page) div[data-testid="stExpander"] details[open],
                html body:has(.sna-v9-page) div[data-testid="stExpander"] summary,
                html body:has(.sna-v9-page) div[data-testid="stExpander"] [data-testid="stExpanderDetails"] {
                    background: #FFFFFF !important;
                    background-color: #FFFFFF !important;
                    border-color: #D8E0EA !important;
                    color: #1F2937 !important;
                }

                html body:has(.sna-v9-page) div[data-testid="stExpander"] summary,
                html body:has(.sna-v9-page) div[data-testid="stExpander"] summary p,
                html body:has(.sna-v9-page) div[data-testid="stExpander"] summary span,
                html body:has(.sna-v9-page) div[data-testid="stExpander"] summary svg {
                    color: #1F2937 !important;
                    fill: currentColor !important;
                }

                /* Frame graf interaktif. Isi iframe juga diberi tema terpisah. */
                html body:has(.sna-v9-page) .sna-v9-graph-frame iframe,
                html body:has(.sna-v9-page) [data-testid="stIFrame"] iframe {
                    background: #FFFFFF !important;
                    border-color: #D8E0EA !important;
                    box-shadow: 0 12px 28px rgba(15,23,42,0.08) !important;
                }

                /* Graf statis akademik IndiBiz. */
                html body:has(.sna-v9-page) .sna-v11-check-item,
                html body:has(.sna-v9-page) .sna-v11-platform-card,
                html body:has(.sna-v9-page) .sna-v13-static-guide,
                html body:has(.sna-v9-page) .sna-v13-static-kpi {
                    background: linear-gradient(145deg, #FFFFFF, #F8FAFC) !important;
                    border-color: #D8E0EA !important;
                    color: #475569 !important;
                    box-shadow: 0 6px 16px rgba(15,23,42,0.05) !important;
                }

                html body:has(.sna-v9-page) .sna-v11-stage-shell,
                html body:has(.sna-v9-page) div[data-testid="stVerticalBlockBorderWrapper"]:has(.sna-v13-indibiz-static-marker) {
                    background:
                        radial-gradient(circle at 0% 0%, rgba(229,57,53,0.065), transparent 24%),
                        radial-gradient(circle at 100% 0%, rgba(131,58,180,0.05), transparent 26%),
                        radial-gradient(circle at 100% 100%, rgba(29,161,242,0.05), transparent 28%),
                        linear-gradient(180deg, #FFFFFF, #F8FAFC) !important;
                    border-color: #D8E0EA !important;
                    box-shadow: 0 14px 32px rgba(15,23,42,0.08) !important;
                }

                html body:has(.sna-v9-page) .sna-v11-platform-title,
                html body:has(.sna-v9-page) .sna-v11-platform-count,
                html body:has(.sna-v9-page) .sna-v13-static-guide strong {
                    color: #1F2937 !important;
                }

                html body:has(.sna-v9-page) .sna-v11-platform-note,
                html body:has(.sna-v9-page) .sna-v11-platform-share,
                html body:has(.sna-v9-page) .sna-v13-static-guide span {
                    color: #64748B !important;
                }

                html body:has(.sna-v9-page) div[data-testid="stVerticalBlockBorderWrapper"]:has(.sna-v13-indibiz-static-marker)
                div[data-testid="stPlotlyChart"] {
                    background: #FFFFFF !important;
                    border-color: #D8E0EA !important;
                }

                /* Dialog fullscreen chart tetap mengikuti tema aktif. */
                html body:has(.sna-v9-page) div[data-testid="stDialog"],
                html body:has(.sna-v9-page) div[data-baseweb="modal"] {
                    background: #F5F7FA !important;
                }

                html body:has(.sna-v9-page) div[data-testid="stDialog"] [data-testid="stPlotlyChart"],
                html body:has(.sna-v9-page) div[data-baseweb="modal"] [data-testid="stPlotlyChart"] {
                    background: #FFFFFF !important;
                    border-color: #D8E0EA !important;
                }

                html body:has(.sna-v9-page) .sna-v9-fullscreen-title {
                    color: #1F2937 !important;
                }

                html body:has(.sna-v9-page) .sna-v9-fullscreen-hint {
                    color: #64748B !important;
                }

                html body:has(.sna-v9-page) div[data-testid="stDialog"] button[aria-label="Close"],
                html body:has(.sna-v9-page) div[data-baseweb="modal"] button[aria-label="Close"] {
                    background: #FFFFFF !important;
                    border-color: #CBD5E1 !important;
                    color: #334155 !important;
                }

                /* Caption akhir halaman tetap terbaca di latar terang. */
                html body:has(.sna-v9-page) [data-testid="stCaptionContainer"],
                html body:has(.sna-v9-page) [data-testid="stCaptionContainer"] p {
                    color: #64748B !important;
                }
            </style>
            """,
            unsafe_allow_html=True,
        )
    except Exception as exc:
        st.error(f"Penyesuaian light theme halaman SNA belum dapat dimuat: {exc}")


# -----------------------------------------------------------------------------
# Helper normalisasi data
# -----------------------------------------------------------------------------

def _normalize_username(value: Any) -> str:
    """Bersihkan username dan samakan menjadi huruf kecil."""
    try:
        username = str(value or "").strip().lstrip("'").strip()
        return username.lstrip("@").strip().lower()
    except Exception:
        return ""


def _compact_username(value: Any) -> str:
    """Ubah username menjadi format alfanumerik kecil untuk pencocokan akun brand."""
    try:
        return "".join(char for char in str(value or "").lower() if char.isalnum())
    except Exception:
        return ""


def _normalize_platform(value: Any) -> str:
    """Normalisasi nama platform ke twitter, instagram, tiktok, atau unknown."""
    try:
        platform = str(value or "").lower().strip().lstrip("'")
        aliases = {
            "x": "twitter",
            "twitter/x": "twitter",
            "twitter": "twitter",
            "twitter (x)": "twitter",
            "ig": "instagram",
            "instagram": "instagram",
            "tik tok": "tiktok",
            "tiktok": "tiktok",
            "tik-tok": "tiktok",
        }
        return aliases.get(platform, platform if platform else "unknown")
    except Exception:
        return "unknown"


def _is_brand_account(username: str) -> bool:
    """Tentukan apakah username termasuk akun resmi/brand layanan."""
    try:
        compact = _compact_username(username)
        if not compact:
            return False
        return compact in BRAND_ALIASES or compact.startswith(BRAND_PREFIXES)
    except Exception:
        return False


def _hide_service_account_from_exploration_graph(username: Any) -> bool:
    """Sembunyikan akun layanan turunan dari visualisasi graf interaktif.

    Hanya akun layanan utama ``indihome``, ``indibiz``, dan ``telkomsel`` yang
    boleh tetap tampil sebagai hub merah. Data SNA asli tidak dihapus.
    """
    try:
        compact = _compact_username(username)
        if not compact:
            return False
        if compact in PRIMARY_SERVICE_GRAPH_ACCOUNTS:
            return False

        # Gunakan aturan akun layanan yang sudah dipakai ranking agar variasi
        # seperti indihomecare, indihomejtd, telkomjabar, atau telkomselcare
        # ikut dibersihkan dari visualisasi tanpa menghapusnya dari data SNA.
        return _is_brand_account(str(username)) or compact.startswith(EXCLUDE_SERVICE_PREFIXES)
    except Exception as exc:
        st.error(f"Filter akun layanan pada graf interaktif belum dapat diterapkan: {exc}")
        return False




def _map_service_account_for_indibiz_graph(username: Any) -> str:
    """Petakan akun layanan ke node utama khusus visualisasi graf IndiBiz.

    Akun regional/care IndiBiz disatukan ke ``indibiz`` agar interaksi tetap
    terbaca sebagai hubungan ke layanan utama, bukan sebagai influencer atau
    hub terpisah. Pada graf IndiBiz, hanya akun utama ``indibiz`` yang
    dipertahankan sebagai node layanan. Akun layanan lain disembunyikan dari
    visualisasi saja dan tidak dihapus dari data penelitian.
    """
    try:
        normalized = _normalize_username(username)
        compact = _compact_username(normalized)
        if not compact:
            return ""

        # Pada konteks layanan IndiBiz, hanya node utama ``indibiz`` yang
        # dipertahankan sebagai hub merah. Seluruh akun regional/care IndiBiz
        # digabung ke hub ini. Akun layanan lain tidak ditampilkan pada graf
        # IndiBiz agar tidak terbaca sebagai influencer percakapan IndiBiz.
        if compact == "indibiz" or compact.startswith("indibiz"):
            return "indibiz"
        if compact in PRIMARY_SERVICE_GRAPH_ACCOUNTS:
            return ""
        if compact.startswith(("indihome", "myindihome")):
            return ""
        if compact.startswith(("telkomsel", "mytelkomsel", "tsel")):
            return ""

        # Akun Telkom/regional lain tidak dipaksakan menjadi Telkomsel karena
        # secara entitas berbeda. Node tersebut cukup disembunyikan dari graf.
        if _is_brand_account(normalized) or compact.startswith(EXCLUDE_SERVICE_PREFIXES):
            return ""
        return normalized
    except Exception as exc:
        st.error(f"Pemetaan akun layanan pada graf IndiBiz belum dapat diterapkan: {exc}")
        return _normalize_username(username)


def _collapse_indibiz_service_accounts_for_graph(
    graph: nx.DiGraph,
    node_df: pd.DataFrame,
) -> tuple[nx.DiGraph, pd.DataFrame]:
    """Satukan akun turunan IndiBiz ke satu hub visual tanpa mengubah data asli."""
    try:
        if graph is None or graph.number_of_nodes() == 0 or node_df is None or node_df.empty:
            return graph.copy(), node_df.copy()

        node_mapping = {
            str(node): _map_service_account_for_indibiz_graph(node)
            for node in graph.nodes
        }
        collapsed_graph = nx.DiGraph()

        # Bangun ulang edge sehingga seluruh interaksi ke akun regional/care
        # IndiBiz tetap dipertahankan, tetapi target/source visualnya menjadi
        # satu node utama ``indibiz``. Edge ganda dijumlahkan melalui weight.
        for source, target, attributes in graph.edges(data=True):
            mapped_source = node_mapping.get(str(source), str(source))
            mapped_target = node_mapping.get(str(target), str(target))
            if not mapped_source or not mapped_target or mapped_source == mapped_target:
                continue

            weight = int(attributes.get("weight", 1) or 1)
            if collapsed_graph.has_edge(mapped_source, mapped_target):
                collapsed_graph[mapped_source][mapped_target]["weight"] = int(
                    collapsed_graph[mapped_source][mapped_target].get("weight", 1)
                ) + weight
            else:
                collapsed_graph.add_edge(
                    mapped_source,
                    mapped_target,
                    relationship=str(attributes.get("relationship", "interaction")),
                    platform=str(attributes.get("platform", "unknown")),
                    weight=weight,
                )

        if collapsed_graph.number_of_nodes() == 0:
            return graph.copy(), node_df.copy()

        work = node_df.copy()
        work["username"] = work["username"].astype(str)
        work["visual_username"] = work["username"].map(
            lambda value: node_mapping.get(str(value), _map_service_account_for_indibiz_graph(value))
        )
        work = work[work["visual_username"].astype(str).ne("")].copy()

        degree_centrality = (
            nx.degree_centrality(collapsed_graph)
            if collapsed_graph.number_of_nodes() > 1
            else {str(node): 0.0 for node in collapsed_graph.nodes}
        )
        try:
            pagerank = nx.pagerank(
                collapsed_graph,
                alpha=0.85,
                weight="weight",
                max_iter=200,
                tol=1.0e-6,
            )
        except Exception:
            pagerank = {str(node): 0.0 for node in collapsed_graph.nodes}

        rows: list[dict[str, Any]] = []
        for username in collapsed_graph.nodes:
            candidates = work[work["visual_username"].eq(str(username))].copy()
            exact = candidates[candidates["username"].eq(str(username))]
            if not exact.empty:
                base = exact.iloc[0].to_dict()
            elif not candidates.empty:
                base = candidates.iloc[0].to_dict()
            else:
                base = {"username": str(username)}

            followers = 0
            if not candidates.empty and "followers" in candidates.columns:
                followers = int(
                    pd.to_numeric(candidates["followers"], errors="coerce").fillna(0).max()
                )

            is_primary_service = str(username) in PRIMARY_SERVICE_GRAPH_ACCOUNTS
            sentiment = _normalize_sentiment(base.get("dominant_sentiment", "unknown"))
            base.update(
                {
                    "username": str(username),
                    "platform": str(username) if is_primary_service else str(base.get("platform", "unknown")),
                    "platform_group": "target" if is_primary_service else str(base.get("platform_group", "unknown")),
                    "platform_label": PLATFORM_DISPLAY["target"] if is_primary_service else str(base.get("platform_label", "Tidak diketahui")),
                    "followers": followers,
                    "degree": int(collapsed_graph.degree(username)),
                    "degree_centrality": float(degree_centrality.get(username, 0.0)),
                    "pagerank": float(pagerank.get(username, 0.0)),
                    "in_degree": int(collapsed_graph.in_degree(username)),
                    "out_degree": int(collapsed_graph.out_degree(username)),
                    "dominant_sentiment": sentiment,
                    "sentiment_label": SENTIMENT_DISPLAY.get(sentiment, "Belum tersedia"),
                    "is_brand": bool(is_primary_service),
                }
            )
            base.pop("visual_username", None)
            rows.append(base)

        collapsed_nodes = pd.DataFrame(rows)
        if not collapsed_nodes.empty:
            collapsed_nodes = collapsed_nodes.sort_values(
                ["pagerank", "degree_centrality", "followers", "username"],
                ascending=[False, False, False, True],
                kind="mergesort",
            ).reset_index(drop=True)

        return collapsed_graph, collapsed_nodes
    except Exception as exc:
        st.error(f"Gagal merapikan akun layanan pada graf IndiBiz: {exc}")
        return graph.copy(), node_df.copy()


def _is_excluded_from_influencer(username: Any) -> bool:
    """Cek akun layanan/turunan yang harus disembunyikan dari ranking influencer."""
    try:
        normalized = _normalize_username(username)
        if normalized in EXCLUDE_ACCOUNTS_NORMALIZED:
            return True

        # Variasi pemisah seperti indihome.id tetap dikenali, tanpa mengubah graph.
        compact = _compact_username(normalized)
        if compact in EXCLUDE_ACCOUNTS_COMPACT:
            return True

        # Tangkap akun layanan regional/care/turunan seperti indihomejtd,
        # indihomecare_jabar, telkomjabar, telkomselcare, dan variasi sejenis.
        return compact.startswith(EXCLUDE_SERVICE_PREFIXES)
    except Exception as exc:
        st.error(f"Filter akun layanan belum dapat diterapkan: {exc}")
        return False


def _infer_service(row: pd.Series) -> str:
    """Inferensi layanan dari kolom layanan atau dari akun source/target."""
    try:
        if "layanan" in row.index:
            raw_service = str(row.get("layanan", "")).strip().lower()
            service_alias = {
                "indihome": "IndiHome",
                "indi home": "IndiHome",
                "indibiz": "IndiBiz",
                "indi biz": "IndiBiz",
                "telkomsel": "Telkomsel",
            }
            if raw_service in service_alias:
                return service_alias[raw_service]

        joined = f"{row.get('source', '')} {row.get('target', '')} {row.get('relationship', '')}"
        compact = _compact_username(joined)
        for service, aliases in SERVICE_ALIASES.items():
            if any(alias in compact for alias in aliases):
                return service
        return "Tidak diketahui"
    except Exception:
        return "Tidak diketahui"


@st.cache_data(show_spinner=False, max_entries=12)
def _prepare_sna_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    """Validasi dan bersihkan data SNA sebelum membangun graf."""
    try:
        if df is None or df.empty:
            return pd.DataFrame(columns=sorted(REQUIRED_SNA_COLUMNS | {"layanan"}))

        missing = sorted(REQUIRED_SNA_COLUMNS.difference(df.columns))
        if missing:
            raise ValueError(f"Kolom wajib belum tersedia: {', '.join(missing)}")

        work = df.copy()
        work["source"] = work["source"].apply(_normalize_username)
        work["target"] = work["target"].apply(_normalize_username)
        work["relationship"] = (
            work["relationship"].fillna("interaction").astype(str).str.lower().str.strip()
        )
        work["platform"] = work["platform"].apply(_normalize_platform)
        work["followers"] = (
            pd.to_numeric(work["followers"], errors="coerce")
            .fillna(0)
            .clip(lower=0)
            .astype(int)
        )

        if "layanan" not in work.columns:
            work["layanan"] = work.apply(_infer_service, axis=1)
        else:
            work["layanan"] = work.apply(_infer_service, axis=1)

        invalid = {"", "nan", "none", "null"}
        work = work[
            ~work["source"].str.lower().isin(invalid)
            & ~work["target"].str.lower().isin(invalid)
        ].copy()

        # Edge berulang dipertahankan karena mewakili frekuensi interaksi nyata.
        # Fungsi _aggregate_edges() akan mengubah pengulangan tersebut menjadi
        # atribut weight saat graf NetworkX dibangun.
        return work.reset_index(drop=True)
    except Exception as exc:
        st.error(f"Gagal menyiapkan data SNA: {exc}")
        return pd.DataFrame(columns=sorted(REQUIRED_SNA_COLUMNS | {"layanan"}))


def _filter_sna_dataframe(
    df: pd.DataFrame,
    service: str,
    platform: str,
) -> pd.DataFrame:
    """Filter DataFrame SNA berdasarkan layanan dan platform yang dipilih."""
    try:
        if df is None or df.empty:
            return pd.DataFrame(columns=sorted(REQUIRED_SNA_COLUMNS | {"layanan"}))

        result = df.copy()
        if service in SERVICE_OPTIONS and "layanan" in result.columns:
            layanan_unik = set(result["layanan"].dropna().astype(str).str.strip())
            if len(layanan_unik) > 1:
                result = result[result["layanan"].eq(service)].copy()
        if platform != "all" and "platform" in result.columns:
            result = result[result["platform"].eq(platform)].copy()
        return result.reset_index(drop=True)
    except Exception as exc:
        st.error(f"Gagal memfilter data SNA: {exc}")
        return df.copy() if isinstance(df, pd.DataFrame) else pd.DataFrame()


@st.cache_data(show_spinner=False)
def _aggregate_edges(df: pd.DataFrame) -> pd.DataFrame:
    """Gabungkan edge berulang dan simpan frekuensinya sebagai weight."""
    try:
        if df is None or df.empty:
            return pd.DataFrame(columns=["source", "target", "relationship", "platform", "weight"])

        grouped = (
            df.groupby(["source", "target"], as_index=False, sort=False)
            .agg(
                relationship=("relationship", "first"),
                platform=("platform", "first"),
                weight=("relationship", "size"),
            )
            .reset_index(drop=True)
        )
        grouped["weight"] = pd.to_numeric(grouped["weight"], errors="coerce").fillna(1).astype(int)
        return grouped
    except Exception as exc:
        st.error(f"Gagal menggabungkan edge SNA: {exc}")
        return pd.DataFrame(columns=["source", "target", "relationship", "platform", "weight"])


@st.cache_data(show_spinner=False, max_entries=24)
def _build_node_metadata(df: pd.DataFrame) -> tuple[dict[str, str], dict[str, int]]:
    """Bangun peta platform dan followers untuk setiap node."""
    try:
        if df is None or df.empty:
            return {}, {}

        source_platform = df.groupby("source", sort=False)["platform"].first().astype(str).to_dict()
        target_platform = df.groupby("target", sort=False)["platform"].first().astype(str).to_dict()
        followers_map = df.groupby("source", sort=False)["followers"].max().fillna(0).astype(int).to_dict()

        platform_map = dict(target_platform)
        platform_map.update(source_platform)
        return platform_map, followers_map
    except Exception as exc:
        st.error(f"Gagal membangun metadata node: {exc}")
        return {}, {}



def _normalize_sentiment(value: Any) -> str:
    """Normalisasi sentimen tanpa menganggap label kosong sebagai sentimen netral."""
    try:
        raw = str(value or "").strip().lower()
        aliases = {
            "positive": "positive", "positif": "positive", "label_0": "positive",
            "neutral": "neutral", "netral": "neutral", "label_1": "neutral",
            "negative": "negative", "negatif": "negative", "label_2": "negative",
        }
        return aliases.get(raw, "unknown")
    except Exception:
        return "unknown"


@st.cache_data(show_spinner=False, max_entries=24)
def _build_node_sentiment_map(df: pd.DataFrame) -> dict[str, str]:
    """Hitung sentimen dominan setiap node dari edge yang melibatkannya."""
    try:
        if df is None or df.empty:
            return {}

        sentiment_column = next(
            (
                column
                for column in ["sentiment", "predicted_sentiment", "label", "sentimen"]
                if column in df.columns
            ),
            None,
        )
        if sentiment_column is None:
            return {}

        observations: list[tuple[str, str]] = []
        for row in df[["source", "target", sentiment_column]].itertuples(index=False, name=None):
            source, target, sentiment_value = row
            sentiment = _normalize_sentiment(sentiment_value)
            if sentiment == "unknown":
                continue
            if source:
                observations.append((str(source), sentiment))
            if target:
                observations.append((str(target), sentiment))

        if not observations:
            return {}

        sentiment_df = pd.DataFrame(observations, columns=["username", "sentiment"])
        counts = (
            sentiment_df.groupby(["username", "sentiment"], as_index=False)
            .size()
            .rename(columns={"size": "jumlah"})
        )
        counts["prioritas"] = counts["sentiment"].map(SENTIMENT_PRIORITY).fillna(0)
        dominant = (
            counts.sort_values(
                ["username", "jumlah", "prioritas"],
                ascending=[True, False, False],
                kind="mergesort",
            )
            .drop_duplicates("username", keep="first")
        )
        return dominant.set_index("username")["sentiment"].to_dict()
    except Exception as exc:
        st.error(f"Gagal menghitung sentimen dominan node: {exc}")
        return {}


def _calculate_betweenness_safe(graph: nx.DiGraph) -> dict[str, float]:
    """Hitung betweenness secara defensif agar graf besar tetap responsif."""
    try:
        node_count = graph.number_of_nodes()
        if node_count <= 1:
            return {str(node): 0.0 for node in graph.nodes}
        if node_count <= 1200:
            return nx.betweenness_centrality(graph, normalized=True, weight=None)
        if node_count <= 8000:
            sample_size = min(64, node_count)
            return nx.betweenness_centrality(
                graph,
                k=sample_size,
                normalized=True,
                weight=None,
                seed=42,
            )

        # Pada graf sangat besar, hitung aproksimasi pada subgraf kandidat utama.
        ranked_nodes = sorted(graph.degree, key=lambda item: item[1], reverse=True)
        candidate_nodes = [node for node, _ in ranked_nodes[:2000]]
        candidate_graph = graph.subgraph(candidate_nodes).copy()
        sample_size = min(64, candidate_graph.number_of_nodes())
        approximate = nx.betweenness_centrality(
            candidate_graph,
            k=sample_size,
            normalized=True,
            weight=None,
            seed=42,
        )
        return {str(node): float(approximate.get(node, 0.0)) for node in graph.nodes}
    except Exception:
        return {str(node): 0.0 for node in graph.nodes}



@st.cache_data(show_spinner=False)
def _analyze_network(
    clean_df: pd.DataFrame,
    calculate_pagerank: bool = True,
) -> tuple[nx.DiGraph, pd.DataFrame, pd.DataFrame, dict[str, float]]:
    """Bangun DiGraph, hitung seluruh metrik, dan susun tabel node."""
    try:
        graph = nx.DiGraph()
        empty_summary = {
            "total_nodes": 0,
            "total_edges": 0,
            "density": 0.0,
            "avg_degree": 0.0,
        }
        if clean_df is None or clean_df.empty:
            return graph, pd.DataFrame(), pd.DataFrame(), empty_summary

        edge_df = _aggregate_edges(clean_df)
        platform_map, followers_map = _build_node_metadata(clean_df)
        sentiment_map = _build_node_sentiment_map(clean_df)

        for row in edge_df.itertuples(index=False):
            graph.add_edge(
                row.source,
                row.target,
                relationship=row.relationship,
                platform=row.platform,
                weight=int(row.weight),
            )

        for username in graph.nodes:
            graph.nodes[username]["followers"] = int(followers_map.get(username, 0))
            graph.nodes[username]["platform"] = platform_map.get(username, "unknown")
            graph.nodes[username]["dominant_sentiment"] = sentiment_map.get(username, "unknown")
            if _is_brand_account(username):
                graph.nodes[username]["platform"] = _compact_username(username) or "target"

        degree_centrality = nx.degree_centrality(graph) if graph.number_of_nodes() > 1 else {}
        betweenness = _calculate_betweenness_safe(graph)
        pagerank: dict[str, float] = {}
        if calculate_pagerank and graph.number_of_nodes() > 0:
            try:
                pagerank = nx.pagerank(
                    graph,
                    alpha=0.85,
                    weight="weight",
                    max_iter=200,
                    tol=1.0e-6,
                )
            except Exception as pagerank_error:
                st.warning(
                    "PageRank belum konvergen pada graf aktif. Metrik lain tetap "
                    f"ditampilkan. Detail: {pagerank_error}"
                )
                pagerank = {}

        rows: list[dict[str, Any]] = []
        for username in graph.nodes:
            is_brand = _is_brand_account(username)
            raw_platform = str(graph.nodes[username].get("platform", "unknown"))
            platform_group = "target" if is_brand else raw_platform
            sentiment = _normalize_sentiment(
                graph.nodes[username].get("dominant_sentiment", "unknown")
            )
            rows.append(
                {
                    "username": username,
                    "platform": raw_platform,
                    "platform_group": platform_group,
                    "platform_label": PLATFORM_DISPLAY.get(
                        platform_group, str(platform_group).title()
                    ),
                    "followers": int(graph.nodes[username].get("followers", 0)),
                    "degree": int(graph.degree(username)),
                    "degree_centrality": float(degree_centrality.get(username, 0.0)),
                    "betweenness_centrality": float(betweenness.get(username, 0.0)),
                    "pagerank": float(pagerank.get(username, 0.0)),
                    "in_degree": int(graph.in_degree(username)),
                    "out_degree": int(graph.out_degree(username)),
                    "dominant_sentiment": sentiment,
                    "sentiment_label": SENTIMENT_DISPLAY.get(sentiment, "Belum tersedia"),
                    "is_brand": bool(is_brand),
                }
            )

        node_df = pd.DataFrame(rows)
        if not node_df.empty:
            node_df = node_df.sort_values(
                ["pagerank", "degree_centrality", "followers", "username"],
                ascending=[False, False, False, True],
                kind="mergesort",
            ).reset_index(drop=True)

        node_count = graph.number_of_nodes()
        edge_count = graph.number_of_edges()
        summary = {
            "total_nodes": int(node_count),
            "total_edges": int(edge_count),
            "density": float(nx.density(graph)) if node_count > 1 else 0.0,
            "avg_degree": (
                float(sum(dict(graph.degree()).values()) / node_count)
                if node_count
                else 0.0
            ),
        }
        return graph, node_df, edge_df, summary
    except Exception as exc:
        st.error(f"Gagal menghitung metrik jaringan: {exc}")
        return nx.DiGraph(), pd.DataFrame(), pd.DataFrame(), {
            "total_nodes": 0,
            "total_edges": 0,
            "density": 0.0,
            "avg_degree": 0.0,
        }


def _calculate_network_statistics(
    graph: nx.DiGraph,
    clean_df: pd.DataFrame,
) -> dict[str, Any]:
    """Hitung statistik NetworkX yang setara dengan Cell [10] notebook IndiBiz."""
    try:
        # Degree centrality menunjukkan proporsi koneksi langsung setiap akun.
        degree_centrality = nx.degree_centrality(graph)

        # In-degree menghitung edge masuk, sedangkan out-degree menghitung edge keluar.
        in_degree = dict(graph.in_degree())
        out_degree = dict(graph.out_degree())

        # Urutan ini sama dengan notebook: nilai degree centrality tertinggi lebih dulu.
        top_active = sorted(
            degree_centrality.items(),
            key=lambda item: item[1],
            reverse=True,
        )[:10]

        # Followers dihitung dari node source dan mengambil nilai terbesar per akun.
        followers_map = (
            clean_df.groupby("source")["followers"].max()
            if clean_df is not None and not clean_df.empty
            else pd.Series(dtype="int64")
        )
        top_followers = followers_map.sort_values(ascending=False).head(10)

        # Rata-rata dibuat aman ketika graf kosong agar dashboard tidak crash.
        avg_in_degree = float(np.mean(list(in_degree.values()))) if in_degree else 0.0
        avg_out_degree = float(np.mean(list(out_degree.values()))) if out_degree else 0.0

        # Nama network_stats dipertahankan agar mudah dicocokkan dengan Cell [10].
        network_stats = {
            "degree_centrality": degree_centrality,
            "in_degree": in_degree,
            "out_degree": out_degree,
            "top_active": top_active,
            "top_followers": top_followers,
            "node_count": int(graph.number_of_nodes()),
            "edge_count": int(graph.number_of_edges()),
            "density": float(nx.density(graph)) if graph.number_of_nodes() > 1 else 0.0,
            "avg_in_degree": avg_in_degree,
            "avg_out_degree": avg_out_degree,
        }
        return network_stats
    except Exception as exc:
        st.error(f"Gagal menghitung statistik network IndiBiz: {exc}")
        return {
            "degree_centrality": {},
            "in_degree": {},
            "out_degree": {},
            "top_active": [],
            "top_followers": pd.Series(dtype="int64"),
            "node_count": 0,
            "edge_count": 0,
            "density": 0.0,
            "avg_in_degree": 0.0,
            "avg_out_degree": 0.0,
        }


def _account_initials(account: str) -> str:
    """Ambil dua karakter awal akun untuk avatar visual tabel."""
    try:
        clean = str(account or "?").strip().lstrip("@")
        parts = [part for part in clean.replace("-", "_").split("_") if part]
        if len(parts) >= 2:
            return f"{parts[0][0]}{parts[1][0]}".upper()
        return clean[:2].upper() if clean else "?"
    except Exception:
        return "?"


def _build_cell10_active_rows(top_active: list[tuple[str, float]]) -> str:
    """Bangun baris tabel akun aktif dengan indikator visual terukur."""
    try:
        rows: list[str] = []
        max_score = max((float(score) for _, score in top_active), default=0.0)
        for rank, (account, score) in enumerate(top_active, 1):
            score_value = float(score)
            bar_width = 0.0 if max_score <= 0 else max(4.0, min(100.0, (score_value / max_score) * 100.0))
            safe_account = escape(str(account))
            initials = escape(_account_initials(str(account)))
            rows.append(
                f'<tr class="sna-v10-rank-row sna-v10-rank-row--{rank}" '
                f'style="--row-delay:{rank * 45}ms; --bar-width:{bar_width:.2f}%;">'
                f'<td class="sna-v10-table-rank"><span class="sna-v10-rank-chip">#{rank}</span></td>'
                '<td class="sna-v10-table-username">'
                '<span class="sna-v10-account-wrap">'
                f'<span class="sna-v10-account-avatar" aria-hidden="true">{initials}</span>'
                f'<span title="{safe_account}">{safe_account}</span>'
                '</span></td>'
                '<td class="sna-v10-table-number">'
                '<span class="sna-v10-number-wrap">'
                f'<span>{score_value:.5f}</span>'
                '<span class="sna-v10-mini-track" aria-hidden="true"><span class="sna-v10-mini-bar"></span></span>'
                '</span></td>'
                '</tr>'
            )
        if not rows:
            return '<tr><td colspan="3">Data akun aktif belum tersedia.</td></tr>'
        return "".join(rows)
    except Exception as exc:
        return f'<tr><td colspan="3">Gagal membangun tabel: {escape(str(exc))}</td></tr>'


def _build_cell10_followers_rows(top_followers: pd.Series) -> str:
    """Bangun baris tabel followers dengan indikator visual terukur."""
    try:
        rows: list[str] = []
        if isinstance(top_followers, pd.Series):
            items = list(top_followers.items())
        elif isinstance(top_followers, dict):
            items = list(top_followers.items())
        else:
            items = []

        numeric_items: list[tuple[Any, int]] = []
        for account, followers in items:
            numeric_value = pd.to_numeric(followers, errors="coerce")
            followers_int = int(numeric_value) if pd.notna(numeric_value) else 0
            numeric_items.append((account, followers_int))
        max_followers = max((followers for _, followers in numeric_items), default=0)

        for rank, (account, followers_int) in enumerate(numeric_items, 1):
            followers_label = f"{followers_int:,}".replace(",", ".")
            bar_width = 0.0 if max_followers <= 0 else max(4.0, min(100.0, (followers_int / max_followers) * 100.0))
            safe_account = escape(str(account))
            initials = escape(_account_initials(str(account)))
            rows.append(
                f'<tr class="sna-v10-rank-row sna-v10-rank-row--{rank}" '
                f'style="--row-delay:{rank * 45}ms; --bar-width:{bar_width:.2f}%;">'
                f'<td class="sna-v10-table-rank"><span class="sna-v10-rank-chip">#{rank}</span></td>'
                '<td class="sna-v10-table-username">'
                '<span class="sna-v10-account-wrap">'
                f'<span class="sna-v10-account-avatar" aria-hidden="true">{initials}</span>'
                f'<span title="{safe_account}">{safe_account}</span>'
                '</span></td>'
                '<td class="sna-v10-table-number">'
                '<span class="sna-v10-number-wrap">'
                f'<span>{followers_label}</span>'
                '<span class="sna-v10-mini-track" aria-hidden="true"><span class="sna-v10-mini-bar"></span></span>'
                '</span></td>'
                '</tr>'
            )
        if not rows:
            return '<tr><td colspan="3">Data followers belum tersedia.</td></tr>'
        return "".join(rows)
    except Exception as exc:
        return f'<tr><td colspan="3">Gagal membangun tabel: {escape(str(exc))}</td></tr>'


def _render_indibiz_network_statistics(
    network_stats: dict[str, Any],
    source_name: str,
    platform: str,
) -> None:
    """Tampilkan panel statistik IndiBiz yang interaktif dan responsif."""
    try:
        if not network_stats:
            st.info("Statistik network IndiBiz belum tersedia.")
            return

        node_count = int(network_stats.get("node_count", 0))
        edge_count = int(network_stats.get("edge_count", 0))
        density = float(network_stats.get("density", 0.0))
        avg_in_degree = float(network_stats.get("avg_in_degree", 0.0))
        avg_out_degree = float(network_stats.get("avg_out_degree", 0.0))
        top_active = list(network_stats.get("top_active", []))
        top_followers = network_stats.get("top_followers", pd.Series(dtype="int64"))

        active_rows = _build_cell10_active_rows(top_active)
        followers_rows = _build_cell10_followers_rows(top_followers)
        density_status = "Terhitung" if density > 0 else "Perlu diperiksa"

        html = f"""
        <section class="sna-v10-statistics-card">
            <div class="sna-v10-statistics-head">
                <div>
                    <div class="sna-v10-statistics-eyebrow">
                        <span class="sna-v10-live-dot" aria-hidden="true"></span>
                        Analisis jaringan aktif
                    </div>
                    <h2 class="sna-v10-statistics-title">STATISTIK NETWORK ANALYSIS — INDIBIZ</h2>
                    <div class="sna-v10-statistics-subtitle">Ringkasan struktur jaringan, konektivitas akun, dan influencer utama pada percakapan IndiBiz.</div>
                </div>
                <div class="sna-v10-statistics-badges">
                    <span class="sna-v10-statistics-badge">● Density: {density_status}</span>
                    <span class="sna-v10-statistics-badge sna-v10-statistics-badge--soft">5 metrik utama</span>
                </div>
            </div>
            <div class="sna-v10-statistics-body">
                <div class="sna-v10-metric-grid">
                    <div class="sna-v10-metric sna-v10-metric--node" style="--metric-delay:40ms;">
                        <div class="sna-v10-metric-top">
                            <span class="sna-v10-metric-label">Jumlah Node</span>
                            <span class="sna-v10-metric-icon" aria-hidden="true">●</span>
                        </div>
                        <span class="sna-v10-metric-value">{f"{node_count:,}".replace(",", ".")}</span>
                        <span class="sna-v10-metric-hint">Akun unik dalam jaringan</span>
                    </div>
                    <div class="sna-v10-metric sna-v10-metric--edge" style="--metric-delay:90ms;">
                        <div class="sna-v10-metric-top">
                            <span class="sna-v10-metric-label">Jumlah Edge</span>
                            <span class="sna-v10-metric-icon" aria-hidden="true">↔</span>
                        </div>
                        <span class="sna-v10-metric-value">{f"{edge_count:,}".replace(",", ".")}</span>
                        <span class="sna-v10-metric-hint">Relasi antar akun</span>
                    </div>
                    <div class="sna-v10-metric sna-v10-metric--density" style="--metric-delay:140ms;">
                        <div class="sna-v10-metric-top">
                            <span class="sna-v10-metric-label">Density</span>
                            <span class="sna-v10-metric-icon" aria-hidden="true">◇</span>
                        </div>
                        <span class="sna-v10-metric-value">{density:.6f}</span>
                        <span class="sna-v10-metric-hint">Kerapatan hubungan jaringan</span>
                    </div>
                    <div class="sna-v10-metric sna-v10-metric--in" style="--metric-delay:190ms;">
                        <div class="sna-v10-metric-top">
                            <span class="sna-v10-metric-label">Rata-rata In-Degree</span>
                            <span class="sna-v10-metric-icon" aria-hidden="true">↙</span>
                        </div>
                        <span class="sna-v10-metric-value">{avg_in_degree:.2f}</span>
                        <span class="sna-v10-metric-hint">Interaksi masuk per akun</span>
                    </div>
                    <div class="sna-v10-metric sna-v10-metric--out" style="--metric-delay:240ms;">
                        <div class="sna-v10-metric-top">
                            <span class="sna-v10-metric-label">Rata-rata Out-Degree</span>
                            <span class="sna-v10-metric-icon" aria-hidden="true">↗</span>
                        </div>
                        <span class="sna-v10-metric-value">{avg_out_degree:.2f}</span>
                        <span class="sna-v10-metric-hint">Interaksi keluar per akun</span>
                    </div>
                </div>

                <div class="sna-v10-table-grid">
                    <div class="sna-v10-table-card sna-v10-table-card--active">
                        <div class="sna-v10-table-head">
                            <div class="sna-v10-table-heading">
                                <span class="sna-v10-table-icon" aria-hidden="true">↯</span>
                                <div>
                                    <div class="sna-v10-table-title">Top 10 Akun Paling Aktif</div>
                                    <div class="sna-v10-table-note">Peringkat berdasarkan konektivitas langsung tertinggi. Akun resmi tetap ditampilkan untuk memperlihatkan pusat jaringan.</div>
                                </div>
                            </div>
                            <span class="sna-v10-table-badge">Degree</span>
                        </div>
                        <div class="sna-v10-table-scroll">
                            <table class="sna-v10-table">
                                <thead><tr><th>Rank</th><th>Akun</th><th>Degree Centrality</th></tr></thead>
                                <tbody>{active_rows}</tbody>
                            </table>
                        </div>
                    </div>

                    <div class="sna-v10-table-card sna-v10-table-card--followers">
                        <div class="sna-v10-table-head">
                            <div class="sna-v10-table-heading">
                                <span class="sna-v10-table-icon" aria-hidden="true">◎</span>
                                <div>
                                    <div class="sna-v10-table-title">Top 10 Akun Followers Terbesar</div>
                                    <div class="sna-v10-table-note">Peringkat berdasarkan followers tertinggi untuk menggambarkan potensi jangkauan akun.</div>
                                </div>
                            </div>
                            <span class="sna-v10-table-badge">Reach</span>
                        </div>
                        <div class="sna-v10-table-scroll">
                            <table class="sna-v10-table">
                                <thead><tr><th>Rank</th><th>Akun</th><th>Followers</th></tr></thead>
                                <tbody>{followers_rows}</tbody>
                            </table>
                        </div>
                    </div>
                </div>

                <details class="sna-v10-interpretation" open>
                    <summary>
                        <span class="sna-v10-interpretation-title">
                            <span class="sna-v10-interpretation-icon" aria-hidden="true">i</span>
                            Cara membaca hasil analisis
                        </span>
                        <span class="sna-v10-interpretation-chevron" aria-hidden="true">⌃</span>
                    </summary>
                    <div class="sna-v10-interpretation-content">
                        <p><strong>Degree centrality</strong> menunjukkan banyaknya koneksi langsung. <strong>In-degree</strong> menunjukkan interaksi yang masuk, sedangkan <strong>out-degree</strong> menunjukkan interaksi yang dikirim. Density yang mendekati nol menandakan jaringan renggang. Followers menunjukkan potensi jangkauan dan tidak menjadi bukti tunggal pengaruh.</p>
                        <div class="sna-v10-insight-chips">
                            <span class="sna-v10-insight-chip">Degree = konektivitas</span>
                            <span class="sna-v10-insight-chip">In-degree = interaksi masuk</span>
                            <span class="sna-v10-insight-chip">Out-degree = interaksi keluar</span>
                            <span class="sna-v10-insight-chip">Followers = potensi jangkauan</span>
                        </div>
                    </div>
                </details>
            </div>
        </section>
        """
        st.markdown(_compact_html(html), unsafe_allow_html=True)
    except Exception as exc:
        st.error(f"Gagal menampilkan statistik network IndiBiz: {exc}")


# -----------------------------------------------------------------------------
# Helper visualisasi Plotly dan tabel
# -----------------------------------------------------------------------------

def _apply_plotly_theme(fig: go.Figure, title: str = "") -> go.Figure:
    """Terapkan tema Plotly gelap yang konsisten dengan halaman lain."""
    try:
        fig.update_layout(
            template="plotly_dark",
            title={"text": title, "x": 0.0, "xanchor": "left"},
            font={"family": "Inter, sans-serif", "color": "#FFFFFF"},
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
            margin={"l": 36, "r": 22, "t": 58 if title else 28, "b": 42},
            hoverlabel={"bgcolor": "#151515", "font_color": "#FFFFFF", "bordercolor": "#2A2A2A"},
            legend={"orientation": "h", "yanchor": "bottom", "y": 1.02, "xanchor": "right", "x": 1},
        )
        fig.update_xaxes(color="#FFFFFF", tickfont={"color": "#AAAAAA"}, gridcolor="rgba(170,170,170,0.16)", zeroline=False)
        fig.update_yaxes(color="#FFFFFF", tickfont={"color": "#AAAAAA"}, gridcolor="rgba(170,170,170,0.16)", zeroline=False)
        return fig
    except Exception as exc:
        st.error(f"Gagal menerapkan tema grafik: {exc}")
        return fig


def _top_influencer_name(node_df: pd.DataFrame) -> str:
    """Ambil influencer non-brand dengan degree centrality tertinggi."""
    try:
        if node_df is None or node_df.empty:
            return "-"
        non_brand = node_df[~node_df["is_brand"]].copy()
        if non_brand.empty:
            return "-"
        top_name = str(non_brand.iloc[0]["username"]).strip()
        return top_name if top_name else "-"
    except Exception:
        return "-"


def _render_stat_card(label: str, value: str, note: str = "", extra_class: str = "") -> str:
    """Bangun HTML satu metric card."""
    safe_extra_class = escape(extra_class.strip()) if extra_class else ""
    class_attr = "sna-v9-stat" if not safe_extra_class else f"sna-v9-stat {safe_extra_class}"
    safe_value = escape(value)
    return (
        f'<div class="{class_attr}">'
        f'<div class="sna-v9-stat-label">{escape(label)}</div>'
        f'<div class="sna-v9-stat-value" title="{safe_value}">{safe_value}</div>'
        f'<div class="sna-v9-stat-note">{escape(note)}</div>'
        '</div>'
    )


def _render_metric_cards(summary: dict[str, float], node_df: pd.DataFrame) -> None:
    """Tampilkan tiga kartu statistik utama jaringan."""
    try:
        cards = [
            _render_stat_card(
                "Jumlah Node",
                f"{int(summary.get('total_nodes', 0)):,}".replace(",", "."),
                "Total akun unik dalam jaringan",
            ),
            _render_stat_card(
                "Jumlah Edge",
                f"{int(summary.get('total_edges', 0)):,}".replace(",", "."),
                "Total relasi/interaksi berarah",
            ),
            _render_stat_card(
                "Rata-rata Degree",
                f"{float(summary.get('avg_degree', 0.0)):.2f}",
                "Rata-rata koneksi per node",
            ),
        ]
        st.markdown(
            f'<div class="sna-v9-stat-row">{"".join(cards)}</div>',
            unsafe_allow_html=True,
        )
    except Exception as exc:
        st.error(f"Gagal menampilkan kartu statistik jaringan: {exc}")


def _render_telkomsel_pagerank_table(node_df: pd.DataFrame) -> None:
    """Tampilkan Top 10 node Telkomsel berdasarkan PageRank alpha 0,85."""
    try:
        if node_df is None or node_df.empty or "pagerank" not in node_df.columns:
            st.info("Ranking PageRank Telkomsel belum dapat dihitung dari graf aktif.")
            return

        top = node_df.sort_values(
            ["pagerank", "in_degree", "followers", "username"],
            ascending=[False, False, False, True],
        ).head(10).copy()
        max_pagerank = float(top["pagerank"].max() or 0.0)
        rows_html: list[str] = []
        for rank, (_, row) in enumerate(top.iterrows(), 1):
            username = str(row.get("username", "-"))
            platform_label = row.get("platform_label", "Tidak diketahui")
            platform_group = row.get("platform_group", row.get("platform", "unknown"))
            rank_class = f"sna-v12-rank-{rank}" if rank <= 3 else ""
            row_class = "sna-v12-row-top" if rank <= 3 else ""
            rows_html.append(
                f'<tr class="{row_class}">'
                f'<td><span class="sna-v9-rank-pill {rank_class}">#{rank}</span></td>'
                f'<td><span class="sna-v9-username-cell" title="{escape(username)}">{escape(username)}</span></td>'
                f'<td>{_score_bar_html(row.get("pagerank", 0), max_pagerank, 8)}</td>'
                f'<td class="sna-v9-num-cell">{_format_integer(row.get("in_degree", 0))}</td>'
                f'<td class="sna-v9-num-cell">{_format_integer(row.get("followers", 0))}</td>'
                f'<td>{_platform_chip(platform_label, platform_group)}</td>'
                '</tr>'
            )

        with st.container(border=True):
            st.markdown('<span class="sna-v9-section-marker"></span>', unsafe_allow_html=True)
            table_html = f'''
                <div class="sna-v9-section-head">
                    <div>
                        <h2 class="sna-v9-section-title">Top 10 Node Telkomsel berdasarkan PageRank</h2>
                        <p class="sna-v9-section-subtitle">PageRank memakai alpha 0,85 dan bobot frekuensi interaksi. Tabel mencakup akun brand dan akun publik agar struktur pengaruh graf dapat diperiksa secara utuh.</p>
                    </div>
                    <span class="sna-v12-live-badge"><span class="sna-v12-live-dot"></span>PageRank aktif</span>
                </div>
                <div class="sna-v9-influencer-table-card sna-v12-table-degree">
                    <div class="sna-v9-table-scroll">
                        <table class="sna-v9-influencer-table">
                            <thead><tr><th>Rank</th><th>Username</th><th>PageRank</th><th>In-Degree</th><th>Followers</th><th>Platform</th></tr></thead>
                            <tbody>{''.join(rows_html)}</tbody>
                        </table>
                    </div>
                </div>
            '''
            st.markdown(_compact_html(table_html), unsafe_allow_html=True)

            export_df = top[[
                "username", "pagerank", "in_degree", "followers", "platform_label"
            ]].copy()
            export_df.insert(0, "rank", range(1, len(export_df) + 1))
            export_df = export_df.rename(
                columns={
                    "rank": "Rank",
                    "username": "Username",
                    "pagerank": "PageRank",
                    "in_degree": "In-Degree",
                    "followers": "Followers",
                    "platform_label": "Platform",
                }
            )
            st.download_button(
                "Unduh Top 10 PageRank Telkomsel",
                data=export_to_csv(export_df, "top10_pagerank_telkomsel"),
                file_name=get_export_filename(
                    "top10_pagerank", layanan="Telkomsel", ext="csv"
                ),
                mime="text/csv",
                key="sna_v9_download_pagerank_telkomsel",
                use_container_width=True,
            )
    except Exception as exc:
        st.error(f"Gagal menampilkan Top 10 PageRank Telkomsel: {exc}")


def _render_pagerank_overview(node_df: pd.DataFrame, service: str) -> None:
    """Render chart Top 10 PageRank dan tabel Top 40 metrik akun non-layanan."""
    try:
        if node_df is None or node_df.empty:
            st.info("Belum ada node untuk menampilkan ranking PageRank.")
            return

        ranking = node_df.copy()
        numeric_columns = [
            "followers", "degree_centrality", "in_degree", "out_degree",
            "betweenness_centrality", "pagerank",
        ]
        for column in numeric_columns:
            ranking[column] = pd.to_numeric(
                ranking.get(column, 0), errors="coerce"
            ).fillna(0)
        ranking = ranking.sort_values(
            ["pagerank", "degree_centrality", "followers", "username"],
            ascending=[False, False, False, True],
            kind="mergesort",
        ).reset_index(drop=True)

        # Top Influencer hanya berisi akun non-brand. Akun layanan resmi dan
        # turunannya tetap dipertahankan pada graph, tetapi dikeluarkan dari ranking.
        if "is_brand" in ranking.columns:
            brand_mask = ranking["is_brand"].astype(bool)
        else:
            brand_mask = ranking["username"].map(_is_brand_account)
        excluded_mask = ranking["username"].map(_is_excluded_from_influencer)
        influencer_ranking = ranking[(~brand_mask) & (~excluded_mask)].copy()

        if influencer_ranking.empty:
            st.info("Belum ada akun non-brand untuk ditampilkan pada Top 10 Influencer.")
        else:
            top10 = influencer_ranking.head(10).sort_values("pagerank", ascending=True)
            fig = go.Figure(
                go.Bar(
                    x=top10["pagerank"],
                    y=top10["username"],
                    orientation="h",
                    marker={"color": "#E53935"},
                    customdata=top10[["platform_label", "followers"]],
                    hovertemplate=(
                        "<b>%{y}</b><br>PageRank: %{x:.8f}<br>"
                        "Platform: %{customdata[0]}<br>Followers: %{customdata[1]:,.0f}"
                        "<extra></extra>"
                    ),
                )
            )
            fig.update_layout(
                height=430,
                xaxis_title="PageRank Score",
                yaxis_title="Akun / Username",
                paper_bgcolor="rgba(0,0,0,0)",
                plot_bgcolor="rgba(0,0,0,0)",
                showlegend=False,
            )
            fig = _apply_plotly_theme(fig, f"Top 10 Influencer — {service}")
            _plotly_chart_aman(
                fig,
                use_container_width=True,
                key=f"sna_pagerank_{service.lower()}",
            )

        # Tabel semua metrik menggunakan ranking akun non-layanan yang sama
        # dengan Top Influencer. Akun brand tetap dipertahankan pada graph.
        top40 = influencer_ranking.head(40).copy()
        top40.insert(0, "Rank", range(1, len(top40) + 1))
        top40 = top40[
            [
                "Rank", "username", "platform_label", "followers",
                "degree_centrality", "in_degree", "out_degree",
                "betweenness_centrality", "pagerank",
            ]
        ].rename(
            columns={
                "username": "Username",
                "platform_label": "Platform",
                "followers": "Followers",
                "degree_centrality": "Degree Centrality",
                "in_degree": "In-Degree",
                "out_degree": "Out-Degree",
                "betweenness_centrality": "Betweenness Centrality",
                "pagerank": "PageRank",
            }
        )

        with st.container(border=True):
            st.markdown('<span class="sna-v9-section-marker"></span>', unsafe_allow_html=True)
            st.markdown(
                f"""
                <div class="sna-v9-section-head">
                    <div>
                        <h2 class="sna-v9-section-title">Top 40 Node — Semua Metrik</h2>
                        <p class="sna-v9-section-subtitle">Default diurutkan berdasarkan PageRank tertinggi. Akun layanan resmi dan turunannya tidak disertakan. Klik judul kolom pada tabel untuk mengurutkan ulang.</p>
                    </div>
                    <span class="sna-v12-live-badge"><span class="sna-v12-live-dot"></span>{escape(service)}</span>
                </div>
                """,
                unsafe_allow_html=True,
            )
            st.dataframe(
                top40,
                use_container_width=True,
                hide_index=True,
                height=520,
                column_config={
                    "Rank": st.column_config.NumberColumn(format="%d"),
                    "Followers": st.column_config.NumberColumn(format="%d"),
                    "Degree Centrality": st.column_config.NumberColumn(format="%.8f"),
                    "In-Degree": st.column_config.NumberColumn(format="%d"),
                    "Out-Degree": st.column_config.NumberColumn(format="%d"),
                    "Betweenness Centrality": st.column_config.NumberColumn(format="%.8f"),
                    "PageRank": st.column_config.NumberColumn(format="%.8f"),
                },
            )
            st.download_button(
                label="⬇️ Unduh CSV Top 40 Node",
                data=top40.to_csv(index=False).encode("utf-8-sig"),
                file_name=f"top40_node_sna_{service.lower()}.csv",
                mime="text/csv",
                use_container_width=True,
                key=f"download_top40_sna_{service.lower()}",
            )
    except Exception as exc:
        st.error(f"Gagal menampilkan ranking PageRank dan tabel Top 40: {exc}")


def _display_node_table(df: pd.DataFrame, height: int = 390, mode: str = "degree") -> None:
    """Tampilkan tabel node dengan nama kolom berbahasa Indonesia."""
    try:
        if df is None or df.empty:
            st.info("Belum ada data akun untuk ditampilkan.")
            return

        table = df.copy().reset_index(drop=True)
        table.insert(0, "rank", range(1, len(table) + 1))

        if mode == "followers":
            selected = ["rank", "username", "platform_label", "followers", "degree_centrality"]
            rename_map = {
                "rank": "Rank",
                "username": "Username",
                "platform_label": "Platform",
                "followers": "Followers",
                "degree_centrality": "Degree Centrality",
            }
        else:
            selected = ["rank", "username", "platform_label", "in_degree", "out_degree", "followers"]
            rename_map = {
                "rank": "Rank",
                "username": "Username",
                "platform_label": "Platform",
                "in_degree": "In-Degree",
                "out_degree": "Out-Degree",
                "followers": "Followers",
            }

        table = table[[column for column in selected if column in table.columns]].rename(columns=rename_map)
        st.dataframe(
            table,
            use_container_width=True,
            hide_index=True,
            height=height,
            column_config={
                "Rank": st.column_config.NumberColumn(format="%d"),
                "Followers": st.column_config.NumberColumn(format="%d"),
                "Degree Centrality": st.column_config.NumberColumn(format="%.6f"),
                "In-Degree": st.column_config.NumberColumn(format="%d"),
                "Out-Degree": st.column_config.NumberColumn(format="%d"),
            },
        )
    except Exception as exc:
        st.error(f"Gagal menampilkan tabel akun: {exc}")




def _format_integer(value: Any) -> str:
    """Format angka integer dengan pemisah ribuan Indonesia."""
    try:
        return f"{int(float(value or 0)):,}".replace(",", ".")
    except Exception:
        return "0"


def _format_decimal(value: Any, digits: int = 6) -> str:
    """Format angka desimal secara aman."""
    try:
        return f"{float(value or 0):.{digits}f}"
    except Exception:
        return f"{0:.{digits}f}"




def _compact_html(html: str) -> str:
    """Padatkan HTML agar Streamlit tidak membacanya sebagai blok kode Markdown."""
    try:
        return " ".join(str(html).replace("\n", " ").split())
    except Exception:
        return str(html)

def _platform_chip(platform_label: Any, platform_raw: Any = None) -> str:
    """Bangun chip platform berwarna untuk tabel HTML."""
    try:
        label = str(platform_label or "Tidak diketahui")
        raw = str(platform_raw or "").lower().strip()
        if raw not in PLATFORM_GRAPH_COLORS:
            reverse = {v.lower(): k for k, v in PLATFORM_DISPLAY.items()}
            raw = reverse.get(label.lower(), "unknown")
        color = PLATFORM_GRAPH_COLORS.get(raw, PLATFORM_GRAPH_COLORS["unknown"])
        return (
            '<span class="sna-v9-platform-chip">'
            f'<span class="sna-v9-platform-chip-dot" style="background:{escape(color)}"></span>'
            f'{escape(label)}'
            '</span>'
        )
    except Exception:
        return '<span class="sna-v9-platform-chip"><span class="sna-v9-platform-chip-dot"></span>Tidak diketahui</span>'


def _score_bar_html(value: Any, max_value: float, digits: int = 6) -> str:
    """Bangun visual bar kecil untuk metrik numerik tanpa library tambahan."""
    try:
        numeric_value = float(value or 0)
        denominator = float(max_value or 0)
        percent = 0 if denominator <= 0 else max(2, min(100, (numeric_value / denominator) * 100))
        label = _format_decimal(numeric_value, digits)
        return (
            '<div class="sna-v9-score-wrap">'
            f'<span class="sna-v9-score-text">{escape(label)}</span>'
            '<span class="sna-v9-score-bar">'
            f'<span class="sna-v9-score-fill" style="width:{percent:.2f}%"></span>'
            '</span>'
            '</div>'
        )
    except Exception:
        return '<span class="sna-v9-score-text">0.000000</span>'


def _row_value(row: pd.Series, column: str, default: Any = "") -> Any:
    """Ambil nilai row secara aman."""
    try:
        value = row.get(column, default)
        if pd.isna(value):
            return default
        return value
    except Exception:
        return default


def _render_influencer_summary_cards(non_brand: pd.DataFrame) -> None:
    """Tampilkan ringkasan kecil di atas tabel influencer."""
    try:
        if non_brand is None or non_brand.empty:
            st.markdown(
                '<div class="sna-v9-influencer-control-note">Belum ada akun non-brand untuk diringkas.</div>',
                unsafe_allow_html=True,
            )
            return

        top_degree = non_brand.sort_values(["degree_centrality", "followers"], ascending=[False, False]).iloc[0]
        positive_followers = non_brand[
            pd.to_numeric(non_brand["followers"], errors="coerce").fillna(0).gt(0)
        ].copy()
        platform_counts = non_brand["platform_label"].value_counts()
        dominant_platform = str(platform_counts.index[0]) if not platform_counts.empty else "-"
        dominant_count = int(platform_counts.iloc[0]) if not platform_counts.empty else 0

        if positive_followers.empty:
            reach_value = "Belum tersedia"
            reach_title = "Data followers belum tersedia"
            reach_note = "Sumber Twitter/X tidak memuat followers"
        else:
            top_followers = positive_followers.sort_values(
                ["followers", "degree_centrality"], ascending=[False, False]
            ).iloc[0]
            reach_value = str(_row_value(top_followers, "username", "-"))
            reach_title = reach_value
            reach_note = f"Followers {_format_integer(_row_value(top_followers, 'followers', 0))}"

        html = f"""
        <div class="sna-v9-influencer-summary">
            <div class="sna-v9-influencer-mini-card sna-v12-summary-degree">
                <div class="sna-v12-summary-top">
                    <span class="sna-v12-summary-icon">◎</span>
                    <span class="sna-v12-summary-tag">Struktural</span>
                </div>
                <span class="sna-v9-influencer-mini-label">Aktor sentral</span>
                <span class="sna-v9-influencer-mini-value" title="{escape(str(_row_value(top_degree, 'username', '-')))}">{escape(str(_row_value(top_degree, 'username', '-')))}</span>
                <span class="sna-v9-influencer-mini-note">Degree centrality {_format_decimal(_row_value(top_degree, 'degree_centrality', 0), 6)}</span>
            </div>
            <div class="sna-v9-influencer-mini-card sna-v12-summary-reach">
                <div class="sna-v12-summary-top">
                    <span class="sna-v12-summary-icon">↗</span>
                    <span class="sna-v12-summary-tag">Jangkauan</span>
                </div>
                <span class="sna-v9-influencer-mini-label">Jangkauan terbesar</span>
                <span class="sna-v9-influencer-mini-value" title="{escape(reach_title)}">{escape(reach_value)}</span>
                <span class="sna-v9-influencer-mini-note">{escape(reach_note)}</span>
            </div>
            <div class="sna-v9-influencer-mini-card sna-v12-summary-platform">
                <div class="sna-v12-summary-top">
                    <span class="sna-v12-summary-icon">◉</span>
                    <span class="sna-v12-summary-tag">Komposisi</span>
                </div>
                <span class="sna-v9-influencer-mini-label">Platform dominan</span>
                <span class="sna-v9-influencer-mini-value">{escape(dominant_platform)}</span>
                <span class="sna-v9-influencer-mini-note">{_format_integer(dominant_count)} akun pada tabel aktif</span>
            </div>
        </div>
        """
        st.markdown(_compact_html(html), unsafe_allow_html=True)
    except Exception as exc:
        st.error(f"Gagal menampilkan ringkasan influencer: {exc}")


def _build_influencer_html_table(df: pd.DataFrame, title: str, subtitle: str, mode: str, max_rows: int) -> str:
    """Bangun tabel influencer HTML yang ringan dan responsif."""
    try:
        safe_title = escape(title)
        safe_subtitle = escape(subtitle)
        table_mode_class = "sna-v12-table-followers" if mode == "followers" else "sna-v12-table-degree"
        if df is None or df.empty:
            empty_message = (
                "Data followers belum tersedia pada sumber Twitter/X ini."
                if mode == "followers"
                else "Tidak ada akun yang sesuai dengan filter tabel."
            )
            return _compact_html(f"""
            <div class="sna-v9-influencer-table-card {table_mode_class}">
                <div class="sna-v9-influencer-table-head">
                    <div>
                        <div class="sna-v9-influencer-table-title">{safe_title}</div>
                        <div class="sna-v9-influencer-table-subtitle">{safe_subtitle}</div>
                    </div>
                    <span class="sna-v9-influencer-table-badge">0 akun</span>
                </div>
                <div class="sna-v9-empty">{escape(empty_message)}</div>
            </div>
            """)

        view_df = df.copy().reset_index(drop=True).head(int(max_rows))
        max_degree = float(view_df.get("degree_centrality", pd.Series([0])).max() or 0)
        max_followers = float(view_df.get("followers", pd.Series([0])).max() or 0)

        if mode == "followers":
            headers = ["Rank", "Username", "Platform", "Followers", "Degree", "In", "Out"]
        else:
            headers = ["Rank", "Username", "Platform", "Degree", "In", "Out", "Followers"]

        header_html = "".join(f"<th>{escape(header)}</th>" for header in headers)
        rows_html: list[str] = []
        for index, row in view_df.iterrows():
            rank = index + 1
            username = str(_row_value(row, "username", "-"))
            platform_label = _row_value(row, "platform_label", "Tidak diketahui")
            platform_raw = _row_value(row, "platform_group", _row_value(row, "platform", "unknown"))
            followers = _row_value(row, "followers", 0)
            degree = _row_value(row, "degree_centrality", 0)
            in_degree = _row_value(row, "in_degree", 0)
            out_degree = _row_value(row, "out_degree", 0)

            rank_class = f"sna-v12-rank-{rank}" if rank <= 3 else ""
            row_class = "sna-v12-row-top" if rank <= 3 else ""
            username_token = "".join(character for character in username if character.isalnum())
            avatar_text = (username_token[:2] or "?").upper()
            common_cells = [
                f'<td><span class="sna-v9-rank-pill {rank_class}">#{rank}</span></td>',
                f'<td><span class="sna-v12-user-wrap"><span class="sna-v12-avatar">{escape(avatar_text)}</span><span class="sna-v9-username-cell" title="{escape(username)}">{escape(username)}</span></span></td>',
                f'<td>{_platform_chip(platform_label, platform_raw)}</td>',
            ]
            if mode == "followers":
                metric_cells = [
                    f'<td>{_score_bar_html(followers, max_followers, 0)}</td>',
                    f'<td>{_score_bar_html(degree, max_degree, 6)}</td>',
                    f'<td class="sna-v9-num-cell">{_format_integer(in_degree)}</td>',
                    f'<td class="sna-v9-num-cell">{_format_integer(out_degree)}</td>',
                ]
            else:
                metric_cells = [
                    f'<td>{_score_bar_html(degree, max_degree, 6)}</td>',
                    f'<td class="sna-v9-num-cell">{_format_integer(in_degree)}</td>',
                    f'<td class="sna-v9-num-cell">{_format_integer(out_degree)}</td>',
                    f'<td class="sna-v9-num-cell">{_format_integer(followers)}</td>',
                ]
            rows_html.append(f'<tr class="{row_class}">' + "".join(common_cells + metric_cells) + "</tr>")

        return _compact_html(f"""
        <div class="sna-v9-influencer-table-card {table_mode_class}">
            <div class="sna-v9-influencer-table-head">
                <div>
                    <div class="sna-v9-influencer-table-title">{safe_title}</div>
                    <div class="sna-v9-influencer-table-subtitle">{safe_subtitle}</div>
                </div>
                <span class="sna-v9-influencer-table-badge">Top {min(int(max_rows), len(view_df))}</span>
            </div>
            <div class="sna-v9-table-scroll">
                <table class="sna-v9-influencer-table">
                    <thead><tr>{header_html}</tr></thead>
                    <tbody>{''.join(rows_html)}</tbody>
                </table>
            </div>
        </div>
        """)
    except Exception as exc:
        return _compact_html(f'<div class="sna-v9-empty">Gagal membangun tabel influencer: {escape(str(exc))}</div>')


def _render_selected_account_detail(data_df: pd.DataFrame, selected_username: str) -> None:
    """Tampilkan detail akun terpilih dari tabel influencer."""
    try:
        if data_df is None or data_df.empty or not selected_username:
            return
        selected_df = data_df[data_df["username"].astype(str) == str(selected_username)]
        if selected_df.empty:
            return
        row = selected_df.iloc[0]
        username = escape(str(_row_value(row, "username", "-")))
        platform_label = escape(str(_row_value(row, "platform_label", "-")))
        followers_value = _format_integer(_row_value(row, "followers", 0))
        degree_value = _format_decimal(_row_value(row, "degree_centrality", 0), 6)
        in_degree_raw = _row_value(row, "in_degree", 0)
        out_degree_raw = _row_value(row, "out_degree", 0)
        in_degree_value = _format_integer(in_degree_raw)
        out_degree_value = _format_integer(out_degree_raw)
        direct_degree_series = pd.to_numeric(pd.Series([in_degree_raw, out_degree_raw]), errors="coerce").fillna(0)
        direct_degree = _format_integer(direct_degree_series.sum())

        html = f"""
        <div class="sna-v9-detail-panel">
            <div class="sna-v9-detail-header">
                <div>
                    <h3 class="sna-v9-detail-title">Detail Akun: {username}</h3>
                    <p class="sna-v9-detail-subtitle">Klik salah satu card untuk membuka keterangan singkat. Card ini bersifat ringan dan tidak menjalankan komputasi ulang.</p>
                </div>
                <span class="sna-v9-detail-chip">{platform_label} • {direct_degree} koneksi</span>
            </div>
            <div class="sna-v9-detail-grid">
                <details class="sna-v9-detail-item sna-v9-detail-platform">
                    <summary>
                        <div class="sna-v9-detail-card-top"><span class="sna-v9-detail-label">Platform</span><span class="sna-v9-detail-icon">●</span></div>
                        <span class="sna-v9-detail-value">{platform_label}</span>
                        <span class="sna-v9-detail-hint">Sumber jaringan akun</span>
                    </summary>
                    <div class="sna-v9-detail-more">Menunjukkan platform asal node dalam graf. Warna node pada visualisasi mengikuti kelompok platform ini.</div>
                </details>
                <details class="sna-v9-detail-item sna-v9-detail-followers">
                    <summary>
                        <div class="sna-v9-detail-card-top"><span class="sna-v9-detail-label">Followers</span><span class="sna-v9-detail-icon">↗</span></div>
                        <span class="sna-v9-detail-value">{followers_value}</span>
                        <span class="sna-v9-detail-hint">Potensi jangkauan</span>
                    </summary>
                    <div class="sna-v9-detail-more">Followers digunakan sebagai indikator potensi jangkauan, bukan bukti pengaruh kausal.</div>
                </details>
                <details class="sna-v9-detail-item sna-v9-detail-degree">
                    <summary>
                        <div class="sna-v9-detail-card-top"><span class="sna-v9-detail-label">Degree</span><span class="sna-v9-detail-icon">✦</span></div>
                        <span class="sna-v9-detail-value">{degree_value}</span>
                        <span class="sna-v9-detail-hint">Kekuatan posisi node</span>
                    </summary>
                    <div class="sna-v9-detail-more">Degree centrality membaca seberapa kuat akun terhubung langsung dalam jaringan percakapan aktif.</div>
                </details>
                <details class="sna-v9-detail-item sna-v9-detail-in">
                    <summary>
                        <div class="sna-v9-detail-card-top"><span class="sna-v9-detail-label">In-Degree</span><span class="sna-v9-detail-icon">←</span></div>
                        <span class="sna-v9-detail-value">{in_degree_value}</span>
                        <span class="sna-v9-detail-hint">Relasi masuk</span>
                    </summary>
                    <div class="sna-v9-detail-more">In-degree menunjukkan jumlah relasi yang mengarah ke akun ini dari akun lain.</div>
                </details>
                <details class="sna-v9-detail-item sna-v9-detail-out">
                    <summary>
                        <div class="sna-v9-detail-card-top"><span class="sna-v9-detail-label">Out-Degree</span><span class="sna-v9-detail-icon">→</span></div>
                        <span class="sna-v9-detail-value">{out_degree_value}</span>
                        <span class="sna-v9-detail-hint">Relasi keluar</span>
                    </summary>
                    <div class="sna-v9-detail-more">Out-degree menunjukkan jumlah relasi dari akun ini menuju akun lain dalam graf.</div>
                </details>
            </div>
        </div>
        """
        st.markdown(_compact_html(html), unsafe_allow_html=True)
    except Exception as exc:
        st.error(f"Gagal menampilkan detail akun: {exc}")

def _create_degree_histogram(node_df: pd.DataFrame) -> go.Figure:
    """Buat histogram distribusi degree centrality seluruh node secara ringan."""
    try:
        if node_df is None or node_df.empty or "degree_centrality" not in node_df.columns:
            return _apply_plotly_theme(go.Figure(), "Distribusi Degree Centrality")

        values = pd.to_numeric(node_df["degree_centrality"], errors="coerce").dropna()
        if values.empty:
            return _apply_plotly_theme(go.Figure(), "Distribusi Degree Centrality")

        # Agregasi manual agar chart dan link fullscreen tetap ringan.
        bin_count = min(25, max(6, int(values.nunique())))
        bins = pd.cut(values, bins=bin_count, include_lowest=True, duplicates="drop")
        counts = bins.value_counts(sort=False)
        x_labels = [f"{interval.left:.4f} - {interval.right:.4f}" for interval in counts.index]
        centers = [(float(interval.left) + float(interval.right)) / 2 for interval in counts.index]

        fig = go.Figure(
            data=[
                go.Bar(
                    x=centers,
                    y=counts.values,
                    name="Jumlah Node",
                    legendgroup="degree_distribution",
                    showlegend=True,
                    marker=dict(
                        color="#E53935",
                        line=dict(color="rgba(255,255,255,0.18)", width=1),
                    ),
                    customdata=x_labels,
                    hovertemplate=(
                        "<b>Distribusi Degree Centrality</b><br>"
                        "Rentang degree: %{customdata}<br>"
                        "Jumlah node: %{y}<extra></extra>"
                    ),
                )
            ]
        )
        fig.update_layout(
            height=380,
            bargap=0.06,
            showlegend=True,
            legend=dict(
                orientation="h",
                yanchor="bottom",
                y=1.02,
                xanchor="right",
                x=1,
                font=dict(size=13, color="#FFFFFF"),
                bgcolor="rgba(0,0,0,0)",
            ),
            legend_title_text="",
            xaxis_title="Degree Centrality",
            yaxis_title="Jumlah Node",
        )
        return _apply_plotly_theme(fig, "Histogram Degree Centrality")
    except Exception as exc:
        st.error(f"Gagal membuat histogram degree centrality: {exc}")
        return _apply_plotly_theme(go.Figure(), "Distribusi Degree Centrality")


def _create_platform_pie(node_df: pd.DataFrame) -> go.Figure:
    """Buat pie chart distribusi node per platform."""
    try:
        if node_df is None or node_df.empty:
            return _apply_plotly_theme(go.Figure(), "Distribusi Node per Platform")

        plot_df = node_df.copy()
        plot_df["platform_chart"] = plot_df["platform"].where(~plot_df["is_brand"], "target")
        counts = plot_df["platform_chart"].value_counts().reset_index()
        counts.columns = ["platform", "jumlah"]
        counts["label"] = counts["platform"].map(PLATFORM_DISPLAY).fillna("Tidak diketahui")

        color_map = {PLATFORM_DISPLAY.get(k, k): v for k, v in PLATFORM_GRAPH_COLORS.items()}
        fig = px.pie(
            counts,
            names="label",
            values="jumlah",
            color="label",
            color_discrete_map=color_map,
            hole=0.45,
        )
        fig.update_traces(
            textposition="inside",
            textinfo="percent+label",
            hovertemplate="%{label}<br>Jumlah node: %{value}<extra></extra>",
        )

        # Judul chart sudah ditampilkan pada header card Streamlit.
        # Plotly title dihilangkan agar tidak bertabrakan dengan legend.
        fig = _apply_plotly_theme(fig, "")
        fig.update_layout(
            height=400,
            margin={"l": 22, "r": 22, "t": 24, "b": 78},
            showlegend=True,
            legend=dict(
                orientation="h",
                yanchor="top",
                y=-0.06,
                xanchor="center",
                x=0.5,
                font=dict(size=13, color="#FFFFFF"),
                bgcolor="rgba(0,0,0,0)",
                itemwidth=30,
            ),
            legend_title_text="",
        )
        return fig
    except Exception as exc:
        st.error(f"Gagal membuat pie chart platform: {exc}")
        return _apply_plotly_theme(go.Figure(), "Distribusi Node per Platform")


def _build_plotly_fullscreen_href(fig: go.Figure, title: str) -> str:
    """Buat data-URI HTML untuk membuka chart Plotly di tab layar penuh."""
    try:
        full_fig = go.Figure(fig)
        full_fig.update_layout(
            autosize=True,
            height=None,
            margin=dict(l=64, r=36, t=72, b=64),
            paper_bgcolor="#0D0D0D",
            plot_bgcolor="#111821",
            font=dict(color="#FFFFFF", family="Plus Jakarta Sans, Inter, sans-serif"),
        )
        chart_html = full_fig.to_html(
            include_plotlyjs="cdn",
            full_html=False,
            default_width="100%",
            default_height="calc(100vh - 112px)",
            config={
                "displayModeBar": True,
                "displaylogo": False,
                "responsive": True,
                "toImageButtonOptions": {"format": "png", "scale": 2},
            },
        )
        page_html = f"""<!doctype html>
<html lang="id">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{escape(title)}</title>
<style>
    * {{ box-sizing: border-box; }}
    body {{
        margin: 0;
        background: #0D0D0D;
        color: #FFFFFF;
        font-family: 'Plus Jakarta Sans', Inter, sans-serif;
        overflow: hidden;
    }}
    .topbar {{
        align-items: center;
        background: linear-gradient(135deg, rgba(13,13,13,0.98), rgba(20,24,32,0.98));
        border-bottom: 1px solid #2A2A2A;
        display: flex;
        gap: 12px;
        height: 64px;
        justify-content: space-between;
        padding: 0 18px;
    }}
    h1 {{
        font-size: 18px;
        letter-spacing: -0.02em;
        margin: 0;
        overflow: hidden;
        text-overflow: ellipsis;
        white-space: nowrap;
    }}
    .actions {{ display: flex; gap: 10px; flex: 0 0 auto; }}
    button {{
        background: #E53935;
        border: 0;
        border-radius: 999px;
        color: #FFFFFF;
        cursor: pointer;
        font-weight: 800;
        padding: 10px 14px;
    }}
    button.secondary {{ background: #242424; border: 1px solid #3A3A3A; }}
    .chart-wrap {{ height: calc(100vh - 64px); padding: 14px 16px 18px; }}
</style>
</head>
<body>
    <div class="topbar">
        <h1>{escape(title)}</h1>
        <div class="actions">
            <button onclick="document.documentElement.requestFullscreen && document.documentElement.requestFullscreen()">Fullscreen Browser</button>
            <button class="secondary" onclick="window.close()">Tutup</button>
        </div>
    </div>
    <div class="chart-wrap">{chart_html}</div>
</body>
</html>"""
        encoded = base64.b64encode(page_html.encode("utf-8")).decode("ascii")
        return f"data:text/html;base64,{encoded}"
    except Exception:
        return ""


def _render_plotly_fullscreen_link(fig: go.Figure, title: str) -> None:
    """Render link lama tidak dipakai lagi; dipertahankan agar kompatibel dengan patch sebelumnya."""
    try:
        st.caption("Gunakan tombol ⛶ Layar Penuh pada header chart.")
    except Exception:
        pass


@_DIALOG_DECORATOR("Tampilan Layar Penuh", width="large")
def _tampilkan_chart_layar_penuh_sna(title: str, fig: go.Figure) -> None:
    """Tampilkan chart SNA dalam dialog seperti pola halaman Dataset."""
    try:
        st.markdown(
            '<div class="sna-v9-fullscreen-heading">'
            f'<div class="sna-v9-fullscreen-title">{escape(title)}</div>'
            '<div class="sna-v9-fullscreen-hint">Gunakan toolbar Plotly untuk zoom, pan, reset, atau unduh PNG. Klik legenda untuk menyembunyikan/menampilkan kategori jika tersedia.</div>'
            '</div>',
            unsafe_allow_html=True,
        )

        fig_besar = go.Figure(fig)

        # Fullscreen memakai judul dialog di luar area Plotly.
        # Judul bawaan Plotly sengaja dihapus agar tidak bertabrakan
        # dengan legenda ketika chart dibuka dalam mode layar penuh.
        fig_besar.update_layout(
            title=dict(text=""),
            height=820,
            autosize=True,
            margin=dict(l=68, r=48, t=104, b=76),
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
            legend=dict(
                orientation="h",
                yanchor="bottom",
                y=1.075,
                xanchor="center",
                x=0.5,
                bgcolor="rgba(26,26,26,0.92)",
                bordercolor="#343434",
                borderwidth=1,
                font=dict(family="Plus Jakarta Sans, Inter, sans-serif", color="#EAEAEA", size=14),
                itemclick="toggle",
                itemdoubleclick=False,
                traceorder="normal",
            ),
            transition=dict(duration=280, easing="cubic-in-out"),
        )
        _plotly_chart_aman(
            fig_besar,
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
        st.error("Grafik belum dapat ditampilkan dalam layar penuh. Tutup dialog ini lalu coba kembali.")
        st.code(str(exc))


# -----------------------------------------------------------------------------
# Fase 9 — visualisasi graf statis akademik IndiBiz berbasis Plotly
# -----------------------------------------------------------------------------

@st.cache_data(show_spinner=False, max_entries=8)
def _build_indibiz_static_graph_figure(
    indibiz_df: pd.DataFrame,
) -> tuple[go.Figure, dict[str, Any]]:
    """Bangun graf statis akademik IndiBiz yang ringkas, berwarna, dan mudah dibaca."""
    try:
        prepared = _prepare_sna_dataframe(indibiz_df)
        prepared = prepared[prepared["layanan"].eq("IndiBiz")].copy()
        graph, node_df, _, base_summary = _analyze_network(
            prepared,
            calculate_pagerank=True,
        )
        if graph.number_of_nodes() == 0 or node_df.empty:
            return _apply_plotly_theme(go.Figure(), ""), base_summary

        ranked = node_df.copy()
        for column in [
            "pagerank", "degree_centrality", "followers", "degree",
            "in_degree", "out_degree",
        ]:
            ranked[column] = pd.to_numeric(
                ranked.get(column, 0), errors="coerce"
            ).fillna(0)
        ranked = ranked.sort_values(
            ["pagerank", "degree_centrality", "followers", "username"],
            ascending=[False, False, False, True],
            kind="mergesort",
        ).reset_index(drop=True)

        brand_ranked = ranked[ranked["is_brand"].astype(bool)].head(6)
        if TARGET_NODE in graph.nodes:
            center_node = TARGET_NODE
        elif not brand_ranked.empty:
            center_node = str(brand_ranked.iloc[0]["username"])
        else:
            center_node = str(ranked.iloc[0]["username"])

        # Kuota sengaja dibatasi agar graf akademik tidak kembali penuh label.
        platform_quota = {"twitter": 18, "instagram": 14, "tiktok": 14}
        selected_names: list[str] = []

        def _append_unique(values: list[str]) -> None:
            for value in values:
                name = str(value)
                if name in graph.nodes and name not in selected_names:
                    selected_names.append(name)

        _append_unique([center_node])
        _append_unique(brand_ranked["username"].astype(str).tolist())
        for platform_name, quota in platform_quota.items():
            candidates = ranked[
                (~ranked["is_brand"].astype(bool))
                & ranked["platform_group"].astype(str).eq(platform_name)
            ].head(quota)
            _append_unique(candidates["username"].astype(str).tolist())

        # Isi sisa slot dengan node terbaik lintas platform, maksimal 56 node.
        _append_unique(ranked["username"].astype(str).tolist())
        selected_names = selected_names[:56]
        selected_graph = graph.subgraph(selected_names).copy()

        # Hapus node benar-benar terisolasi, tetapi pertahankan node pusat.
        isolates = [
            node for node in nx.isolates(selected_graph)
            if str(node) != center_node
        ]
        selected_graph.remove_nodes_from(isolates)
        selected_nodes = ranked[
            ranked["username"].isin(selected_graph.nodes)
        ].copy()
        if selected_graph.number_of_nodes() == 0 or selected_nodes.empty:
            return _apply_plotly_theme(go.Figure(), ""), base_summary

        lookup = selected_nodes.set_index("username")
        visual_groups: dict[str, list[str]] = {
            "target": [], "twitter": [], "instagram": [], "tiktok": [], "unknown": []
        }
        for username in selected_graph.nodes:
            row = lookup.loc[username]
            group = "target" if bool(row.get("is_brand", False)) else str(
                row.get("platform_group", "unknown")
            )
            if group not in visual_groups:
                group = "unknown"
            visual_groups[group].append(str(username))

        for group_name in visual_groups:
            visual_groups[group_name].sort(
                key=lambda name: (
                    -float(lookup.loc[name].get("pagerank", 0.0)),
                    -float(lookup.loc[name].get("degree_centrality", 0.0)),
                    name,
                )
            )

        # Layout orbit tersegmentasi: akun brand di pusat, tiap platform di sektor sendiri.
        positions: dict[str, tuple[float, float]] = {center_node: (0.0, 0.0)}
        other_brand = [name for name in visual_groups["target"] if name != center_node]
        if other_brand:
            brand_angles = np.linspace(0, 2 * np.pi, len(other_brand), endpoint=False)
            for index, username in enumerate(other_brand):
                radius = 0.64 + 0.08 * (index % 2)
                positions[username] = (
                    float(radius * np.cos(brand_angles[index])),
                    float(radius * np.sin(brand_angles[index])),
                )

        sector_config = {
            "twitter": (125.0, 235.0),
            "instagram": (15.0, 115.0),
            "tiktok": (-105.0, -5.0),
            "unknown": (238.0, 302.0),
        }
        for group_name, (start_deg, end_deg) in sector_config.items():
            names = visual_groups[group_name]
            if not names:
                continue
            ring_count = 3 if len(names) >= 9 else 2
            per_ring = max(1, int(np.ceil(len(names) / ring_count)))
            for index, username in enumerate(names):
                ring_index = index % ring_count
                slot_index = index // ring_count
                slots_in_ring = max(1, int(np.ceil((len(names) - ring_index) / ring_count)))
                fraction = (slot_index + 0.5) / slots_in_ring
                angle_deg = start_deg + (end_deg - start_deg) * fraction
                angle_deg += (ring_index - (ring_count - 1) / 2) * 3.2
                angle = np.deg2rad(angle_deg)
                radius = 1.42 + ring_index * 0.53 + 0.06 * (slot_index % 2)
                positions[username] = (
                    float(radius * np.cos(angle) * 1.16),
                    float(radius * np.sin(angle)),
                )

        # Node yang belum memperoleh posisi ditempatkan pada orbit cadangan.
        missing_positions = [node for node in selected_graph.nodes if node not in positions]
        if missing_positions:
            fallback_angles = np.linspace(0, 2 * np.pi, len(missing_positions), endpoint=False)
            for index, username in enumerate(missing_positions):
                positions[username] = (
                    float(2.65 * np.cos(fallback_angles[index])),
                    float(2.65 * np.sin(fallback_angles[index])),
                )

        # Tampilkan edge penting saja agar visual tidak kembali kusut.
        edge_rows: list[tuple[float, str, str, dict[str, Any]]] = []
        for source, target, attributes in selected_graph.edges(data=True):
            weight = float(attributes.get("weight", 1) or 1)
            importance = weight
            if source in lookup.index:
                importance += float(lookup.loc[source].get("pagerank", 0.0)) * 1000
            if target in lookup.index:
                importance += float(lookup.loc[target].get("pagerank", 0.0)) * 1000
            edge_rows.append((importance, str(source), str(target), attributes))
        edge_rows.sort(key=lambda item: item[0], reverse=True)
        edge_rows = edge_rows[:180]

        regular_x: list[float | None] = []
        regular_y: list[float | None] = []
        brand_x: list[float | None] = []
        brand_y: list[float | None] = []
        for _, source, target, _ in edge_rows:
            if source not in positions or target not in positions:
                continue
            x0, y0 = positions[source]
            x1, y1 = positions[target]
            target_x = brand_x if (source == center_node or target == center_node) else regular_x
            target_y = brand_y if (source == center_node or target == center_node) else regular_y
            target_x.extend([x0, x1, None])
            target_y.extend([y0, y1, None])

        traces: list[go.Scatter] = [
            go.Scatter(
                x=regular_x,
                y=regular_y,
                mode="lines",
                line={"width": 0.85, "color": "rgba(148,163,184,0.19)"},
                hoverinfo="skip",
                showlegend=False,
            ),
            go.Scatter(
                x=brand_x,
                y=brand_y,
                mode="lines",
                line={"width": 1.25, "color": "rgba(229,57,53,0.34)"},
                hoverinfo="skip",
                showlegend=False,
            ),
        ]

        max_pagerank = max(float(selected_nodes["pagerank"].max()), 1.0e-12)
        max_followers = max(float(selected_nodes["followers"].max()), 1.0)
        label_nodes: set[str] = {center_node}
        label_nodes.update(other_brand[:4])
        for group_name in ["twitter", "instagram", "tiktok"]:
            label_nodes.update(visual_groups[group_name][:3])

        group_labels = {
            "target": "Akun Brand IndiBiz",
            "twitter": "Twitter/X",
            "instagram": "Instagram",
            "tiktok": "TikTok",
            "unknown": "Platform lain",
        }
        for group_name in ["twitter", "instagram", "tiktok", "target", "unknown"]:
            names = visual_groups[group_name]
            if not names:
                continue
            xs: list[float] = []
            ys: list[float] = []
            sizes: list[float] = []
            outline_colors: list[str] = []
            hover_rows: list[list[Any]] = []
            labels: list[str] = []
            text_positions: list[str] = []
            for username in names:
                row = lookup.loc[username]
                x, y = positions[username]
                pagerank = float(row.get("pagerank", 0.0))
                followers = float(row.get("followers", 0.0))
                pagerank_scale = (pagerank / max_pagerank) ** 0.5
                follower_scale = np.log1p(followers) / np.log1p(max_followers)
                size = 15 + 31 * pagerank_scale + 7 * follower_scale
                if username == center_node:
                    size = max(size, 62)
                elif group_name == "target":
                    size = max(size, 29)
                sentiment = _normalize_sentiment(row.get("dominant_sentiment", "unknown"))
                outline_color = SENTIMENT_COLORS.get(sentiment, "#F8FAFC")
                label = username if username in label_nodes else ""
                if len(label) > 18:
                    label = f"{label[:15]}..."
                xs.append(x)
                ys.append(y)
                sizes.append(float(min(size, 68)))
                outline_colors.append(outline_color)
                labels.append(label)
                if username == center_node:
                    text_positions.append("bottom center")
                elif x >= 0:
                    text_positions.append("middle left")
                else:
                    text_positions.append("middle right")
                hover_rows.append([
                    str(row.get("platform_label", "Tidak diketahui")),
                    int(row.get("followers", 0)),
                    int(row.get("degree", 0)),
                    pagerank,
                    str(row.get("sentiment_label", "Belum tersedia")),
                ])

            traces.append(
                go.Scatter(
                    x=xs,
                    y=ys,
                    mode="markers+text",
                    name=group_labels[group_name],
                    text=labels,
                    textposition=text_positions,
                    textfont={"family": "Inter", "size": 10, "color": "#F8FAFC"},
                    customdata=hover_rows,
                    hovertemplate=(
                        "<b>%{text}</b><br>Platform: %{customdata[0]}"
                        "<br>Followers: %{customdata[1]:,}"
                        "<br>Degree: %{customdata[2]:,}"
                        "<br>PageRank: %{customdata[3]:.8f}"
                        "<br>Sentimen: %{customdata[4]}<extra></extra>"
                    ),
                    marker={
                        "size": sizes,
                        "color": PLATFORM_GRAPH_COLORS.get(
                            group_name, PLATFORM_GRAPH_COLORS["unknown"]
                        ),
                        "line": {"width": 2.2, "color": outline_colors},
                        "opacity": 0.94,
                    },
                    showlegend=True,
                )
            )

        figure = go.Figure(data=traces)
        figure.add_shape(
            type="circle",
            xref="x", yref="y",
            x0=-0.62, y0=-0.62, x1=0.62, y1=0.62,
            fillcolor="rgba(229,57,53,0.055)",
            line={"color": "rgba(229,57,53,0.16)", "width": 1},
            layer="below",
        )
        figure.add_annotation(
            x=0,
            y=0.78,
            text="PUSAT JARINGAN INDIBIZ",
            showarrow=False,
            font={"family": "Plus Jakarta Sans", "size": 11, "color": "#FF8A87"},
            bgcolor="rgba(127,29,29,0.34)",
            bordercolor="rgba(229,57,53,0.30)",
            borderpad=5,
        )
        figure.update_layout(
            height=720,
            xaxis={"visible": False, "range": [-3.35, 3.35], "fixedrange": False},
            yaxis={
                "visible": False,
                "range": [-3.0, 3.0],
                "scaleanchor": "x",
                "scaleratio": 1,
                "fixedrange": False,
            },
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
            margin={"l": 22, "r": 22, "t": 68, "b": 22},
            hoverlabel={
                "bgcolor": "#111827",
                "bordercolor": "#334155",
                "font": {"family": "Inter", "size": 12, "color": "#F8FAFC"},
            },
            legend={
                "orientation": "h",
                "yanchor": "bottom",
                "y": 1.02,
                "xanchor": "center",
                "x": 0.5,
                "bgcolor": "rgba(15,23,42,0.76)",
                "bordercolor": "rgba(148,163,184,0.22)",
                "borderwidth": 1,
                "font": {"family": "Inter", "size": 11, "color": "#E5E7EB"},
            },
            dragmode="pan",
            uirevision="indibiz-static-v13",
        )

        platform_counts = {
            group: len(names) for group, names in visual_groups.items()
        }
        summary = {
            **base_summary,
            "nodes": int(selected_graph.number_of_nodes()),
            "edges": int(selected_graph.number_of_edges()),
            "density": float(nx.density(selected_graph))
            if selected_graph.number_of_nodes() > 1 else 0.0,
            "center_node": center_node,
            "twitter": int(platform_counts.get("twitter", 0)),
            "instagram": int(platform_counts.get("instagram", 0)),
            "tiktok": int(platform_counts.get("tiktok", 0)),
            "target": int(platform_counts.get("target", 0)),
            "removed_isolates": int(len(isolates)),
            "layout": "segmented_orbit",
        }
        return _apply_plotly_theme(figure, ""), summary
    except Exception as exc:
        raise RuntimeError(f"Gagal membangun graf statis Plotly IndiBiz: {exc}") from exc


def _render_compact_html(html_content: str) -> None:
    """Render HTML tanpa baris berindentasi agar tidak dibaca sebagai blok kode Markdown."""
    compact_html = "".join(line.strip() for line in dedent(html_content).splitlines())
    st.markdown(compact_html, unsafe_allow_html=True)


def _render_indibiz_static_network_graph(indibiz_df: pd.DataFrame) -> None:
    """Render graf statis akademik IndiBiz dengan komposisi yang mudah dibaca."""
    try:
        with st.container(border=True):
            st.markdown(
                '<span class="sna-v13-indibiz-static-marker"></span>',
                unsafe_allow_html=True,
            )
            figure, summary = _build_indibiz_static_graph_figure(indibiz_df)
            center_node = escape(str(summary.get("center_node", "IndiBiz")))
            _render_compact_html(
                f"""
                <div class="sna-v13-static-head">
                    <div>
                        <h2 class="sna-v13-static-title">Graf Statis Akademik IndiBiz</h2>
                        <p class="sna-v13-static-subtitle">Komposisi jaringan dibuat tersegmentasi agar akun tidak menumpuk. Warna isi node menunjukkan platform, garis luar menunjukkan sentimen dominan, dan ukuran node mengikuti PageRank.</p>
                    </div>
                    <span class="sna-v13-static-badge">Visualisasi Akademik</span>
                </div>
                <div class="sna-v13-static-guide">
                    <div class="sna-v13-guide-item"><span class="sna-v13-guide-icon" style="background:rgba(29,161,242,.15);color:#6FC4FF;">●</span><span><strong style="color:#F8FAFC;">Warna isi</strong><br>Platform akun</span></div>
                    <div class="sna-v13-guide-item"><span class="sna-v13-guide-icon" style="background:rgba(76,175,80,.14);color:#7DDB82;">◎</span><span><strong style="color:#F8FAFC;">Garis luar</strong><br>Sentimen dominan</span></div>
                    <div class="sna-v13-guide-item"><span class="sna-v13-guide-icon" style="background:rgba(229,57,53,.14);color:#FF8A87;">↗</span><span><strong style="color:#F8FAFC;">Ukuran node</strong><br>Skor PageRank</span></div>
                </div>
                <div class="sna-v13-static-kpis">
                    <div class="sna-v13-static-kpi"><span class="sna-v13-static-kpi-label">Node ditampilkan</span><span class="sna-v13-static-kpi-value">{int(summary.get('nodes', 0)):,}</span></div>
                    <div class="sna-v13-static-kpi"><span class="sna-v13-static-kpi-label">Edge aktif</span><span class="sna-v13-static-kpi-value">{int(summary.get('edges', 0)):,}</span></div>
                    <div class="sna-v13-static-kpi"><span class="sna-v13-static-kpi-label">Density</span><span class="sna-v13-static-kpi-value">{float(summary.get('density', 0.0)):.5f}</span></div>
                    <div class="sna-v13-static-kpi"><span class="sna-v13-static-kpi-label">Node pusat visual</span><span class="sna-v13-static-kpi-value" title="{center_node}">{center_node}</span></div>
                </div>
                """
            )
            _plotly_chart_aman(
                figure,
                config={
                    "displayModeBar": True,
                    "displaylogo": False,
                    "responsive": True,
                    "scrollZoom": True,
                    "toImageButtonOptions": {
                        "format": "png",
                        "filename": "graf_statis_akademik_indibiz",
                        "scale": 2,
                    },
                    "modeBarButtonsToRemove": ["lasso2d", "select2d"],
                },
                key="sna_indibiz_static_plotly_v13",
                **_opsi_lebar_penuh(st.plotly_chart),
            )
            st.caption(
                "Label hanya ditampilkan pada node penting. Arahkan kursor ke node lain untuk melihat username, platform, followers, degree, PageRank, dan sentimennya."
            )
    except Exception as exc:
        st.error(f"Gagal menampilkan graf statis akademik IndiBiz: {exc}")


# -----------------------------------------------------------------------------
# Pyvis network graph


# -----------------------------------------------------------------------------
# Pyvis network graph
# -----------------------------------------------------------------------------

def _hash_digraph_for_cache(graph: nx.DiGraph) -> tuple[Any, ...]:
    """Buat hash stabil dari node, edge, dan atribut edge untuk cache PyVis."""
    try:
        nodes = tuple(sorted(str(node) for node in graph.nodes()))
        edges: list[tuple[str, str, tuple[tuple[str, str], ...]]] = []
        for source, target, attributes in graph.edges(data=True):
            attr_items = tuple(
                sorted((str(key), repr(value)) for key, value in attributes.items())
            )
            edges.append((str(source), str(target), attr_items))
        return nodes, tuple(sorted(edges))
    except Exception:
        return (repr(graph),)


def _ensure_indibiz_platform_representatives(
    graph: nx.DiGraph,
    node_df: pd.DataFrame,
    minimum_per_platform: int = 2,
) -> tuple[nx.DiGraph, pd.DataFrame]:
    """Pastikan graf visual IndiBiz memiliki wakil nyata dari tiap platform.

    Sumber SNA IndiBiz lama dapat hanya berisi edge Twitter/X. Saat itu terjadi,
    fungsi ini mengambil akun non-brand yang benar-benar ada pada dataset
    sentimen IndiBiz untuk menjadi wakil Instagram/TikTok pada visualisasi.
    Akun tambahan tidak diberi edge buatan, sehingga struktur relasi SNA asli
    tidak dipalsukan. Statistik utama tetap dihitung dari graf SNA asli.
    """
    try:
        if graph is None or node_df is None or node_df.empty:
            return graph.copy(), node_df.copy()

        visual_graph = graph.copy()
        visual_nodes = node_df.copy()
        if "platform_group" not in visual_nodes.columns:
            return visual_graph, visual_nodes

        target_minimum = max(1, int(minimum_per_platform))
        current_counts = (
            visual_nodes.loc[~visual_nodes["is_brand"].astype(bool), "platform_group"]
            .astype(str)
            .value_counts()
            .to_dict()
        )
        missing_platforms = [
            platform
            for platform in PLATFORM_ORDER
            if int(current_counts.get(platform, 0)) < target_minimum
        ]
        if not missing_platforms:
            return visual_graph, visual_nodes

        # Jangan memakai dummy untuk membuat representasi platform. Wakil
        # Instagram/TikTok hanya boleh berasal dari sumber IndiBiz aktual.
        if not sentiment_file_exists("IndiBiz"):
            return visual_graph, visual_nodes

        sentiment_df = load_sentiment_data("IndiBiz")
        if (
            sentiment_df is None
            or sentiment_df.empty
            or bool(sentiment_df.attrs.get("is_dummy", False))
            or str(sentiment_df.attrs.get("data_source", "")).lower() == "dummy"
        ):
            return visual_graph, visual_nodes
        if "username" not in sentiment_df.columns or "platform" not in sentiment_df.columns:
            return visual_graph, visual_nodes

        candidates = sentiment_df.copy()
        candidates["username"] = candidates["username"].map(_normalize_username)
        candidates["platform_group"] = candidates["platform"].map(_normalize_platform)
        if "followers" not in candidates.columns:
            candidates["followers"] = 0
        candidates["followers"] = (
            pd.to_numeric(candidates["followers"], errors="coerce")
            .fillna(0)
            .clip(lower=0)
            .astype(int)
        )

        sentiment_column = next(
            (
                column
                for column in ["predicted_sentiment", "sentiment", "label", "sentimen"]
                if column in candidates.columns
            ),
            None,
        )
        if sentiment_column is None:
            candidates["dominant_sentiment"] = "unknown"
        else:
            candidates["dominant_sentiment"] = candidates[sentiment_column].map(
                _normalize_sentiment
            )

        invalid_usernames = {"", "nan", "none", "null"}
        candidates = candidates[
            candidates["platform_group"].isin(PLATFORM_ORDER)
            & ~candidates["username"].isin(invalid_usernames)
        ].copy()
        candidates = candidates[
            ~candidates["username"].map(_hide_service_account_from_exploration_graph)
        ].copy()
        if candidates.empty:
            return visual_graph, visual_nodes

        # Satu username cukup satu kali per platform. Followers maksimum dipakai
        # agar ukuran node Instagram/TikTok mengikuti jangkauan akun terbaru.
        candidates = candidates.sort_values(
            ["platform_group", "followers", "username"],
            ascending=[True, False, True],
            kind="mergesort",
        ).drop_duplicates(["platform_group", "username"], keep="first")

        existing_usernames = set(visual_nodes["username"].astype(str))
        representative_rows: list[dict[str, Any]] = []

        for platform in missing_platforms:
            current = int(current_counts.get(platform, 0))
            needed = max(0, target_minimum - current)
            if needed <= 0:
                continue

            platform_candidates = candidates[
                candidates["platform_group"].eq(platform)
                & ~candidates["username"].isin(existing_usernames)
            ].copy()
            if platform_candidates.empty:
                continue

            for row in platform_candidates.head(needed).itertuples(index=False):
                username = str(row.username)
                followers = int(getattr(row, "followers", 0) or 0)
                sentiment = _normalize_sentiment(
                    getattr(row, "dominant_sentiment", "unknown")
                )

                # Node representatif berasal dari data aktual platform, tetapi
                # tidak diberi relasi sintetis. Dengan begitu graf tidak
                # menyatakan adanya edge yang memang tidak tersedia di SNA.
                visual_graph.add_node(
                    username,
                    followers=followers,
                    platform=platform,
                    dominant_sentiment=sentiment,
                    platform_representative=True,
                )
                representative_rows.append(
                    {
                        "username": username,
                        "platform": platform,
                        "platform_group": platform,
                        "platform_label": PLATFORM_DISPLAY.get(platform, platform.title()),
                        "followers": followers,
                        "degree": 0,
                        "degree_centrality": 0.0,
                        "betweenness_centrality": 0.0,
                        "pagerank": 0.0,
                        "in_degree": 0,
                        "out_degree": 0,
                        "dominant_sentiment": sentiment,
                        "sentiment_label": SENTIMENT_DISPLAY.get(
                            sentiment, "Belum tersedia"
                        ),
                        "is_brand": False,
                        "is_platform_representative": True,
                    }
                )
                existing_usernames.add(username)

        if representative_rows:
            additions = pd.DataFrame(representative_rows)
            visual_nodes = pd.concat([visual_nodes, additions], ignore_index=True, sort=False)
            if "is_platform_representative" not in visual_nodes.columns:
                visual_nodes["is_platform_representative"] = False
            visual_nodes["is_platform_representative"] = (
                visual_nodes["is_platform_representative"].fillna(False).astype(bool)
            )

        return visual_graph, visual_nodes.reset_index(drop=True)
    except Exception as exc:
        st.error(f"Gagal menyiapkan wakil platform pada graf IndiBiz: {exc}")
        return graph.copy(), node_df.copy()


@st.cache_data(
    show_spinner=False,
    max_entries=24,
    hash_funcs={nx.DiGraph: _hash_digraph_for_cache},
)
def _limit_graph_nodes(
    graph: nx.DiGraph,
    node_df: pd.DataFrame,
    node_limit: int,
    service: str = "",
) -> tuple[nx.DiGraph, pd.DataFrame]:
    """Batasi node secara adil agar semua platform tetap terwakili.

    Pada filter satu platform, pemilihan tetap memakai ranking metrik jaringan.
    Pada filter Semua Platform, slot non-brand dibagi merata antara Twitter/X,
    Instagram, dan TikTok yang tersedia. Khusus IndiHome dan IndiBiz, akun
    layanan turunan disembunyikan dari visualisasi. Hanya akun utama
    ``indihome``, ``indibiz``, atau ``telkomsel`` yang boleh tetap tampil
    sebagai node brand/hub merah.
    """
    try:
        limit = max(1, int(node_limit))
        graph_work = graph.copy()
        node_work = node_df.copy()
        service_key = str(service).strip().lower()

        # Terapkan aturan visual yang sama pada IndiHome dan IndiBiz:
        # akun layanan turunan/regional/care dihapus hanya dari graf interaktif.
        # Akun utama indihome, indibiz, dan telkomsel tetap boleh tampil.
        # Edge yang menempel pada akun turunan ikut tidak divisualisasikan, sama
        # seperti perilaku graf IndiHome yang sudah disetujui. Data asli tetap utuh.
        if service_key in {"indihome", "indibiz"} and not node_work.empty:
            hidden_mask = node_work["username"].map(
                _hide_service_account_from_exploration_graph
            )
            hidden_usernames = set(node_work.loc[hidden_mask, "username"].astype(str))
            if hidden_usernames:
                visible_nodes = [
                    str(node) for node in graph_work.nodes
                    if str(node) not in hidden_usernames
                ]
                graph_work = graph_work.subgraph(visible_nodes).copy()
                node_work = node_work[~node_work["username"].isin(hidden_usernames)].copy()

        if graph_work.number_of_nodes() <= limit:
            return graph_work, node_work.reset_index(drop=True)

        work = node_work[node_work["username"].isin(graph_work.nodes)].copy()
        if work.empty:
            return graph_work, node_work.reset_index(drop=True)

        # Pastikan kolom ranking numerik agar pengurutan konsisten meskipun
        # sumber CSV memiliki tipe data campuran.
        for column in ["pagerank", "degree_centrality", "followers", "degree"]:
            work[column] = pd.to_numeric(work.get(column, 0), errors="coerce").fillna(0)

        def _rank(frame: pd.DataFrame) -> pd.DataFrame:
            if frame.empty:
                return frame.copy()
            return frame.sort_values(
                ["pagerank", "degree_centrality", "followers", "degree", "username"],
                ascending=[False, False, False, False, True],
                kind="mergesort",
            )

        non_brand = work[~work["is_brand"].astype(bool)].copy()
        brand = work[work["is_brand"].astype(bool)].copy()
        available_platforms = [
            platform
            for platform in PLATFORM_ORDER
            if not non_brand[non_brand["platform_group"].eq(platform)].empty
        ]

        # Filter satu platform tidak membutuhkan pembagian kuota. Ranking lama
        # dipertahankan, tetapi akun brand tidak lagi otomatis mengalahkan semua
        # akun percakapan hanya karena statusnya sebagai brand.
        if len(available_platforms) <= 1:
            if service_key in {"indihome", "indibiz"}:
                # Sumber SNA IndiBiz aktual dapat hanya memiliki label Twitter/X.
                # Hub utama tetap wajib masuk visualisasi agar subgraf tidak
                # kehilangan pusat jaringan saat kandidat non-brand melebihi limit.
                allowed_primary_accounts = PRIMARY_SERVICE_GRAPH_ACCOUNTS
                primary_brand = brand[
                    brand["username"].map(_compact_username).isin(
                        allowed_primary_accounts
                    )
                ].copy()
                primary_names = _rank(primary_brand).head(3)["username"].tolist()
                selected_nodes = list(dict.fromkeys(primary_names))
                remaining = max(0, limit - len(selected_nodes))
                selected_nodes.extend(
                    _rank(non_brand).head(remaining)["username"].tolist()
                )
                selected_nodes = list(dict.fromkeys(selected_nodes))
                if len(selected_nodes) < limit:
                    remaining_brand = _rank(
                        brand[~brand["username"].isin(selected_nodes)]
                    )
                    selected_nodes.extend(
                        remaining_brand.head(limit - len(selected_nodes))["username"].tolist()
                    )
                    selected_nodes = list(dict.fromkeys(selected_nodes))
            else:
                ranked = pd.concat([_rank(non_brand), _rank(brand)], ignore_index=True)
                selected_nodes = ranked.drop_duplicates("username").head(limit)["username"].tolist()

            subgraph = graph_work.subgraph(selected_nodes[:limit]).copy()
            selected_df = work[work["username"].isin(selected_nodes[:limit])].copy()
            return subgraph, selected_df

        # Maksimal 10 akun brand atau sekitar 10% dari batas node. Dengan batas
        # 80 node, hasilnya paling banyak 8 akun brand sehingga platform pengguna
        # tidak tersingkir dari graf gabungan.
        brand_quota = min(len(brand), max(1, min(10, round(limit * 0.10))))
        selected: list[str] = _rank(brand).head(brand_quota)["username"].tolist()
        remaining_slots = max(0, limit - len(selected))

        platform_frames = {
            platform: _rank(non_brand[non_brand["platform_group"].eq(platform)].copy())
            for platform in available_platforms
        }
        platform_quotas = {platform: 0 for platform in available_platforms}

        # Sisihkan minimal 1-2 akun per platform, lalu isi seluruh slot sisa
        # berdasarkan ranking global. Tujuannya bukan membagi node secara sama
        # rata, tetapi memastikan Twitter/X, Instagram, dan TikTok tetap punya
        # representasi saat data platform tersebut memang tersedia.
        if available_platforms and remaining_slots > 0:
            minimum_target = 2 if remaining_slots >= (2 * len(available_platforms)) else 1
            for platform in available_platforms:
                if remaining_slots <= 0:
                    break
                quota = min(
                    minimum_target,
                    len(platform_frames[platform]),
                    remaining_slots,
                )
                platform_quotas[platform] = quota
                remaining_slots -= quota

        for platform in available_platforms:
            quota = platform_quotas[platform]
            selected.extend(platform_frames[platform].head(quota)["username"].tolist())

        # Setelah kuota minimum terpenuhi, ranking jaringan kembali menjadi
        # prioritas agar sebagian besar node tetap mencerminkan struktur SNA.
        selected = list(dict.fromkeys(selected))
        if len(selected) < limit:
            remaining_non_brand = _rank(non_brand[~non_brand["username"].isin(selected)])
            selected.extend(remaining_non_brand.head(limit - len(selected))["username"].tolist())
            selected = list(dict.fromkeys(selected))

        # Fallback terakhir bila jumlah akun non-brand memang lebih sedikit dari
        # batas visualisasi: tambahkan akun brand lain sesuai ranking.
        if len(selected) < limit:
            remaining_brand = _rank(brand[~brand["username"].isin(selected)])
            selected.extend(remaining_brand.head(limit - len(selected))["username"].tolist())
            selected = list(dict.fromkeys(selected))

        selected_nodes = selected[:limit]
        subgraph = graph_work.subgraph(selected_nodes).copy()
        selected_df = work[work["username"].isin(selected_nodes)].copy()
        return subgraph, selected_df
    except Exception as exc:
        st.error(f"Gagal membatasi jumlah node graf: {exc}")
        return graph.copy(), node_df.copy()


@st.cache_data(
    show_spinner="Menyusun graf interaktif SNA...",
    max_entries=12,
    hash_funcs={nx.DiGraph: _hash_digraph_for_cache},
)
def generate_pyvis_graph(
    graph: nx.DiGraph,
    visual_nodes: pd.DataFrame,
    dark_mode: bool = True,
    service: str = "",
) -> str:
    """Bangun HTML graf PyVis sesuai tema aktif dan aman memakai file sementara."""
    try:
        if graph.number_of_nodes() == 0 or visual_nodes.empty:
            return ""

        # PyVis hanya diperlukan saat pengguna meminta Network Graph. Halaman
        # statistik dan tabel influencer tidak perlu menanggung biaya import ini.
        from pyvis.network import Network

        graph_bg = "#0D0D0D" if dark_mode else "#F8FAFC"
        graph_text = "#FFFFFF" if dark_mode else "#1F2937"
        graph_label_stroke = "#06080C" if dark_mode else "#FFFFFF"
        graph_highlight = "#FFFFFF" if dark_mode else "#0F172A"

        net = Network(
            height="660px",
            width="100%",
            bgcolor=graph_bg,
            font_color=graph_text,
            directed=True,
            cdn_resources="in_line",
        )

        node_lookup = visual_nodes.set_index("username")
        max_pagerank = max(
            float(pd.to_numeric(visual_nodes.get("pagerank", 0), errors="coerce").fillna(0).max()),
            1.0e-12,
        )

        # Skala ukuran khusus Eksplorasi Graf SNA IndiHome dan IndiBiz:
        # Twitter/X mengikuti degree, sedangkan Instagram dan TikTok mengikuti
        # followers. Logarithmic scaling pada followers mencegah satu akun dengan
        # followers sangat besar membuat node lain nyaris tidak terlihat.
        service_graph_key = str(service).strip().lower()
        hybrid_metric_graph_mode = service_graph_key in {"indihome", "indibiz"}
        twitter_nodes = visual_nodes[visual_nodes.get("platform_group", "unknown").eq("twitter")] if "platform_group" in visual_nodes.columns else pd.DataFrame()
        instagram_nodes = visual_nodes[visual_nodes.get("platform_group", "unknown").eq("instagram")] if "platform_group" in visual_nodes.columns else pd.DataFrame()
        tiktok_nodes = visual_nodes[visual_nodes.get("platform_group", "unknown").eq("tiktok")] if "platform_group" in visual_nodes.columns else pd.DataFrame()
        max_twitter_degree = max(
            float(pd.to_numeric(twitter_nodes.get("degree", 0), errors="coerce").fillna(0).max()) if not twitter_nodes.empty else 0.0,
            1.0,
        )
        max_instagram_followers = max(
            float(pd.to_numeric(instagram_nodes.get("followers", 0), errors="coerce").fillna(0).max()) if not instagram_nodes.empty else 0.0,
            1.0,
        )
        max_tiktok_followers = max(
            float(pd.to_numeric(tiktok_nodes.get("followers", 0), errors="coerce").fillna(0).max()) if not tiktok_nodes.empty else 0.0,
            1.0,
        )

        ranked_for_labels = visual_nodes.sort_values(
            ["pagerank", "degree_centrality", "followers"],
            ascending=[False, False, False],
            kind="mergesort",
        )
        key_label_count = max(8, min(14, int(round(len(ranked_for_labels) * 0.12))))
        key_label_nodes = set(ranked_for_labels.head(key_label_count)["username"].astype(str))

        for username in graph.nodes:
            if username not in node_lookup.index:
                continue
            row = node_lookup.loc[username]
            centrality = float(row.get("degree_centrality", 0.0))
            degree_count = int(row.get("degree", 0))
            pagerank_score = float(row.get("pagerank", 0.0))
            followers = int(row.get("followers", 0))
            is_brand = bool(row.get("is_brand", False))
            platform_group = str(row.get("platform_group", "unknown"))

            if hybrid_metric_graph_mode and not is_brand and platform_group == "twitter":
                relative_degree = max(0.0, min(1.0, degree_count / max_twitter_degree))
                node_size = max(13, min(68, 13 + 55 * (relative_degree ** 0.50)))
            elif hybrid_metric_graph_mode and not is_brand and platform_group == "instagram":
                relative_followers = np.log1p(max(0, followers)) / np.log1p(max_instagram_followers)
                node_size = max(13, min(68, 13 + 55 * (relative_followers ** 0.72)))
            elif hybrid_metric_graph_mode and not is_brand and platform_group == "tiktok":
                relative_followers = np.log1p(max(0, followers)) / np.log1p(max_tiktok_followers)
                node_size = max(13, min(68, 13 + 55 * (relative_followers ** 0.72)))
            else:
                relative_pagerank = max(0.0, pagerank_score / max_pagerank)
                node_size = max(13, min(76, 13 + 63 * (relative_pagerank ** 0.42)))

            if is_brand:
                # Hub utama tetap mudah dikenali. Pada IndiHome dan IndiBiz,
                # akun layanan turunan sudah dibuang sebelum PyVis dirender.
                node_size = 82 if hybrid_metric_graph_mode else max(74, min(98, node_size * 1.22))

            platform_color = PLATFORM_GRAPH_COLORS.get(
                platform_group, PLATFORM_GRAPH_COLORS["unknown"]
            )
            dominant_sentiment = _normalize_sentiment(
                row.get("dominant_sentiment", "unknown")
            )
            # Warna node mengikuti platform agar visual konsisten dengan legenda:
            # Twitter/X = biru, Instagram = ungu, TikTok = cyan, dan akun
            # brand/hub = merah. Sentimen tetap tersedia pada tooltip, tetapi
            # tidak lagi mengganti warna utama node.
            fill_color = (
                PLATFORM_GRAPH_COLORS["target"]
                if is_brand
                else platform_color
            )
            border_color = graph_highlight if is_brand else platform_color
            platform_label = str(row.get("platform_label", "Tidak diketahui"))
            label = username if len(username) <= 22 else f"{username[:19]}..."
            is_key_label = is_brand or str(username) in key_label_nodes
            visible_label = label if is_key_label else ""
            is_platform_representative = bool(row.get("is_platform_representative", False))
            if is_brand:
                node_role = "Akun Brand / Hub"
            elif is_platform_representative:
                node_role = "Wakil platform (tanpa edge SNA)"
            else:
                node_role = "Akun Percakapan"
            label_font_size = 18 if is_brand else 12

            net.add_node(
                username,
                label=visible_label,
                # Data tooltip disimpan sebagai atribut kustom agar tampilannya
                # konsisten dan tidak memunculkan HTML mentah bawaan PyVis.
                sna_label=label,
                sna_fullname=username,
                sna_is_brand="1" if is_brand else "0",
                sna_is_key="1" if is_key_label else "0",
                sna_platform=platform_label,
                sna_followers=followers,
                sna_degree=f"{degree_count}",
                sna_degree_centrality=f"{centrality:.8f}",
                sna_pagerank=f"{pagerank_score:.8f}",
                sna_sentiment=SENTIMENT_DISPLAY.get(dominant_sentiment, "Belum tersedia"),
                sna_role=node_role,
                sna_color=fill_color,
                sna_border_color=border_color,
                sna_group_key=platform_group,
                color={
                    "background": fill_color,
                    "border": border_color,
                    "highlight": {"background": fill_color, "border": graph_highlight},
                    "hover": {"background": fill_color, "border": graph_highlight},
                },
                size=node_size,
                borderWidth=5 if is_brand else 3,
                borderWidthSelected=6,
                shape="dot",
                shadow={
                    "enabled": True,
                    "color": "rgba(229,57,53,0.52)" if is_brand else "rgba(0,0,0,0.50)",
                    "size": 18 if is_brand else 10,
                    "x": 0,
                    "y": 3,
                },
                font={
                    "color": graph_text,
                    "size": label_font_size,
                    "face": "Inter",
                    "bold": {"color": graph_text, "size": label_font_size},
                    "strokeWidth": 6 if dark_mode else 4,
                    "strokeColor": graph_label_stroke,
                    "vadjust": -3,
                },
            )

        for source, target, attributes in graph.edges(data=True):
            relation = str(attributes.get("relationship", "interaction"))
            weight = int(attributes.get("weight", 1))
            source_platform = "unknown"
            if source in node_lookup.index:
                source_platform = str(node_lookup.loc[source].get("platform_group", "unknown"))
            edge_color = PLATFORM_GRAPH_COLORS.get(
                source_platform, PLATFORM_GRAPH_COLORS["unknown"]
            )
            net.add_edge(
                source,
                target,
                sna_source=str(source),
                sna_target=str(target),
                sna_relation=relation,
                sna_weight=weight,
                value=max(1, min(weight, 6)),
                color={
                    "color": edge_color,
                    "highlight": graph_highlight,
                    "hover": "#E53935",
                    "opacity": 0.24,
                },
                width=max(0.7, min(2.6, 0.7 + (weight ** 0.5) * 0.55)),
                hoverWidth=3.2,
                selectionWidth=3.4,
                arrows={"to": {"enabled": True, "scaleFactor": 0.38}},
                smooth={"enabled": True, "type": "continuous", "roundness": 0.12},
            )

        net.set_options(
            r"""
            {
              "layout": {
                "improvedLayout": true,
                "randomSeed": 42
              },
              "physics": {
                "enabled": true,
                "forceAtlas2Based": {
                  "gravitationalConstant": -88,
                  "centralGravity": 0.0025,
                  "springLength": 165,
                  "springConstant": 0.045,
                  "damping": 0.68,
                  "avoidOverlap": 0.92
                },
                "solver": "forceAtlas2Based",
                "maxVelocity": 24,
                "minVelocity": 0.45,
                "timestep": 0.42,
                "stabilization": {
                  "enabled": true,
                  "iterations": 520,
                  "updateInterval": 40,
                  "fit": true
                }
              },
              "edges": {
                "chosen": true,
                "smooth": {"enabled": true, "type": "continuous", "roundness": 0.12},
                "arrows": {"to":{"enabled":true,"scaleFactor":0.38}}
              },
              "nodes": {
                "borderWidth": 3,
                "borderWidthSelected": 6,
                "chosen": true,
                "font": {"size":12,"color":"__GRAPH_TEXT__","face":"Inter"}
              },
              "interaction": {
                "hover": true,
                "tooltipDelay": 80,
                "dragNodes": true,
                "dragView": true,
                "zoomView": true,
                "hideEdgesOnDrag": true,
                "navigationButtons": false,
                "keyboard": false
              }
            }
            """.replace("__GRAPH_TEXT__", graph_text)
        )

        # HOTFIX WINDOWS UTF-8:
        # net.save_graph() pada beberapa versi PyVis membuka file tanpa parameter
        # encoding. Di Windows, Python kemudian memakai codec bawaan seperti
        # cp1252/charmap dan gagal ketika HTML mengandung karakter Unicode.
        # Karena itu HTML dibangkitkan sebagai string, lalu ditulis sendiri
        # dengan encoding UTF-8 yang eksplisit.
        temporary_html_path = ""
        try:
            with tempfile.NamedTemporaryFile(
                prefix="telkom_sna_",
                suffix=".html",
                delete=False,
            ) as temporary_file:
                temporary_html_path = temporary_file.name

            try:
                generated_html = net.generate_html(notebook=False)
            except TypeError:
                # Kompatibilitas dengan versi PyVis lama yang belum menerima
                # parameter notebook pada generate_html().
                generated_html = net.generate_html()

            if not isinstance(generated_html, str):
                generated_html = str(generated_html)

            with open(
                temporary_html_path,
                "w",
                encoding="utf-8",
                newline="\n",
            ) as html_file:
                html_file.write(generated_html)

            with open(temporary_html_path, "r", encoding="utf-8") as html_file:
                html = html_file.read()
        finally:
            if temporary_html_path and os.path.exists(temporary_html_path):
                try:
                    os.unlink(temporary_html_path)
                except OSError:
                    # Kegagalan menghapus file sementara tidak boleh menjatuhkan halaman.
                    pass
        custom_css = """
        <style>
            @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&family=Plus+Jakarta+Sans:wght@500;600;700;800&display=swap');
            :root {
                --sna-bg: #0D0D0D;
                --sna-card: #121821;
                --sna-card-2: #101010;
                --sna-border: #2A2A2A;
                --sna-red: #E53935;
                --sna-red-soft: rgba(229,57,53,0.16);
                --sna-blue-soft: rgba(29,161,242,0.12);
                --sna-text: #FFFFFF;
                --sna-muted: #A9A9A9;
            }
            html,
            body {
                margin: 0;
                width: 100%;
                max-width: 100%; /* FIX: batasi dokumen PyVis pada iframe. */
                min-height: 100%;
                background: var(--sna-bg);
                color: var(--sna-text);
                font-family: 'Inter', sans-serif;
                overflow-x: auto; /* FIX: sediakan scroll aman bila toolbar sangat panjang. */
                overflow-y: hidden;
            }
            *, *::before, *::after {
                box-sizing: border-box;
            }
            .sna-pyvis-shell {
                background:
                    radial-gradient(circle at 16% 10%, rgba(229,57,53,0.16), transparent 28%),
                    radial-gradient(circle at 86% 12%, rgba(29,161,242,0.14), transparent 30%),
                    linear-gradient(145deg, #0D0D0D 0%, #111827 50%, #0D0D0D 100%);
                border: 1px solid var(--sna-border);
                border-radius: 16px;
                box-shadow: inset 0 0 0 1px rgba(255,255,255,0.025), 0 18px 45px rgba(0,0,0,0.30);
                height: 850px;
                max-height: 850px;
                min-height: 850px;
                max-width: 100%; /* FIX: shell PyVis mengikuti iframe. */
                width: 100%; /* FIX: shell PyVis mengikuti iframe. */
                overflow: hidden;
                padding: 12px;
                position: relative;
                clip-path: inset(0 round 16px);
                -webkit-mask-image: -webkit-radial-gradient(white, black);
                transform: translateZ(0);
                margin-bottom: 18px;
            }
            .sna-pyvis-shell:fullscreen,
            .sna-pyvis-shell:-webkit-full-screen {
                background:
                    radial-gradient(circle at 16% 10%, rgba(229,57,53,0.18), transparent 28%),
                    radial-gradient(circle at 86% 12%, rgba(29,161,242,0.15), transparent 30%),
                    linear-gradient(145deg, #0D0D0D 0%, #111827 50%, #0D0D0D 100%);
                border: 0;
                border-radius: 0;
                box-shadow: none;
                height: 100vh;
                max-height: 100vh;
                min-height: 100vh;
                padding: 14px;
                width: 100vw;
            }
            .sna-pyvis-shell:fullscreen #mynetwork,
            .sna-pyvis-shell:-webkit-full-screen #mynetwork {
                height: calc(100vh - 126px) !important;
            }
            .sna-pyvis-shell:fullscreen .sna-pyvis-toolbar,
            .sna-pyvis-shell:-webkit-full-screen .sna-pyvis-toolbar {
                margin-bottom: 10px;
            }

            .sna-pyvis-toolbar {
                align-items: center;
                backdrop-filter: blur(14px);
                background: rgba(17,17,17,0.76);
                border: 1px solid rgba(255,255,255,0.08);
                border-radius: 14px;
                box-shadow: 0 16px 38px rgba(0,0,0,0.30);
                display: flex;
                gap: 10px;
                justify-content: space-between;
                margin-bottom: 10px;
                padding: 10px 12px;
            }
            .sna-pyvis-toolbar-title { display: grid; gap: 2px; }
            .sna-pyvis-kicker {
                color: var(--sna-red);
                font-family: 'Plus Jakarta Sans', 'Inter', sans-serif;
                font-size: 0.75rem /* FIX: minimum 12px agar terbaca di tablet */;
                font-weight: 800;
                letter-spacing: 0.13em;
                text-transform: uppercase;
            }
            .sna-pyvis-toolbar-title strong {
                color: #FFFFFF;
                font-family: 'Plus Jakarta Sans', 'Inter', sans-serif;
                font-size: 14px;
                font-weight: 800;
            }
            .sna-pyvis-actions {
                display: flex;
                flex-wrap: wrap;
                gap: 8px;
                justify-content: flex-end;
            }
            .sna-pyvis-actions button {
                background: #1A1A1A;
                border: 1px solid #343434;
                border-radius: 999px;
                color: #FFFFFF;
                cursor: pointer;
                font-family: 'Inter', sans-serif;
                font-size: 0.75rem /* FIX: minimum 12px agar terbaca di tablet */;
                font-weight: 800;
                min-height: 30px;
                padding: 7px 11px;
                transition: transform .16s ease, border-color .16s ease, background .16s ease, box-shadow .16s ease;
            }
            .sna-pyvis-actions button:hover {
                background: #242424;
                border-color: var(--sna-red);
                box-shadow: 0 0 0 3px rgba(229,57,53,0.13);
                transform: translateY(-1px);
            }
            .sna-pyvis-actions button.primary {
                background: linear-gradient(135deg, #E53935, #B71C1C);
                border-color: rgba(255,255,255,0.12);
            }
            .sna-pyvis-guide {
                align-items: center;
                background: linear-gradient(135deg, rgba(229,57,53,0.10), rgba(29,161,242,0.07));
                border: 1px solid rgba(255,255,255,0.07);
                border-radius: 12px;
                color: var(--sna-muted);
                display: flex;
                flex-wrap: wrap;
                font-size: 0.75rem /* FIX: minimum 12px agar terbaca di tablet */;
                gap: 8px;
                justify-content: space-between;
                margin-bottom: 10px;
                padding: 9px 11px;
            }
            .sna-pyvis-guide strong { color: #FFFFFF; }
            .sna-pyvis-status {
                background: rgba(0,0,0,0.20);
                border: 1px solid rgba(255,255,255,0.07);
                border-radius: 999px;
                color: #D9D9D9;
                font-weight: 700;
                padding: 5px 9px;
            }
            #mynetwork {
                background:
                    radial-gradient(circle at 12% 18%, rgba(229,57,53,0.13), transparent 28%),
                    radial-gradient(circle at 88% 16%, rgba(29,161,242,0.12), transparent 32%),
                    linear-gradient(rgba(255,255,255,0.018) 1px, transparent 1px),
                    linear-gradient(90deg, rgba(255,255,255,0.018) 1px, transparent 1px),
                    linear-gradient(180deg, #0B1119 0%, #05070A 100%) !important;
                background-size: auto, auto, 34px 34px, 34px 34px, auto !important;
                border: 0 !important;
                border-radius: 14px !important;
                box-shadow: inset 0 0 0 1px rgba(255,255,255,0.025);
                height: 660px !important;
                isolation: isolate;
                overflow: hidden !important;
                position: relative !important;
                clip-path: inset(0 round 14px);
                -webkit-mask-image: -webkit-radial-gradient(white, black);
                transform: translateZ(0);
            }
            #mynetwork::after {
                border: 1px solid rgba(255,255,255,0.14);
                border-radius: 14px;
                content: "";
                inset: 0;
                pointer-events: none;
                position: absolute;
                z-index: 50;
            }
            #mynetwork .vis-network,
            #mynetwork canvas {
                border-radius: 14px !important;
                overflow: hidden !important;
            }
            div.vis-tooltip {
                background: #151515 !important;
                border: 1px solid #2A2A2A !important;
                border-radius: 10px !important;
                box-shadow: 0 14px 34px rgba(0,0,0,.45) !important;
                color: #FFFFFF !important;
                font-family: 'Inter', sans-serif !important;
                padding: 8px 10px !important;
            }
            .sna-pyvis-platform-filter {
                align-items: center;
                background: rgba(17,17,17,0.70);
                border: 1px solid rgba(255,255,255,0.08);
                border-radius: 14px;
                display: flex;
                flex-wrap: wrap;
                gap: 8px;
                justify-content: space-between;
                margin-bottom: 10px;
                padding: 10px 12px;
            }
            .sna-pyvis-platform-label {
                color: #B8B8B8;
                font-size: 0.75rem /* FIX: minimum 12px agar terbaca di tablet */;
                font-weight: 800;
                letter-spacing: .08em;
                margin-right: 4px;
                text-transform: uppercase;
            }
            .sna-pyvis-platform-buttons {
                align-items: center;
                display: flex;
                flex-wrap: wrap;
                gap: 8px;
            }
            .sna-pyvis-platform-button {
                align-items: center;
                background: rgba(13,13,13,0.92);
                border: 1px solid rgba(255,255,255,0.11);
                border-radius: 999px;
                color: #FFFFFF;
                cursor: pointer;
                display: inline-flex;
                font-family: 'Plus Jakarta Sans', 'Inter', sans-serif;
                font-size: 12px;
                font-weight: 800;
                gap: 8px;
                line-height: 1;
                min-height: 34px;
                padding: 8px 12px;
                transition: transform .14s ease, border-color .14s ease, opacity .14s ease, background .14s ease;
                user-select: none;
            }
            .sna-pyvis-platform-button:hover {
                border-color: rgba(255,255,255,0.34);
                transform: translateY(-1px);
            }
            .sna-pyvis-platform-button.is-hidden {
                background: rgba(255,255,255,0.045);
                color: #8A8A8A;
                opacity: .58;
                text-decoration: line-through;
            }
            .sna-pyvis-platform-dot {
                border-radius: 999px;
                box-shadow: 0 0 0 3px rgba(255,255,255,0.06);
                display: inline-block;
                height: 11px;
                width: 11px;
            }
            .sna-pyvis-platform-help {
                color: #858585;
                font-size: 0.75rem /* FIX: minimum 12px agar terbaca di tablet */;
                font-weight: 700;
            }
            .sna-node-tooltip {
                background: #1A1A1A;
                border: 1px solid #E53935;
                border-radius: 8px;
                box-shadow: 0 18px 45px rgba(0,0,0,0.55), 0 0 0 1px rgba(229,57,53,0.08);
                color: #FFFFFF;
                display: none;
                font-family: 'Inter', sans-serif;
                left: 0;
                max-width: 340px;
                min-width: 275px;
                overflow: hidden;
                pointer-events: none;
                position: absolute;
                top: 0;
                transform: translate(14px, -18px);
                z-index: 1000;
            }
            .sna-node-tooltip.is-visible {
                animation: snaTooltipIn .13s ease-out;
                display: block;
            }
            @keyframes snaTooltipIn {
                from { opacity: 0; transform: translate(10px, -12px) scale(.98); }
                to { opacity: 1; transform: translate(14px, -18px) scale(1); }
            }
            .sna-node-tooltip__head {
                align-items: center;
                border-bottom: 1px solid rgba(255,255,255,0.08);
                display: flex;
                gap: 10px;
                padding: 12px 13px 10px 13px;
            }
            .sna-node-tooltip__dot {
                border: 2px solid rgba(255,255,255,0.88);
                border-radius: 999px;
                box-shadow: 0 0 0 4px rgba(255,255,255,0.06);
                display: inline-block;
                flex: 0 0 auto;
                height: 13px;
                width: 13px;
            }
            .sna-node-tooltip__name {
                color: #FFFFFF;
                display: block;
                font-family: 'Plus Jakarta Sans', 'Inter', sans-serif;
                font-size: 14px;
                font-weight: 800;
                letter-spacing: .01em;
                line-height: 1.25;
                max-width: 270px;
                overflow: hidden;
                text-overflow: ellipsis;
                white-space: nowrap;
            }
            .sna-node-tooltip__role {
                color: #BDBDBD;
                display: block;
                font-size: 0.75rem /* FIX: minimum 12px agar terbaca di tablet */;
                font-weight: 700;
                margin-top: 2px;
            }
            .sna-node-tooltip__grid {
                display: grid;
                gap: 8px;
                grid-template-columns: 1fr 1fr;
                padding: 11px 13px 13px 13px;
            }
            .sna-node-tooltip__item {
                background: rgba(255,255,255,0.045);
                border: 1px solid rgba(255,255,255,0.07);
                border-radius: 10px;
                padding: 8px 9px;
            }
            .sna-node-tooltip__label {
                color: #8E8E8E;
                display: block;
                font-size: 0.75rem /* FIX: minimum 12px agar terbaca di tablet */;
                font-weight: 800;
                letter-spacing: .07em;
                margin-bottom: 4px;
                text-transform: uppercase;
            }
            .sna-node-tooltip__value {
                color: #FFFFFF;
                display: block;
                font-size: 12px;
                font-weight: 800;
                line-height: 1.25;
                overflow: hidden;
                text-overflow: ellipsis;
                white-space: nowrap;
            }
            .sna-node-tooltip__hint {
                background: rgba(229,57,53,0.10);
                border-top: 1px solid rgba(255,255,255,0.06);
                color: #D6D6D6;
                font-size: 0.75rem /* FIX: minimum 12px agar terbaca di tablet */;
                font-weight: 700;
                padding: 8px 13px 10px 13px;
            }
            .sna-edge-tooltip {
                background:
                    radial-gradient(circle at 12% 0%, rgba(29,161,242,0.20), transparent 36%),
                    radial-gradient(circle at 88% 0%, rgba(229,57,53,0.16), transparent 34%),
                    linear-gradient(145deg, rgba(18,24,33,0.98), rgba(10,10,10,0.98));
                border: 1px solid rgba(255,255,255,0.12);
                border-left: 3px solid #1DA1F2;
                border-radius: 14px;
                box-shadow: 0 18px 45px rgba(0,0,0,0.55), 0 0 0 1px rgba(29,161,242,0.08);
                color: #FFFFFF;
                display: none;
                font-family: 'Inter', sans-serif;
                left: 0;
                max-width: 370px;
                min-width: 292px;
                overflow: hidden;
                pointer-events: none;
                position: absolute;
                top: 0;
                transform: translate(14px, -18px);
                z-index: 1001;
            }
            .sna-edge-tooltip.is-visible {
                animation: snaTooltipIn .13s ease-out;
                display: block;
            }
            .sna-edge-tooltip__head {
                align-items: center;
                border-bottom: 1px solid rgba(255,255,255,0.08);
                display: flex;
                gap: 10px;
                padding: 12px 13px 10px 13px;
            }
            .sna-edge-tooltip__icon {
                align-items: center;
                background: linear-gradient(135deg, #1DA1F2, #E53935);
                border: 2px solid rgba(255,255,255,0.88);
                border-radius: 999px;
                box-shadow: 0 0 0 4px rgba(255,255,255,0.06);
                color: #FFFFFF;
                display: inline-flex;
                flex: 0 0 auto;
                font-size: 12px;
                font-weight: 900;
                height: 24px;
                justify-content: center;
                line-height: 1;
                width: 24px;
            }
            .sna-edge-tooltip__title {
                color: #FFFFFF;
                display: block;
                font-family: 'Plus Jakarta Sans', 'Inter', sans-serif;
                font-size: 14px;
                font-weight: 900;
                letter-spacing: .01em;
                line-height: 1.25;
            }
            .sna-edge-tooltip__subtitle {
                color: #BDBDBD;
                display: block;
                font-size: 0.75rem /* FIX: minimum 12px agar terbaca di tablet */;
                font-weight: 700;
                margin-top: 2px;
            }
            .sna-edge-tooltip__flow {
                align-items: center;
                display: grid;
                gap: 8px;
                grid-template-columns: minmax(0, 1fr) auto minmax(0, 1fr);
                padding: 11px 13px 8px 13px;
            }
            .sna-edge-tooltip__node {
                background: rgba(255,255,255,0.045);
                border: 1px solid rgba(255,255,255,0.07);
                border-radius: 10px;
                min-width: 0;
                padding: 8px 9px;
            }
            .sna-edge-tooltip__arrow {
                color: #E53935;
                font-family: 'Plus Jakarta Sans', 'Inter', sans-serif;
                font-size: 18px;
                font-weight: 900;
                line-height: 1;
            }
            .sna-edge-tooltip__label {
                color: #8E8E8E;
                display: block;
                font-size: 0.75rem /* FIX: minimum 12px agar terbaca di tablet */;
                font-weight: 800;
                letter-spacing: .07em;
                margin-bottom: 4px;
                text-transform: uppercase;
            }
            .sna-edge-tooltip__value {
                color: #FFFFFF;
                display: block;
                font-size: 12px;
                font-weight: 800;
                line-height: 1.25;
                overflow: hidden;
                text-overflow: ellipsis;
                white-space: nowrap;
            }
            .sna-edge-tooltip__meta {
                display: grid;
                gap: 8px;
                grid-template-columns: 1fr 1fr;
                padding: 0 13px 13px 13px;
            }
            .sna-edge-tooltip__meta-item {
                background: rgba(255,255,255,0.045);
                border: 1px solid rgba(255,255,255,0.07);
                border-radius: 10px;
                padding: 8px 9px;
            }
            .sna-edge-tooltip__hint {
                background: rgba(29,161,242,0.10);
                border-top: 1px solid rgba(255,255,255,0.06);
                color: #D6D6D6;
                font-size: 0.75rem /* FIX: minimum 12px agar terbaca di tablet */;
                font-weight: 700;
                padding: 8px 13px 10px 13px;
            }
            @media (max-width: 720px) {
                .sna-pyvis-shell { height: 760px; min-height: 760px; max-height: 760px; }
                .sna-pyvis-toolbar { align-items: flex-start; flex-direction: column; }
                .sna-pyvis-actions { justify-content: flex-start; }
                #mynetwork { height: 560px !important; }
            }
        </style>
        """
        if not dark_mode:
            custom_css += """
            <style>
                :root {
                    --sna-bg: #F8FAFC;
                    --sna-card: #FFFFFF;
                    --sna-card-2: #F1F5F9;
                    --sna-border: #D8E0EA;
                    --sna-text: #1F2937;
                    --sna-muted: #64748B;
                }
                html,
                body {
                    background: #F8FAFC !important;
                    color: #1F2937 !important;
                }
                .sna-pyvis-shell,
                .sna-pyvis-shell:fullscreen,
                .sna-pyvis-shell:-webkit-full-screen {
                    background:
                        radial-gradient(circle at 16% 10%, rgba(229,57,53,0.07), transparent 28%),
                        radial-gradient(circle at 86% 12%, rgba(29,161,242,0.07), transparent 30%),
                        linear-gradient(145deg, #FFFFFF 0%, #F8FAFC 50%, #FFFFFF 100%) !important;
                    border-color: #D8E0EA !important;
                    box-shadow: inset 0 0 0 1px #FFFFFF, 0 12px 28px rgba(15,23,42,0.08) !important;
                }
                .sna-pyvis-toolbar,
                .sna-pyvis-platform-filter {
                    background: rgba(255,255,255,0.92) !important;
                    border-color: #D8E0EA !important;
                    box-shadow: 0 8px 22px rgba(15,23,42,0.07) !important;
                }
                .sna-pyvis-toolbar-title strong,
                .sna-pyvis-guide strong {
                    color: #1F2937 !important;
                }
                .sna-pyvis-actions button,
                .sna-pyvis-platform-button {
                    background: #FFFFFF !important;
                    border-color: #CBD5E1 !important;
                    color: #334155 !important;
                    box-shadow: 0 3px 9px rgba(15,23,42,0.04) !important;
                }
                .sna-pyvis-actions button:hover,
                .sna-pyvis-platform-button:hover {
                    background: #F8FAFC !important;
                    border-color: rgba(229,57,53,0.48) !important;
                    color: #1F2937 !important;
                }
                .sna-pyvis-actions button.primary,
                .sna-pyvis-actions button.primary:hover {
                    background: linear-gradient(135deg, #E53935, #B71C1C) !important;
                    border-color: #E53935 !important;
                    color: #FFFFFF !important;
                }
                .sna-pyvis-guide {
                    background: linear-gradient(135deg, rgba(229,57,53,0.05), rgba(29,161,242,0.04)) !important;
                    border-color: #D8E0EA !important;
                    color: #64748B !important;
                }
                .sna-pyvis-status {
                    background: #F1F5F9 !important;
                    border-color: #D8E0EA !important;
                    color: #475569 !important;
                }
                .sna-pyvis-platform-label,
                .sna-pyvis-platform-help {
                    color: #64748B !important;
                }
                .sna-pyvis-platform-button.is-hidden {
                    background: #F1F5F9 !important;
                    color: #94A3B8 !important;
                }
                .sna-pyvis-platform-dot {
                    box-shadow: 0 0 0 3px rgba(15,23,42,0.05) !important;
                }
                #mynetwork {
                    background:
                        radial-gradient(circle at 12% 18%, rgba(229,57,53,0.07), transparent 28%),
                        radial-gradient(circle at 88% 16%, rgba(29,161,242,0.07), transparent 32%),
                        linear-gradient(rgba(100,116,139,0.08) 1px, transparent 1px),
                        linear-gradient(90deg, rgba(100,116,139,0.08) 1px, transparent 1px),
                        linear-gradient(180deg, #FFFFFF 0%, #F8FAFC 100%) !important;
                    box-shadow: inset 0 0 0 1px #D8E0EA !important;
                }
                #mynetwork::after {
                    border-color: #D8E0EA !important;
                }
                div.vis-tooltip,
                .sna-node-tooltip,
                .sna-edge-tooltip {
                    background: #FFFFFF !important;
                    border-color: #D8E0EA !important;
                    box-shadow: 0 14px 34px rgba(15,23,42,0.16) !important;
                    color: #1F2937 !important;
                }
                .sna-node-tooltip__head,
                .sna-edge-tooltip__head {
                    background: linear-gradient(135deg, rgba(229,57,53,0.08), rgba(29,161,242,0.05)) !important;
                    border-bottom-color: #E2E8F0 !important;
                }
                .sna-node-tooltip__name,
                .sna-node-tooltip__value,
                .sna-edge-tooltip__title,
                .sna-edge-tooltip__value {
                    color: #1F2937 !important;
                }
                .sna-node-tooltip__role,
                .sna-node-tooltip__label,
                .sna-edge-tooltip__subtitle,
                .sna-edge-tooltip__label {
                    color: #64748B !important;
                }
                .sna-node-tooltip__item,
                .sna-edge-tooltip__node,
                .sna-edge-tooltip__meta-item {
                    background: #F8FAFC !important;
                    border-color: #E2E8F0 !important;
                }
                .sna-node-tooltip__hint,
                .sna-edge-tooltip__hint {
                    background: rgba(29,161,242,0.055) !important;
                    border-top-color: #E2E8F0 !important;
                    color: #475569 !important;
                }
            </style>
            """
        custom_toolbar = """
        <div class="sna-pyvis-shell">
            <div class="sna-pyvis-toolbar">
                <div class="sna-pyvis-toolbar-title">
                    <span class="sna-pyvis-kicker">Mode Interaktif</span>
                    <strong>Eksplorasi Graf SNA</strong>
                </div>
                <div class="sna-pyvis-actions">
                    <button class="primary" id="snaFitGraph" type="button">Pusatkan Graf</button>
                    <button id="snaFullscreenGraph" type="button">Layar Penuh</button>
                    <button id="snaToggleLabels" type="button">Nama Akun: UTAMA</button>
                    <button id="snaStabilizeGraph" type="button">Stabilkan</button>
                    <button id="snaTogglePhysics" type="button">Physics: ON</button>
                    <button id="snaToggleEdges" type="button">Sembunyikan Edge</button>
                    <button id="snaResetGraph" type="button">Reset</button>
                </div>
            </div>
            <div class="sna-pyvis-guide">
                <span><strong>Interaksi:</strong> drag node, scroll untuk zoom, klik node untuk fokus. Label awal hanya menampilkan akun utama agar graf tetap bersih.</span>
                <span class="sna-pyvis-status" id="snaGraphStatus">Siap dieksplorasi</span>
            </div>
            <div class="sna-pyvis-platform-filter" aria-label="Filter node berdasarkan platform">
                <div class="sna-pyvis-platform-buttons">
                    <span class="sna-pyvis-platform-label">Tampilkan/Sembunyikan Node</span>
                    <button class="sna-pyvis-platform-button" data-platform-toggle="twitter" type="button"><span class="sna-pyvis-platform-dot" style="background:#1DA1F2"></span>Twitter/X</button>
                    <button class="sna-pyvis-platform-button" data-platform-toggle="instagram" type="button"><span class="sna-pyvis-platform-dot" style="background:#833AB4"></span>Instagram</button>
                    <button class="sna-pyvis-platform-button" data-platform-toggle="tiktok" type="button"><span class="sna-pyvis-platform-dot" style="background:#25F4EE"></span>TikTok</button>
                    <button class="sna-pyvis-platform-button" data-platform-toggle="target" type="button"><span class="sna-pyvis-platform-dot" style="background:#E53935"></span>Akun Brand / Hub</button>
                </div>
                <span class="sna-pyvis-platform-help">Warna node = platform · Twitter/X biru · Instagram ungu · TikTok cyan · akun Brand/Hub merah. Sentimen tersedia saat hover.</span>
            </div>
            <div class="sna-node-tooltip" id="snaNodeTooltip" aria-hidden="true"></div>
            <div class="sna-edge-tooltip" id="snaEdgeTooltip" aria-hidden="true"></div>
        """
        custom_js = """
        </div>
        <script>
        (function () {
            var physicsEnabled = true;
            var edgesHidden = false;
            var labelMode = "key";
            var hiddenPlatformGroups = {};

            function byId(id) { return document.getElementById(id); }
            function setStatus(message) {
                var el = byId('snaGraphStatus');
                if (el) { el.textContent = message; }
            }
            function getNetwork() {
                try {
                    if (typeof network !== 'undefined') { return network; }
                    if (window.network) { return window.network; }
                } catch (err) {}
                return null;
            }
            function getEdges() {
                try {
                    if (typeof edges !== 'undefined') { return edges; }
                    if (window.edges) { return window.edges; }
                } catch (err) {}
                return null;
            }
            function getNodes() {
                try {
                    if (typeof nodes !== 'undefined') { return nodes; }
                    if (window.nodes) { return window.nodes; }
                } catch (err) {}
                return null;
            }
            function escapeHtml(value) {
                return String(value == null ? '' : value)
                    .replace(/&/g, '&amp;')
                    .replace(/</g, '&lt;')
                    .replace(/>/g, '&gt;')
                    .replace(/"/g, '&quot;')
                    .replace(/'/g, '&#039;');
            }
            function formatNumber(value) {
                var number = Number(value || 0);
                try { return number.toLocaleString('id-ID'); }
                catch (err) { return String(value || 0); }
            }
            function ready(callback) {
                if (document.readyState === 'loading') {
                    document.addEventListener('DOMContentLoaded', function () { window.setTimeout(callback, 350); });
                } else {
                    window.setTimeout(callback, 350);
                }
            }

            ready(function () {
                var graph = getNetwork();
                if (!graph) {
                    setStatus('Graf belum siap. Muat ulang halaman jika tombol tidak merespons.');
                    return;
                }
                window.snaNetwork = graph;
                setStatus('Siap: drag, zoom, klik node, atau gunakan tombol.');

                function fullscreenElement() {
                    return document.fullscreenElement || document.webkitFullscreenElement || null;
                }
                function isFullscreenActive() {
                    return !!fullscreenElement();
                }
                function fitGraphAfterResize() {
                    window.setTimeout(function () {
                        try { graph.redraw(); } catch (err) {}
                        try { graph.fit({ animation: { duration: 450, easingFunction: 'easeInOutQuad' } }); } catch (err) {}
                    }, 220);
                }
                function updateFullscreenButton() {
                    var button = byId('snaFullscreenGraph');
                    if (!button) { return; }
                    button.textContent = isFullscreenActive() ? 'Keluar Fullscreen' : 'Layar Penuh';
                }
                function requestGraphFullscreen() {
                    var shell = document.querySelector('.sna-pyvis-shell');
                    if (!shell) {
                        setStatus('Panel graf tidak ditemukan.');
                        return;
                    }
                    try {
                        if (shell.requestFullscreen) {
                            shell.requestFullscreen();
                        } else if (shell.webkitRequestFullscreen) {
                            shell.webkitRequestFullscreen();
                        } else {
                            setStatus('Browser tidak mendukung mode layar penuh.');
                            return;
                        }
                        setStatus('Mode layar penuh aktif. Tekan Esc untuk keluar.');
                    } catch (err) {
                        setStatus('Mode layar penuh tidak diizinkan browser. Coba buka aplikasi di Chrome/Edge.');
                    }
                }
                function exitGraphFullscreen() {
                    try {
                        if (document.exitFullscreen) {
                            document.exitFullscreen();
                        } else if (document.webkitExitFullscreen) {
                            document.webkitExitFullscreen();
                        }
                        setStatus('Keluar dari mode layar penuh.');
                    } catch (err) {
                        setStatus('Tidak bisa keluar dari layar penuh secara otomatis. Tekan Esc.');
                    }
                }

                var fitButton = byId('snaFitGraph');
                if (fitButton) {
                    fitButton.onclick = function () {
                        graph.fit({ animation: { duration: 650, easingFunction: 'easeInOutQuad' } });
                        setStatus('Graf dipusatkan.');
                    };
                }

                var fullscreenButton = byId('snaFullscreenGraph');
                if (fullscreenButton) {
                    fullscreenButton.onclick = function () {
                        if (isFullscreenActive()) {
                            exitGraphFullscreen();
                        } else {
                            requestGraphFullscreen();
                        }
                    };
                }
                document.addEventListener('fullscreenchange', function () {
                    updateFullscreenButton();
                    fitGraphAfterResize();
                });
                document.addEventListener('webkitfullscreenchange', function () {
                    updateFullscreenButton();
                    fitGraphAfterResize();
                });
                updateFullscreenButton();

                function applyLabelState(mode) {
                    var nodeDataSet = getNodes();
                    if (!nodeDataSet) { return; }
                    try {
                        var updates = nodeDataSet.getIds().map(function (id) {
                            var item = nodeDataSet.get(id) || {};
                            var isBrand = String(item.sna_is_brand || '') === '1';
                            var isKey = String(item.sna_is_key || '') === '1';
                            var showLabel = mode === 'all' || (mode === 'key' && (isBrand || isKey));
                            return {
                                id: id,
                                label: showLabel ? (item.sna_label || String(id)) : '',
                                font: {
                                    color: '#FFFFFF',
                                    size: isBrand ? 18 : 12,
                                    face: 'Inter',
                                    strokeWidth: 6,
                                    strokeColor: '#06080C',
                                    vadjust: -3
                                }
                            };
                        });
                        nodeDataSet.update(updates);
                        try { graph.redraw(); } catch (err) {}
                    } catch (err) {
                        setStatus('Label node belum bisa diperbarui. Muat ulang halaman jika nama akun belum muncul.');
                    }
                }

                function getNodePlatformGroup(node) {
                    return String((node && node.sna_group_key) || 'unknown').toLowerCase();
                }
                function isNodeGroupHidden(node) {
                    var group = getNodePlatformGroup(node);
                    return !!hiddenPlatformGroups[group];
                }
                function applyPlatformVisibility() {
                    var nodeDataSet = getNodes();
                    var edgeDataSet = getEdges();
                    if (!nodeDataSet || !nodeDataSet.getIds) { return; }
                    var hiddenNodes = {};
                    try {
                        var nodeUpdates = nodeDataSet.getIds().map(function (id) {
                            var item = nodeDataSet.get(id) || {};
                            var shouldHide = isNodeGroupHidden(item);
                            hiddenNodes[String(id)] = shouldHide;
                            return { id: id, hidden: shouldHide };
                        });
                        nodeDataSet.update(nodeUpdates);
                    } catch (err) {
                        setStatus('Filter node belum bisa diterapkan. Muat ulang halaman jika perlu.');
                        return;
                    }
                    if (edgeDataSet && edgeDataSet.getIds) {
                        try {
                            var edgeUpdates = edgeDataSet.getIds().map(function (id) {
                                var item = edgeDataSet.get(id) || {};
                                var sourceHidden = !!hiddenNodes[String(item.from)];
                                var targetHidden = !!hiddenNodes[String(item.to)];
                                return { id: id, hidden: edgesHidden || sourceHidden || targetHidden };
                            });
                            edgeDataSet.update(edgeUpdates);
                        } catch (err) {}
                    }
                    hideCustomTooltip();
                    try { graph.redraw(); } catch (err) {}
                }
                function updatePlatformButtons() {
                    var buttons = document.querySelectorAll('[data-platform-toggle]');
                    for (var i = 0; i < buttons.length; i += 1) {
                        var group = String(buttons[i].getAttribute('data-platform-toggle') || '').toLowerCase();
                        if (hiddenPlatformGroups[group]) {
                            buttons[i].classList.add('is-hidden');
                            buttons[i].setAttribute('aria-pressed', 'false');
                            buttons[i].setAttribute('title', 'Klik untuk menampilkan node ini lagi');
                        } else {
                            buttons[i].classList.remove('is-hidden');
                            buttons[i].setAttribute('aria-pressed', 'true');
                            buttons[i].setAttribute('title', 'Klik untuk menyembunyikan node ini');
                        }
                    }
                }
                function countVisibleNodeGroups() {
                    var nodeDataSet = getNodes();
                    var counts = {};
                    if (!nodeDataSet || !nodeDataSet.getIds) { return counts; }
                    try {
                        nodeDataSet.getIds().forEach(function (id) {
                            var item = nodeDataSet.get(id) || {};
                            var group = getNodePlatformGroup(item);
                            if (!hiddenPlatformGroups[group]) {
                                counts[group] = (counts[group] || 0) + 1;
                            }
                        });
                    } catch (err) {}
                    return counts;
                }
                function bindPlatformToggleButtons() {
                    var buttons = document.querySelectorAll('[data-platform-toggle]');
                    for (var i = 0; i < buttons.length; i += 1) {
                        buttons[i].onclick = function () {
                            var group = String(this.getAttribute('data-platform-toggle') || '').toLowerCase();
                            if (!group) { return; }
                            hiddenPlatformGroups[group] = !hiddenPlatformGroups[group];
                            if (!hiddenPlatformGroups[group]) { delete hiddenPlatformGroups[group]; }
                            updatePlatformButtons();
                            applyPlatformVisibility();
                            var counts = countVisibleNodeGroups();
                            var totalVisible = Object.keys(counts).reduce(function (sum, key) { return sum + counts[key]; }, 0);
                            setStatus((hiddenPlatformGroups[group] ? 'Node disembunyikan: ' : 'Node ditampilkan kembali: ') + this.textContent.trim() + ' • node terlihat: ' + totalVisible);
                        };
                    }
                    updatePlatformButtons();
                    applyPlatformVisibility();
                }

                var labelButton = byId('snaToggleLabels');
                if (labelButton) {
                    labelButton.onclick = function () {
                        labelMode = labelMode === 'key' ? 'all' : (labelMode === 'all' ? 'none' : 'key');
                        applyLabelState(labelMode);
                        if (labelMode === 'key') {
                            labelButton.textContent = 'Nama Akun: UTAMA';
                            setStatus('Hanya akun utama dan node paling penting yang diberi label.');
                        } else if (labelMode === 'all') {
                            labelButton.textContent = 'Nama Akun: SEMUA';
                            setStatus('Semua nama akun ditampilkan. Gunakan mode UTAMA jika terasa padat.');
                        } else {
                            labelButton.textContent = 'Nama Akun: OFF';
                            setStatus('Nama akun disembunyikan. Detail tetap tersedia saat hover.');
                        }
                    };
                }
                applyLabelState(true);
                bindPlatformToggleButtons();

                function hideCustomTooltip() {
                    var nodeTooltip = byId('snaNodeTooltip');
                    var edgeTooltip = byId('snaEdgeTooltip');
                    if (nodeTooltip) {
                        nodeTooltip.classList.remove('is-visible');
                        nodeTooltip.setAttribute('aria-hidden', 'true');
                    }
                    if (edgeTooltip) {
                        edgeTooltip.classList.remove('is-visible');
                        edgeTooltip.setAttribute('aria-hidden', 'true');
                    }
                }
                function showCustomTooltip(params) {
                    var tooltip = byId('snaNodeTooltip');
                    var edgeTooltip = byId('snaEdgeTooltip');
                    if (edgeTooltip) {
                        edgeTooltip.classList.remove('is-visible');
                        edgeTooltip.setAttribute('aria-hidden', 'true');
                    }
                    var nodeData = null;
                    var nodeDataSet = getNodes();
                    if (!tooltip || !nodeDataSet || !params || !params.node) { return; }
                    try { nodeData = nodeDataSet.get(params.node); } catch (err) { nodeData = null; }
                    if (!nodeData) { return; }

                    var connectedCount = 0;
                    try { connectedCount = (graph.getConnectedNodes(params.node) || []).length; } catch (err) {}
                    var nodeColor = nodeData.sna_color || '#E53935';
                    var nodeName = nodeData.id || params.node;
                    var role = nodeData.sna_role || 'Akun Percakapan';
                    var platform = nodeData.sna_platform || 'Tidak diketahui';
                    var followers = formatNumber(nodeData.sna_followers || 0);
                    var degree = nodeData.sna_degree || '0';
                    var pageRank = nodeData.sna_pagerank || '0.00000000';
                    var sentiment = nodeData.sna_sentiment || 'Netral';

                    tooltip.innerHTML = '' +
                        '<div class="sna-node-tooltip__head">' +
                            '<span class="sna-node-tooltip__dot" style="background:' + escapeHtml(nodeColor) + '"></span>' +
                            '<div>' +
                                '<span class="sna-node-tooltip__name" title="' + escapeHtml(nodeName) + '">' + escapeHtml(nodeName) + '</span>' +
                                '<span class="sna-node-tooltip__role">' + escapeHtml(role) + '</span>' +
                            '</div>' +
                        '</div>' +
                        '<div class="sna-node-tooltip__grid">' +
                            '<div class="sna-node-tooltip__item"><span class="sna-node-tooltip__label">Platform</span><span class="sna-node-tooltip__value">' + escapeHtml(platform) + '</span></div>' +
                            '<div class="sna-node-tooltip__item"><span class="sna-node-tooltip__label">Followers</span><span class="sna-node-tooltip__value">' + escapeHtml(followers) + '</span></div>' +
                            '<div class="sna-node-tooltip__item"><span class="sna-node-tooltip__label">Degree</span><span class="sna-node-tooltip__value">' + escapeHtml(degree) + '</span></div>' +
                            '<div class="sna-node-tooltip__item"><span class="sna-node-tooltip__label">PageRank</span><span class="sna-node-tooltip__value">' + escapeHtml(pageRank) + '</span></div>' +
                            '<div class="sna-node-tooltip__item"><span class="sna-node-tooltip__label">Sentimen</span><span class="sna-node-tooltip__value">' + escapeHtml(sentiment) + '</span></div>' +
                        '</div>' +
                        '<div class="sna-node-tooltip__hint">Klik untuk memilih node · Double click untuk fokus lebih dekat</div>';

                    var networkEl = byId('mynetwork');
                    var shell = document.querySelector('.sna-pyvis-shell');
                    if (networkEl && shell && params.pointer && params.pointer.DOM) {
                        var networkRect = networkEl.getBoundingClientRect();
                        var shellRect = shell.getBoundingClientRect();
                        var left = (networkRect.left - shellRect.left) + params.pointer.DOM.x + 18;
                        var top = (networkRect.top - shellRect.top) + params.pointer.DOM.y - 12;
                        var maxLeft = Math.max(12, shell.clientWidth - 365);
                        var maxTop = Math.max(12, shell.clientHeight - 230);
                        tooltip.style.left = Math.min(Math.max(12, left), maxLeft) + 'px';
                        tooltip.style.top = Math.min(Math.max(12, top), maxTop) + 'px';
                    }
                    tooltip.classList.add('is-visible');
                    tooltip.setAttribute('aria-hidden', 'false');
                }

                function relationLabel(value) {
                    var raw = String(value || 'interaction').trim();
                    var map = {
                        mention: 'Mention',
                        reply: 'Reply',
                        retweet: 'Retweet',
                        comment: 'Komentar',
                        interaction: 'Interaksi'
                    };
                    return map[raw.toLowerCase()] || raw.replace(/_/g, ' ');
                }
                function showCustomEdgeTooltip(params) {
                    var tooltip = byId('snaEdgeTooltip');
                    var nodeTooltip = byId('snaNodeTooltip');
                    var edgeDataSet = getEdges();
                    var edgeData = null;
                    if (nodeTooltip) {
                        nodeTooltip.classList.remove('is-visible');
                        nodeTooltip.setAttribute('aria-hidden', 'true');
                    }
                    if (!tooltip || !edgeDataSet || !params || !params.edge) { return; }
                    try { edgeData = edgeDataSet.get(params.edge); } catch (err) { edgeData = null; }
                    if (!edgeData) { return; }

                    var source = edgeData.sna_source || edgeData.from || '-';
                    var target = edgeData.sna_target || edgeData.to || '-';
                    var relation = relationLabel(edgeData.sna_relation || 'interaction');
                    var weight = formatNumber(edgeData.sna_weight || edgeData.value || 1);

                    tooltip.innerHTML = '' +
                        '<div class="sna-edge-tooltip__head">' +
                            '<span class="sna-edge-tooltip__icon">↗</span>' +
                            '<div>' +
                                '<span class="sna-edge-tooltip__title">Relasi Interaksi</span>' +
                                '<span class="sna-edge-tooltip__subtitle">Arah panah menunjukkan source → target</span>' +
                            '</div>' +
                        '</div>' +
                        '<div class="sna-edge-tooltip__flow">' +
                            '<div class="sna-edge-tooltip__node"><span class="sna-edge-tooltip__label">Source</span><span class="sna-edge-tooltip__value" title="' + escapeHtml(source) + '">' + escapeHtml(source) + '</span></div>' +
                            '<div class="sna-edge-tooltip__arrow">→</div>' +
                            '<div class="sna-edge-tooltip__node"><span class="sna-edge-tooltip__label">Target</span><span class="sna-edge-tooltip__value" title="' + escapeHtml(target) + '">' + escapeHtml(target) + '</span></div>' +
                        '</div>' +
                        '<div class="sna-edge-tooltip__meta">' +
                            '<div class="sna-edge-tooltip__meta-item"><span class="sna-edge-tooltip__label">Jenis Relasi</span><span class="sna-edge-tooltip__value">' + escapeHtml(relation) + '</span></div>' +
                            '<div class="sna-edge-tooltip__meta-item"><span class="sna-edge-tooltip__label">Frekuensi</span><span class="sna-edge-tooltip__value">' + escapeHtml(weight) + ' interaksi</span></div>' +
                        '</div>' +
                        '<div class="sna-edge-tooltip__hint">Garis menandakan relasi langsung antarakun dalam edge list SNA.</div>';

                    var networkEl = byId('mynetwork');
                    var shell = document.querySelector('.sna-pyvis-shell');
                    if (networkEl && shell && params.pointer && params.pointer.DOM) {
                        var networkRect = networkEl.getBoundingClientRect();
                        var shellRect = shell.getBoundingClientRect();
                        var left = (networkRect.left - shellRect.left) + params.pointer.DOM.x + 18;
                        var top = (networkRect.top - shellRect.top) + params.pointer.DOM.y - 12;
                        var maxLeft = Math.max(12, shell.clientWidth - 395);
                        var maxTop = Math.max(12, shell.clientHeight - 245);
                        tooltip.style.left = Math.min(Math.max(12, left), maxLeft) + 'px';
                        tooltip.style.top = Math.min(Math.max(12, top), maxTop) + 'px';
                    }
                    tooltip.classList.add('is-visible');
                    tooltip.setAttribute('aria-hidden', 'false');
                }

                graph.on('hoverNode', showCustomTooltip);
                graph.on('blurNode', hideCustomTooltip);
                graph.on('hoverEdge', showCustomEdgeTooltip);
                graph.on('blurEdge', hideCustomTooltip);
                graph.on('dragStart', hideCustomTooltip);
                graph.on('zoom', hideCustomTooltip);

                var stabilizeButton = byId('snaStabilizeGraph');
                if (stabilizeButton) {
                    stabilizeButton.onclick = function () {
                        graph.setOptions({ physics: { enabled: true } });
                        physicsEnabled = true;
                        var physicsButton = byId('snaTogglePhysics');
                        if (physicsButton) { physicsButton.textContent = 'Physics: ON'; }
                        graph.stabilize(160);
                        setStatus('Graf sedang distabilkan.');
                    };
                }

                var physicsButton = byId('snaTogglePhysics');
                if (physicsButton) {
                    physicsButton.onclick = function () {
                        physicsEnabled = !physicsEnabled;
                        graph.setOptions({ physics: { enabled: physicsEnabled } });
                        physicsButton.textContent = physicsEnabled ? 'Physics: ON' : 'Physics: OFF';
                        setStatus(physicsEnabled ? 'Physics aktif. Node dapat bergerak dinamis.' : 'Physics nonaktif. Posisi graf dikunci.');
                    };
                }

                var edgesButton = byId('snaToggleEdges');
                if (edgesButton) {
                    edgesButton.onclick = function () {
                        var edgeData = getEdges();
                        if (!edgeData || !edgeData.getIds) {
                            setStatus('Edge dataset tidak tersedia.');
                            return;
                        }
                        edgesHidden = !edgesHidden;
                        applyPlatformVisibility();
                        edgesButton.textContent = edgesHidden ? 'Tampilkan Edge' : 'Sembunyikan Edge';
                        setStatus(edgesHidden ? 'Edge disembunyikan untuk membaca node.' : 'Edge ditampilkan kembali sesuai node yang masih aktif.');
                    };
                }

                var resetButton = byId('snaResetGraph');
                if (resetButton) {
                    resetButton.onclick = function () {
                        var edgeData = getEdges();
                        if (edgeData && edgeData.getIds) {
                            edgeData.update(edgeData.getIds().map(function (id) { return { id: id, hidden: false }; }));
                        }
                        edgesHidden = false;
                        hiddenPlatformGroups = {};
                        var edgesButton = byId('snaToggleEdges');
                        if (edgesButton) { edgesButton.textContent = 'Sembunyikan Edge'; }
                        updatePlatformButtons();
                        applyPlatformVisibility();
                        graph.unselectAll();
                        hideCustomTooltip();
                        graph.fit({ animation: { duration: 650, easingFunction: 'easeInOutQuad' } });
                        setStatus('Tampilan graf direset. Semua kelompok node ditampilkan kembali.');
                    };
                }

                graph.on('selectNode', function (params) {
                    if (!params.nodes || !params.nodes.length) { return; }
                    var nodeId = params.nodes[0];
                    var connected = [];
                    try { connected = graph.getConnectedNodes(nodeId) || []; } catch (err) {}
                    setStatus('Node dipilih: ' + nodeId + ' • koneksi langsung: ' + connected.length);
                });

                graph.on('deselectNode', function () {
                    setStatus('Siap dieksplorasi.');
                });

                graph.on('doubleClick', function (params) {
                    if (params.nodes && params.nodes.length) {
                        graph.focus(params.nodes[0], { scale: 1.45, animation: { duration: 650, easingFunction: 'easeInOutQuad' } });
                        setStatus('Fokus ke node: ' + params.nodes[0]);
                    }
                });

                graph.on('stabilizationIterationsDone', function () {
                    graph.setOptions({ physics: { enabled: false } });
                    physicsEnabled = false;
                    var physicsButton = byId('snaTogglePhysics');
                    if (physicsButton) { physicsButton.textContent = 'Physics: OFF'; }
                    setStatus('Graf stabil. Tampilan dirapikan dan dipusatkan.');
                    window.setTimeout(function () {
                        try { graph.fit({ animation: { duration: 900, easingFunction: 'easeInOutQuad' } }); } catch (err) {}
                    }, 120);
                });
            });
        })();
        </script>
        """
        html = html.replace("</head>", f"{custom_css}</head>")
        html = html.replace("<body>", f"<body>{custom_toolbar}", 1)
        html = html.replace("</body>", f"{custom_js}</body>", 1)
        return html
    except Exception as exc:
        raise RuntimeError(f"PyVis gagal membuat HTML graf: {exc}") from exc



def _pyvis_html(graph: nx.DiGraph, visual_nodes: pd.DataFrame) -> str:
    """Alias kompatibilitas untuk implementasi PyVis sebelum Fase 14."""
    return generate_pyvis_graph(
        graph,
        visual_nodes,
        dark_mode=bool(st.session_state.get("dark_mode", False)),
    )

def _render_networkx_fallback(graph: nx.DiGraph, visual_nodes: pd.DataFrame) -> None:
    """Tampilkan ringkasan aman apabila HTML PyVis gagal dirender."""
    try:
        st.error(
            "Graf interaktif PyVis belum dapat ditampilkan. Periksa instalasi "
            "library pyvis, lalu restart Streamlit. Data dan metrik tetap aman."
        )
        if visual_nodes is not None and not visual_nodes.empty:
            preview_columns = [
                column
                for column in ["username", "platform_label", "pagerank", "degree"]
                if column in visual_nodes.columns
            ]
            st.dataframe(
                visual_nodes[preview_columns].head(10),
                use_container_width=True,
                hide_index=True,
            )
    except Exception as exc:
        st.error(f"Ringkasan fallback graf juga gagal ditampilkan: {exc}")


def _render_graph_legend(service: str = "") -> None:
    """Tampilkan legenda warna sentimen node pada visualisasi graf."""
    try:
        items = [
            (SENTIMENT_COLORS["positive"], "Isi node: Sentimen Positif"),
            (SENTIMENT_COLORS["neutral"], "Isi node: Sentimen Netral"),
            (SENTIMENT_COLORS["negative"], "Isi node: Sentimen Negatif"),
            (PLATFORM_GRAPH_COLORS["twitter"], "Garis tepi/platform: Twitter/X"),
            (PLATFORM_GRAPH_COLORS["instagram"], "Garis tepi/platform: Instagram"),
            (PLATFORM_GRAPH_COLORS["tiktok"], "Garis tepi/platform: TikTok"),
        ]
        legend = "".join(
            f'<span class="sna-v9-legend-item"><span class="sna-v9-dot" style="background:{color};"></span>{label}</span>'
            for color, label in items
        )
        service_key = str(service).strip().lower()
        size_note = (
            "Ukuran node: Twitter/X mengikuti degree, sedangkan Instagram dan TikTok mengikuti jumlah followers. "
            "Node tanpa data sentimen menggunakan warna platform sebagai isi. Chip platform di dalam graf tetap dapat dipakai untuk menyaring kelompok node."
            if service_key in {"indihome", "indibiz"}
            else "Ukuran node mengikuti PageRank. Node tanpa data sentimen menggunakan warna platform sebagai isi. Chip platform di dalam graf tetap dapat dipakai untuk menyaring kelompok node."
        )
        st.markdown(
            f'<div class="sna-v9-platform-legend">{legend}</div>'
            f'<div class="sna-v9-section-subtitle" style="margin-top:.35rem;">{escape(size_note)}</div>',
            unsafe_allow_html=True,
        )
    except Exception as exc:
        st.error(f"Gagal menampilkan legenda graf: {exc}")



def _network_graph_request_id(graph: nx.DiGraph, node_limit: int) -> str:
    """Buat identitas stabil agar PyVis hanya dirender setelah diminta."""
    try:
        payload = repr((int(node_limit), _hash_digraph_for_cache(graph))).encode(
            "utf-8", errors="ignore"
        )
        return hashlib.sha256(payload).hexdigest()[:20]
    except Exception:
        return hashlib.sha256(repr(graph).encode("utf-8", errors="ignore")).hexdigest()[:20]


def _queue_network_graph_render(request_id: str) -> None:
    """Simpan permintaan render dan gunakan loading custom halaman SNA."""
    try:
        st.session_state[SNA_GRAPH_RENDER_REQUEST_KEY] = str(request_id)
        st.session_state[SNA_ACTION_LOADING_KEY] = "Membangun network graph interaktif..."
    except Exception as exc:
        st.error(f"Permintaan graf belum dapat disiapkan: {exc}")

def _render_network_graph(graph: nx.DiGraph, node_df: pd.DataFrame, node_limit: int, service: str = "") -> None:
    """Render graf jaringan interaktif Pyvis full width."""
    try:
        with st.container(border=True):
            st.markdown('<span class="sna-v9-graph-marker"></span>', unsafe_allow_html=True)
            st.markdown(
                """
                <div class="sna-v9-section-head">
                    <div>
                        <h2 class="sna-v9-section-title">Visualisasi Graf Interaktif</h2>
                        <p class="sna-v9-section-subtitle">Arah panah menunjukkan source → target. Arahkan kursor ke node untuk melihat username, followers, platform, degree, PageRank, dan sentimen dominan.</p>
                    </div>
                </div>
                """,
                unsafe_allow_html=True,
            )

            service_key = str(service).strip().lower()
            graph_for_visual = graph
            nodes_for_visual = node_df
            if service_key == "indibiz":
                graph_for_visual, nodes_for_visual = _ensure_indibiz_platform_representatives(
                    graph,
                    node_df,
                    minimum_per_platform=2,
                )

            visual_graph, visual_nodes = _limit_graph_nodes(
                graph_for_visual,
                nodes_for_visual,
                node_limit,
                service=service,
            )
            if visual_graph.number_of_nodes() == 0:
                st.info("Tidak ada data graf pada kombinasi filter yang dipilih.")
                return

            graph_density = nx.density(visual_graph) if visual_graph.number_of_nodes() > 1 else 0.0
            st.markdown(
                f"""
                <div class="sna-v9-graph-kpi-grid">
                    <div class="sna-v9-graph-kpi">
                        <span class="sna-v9-graph-kpi-label">Node Ditampilkan</span>
                        <span class="sna-v9-graph-kpi-value">{visual_graph.number_of_nodes():,}</span>
                        <span class="sna-v9-graph-kpi-note">Akun yang masuk ke visualisasi aktif</span>
                    </div>
                    <div class="sna-v9-graph-kpi">
                        <span class="sna-v9-graph-kpi-label">Edge Ditampilkan</span>
                        <span class="sna-v9-graph-kpi-value">{visual_graph.number_of_edges():,}</span>
                        <span class="sna-v9-graph-kpi-note">Relasi source → target pada graf</span>
                    </div>
                    <div class="sna-v9-graph-kpi">
                        <span class="sna-v9-graph-kpi-label">Density Subgraf</span>
                        <span class="sna-v9-graph-kpi-value">{graph_density:.6f}</span>
                        <span class="sna-v9-graph-kpi-note">Batas node aktif: {int(node_limit):,}</span>
                    </div>
                </div>
                """,
                unsafe_allow_html=True,
            )
            # Tampilkan komposisi node terpilih agar pengguna dapat memastikan
            # ketiga platform benar-benar masuk pada mode Semua Platform.
            composition_counts = visual_nodes["platform_group"].value_counts().to_dict()
            composition_order = ["twitter", "instagram", "tiktok", "target"]
            composition_chips = []
            for platform_key in composition_order:
                count = int(composition_counts.get(platform_key, 0))
                if count <= 0:
                    continue
                color = PLATFORM_GRAPH_COLORS.get(platform_key, PLATFORM_GRAPH_COLORS["unknown"])
                label = PLATFORM_DISPLAY.get(platform_key, platform_key.title())
                composition_chips.append(
                    '<span class="sna-v9-legend-item">'
                    f'<span class="sna-v9-dot" style="background:{color};"></span>'
                    f'{escape(label)}: <strong>{count}</strong></span>'
                )
            st.markdown(
                '<div class="sna-v9-platform-legend" style="margin-top:.8rem;">'
                '<span class="sna-v9-section-subtitle" style="margin:0 .35rem 0 0;">Komposisi node terpilih:</span>'
                + "".join(composition_chips)
                + '</div>',
                unsafe_allow_html=True,
            )
            st.markdown(
                """
                <div class="sna-v9-interaction-strip">
                    <div>
                        <strong>Kontrol interaktif tersedia di dalam graf.</strong><br>
                        <span>Gunakan tombol Pusatkan Graf, Layar Penuh, Stabilkan, Physics ON/OFF, Sembunyikan Edge, dan Reset.</span>
                    </div>
                    <div>
                        <span class="sna-v9-interaction-pill">Drag node</span>
                        <span class="sna-v9-interaction-pill">Scroll zoom</span>
                        <span class="sna-v9-interaction-pill">Klik node</span>
                        <span class="sna-v9-interaction-pill">Double click focus</span>
                    </div>
                </div>
                """,
                unsafe_allow_html=True,
            )

            graph_request_id = _network_graph_request_id(visual_graph, node_limit)
            graph_requested = (
                st.session_state.get(SNA_GRAPH_RENDER_REQUEST_KEY)
                == graph_request_id
            )
            if not graph_requested:
                st.button(
                    "🕸️ Tampilkan Network Graph",
                    type="primary",
                    use_container_width=True,
                    key=f"sna_v9_show_network_graph_{graph_request_id}",
                    on_click=_queue_network_graph_render,
                    args=(graph_request_id,),
                )
                return

            try:
                with st.spinner("Membangun network graph..."):
                    html = generate_pyvis_graph(
                        visual_graph,
                        visual_nodes,
                        dark_mode=bool(st.session_state.get("dark_mode", False)),
                        service=service,
                    )
                if not html:
                    raise RuntimeError("HTML PyVis kosong.")
                st.markdown('<div class="sna-v9-graph-frame">', unsafe_allow_html=True)
                render_html_iframe(html, height=930, scrolling=False)
                st.markdown('</div>', unsafe_allow_html=True)
            except Exception as pyvis_exc:
                st.warning("Visualisasi interaktif PyVis tidak berhasil dimuat. Dashboard menampilkan graf statis sebagai pengganti.")
                LOGGER.warning("Visualisasi PyVis memakai graf pengganti karena komponen interaktif belum siap: %s", pyvis_exc)
                _render_networkx_fallback(visual_graph, visual_nodes)

            _render_graph_legend(service)
            service_key = str(service).strip().lower()
            if service_key == "indihome":
                st.caption(
                    "Ukuran node Twitter/X mengikuti degree. Ukuran node Instagram dan TikTok mengikuti jumlah followers. "
                    "Akun layanan turunan disembunyikan dari graf IndiHome; akun utama IndiHome, IndiBiz, dan Telkomsel tetap dapat tampil sebagai hub merah bila terdapat pada jaringan aktif."
                )
            elif service_key == "indibiz":
                st.caption(
                    "Ukuran node Twitter/X mengikuti degree. Ukuran node Instagram dan TikTok mengikuti jumlah followers. "
                    "Akun layanan turunan/regional/care disembunyikan dari graf IndiBiz; hanya akun utama IndiHome, IndiBiz, dan Telkomsel yang tetap dapat tampil sebagai hub merah bila terdapat pada jaringan aktif. Jika edge suatu platform belum tersedia, maksimal dua akun nyata dari dataset IndiBiz ditampilkan sebagai wakil platform tanpa membuat edge baru. Data SNA asli tidak diubah."
                )
            else:
                st.caption("Ukuran node mengikuti PageRank. Isi node menunjukkan sentimen; garis tepi menunjukkan platform. Jika sentimen node belum tersedia, isi node memakai warna platform agar jaringan tetap mudah dibaca.")
    except Exception as exc:
        st.error(f"Gagal menampilkan visualisasi graf: {exc}")


# -----------------------------------------------------------------------------
# Helper loading aksi dan state filter
# -----------------------------------------------------------------------------

def _start_filter_loading(label: str):
    """Tampilkan overlay loading khusus saat tombol Terapkan Filter diklik."""
    try:
        if callable(mulai_loading_aksi):
            return mulai_loading_aksi(label)
    except Exception:
        return None
    return None


def _plotly_chart_aman(figur: go.Figure | None, *args: Any, **kwargs: Any) -> Any:
    """Render Plotly hanya ketika objek figur tersedia."""
    try:
        if figur is None:
            st.warning("Grafik tidak dapat ditampilkan.")
            return None
        # FIX: Plotly mengikuti lebar container dan merespons perubahan viewport.
        if "width" not in kwargs and "use_container_width" not in kwargs:
            kwargs["width"] = "stretch"
        config = dict(kwargs.pop("config", {}) or {})
        config.setdefault("responsive", True)
        kwargs["config"] = config
        return st.plotly_chart(figur, *args, **kwargs)
    except Exception as exc:
        st.warning(f"Grafik tidak dapat ditampilkan: {exc}")
        return None


def _finish_filter_loading(handle: Any) -> None:
    """Tutup overlay loading filter jika utilitas loading tersedia."""
    try:
        if handle is not None and callable(selesaikan_loading_aksi):
            selesaikan_loading_aksi(handle)
    except Exception:
        return None


def _show_filter_loading() -> None:
    """Aktifkan overlay loading custom hanya untuk perubahan filter yang nyata."""
    try:
        st.session_state.pop(SNA_GRAPH_RENDER_REQUEST_KEY, None)
        layanan = str(st.session_state.get("sna_v9_service_filter", "layanan terpilih")).strip()
        layanan = layanan or "layanan terpilih"
        st.session_state[SNA_ACTION_LOADING_KEY] = f"Menerapkan filter SNA untuk {layanan}..."
    except Exception as exc:
        st.error(f"Loading filter SNA belum dapat disiapkan: {exc}")


def _filter_node_limit(value: Any, default: int = SNA_FILTER_DEFAULT_NODE_LIMIT) -> int:
    """Normalisasi nilai jumlah node agar selalu berada pada rentang slider."""
    try:
        node_limit = int(value)
    except (TypeError, ValueError):
        node_limit = int(default)
    if node_limit < 20 or node_limit > 160:
        node_limit = int(default)
    return node_limit


def _current_filter_values() -> tuple[str, str, int]:
    """Ambil nilai filter yang saat ini dipilih pada widget form."""
    service = str(st.session_state.get("sna_v9_service_filter", "IndiHome"))
    platform = str(
        st.session_state.get("sna_v9_platform_filter", SNA_FILTER_DEFAULT_PLATFORM)
    )
    node_limit = _filter_node_limit(st.session_state.get("sna_v9_node_limit"))
    return service, platform, node_limit


def _applied_filter_values() -> tuple[str, str, int]:
    """Ambil snapshot filter terakhir yang benar-benar diterapkan."""
    current_service, current_platform, current_node_limit = _current_filter_values()
    service = str(
        st.session_state.get(SNA_FILTER_APPLIED_SERVICE_KEY, current_service)
    )
    platform = str(
        st.session_state.get(SNA_FILTER_APPLIED_PLATFORM_KEY, current_platform)
    )
    node_limit = _filter_node_limit(
        st.session_state.get(
            SNA_FILTER_APPLIED_NODE_LIMIT_KEY,
            current_node_limit,
        )
    )
    return service, platform, node_limit


def _save_applied_filter_values(values: tuple[str, str, int]) -> None:
    """Simpan snapshot filter yang sudah diterapkan ke session state."""
    service, platform, node_limit = values
    st.session_state[SNA_FILTER_APPLIED_SERVICE_KEY] = str(service)
    st.session_state[SNA_FILTER_APPLIED_PLATFORM_KEY] = str(platform)
    st.session_state[SNA_FILTER_APPLIED_NODE_LIMIT_KEY] = int(node_limit)


def _apply_sna_filters() -> bool:
    """Terapkan filter hanya ketika nilainya berbeda dari snapshot aktif."""
    try:
        current_values = _current_filter_values()
        changed = current_values != _applied_filter_values()
        st.session_state[SNA_FILTER_EVENT_KIND_KEY] = "apply"
        st.session_state[SNA_FILTER_EVENT_CHANGED_KEY] = bool(changed)
        if not changed:
            return False

        _save_applied_filter_values(current_values)
        _show_filter_loading()
        return True
    except Exception as exc:
        st.error(f"Filter SNA belum dapat diterapkan: {exc}")
        return False


def _reset_sna_filters(default_service: str) -> bool:
    """Kembalikan filter ke nilai awal dan terapkan reset bila diperlukan."""
    try:
        service = str(default_service).strip() or "IndiHome"
        default_values = (
            service,
            SNA_FILTER_DEFAULT_PLATFORM,
            SNA_FILTER_DEFAULT_NODE_LIMIT,
        )
        pending_changed = _current_filter_values() != default_values
        analysis_changed = _applied_filter_values() != default_values
        changed = bool(pending_changed or analysis_changed)

        st.session_state[SNA_FILTER_EVENT_KIND_KEY] = "reset"
        st.session_state[SNA_FILTER_EVENT_CHANGED_KEY] = bool(changed)
        if not changed:
            return False

        st.session_state["sna_v9_service_filter"] = service
        st.session_state["sna_v9_platform_filter"] = SNA_FILTER_DEFAULT_PLATFORM
        st.session_state["sna_v9_node_limit"] = SNA_FILTER_DEFAULT_NODE_LIMIT
        _save_applied_filter_values(default_values)
        _show_filter_loading()
        return True
    except Exception as exc:
        st.error(f"Filter SNA belum dapat direset: {exc}")
        return False

def _show_influencer_table_loading() -> None:
    """Aktifkan overlay loading custom pada rerun setelah filter tabel influencer diklik."""
    try:
        st.session_state[SNA_ACTION_LOADING_KEY] = "Menerapkan filter tabel influencer..."
    except Exception as exc:
        st.error(f"Loading filter tabel influencer belum dapat disiapkan: {exc}")


def _current_influencer_filter_values() -> tuple[str, str, int, str]:
    """Ambil nilai filter tabel influencer yang sedang dipilih pengguna."""
    search_value = str(
        st.session_state.get(
            "sna_v9_influencer_search",
            SNA_INFLUENCER_DEFAULT_SEARCH,
        )
    )
    platform_value = str(
        st.session_state.get(
            "sna_v9_influencer_platform",
            SNA_INFLUENCER_DEFAULT_PLATFORM,
        )
    )
    try:
        row_value = int(
            st.session_state.get(
                "sna_v9_influencer_rows",
                SNA_INFLUENCER_DEFAULT_ROWS,
            )
        )
    except (TypeError, ValueError):
        row_value = SNA_INFLUENCER_DEFAULT_ROWS
    mode_value = str(
        st.session_state.get(
            "sna_v9_influencer_mode",
            SNA_INFLUENCER_DEFAULT_MODE,
        )
    )
    return search_value, platform_value, row_value, mode_value


def _applied_influencer_filter_values() -> tuple[str, str, int, str]:
    """Ambil snapshot filter tabel influencer yang terakhir diterapkan."""
    current_search, current_platform, current_rows, current_mode = (
        _current_influencer_filter_values()
    )
    search_value = str(
        st.session_state.get(
            SNA_INFLUENCER_APPLIED_SEARCH_KEY,
            current_search,
        )
    )
    platform_value = str(
        st.session_state.get(
            SNA_INFLUENCER_APPLIED_PLATFORM_KEY,
            current_platform,
        )
    )
    try:
        row_value = int(
            st.session_state.get(
                SNA_INFLUENCER_APPLIED_ROWS_KEY,
                current_rows,
            )
        )
    except (TypeError, ValueError):
        row_value = current_rows
    mode_value = str(
        st.session_state.get(
            SNA_INFLUENCER_APPLIED_MODE_KEY,
            current_mode,
        )
    )
    return search_value, platform_value, row_value, mode_value


def _save_applied_influencer_filter_values(
    values: tuple[str, str, int, str],
) -> None:
    """Simpan snapshot filter tabel influencer yang sudah diterapkan."""
    search_value, platform_value, row_value, mode_value = values
    st.session_state[SNA_INFLUENCER_APPLIED_SEARCH_KEY] = str(search_value)
    st.session_state[SNA_INFLUENCER_APPLIED_PLATFORM_KEY] = str(platform_value)
    st.session_state[SNA_INFLUENCER_APPLIED_ROWS_KEY] = int(row_value)
    st.session_state[SNA_INFLUENCER_APPLIED_MODE_KEY] = str(mode_value)


def _ensure_influencer_filter_state(
    platform_labels: list[str],
    row_options: list[int],
    mode_options: list[str],
) -> None:
    """Pastikan nilai draft dan snapshot filter influencer selalu valid."""
    try:
        valid_platforms = platform_labels or [SNA_INFLUENCER_DEFAULT_PLATFORM]
        valid_rows = row_options or [SNA_INFLUENCER_DEFAULT_ROWS]
        valid_modes = mode_options or [SNA_INFLUENCER_DEFAULT_MODE]

        if not isinstance(
            st.session_state.get("sna_v9_influencer_search", ""),
            str,
        ):
            st.session_state["sna_v9_influencer_search"] = str(
                st.session_state.get("sna_v9_influencer_search", "")
            )
        if st.session_state.get("sna_v9_influencer_platform") not in valid_platforms:
            st.session_state["sna_v9_influencer_platform"] = (
                SNA_INFLUENCER_DEFAULT_PLATFORM
                if SNA_INFLUENCER_DEFAULT_PLATFORM in valid_platforms
                else valid_platforms[0]
            )
        if st.session_state.get("sna_v9_influencer_rows") not in valid_rows:
            st.session_state["sna_v9_influencer_rows"] = (
                SNA_INFLUENCER_DEFAULT_ROWS
                if SNA_INFLUENCER_DEFAULT_ROWS in valid_rows
                else valid_rows[0]
            )
        if st.session_state.get("sna_v9_influencer_mode") not in valid_modes:
            st.session_state["sna_v9_influencer_mode"] = (
                SNA_INFLUENCER_DEFAULT_MODE
                if SNA_INFLUENCER_DEFAULT_MODE in valid_modes
                else valid_modes[0]
            )

        applied_search, applied_platform, applied_rows, applied_mode = (
            _applied_influencer_filter_values()
        )
        if applied_platform not in valid_platforms:
            applied_platform = (
                SNA_INFLUENCER_DEFAULT_PLATFORM
                if SNA_INFLUENCER_DEFAULT_PLATFORM in valid_platforms
                else valid_platforms[0]
            )
        if applied_rows not in valid_rows:
            applied_rows = (
                SNA_INFLUENCER_DEFAULT_ROWS
                if SNA_INFLUENCER_DEFAULT_ROWS in valid_rows
                else valid_rows[0]
            )
        if applied_mode not in valid_modes:
            applied_mode = (
                SNA_INFLUENCER_DEFAULT_MODE
                if SNA_INFLUENCER_DEFAULT_MODE in valid_modes
                else valid_modes[0]
            )
        _save_applied_influencer_filter_values(
            (applied_search, applied_platform, applied_rows, applied_mode)
        )
    except Exception as exc:
        st.error(f"State filter tabel influencer belum dapat disiapkan: {exc}")


def _apply_influencer_table_filters() -> bool:
    """Terapkan filter tabel hanya ketika nilai draft benar-benar berubah."""
    try:
        current_values = _current_influencer_filter_values()
        changed = current_values != _applied_influencer_filter_values()
        st.session_state[SNA_INFLUENCER_EVENT_KIND_KEY] = "apply"
        st.session_state[SNA_INFLUENCER_EVENT_CHANGED_KEY] = bool(changed)
        if not changed:
            return False

        _save_applied_influencer_filter_values(current_values)
        _show_influencer_table_loading()
        return True
    except Exception as exc:
        st.error(f"Filter tabel influencer belum dapat diterapkan: {exc}")
        return False


def _reset_influencer_table_filters() -> bool:
    """Kembalikan seluruh filter tabel influencer ke nilai awal."""
    try:
        default_values = (
            SNA_INFLUENCER_DEFAULT_SEARCH,
            SNA_INFLUENCER_DEFAULT_PLATFORM,
            SNA_INFLUENCER_DEFAULT_ROWS,
            SNA_INFLUENCER_DEFAULT_MODE,
        )
        pending_changed = _current_influencer_filter_values() != default_values
        table_changed = _applied_influencer_filter_values() != default_values
        changed = bool(pending_changed or table_changed)

        st.session_state[SNA_INFLUENCER_EVENT_KIND_KEY] = "reset"
        st.session_state[SNA_INFLUENCER_EVENT_CHANGED_KEY] = bool(changed)
        if not changed:
            return False

        st.session_state["sna_v9_influencer_search"] = (
            SNA_INFLUENCER_DEFAULT_SEARCH
        )
        st.session_state["sna_v9_influencer_platform"] = (
            SNA_INFLUENCER_DEFAULT_PLATFORM
        )
        st.session_state["sna_v9_influencer_rows"] = (
            SNA_INFLUENCER_DEFAULT_ROWS
        )
        st.session_state["sna_v9_influencer_mode"] = (
            SNA_INFLUENCER_DEFAULT_MODE
        )
        _save_applied_influencer_filter_values(default_values)
        _show_influencer_table_loading()
        return True
    except Exception as exc:
        st.error(f"Filter tabel influencer belum dapat direset: {exc}")
        return False


def _show_influencer_detail_loading() -> None:
    """Aktifkan overlay loading custom saat panel detail akun diubah."""
    try:
        detail_enabled = bool(st.session_state.get("sna_v9_influencer_detail_enabled", False))
        if detail_enabled:
            st.session_state[SNA_ACTION_LOADING_KEY] = "Membuka panel detail akun influencer..."
        else:
            st.session_state[SNA_ACTION_LOADING_KEY] = "Menutup panel detail akun influencer..."
    except Exception as exc:
        st.error(f"Loading panel detail akun belum dapat disiapkan: {exc}")


def _show_influencer_detail_account_loading() -> None:
    """Aktifkan overlay loading custom saat akun detail dipilih."""
    try:
        selected_user = str(st.session_state.get("sna_v9_influencer_detail_username", "akun terpilih")).strip()
        selected_user = selected_user or "akun terpilih"
        st.session_state[SNA_ACTION_LOADING_KEY] = f"Memuat detail akun {selected_user}..."
    except Exception as exc:
        st.error(f"Loading detail akun belum dapat disiapkan: {exc}")


def _show_statistics_fullscreen_loading(chart_name: str = "grafik statistik") -> None:
    """Aktifkan overlay loading custom saat tombol layar penuh statistik diklik."""
    try:
        label = str(chart_name).strip() or "grafik statistik"
        st.session_state[SNA_ACTION_LOADING_KEY] = f"Membuka layar penuh {label}..."
    except Exception as exc:
        st.error(f"Loading layar penuh statistik belum dapat disiapkan: {exc}")


def _ensure_filter_widget_state(available_services: list[str]) -> None:
    """Pastikan nilai awal filter valid sebelum form ditampilkan."""
    try:
        if not available_services:
            available_services = SERVICE_OPTIONS.copy()

        if st.session_state.get("_active_service_sync_target") == "Analisis Jaringan Sosial":
            layanan_global = str(st.session_state.get("active_service", "IndiHome")).strip()
            if layanan_global not in available_services:
                layanan_global = "IndiHome" if "IndiHome" in available_services else available_services[0]
            st.session_state["sna_v9_service_filter"] = layanan_global
            st.session_state[SNA_FILTER_APPLIED_SERVICE_KEY] = layanan_global
            st.session_state.pop("_active_service_sync_target", None)

        if st.session_state.get("sna_v9_service_filter") not in available_services:
            default_service = "IndiHome" if "IndiHome" in available_services else available_services[0]
            st.session_state["sna_v9_service_filter"] = default_service

        if st.session_state.get("sna_v9_platform_filter") not in PLATFORM_OPTIONS:
            st.session_state["sna_v9_platform_filter"] = SNA_FILTER_DEFAULT_PLATFORM

        st.session_state["sna_v9_node_limit"] = _filter_node_limit(
            st.session_state.get("sna_v9_node_limit")
        )

        current_values = _current_filter_values()
        applied_service, applied_platform, applied_node_limit = _applied_filter_values()
        if applied_service not in available_services:
            applied_service = current_values[0]
        if applied_platform not in PLATFORM_OPTIONS:
            applied_platform = current_values[1]
        applied_node_limit = _filter_node_limit(
            applied_node_limit,
            current_values[2],
        )
        _save_applied_filter_values(
            (applied_service, applied_platform, applied_node_limit)
        )
    except Exception as exc:
        st.error(f"Gagal menyiapkan state filter SNA: {exc}")


# -----------------------------------------------------------------------------
# Render section halaman
# -----------------------------------------------------------------------------

def _render_hero(service: str, has_real_data: bool) -> None:
    """Render hero/header halaman SNA dengan sumber file layanan aktif."""
    try:
        badge_class = "sna-v9-badge-real" if has_real_data else "sna-v9-badge-dummy"
        source_names = get_sna_source_names(service) if has_real_data else "fallback otomatis"
        badge_text = f"Data Real: {source_names}" if has_real_data else "Data Dummy: fallback otomatis"
        st.markdown(
            f"""
            <section class="sna-v9-page sna-v9-hero">
                <h1>Social Network Analysis</h1>
                <p>Analisis struktur jaringan percakapan publik layanan Telkom Group untuk membaca relasi akun, mengidentifikasi influencer, dan melihat pola hub-and-spoke lintas platform.</p>
                <div class="sna-v9-badges">
                    <span class="sna-v9-badge {badge_class}">{escape(badge_text)}</span>
                    <span class="sna-v9-badge sna-v9-badge-glass">NetworkX + Pyvis</span>
                    <span class="sna-v9-badge sna-v9-badge-glass">Degree Centrality</span>
                    <span class="sna-v9-badge sna-v9-badge-glass">Twitter/X · Instagram · TikTok</span>
                </div>
            </section>
            """,
            unsafe_allow_html=True,
        )
    except Exception as exc:
        st.error(f"Gagal menampilkan header halaman SNA: {exc}")


@_FRAGMENT_DECORATOR

def _render_filter_controls_fragment(available_services: list[str]) -> None:
    """Render kontrol filter secara terisolasi agar perubahan belum memuat analisis."""
    try:
        _ensure_filter_widget_state(available_services)

        with st.container(border=True):
            st.markdown('<span class="sna-v9-control-marker"></span>', unsafe_allow_html=True)
            st.markdown(
                """
                <div class="sna-v9-section-head">
                    <div>
                        <h2 class="sna-v9-section-title">Filter Analisis</h2>
                        <p class="sna-v9-section-subtitle">Ubah layanan, platform, atau jumlah node terlebih dahulu. Hasil analisis baru dimuat setelah tombol Terapkan Filter diklik.</p>
                        <p class="sna-v9-section-subtitle" style="margin-top:.32rem;"><strong style="color:#FFB4B0;">Telkomsel aktif</strong> dan membaca <code>output_sna.csv</code>, <code>df_edge_telkomsel.csv</code>, atau data Telkomsel di <code>sna_data.csv</code>. Jika file belum ada, dashboard memakai fallback yang diberi penanda Data Dummy.</p>
                    </div>
                </div>
                """,
                unsafe_allow_html=True,
            )

            col_service, col_platform, col_limit = st.columns(
                [1, 1, 1],
                gap="large",
            )
            with col_service:
                st.selectbox(
                    "Pilih Layanan",
                    options=available_services,
                    key="sna_v9_service_filter",
                )
            with col_platform:
                st.selectbox(
                    "Pilih Platform",
                    options=list(PLATFORM_OPTIONS.keys()),
                    key="sna_v9_platform_filter",
                )
            with col_limit:
                st.slider(
                    "Jumlah node graf",
                    min_value=20,
                    max_value=160,
                    step=10,
                    key="sna_v9_node_limit",
                    help="Naikkan jika ingin melihat graf lebih lengkap. Turunkan jika graf terasa berat.",
                )

            current_values = _current_filter_values()
            filter_changed = current_values != _applied_filter_values()
            default_service = (
                "IndiHome"
                if "IndiHome" in available_services
                else available_services[0]
            )

            if not filter_changed:
                st.markdown(
                    """
                    <style>
                        div[data-testid="stVerticalBlockBorderWrapper"]:has(.sna-v9-control-marker)
                        div[data-testid="stButton"] > button[kind="primary"] {
                            cursor: default !important;
                            pointer-events: none !important;
                        }
                    </style>
                    """,
                    unsafe_allow_html=True,
                )

            col_hint, col_reset, col_apply = st.columns([2.15, 0.9, 1.15], gap="small")
            with col_hint:
                st.caption(
                    "Perubahan pilihan di atas tidak akan langsung memuat ulang graf. "
                    "Klik tombol di sebelah kanan untuk menerapkan filter dan menampilkan loading."
                )
            with col_reset:
                reset_clicked = st.button(
                    "Reset Filter",
                    key="sna_v13_reset_filter_button",
                    use_container_width=True,
                )
            with col_apply:
                apply_clicked = st.button(
                    "Terapkan Filter",
                    key="sna_v13_apply_filter_button",
                    type="primary",
                    use_container_width=True,
                )

            if reset_clicked and _reset_sna_filters(default_service):
                st.rerun(scope="app")

            # Guard backend tetap dipertahankan untuk akses keyboard/otomasi.
            if apply_clicked and filter_changed and _apply_sna_filters():
                st.rerun(scope="app")
    except Exception as exc:
        st.error(f"Gagal menampilkan kontrol filter halaman SNA: {exc}")


def _render_filters(clean_df: pd.DataFrame) -> tuple[str, str, int, bool]:
    """Render kontrol filter dan kembalikan snapshot yang sudah diterapkan."""
    try:
        available_services = [
            service
            for service in SERVICE_OPTIONS
            if service in set(clean_df.get("layanan", []))
        ]
        if not available_services:
            available_services = SERVICE_OPTIONS.copy()

        _ensure_filter_widget_state(available_services)
        _render_filter_controls_fragment(available_services)

        selected_service, selected_platform_label, node_limit = _applied_filter_values()
        if selected_service not in available_services:
            selected_service = (
                "IndiHome" if "IndiHome" in available_services else available_services[0]
            )
        if selected_platform_label not in PLATFORM_OPTIONS:
            selected_platform_label = SNA_FILTER_DEFAULT_PLATFORM
        selected_platform = PLATFORM_OPTIONS[selected_platform_label]

        event_kind = str(st.session_state.pop(SNA_FILTER_EVENT_KIND_KEY, ""))
        event_changed = bool(
            st.session_state.pop(SNA_FILTER_EVENT_CHANGED_KEY, False)
        )
        filter_applied = bool(
            event_changed and event_kind in {"apply", "reset"}
        )
        if filter_applied:
            st.session_state["active_service"] = selected_service
            activity_description = (
                f"Mereset filter analisis jaringan untuk layanan {selected_service}."
                if event_kind == "reset"
                else f"Menjalankan analisis jaringan untuk layanan {selected_service}."
            )
            log_activity(
                "SNA_ANALYSIS",
                "Social Network Analysis",
                activity_description,
                service=selected_service,
                platform=selected_platform_label,
                metadata={
                    "node_limit": int(node_limit),
                    "filter_action": event_kind,
                },
            )
        return selected_service, selected_platform, int(node_limit), filter_applied
    except Exception as exc:
        st.error(f"Gagal menampilkan filter halaman SNA: {exc}")
        return "IndiHome", "all", 80, False

@_FRAGMENT_DECORATOR
def _render_influencer_table_filter_fragment(
    platform_labels: list[str],
    row_options: list[int],
    mode_options: list[str],
) -> None:
    """Render filter tabel influencer tanpa memuat ulang seluruh halaman."""
    try:
        _ensure_influencer_filter_state(
            platform_labels,
            row_options,
            mode_options,
        )

        with st.container(border=True):
            st.markdown(
                '<span class="sna-v12-filter-marker"></span>',
                unsafe_allow_html=True,
            )
            col_search, col_platform, col_rows, col_mode = st.columns(
                [1.35, 1, 0.75, 1.05]
            )
            with col_search:
                st.text_input(
                    "Cari username",
                    placeholder="Contoh: indihome",
                    key="sna_v9_influencer_search",
                )
            with col_platform:
                st.selectbox(
                    "Filter platform tabel",
                    options=platform_labels,
                    key="sna_v9_influencer_platform",
                )
            with col_rows:
                st.selectbox(
                    "Jumlah baris",
                    options=row_options,
                    key="sna_v9_influencer_rows",
                )
            with col_mode:
                st.selectbox(
                    "Mode ranking",
                    options=mode_options,
                    key="sna_v9_influencer_mode",
                )

            filter_changed = (
                _current_influencer_filter_values()
                != _applied_influencer_filter_values()
            )
            if not filter_changed:
                st.markdown(
                    """
                    <style>
                        div[data-testid="stVerticalBlockBorderWrapper"]:has(.sna-v12-filter-marker)
                        button[kind="primary"] {
                            cursor: default !important;
                            pointer-events: none !important;
                        }
                    </style>
                    """,
                    unsafe_allow_html=True,
                )

            col_hint, col_reset, col_apply = st.columns(
                [2.15, 0.9, 1.2],
                gap="small",
            )
            with col_hint:
                st.caption(
                    "Atur pencarian, platform, jumlah baris, dan mode ranking "
                    "terlebih dahulu. Tabel baru diperbarui setelah tombol di "
                    "sebelah kanan diklik."
                )
            with col_reset:
                reset_clicked = st.button(
                    "Reset Filter",
                    key="sna_v13_reset_influencer_table_filter",
                    use_container_width=True,
                )
            with col_apply:
                apply_clicked = st.button(
                    "Terapkan Filter Tabel",
                    key="sna_v13_apply_influencer_table_filter",
                    type="primary",
                    use_container_width=True,
                )

            if reset_clicked and _reset_influencer_table_filters():
                st.rerun(scope="app")

            # Guard backend menjaga klik/otomasi tidak melakukan apa pun
            # ketika nilai filter sama dengan snapshot tabel aktif.
            if (
                apply_clicked
                and filter_changed
                and _apply_influencer_table_filters()
            ):
                st.rerun(scope="app")
    except Exception as exc:
        st.error(f"Filter tabel influencer belum dapat ditampilkan: {exc}")


def _render_influencer_tables(node_df: pd.DataFrame, service: str, platform: str) -> None:
    """Render tabel influencer yang lebih rapi, ringan, dan interaktif."""
    try:
        with st.container(border=True):
            st.markdown('<span class="sna-v9-section-marker"></span><span class="sna-v12-influencer-marker"></span>', unsafe_allow_html=True)
            active_platform_label = "Semua Platform" if platform == "all" else PLATFORM_DISPLAY.get(platform, str(platform).title())
            _render_compact_html(
                f"""
                <div class="sna-v12-influencer-hero">
                    <div>
                        <h2 class="sna-v9-section-title">Tabel Metrik Influencer</h2>
                        <p class="sna-v9-section-subtitle">Gunakan pencarian, filter platform, jumlah baris, dan mode ranking untuk membandingkan posisi struktural akun dengan potensi jangkauannya.</p>
                    </div>
                    <span class="sna-v12-live-badge"><span class="sna-v12-live-dot"></span>Analisis influencer aktif</span>
                </div>
                <div class="sna-v12-chip-row">
                    <span class="sna-v12-chip"><span class="sna-v12-chip-dot" style="--chip-color:#E53935;"></span>{escape(str(service))}</span>
                    <span class="sna-v12-chip"><span class="sna-v12-chip-dot" style="--chip-color:#1DA1F2;"></span>{escape(str(active_platform_label))}</span>
                    <span class="sna-v12-chip"><span class="sna-v12-chip-dot" style="--chip-color:#833AB4;"></span>Degree dan Followers</span>
                    <span class="sna-v12-chip"><span class="sna-v12-chip-dot" style="--chip-color:#4CAF50;"></span>Filter interaktif</span>
                </div>
                """
            )

            if node_df is not None and not node_df.empty:
                excluded_mask = node_df["username"].map(_is_excluded_from_influencer)
                non_brand = node_df[
                    (~node_df["is_brand"].astype(bool)) & (~excluded_mask)
                ].copy()
            else:
                non_brand = pd.DataFrame()
            if non_brand.empty:
                st.info("Belum ada akun non-brand untuk ditampilkan pada tabel influencer.")
                return

            _render_influencer_summary_cards(non_brand)
            st.markdown(
                '<div class="sna-v9-influencer-control-note">Atur pencarian, platform, jumlah baris, dan jenis ranking sesuai kebutuhan. Hasil tabel akan diperbarui setelah tombol Terapkan Filter Tabel diklik.</div>',
                unsafe_allow_html=True,
            )

            platform_labels = ["Semua Platform"] + sorted(non_brand["platform_label"].dropna().astype(str).unique().tolist())
            row_options = [5, 10, 15, 20]
            mode_options = ["Dua Ranking", "Degree Saja", "Followers Saja"]

            _render_influencer_table_filter_fragment(
                platform_labels,
                row_options,
                mode_options,
            )
            _ensure_influencer_filter_state(
                platform_labels,
                row_options,
                mode_options,
            )
            search_keyword, selected_platform, row_limit, view_mode = (
                _applied_influencer_filter_values()
            )

            event_kind = str(
                st.session_state.pop(SNA_INFLUENCER_EVENT_KIND_KEY, "")
            )
            event_changed = bool(
                st.session_state.pop(
                    SNA_INFLUENCER_EVENT_CHANGED_KEY,
                    False,
                )
            )
            if event_changed and event_kind in {"apply", "reset"}:
                message = (
                    "Filter tabel influencer berhasil direset."
                    if event_kind == "reset"
                    else "Filter tabel influencer berhasil diterapkan."
                )
                st.success(message, icon="✅")

            filtered_table_df = non_brand.copy()
            if selected_platform != "Semua Platform":
                filtered_table_df = filtered_table_df[filtered_table_df["platform_label"].astype(str) == selected_platform]
            if search_keyword.strip():
                keyword = search_keyword.strip().lower()
                filtered_table_df = filtered_table_df[
                    filtered_table_df["username"].astype(str).str.lower().str.contains(keyword, na=False)
                ]

            if filtered_table_df.empty:
                st.markdown(
                    '<div class="sna-v9-empty">Tidak ada akun yang cocok dengan pencarian atau filter platform tabel.</div>',
                    unsafe_allow_html=True,
                )
                return

            top_degree = filtered_table_df.sort_values(
                ["degree_centrality", "followers", "username"],
                ascending=[False, False, True],
            ).head(int(row_limit))
            top_followers = filtered_table_df[filtered_table_df["followers"] > 0].sort_values(
                ["followers", "degree_centrality", "username"],
                ascending=[False, False, True],
            ).head(int(row_limit))

            if view_mode == "Degree Saja":
                table_html = _build_influencer_html_table(
                    top_degree,
                    "Ranking Degree Centrality",
                    "Akun dengan posisi struktural paling kuat dalam jaringan aktif.",
                    "degree",
                    int(row_limit),
                )
                st.markdown(_compact_html(f'<div class="sna-v9-influencer-grid" style="grid-template-columns:1fr;">{table_html}</div>'), unsafe_allow_html=True)
            elif view_mode == "Followers Saja":
                table_html = _build_influencer_html_table(
                    top_followers,
                    "Ranking Followers",
                    "Akun dengan potensi jangkauan terbesar berdasarkan jumlah followers.",
                    "followers",
                    int(row_limit),
                )
                st.markdown(_compact_html(f'<div class="sna-v9-influencer-grid" style="grid-template-columns:1fr;">{table_html}</div>'), unsafe_allow_html=True)
            else:
                degree_html = _build_influencer_html_table(
                    top_degree,
                    "Ranking Degree Centrality",
                    "Membaca aktor sentral berdasarkan relasi langsung dalam jaringan.",
                    "degree",
                    int(row_limit),
                )
                followers_html = _build_influencer_html_table(
                    top_followers,
                    "Ranking Followers",
                    "Membaca potensi jangkauan akun berdasarkan followers.",
                    "followers",
                    int(row_limit),
                )
                st.markdown(_compact_html(f'<div class="sna-v9-influencer-grid">{degree_html}{followers_html}</div>'), unsafe_allow_html=True)

            st.caption("* Akun layanan resmi dikeluarkan dari daftar ini")

            detail_options = filtered_table_df.sort_values(
                ["degree_centrality", "followers", "username"],
                ascending=[False, False, True],
            )["username"].astype(str).tolist()
            detail_enabled = st.toggle(
                "Tampilkan panel detail akun",
                value=False,
                key="sna_v9_influencer_detail_enabled",
                help="Aktifkan jika ingin melihat metrik lengkap satu akun tanpa membuka tabel data besar.",
                on_change=_show_influencer_detail_loading,
            )
            if detail_enabled and detail_options:
                selected_username = st.selectbox(
                    "Pilih akun untuk dilihat detailnya",
                    options=detail_options,
                    key="sna_v9_influencer_detail_username",
                    on_change=_show_influencer_detail_account_loading,
                )
                _render_selected_account_detail(filtered_table_df, selected_username)
                st.markdown('<div class="sna-v9-detail-export-gap"></div>', unsafe_allow_html=True)

            export_table = filtered_table_df.copy()
            if not export_table.empty:
                export_table = export_table[
                    ["username", "platform_label", "followers", "degree_centrality", "in_degree", "out_degree", "degree"]
                ].rename(
                    columns={
                        "username": "Username",
                        "platform_label": "Platform",
                        "followers": "Followers",
                        "degree_centrality": "Degree Centrality",
                        "in_degree": "In-Degree",
                        "out_degree": "Out-Degree",
                        "degree": "Degree",
                    }
                )
                platform_filename = "semua-platform" if platform == "all" else platform
                st.download_button(
                    label="⬇️ Export CSV Tabel Influencer Terfilter",
                    data=export_to_csv(export_table, "influencer_sna"),
                    file_name=get_export_filename(
                        "influencer_sna",
                        platform=f"{service.lower()}-{platform_filename}",
                        ext="csv",
                    ),
                    mime="text/csv",
                    use_container_width=True,
                    key="download_sna_v9_influencer_csv",
                )
    except Exception as exc:
        st.error(f"Gagal menampilkan tabel influencer: {exc}")

def _render_statistics_expander(node_df: pd.DataFrame) -> None:
    """Render expander statistik detail dengan fullscreen dialog seperti halaman Dataset."""
    try:
        with st.expander("Lihat Statistik Detail", expanded=False):
            hist_fig = _create_degree_histogram(node_df)
            pie_fig = _create_platform_pie(node_df)

            col_left, col_right = st.columns(2, gap="medium")
            with col_left:
                judul_hist, aksi_hist = st.columns([3.5, 1.35], gap="small")
                with judul_hist:
                    st.markdown(
                        '<div class="sna-v9-section-title">Histogram Degree Centrality</div>',
                        unsafe_allow_html=True,
                    )
                with aksi_hist:
                    st.markdown(
                        '<span class="sna-v9-chart-action-marker" aria-hidden="true">Perbesar</span>',
                        unsafe_allow_html=True,
                    )
                    if st.button(
                        "⛶ Layar Penuh",
                        key="sna_v9_fullscreen_degree_histogram",
                        help="Tampilkan histogram degree centrality dalam layar penuh.",
                        on_click=_show_statistics_fullscreen_loading,
                        args=("histogram degree centrality",),
                        **_opsi_lebar_penuh(st.button),
                    ):
                        _tampilkan_chart_layar_penuh_sna(
                            "Histogram Degree Centrality",
                            hist_fig,
                        )
                _plotly_chart_aman(
                    hist_fig,
                    config={"displayModeBar": False, "responsive": True},
                    **_opsi_lebar_penuh(st.plotly_chart),
                )

            with col_right:
                judul_pie, aksi_pie = st.columns([3.5, 1.35], gap="small")
                with judul_pie:
                    st.markdown(
                        '<div class="sna-v9-section-title">Distribusi Node per Platform</div>',
                        unsafe_allow_html=True,
                    )
                with aksi_pie:
                    st.markdown(
                        '<span class="sna-v9-chart-action-marker" aria-hidden="true">Perbesar</span>',
                        unsafe_allow_html=True,
                    )
                    if st.button(
                        "⛶ Layar Penuh",
                        key="sna_v9_fullscreen_platform_pie",
                        help="Tampilkan diagram distribusi platform dalam layar penuh.",
                        on_click=_show_statistics_fullscreen_loading,
                        args=("diagram distribusi node per platform",),
                        **_opsi_lebar_penuh(st.button),
                    ):
                        _tampilkan_chart_layar_penuh_sna(
                            "Distribusi Node per Platform",
                            pie_fig,
                        )
                _plotly_chart_aman(
                    pie_fig,
                    config={"displayModeBar": False, "responsive": True},
                    **_opsi_lebar_penuh(st.plotly_chart),
                )

            st.caption(
                "Histogram menunjukkan persebaran degree centrality. "
                "Pie chart menunjukkan komposisi node berdasarkan platform pada filter aktif."
            )
    except Exception as exc:
        st.error(f"Gagal menampilkan statistik detail: {exc}")


def _render_method_card() -> None:
    """Render card penjelasan metode SNA yang dipakai pada dashboard."""
    try:
        st.markdown(
            """
            <section class="sna-v9-method-card">
                <div class="sna-v9-method-head">
                    <div class="sna-v9-method-icon">SNA</div>
                    <div>
                        <div class="sna-v9-method-kicker">Catatan metode</div>
                        <h3>Kenapa Degree Centrality yang Dipakai?</h3>
                    </div>
                </div>
                <p class="sna-v9-method-lead">Dashboard ini memprioritaskan <strong>degree centrality</strong>, <strong>in-degree</strong>, <strong>out-degree</strong>, dan <strong>followers</strong> karena struktur percakapan media sosial pada data penelitian cenderung berbentuk <em>hub-and-spoke</em>: banyak akun pengguna berinteraksi langsung dengan akun brand, tetapi tidak selalu saling terhubung satu sama lain.</p>
                <div class="sna-v9-method-grid">
                    <div class="sna-v9-method-mini">
                        <span class="sna-v9-method-chip">Dipakai</span>
                        <strong>Degree Centrality</strong>
                        <p>Mengukur seberapa banyak koneksi langsung yang dimiliki akun. Cocok untuk membaca akun yang paling sering terhubung dalam percakapan.</p>
                    </div>
                    <div class="sna-v9-method-mini">
                        <span class="sna-v9-method-chip">Pendukung</span>
                        <strong>In/Out-Degree + Followers</strong>
                        <p>In-degree dan out-degree membaca arah interaksi, sedangkan followers membantu menilai potensi jangkauan audiens.</p>
                    </div>
                    <div class="sna-v9-method-mini">
                        <span class="sna-v9-method-chip">Dibatasi</span>
                        <strong>Closeness & Betweenness</strong>
                        <p>Pada graf yang tidak selalu strongly connected, dua metrik ini kurang stabil dan dapat terlalu terpusat pada akun brand.</p>
                    </div>
                </div>
                <div class="sna-v9-method-note">
                    <strong>Interpretasi utama:</strong> kombinasi degree centrality dan followers lebih relevan untuk membaca dua aspek influencer, yaitu posisi struktural akun dalam jaringan dan potensi jangkauan audiens.
                </div>
            </section>
            """,
            unsafe_allow_html=True,
        )
    except Exception as exc:
        st.error(f"Gagal menampilkan card penjelasan metode: {exc}")


# -----------------------------------------------------------------------------
# Entry point halaman
# -----------------------------------------------------------------------------

def render_sna() -> None:
    """Render halaman utama Social Network Analysis."""
    action_loading_handle = None

    try:
        # Callback tombol Terapkan Filter mengisi key ini sebelum rerun.
        # Overlay dipanggil paling awal agar pengguna melihat loading custom,
        # bukan efek layar redup bawaan Streamlit ketika halaman sedang stale.
        loading_label = st.session_state.pop(SNA_ACTION_LOADING_KEY, None)
        if loading_label:
            action_loading_handle = _start_filter_loading(str(loading_label))

        _inject_sna_css()
        _inject_sna_light_mode_patch()

        # Hero tetap ditampilkan sebagai bagian pertama halaman. Nilai layanan
        # awal dibaca dari state filter yang sudah tersimpan pada rerun sebelumnya.
        active_service = str(
            st.session_state.get(
                SNA_FILTER_APPLIED_SERVICE_KEY,
                st.session_state.get("sna_v9_service_filter", "IndiHome"),
            )
        )
        if active_service not in SERVICE_OPTIONS:
            active_service = "IndiHome"
        _render_hero(
            active_service,
            False
            if bool(st.session_state.get("demo_mode", False))
            else sna_file_exists(active_service),
        )

        # Daftar layanan bersifat baku. Setelah pengguna memilih layanan,
        # dashboard hanya memuat sumber kanonik yang relevan. Khusus IndiBiz,
        # sumber Twitter/X dan Instagram–TikTok digabung tanpa membaca file mentah.
        filter_seed = pd.DataFrame({"layanan": SERVICE_OPTIONS})
        selected_service, selected_platform, node_limit, filter_submitted = _render_filters(filter_seed)

        # Setiap layanan memakai loader kanoniknya. Loader Telkomsel menerima
        # output notebook yang sudah ada tanpa membuka atau mengubah file .ipynb.
        with st.spinner(f"Memuat data SNA {selected_service}..."):
            if bool(st.session_state.get("demo_mode", False)):
                raw_df = get_demo_sna(selected_service)
            elif selected_service == "IndiBiz":
                # Loader generik IndiBiz memang dirancang menggabungkan output
                # Twitter/X dan output Instagram-TikTok bila keduanya tersedia.
                # Loader khusus lama hanya membaca satu file sehingga graf dapat
                # terlihat seluruhnya sebagai Twitter/X.
                raw_df = load_sna_data("IndiBiz")
            elif selected_service == "Telkomsel":
                raw_df = load_telkomsel_sna()
            else:
                raw_df = load_indihome_sna()
            clean_df = _prepare_sna_dataframe(raw_df)

        if clean_df.empty:
            st.warning(
                f"Data SNA {selected_service} belum tersedia atau kolomnya belum sesuai. "
                "Periksa file pada folder data."
            )
            return

        if filter_submitted:
            st.success("Filter berhasil diterapkan. Metrik, graf, tabel, dan statistik sudah mengikuti pilihan terbaru.", icon="✅")

        filtered_df = _filter_sna_dataframe(clean_df, selected_service, selected_platform)

        if filtered_df.empty:
            platform_label = next((label for label, value in PLATFORM_OPTIONS.items() if value == selected_platform), selected_platform)
            st.markdown(
                f"""
                <div class="sna-v9-empty">
                    Data SNA untuk layanan <strong>{escape(selected_service)}</strong> dan platform <strong>{escape(platform_label)}</strong> belum tersedia pada file saat ini. Coba pilih platform lain atau periksa file SNA kanonik di folder <code>data</code>.
                </div>
                """,
                unsafe_allow_html=True,
            )
            return

        graph, node_df, edge_df, summary = _analyze_network(
            filtered_df,
            calculate_pagerank=True,
        )
        if graph.number_of_nodes() == 0 or node_df.empty:
            st.warning("Graf tidak dapat dibangun dari data yang sudah difilter.")
            return

        _render_metric_cards(summary, node_df)
        _render_pagerank_overview(node_df, selected_service)

        # Fase 8: hitung dan simpan statistik yang setara dengan Cell [10] IndiBiz.
        if selected_service == "IndiBiz":
            network_stats = _calculate_network_statistics(graph, filtered_df)
            st.session_state["indibiz_network_stats"] = network_stats
            _render_indibiz_network_statistics(
                network_stats,
                get_sna_source_names(selected_service),
                selected_platform,
            )
            _render_indibiz_static_network_graph(clean_df)

        _render_network_graph(graph, node_df, node_limit, selected_service)
        _render_influencer_tables(node_df, selected_service, selected_platform)
        _render_statistics_expander(node_df)
        _render_method_card()

        st.caption(
            "SNA dihitung dari edge list terfilter. Jika sumber data dummy aktif, hasil hanya untuk demonstrasi antarmuka dan bukan temuan final penelitian."
        )
    except Exception as exc:
        st.error(f"Gagal memuat halaman Social Network Analysis: {exc}")
    finally:
        _finish_filter_loading(action_loading_handle)
