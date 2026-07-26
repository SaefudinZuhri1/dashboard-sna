"""Panel admin untuk manajemen pengguna dan pemantauan status sistem."""

from __future__ import annotations

import json
import re
from html import escape
from pathlib import Path
from textwrap import dedent

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
import streamlit.components.v1 as components

from utils.access_control import (
    DEFAULT_ROLE,
    ROLE_DATA_ANALYST,
    VALID_ROLES,
    get_role_icon,
    get_role_label,
    normalize_role,
)
from utils.indibiz_config import OUTPUT_FILES as INDIBIZ_OUTPUT_FILES
from utils.audit_logger import (
    audit_dataframe,
    fetch_audit_logs,
    get_audit_filter_options,
    log_activity,
)

from auth.auth_utils import (
    admin_create_user,
    delete_user,
    format_created_at,
    get_all_users,
    get_user_stats,
    update_user_role,
)


PROJECT_ROOT = Path(__file__).resolve().parent.parent
DELETE_TARGET_KEY = "admin_delete_target"
DELETE_SCROLL_PENDING_KEY = "admin_delete_scroll_pending"
FLASH_MESSAGE_KEY = "admin_panel_flash_message"
LOCKED_DEFAULT_USERNAMES = {"admin", "manajemen", "sosmed_officer"}

_DIALOG_DECORATOR = getattr(st, "dialog", None)
if _DIALOG_DECORATOR is None:
    _DIALOG_DECORATOR = st.experimental_dialog

ROLE_DESCRIPTIONS = {
    "management": "Akses Beranda dan Rekomendasi untuk kebutuhan pengambilan keputusan.",
    "data_analyst": "Akses penuh ke seluruh halaman analisis, dataset, dan Admin Panel.",
    "social_media_officer": "Akses Beranda, SNA, Rekomendasi, Profil, dan Tentang.",
}

# Nama file kanonik beserta alternatif file terkompresi yang dipakai proyek.
EXPECTED_DATA_FILES = [
    {
        "label": "Data Sentimen IndiHome",
        "icon": "🏠",
        "canonical": "data/indihome_sentiment.csv",
        "alternatives": [
            "data/indihome_sentiment.csv",
            "data/indihome_sentiment.csv.gz",
        ],
    },
    {
        "label": "Data Sentimen IndiBiz",
        "icon": "🏢",
        "canonical": f"data/{INDIBIZ_OUTPUT_FILES['sentiment_csv']}",
        "alternatives": [
            f"data/{INDIBIZ_OUTPUT_FILES['sentiment_csv']}",
            "data/indibiz_sentiment.csv",
            "data/indibiz_sentiment.csv.gz",
            "data/Indibiz- NovemberDesember 2025.xlsx",
        ],
    },
    {
        "label": "Data SNA IndiBiz",
        "icon": "🕸️",
        "canonical": f"data/{INDIBIZ_OUTPUT_FILES['sna_csv']}",
        "alternatives": [
            f"data/{INDIBIZ_OUTPUT_FILES['sna_csv']}",
            "data/SNA Indibiz.csv",
            "data/SNA IndiBiz.csv",
            "data/sna_data.csv",
        ],
    },
    {
        "label": "Data Sentimen Telkomsel",
        "icon": "📱",
        "canonical": "data/telkomsel_sentiment.csv",
        "alternatives": [
            "data/telkomsel_sentiment.csv",
            "data/telkomsel_sentiment.csv.gz",
        ],
    },
    {
        "label": "Data SNA Gabungan",
        "icon": "🕸️",
        "canonical": "data/sna_data.csv",
        "alternatives": ["data/sna_data.csv"],
    },
]


def _inject_admin_css() -> None:
    """Sisipkan CSS khusus Admin Panel agar konsisten dengan halaman lain."""
    try:
        st.markdown(
            """
            <style>
                @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=Plus+Jakarta+Sans:wght@500;600;700;800&display=swap');

                @keyframes adminHeroGlow {
                    0%, 100% { transform: translate3d(0, 0, 0) scale(1); opacity: .55; }
                    50% { transform: translate3d(-14px, 10px, 0) scale(1.08); opacity: .82; }
                }

                @keyframes adminCardEntry {
                    from { opacity: 0; transform: translateY(10px); }
                    to { opacity: 1; transform: translateY(0); }
                }

                @keyframes adminPulse {
                    0%, 100% { box-shadow: 0 0 0 0 rgba(76, 175, 80, .28); }
                    50% { box-shadow: 0 0 0 8px rgba(76, 175, 80, 0); }
                }

                .admin-v3-hero {
                    animation: adminCardEntry .5s ease both;
                    background:
                        radial-gradient(circle at 12% 18%, rgba(255,255,255,.16), transparent 24%),
                        radial-gradient(circle at 90% 8%, rgba(255,193,7,.22), transparent 22%),
                        linear-gradient(135deg, #8E1017 0%, #C51D25 42%, #E53935 72%, #FF5B57 100%);
                    border: 1px solid rgba(255,255,255,.14);
                    border-radius: 24px;
                    box-shadow: 0 22px 52px rgba(183,28,28,.28), inset 0 1px 0 rgba(255,255,255,.17);
                    color: #FFFFFF;
                    isolation: isolate;
                    margin: .1rem 0 1.35rem;
                    overflow: hidden;
                    padding: clamp(1.45rem, 3vw, 2.35rem);
                    position: relative;
                    transition: transform .28s ease, box-shadow .28s ease, border-color .28s ease;
                }

                .admin-v3-hero:hover {
                    border-color: rgba(255,255,255,.32);
                    box-shadow: 0 28px 68px rgba(229,57,53,.34), inset 0 1px 0 rgba(255,255,255,.22);
                    transform: translateY(-3px);
                }

                .admin-v3-hero::after {
                    animation: adminHeroGlow 8s ease-in-out infinite;
                    background: radial-gradient(circle, rgba(255,255,255,.20), transparent 68%);
                    content: '';
                    height: 260px;
                    pointer-events: none;
                    position: absolute;
                    right: -55px;
                    top: -110px;
                    width: 260px;
                    z-index: -1;
                }

                .admin-v3-hero-top {
                    align-items: flex-start;
                    display: flex;
                    gap: 1rem;
                    justify-content: space-between;
                }

                .admin-v3-hero-icon {
                    align-items: center;
                    background: rgba(255,255,255,.16);
                    border: 1px solid rgba(255,255,255,.24);
                    border-radius: 18px;
                    box-shadow: inset 0 1px 0 rgba(255,255,255,.18);
                    display: inline-flex;
                    flex: 0 0 auto;
                    font-size: 2rem;
                    height: 64px;
                    justify-content: center;
                    width: 64px;
                }

                .admin-v3-hero-copy { flex: 1; min-width: 0; }
                .admin-v3-hero h1 {
                    color: #FFFFFF !important;
                    font-family: 'Plus Jakarta Sans', 'Inter', sans-serif;
                    font-size: clamp(1.65rem, 3vw, 2.15rem);
                    font-weight: 800;
                    letter-spacing: -.035em;
                    line-height: 1.15;
                    margin: 0;
                }
                .admin-v3-hero p {
                    color: rgba(255,255,255,.90) !important;
                    font-family: 'Inter', sans-serif;
                    font-size: .98rem;
                    line-height: 1.65;
                    margin: .65rem 0 0;
                    max-width: 760px;
                }

                .admin-v3-hero-badges {
                    display: flex;
                    flex-wrap: wrap;
                    gap: .5rem;
                    margin-top: 1.15rem;
                }
                .admin-v3-hero-badge {
                    align-items: center;
                    backdrop-filter: blur(8px);
                    background: rgba(18,18,20,.24);
                    border: 1px solid rgba(255,255,255,.22);
                    border-radius: 999px;
                    color: #FFFFFF;
                    display: inline-flex;
                    font-size: 0.75rem /* FIX: minimum 12px agar terbaca di tablet */;
                    font-weight: 700;
                    gap: .35rem;
                    padding: .42rem .72rem;
                }
                .admin-v3-online-dot {
                    animation: adminPulse 2.2s ease-in-out infinite;
                    background: #66BB6A;
                    border-radius: 50%;
                    height: 8px;
                    width: 8px;
                }

                .admin-v3-section-head {
                    align-items: center;
                    animation: adminCardEntry .45s ease both;
                    background: linear-gradient(135deg, rgba(29,161,242,.12), rgba(131,58,180,.08));
                    border: 1px solid rgba(29,161,242,.22);
                    border-radius: 16px;
                    display: flex;
                    gap: .85rem;
                    margin: .25rem 0 1rem;
                    padding: 1rem 1.1rem;
                }
                .admin-v3-section-head.purple {
                    background: linear-gradient(135deg, rgba(131,58,180,.15), rgba(229,57,53,.08));
                    border-color: rgba(171,71,188,.26);
                }
                .admin-v3-section-head.orange {
                    background: linear-gradient(135deg, rgba(255,152,0,.14), rgba(229,57,53,.07));
                    border-color: rgba(255,152,0,.24);
                }
                .admin-v3-section-icon {
                    align-items: center;
                    background: rgba(255,255,255,.07);
                    border: 1px solid rgba(255,255,255,.09);
                    border-radius: 13px;
                    display: inline-flex;
                    flex: 0 0 auto;
                    font-size: 1.45rem;
                    height: 46px;
                    justify-content: center;
                    width: 46px;
                }
                .admin-v3-section-copy h2 {
                    color: var(--app-text) !important;
                    font-family: 'Plus Jakarta Sans', 'Inter', sans-serif;
                    font-size: 1.18rem;
                    font-weight: 800;
                    margin: 0;
                }
                .admin-v3-section-copy p {
                    color: var(--app-muted) !important;
                    font-size: .86rem;
                    line-height: 1.55;
                    margin: .22rem 0 0;
                }

                .admin-v3-mini-stat-grid {
                    display: grid;
                    gap: .8rem;
                    grid-template-columns: repeat(4, minmax(0, 1fr));
                    margin: .45rem 0 1.2rem;
                }
                .admin-v3-mini-stat {
                    animation: adminCardEntry .45s ease both;
                    background: var(--app-card-bg);
                    border: 1px solid var(--app-border);
                    border-radius: 16px;
                    box-shadow: 0 12px 28px rgba(0,0,0,.12);
                    min-height: 122px;
                    overflow: hidden;
                    padding: 1rem 1.05rem;
                    position: relative;
                    transition: transform .24s ease, border-color .24s ease, box-shadow .24s ease;
                }
                .admin-v3-mini-stat:hover {
                    border-color: var(--metric-accent, #E53935);
                    box-shadow: 0 16px 34px rgba(0,0,0,.18);
                    transform: translateY(-4px);
                }
                .admin-v3-mini-stat::before {
                    background: var(--metric-accent, #E53935);
                    content: '';
                    height: 100%;
                    left: 0;
                    position: absolute;
                    top: 0;
                    width: 4px;
                }
                .admin-v3-mini-stat-top {
                    align-items: center;
                    display: flex;
                    justify-content: space-between;
                }
                .admin-v3-mini-stat-icon {
                    align-items: center;
                    background: color-mix(in srgb, var(--metric-accent, #E53935) 15%, transparent);
                    border-radius: 11px;
                    display: inline-flex;
                    font-size: 1.1rem;
                    height: 38px;
                    justify-content: center;
                    width: 38px;
                }
                .admin-v3-mini-stat-value {
                    color: var(--metric-accent, #E53935);
                    font-family: 'Plus Jakarta Sans', 'Inter', sans-serif;
                    font-size: 1.8rem;
                    font-weight: 800;
                    letter-spacing: -.04em;
                    line-height: 1;
                    margin-top: .85rem;
                }
                .admin-v3-mini-stat-label {
                    color: var(--app-muted);
                    font-size: .77rem;
                    font-weight: 600;
                    margin-top: .35rem;
                }

                .admin-v3-toolbar-note {
                    background: rgba(29,161,242,.08);
                    border: 1px solid rgba(29,161,242,.18);
                    border-radius: 12px;
                    color: var(--app-muted);
                    font-size: .78rem;
                    line-height: 1.5;
                    margin: .25rem 0 1rem;
                    padding: .7rem .85rem;
                }

                .admin-v3-user-head {
                    align-items: center;
                    background: linear-gradient(90deg, rgba(229,57,53,.14), rgba(29,161,242,.07));
                    border: 1px solid rgba(229,57,53,.18);
                    border-radius: 13px;
                    display: grid;
                    font-size: .76rem;
                    font-weight: 800;
                    gap: .8rem;
                    grid-template-columns: .45fr 1.4fr 1.15fr 1.85fr .75fr 1.1fr 1.5fr;
                    letter-spacing: .025em;
                    margin: .45rem 0 .7rem;
                    padding: .72rem .9rem;
                    text-transform: uppercase;
                }

                div[data-testid="stVerticalBlockBorderWrapper"] {
                    background: linear-gradient(135deg, rgba(255,255,255,.025), rgba(229,57,53,.025));
                    border-color: var(--app-border) !important;
                    border-radius: 16px !important;
                    box-shadow: 0 8px 20px rgba(0,0,0,.08);
                    transition: transform .22s ease, border-color .22s ease, box-shadow .22s ease;
                }
                div[data-testid="stVerticalBlockBorderWrapper"]:hover {
                    border-color: rgba(229,57,53,.46) !important;
                    box-shadow: 0 14px 30px rgba(0,0,0,.14);
                    transform: translateY(-2px);
                }

                .admin-v3-id-pill,
                .admin-v3-role-pill,
                .admin-v3-status-pill {
                    align-items: center;
                    border-radius: 999px;
                    display: inline-flex;
                    font-size: 0.75rem /* FIX: minimum 12px agar terbaca di tablet */;
                    font-weight: 800;
                    gap: .3rem;
                    justify-content: center;
                    line-height: 1;
                    padding: .38rem .62rem;
                    white-space: nowrap;
                }
                .admin-v3-id-pill { background: rgba(76,175,80,.13); color: #66BB6A; }
                .admin-v3-role-admin { background: rgba(229,57,53,.14); color: #FF6B67; border: 1px solid rgba(229,57,53,.26); }
                .admin-v3-role-user { background: rgba(29,161,242,.13); color: #42A5F5; border: 1px solid rgba(29,161,242,.24); }
                .admin-v3-current-pill { background: rgba(255,193,7,.13); color: #FFC107; border: 1px solid rgba(255,193,7,.24); }

                .admin-v3-user-name {
                    color: var(--app-text);
                    font-family: 'Plus Jakarta Sans', 'Inter', sans-serif;
                    font-size: .9rem;
                    font-weight: 750;
                    line-height: 1.35;
                }
                .admin-v3-user-meta {
                    color: var(--app-muted);
                    font-size: 0.75rem /* FIX: minimum 12px agar terbaca di tablet */;
                    line-height: 1.35;
                    margin-top: .18rem;
                }
                .admin-v3-username {
                    background: rgba(255,255,255,.055);
                    border: 1px solid rgba(255,255,255,.07);
                    border-radius: 9px;
                    color: var(--app-text);
                    display: inline-block;
                    font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
                    font-size: .78rem;
                    max-width: 100%;
                    overflow: hidden;
                    padding: .42rem .55rem;
                    text-overflow: ellipsis;
                    white-space: nowrap;
                }
                .admin-v3-email {
                    color: #42A5F5;
                    font-size: .78rem;
                    overflow-wrap: anywhere;
                }
                .admin-v3-date { color: var(--app-muted); font-size: .76rem; line-height: 1.45; }

                .admin-v3-file-card {
                    background: var(--app-card-bg);
                    border: 1px solid var(--app-border);
                    border-radius: 16px;
                    box-shadow: 0 10px 24px rgba(0,0,0,.10);
                    height: 100%;
                    min-height: 176px;
                    overflow: hidden;
                    padding: 1rem;
                    position: relative;
                    transition: transform .24s ease, border-color .24s ease, box-shadow .24s ease;
                }
                .admin-v3-file-card:hover {
                    border-color: var(--file-accent, #4CAF50);
                    box-shadow: 0 16px 32px rgba(0,0,0,.16);
                    transform: translateY(-4px);
                }
                .admin-v3-file-card::after {
                    background: var(--file-accent, #4CAF50);
                    content: '';
                    height: 3px;
                    left: 0;
                    position: absolute;
                    right: 0;
                    top: 0;
                }
                .admin-v3-file-icon { font-size: 1.45rem; }
                .admin-v3-file-title {
                    color: var(--app-text);
                    font-family: 'Plus Jakarta Sans', 'Inter', sans-serif;
                    font-size: .88rem;
                    font-weight: 800;
                    line-height: 1.4;
                    margin-top: .6rem;
                }
                .admin-v3-file-path {
                    color: var(--app-muted);
                    font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
                    font-size: 0.75rem /* FIX: minimum 12px agar terbaca di tablet */;
                    line-height: 1.45;
                    margin: .45rem 0 .7rem;
                    overflow-wrap: anywhere;
                }
                .admin-v3-file-bottom { align-items: center; display: flex; gap: .5rem; justify-content: space-between; }
                .admin-v3-file-ok { background: rgba(76,175,80,.13); color: #66BB6A; border: 1px solid rgba(76,175,80,.23); }
                .admin-v3-file-missing { background: rgba(244,67,54,.13); color: #EF5350; border: 1px solid rgba(244,67,54,.23); }
                .admin-v3-file-size { color: var(--app-muted); font-size: 0.75rem /* FIX: minimum 12px agar terbaca di tablet */; font-weight: 700; }

                .admin-v3-progress-shell {
                    background: rgba(255,255,255,.06);
                    border-radius: 999px;
                    height: 9px;
                    margin: .8rem 0 .3rem;
                    overflow: hidden;
                }
                .admin-v3-progress-fill {
                    background: linear-gradient(90deg, #4CAF50, #8BC34A);
                    border-radius: inherit;
                    height: 100%;
                    transition: width .4s ease;
                }

                .admin-v3-activity-item {
                    align-items: flex-start;
                    background: var(--app-card-bg);
                    border: 1px solid var(--app-border);
                    border-radius: 14px;
                    display: flex;
                    gap: .85rem;
                    margin-bottom: .65rem;
                    padding: .85rem .95rem;
                    transition: border-color .2s ease, transform .2s ease;
                }
                .admin-v3-activity-item:hover { border-color: rgba(255,152,0,.42); transform: translateX(3px); }
                .admin-v3-activity-icon {
                    align-items: center;
                    background: rgba(255,152,0,.12);
                    border-radius: 11px;
                    display: inline-flex;
                    flex: 0 0 auto;
                    font-size: 1rem;
                    height: 38px;
                    justify-content: center;
                    width: 38px;
                }
                .admin-v3-activity-title { color: var(--app-text); font-size: .82rem; font-weight: 750; line-height: 1.4; }
                .admin-v3-activity-meta { color: var(--app-muted); font-size: 0.75rem /* FIX: minimum 12px agar terbaca di tablet */; line-height: 1.45; margin-top: .18rem; }

                .admin-v3-empty {
                    background: linear-gradient(135deg, rgba(29,161,242,.08), rgba(131,58,180,.06));
                    border: 1px dashed rgba(29,161,242,.30);
                    border-radius: 16px;
                    color: var(--app-muted);
                    padding: 1.25rem;
                    text-align: center;
                }

                div[data-testid="stTabs"] button[role="tab"] {
                    border-radius: 11px 11px 0 0;
                    font-family: 'Plus Jakarta Sans', 'Inter', sans-serif;
                    font-weight: 700;
                    padding-left: 1rem;
                    padding-right: 1rem;
                    transition: background .2s ease, color .2s ease, transform .2s ease;
                }
                div[data-testid="stTabs"] button[role="tab"]:hover {
                    background: rgba(229,57,53,.08);
                    color: #FF625E !important;
                    transform: translateY(-1px);
                }
                div[data-testid="stTabs"] button[role="tab"][aria-selected="true"] {
                    background: linear-gradient(180deg, rgba(229,57,53,.14), rgba(229,57,53,.03));
                    color: #FF625E !important;
                }

                div[data-testid="stExpander"] {
                    background: linear-gradient(135deg, rgba(131,58,180,.07), rgba(229,57,53,.035));
                    border: 1px solid var(--app-border);
                    border-radius: 16px;
                    overflow: hidden;
                }

                @media (max-width: 1100px) {
                    .admin-v3-mini-stat-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); }
                    .admin-v3-user-head { display: none; }
                }
                @keyframes adminV4Aurora {
                    0%, 100% { transform: translate3d(-3%, -2%, 0) rotate(0deg) scale(1); opacity: .62; }
                    50% { transform: translate3d(4%, 3%, 0) rotate(10deg) scale(1.08); opacity: .92; }
                }
                @keyframes adminV4GridDrift {
                    from { background-position: 0 0, 0 0; }
                    to { background-position: 34px 34px, -34px 34px; }
                }
                @keyframes adminV4Orbit {
                    from { transform: rotate(0deg); }
                    to { transform: rotate(360deg); }
                }
                @keyframes adminV4OrbitReverse {
                    from { transform: rotate(360deg); }
                    to { transform: rotate(0deg); }
                }
                @keyframes adminV4CorePulse {
                    0%, 100% { box-shadow: 0 0 0 0 rgba(255,255,255,.16), 0 0 30px rgba(229,57,53,.32); }
                    50% { box-shadow: 0 0 0 12px rgba(255,255,255,0), 0 0 48px rgba(229,57,53,.52); }
                }
                @keyframes adminV4Sweep {
                    0% { transform: translateX(-145%) skewX(-18deg); opacity: 0; }
                    18% { opacity: .34; }
                    100% { transform: translateX(330%) skewX(-18deg); opacity: 0; }
                }
                @keyframes adminV4Bars {
                    0%, 100% { transform: scaleY(.34); opacity: .55; }
                    50% { transform: scaleY(1); opacity: 1; }
                }
                @keyframes adminV4Scan {
                    0% { transform: translateY(-140%); opacity: 0; }
                    15% { opacity: .35; }
                    100% { transform: translateY(440%); opacity: 0; }
                }

                .admin-v3-hero {
                    background:
                        radial-gradient(circle at 18% 12%, rgba(255,255,255,.16), transparent 22%),
                        radial-gradient(circle at 88% 16%, rgba(56,215,255,.20), transparent 25%),
                        linear-gradient(135deg, #4A0B17 0%, #8F101D 33%, #C8202C 67%, #E53935 100%);
                    min-height: 285px;
                    padding-right: clamp(1.4rem, 29vw, 25rem);
                }
                .admin-v3-hero::before {
                    animation: adminV4GridDrift 18s linear infinite;
                    background-image:
                        linear-gradient(rgba(255,255,255,.045) 1px, transparent 1px),
                        linear-gradient(90deg, rgba(255,255,255,.045) 1px, transparent 1px);
                    background-size: 34px 34px;
                    content: '';
                    inset: 0;
                    mask-image: linear-gradient(90deg, rgba(0,0,0,.35), rgba(0,0,0,.06) 62%, transparent);
                    pointer-events: none;
                    position: absolute;
                    z-index: -1;
                }
                .admin-v3-hero-copy { position: relative; z-index: 2; }
                .admin-v3-hero-kicker {
                    color: rgba(255,255,255,.76);
                    font-size: 0.75rem /* FIX: minimum 12px agar terbaca di tablet */;
                    font-weight: 800;
                    letter-spacing: .14em;
                    margin-bottom: .45rem;
                    text-transform: uppercase;
                }
                .admin-v3-hero-orbit {
                    align-items: center;
                    aspect-ratio: 1;
                    display: flex;
                    justify-content: center;
                    pointer-events: none;
                    position: absolute;
                    right: clamp(1.3rem, 4vw, 4rem);
                    top: 50%;
                    transform: translateY(-50%);
                    width: clamp(185px, 21vw, 245px);
                    z-index: 2;
                }
                .admin-v3-orbit-ring {
                    border: 1px solid rgba(255,255,255,.24);
                    border-radius: 50%;
                    inset: 4%;
                    position: absolute;
                }
                .admin-v3-orbit-ring.ring-one { animation: adminV4Orbit 15s linear infinite; }
                .admin-v3-orbit-ring.ring-two {
                    animation: adminV4OrbitReverse 10s linear infinite;
                    border-color: rgba(56,215,255,.34);
                    inset: 20%;
                }
                .admin-v3-orbit-ring::before,
                .admin-v3-orbit-ring::after {
                    background: #FFFFFF;
                    border: 3px solid rgba(229,57,53,.72);
                    border-radius: 50%;
                    box-shadow: 0 0 18px rgba(255,255,255,.50);
                    content: '';
                    height: 12px;
                    position: absolute;
                    width: 12px;
                }
                .admin-v3-orbit-ring::before { left: 8%; top: 20%; }
                .admin-v3-orbit-ring::after { bottom: 12%; right: 15%; }
                .admin-v3-orbit-core {
                    align-items: center;
                    animation: adminV4CorePulse 2.8s ease-in-out infinite;
                    background: linear-gradient(145deg, rgba(255,255,255,.22), rgba(255,255,255,.08));
                    border: 1px solid rgba(255,255,255,.36);
                    border-radius: 50%;
                    color: #FFFFFF;
                    display: flex;
                    flex-direction: column;
                    font-family: 'Plus Jakarta Sans', sans-serif;
                    height: 92px;
                    justify-content: center;
                    text-align: center;
                    width: 92px;
                }
                .admin-v3-orbit-core strong { font-size: 1.48rem; line-height: 1; }
                .admin-v3-orbit-core small { font-size: 0.75rem /* FIX: minimum 12px agar terbaca di tablet */; font-weight: 800; letter-spacing: .08em; margin-top: .35rem; text-transform: uppercase; }
                .admin-v3-hero-status-grid {
                    display: grid;
                    gap: .62rem;
                    grid-template-columns: repeat(3, minmax(0,1fr));
                    margin-top: 1.2rem;
                    max-width: 780px;
                }
                .admin-v3-hero-status {
                    background: rgba(9,13,24,.28);
                    border: 1px solid rgba(255,255,255,.17);
                    border-radius: 15px;
                    cursor: default;
                    overflow: hidden;
                    padding: .72rem .78rem;
                    position: relative;
                    transition: transform .22s ease, background .22s ease, border-color .22s ease;
                }
                .admin-v3-hero-status::after {
                    animation: adminV4Sweep 6.5s ease-in-out infinite;
                    background: linear-gradient(90deg, transparent, rgba(255,255,255,.16), transparent);
                    content: '';
                    inset: 0 auto 0 -40%;
                    pointer-events: none;
                    position: absolute;
                    width: 34%;
                }
                .admin-v3-hero-status:hover {
                    background: rgba(9,13,24,.42);
                    border-color: rgba(255,255,255,.34);
                    transform: translateY(-3px);
                }
                .admin-v3-hero-status-label { color: rgba(255,255,255,.68); font-size: 0.75rem /* FIX: minimum 12px agar terbaca di tablet */; font-weight: 800; letter-spacing: .08em; text-transform: uppercase; }
                .admin-v3-hero-status-value { color: #FFFFFF; font-size: .92rem; font-weight: 800; margin-top: .2rem; }

                .admin-v3-section-head {
                    overflow: hidden;
                    position: relative;
                }
                .admin-v3-section-head::after {
                    animation: adminV4Sweep 8s ease-in-out infinite;
                    background: linear-gradient(90deg, transparent, rgba(255,255,255,.10), transparent);
                    content: '';
                    inset: 0 auto 0 -30%;
                    pointer-events: none;
                    position: absolute;
                    width: 24%;
                }
                .admin-v3-section-head:hover { transform: translateY(-2px); border-color: rgba(229,57,53,.42); box-shadow: 0 14px 28px rgba(0,0,0,.12); }
                .admin-v3-section-live {
                    align-items: center;
                    background: rgba(255,255,255,.05);
                    border: 1px solid rgba(255,255,255,.09);
                    border-radius: 999px;
                    color: var(--app-muted);
                    display: inline-flex;
                    font-size: 0.75rem /* FIX: minimum 12px agar terbaca di tablet */;
                    font-weight: 800;
                    gap: .42rem;
                    margin-left: auto;
                    padding: .42rem .72rem;
                    white-space: nowrap;
                }
                .admin-v3-section-live i { animation: adminPulse 2.2s ease-in-out infinite; background:#66BB6A; border-radius:50%; height:7px; width:7px; }

                .admin-v3-mini-stat {
                    cursor: default;
                    isolation: isolate;
                }
                .admin-v3-mini-stat::after {
                    background: radial-gradient(circle, color-mix(in srgb, var(--metric-accent, #E53935) 26%, transparent), transparent 68%);
                    bottom: -56px;
                    content: '';
                    height: 135px;
                    position: absolute;
                    right: -38px;
                    transition: transform .28s ease, opacity .28s ease;
                    width: 135px;
                    z-index: -1;
                }
                .admin-v3-mini-stat:hover::after,
                .admin-v3-mini-stat:focus::after { opacity: 1; transform: scale(1.18); }
                .admin-v3-mini-stat:focus { outline: 2px solid color-mix(in srgb, var(--metric-accent, #E53935) 70%, white); outline-offset: 2px; }
                .admin-v3-mini-stat-kicker { color: var(--app-muted); font-size: 0.75rem /* FIX: minimum 12px agar terbaca di tablet */; font-weight: 800; letter-spacing: .08em; text-transform: uppercase; }
                .admin-v3-mini-eq { align-items:flex-end; display:flex; gap:3px; height:18px; }
                .admin-v3-mini-eq span { animation: adminV4Bars 1.35s ease-in-out infinite; background: var(--metric-accent,#E53935); border-radius:2px; height:100%; transform-origin:bottom; width:4px; }
                .admin-v3-mini-eq span:nth-child(2) { animation-delay:.16s; }
                .admin-v3-mini-eq span:nth-child(3) { animation-delay:.31s; }
                .admin-v3-mini-eq span:nth-child(4) { animation-delay:.47s; }
                .admin-v3-mini-stat-foot { align-items:center; color:var(--app-muted); display:flex; font-size:0.75rem /* FIX: minimum 12px agar terbaca di tablet */; gap:.35rem; margin-top:.62rem; }
                .admin-v3-mini-stat-foot i { background:var(--metric-accent,#E53935); border-radius:50%; height:6px; width:6px; }

                .admin-v3-file-card::before {
                    animation: adminV4Scan 5.6s ease-in-out infinite;
                    background: linear-gradient(180deg, transparent, color-mix(in srgb, var(--file-accent,#4CAF50) 22%, transparent), transparent);
                    content: '';
                    height: 42%;
                    left: 0;
                    pointer-events: none;
                    position: absolute;
                    right: 0;
                    top: 0;
                }
                .admin-v3-file-card:active { transform: translateY(-1px) scale(.992); }
                .admin-v3-activity-item { position: relative; overflow: hidden; }
                .admin-v3-activity-item::after { background:linear-gradient(90deg, transparent, rgba(255,152,0,.10), transparent); content:''; inset:0 auto 0 -40%; position:absolute; transition:transform .55s ease; width:34%; }
                .admin-v3-activity-item:hover::after { transform:translateX(410%); }

                div[data-testid="stTabs"] > div:first-child {
                    background: rgba(255,255,255,.025);
                    border: 1px solid var(--app-border);
                    border-radius: 16px;
                    gap: .35rem;
                    padding: .35rem;
                }
                div[data-testid="stTabs"] button[role="tab"] {
                    border-radius: 12px;
                    min-height: 48px;
                }
                div[data-testid="stTabs"] button[role="tab"][aria-selected="true"] {
                    background: linear-gradient(135deg, rgba(229,57,53,.26), rgba(142,90,247,.18));
                    box-shadow: inset 0 0 0 1px rgba(229,57,53,.26), 0 8px 22px rgba(229,57,53,.08);
                }

                div[data-testid="stTextInput"] input,
                div[data-testid="stSelectbox"] > div > div {
                    border-radius: 14px !important;
                    transition: border-color .2s ease, box-shadow .2s ease, transform .2s ease;
                }
                div[data-testid="stTextInput"] input:hover,
                div[data-testid="stSelectbox"] > div > div:hover {
                    border-color: rgba(229,57,53,.45) !important;
                    box-shadow: 0 0 0 3px rgba(229,57,53,.06);
                }
                div[data-testid="stButton"] button,
                div[data-testid="stFormSubmitButton"] button {
                    border-radius: 13px !important;
                    transition: transform .18s ease, box-shadow .18s ease, filter .18s ease;
                }
                div[data-testid="stButton"] button:hover,
                div[data-testid="stFormSubmitButton"] button:hover {
                    box-shadow: 0 12px 26px rgba(229,57,53,.18);
                    filter: brightness(1.07);
                    transform: translateY(-2px);
                }
                div[data-testid="stButton"] button:active,
                div[data-testid="stFormSubmitButton"] button:active { transform: translateY(0) scale(.985); }
                div[data-testid="stExpander"] details[open] { box-shadow: 0 18px 34px rgba(142,90,247,.08); }
                div[data-testid="stExpander"] summary:hover { background: rgba(142,90,247,.06); }

                @keyframes adminV5UserAura {
                    0%, 100% { opacity: .42; transform: translate3d(0, 0, 0) scale(1); }
                    50% { opacity: .78; transform: translate3d(-8px, 5px, 0) scale(1.08); }
                }
                @keyframes adminV5RowSweep {
                    0% { transform: translateX(-145%) skewX(-18deg); opacity: 0; }
                    20% { opacity: .22; }
                    100% { transform: translateX(380%) skewX(-18deg); opacity: 0; }
                }
                @keyframes adminV5DotPulse {
                    0%, 100% { box-shadow: 0 0 0 0 rgba(102,187,106,.32); }
                    50% { box-shadow: 0 0 0 8px rgba(102,187,106,0); }
                }
                @keyframes adminV5AvatarFloat {
                    0%, 100% { transform: translateY(0) rotate(0deg); }
                    50% { transform: translateY(-3px) rotate(-2deg); }
                }

                .admin-v5-directory-head {
                    align-items: center;
                    background:
                        radial-gradient(circle at 8% 12%, rgba(229,57,53,.16), transparent 26%),
                        radial-gradient(circle at 91% 18%, rgba(56,215,255,.12), transparent 24%),
                        linear-gradient(135deg, rgba(18,20,31,.98), rgba(10,18,34,.96));
                    border: 1px solid rgba(229,57,53,.20);
                    border-radius: 20px;
                    box-shadow: 0 18px 38px rgba(0,0,0,.16);
                    display: flex;
                    gap: 1rem;
                    justify-content: space-between;
                    margin: .4rem 0 1rem;
                    overflow: hidden;
                    padding: 1rem 1.08rem;
                    position: relative;
                }
                .admin-v5-directory-head::after {
                    animation: adminV5RowSweep 8.5s ease-in-out infinite;
                    background: linear-gradient(90deg, transparent, rgba(255,255,255,.10), transparent);
                    content: '';
                    inset: 0 auto 0 -32%;
                    pointer-events: none;
                    position: absolute;
                    width: 24%;
                }
                .admin-v5-directory-copy { align-items: center; display: flex; gap: .85rem; min-width: 0; }
                .admin-v5-directory-icon {
                    align-items: center;
                    animation: adminV5AvatarFloat 3.4s ease-in-out infinite;
                    background: linear-gradient(135deg, rgba(229,57,53,.24), rgba(142,90,247,.18));
                    border: 1px solid rgba(229,57,53,.30);
                    border-radius: 15px;
                    color: #FFFFFF;
                    display: flex;
                    flex: 0 0 auto;
                    font-size: 1.15rem;
                    height: 46px;
                    justify-content: center;
                    width: 46px;
                }
                .admin-v5-directory-title {
                    color: var(--app-text);
                    font-family: 'Plus Jakarta Sans', 'Inter', sans-serif;
                    font-size: 1rem;
                    font-weight: 800;
                    letter-spacing: -.02em;
                }
                .admin-v5-directory-note { color: var(--app-muted); font-size: .77rem; line-height: 1.55; margin-top: .18rem; }
                .admin-v5-role-legend { display: flex; flex-wrap: wrap; gap: .42rem; justify-content: flex-end; }
                .admin-v5-legend-pill {
                    align-items: center;
                    background: rgba(255,255,255,.045);
                    border: 1px solid rgba(255,255,255,.08);
                    border-radius: 999px;
                    color: var(--app-muted);
                    display: inline-flex;
                    font-size: 0.75rem /* FIX: minimum 12px agar terbaca di tablet */;
                    font-weight: 800;
                    gap: .38rem;
                    padding: .42rem .64rem;
                    transition: transform .18s ease, border-color .18s ease, color .18s ease;
                }
                .admin-v5-legend-pill:hover { border-color: var(--legend-accent); color: var(--app-text); transform: translateY(-2px); }
                .admin-v5-legend-pill i { background: var(--legend-accent); border-radius: 50%; height: 7px; width: 7px; }

                .admin-v3-toolbar-note {
                    align-items: center;
                    background: linear-gradient(135deg, rgba(29,161,242,.10), rgba(142,90,247,.06));
                    border-color: rgba(29,161,242,.22);
                    box-shadow: inset 0 1px 0 rgba(255,255,255,.025), 0 10px 22px rgba(0,0,0,.08);
                    display: flex;
                    gap: .55rem;
                    min-height: 52px;
                    overflow: hidden;
                    position: relative;
                }
                .admin-v3-toolbar-note::before {
                    animation: adminV5DotPulse 2.3s ease-in-out infinite;
                    background: #66BB6A;
                    border-radius: 50%;
                    content: '';
                    flex: 0 0 auto;
                    height: 8px;
                    width: 8px;
                }

                .admin-v3-user-head {
                    background: linear-gradient(90deg, rgba(229,57,53,.18), rgba(142,90,247,.10), rgba(29,161,242,.08));
                    border-color: rgba(229,57,53,.28);
                    box-shadow: inset 0 1px 0 rgba(255,255,255,.03);
                    grid-template-columns: .48fr 1.62fr 1.12fr 1.72fr 1.08fr 1.02fr 1.45fr;
                    min-height: 54px;
                    padding: .82rem 1rem;
                }
                .admin-v3-user-head span { align-items: center; display: inline-flex; gap: .3rem; }

                div[data-testid="stVerticalBlockBorderWrapper"]:has(.admin-v5-user-row-marker) {
                    --row-accent: #42A5F5;
                    --row-soft: rgba(29,161,242,.11);
                    background:
                        radial-gradient(circle at 94% 10%, var(--row-soft), transparent 24%),
                        linear-gradient(135deg, rgba(255,255,255,.028), rgba(8,13,24,.20));
                    border-color: rgba(255,255,255,.10) !important;
                    box-shadow: 0 12px 28px rgba(0,0,0,.11), inset 3px 0 0 var(--row-accent);
                    isolation: isolate;
                    overflow: hidden;
                    position: relative;
                }
                div[data-testid="stVerticalBlockBorderWrapper"]:has(.admin-v5-row-analyst) {
                    --row-accent: #FF625E;
                    --row-soft: rgba(229,57,53,.12);
                }
                div[data-testid="stVerticalBlockBorderWrapper"]:has(.admin-v5-row-standard) {
                    --row-accent: #42A5F5;
                    --row-soft: rgba(29,161,242,.11);
                }
                div[data-testid="stVerticalBlockBorderWrapper"]:has(.admin-v5-user-row-marker)::before {
                    animation: adminV5UserAura 5.2s ease-in-out infinite;
                    background: radial-gradient(circle, var(--row-soft, rgba(229,57,53,.12)), transparent 68%);
                    content: '';
                    height: 170px;
                    pointer-events: none;
                    position: absolute;
                    right: -58px;
                    top: -76px;
                    width: 170px;
                    z-index: -1;
                }
                div[data-testid="stVerticalBlockBorderWrapper"]:has(.admin-v5-user-row-marker)::after {
                    animation: adminV5RowSweep 9s ease-in-out infinite;
                    background: linear-gradient(90deg, transparent, rgba(255,255,255,.07), transparent);
                    content: '';
                    inset: 0 auto 0 -28%;
                    pointer-events: none;
                    position: absolute;
                    width: 18%;
                }
                div[data-testid="stVerticalBlockBorderWrapper"]:has(.admin-v5-user-row-marker):hover {
                    border-color: var(--row-accent, rgba(229,57,53,.48)) !important;
                    box-shadow: 0 20px 42px rgba(0,0,0,.18), inset 4px 0 0 var(--row-accent, #E53935);
                    transform: translateY(-3px);
                }
                .admin-v5-user-row-marker { display: none; }
                .admin-v5-name-wrap { align-items: center; display: flex; gap: .72rem; min-width: 0; }
                .admin-v5-avatar {
                    align-items: center;
                    animation: adminV5AvatarFloat 4s ease-in-out infinite;
                    background: linear-gradient(145deg, var(--avatar-start, #E53935), var(--avatar-end, #8E5AF7));
                    border: 1px solid rgba(255,255,255,.16);
                    border-radius: 14px;
                    box-shadow: 0 10px 20px var(--avatar-shadow, rgba(229,57,53,.16));
                    color: #FFFFFF;
                    display: flex;
                    flex: 0 0 auto;
                    font-family: 'Plus Jakarta Sans', sans-serif;
                    font-size: .82rem;
                    font-weight: 800;
                    height: 40px;
                    justify-content: center;
                    text-transform: uppercase;
                    width: 40px;
                }
                .admin-v5-name-text { min-width: 0; }
                .admin-v3-user-name { font-size: .88rem; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
                .admin-v3-user-meta { align-items: center; display: flex; gap: .28rem; }
                .admin-v3-user-meta::before { background: #66BB6A; border-radius: 50%; content: ''; height: 6px; width: 6px; }
                .admin-v3-username {
                    background: linear-gradient(135deg, rgba(255,255,255,.065), rgba(255,255,255,.035));
                    border-color: rgba(255,255,255,.10);
                    transition: border-color .18s ease, transform .18s ease, box-shadow .18s ease;
                }
                .admin-v3-username:hover { border-color: rgba(142,90,247,.36); box-shadow: 0 8px 20px rgba(142,90,247,.08); transform: translateY(-2px); }
                .admin-v3-email {
                    align-items: center;
                    background: rgba(29,161,242,.07);
                    border: 1px solid rgba(29,161,242,.14);
                    border-radius: 10px;
                    display: inline-flex;
                    gap: .38rem;
                    max-width: 100%;
                    overflow: hidden;
                    padding: .43rem .56rem;
                    text-decoration: none;
                    text-overflow: ellipsis;
                    white-space: nowrap;
                }
                .admin-v3-email::before { content: '✉'; font-size: 0.75rem /* FIX: minimum 12px agar terbaca di tablet */; }
                .admin-v3-email:hover { background: rgba(29,161,242,.12); border-color: rgba(29,161,242,.32); color: #79C8FF; }
                .admin-v3-role-pill { min-width: 108px; padding: .48rem .68rem; transition: transform .18s ease, box-shadow .18s ease, filter .18s ease; }
                .admin-v3-role-pill:hover { box-shadow: 0 10px 22px rgba(0,0,0,.12); filter: brightness(1.08); transform: translateY(-2px); }
                .admin-v3-date {
                    align-items: center;
                    background: rgba(255,255,255,.035);
                    border: 1px solid rgba(255,255,255,.07);
                    border-radius: 10px;
                    display: inline-flex;
                    gap: .36rem;
                    padding: .42rem .52rem;
                    white-space: nowrap;
                }
                .admin-v3-date::before { color: #FFB74D; content: '◷'; font-size: .76rem; }

                div[data-testid="stVerticalBlock"]:has(.admin-v5-role-action-marker) div[data-testid="stButton"] button {
                    background: linear-gradient(135deg, #E53935, #8E5AF7) !important;
                    border: 1px solid rgba(255,255,255,.12) !important;
                    box-shadow: 0 10px 22px rgba(229,57,53,.16);
                    color: #FFFFFF !important;
                }
                div[data-testid="stVerticalBlock"]:has(.admin-v5-role-action-marker) div[data-testid="stButton"] button:hover {
                    box-shadow: 0 14px 30px rgba(142,90,247,.26);
                    filter: brightness(1.10);
                }
                div[data-testid="stVerticalBlock"]:has(.admin-v5-delete-action-marker) div[data-testid="stButton"] button {
                    background: linear-gradient(135deg, rgba(244,67,54,.10), rgba(10,13,22,.86)) !important;
                    border: 1px solid rgba(244,67,54,.28) !important;
                    color: #FF8A86 !important;
                }
                div[data-testid="stVerticalBlock"]:has(.admin-v5-delete-action-marker) div[data-testid="stButton"] button:hover {
                    background: linear-gradient(135deg, rgba(244,67,54,.22), rgba(42,12,18,.90)) !important;
                    box-shadow: 0 14px 28px rgba(244,67,54,.18);
                    color: #FFFFFF !important;
                }
                .admin-v5-role-action-marker,
                .admin-v5-delete-action-marker { display: none; }
                div[data-testid="stMarkdownContainer"]:has(.admin-v5-user-row-marker),
                div[data-testid="stMarkdownContainer"]:has(.admin-v5-role-action-marker),
                div[data-testid="stMarkdownContainer"]:has(.admin-v5-delete-action-marker) { display: none; }
                div[data-testid="stVerticalBlock"]:has(.admin-v5-role-action-marker) div[data-testid="stButton"] button:disabled,
                div[data-testid="stVerticalBlock"]:has(.admin-v5-delete-action-marker) div[data-testid="stButton"] button:disabled {
                    background: rgba(255,255,255,.035) !important;
                    border-color: rgba(255,255,255,.08) !important;
                    box-shadow: none !important;
                    color: rgba(255,255,255,.34) !important;
                    filter: none !important;
                    transform: none !important;
                }

                @keyframes adminV6CardReveal {
                    from { opacity: 0; transform: translateY(14px) scale(.988); }
                    to { opacity: 1; transform: translateY(0) scale(1); }
                }
                @keyframes adminV6AccentFlow {
                    0%, 100% { background-position: 0% 50%; }
                    50% { background-position: 100% 50%; }
                }
                @keyframes adminV6StatusPulse {
                    0%, 100% { box-shadow: 0 0 0 0 rgba(102,187,106,.24); }
                    50% { box-shadow: 0 0 0 8px rgba(102,187,106,0); }
                }

                .admin-v6-list-head {
                    align-items: center;
                    background: linear-gradient(135deg, rgba(255,255,255,.045), rgba(255,255,255,.018));
                    border: 1px solid rgba(255,255,255,.09);
                    border-radius: 18px;
                    display: flex;
                    gap: 1rem;
                    justify-content: space-between;
                    margin: 1rem 0 .72rem;
                    padding: .88rem 1rem;
                }
                .admin-v6-list-copy { align-items: center; display: flex; gap: .72rem; min-width: 0; }
                .admin-v6-list-icon {
                    align-items: center;
                    background: linear-gradient(145deg, rgba(229,57,53,.24), rgba(142,90,247,.18));
                    border: 1px solid rgba(229,57,53,.28);
                    border-radius: 13px;
                    color: #FFFFFF;
                    display: flex;
                    flex: 0 0 auto;
                    font-size: 1rem;
                    height: 40px;
                    justify-content: center;
                    width: 40px;
                }
                .admin-v6-list-title { color: #FFFFFF; font-size: .92rem; font-weight: 800; letter-spacing: -.02em; }
                .admin-v6-list-note { color: #8F98AA; font-size: 0.75rem /* FIX: minimum 12px agar terbaca di tablet */; line-height: 1.45; margin-top: .12rem; }
                .admin-v6-count-pill {
                    align-items: center;
                    background: rgba(29,161,242,.09);
                    border: 1px solid rgba(29,161,242,.20);
                    border-radius: 999px;
                    color: #90D3FF;
                    display: inline-flex;
                    flex: 0 0 auto;
                    font-size: 0.75rem /* FIX: minimum 12px agar terbaca di tablet */;
                    font-weight: 800;
                    gap: .42rem;
                    padding: .48rem .72rem;
                }
                .admin-v6-count-pill i {
                    animation: adminV6StatusPulse 2.2s ease-in-out infinite;
                    background: #66BB6A;
                    border-radius: 50%;
                    height: 7px;
                    width: 7px;
                }

                div[data-testid="stVerticalBlockBorderWrapper"]:has(.admin-v6-user-card-marker) {
                    --card-accent: #42A5F5;
                    --card-accent-soft: rgba(66,165,245,.14);
                    animation: adminV6CardReveal .42s ease both;
                    background:
                        radial-gradient(circle at 92% 2%, var(--card-accent-soft), transparent 27%),
                        linear-gradient(145deg, rgba(21,25,36,.98), rgba(9,14,24,.98));
                    border: 1px solid rgba(255,255,255,.09) !important;
                    border-radius: 22px !important;
                    box-shadow: 0 16px 36px rgba(0,0,0,.16), inset 0 1px 0 rgba(255,255,255,.025);
                    margin-bottom: .88rem;
                    overflow: hidden;
                    padding: .18rem .18rem .06rem !important;
                    position: relative;
                    transition: border-color .22s ease, box-shadow .22s ease, transform .22s ease;
                }
                div[data-testid="stVerticalBlockBorderWrapper"]:has(.admin-v6-card-analyst) {
                    --card-accent: #FF625E;
                    --card-accent-soft: rgba(255,98,94,.15);
                }
                div[data-testid="stVerticalBlockBorderWrapper"]:has(.admin-v6-card-management) {
                    --card-accent: #42A5F5;
                    --card-accent-soft: rgba(66,165,245,.14);
                }
                div[data-testid="stVerticalBlockBorderWrapper"]:has(.admin-v6-card-social) {
                    --card-accent: #FFB74D;
                    --card-accent-soft: rgba(255,183,77,.14);
                }
                div[data-testid="stVerticalBlockBorderWrapper"]:has(.admin-v6-user-card-marker)::before {
                    background: linear-gradient(90deg, var(--card-accent), #8E5AF7, #38D7FF, var(--card-accent));
                    background-size: 240% 100%;
                    animation: adminV6AccentFlow 6s ease infinite;
                    content: '';
                    height: 3px;
                    inset: 0 0 auto 0;
                    position: absolute;
                }
                div[data-testid="stVerticalBlockBorderWrapper"]:has(.admin-v6-user-card-marker):hover {
                    border-color: color-mix(in srgb, var(--card-accent) 58%, transparent) !important;
                    box-shadow: 0 24px 50px rgba(0,0,0,.24), 0 0 0 1px var(--card-accent-soft);
                    transform: translateY(-4px);
                }
                .admin-v6-user-card-marker { display: none; }
                div[data-testid="stMarkdownContainer"]:has(.admin-v6-user-card-marker),
                div[data-testid="stMarkdownContainer"]:has(.admin-v6-role-action-marker),
                div[data-testid="stMarkdownContainer"]:has(.admin-v6-delete-action-marker) { display: none; }

                .admin-v6-card-top {
                    align-items: center;
                    display: flex;
                    gap: 1rem;
                    justify-content: space-between;
                    padding: .88rem .92rem .66rem;
                }
                .admin-v6-identity { align-items: center; display: flex; gap: .9rem; min-width: 0; }
                .admin-v6-avatar {
                    align-items: center;
                    background: linear-gradient(145deg, var(--card-accent), #8E5AF7);
                    border: 1px solid rgba(255,255,255,.18);
                    border-radius: 18px;
                    box-shadow: 0 12px 26px var(--card-accent-soft);
                    color: #FFFFFF;
                    display: flex;
                    flex: 0 0 auto;
                    font-family: 'Plus Jakarta Sans', sans-serif;
                    font-size: 1rem;
                    font-weight: 800;
                    height: 54px;
                    justify-content: center;
                    letter-spacing: -.02em;
                    width: 54px;
                }
                .admin-v6-name-wrap { min-width: 0; }
                .admin-v6-name { color: #FFFFFF; font-size: 1rem; font-weight: 800; line-height: 1.2; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
                .admin-v6-handle { color: #9EA8BA; font-size: 0.75rem /* FIX: minimum 12px agar terbaca di tablet */; font-weight: 600; margin-top: .18rem; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
                .admin-v6-account-note {
                    align-items: center;
                    color: #88D69A;
                    display: flex;
                    font-size: 0.75rem /* FIX: minimum 12px agar terbaca di tablet */;
                    font-weight: 700;
                    gap: .34rem;
                    margin-top: .28rem;
                }
                .admin-v6-account-note i { animation: adminV6StatusPulse 2.2s ease-in-out infinite; background:#66BB6A; border-radius:50%; height:6px; width:6px; }
                .admin-v6-access-stack { align-items: flex-end; display: flex; flex-direction: column; gap: .42rem; }
                .admin-v6-role-pill {
                    align-items: center;
                    background: var(--card-accent-soft);
                    border: 1px solid color-mix(in srgb, var(--card-accent) 44%, transparent);
                    border-radius: 999px;
                    color: #FFFFFF;
                    display: inline-flex;
                    font-size: 0.75rem /* FIX: minimum 12px agar terbaca di tablet */;
                    font-weight: 800;
                    gap: .38rem;
                    padding: .48rem .72rem;
                    white-space: nowrap;
                }
                .admin-v6-access-note { color:#747E91; font-size:0.75rem /* FIX: minimum 12px agar terbaca di tablet */; font-weight:700; letter-spacing:.05em; text-transform:uppercase; }

                .admin-v6-meta-grid {
                    display: grid;
                    gap: .62rem;
                    grid-template-columns: .72fr 1.2fr 2.25fr 1.45fr;
                    padding: 0 .92rem .76rem;
                }
                .admin-v6-meta-item {
                    background: rgba(255,255,255,.032);
                    border: 1px solid rgba(255,255,255,.065);
                    border-radius: 14px;
                    min-width: 0;
                    padding: .62rem .7rem;
                    transition: border-color .18s ease, background .18s ease, transform .18s ease;
                }
                .admin-v6-meta-item:hover { background: rgba(255,255,255,.055); border-color: var(--card-accent-soft); transform: translateY(-2px); }
                .admin-v6-meta-label { color:#6F798C; font-size:0.75rem /* FIX: minimum 12px agar terbaca di tablet */; font-weight:800; letter-spacing:.08em; text-transform:uppercase; }
                .admin-v6-meta-value { color:#DDE3EE; font-size:0.75rem /* FIX: minimum 12px agar terbaca di tablet */; font-weight:700; line-height:1.4; margin-top:.18rem; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }
                .admin-v6-card-divider { background: linear-gradient(90deg, transparent, rgba(255,255,255,.08), transparent); height:1px; margin: 0 .92rem .72rem; }
                .admin-v6-action-label { color:#687286; font-size:0.75rem /* FIX: minimum 12px agar terbaca di tablet */; font-weight:800; letter-spacing:.08em; text-transform:uppercase; padding:.3rem 0 0; }
                .admin-v6-role-action-marker,
                .admin-v6-delete-action-marker { display:none; }
                div[data-testid="stVerticalBlock"]:has(.admin-v6-role-action-marker) div[data-testid="stButton"] button,
                div[data-testid="stVerticalBlock"]:has(.admin-v6-delete-action-marker) div[data-testid="stButton"] button {
                    min-height: 43px;
                    font-size: 0.75rem /* FIX: minimum 12px agar terbaca di tablet */;
                    font-weight: 800;
                }
                div[data-testid="stVerticalBlock"]:has(.admin-v6-role-action-marker) div[data-testid="stButton"] button {
                    background: linear-gradient(135deg, var(--card-accent), #8E5AF7) !important;
                    border: 1px solid rgba(255,255,255,.12) !important;
                    box-shadow: 0 10px 24px var(--card-accent-soft);
                    color:#FFFFFF !important;
                }
                div[data-testid="stVerticalBlock"]:has(.admin-v6-delete-action-marker) div[data-testid="stButton"] button {
                    background: rgba(244,67,54,.075) !important;
                    border: 1px solid rgba(244,67,54,.24) !important;
                    color:#FF9B97 !important;
                }
                div[data-testid="stVerticalBlock"]:has(.admin-v6-delete-action-marker) div[data-testid="stButton"] button:hover {
                    background: rgba(244,67,54,.18) !important;
                    color:#FFFFFF !important;
                }
                div[data-testid="stVerticalBlock"]:has(.admin-v6-role-action-marker) div[data-testid="stButton"] button:disabled,
                div[data-testid="stVerticalBlock"]:has(.admin-v6-delete-action-marker) div[data-testid="stButton"] button:disabled {
                    background: rgba(255,255,255,.025) !important;
                    border-color: rgba(255,255,255,.065) !important;
                    box-shadow: none !important;
                    color: rgba(255,255,255,.30) !important;
                    transform: none !important;
                }

                @media (max-width: 1180px) {
                    .admin-v5-directory-head { align-items: flex-start; flex-direction: column; }
                    .admin-v5-role-legend { justify-content: flex-start; }
                    .admin-v6-meta-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); }
                }
                @media (max-width: 720px) {
                    .admin-v6-list-head, .admin-v6-card-top { align-items:flex-start; flex-direction:column; }
                    .admin-v6-access-stack { align-items:flex-start; }
                    .admin-v6-meta-grid { grid-template-columns: 1fr; }
                }

                /* V7 — kartu Manajemen Pengguna lebih berwarna dan memiliki identitas role yang kuat. */
                @keyframes adminV7CardAura {
                    0%, 100% { transform: translate3d(0, 0, 0) scale(1); opacity: .55; }
                    50% { transform: translate3d(-18px, 10px, 0) scale(1.12); opacity: .82; }
                }
                @keyframes adminV7AvatarFlow {
                    0%, 100% { background-position: 0% 50%; }
                    50% { background-position: 100% 50%; }
                }
                @keyframes adminV7CardSweep {
                    0% { transform: translateX(-155%) skewX(-18deg); opacity: 0; }
                    20% { opacity: .32; }
                    100% { transform: translateX(420%) skewX(-18deg); opacity: 0; }
                }

                .admin-v6-list-head {
                    background:
                        radial-gradient(circle at 10% 20%, rgba(229,57,53,.18), transparent 30%),
                        radial-gradient(circle at 88% 10%, rgba(56,215,255,.15), transparent 27%),
                        linear-gradient(135deg, rgba(31,18,38,.97), rgba(10,25,43,.96));
                    border-color: rgba(159,113,255,.24);
                    box-shadow: 0 16px 34px rgba(0,0,0,.18), inset 0 1px 0 rgba(255,255,255,.04);
                }
                .admin-v6-list-icon {
                    background: linear-gradient(135deg, #FF4742, #C850C0 52%, #38D7FF);
                    background-size: 220% 220%;
                    animation: adminV7AvatarFlow 5s ease infinite;
                    border-color: rgba(255,255,255,.20);
                    box-shadow: 0 10px 24px rgba(200,80,192,.26);
                }
                .admin-v6-count-pill {
                    background: linear-gradient(135deg, rgba(29,161,242,.19), rgba(142,90,247,.17));
                    border-color: rgba(93,192,255,.34);
                    box-shadow: 0 10px 24px rgba(29,161,242,.12);
                    color: #D8F0FF;
                }

                div[data-testid="stVerticalBlockBorderWrapper"]:has(.admin-v6-user-card-marker) {
                    --card-accent-2: #8E5AF7;
                    --card-aura: rgba(66,165,245,.24);
                    background:
                        radial-gradient(circle at 8% 0%, var(--card-aura), transparent 31%),
                        radial-gradient(circle at 96% 18%, var(--card-accent-soft), transparent 30%),
                        linear-gradient(135deg, rgba(18,24,39,.99), rgba(10,15,28,.99));
                    border-color: color-mix(in srgb, var(--card-accent) 34%, rgba(255,255,255,.10)) !important;
                    box-shadow:
                        0 22px 48px rgba(0,0,0,.22),
                        0 0 0 1px rgba(255,255,255,.018),
                        inset 0 1px 0 rgba(255,255,255,.05);
                }
                div[data-testid="stVerticalBlockBorderWrapper"]:has(.admin-v6-card-analyst) {
                    --card-accent: #FF4742;
                    --card-accent-2: #D94FA3;
                    --card-accent-soft: rgba(255,71,66,.20);
                    --card-aura: rgba(217,79,163,.23);
                }
                div[data-testid="stVerticalBlockBorderWrapper"]:has(.admin-v6-card-management) {
                    --card-accent: #2E9DFF;
                    --card-accent-2: #38D7FF;
                    --card-accent-soft: rgba(46,157,255,.20);
                    --card-aura: rgba(56,215,255,.22);
                }
                div[data-testid="stVerticalBlockBorderWrapper"]:has(.admin-v6-card-social) {
                    --card-accent: #FF9D3D;
                    --card-accent-2: #FF5F7E;
                    --card-accent-soft: rgba(255,157,61,.20);
                    --card-aura: rgba(255,95,126,.21);
                }
                div[data-testid="stVerticalBlockBorderWrapper"]:has(.admin-v6-user-card-marker)::before {
                    height: 5px;
                    background: linear-gradient(90deg, var(--card-accent), var(--card-accent-2), #B97CFF, var(--card-accent));
                    background-size: 250% 100%;
                    box-shadow: 0 0 24px var(--card-aura);
                }
                div[data-testid="stVerticalBlockBorderWrapper"]:has(.admin-v6-user-card-marker)::after {
                    animation: adminV7CardAura 6.5s ease-in-out infinite;
                    background: radial-gradient(circle, var(--card-aura), transparent 66%);
                    border-radius: 50%;
                    content: '';
                    height: 210px;
                    pointer-events: none;
                    position: absolute;
                    right: -72px;
                    top: -88px;
                    width: 210px;
                    z-index: 0;
                }
                div[data-testid="stVerticalBlockBorderWrapper"]:has(.admin-v6-user-card-marker):hover {
                    border-color: color-mix(in srgb, var(--card-accent) 70%, white 8%) !important;
                    box-shadow:
                        0 28px 58px rgba(0,0,0,.28),
                        0 0 32px var(--card-aura),
                        inset 0 1px 0 rgba(255,255,255,.065);
                    transform: translateY(-5px) scale(1.002);
                }
                div[data-testid="stVerticalBlockBorderWrapper"]:has(.admin-v6-user-card-marker) > div {
                    position: relative;
                    z-index: 1;
                }

                .admin-v6-card-top {
                    background: linear-gradient(110deg, var(--card-accent-soft), rgba(255,255,255,.025) 46%, rgba(255,255,255,0));
                    border-bottom: 1px solid color-mix(in srgb, var(--card-accent) 18%, transparent);
                    border-radius: 18px 18px 0 0;
                    margin: .18rem .18rem .78rem;
                    padding: 1rem 1rem .92rem;
                    position: relative;
                    overflow: hidden;
                }
                .admin-v6-card-top::after {
                    animation: adminV7CardSweep 7.5s ease-in-out infinite;
                    background: linear-gradient(90deg, transparent, rgba(255,255,255,.13), transparent);
                    content: '';
                    inset: 0 auto 0 -28%;
                    pointer-events: none;
                    position: absolute;
                    width: 24%;
                }
                .admin-v6-avatar {
                    background: linear-gradient(135deg, var(--card-accent), var(--card-accent-2), #B97CFF);
                    background-size: 220% 220%;
                    animation: adminV7AvatarFlow 4.8s ease infinite;
                    border-color: rgba(255,255,255,.28);
                    box-shadow: 0 14px 30px var(--card-aura), inset 0 1px 0 rgba(255,255,255,.24);
                    height: 62px;
                    width: 62px;
                }
                .admin-v6-name { font-size: 1.08rem; text-shadow: 0 2px 16px rgba(0,0,0,.25); }
                .admin-v6-handle { color: color-mix(in srgb, var(--card-accent) 55%, white 45%); }
                .admin-v6-account-note {
                    background: rgba(76,175,80,.11);
                    border: 1px solid rgba(76,175,80,.20);
                    border-radius: 999px;
                    color: #8DE49F;
                    display: inline-flex;
                    padding: .28rem .52rem;
                }
                .admin-v6-access-stack {
                    background: linear-gradient(135deg, rgba(255,255,255,.045), var(--card-accent-soft));
                    border: 1px solid color-mix(in srgb, var(--card-accent) 28%, transparent);
                    border-radius: 16px;
                    padding: .66rem .72rem;
                }
                .admin-v6-role-pill {
                    background: linear-gradient(135deg, var(--card-accent), var(--card-accent-2));
                    border-color: rgba(255,255,255,.20);
                    box-shadow: 0 10px 24px var(--card-aura);
                    color: #FFFFFF;
                    padding: .52rem .78rem;
                }
                .admin-v6-access-note { color: #BBC4D3; }

                .admin-v6-meta-grid { gap: .72rem; padding: 0 1rem .82rem; }
                .admin-v6-meta-item {
                    --meta-accent: var(--card-accent);
                    --meta-soft: var(--card-accent-soft);
                    background:
                        radial-gradient(circle at 96% 0%, var(--meta-soft), transparent 45%),
                        linear-gradient(145deg, rgba(255,255,255,.052), rgba(255,255,255,.022));
                    border-color: color-mix(in srgb, var(--meta-accent) 25%, rgba(255,255,255,.08));
                    box-shadow: inset 0 1px 0 rgba(255,255,255,.025);
                    min-height: 76px;
                    padding: .76rem .8rem;
                    position: relative;
                    overflow: hidden;
                }
                .admin-v6-meta-item:nth-child(1) { --meta-accent:#67D391; --meta-soft:rgba(103,211,145,.15); }
                .admin-v6-meta-item:nth-child(2) { --meta-accent:#B97CFF; --meta-soft:rgba(185,124,255,.16); }
                .admin-v6-meta-item:nth-child(3) { --meta-accent:#38D7FF; --meta-soft:rgba(56,215,255,.15); }
                .admin-v6-meta-item:nth-child(4) { --meta-accent:#FFB74D; --meta-soft:rgba(255,183,77,.16); }
                .admin-v6-meta-item::before {
                    background: var(--meta-accent);
                    border-radius: 999px;
                    content: '';
                    height: 6px;
                    left: .8rem;
                    position: absolute;
                    top: .7rem;
                    width: 22px;
                    box-shadow: 0 0 14px var(--meta-soft);
                }
                .admin-v6-meta-item:hover {
                    background:
                        radial-gradient(circle at 88% 12%, var(--meta-soft), transparent 52%),
                        linear-gradient(145deg, rgba(255,255,255,.085), rgba(255,255,255,.035));
                    border-color: color-mix(in srgb, var(--meta-accent) 58%, transparent);
                    box-shadow: 0 14px 28px rgba(0,0,0,.14), 0 0 20px var(--meta-soft);
                    transform: translateY(-4px);
                }
                .admin-v6-meta-label { color: color-mix(in srgb, var(--meta-accent) 62%, white 38%); padding-top: .42rem; }
                .admin-v6-meta-value { color:#FFFFFF; font-size:.78rem; }
                .admin-v6-card-divider {
                    background: linear-gradient(90deg, transparent, var(--card-accent), var(--card-accent-2), transparent);
                    height: 2px;
                    margin: .08rem 1rem .68rem;
                    opacity: .55;
                }

                div[data-testid="stHorizontalBlock"]:has(.admin-v6-role-action-marker) {
                    background:
                        radial-gradient(circle at 78% 20%, var(--card-accent-soft), transparent 34%),
                        linear-gradient(135deg, rgba(255,255,255,.035), rgba(255,255,255,.012));
                    border: 1px solid color-mix(in srgb, var(--card-accent) 20%, rgba(255,255,255,.06));
                    border-radius: 16px;
                    margin: 0 .86rem .84rem;
                    padding: .68rem .72rem;
                }
                .admin-v6-action-label {
                    color: color-mix(in srgb, var(--card-accent) 58%, white 42%);
                    padding: .55rem 0 0;
                }
                div[data-testid="stVerticalBlock"]:has(.admin-v6-role-action-marker) div[data-testid="stButton"] button {
                    background: linear-gradient(135deg, var(--card-accent), var(--card-accent-2)) !important;
                    border-color: rgba(255,255,255,.18) !important;
                    box-shadow: 0 12px 26px var(--card-aura) !important;
                    color: #FFFFFF !important;
                }
                div[data-testid="stVerticalBlock"]:has(.admin-v6-role-action-marker) div[data-testid="stButton"] button:hover {
                    box-shadow: 0 16px 34px var(--card-aura), 0 0 0 1px rgba(255,255,255,.10) !important;
                    filter: brightness(1.10) saturate(1.12);
                    transform: translateY(-3px) scale(1.015);
                }
                div[data-testid="stVerticalBlock"]:has(.admin-v6-delete-action-marker) div[data-testid="stButton"] button {
                    background: linear-gradient(135deg, rgba(183,28,28,.92), rgba(255,71,66,.92), rgba(217,79,163,.86)) !important;
                    border-color: rgba(255,104,100,.34) !important;
                    box-shadow: 0 12px 24px rgba(244,67,54,.18) !important;
                    color: #FFFFFF !important;
                }
                div[data-testid="stVerticalBlock"]:has(.admin-v6-delete-action-marker) div[data-testid="stButton"] button:hover {
                    box-shadow: 0 16px 34px rgba(244,67,54,.28), 0 0 0 1px rgba(255,105,101,.14) !important;
                    filter: brightness(1.10) saturate(1.12);
                    transform: translateY(-3px) scale(1.015);
                }

                @media (max-width: 1000px) {
                    .admin-v3-hero { padding-right: clamp(1.25rem, 3vw, 2rem); }
                    .admin-v3-hero-orbit { display: none; }
                    .admin-v3-hero-status-grid { grid-template-columns: 1fr; }
                }
                @media (max-width: 700px) {
                    .admin-v3-hero-top { align-items: flex-start; flex-direction: column; }
                    .admin-v3-mini-stat-grid { grid-template-columns: 1fr; }
                    .admin-v3-section-head { align-items: flex-start; }
                    .admin-v3-section-live { margin-left: 0; }
                }
                @media (prefers-reduced-motion: reduce) {
                    .admin-v3-hero::before,
                    .admin-v3-hero::after,
                    .admin-v3-orbit-ring,
                    .admin-v3-orbit-core,
                    .admin-v3-hero-status::after,
                    .admin-v3-section-head::after,
                    .admin-v3-mini-eq span,
                    .admin-v3-file-card::before,
                    .admin-v5-directory-head::after,
                    .admin-v5-directory-icon,
                    .admin-v5-avatar,
                    .admin-v3-toolbar-note::before,
                    div[data-testid="stVerticalBlockBorderWrapper"]:has(.admin-v5-user-row-marker)::before,
                    div[data-testid="stVerticalBlockBorderWrapper"]:has(.admin-v5-user-row-marker)::after { animation: none !important; }
                }
            </style>
            """,
            unsafe_allow_html=True,
        )
    except Exception as error:
        st.error(f"Gagal memuat tampilan Admin Panel: {error}")


def _render_admin_hero() -> None:
    """Tampilkan hero Admin Panel sebagai command center interaktif."""
    try:
        admin_name = escape(
            str(
                st.session_state.get("fullname")
                or st.session_state.get("username")
                or "Data Analis"
            )
        )
        stats = get_user_stats()
        status_table = _build_file_status_table()
        available_count = (
            int(status_table["Tersedia"].sum()) if not status_table.empty else 0
        )
        total_files = len(status_table)
        total_users = int(stats.get("total_users", 0) or 0)
        analyst_count = int(stats.get("total_data_analyst", 0) or 0)
        st.markdown(
            f"""
            <section class="admin-v3-hero" tabindex="0">
                <div class="admin-v3-hero-top">
                    <div class="admin-v3-hero-icon">⚙️</div>
                    <div class="admin-v3-hero-copy">
                        <div class="admin-v3-hero-kicker">Administrative Command Center</div>
                        <h1>Admin Panel</h1>
                        <p>
                            Kendalikan pengguna, hak akses, kesiapan data, dan kesehatan sistem
                            dalam satu pusat operasi. Selamat datang, <strong>{admin_name}</strong>.
                        </p>
                        <div class="admin-v3-hero-badges">
                            <span class="admin-v3-hero-badge"><span class="admin-v3-online-dot"></span>Sistem aktif</span>
                            <span class="admin-v3-hero-badge">🛡️ Role guard aktif</span>
                            <span class="admin-v3-hero-badge">🗃️ SQLite terhubung</span>
                            <span class="admin-v3-hero-badge">✨ Dashboard v2.0</span>
                        </div>
                        <div class="admin-v3-hero-status-grid">
                            <div class="admin-v3-hero-status" tabindex="0">
                                <div class="admin-v3-hero-status-label">User Registry</div>
                                <div class="admin-v3-hero-status-value">{total_users} akun terdaftar</div>
                            </div>
                            <div class="admin-v3-hero-status" tabindex="0">
                                <div class="admin-v3-hero-status-label">Analyst Access</div>
                                <div class="admin-v3-hero-status-value">{analyst_count} Data Analis</div>
                            </div>
                            <div class="admin-v3-hero-status" tabindex="0">
                                <div class="admin-v3-hero-status-label">Data Readiness</div>
                                <div class="admin-v3-hero-status-value">{available_count}/{total_files} file siap</div>
                            </div>
                        </div>
                    </div>
                </div>
                <div class="admin-v3-hero-orbit" aria-hidden="true">
                    <div class="admin-v3-orbit-ring ring-one"></div>
                    <div class="admin-v3-orbit-ring ring-two"></div>
                    <div class="admin-v3-orbit-core"><strong>{available_count}/{total_files}</strong><small>System Core</small></div>
                </div>
            </section>
            """,
            unsafe_allow_html=True,
        )
    except Exception as error:
        st.error(f"Gagal menampilkan header Admin Panel: {error}")


def _render_section_header(icon: str, title: str, description: str, tone: str = "") -> None:
    """Tampilkan judul seksi dalam kartu animatif."""
    try:
        st.markdown(
            f"""
            <div class="admin-v3-section-head {escape(tone)}" tabindex="0">
                <div class="admin-v3-section-icon">{escape(icon)}</div>
                <div class="admin-v3-section-copy">
                    <h2>{escape(title)}</h2>
                    <p>{escape(description)}</p>
                </div>
                <div class="admin-v3-section-live"><i></i>Live view</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
    except Exception as error:
        st.error(f"Gagal menampilkan judul bagian: {error}")


def _render_metric_cards(items: list[dict]) -> None:
    """Tampilkan kartu metrik animatif dan dapat difokuskan."""
    try:
        cards = []
        for index, item in enumerate(items):
            cards.append(
                '<article class="admin-v3-mini-stat" tabindex="0" '
                f'style="--metric-accent:{escape(str(item["color"]))}; animation-delay:{index * 65}ms;">'
                '<div class="admin-v3-mini-stat-top">'
                '<div>'
                '<div class="admin-v3-mini-stat-kicker">Live metric</div>'
                f'<span class="admin-v3-mini-stat-icon">{escape(str(item["icon"]))}</span>'
                '</div>'
                '<div class="admin-v3-mini-eq" aria-hidden="true"><span></span><span></span><span></span><span></span></div>'
                '</div>'
                f'<div class="admin-v3-mini-stat-value">{escape(str(item["value"]))}</div>'
                f'<div class="admin-v3-mini-stat-label">{escape(str(item["label"]))}</div>'
                '<div class="admin-v3-mini-stat-foot"><i></i>Arahkan kursor untuk fokus</div>'
                '</article>'
            )

        metric_html = '<div class="admin-v3-mini-stat-grid">' + ''.join(cards) + '</div>'
        st.markdown(metric_html, unsafe_allow_html=True)
    except Exception as error:
        st.error(f"Gagal menampilkan kartu statistik: {error}")


def _set_flash_message(message_type: str, message: str) -> None:
    """Simpan pesan sementara agar tetap tampil setelah halaman dimuat ulang."""
    try:
        st.session_state[FLASH_MESSAGE_KEY] = {
            "type": message_type,
            "message": message,
        }
    except Exception as error:
        st.error(f"Gagal menyimpan notifikasi admin: {error}")


def _show_flash_message() -> None:
    """Tampilkan dan hapus pesan sementara dari session state."""
    try:
        flash = st.session_state.pop(FLASH_MESSAGE_KEY, None)
        if not flash:
            return

        message_type = flash.get("type", "info")
        message = flash.get("message", "")

        if message_type == "success":
            st.success(message)
        elif message_type == "warning":
            st.warning(message)
        elif message_type == "error":
            st.error(message)
        else:
            st.info(message)
    except Exception as error:
        st.error(f"Gagal menampilkan notifikasi admin: {error}")


def _format_file_size(size_bytes: int) -> str:
    """Ubah ukuran file dalam byte menjadi format yang mudah dibaca."""
    try:
        size = float(max(size_bytes, 0))
        units = ["B", "KB", "MB", "GB"]
        for unit in units:
            if size < 1024 or unit == units[-1]:
                return f"{size:.2f} {unit}"
            size /= 1024
        return "0.00 B"
    except Exception as error:
        st.error(f"Gagal membaca ukuran file: {error}")
        return "-"


def _parse_created_at(value) -> pd.Timestamp | None:
    """Konversi nilai created_at menjadi Timestamp Pandas secara defensif."""
    try:
        if value is None or str(value).strip() == "":
            return None
        parsed = pd.to_datetime(value, errors="coerce")
        if pd.isna(parsed):
            return None
        return parsed
    except Exception as error:
        st.error(f"Gagal membaca tanggal registrasi: {error}")
        return None


def _count_new_users_this_month(users: list[dict]) -> int:
    """Hitung jumlah pengguna yang dibuat pada bulan berjalan."""
    try:
        now = pd.Timestamp.now()
        total = 0
        for user in users:
            created_at = _parse_created_at(user.get("created_at"))
            if created_at is not None and created_at.year == now.year and created_at.month == now.month:
                total += 1
        return total
    except Exception as error:
        st.error(f"Gagal menghitung pengguna baru bulan ini: {error}")
        return 0


def _build_monthly_registration(users: list[dict]) -> pd.DataFrame:
    """Bangun ringkasan jumlah registrasi pengguna per bulan."""
    try:
        registration_dates = []
        for user in users:
            created_at = _parse_created_at(user.get("created_at"))
            if created_at is not None:
                registration_dates.append(created_at)

        if not registration_dates:
            return pd.DataFrame(columns=["Bulan", "Jumlah Registrasi"])

        date_series = pd.Series(registration_dates, name="created_at")
        monthly = (
            date_series.dt.to_period("M")
            .value_counts()
            .sort_index()
            .rename_axis("periode")
            .reset_index(name="Jumlah Registrasi")
        )
        monthly["Bulan"] = monthly["periode"].astype(str)
        return monthly[["Bulan", "Jumlah Registrasi"]]
    except Exception as error:
        st.error(f"Gagal membuat statistik registrasi bulanan: {error}")
        return pd.DataFrame(columns=["Bulan", "Jumlah Registrasi"])


def _find_available_file(alternatives: list[str]) -> Path | None:
    """Cari file pertama yang tersedia dari daftar path alternatif."""
    try:
        for relative_path in alternatives:
            full_path = PROJECT_ROOT / relative_path
            if full_path.is_file():
                return full_path
        return None
    except Exception as error:
        st.error(f"Gagal mencari file data: {error}")
        return None


def _build_file_status_table() -> pd.DataFrame:
    """Bangun tabel status keberadaan dan ukuran file data penelitian."""
    try:
        rows = []
        for item in EXPECTED_DATA_FILES:
            available_file = _find_available_file(item["alternatives"])
            exists = available_file is not None
            if exists:
                displayed_path = available_file.relative_to(PROJECT_ROOT).as_posix()
                size_text = _format_file_size(available_file.stat().st_size)
                status_text = "Tersedia"
            else:
                displayed_path = item["canonical"]
                size_text = "-"
                status_text = "Tidak tersedia"

            rows.append(
                {
                    "Jenis Data": item["label"],
                    "Ikon": item["icon"],
                    "File": displayed_path,
                    "Status": status_text,
                    "Ukuran": size_text,
                    "Tersedia": exists,
                }
            )
        return pd.DataFrame(rows)
    except Exception as error:
        st.error(f"Gagal membuat status file: {error}")
        return pd.DataFrame(columns=["Jenis Data", "Ikon", "File", "Status", "Ukuran", "Tersedia"])


def _validate_new_user(fullname: str, username: str, email: str, password: str) -> tuple[bool, str]:
    """Validasi input form tambah pengguna sebelum diteruskan ke database."""
    try:
        fullname = fullname.strip()
        username = username.strip()
        email = email.strip()

        if not fullname or not username or not email or not password:
            return False, "Semua kolom wajib diisi."
        if len(fullname) < 3:
            return False, "Nama lengkap minimal 3 karakter."
        if len(username) < 3:
            return False, "Username minimal 3 karakter."
        if " " in username:
            return False, "Username tidak boleh mengandung spasi."
        if not re.fullmatch(r"[A-Za-z0-9_.-]+", username):
            return False, "Username hanya boleh berisi huruf, angka, titik, garis bawah, atau tanda minus."
        if not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", email):
            return False, "Format email belum valid."
        if len(password) < 8:
            return False, "Password minimal 8 karakter."
        return True, "Input valid."
    except Exception as error:
        st.error(f"Gagal memvalidasi form pengguna: {error}")
        return False, "Validasi form gagal dilakukan."


def _scroll_ke_konfirmasi_hapus() -> None:
    """Gulirkan area utama ke card konfirmasi hapus setelah tombol diklik."""
    try:
        components.html(
            """
            <script>
                (() => {
                    const scrollToConfirmation = () => {
                        const parentDocument = window.parent.document;
                        const target = parentDocument.getElementById(
                            'admin-delete-confirmation-anchor'
                        );
                        if (!target) return false;

                        target.scrollIntoView({
                            behavior: 'smooth',
                            block: 'start',
                            inline: 'nearest'
                        });

                        window.setTimeout(() => {
                            const mainContainer = target.closest(
                                'section[data-testid="stMain"]'
                            ) || parentDocument.querySelector(
                                'section[data-testid="stMain"]'
                            );
                            if (mainContainer) {
                                mainContainer.scrollBy({
                                    top: -72,
                                    behavior: 'smooth'
                                });
                            } else {
                                window.parent.scrollBy({
                                    top: -72,
                                    behavior: 'smooth'
                                });
                            }
                        }, 240);
                        return true;
                    };

                    let attempts = 0;
                    const timer = window.setInterval(() => {
                        attempts += 1;
                        if (scrollToConfirmation() || attempts >= 12) {
                            window.clearInterval(timer);
                        }
                    }, 90);
                })();
            </script>
            """,
            height=0,
            width=0,
        )
    except Exception:
        # Auto-scroll bersifat bantuan visual; kegagalan JS tidak boleh
        # mengganggu mekanisme penghapusan akun.
        pass


def _render_delete_confirmation(current_user_id: int) -> None:
    """Tampilkan konfirmasi penghapusan akun yang rapi dan tetap aman."""
    try:
        target = st.session_state.get(DELETE_TARGET_KEY)
        if not target:
            return

        target_id = int(target.get("user_id", 0))
        target_username = str(target.get("username", "-") or "-").strip()
        target_fullname = str(target.get("fullname", "-") or "-").strip()
        initials = "".join(
            part[0] for part in target_fullname.split()[:2] if part
        ).upper() or "U"

        st.markdown(
            '<div id="admin-delete-confirmation-anchor" '
            'style="scroll-margin-top:88px;height:1px;"></div>',
            unsafe_allow_html=True,
        )
        if st.session_state.pop(DELETE_SCROLL_PENDING_KEY, False):
            _scroll_ke_konfirmasi_hapus()

        st.markdown(
            """
            <style>
                @keyframes adminDeletePulse {
                    0%, 100% { box-shadow: 0 0 0 0 rgba(244,63,94,.20), 0 16px 34px rgba(0,0,0,.18); }
                    50% { box-shadow: 0 0 0 12px rgba(244,63,94,0), 0 20px 42px rgba(244,63,94,.14); }
                }
                @keyframes adminDeleteSweep {
                    0% { transform: translateX(-145%) skewX(-18deg); opacity: 0; }
                    18% { opacity: .24; }
                    100% { transform: translateX(260%) skewX(-18deg); opacity: 0; }
                }
                @keyframes adminDeleteFloat {
                    0%, 100% { transform: translateY(0) rotate(0deg); }
                    50% { transform: translateY(-4px) rotate(-4deg); }
                }
                .admin-delete-v1-shell {
                    position: relative;
                    overflow: hidden;
                    margin: .72rem 0 .84rem;
                    padding: 1.12rem 1.14rem 1rem;
                    border-radius: 22px;
                    border: 1px solid rgba(244,63,94,.28);
                    background:
                        radial-gradient(circle at 8% 8%, rgba(244,63,94,.14), transparent 31%),
                        radial-gradient(circle at 92% 4%, rgba(217,70,239,.10), transparent 27%),
                        linear-gradient(135deg, rgba(41,14,24,.96), rgba(18,14,24,.98) 54%, rgba(11,18,31,.98));
                    box-shadow: 0 20px 46px rgba(0,0,0,.22), inset 0 1px 0 rgba(255,255,255,.035);
                }
                .admin-delete-v1-shell::before {
                    content: '';
                    position: absolute;
                    inset: 0;
                    background: linear-gradient(112deg, transparent 0%, rgba(255,255,255,.08) 47%, transparent 100%);
                    transform: translateX(-145%) skewX(-18deg);
                    animation: adminDeleteSweep 8.5s linear infinite;
                    pointer-events: none;
                }
                .admin-delete-v1-top {
                    position: relative;
                    z-index: 1;
                    display: flex;
                    align-items: flex-start;
                    justify-content: space-between;
                    gap: 1rem;
                    flex-wrap: wrap;
                }
                .admin-delete-v1-heading {
                    display: flex;
                    align-items: flex-start;
                    gap: .86rem;
                    min-width: 0;
                }
                .admin-delete-v1-icon {
                    width: 50px;
                    height: 50px;
                    min-width: 50px;
                    border-radius: 17px;
                    display: flex;
                    align-items: center;
                    justify-content: center;
                    color: #FFF;
                    font-size: 1.22rem;
                    background: linear-gradient(145deg, #F43F5E, #D946EF);
                    border: 1px solid rgba(255,255,255,.14);
                    animation: adminDeleteFloat 3.3s ease-in-out infinite, adminDeletePulse 2.4s ease-in-out infinite;
                }
                .admin-delete-v1-title {
                    color: #FFFFFF;
                    font-size: clamp(1.1rem, 1.7vw, 1.42rem);
                    font-weight: 900;
                    letter-spacing: -.025em;
                    line-height: 1.15;
                }
                .admin-delete-v1-copy {
                    color: #C6CDDA;
                    font-size: .84rem;
                    line-height: 1.62;
                    margin-top: .3rem;
                    max-width: 780px;
                }
                .admin-delete-v1-permanent {
                    display: inline-flex;
                    align-items: center;
                    gap: .45rem;
                    padding: .52rem .78rem;
                    border-radius: 999px;
                    color: #FFD4DB;
                    font-size: 0.75rem /* FIX: minimum 12px agar terbaca di tablet */;
                    font-weight: 850;
                    letter-spacing: .045em;
                    text-transform: uppercase;
                    background: rgba(244,63,94,.10);
                    border: 1px solid rgba(244,63,94,.24);
                }
                .admin-delete-v1-permanent i {
                    width: 7px;
                    height: 7px;
                    border-radius: 50%;
                    background: #FB7185;
                    box-shadow: 0 0 0 6px rgba(251,113,133,.09);
                }
                .admin-delete-v1-user {
                    position: relative;
                    z-index: 1;
                    display: grid;
                    grid-template-columns: auto minmax(0,1fr) auto;
                    align-items: center;
                    gap: .82rem;
                    margin-top: .92rem;
                    padding: .86rem .92rem;
                    border-radius: 18px;
                    border: 1px solid rgba(255,255,255,.085);
                    background: linear-gradient(135deg, rgba(255,255,255,.052), rgba(255,255,255,.024));
                    transition: transform .18s ease, border-color .18s ease, box-shadow .18s ease;
                }
                .admin-delete-v1-user:hover {
                    transform: translateY(-2px);
                    border-color: rgba(244,63,94,.23);
                    box-shadow: 0 15px 30px rgba(0,0,0,.17);
                }
                .admin-delete-v1-avatar {
                    width: 48px;
                    height: 48px;
                    border-radius: 16px;
                    display: flex;
                    align-items: center;
                    justify-content: center;
                    color: #FFFFFF;
                    font-weight: 900;
                    font-size: .95rem;
                    background: linear-gradient(145deg, rgba(244,63,94,.88), rgba(139,92,246,.84));
                    border: 1px solid rgba(255,255,255,.13);
                    box-shadow: 0 12px 25px rgba(217,70,239,.16);
                }
                .admin-delete-v1-name {
                    color: #FFFFFF;
                    font-size: .92rem;
                    font-weight: 850;
                    line-height: 1.2;
                    overflow: hidden;
                    text-overflow: ellipsis;
                    white-space: nowrap;
                }
                .admin-delete-v1-handle {
                    color: #AAB4C5;
                    font-size: 0.75rem /* FIX: minimum 12px agar terbaca di tablet */;
                    font-weight: 650;
                    margin-top: .17rem;
                }
                .admin-delete-v1-id {
                    padding: .46rem .68rem;
                    border-radius: 12px;
                    color: #F8FAFC;
                    font-size: 0.75rem /* FIX: minimum 12px agar terbaca di tablet */;
                    font-weight: 800;
                    background: rgba(255,255,255,.055);
                    border: 1px solid rgba(255,255,255,.09);
                    white-space: nowrap;
                }
                .admin-delete-v1-warning-grid {
                    position: relative;
                    z-index: 1;
                    display: grid;
                    grid-template-columns: repeat(3, minmax(0,1fr));
                    gap: .62rem;
                    margin-top: .72rem;
                }
                .admin-delete-v1-warning {
                    padding: .62rem .72rem;
                    border-radius: 14px;
                    color: #C9D1DE;
                    font-size: 0.75rem /* FIX: minimum 12px agar terbaca di tablet */;
                    font-weight: 700;
                    line-height: 1.45;
                    background: rgba(255,255,255,.035);
                    border: 1px solid rgba(255,255,255,.075);
                    transition: transform .16s ease, background .16s ease, border-color .16s ease;
                }
                .admin-delete-v1-warning:hover {
                    transform: translateY(-2px);
                    background: rgba(244,63,94,.07);
                    border-color: rgba(244,63,94,.18);
                }
                .admin-delete-v1-warning b {
                    color: #FFFFFF;
                    display: block;
                    font-size: 0.75rem /* FIX: minimum 12px agar terbaca di tablet */;
                    margin-bottom: .12rem;
                }
                .admin-delete-v1-confirm-marker,
                .admin-delete-v1-cancel-marker { display: none; }
                div[data-testid="stVerticalBlock"]:has(.admin-delete-v1-confirm-marker) div[data-testid="stButton"] button,
                div[data-testid="stVerticalBlock"]:has(.admin-delete-v1-cancel-marker) div[data-testid="stButton"] button {
                    min-height: 54px !important;
                    border-radius: 15px !important;
                    font-weight: 850 !important;
                    transition: transform .16s ease, box-shadow .16s ease, border-color .16s ease, filter .16s ease !important;
                }
                div[data-testid="stVerticalBlock"]:has(.admin-delete-v1-confirm-marker) div[data-testid="stButton"] button {
                    color: #FFFFFF !important;
                    background: linear-gradient(100deg, #DC2626, #F43F5E 48%, #D946EF) !important;
                    border: 1px solid rgba(255,255,255,.10) !important;
                    box-shadow: 0 14px 28px rgba(244,63,94,.22) !important;
                }
                div[data-testid="stVerticalBlock"]:has(.admin-delete-v1-confirm-marker) div[data-testid="stButton"] button:hover {
                    transform: translateY(-2px);
                    box-shadow: 0 18px 34px rgba(244,63,94,.32) !important;
                    filter: saturate(1.08) brightness(1.05);
                }
                div[data-testid="stVerticalBlock"]:has(.admin-delete-v1-cancel-marker) div[data-testid="stButton"] button {
                    color: #E7ECF5 !important;
                    background: linear-gradient(145deg, rgba(24,33,48,.96), rgba(15,23,38,.96)) !important;
                    border: 1px solid rgba(148,163,184,.20) !important;
                    box-shadow: 0 12px 25px rgba(0,0,0,.15) !important;
                }
                div[data-testid="stVerticalBlock"]:has(.admin-delete-v1-cancel-marker) div[data-testid="stButton"] button:hover {
                    transform: translateY(-2px);
                    border-color: rgba(148,163,184,.36) !important;
                    box-shadow: 0 16px 30px rgba(0,0,0,.20) !important;
                }
                @media (max-width: 760px) {
                    .admin-delete-v1-user { grid-template-columns: auto minmax(0,1fr); }
                    .admin-delete-v1-id { grid-column: 1 / -1; justify-self: start; }
                    .admin-delete-v1-warning-grid { grid-template-columns: 1fr; }
                }
                @media (prefers-reduced-motion: reduce) {
                    .admin-delete-v1-shell::before,
                    .admin-delete-v1-icon { animation: none !important; }
                }
            </style>
            """,
            unsafe_allow_html=True,
        )

        st.markdown(
            f"""
            <section class="admin-delete-v1-shell">
                <div class="admin-delete-v1-top">
                    <div class="admin-delete-v1-heading">
                        <div class="admin-delete-v1-icon">⚠</div>
                        <div>
                            <div class="admin-delete-v1-title">Konfirmasi Penghapusan Akun</div>
                            <div class="admin-delete-v1-copy">
                                Periksa kembali akun tujuan sebelum melanjutkan. Setelah dikonfirmasi,
                                akun akan dihapus secara permanen dan tindakan ini tidak dapat dibatalkan.
                            </div>
                        </div>
                    </div>
                    <div class="admin-delete-v1-permanent"><i></i>Tindakan permanen</div>
                </div>
                <div class="admin-delete-v1-user" tabindex="0">
                    <div class="admin-delete-v1-avatar">{escape(initials)}</div>
                    <div>
                        <div class="admin-delete-v1-name">{escape(target_fullname)}</div>
                        <div class="admin-delete-v1-handle">@{escape(target_username)}</div>
                    </div>
                    <div class="admin-delete-v1-id">ID Pengguna #{target_id}</div>
                </div>
                <div class="admin-delete-v1-warning-grid">
                    <div class="admin-delete-v1-warning"><b>🗑 Akun dihapus</b>Pengguna tidak lagi dapat masuk menggunakan akun ini.</div>
                    <div class="admin-delete-v1-warning"><b>↩ Tidak dapat dibatalkan</b>Pastikan nama, username, dan ID sudah sesuai.</div>
                    <div class="admin-delete-v1-warning"><b>🛡 Pemeriksaan aman</b>Akun utama dan akun aktif tetap dilindungi oleh sistem.</div>
                </div>
            </section>
            """,
            unsafe_allow_html=True,
        )

        spacer_col, cancel_col, confirm_col = st.columns([3.9, 1.25, 1.65], gap="small")
        with spacer_col:
            st.empty()
        with cancel_col:
            st.markdown(
                '<span class="admin-delete-v1-cancel-marker"></span>',
                unsafe_allow_html=True,
            )
            cancel_delete = st.button(
                "↩ Batal",
                key=f"cancel_delete_user_{target_id}",
                use_container_width=True,
            )
        with confirm_col:
            st.markdown(
                '<span class="admin-delete-v1-confirm-marker"></span>',
                unsafe_allow_html=True,
            )
            confirm_delete = st.button(
                "🗑 Hapus Permanen",
                key=f"confirm_delete_user_{target_id}",
                type="primary",
                use_container_width=True,
            )

        if cancel_delete:
            st.session_state.pop(DELETE_TARGET_KEY, None)
            st.rerun()

        if confirm_delete:
            if target_username.lower() in LOCKED_DEFAULT_USERNAMES:
                st.session_state.pop(DELETE_TARGET_KEY, None)
                _set_flash_message(
                    "error",
                    "Akun default admin, manajemen, dan sosmed_officer tidak dapat dihapus.",
                )
                st.rerun()
            if target_id == 1:
                st.session_state.pop(DELETE_TARGET_KEY, None)
                _set_flash_message("error", "Data Analis utama dengan user_id=1 tidak dapat dihapus.")
                st.rerun()
            if target_id == current_user_id:
                st.session_state.pop(DELETE_TARGET_KEY, None)
                _set_flash_message("error", "Akun yang sedang digunakan tidak dapat dihapus.")
                st.rerun()

            success, message = delete_user(target_id)
            log_activity(
                "DELETE_USER",
                "Admin Panel",
                (
                    f"Akun @{target_username} berhasil dihapus oleh administrator."
                    if success
                    else f"Penghapusan akun @{target_username} gagal."
                ),
                status="success" if success else "failed",
                metadata={
                    "target_user_id": target_id,
                    "target_username": target_username,
                    "result": message,
                },
            )
            st.session_state.pop(DELETE_TARGET_KEY, None)
            _set_flash_message("success" if success else "error", message)
            st.rerun()
    except Exception as error:
        st.error(f"Gagal menampilkan konfirmasi penghapusan: {error}")


def _filter_users(users: list[dict], keyword: str, role_filter: str) -> list[dict]:
    """Filter pengguna berdasarkan kata pencarian dan role."""
    try:
        keyword_normalized = keyword.strip().lower()
        result = []
        for user in users:
            role = normalize_role(
                user.get("role", DEFAULT_ROLE),
                user.get("user_id"),
            )
            if role_filter != "Semua Role" and role != role_filter:
                continue
            searchable = " ".join(
                [
                    *(
                        str(user.get(field, ""))
                        for field in ["user_id", "fullname", "username", "email", "role"]
                    ),
                    get_role_label(role, user.get("user_id")),
                ]
            ).lower()
            if keyword_normalized and keyword_normalized not in searchable:
                continue
            result.append(user)
        return result
    except Exception as error:
        st.error(f"Gagal memfilter pengguna: {error}")
        return users


@_DIALOG_DECORATOR("Ubah Role Pengguna")
def _render_change_role_dialog(
    user_id: int,
    username: str,
    fullname: str,
    current_role: str,
) -> None:
    """Tampilkan dialog pemilihan role manual yang rapi dan informatif."""
    try:
        username_normalized = str(username or "").strip().lower()
        if username_normalized in LOCKED_DEFAULT_USERNAMES:
            st.error("Role akun default admin, manajemen, dan sosmed_officer tidak dapat diubah.")
            return

        current_role_normalized = normalize_role(current_role, user_id)
        role_theme = {
            "management": {
                "accent": "#38BDF8",
                "soft": "rgba(56,189,248,.14)",
                "border": "rgba(56,189,248,.34)",
                "icon": "💼",
                "label": "Manajemen",
                "access": ["Beranda", "Rekomendasi"],
            },
            "data_analyst": {
                "accent": "#8B5CF6",
                "soft": "rgba(139,92,246,.15)",
                "border": "rgba(139,92,246,.36)",
                "icon": "🛡️",
                "label": "Data Analis",
                "access": ["Seluruh Analisis", "Dataset", "Admin Panel"],
            },
            "social_media_officer": {
                "accent": "#F97316",
                "soft": "rgba(249,115,22,.15)",
                "border": "rgba(249,115,22,.36)",
                "icon": "📣",
                "label": "Sosmed Officer",
                "access": ["Beranda", "SNA", "Rekomendasi", "Profil"],
            },
        }

        st.markdown(
            """
            <style>
                @keyframes adminRoleDialogGlow {
                    0%,100% { opacity:.50; transform:translate3d(0,0,0) scale(1); }
                    50% { opacity:.88; transform:translate3d(0,-6px,0) scale(1.05); }
                }
                @keyframes adminRoleDialogSweep {
                    0% { transform:translateX(-145%) skewX(-18deg); opacity:0; }
                    18% { opacity:.25; }
                    100% { transform:translateX(265%) skewX(-18deg); opacity:0; }
                }
                @keyframes adminRoleAvatarPulse {
                    0%,100% { box-shadow:0 12px 30px rgba(229,57,53,.20),0 0 0 0 rgba(229,57,53,.18); }
                    50% { box-shadow:0 18px 38px rgba(139,92,246,.24),0 0 0 9px rgba(139,92,246,0); }
                }

                div[data-testid="stDialog"] > div[role="dialog"] {
                    width:min(820px,calc(100vw - 2rem)) !important;
                    max-width:820px !important;
                    border:1px solid rgba(255,255,255,.11) !important;
                    border-radius:28px !important;
                    overflow:hidden;
                    background:
                        radial-gradient(circle at 9% 0%,rgba(229,57,53,.20),transparent 31%),
                        radial-gradient(circle at 94% 4%,rgba(139,92,246,.19),transparent 32%),
                        linear-gradient(145deg,#111722 0%,#0B1019 58%,#0C121D 100%) !important;
                    box-shadow:0 34px 90px rgba(0,0,0,.58),inset 0 1px 0 rgba(255,255,255,.04) !important;
                }
                div[data-testid="stDialog"] > div[role="dialog"]::before {
                    content:""; position:absolute; inset:0 0 auto; height:3px;
                    background:linear-gradient(90deg,#E53935,#D946EF,#38BDF8,#F97316);
                    background-size:220% 100%; animation:adminRoleDialogGlow 4s ease-in-out infinite;
                }
                div[data-testid="stDialog"] h2 {
                    color:#FFF !important; font-weight:900 !important;
                    letter-spacing:-.035em !important; font-size:clamp(1.65rem,3vw,2.15rem) !important;
                }
                div[data-testid="stDialog"] [data-testid="stDialogContent"] {
                    padding-top:.15rem !important;
                }

                .admin-role-v2-eyebrow {
                    display:flex;align-items:center;gap:.48rem;margin:.05rem 0 .72rem;
                    color:#A9B5C8;font-size:0.75rem /* FIX: minimum 12px agar terbaca di tablet */;font-weight:800;letter-spacing:.12em;text-transform:uppercase;
                }
                .admin-role-v2-eyebrow span {width:7px;height:7px;border-radius:99px;background:#F43F5E;box-shadow:0 0 14px rgba(244,63,94,.76);}
                .admin-role-v2-hero {
                    position:relative;overflow:hidden;display:grid;grid-template-columns:auto 1fr auto;
                    align-items:center;gap:1rem;padding:1.05rem 1.1rem;margin:.05rem 0 1rem;
                    border:1px solid rgba(255,255,255,.10);border-radius:22px;
                    background:linear-gradient(135deg,rgba(229,57,53,.14),rgba(139,92,246,.11) 55%,rgba(56,189,248,.07));
                    box-shadow:0 18px 36px rgba(0,0,0,.20),inset 0 1px 0 rgba(255,255,255,.04);
                }
                .admin-role-v2-hero::after {
                    content:"";position:absolute;inset:0;width:34%;pointer-events:none;
                    background:linear-gradient(100deg,transparent,rgba(255,255,255,.12),transparent);
                    animation:adminRoleDialogSweep 7.5s linear infinite;
                }
                .admin-role-v2-avatar {
                    width:62px;height:62px;border-radius:20px;display:flex;align-items:center;justify-content:center;
                    color:#FFF;font-size:1.18rem;font-weight:950;letter-spacing:-.03em;
                    background:linear-gradient(135deg,#F43F5E,#A855F7 58%,#38BDF8);
                    border:1px solid rgba(255,255,255,.16);animation:adminRoleAvatarPulse 3.4s ease-in-out infinite;
                }
                .admin-role-v2-name {color:#FFF;font-size:1.12rem;font-weight:900;line-height:1.14;letter-spacing:-.02em;}
                .admin-role-v2-handle {color:#AAB4C5;font-size:.83rem;margin-top:.24rem;}
                .admin-role-v2-current {
                    position:relative;z-index:1;padding:.62rem .82rem;border-radius:16px;text-align:right;
                    background:rgba(5,9,15,.42);border:1px solid rgba(255,255,255,.08);
                }
                .admin-role-v2-current small {display:block;color:#7F8A9D;font-size:0.75rem /* FIX: minimum 12px agar terbaca di tablet */;font-weight:800;letter-spacing:.1em;text-transform:uppercase;}
                .admin-role-v2-current strong {display:block;color:#FFF;font-size:.82rem;margin-top:.22rem;white-space:nowrap;}

                .admin-role-v2-stepbar {
                    display:grid;grid-template-columns:repeat(3,1fr);gap:.55rem;margin:.2rem 0 1rem;
                }
                .admin-role-v2-step {
                    display:flex;align-items:center;gap:.52rem;padding:.58rem .68rem;border-radius:14px;
                    color:#8F9BAD;font-size:0.75rem /* FIX: minimum 12px agar terbaca di tablet */;font-weight:750;background:rgba(255,255,255,.025);
                    border:1px solid rgba(255,255,255,.065);
                }
                .admin-role-v2-step b {
                    width:24px;height:24px;border-radius:9px;display:flex;align-items:center;justify-content:center;
                    color:#FFF;font-size:0.75rem /* FIX: minimum 12px agar terbaca di tablet */;background:rgba(255,255,255,.08);
                }
                .admin-role-v2-step.active {color:#F8FAFC;border-color:rgba(139,92,246,.28);background:rgba(139,92,246,.09);}
                .admin-role-v2-step.active b {background:linear-gradient(135deg,#E53935,#8B5CF6);box-shadow:0 7px 16px rgba(139,92,246,.20);}

                .admin-role-v2-section-title {color:#FFF;font-size:.92rem;font-weight:900;margin:.18rem 0 .22rem;}
                .admin-role-v2-section-note {color:#8F9BAD;font-size:.78rem;line-height:1.55;margin-bottom:.68rem;}

                div[data-testid="stDialog"] div[role="radiogroup"] {
                    display:grid !important;grid-template-columns:repeat(3,minmax(0,1fr)) !important;
                    gap:.72rem !important;margin-bottom:.15rem !important;
                }
                div[data-testid="stDialog"] div[role="radiogroup"] > label {
                    position:relative;overflow:hidden;min-height:106px !important;padding:.9rem .88rem !important;
                    border-radius:18px !important;border:1px solid rgba(255,255,255,.095) !important;
                    background:linear-gradient(180deg,rgba(255,255,255,.045),rgba(255,255,255,.022)) !important;
                    align-items:flex-start !important;transition:transform .18s ease,border-color .18s ease,box-shadow .18s ease,background .18s ease !important;
                    box-shadow:inset 0 1px 0 rgba(255,255,255,.025);
                }
                div[data-testid="stDialog"] div[role="radiogroup"] > label::after {
                    content:"";position:absolute;inset:auto -18px -24px auto;width:90px;height:90px;border-radius:99px;
                    filter:blur(5px);opacity:.22;transition:opacity .18s ease,transform .18s ease;
                }
                div[data-testid="stDialog"] div[role="radiogroup"] > label:nth-child(1)::after {background:#38BDF8;}
                div[data-testid="stDialog"] div[role="radiogroup"] > label:nth-child(2)::after {background:#8B5CF6;}
                div[data-testid="stDialog"] div[role="radiogroup"] > label:nth-child(3)::after {background:#F97316;}
                div[data-testid="stDialog"] div[role="radiogroup"] > label:hover {
                    transform:translateY(-4px);border-color:rgba(255,255,255,.20) !important;
                    box-shadow:0 18px 30px rgba(0,0,0,.22),inset 0 1px 0 rgba(255,255,255,.05);
                }
                div[data-testid="stDialog"] div[role="radiogroup"] > label:hover::after {opacity:.48;transform:scale(1.08);}
                div[data-testid="stDialog"] div[role="radiogroup"] > label:has(input:checked) {
                    transform:translateY(-3px);
                    border-color:rgba(236,72,153,.58) !important;
                    background:linear-gradient(145deg,rgba(229,57,53,.15),rgba(139,92,246,.16)) !important;
                    box-shadow:0 18px 36px rgba(139,92,246,.20),inset 0 0 0 1px rgba(255,255,255,.045);
                }
                div[data-testid="stDialog"] div[role="radiogroup"] > label:has(input:checked)::before {
                    content:"TERPILIH";position:absolute;right:.6rem;top:.55rem;padding:.2rem .42rem;border-radius:999px;
                    color:#FFF;font-size:0.75rem /* FIX: minimum 12px agar terbaca di tablet */;font-weight:900;letter-spacing:.08em;
                    background:linear-gradient(90deg,#E53935,#A855F7);box-shadow:0 6px 14px rgba(139,92,246,.26);
                }
                div[data-testid="stDialog"] div[role="radiogroup"] p {
                    color:#F8FAFC !important;font-size:.83rem !important;font-weight:850 !important;line-height:1.35 !important;
                    position:relative;z-index:2;margin-top:.05rem !important;
                }
                div[data-testid="stDialog"] div[role="radiogroup"] input[type="radio"] {accent-color:#F43F5E;}

                .admin-role-v2-preview {
                    position:relative;overflow:hidden;display:grid;grid-template-columns:auto 1fr;gap:.85rem;
                    padding:.92rem 1rem;margin:.88rem 0 .82rem;border-radius:19px;
                    border:1px solid var(--role-border);background:linear-gradient(135deg,var(--role-soft),rgba(255,255,255,.025));
                    box-shadow:0 14px 28px rgba(0,0,0,.16),inset 0 1px 0 rgba(255,255,255,.035);
                }
                .admin-role-v2-preview-icon {
                    width:46px;height:46px;border-radius:15px;display:flex;align-items:center;justify-content:center;
                    font-size:1.1rem;background:var(--role-soft);border:1px solid var(--role-border);color:#FFF;
                }
                .admin-role-v2-preview-title {color:#FFF;font-size:.94rem;font-weight:900;}
                .admin-role-v2-preview-copy {color:#ABB6C8;font-size:.78rem;line-height:1.55;margin-top:.18rem;}
                .admin-role-v2-chip-row {display:flex;gap:.38rem;flex-wrap:wrap;margin-top:.48rem;}
                .admin-role-v2-chip {
                    padding:.3rem .52rem;border-radius:999px;color:#F8FAFC;font-size:0.75rem /* FIX: minimum 12px agar terbaca di tablet */;font-weight:800;
                    border:1px solid var(--role-border);background:rgba(4,8,14,.28);
                }
                .admin-role-v2-impact {
                    display:flex;align-items:center;gap:.55rem;padding:.62rem .72rem;margin:.12rem 0 .82rem;
                    border-radius:14px;color:#C5CEDB;font-size:0.75rem /* FIX: minimum 12px agar terbaca di tablet */;line-height:1.5;
                    background:rgba(245,158,11,.07);border:1px solid rgba(245,158,11,.17);
                }
                .admin-role-v2-impact b {color:#FBBF24;}

                div[data-testid="stDialog"] .stButton > button {
                    min-height:52px !important;border-radius:15px !important;font-weight:850 !important;
                    transition:transform .16s ease,box-shadow .16s ease,border-color .16s ease !important;
                }
                div[data-testid="stDialog"] .stButton > button:hover:not(:disabled) {transform:translateY(-2px);}
                div[data-testid="stDialog"] button[kind="primary"] {
                    color:#FFF !important;border-color:rgba(255,255,255,.08) !important;
                    background:linear-gradient(100deg,#E53935,#D946EF 52%,#8B5CF6) !important;
                    box-shadow:0 14px 28px rgba(217,70,239,.20) !important;
                }
                div[data-testid="stDialog"] button[kind="primary"]:hover:not(:disabled) {
                    box-shadow:0 18px 34px rgba(217,70,239,.30) !important;
                }
                div[data-testid="stDialog"] button:disabled {opacity:.42 !important;filter:saturate(.35);}

                @media(max-width:700px) {
                    .admin-role-v2-hero {grid-template-columns:auto 1fr;}
                    .admin-role-v2-current {grid-column:1/-1;text-align:left;}
                    .admin-role-v2-stepbar {grid-template-columns:1fr;}
                    div[data-testid="stDialog"] div[role="radiogroup"] {grid-template-columns:1fr !important;}
                }
                @media(prefers-reduced-motion:reduce) {
                    .admin-role-v2-hero::after,.admin-role-v2-avatar,div[data-testid="stDialog"] > div[role="dialog"]::before {animation:none !important;}
                    div[data-testid="stDialog"] * {transition:none !important;}
                }
            </style>
            """,
            unsafe_allow_html=True,
        )

        initials = "".join(
            part[0] for part in str(fullname or username).split()[:2] if part
        ).upper() or "U"
        current_label = get_role_label(current_role_normalized, user_id)
        st.markdown(
            f"""
            <div class="admin-role-v2-eyebrow"><span></span>PENGATURAN HAK AKSES AKUN</div>
            <div class="admin-role-v2-hero">
                <div class="admin-role-v2-avatar">{escape(initials)}</div>
                <div>
                    <div class="admin-role-v2-name">{escape(str(fullname or username))}</div>
                    <div class="admin-role-v2-handle">@{escape(str(username))} · ID pengguna #{int(user_id)}</div>
                </div>
                <div class="admin-role-v2-current">
                    <small>Role saat ini</small>
                    <strong>{escape(get_role_icon(current_role_normalized, user_id))} {escape(current_label)}</strong>
                </div>
            </div>
            <div class="admin-role-v2-stepbar">
                <div class="admin-role-v2-step"><b>1</b>Akun dipilih</div>
                <div class="admin-role-v2-step active"><b>2</b>Tentukan role</div>
                <div class="admin-role-v2-step"><b>3</b>Konfirmasi perubahan</div>
            </div>
            <div class="admin-role-v2-section-title">Pilih role tujuan</div>
            <div class="admin-role-v2-section-note">Pilih satu hak akses yang paling sesuai. Perubahan belum diterapkan sebelum tombol Simpan Role ditekan.</div>
            """,
            unsafe_allow_html=True,
        )

        role_options = list(VALID_ROLES)
        selected_role = st.radio(
            "Pilih role tujuan",
            options=role_options,
            index=role_options.index(current_role_normalized),
            format_func=lambda role_value: (
                f"{get_role_icon(role_value)}  {get_role_label(role_value)}"
            ),
            key=f"admin_selected_role_{user_id}",
            horizontal=True,
            label_visibility="collapsed",
        )

        selected_theme = role_theme.get(selected_role, role_theme["data_analyst"])
        access_html = "".join(
            f'<span class="admin-role-v2-chip">{escape(item)}</span>'
            for item in selected_theme["access"]
        )
        st.markdown(
            f"""
            <div class="admin-role-v2-preview"
                 style="--role-soft:{selected_theme['soft']};--role-border:{selected_theme['border']};">
                <div class="admin-role-v2-preview-icon">{escape(selected_theme['icon'])}</div>
                <div>
                    <div class="admin-role-v2-preview-title">Akses {escape(selected_theme['label'])}</div>
                    <div class="admin-role-v2-preview-copy">{escape(ROLE_DESCRIPTIONS.get(selected_role, 'Hak akses mengikuti konfigurasi role dashboard.'))}</div>
                    <div class="admin-role-v2-chip-row">{access_html}</div>
                </div>
            </div>
            <div class="admin-role-v2-impact"><b>ℹ</b> Perubahan role akan langsung memengaruhi menu dan halaman yang dapat diakses pengguna pada sesi berikutnya.</div>
            """,
            unsafe_allow_html=True,
        )

        cancel_col, save_col = st.columns([1, 1.55], gap="medium")
        with cancel_col:
            if st.button(
                "← Batal",
                key=f"cancel_role_dialog_{user_id}",
                use_container_width=True,
            ):
                st.rerun()
        with save_col:
            save_clicked = st.button(
                "✓ Simpan Role",
                key=f"save_role_dialog_{user_id}",
                type="primary",
                use_container_width=True,
                disabled=selected_role == current_role_normalized,
                help=(
                    "Pilih role yang berbeda terlebih dahulu."
                    if selected_role == current_role_normalized
                    else f"Ubah role menjadi {get_role_label(selected_role)}"
                ),
            )

        if save_clicked:
            if username_normalized in LOCKED_DEFAULT_USERNAMES:
                _set_flash_message(
                    "error",
                    "Role akun default admin, manajemen, dan sosmed_officer tidak dapat diubah.",
                )
            else:
                success, message = update_user_role(user_id, selected_role)
                log_activity(
                    "CHANGE_ROLE",
                    "Admin Panel",
                    (
                        f"Role akun @{username} diubah dari {current_role_normalized} menjadi {selected_role}."
                        if success
                        else f"Perubahan role akun @{username} gagal."
                    ),
                    status="success" if success else "failed",
                    metadata={
                        "target_user_id": user_id,
                        "target_username": username,
                        "old_role": current_role_normalized,
                        "new_role": selected_role,
                        "result": message,
                    },
                )
                _set_flash_message("success" if success else "error", message)
            st.rerun()
    except Exception as error:
        st.error(f"Dialog perubahan role tidak dapat ditampilkan: {error}")


def _render_user_table(users: list[dict], current_user_id: int) -> None:
    """Tampilkan daftar pengguna sebagai kartu akses yang rapi dan responsif."""
    try:
        if not users:
            st.markdown(
                '<div class="admin-v3-empty">🔎 Tidak ada pengguna yang cocok dengan pencarian atau filter.</div>',
                unsafe_allow_html=True,
            )
            return

        st.markdown(
            f"""
            <div class="admin-v6-list-head">
                <div class="admin-v6-list-copy">
                    <div class="admin-v6-list-icon">☷</div>
                    <div>
                        <div class="admin-v6-list-title">Daftar Akun Terfilter</div>
                        <div class="admin-v6-list-note">Setiap kartu menampilkan identitas, hak akses, metadata akun, dan tindakan administrasi.</div>
                    </div>
                </div>
                <div class="admin-v6-count-pill"><i></i>{len(users)} akun ditemukan</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        for index, user in enumerate(users):
            user_id = int(user.get("user_id", 0))
            role = normalize_role(user.get("role", DEFAULT_ROLE), user_id)
            role_text = str(role).lower()
            is_main_admin = user_id == 1
            is_current_account = user_id == current_user_id
            username_normalized = username_display = str(user.get("username", "-") or "-").strip()
            is_default_account = username_normalized.lower() in LOCKED_DEFAULT_USERNAMES
            role_action_disabled = is_default_account
            delete_action_disabled = is_default_account or is_main_admin or is_current_account

            if role == ROLE_DATA_ANALYST:
                role_class = "admin-v6-card-analyst"
            elif "manag" in role_text:
                role_class = "admin-v6-card-management"
            else:
                role_class = "admin-v6-card-social"

            fullname_display = str(user.get("fullname", "-") or "-")
            email_display = str(user.get("email", "-") or "-")
            created_display = format_created_at(user.get("created_at"))
            initials = "".join(part[0] for part in fullname_display.split()[:2] if part).upper() or "U"
            role_icon = get_role_icon(role, user_id)
            role_label_current = get_role_label(role, user_id)

            if is_default_account:
                account_note = "Role akun default dikunci"
            elif is_current_account:
                account_note = "Sedang digunakan"
            else:
                account_note = "Akun dapat dikelola"

            role_disable_reason = (
                "Role akun default admin, manajemen, dan sosmed_officer tidak dapat diubah."
                if is_default_account
                else None
            )
            delete_disable_reason = None
            if is_default_account:
                delete_disable_reason = (
                    "Akun default admin, manajemen, dan sosmed_officer tidak dapat dihapus."
                )
            elif is_main_admin:
                delete_disable_reason = "Data Analis utama tidak dapat dihapus."
            elif is_current_account:
                delete_disable_reason = "Akun yang sedang digunakan tidak dapat dihapus."

            with st.container(border=True):
                st.markdown(
                    f'<span class="admin-v6-user-card-marker {role_class}" style="--card-index:{index}"></span>',
                    unsafe_allow_html=True,
                )
                st.markdown(
                    f"""
                    <div class="admin-v6-card-top">
                        <div class="admin-v6-identity">
                            <div class="admin-v6-avatar">{escape(initials)}</div>
                            <div class="admin-v6-name-wrap">
                                <div class="admin-v6-name">{escape(fullname_display)}</div>
                                <div class="admin-v6-handle">@{escape(username_display)}</div>
                                <div class="admin-v6-account-note"><i></i>{escape(account_note)}</div>
                            </div>
                        </div>
                        <div class="admin-v6-access-stack">
                            <span class="admin-v6-role-pill">{role_icon} {escape(role_label_current)}</span>
                            <span class="admin-v6-access-note">Hak akses akun</span>
                        </div>
                    </div>
                    <div class="admin-v6-meta-grid">
                        <div class="admin-v6-meta-item">
                            <div class="admin-v6-meta-label">ID Pengguna</div>
                            <div class="admin-v6-meta-value">#{user_id}</div>
                        </div>
                        <div class="admin-v6-meta-item">
                            <div class="admin-v6-meta-label">Username</div>
                            <div class="admin-v6-meta-value">{escape(username_display)}</div>
                        </div>
                        <div class="admin-v6-meta-item" title="{escape(email_display)}">
                            <div class="admin-v6-meta-label">Alamat Email</div>
                            <div class="admin-v6-meta-value">{escape(email_display)}</div>
                        </div>
                        <div class="admin-v6-meta-item">
                            <div class="admin-v6-meta-label">Dibuat</div>
                            <div class="admin-v6-meta-value">{escape(created_display)}</div>
                        </div>
                    </div>
                    <div class="admin-v6-card-divider"></div>
                    """,
                    unsafe_allow_html=True,
                )

                spacer_col, label_col, role_col, delete_col = st.columns([4.4, 1.35, 1.25, 1.25], gap="small")
                with spacer_col:
                    st.empty()
                with label_col:
                    st.markdown('<div class="admin-v6-action-label">Tindakan akun</div>', unsafe_allow_html=True)
                with role_col:
                    st.markdown('<span class="admin-v6-role-action-marker"></span>', unsafe_allow_html=True)
                    change_clicked = st.button(
                        "↻ Ubah Role",
                        key=f"change_role_user_{user_id}",
                        help=(
                            role_disable_reason
                            if role_action_disabled
                            else "Buka pilihan role untuk akun ini"
                        ),
                        disabled=role_action_disabled,
                        use_container_width=True,
                        type="primary",
                    )
                with delete_col:
                    st.markdown('<span class="admin-v6-delete-action-marker"></span>', unsafe_allow_html=True)
                    delete_clicked = st.button(
                        "⌫ Hapus",
                        key=f"request_delete_user_{user_id}",
                        help=(
                            delete_disable_reason
                            if delete_action_disabled
                            else f"Hapus akun {username_display}"
                        ),
                        disabled=delete_action_disabled,
                        use_container_width=True,
                    )

                if change_clicked:
                    if username_normalized.lower() in LOCKED_DEFAULT_USERNAMES:
                        _set_flash_message(
                            "error",
                            "Role akun default admin, manajemen, dan sosmed_officer tidak dapat diubah.",
                        )
                        st.rerun()
                    else:
                        _render_change_role_dialog(
                            user_id=user_id,
                            username=username_display,
                            fullname=fullname_display,
                            current_role=role,
                        )

                if delete_clicked:
                    if username_normalized.lower() in LOCKED_DEFAULT_USERNAMES:
                        _set_flash_message(
                            "error",
                            "Akun default admin, manajemen, dan sosmed_officer tidak dapat dihapus.",
                        )
                        st.rerun()
                    st.session_state[DELETE_TARGET_KEY] = {
                        "user_id": user_id,
                        "username": username_display,
                        "fullname": fullname_display,
                    }
                    st.session_state[DELETE_SCROLL_PENDING_KEY] = True
                    st.rerun()
    except Exception as error:
        st.error(f"Gagal menampilkan daftar pengguna: {error}")

def _render_create_user_form() -> None:
    """Tampilkan form tambah pengguna baru di dalam expander."""
    try:
        with st.expander("➕ Tambah Pengguna Baru", expanded=False):
            st.caption("Buat akun baru dan tentukan hak aksesnya langsung dari Admin Panel.")
            with st.form("admin_create_user_form", clear_on_submit=False):
                left_column, right_column = st.columns(2, gap="large")
                with left_column:
                    fullname = st.text_input("Nama Lengkap", placeholder="Contoh: Aulia Rahmadiva Wardana")
                    username = st.text_input("Username", placeholder="Contoh: aulia.rahmadiva")
                    role = st.selectbox(
                        "Role",
                        options=list(VALID_ROLES),
                        format_func=get_role_label,
                    )
                with right_column:
                    email = st.text_input("Email", placeholder="Contoh: nama@email.com")
                    password = st.text_input("Password", type="password", placeholder="Minimal 8 karakter")
                    confirm_password = st.text_input("Konfirmasi Password", type="password", placeholder="Ketik ulang password")

                submitted = st.form_submit_button("✨ Buat Akun Pengguna", type="primary", use_container_width=True)
                if submitted:
                    is_valid, validation_message = _validate_new_user(fullname, username, email, password)
                    if not is_valid:
                        st.error(validation_message)
                        return
                    if password != confirm_password:
                        st.error("Konfirmasi password tidak sama dengan password.")
                        return

                    success, message = admin_create_user(fullname, username, email, password, role)
                    log_activity(
                        "CREATE_USER",
                        "Admin Panel",
                        (
                            f"Administrator membuat akun baru @{username.strip().lower()}."
                            if success
                            else f"Pembuatan akun @{username.strip().lower()} gagal."
                        ),
                        status="success" if success else "failed",
                        metadata={
                            "target_username": username.strip().lower(),
                            "target_role": role,
                            "result": message,
                        },
                    )
                    _set_flash_message("success" if success else "error", message)
                    st.rerun()
    except Exception as error:
        st.error(f"Gagal menampilkan form tambah pengguna: {error}")


def _render_user_management_tab() -> None:
    """Render tab manajemen pengguna dan seluruh aksi CRUD admin."""
    try:
        _render_section_header(
            "👥",
            "Manajemen Pengguna",
            "Cari akun, ubah hak akses, hapus akun yang tidak digunakan, atau tambahkan pengguna baru.",
            "purple",
        )
        _show_flash_message()

        current_user_id = int(st.session_state.get("user_id", 0) or 0)
        users = get_all_users()
        stats = get_user_stats()

        _render_metric_cards(
            [
                {"icon": "👥", "label": "Total Pengguna", "value": stats.get("total_users", len(users)), "color": "#E53935"},
                {"icon": "🛡️", "label": "Data Analis", "value": stats.get("total_data_analyst", 0), "color": "#AB47BC"},
                {"icon": "💼", "label": "Manajemen", "value": stats.get("total_management", 0), "color": "#1DA1F2"},
                {"icon": "📣", "label": "Sosmed Officer", "value": stats.get("total_social_media_officer", 0), "color": "#FF9800"},
            ]
        )

        st.markdown(
            """
            <section class="admin-v5-directory-head" tabindex="0">
                <div class="admin-v5-directory-copy">
                    <div class="admin-v5-directory-icon">⌕</div>
                    <div>
                        <div class="admin-v5-directory-title">Direktori Akses Pengguna</div>
                        <div class="admin-v5-directory-note">Cari identitas akun, saring berdasarkan role, lalu kelola hak akses secara aman dari satu tempat.</div>
                    </div>
                </div>
                <div class="admin-v5-role-legend">
                    <span class="admin-v5-legend-pill" style="--legend-accent:#FF625E"><i></i>Data Analis</span>
                    <span class="admin-v5-legend-pill" style="--legend-accent:#42A5F5"><i></i>Manajemen</span>
                    <span class="admin-v5-legend-pill" style="--legend-accent:#FFB74D"><i></i>Sosmed Officer</span>
                </div>
            </section>
            """,
            unsafe_allow_html=True,
        )

        search_col, role_col = st.columns([2.2, 1], gap="medium")
        with search_col:
            keyword = st.text_input(
                "Cari Pengguna",
                placeholder="Ketik nama, username, email, role, atau ID...",
                key="admin_user_search",
            )
        with role_col:
            role_filter = st.selectbox(
                "Filter Role",
                options=["Semua Role", *VALID_ROLES],
                format_func=(
                    lambda value: value
                    if value == "Semua Role"
                    else get_role_label(value)
                ),
                key="admin_role_filter",
            )

        filtered_users = _filter_users(users, keyword, role_filter)
        st.markdown(
            f'<div class="admin-v3-toolbar-note">Menampilkan <strong>{len(filtered_users)}</strong> dari <strong>{len(users)}</strong> akun. Tombol aksi dinonaktifkan untuk Data Analis utama dan akun yang sedang dipakai.</div>',
            unsafe_allow_html=True,
        )

        _render_delete_confirmation(current_user_id)
        _render_user_table(filtered_users, current_user_id)
        st.markdown('<div style="height:.45rem"></div>', unsafe_allow_html=True)
        _render_create_user_form()
    except Exception as error:
        st.error(f"Gagal memuat manajemen pengguna: {error}")


@st.cache_data(ttl=60)
def _load_manual_analysis_history_cached(
    history_path_text: str,
    modified_ns: int,
) -> pd.DataFrame:
    """Baca riwayat prediksi manual yang tersimpan per akun secara aman."""
    del modified_ns  # Dipakai sebagai cache-buster saat isi file berubah.
    columns = [
        "owner_key",
        "activity_at",
        "sentiment",
        "confidence",
        "text",
    ]
    try:
        history_path = Path(history_path_text)
        if not history_path.is_file():
            return pd.DataFrame(columns=columns)

        payload = json.loads(history_path.read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            return pd.DataFrame(columns=columns)

        rows: list[dict] = []
        for owner_key, activities in payload.items():
            if not isinstance(owner_key, str) or not isinstance(activities, list):
                continue
            for item in activities:
                if not isinstance(item, dict):
                    continue
                parsed_at = pd.to_datetime(
                    item.get("Waktu"),
                    format="%d-%m-%Y %H:%M:%S",
                    errors="coerce",
                )
                if pd.isna(parsed_at):
                    parsed_at = pd.to_datetime(item.get("id"), errors="coerce")
                rows.append(
                    {
                        "owner_key": owner_key,
                        "activity_at": parsed_at,
                        "sentiment": str(item.get("Sentimen") or "Tidak diketahui"),
                        "confidence": str(item.get("Confidence") or "-"),
                        "text": str(item.get("Teks") or "").strip(),
                    }
                )

        frame = pd.DataFrame(rows, columns=columns)
        if frame.empty:
            return frame
        frame = frame.dropna(subset=["activity_at"]).sort_values(
            "activity_at", ascending=False
        )
        return frame.reset_index(drop=True)
    except Exception:
        return pd.DataFrame(columns=columns)


def _load_user_activity_data(users: list[dict]) -> pd.DataFrame:
    """Gabungkan riwayat analisis manual dengan identitas akun yang tersedia."""
    try:
        history_path = PROJECT_ROOT / "data" / "manual_prediction_history.json"
        modified_ns = history_path.stat().st_mtime_ns if history_path.is_file() else 0
        history = _load_manual_analysis_history_cached(
            str(history_path),
            modified_ns,
        )
        if history.empty:
            return history.assign(
                user_id=pd.Series(dtype="Int64"),
                username=pd.Series(dtype="object"),
                fullname=pd.Series(dtype="object"),
                role=pd.Series(dtype="object"),
            )

        users_by_id = {
            int(user.get("user_id")): user
            for user in users
            if user.get("user_id") not in (None, "")
        }
        users_by_username = {
            str(user.get("username") or "").strip().lower(): user
            for user in users
            if str(user.get("username") or "").strip()
        }

        identity_rows: list[dict] = []
        for owner_key in history["owner_key"].astype(str):
            user = None
            resolved_user_id = None
            if owner_key.startswith("user_id:"):
                try:
                    resolved_user_id = int(owner_key.split(":", 1)[1])
                    user = users_by_id.get(resolved_user_id)
                except (TypeError, ValueError):
                    user = None
            elif owner_key.startswith("username:"):
                username_key = owner_key.split(":", 1)[1].strip().lower()
                user = users_by_username.get(username_key)

            if user:
                identity_rows.append(
                    {
                        "user_id": int(user.get("user_id") or 0),
                        "username": str(user.get("username") or "-").strip(),
                        "fullname": str(user.get("fullname") or user.get("username") or "Pengguna"),
                        "role": normalize_role(user.get("role"), user.get("user_id")),
                    }
                )
            else:
                identity_rows.append(
                    {
                        "user_id": resolved_user_id,
                        "username": owner_key.replace("user_id:", "akun-").replace("username:", ""),
                        "fullname": "Akun tidak ditemukan",
                        "role": DEFAULT_ROLE,
                    }
                )

        identity = pd.DataFrame(identity_rows)
        return pd.concat(
            [history.reset_index(drop=True), identity.reset_index(drop=True)], axis=1
        )
    except Exception as error:
        st.error(f"Gagal membaca aktivitas analisis pengguna: {error}")
        return pd.DataFrame()


def _activity_period_days(period_label: str) -> int | None:
    """Ubah pilihan rentang waktu menjadi jumlah hari."""
    return {
        "7 Hari": 7,
        "30 Hari": 30,
        "90 Hari": 90,
        "Semua Waktu": None,
    }.get(period_label, 30)


def _format_activity_time(value) -> str:
    """Format waktu aktivitas ke bentuk Indonesia yang ringkas."""
    try:
        parsed = pd.to_datetime(value, errors="coerce")
        if pd.isna(parsed):
            return "Waktu tidak tersedia"
        return parsed.strftime("%d %b %Y · %H:%M")
    except Exception:
        return "Waktu tidak tersedia"


def _render_user_activity_analytics(
    users: list[dict],
    status_table: pd.DataFrame,
) -> None:
    """Render dashboard aktivitas pengguna seperti insight media sosial."""
    try:
        activity = _load_user_activity_data(users)
        filter_col, source_col = st.columns([1, 2.4], gap="medium")
        with filter_col:
            period_label = st.selectbox(
                "Rentang Aktivitas",
                options=["7 Hari", "30 Hari", "90 Hari", "Semua Waktu"],
                index=1,
                key="admin_activity_period",
            )
        with source_col:
            st.markdown(
                '<div class="admin-v7-source-note"><b>Sumber data aktual</b><span>Registrasi dari database pengguna dan aktivitas dari riwayat prediksi sentimen manual.</span></div>',
                unsafe_allow_html=True,
            )

        period_days = _activity_period_days(period_label)
        now = pd.Timestamp.now()
        cutoff = now.normalize() - pd.Timedelta(days=period_days - 1) if period_days else None

        registration_rows: list[dict] = []
        for user in users:
            created_at = _parse_created_at(user.get("created_at"))
            if created_at is None:
                continue
            if cutoff is not None and created_at < cutoff:
                continue
            registration_rows.append(
                {
                    "activity_at": created_at,
                    "username": str(user.get("username") or "-"),
                    "fullname": str(user.get("fullname") or user.get("username") or "Pengguna"),
                    "role": normalize_role(user.get("role"), user.get("user_id")),
                    "user_id": user.get("user_id"),
                }
            )
        registrations = pd.DataFrame(registration_rows)

        filtered_activity = activity.copy()
        if not filtered_activity.empty and cutoff is not None:
            filtered_activity = filtered_activity[
                filtered_activity["activity_at"] >= cutoff
            ].copy()

        total_registrations = len(registrations)
        total_analyses = len(filtered_activity)
        active_analysts = (
            int(filtered_activity["owner_key"].nunique())
            if not filtered_activity.empty
            else 0
        )
        latest_analysis = (
            _format_activity_time(filtered_activity.iloc[0]["activity_at"])
            if not filtered_activity.empty
            else "Belum ada"
        )

        latest_user = None
        if registration_rows:
            latest_user = max(
                registration_rows,
                key=lambda row: pd.Timestamp(row["activity_at"]),
            )
        elif users:
            valid_users = [
                user for user in users if _parse_created_at(user.get("created_at")) is not None
            ]
            if valid_users:
                latest_user = max(
                    valid_users,
                    key=lambda user: _parse_created_at(user.get("created_at")),
                )

        latest_name = (
            str(latest_user.get("fullname") or latest_user.get("username") or "-")
            if latest_user
            else "Belum ada"
        )

        st.markdown(
            """
            <style>
                @keyframes adminV7PulseDot {
                    0%, 100% { box-shadow: 0 0 0 0 rgba(76,217,137,.30); }
                    50% { box-shadow: 0 0 0 8px rgba(76,217,137,0); }
                }
                @keyframes adminV7Sweep {
                    0% { transform: translateX(-140%) skewX(-18deg); opacity: 0; }
                    20% { opacity: .45; }
                    100% { transform: translateX(350%) skewX(-18deg); opacity: 0; }
                }
                .admin-v7-source-note {
                    align-items: center;
                    background: linear-gradient(135deg, rgba(29,161,242,.10), rgba(142,90,247,.08));
                    border: 1px solid rgba(66,165,245,.20);
                    border-radius: 15px;
                    display: flex;
                    gap: .65rem;
                    min-height: 53px;
                    padding: .72rem .9rem;
                }
                .admin-v7-source-note b { color:#79C8FF; font-size:.76rem; white-space:nowrap; }
                .admin-v7-source-note span { color:#AAB5C7; font-size:0.75rem /* FIX: minimum 12px agar terbaca di tablet */; line-height:1.45; }
                .admin-v7-kpi-grid { display:grid; gap:.82rem; grid-template-columns:repeat(4,minmax(0,1fr)); margin:.45rem 0 1rem; }
                .admin-v7-kpi {
                    background: linear-gradient(145deg, color-mix(in srgb,var(--v7-accent) 12%,#0D1422), #0A101B 75%);
                    border:1px solid color-mix(in srgb,var(--v7-accent) 32%,transparent);
                    border-radius:18px;
                    box-shadow:0 14px 28px rgba(0,0,0,.18);
                    min-height:126px;
                    overflow:hidden;
                    padding:1rem;
                    position:relative;
                    transition:transform .22s ease,box-shadow .22s ease,border-color .22s ease;
                }
                .admin-v7-kpi:hover { border-color:color-mix(in srgb,var(--v7-accent) 58%,transparent); box-shadow:0 20px 38px color-mix(in srgb,var(--v7-accent) 14%,transparent); transform:translateY(-4px); }
                .admin-v7-kpi::after { animation:adminV7Sweep 7s linear infinite; background:linear-gradient(100deg,transparent,rgba(255,255,255,.10),transparent); content:''; inset:0 auto 0 -45%; position:absolute; width:35%; }
                .admin-v7-kpi-label { color:#9EABC0; font-size:0.75rem /* FIX: minimum 12px agar terbaca di tablet */; font-weight:800; letter-spacing:.08em; text-transform:uppercase; }
                .admin-v7-kpi-value { color:#FFFFFF; font-size:1.52rem; font-weight:850; line-height:1.1; margin-top:.48rem; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }
                .admin-v7-kpi-note { color:#B7C0D0; font-size:0.75rem /* FIX: minimum 12px agar terbaca di tablet */; line-height:1.45; margin-top:.42rem; }
                .admin-v7-kpi-dot { animation:adminV7PulseDot 2s ease-in-out infinite; background:var(--v7-accent); border-radius:50%; height:8px; position:absolute; right:1rem; top:1rem; width:8px; }
                .admin-v7-panel {
                    background:linear-gradient(145deg,rgba(15,23,38,.96),rgba(8,14,25,.98));
                    border:1px solid rgba(255,255,255,.09);
                    border-radius:20px;
                    box-shadow:0 16px 34px rgba(0,0,0,.18);
                    min-height:100%;
                    overflow:hidden;
                    padding:1rem;
                    position:relative;
                }
                .admin-v7-panel-head { align-items:center; display:flex; gap:.7rem; justify-content:space-between; margin-bottom:.8rem; }
                .admin-v7-panel-title { color:#FFFFFF; font-size:.92rem; font-weight:850; }
                .admin-v7-panel-badge { background:rgba(255,255,255,.05); border:1px solid rgba(255,255,255,.09); border-radius:999px; color:#AEB8C9; font-size:0.75rem /* FIX: minimum 12px agar terbaca di tablet */; font-weight:800; padding:.35rem .58rem; }
                .admin-v7-person {
                    align-items:center;
                    background:rgba(255,255,255,.035);
                    border:1px solid rgba(255,255,255,.07);
                    border-radius:14px;
                    display:grid;
                    gap:.72rem;
                    grid-template-columns:42px minmax(0,1fr) auto;
                    margin-bottom:.58rem;
                    padding:.65rem .72rem;
                    transition:transform .18s ease,border-color .18s ease,background .18s ease;
                }
                .admin-v7-person:hover { background:rgba(255,255,255,.06); border-color:rgba(66,165,245,.24); transform:translateX(3px); }
                .admin-v7-avatar { align-items:center; background:linear-gradient(135deg,#E53935,#8E5AF7); border-radius:13px; color:white; display:flex; font-size:.75rem; font-weight:900; height:42px; justify-content:center; width:42px; }
                .admin-v7-person-name { color:#F7F9FC; font-size:.76rem; font-weight:800; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }
                .admin-v7-person-meta { color:#8F9BAF; font-size:0.75rem /* FIX: minimum 12px agar terbaca di tablet */; line-height:1.45; margin-top:.15rem; }
                .admin-v7-person-value { color:#79C8FF; font-size:0.75rem /* FIX: minimum 12px agar terbaca di tablet */; font-weight:850; text-align:right; white-space:nowrap; }
                .admin-v7-sentiment { border-radius:999px; display:inline-flex; font-size:0.75rem /* FIX: minimum 12px agar terbaca di tablet */; font-weight:850; margin-top:.24rem; padding:.25rem .45rem; }
                .admin-v7-sentiment.positif { background:rgba(76,175,80,.13); border:1px solid rgba(76,175,80,.25); color:#75E087; }
                .admin-v7-sentiment.netral { background:rgba(255,152,0,.13); border:1px solid rgba(255,152,0,.25); color:#FFBD63; }
                .admin-v7-sentiment.negatif { background:rgba(244,67,54,.13); border:1px solid rgba(244,67,54,.25); color:#FF827E; }
                .admin-v7-empty { border:1px dashed rgba(255,255,255,.12); border-radius:14px; color:#8E99AB; font-size:0.75rem /* FIX: minimum 12px agar terbaca di tablet */; padding:1.2rem; text-align:center; }
                @media(max-width:980px){ .admin-v7-kpi-grid{grid-template-columns:repeat(2,minmax(0,1fr));} }
                @media(max-width:560px){ .admin-v7-kpi-grid{grid-template-columns:1fr;} .admin-v7-source-note{align-items:flex-start;flex-direction:column;} }
            </style>
            """,
            unsafe_allow_html=True,
        )

        kpi_html = (
            '<div class="admin-v7-kpi-grid">'
            f'<div class="admin-v7-kpi" tabindex="0" style="--v7-accent:#29B6F6"><i class="admin-v7-kpi-dot"></i><div class="admin-v7-kpi-label">Siapa yang baru daftar</div><div class="admin-v7-kpi-value">{escape(latest_name)}</div><div class="admin-v7-kpi-note">{total_registrations} registrasi pada {escape(period_label.lower())}</div></div>'
            f'<div class="admin-v7-kpi" tabindex="0" style="--v7-accent:#8E5AF7"><i class="admin-v7-kpi-dot"></i><div class="admin-v7-kpi-label">Siapa yang melakukan analisis</div><div class="admin-v7-kpi-value">{active_analysts} akun</div><div class="admin-v7-kpi-note">Akun unik dengan riwayat prediksi manual</div></div>'
            f'<div class="admin-v7-kpi" tabindex="0" style="--v7-accent:#FF4D48"><i class="admin-v7-kpi-dot"></i><div class="admin-v7-kpi-label">Total aktivitas analisis</div><div class="admin-v7-kpi-value">{total_analyses}</div><div class="admin-v7-kpi-note">Prediksi manual yang tersimpan pada periode aktif</div></div>'
            f'<div class="admin-v7-kpi" tabindex="0" style="--v7-accent:#35D07F"><i class="admin-v7-kpi-dot"></i><div class="admin-v7-kpi-label">Aktivitas terakhir</div><div class="admin-v7-kpi-value" style="font-size:1rem">{escape(latest_analysis)}</div><div class="admin-v7-kpi-note">Waktu analisis terbaru yang tercatat</div></div>'
            '</div>'
        )
        st.markdown(kpi_html, unsafe_allow_html=True)

        trend_col, leaderboard_col = st.columns([1.75, 1], gap="large")
        with trend_col:
            dates: list[pd.Timestamp] = []
            if cutoff is not None:
                dates = list(pd.date_range(cutoff, now.normalize(), freq="D"))
            else:
                candidates = []
                if not registrations.empty:
                    candidates.extend(pd.to_datetime(registrations["activity_at"]).tolist())
                if not filtered_activity.empty:
                    candidates.extend(pd.to_datetime(filtered_activity["activity_at"]).tolist())
                if candidates:
                    start_date = min(candidates).normalize()
                    dates = list(pd.date_range(start_date, now.normalize(), freq="D"))

            if dates:
                trend = pd.DataFrame({"Tanggal": dates})
                trend["Registrasi"] = 0
                trend["Analisis"] = 0
                if not registrations.empty:
                    reg_counts = (
                        pd.to_datetime(registrations["activity_at"])
                        .dt.normalize()
                        .value_counts()
                    )
                    trend["Registrasi"] = trend["Tanggal"].map(reg_counts).fillna(0).astype(int)
                if not filtered_activity.empty:
                    analysis_counts = (
                        pd.to_datetime(filtered_activity["activity_at"])
                        .dt.normalize()
                        .value_counts()
                    )
                    trend["Analisis"] = trend["Tanggal"].map(analysis_counts).fillna(0).astype(int)

                figure = go.Figure()
                figure.add_trace(
                    go.Bar(
                        x=trend["Tanggal"],
                        y=trend["Registrasi"],
                        name="Registrasi",
                        marker_color="#29B6F6",
                        hovertemplate="%{x|%d %b %Y}<br>Registrasi: %{y}<extra></extra>",
                    )
                )
                figure.add_trace(
                    go.Scatter(
                        x=trend["Tanggal"],
                        y=trend["Analisis"],
                        name="Analisis manual",
                        mode="lines+markers",
                        line=dict(color="#FF4D48", width=3),
                        marker=dict(size=8, color="#FF4D48"),
                        fill="tozeroy",
                        fillcolor="rgba(255,77,72,.10)",
                        hovertemplate="%{x|%d %b %Y}<br>Analisis: %{y}<extra></extra>",
                    )
                )
                figure.update_layout(
                    title="Pertumbuhan Registrasi & Aktivitas Analisis",
                    barmode="group",
                    hovermode="x unified",
                    height=390,
                    margin=dict(l=18, r=18, t=65, b=18),
                    paper_bgcolor="rgba(0,0,0,0)",
                    plot_bgcolor="rgba(0,0,0,0)",
                    font=dict(color="#FFFFFF", family="Inter"),
                    title_font=dict(size=18, family="Plus Jakarta Sans"),
                    legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
                )
                figure.update_xaxes(gridcolor="rgba(255,255,255,.04)", title_text="Tanggal")
                figure.update_yaxes(gridcolor="rgba(255,255,255,.07)", title_text="Jumlah Aktivitas", dtick=1)
                st.plotly_chart(
                    figure,
                    use_container_width=True,
                    config={"displayModeBar": False, "responsive": True},
                )
            else:
                st.markdown('<div class="admin-v7-empty">Belum ada tanggal aktivitas yang dapat divisualisasikan.</div>', unsafe_allow_html=True)

        with leaderboard_col:
            leaderboard_rows = []
            if not filtered_activity.empty:
                grouped = (
                    filtered_activity.groupby(["owner_key", "fullname", "username"], dropna=False)
                    .size()
                    .reset_index(name="total")
                    .sort_values(["total", "fullname"], ascending=[False, True])
                    .head(5)
                )
                for _, row in grouped.iterrows():
                    name = str(row["fullname"] or row["username"] or "Pengguna")
                    username = str(row["username"] or "-")
                    initials = "".join(part[:1] for part in name.split()[:2]).upper() or "PG"
                    leaderboard_rows.append(
                        '<div class="admin-v7-person" tabindex="0">'
                        f'<div class="admin-v7-avatar">{escape(initials)}</div>'
                        f'<div><div class="admin-v7-person-name">{escape(name)}</div><div class="admin-v7-person-meta">@{escape(username)}</div></div>'
                        f'<div class="admin-v7-person-value">{int(row["total"])} analisis</div>'
                        '</div>'
                    )
            leaderboard_html = (
                '<div class="admin-v7-panel">'
                '<div class="admin-v7-panel-head"><div class="admin-v7-panel-title">Siapa yang Melakukan Analisis</div><div class="admin-v7-panel-badge">Top 5 akun</div></div>'
                + (''.join(leaderboard_rows) if leaderboard_rows else '<div class="admin-v7-empty">Belum ada riwayat analisis manual pada periode ini.</div>')
                + '</div>'
            )
            st.markdown(leaderboard_html, unsafe_allow_html=True)

        recent_col, registration_col = st.columns(2, gap="large")
        with recent_col:
            recent_rows = []
            for _, row in filtered_activity.head(5).iterrows() if not filtered_activity.empty else []:
                name = str(row.get("fullname") or row.get("username") or "Pengguna")
                username = str(row.get("username") or "-")
                sentiment = str(row.get("sentiment") or "Tidak diketahui")
                sentiment_class = "positif" if "positif" in sentiment.lower() else "negatif" if "negatif" in sentiment.lower() else "netral"
                initials = "".join(part[:1] for part in name.split()[:2]).upper() or "PG"
                recent_rows.append(
                    '<div class="admin-v7-person" tabindex="0">'
                    f'<div class="admin-v7-avatar">{escape(initials)}</div>'
                    f'<div><div class="admin-v7-person-name">{escape(name)}</div><div class="admin-v7-person-meta">@{escape(username)} · {_format_activity_time(row.get("activity_at"))}</div><span class="admin-v7-sentiment {sentiment_class}">{escape(sentiment)}</span></div>'
                    f'<div class="admin-v7-person-value">{escape(str(row.get("confidence") or "-"))}</div>'
                    '</div>'
                )
            st.markdown(
                '<div class="admin-v7-panel"><div class="admin-v7-panel-head"><div class="admin-v7-panel-title">Aktivitas Analisis Terbaru</div><div class="admin-v7-panel-badge">Prediksi manual</div></div>'
                + (''.join(recent_rows) if recent_rows else '<div class="admin-v7-empty">Belum ada aktivitas analisis yang tersimpan.</div>')
                + '</div>',
                unsafe_allow_html=True,
            )

        with registration_col:
            recent_registrations = sorted(
                registration_rows,
                key=lambda row: pd.Timestamp(row["activity_at"]),
                reverse=True,
            )[:5]
            registration_cards = []
            for row in recent_registrations:
                name = str(row.get("fullname") or row.get("username") or "Pengguna")
                username = str(row.get("username") or "-")
                role = normalize_role(row.get("role"), row.get("user_id"))
                initials = "".join(part[:1] for part in name.split()[:2]).upper() or "PG"
                registration_cards.append(
                    '<div class="admin-v7-person" tabindex="0">'
                    f'<div class="admin-v7-avatar" style="background:linear-gradient(135deg,#29B6F6,#00D4B8)">{escape(initials)}</div>'
                    f'<div><div class="admin-v7-person-name">{escape(name)}</div><div class="admin-v7-person-meta">@{escape(username)} · {_format_activity_time(row.get("activity_at"))}</div></div>'
                    f'<div class="admin-v7-person-value">{escape(get_role_label(role))}</div>'
                    '</div>'
                )
            st.markdown(
                '<div class="admin-v7-panel"><div class="admin-v7-panel-head"><div class="admin-v7-panel-title">Siapa yang Baru Daftar</div><div class="admin-v7-panel-badge">5 terbaru</div></div>'
                + (''.join(registration_cards) if registration_cards else '<div class="admin-v7-empty">Tidak ada registrasi baru pada periode ini.</div>')
                + '</div>',
                unsafe_allow_html=True,
            )

        if activity.empty:
            st.info(
                "Riwayat analisis manual belum tersedia. Bagian 'Siapa yang Melakukan Analisis' akan terisi otomatis setelah pengguna menjalankan prediksi sentimen manual."
            )
    except Exception as error:
        st.error(f"Dashboard aktivitas pengguna tidak dapat ditampilkan: {error}")


def _render_registration_chart(users: list[dict]) -> None:
    """Tampilkan bar chart jumlah registrasi pengguna per bulan."""
    try:
        monthly_registration = _build_monthly_registration(users)
        if monthly_registration.empty:
            st.markdown(
                '<div class="admin-v3-empty">📊 Belum ada tanggal registrasi yang valid untuk divisualisasikan.</div>',
                unsafe_allow_html=True,
            )
            return

        figure = px.bar(
            monthly_registration,
            x="Bulan",
            y="Jumlah Registrasi",
            text="Jumlah Registrasi",
            title="Pertumbuhan Registrasi Pengguna",
        )
        figure.update_traces(
            textposition="outside",
            cliponaxis=False,
            marker=dict(color="#E53935", line=dict(color="#FF706C", width=1.2)),
            hovertemplate="<b>%{x}</b><br>Registrasi: %{y}<extra></extra>",
        )
        figure.update_layout(
            xaxis_title="Bulan Registrasi",
            yaxis_title="Jumlah Pengguna",
            hovermode="x unified",
            margin=dict(l=20, r=20, t=70, b=20),
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
            font=dict(color="#FFFFFF", family="Inter"),
            title_font=dict(size=18, family="Plus Jakarta Sans"),
            bargap=0.38,
        )
        figure.update_xaxes(gridcolor="rgba(255,255,255,0.05)", linecolor="rgba(255,255,255,0.10)")
        figure.update_yaxes(dtick=1, rangemode="tozero", gridcolor="rgba(255,255,255,0.07)", linecolor="rgba(255,255,255,0.10)")
        st.plotly_chart(figure, use_container_width=True, config={"displayModeBar": False})
    except Exception as error:
        st.error(f"Gagal menampilkan grafik registrasi: {error}")


def _render_file_cards(status_table: pd.DataFrame) -> None:
    """Tampilkan status file data dalam grid interaktif dan berwarna."""
    try:
        if status_table.empty:
            st.markdown(
                '<div class="admin-v3-empty">📁 Status file belum dapat dibaca.</div>',
                unsafe_allow_html=True,
            )
            return

        palet_file = [
            ("#35D07F", "#00B8D9", "rgba(53,208,127,.22)"),
            ("#8E5AF7", "#E653FF", "rgba(142,90,247,.24)"),
            ("#29B6F6", "#4C6FFF", "rgba(41,182,246,.22)"),
            ("#FF4D48", "#FF9A44", "rgba(255,77,72,.23)"),
            ("#00D4B8", "#2F80ED", "rgba(0,212,184,.22)"),
        ]
        available_count = int(status_table["Tersedia"].sum())
        total_files = len(status_table)
        missing_count = max(total_files - available_count, 0)
        readiness = round((available_count / total_files) * 100) if total_files else 0

        cards_html: list[str] = []
        for index, row in status_table.iterrows():
            is_available = bool(row["Tersedia"])
            primary, secondary, halo = palet_file[index % len(palet_file)]
            label = str(row["Jenis Data"])
            file_path = str(row["File"])
            category = "Analisis Sentimen" if "Sentimen" in label else "Jejaring SNA"
            lower_path = file_path.lower()
            if lower_path.endswith(".csv.gz"):
                file_type = "CSV.GZ"
            elif "." in file_path:
                file_type = file_path.rsplit(".", 1)[-1].upper()
            else:
                file_type = "DATA"
            status_label = "Siap digunakan" if is_available else "Perlu dilengkapi"
            status_icon = "✓" if is_available else "!"
            state_class = "is-ready" if is_available else "is-missing"
            meter_width = 100 if is_available else 18

            cards_html.append(
                dedent(
                    f'''
                    <article class="admin-v6-file-card {state_class}" tabindex="0"
                    style="--file-primary:{primary};--file-secondary:{secondary};--file-halo:{halo};"
                    aria-label="{escape(label)}: {escape(status_label)}">
                    <div class="admin-v6-file-orb"></div>
                    <div class="admin-v6-file-scan"></div>
                    <div class="admin-v6-file-topline"></div>
                    <div class="admin-v6-file-head">
                        <div class="admin-v6-file-icon-wrap">
                            <span class="admin-v6-file-icon">{escape(str(row["Ikon"]))}</span>
                            <i></i>
                        </div>
                        <div class="admin-v6-file-index">FILE {index + 1:02d}</div>
                    </div>
                    <div class="admin-v6-file-category">{escape(category)}</div>
                    <div class="admin-v6-file-title">{escape(label)}</div>
                    <div class="admin-v6-file-path" title="{escape(file_path)}">{escape(file_path)}</div>
                    <div class="admin-v6-file-meter" aria-hidden="true">
                        <span style="width:{meter_width}%"></span>
                    </div>
                    <div class="admin-v6-file-foot">
                        <span class="admin-v6-file-status"><b>{status_icon}</b>{escape(status_label)}</span>
                        <span class="admin-v6-file-meta">{escape(file_type)} · {escape(str(row["Ukuran"]))}</span>
                    </div>
                </article>'''
                ).strip()
            )

        health_title = (
            "Seluruh file siap digunakan"
            if available_count == total_files and total_files > 0
            else "Sebagian file masih perlu dilengkapi"
        )
        health_note = (
            "Seluruh sumber data inti terdeteksi dan dapat digunakan oleh halaman analitik."
            if available_count == total_files and total_files > 0
            else f"{missing_count} file belum ditemukan. Halaman terkait dapat memakai fallback bila diperlukan."
        )
        health_class = "is-healthy" if available_count == total_files and total_files > 0 else "is-warning"
        health_icon = "✅" if health_class == "is-healthy" else "⚠️"

        html_status_file = dedent(
            f'''
            <style>
                @keyframes adminV6FileFloat {{
                    0%, 100% {{ transform: translate3d(0,0,0) scale(1); }}
                    50% {{ transform: translate3d(-8px,8px,0) scale(1.08); }}
                }}
                @keyframes adminV6FileSweep {{
                    0% {{ transform: translateX(-150%) skewX(-18deg); opacity:0; }}
                    18% {{ opacity:.6; }}
                    100% {{ transform: translateX(340%) skewX(-18deg); opacity:0; }}
                }}
                @keyframes adminV6FilePulse {{
                    0%,100% {{ box-shadow:0 0 0 0 color-mix(in srgb, var(--file-primary) 28%, transparent); }}
                    50% {{ box-shadow:0 0 0 9px transparent; }}
                }}
                @keyframes adminV6Meter {{
                    from {{ transform:scaleX(0); }}
                    to {{ transform:scaleX(1); }}
                }}
                .admin-v6-file-overview {{
                    align-items:center;
                    background:
                        radial-gradient(circle at 12% 15%, rgba(142,90,247,.18), transparent 30%),
                        radial-gradient(circle at 88% 12%, rgba(0,212,184,.13), transparent 28%),
                        linear-gradient(135deg, rgba(20,14,38,.96), rgba(9,22,38,.94));
                    border:1px solid rgba(142,90,247,.28);
                    border-radius:22px;
                    display:grid;
                    gap:1rem;
                    grid-template-columns:auto 1fr auto;
                    margin:.1rem 0 1rem;
                    overflow:hidden;
                    padding:1rem 1.15rem;
                    position:relative;
                    box-shadow:0 18px 38px rgba(0,0,0,.16);
                }}
                .admin-v6-file-overview::after {{
                    animation:adminV6FileSweep 9s linear infinite;
                    background:linear-gradient(100deg,transparent,rgba(255,255,255,.08),transparent);
                    content:'';
                    inset:0 auto 0 -30%;
                    pointer-events:none;
                    position:absolute;
                    width:22%;
                }}
                .admin-v6-readiness-ring {{
                    align-items:center;
                    background:conic-gradient(#55D88B {readiness}%, rgba(255,255,255,.08) 0);
                    border-radius:50%;
                    display:flex;
                    height:82px;
                    justify-content:center;
                    position:relative;
                    width:82px;
                }}
                .admin-v6-readiness-ring::before {{
                    background:#101522;
                    border:1px solid rgba(255,255,255,.08);
                    border-radius:50%;
                    content:'';
                    inset:8px;
                    position:absolute;
                }}
                .admin-v6-readiness-ring strong {{ color:#fff; font-size:1.08rem; position:relative; z-index:1; }}
                .admin-v6-overview-copy h3 {{ color:#fff !important; font-size:1.02rem; margin:0; }}
                .admin-v6-overview-copy p {{ color:#AEB8CA !important; font-size:.78rem; line-height:1.55; margin:.28rem 0 0; }}
                .admin-v6-overview-badges {{ display:flex; flex-wrap:wrap; gap:.5rem; justify-content:flex-end; }}
                .admin-v6-overview-badge {{
                    align-items:center;
                    background:rgba(255,255,255,.055);
                    border:1px solid rgba(255,255,255,.10);
                    border-radius:999px;
                    color:#F5F7FB;
                    display:inline-flex;
                    font-size:0.75rem /* FIX: minimum 12px agar terbaca di tablet */;
                    font-weight:800;
                    gap:.35rem;
                    padding:.45rem .7rem;
                    transition:transform .18s ease,border-color .18s ease,background .18s ease;
                }}
                .admin-v6-overview-badge:hover {{ background:rgba(255,255,255,.09); border-color:rgba(255,255,255,.18); transform:translateY(-2px); }}
                .admin-v6-overview-badge.ready b {{ color:#5DE08D; }}
                .admin-v6-overview-badge.missing b {{ color:#FF746E; }}
                .admin-v6-file-grid {{
                    display:grid;
                    gap:1rem;
                    grid-template-columns:repeat(auto-fit,minmax(250px,1fr));
                    margin:.2rem 0 1rem;
                }}
                .admin-v6-file-card {{
                    background:
                        radial-gradient(circle at 92% 8%, var(--file-halo), transparent 32%),
                        linear-gradient(155deg, rgba(17,22,34,.98), rgba(9,14,25,.97));
                    border:1px solid color-mix(in srgb,var(--file-primary) 36%,rgba(255,255,255,.08));
                    border-radius:22px;
                    box-shadow:0 16px 32px rgba(0,0,0,.16);
                    min-height:286px;
                    overflow:hidden;
                    padding:1.08rem;
                    position:relative;
                    transition:transform .24s ease,border-color .24s ease,box-shadow .24s ease;
                }}
                .admin-v6-file-card:hover,
                .admin-v6-file-card:focus {{
                    border-color:var(--file-primary);
                    box-shadow:0 22px 46px rgba(0,0,0,.24),0 0 28px var(--file-halo);
                    outline:none;
                    transform:translateY(-6px);
                }}
                .admin-v6-file-card.is-missing {{ filter:saturate(.78); }}
                .admin-v6-file-topline {{
                    background:linear-gradient(90deg,var(--file-primary),var(--file-secondary));
                    height:4px;
                    inset:0 0 auto;
                    position:absolute;
                }}
                .admin-v6-file-orb {{
                    animation:adminV6FileFloat 6.2s ease-in-out infinite;
                    background:radial-gradient(circle,var(--file-halo),transparent 70%);
                    border-radius:50%;
                    height:150px;
                    position:absolute;
                    right:-52px;
                    top:-44px;
                    width:150px;
                }}
                .admin-v6-file-scan {{
                    animation:adminV6FileSweep 7s ease-in-out infinite;
                    background:linear-gradient(100deg,transparent,color-mix(in srgb,var(--file-primary) 16%,transparent),transparent);
                    inset:0 auto 0 -45%;
                    pointer-events:none;
                    position:absolute;
                    width:34%;
                }}
                .admin-v6-file-head {{ align-items:center; display:flex; justify-content:space-between; position:relative; z-index:1; }}
                .admin-v6-file-icon-wrap {{
                    align-items:center;
                    background:linear-gradient(135deg,color-mix(in srgb,var(--file-primary) 28%,transparent),color-mix(in srgb,var(--file-secondary) 20%,transparent));
                    border:1px solid color-mix(in srgb,var(--file-primary) 42%,transparent);
                    border-radius:17px;
                    display:flex;
                    height:56px;
                    justify-content:center;
                    position:relative;
                    width:56px;
                }}
                .admin-v6-file-icon-wrap i {{
                    animation:adminV6FilePulse 2.3s ease-in-out infinite;
                    background:var(--file-primary);
                    border:2px solid #101522;
                    border-radius:50%;
                    height:11px;
                    position:absolute;
                    right:-3px;
                    top:-3px;
                    width:11px;
                }}
                .admin-v6-file-icon {{ font-size:1.55rem; }}
                .admin-v6-file-index {{ color:#7F8A9E; font-size:0.75rem /* FIX: minimum 12px agar terbaca di tablet */; font-weight:900; letter-spacing:.12em; }}
                .admin-v6-file-category {{
                    color:var(--file-primary);
                    font-size:0.75rem /* FIX: minimum 12px agar terbaca di tablet */;
                    font-weight:900;
                    letter-spacing:.10em;
                    margin-top:1.05rem;
                    position:relative;
                    text-transform:uppercase;
                    z-index:1;
                }}
                .admin-v6-file-title {{ color:#fff; font-size:1.02rem; font-weight:800; line-height:1.3; margin-top:.32rem; min-height:2.65rem; position:relative; z-index:1; }}
                .admin-v6-file-path {{
                    -webkit-box-orient:vertical;
                    -webkit-line-clamp:2;
                    color:#9AA6B9;
                    display:-webkit-box;
                    font-family:'JetBrains Mono','Consolas',monospace;
                    font-size:0.75rem /* FIX: minimum 12px agar terbaca di tablet */;
                    line-height:1.55;
                    margin-top:.52rem;
                    min-height:2.2rem;
                    overflow:hidden;
                    overflow-wrap:anywhere;
                    position:relative;
                    z-index:1;
                }}
                .admin-v6-file-meter {{ background:rgba(255,255,255,.065); border-radius:999px; height:7px; margin:1rem 0 .72rem; overflow:hidden; position:relative; z-index:1; }}
                .admin-v6-file-meter span {{
                    animation:adminV6Meter .9s ease both;
                    background:linear-gradient(90deg,var(--file-primary),var(--file-secondary));
                    border-radius:inherit;
                    display:block;
                    height:100%;
                    transform-origin:left;
                }}
                .admin-v6-file-foot {{ align-items:center; display:flex; gap:.45rem; justify-content:space-between; position:relative; z-index:1; }}
                .admin-v6-file-status {{
                    align-items:center;
                    background:color-mix(in srgb,var(--file-primary) 12%,transparent);
                    border:1px solid color-mix(in srgb,var(--file-primary) 32%,transparent);
                    border-radius:999px;
                    color:#F7F9FC;
                    display:inline-flex;
                    font-size:0.75rem /* FIX: minimum 12px agar terbaca di tablet */;
                    font-weight:800;
                    gap:.35rem;
                    padding:.4rem .62rem;
                    white-space:nowrap;
                }}
                .admin-v6-file-status b {{ color:var(--file-primary); font-size:.8rem; }}
                .admin-v6-file-meta {{ color:#A7B1C2; font-size:0.75rem /* FIX: minimum 12px agar terbaca di tablet */; font-weight:800; text-align:right; }}
                .admin-v6-health-banner {{
                    align-items:center;
                    border:1px solid;
                    border-radius:18px;
                    display:flex;
                    gap:.8rem;
                    margin:.15rem 0 .8rem;
                    overflow:hidden;
                    padding:.85rem 1rem;
                    position:relative;
                }}
                .admin-v6-health-banner.is-healthy {{ background:linear-gradient(135deg,rgba(30,92,64,.55),rgba(12,49,45,.70)); border-color:rgba(76,217,137,.28); }}
                .admin-v6-health-banner.is-warning {{ background:linear-gradient(135deg,rgba(103,60,18,.55),rgba(67,27,23,.72)); border-color:rgba(255,167,38,.30); }}
                .admin-v6-health-icon {{ align-items:center; background:rgba(255,255,255,.08); border-radius:13px; display:flex; font-size:1.15rem; height:42px; justify-content:center; min-width:42px; }}
                .admin-v6-health-copy strong {{ color:#fff; display:block; font-size:.82rem; }}
                .admin-v6-health-copy span {{ color:#C2CCDA; display:block; font-size:0.75rem /* FIX: minimum 12px agar terbaca di tablet */; line-height:1.5; margin-top:.14rem; }}
                @media (max-width:800px) {{
                    .admin-v6-file-overview {{ grid-template-columns:auto 1fr; }}
                    .admin-v6-overview-badges {{ grid-column:1 / -1; justify-content:flex-start; }}
                }}
                @media (max-width:520px) {{
                    .admin-v6-file-overview {{ grid-template-columns:1fr; text-align:center; }}
                    .admin-v6-readiness-ring {{ margin:0 auto; }}
                    .admin-v6-overview-badges {{ justify-content:center; }}
                    .admin-v6-file-grid {{ grid-template-columns:1fr; }}
                }}
                @media (prefers-reduced-motion:reduce) {{
                    .admin-v6-file-card *, .admin-v6-file-card::before, .admin-v6-file-card::after,
                    .admin-v6-file-overview::after {{ animation:none !important; transition:none !important; }}
                }}
            </style>
            <section class="admin-v6-file-overview" tabindex="0">
                <div class="admin-v6-readiness-ring"><strong>{readiness}%</strong></div>
                <div class="admin-v6-overview-copy">
                    <h3>Kesiapan Data Penelitian</h3>
                    <p>Pemeriksaan otomatis membaca keberadaan file, format sumber, dan ukuran data yang digunakan dashboard.</p>
                </div>
                <div class="admin-v6-overview-badges">
                    <span class="admin-v6-overview-badge ready"><b>●</b>{available_count} tersedia</span>
                    <span class="admin-v6-overview-badge missing"><b>●</b>{missing_count} perlu perhatian</span>
                    <span class="admin-v6-overview-badge"><b>↻</b>Live scan</span>
                </div>
            </section>
            <div class="admin-v6-file-grid">{''.join(cards_html)}</div>
            <div class="admin-v6-health-banner {health_class}" tabindex="0">
                <div class="admin-v6-health-icon">{health_icon}</div>
                <div class="admin-v6-health-copy">
                    <strong>{escape(health_title)}</strong>
                    <span>{escape(health_note)}</span>
                </div>
            </div>'''
        ).strip()
        # Streamlit/Markdown menganggap baris dengan empat spasi sebagai blok kode.
        # Ratakan seluruh baris HTML dinamis agar setiap card selalu dirender sebagai HTML.
        html_status_file = "\n".join(
            baris.lstrip() for baris in html_status_file.splitlines()
        )
        st.markdown(html_status_file, unsafe_allow_html=True)
    except Exception as error:
        st.error(f"Gagal menampilkan kartu status file: {error}")


def _render_system_statistics_tab() -> None:
    """Render metrik pengguna, grafik registrasi, dan status file data."""
    try:
        _render_section_header(
            "📊",
            "Statistik & Kesehatan Sistem",
            "Pantau pertumbuhan akun, komposisi hak akses, dan kesiapan seluruh file data penelitian.",
        )

        users = get_all_users()
        stats = get_user_stats()
        status_table = _build_file_status_table()
        available_count = int(status_table["Tersedia"].sum()) if not status_table.empty else 0
        total_files = len(status_table)

        _render_metric_cards(
            [
                {"icon": "👥", "label": "Total Pengguna", "value": stats.get("total_users", len(users)), "color": "#E53935"},
                {"icon": "🛡️", "label": "Total Data Analis", "value": stats.get("total_data_analyst", 0), "color": "#AB47BC"},
                {"icon": "🆕", "label": "Pengguna Baru Bulan Ini", "value": _count_new_users_this_month(users), "color": "#FF9800"},
                {"icon": "🗂️", "label": "File Data Tersedia", "value": f"{available_count}/{total_files}", "color": "#4CAF50"},
            ]
        )

        _render_section_header(
            "📈",
            "Insight Aktivitas Pengguna",
            "Pantau siapa yang mendaftar, siapa yang menjalankan analisis manual, dan bagaimana aktivitas berkembang dari waktu ke waktu.",
            "orange",
        )
        _render_user_activity_analytics(users, status_table)

        _render_section_header(
            "📁",
            "Status File Data",
            "File CSV terkompresi (.csv.gz) tetap dihitung tersedia dan dapat digunakan oleh aplikasi.",
            "purple",
        )
        _render_file_cards(status_table)
    except Exception as error:
        st.error(f"Gagal memuat statistik sistem: {error}")


def _audit_status_label(status: str) -> str:
    """Ubah status internal menjadi label Bahasa Indonesia."""
    return {
        "success": "Berhasil",
        "failed": "Gagal",
        "denied": "Ditolak",
        "warning": "Peringatan",
    }.get(str(status).lower(), str(status).title())


def _audit_action_label(action: str) -> str:
    """Ubah kode aktivitas menjadi label yang mudah dibaca."""
    labels = {
        "LOGIN_SUCCESS": "Login Berhasil",
        "LOGIN_FAILED": "Login Gagal",
        "LOGOUT": "Logout",
        "REGISTER_SUCCESS": "Registrasi",
        "REGISTER_FAILED": "Registrasi Gagal",
        "OPEN_PAGE": "Membuka Halaman",
        "ACCESS_DENIED": "Akses Ditolak",
        "UPLOAD_ANALYSIS": "Analisis Dataset Upload",
        "SENTIMENT_PREDICTION": "Prediksi Sentimen",
        "TOPIC_ANALYSIS": "Analisis Topik",
        "SNA_ANALYSIS": "Analisis SNA",
        "GEMINI_CONTENT": "Generate Konten Gemini",
        "GEMINI_STRATEGY": "Strategi Gemini",
        "PROFILE_UPDATE": "Ubah Profil",
        "PROFILE_PHOTO_UPDATE": "Ubah Foto Profil",
        "PASSWORD_CHANGE": "Ubah Password",
        "CREATE_USER": "Tambah Pengguna",
        "CHANGE_ROLE": "Ubah Role",
        "DELETE_USER": "Hapus Pengguna",
        "SELF_DELETE_ACCOUNT": "Hapus Akun Sendiri",
    }
    return labels.get(str(action), str(action).replace("_", " ").title())


def _render_activity_log_tab() -> None:
    """Render audit trail nyata dari tabel audit_logs di SQLite."""
    try:
        _render_section_header(
            "🧾",
            "Audit Log Aktivitas Sistem",
            "Pantau siapa melakukan apa, kapan aktivitas terjadi, modul yang digunakan, serta status berhasil atau gagal.",
            "orange",
        )

        period_map = {"Hari Ini": 1, "7 Hari": 7, "30 Hari": 30, "90 Hari": 90, "Semua Waktu": None}
        options = get_audit_filter_options()

        with st.container(border=True):
            st.markdown(
                """
                <div style="padding:.25rem 0 .65rem;">
                    <div style="font-size:1.04rem;font-weight:800;color:#fff;">Filter Audit Terperinci</div>
                    <div style="font-size:.78rem;color:#9AA5B8;margin-top:.18rem;">Filter tidak mengubah atau menghapus data. Semua hasil dapat diekspor sebagai CSV.</div>
                </div>
                """,
                unsafe_allow_html=True,
            )
            f1, f2, f3, f4 = st.columns([1.05, 1.15, 1.25, 1.0], gap="medium")
            with f1:
                period_label = st.selectbox("Periode", list(period_map), index=2, key="admin_audit_period")
            with f2:
                username_filter = st.selectbox(
                    "Pengguna",
                    ["Semua Pengguna", *options.get("usernames", [])],
                    key="admin_audit_username",
                )
            with f3:
                action_filter = st.selectbox(
                    "Jenis Aktivitas",
                    ["Semua Aktivitas", *options.get("actions", [])],
                    format_func=lambda value: value if value == "Semua Aktivitas" else _audit_action_label(value),
                    key="admin_audit_action",
                )
            with f4:
                status_filter = st.selectbox(
                    "Status",
                    ["Semua Status", "success", "failed", "denied", "warning"],
                    format_func=lambda value: value if value == "Semua Status" else _audit_status_label(value),
                    key="admin_audit_status",
                )
            search_text = st.text_input(
                "Cari username, modul, atau deskripsi",
                placeholder="Contoh: admin, Analisis Sentimen, Gemini...",
                key="admin_audit_search",
            )

        logs = fetch_audit_logs(
            days=period_map[period_label],
            username=username_filter,
            action=action_filter,
            status=status_filter,
            search=search_text,
            limit=5000,
        )
        frame = audit_dataframe(logs)

        total_activity = len(frame)
        unique_users = int(frame["Pengguna"].nunique()) if not frame.empty else 0
        success_count = int((frame["Status"] == "success").sum()) if not frame.empty else 0
        failed_count = int(frame["Status"].isin(["failed", "denied"]).sum()) if not frame.empty else 0
        _render_metric_cards(
            [
                {"icon": "⚡", "label": "Total Aktivitas", "value": total_activity, "color": "#FF9800"},
                {"icon": "👥", "label": "Pengguna Aktif", "value": unique_users, "color": "#38BDF8"},
                {"icon": "✅", "label": "Berhasil", "value": success_count, "color": "#4CAF50"},
                {"icon": "⚠️", "label": "Gagal / Ditolak", "value": failed_count, "color": "#F44336"},
            ]
        )

        if frame.empty:
            st.info(
                "Belum ada audit log pada filter ini. Aktivitas baru akan tercatat sejak patch audit dipasang."
            )
            return

        chart_col, module_col = st.columns([1.65, 1], gap="large")
        with chart_col:
            timeline = frame.dropna(subset=["Waktu"]).copy()
            timeline["Tanggal"] = timeline["Waktu"].dt.floor("D")
            timeline = timeline.groupby(["Tanggal", "Status"], as_index=False).size()
            fig_timeline = px.area(
                timeline,
                x="Tanggal",
                y="size",
                color="Status",
                title="Tren Aktivitas Sistem",
                labels={"size": "Jumlah Aktivitas"},
                color_discrete_map={
                    "success": "#4CAF50",
                    "failed": "#F44336",
                    "denied": "#FF9800",
                    "warning": "#AB47BC",
                },
            )
            fig_timeline.update_layout(
                paper_bgcolor="rgba(0,0,0,0)",
                plot_bgcolor="rgba(0,0,0,0)",
                font={"color": "#E8ECF3"},
                legend_title_text="Status",
                margin={"l": 20, "r": 20, "t": 55, "b": 20},
                height=360,
            )
            st.plotly_chart(fig_timeline, use_container_width=True, config={"displayModeBar": False})

        with module_col:
            module_counts = frame["Modul"].fillna("Sistem").value_counts().head(8).reset_index()
            module_counts.columns = ["Modul", "Jumlah"]
            fig_module = px.bar(
                module_counts.sort_values("Jumlah"),
                x="Jumlah",
                y="Modul",
                orientation="h",
                title="Modul Paling Aktif",
                text="Jumlah",
            )
            fig_module.update_traces(marker_color="#8B5CF6", textposition="outside")
            fig_module.update_layout(
                paper_bgcolor="rgba(0,0,0,0)",
                plot_bgcolor="rgba(0,0,0,0)",
                font={"color": "#E8ECF3"},
                margin={"l": 10, "r": 35, "t": 55, "b": 20},
                height=360,
            )
            st.plotly_chart(fig_module, use_container_width=True, config={"displayModeBar": False})

        st.markdown("### Aktivitas Terbaru")
        display_frame = frame.copy()
        display_frame["Waktu"] = display_frame["Waktu"].dt.strftime("%d-%m-%Y %H:%M:%S")
        display_frame["Aktivitas"] = display_frame["Aktivitas"].map(_audit_action_label)
        display_frame["Status"] = display_frame["Status"].map(_audit_status_label)
        st.dataframe(
            display_frame,
            use_container_width=True,
            hide_index=True,
            height=440,
            column_config={
                "Waktu": st.column_config.TextColumn("Waktu", width="medium"),
                "Pengguna": st.column_config.TextColumn("Pengguna", width="small"),
                "Aktivitas": st.column_config.TextColumn("Aktivitas", width="medium"),
                "Deskripsi": st.column_config.TextColumn("Deskripsi", width="large"),
            },
        )

        st.download_button(
            "⬇️ Ekspor Audit Log (CSV)",
            data=display_frame.to_csv(index=False).encode("utf-8-sig"),
            file_name=f"audit_log_dashboard_{pd.Timestamp.now():%Y%m%d_%H%M%S}.csv",
            mime="text/csv",
            use_container_width=True,
        )

        st.caption(
            "Audit log tidak menyimpan password, token, API key, cookie, atau isi BLOB foto. "
            "Aktivitas lama sebelum patch dipasang tidak dibuat secara retroaktif."
        )
    except Exception as error:
        st.error(f"Audit log sistem belum dapat dimuat: {error}")

def render_admin_panel() -> None:
    """Tampilkan Admin Panel dan hentikan akses selain Data Analis."""
    try:
        role = normalize_role(
            st.session_state.get("role", DEFAULT_ROLE),
            st.session_state.get("user_id"),
        )
        if role != ROLE_DATA_ANALYST:
            st.error("⛔ Akses ditolak. Halaman ini hanya dapat dibuka oleh Data Analis.")
            st.stop()

        _inject_admin_css()
        _render_admin_hero()

        management_tab, statistics_tab, activity_tab = st.tabs(
            [
                "👥 Manajemen Pengguna",
                "📊 Statistik Sistem",
                "🧾 Aktivitas Sistem",
            ]
        )

        with management_tab:
            _render_user_management_tab()
        with statistics_tab:
            _render_system_statistics_tab()
        with activity_tab:
            _render_activity_log_tab()
    except Exception as error:
        st.error(f"Gagal memuat Admin Panel: {error}")
