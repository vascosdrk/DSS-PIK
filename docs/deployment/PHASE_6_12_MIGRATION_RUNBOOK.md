# PHASE 6.12 — MIGRATION RUNBOOK (PROSEDUR PEMINDAHAN SERVER)

---

## Tahap 1 — Di Komputer Lama (Sumber)
1. Buka Command Prompt di folder proyek DSS-PIK.
2. Jalankan:
   ```cmd
   prepare_dss_pik_migration.bat
   ```
   Script ini akan:
   - Menghentikan backend DSS-PIK secara aman (`stop_cews_lan.bat`).
   - Membuat dump SQL MariaDB terbaru (`cews_db_YYYYMMDD_HHMMSS.sql`) dan manifest SHA-256 untuk 34 file Parquet di `C:\DSS_PIK_BACKUPS\backup_YYYYMMDD_HHMMSS`.
   - Memvalidasi kelengkapan `frontend\dist\index.html` dan `requirements.txt`.
3. Salin folder proyek DSS-PIK dan folder backup terbaru dari `C:\DSS_PIK_BACKUPS\` ke media penyimpanan eksternal.

---

## Tahap 2 — Di Komputer Baru (Target Server Utama LAN)
1. Tempelkan folder proyek ke direktori target (misal `D:\DSS-PIK`) dan folder backup ke `C:\DSS_PIK_BACKUPS`.
2. Pastikan service MariaDB berjalan di port `3306` dan sesuaikan `CEWS_DB_PASSWORD` di `.env`.
3. Jalankan restore database dan verifikasi SHA-256 Parquet:
   ```cmd
   python scripts\restore_dss_pik.py
   ```
   *(Catatan: Jika database target sudah berisi data, script akan meminta konfirmasi eksplisit `YA` sebelum menimpa).*
4. Jalankan validasi kesiapan:
   ```cmd
   setup_dss_pik_new_pc.bat
   ```
5. Nyalakan server LAN:
   ```cmd
   run_cews_lan.bat
   ```
   Catat `Client URL: http://<IP-LAN-BARU>:8000` yang tampil di layar dan bagikan kepada operator Komputer B dan C.

