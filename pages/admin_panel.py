"""Panel admin untuk manajemen pengguna dan pemantauan status sistem."""

from __future__ import annotations

import re
from html import escape
from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st

from utils.indibiz_config import OUTPUT_FILES as INDIBIZ_OUTPUT_FILES

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
FLASH_MESSAGE_KEY = "admin_panel_flash_message"

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
                    font-size: .72rem;
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
                    font-size: .72rem;
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
                    font-size: .73rem;
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
                    font-size: .67rem;
                    line-height: 1.45;
                    margin: .45rem 0 .7rem;
                    overflow-wrap: anywhere;
                }
                .admin-v3-file-bottom { align-items: center; display: flex; gap: .5rem; justify-content: space-between; }
                .admin-v3-file-ok { background: rgba(76,175,80,.13); color: #66BB6A; border: 1px solid rgba(76,175,80,.23); }
                .admin-v3-file-missing { background: rgba(244,67,54,.13); color: #EF5350; border: 1px solid rgba(244,67,54,.23); }
                .admin-v3-file-size { color: var(--app-muted); font-size: .7rem; font-weight: 700; }

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
                .admin-v3-activity-meta { color: var(--app-muted); font-size: .7rem; line-height: 1.45; margin-top: .18rem; }

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
                @media (max-width: 700px) {
                    .admin-v3-hero-top { align-items: flex-start; flex-direction: column; }
                    .admin-v3-mini-stat-grid { grid-template-columns: 1fr; }
                    .admin-v3-section-head { align-items: flex-start; }
                }
            </style>
            """,
            unsafe_allow_html=True,
        )
    except Exception as error:
        st.error(f"Gagal memuat tampilan Admin Panel: {error}")


def _render_admin_hero() -> None:
    """Tampilkan hero Admin Panel yang lebih informatif dan visual."""
    try:
        admin_name = escape(str(st.session_state.get("fullname") or st.session_state.get("username") or "Administrator"))
        st.markdown(
            f"""
            <section class="admin-v3-hero">
                <div class="admin-v3-hero-top">
                    <div class="admin-v3-hero-icon">⚙️</div>
                    <div class="admin-v3-hero-copy">
                        <h1>Admin Panel</h1>
                        <p>
                            Pusat kendali pengguna, statistik sistem, dan kesiapan data penelitian.
                            Selamat datang, <strong>{admin_name}</strong>.
                        </p>
                        <div class="admin-v3-hero-badges">
                            <span class="admin-v3-hero-badge"><span class="admin-v3-online-dot"></span>Sistem aktif</span>
                            <span class="admin-v3-hero-badge">🛡️ Akses administrator</span>
                            <span class="admin-v3-hero-badge">🗃️ SQLite terhubung</span>
                            <span class="admin-v3-hero-badge">✨ Dashboard v2.0</span>
                        </div>
                    </div>
                </div>
            </section>
            """,
            unsafe_allow_html=True,
        )
    except Exception as error:
        st.error(f"Gagal menampilkan header Admin Panel: {error}")


def _render_section_header(icon: str, title: str, description: str, tone: str = "") -> None:
    """Tampilkan judul seksi dalam kartu ringkas."""
    try:
        st.markdown(
            f"""
            <div class="admin-v3-section-head {escape(tone)}">
                <div class="admin-v3-section-icon">{escape(icon)}</div>
                <div class="admin-v3-section-copy">
                    <h2>{escape(title)}</h2>
                    <p>{escape(description)}</p>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )
    except Exception as error:
        st.error(f"Gagal menampilkan judul bagian: {error}")


def _render_metric_cards(items: list[dict]) -> None:
    """Tampilkan kartu metrik berwarna tanpa membuat HTML terbaca sebagai kode."""
    try:
        cards = []
        for index, item in enumerate(items):
            # HTML sengaja dibuat tanpa indentasi dan baris kosong.
            # Markdown menganggap baris dengan empat spasi sebagai blok kode.
            cards.append(
                '<article class="admin-v3-mini-stat" '
                f'style="--metric-accent:{escape(str(item["color"]))}; animation-delay:{index * 65}ms;">'
                '<div class="admin-v3-mini-stat-top">'
                f'<span class="admin-v3-mini-stat-icon">{escape(str(item["icon"]))}</span>'
                '</div>'
                f'<div class="admin-v3-mini-stat-value">{escape(str(item["value"]))}</div>'
                f'<div class="admin-v3-mini-stat-label">{escape(str(item["label"]))}</div>'
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


def _render_delete_confirmation(current_user_id: int) -> None:
    """Tampilkan peringatan dan tombol konfirmasi penghapusan pengguna."""
    try:
        target = st.session_state.get(DELETE_TARGET_KEY)
        if not target:
            return

        target_id = int(target.get("user_id", 0))
        target_username = str(target.get("username", "-"))
        target_fullname = str(target.get("fullname", "-"))

        st.error(
            "⚠️ **Konfirmasi penghapusan akun**\n\n"
            f"Akun **{target_fullname}** (`{target_username}`, ID {target_id}) akan dihapus permanen. "
            "Tindakan ini tidak dapat dibatalkan."
        )

        confirm_col, cancel_col, spacer_col = st.columns([1.35, 1.1, 4.55])
        with confirm_col:
            confirm_delete = st.button(
                "🗑️ Ya, Hapus",
                key=f"confirm_delete_user_{target_id}",
                type="primary",
                use_container_width=True,
            )
        with cancel_col:
            cancel_delete = st.button(
                "↩️ Batal",
                key=f"cancel_delete_user_{target_id}",
                use_container_width=True,
            )
        with spacer_col:
            st.empty()

        if cancel_delete:
            st.session_state.pop(DELETE_TARGET_KEY, None)
            st.rerun()

        if confirm_delete:
            if target_id == 1:
                st.session_state.pop(DELETE_TARGET_KEY, None)
                _set_flash_message("error", "Admin utama dengan user_id=1 tidak dapat dihapus.")
                st.rerun()
            if target_id == current_user_id:
                st.session_state.pop(DELETE_TARGET_KEY, None)
                _set_flash_message("error", "Akun yang sedang digunakan tidak dapat dihapus.")
                st.rerun()

            success, message = delete_user(target_id)
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
            role = str(user.get("role", "user")).lower()
            if role_filter != "Semua Role" and role != role_filter.lower():
                continue
            searchable = " ".join(
                str(user.get(field, ""))
                for field in ["user_id", "fullname", "username", "email", "role"]
            ).lower()
            if keyword_normalized and keyword_normalized not in searchable:
                continue
            result.append(user)
        return result
    except Exception as error:
        st.error(f"Gagal memfilter pengguna: {error}")
        return users


def _render_user_table(users: list[dict], current_user_id: int) -> None:
    """Tampilkan daftar pengguna beserta tombol aksi pada setiap baris."""
    try:
        if not users:
            st.markdown(
                '<div class="admin-v3-empty">🔎 Tidak ada pengguna yang cocok dengan pencarian atau filter.</div>',
                unsafe_allow_html=True,
            )
            return

        st.markdown(
            """
            <div class="admin-v3-user-head">
                <span>ID</span><span>Nama</span><span>Username</span><span>Email</span>
                <span>Role</span><span>Dibuat</span><span>Aksi</span>
            </div>
            """,
            unsafe_allow_html=True,
        )

        for user in users:
            user_id = int(user.get("user_id", 0))
            role = str(user.get("role", "user")).lower()
            is_main_admin = user_id == 1
            is_current_account = user_id == current_user_id
            action_disabled = is_main_admin or is_current_account

            with st.container(border=True):
                row_columns = st.columns([0.55, 1.45, 1.25, 1.85, 0.75, 1.25, 1.65], gap="small")

                row_columns[0].markdown(
                    f'<span class="admin-v3-id-pill">#{user_id}</span>',
                    unsafe_allow_html=True,
                )

                account_marker = ""
                if is_main_admin:
                    account_marker = '<div class="admin-v3-user-meta">🛡️ Admin utama</div>'
                elif is_current_account:
                    account_marker = '<div class="admin-v3-user-meta">✨ Akun aktif saat ini</div>'
                row_columns[1].markdown(
                    f'<div class="admin-v3-user-name">{escape(str(user.get("fullname", "-")))}</div>{account_marker}',
                    unsafe_allow_html=True,
                )
                row_columns[2].markdown(
                    f'<span class="admin-v3-username">{escape(str(user.get("username", "-")))}</span>',
                    unsafe_allow_html=True,
                )
                row_columns[3].markdown(
                    f'<span class="admin-v3-email">{escape(str(user.get("email", "-")))}</span>',
                    unsafe_allow_html=True,
                )

                role_class = "admin-v3-role-admin" if role == "admin" else "admin-v3-role-user"
                role_icon = "🛡️" if role == "admin" else "👤"
                row_columns[4].markdown(
                    f'<span class="admin-v3-role-pill {role_class}">{role_icon} {escape(role.title())}</span>',
                    unsafe_allow_html=True,
                )
                row_columns[5].markdown(
                    f'<div class="admin-v3-date">{escape(format_created_at(user.get("created_at")))}</div>',
                    unsafe_allow_html=True,
                )

                action_col_role, action_col_delete = row_columns[6].columns(2, gap="small")
                new_role = "user" if role == "admin" else "admin"
                role_label = "User" if new_role == "user" else "Admin"

                disable_reason = None
                if is_main_admin:
                    disable_reason = "Admin utama tidak dapat diubah atau dihapus."
                elif is_current_account:
                    disable_reason = "Akun yang sedang digunakan tidak dapat diubah atau dihapus."

                with action_col_role:
                    change_clicked = st.button(
                        "🔄 Role",
                        key=f"change_role_user_{user_id}",
                        help=disable_reason if action_disabled else f"Ubah role menjadi {role_label}",
                        disabled=action_disabled,
                        use_container_width=True,
                        type="primary",
                    )
                with action_col_delete:
                    delete_clicked = st.button(
                        "🗑️ Hapus",
                        key=f"request_delete_user_{user_id}",
                        help=disable_reason if action_disabled else f"Hapus akun {user.get('username', '-')}",
                        disabled=action_disabled,
                        use_container_width=True,
                    )

                if change_clicked:
                    success, message = update_user_role(user_id, new_role)
                    _set_flash_message("success" if success else "error", message)
                    st.rerun()

                if delete_clicked:
                    st.session_state[DELETE_TARGET_KEY] = {
                        "user_id": user_id,
                        "username": user.get("username", "-"),
                        "fullname": user.get("fullname", "-"),
                    }
                    st.rerun()
    except Exception as error:
        st.error(f"Gagal menampilkan tabel pengguna: {error}")


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
                    role = st.selectbox("Role", options=["user", "admin"], format_func=lambda value: "Pengguna" if value == "user" else "Administrator")
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
                {"icon": "🛡️", "label": "Administrator", "value": stats.get("total_admin", 0), "color": "#AB47BC"},
                {"icon": "👤", "label": "Pengguna Reguler", "value": stats.get("total_regular", 0), "color": "#1DA1F2"},
                {"icon": "🆕", "label": "Baru Bulan Ini", "value": _count_new_users_this_month(users), "color": "#FF9800"},
            ]
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
                options=["Semua Role", "Admin", "User"],
                key="admin_role_filter",
            )

        filtered_users = _filter_users(users, keyword, role_filter)
        st.markdown(
            f'<div class="admin-v3-toolbar-note">Menampilkan <strong>{len(filtered_users)}</strong> dari <strong>{len(users)}</strong> akun. Tombol aksi dinonaktifkan untuk admin utama dan akun yang sedang dipakai.</div>',
            unsafe_allow_html=True,
        )

        _render_delete_confirmation(current_user_id)
        _render_user_table(filtered_users, current_user_id)
        st.markdown('<div style="height:.45rem"></div>', unsafe_allow_html=True)
        _render_create_user_form()
    except Exception as error:
        st.error(f"Gagal memuat manajemen pengguna: {error}")


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
    """Tampilkan status file data dalam kartu visual."""
    try:
        if status_table.empty:
            st.markdown('<div class="admin-v3-empty">📁 Status file belum dapat dibaca.</div>', unsafe_allow_html=True)
            return

        columns = st.columns(4, gap="medium")
        for index, row in status_table.iterrows():
            is_available = bool(row["Tersedia"])
            accent = "#4CAF50" if is_available else "#F44336"
            status_class = "admin-v3-file-ok" if is_available else "admin-v3-file-missing"
            status_icon = "✓" if is_available else "!"
            with columns[index % 4]:
                file_card_html = (
                    '<article class="admin-v3-file-card" '
                    f'style="--file-accent:{accent};">'
                    f'<div class="admin-v3-file-icon">{escape(str(row["Ikon"]))}</div>'
                    f'<div class="admin-v3-file-title">{escape(str(row["Jenis Data"]))}</div>'
                    f'<div class="admin-v3-file-path">{escape(str(row["File"]))}</div>'
                    '<div class="admin-v3-file-bottom">'
                    f'<span class="admin-v3-status-pill {status_class}">'
                    f'{status_icon} {escape(str(row["Status"]))}</span>'
                    f'<span class="admin-v3-file-size">{escape(str(row["Ukuran"]))}</span>'
                    '</div></article>'
                )
                st.markdown(file_card_html, unsafe_allow_html=True)
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
                {"icon": "🛡️", "label": "Total Administrator", "value": stats.get("total_admin", 0), "color": "#AB47BC"},
                {"icon": "🆕", "label": "Pengguna Baru Bulan Ini", "value": _count_new_users_this_month(users), "color": "#FF9800"},
                {"icon": "🗂️", "label": "File Data Tersedia", "value": f"{available_count}/{total_files}", "color": "#4CAF50"},
            ]
        )

        chart_col, insight_col = st.columns([2.15, 1], gap="large")
        with chart_col:
            _render_registration_chart(users)
        with insight_col:
            latest_user = escape(str(stats.get("latest_user") or "Belum ada pengguna"))
            admin_total = int(stats.get("total_admin", 0) or 0)
            total_user = max(int(stats.get("total_users", len(users)) or 0), 1)
            admin_ratio = round((admin_total / total_user) * 100)
            file_ratio = round((available_count / total_files) * 100) if total_files else 0
            st.markdown(
                f"""
                <div class="admin-v3-file-card" style="--file-accent:#1DA1F2; min-height: 305px;">
                    <div class="admin-v3-file-icon">💡</div>
                    <div class="admin-v3-file-title">Ringkasan Sistem</div>
                    <div class="admin-v3-file-path" style="font-family:Inter,sans-serif; font-size:.78rem;">
                        Pengguna terbaru: <strong style="color:var(--app-text);">{latest_user}</strong>
                    </div>
                    <div class="admin-v3-user-meta">Komposisi administrator</div>
                    <div class="admin-v3-progress-shell"><div class="admin-v3-progress-fill" style="width:{admin_ratio}%; background:linear-gradient(90deg,#AB47BC,#E53935);"></div></div>
                    <div class="admin-v3-file-size">{admin_ratio}% dari seluruh akun</div>
                    <div class="admin-v3-user-meta" style="margin-top:1rem;">Kesiapan file penelitian</div>
                    <div class="admin-v3-progress-shell"><div class="admin-v3-progress-fill" style="width:{file_ratio}%;"></div></div>
                    <div class="admin-v3-file-size">{available_count} dari {total_files} file tersedia</div>
                </div>
                """,
                unsafe_allow_html=True,
            )

        _render_section_header(
            "📁",
            "Status File Data",
            "File CSV terkompresi (.csv.gz) tetap dihitung tersedia dan dapat digunakan oleh aplikasi.",
            "purple",
        )
        _render_file_cards(status_table)

        if available_count == total_files and total_files > 0:
            st.success("✅ Seluruh file data yang dibutuhkan tersedia dan siap digunakan.")
        else:
            missing = max(total_files - available_count, 0)
            st.warning(
                f"⚠️ {missing} dari {total_files} file data belum tersedia. Halaman analitik terkait akan menggunakan data fallback bila diperlukan."
            )
    except Exception as error:
        st.error(f"Gagal memuat statistik sistem: {error}")


def _render_activity_log_tab() -> None:
    """Render aktivitas registrasi terbaru dan ringkasan kesehatan sistem."""
    try:
        _render_section_header(
            "🧾",
            "Aktivitas & Audit Ringkas",
            "Lihat registrasi akun terbaru serta kondisi komponen penting yang digunakan dashboard.",
            "orange",
        )

        users = get_all_users()
        stats = get_user_stats()
        status_table = _build_file_status_table()
        available_count = int(status_table["Tersedia"].sum()) if not status_table.empty else 0
        total_files = len(status_table)

        _render_metric_cards(
            [
                {"icon": "👥", "label": "Total Akun", "value": stats.get("total_users", len(users)), "color": "#E53935"},
                {"icon": "🛡️", "label": "Akun Admin", "value": stats.get("total_admin", 0), "color": "#AB47BC"},
                {"icon": "🗃️", "label": "Database Pengguna", "value": "Aktif", "color": "#4CAF50"},
                {"icon": "📁", "label": "Kesiapan Data", "value": f"{available_count}/{total_files}", "color": "#FF9800"},
            ]
        )

        activity_col, health_col = st.columns([1.55, 1], gap="large")
        with activity_col:
            st.markdown("#### 🕒 Registrasi Akun Terbaru")
            sorted_users = sorted(
                users,
                key=lambda item: _parse_created_at(item.get("created_at")) or pd.Timestamp.min,
                reverse=True,
            )[:6]

            if not sorted_users:
                st.markdown('<div class="admin-v3-empty">Belum ada aktivitas registrasi akun.</div>', unsafe_allow_html=True)
            else:
                for user in sorted_users:
                    role = str(user.get("role", "user")).title()
                    st.markdown(
                        f"""
                        <div class="admin-v3-activity-item">
                            <div class="admin-v3-activity-icon">👤</div>
                            <div>
                                <div class="admin-v3-activity-title">{escape(str(user.get('fullname', '-')))} bergabung sebagai {escape(role)}</div>
                                <div class="admin-v3-activity-meta">@{escape(str(user.get('username', '-')))} · {escape(format_created_at(user.get('created_at')))}</div>
                            </div>
                        </div>
                        """,
                        unsafe_allow_html=True,
                    )

        with health_col:
            st.markdown("#### 🩺 Pemeriksaan Komponen")
            checks = [
                ("🗃️", "Database pengguna", "Terhubung", "Data akun dapat dibaca oleh sistem."),
                ("🔐", "Kontrol akses", "Aktif", "Halaman hanya dapat dibuka oleh administrator."),
                ("📊", "Mesin visualisasi", "Aktif", "Plotly siap menampilkan statistik sistem."),
                ("📁", "File penelitian", f"{available_count}/{total_files} tersedia", "Fallback tetap tersedia saat file belum lengkap."),
            ]
            for icon, title, status, detail in checks:
                st.markdown(
                    f"""
                    <div class="admin-v3-activity-item">
                        <div class="admin-v3-activity-icon">{escape(icon)}</div>
                        <div>
                            <div class="admin-v3-activity-title">{escape(title)} · <span style="color:#66BB6A;">{escape(status)}</span></div>
                            <div class="admin-v3-activity-meta">{escape(detail)}</div>
                        </div>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )

            st.info(
                "Catatan audit terperinci belum disimpan sebagai tabel terpisah. Bagian ini menampilkan informasi aktual yang tersedia dari database pengguna dan file proyek."
            )
    except Exception as error:
        st.error(f"Gagal memuat aktivitas sistem: {error}")


def render_admin_panel() -> None:
    """Tampilkan Admin Panel dan hentikan akses untuk role selain admin."""
    try:
        if st.session_state.get("role") != "admin":
            st.error("⛔ Akses ditolak. Halaman ini hanya dapat dibuka oleh administrator.")
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
