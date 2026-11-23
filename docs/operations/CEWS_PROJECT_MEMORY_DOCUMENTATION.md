# CEWS PROJECT MEMORY DOCUMENTATION

==================================================
## BAB 1: IDENTITAS PROYEK
==================================================

**Nama:** Climate Early Warning System (CEWS)  
**Basis:** Peraturan BMKG Nomor 9 Tahun 2019 tentang Penyediaan dan Penyebaran Peringatan Dini Iklim Ekstrem  
**Wilayah:** Kepulauan Riau / Tanjungpinang  
**Status:** Development and Data Preparation Phase  

**Tujuan Utama:**  
Membangun sistem peringatan dini iklim berbasis data klimatologi yang robust, akurat, dan terstandardisasi. CEWS difokuskan pada pengolahan indikator iklim ekstrem, khususnya kekeringan meteorologis dan curah hujan tinggi, dengan memanfaatkan data observasi historis, indikator kekeringan (HTH & SPI), serta probabilitas curah hujan. Output akhir dari sistem ini adalah *Dashboard Operasional* yang terintegrasi.

==================================================
## BAB 2: FILOSOFI DAN KONSEP SISTEM
==================================================

**CEWS bukan sekadar dashboard.** Dashboard hanyalah antarmuka presentasi di ujung sistem. Kekuatan utama CEWS terletak pada kemampuan pemrosesan dan integrasi *backend* yang kompleks untuk mengubah data mentah dan heterogen menjadi indikator pengambil keputusan yang sah secara saintifik dan regulasi.

**Konsep Alur Sistem:**
```text
[DATA SOURCE] (Excel, Parquet, Metadata, Observasi CHIRPS)
      ↓
[DATA PROCESSING PIPELINE] (ETL, Cleaning, Resolusi Spasial)
      ↓
[CLIMATE INDICATOR ENGINE] (HTH, SPI, Dasarian/Monthly Probabilities)
      ↓
[DECISION ENGINE] (Ruleset Peraturan BMKG No. 9 Tahun 2019)
      ↓
[DATABASE OPERATIONAL] (MariaDB - Siap Tayang)
      ↓
[GIS DASHBOARD] (Visualisasi Spasial & Alerting)
```

Dashboard tidak boleh dibebani komputasi berat. Semua agregasi, penanganan *missing data*, perhitungan *streak*, hingga penentuan status (Awas/Siaga/Waspada) harus telah diselesaikan oleh *Decision Engine* dan dimasukkan bersih ke *Database Operational*.

==================================================
## BAB 3: KRONOLOGI PEMBANGUNAN SISTEM
==================================================

Pembangunan CEWS dilakukan secara iteratif dan struktural.

*   **Tahap 1: Audit dan Profiling Data Awal**
    *   **Pemeriksaan:** Melakukan audit struktur data terhadap file *master metadata* dan sampel data mentah (*raw data*).
    *   **Masalah Ditemukan:** Ketidakkonsistenan penamaan stasiun antar-sumber data, *missing values*, dan format nama kolom yang bervariasi. Terdapat stasiun di lapangan (seperti Tanjung Riau Kota Batam) yang tidak tercatat di Master Metadata.
    *   **Keputusan:** Membuat sistem *mapping* bertingkat (3-level) dan tidak memaksakan penghapusan stasiun tak dikenal, melainkan memberikan label *UNMATCHED* agar transparan.
*   **Tahap 2: Integrasi Dataset Rainfall**
    *   Menggabungkan curah hujan harian (`final_rainfall_daily.parquet`) dengan metadata stasiun (`station_metadata.parquet`), menghasilkan **`cews_integrated_2021_2025.parquet`**. Ini menjadi sumber valid kebenaran observasi CH.
*   **Tahap 3: Pembangunan Modul HTH (Hari Tanpa Hujan)**
    *   Membangun skrip pelacak hari tanpa hujan untuk mendeteksi *streak* di bawah ambang batas (1 mm/hari). Menghasilkan `hth_daily_2021_2025.parquet`.
*   **Tahap 4: Pembangunan Modul SPI**
    *   Memasukkan data Standardized Precipitation Index ke dalam ekosistem Parquet (`spi_cews_2021_2025.parquet`) untuk dimensi kekeringan historis bulanan.
*   **Tahap 5: Pembangunan Probabilitas Curah Hujan Dasarian**
    *   Mengekstraksi data prediksi curah hujan dasarian ECMWF, melakukan pivot kolom bulan-dasarian, melakukan *mapping* spasial, dan membungkusnya menjadi `probability_rainfall_dasarian_2025.parquet`.
*   **Tahap 6: Pembangunan Probabilitas Curah Hujan Bulanan**
    *   Mengadopsi pola dasarian untuk mengekstrak data probabilitas bulanan (`probability_rainfall_monthly_2021_2025.parquet`) dari puluhan *sheet* di 12 file Excel.
*   **Tahap 7: Pembangunan CEWS Indicator Pipeline**
    *   Menyatukan (mengagregasi) seluruh indikator di atas menjadi format *flat-table* dengan resolusi dasar Dasarian (`cews_indicator_dataset.parquet`) guna diumpankan ke tahap berikutnya (Decision Engine).

==================================================
## BAB 4: ARSITEKTUR DATA CEWS
==================================================

```text
========================================================================
| INPUT DATA                                                           |
| - rainfall_daily.csv                                                 |
| - station_metadata.parquet (Master Key)                              |
| - SPI BMKG                                                           |
| - KEPRI_pch_ecmwf_perpos_ver_xxxx.xlsx (Dasarian/Bulanan)            |
| - mapping_tambahan.xlsx                                              |
========================================================================
                   ||
                   \/
========================================================================
| PROCESSING (CEWS PIPELINE)                                           |
| 1. ETL (Extract, Transform, Load) to Parquet                         |
| 2. Quality Control (Missing, Range 0-100%, Streak >=0)               |
| 3. Mapping 3-Level (Exact -> Reference -> Haversine)                 |
| 4. Aggregation (Daily -> Dasarian -> Monthly)                        |
| 5. Indicator Extraction (HTH, SPI, Probability Thresholds)           |
========================================================================
                   ||
                   \/
========================================================================
| OUTPUT & SERVING                                                     |
| - cews_indicator_dataset.parquet (Analytical Base Table)             |
| - CEWS Decision Engine (To Be Developed)                             |
| - MariaDB Operational Database (To Be Developed)                     |
| - GIS Dashboard (Final Presentation)                                 |
========================================================================
```

==================================================
## BAB 5: MASTER METADATA DAN SISTEM MAPPING
==================================================

**Master Metadata (`station_metadata.parquet`)** adalah *Source of Truth* (buku induk) untuk seluruh identitas stasiun (ID, Nama, Lat, Lon, Provinsi, Kabupaten). Jika data lain memiliki koordinat berbeda, sistem harus dipaksa tunduk pada latitude/longitude dari master metadata ini.

**Buku Tambahan (`mapping_tambahan.xlsx`)** digunakan untuk menampung variasi penamaan (*alias*) yang kerap muncul dari file-file *Excel* sumber (misal: "Stasiun Meteorologi RHF" vs "Raja Haji Fisabilillah").

**Mekanisme Mapping 3-Level:** Karena dataset datang dari divisi yang berbeda, resolusi stasiun wajib berlapis:
1.  **Exact Match:** Membandingkan ID atau nama yang telah dinormalisasi (huruf kapital, tanpa spasi ekstra) langsung dengan `station_id`.
2.  **Reference/String Match:** Mencari di dalam *lookup table* (`mapping_tambahan.xlsx`) untuk alias atau NOPOS.
3.  **Spatial Haversine Match:** Mengukur jarak Euclidean melengkung (*Haversine*) berdasarkan Latitude/Longitude. Jika jarak < 1 km, maka dianggap *MATCHED*. Jika jarak > 1 km, ditandai sebagai *SPATIAL WARNING*. Jika gagal sama sekali = *UNMATCHED*.

==================================================
## BAB 6: DATABASE RAINFALL
==================================================

**Dataset:** `cews_integrated_2021_2025.parquet`

*   **Tujuan:** Menyediakan landasan parameter CHIRPS/observasi (*ground truth*) di tiap titik observasi untuk validasi/pemodelan.
*   **Sumber Data:** Integrasi data pengukuran curah hujan harian BMKG/stasiun terkait.
*   **Periode:** 2021 hingga 2025 (2025 dikhususkan sebagai area *Trial/Backtesting* sistem, karena pergerakan dinamisnya belum selesai/selalu ada data masuk harian).
*   **Resolusi:** Harian.
*   **Kolom Utama:** `date`, `station_id`, `rainfall` (mm).
*   **Penggunaan:** Menghitung deret kemarau (HTH) serta analisis baseline.

==================================================
## BAB 7: MODUL HARI TANPA HUJAN (HTH)
==================================================

**Dataset:** `hth_daily_2021_2025.parquet` (Tracking) & `hth_monthly_snapshot_2021_2025.parquet` (Aggregasi)

*   **Definisi Operasional:** "Hari Tanpa Hujan" terjadi jika akumulasi curah hujan harian kurang dari 1.0 mm (Hujan < 1 mm = Kering).
*   **Algoritma:**
    - Jika `rainfall < 1` -> counter (streak) `+1`.
    - Jika `rainfall >= 1` -> counter di-reset ke `0`.
*   **Threshold Kriteria BMKG:**
    - 1-5 hari: Sangat Pendek
    - 6-10 hari: Pendek
    - 11-20 hari: Menengah
    - 21-30 hari: Panjang
    - 31-60 hari: Sangat Panjang
    - > 60 hari: Kekeringan Ekstrem
*   **Uncertainty Handling:** Jika dalam suatu deret HTH terdapat satu hari dengan data curah hujan *NaN* (kosong/alat rusak), nilai streak tetap dilanjutkan, namun kolom `is_uncertain` (atau `hth_uncertain`) di-*flag* menjadi `True`. Ini mengamankan integritas saintifik agar nilai kekeringan tidak hilang sepenuhnya namun memberikan penanda keraguan bagi pengambil kebijakan.

==================================================
## BAB 8: MODUL SPI
==================================================

**Dataset:** `spi_cews_2021_2025.parquet`

*   **Fungsi SPI:** Standardized Precipitation Index. Bukan alat pengukur hujan hari itu, melainkan pengukur deviasi kekeringan (defisit) historis selama jangka waktu tertentu.
*   **Resolusi:** Bulanan.
*   **Integrasi:** SPI bukan penentu keputusan tunggal. Menurut regulasi, ia diintegrasikan dengan HTH untuk menghasilkan peringatan dini yang utuh. Data SPI di-*broadcast* mengisi setiap dasarian di bulan target yang sama.

==================================================
## BAB 9: PROBABILITAS CURAH HUJAN DASARIAN
==================================================

**Dataset:** `probability_rainfall_dasarian_2025.parquet`

*   **Sumber:** File-file prediksi ECMWF berformat Excel seperti `KEPRI_pch_ecmwf_perpos_ver_2025.01.01.xlsx`.
*   **Konsep `issue_date`:** `issue_date` adalah tanggal *terbitnya* prediksi (saat model *run*), yang seringkali tidak sama dengan rentang tanggal *kejadian* yang diramalkan (target). Karena itu kita memisahkannya dari `target_year`, `target_month`, dan `target_dasarian`.
*   **Logika Sheet Excel:** 
    - `pbXX`: **P**robability **B**elow `XX` mm. Digunakan untuk mendeteksi ancaman kekeringan/ketiadaan hujan. Threshold = 50mm. (Telah diamankan kolom prob_below20 untuk kompatibilitas ekstensi target).
    - `paXX`: **P**robability **A**bove `XX` mm. Digunakan untuk mendeteksi ancaman curah hujan ekstrem/banjir. Threshold = 50, 150, 200, 300 mm.
*   **Output Parquet:** Setiap probabilitas diletakkan vertikal/Melted dengan kolom `threshold_mm`, `probability_type` (BELOW/ABOVE), dan `probability_percent`.

==================================================
## BAB 10: PROBABILITAS CURAH HUJAN BULANAN
==================================================

**Dataset:** `probability_rainfall_monthly_2021_2025.parquet`

*   **Perbedaan dengan Dasarian:** Resolusi target kejadiannya satu bulan penuh (indikasi jangka menengah). Konsep penarikan sama persis menggunakan metode Melt data antar-sheet.
*   **Threshold Tersedia:**
    - **BELOW**: 50, 100, 150 mm.
    - **ABOVE**: 50, 100, 150, 200, 300, 400, 500 mm.

==================================================
## BAB 11: CEWS INDICATOR PIPELINE
==================================================

**Script:** `generate_cews_indicator_pipeline.py`
**Output Dataset:** `cews_indicator_dataset.parquet`

Pipeline tahap akhir ini mengonsolidasikan semua modul di atas ke dalam satu format matriks agregasi beresolusi Dasarian (Tanggal 1-10, 11-20, 21-akhir bulan).

**Mekanisme Mode (Terdefinisi via `cews_config.yaml`):**
1.  **BACKTEST MODE:**
    Diperuntukkan utamanya untuk periode "2025". Mode ini akan membongkar rentang tanggal `start_date` hingga `end_date` yang tertulis dan memprosesnya dari nol. Sangat ideal untuk *Trial Validation* dan *Debugging* algoritma karena aman digunakan merusak/menciptakan ulang *state* sistem di masa lalu.
2.  **OPERATIONAL MODE:**
    Mode untuk tahun 2026 dan seterusnya.
    - *Incremental Update:* Sistem cukup melihat stempel periode terakhir di dalam tabel (contoh: 30 September 2026).
    - Pipeline hanya akan mengeksekusi perhitungan HTH dan mengekstrak Excel **hanya** sejak tanggal 1 Oktober 2026 hingga ke hari operasi sistem *saat ini*.
    - Data ini kemudian di-*append* (tambahkan) ke *Parquet* di belakang, memastikan tidak ada perhitungan ulang jutaan baris historis yang buang-buang komputasi.

==================================================
## BAB 12: QUALITY CONTROL DAN VALIDASI
==================================================

Seluruh tahapan CEWS memiliki modul QC yang keras, dan memuntahkan log ke `cews_indicator_qc_report.txt` dan `cews_indicator_pipeline.log`.

**Metrik QC:**
*   **Audit Data:** Memastikan tidak ada kolom krusial yang hilang (Misal: pergeseran header `kab_kota` vs `kabupaten` telah di-*handle* via *fallback* kondisional).
*   **Missing Handling:** `NaN` diizinkan pada metrik Prediksi (SPI/Probabilitas) karena ketersediaannya wajar bolong-bolong dalam periode observasi. Namun, nilai-nilai tersebut **TIDAK** diimputasi/ditebak agar tidak merusak kaidah klimatologi.
*   **Mapping & Spatial Validation:** Pengecekan jarak koordinat dengan batasan toleransi 1 km (*Haversine*).
*   **Probability Validation:** Tidak mentoleransi angka prediksi di bawah `0` atau di atas `100`.
*   **Consistency Check:** Ditegaskan *primary key constraint*: Satu kombinasi `station_id` + `period_start` di akhir tabel Indikator hanya boleh ada 1 kemunculan (Telah diverifikasi PASS = 0 duplikasi).

==================================================
## BAB 13: STATUS TERAKHIR PROJECT
==================================================

| Komponen | Status | Output Final |
| Komponen | Status | Output Final |
| :--- | :---: | :--- |
| **Master Metadata & Mapping** | ✅ DONE | `station_metadata.parquet`, `mapping_tambahan.xlsx` |
| **Rainfall Integrated Dataset** | ✅ DONE | `cews_integrated_2021_2025.parquet` |
| **Modul HTH (Daily & Snapshot)** | ✅ DONE | `hth_daily_2021_2025.parquet` |
| **Modul SPI** | ✅ DONE | `spi_cews_2021_2025.parquet` |
| **Modul Probability Dasarian**| ✅ DONE | `probability_rainfall_dasarian_2025.parquet` |
| **Modul Probability Bulanan** | ✅ DONE | `probability_rainfall_monthly_2021_2025.parquet` |
| **CEWS Indicator Pipeline** | ✅ DONE | `cews_indicator_dataset.parquet` |
| **CEWS Decision Engine (Dual Layer)** | ✅ DONE | `cews_warning_history.parquet`, `cews_current_warning.parquet`, `cews_forecast_snapshot.parquet`, `cews_rules.xlsx` |

==================================================
## BAB 14: ARSITEKTUR CEWS DECISION ENGINE (OPERATIONAL & HISTORICAL REDESIGN)
==================================================

**Script:** `generate_cews_decision_engine.py`  
**Konsep Pendekatan:** *Regulation-Based Hybrid Rule Engine* (Deterministik, Tanpa ML/Scoring Arbitrer) dengan **Dual-Layer State Management**.

Setelah evaluasi desain, sistem direfaktor agar memisahkan secara tegas fungsi **Histori Analitik** dan **Operasional Aktif**:

### 1. Dual-Layer Architecture (Pemisahan Histori vs Kondisi Terkini):

*   **Layer 1: Historical Analytical System (`cews_warning_history.parquet`)**
    *   **Tujuan:** Backtesting, validasi model, audit kepatuhan regulasi, dan penelitian klimatologi.
    *   **Karakteristik:** Bersifat *immutable ledger* (catatan permanen) yang menyimpan riwayat seluruh periode dasarian historis (misal: 36 dasarian tahun 2025).
    *   **Output:** `cews_warning_history.parquet` (dan laporan `cews_decision_qc_report.txt`).

*   **Layer 2: Operational Current Warning System (`cews_current_warning.parquet`)**
    *   **Tujuan:** Menyajikan status peringatan dini aktif terkini yang siap dikonsumsi langsung oleh antarmuka dashboard operasional.
    *   **Karakteristik:** **Tepat 1 baris status aktif per stasiun**. Tidak mencampurkan data masa lalu. Diperbarui secara dinamis setiap kali observasi baru atau berkas prakiraan baru masuk.
    *   **Field Kunci:** `station_id`, `station_name`, `last_observation_period`, `target_warning_period`, `hazard_type`, `warning_level`, `trigger_reason`, `confidence_level`, `data_quality_status`, `updated_at`.

*   **Layer 3: Forecast Provenance Snapshot (`cews_forecast_snapshot.parquet`)**
    *   **Tujuan:** Melacak secara transparan (*audit trail*) berkas prediksi model (ECMWF) dan parameter probabilitas mana yang digunakan sebagai dasar terbitnya status pada periode target tertentu.
    *   **Field Kunci:** `station_id`, `issue_date`, `source_file`, `target_year`, `target_month`, `target_dasarian`, `forecast_parameter`, `probability_value`, `snapshot_timestamp`.

---

### 2. Konsep Target Period (Forward-Looking Warning):

> **Prinsip Utama:** Sistem peringatan dini iklim **TIDAK** memberikan peringatan untuk periode yang sudah lewat. Peringatan dini harus bersifat *prospektif (forward-looking)* menuju periode mendatang.

*   **Mekanisme:**
    1.  Sistem mendeteksi tanggal observasi terakhir yang tersedia (*last available observation*), misalnya: **Dasarian 3 Desember 2025 (21-31 Des 2025)**.
    2.  Sistem mengambil terbitan prakiraan terbaru (*latest issue_date*), misalnya terbit tanggal **29 Desember 2025**.
    3.  Periode target yang dievaluasi peringatannya adalah periode berikutnya yang sedang dihadapi: **Dasarian 1 Januari 2026 (01-10 Jan 2026)**.
    4.  Dashboard secara eksplisit menampilkan:  
        *"Status Peringatan Dini untuk Dasarian 1 Januari 2026 (Berdasarkan data observasi hingga 31 Desember 2025 dan prakiraan ECMWF issue 29 Desember 2025)"*.

---

### 3. Filosofi Dashboard sebagai Decision Support System (DSS):

*   **Bukan Pengganti Forecaster:** CEWS dirancang sebagai **Decision Support System (DSS)**, bukan *automated replacement* bagi personil prakirawan (forecaster) BMKG.
*   **Fungsi Utama Dashboard:**
    1.  Menyajikan visualisasi kondisi terkini di seluruh stasiun/pos hujan wilayah kerja secara cepat dan intuitif.
    2.  Melakukan *highlighting* otomatis terhadap wilayah-wilayah prioritas yang berada pada status WASPADA, SIAGA, atau AWAS.
    3.  Membantu forecaster agar tidak melewatkan (*fail-safe*) indikasi bahaya kekeringan meteorologis maupun curah hujan tinggi yang kompleks di lapangan.
    4.  **Keputusan Akhir (Final Decision):** Rilis narasi peringatan resmi ke publik dan instansi BPBD tetap berada di tangan pertimbangan profesional *Forecaster on Duty*.

---

### 4. Rule Configuration Layer & Safeguard (`cews_rules.xlsx`):

Aturan regulasi dikonfigurasi secara transparan via Excel:
*   `HTH_RULES`: Status dasar deret kekeringan (NORMAL <=20, WASPADA 21-30, SIAGA 31-60, AWAS >=61 hari).
*   `SPI_RULES`: Konfirmasi kondisi defisit hujan bulanan (Kering Ringan -1 s/d -1.49, Kering Sedang -1.5 s/d -1.99, Kering Ekstrem <= -2.0). SPI tidak menaikkan status HTH secara sepihak.
*   `PROBABILITY_RULES`: Ambang batas probabilitas prospek (>= 70%).
*   `HEAVY_RAIN_RULES`: Curah hujan tinggi dasarian/bulanan (WASPADA >150 mm dasarian, SIAGA >200 mm dasarian / >400 mm bulanan, AWAS >300 mm dasarian / >500 mm bulanan).
*   `hth_uncertain Safeguard`: Jika terdeteksi kekosongan observasi (`hth_uncertain = True`), status AWAS dicegah secara otomatis dan diturunkan ke SIAGA, serta dilabeli `data_quality_status = UNCERTAIN`, `confidence_level = LOW`.

==================================================
## BAB 15: DESAIN MASA DEPAN (ROADMAP)
==================================================

Tahapan yang akan dikejar di fase iterasi (Sprint) selanjutnya:
1.  **MariaDB Operational Database:** Migrasi `cews_current_warning.parquet` dan `cews_warning_history.parquet` ke skema tabel relasional RDBMS (`.sql`) untuk melayani query API real-time.
2.  **GIS Dashboard Backend/API:** Endpoint REST/GeoJSON untuk plotting status stasiun dan poligon peringatan.
3.  **GIS Dashboard Frontend:** Visualisasi peta tematik peringatan dini iklim berbasis web sebagai DSS forecaster.
4.  **Automated Scheduling (Cron/Task Scheduler):** Orkestrasi operational mode mandiri setiap tanggal 1, 11, dan 21.

==================================================
## BAB 16: KEPUTUSAN DESAIN PENTING
==================================================

*   **Pemisahan Tabel Current vs History:** Mencegah redundansi query dashboard dan memastikan dashboard selalu memuat *snapshot* status aktif yang ringan tanpa memproses histori jutaan baris.
*   **Rule Engine Deterministik (Bukan ML/Scoring):** Menjamin legalitas, transparansi, dan auditabilitas sesuai Peraturan BMKG No. 9 Tahun 2019.
*   **Target Warning Period Forward-Looking:** Menjamin sistem peringatan memberikan nilai mitigasi sebelum bencana terjadi.
*   **Audit Trail via Forecast Snapshot:** Memungkinkan rekonstruksi ilmiah terhadap setiap peringatan yang pernah diterbitkan.

==================================================
## BAB 17: CATATAN UNTUK GPT BERIKUTNYA (CONTEXT FOR FUTURE AI ASSISTANT)
==================================================

> **PERHATIAN UNTUK AI LAIN (SYSTEM HANDOFF):**
> Jika Anda (AI lain) di- *assign* ke dalam project Workspace ini, Anda HARUS memahami status terkini berikut:
> 1. Modul **CEWS DECISION ENGINE** telah beroperasi dengan arsitektur **Dual-Layer (Operational + Historical)**.
> 2. Dataset peringatan aktif terkini tersimpan di `cews_current_warning.parquet` (persis 1 baris per stasiun untuk periode target mendatang).
> 3. Dataset histori analitik tersimpan di `cews_warning_history.parquet`.
> 4. Snapshot input prediksi tersimpan di `cews_forecast_snapshot.parquet`.
> 5. Skrip eksekusi utama adalah `generate_cews_decision_engine.py` dengan opsi `--mode operational`, `--mode backtest`, atau `--mode all`.
> 6. Tahap berikutnya adalah perancangan skema relasional **MariaDB/MySQL** dan API layer sebelum membangun UI Dashboard.

==================================================
## BAB 18: CURRENT NEXT ACTION
==================================================

**NEXT STEPS:**
1.  **Siapkan Migrasi Database MariaDB:** Rancang skema DDL tabel `cews_current_warning` dan `cews_warning_history` serta script migrasi data dari Parquet ke RDBMS.
2.  **Rancang API Layer / Backend Service:** Siapkan service query data status peringatan untuk konsumsi dashboard GIS.
==================================================


