# PHASE 8.5 — GITHUB REPOSITORY HARDENING & TECHNICIAN HANDOVER REPORT

**Repository**: https://github.com/vascosdrk/DSS-PIK  
**Branch**: `main`  
**Date**: 2026-11-24  
**Status**: **HARDENED & READY FOR TECHNICIAN DEPLOYMENT (BANG HILMI)**

---

## 1. Final Repository Structure
- **Primary Compose**: `compose.yaml` (root) — 3-service split architecture (`frontend` Nginx -> `backend` FastAPI -> `mariadb` 11.4).
- **Split Dockerfiles**:
  - `frontend/Dockerfile` (Node 22 -> Nginx 1.27 + `frontend/nginx.conf`)
  - `backend/Dockerfile` (Python 3.12-slim non-root, `CEWS_SERVE_FRONTEND=false`)
- **Supporting Root Modules (Preserved)**: `SPEI/`, `config/`, `pipeline/`, `scripts/`, `database/`, `tests/`, `docs/`, `.github/workflows/deploy.yml`, `requirements.txt`, `requirements-lock.txt`.
- **Legacy Single-Container Archive (`deploy/legacy/`)**:
  - Moved `Dockerfile` -> `deploy/legacy/Dockerfile.single-container`
  - Moved `compose.production.yaml` -> `deploy/legacy/compose.production.single-container.yaml`
  - Added `deploy/legacy/README.md` clarifying that root `compose.yaml` is the sole recommended production configuration.

---

## 2. Security Audit Results (Current Tree & Full Git History)
| Category | Status | Finding |
|---|---|---|
| **Database & App Passwords** | **PASS** | Zero real MariaDB/root/app passwords or production bcrypt hashes in tracked files or Git history. |
| **API Keys, Tokens & SSH Keys** | **PASS** | Zero GitHub PATs, AWS keys, private keys, or real session secrets across entire Git history. |
| **Database Dumps & Operational Data** | **PASS** | Zero `.sql` dumps, `.parquet` datasets, SQLite DBs, or backups tracked in Git. |
| **Environment Files & Developer Paths** | **PASS** | Active `.env`, `.env.docker`, `.env.production`, `frontend/.env`, and `config/lan_access_policy.json` excluded. Removed developer path comment from `.env.docker.example`. |
| **`.gitignore` Hardening** | **PASS** | Added exclusions for `*.pem`, `*.key`, `*.p12`, `*.pfx`, `id_rsa*`, `id_ed25519*`, `*.sqlite*`, `*.db` while preserving `.env*.example` templates. |

---

## 3. Environment Template & Compose Consistency
- Standardized `.env.example`, `.env.production.example`, and `deploy/.env.production.example` to match 100% of root `compose.yaml` variables (`DSS_PIK_VERSION`, `DSS_PIK_BIND_IP`, `DSS_PIK_HTTP_PORT`, `DSS_PIK_DATA_DIR`, `CEWS_DB_*`, `MARIADB_ROOT_PASSWORD`, `CEWS_DOCKER_LOCAL_ONLY=false`, `CEWS_TRUSTED_PROXY_CIDRS=172.16.0.0/12`, `DSS_PIK_USERNAME`, `DSS_PIK_PASSWORD_HASH`, `DSS_PIK_SESSION_SECRET`).
- Updated `README.md` with complete technician deployment, `git pull` update, logging, and volume-safe backup instructions (zero internal IPs, passwords, or SSH keys).
- Validated `docker compose --env-file .env.example config --quiet` and `docker compose --env-file .env.production.example config --quiet` -> **PASS (0 errors)**.

---

## 4. Items Remaining for BMKG IT Technician (Bang Hilmi)
- Clone `https://github.com/vascosdrk/DSS-PIK.git` on Ubuntu Server.
- Generate unique production credentials in `.env.production` (`chmod 600`).
- Place operational `data/` directory at `/srv/dss-pik/data` and perform guarded first-time SQL restore from the separately delivered `DSS-PIK_v1.0.0_RESTRICTED_DATABASE`.
- Configure host HTTPS/TLS reverse proxy, `ufw` firewall rules, and GitHub Actions deployment secrets (`DEPLOY_HOST`, `DEPLOY_USER`, `DEPLOY_SSH_KEY`, `DEPLOY_PATH`, `GHCR_*`) when enabling CI/CD.
