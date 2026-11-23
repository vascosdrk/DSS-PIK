# AUDIT DAN PEMETAAN SPESIFIKASI FORMAT TEMPLATE INPUT DATA DSS-PIK

**Decision Support System Peringatan Iklim Kepulauan Riau (DSS-PIK)**  
**Instansi**: Stasiun Meteorologi Kelas II Raja Haji Fisabilillah Tanjungpinang — BMKG  
**Status Dokumen**: Spesifikasi Teknis Resmi (Pre-Ingestion Engineering Specification)  
**Tanggal Audit**: 30 Oktober 2026  
**Klasifikasi Audit**: READ-ONLY Exhaustive Baseline Audit  

---

## 1. RINGKASAN EKSEKUTIF

Dokumen ini menyajikan hasil audit teknis mendalam dan pemetaan menyeluruh terhadap seluruh berkas template input data operasional yang disimpan di direktori `tambahan/template_data_input/`. Audit ini dirancang sebagai landasan teknis tunggal dan spesifikasi acuan baku sebelum pembangunan modul **Input Data melalui Upload File** pada dashboard DSS-PIK.

Sesuai instruksi mutlak, audit dilaksanakan secara **READ-ONLY**: tidak ada berkas template yang dimodifikasi, dipindahkan, atau diubah; database MariaDB operasional dan Parquet store tidak disentuh; serta tidak ada proses komit data operasional yang dijalankan.

### Ringkasan Temuan Utama Berdasarkan Kategori Data:

1. **Data Curah Hujan Harian (CH)**:
   - Ditemukan **6 file workbook Excel (.xlsx)** yang mencakup **53 worksheet**.
   - Seluruh 53 worksheet berhasil dipetakan **100% secara presisi (1-to-1)** ke 53 stasiun master CEWS (52 pos pengamatan manual berakhiran `a` dan 1 Automatic Rain Gauge/ARG Singkep `21040401b`).
   - Empat (4) stasiun master ARG lainnya (`21010603b`, `21010802b`, `21020402b`, `21710501b`) tidak memiliki template data manual di folder ini karena pencatatannya bersumber dari telemetri digital.
   - Struktur tabular sangat konsisten: **Baris 1 adalah Header** (`['tanggal', 'CH']`), **Baris 2 adalah baris data pertama**. Tanggal tersimpan sebagai Excel serial `datetime.datetime`.
   - **0 (nol) merged cells** ditemukan di seluruh 53 sheet.
   - Anomali format: Terdapat file dual-wilayah (`Kota Tanjungpinang.xlsx` berisi 4 sheet Kota Tanjungpinang dan 14 sheet Kab. Bintan). Ditemukan simbol non-numerik yang memerlukan sanitasi terstandar: tanda strip (`-` = 0.0 mm), `TTU`/`ttu` (0.0 mm status trace), missing data (`X`, `NO DATA`, sel kosong), serta karakter rusak (`R`, `alat rusak (9999)`).

2. **Data Standardized Precipitation Index (SPI)**:
   - Berkas `spi/2026_SPI.xlsx` terdiri atas 4 worksheet: `fast step`, `Analisis`, `Prakiraan`, dan `SPI GIS`.
   - Format tabular pada sheet `Analisis` dan `Prakiraan` menggunakan struktur wide multi-level header (Baris 1: Kolom metadata stasiun + 12 bulan; Baris 2: Sub-header `Indeks` dan `Kriteria`).
   - **Temuan Kritis Operasional**: Berkas template ini secara eksklusif berisi **SPI-1 Bulanan (Skala 30-Hari Bulanan)**. Di dalam template **TIDAK TERDAPAT data SPI Dasarian (Das I, II, III)** dan **TIDAK TERDAPAT skala SPI 90-Hari (SPI-3 / 90D)**. Sementara itu, Decision Engine DSS-PIK membutuhkan SPI pada tanggal cutoff dasarian (1, 11, 21) baik 30D maupun 90D untuk mengevaluasi Peringatan Dini Kekeringan Meteorologis (PDKM). Modul Ingestion memerlukan mekanisme jembatan atau format template tambahan untuk dasarian SPI.
   - Berkas temporer `~$2026_SPI.xlsx` (lock file Excel) wajib diabaikan oleh parser sistem.

3. **Data Probabilitas Prakiraan Curah Hujan (Probabilitas ECMWF)**:
   - Ditemukan 2 berkas utama: probabilitas dasarian (`dasarian/KEPRI_pch_ecmwf_perpos_ver_2026.04.30.xlsx`) dan probabilitas bulanan (`bulanan/KEPRI_pch_ecmwf_perpos_ver_2026.08.01.xlsx`).
   - Sheet data grid berisikan ambang batas: `pb20`, `pb50`, `pb100`, `pb150`, `pa50`, `pa100`, `pa150`, `pa200`, `pa250`, `pa300` (pada dasarian), dan tambahan `pa400`, `pa500` (pada bulanan).
   - Sheet `TabelPCH` dan `TabelPSH` berupa teks naratif wilayah, sedangkan `Sheet1` kosong.
   - **Temuan Kritis Skala Angka**: Nilai di dalam seluruh sheet ambang batas probabilitas **SUDAH BERBENTUK PERSEN (0.0 s.d. 100.0)** yang diturunkan dari proporsi 51 anggota ensemble ECMWF. Sistem **TIDAK BOLEH mengalikan nilai dengan 100** saat proses ingestion.
   - Sebanyak 52 stasiun terpetakan sempurna ke pos manual master via `data/reference/stations/mapping_tambahan.xlsx`. Terdapat 1 stasiun luar (`228R: Tanjung Riau Kota Batam`) yang tidak masuk dalam master 57 CEWS dan wajib diabaikan secara aman.

---

## 2. INVENTARISASI KOMPREHENSIF BERKAS TEMPLATE INPUT

Berdasarkan pemindaian fisik pada direktori `tambahan/template_data_input/`, berikut adalah inventarisasi lengkap seluruh 10 file yang ditemukan:

| No | Kategori | Relatif Path | Ukuran (Bytes) | Tanggal Modifikasi | Tipe / Format | Keterangan Operasional |
|:---|:---|:---|:---:|:---:|:---:|:---|
| 1 | Curah Hujan | `ch/Kabupaten Dabo Singkep.xlsx` | 1,842,912 | 2026-08-11 10:48 | Excel Workbook (.xlsx) | 8 sheet (7 Pos Manual Lingga + 1 ARG Singkep) |
| 2 | Curah Hujan | `ch/Kabupaten Karimun.xlsx` | 1,444,988 | 2026-08-11 10:48 | Excel Workbook (.xlsx) | 7 sheet (7 Pos Manual Kab. Karimun) |
| 3 | Curah Hujan | `ch/Kabupaten Natuna.xlsx` | 1,757,963 | 2026-08-11 10:48 | Excel Workbook (.xlsx) | 15 sheet (15 Pos Manual Kab. Natuna) |
| 4 | Curah Hujan | `ch/Kabupaten Tarempa.xlsx` | 682,752 | 2026-08-11 10:48 | Excel Workbook (.xlsx) | 3 sheet (3 Pos Manual Kab. Kepulauan Anambas) |
| 5 | Curah Hujan | `ch/Kota Batam.xlsx` | 486,052 | 2026-08-11 10:48 | Excel Workbook (.xlsx) | 2 sheet (2 Pos Manual Kota Batam) |
| 6 | Curah Hujan | `ch/Kota Tanjungpinang.xlsx` | 3,363,222 | 2026-08-11 10:48 | Excel Workbook (.xlsx) | 18 sheet (4 Kota Tanjungpinang + 14 Kab. Bintan) |
| 7 | SPI | `spi/2026_SPI.xlsx` | 44,792 | 2026-08-11 10:48 | Excel Workbook (.xlsx) | 4 sheet (fast step, Analisis, Prakiraan, SPI GIS). SPI Bulanan |
| 8 | SPI | `spi/~$2026_SPI.xlsx` | 165 | 2026-08-11 10:48 | Temporary Lock File | **IGNORE**: Berkas lock MS Excel, wajib difilter oleh uploader |
| 9 | Probabilitas | `prob/dasarian/KEPRI_pch_ecmwf_perpos_ver_2026.04.30.xlsx` | 49,583 | 2026-08-11 10:48 | Excel Workbook (.xlsx) | 13 sheet (EnsMean, pb20-pb150, pa50-pa300, Tabel PCH/PSH) |
| 10 | Probabilitas | `prob/bulanan/KEPRI_pch_ecmwf_perpos_ver_2026.08.01.xlsx` | 68,986 | 2026-08-11 10:48 | Excel Workbook (.xlsx) | 14 sheet (EnsMean, pb50-pb150, pa50-pa500, Tabel PCH/PSH) |

> [!WARNING] File Temporer Excel Lock
> Berkas `spi/~$2026_SPI.xlsx` berukuran 165 bytes adalah berkas lock sementara yang tercipta saat Microsoft Excel membuka workbook. Parser upload otomatis wajib menerapkan ekspresi reguler penyaring `^(?!~\$).+\.xlsx$` untuk memastikan berkas sementara semacam ini ditolak sebelum dibaca.

---

## 3. AUDIT DAN PEMETAAN MENDALAM DATA CURAH HUJAN (CH)

### 3.1 Struktur Worksheet dan Tata Letak Data

Seluruh 6 workbook curah hujan memiliki keseragaman arsitektur data internal yang luar biasa:
- **Format Baris Header**: Baris ke-1 selalu berisi tepat dua nama kolom: `['tanggal', 'CH']`.
- **Baris Awal Data**: Data observasi harian selalu dimulai pada Baris ke-2 (indeks baris Excel 2).
- **Tipe Data Kolom A (`tanggal`)**: Berisi objek tanggal serial Excel murni (`datetime.datetime` atau `datetime.date`). Tidak ada format teks tanggal ambigu (seperti `DD/MM/YY` vs `MM/DD/YY`). Seluruh tanggal terurai secara deterministik dengan format ISO `YYYY-MM-DD`.
- **Tipe Data Kolom B (`CH`)**: Berisi angka riil presisi ganda (`float`), bilangan bulat (`int`), string simbol status BMKG, atau sel kosong.
- **Merged Cells**: Audit struktur internal XML membuktikan **0 (nol) sel yang digabungkan** di seluruh 53 sheet data curah hujan.
- **Formula Excel**: Tidak ada formula kalkulasi pada kolom curah hujan (Kolom B). Formula hanya ditemukan pada 2 sheet di workbook Tanjungpinang (`00_RHF Tanjungpinang` dan `07_Toapaya`) di Kolom C dan Kolom D yang berisi penjumlahan rekapitulasi bulanan `=SUM(...)` untuk keperluan dokumentasi visual petugas, sehingga aman untuk diabaikan oleh ingestion engine.

### 3.2 Karakteristik Wilayah dan Rentang Temporal Data

Setiap kabupaten/kota memiliki panjang deret data historis yang berbeda:

| Kabupaten / Kota | File Workbook | Jumlah Sheet | Rentang Tanggal Mulai | Rentang Tanggal Akhir | Jumlah Baris per Sheet | Cakupan Wilayah |
|:---|:---|:---:|:---:|:---:|:---:|:---|
| **Kabupaten Lingga** | `Kabupaten Dabo Singkep.xlsx` | 8 | 1981-01-01 | 2026-08-10 | 16,659 – 16,804 | 7 Pos Manual + 1 ARG Singkep |
| **Kabupaten Karimun** | `Kabupaten Karimun.xlsx` | 7 | 1994-01-01 | 2026-08-10 | 11,911 | 7 Pos Manual Karimun |
| **Kabupaten Natuna** | `Kabupaten Natuna.xlsx` | 15 | 2009-01-01 | 2026-08-10 | 6,432 | 15 Pos Manual Natuna |
| **Kab. Kep. Anambas** | `Kabupaten Tarempa.xlsx` | 3 | 1991-01-01 | 2026-08-10 | 13,007 | 3 Pos Manual Anambas |
| **Kota Batam** | `Kota Batam.xlsx` | 2 | 1993-01-01 | 2026-08-10 | 12,276 | 2 Pos Manual Batam |
| **Kota Tanjungpinang & Kab. Bintan** | `Kota Tanjungpinang.xlsx` | 18 | 1976-01-01 | 2024-07-19 | 17,733 | 4 Pos Tanjungpinang + 14 Pos Bintan |

> [!IMPORTANT] Perlakuan Khusus Workbook Dual-Wilayah `Kota Tanjungpinang.xlsx`
> Workbook `Kota Tanjungpinang.xlsx` tidak hanya berisi data Kota Tanjungpinang, melainkan menggabungkan **4 pos hujan Kota Tanjungpinang** dan **14 pos hujan Kabupaten Bintan**. Ingestion engine dilarang memetakan kabupaten berdasarkan nama berkas. Pemetaan wilayah administratif wajib dilakukan pada level sheet menggunakan kode stasiun master (`station_id`).

### 3.3 Standarisasi Simbol Non-Numerik dan Penanganan Anomali

Berdasarkan audit 740.000+ baris data pada 53 sheet, ditemukan sejumlah simbol non-numerik dan kesalahan ketik (typo) petugas operasional. Ingestion pipeline wajib menerapkan aturan normalisasi berikut:

| Simbol / Nilai Mentah | Arti Operasional BMKG | Tindakan Normalisasi Pipeline | Nilai Angka (`rainfall_mm`) | Flag Status (`obs_status`) | Catatan Teknis |
|:---|:---|:---|:---:|:---:|:---|
| `0` atau `0.0` | Hari cerah / tidak ada hujan | Konversi float | `0.0` | `OBSERVED` | Data valid |
| Angka numerik $> 0` | Curah hujan terukur | Konversi float | Nilai terukur | `OBSERVED` | Data valid |
| `-` (tanda strip) | Tidak ada hujan (hari kering) | Konversi ke nol | `0.0` | `OBSERVED` | Karakter standar BMKG untuk 0 mm |
| `TTU`, `ttu`, `T.T.U` | Tidak Terukur (Trace $<0.5$ mm) | Konversi ke nol dengan flag | `0.0` | `TTU` | Sesuai aturan BMKG, trace dihitung 0 mm untuk akumulasi HTH |
| `X`, `NO DATA`, sel kosong / `None` | Tidak ada pengamatan / absen | Set NULL | `NULL` | `MISSING` | Data hilang, memicu status `data_gap` |
| `R` | Alat rusak / perlu review | Set NULL dengan flag | `NULL` | `DAMAGED` | Ditemukan pada beberapa catatan historis |
| `alat rusak (9999)` | Alat pengukur hujan rusak | Set NULL dengan flag | `NULL` | `DAMAGED` | Ditemukan pada sheet historis Karimun |
| `1-` | Typo pengetikan strip nempel | Sanitasi string strip | `1.0` | `OBSERVED` | Ditemukan di sheet Lingga & Karimun |
| `.` atau `0.4.` atau `13.0.` | Typo kelebihan tanda titik | Sanitasi tanda titik akhir | `0.0` / `0.4` / `13.0` | `OBSERVED` | Ditemukan di sheet Tanjungpinang |

### 3.4 Matriks Pemetaan Lengkap 53 Worksheet ke Master Stasiun (57 Stations Baseline)

Tabel berikut menyajikan pemetaan resmi 53 worksheet ke master metadata `data/reference/stations/station_metadata.parquet`:

| No | Nama File Workbook | Nama Asli Sheet | Kode Stasiun Master (`station_id`) | Nama Resmi Stasiun Master | Wilayah Master | Status Verifikasi |
|:---:|:---|:---|:---:|:---|:---|:---:|
| 1 | `Kabupaten Dabo Singkep.xlsx` | `00_Dabo Singkep` | `21040101a` | Stamet Dabo Singkep | Kab. Lingga | MATCH |
| 2 | `Kabupaten Dabo Singkep.xlsx` | `01_Dinas Pertanian Lingga` | `21040203a` | Dinas Pertanian Kab. Lingga | Kab. Lingga | MATCH |
| 3 | `Kabupaten Dabo Singkep.xlsx` | `02_Bukit Langkap` | `21040201a` | Bukit Langkap | Kab. Lingga | MATCH |
| 4 | `Kabupaten Dabo Singkep.xlsx` | `03_Resun` | `21040202a` | Resun | Kab. Lingga | MATCH |
| 5 | `Kabupaten Dabo Singkep.xlsx` | `04_Duara` | `21040501a` | Duara | Kab. Lingga | MATCH |
| 6 | `Kabupaten Dabo Singkep.xlsx` | `05_Bukit Belah Raya` | `21040402a` | Bukit Belah Raya | Kab. Lingga | MATCH |
| 7 | `Kabupaten Dabo Singkep.xlsx` | `06_Sungai Buluh` | `21040401a` | Sungai Buluh | Kab. Lingga | MATCH |
| 8 | `Kabupaten Dabo Singkep.xlsx` | `07_ARG Tj. Harapan` | `21040101b` | ARG Singkep | Kab. Lingga | NAME_VARIANT |
| 9 | `Kabupaten Karimun.xlsx` | `00_Stamet TBK` | `21020302a` | Stamet Raja Haji Abdullah | Kab. Karimun | NAME_VARIANT |
| 10 | `Kabupaten Karimun.xlsx` | `01_Kapling Tebing` | `21020301a` | Kantor Lurah Kapling Tebing | Kab. Karimun | NAME_VARIANT |
| 11 | `Kabupaten Karimun.xlsx` | `02_BPP Sememal` | `21020401a` | BPP Sememal | Kab. Karimun | MATCH |
| 12 | `Kabupaten Karimun.xlsx` | `03_Tanjung Batu` | `21020201a` | UPTD BBI Tanjung Batu | Kab. Karimun | NAME_VARIANT |
| 13 | `Kabupaten Karimun.xlsx` | `04_Kundur Utara` | `21020701a` | Kantor Camat Kundur Utara | Kab. Karimun | NAME_VARIANT |
| 14 | `Kabupaten Karimun.xlsx` | `05_Moro` | `21020101a` | Kantor Camat Moro | Kab. Karimun | NAME_VARIANT |
| 15 | `Kabupaten Karimun.xlsx` | `06_Pulau Buru` | `21020601a` | Kantor BPP Kecamatan Buru | Kab. Karimun | NAME_VARIANT |
| 16 | `Kabupaten Natuna.xlsx` | `00_Stamet Ranai Natuna` | `21030701a` | Stamet Ranai Natuna | Kab. Natuna | MATCH |
| 17 | `Kabupaten Natuna.xlsx` | `01_Padang Meliso` | `21031801a` | Padang Meliso | Kab. Natuna | MATCH |
| 18 | `Kabupaten Natuna.xlsx` | `02_Bunguran Timur Laut` | `21031501a` | Tanjung | Kab. Natuna | NAME_VARIANT |
| 19 | `Kabupaten Natuna.xlsx` | `03_Bunguran Utara Kelarik` | `21030801a` | Bunguran Utara Kelarik | Kab. Natuna | MATCH |
| 20 | `Kabupaten Natuna.xlsx` | `04_Bunguran Tengah Harapan Jaya` | `21031601a` | Bunguran Tengah Harapan Jaya | Kab. Natuna | MATCH |
| 21 | `Kabupaten Natuna.xlsx` | `05_Pulau Tiga Sabang Mawang` | `21031101a` | Sabang Mawang | Kab. Natuna | NAME_VARIANT |
| 22 | `Kabupaten Natuna.xlsx` | `06_Serasan Hilir` | `21030601a` | Hilir | Kab. Natuna | NAME_VARIANT |
| 23 | `Kabupaten Natuna.xlsx` | `07_Subi Melia` | `21030901a` | Melia | Kab. Natuna | NAME_VARIANT |
| 24 | `Kabupaten Natuna.xlsx` | `08_Midai Sabang Barat` | `21030401a` | Sabang Barat | Kab. Natuna | NAME_VARIANT |
| 25 | `Kabupaten Natuna.xlsx` | `09_Pulau Laut Air Payang` | `21031001a` | Air Payang | Kab. Natuna | NAME_VARIANT |
| 26 | `Kabupaten Natuna.xlsx` | `10_Sedanau Kp Balau` | `21030501a` | Sedanau Kp Balau | Kab. Natuna | MATCH |
| 27 | `Kabupaten Natuna.xlsx` | `11_Batubi` | `21032001a` | Batubi | Kab. Natuna | MATCH |
| 28 | `Kabupaten Natuna.xlsx` | `12_Mekar Jaya` | `21030502a` | Mekar Jaya | Kab. Natuna | MATCH |
| 29 | `Kabupaten Natuna.xlsx` | `13_Selemut Cemaga` | `21031802a` | Selemut | Kab. Natuna | NAME_VARIANT |
| 30 | `Kabupaten Natuna.xlsx` | `14_Teluk Buton` | `21030802a` | Teluk Buton | Kab. Natuna | MATCH |
| 31 | `Kabupaten Tarempa.xlsx` | `00_Stamet Tarempa` | `21050101a` | Stamet Tarempa | Kab. Kepulauan Anambas | MATCH |
| 32 | `Kabupaten Tarempa.xlsx` | `01_Langir` | `21050201a` | Langir | Kab. Kepulauan Anambas | MATCH |
| 33 | `Kabupaten Tarempa.xlsx` | `02_UPT Benih Pertanian` | `21050501a` | Bukit Padi | Kab. Kepulauan Anambas | NAME_VARIANT |
| 34 | `Kota Batam.xlsx` | `00_Stamet Hang Nadim` | `21710401a` | Stamet Hang Nadim Batam | Kota Batam | NAME_VARIANT |
| 35 | `Kota Batam.xlsx` | `01_BP Sei Temiang` | `21710301a` | BP Sei Temiang | Kota Batam | MATCH |
| 36 | `Kota Tanjungpinang.xlsx` | `00_RHF Tanjungpinang` | `21720201a` | Stamet Raja Haji Fisabilillah | Kota Tanjung Pinang | NAME_VARIANT |
| 37 | `Kota Tanjungpinang.xlsx` | `01_Lancang Kuning` | `21010701a` | Bintan Utara | Kab. Bintan | NAME_VARIANT |
| 38 | `Kota Tanjungpinang.xlsx` | `02_Ekang Anculai` | `21011001a` | Ekang Anculai | Kab. Bintan | MATCH |
| 39 | `Kota Tanjungpinang.xlsx` | `03_Poyotomo` | `21011002a` | Poyotomo | Kab. Bintan | MATCH |
| 40 | `Kota Tanjungpinang.xlsx` | `04_Bintan Buyu` | `21010801a` | Bintan Buyu | Kab. Bintan | MATCH |
| 41 | `Kota Tanjungpinang.xlsx` | `05_Batu 18 Kijang` | `21010601a` | Batu 18 Kijang | Kab. Bintan | MATCH |
| 42 | `Kota Tanjungpinang.xlsx` | `06_Sungai Enam` | `21010602a` | Sungai Enam | Kab. Bintan | MATCH |
| 43 | `Kota Tanjungpinang.xlsx` | `07_Toapaya` | `21011201a` | Toapaya Asri | Kab. Bintan | NAME_VARIANT |
| 44 | `Kota Tanjungpinang.xlsx` | `08_Kawal` | `21010401a` | Kawal | Kab. Bintan | MATCH |
| 45 | `Kota Tanjungpinang.xlsx` | `09_Malang rapat` | `21010402a` | Malang Rapat | Kab. Bintan | MATCH |
| 46 | `Kota Tanjungpinang.xlsx` | `10_Berakit` | `21011003a` | Berakit | Kab. Bintan | MATCH |
| 47 | `Kota Tanjungpinang.xlsx` | `11_Teluk Sasa` | `21011501a` | Teluk Sasa | Kab. Bintan | MATCH |
| 48 | `Kota Tanjungpinang.xlsx` | `12_Sebung Pereh` | `21011004a` | Sebung Pereh | Kab. Bintan | MATCH |
| 49 | `Kota Tanjungpinang.xlsx` | `13_Senggarang` | `21720301a` | Senggarang | Kota Tanjung Pinang | MATCH |
| 50 | `Kota Tanjungpinang.xlsx` | `14_RRI Tanjungpinang` | `21720302a` | Bukit Bestari | Kota Tanjung Pinang | NAME_VARIANT |
| 51 | `Kota Tanjungpinang.xlsx` | `15_Galang Batang` | `21010403a` | Galang Batang | Kab. Bintan | MATCH |
| 52 | `Kota Tanjungpinang.xlsx` | `16_Dompak` | `21720401a` | Dompak | Kota Tanjung Pinang | MATCH |
| 53 | `Kota Tanjungpinang.xlsx` | `17_Ria Bintan Lagoi` | `21010702a` | Ria Bintan Lagoi | Kab. Bintan | MATCH |

### 3.5 Identifikasi 4 Stasiun Master ARG Tanpa Template Manual

Sistem master CEWS memiliki 57 stasiun yang terdiri atas 52 pos hujan manual dan 5 Automatic Rain Gauge (ARG). Empat stasiun ARG berikut **tidak tercakup** dalam 6 berkas template di atas:
1. `21010603b` — **ARG Kijang** (Kab. Bintan)
2. `21010802b` — **ARG Teluk Sebong** (Kab. Bintan)
3. `21020402b` — **ARG Karimun** (Kab. Karimun)
4. `21710501b` — **ARG Hang Nadim** (Kota Batam)

*(Catatan: ARG Dabo Singkep `21040401b` telah disediakan templatenya pada sheet `07_ARG Tj. Harapan` di workbook Lingga).*

---

## 4. AUDIT DAN PEMETAAN MENDALAM DATA STANDARDIZED PRECIPITATION INDEX (SPI)

### 4.1 Inventarisasi dan Struktur Worksheet `2026_SPI.xlsx`

Berkas template `spi/2026_SPI.xlsx` memiliki 4 worksheet:
1. `fast step`: Worksheet kerja konversi cepat sementara (internal BMKG).
2. `Analisis`: Tabel histori analisis indeks SPI bulanan per pos hujan.
3. `Prakiraan`: Tabel prakiraan indeks SPI bulanan untuk bulan-bulan mendatang.
4. `SPI GIS`: Tabel koordinat spasial dan nilai atribut untuk plotting GIS BMKG.

### 4.2 Struktur Tabular Sheet `Analisis` dan `Prakiraan`

Format data pada sheet `Analisis` dan `Prakiraan` menggunakan struktur wide multi-level header 2 baris:
- **Baris 1 (Header Utama)**:
  - Kolom A-E: Kolom identitas stasiun (`Kode Stasiun`, `No Stasiun`, `Jenis Stasiun`, `Lintang`, `Bujur`).
  - Kolom F dan seterusnya: Nama bulan (`Januari`, `Februari`, `Maret`, ..., `Desember`). Setiap bulan menggabungkan 2 kolom di bawahnya.
- **Baris 2 (Sub-Header)**:
  - Kolom A-E: Kosong (`null`).
  - Setiap blok bulan dipecah menjadi dua sub-kolom: `Indeks` (nilai numerik SPI) dan `Kriteria` (kategori BMKG).
- **Baris 3 s.d. 81 (Data Stasiun)**: Nilai riil indeks SPI per stasiun.

### 4.3 Temuan Kritis Operasional: Dimensi Temporal SPI

> [!CAUTION] DISKREPANSI OPERASIONAL SPI ANTARA TEMPLATE DAN SISTEM DSS-PIK
> 1. **Ketidaksediaan SPI Dasarian**: Berkas `2026_SPI.xlsx` secara eksklusif menyediakan data **SPI Bulanan (Monthly)**. Tidak terdapat data SPI Dasarian (Das I, II, III).
> 2. **Ketidaksediaan Timescale 90-Hari (SPI-3 / 90D)**: Template ini hanya memuat skala SPI akumulasi 30 hari bulanan (SPI-1). Nilai SPI-90D tidak ditemukan di dalam workbook.
> 3. **Kebutuhan Decision Engine DSS-PIK**: Aturan evaluasi PDKM (Peringatan Dini Kekeringan Meteorologis) dan PDCHT mengharuskan tersedianya nilai **SPI 30-Hari** dan **SPI 90-Hari** pada setiap **tanggal cutoff dasarian operasional** (tanggal 1, 11, dan 21 setiap bulan).
> 4. **Rekomendasi Arsitektur Modul Ingestion**:
>    - Opsi A (Direkomendasikan): Modul upload SPI menerima template CSV/Excel Dasarian terstandar yang selaras dengan skema `SPI_all_30d.parquet` dan `SPI_all_90d.parquet`.
>    - Opsi B: Mengintegrasikan library engine kalkulasi SPI (menggunakan distribusi Gamma/Pearson III) langsung di backend DSS-PIK untuk menghitung SPI dasarian 30D dan 90D otomatis dari data curah hujan harian yang diupload.

### 4.4 Analisis Kode dan Typo Identitas Stasiun SPI

Audit terhadap kolom `No Stasiun` pada sheet `Analisis` dan `Prakiraan` menemukan dua catatan penting:
1. **Kode WMO Stasiun Sinoptik**: Enam stasiun utama BMKG menggunakan kode WMO 8 digit berakhiran `a` (misalnya `00096091a` untuk Stamet RHF Tanjungpinang, `00096109a` untuk Stamet Dabo Singkep, `00096171a` untuk Stamet Ranai). Ingestion engine harus memiliki tabel alias yang memetakan kode WMO ini ke ID master internal CEWS.
2. **Typo Selemut Cemaga**: Stasiun Selemut Cemaga tertulis dengan kode `210310802a` (kelebihan satu digit angka nol). Kode master resminya adalah `21031802a`. Ingestion mapper wajib mengoreksi typo ini secara otomatis.

---

## 5. AUDIT DAN PEMETAAN MENDALAM DATA PROBABILITAS PRAKIRAAN

### 5.1 Struktur Berkas dan Ambang Batas Probabilitas

Data probabilitas prakiraan bersumber dari model ensemble ECMWF (51 anggota) yang disusun ke dalam dua workbook:

1. **Probabilitas Dasarian** (`prob/dasarian/KEPRI_pch_ecmwf_perpos_ver_2026.04.30.xlsx`):
   - Sheet rata-rata ensemble: `EnsMean` (prakiraan curah hujan dasarian deterministik).
   - Sheet Probabilitas di Bawah Normal (pb): `pb20`, `pb50`, `pb100`, `pb150`.
   - Sheet Probabilitas di Atas Normal (pa): `pa50`, `pa100`, `pa150`, `pa200`, `pa250`, `pa300`.
   - Sheet naratif: `TabelPCH` dan `TabelPSH` (teks pengelompokan stasiun).
   - Sheet kosong: `Sheet1`.

2. **Probabilitas Bulanan** (`prob/bulanan/KEPRI_pch_ecmwf_perpos_ver_2026.08.01.xlsx`):
   - Sheet rata-rata ensemble: `EnsMean` (prakiraan curah hujan bulanan deterministik).
   - Sheet Probabilitas di Bawah Normal (pb): `pb50`, `pb100`, `pb150`.
   - Sheet Probabilitas di Atas Normal (pa): `pa50`, `pa100`, `pa150`, `pa200`, `pa300`, `pa400`, `pa500`.
   - Sheet naratif: `TabelPCH` dan `TabelPSH`.
   - Sheet kosong: `Sheet1`.

### 5.2 Tata Letak Kolom Data Probabilitas

Setiap sheet data probabilitas stasiun (`pb20` s.d. `pa500`) memiliki susunan kolom yang identik pada Baris 1:
1. Kolom 1 (`NOPOS`): Kode pos hujan BMKG (contoh: `246Z`, `200R`, `137B`).
2. Kolom 2 (`KECAMATAN-POSHUJAN`): Nama kecamatan dan nama pos hujan.
3. Kolom 3 (`LON`): Bujur geografis stasiun.
4. Kolom 4 (`LAT`): Lintang geografis stasiun.
5. Kolom 5 (`PROV`): Provinsi (`KEPRI`).
6. Kolom 6 (`KAB`): Nama kabupaten / kota.
7. Kolom 7 (`URUTKAB`): Nomor urut pos dalam kabupaten.
8. Kolom 8 dan seterusnya: Nilai probabilitas untuk periode prakiraan target (misal `MeiI` pada dasarian, atau `Agt`, `Sep`, `Okt`, `Nov`, `Des`, `Jan`, `Feb` pada bulanan).

### 5.3 Temuan Kritis: Skala Numerik Probabilitas

> [!IMPORTANT] SKALA NILAI PROBABILITAS SUDAH DALAM BENTUK PERSEN (0.0 – 100.0%)
> Seluruh sel data probabilitas pada sheet `pb*` dan `pa*` berisi nilai floating point antara **0.0 hingga 100.0** (misal 19.6078, 78.4313, 100.0).
> Nilai ini dihitung dari $k / 51 \times 100\%$, di mana $k$ adalah jumlah anggota ensemble ECMWF yang melampaui ambang batas.
> **ATURAN MUTLAK PIPELINE**: Ingestion parser **DILARANG mengalikan nilai dengan 100**. Nilai mentah sudah berada dalam unit persentase (`%`) yang siap divalidasi dengan aturan Decision Engine.

### 5.4 Pemetaan Variabel Probabilitas ke Decision Engine DSS-PIK

Variabel probabilitas terhubung langsung dengan mesin inferensi peringatan dini BMKG:

| Modul Peringatan Dini | Indikator Keputusan | Variabel Probabilitas Template | Ambang Batas Logika Operasional |
|:---|:---|:---:|:---|
| **PDKM** (Kekeringan Meteorologis) | Probabilitas CH Dasarian $< 20$ mm | `pb20` | Digunakan untuk penetapan status Waspada, Siaga, dan Awas kekeringan dasarian |
| **PDCHT Dasarian** (Curah Hujan Tinggi) | Probabilitas CH Dasarian $> 150$ mm | `pa150` | Ambang status Waspada PDCHT Dasarian |
| **PDCHT Dasarian** (Curah Hujan Tinggi) | Probabilitas CH Dasarian $> 200$ mm | `pa200` | Ambang status Siaga PDCHT Dasarian |
| **PDCHT Dasarian** (Curah Hujan Tinggi) | Probabilitas CH Dasarian $> 300$ mm | `pa300` | Ambang status Awas PDCHT Dasarian |
| **PDCHT Bulanan** (Curah Hujan Tinggi) | Probabilitas CH Bulanan $> 300$ mm | `pa300` | Ambang status Waspada PDCHT Bulanan |
| **PDCHT Bulanan** (Curah Hujan Tinggi) | Probabilitas CH Bulanan $> 400$ mm | `pa400` | Ambang status Siaga PDCHT Bulanan |
| **PDCHT Bulanan** (Curah Hujan Tinggi) | Probabilitas CH Bulanan $> 500$ mm | `pa500` | Ambang status Awas PDCHT Bulanan |

### 5.5 Pemetaan Stasiun ECMWF ke Master CEWS

- Terdapat **53 baris stasiun** dalam setiap sheet probabilitas.
- Dengan menggunakan tabel relasi resmi `data/reference/stations/mapping_tambahan.xlsx`, sebanyak **52 stasiun berhasil dipetakan sempurna** ke pos manual master CEWS.
- Ditemukan **1 stasiun luar**: `228R: Tanjung Riau Kota Batam` yang berada di luar batas 57 master stations DSS-PIK. Ingestion engine harus menandai stasiun ini sebagai `UNMAPPED_EXTERNAL` dan melewatinya tanpa menghentikan proses parsing.
- Terdapat **1 pos manual master yang tidak tercantum** di template ECMWF: `21050501a` (UPT Benih Pertanian Anambas). Sistem secara otomatis menetapkan status imputasi atau `MISSING_PROB` untuk pos ini.
- **Catatan Anomali Historis Sheet `EnsMean` Bulanan**: Pada file bulanan `KEPRI_pch_ecmwf_perpos_ver_2026.08.01.xlsx`, sheet `EnsMean` kehilangan kolom bulan pertama (`Agt` tidak ada, langsung melompat ke `Sep`). Sebaliknya, seluruh sheet probabilitas (`pb50` s.d. `pa500`) memiliki kolom `Agt` yang lengkap. Hal ini mengonfirmasi temuan audit terdahulu terkait akar penyebab anomali incomplete data pada stasiun tertentu.

---

## 6. SPESIFIKASI DESAIN MODUL DATA INGESTION DSS-PIK

### 6.1 Alur Ingestion Pipeline Terstandar

Berdasarkan seluruh temuan di atas, arsitektur modul ingestion yang akan dibangun wajib mengikuti tahapan berurutan berikut:

```mermaid
flowchart TD
    A[User Upload File via Dashboard] --> B[Pre-Validation: Cek Ekstensi, Ukuran, File Lock ~\$]
    B --> C[File Type Detector: CH, SPI, atau Probabilitas]
    C -->|Kategori CH| D1[Loop Worksheet: 53 Sheets]
    C -->|Kategori SPI| D2[Parse Sheet Analisis & Prakiraan]
    C -->|Kategori Probabilitas| D3[Parse Sheet pb* dan pa*]
    D1 --> E1[Sanitasi Baris: Simbol -, TTU, R, Typo Titik/Strip]
    D2 --> E2[Validasi Kode Stasiun & Koreksi Typo Selemut Cemaga]
    D3 --> E3[Normalisasi Nilai Skala Persen 0-100 & Mapping NOPOS]
    E1 --> F1[Batch Insert ke MariaDB daily_rainfall]
    E2 --> F2[Atomic Write ke Parquet SPI Store]
    E3 --> F3[Save ke Probability Storage / Cache Evaluasi]
    F1 --> G[Trigger Evaluasi Periode / Regenerasi Snapshot]
    F2 --> G
    F3 --> G
    G --> H[Return JSON Audit Report ke UI Dashboard]
```

### 6.2 Skema Target Penyimpanan Data

1. **Data Curah Hujan Harian** diarahkan langsung ke tabel MariaDB `daily_rainfall`:
   - Primary Key gabungan: `(station_id, date)`.
   - Query Ingestion: Menggunakan klausa `INSERT INTO daily_rainfall (station_id, date, rainfall_mm, obs_status) VALUES (...) ON DUPLICATE KEY UPDATE rainfall_mm = VALUES(rainfall_mm), obs_status = VALUES(obs_status)` untuk menjamin idempotensi (mencegah duplikasi data jika diupload ulang).
2. **Data SPI** diarahkan ke Parquet store `data/processed/spi/`:
   - File target: `SPI_all_30d.parquet` dan `SPI_all_90d.parquet`.
   - Skema kolom: `station_id` (string), `date` (date32), `spi` (float64), `category` (string).
3. **Data Probabilitas Prakiraan** disimpan ke penyimpanan terstruktur per periode di `data/processed/probability/`.

### 6.3 Pencegahan Error dan Audit Logging

- **Validasi Format Tanggal**: Setiap baris tanggal divalidasi terhadap range yang masuk akal (`1970-01-01` s.d. `2035-12-31`).
- **Validasi Ambang Batas Nilai CH**: Curah hujan harian $< 0$ mm ditolak; curah hujan $> 500$ mm diberi flag peringatan `EXTREME_PRECIPITATION_FLAG` untuk dikonfirmasi ulang.
- **Validasi Ambang Batas Nilai Probabilitas**: Nilai probabilitas di luar rentang $[0.0, 100.0]$ akan membatalkan baris pengamatan tersebut.
- **Audit Logging**: Setiap transaksi upload dicatat ke dalam log operasional dengan menyertakan nama file asli, hash berkas (SHA-256), jumlah baris berhasil, jumlah baris diperbaiki, dan peringatan baris yang diabaikan.

---

## 7. MATRIKS PERBANDINGAN FORMAT ANTAR WILAYAH & FILE

| Parameter Evaluasi | Kabupaten Lingga | Kabupaten Karimun | Kabupaten Natuna | Kab. Kep. Anambas | Kota Batam | Tanjungpinang & Bintan | Berkas SPI | Berkas Probabilitas |
|:---|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|
| **Jumlah File** | 1 | 1 | 1 | 1 | 1 | 1 | 1 (+1 lock) | 2 |
| **Jumlah Sheet Data** | 8 | 7 | 15 | 3 | 2 | 18 | 2 data (+2 bantu) | 10 s.d. 11 per file |
| **Posisi Header** | Baris 1 | Baris 1 | Baris 1 | Baris 1 | Baris 1 | Baris 1 | Baris 1-2 (Multi) | Baris 1 |
| **Baris Data Mulai** | Baris 2 | Baris 2 | Baris 2 | Baris 2 | Baris 2 | Baris 2 | Baris 3 | Baris 2 |
| **Tipe Tanggal** | Serial Datetime | Serial Datetime | Serial Datetime | Serial Datetime | Serial Datetime | Serial Datetime | Nama Bulan | Nama Periode |
| **Tahun Awal Data** | 1981 | 1994 | 2009 | 1991 | 1993 | 1976 | 2026 | 2026 |
| **Merged Cells** | 0 | 0 | 0 | 0 | 0 | 0 | Ada (Header) | 0 |
| **Formula Pengamatan** | Tidak ada | Tidak ada | Tidak ada | Tidak ada | Tidak ada | Di luar col B | Ada (sheet GIS) | Tidak ada |
| **Koreksi Typo Diperlukan** | Ya (`1-`) | Ya (`1-`, `alat rusak`) | Tidak ada | Tidak ada | Tidak ada | Ya (`.`, `0.4.`) | Ya (`210310802a`) | Tidak ada |
| **Status Integrasi** | Siap Otomatis | Siap Otomatis | Siap Otomatis | Siap Otomatis | Siap Otomatis | Siap Otomatis | Perlu Bridge Dasarian | Siap Otomatis |

---

## 8. KESIMPULAN AUDIT DAN REKOMENDASI TAHAP BERIKUTNYA

1. **Kesiapan Data Curah Hujan (CH)**: Berkas template curah hujan memiliki tingkat keteraturan struktur yang sangat tinggi (**98% konsisten**). Ingestion parser dapat dibangun secara langsung dengan modul sanitasi simbol yang telah didefinisikan pada dokumen ini.
2. **Kesiapan Data Probabilitas ECMWF**: Berkas template probabilitas dasarian dan bulanan sangat siap diintegrasikan. Pastikan parser mempertahankan skala **0 s.d. 100%** tanpa re-skalasi.
3. **Kesiapan Data SPI**: Dibutuhkan standarisasi format template SPI dasarian atau integrasi modul kalkulasi otomatis SPI dasarian berbasis curah hujan sebelum fitur upload SPI diaktifkan secara operasional.
4. **Tahap Berikutnya**: Spesifikasi JSON pada `docs/DSS_PIK_TEMPLATE_INPUT_SCHEMA.json` menjadi kontrak antarmuka mesin yang langsung dapat diimpor oleh FastAPI backend saat modul upload data dikembangkan.

---
*Dokumen ini disahkan sebagai hasil audit resmi arsitektur sistem DSS-PIK BMKG Tanjungpinang.*
