# PHASE 7.3 — SAFE REPOSITORY CLEANUP MANIFEST
**Project**: Decision Support System Peringatan Iklim (DSS-PIK)  
**Institusi**: BMKG Stasiun Meteorologi Kelas II Raja Haji Fisabilillah Tanjungpinang  
**Tanggal Eksekusi**: 22 November 2026

---

## 1. RINGKASAN EKSEKUSI SAFE CLEANUP

Pembersihan dilakukan setelah `DSS-PIK.bat` dan pengujian LAN lulus, diawali checkpoint backup ke `backups/phase_7_3_checkpoint/` serta audit referensi dependensi lintas script.

| Kategori | Jumlah | Tujuan / Aksi |
|---|---:|---|
| **ARCHIVE — Legacy Root Launchers** | 6 file | Dipindahkan ke `backups/legacy_launchers_phase7_3/` |
| **ARCHIVE — Stale Frontend `.bak_*` Files** | 17 file | Dipindahkan ke `backups/legacy_frontend_bak_phase7_3/` |
| **REMOVE — Regenerated Caches** | 6 direktori | Dihapus aman (`__pycache__`, `.pytest_cache`) |
| **KEEP — Inti Operasional & Data** | Seluruhnya | 100% utuh (34 Parquet, MariaDB, `.env`, `requirements-lock.txt`, `DSS-PIK.bat`, skrip migrasi, tests, docs) |

---

## 2. MANIFEST DETAIL

### A. ARCHIVED — Legacy Root Launchers (`backups/legacy_launchers_phase7_3/`)
| Path Asal | Alasan | Tindakan |
|---|---|---|
| `run_cews.bat` | Digantikan oleh single unified launcher `DSS-PIK.bat` | `ARCHIVE` |
| `stop_cews.bat` | Digantikan oleh `DSS-PIK.bat stop` / menu interaktif | `ARCHIVE` |
| `run_cews_lan.bat` | Digantikan oleh `DSS-PIK.bat` (referensi di `setup_dss_pik_new_pc.bat` sudah diperbarui) | `ARCHIVE` |
| `stop_cews_lan.bat` | Digantikan oleh `DSS-PIK.bat stop` (referensi di `prepare_dss_pik_migration.bat` sudah diperbarui) | `ARCHIVE` |
| `run_cews_prod.bat` | Binding `127.0.0.1`-only usang, digantikan oleh `DSS-PIK.bat` | `ARCHIVE` |
| `stop_cews_prod.bat` | Digantikan oleh `DSS-PIK.bat stop` | `ARCHIVE` |

### B. ARCHIVED — Stale Frontend Development Backups (`backups/legacy_frontend_bak_phase7_3/`)
17 berkas salinan historis Oktober 2025 yang sebelumnya berada di dalam `frontend/src/`:
- `App.css.bak_perf20261025`, `App.css.bak_popup20261025`, `App.jsx.bak_20261025`, `App.jsx.bak_perf20261025`
- `components/DailyRainfallTable.jsx.bak_perf20261025`, `components/DataCenter.jsx.bak_ingestion`, `components/DataCenter.jsx.bak_perf20261025`
- `components/DataDownloadModal.jsx.bak_perf20261025`, `components/DataDownloadModal.jsx.bak_popup20261025`
- `components/KamusPage.jsx.bak_ingestion`, `components/KamusPage.jsx.bak_perf20261025`
- `components/ProbabilityDataTable.jsx.bak_perf20261025`, `components/SpiDataTable.jsx.bak_ingestion`, `components/SpiDataTable.jsx.bak_perf20261025`
- `components/StationDetailDrawer.jsx.bak_ingestion`, `components/StationInfoModal.jsx.bak_perf20261025`, `components/StationInfoModal.jsx.bak_popup20261025`

### C. REMOVED — Safe Regenerated Caches
- `__pycache__/`, `backend/__pycache__/`, `config/__pycache__/`, `tests/__pycache__/`, `SPEI/src/spei/__pycache__/`, `.pytest_cache/`

### D. KEPT — File Operasional & Migrasi di Root
- `DSS-PIK.bat` (satu-satunya launcher operasional harian)
- `prepare_dss_pik_migration.bat` (diperbarui memanggil `DSS-PIK.bat stop`)
- `setup_dss_pik_new_pc.bat` (diperbarui mengarahkan operator menjalankan `DSS-PIK.bat`)
- `.env`, `.env.example`, `.env.production.example`, `.gitignore` (diperbarui mengabaikan `logs/runtime/*.lock`, `dss_pik_state.json`, `*.bak_*`)
- `requirements.txt`, `requirements-lock.txt`, `pytest.ini`
- Seluruh 34 file Parquet di `data/`, seluruh tabel MariaDB `cews_db`, seluruh test suite (`test_*.py`), dan seluruh dokumen di `docs/`.
