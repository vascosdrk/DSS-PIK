# PHASE 6.12 — REPOSITORY CLEANUP REPORT
**Sistem:** DSS-PIK BMKG Stasiun Meteorologi Kelas I Raja Haji Fisabilillah Tanjungpinang  
**Tanggal:** 19 November 2026  

---

## 1. Perbandingan Statistik Repository (Sebelum vs Sesudah Cleanup)

| Metrik | Sebelum Cleanup | Sesudah Cleanup | Pengurangan |
|---|---:|---:|---:|
| **Jumlah File (Tanpa `node_modules`)** | `5,828` files | `1,766` files | **-4,062 files (-69.7%)** |
| **Ukuran Repository (Tanpa `node_modules`)** | `698.44 MB` | `260.40 MB` | **-438.04 MB (-62.7%)** |
| **Jumlah File (Termasuk `node_modules`)** | `13,187` files | `9,125` files | **-4,062 files** |
| **Ukuran Repository (Termasuk `node_modules`)** | `780.30 MB` | `342.26 MB` | **-438.04 MB** |

---

## 2. Daftar Kategori File yang Dihapus
1. **File Accidental & One-Off Debug di Root**:
   - `%s` (0 B), `''2026-08-01''` (2.3 KB), `8')` (0 B), `powershell.cmd` (71 B — pemicu bug intersepsi batch Phase 6.11.4).
   - `add_refresh_endpoint.py`, `find_login_css2.py`, `find_schema.py`, `harmonize_prob_font.py`, `inspect_table_item.py`, `print_regions_summary.py`, `quick_parquet_check.py`.
2. **Cache, Virtualenv Internal & Artefak Eksperimen di `SPEI/` (~110.84 MB)**:
   - `SPEI/.mypy_cache/` (46.96 MB), `SPEI/outputs/` (32.96 MB), `SPEI/.git/` (23.11 MB), `SPEI/.venv/` (7.64 MB), `SPEI/scratch/`, `SPEI/.pytest_cache/`, `SPEI/__pycache__/`.
3. **File Excel Duplikat, Arsip RAR & Contoh Laporan di `tambahan/` (~160.89 MB)**:
   - `tambahan/Timeseries_Kepri.xls` (52.30 MB), `tambahan/baru/Timeseries_Kepri.xls` (55.21 MB), `Timeseries_Kepri.rar` (6.09 MB), `02_EKSTRAK_POS.rar` (5.56 MB).
   - `tambahan/baru/baru_lagi/**` (duplikat ketiga CH kabupaten), `tambahan/laporan_mingguan/**` (8.22 MB), dan file lock `~$*.xlsx`.
4. **Artefak Peta Pengujian Lama di `data/operational/maps/` (~125 MB)**:
   - 402 file hasil test render lama dibersihkan (menyisakan 4 file terbaru di `data/operational/maps/` dan 2 file terbaru di `data/output/sih3/`).
5. **Backup Kode Lama & Scratch (~31.27 MB)**:
   - 14 subfolder lama di `backups/` (18.69 MB; `backups/launcher_archive/` tetap dipertahankan), `frontend_backup_pre_hedgerow/` (1.28 MB), `scratch/inspect_*` (9.48 MB), `backend/*.bak_ingestion`, dan 36 file `data/raw/spi/**/*.parquet.bak_*`.
6. **Bytecode & Test Cache**:
   - Seluruh `__pycache__/` dan `.pytest_cache/` di seluruh repository.

---

## 3. Verifikasi Integritas Pasca-Cleanup
- **34/34 File Parquet Kanonikal & Historis**: 100% utuh (`Verifikasi SHA-256 berhasil: 34/34 file Parquet identik dan utuh`).
- **Database MariaDB (`cews_db`)**: 100% utuh (`57` stasiun, `287,189` baris CH harian).
- **Decision Engine Regression Suite**: `test_phase4_decision_engine.py`, `test_phase41_regression.py`, dan `test_phase42_consistency.py` lulus **100% (29/29 PASSED)**.

