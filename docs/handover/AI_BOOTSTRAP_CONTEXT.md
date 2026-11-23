# AI BOOTSTRAP CONTEXT — DSS-PIK BMKG KEPULAUAN RIAU
**Konteks Ringkas & Pedoman Wajib untuk AI Developer / Engineer Baru**  
**Institusi**: BMKG Stasiun Meteorologi Kelas II Raja Haji Fisabilillah Tanjungpinang  
**Status**: `VERIFIED CURRENT` (November 2026)

---

> **INSTRUKSI EKSPLISIT UNTUK AI AGENT / DEVELOPER BARU:**  
> Anda sedang melanjutkan pemeliharaan dan pengembangan **Decision Support System Peringatan Iklim (DSS-PIK)**.  
> Sistem ini telah melalui fase pematangan intensif dari Phase 1 hingga Phase 7.2.  
> **DILARANG MENGUBAH LOGIKA DASAR DECISION ENGINE, DATABASE, MAUPUN IDENTITAS RESMI TANPA PERMINTAAN TERTULIS.**  
> Selalu baca dokumen di `docs/handover/` sebelum melakukan perubahan kode.

---

## 1. IDENTITAS SISTEM & SINGLE SOURCE OF TRUTH

- **Nama Sistem**: Decision Support System Peringatan Iklim (DSS-PIK) Kepulauan Riau
- **Institusi Resmi**: **BMKG Stasiun Meteorologi Kelas II Raja Haji Fisabilillah Tanjungpinang**
- **Single Source of Truth Identitas**:
  - Backend: `backend/config.py` (`INSTITUTION_NAME`, `INSTITUTION_SHORT_NAME`, `SYSTEM_NAME`)
  - Frontend: `frontend/src/config.js` (`INSTITUTION_NAME`, `INSTITUTION_SHORT_NAME`)
  - JSON Schema: `docs/schemas/sih3_regional_warning.schema.json`
- **Cakupan Wilayah**: Provinsi Kepulauan Riau (59 Kecamatan, 7 Kabupaten/Kota, 57 Pos Pengamatan Aktif)

---

## 2. MODUL PENTING & LOKASINYA

```
c:\LATSAR\ASLI2\
├── backend/
│   ├── config.py                   # Single Source of Truth Identitas Institusi
│   ├── main.py                     # API Router, Session Auth, Static SPA Server
│   ├── decision_engine.py          # Logika Evaluasi Stasiun (HTH, SPI 90D, Pb20, Pa/PM > 50%)
│   ├── regional_warning_service.py # Agregasi 59 Kecamatan & 7 Kab/Kota, Serializer JSON 10 Kunci
│   ├── map_generator.py            # Generator Peta Resmi BMKG JPG (1653x1170 px)
│   ├── period_service.py           # Resolver Kalender Dasarian & Cutoff Waktu
│   ├── data_service.py             # Data Center Handler, Ekspor Excel Ber-header Resmi
│   ├── ingestion_service.py        # Pipeline Parsing Excel, Delta Staging, Atomic Commit
│   └── spi_calculation_service.py  # Perhitungan SPI & Loader Parquet
├── frontend/src/
│   ├── App.jsx                     # Root Controller Dasbor
│   ├── config.js                   # Konfigurasi API Base URL & Identitas Institusi
│   ├── cobalt-theme.css            # Desain Sistem Cobalt Theme & Gradien BMKG
│   └── components/
│       ├── MapLeaflet.jsx          # Peta Interaktif 57 Stasiun & Poligon Kecamatan
│       ├── HthTable.jsx            # Tabel Peringatan Dini Stasiun
│       ├── StationDetailDrawer.jsx # Laci Analitik Stasiun (Grafik Tren SPI di Ringkasan Statistik)
│       ├── OfficialMapModal.jsx    # Modal Penetapan Peringatan 59 Kecamatan & Ekspor Peta/JSON
│       └── DataCenter.jsx          # Pusat Monitoring, Input Data, & SPI Generator
├── data/
│   ├── raw/spi/dasarian/           # Canonical Parquet SPI 30D & 90D
│   ├── operational/maps/           # Arsip JSON & Peta Operasional
│   └── reference/stations/         # Metadata Stasiun
├── docs/handover/                  # Seluruh Dokumentasi Handover Resmi
├── docs/deployment/                # Laporan Deployment (termasuk Phase 7.3, 7.3.1, 7.4)
├── scripts/dss_pik_firewall.ps1    # Pengelola Rule Firewall Scoped 'DSS-PIK - LAN Access'
├── config/lan_access_policy.json   # Kebijakan Akses LAN Portabel (tanpa secret)
└── DSS-PIK.bat                     # Single Unified Operational Launcher (START/STOP/RESTART/STATUS/LAN)
```

---

## 3. ATURAN BAKU DECISION ENGINE (BASELINE PHASE 7.2)

### A. PDKM (Kekeringan Meteorologis)
1. **HTH (Hari Tanpa Hujan)**:
   - `< 21 hari` = NORMAL (0)
   - `21 - 30 hari` = WASPADA (1)
   - `31 - 60 hari` = SIAGA (2)
   - `>= 61 hari` = AWAS (3)
   - *Ambang pemutus HTH*: Curah hujan harian `>= 1.0 mm`.
2. **SPI 90D (Parameter Utama PDKM)**:
   - `> -1.00` = NORMAL (0)
   - `<= -1.00` = WASPADA (1)
   - `<= -1.50` = SIAGA (2)
   - `<= -2.00` = AWAS (3)
3. **SPI 30D (Indikator Pendukung Informasional)**:
   - **TIDAK BOLEH** menaikkan atau menurunkan level PDKM sintesis.
4. **Pb20 (Peluang Curah Hujan Dasarian < 20 mm)**:
   - `<= 70%` = NORMAL (0)
   - `> 70%` = WASPADA (1) *(Maksimal level WASPADA; tidak pernah memicu SIAGA/AWAS)*.
5. **Sintesis Level PDKM**:
   $$\text{Level}_{\text{PDKM}} = \max(\text{Level}_{\text{HTH}}, \text{Level}_{\text{SPI90D}}, \text{Level}_{\text{Pb20}})$$

### B. PDCHT (Curah Hujan Tinggi) — Ambang > 50%
1. **Dasarian (ECMWF)**:
   - `Pa150 > 50%` = WASPADA (1)
   - `Pa200 > 50%` = SIAGA (2)
   - `Pa300 > 50%` = AWAS (3)
2. **Bulanan (ECMWF)**:
   - `PM300 > 50%` = WASPADA (1)
   - `PM400 > 50%` = SIAGA (2)
   - `PM500 > 50%` = AWAS (3)
3. **Sintesis Level PDCHT**:
   $$\text{Level}_{\text{PDCHT}} = \max(\text{Level}_{\text{Dasarian}}, \text{Level}_{\text{Bulanan}})$$

### C. Dual-Hazard Synthesis & Wilayah
- Status `final_status` stasiun/wilayah mengambil level tertinggi antara PDKM dan PDCHT.
- Jika kedua bahaya aktif bersamaan, `hazard_type` wajib diset `"MULTI_HAZARD"`.
- Kecamatan tanpa stasiun **mewarisi keputusan kabupaten/kota induk** (`inherited_from_parent: true`).
- Jika kabupaten induk berstatus `INSUFFICIENT_DATA`, kecamatan tanpa stasiun **wajib tetap** `INSUFFICIENT_DATA` (tidak boleh diubah otomatis menjadi `AMAN`).

---

## 4. KONTRAK DATA JSON TERSTANDAR (10 KUNCI ROOT)

Dokumen JSON utama (`build_sih3_publication_json` dan `build_map_modal_sih3_json`) memiliki struktur ketat:
1. `schema_version`: `"1.0.0"`
2. `system`: `"DSS-PIK"`
3. `institution`: `"BMKG Stasiun Meteorologi Kelas II Raja Haji Fisabilillah Tanjungpinang"`
4. `publication`: metadata publikasi (10 atribut: `publication_id`, `revision`, `status`, `generated_at`, `published_at`, `valid_from`, `valid_until`, `approved_by`, `published_by`, `revision_reason`)
5. `source`: periode evaluasi, tanggal cutoff, dan identitas sistem
6. `generated_at`: ISO-8601 dengan zona waktu WIB (`+07:00`)
7. `period`: `resolution`, `year`, `month`, `dasarian`, `label`, `valid_from`, `valid_until`
8. `province`: `code` ("21"), `name` ("Kepulauan Riau")
9. `kecamatan`: daftar array 59 kecamatan (masing-masing 11 atribut)
10. `regions`: daftar array 7 kabupaten/kota (masing-masing 12 atribut)

*Dilarang menambahkan atribut terlarang root `stations` atau `data_completeness`.*

---

## 5. CARA MENJALANKAN SISTEM & TESTING

1. **Menjalankan Sistem & Mengelola LAN**:
   ```cmd
   DSS-PIK.bat
   ```
   *(Double-click saat OFF otomatis START; double-click saat ON membuka menu `DSS-PIK SYSTEM MANAGER` untuk STATUS, STOP, RESTART, ENABLE/DISABLE LAN, dan LAN DIAGNOSTICS.)*
2. **Menghentikan Server via CLI**:
   ```cmd
   DSS-PIK.bat stop
   ```
3. **Menjalankan Seluruh Regression Test**:
   ```cmd
   python -m pytest test_standardized_decision_json.py test_phase4_decision_engine.py test_phase41_regression.py test_phase42_consistency.py -v
   ```
   *(Harus menghasilkan 36 passed).*

---

## 6. LANGKAH PERTAMA UNTUK MELANJUTKAN PENGEMBANGAN

1. Periksa `docs/handover/PROJECT_MASTER_STATUS.md` untuk gambaran umum sistem.
2. Periksa `docs/handover/OPEN_ISSUES_AND_ROADMAP.md` untuk rekomendasi pengembangan yang direncanakan.
3. Selalu jalankan regression test sebelum dan sesudah melakukan perubahan.
4. Jangan pernah mengubah logika inti klimatologi tanpa arahan resmi dari BMKG.


---

## Phase 8.0 Bootstrap Context — Mandatory Architecture Rules (2026-11-22)

- **Always obey** `.agents/rules/dss-pik-architecture.md`:
  1. Preserve the Three-Environment Architecture (**Development -> Staging -> Production**).
  2. Never bake `.env`, secrets, SQL dumps, or large canonical datasets into Docker images or Git.
  3. Never run `docker compose down -v` during routine maintenance.
  4. Never hardcode host paths or server IPs; keep MariaDB internal-only.
  5. Preserve validated scientific calculation rules and the 34 canonical Parquet files.
- **Active Local Workspace**: `F:\TNJ\paper\DSS_PIK_MIGRATION_EXPORT\ASLI2` (native `.venv` + `cews_db_migration_test` on `:8000`; isolated Docker Compose configured for `:18000`).

- **Docker Dev Instance (Phase 8.2.2)**: Running & verified at `http://127.0.0.1:18000/` (`dss-pik-dev`, `CEWS_DOCKER_LOCAL_ONLY=true`, `lan_enabled=false`, 42/42 tests passed) alongside native DSS-PIK at `http://127.0.0.1:8000/`.

- **Production Release `v1.0.0` (Phase 8.3)**: Packaged at `F:\TNJ\paper\DSS_PIK_PRODUCTION_RELEASE` (`READY FOR TECHNICIAN CONFIGURATION AND SERVER ACCEPTANCE`). `compose.production.yaml` enforces `CEWS_DOCKER_LOCAL_ONLY=false` and internal-only MariaDB.
