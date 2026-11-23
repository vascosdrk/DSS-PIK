# CEWS REPOSITORY STRUCTURE & GOVERNANCE GUIDE
**Climate Early Warning System (CEWS) BMKG Stasiun Klimatologi Kepulauan Riau**  
**Document Version**: 2.0 (Post-Reorganization Canonical Structure)  
**Effective Date**: 2026-10-19  

---

## 1. Top-Level Directory Overview

```
PROJECT_ROOT/
├── README.md                      # Ringkasan operasional dan arsitektur repositori
├── .gitignore                     # Filter git untuk mencegah file temporary masuk
├── .env.example                   # Template konfigurasi environment (DB, API, dll)
├── run_cews_demo.bat              # Script bootstrap operasional (MariaDB + FastAPI + Vite)
├── stop_cews_demo.bat             # Script penghentian layanan operasional
├── powershell.cmd                 # Helper shell execution
│
├── config/                        # Seluruh konfigurasi aturan, database, dan path
│   ├── paths.py                   # Canonical dynamic path resolver untuk seluruh modul
│   ├── cews_config.yaml           # Konfigurasi parameter pipeline
│   ├── cews_rules/                # Excel aturan operasional BMKG (cews_rules.xlsx)
│   ├── database/                  # Skema DDL MariaDB (schema.sql)
│   └── environment/               # Konfigurasi environment tambahan
│
├── data/                          # Repositori data primer, terdistribusi per siklus hidup
│   ├── raw/                       # Data mentah / sumber primer (immutable)
│   │   ├── rainfall/              # final_rainfall_daily.parquet, observation_daily.parquet
│   │   ├── spi/                   # SPI_all_30d_dasarian.xlsx (Authoritative SPI)
│   │   └── forecast/              # Probabilitas prakiraan ECMWF (dasarian & bulanan)
│   ├── reference/                 # Metadata stasiun, koordinat, dan tabel lookup
│   │   └── stations/              # station_metadata.parquet, mapping_tambahan.xlsx
│   ├── processed/                 # Dataset turunan intermediate aktif
│   │   ├── indicators/            # cews_indicator_dataset.parquet
│   │   ├── hth/                   # hth_daily.parquet
│   │   └── forecast/              # Matriks probabilitas dasarian & bulanan
│   ├── operational/               # Artifak operasional terkini (current state)
│   │   ├── current/               # cews_current_warning.parquet (57 stasiun aktif)
│   │   └── snapshot/              # cews_forecast_snapshot.parquet (snapshot prakiraan)
│   ├── historical/                # Ledger analitis historis (immutable)
│   │   └── warnings/              # cews_warning_history.parquet (2.052 dasarian 2025)
│   └── archive/                   # Data lama / legacy yang tidak lagi aktif
│       ├── legacy_spi/            # Buku kerja SPI lama (2021-2025) & parquet eksperimen
│       ├── superseded_processed/  # Dataset riset 2021-2025 yang telah digantikan
│       └── archive_manifest.csv   # Katalog lengkap berkas arsip & SHA-256
│
├── pipeline/                      # Skrip eksekusi pipeline data & Decision Engine
│   ├── generate_cews_decision_engine.py  # Mesin keputusan utama (PDKM & PDCHT)
│   ├── generate_cews_indicator_pipeline.py# Pipeline ekstraksi & integrasi indikator
│   ├── generate_hth_pipeline.py          # Perhitungan Hari Tanpa Hujan
│   ├── generate_probability_pipeline.py  # Ekstraksi probabilitas dasarian
│   ├── generate_probability_monthly_pipeline.py # Ekstraksi probabilitas bulanan
│   ├── generate_spi_pipeline.py          # Pipeline kalkulasi SPI
│   └── prepare_cews_data.py              # Utilitas persiapan data awal
│
├── backend/                       # REST API Backend (FastAPI + MariaDB)
│   ├── main.py                    # Entrypoint FastAPI & routing API v1
│   ├── database.py                # Connection pool & query MariaDB
│   ├── evaluation.py              # Layanan diagnostik & evaluasi kualitas data
│   └── schemas.py                 # Skema data Pydantic (Contract A & B)
│
├── frontend/                      # Web GIS Dashboard (React + Leaflet + Vite)
│   ├── src/                       # Komponen UI, peta interaktif, banner status
│   ├── package.json               # Konfigurasi dependency Node.js
│   └── vite.config.js             # Konfigurasi Vite dev/build
│
├── scripts/                       # Skrip utilitas, pemeliharaan, dan migrasi
│   ├── migration/                 # migrate_cews_to_mariadb.py (Sinkronisasi DB)
│   ├── validation/                # Skrip validasi diagnostik stasiun (Singkep, dll)
│   └── utilities/                 # Skrip bantu audit dan inspeksi data
│
├── tests/                         # Pengujian otomatis terstruktur
│   ├── regression/                # test_october_2026_acceptance.py (Uji regulasi)
│   ├── integration/               # test_dashboard_contract.py (Uji full-stack)
│   ├── api/                       # test_api_endpoints.py (Uji endpoint backend)
│   ├── unit/                      # Pengujian unit kalkulasi & logika
│   └── pipeline/                  # Pengujian integritas pipeline
│
├── reports/                       # Laporan formal, audit, dan sertifikasi operasional
│   ├── operational/               # cews_operational_qc_report.txt, decision QC
│   ├── validation/                # Laporan QC indikator
│   ├── audits/                    # shadow_current_comparison.csv, laporan audit
│   └── archive/                   # Log eksekusi lama dan catatan pemrosesan
│
├── docs/                          # Dokumentasi teknis, regulasi, dan repositori
│   ├── repository/                # STRUCTURE.md, DATA_LINEAGE.md, manifests
│   ├── operations/                # Handover, Project Memory, System docs
│   └── audits/                    # Laporan audit teknis dan pemetaan stasiun
│
├── outputs/                       # Direktori ekspor produk user-facing (CSV/Excel/Peta)
└── logs/                          # Runtime service logs (MariaDB, uvicorn, dev server)
```

---

## 2. Directory Content Guidelines

| Direktori | Apa yang Boleh Disimpan | Apa yang DILARANG Disimpan |
|---|---|---|
| `config/` | Berkas konfigurasi YAML, JSON, spreadsheet aturan baku (`cews_rules.xlsx`), DDL database (`schema.sql`), dan modul resolusi path (`paths.py`). | Dataset operasional, dump log runtime, file backup sementara (`.bak`, `.tmp`). |
| `data/raw/` | Data mentah primer hasil observasi BMKG dan prakiraan ECMWF resmi. File bersifat **IMMUTABLE** (hanya dibaca). | File hasil kalkulasi sementara, file modifikasi yang mengubah data sumber. |
| `data/reference/` | Metadata stasiun BMKG, koordinat geografis, batas administratif kabupaten/kota, dan tabel mapping kode stasiun. | Status peringatan dinamis, data observasi harian. |
| `data/processed/` | Dataset perantara hasil agregasi baku (indikator gabungan, seri HTH terverifikasi, matriks probabilitas). | File duplikat berulang, log pemrosesan, file debug eksperimen. |
| `data/operational/` | Tepat SATU salinan kanonikal status peringatan terkini (`cews_current_warning.parquet`) dan snapshot prakiraan aktif. | Histori multi-tahun, file perbandingan eksperimen, file draft. |
| `data/historical/` | Ledger analitis historis yang telah difinalisasi (`cews_warning_history.parquet`). Data bersifat kekal (*permanent record*). | Status aktif saat ini, file data yang belum divalidasi. |
| `data/archive/` | Sumber data lama, format spreadsheet usang, atau dataset riset yang telah digantikan sumber baru. | File kerja aktif yang masih diakses oleh pipeline harian/dasarian. |
| `reports/` | Laporan QC formal, sertifikat penerimaan dasarian, berkas audit matematis. | Dataset Parquet mentah, kode program. |
| `outputs/` | File hasil ekspor untuk konsumsi pengguna (tabel CSV, laporan PDF/Excel distribusi, gambar peta). | Data mesin permanen (Parquet database kanonikal). |

---

## 3. Authoritative Data Locations

- **SPI 30-Hari Dasarian**: `data/raw/spi/SPI_all_30d_dasarian.xlsx` (Sheet: `SPI`)
- **Observasi Curah Hujan Harian**: `data/raw/rainfall/final_rainfall_daily.parquet`
- **Metadata Stasiun & Pos Hujan**: `data/reference/stations/station_metadata.parquet`
- **Aturan Keputusan Regulasi**: `config/cews_rules/cews_rules.xlsx`
- **Status Peringatan Operasional Aktif**: `data/operational/current/cews_current_warning.parquet`
- **Histori Analitis Peringatan 2025**: `data/historical/warnings/cews_warning_history.parquet`

---

## 4. Archive & Deletion Policy

1. **Archive Policy**: Berkas data yang tidak lagi digunakan dalam pipeline harian dipindahkan ke `data/archive/<subdomain>/` dan dicatat dalam `data/archive/archive_manifest.csv` lengkap dengan alasan pengarsipan dan nilai SHA-256.
2. **Deletion Policy**: Berkas yang boleh dihapus HANYA berkas yang 100% *disposable* dan *reproducible* (misalnya direktori `__pycache__`, `.pytest_cache`, berkas lock `~$*.xlsx`, dan *build artifacts* `dist/` yang dapat dihasilkan ulang seketika dengan `npm run build`). Seluruh penghapusan dicatat dalam `docs/repository/deleted_generated_files_manifest.csv`.
