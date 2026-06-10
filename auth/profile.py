"""Halaman profil pengguna untuk dashboard analisis Telkom Group."""

from __future__ import annotations

import html
import re
from datetime import datetime
from io import BytesIO
from pathlib import Path
from typing import Any

import streamlit as st
from PIL import Image, ImageFile, ImageOps, UnidentifiedImageError

from auth.auth_utils import (
    get_user_by_id,
    update_password,
    update_profile,
    update_profile_picture,
)

# Konfigurasi keamanan pemrosesan gambar.
ImageFile.LOAD_TRUNCATED_IMAGES = False
Image.MAX_IMAGE_PIXELS = 25_000_000

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_AVATAR_PATH = PROJECT_ROOT / "assets" / "default_avatar.png"
MAX_AVATAR_SIZE_BYTES = 2 * 1024 * 1024
AVATAR_OUTPUT_SIZE = (200, 200)
ALLOWED_IMAGE_TYPES = {"image/jpeg", "image/jpg", "image/png"}
EMAIL_PATTERN = re.compile(r"^[A-Za-z0-9.!#$%&'*+/=?^_`{|}~-]+@[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)+$")

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


def _inject_profile_css() -> None:
    """Sisipkan CSS khusus halaman profil tanpa mengubah tema global."""
    try:
        st.markdown(
            """
            <style>
                .profile-card {
                    border: 1px solid var(--app-border, rgba(120, 130, 145, 0.25));
                    border-radius: 16px;
                    padding: 1.15rem;
                    background: var(--app-card, rgba(255, 255, 255, 0.04));
                    box-shadow: 0 10px 28px rgba(15, 23, 42, 0.06);
                    margin-bottom: 1rem;
                }

                .profile-user-name {
                    margin: 0.1rem 0 0.15rem 0;
                    font-size: 1.25rem;
                    font-weight: 800;
                    line-height: 1.35;
                    text-align: center;
                    overflow-wrap: anywhere;
                }

                .profile-username {
                    margin: 0 0 0.7rem 0;
                    color: var(--app-muted, #64748B);
                    font-size: 0.93rem;
                    text-align: center;
                    overflow-wrap: anywhere;
                }

                .profile-role-row {
                    display: flex;
                    justify-content: center;
                    margin-bottom: 0.85rem;
                }

                .profile-role-badge {
                    display: inline-flex;
                    align-items: center;
                    justify-content: center;
                    border-radius: 999px;
                    padding: 0.28rem 0.72rem;
                    color: #FFFFFF !important;
                    font-size: 0.76rem;
                    font-weight: 800;
                    letter-spacing: 0.02em;
                }

                .profile-role-admin {
                    background: #E53935;
                }

                .profile-role-user {
                    background: #1DA1F2;
                }

                .profile-member-box {
                    border-top: 1px solid var(--app-border, rgba(120, 130, 145, 0.25));
                    padding-top: 0.8rem;
                    color: var(--app-muted, #64748B);
                    font-size: 0.84rem;
                    text-align: center;
                }

                .profile-section-title {
                    margin: 0.15rem 0 0.3rem 0;
                    font-size: 1.05rem;
                    font-weight: 800;
                }

                .profile-section-note {
                    margin: 0 0 0.85rem 0;
                    color: var(--app-muted, #64748B);
                    font-size: 0.86rem;
                    line-height: 1.55;
                }

                .password-strength-label {
                    display: flex;
                    justify-content: space-between;
                    align-items: center;
                    margin: 0.25rem 0 0.35rem 0;
                    color: var(--app-muted, #64748B);
                    font-size: 0.82rem;
                }

                .activity-placeholder {
                    border: 1px dashed var(--app-border, rgba(120, 130, 145, 0.35));
                    border-radius: 14px;
                    padding: 1.25rem;
                    text-align: center;
                    color: var(--app-muted, #64748B);
                    background: rgba(29, 161, 242, 0.035);
                }

                [data-testid="stImage"] img {
                    border-radius: 50%;
                    object-fit: cover;
                    box-shadow: 0 0 0 5px rgba(29, 161, 242, 0.12);
                }
            </style>
            """,
            unsafe_allow_html=True,
        )
    except Exception as error:
        st.error(f"Gaya halaman profil belum dapat dimuat: {error}")


def _set_flash(message: str, level: str = "success") -> None:
    """Simpan pesan sementara agar tetap tampil setelah halaman dimuat ulang."""
    try:
        st.session_state["profile_flash"] = {
            "message": str(message),
            "level": str(level),
        }
    except Exception as error:
        st.error(f"Pesan konfirmasi belum dapat disiapkan: {error}")


def _render_flash() -> None:
    """Tampilkan pesan sementara satu kali."""
    try:
        flash = st.session_state.pop("profile_flash", None)
        if not flash:
            return

        message = flash.get("message", "")
        level = flash.get("level", "success")
        if level == "error":
            st.error(message)
        elif level == "warning":
            st.warning(message)
        else:
            st.success(message)
    except Exception as error:
        st.error(f"Pesan konfirmasi belum dapat ditampilkan: {error}")


def _format_created_at(value: Any) -> str:
    """Ubah nilai created_at menjadi tanggal Indonesia yang mudah dibaca."""
    try:
        if value in (None, ""):
            return "Tanggal tidak tersedia"

        if isinstance(value, datetime):
            parsed = value
        else:
            raw_value = str(value).strip()
            parsed = None
            supported_formats = (
                "%Y-%m-%d %H:%M:%S",
                "%Y-%m-%dT%H:%M:%S",
                "%Y-%m-%d %H:%M:%S.%f",
                "%Y-%m-%d",
            )
            for date_format in supported_formats:
                try:
                    parsed = datetime.strptime(raw_value, date_format)
                    break
                except ValueError:
                    continue

            if parsed is None:
                return raw_value

        month_name = MONTH_NAMES_ID.get(parsed.month, str(parsed.month))
        return f"{parsed.day} {month_name} {parsed.year}, {parsed.strftime('%H:%M')}"
    except Exception as error:
        st.error(f"Tanggal akun belum dapat diformat: {error}")
        return "Tanggal tidak tersedia"


def _create_fallback_avatar(fullname: str) -> Image.Image:
    """Buat avatar sederhana ketika file avatar bawaan tidak tersedia."""
    try:
        # Avatar polos tetap aman digunakan tanpa ketergantungan font eksternal.
        del fullname
        return Image.new("RGB", AVATAR_OUTPUT_SIZE, color=(224, 235, 246))
    except Exception as error:
        st.error(f"Avatar pengganti belum dapat dibuat: {error}")
        return Image.new("RGB", (1, 1), color=(224, 235, 246))


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


def _load_current_avatar(user: dict[str, Any]) -> Image.Image:
    """Muat avatar BLOB pengguna atau gunakan assets/default_avatar.png."""
    try:
        profile_picture = user.get("profile_picture")
        if profile_picture:
            image_bytes = bytes(profile_picture)
            decoded_image = _decode_image_bytes(image_bytes)
            if decoded_image is not None:
                return decoded_image

        if DEFAULT_AVATAR_PATH.exists():
            with Image.open(DEFAULT_AVATAR_PATH) as image:
                image.load()
                normalized = ImageOps.exif_transpose(image).convert("RGB")
                return normalized.copy()

        return _create_fallback_avatar(str(user.get("fullname", "Pengguna")))
    except Exception as error:
        st.error(f"Avatar pengguna belum dapat dimuat: {error}")
        return _create_fallback_avatar(str(user.get("fullname", "Pengguna")))


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


def _validate_email(email: str) -> bool:
    """Periksa format dasar alamat email."""
    try:
        return bool(EMAIL_PATTERN.fullmatch(email.strip()))
    except Exception as error:
        st.error(f"Format email belum dapat diperiksa: {error}")
        return False


def _password_strength(password: str) -> tuple[float, str, str]:
    """Hitung nilai, label, dan catatan kekuatan password."""
    try:
        if not password:
            return 0.0, "Belum diisi", "Gunakan minimal 8 karakter."

        score = 0
        if len(password) >= 8:
            score += 1
        if len(password) >= 12:
            score += 1
        if any(character.islower() for character in password):
            score += 1
        if any(character.isupper() for character in password):
            score += 1
        if any(character.isdigit() for character in password):
            score += 1
        if any(not character.isalnum() for character in password):
            score += 1

        if len(password) < 8 or score <= 2:
            return 0.33, "Lemah", "Tambahkan huruf besar, angka, atau simbol."
        if score <= 4:
            return 0.66, "Sedang", "Sudah cukup, tetapi masih dapat diperkuat."
        return 1.0, "Kuat", "Kombinasi password sudah baik."
    except Exception as error:
        st.error(f"Kekuatan password belum dapat dihitung: {error}")
        return 0.0, "Tidak diketahui", "Periksa kembali password."


def _render_user_identity(user: dict[str, Any]) -> None:
    """Tampilkan nama, username, role, dan tanggal pembuatan akun."""
    try:
        fullname = html.escape(str(user.get("fullname") or "Pengguna"))
        username = html.escape(str(user.get("username") or "pengguna"))
        role = str(user.get("role") or "user").strip().lower()
        role_label = "Admin" if role == "admin" else "User"
        role_class = "profile-role-admin" if role == "admin" else "profile-role-user"
        created_at = html.escape(_format_created_at(user.get("created_at")))

        st.markdown(
            f"""
            <div class="profile-card">
                <div class="profile-user-name">{fullname}</div>
                <div class="profile-username">@{username}</div>
                <div class="profile-role-row">
                    <span class="profile-role-badge {role_class}">{role_label}</span>
                </div>
                <div class="profile-member-box">
                    <strong>Member sejak</strong><br>
                    {created_at}
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )
    except Exception as error:
        st.error(f"Informasi pengguna belum dapat ditampilkan: {error}")


def _render_avatar_section(user_id: int, user: dict[str, Any]) -> None:
    """Tampilkan avatar, upload, preview, validasi, dan penyimpanan foto."""
    try:
        current_avatar = _load_current_avatar(user)
        st.image(current_avatar, width=200, caption="Foto profil saat ini")
        _render_user_identity(user)

        st.markdown('<div class="profile-section-title">📷 Ubah Foto Profil</div>', unsafe_allow_html=True)
        st.markdown(
            '<div class="profile-section-note">Pilih file JPG atau PNG. Ukuran maksimal 2 MB. Foto akan dipotong dan disimpan otomatis menjadi 200 × 200 piksel.</div>',
            unsafe_allow_html=True,
        )

        uploader_version = int(st.session_state.get("profile_uploader_version", 0))
        uploaded_file = st.file_uploader(
            "Pilih foto",
            type=["jpg", "jpeg", "png"],
            accept_multiple_files=False,
            key=f"profile_photo_uploader_{uploader_version}",
            help="Gunakan gambar persegi agar hasil potongan lebih rapi.",
        )

        if uploaded_file is None:
            return

        raw_bytes = uploaded_file.getvalue()
        file_size = len(raw_bytes)
        mime_type = str(getattr(uploaded_file, "type", "") or "").lower()

        if file_size > MAX_AVATAR_SIZE_BYTES:
            st.error(
                f"Ukuran foto {file_size / (1024 * 1024):.2f} MB. Batas maksimal adalah 2 MB."
            )
            return

        if file_size == 0:
            st.error("File foto kosong. Silakan pilih file lain.")
            return

        if mime_type and mime_type not in ALLOWED_IMAGE_TYPES:
            st.error("Format file tidak didukung. Gunakan JPG, JPEG, atau PNG.")
            return

        try:
            processed_bytes, preview_image = _prepare_avatar(raw_bytes)
        except ValueError as error:
            st.error(str(error))
            return

        st.markdown("**Preview sebelum disimpan**")
        st.image(preview_image, width=200, caption="Hasil akhir 200 × 200 piksel")
        st.caption(f"Ukuran file awal: {file_size / 1024:.1f} KB")

        if st.button(
            "💾 Simpan Foto",
            type="primary",
            use_container_width=True,
            key="save_profile_photo_button",
        ):
            try:
                with st.spinner("Menyimpan foto profil..."):
                    saved = update_profile_picture(user_id, processed_bytes)

                if not saved:
                    st.error("Foto profil gagal disimpan ke database.")
                    return

                st.session_state["profile_uploader_version"] = uploader_version + 1
                _set_flash("Foto profil berhasil diperbarui.", "success")
                st.rerun()
            except Exception as error:
                st.error(f"Foto profil gagal disimpan: {error}")
    except Exception as error:
        st.error(f"Bagian foto profil belum dapat ditampilkan: {error}")


def _render_edit_profile_tab(user_id: int, user: dict[str, Any]) -> None:
    """Tampilkan form untuk mengubah nama lengkap dan email."""
    try:
        st.markdown("### ✏️ Edit Profil")
        st.caption("Perbarui identitas akun yang ditampilkan pada dashboard.")

        with st.form("edit_profile_form", clear_on_submit=False):
            fullname = st.text_input(
                "Nama Lengkap",
                value=str(user.get("fullname") or ""),
                max_chars=100,
                placeholder="Masukkan nama lengkap",
            )
            email = st.text_input(
                "Email",
                value=str(user.get("email") or ""),
                max_chars=150,
                placeholder="nama@contoh.com",
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

        if not cleaned_fullname:
            st.error("Nama lengkap wajib diisi.")
            return
        if len(cleaned_fullname) < 2:
            st.error("Nama lengkap minimal 2 karakter.")
            return
        if not cleaned_email:
            st.error("Email wajib diisi.")
            return
        if not _validate_email(cleaned_email):
            st.error("Format email tidak valid. Contoh yang benar: nama@contoh.com")
            return

        with st.spinner("Menyimpan perubahan profil..."):
            success, message = update_profile(user_id, cleaned_fullname, cleaned_email)

        if not success:
            st.error(message)
            return

        st.session_state["fullname"] = cleaned_fullname
        _set_flash(message or "Profil berhasil diperbarui.", "success")
        st.rerun()
    except Exception as error:
        st.error(f"Form edit profil belum dapat diproses: {error}")


def _reset_password_widget_state() -> None:
    """Kosongkan nilai widget password sebelum widget dibuat kembali."""
    try:
        if not st.session_state.pop("profile_reset_password_fields", False):
            return

        st.session_state["profile_old_password"] = ""
        st.session_state["profile_new_password"] = ""
        st.session_state["profile_confirm_password"] = ""
        st.session_state["profile_show_password"] = False
    except Exception as error:
        st.error(f"Kolom password belum dapat dikosongkan: {error}")


def _render_password_tab(user_id: int) -> None:
    """Tampilkan form ganti password dengan indikator kekuatan."""
    try:
        _reset_password_widget_state()

        st.markdown("### 🔐 Ganti Password")
        st.caption("Gunakan password yang berbeda dari password lama dan mudah Anda ingat.")

        show_password = st.toggle(
            "Tampilkan password",
            value=False,
            key="profile_show_password",
            help="Aktifkan untuk melihat isi ketiga kolom password.",
        )
        input_type = "default" if show_password else "password"

        with st.container(border=True):
            old_password = st.text_input(
                "Password Lama",
                type=input_type,
                key="profile_old_password",
                placeholder="Masukkan password saat ini",
            )
            new_password = st.text_input(
                "Password Baru",
                type=input_type,
                key="profile_new_password",
                placeholder="Minimal 8 karakter",
            )

            strength_value, strength_label, strength_note = _password_strength(new_password)
            st.markdown(
                f"""
                <div class="password-strength-label">
                    <span>Kekuatan password</span>
                    <strong>{html.escape(strength_label)}</strong>
                </div>
                """,
                unsafe_allow_html=True,
            )
            st.progress(strength_value)
            st.caption(strength_note)

            confirm_password = st.text_input(
                "Konfirmasi Password Baru",
                type=input_type,
                key="profile_confirm_password",
                placeholder="Ketik ulang password baru",
            )

            password_submitted = st.button(
                "🔒 Perbarui Password",
                type="primary",
                use_container_width=True,
                key="update_profile_password_button",
            )

        if not password_submitted:
            return

        if not old_password:
            st.error("Password lama wajib diisi.")
            return
        if not new_password:
            st.error("Password baru wajib diisi.")
            return
        if len(new_password) < 8:
            st.error("Password baru minimal 8 karakter.")
            return
        if new_password != confirm_password:
            st.error("Konfirmasi password baru tidak cocok.")
            return
        if old_password == new_password:
            st.error("Password baru harus berbeda dari password lama.")
            return

        with st.spinner("Memverifikasi dan memperbarui password..."):
            success, message = update_password(user_id, old_password, new_password)

        if not success:
            st.error(message)
            return

        st.session_state["profile_reset_password_fields"] = True
        _set_flash(message or "Password berhasil diperbarui.", "success")
        st.rerun()
    except Exception as error:
        st.error(f"Form ganti password belum dapat diproses: {error}")


def _render_activity_tab(user: dict[str, Any]) -> None:
    """Tampilkan informasi pembuatan akun dan placeholder aktivitas."""
    try:
        created_at = _format_created_at(user.get("created_at"))

        st.markdown("### 🕘 Aktivitas Akun")
        st.info(f"Akun dibuat pada {created_at}")
        st.markdown(
            """
            <div class="activity-placeholder">
                <div style="font-size:2rem;margin-bottom:0.45rem;">📋</div>
                <strong>Riwayat aktivitas segera tersedia</strong><br>
                <span>Bagian ini telah disiapkan untuk menampilkan aktivitas login, perubahan profil, dan penggunaan fitur dashboard pada pengembangan berikutnya.</span>
            </div>
            """,
            unsafe_allow_html=True,
        )
    except Exception as error:
        st.error(f"Aktivitas akun belum dapat ditampilkan: {error}")


def render_profile() -> None:
    """Render halaman profil pengguna dengan avatar, data akun, dan keamanan."""
    try:
        from utils.css_loader import render_page_header

        render_page_header(
            "👤 Profil Pengguna",
            "Kelola identitas akun, foto profil, dan keamanan password Anda.",
        )
        _inject_profile_css()
        _render_flash()

        user_id = st.session_state.get("user_id")
        if not user_id:
            st.error("Sesi pengguna tidak valid. Silakan logout lalu login kembali.")
            return

        user = get_user_by_id(int(user_id))
        if user is None:
            st.error("Data pengguna tidak ditemukan di database.")
            return

        left_column, right_column = st.columns([1, 2], gap="large")

        with left_column:
            _render_avatar_section(int(user_id), user)

        with right_column:
            edit_tab, password_tab, activity_tab = st.tabs(
                ["✏️ Edit Profil", "🔐 Ganti Password", "🕘 Aktivitas"]
            )

            with edit_tab:
                _render_edit_profile_tab(int(user_id), user)

            with password_tab:
                _render_password_tab(int(user_id))

            with activity_tab:
                _render_activity_tab(user)
    except Exception as error:
        st.error(f"Terjadi kesalahan pada halaman profil: {error}")
