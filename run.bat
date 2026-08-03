@echo off
setlocal EnableExtensions EnableDelayedExpansion

REM ==============================================================
REM Launcher Windows - Dashboard Analisis Sentimen dan SNA Telkom
REM Python proyek dikunci ke versi 3.10.
REM File ini tidak mengubah UI/UX maupun logika halaman dashboard.
REM ==============================================================

cd /d "%~dp0"
title Dashboard Telkom Group - Analisis Sentimen SNA
color 0A

set "APP_FILE=app.py"
set "REQUIREMENTS_FILE=requirements.txt"
set "VENV_DIR=venv"
set "VENV_PYTHON=%VENV_DIR%\Scripts\python.exe"
set "REQUIREMENTS_MARKER=%VENV_DIR%\.requirements.sha256"
set "BASE_PYTHON_EXE="
set "BASE_PYTHON_ARGS="
set "DASHBOARD_PORT=8501"
set "VERSION_TEMP=%TEMP%\dashboard_python_version_%RANDOM%_%RANDOM%.txt"

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

REM ==============================================================
REM 1. Cari Python 3.10 saja. Python 3.11/3.12 tidak dipakai.
REM ==============================================================
py -3.10 -c "import sys; raise SystemExit(0 if sys.version_info[:2] == (3, 10) else 1)" >nul 2>&1
if not errorlevel 1 (
    set "BASE_PYTHON_EXE=py"
    set "BASE_PYTHON_ARGS=-3.10"
)

REM Fallback jika Python Launcher (py) tidak tersedia, tetapi Python 3.10
REM terpasang pada salah satu lokasi standar Windows.
if not defined BASE_PYTHON_EXE if exist "%LocalAppData%\Programs\Python\Python310\python.exe" set "BASE_PYTHON_EXE=%LocalAppData%\Programs\Python\Python310\python.exe"
if not defined BASE_PYTHON_EXE if exist "%ProgramFiles%\Python310\python.exe" set "BASE_PYTHON_EXE=%ProgramFiles%\Python310\python.exe"
if not defined BASE_PYTHON_EXE if exist "%ProgramFiles(x86)%\Python310\python.exe" set "BASE_PYTHON_EXE=%ProgramFiles(x86)%\Python310\python.exe"

if not defined BASE_PYTHON_EXE (
    echo [GAGAL] Python 3.10 tidak ditemukan di komputer ini.
    echo.
    echo Launcher sengaja tidak memakai Python 3.11 atau versi lain.
    echo Pastikan Python 3.10 masih terpasang, lalu coba perintah berikut di CMD:
    echo     py -3.10 --version
    echo.
    echo Hasil yang benar harus menyerupai: Python 3.10.x
    echo.
    pause
    exit /b 1
)

"%BASE_PYTHON_EXE%" %BASE_PYTHON_ARGS% --version >"%VERSION_TEMP%" 2>&1
set "PYTHON_VERSION="
set /p PYTHON_VERSION=<"%VERSION_TEMP%"
del /q "%VERSION_TEMP%" >nul 2>&1

if not defined PYTHON_VERSION (
    call :fatal "Versi Python 3.10 gagal dibaca. Jalankan py -3.10 --version di CMD untuk pemeriksaan."
    exit /b 1
)

echo [OK] Python proyek ditemukan: %PYTHON_VERSION%
echo [OK] Launcher dikunci menggunakan Python 3.10.

REM ==============================================================
REM 2. Gunakan ulang venv yang sudah ada jika memang berbasis 3.10.
REM ==============================================================
if exist "%VENV_DIR%\" if not exist "%VENV_PYTHON%" (
    call :fatal "Folder venv ditemukan, tetapi python.exe di dalamnya tidak ada. Rename folder venv menjadi venv_rusak lalu jalankan run.bat kembali."
    exit /b 1
)

if exist "%VENV_PYTHON%" (
    "%VENV_PYTHON%" -c "import sys; raise SystemExit(0 if sys.version_info[:2] == (3, 10) else 1)" >nul 2>&1
    if errorlevel 1 (
        "%VENV_PYTHON%" --version >"%VERSION_TEMP%" 2>&1
        set "VENV_WRONG_VERSION="
        set /p VENV_WRONG_VERSION=<"%VERSION_TEMP%"
        del /q "%VERSION_TEMP%" >nul 2>&1
        echo.
        echo [GAGAL] Venv lama bukan dibuat dengan Python 3.10.
        echo [INFO] Versi venv saat ini: !VENV_WRONG_VERSION!
        echo.
        echo Venv tidak dapat diganti versi Python tanpa dibuat ulang satu kali.
        echo Rename folder venv menjadi venv_backup, lalu jalankan run.bat lagi.
        echo Launcher berikutnya akan membuat venv baru memakai Python 3.10.
        echo.
        pause
        exit /b 1
    )

    echo [OK] Virtual environment Python 3.10 sudah tersedia.
    echo [OK] Venv lama digunakan kembali; tidak dibuat ulang.
) else (
    echo.
    echo [SETUP 1/3] Virtual environment belum tersedia.
    echo [SETUP 1/3] Membuat venv menggunakan Python 3.10...
    "%BASE_PYTHON_EXE%" %BASE_PYTHON_ARGS% -m venv "%VENV_DIR%"
    if errorlevel 1 (
        call :fatal "Pembuatan virtual environment Python 3.10 gagal. Salin pesan error di atas untuk proses debug."
        exit /b 1
    )
    echo [OK] Virtual environment Python 3.10 berhasil dibuat.
)

if not exist "%VENV_PYTHON%" (
    call :fatal "Python di dalam virtual environment tidak ditemukan. Rename folder venv lalu jalankan run.bat kembali."
    exit /b 1
)

REM Verifikasi ulang setelah venv baru dibuat.
"%VENV_PYTHON%" -c "import sys; raise SystemExit(0 if sys.version_info[:2] == (3, 10) else 1)" >nul 2>&1
if errorlevel 1 (
    call :fatal "Virtual environment tidak menggunakan Python 3.10. Proses dihentikan agar dependency tidak dipasang pada versi yang salah."
    exit /b 1
)

"%VENV_PYTHON%" --version >"%VERSION_TEMP%" 2>&1
set "VENV_PYTHON_VERSION="
set /p VENV_PYTHON_VERSION=<"%VERSION_TEMP%"
del /q "%VERSION_TEMP%" >nul 2>&1
if not defined VENV_PYTHON_VERSION (
    call :fatal "Versi Python di dalam virtual environment gagal dibaca."
    exit /b 1
)
echo [OK] Python aktif di venv: %VENV_PYTHON_VERSION%

REM ==============================================================
REM 3. Hitung fingerprint requirements tanpa FOR/F yang memanggil
REM    executable ber-path terkutip. Ini memperbaiki error:
REM    'venv\Scripts\python.exe" -c "import' is not recognized...
REM ==============================================================
set "CURRENT_REQUIREMENTS_HASH="
for /f "usebackq delims=" %%H in (`powershell.exe -NoProfile -ExecutionPolicy Bypass -Command "$ErrorActionPreference='Stop'; (Get-FileHash -LiteralPath '%REQUIREMENTS_FILE%' -Algorithm SHA256).Hash.ToLowerInvariant()"`) do set "CURRENT_REQUIREMENTS_HASH=%%H"

if not defined CURRENT_REQUIREMENTS_HASH (
    call :fatal "Fingerprint requirements.txt gagal dibuat. PowerShell atau file requirements.txt tidak dapat dibaca."
    exit /b 1
)

set "INSTALLED_REQUIREMENTS_HASH="
if exist "%REQUIREMENTS_MARKER%" set /p INSTALLED_REQUIREMENTS_HASH=<"%REQUIREMENTS_MARKER%"

set "INSTALL_REQUIRED=0"
if /I not "%CURRENT_REQUIREMENTS_HASH%"=="%INSTALLED_REQUIREMENTS_HASH%" set "INSTALL_REQUIRED=1"

REM Verifikasi import library inti. Jika ada library hilang, dependency
REM dipasang ulang walaupun requirements.txt tidak berubah.
if "%INSTALL_REQUIRED%"=="0" (
    "%VENV_PYTHON%" -c "import streamlit, pandas, plotly, networkx, pyvis, bcrypt, transformers, torch, wordcloud, openpyxl; import google.genai" >nul 2>&1
    if errorlevel 1 set "INSTALL_REQUIRED=1"
)

if "%INSTALL_REQUIRED%"=="1" (
    echo.
    echo [SETUP 2/3] Menyiapkan pip pada venv Python 3.10...
    "%VENV_PYTHON%" -m pip install --upgrade pip
    if errorlevel 1 (
        call :fatal "Pembaruan pip gagal. Periksa koneksi internet lalu jalankan run.bat kembali."
        exit /b 1
    )

    echo.
    echo [SETUP 3/3] Menginstall dependency dari requirements.txt...
    echo Proses hanya dilakukan jika dependency belum lengkap atau requirements.txt berubah.
    "%VENV_PYTHON%" -m pip install -r "%REQUIREMENTS_FILE%"
    if errorlevel 1 (
        if exist "%REQUIREMENTS_MARKER%" del /q "%REQUIREMENTS_MARKER%" >nul 2>&1
        call :fatal "Instalasi dependency gagal. Jangan tutup jendela sebelum menyalin pesan ERROR atau FAILED di atas."
        exit /b 1
    )

    >"%REQUIREMENTS_MARKER%" echo %CURRENT_REQUIREMENTS_HASH%
    echo [OK] Seluruh dependency berhasil dipasang pada Python 3.10.
) else (
    echo [OK] Dependency sudah lengkap dan sesuai requirements.txt.
    echo [OK] Tidak ada instalasi ulang dependency.
)

REM Verifikasi terakhir sebelum server dijalankan.
"%VENV_PYTHON%" -m streamlit --version >nul 2>&1
if errorlevel 1 (
    call :fatal "Streamlit belum dapat dijalankan dari virtual environment Python 3.10."
    exit /b 1
)

REM Setup hanya dilakukan sekali. Setelah server dihentikan dengan Ctrl+C,
REM launcher masuk ke menu pilihan tanpa membuat ulang venv atau dependency.
goto :run_dashboard

:run_dashboard
REM Port diperiksa ulang setiap kali dashboard dijalankan kembali.
set "DASHBOARD_PORT=8501"

REM Jika port 8501 sedang dipakai, gunakan 8502.
"%VENV_PYTHON%" -c "import socket; s=socket.socket(); code=s.connect_ex(('127.0.0.1',8501)); s.close(); raise SystemExit(0 if code != 0 else 1)" >nul 2>&1
if errorlevel 1 set "DASHBOARD_PORT=8502"

set "DASHBOARD_URL=http://localhost:%DASHBOARD_PORT%"
echo.
echo ======================================================
echo [INFO] Memulai dashboard...
echo [INFO] Python aktif: %VENV_PYTHON_VERSION%
echo [INFO] Alamat dashboard: %DASHBOARD_URL%
echo [INFO] Browser akan dibuka otomatis.
echo [INFO] Jangan tutup jendela ini selama dashboard digunakan.
echo [INFO] Tekan Ctrl+C untuk menghentikan server.
echo ======================================================
echo.

REM Buka browser beberapa detik setelah proses server dimulai.
start "" /b "%VENV_PYTHON%" -c "import time, webbrowser; time.sleep(4); webbrowser.open('%DASHBOARD_URL%')"

REM Streamlit dijalankan melalui CMD anak. Saat Ctrl+C ditekan, proses
REM Streamlit dihentikan lalu kontrol dikembalikan ke menu launcher.
cmd.exe /d /s /c ""%VENV_PYTHON%" -m streamlit run "%APP_FILE%" --server.port %DASHBOARD_PORT% --server.headless true"
set "STREAMLIT_EXIT=%ERRORLEVEL%"

echo.
echo ======================================================
if "%STREAMLIT_EXIT%"=="0" (
    echo [OK] Dashboard telah dihentikan.
) else (
    echo [INFO] Dashboard telah berhenti dengan kode %STREAMLIT_EXIT%.
    echo [INFO] Jika Anda baru menekan Ctrl+C, kondisi ini normal.
    echo [INFO] Jika berhenti sendiri, periksa pesan error di atas.
)
echo ======================================================
echo.
echo Pilih tindakan berikut:
echo   [R] Jalankan dashboard lagi
echo   [C] Tutup launcher
echo.
choice /C RC /N /M "Tekan R untuk running lagi atau C untuk close: "

if errorlevel 2 goto :close_launcher
if errorlevel 1 goto :run_dashboard

goto :run_dashboard

:close_launcher
echo.
echo [INFO] Launcher ditutup. Sampai jumpa.
timeout /t 1 /nobreak >nul
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
