"""
Entry point utama dashboard analitik media sosial Telkom Group.
Skripsi S1 Sains Data — SNA & IndoBERT Sentiment Analysis.
"""

from base64 import b64encode
from html import escape
from pathlib import Path

import streamlit as st

st.set_page_config(
    page_title="Dashboard Analisis Telkom Group",
    page_icon="📡",
    layout="wide",
    initial_sidebar_state="expanded",
)

from auth.auth_utils import get_user_by_id, init_db, revoke_remember_token  # noqa: E402
from auth.login import (  # noqa: E402
    MAX_COOKIE_POLLS,
    clear_remember_cookie,
    complete_pending_remember_login,
    show_login_page,
    try_restore_remember_login,
)
from auth.profile import render_profile  # noqa: E402
from auth.register import show_register_page  # noqa: E402
from pages import (  # noqa: E402
    about,
    admin_panel,
    dataset,
    home,
    recommendation,
    sentiment,
    sna,
    wordcloud_page,
)
from utils.css_loader import load_css  # noqa: E402

ASSETS_DIR = Path(__file__).resolve().parent / "assets"
DEFAULT_AVATAR = ASSETS_DIR / "default_avatar.png"
LOGO_PATH = ASSETS_DIR / "logo.png"

FOOTER_TEXT = "© 2026 Aulia Rahmadiva Wardana · NPM 184220019 · ULBI Bandung"
APP_VERSION = "v0.4 · UI Patch 1.1"


MENU_BASE = [
    ("Beranda", "⌂"),
    ("Dataset", "▣"),
    ("Analisis Sentimen", "◉"),
    ("WordCloud", "☁"),
    ("Analisis Jaringan Sosial", "⌘"),
    ("Rekomendasi", "◎"),
    ("Profil", "●"),
]


def init_session_state() -> None:
    """Inisialisasi session state dengan nilai default."""
    defaults = {
        "logged_in": False,
        "page": "login",
        "username": "",
        "fullname": "",
        "role": "",
        "user_id": None,
        "dark_mode": True,
        "remembered_username": "",
        "selected_page": "Beranda",
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


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


def render_sidebar_brand() -> None:
    """Tampilkan identitas aplikasi secara ringkas di sidebar."""
    logo_uri = _file_data_uri(LOGO_PATH)
    if logo_uri:
        icon_html = (
            f'<img class="sidebar-brand-logo" src="{logo_uri}" '
            'alt="Logo Dashboard Telkom Group">'
        )
    else:
        icon_html = '<div class="sidebar-brand-fallback">📡</div>'

    st.markdown(
        f"""
        <div class="sidebar-brand">
            {icon_html}
            <div class="sidebar-brand-copy">
                <div class="sidebar-brand-title">Telkom Analytics</div>
                <div class="sidebar-brand-subtitle">SNA · IndoBERT</div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_sidebar_avatar() -> None:
    """Tampilkan identitas pengguna secara ringkas di sidebar."""
    try:
        avatar_uri = _bytes_data_uri(get_avatar_bytes())
        fullname = escape(st.session_state.get("fullname") or "Pengguna")
        role = (st.session_state.get("role") or "user").lower()

        if avatar_uri:
            avatar_html = (
                f'<img class="sidebar-avatar" src="{avatar_uri}" '
                'alt="Foto profil pengguna">'
            )
        else:
            avatar_html = '<div class="sidebar-avatar-fallback">👤</div>'

        if role == "admin":
            role_label = "Administrator"
            role_class = "sidebar-role-admin"
        else:
            role_label = "Pengguna"
            role_class = "sidebar-role-user"

        st.markdown(
            f"""
            <div class="sidebar-profile-card">
                {avatar_html}
                <div class="sidebar-profile-copy">
                    <div class="sidebar-profile-name">{fullname}</div>
                    <span class="sidebar-role-badge {role_class}">{role_label}</span>
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
    """Tampilkan halaman login atau registrasi sesuai session state."""
    try:
        if st.session_state.get("page") == "register":
            show_register_page()
        else:
            show_login_page()
    except Exception:
        st.error("Halaman autentikasi belum dapat ditampilkan.")


def _menu_items() -> list[tuple[str, str]]:
    """Susun menu berdasarkan role pengguna."""
    items = list(MENU_BASE)
    if st.session_state.get("role") == "admin":
        items.append(("Admin Panel", "◆"))
    items.append(("Tentang Penelitian", "ⓘ"))
    return items


def _menu_key(label: str) -> str:
    """Buat key widget yang stabil dari label menu."""
    normalized = "".join(char.lower() if char.isalnum() else "_" for char in label)
    return f"nav_{normalized.strip('_')}"


def render_sidebar_menu() -> str:
    """Render identitas, tema, navigasi, dan logout di sidebar."""
    dark_mode = bool(st.session_state.get("dark_mode", True))
    load_css(dark_mode=dark_mode, hide_sidebar=False)

    try:
        menu_items = _menu_items()
        menu_labels = [label for label, _ in menu_items]
        selected = st.session_state.get("selected_page", "Beranda")
        if selected not in menu_labels:
            selected = "Beranda"
            st.session_state.selected_page = selected

        with st.sidebar:
            render_sidebar_brand()
            render_sidebar_avatar()

            st.markdown(
                '<div class="sidebar-section-label">TAMPILAN</div>',
                unsafe_allow_html=True,
            )
            new_dark_mode = st.toggle(
                "Mode Gelap",
                value=dark_mode,
                key="dark_mode_toggle",
                help="Aktifkan atau nonaktifkan tampilan gelap dashboard.",
            )
            if new_dark_mode != dark_mode:
                st.session_state.dark_mode = new_dark_mode
                st.rerun()

            st.markdown(
                '<div class="sidebar-section-label sidebar-menu-label">MENU UTAMA</div>',
                unsafe_allow_html=True,
            )

            for label, icon in menu_items:
                is_active = label == selected
                clicked = st.button(
                    f"{icon}  {label}",
                    key=_menu_key(label),
                    type="primary" if is_active else "secondary",
                    use_container_width=True,
                    help=f"Buka halaman {label}",
                )
                if clicked and not is_active:
                    st.session_state.selected_page = label
                    st.rerun()

            st.markdown('<div class="sidebar-account-divider"></div>', unsafe_allow_html=True)
            if st.button(
                "↪  Keluar",
                type="secondary",
                use_container_width=True,
                key="btn_logout",
                help="Keluar dari akun dashboard.",
            ):
                logout()

            st.markdown(
                f"""
                <div class="sidebar-version">
                    <span>{APP_VERSION}</span>
                    <span>ULBI Bandung · 2026</span>
                </div>
                """,
                unsafe_allow_html=True,
            )

        return selected
    except Exception:
        st.error("Navigasi belum dapat ditampilkan.")
        return "Beranda"


def route_page(selected: str) -> None:
    """Routing ke halaman sesuai pilihan menu sidebar."""
    routes = {
        "Beranda": home.render_home,
        "Dataset": dataset.render_dataset,
        "Analisis Sentimen": sentiment.render_sentiment,
        "WordCloud": wordcloud_page.render_wordcloud,
        "Analisis Jaringan Sosial": sna.render_sna,
        "Rekomendasi": recommendation.render_recommendation,
        "Profil": render_profile,
        "Admin Panel": admin_panel.render_admin_panel,
        "Tentang Penelitian": about.render_about,
    }
    render_fn = routes.get(selected, home.render_home)
    render_fn()


def render_footer() -> None:
    """Tampilkan footer copyright di bagian bawah halaman."""
    st.caption(FOOTER_TEXT)


def main() -> None:
    """Jalankan autentikasi, sidebar, routing, dan footer dashboard."""
    try:
        init_db()
        init_session_state()

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
                    st.markdown(
                        "<p style='text-align:center;padding:2rem;'>"
                        "Memverifikasi sesi Anda...</p>",
                        unsafe_allow_html=True,
                    )
                    import time

                    time.sleep(0.35)
                    st.rerun()
                st.session_state._remember_restore_done = True

            if restore_status == "ok" or st.session_state.get("logged_in"):
                st.rerun()

            render_auth_page()
            render_footer()
            return

        selected = render_sidebar_menu()
        route_page(selected)
        render_footer()

    except Exception:
        st.error(
            "Aplikasi belum dapat ditampilkan. Silakan muat ulang halaman "
            "atau hubungi administrator."
        )


if __name__ == "__main__":
    main()
