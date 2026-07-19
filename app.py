"""
Entry point utama dashboard analitik media sosial Telkom Group.
Skripsi S1 Sains Data — SNA & IndoBERT Sentiment Analysis.
"""

from base64 import b64encode
from html import escape
from functools import lru_cache
import logging
from importlib import import_module
from pathlib import Path
from typing import Callable
import sys

import streamlit as st
import streamlit.components.v1 as components

LOGGER = logging.getLogger(__name__)

# Pastikan import lokal (auth/, pages/, utils/) selalu dapat ditemukan,
# termasuk saat aplikasi dijalankan dari Command Prompt Windows.
PROJECT_ROOT = Path(__file__).resolve().parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

st.set_page_config(
    page_title="Dashboard Analisis Telkom Group",
    page_icon="📡",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Inisialisasi state paling awal sebelum loader, autentikasi, sidebar, atau
# halaman lain membaca session_state. Ini mencegah key hilang saat rerun.
_EARLY_SESSION_DEFAULTS = {
    "user": None,
    "logged_in": False,
    "page": "login",
    "username": "",
    "fullname": "",
    "role": "",
    "user_id": None,
    "dark_mode": True,
    "remembered_username": "",
    "selected_page": "Beranda",
    "_last_rendered_route": None,
    "_startup_loading_active": True,
}
for _session_key, _session_default in _EARLY_SESSION_DEFAULTS.items():
    if _session_key not in st.session_state:
        st.session_state[_session_key] = _session_default

# Import loader lebih awal agar animasi dapat dikirim ke browser sebelum
# modul halaman, model, chart, dan autentikasi selesai di-import.
from utils.loading_screen import tampilkan_loading_awal  # noqa: E402

_STARTUP_LOADING_PLACEHOLDER = None
if st.session_state.get("_startup_loading_active", True):
    _STARTUP_LOADING_PLACEHOLDER = tampilkan_loading_awal()

from streamlit_option_menu import option_menu  # noqa: E402

from auth.auth_utils import get_user_by_id, init_db, revoke_remember_token  # noqa: E402
from auth.login import (  # noqa: E402
    MAX_COOKIE_POLLS,
    clear_remember_cookie,
    complete_pending_remember_login,
    show_login_page,
    try_restore_remember_login,
)
from auth.register import show_register_page  # noqa: E402
from utils.css_loader import load_css  # noqa: E402
from utils.loading_screen import layar_loading  # noqa: E402

ASSETS_DIR = Path(__file__).resolve().parent / "assets"
DEFAULT_AVATAR = ASSETS_DIR / "default_avatar.png"
LOGO_PATH = ASSETS_DIR / "logo.png"
TELKOM_LOGO_PATH = ASSETS_DIR / "telkom_indonesia_logo.png"

FOOTER_TEXT = "© 2026 Aulia Rahmadiva Wardana · NPM 184220019 · ULBI Bandung"
APP_VERSION = "v2.0 · ULBI 2026"

# Label yang terlihat pengguna dipisahkan dari nama route lama agar routing tetap aman.
MENU_USER = [
    {"label": "Beranda", "icon": "house", "route": "Beranda"},
    {"label": "Dataset", "icon": "bar-chart", "route": "Dataset"},
    {
        "label": "Analisis Sentimen",
        "icon": "emoji-smile",
        "route": "Analisis Sentimen",
    },
    {
        "label": "Analisis Topik",
        "icon": "chat-left-text",
        "route": "Analisis Topik",
    },
    {
        "label": "Social Network Analysis",
        "icon": "diagram-3",
        "route": "Analisis Jaringan Sosial",
    },
    {"label": "Rekomendasi", "icon": "lightbulb", "route": "Rekomendasi"},
    {"label": "Profil", "icon": "person-circle", "route": "Profil"},
    {"label": "Tentang", "icon": "book", "route": "Tentang Penelitian"},
]

ADMIN_MENU = {
    "label": "Admin Panel",
    "icon": "shield-lock",
    "route": "Admin Panel",
}


# Modul halaman tidak diimpor pada startup. Setiap route hanya menyimpan
# lokasi modul dan nama fungsi render. Modul berat seperti Transformers,
# NetworkX, PyVis, WordCloud, dan Plotly baru dimuat ketika halamannya dibuka.
ROUTES: dict[str, tuple[str, str]] = {
    "Beranda": ("pages.home", "render_home"),
    "Dataset": ("pages.dataset", "render_dataset"),
    "Analisis Sentimen": ("pages.sentiment", "render_sentiment"),
    "Analisis Topik": ("pages.topic_analysis", "render_topic_analysis"),
    "Analisis Jaringan Sosial": ("pages.sna", "render_sna"),
    "Rekomendasi": ("pages.recommendation", "render_recommendation"),
    "Profil": ("auth.profile", "render_profile"),
    "Admin Panel": ("pages.admin_panel", "render_admin_panel"),
    "Tentang Penelitian": ("pages.about", "render_about"),
}


@lru_cache(maxsize=12)
def _resolve_route_handler(module_name: str, function_name: str) -> Callable[[], None]:
    """Impor fungsi halaman hanya saat route pertama kali dibuka.

    lru_cache menyimpan referensi fungsi pada proses Python tanpa mengikat
    handler halaman ke siklus cache widget Streamlit.
    """
    try:
        module = import_module(module_name)
        handler = getattr(module, function_name)
        if not callable(handler):
            raise TypeError(f"{module_name}.{function_name} bukan fungsi yang dapat dipanggil.")
        return handler
    except Exception as exc:
        raise RuntimeError(
            f"Halaman {module_name}.{function_name} gagal dimuat: {exc}"
        ) from exc


LEGACY_ROUTE_ALIASES = {
    "WordCloud": "Analisis Topik",
}

VISUAL_ROUTE_ALIASES = {
    item["label"]: item["route"] for item in [*MENU_USER, ADMIN_MENU]
}


ROUTE_VISUAL_ALIASES = {
    item["route"]: item["label"] for item in [*MENU_USER, ADMIN_MENU]
}



def _selesaikan_loading_awal() -> None:
    """Tutup loader setelah Login atau halaman dashboard selesai dirender."""
    global _STARTUP_LOADING_PLACEHOLDER

    try:
        if _STARTUP_LOADING_PLACEHOLDER is not None:
            _STARTUP_LOADING_PLACEHOLDER.empty()
    except Exception:
        pass
    finally:
        st.session_state["_startup_loading_active"] = False
        _STARTUP_LOADING_PLACEHOLDER = None


def init_session_state() -> None:
    """Inisialisasi session state dengan nilai default."""
    defaults = {
        "user": None,
        "logged_in": False,
        "page": "login",
        "username": "",
        "fullname": "",
        "role": "",
        "user_id": None,
        "dark_mode": True,
        "remembered_username": "",
        "selected_page": "Beranda",
        "_last_rendered_route": None,
        "_startup_loading_active": True,
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


def sync_authenticated_user_state() -> bool:
    """Pastikan data login tetap lengkap pada setiap rerun dan navigasi."""
    try:
        if not st.session_state.get("logged_in", False):
            st.session_state["user"] = None
            return True

        session_user = st.session_state.get("user")
        session_user_id = (
            session_user.get("user_id")
            if isinstance(session_user, dict)
            else None
        )
        user_id = st.session_state.get("user_id") or session_user_id
        if not user_id:
            raise ValueError("ID pengguna tidak tersedia pada session.")

        # Ambil data terbaru dari SQLite agar perubahan profil/role tidak ditimpa
        # oleh salinan session lama. Jika database sesaat tidak dapat dibaca,
        # gunakan objek session yang sudah tervalidasi sebagai fallback.
        user = get_user_by_id(int(user_id))
        if not user and isinstance(session_user, dict) and session_user_id:
            user = session_user
        if not user:
            raise ValueError("Data pengguna tidak ditemukan di database.")

        public_user = {
            "user_id": user.get("user_id"),
            "username": user.get("username", ""),
            "fullname": user.get("fullname", ""),
            "email": user.get("email", ""),
            "role": user.get("role", "user"),
        }
        st.session_state["user"] = public_user
        st.session_state["user_id"] = public_user["user_id"]
        st.session_state["username"] = str(public_user["username"])
        st.session_state["fullname"] = str(public_user["fullname"])
        st.session_state["role"] = str(public_user["role"])
        return True
    except Exception as exc:
        st.error(f"Sesi login tidak dapat dipulihkan: {exc}")
        st.session_state["user"] = None
        st.session_state["logged_in"] = False
        st.session_state["page"] = "login"
        st.session_state["selected_page"] = "Beranda"
        return False


def get_avatar_bytes() -> bytes | None:
    """Ambil avatar pengguna dari database atau file avatar default."""
    try:
        user_id = st.session_state.get("user_id")
        if user_id:
            user = get_user_by_id(user_id)
            if user and user.get("profile_picture"):
                return user["profile_picture"]
        if DEFAULT_AVATAR.exists():
            return DEFAULT_AVATAR.read_bytes()
        return None
    except Exception:
        st.error("Foto profil belum dapat dimuat.")
        return None


def _bytes_data_uri(image_bytes: bytes | None) -> str | None:
    """Konversi byte gambar menjadi data URI untuk HTML."""
    if not image_bytes:
        return None

    mime_type = "image/png"
    if image_bytes.startswith(b"\xff\xd8\xff"):
        mime_type = "image/jpeg"
    elif image_bytes.startswith(b"GIF8"):
        mime_type = "image/gif"
    elif image_bytes.startswith(b"RIFF") and b"WEBP" in image_bytes[:16]:
        mime_type = "image/webp"

    encoded = b64encode(image_bytes).decode("ascii")
    return f"data:{mime_type};base64,{encoded}"


def _file_data_uri(path: Path) -> str | None:
    """Baca file gambar lokal lalu ubah menjadi data URI."""
    try:
        if not path.exists():
            return None
        return _bytes_data_uri(path.read_bytes())
    except Exception:
        return None


def _inject_sidebar_css() -> None:
    """Terapkan gaya khusus sidebar Minimalist with Deep."""
    try:
        st.markdown(
            """
            <style>
                @import url('https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;600;700&family=Syne:wght@600;700;800&display=swap');

                section[data-testid="stSidebar"],
                section[data-testid="stSidebar"] > div {
                    background: #111111 !important;
                }

                section[data-testid="stSidebar"] {
                    border-right: 1px solid #2A2A2A !important;
                }

                /* Kontrol sidebar V2.19 — hanya tombol aktual yang diberi
                   gaya. Wrapper Streamlit tidak diwarnai agar tidak muncul
                   kotak merah kosong atau ikon yang hilang. */
                [data-testid="collapsedControl"],
                [data-testid="stSidebarCollapsedControl"] {
                    background: transparent !important;
                    border: 0 !important;
                    box-shadow: none !important;
                    overflow: visible !important;
                    opacity: 1 !important;
                    visibility: visible !important;
                    z-index: 1001 !important;
                }

                /* Tombol tutup: X putih selalu terlihat. */
                section[data-testid="stSidebar"] button[data-testid="stSidebarCollapseButton"],
                section[data-testid="stSidebar"] [data-testid="stSidebarCollapseButton"] > button,
                section[data-testid="stSidebar"] button[aria-label="Close sidebar"],
                section[data-testid="stSidebar"] button[aria-label="Collapse sidebar"],
                section[data-testid="stSidebar"] button[aria-label="Tutup sidebar"],
                section[data-testid="stSidebar"] button[kind="header"],
                section[data-testid="stSidebar"] button[kind="headerNoPadding"] {
                    position: relative !important;
                    width: 40px !important;
                    min-width: 40px !important;
                    height: 40px !important;
                    min-height: 40px !important;
                    margin: 0 !important;
                    padding: 0 !important;
                    display: inline-flex !important;
                    align-items: center !important;
                    justify-content: center !important;
                    opacity: 1 !important;
                    visibility: visible !important;
                    overflow: hidden !important;
                    background: #1A1A1A url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24'%3E%3Cpath d='M6.5 6.5L17.5 17.5M17.5 6.5L6.5 17.5' fill='none' stroke='%23FFFFFF' stroke-width='2.5' stroke-linecap='round'/%3E%3C/svg%3E") center / 21px 21px no-repeat !important;
                    border: 1px solid #4A4A4A !important;
                    border-radius: 10px !important;
                    box-shadow: 0 6px 18px rgba(0, 0, 0, 0.28) !important;
                    color: transparent !important;
                    -webkit-text-fill-color: transparent !important;
                    cursor: pointer !important;
                    transform: none !important;
                    transition: background-color 0.18s ease,
                                border-color 0.18s ease,
                                box-shadow 0.18s ease,
                                transform 0.22s ease !important;
                }

                section[data-testid="stSidebar"] button[data-testid="stSidebarCollapseButton"] > *,
                section[data-testid="stSidebar"] [data-testid="stSidebarCollapseButton"] > button > *,
                section[data-testid="stSidebar"] button[aria-label="Close sidebar"] > *,
                section[data-testid="stSidebar"] button[aria-label="Collapse sidebar"] > *,
                section[data-testid="stSidebar"] button[aria-label="Tutup sidebar"] > *,
                section[data-testid="stSidebar"] button[kind="header"] > *,
                section[data-testid="stSidebar"] button[kind="headerNoPadding"] > * {
                    opacity: 0 !important;
                    visibility: hidden !important;
                    pointer-events: none !important;
                }

                section[data-testid="stSidebar"] button[data-testid="stSidebarCollapseButton"]::before,
                section[data-testid="stSidebar"] button[data-testid="stSidebarCollapseButton"]::after,
                section[data-testid="stSidebar"] [data-testid="stSidebarCollapseButton"] > button::before,
                section[data-testid="stSidebar"] [data-testid="stSidebarCollapseButton"] > button::after,
                section[data-testid="stSidebar"] button[aria-label="Close sidebar"]::before,
                section[data-testid="stSidebar"] button[aria-label="Close sidebar"]::after,
                section[data-testid="stSidebar"] button[aria-label="Collapse sidebar"]::before,
                section[data-testid="stSidebar"] button[aria-label="Collapse sidebar"]::after,
                section[data-testid="stSidebar"] button[aria-label="Tutup sidebar"]::before,
                section[data-testid="stSidebar"] button[aria-label="Tutup sidebar"]::after,
                section[data-testid="stSidebar"] button[kind="header"]::before,
                section[data-testid="stSidebar"] button[kind="header"]::after,
                section[data-testid="stSidebar"] button[kind="headerNoPadding"]::before,
                section[data-testid="stSidebar"] button[kind="headerNoPadding"]::after {
                    content: none !important;
                    display: none !important;
                }

                section[data-testid="stSidebar"] button[data-testid="stSidebarCollapseButton"]:hover,
                section[data-testid="stSidebar"] [data-testid="stSidebarCollapseButton"] > button:hover,
                section[data-testid="stSidebar"] button[aria-label="Close sidebar"]:hover,
                section[data-testid="stSidebar"] button[aria-label="Collapse sidebar"]:hover,
                section[data-testid="stSidebar"] button[aria-label="Tutup sidebar"]:hover,
                section[data-testid="stSidebar"] button[kind="header"]:hover,
                section[data-testid="stSidebar"] button[kind="headerNoPadding"]:hover {
                    background: #E53935 url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24'%3E%3Cpath d='M6.5 6.5L17.5 17.5M17.5 6.5L6.5 17.5' fill='none' stroke='%23FFFFFF' stroke-width='2.5' stroke-linecap='round'/%3E%3C/svg%3E") center / 21px 21px no-repeat !important;
                    border-color: #FF5252 !important;
                    box-shadow: 0 8px 22px rgba(229, 57, 53, 0.30),
                                0 0 0 2px rgba(229, 57, 53, 0.12) !important;
                    transform: rotate(90deg) scale(1.03) !important;
                }

                /* Tombol pembuka sidebar ditangani oleh skrip terisolasi V2.27.
                   Aturan tombol X/Close di atas tidak diubah. */

                section[data-testid="stSidebar"] button[data-testid="stSidebarCollapseButton"]:focus-visible,
                section[data-testid="stSidebar"] [data-testid="stSidebarCollapseButton"] > button:focus-visible,
                button[data-testid="collapsedControl"]:focus-visible,
                [data-testid="collapsedControl"] button:focus-visible,
                button[aria-label="Open sidebar"]:focus-visible,
                button[aria-label="Close sidebar"]:focus-visible {
                    outline: 2px solid #FF5252 !important;
                    outline-offset: 2px !important;
                }

                .sidebar-v2-header {
                    display: flex;
                    align-items: center;
                    gap: 0.75rem;
                    padding: 0.35rem 0.25rem 0.8rem 0.25rem;
                }

                .sidebar-v2-logo-wrap {
                    width: 52px;
                    height: 52px;
                    min-width: 52px;
                    display: flex;
                    align-items: center;
                    justify-content: center;
                    overflow: hidden;
                    padding: 5px;
                    border: 1px solid rgba(229, 57, 53, 0.34);
                    border-radius: 15px;
                    background: #171717;
                    box-shadow:
                        0 8px 22px rgba(0, 0, 0, 0.28),
                        0 0 18px rgba(229, 57, 53, 0.10);
                }

                .sidebar-v2-logo-image {
                    width: 100%;
                    height: 100%;
                    display: block;
                    object-fit: contain;
                    object-position: center;
                    filter: drop-shadow(0 2px 4px rgba(0, 0, 0, 0.28));
                }

                .sidebar-v2-logo-fallback {
                    color: #FFFFFF !important;
                    font-family: 'Syne', sans-serif !important;
                    font-size: 1.35rem;
                    font-weight: 800;
                    line-height: 1;
                }

                .sidebar-v2-header-copy {
                    min-width: 0;
                }

                .sidebar-v2-title {
                    color: #FFFFFF !important;
                    font-family: 'Syne', sans-serif !important;
                    font-size: 1rem;
                    font-weight: 700;
                    line-height: 1.2;
                    white-space: nowrap;
                }

                .sidebar-v2-subtitle {
                    margin-top: 0.2rem;
                    color: #AAAAAA !important;
                    font-size: 0.72rem;
                    line-height: 1.25;
                }

                .sidebar-v2-red-divider {
                    height: 2px;
                    margin: 0 0 0.85rem 0;
                    border-radius: 999px;
                    background: #E53935;
                }

                .sidebar-v2-user-card {
                    display: flex;
                    align-items: center;
                    gap: 0.72rem;
                    min-height: 68px;
                    padding: 0.75rem;
                    margin-bottom: 0.9rem;
                    background: #242424;
                    border: 1px solid #2A2A2A;
                    border-radius: 8px;
                }

                .sidebar-v2-avatar,
                .sidebar-v2-initials {
                    width: 46px;
                    height: 46px;
                    min-width: 46px;
                    border-radius: 50%;
                    border: 2px solid #E53935;
                    background: #E53935;
                    box-shadow: 0 0 0 3px rgba(229, 57, 53, 0.12);
                }

                .sidebar-v2-avatar {
                    display: block;
                    object-fit: cover;
                }

                .sidebar-v2-initials {
                    display: flex;
                    align-items: center;
                    justify-content: center;
                    color: #FFFFFF !important;
                    font-family: 'Syne', sans-serif !important;
                    font-size: 0.95rem;
                    font-weight: 700;
                    letter-spacing: 0.04em;
                }

                .sidebar-v2-user-copy {
                    min-width: 0;
                }

                .sidebar-v2-user-name {
                    max-width: 195px;
                    overflow: hidden;
                    color: #FFFFFF !important;
                    font-size: 0.88rem;
                    font-weight: 700;
                    line-height: 1.25;
                    text-overflow: ellipsis;
                    white-space: nowrap;
                }

                .sidebar-v2-user-role {
                    margin-top: 0.24rem;
                    color: #AAAAAA !important;
                    font-size: 0.72rem;
                    font-weight: 500;
                }

                .sidebar-v2-section-label {
                    margin: 0.15rem 0 0.42rem 0.2rem;
                    color: #AAAAAA !important;
                    font-size: 0.64rem;
                    font-weight: 700;
                    letter-spacing: 0.11em;
                    text-transform: uppercase;
                }

                /* Pastikan option-menu mengikuti tema gelap sidebar. */
                section[data-testid="stSidebar"] .streamlit-option-menu,
                section[data-testid="stSidebar"] .streamlit-option-menu > div,
                section[data-testid="stSidebar"] ul.nav,
                section[data-testid="stSidebar"] .nav,
                section[data-testid="stSidebar"] .nav-pills,
                section[data-testid="stSidebar"] .nav-item,
                section[data-testid="stSidebar"] [data-testid="stCustomComponentV1"],
                section[data-testid="stSidebar"] [data-testid="stCustomComponentV1"] > div,
                section[data-testid="stSidebar"] iframe[title*="streamlit_option_menu"] {
                    background: #111111 !important;
                    background-color: #111111 !important;
                    border: 0 !important;
                    border-radius: 0 !important;
                    box-shadow: none !important;
                    overflow: hidden !important;
                }

                section[data-testid="stSidebar"] [data-testid="stCustomComponentV1"],
                section[data-testid="stSidebar"] [data-testid="stCustomComponentV1"] > div,
                section[data-testid="stSidebar"] [data-testid="stCustomComponentV1"] iframe {
                    border-radius: 0 !important;
                    overflow: hidden !important;
                }

                section[data-testid="stSidebar"] .nav-pills {
                    gap: 0.15rem;
                    padding: 0 !important;
                    border: 0 !important;
                    box-shadow: none !important;
                }

                section[data-testid="stSidebar"] .nav-link {
                    border-left: 3px solid transparent !important;
                }

                section[data-testid="stSidebar"] .nav-link:not(.active):hover {
                    background: #E53935 !important;
                    color: #FFFFFF !important;
                }

                section[data-testid="stSidebar"] .nav-link:not(.active):hover i {
                    color: #FFFFFF !important;
                }

                section[data-testid="stSidebar"] .nav-link.active {
                    background: #E53935 !important;
                    border-left: 3px solid #FF5252 !important;
                    color: #FFFFFF !important;
                }

                section[data-testid="stSidebar"] .nav-link.active i {
                    color: #FFFFFF !important;
                }

                section[data-testid="stSidebar"] [data-testid="stToggle"] {
                    margin: 0.65rem 0 0.1rem 0;
                    padding: 0.6rem 0.2rem 0.2rem 0.2rem;
                    border-top: 1px solid #2A2A2A;
                }

                /* Label Mode Gelap harus tetap putih pada kondisi aktif maupun nonaktif. */
                section[data-testid="stSidebar"] [data-testid="stToggle"] label,
                section[data-testid="stSidebar"] [data-testid="stToggle"] label p,
                section[data-testid="stSidebar"] [data-testid="stToggle"] label span,
                section[data-testid="stSidebar"] [data-testid="stToggle"] label div,
                section[data-testid="stSidebar"] [data-testid="stToggle"] [data-testid="stMarkdownContainer"],
                section[data-testid="stSidebar"] [data-testid="stToggle"] [data-testid="stMarkdownContainer"] * {
                    color: #FFFFFF !important;
                    -webkit-text-fill-color: #FFFFFF !important;
                    opacity: 1 !important;
                    font-size: 0.78rem !important;
                    font-weight: 500 !important;
                }

                section[data-testid="stSidebar"] [data-testid="stToggle"] button[role="switch"][aria-checked="true"] {
                    background: #E53935 !important;
                    border-color: #E53935 !important;
                }

                .mode-dark-label-v226 {
                    min-height: 42px !important;
                    display: flex !important;
                    align-items: center !important;
                    color: #FFFFFF !important;
                    -webkit-text-fill-color: #FFFFFF !important;
                    font-family: "DM Sans", sans-serif !important;
                    font-size: 0.82rem !important;
                    font-weight: 600 !important;
                    line-height: 1.2 !important;
                    white-space: nowrap !important;
                    opacity: 1 !important;
                }

                /* Ikon bantuan Mode Gelap dibuat sendiri agar stabil pada
                   Streamlit 1.35 dan tidak menggunakan popover bawaan. */
                .mode-dark-help-wrap-v215 {
                    position: relative !important;
                    width: 100% !important;
                    min-height: 42px !important;
                    display: flex !important;
                    align-items: center !important;
                    justify-content: flex-start !important;
                    overflow: visible !important;
                    padding-top: 7px !important;
                }

                .mode-dark-help-v215 {
                    position: relative !important;
                    width: 22px !important;
                    height: 22px !important;
                    min-width: 22px !important;
                    display: inline-flex !important;
                    align-items: center !important;
                    justify-content: center !important;
                    color: #FFFFFF !important;
                    -webkit-text-fill-color: #FFFFFF !important;
                    background: transparent !important;
                    border: 2px solid #FFFFFF !important;
                    border-radius: 50% !important;
                    font-size: 13px !important;
                    font-weight: 800 !important;
                    line-height: 1 !important;
                    cursor: help !important;
                    user-select: none !important;
                    outline: none !important;
                    z-index: 20 !important;
                }

                .mode-dark-help-v215:hover,
                .mode-dark-help-v215:focus-visible {
                    color: #FFFFFF !important;
                    -webkit-text-fill-color: #FFFFFF !important;
                    background: #E53935 !important;
                    border-color: #FF5252 !important;
                    box-shadow: 0 0 0 3px rgba(229, 57, 53, 0.18) !important;
                }

                .mode-dark-help-tooltip-v215 {
                    position: absolute !important;
                    right: -4px !important;
                    bottom: 32px !important;
                    width: 230px !important;
                    padding: 10px 12px !important;
                    display: none !important;
                    background: #242424 !important;
                    color: #FFFFFF !important;
                    -webkit-text-fill-color: #FFFFFF !important;
                    border: 1px solid #3A3A3A !important;
                    border-radius: 8px !important;
                    box-shadow: 0 10px 28px rgba(0, 0, 0, 0.42) !important;
                    font-family: "DM Sans", sans-serif !important;
                    font-size: 12px !important;
                    font-weight: 500 !important;
                    line-height: 1.45 !important;
                    text-align: left !important;
                    white-space: normal !important;
                    z-index: 99999 !important;
                    pointer-events: none !important;
                }

                .mode-dark-help-v215:hover .mode-dark-help-tooltip-v215,
                .mode-dark-help-v215:focus-visible .mode-dark-help-tooltip-v215 {
                    display: block !important;
                }

                .sidebar-v2-footer-divider {
                    height: 1px;
                    margin: 0.8rem 0 0.55rem 0;
                    background: #2A2A2A;
                }

                section[data-testid="stSidebar"] .st-key-sidebar_logout_v2,
                section[data-testid="stSidebar"] [data-testid="stButton"] {
                    margin: 0 !important;
                }

                section[data-testid="stSidebar"] .st-key-sidebar_logout_v2 button,
                section[data-testid="stSidebar"] [data-testid="stButton"] button[data-testid="baseButton-secondary"],
                section[data-testid="stSidebar"] [data-testid="stButton"] button[kind="secondary"] {
                    width: 100% !important;
                    min-height: 42px !important;
                    justify-content: center !important;
                    background: #E53935 !important;
                    background-color: #E53935 !important;
                    border: 1px solid #E53935 !important;
                    border-radius: 8px !important;
                    color: #FFFFFF !important;
                    -webkit-text-fill-color: #FFFFFF !important;
                    font-weight: 600 !important;
                    box-shadow: 0 8px 20px rgba(229, 57, 53, 0.18) !important;
                }

                section[data-testid="stSidebar"] .st-key-sidebar_logout_v2 button p,
                section[data-testid="stSidebar"] .st-key-sidebar_logout_v2 button span,
                section[data-testid="stSidebar"] [data-testid="stButton"] button[data-testid="baseButton-secondary"] p,
                section[data-testid="stSidebar"] [data-testid="stButton"] button[data-testid="baseButton-secondary"] span,
                section[data-testid="stSidebar"] [data-testid="stButton"] button[kind="secondary"] p,
                section[data-testid="stSidebar"] [data-testid="stButton"] button[kind="secondary"] span {
                    color: #FFFFFF !important;
                    -webkit-text-fill-color: #FFFFFF !important;
                    text-align: center !important;
                }

                section[data-testid="stSidebar"] .st-key-sidebar_logout_v2 button:hover,
                section[data-testid="stSidebar"] [data-testid="stButton"] button[data-testid="baseButton-secondary"]:hover,
                section[data-testid="stSidebar"] [data-testid="stButton"] button[kind="secondary"]:hover {
                    background: #FF5252 !important;
                    background-color: #FF5252 !important;
                    border-color: #FF5252 !important;
                    color: #FFFFFF !important;
                    -webkit-text-fill-color: #FFFFFF !important;
                    transform: translateY(-1px) !important;
                    box-shadow: 0 10px 24px rgba(229, 57, 53, 0.25) !important;
                }

                .sidebar-v2-version {
                    margin-top: 0.55rem;
                    color: #666666 !important;
                    font-size: 0.66rem;
                    line-height: 1.4;
                    text-align: center;
                }
            </style>
            """,
            unsafe_allow_html=True,
        )
    except Exception:
        st.error("Gaya sidebar belum dapat dimuat.")


def _get_user_initials(fullname: str | None) -> str:
    """Buat maksimal dua huruf inisial dari nama pengguna."""
    try:
        clean_name = " ".join(str(fullname or "").split())
        if not clean_name:
            return "PG"

        name_parts = clean_name.split(" ")
        if len(name_parts) >= 2:
            initials = f"{name_parts[0][0]}{name_parts[-1][0]}"
        else:
            initials = name_parts[0][:2]
        return initials.upper()
    except Exception:
        return "PG"


def render_sidebar_brand() -> None:
    """Tampilkan logo Telkom Indonesia pada header sidebar."""
    try:
        logo_uri = _file_data_uri(TELKOM_LOGO_PATH)
        if not logo_uri:
            logo_uri = _file_data_uri(LOGO_PATH)

        if logo_uri:
            brand_visual = (
                '<div class="sidebar-v2-logo-wrap" '
                'aria-label="Logo Telkom Indonesia">'
                f'<img class="sidebar-v2-logo-image" src="{logo_uri}" '
                'alt="Logo Telkom Indonesia">'
                '</div>'
            )
        else:
            brand_visual = (
                '<div class="sidebar-v2-logo-wrap" '
                'aria-label="Logo Telkom Indonesia tidak tersedia">'
                '<span class="sidebar-v2-logo-fallback">T</span>'
                '</div>'
            )

        st.markdown(
            f"""
            <div class="sidebar-v2-header">
                {brand_visual}
                <div class="sidebar-v2-header-copy">
                    <div class="sidebar-v2-title">Telkom Dashboard</div>
                    <div class="sidebar-v2-subtitle">Analisis Sentimen &amp; SNA</div>
                </div>
            </div>
            <div class="sidebar-v2-red-divider"></div>
            """,
            unsafe_allow_html=True,
        )
    except Exception:
        st.error("Header sidebar belum dapat ditampilkan.")


def render_sidebar_avatar() -> None:
    """Tampilkan kartu pengguna dengan foto profil atau fallback inisial."""
    try:
        fullname_raw = st.session_state.get("fullname") or "Pengguna"
        fullname_safe = escape(str(fullname_raw))
        initials_safe = escape(_get_user_initials(str(fullname_raw)))
        role = str(st.session_state.get("role") or "user").lower()
        role_label = "Administrator" if role == "admin" else "Researcher"

        avatar_uri = _bytes_data_uri(get_avatar_bytes())
        if avatar_uri:
            avatar_html = (
                f'<img class="sidebar-v2-avatar" src="{avatar_uri}" '
                'alt="Foto profil pengguna">'
            )
        else:
            avatar_html = (
                f'<div class="sidebar-v2-initials">{initials_safe}</div>'
            )

        st.markdown(
            f"""
            <div class="sidebar-v2-user-card">
                {avatar_html}
                <div class="sidebar-v2-user-copy">
                    <div class="sidebar-v2-user-name" title="{fullname_safe}">
                        {fullname_safe}
                    </div>
                    <div class="sidebar-v2-user-role">{role_label}</div>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )
    except Exception:
        st.error("Identitas pengguna belum dapat ditampilkan.")


def logout() -> None:
    """Logout pengguna, hapus cookie, dan bersihkan session state."""
    try:
        token = st.session_state.get("active_remember_token")
        if token:
            revoke_remember_token(token)
        clear_remember_cookie()
        st.session_state.clear()
        st.rerun()
    except Exception:
        st.error("Logout belum berhasil. Silakan coba kembali.")


def render_auth_page() -> None:
    """Tampilkan autentikasi tanpa menumpuk loader kedua."""
    try:
        # Pemeriksaan sesi sudah memakai loading awal. Halaman login/register
        # dirender langsung agar tidak muncul dua overlay secara berurutan.
        if st.session_state.get("page") == "register":
            show_register_page()
        else:
            show_login_page()
    except Exception:
        st.error("Halaman autentikasi belum dapat ditampilkan.")


def _menu_items() -> list[dict[str, str]]:
    """Susun delapan menu pengguna dan menu admin sesuai role."""
    try:
        items = [item.copy() for item in MENU_USER]
        if str(st.session_state.get("role") or "").lower() == "admin":
            # Admin Panel ditempatkan setelah Profil dan sebelum Tentang.
            items.insert(7, ADMIN_MENU.copy())
        return items
    except Exception:
        return [item.copy() for item in MENU_USER]


def _normalise_selected_route(selected_value: str | None) -> str:
    """Ubah label visual, alias lama, atau route menjadi route internal valid."""
    try:
        value = str(selected_value or "Beranda")
        value = LEGACY_ROUTE_ALIASES.get(value, value)
        if value in ROUTES:
            return value
        visual_route = VISUAL_ROUTE_ALIASES.get(value, "Beranda")
        return LEGACY_ROUTE_ALIASES.get(visual_route, visual_route)
    except Exception:
        return "Beranda"




def _inject_sidebar_open_button_fix() -> None:
    """Pastikan ikon pembuka sidebar selalu terlihat pada mode terang/gelap."""
    try:
        components.html(
            r"""
            <script>
            (() => {
                const parentDocument = window.parent.document;
                const styleId = "telkom-sidebar-open-control-v227-style";
                const buttonClass = "telkom-sidebar-open-control-v227";
                const iconClass = "telkom-sidebar-open-icon-v227";

                const ensureStyle = () => {
                    if (parentDocument.getElementById(styleId)) {
                        return;
                    }

                    const style = parentDocument.createElement("style");
                    style.id = styleId;
                    style.textContent = `
                        [data-testid="collapsedControl"] {
                            background: transparent !important;
                            border: 0 !important;
                            box-shadow: none !important;
                            opacity: 1 !important;
                            visibility: visible !important;
                            overflow: visible !important;
                            z-index: 1002 !important;
                        }

                        [data-testid="collapsedControl"] button.${buttonClass} {
                            position: relative !important;
                            width: 46px !important;
                            min-width: 46px !important;
                            height: 46px !important;
                            min-height: 46px !important;
                            margin: 0 !important;
                            padding: 0 !important;
                            display: inline-flex !important;
                            align-items: center !important;
                            justify-content: center !important;
                            overflow: hidden !important;
                            opacity: 1 !important;
                            visibility: visible !important;
                            background: #1F2633 !important;
                            border: 1px solid #4A5568 !important;
                            border-radius: 11px !important;
                            box-shadow: 0 7px 20px rgba(0, 0, 0, 0.30) !important;
                            color: #FFFFFF !important;
                            -webkit-text-fill-color: #FFFFFF !important;
                            cursor: pointer !important;
                            transform: none !important;
                            transition: background-color 0.18s ease,
                                        border-color 0.18s ease,
                                        box-shadow 0.18s ease,
                                        transform 0.18s ease !important;
                        }

                        [data-testid="collapsedControl"] button.${buttonClass}
                        > :not(.${iconClass}) {
                            opacity: 0 !important;
                            visibility: hidden !important;
                            pointer-events: none !important;
                        }

                        [data-testid="collapsedControl"] button.${buttonClass}
                        .${iconClass} {
                            position: absolute !important;
                            inset: 0 !important;
                            display: flex !important;
                            align-items: center !important;
                            justify-content: center !important;
                            opacity: 1 !important;
                            visibility: visible !important;
                            color: #FFFFFF !important;
                            pointer-events: none !important;
                        }

                        [data-testid="collapsedControl"] button.${buttonClass}
                        .${iconClass} svg {
                            width: 25px !important;
                            height: 25px !important;
                            display: block !important;
                            overflow: visible !important;
                            fill: none !important;
                            stroke: #FFFFFF !important;
                            opacity: 1 !important;
                            visibility: visible !important;
                            filter: none !important;
                        }

                        [data-testid="collapsedControl"] button.${buttonClass}:hover {
                            background: #E53935 !important;
                            border-color: #FF5252 !important;
                            box-shadow: 0 9px 24px rgba(229, 57, 53, 0.30),
                                        0 0 0 2px rgba(229, 57, 53, 0.12) !important;
                            transform: translateX(2px) scale(1.03) !important;
                        }

                        [data-testid="collapsedControl"] button.${buttonClass}:focus-visible {
                            outline: 2px solid #FF5252 !important;
                            outline-offset: 2px !important;
                        }
                    `;
                    parentDocument.head.appendChild(style);
                };

                const applyOpenButton = () => {
                    const wrapper = parentDocument.querySelector(
                        '[data-testid="collapsedControl"]'
                    );
                    if (!wrapper) {
                        return;
                    }

                    const button = wrapper.querySelector("button");
                    if (!button) {
                        return;
                    }

                    button.classList.add(buttonClass);
                    button.setAttribute(
                        "aria-label",
                        button.getAttribute("aria-label") || "Buka sidebar"
                    );

                    let icon = button.querySelector(`.${iconClass}`);
                    if (!icon) {
                        icon = parentDocument.createElement("span");
                        icon.className = iconClass;
                        icon.setAttribute("aria-hidden", "true");
                        icon.innerHTML = `
                            <svg viewBox="0 0 24 24" aria-hidden="true">
                                <path d="M5.5 5.5L12 12L5.5 18.5"
                                      stroke-width="2.6"
                                      stroke-linecap="round"
                                      stroke-linejoin="round"></path>
                                <path d="M11 5.5L17.5 12L11 18.5"
                                      stroke-width="2.6"
                                      stroke-linecap="round"
                                      stroke-linejoin="round"></path>
                            </svg>
                        `;
                        button.appendChild(icon);
                    }
                };

                ensureStyle();
                applyOpenButton();
                window.setTimeout(applyOpenButton, 80);
                window.setTimeout(applyOpenButton, 250);
                window.setTimeout(applyOpenButton, 700);

                const observer = new MutationObserver(() => {
                    applyOpenButton();
                });
                observer.observe(parentDocument.body, {
                    childList: true,
                    subtree: true,
                });
            })();
            </script>
            """,
            height=0,
            scrolling=False,
        )
    except Exception:
        # Tombol bawaan Streamlit tetap tersedia jika injeksi visual gagal.
        pass

def _inject_option_menu_hover_fallback() -> None:
    """Pastikan hover option-menu berwarna merah di dalam iframe komponen."""
    try:
        components.html(
            r"""
            <script>
            (() => {
                const parentDocument = window.parent.document;
                const styleId = "telkom-option-menu-hover-v212";

                const applyHoverStyle = () => {
                    const frames = Array.from(
                        parentDocument.querySelectorAll("iframe")
                    );

                    frames.forEach((frame) => {
                        try {
                            const frameDocument =
                                frame.contentDocument || frame.contentWindow.document;
                            if (!frameDocument) {
                                return;
                            }

                            const links = Array.from(
                                frameDocument.querySelectorAll(".nav-link")
                            );
                            const isSidebarMenu = links.some(
                                (link) => link.textContent.trim() === "Beranda"
                            );

                            if (!isSidebarMenu) {
                                return;
                            }

                            if (!frameDocument.getElementById(styleId)) {
                                const style = frameDocument.createElement("style");
                                style.id = styleId;
                                style.textContent = `
                                    .nav-link:not(.active):hover,
                                    .nav-link:not(.active):focus-visible {
                                        background-color: #E53935 !important;
                                        color: #FFFFFF !important;
                                    }

                                    .nav-link:not(.active):hover i,
                                    .nav-link:not(.active):hover span,
                                    .nav-link:not(.active):hover p,
                                    .nav-link:not(.active):focus-visible i,
                                    .nav-link:not(.active):focus-visible span,
                                    .nav-link:not(.active):focus-visible p {
                                        color: #FFFFFF !important;
                                    }
                                `;
                                frameDocument.head.appendChild(style);
                            }
                        } catch (error) {
                            /* Abaikan iframe lain yang tidak dapat diakses. */
                        }
                    });
                };

                applyHoverStyle();
                window.setTimeout(applyHoverStyle, 150);
                window.setTimeout(applyHoverStyle, 500);
                window.setTimeout(applyHoverStyle, 1200);
            })();
            </script>
            """,
            height=0,
            scrolling=False,
        )
    except Exception:
        # Hover dasar tetap tersedia melalui --hover-color.
        pass

def _sinkronkan_pilihan_menu(widget_key: str) -> None:
    """Simpan pilihan sidebar terbaru sebelum skrip dirender ulang."""
    try:
        visual_value = st.session_state.get(widget_key, "Beranda")
        route_value = VISUAL_ROUTE_ALIASES.get(str(visual_value), "Beranda")
        allowed_routes = {item["route"] for item in _menu_items()}
        if route_value not in allowed_routes:
            route_value = "Beranda"
        st.session_state["selected_page"] = route_value
        st.session_state["page"] = route_value
    except Exception as exc:
        st.error(f"Pilihan menu belum dapat disinkronkan: {exc}")


def render_sidebar_menu() -> str:
    """Render header, kartu pengguna, navigasi, tema, logout, dan versi."""
    dark_mode = bool(st.session_state.get("dark_mode", True))
    load_css(dark_mode=dark_mode, hide_sidebar=False)
    _inject_sidebar_css()
    _inject_sidebar_open_button_fix()

    try:
        menu_items = _menu_items()
        menu_labels = [item["label"] for item in menu_items]
        menu_icons = [item["icon"] for item in menu_items]
        allowed_routes = {item["route"] for item in menu_items}

        active_route = _normalise_selected_route(
            st.session_state.get("selected_page", "Beranda")
        )
        if active_route not in allowed_routes:
            active_route = "Beranda"
            st.session_state["selected_page"] = active_route

        active_visual = ROUTE_VISUAL_ALIASES.get(active_route, "Beranda")
        default_index = (
            menu_labels.index(active_visual) if active_visual in menu_labels else 0
        )

        # Navigasi dari tombol di dalam halaman memerlukan sinkronisasi visual
        # eksplisit. streamlit-option-menu mempertahankan state komponen sendiri,
        # sehingga default_index saja belum selalu memindahkan highlight sidebar.
        forced_route_raw = st.session_state.get("_sidebar_force_route")
        forced_route = (
            _normalise_selected_route(str(forced_route_raw))
            if forced_route_raw
            else None
        )
        if forced_route not in allowed_routes:
            forced_route = None
        forced_index = (
            menu_labels.index(ROUTE_VISUAL_ALIASES.get(forced_route, "Beranda"))
            if forced_route
            else None
        )

        # Nilai widget tidak boleh dihapus ketika berbeda dari selected_page.
        # Pada saat pengguna mengeklik menu baru, nilai widget memang berubah lebih
        # dahulu. Menghapusnya di sini akan mengembalikan pilihan ke Beranda.
        menu_widget_key = "sidebar_navigation_v2"

        with st.sidebar:
            render_sidebar_brand()
            render_sidebar_avatar()

            st.markdown(
                '<div class="sidebar-v2-section-label">MENU UTAMA</div>',
                unsafe_allow_html=True,
            )

            selected_visual = option_menu(
                menu_title=None,
                options=menu_labels,
                icons=menu_icons,
                default_index=default_index,
                manual_select=forced_index,
                key=menu_widget_key,
                on_change=_sinkronkan_pilihan_menu,
                styles={
                    "container": {
                        "padding": "0!important",
                        "margin": "0!important",
                        "background-color": "#111111!important",
                        "border": "0!important",
                        "border-radius": "0!important",
                        "box-shadow": "none!important",
                        "overflow": "hidden!important",
                    },
                    "icon": {
                        "color": "inherit",
                        "font-size": "18px",
                    },
                    "nav-link": {
                        "font-family": "DM Sans, sans-serif",
                        "font-size": "14px",
                        "font-weight": "500",
                        "text-align": "left",
                        "margin": "3px 0",
                        "padding": "10px 12px",
                        "border-radius": "8px",
                        "color": "#AAAAAA",
                        "--hover-color": "#E53935",
                        "transition": "all 0.16s ease",
                    },
                    "nav-link-selected": {
                        "background-color": "#E53935!important",
                        "color": "#FFFFFF!important",
                        "font-weight": "600",
                        "border-left": "3px solid #FF5252",
                    },
                },
            )
            _inject_option_menu_hover_fallback()

            if forced_route:
                # Pada rerun pertama setelah tombol halaman diklik, nilai komponen
                # dapat masih memuat pilihan lama. Route paksa harus menjadi sumber
                # kebenaran sampai highlight option-menu selesai diperbarui.
                selected_route = forced_route
                st.session_state.pop("_sidebar_force_route", None)
            else:
                selected_route = VISUAL_ROUTE_ALIASES.get(selected_visual, "Beranda")
                if selected_route not in allowed_routes:
                    selected_route = "Beranda"

            # Simpan route sebelum rerun berikutnya agar menu dan halaman selalu sinkron.
            st.session_state["selected_page"] = selected_route
            st.session_state["page"] = selected_route

            mode_switch_col, mode_label_col, mode_help_col = st.columns(
                [0.20, 0.66, 0.14]
            )
            with mode_switch_col:
                new_dark_mode = st.toggle(
                    "Mode Gelap",
                    value=dark_mode,
                    key="dark_mode_toggle",
                    label_visibility="collapsed",
                )
            with mode_label_col:
                st.markdown(
                    '<div class="mode-dark-label-v226">Mode Gelap</div>',
                    unsafe_allow_html=True,
                )
            with mode_help_col:
                st.markdown(
                    """
                    <div class="mode-dark-help-wrap-v215">
                        <span
                            class="mode-dark-help-v215"
                            tabindex="0"
                            aria-label="Informasi Mode Gelap"
                        >
                            ?
                            <span class="mode-dark-help-tooltip-v215">
                                Aktifkan atau nonaktifkan tampilan gelap dashboard.
                            </span>
                        </span>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )
            if new_dark_mode != dark_mode:
                st.session_state["dark_mode"] = new_dark_mode
                st.rerun()

            st.markdown(
                '<div class="sidebar-v2-footer-divider"></div>',
                unsafe_allow_html=True,
            )
            if st.button(
                "Keluar",
                type="secondary",
                use_container_width=True,
                key="sidebar_logout_v2",
            ):
                logout()

            st.markdown(
                f'<div class="sidebar-v2-version">{APP_VERSION}</div>',
                unsafe_allow_html=True,
            )

        return selected_route
    except Exception:
        st.error("Navigasi belum dapat ditampilkan.")
        return "Beranda"


def route_page(selected: str) -> None:
    """Render halaman dengan loading global hanya saat route benar-benar berubah."""
    try:
        selected_route = _normalise_selected_route(selected)
        if (
            selected_route == "Admin Panel"
            and str(st.session_state.get("role") or "").lower() != "admin"
        ):
            st.error("Halaman Admin Panel hanya dapat dibuka oleh administrator.")
            selected_route = "Beranda"
            st.session_state["selected_page"] = selected_route
            st.session_state["page"] = selected_route

        # Route ditulis ke session sebelum halaman dirender.
        st.session_state["selected_page"] = selected_route
        st.session_state["page"] = selected_route
        module_name, function_name = ROUTES.get(
            selected_route,
            ROUTES["Beranda"],
        )
        render_fn = _resolve_route_handler(module_name, function_name)
        previous_route = st.session_state.get("_last_rendered_route")
        route_changed = previous_route != selected_route

        # Widget Streamlit selalu memicu rerun. Loader global hanya diperlukan
        # saat pengguna benar-benar berpindah halaman, bukan saat menekan tombol,
        # mengganti tab, membuka expander, atau menjalankan prediksi pada route sama.
        if route_changed:
            with layar_loading(selected_route):
                render_fn()
        else:
            render_fn()

        st.session_state["_last_rendered_route"] = selected_route
    except Exception as exc:
        LOGGER.exception("Halaman %s gagal ditampilkan: %s", selected, exc)
        st.error(
            "Halaman yang dipilih belum dapat ditampilkan. "
            "Silakan muat ulang halaman atau pilih menu lain."
        )


def render_footer() -> None:
    """Tampilkan footer copyright global di bagian bawah halaman.

    Catatan:
    Halaman Tentang Penelitian sudah memiliki footer khusus berbentuk card.
    Supaya tidak muncul dua footer sekaligus, footer global disembunyikan
    khusus saat pengguna berada di menu Tentang Penelitian.
    """
    selected_page = st.session_state.get("selected_page")
    if selected_page == "Tentang Penelitian":
        return

    st.caption(FOOTER_TEXT)


def main() -> None:
    """Jalankan autentikasi, sidebar, routing, dan footer dashboard."""
    try:
        init_db()
        init_session_state()
        sync_authenticated_user_state()

        if not st.session_state.logged_in:
            load_css(
                dark_mode=st.session_state.get("dark_mode", True),
                hide_sidebar=True,
            )

            if complete_pending_remember_login():
                st.rerun()

            restore_status = try_restore_remember_login()
            if restore_status == "wait":
                if st.session_state.get("_cookie_polls", 0) < MAX_COOKIE_POLLS:
                    # Loader sudah dipasang sejak awal eksekusi aplikasi.
                    # Pertahankan loader yang sama selama pemeriksaan cookie.
                    import time

                    time.sleep(0.35)
                    st.rerun()
                st.session_state._remember_restore_done = True

            if restore_status == "ok" or st.session_state.get("logged_in"):
                st.rerun()

            render_auth_page()
            render_footer()
            _selesaikan_loading_awal()
            return

        selected = render_sidebar_menu()
        route_page(selected)
        render_footer()
        _selesaikan_loading_awal()

    except Exception as exc:
        LOGGER.exception("Aplikasi gagal dijalankan: %s", exc)
        _selesaikan_loading_awal()
        st.error(
            "Aplikasi belum dapat ditampilkan. Silakan muat ulang halaman "
            "atau hubungi administrator."
        )


if __name__ == "__main__":
    main()
