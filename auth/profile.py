"""Halaman profil pengguna."""

import streamlit as st

from auth.auth_utils import get_user_by_id, update_avatar, update_password, update_profile


def render_profile() -> None:
    """Menampilkan halaman edit profil, password, dan avatar."""
    try:
        from utils.css_loader import render_page_header

        render_page_header("👤 Profil Pengguna", "Kelola informasi akun Anda")

        user_id = st.session_state.get("user_id")
        if not user_id:
            st.error("Sesi tidak valid. Silakan login kembali.")
            return

        user = get_user_by_id(user_id)
        if user is None:
            st.error("Data pengguna tidak ditemukan.")
            return

        tab1, tab2, tab3 = st.tabs(["Edit Profil", "Ganti Password", "Ganti Avatar"])

        with tab1:
            with st.form("edit_profile_form"):
                new_fullname = st.text_input("Nama Lengkap", value=user.get("fullname", ""))
                new_email = st.text_input("Email", value=user.get("email", ""))
                if st.form_submit_button("Simpan Perubahan", use_container_width=True):
                    ok, msg = update_profile(user_id, new_fullname, new_email)
                    if ok:
                        st.session_state.fullname = new_fullname.strip()
                        st.success(msg)
                    else:
                        st.error(msg)

        with tab2:
            with st.form("change_password_form"):
                old_pw = st.text_input("Password Lama", type="password")
                new_pw = st.text_input("Password Baru", type="password")
                confirm_pw = st.text_input("Konfirmasi Password Baru", type="password")
                if st.form_submit_button("Ubah Password", use_container_width=True):
                    if new_pw != confirm_pw:
                        st.error("Konfirmasi password tidak cocok.")
                    else:
                        ok, msg = update_password(user_id, old_pw, new_pw)
                        st.success(msg) if ok else st.error(msg)

        with tab3:
            uploaded = st.file_uploader(
                "Upload Avatar (JPG/PNG, maks 2MB)",
                type=["jpg", "jpeg", "png"],
            )
            if uploaded is not None:
                if uploaded.size > 2 * 1024 * 1024:
                    st.error("Ukuran file maksimal 2MB.")
                else:
                    st.image(uploaded, caption="Preview Avatar", width=200)
                    if st.button("Simpan Avatar", use_container_width=True):
                        ok, msg = update_avatar(user_id, uploaded.getvalue())
                        st.success(msg) if ok else st.error(msg)
                        if ok:
                            st.rerun()

    except Exception as e:
        st.error(f"Terjadi kesalahan pada halaman profil: {e}")
