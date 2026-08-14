"""Halaman profil dan manajemen akun pengguna dashboard Telkom Group.

Fase 11 — Redesign Profile & User Management.
Fokus file ini adalah tampilan dan interaksi halaman profil tanpa mengubah
alur login, register, maupun routing utama aplikasi.
"""

from __future__ import annotations

import base64
import html
import re
import sqlite3
from datetime import datetime
from io import BytesIO
from pathlib import Path
from textwrap import dedent
from typing import Any

import streamlit as st
from PIL import Image, ImageFile, ImageOps, UnidentifiedImageError

from auth.auth_utils import (
    delete_user,
    get_db_path,
    get_user_by_id,
    hash_password,
    revoke_all_remember_tokens,
    revoke_remember_token,
    update_profile,
    update_profile_picture,
    verify_password,
)
from utils.access_control import DEFAULT_ROLE, get_role_label, normalize_role
from utils.css_loader import render_page_header
from utils.loading_screen import mulai_loading_aksi, selesaikan_loading_aksi

# -----------------------------------------------------------------------------
# Konfigurasi dasar halaman profil
# -----------------------------------------------------------------------------

ImageFile.LOAD_TRUNCATED_IMAGES = False
Image.MAX_IMAGE_PIXELS = 25_000_000

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_AVATAR_PATH = PROJECT_ROOT / "assets" / "default_avatar.png"
MAX_AVATAR_SIZE_BYTES = 2 * 1024 * 1024
AVATAR_OUTPUT_SIZE = (200, 200)
ALLOWED_IMAGE_TYPES = {"image/jpeg", "image/jpg", "image/png"}
EMAIL_PATTERN = re.compile(
    r"^[A-Za-z0-9.!#$%&'*+/=?^_`{|}~-]+@[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)+$"
)

MONTH_NAMES_ID = {
    1: "Januari",
    2: "Februari",
    3: "Maret",
    4: "April",
    5: "Mei",
    6: "Juni",
    7: "Juli",
    8: "Agustus",
    9: "September",
    10: "Oktober",
    11: "November",
    12: "Desember",
}

STATE_AVATAR_UPLOAD_EVENT_ID = "profile_v11_avatar_upload_event_id"
STATE_AVATAR_UPLOAD_COMPLETED_ID = "profile_v11_avatar_upload_completed_id"
STATE_AVATAR_UPLOAD_LOADING_LABEL = "profile_v11_avatar_upload_loading_label"


def _antrekan_loading_upload_foto(label: str) -> None:
    """Antrekan custom loading dan paksa expander foto tetap terbuka satu siklus."""
    event_id = int(st.session_state.get(STATE_AVATAR_UPLOAD_EVENT_ID, 0)) + 1
    st.session_state[STATE_AVATAR_UPLOAD_EVENT_ID] = event_id
    st.session_state[STATE_AVATAR_UPLOAD_LOADING_LABEL] = str(label).strip() or "Memproses foto profil..."


def _status_loading_upload_foto() -> tuple[int, bool, str]:
    """Ambil ID event, status pending, dan label loading upload foto."""
    event_id = int(st.session_state.get(STATE_AVATAR_UPLOAD_EVENT_ID, 0))
    completed_id = int(st.session_state.get(STATE_AVATAR_UPLOAD_COMPLETED_ID, 0))
    label = str(
        st.session_state.get(
            STATE_AVATAR_UPLOAD_LOADING_LABEL,
            "Memproses foto profil...",
        )
    )
    return event_id, event_id > completed_id, label


# -----------------------------------------------------------------------------
# CSS khusus halaman profil
# -----------------------------------------------------------------------------


def _inject_profile_css() -> None:
    """Sisipkan CSS khusus halaman profil yang mengikuti tema global dashboard."""
    try:
        st.markdown(
            """
            <style>
                @import url('https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700;800&display=swap');

                :root {
                    --profile-bg-main: var(--app-bg, #0B0F17);
                    --profile-bg-card: var(--app-card, #151B26);
                    --profile-bg-card-soft: var(--app-secondary, #1E293B);
                    --profile-bg-input: var(--app-input, #111827);
                    --profile-primary: var(--app-primary, #E53935);
                    --profile-primary-hover: #FF5252;
                    --profile-primary-dark: var(--app-accent, #B71C1C);
                    --profile-border: var(--app-border, #2A3648);
                    --profile-text: var(--app-text, #F8FAFC);
                    --profile-muted: var(--app-muted, #A7B0BF);
                    --profile-muted-dark: color-mix(in srgb, var(--app-muted, #A7B0BF) 68%, transparent);
                    --profile-success: var(--app-positive, #4CAF50);
                    --profile-warning: var(--app-neutral, #FF9800);
                    --profile-danger: var(--app-negative, #F44336);
                }

                .profile-v11-wrapper,
                .profile-v11-wrapper * {
                    font-family: 'Plus Jakarta Sans', sans-serif;
                }

                /* Header profil dibuat mengikuti pola header halaman lain: compact, responsive, dan tidak memakai iframe. */
                .banner-header {
                    position: relative;
                    overflow: hidden;
                    min-height: auto !important;
                    margin-bottom: 1.25rem !important;
                    padding: clamp(1.35rem, 2.2vw, 1.75rem) clamp(1.35rem, 2.4vw, 2rem) !important;
                    border-radius: 14px !important;
                    border: 1px solid rgba(255, 255, 255, 0.12) !important;
                    background:
                        radial-gradient(circle at 92% 8%, rgba(255, 255, 255, 0.18), transparent 30%),
                        radial-gradient(circle at 7% 70%, rgba(255, 255, 255, 0.10), transparent 24%),
                        linear-gradient(135deg, #B71C1C 0%, #E53935 56%, #F05A56 100%) !important;
                    box-shadow: 0 12px 30px rgba(183, 28, 28, 0.18) !important;
                    text-shadow: 0 1px 3px rgba(0, 0, 0, 0.24) !important;
                }

                .banner-header::before {
                    content: '';
                    position: absolute;
                    inset: 0;
                    background:
                        linear-gradient(90deg, rgba(255,255,255,0.20), rgba(255,255,255,0) 42%),
                        repeating-linear-gradient(135deg, rgba(255,255,255,0.055) 0 1px, transparent 1px 15px);
                    pointer-events: none;
                }

                .banner-header h1,
                .banner-header p {
                    position: relative;
                    z-index: 1;
                    font-family: 'Plus Jakarta Sans', sans-serif !important;
                }

                .banner-header h1 {
                    font-size: clamp(1.45rem, 2.25vw, 1.85rem) !important;
                    line-height: 1.25 !important;
                    font-weight: 800 !important;
                    letter-spacing: -0.03em !important;
                }

                .banner-header p {
                    max-width: 920px;
                    margin-top: 0.6rem !important;
                    font-size: clamp(0.9rem, 1.2vw, 1rem) !important;
                    line-height: 1.6 !important;
                    font-weight: 500 !important;
                    opacity: 0.95 !important;
                }

                .profile-v11-grid {
                    display: grid;
                    grid-template-columns: minmax(280px, 0.9fr) minmax(360px, 1.7fr);
                    gap: 1.1rem;
                    align-items: stretch;
                    margin-bottom: 1.1rem;
                }

                .profile-v11-card {
                    position: relative;
                    background:
                        radial-gradient(circle at top left, rgba(229, 57, 53, 0.10), transparent 34%),
                        var(--profile-bg-card);
                    border: 1px solid var(--profile-border);
                    border-radius: 12px;
                    padding: 1.25rem;
                    color: var(--profile-text);
                    box-shadow: 0 18px 36px rgba(0, 0, 0, 0.24);
                    transition: border-color 0.18s ease, box-shadow 0.18s ease, transform 0.18s ease;
                }

                .profile-v11-card:hover {
                    border-color: rgba(229, 57, 53, 0.70);
                    box-shadow: 0 18px 44px rgba(229, 57, 53, 0.11);
                    transform: translateY(-1px);
                }

                .profile-v11-card-title {
                    display: flex;
                    align-items: center;
                    gap: 0.55rem;
                    margin: 0 0 0.35rem 0;
                    font-family: 'Plus Jakarta Sans', sans-serif;
                    font-size: 1.12rem;
                    font-weight: 800;
                    letter-spacing: -0.01em;
                    color: var(--profile-text);
                }

                .profile-v11-note {
                    margin: 0 0 0.95rem 0;
                    color: var(--profile-muted);
                    font-size: 0.92rem;
                    line-height: 1.55;
                }

                .profile-v11-identity {
                    display: flex;
                    flex-direction: column;
                    align-items: center;
                    text-align: center;
                    min-height: 100%;
                }

                .profile-v11-avatar {
                    width: 80px;
                    height: 80px;
                    display: flex;
                    align-items: center;
                    justify-content: center;
                    border-radius: 50%;
                    background: linear-gradient(135deg, #E53935, #B71C1C);
                    color: #FFFFFF;
                    font-family: 'Plus Jakarta Sans', sans-serif;
                    font-size: 28px;
                    font-weight: 800;
                    line-height: 1;
                    box-shadow: 0 0 0 6px rgba(229, 57, 53, 0.10), 0 14px 30px rgba(183, 28, 28, 0.35);
                    margin-bottom: 0.95rem;
                    user-select: none;
                }

                .profile-v11-fullname {
                    margin: 0;
                    color: #FFFFFF;
                    font-family: 'Plus Jakarta Sans', sans-serif;
                    font-size: 22px;
                    font-weight: 800;
                    line-height: 1.25;
                    overflow-wrap: anywhere;
                }

                .profile-v11-username {
                    margin: 0.25rem 0 0.75rem 0;
                    color: var(--profile-muted);
                    font-size: 0.95rem;
                    font-weight: 500;
                    overflow-wrap: anywhere;
                }

                .profile-v11-badge-row {
                    display: flex;
                    flex-wrap: wrap;
                    justify-content: center;
                    gap: 0.45rem;
                    margin-bottom: 0.9rem;
                }

                .profile-v11-badge {
                    display: inline-flex;
                    align-items: center;
                    justify-content: center;
                    padding: 0.34rem 0.76rem;
                    border-radius: 20px;
                    border: 1px solid rgba(255, 82, 82, 0.24);
                    background: #2C0000;
                    color: #FF5252;
                    font-size: 0.78rem;
                    font-weight: 800;
                    letter-spacing: 0.01em;
                }

                .profile-v11-role-badge {
                    background: rgba(255, 255, 255, 0.055);
                    border-color: rgba(255, 255, 255, 0.10);
                    color: var(--profile-muted);
                }

                .profile-v11-joined {
                    width: 100%;
                    margin-top: auto;
                    padding-top: 0.95rem;
                    border-top: 1px solid var(--profile-border);
                    color: var(--profile-muted);
                    font-size: 0.84rem;
                    line-height: 1.5;
                }

                .profile-v11-metric-grid {
                    display: grid;
                    grid-template-columns: repeat(2, minmax(0, 1fr));
                    gap: 0.85rem;
                    margin-top: 0.85rem;
                }

                .profile-v11-metric-card {
                    min-height: 104px;
                    border-left: 3px solid #E53935;
                    border-top: 1px solid var(--profile-border);
                    border-right: 1px solid var(--profile-border);
                    border-bottom: 1px solid var(--profile-border);
                    border-radius: 12px;
                    background: var(--profile-bg-card);
                    padding: 0.95rem 1rem;
                }

                .profile-v11-metric-label {
                    color: var(--profile-muted);
                    font-size: 0.84rem;
                    font-weight: 700;
                    margin-bottom: 0.35rem;
                }

                .profile-v11-metric-value {
                    color: #E53935;
                    font-family: 'Plus Jakarta Sans', sans-serif;
                    font-size: 32px;
                    line-height: 1.05;
                    font-weight: 800;
                    overflow-wrap: anywhere;
                }

                .profile-v11-metric-subtitle {
                    margin-top: 0.35rem;
                    color: var(--profile-muted-dark);
                    font-size: 0.79rem;
                    line-height: 1.4;
                }

                .profile-v11-section-space {
                    margin-top: 1rem;
                }

                .profile-v11-strength-shell {
                    width: 100%;
                    height: 10px;
                    overflow: hidden;
                    border-radius: 999px;
                    border: 1px solid var(--profile-border);
                    background: var(--profile-bg-input);
                    margin: 0.35rem 0 0.3rem 0;
                }

                .profile-v11-strength-fill {
                    height: 100%;
                    border-radius: 999px;
                    transition: width 0.18s ease;
                }

                .profile-v11-strength-meta {
                    display: flex;
                    justify-content: space-between;
                    align-items: center;
                    gap: 0.75rem;
                    color: var(--profile-muted);
                    font-size: 0.84rem;
                    margin-bottom: 0.75rem;
                }

                .profile-v11-danger-card {
                    border: 1px solid rgba(244, 67, 54, 0.55);
                    border-radius: 12px;
                    background:
                        radial-gradient(circle at top right, rgba(244, 67, 54, 0.11), transparent 38%),
                        var(--profile-bg-card);
                    padding: 1.25rem;
                    margin-top: 1rem;
                }

                .profile-v11-danger-title {
                    color: #FF5252;
                    font-family: 'Plus Jakarta Sans', sans-serif;
                    font-size: 1.08rem;
                    font-weight: 800;
                    margin-bottom: 0.35rem;
                }

                .profile-v11-danger-text {
                    color: var(--profile-muted);
                    font-size: 0.91rem;
                    line-height: 1.55;
                    margin-bottom: 0.95rem;
                }

                .profile-v11-mini-divider {
                    height: 1px;
                    background: var(--profile-border);
                    margin: 1rem 0;
                }

                /* V6: polishing profile card + statistik agar lebih premium namun tetap konsisten dengan halaman lain. */
                .profile-v11-profile-card {
                    overflow: hidden;
                    min-height: 508px;
                    padding: 1.65rem 1.55rem 1.45rem 1.55rem;
                    background:
                        radial-gradient(circle at 50% 8%, rgba(229, 57, 53, 0.22), transparent 22%),
                        radial-gradient(circle at 0% 0%, rgba(229, 57, 53, 0.14), transparent 36%),
                        linear-gradient(145deg, rgba(21, 27, 38, 0.98), rgba(12, 18, 29, 0.98));
                    border-color: rgba(94, 114, 143, 0.55);
                }

                .profile-v11-profile-card::before {
                    content: '';
                    position: absolute;
                    inset: 0;
                    background:
                        radial-gradient(circle at 18% 12%, rgba(255, 82, 82, 0.22), transparent 7%),
                        radial-gradient(circle at 80% 86%, rgba(229, 57, 53, 0.10), transparent 22%),
                        repeating-linear-gradient(135deg, rgba(255, 255, 255, 0.035) 0 1px, transparent 1px 14px);
                    opacity: 0.72;
                    pointer-events: none;
                }

                .profile-v11-profile-card::after {
                    content: '';
                    position: absolute;
                    left: 0;
                    top: 0;
                    width: 4px;
                    height: 100%;
                    background: linear-gradient(180deg, #FF5252, rgba(229, 57, 53, 0.25), transparent);
                    box-shadow: 0 0 22px rgba(229, 57, 53, 0.55);
                    pointer-events: none;
                }

                .profile-v11-profile-card > * {
                    position: relative;
                    z-index: 1;
                }

                .profile-v11-avatar-wrap {
                    position: relative;
                    width: 132px;
                    height: 132px;
                    display: flex;
                    align-items: center;
                    justify-content: center;
                    margin: 0.2rem auto 1.2rem auto;
                    border-radius: 50%;
                    background:
                        conic-gradient(from 210deg, rgba(255,255,255,0.55), rgba(229,57,53,0.1), rgba(255,82,82,0.85), rgba(255,255,255,0.30));
                    box-shadow: 0 0 0 1px rgba(255, 82, 82, 0.15), 0 22px 52px rgba(229, 57, 53, 0.24);
                }

                .profile-v11-avatar-wrap::before {
                    content: '';
                    position: absolute;
                    inset: 10px;
                    border-radius: 50%;
                    background: rgba(10, 14, 22, 0.92);
                }

                .profile-v11-avatar {
                    position: relative;
                    z-index: 1;
                    width: 108px;
                    height: 108px;
                    margin: 0;
                    font-size: 42px;
                    background: radial-gradient(circle at 28% 18%, #FF6B6B, #E53935 42%, #B71C1C 100%);
                    box-shadow:
                        inset 0 1px 0 rgba(255, 255, 255, 0.28),
                        0 0 0 7px rgba(229, 57, 53, 0.12),
                        0 18px 34px rgba(183, 28, 28, 0.42);
                }

                .profile-v11-fullname {
                    font-size: clamp(1.45rem, 2.1vw, 1.85rem);
                    letter-spacing: -0.045em;
                    text-shadow: 0 8px 22px rgba(0, 0, 0, 0.35);
                }

                .profile-v11-username {
                    margin-top: 0.42rem;
                    margin-bottom: 1.05rem;
                    color: #C6D0E1;
                    font-weight: 600;
                }

                .profile-v11-badge-row {
                    gap: 0.62rem;
                    margin-bottom: 1.3rem;
                }

                .profile-v11-badge {
                    min-height: 40px;
                    gap: 0.45rem;
                    padding: 0.52rem 0.96rem;
                    border-radius: 999px;
                    font-size: 0.86rem;
                    box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.14);
                }

                .profile-v11-badge-primary {
                    color: #FFFFFF;
                    border-color: rgba(255, 82, 82, 0.72);
                    background: linear-gradient(135deg, rgba(229,57,53,0.96), rgba(183,28,28,0.92));
                    box-shadow: 0 10px 24px rgba(229, 57, 53, 0.22), inset 0 1px 0 rgba(255, 255, 255, 0.16);
                }

                .profile-v11-role-badge {
                    color: #F8FAFC;
                    border-color: rgba(255, 255, 255, 0.16);
                    background: linear-gradient(135deg, rgba(255,255,255,0.12), rgba(255,255,255,0.05));
                }

                .profile-v11-badge-icon {
                    display: inline-flex;
                    align-items: center;
                    justify-content: center;
                    width: 18px;
                    height: 18px;
                    font-size: 0.88rem;
                    line-height: 1;
                }

                .profile-v11-joined {
                    display: grid;
                    grid-template-columns: 48px 1fr;
                    align-items: center;
                    gap: 0.78rem;
                    margin-top: auto;
                    padding: 1.05rem 0 0 0;
                    border-top: 1px solid rgba(167, 176, 191, 0.16);
                    text-align: left;
                    color: #C6D0E1;
                }

                .profile-v11-joined-icon {
                    width: 46px;
                    height: 46px;
                    display: flex;
                    align-items: center;
                    justify-content: center;
                    border-radius: 14px;
                    border: 1px solid rgba(255, 82, 82, 0.30);
                    background: rgba(229, 57, 53, 0.10);
                    color: #FF5252;
                    font-size: 1.1rem;
                    box-shadow: 0 12px 24px rgba(229, 57, 53, 0.10);
                }

                .profile-v11-joined strong {
                    display: block;
                    color: #AFC0D7;
                    font-size: 0.82rem;
                    margin-bottom: 0.15rem;
                }

                .profile-v11-joined span {
                    display: block;
                    color: #FFFFFF;
                    font-size: 0.98rem;
                    font-weight: 800;
                    letter-spacing: -0.01em;
                }

                .profile-v11-section-gap {
                    height: 18px;
                }

                [data-testid="stExpander"] {
                    overflow: hidden;
                    border-color: rgba(94, 114, 143, 0.60) !important;
                    background: linear-gradient(145deg, rgba(21, 27, 38, 0.96), rgba(12, 18, 29, 0.96)) !important;
                    box-shadow: 0 14px 32px rgba(0, 0, 0, 0.22) !important;
                }

                [data-testid="stExpander"] summary {
                    font-weight: 800 !important;
                    color: #F8FAFC !important;
                }

                .profile-v11-stats-card {
                    overflow: hidden;
                    /* Samakan tinggi kartu Statistik Penggunaan dengan kartu profil di kolom kiri. */
                    min-height: 508px;
                    /* Isi kartu ikut mengisi tinggi kartu agar tidak menyisakan ruang kosong di bagian bawah. */
                    display: flex;
                    flex-direction: column;
                    padding: clamp(1.35rem, 2vw, 1.65rem);
                    background:
                        radial-gradient(circle at 92% 8%, rgba(229, 57, 53, 0.12), transparent 27%),
                        radial-gradient(circle at 8% 92%, rgba(255, 82, 82, 0.08), transparent 24%),
                        linear-gradient(145deg, rgba(21, 27, 38, 0.98), rgba(10, 15, 24, 0.99));
                    border-color: rgba(94, 114, 143, 0.52);
                }

                .profile-v11-stats-card::before {
                    content: '';
                    position: absolute;
                    inset: 0;
                    background:
                        linear-gradient(120deg, rgba(255,255,255,0.055), transparent 38%),
                        radial-gradient(circle at 86% 76%, rgba(229, 57, 53, 0.11), transparent 25%);
                    pointer-events: none;
                }

                .profile-v11-stats-card > * {
                    position: relative;
                    z-index: 1;
                }

                .profile-v11-stats-heading {
                    display: grid;
                    grid-template-columns: 56px 1fr;
                    gap: 0.86rem;
                    align-items: center;
                    margin-bottom: 0.85rem;
                }

                .profile-v11-stats-icon {
                    width: 52px;
                    height: 52px;
                    display: flex;
                    align-items: end;
                    justify-content: center;
                    gap: 4px;
                    padding-bottom: 12px;
                    border-radius: 16px;
                    border: 1px solid rgba(255, 82, 82, 0.38);
                    background: linear-gradient(145deg, rgba(229,57,53,0.24), rgba(255,255,255,0.04));
                    box-shadow: 0 14px 32px rgba(229, 57, 53, 0.14), inset 0 1px 0 rgba(255, 255, 255, 0.12);
                }

                .profile-v11-stats-icon span {
                    display: block;
                    width: 6px;
                    border-radius: 999px 999px 2px 2px;
                    background: linear-gradient(180deg, #FF8A80, #E53935);
                    box-shadow: 0 0 10px rgba(229, 57, 53, 0.42);
                }

                .profile-v11-stats-icon span:nth-child(1) { height: 14px; }
                .profile-v11-stats-icon span:nth-child(2) { height: 22px; }
                .profile-v11-stats-icon span:nth-child(3) { height: 30px; }

                .profile-v11-stats-title {
                    margin: 0;
                    font-size: clamp(1.35rem, 2.2vw, 1.75rem);
                    line-height: 1.22;
                    font-weight: 800;
                    letter-spacing: -0.04em;
                    color: #FFFFFF;
                    text-shadow: 0 8px 22px rgba(0, 0, 0, 0.35);
                }

                .profile-v11-stats-note {
                    margin: 0.55rem 0 1.35rem 0;
                    max-width: 920px;
                    color: #B9C4D6;
                    font-size: 0.95rem;
                    line-height: 1.68;
                    font-weight: 500;
                }

                .profile-v11-metric-grid {
                    gap: 1rem;
                    margin-top: 1rem;
                    flex: 1 1 auto;
                    min-height: 0;
                    align-items: stretch;
                    grid-auto-rows: 1fr;
                }

                .profile-v11-metric-card {
                    position: relative;
                    overflow: hidden;
                    min-height: 170px;
                    height: 100%;
                    display: flex;
                    flex-direction: column;
                    padding: 1.12rem 1.15rem;
                    border: 1px solid rgba(255, 82, 82, 0.38);
                    border-radius: 16px;
                    background:
                        radial-gradient(circle at top right, rgba(229, 57, 53, 0.14), transparent 24%),
                        linear-gradient(145deg, rgba(17, 24, 39, 0.98), rgba(11, 16, 26, 0.98));
                    box-shadow: 0 18px 36px rgba(0, 0, 0, 0.18), inset 0 1px 0 rgba(255, 255, 255, 0.05);
                    border-left-width: 1px;
                }

                .profile-v11-metric-card::before {
                    content: '';
                    position: absolute;
                    left: 0;
                    top: 0;
                    width: 3px;
                    height: 100%;
                    background: linear-gradient(180deg, #FF5252, #E53935, rgba(229, 57, 53, 0.18));
                    box-shadow: 0 0 18px rgba(229, 57, 53, 0.52);
                }

                .profile-v11-metric-card::after {
                    content: '';
                    position: absolute;
                    right: 0.65rem;
                    top: 0.55rem;
                    width: 92px;
                    height: 92px;
                    opacity: 0.17;
                    background-image: radial-gradient(#FF5252 1px, transparent 1px);
                    background-size: 8px 8px;
                    pointer-events: none;
                }

                .profile-v11-metric-head {
                    position: relative;
                    z-index: 1;
                    display: flex;
                    align-items: center;
                    gap: 0.72rem;
                    margin-bottom: 1.05rem;
                }

                .profile-v11-metric-icon {
                    width: 42px;
                    height: 42px;
                    display: flex;
                    align-items: center;
                    justify-content: center;
                    flex: 0 0 auto;
                    border-radius: 13px;
                    color: #FF8A80;
                    border: 1px solid rgba(255, 82, 82, 0.33);
                    background: rgba(229, 57, 53, 0.10);
                    box-shadow: inset 0 1px 0 rgba(255,255,255,0.09);
                }

                .profile-v11-metric-label {
                    margin: 0;
                    color: #E6ECF5;
                    font-size: 0.95rem;
                    font-weight: 800;
                    letter-spacing: -0.01em;
                }

                .profile-v11-metric-value {
                    position: relative;
                    z-index: 1;
                    color: #FF4545;
                    font-size: clamp(2.25rem, 4vw, 3.2rem);
                    line-height: 1;
                    letter-spacing: -0.055em;
                    text-shadow: 0 14px 34px rgba(229, 57, 53, 0.30);
                }

                .profile-v11-metric-value.profile-v11-date-value {
                    font-size: clamp(1.5rem, 2.4vw, 2.15rem);
                    line-height: 1.12;
                    letter-spacing: -0.045em;
                }

                .profile-v11-metric-accent-line {
                    width: 54px;
                    height: 3px;
                    border-radius: 999px;
                    margin: 0.72rem 0 0.68rem 0;
                    background: linear-gradient(90deg, #FF5252, rgba(255, 82, 82, 0));
                    box-shadow: 0 0 14px rgba(229, 57, 53, 0.50);
                }

                .profile-v11-metric-subtitle {
                    position: relative;
                    z-index: 1;
                    color: #9EABBE;
                    font-size: 0.84rem;
                    line-height: 1.52;
                    margin: auto 0 0 0;
                }

                /* Input dan tombol dibuat selaras dengan tema halaman lain. */
                [data-testid="stTextInput"] input {
                    background: var(--profile-bg-input) !important;
                    border: 1px solid var(--profile-border) !important;
                    border-radius: 8px !important;
                    color: var(--profile-text) !important;
                }

                [data-testid="stTextInput"] input:focus {
                    border-color: #E53935 !important;
                    box-shadow: 0 0 0 1px rgba(229, 57, 53, 0.35) !important;
                }

                div[data-testid="stButton"] button[kind="primary"],
                div[data-testid="stFormSubmitButton"] button[kind="primary"] {
                    background: #E53935 !important;
                    border: 1px solid #E53935 !important;
                    border-radius: 8px !important;
                    color: var(--profile-text) !important;
                    font-weight: 700 !important;
                }

                div[data-testid="stButton"] button[kind="primary"]:hover,
                div[data-testid="stFormSubmitButton"] button[kind="primary"]:hover {
                    background: #FF5252 !important;
                    border-color: #FF5252 !important;
                }

                div[data-testid="stButton"] button[kind="secondary"] {
                    background: transparent !important;
                    border: 1px solid #E53935 !important;
                    border-radius: 8px !important;
                    color: #FF5252 !important;
                    font-weight: 800 !important;
                }

                div[data-testid="stButton"] button[kind="secondary"]:hover {
                    background: rgba(229, 57, 53, 0.10) !important;
                    border-color: #FF5252 !important;
                    color: var(--profile-text) !important;
                }

                [data-testid="stExpander"] {
                    border: 1px solid var(--profile-border) !important;
                    border-radius: 12px !important;
                    background: #1A1A1A !important;
                }

                [data-testid="stImage"] img {
                    border-radius: 50%;
                    object-fit: cover;
                    border: 3px solid #E53935;
                    box-shadow: 0 0 0 5px rgba(229, 57, 53, 0.10);
                }



                /* V10: layout foto profil opsional dibuat melebar, tidak menumpuk ke bawah. */
                .profile-v11-section-gap {
                    height: 20px;
                }

                .profile-v11-avatar-upload-intro {
                    display: grid;
                    grid-template-columns: 52px minmax(0, 1fr) auto;
                    gap: 0.95rem;
                    align-items: center;
                    padding: 0.95rem 1rem;
                    margin: 0.15rem 0 0.95rem 0;
                    border: 1px solid rgba(229, 57, 53, 0.28);
                    border-radius: 16px;
                    background:
                        radial-gradient(circle at 0% 0%, rgba(229, 57, 53, 0.18), transparent 40%),
                        linear-gradient(135deg, rgba(229, 57, 53, 0.08), rgba(255, 255, 255, 0.025));
                    box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.07), 0 14px 26px rgba(0, 0, 0, 0.18);
                }

                .profile-v11-avatar-upload-icon {
                    width: 52px;
                    height: 52px;
                    display: flex;
                    align-items: center;
                    justify-content: center;
                    border-radius: 16px;
                    background: linear-gradient(135deg, rgba(229, 57, 53, 0.96), rgba(183, 28, 28, 0.90));
                    color: #FFFFFF;
                    font-size: 1.25rem;
                    box-shadow: 0 14px 28px rgba(229, 57, 53, 0.22), inset 0 1px 0 rgba(255,255,255,0.22);
                }

                .profile-v11-avatar-upload-title {
                    margin: 0;
                    color: #FFFFFF;
                    font-size: 1.04rem;
                    font-weight: 800;
                    letter-spacing: -0.02em;
                }

                .profile-v11-avatar-upload-desc {
                    margin: 0.24rem 0 0 0;
                    color: #B9C6D8;
                    font-size: 0.86rem;
                    line-height: 1.48;
                    max-width: 760px;
                }

                .profile-v11-upload-tip-grid {
                    display: grid;
                    grid-template-columns: repeat(3, minmax(96px, 1fr));
                    gap: 0.55rem;
                    min-width: 330px;
                    margin: 0;
                }

                .profile-v11-upload-tip {
                    display: flex;
                    gap: 0.42rem;
                    align-items: center;
                    justify-content: center;
                    min-height: 44px;
                    padding: 0.55rem 0.7rem;
                    border-radius: 14px;
                    border: 1px solid rgba(167, 176, 191, 0.18);
                    background: rgba(255, 255, 255, 0.035);
                    color: #D7E1F0;
                    font-size: 0.78rem;
                    font-weight: 800;
                    text-align: center;
                    white-space: nowrap;
                }

                .profile-v11-upload-tip span:first-child {
                    color: #FF5252;
                    font-size: 0.98rem;
                    line-height: 1;
                }

                .profile-v11-upload-panel-title {
                    color: #FFFFFF;
                    font-size: 1rem;
                    font-weight: 800;
                    margin: 0 0 0.35rem 0;
                    letter-spacing: -0.02em;
                }

                .profile-v11-upload-panel-note {
                    color: #9EABBE;
                    font-size: 0.82rem;
                    line-height: 1.45;
                    margin: 0 0 0.75rem 0;
                }

                /* V20.3: preview foto dibuat sebagai satu card utuh agar tidak muncul kotak kosong di atas foto. */
                .profile-v11-current-photo-card {
                    display: grid;
                    grid-template-columns: 118px minmax(0, 1fr);
                    gap: 1rem;
                    align-items: center;
                    min-height: 142px;
                    padding: 1rem;
                    margin-bottom: 1.1rem;
                    border-radius: 20px;
                    border: 1px solid rgba(229, 57, 53, 0.28);
                    background:
                        radial-gradient(circle at 8% 12%, rgba(229, 57, 53, 0.15), transparent 34%),
                        radial-gradient(circle at 100% 0%, rgba(255, 255, 255, 0.055), transparent 28%),
                        rgba(255, 255, 255, 0.035);
                    box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.06), 0 16px 32px rgba(0, 0, 0, 0.18);
                }

                /* V20.6: beri ruang bawah pada kartu foto tersimpan agar tidak menempel ke batas section. */
                .profile-v11-current-photo-bottom-gap {
                    height: 0.85rem;
                    min-height: 0.85rem;
                }

                .profile-v11-current-photo-frame {
                    width: 112px;
                    height: 112px;
                    display: flex;
                    align-items: center;
                    justify-content: center;
                    border-radius: 24px;
                    border: 1px solid rgba(229, 57, 53, 0.30);
                    background: linear-gradient(135deg, rgba(229, 57, 53, 0.09), rgba(255, 255, 255, 0.035));
                    box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.06);
                }

                .profile-v11-current-photo-img {
                    width: 92px;
                    height: 92px;
                    border-radius: 999px;
                    object-fit: cover;
                    border: 4px solid #E53935;
                    background: #FFFFFF;
                    box-shadow: 0 0 0 6px rgba(229, 57, 53, 0.14), 0 12px 24px rgba(0, 0, 0, 0.26);
                }

                .profile-v11-current-photo-placeholder {
                    width: 92px;
                    height: 92px;
                    border-radius: 999px;
                    display: flex;
                    align-items: center;
                    justify-content: center;
                    background: linear-gradient(135deg, #E53935, #B71C1C);
                    color: #FFFFFF;
                    font-size: 2rem;
                    font-weight: 900;
                    border: 4px solid rgba(255, 255, 255, 0.90);
                    box-shadow: 0 0 0 6px rgba(229, 57, 53, 0.14), 0 12px 24px rgba(0, 0, 0, 0.26);
                }

                .profile-v11-current-photo-content {
                    min-width: 0;
                }

                .profile-v11-current-photo-label {
                    display: inline-flex;
                    align-items: center;
                    gap: 0.42rem;
                    width: fit-content;
                    padding: 0.34rem 0.62rem;
                    margin-bottom: 0.56rem;
                    border-radius: 999px;
                    border: 1px solid rgba(76, 175, 80, 0.28);
                    background: rgba(76, 175, 80, 0.10);
                    color: #DFF7E6;
                    font-size: 0.76rem;
                    font-weight: 800;
                    line-height: 1;
                }

                .profile-v11-current-photo-label.is-default {
                    border-color: rgba(255, 152, 0, 0.30);
                    background: rgba(255, 152, 0, 0.10);
                    color: #FFE4B8;
                }

                .profile-v11-status-dot {
                    width: 8px;
                    height: 8px;
                    border-radius: 999px;
                    background: currentColor;
                    box-shadow: 0 0 0 4px rgba(76, 175, 80, 0.12);
                }

                .profile-v11-current-photo-heading {
                    margin: 0 0 0.28rem 0;
                    color: #FFFFFF;
                    font-size: 1rem;
                    font-weight: 850;
                    letter-spacing: -0.02em;
                }

                .profile-v11-current-photo-text {
                    margin: 0;
                    color: #AFC0D7;
                    font-size: 0.84rem;
                    line-height: 1.55;
                }

                .profile-v11-uploader-title {
                    display: flex;
                    align-items: center;
                    gap: 0.48rem;
                    margin: 0 0 0.35rem 0;
                    color: #FFFFFF;
                    font-size: 1rem;
                    font-weight: 800;
                    letter-spacing: -0.02em;
                }

                .profile-v11-uploader-helper {
                    margin: 0 0 0.65rem 0;
                    color: #9EABBE;
                    font-size: 0.82rem;
                    line-height: 1.45;
                }

                [data-testid="stExpander"] [data-testid="stFileUploader"] {
                    margin-top: 0.15rem;
                }

                [data-testid="stExpander"] [data-testid="stFileUploader"] section {
                    min-height: 156px;
                    display: grid !important;
                    grid-template-columns: minmax(0, 1fr) !important;
                    grid-auto-rows: max-content !important;
                    place-content: center !important;
                    place-items: center !important;
                    row-gap: 0.72rem !important;
                    padding: 1.35rem 1.25rem !important;
                    text-align: center !important;
                    border: 1.5px dashed rgba(255, 82, 82, 0.50) !important;
                    border-radius: 18px !important;
                    background:
                        radial-gradient(circle at 15% 20%, rgba(229, 57, 53, 0.12), transparent 35%),
                        linear-gradient(135deg, rgba(10, 15, 24, 0.92), rgba(17, 24, 39, 0.92)) !important;
                    box-shadow: inset 0 1px 0 rgba(255,255,255,0.06), 0 16px 30px rgba(0,0,0,0.18) !important;
                    transition: border-color 0.18s ease, box-shadow 0.18s ease, transform 0.18s ease;
                }

                [data-testid="stExpander"] [data-testid="stFileUploader"] section > div {
                    grid-column: 1 !important;
                    grid-row: 2 !important;
                    width: 100% !important;
                    min-width: 0 !important;
                    display: flex !important;
                    flex-direction: column !important;
                    align-items: center !important;
                    justify-content: center !important;
                    gap: 0.18rem !important;
                    margin: 0 !important;
                    padding: 0 !important;
                    text-align: center !important;
                }

                [data-testid="stExpander"] [data-testid="stFileUploader"] section > button {
                    grid-column: 1 !important;
                    grid-row: 1 !important;
                    align-self: center !important;
                    justify-self: center !important;
                    margin: 0 auto !important;
                }

                [data-testid="stExpander"] [data-testid="stFileUploader"] section small {
                    display: block !important;
                    width: 100% !important;
                    margin: 0 !important;
                    text-align: center !important;
                    line-height: 1.35 !important;
                }

                [data-testid="stExpander"] [data-testid="stFileUploader"] section:hover {
                    border-color: rgba(255, 82, 82, 0.92) !important;
                    box-shadow: inset 0 1px 0 rgba(255,255,255,0.08), 0 0 0 1px rgba(229,57,53,0.16), 0 18px 36px rgba(229,57,53,0.12) !important;
                    transform: translateY(-1px);
                }

                [data-testid="stExpander"] [data-testid="stFileUploader"] button {
                    border-radius: 12px !important;
                    border: 1px solid rgba(255, 82, 82, 0.45) !important;
                    background: rgba(229, 57, 53, 0.10) !important;
                    color: #FFFFFF !important;
                    font-weight: 800 !important;
                }

                [data-testid="stExpander"] [data-testid="stFileUploader"] button:hover {
                    background: #E53935 !important;
                    border-color: #FF5252 !important;
                }

                [data-testid="stExpander"] [data-testid="stFileUploader"] small,
                [data-testid="stExpander"] [data-testid="stFileUploader"] div {
                    color: #C6D0E1;
                }

                .profile-v11-upload-preview-card {
                    padding: 0.85rem 0.95rem;
                    margin: 0.75rem 0;
                    border-radius: 16px;
                    border: 1px solid rgba(76, 175, 80, 0.30);
                    background: linear-gradient(135deg, rgba(76, 175, 80, 0.10), rgba(255, 255, 255, 0.025));
                    color: #D7E1F0;
                    font-size: 0.86rem;
                    line-height: 1.52;
                }

                /* V20.4: area file terpilih dan preview upload dibuat lebih rapi setelah Browse files dipilih. */
                [data-testid="stExpander"] [data-testid="stFileUploader"] [data-testid="stFileUploaderFile"] {
                    display: grid !important;
                    grid-template-columns: 34px minmax(0, 1fr) auto !important;
                    gap: 0.7rem !important;
                    align-items: center !important;
                    margin-top: 0.72rem !important;
                    padding: 0.72rem 0.82rem !important;
                    border-radius: 16px !important;
                    border: 1px solid rgba(229, 57, 53, 0.28) !important;
                    background:
                        radial-gradient(circle at 0% 0%, rgba(229, 57, 53, 0.12), transparent 36%),
                        rgba(255, 255, 255, 0.035) !important;
                    box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.06), 0 12px 22px rgba(0, 0, 0, 0.16) !important;
                }

                [data-testid="stExpander"] [data-testid="stFileUploader"] [data-testid="stFileUploaderFile"] svg {
                    width: 27px !important;
                    height: 27px !important;
                    color: #D7E1F0 !important;
                }

                [data-testid="stExpander"] [data-testid="stFileUploader"] [data-testid="stFileUploaderFileName"] {
                    color: #EAF1FF !important;
                    font-size: 0.9rem !important;
                    font-weight: 800 !important;
                    line-height: 1.25 !important;
                    white-space: nowrap !important;
                    overflow: hidden !important;
                    text-overflow: ellipsis !important;
                    max-width: 100% !important;
                }

                [data-testid="stExpander"] [data-testid="stFileUploader"] [data-testid="stFileUploaderFileData"] {
                    color: #AFC0D7 !important;
                    font-size: 0.78rem !important;
                    font-weight: 700 !important;
                    white-space: nowrap !important;
                }

                [data-testid="stExpander"] [data-testid="stFileUploader"] [data-testid="stFileUploaderDeleteBtn"] button {
                    width: 34px !important;
                    height: 34px !important;
                    min-height: 34px !important;
                    border-radius: 999px !important;
                    border: 1px solid rgba(255, 82, 82, 0.50) !important;
                    background: rgba(229, 57, 53, 0.10) !important;
                    color: #FFFFFF !important;
                    padding: 0 !important;
                }

                [data-testid="stExpander"] [data-testid="stFileUploader"] [data-testid="stFileUploaderDeleteBtn"] button:hover {
                    background: #E53935 !important;
                    border-color: #FF6B6B !important;
                }

                .profile-v11-selected-photo-card {
                    display: grid;
                    grid-template-columns: 112px minmax(0, 1fr);
                    gap: 1rem;
                    align-items: center;
                    margin: 0.95rem 0 0.75rem 0;
                    padding: 1rem;
                    border-radius: 20px;
                    border: 1px solid rgba(76, 175, 80, 0.34);
                    background:
                        radial-gradient(circle at 10% 12%, rgba(76, 175, 80, 0.17), transparent 34%),
                        radial-gradient(circle at 100% 0%, rgba(229, 57, 53, 0.10), transparent 28%),
                        rgba(255, 255, 255, 0.035);
                    box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.06), 0 16px 32px rgba(0, 0, 0, 0.18);
                }

                .profile-v11-selected-photo-frame {
                    width: 106px;
                    height: 106px;
                    display: flex;
                    align-items: center;
                    justify-content: center;
                    border-radius: 26px;
                    border: 1px solid rgba(76, 175, 80, 0.30);
                    background: rgba(255, 255, 255, 0.05);
                    box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.08);
                }

                .profile-v11-selected-photo-img {
                    width: 86px;
                    height: 86px;
                    border-radius: 999px;
                    object-fit: cover;
                    border: 4px solid #E53935;
                    background: #FFFFFF;
                    box-shadow: 0 0 0 6px rgba(229, 57, 53, 0.14), 0 12px 24px rgba(0, 0, 0, 0.26);
                }

                .profile-v11-selected-photo-content {
                    min-width: 0;
                }

                .profile-v11-selected-photo-status {
                    display: inline-flex;
                    align-items: center;
                    gap: 0.42rem;
                    width: fit-content;
                    padding: 0.34rem 0.62rem;
                    margin-bottom: 0.56rem;
                    border-radius: 999px;
                    border: 1px solid rgba(76, 175, 80, 0.34);
                    background: rgba(76, 175, 80, 0.11);
                    color: #DFF7E6;
                    font-size: 0.76rem;
                    font-weight: 900;
                    line-height: 1;
                }

                .profile-v11-selected-photo-dot {
                    width: 8px;
                    height: 8px;
                    border-radius: 999px;
                    background: #4CAF50;
                    box-shadow: 0 0 0 4px rgba(76, 175, 80, 0.12);
                }

                .profile-v11-selected-photo-heading {
                    margin: 0 0 0.35rem 0;
                    color: #FFFFFF;
                    font-size: 1rem;
                    font-weight: 850;
                    letter-spacing: -0.02em;
                    white-space: nowrap;
                    overflow: hidden;
                    text-overflow: ellipsis;
                }

                .profile-v11-selected-photo-text {
                    margin: 0;
                    color: #AFC0D7;
                    font-size: 0.84rem;
                    line-height: 1.55;
                }

                .profile-v11-selected-photo-meta {
                    display: flex;
                    flex-wrap: wrap;
                    gap: 0.48rem;
                    margin-top: 0.72rem;
                }

                .profile-v11-selected-photo-chip {
                    display: inline-flex;
                    align-items: center;
                    gap: 0.34rem;
                    padding: 0.34rem 0.58rem;
                    border-radius: 999px;
                    border: 1px solid rgba(167, 176, 191, 0.18);
                    background: rgba(255, 255, 255, 0.045);
                    color: #D7E1F0;
                    font-size: 0.76rem;
                    font-weight: 800;
                }

                .profile-v11-save-photo-box {
                    margin: 0.15rem 0 1.05rem 0;
                    padding: 0.78rem 0.92rem;
                    border-radius: 16px;
                    border: 1px solid rgba(229, 57, 53, 0.22);
                    background: rgba(255, 255, 255, 0.025);
                    color: #9EABBE;
                    font-size: 0.8rem;
                    line-height: 1.48;
                }

                /* V20.5: beri ruang tegas antara catatan preview dan tombol simpan agar tidak terlihat menempel. */
                .profile-v11-save-button-spacer {
                    height: 0.45rem;
                    min-height: 0.45rem;
                }


                /* V20.7: Edit Profil dibuat lebih premium, rapi, dan eye catching. */
                .profile-v11-edit-hero {
                    position: relative;
                    overflow: hidden;
                    margin: 1.15rem 0 0.9rem 0;
                    padding: clamp(1.15rem, 2vw, 1.45rem);
                    border-radius: 24px;
                    border: 1px solid rgba(229, 57, 53, 0.48);
                    background:
                        radial-gradient(circle at 6% 8%, rgba(255, 82, 82, 0.25), transparent 28%),
                        radial-gradient(circle at 94% 18%, rgba(255, 255, 255, 0.08), transparent 24%),
                        linear-gradient(135deg, rgba(45, 18, 25, 0.94), rgba(12, 19, 31, 0.98) 58%, rgba(15, 23, 42, 0.98));
                    box-shadow:
                        0 20px 44px rgba(0, 0, 0, 0.28),
                        0 0 0 1px rgba(255, 255, 255, 0.035) inset,
                        0 0 38px rgba(229, 57, 53, 0.10);
                }

                .profile-v11-edit-hero::before {
                    content: '';
                    position: absolute;
                    inset: 0;
                    background:
                        linear-gradient(115deg, rgba(255, 255, 255, 0.09), transparent 36%),
                        repeating-linear-gradient(135deg, rgba(255,255,255,0.035) 0 1px, transparent 1px 16px);
                    pointer-events: none;
                }

                .profile-v11-edit-hero::after {
                    content: '';
                    position: absolute;
                    right: -42px;
                    bottom: -56px;
                    width: 190px;
                    height: 190px;
                    border-radius: 50%;
                    border: 1px solid rgba(255, 82, 82, 0.22);
                    background: radial-gradient(circle, rgba(229, 57, 53, 0.16), transparent 62%);
                    pointer-events: none;
                }

                .profile-v11-edit-hero-inner {
                    position: relative;
                    z-index: 1;
                    display: grid;
                    grid-template-columns: 62px minmax(0, 1fr) auto;
                    gap: 1rem;
                    align-items: center;
                }

                .profile-v11-edit-icon {
                    width: 62px;
                    height: 62px;
                    display: flex;
                    align-items: center;
                    justify-content: center;
                    border-radius: 20px;
                    background: linear-gradient(135deg, #FF6B6B, #E53935 58%, #B71C1C);
                    color: #FFFFFF;
                    font-size: 1.55rem;
                    box-shadow:
                        0 16px 34px rgba(229, 57, 53, 0.28),
                        inset 0 1px 0 rgba(255, 255, 255, 0.24);
                }

                .profile-v11-edit-eyebrow {
                    margin: 0 0 0.24rem 0;
                    color: #FFB4B4;
                    font-size: 0.76rem;
                    font-weight: 900;
                    letter-spacing: 0.11em;
                    text-transform: uppercase;
                }

                .profile-v11-edit-title {
                    margin: 0;
                    color: #FFFFFF;
                    font-size: clamp(1.35rem, 2vw, 1.72rem);
                    line-height: 1.18;
                    font-weight: 900;
                    letter-spacing: -0.045em;
                    text-shadow: 0 10px 26px rgba(0, 0, 0, 0.32);
                }

                .profile-v11-edit-desc {
                    margin: 0.42rem 0 0 0;
                    max-width: 760px;
                    color: #C7D2E4;
                    font-size: 0.94rem;
                    line-height: 1.58;
                    font-weight: 500;
                }

                .profile-v11-edit-chips {
                    display: flex;
                    flex-wrap: wrap;
                    justify-content: flex-end;
                    gap: 0.52rem;
                    min-width: 255px;
                }

                .profile-v11-edit-chip {
                    display: inline-flex;
                    align-items: center;
                    justify-content: center;
                    gap: 0.38rem;
                    min-height: 38px;
                    padding: 0.48rem 0.72rem;
                    border-radius: 999px;
                    border: 1px solid rgba(255, 82, 82, 0.28);
                    background: rgba(255, 255, 255, 0.055);
                    color: #EAF1FF;
                    font-size: 0.78rem;
                    font-weight: 900;
                    white-space: nowrap;
                    box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.09);
                }

                .profile-v11-edit-chip span {
                    color: #FF8A80;
                    font-size: 0.95rem;
                    line-height: 1;
                }

                /* Kartu form Streamlit dibuat lebih menyatu dengan hero edit profil. */
                [data-testid="stForm"] {
                    position: relative;
                    overflow: hidden;
                    padding: clamp(1.15rem, 2vw, 1.45rem) !important;
                    border-radius: 24px !important;
                    border: 1px solid rgba(94, 114, 143, 0.62) !important;
                    background:
                        radial-gradient(circle at 0% 0%, rgba(229, 57, 53, 0.12), transparent 30%),
                        radial-gradient(circle at 100% 100%, rgba(255, 82, 82, 0.07), transparent 26%),
                        linear-gradient(145deg, rgba(21, 27, 38, 0.98), rgba(10, 15, 24, 0.98)) !important;
                    box-shadow:
                        0 18px 38px rgba(0, 0, 0, 0.24),
                        inset 0 1px 0 rgba(255, 255, 255, 0.055) !important;
                }

                [data-testid="stForm"]::before {
                    content: '';
                    position: absolute;
                    left: 0;
                    top: 0;
                    width: 100%;
                    height: 3px;
                    background: linear-gradient(90deg, #E53935, rgba(255, 82, 82, 0.52), transparent);
                    box-shadow: 0 0 20px rgba(229, 57, 53, 0.42);
                    pointer-events: none;
                }

                .profile-v11-form-intro {
                    display: grid;
                    grid-template-columns: repeat(3, minmax(0, 1fr));
                    gap: 0.78rem;
                    margin: 0.15rem 0 1.05rem 0;
                }

                .profile-v11-form-tip-card {
                    display: grid;
                    grid-template-columns: 38px 1fr;
                    gap: 0.65rem;
                    align-items: center;
                    min-height: 76px;
                    padding: 0.82rem 0.9rem;
                    border-radius: 18px;
                    border: 1px solid rgba(167, 176, 191, 0.16);
                    background: rgba(255, 255, 255, 0.04);
                    box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.06);
                }

                .profile-v11-form-tip-icon {
                    width: 38px;
                    height: 38px;
                    display: flex;
                    align-items: center;
                    justify-content: center;
                    border-radius: 13px;
                    border: 1px solid rgba(255, 82, 82, 0.30);
                    background: rgba(229, 57, 53, 0.11);
                    color: #FF8A80;
                    font-size: 1rem;
                }

                .profile-v11-form-tip-title {
                    margin: 0;
                    color: #F8FAFC;
                    font-size: 0.82rem;
                    font-weight: 900;
                    letter-spacing: -0.01em;
                }

                .profile-v11-form-tip-text {
                    margin: 0.18rem 0 0 0;
                    color: #9EABBE;
                    font-size: 0.75rem /* FIX: minimum 12px agar terbaca di tablet */;
                    line-height: 1.38;
                    font-weight: 600;
                }

                [data-testid="stForm"] [data-testid="stTextInput"] {
                    margin-bottom: 0.45rem;
                }

                [data-testid="stForm"] [data-testid="stTextInput"] label p {
                    color: #EAF1FF !important;
                    font-weight: 900 !important;
                    letter-spacing: -0.015em !important;
                }

                [data-testid="stForm"] [data-testid="stTextInput"] input {
                    min-height: 54px !important;
                    border-radius: 15px !important;
                    border-color: rgba(94, 114, 143, 0.82) !important;
                    background:
                        linear-gradient(135deg, rgba(17, 24, 39, 0.98), rgba(10, 15, 24, 0.98)) !important;
                    box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.045) !important;
                    font-weight: 750 !important;
                }

                [data-testid="stForm"] [data-testid="stTextInput"] input:focus {
                    border-color: rgba(255, 82, 82, 0.95) !important;
                    box-shadow:
                        0 0 0 1px rgba(229, 57, 53, 0.42),
                        0 0 24px rgba(229, 57, 53, 0.12),
                        inset 0 1px 0 rgba(255, 255, 255, 0.06) !important;
                }

                .profile-v11-form-submit-note {
                    display: flex;
                    align-items: center;
                    gap: 0.55rem;
                    margin: 0.78rem 0 0.75rem 0;
                    padding: 0.78rem 0.92rem;
                    border-radius: 16px;
                    border: 1px solid rgba(76, 175, 80, 0.22);
                    background: rgba(76, 175, 80, 0.07);
                    color: #C7D2E4;
                    font-size: 0.82rem;
                    line-height: 1.45;
                    font-weight: 650;
                }

                .profile-v11-form-submit-note strong {
                    color: #DFF7E6;
                    font-weight: 900;
                }

                [data-testid="stForm"] div[data-testid="stFormSubmitButton"] button[kind="primary"] {
                    min-height: 56px !important;
                    border-radius: 16px !important;
                    background: linear-gradient(135deg, #FF4B4B, #E53935 48%, #B71C1C) !important;
                    border: 1px solid rgba(255, 82, 82, 0.70) !important;
                    box-shadow:
                        0 16px 28px rgba(229, 57, 53, 0.24),
                        inset 0 1px 0 rgba(255, 255, 255, 0.18) !important;
                    font-size: 0.98rem !important;
                    letter-spacing: -0.01em !important;
                }

                [data-testid="stForm"] div[data-testid="stFormSubmitButton"] button[kind="primary"]:hover {
                    transform: translateY(-1px);
                    background: linear-gradient(135deg, #FF6B6B, #F44336 48%, #C62828) !important;
                    box-shadow:
                        0 18px 34px rgba(229, 57, 53, 0.30),
                        0 0 0 1px rgba(255, 255, 255, 0.035) inset !important;
                }

                /* V20.8: Animasi interaktif untuk section Edit Profil agar terasa lebih hidup saat disentuh pengguna. */
                @keyframes profileV11EntranceUp {
                    from {
                        opacity: 0;
                        transform: translateY(10px) scale(0.992);
                    }
                    to {
                        opacity: 1;
                        transform: translateY(0) scale(1);
                    }
                }

                @keyframes profileV11SoftPulse {
                    0%, 100% {
                        box-shadow: 0 16px 34px rgba(229, 57, 53, 0.28), inset 0 1px 0 rgba(255, 255, 255, 0.24);
                    }
                    50% {
                        box-shadow: 0 18px 42px rgba(229, 57, 53, 0.40), 0 0 0 7px rgba(229, 57, 53, 0.08), inset 0 1px 0 rgba(255, 255, 255, 0.26);
                    }
                }

                @keyframes profileV11ShimmerMove {
                    from {
                        background-position: -220px 0, 0 0;
                    }
                    to {
                        background-position: 220px 0, 0 0;
                    }
                }

                .profile-v11-edit-hero {
                    transition:
                        transform 0.28s cubic-bezier(0.22, 1, 0.36, 1),
                        border-color 0.28s ease,
                        box-shadow 0.28s ease,
                        filter 0.28s ease;
                    animation: profileV11EntranceUp 0.45s ease both;
                }

                .profile-v11-edit-hero:hover {
                    transform: translateY(-3px);
                    border-color: rgba(255, 82, 82, 0.82);
                    box-shadow:
                        0 24px 54px rgba(0, 0, 0, 0.34),
                        0 0 0 1px rgba(255, 255, 255, 0.045) inset,
                        0 0 46px rgba(229, 57, 53, 0.18);
                    filter: saturate(1.06);
                }

                .profile-v11-edit-hero:hover::before {
                    background:
                        linear-gradient(115deg, transparent 0%, rgba(255, 255, 255, 0.12) 46%, transparent 66%),
                        repeating-linear-gradient(135deg, rgba(255,255,255,0.04) 0 1px, transparent 1px 16px);
                    background-size: 220px 100%, auto;
                    animation: profileV11ShimmerMove 1.45s linear infinite;
                }

                .profile-v11-edit-icon {
                    transition:
                        transform 0.28s cubic-bezier(0.34, 1.56, 0.64, 1),
                        box-shadow 0.28s ease,
                        filter 0.28s ease;
                    will-change: transform;
                }

                .profile-v11-edit-hero:hover .profile-v11-edit-icon {
                    transform: translateY(-2px) rotate(-5deg) scale(1.06);
                    filter: brightness(1.08);
                    animation: profileV11SoftPulse 1.7s ease-in-out infinite;
                }

                .profile-v11-edit-title,
                .profile-v11-edit-desc,
                .profile-v11-edit-eyebrow {
                    transition: color 0.24s ease, text-shadow 0.24s ease, transform 0.24s ease;
                }

                .profile-v11-edit-hero:hover .profile-v11-edit-title {
                    text-shadow: 0 12px 28px rgba(229, 57, 53, 0.22), 0 10px 26px rgba(0, 0, 0, 0.32);
                }

                .profile-v11-edit-hero:hover .profile-v11-edit-eyebrow {
                    color: #FFD1D1;
                }

                .profile-v11-edit-chip {
                    position: relative;
                    overflow: hidden;
                    transition:
                        transform 0.22s cubic-bezier(0.22, 1, 0.36, 1),
                        border-color 0.22s ease,
                        background 0.22s ease,
                        color 0.22s ease,
                        box-shadow 0.22s ease;
                    will-change: transform;
                }

                .profile-v11-edit-chip::before {
                    content: '';
                    position: absolute;
                    inset: 0;
                    background: linear-gradient(120deg, transparent 0%, rgba(255,255,255,0.13) 46%, transparent 68%);
                    transform: translateX(-120%);
                    transition: transform 0.45s ease;
                    pointer-events: none;
                }

                .profile-v11-edit-chip:hover {
                    transform: translateY(-3px) scale(1.025);
                    border-color: rgba(255, 82, 82, 0.68);
                    background: rgba(229, 57, 53, 0.13);
                    color: #FFFFFF;
                    box-shadow: 0 12px 24px rgba(229, 57, 53, 0.16), inset 0 1px 0 rgba(255, 255, 255, 0.13);
                }

                .profile-v11-edit-chip:hover::before {
                    transform: translateX(120%);
                }

                .profile-v11-edit-chip span {
                    transition: transform 0.22s cubic-bezier(0.34, 1.56, 0.64, 1), color 0.22s ease;
                }

                .profile-v11-edit-chip:hover span {
                    transform: rotate(-8deg) scale(1.18);
                    color: #FFFFFF;
                }

                [data-testid="stForm"] {
                    transition:
                        transform 0.28s cubic-bezier(0.22, 1, 0.36, 1),
                        border-color 0.28s ease,
                        box-shadow 0.28s ease;
                    animation: profileV11EntranceUp 0.52s 0.05s ease both;
                }

                [data-testid="stForm"]:hover {
                    transform: translateY(-2px);
                    border-color: rgba(255, 82, 82, 0.46) !important;
                    box-shadow:
                        0 22px 46px rgba(0, 0, 0, 0.28),
                        0 0 36px rgba(229, 57, 53, 0.11),
                        inset 0 1px 0 rgba(255, 255, 255, 0.06) !important;
                }

                [data-testid="stForm"]:hover::before {
                    background: linear-gradient(90deg, #FF6B6B, #E53935, rgba(255, 82, 82, 0.12));
                    box-shadow: 0 0 26px rgba(229, 57, 53, 0.56);
                }

                .profile-v11-form-tip-card {
                    position: relative;
                    overflow: hidden;
                    transition:
                        transform 0.24s cubic-bezier(0.22, 1, 0.36, 1),
                        border-color 0.24s ease,
                        background 0.24s ease,
                        box-shadow 0.24s ease;
                    animation: profileV11EntranceUp 0.45s ease both;
                    will-change: transform;
                }

                .profile-v11-form-tip-card:nth-child(1) { animation-delay: 0.08s; }
                .profile-v11-form-tip-card:nth-child(2) { animation-delay: 0.14s; }
                .profile-v11-form-tip-card:nth-child(3) { animation-delay: 0.20s; }

                .profile-v11-form-tip-card::after {
                    content: '';
                    position: absolute;
                    inset: auto -32px -38px auto;
                    width: 86px;
                    height: 86px;
                    border-radius: 50%;
                    background: radial-gradient(circle, rgba(229, 57, 53, 0.20), transparent 64%);
                    opacity: 0;
                    transition: opacity 0.24s ease, transform 0.24s ease;
                    pointer-events: none;
                }

                .profile-v11-form-tip-card:hover {
                    transform: translateY(-5px) scale(1.012);
                    border-color: rgba(255, 82, 82, 0.42);
                    background: rgba(229, 57, 53, 0.075);
                    box-shadow: 0 18px 30px rgba(0, 0, 0, 0.22), 0 0 22px rgba(229, 57, 53, 0.10), inset 0 1px 0 rgba(255, 255, 255, 0.08);
                }

                .profile-v11-form-tip-card:hover::after {
                    opacity: 1;
                    transform: scale(1.05);
                }

                .profile-v11-form-tip-icon {
                    transition:
                        transform 0.24s cubic-bezier(0.34, 1.56, 0.64, 1),
                        border-color 0.24s ease,
                        background 0.24s ease,
                        color 0.24s ease,
                        box-shadow 0.24s ease;
                    will-change: transform;
                }

                .profile-v11-form-tip-card:hover .profile-v11-form-tip-icon {
                    transform: rotate(-6deg) scale(1.12);
                    border-color: rgba(255, 82, 82, 0.62);
                    background: rgba(229, 57, 53, 0.20);
                    color: #FFFFFF;
                    box-shadow: 0 12px 22px rgba(229, 57, 53, 0.18), inset 0 1px 0 rgba(255, 255, 255, 0.12);
                }

                .profile-v11-form-tip-title,
                .profile-v11-form-tip-text,
                .profile-v11-form-submit-note {
                    transition: color 0.22s ease, transform 0.22s ease, border-color 0.22s ease, background 0.22s ease, box-shadow 0.22s ease;
                }

                .profile-v11-form-tip-card:hover .profile-v11-form-tip-title {
                    color: #FFFFFF;
                }

                .profile-v11-form-tip-card:hover .profile-v11-form-tip-text {
                    color: #C7D2E4;
                }

                [data-testid="stForm"] [data-testid="stTextInput"] label p {
                    transition: color 0.22s ease, transform 0.22s ease;
                }

                [data-testid="stForm"] [data-testid="stTextInput"]:focus-within label p {
                    color: #FFB4B4 !important;
                    transform: translateX(2px);
                }

                [data-testid="stForm"] [data-testid="stTextInput"] input {
                    transition:
                        border-color 0.22s ease,
                        box-shadow 0.22s ease,
                        transform 0.22s ease,
                        background 0.22s ease;
                }

                [data-testid="stForm"] [data-testid="stTextInput"] input:hover {
                    border-color: rgba(255, 82, 82, 0.58) !important;
                    box-shadow:
                        0 0 0 1px rgba(229, 57, 53, 0.12),
                        inset 0 1px 0 rgba(255, 255, 255, 0.052) !important;
                }

                [data-testid="stForm"] [data-testid="stTextInput"] input:focus {
                    transform: translateY(-1px);
                    background:
                        linear-gradient(135deg, rgba(19, 29, 45, 0.99), rgba(10, 15, 24, 0.99)) !important;
                }

                .profile-v11-form-submit-note:hover {
                    transform: translateY(-2px);
                    border-color: rgba(76, 175, 80, 0.38);
                    background: rgba(76, 175, 80, 0.10);
                    box-shadow: 0 12px 22px rgba(76, 175, 80, 0.08);
                }

                [data-testid="stForm"] div[data-testid="stFormSubmitButton"] button[kind="primary"] {
                    position: relative;
                    overflow: hidden;
                    transition:
                        transform 0.20s cubic-bezier(0.22, 1, 0.36, 1),
                        box-shadow 0.20s ease,
                        filter 0.20s ease,
                        background 0.20s ease;
                }

                [data-testid="stForm"] div[data-testid="stFormSubmitButton"] button[kind="primary"]::before {
                    content: '';
                    position: absolute;
                    inset: 0;
                    background: linear-gradient(120deg, transparent 0%, rgba(255,255,255,0.20) 44%, transparent 64%);
                    transform: translateX(-120%);
                    transition: transform 0.55s ease;
                    pointer-events: none;
                }

                [data-testid="stForm"] div[data-testid="stFormSubmitButton"] button[kind="primary"]:hover::before {
                    transform: translateX(120%);
                }

                [data-testid="stForm"] div[data-testid="stFormSubmitButton"] button[kind="primary"]:active {
                    transform: translateY(0) scale(0.985);
                    filter: brightness(0.96);
                    box-shadow:
                        0 10px 20px rgba(229, 57, 53, 0.20),
                        inset 0 2px 4px rgba(0, 0, 0, 0.18) !important;
                }


                /* V20.9: Redesign interaktif khusus section Ubah Password. */
                @keyframes profileV11PasswordSweep {
                    from { transform: translateX(-140%); }
                    to { transform: translateX(140%); }
                }

                @keyframes profileV11PasswordFloat {
                    0%, 100% { transform: translateY(0) rotate(0deg); }
                    50% { transform: translateY(-4px) rotate(-4deg); }
                }

                @keyframes profileV11PasswordAura {
                    0%, 100% {
                        box-shadow: 0 18px 34px rgba(229, 57, 53, 0.26), inset 0 1px 0 rgba(255, 255, 255, 0.24);
                    }
                    50% {
                        box-shadow: 0 22px 46px rgba(229, 57, 53, 0.42), 0 0 0 8px rgba(229, 57, 53, 0.075), inset 0 1px 0 rgba(255, 255, 255, 0.28);
                    }
                }

                @keyframes profileV11PasswordMeter {
                    0% { filter: brightness(0.98); }
                    50% { filter: brightness(1.14); }
                    100% { filter: brightness(0.98); }
                }

                .profile-v11-password-hero {
                    position: relative;
                    overflow: hidden;
                    margin: 1.05rem 0 1rem 0;
                    padding: clamp(1.18rem, 2.15vw, 1.6rem);
                    border-radius: 24px;
                    border: 1px solid rgba(255, 82, 82, 0.38);
                    background:
                        radial-gradient(circle at 9% 18%, rgba(255, 82, 82, 0.34), transparent 25%),
                        radial-gradient(circle at 90% 14%, rgba(255, 152, 0, 0.16), transparent 26%),
                        radial-gradient(circle at 88% 88%, rgba(76, 175, 80, 0.12), transparent 22%),
                        linear-gradient(135deg, rgba(44, 20, 34, 0.98), rgba(10, 15, 24, 0.98) 48%, rgba(16, 27, 43, 0.98));
                    box-shadow:
                        0 20px 44px rgba(0, 0, 0, 0.28),
                        0 0 0 1px rgba(255, 255, 255, 0.04) inset;
                    transition: transform 0.28s cubic-bezier(0.22, 1, 0.36, 1), border-color 0.28s ease, box-shadow 0.28s ease, filter 0.28s ease;
                    animation: profileV11EntranceUp 0.48s 0.03s ease both;
                }

                .profile-v11-password-hero::before {
                    content: '';
                    position: absolute;
                    inset: 0;
                    background:
                        linear-gradient(115deg, transparent 0%, rgba(255, 255, 255, 0.10) 45%, transparent 66%),
                        repeating-linear-gradient(135deg, rgba(255, 255, 255, 0.045) 0 1px, transparent 1px 16px);
                    background-size: 260px 100%, auto;
                    transform: translateX(-120%);
                    opacity: 0;
                    pointer-events: none;
                }

                .profile-v11-password-hero::after {
                    content: '';
                    position: absolute;
                    right: -78px;
                    bottom: -88px;
                    width: 230px;
                    height: 230px;
                    border-radius: 50%;
                    border: 1px solid rgba(255, 82, 82, 0.22);
                    background: radial-gradient(circle, rgba(229, 57, 53, 0.12), transparent 66%);
                    pointer-events: none;
                    transition: transform 0.32s ease, opacity 0.32s ease;
                }

                .profile-v11-password-hero:hover {
                    transform: translateY(-3px);
                    border-color: rgba(255, 82, 82, 0.78);
                    box-shadow:
                        0 24px 58px rgba(0, 0, 0, 0.34),
                        0 0 44px rgba(229, 57, 53, 0.16),
                        0 0 0 1px rgba(255, 255, 255, 0.055) inset;
                    filter: saturate(1.08);
                }

                .profile-v11-password-hero:hover::before {
                    opacity: 1;
                    animation: profileV11PasswordSweep 1.5s linear infinite;
                }

                .profile-v11-password-hero:hover::after {
                    transform: scale(1.05) translate(-8px, -8px);
                    opacity: 0.95;
                }

                .profile-v11-password-hero-inner {
                    position: relative;
                    z-index: 1;
                    display: grid;
                    grid-template-columns: 64px minmax(0, 1fr) auto;
                    gap: 1rem;
                    align-items: center;
                }

                .profile-v11-password-icon {
                    width: 64px;
                    height: 64px;
                    display: flex;
                    align-items: center;
                    justify-content: center;
                    border-radius: 22px;
                    background: linear-gradient(135deg, #FFB74D, #FF5252 52%, #B71C1C);
                    color: #FFFFFF;
                    font-size: 1.58rem;
                    box-shadow: 0 18px 34px rgba(229, 57, 53, 0.26), inset 0 1px 0 rgba(255, 255, 255, 0.24);
                    transition: transform 0.28s cubic-bezier(0.34, 1.56, 0.64, 1), filter 0.28s ease, box-shadow 0.28s ease;
                    will-change: transform;
                }

                .profile-v11-password-hero:hover .profile-v11-password-icon {
                    transform: translateY(-3px) rotate(-5deg) scale(1.06);
                    filter: brightness(1.08);
                    animation: profileV11PasswordAura 1.7s ease-in-out infinite;
                }

                .profile-v11-password-eyebrow {
                    margin: 0 0 0.24rem 0;
                    color: #FFD1D1;
                    font-size: 0.76rem;
                    font-weight: 950;
                    letter-spacing: 0.12em;
                    text-transform: uppercase;
                    transition: color 0.24s ease;
                }

                .profile-v11-password-title {
                    margin: 0;
                    color: #FFFFFF;
                    font-size: clamp(1.34rem, 2vw, 1.76rem);
                    line-height: 1.16;
                    font-weight: 950;
                    letter-spacing: -0.045em;
                    text-shadow: 0 12px 30px rgba(0, 0, 0, 0.34);
                    transition: text-shadow 0.24s ease;
                }

                .profile-v11-password-desc {
                    margin: 0.42rem 0 0 0;
                    max-width: 780px;
                    color: #C7D2E4;
                    font-size: 0.94rem;
                    line-height: 1.58;
                    font-weight: 600;
                }

                .profile-v11-password-hero:hover .profile-v11-password-title {
                    text-shadow: 0 12px 30px rgba(255, 82, 82, 0.22), 0 12px 30px rgba(0, 0, 0, 0.34);
                }

                .profile-v11-password-chips {
                    display: flex;
                    flex-wrap: wrap;
                    justify-content: flex-end;
                    gap: 0.52rem;
                    min-width: 270px;
                }

                .profile-v11-password-chip {
                    position: relative;
                    overflow: hidden;
                    display: inline-flex;
                    align-items: center;
                    justify-content: center;
                    gap: 0.38rem;
                    min-height: 38px;
                    padding: 0.48rem 0.72rem;
                    border-radius: 999px;
                    border: 1px solid rgba(255, 82, 82, 0.30);
                    background: rgba(255, 255, 255, 0.06);
                    color: #EAF1FF;
                    font-size: 0.78rem;
                    font-weight: 950;
                    white-space: nowrap;
                    box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.09);
                    transition: transform 0.22s cubic-bezier(0.22, 1, 0.36, 1), border-color 0.22s ease, background 0.22s ease, box-shadow 0.22s ease;
                }

                .profile-v11-password-chip::before {
                    content: '';
                    position: absolute;
                    inset: 0;
                    background: linear-gradient(120deg, transparent 0%, rgba(255, 255, 255, 0.15) 45%, transparent 68%);
                    transform: translateX(-120%);
                    transition: transform 0.45s ease;
                    pointer-events: none;
                }

                .profile-v11-password-chip span {
                    color: #FFCC80;
                    font-size: 0.94rem;
                    transition: transform 0.22s cubic-bezier(0.34, 1.56, 0.64, 1), color 0.22s ease;
                }

                .profile-v11-password-chip:hover {
                    transform: translateY(-3px) scale(1.025);
                    border-color: rgba(255, 183, 77, 0.68);
                    background: rgba(255, 152, 0, 0.12);
                    box-shadow: 0 12px 24px rgba(255, 152, 0, 0.13), inset 0 1px 0 rgba(255, 255, 255, 0.13);
                }

                .profile-v11-password-chip:hover::before {
                    transform: translateX(120%);
                }

                .profile-v11-password-chip:hover span {
                    transform: rotate(-8deg) scale(1.18);
                    color: #FFFFFF;
                }

                .profile-v11-password-intro {
                    display: grid;
                    grid-template-columns: repeat(3, minmax(0, 1fr));
                    gap: 0.78rem;
                    margin: 0.15rem 0 1.05rem 0;
                }

                .profile-v11-password-tip-card {
                    position: relative;
                    overflow: hidden;
                    display: grid;
                    grid-template-columns: 40px 1fr;
                    gap: 0.68rem;
                    align-items: center;
                    min-height: 82px;
                    padding: 0.86rem 0.92rem;
                    border-radius: 18px;
                    border: 1px solid rgba(167, 176, 191, 0.16);
                    background:
                        radial-gradient(circle at 92% 12%, rgba(255, 183, 77, 0.10), transparent 36%),
                        rgba(255, 255, 255, 0.045);
                    box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.065);
                    transition: transform 0.24s cubic-bezier(0.22, 1, 0.36, 1), border-color 0.24s ease, background 0.24s ease, box-shadow 0.24s ease;
                    animation: profileV11EntranceUp 0.45s ease both;
                    will-change: transform;
                }

                .profile-v11-password-tip-card:nth-child(1) { animation-delay: 0.08s; }
                .profile-v11-password-tip-card:nth-child(2) { animation-delay: 0.14s; }
                .profile-v11-password-tip-card:nth-child(3) { animation-delay: 0.20s; }

                .profile-v11-password-tip-card::after {
                    content: '';
                    position: absolute;
                    inset: auto -34px -42px auto;
                    width: 94px;
                    height: 94px;
                    border-radius: 50%;
                    background: radial-gradient(circle, rgba(255, 183, 77, 0.18), transparent 64%);
                    opacity: 0;
                    transition: opacity 0.24s ease, transform 0.24s ease;
                    pointer-events: none;
                }

                .profile-v11-password-tip-card:hover {
                    transform: translateY(-5px) scale(1.012);
                    border-color: rgba(255, 183, 77, 0.44);
                    background: rgba(255, 152, 0, 0.075);
                    box-shadow: 0 18px 30px rgba(0, 0, 0, 0.22), 0 0 22px rgba(255, 152, 0, 0.10), inset 0 1px 0 rgba(255, 255, 255, 0.08);
                }

                .profile-v11-password-tip-card:hover::after {
                    opacity: 1;
                    transform: scale(1.08);
                }

                .profile-v11-password-tip-icon {
                    width: 40px;
                    height: 40px;
                    display: flex;
                    align-items: center;
                    justify-content: center;
                    border-radius: 14px;
                    border: 1px solid rgba(255, 183, 77, 0.34);
                    background: rgba(255, 152, 0, 0.12);
                    color: #FFCC80;
                    font-size: 1.05rem;
                    transition: transform 0.24s cubic-bezier(0.34, 1.56, 0.64, 1), border-color 0.24s ease, background 0.24s ease, color 0.24s ease, box-shadow 0.24s ease;
                    will-change: transform;
                }

                .profile-v11-password-tip-card:hover .profile-v11-password-tip-icon {
                    transform: rotate(-6deg) scale(1.12);
                    border-color: rgba(255, 183, 77, 0.72);
                    background: rgba(255, 152, 0, 0.20);
                    color: #FFFFFF;
                    box-shadow: 0 12px 22px rgba(255, 152, 0, 0.15), inset 0 1px 0 rgba(255, 255, 255, 0.12);
                }

                .profile-v11-password-tip-title {
                    margin: 0;
                    color: #F8FAFC;
                    font-size: 0.84rem;
                    font-weight: 950;
                    letter-spacing: -0.01em;
                    transition: color 0.22s ease;
                }

                .profile-v11-password-tip-text {
                    margin: 0.18rem 0 0 0;
                    color: #9EABBE;
                    font-size: 0.75rem /* FIX: minimum 12px agar terbaca di tablet */;
                    line-height: 1.38;
                    font-weight: 650;
                    transition: color 0.22s ease;
                }

                .profile-v11-password-tip-card:hover .profile-v11-password-tip-title {
                    color: #FFFFFF;
                }

                .profile-v11-password-tip-card:hover .profile-v11-password-tip-text {
                    color: #D7DEE9;
                }

                .profile-v11-strength-panel {
                    position: relative;
                    overflow: hidden;
                    margin: 0.18rem 0 1rem 0;
                    padding: 0.82rem 0.92rem;
                    border-radius: 18px;
                    border: 1px solid rgba(167, 176, 191, 0.18);
                    background:
                        radial-gradient(circle at 88% 20%, rgba(229, 57, 53, 0.10), transparent 34%),
                        rgba(255, 255, 255, 0.04);
                    box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.055);
                    transition: transform 0.22s ease, border-color 0.22s ease, background 0.22s ease, box-shadow 0.22s ease;
                }

                .profile-v11-strength-panel::before {
                    content: '';
                    position: absolute;
                    inset: 0;
                    background: linear-gradient(120deg, transparent 0%, rgba(255, 255, 255, 0.10) 45%, transparent 66%);
                    transform: translateX(-130%);
                    transition: transform 0.55s ease;
                    pointer-events: none;
                }

                .profile-v11-strength-panel:hover {
                    transform: translateY(-2px);
                    border-color: rgba(255, 82, 82, 0.36);
                    background: rgba(229, 57, 53, 0.065);
                    box-shadow: 0 14px 26px rgba(0, 0, 0, 0.20), 0 0 22px rgba(229, 57, 53, 0.08), inset 0 1px 0 rgba(255, 255, 255, 0.07);
                }

                .profile-v11-strength-panel:hover::before {
                    transform: translateX(130%);
                }

                .profile-v11-strength-head {
                    display: grid;
                    grid-template-columns: 38px minmax(0, 1fr) auto;
                    gap: 0.68rem;
                    align-items: center;
                    margin-bottom: 0.68rem;
                }

                .profile-v11-strength-icon {
                    width: 38px;
                    height: 38px;
                    display: flex;
                    align-items: center;
                    justify-content: center;
                    border-radius: 14px;
                    border: 1px solid rgba(255, 82, 82, 0.25);
                    background: rgba(229, 57, 53, 0.10);
                    font-size: 1rem;
                    transition: transform 0.22s cubic-bezier(0.34, 1.56, 0.64, 1), background 0.22s ease, border-color 0.22s ease;
                }

                .profile-v11-strength-panel:hover .profile-v11-strength-icon {
                    transform: rotate(-6deg) scale(1.1);
                    background: rgba(229, 57, 53, 0.18);
                    border-color: rgba(255, 82, 82, 0.54);
                }

                .profile-v11-strength-label {
                    margin: 0;
                    color: #F8FAFC;
                    font-size: 0.86rem;
                    font-weight: 950;
                    letter-spacing: -0.012em;
                }

                .profile-v11-strength-note {
                    margin: 0.16rem 0 0 0;
                    color: #A7B0BF;
                    font-size: 0.76rem;
                    line-height: 1.38;
                    font-weight: 650;
                }

                .profile-v11-strength-badge {
                    display: inline-flex;
                    align-items: center;
                    min-height: 30px;
                    padding: 0.28rem 0.58rem;
                    border-radius: 999px;
                    border: 1px solid currentColor;
                    background: rgba(255, 255, 255, 0.05);
                    font-size: 0.78rem;
                    font-weight: 950;
                    white-space: nowrap;
                    box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.08);
                }

                .profile-v11-strength-panel .profile-v11-strength-shell {
                    height: 13px;
                    margin: 0;
                    border-color: rgba(167, 176, 191, 0.18);
                    background: rgba(8, 13, 22, 0.88);
                    box-shadow: inset 0 1px 3px rgba(0, 0, 0, 0.40);
                }

                .profile-v11-strength-panel .profile-v11-strength-fill {
                    position: relative;
                    min-width: 0;
                    box-shadow: 0 0 16px rgba(229, 57, 53, 0.18);
                    animation: profileV11PasswordMeter 1.8s ease-in-out infinite;
                }

                .profile-v11-strength-panel .profile-v11-strength-fill::after {
                    content: '';
                    position: absolute;
                    inset: 0;
                    background: linear-gradient(120deg, transparent 0%, rgba(255,255,255,0.38) 50%, transparent 70%);
                    transform: translateX(-120%);
                    animation: profileV11PasswordSweep 1.45s linear infinite;
                    pointer-events: none;
                }

                .profile-v11-strength-strong {
                    border-color: rgba(76, 175, 80, 0.34);
                    background:
                        radial-gradient(circle at 88% 20%, rgba(76, 175, 80, 0.13), transparent 34%),
                        rgba(76, 175, 80, 0.055);
                }

                .profile-v11-strength-medium {
                    border-color: rgba(255, 152, 0, 0.36);
                    background:
                        radial-gradient(circle at 88% 20%, rgba(255, 152, 0, 0.13), transparent 34%),
                        rgba(255, 152, 0, 0.055);
                }

                .profile-v11-strength-weak {
                    border-color: rgba(244, 67, 54, 0.34);
                    background:
                        radial-gradient(circle at 88% 20%, rgba(244, 67, 54, 0.13), transparent 34%),
                        rgba(244, 67, 54, 0.055);
                }

                .profile-v11-password-submit-note {
                    position: relative;
                    overflow: hidden;
                    display: flex;
                    align-items: center;
                    gap: 0.58rem;
                    margin: 0.8rem 0 0.78rem 0;
                    padding: 0.82rem 0.96rem;
                    border-radius: 17px;
                    border: 1px solid rgba(255, 183, 77, 0.26);
                    background:
                        radial-gradient(circle at 0% 50%, rgba(255, 183, 77, 0.13), transparent 30%),
                        rgba(255, 152, 0, 0.07);
                    color: #D7DEE9;
                    font-size: 0.84rem;
                    line-height: 1.45;
                    font-weight: 700;
                    transition: transform 0.22s ease, border-color 0.22s ease, background 0.22s ease, box-shadow 0.22s ease;
                }

                .profile-v11-password-submit-note strong {
                    color: #FFE0B2;
                    font-weight: 950;
                }

                .profile-v11-password-submit-note:hover {
                    transform: translateY(-2px);
                    border-color: rgba(255, 183, 77, 0.44);
                    background: rgba(255, 152, 0, 0.11);
                    box-shadow: 0 14px 24px rgba(255, 152, 0, 0.08);
                }

                .profile-v11-password-live-caption {
                    display: inline-flex;
                    align-items: center;
                    gap: 0.42rem;
                    margin: 0.25rem 0 0.92rem 0;
                    padding: 0.44rem 0.70rem;
                    border-radius: 999px;
                    border: 1px solid rgba(76, 175, 80, 0.24);
                    background: rgba(76, 175, 80, 0.08);
                    color: #C8E6C9;
                    font-size: 0.78rem;
                    font-weight: 850;
                    box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.06);
                    animation: profileV11EntranceUp 0.42s ease both;
                }

                .profile-v11-password-match-card {
                    position: relative;
                    overflow: hidden;
                    display: flex;
                    align-items: center;
                    gap: 0.62rem;
                    margin: -0.35rem 0 1rem 0;
                    padding: 0.75rem 0.90rem;
                    border-radius: 16px;
                    border: 1px solid rgba(167, 176, 191, 0.18);
                    background: rgba(255, 255, 255, 0.045);
                    color: #D7DEE9;
                    font-size: 0.82rem;
                    line-height: 1.45;
                    font-weight: 800;
                    transition: transform 0.22s ease, border-color 0.22s ease, background 0.22s ease, box-shadow 0.22s ease;
                    animation: profileV11EntranceUp 0.42s 0.05s ease both;
                }

                .profile-v11-password-match-card:hover {
                    transform: translateY(-2px);
                    box-shadow: 0 12px 24px rgba(0, 0, 0, 0.18);
                }

                .profile-v11-password-match-card.is-match {
                    border-color: rgba(76, 175, 80, 0.35);
                    background:
                        radial-gradient(circle at 0% 50%, rgba(76, 175, 80, 0.13), transparent 32%),
                        rgba(76, 175, 80, 0.07);
                    color: #C8E6C9;
                }

                .profile-v11-password-match-card.is-mismatch {
                    border-color: rgba(244, 67, 54, 0.36);
                    background:
                        radial-gradient(circle at 0% 50%, rgba(244, 67, 54, 0.13), transparent 32%),
                        rgba(244, 67, 54, 0.07);
                    color: #FFCDD2;
                }

                .profile-v11-password-match-icon {
                    width: 34px;
                    height: 34px;
                    display: inline-flex;
                    align-items: center;
                    justify-content: center;
                    flex: 0 0 auto;
                    border-radius: 12px;
                    border: 1px solid rgba(255, 255, 255, 0.12);
                    background: rgba(255, 255, 255, 0.08);
                    transition: transform 0.22s cubic-bezier(0.34, 1.56, 0.64, 1);
                }

                .profile-v11-password-match-card:hover .profile-v11-password-match-icon {
                    transform: rotate(-5deg) scale(1.08);
                }

                .profile-v11-password-hero + [data-testid="stForm"] {
                    animation: profileV11EntranceUp 0.52s 0.08s ease both;
                }



                /* V20.11: Zona Berbahaya dibuat lebih eye catching + interaktif. */
                @keyframes profileV11DangerSweep {
                    from { transform: translateX(-145%); }
                    to { transform: translateX(145%); }
                }

                @keyframes profileV11DangerPulse {
                    0%, 100% {
                        box-shadow:
                            0 18px 38px rgba(229, 57, 53, 0.20),
                            0 0 0 0 rgba(255, 82, 82, 0.00),
                            inset 0 1px 0 rgba(255, 255, 255, 0.16);
                    }
                    50% {
                        box-shadow:
                            0 24px 54px rgba(229, 57, 53, 0.32),
                            0 0 0 8px rgba(255, 82, 82, 0.06),
                            inset 0 1px 0 rgba(255, 255, 255, 0.22);
                    }
                }

                @keyframes profileV11DangerGlow {
                    0%, 100% { filter: drop-shadow(0 0 0 rgba(255, 183, 77, 0)); }
                    50% { filter: drop-shadow(0 0 12px rgba(255, 183, 77, 0.42)); }
                }

                .profile-v11-danger-card {
                    position: relative;
                    overflow: hidden;
                    margin: 1.12rem 0 1.05rem 0;
                    padding: clamp(1.2rem, 2.2vw, 1.7rem);
                    border-radius: 24px;
                    border: 1px solid rgba(255, 82, 82, 0.52);
                    background:
                        radial-gradient(circle at 5% 10%, rgba(255, 183, 77, 0.18), transparent 24%),
                        radial-gradient(circle at 94% 18%, rgba(244, 67, 54, 0.26), transparent 30%),
                        radial-gradient(circle at 85% 95%, rgba(229, 57, 53, 0.13), transparent 22%),
                        linear-gradient(135deg, rgba(53, 20, 29, 0.98), rgba(15, 23, 36, 0.98) 48%, rgba(33, 19, 33, 0.98));
                    box-shadow:
                        0 20px 48px rgba(0, 0, 0, 0.30),
                        0 0 0 1px rgba(255, 255, 255, 0.04) inset;
                    transition: transform 0.28s cubic-bezier(0.22, 1, 0.36, 1), border-color 0.28s ease, box-shadow 0.28s ease, filter 0.28s ease;
                    animation: profileV11EntranceUp 0.48s ease both;
                }

                .profile-v11-danger-card::before {
                    content: '';
                    position: absolute;
                    inset: 0;
                    background:
                        linear-gradient(115deg, transparent 0%, rgba(255, 255, 255, 0.12) 45%, transparent 66%),
                        repeating-linear-gradient(135deg, rgba(255, 255, 255, 0.045) 0 1px, transparent 1px 16px);
                    background-size: 280px 100%, auto;
                    transform: translateX(-125%);
                    opacity: 0;
                    pointer-events: none;
                }

                .profile-v11-danger-card::after {
                    content: '';
                    position: absolute;
                    right: -74px;
                    bottom: -86px;
                    width: 230px;
                    height: 230px;
                    border-radius: 50%;
                    border: 1px solid rgba(255, 82, 82, 0.24);
                    background: radial-gradient(circle, rgba(255, 82, 82, 0.13), transparent 66%);
                    pointer-events: none;
                    transition: transform 0.32s ease, opacity 0.32s ease;
                }

                .profile-v11-danger-card:hover {
                    transform: translateY(-3px);
                    border-color: rgba(255, 82, 82, 0.88);
                    box-shadow:
                        0 26px 62px rgba(0, 0, 0, 0.36),
                        0 0 46px rgba(244, 67, 54, 0.18),
                        0 0 0 1px rgba(255, 255, 255, 0.06) inset;
                    filter: saturate(1.08);
                }

                .profile-v11-danger-card:hover::before {
                    opacity: 1;
                    animation: profileV11DangerSweep 1.45s linear infinite;
                }

                .profile-v11-danger-card:hover::after {
                    transform: scale(1.06) translate(-9px, -8px);
                    opacity: 0.95;
                }

                .profile-v11-danger-inner {
                    position: relative;
                    z-index: 1;
                    display: grid;
                    grid-template-columns: 64px minmax(0, 1fr) auto;
                    gap: 1rem;
                    align-items: center;
                }

                .profile-v11-danger-icon {
                    width: 64px;
                    height: 64px;
                    display: flex;
                    align-items: center;
                    justify-content: center;
                    border-radius: 22px;
                    background: linear-gradient(135deg, #FFB74D, #FF5252 55%, #B71C1C);
                    color: #FFFFFF;
                    font-size: 1.6rem;
                    box-shadow: 0 18px 34px rgba(229, 57, 53, 0.28), inset 0 1px 0 rgba(255, 255, 255, 0.22);
                    transition: transform 0.28s cubic-bezier(0.34, 1.56, 0.64, 1), filter 0.28s ease, box-shadow 0.28s ease;
                }

                .profile-v11-danger-card:hover .profile-v11-danger-icon {
                    transform: translateY(-3px) rotate(-6deg) scale(1.06);
                    filter: brightness(1.08);
                    animation: profileV11DangerPulse 1.65s ease-in-out infinite;
                }

                .profile-v11-danger-eyebrow {
                    margin: 0 0 0.26rem 0;
                    color: #FFD1D1;
                    font-size: 0.76rem;
                    font-weight: 950;
                    letter-spacing: 0.13em;
                    text-transform: uppercase;
                }

                .profile-v11-danger-title {
                    margin: 0;
                    color: #FFFFFF;
                    font-family: 'Plus Jakarta Sans', sans-serif;
                    font-size: clamp(1.36rem, 2vw, 1.78rem);
                    line-height: 1.16;
                    font-weight: 950;
                    letter-spacing: -0.045em;
                    text-shadow: 0 12px 28px rgba(0, 0, 0, 0.36);
                }

                .profile-v11-danger-text {
                    margin: 0.45rem 0 0 0;
                    max-width: 850px;
                    color: #C7D2E4;
                    font-size: 0.95rem;
                    line-height: 1.68;
                    font-weight: 650;
                }

                .profile-v11-danger-chips {
                    display: flex;
                    flex-wrap: wrap;
                    justify-content: flex-end;
                    gap: 0.52rem;
                    min-width: 310px;
                }

                .profile-v11-danger-chip {
                    position: relative;
                    overflow: hidden;
                    display: inline-flex;
                    align-items: center;
                    justify-content: center;
                    gap: 0.38rem;
                    min-height: 38px;
                    padding: 0.48rem 0.74rem;
                    border-radius: 999px;
                    border: 1px solid rgba(255, 183, 77, 0.28);
                    background: rgba(255, 255, 255, 0.065);
                    color: #F8FAFC;
                    font-size: 0.78rem;
                    font-weight: 950;
                    white-space: nowrap;
                    box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.09);
                    transition: transform 0.22s cubic-bezier(0.22, 1, 0.36, 1), border-color 0.22s ease, background 0.22s ease, box-shadow 0.22s ease;
                }

                .profile-v11-danger-chip::before {
                    content: '';
                    position: absolute;
                    inset: 0;
                    background: linear-gradient(120deg, transparent 0%, rgba(255, 255, 255, 0.16) 45%, transparent 68%);
                    transform: translateX(-120%);
                    transition: transform 0.45s ease;
                    pointer-events: none;
                }

                .profile-v11-danger-chip span {
                    color: #FFCC80;
                    font-size: 0.96rem;
                    transition: transform 0.22s cubic-bezier(0.34, 1.56, 0.64, 1);
                }

                .profile-v11-danger-chip:hover {
                    transform: translateY(-3px);
                    border-color: rgba(255, 183, 77, 0.55);
                    background: rgba(255, 183, 77, 0.12);
                    box-shadow: 0 12px 24px rgba(255, 152, 0, 0.10), inset 0 1px 0 rgba(255, 255, 255, 0.10);
                }

                .profile-v11-danger-chip:hover::before {
                    transform: translateX(120%);
                }

                .profile-v11-danger-chip:hover span {
                    transform: rotate(-8deg) scale(1.12);
                }

                .profile-v11-danger-panel {
                    position: relative;
                    overflow: hidden;
                    margin: 0.85rem 0 1.1rem 0;
                    padding: clamp(1.15rem, 2vw, 1.55rem);
                    border-radius: 24px;
                    border: 1px solid rgba(94, 114, 143, 0.56);
                    background:
                        radial-gradient(circle at 8% 0%, rgba(229, 57, 53, 0.14), transparent 28%),
                        radial-gradient(circle at 90% 100%, rgba(255, 152, 0, 0.10), transparent 26%),
                        linear-gradient(145deg, rgba(15, 23, 42, 0.98), rgba(11, 15, 25, 0.99));
                    box-shadow: 0 20px 44px rgba(0, 0, 0, 0.27), inset 0 1px 0 rgba(255, 255, 255, 0.035);
                    animation: profileV11EntranceUp 0.50s 0.07s ease both;
                }

                .profile-v11-danger-step-grid {
                    display: grid;
                    grid-template-columns: repeat(3, minmax(0, 1fr));
                    gap: 0.9rem;
                    margin-bottom: 1rem;
                }

                .profile-v11-danger-step-card {
                    position: relative;
                    overflow: hidden;
                    display: grid;
                    grid-template-columns: 46px minmax(0, 1fr);
                    gap: 0.75rem;
                    align-items: center;
                    min-height: 110px;
                    padding: 0.95rem;
                    border-radius: 20px;
                    border: 1px solid rgba(255, 255, 255, 0.10);
                    background:
                        radial-gradient(circle at 100% 0%, rgba(255, 82, 82, 0.11), transparent 34%),
                        rgba(255, 255, 255, 0.045);
                    color: #F8FAFC;
                    transition: transform 0.24s cubic-bezier(0.22, 1, 0.36, 1), border-color 0.24s ease, background 0.24s ease, box-shadow 0.24s ease;
                }

                .profile-v11-danger-step-card::after {
                    content: '';
                    position: absolute;
                    inset: 0;
                    background: linear-gradient(120deg, transparent, rgba(255, 255, 255, 0.10), transparent);
                    transform: translateX(-120%);
                    transition: transform 0.55s ease;
                    pointer-events: none;
                }

                .profile-v11-danger-step-card:hover {
                    transform: translateY(-4px);
                    border-color: rgba(255, 82, 82, 0.40);
                    background:
                        radial-gradient(circle at 100% 0%, rgba(255, 82, 82, 0.17), transparent 34%),
                        rgba(255, 255, 255, 0.065);
                    box-shadow: 0 16px 30px rgba(229, 57, 53, 0.10);
                }

                .profile-v11-danger-step-card:hover::after {
                    transform: translateX(120%);
                }

                .profile-v11-danger-step-icon {
                    width: 46px;
                    height: 46px;
                    display: flex;
                    align-items: center;
                    justify-content: center;
                    border-radius: 16px;
                    border: 1px solid rgba(255, 82, 82, 0.34);
                    background: rgba(229, 57, 53, 0.12);
                    font-size: 1.08rem;
                    transition: transform 0.24s cubic-bezier(0.34, 1.56, 0.64, 1), background 0.24s ease;
                }

                .profile-v11-danger-step-card:hover .profile-v11-danger-step-icon {
                    transform: rotate(-6deg) scale(1.08);
                    background: rgba(255, 82, 82, 0.18);
                    animation: profileV11DangerGlow 1.4s ease-in-out infinite;
                }

                .profile-v11-danger-step-title {
                    margin: 0 0 0.22rem 0;
                    color: #FFFFFF;
                    font-size: 0.92rem;
                    line-height: 1.28;
                    font-weight: 950;
                    letter-spacing: -0.015em;
                }

                .profile-v11-danger-step-text {
                    margin: 0;
                    color: #B7C0CF;
                    font-size: 0.78rem;
                    line-height: 1.48;
                    font-weight: 700;
                }

                .profile-v11-admin-lock-card,
                .profile-v11-delete-confirm-card {
                    position: relative;
                    overflow: hidden;
                    display: grid;
                    grid-template-columns: 58px minmax(0, 1fr) auto;
                    gap: 0.9rem;
                    align-items: center;
                    padding: 1rem 1.05rem;
                    border-radius: 20px;
                    border: 1px solid rgba(76, 175, 80, 0.32);
                    background:
                        radial-gradient(circle at 0% 50%, rgba(76, 175, 80, 0.16), transparent 30%),
                        linear-gradient(135deg, rgba(18, 52, 38, 0.72), rgba(20, 28, 45, 0.94));
                    color: #F8FAFC;
                    transition: transform 0.24s cubic-bezier(0.22, 1, 0.36, 1), border-color 0.24s ease, box-shadow 0.24s ease, filter 0.24s ease;
                }

                .profile-v11-delete-confirm-card {
                    grid-template-columns: 58px minmax(0, 1fr);
                    border-color: rgba(255, 183, 77, 0.34);
                    background:
                        radial-gradient(circle at 0% 50%, rgba(255, 183, 77, 0.15), transparent 30%),
                        linear-gradient(135deg, rgba(72, 47, 18, 0.55), rgba(20, 28, 45, 0.94));
                }

                .profile-v11-admin-lock-card::before,
                .profile-v11-delete-confirm-card::before {
                    content: '';
                    position: absolute;
                    inset: 0;
                    background: linear-gradient(120deg, transparent, rgba(255, 255, 255, 0.12), transparent);
                    transform: translateX(-120%);
                    transition: transform 0.56s ease;
                    pointer-events: none;
                }

                .profile-v11-admin-lock-card:hover,
                .profile-v11-delete-confirm-card:hover {
                    transform: translateY(-3px);
                    box-shadow: 0 18px 34px rgba(76, 175, 80, 0.10);
                    border-color: rgba(76, 175, 80, 0.52);
                    filter: saturate(1.08);
                }

                .profile-v11-delete-confirm-card:hover {
                    box-shadow: 0 18px 34px rgba(255, 152, 0, 0.11);
                    border-color: rgba(255, 183, 77, 0.56);
                }

                .profile-v11-admin-lock-card:hover::before,
                .profile-v11-delete-confirm-card:hover::before {
                    transform: translateX(120%);
                }

                .profile-v11-admin-lock-icon,
                .profile-v11-delete-confirm-icon {
                    width: 58px;
                    height: 58px;
                    display: flex;
                    align-items: center;
                    justify-content: center;
                    border-radius: 19px;
                    border: 1px solid rgba(76, 175, 80, 0.34);
                    background: rgba(76, 175, 80, 0.14);
                    font-size: 1.35rem;
                    transition: transform 0.24s cubic-bezier(0.34, 1.56, 0.64, 1), background 0.24s ease;
                }

                .profile-v11-delete-confirm-icon {
                    border-color: rgba(255, 183, 77, 0.36);
                    background: rgba(255, 152, 0, 0.13);
                }

                .profile-v11-admin-lock-card:hover .profile-v11-admin-lock-icon,
                .profile-v11-delete-confirm-card:hover .profile-v11-delete-confirm-icon {
                    transform: rotate(-6deg) scale(1.08);
                }

                .profile-v11-admin-lock-title,
                .profile-v11-delete-confirm-title {
                    margin: 0 0 0.25rem 0;
                    color: #FFFFFF;
                    font-size: 1rem;
                    line-height: 1.28;
                    font-weight: 950;
                    letter-spacing: -0.02em;
                }

                .profile-v11-admin-lock-text,
                .profile-v11-delete-confirm-text {
                    margin: 0;
                    color: #C9D4E5;
                    font-size: 0.84rem;
                    line-height: 1.55;
                    font-weight: 720;
                }

                .profile-v11-admin-lock-pill {
                    position: relative;
                    z-index: 1;
                    display: inline-flex;
                    align-items: center;
                    justify-content: center;
                    gap: 0.35rem;
                    padding: 0.48rem 0.78rem;
                    border-radius: 999px;
                    border: 1px solid rgba(76, 175, 80, 0.30);
                    background: rgba(76, 175, 80, 0.12);
                    color: #C8E6C9;
                    font-size: 0.78rem;
                    font-weight: 950;
                    white-space: nowrap;
                    box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.08);
                    transition: transform 0.22s ease, background 0.22s ease, border-color 0.22s ease;
                }

                .profile-v11-admin-lock-pill:hover {
                    transform: translateY(-2px);
                    border-color: rgba(76, 175, 80, 0.55);
                    background: rgba(76, 175, 80, 0.18);
                }

                .profile-v11-danger-panel + div[data-testid="stCheckbox"] {
                    margin-top: 0.35rem;
                }

                div[data-testid="stCheckbox"] label {
                    border-radius: 16px;
                    transition: transform 0.22s ease, filter 0.22s ease;
                }

                div[data-testid="stCheckbox"] label:hover {
                    transform: translateX(3px);
                    filter: brightness(1.08);
                }

                .stButton button[kind="secondary"] {
                    position: relative;
                    overflow: hidden;
                    min-height: 48px;
                    border-radius: 16px !important;
                    border: 1px solid rgba(255, 82, 82, 0.38) !important;
                    background: linear-gradient(135deg, #5A1515, #B71C1C, #E53935) !important;
                    color: #FFFFFF !important;
                    font-weight: 950 !important;
                    box-shadow: 0 16px 30px rgba(229, 57, 53, 0.20) !important;
                    transition: transform 0.22s cubic-bezier(0.22, 1, 0.36, 1), box-shadow 0.22s ease, filter 0.22s ease !important;
                }

                .stButton button[kind="secondary"]::before {
                    content: '';
                    position: absolute;
                    inset: 0;
                    background: linear-gradient(120deg, transparent 0%, rgba(255, 255, 255, 0.22) 44%, transparent 66%);
                    transform: translateX(-120%);
                    transition: transform 0.55s ease;
                    pointer-events: none;
                }

                .stButton button[kind="secondary"]:hover:not(:disabled) {
                    transform: translateY(-2px) !important;
                    box-shadow: 0 20px 38px rgba(229, 57, 53, 0.30) !important;
                    filter: saturate(1.08) brightness(1.04);
                }

                .stButton button[kind="secondary"]:hover:not(:disabled)::before {
                    transform: translateX(120%);
                }

                .stButton button[kind="secondary"]:active:not(:disabled) {
                    transform: translateY(0) scale(0.985) !important;
                    filter: brightness(0.96);
                }

                .stButton button[kind="secondary"]:disabled {
                    background: rgba(100, 116, 139, 0.22) !important;
                    color: rgba(248, 250, 252, 0.45) !important;
                    border-color: rgba(148, 163, 184, 0.20) !important;
                    box-shadow: none !important;
                    cursor: not-allowed !important;
                }

                @media (max-width: 980px) {
                    .profile-v11-danger-inner {
                        grid-template-columns: 64px minmax(0, 1fr);
                    }

                    .profile-v11-danger-chips {
                        grid-column: 1 / -1;
                        justify-content: flex-start;
                        min-width: 0;
                    }

                    .profile-v11-danger-step-grid {
                        grid-template-columns: 1fr;
                    }

                    .profile-v11-admin-lock-card {
                        grid-template-columns: 58px minmax(0, 1fr);
                    }

                    .profile-v11-admin-lock-pill {
                        grid-column: 1 / -1;
                        justify-self: flex-start;
                    }
                }

                @media (max-width: 560px) {
                    .profile-v11-danger-inner,
                    .profile-v11-danger-step-card,
                    .profile-v11-admin-lock-card,
                    .profile-v11-delete-confirm-card {
                        grid-template-columns: 1fr;
                    }

                    .profile-v11-danger-icon,
                    .profile-v11-admin-lock-icon,
                    .profile-v11-delete-confirm-icon {
                        width: 56px;
                        height: 56px;
                    }
                }

                @media (prefers-reduced-motion: reduce) {
                    .profile-v11-edit-hero,
                    .profile-v11-edit-hero::before,
                    .profile-v11-edit-icon,
                    .profile-v11-edit-chip,
                    .profile-v11-edit-chip::before,
                    .profile-v11-password-hero,
                    .profile-v11-password-hero::before,
                    .profile-v11-password-hero::after,
                    .profile-v11-password-icon,
                    .profile-v11-password-chip,
                    .profile-v11-password-chip::before,
                    .profile-v11-password-tip-card,
                    .profile-v11-password-tip-card::after,
                    .profile-v11-password-tip-icon,
                    .profile-v11-strength-panel,
                    .profile-v11-strength-panel::before,
                    .profile-v11-strength-icon,
                    .profile-v11-strength-fill,
                    .profile-v11-strength-fill::after,
                    .profile-v11-password-submit-note,
                    .profile-v11-password-live-caption,
                    .profile-v11-password-match-card,
                    .profile-v11-password-match-icon,
                    .profile-v11-form-tip-card,
                    .profile-v11-form-tip-card::after,
                    .profile-v11-form-tip-icon,
                    [data-testid="stForm"],
                    [data-testid="stForm"]::before,
                    [data-testid="stForm"] [data-testid="stTextInput"] input,
                    [data-testid="stForm"] div[data-testid="stFormSubmitButton"] button[kind="primary"],
                    [data-testid="stForm"] div[data-testid="stFormSubmitButton"] button[kind="primary"]::before {
                        animation: none !important;
                        transition: none !important;
                    }
                }

                @media (max-width: 980px) {
                    .profile-v11-edit-hero-inner {
                        grid-template-columns: 62px minmax(0, 1fr);
                    }

                    .profile-v11-edit-chips {
                        grid-column: 1 / -1;
                        justify-content: flex-start;
                        min-width: 0;
                    }

                    .profile-v11-form-intro,
                    .profile-v11-password-intro {
                        grid-template-columns: 1fr;
                    }

                    .profile-v11-password-hero-inner {
                        grid-template-columns: 64px minmax(0, 1fr);
                    }

                    .profile-v11-password-chips {
                        grid-column: 1 / -1;
                        justify-content: flex-start;
                        min-width: 0;
                    }
                }

                @media (max-width: 560px) {
                    .profile-v11-edit-hero-inner {
                        grid-template-columns: 1fr;
                    }

                    .profile-v11-edit-icon,
                    .profile-v11-password-icon {
                        width: 56px;
                        height: 56px;
                    }

                    .profile-v11-password-hero-inner {
                        grid-template-columns: 1fr;
                    }

                    .profile-v11-form-tip-card,
                    .profile-v11-password-tip-card {
                        min-height: auto;
                    }

                    .profile-v11-strength-head {
                        grid-template-columns: 38px minmax(0, 1fr);
                    }

                    .profile-v11-strength-badge {
                        grid-column: 1 / -1;
                        justify-content: center;
                    }
                }

                @media (max-width: 980px) {
                    .profile-v11-avatar-upload-intro {
                        grid-template-columns: 52px 1fr;
                    }

                    .profile-v11-upload-tip-grid {
                        grid-column: 1 / -1;
                        min-width: 0;
                    }
                }

                @media (max-width: 560px) {
                    .profile-v11-avatar-upload-intro,
                    .profile-v11-upload-tip-grid,
                    .profile-v11-current-photo-card {
                        grid-template-columns: 1fr;
                    }

                    .profile-v11-current-photo-frame {
                        width: 100%;
                    }
                }

                @media (max-width: 900px) {
                    .profile-v11-grid,
                    .profile-v11-metric-grid {
                        grid-template-columns: 1fr;
                    }
                }

                /* V5.12 Light Theme Profile — override terarah, Dark Mode tetap memakai desain existing. */
                html body:has(.profile-v11-theme-light) {
                    --profile-light-surface: #FFFFFF;
                    --profile-light-surface-soft: #F7F9FC;
                    --profile-light-text: #1F2937;
                    --profile-light-text-strong: #111827;
                    --profile-light-muted: #667085;
                    --profile-light-muted-soft: #7A8698;
                    --profile-light-border: #DCE3EC;
                    --profile-light-shadow: 0 16px 34px rgba(15, 23, 42, 0.08);
                }

                /* Kartu identitas dan statistik. */
                html body:has(.profile-v11-theme-light) .profile-v11-profile-card {
                    background:
                        radial-gradient(circle at 50% 7%, rgba(229, 57, 53, 0.12), transparent 24%),
                        radial-gradient(circle at 0% 0%, rgba(229, 57, 53, 0.07), transparent 34%),
                        linear-gradient(145deg, #FFFFFF, #FAFBFD) !important;
                    border-color: rgba(229, 57, 53, 0.22) !important;
                    box-shadow: var(--profile-light-shadow) !important;
                }

                html body:has(.profile-v11-theme-light) .profile-v11-profile-card::before {
                    background:
                        radial-gradient(circle at 18% 12%, rgba(255, 82, 82, 0.10), transparent 8%),
                        radial-gradient(circle at 80% 86%, rgba(229, 57, 53, 0.06), transparent 24%),
                        repeating-linear-gradient(135deg, rgba(31, 41, 55, 0.018) 0 1px, transparent 1px 14px) !important;
                    opacity: 1 !important;
                }

                html body:has(.profile-v11-theme-light) .profile-v11-avatar-wrap {
                    background: conic-gradient(from 210deg, #FFFFFF, rgba(229,57,53,0.10), rgba(255,82,82,0.48), #FFFFFF) !important;
                    box-shadow: 0 0 0 1px rgba(229,57,53,0.12), 0 18px 40px rgba(229,57,53,0.16) !important;
                }

                html body:has(.profile-v11-theme-light) .profile-v11-avatar-wrap::before {
                    background: #FFF9F9 !important;
                }

                html body:has(.profile-v11-theme-light) .profile-v11-fullname,
                html body:has(.profile-v11-theme-light) .profile-v11-joined span {
                    color: var(--profile-light-text-strong) !important;
                    text-shadow: none !important;
                }

                html body:has(.profile-v11-theme-light) .profile-v11-username,
                html body:has(.profile-v11-theme-light) .profile-v11-joined,
                html body:has(.profile-v11-theme-light) .profile-v11-joined strong {
                    color: var(--profile-light-muted) !important;
                }

                html body:has(.profile-v11-theme-light) .profile-v11-joined {
                    border-top-color: #E7EBF1 !important;
                }

                html body:has(.profile-v11-theme-light) .profile-v11-role-badge {
                    color: #42526B !important;
                    border-color: #D9E1EB !important;
                    background: linear-gradient(135deg, #FFFFFF, #F3F6FA) !important;
                    box-shadow: inset 0 1px 0 rgba(255,255,255,0.9), 0 8px 18px rgba(15,23,42,0.05) !important;
                }

                html body:has(.profile-v11-theme-light) .profile-v11-stats-card {
                    background:
                        radial-gradient(circle at 92% 8%, rgba(229,57,53,0.08), transparent 28%),
                        radial-gradient(circle at 8% 92%, rgba(29,161,242,0.06), transparent 26%),
                        linear-gradient(145deg, #FFFFFF, #F9FBFD) !important;
                    border-color: var(--profile-light-border) !important;
                    box-shadow: var(--profile-light-shadow) !important;
                }

                html body:has(.profile-v11-theme-light) .profile-v11-stats-card::before {
                    background:
                        linear-gradient(120deg, rgba(255,255,255,0.62), transparent 42%),
                        radial-gradient(circle at 86% 76%, rgba(229,57,53,0.06), transparent 28%) !important;
                }

                html body:has(.profile-v11-theme-light) .profile-v11-stats-title {
                    color: var(--profile-light-text-strong) !important;
                    text-shadow: none !important;
                }

                html body:has(.profile-v11-theme-light) .profile-v11-stats-note {
                    color: var(--profile-light-muted) !important;
                }

                html body:has(.profile-v11-theme-light) .profile-v11-metric-card {
                    border-color: rgba(229,57,53,0.20) !important;
                    background:
                        radial-gradient(circle at top right, rgba(229,57,53,0.08), transparent 28%),
                        linear-gradient(145deg, #FFFFFF, #FFF9F9) !important;
                    box-shadow: 0 12px 26px rgba(15,23,42,0.06), inset 0 1px 0 rgba(255,255,255,0.9) !important;
                }

                html body:has(.profile-v11-theme-light) .profile-v11-metric-label {
                    color: #475467 !important;
                }

                html body:has(.profile-v11-theme-light) .profile-v11-metric-value {
                    color: #D92D20 !important;
                    text-shadow: none !important;
                }

                html body:has(.profile-v11-theme-light) .profile-v11-metric-subtitle {
                    color: var(--profile-light-muted-soft) !important;
                }

                /* Expander foto profil dan uploader. */
                html body:has(.profile-v11-theme-light) [data-testid="stExpander"] {
                    border-color: var(--profile-light-border) !important;
                    background: #FFFFFF !important;
                    box-shadow: 0 12px 28px rgba(15,23,42,0.07) !important;
                }

                html body:has(.profile-v11-theme-light) [data-testid="stExpander"] summary,
                html body:has(.profile-v11-theme-light) [data-testid="stExpander"] summary * {
                    color: #344054 !important;
                }

                html body:has(.profile-v11-theme-light) .profile-v11-avatar-upload-title,
                html body:has(.profile-v11-theme-light) .profile-v11-upload-panel-title,
                html body:has(.profile-v11-theme-light) .profile-v11-current-photo-heading,
                html body:has(.profile-v11-theme-light) .profile-v11-uploader-title,
                html body:has(.profile-v11-theme-light) .profile-v11-selected-photo-heading {
                    color: var(--profile-light-text-strong) !important;
                }

                html body:has(.profile-v11-theme-light) .profile-v11-avatar-upload-desc,
                html body:has(.profile-v11-theme-light) .profile-v11-upload-panel-note,
                html body:has(.profile-v11-theme-light) .profile-v11-current-photo-text,
                html body:has(.profile-v11-theme-light) .profile-v11-uploader-helper,
                html body:has(.profile-v11-theme-light) .profile-v11-selected-photo-text,
                html body:has(.profile-v11-theme-light) .profile-v11-selected-photo-meta {
                    color: var(--profile-light-muted) !important;
                }

                /* Light theme: kedua badge status foto wajib kontras dan tidak saling menimpa. */
                html body:has(.profile-v11-theme-light) .profile-v11-current-photo-label {
                    color: #166534 !important;
                    -webkit-text-fill-color: #166534 !important;
                    background: #ECFDF3 !important;
                    border-color: #A7E3B8 !important;
                    text-shadow: none !important;
                    box-shadow: 0 4px 12px rgba(22, 101, 52, 0.08) !important;
                    user-select: none !important;
                    -webkit-user-select: none !important;
                }

                html body:has(.profile-v11-theme-light) .profile-v11-current-photo-label.is-default {
                    color: #92400E !important;
                    -webkit-text-fill-color: #92400E !important;
                    background: #FFF7ED !important;
                    border-color: #F6C98A !important;
                    box-shadow: 0 4px 12px rgba(146, 64, 14, 0.07) !important;
                }

                html body:has(.profile-v11-theme-light) .profile-v11-status-dot {
                    background: #22C55E !important;
                    color: #22C55E !important;
                    box-shadow: 0 0 0 4px rgba(34, 197, 94, 0.14) !important;
                }

                html body:has(.profile-v11-theme-light) .profile-v11-current-photo-label.is-default .profile-v11-status-dot {
                    background: #F59E0B !important;
                    color: #F59E0B !important;
                    box-shadow: 0 0 0 4px rgba(245, 158, 11, 0.14) !important;
                }

                /* Light theme: badge preview foto harus kontras dan mudah dibaca. */
                html body:has(.profile-v11-theme-light) .profile-v11-selected-photo-status {
                    color: #166534 !important;
                    -webkit-text-fill-color: #166534 !important;
                    background: #ECFDF3 !important;
                    border-color: #A7E3B8 !important;
                    text-shadow: none !important;
                    box-shadow: 0 4px 12px rgba(22, 101, 52, 0.08) !important;
                    user-select: none;
                    -webkit-user-select: none;
                }

                html body:has(.profile-v11-theme-light) .profile-v11-selected-photo-dot {
                    background: #22C55E !important;
                    box-shadow: 0 0 0 4px rgba(34, 197, 94, 0.14) !important;
                }

                html body:has(.profile-v11-theme-light) .profile-v11-upload-tip,
                html body:has(.profile-v11-theme-light) .profile-v11-current-photo-card,
                html body:has(.profile-v11-theme-light) .profile-v11-selected-photo-card,
                html body:has(.profile-v11-theme-light) .profile-v11-save-photo-box,
                html body:has(.profile-v11-theme-light) .profile-v11-upload-preview-card {
                    border-color: #E1E7EF !important;
                    background: #F9FBFD !important;
                    color: #344054 !important;
                    box-shadow: inset 0 1px 0 #FFFFFF, 0 10px 22px rgba(15,23,42,0.045) !important;
                }

                html body:has(.profile-v11-theme-light) [data-testid="stExpander"] [data-testid="stFileUploader"] section {
                    border-color: rgba(229,57,53,0.34) !important;
                    background:
                        radial-gradient(circle at 15% 20%, rgba(229,57,53,0.07), transparent 36%),
                        linear-gradient(135deg, #FFFFFF, #F7F9FC) !important;
                    box-shadow: inset 0 1px 0 #FFFFFF, 0 12px 24px rgba(15,23,42,0.06) !important;
                }

                html body:has(.profile-v11-theme-light) [data-testid="stExpander"] [data-testid="stFileUploader"] small,
                html body:has(.profile-v11-theme-light) [data-testid="stExpander"] [data-testid="stFileUploader"] div {
                    color: #667085 !important;
                }

                html body:has(.profile-v11-theme-light) [data-testid="stExpander"] [data-testid="stFileUploader"] button {
                    background: #FFF4F4 !important;
                    color: #B42318 !important;
                    border-color: rgba(229,57,53,0.34) !important;
                }

                html body:has(.profile-v11-theme-light) [data-testid="stExpander"] [data-testid="stFileUploader"] button:hover {
                    background: #E53935 !important;
                    color: #FFFFFF !important;
                }

                html body:has(.profile-v11-theme-light) [data-testid="stExpander"] [data-testid="stFileUploader"] [data-testid="stFileUploaderFile"] {
                    border-color: #E1E7EF !important;
                    background: #F8FAFC !important;
                    box-shadow: inset 0 1px 0 #FFFFFF, 0 8px 18px rgba(15,23,42,0.045) !important;
                }

                html body:has(.profile-v11-theme-light) [data-testid="stExpander"] [data-testid="stFileUploader"] [data-testid="stFileUploaderFileName"] {
                    color: #26364D !important;
                }

                html body:has(.profile-v11-theme-light) [data-testid="stExpander"] [data-testid="stFileUploader"] [data-testid="stFileUploaderFileData"] {
                    color: #667085 !important;
                }

                /* Hero Edit Profil. */
                html body:has(.profile-v11-theme-light) .profile-v11-edit-hero {
                    border-color: rgba(229,57,53,0.24) !important;
                    background:
                        radial-gradient(circle at 6% 8%, rgba(255,82,82,0.14), transparent 30%),
                        radial-gradient(circle at 94% 18%, rgba(29,161,242,0.08), transparent 25%),
                        linear-gradient(135deg, #FFF7F7, #FFFFFF 56%, #F5F9FF) !important;
                    box-shadow: 0 16px 34px rgba(15,23,42,0.075), inset 0 1px 0 #FFFFFF !important;
                }

                html body:has(.profile-v11-theme-light) .profile-v11-edit-hero::before {
                    background:
                        linear-gradient(115deg, rgba(255,255,255,0.68), transparent 38%),
                        repeating-linear-gradient(135deg, rgba(31,41,55,0.018) 0 1px, transparent 1px 16px) !important;
                }

                html body:has(.profile-v11-theme-light) .profile-v11-edit-eyebrow {
                    color: #B42318 !important;
                }

                html body:has(.profile-v11-theme-light) .profile-v11-edit-title {
                    color: var(--profile-light-text-strong) !important;
                    text-shadow: none !important;
                }

                html body:has(.profile-v11-theme-light) .profile-v11-edit-desc {
                    color: var(--profile-light-muted) !important;
                }

                html body:has(.profile-v11-theme-light) .profile-v11-edit-chip {
                    border-color: #D9E1EB !important;
                    background: rgba(255,255,255,0.78) !important;
                    color: #344054 !important;
                    box-shadow: inset 0 1px 0 #FFFFFF !important;
                }

                html body:has(.profile-v11-theme-light) .profile-v11-edit-chip:hover {
                    border-color: rgba(229,57,53,0.38) !important;
                    background: #FFF1F1 !important;
                    color: #B42318 !important;
                }

                html body:has(.profile-v11-theme-light) .profile-v11-edit-chip:hover span {
                    color: #D92D20 !important;
                }

                /* Form Edit Profil dan Ganti Password. */
                html body:has(.profile-v11-theme-light) [data-testid="stForm"] {
                    border-color: var(--profile-light-border) !important;
                    background:
                        radial-gradient(circle at 0% 0%, rgba(229,57,53,0.055), transparent 32%),
                        radial-gradient(circle at 100% 100%, rgba(29,161,242,0.045), transparent 28%),
                        linear-gradient(145deg, #FFFFFF, #FAFBFD) !important;
                    box-shadow: var(--profile-light-shadow), inset 0 1px 0 #FFFFFF !important;
                }

                html body:has(.profile-v11-theme-light) .profile-v11-form-tip-card,
                html body:has(.profile-v11-theme-light) .profile-v11-password-tip-card {
                    border-color: #E1E7EF !important;
                    background: #F8FAFC !important;
                    box-shadow: inset 0 1px 0 #FFFFFF, 0 8px 18px rgba(15,23,42,0.035) !important;
                }

                html body:has(.profile-v11-theme-light) .profile-v11-form-tip-title,
                html body:has(.profile-v11-theme-light) .profile-v11-password-tip-title {
                    color: #26364D !important;
                }

                html body:has(.profile-v11-theme-light) .profile-v11-form-tip-text,
                html body:has(.profile-v11-theme-light) .profile-v11-password-tip-text {
                    color: #667085 !important;
                }

                html body:has(.profile-v11-theme-light) .profile-v11-form-tip-card:hover .profile-v11-form-tip-title,
                html body:has(.profile-v11-theme-light) .profile-v11-password-tip-card:hover .profile-v11-password-tip-title {
                    color: #B42318 !important;
                }

                html body:has(.profile-v11-theme-light) .profile-v11-form-tip-card:hover .profile-v11-form-tip-text,
                html body:has(.profile-v11-theme-light) .profile-v11-password-tip-card:hover .profile-v11-password-tip-text {
                    color: #475467 !important;
                }

                html body:has(.profile-v11-theme-light) [data-testid="stForm"] [data-testid="stTextInput"] label p {
                    color: #344054 !important;
                }

                html body:has(.profile-v11-theme-light) [data-testid="stForm"] [data-testid="stTextInput"] input {
                    color: #1F2937 !important;
                    -webkit-text-fill-color: #1F2937 !important;
                    border-color: #D5DDE8 !important;
                    background: #FFFFFF !important;
                    box-shadow: inset 0 1px 0 #FFFFFF !important;
                }

                html body:has(.profile-v11-theme-light) [data-testid="stForm"] [data-testid="stTextInput"] input::placeholder {
                    color: #98A2B3 !important;
                    -webkit-text-fill-color: #98A2B3 !important;
                    opacity: 1 !important;
                }

                /* V5.12: Rapikan field Edit Profil pada Light Theme.
                   Border ditempatkan di wrapper BaseWeb agar simetris dan tidak terpotong oleh input internal. */
                html body:has(.profile-v11-theme-light) [data-testid="stForm"] [data-testid="stTextInput"] div[data-baseweb="input"] {
                    min-height: 56px !important;
                    border: 1.5px solid #D4DCE8 !important;
                    border-radius: 14px !important;
                    background: #FFFFFF !important;
                    box-shadow:
                        0 1px 2px rgba(15, 23, 42, 0.035),
                        inset 0 1px 0 rgba(255, 255, 255, 0.95) !important;
                    overflow: hidden !important;
                    transition: border-color 0.18s ease, box-shadow 0.18s ease !important;
                }

                html body:has(.profile-v11-theme-light) [data-testid="stForm"] [data-testid="stTextInput"] div[data-baseweb="input"]:hover {
                    border-color: #B8C3D3 !important;
                    box-shadow:
                        0 2px 8px rgba(15, 23, 42, 0.05),
                        inset 0 1px 0 rgba(255, 255, 255, 0.95) !important;
                }

                html body:has(.profile-v11-theme-light) [data-testid="stForm"] [data-testid="stTextInput"]:focus-within div[data-baseweb="input"] {
                    border-color: #F04438 !important;
                    box-shadow:
                        0 0 0 3px rgba(229, 57, 53, 0.10),
                        0 6px 16px rgba(15, 23, 42, 0.06),
                        inset 0 1px 0 rgba(255, 255, 255, 0.95) !important;
                }

                html body:has(.profile-v11-theme-light) [data-testid="stForm"] [data-testid="stTextInput"] div[data-baseweb="input"] input {
                    min-height: 53px !important;
                    padding: 0 16px !important;
                    border: 0 !important;
                    border-radius: 13px !important;
                    background: transparent !important;
                    box-shadow: none !important;
                    transform: none !important;
                }

                html body:has(.profile-v11-theme-light) [data-testid="stForm"] [data-testid="stTextInput"] div[data-baseweb="input"] input:hover,
                html body:has(.profile-v11-theme-light) [data-testid="stForm"] [data-testid="stTextInput"] div[data-baseweb="input"] input:focus {
                    border: 0 !important;
                    background: transparent !important;
                    box-shadow: none !important;
                    transform: none !important;
                }

                /* V5.12: Teks tombol Simpan Perubahan wajib kontras pada tombol primary Light Theme. */
                html body:has(.profile-v11-theme-light) [data-testid="stForm"] div[data-testid="stFormSubmitButton"] button[kind="primary"],
                html body:has(.profile-v11-theme-light) [data-testid="stForm"] div[data-testid="stFormSubmitButton"] button[kind="primary"] p,
                html body:has(.profile-v11-theme-light) [data-testid="stForm"] div[data-testid="stFormSubmitButton"] button[kind="primary"] span,
                html body:has(.profile-v11-theme-light) [data-testid="stForm"] div[data-testid="stFormSubmitButton"] button[kind="primary"] div {
                    color: #FFFFFF !important;
                    -webkit-text-fill-color: #FFFFFF !important;
                    opacity: 1 !important;
                    text-shadow: 0 1px 1px rgba(0, 0, 0, 0.14) !important;
                }

                html body:has(.profile-v11-theme-light) .profile-v11-form-submit-note {
                    border-color: rgba(76,175,80,0.22) !important;
                    background: #F0FAF3 !important;
                    color: #475467 !important;
                }

                html body:has(.profile-v11-theme-light) .profile-v11-form-submit-note strong {
                    color: #217A3C !important;
                }

                /* Hero keamanan password. */
                html body:has(.profile-v11-theme-light) .profile-v11-password-hero {
                    border-color: rgba(255,152,0,0.28) !important;
                    background:
                        radial-gradient(circle at 7% 10%, rgba(255,183,77,0.18), transparent 30%),
                        radial-gradient(circle at 93% 24%, rgba(229,57,53,0.07), transparent 26%),
                        linear-gradient(135deg, #FFF9EF, #FFFFFF 58%, #FFF7F7) !important;
                    box-shadow: 0 16px 34px rgba(15,23,42,0.075), inset 0 1px 0 #FFFFFF !important;
                }

                html body:has(.profile-v11-theme-light) .profile-v11-password-hero::before {
                    background:
                        linear-gradient(115deg, rgba(255,255,255,0.70), transparent 38%),
                        repeating-linear-gradient(135deg, rgba(31,41,55,0.016) 0 1px, transparent 1px 16px) !important;
                }

                html body:has(.profile-v11-theme-light) .profile-v11-password-eyebrow {
                    color: #B54708 !important;
                }

                html body:has(.profile-v11-theme-light) .profile-v11-password-title {
                    color: var(--profile-light-text-strong) !important;
                    text-shadow: none !important;
                }

                html body:has(.profile-v11-theme-light) .profile-v11-password-desc {
                    color: var(--profile-light-muted) !important;
                }

                html body:has(.profile-v11-theme-light) .profile-v11-password-chip {
                    border-color: #E5D5B7 !important;
                    background: rgba(255,255,255,0.80) !important;
                    color: #475467 !important;
                }

                html body:has(.profile-v11-theme-light) .profile-v11-password-chip:hover {
                    border-color: rgba(255,152,0,0.40) !important;
                    background: #FFF5E7 !important;
                    color: #B54708 !important;
                }

                html body:has(.profile-v11-theme-light) .profile-v11-password-chip:hover span {
                    color: #B54708 !important;
                }

                html body:has(.profile-v11-theme-light) .profile-v11-password-live-caption {
                    border-color: rgba(76,175,80,0.22) !important;
                    background: #EFFAF2 !important;
                    color: #2E7D46 !important;
                    box-shadow: inset 0 1px 0 #FFFFFF !important;
                }

                html body:has(.profile-v11-theme-light) .profile-v11-strength-panel {
                    border-color: #E1E7EF !important;
                    background: #F9FBFD !important;
                    box-shadow: inset 0 1px 0 #FFFFFF !important;
                }

                html body:has(.profile-v11-theme-light) .profile-v11-strength-label {
                    color: #26364D !important;
                }

                html body:has(.profile-v11-theme-light) .profile-v11-strength-note {
                    color: #667085 !important;
                }

                html body:has(.profile-v11-theme-light) .profile-v11-strength-badge {
                    background: #FFFFFF !important;
                    box-shadow: inset 0 1px 0 #FFFFFF !important;
                }

                html body:has(.profile-v11-theme-light) .profile-v11-strength-panel .profile-v11-strength-shell {
                    border-color: #D9E1EB !important;
                    background: #E8EDF3 !important;
                    box-shadow: inset 0 1px 3px rgba(15,23,42,0.08) !important;
                }

                html body:has(.profile-v11-theme-light) .profile-v11-password-submit-note {
                    border-color: rgba(255,152,0,0.24) !important;
                    background: #FFF8E8 !important;
                    color: #475467 !important;
                }

                html body:has(.profile-v11-theme-light) .profile-v11-password-submit-note strong {
                    color: #B54708 !important;
                }

                html body:has(.profile-v11-theme-light) .profile-v11-password-match-card {
                    border-color: #DDE4EC !important;
                    background: #F8FAFC !important;
                    color: #475467 !important;
                    box-shadow: none !important;
                }

                html body:has(.profile-v11-theme-light) .profile-v11-password-match-card.is-match {
                    border-color: rgba(76,175,80,0.30) !important;
                    background: #EFFAF2 !important;
                    color: #26713E !important;
                }

                html body:has(.profile-v11-theme-light) .profile-v11-password-match-card.is-mismatch {
                    border-color: rgba(244,67,54,0.28) !important;
                    background: #FFF1F1 !important;
                    color: #B42318 !important;
                }

                /* Zona Berbahaya tetap tegas, tetapi tidak menjadi blok gelap di Light Theme. */
                html body:has(.profile-v11-theme-light) .profile-v11-danger-card {
                    border-color: rgba(244,67,54,0.26) !important;
                    background:
                        radial-gradient(circle at 8% 8%, rgba(255,183,77,0.17), transparent 28%),
                        radial-gradient(circle at 94% 18%, rgba(244,67,54,0.10), transparent 27%),
                        linear-gradient(135deg, #FFF8F2, #FFFFFF 55%, #FFF2F2) !important;
                    box-shadow: 0 16px 34px rgba(15,23,42,0.075), inset 0 1px 0 #FFFFFF !important;
                }

                html body:has(.profile-v11-theme-light) .profile-v11-danger-card::before {
                    background:
                        linear-gradient(115deg, rgba(255,255,255,0.70), transparent 38%),
                        repeating-linear-gradient(135deg, rgba(31,41,55,0.016) 0 1px, transparent 1px 16px) !important;
                }

                html body:has(.profile-v11-theme-light) .profile-v11-danger-eyebrow {
                    color: #B42318 !important;
                }

                html body:has(.profile-v11-theme-light) .profile-v11-danger-title {
                    color: var(--profile-light-text-strong) !important;
                    text-shadow: none !important;
                }

                html body:has(.profile-v11-theme-light) .profile-v11-danger-text {
                    color: var(--profile-light-muted) !important;
                }

                html body:has(.profile-v11-theme-light) .profile-v11-danger-chip {
                    border-color: #E6D7C6 !important;
                    background: rgba(255,255,255,0.82) !important;
                    color: #475467 !important;
                    box-shadow: inset 0 1px 0 #FFFFFF !important;
                }

                html body:has(.profile-v11-theme-light) .profile-v11-danger-chip:hover {
                    border-color: rgba(244,67,54,0.34) !important;
                    background: #FFF1F1 !important;
                    color: #B42318 !important;
                }

                html body:has(.profile-v11-theme-light) .profile-v11-danger-chip:hover span {
                    color: #B42318 !important;
                }

                html body:has(.profile-v11-theme-light) .profile-v11-danger-panel {
                    border-color: #E1E7EF !important;
                    background:
                        radial-gradient(circle at 0% 0%, rgba(244,67,54,0.055), transparent 32%),
                        linear-gradient(145deg, #FFFFFF, #FAFBFD) !important;
                    box-shadow: var(--profile-light-shadow), inset 0 1px 0 #FFFFFF !important;
                }

                html body:has(.profile-v11-theme-light) .profile-v11-danger-step-card {
                    border-color: #E3E8EF !important;
                    background:
                        radial-gradient(circle at 100% 0%, rgba(244,67,54,0.065), transparent 36%),
                        #F9FBFD !important;
                    color: #344054 !important;
                    box-shadow: inset 0 1px 0 #FFFFFF !important;
                }

                html body:has(.profile-v11-theme-light) .profile-v11-danger-step-card:hover {
                    border-color: rgba(244,67,54,0.28) !important;
                    background: #FFF7F7 !important;
                }

                html body:has(.profile-v11-theme-light) .profile-v11-danger-step-title {
                    color: #26364D !important;
                }

                html body:has(.profile-v11-theme-light) .profile-v11-danger-step-text {
                    color: #667085 !important;
                }

                html body:has(.profile-v11-theme-light) .profile-v11-admin-lock-card {
                    border-color: rgba(76,175,80,0.24) !important;
                    background:
                        radial-gradient(circle at 0% 50%, rgba(76,175,80,0.11), transparent 31%),
                        linear-gradient(135deg, #F0FAF3, #FFFFFF) !important;
                    color: #344054 !important;
                }

                html body:has(.profile-v11-theme-light) .profile-v11-delete-confirm-card {
                    border-color: rgba(255,152,0,0.24) !important;
                    background:
                        radial-gradient(circle at 0% 50%, rgba(255,183,77,0.12), transparent 31%),
                        linear-gradient(135deg, #FFF8EB, #FFFFFF) !important;
                    color: #344054 !important;
                }

                html body:has(.profile-v11-theme-light) .profile-v11-admin-lock-title,
                html body:has(.profile-v11-theme-light) .profile-v11-delete-confirm-title {
                    color: #26364D !important;
                }

                html body:has(.profile-v11-theme-light) .profile-v11-admin-lock-text,
                html body:has(.profile-v11-theme-light) .profile-v11-delete-confirm-text {
                    color: #667085 !important;
                }

                html body:has(.profile-v11-theme-light) .profile-v11-admin-lock-pill {
                    color: #26713E !important;
                    background: #EAF8EE !important;
                    border-color: rgba(76,175,80,0.24) !important;
                    box-shadow: inset 0 1px 0 #FFFFFF !important;
                }

                /* Teks umum Streamlit di dalam halaman profil tetap kontras pada mode terang. */
                html body:has(.profile-v11-theme-light) [data-testid="stForm"] p,
                html body:has(.profile-v11-theme-light) [data-testid="stForm"] label,
                html body:has(.profile-v11-theme-light) [data-testid="stCheckbox"] label,
                html body:has(.profile-v11-theme-light) [data-testid="stCheckbox"] p {
                    color: #344054 !important;
                }
            </style>
            """,
            unsafe_allow_html=True,
        )
    except Exception as error:
        st.error(f"Gaya halaman profil belum dapat dimuat: {error}")


# -----------------------------------------------------------------------------
# Helper umum
# -----------------------------------------------------------------------------


def _safe_text(value: Any, fallback: str = "-") -> str:
    """Ubah nilai menjadi teks aman untuk HTML."""
    try:
        if value is None:
            return fallback
        cleaned = str(value).strip()
        return cleaned if cleaned else fallback
    except Exception:
        return fallback


def _escape(value: Any, fallback: str = "-") -> str:
    """Escape teks agar aman dirender dengan unsafe_allow_html."""
    try:
        return html.escape(_safe_text(value, fallback=fallback))
    except Exception:
        return html.escape(fallback)


def _set_flash(message: str, level: str = "success") -> None:
    """Simpan pesan sementara agar tetap tampil setelah rerun."""
    try:
        st.session_state["profile_v11_flash"] = {
            "message": str(message),
            "level": str(level),
        }
    except Exception as error:
        st.error(f"Pesan konfirmasi belum dapat disiapkan: {error}")


def _render_flash() -> None:
    """Tampilkan pesan sementara satu kali."""
    try:
        flash = st.session_state.pop("profile_v11_flash", None)
        if not flash:
            return

        message = str(flash.get("message", ""))
        level = str(flash.get("level", "success"))
        if level == "error":
            st.error(message)
        elif level == "warning":
            st.warning(message)
        else:
            st.success(message)
    except Exception as error:
        st.error(f"Pesan konfirmasi belum dapat ditampilkan: {error}")


def _format_datetime_id(value: Any) -> str:
    """Ubah timestamp menjadi format Indonesia yang mudah dibaca."""
    try:
        if value in (None, ""):
            return "Belum tersedia"

        if isinstance(value, datetime):
            parsed = value
        else:
            raw_value = str(value).strip()
            parsed = None
            supported_formats = (
                "%Y-%m-%d %H:%M:%S.%f",
                "%Y-%m-%d %H:%M:%S",
                "%Y-%m-%dT%H:%M:%S.%f",
                "%Y-%m-%dT%H:%M:%S",
                "%Y-%m-%d",
            )
            for date_format in supported_formats:
                try:
                    parsed = datetime.strptime(raw_value, date_format)
                    break
                except ValueError:
                    continue
            if parsed is None:
                try:
                    parsed = datetime.fromisoformat(raw_value)
                except ValueError:
                    return raw_value

        month_name = MONTH_NAMES_ID.get(parsed.month, str(parsed.month))
        return f"{parsed.day} {month_name} {parsed.year}, {parsed.strftime('%H:%M')}"
    except Exception as error:
        st.error(f"Tanggal belum dapat diformat: {error}")
        return "Belum tersedia"


def _get_initial(fullname: str, username: str) -> str:
    """Ambil inisial huruf pertama dari nama, fallback ke username."""
    try:
        source = (fullname or username or "Pengguna").strip()
        if not source:
            return "P"
        return source[0].upper()
    except Exception:
        return "P"


def _validate_email(email: str) -> bool:
    """Periksa format email; email kosong diperbolehkan pada form profil."""
    try:
        cleaned_email = email.strip()
        if cleaned_email == "":
            return True
        return bool(EMAIL_PATTERN.fullmatch(cleaned_email))
    except Exception as error:
        st.error(f"Format email belum dapat diperiksa: {error}")
        return False


def _format_file_size(size_bytes: int) -> str:
    """Ubah ukuran file byte menjadi teks singkat yang mudah dibaca."""
    try:
        if size_bytes < 1024:
            return f"{size_bytes} B"
        if size_bytes < 1024 * 1024:
            return f"{size_bytes / 1024:.1f} KB"
        return f"{size_bytes / (1024 * 1024):.1f} MB"
    except Exception:
        return "Ukuran tidak diketahui"


# -----------------------------------------------------------------------------
# Helper gambar profil opsional
# -----------------------------------------------------------------------------


def _decode_image_bytes(image_bytes: bytes) -> Image.Image | None:
    """Dekode byte gambar menjadi objek PIL yang aman digunakan."""
    try:
        with Image.open(BytesIO(image_bytes)) as image:
            image.load()
            normalized = ImageOps.exif_transpose(image).convert("RGB")
            return normalized.copy()
    except (UnidentifiedImageError, OSError, ValueError, Image.DecompressionBombError):
        return None
    except Exception as error:
        st.error(f"Foto profil belum dapat dibaca: {error}")
        return None


def _image_to_data_uri(image: Image.Image | None) -> str:
    """Ubah gambar PIL menjadi data URI agar preview dapat dirender rapi dalam satu HTML card."""
    try:
        if image is None:
            return ""
        normalized = ImageOps.fit(
            image.convert("RGB"),
            AVATAR_OUTPUT_SIZE,
            method=Image.Resampling.LANCZOS,
            centering=(0.5, 0.5),
        )
        output_buffer = BytesIO()
        normalized.save(output_buffer, format="PNG", optimize=True)
        encoded = base64.b64encode(output_buffer.getvalue()).decode("ascii")
        return f"data:image/png;base64,{encoded}"
    except Exception as error:
        st.error(f"Preview foto profil belum dapat dibuat: {error}")
        return ""


def _load_current_avatar(user: dict[str, Any]) -> Image.Image | None:
    """Muat foto profil pengguna jika sudah pernah diunggah."""
    try:
        profile_picture = user.get("profile_picture")
        if profile_picture:
            decoded_image = _decode_image_bytes(bytes(profile_picture))
            if decoded_image is not None:
                return decoded_image

        if DEFAULT_AVATAR_PATH.exists():
            with Image.open(DEFAULT_AVATAR_PATH) as image:
                image.load()
                normalized = ImageOps.exif_transpose(image).convert("RGB")
                return normalized.copy()
        return None
    except Exception as error:
        st.error(f"Foto profil belum dapat dimuat: {error}")
        return None


def _prepare_avatar(image_bytes: bytes) -> tuple[bytes, Image.Image]:
    """Validasi, potong persegi, dan resize avatar menjadi 200x200 piksel."""
    try:
        with Image.open(BytesIO(image_bytes)) as verification_image:
            verification_image.verify()

        with Image.open(BytesIO(image_bytes)) as image:
            image.load()
            normalized = ImageOps.exif_transpose(image).convert("RGB")
            resized = ImageOps.fit(
                normalized,
                AVATAR_OUTPUT_SIZE,
                method=Image.Resampling.LANCZOS,
                centering=(0.5, 0.5),
            )

            output_buffer = BytesIO()
            resized.save(output_buffer, format="PNG", optimize=True)
            return output_buffer.getvalue(), resized.copy()
    except Image.DecompressionBombError as error:
        raise ValueError("Resolusi gambar terlalu besar dan tidak aman diproses.") from error
    except (UnidentifiedImageError, OSError, ValueError) as error:
        raise ValueError("File tidak dapat dibaca sebagai gambar JPG atau PNG yang valid.") from error
    except Exception as error:
        raise ValueError(f"Gambar gagal diproses: {error}") from error


# -----------------------------------------------------------------------------
# Helper password dan database profil
# -----------------------------------------------------------------------------


def _password_strength(password: str) -> dict[str, Any]:
    """Tentukan indikator kekuatan password sesuai panjang karakter."""
    try:
        password_length = len(password or "")
        if password_length == 0:
            return {
                "label": "Belum diisi",
                "color": "#666666",
                "width": "0%",
                "note": "Ketik password baru untuk melihat indikator kekuatannya.",
            }
        if password_length < 6:
            return {
                "label": "Lemah",
                "color": "#F44336",
                "width": "33%",
                "note": "Password masih kurang dari 6 karakter.",
            }
        if 6 <= password_length <= 9:
            return {
                "label": "Sedang",
                "color": "#FF9800",
                "width": "66%",
                "note": "Sudah memenuhi minimum, tetapi lebih baik dibuat lebih panjang.",
            }
        return {
            "label": "Kuat",
            "color": "#4CAF50",
            "width": "100%",
            "note": "Panjang password sudah baik. Tambahkan kombinasi huruf dan angka bila perlu.",
        }
    except Exception as error:
        st.error(f"Kekuatan password belum dapat dihitung: {error}")
        return {
            "label": "Tidak diketahui",
            "color": "#666666",
            "width": "0%",
            "note": "Periksa kembali password yang diketik.",
        }


def _render_password_strength(password: str) -> None:
    """Render indikator kekuatan password berbasis HTML."""
    try:
        strength = _password_strength(password)
        label = str(strength["label"])
        level_class = {
            "Belum diisi": "idle",
            "Lemah": "weak",
            "Sedang": "medium",
            "Kuat": "strong",
        }.get(label, "idle")
        icon = {
            "Belum diisi": "🕯️",
            "Lemah": "⚠️",
            "Sedang": "🧩",
            "Kuat": "🛡️",
        }.get(label, "🔎")
        st.markdown(
            f"""
            <div class="profile-v11-strength-panel profile-v11-strength-{level_class}">
                <div class="profile-v11-strength-head">
                    <div class="profile-v11-strength-icon">{icon}</div>
                    <div>
                        <p class="profile-v11-strength-label">Kekuatan password</p>
                        <p class="profile-v11-strength-note">{html.escape(str(strength['note']))}</p>
                    </div>
                    <strong class="profile-v11-strength-badge" style="color:{strength['color']};">
                        {html.escape(label)}
                    </strong>
                </div>
                <div class="profile-v11-strength-shell">
                    <div class="profile-v11-strength-fill" style="width:{strength['width']};background:{strength['color']};"></div>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )
    except Exception as error:
        st.error(f"Indikator password belum dapat ditampilkan: {error}")


def _render_password_match_status(new_password: str, confirm_password: str) -> None:
    """Tampilkan status kecocokan password baru dan konfirmasi secara live."""
    try:
        if not new_password and not confirm_password:
            return

        if not confirm_password:
            card_class = ""
            icon = "⌛"
            message = "Ketik ulang password baru pada kolom konfirmasi."
        elif new_password == confirm_password:
            card_class = "is-match"
            icon = "✅"
            message = "Konfirmasi cocok. Password siap disimpan setelah password lama benar."
        else:
            card_class = "is-mismatch"
            icon = "⚠️"
            message = "Konfirmasi belum sama dengan password baru. Periksa kembali sebelum menyimpan."

        st.markdown(
            f"""
            <div class="profile-v11-password-match-card {card_class}">
                <span class="profile-v11-password-match-icon">{icon}</span>
                <span>{html.escape(message)}</span>
            </div>
            """,
            unsafe_allow_html=True,
        )
    except Exception as error:
        st.error(f"Status konfirmasi password belum dapat ditampilkan: {error}")


def _update_password_minimum_six(
    user_id: int, old_password: str, new_password: str
) -> tuple[bool, str]:
    """Ubah password profil dengan validasi password lama dan minimum 6 karakter."""
    try:
        if len(new_password) < 6:
            return False, "Password baru minimal 6 karakter."

        user = get_user_by_id(user_id)
        if user is None:
            return False, "User tidak ditemukan. Silakan login ulang."

        password_hash = str(user.get("password_hash") or "")
        if not verify_password(old_password, password_hash):
            return False, "Password lama tidak sesuai."

        new_password_hash = hash_password(new_password)
        if not new_password_hash:
            return False, "Password baru gagal dienkripsi."

        with sqlite3.connect(get_db_path()) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "UPDATE users SET password_hash = ? WHERE user_id = ?",
                (new_password_hash, user_id),
            )
            if cursor.rowcount == 0:
                return False, "User tidak ditemukan di database."
            conn.commit()

        revoke_all_remember_tokens(user_id)
        return True, "Password berhasil diubah. Silakan gunakan password baru pada login berikutnya."
    except Exception as error:
        return False, f"Gagal mengubah password: {error}"


def _get_usage_stats(user_id: int, user: dict[str, Any]) -> dict[str, str]:
    """Ambil statistik penggunaan; gunakan fallback jika kolom belum tersedia."""
    try:
        total_sessions: Any = None
        last_login: Any = None

        with sqlite3.connect(get_db_path()) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("PRAGMA table_info(users)")
            columns = {str(row["name"]) for row in cursor.fetchall()}

            selected_columns = []
            for candidate in ("login_count", "total_login", "total_sessions"):
                if candidate in columns:
                    selected_columns.append(candidate)
                    break
            for candidate in ("last_login", "last_login_at", "updated_at"):
                if candidate in columns:
                    selected_columns.append(candidate)
                    break

            if selected_columns:
                query = f"SELECT {', '.join(selected_columns)} FROM users WHERE user_id = ?"
                cursor.execute(query, (user_id,))
                row = cursor.fetchone()
                if row:
                    for key in row.keys():
                        if key in ("login_count", "total_login", "total_sessions"):
                            total_sessions = row[key]
                        if key in ("last_login", "last_login_at", "updated_at"):
                            last_login = row[key]

        if total_sessions in (None, ""):
            session_key = f"profile_v11_total_session_{user_id}"
            if session_key not in st.session_state:
                st.session_state[session_key] = 1
            total_sessions = st.session_state[session_key]

        if last_login in (None, ""):
            last_key = f"profile_v11_last_login_{user_id}"
            if last_key not in st.session_state:
                st.session_state[last_key] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            last_login = st.session_state[last_key]

        return {
            "total_sessions": str(total_sessions),
            "last_login": _format_datetime_id(last_login),
            "created_at": _format_datetime_id(user.get("created_at")),
        }
    except Exception as error:
        st.error(f"Statistik penggunaan belum dapat dibaca: {error}")
        return {
            "total_sessions": "1",
            "last_login": _format_datetime_id(datetime.now()),
            "created_at": _format_datetime_id(user.get("created_at")),
        }


def _logout_after_delete(user_id: int) -> None:
    """Bersihkan sesi setelah akun dihapus lalu arahkan ke login."""
    try:
        active_token = st.session_state.get("active_remember_token")
        if active_token:
            revoke_remember_token(str(active_token))
        revoke_all_remember_tokens(user_id)

        try:
            from auth.login import clear_remember_cookie

            clear_remember_cookie()
        except Exception:
            # Cookie remember-me tidak wajib ada. Jika gagal, session tetap dibersihkan.
            pass

        st.session_state.clear()
        st.session_state["logged_in"] = False
        st.session_state["page"] = "login"
        st.session_state["selected_page"] = "Beranda"
        st.session_state["_startup_loading_active"] = False
        st.rerun()
    except Exception as error:
        st.error(f"Logout otomatis setelah hapus akun belum berhasil: {error}")


# -----------------------------------------------------------------------------
# Komponen UI halaman
# -----------------------------------------------------------------------------


def _render_profile_card(user: dict[str, Any]) -> None:
    """Render section 1: profile card dengan avatar inisial."""
    try:
        fullname = _safe_text(user.get("fullname"), "Pengguna")
        username = _safe_text(user.get("username"), "pengguna")
        role = normalize_role(
            _safe_text(user.get("role"), DEFAULT_ROLE),
            user.get("user_id"),
        )
        role_label = get_role_label(role, user.get("user_id"))
        joined_at = _format_datetime_id(user.get("created_at"))
        initial = _get_initial(fullname, username)

        st.markdown(
            f"""
            <div class="profile-v11-card profile-v11-identity profile-v11-profile-card">
                <div class="profile-v11-avatar-wrap">
                    <div class="profile-v11-avatar">{html.escape(initial)}</div>
                </div>
                <h2 class="profile-v11-fullname">{html.escape(fullname)}</h2>
                <div class="profile-v11-username">@{html.escape(username)}</div>
                <div class="profile-v11-badge-row">
                    <span class="profile-v11-badge profile-v11-badge-primary"><span class="profile-v11-badge-icon">👥</span>Researcher</span>
                    <span class="profile-v11-badge profile-v11-role-badge"><span class="profile-v11-badge-icon">🛡️</span>{html.escape(role_label)}</span>
                </div>
                <div class="profile-v11-joined">
                    <div class="profile-v11-joined-icon">📅</div>
                    <div>
                        <strong>Tanggal bergabung</strong>
                        <span>{html.escape(joined_at)}</span>
                    </div>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )
    except Exception as error:
        st.error(f"Profile card belum dapat ditampilkan: {error}")


def _render_optional_avatar_upload(user_id: int, user: dict[str, Any]) -> None:
    """Render upload foto profil opsional dalam layout horizontal penuh."""
    try:
        _, upload_pending, _ = _status_loading_upload_foto()
        with st.expander("📸 Foto profil opsional", expanded=upload_pending):
            st.markdown(
                """
                <div class="profile-v11-avatar-upload-intro">
                    <div class="profile-v11-avatar-upload-icon">📸</div>
                    <div>
                        <h3 class="profile-v11-avatar-upload-title">Lengkapi Foto Profil</h3>
                        <p class="profile-v11-avatar-upload-desc">
                            Bagian ini opsional. Foto disimpan sebagai data profil tambahan,
                            sedangkan profile card utama tetap memakai avatar inisial agar desain tetap konsisten.
                        </p>
                    </div>
                    <div class="profile-v11-upload-tip-grid">
                        <div class="profile-v11-upload-tip"><span>🖼️</span><strong>JPG / PNG</strong></div>
                        <div class="profile-v11-upload-tip"><span>📦</span><strong>Maks. 2 MB</strong></div>
                        <div class="profile-v11-upload-tip"><span>✂️</span><strong>Auto 200×200</strong></div>
                    </div>
                </div>
                """,
                unsafe_allow_html=True,
            )

            current_avatar = _load_current_avatar(user)
            info_col, upload_col = st.columns([1.0, 1.18], gap="large")

            with info_col:
                has_saved_avatar = bool(user.get("profile_picture"))
                avatar_data_uri = _image_to_data_uri(current_avatar)

                if avatar_data_uri:
                    avatar_preview_html = (
                        f'<img class="profile-v11-current-photo-img" src="{avatar_data_uri}" '
                        'alt="Preview foto profil saat ini">'
                    )
                else:
                    avatar_preview_html = '<div class="profile-v11-current-photo-placeholder">+</div>'

                status_class = "" if has_saved_avatar else " is-default"
                status_text = "Tersimpan di database" if has_saved_avatar else "Menggunakan avatar bawaan"
                heading_text = "Foto profil saat ini" if has_saved_avatar else "Belum ada foto profil"
                body_text = (
                    "Foto sudah aktif dan tersimpan. Unggah file baru di panel kanan untuk mengganti foto ini."
                    if has_saved_avatar
                    else "Panel ini menampilkan avatar bawaan. Unggah file JPG/PNG di panel kanan untuk menambahkan foto profil."
                )

                st.markdown(
                    f"""
                    <div class="profile-v11-upload-panel-title">Foto yang tersimpan</div>
                    <p class="profile-v11-upload-panel-note">
                        Preview dibuat dalam satu kartu agar foto, status, dan keterangan sejajar rapi.
                    </p>
                    <div class="profile-v11-current-photo-card">
                        <div class="profile-v11-current-photo-frame">
                            {avatar_preview_html}
                        </div>
                        <div class="profile-v11-current-photo-content">
                            <div class="profile-v11-current-photo-label{status_class}">
                                <span class="profile-v11-status-dot"></span>{html.escape(status_text)}
                            </div>
                            <h4 class="profile-v11-current-photo-heading">{html.escape(heading_text)}</h4>
                            <p class="profile-v11-current-photo-text">{html.escape(body_text)}</p>
                        </div>
                    </div>
                    <div class="profile-v11-current-photo-bottom-gap"></div>
                    """,
                    unsafe_allow_html=True,
                )

            with upload_col:
                st.markdown(
                    """
                    <div class="profile-v11-uploader-title">⬆️ Unggah foto baru</div>
                    <div class="profile-v11-uploader-helper">
                        Pilih foto wajah yang jelas. Sistem akan memotong dan menyesuaikan ukuran otomatis.
                    </div>
                    """,
                    unsafe_allow_html=True,
                )

                uploader_version = int(st.session_state.get("profile_v11_uploader_version", 0))
                uploaded_file = st.file_uploader(
                    "Pilih file JPG/PNG maksimal 2 MB",
                    type=["jpg", "jpeg", "png"],
                    accept_multiple_files=False,
                    label_visibility="collapsed",
                    key=f"profile_v11_photo_uploader_{uploader_version}",
                    on_change=_antrekan_loading_upload_foto,
                    args=("Menyiapkan preview foto profil...",),
                )

            if uploaded_file is None:
                return

            raw_bytes = uploaded_file.getvalue()
            file_size = len(raw_bytes)
            mime_type = str(getattr(uploaded_file, "type", "") or "").lower()

            if file_size == 0:
                st.error("File foto kosong. Silakan pilih file lain.")
                return
            if file_size > MAX_AVATAR_SIZE_BYTES:
                st.error(
                    f"Ukuran foto {file_size / (1024 * 1024):.2f} MB. Batas maksimal adalah 2 MB."
                )
                return
            if mime_type and mime_type not in ALLOWED_IMAGE_TYPES:
                st.error("Format file tidak didukung. Gunakan JPG, JPEG, atau PNG.")
                return

            try:
                processed_bytes, preview_image = _prepare_avatar(raw_bytes)
            except ValueError as error:
                st.error(str(error))
                return

            preview_data_uri = _image_to_data_uri(preview_image)
            uploaded_name = _safe_text(getattr(uploaded_file, "name", "foto_profil.png"), "foto_profil.png")
            uploaded_size = _format_file_size(file_size)

            st.markdown(
                f"""
                <div class="profile-v11-selected-photo-card">
                    <div class="profile-v11-selected-photo-frame">
                        <img class="profile-v11-selected-photo-img" src="{preview_data_uri}" alt="Preview foto baru">
                    </div>
                    <div class="profile-v11-selected-photo-content">
                        <div class="profile-v11-selected-photo-status">
                            <span class="profile-v11-selected-photo-dot"></span>Preview siap disimpan
                        </div>
                        <h4 class="profile-v11-selected-photo-heading">{html.escape(uploaded_name)}</h4>
                        <p class="profile-v11-selected-photo-text">
                            Foto sudah dipotong otomatis menjadi rasio persegi dan disiapkan sebagai avatar 200 × 200 px.
                        </p>
                        <div class="profile-v11-selected-photo-meta">
                            <span class="profile-v11-selected-photo-chip">📦 {html.escape(uploaded_size)}</span>
                            <span class="profile-v11-selected-photo-chip">✂️ 200 × 200 px</span>
                            <span class="profile-v11-selected-photo-chip">🖼️ PNG tersimpan</span>
                        </div>
                    </div>
                </div>
                <div class="profile-v11-save-photo-box">
                    Periksa preview di atas. Jika sudah sesuai, klik tombol simpan di bawah ini.
                    Gunakan tombol silang pada file terpilih jika ingin mengganti gambar.
                </div>
                <div class="profile-v11-save-button-spacer"></div>
                """,
                unsafe_allow_html=True,
            )

            if st.button(
                "Simpan Foto Profil",
                type="primary",
                use_container_width=True,
                key="profile_v11_save_photo",
                on_click=_antrekan_loading_upload_foto,
                args=("Menyimpan foto profil...",),
            ):
                saved = update_profile_picture(user_id, processed_bytes)
                if not saved:
                    log_activity(
                        "PROFILE_PHOTO_UPDATE",
                        "Profil",
                        "Pembaruan foto profil gagal disimpan.",
                        status="failed",
                        metadata={"file_name": uploaded_name, "file_size": file_size},
                    )
                    st.error("Foto profil gagal disimpan ke database.")
                    return
                log_activity(
                    "PROFILE_PHOTO_UPDATE",
                    "Profil",
                    "Foto profil berhasil diperbarui.",
                    metadata={"file_name": uploaded_name, "file_size": file_size},
                )
                st.session_state["profile_v11_uploader_version"] = uploader_version + 1
                _set_flash("Foto profil berhasil diperbarui.", "success")
                _antrekan_loading_upload_foto("Memuat ulang foto profil terbaru...")
                st.rerun()
    except Exception as error:
        st.error(f"Upload foto profil belum dapat ditampilkan: {error}")


def _render_usage_statistics(user_id: int, user: dict[str, Any]) -> None:
    """Render section 4: statistik penggunaan."""
    try:
        stats = _get_usage_stats(user_id, user)
        st.markdown(
            f"""
            <div class="profile-v11-card profile-v11-stats-card">
                <div class="profile-v11-stats-heading">
                    <div class="profile-v11-stats-icon" aria-hidden="true"><span></span><span></span><span></span></div>
                    <h2 class="profile-v11-stats-title">Statistik Penggunaan</h2>
                </div>
                <p class="profile-v11-stats-note">
                    Ringkasan aktivitas akun. Jika database belum memiliki kolom riwayat login,
                    dashboard memakai fallback sesi saat ini agar halaman tetap bisa diuji.
                </p>
                <div class="profile-v11-metric-grid">
                    <div class="profile-v11-metric-card">
                        <div class="profile-v11-metric-head">
                            <div class="profile-v11-metric-icon">👤</div>
                            <div class="profile-v11-metric-label">Total sesi login</div>
                        </div>
                        <div class="profile-v11-metric-value">{html.escape(stats['total_sessions'])}</div>
                        <div class="profile-v11-metric-accent-line"></div>
                        <div class="profile-v11-metric-subtitle">Sumber: session/database jika tersedia</div>
                    </div>
                    <div class="profile-v11-metric-card">
                        <div class="profile-v11-metric-head">
                            <div class="profile-v11-metric-icon">🕒</div>
                            <div class="profile-v11-metric-label">Terakhir login</div>
                        </div>
                        <div class="profile-v11-metric-value profile-v11-date-value">{html.escape(stats['last_login'])}</div>
                        <div class="profile-v11-metric-accent-line"></div>
                        <div class="profile-v11-metric-subtitle">Ditampilkan dalam waktu lokal perangkat</div>
                    </div>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )
    except Exception as error:
        st.error(f"Statistik penggunaan belum dapat ditampilkan: {error}")


def _render_profile_no_changes_alert() -> None:
    """Tampilkan kartu informasi ketika belum ada perubahan profil."""
    st.markdown(
        """
        <style>
            @keyframes profileV12AlertEnter {
                from { opacity: 0; transform: translateY(-8px) scale(0.985); }
                to { opacity: 1; transform: translateY(0) scale(1); }
            }
            @keyframes profileV12AlertPulse {
                0%, 100% { box-shadow: 0 0 0 0 rgba(255, 167, 38, 0.18); }
                50% { box-shadow: 0 0 0 8px rgba(255, 167, 38, 0); }
            }
            .profile-v12-no-change-alert {
                display: flex;
                align-items: center;
                gap: 0.9rem;
                margin: 0.85rem 0 0.15rem;
                padding: 0.92rem 1rem;
                border: 1px solid rgba(255, 167, 38, 0.30);
                border-radius: 17px;
                background:
                    radial-gradient(circle at 4% 18%, rgba(255, 167, 38, 0.12), transparent 34%),
                    linear-gradient(135deg, rgba(33, 27, 18, 0.96), rgba(16, 22, 32, 0.98));
                color: #F4F7FB;
                animation: profileV12AlertEnter 260ms ease-out both;
            }
            .profile-v12-no-change-icon {
                display: flex;
                align-items: center;
                justify-content: center;
                width: 42px;
                height: 42px;
                min-width: 42px;
                border-radius: 14px;
                border: 1px solid rgba(255, 167, 38, 0.36);
                background: rgba(255, 167, 38, 0.13);
                color: #FFD180;
                font-size: 1.05rem;
                animation: profileV12AlertPulse 2s ease-in-out infinite;
            }
            .profile-v12-no-change-title {
                color: #FFFFFF;
                font-size: 0.94rem;
                font-weight: 850;
                line-height: 1.25;
            }
            .profile-v12-no-change-text {
                color: #B8C2D2;
                font-size: 0.82rem;
                line-height: 1.55;
                margin-top: 0.16rem;
            }
            html body:has(.profile-v11-theme-light) .profile-v12-no-change-alert {
                border-color: rgba(255, 167, 38, 0.28);
                background:
                    radial-gradient(circle at 4% 18%, rgba(255, 167, 38, 0.10), transparent 36%),
                    linear-gradient(135deg, #FFF9ED, #FFFFFF);
                color: #344054;
                box-shadow: 0 10px 24px rgba(15, 23, 42, 0.06);
            }
            html body:has(.profile-v11-theme-light) .profile-v12-no-change-icon {
                background: #FFF2D7;
                color: #B54708;
            }
            html body:has(.profile-v11-theme-light) .profile-v12-no-change-title {
                color: #7A2E0E;
            }
            html body:has(.profile-v11-theme-light) .profile-v12-no-change-text {
                color: #667085;
            }
        </style>
        <div class="profile-v12-no-change-alert" role="status" aria-live="polite">
            <div class="profile-v12-no-change-icon">ℹ</div>
            <div>
                <div class="profile-v12-no-change-title">Belum ada perubahan yang dapat disimpan</div>
                <div class="profile-v12-no-change-text">
                    Ubah nama lengkap atau email terlebih dahulu, lalu klik Simpan Perubahan kembali.
                </div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def _render_edit_profile_form(user_id: int, user: dict[str, Any]) -> None:
    """Render section 2: form edit profil."""
    try:
        st.markdown(
            """
            <div class="profile-v11-edit-hero">
                <div class="profile-v11-edit-hero-inner">
                    <div class="profile-v11-edit-icon">✏️</div>
                    <div>
                        <p class="profile-v11-edit-eyebrow">Pengaturan Identitas</p>
                        <h2 class="profile-v11-edit-title">Edit Profil Akun</h2>
                        <p class="profile-v11-edit-desc">
                            Perbarui nama lengkap dan email yang akan tampil pada dashboard.
                            Data tersimpan langsung ke database setelah tombol simpan ditekan.
                        </p>
                    </div>
                    <div class="profile-v11-edit-chips">
                        <span class="profile-v11-edit-chip"><span>🛡️</span>Aman</span>
                        <span class="profile-v11-edit-chip"><span>💾</span>SQLite</span>
                        <span class="profile-v11-edit-chip"><span>⚡</span>Instan</span>
                    </div>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        with st.form("profile_v11_edit_form", clear_on_submit=False):
            st.markdown(
                """
                <div class="profile-v11-form-intro">
                    <div class="profile-v11-form-tip-card">
                        <div class="profile-v11-form-tip-icon">👤</div>
                        <div>
                            <p class="profile-v11-form-tip-title">Nama tampil</p>
                            <p class="profile-v11-form-tip-text">Gunakan nama yang mudah dikenali di dashboard.</p>
                        </div>
                    </div>
                    <div class="profile-v11-form-tip-card">
                        <div class="profile-v11-form-tip-icon">✉️</div>
                        <div>
                            <p class="profile-v11-form-tip-title">Email opsional</p>
                            <p class="profile-v11-form-tip-text">Boleh dikosongkan, tetapi format harus valid bila diisi.</p>
                        </div>
                    </div>
                    <div class="profile-v11-form-tip-card">
                        <div class="profile-v11-form-tip-icon">✅</div>
                        <div>
                            <p class="profile-v11-form-tip-title">Validasi otomatis</p>
                            <p class="profile-v11-form-tip-text">Sistem mengecek nama dan email sebelum menyimpan.</p>
                        </div>
                    </div>
                </div>
                """,
                unsafe_allow_html=True,
            )

            fullname_col, email_col = st.columns([1, 1], gap="large")
            with fullname_col:
                fullname = st.text_input(
                    "Nama Lengkap",
                    value=str(user.get("fullname") or ""),
                    max_chars=100,
                    placeholder="Contoh: Aulia Rahmadiva Wardana",
                )
            with email_col:
                email = st.text_input(
                    "Email (opsional)",
                    value=str(user.get("email") or ""),
                    max_chars=150,
                    placeholder="contoh@email.com",
                )

            st.markdown(
                """
                <div class="profile-v11-form-submit-note">
                    <span>💡</span>
                    <div><strong>Tips:</strong> cek kembali nama dan email sebelum menyimpan agar identitas akun tetap rapi.</div>
                </div>
                """,
                unsafe_allow_html=True,
            )
            submitted = st.form_submit_button(
                "💾 Simpan Perubahan",
                type="primary",
                use_container_width=True,
            )

        if not submitted:
            return

        cleaned_fullname = fullname.strip()
        cleaned_email = email.strip().lower()
        original_fullname = str(user.get("fullname") or "").strip()
        original_email = str(user.get("email") or "").strip().lower()

        if (
            cleaned_fullname == original_fullname
            and cleaned_email == original_email
        ):
            _render_profile_no_changes_alert()
            return

        if not cleaned_fullname:
            st.error("Nama lengkap wajib diisi.")
            return
        if len(cleaned_fullname) < 2:
            st.error("Nama lengkap minimal 2 karakter.")
            return
        if not _validate_email(cleaned_email):
            st.error("Format email tidak valid. Contoh yang benar: nama@contoh.com")
            return

        with st.spinner("Menyimpan perubahan profil..."):
            success, message = update_profile(user_id, cleaned_fullname, cleaned_email)

        if not success:
            log_activity(
                "PROFILE_UPDATE",
                "Profil",
                "Perubahan profil gagal disimpan.",
                status="failed",
                metadata={"reason": message},
            )
            st.error(message)
            return

        log_activity(
            "PROFILE_UPDATE",
            "Profil",
            "Nama lengkap atau email profil berhasil diperbarui.",
            metadata={
                "fullname_changed": cleaned_fullname != original_fullname,
                "email_changed": cleaned_email != original_email,
            },
        )
        st.session_state["fullname"] = cleaned_fullname
        _set_flash(message or "Profil berhasil diperbarui.", "success")
        st.rerun()
    except Exception as error:
        st.error(f"Form edit profil belum dapat diproses: {error}")


def _reset_password_widget_state() -> None:
    """Kosongkan nilai widget password setelah password berhasil diubah."""
    try:
        if not st.session_state.pop("profile_v11_reset_password_fields", False):
            return
        st.session_state["profile_v11_old_password"] = ""
        st.session_state["profile_v11_new_password"] = ""
        st.session_state["profile_v11_confirm_password"] = ""
    except Exception as error:
        st.error(f"Kolom password belum dapat dikosongkan: {error}")


def _render_password_form(user_id: int) -> None:
    """Render section 3: form ubah password dengan indikator live di luar st.form."""
    try:
        _reset_password_widget_state()
        st.markdown(
            """
            <div class="profile-v11-password-hero">
                <div class="profile-v11-password-hero-inner">
                    <div class="profile-v11-password-icon">🔐</div>
                    <div>
                        <p class="profile-v11-password-eyebrow">Pengaturan Keamanan</p>
                        <h2 class="profile-v11-password-title">Ubah Password Akun</h2>
                        <p class="profile-v11-password-desc">
                            Perbarui password dashboard dengan validasi bertahap. Gunakan kombinasi yang mudah diingat,
                            tetapi tetap aman dan berbeda dari password lama.
                        </p>
                    </div>
                    <div class="profile-v11-password-chips">
                        <span class="profile-v11-password-chip"><span>🧬</span>bcrypt</span>
                        <span class="profile-v11-password-chip"><span>🛡️</span>Validasi</span>
                        <span class="profile-v11-password-chip"><span>⚡</span>Instan</span>
                    </div>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        st.markdown(
            """
            <div class="profile-v11-password-live-caption">
                <span>⚡</span>
                <span>Mode live aktif: indikator kekuatan berubah otomatis saat password baru diketik.</span>
            </div>
            """,
            unsafe_allow_html=True,
        )

        # Jangan memakai st.form untuk bagian ini. Di dalam st.form, nilai text_input baru
        # dikirim setelah tombol submit ditekan, sehingga indikator kekuatan tidak bisa berubah real-time.
        with st.container(border=True):
            st.markdown(
                """
                <div class="profile-v11-password-intro">
                    <div class="profile-v11-password-tip-card">
                        <div class="profile-v11-password-tip-icon">🔑</div>
                        <div>
                            <p class="profile-v11-password-tip-title">Password lama</p>
                            <p class="profile-v11-password-tip-text">Dipakai untuk memastikan perubahan dilakukan oleh pemilik akun.</p>
                        </div>
                    </div>
                    <div class="profile-v11-password-tip-card">
                        <div class="profile-v11-password-tip-icon">🧱</div>
                        <div>
                            <p class="profile-v11-password-tip-title">Minimal 6 karakter</p>
                            <p class="profile-v11-password-tip-text">Indikator kekuatan akan berubah otomatis saat password diketik.</p>
                        </div>
                    </div>
                    <div class="profile-v11-password-tip-card">
                        <div class="profile-v11-password-tip-icon">✅</div>
                        <div>
                            <p class="profile-v11-password-tip-title">Konfirmasi ulang</p>
                            <p class="profile-v11-password-tip-text">Password baru harus sama pada kolom konfirmasi sebelum disimpan.</p>
                        </div>
                    </div>
                </div>
                """,
                unsafe_allow_html=True,
            )

            old_password = st.text_input(
                "Password Lama",
                type="password",
                key="profile_v11_old_password",
                placeholder="Masukkan password saat ini",
            )
            new_col, confirm_col = st.columns([1, 1], gap="large")
            with new_col:
                new_password = st.text_input(
                    "Password Baru",
                    type="password",
                    key="profile_v11_new_password",
                    placeholder="Minimal 6 karakter",
                )
            with confirm_col:
                confirm_password = st.text_input(
                    "Konfirmasi Password Baru",
                    type="password",
                    key="profile_v11_confirm_password",
                    placeholder="Ketik ulang password baru",
                )

            _render_password_strength(new_password)
            _render_password_match_status(new_password, confirm_password)

            st.markdown(
                """
                <div class="profile-v11-password-submit-note">
                    <span>✨</span>
                    <div><strong>Tips keamanan:</strong> hindari password yang sama dengan akun lain dan jangan bagikan password kepada siapa pun.</div>
                </div>
                """,
                unsafe_allow_html=True,
            )
            submitted = st.button(
                "🛡️ Simpan Password Baru",
                type="primary",
                use_container_width=True,
                key="profile_v11_password_save_button",
            )

        if not submitted:
            return

        if not old_password:
            st.error("Password lama wajib diisi.")
            return
        if not new_password:
            st.error("Password baru wajib diisi.")
            return
        if len(new_password) < 6:
            st.error("Password baru minimal 6 karakter.")
            return
        if new_password != confirm_password:
            st.error("Konfirmasi password baru harus sama dengan password baru.")
            return
        if old_password == new_password:
            st.error("Password baru harus berbeda dari password lama.")
            return

        with st.spinner("Memverifikasi password lama dan menyimpan password baru..."):
            success, message = _update_password_minimum_six(
                user_id=user_id,
                old_password=old_password,
                new_password=new_password,
            )

        if not success:
            log_activity(
                "PASSWORD_CHANGE",
                "Profil",
                "Perubahan password akun gagal.",
                status="failed",
                metadata={"reason": message},
            )
            st.error(message)
            return

        log_activity(
            "PASSWORD_CHANGE",
            "Profil",
            "Password akun berhasil diperbarui.",
        )
        st.session_state["profile_v11_reset_password_fields"] = True
        _set_flash(message, "success")
        st.rerun()
    except Exception as error:
        st.error(f"Form ubah password belum dapat diproses: {error}")

def _render_danger_zone(user_id: int, user: dict[str, Any]) -> None:
    """Render section 5: zona berbahaya hapus akun dengan desain interaktif."""
    try:
        username = _safe_text(user.get("username"), "pengguna")
        safe_username = html.escape(username)
        is_main_admin = int(user_id) == 1

        # Penting: HTML harus di-dedent agar Streamlit tidak membacanya sebagai blok kode Markdown.
        danger_header_html = dedent("""
            <div class="profile-v11-danger-card">
                <div class="profile-v11-danger-inner">
                    <div class="profile-v11-danger-icon">⚠️</div>
                    <div>
                        <p class="profile-v11-danger-eyebrow">Kontrol Risiko Akun</p>
                        <h2 class="profile-v11-danger-title">Zona Berbahaya</h2>
                        <p class="profile-v11-danger-text">
                            Area ini dipakai untuk tindakan sensitif pada akun. Semua aksi dibuat jelas,
                            diberi konfirmasi, dan tidak dijalankan diam-diam agar akses dashboard tetap aman.
                        </p>
                    </div>
                    <div class="profile-v11-danger-chips">
                        <span class="profile-v11-danger-chip"><span>🚫</span>Permanen</span>
                        <span class="profile-v11-danger-chip"><span>🔐</span>Butuh konfirmasi</span>
                        <span class="profile-v11-danger-chip"><span>⚡</span>Logout otomatis</span>
                    </div>
                </div>
            </div>
            <div class="profile-v11-danger-panel">
                <div class="profile-v11-danger-step-grid">
                    <div class="profile-v11-danger-step-card">
                        <div class="profile-v11-danger-step-icon">🧨</div>
                        <div>
                            <p class="profile-v11-danger-step-title">Tidak bisa dibatalkan</p>
                            <p class="profile-v11-danger-step-text">Akun yang terhapus tidak dapat dipulihkan dari halaman profil.</p>
                        </div>
                    </div>
                    <div class="profile-v11-danger-step-card">
                        <div class="profile-v11-danger-step-icon">🚪</div>
                        <div>
                            <p class="profile-v11-danger-step-title">Logout otomatis</p>
                            <p class="profile-v11-danger-step-text">Sesi aktif akan dibersihkan setelah proses penghapusan berhasil.</p>
                        </div>
                    </div>
                    <div class="profile-v11-danger-step-card">
                        <div class="profile-v11-danger-step-icon">🛡️</div>
                        <div>
                            <p class="profile-v11-danger-step-title">Proteksi admin utama</p>
                            <p class="profile-v11-danger-step-text">Akun utama dashboard dilindungi agar akses sistem tidak hilang.</p>
                        </div>
                    </div>
                </div>
        """).strip()

        if is_main_admin:
            st.markdown(
                danger_header_html
                + dedent("""
                    <div class="profile-v11-admin-lock-card">
                        <div class="profile-v11-admin-lock-icon">🔒</div>
                        <div>
                            <p class="profile-v11-admin-lock-title">Admin utama terlindungi</p>
                            <p class="profile-v11-admin-lock-text">
                                Akun admin utama dengan <strong>user_id=1</strong> tidak dapat dihapus dari halaman profil.
                                Proteksi ini menjaga dashboard tetap punya akses administrator.
                            </p>
                        </div>
                        <span class="profile-v11-admin-lock-pill">🛡️ User ID #1 aman</span>
                    </div>
                </div>
                """).strip(),
                unsafe_allow_html=True,
            )
            return

        st.markdown(
            danger_header_html
            + dedent(f"""
                <div class="profile-v11-delete-confirm-card">
                    <div class="profile-v11-delete-confirm-icon">✍️</div>
                    <div>
                        <p class="profile-v11-delete-confirm-title">Konfirmasi diperlukan untuk @{safe_username}</p>
                        <p class="profile-v11-delete-confirm-text">
                            Centang persetujuan di bawah agar tombol hapus aktif. Periksa kembali sebelum melanjutkan.
                        </p>
                    </div>
                </div>
            </div>
            """).strip(),
            unsafe_allow_html=True,
        )

        confirm_delete = st.checkbox(
            "Saya paham bahwa tindakan ini tidak dapat dibatalkan.",
            key="profile_v11_confirm_delete_checkbox",
        )
        delete_clicked = st.button(
            "🗑️ Hapus Akun Permanen",
            type="secondary",
            use_container_width=True,
            disabled=not confirm_delete,
            key="profile_v11_delete_account_button",
        )

        if not delete_clicked:
            return

        with st.spinner("Menghapus akun dan membersihkan sesi..."):
            revoke_all_remember_tokens(user_id)
            success, message = delete_user(user_id)

        if not success:
            log_activity(
                "SELF_DELETE_ACCOUNT",
                "Profil",
                "Penghapusan akun sendiri gagal.",
                status="failed",
                metadata={"reason": message},
            )
            st.error(message)
            return

        log_activity(
            "SELF_DELETE_ACCOUNT",
            "Profil",
            "Pengguna menghapus akun sendiri secara permanen.",
            metadata={"deleted_user_id": user_id, "deleted_username": username},
        )
        st.success("Akun berhasil dihapus. Anda akan diarahkan ke halaman login.")
        _logout_after_delete(user_id)
    except Exception as error:
        st.error(f"Zona berbahaya belum dapat diproses: {error}")


# -----------------------------------------------------------------------------
# Entry point halaman profil
# -----------------------------------------------------------------------------


def render_profile() -> None:
    """Render halaman profil pengguna dengan desain yang mengikuti tema global dashboard."""
    loading_handle = None
    upload_event_id, upload_pending, upload_loading_label = _status_loading_upload_foto()
    try:
        if upload_pending:
            loading_handle = mulai_loading_aksi(upload_loading_label)

        render_page_header(
            "👤 Profil Pengguna",
            "Kelola identitas akun, keamanan password, dan pengaturan akun dashboard.",
        )
        _inject_profile_css()
        _render_flash()

        user_id = st.session_state.get("user_id")
        if not user_id:
            st.error("Sesi pengguna tidak valid. Silakan logout lalu login kembali.")
            return

        user = get_user_by_id(int(user_id))
        if user is None:
            st.error("Data pengguna tidak ditemukan di database. Silakan login ulang.")
            return

        profile_theme_class = (
            "profile-v11-theme-dark"
            if bool(st.session_state.get("dark_mode", False))
            else "profile-v11-theme-light"
        )
        st.markdown(
            f'<div class="profile-v11-wrapper {profile_theme_class}">',
            unsafe_allow_html=True,
        )

        left_column, right_column = st.columns([0.92, 1.58], gap="large")
        with left_column:
            _render_profile_card(user)

        with right_column:
            _render_usage_statistics(int(user_id), user)

        # Section foto profil dibuat full-width agar melebar ke kanan dan tidak terlalu panjang ke bawah.
        st.markdown('<div class="profile-v11-section-gap"></div>', unsafe_allow_html=True)
        _render_optional_avatar_upload(int(user_id), user)

        _render_edit_profile_form(int(user_id), user)
        _render_password_form(int(user_id))
        _render_danger_zone(int(user_id), user)

        st.markdown("</div>", unsafe_allow_html=True)
    except Exception as error:
        st.error(f"Terjadi kesalahan pada halaman profil: {error}")
    finally:
        if loading_handle is not None:
            selesaikan_loading_aksi(loading_handle)
        completed_id = int(st.session_state.get(STATE_AVATAR_UPLOAD_COMPLETED_ID, 0))
        if upload_event_id > completed_id:
            st.session_state[STATE_AVATAR_UPLOAD_COMPLETED_ID] = upload_event_id
