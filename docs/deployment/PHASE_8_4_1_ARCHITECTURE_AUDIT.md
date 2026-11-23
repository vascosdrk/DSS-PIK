# PHASE 8.4.1 — COMPLETE ARCHITECTURE AUDIT (SPLIT MULTI-CONTAINER)

**Project**: DSS-PIK BMKG Kepulauan Riau  
**Baseline**: `v1.0.0` (42/42 tests passed, sealed at `F:\TNJ\paper\DSS_PIK_DELIVERY_v1.0.0`)  
**Date**: 2026-11-23

---

## 1. Existing Architecture (`v1.0.0` Single-Container)
- **Container 1 (`dss_pik_app`)**: FastAPI (`uvicorn backend.main:app`) serving both REST API (`/api/v1/*`, `/health`) and static React/Vite SPA (`frontend/dist/`, `CEWS_SERVE_FRONTEND=true`).
- **Container 2 (`mariadb:11.4`)**: Internal-only database (`cews_db` / `cews_db_migration_test`).
- **Frontend API Routing (`frontend/src/config.js`)**: Already uses same-origin relative URLs (`''`) in production/reverse-proxy mode — **zero breaking frontend API changes required**.

## 2. Target Architecture (Phase 8.4 — 3-Container Split)
```text
Client Browser -> [frontend (Nginx :80)] -> [backend (FastAPI :8000, internal)] -> [mariadb (11.4 :3306, internal)]
```
- **`frontend/`**: Multi-stage `node:22-alpine` (`npm ci` + `npm run build`) -> `nginx:1.27-alpine` serving SPA + reverse proxying `/api/` and `/health` to `http://backend:8000` (overwriting `X-Real-IP` with `$remote_addr`).
- **`backend/`**: `python:3.12-slim` non-root (`dsspik`), `CEWS_SERVE_FRONTEND=false`, `requirements-lock.txt`, `SPEI/src` on `PYTHONPATH`, internal-only (`8000/tcp` not published publicly).
- **`mariadb`**: `mariadb:11.4`, internal-only (`3306/tcp` not published), persistent named volume.
- **Root `compose.yaml`**: Orchestrates `frontend`, `backend`, `mariadb` on internal Docker bridge network; previous single-container compose preserved as `compose.single-container.yaml`.

## 3. Data Persistence & Security Considerations
- **Persistence**: MariaDB volume + read-only canonical data mount (`./data:/app/data:ro`) + isolated writable named volumes for generated maps, SIH3 outputs, and runtime logs.
- **Security**: `lan_access_guard_middleware` extended with explicit `CEWS_TRUSTED_PROXY_CIDRS` support so ONLY requests arriving from the trusted internal Docker Nginx proxy honor the overwritten `X-Real-IP` header; untrusted peers and spoofed `X-Forwarded-For` headers remain strictly rejected (`HTTP 403`).
