@echo off
setlocal
cd /d "%~dp0"
title Dashboard Analisis Telkom Group

echo ================================================================
echo DASHBOARD ANALISIS TELKOM GROUP
echo ================================================================
echo.

if defined VIRTUAL_ENV goto :CHECK_PYTHON

if exist ".venv\Scripts\activate.bat" (
    echo Mengaktifkan virtual environment .venv...
    call ".venv\Scripts\activate.bat"
    goto :CHECK_PYTHON
)

if exist "venv\Scripts\activate.bat" (
    echo Mengaktifkan virtual environment venv...
    call "venv\Scripts\activate.bat"
)

:CHECK_PYTHON
where python >nul 2>nul
if errorlevel 1 (
    echo [GAGAL] Python tidak ditemukan.
    echo Instal Python 3.10 atau 3.11, lalu jalankan file ini kembali.
    pause
    exit /b 1
)

python -c "import streamlit" >nul 2>nul
if errorlevel 1 (
    echo [GAGAL] Streamlit belum terpasang pada environment aktif.
    echo Jalankan: python -m pip install -r requirements.txt
    pause
    exit /b 1
)

echo Dashboard siap di http://localhost:8501
echo Tekan Ctrl+C pada jendela ini untuk menghentikan dashboard.
echo.
python -m streamlit run app.py
set "APP_EXIT=%ERRORLEVEL%"

if not "%APP_EXIT%"=="0" (
    echo.
    echo [GAGAL] Dashboard berhenti dengan kode %APP_EXIT%.
    echo Baca pesan error paling bawah pada terminal.
    pause
)

exit /b %APP_EXIT%
