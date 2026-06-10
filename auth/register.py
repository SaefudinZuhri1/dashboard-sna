"""Halaman registrasi pengguna baru."""

import re

import streamlit as st

from auth.auth_utils import register_user


def _password_strength(password: str) -> tuple[float, str]:
    """Hitung skor kekuatan password (0.0–1.0) dan label weak/medium/strong."""
    if len(password) < 8:
        return 0.25, "weak"

    score = 0
    if any(c.isupper() for c in password):
        score += 1
    if any(c.isdigit() for c in password):
        score += 1
    if any(not c.isalnum() for c in password):
        score += 1
    if len(password) >= 12:
        score += 1

    if score <= 1:
        return 0.33, "weak"
    if score == 2:
        return 0.66, "medium"
    return 1.0, "strong"


def _strength_label_id(label: str) -> str:
    """Terjemahkan label kekuatan password untuk UI."""
    mapping = {"weak": "Lemah", "medium": "Sedang", "strong": "Kuat"}
    return mapping.get(label, label)


def show_register_page() -> None:
    """Tampilkan halaman registrasi dengan form dan validasi."""
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
                "<p style='text-align:center;color:#888;'>Buat akun baru</p>",
                unsafe_allow_html=True,
            )
            st.markdown("")

            with st.form("register_form"):
                fullname = st.text_input("Nama Lengkap", placeholder="Nama lengkap Anda")
                username = st.text_input(
                    "Username",
                    placeholder="Min. 4 karakter, huruf/angka/underscore",
                )
                email = st.text_input("Email", placeholder="contoh@email.com")
                password = st.text_input("Password", type="password")
                confirm = st.text_input("Konfirmasi Password", type="password")

                submitted = st.form_submit_button("Daftar", use_container_width=True)

            if submitted:
                progress_val, strength = _password_strength(password)
                st.progress(progress_val, text=f"Kekuatan password: {_strength_label_id(strength)}")

                if not all([fullname.strip(), username.strip(), email.strip(), password, confirm]):
                    st.error("Semua field wajib diisi.")
                    return

                username_clean = username.strip().lower()
                if len(username_clean) < 4:
                    st.error("Username minimal 4 karakter.")
                    return
                if not re.match(r"^[a-z0-9_]+$", username_clean):
                    st.error("Username hanya boleh huruf, angka, dan underscore (_).")
                    return

                if "@" not in email.strip():
                    st.error("Format email tidak valid.")
                    return

                if len(password) < 8:
                    st.error("Password minimal 8 karakter.")
                    return

                if password != confirm:
                    st.error("Konfirmasi password tidak cocok.")
                    return

                with st.spinner("Mendaftarkan akun..."):
                    success, message = register_user(fullname, username_clean, email, password)

                if success:
                    st.success("Akun berhasil dibuat! Silakan login.")
                    st.session_state.page = "login"
                    st.rerun()
                else:
                    st.error(message)

            st.markdown("---")
            st.markdown(
                "<p style='text-align:center;'>Sudah punya akun?</p>",
                unsafe_allow_html=True,
            )
            if st.button("Login di sini", use_container_width=True, key="go_login"):
                st.session_state.page = "login"
                st.rerun()

    except Exception as e:
        st.error(f"Terjadi kesalahan saat registrasi: {e}")


def render_register() -> None:
    """Alias lama — kompatibilitas dengan kode sebelumnya."""
    show_register_page()
