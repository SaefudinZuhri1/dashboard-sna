@echo off
setlocal EnableExtensions

REM ==============================================================
REM Launcher Windows - Dashboard Analisis Sentimen dan SNA Telkom
REM File ini hanya mengatur instalasi lokal dan menjalankan aplikasi.
REM Tidak mengubah tampilan atau logika halaman dashboard.
REM ==============================================================

cd /d "%~dp0"
title Dashboard Telkom Group - Analisis Sentimen SNA
color 0A

set "APP_FILE=app.py"
set "REQUIREMENTS_FILE=requirements.txt"
set "VENV_DIR=venv"
set "VENV_PYTHON=%VENV_DIR%\Scripts\python.exe"
set "REQUIREMENTS_MARKER=%VENV_DIR%\.requirements.sha256"
set "PYTHON_CMD="
set "DASHBOARD_PORT=8501"

call :header

REM Pastikan launcher dijalankan dari folder proyek yang benar.
if not exist "%APP_FILE%" (
    call :fatal "File app.py tidak ditemukan. Pastikan run.bat berada satu folder dengan app.py."
    exit /b 1
)

if not exist "%REQUIREMENTS_FILE%" (
    call :fatal "File requirements.txt tidak ditemukan. Instalasi dependency tidak dapat dilanjutkan."
    exit /b 1
)

REM Cari Python yang kompatibel. Prioritas 3.11, 3.10, lalu 3.12.
py -3.11 --version >nul 2>&1 && set "PYTHON_CMD=py -3.11"
if not defined PYTHON_CMD py -3.10 --version >nul 2>&1 && set "PYTHON_CMD=py -3.10"
if not defined PYTHON_CMD py -3.12 --version >nul 2>&1 && set "PYTHON_CMD=py -3.12"
if not defined PYTHON_CMD python --version >nul 2>&1 && set "PYTHON_CMD=python"

if not defined PYTHON_CMD (
    echo [GAGAL] Python tidak ditemukan di komputer ini.
    echo.
    echo Instal Python 3.10 atau 3.11 dari https://www.python.org/downloads/
    echo Saat instalasi, WAJIB centang kotak "Add Python to PATH".
    echo Setelah instalasi selesai, tutup jendela ini lalu klik dua kali run.bat lagi.
    echo.
    pause
    exit /b 1
)

REM Tolak versi yang terlalu lama atau belum kompatibel dengan dependency proyek.
%PYTHON_CMD% -c "import sys; raise SystemExit(0 if (3, 10) <= sys.version_info[:2] <= (3, 12) else 1)" >nul 2>&1
if errorlevel 1 (
    echo [GAGAL] Versi Python yang ditemukan tidak kompatibel.
    %PYTHON_CMD% --version
    echo.
    echo Gunakan Python 3.10 atau 3.11 untuk hasil paling aman.
    echo Python 3.13 atau lebih baru belum digunakan oleh baseline dependency proyek ini.
    echo.
    pause
    exit /b 1
)

for /f "delims=" %%V in ('%PYTHON_CMD% --version 2^>^&1') do set "PYTHON_VERSION=%%V"
echo [OK] Python ditemukan: %PYTHON_VERSION%

REM Buat virtual environment hanya jika belum tersedia.
if not exist "%VENV_PYTHON%" (
    echo.
    echo [SETUP 1/3] Virtual environment belum tersedia.
    echo [SETUP 1/3] Membuat folder %VENV_DIR% ...
    %PYTHON_CMD% -m venv "%VENV_DIR%"
    if errorlevel 1 (
        call :fatal "Pembuatan virtual environment gagal. Salin pesan error di atas untuk proses debug."
        exit /b 1
    )
    echo [OK] Virtual environment berhasil dibuat.
) else (
    echo [OK] Virtual environment sudah tersedia.
)

if not exist "%VENV_PYTHON%" (
    call :fatal "Python di dalam virtual environment tidak ditemukan. Hapus folder venv lalu jalankan run.bat kembali."
    exit /b 1
)

REM Hitung fingerprint requirements agar instalasi hanya diulang saat diperlukan.
for /f "delims=" %%H in ('"%VENV_PYTHON%" -c "import hashlib; print(hashlib.sha256(open('requirements.txt','rb').read()).hexdigest())"') do set "CURRENT_REQUIREMENTS_HASH=%%H"
set "INSTALLED_REQUIREMENTS_HASH="
if exist "%REQUIREMENTS_MARKER%" set /p INSTALLED_REQUIREMENTS_HASH=<"%REQUIREMENTS_MARKER%"

set "INSTALL_REQUIRED=0"
if not "%CURRENT_REQUIREMENTS_HASH%"=="%INSTALLED_REQUIREMENTS_HASH%" set "INSTALL_REQUIRED=1"

REM Verifikasi import library inti. Jika gagal, dependency dipasang ulang.
if "%INSTALL_REQUIRED%"=="0" (
    "%VENV_PYTHON%" -c "import streamlit, pandas, plotly, networkx, pyvis, bcrypt, transformers, torch, wordcloud, openpyxl; import google.genai" >nul 2>&1
    if errorlevel 1 set "INSTALL_REQUIRED=1"
)

if "%INSTALL_REQUIRED%"=="1" (
    echo.
    echo [SETUP 2/3] Menyiapkan pip terbaru...
    "%VENV_PYTHON%" -m pip install --upgrade pip
    if errorlevel 1 (
        call :fatal "Pembaruan pip gagal. Periksa koneksi internet lalu jalankan run.bat kembali."
        exit /b 1
    )

    echo.
    echo [SETUP 3/3] Menginstall dependency dari requirements.txt...
    echo Proses pertama dapat cukup lama karena PyTorch dan model NLP berukuran besar.
    "%VENV_PYTHON%" -m pip install -r "%REQUIREMENTS_FILE%"
    if errorlevel 1 (
        if exist "%REQUIREMENTS_MARKER%" del /q "%REQUIREMENTS_MARKER%" >nul 2>&1
        call :fatal "Instalasi dependency gagal. Jangan tutup jendela sebelum menyalin pesan ERROR atau FAILED di atas."
        exit /b 1
    )

    >"%REQUIREMENTS_MARKER%" echo %CURRENT_REQUIREMENTS_HASH%
    echo [OK] Seluruh dependency berhasil dipasang.
) else (
    echo [OK] Dependency sudah lengkap dan sesuai requirements.txt.
)

REM Verifikasi terakhir sebelum server dijalankan.
"%VENV_PYTHON%" -m streamlit --version >nul 2>&1
if errorlevel 1 (
    call :fatal "Streamlit belum dapat dijalankan dari virtual environment."
    exit /b 1
)

REM Jika port 8501 sedang dipakai, gunakan 8502.
"%VENV_PYTHON%" -c "import socket; s=socket.socket(); code=s.connect_ex(('127.0.0.1',8501)); s.close(); raise SystemExit(0 if code != 0 else 1)" >nul 2>&1
if errorlevel 1 set "DASHBOARD_PORT=8502"

set "DASHBOARD_URL=http://localhost:%DASHBOARD_PORT%"
echo.
echo ======================================================
echo [INFO] Memulai dashboard...
echo [INFO] Alamat dashboard: %DASHBOARD_URL%
echo [INFO] Browser akan dibuka otomatis.
echo [INFO] Jangan tutup jendela ini selama dashboard digunakan.
echo [INFO] Tekan Ctrl+C untuk menghentikan server.
echo ======================================================
echo.

REM Buka browser beberapa detik setelah proses server dimulai.
start "" /b "%VENV_PYTHON%" -c "import time, webbrowser; time.sleep(4); webbrowser.open('%DASHBOARD_URL%')"

"%VENV_PYTHON%" -m streamlit run "%APP_FILE%" --server.port %DASHBOARD_PORT% --server.headless true
set "STREAMLIT_EXIT=%ERRORLEVEL%"

if not "%STREAMLIT_EXIT%"=="0" (
    echo.
    echo [GAGAL] Streamlit berhenti dengan kode %STREAMLIT_EXIT%.
    echo Salin pesan error di atas untuk proses debug.
    pause
    exit /b %STREAMLIT_EXIT%
)

endlocal
exit /b 0

:header
echo.
echo ======================================================
echo  Dashboard Analisis Sentimen dan SNA - Telkom Group
echo  Skripsi S1 Sains Data - ULBI Bandung 2026
echo ======================================================
echo.
exit /b 0

:fatal
echo.
echo [GAGAL] %~1
echo.
echo Jendela ini sengaja tidak ditutup agar pesan error dapat dibaca.
pause
exit /b 1
