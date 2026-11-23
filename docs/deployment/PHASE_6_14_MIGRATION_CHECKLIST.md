# PHASE 6.14 — MIGRATION CHECKLIST (OPERATOR & ADMINISTRATOR)

- [ ] **1. Persiapan Paket**: Folder `C:\DSS_PIK_RELEASE\DSS-PIK_PORTABLE_RELEASE_2026\` tersedia lengkap (`DSS-PIK/`, `database/cews_db_migration.sql`, `manifests/`, `documentation/`).
- [ ] **2. Keamanan Kredensial**: Pastikan tidak ada berkas `.env` berisi password plaintext di dalam media transfer terbuka.
- [ ] **3. Prasyarat PC Baru**: Python `3.12.10` (64-bit, di PATH) dan MariaDB `13.0.2` / `11.4+` (port `3306`) sudah terpasang dan berjalan.
- [ ] **4. Konfigurasi `.env`**: Berkas `.env` dibuat di `DSS-PIK\.env` dengan `CEWS_DB_PASSWORD`, `DSS_PIK_PASSWORD_HASH`, dan `DSS_PIK_SESSION_SECRET` yang valid.
- [ ] **5. Dependency Python**: `pip install -r requirements-lock.txt` selesai tanpa error.
- [ ] **6. Restore Database**: `cews_db_migration.sql` berhasil di-restore ke `cews_db` (`13` tabel/view, `57` stasiun, `287,189` baris CH harian).
- [ ] **7. Verifikasi Parquet**: `setup_dss_pik_new_pc.bat` melaporkan `34/34 file Parquet identik dan utuh`.
- [ ] **8. Windows Firewall**: Rule Inbound TCP `8000` (`LocalSubnet`, `Private`) aktif; port `3306` tetap tertutup dari jaringan luar.
- [ ] **9. Startup Server**: `run_cews_lan.bat` menampilkan `Backend: RUNNING`, `Database: CONNECTED`, `Browser: OPEN REQUESTED`.
- [ ] **10. Uji Multi-Client LAN**: Komputer A (`http://127.0.0.1:8000`) serta Komputer B & C (`http://<IP-LAN>:8000`) berhasil login bersamaan.

