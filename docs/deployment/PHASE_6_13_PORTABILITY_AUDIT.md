# PHASE 6.13 — PORTABILITY & PATH INDEPENDENCE AUDIT
**Sistem:** DSS-PIK BMKG Stasiun Meteorologi Kelas II Raja Haji Fisabilillah Tanjungpinang  
**Lokasi Salinan Uji (Rehearsal):** `C:\DSS_PIK_MIGRATION_REHEARSAL\DSS-PIK\`  
**Lokasi Produksi Aktif:** `C:\LATSAR\ASLI2\`  

---

## 1. Audit Resolusi Path Internal (`config/paths.py` & `backend/`)
Seluruh modul aplikasi menggunakan `Path(__file__).resolve().parent.parent` untuk menentukan `PROJECT_ROOT` secara dinamis pada saat runtime:

| Komponen / Path | Resolusi pada Salinan Uji | Status |
|---|---|---|
| `config.paths.PROJECT_ROOT` | `C:\DSS_PIK_MIGRATION_REHEARSAL\DSS-PIK` | **PASS** (100% Independen dari `C:\LATSAR\ASLI2`) |
| `PATH_SPI_PARQUET_DASARIAN_90D` | `...\DSS-PIK\data\raw\spi\dasarian\SPI_all_90d.parquet` | **PASS** |
| `PATH_SPI_PARQUET_DASARIAN_30D` | `...\DSS-PIK\data\raw\spi\dasarian\SPI_all_30d.parquet` | **PASS** |
| `PATH_STATION_METADATA` | `...\DSS-PIK\data\reference\stations\station_metadata.parquet` | **PASS** |
| `SPEI_SRC` (`spi_calculation_worker.py`) | `...\DSS-PIK\SPEI\src` | **PASS** |
| `_FRONTEND_DIST` (`backend/main.py`) | `...\DSS-PIK\frontend\dist` | **PASS** |
| `ROOT_DIR` (`run_cews_lan.bat`) | `%~dp0` (Direktori tempat file `.bat` berada) | **PASS** |

---

## 2. Audit Ketergantungan Perangkat Lunak Komputer Baru (Phase 13.6)

1. **Apa saja software yang WAJIB dipasang di komputer baru?**
   - **Python `3.10` – `3.12` (64-bit)** + paket di `requirements.txt`.
   - **MariaDB Server `11.4+` / `13.0+`** (berjalan pada `127.0.0.1:3306`).
   - **Browser Modern** (Edge / Chrome / Firefox).
2. **Apa saja yang TIDAK PERLU dipasang untuk menjalankan server?**
   - **Node.js & npm TIDAK wajib untuk runtime** karena `frontend/dist/` sudah berisi bundle produksi yang langsung dilayani oleh FastAPI (`CEWS_SERVE_FRONTEND=true`). Node.js hanya diperlukan jika pengembang ingin mengubah kode React di `frontend/src/` dan menjalankan `vite build`.
   - Komputer Client (Komputer B, C, dst.) **tidak perlu** menginstal Python, MariaDB, maupun menyalin folder proyek.
3. **Apa saja yang harus disalin ke komputer baru?**
   - Folder utama `DSS-PIK/` (`1,763` file, `~259.88 MB`, tanpa `node_modules`).
   - File dump SQL MariaDB terbaru (`cews_db_YYYYMMDD_HHMMSS.sql`) dan `parquet_sha256_manifest.json`.
4. **Apa saja yang harus dikonfigurasi ulang?**
   - Berkas `.env` pada komputer baru: `CEWS_DB_PASSWORD` (dan `CEWS_DB_USER` / `CEWS_DB_PORT` jika berbeda dari `root` / `3306`).
   - Rule Windows Firewall Inbound TCP Port `8000` (`LocalSubnet`, profil `Private`) pada komputer baru.
5. **Apakah DSS-PIK bisa dijalankan tanpa internet setelah seluruh dependency tersedia?**
   - **YA (`PASS`)**. Seluruh kalkulasi Decision Engine, SPI Generator (`SPEI/src`), batas wilayah GeoJSON/SHP, template peta resmi BMKG, dan database MariaDB berjalan 100% lokal/offline di dalam jaringan LAN kantor.

