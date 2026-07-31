@echo off
title Dashboard Telkom Group — Analisis Sentimen SNA
color 0A
echo.
echo  ======================================================
echo   Dashboard Analisis Sentimen ^& SNA — Telkom Group
echo   Skripsi S1 Sains Data — ULBI Bandung 2026
echo  ======================================================
echo.

REM Cek apakah virtual environment ada
if not exist "venv\Scripts\activate.bat" (
    echo [SETUP] Virtual environment tidak ditemukan.
    echo [SETUP] Membuat virtual environment baru...
    python -m venv venv
    echo [SETUP] Menginstall dependency dari requirements.txt...
    call venv\Scripts\activate.bat
    pip install -r requirements.txt
    echo [SETUP] Instalasi selesai!
) else (
    call venv\Scripts\activate.bat
)

echo.
echo [INFO] Memulai dashboard...
echo [INFO] Browser akan terbuka otomatis di http://localhost:8501
echo [INFO] Tekan Ctrl+C untuk menghentikan server
echo.
streamlit run app.py --server.port 8501 --server.headless false

pause
