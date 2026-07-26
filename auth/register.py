"""Halaman registrasi pengguna Dashboard Analisis Telkom Group."""

import re
import time

import streamlit as st

from utils.audit_logger import log_activity
from utils.app_version import get_auth_footer_text
import streamlit.components.v1 as components

from auth.auth_utils import register_user

EMAIL_PATTERN = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")
USERNAME_PATTERN = re.compile(r"^[a-z0-9_]+$")


def _inject_register_css() -> None:
    """Terapkan halaman putih dengan form register hitam yang terpusat."""
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
            padding: 56px 20px 40px !important;
            display: flex !important;
            flex-direction: column !important;
            justify-content: flex-start !important;
            background: transparent !important;
            overflow: visible !important;
        }

        div[data-testid="stHorizontalBlock"] {
            width: 100% !important;
            align-items: center !important;
            justify-content: center !important;
        }

        body [data-testid="stAppViewContainer"] div[data-testid="stForm"] {
            width: 100% !important;
            max-width: 660px !important;
            margin: 0 auto !important;
            padding: 34px 34px 24px !important;
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
            margin: 0 0 22px !important;
            text-align: center !important;
        }

        .auth-icon-wrap {
            width: 64px;
            height: 64px;
            display: flex;
            align-items: center;
            justify-content: center;
            margin: 0 auto 16px;
            border: 1px solid rgba(229, 57, 53, 0.75);
            border-radius: 18px;
            background: rgba(229, 57, 53, 0.10);
            box-shadow: 0 0 24px rgba(229, 57, 53, 0.16);
        }

        .auth-icon {
            font-size: 30px;
            line-height: 1;
        }

        .auth-title {
            margin: 0 !important;
            color: var(--auth-text) !important;
            -webkit-text-fill-color: var(--auth-text) !important;
            font-size: 28px !important;
            font-weight: 800 !important;
            line-height: 1.18 !important;
            letter-spacing: -0.035em !important;
        }

        .auth-subtitle {
            margin: 8px 0 0 !important;
            color: var(--auth-muted) !important;
            -webkit-text-fill-color: var(--auth-muted) !important;
            font-size: 14px !important;
            font-weight: 400 !important;
            line-height: 1.55 !important;
        }

        body [data-testid="stAppViewContainer"] div[data-testid="stForm"] div[data-testid="stTextInput"] {
            width: 100% !important;
            margin-bottom: 6px !important;
        }

        body [data-testid="stAppViewContainer"] div[data-testid="stForm"] div[data-testid="stTextInput"] label,
        body [data-testid="stAppViewContainer"] div[data-testid="stForm"] div[data-testid="stTextInput"] label p {
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

        .password-strength {
            width: 100%;
            margin: 2px 0 10px !important;
            padding: 10px 12px !important;
            background: rgba(255, 255, 255, 0.035) !important;
            border: 1px solid rgba(255, 255, 255, 0.08) !important;
            border-radius: 10px !important;
            transition: border-color 0.2s ease, background 0.2s ease !important;
        }

        .password-strength__header {
            display: flex;
            align-items: center;
            justify-content: space-between;
            gap: 12px;
            margin-bottom: 8px;
        }

        .password-strength__label {
            color: #A9A9A9 !important;
            -webkit-text-fill-color: #A9A9A9 !important;
            font-size: 12px !important;
            font-weight: 600 !important;
            line-height: 1.3 !important;
        }

        .password-strength__status {
            color: #777777 !important;
            -webkit-text-fill-color: #777777 !important;
            font-size: 12px !important;
            font-weight: 800 !important;
            line-height: 1.3 !important;
        }

        .password-strength__bars {
            display: grid;
            grid-template-columns: repeat(3, minmax(0, 1fr));
            gap: 6px;
            width: 100%;
            margin-bottom: 7px;
        }

        .password-strength__bar {
            height: 5px;
            border-radius: 999px;
            background: #343434;
            transition: background 0.2s ease, box-shadow 0.2s ease;
        }

        .password-strength__hint {
            margin: 0 !important;
            color: #7F7F7F !important;
            -webkit-text-fill-color: #7F7F7F !important;
            font-size: 0.75rem /* FIX: minimum 12px agar terbaca di tablet */ !important;
            font-weight: 500 !important;
            line-height: 1.45 !important;
        }

        .password-strength[data-state="weak"] {
            background: rgba(229, 57, 53, 0.055) !important;
            border-color: rgba(229, 57, 53, 0.32) !important;
        }

        .password-strength[data-state="weak"] .password-strength__status {
            color: #FF5C58 !important;
            -webkit-text-fill-color: #FF5C58 !important;
        }

        .password-strength[data-state="weak"] .password-strength__bar:nth-child(1) {
            background: #E53935 !important;
            box-shadow: 0 0 10px rgba(229, 57, 53, 0.32) !important;
        }

        .password-strength[data-state="medium"] {
            background: rgba(255, 152, 0, 0.055) !important;
            border-color: rgba(255, 152, 0, 0.32) !important;
        }

        .password-strength[data-state="medium"] .password-strength__status {
            color: #FFB13B !important;
            -webkit-text-fill-color: #FFB13B !important;
        }

        .password-strength[data-state="medium"] .password-strength__bar:nth-child(-n+2) {
            background: #FF9800 !important;
            box-shadow: 0 0 10px rgba(255, 152, 0, 0.26) !important;
        }

        .password-strength[data-state="strong"] {
            background: rgba(76, 175, 80, 0.055) !important;
            border-color: rgba(76, 175, 80, 0.32) !important;
        }

        .password-strength[data-state="strong"] .password-strength__status {
            color: #66C96A !important;
            -webkit-text-fill-color: #66C96A !important;
        }

        .password-strength[data-state="strong"] .password-strength__bar {
            background: #4CAF50 !important;
            box-shadow: 0 0 10px rgba(76, 175, 80, 0.24) !important;
        }

        .password-note {
            margin: -2px 0 7px !important;
            color: #808080 !important;
            -webkit-text-fill-color: #808080 !important;
            font-size: 0.75rem /* FIX: minimum 12px agar terbaca di tablet */ !important;
            line-height: 1.45 !important;
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


        @media (max-height: 920px) {
            .block-container,
            [data-testid="stMainBlockContainer"] {
                padding-top: 32px !important;
                justify-content: flex-start !important;
            }
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

        @media (max-width: 760px) {
            .block-container,
            [data-testid="stMainBlockContainer"] {
                min-height: 100vh !important;
                padding: 22px 12px 28px !important;
                display: block !important;
            }

            body [data-testid="stAppViewContainer"] div[data-testid="stForm"] {
                width: 100% !important;
                max-width: 660px !important;
                padding: 26px 20px 21px !important;
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


def _render_password_strength_tracker() -> None:
    """Render indikator kekuatan password yang berubah langsung saat diketik."""
    tracker_html = (
        '<div id="register-password-strength" '
        'class="password-strength" data-state="empty" aria-live="polite">'
        '<div class="password-strength__header">'
        '<span class="password-strength__label">Kekuatan password</span>'
        '<span id="register-password-strength-status" '
        'class="password-strength__status">Belum dinilai</span>'
        '</div>'
        '<div class="password-strength__bars" aria-hidden="true">'
        '<span class="password-strength__bar"></span>'
        '<span class="password-strength__bar"></span>'
        '<span class="password-strength__bar"></span>'
        '</div>'
        '<p id="register-password-strength-hint" '
        'class="password-strength__hint">Gunakan minimal 8 karakter.</p>'
        '</div>'
    )

    st.markdown(
        tracker_html,
        unsafe_allow_html=True,
    )

    # Nilai widget di dalam st.form tidak memicu rerun saat pengguna mengetik.
    # Listener browser berikut membaca input password secara langsung agar
    # indikator tetap berubah real-time tanpa mengganggu proses registrasi.
    tracker_script = r"""
        <script>
        (() => {
            const parentDocument = window.parent.document;
            const trackerId = "register-password-strength";
            const statusId = "register-password-strength-status";
            const hintId = "register-password-strength-hint";

            const evaluatePassword = (value) => {
                const hasLower = /[a-z]/.test(value);
                const hasUpper = /[A-Z]/.test(value);
                const hasNumber = /[0-9]/.test(value);
                const hasSymbol = /[^A-Za-z0-9]/.test(value);
                const variety = [hasLower, hasUpper, hasNumber, hasSymbol]
                    .filter(Boolean)
                    .length;

                if (!value) {
                    return {
                        state: "empty",
                        status: "Belum dinilai",
                        hint: "Gunakan minimal 8 karakter.",
                    };
                }

                if (value.length < 8 || variety <= 1) {
                    return {
                        state: "weak",
                        status: "Lemah",
                        hint: "Tambahkan panjang serta variasi huruf, angka, atau simbol.",
                    };
                }

                if (value.length >= 10 && variety >= 3) {
                    return {
                        state: "strong",
                        status: "Kuat",
                        hint: "Password memiliki panjang dan kombinasi karakter yang kuat.",
                    };
                }

                return {
                    state: "medium",
                    status: "Sedang",
                    hint: "Tambahkan huruf besar, angka, atau simbol agar lebih kuat.",
                };
            };

            const findPasswordInput = () => {
                const exactInput = parentDocument.querySelector(
                    'input[aria-label="Password"]'
                );

                if (exactInput) {
                    return exactInput;
                }

                const passwordInputs = Array.from(
                    parentDocument.querySelectorAll('input[type="password"]')
                );

                return passwordInputs[0] || null;
            };

            const updateTracker = (input) => {
                const tracker = parentDocument.getElementById(trackerId);
                const status = parentDocument.getElementById(statusId);
                const hint = parentDocument.getElementById(hintId);

                if (!tracker || !status || !hint) {
                    return;
                }

                const result = evaluatePassword(input.value || "");
                tracker.dataset.state = result.state;
                status.textContent = result.status;
                hint.textContent = result.hint;
            };

            const bindTracker = () => {
                const input = findPasswordInput();
                const tracker = parentDocument.getElementById(trackerId);

                if (!input || !tracker) {
                    window.setTimeout(bindTracker, 120);
                    return;
                }

                if (input.dataset.passwordStrengthBound !== "true") {
                    input.dataset.passwordStrengthBound = "true";
                    input.addEventListener("input", () => updateTracker(input));
                    input.addEventListener("change", () => updateTracker(input));
                }

                updateTracker(input);

                let previousValue = input.value || "";
                window.setInterval(() => {
                    const currentValue = input.value || "";
                    if (currentValue !== previousValue) {
                        previousValue = currentValue;
                        updateTracker(input);
                    }
                }, 350);
            };

            bindTracker();
        })();
        </script>
    """

    components.html(
        tracker_script,
        height=0,
        scrolling=False,
    )

def _translate_registration_error(message: str) -> str:
    """Terjemahkan pesan autentikasi menjadi pesan UI yang ramah."""
    normalized = message.strip().lower()
    if "username sudah digunakan" in normalized:
        return "❌ Username sudah digunakan, coba yang lain"
    if "email sudah terdaftar" in normalized:
        return "❌ Email sudah terdaftar, gunakan email lain"
    if "password minimal" in normalized:
        return "❌ Password minimal 8 karakter"
    if "username tidak boleh mengandung spasi" in normalized:
        return "❌ Username tidak boleh mengandung spasi"
    return f"❌ {message}"


def show_register_page() -> None:
    """Tampilkan halaman registrasi beserta seluruh validasinya."""
    try:
        _inject_register_css()

        if "page" not in st.session_state:
            st.session_state["page"] = "login"

        with st.form("register_form", clear_on_submit=False, border=True):
            st.markdown(
                """
                <div class="auth-header">
                    <div class="auth-icon-wrap">
                        <div class="auth-icon">🛡️</div>
                    </div>
                    <h1 class="auth-title">Buat Akun Baru</h1>
                    <p class="auth-subtitle">
                        Lengkapi data berikut untuk mendaftar
                    </p>
                </div>
                """,
                unsafe_allow_html=True,
            )

            fullname = st.text_input(
                "Nama Lengkap",
                placeholder="Masukkan nama lengkap",
                key="register_fullname",
            )
            username = st.text_input(
                "Username",
                placeholder="Buat username (min. 3 karakter)",
                key="register_username",
            )
            email = st.text_input(
                "Email",
                placeholder="Masukkan alamat email aktif",
                key="register_email",
            )
            password = st.text_input(
                "Password",
                type="password",
                placeholder="Buat password (min. 8 karakter)",
                key="register_password",
            )

            _render_password_strength_tracker()

            confirm_password = st.text_input(
                "Konfirmasi Password",
                type="password",
                placeholder="Ulangi password",
                key="register_confirm_password",
            )

            st.markdown(
                '<div class="password-note">'
                'Gunakan minimal 8 karakter agar akun dapat didaftarkan.'
                '</div>',
                unsafe_allow_html=True,
            )

            feedback_slot = st.empty()

            register_submitted = st.form_submit_button(
                "📝 Daftar",
                use_container_width=True,
            )

            st.markdown(
                '<div class="auth-divider"></div>',
                unsafe_allow_html=True,
            )
            st.markdown(
                '<p class="auth-helper-text">Sudah punya akun?</p>',
                unsafe_allow_html=True,
            )

            login_submitted = st.form_submit_button(
                "Login di sini",
                use_container_width=True,
            )

            st.caption(get_auth_footer_text())

        if login_submitted:
            st.session_state["page"] = "login"
            st.rerun()

        if register_submitted:
            fullname_clean = fullname.strip()
            username_clean = username.strip().lower()
            email_clean = email.strip().lower()

            if not all(
                [
                    fullname_clean,
                    username_clean,
                    email_clean,
                    password,
                    confirm_password,
                ]
            ):
                feedback_slot.warning("⚠️ Semua field wajib diisi")
            elif len(username_clean) < 3:
                feedback_slot.error("❌ Username minimal 3 karakter")
            elif not USERNAME_PATTERN.fullmatch(username_clean):
                feedback_slot.error(
                    "❌ Username hanya boleh berisi huruf kecil, angka, "
                    "dan underscore (_)"
                )
            elif not EMAIL_PATTERN.fullmatch(email_clean):
                feedback_slot.error("❌ Format email tidak valid")
            elif len(password) < 8:
                feedback_slot.error("❌ Password minimal 8 karakter")
            elif password != confirm_password:
                feedback_slot.error("❌ Password tidak cocok")
            else:
                success, message = register_user(
                    fullname_clean,
                    username_clean,
                    email_clean,
                    password,
                )

                if success:
                    log_activity(
                        "REGISTER_SUCCESS",
                        "Autentikasi",
                        "Registrasi akun baru berhasil.",
                        username=username_clean,
                        fullname=fullname_clean,
                        role="management",
                        metadata={"email_domain": email_clean.split("@")[-1] if "@" in email_clean else "-"},
                    )
                    feedback_slot.success(
                        "✅ Akun berhasil dibuat! Mengarahkan ke halaman login..."
                    )
                    time.sleep(2)
                    st.session_state["page"] = "login"
                    st.rerun()
                else:
                    log_activity(
                        "REGISTER_FAILED",
                        "Autentikasi",
                        "Registrasi akun baru gagal.",
                        status="failed",
                        username=username_clean or "anonymous",
                        fullname=fullname_clean or "-",
                        metadata={"reason": message},
                    )
                    feedback_slot.error(_translate_registration_error(message))

    except Exception as error:
        st.error(f"Terjadi kesalahan saat registrasi: {error}")


def render_register() -> None:
    """Alias kompatibilitas untuk pemanggilan halaman register lama."""
    show_register_page()
