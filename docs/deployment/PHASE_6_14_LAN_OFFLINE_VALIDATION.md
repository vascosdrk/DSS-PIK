# PHASE 6.14 — OFFLINE & LAN OPERATIONAL VALIDATION
**Sistem:** DSS-PIK BMKG Kepulauan Riau  

---

## 1. Validasi Operasi Jaringan Lokal (LAN) Tanpa Internet

| Fungsi / Komponen | Kebutuhan Internet | Status Validasi Offline / LAN |
|---|---|---|
| **Login & Multi-Session Auth (`backend/auth.py`)** | **Tidak Perlu (100% Lokal)** | **PASS** — HMAC-SHA256 stateless token & HttpOnly cookie mendukung login bersamaan dari Komputer A, B, dan C dengan satu akun operator |
| **Decision Engine PDKM & PDCHT (`decision_engine.py`)** | **Tidak Perlu (100% Lokal)** | **PASS** — Evaluasi HTH, SPI 90D/30D, Pb20, Pa150–Pa300, PM300–PM500 berjalan di memori server pusat |
| **Agregasi 59 Kecamatan & 7 Kab/Kota (`regional_warning_service.py`)** | **Tidak Perlu (100% Lokal)** | **PASS** — Menggunakan `data/reference/boundaries/kepri_kecamatan.geojson` & `station_kecamatan_mapping.json` lokal |
| **Generator Peta Resmi BMKG JPG/PDF (`map_generator.py`)** | **Tidak Perlu (100% Lokal)** | **PASS** — Merasterisasi `KEPRI.shp` / GeoJSON di atas template JPG lokal (`data/reference/map_templates/`) |
| **Ekspor JSON SIH3 (`/api/v1/maps/generate-json`)** | **Tidak Perlu (100% Lokal)** | **PASS** — Menghasilkan dokumen JSON 59 kecamatan + 7 kabupaten/kota secara lokal |
| **Data Center, Upload CH/SPI/Probabilitas & Download** | **Tidak Perlu (100% Lokal)** | **PASS** — Seluruh unggahan dari Client B/C masuk ke MariaDB & Parquet pusat di Komputer A |
| **Generator SPI Manual (`spi_calculation_service.py`)** | **Tidak Perlu (100% Lokal)** | **PASS** — Menggunakan `SPEI/src` lokal, BestDist CSV lokal, dan `_SPI_COMMIT_LOCK` |
| **Segarkan & Evaluasi (`/api/v1/warnings/refresh-evaluate`)** | **Tidak Perlu (100% Lokal)** | **PASS** — Dilindungi `_REFRESH_EVALUATE_LOCK` (mencegah evaluasi ganda antar-operator) |
| **Basemap Tile Eksternal pada Peta Interaktif Leaflet** | *Opsional Internet* | Poligon GeoJSON batas kabupaten/kecamatan/ZOM dan marker 57 stasiun tetap tampil 100% offline; hanya *background street tile* OpenStreetMap/Carto yang memerlukan koneksi internet jika belum ter-cache di browser |
| **Akuisisi Data Mentah Eksternal (ECMWF / CAMS di luar DSS-PIK)** | *Memerlukan Internet* | Proses pengunduhan file Excel prakiraan dari portal pusat BMKG/ECMWF dilakukan sebelum file diunggah ke DSS-PIK |

---

## 2. Validasi Keamanan & Routing LAN
- **Same-Origin API Routing**: Bundle produksi `frontend/dist/assets/index-BvdkRXCN.js` menggunakan `API_BASE_URL = ''` saat diakses melalui port `:8000`, sehingga browser Komputer B dan C selalu memanggil `http://<IP-SERVER>:8000/api/v1/...` (bukan `127.0.0.1` milik client).
- **Isolasi Port Database**: Port `3306` (MariaDB) hanya diakses oleh backend di `127.0.0.1:3306` dan tidak dibuka ke jaringan LAN. Hanya port `8000` yang dibuka terbatas pada `LocalSubnet` (`Private` profile).

