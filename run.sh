#!/usr/bin/env bash

# ==============================================================
# Launcher macOS/Linux - Dashboard Analisis Sentimen dan SNA
# File ini hanya mengatur instalasi lokal dan menjalankan aplikasi.
# Tidak mengubah tampilan atau logika halaman dashboard.
# ==============================================================

set -u

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR" || exit 1

APP_FILE="app.py"
REQUIREMENTS_FILE="requirements.txt"
VENV_DIR="venv"
VENV_PYTHON="$VENV_DIR/bin/python"
REQUIREMENTS_MARKER="$VENV_DIR/.requirements.sha256"
PYTHON_CMD=""
DASHBOARD_PORT="8501"

tampilkan_header() {
    printf '\n'
    printf '%s\n' '======================================================'
    printf '%s\n' ' Dashboard Analisis Sentimen dan SNA - Telkom Group'
    printf '%s\n' ' Skripsi S1 Sains Data - ULBI Bandung 2026'
    printf '%s\n' '======================================================'
    printf '\n'
}

gagal() {
    printf '\n[GAGAL] %s\n\n' "$1" >&2
    exit 1
}

tampilkan_header

[[ -f "$APP_FILE" ]] || gagal "File app.py tidak ditemukan. Pastikan run.sh berada satu folder dengan app.py."
[[ -f "$REQUIREMENTS_FILE" ]] || gagal "File requirements.txt tidak ditemukan. Instalasi dependency tidak dapat dilanjutkan."

for kandidat in python3.11 python3.10 python3.12 python3 python; do
    if command -v "$kandidat" >/dev/null 2>&1; then
        if "$kandidat" -c 'import sys; raise SystemExit(0 if (3, 10) <= sys.version_info[:2] <= (3, 12) else 1)' >/dev/null 2>&1; then
            PYTHON_CMD="$kandidat"
            break
        fi
    fi
done

if [[ -z "$PYTHON_CMD" ]]; then
    gagal "Python 3.10-3.12 tidak ditemukan. Instal Python 3.10 atau 3.11, lalu jalankan run.sh kembali."
fi

PYTHON_VERSION="$($PYTHON_CMD --version 2>&1)"
printf '[OK] Python ditemukan: %s\n' "$PYTHON_VERSION"

if [[ ! -x "$VENV_PYTHON" ]]; then
    printf '\n[SETUP 1/3] Virtual environment belum tersedia.\n'
    printf '[SETUP 1/3] Membuat folder %s ...\n' "$VENV_DIR"
    "$PYTHON_CMD" -m venv "$VENV_DIR" || gagal "Pembuatan virtual environment gagal."
    printf '[OK] Virtual environment berhasil dibuat.\n'
else
    printf '[OK] Virtual environment sudah tersedia.\n'
fi

[[ -x "$VENV_PYTHON" ]] || gagal "Python di dalam virtual environment tidak ditemukan. Hapus folder venv lalu jalankan run.sh kembali."

CURRENT_REQUIREMENTS_HASH="$($VENV_PYTHON -c "import hashlib; print(hashlib.sha256(open('requirements.txt','rb').read()).hexdigest())")"
INSTALLED_REQUIREMENTS_HASH=""
if [[ -f "$REQUIREMENTS_MARKER" ]]; then
    INSTALLED_REQUIREMENTS_HASH="$(cat "$REQUIREMENTS_MARKER")"
fi

INSTALL_REQUIRED="0"
if [[ "$CURRENT_REQUIREMENTS_HASH" != "$INSTALLED_REQUIREMENTS_HASH" ]]; then
    INSTALL_REQUIRED="1"
fi

if [[ "$INSTALL_REQUIRED" == "0" ]]; then
    if ! "$VENV_PYTHON" -c 'import streamlit, pandas, plotly, networkx, pyvis, bcrypt, transformers, torch, wordcloud, openpyxl; import google.genai' >/dev/null 2>&1; then
        INSTALL_REQUIRED="1"
    fi
fi

if [[ "$INSTALL_REQUIRED" == "1" ]]; then
    printf '\n[SETUP 2/3] Menyiapkan pip terbaru...\n'
    "$VENV_PYTHON" -m pip install --upgrade pip || gagal "Pembaruan pip gagal. Periksa koneksi internet."

    printf '\n[SETUP 3/3] Menginstall dependency dari requirements.txt...\n'
    printf '%s\n' 'Proses pertama dapat cukup lama karena PyTorch dan model NLP berukuran besar.'
    if ! "$VENV_PYTHON" -m pip install -r "$REQUIREMENTS_FILE"; then
        rm -f "$REQUIREMENTS_MARKER"
        gagal "Instalasi dependency gagal. Salin pesan ERROR atau FAILED di atas untuk proses debug."
    fi

    printf '%s\n' "$CURRENT_REQUIREMENTS_HASH" > "$REQUIREMENTS_MARKER"
    printf '[OK] Seluruh dependency berhasil dipasang.\n'
else
    printf '[OK] Dependency sudah lengkap dan sesuai requirements.txt.\n'
fi

"$VENV_PYTHON" -m streamlit --version >/dev/null 2>&1 || gagal "Streamlit belum dapat dijalankan dari virtual environment."

if "$VENV_PYTHON" -c "import socket; s=socket.socket(); code=s.connect_ex(('127.0.0.1',8501)); s.close(); raise SystemExit(0 if code != 0 else 1)" >/dev/null 2>&1; then
    DASHBOARD_PORT="8501"
else
    DASHBOARD_PORT="8502"
fi

DASHBOARD_URL="http://localhost:${DASHBOARD_PORT}"
printf '\n%s\n' '======================================================'
printf '[INFO] Memulai dashboard...\n'
printf '[INFO] Alamat dashboard: %s\n' "$DASHBOARD_URL"
printf '[INFO] Browser akan dibuka otomatis jika sistem mendukung.\n'
printf '[INFO] Jangan tutup Terminal selama dashboard digunakan.\n'
printf '[INFO] Tekan Ctrl+C untuk menghentikan server.\n'
printf '%s\n\n' '======================================================'

(
    sleep 4
    if command -v open >/dev/null 2>&1; then
        open "$DASHBOARD_URL" >/dev/null 2>&1 || true
    elif command -v xdg-open >/dev/null 2>&1; then
        xdg-open "$DASHBOARD_URL" >/dev/null 2>&1 || true
    else
        "$VENV_PYTHON" -m webbrowser "$DASHBOARD_URL" >/dev/null 2>&1 || true
    fi
) &

exec "$VENV_PYTHON" -m streamlit run "$APP_FILE" --server.port "$DASHBOARD_PORT" --server.headless true
