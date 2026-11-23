# DSS-PIK — Decision Support System Peringatan Iklim Kepulauan Riau
**BMKG Stasiun Meteorologi Kelas II Raja Haji Fisabilillah Tanjungpinang**

Sistem pendukung keputusan peringatan dini iklim operasional untuk memantau dan memetakan potensi **PDKM (Peringatan Dini Kekeringan Meteorologis)** dan **PDCHT (Peringatan Dini Curah Hujan Tinggi)** pada **57 Stasiun Pengamatan** dan **59 Kecamatan (7 Kabupaten/Kota)** di Provinsi Kepulauan Riau.

---

## 1. Menjalankan Server Utama LAN (Komputer A)
Pastikan layanan **MariaDB** aktif pada port `3306`, lalu jalankan:
```cmd
run_cews_lan.bat
```
- Backend FastAPI dan Frontend Production (`frontend/dist/`) akan berjalan pada `0.0.0.0:8000` (1 worker).
- Browser pada Komputer A otomatis terbuka ke `http://127.0.0.1:8000/`.
- Komputer Client (Komputer B, C, dst. pada Wi-Fi/LAN yang sama) dapat langsung mengakses `http://<IP-LAN-KOMPUTER-A>:8000` dan login menggunakan akun operator bersama.

Untuk menghentikan server tanpa mematikan MariaDB:
```cmd
stop_cews_lan.bat
```

---

## 2. Backup & Pemindahan ke Komputer Baru (Migrasi Portable)
- **Di Komputer Lama**: Jalankan `prepare_dss_pik_migration.bat` untuk membuat dump SQL MariaDB dan manifest SHA-256 seluruh 34 file Parquet di `C:\DSS_PIK_BACKUPS`.
- **Di Komputer Baru**: Salin folder proyek, sesuaikan `.env`, pulihkan database dengan `python scripts\restore_dss_pik.py`, dan verifikasi kesiapan dengan `setup_dss_pik_new_pc.bat`.

---

## 3. Dokumentasi Utama
- **Konteks Teknis & Aturan Decision Engine**: [`docs/handover/AI_BOOTSTRAP_CONTEXT.md`](docs/handover/AI_BOOTSTRAP_CONTEXT.md) & [`docs/handover/PROJECT_HANDOVER.md`](docs/handover/PROJECT_HANDOVER.md)
- **Panduan Operasional LAN Multi-User**: [`docs/deployment/PHASE_6_11_LAN_MULTIUSER.md`](docs/deployment/PHASE_6_11_LAN_MULTIUSER.md)
- **Panduan Instalasi & Migrasi Portable**: [`docs/deployment/PHASE_6_12_PORTABLE_INSTALLATION_GUIDE.md`](docs/deployment/PHASE_6_12_PORTABLE_INSTALLATION_GUIDE.md) & [`docs/deployment/PHASE_6_12_MIGRATION_RUNBOOK.md`](docs/deployment/PHASE_6_12_MIGRATION_RUNBOOK.md)
- **Laporan Audit & Pembersihan Repository**: [`docs/maintenance/PHASE_6_12_REPOSITORY_AUDIT.md`](docs/maintenance/PHASE_6_12_REPOSITORY_AUDIT.md) & [`docs/maintenance/PHASE_6_12_CLEANUP_REPORT.md`](docs/maintenance/PHASE_6_12_CLEANUP_REPORT.md)
