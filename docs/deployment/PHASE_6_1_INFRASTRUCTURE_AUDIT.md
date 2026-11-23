# PHASE 6.1 — INFRASTRUCTURE & DEPLOYMENT AUDIT
**Sistem:** DSS-PIK BMKG Stasiun Meteorologi Kelas II Raja Haji Fisabilillah Tanjungpinang  
**Tanggal Audit:** 18 November 2026  
**Status:** Read-Only Audit Selesai  

---

## 1. Fakta yang Sudah Diverifikasi

| Komponen | Hasil Pemeriksaan Aktual |
|---|---|
| **Sistem Operasi** | Windows 11 (`Windows-11-10.0.26200-SP0`, 64-bit AMD64) |
| **Python Environment** | Python `3.12.10` (Global/System Python, tanpa `.venv` aktif) |
| **Lokasi Repository** | `C:\LATSAR\ASLI2` (menggunakan `Path(__file__).resolve().parent.parent` di `config/paths.py`, tidak bergantung pada drive `F:\`) |
| **Backend Server** | FastAPI `0.116.1` + Uvicorn `0.35.0` dijalankan via `backend/launcher.py` (`0.0.0.0:8000`) |
| **Frontend Build** | React `18.3.1` + Vite `5.4.21`. Production bundle (`frontend/dist/`) sudah dapat di-build (`npm --prefix frontend run build`) |
| **Database** | MariaDB (`cews_db`) pada `127.0.0.1:3306`, dikonfigurasi via `CEWS_DB_*` env vars di `backend/database.py` |
| **Parquet & Referensi** | 34 file `.parquet` terverifikasi di `data/` (SPI harian, dasarian, bulanan, metadata stasiun, ECMWF snapshot) |
| **Reverse Proxy** | Belum ada `nginx`, `caddy`, atau `IIS` terpasang pada mesin pengembangan |
| **Autentikasi** | Signed HttpOnly session cookie + Bearer token fallback (`DSS_PIK_USERNAME`, `DSS_PIK_PASSWORD_HASH`, `DSS_PIK_SESSION_SECRET`) |

---

## 2. Masalah yang Ditemukan (Deployment Blockers)

1. **Frontend API URL Fallback (`frontend/src/config.js`)**:
   - Jika `VITE_API_BASE_URL` tidak diset, kode melakukan fallback ke `http://${window.location.hostname}:8000`.
   - Pada akses HTTPS melalui Reverse Proxy/VPN, ini akan memicu **Mixed Content Error** dan mencoba mengakses port `8000` yang seharusnya tertutup.
2. **CORS Configuration (`backend/main.py`)**:
   - `ALLOWED_ORIGINS` dan `LAN_ORIGIN_REGEX` masih hardcoded untuk localhost dan subnet LAN. Belum mendukung allowlist berbasis environment variable (`CEWS_CORS_ORIGINS`) untuk hostname internal/VPN.
3. **API Documentation Terbuka di Production (`backend/main.py`)**:
   - `/docs`, `/redoc`, dan `/openapi.json` selalu aktif dan terdaftar di `public_paths` tanpa proteksi di mode production.
4. **Cookie `Secure` Flag (`backend/main.py`)**:
   - `response.set_cookie(..., secure=False)` hardcoded. Saat diakses via HTTPS Reverse Proxy, flag `Secure` harus aktif (`CEWS_COOKIE_SECURE=true`).
5. **Mode Development pada Launcher & Main (`backend/main.py`, `backend/launcher.py`)**:
   - `backend/main.py` `__main__` menggunakan `reload=True`.
   - `backend/launcher.py` menjalankan Vite dev server (`port 5173`) sebagai server frontend utama, padahal di production harus menyajikan `frontend/dist` (tanpa Vite dev server).
6. **Tidak Ada `.env.production.example` & Skrip Backup Terotomasi**:
   - Baru tersedia `.env.example` dasar; belum ada template konfigurasi production dan skrip backup MariaDB + Parquet SHA-256.

---

## 3. Risiko Deployment

- **Risiko Eksposur Port**: Menjalankan `0.0.0.0:8000` atau `0.0.0.0:5173` tanpa firewall/reverse proxy berisiko mengekspos layanan secara langsung ke jaringan non-VPN.
- **Risiko Multi-Worker State**: `backend/main.py` dan `spi_calculation_service.py` menyimpan cache dan staging session di memori proses. Menjalankan `uvicorn --workers > 1` tanpa external store akan menyebabkan inkonsistensi session/cache. **Wajib menggunakan 1 worker (`--workers 1`)**.
- **Risiko Kebocoran Data Operasional**: Folder `data/` dan `.env` tidak boleh berada di root web server publik.

---

## 4. Konfigurasi yang Belum Tersedia (Diperlukan dari Administrator BMKG)

1. **Hostname / DNS Internal** (contoh: `dss-pik.bmkg-kepri.internal`) atau Private IP tetap server kantor.
2. **Sertifikat TLS/HTTPS** (Internal CA BMKG atau self-signed internal yang dipercaya).
3. **VPN Institusi BMKG** (konfigurasi gateway, client profile, dan firewall allowlist menuju server kantor).
4. **Reverse Proxy** di server kantor (IIS dengan ARR/URL Rewrite atau Nginx for Windows).

