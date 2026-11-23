# PROJECT MASTER STATUS — DSS-PIK BMKG KEPULAUAN RIAU
**Sistem Pendukung Keputusan Peringatan Dini Iklim (Decision Support System Peringatan Iklim)**  
**Institusi**: BMKG Stasiun Meteorologi Kelas II Raja Haji Fisabilillah Tanjungpinang  
**Cakupan Wilayah**: Provinsi Kepulauan Riau (59 Kecamatan, 7 Kabupaten/Kota, 57 Pos/Stasiun Pengamatan)  
**Status Audit & Konsolidasi**: `VERIFIED CURRENT` (November 2026)

---

## 1. IDENTITAS & TUJUAN UTAMA SISTEM

DSS-PIK dirancang khusus untuk memenuhi mandat BMKG dalam menyediakan peringatan dini iklim yang objektif, berbasis data terukur, dan transparan bagi para pemangku kepentingan di Provinsi Kepulauan Riau.

Sistem mendeteksi dua ancaman iklim ekstrem secara simultan:
1. **PDKM (Peringatan Dini Kekeringan Meteorologis)**:
   - Evaluasi defisit air jangka pendek hingga menengah.
   - Pemicu utama: **Hari Tanpa Hujan (HTH)**, **SPI 90D** (Standardized Precipitation Index 90 hari sebagai parameter utama), dan **Pb20** (Probabilitas Curah Hujan Dasarian < 20 mm).
2. **PDCHT (Peringatan Dini Curah Hujan Tinggi)**:
   - Evaluasi potensi curah hujan lebat hingga ekstrem berbasis model probabilistik ECMWF.
   - Pemicu: **Pa150**, **Pa200**, **Pa300** (probabilitas dasarian) serta **PM300**, **PM400**, **PM500** (probabilitas bulanan) dengan ambang pemicu terstandarisasi **> 50%**.
3. **Dual-Hazard Synthesis**:
   - Menghasilkan keputusan sintesis tingkat bahaya tertinggi (`AWAS` > `SIAGA` > `WASPADA` > `AMAN` / `INSUFFICIENT_DATA`), dengan penandaan eksplisit `MULTI_HAZARD` jika kedua ancaman aktif sekaligus.

---

## 2. STATUS SISTEM SECARA KESELURUHAN (EXECUTIVE SUMMARY)

| Dimensi | Status | Ringkasan Kondisi Aktual |
|---|:---:|---|
| **Core Decision Engine** | `VERIFIED CURRENT` | Logika dual-hazard berjalan stabil di `backend/decision_engine.py`. Threshold PDCHT telah diperbarui ke `> 50%`. SPI 90D terisolasi sebagai parameter utama PDKM. |
| **Penyimpanan Data** | `VERIFIED CURRENT` | MariaDB `13.0.2-MariaDB` (database `cews_db`) menampung 57 stasiun, 287.189 data curah hujan harian, dan snapshot operasional. Parquet (34 file) berfungsi sebagai canonical storage untuk SPI dan time series. |
| **Regional Decision & Output** | `VERIFIED CURRENT` | Standardized Decision-Based Schema (10 field root) aktif di `backend/regional_warning_service.py` untuk 59 Kecamatan dan 7 Kabupaten/Kota. Mendukung operator override tanpa merusak rekomendasi sistem. |
| **Identitas Institusi** | `VERIFIED CURRENT` | Terkunci pada *Single Source of Truth* `backend/config.py` dan `frontend/src/config.js` sebagai: **BMKG Stasiun Meteorologi Kelas II Raja Haji Fisabilillah Tanjungpinang**. |
| **Akses LAN Multi-User** | `VERIFIED CURRENT` | Server beroperasi di `0.0.0.0:8000` (FastAPI) melayani bundle frontend production (`CEWS_SERVE_FRONTEND=true`) melalui single launcher `DSS-PIK.bat`. Sesi multi-user terisolasi dengan UUID `jti` dan concurrency locks (`_CACHE_LOCK`, `_REGIONAL_WRITE_LOCK`). Verifikasi fisik lintas PC (PC B & C) memerlukan pengujian langsung di jaringan kantor + rule firewall port 8000. |
| **Generator Peta & Ekspor** | `VERIFIED CURRENT` | Peta resmi BMKG resolusi 1653x1170 px (A4 Landscape) dengan partisi 59 kecamatan dihasilkan otomatis dalam format JPG. Ekspor JSON tervalidasi skema RFC 8259 dan JSON Schema Draft 2020-12. |
| **Stabilitas & Pengujian** | `VERIFIED CURRENT` | 36 dari 36 pengujian otomatis lulus (`pytest`), ditambah isolated MariaDB restore rehearsal (12/12 tabel cocok 100%) dan isolated deployment rehearsal (`C:\DSS_PIK_REHEARSAL_TMP`). Paket handover teknisi tersedia di `releases/DSS-PIK_TECHNICIAN_HANDOVER/` (lihat [PHASE_7_4_FINAL_DEPLOYMENT_READINESS.md](file:///c:/LATSAR/ASLI2/docs/deployment/PHASE_7_4_FINAL_DEPLOYMENT_READINESS.md)). |

---

## 3. ARSITEKTUR TINGKAT TINGGI

Sistem menggunakan topologi **Local-first Client-Server with Centralized LAN Engine**:

```
[ Browser Komputer A (Server) ]    [ Browser Komputer B (Client) ]    [ Browser Komputer C (Client) ]
               \                                  |                                  /
                \---------------------------------+---------------------------------/
                                                  |
                                                  v  HTTP (Port 8000)
                    +-------------------------------------------------------------+
                    |           FASTAPI APPLICATION SERVER (Uvicorn 0.35.0)       |
                    |  - Routing & Session Auth (backend/main.py, backend/auth.py)|
                    |  - Static SPA Production Serving (frontend/dist/)           |
                    |  - Decision Engine (backend/decision_engine.py)             |
                    |  - Regional Aggregator 59 Kec (regional_warning_service.py) |
                    |  - Map & JSON Generator (map_generator.py)                  |
                    |  - Data Ingestion & SPI Service (ingestion_service.py)      |
                    +-------------------------------------------------------------+
                                      |                               |
                                      v                               v
                    +----------------------------------+  +-----------------------+
                    |    MARIADB 13.0 (cews_db)        |  |  CANONICAL PARQUET    |
                    |  - 57 stasiun metadata           |  |  - SPI Dasarian 30D   |
                    |  - 287k curah hujan harian       |  |  - SPI Dasarian 90D   |
                    |  - Snapshot periode & probabilitas| |  - SPI Harian/Bulanan |
                    |  - Keputusan & audit log wilayah |  |  - Reference bestdist |
                    +----------------------------------+  +-----------------------+
```

---

## 4. DAFTAR MODUL UTAMA & PERANANNYA

### A. Backend Python
1. **`backend/config.py`**: *Single Source of Truth* untuk nama institusi, singkatan resmi, nama sistem, dan kode provinsi Kepulauan Riau (`21`).
2. **`backend/decision_engine.py`**: Mesin evaluasi status HTH, SPI 90D, Pb20, Pa150-300, PM300-500, serta penentu status parsial/inkomplit dan dual-hazard.
3. **`backend/regional_warning_service.py`**: Agregasi bahaya tingkat 7 Kabupaten/Kota dan 59 Kecamatan, pengelolaan hierarki pewarisan keputusan induk, operator override, dan pembentukan payload JSON terstandar 10 atribut root.
4. **`backend/map_generator.py`**: Engine perender peta grafis resmi BMKG (1653x1170) dengan masker batas administrasi SHP, inset Natuna dan Anambas, serta pewarnaan akurat sesuai penetapan operator.
5. **`backend/period_service.py`**: Pengelola logika kalender dasarian, deteksi cutoff observasi tanggal 10, 20, dan akhir bulan, serta pembuatan snapshot periode.
6. **`backend/data_service.py`**: Handler data time series, ekspor template Excel dengan header identitas institusi Kelas II, dan penyaji statistik stasiun.
7. **`backend/ingestion_service.py`**: Pipeline parsing file Excel (curah hujan harian, probabilitas dasarian/bulanan, dan SPI), deteksi anomali, kalkulasi delta, validasi multi-vintage, serta atomic commit staging ke MariaDB.
8. **`backend/spi_calculation_service.py` & `spi_calculation_worker.py`**: Generator kalkulasi SPI multi-skala berbasis fitting distribusi probabilitas empiris terbaik (*best-fit distribution*).
9. **`backend/auth.py`**: Manajemen token sesi operator berbasis cookie dan header Authorization Bearer dengan proteksi brute-force.
10. **`backend/launcher.py`**: Pengawas proses Windows, pengecekan dependensi port 3306 dan 8000, serta penanganan shutdown proses secara rapi.

### B. Frontend React (SPA Production Build)
1. **`frontend/src/App.jsx`**: Controller utama dasbor, pengatur state autentikasi, filter wilayah, dan pemilih periode.
2. **`frontend/src/components/MapLeaflet.jsx`**: Visualisasi WebGIS interaktif berbasis Leaflet dengan marker stasiun dan poligon batas administrasi 59 kecamatan yang terhubung ke payload keputusan API.
3. **`frontend/src/components/HthTable.jsx`**: Tabel matriks evaluasi 57 pos pengamatan dengan status dual-hazard, HTH, SPI, dan probabilitas.
4. **`frontend/src/components/StationDetailDrawer.jsx`**: Laci analitik mendalam per stasiun yang menampilkan grafik tren SPI 30D/90D pada tab Ringkasan Statistik.
5. **`frontend/src/components/OfficialMapModal.jsx`**: Antarmuka penetapan keputusan peringatan dini tingkat kecamatan dan kabupaten/kota, kontrol override operator, pratinjau peta resmi, dan ekspor JSON.
6. **`frontend/src/components/DataCenter.jsx`**: Pusat operasional pemantauan dan pembaruan data, upload file curah hujan/probabilitas/SPI, dan generator SPI manual.
7. **`frontend/src/components/KamusPage.jsx`**: Kamus terminologi klimatologi dan panduan teknis operasional sistem.

---

## 5. KONDISI KELAYAKAN DATA & STASIUN PENGAMATAN

- **Total Stasiun Aktif**: Tepat **57 Stasiun** pengamatan yang terdaftar di MariaDB table `stations` dan metadata kanonikal.
  - Kabupaten Bintan: 16 stasiun
  - Kabupaten Natuna: 15 stasiun
  - Kabupaten Lingga: 8 stasiun
  - Kabupaten Karimun: 8 stasiun
  - Kota Tanjungpinang: 4 stasiun
  - Kota Batam: 3 stasiun
  - Kabupaten Kepulauan Anambas: 3 stasiun
- **Total Kecamatan Resmi**: **59 Kecamatan** di Provinsi Kepulauan Riau yang dipetakan secara kanonikal ke 7 Kabupaten/Kota induknya.
- **Kebijakan Kecamatan Tanpa Stasiun**: Kecamatan yang tidak memiliki pos pengamatan fisik mewarisi rekomendasi dan keputusan dari Kabupaten/Kota induk (`inherited_from_parent: true`). Apabila kabupaten induk berstatus `INSUFFICIENT_DATA`, kecamatan tersebut tetap berstatus `INSUFFICIENT_DATA` (tidak pernah dipaksa menjadi `AMAN` palsu).

---

## 6. STATUS OPERASIONAL & RISIKO UTAMA

1. **Kesiapan Workstation Server Kantor**:
   - Sistem dijalankan melalui satu launcher tunggal **`DSS-PIK.bat`** (auto-START saat OFF, menu STATUS/STOP/RESTART saat ON) pada komputer server kantor BMKG yang terhubung LAN.
   - Browser default terbuka otomatis ke `http://127.0.0.1:8000/` setelah database dan backend siap (`HTTP 200 /health`). Lihat detail pada [PHASE_7_3_UNIFIED_LAUNCHER_AND_LAN.md](file:///c:/LATSAR/ASLI2/docs/deployment/PHASE_7_3_UNIFIED_LAUNCHER_AND_LAN.md).
2. **Risiko yang Perlu Diperhatikan (Known Considerations)**:
   - *WordPress Payload Parser Compatibility*: Skema JSON terbaru menggunakan array-of-objects terstruktur pada `triggered_conditions` untuk kecamatan. Parser pihak ketiga atau plugin WordPress lama yang mengharapkan array-of-strings perlu disesuaikan atau membaca atribut `.description`.
   - *Network Security di Lingkungan LAN*: Akses LAN saat ini beroperasi pada plain HTTP port 8000. Untuk pengoperasian jangka panjang di luar Wi-Fi terisolasi kantor, disarankan memasang reverse proxy (Nginx/Caddy) dengan TLS lokal.
   - *Tabel Publikasi `cews_sih3_publications`*: Saat ini belum ada rekaman yang berstatus final `PUBLISHED` di database. Endpoint publik preview dan map export menghasilkan dokumen operasional berstatus `"Aktif"`. Begitu workflow formal (APPROVE -> PUBLISH) dieksekusi oleh pejabat berwenang, riwayat publikasi akan tersimpan di tabel ini.

---
*Dokumen ini diverifikasi secara langsung melalui inspeksi source code, pengujian test suite, dan pembacaan state MariaDB pada tanggal 22 November 2026.*


---

## Phase 8.0 Update — Official Three-Environment Architecture & Dockerization (2026-11-22)

- **Official Architecture**: Three separated environments — **Development** (Windows laptop), **Staging** (local Docker Compose / test server), **Production** (BMKG Office Ubuntu Server with Docker Engine & Compose).
- **Release Workflow**: `DEVELOP -> TEST LOCALLY -> STAGING VALIDATION -> VERSION/TAG -> APPROVED PRODUCTION DEPLOYMENT -> POST-DEPLOYMENT VERIFICATION`.
- **Persistence Policy**: Application containers are replaceable; MariaDB and canonical Parquet/spatial datasets are persistent (`docker compose down -v` prohibited for routine maintenance).
- **Docker Foundation Ready**: `Dockerfile`, `.dockerignore`, `compose.yaml` (isolated port `127.0.0.1:18000:8000`), `.env.docker.example`, and permanent rule `.agents/rules/dss-pik-architecture.md`.
- **References**: `docs/deployment/DSS_PIK_DEPLOYMENT_ARCHITECTURE.md`, `docs/deployment/DOCKERIZATION_ROADMAP.md`, `docs/deployment/PHASE_8_0_DOCKERIZATION_FOUNDATION.md`.


---

## Phase 8.2 / 8.2.1 Update — Dockerized Operational Test Verified (2026-11-22)

- **Docker Stack (`dss-pik-dev`)**: `dss-pik:0.8.2-dev` + `mariadb:11.4` built and running in Ubuntu-24.04 (WSL2), both **`healthy`**.
- **Database & Regression**: All 5 baseline table counts verified (`57 / 287,189 / 3,244 / 42 / 462`), **36/36 pytest tests PASSED** inside `dss_pik_dev_app`, and restart persistence verified (`docker compose restart` without `-v`).
- **Known Docker Finding**: Host requests on `127.0.0.1:18000` arrive via Docker bridge NAT (`172.18.0.1`) and are blocked (`403`) by `lan_access_policy.json` (`enabled: false`); tracked for Phase 8.2.2.
- **Reports**: `docs/deployment/PHASE_8_2_DOCKERIZED_OPERATIONAL_TEST.md`, `docs/deployment/PHASE_8_2_1_DOCKER_BUILD_RECOVERY.md`.


### Phase 8.2.2 Update — Docker Localhost Access Verified (2026-11-23)
- Implemented `CEWS_DOCKER_LOCAL_ONLY=true` in `backend/lan_firewall_service.py` using dynamic `/proc/net/route` exact gateway detection (`172.19.0.1`). `lan_enabled` remains `false`, host port remains `127.0.0.1:18000:8000`, and `X-Forwarded-For` cannot bypass the guard.
- Verified Windows host `http://127.0.0.1:18000/health`, `/`, JS/CSS assets, and `/api/v1/geo/layers/kabkot` all return **HTTP 200**, with **42/42 tests PASSED** (`36` regression + `6` security tests in `test_phase822_docker_local_security.py`).
- Report: `docs/deployment/PHASE_8_2_2_DOCKER_LOCALHOST_ACCESS_FIX.md`.


### Phase 8.3 Update — Production Release `v1.0.0` Packaged (2026-11-23)
- Built and exported offline-ready production release package at `F:\TNJ\paper\DSS_PIK_PRODUCTION_RELEASE` (`dss-pik:1.0.0` `301 MB` + `mariadb:11.4` `98 MB`, `compose.production.yaml`, `.env.production.example`, `RESTRICTED_cews_db_release_20261123.sql`, `302` operational data files + `SHA256SUMS.txt`, and full BMKG IT technician guides).
- Status: **`READY FOR TECHNICIAN CONFIGURATION AND SERVER ACCEPTANCE`**. Report: `docs/deployment/PHASE_8_3_FINAL_PRODUCTION_PACKAGING.md`.


### Phase 8.4 Update — Split 3-Container Architecture & CI/CD Verified (2026-11-23)
- Implemented split 3-container architecture (`frontend` Nginx -> `backend` FastAPI -> `mariadb` 11.4) with `frontend/Dockerfile`, `frontend/nginx.conf`, `backend/Dockerfile`, root `compose.yaml`, `CEWS_TRUSTED_PROXY_CIDRS` security middleware, `.github/workflows/deploy.yml`, and server handover package `F:\TNJ\paper\DSS_PIK_SERVER_DEPLOYMENT`.
- Verified isolated split stack on `:28080`: **47/47 tests PASSED** (`36` regression + `11` security tests), all HTTP/branding/WebGIS endpoints **HTTP 200**, and restart persistence verified.
- Report: `docs/deployment/PHASE_8_4_FINAL_GITHUB_AND_SPLIT_ARCHITECTURE.md`.
