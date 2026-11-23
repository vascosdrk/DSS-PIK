# DSS-PIK OFFICIAL DEPLOYMENT ARCHITECTURE (PHASE 8.0)

**Project**: Decision Support System Peringatan Iklim (DSS-PIK) Kepulauan Riau  
**Institution**: BMKG Stasiun Meteorologi Kelas II Raja Haji Fisabilillah Tanjungpinang  
**Status**: Official Approved Architecture (2026-11-22)

---

## 1. Three-Environment Architecture

| Environment | Host / Platform | Stack | Purpose |
|---|---|---|---|
| **DEVELOPMENT** | Windows 10/11 Laptop (Antigravity IDE) | Python 3.12 `.venv`, FastAPI, React/Vite, MariaDB 11.4, Docker Desktop, Private Git | Daily feature development, bug fixes, scientific improvements, local Docker testing |
| **STAGING** | Local Docker Compose (`127.0.0.1:18000`) or Test Server | Versioned `dss-pik:<ver>` image + `mariadb:11.4` container + isolated volumes | Image build verification, DB compatibility, `pytest` regression, spatial/map validation |
| **PRODUCTION** | BMKG Office Ubuntu Server | Ubuntu Server, Docker Engine, Docker Compose, versioned `dss-pik:<ver>` image, MariaDB 11.4, persistent volumes | Official operational service for authorized office LAN clients (never used for primary dev) |

---

## 2. Development & Release Workflow

```text
DEVELOP (Windows Laptop)
   -> TEST LOCALLY (pytest 36/36 + UI + SPI)
   -> STAGING VALIDATION (Docker Compose isolated stack)
   -> VERSION / TAG (Git tag + versioned Docker image `dss-pik:x.y.z`)
   -> APPROVED PRODUCTION DEPLOYMENT (BMKG IT Technician on Ubuntu Server)
   -> POST-DEPLOYMENT VERIFICATION (/health, DB counts, UI, maps)
```

- **Git Policy**: Private repository only. Track source code and `.env*.example`. Never commit `.env`, credentials, SQL dumps, or sensitive operational datasets.
- **Image Versioning**: Always tag production images with explicit semantic versions (e.g., `dss-pik:1.0.0`). Never rely exclusively on `latest`. Keep the previous verified image tag available for instant rollback.

---

## 3. Data & Database Persistence Policy (CRITICAL)

**Application containers are replaceable. Operational data is NOT replaceable.**

1. **MariaDB Storage**:
   - Store MariaDB data in a persistent named volume (`dss_pik_mariadb_data`) or approved host persistent directory (`/srv/dss-pik/mariadb`).
   - Database data must survive container recreation, image upgrades, and server reboots.
2. **Operational & Canonical Datasets**:
   - Canonical datasets (`data/raw/`, `data/reference/`, `data/historical/` — including the 34 canonical Parquet files, SPI datasets, GeoJSON, and shapefiles) are stored outside the Docker image and mounted **read-only (`:ro`)**.
   - Generated operational outputs (`data/operational/`, `data/processed/`, `data/output/`, `logs/runtime/`) use separate persistent writable volumes/directories.
3. **Prohibited Routine Command**:
   - **NEVER run `docker compose down -v`** during routine updates or maintenance! The `-v` flag permanently deletes named volumes, including the MariaDB database volume.
4. **Schema Migrations**:
   - Every schema change requires: (1) pre-migration `mariadb-dump` backup, (2) isolated staging test, and (3) explicit approval before production rollout.

---

## 4. Configuration & Security Policy

- Keep all secrets in host-side `.env.docker` / `.env.production` (mode `600`), never baked into Docker images or Git.
- Never hardcode host paths or server IP addresses; rely on `config/paths.py` and environment variables (`CEWS_DB_HOST=mariadb`).
- Do **not** publish MariaDB port `3306` to the host or office LAN; keep MariaDB strictly on the internal Docker bridge network.
- Expose only the application HTTP/HTTPS endpoint to authorized office subnets via Ubuntu `ufw` / office firewall policy.
- Do not assume external internet access on the office Ubuntu Server.

---

## 5. Ubuntu Server Production Release Preparation

### 5.1 Prerequisites (Ubuntu Server 22.04 / 24.04 LTS)
- Docker Engine (official Docker CE repository or offline `.deb` bundle)
- Docker Compose v2 plugin (`docker compose version`)
- Persistent host storage directory (e.g., `/srv/dss-pik/` with dedicated backup storage `/srv/dss-pik-backups/`)

### 5.2 Image Distribution (Online Private Registry OR Offline Air-Gapped Transfer)
- **Option A (Private Registry)**: Push `registry.internal/dss-pik:<version>` from staging and pull on Ubuntu Server.
- **Option B (Offline Transfer — No Internet Required)**:
  ```bash
  # On staging/dev machine:
  docker save dss-pik:<version> mariadb:11.4 | gzip > dss-pik-bundle-<version>.tar.gz
  sha256sum dss-pik-bundle-<version>.tar.gz > dss-pik-bundle-<version>.sha256

  # On Ubuntu Server:
  sha256sum -c dss-pik-bundle-<version>.sha256
  docker load < dss-pik-bundle-<version>.tar.gz
  ```

### 5.3 Database Initialization & Scheduled Backups
- First-time initialization: seed `cews_db` from the verified SQL dump into the persistent MariaDB volume, then verify table counts (`stations=57`, `cews_rainfall_daily=287189`, etc.).
- Scheduled daily backup via `cron` on Ubuntu Server:
  ```bash
  docker exec dss_pik_mariadb mariadb-dump --single-transaction --routines --triggers -u root -p"$MARIADB_ROOT_PASSWORD" "$CEWS_DB_NAME" | gzip > /srv/dss-pik-backups/cews_db_$(date +%Y%m%d_%H%M%S).sql.gz
  ```

### 5.4 LAN Access, Firewall & HTTPS / Reverse Proxy
- Bind app container to `127.0.0.1:8000:8000` behind **Nginx / Caddy** reverse proxy terminating TLS (internal BMKG CA or self-signed cert) on ports `80`/`443`.
- Configure `ufw` to allow `443/tcp` only from approved office LAN subnets and deny `3306/tcp` externally.

### 5.5 Upgrade & Rollback Procedures
- **Upgrade**:
  1. Run pre-upgrade database backup.
  2. Load/pull new versioned image `dss-pik:<new_version>`.
  3. Update `DSS_PIK_VERSION=<new_version>` in `.env.production`.
  4. Run `docker compose --env-file .env.production up -d --no-deps app`.
  5. Verify `GET /health` -> HTTP 200 and UI/map rendering.
- **Rollback**:
  1. Revert `DSS_PIK_VERSION=<prev_version>` in `.env.production`.
  2. Run `docker compose --env-file .env.production up -d --no-deps app`.
  3. If a schema migration occurred, restore the pre-upgrade SQL backup into MariaDB.
