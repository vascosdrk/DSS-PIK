# PHASE 6.4 — DATABASE BACKUP & RESTORE

## 1. Skrip Backup Terotomasi
Jalankan skrip berikut untuk mem-backup database `cews_db` (`mariadb-dump`) dan seluruh 34 file Parquet beserta manifest SHA-256 ke direktori terpisah (`C:\DSS_PIK_BACKUPS`):

```powershell
python scripts/backup_dss_pik.py
```

## 2. Prosedur Restore (Uji pada Database Sementara)
**PENTING:** Jangan menimpa database production secara langsung saat pengujian.
```powershell
mariadb -u root -p -e "CREATE DATABASE IF NOT EXISTS cews_db_staging;"
mariadb -u root -p cews_db_staging < C:\DSS_PIK_BACKUPS\backup_YYYYMMDD_HHMMSS\cews_db_YYYYMMDD_HHMMSS.sql
```

## 3. Verifikasi Integritas Parquet
Bandingkan checksum pada `parquet_sha256_manifest.json` dengan file aktual menggunakan PowerShell:
```powershell
Get-FileHash data\raw\spi\dasarian\SPI_all_90d.parquet -Algorithm SHA256
```

