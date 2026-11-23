# DSS-PIK PRODUCTION CONFIGURATION GUIDE (UBUNTU SERVER)

**Release**: `v1.0.0` (`dss-pik:1.0.0`)  
**Target**: BMKG Office Ubuntu Server (Docker Engine + Docker Compose v2)

---

## 1. Security Architecture

- **`CEWS_DOCKER_LOCAL_ONLY`**: Hardcoded to `"false"` in `compose.production.yaml`. Never enable this in production.
- **MariaDB Isolation**: `dss_pik_prod_mariadb` listens only on `dss_pik_prod_internal` (`3306/tcp` is never published to host/LAN).
- **Default Ingress**: `dss_pik_prod_app` binds to `127.0.0.1:8000:8000` by default. Production office access should be terminated through an approved reverse proxy (**Nginx** or **Caddy**) with HTTPS/TLS and Ubuntu `ufw` firewall rules allowing only authorized office LAN subnets.
- **LAN Access Policy (`config/lan_access_policy.json`)**: When deploying behind a host reverse proxy on Ubuntu, configure the approved reverse proxy / office subnet explicitly with the BMKG IT technician rather than disabling authentication or trusting arbitrary `X-Forwarded-For` headers.

## 2. Credential Provisioning (On Target Server Only)

Never reuse development passwords. On the Ubuntu Server:
```bash
cp .env.production.example .env.production
chmod 600 .env.production

# Generate 64-char session secret:
openssl rand -hex 32

# Generate strong DB passwords:
openssl rand -base64 24

# Generate operator bcrypt password hash (wrap result in single quotes in .env.production):
docker run --rm -it dss-pik:1.0.0 python -c "import bcrypt, getpass; print(bcrypt.hashpw(getpass.getpass('Operator password: ').encode(), bcrypt.gensalt()).decode())"
```

## 3. Persistent Storage Layout (`/srv/dss-pik/`)

- `/srv/dss-pik/data/` — Canonical Parquet files (34 files), GeoJSON, shapefiles, reference assets (mounted `:ro`).
- Docker named volumes (survive container replacement and image upgrades):
  - `dss_pik_prod_mariadb_data` — MariaDB database files.
  - `dss_pik_prod_maps_output` — Generated official warning maps.
  - `dss_pik_prod_sih3_output` — Generated SIH3 JSON publications.
  - `dss_pik_prod_runtime_logs` — Application runtime logs.
  - `dss_pik_prod_outputs` — General operational outputs.
- **PROHIBITED**: Never run `docker compose -f compose.production.yaml down -v` during routine maintenance or upgrades.
