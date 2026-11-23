# DOKUMEN SERAH TERIMA PROYEK (PROJECT HANDOVER)
# DECISION SUPPORT SYSTEM PERINGATAN DINI IKLIM (DSS-PIK)
## BMKG Stasiun Meteorologi Kelas II Raja Haji Fisabilillah Tanjungpinang
**Provinsi Kepulauan Riau**  
**Versi Dokumen**: 2.0 (Master Hardened Release)  
**Tanggal Rilis**: 28 Oktober 2026  
**Status Sistem**: Produksi / Operasional Aktif (Ready for Local & LAN Deployment)

---

## DAFTAR ISI
1. [Ringkasan Eksekutif](#1-ringkasan-eksekutif)
2. [Riwayat Pengembangan dari Awal hingga Kondisi Terakhir](#2-riwayat-pengembangan-dari-awal-hingga-kondisi-terakhir)
3. [Arsitektur Sistem](#3-arsitektur-sistem)
4. [Struktur Folder & Direktori Penting](#4-struktur-folder--direktori-penting)
5. [Sumber Data dan Status Otoritatif](#5-sumber-data-dan-status-otoritatif)
6. [Semantik Data Curah Hujan & Integritas HTH](#6-semantik-data-curah-hujan--integritas-hth)
7. [Aturan Operasional Decision Engine (Rules Aktif)](#7-aturan-operasional-decision-engine-rules-aktif)
8. [Mapping Temporal Data (Tanpa Lookahead Bias)](#8-mapping-temporal-data-tanpa-lookahead-bias)
9. [Database MariaDB & Skema Tabel Penting](#9-database-mariadb--skema-tabel-penting)
10. [Fitur Dashboard yang Tersedia](#10-fitur-dashboard-yang-tersedia)
11. [Generator Peta Resmi PDKM & PDCHT](#11-generator-peta-resmi-pdkm--pdcht)
12. [Panduan Operasional Menjalankan Sistem (Runbook)](#12-panduan-operasional-menjalankan-sistem-runbook)
13. [Pengujian, Verifikasi, & Penjaminan Mutu](#13-pengujian-verifikasi--penjaminan-mutu)
14. [Prosedur Backup, Rollback, & Kehati-hatian](#14-prosedur-backup-rollback--kehati-hatian)
15. [Catatan Masalah yang Pernah Terjadi & Solusinya](#15-catatan-masalah-yang-pernah-terjadi--solusinya)
16. [Isu Terbuka & Rekomendasi Pekerjaan Lanjutan](#16-isu-terbuka--rekomendasi-pekerjaan-lanjutan)
17. [Panduan Cepat untuk Pengembang Penerus (Developer Cheat Sheet)](#17-panduan-cepat-untuk-pengembang-penerus-developer-cheat-sheet)
18. [Pengelolaan Periode Real-Time & Launcher Recovery](#18-pengelolaan-periode-real-time--launcher-recovery)
19. [Sistem Ingestion Data Operasional & Optimalisasi Monitoring SPI Multi-Skala](#19-sistem-ingestion-data-operasional--optimalisasi-monitoring-spi-multi-skala-rilis-30-oktober-2026)
20. [Ketahanan Antarmuka & Penanganan Insiden Blank White Page](#20-ketahanan-antarmuka--penanganan-insiden-blank-white-page-pada-modul-ingestion)
21. [Prosedur Operasional Penerimaan Data & Hasil Acceptance Test End-to-End](#21-prosedur-operasional-penerimaan-data-data-ingestion-runbook--hasil-acceptance-test-end-to-end)
22. [Final Hardening Audit, Period-Aware Data Ingestion & Ketahanan Multi-Penyimpanan](#22-final-hardening-audit-period-aware-data-ingestion--ketahanan-multi-penyimpanan-rilis-31-oktober-2026)
23. [Pusat Pengelolaan Data Operasional, Penanganan Vintage, dan Koreksi/Pembatalan Data](#23-pusat-pengelolaan-data-operasional-penanganan-vintage-dan-koreksipembatalan-data-rilis-31-oktober-2026)
24. [Penyempurnaan Final Antarmuka Pengelolaan Data, Periode Dinamis, Validasi Metadata Stasiun & Idempotensi Ingestion](#24-penyempurnaan-final-antarmuka-pengelolaan-data-periode-dinamis-validasi-metadata-stasiun--idempotensi-ingestion-rilis-31-oktober-2026)
25. [Multi-Vintage ECMWF, Sinkronisasi Database & Modernisasi UI](#25-final-refinement--multi-vintage-ecmwf-database-synchronization--ui-modernization-31-oktober-2026)
26. [Penetapan Peringatan Dini Wilayah & Integrasi Publikasi JSON SIH3](#27-penetapan-peringatan-dini-wilayah-7-kabupatenkota--integrasi-publikasi-json-sih3-1-november-2026)
27. [Penyempurnaan Final — Daftar Tunggal 7 Wilayah & Dual Output Generator (JPG + JSON SIH3)](#28-penyempurnaan-final--daftar-tunggal-7-wilayah--dual-output-generator-jpg--json-sih3-1-november-2026)
28. [Penyempurnaan Generator Peta Resmi BMKG, Batas Administratif SHP, Integrasi ZOM & Ekspor JSON](#29-penyempurnaan-generator-peta-resmi-bmkg-batas-administratif-shp-integrasi-zom--ekspor-json-2-november-2026)
29. [Penyempurnaan Ingestion Data Makro Bintan, Filter Pratinjau Periode, SPI Wide Parquet & Sinkronisasi Tabel Data](#30-penyempurnaan-ingestion-data-makro-bintan-filter-pratinjau-periode-spi-wide-parquet--sinkronisasi-tabel-data-2-november-2026)

---

## 1. RINGKASAN EKSEKUTIF

### 1.1 Apa Itu DSS-PIK?
**DSS-PIK** (*Decision Support System Peringatan Dini Iklim*) adalah sistem informasi cerdas berbasis web yang dirancang khusus untuk operasional pemantauan, analisis, evaluasi, dan penerbitan peringatan dini iklim ekstrem di wilayah Provinsi Kepulauan Riau. Sistem ini dioperasikan oleh **Stasiun Meteorologi Kelas II Raja Haji Fisabilillah (RHF) Tanjungpinang**, Badan Meteorologi, Klimatologi, dan Geofisika (BMKG).

### 1.2 Tujuan Utama Sistem
1. **Deteksi Dini Bahaya Kekeringan Meteorologis (PDKM)**: Mengevaluasi Hari Tanpa Hujan (HTH), peluang curah hujan rendah ($<20\text{ mm}$), dan indeks kekeringan *Standardized Precipitation Index* (SPI 30D Dasarian).
2. **Deteksi Dini Bahaya Curah Hujan Tinggi (PDCHT)**: Mengevaluasi potensi hujan lebat dan ekstrem pada skala dasarian ($>150, >200, >300\text{ mm}$) dan bulanan ($>300, >400, >500\text{ mm}$) berbasis ensemble numerik ECMWF.
3. **Membantu Keputusan Operator (Decision Support System)**: Sistem menyajikan rekomendasi objektif berbasis bukti (*evidence-based*), sementara penetapan status resmi per kabupaten/kota tetap berada di tangan operator/prakirawan iklim.
4. **Penerbitan Produk Resmi Siap Sebar**: Menghasilkan peta resmi resolusi tinggi (PNG 150 DPI dan PDF siap cetak) yang menyerupai format baku publikasi BMKG.

### 1.3 Ruang Lingkup Operasional
Sistem memantau **57 stasiun/pos hujan** yang tersebar di 7 wilayah administratif Kepulauan Riau:
- **52 Pos Hujan Manual**: Memiliki data observasi curah hujan harian, deret HTH, SPI 30D, SPI 90D, dan probabilitas model ECMWF.
- **5 Stasiun Otomatis (ARG / AWS)**: Memiliki data observasi curah hujan harian dan deret HTH faktual (dikecualikan dari pemodelan SPI/probabilitas sesuai kebijakan operasional stasiun otomatis).

---

## 2. RIWAYAT PENGEMBANGAN DARI AWAL HINGGA KONDISI TERAKHIR

Pembangunan DSS-PIK melalui serangkaian tahapan rekayasa perangkat lunak dan penyesuaian operasional iklim yang ketat:

1. **Pembangunan Fondasi & Struktur Data Curah Hujan**:
   - Desain skema tabel `cews_rainfall_daily` di MariaDB dengan prinsip integritas relasional terhadap tabel metadata stasiun (`stations`).
   - Implementasi skema *append-only* untuk penambahan data harian baru tanpa merusak data historis.
2. **Koreksi Semantik Simbol Data Curah Hujan**:
   - Standarisasi interpretasi simbol BMKG: angka (curah hujan terukur $\ge 1.0\text{ mm}$), `TTU` (jejak hujan $<0.5\text{ mm}$, dicatat 0.0 mm dan tidak memutus HTH), `-` (hari kering 0.0 mm), dan `X`/kosong (missing data yang memutus HTH secara konservatif).
3. **Pengembangan Dashboard Multi-Periode & Virtualisasi**:
   - Pembuatan antarmuka visual berbasis React + Vite yang mendukung pemilihan dasarian target secara dinamis.
   - Paginasi virtual dan optimasi rendering tabel untuk menangani ribuan rekaman secara instan tanpa lag.
4. **Pusat Data & Import Staging Terkelola**:
   - Penambahan halaman Pusat Data untuk melihat time-series curah hujan, SPI, dan probabilitas ECMWF.
   - Fitur upload data harian dan dasarian melalui tabel staging verifikasi (`staging_rainfall_import`) sebelum di-commit ke database utama.
5. **Autentikasi & Keamanan Akses**:
   - Penerapan autentikasi JWT session token (`backend/auth.py`), membatasi aksi sensitif (import data, simpan keputusan, generate peta) hanya untuk operator berwenang.
6. **Migrasi Penyimpanan SPI ke Format Parquet**:
   - Pemindahan data operasional SPI dasarian dari Excel/CSV lambat ke Apache Parquet (`SPI_all_30d.parquet` dan `SPI_all_90d.parquet`) dengan pembacaan berbasis PyArrow yang menghasilkan kecepatan query $<5\text{ ms}$.
7. **Penyelarasan SPI 30D (Otoritatif) dan SPI 90D (Pendamping)**:
   - Penegasan SPI 30D Dasarian sebagai acuan keputusan operasional resmi PDKM, sedangkan SPI 90D ditampilkan berdampingan sebagai indikator pembanding jangka menengah.
8. **Pengembangan Generator Peta Resmi (Paket 4)**:
   - Modul `backend/map_generator.py` untuk menghasilkan peta A4 landscape (1653 x 1170 piksel) yang otomatis mewarnai kepulauan sesuai status pilihan operator dengan tetap melindungi seluruh garis batas kecamatan, garis provinsi, logo BMKG, dan legenda resmi.
9. **Dukungan Akses Jaringan Lokal (LAN Kantor BMKG RHF)**:
   - Pengikatan server backend ke `0.0.0.0:8000` dan frontend ke `0.0.0.0:5173`, memungkinkan seluruh komputer pegawai di kantor BMKG RHF mengakses dashboard secara bersamaan.
10. **Audit & Penyelarasan Aturan Decision Engine (Aturan Final)**:
    - Pemisahan evaluasi PDKM dan PDCHT menjadi dua pilar independen.
    - Penetapan sintesis status akhir berprinsip *worst-case safety*: $\text{status\_akhir} = \max(\text{status\_pdkm}, \text{status\_pdcht})$.
    - Penerapan aturan data parsial jujur (larangan auto-hijau dan larangan zero-fill).
    - Resolusi isu "57 Stasiun Incomplete" pada target Dasarian II September 2026 (`2026-09-das2`), perbaikan sourcing probabilitas bulanan ECMWF, dan penyempurnaan tipografi judul peta resmi.
11. **Pengelolaan Periode Real-Time Dinamis & UI Responsif**:
    - Perhitungan dasarian aktif berbasis kalender riil WIB (`Asia/Jakarta`) tanpa hardcoding tanggal/bulan/tahun.
    - Penyusunan jendela geser 10 dasarian dinamis serta persistensi preferensi operator di server (`data/operational/period_config.json`).
    - Desain ulang panel pemilih periode pada header dashboard dengan tata letak adaptif (grid dua baris pada layar sempit, flex responsif pada layar lebar) untuk mencegah text-overflow dan penumpukan tombol.
12. **Perbaikan Permanen Startup & Ketahanan Launcher (Eliminasi ERR_CONNECTION_REFUSED)**:
    - Penggantian logika launcher berbasis perintah netstat mentah dengan engine manajemen proses Python berketahanan tinggi (`backend/launcher.py`).
    - Pengecekan kesiapan deterministik berbasis real HTTP GET (`/health` dengan verifikasi koneksi MariaDB dan `/dashboard` dengan verifikasi dokumen HTML aplikasi).
    - Pembukaan peramban web Chrome secara otomatis tepat satu kali **hanya setelah** respons HTTP 200 terverifikasi.
    - Eksekusi langsung biner Vite (`node frontend/node_modules/vite/bin/vite.js`) dengan opsi `strictPort: true` guna mengeliminasi wrapper `npm.cmd` dan perpindahan port.
    - Penjaminan isolasi penghentian layanan (`stop_cews.bat`) berbasis pohon PID tanpa mematikan database MariaDB (Port 3306).

---

## 3. ARSITEKTUR SISTEM

Sistem menggunakan arsitektur modern berbasis klien-server (*decoupled single-page application*):

```
+-----------------------------------------------------------------------------------+
|                            LAPISAN KLIEN (FRONTEND)                               |
|   React 18 + Vite 5 + Leaflet 1.9 Map Engine + Vanilla Modern CSS (Tailwind-Free) |
|   - Dashboard Monitoring & Evaluasi   - Pusat Data & Staging Import               |
|   - Kamus Istilah Iklim & Operasional - Modal Peta Resmi & Ekspor Laporan         |
+-----------------------------------------------------------------------------------+
                                      │  ▲
                         HTTP / REST  │  │  JSON Response
                        Bearer Token  │  │  (Status, Stations, Maps)
                                      ▼  │
+-----------------------------------------------------------------------------------+
|                            LAPISAN SERVER (BACKEND)                               |
|   FastAPI (Python 3.12) + Uvicorn ASGI Server (Host 0.0.0.0, Port 8000)           |
|   - backend/main.py            : API Gateway, Routing, Snapshot Enriched         |
|   - backend/decision_engine.py : Evaluasi Independen PDKM, PDCHT, & Sintesis     |
|   - backend/map_generator.py   : Map Rendering Engine (Pillow, NumPy, Masks)      |
|   - backend/auth.py            : JWT Session Manager & RBAC                       |
|   - backend/database.py        : PyMySQL Connection Pool ke MariaDB               |
+-----------------------------------------------------------------------------------+
             │                                              │
             ▼                                              ▼
+-------------------------+                 +---------------------------------------+
|  DATABASE RELASIONAL    |                 |        PENYIMPANAN DATA FILE          |
|  MariaDB (Port 3306)    |                 |  - Parquet : SPI 30D & SPI 90D        |
|  - cews_rainfall_daily  |                 |  - Excel   : ECMWF Dasarian & Bulanan |
|  - stations (57 pos)    |                 |  - JSON    : Snapshot Periode         |
|  - cews_period_snapshot |                 |  - PNG/PDF : Output Peta Resmi        |
|  - cews_warning_history |                 |  - BaseMap : Template BMKG 1653x1170  |
+-------------------------+                 +---------------------------------------+
```

---

## 4. STRUKTUR FOLDER & DIREKTORI PENTING

| Direktori | Deskripsi & Fungsi Utama |
| :--- | :--- |
| `backend/` | Kode sumber layanan API backend FastAPI (`main.py`, `decision_engine.py`, `map_generator.py`, `auth.py`, `database.py`). |
| `frontend/` | Kode sumber aplikasi antarmuka React (`src/App.jsx`, `src/components/`, `src/config.js`, `package.json`, `dist/`). |
| `config/` | File konfigurasi environment dan database connection template. |
| `data/raw/` | Penyimpanan data mentah observasi curah hujan, file parquet SPI harian/dasarian, dan prakiraan ECMWF. |
| `data/reference/` | Data master stasiun (`stations_master.json`) dan template peta resmi BMKG (`map_templates/04. Peta PDKM_Agustus II 26.jpg`). |
| `data/processed/` | Hasil ekstraksi dan kompilasi data, termasuk file cache snapshot evaluasi (`snapshots/2026-09-das2.json`). |
| `data/operational/` | Direktori output produk resmi operasional (`maps/*.png`, `maps/*.pdf`, `maps/*.json`). |
| `docs/` | Dokumentasi arsitektur, serah terima, kamus data, dan aturan keputusan. |
| `reports/validation/` | Laporan teknis validasi, hasil audit mendalam, dan berita acara penjaminan mutu. |
| `backups/` | Cadangan kode sumber dan snapshot database sebelum modifikasi penting dilakukan. |
| `scratch/` | Skrip-skrip pengujian sementara, utilitas diagnostik, dan analisis ad-hoc. |
| `tests/` | Suite pengujian otomatis berbasis `unittest` untuk menguji logika sistem, database, dan generator peta. |

---

## 5. SUMBER DATA DAN STATUS OTORITATIF

| Nama Sumber Data | Lokasi / Media | Status Otoritatif | Peran dalam Sistem |
| :--- | :--- | :--- | :--- |
| **Curah Hujan Harian** | Tabel MariaDB `cews_rainfall_daily` | **OPERASIONAL UTAMA** | Menghitung Hari Tanpa Hujan (HTH) dan statistik historis 57 stasiun. |
| **Metadata Stasiun** | Tabel MariaDB `stations` & `data/reference/stations_master.json` | **OPERASIONAL UTAMA** | Master data 57 stasiun (ID, nama, koordinat, kabupaten, tipe POS/ARG). |
| **SPI 30D Dasarian** | `data/raw/spi/dasarian/SPI_all_30d.parquet` | **OPERASIONAL UTAMA** | **Acuan Resmi Keputusan PDKM** (menentukan status AWAS/SIAGA/WASPADA). |
| **SPI 90D Dasarian** | `data/raw/spi/dasarian/SPI_all_90d.parquet` | **OPERASIONAL UTAMA** | **Indikator Pendamping** (pemantauan tren kekeringan hidrologis jangka menengah). |
| **SPI Harian** | `data/raw/spi/daily/*.parquet` | **PUSAT DATA** | Visualisasi grafik deret waktu pada modal detail stasiun. |
| **Prob. Dasarian ECMWF** | `tambahan/*.xlsx` (`SepII`) | **OPERASIONAL UTAMA** | Parameter `pb20` (PDKM) serta `pa150`, `pa200`, `pa300` (PDCHT). |
| **Prob. Bulanan ECMWF** | `tambahan/02_EKSTRAK_POS/BULANAN/*.xlsx` | **OPERASIONAL UTAMA** | Parameter `pa300`, `pa400`, `pa500` skala bulanan (PDCHT). |
| **Snapshot Evaluasi** | `data/processed/evaluation/snapshots/*.json` | **OPERASIONAL CACHE** | Cache performa tinggi untuk merender dasarian aktif secara instan. |
| **Template Peta BMKG** | `data/reference/map_templates/04. Peta PDKM_Agustus II 26.jpg` | **OPERASIONAL BASEMAP** | Citra referensi A4 Landscape (1653 x 1170 px) dengan batas kecamatan utuh. |
| **File CSV SPI Lama** | Direktori root / arsip CSV | **DEPRECATED / ARSIP** | Tidak digunakan lagi (telah digantikan penuh oleh Parquet). |

---

## 6. SEMANTIK DATA CURAH HUJAN & INTEGRITAS HTH

Sistem menerapkan konvensi semantik BMKG yang ketat pada pembacaan curah hujan harian:

1. **Angka Numerik $\ge 1.0\text{ mm}$**:
   - Curah hujan terukur signifikan.
   - **Mereset Hari Tanpa Hujan (HTH)** kembali menjadi $0$.
2. **Angka Numerik $0.0\text{ mm}$**:
   - Hari kering terukur tanpa hujan.
   - **Menambah Hari Tanpa Hujan**: $\text{HTH} = \text{HTH} + 1$.
3. **Simbol `TTU` (Tidak Terukur / Trace, $0.1 - 0.4\text{ mm}$)**:
   - Terjadi hujan faktual namun di bawah ambang batas ukur gelas penakar ($<0.5\text{ mm}$).
   - Dalam database numerik dikonversi menjadi $0.0\text{ mm}$.
   - **TIDAK memutus deret HTH** (HTH tetap bertambah $+1$).
4. **Simbol `-` (Tanda Hubung / Strip)**:
   - Menandakan ketiadaan hujan faktual (identik dengan $0.0\text{ mm}$).
   - **Menambah Hari Tanpa Hujan**: $\text{HTH} = \text{HTH} + 1$.
5. **Simbol `X`, `M`, atau Kosong (Missing Data)**:
   - Pengamat tidak mencatat atau transmisi stasiun otomatis terputus.
   - **Prinsip Konservatif**: Memutus perhitungan deret HTH untuk mencegah penumpukan hari kering palsu akibat kekosongan alat.
   - Status kualitas data ditandai sebagai `UNCERTAIN` atau `INCOMPLETE`.
6. **Larangan Zero-Fill**:
   - Sistem **DILARANG KERAS** mengonversi data missing menjadi $0.0\text{ mm}$ secara sepihak.

---

## 7. ATURAN OPERASIONAL DECISION ENGINE (RULES AKTIF)

Logika keputusan berada pada [backend/decision_engine.py](file:///f:/TNJ/paper/DATA_ANALISIS_PRAKIRAAN/CEWS/MAS_HAYU/ASLI/backend/decision_engine.py).

### 7.1 Hierarki Tingkat Peringatan
| Level | Status Kode | Warna Tampilan | Deskripsi Risiko |
| :---: | :--- | :--- | :--- |
| **0** | `NORMAL` / `TIDAK_ADA_PERINGATAN` | Hijau (`#22c55e`) | Parameter aman / normal; tidak ada ancaman iklim ekstrem. |
| **1** | `WASPADA` | Kuning (`#eab308`) | Indikasi awal; kesiapsiagaan dan pemantauan berkala. |
| **2** | `SIAGA` | Oranye (`#f97316`) | Potensi bahaya tinggi; persiapan logistik dan koordinasi teknis. |
| **3** | `AWAS` | Merah (`#ef4444`) | Bahaya ekstrem tertinggi; rekomendasi tanggap darurat segera. |
| **—** | `INCOMPLETE` / `TIDAK_ADA_DATA` | Abu-abu (`#94a3b8`) | Data belum lengkap; tidak dapat dipastikan aman. |

### 7.2 Evaluasi Independen PDKM (Kekeringan Meteorologis)
Tiga indikator kekeringan dievaluasi mandiri tanpa saling mengunci:
1. **Hari Tanpa Hujan (HTH)**:
   $$\text{HTH} \ge 61 \rightarrow \textbf{AWAS (3)}, \quad 31 \le \text{HTH} < 61 \rightarrow \textbf{SIAGA (2)}, \quad 21 \le \text{HTH} < 31 \rightarrow \textbf{WASPADA (1)}, \quad \text{HTH} < 21 \rightarrow \textbf{NORMAL (0)}$$
2. **Probabilitas Curah Hujan Rendah (pb20)**:
   $$\text{Forecast} < 20\text{ mm} \quad\text{DAN}\quad \text{pb20} > 70.0\% \rightarrow \textbf{WASPADA (1)}, \quad\text{Selain itu} \rightarrow \textbf{NORMAL (0)}$$
   *(Catatan: Probabilitas rendah semata dibatasi maksimum menghasilkan WASPADA).*
3. **SPI 30D Dasarian (Acuan Otoritatif Keputusan)**:
   $$\text{SPI} \le -2.00 \rightarrow \textbf{AWAS (3)}, \quad -2.00 < \text{SPI} \le -1.50 \rightarrow \textbf{SIAGA (2)}, \quad -1.50 < \text{SPI} \le -1.00 \rightarrow \textbf{WASPADA (1)}, \quad \text{SPI} > -1.00 \rightarrow \textbf{NORMAL (0)}$$
4. **Formula Status PDKM**:
   $$\text{status\_pdkm} = \max(\text{level\_hth}, \text{level\_prob}, \text{level\_spi})$$

### 7.3 Evaluasi Independen PDCHT (Curah Hujan Tinggi)
Menggunakan ambang batas probabilitas ketat $> 70.0\%$:
1. **Skala Dasarian (Peluang Akumulasi 10 Hari)**:
   $$\text{pa300} > 70.0\% \rightarrow \textbf{AWAS (3)}, \quad \text{pa200} > 70.0\% \rightarrow \textbf{SIAGA (2)}, \quad \text{pa150} > 70.0\% \rightarrow \textbf{WASPADA (1)}$$
2. **Skala Bulanan (Peluang Akumulasi 1 Bulan)**:
   $$\text{Peluang } >500\text{ mm} > 70.0\% \rightarrow \textbf{AWAS (3)}, \quad >400\text{ mm} > 70.0\% \rightarrow \textbf{SIAGA (2)}, \quad >300\text{ mm} > 70.0\% \rightarrow \textbf{WASPADA (1)}$$
3. **Formula Status PDCHT**:
   $$\text{status\_pdcht} = \max(\text{level\_dasarian}, \text{level\_bulanan})$$

### 7.4 Sintesis Status Akhir & Hazard Attribution (Worst-Case Principle)
$$\text{status\_akhir} = \max(\text{status\_pdkm}, \text{status\_pdcht})$$
- Jika $\text{status\_pdkm} > \text{status\_pdcht} \rightarrow \textbf{DROUGHT (Kekeringan Meteorologis)}$
- Jika $\text{status\_pdcht} > \text{status\_pdkm} \rightarrow \textbf{HEAVY\_RAIN (Curah Hujan Tinggi)}$
- Jika $\text{status\_pdkm} == \text{status\_pdcht} > 0 \rightarrow \textbf{MULTI\_HAZARD (Bahaya Ganda)}$
- Jika keduanya Level 0 $\rightarrow \textbf{NORMAL (Aman)}$

### 7.5 Kebijakan Data Parsial & Stasiun ARG
- **Larangan Auto-Hijau**: Jika parameter wajib belum lengkap, stasiun tidak boleh diberi status aman (`NORMAL`).
- **Evaluasi Parsial Jujur**: Jika salah satu indikator yang tersedia melampaui ambang bahaya (misal HTH 35 hari $\rightarrow$ SIAGA), peringatan tetap ditampilkan disertai catatan `(Evaluasi Parsial)`.
- **Kebijakan Stasiun ARG**: 5 stasiun ARG dievaluasi berbasis HTH observasi. Jika data HTH valid, evaluasi stasiun berstatus $\textbf{COMPLETE}$.

---

## 8. MAPPING TEMPORAL DATA (TANPA LOOKAHEAD BIAS)

Sistem mematuhi kaidah operasional BMKG mengenai garis waktu peringatan iklim:

```
                  CUTOFF OBSERVASI CH
                  (Akhir Dasarian I Sep: 10 Sep 23:59 WIB)
                             │
                             ▼
──[ Observasi Faktual HTH ]──┼──[ Periode Target Peringatan Dini ]──►
  (Data historis s.d. 10 Sep)│     (Dasarian II September 2026: 11-20 Sep)
                             │
                             ├─► [ Prakiraan ECMWF Dasarian: Siklus terbit <= 10 Sep ]
                             ├─► [ Prakiraan ECMWF Bulanan : Siklus terbit untuk Sep ]
                             └─► [ SPI 30D Otoritatif      : Nilai Dasarian 1 Sep ]
```

1. **Jendela Cutoff Observasi**:
   - Untuk target Dasarian II September (11–20 September), cutoff observasi adalah tanggal **10 September pukul 23.59 WIB**.
   - Tidak ada data observasi dari tanggal 11 September ke atas yang boleh masuk ke dalam evaluasi target Dasarian II (*Zero Lookahead Bias*).
2. **Prakiraan ECMWF Dasarian**:
   - Menggunakan ensemble run ECMWF terdekat yang terbit sebelum tanggal 11 September (misalnya file terbit tanggal 9 September).
3. **SPI 30D Dasarian**:
   - Menggunakan nilai SPI 30 hari yang terhitung pada tanggal cutoff observasi (1 September 2026).

---

## 9. DATABASE MARIADB & SKEMA TABEL PENTING

Database MariaDB berjalan pada port `3306` dengan nama database `cews_db`.

| Nama Tabel | Jumlah Baris (Baseline) | Fungsi & Keterangan |
| :--- | :---: | :--- |
| `stations` | 57 | Metadata 57 stasiun/pos hujan (ID, nama, latitude, longitude, elevasi, kabupaten, jenis POS/ARG). |
| `cews_rainfall_daily` | **286.085** | **Tabel Inti**: Deret waktu curah hujan harian per pos sejak tahun 2010. Dikelola dengan aturan *append-only*. |
| `cews_period_snapshot` | Dinamis (57 per periode) | Snapshot hasil evaluasi sintesis lengkap untuk melayani query API frontend secara cepat. |
| `cews_current_warning` | 57 | Status peringatan dini aktif terkini per stasiun untuk dasarian berjalan. |
| `cews_warning_history` | **2.052** | Arsip histori peringatan dini multi-tahun yang telah diterbitkan sebelumnya. |
| `staging_rainfall_import`| Transien | Tabel penampungan sementara saat operator melakukan upload file curah hujan harian/dasarian. |
| `cews_rainfall_correction_log` | Dinamis | Log audit trail pencatatan setiap koreksi manual terhadap data curah hujan. |

---

## 10. FITUR DASHBOARD YANG TERSEDIA

### 10.1 Halaman Monitoring & Evaluasi (Peringatan Dini)
1. **Header & Pemilih Periode (2-Tier Responsive Layout)**:
   - *Tier 1 (Header Status)*: Label "Periode Peringatan Dini", badge mode operasional (`[Real-Time]` atau `[Mode Manual]`), tombol `[Ikuti Waktu Real-time]` (tersedia saat mode manual), dan badge kelengkapan data (`[Terverifikasi]` atau `[Data Parsial]`).
   - *Tier 2 (Full-Width Dropdown)*: Selektor dasarian selebar kontainer tanpa batasan rigid `max-width` yang menyajikan jendela geser 10 dasarian serta opsi custom lintas bulan/tahun (`➕ Pilih Periode Dasarian Lain...`).
   - *Pemberitahuan Lagging*: Menampilkan bar peringatan operasional otomatis jika tanggal cutoff periode aktif melampaui data observasi terakhir di database.
2. **Grid Kartu KPI Interaktif**:
   - *Total Stasiun (57)*: Klik kartu ini memfokuskan peta Leaflet ke seluruh batas geografis Kepulauan Riau (`KEPRI_BOUNDS`).
   - *Awas, Siaga, Waspada, Normal*: Klik kartu menyaring tabel dan peta sesuai tingkat peringatan.
   - *Tidak Lengkap*: Menampilkan stasiun yang memerlukan kelengkapan data.
3. **Peta Interaktif Leaflet**:
   - Marker stasiun dengan warna sesuai status peringatan.
   - Tooltip dan popup detail saat marker diklik.
   - Mendukung filter spasial per kabupaten/kota.
4. **Tabel Pemantauan Lengkap**:
   - Menampilkan kolom HTH, pb20, SPI 30D (Otoritatif), SPI 90D (Pendamping), Status PDKM, Prob Dasarian (pa150/pa200/pa300), Status PDCHT, Status Akhir, dan Status Evaluasi.
   - Dilengkapi pencarian cepat (*fuzzy quick search*) dan paginasi virtual.
5. **Modal Detail Stasiun**:
   - Analisis mendalam per pos: grafik deret waktu curah hujan, grafik SPI harian, dan tombol ekspor data pos ke format CSV.
6. **Modal Peta Resmi BMKG**:
   - Membuka antarmuka penetapan status per kabupaten dan pembuatan peta publikasi resmi.

### 10.2 Halaman Data (Pusat Data & Import)
- **Tab Input Harian**: Form penginputan manual nilai curah hujan harian untuk pos tertentu.
- **Tab Import Staging**: Pengunggahan file Excel/CSV curah hujan dengan validasi semantik sebelum di-commit.
- **Tab Pusat Data**: Penjelajah data multi-parameter (Curah Hujan, SPI, Probabilitas) dengan fitur unduh dataset lengkap.

### 10.3 Halaman Kamus Istilah
- Kamus interaktif dengan 4 kategori: *Meteorologi*, *Operasional DSS-PIK*, *Indeks Iklim*, dan *Teknologi*.
- Terintegrasi penuh dengan prinsip evaluasi independen, worst-case safety, dan kebijakan integritas data BMKG.

---

## 11. GENERATOR PETA RESMI PDKM & PDCHT

Modul: [backend/map_generator.py](file:///f:/TNJ/paper/DATA_ANALISIS_PRAKIRAAN\CEWS\MAS_HAYU\ASLI\backend\map_generator.py)

### 11.1 Alur Kerja Operator
1. Operator membuka tombol **Peta Resmi** pada dashboard.
2. Sistem menyajikan ringkasan statistik stasiun per kabupaten sebagai panduan rekomendasi.
3. Operator memilih status resmi untuk masing-masing 7 kabupaten/kota (prinsip *decision support*).
4. Operator menekan tombol **Generate Peta Resmi**.
5. Backend merender peta dan mengembalikan URL download untuk file PNG dan PDF.

### 11.2 Spesifikasi Layout & Tipografi Peta
- **Dimensi**: 1653 x 1170 piksel (A4 Landscape, 150 DPI).
- **Template Dasar**: `data/reference/map_templates/04. Peta PDKM_Agustus II 26.jpg`.
- **Panel Kiri Bawah (Panel Judul)**:
  - Kotak batas luar utuh: $x \in [64, 577]$, $y \in [808, 1150]$.
  - Area pembersihan teks: $x \in [68, 573]$, $y \in [814, 927]$ (menjaga garis bingkai dan logo BMKG di $y \ge 932$).
  - Titik tengah horizontal: $cx = 318$ (presisi 100% dengan center template asli).
  - Font: `arialbd.ttf` (Arial Bold) ukuran 23.
  - Susunan 4 baris teks:
    * Baris 1 ($y_{\text{top}} = 821$): `PETA PERINGATAN DINI`
    * Baris 2 ($y_{\text{top}} = 850$): `KEKERINGAN METEOROLOGIS` (PDKM) atau `CURAH HUJAN TINGGI` (PDCHT)
    * Baris 3 ($y_{\text{top}} = 879$): `DASARIAN [I/II/III] [BULAN] [TAHUN]`
    * Baris 4 ($y_{\text{top}} = 907$): `PROVINSI KEPULAUAN RIAU`
- **Panel Tengah Bawah (Panel Legenda)**:
  - Bagian KETERANGAN: Batas Provinsi (garis putus-putus merah) dan Batas Kecamatan (garis hitam solid).
  - Bagian KLASIFIKASI: Tidak Ada Data (putih), Waspada (kuning), Siaga (oranye), Awas (merah), Tidak Ada Peringatan (hijau).
- **Panel Kanan Bawah**:
  - Kompas mata angin bintang (N, E, S, W).
  - Skala batang 200 km.
  - Teks atribusi sumber peta: 1. Peta Rupa Bumi - BIG, 2. Data Curah Hujan - BMKG.
- **Proteksi Garis Batas & Pulau**:
  - Algoritma pencocokan luminansi (`lum < 65`) melindungi seluruh garis batas kecamatan dan pantai agar tetap tampak tajam di atas warna status wilayah.
  - Masking spasial 100% mencakup seluruh pulau di Kepulauan Riau termasuk Pulau Singkep, Lingga, Karimun, Kundur, Batam, Rempang, Galang, Bintan, Tanjungpinang, Anambas, dan Natuna.

---

## 12. PANDUAN OPERASIONAL MENJALANKAN SISTEM (RUNBOOK)

### 12.1 Persyaratan Lingkungan (Prerequisites)
- Sistem Operasi: Windows 10/11 atau Windows Server (tersedia skrip batch portabel).
- Python: Versi 3.10 atau lebih baru (Python 3.12 direkomendasikan).
- Node.js: Versi 18 atau lebih baru dengan npm.
- Database: MariaDB / MySQL 10.4+ pada port `3306` (tersedia di `C:\Users\vasco\mariadb-11.4\bin\mariadbd.exe`).

### 12.2 Menjalankan dan Menghentikan Sistem (Launcher Resmi)

Pengoperasian sistem telah disederhanakan menjadi tepat **DUA launcher operasional** pada root repositori yang ditenagai oleh engine ketahanan proses Python (`backend/launcher.py`):

#### A. Menjalankan Seluruh Layanan & Membuka Dashboard (`run_cews.bat`)
Buka File Explorer atau terminal di root folder proyek, lalu jalankan:
```bat
run_cews.bat
```
Skrip ini secara otomatis:
1. Menentukan direktori kerja secara portabel menggunakan `%~dp0`.
2. Memeriksa ketersediaan Python 3.10+, Node.js 18+, dan folder `frontend/node_modules`.
3. Memeriksa status MariaDB di port 3306; jika belum aktif, MariaDB dijalankan di latar belakang.
4. Memeriksa backend di port 8000; jika belum berjalan, menjalankan FastAPI Uvicorn dengan binding `0.0.0.0:8000` (siap akses lokal dan LAN kantor).
5. Memeriksa frontend di port 5173; jika belum berjalan, menjalankan Vite secara langsung via `node.exe` dengan opsi `strictPort: true` dan host `0.0.0.0:5173` (mengeliminasi wrapper `npm.cmd` dan mencegah perpindahan port ke 5174).
6. Melakukan inspeksi kesiapan deterministik berbasis real HTTP GET:
   - Backend: `http://127.0.0.1:8000/health` (memvalidasi respons `200 OK` dan status database `"connected"`).
   - Frontend: `http://127.0.0.1:5173/` dan `http://127.0.0.1:5173/dashboard` (memvalidasi respons `200 OK` dan dokumen HTML aplikasi).
7. Mencatat PID proses aktif ke `logs/runtime/backend.pid` dan `frontend.pid`, serta mencatat runtime log ke:
   - `logs\runtime\backend.log`
   - `logs\runtime\frontend.log`
   - `logs\runtime\launcher.log`
8. Mencegah pembuatan instance duplikat jika port sudah aktif dan sehat.
9. **Membuka browser default tepat satu kali** menuju `http://localhost:5173/dashboard` **hanya setelah** kedua layanan terverifikasi 100% siap via HTTP (mengeliminasi galat `ERR_CONNECTION_REFUSED`).

#### B. Menghentikan Seluruh Layanan Secara Aman (`stop_cews.bat`)
Ketika jam operasional selesai atau operator ingin mematikan sistem, jalankan:
```bat
stop_cews.bat
```
Skrip ini secara otomatis:
1. Membaca PID terdaftar dari `backend.pid` dan `frontend.pid`, serta memindai proses yang mendengarkan di port 8000 dan 5173.
2. Memverifikasi identitas proses (*process identity check*) untuk memastikan hanya proses DSS-PIK yang dihentikan.
3. Menghentikan proses secara bertahap: *graceful termination* (`SIGTERM`), *force kill* (`SIGKILL`), dan fallback Windows (`taskkill /F /T /PID <PID>`).
4. Menunggu hingga port benar-benar terbebas dari status `LISTENING` sebelum melanjutkan.
5. **Melindungi Database MariaDB**: Port 3306 TETAP AKTIF dan tidak dimatikan guna menjaga integritas transaksi database dan melayani proses BMKG lainnya.
6. Menghapus berkas `.pid` lama dan menampilkan ringkasan jumlah layanan yang dihentikan.

### 12.3 Prosedur Diagnosis Masalah Startup & Pemeriksaan Status
Jika terjadi kendala saat menjalankan sistem:
1. **Periksa Status Layanan via CLI**:
   ```cmd
   python -m backend.launcher status
   ```
2. **Port 8000/5173 Terkunci atau Perlu Restart**: Jalankan `stop_cews.bat`, tunggu 2 detik, lalu jalankan `run_cews.bat` kembali.
3. **Database Tidak Terhubung**: Pastikan MariaDB aktif di port 3306. Periksa kredensial di file `.env`.
4. **Log Runtime Terpusat**: Seluruh output diagnostik tersimpan di folder `logs/runtime/`:
   - `logs/runtime/launcher.log`: Riwayat startup, polling kesiapan, PID, dan penghentian layanan.
   - `logs/runtime/backend.log`: Log server Uvicorn dan penanganan request API.
   - `logs/runtime/frontend.log`: Log bundler Vite dan serving assets web GIS.

### 12.4 Mengakses dari Jaringan Kantor (LAN BMKG RHF)
1. Cek alamat IP server di jaringan kantor melalui perintah `ipconfig` (misalnya `192.168.1.50`).
2. Seluruh komputer klien di jaringan WiFi/LAN kantor dapat mengakses dashboard melalui:
   `http://192.168.1.50:5173/`

### 12.5 Status Berkas Launcher
- **Berkas Resmi di Root**:
  - `run_cews.bat` (Start all services + open browser)
  - `stop_cews.bat` (Stop services safely via PID isolation)
- **Berkas yang Telah Diarsipkan ke `backups/launcher_archive/`**:
  - `buka_dashboard.bat` (Disatukan ke dalam `run_cews.bat`)
  - `buka_dashboard_cews.bat` (Wrapper lama diarsipkan)
  - `run_cews_demo.bat` (Launcher demo lama diarsipkan)
  - `stop_cews_demo.bat` (Skrip taskkill agresif digantikan oleh `stop_cews.bat`)

---

## 13. PENGUJIAN, VERIFIKASI, & PENJAMINAN MUTU

Sistem dilengkapi suite pengujian otomatis komprehensif (38 kasus uji) untuk memverifikasi fungsionalitas, integritas data, aturan operasional BMKG, dan launcher Windows:

### 13.1 Menjalankan Test Suite Otomatis
```powershell
# 1. Test Suite Audit & Aturan Operasional (16 unittest)
python tests/test_audit_incomplete_and_ui_refinements.py

# 2. Test Suite Period Management Real-Time, Launcher, & Database Baselines (11 pytest)
python -m pytest tests/test_realtime_period_and_launcher_recovery.py -v

# 3. Test Suite Audit Refinement (7 pytest)
python -m pytest tests/test_audit_incomplete_and_ui_refinement.py -v

# 4. Test Suite Penerimaan Regresi Keputusan (3 pytest)
python -m pytest tests/regression/test_october_2026_acceptance.py -v

# 5. Test Suite Integrasi Dashboard Kontrak Klien (1 pytest)
python -m pytest tests/integration/test_dashboard_contract.py -v
```

*Ringkasan Hasil Uji Keseluruhan*:
```
======================== 38 passed in 12.3s (100% PASS) ========================
```

### 13.2 Cakupan Kasus Uji Otomatis
1. **Aturan Evaluasi BMKG**: Boundary testing HTH (0, 20, 21, 30, 31, 60, 61, 100 hari), probabilitas pb20 ($70.0\%$), dan SPI 30D ($-0.99, -1.00, -1.49, -1.50, -1.99, -2.00$).
2. **Pilar Independen PDKM & PDCHT**: Evaluasi independen tanpa cross-contamination, worst-case safety synthesis, dan penanganan data parsial jujur.
3. **Stasiun ARG**: Validitas observasi HTH ARG tanpa penalti incompleteness palsu.
4. **Kalender Real-Time & Dasarian Dinamis**: Perhitungan dasarian aktual WIB (Asia/Jakarta), transisi akhir bulan, pergantian tahun, dan tahun kabisat (Februari 29 hari).
5. **Jendela Geser 10 Dasarian**: Pembangkitan deret 10 dasarian dinamis dengan pemetaan SPI 30D otoritatif & SPI 90D pendamping.
6. **Persistensi Konfigurasi Server**: Penyimpanan mode `auto` / `manual` pada `data/operational/period_config.json` yang konsisten untuk seluruh klien LAN.
7. **Audit Kesiapan Data & Lagging**: Deteksi keterlambatan data observasi terhadap cutoff periode aktif tanpa mengunci fungsi navigasi operator.
8. **Simplifikasi Launcher Windows**: Verifikasi keberadaan tepat 2 launcher resmi (`run_cews.bat` dan `stop_cews.bat`), ketiadaan launcher redundan di root, dan isolasi terminasi PID.
9. **Integritas Baseline Data Operasional**: Verifikasi bahwa tidak ada perubahan baris pada `cews_rainfall_daily` (286.085), `cews_warning_history` (2.052), `stations` (57), dan checksum 4 file SPI Parquet.

---

## 14. PROSEDUR BACKUP, ROLLBACK, & KEHATI-HATIAN

### 14.1 Lokasi Backup Penting
Sebelum melakukan perubahan kode atau database, salinan cadangan disimpan pada folder `backups/`:
- `backups/backup_audit_incomplete_20261027/`: Backup kode sumber engine dan frontend sebelum audit incomplete.
- `backups/backup_map_and_handover_20261027/`: Backup modul generator peta sebelum refinement layout.

### 14.2 Aturan Kehati-hatian (Golden Rules)
1. **Dilarang Mengubah Data Mentah Secara Destruktif**: Tabel `cews_rainfall_daily` berisi 286.085 baris data historis yang tidak boleh di-update massal atau di-truncate.
2. **Snapshot Bersifat Append / Cached**: Jangan menimpa snapshot periode lama yang sudah terbit secara operasional.
3. **Parquet Read-Only**: File `SPI_all_30d.parquet` dan `SPI_all_90d.parquet` tidak boleh dimodifikasi di tempat tanpa skrip generator resmi yang terverifikasi.
4. **Kredensial Sensitif**: Jangan pernah memasukkan kata sandi, secret key, atau isi file `.env` ke dalam berkas dokumentasi publik atau repositori git.

---

## 15. CATATAN MASALAH YANG PERNAH TERJADI & SOLUSINYA

| Isu / Bug | Gejala Masalah | Akar Penyebab | Solusi yang Diterapkan |
| :--- | :--- | :--- | :--- |
| **Isu 57 Stasiun Incomplete (Sep II 2026)** | Seluruh 57 stasiun berstatus "TIDAK LENGKAP" di dashboard. | Script snapshot membaca file probabilitas bulanan yang tidak memiliki kolom `Sep`, sehingga data bulanan null dan mengunci status sistem. | Memperbaiki sumber data ke file ECMWF bulanan yang benar, memperbaiki logika decision engine agar menoleransi evaluasi parsial jujur, dan memperbarui snapshot di JSON & database. |
| **Bug Probabilitas 9600%** | Nilai probabilitas tampil ribuan persen pada UI. | Terjadi perkalian ganda `x * 100` pada data yang sudah berformat persentase (0–100). | Standarisasi skala probabilitas: nilai disimpan murni 0.0–100.0, format persen hanya diterapkan satu kali di view. |
| **Singkep Tidak Terwarnai di Peta** | Pulau Singkep dan Lingga Barat tetap berwarna template lama saat Lingga berstatus Siaga/Awas. | Masking koordinat Lingga lama dimulai dari $x \ge 400$, padahal Singkep berada di $x \in [178, 399]$. | Memperluas masking Lingga ke $x \ge 150$ untuk $y \ge 425$, sehingga 100% pulau Lingga dan Singkep terwarnai sempurna. |
| **Judul Peta Menabrak Legenda** | Teks judul pada peta terpotong atau menabrak kotak keterangan di sisi kanan. | Titik tengah horizontal disetel di $cx = 505$ (kotak keseluruhan), padahal kotak judul berada di kiri bawah dengan $cx = 318$. | Menyetel $cx = 318$, membatasi clear box di $x \in [68, 573]$, dan menggunakan font Arial Bold 23 dengan spasi baris presisi. |
| **Stasiun ARG Ditandai Incomplete** | 5 stasiun ARG selalu berstatus Incomplete meskipun observasi HTH valid. | Terdapat hardcode di backend yang menandai stasiun ARG Incomplete karena tidak memiliki data SPI/model. | Menerapkan kebijakan resmi stasiun ARG: stasiun ARG berstatus `COMPLETE` jika observasi HTH valid. |
| **Banyaknya Launcher & Kebocoran Proses** | Terlalu banyak file `.bat` di root, proses Python/Node menggantung, dan skrip stop mematikan sembarang proses. | Duplikasi script launcher lama (`run_cews_demo.bat`, `buka_dashboard.bat`, `stop_cews_demo.bat`) tanpa targeting PID spesifik. | Menyederhanakan menjadi tepat 2 launcher resmi (`run_cews.bat` & `stop_cews.bat`). Menggunakan targeting PID berbasis `netstat` dan mengarsipkan launcher lama ke `backups/launcher_archive/`. |
| **Overflow Visual Panel Periode** | Badge `[MODE MANUAL]`, tombol `[Ikuti Waktu Real-time]`, dan status data meluap keluar batas kartu di UI. | Struktur 1-baris datar pada `.period-selector-container` dengan pembatas lebar rigid (`max-width: 500px`) dan `white-space: nowrap`. | Merestrukturisasi menjadi layout bertingkat 2-Tier: Tier 1 untuk header label/mode/tombol/status, Tier 2 untuk dropdown selector selebar 100% kontainer yang fleksibel dan bebas overflow. |
| **ERR_CONNECTION_REFUSED Saat Restart Sistem** | Chrome menampilkan `ERR_CONNECTION_REFUSED` pada `http://localhost:5173/dashboard` setelah sistem ditutup dan dijalankan ulang. | 1) Bug parentesis tak ter-escape pada skrip stop batch menutup loop `do` prematur sehingga proses zombie tak terbunuh; 2) Pengecekan netstat tanpa filter listening mencocokkan soket `TIME_WAIT` dan membuka browser sebelum Vite siap; 3) Pembungkus `npm.cmd` menggantung; 4) Vite port hopping ke 5174. | Membangun engine proses berketahanan tinggi (`backend/launcher.py`), mengonfigurasi `strictPort: true` pada Vite, menerapkan polling kesiapan real HTTP GET (`/health` & `/dashboard`), dan membuka browser tepat satu kali **hanya setelah** respons HTTP 200 OK diverifikasi faktual. |

---

## 16. ISU TERBUKA & REKOMENDASI PEKERJAAN LANJUTAN

Bagi pengembang atau petugas BMKG yang akan melanjutkan pengembangan DSS-PIK ke depan, berikut beberapa rekomendasi strategis:

1. **Otomatisasi Pipeline Ingesti Prakiraan ECMWF**:
   - Saat ini file ECMWF perpos dimasukkan secara manual ke folder `tambahan/`. Disarankan membangun modul *scheduled ingestion* (menggunakan Airflow atau Windows Task Scheduler) untuk mengunduh dan mengekstrak file ECMWF dari server BMKG Pusat secara otomatis setiap tanggal 1, 10, dan 20.
2. **Template Terpisah untuk PDCHT Khusus**:
   - Saat ini generator peta menggunakan template dasar `04. Peta PDKM_Agustus II 26.jpg` dengan penyesuaian dinamis judul "CURAH HUJAN TINGGI". Jika BMKG Pusat di masa mendatang merilis format basemap khusus PDCHT dengan skema warna yang berbeda, modul `backend/map_generator.py` dapat dikembangkan untuk memuat template basemap terpisah sesuai `map_type`.
3. **Integrasi Notifikasi Peringatan Dini Otomatis**:
   - Menambahkan webhook pengiriman ringkasan peringatan dini (PDF dan infografis) secara otomatis ke grup WhatsApp atau Telegram BPBD Provinsi Kepulauan Riau saat operator memfinalisasi peta resmi.

---

## 17. PANDUAN CEPAT UNTUK PENGEMBANG PENERUS (DEVELOPER CHEAT SHEET)

| Komponen | File Utama | Hal Penting yang Perlu Diketahui |
| :--- | :--- | :--- |
| **API Server** | [backend/main.py](file:///f:/TNJ/paper/DATA_ANALISIS_PRAKIRAAN/CEWS/MAS_HAYU/ASLI/backend/main.py) | Entry point FastAPI. Endpoint `/api/v1/hth` melayani tabel pemantauan, `/api/v1/periods` melayani list periode, `/api/v1/maps/generate` melayani render peta. |
| **Decision Engine** | [backend/decision_engine.py](file:///f:/TNJ/paper/DATA_ANALISIS_PRAKIRAAN/CEWS/MAS_HAYU/ASLI/backend/decision_engine.py) | Logika murni evaluasi PDKM, PDCHT, dan arbitrase status akhir. Selalu jalankan `test_audit_incomplete_and_ui_refinements.py` jika mengubah file ini. |
| **Map Generator** | [backend/map_generator.py](file:///f:/TNJ/paper/DATA_ANALISIS_PRAKIRAAN/CEWS/MAS_HAYU/ASLI/backend/map_generator.py) | Engine rendering peta dengan Pillow. Mengatur warna status regency, proteksi garis batas, dan tipografi judul 4 baris. |
| **Frontend Root** | [frontend/src/App.jsx](file:///f:/TNJ/paper/DATA_ANALISIS_PRAKIRAAN/CEWS/MAS_HAYU/ASLI/frontend/src/App.jsx) | State manajemen utama React: filter periode, KPI counts, search query, dan sinkronisasi peta/tabel. |
| **Peta Interaktif** | [frontend/src/components/MapLeaflet.jsx](file:///f:/TNJ/paper/DATA_ANALISIS_PRAKIRAAN/CEWS/MAS_HAYU/ASLI/frontend/src/components/MapLeaflet.jsx) | Komponen peta Leaflet. Mengelola zoom, cluster stasiun, boundary Kepri, dan event `focusTrigger`. |
| **Modal Peta Resmi**| [frontend/src/components/OfficialMapModal.jsx](file:///f:/TNJ/paper/DATA_ANALISIS_PRAKIRAAN/CEWS/MAS_HAYU/ASLI/frontend/src/components/OfficialMapModal.jsx) | Dialog penetapan status 7 kabupaten/kota dan pratinjau peta resmi hasil generator. |
| **Kamus Istilah** | [frontend/src/components/KamusPage.jsx](file:///f:/TNJ/paper/DATA_ANALISIS_PRAKIRAAN/CEWS/MAS_HAYU/ASLI/frontend/src/components/KamusPage.jsx) | Halaman referensi operasional dan istilah teknis iklim. |
| **Test Suite** | [tests/test_audit_incomplete_and_ui_refinements.py](file:///f:/TNJ/paper/DATA_ANALISIS_PRAKIRAAN/CEWS/MAS_HAYU/ASLI/tests/test_audit_incomplete_and_ui_refinements.py) | Test suite wajib dijalankan sebelum melakukan deployment atau rilis versi baru. |
| **Period Service** | [backend/period_service.py](file:///f:/TNJ/paper/DATA_ANALISIS_PRAKIRAAN/CEWS/MAS_HAYU/ASLI/backend/period_service.py) | Pengelolaan kalender dinamis dasarian (WIB), rolling 10-dasarian window, audit kesiapan data, dan preview on-the-fly. |
| **Test Suite Periode & Launcher** | [tests/test_realtime_period_and_launcher_recovery.py](file:///f:/TNJ/paper/DATA_ANALISIS_PRAKIRAAN/CEWS/MAS_HAYU/ASLI/tests/test_realtime_period_and_launcher_recovery.py) | Suite pengujian otomatis kalender dasarian, mode auto/manual, audit lagging, checksum SPI, dan skrip launcher. |

---

## 18. PENGELOLAAN PERIODE REAL-TIME, MODE MANUAL, & LAUNCHER (RILIS 28 OKTOBER 2026)

Modul Utama: [backend/period_service.py](file:///f:/TNJ/paper/DATA_ANALISIS_PRAKIRAAN/CEWS/MAS_HAYU/ASLI/backend/period_service.py)

### 18.1 Kalender Dasarian Dinamis Real-Time (WIB / Asia/Jakarta)
Sistem menggunakan waktu aktual server dalam zona waktu `Asia/Jakarta` (WIB, UTC+7) sebagai sumber kebenaran tunggal (*single source of truth*).
- **Dasarian I**: Tanggal 1 s.d. 10.
- **Dasarian II**: Tanggal 11 s.d. 20.
- **Dasarian III**: Tanggal 21 s.d. hari terakhir bulan (28/29 untuk Februari, 30, atau 31).
Perhitungan menangani pergantian bulan, pergantian tahun, dan tahun kabisat secara matematis.

### 18.2 Mode Operasional: Otomatis vs Manual
Sistem menyediakan dua mode operasional:
1. **Mode A — Otomatis (Real-Time)**:
   - Sistem menentukan periode aktif berdasarkan tanggal jam server aktual.
   - Mengikuti pergantian dasarian secara dinamis tanpa perlu intervensi operator.
   - Ditandai dengan badge biru `[Real-Time (Otomatis)]` pada bilah periode dashboard.
2. **Mode B — Manual (Pilihan Petugas)**:
   - Petugas dapat memilih periode dasarian aktif secara eksplisit melalui dropdown atau tombol `Pilih Periode Dasarian Lain...`.
   - Dapat mencakup periode historis maupun periode masa depan yang belum memiliki snapshot.
   - Pilihan manual disimpan di sisi server pada:
     `data/operational/period_config.json`
     Hal ini memastikan pilihan periode konsisten di seluruh komputer klien dan perangkat yang mengakses server melalui jaringan LAN kantor.
   - Ditandai dengan badge oranye `[Mode Manual]` disertai tombol:
     `[Ikuti Waktu Real-time]`
     Klik tombol ini akan mengembalikan sistem ke mode otomatis kalender server.
   - Panel pemilih periode menggunakan **layout bertingkat 2-Tier**: Tier 1 untuk header status (label, mode badge, switch button, status kelengkapan data), dan Tier 2 untuk dropdown selector selebar kontainer tanpa batasan kaku `max-width` yang mencegah visual overflow pada segala kombinasi badge dan resolusi layar operator.

### 18.3 Pembentukan Jendela Rolling 10 Dasarian
Untuk setiap periode aktif yang terpilih:
- Diambil **9 dasarian tepat sebelumnya** sebagai riwayat secara kronologis.
- Ditambah **1 dasarian aktif** di ujung kanan jendela.
- Total selalu tepat **10 dasarian**, tanpa duplikasi dan tanpa celah kalender.
- Jendela otomatis bergeser jika periode aktif berubah.

### 18.4 Pemisahan Periode Kalender dari Kesiapan Data (Decoupled Readiness)
Periode aktif ditentukan oleh waktu kalender atau pilihan manual, sedangkan kesiapan evaluasi ditentukan oleh ketersediaan data aktual di database:
- **Status Kesiapan Evaluasi**:
  * `READY` (Hijau): Data observasi curah hujan lengkap ($\ge 50$ stasiun) pada tanggal cutoff dan SPI 30D tersedia.
  * `PARTIAL` (Kuning): Sebagian parameter observasi atau SPI tersedia ($\ge 30$ stasiun).
  * `LAGGING` (Oranye/Merah): Data observasi curah hujan di database tertinggal di belakang tanggal cutoff periode aktif. Sistem menampilkan spanduk peringatan eksplisit:
    > **Pemberitahuan Operasional**: Periode aktif (misal Dasarian III Oktober 2026) melampaui data observasi terakhir di database (11 Oktober 2026). Evaluasi berstatus data parsial/sementara.
  * `NOT_READY` (Merah): Data observasi belum mencukupi.

### 18.5 Arsitektur Pratinjau Dinamis (Dynamic Preview)
Jika operator memilih periode baru yang belum memiliki file snapshot historis:
- Sistem menjalankan fungsi `generate_dynamic_snapshot_for_period(period_id)`.
- Evaluasi dihitung secara langsung (*on-the-fly*) dari data observasi harian, SPI Parquet, dan prakiraan ECMWF yang sah.
- **Prinsip Keamanan**:
  1. *Zero Lookahead Bias*: Hanya membaca data $\le$ tanggal cutoff periode tersebut.
  2. *Tanpa Zero-Fill*: Nilai yang tidak tersedia tetap dibiarkan `null`.
  3. *Tanpa Status Hijau Palsu*: Stasiun dengan data belum lengkap ditandai `INCOMPLETE` atau `DATA_PARSIAL`.
  4. *Kebijakan ARG*: 5 stasiun ARG dievaluasi berbasis HTH observasi; jika HTH valid, statusnya `COMPLETE`.
  5. *Snapshot Historis Terkunci*: Tidak ada file snapshot di disk yang ditimpa secara otomatis.

---

## 19. SISTEM INGESTION DATA OPERASIONAL & OPTIMALISASI MONITORING SPI MULTI-SKALA (RILIS 30 OKTOBER 2026)

Modul Utama:
- Backend: [backend/ingestion_service.py](file:///f:/TNJ/paper/DATA_ANALISIS_PRAKIRAAN/CEWS/MAS_HAYU/ASLI/backend/ingestion_service.py), [backend/data_service.py](file:///f:/TNJ/paper/DATA_ANALISIS_PRAKIRAAN/CEWS/MAS_HAYU/ASLI/backend/data_service.py), [backend/main.py](file:///f:/TNJ/paper/DATA_ANALISIS_PRAKIRAAN/CEWS/MAS_HAYU/ASLI/backend/main.py)
- Frontend: [frontend/src/components/DataIngestionModal.jsx](file:///f:/TNJ/paper/DATA_ANALISIS_PRAKIRAAN/CEWS/MAS_HAYU/ASLI/frontend/src/components/DataIngestionModal.jsx), [frontend/src/components/StationSpiTrendChart.jsx](file:///f:/TNJ/paper/DATA_ANALISIS_PRAKIRAAN/CEWS/MAS_HAYU/ASLI/frontend/src/components/StationSpiTrendChart.jsx), [frontend/src/components/SpiDataTable.jsx](file:///f:/TNJ/paper/DATA_ANALISIS_PRAKIRAAN/CEWS/MAS_HAYU/ASLI/frontend/src/components/SpiDataTable.jsx), [frontend/src/components/StationDetailDrawer.jsx](file:///f:/TNJ/paper/DATA_ANALISIS_PRAKIRAAN/CEWS/MAS_HAYU/ASLI/frontend/src/components/StationDetailDrawer.jsx), [frontend/src/components/KamusPage.jsx](file:///f:/TNJ/paper/DATA_ANALISIS_PRAKIRAAN/CEWS/MAS_HAYU/ASLI/frontend/src/components/KamusPage.jsx)

### 19.1 Arsitektur Modul Ingestion Multi-Format
Sistem menyediakan pintu masuk terpusat bagi operator untuk memperbarui seluruh data operasional setiap awal dasarian melalui tombol **"Input / Pembaruan Data Operasional"** pada Pusat Data (`DataCenter.jsx`).

**Dukungan Format Dataset:**
1. **Curah Hujan Harian (.xlsx / .xls)**:
   - Mendukung format buku kerja 7 kabupaten/kota (53 sheet stasiun).
   - Penanganan khusus pembagian dwi-wilayah pada file Kota Tanjungpinang (Bintan vs Tanjungpinang).
   - Normalisasi otomatis simbol BMKG: `TTU` $\rightarrow$ 0.0 mm (tidak memutus HTH), `-` $\rightarrow$ 0.0 mm, `X`/`ALAT RUSAK`/kosong $\rightarrow$ `MISSING` (memutus HTH).
   - Komparasi diff berkinerja tinggi terhadap basis data `cews_rainfall_daily` menggunakan kueri rentang tunggal.
2. **SPI Harian & Dasarian (.parquet)**:
   - Matriks lebar (*wide matrix*) berisi 52 stasiun manual dengan kolom huruf kapital.
   - Dukungan timescale 30D (akumulasi 30 hari) dan 90D (akumulasi 90 hari).
3. **SPI Bulanan (.xlsx)**:
   - Pembacaan multi-sheet dengan header bertingkat (Bulan di Baris 1, Indeks/Kriteria di Baris 2).
   - Resolusi pemetaan kode stasiun internal (`TNJ000`), kode WMO 6 digit, koreksi salah ketik stasiun (`210310802A` $\rightarrow$ `21031802A`), dan ekstraksi nilai numerik indeks.
4. **Probabilitas Dasarian & Bulanan (.xlsx)**:
   - Pembacaan seluruh sheet ambang probabilitas: Pb20, Pa150, Pa200, Pa300 (dasarian) serta Pa300, Pa400, Pa500 (bulanan).
   - Resolusi pemetaan stasiun melalui `mapping_tambahan.xlsx` (mengabaikan titik eksternal `228R`).
   - Validasi rentang skala persentase ketat (0–100%) tanpa pengalian ganda.

### 19.2 Pipa Ingestion Aman Multi-Tahap (Safe Ingestion Pipeline)
Proses pembaruan data menerapkan protokol 7 langkah dengan jaminan integritas:
- **Tahap 1**: Pemilihan kategori dataset atau deteksi otomatis (*auto-detect*).
- **Tahap 2**: Pengunggahan berkas (mendukung multi-file drag-and-drop).
- **Tahap 3 & 4**: Validasi struktur, pratinjau diff (*dry-run*), dan deteksi anomali. Sistem menghitung jumlah baris baru, baris yang ditimpa (*updated*), baris identik, dan mendeteksi anomali (angka negatif, probabilitas $> 100\%$, dsb.) tanpa menyentuh basis data operasional.
- **Tahap 5**: Konfirmasi resmi operator (nama petugas, alasan pembaruan, dan persetujuan pernyataan integritas).
- **Tahap 6**: Eksekusi commit atomik (`POST /api/v1/ingestion/commit`). Untuk MariaDB, diterapkan transaksi ACID berprinsip `INSERT ... ON DUPLICATE KEY UPDATE`. Untuk Parquet, diterapkan backup cadangan ber-timestamp sebelum penggantian berkas atomik.
- **Tahap 7**: Sinkronisasi status kesiapan periode dasarian dan pencatatan riwayat transaksi permanen pada tabel `cews_ingestion_history`.

### 19.3 Penyimpanan Kanonikal SPI Bulanan
Dibangun berkas penyimpanan kanonikal Parquet untuk data SPI skala bulanan:
`data/raw/spi/bulanan/SPI_monthly.parquet`
Berkas ini berisi deret waktu 60 bulan (Januari 2021 hingga Desember 2025) untuk 52 pos pengamatan manual, dibangun dari arsip historis resmi BMKG dan siap menerima pembaruan berkala tahun 2026.

### 19.4 Pemanfaatan Multi-Skala SPI & Pemisahan Peran
Sistem membedakan secara tegas peran operasional setiap skala SPI:
1. **SPI Dasarian 30D**: Merupakan **pemicu utama keputusan resmi PDKM** pada Decision Engine BMKG.
2. **SPI Dasarian 90D**: Berfungsi sebagai **indikator pendamping** dinamika kebasahan jangka menengah (3 bulan) non-pemicu PDKM.
3. **SPI Harian (30D & 90D)**: Berfungsi untuk **pemantauan real-time** pergerakan harian yang mengacu pada tanggal observasi terakhir.
4. **SPI Bulanan (1 Bulan)**: Berfungsi untuk **pemantauan klimatologis** dan perbandingan anomali antar-tahun.
5. **Kebijakan 5 Pos ARG**: Seluruh skala SPI untuk 5 stasiun ARG berstatus `NULL` / Tidak Tersedia dan dilarang diisi 0.00 atau NORMAL palsu. Pos ARG dievaluasi murni berbasis HTH observasi.

### 19.5 Visualisasi Tren SPI Stasiun (StationSpiTrendChart)
Panel detail stasiun (`StationDetailDrawer.jsx`) kini dilengkapi grafik deret waktu SPI berbasis SVG interaktif:
- Mendukung peralihan skala instan: Dasarian (30D & 90D), Harian (30D & 90D), dan Bulanan.
- Rentang waktu fleksibel (6, 12, atau 24 bulan).
- Menampilkan garis ambang batas resmi BMKG:
  * $-1.00$ : Waspada (Kuning)
  * $-1.50$ : Siaga (Oranye)
  * $-2.00$ : Awas (Merah)
  * $0.00$ : Normal (Abu-abu)
- **Penanganan Data Hilang Tanpa Interpolasi Semu**: Jika terdapat data kosong/null, garis visual grafik terputus (*disjoint paths*) dan tidak menghubungkan titik-titik valid secara palsu.

### 19.6 Ringkasan Endpoint API Baru
| Metode | Endpoint | Keterangan |
| :--- | :--- | :--- |
| `GET` | `/api/v1/stations/{station_id}/spi-trend?months=12` | Mengambil deret waktu SPI multi-skala stasiun beserta garis ambang batas |
| `POST` | `/api/v1/ingestion/preview` | Mengunggah dan memvalidasi berkas input operasional (dry-run) |
| `POST` | `/api/v1/ingestion/commit` | Menyimpan perubahan batch secara transaksional atomik |
| `GET` | `/api/v1/ingestion/history?limit=30` | Mengambil log riwayat audit transaksi ingestion |
| `GET` | `/api/v1/spi/data?period_type=BULANAN` | Menampilkan tabel spreadsheet SPI bulanan |
| `GET` | `/api/v1/spi/download?period_type=BULANAN` | Mengunduh berkas SPI resolusi bulanan |

---

## 20. KETAHANAN ANTARMUKA & PENANGANAN INSIDEN BLANK WHITE PAGE PADA MODUL INGESTION

### 20.1 Diagnosis Masalah Blank White Page
Pada saat operator mengklik tombol **"Input / Pembaruan Data Operasional"** (`.btn-action-ingestion-primary`) pada menu Data di dashboard, seluruh tampilan dashboard berubah menjadi putih kosong (*blank white page*).

Melalui investigasi forensik berbasis Chrome DevTools Protocol (CDP), ditemukan bahwa akar masalahnya adalah **pelanggaran aturan Rules of Hooks pada React 18** di dalam `frontend/src/components/DataIngestionModal.jsx`:
- Pernyataan `if (!isOpen) return null;` diletakkan di baris 103.
- Hook ke-22 (`const previewSummary = useMemo(...)`) diletakkan di baris 208, yakni **setelah** pernyataan `return null` tersebut.
- Saat initial render (`isOpen=false`), komponen keluar pada baris 103 sehingga hanya mengeksekusi 21 hooks.
- Saat tombol diklik (`isOpen=true`), baris 103 dilewati dan hook ke-22 (`useMemo`) dieksekusi.
- React mendeteksi ketidaksesuaian jumlah hook dan melempar eksepsi fatal:
  `Error: Rendered more hooks than during the previous render.`
- Tanpa adanya penanganan galat di level pohon komponen, React 18 me-unmount seluruh elemen root (`#root`), menghasilkan layar putih kosong.

### 20.2 Solusi Arsitektural Permanen
1. **Kepatuhan Mutlak Aturan Hooks**:
   - Seluruh hook (`useState`, `useEffect`, `useCallback`, `useMemo`) dipindahkan dan dideklarasikan tanpa syarat pada blok teratas komponen `DataIngestionModal.jsx`.
   - Pernyataan pengembalian `if (!isOpen) return null;` dipindahkan ke baris akhir sebelum rendering elemen JSX modal.
   - Dengan perbaikan ini, seluruh 22 hook selalu dieksekusi dalam urutan yang identik 100% pada setiap siklus render, baik saat `isOpen` bernilai `false` maupun `true`.
2. **Implementasi BMKG Institutional Error Boundary (`frontend/src/components/ErrorBoundary.jsx`)**:
   - Mencegah error rendering lokal pada komponen anak merusak tampilan dashboard secara global.
   - Menyajikan antarmuka pemulihan profesional berstandar BMKG dengan kartu peringatan ramah pengguna, tombol coba muat ulang komponen mandiri, tombol reload halaman, serta panel detail teknis stack trace yang dapat dibuka/tutup.
   - Dipasang pada 3 lapis pertahanan: Root level (`main.jsx`), View/Tab level (`App.jsx`), dan Modal level (`DataCenter.jsx`).
3. **Pembersihan CSS & Penanganan Siklus Hidup**:
   - Menghapus typo `background: linear-flex;` pada kelas `.btn-action-ingestion-primary` di `App.css`.
   - Menambahkan pelindung `active` (isMounted cancellation guard) pada pemanggilan data riwayat audit `fetchHistory` untuk mencegah kebocoran memori pada unmount cepat.

### 20.3 Verifikasi Kualitas & Regresi
- **10 Skenario Pengujian Fungsional Otomatis** (`scratch/test_all_10_scenarios.mjs`) dijalankan pada browser headless nyata: seluruh 10 skenario lulus 100% tanpa eksepsi runtime.
- **Uji Regresi Penuh**: 24 uji Pytest lulus 100% (Decision Engine PDKM/PDCHT utuh, 286.085 baris data observasi MariaDB utuh, 570 snapshot historis utuh, 4 berkas Parquet SPI primer utuh, dan 5 stasiun ARG konsisten berstatus `NULL`).
- **Kompilasi Produksi**: `npm run build` sukses 100% tanpa error bundling.

---

## 21. PROSEDUR OPERASIONAL PENERIMAAN DATA (DATA INGESTION RUNBOOK) & HASIL ACCEPTANCE TEST END-TO-END

### 21.1 Hasil End-to-End Acceptance Test (18 Skenario 100% PASS)
Telah dibangun dan diverifikasi rangkaian uji penerimaan sistem (*End-to-End Acceptance Test*) di `tests/integration/test_ingestion_end_to_end_acceptance.py`:
1. **Validasi Parsing CH**: 6 berkas CH dikenali otomatis sebagai `CURAH_HUJAN`, header `['tanggal', 'CH']`, data mulai baris 2.
2. **Pemetaan 53 Sheet & Dwi-Wilayah**: 53 sheet stasiun 100% terpetakan (`0 unrecognized`). File `Kota Tanjungpinang.xlsx` (18 sheet) secara akurat dipecah menjadi 14 stasiun Kab. Bintan dan 4 stasiun Kota Tanjung Pinang berdasarkan metadata stasiun master, bukan nama berkas.
3. **Normalisasi Simbol BMKG**: `-` $\rightarrow 0.0$ (`OBSERVED_ZERO`), `TTU`/`ttu`/`T.T.U` $\rightarrow 0.0$ (`TTU`), `X`/`NO DATA`/kosong/`R`/`ALAT RUSAK (9999)` $\rightarrow \text{None}$ (`MISSING`), typo trailing `1-` $\rightarrow 1.0$, `0.4.` $\rightarrow 0.4$, `.` $\rightarrow 0.0$, dan nilai negatif ditolak.
4. **SPI Dasarian 30D/90D**: Matriks lebar tanggal cutoff dasarian $\{1, 11, 21\}$, 52 stasiun manual, idempotensi 100%.
5. **SPI Harian 30D/90D**: Matriks harian kalender penuh (16.690 tanggal), 52 stasiun manual.
6. **SPI Bulanan (2026_SPI.xlsx)**: Header bertingkat 12 bulan terekstraksi. Kode WMO `00096091A` dipetakan ke `21720201A` (Stamet RHF), typo `210310802A` otomatis dikoreksi ke `21031802A` (Selemut Cemaga).
7. **Probabilitas Dasarian**: Sheet `pb20`, `pb50`, `pb100`, `pb150`, `pa150`, `pa200`, `pa300`, `EnsMean` terekstraksi dengan kolom periode target (`MeiI`).
8. **Probabilitas Bulanan**: Sheet `pa300`, `pa400`, `pa500`, `EnsMean` terekstraksi dengan periode multi-bulan (`Sep` s.d. `Feb`).
9. **Skala Probabilitas 0–100% Strict**: Nilai murni persentase tanpa pengalian ganda, ambang pemicu ketat $>70.0\%$.
10. **Deteksi Duplikasi**: Duplikasi kunci `(station_id, observation_date)` dalam satu file otomatis disaring bersih.
11. **Deteksi Diff**: Identifikasi otomatis `NEW` (tanggal baru), `IDENTICAL` (data cocok), dan `DIFF` (perubahan nilai dengan inspeksi lama vs baru).
12. **Proteksi Historis**: Data di luar periode unggah tidak tersentuh. Baseline MariaDB `cews_rainfall_daily` tetap tepat 286.085 baris.
13. **Idempotensi**: Mengunggah kembali berkas yang sama menghasilkan 0 record baru / 0 update.
14. **Transaksi Atomik**: Rollback otomatis jika terjadi kegagalan database saat commit batch.
15. **Audit Trail**: Pencatatan log permanen di tabel `cews_ingestion_history` dan API `GET /api/v1/ingestion/history`.
16. **Kepatuhan Decision Engine**: Formula $\max(\text{HTH}, \text{Prob}, \text{SPI})$ dan $\max(\text{Dasarian}, \text{Bulanan})$ terlindungi 100%.
17. **Sinkronisasi Periode Tanpa Lookahead Bias**: Cutoff observasi dievaluasi tegas pada tanggal akhir periode sebelumnya (misal Dasarian II cutoff 10 September).
18. **Strict NULL ARG**: 5 pos ARG strictly bernilai `NULL` pada semua skala SPI dan tidak memicu *false green* (Aman palsu).

### 21.2 Panduan Operasional Unggah Data (Runbook)
Petugas operasional BMKG dapat memperbarui data setiap awal dasarian dengan langkah-langkah berikut:
1. Buka dashboard pada peramban web: `http://localhost:5173/dashboard` (atau IP LAN kantor BMKG).
2. Navigasikan ke menu **Data Center** (Pusat Data).
3. Klik tombol biru **"Input / Pembaruan Data Operasional"**.
4. Seret (*drag-and-drop*) berkas pembaruan data (Excel curah hujan, SPI Parquet, SPI Excel, atau Excel probabilitas). Sistem akan mendeteksi tipe dataset secara otomatis.
5. Periksa ringkasan pratinjau (*dry-run preview*):
   - Periksa jumlah stasiun yang dikenali vs tidak dikenali.
   - Periksa rentang tanggal pembaruan.
   - Periksa jumlah baris baru (`total_new`), baris update (`total_updated`), dan baris identik (`total_identical`).
   - Periksa daftar anomali (jika ada nilai curah hujan yang tidak lazim atau typo).
6. Berikan catatan audit pada kolom catatan (misal: "Pembaruan Dasarian III Oktober 2026 oleh Forecaster Piket").
7. Klik tombol hijau **"Konfirmasi & Simpan ke Sistem"**.
8. Sistem akan melakukan *atomic commit* ke MariaDB atau Parquet, mencatat riwayat ke tabel audit, dan memperbarui status peringatan dini secara otomatis.

### 21.3 Prosedur Pemulihan (Rollback Procedure)
- **Kegagalan Saat Transaksi Berjalan**: Backend secara otomatis menjalankan perintah `conn.rollback()` pada transaksi MariaDB. Data staging yang belum divalidasi tidak akan masuk ke `cews_rainfall_daily`.
- **Pemulihan Berkas Parquet**: Setiap kali pembaruan berkas Parquet dilakukan, sistem membuat berkas cadangan otomatis di direktori yang sama dengan ekstensi `.parquet.bak_<timestamp>`. Jika pembaruan perlu dibatalkan, operator cukup mengganti nama berkas cadangan tersebut kembali ke nama aslinya.
- **Pemeriksaan Audit Trail**: Riwayat seluruh batch commit dapat dipantau melalui tab "Riwayat Pembaruan Data" di antarmuka modal atau melalui API `GET /api/v1/ingestion/history`.

---

## 22. FINAL HARDENING AUDIT, PERIOD-AWARE DATA INGESTION & KETAHANAN MULTI-PENYIMPANAN (RILIS 31 OKTOBER 2026)

### 22.1 Normalisasi Simbol Curah Hujan & Perluasan Skema Status Observasi
Berdasarkan audit operasional BMKG, pemisahan semantik antara nilai nol terukur, jejak hujan, data hilang, dan kerusakan peralatan instrumen telah diperketat pada modul ingestion (`backend/ingestion_service.py` versi `1.2.0`).

| Simbol Masukan | Nilai Numerik | Status Observasi (`obs_status`) | Dampak pada Running HTH | Status Tampilan UI | Keterangan Operasional |
|---|---|---|---|---|---|
| Bilangan $\ge 1.0\text{ mm}$ | Float asli | `OBSERVED_VALID` | Mereset streak HTH menjadi 0 | Hujan ($X.X\text{ mm}$) | Hujan terukur harian |
| Bilangan $0.0 \le \text{CH} < 1.0\text{ mm}$ | Float asli | `OBSERVED_ZERO` | Menambah counter HTH (+1) | Hari Tanpa Hujan | Hujan sangat ringan non-efektif |
| `-` (strip / dash) | $0.0\text{ mm}$ | `OBSERVED_ZERO` | Menambah counter HTH (+1) | Hari Tanpa Hujan | Konvensi BMKG untuk tidak ada hujan |
| `TTU` / `ttu` / `T.T.U` | $0.0\text{ mm}$ | `TTU` | Menambah counter HTH (+1) | TTU (Jejak Hujan) | Terukur Tak Tentu ($<0.5\text{ mm}$) |
| `X` / `NO DATA` / kosong | `NULL` | `MISSING` | Memutus streak HTH (reset 0) | Tidak tersedia | Data tidak tercatat / kosong |
| `R` / `ALAT RUSAK` / `9999` | `NULL` | `DAMAGED` | Memutus streak HTH (reset 0) | Alat Rusak | Instrumen pos mengalami kerusakan |
| `.` (titik tunggal) | `NULL` | `AMBIGUOUS` | Memutus streak HTH (reset 0) | Perlu Verifikasi | Simbol ambigu; wajib dikonfirmasi |
| Typo `1-` | $1.0\text{ mm}$ | `OBSERVED_VALID` | Mereset streak HTH menjadi 0 | Hujan ($1.0\text{ mm}$) | Sanitasi typo tanda minus di belakang |
| Typo `0.4.` / `13.0.` | $0.4 / 13.0\text{ mm}$ | `OBSERVED_VALID` | Mereset streak HTH menjadi 0 | Hujan ($X.X\text{ mm}$) | Sanitasi typo tanda titik di belakang |
| Bilangan negatif (misal $-5.0$) | `NULL` | `REJECTED` | Ditolak masuk basis data | Anomali Ditolak | Nilai di luar batas fisik presipitasi |

**Perluasan Skema Basis Data MariaDB**:
Kolom `obs_status` pada tabel `cews_rainfall_daily` diperbarui secara permanen dengan penambahan status `DAMAGED` dan `AMBIGUOUS`:
```sql
ALTER TABLE cews_rainfall_daily 
MODIFY COLUMN obs_status ENUM(
    'OBSERVED_VALID',
    'OBSERVED_ZERO',
    'TTU',
    'MISSING',
    'CORRECTED',
    'DAMAGED',
    'AMBIGUOUS'
) NOT NULL DEFAULT 'OBSERVED_VALID';
```

**Kamus Istilah & Konsistensi UI**:
Komponen Kamus Istilah (`frontend/src/components/KamusPage.jsx`) telah disinkronkan dengan penjelasan resmi:
- *Authoritative Basis*: SPI 30D sebagai landasan evaluasi bahaya kekeringan meteorologis dasarian.
- *Informative Companion*: SPI 90D sebagai rujukan kondisi jangka menengah untuk memperkaya interpretasi tanpa memicu peringatan.

---

### 22.2 Hirarki Otoritas SPI & Uji Konflik Decision Engine PDKM
Sistem menegakkan hirarki otoritas yang tegas terhadap seluruh skala waktu SPI:
1. **SPI Dasarian 30D (Otoritatif Tunggal PDKM)**:
   - Ambang pemicu: Waspada ($\le -1.00$), Siaga ($\le -1.50$), Awas ($\le -2.00$).
   - Merupakan satu-satunya skala SPI yang berhak memicu status peringatan dini kekeringan meteorologis.
2. **SPI Dasarian 90D (Pendamping Informatif)**:
   - Digunakan untuk melihat persistensi kekeringan 3 bulanan.
   - **Tidak memiliki hak veto maupun kuasa pemicu status peringatan**.
3. **Hasil Uji Ketahanan Konflik**:
   - *Kasus Konflik 1*: SPI 30D Normal ($+0.50$) dan SPI 90D Kering Ekstrem ($-2.50$) $\rightarrow$ Status PDKM tetap **NORMAL** (tidak ada *false alarm*).
   - *Kasus Konflik 2*: SPI 30D Kering Ekstrem ($-2.20$) dan SPI 90D Normal ($0.00$) $\rightarrow$ Status PDKM dipicu menjadi **AWAS** secara akurat.
4. **Stasiun Otomatis (ARG / AWS)**:
   - 5 stasiun otomatis (`2171001`, `2171002`, `2102001`, `2101001`, `2103001`) secara ketat diatur bernilai `NULL` pada seluruh matriks SPI dan tidak pernah memicu status hijau palsu (*false green*).

---

### 22.3 Deteksi Periode Otomatis, Isolasi Vintage & Penanganan Pergantian Tahun
1. **Pendeteksian Periode Berbasis Konten**:
   - Sistem membaca tanggal, periode dasarian, dan metadata langsung dari struktur internal berkas (tanggal cut-off, nama sheet, header tanggal).
   - Nama berkas yang tidak sesuai (misal berkas bernama `Dasarian_I.xlsx` tetapi berisi tanggal Dasarian II) tetap diidentifikasi secara tepat sesuai data aslinya.
2. **Pemisahan Tanggal Terbit vs Periode Target**:
   - Nilai `issue_date` (tanggal terbit model) dipisahkan secara tegas dari `target_period` (dasarian/bulan prakiraan).
3. **Isolasi Vintage Prakiraan ECMWF**:
   - Tabel `cews_forecast_snapshot` menggunakan composite unique key:
     `UNIQUE KEY uq_forecast_evidence (station_id, target_year, target_month, target_dasarian, issue_date, forecast_parameter)`.
   - Unggahan prakiraan baru tidak akan menimpa snapshot terbitan sebelumnya, memungkinkan penelusuran audit multi-vintage.
4. **Penanganan Otomatis Pergantian Tahun (Year Rollover)**:
   - Pada pembacaan probabilitas bulanan (misal terbit Agustus 2026 dengan deret bulan `Sep`, `Okt`, `Nov`, `Des`, `Jan`), sistem secara otomatis mendeteksi ketika indeks bulan target lebih kecil daripada bulan terbit:
     $$\text{target\_year} = \begin{cases} \text{issue\_year} + 1 & \text{jika } \text{target\_month} < \text{issue\_month} \\ \text{issue\_year} & \text{lainnya} \end{cases}$$
   - Bulan `Jan` otomatis dialokasikan ke tahun 2027 dengan horizon waktu yang tepat.

---

### 22.4 Otorisasi Pembaruan Bertarget (Scoped Update Authorization) & Proteksi Data
Modul antarmuka dan backend kini mengimplementasikan 5 lapis pengamanan pembaruan:
1. **Seleksi Dasarian Bertarget**: Petugas dapat memilih dasarian tertentu yang ingin disimpan melalui kartu seleksi periode. Dasarian yang tidak dicentang tidak akan diproses atau disimpan ke database.
2. **Persetujuan Eksplisit Data Berubah (`UPDATED`)**:
   - Disertai kotak persetujuan: `[x] Saya mengizinkan pembaruan data pada periode terkait.`
   - Jika kotak tidak dicentang:
     - Rekaman baru (`NEW`) tetap disimpan untuk periode yang dipilih.
     - Rekaman identik (`IDENTICAL`) dilewati (*skipped*).
     - Rekaman yang berbeda (`UPDATED`) dilewati/ditolak dan dicatat pada audit trail sebagai `rejected_records`.
     - Jika seluruh data dalam file berstatus `UPDATED` dan kotak tidak dicentang, proses commit dibatalkan dengan peringatan penolakan.
3. **Proteksi Anti-Nullification**:
   - Data observasi valid yang sudah tersimpan di database tidak dapat ditimpa oleh nilai `NULL` atau `MISSING` dari file unggahan baru.
4. **Proteksi Kerusakan Alat**:
   - Simbol kerusakan alat (`DAMAGED`) tidak diizinkan menimpa data observasi berstatus `OBSERVED_VALID` tanpa otorisasi pembaruan eksplisit.
5. **Verifikasi Sidik Jari Baseline (`baseline_fingerprint`)**:
   - Hash SHA-256 dari kondisi data database dihitung saat pratinjau (*preview*). Jika terjadi perubahan data konkuren sebelum *commit*, sistem membatalkan transaksi untuk mencegah inkonsistensi data.

---

### 22.5 Rekayasa Audit Trail Multi-Penyimpanan & Rollback Atomik
Tabel `cews_ingestion_history` diperkaya dengan 7 kolom baru untuk menjamin transparansi penuh:
```sql
ALTER TABLE cews_ingestion_history
    ADD COLUMN target_period TEXT NULL AFTER session_token,
    ADD COLUMN rejected_records INT NOT NULL DEFAULT 0 AFTER records_skipped,
    ADD COLUMN missing_records INT NOT NULL DEFAULT 0 AFTER rejected_records,
    ADD COLUMN damaged_records INT NOT NULL DEFAULT 0 AFTER missing_records,
    ADD COLUMN parser_version VARCHAR(20) NOT NULL DEFAULT '1.2.0' AFTER damaged_records,
    ADD COLUMN backup_reference VARCHAR(255) NULL AFTER parser_version,
    ADD COLUMN approval_scope TEXT NULL AFTER backup_reference;
```
- **Atomisitas MariaDB**: Menggunakan blok transaksi `BEGIN ... COMMIT` dengan `conn.rollback()` otomatis saat terjadi kesalahan.
- **Cadangan Parquet Otomatis**: Setiap modifikasi berkas SPI Parquet didahului pembuatan salinan cadangan fisik (`.parquet.bak_<timestamp>`).

---

### 22.6 Hasil Pengujian Komprehensif (23 Skenario Hardening 100% Pass, Total 88/88 Uji Terpadu)
Rangkaian pengujian integrasi baru pada `tests/integration/test_period_aware_ingestion_hardening.py` menguji seluruh skenario secara mendalam:
- **23 Skenario Period-Aware & Hardening**: Seluruh 23 pengujian lulus 100% (Normalisasi simbol, HTH streak, otorisasi selektif, isolasi vintage, year rollover, baseline fingerprinting, dan mitigasi konflik SPI).
- **88 Uji Regresi Menyeluruh**: Seluruh 88 pengujian otomatis di repositori lulus 100% tanpa kegagalan:
  - `tests/test_operational_rules.py` (24 uji)
  - `tests/test_dss_pik_57_stations_incomplete.py` (9 uji)
  - `tests/test_dashboard_contract.py` (14 uji)
  - `tests/integration/test_ingestion_end_to_end_acceptance.py` (18 uji)
  - `tests/integration/test_period_aware_ingestion_hardening.py` (23 uji)
- **Integritas Basis Data Produksi**: Tabel `cews_rainfall_daily` dipertahankan utuh tepat pada **286.085 baris**.
- **Kompilasi Frontend Produksi**: Build React/Vite sukses 100% tanpa galat (`dist/index.html` dan bundel aset terverifikasi).

---

## 23. PUSAT PENGELOLAAN DATA OPERASIONAL, PENANGANAN VINTAGE, DAN KOREKSI/PEMBATALAN DATA (RILIS 31 OKTOBER 2026)

### 23.1 Latar Belakang & Ruang Lingkup Pengembangan
Menindaklanjuti kebutuhan operasional Stasiun Meteorologi Kelas II Raja Haji Fisabilillah Tanjungpinang dalam mengelola siklus data iklim dinamis, modul data ingestion telah ditingkatkan menjadi **Pusat Pengelolaan Data Operasional (Operational Data Management Center)** yang komprehensif. Modul ini melengkapi kemampuan sistem dengan monitoring penyimpanan kanonikal real-time, penanganan vintage prakiraan ensemble ECMWF, pembatalan batch (rollback) aman berdasar alasan operasional, serta koreksi dan pembatalan data curah hujan individual dengan pencatatan buku besar (*ledger*) audit permanen.

---

### 23.2 Pemisahan Temporal Ketat: Data Observasi vs Data Prakiraan
Sistem menerapkan pemisahan temporal yang kaku (*Strict Temporal Separation*):
1. **Data Observasi Mengendalikan Dasarian Aktif**: Tanggal observasi curah hujan riil yang lengkap pada `cews_rainfall_daily` dan SPI Parquet menentukan dasarian operasional yang sedang aktif dievaluasi di dashboard.
2. **Data Prakiraan Berorientasi Masa Depan**: Mengunggah berkas probabilitas ECMWF dengan tanggal masa depan (misal Dasarian I s/d III Oktober 2026 atau Januari 2027) **TIDAK AKAN** menggeser periode aktif observasi dashboard secara prematur.
3. **Pencegahan Lookahead Bias**: Decision Engine PDKM dan PDCHT membaca data historis observasi dan proyeksi masa depan dari sumber kanonikal masing-masing secara terisolasi tanpa saling mencemari.

---

### 23.3 Panel Monitoring Status Data Terkini (Canonical Storage Status)
Pusat Data menyediakan antarmuka pemantauan status penyimpanan kanonikal terpadu (tersedia pada *Modal Ingestion Header* dan subtab *Manajemen Data Operasional* di *Data Center*):
- **Kueri Langsung Basis Data**: Menampilkan tanggal observasi maksimum (`MAX(observation_date)`), total baris aktif, dan stasiun terdaftar di MariaDB.
- **Kueri Langsung Berkas Parquet**: Menampilkan tanggal indeks terakhir untuk SPI Dasarian (`SPI_dasarian_30d.parquet`) dan SPI Bulanan (`SPI_monthly.parquet`).
- **Status Vintage Prakiraan**: Menampilkan tanggal terbit (*issue date*) terakhir beserta jumlah snapshot aktif di `cews_forecast_snapshot`.
- **Tombol Penyegaran Cepat (Refresh)**: Memaksa pembaruan status langsung dari storage fisik tanpa jeda cache.

---

### 23.4 Perbaikan Pratinjau & Diff Nilai Probabilitas
1. **Standarisasi Skala Baku 0–100%**: Nilai probabilitas dalam rentang desimal `0.0 < val <= 1.0` secara otomatis dikonversikan menjadi persentase utuh `0.0% – 100.0%`. Nilai anomali di atas 100% atau bernilai negatif ditolak.
2. **Penghilangan Bug Tanda Strip (`–`)**: Kolom *Nilai Baru* pada tabel pratinjau dan perbandingan (*diff*) kini memuat nilai desimal yang presisi (misal `45.00%`), disertai perbandingan terhadap nilai lama di database (`Nilai Lama`), nilai selisih (`Selisih / Diff`), nama parameter, periode target, dan tanggal terbit model.

---

### 23.5 Manajemen Vintage Prakiraan ECMWF & Isolasi Rilis Model
1. **Pencegahan Data Overwriting**: Tabel `cews_forecast_snapshot` menggunakan composite unique key `(station_id, target_year, target_month, target_dasarian, issue_date, forecast_parameter)`, sehingga unggahan rilis model baru untuk periode target yang sama tidak menghapus rilis model terdahulu.
2. **Penelusuran Vintage Interaktif**: Subtab Manajemen Data Operasional menyediakan antarmuka filter horizon (Dasarian/Bulanan), Tahun Target, dan Bulan Target untuk meninjau seluruh vintage yang pernah diunggah.
3. **Seleksi Vintage Otoritatif**: Decision Engine secara otomatis memilih vintage terbaru yang tanggal terbitnya mendahului atau sama dengan tanggal cut-off evaluasi dasarian aktif ($\text{issue\_date} \le \text{cutoff\_date}$).

---

### 23.6 Manajemen Batch Ingestion, Pembatalan Aman (Rollback) & Koreksi Data Tunggal
1. **Manajemen Batch Ingestion**:
   - Setiap transaksi unggahan disimpan sebagai satu batch dengan pengenal unik (*Session Token* / *Batch ID*).
   - Rincian item batch (stasiun, tanggal, nilai lama, nilai baru, parameter) disimpan secara terstruktur dalam kolom `batch_items_json` pada tabel `cews_ingestion_history`.
2. **Pembatalan Batch Aman (Safe Rollback)**:
   - Operator dapat membatalkan batch yang keliru langsung dari antarmuka.
   - **Alasan Pembatalan Wajib**: Dialog pembatalan mewajibkan input teks alasan operasional sebelum pembatalan dieksekusi.
   - Sistem memulihkan nilai lama atau menghapus baris yang disisipkan oleh batch tersebut di MariaDB, memulihkan berkas cadangan Parquet fisik, dan menandai status batch sebagai `ROLLED_BACK`.
3. **Koreksi Data Tunggal (Single Record Correction)**:
   - Formulir koreksi memungkinkan pembaruan nilai curah hujan harian untuk satu stasiun dan satu tanggal tertentu dengan mencantumkan nilai baru, status observasi, identitas operator, dan alasan koreksi.
   - Setiap perubahan dicatat ke tabel `cews_rainfall_correction_log` yang bertindak sebagai buku besar audit yang tidak dapat dihapus (*append-only ledger*).
4. **Pembatalan Catatan (Record Voiding)**:
   - Fitur pembatalan catatan menandai observasi yang cacat/fiktif sebagai `VOID` dan `rainfall_mm = NULL` tanpa menghapus baris fisik dari tabel `cews_rainfall_daily`, menjamin integritas referensial dan jejak audit.

---

### 23.7 Aturan Semantik Hari Tanpa Hujan (HTH) & Integritas PDKM
1. **Semantik Simbol BMKG**:
   - `OBSERVED_ZERO` ($0.0\text{ mm}$) dan `TTU` (Jejak $< 0.5\text{ mm}$) menambah akumulasi HTH (+1 hari).
   - Curah hujan $\ge 1.0\text{ mm}$ mereset akumulasi HTH ke 0 hari.
   - Simbol `DAMAGED` (8888), `MISSING` (9999), dan `AMBIGUOUS` (.) **TIDAK MERESET HTH KE 0**, melainkan mempertahankan akumulasi sebelumnya dan menandai `hth_uncertain = True`.
2. **Pencegahan False Green ("Aman Palsu")**:
   - Pada Decision Engine PDKM, jika pos hujan memiliki nilai $\text{HTH} < 21\text{ hari}$ tetapi benderanya `hth_uncertain = True`, indikator HTH diklasifikasikan sebagai `UNCERTAIN` / Tidak Lengkap.
   - Sistem menolak memberikan rekomendasi hijau `AMAN` secara gegabah, mencegah bahaya tersembunyi kekeringan meteorologis di Kepulauan Riau.

---

### 23.8 Spesifikasi Endpoint API Baru
Modul ini menambahkan 7 endpoint RESTful resmi pada FastAPI:
| Metode | Rute Endpoint | Deskripsi Operasional |
| :--- | :--- | :--- |
| `GET` | `/api/v1/ingestion/latest-status` | Kueri status kanonikal MariaDB, Parquet SPI, dan Vintage Prakiraan. |
| `GET` | `/api/v1/ingestion/batches` | Daftar riwayat batch ingestion dengan filter tipe file dan rentang tanggal. |
| `GET` | `/api/v1/ingestion/batch/{batch_id}` | Pengambilan rincian detail item perubahan pada suatu batch ingestion. |
| `POST` | `/api/v1/ingestion/batch/{batch_id}/cancel` | Pembatalan aman (rollback) batch dengan alasan operasional wajib. |
| `POST` | `/api/v1/ingestion/record/correct` | Koreksi nilai data curah hujan individual dan pencatatan log koreksi. |
| `POST` | `/api/v1/ingestion/record/void` | Pembatalan status rekaman curah hujan (`VOID`) dan pencatatan log. |
| `GET` | `/api/v1/forecast/vintages` | Penelusuran rilis vintage model prakiraan ECMWF dasarian dan bulanan. |

---

### 23.9 Hasil Verifikasi Pengujian Menyeluruh (97/97 Pengujian Pass 100%)
Rangkaian pengujian integrasi baru pada `tests/integration/test_operational_data_management.py` (9 pengujian komprehensif) bersama seluruh pengujian regresi repositori berhasil dieksekusi dengan hasil sempurna:
- **Hasil Pengujian Keseluruhan**: **97 passed, 1 warning in 90.32s (100% PASS)**.
- **Integritas Basis Data Produksi**: Tabel `cews_rainfall_daily` terverifikasi presisi pada **286.085 baris**.
- **Kompilasi Frontend Produksi**: Build Vite (`dist/index.html`, `dist/assets/`) selesai dalam 12.51 detik dengan exit code 0.
- **Panduan Operasional Lengkap**: Tersedia pada dokumen resmi [`docs/DSS_PIK_OPERATOR_DATA_MANAGEMENT_GUIDE.md`](file:///f:/TNJ/paper/DATA_ANALISIS_PRAKIRAAN/CEWS/MAS_HAYU/ASLI/docs/DSS_PIK_OPERATOR_DATA_MANAGEMENT_GUIDE.md).

---

## 24. PENYEMPURNAAN FINAL ANTARMUKA PENGELOLAAN DATA, PERIODE DINAMIS, VALIDASI METADATA STASIUN & IDEMPOTENSI INGESTION (RILIS 31 OKTOBER 2026)

Tahap penyempurnaan akhir (*Final Refinement*) berfokus pada keandalan antarmuka operasional, fleksibilitas navigasi dasarian dinamis, penjaminan integritas metadata stasiun otoritatif, dan idempotensi transaksi input data.

### 24.1 Redesain Status Data Operasional (Canonical Storage Live Card)
Dibuat komponen khusus `CanonicalStorageStatusCard.jsx` yang menyajikan status kesiapan data real-time BMKG Kepulauan Riau:
- **Header Status**: Indikator LIVE berdenyut (*pulsing indicator*), stempel waktu pemeriksaan WIB, dan tombol penyegaran instan.
- **Baris 1 Curah Hujan Harian (MariaDB `cews_rainfall_daily`)**:
  - Tanggal terakhir data observasi dan periode dasarian.
  - Jumlah pos melapor vs total pos master (misal: 23/57 pos).
  - Progress bar persentase cakupan pos dengan palet warna hijau zamrud BMKG ($\ge 80\%$), amber ($50-79\%$), dan merah ($<50\%$).
  - Daftar pos yang belum melapor yang dapat diperluas (*expandable list*).
- **Baris 2 SPI Multi-Skala (Parquet 5 Skala)**:
  - 5 Kartu responsif: SPI Harian 30D, SPI Harian 90D, SPI Dasarian 30D, SPI Dasarian 90D, dan SPI Bulanan.
  - Pos terhitung (52/52 pos manual) dan status siap Parquet.
  - Spanduk integritas standar: *5 Pos ARG dikecualikan strictly NULL (non-SPI)*.
- **Baris 3 Probabilitas Prakiraan ECMWF (Snapshot Store)**:
  - Kartu Dasarian ECMWF: Periode target, tanggal rilis/issue, 52 pos terpetakan, dan 11 parameter probabilitas.
  - Kartu Bulanan ECMWF: Bulan target, tanggal rilis, cakupan pos dan indikator.

### 24.2 Redesain Ruang Kerja Manajemen Data Operasional
Pusat Pengelolaan Data Operasional (`OperationalDataManager.jsx`) disempurnakan dengan arsitektur profesional:
- **Bagian A: 6 KPI Cards Real-Time**: Terhubung langsung ke endpoint `GET /api/v1/ingestion/operational-summary` untuk menyajikan: Total Batch, Batch Berhasil, Batch Dibatalkan, Total Record Baru, Total Record Diperbarui, dan Total Record Ditolak.
- **Bagian B: Tab Navigasi Terstruktur**:
  1. *Ringkasan Penyimpanan*: Memuat `CanonicalStorageStatusCard`.
  2. *Riwayat Batch Ingestion*: Bilah pencarian instan, filter tipe data dan status batch, tabel paginasi, modal detail lengkap dengan SHA-256 hash, dan rollback bertarget.
  3. *Koreksi & Pembatalan Rekaman*: Formulir koreksi CH, formulir void CH, formulir void SPI terisolasi per timescale (30D vs 90D), dan formulir void snapshot probabilitas.
  4. *Vintage Prakiraan ECMWF*: Penjelajah rilis vintage snapshot ECMWF dengan metrik jumlah pos dan indikator.

### 24.3 Dinamika Periode Dasarian (+1 Periode Prakiraan) & Proteksi Lookahead
- Selector dasarian menyajikan jendela 10 dasarian observasi ditambah **1 periode dasarian prakiraan ke depan (+1)** (misal pada 31 Oktober 2026, muncul opsi Dasarian I November 2026 bertanda `🔮 [Prakiraan]`).
- Periode aktif default tetap berlabuh pada periode observasi kalender aktual.
- Ketika operator memilih periode masa depan (+1), antarmuka menampilkan spanduk ungu berstandar BMKG:
  `PERIODE PRAKIRAAN — BELUM MENJADI PERIODE OBSERVASI`
  menghilangkan bias *lookahead* dan mencegah penetapan status *False Green* (`AMAN` palsu).

### 24.4 Validasi Metadata Stasiun Otoritatif & Resolusi Tabrakan Pos
- Menetapkan `station_metadata.parquet` (57 stasiun: 52 Manual + 5 ARG) sebagai sumber acuan tunggal yang tidak boleh diubah oleh proses parsing berkas.
- Menghapus pencocokan substring longgar (*loose fuzzy matching*).
- Pos eksternal di luar 57 stasiun (seperti baris 50 `Tanjung Riau Kota Batam`) diisolasi secara aman ke dalam kategori `unmapped_external_stations`, melindungi master station dari duplikasi.
- Mengatasi tabrakan nomor pos `228D` antara `Duara` (Lingga) dan `UPT Benih Pertanian` (Anambas) dengan resolusi pasangan nama normalisasi: `Duara` memetakan ke `21040501A`, dan `UPT Benih Pertanian` ke `21050501A` (`Bukit Padi`), menghasilkan 52 pos manual terpetakan 100% tanpa duplikat.
- Modal ingestion menyajikan ringkasan validasi pemetaan stasiun secara transparan pada tahap pratinjau.

### 24.5 Idempotensi Mutlak Preview & Diff
- Menerapkan perbandingan nilai mengambang deterministik $|\text{Prob}_{\text{baru}} - \text{Prob}_{\text{lama}}| < 10^{-4}$ untuk mencegah selisih pembulatan memicu status `UPDATED` palsu.
- Unggah ulang file identik menghasilkan **NEW = 0, UPDATED = 0, IDENTICAL = 572, REJECTED = 0**.
- Komitmen transaksi mencatat jumlah identik secara presisi pada `cews_ingestion_history` dan melewati penulisan fisik redundan ke basis data.

### 24.6 Tombol Aksi Kontekstual Lintas Halaman Dataset
Pada setiap tabel dataset di Data Center (`DailyRainfallTable`, `SpiDataTable`, `ProbabilityDataTable`), disediakan tombol aksi terpadu:
- `[Input / Pembaruan Data ...]`: Membuka modal ingestion dengan tipe dataset yang langsung terkunci sesuai konteks.
- `[Kelola / Koreksi / Void ...]`: Mengarahkan langsung operator ke sub-form manajemen yang relevan di tab Manajemen Data Operasional.

### 24.7 Spesifikasi Endpoint API Tambahan
| Metode | Endpoint | Deskripsi |
| :--- | :--- | :--- |
| `GET` | `/api/v1/ingestion/operational-summary` | Mengambil metrik ringkasan KPI agregat dari tabel `cews_ingestion_history`. |
| `POST` | `/api/v1/ingestion/spi/void` | Membatalkan/nullify rekor SPI pada file Parquet terisolasi per timescale (30D vs 90D). |
| `POST` | `/api/v1/ingestion/probability/void` | Membatalkan/menghapus rekor probabilitas snapshot dari `cews_forecast_snapshot`. |

### 24.8 Verifikasi Penjaminan Mutu & Ketahanan Sistem
- **Test Suite Khusus**: `tests/integration/test_ui_period_metadata_idempotency.py` (10/10 pengujian integrasi pass 100%).
- **Integritas Basis Data**: Deret observasi `cews_rainfall_daily` terverifikasi presisi pada **286.085 baris**.
- **Kompilasi Frontend Produksi**: Build Vite (`npm run build`) sukses tanpa peringatan sintaks dalam 15.84 detik.

---

## 25. FINAL REFINEMENT — MULTI-VINTAGE ECMWF, DATABASE SYNCHRONIZATION & UI MODERNIZATION (31 OKTOBER 2026)

### 25.1 Arsitektur Multi-Vintage ECMWF Kumulatif & Non-Destruktif
1. **Isolasi Rilis Prakiraan:**
   - Penambahan kolom `forecast_resolution` dan indeks unik multi-kolom kanonikal pada MariaDB:
     `uq_fc_multi_vintage (station_id, forecast_resolution, target_year, target_month, target_dasarian, issue_date, forecast_parameter)`.
   - Menghapus resiko terhapusnya rekaman rilis lama saat mengunggah rilis baru untuk periode target yang sama.
2. **Kategori Diff & Audit Mutakhir:**
   - `NEW`: Periode target pertama kali diunggah (52 stasiun x 4 parameter = 208 rekaman).
   - `NEW VINTAGE`: Periode target sudah pernah ada, tetapi file memiliki tanggal rilis (*issue date*) baru. Diterima langsung tanpa perlu izin timpa.
   - `IDENTICAL`: Data dan tanggal rilis identik (selisih $< 10^{-4}$). Sistem melewati penulisan basis data secara aman.
   - `UPDATED`: Terdeteksi koreksi angka pada tanggal rilis yang sama. Mewajibkan persetujuan operator (*consent gate*).

### 25.2 Pembatasan Parameter Operasional (Deterministic Batch)
- **Dasarian (4 Parameter):** `pb20`, `pa150`, `pa200`, `pa300`.
- **Bulanan (3 Parameter):** `pa300`, `pa400`, `pa500`.
- Parameter non-operasional (`EnsMean`, `pb50`, `pb100`, `pb150`, `pa50`, `pa100`, `pa250`) diabaikan pada level parser.
- Pembersihan 1.864 baris lama non-operasional dari database menghasilkan ukuran batch deterministik:
  - 1 Dasarian Target = **208 baris** (52 stasiun manual x 4 parameter).
  - 1 Bulan Target = **156 baris** (52 stasiun manual x 3 parameter).

### 25.3 Eliminasi Bug 0 Stasiun & Sinkronisasi Tabel Probabilitas
- `get_probability_data()` mengkueri langsung tabel kanonikal `cews_forecast_snapshot` dengan fallback aman ke `cews_period_snapshot`.
- Mendukung pemfilteran parameter `issue_date` dinamis; jika dikosongkan, otomatis menyajikan rilis terbaru (`active_vintage_issue`).
- Menjamin kehadiran 57 stasiun master: 52 pos manual dengan angka probabilitas operasional, 5 pos ARG berstatus NULL (`-`).
- Kolom tabel adaptif otomatis sesuai resolusi: 4 kolom dasarian atau 3 kolom bulanan.

### 25.4 Dinamika Periode Masa Depan (Dynamic Lookahead Synchronization)
- `backend/period_service.py` memuat seluruh periode target yang tersimpan pada `cews_forecast_snapshot` ke selector dasarian secara dinamis.
- Periode mendatang ditandai dengan flag `is_forecast: True` dan label `[Prakiraan]`.
- Decision Engine PDKM dan PDCHT membaca parameter probabilitas langsung dari snapshot kanonikal.

### 25.5 Modernisasi Antarmuka Pengguna & Integrasi Tailwind CSS
- **Tailwind Engine Integration**: Instalasi `tailwindcss`, `postcss`, `autoprefixer` dengan `corePlugins: { preflight: false }` untuk menjaga keutuhan peta Leaflet.
- **CanonicalStorageStatusCard**: Tampilan institusional terang, badge LIVE berkedip hijau, jam WIB real-time, 5 kartu SPI berbadge ARG, 2 kartu Probabilitas ECMWF, dan modal daftar pos belum melapor.
- **OperationalDataManager**: 6 KPI cards, 4 tab navigasi, tabel vintage ECMWF berbadge status `AKTIF (Terbaru)` vs `HISTORIS`.
- **ProbabilityDataTable**: Dropdown multi-vintage, resolusi adaptif dasarian/bulanan, proteksi ARG strict NULL.
- **DataIngestionModal**: Wizard 3 langkah dengan konfirmasi izin eksplisit khusus rekaman `UPDATED`.

### 25.6 Ringkasan Verifikasi Penjaminan Mutu & Uji Penerimaan
- **72/72 Test Passed (100%)**:
  - `tests/integration/test_multivintage_ecmwf.py` : **12/12 PASSED (100%)**
  - `tests/integration/test_ui_period_metadata_idempotency.py` : **10/10 PASSED (100%)**
  - `tests/integration/test_operational_data_management.py` : **9/9 PASSED (100%)**
  - `tests/integration/test_period_aware_ingestion_hardening.py` : **23/23 PASSED (100%)**
  - `tests/integration/test_ingestion_end_to_end_acceptance.py` : **18/18 PASSED (100%)**
- **Integritas Basis Data**: `cews_rainfall_daily` tetap presisi pada **286.085 baris** (0 data hilang).
- **Frontend Production Build**: `npm run build` sukses 100% tanpa error sintaks dalam 27.93 detik.

---

## 26. INDEPENDENT FINAL ACCEPTANCE AUDIT, KONSOLIDASI UI/UX & KEANDALAN DATA OPERASIONAL (31 OKTOBER 2026)

### 26.1 Audit Independen Multi-Vintage ECMWF & Penegakan Cutoff Evaluasi
1. **Normalisasi Sentinel `target_dasarian = 0` untuk Resolusi Bulanan:**
   - Karena indeks unik SQL standar memperlakukan nilai `NULL` sebagai tidak setara (`NULL != NULL`), seluruh rekaman prakiraan skala `BULANAN` pada tabel `cews_forecast_snapshot` dinormalisasi menggunakan nilai sentinel integer `target_dasarian = 0`.
   - Dengan demikian, indeks unik `uq_fc_multi_vintage (station_id, forecast_resolution, target_year, target_month, target_dasarian, issue_date, forecast_parameter)` menegakkan keunikan fisik 100% baik untuk skala `DASARIAN` (`1, 2, 3`) maupun `BULANAN` (`0`).
2. **Aturan Seleksi Vintage Bebas Lookahead (`select_eligible_vintage`):**
   - Fungsi `select_eligible_vintage(available_issue_dates, evaluation_cutoff_date)` di [`backend/data_service.py`](file:///f:/TNJ/paper/DATA_ANALISIS_PRAKIRAAN/CEWS/MAS_HAYU/ASLI/backend/data_service.py) dan [`backend/period_service.py`](file:///f:/TNJ/paper/DATA_ANALISIS_PRAKIRAAN/CEWS/MAS_HAYU/ASLI/backend/period_service.py) memilih $\max(\text{issue\_date})$ yang memenuhi syarat $\text{issue\_date} \le \text{evaluation\_cutoff\_date}$.
   - Apabila seluruh vintage yang tersedia memiliki tanggal terbit setelah `evaluation_cutoff_date` ($\text{issue\_date} > \text{cutoff}$), fungsi mengembalikan `None` sehingga tidak pernah membocorkan rilis prakiraan masa depan ke evaluasi masa lalu.
3. **Deteksi Konflik Tanggal Rilis (Workbook vs Nama Berkas):**
   - `parse_probability_excel()` di [`backend/ingestion_service.py`](file:///f:/TNJ/paper/DATA_ANALISIS_PRAKIRAAN/CEWS/MAS_HAYU/ASLI/backend/ingestion_service.py) membandingkan tanggal rilis di nama berkas (`ver_YYYY.MM.DD`) dengan tanggal rilis di header lembar kerja internal, dan menolak berkas secara eksplisit jika keduanya berbeda.

### 26.2 Pembersihan & Standarisasi Database `cews_forecast_snapshot`
1. **Backup Tabel Audit:** Sebelum pembersihan, dibuat salinan cadangan penuh pada tabel MariaDB `cews_forecast_snapshot_backup_audit_20261031`.
2. **Standarisasi Nama Parameter & Pembersihan Stasiun ARG:**
   - Kode parameter warisan (`prob_below20`, `prob_above150`, `prob_above200`, `prob_above300`, `prob_above400`, `prob_above500`) dinormalisasi seluruhnya menjadi kode baku (`pb20`, `pa150`, `pa200`, `pa300`, `pa400`, `pa500`).
   - Rekaman probabilitas historis yang terikat pada 5 stasiun ARG (`160004`, `160020`, `160024`, `160040`, `160042`) dihapus dari `cews_forecast_snapshot` sehingga basis data hanya menyimpan 52 pos manual (`1.969 baris` bersih).

### 26.3 Konsistensi 57 Stasiun Master Lintas Seluruh Halaman
- Fungsi `get_harian_station_columns(master_only=True)` di [`backend/main.py`](file:///f:/TNJ/paper/DATA_ANALISIS_PRAKIRAAN/CEWS/MAS_HAYU/ASLI/backend/main.py) memfilter keluar pos ke-58 non-master (`Tanjung Riau Kota Batam` / `21710502A`, `in_master_57: false`) secara default.
- Seluruh halaman (`Peringatan Dini`, `Data Curah Hujan`, `Data SPI`, `Data Probabilitas`, dan `Manajemen Data Operasional`) kini menampilkan secara seragam tepat **57 Stasiun Master (52 Manual + 5 ARG)**.

### 26.4 Konsolidasi UI/UX, Deduplikasi Fitur & Audit Log Koreksi Terpadu
- **Penghapusan Tombol Global Redundan:** Tombol global `Input / Pembaruan Data Operasional` di header `DataCenter.jsx` dihapus karena sudah diwakili oleh tombol kontekstual di setiap halaman dataset.
- **Pembedaan Label Ekspor:** Tombol di header `DataCenter.jsx` diberi label **`Unduh Semua Dataset`**, sedangkan tombol kontekstual diberi label **`Ekspor Data CH`**, **`Ekspor Data SPI`**, dan **`Ekspor Data Probabilitas`**.
- **Penyederhanaan Modal Ingestion (`DataIngestionModal.jsx`):** Tab `Riwayat Audit` duplikat dan kartu penuh `CanonicalStorageStatusCard` di dalam modal digantikan dengan **1-Line Compact Storage Summary Bar** beserta tombol pintas **`Detail Penyimpanan ->`** dan **`Riwayat Batch Lengkap`**.
- **Tabel Audit Log Koreksi & Pembatalan Terpadu:** Tab 3 (`3. Koreksi & Pembatalan Rekaman`) pada `OperationalDataManager.jsx` dilengkapi filter dataset (`Semua`, `Curah Hujan`, `SPI Parquet`, `Probabilitas`) dan tabel riwayat audit log yang terhubung ke endpoint baru `GET /api/v1/ingestion/corrections-log`.
- **Akurasi KPI Operasional:** Fungsi `get_operational_summary()` diperbaiki agar metrik `total_new_records` dan `total_updated_records` hanya menjumlahkan batch berstatus `COMMITTED` (mengabaikan batch `ROLLED_BACK`).

### 26.5 Ringkasan Hasil Pengujian Akhir (126/126 Pengujian Otomatis Lulus 100%)
- **Suite Acceptance Independen Baru (`tests/integration/test_independent_final_acceptance.py`):** **7/7 PASSED (100%)**.
- **Seluruh Suite Pengujian Repositori (`pytest tests/`):** **126 passed, 0 failed, 0 skipped (100% PASS)**.
- **Verifikasi Visual Browser (Chrome Headless CDP `1920x1080` & `1366x768`):** **10/10 tangkapan layar terverifikasi**, **0 console errors**, **0 network errors**.
- **Integritas Data Kanonikal:**
  - `cews_rainfall_daily`: **286.085 baris** (100% utuh).
  - `stations`: **57 baris** (100% utuh).
  - Seluruh 5 berkas Parquet SPI cocok 100% dengan checksum MD5 baseline.

---

## 27. PENETAPAN PERINGATAN DINI WILAYAH (7 KABUPATEN/KOTA) & INTEGRASI PUBLIKASI JSON SIH3 (1 NOVEMBER 2026)

### 27.1 Evaluasi Terpisah PDKM & PDCHT per Kabupaten/Kota (7 Wilayah Administratif)
- Modul [`backend/regional_warning_service.py`](file:///f:/TNJ/paper/DATA_ANALISIS_PRAKIRAAN/CEWS/MAS_HAYU/ASLI/backend/regional_warning_service.py) mengevaluasi **PDKM (Kekeringan Meteorologis)** dan **PDCHT (Curah Hujan Tinggi)** secara terpisah untuk masing-masing dari 7 Kabupaten/Kota di Provinsi Kepulauan Riau (`21.01` Kab. Bintan, `21.02` Kab. Karimun, `21.03` Kab. Natuna, `21.04` Kab. Lingga, `21.05` Kab. Kepulauan Anambas, `21.71` Kota Batam, `21.72` Kota Tanjungpinang).
- Mendukung penuh kondisi **multi-bahaya simultan** pada kabupaten/kota yang sama (misalnya pos bagian utara memicu PDKM sementara pos bagian selatan memicu PDCHT) tanpa meleburkannya menjadi satu status tunggal tingkat provinsi.
- Setiap wilayah menyertakan pengenal ganda: `region_code` (`21.01`..`21.72`), `bps_code_compact` (`2101`..`2172`), dan `sih3_polygon_key` (`BINTAN`, `KARIMUN`, `NATUNA`, `LINGGA`, `KEPULAUAN ANAMBAS`, `KOTA BATAM`, `KOTA TANJUNGPINANG`) yang telah diverifikasi langsung terhadap geodatabase batas wilayah BMKG (`data/reference/boundaries/PDCHT_Kab_202501_das1.gdb`).

### 27.2 Kebijakan Kejujuran Cakupan Data (`INSUFFICIENT_DATA`)
- Apabila tidak ada pos pengamatan yang memicu peringatan dini di suatu wilayah **dan** persentase pos pengamatan yang memiliki data evaluasi valid berada di bawah ambang batas minimum (`DEFAULT_MIN_COVERAGE_PCT = 50.0%` atau `0` pos valid), sistem secara tegas menetapkan rekomendasi **`INSUFFICIENT_DATA`** — tidak pernah mengubahnya menjadi *False Green* (`AMAN`).

### 27.3 Keputusan Petugas, Override Berbukti & Alur Publikasi Berjenjang
- Tabel MariaDB `cews_regional_warning_decisions`, `cews_regional_decision_audit_log`, dan `cews_sih3_publications` menyimpan baik `recommended_level` (rekomendasi otomatis DSS-PIK) maupun `final_level` (keputusan akhir petugas).
- Apabila petugas melakukan *override* (`OPERATOR_OVERRIDE`), sistem mewajibkan pengisian `override_reason` dan `analysis_notes` serta mencatat jejak audit permanen.
- Alur publikasi menegakkan state machine **`DRAFT -> REVIEW -> APPROVED -> PUBLISHED`**. Hanya dokumen berstatus `APPROVED` yang dapat diterbitkan (`PUBLISHED`). Perubahan setelah `PUBLISHED` membentuk revisi baru (`revision + 1`) tanpa menimpa histori revisi sebelumnya.

### 27.4 Kontrak JSON Schema & Arsitektur Awal Integrasi SIH3
- Kontrak skema JSON resmi didokumentasikan pada [`docs/schemas/sih3_regional_warning.schema.json`](file:///f:/TNJ/paper/DATA_ANALISIS_PRAKIRAAN/CEWS/MAS_HAYU/ASLI/docs/schemas/sih3_regional_warning.schema.json) beserta 6 berkas contoh tervalidasi di `docs/schemas/examples/`.
- Endpoint publik `GET /api/v1/publications/sih3/latest.json` dapat diakses secara *read-only* oleh portal WordPress SIH3 Provinsi Kepulauan Riau dan secara ketat hanya menyajikan dokumen berstatus `PUBLISHED`.

---

## 28. PENYEMPURNAAN FINAL — DAFTAR TUNGGAL 7 WILAYAH & DUAL OUTPUT GENERATOR (JPG + JSON SIH3) (1 NOVEMBER 2026)

### 28.1 Penghapusan Tab Switcher & Penggabungan 7 Wilayah dalam Satu Daftar
- Menghapus tab toggle top-level (`PDKM` vs `PDCHT`) dan pemilih lingkup global (`GABUNGAN`, `PDKM Saja`, `PDCHT Saja`).
- Seluruh 7 kabupaten/kota (Bintan, Karimun, Kepulauan Anambas, Kota Batam, Kota Tanjungpinang, Lingga, Natuna) ditampilkan dalam **satu daftar terpadu tunggal**.

### 28.2 Penetapan Langsung Jenis Peringatan & Tingkat Klasifikasi per Kabupaten/Kota
- Setiap kartu wilayah memiliki sepasang dropdown kontrol mandiri:
  1. **Dropdown Jenis Peringatan (`warning_type`)**: `PDKM (Kekeringan)`, `PDCHT (Curah Hujan Tinggi)`, atau `Tidak Ada Peringatan (AMAN)`.
  2. **Dropdown Tingkat Klasifikasi (`final_level`)**: `WASPADA`, `SIAGA`, `AWAS` (jika memilih PDKM/PDCHT); atau terkunci otomatis pada `AMAN` / `DATA KURANG` (jika memilih `Tidak Ada Peringatan`).
- Mendukung penetapan heterogen dalam 1 rilis (misal Bintan PDKM Waspada, Natuna PDCHT Siaga, Batam PDCHT Waspada, Karimun Aman).
- Fitur *Terapkan Rekomendasi DSS* mengisi otomatis rekomendasi engine ke seluruh 7 wilayah.
- Proteksi *Honest Data Sufficiency*: jika pos valid $< 50\%$ dan tidak ada peringatan aktif, status tetap `INSUFFICIENT_DATA` (tidak false-green).

### 28.3 Peta Gabungan Resmi Format JPG (A4 Landscape, 150 DPI)
- Backend cartographic engine (`backend/map_generator.py`) mendukung mode `map_type='UNIFIED'`:
  - Format keluaran standar: **JPG (150 DPI, 95% quality, 1653 x 1170 piksel)** berukuran $\approx 530\text{ KB}$ yang cepat diunduh dan dibuka.
  - Setiap pulau diwarnai sesuai tingkat bahaya masing-masing dengan badge callout informatif: `NAMA WILAYAH | HAZARD - LEVEL`.
  - Judul peta resmi: `PETA PERINGATAN DINI IKLIM / PDKM & PDCHT (MULTI-BAHAYA)`.
  - Tetap menyediakan unduhan arsip PDF A4 Landscape.

### 28.4 Dual Output Action Buttons & Eliminasi WordPress Auto-Publish
- Panel aksi menghadirkan dua tombol terpisah yang berdampingan:
  - `[ Generate Peta JPG ]`: Menghasilkan peta gabungan JPG dan menampilkan kartu pratinjau beserta tombol unduh.
  - `[ Generate JSON SIH3 ]`: Membentuk dokumen JSON untuk seluruh 7 wilayah, memvalidasi terhadap JSON schema, membuka dialog pratinjau in-modal, dan menyediakan tombol salin clipboard serta unduh berkas `.json`.
- Tombol penerbitan otomatis WordPress (`Publikasikan ke Portal SIH3`) **dihapus sepenuhnya** dari UI modal untuk mencegah transmisi tidak sengaja ke portal publik. Berkas JSON dipanen via API atau diunggah manual oleh tim terkait.

### 28.5 Hasil Pengujian & Jaminan Mutu 100%
- **Suite Pengujian Terintegrasi (`tests/integration/test_official_map_modal_and_sih3_export.py`):** **12/12 PASSED (100%)** mencakup skenario single-hazard, multi-hazard, all-aman, override audit, resolusi konflik, data kurang, generasi JPG, validasi JSON schema, identitas unduh vs pratinjau, dan invarian navigasi 3 menu.
- **Audit Visual Headless Chrome CDP (`1920x1080` & `1366x768`):** 6 tangkapan layar tersimpan, **0 console errors**, **0 network errors**.
- **Integritas Basis Data & Parquet:**
  - `cews_rainfall_daily`: **286.085 baris** (100% utuh).
  - `stations`: **57 baris** (100% utuh).
  - `cews_period_snapshot`: **570 baris** (100% utuh).
  - 5 Berkas SPI Parquet checksum identik baseline.

---

## 29. PENYEMPURNAAN GENERATOR PETA RESMI BMKG, BATAS ADMINISTRATIF SHP, INTEGRASI ZOM & EKSPOR JSON (2 NOVEMBER 2026)

### 29.1 Pemulihan Konsep Peta PDKM dan PDCHT Terpisah (Single-Hazard Restoration)
- Menghilangkan konsep peta gabungan multi-hazard untuk keluaran resmi operasional BMKG.
- Kedua peta dipulihkan secara visual mengikuti template resmi historis BMKG (A4 Landscape, 1653 $\times$ 1170 piksel pada resolusi 150 DPI):
  - **Peta PDKM (`PETA_PDKM_{period_id}_{timestamp}.jpg`)**: Menggunakan template resmi PDKM (`04. Peta PDKM_Agustus II 26.jpg`), judul resmi `PETA PERINGATAN DINI / KEKERINGAN METEOROLOGIS`, tanpa badge callout buatan.
  - **Peta PDCHT (`PETA_PDCHT_{period_id}_{timestamp}.jpg`)**: Menggunakan template resmi PDCHT (`01. Peta Lampiran PDCI_Das II Jan 25.jpg`), judul resmi `PETA PERINGATAN DINI / CURAH HUJAN TINGGI`, tanpa badge callout buatan.
- Panel aksi **Keluaran Peringatan Dini** pada modal `OfficialMapModal.jsx` menyediakan 3 tombol terpisah:
  1. `[ Peta PDKM (JPG) ]`
  2. `[ Peta PDCHT (JPG) ]`
  3. `[ Ekspor JSON ]`

### 29.2 Presisi Pewarnaan Batas Administratif SHP (7 Kabupaten/Kota)
- Ekstraksi dan rasterisasi poligon resmi dari `KEPRI.shp` ke `data/reference/boundaries/kepri_kabkot.geojson` (7 kabupaten/kota) dan `kepri_kecamatan.geojson` (59 kecamatan).
- Sistem pemetaan raster (`backend/map_generator.py`) mengalibrasi koordinat kartografis secara presisi ke dalam kanvas 1653 $\times$ 1170 px:
  - **Main Map**: $sx = 1313/6$, $sy = -657/3$, $ox = 155 - sx \times 103.5$, $oy = 577.75$.
  - **Inset Kepulauan Anambas**: $x \in [965..1223], y \in [63..316]$.
  - **Inset Natuna**: $x \in [1308..1566], y \in [64..400]$.
- **Pemisahan Akurat Kota Tanjungpinang vs Kabupaten Bintan**: Kota Tanjungpinang (`21.72`) dan Kabupaten Bintan (`21.01`) dipisahkan secara strictly geometris berbasis SHP resmi tanpa kebocoran warna (*zero bleed*), dengan tetap melestarikan garis pantai, batas kecamatan hitam, garis grid koordinat, dan furnitur peta bawaan.

### 29.3 Integrasi SHP Zona Musim (ZOM) & Point-in-Polygon Spatial Join
- Layer 14 Zona Musim Provinsi Kepulauan Riau diekstraksi dari `Kepri__ZOM9120.shp` ke `data/reference/boundaries/kepri_zom.geojson`.
- Layanan spasial `backend/zom_service.py` dan endpoint `GET /api/v1/geo/zom-analysis` melakukan *point-in-polygon spatial join* terhadap 57 pos hujan master:
  - **56 stasiun** jatuh tepat di dalam poligon ZOM.
  - **1 stasiun (Stamet Tarempa / `21050101A`)** berada pada koordinat pulau (106.2167°BT, 3.2167°LU) di luar batas poligon ZOM yang telah disederhanakan. Sistem secara jujur menandainya sebagai `"Belum terpetakan / Tidak masuk poligon ZOM"` dengan rujukan fallback resmi ke `KEPRI_12`.
- Komponen Leaflet (`frontend/src/components/MapLeaflet.jsx`) dilengkapi layer toggle ZOM interaktif beserta popup rincian tipe musim (AMH, AMK, Puncak MH/MK), jumlah stasiun terpetakan, dan rata-rata HTH.

### 29.4 Ekspor JSON Terstandarisasi & Sanitasi String UI
- Format nama berkas JSON terstandarisasi: `PERINGATAN_DINI_KEPRI_{period_id}_{timestamp}.json`.
- Bagian `triggered_conditions` distrukturkan menjadi objek indikator yang jelas (`indicator`, `value`, `unit`, `operator`, `threshold`, `period`, `station_code`, `station_name`).
- Seluruh teks antarmuka pengguna (UI) disanitasi sehingga **0 kemunculan string "SIH3"** pada teks yang terlihat oleh pengguna.
- Enam contoh payload JSON terstandarisasi disediakan dan tervalidasi 100% pada `docs/schemas/examples/`:
  1. `01_all_regions_aman.json`
  2. `02_single_region_pdkm_active.json`
  3. `03_single_region_pdcht_active.json`
  4. `04_single_region_simultaneous_pdkm_pdcht.json`
  5. `05_region_insufficient_data.json`
  6. `06_region_operator_override.json`

### 29.5 Hasil Pengujian & Verifikasi Mutu Final
- **Integration Test Suite (`tests/integration/test_official_map_modal_and_sih3_export.py`):** **15/15 PASSED (100%)** dalam 142.06 detik (termasuk Skenario 13 untuk PDKM, Skenario 14 untuk PDCHT, dan Skenario 15 untuk presisi Tanjungpinang vs Bintan).
- **Verifikasi Spasial Peta (Skenario A s/d E):** 6 berkas JPG verifikasi berhasil di-generate dan tersimpan di `data/operational/maps/` dan direktori artefak.
- **Integritas Basis Data & Parquet:**
  - `cews_rainfall_daily`: **286.085 baris** (100% utuh).
  - `stations`: **57 baris** (100% utuh).
  - `cews_period_snapshot`: **570 baris** (100% utuh).
  - 5 Berkas SPI Parquet di `data/raw/spi/` utuh dan tidak tersentuh.
- **Invarian Sistem:** 3 Menu Navigasi Utama tetap terjaga (`Peringatan Dini`, `Data`, `Kamus`), zero external publishing.

---

## 30. PENYEMPURNAAN INGESTION DATA MAKRO BINTAN, FILTER PRATINJAU PERIODE, SPI WIDE PARQUET & SINKRONISASI TABEL DATA (2 NOVEMBER 2026)

### 30.1 Pengenalan & Penguraian Otomatis Workbook Makro Bintan (.xlsm)
- **Deteksi Format:** `backend/ingestion_service.py` (`detect_file_type`) diperluas untuk mendeteksi berkas berekstensi `.xlsm` dan lembar data operasional `Data_Pos_Hujan` atau kata kunci nama berkas `pos hujan` sebagai tipe `CURAH_HUJAN`.
- **Parsing Kolom Horisontal (Wide Format):**
  - Baris 2 lembar kerja dipindai pada rentang Kolom C hingga T untuk mengenali 18 pos hujan Bintan secara otomatis dan memetakannya ke ID stasiun kanonikal 9 karakter (misal `Pos Hujan Toapaya` -> `21010301A`, `Pos Hujan Sri Bintan` -> `21011305A`).
  - Kolom B dibaca sebagai tanggal observasi resmi (`YYYY-MM-DD`).
  - Nilai sel dinormalisasi dengan aman terhadap karakter khusus BMKG (`-` -> 0.0, `TTU` -> 0.0, `X` -> `MISSING`, `R` -> `DAMAGED`).
  - **Early Stopping:** Baris template kosong yang membentang hingga akhir tahun kalender dipotong (*early-stopped*), menjamin hanya data observasi riil yang diproses.

### 30.2 Pratinjau Terfokus & Filter Periode Ingestion
- Komponen `frontend/src/components/DataIngestionModal.jsx` ditambahkan filter periode interaktif:
  - Kotak centang pilihan periode terdeteksi (*detected periods checkboxes*) memungkinkan operator memilih secara selektif dasarian/bulan target yang ingin dikomit ke database.
  - Dropdown filter pratinjau perubahan (*diff table period filter*) memungkinkan operator memfokuskan pratinjau hanya pada periode tertentu tanpa harus menggulir ratusan baris.
  - Banner informasi secara langsung menghitung jumlah baris yang tampil vs total perubahan terdeteksi.

### 30.3 Standarisasi SPI Wide Parquet & Eliminasi Bug Tanggal 1970
- **Akar Masalah Bug 1970:** Komit SPI Bulanan sebelumnya menyimpan data format panjang (*long format*) dengan `RangeIndex(0, 1, ...)` melalui `df.to_parquet(index=False)`. Ketika dibaca oleh `data_service.py`, `pd.to_datetime(df.index)` mengonversi integer indeks sebagai nanodetik dari Unix Epoch (`1970-01-01 00:00:00`), menyebabkan tanggal salah dan kolom stasiun tidak terpetakan.
- **Solusi Tepat:**
  - `backend/ingestion_service.py`: Mem-pivot data SPI yang diunggah ke format matriks lebar (*wide matrix*) dengan `pivot(index='date', columns='station_id', values='spi_value')` dan menggabungkannya ke `SPI_monthly.parquet` dengan tetap melestarikan `DatetimeIndex` dan tepat 52 kolom stasiun manual.
  - Menghapus kolom metadata asing yang mencemari Parquet (`station_id`, `station_name`, `date`, `change_type`, dll.).
  - `backend/data_service.py`: Fungsi `get_cached_spi_df` dilengkapi lapisan *self-healing* yang mendeteksi RangeIndex, menyaring tahun $\le 1970$, dan menginjeksi `period_label` berbahasa Indonesia (misal: `"Oktober 2026"`).
  - Panggilan `clear_spi_cache()` otomatis dijalankan pada setiap komit SPI, menjamin data langsung tampil di dashboard tanpa perlu restart server.

### 30.4 Redesain Tabel Probabilitas ECMWF & Endpoint Dinamis
- **Endpoint Dinamis:** Endpoint `GET /api/v1/probability/periods` (`get_probability_periods_list()`) mengekstrak seluruh periode target prakiraan riil dari `cews_forecast_snapshot` dikelompokkan berdasarkan resolusi `dasarian` dan `bulanan`.
- **Desain UI Standar Emas:** Komponen `frontend/src/components/ProbabilityDataTable.jsx` direfaktor menyerupai `DailyRainfallTable.jsx`:
  - Tombol pemilih resolusi: **PROBABILITAS DASARIAN (pb20, pa150, pa200, pa300)** vs **PROBABILITAS BULANAN (pa300, pa400, pa500)**.
  - Dropdown periode dinamis dan pemilih vintage dengan badge hijau `AKTIF`.
  - Format angka skala persentase `0–100%` dengan sorotan visual (*warning badge*) untuk probabilitas $\ge 70\%$.
  - 5 Pos ARG diberi penanda otoritatif: `— / Tidak tersedia (ARG)`.

### 30.5 Verifikasi & Jaminan Integritas Data
- **Hasil Pengujian Otomatis:**
  - `tests/integration/test_bintan_xlsm_ingestion.py`: **5/5 PASSED (100%)**.
  - `tests/integration/test_ingestion_table_synchronization.py`: **7/7 PASSED (100%)**.
  - **Total 12/12 Integration Tests Passed** dalam 35.17 detik.
- **Frontend Production Build:** `npm run build` sukses 100% tanpa galat (Vite v5.4.11, 461 modul tertransformasi).
- **Integritas Basis Data:**
  - `cews_rainfall_daily`: **286.742 baris** (100% utuh tanpa kerusakan baseline).
  - `stations`: **57 baris** (52 manual + 5 ARG utuh).
  - 5 Berkas Parquet SPI di `data/raw/spi/` dan `data/processed/` berformat matriks lebar kanonikal murni.

---
**Dokumen ini disahkan sebagai Pedoman Resmi Serah Terima DSS-PIK BMKG Stasiun Meteorologi Kelas II Raja Haji Fisabilillah Tanjungpinang.**
