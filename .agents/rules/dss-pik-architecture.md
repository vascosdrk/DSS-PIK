---
trigger: always_on
---

# DSS-PIK Official Architecture & Persistence Rules (Phase 8.0+)

These rules are permanent architectural decisions for the **DSS-PIK (Decision Support System Peringatan Iklim) Kepulauan Riau** project. All future AI development sessions MUST follow them.

## 1. Three-Environment Architecture

DSS-PIK operates across three strictly separated environments:

1. **DEVELOPMENT** (Windows laptop — Antigravity IDE, Python 3.12 `.venv`, FastAPI, React/Vite, Docker Desktop, local MariaDB, private Git repo):
   - Daily feature development, bug fixing, scientific calculation improvements, and local Docker testing.
   - Must never interrupt or connect directly to the office production server.
2. **STAGING** (Local Docker Compose stack or designated test server):
   - Validates versioned Docker images, database compatibility, regression suites (`pytest`), scientific calculations, and spatial/map rendering.
   - No release may go to production without staging validation.
3. **PRODUCTION** (BMKG office Ubuntu Server — Docker Engine, Docker Compose, versioned DSS-PIK image, persistent MariaDB & operational storage):
   - Official operational service for authorized office clients.
   - Never use production as a primary development environment.

## 2. Development & Release Workflow

Enforce: `DEVELOP -> TEST LOCALLY -> STAGING VALIDATION -> VERSION/TAG -> APPROVED PRODUCTION DEPLOYMENT -> POST-DEPLOYMENT VERIFICATION`.

- **Git**: Private repository only. Track source code and `.env*.example` templates. NEVER commit `.env`, credentials, database dumps, or sensitive operational datasets.
- **Docker**: Always build versioned images (e.g., `dss-pik:1.x.y`); never rely solely on `latest` in production. Preserve rollback capability to the previous verified image.

## 3. Data & Database Persistence Policy (CRITICAL)

**Application containers are replaceable. Operational data is NOT replaceable.**

- **MariaDB**: Must use persistent named volumes or approved host persistent storage. Data must survive container recreation and upgrades.
- **Operational Datasets**: Keep canonical Parquet files (34 files), SPI datasets, shapefiles, GeoJSON, reference datasets, and historical rainfall data outside replaceable Docker images (mount read-only for canonical data; separate writable volumes for generated outputs).
- **Destructive Commands**: NEVER run `docker compose down -v` during routine maintenance or updates.
- **Migrations**: Schema changes require a pre-migration backup, isolated compatibility testing, and explicit approval.

## 4. Configuration, Security & Scientific Integrity

- Keep secrets out of Docker images and Git.
- Never hardcode host paths (e.g., `C:\LATSAR\ASLI2`) or server IP addresses.
- Do not expose MariaDB port `3306` directly to the office LAN unless explicitly authorized.
- Do not assume external internet access on the office production server.
- Never modify validated scientific calculation rules or historical rainfall/canonical Parquet datasets without explicit scientific approval and full regression testing.
