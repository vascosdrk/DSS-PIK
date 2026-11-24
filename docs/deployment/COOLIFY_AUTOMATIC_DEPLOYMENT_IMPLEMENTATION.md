# IMPLEMENTASI DEPLOY OTOMATIS COOLIFY — DSS-PIK

**Repository**: https://github.com/vascosdrk/DSS-PIK (`main`)  
**Production URL**: https://dss-pik.stamet-rhf.com/  
**Acuan**: Runbook Resmi Admin Server (`DSS-PIK: Deploy otomatis setiap push ke main` — @Hilmi)  
**Tanggal**: 2026-11-24

---

## 1. Audit Panduan & Source Code Aktual
- **`database/` di repository**: Lokal hanya memuat `database/schema.sql` (`9,916` bytes) yang dikecualikan oleh `*.sql` di `.gitignore`, sehingga direktori `database/` tidak ada di GitHub dan tidak digunakan oleh runtime `backend/`.
- **Autentikasi (`backend/auth.py`)**: Sudah mendukung `DSS_PIK_PASSWORD` (utama, bcrypt 1x di memori saat startup) dan `DSS_PIK_PASSWORD_HASH` (legacy fallback) sejak commit `4fe6f0a` — 100% kompatibel dengan `compose.coolify.yaml`.
- **`compose.yaml` lokal/server biasa**: Dipertahankan utuh tanpa perubahan.

---

## 2. Perubahan Dockerfile & Implementasi `compose.coolify.yaml`
1. **`backend/Dockerfile`**: Menghapus baris `COPY database/ ./database/` yang menyebabkan build Coolify gagal (`"/database": not found`).
2. **`compose.coolify.yaml`**: Dibuat di root repository persis mengikuti spesifikasi Bang Hilmi:
   - 3 service (`mariadb:11.4`, `backend` FastAPI, `frontend` Nginx `expose: 80` tanpa host port).
   - Startup script backend menulis `/app/config/lan_access_policy.json` dari `DSS_PIK_LAN_ALLOWED` lalu `exec uvicorn ...` sebagai user `dsspik`.
   - 6 named volumes: `dss_pik_mariadb_data`, `dss_pik_data`, `dss_pik_maps_output`, `dss_pik_sih3_output`, `dss_pik_runtime_logs`, `dss_pik_outputs`.

---

## 3. Validasi Persistent Database Volume & Integrasi Dataset

### A. Status Persistent Database Volume (`dss_pik_mariadb_data`)
- **Status**: **`BLOCKED FOR ADMIN CONFIRMATION`** (tidak memiliki akses panel Coolify untuk memverifikasi nama volume MariaDB aktual di server).
- **Risiko**: Coolify memberi prefix nama project ke named volume (`<project>_dss_pik_mariadb_data`). Saat beralih ke Application baru berbasis `compose.coolify.yaml`, admin server wajib memastikan volume MariaDB produksi yang sudah terisi (`stations=57`, `cews_rainfall_daily=287,189`) terhubung atau di-restore sekali dengan aman — **jangan pernah menjalankan `docker compose down -v`**.

### B. Integrasi Dataset Operasional (`/app/data`) — Perbandingan Pendekatan
| Pendekatan | Mekanisme | Kelebihan | Risiko / Catatan |
|---|---|---|---|
| **A. Named Volume (`dss_pik_data:/app/data`)** *(sesuai `compose.coolify.yaml` Bang Hilmi)* | Coolify membuat volume `dss_pik_data`, lalu admin menyalin `04_OPERATIONAL_DATA/data/` (`302` file, `34` Parquet, `kepri_kabkot.geojson`) ke dalam volume tersebut sekali + `chown -R 1000:1000 /app/data` | 100% portable di Coolify, tidak tergantung path host tertentu, tahan rebuild container | Volume baru **kosong** saat pertama dibuat; wajib diisi admin agar `/api/v1/geo/layers/kabkot` & Parquet tersedia |
| **B. Host Bind Mount (`/srv/dss-pik/data:/app/data:ro`)** *(dipakai di `compose.yaml`)* | Mount folder host read-only ke `/app/data` | Mudah diperbarui langsung di host server | Membutuhkan path host `/srv/dss-pik/data` tersedia dan terkonfigurasi di Coolify |

- **Rekomendasi**: Pertahankan **`dss_pik_data:/app/data`** sesuai `compose.coolify.yaml` Bang Hilmi agar kompatibel 100% dengan setup Coolify, lalu minta Bang Hilmi mengisi volume `dss_pik_data` sekali dari paket `04_OPERATIONAL_DATA/data/` (verifikasi: `reference/boundaries/kepri_kabkot.geojson` & `reference/stations/station_metadata.parquet` ada dan readable oleh UID `1000`).

---

## 4. Hasil Validasi Lokal (Tahap 5)
- `docker compose -f compose.yaml --env-file .env.example config --quiet` -> **PASS (`0` error)**
- `docker compose -f compose.coolify.yaml --env-file .env.example config --quiet` -> **PASS (`0` error)**
- `backend/Dockerfile` build test (`docker build -f backend/Dockerfile .`) -> **PASS** (tanpa `COPY database/`)
- `frontend/Dockerfile` build test -> **PASS** (cached, tidak berubah)
- Targeted auth tests (`test_auth_env_config.py`) -> **6/6 PASSED**
- Secret scan -> **PASS (`0` password, token, SSH key, `.env` aktif, `.sql`, atau `.parquet`)**

---

## 5. Status Webhook & Daftar Tindakan Lanjutan (Menunggu Bang Hilmi)
- **Status Webhook**: **BELUM DIPASANG** — menunggu **Payload URL** dan **Webhook Secret** privat dari Bang Hilmi.
- **Langkah Setelah Bang Hilmi Mengirimkan Payload URL & Secret**:
  1. Buka `https://github.com/vascosdrk/DSS-PIK/settings/hooks` -> **Add webhook**.
  2. Isi **Payload URL** & **Secret** dari Bang Hilmi, Content type `application/json`, **Enable SSL verification**, Event **Just the push event**, **Active** dicentang.
  3. Setelah deploy pertama dikonfirmasi admin, lakukan push uji kecil ke `main` dan pastikan delivery `200` + `https://dss-pik.stamet-rhf.com/health` mengembalikan `"database":"connected"`.
- **Konfirmasi yang Masih Dibutuhkan dari Bang Hilmi**:
  1. Konfirmasi nama volume MariaDB produksi aktual & isi tabel (`stations=57`, `cews_rainfall_daily=287,189`).
  2. Pengisian dataset operasional (`302` file, `34` Parquet, `kepri_kabkot.geojson`) ke named volume `dss_pik_data` (dengan ownership `1000:1000`).
  3. Pengiriman privat **Payload URL** dan **Webhook Secret** Coolify.
