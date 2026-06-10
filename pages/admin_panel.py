"""Panel admin untuk manajemen pengguna dan status sistem."""

from datetime import datetime
from pathlib import Path

import pandas as pd
import streamlit as st

from auth.auth_utils import (
    admin_create_user,
    delete_user,
    format_created_at,
    get_all_users,
    update_user_role,
)
from utils.css_loader import render_page_header
from utils.data_loader import DATA_FILES, get_data_status


def render_admin_panel() -> None:
    """Menampilkan panel admin jika role pengguna adalah admin."""
    try:
        if st.session_state.get("role") != "admin":
            st.error("⛔ Akses ditolak. Halaman ini hanya untuk administrator.")
            return

        render_page_header("⚙️ Admin Panel", "Manajemen pengguna dan status sistem")

        tab1, tab2, tab3 = st.tabs(["Manajemen Pengguna", "Status Sistem", "Log Aktivitas"])

        with tab1:
            users = get_all_users()
            if users:
                display = []
                for u in users:
                    display.append({
                        "ID": u["user_id"],
                        "Nama": u["fullname"],
                        "Username": u["username"],
                        "Email": u["email"],
                        "Role": u["role"],
                        "Dibuat": format_created_at(u.get("created_at")),
                    })
                st.dataframe(pd.DataFrame(display), use_container_width=True, hide_index=True)

            st.subheader("Ubah Role User")
            with st.form("change_role_form"):
                role_user_id = st.number_input("User ID", min_value=1, step=1)
                new_role = st.selectbox("Role Baru", ["user", "admin"])
                if st.form_submit_button("Ubah Role"):
                    ok, msg = update_user_role(int(role_user_id), new_role)
                    st.success(msg) if ok else st.error(msg)
                    if ok:
                        st.rerun()

            st.subheader("Hapus User")
            with st.form("delete_user_form"):
                del_user_id = st.number_input("User ID untuk dihapus", min_value=2, step=1, key="del_uid")
                if st.form_submit_button("Hapus User"):
                    ok, msg = delete_user(int(del_user_id))
                    st.success(msg) if ok else st.error(msg)
                    if ok:
                        st.rerun()

            st.subheader("Tambah User Baru")
            with st.form("create_user_form"):
                c_fullname = st.text_input("Nama Lengkap")
                c_username = st.text_input("Username")
                c_email = st.text_input("Email")
                c_password = st.text_input("Password", type="password")
                c_role = st.selectbox("Role", ["user", "admin"], key="new_role")
                if st.form_submit_button("Buat Akun"):
                    ok, msg = admin_create_user(c_fullname, c_username, c_email, c_password, c_role)
                    st.success(msg) if ok else st.error(msg)
                    if ok:
                        st.rerun()

        with tab2:
            all_users = get_all_users()
            admins = [u for u in all_users if u["role"] == "admin"]
            st.metric("Total User", len(all_users))
            st.metric("Total Admin", len(admins))

            st.subheader("Status File Data")
            for layanan in ["IndiHome", "IndiBiz", "Telkomsel"]:
                status = get_data_status(layanan)
                sent_icon = "✅" if status["sentiment_exists"] else "❌"
                sna_icon = "✅" if status["sna_exists"] else "❌"
                st.markdown(
                    f"**{layanan}** — Sentimen: {sent_icon} ({status['sentiment_rows']} baris) | "
                    f"SNA: {sna_icon} ({status['sna_edges']} edge) | "
                    f"Terakhir diubah: {status['last_modified']}"
                )

            st.subheader("Status Model")
            st.markdown("✅ IndiHome — READY")
            st.markdown("⏳ IndiBiz — Coming Soon")
            st.markdown("⏳ Telkomsel — Coming Soon")

            st.subheader("Info Server")
            root = Path(__file__).resolve().parent.parent
            for layanan, paths in DATA_FILES.items():
                for key, rel in paths.items():
                    full = root / rel
                    st.caption(f"{layanan}/{key}: {'Ada' if full.exists() else 'Belum ada'} — {full}")

            st.caption(f"Waktu server: {datetime.now().strftime('%d-%m-%Y %H:%M:%S')}")
            st.caption("Versi aplikasi: 1.0.0")

        with tab3:
            st.info("Log aktivitas akan tersedia pada versi berikutnya.")

    except Exception as e:
        st.error(f"Gagal memuat panel admin: {e}")
