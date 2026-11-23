# PHASE 6.14 — FINAL HANDOVER DOCUMENT
**Sistem:** Decision Support System Peringatan Iklim (DSS-PIK) Kepulauan Riau  
**Institusi:** BMKG Stasiun Meteorologi Kelas II Raja Haji Fisabilillah Tanjungpinang  
**Tanggal Serah Terima:** 19 November 2026  

---

## 1. Informasi Arsitektur & Port Jaringan
- **Arsitektur**: Shared LAN Server (Komputer A sebagai Server Utama + Database + Parquet; Komputer B, C, dst. mengakses melalui browser).
- **Port Backend & Frontend Production**: TCP `8000` (`0.0.0.0:8000`, Uvicorn `--workers 1`, melayani `frontend/dist/` secara langsung).
- **Port Database MariaDB**: TCP `3306` (`127.0.0.1:3306`, hanya diakses lokal oleh backend).
- **Lokasi Log Runtime**: `<PROJECT_ROOT>\logs\runtime\backend_lan.log`.
- **Lokasi Data Operasional**: `<PROJECT_ROOT>\data\` (`34` file Parquet + GeoJSON/SHP 59 Kecamatan + template peta resmi BMKG).
- **Lokasi Paket Rilis Portable**: `C:\DSS_PIK_RELEASE\DSS-PIK_PORTABLE_RELEASE_2026\`.

## 2. Cara Menemukan IP LAN & Mengubah Konfigurasi Database
- **Menemukan IP LAN**: Saat `run_cews_lan.bat` dijalankan, IP LAN otomatis dideteksi dan ditampilkan pada baris `Client URL: http://<IP-LAN>:8000`. Dapat juga diperiksa kapan saja melalui `powershell -ExecutionPolicy Bypass -File scripts\check_dss_pik_lan.ps1`.
- **Mengubah Konfigurasi Database**: Edit berkas `<PROJECT_ROOT>\.env` (`CEWS_DB_HOST`, `CEWS_DB_PORT`, `CEWS_DB_NAME`, `CEWS_DB_USER`, `CEWS_DB_PASSWORD`), lalu restart server dengan `stop_cews_lan.bat` dan `run_cews_lan.bat`.

## 3. Cara Mengganti Komputer Server & Rollback
1. Salin `C:\DSS_PIK_RELEASE\DSS-PIK_PORTABLE_RELEASE_2026\` ke komputer server baru.
2. Ikuti 14 langkah pada [`PHASE_6_14_NEW_PC_INSTALLATION_GUIDE.md`](PHASE_6_14_NEW_PC_INSTALLATION_GUIDE.md).
3. **Rollback**: Komputer lama tetap utuh 100%; jika diperlukan rollback, cukup jalankan `run_cews_lan.bat` kembali pada komputer lama dan arahkan browser client ke IP LAN komputer lama.

## 4. Catatan Penting untuk Migrasi Komputer di Masa Depan
1. **Validasi Ulang `release_sha256_manifest.json`**: Periksa dan validasi ulang `release_sha256_manifest.json` setelah final package sync agar hash manifest benar-benar mencerminkan kondisi file terbaru pada paket rilis.
2. **Kesamaan Versi Software pada Migrasi Awal**: Untuk meminimalkan potensi ketidaksesuaian saat migrasi awal, disarankan menggunakan versi software yang sama dengan komputer saat ini: Windows 10/11 64-bit, Python `3.12.10` 64-bit, MariaDB `13.0.2`, dan browser modern (Edge/Chrome).
3. **Offline Python Wheelhouse**: Jika instalasi dilakukan sepenuhnya tanpa koneksi internet, siapkan wheelhouse offline terlebih dahulu (`pip download -r requirements-lock.txt -d offline_wheels`).
4. **Rekonstruksi File `.env`**: Pastikan file `.env` direkonstruksi dengan benar pada komputer tujuan (`CEWS_DB_PASSWORD`, `DSS_PIK_PASSWORD_HASH`, `DSS_PIK_SESSION_SECRET`, `CEWS_SERVE_FRONTEND=true`, `CEWS_ALLOW_LAN=true`).


