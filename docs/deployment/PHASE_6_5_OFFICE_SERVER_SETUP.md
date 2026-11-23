# PHASE 6.5 — OFFICE SERVER SETUP (WINDOWS)

## Prasyarat Server Kantor BMKG
1. Windows 10/11 atau Windows Server 2019/2022 (64-bit).
2. Python `3.12+` dengan dependensi dari `requirements.txt`.
3. Node.js `20+` (hanya untuk build `npm --prefix frontend run build`).
4. MariaDB `11.4+` dengan database `cews_db` ter-restore dan akun hak minimum (`dss_pik_app`).

## Langkah Setup
1. Salin seluruh repository ke direktori target (misal `C:\DSS-PIK\`).
2. Salin `.env.production.example` menjadi `.env` dan isi credential production.
3. Build frontend production:
   ```cmd
   npm --prefix frontend run build
   ```
4. Jalankan layanan production:
   ```cmd
   run_cews_prod.bat
   ```
5. (Opsional) Daftarkan `run_cews_prod.bat` pada Windows Task Scheduler (*At startup*, *Run whether user is logged on or not*) setelah disetujui administrator.

