#!/usr/bin/env bash
set -u

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

if [[ -z "${VIRTUAL_ENV:-}" ]]; then
    if [[ -f ".venv/bin/activate" ]]; then
        echo "Mengaktifkan virtual environment .venv..."
        # shellcheck disable=SC1091
        source ".venv/bin/activate"
    elif [[ -f "venv/bin/activate" ]]; then
        echo "Mengaktifkan virtual environment venv..."
        # shellcheck disable=SC1091
        source "venv/bin/activate"
    fi
fi

if command -v python3 >/dev/null 2>&1; then
    PYTHON_BIN="python3"
elif command -v python >/dev/null 2>&1; then
    PYTHON_BIN="python"
else
    echo "[GAGAL] Python tidak ditemukan. Instal Python 3.10 atau 3.11."
    exit 1
fi

if ! "$PYTHON_BIN" -c "import streamlit" >/dev/null 2>&1; then
    echo "[GAGAL] Streamlit belum terpasang pada environment aktif."
    echo "Jalankan: $PYTHON_BIN -m pip install -r requirements.txt"
    exit 1
fi

echo "Dashboard siap di http://localhost:8501"
echo "Tekan Ctrl+C untuk menghentikan dashboard."
exec "$PYTHON_BIN" -m streamlit run app.py
