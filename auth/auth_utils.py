"""Utilitas autentikasi dan manajemen database pengguna SQLite."""

import hashlib
import secrets
import sqlite3
from datetime import datetime, timedelta
from io import BytesIO
from pathlib import Path

import bcrypt
from PIL import Image

DB_DIR = "database"
DB_NAME = "users.db"
REMEMBER_ME_HOURS = 72  # 3 hari — sesi "Ingat Saya" di browser
ADMIN_SEED = {
    "fullname": "Administrator",
    "username": "admin",
    "email": "admin@dashboard.local",
    "password": "admin123",
    "role": "admin",
}


def get_db_path() -> str:
    """Return path absolut ke database/users.db."""
    base = Path(__file__).resolve().parent.parent
    db_dir = base / DB_DIR
    db_dir.mkdir(parents=True, exist_ok=True)
    return str(db_dir / DB_NAME)


def _row_to_dict(row: sqlite3.Row | None) -> dict | None:
    """Konversi sqlite3.Row ke dictionary."""
    if row is None:
        return None
    return dict(row)


def init_db() -> None:
    """Buat tabel users dan seed akun admin jika belum ada."""
    try:
        with sqlite3.connect(get_db_path()) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS users (
                    user_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    fullname TEXT NOT NULL,
                    username TEXT UNIQUE NOT NULL,
                    email TEXT UNIQUE NOT NULL,
                    password_hash TEXT NOT NULL,
                    role TEXT DEFAULT 'user',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    profile_picture BLOB
                )
                """
            )
            cursor.execute(
                "SELECT user_id FROM users WHERE username = ?",
                (ADMIN_SEED["username"],),
            )
            if cursor.fetchone() is None:
                password_hash = hash_password(ADMIN_SEED["password"])
                cursor.execute(
                    """
                    INSERT INTO users (fullname, username, email, password_hash, role)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (
                        ADMIN_SEED["fullname"],
                        ADMIN_SEED["username"],
                        ADMIN_SEED["email"],
                        password_hash,
                        ADMIN_SEED["role"],
                    ),
                )
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS remember_tokens (
                    token_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    token_hash TEXT NOT NULL UNIQUE,
                    expires_at TIMESTAMP NOT NULL,
                    FOREIGN KEY (user_id) REFERENCES users(user_id)
                )
                """
            )
            conn.commit()
    except Exception as e:
        print(f"[init_db] Error: {e}")
        raise RuntimeError(f"Gagal inisialisasi database: {e}") from e


def hash_password(password: str) -> str:
    """Enkripsi password dengan bcrypt, return hash sebagai string."""
    try:
        hashed = bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt())
        return hashed.decode("utf-8")
    except Exception as e:
        print(f"[hash_password] Error: {e}")
        return ""


def verify_password(password: str, hashed: str) -> bool:
    """Verifikasi password terhadap hash bcrypt."""
    try:
        return bcrypt.checkpw(password.encode("utf-8"), hashed.encode("utf-8"))
    except Exception as e:
        print(f"[verify_password] Error: {e}")
        return False


def get_user(username: str) -> dict | None:
    """Ambil data user berdasarkan username."""
    try:
        with sqlite3.connect(get_db_path()) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM users WHERE username = ?",
                (username.strip().lower(),),
            )
            return _row_to_dict(cursor.fetchone())
    except Exception as e:
        print(f"[get_user] Error: {e}")
        return None


def get_user_by_id(user_id: int) -> dict | None:
    """Ambil data user berdasarkan user_id."""
    try:
        with sqlite3.connect(get_db_path()) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
            return _row_to_dict(cursor.fetchone())
    except Exception as e:
        print(f"[get_user_by_id] Error: {e}")
        return None


def create_user(
    fullname: str, username: str, email: str, password: str
) -> tuple[bool, str]:
    """Buat akun user baru dengan cek duplikat username dan email."""
    try:
        username = username.strip().lower()
        email = email.strip().lower()
        fullname = fullname.strip()

        with sqlite3.connect(get_db_path()) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            cursor.execute("SELECT user_id FROM users WHERE username = ?", (username,))
            if cursor.fetchone():
                return False, "Username sudah digunakan"

            cursor.execute("SELECT user_id FROM users WHERE email = ?", (email,))
            if cursor.fetchone():
                return False, "Email sudah terdaftar"

            password_hash = hash_password(password)
            if not password_hash:
                return False, "Gagal mengenkripsi password"

            cursor.execute(
                """
                INSERT INTO users (fullname, username, email, password_hash, role)
                VALUES (?, ?, ?, ?, 'user')
                """,
                (fullname, username, email, password_hash),
            )
            conn.commit()
        return True, "Akun berhasil dibuat"
    except Exception as e:
        print(f"[create_user] Error: {e}")
        return False, f"Gagal membuat akun: {e}"


def update_user_profile(user_id: int, fullname: str, email: str) -> tuple[bool, str]:
    """Perbarui fullname dan email user."""
    try:
        email = email.strip().lower()
        fullname = fullname.strip()

        with sqlite3.connect(get_db_path()) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            cursor.execute(
                "SELECT user_id FROM users WHERE email = ? AND user_id != ?",
                (email, user_id),
            )
            if cursor.fetchone():
                return False, "Email sudah terdaftar"

            cursor.execute(
                "UPDATE users SET fullname = ?, email = ? WHERE user_id = ?",
                (fullname, email, user_id),
            )
            if cursor.rowcount == 0:
                return False, "User tidak ditemukan"
            conn.commit()
        return True, "Profil berhasil diperbarui"
    except Exception as e:
        print(f"[update_user_profile] Error: {e}")
        return False, f"Gagal memperbarui profil: {e}"


def _save_password(user_id: int, new_password: str) -> tuple[bool, str]:
    """Simpan hash password baru ke database (tanpa verifikasi password lama)."""
    try:
        password_hash = hash_password(new_password)
        if not password_hash:
            return False, "Gagal mengenkripsi password"

        with sqlite3.connect(get_db_path()) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "UPDATE users SET password_hash = ? WHERE user_id = ?",
                (password_hash, user_id),
            )
            if cursor.rowcount == 0:
                return False, "User tidak ditemukan"
            conn.commit()
        return True, "Password berhasil diubah"
    except Exception as e:
        print(f"[_save_password] Error: {e}")
        return False, f"Gagal mengubah password: {e}"


def update_password(
    user_id: int, old_password: str, new_password: str
) -> tuple[bool, str]:
    """Ganti password setelah verifikasi password lama (untuk halaman profil)."""
    try:
        if len(new_password) < 8:
            return False, "Password baru minimal 8 karakter."

        user = get_user_by_id(user_id)
        if user is None:
            return False, "User tidak ditemukan."

        if not verify_password(old_password, user["password_hash"]):
            return False, "Password lama tidak sesuai."

        return _save_password(user_id, new_password)
    except Exception as e:
        print(f"[update_password] Error: {e}")
        return False, f"Gagal mengubah password: {e}"


def update_profile_picture(user_id: int, image_bytes: bytes) -> bool:
    """Simpan gambar profil sebagai BLOB ke database."""
    try:
        with sqlite3.connect(get_db_path()) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "UPDATE users SET profile_picture = ? WHERE user_id = ?",
                (image_bytes, user_id),
            )
            if cursor.rowcount == 0:
                return False
            conn.commit()
        return True
    except Exception as e:
        print(f"[update_profile_picture] Error: {e}")
        return False


def get_all_users() -> list[dict]:
    """Ambil semua user, urut dari yang terbaru daftar."""
    try:
        with sqlite3.connect(get_db_path()) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT user_id, fullname, username, email, role, created_at
                FROM users
                ORDER BY created_at DESC
                """
            )
            return [_row_to_dict(row) for row in cursor.fetchall()]
    except Exception as e:
        print(f"[get_all_users] Error: {e}")
        return []


def delete_user(user_id: int) -> tuple[bool, str]:
    """Hapus user; admin utama (user_id=1) tidak boleh dihapus."""
    try:
        if user_id == 1:
            return False, "Admin utama tidak dapat dihapus"

        with sqlite3.connect(get_db_path()) as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM users WHERE user_id = ?", (user_id,))
            if cursor.rowcount == 0:
                return False, "User tidak ditemukan"
            conn.commit()
        return True, "User berhasil dihapus"
    except Exception as e:
        print(f"[delete_user] Error: {e}")
        return False, f"Gagal menghapus user: {e}"


def get_user_stats() -> dict:
    """Ambil statistik jumlah user untuk dashboard admin."""
    try:
        with sqlite3.connect(get_db_path()) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            cursor.execute("SELECT COUNT(*) AS total FROM users")
            total_users = cursor.fetchone()["total"]

            cursor.execute("SELECT COUNT(*) AS total FROM users WHERE role = 'admin'")
            total_admin = cursor.fetchone()["total"]

            cursor.execute("SELECT COUNT(*) AS total FROM users WHERE role = 'user'")
            total_regular = cursor.fetchone()["total"]

            cursor.execute(
                """
                SELECT username FROM users
                ORDER BY created_at DESC
                LIMIT 1
                """
            )
            latest_row = cursor.fetchone()
            latest_user = latest_row["username"] if latest_row else None

        return {
            "total_users": total_users,
            "total_admin": total_admin,
            "total_regular": total_regular,
            "latest_user": latest_user,
        }
    except Exception as e:
        print(f"[get_user_stats] Error: {e}")
        return {
            "total_users": 0,
            "total_admin": 0,
            "total_regular": 0,
            "latest_user": None,
        }


def _hash_token(token: str) -> str:
    """Hash token remember-me untuk disimpan di database."""
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def create_remember_token(user_id: int) -> str | None:
    """Buat token remember-me dan simpan hash-nya di database."""
    try:
        token = secrets.token_urlsafe(32)
        token_hash = _hash_token(token)
        expires_at = datetime.now() + timedelta(hours=REMEMBER_ME_HOURS)

        with sqlite3.connect(get_db_path()) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "DELETE FROM remember_tokens WHERE user_id = ?",
                (user_id,),
            )
            cursor.execute(
                """
                INSERT INTO remember_tokens (user_id, token_hash, expires_at)
                VALUES (?, ?, ?)
                """,
                (user_id, token_hash, expires_at.isoformat()),
            )
            conn.commit()
        return token
    except Exception as e:
        print(f"[create_remember_token] Error: {e}")
        return None


def validate_remember_token(token: str) -> dict | None:
    """Validasi token remember-me dan kembalikan data user jika masih aktif."""
    try:
        if not token:
            return None

        token_hash = _hash_token(token)
        with sqlite3.connect(get_db_path()) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT user_id, expires_at FROM remember_tokens
                WHERE token_hash = ?
                """,
                (token_hash,),
            )
            row = cursor.fetchone()
            if row is None:
                return None

            expires_at = datetime.fromisoformat(str(row["expires_at"]))
            if datetime.now() > expires_at:
                cursor.execute(
                    "DELETE FROM remember_tokens WHERE token_hash = ?",
                    (token_hash,),
                )
                conn.commit()
                return None

        user = get_user_by_id(row["user_id"])
        if user is None:
            revoke_remember_token(token)
        return user
    except Exception as e:
        print(f"[validate_remember_token] Error: {e}")
        return None


def revoke_remember_token(token: str) -> bool:
    """Hapus satu token remember-me dari database."""
    try:
        if not token:
            return False
        token_hash = _hash_token(token)
        with sqlite3.connect(get_db_path()) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "DELETE FROM remember_tokens WHERE token_hash = ?",
                (token_hash,),
            )
            conn.commit()
        return True
    except Exception as e:
        print(f"[revoke_remember_token] Error: {e}")
        return False


def revoke_all_remember_tokens(user_id: int) -> bool:
    """Hapus semua token remember-me milik satu user."""
    try:
        with sqlite3.connect(get_db_path()) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "DELETE FROM remember_tokens WHERE user_id = ?",
                (user_id,),
            )
            conn.commit()
        return True
    except Exception as e:
        print(f"[revoke_all_remember_tokens] Error: {e}")
        return False


# ---------------------------------------------------------------------------
# Wrapper & fungsi tambahan (kompatibilitas UI yang sudah ada)
# ---------------------------------------------------------------------------


def verify_login(username: str, password: str) -> dict | None:
    """Verifikasi login; kembalikan data user jika username dan password cocok."""
    try:
        user = get_user(username)
        if user is None:
            return None
        if verify_password(password, user["password_hash"]):
            return user
        return None
    except Exception as e:
        print(f"[verify_login] Error: {e}")
        return None


def register_user(
    fullname: str, username: str, email: str, password: str
) -> tuple[bool, str]:
    """Registrasi user baru (wrapper create_user dengan validasi tambahan)."""
    try:
        if len(password) < 8:
            return False, "Password minimal 8 karakter."
        if " " in username.strip():
            return False, "Username tidak boleh mengandung spasi."

        success, message = create_user(fullname, username, email, password)
        if success:
            return True, "Registrasi berhasil. Silakan login."
        return False, message
    except Exception as e:
        print(f"[register_user] Error: {e}")
        return False, f"Registrasi gagal: {e}"


def update_profile(user_id: int, fullname: str, email: str) -> tuple[bool, str]:
    """Wrapper update_user_profile untuk halaman profil."""
    return update_user_profile(user_id, fullname, email)


def _resize_avatar(image_bytes: bytes) -> bytes:
    """Resize gambar avatar ke 200x200 pixel."""
    img = Image.open(BytesIO(image_bytes)).convert("RGB")
    img = img.resize((200, 200), Image.Resampling.LANCZOS)
    buffer = BytesIO()
    img.save(buffer, format="PNG")
    return buffer.getvalue()


def update_avatar(user_id: int, image_bytes: bytes) -> tuple[bool, str]:
    """Simpan avatar setelah validasi ukuran dan resize."""
    try:
        if len(image_bytes) > 2 * 1024 * 1024:
            return False, "Ukuran file maksimal 2MB."

        resized = _resize_avatar(image_bytes)
        if update_profile_picture(user_id, resized):
            return True, "Avatar berhasil diperbarui."
        return False, "Gagal menyimpan avatar."
    except Exception as e:
        print(f"[update_avatar] Error: {e}")
        return False, f"Gagal menyimpan avatar: {e}"


def update_user_role(user_id: int, new_role: str) -> tuple[bool, str]:
    """Ubah role user dengan proteksi admin utama."""
    try:
        if user_id == 1:
            return False, "Admin utama (user_id=1) tidak boleh diubah rolenya."
        if new_role not in ("user", "admin"):
            return False, "Role tidak valid."

        with sqlite3.connect(get_db_path()) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "UPDATE users SET role = ? WHERE user_id = ?",
                (new_role, user_id),
            )
            if cursor.rowcount == 0:
                return False, "User tidak ditemukan"
            conn.commit()
        return True, "Role berhasil diperbarui."
    except Exception as e:
        print(f"[update_user_role] Error: {e}")
        return False, f"Gagal mengubah role: {e}"


def admin_create_user(
    fullname: str, username: str, email: str, password: str, role: str = "user"
) -> tuple[bool, str]:
    """Buat akun user baru oleh admin dengan role pilihan."""
    try:
        if role not in ("user", "admin"):
            return False, "Role tidak valid."

        success, message = create_user(fullname, username, email, password)
        if not success:
            return False, message

        with sqlite3.connect(get_db_path()) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "UPDATE users SET role = ? WHERE username = ?",
                (role, username.strip().lower()),
            )
            conn.commit()
        return True, "Akun baru berhasil dibuat."
    except Exception as e:
        print(f"[admin_create_user] Error: {e}")
        return False, f"Gagal membuat akun: {e}"


def format_created_at(value) -> str:
    """Format timestamp created_at untuk tampilan di tabel."""
    try:
        if value is None:
            return "-"
        if isinstance(value, str):
            return value
        return datetime.fromisoformat(str(value)).strftime("%d-%m-%Y %H:%M")
    except Exception as e:
        print(f"[format_created_at] Error: {e}")
        return "-"
