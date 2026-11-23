# PHASE 6.14 — PANDUAN LENGKAP INSTALASI PADA KOMPUTER BARU (14 LANGKAH)
**Sistem:** Decision Support System Peringatan Iklim (DSS-PIK) Kepulauan Riau  
**Institusi:** BMKG Stasiun Meteorologi Kelas II Raja Haji Fisabilillah Tanjungpinang  

---

## Langkah 1 — Persiapan Komputer Baru
Pastikan komputer baru menggunakan **Windows 10 / 11 / Windows Server (64-bit)**, terhubung ke jaringan Wi-Fi/LAN kantor dengan profil jaringan **Private**, dan memiliki ruang disk bebas minimal **5 GB**.

## Langkah 2 — Instalasi Python
1. Instal **Python 3.12.10 (64-bit)** (atau Python `3.10`–`3.12`).
2. **Wajib** mencentang opsi **"Add python.exe to PATH"** pada layar pertama installer.
3. Verifikasi di Command Prompt: `python --version`.

## Langkah 3 — Instalasi MariaDB
1. Instal **MariaDB Server 13.0.2 (64-bit)** (atau MariaDB `11.4 LTS`).
2. Gunakan port standar **`3306`** dan aktifkan sebagai Windows Service.
3. Catat password akun `root` MariaDB yang Anda buat.

## Langkah 4 — Penyalinan Portable Package
Salin folder `DSS-PIK_PORTABLE_RELEASE_2026` ke komputer baru, lalu tempatkan subfolder aplikasinya di lokasi target (misal `D:\DSS-PIK\` atau `C:\DSS-PIK\`).

## Langkah 5 — Pembuatan Berkas `.env`
Di dalam folder `DSS-PIK\`, salin `.env.production.example` menjadi `.env`, lalu sesuaikan:
- `CEWS_DB_HOST=127.0.0.1`
- `CEWS_DB_PORT=3306`
- `CEWS_DB_NAME=cews_db`
- `CEWS_DB_USER=root`
- `CEWS_DB_PASSWORD=<password_mariadb_komputer_baru>`
- `DSS_PIK_USERNAME=klimatkepri`
- `DSS_PIK_PASSWORD_HASH=<bcrypt_hash_operator>`
- `DSS_PIK_SESSION_SECRET=<64_char_random_hex>`

## Langkah 6 — Instalasi Dependency Python
Buka Command Prompt di dalam folder `DSS-PIK\`, lalu jalankan:
```cmd
pip install -r requirements-lock.txt
```
*(Atau gunakan `pip install -r requirements.txt` / `setup_dss_pik_new_pc.bat --create-venv`).*

## Langkah 7 — Restore Database MariaDB
Pulihkan dump SQL dari folder `database\cews_db_migration.sql`:
```cmd
mariadb -u root -p -e "CREATE DATABASE IF NOT EXISTS cews_db CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;"
mariadb -u root -p cews_db < ..\database\cews_db_migration.sql
```
*(Atau gunakan `python scripts\restore_dss_pik.py --backup-dir "..\database"`).*

## Langkah 8 — Verifikasi Integritas 34 File Parquet & Database
Jalankan script validasi otomatis:
```cmd
setup_dss_pik_new_pc.bat
```
Pastikan muncul pesan:
- `[OK] Verifikasi SHA-256 berhasil: 34/34 file Parquet identik dan utuh.`
- `[INFO] Database cews_db saat ini memiliki 57 stasiun terdaftar.`

## Langkah 9 — Konfigurasi Windows Firewall (Khusus LAN Kantor)
Buka PowerShell sebagai **Administrator** pada komputer server baru, lalu jalankan:
```powershell
New-NetFirewallRule -DisplayName "DSS-PIK LAN Port 8000" -Direction Inbound -Protocol TCP -LocalPort 8000 -RemoteAddress LocalSubnet -Action Allow -Profile Private
```
*(Jangan pernah membuka port `3306` MariaDB ke jaringan luar).*

## Langkah 10 — Menjalankan Server (`run_cews_lan.bat`)
Klik ganda atau jalankan:
```cmd
run_cews_lan.bat
```
Server akan memverifikasi `/health` (HTTP 200), membuka browser default di komputer server ke `http://127.0.0.1:8000/`, dan menampilkan `Client URL: http://<IP-LAN-SERVER>:8000`.

## Langkah 11 — Mengakses DSS-PIK dari Komputer Client (Komputer B, C, dst.)
Pada komputer client di Wi-Fi/LAN yang sama:
1. Buka browser (Chrome / Edge / Firefox) ke `http://<IP-LAN-SERVER>:8000`.
2. Login menggunakan akun operator bersama (`klimatkepri`).
3. Seluruh komputer dapat bekerja bersamaan menggunakan satu database dan penyimpanan Parquet pusat.

## Langkah 12 — Menghentikan Server (`stop_cews_lan.bat`)
Untuk menghentikan server DSS-PIK tanpa mematikan layanan MariaDB:
```cmd
stop_cews_lan.bat
```

## Langkah 13 — Backup Rutin
Jalankan backup harian database + 34 file Parquet ke `C:\DSS_PIK_BACKUPS`:
```cmd
python scripts\backup_dss_pik.py
```

## Langkah 14 — Pemulihan (Recovery & Rollback)
Jika terjadi kegagalan pada komputer baru, jalankan `python scripts\restore_dss_pik.py` untuk memulihkan backup terakhir, atau aktifkan kembali `run_cews_lan.bat` pada komputer lama karena komputer sumber tidak dimodifikasi selama proses migrasi.

