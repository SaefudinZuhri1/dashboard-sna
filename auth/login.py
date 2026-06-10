"""Halaman login pengguna."""

from datetime import datetime, timedelta

import extra_streamlit_components as stx
import streamlit as st

from auth.auth_utils import (
    REMEMBER_ME_HOURS,
    create_remember_token,
    get_user,
    revoke_remember_token,
    validate_remember_token,
    verify_password,
)

REMEMBER_COOKIE_KEY = "remember_token"
MAX_COOKIE_POLLS = 8


def _get_cookie_manager() -> stx.CookieManager:
    """Inisialisasi CookieManager sekali per sesi Streamlit."""
    if "cookie_manager" not in st.session_state:
        st.session_state.cookie_manager = stx.CookieManager(
            key="dashboard_remember_me"
        )
    return st.session_state.cookie_manager


def _read_remember_token() -> str | None:
    """Baca token remember-me dari cookie browser."""
    cookies = _get_cookie_manager().get_all()
    if not cookies:
        return None
    return cookies.get(REMEMBER_COOKIE_KEY)


def set_remember_cookie(token: str) -> None:
    """Simpan token remember-me ke cookie browser."""
    try:
        expires = datetime.now() + timedelta(hours=REMEMBER_ME_HOURS)
        _get_cookie_manager().set(
            REMEMBER_COOKIE_KEY,
            token,
            expires_at=expires,
            path="/",
            same_site="lax",
            key="set_remember_cookie",
        )
    except Exception as e:
        print(f"[set_remember_cookie] Error: {e}")


def clear_remember_cookie() -> None:
    """Hapus cookie remember-me dari browser."""
    try:
        _get_cookie_manager().delete(
            REMEMBER_COOKIE_KEY,
            key="clear_remember_cookie",
        )
    except Exception as e:
        print(f"[clear_remember_cookie] Error: {e}")


def _finish_login(user: dict, token: str | None = None) -> None:
    """Set session state setelah login berhasil."""
    st.session_state.logged_in = True
    st.session_state.username = user["username"]
    st.session_state.fullname = user["fullname"]
    st.session_state.role = user["role"]
    st.session_state.user_id = user["user_id"]
    st.session_state.page = "login"
    st.session_state.pop("_cookie_polls", None)
    st.session_state.pop("_remember_restore_done", None)

    if token:
        st.session_state.active_remember_token = token
    else:
        st.session_state.pop("active_remember_token", None)


def complete_pending_remember_login() -> bool:
    """
    Lanjutkan login Ingat Saya setelah cookie disimpan (langkah ke-2).

    CookieManager.set() dipanggil di rerun sebelumnya; sekarang selesaikan login.
    """
    try:
        pending_user = st.session_state.get("pending_remember_user")
        pending_token = st.session_state.get("pending_remember_token")
        if not pending_user or not pending_token:
            return False

        st.session_state.pop("pending_remember_user", None)
        st.session_state.pop("pending_remember_token", None)
        st.session_state.remembered_username = pending_user["username"]
        _finish_login(pending_user, pending_token)
        return True
    except Exception as e:
        print(f"[complete_pending_remember_login] Error: {e}")
        return False


def try_restore_remember_login() -> str:
    """
    Coba login otomatis dari cookie remember-me.

    Returns:
        "wait" — masih menunggu cookie browser dimuat
        "ok"   — login otomatis berhasil
        "none" — tidak ada sesi tersimpan / gagal
    """
    try:
        if st.session_state.get("logged_in"):
            return "none"

        if st.session_state.get("pending_remember_user"):
            return "none"

        if st.session_state.get("_remember_restore_done"):
            return "none"

        token = _read_remember_token()

        if not token:
            polls = st.session_state.get("_cookie_polls", 0)
            if polls < MAX_COOKIE_POLLS:
                st.session_state._cookie_polls = polls + 1
                return "wait"
            st.session_state._remember_restore_done = True
            return "none"

        st.session_state._remember_restore_done = True

        user = validate_remember_token(token)
        if user is None:
            clear_remember_cookie()
            return "none"

        st.session_state.remembered_username = user["username"]
        _finish_login(user, token)
        return "ok"
    except Exception as e:
        print(f"[try_restore_remember_login] Error: {e}")
        return "none"


def start_remember_login(user: dict) -> None:
    """Mulai login dengan Ingat Saya — simpan cookie dulu, login di rerun berikutnya."""
    token = create_remember_token(user["user_id"])
    if not token:
        _finish_login(user, None)
        clear_remember_cookie()
        return

    st.session_state.pending_remember_user = user
    st.session_state.pending_remember_token = token
    st.session_state.remembered_username = user["username"]
    set_remember_cookie(token)


def show_login_page() -> None:
    """Tampilkan halaman login dengan form dan validasi."""
    try:
        _, col_center, _ = st.columns([1, 1.2, 1])
        with col_center:
            st.markdown(
                "<h1 style='text-align:center;font-size:3rem;margin-bottom:0;'>📡</h1>",
                unsafe_allow_html=True,
            )
            st.markdown(
                "<h2 style='text-align:center;'>Dashboard Analisis Telkom Group</h2>",
                unsafe_allow_html=True,
            )
            st.markdown(
                "<p style='text-align:center;color:var(--app-muted);'>Masuk untuk melanjutkan</p>",
                unsafe_allow_html=True,
            )
            st.markdown("")

            default_username = st.session_state.get("remembered_username", "")

            with st.form("login_form", clear_on_submit=False):
                username = st.text_input(
                    "Username",
                    value=default_username,
                    placeholder="Masukkan username",
                )
                password = st.text_input(
                    "Password",
                    type="password",
                    placeholder="Masukkan password",
                )
                show_password = st.checkbox("Tampilkan password")
                if show_password:
                    st.caption(
                        f"Password: {password}" if password else "Password: (kosong)"
                    )
                remember_me = st.checkbox(
                    "Ingat Saya",
                    help=(
                        f"Tetap masuk otomatis selama {REMEMBER_ME_HOURS} jam (±3 hari). "
                        "Gunakan alamat URL yang SAMA setiap kali."
                    ),
                )
                submitted = st.form_submit_button(
                    "Masuk",
                    type="primary",
                    use_container_width=True,
                )

            if submitted:
                if not username.strip() or not password:
                    st.error("Username dan password wajib diisi.")
                    return

                with st.spinner("Memverifikasi kredensial..."):
                    user = get_user(username.strip())

                if user is None:
                    st.error("Username tidak terdaftar")
                    return

                if not verify_password(password, user["password_hash"]):
                    st.error("Password salah")
                    return

                if remember_me:
                    start_remember_login(user)
                else:
                    st.session_state.remembered_username = ""
                    old_token = st.session_state.get("active_remember_token")
                    if old_token:
                        revoke_remember_token(old_token)
                    clear_remember_cookie()
                    _finish_login(user, None)

                st.rerun()

            st.markdown("---")
            st.markdown(
                "<p style='text-align:center;'>Belum punya akun?</p>",
                unsafe_allow_html=True,
            )
            if st.button("Daftar di sini", use_container_width=True, key="go_register"):
                st.session_state.page = "register"
                st.rerun()

            st.caption(
                f"Akun demo: admin / admin123 | Ingat Saya: ±{REMEMBER_ME_HOURS} jam"
            )
            st.info(
                "**Tips Ingat Saya:** selalu buka dashboard lewat **alamat URL yang sama**. "
                "Tutup tab lalu buka lagi URL **yang persis sama** dengan saat login."
            )

    except Exception as e:
        st.error(f"Terjadi kesalahan saat login: {e}")


def render_login() -> None:
    """Alias lama — kompatibilitas dengan kode sebelumnya."""
    show_login_page()
