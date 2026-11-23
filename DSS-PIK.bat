@echo off
setlocal enabledelayedexpansion

:: ==============================================================================
:: DSS-PIK BMKG STASIUN METEOROLOGI KELAS II RAJA HAJI FISABILILLAH TANJUNGPINANG
:: SINGLE UNIFIED OPERATIONAL LAUNCHER (DSS-PIK.bat)
::
:: Cara pakai:
::   - Double-click saat OFF : Otomatis START (MariaDB + Backend + Frontend + Browser)
::   - Double-click saat ON  : Menampilkan DSS-PIK SYSTEM MANAGER (STATUS/STOP/RESTART/LAN)
::   - CLI opsional          : DSS-PIK.bat [start|stop|restart|status|enable-lan|disable-lan|lan-diagnostics|rollback-lan]
:: ==============================================================================

set "ROOT_DIR=%~dp0"
cd /d "%ROOT_DIR%"
set "PATH=C:\Windows\System32;C:\Windows;C:\Windows\System32\Wbem;C:\Windows\System32\WindowsPowerShell\v1.0;%PATH%"

title DSS-PIK BMKG Kepulauan Riau - Unified Operational Launcher

:: Verifikasi Python tersedia di PATH
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo ========================================================================
    echo   [ERROR] Python tidak ditemukan di PATH sistem.
    echo   Pastikan Python 3.12+ telah terinstal dan terdaftar di PATH Windows.
    echo ========================================================================
    if "%~1"=="" pause
    exit /b 1
)

:: Delegasikan seluruh manajemen lifecycle ke backend.unified_launcher
python -m backend.unified_launcher %*
set "EXIT_CODE=%errorlevel%"
exit /b %EXIT_CODE%
