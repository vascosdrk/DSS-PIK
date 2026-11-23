@echo off
setlocal enabledelayedexpansion

:: ==============================================================================
:: DSS-PIK BMKG KEPULAUAN RIAU - MIGRATION PREPARATION (prepare_dss_pik_migration.bat)
:: Menyiapkan paket migrasi (Database Dump + Parquet SHA-256 Manifest + Validasi)
:: ==============================================================================

set "ROOT_DIR=%~dp0"
cd /d "%ROOT_DIR%"
set "PATH=C:\Windows\System32;C:\Windows;C:\Windows\System32\Wbem;%PATH%"

title DSS-PIK BMKG Kepri - Prepare Migration Bundle

echo ======================================================================
echo   PERSIAPAN MIGRASI SERVER DSS-PIK BMKG KEPULAUAN RIAU
echo ======================================================================

:: 1. Hentikan backend secara aman
echo [1/4] Menghentikan layanan backend DSS-PIK (jika aktif)...
call DSS-PIK.bat stop >nul 2>&1

:: 2. Pastikan MariaDB aktif untuk backup
echo [2/4] Memeriksa koneksi MariaDB pada port 3306...
netstat -ano | findstr ":3306 " | findstr "LISTENING" >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] MariaDB tidak aktif di port 3306. Nyalakan MariaDB terlebih dahulu.
    exit /b 1
)

:: 3. Jalankan backup MariaDB + Parquet SHA-256 Manifest
echo [3/4] Membuat dump SQL MariaDB dan manifest SHA-256 Parquet...
python scripts\backup_dss_pik.py
if %errorlevel% neq 0 (
    echo [ERROR] Gagal membuat backup migrasi.
    exit /b 1
)

:: 4. Validasi kelengkapan repository
echo [4/4] Memvalidasi kelengkapan berkas inti repository...
if not exist "frontend\dist\index.html" (
    echo [ERROR] frontend\dist\index.html belum tersedia. Jalankan: npm --prefix frontend run build
    exit /b 1
)
if not exist "requirements.txt" (
    echo [ERROR] requirements.txt tidak ditemukan.
    exit /b 1
)

echo ======================================================================
echo   [SUKSES] PAKET MIGRASI DSS-PIK SIAP DIPINDAHKAN
echo   1. Salin seluruh folder proyek ini ke komputer baru (misal D:\DSS-PIK).
echo   2. Salin folder backup terbaru dari C:\DSS_PIK_BACKUPS ke komputer baru.
echo   3. Pada komputer baru, jalankan: setup_dss_pik_new_pc.bat
echo ======================================================================
exit /b 0

