# PHASE 8.4 — SPLIT MULTI-CONTAINER ARCHITECTURE, GITHUB & CI/CD REPORT

**Project**: Decision Support System Peringatan Iklim (DSS-PIK) Kepulauan Riau  
**Workspace**: `F:\TNJ\paper\DSS_PIK_MIGRATION_EXPORT\ASLI2`  
**Server Handover Package**: `F:\TNJ\paper\DSS_PIK_SERVER_DEPLOYMENT`  
**Date**: 2026-11-23  
**Status**: **SPLIT 3-CONTAINER ARCHITECTURE VERIFIED (47/47 TESTS PASSED)**

---

## 1. Architecture Changes Implemented
- **Frontend Service (`frontend/Dockerfile`, `frontend/nginx.conf`)**: Multi-stage `node:22-alpine` (`npm ci` + `npm run build`) -> `nginx:1.27-alpine` (`dss-pik-frontend:1.1.0`), serving SPA + reverse proxying `/api/` and `/health` to `http://backend:8000` while overwriting `X-Real-IP` with `$remote_addr`.
- **Backend Service (`backend/Dockerfile`)**: `python:3.12-slim` non-root `dsspik` (`dss-pik-backend:1.1.0`), `CEWS_SERVE_FRONTEND=false`, internal-only `8000/tcp`.
- **Root `compose.yaml`**: Orchestrates `frontend` -> `backend` -> `mariadb` (`mariadb:11.4`, internal-only `3306/tcp`) with persistent named volumes and read-only canonical data mount.
- **Trusted Proxy Security (`backend/lan_firewall_service.py`, `backend/main.py`)**: Added `CEWS_TRUSTED_PROXY_CIDRS` so `X-Real-IP` is honored **only** when arriving from the trusted internal Docker proxy CIDR; untrusted peers and spoofed headers remain rejected (`HTTP 403`).
- **CI/CD Workflow (`.github/workflows/deploy.yml`)**: Manual (`workflow_dispatch`) GitHub Actions workflow running automated tests, building & publishing `dss-pik-backend` and `dss-pik-frontend` to GHCR, and deploying over SSH via GitHub Secrets (`DEPLOY_HOST`, `DEPLOY_USER`, `DEPLOY_SSH_KEY`, `DEPLOY_PATH`, `DEPLOY_PORT`, `GHCR_USER`, `GHCR_TOKEN`).

---

## 2. Isolated 3-Container Integration Test Results (`dss-pik-split-test`, Port `28080`)
- **All 3 Containers Healthy**: `dss-pik-split-test-mariadb-1`, `dss-pik-split-test-backend-1`, `dss-pik-split-test-frontend-1`.
- **Database Counts**: `stations=57`, `cews_rainfall_daily=287,189`, `cews_forecast_snapshot=3,244`, `cews_regional_warning_decisions=42`, `cews_regional_decision_audit_log=462`.
- **End-to-End HTTP via Nginx (`:28080`)**:
  - `GET /health` -> **HTTP 200** `{"status":"ok","service":"cews-api","database":"connected"}`
  - `GET /`, `/DSS_PIK_logo_hitam.png`, `/dss_pik_shield_white_line_transparent.png`, `/api/v1/geo/layers/kabkot` -> all **HTTP 200**.
- **Automated Regression & Security Suite**: **`47 passed in 109.78s`** (`36` regression + `6` Phase 8.2.2 + `5` Phase 8.4 split-proxy tests; `0` failed, `0` skipped).
- **Restart Persistence**: All 3 containers restarted cleanly and recovered to `healthy` (`HTTP 200`).
- **Existing Environments Preserved**: Native `:8000`, Docker dev `:18000`, sealed `v1.0.0` release (`F:\TNJ\paper\DSS_PIK_PRODUCTION_RELEASE`), and delivery (`F:\TNJ\paper\DSS_PIK_DELIVERY_v1.0.0`) remain untouched.

---

## 3. GitHub & Technician Pending Requirements
- **Local Git**: `git 2.43.0` is available in Ubuntu-24.04 WSL2; `.gitignore` hardened to exclude `.env*`, `data/`, `backups/`, `*.sql`, `*.tar.gz`, `*.zip`, `.venv/`, `node_modules/`.
- **GitHub Push Prerequisite**: `gh` CLI is not installed and GitHub authentication is not yet configured. To push to a **private** `dss-pik` repository:
  ```bash
  # In Ubuntu-24.04 WSL2:
  cd /mnt/f/TNJ/paper/DSS_PIK_MIGRATION_EXPORT/ASLI2
  git init -b main && git add . && git commit -m "Phase 8.4: Split 3-container architecture and CI/CD"
  git remote add origin https://github.com/<ORG_OR_USER>/dss-pik.git
  git push -u origin main
  ```
- **BMKG IT Technician Inputs Required**: Ubuntu Server `DEPLOY_HOST`, `DEPLOY_USER`, `DEPLOY_SSH_KEY`, `DEPLOY_PATH`, `GHCR` credentials, authorized LAN subnets, and HTTPS/TLS reverse proxy certificates.
