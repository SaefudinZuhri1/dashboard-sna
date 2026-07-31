#!/bin/bash

echo ""
echo "======================================================"
echo " Dashboard Analisis Sentimen & SNA — Telkom Group"
echo " Skripsi S1 Sains Data — ULBI Bandung 2026"
echo "======================================================"
echo ""

# Cek apakah virtual environment ada
if [ ! -d "venv" ]; then
    echo "[SETUP] Virtual environment tidak ditemukan."
    echo "[SETUP] Membuat virtual environment baru..."
    python3 -m venv venv
    echo "[SETUP] Menginstall dependency dari requirements.txt..."
    source venv/bin/activate
    pip install -r requirements.txt
    echo "[SETUP] Instalasi selesai!"
else
    source venv/bin/activate
fi

echo ""
echo "[INFO] Memulai dashboard..."
echo "[INFO] Buka browser di http://localhost:8501"
echo "[INFO] Tekan Ctrl+C untuk menghentikan server"
echo ""
streamlit run app.py --server.port 8501
