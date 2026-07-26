"""Pencatatan audit terpusat untuk aktivitas pengguna dashboard.

Modul ini sengaja tidak menampilkan error ke antarmuka. Kegagalan audit tidak
boleh menghentikan fungsi utama dashboard, tetapi tetap ditulis ke log Python.
"""

from __future__ import annotations

import json
import logging
import re
import sqlite3
import threading
import uuid
from pathlib import Path
from datetime import datetime, timedelta
from typing import Any

LOGGER = logging.getLogger(__name__)
_AUDIT_LOCK = threading.RLock()
_SENSITIVE_KEY_PATTERN = re.compile(
    r"password|passphrase|token|secret|api[_-]?key|cookie|authorization|blob|image|picture",
    re.IGNORECASE,
)


def _db_path() -> str:
    """Bangun path database secara portabel tanpa circular import."""
    project_root = Path(__file__).resolve().parent.parent
    database_dir = project_root / "database"
    database_dir.mkdir(parents=True, exist_ok=True)
    return str(database_dir / "users.db")


def _connect() -> sqlite3.Connection:
    """Buat koneksi SQLite yang toleran terhadap beberapa rerun Streamlit."""
    conn = sqlite3.connect(_db_path(), timeout=12)
    conn.row_factory = sqlite3.Row
    try:
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA synchronous=NORMAL")
        conn.execute("PRAGMA foreign_keys=ON")
    except sqlite3.DatabaseError:
        pass
    return conn


def ensure_audit_table() -> bool:
    """Buat tabel audit dan indeks pendukung jika belum tersedia."""
    try:
        with _AUDIT_LOCK, _connect() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS audit_logs (
                    audit_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    created_at TEXT NOT NULL DEFAULT (datetime('now', 'localtime')),
                    user_id INTEGER,
                    username TEXT,
                    fullname TEXT,
                    role TEXT,
                    session_id TEXT,
                    action TEXT NOT NULL,
                    module TEXT NOT NULL,
                    description TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT 'success',
                    service TEXT,
                    platform TEXT,
                    metadata_json TEXT,
                    FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE SET NULL
                );
                CREATE INDEX IF NOT EXISTS idx_audit_created_at ON audit_logs(created_at DESC);
                CREATE INDEX IF NOT EXISTS idx_audit_username ON audit_logs(username);
                CREATE INDEX IF NOT EXISTS idx_audit_action ON audit_logs(action);
                CREATE INDEX IF NOT EXISTS idx_audit_module ON audit_logs(module);
                CREATE INDEX IF NOT EXISTS idx_audit_status ON audit_logs(status);
                """
            )
            conn.commit()
        return True
    except Exception as exc:
        LOGGER.exception("Tabel audit tidak dapat disiapkan: %s", exc)
        return False


def _safe_scalar(value: Any, max_length: int = 500) -> Any:
    """Ubah nilai metadata menjadi bentuk JSON aman dan ringkas."""
    if value is None or isinstance(value, (bool, int, float)):
        return value
    if isinstance(value, datetime):
        return value.isoformat(timespec="seconds")
    text = str(value).strip()
    return text[:max_length]


def _sanitize_metadata(value: Any, depth: int = 0) -> Any:
    """Hapus field sensitif dan batasi ukuran metadata audit."""
    if depth > 3:
        return "[dipangkas]"
    if isinstance(value, dict):
        cleaned: dict[str, Any] = {}
        for key, item in list(value.items())[:30]:
            key_text = str(key)
            if _SENSITIVE_KEY_PATTERN.search(key_text):
                cleaned[key_text] = "[DISEMBUNYIKAN]"
            else:
                cleaned[key_text] = _sanitize_metadata(item, depth + 1)
        return cleaned
    if isinstance(value, (list, tuple, set)):
        return [_sanitize_metadata(item, depth + 1) for item in list(value)[:30]]
    return _safe_scalar(value)


def _session_context() -> dict[str, Any]:
    """Ambil identitas pengguna dari session Streamlit jika tersedia."""
    try:
        import streamlit as st

        if "_audit_session_id" not in st.session_state:
            st.session_state["_audit_session_id"] = uuid.uuid4().hex
        user = st.session_state.get("user")
        user = user if isinstance(user, dict) else {}
        return {
            "user_id": st.session_state.get("user_id") or user.get("user_id"),
            "username": st.session_state.get("username") or user.get("username"),
            "fullname": st.session_state.get("fullname") or user.get("fullname"),
            "role": st.session_state.get("role") or user.get("role"),
            "session_id": st.session_state.get("_audit_session_id"),
        }
    except Exception:
        return {"session_id": uuid.uuid4().hex}


def log_activity(
    action: str,
    module: str,
    description: str,
    *,
    status: str = "success",
    service: str | None = None,
    platform: str | None = None,
    metadata: dict[str, Any] | None = None,
    user_id: int | None = None,
    username: str | None = None,
    fullname: str | None = None,
    role: str | None = None,
    session_id: str | None = None,
) -> bool:
    """Simpan satu aktivitas nyata ke tabel ``audit_logs``.

    Nilai password, token, API key, cookie, dan BLOB tidak pernah disimpan.
    """
    try:
        if not ensure_audit_table():
            return False

        context = _session_context()
        normalized_status = str(status or "success").strip().lower()
        if normalized_status not in {"success", "failed", "denied", "warning"}:
            normalized_status = "warning"

        metadata_safe = _sanitize_metadata(metadata or {})
        metadata_json = json.dumps(metadata_safe, ensure_ascii=False, separators=(",", ":"))
        with _AUDIT_LOCK, _connect() as conn:
            conn.execute(
                """
                INSERT INTO audit_logs (
                    user_id, username, fullname, role, session_id,
                    action, module, description, status,
                    service, platform, metadata_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    user_id if user_id is not None else context.get("user_id"),
                    (username if username is not None else context.get("username")) or "anonymous",
                    (fullname if fullname is not None else context.get("fullname")) or "-",
                    (role if role is not None else context.get("role")) or "-",
                    session_id or context.get("session_id"),
                    str(action or "UNKNOWN").strip().upper()[:80],
                    str(module or "Sistem").strip()[:120],
                    str(description or "Aktivitas tanpa deskripsi").strip()[:1000],
                    normalized_status,
                    str(service).strip()[:80] if service else None,
                    str(platform).strip()[:80] if platform else None,
                    metadata_json[:5000],
                ),
            )
            conn.commit()
        return True
    except Exception as exc:
        LOGGER.exception("Audit aktivitas gagal disimpan: %s", exc)
        return False


def log_page_view_once(page_name: str) -> bool:
    """Catat pembukaan halaman hanya ketika route benar-benar berubah."""
    try:
        import streamlit as st

        page_name = str(page_name or "Beranda").strip()
        previous_page = st.session_state.get("_audit_last_page")
        if previous_page == page_name:
            return False
        st.session_state["_audit_last_page"] = page_name
        return log_activity(
            "OPEN_PAGE",
            page_name,
            f"Membuka halaman {page_name}.",
            metadata={"route": page_name},
        )
    except Exception as exc:
        LOGGER.debug("Page view audit dilewati: %s", exc)
        return False


def fetch_audit_logs(
    *,
    days: int | None = 30,
    username: str | None = None,
    action: str | None = None,
    module: str | None = None,
    status: str | None = None,
    search: str | None = None,
    limit: int = 2000,
) -> list[dict[str, Any]]:
    """Ambil audit log dengan filter aman untuk Admin Panel."""
    try:
        ensure_audit_table()
        clauses: list[str] = []
        params: list[Any] = []
        if days is not None:
            cutoff = (datetime.now() - timedelta(days=max(0, int(days)))).isoformat(timespec="seconds")
            clauses.append("datetime(created_at) >= datetime(?)")
            params.append(cutoff)
        if username and username != "Semua Pengguna":
            clauses.append("username = ?")
            params.append(username)
        if action and action != "Semua Aktivitas":
            clauses.append("action = ?")
            params.append(action)
        if module and module != "Semua Modul":
            clauses.append("module = ?")
            params.append(module)
        if status and status != "Semua Status":
            clauses.append("status = ?")
            params.append(status)
        if search:
            clauses.append("(LOWER(username) LIKE ? OR LOWER(description) LIKE ? OR LOWER(module) LIKE ?)")
            keyword = f"%{str(search).strip().lower()}%"
            params.extend([keyword, keyword, keyword])

        where_clause = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        query = f"""
            SELECT audit_id, created_at, user_id, username, fullname, role,
                   session_id, action, module, description, status,
                   service, platform, metadata_json
            FROM audit_logs
            {where_clause}
            ORDER BY datetime(created_at) DESC, audit_id DESC
            LIMIT ?
        """
        params.append(max(1, min(int(limit), 10000)))
        with _connect() as conn:
            rows = conn.execute(query, params).fetchall()
        return [dict(row) for row in rows]
    except Exception as exc:
        LOGGER.exception("Audit log gagal dibaca: %s", exc)
        return []


def get_audit_filter_options() -> dict[str, list[str]]:
    """Ambil opsi filter unik dari tabel audit."""
    try:
        ensure_audit_table()
        with _connect() as conn:
            usernames = [row[0] for row in conn.execute(
                "SELECT DISTINCT username FROM audit_logs WHERE username IS NOT NULL ORDER BY username"
            ).fetchall()]
            actions = [row[0] for row in conn.execute(
                "SELECT DISTINCT action FROM audit_logs ORDER BY action"
            ).fetchall()]
            modules = [row[0] for row in conn.execute(
                "SELECT DISTINCT module FROM audit_logs ORDER BY module"
            ).fetchall()]
        return {"usernames": usernames, "actions": actions, "modules": modules}
    except Exception as exc:
        LOGGER.exception("Opsi filter audit gagal dibaca: %s", exc)
        return {"usernames": [], "actions": [], "modules": []}


def audit_dataframe(logs: list[dict[str, Any]]) -> "Any":
    """Ubah daftar audit menjadi DataFrame tanpa metadata sensitif."""
    import pandas as pd

    if not logs:
        return pd.DataFrame(
            columns=["Waktu", "Pengguna", "Role", "Aktivitas", "Modul", "Deskripsi", "Status", "Layanan", "Platform"]
        )
    frame = pd.DataFrame(logs)
    frame["created_at"] = pd.to_datetime(frame["created_at"], errors="coerce")
    frame = frame.rename(
        columns={
            "created_at": "Waktu",
            "username": "Pengguna",
            "role": "Role",
            "action": "Aktivitas",
            "module": "Modul",
            "description": "Deskripsi",
            "status": "Status",
            "service": "Layanan",
            "platform": "Platform",
        }
    )
    columns = ["Waktu", "Pengguna", "Role", "Aktivitas", "Modul", "Deskripsi", "Status", "Layanan", "Platform"]
    return frame.reindex(columns=columns)
