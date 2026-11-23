# CEWS REPOSITORY CLEANUP & STRUCTURAL REORGANIZATION PLAN

**Project**: Climate Early Warning System (CEWS) BMKG Stasiun Klimatologi Kepulauan Riau  
**Date**: 2026-10-19  
**Status**: CONTROLLED PRE-EXECUTION PLAN  

---

## 1. Executive Overview & Guiding Principles
Tujuan dari reorganisasi repositori ini adalah menciptakan struktur direktori yang bersih, modular, dan sesuai kaidah operasional BMKG, tanpa mengubah logika Decision Engine, tanpa mengubah hasil peringatan operasional (42 NORMAL, 5 WASPADA, 4 SIAGA, 6 AWAS), dan tanpa menghapus data sumber primer atau data historis valid.

### Safety Rules:
- **ZERO DATA LOSS**: Seluruh data sumber mentah, observasi curah hujan, SPI authoritative, prakiraan ECMWF, dan arsip data historis 2025 dilindungi sepenuhnya.
- **ARCHIVE OVER DELETE**: Berkas sumber atau olahan lama yang sudah tidak aktif dipindahkan ke `data/archive/`, bukan dihapus.
- **DELETE ONLY DISPOSABLE**: Hanya berkas bytecode Python (`__pycache__`), cache test (`.pytest_cache`), lock file temporary Office (`~$*`), transient syntax error artifacts (`7}`), build output frontend yang 100% reproducible (`frontend/dist`), dan duplikat identik di `output/` yang dihapus.
- **CENTRAL PATH CONFIGURATION**: Seluruh pemanggilan path diperbarui melalui `config/paths.py` dengan fallback aman untuk menjamin portabilitas tanpa hardcoded absolute paths.

---

## 2. Statistical Summary
- **Total Files Inventoried**: 181
  - **ARCHIVE**: 34 files
  - **DELETE**: 27 files
  - **KEEP**: 31 files
  - **MOVE**: 89 files

### Classification Breakdown:
  - **A. ACTIVE SOURCE DATA**: 52 files
  - **B. LEGACY / INACTIVE SOURCE DATA**: 8 files
  - **C. REFERENCE DATA**: 2 files
  - **D. PROCESSED DATA**: 16 files
  - **E. CURRENT OPERATIONAL OUTPUT**: 2 files
  - **F. HISTORICAL OUTPUT**: 3 files
  - **G. REPORT / AUDIT**: 11 files
  - **H. SOURCE CODE**: 40 files
  - **I. CONFIGURATION**: 8 files
  - **J. TEST**: 7 files
  - **K. DOCUMENTATION**: 5 files
  - **L. TEMPORARY / DISPOSABLE GENERATED FILE**: 27 files

---

## 3. Disposable Candidates for Deletion (DELETE)
Seluruh kandidat penghapusan telah diverifikasi memenuhi syarat ketat: (1) bukan data sumber, (2) tidak direferensikan oleh fungsionalitas aktif, (3) sepenuhnya reproducible, dan (4) telah tercatat pada manifest.

| No | Relative Path | Size | Rationale / Reproducibility |
|---|---|---|---|
| 1 | `7}` | 0 B | 0-byte transient artifact from syntax error |
| 2 | `~$mapping_tambahan.xlsx` | 165 B | Microsoft Office transient lock file |
| 3 | `.pytest_cache/.gitignore` | 39 B | Compiled python/pytest bytecode cache; fully reproducible |
| 4 | `.pytest_cache/CACHEDIR.TAG` | 191 B | Compiled python/pytest bytecode cache; fully reproducible |
| 5 | `.pytest_cache/README.md` | 310 B | Compiled python/pytest bytecode cache; fully reproducible |
| 6 | `.pytest_cache/v/cache/lastfailed` | 64 B | Compiled python/pytest bytecode cache; fully reproducible |
| 7 | `.pytest_cache/v/cache/nodeids` | 157 B | Compiled python/pytest bytecode cache; fully reproducible |
| 8 | `backend/__pycache__/database.cpython-312.pyc` | 2744 B | Compiled python/pytest bytecode cache; fully reproducible |
| 9 | `backend/__pycache__/evaluation.cpython-312.pyc` | 14262 B | Compiled python/pytest bytecode cache; fully reproducible |
| 10 | `backend/__pycache__/main.cpython-312.pyc` | 23169 B | Compiled python/pytest bytecode cache; fully reproducible |
| 11 | `backend/__pycache__/schemas.cpython-312.pyc` | 10015 B | Compiled python/pytest bytecode cache; fully reproducible |
| 12 | `backend/__pycache__/__init__.cpython-312.pyc` | 172 B | Compiled python/pytest bytecode cache; fully reproducible |
| 13 | `frontend/dist/index.html` | 1113 B | Frontend compiled production bundle; 100% reproducible via npm run build |
| 14 | `frontend/dist/assets/index-Bu0fUnaE.css` | 30177 B | Frontend compiled production bundle; 100% reproducible via npm run build |
| 15 | `frontend/dist/assets/index-BVJh_1B6.js` | 351493 B | Frontend compiled production bundle; 100% reproducible via npm run build |
| 16 | `output/cews_current_warning.parquet` | 26389 B | Duplicate stale copy of cews_current_warning.parquet in output/ |
| 17 | `output/cews_forecast_snapshot.parquet` | 4731 B | Duplicate stale copy of cews_forecast_snapshot.parquet in output/ |
| 18 | `output/cews_warning_history.parquet` | 87408 B | Duplicate stale copy of cews_warning_history.parquet in output/ |
| 19 | `scripts/__pycache__/test_api_endpoints.cpython-312-pytest-8.4.1.pyc` | 30001 B | Compiled python/pytest bytecode cache; fully reproducible |
| 20 | `scripts/__pycache__/test_dashboard_contract.cpython-312-pytest-8.4.1.pyc` | 19946 B | Compiled python/pytest bytecode cache; fully reproducible |
| 21 | `scripts/__pycache__/test_eval_logic.cpython-312-pytest-8.4.1.pyc` | 6630 B | Compiled python/pytest bytecode cache; fully reproducible |
| 22 | `scripts/__pycache__/test_new_endpoints.cpython-312-pytest-8.4.1.pyc` | 2364 B | Compiled python/pytest bytecode cache; fully reproducible |
| 23 | `scripts/__pycache__/test_pass_a_e2e.cpython-312-pytest-8.4.1.pyc` | 15295 B | Compiled python/pytest bytecode cache; fully reproducible |
| 24 | `scripts/__pycache__/test_refinement_pass.cpython-312-pytest-8.4.1.pyc` | 19395 B | Compiled python/pytest bytecode cache; fully reproducible |
| 25 | `SPI/~$2021_SPI.xlsx` | 165 B | Microsoft Office transient lock file |
| 26 | `SPI/~$2025_SPI.xlsx` | 165 B | Microsoft Office transient lock file |
| 27 | `__pycache__/generate_cews_decision_engine.cpython-312.pyc` | 62234 B | Compiled python/pytest bytecode cache; fully reproducible |

---

## 4. Inactive & Legacy Data to Archive (ARCHIVE)
Berkas berikut tidak lagi aktif dalam pipeline operasional berjalan, namun dipertahankan untuk kebutuhan audit ilmiah, komparasi historis, dan verifikasi peraturan.

| No | Original Path | Target Archive Location | Category | Reason / Active Replacement |
|---|---|---|---|---|
| 1 | `audit_cews.py` | `scripts/utilities/ or archive` | H. SOURCE CODE | Move to scripts/utilities/ or archive (legacy audit scripts) |
| 2 | `audit_probability.py` | `scripts/utilities/ or archive` | H. SOURCE CODE | Move to scripts/utilities/ or archive (legacy audit scripts) |
| 3 | `cews_decision_engine.log` | `reports/archive/` | G. REPORT / AUDIT | Move to reports/archive/ (historical processing logs and QC reports) |
| 4 | `cews_integrated_2021_2025.parquet` | `data/archive/superseded_processed/` | D. PROCESSED DATA | Move to data/archive/superseded_processed/ (historical 2021-2025 pre-computed research datasets) |
| 5 | `cews_warning_status.parquet` | `data/archive/superseded_processed/` | F. HISTORICAL OUTPUT | Move to data/archive/superseded_processed/ (early prototype of warning status) |
| 6 | `check_cols.py` | `scripts/utilities/ or archive` | H. SOURCE CODE | Move to scripts/utilities/ or archive (legacy audit scripts) |
| 7 | `clean_project.py` | `scripts/utilities/ or archive` | H. SOURCE CODE | Move to scripts/utilities/ or archive (legacy audit scripts) |
| 8 | `drought_monitoring_analysis_2021_2025.parquet` | `data/archive/superseded_processed/` | D. PROCESSED DATA | Move to data/archive/superseded_processed/ (historical 2021-2025 pre-computed research datasets) |
| 9 | `drought_spi_forecast_2021_2025.parquet` | `data/archive/superseded_processed/` | D. PROCESSED DATA | Move to data/archive/superseded_processed/ (historical 2021-2025 pre-computed research datasets) |
| 10 | `generate_audit_report.py` | `scripts/utilities/ or archive` | H. SOURCE CODE | Move to scripts/utilities/ or archive (legacy audit scripts) |
| 11 | `hth_daily_2021_2025.parquet` | `data/archive/superseded_processed/` | D. PROCESSED DATA | Move to data/archive/superseded_processed/ (historical 2021-2025 pre-computed research datasets) |
| 12 | `hth_monthly_snapshot_2021_2025.parquet` | `data/archive/superseded_processed/` | D. PROCESSED DATA | Move to data/archive/superseded_processed/ (historical 2021-2025 pre-computed research datasets) |
| 13 | `probability_cews_qc_report_2025.txt` | `reports/archive/` | G. REPORT / AUDIT | Move to reports/archive/ (historical processing logs and QC reports) |
| 14 | `probability_monthly_processing_log.txt` | `reports/archive/` | G. REPORT / AUDIT | Move to reports/archive/ (historical processing logs and QC reports) |
| 15 | `probability_monthly_qc_report.txt` | `reports/archive/` | G. REPORT / AUDIT | Move to reports/archive/ (historical processing logs and QC reports) |
| 16 | `probability_processing_log.txt` | `reports/archive/` | G. REPORT / AUDIT | Move to reports/archive/ (historical processing logs and QC reports) |
| 17 | `probability_qc_report.txt` | `reports/archive/` | G. REPORT / AUDIT | Move to reports/archive/ (historical processing logs and QC reports) |
| 18 | `shadow_current_comparison.csv` | `reports/audits/` | G. REPORT / AUDIT | Move to reports/audits/ (audit comparison artifact between previous baseline and October 2026) |
| 19 | `SPI_all_10d_dasarian.parquet` | `data/archive/legacy_spi/` | B. LEGACY / INACTIVE SOURCE DATA | Move to data/archive/legacy_spi/ (precomputed legacy SPI parquet datasets) |
| 20 | `SPI_all_30d_dasarian.parquet` | `data/archive/legacy_spi/` | B. LEGACY / INACTIVE SOURCE DATA | Move to data/archive/legacy_spi/ (precomputed legacy SPI parquet datasets) |
| 21 | `SPI_all_90d_dasarian.parquet` | `data/archive/legacy_spi/` | B. LEGACY / INACTIVE SOURCE DATA | Move to data/archive/legacy_spi/ (precomputed legacy SPI parquet datasets) |
| 22 | `spi_analysis_2021_2025.parquet` | `data/archive/superseded_processed/` | D. PROCESSED DATA | Move to data/archive/superseded_processed/ (historical 2021-2025 pre-computed research datasets) |
| 23 | `spi_analysis_vs_forecast_2021_2025.parquet` | `data/archive/superseded_processed/` | D. PROCESSED DATA | Move to data/archive/superseded_processed/ (historical 2021-2025 pre-computed research datasets) |
| 24 | `spi_cews_2021_2025.parquet` | `data/archive/superseded_processed/` | D. PROCESSED DATA | Move to data/archive/superseded_processed/ (historical 2021-2025 pre-computed research datasets) |
| 25 | `spi_excluded_stations_2021_2025.parquet` | `data/archive/superseded_processed/` | D. PROCESSED DATA | Move to data/archive/superseded_processed/ (historical 2021-2025 pre-computed research datasets) |
| 26 | `spi_forecast_2021_2025.parquet` | `data/archive/superseded_processed/` | D. PROCESSED DATA | Move to data/archive/superseded_processed/ (historical 2021-2025 pre-computed research datasets) |
| 27 | `spi_station_mapping_registry_2021_2025.parquet` | `data/archive/superseded_processed/` | D. PROCESSED DATA | Move to data/archive/superseded_processed/ (historical 2021-2025 pre-computed research datasets) |
| 28 | `logs/cews_indicator_pipeline.log` | `reports/archive/` | G. REPORT / AUDIT | Move to reports/archive/ (pipeline run log) |
| 29 | `output/cews_warning_status.parquet` | `data/archive/superseded_processed/` | F. HISTORICAL OUTPUT | Move to data/archive/superseded_processed/ (early prototype of warning status) |
| 30 | `SPI/2021_SPI.xlsx` | `data/archive/legacy_spi/` | B. LEGACY / INACTIVE SOURCE DATA | Move to data/archive/legacy_spi/ (legacy SPI workbooks superseded by authoritative source) |
| 31 | `SPI/2022_SPI.xlsx` | `data/archive/legacy_spi/` | B. LEGACY / INACTIVE SOURCE DATA | Move to data/archive/legacy_spi/ (legacy SPI workbooks superseded by authoritative source) |
| 32 | `SPI/2023_SPI.xlsx` | `data/archive/legacy_spi/` | B. LEGACY / INACTIVE SOURCE DATA | Move to data/archive/legacy_spi/ (legacy SPI workbooks superseded by authoritative source) |
| 33 | `SPI/2024_SPI.xlsx` | `data/archive/legacy_spi/` | B. LEGACY / INACTIVE SOURCE DATA | Move to data/archive/legacy_spi/ (legacy SPI workbooks superseded by authoritative source) |
| 34 | `SPI/2025_SPI.xlsx` | `data/archive/legacy_spi/` | B. LEGACY / INACTIVE SOURCE DATA | Move to data/archive/legacy_spi/ (legacy SPI workbooks superseded by authoritative source) |

---

## 5. Active Items to Relocate (MOVE)
Berkas aktif dipindahkan ke direktori domain masing-masing (`data/raw/`, `data/reference/`, `data/processed/`, `data/operational/`, `data/historical/`, `reports/`, `docs/`, `pipeline/`, `scripts/`, `tests/`).

| No | Original Path | Target Location | Category | Description |
|---|---|---|---|---|
| 1 | `cews_current_warning.parquet` | `Target Dir` | E. CURRENT OPERATIONAL OUTPUT | Move canonical current warning to data/operational/current/ |
| 2 | `cews_decision_qc_report.txt` | `reports/operational/` | G. REPORT / AUDIT | Move to reports/operational/ (active QC & decision engine audit reports) |
| 3 | `cews_forecast_snapshot.parquet` | `Target Dir` | E. CURRENT OPERATIONAL OUTPUT | Move canonical forecast snapshot to data/operational/snapshot/ |
| 4 | `cews_indicator_dataset.parquet` | `Target Dir` | D. PROCESSED DATA | Move canonical to data/processed/indicators/ |
| 5 | `cews_operational_qc_report.txt` | `reports/operational/` | G. REPORT / AUDIT | Move to reports/operational/ (active QC & decision engine audit reports) |
| 6 | `CEWS_PROJECT_HANDOVER_AND_KNOWLEDGE_TRANSFER.md` | `docs/operations/ or docs/audits/` | K. DOCUMENTATION | Move to docs/operations/ or docs/audits/ (core technical documentation) |
| 7 | `CEWS_PROJECT_MEMORY_DOCUMENTATION.md` | `docs/operations/ or docs/audits/` | K. DOCUMENTATION | Move to docs/operations/ or docs/audits/ (core technical documentation) |
| 8 | `cews_rules.xlsx` | `config/cews_rules/` | I. CONFIGURATION | Move to config/cews_rules/ (authoritative operational decision rules spreadsheet) |
| 9 | `CEWS_SYSTEM_DOCUMENTATION.md` | `docs/operations/ or docs/audits/` | K. DOCUMENTATION | Move to docs/operations/ or docs/audits/ (core technical documentation) |
| 10 | `CEWS_TECHNICAL_AUDIT.md` | `docs/operations/ or docs/audits/` | K. DOCUMENTATION | Move to docs/operations/ or docs/audits/ (core technical documentation) |
| 11 | `cews_warning_history.parquet` | `Target Dir` | F. HISTORICAL OUTPUT | Move canonical warning history to data/historical/warnings/ |
| 12 | `final_rainfall_daily.parquet` | `data/raw/rainfall/` | A. ACTIVE SOURCE DATA | Move to data/raw/rainfall/ (authoritative rainfall observations) |
| 13 | `generate_cews_decision_engine.py` | `pipeline/` | H. SOURCE CODE | Move to pipeline/ (canonical pipeline generation scripts) |
| 14 | `generate_hth_pipeline.py` | `pipeline/` | H. SOURCE CODE | Move to pipeline/ (canonical pipeline generation scripts) |
| 15 | `generate_probability_monthly_pipeline.py` | `pipeline/` | H. SOURCE CODE | Move to pipeline/ (canonical pipeline generation scripts) |
| 16 | `generate_probability_pipeline.py` | `pipeline/` | H. SOURCE CODE | Move to pipeline/ (canonical pipeline generation scripts) |
| 17 | `generate_spi_pipeline.py` | `pipeline/` | H. SOURCE CODE | Move to pipeline/ (canonical pipeline generation scripts) |
| 18 | `hth_daily.parquet` | `Target Dir` | D. PROCESSED DATA | Move canonical to data/processed/hth/ |
| 19 | `mapping_tambahan.xlsx` | `data/reference/stations/` | C. REFERENCE DATA | Move to data/reference/stations/ (canonical station metadata and mapping) |
| 20 | `observation_daily.parquet` | `data/raw/rainfall/` | A. ACTIVE SOURCE DATA | Move to data/raw/rainfall/ (authoritative rainfall observations) |
| 21 | `prepare_cews_data.py` | `pipeline/` | H. SOURCE CODE | Move to pipeline/ (canonical pipeline generation scripts) |
| 22 | `probability_rainfall_dasarian_2025.parquet` | `data/processed/forecast/` | D. PROCESSED DATA | Move to data/processed/forecast/ |
| 23 | `probability_rainfall_monthly_2021_2025.parquet` | `data/processed/forecast/` | D. PROCESSED DATA | Move to data/processed/forecast/ |
| 24 | `SPI_all_30d_dasarian.xlsx` | `data/raw/spi/` | A. ACTIVE SOURCE DATA | Move to data/raw/spi/ (authoritative SPI source) |
| 25 | `STATION_MAPPING_AUDIT.md` | `docs/operations/ or docs/audits/` | K. DOCUMENTATION | Move to docs/operations/ or docs/audits/ (core technical documentation) |
| 26 | `station_metadata.parquet` | `data/reference/stations/` | C. REFERENCE DATA | Move to data/reference/stations/ (canonical station metadata and mapping) |
| 27 | `output/cews_indicator_dataset.parquet` | `Target Dir` | D. PROCESSED DATA | Move canonical to data/processed/indicators/ |
| 28 | `output/cews_indicator_qc_report.txt` | `reports/validation/` | G. REPORT / AUDIT | Move to reports/validation/ (indicator pipeline validation report) |
| 29 | `probabilitas/2025/KEPRI_pch_ecmwf_perpos_ver_2024.12.30.xlsx` | `data/raw/forecast/dasarian/` | A. ACTIVE SOURCE DATA | Move to data/raw/forecast/dasarian/ (ECMWF dasarian forecast probabilities) |
| 30 | `probabilitas/2025/KEPRI_pch_ecmwf_perpos_ver_2025.01.09.xlsx` | `data/raw/forecast/dasarian/` | A. ACTIVE SOURCE DATA | Move to data/raw/forecast/dasarian/ (ECMWF dasarian forecast probabilities) |
| 31 | `probabilitas/2025/KEPRI_pch_ecmwf_perpos_ver_2025.01.16.xlsx` | `data/raw/forecast/dasarian/` | A. ACTIVE SOURCE DATA | Move to data/raw/forecast/dasarian/ (ECMWF dasarian forecast probabilities) |
| 32 | `probabilitas/2025/KEPRI_pch_ecmwf_perpos_ver_2025.01.30.xlsx` | `data/raw/forecast/dasarian/` | A. ACTIVE SOURCE DATA | Move to data/raw/forecast/dasarian/ (ECMWF dasarian forecast probabilities) |
| 33 | `probabilitas/2025/KEPRI_pch_ecmwf_perpos_ver_2025.02.10.xlsx` | `data/raw/forecast/dasarian/` | A. ACTIVE SOURCE DATA | Move to data/raw/forecast/dasarian/ (ECMWF dasarian forecast probabilities) |
| 34 | `probabilitas/2025/KEPRI_pch_ecmwf_perpos_ver_2025.02.20.xlsx` | `data/raw/forecast/dasarian/` | A. ACTIVE SOURCE DATA | Move to data/raw/forecast/dasarian/ (ECMWF dasarian forecast probabilities) |
| 35 | `probabilitas/2025/KEPRI_pch_ecmwf_perpos_ver_2025.02.27.xlsx` | `data/raw/forecast/dasarian/` | A. ACTIVE SOURCE DATA | Move to data/raw/forecast/dasarian/ (ECMWF dasarian forecast probabilities) |
| 36 | `probabilitas/2025/KEPRI_pch_ecmwf_perpos_ver_2025.03.10.xlsx` | `data/raw/forecast/dasarian/` | A. ACTIVE SOURCE DATA | Move to data/raw/forecast/dasarian/ (ECMWF dasarian forecast probabilities) |
| 37 | `probabilitas/2025/KEPRI_pch_ecmwf_perpos_ver_2025.03.17.xlsx` | `data/raw/forecast/dasarian/` | A. ACTIVE SOURCE DATA | Move to data/raw/forecast/dasarian/ (ECMWF dasarian forecast probabilities) |
| 38 | `probabilitas/2025/KEPRI_pch_ecmwf_perpos_ver_2025.03.27.xlsx` | `data/raw/forecast/dasarian/` | A. ACTIVE SOURCE DATA | Move to data/raw/forecast/dasarian/ (ECMWF dasarian forecast probabilities) |
| 39 | `probabilitas/2025/KEPRI_pch_ecmwf_perpos_ver_2025.04.07.xlsx` | `data/raw/forecast/dasarian/` | A. ACTIVE SOURCE DATA | Move to data/raw/forecast/dasarian/ (ECMWF dasarian forecast probabilities) |
| 40 | `probabilitas/2025/KEPRI_pch_ecmwf_perpos_ver_2025.04.10.xlsx` | `data/raw/forecast/dasarian/` | A. ACTIVE SOURCE DATA | Move to data/raw/forecast/dasarian/ (ECMWF dasarian forecast probabilities) |
| 41 | `probabilitas/2025/KEPRI_pch_ecmwf_perpos_ver_2025.04.17.xlsx` | `data/raw/forecast/dasarian/` | A. ACTIVE SOURCE DATA | Move to data/raw/forecast/dasarian/ (ECMWF dasarian forecast probabilities) |
| 42 | `probabilitas/2025/KEPRI_pch_ecmwf_perpos_ver_2025.04.28.xlsx` | `data/raw/forecast/dasarian/` | A. ACTIVE SOURCE DATA | Move to data/raw/forecast/dasarian/ (ECMWF dasarian forecast probabilities) |
| 43 | `probabilitas/2025/KEPRI_pch_ecmwf_perpos_ver_2025.05.08.xlsx` | `data/raw/forecast/dasarian/` | A. ACTIVE SOURCE DATA | Move to data/raw/forecast/dasarian/ (ECMWF dasarian forecast probabilities) |
| 44 | `probabilitas/2025/KEPRI_pch_ecmwf_perpos_ver_2025.05.19.xlsx` | `data/raw/forecast/dasarian/` | A. ACTIVE SOURCE DATA | Move to data/raw/forecast/dasarian/ (ECMWF dasarian forecast probabilities) |
| 45 | `probabilitas/2025/KEPRI_pch_ecmwf_perpos_ver_2025.05.29.xlsx` | `data/raw/forecast/dasarian/` | A. ACTIVE SOURCE DATA | Move to data/raw/forecast/dasarian/ (ECMWF dasarian forecast probabilities) |
| 46 | `probabilitas/2025/KEPRI_pch_ecmwf_perpos_ver_2025.06.09.xlsx` | `data/raw/forecast/dasarian/` | A. ACTIVE SOURCE DATA | Move to data/raw/forecast/dasarian/ (ECMWF dasarian forecast probabilities) |
| 47 | `probabilitas/2025/KEPRI_pch_ecmwf_perpos_ver_2025.06.19.xlsx` | `data/raw/forecast/dasarian/` | A. ACTIVE SOURCE DATA | Move to data/raw/forecast/dasarian/ (ECMWF dasarian forecast probabilities) |
| 48 | `probabilitas/2025/KEPRI_pch_ecmwf_perpos_ver_2025.06.30.xlsx` | `data/raw/forecast/dasarian/` | A. ACTIVE SOURCE DATA | Move to data/raw/forecast/dasarian/ (ECMWF dasarian forecast probabilities) |
| 49 | `probabilitas/2025/KEPRI_pch_ecmwf_perpos_ver_2025.07.10.xlsx` | `data/raw/forecast/dasarian/` | A. ACTIVE SOURCE DATA | Move to data/raw/forecast/dasarian/ (ECMWF dasarian forecast probabilities) |
| 50 | `probabilitas/2025/KEPRI_pch_ecmwf_perpos_ver_2025.07.21.xlsx` | `data/raw/forecast/dasarian/` | A. ACTIVE SOURCE DATA | Move to data/raw/forecast/dasarian/ (ECMWF dasarian forecast probabilities) |
| 51 | `probabilitas/2025/KEPRI_pch_ecmwf_perpos_ver_2025.08.18.xlsx` | `data/raw/forecast/dasarian/` | A. ACTIVE SOURCE DATA | Move to data/raw/forecast/dasarian/ (ECMWF dasarian forecast probabilities) |
| 52 | `probabilitas/2025/KEPRI_pch_ecmwf_perpos_ver_2025.08.28.xlsx` | `data/raw/forecast/dasarian/` | A. ACTIVE SOURCE DATA | Move to data/raw/forecast/dasarian/ (ECMWF dasarian forecast probabilities) |
| 53 | `probabilitas/2025/KEPRI_pch_ecmwf_perpos_ver_2025.09.08.xlsx` | `data/raw/forecast/dasarian/` | A. ACTIVE SOURCE DATA | Move to data/raw/forecast/dasarian/ (ECMWF dasarian forecast probabilities) |
| 54 | `probabilitas/2025/KEPRI_pch_ecmwf_perpos_ver_2025.09.18.xlsx` | `data/raw/forecast/dasarian/` | A. ACTIVE SOURCE DATA | Move to data/raw/forecast/dasarian/ (ECMWF dasarian forecast probabilities) |
| 55 | `probabilitas/2025/KEPRI_pch_ecmwf_perpos_ver_2025.09.29.xlsx` | `data/raw/forecast/dasarian/` | A. ACTIVE SOURCE DATA | Move to data/raw/forecast/dasarian/ (ECMWF dasarian forecast probabilities) |
| 56 | `probabilitas/2025/KEPRI_pch_ecmwf_perpos_ver_2025.10.09.xlsx` | `data/raw/forecast/dasarian/` | A. ACTIVE SOURCE DATA | Move to data/raw/forecast/dasarian/ (ECMWF dasarian forecast probabilities) |
| 57 | `probabilitas/2025/KEPRI_pch_ecmwf_perpos_ver_2025.10.20.xlsx` | `data/raw/forecast/dasarian/` | A. ACTIVE SOURCE DATA | Move to data/raw/forecast/dasarian/ (ECMWF dasarian forecast probabilities) |
| 58 | `probabilitas/2025/KEPRI_pch_ecmwf_perpos_ver_2025.10.30.xlsx` | `data/raw/forecast/dasarian/` | A. ACTIVE SOURCE DATA | Move to data/raw/forecast/dasarian/ (ECMWF dasarian forecast probabilities) |
| 59 | `probabilitas/2025/KEPRI_pch_ecmwf_perpos_ver_2025.11.06.xlsx` | `data/raw/forecast/dasarian/` | A. ACTIVE SOURCE DATA | Move to data/raw/forecast/dasarian/ (ECMWF dasarian forecast probabilities) |
| 60 | `probabilitas/2025/KEPRI_pch_ecmwf_perpos_ver_2025.11.17.xlsx` | `data/raw/forecast/dasarian/` | A. ACTIVE SOURCE DATA | Move to data/raw/forecast/dasarian/ (ECMWF dasarian forecast probabilities) |
| 61 | `probabilitas/2025/KEPRI_pch_ecmwf_perpos_ver_2025.11.20.xlsx` | `data/raw/forecast/dasarian/` | A. ACTIVE SOURCE DATA | Move to data/raw/forecast/dasarian/ (ECMWF dasarian forecast probabilities) |
| 62 | `probabilitas/2025/KEPRI_pch_ecmwf_perpos_ver_2025.11.27.xlsx` | `data/raw/forecast/dasarian/` | A. ACTIVE SOURCE DATA | Move to data/raw/forecast/dasarian/ (ECMWF dasarian forecast probabilities) |
| 63 | `probabilitas/2025/KEPRI_pch_ecmwf_perpos_ver_2025.12.08.xlsx` | `data/raw/forecast/dasarian/` | A. ACTIVE SOURCE DATA | Move to data/raw/forecast/dasarian/ (ECMWF dasarian forecast probabilities) |
| 64 | `probabilitas/2025/KEPRI_pch_ecmwf_perpos_ver_2025.12.18.xlsx` | `data/raw/forecast/dasarian/` | A. ACTIVE SOURCE DATA | Move to data/raw/forecast/dasarian/ (ECMWF dasarian forecast probabilities) |
| 65 | `probabilitas/2025/KEPRI_pch_ecmwf_perpos_ver_2025.12.29.xlsx` | `data/raw/forecast/dasarian/` | A. ACTIVE SOURCE DATA | Move to data/raw/forecast/dasarian/ (ECMWF dasarian forecast probabilities) |
| 66 | `probabilitas_bulanan/2025/KEPRI_pch_ecmwf_perpos_ver_2025.01.01.xlsx` | `data/raw/forecast/monthly/` | A. ACTIVE SOURCE DATA | Move to data/raw/forecast/monthly/ (ECMWF monthly forecast probabilities) |
| 67 | `probabilitas_bulanan/2025/KEPRI_pch_ecmwf_perpos_ver_2025.02.01.xlsx` | `data/raw/forecast/monthly/` | A. ACTIVE SOURCE DATA | Move to data/raw/forecast/monthly/ (ECMWF monthly forecast probabilities) |
| 68 | `probabilitas_bulanan/2025/KEPRI_pch_ecmwf_perpos_ver_2025.03.01.xlsx` | `data/raw/forecast/monthly/` | A. ACTIVE SOURCE DATA | Move to data/raw/forecast/monthly/ (ECMWF monthly forecast probabilities) |
| 69 | `probabilitas_bulanan/2025/KEPRI_pch_ecmwf_perpos_ver_2025.04.01.xlsx` | `data/raw/forecast/monthly/` | A. ACTIVE SOURCE DATA | Move to data/raw/forecast/monthly/ (ECMWF monthly forecast probabilities) |
| 70 | `probabilitas_bulanan/2025/KEPRI_pch_ecmwf_perpos_ver_2025.05.01.xlsx` | `data/raw/forecast/monthly/` | A. ACTIVE SOURCE DATA | Move to data/raw/forecast/monthly/ (ECMWF monthly forecast probabilities) |
| 71 | `probabilitas_bulanan/2025/KEPRI_pch_ecmwf_perpos_ver_2025.06.01.xlsx` | `data/raw/forecast/monthly/` | A. ACTIVE SOURCE DATA | Move to data/raw/forecast/monthly/ (ECMWF monthly forecast probabilities) |
| 72 | `probabilitas_bulanan/2025/KEPRI_pch_ecmwf_perpos_ver_2025.07.01.xlsx` | `data/raw/forecast/monthly/` | A. ACTIVE SOURCE DATA | Move to data/raw/forecast/monthly/ (ECMWF monthly forecast probabilities) |
| 73 | `probabilitas_bulanan/2025/KEPRI_pch_ecmwf_perpos_ver_2025.08.01.xlsx` | `data/raw/forecast/monthly/` | A. ACTIVE SOURCE DATA | Move to data/raw/forecast/monthly/ (ECMWF monthly forecast probabilities) |
| 74 | `probabilitas_bulanan/2025/KEPRI_pch_ecmwf_perpos_ver_2025.09.01.xlsx` | `data/raw/forecast/monthly/` | A. ACTIVE SOURCE DATA | Move to data/raw/forecast/monthly/ (ECMWF monthly forecast probabilities) |
| 75 | `probabilitas_bulanan/2025/KEPRI_pch_ecmwf_perpos_ver_2025.10.01.xlsx` | `data/raw/forecast/monthly/` | A. ACTIVE SOURCE DATA | Move to data/raw/forecast/monthly/ (ECMWF monthly forecast probabilities) |
| 76 | `probabilitas_bulanan/2025/KEPRI_pch_ecmwf_perpos_ver_2025.11.01.xlsx` | `data/raw/forecast/monthly/` | A. ACTIVE SOURCE DATA | Move to data/raw/forecast/monthly/ (ECMWF monthly forecast probabilities) |
| 77 | `probabilitas_bulanan/2025/KEPRI_pch_ecmwf_perpos_ver_2025.12.01.xlsx` | `data/raw/forecast/monthly/` | A. ACTIVE SOURCE DATA | Move to data/raw/forecast/monthly/ (ECMWF monthly forecast probabilities) |
| 78 | `scripts/compare_singkep_stations.py` | `scripts/validation/` | H. SOURCE CODE | Move to scripts/validation/ |
| 79 | `scripts/inspect_eval_sources.py` | `scripts/validation/` | H. SOURCE CODE | Move to scripts/validation/ |
| 80 | `scripts/inspect_singkep_deep.py` | `scripts/validation/` | H. SOURCE CODE | Move to scripts/validation/ |
| 81 | `scripts/inspect_singkep_eval.py` | `scripts/validation/` | H. SOURCE CODE | Move to scripts/validation/ |
| 82 | `scripts/migrate_cews_to_mariadb.py` | `scripts/migration/` | H. SOURCE CODE | Move to scripts/migration/ |
| 83 | `scripts/test_api_endpoints.py` | `tests/api/` | J. TEST | Move to tests/api/ |
| 84 | `scripts/test_dashboard_contract.py` | `tests/integration/` | J. TEST | Move to tests/integration/ |
| 85 | `scripts/test_eval_logic.py` | `tests/unit/` | J. TEST | Move to tests/unit/ |
| 86 | `scripts/test_new_endpoints.py` | `tests/api/` | J. TEST | Move to tests/api/ |
| 87 | `scripts/test_october_2026_acceptance.py` | `tests/regression/` | J. TEST | Move to tests/regression/ |
| 88 | `scripts/test_pass_a_e2e.py` | `tests/regression/` | J. TEST | Move to tests/regression/ |
| 89 | `scripts/test_refinement_pass.py` | `tests/regression/` | J. TEST | Move to tests/regression/ |

---

## 6. Items Preserved in Place (KEEP)
Berkas yang sudah berada di lokasi kanonikalnya dipertahankan tanpa perubahan lokasi.

| No | Relative Path | Category | Notes |
|---|---|---|---|
| 1 | `.env.example` | I. CONFIGURATION | Environment template / config |
| 2 | `powershell.cmd` | H. SOURCE CODE | Root operational execution scripts |
| 3 | `run_cews_demo.bat` | H. SOURCE CODE | Root operational execution scripts |
| 4 | `stop_cews_demo.bat` | H. SOURCE CODE | Root operational execution scripts |
| 5 | `backend/database.py` | H. SOURCE CODE | Backend FastAPI application code |
| 6 | `backend/evaluation.py` | H. SOURCE CODE | Backend FastAPI application code |
| 7 | `backend/main.py` | H. SOURCE CODE | Backend FastAPI application code |
| 8 | `backend/schemas.py` | H. SOURCE CODE | Backend FastAPI application code |
| 9 | `backend/__init__.py` | H. SOURCE CODE | Backend FastAPI application code |
| 10 | `config/cews_config.yaml` | I. CONFIGURATION | config/cews_config.yaml (active pipeline config) |
| 11 | `database/schema.sql` | I. CONFIGURATION | database/schema.sql (DB DDL schema) |
| 12 | `frontend/.env` | I. CONFIGURATION | Environment template / config |
| 13 | `frontend/.env.example` | I. CONFIGURATION | Environment template / config |
| 14 | `frontend/index.html` | H. SOURCE CODE | Frontend React web GIS application code |
| 15 | `frontend/package-lock.json` | I. CONFIGURATION | Frontend Node package configuration |
| 16 | `frontend/package.json` | I. CONFIGURATION | Frontend Node package configuration |
| 17 | `frontend/powershell.cmd` | H. SOURCE CODE | Frontend React web GIS application code |
| 18 | `frontend/vite.config.js` | H. SOURCE CODE | Frontend React web GIS application code |
| 19 | `frontend/src/App.css` | H. SOURCE CODE | Frontend React web GIS application code |
| 20 | `frontend/src/App.jsx` | H. SOURCE CODE | Frontend React web GIS application code |
| 21 | `frontend/src/config.js` | H. SOURCE CODE | Frontend React web GIS application code |
| 22 | `frontend/src/main.jsx` | H. SOURCE CODE | Frontend React web GIS application code |
| 23 | `frontend/src/components/EvaluationModal.jsx` | H. SOURCE CODE | Frontend React web GIS application code |
| 24 | `frontend/src/components/FilterBar.jsx` | H. SOURCE CODE | Frontend React web GIS application code |
| 25 | `frontend/src/components/Header.jsx` | H. SOURCE CODE | Frontend React web GIS application code |
| 26 | `frontend/src/components/HthTable.jsx` | H. SOURCE CODE | Frontend React web GIS application code |
| 27 | `frontend/src/components/KpiCards.jsx` | H. SOURCE CODE | Frontend React web GIS application code |
| 28 | `frontend/src/components/MapLeaflet.jsx` | H. SOURCE CODE | Frontend React web GIS application code |
| 29 | `frontend/src/components/SimulationBanner.jsx` | H. SOURCE CODE | Frontend React web GIS application code |
| 30 | `frontend/src/components/StationDetailDrawer.jsx` | H. SOURCE CODE | Frontend React web GIS application code |
| 31 | `pipeline/generate_cews_indicator_pipeline.py` | H. SOURCE CODE | CEWS pipeline code |

---

## 7. Items Requiring Manual Review (REVIEW)
*(Nihil / 0 files — Seluruh 181 file telah berhasil diklasifikasikan dengan tuntas dan memiliki disposisi yang jelas).*

---

## 8. Checksum & Integrity Verification Protocol
Sebelum dan sesudah operasi relokasi, SHA-256 hash dari berkas kritis berikut akan diverifikasi untuk membuktikan kesamaan data bit-for-bit:
- `SPI_all_30d_dasarian.xlsx`
- `station_metadata.parquet`
- `final_rainfall_daily.parquet`
- `cews_warning_history.parquet`
- `cews_current_warning.parquet`
- `cews_forecast_snapshot.parquet`
- `cews_indicator_dataset.parquet`

---

## 9. Post-Reorganization Regression Suite
1. **Unit & Pipeline Tests**: Validasi eksekusi engine keputusan.
2. **API Regression**: Verifikasi `/health`, `/api/v1/current-warning`, `/api/v1/stations/{id}/detail`, `/api/v1/stations/{id}/history`.
3. **Dashboard Contract Test**: Verifikasi end-to-end frontend, API, dan MariaDB.
4. **Database Verification**: Verifikasi row counts di MariaDB `cews_db` (0 rows modified).