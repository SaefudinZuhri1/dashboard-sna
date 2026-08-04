"""Pesan error ramah pengguna dan penyaring log aplikasi.

Detail teknis tidak ditampilkan kepada pengguna awam. Pesan internal proyek di
Command Prompt atau Streamlit Community Cloud disederhanakan menjadi Bahasa
Indonesia yang lebih mudah dipahami.
"""

from __future__ import annotations

import logging
import re
from typing import Any, Callable

import streamlit as st


_INSTALLED = False
_ORIGINAL_FACTORY = logging.getLogRecordFactory()
_PROJECT_LOGGER_PREFIXES = {"__main__", "app", "auth", "pages", "utils"}
_TECHNICAL_MARKERS = (
    "traceback",
    "filenotfounderror",
    "modulenotfounderror",
    "keyerror",
    "typeerror",
    "valueerror",
    "attributeerror",
    "runtimeerror",
    "permissionerror",
    "sqlite3.",
    "no module named",
    "errno ",
    "detail teknis",
)


def _clean_context(text: str) -> str:
    """Ambil konteks manusiawi tanpa isi exception mentah."""
    value = re.sub(r"\s+", " ", str(text or "")).strip()
    value = re.sub(r"\([^)]*(Error|Exception)[^)]*\)", "", value, flags=re.I)
    value = re.sub(r"\b[A-Za-z_][\w.]*Error\b", "", value)
    value = re.sub(r"\s*[:.\-]\s*$", "", value).strip()
    return value


def humanize_message(message: Any, *, level: str = "error") -> str:
    """Ubah pesan teknis menjadi kalimat singkat yang mudah dipahami."""
    text = str(message or "").strip()
    lowered = text.lower()

    for marker in (
        "detail teknis:",
        "detail:",
        "traceback (most recent call last):",
    ):
        index = lowered.find(marker)
        if index >= 0:
            text = text[:index].rstrip(" :-\n")
            lowered = text.lower()

    has_technical_marker = any(marker in lowered for marker in _TECHNICAL_MARKERS)
    contains_path = bool(
        re.search(r"(?:[A-Za-z]:\\|/home/|/mount/|/app/|\\venv\\)", text)
    )

    if not (has_technical_marker or contains_path):
        if ":" in text and any(
            word in lowered for word in ("gagal", "belum dapat", "tidak dapat")
        ):
            context = _clean_context(text.split(":", 1)[0])
            if context:
                return f"{context}. Silakan coba kembali."
        return text

    context = _clean_context(text.split(":", 1)[0])
    if level == "warning":
        if context:
            return f"{context}. Aplikasi tetap mencoba menggunakan pilihan yang aman."
        return (
            "Ada bagian yang belum siap. "
            "Aplikasi tetap mencoba menggunakan pilihan yang aman."
        )

    if context:
        return f"{context}. Silakan coba kembali atau jalankan ulang aplikasi."
    return "Aplikasi mengalami kendala. Silakan coba kembali atau jalankan ulang aplikasi."


def friendly_exception_message(
    error: BaseException,
    *,
    action: str = "Proses",
) -> str:
    """Petakan jenis exception umum ke penjelasan Bahasa Indonesia."""
    if isinstance(error, FileNotFoundError):
        return f"{action} belum berhasil karena file yang diperlukan tidak ditemukan."
    if isinstance(error, PermissionError):
        return (
            f"{action} belum berhasil karena aplikasi tidak memiliki izin "
            "membuka file tersebut."
        )
    if isinstance(error, ModuleNotFoundError):
        return f"{action} belum berhasil karena ada komponen aplikasi yang belum terpasang."
    if isinstance(error, (ConnectionError, TimeoutError)):
        return f"{action} belum berhasil karena koneksi belum stabil."
    return f"{action} belum berhasil. Silakan coba kembali atau jalankan ulang aplikasi."


def _friendly_record_factory(*args: Any, **kwargs: Any) -> logging.LogRecord:
    """Hilangkan traceback panjang dari log modul milik proyek."""
    record = _ORIGINAL_FACTORY(*args, **kwargs)
    root_name = str(record.name).split(".", 1)[0]
    if root_name in _PROJECT_LOGGER_PREFIXES and record.levelno >= logging.WARNING:
        try:
            rendered = record.getMessage()
        except Exception:
            rendered = str(record.msg)
        record.msg = humanize_message(
            rendered,
            level="warning" if record.levelno == logging.WARNING else "error",
        )
        record.args = ()
        record.exc_info = None
        record.exc_text = None
        record.stack_info = None
    return record


def _wrap_alert(
    original: Callable[..., Any],
    *,
    level: str,
) -> Callable[..., Any]:
    """Bungkus alert Streamlit agar isi teknis tidak tampil mentah."""

    def wrapped(body: Any, *args: Any, **kwargs: Any):
        return original(humanize_message(body, level=level), *args, **kwargs)

    return wrapped


def install_friendly_runtime_messages() -> None:
    """Aktifkan pesan ramah pengguna satu kali pada awal aplikasi."""
    global _INSTALLED
    if _INSTALLED:
        return

    logging.setLogRecordFactory(_friendly_record_factory)
    st.error = _wrap_alert(st.error, level="error")
    st.warning = _wrap_alert(st.warning, level="warning")

    original_error = st.error

    def friendly_exception(
        error: BaseException,
        *args: Any,
        **kwargs: Any,
    ):
        message = friendly_exception_message(error, action="Aplikasi")
        logging.getLogger("app").error(message)
        return original_error(message, *args, **kwargs)

    st.exception = friendly_exception
    _INSTALLED = True
