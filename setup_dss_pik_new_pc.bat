@echo off
setlocal enabledelayedexpansion

:: ==============================================================================
:: DSS-PIK BMKG KEPULAUAN RIAU - NEW PC SETUP (setup_dss_pik_new_pc.bat)
:: Menyiapkan environment, validasi konfigurasi, database, dan Parquet di PC baru
:: ==============================================================================

set "ROOT_DIR=%~dp0"
cd /d "%ROOT_DIR%"
set "PATH=C:\Windows\System32;C:\Windows;C:\Windows\System32\Wbem;%PATH%"

title DSS-PIK BMKG Kepri - Setup New PC

echo ======================================================================
echo   SETUP DSS-PIK PADA KOMPUTER BARU
echo   Lokasi Proyek: %ROOT_DIR%
echo ======================================================================

:: 1. Cek Python
echo [1/6] Memeriksa instalasi Python...
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Python tidak ditemukan di PATH. Instal Python 3.10 - 3.12 terlebih dahulu.
    exit /b 1
)

:: 2. Buat / Gunakan Virtual Environment jika diminta dengan --create-venv
if "%~1"=="--create-venv" (
    echo [2/6] Membuat virtual environment lokal .venv dan menginstal dependency...
    python -m venv .venv
    call .venv\Scripts\activate.bat
    pip install -r requirements.txt
) else (
    echo [2/6] Memeriksa dependency Python...
    python -c "import fastapi, uvicorn, pymysql, pandas, scipy, pyarrow, openpyxl, geopandas, bcrypt" >nul 2>&1
    if !errorlevel! neq 0 (
        echo [INFO] Menginstal dependency dari requirements.txt...
        pip install -r requirements.txt
    )
)

:: 3. Cek .env
echo [3/6] Memeriksa berkas konfigurasi .env...
if not exist ".env" (
    if exist ".env.production.example" (
        copy /y ".env.production.example" ".env" >nul
        echo [PERHATIAN] Berkas .env baru dibuat dari .env.production.example.
        echo Harap sesuaikan CEWS_DB_PASSWORD dan DSS_PIK_PASSWORD_HASH di .env.
    )
)

:: 4. Cek MariaDB
echo [4/6] Memeriksa layanan MariaDB pada port 3306...
netstat -ano | findstr ":3306 " | findstr "LISTENING" >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] MariaDB belum aktif di port 3306. Pastikan MariaDB terinstal dan berjalan.
    exit /b 1
)

:: 5. Verifikasi Database & Parquet (tanpa menimpa data yang sudah ada secara paksa)
echo [5/6] Memverifikasi database cews_db dan integritas file Parquet...
python scripts\restore_dss_pik.py --verify-only
if %errorlevel% neq 0 (
    echo [PERHATIAN] Verifikasi database memerlukan penyesuaian .env atau restore SQL.
    echo Untuk restore dari backup: python scripts\restore_dss_pik.py --backup-dir "PATH_KE_BACKUP"
    exit /b 1
)

:: 6. Cek Frontend Production Bundle
echo [6/6] Memeriksa bundle production frontend...
if not exist "frontend\dist\index.html" (
    echo [ERROR] frontend\dist\index.html tidak ditemukan. Jalankan: npm --prefix frontend run build
    exit /b 1
)

echo ======================================================================
echo   [SUKSES] KOMPUTER BARU SIAP MENJALANKAN DSS-PIK
echo   Jalankan server LAN dengan perintah: DSS-PIK.bat
echo ======================================================================
exit /b 0
