# PHASE 6.13 — FINAL HANDOVER & PORTABLE MIGRATION GUIDE
**Sistem:** Decision Support System Peringatan Iklim (DSS-PIK) Kepulauan Riau  
**Institusi:** BMKG Stasiun Meteorologi Kelas II Raja Haji Fisabilillah Tanjungpinang  

---

## 1. Ringkasan Kesiapan Sistem
DSS-PIK kini sepenuhnya **portable** dan siap dipindahkan ke komputer server baru kapan saja tanpa perlu membangun ulang aplikasi, tanpa perlu menginstal Node.js untuk runtime, dan tanpa perlu menghitung ulang SPI historis.

## 2. Urutan Perintah Pemindahan Server (Step-by-Step)

### Langkah 1 — Buat Paket Backup di Komputer Lama
```cmd
prepare_dss_pik_migration.bat
```

### Langkah 2 — Salin ke Komputer Baru
Salin folder proyek `DSS-PIK` (misal ke `D:\DSS-PIK`) dan folder backup terbaru dari `C:\DSS_PIK_BACKUPS\backup_YYYYMMDD_HHMMSS`.

### Langkah 3 — Sesuaikan `.env` & Pulihkan Database di Komputer Baru
Edit `.env` (isi `CEWS_DB_PASSWORD`), lalu jalankan:
```cmd
pip install -r requirements.txt
python scripts\restore_dss_pik.py --backup-dir "C:\DSS_PIK_BACKUPS\backup_YYYYMMDD_HHMMSS"
setup_dss_pik_new_pc.bat
```

### Langkah 4 — Jalankan Server LAN Multi-User
```cmd
run_cews_lan.bat
```

## 3. Prosedur Rollback
Apabila terjadi kendala pada komputer baru saat proses migrasi:
1. Komputer lama (`C:\LATSAR\ASLI2`) sama sekali tidak diubah selama proses backup/ekspor, sehingga operator dapat langsung menjalankan kembali `run_cews_lan.bat` pada komputer lama tanpa downtime.
2. Untuk menghentikan server di komputer mana pun tanpa mematikan MariaDB, jalankan `stop_cews_lan.bat`.

