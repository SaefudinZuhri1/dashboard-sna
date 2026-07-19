# pages/recommendation.py
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

import networkx as nx
import pandas as pd
import plotly.graph_objects as go
import streamlit as st
import streamlit.components.v1 as components

from utils.gemini_client import (
    GEMINI_AVAILABLE,
    generate_content_idea,
    get_fallback_content_idea,
    get_gemini_runtime_status,
)
from utils.dummy_data import get_dummy_topic_data
from utils.data_loader import (
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
    from utils.loading_screen import mulai_loading_aksi, selesaikan_loading_aksi
except Exception:  # pragma: no cover - fallback jika utilitas loading belum tersedia
    mulai_loading_aksi = None
    selesaikan_loading_aksi = None


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
# FASE12_UI_AI_STUDIO_V1_5
# FASE12_FILTER_MANUAL_V1_4
# FASE12_INFLUENCER_DETAIL_CUSTOM_LOADING_V1_9
# Nilai draft hanya mengikuti pilihan pengguna di dalam form. Nilai aktif baru
# berubah setelah tombol Terapkan Filter ditekan.
RECOMMENDATION_FILTER_DEFAULTS = {
    "layanan": "IndiHome",
    "platform": "Instagram",
    "topik": "Gangguan Sinyal dan Jaringan Internet",
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
    font-size: 11px;
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
    font-size: 10px;
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
    overflow: hidden;
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
    transition: transform .28s ease, border-color .28s ease, box-shadow .28s ease;
}
.rec-ai-shell:hover {
    transform: translateY(-3px);
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
    z-index: -2;
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
    left: 24px;
    right: 24px;
    bottom: 0;
    height: 3px;
    border-radius: 999px 999px 0 0;
    background: linear-gradient(90deg, #E53935, #FFB020, #1DA1F2, #8B5CF6, #4CAF50, #E53935);
    background-size: 220% 100%;
    opacity: .95;
    animation: recAiBorderFlow 7s linear infinite;
}
.rec-ai-orb {
    position: absolute;
    z-index: -1;
    width: 210px;
    height: 210px;
    border-radius: 50%;
    filter: blur(18px);
    opacity: .22;
    pointer-events: none;
}
.rec-ai-orb.one {
    top: -120px;
    left: 8%;
    background: #E53935;
    animation: recAiFloatOne 9s ease-in-out infinite;
}
.rec-ai-orb.two {
    right: 5%;
    bottom: -150px;
    background: #1DA1F2;
    animation: recAiFloatTwo 11s ease-in-out infinite;
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
    animation: recAiLogoPulse 3.4s ease-in-out infinite;
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
    font-size: 10px;
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
    backdrop-filter: blur(8px);
    font-size: 10px;
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
    backdrop-filter: blur(10px);
    font-size: 10px;
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
    box-shadow: 0 0 14px currentColor;
    animation: recAiStatusPulse 1.8s ease-in-out infinite;
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
    font-size: 11px;
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
    font-size: 9px;
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
    font-size: 9px;
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
    font-size: 9px;
    letter-spacing: .08em;
    text-transform: uppercase;
}
.rec-ai-copy-heading {
    display: flex;
    align-items: center;
    gap: 8px;
    margin: 15px 0 9px;
    color: #FFFFFF;
    font-size: 10px;
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
    font-size: 10px;
    font-weight: 900;
}
.rec-ai-idea-row p,
.rec-ai-copy-text {
    margin: 0;
    color: rgba(255,255,255,.79);
    font-size: 11px;
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
    font-size: 9px;
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
    font-size: 10px;
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
    font-size: 10px;
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
    font-size: 11px;
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
    font-size: 11px;
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
    font-size: 9px;
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
    font-size: 9px;
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
    font-size: 9px;
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
    .rec-ai-shell { padding: 20px 17px; border-radius: 20px; }
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
    font-size: 11px;
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
    font-size: 11px;
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
    font-size: 11px;
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

.rec-influencer-card {
    position: relative;
    display: flex;
    flex-direction: column;
    height: 452px;
    min-height: 452px;
    padding: 19px;
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
    font-size: 11px;
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
    font-size: 10px;
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
    gap: 8px;
    margin-bottom: 14px;
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
    font-size: 10px;
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
    gap: 6px;
    min-height: 52px;
    margin-bottom: 12px;
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
    font-size: 10px;
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
    height: 154px;
    min-height: 154px;
    /* Posisi vertikal panel dikendalikan langsung pada outer wrapper HTML. */
    margin-top: 4px;
    padding: 12px 10px 12px 13px;
    overflow: hidden;
    border: 1px solid #2B2B2B;
    border-radius: 10px;
    background: #141414;
}

.rec-content-preview-head {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 8px;
    /* Dekatkan area bukti ke judul agar panel tidak menyisakan ruang kosong. */
    margin-bottom: 3px;
}

.rec-content-preview-title {
    color: #F3F3F3;
    font-size: 10px;
    font-weight: 800;
    letter-spacing: .055em;
    text-transform: uppercase;
}

.rec-content-source-badge {
    flex: 0 0 auto;
    padding: 3px 7px;
    border: 1px solid rgba(76,175,80,.35);
    border-radius: 999px;
    color: #81C784;
    background: rgba(76,175,80,.08);
    font-size: 8px;
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
    /* Isi scroll tetap pada posisi normal di dalam panel. */
    margin-top: 0;
    margin-bottom: 0;
    flex: 0 0 96px;
    width: 100%;
    height: 96px;
    min-height: 96px;
    max-height: 96px;
    padding: 0 5px 4px 0;
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
    gap: 8px;
    min-width: 0;
    margin: 0;
    padding: 0 2px 12px 0;
    list-style: none;
}

.rec-content-list li {
    display: grid;
    grid-template-columns: 18px minmax(0, 1fr);
    align-items: start;
    gap: 7px;
    color: #C8C8C8;
    font-size: 10px;
    line-height: 1.45;
}

.rec-content-list li > span:last-child {
    min-width: 0;
    overflow-wrap: anywhere;
    word-break: break-word;
}

.rec-content-preview-meta {
    display: block;
    margin-top: 3px;
    color: #777777;
    font-size: 8px;
    line-height: 1.3;
}

.rec-content-index {
    display: grid;
    place-items: center;
    width: 18px;
    height: 18px;
    border: 1px solid rgba(229,57,53,.38);
    border-radius: 5px;
    color: #FF7773;
    background: rgba(229,57,53,.08);
    font-size: 8px;
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
    font-size: 10px;
    font-weight: 800;
}

.rec-detail-content-text {
    margin: 0;
    color: #E1E1E1;
    font-size: 11px;
    line-height: 1.5;
}

.rec-detail-content-meta {
    display: flex;
    flex-wrap: wrap;
    gap: 6px;
    margin-top: 6px;
    color: #888888;
    font-size: 9px;
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
    font-size: 9px;
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
    font-size: 9px;
    font-weight: 700;
}

.rec-detail-recommendation {
    margin: 0;
    color: #D2D2D2;
    font-size: 11px;
    line-height: 1.62;
}

.rec-detail-note {
    margin-top: 10px;
    padding: 9px 10px;
    border-left: 2px solid #FF9800;
    border-radius: 6px;
    color: #C7C7C7;
    background: rgba(255,152,0,.07);
    font-size: 10px;
    line-height: 1.5;
}

@media (max-width: 1100px) {
    .rec-influencer-card {
        height: 470px;
        min-height: 470px;
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
    font-size: 10px;
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
    font-size: 10px;
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
    font-size: 9px;
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
    font-size: 9px;
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
    font-size: 9px;
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
    font-size: 10px;
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
    font-size: 8px;
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
    font-size: 9px;
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
    font-size: 10px;
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
    font-size: 9px;
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
    font-size: 10px;
    font-weight: 850;
}

.rec-detail-strategy-title {
    display: block;
    margin-bottom: 5px;
    color: #FFFFFF;
    font-size: 11px;
    font-weight: 850;
}

.rec-detail-recommendation {
    margin: 0;
    color: #CFCFCF;
    font-size: 11px;
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
    font-size: 9px;
}

.rec-detail-basis-row strong {
    color: #EAEAEA;
    font-weight: 800;
    text-align: right;
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
    font-size: 10px;
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
    font-size: 11px;
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
    font-size: 10px;
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
    font-size: 10px;
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
    font-size: 11px;
    font-weight: 600;
    letter-spacing: 0;
}

.rec-topic-stat-note {
    display: block;
    margin-top: 8px;
    color: #8E8E8E;
    font-size: 11px;
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
    font-size: 11px;
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
    font-size: 10px;
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
    font-size: 10px;
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
    font-size: 11px;
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
    font-size: 9px;
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
    font-size: 10px;
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
    font-size: 10px;
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
    font-size: 10.5px;
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
    font-size: 9px;
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
    font-size: 11px;
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
    font-size: 10px;
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
    font-size: 10px;
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
    font-size: 10px;
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
    font-size: 10px;
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
    font-size: 11px;
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
    font-size: 11px;
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
    font-size: 11px;
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
    font-size: 11.2px !important;
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
    font-size: 10px;
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
    font-size: 10px;
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
    font-size: 10px;
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


@st.cache_data(show_spinner=False, persist="disk", max_entries=12)
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


@st.cache_data(show_spinner=False, persist="disk", max_entries=12)
def _build_topic_summary(layanan: str) -> tuple[pd.DataFrame, dict[str, Any]]:
    """Bangun ringkasan lima topik dari data aktual atau fallback."""
    try:
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


def _calculate_influencers_from_sna(
    df: pd.DataFrame,
    layanan: str,
) -> pd.DataFrame:
    """Hitung kandidat influencer per platform dari edge list SNA."""
    try:
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


@st.cache_data(show_spinner=False, persist="disk", max_entries=12)
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
        work["username"] = work["username"].map(_safe_username)
        work["username_key"] = work["username"].map(_username_lookup_key)
        work["platform"] = (
            work["platform"]
            .fillna("")
            .astype(str)
            .str.lower()
            .str.strip()
            .replace({"x": "twitter", "twitter/x": "twitter", "ig": "instagram"})
        )
        work["content_clean"] = work["content"].map(_clean_content_text)
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

    # Transformasi log menjaga followers/engagement besar tidak mendominasi skor.
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

    result["selection_basis"] = result.apply(
        lambda row: (
            "Jaringan + konten asli"
            if float(row.get("degree_centrality", 0)) > 0
            else "Konten asli + jangkauan"
        ),
        axis=1,
    )
    return result



@st.cache_data(show_spinner=False, persist="disk", max_entries=12)
def _build_indibiz_influencer_data() -> tuple[pd.DataFrame, dict[str, Any]]:
    """Pilih Top 5 influencer IndiBiz dari followers dan degree centrality."""
    columns = [
        "username", "username_key", "platform", "followers",
        "degree_centrality", "network_edges", "content_count",
        "relevant_content_count", "content_engagement", "dominant_topic",
        "content_topics", "recommendation_score", "recommendation_rank",
        "selection_basis", "layanan",
    ]
    try:
        sna_df = load_sna_data("IndiBiz").copy()
        service_df = _filter_sna_by_service(sna_df, "IndiBiz")
        candidates = _calculate_influencers_from_sna(service_df, "IndiBiz")
        if candidates.empty:
            raise ValueError("Edge SNA IndiBiz tidak menghasilkan kandidat non-brand.")

        candidates["followers"] = pd.to_numeric(
            candidates["followers"], errors="coerce"
        ).fillna(0).clip(lower=0)
        candidates["degree_centrality"] = pd.to_numeric(
            candidates["degree_centrality"], errors="coerce"
        ).fillna(0).clip(lower=0)
        candidates["network_edges"] = pd.to_numeric(
            candidates["network_edges"], errors="coerce"
        ).fillna(0).clip(lower=0)

        follower_log = candidates["followers"].map(math.log1p)
        follower_max = float(follower_log.max()) if not follower_log.empty else 0.0
        degree_max = float(candidates["degree_centrality"].max()) if not candidates.empty else 0.0
        follower_norm = follower_log / follower_max if follower_max > 0 else 0.0
        degree_norm = (
            candidates["degree_centrality"] / degree_max
            if degree_max > 0
            else 0.0
        )
        candidates["recommendation_score"] = (
            degree_norm * 0.55 + follower_norm * 0.45
        )
        candidates["selection_basis"] = "Followers + degree centrality"

        # Konten asli memperkaya detail kartu, tetapi tidak menjadi syarat agar
        # influencer SNA IndiBiz dapat tampil.
        content_stats = _build_content_author_stats("IndiBiz")
        if not content_stats.empty:
            candidates = candidates.merge(
                content_stats,
                on=["username_key", "platform"],
                how="left",
                suffixes=("", "_content"),
            )
            if "followers_content" in candidates.columns:
                candidates["followers"] = candidates[["followers", "followers_content"]].max(axis=1)
                candidates = candidates.drop(columns=["followers_content"], errors="ignore")
            if "username_content" in candidates.columns:
                candidates["username"] = candidates["username_content"].fillna(candidates["username"])
                candidates = candidates.drop(columns=["username_content"], errors="ignore")

        for column in (
            "content_count", "relevant_content_count", "content_engagement",
        ):
            if column not in candidates.columns:
                candidates[column] = 0
            candidates[column] = pd.to_numeric(
                candidates[column], errors="coerce"
            ).fillna(0)
        for column in ("dominant_topic", "content_topics"):
            if column not in candidates.columns:
                candidates[column] = ""
            candidates[column] = candidates[column].fillna("").astype(str)

        ranked = candidates.sort_values(
            ["recommendation_score", "degree_centrality", "followers", "username"],
            ascending=[False, False, False, True],
        ).drop_duplicates(subset=["username_key", "platform"], keep="first")

        # Ambil kandidat terbaik tiap platform lebih dahulu agar Top 5 tetap
        # merepresentasikan Twitter/X, Instagram, dan TikTok bila datanya ada.
        selected_indices: list[int] = []
        for platform in PLATFORM_ORDER:
            group = ranked[ranked["platform"].eq(platform)]
            if not group.empty:
                selected_indices.append(int(group.index[0]))
        for index_value in ranked.index:
            if int(index_value) not in selected_indices:
                selected_indices.append(int(index_value))
            if len(selected_indices) >= 5:
                break

        result = ranked.loc[selected_indices[:5]].copy()
        result = result.sort_values(
            ["recommendation_score", "degree_centrality", "followers"],
            ascending=[False, False, False],
        ).reset_index(drop=True)
        result["recommendation_rank"] = range(1, len(result) + 1)
        result["layanan"] = "IndiBiz"
        for column in columns:
            if column not in result.columns:
                result[column] = "" if column in {
                    "username", "username_key", "platform", "dominant_topic",
                    "content_topics", "selection_basis", "layanan",
                } else 0
        result = result[columns]

        is_real = sna_file_exists("IndiBiz")
        source_name = (
            get_sna_source_names("IndiBiz")
            if is_real
            else "Dummy SNA IndiBiz dari utils/dummy_data.py"
        )
        return result, {
            "is_real": is_real,
            "source_name": source_name,
            "actual_rows": int(len(result)),
            "content_authors": int(len(content_stats)),
            "ranking_method": "55% degree centrality + 45% followers",
        }
    except Exception as error:
        st.error(f"Gagal menghitung Top 5 influencer IndiBiz: {error}")
        return pd.DataFrame(columns=columns), {
            "is_real": False,
            "source_name": "Fallback SNA IndiBiz belum dapat dihitung",
            "actual_rows": 0,
            "content_authors": 0,
            "ranking_method": "55% degree centrality + 45% followers",
        }


@st.cache_data(show_spinner=False, persist="disk", max_entries=12)
def _build_influencer_data(layanan: str) -> tuple[pd.DataFrame, dict[str, Any]]:
    """Pilih influencer layanan dengan aturan data yang sesuai konteksnya."""
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
        if content_stats.empty:
            return pd.DataFrame(columns=empty_columns), {
                "is_real": False,
                "source_name": get_sentiment_source_name(layanan),
                "actual_rows": 0,
                "content_authors": 0,
            }

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

        pool = network_pool.merge(
            content_stats,
            on=["username_key", "platform"],
            how="inner",
            suffixes=("_network", "_content"),
        )
        if not pool.empty:
            pool["username"] = pool["username_content"].fillna(
                pool["username_network"]
            )
            pool["followers"] = pool[["followers_network", "followers_content"]].max(axis=1)
            pool = pool.drop(
                columns=[
                    "username_network", "username_content",
                    "followers_network", "followers_content",
                ],
                errors="ignore",
            )

        pool = pool[
            pd.to_numeric(
                pool["relevant_content_count"], errors="coerce"
            ).fillna(0).gt(0)
        ].copy()
        pool = pool.drop_duplicates(
            subset=["username_key", "platform"], keep="first"
        )

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
            ).head(3)
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
            ["recommendation_score", "degree_centrality", "followers"],
            ascending=[False, False, False],
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

    work = frame.copy()
    work["_username_key"] = work[username_column].map(_username_lookup_key)
    work["_content_clean"] = work[content_column].map(_clean_content_text)
    work = work[
        work["_username_key"].isin(username_keys)
        & work["_content_clean"].str.len().ge(8)
    ].copy()
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


@st.cache_data(show_spinner=False, persist="disk", max_entries=12)
def _build_influencer_content_catalog(
    layanan: str,
    usernames: tuple[str, ...],
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
        sentiment_df = load_influencer_content_data(layanan).copy()
        sentiment_items = _collect_content_items(
            sentiment_df,
            username_column="username",
            content_column="content",
            username_keys=username_keys,
            source_label=get_sentiment_source_name(layanan),
            layanan=layanan,
        )
        for key, items in sentiment_items.items():
            catalog[key]["actual_items"].extend(items)
    except Exception:
        pass

    try:
        sna_df = _filter_sna_by_service(load_sna_data(layanan).copy(), layanan)
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
                <span class="rec-platform-badge">
                    {escape(meta['ikon'])} {escape(meta['label'])}
                </span>
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
            <div
                class="rec-content-preview"
                style="position:relative !important; top:-12px !important; margin-bottom:-12px !important; z-index:1;"
            >
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
    selection_key = f"{layanan}|{username}"
    is_selected = (
        str(st.session_state.get("rec_selected_influencer", ""))
        == selection_key
    )
    button_label = "Tutup Detail" if is_selected else "Lihat Detail"

    if st.button(
        button_label,
        key=f"rec_detail_{_safe_key(layanan)}_{_safe_key(username)}",
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
    """Tampilkan influencer dengan tata letak yang sesuai untuk tiap layanan."""
    if influencers is None or influencers.empty:
        _render_influencer_empty_state(layanan, influencer_meta)
        return

    top_topics = (
        topic_summary.sort_values("jumlah_komentar", ascending=False)["topik_singkat"]
        .astype(str)
        .tolist()
    )
    usernames = tuple(influencers["username"].astype(str).tolist())
    content_catalog = _build_influencer_content_catalog(layanan, usernames)

    selected_state = str(st.session_state.get("rec_selected_influencer", ""))
    if selected_state and not selected_state.startswith(f"{layanan}|"):
        st.session_state["rec_selected_influencer"] = ""

    if layanan == "IndiBiz":
        ranked = influencers.sort_values(
            ["recommendation_rank", "recommendation_score"],
            ascending=[True, False],
        ).head(5).reset_index(drop=True)

        # Detail baris pertama dirender langsung setelah tiga kartu pertama.
        # Posisi ini menjaga panel tetap selebar halaman dan dekat dengan
        # tombol yang baru saja diklik pengguna.
        first_row_detail: dict[str, Any] | None = None
        first_row = st.columns(3, gap="medium")
        for slot, column in enumerate(first_row):
            if slot >= len(ranked):
                break
            with column:
                detail_payload = _render_influencer_entry(
                    layanan, ranked.iloc[slot], slot, top_topics, content_catalog
                )
                if detail_payload is not None:
                    first_row_detail = detail_payload

        if first_row_detail is not None:
            _render_influencer_detail_inline(**first_row_detail)

        # Detail baris kedua dirender langsung setelah dua kartu berikutnya.
        if len(ranked) > 3:
            second_row_detail: dict[str, Any] | None = None
            second_row = st.columns([0.5, 1, 1, 0.5], gap="medium")
            for offset, column in enumerate(second_row[1:3], start=3):
                if offset >= len(ranked):
                    break
                with column:
                    detail_payload = _render_influencer_entry(
                        layanan, ranked.iloc[offset], offset, top_topics, content_catalog
                    )
                    if detail_payload is not None:
                        second_row_detail = detail_payload

            if second_row_detail is not None:
                _render_influencer_detail_inline(**second_row_detail)
        return

    for platform in PLATFORM_ORDER:
        platform_rows = (
            influencers[influencers["platform"].eq(platform)]
            .sort_values("recommendation_score", ascending=False)
            .head(3)
            .reset_index(drop=True)
        )
        columns = st.columns(3, gap="medium")
        selected_detail: dict[str, Any] | None = None

        for slot, column in enumerate(columns):
            with column:
                if slot >= len(platform_rows):
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
                    platform_rows.iloc[slot],
                    slot,
                    top_topics,
                    content_catalog,
                )
                if detail_payload is not None:
                    selected_detail = detail_payload

        # Detail tiap platform dirender setelah kolom kartu agar melebar penuh.
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


def _render_topic_strategies(
    layanan: str,
    topic_summary: pd.DataFrame,
    score_matrix: pd.DataFrame,
) -> None:
    """Tampilkan lima expander strategi dengan tampilan playbook yang lebih rapi."""
    for topic_index, (_, row) in enumerate(topic_summary.iterrows(), start=1):
        topic_key = str(row["key"])
        topic_name = str(row["topik"])
        sentiment = SENTIMENT_LABELS.get(
            str(row.get("sentimen_dominan", "neutral")),
            "Netral",
        )
        visual = _topic_visual_meta(topic_key)
        title = (
            f"{visual['icon']} {topic_index:02d} · {topic_name} · "
            f"{_format_number(int(row['jumlah_komentar']))} komentar · {sentiment}"
        )
        with st.expander(title, expanded=(topic_index == 1)):
            _render_topic_summary(row)

            examples = _content_examples(layanan, topic_key)
            st.markdown(
                f"""
                <div class="rec-copy-header" style="--topic-color:{visual['color']};--topic-soft:{visual['soft']};">
                    <div>
                        <span>Konten siap salin</span>
                        <strong>Gunakan format sesuai karakter tiap platform</strong>
                    </div>
                    <em>{escape(layanan)}</em>
                </div>
                """,
                unsafe_allow_html=True,
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
                    # Konten dipecah ke beberapa baris agar mudah dibaca tanpa scroll horizontal.
                    st.code(_wrap_content_for_display(examples[platform]), language=None)

            recommended = _top_influencers_for_topic(
                score_matrix,
                topic_key,
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
                            <b>{platform_icon}</b>{platform_label}
                        </span>
                    </div>
                    <div class="rec-rank-score">{score}<em>/10</em></div>
                </article>
                """
            ).strip()
        )

    # Memakai components.html agar HTML kartu benar-benar dirender sebagai UI,
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
                    font-size: 10px;
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
                    font-size: 10px;
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
                    font-size: 11px;
                    font-weight: 800;
                    letter-spacing: 0;
                }}
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

    components.html(rank_html, height=112, scrolling=False)


def _render_matrix_table(filtered_matrix: pd.DataFrame) -> None:
    """Tampilkan tabel skor dengan pencarian, filter, sorting, dan detail akun."""
    if filtered_matrix.empty:
        return

    topic_keys = [str(item["key"]) for item in TOPIC_CONFIG]
    rename_map = {str(item["key"]): str(item["singkat"]) for item in TOPIC_CONFIG}
    topic_labels = [str(item["singkat"]) for item in TOPIC_CONFIG]

    table = filtered_matrix[["username", "platform", *topic_keys]].copy()
    table["platform"] = table["platform"].map(
        lambda item: PLATFORM_META.get(str(item), PLATFORM_META["twitter"])["label"]
    )
    table = table.rename(columns={"username": "Influencer", "platform": "Platform", **rename_map})

    for column in topic_labels:
        table[column] = pd.to_numeric(table[column], errors="coerce").fillna(0).astype(int)
    table["Rata-rata"] = table[topic_labels].mean(axis=1).round(1)
    table = table[["Influencer", "Platform", "Rata-rata", *topic_labels]]

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
        sort_options = ["Rata-rata", *topic_labels, "Influencer", "Platform"]
        # Jumlah baris tabel bisa kecil pada layanan tertentu (misalnya hanya 1-5 kandidat).
        # Streamlit tidak mengizinkan slider ketika min_value sama dengan max_value,
        # sehingga kontrol jumlah baris dibuat adaptif agar halaman tidak gagal tampil.
        available_row_count = int(len(table))
        limit_max = min(50, available_row_count)
        default_limit = min(15, limit_max) if limit_max > 0 else 0

        # Form dipakai agar perubahan filter baru diterapkan setelah tombol diklik.
        with st.form("rec_matrix_table_filter_form", border=False):
            filter_col, platform_col, sort_col, order_col, apply_col = st.columns(
                [1.25, 1.10, 1.00, .78, .88],
                gap="medium",
            )
            with filter_col:
                keyword = st.text_input(
                    "Cari influencer",
                    value="",
                    placeholder="Contoh: ferindra, detikcom",
                    key="rec_matrix_table_keyword",
                )
            with platform_col:
                selected_platforms = st.multiselect(
                    "Filter platform",
                    options=platform_options,
                    default=platform_options,
                    key="rec_matrix_table_platforms",
                )
            with sort_col:
                sort_by = st.selectbox(
                    "Urutkan berdasarkan",
                    options=sort_options,
                    index=0,
                    key="rec_matrix_table_sort_by",
                )
            with order_col:
                descending = st.toggle(
                    "Tertinggi dulu",
                    value=True,
                    key="rec_matrix_table_descending",
                )
            with apply_col:
                st.markdown("<div style='height: 31px;'></div>", unsafe_allow_html=True)
                table_filter_submitted = st.form_submit_button(
                    "Terapkan Filter",
                    use_container_width=True,
                    type="primary",
                    on_click=_show_matrix_table_filter_loading,
                )

            if available_row_count > 5:
                row_limit = st.slider(
                    "Jumlah baris yang ditampilkan",
                    min_value=5,
                    max_value=limit_max,
                    value=default_limit,
                    step=1,
                    key="rec_matrix_table_limit",
                )
            else:
                row_limit = max(available_row_count, 0)
                st.markdown(
                    f"""
                    <div class="rec-matrix-table-fixed-limit">
                        <span>Jumlah baris yang ditampilkan</span>
                        <strong>{row_limit}</strong>
                        <small>Semua kandidat tersedia langsung ditampilkan, jadi slider tidak diperlukan.</small>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )

        if table_filter_submitted:
            st.toast("Filter tabel berhasil diterapkan.", icon="✅")

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

        def _score_style(value: Any) -> str:
            try:
                score = float(value)
            except (TypeError, ValueError):
                return ""
            if score >= 9:
                return (
                    "background: linear-gradient(90deg, rgba(53,217,139,.24), rgba(53,217,139,.06)); "
                    "color: #FFFFFF; font-weight: 900; border-left: 3px solid #35D98B;"
                )
            if score >= 7:
                return (
                    "background: linear-gradient(90deg, rgba(255,152,0,.22), rgba(255,152,0,.05)); "
                    "color: #FFFFFF; font-weight: 850; border-left: 3px solid #FF9800;"
                )
            return (
                "background: linear-gradient(90deg, rgba(229,57,53,.20), rgba(229,57,53,.05)); "
                "color: #FFFFFF; font-weight: 800; border-left: 3px solid #E53935;"
            )

        styled_table = (
            display_table.style
            .format({"Rata-rata": "{:.1f}"})
            .map(_score_style, subset=["Rata-rata", *topic_labels])
            .set_properties(
                subset=["Influencer", "Platform"],
                **{
                    "color": "#FFFFFF",
                    "font-weight": "850",
                    "background-color": "rgba(255,255,255,.015)",
                },
            )
            .set_table_styles(
                [
                    {
                        "selector": "th",
                        "props": [
                            ("background", "linear-gradient(135deg, #1D2230, #151821)"),
                            ("color", "#DDE6F3"),
                            ("font-weight", "900"),
                            ("border-color", "rgba(29,161,242,.22)"),
                        ],
                    },
                    {
                        "selector": "td",
                        "props": [
                            ("border-color", "rgba(255,255,255,.07)"),
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
                    <span>{escape(str(selected_row['Platform']))}</span>
                </div>
                <div class="rec-matrix-table-score-pills">{''.join(score_pills)}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )


def _build_heatmap_figure(
    score_matrix: pd.DataFrame,
    focus_topic_key: str | None = None,
) -> go.Figure:
    """Bangun heatmap kesesuaian influencer × topik dengan Plotly."""
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


def _render_interactive_matrix(score_matrix: pd.DataFrame, layanan: str) -> None:
    """Render matriks dengan kontrol interaktif Streamlit."""
    try:
        _render_matrix_intro(layanan)
        if score_matrix is None or score_matrix.empty:
            _render_matrix_unavailable_state(layanan)
            return

        topic_label_to_key = {str(item["singkat"]): str(item["key"]) for item in TOPIC_CONFIG}
        platform_label_to_key = _matrix_platform_options()

        # Kontrol matriks dibungkus dalam form agar halaman tidak langsung reload
        # setiap kali pengguna baru memilih satu filter. Hasil baru diterapkan
        # setelah tombol "Terapkan Filter" diklik.
        with st.form(key=f"rec_matrix_filter_form_{_safe_key(layanan)}", border=False):
            control_1, control_2, control_3, control_4 = st.columns(
                [1.15, 1.25, 1.0, 0.78],
                gap="medium",
            )
            with control_1:
                selected_topic_label = st.selectbox(
                    "Fokus topik",
                    options=list(topic_label_to_key.keys()),
                    index=0,
                    key=f"rec_matrix_topic_{_safe_key(layanan)}",
                    help="Kolom ini dipakai untuk mengurutkan influencer dari skor tertinggi.",
                )
            with control_2:
                selected_platform_labels = st.multiselect(
                    "Filter platform",
                    options=list(platform_label_to_key.keys()),
                    default=list(platform_label_to_key.keys()),
                    key=f"rec_matrix_platform_{_safe_key(layanan)}",
                    help="Kosongkan semua pilihan untuk menampilkan semua platform.",
                )
            with control_3:
                min_score = st.slider(
                    "Skor minimum",
                    min_value=1,
                    max_value=10,
                    value=1,
                    step=1,
                    key=f"rec_matrix_min_score_{_safe_key(layanan)}",
                    help="Naikkan nilai ini untuk menyaring hanya influencer dengan kecocokan tinggi.",
                )
            with control_4:
                st.markdown("<div style='height: 31px;'></div>", unsafe_allow_html=True)
                filter_submitted = st.form_submit_button(
                    "Terapkan Filter",
                    use_container_width=True,
                    type="primary",
                    on_click=_show_matrix_filter_loading,
                    args=(layanan,),
                )

        selected_topic_key = topic_label_to_key[selected_topic_label]
        selected_platforms = [
            platform_label_to_key[label]
            for label in selected_platform_labels
            if label in platform_label_to_key
        ]
        if not selected_platforms:
            selected_platforms = list(PLATFORM_ORDER)

        if filter_submitted:
            st.toast("Filter matriks berhasil diterapkan.", icon="✅")

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
    """Tampilkan ringkasan strategis dalam panel visual interaktif dan berwarna.

    Bagian ini sengaja dirender melalui components.html supaya seluruh elemen HTML,
    animasi, dan dekorasi card tampil sebagai UI, bukan sebagai teks kode.
    """
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
    <html>
    <head>
        <meta charset="utf-8" />
        <style>
            :root {{
                color-scheme: dark;
                --red: #FF3B3B;
                --orange: #FFB020;
                --cyan: #1DA1F2;
                --purple: #B45CFF;
                --green: #22C55E;
                --panel: rgba(13, 13, 13, .88);
                --line: rgba(255, 255, 255, .10);
            }}
            * {{ box-sizing: border-box; }}
            html, body {{
                margin: 0;
                padding: 0;
                background: transparent;
                font-family: 'Inter', 'Plus Jakarta Sans', system-ui, -apple-system, BlinkMacSystemFont, sans-serif;
            }}
            html {{
                overflow: hidden;
            }}
            body {{
                min-height: 100%;
                max-height: 560px;
                overflow-x: hidden;
                overflow-y: auto;
                padding: 0 6px 0 0;
                scrollbar-width: thin;
                scrollbar-color: rgba(255,59,59,.75) rgba(255,255,255,.06);
            }}
            body::-webkit-scrollbar {{
                width: 10px;
            }}
            body::-webkit-scrollbar-track {{
                background: rgba(255,255,255,.055);
                border-radius: 999px;
            }}
            body::-webkit-scrollbar-thumb {{
                background: linear-gradient(180deg, #FF3B3B, #1DA1F2, #22C55E);
                border: 2px solid rgba(8,10,16,.88);
                border-radius: 999px;
                box-shadow: 0 0 14px rgba(255,59,59,.28);
            }}
            body::-webkit-scrollbar-thumb:hover {{
                background: linear-gradient(180deg, #FF5B5B, #36B6FF, #34D873);
            }}
            .rec-strategy-showcase {{
                position: relative;
                isolation: isolate;
                width: 100%;
                min-height: 392px;
                padding: 24px;
                overflow: hidden;
                border: 1px solid rgba(255,255,255,.10);
                border-left: 5px solid var(--red);
                border-radius: 24px;
                background:
                    radial-gradient(circle at 10% 12%, rgba(255,59,59,.28), transparent 26%),
                    radial-gradient(circle at 84% 10%, rgba(29,161,242,.22), transparent 30%),
                    radial-gradient(circle at 70% 92%, rgba(180,92,255,.14), transparent 34%),
                    linear-gradient(135deg, rgba(35,14,18,.96), rgba(10,18,25,.96) 46%, rgba(11,11,12,.98));
                box-shadow:
                    0 24px 70px rgba(0,0,0,.42),
                    inset 0 1px 0 rgba(255,255,255,.08),
                    inset 0 -1px 0 rgba(255,255,255,.04);
                animation: strategyPanelIn .62s cubic-bezier(.2,.85,.2,1) both;
            }}
            .rec-strategy-showcase::before {{
                content: "";
                position: absolute;
                inset: -40% -18%;
                z-index: -2;
                background:
                    conic-gradient(from 180deg at 50% 50%, rgba(255,59,59,.18), rgba(255,176,32,.11), rgba(29,161,242,.18), rgba(180,92,255,.15), rgba(255,59,59,.18));
                filter: blur(42px);
                opacity: .72;
                animation: strategyAura 9s linear infinite;
            }}
            .rec-strategy-showcase::after {{
                content: "";
                position: absolute;
                inset: 0;
                z-index: -1;
                background:
                    linear-gradient(115deg, transparent 0%, rgba(255,255,255,.09) 46%, transparent 58%),
                    linear-gradient(90deg, rgba(255,255,255,.035) 1px, transparent 1px),
                    linear-gradient(0deg, rgba(255,255,255,.025) 1px, transparent 1px);
                background-size: 100% 100%, 46px 46px, 46px 46px;
                transform: translateX(-120%);
                opacity: .55;
                animation: strategySweep 6.5s ease-in-out infinite;
            }}
            .rec-orb {{
                position: absolute;
                border-radius: 999px;
                filter: blur(2px);
                opacity: .68;
                pointer-events: none;
            }}
            .rec-orb-1 {{
                width: 145px;
                height: 145px;
                right: 42px;
                top: 34px;
                background: radial-gradient(circle, rgba(29,161,242,.30), transparent 67%);
                animation: strategyFloat 7.5s ease-in-out infinite;
            }}
            .rec-orb-2 {{
                width: 118px;
                height: 118px;
                left: 76px;
                bottom: 28px;
                background: radial-gradient(circle, rgba(255,176,32,.24), transparent 68%);
                animation: strategyFloat 8s ease-in-out infinite reverse;
            }}
            .rec-strategy-top {{
                position: relative;
                display: flex;
                align-items: center;
                justify-content: space-between;
                gap: 16px;
                margin-bottom: 18px;
                padding: 14px 16px;
                border: 1px solid rgba(255,255,255,.10);
                border-radius: 18px;
                background: rgba(255,255,255,.045);
                backdrop-filter: blur(10px);
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
                width: 44px;
                height: 44px;
                border-radius: 15px;
                background: linear-gradient(135deg, #FF3B3B, #FFB020);
                box-shadow: 0 0 28px rgba(255,59,59,.32);
                color: #fff;
                font-size: 20px;
                animation: strategyPulse 2.6s ease-in-out infinite;
            }}
            .rec-strategy-heading span {{
                display: block;
                color: rgba(255,255,255,.55);
                font-size: 10px;
                font-weight: 900;
                letter-spacing: .13em;
                text-transform: uppercase;
            }}
            .rec-strategy-heading strong {{
                display: block;
                margin-top: 2px;
                color: #fff;
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
                color: #fff;
                font-size: 11px;
                font-weight: 900;
                border: 1px solid rgba(255,255,255,.11);
                box-shadow: inset 0 1px 0 rgba(255,255,255,.09);
                white-space: nowrap;
            }}
            .rec-badge.red {{ background: rgba(255,59,59,.18); border-color: rgba(255,59,59,.38); }}
            .rec-badge.blue {{ background: rgba(29,161,242,.16); border-color: rgba(29,161,242,.36); }}
            .rec-badge.green {{ background: rgba(34,197,94,.14); border-color: rgba(34,197,94,.34); }}
            .rec-strategy-list {{
                display: grid;
                grid-template-columns: repeat(3, minmax(0, 1fr));
                gap: 14px;
                position: relative;
            }}
            .rec-strategy-item {{
                position: relative;
                min-height: 190px;
                padding: 18px 17px 17px;
                overflow: hidden;
                border: 1px solid rgba(255,255,255,.10);
                border-radius: 20px;
                background: linear-gradient(145deg, rgba(255,255,255,.075), rgba(255,255,255,.025));
                box-shadow: 0 18px 40px rgba(0,0,0,.30), inset 0 1px 0 rgba(255,255,255,.08);
                animation: strategyCardIn .58s cubic-bezier(.2,.85,.2,1) both;
                transition: transform .24s ease, border-color .24s ease, box-shadow .24s ease;
            }}
            .rec-strategy-item:hover {{
                transform: translateY(-7px);
                border-color: var(--tone);
                box-shadow: 0 26px 54px rgba(0,0,0,.38), 0 0 28px color-mix(in srgb, var(--tone) 24%, transparent);
            }}
            .rec-strategy-item::before {{
                content: "";
                position: absolute;
                inset: 0;
                background:
                    radial-gradient(circle at 78% 20%, color-mix(in srgb, var(--tone) 28%, transparent), transparent 35%),
                    linear-gradient(135deg, color-mix(in srgb, var(--tone) 13%, transparent), transparent 58%);
                opacity: .95;
                z-index: 0;
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
            .tone-content {{ --tone: #FF3B3B; }}
            .tone-creator {{ --tone: #1DA1F2; }}
            .tone-response {{ --tone: #22C55E; }}
            .rec-strategy-item-1 {{ animation-delay: .08s; }}
            .rec-strategy-item-2 {{ animation-delay: .18s; }}
            .rec-strategy-item-3 {{ animation-delay: .28s; }}
            .rec-strategy-number-wrap {{
                position: relative;
                z-index: 1;
                display: flex;
                align-items: center;
                justify-content: space-between;
                margin-bottom: 18px;
            }}
            .rec-strategy-icon {{
                display: grid;
                place-items: center;
                width: 42px;
                height: 42px;
                border-radius: 14px;
                color: #fff;
                background: color-mix(in srgb, var(--tone) 22%, rgba(255,255,255,.07));
                border: 1px solid color-mix(in srgb, var(--tone) 42%, rgba(255,255,255,.10));
                box-shadow: 0 0 24px color-mix(in srgb, var(--tone) 24%, transparent);
                font-size: 18px;
                font-weight: 950;
            }}
            .rec-strategy-number {{
                display: grid;
                place-items: center;
                min-width: 36px;
                height: 36px;
                padding: 0 10px;
                border-radius: 999px;
                color: #fff;
                background: color-mix(in srgb, var(--tone) 68%, #111111);
                border: 1px solid rgba(255,255,255,.14);
                box-shadow: 0 0 18px color-mix(in srgb, var(--tone) 28%, transparent);
                font-family: 'Plus Jakarta Sans', 'Inter', sans-serif;
                font-size: 13px;
                font-weight: 950;
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
                color: #fff;
                background: color-mix(in srgb, var(--tone) 15%, rgba(255,255,255,.05));
                border: 1px solid color-mix(in srgb, var(--tone) 30%, rgba(255,255,255,.08));
                font-size: 10px;
                font-weight: 950;
                letter-spacing: .09em;
                text-transform: uppercase;
            }}
            .rec-strategy-text {{
                color: rgba(255,255,255,.82);
                font-size: 14px;
                font-weight: 720;
                line-height: 1.58;
                text-wrap: pretty;
            }}
            .rec-strategy-text strong {{
                color: #fff;
                font-weight: 950;
                text-shadow: 0 0 18px color-mix(in srgb, var(--tone) 24%, transparent);
            }}
            .rec-strategy-footer {{
                position: relative;
                display: flex;
                align-items: center;
                justify-content: space-between;
                gap: 14px;
                margin-top: 14px;
                padding: 12px 14px;
                border: 1px solid rgba(255,255,255,.09);
                border-radius: 16px;
                background: rgba(255,255,255,.04);
                color: rgba(255,255,255,.70);
                font-size: 12px;
                font-weight: 750;
            }}
            .rec-strategy-footer strong {{ color: #fff; }}
            .rec-footer-line {{
                flex: 1 1 auto;
                height: 2px;
                border-radius: 999px;
                background: linear-gradient(90deg, #FF3B3B, #FFB020, #1DA1F2, #22C55E);
                animation: strategyLine 3.2s ease-in-out infinite;
            }}
            @keyframes strategyPanelIn {{
                from {{ opacity: 0; transform: translateY(18px) scale(.985); filter: blur(5px); }}
                to {{ opacity: 1; transform: translateY(0) scale(1); filter: blur(0); }}
            }}
            @keyframes strategyCardIn {{
                from {{ opacity: 0; transform: translateY(20px); }}
                to {{ opacity: 1; transform: translateY(0); }}
            }}
            @keyframes strategySweep {{
                0%, 58% {{ transform: translateX(-120%); }}
                82%, 100% {{ transform: translateX(120%); }}
            }}
            @keyframes strategyAura {{
                to {{ transform: rotate(360deg); }}
            }}
            @keyframes strategyFloat {{
                0%, 100% {{ transform: translate3d(0,0,0) scale(1); }}
                50% {{ transform: translate3d(-16px, 14px, 0) scale(1.07); }}
            }}
            @keyframes strategyPulse {{
                0%, 100% {{ transform: scale(1); box-shadow: 0 0 24px rgba(255,59,59,.28); }}
                50% {{ transform: scale(1.06); box-shadow: 0 0 34px rgba(255,176,32,.36); }}
            }}
            @keyframes strategyLine {{
                0%, 100% {{ opacity: .55; filter: saturate(1); }}
                50% {{ opacity: 1; filter: saturate(1.35); }}
            }}
            @media (max-width: 980px) {{
                .rec-strategy-showcase {{ min-height: 0; padding: 18px; }}
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
                .rec-badge {{ padding: 7px 9px; font-size: 10px; }}
                .rec-strategy-text {{ font-size: 13px; line-height: 1.52; }}
            }}
            @media (prefers-reduced-motion: reduce) {{
                .rec-strategy-showcase,
                .rec-strategy-showcase::before,
                .rec-strategy-showcase::after,
                .rec-strategy-item,
                .rec-strategy-heading-icon,
                .rec-orb,
                .rec-footer-line {{ animation: none !important; }}
                .rec-strategy-item:hover {{ transform: none; }}
            }}
        </style>
    </head>
    <body>
        <section class="rec-strategy-showcase" aria-label="Ringkasan strategi rekomendasi">
            <div class="rec-orb rec-orb-1"></div>
            <div class="rec-orb rec-orb-2"></div>

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
    components.html(html, height=560, scrolling=True)


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

    st.markdown(
        dedent(
            f"""
            <section class="rec-ai-shell">
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
                st.cache_data.clear()
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
        except Exception as error:
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


def _filter_topic_options() -> list[str]:
    """Sediakan topik kanonik agar form tidak perlu rerun saat layanan diganti."""
    try:
        values = [
            str(item.get("nama", "")).strip()
            for item in TOPIC_CONFIG
            if str(item.get("nama", "")).strip()
        ]
        if values:
            return list(dict.fromkeys(values))
    except Exception:
        pass
    return [RECOMMENDATION_FILTER_DEFAULTS["topik"]]


def _normalise_recommendation_filter_state() -> None:
    """Siapkan draft dan filter aktif sebelum widget form dibuat."""
    service_options = list(ACTIVE_LAYANAN_OPTIONS)
    platform_options = ["Instagram", "TikTok", "Twitter"]
    topic_options = _filter_topic_options()

    if st.session_state.pop(RECOMMENDATION_FILTER_RESET_PENDING_KEY, False):
        for field, default_value in RECOMMENDATION_FILTER_DEFAULTS.items():
            st.session_state[RECOMMENDATION_FILTER_DRAFT_KEYS[field]] = default_value
            st.session_state[RECOMMENDATION_FILTER_ACTIVE_KEYS[field]] = default_value
        st.session_state["recommendation_service_selector"] = RECOMMENDATION_FILTER_DEFAULTS["layanan"]
        st.session_state["recommendation_ai_platform_selector"] = RECOMMENDATION_FILTER_DEFAULTS["platform"]
        st.session_state["recommendation_ai_topic_selector"] = RECOMMENDATION_FILTER_DEFAULTS["topik"]
        st.session_state.pop("recommendation_ai_payload", None)

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
            RECOMMENDATION_FILTER_DEFAULTS["topik"],
        ),
    }
    option_map = {
        "layanan": service_options,
        "platform": platform_options,
        "topik": topic_options,
    }

    for field, options in option_map.items():
        active_key = RECOMMENDATION_FILTER_ACTIVE_KEYS[field]
        draft_key = RECOMMENDATION_FILTER_DRAFT_KEYS[field]
        default_value = RECOMMENDATION_FILTER_DEFAULTS[field]
        candidate = str(legacy_values[field]).strip()
        if candidate not in options:
            candidate = default_value if default_value in options else options[0]

        if st.session_state.get(active_key) not in options:
            st.session_state[active_key] = candidate
        if st.session_state.get(draft_key) not in options:
            st.session_state[draft_key] = st.session_state[active_key]


def _render_recommendation_filter_form() -> tuple[str, str, str]:
    """Render tiga filter dalam form dan terapkan nilai hanya melalui tombol."""
    _normalise_recommendation_filter_state()
    topic_options = _filter_topic_options()

    with st.form("recommendation_main_filter_form", clear_on_submit=False):
        filter_service_col, filter_platform_col, filter_topic_col = st.columns(3, gap="medium")
        with filter_service_col:
            st.selectbox(
                "Pilih Layanan",
                options=ACTIVE_LAYANAN_OPTIONS,
                key=RECOMMENDATION_FILTER_DRAFT_KEYS["layanan"],
                help="Pilihan belum mengubah analisis sampai tombol Terapkan Filter ditekan.",
            )

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
                key=RECOMMENDATION_FILTER_DRAFT_KEYS["topik"],
                help="Topik baru dipakai setelah tombol Terapkan Filter ditekan.",
            )

        apply_col, reset_col, spacer_col = st.columns([1.35, 1.35, 4.3], gap="small")
        with apply_col:
            apply_clicked = st.form_submit_button(
                "Terapkan Filter",
                type="primary",
                use_container_width=True,
            )
        with reset_col:
            reset_clicked = st.form_submit_button(
                "Reset Filter",
                type="secondary",
                use_container_width=True,
            )
        with spacer_col:
            st.empty()

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
        for field in ("layanan", "platform", "topik"):
            draft_value = st.session_state[RECOMMENDATION_FILTER_DRAFT_KEYS[field]]
            st.session_state[RECOMMENDATION_FILTER_ACTIVE_KEYS[field]] = draft_value

        # Sinkronisasi key lama menjaga kompatibilitas dengan hasil AI Fase 10-12.
        st.session_state["recommendation_service_selector"] = st.session_state[
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
# ENTRY POINT HALAMAN
# -----------------------------------------------------------------------------


def render_recommendation() -> None:
    """Render halaman Rekomendasi Konten & Influencer untuk tiga layanan."""
    action_loading_handle = None

    try:
        loading_label = st.session_state.pop(RECOMMENDATION_ACTION_LOADING_KEY, None)
        if loading_label:
            action_loading_handle = _start_recommendation_loading(str(loading_label))

        st.markdown(RECOMMENDATION_HIDE_NATIVE_LOADING_CSS, unsafe_allow_html=True)
        st.markdown(RECOMMENDATION_CSS, unsafe_allow_html=True)
        st.markdown(PHASE12_AI_CSS, unsafe_allow_html=True)
        st.markdown(RECOMMENDATION_FILTER_FORM_CSS, unsafe_allow_html=True)
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

        # Data berat dan seluruh kartu hanya memakai nilai aktif hasil tombol Terapkan Filter.
        topic_summary, topic_meta = _build_topic_summary(layanan)

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

        _render_section_header(
            "Sentiment Response Framework",
            "Strategi Per Sentimen",
            "Gunakan tiga pola respons berikut sebagai pagar strategis sebelum konten dipublikasikan.",
        )
        _render_sentiment_strategy_cards()

        influencers, influencer_meta = _build_influencer_data(layanan)
        score_matrix = _build_score_matrix(influencers, layanan)

        _render_context_card(layanan, topic_meta, influencer_meta)

        _render_section_header(
            "01 · Recommended Influencers",
            "Influencer yang Direkomendasikan",
            (
                "Akun dipilih dari kombinasi posisi jaringan, jangkauan followers, dan "
                "konten asli yang relevan pada dataset layanan terpilih."
            ),
        )
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

        _render_section_header(
            f"{topic_section_number} · Topic Playbook",
            "Strategi per Topik",
            (
                "Buka setiap topik untuk melihat volume percakapan, sentimen dominan, "
                "tiga contoh konten siap salin, dan influencer yang paling sesuai."
            ),
        )
        _render_topic_strategies(layanan, topic_summary, score_matrix)

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
    except Exception as exc:
        st.error(
            "Halaman rekomendasi tidak dapat ditampilkan. "
            f"Detail kesalahan: {exc}"
        )
        st.info(
            "Periksa keberadaan file data pada folder data/, kemudian muat ulang halaman."
        )
    finally:
        _finish_recommendation_loading(action_loading_handle)

