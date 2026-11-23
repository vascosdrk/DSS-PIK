# FEATURE INVENTORY — DSS-PIK BMKG KEPULAUAN RIAU
**Inventarisasi Lengkap Fitur Aktif, Antarmuka Pengguna, dan Komponen Sistem**  
**Institusi**: BMKG Stasiun Meteorologi Kelas II Raja Haji Fisabilillah Tanjungpinang  
**Status Audit**: `VERIFIED CURRENT` (November 2026)

---

## 1. TABEL INVENTARISASI FITUR UTAMA

| No | Fitur / Komponen | Menu / Akses | Fungsi Operasional | Modul Backend | Komponen Frontend | Sumber Data (DB / File) | Status |
|:---:|---|---|---|---|---|---|:---:|
| **1** | **Pemilih Periode Operasional** | Header / Banner Dasbor | Memilih periode evaluasi iklim aktif (resolusi Dasarian) serta mendeteksi otomatis periode terbaru berbasis tanggal cutoff observasi. | `backend/period_service.py`, `backend/main.py` | `PeriodSelector.jsx`, `SimulationBanner.jsx` | MariaDB `cews_period_snapshot`, Parquet `cews_forecast_snapshot` | `ACTIVE` |
| **2** | **Kartu Ringkasan KPI** | Beranda Dasbor | Menampilkan rekapitulasi cepat jumlah stasiun pada setiap status bahaya (Total Stasiun, Normal, Waspada, Siaga, Awas, dan Incomplete). | `backend/main.py` (`/api/v1/early-warning-table`) | `KpiCards.jsx` | Kalkulasi dinamis via `backend/decision_engine.py` | `ACTIVE` |
| **3** | **Mode Filter Dual-Hazard** | Bilah Filter Dasbor | Menyaring tampilan dasbor dan tabel berdasarkan jenis ancaman: Semua Bahaya (Dual-Hazard), Mode PDKM (Kekeringan), atau Mode PDCHT (Curah Hujan Tinggi). | `backend/main.py`, `backend/decision_engine.py` | `FilterBar.jsx` | In-memory filtering state pada frontend | `ACTIVE` |
| **4** | **Peta WebGIS Interaktif 57 Stasiun** | Beranda Dasbor | Visualisasi sebaran geografis 57 pos pengamatan dengan pin status warna (Hijau/Kuning/Oranye/Merah/Abu-abu), tooltip cepat, dan poligon batas kecamatan. | `backend/main.py`, `backend/regional_warning_service.py` | `MapLeaflet.jsx` | GeoJSON poligon Kepri, MariaDB `stations`, API `/preview` | `ACTIVE` |
| **5** | **Tabel Peringatan Dini Stasiun** | Beranda Dasbor | Matriks tabular 57 stasiun yang menampilkan data HTH, SPI 30D, SPI 90D, Pb20, Pa150-300, PM300-500, serta status rekomendasi sistem. | `backend/main.py` (`/api/v1/early-warning-table`) | `HthTable.jsx` | MariaDB `stations`, `cews_rainfall_daily`, snapshot periode | `ACTIVE` |
| **6** | **Daftar Perhatian Prioritas** | Beranda Dasbor (Samping Peta) | Kartu peringatan cepat yang menyorot stasiun-stasiun dengan status bahaya aktif (`WASPADA`, `SIAGA`, `AWAS`) yang membutuhkan atensi segera forecaster. | `backend/main.py` | `HthTable.jsx` (Priority section) | Data derived dari tabel peringatan dini aktif | `ACTIVE` |
| **7** | **Station Detail Drawer (Laci Analitik)** | Klik Baris Tabel / Marker Peta | Menampilkan analisis multi-parameter rinci stasiun tertentu, ringkasan statistik, dan riwayat observasi curah hujan 30 hari terakhir. | `backend/main.py` (`/api/v1/stations/{id}/detail`) | `StationDetailDrawer.jsx` | MariaDB `cews_rainfall_daily`, `cews_forecast_snapshot` | `ACTIVE` |
| **8** | **Grafik Tren SPI Multi-Skala** | Station Detail Drawer (Tab Statistik) | Grafik visualisasi time series indeks SPI 30-harian dan 90-harian untuk memantau dinamika kebasahan/kekeringan stasiun terpilih. | `backend/spi_calculation_service.py` | `StationSpiTrendChart.jsx` | Parquet `data/raw/spi/dasarian/` | `ACTIVE` |
| **9** | **Penetapan Peringatan Wilayah (59 Kecamatan)** | Tombol Header "Peta & Keputusan Resmi" | Modal kerja interaktif untuk menetapkan status peringatan dini tingkat kecamatan, melakukan operator override berdasar analisis lokal, dan verifikasi status. | `backend/regional_warning_service.py` | `OfficialMapModal.jsx` | MariaDB `cews_regional_warning_decisions`, GeoJSON 59 Kec | `ACTIVE` |
| **10** | **Generator Peta Resmi BMKG** | Official Map Modal | Merender peta grafis A4 landscape resmi BMKG (1653x1170 px) berpartisi 59 kecamatan, dilengkapi legenda 4 kelas, compass rose, skala, dan logo BMKG. | `backend/map_generator.py` | `OfficialMapModal.jsx` | Shapefile batas administrasi Kepri, template BMKG resmi | `ACTIVE` |
| **11** | **Ekspor & Validasi JSON Terstandar** | Official Map Modal & REST API | Menghasilkan berkas JSON publikasi SIH3 dengan skema kanonikal 10 atribut root, divalidasi dengan 18-point Quality Control dan JSON Schema. | `backend/regional_warning_service.py` | `OfficialMapModal.jsx` | Derived snapshot keputusan, schema JSON | `ACTIVE` |
| **12** | **Data Center — Monitoring Penyimpanan Data** | Tab Navigasi "Data Center" | Panel monitoring status kesehatan basis data MariaDB, integritas berkas Parquet, waktu sinkronisasi, dan jumlah record aktif. | `backend/data_service.py` | `CanonicalStorageStatusCard.jsx`, `DataCenter.jsx` | System inspection, MariaDB query, Parquet scan | `ACTIVE` |
| **13** | **Data Center — Tabel Curah Hujan Harian** | Tab Navigasi "Data Center" | Tampilan tabular data pengamatan curah hujan harian per pos pengamatan, filter rentang tanggal, status observasi, dan fitur ekspor ke Excel. | `backend/data_service.py` (`/api/v1/rainfall/daily`) | `DailyRainfallTable.jsx` | MariaDB `cews_rainfall_daily`, `stations` | `ACTIVE` |
| **14** | **Data Center — Tabel Probabilitas Prakiraan** | Tab Navigasi "Data Center" | Tampilan data ensemble probabilitas prakiraan iklim ECMWF (dasarian dan bulanan) per stasiun untuk periode aktif dan riwayat. | `backend/data_service.py` | `ProbabilityDataTable.jsx` | MariaDB `cews_forecast_snapshot` | `ACTIVE` |
| **15** | **Data Center — Tabel SPI Kanonikal** | Tab Navigasi "Data Center" | Menampilkan tabel nilai indeks SPI per pos pada resolusi dasarian, bulanan, dan harian untuk skala waktu 30D dan 90D. | `backend/spi_calculation_service.py` | `SpiDataTable.jsx` | Berkas Parquet canonical storage di `data/raw/spi/` | `ACTIVE` |
| **16** | **Modul Upload & Ingestion Data Operasional** | Data Center / Tombol Input Data | Wizard multi-langkah untuk mengunggah file Excel operasional (Curah Hujan, Probabilitas ECMWF, SPI), validasi format, delta staging, dan commit atomic. | `backend/ingestion_service.py` | `DataIngestionModal.jsx`, `OperationalDataManager.jsx` | MariaDB `staging_rainfall_import`, `cews_ingestion_history` | `ACTIVE` |
| **17** | **Generator SPI Manual Multi-Skala** | Data Center / Sub-fitur SPI | Menjalankan perhitungan ulang SPI historis dan operasional secara paralel menggunakan pustaka Joblib dan pemodelan parameter distribusi terbaik. | `backend/spi_calculation_service.py`, `backend/spi_calculation_worker.py` | `SpiGeneratorModal.jsx` | Time series rainfall di MariaDB, output Parquet | `ACTIVE` |
| **18** | **Autentikasi & Manajemen Sesi Operator** | Halaman Login & Header | Autentikasi terpusat operator BMKG (`klimatkepri` / `OPERATOR_BMKG`) menggunakan JWT token berbasis HttpOnly cookie dan Authorization header. | `backend/auth.py`, `backend/main.py` | `LoginPage.jsx`, `Header.jsx` | Internal auth credential hash & session storage | `ACTIVE` |
| **19** | **Kamus Istilah & Regulasi Teknis** | Tab Navigasi "Kamus Istilah" | Panduan referensi komprehensif terminologi meteorologi, definisi teknis parameter (HTH, SPI, Probabilitas), ambang batas, dan SOP evaluasi. | Statis / Frontend Config | `KamusPage.jsx` | Kamus data internal sistem BMKG | `ACTIVE` |
| **20** | **Shared LAN Server & Auto Launcher** | Launcher Script Windows | Menjalankan server pada IP LAN (Komputer A), memverifikasi kesiapan port dan endpoint `/health`, serta membuka browser default secara otomatis. | `backend/launcher.py`, `run_cews_lan.bat` | Windows Shell / PowerShell | Konfigurasi runtime environment Windows | `ACTIVE` |

---

## 2. ALUR OPERASIONAL PENGOLAHAN DATA UTAMA (DATA PIPELINE FLOW)

```
[ INPUT ] File Excel Operasional (CH Harian / Probabilitas ECMWF / SPI)
    │
    ▼
[ VALIDASI FORMAT ] Pengecekan Header, Tipe Data, Mapping ID Pos 57 Stasiun
    │
    ▼
[ STAGING AREA ] Deteksi Duplikasi, Delta Perubahan (NEW/UPDATED/IDENTICAL)
    │
    ▼
[ COMMIT ATOMIC ] Transaksi database MariaDB & Penyimpanan Parquet
    │
    ▼
[ EVALUASI DECISION ENGINE ] Evaluasi HTH, SPI 90D, Pb20, Pa/PM > 50%
    │
    ▼
[ DASHBOARD & WEBGIS ] Pembaharuan KPI, Tabel Peringatan Dini, & Status Peta
    │
    ▼
[ PENETAPAN OPERATOR ] Penetapan 59 Kecamatan & 7 Kab/Kota (Review / Override)
    │
    ▼
[ OUTPUT RESMI ] Generator Peta JPG BMKG (1653x1170) & JSON Standardized
```

---
*Seluruh fitur yang tercantum telah diuji dan terbukti aktif beroperasi pada sistem per November 2026.*
