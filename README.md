# DSS-PIK — Decision Support System Peringatan Iklim Kepulauan Riau

**BMKG Stasiun Meteorologi Kelas II Raja Haji Fisabilillah Tanjungpinang**

DSS-PIK adalah sistem pendukung keputusan peringatan dini iklim operasional untuk memantau, menganalisis, dan memetakan potensi **PDKM (Peringatan Dini Kekeringan Meteorologis)** dan **PDCHT (Peringatan Dini Curah Hujan Tinggi)** pada **57 Stasiun Pengamatan** dan **59 Kecamatan (7 Kabupaten/Kota)** di Provinsi Kepulauan Riau.

---

## 1. Arsitektur Aplikasi (Split 3-Container)

```text
Client Browser
     │
     ▼ (HTTP/HTTPS via Host Reverse Proxy)
┌─────────────────────────────┐
│  frontend (Nginx 1.27)      │  Menyajikan React/Vite SPA & reverse proxy /api/, /health
└──────────────┬──────────────┘
               │ Internal Docker Network (`dss_pik_internal`)
               ▼
┌─────────────────────────────┐
│  backend (FastAPI / Py 3.12)│  REST API, Decision Engine, SPEI, WebGIS (CEWS_SERVE_FRONTEND=false)
└──────────────┬──────────────┘
               │ Internal Docker Network (`mariadb:3306`, tidak diekspos ke LAN)
               ▼
┌─────────────────────────────┐
│  mariadb (MariaDB 11.4)     │  Database operasional persisten (`dss_pik_mariadb_data`)
└─────────────────────────────┘
```

- **MariaDB (`3306`)** dan **Backend (`8000`)** bersifat **internal-only** (tidak diekspos ke jaringan publik).
- **Frontend (`Nginx :80`)** menjadi satu-satunya entry point HTTP (default terikat ke `127.0.0.1:8080:80` untuk diterminasi oleh reverse proxy TLS/HTTPS server).

---

## 2. Struktur Direktori Utama

```text
DSS-PIK/
├── compose.yaml                  # Konfigurasi Docker Compose utama (3 service: frontend, backend, mariadb)
├── .env.example                  # Template environment standar untuk split Compose
├── .env.production.example       # Template environment produksi Ubuntu Server
├── .gitignore / .dockerignore    # Pengecualian secret, database dump, Parquet, cache
├── frontend/
│   ├── Dockerfile                # Multi-stage Node 22 build -> Nginx 1.27 runtime
│   ├── nginx.conf                # Konfigurasi SPA fallback & reverse proxy (/api/, /health)
│   ├── package.json / src/ / public/
├── backend/
│   ├── Dockerfile                # Python 3.12-slim non-root runtime (CEWS_SERVE_FRONTEND=false)
│   └── main.py, database.py, decision_engine.py, lan_firewall_service.py, ...
├── SPEI/                         # Modul perhitungan SPI/SPEI
├── config/                       # Konfigurasi path, aturan CEWS, & template LAN policy
├── pipeline/ & scripts/          # Utilitas pemrosesan data, backup & restore
├── deploy/                       # Template deployment & konfigurasi legacy (`deploy/legacy/`)
├── docs/                         # Dokumentasi arsitektur, handover, & deployment
├── tests/                        # Suite pengujian integrasi & regresi
└── .github/workflows/deploy.yml  # Workflow CI/CD manual (`workflow_dispatch`)
```

---

## 3. Prasyarat Server (Ubuntu Server)

- **OS**: Ubuntu Server 22.04 / 24.04 LTS (`linux/amd64`)
- **Runtime**: Docker Engine >= 24.x dan Docker Compose v2 plugin (`docker compose version`)
- **Dataset & Database**: File data operasional (`data/`) dan dump SQL awal diserahkan terpisah melalui media terenkripsi resmi (tidak disimpan di GitHub).

---

## 4. Persiapan Environment (Wajib Dibuat di Server)

> **PENTING KEAMANAN**: Jangan pernah menyimpan password, session secret, bcrypt hash produksi, atau SSH key ke GitHub. Buat seluruh credential unik langsung di server target!

```bash
cp .env.production.example .env.production
chmod 600 .env.production

# Generate session secret (64 hex):
openssl rand -hex 32

# Generate password database kuat (buat dua nilai berbeda untuk app & root):
openssl rand -base64 24
```

Isi akun administrator unik pada `.env.production` (backend otomatis melakukan bcrypt hash satu kali di memori saat startup):
```env
DSS_PIK_USERNAME=your_admin_username
DSS_PIK_PASSWORD=your_own_strong_password
DSS_PIK_SESSION_SECRET=<hasil_openssl_rand_hex_32>
```
*(Kompatibilitas legacy: `DSS_PIK_PASSWORD_HASH` tetap didukung sementara jika `DSS_PIK_PASSWORD` tidak disetel.)*

Pastikan pada `.env.production`:
- `CEWS_DOCKER_LOCAL_ONLY=false`
- `CEWS_TRUSTED_PROXY_CIDRS=172.16.0.0/12` (atau CIDR bridge Docker spesifik)
- `DSS_PIK_DATA_DIR=/srv/dss-pik/data` (lokasi mount read-only dataset operasional)

---

## 5. Menjalankan, Memantau, & Mengelola Container

### Menjalankan Stack
```bash
docker compose --env-file .env.production up -d --build
```

### Memeriksa Status & Logs
```bash
docker compose --env-file .env.production ps
docker compose --env-file .env.production logs -f --tail=100 backend frontend
curl -fsS http://127.0.0.1:8080/health
```

### Menghentikan / Restart Aman
```bash
docker compose --env-file .env.production stop
docker compose --env-file .env.production restart
```

---

## 6. Update Source Code Melalui `git pull`

```bash
# 1. Backup database terlebih dahulu sebelum update!
# 2. Tarik perubahan terbaru dari branch main:
git pull origin main

# 3. Rebuild & restart hanya service aplikasi (volume database tidak tersentuh):
docker compose --env-file .env.production up -d --build --no-deps backend frontend

# 4. Verifikasi kesehatan aplikasi:
curl -fsS http://127.0.0.1:8080/health
```

---

## 7. Perlindungan Volume Database & Backup

> **PERINGATAN KERAS**: **JANGAN PERNAH** menjalankan `docker compose down -v` saat pemeliharaan rutin atau update! Opsi `-v` menghapus volume persisten `dss_pik_mariadb_data` beserta seluruh data operasional.

### Backup Database (Aman Tanpa Mengekspos Password di `ps`)
```bash
docker compose --env-file .env.production exec -T mariadb \
  bash -c 'MYSQL_PWD="$MARIADB_PASSWORD" mariadb-dump --single-transaction --routines --triggers -u"$MARIADB_USER" "$MARIADB_DATABASE"' \
  | gzip > /srv/dss-pik-backups/cews_db_$(date +%Y%m%d_%H%M%S).sql.gz
```

---

## 8. Dokumentasi Terkait
- Arsitektur Deployment: [`docs/deployment/DSS_PIK_DEPLOYMENT_ARCHITECTURE.md`](docs/deployment/DSS_PIK_DEPLOYMENT_ARCHITECTURE.md)
- Panduan Konfigurasi Produksi: [`docs/deployment/PRODUCTION_CONFIGURATION_GUIDE.md`](docs/deployment/PRODUCTION_CONFIGURATION_GUIDE.md)
- Arsitektur Split & CI/CD (Phase 8.4): [`docs/deployment/PHASE_8_4_FINAL_GITHUB_AND_SPLIT_ARCHITECTURE.md`](docs/deployment/PHASE_8_4_FINAL_GITHUB_AND_SPLIT_ARCHITECTURE.md)
- Hardening Repository (Phase 8.5): [`docs/deployment/PHASE_8_5_GITHUB_HARDENING.md`](docs/deployment/PHASE_8_5_GITHUB_HARDENING.md)
