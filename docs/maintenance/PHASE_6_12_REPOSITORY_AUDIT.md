# PHASE 6.12 — FULL REPOSITORY INVENTORY & DEPENDENCY AUDIT
**Sistem:** Decision Support System Peringatan Iklim (DSS-PIK) BMKG Tanjungpinang  
**Tanggal Audit:** 19 November 2026  
**Baseline Sebelum Cleanup:**
- **Total (Termasuk `node_modules`)**: `13,187` files (`780.30 MB`)
- **Total (Tanpa `node_modules`)**: `5,828` files (`698.44 MB`)
- **Backup Pre-Cleanup Terverifikasi**: `C:\DSS_PIK_BACKUPS\backup_20261119_011157` (`cews_db` SQL dump + 34 file Parquet SHA-256 manifest)

---

## 1. Ringkasan Klasifikasi Direktori & Berkas

| Lokasi / Berkas | Ukuran | Klasifikasi | Alasan & Referensi | Keputusan |
|---|---:|---|---|---|
| `backend/*.py` (18 modul inti) | 1.37 MB | **ACTIVE RUNTIME** | FastAPI app, Decision Engine, Period, Regional/Kecamatan Warning, Ingestion, SPI Service & Worker, Auth, Launcher | **Pertahankan** |
| `backend/*.bak_ingestion` (2 file) | 0.12 MB | **TEMPORARY / DUPLICATE** | Backup kode lama saat pengembangan ingestion | **Hapus** |
| `frontend/src/**`, `frontend/public/**`, `frontend/package*.json`, `frontend/vite.config.js` | 1.60 MB | **ACTIVE RUNTIME** | Source code React + Cobalt Theme (`cobalt-theme.css`) + aset BMKG | **Pertahankan** |
| `frontend/dist/**` | 0.90 MB | **ACTIVE RUNTIME** | Production bundle SPA yang disajikan oleh FastAPI pada mode LAN (`CEWS_SERVE_FRONTEND=true`) | **Pertahankan** |
| `config/**`, `.env`, `.env.example`, `.env.production.example`, `pytest.ini` | 0.04 MB | **ACTIVE CONFIGURATION** | Resolusi path dinamis (`config/paths.py`), aturan `cews_rules.xlsx`, environment | **Pertahankan** |
| `data/raw/spi/**` (5 Parquet kanonikal) | 8.68 MB | **ACTIVE DATA** | `SPI_all_30d.parquet`, `SPI_all_90d.parquet` (harian & dasarian), `SPI_monthly.parquet` | **Pertahankan** |
| `data/raw/spi/**/*.parquet.bak_*` (36 file) | 1.80 MB | **TEMPORARY** | File `.bak` hasil percobaan commit SPI Generator sebelumnya | **Hapus** |
| `data/reference/**` | 114.61 MB | **ACTIVE DATA** | `station_metadata.parquet`, `mapping_tambahan.xlsx`, BestDist CSV, `kepri_kecamatan.geojson`, `KEPRI.shp`, template peta BMKG | **Pertahankan** |
| `data/operational/current/**`, `data/operational/snapshot/**`, `data/processed/**`, `data/raw/rainfall/**`, `data/raw/forecast/**`, `data/historical/**` | 13.80 MB | **ACTIVE DATA** | Data operasional & historis Parquet/Excel | **Pertahankan** |
| `data/operational/maps/**` (406 file) | 129.71 MB | **TEMPORARY / ARTIFACT** | Ratusan peta JPG/PNG/PDF/JSON hasil pengujian otomatis; cukup sisakan 1 set terbaru | **Bersihkan (Sisakan terbaru)** |
| `SPEI/src/**`, `SPEI/pyproject.toml`, `SPEI/*.csv`, `SPEI/README.md`, `SPEI/LICENSE` | 15.00 MB | **ACTIVE RUNTIME** | Library kalkulasi SPI/SPEI yang di-import oleh `backend/spi_calculation_worker.py` | **Pertahankan** |
| `SPEI/.mypy_cache/**`, `SPEI/.venv/**`, `SPEI/.pytest_cache/**`, `SPEI/__pycache__/**`, `SPEI/scratch/**`, `SPEI/outputs/**`, `SPEI/.git/**` | 110.84 MB | **TEMPORARY / UNUSED** | Cache MyPy (46.96 MB), venv lokal SPEI (7.64 MB), output eksperimen SPEI (32.96 MB), sub-git internal (23.11 MB) | **Hapus** |
| `tambahan/template_data_input/**` (9 file) | 7.43 MB | **ACTIVE DEVELOPMENT** | Template resmi input CH/SPI/Probabilitas & fixture `tests/integration/` | **Pertahankan** |
| `tambahan/02_EKSTRAK_POS/DASARIAN/*.xlsx` | 6.25 MB | **ACTIVE DEVELOPMENT** | Fixture multi-vintage ECMWF untuk `test_multivintage_ecmwf.py` & `test_independent_final_acceptance.py` | **Pertahankan (Hapus lock `~$*`)** |
| `tambahan/baru/Entry Data Pos Hujan Bintan.xlsm` | 1.71 MB | **ACTIVE DEVELOPMENT** | Fixture `tests/integration/test_bintan_xlsm_ingestion.py` | **Pertahankan** |
| `tambahan/Timeseries_Kepri.xls` (52.3 MB), `tambahan/baru/Timeseries_Kepri.xls` (55.2 MB), `*.rar` (11.6 MB), `tambahan/baru/baru_lagi/**`, `tambahan/laporan_mingguan/**`, file duplikat di `tambahan/baru/` | 160.89 MB | **DUPLICATE / SAMPLE** | File duplikat berkali-kali, arsip `.rar`, laporan mingguan contoh, dan lock file `~$*.xlsx` | **Hapus** |
| `backups/launcher_archive/**` (4 file) | 0.01 MB | **ACTIVE DEVELOPMENT** | Diverifikasi oleh `tests/test_realtime_period_and_launcher_recovery.py` | **Pertahankan** |
| `backups/*` (14 subfolder backup Oktober 2026) | 18.69 MB | **TEMPORARY / DUPLICATE** | Snapshot kode lama Oktober 2026 | **Hapus** |
| `frontend_backup_pre_hedgerow/**` | 1.28 MB | **DUPLICATE / UNUSED** | Backup UI lama sebelum tema Hedgerow & Cobalt | **Hapus** |
| `scratch/inspect_ch/**`, `scratch/inspect_ecmwf/**` | 9.48 MB | **TEMPORARY** | Folder scratch inspeksi sementara (sisakan `scratch/.gitkeep`) | **Hapus** |
| Root accidental & one-off debug files (`%s`, `''2026-08-01''`, `8')`, `powershell.cmd`, `add_refresh_endpoint.py`, `find_login_css2.py`, `find_schema.py`, `harmonize_prob_font.py`, `inspect_table_item.py`, `print_regions_summary.py`, `quick_parquet_check.py`) | 0.01 MB | **TEMPORARY / UNUSED** | File tidak sengaja terbuat dan script debug 1x pakai (`powershell.cmd` juga memicu bug intersepsi batch) | **Hapus** |
| `tests/**`, `test_phase4_decision_engine.py`, `test_phase41_regression.py`, `test_phase42_consistency.py` | 0.50 MB | **ACTIVE DEVELOPMENT** | Seluruh regression & integration test suite | **Pertahankan** |
| `.agents/skills/hallmark/**`, `vendor/hallmark-upstream/**`, `docs/**` | 70.32 MB | **ACTIVE DEVELOPMENT** | Aset Hallmark Design Engine & dokumentasi resmi proyek | **Pertahankan** |

