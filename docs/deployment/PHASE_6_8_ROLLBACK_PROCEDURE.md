# PHASE 6.8 — ROLLBACK PROCEDURE

Jika terjadi kendala setelah deployment production:

1. Hentikan layanan production:
   ```cmd
   stop_cews_prod.bat
   ```
2. Jika ingin kembali ke mode lokal/development sementara:
   ```cmd
   run_cews.bat
   ```
3. Jika terjadi kerusakan data, lakukan restore database dari backup terakhir di `C:\DSS_PIK_BACKUPS` (lihat `PHASE_6_4_DATABASE_BACKUP_RESTORE.md`) dan verifikasi SHA-256 file Parquet.

