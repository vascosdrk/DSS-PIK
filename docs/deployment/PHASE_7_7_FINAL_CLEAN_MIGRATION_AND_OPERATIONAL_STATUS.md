# PHASE 7.7 — FINAL CLEAN MIGRATION & OPERATIONAL STATUS REPORT

**Project**: Decision Support System Peringatan Iklim (DSS-PIK) Kepulauan Riau  
**Institution**: BMKG Stasiun Meteorologi Kelas II Raja Haji Fisabilillah Tanjungpinang  
**Date**: 2026-11-22  
**Status**: **OPERATIONAL (RUNNING)**

---

## 1. Active Project Location

- **Official Active Workspace**: `F:\TNJ\paper\DSS_PIK_MIGRATION_EXPORT\ASLI2`
- **Migration Backups (Preserved Intact)**: `F:\TNJ\paper\DSS_PIK_MIGRATION_EXPORT\DSS_PIK_BACKUPS\backup_20261122_131441`
- **Canonical Parquet Integrity**: **34/34** files verified SHA-256 identical against `parquet_sha256_manifest.json`.
- **Spatial & Reference Assets**: GeoJSON boundaries (`kepri_kabkot.geojson`, `kepri_kecamatan.geojson`, `kepri_zom.geojson`), shapefiles (`KEPRI.shp`, `Kepri__ZOM9120.shp`), and `SPEI/src/spei` verified intact.

---

## 2. Active Database

- **Active Database Name**: `cews_db_migration_test`
- **Configuration**: `.env` updated to `CEWS_DB_NAME=cews_db_migration_test` (timestamped backup saved at `.env.bak_20261122_191600`, excluded by `.gitignore`).
- **Verified Baseline Row Counts**:
  - `stations`: **57**
  - `cews_rainfall_daily`: **287,189**
  - `cews_forecast_snapshot`: **3,244**
  - `cews_regional_warning_decisions`: **42**
  - `cews_regional_decision_audit_log`: **462**
- **Integrity**: `12/12` base tables passed `CHECK TABLE` (`status: OK`); `3/3` foreign keys and view `v_cews_current_warning_map` intact.

---

## 3. Removed Legacy Artifacts

Executed only after full operational verification (HTTP 200 + 36/36 passing tests):

1. **Obsolete Database Dropped**: `cews_db` (`125,698,048` bytes / `119.88 MB` data + index).
2. **Obsolete Old-Laptop Backup Removed**: `backups/pre_migration_existing_cews_db_20261122.sql` (`91.16 MB`).
3. **Cache Directories Cleaned**: `6` safe cache directories (`__pycache__`, `.pytest_cache`) outside `.venv` and `node_modules`.
4. **Obsolete Project Copies Checked**: Scanned `F:\TNJ\paper\`; no `DSS-PIK-DEV` or duplicate DSS-PIK copies existed. Only `DSS_PIK_MIGRATION_EXPORT` and unrelated user folders (`DATA_ANALISIS_PRAKIRAAN`, `INDEKS_UV`, `shp_kepri`) were present and left untouched.

---

## 4. Disk Space Recovered

- **Total Measurable Space Recovered**: **212.02 MB** (`119.88 MB` obsolete `cews_db` + `91.16 MB` obsolete SQL dump + `~0.98 MB` Python/pytest caches).

---

## 5. Python Environment Status

- **Runtime**: Python `3.12.0` (64-bit)
- **Virtual Environment**: `F:\TNJ\paper\DSS_PIK_MIGRATION_EXPORT\ASLI2\.venv` (excluded in `.gitignore`)
- **Dependencies**: Installed cleanly from `requirements-lock.txt`
- **Integrity Check**: `pip check` -> `No broken requirements found.`
- **Imports Verified**: `backend.main`, `backend.database`, `SPEI/src/spei`.

---

## 6. Frontend Status

- **Node.js / npm**: Node `v22.23.2` / npm `10.9.8` (run via `cmd /c npm` due to Windows PowerShell script execution policy)
- **Production Bundle**: `frontend/dist/` verified and served via FastAPI on port `8000`
- **Live Verification**:
  - `GET /` -> `HTTP 200` (`1,370` bytes, `id="root"` present)
  - `GET /assets/index-BRK1kGL_.js` -> `HTTP 200` (`692,775` bytes)

---

## 7. MariaDB Status

- **Version**: `11.4.10-MariaDB` (Win64 AMD64)
- **Executable**: `C:\Users\vasco\mariadb-11.4\bin\mariadbd.exe` (PID `1240`, Port `3306`)
- **Data Directory**: `C:\Users\vasco\mariadb-11.4\data\`
- **Databases Present**: `cews_db_migration_test`, `information_schema`, `mysql`, `performance_schema`, `sys`, `test` (`cews_db` removed).

---

## 8. Backend Status

- **Launcher**: Started via official unified launcher (`DSS-PIK.bat start --no-browser`) using `.venv\Scripts\python.exe`.
- **URL**: `http://127.0.0.1:8000/` (Localhost only; LAN Policy `DISABLED`, Windows Firewall untouched).
- **Spatial API Check**: `GET /api/v1/geo/layers/kabkot` -> `HTTP 200` (`1,013,227` bytes).
- **Auth Guard Check**: `GET /api/v1/periods` -> `HTTP 401` (authentication enforced as expected).

---

## 9. Health Check Results

- **Endpoint**: `http://127.0.0.1:8000/health`
- **HTTP Status**: `200 OK`
- **Response**: `{"status":"ok","service":"cews-api","database":"connected"}`
- **Verified both before and after legacy cleanup.**

---

## 10. Regression Test Results

Executed via `.venv\Scripts\python.exe -m pytest`:

| Test Suite | Result |
|---|---|
| `test_standardized_decision_json.py` | 7/7 PASSED |
| `test_phase4_decision_engine.py` | 9/9 PASSED |
| `test_phase41_regression.py` (incl. 5 live API tests) | 16/16 PASSED |
| `test_phase42_consistency.py` | 4/4 PASSED |
| **Total** | **36 passed in 10.03s (0 failed, 0 skipped)** |

---

## 11. Remaining Warnings

1. **Frontend Timestamp Notice**: `DSS-PIK.bat` logged `[WARN] Frontend build notice: Source 'App.jsx' lebih baru daripada frontend/dist`. If UI changes are made, rebuild using `cmd /c "npm --prefix frontend run build"`.
2. **PowerShell Execution Policy**: `npm` must be invoked via `cmd /c npm` in PowerShell because `npm.ps1` is blocked by default Windows execution policy.
3. **Virtual Environment Activation**: When launching `DSS-PIK.bat` from a fresh terminal, ensure `.venv\Scripts` is activated (or in `PATH`) so the launcher uses the `.venv` Python environment.

---

## 12. Startup Instructions

From Command Prompt in `F:\TNJ\paper\DSS_PIK_MIGRATION_EXPORT\ASLI2`:
```cmd
.venv\Scripts\activate
DSS-PIK.bat start --no-browser
```
*(Or omit `--no-browser` to open `http://127.0.0.1:8000/` automatically in the default browser.)*

---

## 13. Shutdown Instructions

```cmd
.venv\Scripts\activate
DSS-PIK.bat stop
```

---

## 14. Restart Instructions

```cmd
.venv\Scripts\activate
DSS-PIK.bat restart --no-browser
```
