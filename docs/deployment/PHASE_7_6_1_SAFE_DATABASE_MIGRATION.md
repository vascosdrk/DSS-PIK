# PHASE 7.6.1 — SAFE DATABASE MIGRATION & ISOLATED RESTORE REPORT

**Project**: Decision Support System Peringatan Iklim (DSS-PIK) Kepulauan Riau  
**Location**: `F:\TNJ\paper\DSS_PIK_MIGRATION_EXPORT\ASLI2`  
**Date**: 2026-11-22  
**MariaDB Instance**: `11.4.10-MariaDB` (PID `1240`, Port `3306`, `C:\Users\vasco\mariadb-11.4\bin\mariadbd.exe`)

---

## 1. Existing Database Status (`cews_db`)

- **Status**: Preserved untouched (no `DROP`, no overwrite, no schema or data modifications).
- **Character Set / Collation**: `utf8mb4` / `utf8mb4_unicode_ci`.
- **Objects**: 14 base tables + 1 view (`v_cews_current_warning_map`).
- **Observation Date Range (`cews_rainfall_daily`)**: `1981-01-01` to `2027-08-31` (287,144 rows — note future test/placeholder dates in 2027).
- **Last Operational Activity**: ~2026-10-31 to 2026-11-01.

---

## 2. Existing Database Backup Verification

Before any isolated restoration work, a full consistent dump of the existing `cews_db` was created using `mariadb-dump --single-transaction --routines --triggers --events`:

- **File**: `F:\TNJ\paper\DSS_PIK_MIGRATION_EXPORT\ASLI2\backups\pre_migration_existing_cews_db_20261122.sql`
- **Size**: `95,592,342` bytes (91.16 MiB)
- **SHA-256**: `79D52A0CC0599FF23791A333E0E8D55475BAFDAA8AA19EBF399B82B2AE827127`
- **Integrity**: Verified readable header (`MariaDB dump 10.19-11.4.10-MariaDB`) and complete footer (`-- Dump completed on 2026-11-22 19:02:29`).

---

## 3. Restore Mechanism & SQL Dump Safety Audit

### Scripts Inspected
- `scripts/restore_dss_pik.py`: Reads `CEWS_DB_NAME` from `.env` (no `--db-name` CLI flag). Therefore, it was **not** executed against the isolated target.
- `scripts/backup_dss_pik.py`: Dumps `CEWS_DB_NAME` using `mariadb-dump --single-transaction --routines --triggers`.

### Migration SQL Dump Audit (`backup_20261122_131441`)
- **Source**: `F:\TNJ\paper\DSS_PIK_MIGRATION_EXPORT\DSS_PIK_BACKUPS\backup_20261122_131441\cews_db_20261122_131441.sql` (`41,683,336` bytes, untouched/read-only)
- `CREATE DATABASE`: **0**
- `DROP DATABASE`: **0**
- `USE` statements: **0**
- Hardcoded `cews_db` references: **2 SQL comments only** (`-- Host: 127.0.0.1 Database: cews_db` and `-- Dumping routines for database 'cews_db'`). Zero executable references.
- `CREATE TABLE`: **12** | `FOREIGN KEY`: **3** | `VIEW`: **1** (`v_cews_current_warning_map`) | `TRIGGER`: **0** | `PROCEDURE/FUNCTION`: **0** | `INSERT INTO`: **45**

---

## 4. Isolated Database Restoration (`cews_db_migration_test`)

- **Database Created**: `cews_db_migration_test` (`utf8mb4` / `utf8mb4_general_ci`)
- **Restore Command**: Direct `mariadb.exe` stdin import targeting `cews_db_migration_test` only.
- **SQL Import Exit Code**: `0` (zero errors).
- **InnoDB Integrity (`CHECK TABLE`)**: **12/12 base tables returned `status: OK`**.
- **Foreign Keys Verified (3/3)**:
  - `cews_current_warning.fk_curr_warning_station` -> `stations`
  - `cews_forecast_snapshot.fk_fc_snapshot_station` -> `stations`
  - `cews_warning_history.fk_hist_warning_station` -> `stations`
- **View Verified**: `v_cews_current_warning_map` created cleanly, referencing `cews_db_migration_test`.
- **Observation Date Range (`cews_rainfall_daily`)**: `1981-01-01` to `2026-10-31` (287,189 rows).

---

## 5. Row Count Comparison

| Table / View | Existing `cews_db` | Restored `cews_db_migration_test` | Expected (Migration README) | Notes |
|---|---:|---:|---:|---|
| `stations` | 57 | **57** | 57 | Exact match |
| `cews_rainfall_daily` | 287,144 | **287,189** | 287,189 | Exact match (+45 rows vs existing) |
| `cews_forecast_snapshot` | 3,113 | **3,244** | 3,244 | Exact match (+131 rows vs existing) |
| `cews_regional_warning_decisions` | 14 | **42** | 42 | Exact match (+28 rows vs existing) |
| `cews_regional_decision_audit_log` | 14 | **462** | 462 | Exact match (+448 rows vs existing) |
| `cews_period_snapshot` | 570 | **570** | — | Identical count |
| `cews_ingestion_history` | 216 | **15** | — | Cleaned operational log in backup |
| `staging_rainfall_import` | 297,097 | **4,275** | — | Trimmed staging table in backup |
| `cews_current_warning` | 57 | **0** | — | Regenerated dynamically / operational cache |
| `cews_warning_history` | 2,052 | **0** | — | Historical cache in older DB |
| `cews_rainfall_correction_log` | 21 | **0** | — | Older correction log |
| `cews_sih3_publications` | 0 | **0** | — | Identical |
| `v_cews_current_warning_map` (view) | 57 | **0** | — | Reflects `cews_current_warning` |
| `cews_forecast_snapshot_backup_20261031` | 3,660 | *(absent)* | — | Legacy backup table |
| `cews_forecast_snapshot_backup_audit_20261031` | 2,004 | *(absent)* | — | Legacy audit backup table |

---

## 6. Schema Comparison

Across the 13 shared tables/views, **6 tables** have schema differences reflecting Phase 7.4/7.5 schema evolution in `cews_db_migration_test`:

1. **`cews_rainfall_daily`**: `cews_db_migration_test` adds `id` (`bigint(20)`) and `operational_source` (`varchar(100)`), and changes `obs_status` from `ENUM(...)` to `varchar(50)` and `station_id` from `varchar(20)` to `varchar(50)`.
2. **`cews_period_snapshot`**: `cews_db_migration_test` upgrades floating-point columns (`float`/`double`) to `decimal(6,2)` / `decimal(7,2)` / `decimal(9,6)`, `id` to `bigint(20)`, and `last_rain_date` from `varchar(32)` to `date`.
3. **`cews_forecast_snapshot`**: `forecast_resolution` is nullable (`YES`) in `cews_db_migration_test` vs `NO` in `cews_db`.
4. **`cews_rainfall_correction_log`**: `station_id` widened to `varchar(50)` and `corrected_at` changed from `datetime` to `timestamp`.
5. **`staging_rainfall_import`**: `station_id` widened to `varchar(50)`, `import_batch_id` to `varchar(100)`, `created_at` to `timestamp`.
6. **`cews_ingestion_history`**: Column ordering/metadata minor alignment.

---

## 7. Legacy Table Assessment

Codebase search across `backend/`, `scripts/`, and `pipeline/` confirmed **0 references** to:
- `cews_forecast_snapshot_backup_20261031`
- `cews_forecast_snapshot_backup_audit_20261031`

These two tables are one-off October 31, 2026 manual/audit snapshots and are **not required** by the DSS-PIK application. They remain safely preserved in both the untouched `cews_db` and in `pre_migration_existing_cews_db_20261122.sql`.

---

## 8. Application Compatibility (Read-Only Verification)

Tested using `.venv\Scripts\python.exe` (all locked dependencies installed; `pip check` passed with zero broken requirements) with a temporary process-only environment variable `CEWS_DB_NAME=cews_db_migration_test` (`.env` was **not** modified):

- `SPEI/src/spei` import: **PASS**
- `backend.database` connection to `cews_db_migration_test`: **PASS** (`stations=57`, `cews_rainfall_daily=287189`, `cews_regional_warning_decisions=42`)
- `backend.main` import & `health_check()`: **PASS** (`status='ok' service='cews-api' database='connected'`)

---

## 9. Outstanding Issues & Recommendations

### Outstanding Issues
- `cews_db` and `cews_db_migration_test` both currently coexist; `.env` still points to `CEWS_DB_NAME=cews_db`.
- `starlette.testclient.TestClient` requires `httpx2` if used directly, though standard `pytest` regression suites and live `uvicorn` do not require it unless explicitly imported.

### Recommended Production Development Database
- **Recommendation**: Promote **`cews_db_migration_test`** as the primary development database (either by setting `CEWS_DB_NAME=cews_db_migration_test` in `.env`, or by renaming `cews_db` -> `cews_db_legacy_20261031` and promoting `cews_db_migration_test` -> `cews_db` after explicit user approval).
- **Rationale**: `cews_db_migration_test` matches the exact Phase 7.4/7.5 schema (`operational_source`, `DECIMAL` precision, `varchar(50)` statuses), matches 100% of the expected migration row counts, passes InnoDB `CHECK TABLE`, and passes read-only FastAPI backend compatibility checks.

**Awaiting explicit user approval before promoting `cews_db_migration_test` or modifying `.env`.**
