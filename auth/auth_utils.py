"""Utilitas autentikasi dan manajemen database pengguna SQLite."""

import hashlib
import logging
import secrets
import sqlite3
from datetime import datetime, timedelta
from io import BytesIO
from pathlib import Path

import bcrypt
from PIL import Image

from utils.access_control import (
    DEFAULT_ROLE,
    ROLE_DATA_ANALYST,
    ROLE_MANAGEMENT,
    ROLE_SOCIAL_MEDIA_OFFICER,
    VALID_ROLES,
    normalize_role,
)

LOGGER = logging.getLogger(__name__)

DB_DIR = "database"
DB_NAME = "users.db"
DB_PATH = Path(__file__).resolve().parent.parent / DB_DIR / DB_NAME
REMEMBER_ME_HOURS = 72  # 3 hari — sesi "Ingat Saya" di browser
ADMIN_SEED = {
    "fullname": "Administrator",
    "username": "admin",
    "email": "admin@dashboard.local",
    "password": "admin123",
    "role": ROLE_DATA_ANALYST,
}



def get_db_path() -> str:
    """Bangun path database dari lokasi folder proyek secara portabel."""
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    return str(DB_PATH)



def _connect_raw() -> sqlite3.Connection:
    """Buka koneksi SQLite dasar tanpa memanggil inisialisasi ulang."""
    conn = sqlite3.connect(get_db_path(), timeout=30)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    conn.execute("PRAGMA busy_timeout=30000")
    return conn



def _row_to_dict(row: sqlite3.Row | None) -> dict | None:
    """Konversi sqlite3.Row ke dictionary dan normalisasi role."""
    if row is None:
        return None
    data = dict(row)
    if "role" in data:
        data["role"] = normalize_role(data.get("role"), data.get("user_id"))
    return data



def _migrate_legacy_roles(cursor: sqlite3.Cursor) -> None:
    """Migrasikan role lama tanpa menghapus akun atau password pengguna."""
    # Role admin lama menjadi Data Analis. Role user lama dipindahkan ke
    # Manajemen sebagai role nonteknis dengan hak akses paling terbatas.
    cursor.execute(
        """
        UPDATE users
        SET role = ?
        WHERE LOWER(TRIM(COALESCE(role, ''))) IN (
            'admin', 'administrator', 'data analyst', 'data analis', 'data_analis'
        )
        """,
        (ROLE_DATA_ANALYST,),
    )
    cursor.execute(
        """
        UPDATE users
        SET role = ?
        WHERE LOWER(TRIM(COALESCE(role, ''))) IN (
            'user', 'researcher', 'manajemen'
        )
        """,
        (ROLE_MANAGEMENT,),
    )
    cursor.execute(
        """
        UPDATE users
        SET role = ?
        WHERE LOWER(TRIM(COALESCE(role, ''))) IN (
            'sosmed officer', 'sosmed_officer', 'social media officer'
        )
        """,
        (ROLE_SOCIAL_MEDIA_OFFICER,),
    )

    placeholders = ", ".join("?" for _ in VALID_ROLES)
    cursor.execute(
        f"UPDATE users SET role = ? WHERE role IS NULL OR role NOT IN ({placeholders})",
        (DEFAULT_ROLE, *VALID_ROLES),
    )

    # Pemilik database utama tidak boleh kehilangan akses pengelolaan pengguna.
    cursor.execute(
        "UPDATE users SET role = ? WHERE user_id = 1",
        (ROLE_DATA_ANALYST,),
    )



def _database_is_corrupt(error: Exception) -> bool:
    """Kenali error SQLite yang menandakan file database benar-benar rusak."""
    message = str(error).strip().lower()
    return any(
        marker in message
        for marker in (
            "database disk image is malformed",
            "file is not a database",
            "unsupported file format",
        )
    )



def _remove_corrupt_database() -> None:
    """Hapus file database rusak agar dapat dibuat ulang saat startup."""
    try:
        if DB_PATH.exists():
            DB_PATH.unlink()
    except Exception as error:
        LOGGER.exception("Database rusak tidak dapat dihapus: %s", error)
        raise RuntimeError(f"Database rusak tidak dapat dipulihkan: {error}") from error



def _create_schema_and_seed(conn: sqlite3.Connection) -> None:
    """Buat seluruh tabel inti dan seed admin pada satu transaksi."""
    cursor = conn.cursor()
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY AUTOINCREMENT,
            fullname TEXT NOT NULL,
            username TEXT UNIQUE NOT NULL,
            email TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            role TEXT DEFAULT 'management',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            profile_picture BLOB
        )
        """
    )

    # Hash bcrypt hanya dibuat ketika akun admin belum tersedia.
    cursor.execute(
        "SELECT user_id FROM users WHERE username = ?",
        (ADMIN_SEED["username"],),
    )
    if cursor.fetchone() is None:
        password_hash = hash_password(ADMIN_SEED["password"])
        if not password_hash:
            raise RuntimeError("Password admin default gagal dienkripsi.")
        # INSERT OR IGNORE tetap melindungi startup cloud yang berjalan paralel.
        cursor.execute(
            """
            INSERT OR IGNORE INTO users (fullname, username, email, password_hash, role)
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

    _migrate_legacy_roles(cursor)
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



def init_database() -> None:
    """Inisialisasi database cloud secara idempotent saat startup aplikasi.

    Folder dan file SQLite dibuat otomatis bila belum ada. Tabel pengguna,
    remember-me, audit, dan akun admin default juga dibuat satu kali tanpa
    menggandakan data ketika fungsi dipanggil berulang kali.
    """
    try:
        with _connect_raw() as conn:
            quick_check = conn.execute("PRAGMA quick_check").fetchone()
            if quick_check and str(quick_check[0]).lower() != "ok":
                raise sqlite3.DatabaseError(str(quick_check[0]))
            _create_schema_and_seed(conn)
    except sqlite3.DatabaseError as error:
        if not _database_is_corrupt(error):
            LOGGER.exception("Inisialisasi database gagal: %s", error)
            raise RuntimeError(f"Gagal inisialisasi database: {error}") from error

        LOGGER.warning("Database rusak terdeteksi dan akan dibuat ulang: %s", error)
        _remove_corrupt_database()
        try:
            with _connect_raw() as conn:
                _create_schema_and_seed(conn)
        except Exception as retry_error:
            LOGGER.exception("Pemulihan database gagal: %s", retry_error)
            raise RuntimeError(f"Gagal memulihkan database: {retry_error}") from retry_error
    except Exception as error:
        LOGGER.exception("Inisialisasi database gagal: %s", error)
        raise RuntimeError(f"Gagal inisialisasi database: {error}") from error

    # Tabel audit dibuat setelah tabel users tersedia agar foreign key aman.
    try:
        from utils.audit_logger import ensure_audit_table

        ensure_audit_table()
    except Exception as audit_error:
        LOGGER.exception("Tabel audit belum dapat disiapkan: %s", audit_error)



def init_db() -> None:
    """Alias kompatibilitas untuk pemanggilan lama di modul dan skrip uji."""
    init_database()



def get_db_connection() -> sqlite3.Connection:
    """Kembalikan koneksi database yang siap dipakai dan pulihkan jika rusak."""
    conn: sqlite3.Connection | None = None
    try:
        conn = _connect_raw()
        quick_check = conn.execute("PRAGMA quick_check").fetchone()
        if quick_check and str(quick_check[0]).lower() != "ok":
            raise sqlite3.DatabaseError(str(quick_check[0]))

        users_table = conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name='users'"
        ).fetchone()
        if users_table is None:
            conn.close()
            conn = None
            init_database()
            return _connect_raw()
        return conn
    except sqlite3.DatabaseError as error:
        if conn is not None:
            conn.close()
        if not _database_is_corrupt(error):
            LOGGER.exception("Koneksi database gagal: %s", error)
            raise RuntimeError(f"Gagal membuka database: {error}") from error

        LOGGER.warning("Koneksi menemukan database rusak; melakukan pemulihan: %s", error)
        _remove_corrupt_database()
        init_database()
        return _connect_raw()
    except Exception as error:
        if conn is not None:
            conn.close()
        LOGGER.exception("Koneksi database gagal: %s", error)
        raise RuntimeError(f"Gagal membuka database: {error}") from error

def hash_password(password: str) -> str:
    """Enkripsi password dengan bcrypt, return hash sebagai string."""
    try:
        hashed = bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt())
        return hashed.decode("utf-8")
    except Exception as e:
        LOGGER.exception("hash_password gagal: %s", e)
        return ""


def verify_password(password: str, hashed: str) -> bool:
    """Verifikasi password terhadap hash bcrypt."""
    try:
        return bcrypt.checkpw(password.encode("utf-8"), hashed.encode("utf-8"))
    except Exception as e:
        LOGGER.exception("verify_password gagal: %s", e)
        return False


def get_user(username: str) -> dict | None:
    """Ambil data user berdasarkan username."""
    try:
        with get_db_connection() as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM users WHERE username = ?",
                (username.strip().lower(),),
            )
            return _row_to_dict(cursor.fetchone())
    except Exception as e:
        LOGGER.exception("get_user gagal: %s", e)
        return None


def get_user_by_id(user_id: int) -> dict | None:
    """Ambil data user berdasarkan user_id."""
    try:
        with get_db_connection() as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
            return _row_to_dict(cursor.fetchone())
    except Exception as e:
        LOGGER.exception("get_user_by_id gagal: %s", e)
        return None


def create_user(
    fullname: str, username: str, email: str, password: str
) -> tuple[bool, str]:
    """Buat akun user baru dengan cek duplikat username dan email."""
    try:
        username = username.strip().lower()
        email = email.strip().lower()
        fullname = fullname.strip()

        with get_db_connection() as conn:
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
                VALUES (?, ?, ?, ?, ?)
                """,
                (fullname, username, email, password_hash, DEFAULT_ROLE),
            )
            conn.commit()
        return True, "Akun berhasil dibuat"
    except Exception as e:
        LOGGER.exception("create_user gagal: %s", e)
        return False, f"Gagal membuat akun: {e}"


def update_user_profile(user_id: int, fullname: str, email: str) -> tuple[bool, str]:
    """Perbarui fullname dan email user."""
    try:
        email = email.strip().lower()
        fullname = fullname.strip()

        with get_db_connection() as conn:
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
        LOGGER.exception("update_user_profile gagal: %s", e)
        return False, f"Gagal memperbarui profil: {e}"


def _save_password(user_id: int, new_password: str) -> tuple[bool, str]:
    """Simpan hash password baru ke database (tanpa verifikasi password lama)."""
    try:
        password_hash = hash_password(new_password)
        if not password_hash:
            return False, "Gagal mengenkripsi password"

        with get_db_connection() as conn:
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
        LOGGER.exception("_save_password gagal: %s", e)
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
        LOGGER.exception("update_password gagal: %s", e)
        return False, f"Gagal mengubah password: {e}"


def update_profile_picture(user_id: int, image_bytes: bytes) -> bool:
    """Simpan gambar profil sebagai BLOB ke database."""
    try:
        with get_db_connection() as conn:
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
        LOGGER.exception("update_profile_picture gagal: %s", e)
        return False


def get_all_users() -> list[dict]:
    """Ambil semua user, urut dari yang terbaru daftar."""
    try:
        with get_db_connection() as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT user_id, fullname, username, email, role, created_at
                FROM users
                ORDER BY created_at DESC
                """
            )
            return [
                user
                for row in cursor.fetchall()
                if (user := _row_to_dict(row)) is not None
            ]
    except Exception as e:
        LOGGER.exception("get_all_users gagal: %s", e)
        return []


def delete_user(user_id: int) -> tuple[bool, str]:
    """Hapus user; Data Analis utama (user_id=1) tidak boleh dihapus."""
    try:
        if user_id == 1:
            return False, "Data Analis utama tidak dapat dihapus"

        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM users WHERE user_id = ?", (user_id,))
            if cursor.rowcount == 0:
                return False, "User tidak ditemukan"
            conn.commit()
        return True, "User berhasil dihapus"
    except Exception as e:
        LOGGER.exception("delete_user gagal: %s", e)
        return False, f"Gagal menghapus user: {e}"


def get_user_stats() -> dict:
    """Ambil statistik jumlah pengguna per role untuk Admin Panel."""
    try:
        with get_db_connection() as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            cursor.execute("SELECT COUNT(*) AS total FROM users")
            total_users = int(cursor.fetchone()["total"] or 0)

            role_counts = {role: 0 for role in VALID_ROLES}
            cursor.execute(
                "SELECT role, COUNT(*) AS total FROM users GROUP BY role"
            )
            for row in cursor.fetchall():
                normalized_role = normalize_role(row["role"])
                role_counts[normalized_role] += int(row["total"] or 0)

            cursor.execute(
                """
                SELECT username FROM users
                ORDER BY created_at DESC
                LIMIT 1
                """
            )
            latest_row = cursor.fetchone()
            latest_user = latest_row["username"] if latest_row else None

        total_data_analyst = role_counts[ROLE_DATA_ANALYST]
        total_management = role_counts[ROLE_MANAGEMENT]
        total_social_media_officer = role_counts[ROLE_SOCIAL_MEDIA_OFFICER]
        return {
            "total_users": total_users,
            "total_data_analyst": total_data_analyst,
            "total_management": total_management,
            "total_social_media_officer": total_social_media_officer,
            # Alias lama dipertahankan sementara agar modul eksternal tidak crash.
            "total_admin": total_data_analyst,
            "total_regular": total_management + total_social_media_officer,
            "latest_user": latest_user,
        }
    except Exception as e:
        LOGGER.exception("get_user_stats gagal: %s", e)
        return {
            "total_users": 0,
            "total_data_analyst": 0,
            "total_management": 0,
            "total_social_media_officer": 0,
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

        with get_db_connection() as conn:
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
        LOGGER.exception("create_remember_token gagal: %s", e)
        return None


def validate_remember_token(token: str) -> dict | None:
    """Validasi token remember-me dan kembalikan data user jika masih aktif."""
    try:
        if not token:
            return None

        token_hash = _hash_token(token)
        with get_db_connection() as conn:
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
        LOGGER.exception("validate_remember_token gagal: %s", e)
        return None


def revoke_remember_token(token: str) -> bool:
    """Hapus satu token remember-me dari database."""
    try:
        if not token:
            return False
        token_hash = _hash_token(token)
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "DELETE FROM remember_tokens WHERE token_hash = ?",
                (token_hash,),
            )
            conn.commit()
        return True
    except Exception as e:
        LOGGER.exception("revoke_remember_token gagal: %s", e)
        return False


def revoke_all_remember_tokens(user_id: int) -> bool:
    """Hapus semua token remember-me milik satu user."""
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "DELETE FROM remember_tokens WHERE user_id = ?",
                (user_id,),
            )
            conn.commit()
        return True
    except Exception as e:
        LOGGER.exception("revoke_all_remember_tokens gagal: %s", e)
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
        LOGGER.exception("verify_login gagal: %s", e)
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
        LOGGER.exception("register_user gagal: %s", e)
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
        LOGGER.exception("update_avatar gagal: %s", e)
        return False, f"Gagal menyimpan avatar: {e}"


def update_user_role(user_id: int, new_role: str) -> tuple[bool, str]:
    """Ubah role pengguna dengan proteksi Data Analis utama."""
    try:
        if user_id == 1:
            return False, "Data Analis utama (user_id=1) tidak boleh diubah rolenya."

        role_value = str(new_role or "").strip().lower()
        if role_value not in VALID_ROLES:
            return False, "Role tidak valid."

        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "UPDATE users SET role = ? WHERE user_id = ?",
                (role_value, user_id),
            )
            if cursor.rowcount == 0:
                return False, "User tidak ditemukan"
            conn.commit()
        return True, "Role berhasil diperbarui."
    except Exception as e:
        LOGGER.exception("update_user_role gagal: %s", e)
        return False, f"Gagal mengubah role: {e}"


def admin_create_user(
    fullname: str,
    username: str,
    email: str,
    password: str,
    role: str = DEFAULT_ROLE,
) -> tuple[bool, str]:
    """Buat akun baru oleh Data Analis dengan role pilihan."""
    try:
        role_value = str(role or "").strip().lower()
        if role_value not in VALID_ROLES:
            return False, "Role tidak valid."

        success, message = create_user(fullname, username, email, password)
        if not success:
            return False, message

        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "UPDATE users SET role = ? WHERE username = ?",
                (role_value, username.strip().lower()),
            )
            conn.commit()
        return True, "Akun baru berhasil dibuat."
    except Exception as e:
        LOGGER.exception("admin_create_user gagal: %s", e)
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
        LOGGER.exception("format_created_at gagal: %s", e)
        return "-"
