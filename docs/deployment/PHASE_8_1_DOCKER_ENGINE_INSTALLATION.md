# PHASE 8.1 — DOCKER ENGINE INSTALLATION REPORT (UBUNTU WSL2)

**Project**: Decision Support System Peringatan Iklim (DSS-PIK) Kepulauan Riau  
**Host OS**: Windows 10 Pro (`10.0.19045`, 64-bit)  
**WSL2 Distribution**: `Ubuntu-24.04` (`Ubuntu 24.04.5 LTS`, `noble`, `x86_64`, systemd `running`)  
**Date**: 2026-11-22  
**Status**: **SUCCESS — DOCKER ENGINE & COMPOSE VERIFIED**

---

## 1. Environment Inspection Results (Stage 1)

- **Linux Distribution**: `Ubuntu 24.04.5 LTS` (`VERSION_CODENAME=noble`)
- **Architecture**: `x86_64` (`amd64`)
- **Systemd**: `running`
- **Existing Docker Packages**: None installed prior to setup
- **Existing Docker APT Repository**: None configured prior to setup
- **TCP Ports 2375 & 2376**: Free (not occupied)
- **Available Disk Space (`/`)**: `955 GB` available (`1.3 GB` used of `1007 GB`, `1%`)

---

## 2. Installed Package Versions (Stages 2 & 3)

Configured via official Docker APT repository (`https://download.docker.com/linux/ubuntu`, GPG key `/etc/apt/keyrings/docker.asc`, suite `noble stable`):

| Package | Installed Version |
|---|---|
| `docker-ce` | `5:29.10.0-1~ubuntu.24.04~noble` |
| `docker-ce-cli` | `5:29.10.0-1~ubuntu.24.04~noble` |
| `containerd.io` | `2.4.2-4~ubuntu.24.04~noble` |
| `docker-buildx-plugin` | `0.39.1-1~ubuntu.24.04~noble` |
| `docker-compose-plugin` | `5.8.0-1~ubuntu.24.04~noble` |

---

## 3. Docker Engine & Systemd Status (Stage 4)

- **`containerd.service`**: enabled and **`active`**
- **`docker.service`**: enabled and **`active`**
- **Docker Engine Runtime Info**:
  - `ServerVersion`: `29.10.0` (API `1.57`, `linux/amd64`)
  - `containerd`: `v2.4.2` | `runc`: `1.5.3`
  - `StorageDriver`: `overlayfs`
  - `CgroupDriver`: `systemd`

---

## 4. Docker Compose Version

- `Docker Compose version v5.8.0`

---

## 5. Hello World Container Result (Stage 5)

- Command: `docker run --rm hello-world`
- Result: **PASS** — pulled `hello-world:latest` (`amd64`) from Docker Hub, created and executed the container, and returned `Hello from Docker!`.

---

## 6. Security Configuration & DSS-PIK Protection (Stages 6 & 7)

- **Docker TCP API (`2375` / `2376`)**: Verified **NOT exposed** (Unix socket only).
- **Windows Defender Firewall & Network Profiles**: Untouched.
- **Linux User Group**: `vascosdrk_` was **not** automatically added to the `docker` group (admin/root execution only).
- **Native DSS-PIK Protection**: Verified undisturbed on Windows port `8000` (`GET http://127.0.0.1:8000/health` -> `HTTP 200`, `{"status":"ok","service":"cews-api","database":"connected"}`). Native MariaDB, `.env`, database, and source code were not modified.

---

## 7. Installation Errors

- **None** for Docker repository setup, package installation, systemd startup, or `hello-world` container verification.
- *(Minor shell note: a trailing `\r` from Windows pipe formatting caused the final `id vascosdrk_` diagnostic line to print `no such user`, with zero impact on Docker installation or security.)*

---

## 8. Remaining Prerequisites for DSS-PIK Dockerization

Docker Engine and Docker Compose are now ready in `Ubuntu-24.04` (WSL2). To run the isolated DSS-PIK Compose stack (`127.0.0.1:18000:8000`) from WSL2:

1. Create `.env.docker` from `.env.docker.example` with local Docker test credentials.
2. Run `docker compose --env-file .env.docker build` and `docker compose --env-file .env.docker up -d` inside `/mnt/f/TNJ/paper/DSS_PIK_MIGRATION_EXPORT/ASLI2` (using `sudo` unless `vascosdrk_` is explicitly granted `docker` group access later).
3. Seed `cews_db_migration_test` into the isolated Docker MariaDB volume from `backup_20261122_131441` and verify `http://127.0.0.1:18000/health` and `http://127.0.0.1:18000/`.
