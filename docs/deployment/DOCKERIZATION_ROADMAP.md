# DSS-PIK DOCKERIZATION ROADMAP

**Baseline**: Phase 8.0 (2026-11-22)  
**Target**: Reproducible multi-environment Docker deployment (Windows Dev -> Staging -> Ubuntu Server Production)

---

## Stage 1 — Architecture & Foundation (COMPLETE — Phase 8.0)
- [x] Establish official Three-Environment Architecture (`Development`, `Staging`, `Production`).
- [x] Add permanent Antigravity project rules in `.agents/rules/dss-pik-architecture.md`.
- [x] Audit backend, frontend SPA serving, MariaDB connectivity, `config/paths.py`, and `SPEI/src` paths.
- [x] Create `Dockerfile` (multi-stage Node 22 + Python 3.12 non-root runtime).
- [x] Create `.dockerignore` (excludes secrets, dumps, caches, and large datasets).
- [x] Create isolated `compose.yaml` (`127.0.0.1:18000:8000`, internal-only MariaDB 11.4, persistent volumes).
- [x] Create `.env.docker.example` template.
- [x] Document Ubuntu Server production deployment, offline image transfer, backup, upgrade, and rollback.

## Stage 2 — Local Docker Desktop Activation (PENDING PREREQUISITE)
- [ ] Install **Docker Desktop for Windows** (WSL2 backend is already enabled: `Default Version: 2`).
- [ ] Copy `.env.docker.example` -> `.env.docker` and populate local test credentials.
- [ ] Build versioned image: `docker compose --env-file .env.docker build`.
- [ ] Start isolated stack: `docker compose --env-file .env.docker up -d`.
- [ ] Seed `cews_db_migration_test` into the isolated Docker MariaDB volume from `backup_20261122_131441`.
- [ ] Verify `http://127.0.0.1:18000/health`, `http://127.0.0.1:18000/`, maps, SPI, and `pytest` while native DSS-PIK stays running on `:8000`.

## Stage 3 — Staging Validation & Release Tagging
- [ ] Initialize private Git repository and push clean source code (verifying `.env` and dumps are excluded).
- [ ] Tag first release candidate (e.g., `v1.0.0-rc1` / `dss-pik:1.0.0-rc1`).
- [ ] Run full 36-test regression suite + manual operator UI checklist against the Dockerized staging stack.
- [ ] Verify container restart resilience and volume persistence (`docker compose down` without `-v`, then `up -d`).

## Stage 4 — Authorized Ubuntu Server Production Deployment
- [ ] Coordinate with BMKG IT technician on Ubuntu Server prerequisites (Docker Engine + Compose v2 + `/srv/dss-pik/`).
- [ ] Transfer verified versioned image (private registry or offline `.tar.gz` + SHA-256).
- [ ] Configure `.env.production`, reverse proxy (HTTPS), `ufw` firewall rules, and daily MariaDB backup cron.
- [ ] Execute controlled cutover and post-deployment verification.
