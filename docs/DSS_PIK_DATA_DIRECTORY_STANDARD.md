# DSS-PIK DATA DIRECTORY & GOVERNANCE STANDARD
**Sistem:** Decision Support System Peringatan Iklim Kepulauan Riau (DSS-PIK)  
**Institusi:** BMKG Stasiun Meteorologi Kelas II Raja Haji Fisabilillah Tanjungpinang  
**Versi:** 2.0 (November 2026)  
**Tujuan Dokumen:** Standar tata kelola direktori, penempatan data, dan pemeliharaan repository untuk operasionalisasi rutin DSS-PIK.

---

## 1. STRUKTUR DIREKTORI STANDAR REPOSITORY

Struktur direktori DSS-PIK distandarkan dengan hierarki fungsional berikut:

```text
DSS-PIK/
├── backend/                  # Kode sumber Backend FastAPI, Decision Engine, API routes
├── frontend/                 # Web GIS React 18 / Vite / Tailwind UI
│   ├── src/
│   │   ├── components/       # Komponen UI (OfficialMapModal, MapPreview, dll.)
│   │   └── ...
│   └── package.json
├── pipeline/                 # Pipeline ingestion, evaluasi bahaya, sinkronisasi data
├── config/                   # Konfigurasi sistem, path absolut/relatif, parameter iklim
├── database/                 # Skema DDL MariaDB, inisialisasi basis data
├── data/                     # PENYIMPANAN DATA UTAMA
│   ├── raw/                  # Data mentah kanonikal (Read-Only)
│   │   ├── rainfall/         # Parquet curah hujan harian (final_rainfall_daily, observation_daily)
│   │   ├── spi/              # Parquet SPI terstandar (bulanan, dasarian, harian)
│   │   └── forecast/         # Workbook probabilitas curah hujan ECMWF
│   ├── processed/            # Data terproses kanonikal & snapshot operasional
│   ├── reference/            # Aset spasial kanonikal & metadata BMKG
│   │   ├── boundaries/       # GeoJSON batas wilayah (kepri_kabkot, kepri_kecamatan, kepri_zom)
│   │   ├── PETA/             # Shapefile resmi batas KEPRI (KEPRI.shp, .shx, .dbf, .prj)
│   │   ├── map_templates/    # Template peta kartografi resmi BMKG (PDCI & PDKM)
│   │   └── stations/         # Metadata kanonikal 57 stasiun (station_metadata.parquet)
│   ├── operational/          # Output operasional aktif
│   │   └── maps/             # Peta resmi hasil generate (PETA_PDKM_*, PETA_PDCHT_*) format JPG 300 DPI
│   └── output/               # Artefak integrasi eksternal
│       └── sih3/             # File ekspor JSON standar SIH3 Provinsi Kepulauan Riau
├── tambahan/                 # Folder staging file Excel sumber (input operasional manual)
├── backups/                  # Backup basis data MariaDB & snapshot sistem
├── reports/                  # Laporan audit resmi, hasil pengujian, ringkasan pemeliharaan
│   └── maintenance/          # Log pembersihan repository & hash baseline kriptografis
├── docs/                     # Dokumentasi arsitektur, SOP operasional, checklist verifikasi
├── logs/                     # Log runtime aplikasi (backend.log, frontend.log)
├── scripts/                  # Script pemeliharaan, audit integritas, verifikasi pre-operasional
├── tests/                    # Rangkaian pengujian otomatis (unit & integration)
└── scratch/                  # Direktori kerja sementara (scratchpad / ephemeral)
```

---

## 2. ATURAN PENEMPATAN FILE & DATA GOVERNANCE

### A. Data Curah Hujan (Rainfall / CH) — *Zero-Touch Rule*
1. **Status Imutabel:** Seluruh data curah hujan historis di `data/raw/rainfall/` dan tabel `cews_rainfall_daily` berstatus **Read-Only**.
2. **Larangan Keras:** Dilarang melakukan manipulasi in-place, penghapusan, penggantian nama, deduplikasi, atau penimpaan pada dataset curah hujan kanonikal tanpa prosedur audit resmi.
3. **Protokol Penambahan Data Baru:**
   - File baru ditempatkan di `tambahan/` atau `data/raw/rainfall/incoming/`.
   - Data dibaca ke dalam tabel staging `staging_rainfall_import` terlebih dahulu.
   - Setelah validasi integritas (rentang nilai 0–1000 mm, stasiun ID valid, tanggal valid), data di-append ke tabel utama via transaksi ACID.

### B. Data SPI (Standardized Precipitation Index)
- Disimpan dalam format Apache Parquet dengan kompresi Snappy di `data/raw/spi/`:
  - `bulanan/SPI_monthly.parquet`
  - `dasarian/SPI_all_30d.parquet` dan `SPI_all_90d.parquet`
  - `harian/SPI_all_30d.parquet` dan `SPI_all_90d.parquet`
- Perhitungan ulang SPI hanya dilakukan bila ada penambahan data curah hujan baru minimal 1 dasarian penuh.

### C. Aset Geospasial & Peta Referensi
- **Shapefile Batas Wilayah:** Tersimpan di `data/reference/PETA/` (CRS: WGS84 EPSG:4326). Shapefile ini merupakan rujukan batas resmi kabupaten/kota untuk pewarnaan poligon generator peta.
- **GeoJSON Batas:** `data/reference/boundaries/kepri_kabkot.geojson` dan `kepri_zom.geojson` digunakan untuk visualisasi interaktif pada peta Leaflet dashboard.
- **Template Resmi:** `data/reference/map_templates/` menyimpan master background kartografi BMKG:
  - `04. Peta PDKM_Agustus II 26.jpg` (Template Peta Kekeringan Meteorologis)
  - `01. Peta Lampiran PDCI_Das II Jan 25.jpg` (Template Peta Curah Hujan Tinggi)

### D. Keluaran Operasional (Operational Output)
- **Generator Peta Resmi (`data/operational/maps/`):**
  - Pola penamaan PDKM: `PETA_PDKM_<periode>_<timestamp>.jpg`
  - Pola penamaan PDCHT: `PETA_PDCHT_<periode>_<timestamp>.jpg`
  - Resolusi wajib: 300 DPI, format RGB JPEG.
- **Ekspor JSON SIH3 (`data/output/sih3/`):**
  - Pola penamaan: `PERINGATAN_DINI_KEPRI_<periode>_<timestamp>.json`
  - File link aktif terkini: `sih3_regional_warning_latest.json`.

---

## 3. KEBIJAKAN RETENSI DATA (DATA RETENTION POLICY)

Untuk mencegah pembengkakan ukuran repository secara berkala:

| Jenis Data / File | Kebijakan Retensi | Mekanisme Pembersihan |
| :--- | :--- | :--- |
| **Data CH Kanonikal** | **Permanen / Selamanya** | Tidak boleh dihapus atau dipangkas. |
| **Peta Resmi Terbitan Final (JPG)** | **Permanen (Arsip Operasional)** | Disimpan sebagai rekam jejak peringatan dini BMKG. |
| **Hasil Render Uji / Intermediate** | **Rolling Retensi (7 Hari)** | Render pengujian sementara dihapus otomatis setelah audit. |
| **Ekspor JSON SIH3** | **5 Rilis Terakhir per Periode** | Rilis resmi dipertahankan, uji debug dihapus. |
| **Direktori `scratch/`** | **Ephemeral (Sementara)** | Bebas dibersihkan setiap rilis operasional. Jangan menyimpan dependensi produksi di sini. |
| **Log Runtime (`logs/`)** | **Maksimum 50 MB per file** | Rotasi log otomatis via logging handler. |
| **Cache Bytecode (`__pycache__`)** | **Non-persistent** | Dikecualikan dari version control via `.gitignore`. |

---

## 4. INTEGRITAS KONFIGURASI `.gitignore`

Pastikan file `.gitignore` mencakup direktori sementara berikut agar repository tetap ramping:
```gitignore
# Bytecode & Caches
__pycache__/
*.py[cod]
.pytest_cache/
.vite/
node_modules/

# Temporary / Scratch
scratch/*
!scratch/.gitkeep

# Local Logs
logs/runtime/*.log
logs/*.log

# Operational Intermediate Render Dumps (keep official outputs)
# data/operational/maps/temp_*
```

---

## 5. KEPATUHAN TATA KELOLA KEPUTUSAN OPERATOR

1. **Pemilihan Hazard Terpisah:** Operator memilih moda keluaran yang spesifik (PDKM atau PDCHT) pada generator peta resmi.
2. **Integritas Rekomendasi:** Status rekomendasi DSS-PIK dihitung secara deterministik dari HTH, SPI, dan Probabilitas ECMWF.
3. **Audit Trail Override:** Jika operator mengubah status rekomendasi menjadi manual override, alasan penyesuaian dicatat secara eksplisit ke dalam metadata JSON SIH3.

