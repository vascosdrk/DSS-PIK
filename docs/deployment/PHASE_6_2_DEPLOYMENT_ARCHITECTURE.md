# PHASE 6.2 — DEPLOYMENT ARCHITECTURE
**Model:** Option B — Institutional Server + Secure VPN + Private Network

```
Remote User (Browser)
  │
  ▼ [Encrypted Tunnel]
Institutional VPN BMKG
  │
  ▼ [Private Network / Internal DNS]
HTTPS Reverse Proxy (IIS ARR / Nginx for Windows :443)
  │  - TLS Termination
  │  - Security Headers & Rate/Access Control
  │  - Blocks /data/, /backend/, /.env
  │
  ▼ [Localhost Loopback 127.0.0.1:8000]
FastAPI Backend + Production SPA (Uvicorn, 1 Worker, CEWS_ENV=production)
  │  - Serves frontend/dist/ (no Vite dev server :5173)
  │  - /api/v1/* protected by HttpOnly Cookie + Bearer Auth
  │
  ├──► MariaDB 11.4.10 (127.0.0.1:3306, cews_db) — Localhost Only
  └──► Operational Parquet & Reference Files (data/) — Internal Disk Only
```

## Ketentuan Arsitektur
- **Single Worker (`--workers 1`)**: Wajib dipertahankan karena cache stasiun dan staging session SPI berada di memori proses.
- **Same-Origin Routing**: `frontend/src/config.js` otomatis menggunakan relative path (`''`) saat tidak berjalan di Vite dev server (`5173`), sehingga tidak ada hardcoded `localhost` atau port `8000` pada traffic browser.

