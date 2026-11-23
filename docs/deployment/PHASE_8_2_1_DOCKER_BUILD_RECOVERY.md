# PHASE 8.2.1 — DOCKER BUILD RECOVERY & INTERPOLATION FIX REPORT

**Project**: DSS-PIK BMKG Kepulauan Riau  
**Date**: 2026-11-22  
**Status**: **RECOVERED — IMAGE BUILT & CONTAINERS HEALTHY**

---

## 1. Root Cause Analysis of Initial Build (`PID 7107`)

- **Inspection**: `PID 7107` (`docker compose up -d --build`) was **not deadlocked**; it was actively downloading large `manylinux` Python wheels (`matplotlib`, `numpy`, `pandas`, `pyarrow`, `scipy`) over a ~50–80 kB/s link.
- **Failure**: After ~47 minutes, `pip install --no-cache-dir -r requirements-lock.txt` exited with `ReadTimeoutError: HTTPSConnectionPool(host='files.pythonhosted.org', port=443): Read timed out.` (default 15s socket timeout).

## 2. Recovery Actions Executed

1. **Dockerfile Pip Resilience**: Updated `Dockerfile` to use BuildKit's `--mount=type=cache,target=/root/.cache/pip` with `--default-timeout=180 --retries=10` (keeps the final runtime image lean while preventing timeouts and re-downloads).
2. **`.env.docker` Quoting**: Preserved the exact original 60-character `DSS_PIK_PASSWORD_HASH` and wrapped it in single quotes (`'...'`); validated with `docker compose -p dss-pik-dev --env-file .env.docker config --quiet` (exit code `0`).
3. **Clean Rebuild**: Reused cached `frontend-builder`, `apt-get`, and `mariadb:11.4` layers; `dss-pik:0.8.2-dev` built cleanly with exit code `0`.

## 3. Post-Recovery Verification

- **Image Built**: `dss-pik:0.8.2-dev` (verified present).
- **Containers**: `dss_pik_dev_mariadb` (`healthy`) and `dss_pik_dev_app` (`healthy`) on `dss-pik-dev`.
- **Database**: `stations=57`, `cews_rainfall_daily=287,189`, `cews_forecast_snapshot=3,244`, `cews_regional_warning_decisions=42`, `cews_regional_decision_audit_log=462`.
- **Regression Suite**: **36/36 PASSED** inside `dss_pik_dev_app` (`36.60s`).
- **Native DSS-PIK (`:8000`)**: Untouched and verified `HTTP 200` (`{"status":"ok","service":"cews-api","database":"connected"}`).
- **Remaining Note**: Host-to-container requests on `http://127.0.0.1:18000` currently receive `HTTP 403` from `lan_access_policy.json` (`enabled: false`) because Docker bridge NAT uses gateway IP `172.18.0.1`; documented in `PHASE_8_2_DOCKERIZED_OPERATIONAL_TEST.md` for next-step resolution.
