# DOKUMEN SERAH TERIMA PROYEK & TRANSFER PENGETAHUAN
# (PROJECT HANDOVER & KNOWLEDGE TRANSFER DOCUMENT)
## CLIMATE EARLY WARNING SYSTEM (CEWS) BMKG
**Wilayah:** Provinsi Kepulauan Riau (Tanjungpinang, Batam, Bintan, Karimun, Lingga, Natuna, Anambas)  
**Dasar Regulasi:** Peraturan BMKG Nomor 9 Tahun 2019 tentang Penyediaan dan Penyebaran Peringatan Dini Iklim Ekstrem  
**Target Pembaca:** Penanggung Jawab / PIC Baru, Tim Data Science, Forecaster BMKG, dan Software Engineer  
**Status Workspace:** Siap Operasional (*Operational & Historical Ready* - 100% QC Passed)  
**Versi Dokumen:** 2.0 (Revisi Arsitektur Operasional Lifetime)  
**Tanggal Penyusunan:** Oktober 2026  

---

# DAFTAR ISI

1. [EXECUTIVE SUMMARY](#1-executive-summary)
2. [PERJALANAN PROYEK DARI AWAL SAMPAI UPDATE TERAKHIR](#2-perjalanan-proyek-dari-awal-sampai-update-terakhir)
3. [STATUS PROYEK TERKINI](#3-status-proyek-terkini)
4. [ARSITEKTUR SISTEM](#4-arsitektur-sistem)
5. [STRUKTUR DIREKTORI & INVENTARISASI ARTEFAK](#5-struktur-direktori--inventarisasi-artefak)
6. [TEKNOLOGI DAN DEPENDENSI](#6-teknologi-dan-dependensi)
7. [DATABASE DAN DATA MODEL (DATA DICTIONARY LENGKAP)](#7-database-dan-data-model-data-dictionary-lengkap)
8. [HUBUNGAN ANTAR DATA (ERD TEKSTUAL & RELASI)](#8-hubungan-antar-data-erd-tekstual--relasi)
9. [DATA PALING PENTING / SOURCE OF TRUTH](#9-data-paling-penting--source-of-truth)
10. [DATA FLOW & SKENARIO EKSEKUSI](#10-data-flow--skenario-eksekusi)
11. [BUSINESS RULES & REGULASI BMKG NO. 9 TAHUN 2019](#11-business-rules--regulasi-bmkg-no-9-tahun-2019)
12. [API / ENDPOINT (STATUS & RANCANGAN)](#12-api--endpoint-status--rancangan)
13. [AUTENTIKASI & OTORISASI (STATUS & RANCANGAN)](#13-autentikasi--otorisasi-status--rancangan)
14. [FRONTEND & DASHBOARD AS DECISION SUPPORT SYSTEM](#14-frontend--dashboard-as-decision-support-system)
15. [INTEGRASI EKSTERNAL & DATA INGESTION](#15-integrasi-eksternal--data-ingestion)
16. [ENVIRONMENT, KONFIGURASI, & RUNBOOK OPERASIONAL](#16-environment-konfigurasi--runbook-operasional)
17. [PANDUAN KHUSUS & CHECKLIST UNTUK PIC BARU](#17-panduan-khusus--checklist-untuk-pic-baru)

---

# 1. EXECUTIVE SUMMARY

### 1.1 Identitas dan Tujuan Proyek
Proyek **Climate Early Warning System (CEWS)** adalah sistem otomasi pemantauan, analisis, dan peringatan dini iklim ekstrem berbasis aturan resmi **Peraturan BMKG Nomor 9 Tahun 2019**. Sistem ini dikembangkan untuk mencakup 57 titik stasiun observasi meteorologi, klimatologi, dan pos hujan kerja sama yang tersebar di wilayah kepulauan Provinsi Kepulauan Riau (Kota Tanjungpinang, Kota Batam, Kabupaten Bintan, Kabupaten Karimun, Kabupaten Lingga, Kabupaten Natuna, dan Kabupaten Kepulauan Anambas).

### 1.2 Masalah yang Diselesaikan
Sebelum adanya CEWS, penyusunan informasi peringatan dini kekeringan meteorologis dan curah hujan tinggi dilakukan melalui proses manual yang terfragmentasi:
1. Data curah hujan harian dari observasi pos hujan harus dihitung manual deret keringnya (Hari Tanpa Hujan / HTH).
2. Data indeks kekeringan bulanan (*Standardized Precipitation Index* / SPI) tersimpan dalam format berkas *spreadsheet* Excel terpisah dengan skema penamaan stasiun yang sering kali tidak konsisten.
3. Prakiraan peluang curah hujan deterministik dan probabilistik dari model global (ECMWF) terbit setiap dasarian dalam puluhan lembar kerja (*sheet*) Excel yang rawan terlewat oleh petugas prakirawan (*forecaster*).
4. Penentuan status (Normal, Waspada, Siaga, Awas) rawan bias subjektif dan membutuhkan waktu komputasi yang lama sebelum diseminasi ke BPBD dan pemerintah daerah.

### 1.3 Pengguna dan Pemangku Kepentingan Utama (Stakeholders)
- **Prakirawan BMKG (Forecasters on Duty):** Pengguna utama antarmuka sistem sebagai *Decision Support System* (DSS).
- **Kepala Stasiun BMKG:** Penanggung jawab verifikasi dan legalitas rilis informasi peringatan dini iklim.
- **BPBD Provinsi & Kabupaten/Kota:** Penerima informasi peringatan dini untuk kesiapsiagaan bencana hidrometeorologi.
- **Dinas Pertanian & Ketahanan Pangan:** Pemanfaat data prospek ketersediaan air tanah bagi jadwal tanam.
- **Masyarakat Luas:** Penerima manfaat akhir mitigasi risiko kekeringan dan banjir.

### 1.4 Pendekatan Arsitektur: *Regulation-Based Hybrid Rule Engine*
CEWS **BUKAN** sistem *Machine Learning*, sistem *Scoring* tertimbang (*weighted scoring*), ataupun sistem *black-box*. Sistem ini dibangun menggunakan pendekatan **Regulation-Based Hybrid Rule Engine yang Deterministik**. Setiap penetapan status (WASPADA, SIAGA, AWAS) memiliki dasar klausul aturan yang tegas, dapat diverifikasi secara ilmiah (*explainable*), dan diaudit sesuai hukum meteorologi Indonesia.

### 1.5 Kondisi Terkini dan Tingkat Kesiapan Sistem
- **Tingkat Kesiapan:** **Data Pipeline & Decision Engine Layer 100% Selesai dan Tervalidasi (Status: GREEN).**
- **Dual-Layer Architecture:** Sistem telah berhasil dipisahkan menjadi dua mode independen:
  1. *Historical Analytical Layer* (`cews_warning_history.parquet`): Berisi 2.052 baris rekam jejak dasarian tahun 2025 (57 stasiun × 36 dasarian) untuk keperluan riset, audit, dan evaluasi verifikasi.
  2. *Operational Current Warning Layer* (`cews_current_warning.parquet`): Berisi tepat 57 baris (1 status aktif per stasiun) yang berorientasi ke depan (*forward-looking*) menuju target Dasarian 1 Januari 2026.
  3. *Forecast Lineage Snapshot* (`cews_forecast_snapshot.parquet`): Berisi 1.040 baris rekaman pembuktian asal-usul data prakiraan model yang melandasi keputusan.
- **Komponen Selanjutnya (Roadmap):** Perancangan skema relasional MariaDB/MySQL, pembuatan API REST/GeoJSON, dan antarmuka Web GIS Dashboard.

---

# 2. PERJALANAN PROYEK DARI AWAL SAMPAI UPDATE TERAKHIR

> **Catatan Bukti Git:** Berdasarkan penelusuran artefak direktori, workspace ini dikelola secara lokal pada path `f:\TNJ\paper\DATA_ANALISIS_PRAKIRAAN\CEWS\MAS_HAYU\ASLI` tanpa inisialisasi `.git` aktif di direktori kerja saat ini. Oleh karena itu, rekonstruksi perjalanan proyek berikut disusun berdasarkan bukti historis stempel waktu berkas sistem (*filesystem timestamps*), jejak eksekusi log, dokumen audit teknis, serta evolusi skrip Python dari fase data preparation hingga keputusan operasional.

```
Kronologi Pembangunan CEWS:
[Sept 2026] Raw Data Ingestion (observation_daily, final_rainfall_daily, station_metadata)
    ↓
[Okt 2026] Fase 1: Integrasi Data Harian & Spasial (prepare_cews_data.py -> cews_integrated_2021_2025.parquet)
    ↓
[Okt 2026] Fase 2: Pembangunan Modul HTH (generate_hth_pipeline.py -> hth_daily_2021_2025.parquet)
    ↓
[Okt 2026] Fase 3: Integrasi SPI & Mapping 3-Level (generate_spi_pipeline.py -> spi_cews_2021_2025.parquet)
    ↓
[Okt 2026] Fase 4: Modul Probabilitas ECMWF Dasarian & Bulanan (generate_probability_pipeline.py)
    ↓
[Okt 2026] Fase 5: CEWS Indicator Pipeline (generate_cews_indicator_pipeline.py -> cews_indicator_dataset.parquet)
    ↓
[Okt 2026] Fase 6: Dual-Layer Decision Engine & Operasionalisasi (generate_cews_decision_engine.py)
```

---

## Fase 1 — Inisialisasi Proyek dan Integrasi Data Dasar
- **Periode Waktu:** Akhir September 2026 – 6 Oktober 2026.
- **Tujuan:** Mengonsolidasikan data curah hujan harian hasil koreksi satelit CHIRPS dengan buku induk metadata stasiun BMKG untuk rentang 2021–2025.
- **Artefak Utama Dibuat:**
  - `station_metadata.parquet` (Buku Induk: 57 stasiun, ID, Nama, Lat, Lon, Elevasi, Kabupaten, Provinsi).
  - `final_rainfall_daily.parquet` (283.450 baris data observasi harian terkoreksi).
  - `prepare_cews_data.py` (Skrip ETL tahap pertama).
  - `cews_integrated_2021_2025.parquet` (Hasil penggabungan: 98.684 baris curah hujan harian berkoordinat).
- **Keputusan Teknis Penting:**
  1. *Standarisasi ID Stasiun:* Menggunakan normalisasi `.str.upper()` pada `station_id` untuk menghindari hilangnya data akibat ketidaksesuaian huruf kapital.
  2. *Left Join:* Data hujan menjadi tabel utama (*left table*), sehingga seluruh rekaman observasi tetap dipertahankan meski metadata stasiun baru ditambahkan kemudian.

---

## Fase 2 — Pembangunan Engine Hari Tanpa Hujan (HTH)
- **Periode Waktu:** 6 Oktober 2026.
- **Tujuan:** Mengimplementasikan kalkulasi sekuensial deret Hari Tanpa Hujan (HTH) sesuai kaidah klimatologi BMKG secara matematis dan vektor.
- **Artefak Utama Dibuat:**
  - `generate_hth_pipeline.py` (Engine HTH).
  - `hth_daily_2021_2025.parquet` (98.684 baris hasil kalkulasi HTH harian).
  - `hth_qc_report.txt` (Laporan kendali mutu HTH).
- **Logika Bisnis & Algoritma:**
  - Hari Hujan didefinisikan jika akumulasi $CH \ge 1.0\text{ mm/hari}$.
  - Hari Kering didefinisikan jika $CH < 1.0\text{ mm/hari}$. Counter bertambah $+1$.
  - Jika terjadi hari hujan ($CH \ge 1.0\text{ mm}$), counter HTH di-reset kembali ke `0`.
- **Inovasi Data Quality (Uncertainty Handling):**
  - Jika terjadi kekosongan data observasi (*missing value* / $CH = \text{NaN}$), nilai HTH tidak ditebak/diinterpolasi.
  - Nilai HTH disuntikkan `NaN`, flag `hth_valid = False`, dan flag `hth_uncertain = True`.
  - Ketidakpastian diteruskan ke hari-hari berikutnya hingga hari hujan terkonfirmasi, mencegah sistem merilis peringatan palsu akibat alat observasi rusak.

---

## Fase 3 — Ekstraksi SPI dan Rekayasa Resolusi Spasial 3-Level
- **Periode Waktu:** 7 Oktober 2026.
- **Tujuan:** Mengekstrak indeks kekeringan jangka panjang bulanan (SPI-1, SPI-3) dari berkas Excel tahun 2021–2025 dan menyelesaikan perbedaan nama stasiun lintas divisi BMKG.
- **Artefak Utama Dibuat:**
  - `generate_spi_pipeline.py` (Engine ekstraksi SPI multi-sheet).
  - `mapping_tambahan.xlsx` (Kamus alias pemetaan stasiun).
  - `spi_cews_2021_2025.parquet` (5.170 baris data SPI analisis dan prakiraan).
  - `hth_monthly_snapshot_2021_2025.parquet` (3.249 baris snapshot HTH akhir bulan).
  - `drought_monitoring_analysis_2021_2025.parquet` (Tabel gabungan HTH snapshot + SPI).
  - `STATION_MAPPING_AUDIT.md` (Dokumentasi audit rekonsiliasi spasial stasiun).
- **Masalah Kritis Ditemukan & Dipecahkan:**
  - Berkas Excel SPI menggunakan penamaan bervariasi (contoh: "Stasiun Meteorologi RHF Tanjungpinang" atau "00096091a") yang tidak cocok dengan ID master ("21720201A").
  - Dibangun algoritma **3-Level Resolution Mapping**:
    1. *Exact Match:* Pencocokan langsung normalized ID.
    2. *Reference Match:* Pencocokan string nama stasiun menggunakan kamus `mapping_tambahan.xlsx`.
    3. *Spatial Haversine Match:* Pencocokan koordinat geografis jika jarak $< 1.0\text{ km}$.
  - Dari 57 stasiun master: 39 *exact match*, 7 terselamatkan lewat kamus referensi, 3 terselamatkan lewat koordinat Haversine, 5 stasiun tidak memiliki data SPI dari BMKG Pusat (diberi status transparan `TRUE_SPI_NOT_AVAILABLE`, tidak di-drop).

---

## Fase 4 — Ekstraksi Probabilitas Curah Hujan ECMWF
- **Periode Waktu:** 9 – 13 Oktober 2026.
- **Tujuan:** Mengotomatisasi ekstraksi peluang curah hujan probabilistik luaran model ECMWF tingkat dasarian dan bulanan dari 45+ berkas Excel.
- **Artefak Utama Dibuat:**
  - `generate_probability_pipeline.py` (Engine dasarian).
  - `generate_probability_monthly_pipeline.py` (Engine bulanan).
  - `probability_rainfall_dasarian_2025.parquet` (19.610 baris data probabilitas dasarian).
  - `probability_rainfall_monthly_2021_2025.parquet` (14.840 baris data probabilitas bulanan).
- **Logika Bisnis:**
  - Memisahkan secara ketat `issue_date` (tanggal saat model di-run oleh ECMWF/BMKG) dengan `target_start_date` dan `target_end_date` (periode kejadian yang diprakirakan).
  - Ekstraksi sheet:
    - `pb50` / `pb20`: *Probability Below* (indikator potensi defisit/kekeringan).
    - `pa50`, `pa150`, `pa200`, `pa300`: *Probability Above* dasarian (indikator curah hujan tinggi/ekstrem).
    - `pa400`, `pa500`: *Probability Above* bulanan (indikator curah hujan tinggi bulanan).

---

## Fase 5 — Pembangunan CEWS Indicator Pipeline
- **Periode Waktu:** 13 Oktober 2026.
- **Tujuan:** Menyatukan seluruh modul indikator (HTH, SPI, Probabilitas Dasarian, Probabilitas Bulanan, dan Metadata Spasial) ke dalam satu matriks agregasi beresolusi Dasarian (1–10, 11–20, 21–akhir bulan).
- **Artefak Utama Dibuat:**
  - `pipeline/generate_cews_indicator_pipeline.py`.
  - `config/cews_config.yaml`.
  - `cews_indicator_dataset.parquet` (2.052 baris: 57 stasiun × 36 dasarian tahun 2025).
  - `output/cews_indicator_qc_report.txt` (Kendali mutu integritas indikator: 0 duplikasi, probabilitas dalam batas 0–100%).
- **Bug Kritis yang Diperbaiki pada Fase Ini:**
  - *Bug Pemetaan Kolom Probabilitas:* Sebelumnya terjadi pemetaan kolom yang mengembalikan seluruh nilai NaN pada parameter probabilitas dasarian. Dilakukan refactor pada skrip parser sehingga nilai probabilitas terpetakan presisi ke kolom `prob_below20`, `prob_above150`, `prob_above200`, `prob_above300`.
  - *Bug Inkonsistensi Header Kabupaten:* Terjadi perbedaan penamaan `kab_kota` vs `regency` vs `kabupaten` di metadata, dipecahkan melalui mekanisme *fallback* bertingkat pada skrip pipeline.

---

## Fase 6 — Redesign Arsitektur Operasional Lifetime (Fase Terakhir)
- **Periode Waktu:** 13 – 15 Oktober 2026.
- **Tujuan:** Mengubah arsitektur sistem dari yang semula hanya berorientasi analisis masa lalu (*backtesting*) menjadi **Sistem Peringatan Dini Operasional Aktif (Lifetime Operational Early Warning System)** yang siap melayani dashboard BMKG.
- **Artefak Utama Dibuat:**
  - `generate_cews_decision_engine.py` (Engine keputusan multi-mode).
  - `cews_rules.xlsx` (Konfigurasi aturan regulasi BMKG transparan dalam format Excel 4 sheet).
  - `cews_warning_history.parquet` (2.052 baris histori analitik dasarian 2025).
  - `cews_current_warning.parquet` (57 baris status aktif terkini, persis 1 baris per stasiun untuk periode masa depan).
  - `cews_forecast_snapshot.parquet` (1.040 baris jejak audit ECMWF).
  - `cews_decision_qc_report.txt` & `cews_operational_qc_report.txt` (Laporan QC otomatis: 100% PASS).
  - `CEWS_PROJECT_MEMORY_DOCUMENTATION.md` (Dokumentasi memori proyek diperbarui).

---

# 3. STATUS PROYEK TERKINI

### 3.1 Komponen yang Sudah Selesai dan Stabil (Production-Ready)
1. **Engine Pembersihan & Integrasi Metadata Spasial:** Normalisasi 57 stasiun BMKG dan pos hujan kerja sama di Kepulauan Riau (`station_metadata.parquet`, `mapping_tambahan.xlsx`).
2. **Engine Hari Tanpa Hujan (HTH):** Kalkulasi streak harian, reset otomatis, pelacakan ketidakpastian data observasi (`hth_daily_2021_2025.parquet`).
3. **Engine Ekstraksi SPI Bulanan:** Parser berkas Excel SPI BMKG Pusat tahun 2021–2025 dengan resolusi spasial 3-level (`spi_cews_2021_2025.parquet`).
4. **Engine Ekstraksi Probabilitas ECMWF:** Parser puluhan sheet Excel peluang curah hujan dasarian dan bulanan (`probability_rainfall_dasarian_2025.parquet`, `probability_rainfall_monthly_2021_2025.parquet`).
5. **CEWS Indicator Pipeline:** Konsolidator matriks dasarian standar dengan kendali mutu otomatis (`cews_indicator_dataset.parquet`).
6. **Dual-Layer Decision Engine:** Evaluator regulasi Peraturan BMKG No. 9 Tahun 2019 dengan pemisahan tabel histori dan tabel operasional aktif (`generate_cews_decision_engine.py`).
7. **Audit & Quality Control System:** Script validator integritas data yang menghasilkan laporan kelayakan sistem secara otomatis (`cews_operational_qc_report.txt`).

### 3.2 Komponen yang Sudah Dibuat Tetapi Perlu Penyesuaian Saat Deployment
- **Konfigurasi Operasional Real-time (`config/cews_config.yaml`):** Saat ini disetel pada mode `backtest` untuk validasi tahun 2025. Ketika data harian tahun 2026 dimasukkan, konfigurasi perlu dialihkan ke mode `operational`.
- **Pemberian Izin Eksekusi Shell di Server Linux/Container:** Sistem saat ini berjalan di Windows dengan bantuan wrapper `powershell.cmd`. Ketika dideploy ke server produksi (Ubuntu/Debian BMKG), skrip dapat dieksekusi langsung via bash/python standar.

### 3.3 Komponen yang Sedang Berjalan Menuju Fase Berikutnya
- **Persiapan Skema Relasional Database (MariaDB/MySQL):** Memetakan struktur Parquet ke dalam skema Data Definition Language (DDL) `.sql` untuk melayani kebutuhan query API web dashboard.

### 3.4 Komponen yang Belum Dikerjakan (Direncanakan Sesuai Batasan)
Sesuai batasan eksplisit dari stakeholder, modul berikut memang belum dibangun dan menjadi agenda tahap berikutnya:
1. **RDBMS Database Instance:** Pembuatan instance aktif MariaDB/MySQL.
2. **Backend API Service:** Endpoint REST API (FastAPI / Express / Laravel) dan GeoJSON service.
3. **Web GIS Dashboard UI:** Tampilan visual peta interaktif (Leaflet / Mapbox / OpenLayers) untuk prakirawan BMKG.

### 3.5 Analisis Technical Debt & Potensi Risiko
| Kategori | Temuan Fakta di Kode | Potensi Risiko | Rekomendasi Solusi untuk PIC Baru |
|:---|:---|:---|:---|
| **Penyimpanan Ganda** | File Parquet disimpan ganda di root workspace dan folder `output/` | Redundansi kapasitas disk (meski ukuran Parquet sangat kecil <50MB) | Pertahankan sinkronisasi ini karena beberapa script warisan merujuk ke root dan script baru merujuk ke `output/`. |
| **Ketergantungan Excel Sumber** | Pipeline probabilitas membaca file Excel ECMWF dengan struktur nama sheet `pb50`, `pa150`, dll. | Jika BMKG Pusat mengubah penamaan sheet di masa depan, parser akan error | Tambahkan validator nama sheet pada `generate_probability_pipeline.py`. |
| **Kekosongan SPI Stasiun Baru** | Terdapat 5 pos hujan baru (ARG Setokok, ARG Karimun, ARG Singkep, ARG Tembeling, ARG Bintan Timur) yang belum memiliki data historis SPI | Nilai SPI menjadi NaN pada stasiun-stasiun tersebut | Engine sudah memiliki fallback: status kekeringan tetap dihitung dari HTH dan didukung probabilitas dasarian. Tidak perlu diimputasi buatan. |
| **Temporal Edge Case** | Pergantian tahun pada target dasarian (Desember Dasarian 3 menuju Januari Dasarian 1) | Pergeseran integer bulan dari 12 ke 1 | Sudah ditangani dengan aman pada baris 540–550 `generate_cews_decision_engine.py` menggunakan pencarian berbasis `target_month = 1`. |

---

# 4. ARSITEKTUR SISTEM

Sistem CEWS dibangun dengan arsitektur **Data-Centric Pipeline Layered Architecture**. Pemrosesan data dipisahkan secara modular sehingga kegagalan pada satu modul tidak menghentikan modul lainnya.

```
+-----------------------------------------------------------------------------------+
|                              1. DATA SOURCE LAYER                                 |
| - Curah Hujan Harian (final_rainfall_daily.parquet)                               |
| - Master Metadata Stasiun (station_metadata.parquet)                              |
| - File Excel SPI BMKG (SPI/2021_SPI.xlsx s/d 2025_SPI.xlsx)                       |
| - File Excel Prediksi ECMWF (probabilitas/2025/*.xlsx & probabilitas_bulanan/2025) |
| - Kamus Pemetaan Stasiun (mapping_tambahan.xlsx)                                  |
+-----------------------------------------------------------------------------------+
                                          |
                                          v
+-----------------------------------------------------------------------------------+
|                         2. CLIMATE INDICATOR ENGINES                              |
| +-------------------------+ +-------------------------+ +-----------------------+ |
| |       HTH Engine        | |       SPI Engine        | |  Probability Engine   | |
| | (generate_hth_pipeline) | | (generate_spi_pipeline) | | (generate_prob_pipe)  | |
| | Streak HTH, Uncertainty | | 3-Level Spatial Mapping | | Dasarian & Monthly    | |
| +-------------------------+ +-------------------------+ +-----------------------+ |
+-----------------------------------------------------------------------------------+
                                          |
                                          v
+-----------------------------------------------------------------------------------+
|                        3. CEWS INDICATOR PIPELINE                                 |
|                     (generate_cews_indicator_pipeline.py)                         |
|  - Agregasi Standar Dasarian (1-10, 11-20, 21-Akhir Bulan)                        |
|  - Standarisasi Flat Table: cews_indicator_dataset.parquet                        |
+-----------------------------------------------------------------------------------+
                                          |
                                          v
+-----------------------------------------------------------------------------------+
|                    4. REGULATION DECISION & ARBITRATION ENGINE                    |
|                        (generate_cews_decision_engine.py)                         |
|  - Aturan Regulasi: cews_rules.xlsx (HTH, SPI, Probability, Heavy Rain)           |
|  - Evaluasi Bahaya Kekeringan (Drought) & Curah Hujan Tinggi (Heavy Rain)         |
|  - Arbitrase Bahaya Tertinggi (Level Ranking: AWAS > SIAGA > WASPADA > NORMAL)    |
|  - Safeguard Kualitas Data: hth_uncertain membatasi status maksimal ke SIAGA      |
+-----------------------------------------------------------------------------------+
                                          |
                     +--------------------+--------------------+
                     |                                         |
                     v                                         v
+---------------------------------------+ +-----------------------------------------+
|   5A. HISTORICAL ANALYTICAL LAYER     | |    5B. OPERATIONAL CURRENT LAYER        |
|     (cews_warning_history.parquet)    | |      (cews_current_warning.parquet)     |
| - Seluruh periode dasarian masa lalu  | | - Tepat 1 baris aktif per stasiun       |
| - Immutable ledger untuk audit/riset  | | - Target peringatan periode masa depan  |
| - 2.052 baris (57 stn x 36 dasarian)  | | - cews_forecast_snapshot.parquet        |
+---------------------------------------+ +-----------------------------------------+
                                                               |
                                                               v (Tahap Selanjutnya)
                                          +-----------------------------------------+
                                          |      6. SERVING & PRESENTATION LAYER    |
                                          |  - MariaDB Database (Tables: cews_*)    |
                                          |  - REST & GeoJSON API Services          |
                                          |  - Web GIS Dashboard (Decision Support) |
                                          +-----------------------------------------+
```

### Alur Request Nyata (Traceability Contoh Kasus)
**Skenario: Sistem Menghasilkan Peringatan Operasional untuk Stasiun Batam (Stamet Hang Nadim)**
1. **Trigger:** Jadwal rutin dasarian atau operator menjalankan `python generate_cews_decision_engine.py --mode operational`.
2. **Deteksi Observasi:** Engine membaca `hth_daily_2021_2025.parquet`, mendeteksi tanggal observasi terakhir adalah `2025-12-31` (Dasarian 3 Desember 2025). Diperoleh nilai `hth_days_current = 2 hari`, `hth_uncertain = False`.
3. **Deteksi Prakiraan:** Engine memeriksa `probability_rainfall_dasarian_2025.parquet`, menemukan issue date terbaru `2025-12-29`.
4. **Penetapan Target Period:** Karena observasi terakhir adalah akhir Desember 2025, maka periode target yang dihadapi adalah **Dasarian 1 Januari 2026 (01–10 Januari 2026)**.
5. **Evaluasi Aturan Kekeringan:** HTH 2 hari masuk sheet `HTH_RULES` baris 1 (rentang 0–20 hari) $\rightarrow$ Status Dasar: `NORMAL`.
6. **Evaluasi Aturan Hujan Lebat:** Nilai `prob_above150` untuk Dasarian 1 Januari 2026 adalah $18.5\%$ ($< 70\%$) $\rightarrow$ Status Hujan Lebat: `NORMAL`.
7. **Arbitrase:** Kedua bahaya berada pada tingkat `NORMAL`. Engine menyusun narasi `trigger_reason`: *"HTH 2 hari berada pada kategori NORMAL (<= 20 hari). SPI 0.45 menunjukkan kondisi normal. Tidak ada indikasi ancaman curah hujan tinggi."*
8. **Penyimpanan State:** Tepat 1 record berkoordinat disimpan ke `cews_current_warning.parquet` dengan timestamp evaluasi `updated_at`.
9. **Snapshot Audit:** Rincian file sumber ECMWF dan seluruh nilai probabilitas yang dibaca disimpan ke `cews_forecast_snapshot.parquet`.

---

# 5. STRUKTUR DIREKTORI & INVENTARISASI ARTEFAK

### 5.1 Pohon Direktori Workspace
```
f:\TNJ\paper\DATA_ANALISIS_PRAKIRAAN\CEWS\MAS_HAYU\ASLI\
│
├── config/
│   └── cews_config.yaml                  # Konfigurasi parameter pipeline (mode, start, end, output)
│
├── logs/
│   └── cews_indicator_pipeline.log       # Berkas log eksekusi penyusunan indikator
│
├── output/                               # Folder replikasi artefak Parquet & QC
│   ├── cews_current_warning.parquet      # Status operasional aktif terkini (57 stasiun)
│   ├── cews_warning_history.parquet      # Histori peringatan komprehensif (2.052 baris)
│   ├── cews_forecast_snapshot.parquet    # Snapshot parameter prakiraan ECMWF (1.040 baris)
│   ├── cews_indicator_dataset.parquet    # Dataset gabungan indikator dasarian (2.052 baris)
│   ├── cews_warning_status.parquet       # Salinan kompatibilitas downstream
│   └── cews_indicator_qc_report.txt      # Laporan kendali mutu indikator
│
├── pipeline/
│   └── generate_cews_indicator_pipeline.py # Script penggabung HTH, SPI, dan Probabilitas
│
├── probabilitas/
│   └── 2025/                            # 33 Berkas Excel ECMWF probabilitas dasarian per pos
│       ├── KEPRI_pch_ecmwf_perpos_ver_2024.12.30.xlsx
│       └── ... (hingga ver_2025.12.29.xlsx)
│
├── probabilitas_bulanan/
│   └── 2025/                            # 12 Berkas Excel ECMWF probabilitas bulanan per pos
│       ├── KEPRI_pch_ecmwf_perpos_ver_2025.01.09.xlsx
│       └── ... (hingga ver_2025.12.29.xlsx)
│
├── SPI/                                  # 5 Berkas Excel SPI resmi BMKG (2021-2025)
│   ├── 2021_SPI.xlsx
│   ├── 2022_SPI.xlsx
│   ├── 2023_SPI.xlsx
│   ├── 2024_SPI.xlsx
│   └── 2025_SPI.xlsx
│
├── cews_current_warning.parquet          # [PRIMARY] Status operasional aktif (Root copy)
├── cews_warning_history.parquet          # [PRIMARY] Histori peringatan analitis (Root copy)
├── cews_forecast_snapshot.parquet        # [PRIMARY] Jejak audit prakiraan (Root copy)
├── cews_indicator_dataset.parquet        # [PRIMARY] Matriks indikator dasarian (Root copy)
├── cews_warning_status.parquet           # Salinan kompatibilitas
├── cews_rules.xlsx                       # [CONFIG] Konfigurasi tabel aturan Peraturan BMKG No. 9/2019
│
├── generate_cews_decision_engine.py      # [ENGINE] Skrip utama evaluasi keputusan (Dual Mode)
├── generate_hth_pipeline.py              # [ENGINE] Skrip kalkulasi Hari Tanpa Hujan harian
├── generate_spi_pipeline.py              # [ENGINE] Skrip ekstraksi dan pemetaan spasial SPI
├── generate_probability_pipeline.py      # [ENGINE] Skrip ekstraksi probabilitas dasarian
├── generate_probability_monthly_pipeline.py # [ENGINE] Skrip ekstraksi probabilitas bulanan
├── prepare_cews_data.py                  # [ETL] Skrip awal penggabungan curah hujan harian & metadata
│
├── station_metadata.parquet              # [MASTER] Buku induk identitas & koordinat 57 stasiun
├── mapping_tambahan.xlsx                 # [REFERENCE] Kamus resolusi alias & ID alternatif stasiun
├── final_rainfall_daily.parquet          # [RAW/CORRECTED] Data curah hujan harian terkoreksi CHIRPS
├── cews_integrated_2021_2025.parquet     # [INTEGRATED] Curah hujan harian terhubung koordinat
├── hth_daily_2021_2025.parquet           # [PROCESSED] Deret HTH harian per stasiun
├── spi_cews_2021_2025.parquet            # [PROCESSED] SPI bulanan analisis & prakiraan
│
├── cews_operational_qc_report.txt        # Laporan audit integritas layer operasional (100% PASS)
├── cews_decision_qc_report.txt           # Laporan audit integritas layer historis (100% PASS)
├── cews_decision_engine.log              # Berkas runtime log Decision Engine
├── powershell.cmd                        # Wrapper eksekusi terminal Windows
│
├── CEWS_PROJECT_MEMORY_DOCUMENTATION.md  # Dokumentasi teknis memori sistem lengkap
├── CEWS_TECHNICAL_AUDIT.md               # Laporan audit data science & kepatuhan regulasi
├── CEWS_SYSTEM_DOCUMENTATION.md          # Ringkasan konsep sistem awal
└── STATION_MAPPING_AUDIT.md              # Laporan audit pencocokan 57 stasiun BMKG
```

### 5.2 Berkas Paling Penting yang Wajib Dipahami Pertama Kali oleh PIC Baru
1. [`generate_cews_decision_engine.py`](file:///f:/TNJ/paper/DATA_ANALISIS_PRAKIRAAN/CEWS/MAS_HAYU/ASLI/generate_cews_decision_engine.py): Jantung logika operasional dan evaluasi aturan Peraturan BMKG No. 9 Tahun 2019.
2. [`cews_rules.xlsx`](file:///f:/TNJ/paper/DATA_ANALISIS_PRAKIRAAN/CEWS/MAS_HAYU/ASLI/cews_rules.xlsx): Berkas spreadsheet tempat mendefinisikan ambang batas HTH, SPI, dan Probabilitas tanpa perlu mengedit kode sumber Python.
3. [`station_metadata.parquet`](file:///f:/TNJ/paper/DATA_ANALISIS_PRAKIRAAN/CEWS/MAS_HAYU/ASLI/station_metadata.parquet): *Single Source of Truth* untuk 57 stasiun yang dilayani sistem.
4. [`cews_current_warning.parquet`](file:///f:/TNJ/paper/DATA_ANALISIS_PRAKIRAAN/CEWS/MAS_HAYU/ASLI/cews_current_warning.parquet): Output operasional yang akan di-push ke database MariaDB untuk konsumsi dashboard.
5. [`pipeline/generate_cews_indicator_pipeline.py`](file:///f:/TNJ/paper/DATA_ANALISIS_PRAKIRAAN/CEWS/MAS_HAYU/ASLI/pipeline/generate_cews_indicator_pipeline.py): Skrip ETL yang mengagregasikan seluruh data cuaca harian dan bulanan ke format dasarian.

---

# 6. TEKNOLOGI DAN DEPENDENSI

### 6.1 Daftar Komponen Teknologi
- **Bahasa Pemrograman:** Python 3.12 (CPython x64 pada lingkungan sistem Windows / Server).
- **Format Penyimpanan Utama:** **Apache Parquet (Snappy Compression)**. Format kolumnar biner berkecepatan tinggi yang menghemat ruang disk hingga 80% dibanding CSV/Excel dan mempertahankan tipe data (*type safety*) tanpa konversi ulang.
- **Konfigurasi Eksternal:** YAML (`PyYAML`) untuk konfigurasi runtime pipeline dan Microsoft Excel (`openpyxl`) untuk konfigurasi tabel aturan.

### 6.2 Inventarisasi Library Python Utama
| Library | Versi Digunakan | Alasan Penggunaan & Peran Kritis dalam Proyek |
|:---|:---:|:---|
| `pandas` | 2.2+ | Manipulasi dataframe tabular, operasi merge spasial, pivot indikator, dan time-series grouping. |
| `numpy` | 1.26+ | Vektorisasi perhitungan matematis, array boolean streak HTH, dan operasi jarak Haversine. |
| `pyarrow` | 15.0+ | Engine backend pembacaan dan penulisan berkas Parquet dengan kompresi Snappy. |
| `openpyxl` | 3.1+ | Parsing berkas Excel multi-sheet ECMWF dan SPI, serta formatting tabel aturan ber-header warna. |
| `pyyaml` | 6.0+ | Parsing berkas konfigurasi `config/cews_config.yaml`. |
| `logging` | Built-in | Perekaman jejak audit runtime (*audit trail*) ke berkas log harian. |
| `datetime` / `calendar` | Built-in | Penentuan rentang temporal dasarian (tanggal 1–10, 11–20, 21–akhir bulan) dan leap year. |

---

# 7. DATABASE DAN DATA MODEL (DATA DICTIONARY LENGKAP)

Berikut adalah kamus data (*Data Dictionary*) sangat detail untuk dataset inti yang menjadi tulang punggung CEWS.

---

## 7.1 Dataset: `cews_current_warning.parquet` (State Operasional Aktif Dashboard)
- **Tujuan Bisnis:** Menyimpan status peringatan dini aktif terkini untuk seluruh stasiun di Kepulauan Riau yang siap ditampilkan pada dashboard GIS.
- **Karakteristik Unik:** **Persis 57 baris (1 baris per stasiun)**. Tidak mencampur data masa lalu. Bersifat prospektif (*forward-looking*) menuju target dasarian mendatang.
- **Ukuran File / Rekaman:** ~26 KB | 57 baris × 31 kolom.

| Field | Type | Nullable | Default | Key | Referensi | Fungsi Bisnis & Deskripsi |
|:---|:---|:---:|:---:|:---:|:---|:---|
| `station_id` | String | NO | - | **PK** | `station_metadata.station_id` | ID unik stasiun pengamatan BMKG (8–10 karakter alfanumerik). |
| `station_name` | String | NO | - | - | `station_metadata.station_name` | Nama resmi stasiun/pos hujan pengamatan. |
| `latitude` | Float64 | NO | - | - | `station_metadata.latitude` | Koordinat lintang geografis (derajat desimal). |
| `longitude` | Float64 | NO | - | - | `station_metadata.longitude` | Koordinat bujur geografis (derajat desimal). |
| `province` | String | NO | 'KEPULAUAN RIAU' | - | - | Nama provinsi administratif. |
| `kabupaten` | String | NO | - | - | - | Nama kabupaten/kota administratif (Batam, Bintan, Karimun, Lingga, Natuna, Anambas, Tanjungpinang). |
| `last_observation_period` | String | NO | - | - | - | Label periode observasi terakhir yang tersedia (contoh: *"Dasarian 3 Desember 2025 (per 31-12-2025)"*). |
| `last_observation_date` | Date | NO | - | - | - | Tanggal pasti pengamatan curah hujan terakhir (contoh: `2025-12-31`). |
| `target_warning_period` | String | NO | - | - | - | Label periode masa depan yang menjadi sasaran peringatan dini (contoh: *"Dasarian 1 Januari 2026 (01 Jan 2026 s/d 10 Jan 2026)"*). |
| `target_period_start` | Date | NO | - | - | - | Tanggal mulai periode peringatan dini (contoh: `2026-01-01`). |
| `target_period_end` | Date | NO | - | - | - | Tanggal akhir periode peringatan dini (contoh: `2026-01-10`). |
| `target_year` | Int64 | NO | - | - | - | Tahun kalender target (contoh: `2026`). |
| `target_month` | Int64 | NO | - | - | - | Bulan kalender target (1–12). |
| `target_dasarian` | Int64 | NO | - | - | - | Nomor dasarian target (1, 2, atau 3). |
| `hazard_type` | String | NO | 'NORMAL' | - | - | Jenis ancaman iklim dominan (`NORMAL`, `DROUGHT`, `HEAVY_RAIN`). |
| `warning_level` | String | NO | 'NORMAL' | - | - | Tingkat keparahan peringatan dini (`NORMAL`, `WASPADA`, `SIAGA`, `AWAS`). |
| `trigger_reason` | String | NO | - | - | - | Penjelasan tekstual deterministik asal-usul ditetapkannya status peringatan sesuai regulasi BMKG. |
| `confidence_level` | String | NO | 'HIGH' | - | - | Derajat kepercayaan saintifik keputusan (`HIGH`, `MEDIUM`, `LOW`). |
| `data_quality_status` | String | NO | 'VALID' | - | - | Integritas deret observasi (`VALID`, `UNCERTAIN`). Menjadi `UNCERTAIN` jika ada data kosong pada periode HTH. |
| `spi_condition` | String | NO | 'kondisi normal' | - | - | Frasa kategori defisit hujan bulanan dari SPI (`kondisi normal`, `kondisi kering ringan`, `kondisi kering sedang`, `kondisi kering ekstrem`). |
| `probability_support` | Boolean | NO | False | - | - | Flag apakah model ECMWF mendukung keberlanjutan kekeringan (True jika probabilitas curah hujan rendah $\ge 70\%$). |
| `hth_days_current` | Float64 | YES | np.nan | - | - | Nilai deret Hari Tanpa Hujan terakhir yang tercatat di pos pengamatan (hari). |
| `hth_uncertain` | Boolean | NO | False | - | - | Flag apakah deret HTH memiliki catatan ketidakpastian (data observasi bolong). |
| `spi_value` | Float64 | YES | np.nan | - | - | Nilai numerik Standardized Precipitation Index bulan target. |
| `prob_below20` | Float64 | YES | np.nan | - | - | Peluang curah hujan dasarian $< 20\text{ mm}$ dari model ECMWF (persen: 0–100). |
| `prob_above150` | Float64 | YES | np.nan | - | - | Peluang curah hujan dasarian $> 150\text{ mm}$ (ambang batas Waspada hujan lebat). |
| `prob_above200` | Float64 | YES | np.nan | - | - | Peluang curah hujan dasarian $> 200\text{ mm}$ (ambang batas Siaga hujan lebat). |
| `prob_above300` | Float64 | YES | np.nan | - | - | Peluang curah hujan dasarian $> 300\text{ mm}$ (ambang batas Awas hujan ekstrem). |
| `prob_month_above400`| Float64 | YES | np.nan | - | - | Peluang curah hujan bulanan $> 400\text{ mm}$ (ambang batas Siaga bulanan). |
| `prob_month_above500`| Float64 | YES | np.nan | - | - | Peluang curah hujan bulanan $> 500\text{ mm}$ (ambang batas Awas bulanan). |
| `updated_at` | Timestamp | NO | - | - | - | Waktu komputasi pembuatan state operasional (zona waktu lokal/server). |

---

## 7.2 Dataset: `cews_forecast_snapshot.parquet` (Audit Provenance Prakiraan)
- **Tujuan Bisnis:** Menyediakan transparansi ilmiah dan pembuktian hukum (*audit trail*) mengenai berkas model prakiraan mana, terbitan tanggal berapa (*issue date*), dan nilai probabilitas apa yang dipakai saat menghasilkan status peringatan dini.
- **Ukuran File / Rekaman:** ~8 KB | 1.040 baris × 9 kolom.

| Field | Type | Nullable | Default | Key | Deskripsi Bisnis |
|:---|:---|:---:|:---:|:---:|:---|
| `station_id` | String | NO | - | **FK** | ID stasiun penerima prakiraan. |
| `issue_date` | Date | NO | - | - | Tanggal terbitnya berkas model ECMWF (contoh: `2025-12-29`). Wajib $< \text{target\_period\_start}$. |
| `source_file` | String | NO | - | - | Nama berkas Excel sumber (contoh: `KEPRI_pch_ecmwf_perpos_ver_2025.12.29.xlsx`). |
| `target_year` | Int64 | NO | - | - | Tahun target prakiraan (`2026`). |
| `target_month` | Int64 | NO | - | - | Bulan target prakiraan (`1`). |
| `target_dasarian` | Int64 | NO | - | - | Dasarian target prakiraan (`1`). |
| `forecast_parameter` | String | NO | - | - | Kode parameter probabilitas (contoh: `prob_below20`, `prob_above150`, `prob_month_above400`). |
| `probability_value` | Float64 | NO | - | - | Nilai probabilitas peluang kejadian (persen: 0.0 s/d 100.0). |
| `snapshot_timestamp` | Timestamp | NO | - | - | Waktu snapshot data diambil oleh engine. |

---

## 7.3 Dataset: `cews_warning_history.parquet` (Ledger Analitis Historis)
- **Tujuan Bisnis:** Menyimpan seluruh riwayat penetapan status peringatan dini dari masa lalu untuk keperluan *backtesting*, verifikasi akurasi prakiraan (*skill score*), audit regulasi, dan penelitian klimatologi.
- **Karakteristik Unik:** Bersifat *immutable* (tidak boleh ditimpa saat mode operasional berjalan).
- **Ukuran File / Rekaman:** ~49 KB | 2.052 baris × 28 kolom (57 stasiun × 36 dasarian tahun 2025).
- **Primary Composite Key:** `(station_id, period_start)`.

---

## 7.4 Dataset: `station_metadata.parquet` (Master Buku Induk Stasiun)
- **Tujuan Bisnis:** Menjadi *Single Source of Truth* spasial untuk seluruh stasiun di wilayah kerja Kepulauan Riau.
- **Ukuran File / Rekaman:** ~8 KB | 57 baris × 9 kolom.

| Field | Type | Nullable | Key | Deskripsi |
|:---|:---|:---:|:---:|:---|
| `station_id` | String | NO | **PK** | ID resmi stasiun pengamatan BMKG (contoh: `21720201A`, `21710401A`). |
| `station_name` | String | NO | - | Nama stasiun pengamatan (contoh: `Stamet Raja Haji Fisabilillah`). |
| `region` | String | NO | - | Wilayah administratif / regional BMKG (Wilayah I Medan). |
| `province` | String | NO | - | Nama provinsi (`KEPULAUAN RIAU`). |
| `regency` | String | NO | - | Nama kabupaten/kota (`Kota Tanjungpinang`, `Kota Batam`, `Kabupaten Bintan`, dll.). |
| `latitude` | Float64 | NO | - | Titik koordinat lintang resmi. |
| `longitude` | Float64 | NO | - | Titik koordinat bujur resmi. |
| `elevation_m` | Float64 | YES | - | Ketinggian stasiun di atas permukaan laut (meter). |

---

# 8. HUBUNGAN ANTAR DATA (ERD TEKSTUAL & RELASI)

```
station_metadata (Master Buku Induk 57 Stasiun)
 │
 ├── 1:N ──> final_rainfall_daily (Observasi Harian)
 │                │
 │                └── 1:1 ──> hth_daily_2021_2025 (Kalkulasi HTH Harian)
 │
 ├── 1:N ──> spi_cews_2021_2025 (Nilai SPI Bulanan)
 │
 ├── 1:N ──> probability_rainfall_dasarian_2025 (Prakiraan Dasarian ECMWF)
 │
 ├── 1:N ──> probability_rainfall_monthly_2021_2025 (Prakiraan Bulanan ECMWF)
 │
 └── 1:N ──> cews_indicator_dataset (Matriks Indikator Terkonsolidasi)
                  │
                  ├── 1:1 ──> cews_warning_history (Ledger Histori Peringatan 2025)
                  │
                  └── (Operational Pipeline)
                           │
                           ├── 1:1 (per Station) ──> cews_current_warning (State Aktif Terkini)
                           │
                           └── 1:N (Parameters)  ──> cews_forecast_snapshot (Jejak Bukti Prakiraan)
```

### Rincian Relasi & Integritas Data
1. **`station_metadata` $\rightarrow$ `cews_current_warning` (1-to-1):**
   - *Field Penghubung:* `station_id`.
   - *Kaidah Integritas:* Pada tabel operasional, setiap `station_id` yang ada di master metadata **WAJIB** memiliki tepat satu baris rekaman status aktif. Tidak boleh ada stasiun yang tertinggal (*no missing station*), dan tidak boleh ada stasiun ganda (*no duplicate station*). Telah diverifikasi 100% PASS (57/57).
2. **`cews_current_warning` $\rightarrow$ `cews_forecast_snapshot` (1-to-Many):**
   - *Field Penghubung:* `(station_id, target_year, target_month, target_dasarian)`.
   - *Kaidah Integritas:* Setiap stasiun pada periode target yang sama merujuk pada sekumpulan parameter probabilitas ECMWF yang mendasari terbitnya status tersebut.
3. **Risiko Data Yatim (*Orphan Records*):**
   - Jika berkas Excel ECMWF baru memasukkan stasiun yang belum terdaftar di `station_metadata.parquet`, sistem mapping 3-level akan mencari alias di `mapping_tambahan.xlsx`. Jika tetap tidak ditemukan, data tersebut ditandai `EXCLUDED_OUTSIDE_MASTER` dan dicatat ke `spi_excluded_stations_2021_2025.parquet`, sehingga tidak mengotori tabel utama.

---

# 9. DATA PALING PENTING / SOURCE OF TRUTH

Sistem CEWS membagi klasifikasi data secara ketat:

### 9.1 Master Data (Buku Induk)
- **Berkas:** `station_metadata.parquet`.
- **Peran:** Sumber kebenaran mutlak untuk koordinat (Latitude/Longitude), nama resmi, dan hirarki wilayah administratif. Jika terdapat perbedaan koordinat di berkas Excel luar, koordinat dari `station_metadata` adalah yang dimenangkan secara mutlak.

### 9.2 Transaction / Observational Data (Fakta Lapangan)
- **Berkas:** `final_rainfall_daily.parquet` dan `cews_integrated_2021_2025.parquet`.
- **Peran:** Data fakta curah hujan harian hasil pengamatan penakar hujan BMKG dan jaringan pos hujan kerja sama.

### 9.3 Reference Data (Lookup Table)
- **Berkas:** `mapping_tambahan.xlsx`.
- **Peran:** Kamus penyeragaman alias stasiun, kode pos lama (NOPOS), dan variasi ejaan nama stasiun.

### 9.4 Configuration Data (Aturan Bisnis & Ambang Batas)
- **Berkas:** `cews_rules.xlsx` dan `config/cews_config.yaml`.
- **Peran:** Tabel aturan resmi Peraturan BMKG No. 9 Tahun 2019 yang dapat diubah parameternya oleh forecaster tanpa menyentuh kode program.

### 9.5 Derived / Calculated Data (Indikator Turunan)
- **Berkas:** `hth_daily_2021_2025.parquet`, `spi_cews_2021_2025.parquet`, dan `cews_indicator_dataset.parquet`.
- **Peran:** Hasil komputasi matematika iklim (deret hari kering berturut-turut, standar deviasi defisit hujan, dan pemetaan probabilitas).

### 9.6 State / Operational Data (Status Aktif Terkini)
- **Berkas:** `cews_current_warning.parquet`.
- **Peran:** Snapshot status peringatan aktif yang ditampilkan kepada pengguna dashboard.

### 9.7 Audit & History Data (Jejak Rekam)
- **Berkas:** `cews_warning_history.parquet`, `cews_forecast_snapshot.parquet`, dan `logs/cews_decision_engine.log`.
- **Peran:** Catatan forensik data untuk pembuktian ilmiah dan rekonstruksi peringatan masa lalu.

---

# 10. DATA FLOW & SKENARIO EKSEKUSI

### Skenario 1: Eksekusi Mode Operasional Rutin (Setiap Dasarian)
- **Pemicu (Trigger):** Operator/Forecaster menjalankan engine di terminal atau cron scheduler dasarian:
  ```powershell
  python generate_cews_decision_engine.py --mode operational
  ```
- **Data Masuk (Input):**
  - Data HTH harian terakhir dari `hth_daily_2021_2025.parquet`.
  - Berkas prakiraan ECMWF terbitan terbaru di folder `probabilitas/2025/`.
  - Tabel aturan `cews_rules.xlsx`.
- **Validasi Data (Validation):**
  - Memeriksa apakah `issue_date` lebih kecil dari tanggal mulai periode target ($issue\_date < target\_start$).
  - Memeriksa apakah seluruh nilai probabilitas berada dalam rentang $0 \le P \le 100$.
- **Pemrosesan (Processing):**
  - Menentukan periode target masa depan ($T+1$).
  - Evaluasi aturan HTH, SPI, dan Probabilitas secara deterministik.
  - Arbitrase tingkat bahaya tertinggi.
  - Validasi ketidakpastian (`hth_uncertain`).
- **Penulisan Output (Database Write):**
  - Menulis 57 baris status aktif ke `cews_current_warning.parquet`.
  - Menulis snapshot parameter prakiraan ke `cews_forecast_snapshot.parquet`.
- **Side Effects & Log:**
  - Menghasilkan laporan kendali mutu `cews_operational_qc_report.txt`.
  - Menulis timestamp dan ringkasan eksekusi ke `cews_decision_engine.log`.
- **Penanganan Kegagalan (Failure Scenario):**
  - Jika berkas ECMWF belum terbit, sistem mencatat peringatan di log dan tetap mengevaluasi status berdasarkan HTH dan SPI dengan `probability_support = False` dan `confidence_level = MEDIUM`.

---

# 11. BUSINESS RULES & REGULASI BMKG NO. 9 TAHUN 2019

Seluruh logika keputusan CEWS tertuang di dalam [`cews_rules.xlsx`](file:///f:/TNJ/paper/DATA_ANALISIS_PRAKIRAAN/CEWS/MAS_HAYU/ASLI/cews_rules.xlsx) dengan pembagian 4 lembar kerja (*sheets*):

### Rule 1: Klasifikasi Hari Tanpa Hujan (`HTH_RULES`)
Sesuai Pasal 15 Peraturan BMKG No. 9 Tahun 2019:
- **`NORMAL`:** Deret HTH $0 \le HTH \le 20\text{ hari}$. Kondisi ketersediaan air tanah masih dalam batas wajar.
- **`WASPADA`:** Deret HTH $21 \le HTH \le 30\text{ hari}$ (Kategori Panjang).
- **`SIAGA`:** Deret HTH $31 \le HTH \le 60\text{ hari}$ (Kategori Sangat Panjang).
- **`AWAS`:** Deret HTH $HTH > 60\text{ hari}$ (Kategori Kekeringan Ekstrem).

### Rule 2: Konfirmasi Defisit SPI (`SPI_RULES`)
Sesuai Pasal 16 Peraturan BMKG No. 9 Tahun 2019:
- Nilai SPI digunakan sebagai konfirmasi kondisi defisit kebasahan tanah jangka menengah:
  - $SPI > -1.0$: Kondisi Normal / Basah.
  - $-1.49 \le SPI \le -1.0$: Kering Ringan.
  - $-1.99 \le SPI \le -1.5$: Kering Sedang.
  - $SPI \le -2.0$: Kering Ekstrem.
- **Catatan Penting:** SPI berfungsi sebagai pengonfirmasi (*supporting evidence*), bukan pemicu tunggal kenaikan status HTH.

### Rule 3: Konfirmasi Peluang Prakiraan (`PROBABILITY_RULES`)
- Ambang batas keyakinan probabilitas prospek ditetapkan minimal **$70\%$**.
- Jika Peluang Curah Hujan Rendah ($CH < 20\text{ mm/dasarian}$) $\ge 70\%$, maka prospek kekeringan terkonfirmasi kuat (*probability_support = True*).

### Rule 4: Peringatan Curah Hujan Tinggi (`HEAVY_RAIN_RULES`)
Sesuai Pasal 8 Peraturan BMKG No. 9 Tahun 2019:
- **`WASPADA`:** Peluang curah hujan dasarian $> 150\text{ mm} \ge 70\%$.
- **`SIAGA`:** Peluang curah hujan dasarian $> 200\text{ mm} \ge 70\%$ ATAU peluang curah hujan bulanan $> 400\text{ mm} \ge 70\%$.
- **`AWAS`:** Peluang curah hujan dasarian $> 300\text{ mm} \ge 70\%$ ATAU peluang curah hujan bulanan $> 500\text{ mm} \ge 70\%$.

### Rule 5: Logika Arbitrase Bahaya Tertinggi (Hazard Arbitration)
Jika dalam satu stasiun terdeteksi indikasi bahaya kekeringan sekaligus curah hujan tinggi, sistem menerapkan prinsip kehati-hatian meteorologi:
$$\text{Warning Level} = \max(\text{Level}_{\text{Drought}}, \text{Level}_{\text{Heavy Rain}})$$
Status dengan peringkat tertinggi (`AWAS` > `SIAGA` > `WASPADA` > `NORMAL`) yang akan dimenangkan, dengan narasi gabungan pada kolom `trigger_reason`.

### Rule 6: Safeguard Ketidakpastian Data Observasi (`hth_uncertain Safeguard`)
- **Kondisi:** Jika stasiun mengalami kekosongan data observasi harian pada periode deret HTH berjalan (`hth_uncertain = True`).
- **Konsekuensi Bisnis:** Status **AWAS TIDAK BOLEH DIRILIS SECARA OTOMATIS OLEH SISTEM**.
- **Aksi Sistem:** Status diturunkan maksimal ke **`SIAGA`**, flag `data_quality_status = UNCERTAIN`, dan `confidence_level = LOW`. Sistem memberikan catatan peringatan eksplisit pada narasi keputusan agar forecaster melakukan verifikasi manual ke pos hujan terkait.

---

# 12. API / ENDPOINT (STATUS & RANCANGAN)

> **Status Saat Ini:** Belum diimplementasikan (Tahap pengembangan backend API dijadwalkan pada Sprint berikutnya sesuai batasan proyek).

### Rancangan Endpoint yang Wajib Dibangun oleh PIC Baru:
Ketika membangun API service (misalnya menggunakan FastAPI / Python atau Express.js), berikut adalah kontrak antarmuka (*interface contract*) yang direkomendasikan:

| Method | Endpoint | Akses | Parameter / Body | Output | Fungsi Bisnis |
|:---|:---|:---:|:---|:---|:---|
| `GET` | `/api/v1/cews/warnings/current` | Public / Forecaster | `kabupaten` (opsional), `level` (opsional) | JSON Array (57 objek status aktif) | Mengambil seluruh status operasional stasiun untuk peta tematik dashboard. |
| `GET` | `/api/v1/cews/warnings/current/geojson` | Public / GIS | - | FeatureCollection GeoJSON (Point) | Format spasial siap render untuk Leaflet/Mapbox dashboard. |
| `GET` | `/api/v1/cews/warnings/history` | Internal / Auth | `station_id`, `year`, `dasarian` | JSON Array riwayat analitik | Query rekam jejak dasarian masa lalu untuk grafik time-series. |
| `GET` | `/api/v1/cews/forecast/snapshot` | Internal / Forecaster | `station_id`, `target_dasarian` | JSON Detail probabilitas ECMWF | Modal pop-up transparansi data pendukung saat titik stasiun diklik. |
| `POST`| `/api/v1/cews/pipeline/run` | Admin / Auth | `{"mode": "operational"}` | JSON Status eksekusi | Memicu eksekusi Decision Engine melalui antarmuka web. |

---

# 13. AUTENTIKASI & OTORISASI (STATUS & RANCANGAN)

> **Status Saat Ini:** Pipeline data saat ini berjalan sebagai skrip konsol internal (*backend analytical engine*) sehingga belum memerlukan lapisan autentikasi jaringan.

### Rekomendasi Desain Role-Based Access Control (RBAC) untuk Web Dashboard:
| Role | Akses Peta & Status | Eksekusi Pipeline Data | Modifikasi Aturan Excel | Verifikasi Rilis Peringatan |
|:---|:---:|:---:|:---:|:---:|
| **Public / BPBD** | Read-Only (Status Terverifikasi) | NO | NO | NO |
| **Forecaster on Duty** | Read & Drilldown Detail Snapshot | YES (Run Pipeline) | NO | Drafting Peringatan Dini |
| **Koordinator Bidang Data** | Full Read & Analitik Histori | YES | YES (`cews_rules.xlsx`) | Review Teknis |
| **Kepala Stasiun BMKG** | Full Read & Audit Trail | YES | NO | **Final Approval & Tanda Tangan Resmi** |

---

# 14. FRONTEND & DASHBOARD AS DECISION SUPPORT SYSTEM

### Filosofi Dashboard BMKG
Dashboard CEWS **BUKAN PENGGANTI FORECASTER**. Dashboard adalah **Decision Support System (DSS)** yang berfungsi:
1. Menampilkan peta situasi kebasahan dan kekeringan wilayah Kepulauan Riau secara real-time.
2. Melakukan *highlighting* otomatis warna peringatan (Kuning, Oranye, Merah) terhadap stasiun yang berisiko agar tidak terlewat oleh petugas.
3. **Keputusan Akhir:** Forecaster tetap memiliki wewenang penuh untuk menaikkan, menurunkan, atau menyesuaikan narasi buletin resmi berdasarkan pertimbangan dinamika atmosfer lokal (seperti Madden-Julian Oscillation, Siklon Tropis, atau Gelombang Kelvin/Rossby).

---

# 15. INTEGRASI EKSTERNAL & DATA INGESTION

Sistem CEWS bergantung pada 3 sumber data eksternal utama:
1. **Model ECMWF Probabilistik (Pusat Database BMKG):**
   - Format: Berkas Microsoft Excel `.xlsx` multi-sheet per pos hujan.
   - Frekuensi: Terbit setiap dasarian (~tanggal 9/10, 19/20, 28/29/30 setiap bulan).
   - Ingestion: Di-parse otomatis oleh `generate_probability_pipeline.py`.
2. **Indeks SPI BMKG Pusat (Kedeputian Bidang Klimatologi):**
   - Format: Berkas Excel bulanan `SPI/*.xlsx`.
   - Ingestion: Di-parse otomatis oleh `generate_spi_pipeline.py`.
3. **Observasi Curah Hujan Harian Jaringan Stasiun:**
   - Format: Berkas database penakar hujan terintegrasi.
   - Ingestion: Di-parse oleh `generate_hth_pipeline.py`.

---

# 16. ENVIRONMENT, KONFIGURASI, & RUNBOOK OPERASIONAL

### 16.1 Persyaratan Lingkungan Sistem (Environment Requirements)
- **OS:** Windows 10/11 atau Linux Server (Ubuntu 22.04 LTS / Debian 12 direkomendasikan).
- **Python:** Versi 3.10 s/d 3.12 (Teruji stabil di Python 3.12.7).
- **Package Manager:** `pip` standar.
- **Instalasi Dependensi:**
  ```bash
  pip install pandas numpy pyarrow openpyxl pyyaml
  ```

### 16.2 Berkas Konfigurasi
1. [`config/cews_config.yaml`](file:///f:/TNJ/paper/DATA_ANALISIS_PRAKIRAAN/CEWS/MAS_HAYU/ASLI/config/cews_config.yaml):
   ```yaml
   mode: backtest                  # Pilihan: 'backtest' atau 'operational'
   start_date: '2025-01-01'        # Awal periode jika backtest
   end_date: '2025-12-31'          # Akhir periode jika backtest
   data_version: '2026_DASARIAN_1' # Tag versi rilis
   output_path: ../output/cews_indicator_dataset.parquet
   ```
2. [`cews_rules.xlsx`](file:///f:/TNJ/paper/DATA_ANALISIS_PRAKIRAAN/CEWS/MAS_HAYU/ASLI/cews_rules.xlsx):
   - Tempat mengedit batasan hari HTH (sheet `HTH_RULES`), indeks SPI (sheet `SPI_RULES`), ambang probabilitas prospek (sheet `PROBABILITY_RULES`), dan ambang hujan lebat (sheet `HEAVY_RAIN_RULES`).

### 16.3 Runbook Eksekusi Pipeline (Cara Menjalankan Sistem)

#### Langkah 1: Eksekusi Mode Operasional (Menghasilkan Status Aktif Terkini)
Gunakan mode ini untuk operasional harian/dasarian guna memperbarui dashboard:
```powershell
python generate_cews_decision_engine.py --mode operational
```
*Output yang diperbarui:*
- `cews_current_warning.parquet` (57 baris aktif per stasiun).
- `cews_forecast_snapshot.parquet` (Snapshot bukti ECMWF yang digunakan).
- `cews_operational_qc_report.txt` (Laporan validasi otomatis).

#### Langkah 2: Eksekusi Mode Backtest (Menghasilkan Histori Analitis)
Gunakan mode ini saat ingin mengevaluasi performa model di masa lalu (misal tahun 2025):
```powershell
python generate_cews_decision_engine.py --mode backtest
```
*Output yang diperbarui:*
- `cews_warning_history.parquet` (2.052 baris rekam jejak dasarian).
- `cews_decision_qc_report.txt` (Laporan QC backtest).

#### Langkah 3: Eksekusi Penuh (All Mode)
```powershell
python generate_cews_decision_engine.py --mode all
```

---

# 17. PANDUAN KHUSUS & CHECKLIST UNTUK PIC BARU

Bagi Anda yang ditunjuk sebagai penanggung jawab teknis (PIC) baru untuk proyek CEWS ini, berikut adalah daftar periksa (*checklist*) dan langkah prioritas yang harus Anda lakukan:

### Checklist Serah Terima (Handover Checklist):
- [x] Memahami bahwa CEWS adalah sistem berbasis aturan regulasi BMKG (*Rule-Based Engine*), bukan Machine Learning.
- [x] Memverifikasi keberadaan 57 stasiun di `station_metadata.parquet`.
- [x] Memverifikasi bahwa `cews_current_warning.parquet` berisi tepat 57 baris (1 baris per stasiun) untuk target periode mendatang.
- [x] Memverifikasi bahwa `cews_operational_qc_report.txt` berstatus `100% PASS`.
- [x] Mengetahui bahwa file Excel `cews_rules.xlsx` adalah pengendali parameter aturan.

### Rencana Tindak Lanjut Prioritas (Next Action Roadmap):
1. **Prioritas 1 (Database Migration):**
   - Rancang skema tabel relasional SQL (`CREATE TABLE cews_current_warning (...)` dan `CREATE TABLE cews_warning_history (...)`) pada MariaDB/MySQL.
   - Buat skrip Python sederhana (`migrate_parquet_to_mariadb.py`) menggunakan `SQLAlchemy` atau `mysql-connector-python` untuk memuat data Parquet ke MariaDB setiap kali engine selesai berjalan.
2. **Prioritas 2 (Backend API Layer):**
   - Bangun REST API menggunakan FastAPI dengan endpoint utama `GET /api/cews/current-warning` yang membaca data dari MariaDB dan menghasilkan GeoJSON titik stasiun.
3. **Prioritas 3 (Frontend GIS Dashboard):**
   - Kembangkan antarmuka web berbasis Leaflet.js atau Mapbox GL JS yang menampilkan peta Kepulauan Riau dengan pin warna status (Hijau = Normal, Kuning = Waspada, Oranye = Siaga, Merah = Awas) serta panel informasi alasan keputusan (*trigger reason*) saat pin diklik.
4. **Prioritas 4 (Automated Scheduling):**
   - Daftarkan skrip `generate_cews_decision_engine.py --mode operational` ke Windows Task Scheduler atau Linux Cron Job agar dieksekusi otomatis setiap tanggal 1, 11, dan 21 dini hari.

---
*Dokumen ini disusun secara lengkap dan objektif berdasarkan analisis mendalam terhadap seluruh berkas kode sumber, dataset biner, dan log sistem yang tersedia di workspace CEWS BMKG.*
