# PHASE 6.13 — DATA INTEGRITY & RESTORATION REPORT
**Tanggal Verifikasi:** 19 November 2026  
**Database Produksi:** `cews_db` (Tidak diubah)  
**Database Rehearsal Terisolasi:** `cews_db_migration_test_20261119`  

---

## 1. Perbandingan Database Produksi vs Database Hasil Restore (`13/13` Objek Identik)

File Dump: `C:\DSS_PIK_MIGRATION_REHEARSAL\database_backup\cews_db_rehearsal.sql`  
Ukuran Dump: `41,499,877` bytes (`39.58 MB`) | SHA-256: `1e63b63b6cfdb842...`

| Nama Tabel / View | Engine | Baris (`cews_db`) | Baris (`cews_db_migration_test_20261119`) | Status |
|---|---|---:|---:|---|
| `stations` | InnoDB | `57` | `57` | **IDENTICAL (PASS)** |
| `cews_rainfall_daily` | InnoDB | `287,189` | `287,189` | **IDENTICAL (PASS)** |
| `cews_forecast_snapshot` | InnoDB | `3,244` | `3,244` | **IDENTICAL (PASS)** |
| `staging_rainfall_import` | InnoDB | `4,275` | `4,275` | **IDENTICAL (PASS)** |
| `cews_period_snapshot` | InnoDB | `570` | `570` | **IDENTICAL (PASS)** |
| `cews_regional_decision_audit_log` | InnoDB | `56` | `56` | **IDENTICAL (PASS)** |
| `cews_regional_warning_decisions` | InnoDB | `42` | `42` | **IDENTICAL (PASS)** |
| `cews_ingestion_history` | InnoDB | `15` | `15` | **IDENTICAL (PASS)** |
| `cews_current_warning` | InnoDB | `0` | `0` | **IDENTICAL (PASS)** |
| `cews_rainfall_correction_log` | InnoDB | `0` | `0` | **IDENTICAL (PASS)** |
| `cews_sih3_publications` | InnoDB | `0` | `0` | **IDENTICAL (PASS)** |
| `cews_warning_history` | InnoDB | `0` | `0` | **IDENTICAL (PASS)** |
| `v_cews_current_warning_map` | VIEW | `0` | `0` | **IDENTICAL (PASS)** |

---

## 2. Verifikasi Integritas 34 File Parquet (Sumber vs Salinan Rehearsal)

Manifest lengkap tersimpan di `C:\DSS_PIK_MIGRATION_REHEARSAL\parquet_manifest\parquet_integrity_manifest.json`. Berikut ringkasan file Parquet utama operasional:

| Relative Path | Ukuran (Bytes) | SHA-256 (16-char prefix) | Status Sumber vs Salinan |
|---|---:|---|---|
| `data/reference/stations/station_metadata.parquet` | `8,014` | `0b180d695c0307db...` | **100% IDENTICAL (PASS)** |
| `data/raw/spi/dasarian/SPI_all_90d.parquet` | `295,279` | `bc2f4af66f5ffae0...` | **100% IDENTICAL (PASS)** |
| `data/raw/spi/dasarian/SPI_all_30d.parquet` | `293,138` | `365fb43b4ae596d6...` | **100% IDENTICAL (PASS)** |
| `data/raw/spi/harian/SPI_all_90d.parquet` | `2,786,050` | `fa92d707bdd8285c...` | **100% IDENTICAL (PASS)** |
| `data/raw/spi/harian/SPI_all_30d.parquet` | `2,763,280` | `7d035ad6415aaeb9...` | **100% IDENTICAL (PASS)** |
| `data/raw/spi/bulanan/SPI_monthly.parquet` | `43,444` | `df290a867ba6660e...` | **100% IDENTICAL (PASS)** |
| `data/raw/rainfall/observation_daily.parquet` | `3,294,082` | `a0ff07f8271b4ac5...` | **100% IDENTICAL (PASS)** |
| `data/processed/hth/hth_daily.parquet` | `1,027,391` | `2495cce77582826b...` | **100% IDENTICAL (PASS)** |
| `data/operational/current/cews_current_warning.parquet` | `12,031` | `e55097613901de42...` | **100% IDENTICAL (PASS)** |
| `data/operational/snapshot/cews_forecast_snapshot.parquet` | `4,731` | `1916f38f5461fb04...` | **100% IDENTICAL (PASS)** |
| *(+ 24 file Parquet historis & arsip lainnya)* | *Terverifikasi* | *Cocok 100%* | **34/34 IDENTICAL (PASS)** |

