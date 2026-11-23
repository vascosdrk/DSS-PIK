# PHASE 8.2 — DOCKERIZED OPERATIONAL TEST REPORT

**Project**: Decision Support System Peringatan Iklim (DSS-PIK) Kepulauan Riau  
**Host**: Windows 10 Pro + Ubuntu 24.04.5 LTS (WSL2)  
**Docker Engine**: `29.10.0` | **Docker Compose**: `v5.8.0`  
**Date**: 2026-11-22  
**Status**: **OPERATIONAL & VERIFIED (36/36 REGRESSION TESTS PASSED)**

---

## 1. Docker Stack Summary

- **Compose Project Name**: `dss-pik-dev`
- **Application Image Tag**: `dss-pik:0.8.2-dev` (multi-stage `node:22-alpine` -> `python:3.12-slim`, non-root user `dsspik`)
- **Database Image**: `mariadb:11.4` (`11.4.13-MariaDB-ubu2404`)
- **Container Names**:
  - `dss_pik_dev_app` (`127.0.0.1:18000->8000/tcp`, status: **`healthy`**)
  - `dss_pik_dev_mariadb` (`3306/tcp` internal-only, status: **`healthy`**)
- **Internal Network**: `dss_pik_dev_internal` (bridge)
- **Persistent Named Volumes**:
  - `dss_pik_dev_mariadb_data` (`/var/lib/mysql`)
  - `dss_pik_dev_maps_output` (`/app/data/operational/maps`)
  - `dss_pik_dev_sih3_output` (`/app/data/output`)
  - `dss_pik_dev_runtime_logs` (`/app/logs/runtime`)
  - `dss_pik_dev_outputs` (`/app/outputs`)
- **Read-Only Data Mount**: `./data:/app/data:ro` (all 34 canonical Parquet files + GeoJSON + Shapefiles protected read-only).

---

## 2. Database Verification (`cews_db_migration_test` in `dss_pik_dev_mariadb`)

Seeded cleanly on first boot from `backup_20261122_131441/cews_db_20261122_131441.sql` into fresh isolated volume `dss_pik_dev_mariadb_data`:

| Table | Expected | Verified in Docker | Status |
|---|---:|---:|---|
| `stations` | 57 | **57** | PASS |
| `cews_rainfall_daily` | 287,189 | **287,189** | PASS |
| `cews_forecast_snapshot` | 3,244 | **3,244** | PASS |
| `cews_regional_warning_decisions` | 42 | **42** | PASS |
| `cews_regional_decision_audit_log` | 462 | **462** | PASS |

---

## 3. Regression Test Results (Inside `dss_pik_dev_app`)

Executed inside `dss_pik_dev_app` (`Python 3.12.16`, `pytest 9.2.0`) against `dss_pik_dev_mariadb` and the live container backend:

- **SPEI Import**: `PASS` (`/app/SPEI/src/spei/__init__.py`)
- **`test_standardized_decision_json.py`**: `7/7 PASSED`
- **`test_phase4_decision_engine.py`**: `9/9 PASSED`
- **`test_phase41_regression.py`** (including all 5 `TestLiveApiConsistency` tests): `16/16 PASSED`
- **`test_phase42_consistency.py`**: `4/4 PASSED`
- **Total**: **36 passed in 36.60s (0 failed, 0 skipped)**

---

## 4. Restart Persistence Verification (Stage J)

Executed `docker compose -p dss-pik-dev --env-file .env.docker restart` (without `-v`):
- Both `dss_pik_dev_mariadb` and `dss_pik_dev_app` returned to **`healthy`** within 19 seconds.
- Post-restart database counts verified intact: `stations = 57`, `cews_rainfall_daily = 287,189`.
- Native Windows DSS-PIK on `http://127.0.0.1:8000/health` remained **HTTP 200** (`{"status":"ok","service":"cews-api","database":"connected"}`) throughout.

---

## 5. Remaining Issues & Findings

1. **Docker Bridge Gateway IP vs. `lan_access_policy.json` (HTTP 403 on Host `:18000`)**:
   - Inside the container, `http://127.0.0.1:8000/health` returns `HTTP 200` (healthcheck `healthy`, 36/36 tests passed).
   - From the Windows/WSL2 host via `http://127.0.0.1:18000/`, Docker bridge NAT translates the client IP to the bridge gateway (`172.18.0.1`), which `config/lan_access_policy.json` (`enabled: false`) blocks with `HTTP 403 {"detail":"Akses LAN DSS-PIK sedang dinonaktifkan oleh operator server."}`.
   - **Fix for Next Phase**: Either mount a Docker-specific `lan_access_policy.json` allowing the Docker bridge subnet (since `compose.yaml` already restricts host exposure to `127.0.0.1:18000:8000`) or allow `CEWS_TRUST_DOCKER_BRIDGE=true` in middleware.
2. **`.env.docker` Bcrypt `$` Interpolation**:
   - Docker Compose still warns when `${DSS_PIK_PASSWORD_HASH}` in `compose.yaml` expands a bcrypt hash containing `$`. Switching `compose.yaml` to `env_file: .env.docker` (or escaping `$` -> `$$` in `.env.docker`) eliminates the warning completely.

---

## 6. Next Steps Toward Ubuntu Server Deployment
1. Resolve the Docker bridge gateway middleware allowlist for containerized deployments behind localhost/reverse proxy.
2. Switch `compose.yaml` to `env_file` for clean bcrypt hash delivery without interpolation warnings.
3. Tag release image `dss-pik:1.0.0-rc1` and prepare offline `.tar.gz` + `SHA256` transfer bundle for BMKG Office Ubuntu Server.
