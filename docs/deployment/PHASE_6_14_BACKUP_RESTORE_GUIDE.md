# PHASE 6.14 — DATABASE & PARQUET BACKUP / RESTORE GUIDE

---

## 1. Lokasi Penyimpanan Data & Backup
- **Database Produksi**: MariaDB `cews_db` (`127.0.0.1:3306`).
- **Penyimpanan Parquet Aktif**: `<PROJECT_ROOT>\data\` (`34` file `.parquet`).
- **Direktori Backup Otomatis**: `C:\DSS_PIK_BACKUPS\backup_YYYYMMDD_HHMMSS\` (di luar folder aplikasi, retensi default `30` hari).
- **Paket Rilis Portable**: `C:\DSS_PIK_RELEASE\DSS-PIK_PORTABLE_RELEASE_2026\`.

## 2. Membuat Backup Baru
```cmd
python scripts\backup_dss_pik.py
```
Menghasilkan:
1. `cews_db_YYYYMMDD_HHMMSS.sql` (`mariadb-dump --single-transaction --routines --triggers`).
2. `parquet_snapshot/` (salinan fisik ke-34 file Parquet).
3. `parquet_sha256_manifest.json` (daftar checksum SHA-256).

## 3. Memulihkan (Restore) Database & Memverifikasi Parquet
- **Hanya Verifikasi (Read-Only)**:
  ```cmd
  python scripts\restore_dss_pik.py --verify-only
  ```
- **Restore Penuh (Meminta Konfirmasi Eksplisit `YA` jika Database Sudah Berisi Data)**:
  ```cmd
  python scripts\restore_dss_pik.py --backup-dir "C:\DSS_PIK_BACKUPS\backup_YYYYMMDD_HHMMSS"
  ```

