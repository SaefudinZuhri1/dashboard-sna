# app.py
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
from textwrap import dedent
from typing import Callable
import sys
import time

import streamlit as st

LOGGER = logging.getLogger(__name__)

# Pastikan import lokal (auth/, pages/, utils/) selalu dapat ditemukan,
# termasuk saat aplikasi dijalankan dari Command Prompt Windows.
PROJECT_ROOT = Path(__file__).resolve().parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from utils.error_messages import install_friendly_runtime_messages
from utils.streamlit_compat import render_html_iframe

install_friendly_runtime_messages()

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
    "dark_mode": False,
    "remembered_username": "",
    "selected_page": "Beranda",
    "active_service": "IndiHome",
    "demo_mode": False,
    "_last_rendered_route": None,
    "_startup_loading_active": True,
    "_startup_browser_overlay_installed_v3": False,
    "_public_route": "auth",
    "_database_initialized_v1": False,
}
for _session_key, _session_default in _EARLY_SESSION_DEFAULTS.items():
    if _session_key not in st.session_state:
        st.session_state[_session_key] = _session_default


def _install_persistent_startup_overlay() -> bool:
    """Pasang boot overlay langsung pada dokumen browser.

    Overlay ditempel ke ``document.body`` milik halaman induk, bukan ke tree
    elemen Streamlit. Karena itu overlay tetap berada di atas layar ketika
    Streamlit melakukan rerun awal untuk inisialisasi database, pemeriksaan
    cookie, atau pemulihan sesi.
    """
    try:
        startup_is_dark = bool(st.session_state.get("dark_mode", False))
        startup_theme_flag = "true" if startup_is_dark else "false"
        startup_overlay_html = dedent(
            r"""
                <!doctype html>
                <html lang="id">
                <head><meta charset="utf-8"></head>
                <body>
                <script>
                (() => {
                    try {
                        const doc = window.parent.document;
                        const overlayId = 'telkom-startup-boot-overlay-v2';
                        const styleId = 'telkom-startup-boot-style-v2';
                        const lightStyleId = 'telkom-startup-boot-light-style-v1';
                        const isDarkTheme = __IS_DARK_THEME__;
                        const startupPageBackground = isDarkTheme ? '#0D0D0D' : '#F7F8FA';

                        doc.documentElement.style.background = startupPageBackground;
                        if (doc.body) {
                            doc.body.style.background = startupPageBackground;
                        }

                        if (!doc.getElementById(styleId)) {
                            const style = doc.createElement('style');
                            style.id = styleId;
                            style.textContent = `
                                html, body, .stApp,
                                [data-testid="stAppViewContainer"] {
                                    background: #0D0D0D !important;
                                }
                                #${overlayId} {
                                    position: fixed;
                                    inset: 0;
                                    z-index: 2147483647;
                                    display: grid;
                                    place-items: center;
                                    overflow: hidden;
                                    background:
                                        radial-gradient(circle at 18% 18%, rgba(229,57,53,.20), transparent 34%),
                                        radial-gradient(circle at 82% 76%, rgba(56,189,248,.13), transparent 35%),
                                        linear-gradient(145deg, #0D0D0D 0%, #11131A 48%, #0B0D12 100%);
                                    opacity: 1;
                                    visibility: visible;
                                    transition: opacity .34s ease, visibility .34s ease;
                                    font-family: Inter, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
                                }
                                #${overlayId}.is-closing {
                                    opacity: 0;
                                    visibility: hidden;
                                    pointer-events: none;
                                }
                                #${overlayId} .boot-grid {
                                    position: absolute;
                                    inset: 0;
                                    opacity: .20;
                                    background-image:
                                        linear-gradient(rgba(255,255,255,.035) 1px, transparent 1px),
                                        linear-gradient(90deg, rgba(255,255,255,.035) 1px, transparent 1px);
                                    background-size: 38px 38px;
                                    mask-image: radial-gradient(circle at center, #000 18%, transparent 76%);
                                }
                                #${overlayId} .boot-card {
                                    position: relative;
                                    width: min(430px, calc(100vw - 42px));
                                    padding: 30px 30px 27px;
                                    border: 1px solid rgba(255,255,255,.12);
                                    border-radius: 28px;
                                    background: linear-gradient(145deg, rgba(24,24,31,.96), rgba(12,14,20,.96));
                                    box-shadow: 0 28px 90px rgba(0,0,0,.48), 0 0 0 1px rgba(229,57,53,.08) inset;
                                    text-align: center;
                                    isolation: isolate;
                                }
                                #${overlayId} .boot-orbit {
                                    position: relative;
                                    width: 92px;
                                    height: 92px;
                                    margin: 0 auto 20px;
                                    display: grid;
                                    place-items: center;
                                }
                                #${overlayId} .boot-orbit::before,
                                #${overlayId} .boot-orbit::after {
                                    content: "";
                                    position: absolute;
                                    border-radius: 999px;
                                    border: 2px solid transparent;
                                    will-change: transform;
                                }
                                #${overlayId} .boot-orbit::before {
                                    inset: 0;
                                    border-top-color: #E53935;
                                    border-right-color: rgba(229,57,53,.28);
                                    animation: telkomBootSpin 1.05s linear infinite;
                                }
                                #${overlayId} .boot-orbit::after {
                                    inset: 10px;
                                    border-bottom-color: #38BDF8;
                                    border-left-color: rgba(56,189,248,.25);
                                    animation: telkomBootSpinReverse 1.35s linear infinite;
                                }
                                #${overlayId} .boot-logo {
                                    width: 54px;
                                    height: 54px;
                                    display: grid;
                                    place-items: center;
                                    border-radius: 18px;
                                    color: #fff;
                                    font-size: 28px;
                                    background: linear-gradient(145deg, #E53935, #A61B45);
                                    box-shadow: 0 14px 34px rgba(229,57,53,.28);
                                }
                                #${overlayId} .boot-kicker {
                                    margin: 0 0 7px;
                                    color: #FF7774;
                                    font-size: 0.75rem /* FIX: minimum 12px agar terbaca di tablet */;
                                    font-weight: 800;
                                    letter-spacing: .18em;
                                    text-transform: uppercase;
                                }
                                #${overlayId} h2 {
                                    margin: 0;
                                    color: #F8FAFC;
                                    font-size: clamp(22px, 4vw, 30px);
                                    line-height: 1.18;
                                    letter-spacing: -.035em;
                                }
                                #${overlayId} p {
                                    margin: 11px auto 0;
                                    max-width: 340px;
                                    color: #AEB7C8;
                                    font-size: 14px;
                                    line-height: 1.65;
                                }
                                #${overlayId} .boot-progress {
                                    position: relative;
                                    height: 7px;
                                    margin-top: 22px;
                                    overflow: hidden;
                                    border-radius: 999px;
                                    background: rgba(255,255,255,.07);
                                }
                                #${overlayId} .boot-progress span {
                                    position: absolute;
                                    inset: 0 auto 0 -42%;
                                    width: 42%;
                                    border-radius: inherit;
                                    background: linear-gradient(90deg, transparent, #E53935 36%, #B85CFF 66%, #38BDF8);
                                    animation: telkomBootProgress 1.35s ease-in-out infinite;
                                    will-change: transform;
                                }
                                #${overlayId} .boot-status {
                                    display: inline-flex;
                                    align-items: center;
                                    gap: 8px;
                                    margin-top: 15px;
                                    color: #C7D0DF;
                                    font-size: 12px;
                                    font-weight: 650;
                                }
                                #${overlayId} .boot-dot {
                                    width: 8px;
                                    height: 8px;
                                    border-radius: 50%;
                                    background: #65D47B;
                                    box-shadow: 0 0 0 5px rgba(101,212,123,.10);
                                    animation: telkomBootPulse 1.2s ease-in-out infinite;
                                }
                                @keyframes telkomBootSpin { to { transform: rotate(360deg); } }
                                @keyframes telkomBootSpinReverse { to { transform: rotate(-360deg); } }
                                @keyframes telkomBootProgress {
                                    0% { transform: translateX(0); }
                                    100% { transform: translateX(340%); }
                                }
                                @keyframes telkomBootPulse {
                                    0%,100% { transform: scale(.85); opacity: .65; }
                                    50% { transform: scale(1); opacity: 1; }
                                }
                                @media (prefers-reduced-motion: reduce) {
                                    #${overlayId} *, #${overlayId} *::before, #${overlayId} *::after {
                                        animation-duration: .01ms !important;
                                        animation-iteration-count: 1 !important;
                                    }
                                }
                            `;
                            (doc.head || doc.documentElement).appendChild(style);
                        }

                        if (!isDarkTheme && !doc.getElementById(lightStyleId)) {
                            const lightStyle = doc.createElement('style');
                            lightStyle.id = lightStyleId;
                            lightStyle.textContent = `
                                html, body, .stApp,
                                [data-testid="stAppViewContainer"] {
                                    background: #F7F8FA !important;
                                }
                                #${overlayId} {
                                    background:
                                        radial-gradient(circle at 18% 18%, rgba(229,57,53,.12), transparent 34%),
                                        radial-gradient(circle at 82% 76%, rgba(29,161,242,.10), transparent 35%),
                                        linear-gradient(145deg, #F7F8FA 0%, #FFFFFF 48%, #EEF2F7 100%);
                                }
                                #${overlayId} .boot-grid {
                                    opacity: .34;
                                    background-image:
                                        linear-gradient(rgba(15,23,42,.045) 1px, transparent 1px),
                                        linear-gradient(90deg, rgba(15,23,42,.045) 1px, transparent 1px);
                                }
                                #${overlayId} .boot-card {
                                    border-color: rgba(148,163,184,.30);
                                    background: linear-gradient(145deg, rgba(255,255,255,.98), rgba(248,250,252,.98));
                                    box-shadow: 0 28px 80px rgba(15,23,42,.14), 0 0 0 1px rgba(229,57,53,.06) inset;
                                }
                                #${overlayId} h2 { color: #111827; }
                                #${overlayId} p { color: #64748B; }
                                #${overlayId} .boot-progress { background: rgba(15,23,42,.08); }
                                #${overlayId} .boot-status { color: #475569; }
                            `;
                            (doc.head || doc.documentElement).appendChild(lightStyle);
                        }

                        let overlay = doc.getElementById(overlayId);
                        if (!overlay) {
                            overlay = doc.createElement('div');
                            overlay.id = overlayId;
                            overlay.setAttribute('role', 'status');
                            overlay.setAttribute('aria-live', 'polite');
                            overlay.innerHTML = `
                                <div class="boot-grid" aria-hidden="true"></div>
                                <section class="boot-card">
                                    <div class="boot-orbit"><div class="boot-logo">◈</div></div>
                                    <div class="boot-kicker">Telkom Insight Engine</div>
                                    <h2>Menyiapkan Dashboard</h2>
                                    <p>Memeriksa database, sesi pengguna, dan komponen analitik sebelum halaman ditampilkan.</p>
                                    <div class="boot-progress" aria-hidden="true"><span></span></div>
                                    <div class="boot-status"><i class="boot-dot"></i><span>Menghubungkan sistem...</span></div>
                                </section>
                            `;
                            doc.body.appendChild(overlay);
                        } else {
                            overlay.classList.remove('is-closing');
                        }
                    } catch (error) {
                        console.debug('Startup overlay tidak dapat dipasang:', error);
                    }
                })();
                </script>
                </body>
                </html>
                """
        ).replace("__IS_DARK_THEME__", startup_theme_flag)
        render_html_iframe(
            startup_overlay_html,
            height=0,
            scrolling=False,
        )
        return True
    except Exception as exc:
        LOGGER.debug("Boot overlay browser gagal dipasang: %s", exc)
        return False


# Overlay browser cukup dipasang satu kali selama rangkaian rerun startup.
# Cookie remember-me dapat memicu beberapa rerun singkat; memasang ulang komponen
# HTML besar pada setiap putaran hanya menambah waktu tunggu tanpa mengubah UI.
_STARTUP_BROWSER_OVERLAY_INSTALLED = bool(
    st.session_state.get("_startup_browser_overlay_installed_v3", False)
)
if (
    st.session_state.get("_startup_loading_active", True)
    and not _STARTUP_BROWSER_OVERLAY_INSTALLED
):
    _STARTUP_BROWSER_OVERLAY_INSTALLED = _install_persistent_startup_overlay()
    if _STARTUP_BROWSER_OVERLAY_INSTALLED:
        st.session_state["_startup_browser_overlay_installed_v3"] = True

# Fallback hanya dipakai bila overlay browser gagal dikirim. Menjalankan dua
# loader full-screen sekaligus dapat menimbulkan pergantian visual/flicker.
from utils.loading_screen import tampilkan_loading_awal  # noqa: E402

_STARTUP_LOADING_PLACEHOLDER = None
if (
    st.session_state.get("_startup_loading_active", True)
    and not _STARTUP_BROWSER_OVERLAY_INSTALLED
):
    _STARTUP_LOADING_PLACEHOLDER = tampilkan_loading_awal()

from auth.auth_utils import get_user_by_id, init_database, revoke_remember_token  # noqa: E402
from auth.login import (  # noqa: E402
    MAX_COOKIE_POLLS,
    POST_LOGOUT_RESTORE_GUARD_KEY,
    clear_remember_cookie,
    complete_pending_remember_login,
    remove_login_transition_overlay,
    refresh_cookie_manager_for_run,
    show_login_page,
    try_restore_remember_login,
)
from utils.access_control import (  # noqa: E402
    DEFAULT_ROLE,
    can_access_route,
    get_allowed_routes,
    get_role_label,
    normalize_role,
)
from utils.css_loader import load_css  # noqa: E402
from utils.theme_manager import install_plotly_theme_adapter  # noqa: E402
from utils.app_version import get_sidebar_footer_text  # noqa: E402
from utils.loading_screen import layar_loading  # noqa: E402
from utils.audit_logger import log_activity, log_page_view_once  # noqa: E402

ASSETS_DIR = Path(__file__).resolve().parent / "assets"
DEFAULT_AVATAR = ASSETS_DIR / "default_avatar.png"
LOGO_PATH = ASSETS_DIR / "logo.png"
TELKOM_LOGO_PATH = ASSETS_DIR / "telkom_indonesia_logo.png"

FOOTER_TEXT = "© 2026 Aulia Rahmadiva Wardana · NPM 184220019 · ULBI Bandung"
APP_VERSION = "v2.0 · ULBI 2026"

LOGOUT_TRANSITION_PENDING_KEY = "_logout_transition_pending_v2"
LOGOUT_TRANSITION_STARTED_KEY = "_logout_transition_started_v2"
LOGOUT_COOKIE_DELETE_SENT_KEY = "_logout_cookie_delete_sent_v1"

# CookieManager berjalan asinkron. Biarkan komponen browser menyelesaikan
# sinkronisasi cookie secara alami; optimasi dilakukan setelah sesi ditemukan.


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


PUBLIC_ROUTES: dict[str, tuple[str, str]] = {
    "ai_content_studio": ("pages.public_content_ai", "render_public_content_ai"),
}


@lru_cache(maxsize=1)
def _resolve_option_menu_callable():
    """Impor streamlit-option-menu hanya saat sidebar dashboard dipakai."""
    try:
        from streamlit_option_menu import option_menu as option_menu_callable

        return option_menu_callable
    except Exception as exc:
        raise RuntimeError(f"Komponen menu sidebar gagal dimuat: {exc}") from exc


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
    """Tutup loader hanya setelah halaman tujuan selesai dirender.

    Boot overlay browser dipertahankan selama seluruh rerun startup dan baru
    dilepas dengan transisi halus setelah Login atau dashboard siap.
    """
    global _STARTUP_LOADING_PLACEHOLDER

    try:
        if _STARTUP_LOADING_PLACEHOLDER is not None:
            _STARTUP_LOADING_PLACEHOLDER.empty()
    except Exception:
        pass

    try:
        render_html_iframe(
            dedent(
                r"""
                <!doctype html>
                <html><body>
                <script>
                (() => {
                    try {
                        const doc = window.parent.document;
                        const overlay = doc.getElementById('telkom-startup-boot-overlay-v2');
                        if (!overlay) return;

                        // Dua frame memastikan seluruh delta Streamlit sudah masuk DOM.
                        window.parent.requestAnimationFrame(() => {
                            window.parent.requestAnimationFrame(() => {
                                window.setTimeout(() => {
                                    overlay.classList.add('is-closing');
                                    window.setTimeout(() => {
                                        overlay.remove();
                                        const style = doc.getElementById('telkom-startup-boot-style-v2');
                                        if (style) style.remove();
                                        const lightStyle = doc.getElementById('telkom-startup-boot-light-style-v1');
                                        if (lightStyle) lightStyle.remove();
                                    }, 390);
                                }, 90);
                            });
                        });
                    } catch (error) {
                        console.debug('Startup overlay tidak dapat ditutup:', error);
                    }
                })();
                </script>
                </body></html>
                """
            ),
            height=0,
            scrolling=False,
        )
    except Exception as exc:
        LOGGER.debug("Boot overlay browser gagal ditutup: %s", exc)
    finally:
        st.session_state["_startup_loading_active"] = False
        st.session_state["_startup_browser_overlay_installed_v3"] = False
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
        "dark_mode": False,
        "remembered_username": "",
        "selected_page": "Beranda",
        "active_service": "IndiHome",
        "demo_mode": False,
        "_last_rendered_route": None,
        "_startup_loading_active": True,
        "_public_route": "auth",
        "_database_initialized_v1": False,
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
            "role": normalize_role(
                user.get("role", DEFAULT_ROLE),
                user.get("user_id"),
            ),
        }
        st.session_state["user"] = public_user
        st.session_state["user_id"] = public_user["user_id"]
        st.session_state["username"] = str(public_user["username"])
        st.session_state["fullname"] = str(public_user["fullname"])
        st.session_state["role"] = str(public_user["role"])
        # Baris pengguna yang sama juga memuat avatar. Simpan di session agar
        # sidebar tidak membuka koneksi SQLite kedua pada setiap rerun halaman.
        st.session_state["_sidebar_avatar_bytes_v1"] = user.get("profile_picture")
        return True
    except Exception as exc:
        st.error(f"Sesi login tidak dapat dipulihkan: {exc}")
        st.session_state["user"] = None
        st.session_state["logged_in"] = False
        st.session_state["page"] = "login"
        st.session_state["selected_page"] = "Beranda"
        return False


def get_avatar_bytes() -> bytes | None:
    """Ambil avatar dari cache session atau file avatar default."""
    try:
        cached_avatar = st.session_state.get("_sidebar_avatar_bytes_v1")
        if cached_avatar:
            return bytes(cached_avatar)
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
                    font-size: 0.75rem /* FIX: minimum 12px agar terbaca di tablet */;
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
                    font-size: 0.75rem /* FIX: minimum 12px agar terbaca di tablet */;
                    font-weight: 500;
                }

                .sidebar-v2-section-label {
                    margin: 0.15rem 0 0.42rem 0.2rem;
                    color: #AAAAAA !important;
                    font-size: 0.75rem /* FIX: minimum 12px agar terbaca di tablet */;
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
                    font-size: 0.75rem /* FIX: minimum 12px agar terbaca di tablet */;
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
        role = normalize_role(
            st.session_state.get("role", DEFAULT_ROLE),
            st.session_state.get("user_id"),
        )
        role_label = get_role_label(role, st.session_state.get("user_id"))

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


def _logout_transition_html() -> str:
    """Bangun overlay penuh agar halaman lama tidak terlihat saat logout."""
    return dedent(
        """
        <style>
            .logout-transition-v2,
            .logout-transition-v2 * {
                box-sizing: border-box;
            }
            .logout-transition-v2 {
                position: fixed;
                inset: 0;
                z-index: 2147483647;
                width: 100vw;
                min-height: 100dvh;
                display: grid;
                place-items: center;
                overflow: hidden;
                padding: 24px;
                background:
                    radial-gradient(circle at 50% 43%, rgba(229,57,53,.20), transparent 27%),
                    linear-gradient(rgba(255,255,255,.018) 1px, transparent 1px),
                    linear-gradient(90deg, rgba(255,255,255,.018) 1px, transparent 1px),
                    #0D0D0D;
                background-size: auto, 34px 34px, 34px 34px, auto;
                animation: logout-transition-v2-in .16s ease-out both;
            }
            .logout-transition-v2::before,
            .logout-transition-v2::after {
                content: "";
                position: absolute;
                border-radius: 999px;
                filter: blur(42px);
                pointer-events: none;
            }
            .logout-transition-v2::before {
                width: 250px;
                height: 250px;
                left: -100px;
                top: 10%;
                background: rgba(229,57,53,.23);
                animation: logout-transition-v2-orb 2.5s ease-in-out infinite;
            }
            .logout-transition-v2::after {
                width: 290px;
                height: 290px;
                right: -120px;
                bottom: 7%;
                background: rgba(142,22,22,.22);
                animation: logout-transition-v2-orb 2.9s ease-in-out infinite reverse;
            }
            .logout-transition-v2-panel {
                position: relative;
                z-index: 1;
                width: min(92vw, 440px);
                min-height: 390px;
                display: flex;
                flex-direction: column;
                align-items: center;
                justify-content: center;
                padding: 42px 34px 34px;
                text-align: center;
                border: 1px solid rgba(255,255,255,.10);
                border-radius: 26px;
                background: linear-gradient(160deg, rgba(29,29,29,.97), rgba(13,13,13,.98));
                box-shadow: 0 34px 100px rgba(0,0,0,.64), 0 0 42px rgba(229,57,53,.10);
                overflow: hidden;
            }
            .logout-transition-v2-panel::before {
                content: "";
                position: absolute;
                left: 16%;
                right: 16%;
                top: 0;
                height: 2px;
                background: linear-gradient(90deg, transparent, #FF6B67, #E53935, transparent);
                box-shadow: 0 0 18px rgba(229,57,53,.75);
            }
            .logout-transition-v2-visual {
                position: relative;
                width: 146px;
                height: 146px;
                margin-bottom: 24px;
            }
            .logout-transition-v2-ring {
                position: absolute;
                border-radius: 50%;
                border: 1px solid rgba(255,255,255,.15);
                animation: logout-transition-v2-spin 2.05s linear infinite;
            }
            .logout-transition-v2-ring::after {
                content: "";
                position: absolute;
                left: 50%;
                top: -7px;
                width: 14px;
                height: 14px;
                transform: translateX(-50%);
                border: 3px solid #111111;
                border-radius: 50%;
                background: #E53935;
                box-shadow: 0 0 18px rgba(229,57,53,.82);
            }
            .logout-transition-v2-ring.one { inset: 4px; }
            .logout-transition-v2-ring.two {
                inset: 21px;
                border-color: rgba(229,57,53,.30);
                animation-duration: 2.85s;
                animation-direction: reverse;
            }
            .logout-transition-v2-ring.two::after {
                width: 11px;
                height: 11px;
                top: -6px;
                background: #FF8A80;
            }
            .logout-transition-v2-ring.three {
                inset: 37px;
                border-color: rgba(255,255,255,.10);
                animation-duration: 1.45s;
            }
            .logout-transition-v2-ring.three::after {
                width: 8px;
                height: 8px;
                top: -4px;
                border-width: 2px;
                background: #FFFFFF;
                box-shadow: 0 0 12px rgba(255,255,255,.62);
            }
            .logout-transition-v2-core {
                position: absolute;
                left: 50%;
                top: 50%;
                width: 58px;
                height: 58px;
                display: grid;
                place-items: center;
                transform: translate(-50%, -50%);
                border: 1px solid rgba(255,255,255,.20);
                border-radius: 19px;
                color: #FFFFFF;
                background: linear-gradient(145deg, #E53935, #9F1515);
                box-shadow: 0 16px 38px rgba(183,28,28,.38), 0 0 26px rgba(229,57,53,.30);
                font: 800 1.55rem/1 "DM Sans", sans-serif;
                animation: logout-transition-v2-pulse 1.25s ease-in-out infinite;
            }
            .logout-transition-v2-title {
                margin: 0;
                color: #FFFFFF;
                font: 800 clamp(1.28rem, 2.4vw, 1.58rem)/1.25 "Syne", "DM Sans", sans-serif;
                letter-spacing: -.025em;
            }
            .logout-transition-v2-copy {
                margin: 10px 0 0;
                color: #AFAFAF;
                font: 500 .92rem/1.55 "DM Sans", sans-serif;
            }
            .logout-transition-v2-progress {
                width: min(72vw, 286px);
                height: 6px;
                margin-top: 22px;
                overflow: hidden;
                border: 1px solid #303030;
                border-radius: 999px;
                background: #242424;
            }
            .logout-transition-v2-progress::after {
                content: "";
                display: block;
                width: 46%;
                height: 100%;
                border-radius: inherit;
                background: linear-gradient(90deg, #8E1616, #E53935, #FF8A80);
                box-shadow: 0 0 16px rgba(229,57,53,.44);
                animation: logout-transition-v2-progress 1.05s cubic-bezier(.4,0,.2,1) infinite;
            }
            .logout-transition-v2-status {
                display: inline-flex;
                align-items: center;
                gap: 7px;
                margin-top: 18px;
                color: #777777;
                font: 700 .68rem/1 "DM Sans", sans-serif;
                letter-spacing: .12em;
                text-transform: uppercase;
            }
            .logout-transition-v2-status::before {
                content: "";
                width: 7px;
                height: 7px;
                border-radius: 50%;
                background: #66BB6A;
                box-shadow: 0 0 0 0 rgba(102,187,106,.5);
                animation: logout-transition-v2-dot 1.35s ease-out infinite;
            }
            @keyframes logout-transition-v2-in {
                from { opacity: 0; }
                to { opacity: 1; }
            }
            @keyframes logout-transition-v2-spin {
                to { transform: rotate(360deg); }
            }
            @keyframes logout-transition-v2-pulse {
                0%, 100% { transform: translate(-50%, -50%) scale(.96); }
                50% { transform: translate(-50%, -50%) scale(1.05); }
            }
            @keyframes logout-transition-v2-progress {
                0% { transform: translateX(-120%); }
                60% { transform: translateX(125%); }
                100% { transform: translateX(250%); }
            }
            @keyframes logout-transition-v2-orb {
                0%, 100% { transform: scale(.92); opacity: .45; }
                50% { transform: scale(1.09); opacity: .85; }
            }
            @keyframes logout-transition-v2-dot {
                0% { box-shadow: 0 0 0 0 rgba(102,187,106,.45); }
                80%, 100% { box-shadow: 0 0 0 8px rgba(102,187,106,0); }
            }
            @media (max-width: 520px) {
                .logout-transition-v2-panel { min-height: 360px; padding: 36px 22px 30px; }
                .logout-transition-v2-visual { width: 128px; height: 128px; }
            }
            @media (prefers-reduced-motion: reduce) {
                .logout-transition-v2-ring,
                .logout-transition-v2-core,
                .logout-transition-v2-progress::after,
                .logout-transition-v2::before,
                .logout-transition-v2::after,
                .logout-transition-v2-status::before {
                    animation-duration: 4s !important;
                }
            }
        </style>
        <section class="logout-transition-v2" role="status" aria-live="assertive">
            <div class="logout-transition-v2-panel">
                <div class="logout-transition-v2-visual" aria-hidden="true">
                    <span class="logout-transition-v2-ring one"></span>
                    <span class="logout-transition-v2-ring two"></span>
                    <span class="logout-transition-v2-ring three"></span>
                    <span class="logout-transition-v2-core">↪</span>
                </div>
                <h2 class="logout-transition-v2-title">Mengakhiri Sesi</h2>
                <p class="logout-transition-v2-copy">Menyimpan catatan aktivitas dan menyiapkan halaman masuk.</p>
                <div class="logout-transition-v2-progress" aria-hidden="true"></div>
                <div class="logout-transition-v2-status">Logout aman sedang diproses</div>
            </div>
        </section>
        """
    ).strip()


def _install_logout_click_overlay() -> None:
    """Pasang overlay di browser tepat ketika tombol konfirmasi ditekan."""
    try:
        overlay_html = _logout_transition_html().replace("`", "\\`")
        render_html_iframe(
            dedent(
                f"""
                <!doctype html>
                <html>
                <body>
                <script>
                    (() => {{
                        const parentDocument = window.parent.document;
                        const overlayId = 'logout-transition-client-v2';
                        const styleId = 'logout-transition-client-style-v2';

                        const mountOverlay = () => {{
                            const oldOverlay = parentDocument.getElementById(overlayId);
                            if (oldOverlay) oldOverlay.remove();
                            const oldStyle = parentDocument.getElementById(styleId);
                            if (oldStyle) oldStyle.remove();

                            const holder = parentDocument.createElement('div');
                            holder.id = overlayId;
                            holder.innerHTML = `{overlay_html}`;
                            parentDocument.body.appendChild(holder);

                            const overlay = holder.querySelector('.logout-transition-v2');
                            if (overlay) {{
                                overlay.style.animation = 'logout-transition-v2-in .12s ease-out both, logout-transition-v2-safety-hide .25s ease 7s forwards';
                            }}

                            const safetyStyle = parentDocument.createElement('style');
                            safetyStyle.id = styleId;
                            safetyStyle.textContent = `
                                @keyframes logout-transition-v2-safety-hide {{
                                    to {{ opacity: 0; visibility: hidden; pointer-events: none; }}
                                }}
                            `;
                            parentDocument.head.appendChild(safetyStyle);
                        }};

                        const bindButton = () => {{
                            const button = parentDocument.querySelector('.st-key-logout_confirm_v1 button');
                            if (!button || button.dataset.logoutOverlayV2 === '1') return;
                            button.dataset.logoutOverlayV2 = '1';
                            button.addEventListener('pointerdown', mountOverlay, true);
                            button.addEventListener('click', mountOverlay, true);
                        }};

                        bindButton();
                        const observerKey = '__telkomLogoutOverlayObserverV3';
                        const oldObserver = window.parent[observerKey];
                        if (oldObserver && typeof oldObserver.disconnect === 'function') {{
                            oldObserver.disconnect();
                        }}
                        const observer = new MutationObserver(bindButton);
                        observer.observe(parentDocument.body, {{ childList: true, subtree: true }});
                        window.parent[observerKey] = observer;
                    }})();
                </script>
                </body>
                </html>
                """
            ),
            height=0,
            scrolling=False,
        )
    except Exception:
        LOGGER.exception("Overlay klik logout gagal dipasang")


def _remove_client_logout_overlay() -> None:
    """Hapus overlay DOM tambahan setelah halaman masuk selesai dirender."""
    try:
        render_html_iframe(
            """
            <script>
                (() => {
                    try {
                        const doc = window.parent.document;
                        const overlay = doc.getElementById('logout-transition-client-v2');
                        const style = doc.getElementById('logout-transition-client-style-v2');
                        if (overlay) overlay.remove();
                        if (style) style.remove();
                    } catch (error) {}
                })();
            </script>
            """,
            height=0,
            scrolling=False,
        )
    except Exception:
        pass


def logout() -> None:
    """Mulai transisi logout tanpa merender ulang halaman aktif."""
    try:
        st.session_state[LOGOUT_TRANSITION_PENDING_KEY] = True
        st.session_state[LOGOUT_TRANSITION_STARTED_KEY] = time.time()
        st.session_state["_startup_loading_active"] = True
        st.rerun()
    except Exception as exc:
        LOGGER.exception("Transisi logout gagal dimulai: %s", exc)
        st.error("Logout belum berhasil dimulai. Silakan coba kembali.")


def _process_pending_logout() -> bool:
    """Selesaikan logout dalam rerun khusus yang hanya menampilkan loader."""
    if not bool(st.session_state.get(LOGOUT_TRANSITION_PENDING_KEY, False)):
        return False

    placeholder = st.empty()
    try:
        placeholder.markdown(
            _logout_transition_html(),
            unsafe_allow_html=True,
        )

        # Beri browser kesempatan menampilkan overlay sebelum session dibersihkan.
        time.sleep(0.65)

        log_activity(
            "LOGOUT",
            "Autentikasi",
            "Pengguna keluar dari dashboard.",
            metadata={"page_terakhir": st.session_state.get("selected_page")},
        )
        token = st.session_state.get("active_remember_token")
        if token:
            revoke_remember_token(token)

        # CookieManager adalah komponen browser asinkron. Tandai permintaan
        # penghapusan sebelum memanggilnya agar rerun komponen tidak mengirim
        # perintah hapus berulang kali.
        if not st.session_state.get(LOGOUT_COOKIE_DELETE_SENT_KEY, False):
            st.session_state[LOGOUT_COOKIE_DELETE_SENT_KEY] = True
            clear_remember_cookie()

        st.session_state.clear()
        # Sesudah logout, pertahankan overlay logout yang sudah tampil dan
        # langsung render halaman login. Jangan memasang loader startup kedua.
        st.session_state["_startup_loading_active"] = False
        st.session_state["_logout_just_completed_v2"] = True
        st.session_state[POST_LOGOUT_RESTORE_GUARD_KEY] = True
        st.session_state["_remember_restore_done"] = True
        st.session_state["_cookie_polls"] = MAX_COOKIE_POLLS
        st.session_state["page"] = "login"
        st.session_state["_public_route"] = "auth"
        st.rerun()
        return True
    except Exception as exc:
        LOGGER.exception("Logout gagal diselesaikan: %s", exc)
        try:
            st.session_state.pop(LOGOUT_TRANSITION_PENDING_KEY, None)
            st.session_state.pop(LOGOUT_TRANSITION_STARTED_KEY, None)
        except Exception:
            pass
        log_activity(
            "LOGOUT",
            "Autentikasi",
            "Percobaan logout gagal.",
            status="failed",
            metadata={"error": str(exc)},
        )
        placeholder.empty()
        st.error("Logout belum berhasil. Silakan coba kembali.")
        return True


def _logout_confirmation_body() -> None:
    """Tampilkan isi popup konfirmasi sebelum sesi pengguna diakhiri."""
    try:
        fullname_raw = str(st.session_state.get("fullname") or "Pengguna")
        username_raw = str(st.session_state.get("username") or "-")
        user_id_raw = st.session_state.get("user_id")
        role = normalize_role(
            st.session_state.get("role", DEFAULT_ROLE),
            user_id_raw,
        )
        role_label = get_role_label(role, user_id_raw)

        fullname_safe = escape(fullname_raw)
        username_safe = escape(username_raw)
        role_safe = escape(str(role_label))
        initials_safe = escape(_get_user_initials(fullname_raw))

        avatar_uri = _bytes_data_uri(get_avatar_bytes())
        if avatar_uri:
            avatar_html = (
                f'<img class="logout-confirm-v1-avatar" src="{avatar_uri}" '
                'alt="Foto profil pengguna">'
            )
        else:
            avatar_html = (
                f'<div class="logout-confirm-v1-initials">{initials_safe}</div>'
            )

        st.markdown(
            """
            <style>
                div[data-testid="stDialog"] > div[role="dialog"] {
                    width: min(92vw, 520px) !important;
                    max-width: 520px !important;
                    padding: 0.35rem 0.35rem 0.65rem !important;
                    overflow: hidden !important;
                    background:
                        radial-gradient(circle at 12% 0%, rgba(229,57,53,.18), transparent 34%),
                        linear-gradient(145deg, #181818 0%, #101010 100%) !important;
                    border: 1px solid rgba(255,255,255,.10) !important;
                    border-radius: 22px !important;
                    box-shadow: 0 28px 80px rgba(0,0,0,.62), 0 0 0 1px rgba(229,57,53,.08) !important;
                }
                div[data-testid="stDialog"] [data-testid="stDialogHeader"] {
                    padding-bottom: 0.1rem !important;
                }
                div[data-testid="stDialog"] [data-testid="stDialogHeader"] h2 {
                    font-family: "Syne", "DM Sans", sans-serif !important;
                    font-size: 1.22rem !important;
                    font-weight: 750 !important;
                    color: #FFFFFF !important;
                }
                .logout-confirm-v1-shell {
                    position: relative;
                    overflow: hidden;
                    padding: 1.05rem 1.05rem 0.95rem;
                    background: linear-gradient(145deg, rgba(255,255,255,.045), rgba(255,255,255,.018));
                    border: 1px solid rgba(255,255,255,.08);
                    border-radius: 17px;
                }
                .logout-confirm-v1-shell::before {
                    content: "";
                    position: absolute;
                    inset: 0 auto 0 0;
                    width: 4px;
                    background: linear-gradient(180deg, #FF6B6B, #E53935, #8E1616);
                    box-shadow: 0 0 18px rgba(229,57,53,.65);
                }
                .logout-confirm-v1-hero {
                    display: flex;
                    gap: .9rem;
                    align-items: center;
                    margin-bottom: .9rem;
                }
                .logout-confirm-v1-icon {
                    width: 52px;
                    height: 52px;
                    flex: 0 0 52px;
                    display: grid;
                    place-items: center;
                    border-radius: 16px;
                    background: linear-gradient(145deg, rgba(229,57,53,.30), rgba(229,57,53,.10));
                    border: 1px solid rgba(255,107,107,.35);
                    box-shadow: 0 12px 28px rgba(229,57,53,.20);
                    font-size: 1.5rem;
                    animation: logoutConfirmPulseV1 2.2s ease-in-out infinite;
                }
                .logout-confirm-v1-copy h3 {
                    margin: 0 0 .25rem;
                    font-family: "Syne", "DM Sans", sans-serif;
                    font-size: 1.12rem;
                    line-height: 1.25;
                    color: #FFFFFF;
                }
                .logout-confirm-v1-copy p {
                    margin: 0;
                    color: #BDBDBD;
                    font-family: "DM Sans", sans-serif;
                    font-size: .86rem;
                    line-height: 1.55;
                }
                .logout-confirm-v1-user {
                    display: flex;
                    align-items: center;
                    gap: .75rem;
                    margin: .75rem 0;
                    padding: .72rem .78rem;
                    background: rgba(0,0,0,.24);
                    border: 1px solid rgba(255,255,255,.075);
                    border-radius: 14px;
                }
                .logout-confirm-v1-avatar,
                .logout-confirm-v1-initials {
                    width: 44px;
                    height: 44px;
                    flex: 0 0 44px;
                    border-radius: 13px;
                    object-fit: cover;
                    border: 1px solid rgba(255,255,255,.15);
                    box-shadow: 0 7px 20px rgba(0,0,0,.30);
                }
                .logout-confirm-v1-initials {
                    display: grid;
                    place-items: center;
                    background: linear-gradient(145deg, #E53935, #8E1616);
                    color: #FFFFFF;
                    font-family: "Syne", sans-serif;
                    font-size: .84rem;
                    font-weight: 800;
                }
                .logout-confirm-v1-user-name {
                    color: #FFFFFF;
                    font-family: "DM Sans", sans-serif;
                    font-size: .91rem;
                    font-weight: 700;
                    line-height: 1.25;
                }
                .logout-confirm-v1-user-meta {
                    margin-top: .18rem;
                    color: #8F8F8F;
                    font-family: "DM Sans", sans-serif;
                    font-size: .75rem;
                }
                .logout-confirm-v1-role {
                    margin-left: auto;
                    padding: .30rem .56rem;
                    color: #FFB4B4;
                    background: rgba(229,57,53,.12);
                    border: 1px solid rgba(229,57,53,.25);
                    border-radius: 999px;
                    font-family: "DM Sans", sans-serif;
                    font-size: 0.75rem /* FIX: minimum 12px agar terbaca di tablet */;
                    font-weight: 700;
                    white-space: nowrap;
                }
                .logout-confirm-v1-note {
                    display: flex;
                    gap: .55rem;
                    align-items: flex-start;
                    padding: .66rem .72rem;
                    color: #CBCBCB;
                    background: rgba(255,193,7,.065);
                    border: 1px solid rgba(255,193,7,.18);
                    border-radius: 12px;
                    font-family: "DM Sans", sans-serif;
                    font-size: .77rem;
                    line-height: 1.48;
                }
                .logout-confirm-v1-note strong { color: #FFE082; }
                div[data-testid="stDialog"] .st-key-logout_cancel_v1 button,
                div[data-testid="stDialog"] .st-key-logout_confirm_v1 button {
                    min-height: 44px !important;
                    border-radius: 12px !important;
                    font-family: "DM Sans", sans-serif !important;
                    font-weight: 750 !important;
                    transition: transform .16s ease, box-shadow .16s ease, border-color .16s ease !important;
                }
                div[data-testid="stDialog"] .st-key-logout_cancel_v1 button {
                    color: #E5E5E5 !important;
                    background: rgba(255,255,255,.055) !important;
                    border: 1px solid rgba(255,255,255,.12) !important;
                }
                div[data-testid="stDialog"] .st-key-logout_confirm_v1 button {
                    color: #FFFFFF !important;
                    background: linear-gradient(135deg, #E53935, #B71C1C) !important;
                    border: 1px solid #F05252 !important;
                    box-shadow: 0 10px 24px rgba(229,57,53,.22) !important;
                }
                div[data-testid="stDialog"] .st-key-logout_cancel_v1 button:hover,
                div[data-testid="stDialog"] .st-key-logout_confirm_v1 button:hover {
                    transform: translateY(-2px) !important;
                }
                div[data-testid="stDialog"] .st-key-logout_confirm_v1 button:hover {
                    box-shadow: 0 14px 30px rgba(229,57,53,.34) !important;
                }
                @keyframes logoutConfirmPulseV1 {
                    0%, 100% { transform: scale(1); box-shadow: 0 12px 28px rgba(229,57,53,.18); }
                    50% { transform: scale(1.04); box-shadow: 0 14px 34px rgba(229,57,53,.32); }
                }
                @media (max-width: 520px) {
                    .logout-confirm-v1-role { display: none; }
                    .logout-confirm-v1-shell { padding: .9rem .85rem .82rem; }
                }
            </style>
            """,
            unsafe_allow_html=True,
        )

        st.markdown(
            f"""
            <div class="logout-confirm-v1-shell">
                <div class="logout-confirm-v1-hero">
                    <div class="logout-confirm-v1-icon">↪</div>
                    <div class="logout-confirm-v1-copy">
                        <h3>Yakin ingin keluar dari dashboard?</h3>
                        <p>Konfirmasi diperlukan agar sesi tidak berakhir karena salah klik.</p>
                    </div>
                </div>
                <div class="logout-confirm-v1-user">
                    {avatar_html}
                    <div>
                        <div class="logout-confirm-v1-user-name">{fullname_safe}</div>
                        <div class="logout-confirm-v1-user-meta">@{username_safe}</div>
                    </div>
                    <div class="logout-confirm-v1-role">{role_safe}</div>
                </div>
                <div class="logout-confirm-v1-note">
                    <span>⚠</span>
                    <span><strong>Sesi akun akan diakhiri.</strong> Pilihan halaman, filter, dan data sementara dalam sesi ini akan direset. Anda perlu login kembali untuk membuka dashboard.</span>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        _install_logout_click_overlay()

        cancel_col, confirm_col = st.columns(2, gap="small")
        with cancel_col:
            if st.button(
                "Batal",
                use_container_width=True,
                key="logout_cancel_v1",
            ):
                st.rerun()
        with confirm_col:
            if st.button(
                "Ya, Keluar",
                type="primary",
                use_container_width=True,
                key="logout_confirm_v1",
            ):
                logout()
    except Exception as exc:
        st.error(f"Konfirmasi keluar belum dapat ditampilkan: {exc}")


# Gunakan dialog native Streamlit. Fallback dipertahankan agar aplikasi tetap
# dapat dibuka pada versi Streamlit lama, walaupun tampilan akan menjadi inline.
if hasattr(st, "dialog"):
    show_logout_confirmation = st.dialog("Konfirmasi Keluar")(
        _logout_confirmation_body
    )
else:
    show_logout_confirmation = _logout_confirmation_body


def _open_public_ai_content_studio() -> None:
    """Arahkan pengguna umum ke AI Content Studio dengan transisi kustom."""
    st.session_state["_public_route"] = "ai_content_studio"
    st.session_state["page"] = "login"
    st.session_state["_public_route_loading_pending"] = True


def render_auth_page() -> None:
    """Tampilkan autentikasi atau route publik tanpa membuat sesi login palsu."""
    try:
        public_route = str(st.session_state.get("_public_route") or "auth")
        if public_route in PUBLIC_ROUTES:
            module_name, function_name = PUBLIC_ROUTES[public_route]
            handler = _resolve_route_handler(module_name, function_name)
            handler()
            return

        # Pemeriksaan sesi sudah memakai loading awal. Halaman login/register
        # dirender langsung agar tidak muncul dua overlay secara berurutan.
        if st.session_state.get("page") == "register":
            # Form registrasi tidak dibutuhkan pada cold-start halaman Login.
            # Import ditunda sampai pengguna benar-benar membuka Register.
            from auth.register import show_register_page

            show_register_page()
        else:
            show_login_page()

        _, public_entry_column, _ = st.columns([1.05, 2.2, 1.05])
        with public_entry_column:
            st.markdown(
                dedent(
                    r"""
                <style>
                /* Saat route publik berpindah, indikator bawaan Streamlit disembunyikan.
                   Overlay Telkom dari utils/loading_screen.py menjadi satu-satunya loader. */
                [data-testid="stSpinner"],
                [data-testid="stStatusWidget"] {
                    display: none !important;
                    visibility: hidden !important;
                }

                /* ==========================================================
                   AI CONTENT STUDIO PUBLIC TEASER v1.1
                   CSS sengaja di-scope agar tidak memengaruhi form login lain.
                   ========================================================== */
                .public-ai-teaser-v11 {
                    --pa-red: #E53935;
                    --pa-red-soft: rgba(229, 57, 53, 0.24);
                    --pa-purple: #8B5CF6;
                    --pa-blue: #38BDF8;
                    position: relative;
                    isolation: isolate;
                    overflow: hidden;
                    margin: 16px auto 10px;
                    padding: 1.2rem 1.25rem 1.15rem;
                    border: 1px solid transparent;
                    border-radius: 22px;
                    background:
                        linear-gradient(145deg, rgba(24, 17, 22, 0.96), rgba(13, 16, 25, 0.97)) padding-box,
                        linear-gradient(115deg,
                            rgba(229, 57, 53, 0.78),
                            rgba(139, 92, 246, 0.35),
                            rgba(56, 189, 248, 0.38),
                            rgba(229, 57, 53, 0.78)) border-box;
                    background-size: 100% 100%, 280% 280%;
                    box-shadow:
                        0 18px 45px rgba(0, 0, 0, 0.35),
                        0 0 0 1px rgba(255, 255, 255, 0.025) inset,
                        0 0 34px rgba(229, 57, 53, 0.08);
                    transform: translateZ(0);
                    animation:
                        publicAiCardEnter .72s cubic-bezier(.22, 1, .36, 1) both,
                        publicAiBorderFlow 8s ease-in-out infinite;
                    transition:
                        transform .34s cubic-bezier(.22, 1, .36, 1),
                        box-shadow .34s ease,
                        border-color .34s ease;
                }

                .public-ai-teaser-v11::before {
                    content: "";
                    position: absolute;
                    z-index: -2;
                    width: 250px;
                    height: 250px;
                    top: -155px;
                    right: -75px;
                    border-radius: 999px;
                    background: radial-gradient(circle,
                        rgba(229, 57, 53, 0.32) 0%,
                        rgba(139, 92, 246, 0.14) 38%,
                        transparent 72%);
                    filter: blur(6px);
                    animation: publicAiOrbFloat 7s ease-in-out infinite;
                    pointer-events: none;
                }

                .public-ai-teaser-v11::after {
                    content: "";
                    position: absolute;
                    z-index: -1;
                    inset: -70% -45%;
                    background: linear-gradient(105deg,
                        transparent 40%,
                        rgba(255, 255, 255, 0.065) 48%,
                        rgba(255, 255, 255, 0.12) 50%,
                        rgba(255, 255, 255, 0.065) 52%,
                        transparent 60%);
                    transform: translateX(-48%) rotate(4deg);
                    animation: publicAiShimmer 7.5s ease-in-out infinite;
                    pointer-events: none;
                }

                .public-ai-teaser-v11:hover {
                    transform: translateY(-5px) scale(1.008);
                    box-shadow:
                        0 24px 58px rgba(0, 0, 0, 0.46),
                        0 0 0 1px rgba(255, 255, 255, 0.045) inset,
                        0 0 42px rgba(229, 57, 53, 0.18),
                        0 0 64px rgba(139, 92, 246, 0.08);
                }

                .public-ai-teaser-v11:hover::before {
                    animation-duration: 3.8s;
                }

                .public-ai-teaser-v11__topline {
                    display: flex;
                    align-items: center;
                    justify-content: space-between;
                    gap: .75rem;
                    margin-bottom: .9rem;
                }

                .public-ai-teaser-v11__badges {
                    display: flex;
                    flex-wrap: wrap;
                    align-items: center;
                    gap: .45rem;
                }

                .public-ai-teaser-v11__badge {
                    display: inline-flex;
                    align-items: center;
                    gap: .36rem;
                    min-height: 25px;
                    padding: .28rem .58rem;
                    border: 1px solid rgba(255, 255, 255, 0.1);
                    border-radius: 999px;
                    background: rgba(255, 255, 255, 0.055);
                    color: rgba(255, 255, 255, 0.78);
                    font-size: 0.75rem /* FIX: minimum 12px agar terbaca di tablet */;
                    font-weight: 750;
                    letter-spacing: .055em;
                    text-transform: uppercase;
                    backdrop-filter: blur(10px);
                    -webkit-backdrop-filter: blur(10px);
                    opacity: 0;
                    transform: translateY(7px);
                    animation: publicAiBadgeEnter .5s ease forwards;
                    transition:
                        transform .24s ease,
                        background .24s ease,
                        border-color .24s ease,
                        color .24s ease,
                        box-shadow .24s ease;
                }

                .public-ai-teaser-v11__badge:nth-child(1) { animation-delay: .16s; }
                .public-ai-teaser-v11__badge:nth-child(2) { animation-delay: .24s; }
                .public-ai-teaser-v11__badge:nth-child(3) { animation-delay: .32s; }

                .public-ai-teaser-v11__badge:hover {
                    color: #FFFFFF;
                    background: rgba(229, 57, 53, 0.13);
                    border-color: rgba(229, 57, 53, 0.32);
                    box-shadow: 0 0 18px rgba(229, 57, 53, 0.14);
                    transform: translateY(-2px);
                }

                .public-ai-teaser-v11__badge-dot {
                    width: 6px;
                    height: 6px;
                    flex: 0 0 6px;
                    border-radius: 50%;
                    background: #FF665F;
                    box-shadow: 0 0 0 0 rgba(255, 102, 95, .5);
                    animation: publicAiDotPulse 2.15s ease-out infinite;
                }

                .public-ai-teaser-v11__spark {
                    display: grid;
                    place-items: center;
                    width: 34px;
                    height: 34px;
                    flex: 0 0 34px;
                    border: 1px solid rgba(255, 255, 255, 0.1);
                    border-radius: 12px;
                    background: linear-gradient(145deg,
                        rgba(229, 57, 53, 0.16),
                        rgba(139, 92, 246, 0.12));
                    color: #FFFFFF;
                    font-size: 1rem;
                    box-shadow:
                        0 8px 24px rgba(0, 0, 0, .18),
                        0 0 20px rgba(229, 57, 53, .09);
                    animation:
                        publicAiSparkEnter .62s .28s cubic-bezier(.22,1,.36,1) both,
                        publicAiSparkFloat 3.2s 1s ease-in-out infinite;
                    transition: transform .28s ease, box-shadow .28s ease;
                }

                .public-ai-teaser-v11:hover .public-ai-teaser-v11__spark {
                    transform: translateY(-2px) rotate(8deg) scale(1.06);
                    box-shadow:
                        0 12px 28px rgba(0, 0, 0, .22),
                        0 0 24px rgba(229, 57, 53, .22);
                }

                .public-ai-teaser-v11__title {
                    max-width: 690px;
                    margin: 0;
                    color: #FFFFFF;
                    font-size: clamp(1.02rem, 2vw, 1.28rem);
                    font-weight: 850;
                    line-height: 1.28;
                    letter-spacing: -.018em;
                    text-wrap: balance;
                    opacity: 0;
                    transform: translateY(12px);
                    filter: blur(4px);
                    animation: publicAiTextReveal .64s .22s cubic-bezier(.22,1,.36,1) forwards;
                }

                .public-ai-teaser-v11__title-accent {
                    background: linear-gradient(90deg, #FFFFFF 10%, #FFB0AC 50%, #D8C4FF 82%, #FFFFFF 100%);
                    background-size: 220% auto;
                    -webkit-background-clip: text;
                    background-clip: text;
                    color: transparent;
                    animation: publicAiTitleGradient 5.8s ease-in-out infinite;
                }

                .public-ai-teaser-v11__description {
                    max-width: 680px;
                    margin: .55rem 0 0;
                    color: rgba(255, 255, 255, .65);
                    font-size: .86rem;
                    line-height: 1.62;
                    opacity: 0;
                    transform: translateY(10px);
                    animation: publicAiTextReveal .62s .34s cubic-bezier(.22,1,.36,1) forwards;
                }

                .public-ai-teaser-v11__description strong {
                    color: rgba(255, 255, 255, .9);
                    font-weight: 720;
                }

                .public-ai-teaser-v11__meta {
                    display: flex;
                    flex-wrap: wrap;
                    gap: .52rem 1rem;
                    margin-top: .85rem;
                    color: rgba(255, 255, 255, .48);
                    font-size: 0.75rem /* FIX: minimum 12px agar terbaca di tablet */;
                    opacity: 0;
                    transform: translateY(8px);
                    animation: publicAiTextReveal .58s .46s cubic-bezier(.22,1,.36,1) forwards;
                }

                .public-ai-teaser-v11__meta-item {
                    display: inline-flex;
                    align-items: center;
                    gap: .38rem;
                    transition: color .22s ease, transform .22s ease;
                }

                .public-ai-teaser-v11__meta-item::before {
                    content: "✓";
                    display: grid;
                    place-items: center;
                    width: 15px;
                    height: 15px;
                    border-radius: 50%;
                    background: rgba(229, 57, 53, .13);
                    color: #FF837D;
                    font-size: 0.75rem /* FIX: minimum 12px agar terbaca di tablet */;
                    font-weight: 900;
                    transition: transform .22s ease, background .22s ease;
                }

                .public-ai-teaser-v11__meta-item:hover {
                    color: rgba(255, 255, 255, .78);
                    transform: translateX(2px);
                }

                .public-ai-teaser-v11__meta-item:hover::before {
                    transform: scale(1.12) rotate(-6deg);
                    background: rgba(229, 57, 53, .23);
                }

                /* Tombol Streamlit dengan key khusus. Scope ini tidak menyentuh tombol login. */
                .st-key-open_public_ai_content_studio {
                    position: relative;
                    margin-top: .08rem;
                    opacity: 0;
                    transform: translateY(10px);
                    animation: publicAiCtaEnter .62s .48s cubic-bezier(.22,1,.36,1) forwards;
                }

                .st-key-open_public_ai_content_studio button {
                    position: relative;
                    isolation: isolate;
                    overflow: hidden;
                    min-height: 54px;
                    width: 100%;
                    border: 1px solid rgba(255, 255, 255, .13) !important;
                    border-radius: 16px !important;
                    background:
                        linear-gradient(100deg,
                            #B91C1C 0%,
                            #E53935 27%,
                            #7C3AED 67%,
                            #C62828 100%) !important;
                    background-size: 230% 100% !important;
                    color: #FFFFFF !important;
                    box-shadow:
                        0 14px 34px rgba(159, 22, 22, .28),
                        0 0 0 1px rgba(255, 255, 255, .045) inset !important;
                    font-weight: 820 !important;
                    letter-spacing: -.008em;
                    transform: translateZ(0);
                    animation: publicAiButtonGradient 6s ease-in-out infinite;
                    transition:
                        transform .26s cubic-bezier(.22,1,.36,1),
                        box-shadow .26s ease,
                        filter .26s ease,
                        border-color .26s ease !important;
                }

                .st-key-open_public_ai_content_studio button::before {
                    content: "";
                    position: absolute;
                    z-index: -1;
                    top: -60%;
                    left: -42%;
                    width: 34%;
                    height: 220%;
                    transform: rotate(18deg);
                    background: linear-gradient(90deg,
                        transparent,
                        rgba(255, 255, 255, .46),
                        transparent);
                    animation: publicAiButtonShine 4.4s ease-in-out infinite;
                    pointer-events: none;
                }

                .st-key-open_public_ai_content_studio button::after {
                    content: "→";
                    position: absolute;
                    right: 1.1rem;
                    top: 50%;
                    transform: translateY(-50%);
                    color: rgba(255, 255, 255, .78);
                    font-size: 1.08rem;
                    transition: transform .25s ease, color .25s ease;
                    pointer-events: none;
                }

                .st-key-open_public_ai_content_studio button p,
                .st-key-open_public_ai_content_studio button span,
                .st-key-open_public_ai_content_studio button [data-testid="stMarkdownContainer"] {
                    color: #FFFFFF !important;
                    font-weight: 820 !important;
                }

                .st-key-open_public_ai_content_studio button:hover {
                    transform: translateY(-4px) scale(1.012);
                    border-color: rgba(255, 255, 255, .28) !important;
                    filter: saturate(1.12) brightness(1.05);
                    box-shadow:
                        0 19px 42px rgba(176, 28, 28, .38),
                        0 0 30px rgba(229, 57, 53, .24),
                        0 0 48px rgba(124, 58, 237, .14),
                        0 0 0 1px rgba(255, 255, 255, .08) inset !important;
                }

                .st-key-open_public_ai_content_studio button:hover::after {
                    color: #FFFFFF;
                    transform: translate(5px, -50%);
                }

                .st-key-open_public_ai_content_studio button:active {
                    transform: translateY(-1px) scale(.992);
                    transition-duration: .09s !important;
                }

                .st-key-open_public_ai_content_studio button:focus-visible {
                    outline: 3px solid rgba(255, 158, 153, .5) !important;
                    outline-offset: 3px !important;
                    box-shadow:
                        0 18px 40px rgba(176, 28, 28, .38),
                        0 0 0 5px rgba(229, 57, 53, .14) !important;
                }

                @keyframes publicAiCardEnter {
                    from { opacity: 0; transform: translateY(18px) scale(.985); }
                    to   { opacity: 1; transform: translateY(0) scale(1); }
                }

                @keyframes publicAiBorderFlow {
                    0%, 100% { background-position: 0 0, 0% 50%; }
                    50%      { background-position: 0 0, 100% 50%; }
                }

                @keyframes publicAiOrbFloat {
                    0%, 100% { transform: translate3d(0, 0, 0) scale(1); opacity: .72; }
                    50%      { transform: translate3d(-20px, 24px, 0) scale(1.12); opacity: 1; }
                }

                @keyframes publicAiShimmer {
                    0%, 56%  { transform: translateX(-52%) rotate(4deg); opacity: 0; }
                    67%      { opacity: .72; }
                    83%      { transform: translateX(50%) rotate(4deg); opacity: 0; }
                    100%     { transform: translateX(50%) rotate(4deg); opacity: 0; }
                }

                @keyframes publicAiBadgeEnter {
                    to { opacity: 1; transform: translateY(0); }
                }

                @keyframes publicAiDotPulse {
                    0%   { box-shadow: 0 0 0 0 rgba(255, 102, 95, .48); }
                    72%  { box-shadow: 0 0 0 7px rgba(255, 102, 95, 0); }
                    100% { box-shadow: 0 0 0 0 rgba(255, 102, 95, 0); }
                }

                @keyframes publicAiSparkEnter {
                    from { opacity: 0; transform: translateY(8px) rotate(-8deg) scale(.86); }
                    to   { opacity: 1; transform: translateY(0) rotate(0) scale(1); }
                }

                @keyframes publicAiSparkFloat {
                    0%, 100% { transform: translateY(0) rotate(0); }
                    50%      { transform: translateY(-4px) rotate(5deg); }
                }

                @keyframes publicAiTextReveal {
                    to { opacity: 1; transform: translateY(0); filter: blur(0); }
                }

                @keyframes publicAiTitleGradient {
                    0%, 100% { background-position: 0% 50%; }
                    50%      { background-position: 100% 50%; }
                }

                @keyframes publicAiCtaEnter {
                    to { opacity: 1; transform: translateY(0); }
                }

                @keyframes publicAiButtonGradient {
                    0%, 100% { background-position: 0% 50%; }
                    50%      { background-position: 100% 50%; }
                }

                @keyframes publicAiButtonShine {
                    0%, 57% { left: -42%; opacity: 0; }
                    65%     { opacity: 1; }
                    82%     { left: 112%; opacity: 0; }
                    100%    { left: 112%; opacity: 0; }
                }

                @media (max-width: 720px) {
                    .public-ai-teaser-v11 {
                        padding: 1rem 1rem .98rem;
                        border-radius: 18px;
                    }
                    .public-ai-teaser-v11__topline {
                        align-items: flex-start;
                    }
                    .public-ai-teaser-v11__spark {
                        width: 32px;
                        height: 32px;
                        flex-basis: 32px;
                    }
                    .public-ai-teaser-v11__title {
                        font-size: 1rem;
                    }
                    .public-ai-teaser-v11__description {
                        font-size: .81rem;
                    }
                    .public-ai-teaser-v11__meta {
                        display: grid;
                        grid-template-columns: 1fr;
                        gap: .42rem;
                    }
                    .st-key-open_public_ai_content_studio button {
                        min-height: 52px;
                        padding-left: .8rem !important;
                        padding-right: 2.7rem !important;
                        font-size: .88rem !important;
                    }
                }

                @media (prefers-reduced-motion: reduce) {
                    .public-ai-teaser-v11,
                    .public-ai-teaser-v11::before,
                    .public-ai-teaser-v11::after,
                    .public-ai-teaser-v11__badge,
                    .public-ai-teaser-v11__badge-dot,
                    .public-ai-teaser-v11__spark,
                    .public-ai-teaser-v11__title,
                    .public-ai-teaser-v11__title-accent,
                    .public-ai-teaser-v11__description,
                    .public-ai-teaser-v11__meta,
                    .st-key-open_public_ai_content_studio,
                    .st-key-open_public_ai_content_studio button,
                    .st-key-open_public_ai_content_studio button::before {
                        animation: none !important;
                        opacity: 1 !important;
                        transform: none !important;
                        filter: none !important;
                    }
                }
                </style>
                <section class="public-ai-teaser-v11" aria-label="Ajakan mencoba AI Content Studio">
                    <div class="public-ai-teaser-v11__topline">
                        <div class="public-ai-teaser-v11__badges" aria-label="Status fitur">
                            <span class="public-ai-teaser-v11__badge">
                                <span class="public-ai-teaser-v11__badge-dot" aria-hidden="true"></span>
                                Publik
                            </span>
                            <span class="public-ai-teaser-v11__badge">Tanpa Login</span>
                            <span class="public-ai-teaser-v11__badge">Gemini AI</span>
                        </div>
                        <span class="public-ai-teaser-v11__spark" aria-hidden="true">✦</span>
                    </div>
                    <h3 class="public-ai-teaser-v11__title">
                        <span class="public-ai-teaser-v11__title-accent">
                            Butuh ide konten tanpa membuka dashboard penelitian?
                        </span>
                    </h3>
                    <p class="public-ai-teaser-v11__description">
                        <strong>AI Content Studio</strong> dapat digunakan masyarakat umum tanpa login
                        untuk menyusun ide konten yang lebih relevan dengan layanan, platform, topik,
                        dan karakter influencer.
                    </p>
                    <div class="public-ai-teaser-v11__meta" aria-label="Keunggulan fitur">
                        <span class="public-ai-teaser-v11__meta-item">Akses cepat tanpa akun</span>
                        <span class="public-ai-teaser-v11__meta-item">Tidak melakukan scraping profil</span>
                    </div>
                </section>
                """
                ),
                unsafe_allow_html=True,
            )
            st.button(
                "✨ Coba AI Content Studio Tanpa Login",
                key="open_public_ai_content_studio",
                use_container_width=True,
                on_click=_open_public_ai_content_studio,
            )
    except Exception:
        st.error("Halaman autentikasi belum dapat ditampilkan.")


def _menu_items() -> list[dict[str, str]]:
    """Susun menu sidebar berdasarkan role pengguna aktif."""
    try:
        role = normalize_role(
            st.session_state.get("role", DEFAULT_ROLE),
            st.session_state.get("user_id"),
        )
        allowed_routes = set(
            get_allowed_routes(role, st.session_state.get("user_id"))
        )

        # Admin Panel tetap ditempatkan setelah Profil dan sebelum Tentang agar
        # urutan visual Data Analis tidak berubah dari baseline.
        menu_catalog = [
            *MENU_USER[:7],
            ADMIN_MENU,
            *MENU_USER[7:],
        ]
        return [
            item.copy()
            for item in menu_catalog
            if item["route"] in allowed_routes
        ]
    except Exception:
        return [MENU_USER[0].copy()]


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
        render_html_iframe(
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

                const observerKey = "__telkomSidebarOpenObserverV3";
                const oldObserver = window.parent[observerKey];
                if (oldObserver && typeof oldObserver.disconnect === "function") {
                    oldObserver.disconnect();
                }

                const observer = new MutationObserver(() => {
                    applyOpenButton();
                });
                observer.observe(parentDocument.body, {
                    childList: true,
                    subtree: true,
                });
                window.parent[observerKey] = observer;
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
        render_html_iframe(
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

                const timerKey = "__telkomOptionMenuHoverTimersV3";
                const oldTimers = window.parent[timerKey] || [];
                oldTimers.forEach((timerId) => window.parent.clearTimeout(timerId));

                applyHoverStyle();
                window.parent[timerKey] = [
                    window.parent.setTimeout(applyHoverStyle, 150),
                    window.parent.setTimeout(applyHoverStyle, 500),
                    window.parent.setTimeout(applyHoverStyle, 1200),
                ];
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
    option_menu = _resolve_option_menu_callable()
    dark_mode = bool(st.session_state.get("dark_mode", False))
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

            # Mode Demo disimpan pada session agar seluruh halaman membaca
            # status yang sama. Komponen lain di sidebar tidak diubah.
            st.markdown("---")
            demo_mode = st.toggle(
                "🎯 Mode Demo (Sidang)",
                value=bool(st.session_state.get("demo_mode", False)),
                key="sidebar_demo_mode_toggle",
                help=(
                    "Gunakan data sample terkurasi tanpa model IndoBERT, "
                    "file CSV, koneksi internet, atau Gemini API."
                ),
            )
            st.session_state["demo_mode"] = bool(demo_mode)
            if demo_mode:
                st.success("✅ Mode Demo Aktif — Data sample digunakan")

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

            mode_label = "🌙 Mode Gelap" if dark_mode else "☀️ Mode Terang"
            mode_help = (
                "Nonaktifkan untuk kembali ke Mode Terang."
                if dark_mode
                else "Aktifkan untuk menggunakan Mode Gelap."
            )
            mode_switch_col, mode_label_col, mode_help_col = st.columns(
                [0.20, 0.66, 0.14]
            )
            with mode_switch_col:
                new_dark_mode = st.toggle(
                    mode_label,
                    value=dark_mode,
                    key="dark_mode_toggle",
                    label_visibility="collapsed",
                )
            with mode_label_col:
                st.markdown(
                    f'<div class="mode-dark-label-v226">{mode_label}</div>',
                    unsafe_allow_html=True,
                )
            with mode_help_col:
                st.markdown(
                    f"""
                    <div class="mode-dark-help-wrap-v215">
                        <span
                            class="mode-dark-help-v215"
                            tabindex="0"
                            aria-label="Informasi Tema Dashboard"
                        >
                            ?
                            <span class="mode-dark-help-tooltip-v215">
                                {mode_help}
                            </span>
                        </span>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )
            if new_dark_mode != dark_mode:
                st.session_state["dark_mode"] = new_dark_mode
                # Tema memicu rerun pada route yang sama. Tandai satu kali agar
                # viewport kembali ke bagian paling atas setelah tema selesai
                # diterapkan; tanpa flag ini browser dapat mempertahankan posisi
                # scroll lama dan membuat hero seolah-olah menghilang.
                st.session_state["_force_route_top_once"] = True
                st.rerun()

            try:
                from utils.gemini_client import render_gemini_request_counter

                render_gemini_request_counter()
            except Exception as error:
                LOGGER.warning(
                    "Counter Gemini di sidebar belum dapat ditampilkan (%s).",
                    type(error).__name__,
                )

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
                show_logout_confirmation()

            st.markdown(
                f'<div class="sidebar-v2-version">{get_sidebar_footer_text()}</div>',
                unsafe_allow_html=True,
            )

        return selected_route
    except Exception:
        st.error("Navigasi belum dapat ditampilkan.")
        return "Beranda"


DEMO_ANALYTIC_ROUTES = {
    "Beranda",
    "Dataset",
    "Analisis Sentimen",
    "Analisis Topik",
    "Analisis Jaringan Sosial",
    "Rekomendasi",
}


def _render_demo_mode_banner(selected_route: str) -> None:
    """Tampilkan penanda Mode Demo hanya pada enam halaman analitik."""
    try:
        if not bool(st.session_state.get("demo_mode", False)):
            return
        if selected_route not in DEMO_ANALYTIC_ROUTES:
            return
        st.markdown(
            """
            <div style="
                background:linear-gradient(90deg,#B71C1C,#E53935);
                border:1px solid rgba(255,255,255,.18);
                border-radius:10px;
                box-shadow:0 10px 24px rgba(183,28,28,.18);
                color:#FFFFFF;
                font-family:'Plus Jakarta Sans','Inter',sans-serif;
                font-size:14px;
                font-weight:800;
                line-height:1.45;
                margin:0 0 16px 0;
                padding:11px 18px;
                text-align:center;
            ">
                🎯 MODE DEMO AKTIF — Menampilkan data sample untuk presentasi sidang
            </div>
            """,
            unsafe_allow_html=True,
        )
    except Exception as exc:
        LOGGER.warning("Banner Mode Demo gagal ditampilkan (%s).", type(exc).__name__)


def _reset_scroll_ke_hero_setelah_pindah_halaman() -> None:
    """Pulihkan viewport ke bagian paling atas setelah route/tema berubah.

    Streamlit dan browser dapat mempertahankan posisi scroll saat DOM halaman
    dirender ulang. Pada halaman panjang, posisi tersebut bisa berada di bawah
    hero sehingga hero tampak hilang walaupun markup-nya masih ada. Reset ini
    hanya dipanggil saat route berubah atau setelah toggle tema, bukan pada
    rerun filter/tab biasa.
    """
    try:
        render_html_iframe(
            dedent(
                r"""
                <!doctype html>
                <html lang="id">
                <head><meta charset="utf-8" /></head>
                <body>
                <script>
                (() => {
                    try {
                        const parentWindow = window.parent;
                        const parentDocument = parentWindow.document;

                        try {
                            if (parentWindow.history && 'scrollRestoration' in parentWindow.history) {
                                parentWindow.history.scrollRestoration = 'manual';
                            }
                        } catch (error) {}

                        const getCandidates = () => [
                            parentDocument.querySelector('[data-testid="stMain"]'),
                            parentDocument.querySelector('section[data-testid="stMain"]'),
                            parentDocument.querySelector('[data-testid="stMainBlockContainer"]'),
                            parentDocument.querySelector('[data-testid="stAppViewContainer"] .main'),
                            parentDocument.querySelector('[data-testid="stAppViewContainer"]'),
                            parentDocument.querySelector('main'),
                            parentDocument.querySelector('.main'),
                            parentDocument.scrollingElement,
                            parentDocument.documentElement,
                            parentDocument.body,
                        ].filter(Boolean);

                        const forceElementTop = (element) => {
                            try {
                                if (element.style) {
                                    element.style.scrollBehavior = 'auto';
                                }
                            } catch (error) {}
                            try {
                                if (typeof element.scrollTo === 'function') {
                                    element.scrollTo({ top: 0, left: 0, behavior: 'auto' });
                                }
                            } catch (error) {}
                            try {
                                if ('scrollTop' in element) element.scrollTop = 0;
                                if ('scrollLeft' in element) element.scrollLeft = 0;
                            } catch (error) {}
                        };

                        const forceTop = () => {
                            const candidates = [...new Set(getCandidates())];
                            candidates.forEach(forceElementTop);
                            try {
                                parentWindow.scrollTo({ top: 0, left: 0, behavior: 'auto' });
                            } catch (error) {}
                        };

                        // Streamlit menyusun DOM secara bertahap. Ulangi reset
                        // hingga chart/fragment/loading selesai mengubah tinggi halaman.
                        forceTop();
                        parentWindow.requestAnimationFrame(() => {
                            forceTop();
                            parentWindow.requestAnimationFrame(forceTop);
                        });
                        [60, 160, 320, 650, 1000, 1500].forEach((delay) => {
                            parentWindow.setTimeout(forceTop, delay);
                        });
                    } catch (error) {
                        // Kegagalan reset scroll tidak boleh menggagalkan halaman.
                    }
                })();
                </script>
                </body>
                </html>
                """
            ),
            width=0,
            height=0,
            scrolling=False,
            tab_index=-1,
        )
    except Exception as exc:
        LOGGER.debug("Reset scroll route/tema dilewati: %s", exc)


def route_page(selected: str) -> None:
    """Render halaman dengan loading global hanya saat route benar-benar berubah."""
    try:
        selected_route = _normalise_selected_route(selected)
        role = normalize_role(
            st.session_state.get("role", DEFAULT_ROLE),
            st.session_state.get("user_id"),
        )
        if not can_access_route(
            role,
            selected_route,
            user_id=st.session_state.get("user_id"),
        ):
            log_activity(
                "ACCESS_DENIED",
                selected_route,
                f"Akses ke halaman {selected_route} ditolak oleh kontrol role.",
                status="denied",
                metadata={"role": role},
            )
            role_label = get_role_label(role, st.session_state.get("user_id"))
            page_label = ROUTE_VISUAL_ALIASES.get(selected_route, selected_route)
            st.error(
                f"Akses ditolak. Role {role_label} tidak dapat membuka halaman "
                f"{page_label}."
            )
            selected_route = "Beranda"
            st.session_state["selected_page"] = selected_route
            st.session_state["page"] = selected_route
            st.session_state.pop("_sidebar_force_route", None)

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
        force_route_top = route_changed or bool(
            st.session_state.pop("_force_route_top_once", False)
        )
        if route_changed:
            # Halaman tujuan memakai penanda ini satu kali untuk menyelaraskan
            # selector layanan lokal dengan layanan aktif lintas halaman.
            st.session_state["_active_service_sync_target"] = selected_route

        # Widget Streamlit selalu memicu rerun. Loader global hanya diperlukan
        # saat pengguna benar-benar berpindah halaman, bukan saat menekan tombol,
        # mengganti tab, membuka expander, atau menjalankan prediksi pada route sama.
        #
        # Ketika aplikasi baru dibuka, overlay startup sudah menutup seluruh layar.
        # Jangan menumpuk overlay route pertama di bawah/atas overlay tersebut karena
        # dua judul dan pesan loading dapat terlihat bersamaan saat browser dibuka
        # otomatis oleh Streamlit lokal.
        startup_loading_active = bool(
            st.session_state.get("_startup_loading_active", False)
        )
        skip_route_loader_once = bool(
            st.session_state.pop("_skip_route_loader_once", False)
        )
        # Rekomendasi memiliki banyak section. Overlay global sebelumnya menahan
        # seluruh halaman sampai section terakhir selesai. Untuk route ini,
        # biarkan Streamlit mengirim hero, filter, dan section berikutnya secara
        # progresif tanpa mengubah isi atau tampilan komponennya.
        progressive_route = selected_route == "Rekomendasi"

        if (
            route_changed
            and not startup_loading_active
            and not skip_route_loader_once
            and not progressive_route
        ):
            log_page_view_once(selected_route)
            with layar_loading(selected_route):
                _render_demo_mode_banner(selected_route)
                render_fn()
        else:
            if route_changed:
                log_page_view_once(selected_route)
            _render_demo_mode_banner(selected_route)
            render_fn()

        # Saat route atau tema berubah, pastikan viewport kembali ke hero halaman.
        # Filter/tab pada route yang sama tidak mengaktifkan reset ini.
        if force_route_top:
            _reset_scroll_ke_hero_setelah_pindah_halaman()

        st.session_state["_last_rendered_route"] = selected_route
    except Exception as exc:
        LOGGER.exception("Halaman %s gagal ditampilkan: %s", selected, exc)
        st.error(
            "Halaman yang dipilih belum dapat ditampilkan. "
            "Silakan muat ulang halaman atau pilih menu lain."
        )


def render_footer() -> None:
    """Tampilkan footer global interaktif pada seluruh halaman dashboard."""
    try:
        render_html_iframe(
            dedent(
                f"""
                <!doctype html>
                <html lang="id">
                <head>
                    <meta charset="utf-8" />
                    <meta name="viewport" content="width=device-width, initial-scale=1" />
                    <style>
                        * {{ box-sizing: border-box; }}

                        html, body {{
                            margin: 0;
                            padding: 0;
                            background: transparent;
                            color: #FFFFFF;
                            font-family: "Plus Jakarta Sans", "Inter", sans-serif;
                            overflow: hidden;
                        }}

                        .footer-shell {{
                            position: relative;
                            width: 100%;
                            min-height: 152px;
                            padding: 14px 16px 12px;
                            border: 1px solid rgba(255, 255, 255, 0.11);
                            border-radius: 18px;
                            background:
                                radial-gradient(circle at var(--mouse-x, 82%) var(--mouse-y, 18%), rgba(229, 57, 53, 0.19), transparent 31%),
                                radial-gradient(circle at 12% 110%, rgba(33, 150, 243, 0.17), transparent 34%),
                                linear-gradient(135deg, rgba(20, 25, 34, 0.98), rgba(10, 14, 21, 0.98));
                            box-shadow: 0 16px 38px rgba(0, 0, 0, 0.24);
                            overflow: hidden;
                            isolation: isolate;
                            transition: border-color 220ms ease, box-shadow 220ms ease, transform 220ms ease;
                        }}

                        .footer-shell:hover {{
                            border-color: rgba(229, 57, 53, 0.42);
                            box-shadow: 0 18px 44px rgba(0, 0, 0, 0.30), 0 0 28px rgba(229, 57, 53, 0.10);
                            transform: translateY(-1px);
                        }}

                        .footer-shell::before {{
                            content: "";
                            position: absolute;
                            inset: 0 0 auto;
                            height: 3px;
                            background: linear-gradient(90deg, #E53935, #FF9800, #42A5F5, #E53935);
                            background-size: 240% 100%;
                            animation: footer-gradient-flow 6s linear infinite;
                            z-index: 3;
                        }}

                        .footer-shell::after {{
                            content: "";
                            position: absolute;
                            width: 150px;
                            height: 150px;
                            right: -64px;
                            top: -78px;
                            border-radius: 50%;
                            background: rgba(229, 57, 53, 0.15);
                            filter: blur(2px);
                            animation: footer-orbit 7s ease-in-out infinite;
                            z-index: -1;
                        }}

                        .footer-content {{
                            display: grid;
                            grid-template-columns: minmax(0, 1fr) auto;
                            gap: 18px;
                            align-items: center;
                            height: 100%;
                        }}

                        .footer-brand {{
                            display: flex;
                            align-items: center;
                            gap: 13px;
                            min-width: 0;
                        }}

                        .footer-mark {{
                            position: relative;
                            width: 46px;
                            height: 46px;
                            flex: 0 0 46px;
                            display: grid;
                            place-items: center;
                            border: 1px solid rgba(229, 57, 53, 0.36);
                            border-radius: 14px;
                            background: linear-gradient(145deg, rgba(229, 57, 53, 0.22), rgba(229, 57, 53, 0.07));
                            box-shadow: inset 0 0 18px rgba(229, 57, 53, 0.08);
                            font-size: 21px;
                            transition: transform 240ms ease, box-shadow 240ms ease;
                        }}

                        .footer-shell:hover .footer-mark {{
                            transform: rotate(-5deg) scale(1.05);
                            box-shadow: inset 0 0 18px rgba(229, 57, 53, 0.13), 0 0 20px rgba(229, 57, 53, 0.14);
                        }}

                        .footer-mark::after {{
                            content: "";
                            position: absolute;
                            inset: -5px;
                            border: 1px solid rgba(229, 57, 53, 0.18);
                            border-radius: 17px;
                            animation: footer-pulse 2.8s ease-out infinite;
                        }}

                        .footer-copy {{ min-width: 0; }}

                        .footer-title {{
                            margin: 0 0 5px;
                            font-size: 14px;
                            font-weight: 800;
                            letter-spacing: -0.01em;
                            color: #FFFFFF;
                        }}

                        .footer-meta {{
                            margin: 0;
                            color: #AAB3C2;
                            font-size: 0.75rem /* FIX: minimum 12px agar terbaca di tablet */;
                            line-height: 1.55;
                        }}

                        .footer-meta strong {{ color: #FFFFFF; }}

                        .footer-chips {{
                            display: flex;
                            flex-wrap: wrap;
                            gap: 7px;
                            margin-top: 10px;
                        }}

                        .footer-chip {{
                            appearance: none;
                            border: 1px solid rgba(255, 255, 255, 0.10);
                            border-radius: 999px;
                            padding: 6px 9px;
                            background: rgba(255, 255, 255, 0.045);
                            color: #CDD4DF;
                            font: inherit;
                            font-size: 0.75rem /* FIX: minimum 12px agar terbaca di tablet */;
                            font-weight: 700;
                            cursor: pointer;
                            transition: transform 180ms ease, border-color 180ms ease, background 180ms ease, color 180ms ease;
                        }}

                        .footer-chip:hover,
                        .footer-chip.is-active {{
                            transform: translateY(-2px);
                            border-color: rgba(229, 57, 53, 0.42);
                            background: rgba(229, 57, 53, 0.13);
                            color: #FFFFFF;
                        }}

                        .footer-actions {{
                            display: flex;
                            align-items: center;
                            gap: 9px;
                        }}

                        .footer-status {{
                            display: inline-flex;
                            align-items: center;
                            gap: 7px;
                            min-height: 36px;
                            padding: 0 11px;
                            border: 1px solid rgba(76, 175, 80, 0.23);
                            border-radius: 11px;
                            background: rgba(76, 175, 80, 0.08);
                            color: #CFE9D1;
                            font-size: 0.75rem /* FIX: minimum 12px agar terbaca di tablet */;
                            font-weight: 700;
                            white-space: nowrap;
                        }}

                        .footer-status-dot {{
                            width: 7px;
                            height: 7px;
                            border-radius: 50%;
                            background: #4CAF50;
                            box-shadow: 0 0 0 0 rgba(76, 175, 80, 0.45);
                            animation: footer-status-pulse 2s infinite;
                        }}

                        .footer-top-button {{
                            position: relative;
                            display: inline-flex;
                            align-items: center;
                            justify-content: center;
                            gap: 7px;
                            min-height: 36px;
                            padding: 0 12px;
                            border: 1px solid rgba(229, 57, 53, 0.36);
                            border-radius: 11px;
                            background: linear-gradient(135deg, rgba(229, 57, 53, 0.22), rgba(229, 57, 53, 0.10));
                            color: #FFFFFF;
                            font: inherit;
                            font-size: 0.75rem /* FIX: minimum 12px agar terbaca di tablet */;
                            font-weight: 800;
                            cursor: pointer;
                            overflow: hidden;
                            transition: transform 180ms ease, border-color 180ms ease, box-shadow 180ms ease;
                        }}

                        .footer-top-button::before {{
                            content: "";
                            position: absolute;
                            inset: 0;
                            transform: translateX(-115%);
                            background: linear-gradient(90deg, transparent, rgba(255,255,255,0.18), transparent);
                            transition: transform 420ms ease;
                        }}

                        .footer-top-button:hover {{
                            transform: translateY(-2px);
                            border-color: rgba(229, 57, 53, 0.62);
                            box-shadow: 0 9px 22px rgba(229, 57, 53, 0.13);
                        }}

                        .footer-top-button:hover::before {{ transform: translateX(115%); }}

                        .footer-top-button.is-clicked {{ animation: footer-button-pop 420ms ease; }}

                        .footer-arrow {{
                            display: inline-block;
                            transition: transform 200ms ease;
                        }}

                        .footer-top-button:hover .footer-arrow {{ transform: translateY(-2px); }}

                        @keyframes footer-gradient-flow {{
                            to {{ background-position: 240% 0; }}
                        }}

                        @keyframes footer-orbit {{
                            0%, 100% {{ transform: translate3d(0, 0, 0) scale(1); opacity: 0.65; }}
                            50% {{ transform: translate3d(-12px, 14px, 0) scale(1.08); opacity: 1; }}
                        }}

                        @keyframes footer-pulse {{
                            0% {{ transform: scale(0.88); opacity: 0; }}
                            35% {{ opacity: 0.75; }}
                            100% {{ transform: scale(1.24); opacity: 0; }}
                        }}

                        @keyframes footer-status-pulse {{
                            0% {{ box-shadow: 0 0 0 0 rgba(76, 175, 80, 0.40); }}
                            70% {{ box-shadow: 0 0 0 7px rgba(76, 175, 80, 0); }}
                            100% {{ box-shadow: 0 0 0 0 rgba(76, 175, 80, 0); }}
                        }}

                        @keyframes footer-button-pop {{
                            0% {{ transform: scale(1); }}
                            45% {{ transform: scale(0.94); }}
                            100% {{ transform: scale(1); }}
                        }}

                        @media (max-width: 760px) {{
                            .footer-shell {{ min-height: 198px; }}
                            .footer-content {{ grid-template-columns: 1fr; align-content: center; }}
                            .footer-actions {{ justify-content: flex-start; }}
                            .footer-status {{ display: none; }}
                        }}

                        @media (prefers-reduced-motion: reduce) {{
                            *, *::before, *::after {{
                                animation: none !important;
                                transition: none !important;
                                scroll-behavior: auto !important;
                            }}
                        }}
                    </style>
                </head>
                <body>
                    <footer class="footer-shell" id="dashboardFooter">
                        <div class="footer-content">
                            <div class="footer-brand">
                                <div class="footer-mark" aria-hidden="true">📡</div>
                                <div class="footer-copy">
                                    <p class="footer-title">Dashboard Analisis Telkom Group</p>
                                    <p class="footer-meta">
                                        © 2026 <strong>Aulia Rahmadiva Wardana</strong> · NPM <strong>184220019</strong> · ULBI Bandung
                                    </p>
                                    <div class="footer-chips" aria-label="Informasi dashboard">
                                        <button class="footer-chip" type="button">SNA + IndoBERT</button>
                                        <button class="footer-chip" type="button">IndiHome · IndiBiz · Telkomsel</button>
                                        <button class="footer-chip" type="button">Versi {APP_VERSION.split(' · ')[0]}</button>
                                    </div>
                                </div>
                            </div>
                            <div class="footer-actions">
                                <div class="footer-status" title="Dashboard siap digunakan">
                                    <span class="footer-status-dot"></span>
                                    Dashboard Aktif
                                </div>
                                <button class="footer-top-button" id="footerTopButton" type="button" aria-label="Kembali ke bagian atas halaman">
                                    <span class="footer-arrow">↑</span>
                                    <span id="footerTopLabel">Ke atas</span>
                                </button>
                            </div>
                        </div>
                    </footer>

                    <script>
                        const footer = document.getElementById('dashboardFooter');
                        const topButton = document.getElementById('footerTopButton');
                        const topLabel = document.getElementById('footerTopLabel');
                        const chips = document.querySelectorAll('.footer-chip');

                        footer.addEventListener('mousemove', (event) => {{
                            const rect = footer.getBoundingClientRect();
                            const x = ((event.clientX - rect.left) / rect.width) * 100;
                            const y = ((event.clientY - rect.top) / rect.height) * 100;
                            footer.style.setProperty('--mouse-x', `${{x}}%`);
                            footer.style.setProperty('--mouse-y', `${{y}}%`);
                        }});

                        footer.addEventListener('mouseleave', () => {{
                            footer.style.setProperty('--mouse-x', '82%');
                            footer.style.setProperty('--mouse-y', '18%');
                        }});

                        chips.forEach((chip) => {{
                            chip.addEventListener('click', () => {{
                                chip.classList.toggle('is-active');
                            }});
                        }});

                        const scrollElementToTop = (element, behavior = 'smooth') => {{
                            if (!element) return false;

                            let scrolled = false;
                            try {{
                                if (typeof element.scrollTo === 'function') {{
                                    element.scrollTo({{ top: 0, left: 0, behavior }});
                                    scrolled = true;
                                }}
                            }} catch (error) {{
                                // Lanjutkan ke assignment scrollTop sebagai fallback.
                            }}

                            try {{
                                if ('scrollTop' in element) {{
                                    element.scrollTop = 0;
                                    scrolled = true;
                                }}
                            }} catch (error) {{
                                // Elemen tertentu dapat menolak assignment; kandidat lain tetap dicoba.
                            }}

                            return scrolled;
                        }};

                        const scrollDashboardToTop = () => {{
                            try {{
                                const parentWindow = window.parent;
                                const parentDocument = parentWindow.document;
                                const candidates = [
                                    parentDocument.querySelector('[data-testid="stMain"]'),
                                    parentDocument.querySelector('section[data-testid="stMain"]'),
                                    parentDocument.querySelector('section.main'),
                                    parentDocument.querySelector('[data-testid="stAppViewContainer"]'),
                                    parentDocument.querySelector('main'),
                                    parentDocument.scrollingElement,
                                    parentDocument.documentElement,
                                    parentDocument.body,
                                ];

                                // Ikuti rantai parent dari iframe footer karena container scroll
                                // Streamlit dapat berubah antarversi.
                                try {{
                                    let ancestor = window.frameElement;
                                    while (ancestor) {{
                                        candidates.push(ancestor);
                                        ancestor = ancestor.parentElement;
                                    }}
                                }} catch (error) {{
                                    // Kandidat selector di atas tetap cukup sebagai fallback.
                                }}

                                const uniqueCandidates = [...new Set(candidates.filter(Boolean))];
                                let scrolled = false;
                                uniqueCandidates.forEach((candidate) => {{
                                    scrolled = scrollElementToTop(candidate) || scrolled;
                                }});

                                try {{
                                    parentWindow.scrollTo({{ top: 0, left: 0, behavior: 'smooth' }});
                                    scrolled = true;
                                }} catch (error) {{
                                    // Root document sudah dicoba melalui daftar kandidat.
                                }}

                                // Pastikan posisi benar-benar nol setelah animasi browser selesai.
                                parentWindow.setTimeout(() => {{
                                    uniqueCandidates.forEach((candidate) => {{
                                        scrollElementToTop(candidate, 'auto');
                                    }});
                                    try {{
                                        parentWindow.scrollTo({{ top: 0, left: 0, behavior: 'auto' }});
                                    }} catch (error) {{
                                        // Tidak perlu menampilkan error ke pengguna.
                                    }}
                                }}, 420);

                                return scrolled;
                            }} catch (error) {{
                                try {{
                                    window.scrollTo({{ top: 0, left: 0, behavior: 'smooth' }});
                                    return true;
                                }} catch (fallbackError) {{
                                    return false;
                                }}
                            }}
                        }};

                        topButton.addEventListener('click', (event) => {{
                            event.preventDefault();
                            event.stopPropagation();

                            topButton.classList.remove('is-clicked');
                            void topButton.offsetWidth;
                            topButton.classList.add('is-clicked');
                            topLabel.textContent = 'Naik...';

                            scrollDashboardToTop();

                            window.setTimeout(() => {{
                                topLabel.textContent = 'Ke atas';
                                topButton.classList.remove('is-clicked');
                            }}, 900);
                        }});
                    </script>
                </body>
                </html>
                """
            ),
            height=174,
            scrolling=False,
        )
    except Exception as exc:
        LOGGER.exception("Footer global gagal ditampilkan: %s", exc)
        st.caption(FOOTER_TEXT)


def _ensure_database_initialized() -> None:
    """Inisialisasi skema database satu kali pada setiap sesi browser.

    Startup dapat melakukan beberapa rerun singkat ketika membaca cookie
    remember-me. Menjalankan migrasi SQLite pada setiap rerun hanya menambah
    waktu tunggu tanpa mengubah hasil, sehingga status keberhasilan disimpan
    pada session_state.
    """
    if st.session_state.get("_database_initialized_v1", False):
        return

    init_database()
    st.session_state["_database_initialized_v1"] = True


def main() -> None:
    """Jalankan autentikasi, sidebar, routing, dan footer dashboard."""
    try:
        init_session_state()
        install_plotly_theme_adapter()
        _ensure_database_initialized()

        # CookieManager hanya boleh dirender pada fase autentikasi. Setelah
        # session aktif, komponen ini dikeluarkan dari tree Streamlit agar urutan
        # komponen sidebar (terutama streamlit-option-menu) tetap stabil.
        if not st.session_state.get("logged_in", False):
            refresh_cookie_manager_for_run()

        if _process_pending_logout():
            return

        # Kompatibilitas untuk state pending dari patch lama. Penyelesaiannya
        # hanya dilakukan sebelum session aktif dan tidak ikut dirender bersama
        # sidebar dashboard.
        if not st.session_state.get("logged_in", False):
            complete_pending_remember_login()
        sync_authenticated_user_state()

        if not st.session_state.logged_in:
            load_css(
                dark_mode=st.session_state.get("dark_mode", False),
                hide_sidebar=True,
            )

            restore_status = "none"
            if not st.session_state.get("logged_in", False):
                restore_status = try_restore_remember_login()

            if restore_status == "wait":
                # Snapshot cookie pertama bersifat asinkron. Jangan tahan pengguna
                # di balik boot overlay hanya untuk menunggu satu rerun browser.
                # Form login tetap ditampilkan sekarang; bila cookie valid tersedia,
                # rerun berikutnya akan memulihkan sesi secara otomatis.
                render_auth_page()
                _selesaikan_loading_awal()
                render_footer()
                st.stop()

            if restore_status == "ok" or st.session_state.get(
                "logged_in", False
            ):
                # Pemulihan cookie terjadi pada run yang masih memuat komponen
                # autentikasi. Lakukan satu rerun bersih agar sidebar dirender
                # tanpa CookieManager dan option-menu tidak menjadi iframe kosong.
                st.rerun()

            if not st.session_state.get("logged_in", False):
                public_transition_pending = bool(
                    st.session_state.pop("_public_route_loading_pending", False)
                )
                if public_transition_pending:
                    public_route = str(
                        st.session_state.get("_public_route") or "auth"
                    )
                    if public_route == "ai_content_studio":
                        with layar_loading(
                            "AI Content Studio",
                            judul="Membuka AI Content Studio",
                            pesan=(
                                "Menyiapkan ruang ide konten",
                                "Memuat pilihan layanan dan platform",
                                "Mengaktifkan generator Gemini AI",
                                "Menyiapkan formulir influencer",
                            ),
                        ):
                            render_auth_page()
                    else:
                        with layar_loading(
                            "Autentikasi",
                            judul="Kembali ke Halaman Masuk",
                            pesan=(
                                "Menutup ruang ide konten",
                                "Menyiapkan formulir autentikasi",
                                "Memulihkan tampilan halaman masuk",
                            ),
                        ):
                            render_auth_page()
                else:
                    render_auth_page()

                # Form Login/Register sudah siap. Footer tidak perlu menahan
                # overlay startup sehingga tampilan pertama muncul lebih cepat.
                _selesaikan_loading_awal()
                render_footer()
                if st.session_state.pop("_logout_just_completed_v2", False):
                    _remove_client_logout_overlay()
                return

        selected = render_sidebar_menu()

        # Sidebar menandakan sesi sudah siap. Tutup overlay startup di sini agar
        # pengguna tidak menunggu render penuh halaman awal dan footer. Route
        # pertama diberi flag satu-kali supaya tidak langsung diganti overlay
        # perpindahan halaman lain.
        if bool(st.session_state.get("_startup_loading_active", False)):
            st.session_state["_skip_route_loader_once"] = True
            _selesaikan_loading_awal()

        route_page(selected)
        render_footer()
        _selesaikan_loading_awal()

        login_transition_finished = bool(
            st.session_state.pop("_login_just_completed_v1", False)
        )
        login_transition_active = bool(
            st.session_state.pop("_login_transition_active_v1", False)
        )
        if login_transition_finished or login_transition_active:
            remove_login_transition_overlay()

    except Exception as exc:
        LOGGER.exception("Aplikasi gagal dijalankan: %s", exc)
        _selesaikan_loading_awal()
        if st.session_state.pop("_login_transition_active_v1", False):
            st.session_state.pop("_login_just_completed_v1", None)
            remove_login_transition_overlay()
        st.error(
            "Aplikasi belum dapat ditampilkan. Silakan muat ulang halaman "
            "atau hubungi administrator."
        )


if __name__ == "__main__":
    main()
