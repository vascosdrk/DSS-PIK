# OFFICE MIGRATION GUIDE — DSS-PIK BMKG TANJUNGPINANG
## Panduan Pemindahan Sistem ke Komputer Operasional Kantor BMKG

---

## 1. SPESIFIKASI & PERSYARATAN SISTEM KANTOR

### A. Persyaratan Perangkat Keras (Hardware)
| Komponen | Spesifikasi Minimum | Rekomendasi Operasional BMKG |
|---|---|---|
| **CPU** | Intel Core i3 Gen 6 / AMD Ryzen 3 (4 Cores) | Intel Core i5 / i7 Gen 8+ (6-8 Cores) |
| **RAM** | 8 GB DDR4 | 16 GB DDR4/DDR5 |
| **Penyimpanan** | 20 GB ruang kosong (SSD SATA) | 50 GB ruang kosong (NVMe SSD M.2) |
| **Jaringan** | 100 Mbps LAN (Ethernet RJ-45) | Gigabit LAN (1000 Mbps) terhubung ke LAN Kantor BMKG |
| **Resolusi Layar** | 1366 x 768 px | 1920 x 1080 px (FHD) atau monitor operasional 2K |

### B. Persyaratan Perangkat Lunak (Software)
1. **Sistem Operasi**: Windows 10 Pro / Enterprise 64-bit (Build 19045+) atau Windows 11 Pro 64-bit.
2. **Python Environment**:
   - Python `3.12.x` (64-bit) terinstal dari python.org.
   - **PENTING**: Centang opsi *"Add python.exe to PATH"* saat instalasi.
3. **Node.js Environment**:
   - Node.js LTS `v20.x` atau `v22.x` (64-bit) beserta `npm`.
4. **Basis Data**:
   - MariaDB Server `11.4.x` (atau MySQL 8.0+). Port default: `3306`.
5. **Web Browser**:
   - Google Chrome, Microsoft Edge, atau Mozilla Firefox versi terbaru.

---

## 2. CHECKLIST SEBELUM PEMINDAHAN (KOMPUTER SUMBER)

Pastikan langkah persiapan berikut telah selesai di komputer asal sebelum file dipindahkan:

- [ ] Matikan proses backend dan frontend dengan mengeksekusi `stop_cews.bat`.
- [ ] Buat salinan dump database MariaDB:
  ```cmd
  mysqldump -u root -p --routines --triggers --events cews_db > cews_db_backup.sql
  ```
- [ ] Verifikasi keutuhan berkas Parquet SPI di `data/raw/spi/` dan file distribusi di `data/reference/spi_distributions/`.
- [ ] Siapkan media penyimpanan eksternal (USB Drive terenkripsi / Harddisk Eksternal) dengan sistem berkas NTFS/exFAT.

---

## 3. PROSEDUR PEMINDAHAN SOURCE CODE & DATA

### Langkah 1: Pengemasan (Packaging)
Salin seluruh isi folder kerja:
`F:\TNJ\paper\DATA_ANALISIS_PRAKIRAAN\CEWS\MAS_HAYU\ASLI`

> **PERHATIAN (OPTIMASI PEMINDAHAN):**
> Folder berikut **TIDAK PERLU** disalin untuk menghemat ruang dan mencegah konflik biner:
> - `frontend/node_modules/` (akan diinstal ulang di komputer kantor via npm)
> - `__pycache__/` dan `.pytest_cache/`
> - `logs/runtime/*.log` dan `logs/runtime/*.pid`

### Langkah 2: Penempatan Folder di Komputer Kantor
Tempatkan folder proyek pada direktori terdedikasi di komputer kantor, misalnya:
`D:\BMKG_CEWS\DSS_PIK\` atau `C:\BMKG_CEWS\DSS_PIK\`

---

## 4. INSTALASI DEPENDENSI DI KOMPUTER KANTOR

Buka **Command Prompt (CMD)** atau **PowerShell** sebagai Administrator di folder proyek komputer kantor:

### A. Konfigurasi Python & Library Backend
Pastikan Python 3.12 terdeteksi:
```cmd
python --version
```
Instal paket dependensi Python yang dibutuhkan:
```cmd
pip install fastapi==0.116.1 uvicorn==0.35.0 pymysql==2.2.8 pandas==2.3.1 pyarrow==24.0.0 scipy==1.17.0 psutil pytest==8.4.1 requests
```
*(Atau gunakan file `requirements.txt` jika tersedia)*.

### B. Konfigurasi Node.js & Library Frontend
Masuk ke direktori frontend dan jalankan instalasi:
```cmd
cd frontend
npm install
npm run build
cd ..
```
Pastikan perintah `npm run build` selesai dengan status sukses (`Exit Code: 0`).

---

## 5. MIGRASI & RESTORE DATABASE MARIADB KANTOR

1. Buka MariaDB Command Line Client di komputer kantor:
   ```sql
   CREATE DATABASE cews_db CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
   EXIT;
   ```
2. Impor file dump yang telah disiapkan:
   ```cmd
   mysql -u root -p cews_db < cews_db_backup.sql
   ```
3. Verifikasi jumlah record di komputer kantor:
   ```sql
   USE cews_db;
   SELECT 'stations', COUNT(*) FROM stations
   UNION ALL
   SELECT 'cews_rainfall_daily', COUNT(*) FROM cews_rainfall_daily
   UNION ALL
   SELECT 'cews_forecast_snapshot', COUNT(*) FROM cews_forecast_snapshot;
   ```
   *Jumlah baris harus persis:*
   - `stations`: 57 baris
   - `cews_rainfall_daily`: 287.144 baris
   - `cews_forecast_snapshot`: 3.113 baris

---

## 6. PENYESUAIAN KONFIGURASI ENVIRONMENT

1. Salin berkas `.env.example` menjadi `.env`:
   ```cmd
   copy .env.example .env
   ```
2. Buka `.env` dan sesuaikan parameter kredensial lokal komputer kantor:
   ```ini
   CEWS_DB_HOST=127.0.0.1
   CEWS_DB_PORT=3306
   CEWS_DB_NAME=cews_db
   CEWS_DB_USER=root
   CEWS_DB_PASSWORD=password_mariadb_kantor
   ```

### Pemeriksaan Path Hardcoded
File `backend/launcher.py` memiliki fallback deteksi mariadbd pada path:
- `C:\Users\vasco\mariadb-11.4\...`  
Jika MariaDB di komputer kantor terpasang pada `C:\Program Files\MariaDB 11.4\bin\mariadbd.exe`, pastikan layanan MariaDB dijalankan sebagai **Windows Service** standar, sehingga launcher secara otomatis mendeteksi koneksi port `3306` tanpa perlu memicu fallback biner.

---

## 7. VERIFIKASI AKHIR & MENJALANKAN SISTEM

1. Jalankan pengujian regresi:
   ```cmd
   python -m pytest -v test_phase42_consistency.py test_phase41_regression.py
   ```
   **Seluruh 20 pengujian wajib PASSED.**
2. Jalankan sistem melalui launcher:
   ```cmd
   run_cews.bat
   ```
3. Buka browser pada URL:
   - Dashboard: `http://localhost:5173/`
   - API Docs: `http://localhost:8000/docs`

---

## 8. PROSEDUR ROLLBACK (JIKA MIGRASI MENGALAMI KENDALA)

Jika terjadi kendala kritis saat pengoperasian di komputer kantor:
1. Hentikan seluruh service di komputer kantor menggunakan `stop_cews.bat`.
2. Hapus basis data `cews_db` di komputer kantor untuk mencegah rekor data korup.
3. Kembali operasikan sistem pada komputer pengembangan awal (`F:\TNJ\paper\DATA_ANALISIS_PRAKIRAAN\CEWS\MAS_HAYU\ASLI`) dengan menjalankan `run_cews.bat`.
4. Periksa berkas log `logs/runtime/launcher.log` dan `logs/runtime/backend.log` untuk mengidentifikasi penyebab kegagalan sebelum mencoba migrasi ulang.

