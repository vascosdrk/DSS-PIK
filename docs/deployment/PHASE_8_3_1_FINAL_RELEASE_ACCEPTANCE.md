# PHASE 8.3.1 — FINAL PRODUCTION RELEASE ACCEPTANCE REPORT (`v1.0.0`)

**Project**: Decision Support System Peringatan Iklim (DSS-PIK) Kepulauan Riau  
**Release Package**: `F:\TNJ\paper\DSS_PIK_PRODUCTION_RELEASE`  
**Images**: `dss-pik:1.0.0` (`linux/amd64`) + `mariadb:11.4` (`linux/amd64`)  
**Date**: 2026-11-23  
**Release Readiness Decision**: **`READY FOR TECHNICIAN CONFIGURATION AND SERVER ACCEPTANCE`**

---

## 1. Stage 1 — Package & Checksum Verification
- `sha256sum -c 06_VERIFICATION/SHA256SUMS.txt`: **10/10 OK** (`dss-pik_1.0.0_linux_amd64.tar.gz`, `mariadb_11.4_linux_amd64.tar.gz`, `compose.production.yaml`, `.env.production.example`, `lan_access_policy.json.template`, `RESTRICTED_cews_db_release_20261123.sql`, `restore_dss_pik.py`, `backup_dss_pik.py`, `operational_data_manifest.json`, `README_START_HERE.md`).
- Secret audit on `02_COMPOSE/`: **PASS** (zero real development credentials or secrets present).

---

## 2. Stage 2 & 4 — Isolated Production Rehearsal & Installation Procedure Dry Run
- Executed from isolated `/tmp/dss_pik_rehearsal` (100% independent of `ASLI2/`) using `compose.production.yaml`, `dss-pik:1.0.0`, `mariadb:11.4`, `04_OPERATIONAL_DATA/data` (`:ro`), port `127.0.0.1:28000:8000`, and fresh temporary credentials.
- **Rehearsal Catch & Fix**: First-time restore as non-root `dsspik_prod` hit `ERROR 1227` on `v_cews_current_warning_map` (`DEFINER=root@localhost`). Updated `05_TECHNICIAN_GUIDES/UBUNTU_INSTALLATION.md` to run the guarded first-time restore as `root` (`-u root -p"$MARIADB_ROOT_PASSWORD"`). Re-ran cleanly with exit code `0`.

---

## 3. Stage 3 — Database, Endpoint, 42-Test & Persistence Results
- **Database Restore Verified (`cews_db`)**:
  - `stations`: **57** | `cews_rainfall_daily`: **287,189** | `cews_forecast_snapshot`: **3,244** | `cews_regional_warning_decisions`: **42** | `cews_regional_decision_audit_log`: **462** | View `v_cews_current_warning_map`: **present**.
- **HTTP Endpoints (Inside Production Container)**:
  - `GET /health` -> **HTTP 200** `{"status":"ok","service":"cews-api","database":"connected"}`
  - `GET /` -> **HTTP 200** (`1,374` bytes)
  - `GET /DSS_PIK_logo_hitam.png` -> **HTTP 200** (`308,083` bytes)
  - `GET /dss_pik_shield_white_line_transparent.png` -> **HTTP 200** (`320,566` bytes)
  - `GET /api/v1/geo/layers/kabkot` -> **HTTP 200** (`1,013,227` bytes)
- **Automated Regression & Security Suite**: **`42 passed in 42.60s`** (`0` failed, `0` skipped).
- **Restart Persistence (`docker compose restart`, no `-v`)**: Both `dss_pik_prod_mariadb` and `dss_pik_prod_app` returned to `healthy`; `post_restart_stations = 57`, `post_restart_rainfall = 287,189`.

---

## 4. Stage 5 — Security Verification
- `CEWS_DOCKER_LOCAL_ONLY`: **`False`** (strictly disabled in production).
- `lan_enabled`: **`False`** (no global LAN bypass).
- Application port binding: **`127.0.0.1:28000->8000/tcp`** (loopback-only default behind reverse proxy).
- MariaDB port `3306`: **internal-only** (`3306/tcp` not published to host/LAN).
- Temporary rehearsal containers & network cleanly removed; native DSS-PIK (`:8000`) and Docker dev (`:18000`) remained untouched.

---

## 5. Remaining Office-Specific Requirements (BMKG IT Technician)
- Official Ubuntu Server IP/DNS, authorized office LAN client subnet(s), HTTPS/TLS reverse proxy certificates (Nginx/Caddy), `ufw` firewall rules, server-side `.env.production` credential generation, and multi-PC office LAN acceptance testing.
