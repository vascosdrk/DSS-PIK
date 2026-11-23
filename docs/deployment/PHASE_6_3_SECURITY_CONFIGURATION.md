# PHASE 6.3 — SECURITY CONFIGURATION

## Checklist Keamanan Aplikasi (Sudah Diimplementasikan)
- **Production Mode (`CEWS_ENV=production`)**:
  - `/docs`, `/redoc`, dan `/openapi.json` otomatis dinonaktifkan (`None`) kecuali `CEWS_ENABLE_DOCS=true`.
  - `reload=True` tidak digunakan pada `run_cews_prod.bat`.
- **CORS Allowlist (`CEWS_CORS_ORIGINS`)**:
  - Tidak menggunakan wildcard (`*`). Mengizinkan hanya origin internal/VPN yang didaftarkan.
- **Session Cookie (`CEWS_COOKIE_SECURE=true`)**:
  - `HttpOnly=True`, `SameSite=Lax`, `Secure=True` saat diakses via HTTPS.
- **Authentication Guard**:
  - Seluruh endpoint `/api/v1/*` (termasuk ingestion, koreksi, SPI generator, refresh-evaluate, regional/kecamatan warnings) dilindungi oleh `authentication_guard_middleware`.
- **Database & File Isolation**:
  - MariaDB bind pada `127.0.0.1:3306`.
  - Folder `data/`, `backend/`, dan `.env` tidak diekspos oleh web server.

