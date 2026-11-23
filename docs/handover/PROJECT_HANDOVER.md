# PROJECT HANDOVER — DECISION SUPPORT SYSTEM PERINGATAN IKLIM (DSS-PIK)
## BMKG Stasiun Meteorologi Kelas II Raja Haji Fisabilillah Tanjungpinang
**Pedoman Resmi Serah Terima Sistem, Konsolidasi Arsitektur, dan Riwayat Progres**  
**Status**: `VERIFIED CURRENT` (November 2026)

---

## 1. IDENTITAS & LATAR BELAKANG SISTEM

- **Nama Resmi**: Decision Support System Peringatan Iklim (DSS-PIK) Kepulauan Riau
- **Pengelola Teknis**: Unit Analisis dan Informasi Iklim, BMKG Stasiun Meteorologi Kelas II Raja Haji Fisabilillah Tanjungpinang
- **Tujuan Operasional**:
  Menyediakan sistem pendukung keputusan otomatis, terukur, dan berbasis standar klimatologi operasional BMKG untuk mendeteksi secara dini dua potensi bahaya ekstrem di Provinsi Kepulauan Riau:
  1. **PDKM (Peringatan Dini Kekeringan Meteorologis)**: Mendeteksi defisit curah hujan dengan mengintegrasikan Hari Tanpa Hujan (HTH), Standardized Precipitation Index 90-Harian (SPI 90D sebagai parameter utama), dan peluang curah hujan rendah (Pb20).
  2. **PDCHT (Peringatan Dini Curah Hujan Tinggi)**: Mengantisipasi akumulasi curah hujan ekstrem dasarian dan bulanan menggunakan probabilitas prakiraan iklim ECMWF (Pa150, Pa200, Pa300, PM300, PM400, PM500) dengan ambang pemicu terstandarisasi **> 50%**.
  3. **Dual-Hazard Synthesis**: Mengintegrasikan kedua risiko ke dalam status bahaya operasional komprehensif pada 57 pos pengamatan, 59 kecamatan, dan 7 kabupaten/kota.

---

## 2. INDEKS DOKUMENTASI HANDOVER TERKONSOLIDASI

Untuk memastikan pemahaman yang menyeluruh dan tidak terjadi tumpang tindih informasi, seluruh dokumentasi handover resmi DSS-PIK telah dikonsolidasikan pada folder `docs/handover/`:

1. [PROJECT_MASTER_STATUS.md](file:///c:/LATSAR/ASLI2/docs/handover/PROJECT_MASTER_STATUS.md) — Dokumen induk status kesehatan sistem, komponen stabil, kondisi basis data, dan ringkasan eksekutif.
2. [DEVELOPMENT_HISTORY.md](file:///c:/LATSAR/ASLI2/docs/handover/DEVELOPMENT_HISTORY.md) — Kronologi lengkap fase pengembangan dari Phase 1 hingga Phase 7.2 beserta matriks progres.
3. [FEATURE_INVENTORY.md](file:///c:/LATSAR/ASLI2/docs/handover/FEATURE_INVENTORY.md) — Rincian 20 fitur aktif, alur pipeline data dari input Excel hingga output resmi.
4. [ARCHITECTURE_AND_DATA_FLOW.md](file:///c:/LATSAR/ASLI2/docs/handover/ARCHITECTURE_AND_DATA_FLOW.md) — Diagram Mermaid arsitektur berlapis, skema MariaDB, alur sequence data, generator peta, dan topologi LAN.
5. [OPEN_ISSUES_AND_ROADMAP.md](file:///c:/LATSAR/ASLI2/docs/handover/OPEN_ISSUES_AND_ROADMAP.md) — Temuan teknis, mitigasi risiko, technical debt, dan 5 rekomendasi pengembangan berikutnya.
6. [AI_BOOTSTRAP_CONTEXT.md](file:///c:/LATSAR/ASLI2/docs/handover/AI_BOOTSTRAP_CONTEXT.md) — Titik awal referensi cepat bagi developer atau AI baru untuk memahami aturan main tanpa mengulangi analisis dari awal.
7. [PHASE_7_4_FINAL_DEPLOYMENT_READINESS.md](file:///c:/LATSAR/ASLI2/docs/deployment/PHASE_7_4_FINAL_DEPLOYMENT_READINESS.md) — Laporan kesiapan serah terima teknisi IT BMKG, verifikasi backup/restore rehearsal, dan paket distribusi `releases/DSS-PIK_TECHNICIAN_HANDOVER/`.

---

## 3. ARSITEKTUR & TOPOLOGI SISTEM

```
+-----------------------------------------------------------------------------------+
|                            LAPISAN KLIEN / PRESENTASI                             |
|  React 18.3.1 (SPA) + Vite 5.4.21 + Leaflet 1.9.4                                  |
|  Theme: Cobalt Theme (Hallmark Engine) + BMKG Atmospheric Gradients               |
|  - Peta Interaktif 57 Stasiun Kepri (Leaflet Canvas/SVG Markers & Poligon Kec)     |
|  - 6 Kartu KPI Operasional (Total, Normal, Waspada, Siaga, Awas, Incomplete)      |
|  - Tabel Peringatan Dini Dinamis & Filter Dual-Hazard (PDKM / PDCHT)               |
|  - Station Detail Drawer (Analisis Multi-Indikator, Grafik SPI 90D/30D Statistik) |
|  - Data Center & Kamus Istilah Klimatologi                                        |
|  - OfficialMapModal: Generator Peta Resmi BMKG 59 Kecamatan & Ekspor JSON SIH3    |
+-----------------------------------------------------------------------------------+
                                        |  HTTP REST API (JSON)
                                        v  Port 8000 (FastAPI / Uvicorn)
+-----------------------------------------------------------------------------------+
|                             LAPISAN LOGIKA / BACKEND                              |
|  FastAPI 0.116.1 + Python 3.12.10 + Uvicorn 0.35.0 (Host: 0.0.0.0, Port: 8000)    |
|  - backend/config.py: Single Source of Truth Identitas Institusi Kelas II         |
|  - backend/main.py: Routing, State, CORS, HTTP Endpoints, Static File Serving     |
|  - backend/decision_engine.py: Evaluasi Kanonikal PDKM, PDCHT (>50%), Dual-Hazard |
|  - backend/period_service.py: Deteksi Periode Aktif & Cutoff Observasi Dinamis    |
|  - backend/regional_warning_service.py: Agregasi 59 Kecamatan & 7 Kabupaten/Kota  |
|  - backend/map_generator.py: Mesin Render Peta Resmi BMKG JPG (1653x1170 px)      |
|  - backend/spi_calculation_service.py: Loader Parquet SPI & Distribusi Terbaik   |
|  - backend/launcher.py: Process Supervisor, Port Guard, Graceful Termination     |
+-----------------------------------------------------------------------------------+
                   |                                       |
                   v (PyMySQL Driver)                      v (PyArrow / Pandas)
+------------------------------------+   +------------------------------------------+
|          DATABASE RELASIONAL       |   |             DATA OPERASIONAL             |
|  MariaDB 13.0.2 (cews_db)          |   |  Parquet Files & CSV Reference           |
|  - stations (57 Titik Aktif)       |   |  - data/raw/spi/dasarian/SPI_all_90d     |
|  - cews_rainfall_daily (287k rows) |   |  - data/raw/spi/dasarian/SPI_all_30d     |
|  - cews_forecast_snapshot (3.2k)   |   |  - data/reference/spi_distributions/     |
|  - cews_period_snapshot (570 rows) |   |  - data/reference/stations/              |
|  - cews_regional_warning_decisions |   |  - data/operational/maps/                |
+------------------------------------+   +------------------------------------------+
```

---

## 4. BASELINE DECISION ENGINE & ATURAN METEOROLOGIS (PHASE 7.2)

### A. Evaluasi PDKM (Kekeringan Meteorologis)
1. **Hari Tanpa Hujan (HTH)**:
   - `< 21 hari` = NORMAL (Level 0)
   - `21 - 30 hari` = WASPADA (Level 1)
   - `31 - 60 hari` = SIAGA (Level 2)
   - `>= 61 hari` = AWAS (Level 3)
   - *Ambang pemutus HTH*: Curah hujan harian `>= 1.0 mm`.
2. **SPI 90D (Parameter Utama PDKM)**:
   - `> -1.00` = NORMAL (0)
   - `<= -1.00` = WASPADA (1)
   - `<= -1.50` = SIAGA (2)
   - `<= -2.00` = AWAS (3)
3. **SPI 30D (Indikator Pendukung Informasional)**:
   - Tidak menaikkan atau menurunkan level PDKM.
4. **Pb20 (Peluang Curah Hujan Dasarian < 20 mm)**:
   - `<= 70%` = NORMAL (0)
   - `> 70%` = WASPADA (1). Maksimal level WASPADA.
5. **Sintesis Level PDKM**:
   $$L_{\text{PDKM}} = \max(L_{\text{HTH}}, L_{\text{SPI90D}}, L_{\text{Pb20}})$$

### B. Evaluasi PDCHT (Curah Hujan Tinggi) — Ambang > 50%
1. **Peluang Dasarian (ECMWF)**:
   - `Pa150 > 50%` $\rightarrow$ WASPADA (1)
   - `Pa200 > 50%` $\rightarrow$ SIAGA (2)
   - `Pa300 > 50%` $\rightarrow$ AWAS (3)
2. **Peluang Bulanan (ECMWF)**:
   - `PM300 > 50%` $\rightarrow$ WASPADA (1)
   - `PM400 > 50%` $\rightarrow$ SIAGA (2)
   - `PM500 > 50%` $\rightarrow$ AWAS (3)
3. **Sintesis Level PDCHT**:
   $$L_{\text{PDCHT}} = \max(L_{\text{Dasarian}}, L_{\text{Bulanan}})$$

### C. Dual-Hazard Synthesis & Aturan Kewilayahan
- Status gabungan mengambil tingkat bahaya maksimum. Jika PDKM dan PDCHT aktif sekaligus, bahaya diklasifikasikan sebagai `MULTI_HAZARD`.
- Kecamatan tanpa pos pengamatan fisik mewarisi rekomendasi dari kabupaten/kota induknya (`inherited_from_parent: true`).
- Jika kabupaten induk berstatus `INSUFFICIENT_DATA`, kecamatan tanpa stasiun wajib berstatus `INSUFFICIENT_DATA` (tidak pernah dipaksa menjadi `AMAN` palsu).

---

## 5. PROSEDUR MENJALANKAN SISTEM DI WORKSTATION BMKG

1. **Memastikan Service MariaDB Berjalan**:
   Port `3306` aktif melayani basis data `cews_db`.
2. **Menjalankan Sistem Lengkap (Mode LAN Multi-User — Single Unified Launcher)**:
   Double-click atau jalankan file batch tunggal:
   ```cmd
   DSS-PIK.bat
   ```
   *Sistem akan memeriksa/menyalakan MariaDB, memvalidasi `frontend/dist`, mendeteksi IP LAN lokal, memulai server backend pada `0.0.0.0:8000`, melakukan polling health check, dan membuka browser default Windows otomatis ke `http://127.0.0.1:8000/`. Double-click saat server aktif menampilkan menu STATUS / RESTART / STOP.*
3. **Mengakses dari Komputer Client (B dan C)**:
   Buka browser pada komputer lain dalam satu jaringan Wi-Fi/LAN dan arahkan ke alamat server:
   ```
   http://<IP_KOMPUTER_A>:8000/
   ```
4. **Menghentikan Layanan**:
   Pilih opsi `[3] Hentikan Layanan DSS-PIK (STOP)` pada menu `DSS-PIK.bat`, atau jalankan:
   ```cmd
   DSS-PIK.bat stop
   ```
5. **Menjalankan Verifikasi Regresi Menyeluruh**:
   ```cmd
   python -m pytest test_standardized_decision_json.py test_phase4_decision_engine.py test_phase41_regression.py test_phase42_consistency.py -v
   ```
   *(Seluruh 36 test harus dalam status PASSED).*

---
**Dokumen ini disahkan sebagai Pedoman Resmi Serah Terima DSS-PIK BMKG Stasiun Meteorologi Kelas II Raja Haji Fisabilillah Tanjungpinang.**


---

## Phase 8.0 Addendum — Dockerization & Three-Environment Handover (2026-11-22)

- DSS-PIK now follows the official **Development -> Staging -> Production** architecture targeting BMKG Office Ubuntu Server via versioned Docker images and Docker Compose.
- Permanent AI & developer rules are enforced in `.agents/rules/dss-pik-architecture.md`.
- See `docs/deployment/DSS_PIK_DEPLOYMENT_ARCHITECTURE.md` for Ubuntu Server deployment, offline image transfer, persistent storage, backup, upgrade, and rollback procedures.

- **Phase 8.2.2 (2026-11-23)**: Docker localhost access (`http://127.0.0.1:18000`) verified HTTP 200 via `CEWS_DOCKER_LOCAL_ONLY=true` (dynamic `/proc/net/route` exact gateway allowlist, `lan_enabled=false`, 42/42 tests passed). See `docs/deployment/PHASE_8_2_2_DOCKER_LOCALHOST_ACCESS_FIX.md`.

- **Phase 8.3 (2026-11-23)**: Final production release `v1.0.0` packaged at `F:\TNJ\paper\DSS_PIK_PRODUCTION_RELEASE` (offline Docker images, `compose.production.yaml`, DB snapshot, operational data, technician guides, `SHA256SUMS.txt`). Status: `READY FOR TECHNICIAN CONFIGURATION AND SERVER ACCEPTANCE`.
