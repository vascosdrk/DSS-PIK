# PHASE 6.13 — NEW PC MIGRATION CHECKLIST

Gunakan checklist ini saat memindahkan server utama DSS-PIK ke komputer kantor baru:

## A. Persiapan di Komputer Lama
- [ ] Jalankan `prepare_dss_pik_migration.bat`.
- [ ] Pastikan file dump SQL (`cews_db_*.sql`) dan `parquet_sha256_manifest.json` terbentuk di `C:\DSS_PIK_BACKUPS\backup_YYYYMMDD_HHMMSS`.
- [ ] Salin folder proyek `DSS-PIK` dan folder backup terbaru ke USB/External Drive.

## B. Instalasi Prasyarat di Komputer Baru
- [ ] Instal **Python 3.10 – 3.12 (64-bit)** dan centang *"Add Python to PATH"*.
- [ ] Instal **MariaDB Server 11.4+ / 13.0+** pada port `3306` dan catat password `root`.
- [ ] Tempelkan folder proyek ke lokasi target (misal `D:\DSS-PIK` atau `C:\DSS-PIK`).

## C. Konfigurasi & Restore Data di Komputer Baru
- [ ] Buka berkas `.env` di folder proyek dan sesuaikan `CEWS_DB_PASSWORD`.
- [ ] Buka Command Prompt di folder proyek dan instal paket Python:
      `pip install -r requirements.txt` (atau `setup_dss_pik_new_pc.bat --create-venv`).
- [ ] Pulihkan database MariaDB dan verifikasi SHA-256 Parquet:
      `python scripts\restore_dss_pik.py --backup-dir "PATH_KE_FOLDER_BACKUP"`
- [ ] Jalankan pemeriksaan kesiapan:
      `setup_dss_pik_new_pc.bat` (pastikan muncul `[SUKSES] KOMPUTER BARU SIAP MENJALANKAN DSS-PIK`).

## D. Aktivasi Server LAN & Firewall
- [ ] Buka PowerShell sebagai **Administrator** dan izinkan port `8000` untuk jaringan LAN lokal:
      `New-NetFirewallRule -DisplayName "DSS-PIK LAN Port 8000" -Direction Inbound -Protocol TCP -LocalPort 8000 -RemoteAddress LocalSubnet -Action Allow -Profile Private`
- [ ] Jalankan `run_cews_lan.bat`.
- [ ] Pastikan browser di komputer server terbuka otomatis ke `http://127.0.0.1:8000/` dan dapat login.
- [ ] Buka `http://<IP-LAN-KOMPUTER-BARU>:8000` dari Komputer B dan Komputer C, lalu login menggunakan akun operator bersama.

