"""Halaman login pengguna Dashboard Analisis Telkom Group."""

import json
import logging

from datetime import datetime, timedelta

import extra_streamlit_components as stx
import streamlit as st
import streamlit.components.v1 as components

LOGGER = logging.getLogger(__name__)

from auth.auth_utils import (
    REMEMBER_ME_HOURS,
    create_remember_token,
    get_user,
    revoke_remember_token,
    validate_remember_token,
    verify_password,
)
from utils.access_control import DEFAULT_ROLE, normalize_role
from utils.app_version import get_auth_footer_text
from utils.loading_screen import _buat_html_loading
from utils.audit_logger import log_activity

REMEMBER_COOKIE_KEY = "remember_token"
COOKIE_MANAGER_SESSION_KEY = "_remember_cookie_manager_v2"
COOKIE_BOOTSTRAP_PASS_KEY = "_remember_cookie_bootstrap_pass_v2"
# Dipertahankan untuk kompatibilitas blok logout lama. Pemulihan sesi startup
# sekarang memakai satu bootstrap alami dari komponen cookie, bukan polling cepat.
MAX_COOKIE_POLLS = 4
MAX_COOKIE_SAVE_ATTEMPTS = 5

LOGIN_TRANSITION_ACTIVE_KEY = "_login_transition_active_v1"
LOGIN_TRANSITION_DONE_KEY = "_login_just_completed_v1"
LOGIN_SUBMISSION_LOCK_KEY = "_login_submission_lock_v2"
POST_LOGOUT_RESTORE_GUARD_KEY = "_post_logout_restore_guard_v1"
LOGIN_OVERLAY_ID = "login-transition-client-v1"
LOGIN_OVERLAY_STYLE_ID = "login-transition-client-style-v1"


def _inject_login_css() -> None:
    """Terapkan halaman putih dengan form login hitam yang terpusat."""
    st.markdown(
        """
        <style>
        @import url('https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;600;700;800&display=swap');

        :root {
            --auth-page: #0D0D0D;
            --auth-page-soft: #111111;
            --auth-card: #111111;
            --auth-card-bottom: #0B0B0B;
            --auth-input: #232323;
            --auth-border: #343434;
            --auth-red: #E53935;
            --auth-red-hover: #FF5252;
            --auth-text: #FFFFFF;
            --auth-muted: #AAAAAA;
            --auth-placeholder: #929292;
        }

        html,
        body,
        .stApp,
        [data-testid="stAppViewContainer"],
        [data-testid="stMain"] {
            min-height: 100vh !important;
            height: auto !important;
            overflow-x: hidden !important;
            overflow-y: auto !important;
            background: linear-gradient(180deg, var(--auth-page) 0%, var(--auth-page-soft) 100%) !important;
            font-family: 'DM Sans', sans-serif !important;
        }

        /*
         * Jangan memaksa font ke seluruh elemen dengan selector `body *`.
         * Streamlit memakai font/simbol khusus untuk beberapa ikon internal.
         * Font DM Sans tetap diwariskan dari body, sedangkan ikon dibiarkan
         * menggunakan renderer bawaannya.
         */
        body,
        input,
        textarea,
        select,
        label {
            font-family: 'DM Sans', sans-serif;
        }

        /* Dukungan untuk Streamlit versi yang merender ikon sebagai Material Symbols. */
        [data-testid="stIconMaterial"],
        .material-symbols-rounded,
        .material-symbols-outlined,
        [class*="material-symbols"] {
            font-family: 'Material Symbols Rounded', 'Material Symbols Outlined' !important;
            font-weight: normal !important;
            font-style: normal !important;
            font-size: 20px !important;
            line-height: 1 !important;
            letter-spacing: normal !important;
            text-transform: none !important;
            white-space: nowrap !important;
            word-wrap: normal !important;
            direction: ltr !important;
            -webkit-font-feature-settings: 'liga' !important;
            -webkit-font-smoothing: antialiased !important;
            font-feature-settings: 'liga' !important;
        }


        /* Scrollbar halaman autentikasi berwarna merah Telkom. */
        html,
        body,
        [data-testid="stAppViewContainer"],
        [data-testid="stMain"] {
            scrollbar-width: thin !important;
            scrollbar-color: var(--auth-red) #111111 !important;
        }

        html::-webkit-scrollbar,
        body::-webkit-scrollbar,
        [data-testid="stAppViewContainer"]::-webkit-scrollbar,
        [data-testid="stMain"]::-webkit-scrollbar {
            width: 12px !important;
            height: 12px !important;
        }

        html::-webkit-scrollbar-track,
        body::-webkit-scrollbar-track,
        [data-testid="stAppViewContainer"]::-webkit-scrollbar-track,
        [data-testid="stMain"]::-webkit-scrollbar-track {
            background: #111111 !important;
        }

        html::-webkit-scrollbar-thumb,
        body::-webkit-scrollbar-thumb,
        [data-testid="stAppViewContainer"]::-webkit-scrollbar-thumb,
        [data-testid="stMain"]::-webkit-scrollbar-thumb {
            min-height: 48px !important;
            background: linear-gradient(180deg, var(--auth-red-hover) 0%, var(--auth-red) 100%) !important;
            border: 3px solid #111111 !important;
            border-radius: 999px !important;
        }

        html::-webkit-scrollbar-thumb:hover,
        body::-webkit-scrollbar-thumb:hover,
        [data-testid="stAppViewContainer"]::-webkit-scrollbar-thumb:hover,
        [data-testid="stMain"]::-webkit-scrollbar-thumb:hover {
            background: var(--auth-red-hover) !important;
        }

        #MainMenu,
        footer,
        header,
        [data-testid="stHeader"],
        [data-testid="stToolbar"],
        [data-testid="stDecoration"],
        [data-testid="stStatusWidget"],
        section[data-testid="stSidebar"],
        [data-testid="collapsedControl"] {
            display: none !important;
            visibility: hidden !important;
        }

        [data-testid="stAppViewContainer"] > .main,
        [data-testid="stMain"] {
            width: 100% !important;
            max-width: 100% !important;
            margin: 0 !important;
        }

        .block-container,
        [data-testid="stMainBlockContainer"] {
            width: 100% !important;
            max-width: 1180px !important;
            min-height: 100vh !important;
            margin: 0 auto !important;
            padding: 48px 20px !important;
            display: flex !important;
            flex-direction: column !important;
            justify-content: center !important;
            background: transparent !important;
            overflow: visible !important;
        }

        div[data-testid="stHorizontalBlock"] {
            width: 100% !important;
            align-items: center !important;
            justify-content: center !important;
        }

        /*
         * Card memakai elemen Form bawaan Streamlit 1.35.
         * data-testid="stForm" stabil dan tidak bergantung pada wrapper container.
         */
        body [data-testid="stAppViewContainer"] div[data-testid="stForm"] {
            width: 100% !important;
            max-width: 660px !important;
            margin: 0 auto !important;
            padding: 40px 46px 30px !important;
            background: linear-gradient(180deg, var(--auth-card) 0%, var(--auth-card-bottom) 100%) !important;
            background-color: var(--auth-card) !important;
            border: 1px solid rgba(229, 57, 53, 0.88) !important;
            border-radius: 22px !important;
            box-shadow:
                0 22px 60px rgba(0, 0, 0, 0.18),
                0 0 0 1px rgba(229, 57, 53, 0.08),
                0 0 28px rgba(229, 57, 53, 0.10) !important;
            overflow: visible !important;
            color: var(--auth-text) !important;
        }

        body [data-testid="stAppViewContainer"] div[data-testid="stForm"] > div,
        body [data-testid="stAppViewContainer"] div[data-testid="stForm"] > div > div,
        body [data-testid="stAppViewContainer"] div[data-testid="stForm"] div[data-testid="stVerticalBlock"] {
            background: transparent !important;
            background-color: transparent !important;
        }

        .auth-header {
            margin: 0 0 24px !important;
            text-align: center !important;
        }

        .auth-icon-wrap {
            width: 66px;
            height: 66px;
            display: flex;
            align-items: center;
            justify-content: center;
            margin: 0 auto 17px;
            border: 1px solid rgba(229, 57, 53, 0.75);
            border-radius: 18px;
            background: rgba(229, 57, 53, 0.10);
            box-shadow: 0 0 24px rgba(229, 57, 53, 0.16);
        }

        .auth-icon {
            font-size: 31px;
            line-height: 1;
        }

        .auth-title {
            margin: 0 !important;
            color: var(--auth-text) !important;
            -webkit-text-fill-color: var(--auth-text) !important;
            font-size: 29px !important;
            font-weight: 800 !important;
            line-height: 1.18 !important;
            letter-spacing: -0.035em !important;
        }

        .auth-subtitle {
            margin: 9px 0 0 !important;
            color: var(--auth-muted) !important;
            -webkit-text-fill-color: var(--auth-muted) !important;
            font-size: 14px !important;
            font-weight: 400 !important;
            line-height: 1.55 !important;
        }

        body [data-testid="stAppViewContainer"] div[data-testid="stForm"] div[data-testid="stTextInput"] {
            width: 100% !important;
            margin-bottom: 8px !important;
        }

        body [data-testid="stAppViewContainer"] div[data-testid="stForm"] div[data-testid="stTextInput"] label,
        body [data-testid="stAppViewContainer"] div[data-testid="stForm"] div[data-testid="stTextInput"] label p,
        body [data-testid="stAppViewContainer"] div[data-testid="stForm"] div[data-testid="stCheckbox"] label,
        body [data-testid="stAppViewContainer"] div[data-testid="stForm"] div[data-testid="stCheckbox"] label p {
            color: var(--auth-text) !important;
            -webkit-text-fill-color: var(--auth-text) !important;
            font-size: 13px !important;
            font-weight: 700 !important;
        }

        /* Kotak input utama. Hanya wrapper terluar yang memiliki border dan background. */
        body [data-testid="stAppViewContainer"] div[data-testid="stForm"] div[data-testid="stTextInput"] div[data-baseweb="input"] {
            width: 100% !important;
            min-height: 50px !important;
            height: 50px !important;
            display: flex !important;
            align-items: center !important;
            position: relative !important;
            overflow: hidden !important;
            background: var(--auth-input) !important;
            background-color: var(--auth-input) !important;
            border: 1px solid var(--auth-border) !important;
            border-radius: 11px !important;
            box-shadow: none !important;
            color-scheme: dark !important;
        }

        /* Wrapper internal tetap utuh agar input dapat diketik, tetapi tidak membuat kotak kedua. */
        body [data-testid="stAppViewContainer"] div[data-testid="stForm"] div[data-testid="stTextInput"] div[data-baseweb="base-input"] {
            width: auto !important;
            min-width: 0 !important;
            height: 100% !important;
            min-height: 100% !important;
            flex: 1 1 auto !important;
            display: flex !important;
            align-items: center !important;
            position: static !important;
            overflow: visible !important;
            background: transparent !important;
            background-color: transparent !important;
            border: 0 !important;
            border-radius: 0 !important;
            box-shadow: none !important;
        }

        /* Area suffix password ikut tinggi input agar tombol mata selalu tepat di tengah. */
        body [data-testid="stAppViewContainer"] div[data-testid="stForm"] div[data-testid="stTextInput"] div[data-baseweb="input"] > div:not([data-baseweb="base-input"]) {
            height: 100% !important;
            min-height: 100% !important;
            flex: 0 0 48px !important;
            display: flex !important;
            align-items: center !important;
            justify-content: center !important;
            margin: 0 !important;
            padding: 0 !important;
            position: static !important;
        }

        body [data-testid="stAppViewContainer"] div[data-testid="stForm"] div[data-testid="stTextInput"] div[data-baseweb="input"]:focus-within {
            border-color: var(--auth-red) !important;
            box-shadow: 0 0 0 3px rgba(229, 57, 53, 0.16) !important;
        }

        body [data-testid="stAppViewContainer"] div[data-testid="stForm"] div[data-testid="stTextInput"] input,
        body [data-testid="stAppViewContainer"] div[data-testid="stForm"] div[data-testid="stTextInput"] input:focus,
        body [data-testid="stAppViewContainer"] div[data-testid="stForm"] div[data-testid="stTextInput"] input:active {
            width: 100% !important;
            height: 48px !important;
            min-height: 48px !important;
            margin: 0 !important;
            padding: 0 14px !important;
            background: transparent !important;
            background-color: transparent !important;
            border: 0 !important;
            border-radius: 0 !important;
            outline: 0 !important;
            box-shadow: none !important;
            color: #F4F4F4 !important;
            -webkit-text-fill-color: #F4F4F4 !important;
            caret-color: var(--auth-red) !important;
            font-size: 14px !important;
            font-weight: 500 !important;
            line-height: normal !important;
            color-scheme: dark !important;
        }

        body [data-testid="stAppViewContainer"] div[data-testid="stForm"] div[data-testid="stTextInput"] input::placeholder {
            color: var(--auth-placeholder) !important;
            -webkit-text-fill-color: var(--auth-placeholder) !important;
            opacity: 1 !important;
        }

        body [data-testid="stAppViewContainer"] div[data-testid="stForm"] div[data-testid="stTextInput"] input:-webkit-autofill,
        body [data-testid="stAppViewContainer"] div[data-testid="stForm"] div[data-testid="stTextInput"] input:-webkit-autofill:hover,
        body [data-testid="stAppViewContainer"] div[data-testid="stForm"] div[data-testid="stTextInput"] input:-webkit-autofill:focus,
        body [data-testid="stAppViewContainer"] div[data-testid="stForm"] div[data-testid="stTextInput"] input:-webkit-autofill:active {
            -webkit-box-shadow: 0 0 0 1000px var(--auth-input) inset !important;
            box-shadow: 0 0 0 1000px var(--auth-input) inset !important;
            -webkit-text-fill-color: #F4F4F4 !important;
            caret-color: var(--auth-red) !important;
            transition: background-color 9999s ease-out 0s !important;
        }

        /*
         * Posisi tombol mata mengikuti flexbox milik kotak input, bukan absolute
         * terhadap keseluruhan widget yang juga mencakup label. Dengan begitu
         * pusat ikon selalu sejajar dengan pusat area input 50 px.
         */
        body [data-testid="stAppViewContainer"] div[data-testid="stForm"] div[data-testid="stTextInput"] button {
            position: static !important;
            inset: auto !important;
            top: auto !important;
            right: auto !important;
            bottom: auto !important;
            left: auto !important;
            z-index: 10 !important;
            flex: 0 0 40px !important;
            align-self: center !important;
            width: 40px !important;
            min-width: 40px !important;
            height: 40px !important;
            min-height: 40px !important;
            margin: 0 4px 0 0 !important;
            padding: 0 !important;
            display: flex !important;
            align-items: center !important;
            justify-content: center !important;
            background: transparent !important;
            border: 0 !important;
            border-radius: 8px !important;
            box-shadow: none !important;
            color: #A8A8A8 !important;
            line-height: 1 !important;
            transform: none !important;
            pointer-events: auto !important;
        }

        body [data-testid="stAppViewContainer"] div[data-testid="stForm"] div[data-testid="stTextInput"] button > div,
        body [data-testid="stAppViewContainer"] div[data-testid="stForm"] div[data-testid="stTextInput"] button > span {
            width: 100% !important;
            height: 100% !important;
            display: flex !important;
            align-items: center !important;
            justify-content: center !important;
            margin: 0 !important;
            padding: 0 !important;
            line-height: 1 !important;
        }

        body [data-testid="stAppViewContainer"] div[data-testid="stForm"] div[data-testid="stTextInput"] button svg {
            display: block !important;
            width: 20px !important;
            height: 20px !important;
            margin: 0 !important;
            padding: 0 !important;
            transform: none !important;
        }


        /*
         * FIX FINAL IKON PASSWORD:
         * Tidak bergantung pada font Material Symbols. Isi bawaan tombol
         * (SVG maupun teks "visibility") disembunyikan, lalu ikon mata
         * digambar memakai SVG inline. Ini kompatibel dengan Streamlit lama
         * maupun baru dan tetap mempertahankan fungsi klik tampil/sembunyi.
         */
        body [data-testid="stAppViewContainer"] div[data-testid="stForm"] div[data-testid="stTextInput"] button[aria-label*="password" i],
        body [data-testid="stAppViewContainer"] div[data-testid="stForm"] div[data-testid="stTextInput"] button[title*="password" i] {
            font-size: 0 !important;
            color: transparent !important;
            -webkit-text-fill-color: transparent !important;
        }

        body [data-testid="stAppViewContainer"] div[data-testid="stForm"] div[data-testid="stTextInput"] button[aria-label*="password" i] > *,
        body [data-testid="stAppViewContainer"] div[data-testid="stForm"] div[data-testid="stTextInput"] button[title*="password" i] > * {
            display: none !important;
            visibility: hidden !important;
            opacity: 0 !important;
        }

        body [data-testid="stAppViewContainer"] div[data-testid="stForm"] div[data-testid="stTextInput"] button[aria-label^="Show password" i]::before,
        body [data-testid="stAppViewContainer"] div[data-testid="stForm"] div[data-testid="stTextInput"] button[title^="Show password" i]::before {
            content: "" !important;
            display: block !important;
            width: 21px !important;
            height: 21px !important;
            background-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='none' stroke='%23A8A8A8' stroke-width='2' stroke-linecap='round' stroke-linejoin='round'%3E%3Cpath d='M2 12s3.5-7 10-7 10 7 10 7-3.5 7-10 7S2 12 2 12Z'/%3E%3Ccircle cx='12' cy='12' r='3'/%3E%3C/svg%3E") !important;
            background-repeat: no-repeat !important;
            background-position: center !important;
            background-size: contain !important;
        }

        body [data-testid="stAppViewContainer"] div[data-testid="stForm"] div[data-testid="stTextInput"] button[aria-label^="Hide password" i]::before,
        body [data-testid="stAppViewContainer"] div[data-testid="stForm"] div[data-testid="stTextInput"] button[title^="Hide password" i]::before {
            content: "" !important;
            display: block !important;
            width: 21px !important;
            height: 21px !important;
            background-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='none' stroke='%23A8A8A8' stroke-width='2' stroke-linecap='round' stroke-linejoin='round'%3E%3Cpath d='M3 3l18 18'/%3E%3Cpath d='M10.6 5.1A10.8 10.8 0 0 1 12 5c6.5 0 10 7 10 7a17.7 17.7 0 0 1-2.1 3.1'/%3E%3Cpath d='M6.2 6.2C3.5 8.1 2 12 2 12s3.5 7 10 7a10.7 10.7 0 0 0 5.8-1.7'/%3E%3Cpath d='M9.9 9.9a3 3 0 0 0 4.2 4.2'/%3E%3C/svg%3E") !important;
            background-repeat: no-repeat !important;
            background-position: center !important;
            background-size: contain !important;
        }

        body [data-testid="stAppViewContainer"] div[data-testid="stForm"] div[data-testid="stTextInput"] button:hover {
            color: #FFFFFF !important;
            background: rgba(255, 255, 255, 0.04) !important;
            transform: none !important;
        }

        body [data-testid="stAppViewContainer"] div[data-testid="stForm"] div[data-testid="stCheckbox"] {
            margin: 1px 0 4px !important;
        }

        body [data-testid="stAppViewContainer"] div[data-testid="stForm"] div[data-testid="stCheckbox"] label p {
            color: #D0D0D0 !important;
            -webkit-text-fill-color: #D0D0D0 !important;
            font-weight: 600 !important;
        }

        /*
         * Hotfix V2.4: hanya elemen terluar tooltip yang menggambar ikon bantuan.
         * Versi sebelumnya memberi pseudo-element pada beberapa elemen bertingkat,
         * sehingga tanda tanya tampil lebih dari satu saat diarahkan kursor.
         */
        body [data-testid="stAppViewContainer"] div[data-testid="stForm"] div[data-testid="stCheckbox"] [data-testid="stTooltipHoverTarget"]::before,
        body [data-testid="stAppViewContainer"] div[data-testid="stForm"] div[data-testid="stCheckbox"] button[aria-label="Help"]::before {
            content: none !important;
            display: none !important;
        }

        body [data-testid="stAppViewContainer"] div[data-testid="stForm"] div[data-testid="stCheckbox"] [data-testid="stTooltipIcon"] {
            width: 20px !important;
            min-width: 20px !important;
            height: 20px !important;
            min-height: 20px !important;
            margin-left: 7px !important;
            padding: 0 !important;
            display: inline-flex !important;
            align-items: center !important;
            justify-content: center !important;
            position: relative !important;
            overflow: visible !important;
            color: #111111 !important;
            -webkit-text-fill-color: #111111 !important;
            background: #F2F2F2 !important;
            border: 1.5px solid #FFFFFF !important;
            border-radius: 50% !important;
            box-shadow: 0 0 0 2px rgba(229, 57, 53, 0.18) !important;
            opacity: 1 !important;
            line-height: 1 !important;
            cursor: help !important;
        }

        /* Elemen bawaan tetap aktif sebagai pemicu tooltip, tetapi tidak menggambar ikon kedua. */
        body [data-testid="stAppViewContainer"] div[data-testid="stForm"] div[data-testid="stCheckbox"] [data-testid="stTooltipIcon"] [data-testid="stTooltipHoverTarget"],
        body [data-testid="stAppViewContainer"] div[data-testid="stForm"] div[data-testid="stCheckbox"] [data-testid="stTooltipIcon"] button[aria-label="Help"] {
            position: absolute !important;
            inset: 0 !important;
            width: 100% !important;
            min-width: 0 !important;
            height: 100% !important;
            min-height: 0 !important;
            margin: 0 !important;
            padding: 0 !important;
            background: transparent !important;
            border: 0 !important;
            border-radius: 50% !important;
            box-shadow: none !important;
            color: transparent !important;
            -webkit-text-fill-color: transparent !important;
            overflow: hidden !important;
        }

        body [data-testid="stAppViewContainer"] div[data-testid="stForm"] div[data-testid="stCheckbox"] [data-testid="stTooltipIcon"] svg,
        body [data-testid="stAppViewContainer"] div[data-testid="stForm"] div[data-testid="stCheckbox"] [data-testid="stTooltipIcon"] [class*="material"] {
            display: none !important;
            visibility: hidden !important;
        }

        body [data-testid="stAppViewContainer"] div[data-testid="stForm"] div[data-testid="stCheckbox"] [data-testid="stTooltipIcon"]::before {
            content: "?" !important;
            display: block !important;
            color: #111111 !important;
            -webkit-text-fill-color: #111111 !important;
            font-family: 'DM Sans', sans-serif !important;
            font-size: 12px !important;
            font-weight: 800 !important;
            line-height: 1 !important;
            text-align: center !important;
            transform: translateY(-0.2px) !important;
        }

        body [data-testid="stAppViewContainer"] div[data-testid="stForm"] div[data-testid="stCheckbox"] [data-testid="stTooltipIcon"]:hover {
            color: #FFFFFF !important;
            -webkit-text-fill-color: #FFFFFF !important;
            background: var(--auth-red-hover) !important;
            border-color: var(--auth-red-hover) !important;
            box-shadow: 0 0 0 3px rgba(255, 82, 82, 0.20) !important;
        }

        body [data-testid="stAppViewContainer"] div[data-testid="stForm"] div[data-testid="stCheckbox"] [data-testid="stTooltipIcon"]:hover::before {
            color: #FFFFFF !important;
            -webkit-text-fill-color: #FFFFFF !important;
        }

        /* Tooltip harus terbaca pada tema gelap dan tidak ikut mewarisi warna putih-putih. */
        div[data-baseweb="tooltip"],
        div[role="tooltip"] {
            max-width: 320px !important;
            padding: 10px 12px !important;
            background: #242424 !important;
            background-color: #242424 !important;
            border: 1px solid #3A3A3A !important;
            border-radius: 8px !important;
            box-shadow: 0 10px 30px rgba(0, 0, 0, 0.38) !important;
            color: #FFFFFF !important;
            -webkit-text-fill-color: #FFFFFF !important;
            opacity: 1 !important;
        }

        div[data-baseweb="tooltip"] *,
        div[role="tooltip"] * {
            color: #FFFFFF !important;
            -webkit-text-fill-color: #FFFFFF !important;
            background: transparent !important;
            font-family: 'DM Sans', sans-serif !important;
            font-size: 12px !important;
            line-height: 1.45 !important;
        }

        body [data-testid="stAppViewContainer"] div[data-testid="stForm"] div[data-testid="stFormSubmitButton"] > button {
            width: 100% !important;
            min-height: 48px !important;
            margin-top: 7px !important;
            padding: 11px 18px !important;
            background: var(--auth-red) !important;
            border: 1px solid var(--auth-red) !important;
            border-radius: 10px !important;
            box-shadow: 0 10px 24px rgba(229, 57, 53, 0.23) !important;
            color: #FFFFFF !important;
            -webkit-text-fill-color: #FFFFFF !important;
            font-size: 15px !important;
            font-weight: 700 !important;
        }

        body [data-testid="stAppViewContainer"] div[data-testid="stForm"] div[data-testid="stFormSubmitButton"] > button p,
        body [data-testid="stAppViewContainer"] div[data-testid="stForm"] div[data-testid="stFormSubmitButton"] > button span {
            color: #FFFFFF !important;
            -webkit-text-fill-color: #FFFFFF !important;
        }

        body [data-testid="stAppViewContainer"] div[data-testid="stForm"] div[data-testid="stFormSubmitButton"] > button:hover {
            background: var(--auth-red-hover) !important;
            border-color: var(--auth-red-hover) !important;
            color: #FFFFFF !important;
            transform: translateY(-1px) !important;
            box-shadow: 0 13px 28px rgba(229, 57, 53, 0.28) !important;
        }

        /*
         * Pesan validasi/login ditempatkan sebelum card form. Lebarnya dibuat
         * sama dengan card agar langsung terlihat tanpa perlu scroll.
         */
        body [data-testid="stAppViewContainer"] div[data-testid="stAlert"] {
            width: 100% !important;
            max-width: 660px !important;
            margin: 0 auto 16px !important;
            box-sizing: border-box !important;
            border-radius: 12px !important;
        }

        body [data-testid="stAppViewContainer"] div[data-testid="stAlert"] > div {
            width: 100% !important;
            box-sizing: border-box !important;
        }

        .auth-divider {
            width: 100%;
            height: 1px;
            margin: 22px 0 16px;
            background: rgba(255, 255, 255, 0.09);
        }

        .auth-helper-text {
            margin: 0 0 8px !important;
            text-align: center !important;
            color: #BDBDBD !important;
            -webkit-text-fill-color: #BDBDBD !important;
            font-size: 13px !important;
            font-weight: 600 !important;
            line-height: 1.45 !important;
        }

        body [data-testid="stAppViewContainer"] div[data-testid="stForm"] div[data-testid="stCaptionContainer"] p {
            margin-top: 13px !important;
            color: #777777 !important;
            -webkit-text-fill-color: #777777 !important;
            text-align: center !important;
            font-size: 0.75rem /* FIX: minimum 12px agar terbaca di tablet */ !important;
            line-height: 1.5 !important;
        }


        .stage2-footer {
            display: block !important;
            visibility: visible !important;
            width: min(660px, calc(100vw - 40px)) !important;
            max-width: 660px !important;
            margin: 24px auto 0 !important;
            padding: 15px 12px 6px !important;
            color: #777777 !important;
            -webkit-text-fill-color: #777777 !important;
            text-align: center !important;
            font-size: 12px !important;
            line-height: 1.5 !important;
            border-top: 1px solid rgba(229, 57, 53, 0.24) !important;
            background: transparent !important;
        }

        /* Pada layar laptop yang lebih pendek, card dimulai dari atas dan tetap dapat digulir utuh. */
        @media (max-height: 1000px) and (min-width: 761px) {
            .block-container,
            [data-testid="stMainBlockContainer"] {
                padding-top: 42px !important;
                padding-bottom: 32px !important;
                justify-content: flex-start !important;
            }

            body [data-testid="stAppViewContainer"] div[data-testid="stForm"] {
                padding-top: 32px !important;
                padding-bottom: 26px !important;
            }

            .auth-header {
                margin-bottom: 20px !important;
            }

            .auth-icon-wrap {
                width: 58px !important;
                height: 58px !important;
                margin-bottom: 13px !important;
            }

            .auth-icon {
                font-size: 28px !important;
            }

            .auth-title {
                font-size: 27px !important;
            }
        }

        @media (max-width: 760px) {
            .block-container,
            [data-testid="stMainBlockContainer"] {
                min-height: 100vh !important;
                padding: 18px 12px 28px !important;
                display: block !important;
            }

            body [data-testid="stAppViewContainer"] div[data-testid="stForm"] {
                width: 100% !important;
                max-width: 660px !important;
                padding: 28px 20px 22px !important;
                border-radius: 18px !important;
            }

            .auth-title {
                font-size: 25px !important;
            }

            .stage2-footer {
                width: calc(100vw - 24px) !important;
                margin-top: 18px !important;
                font-size: 0.75rem /* FIX: minimum 12px agar terbaca di tablet */ !important;
            }
        }
        </style>
        """,
        unsafe_allow_html=True,
    )



def _login_transition_html() -> str:
    """Bangun overlay login menggunakan desain loading global dashboard."""
    return _buat_html_loading(
        "Memverifikasi Akses",
        (
            "Memeriksa username dan password",
            "Memvalidasi keamanan akun",
            "Menyiapkan sesi pengguna",
            "Membuka halaman Beranda",
        ),
    )


def _install_login_click_overlay() -> None:
    """Pasang overlay sebelum submit agar form tidak berkedip saat rerun."""
    try:
        overlay_json = json.dumps(_login_transition_html())
        components.html(
            f"""
            <!doctype html>
            <html>
            <body>
            <script>
                (() => {{
                    const parentDocument = window.parent.document;
                    const overlayId = {json.dumps(LOGIN_OVERLAY_ID)};
                    const styleId = {json.dumps(LOGIN_OVERLAY_STYLE_ID)};
                    const overlayMarkup = {overlay_json};

                    const hasCompleteCredentials = (form) => {{
                        if (!form) return false;
                        const inputs = Array.from(form.querySelectorAll('input'));
                        const username = inputs.find((input) => input.type === 'text');
                        const password = inputs.find((input) => input.type === 'password');
                        return Boolean(
                            username && password &&
                            username.value.trim().length > 0 &&
                            password.value.length > 0
                        );
                    }};

                    const mountOverlay = () => {{
                        // Bersihkan overlay sisa dari percobaan sebelumnya. Pada versi lama,
                        // holder dapat tetap berada di DOM setelah animasi safety selesai.
                        const oldOverlay = parentDocument.getElementById(overlayId);
                        const oldStyle = parentDocument.getElementById(styleId);
                        if (oldOverlay) oldOverlay.remove();
                        if (oldStyle) oldStyle.remove();

                        const holder = parentDocument.createElement('div');
                        holder.id = overlayId;
                        holder.innerHTML = overlayMarkup;
                        parentDocument.body.appendChild(holder);

                        const overlay = holder.querySelector('.telkom-loading-overlay');
                        if (overlay) {{
                            // Tampilkan penuh sejak pointerdown. Fade-in singkat sebelumnya
                            // masih memberi kesempatan form/layar kosong terlihat saat rerun.
                            overlay.style.opacity = '1';
                            overlay.style.visibility = 'visible';
                            overlay.style.pointerEvents = 'auto';
                        }}

                        const safetyStyle = parentDocument.createElement('style');
                        safetyStyle.id = styleId;
                        safetyStyle.textContent = `
                            #${{overlayId}} {{ position: relative; z-index: 2147483647; }}
                            @keyframes login-overlay-safety-hide-v1 {{
                                to {{ opacity: 0; visibility: hidden; pointer-events: none; }}
                            }}
                            #${{overlayId}} > .telkom-loading-overlay {{
                                animation: login-overlay-safety-hide-v1 .25s ease 15s forwards;
                            }}
                        `;
                        parentDocument.head.appendChild(safetyStyle);
                    }};

                    const bindLoginButton = () => {{
                        const forms = Array.from(
                            parentDocument.querySelectorAll('[data-testid="stForm"]')
                        );
                        for (const form of forms) {{
                            const buttons = Array.from(form.querySelectorAll('button'));
                            const loginButton = buttons.find((button) =>
                                (button.innerText || '').toLowerCase().includes('masuk')
                            );
                            if (!loginButton || loginButton.dataset.loginOverlayV2 === '1') continue;

                            loginButton.dataset.loginOverlayV2 = '1';
                            let submitStarted = false;
                            const scheduleOverlay = () => {{
                                if (submitStarted || !hasCompleteCredentials(form)) return;
                                submitStarted = true;

                                // Jangan memasang overlay pada pointerdown. Overlay full-screen
                                // dapat mengambil pointer sebelum event click mencapai tombol,
                                // sehingga klik pertama hanya menampilkan loading tetapi form
                                // tidak pernah tersubmit. Timer 0 memberi browser kesempatan
                                // menyelesaikan click/submit terlebih dahulu, lalu overlay muncul.
                                window.setTimeout(mountOverlay, 0);
                            }};

                            // Klik tombol dan Enter tetap memakai jalur yang sama. Tidak ada
                            // preventDefault/stopPropagation sehingga submit Streamlit diteruskan.
                            loginButton.addEventListener('click', scheduleOverlay, true);
                            form.addEventListener('submit', scheduleOverlay, true);
                            form.addEventListener('keydown', (event) => {{
                                const target = event.target;
                                const isCredentialInput = target && (
                                    target.type === 'text' || target.type === 'password'
                                );
                                if (
                                    event.key === 'Enter' && !event.repeat &&
                                    !event.shiftKey && !event.ctrlKey && !event.altKey &&
                                    isCredentialInput
                                ) {{
                                    scheduleOverlay();
                                }}
                            }}, true);
                        }}
                    }};

                    bindLoginButton();
                    const observerKey = '__telkomLoginOverlayObserverV2';
                    const oldObserver = window.parent[observerKey];
                    if (oldObserver && typeof oldObserver.disconnect === 'function') {{
                        oldObserver.disconnect();
                    }}
                    const observer = new MutationObserver(bindLoginButton);
                    observer.observe(parentDocument.body, {{ childList: true, subtree: true }});
                    window.parent[observerKey] = observer;
                }})();
            </script>
            </body>
            </html>
            """,
            height=0,
            scrolling=False,
        )
    except Exception as error:
        LOGGER.exception("Overlay klik login gagal dipasang: %s", error)


def remove_login_transition_overlay() -> None:
    """Hilangkan overlay setelah dashboard atau pesan error selesai dirender."""
    try:
        components.html(
            f"""
            <script>
                (() => {{
                    try {{
                        const doc = window.parent.document;
                        const holder = doc.getElementById({json.dumps(LOGIN_OVERLAY_ID)});
                        const style = doc.getElementById({json.dumps(LOGIN_OVERLAY_STYLE_ID)});
                        if (holder) {{
                            const overlay = holder.querySelector('.telkom-loading-overlay');
                            const target = overlay || holder;

                            // Tunggu dua frame dan jeda singkat agar seluruh delta dashboard
                            // sudah selesai dicat sebelum overlay dilepas.
                            window.parent.requestAnimationFrame(() => {{
                                window.parent.requestAnimationFrame(() => {{
                                    window.setTimeout(() => {{
                                        target.style.transition = 'opacity .20s ease, transform .20s ease';
                                        target.style.opacity = '0';
                                        target.style.transform = 'scale(1.008)';
                                        target.style.pointerEvents = 'none';
                                        window.setTimeout(() => holder.remove(), 220);
                                        if (style) window.setTimeout(() => style.remove(), 240);
                                    }}, 70);
                                }});
                            }});
                        }} else if (style) {{
                            style.remove();
                        }}
                    }} catch (error) {{}}
                }})();
            </script>
            """,
            height=0,
            scrolling=False,
        )
    except Exception:
        pass


def _cancel_login_transition() -> None:
    """Batalkan transisi ketika validasi login gagal."""
    st.session_state.pop(LOGIN_TRANSITION_ACTIVE_KEY, None)
    st.session_state.pop(LOGIN_TRANSITION_DONE_KEY, None)
    st.session_state.pop(LOGIN_SUBMISSION_LOCK_KEY, None)
    remove_login_transition_overlay()

def refresh_cookie_manager_for_run() -> stx.CookieManager | None:
    """Segarkan snapshot cookie satu kali pada setiap rerun autentikasi.

    ``extra-streamlit-components`` mengembalikan nilai cookie secara asinkron.
    Objek lama tidak boleh terus dipakai setelah proses Streamlit dimulai ulang,
    karena snapshot awalnya dapat masih kosong. Fungsi ini sengaja dipanggil dari
    ``app.main`` hanya ketika pengguna belum terautentikasi.
    """
    try:
        manager = stx.CookieManager(key="dashboard_remember_me_v2")
        st.session_state[COOKIE_MANAGER_SESSION_KEY] = manager
        return manager
    except Exception as error:
        LOGGER.exception("refresh_cookie_manager_for_run gagal: %s", error)
        st.session_state.pop(COOKIE_MANAGER_SESSION_KEY, None)
        return None


def _get_cookie_manager() -> stx.CookieManager:
    """Ambil CookieManager yang sudah disegarkan pada rerun aktif."""
    manager = st.session_state.get(COOKIE_MANAGER_SESSION_KEY)
    if manager is None:
        manager = refresh_cookie_manager_for_run()
    if manager is None:
        raise RuntimeError("Komponen cookie browser belum tersedia.")
    return manager


def _read_remember_token() -> str | None:
    """Baca token remember-me dari snapshot cookie pada rerun aktif."""
    try:
        token = _get_cookie_manager().get(REMEMBER_COOKIE_KEY)
        if token is None:
            return None
        token_text = str(token).strip()
        return token_text or None
    except Exception as error:
        LOGGER.exception("_read_remember_token gagal: %s", error)
        return None


def set_remember_cookie(token: str) -> bool:
    """Kirim perintah penyimpanan cookie remember-me ke browser."""
    try:
        expires = datetime.now() + timedelta(hours=REMEMBER_ME_HOURS)
        _get_cookie_manager().set(
            REMEMBER_COOKIE_KEY,
            token,
            expires_at=expires,
            max_age=REMEMBER_ME_HOURS * 60 * 60,
            path="/",
            same_site="lax",
            key="set_remember_cookie",
        )
        return True
    except Exception as error:
        LOGGER.exception("set_remember_cookie gagal: %s", error)
        return False


def clear_remember_cookie() -> None:
    """Hapus cookie remember-me tanpa error jika cookie belum tersedia."""
    try:
        _get_cookie_manager().delete(
            REMEMBER_COOKIE_KEY,
            key="clear_remember_cookie",
        )
    except KeyError:
        return
    except Exception as error:
        LOGGER.exception("clear_remember_cookie gagal: %s", error)


def _finish_login(user: dict, token: str | None = None) -> None:
    """Simpan data pengguna ke session setelah login berhasil."""
    public_user = {
        "user_id": user.get("user_id"),
        "username": user.get("username", ""),
        "fullname": user.get("fullname", ""),
        "email": user.get("email", ""),
        "role": normalize_role(
            user.get("role", DEFAULT_ROLE),
            user.get("user_id"),
        ),
    }
    st.session_state["user"] = public_user
    st.session_state["logged_in"] = True
    st.session_state["username"] = public_user["username"]
    st.session_state["fullname"] = public_user["fullname"]
    st.session_state["role"] = public_user["role"]
    st.session_state["user_id"] = public_user["user_id"]
    st.session_state["page"] = "Beranda"
    st.session_state["selected_page"] = "Beranda"
    st.session_state.pop("sidebar_navigation_v2", None)
    st.session_state.pop("_cookie_polls", None)
    st.session_state.pop("_remember_restore_done", None)
    st.session_state.pop("_remember_cookie_save_attempts", None)
    st.session_state.pop(COOKIE_BOOTSTRAP_PASS_KEY, None)
    st.session_state.pop(LOGIN_SUBMISSION_LOCK_KEY, None)
    st.session_state.pop(POST_LOGOUT_RESTORE_GUARD_KEY, None)
    # Objek CookieManager hanya diperlukan saat autentikasi. Jangan bawa objek
    # komponen ini ke run dashboard berikutnya.
    st.session_state.pop(COOKIE_MANAGER_SESSION_KEY, None)

    if token:
        st.session_state["active_remember_token"] = token
    else:
        st.session_state.pop("active_remember_token", None)

    if st.session_state.get(LOGIN_TRANSITION_ACTIVE_KEY):
        st.session_state[LOGIN_TRANSITION_DONE_KEY] = True

    # Audit log bersifat pelengkap. Kegagalan pencatatan tidak boleh
    # membatalkan session yang kredensialnya sudah tervalidasi.
    try:
        log_activity(
            "LOGIN_SUCCESS",
            "Autentikasi",
            "Login pengguna berhasil.",
            user_id=public_user.get("user_id"),
            username=str(public_user.get("username", "")),
            fullname=str(public_user.get("fullname", "")),
            role=str(public_user.get("role", "")),
            metadata={"remember_me": bool(token)},
        )
    except Exception as error:
        LOGGER.exception("Audit login berhasil gagal dicatat: %s", error)


def complete_pending_remember_login() -> bool:
    """Pulihkan transaksi login tertunda dari patch lama tanpa iframe cookie.

    Fungsi ini hanya menjadi jalur kompatibilitas ketika session lama masih
    menyimpan ``pending_remember_user``. Session langsung diselesaikan lalu
    seluruh state pending dibersihkan. Konfirmasi cookie tidak dijalankan lagi
    setelah login karena dapat mengubah urutan komponen sidebar.
    """
    try:
        pending_user = st.session_state.get("pending_remember_user")
        pending_token = st.session_state.get("pending_remember_token")
        if not pending_user:
            return False

        _finish_login(
            pending_user,
            str(pending_token) if pending_token else None,
        )
        st.session_state.pop("pending_remember_user", None)
        st.session_state.pop("pending_remember_token", None)
        st.session_state.pop("_remember_cookie_save_attempts", None)
        st.session_state["remembered_username"] = str(
            pending_user.get("username", "")
        )
        return True
    except Exception as error:
        LOGGER.exception("complete_pending_remember_login gagal: %s", error)
        return False


def try_restore_remember_login() -> str:
    """Coba memulihkan sesi login dari cookie remember-me."""
    try:
        if st.session_state.get("logged_in"):
            return "none"
        if st.session_state.get(POST_LOGOUT_RESTORE_GUARD_KEY):
            # Logout eksplisit tidak boleh langsung diikuti polling cookie.
            # Token server sudah dicabut dan halaman login harus tampil segera.
            st.session_state["_remember_restore_done"] = True
            st.session_state["_cookie_polls"] = MAX_COOKIE_POLLS
            return "none"
        if st.session_state.get("pending_remember_user"):
            return "none"
        if st.session_state.get("_remember_restore_done"):
            return "none"

        token = _read_remember_token()
        if not token:
            # Pada render pertama komponen cookie mengembalikan nilai default
            # sebelum browser mengirim snapshot sebenarnya. Tahan boot overlay
            # satu kali dan biarkan komponen memicu rerun alami. Pada rerun
            # berikutnya, nilai cookie sudah siap atau memang tidak tersedia.
            bootstrap_pass = int(
                st.session_state.get(COOKIE_BOOTSTRAP_PASS_KEY, 0)
            )
            if bootstrap_pass < 1:
                st.session_state[COOKIE_BOOTSTRAP_PASS_KEY] = 1
                return "wait"

            st.session_state["_remember_restore_done"] = True
            return "none"

        st.session_state["_remember_restore_done"] = True
        st.session_state.pop(COOKIE_BOOTSTRAP_PASS_KEY, None)
        user = validate_remember_token(token)
        if user is None:
            clear_remember_cookie()
            return "none"

        st.session_state["remembered_username"] = user["username"]
        _finish_login(user, token)
        return "ok"
    except Exception as error:
        LOGGER.exception("try_restore_remember_login gagal: %s", error)
        return "none"


def start_remember_login(user: dict) -> bool:
    """Aktifkan session dan kirim cookie remember-me satu kali.

    CookieManager hanya hidup pada run form login. Setelah perintah ``set``
    dikirim, session langsung dikomit dan tidak ada proses konfirmasi cookie di
    run dashboard. Ini menjaga urutan komponen sidebar tetap stabil.
    """
    try:
        stale_token = st.session_state.pop("pending_remember_token", None)
        st.session_state.pop("pending_remember_user", None)
        st.session_state.pop("_remember_cookie_save_attempts", None)
        if stale_token:
            revoke_remember_token(str(stale_token))

        token = create_remember_token(user["user_id"])
        if not token:
            _finish_login(user, None)
            return False

        if not set_remember_cookie(token):
            revoke_remember_token(token)
            _finish_login(user, None)
            st.session_state["remember_cookie_warning"] = (
                "Login berhasil, tetapi cookie Ingat Saya belum dapat dibuat."
            )
            return False

        st.session_state["remembered_username"] = str(
            user.get("username", "")
        )
        _finish_login(user, token)
        return True
    except Exception as error:
        LOGGER.exception("start_remember_login gagal: %s", error)
        _finish_login(user, None)
        return False


def show_login_page() -> None:
    """Tampilkan halaman login beserta validasi kredensial pengguna."""
    feedback_slot = None
    try:
        _inject_login_css()

        if "page" not in st.session_state:
            st.session_state["page"] = "login"

        # Placeholder dibuat sebelum form agar semua informasi validasi dan
        # error login selalu muncul di atas card, bukan di bagian bawah halaman.
        feedback_slot = st.empty()

        with st.form("login_form", clear_on_submit=False, border=True):
            st.markdown(
                """
                <div class="auth-header">
                    <div class="auth-icon-wrap">
                        <div class="auth-icon">📡</div>
                    </div>
                    <h1 class="auth-title">Dashboard Telkom Group</h1>
                    <p class="auth-subtitle">
                        Masukkan kredensial Anda untuk melanjutkan
                    </p>
                </div>
                """,
                unsafe_allow_html=True,
            )

            username = st.text_input(
                "Username",
                value=st.session_state.get("remembered_username", ""),
                placeholder="Masukkan username",
                key="login_username",
            )

            password = st.text_input(
                "Password",
                type="password",
                placeholder="Masukkan password",
                key="login_password",
            )

            remember_me = st.checkbox(
                "Ingat Saya",
                key="remember_me",
                help=(
                    f"Simpan sesi login selama {REMEMBER_ME_HOURS} jam "
                    "pada browser ini."
                ),
            )

            login_submitted = st.form_submit_button(
                "🔐 Masuk",
                use_container_width=True,
            )

            st.markdown(
                '<div class="auth-divider"></div>',
                unsafe_allow_html=True,
            )
            st.markdown(
                '<p class="auth-helper-text">Belum punya akun?</p>',
                unsafe_allow_html=True,
            )

            register_submitted = st.form_submit_button(
                "Daftar di sini",
                use_container_width=True,
            )

            st.caption(get_auth_footer_text())

        _install_login_click_overlay()

        if register_submitted:
            st.session_state["page"] = "register"
            st.rerun()

        if login_submitted:
            if st.session_state.get(LOGIN_SUBMISSION_LOCK_KEY):
                # Cegah klik/submit ganda ketika browser masih mengirim delta form.
                st.stop()

            st.session_state[LOGIN_SUBMISSION_LOCK_KEY] = True
            username_clean = username.strip().lower()

            if not username_clean or not password:
                _cancel_login_transition()
                log_activity(
                    "LOGIN_FAILED",
                    "Autentikasi",
                    "Login ditolak karena field belum lengkap.",
                    status="failed",
                    username=username_clean or "anonymous",
                    metadata={"reason": "field_kosong"},
                )
                feedback_slot.warning("⚠️ Mohon isi semua field")
                return

            st.session_state[LOGIN_TRANSITION_ACTIVE_KEY] = True
            st.session_state.pop(LOGIN_TRANSITION_DONE_KEY, None)

            user = get_user(username_clean)
            valid = bool(
                user
                and verify_password(
                    password,
                    str(user.get("password_hash", "")),
                )
            )

            if not valid:
                _cancel_login_transition()
                log_activity(
                    "LOGIN_FAILED",
                    "Autentikasi",
                    "Login ditolak karena kredensial tidak valid.",
                    status="failed",
                    username=username_clean or "anonymous",
                    metadata={"reason": "kredensial_tidak_valid"},
                )
                feedback_slot.error(
                    "❌ Username atau password salah. Silakan coba lagi."
                )
                return

            if remember_me:
                start_remember_login(user)
                # Session sudah dikomit pada klik pertama. Rerun tunggal ini
                # hanya memindahkan tampilan ke Beranda; penulisan cookie akan
                # dikonfirmasi tanpa menahan akses pengguna.
                st.rerun()

            st.session_state["remembered_username"] = ""
            active_token = st.session_state.get("active_remember_token")
            if active_token:
                # Mencabut token pada server sudah cukup untuk menonaktifkan
                # cookie lama. Penghapusan cookie browser dilakukan saat logout
                # agar login biasa tidak memicu rerun komponen tambahan.
                revoke_remember_token(str(active_token))

            _finish_login(user, None)
            st.rerun()

    except Exception as error:
        # Jika session sudah berhasil disimpan, jangan tampilkan error palsu hanya
        # karena komponen browser mengirim delta/rerun sesudah autentikasi.
        if st.session_state.get("logged_in"):
            LOGGER.info("Sesi login sudah aktif; melanjutkan ke dashboard: %s", error)
            st.rerun()

        _cancel_login_transition()
        LOGGER.exception("Login gagal diproses: %s", error)
        pesan_error = "Terjadi kesalahan saat login. Silakan coba kembali."
        if feedback_slot is not None:
            feedback_slot.error(pesan_error)
        else:
            st.error(pesan_error)


def render_login() -> None:
    """Alias kompatibilitas untuk pemanggilan halaman login lama."""
    show_login_page()
