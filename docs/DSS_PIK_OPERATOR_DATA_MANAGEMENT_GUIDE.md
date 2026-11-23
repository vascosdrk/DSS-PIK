# PANDUAN PENGELOLAAN DATA OPERASIONAL DSS-PIK
# OPERATIONAL DATA MANAGEMENT & INTEGRITY GUIDE
## Decision Support System Peringatan Dini Iklim (DSS-PIK)
**Stasiun Meteorologi Kelas II Raja Haji Fisabilillah Tanjungpinang — BMKG Kepulauan Riau**  
**Versi Dokumen:** 1.2 (Rilis Resmi Final Refinement 31 Oktober 2026)  
**Klasifikasi:** Dokumen Teknis & Prosedur Operasional Standar (SOP)

---

## DAFTAR ISI
1. [Prinsip Dasar Arsitektur & Canonical Storage](#1-prinsip-dasar-arsitektur--canonical-storage)
2. [Pemisahan Temporal: Data Observasi vs Data Prakiraan](#2-pemisahan-temporal-data-observasi-vs-data-prakiraan)
3. [Dinamika Periode Dasarian (+1 Periode Prakiraan Antisipatif)](#3-dinamika-periode-dasarian-1-periode-prakiraan-antisipatif)
4. [Monitoring Status Data Terkini (Canonical Storage Status Card)](#4-monitoring-status-data-terkini-canonical-storage-status-card)
5. [Validasi Metadata Stasiun Otoritatif & Resolusi Tabrakan Pos](#5-validasi-metadata-stasiun-otoritatif--resolusi-tabrakan-pos)
6. [Prosedur Input / Pembaruan File Operasional & Idempotensi Diff](#6-prosedur-input--pembaruan-file-operasional--idempotensi-diff)
7. [Ruang Kerja Manajemen Data Operasional (6 KPI Card & 4 Tab)](#7-ruang-kerja-manajemen-data-operasional-6-kpi-card--4-tab)
8. [Manajemen Vintage Prakiraan (Forecast Vintage Management)](#8-manajemen-vintage-prakiraan-forecast-vintage-management)
9. [Manajemen Batch Ingestion & Pembatalan Aman (Rollback)](#9-manajemen-batch-ingestion--pembatalan-aman-rollback)
10. [Koreksi & Pembatalan Data Tunggal (Record Correction & Voiding CH, SPI, Probabilitas)](#10-koreksi--pembatalan-data-tunggal-record-correction--voiding-ch-spi-probabilitas)
11. [Aturan Hari Tanpa Hujan (HTH) & Integritas Evaluasi PDKM](#11-aturan-hari-tanpa-hujan-hth--integritas-evaluasi-pdkm)
12. [Penanganan Masalah (Troubleshooting & FAQ)](#12-penanganan-masalah-troubleshooting--faq)

---

## 1. PRINSIP DASAR ARSITEKTUR & CANONICAL STORAGE

Sistem DSS-PIK mengadopsi prinsip **Canonical Multi-Storage Architecture** yang memisahkan dan mensinkronisasikan dua media penyimpanan utama:
1. **Basis Data Relasional (MariaDB `cews_db`)**:
   - `cews_rainfall_daily`: Menyimpan rekaman deret waktu curah hujan harian (baseline 286.085 baris), simbol BMKG asli, status observasi, dan riwayat koreksi.
   - `stations`: Metadata 57 stasiun/pos hujan resmi (52 Pos Manual + 5 Pos ARG/AWS).
   - `cews_forecast_snapshot`: Penyimpanan terisolasi seluruh vintage prakiraan model numerik ECMWF skala dasarian dan bulanan.
   - `cews_ingestion_history`: Audit trail transaksi unggahan berkas, cakupan periode, verifikasi sidik jari, dan rincian item batch.
   - `cews_rainfall_correction_log`: Buku besar (*ledger*) permanen yang mencatat seluruh koreksi dan pembatalan (*void*) data individual beserta alasan operasional dan identitas petugas.
2. **Penyimpanan Berkas Kolom Berkinerja Tinggi (Apache Parquet)**:
   - `data/processed/SPI_daily_30d.parquet` & `SPI_daily_90d.parquet`: Deret waktu SPI harian seluruh stasiun manual.
   - `data/processed/SPI_dasarian_30d.parquet` & `SPI_dasarian_90d.parquet`: Deret waktu SPI dasarian sebagai indikator otoritatif PDKM.
   - `data/processed/SPI_monthly.parquet`: Deret waktu SPI skala bulanan.
   - `data/processed/rainfall_daily.parquet`: Salinan analitik cepat untuk visualisasi grafik curah hujan.

> [!IMPORTANT]
> **Kebijakan 5 Pos ARG (Strictly NULL SPI):**
> 5 Pos Automatic Rain Gauge (ARG Tanjung Pinang, ARG Bintan, ARG Karimun, ARG Batam, ARG Natuna) **tidak memiliki deret historis 30 tahun**, sehingga nilai SPI harus selalu `NULL`/Kosong. Sistem melarang keras interpolasi buatan yang dapat memicu *False Green* pada evaluasi kekeringan.

---

## 2. PEMISAHAN TEMPORAL: DATA OBSERVASI VS DATA PRAKIRAAN

Dalam operasional BMKG, terjadi perbedaan siklus waktu antara data observasi dan data prakiraan:
- **Data Observasi (CH Harian & SPI)**: Merupakan data rekaman kejadian nyata masa lalu hingga hari terakhir observasi yang telah lengkap (*completed period*). Data observasi **mengendalikan periode aktif dasarian** pada dashboard.
- **Data Prakiraan (Probabilitas ECMWF)**: Merupakan proyeksi ke depan (*forward-looking*) yang mencakup 3–6 dasarian atau 1–3 bulan ke depan.

### Aturan Ketat Pemisahan Waktu:
1. Mengunggah file probabilitas prakiraan dengan tanggal masa depan (misal Dasarian I s/d III Oktober 2026 atau Januari 2027) **TIDAK AKAN** memajukan periode aktif observasi dashboard secara prematur.
2. Dashboard tetap berlabuh pada periode observasi yang lengkap (misal Dasarian II September 2026) hingga petugas mengunggah data curah hujan observasi periode berikutnya.
3. Decision Engine PDKM dan PDCHT membaca data masa lalu dari observasi dan data masa depan dari tabel vintage prakiraan secara harmonis tanpa *lookahead bias*.

---

## 3. DINAMIKA PERIODE DASARIAN (+1 PERIODE PRAKIRAAN ANTISIPATIF)

Dalam operasional peringatan dini iklim BMKG, petugas prakiraan memerlukan visibilitas terhadap dasarian yang akan datang sebelum periode tersebut dimulai:

1. **Jendela 10 Dasarian + 1 Periode Prakiraan**:
   - Selector periode dashboard menyajikan 10 dasarian historis observasi ditambah **1 periode prakiraan berikutnya (+1)**.
   - Sebagai contoh, ketika tanggal kalender aktif adalah **31 Oktober 2026 (Dasarian III Oktober)**, sistem secara dinamis menambahkan opsi **Dasarian I November 2026** bertanda `🔮 [Prakiraan]`.
   - Periode default aktif tetap **Dasarian III Oktober 2026** (periode observasi aktual).

2. **Banner Peringatan Iklim Antisipatif (Lookahead Protection)**:
   - Ketika operator memilih periode prakiraan masa depan (+1), sistem secara otomatis menampilkan spanduk khusus berwarna ungu:
     > **PERIODE PRAKIRAAN — BELUM MENJADI PERIODE OBSERVASI:**  
     > *Dasarian ini belum berakhir dan data observasi curah hujan belum lengkap. Menampilkan indikator probabilitas prakiraan iklim tanpa menghasilkan peringatan observasi definitif.*
   - Hal ini mencegah terjadinya *lookahead bias* dan melarang sistem menerbitkan status *False Green* ("AMAN palsu") saat data observasi belum lengkap.

---

## 4. MONITORING STATUS DATA TERKINI (CANONICAL STORAGE STATUS CARD)

Komponen `CanonicalStorageStatusCard` menyajikan dashboard status kesehatan penyimpanan secara menyeluruh dengan tata letak modular:

### Struktur Visual:
1. **Header Panel**:
   - Indikator **LIVE** berdenyut (*pulsing green dot*).
   - Waktu pemeriksaan terakhir dalam format WIB.
   - Tombol **"Segarkan"** untuk memicu inspeksi langsung ke MariaDB dan Parquet.
2. **Baris 1: Curah Hujan Harian (MariaDB `cews_rainfall_daily`)**:
   - Tanggal terakhir observasi dan dasarian terakhir.
   - Pos melapor vs total pos (misal: `23 / 57 pos (40.4%)`).
   - Progress bar cakupan pos (hijau $\ge 80\%$, kuning $50-79\%$, merah $< 50\%$).
   - Daftar interaktif pos yang belum melapor.
3. **Baris 2: SPI Multi-Skala (Apache Parquet 5 Skala)**:
   - 5 Kartu Responsif: **Harian 30D**, **Harian 90D**, **Dasarian 30D**, **Dasarian 90D**, dan **Bulanan**.
   - Tanggal ref/periode evaluasi dan jumlah pos terhitung (52 Pos Manual).
   - Penanda Integritas: *5 Pos ARG dikecualikan strictly NULL (non-SPI)*.
4. **Baris 3: Probabilitas Prakiraan ECMWF (Snapshot Store)**:
   - Kartu **Dasarian ECMWF**: Periode target (misal `2026-11-das1`), tanggal rilis/issue (`2026-10-19`), 52 pos terpetakan, 11 indikator probabilitas.
   - Kartu **Bulanan ECMWF**: Bulan target, tanggal rilis, cakupan pos, dan indikator.

---

## 5. VALIDASI METADATA STASIUN OTORITATIF & RESOLUSI TABRAKAN POS

Sistem DSS-PIK menetapkan `data/reference/stations/station_metadata.parquet` dan tabel MariaDB `stations` sebagai **satu-satunya sumber kebenaran (*single source of truth*)** dengan tepat **57 stasiun** (52 Pos Manual + 5 Pos ARG).

### Kebijakan Validasi Metadata Ketat:
1. **Larangan Fuzzy Matching Longgar**:
   - Pencocokan nama stasiun dilarang menggunakan pencarian substring longgar yang dapat memicu salah petik (misal "Tanjung" mencocokkan "Tanjung Riau").
2. **Isolasi Pos Eksternal**:
   - Baris dalam file input yang bukan merupakan bagian dari 57 stasiun master (contoh: baris 50 `Tanjung Riau Kota Batam` ber-nopos `228R`) **diisolasi secara aman** ke dalam kategori `unmapped_external_stations`.
   - Pos eksternal ini tidak disisipkan ke master stations, sehingga integritas 57 stasiun tetap terlindungi 100%.
3. **Resolusi Tabrakan Nopos (Collision Disambiguation)**:
   - Teridentifikasi tabrakan nomor pos `228D` antara pos `Duara` (Lingga) dan `UPT Benih Pertanian` (Anambas).
   - Modul pemetaan memetakan `Duara` ke `21040501A` dan `UPT Benih Pertanian` ke `21050501A` (`Bukit Padi`), menghasilkan 0 tabrakan dan mencocokkan seluruh 52 pos manual secara sempurna.
4. **Ringkasan Validasi Pemetaan pada Pratinjau**:
   - Modal ingestion menampilkan kotak validasi:
     - Total baris file (misal 53).
     - Pos master cocok: `52 Pos (100%)`.
     - Pos eksternal diisolasi: `1 Pos` (Tanjung Riau).
     - Duplikat / Tabrakan: `0 Pos`.
     - Pos master hilang: `0 Pos`.

---

## 6. PROSEDUR INPUT / PEMBARUAN FILE OPERASIONAL & IDEMPOTENSI DIFF

### Idempotensi Mutlak & Toleransi Desimal:
Ketika file yang sama diunggah ulang ke sistem:
1. Sistem melakukan perbandingan nilai lama dan nilai baru dengan toleransi floating point:
   $$|\text{Prob}_{\text{baru}} - \text{Prob}_{\text{lama}}| < 10^{-4}$$
2. Jika selisih berada di bawah ambang batas, rekor diklasifikasikan sebagai `IDENTICAL` (Identik).
3. Hasil re-upload file probabilitas yang telah tersimpan adalah **NEW = 0, UPDATED = 0, IDENTICAL = 572, REJECTED = 0**.
4. Sistem tidak melakukan penulisan ulang yang redundan ke database saat seluruh rekor identik, dan histori batch mencatat `new_records: 0, identical_records: 572` secara akurat.

### Alur Langkah Ingestion:
1. **Langkah 1**: Buka modul dari tombol navigasi atau bilah aksi kontekstual di halaman data.
2. **Langkah 2**: Pilih tipe berkas atau gunakan *Deteksi Otomatis*.
3. **Langkah 3**: Unggah berkas Excel / Parquet.
4. **Langkah 4**: Evaluasi ringkasan pratinjau, validasi metadata stasiun, dan diff.
5. **Langkah 5**: Centang dasarian target dan berikan izin eksplisit jika terdapat data `UPDATED`.
6. **Langkah 6**: Klik *Commit* untuk mengeksekusi penyimpanan atomik dan pencatatan audit log.

---

## 7. RUANG KERJA MANAJEMEN DATA OPERASIONAL (6 KPI CARD & 4 TAB)

Pusat Manajemen Data Operasional (`OperationalDataManager`) dapat diakses melalui menu **Pusat Data -> Tab 4: Manajemen Data Operasional**.

### Bagian A: 6 KPI Cards Real-Time:
- **Total Batch**: Total seluruh sesi ingestion yang tercatat di database.
- **Batch Berhasil**: Jumlah batch yang berstatus `COMPLETED`.
- **Batch Dibatalkan**: Jumlah batch yang di-rollback oleh operator.
- **Record Baru**: Akumulasi total data observasi/prakiraan baru.
- **Record Update**: Akumulasi data historis yang telah diperbarui secara berizin.
- **Record Ditolak**: Akumulasi data anomali atau duplikat yang ditolak.

### Bagian B: 4 Tab Navigasi Terstruktur:
1. **1. Ringkasan Penyimpanan**: Menampilkan kartu `CanonicalStorageStatusCard` live.
2. **2. Riwayat Batch Ingestion**:
   - Bilah pencarian instan (Batch ID, nama file, operator).
   - Filter tipe data dan status batch.
   - Tabel riwayat dengan pagination.
   - Tombol **Detail** (membuka modal audit trail, file SHA-256 hash, breakdown station).
   - Tombol **Rollback** bertarget untuk membatalkan batch aktif.
3. **3. Koreksi & Pembatalan Rekaman**:
   - **Sub-Form 1: Koreksi Curah Hujan Harian**: Koreksi nilai salah input per stasiun dan tanggal dengan logging ke `cews_rainfall_correction_log`.
   - **Sub-Form 2: Pembatalan (Void) Curah Hujan**: Menetapkan rekor observasi menjadi `VOID` tanpa menghapus baris fisik.
   - **Sub-Form 3: Pembatalan (Void) Rekor SPI**: Menetapkan nilai SPI menjadi `NaN` pada file Parquet terisolasi per timescale (30D vs 90D independen).
   - **Sub-Form 4: Pembatalan (Void) Snapshot Probabilitas**: Menghapus rekor probabilitas model per tanggal issue dan periode target.
4. **4. Vintage Prakiraan ECMWF**: Menjelajahi seluruh rilisan model ECMWF yang tersimpan di `cews_forecast_snapshot`.

> [!WARNING]
> Jika seluruh isi berkas yang diunggah berstatus `UPDATED` (misal berkas revisi total) dan operator **TIDAK** mencentang persetujuan pembaruan, sistem akan membatalkan proses dengan pesan galat:
> *"Pembaruan dibatalkan: Seluruh data berstatus UPDATED namun persetujuan pembaruan tidak diberikan."*

---

## 7. MANAJEMEN VINTAGE PRAKIRAAN (FORECAST VINTAGE MANAGEMENT)

Dalam prakiraan ensemble iklim, BMKG menerima pembaruan model secara berkala (misal prakiraan Dasarian I Oktober dirilis tanggal 25 September, lalu diperbarui lagi pada 30 September).

### Mengapa Vintage Diisolasi?
Jika sistem langsung menimpa data lama, operator kehilangan jejak historis evaluasi kinerja model (*forecast track record*). Oleh karena itu, DSS-PIK mengisolasi setiap rilis model pada tabel `cews_forecast_snapshot` dengan composite key:
`(station_id, target_year, target_month, target_dasarian, issue_date, forecast_parameter)`

### Cara Menjelajahi Vintage:
1. Buka tab **"Manajemen Data Operasional"** -> Bagian **"Penelusuran Vintage Prakiraan ECMWF"**.
2. Pilih filter:
   - **Tipe Horizon**: Dasarian atau Bulanan.
   - **Tahun Target**: Pilih tahun (misal 2026 atau 2027).
   - **Bulan Target**: Pilih bulan evaluasi (misal September, Oktober).
3. Tabel akan menampilkan seluruh rilis model yang tersedia, tanggal terbit (*issue date*), jumlah stasiun yang tercakup, serta status apakah vintage tersebut merupakan **VINTAGE AKTIF** (*Latest Applicable Vintage*).

### Kebijakan Seleksi Vintage oleh Decision Engine:
Ketika mengevaluasi dasarian target tertentu, Decision Engine memilih vintage yang memenuhi syarat:
$$\text{issue\_date} \le \text{evaluation\_cutoff\_date}$$
dengan memilih $\max(\text{issue\_date})$ yang tersedia. Hal ini memastikan evaluasi dilakukan secara adil sesuai ketersediaan data pada saat dasarian tersebut dievaluasi.

---

## 8. MANAJEMEN BATCH INGESTION & PEMBATALAN AMAN (ROLLBACK)

Setiap kali operator melakukan *commit* data melalui modal, sistem mencatat transaksi sebagai sebuah **Batch Ingestion**.

### Melihat Riwayat Batch:
Pada tab **"Manajemen Data Operasional"**, operator dapat melihat tabel riwayat batch yang memuat:
- **Batch ID / Token**: Pengenal unik transaksi.
- **Waktu Unggah**: Tanggal dan jam presisi eksekusi.
- **Nama Berkas & Tipe Data**: Kategori data yang diproses.
- **Jumlah Rekaman**: Baru, Identik, Diperbarui, Ditolak.
- **Petugas**: Nama atau sesi operator yang melakukan commit.
- **Status Batch**: `COMMITTED` atau `ROLLED_BACK`.

### Prosedur Pembatalan Batch (Rollback):
Jika operator menyadari telah mengunggah berkas yang salah:
1. Klik tombol **"Batalkan (Rollback)"** pada baris batch yang bersangkutan.
2. Jendela konfirmasi akan muncul menampilkan ringkasan data yang akan dipulihkan.
3. **Wajib Memasukkan Alasan Pembatalan**: Operator harus mengetikkan justifikasi operasional (minimal 5 karakter, misal *"Salah mengambil berkas versi draft"*).
4. Klik **"Konfirmasi Pembatalan"**.
5. Sistem akan:
   - Mengembalikan nilai data lama di MariaDB atau menghapus baris baru yang disisipkan oleh batch tersebut.
   - Memulihkan file Parquet dari file cadangan (*backup reference*).
   - Mengubah status batch menjadi `ROLLED_BACK` pada audit trail.
   - Mencatat waktu dan alasan pembatalan secara permanen.

---

## 9. KOREKSI & PEMBATALAN DATA TUNGGAL (RECORD CORRECTION & VOIDING)

Selain pembatalan satu batch utuh, operator lapangan sering kali perlu mengoreksi satu nilai curah hujan harian tertentu (misal pos hujan mencatat salah ketik dari pos pengamat, atau alat penakar hujan sempat tersumbat).

Fitur ini tersedia pada tab **"Manajemen Data Operasional"** bagian **"Koreksi & Pembatalan Data Curah Hujan Harian"**.

### Prosedur Koreksi Data (Correction):
1. Pilih **Stasiun / Pos Hujan**.
2. Masukkan **Tanggal Observasi**.
3. Masukkan **Curah Hujan Baru (mm)** (misal `12.5`).
4. Masukkan **Status Observasi**: `CORRECTED` (atau `OBSERVED_VALID`).
5. Masukkan **Alasan Koreksi Wajib** (misal *"Koreksi kesalahan entri manual dari formulir pos"*).
6. Masukkan **Nama Petugas**.
7. Klik tombol **"Simpan Koreksi Data"**.
8. Sistem akan memperbarui tabel `cews_rainfall_daily` dan mencatat entri baru ke `cews_rainfall_correction_log` lengkap dengan nilai lama, nilai baru, timestamp, dan identitas petugas.

### Prosedur Pembatalan Catatan (Voiding):
Jika sebuah data observasi terbukti tidak valid atau fiktif dan harus ditarik dari perhitungan:
1. Pilih stasiun dan tanggal observasi.
2. Masukkan alasan pembatalan (misal *"Alat ombrometer bocor parah, data tidak dapat dipertanggungjawabkan"*).
3. Klik tombol **"Batalkan Catatan (Void Record)"**.
4. Sistem **TIDAK MENGHAPUS BARIS FISIK** (menjaga integritas audit), melainkan:
   - Mengubah `rainfall_mm = NULL`.
   - Mengubah `obs_status = 'VOID'`.
   - Mengubah `original_symbol = 'VOID'`.
   - Mencatat aksi pembatalan ke dalam buku besar `cews_rainfall_correction_log`.

---

## 10. ATURAN HARI TANPA HUJAN (HTH) & INTEGRITAS EVALUASI PDKM

### Definisi Baku HTH BMKG:
Hari Tanpa Hujan (HTH) dihitung sebagai jumlah hari berturut-turut di mana curah hujan harian terukur $< 1.0\text{ mm}$ (termasuk hari cerah $0.0\text{ mm}$ dan hari jejak hujan `TTU`).

### Penanganan Simbol Khusus BMKG:
| Simbol BMKG | Kode Baku | Nilai Curah Hujan | Dampak terhadap Deret HTH |
| :--- | :--- | :--- | :--- |
| **0** / **0.0** | `OBSERVED_ZERO` | `0.0 mm` | Menambah streak HTH (+1 hari). |
| **-** / **TTU** | `TTU` | `0.0 mm` | Jejak hujan $< 0.5\text{ mm}$, menambah streak HTH (+1 hari). |
| **$\ge 1.0$** | `OBSERVED_VALID` | $\ge 1.0\text{ mm}$ | **Hujan terukur**: Mereset streak HTH menjadi **0 hari**. |
| **8888** | `DAMAGED` | `NULL` | **Alat Rusak**: Tidak mereset ke 0, status `hth_uncertain = True`. |
| **9999** | `MISSING` | `NULL` | **Data Hilang**: Tidak mereset ke 0, status `hth_uncertain = True`. |
| **.** | `AMBIGUOUS` | `NULL` | **Titik Ambigu**: Tidak mereset ke 0, status `hth_uncertain = True`. |

### Pencegahan False Green ("Aman Palsu") pada PDKM:
> [!CAUTION]
> **Prinsip Keselamatan Peringatan Dini:**
> Jika sebuah pos hujan memiliki deret HTH misal baru tercatat 5 hari kering, namun pada 3 hari berikutnya data berstatus `DAMAGED` atau `MISSING`:
> - Sistem **TIDAK BOLEH** berasumsi terjadi hujan (tidak boleh mereset counter ke 0).
> - Sistem **TIDAK BOLEH** menetapkan status **"AMAN"** berwarna hijau.
> - Sistem menandai `hth_uncertain = True`.
> - Decision Engine PDKM mengklasifikasikan indikator HTH sebagai **"UNCERTAIN" / Tidak Lengkap**, dan merekomendasikan operator untuk melakukan verifikasi manual ke pengamat pos sebelum menerbitkan produk resmi.

---

## 11. PENANGANAN MASALAH (TROUBLESHOOTING & FAQ)

### Q1: Mengapa Pratinjau Menampilkan Nilai "Identik" yang Sangat Banyak?
**Penyebab:** Operator mengunggah kembali file yang sebelumnya sudah pernah di-commit ke sistem.  
**Tindakan:** Ini adalah perilaku normal. Sistem secara otomatis mendeteksi data yang sudah ada dan melewatinya (*skip*) sehingga tidak terjadi duplikasi rekaman.

### Q2: Mengapa Tombol "Simpan Data ke Sistem" Berwarna Abu-Abu (Disabled)?
**Penyebab:** 
1. Tidak ada rekaman `NEW` dan tidak ada rekaman `UPDATED` yang dipilih.
2. Seluruh data berstatus `UPDATED`, namun kotak izin pembaruan belum dicentang.
3. Belum ada dasarian target yang dicentang pada daftar periode.  
**Tindakan:** Centang minimal satu periode dasarian target dan centang persetujuan pembaruan jika terdapat data yang diperbarui.

### Q3: Mengapa Indikator SPI untuk Pos ARG Bernilai Kosong / Strip?
**Penyebab:** Pos ARG (Tanjung Pinang, Bintan, Batam, Karimun, Natuna) beroperasi di bawah 30 tahun.  
**Tindakan:** Sesuai standar klimatologi WMO/BMKG, perhitungan SPI memerlukan data historis panjang 30 tahun. Menampilkan nilai kosong adalah perilaku yang benar secara metodologis.

### Q4: Apa yang Harus Dilakukan Jika Terjadi Gangguan Koneksi Saat Melakukan Commit?
**Penyebab:** Jaringan LAN atau sesi browser terputus.  
**Tindakan:** Karena backend menerapkan transaksi basis data atomik (`BEGIN ... COMMIT`), data di basis data akan otomatis di-*rollback* dan tidak akan berada dalam kondisi korup setengah jalan. Periksa status data pada panel **Live Canonical Status**, dan ulangi unggahan berkas.

---

## 12. PANDUAN PENGELOLAAN PRAKIRAAN MULTI-VINTAGE ECMWF & ATURAN CUTOFF EVALUASI

### Konsep Multi-Vintage Kumulatif
Dalam operasional BMKG, prakiraan ECMWF untuk periode target yang sama (contoh: Dasarian I November 2026) dapat diterbitkan berulang kali dengan tanggal rilis (*issue date*) yang berbeda seiring mendekatnya waktu kejadian (misal rilis 9 Okt, 19 Okt, dan 30 Okt).
- **Prinsip Non-Destruktif:** DSS-PIK menyimpan setiap rilis secara independen dalam `cews_forecast_snapshot` dengan composite key `(station_id, forecast_resolution, target_year, target_month, target_dasarian, issue_date, forecast_parameter)` tanpa menimpa (*overwrite*) atau menghapus vintage rilis sebelumnya. Untuk prakiraan `BULANAN`, nilai `target_dasarian` dinormalisasi menjadi sentinel non-NULL `0` agar indeks unik multi-kolom MariaDB menegakkan keunikan mutlak.
- **Status Vintage:**
  - `AKTIF (Terbaru)`: Otomatis digunakan oleh Decision Engine PDKM/PDCHT dan ditampilkan pada tabel/peta secara default (dengan tetap mematuhi aturan cutoff evaluasi).
  - `HISTORIS`: Tetap tersimpan di database dan dapat diinspeksi oleh forecaster melalui dropdown vintage pada *Tabel Data Probabilitas*.

### Aturan Cutoff Evaluasi (`select_eligible_vintage`) — Bebas Lookahead Bias
Ketika Decision Engine mengevaluasi suatu periode dengan batas tanggal evaluasi (`evaluation_cutoff_date`), fungsi `select_eligible_vintage()` menerapkan aturan:
$$\text{active\_issue\_date} = \max\{\text{issue\_date} \mid \text{issue\_date} \le \text{evaluation\_cutoff\_date}\}$$
- **Simulasi Contoh (Dasarian I November 2026 dengan rilis `2026-10-09`, `2026-10-19`, dan `2026-10-30`):**
  - Jika `cutoff = 2026-10-15` -> memilih vintage `2026-10-09`.
  - Jika `cutoff = 2026-10-25` -> memilih vintage `2026-10-19`.
  - Jika `cutoff = 2026-10-31` -> memilih vintage `2026-10-30`.
  - Jika `cutoff = 2026-10-01` (sebelum rilis pertama terbit) -> mengembalikan `None` (tidak ada bocoran data masa depan).

### Validasi Konflik Tanggal Rilis (Issue Date Conflict Rejection)
Apabila berkas Excel yang diunggah memiliki ketidakcocokan antara tanggal rilis di nama berkas (misal `ver_2026.10.19.xlsx`) dan tanggal rilis di sel header internal lembar kerja (misal `2026-10-09`), parser secara otomatis **menolak berkas tersebut pada tahap pratinjau** dengan pesan galat eksplisit untuk mencegah salah label vintage.

### Pembatasan Parameter Operasional
Untuk efisiensi penyimpanan dan integritas pemodelan, sistem membatasi parameter yang diekstrak dari file Excel hanya pada parameter yang digunakan oleh Decision Engine PDKM & PDCHT:
- **Prakiraan Dasarian:** HANYA 4 parameter operasional:
  - `pb20` : Probabilitas Curah Hujan Dasarian $< 20\text{ mm}$ (Pemicu PDKM Kekeringan)
  - `pa150`: Probabilitas Curah Hujan Dasarian $> 150\text{ mm}$ (Pemicu PDCHT Waspada)
  - `pa200`: Probabilitas Curah Hujan Dasarian $> 200\text{ mm}$ (Pemicu PDCHT Siaga)
  - `pa300`: Probabilitas Curah Hujan Dasarian $> 300\text{ mm}$ (Pemicu PDCHT Awas)
  - *Ukuran batch deterministik per dasarian target: 52 pos manual x 4 parameter = 208 baris.*
- **Prakiraan Bulanan:** HANYA 3 parameter operasional:
  - `pa300`: Probabilitas Curah Hujan Bulanan $> 300\text{ mm}$
  - `pa400`: Probabilitas Curah Hujan Bulanan $> 400\text{ mm}$
  - `pa500`: Probabilitas Curah Hujan Bulanan $> 500\text{ mm}$
  - *Ukuran batch deterministik per bulan target: 52 pos manual x 3 parameter = 156 baris.*

---

## 13. ARSITEKTUR NAVIGASI TERKONSOLIDASI & KONSISTENSI 57 STASIUN MASTER

### Konsistensi 57 Stasiun Master (52 Manual + 5 ARG)
Seluruh halaman tabel di Pusat Data (`Data Curah Hujan`, `Data SPI`, dan `Data Probabilitas`) menampilkan secara konsisten **57 Stasiun Master Otoritatif** (`52 Pos Manual + 5 Pos ARG`). Pos eksternal non-master dari file mentah (seperti `Tanjung Riau Kota Batam` / `21710502A`) diisolasi dari tampilan matriks utama agar jumlah stasiun selalu seragam dengan Peta Peringatan Dini dan Decision Engine.

### Navigasi Kontekstual Bebas Redundansi
1. **Header Pusat Data (`DataCenter`)**: Menyediakan tombol **`Unduh Semua Dataset`** untuk mengunduh bundel lengkap lintas dataset.
2. **Halaman Data Curah Hujan (`DailyRainfallTable`)**:
   - **`Input / Pembaruan CH`**: Membuka modal ingestion yang langsung terkunci pada kategori `CH_HARIAN`.
   - **`Koreksi & Kelola CH`**: Membuka `Manajemen Data Operasional -> Tab 3` dengan filter otomatis `Curah Hujan Harian`.
   - **`Ekspor Data CH`**: Mengekspor data curah hujan sesuai filter periode/kabupaten aktif.
3. **Halaman Data SPI (`SpiDataTable`)**:
   - **`Input / Pembaruan SPI`**: Membuka modal ingestion kategori `SPI`.
   - **`Kelola / Pembatalan SPI`**: Membuka `Manajemen Data Operasional -> Tab 3` dengan filter otomatis `SPI Parquet`.
   - **`Ekspor Data SPI`**: Mengekspor tabel matriks SPI aktif.
4. **Halaman Data Probabilitas (`ProbabilityDataTable`)**:
   - **`Input / Pembaruan Probabilitas`**: Membuka modal ingestion kategori `PROB_DASARIAN` / `PROB_BULANAN`.
   - **`Pembatalan / Void Probabilitas`**: Membuka `Manajemen Data Operasional -> Tab 3` dengan filter otomatis `Probabilitas ECMWF`.
   - **`Kelola Vintage ECMWF`**: Membuka `Manajemen Data Operasional -> Tab 4 (Vintage Prakiraan ECMWF)`.
   - **`Ekspor Data Probabilitas`**: Mengekspor matriks probabilitas pada periode dan vintage yang sedang dipilih.
5. **Modal Ingestion Ringkas (`DataIngestionModal`)**:
   - Menampilkan **1-Line Compact Storage Summary Bar** di bagian atas beserta tombol pintas **`Detail Penyimpanan ->`** (menuju Tab 1) dan **`Riwayat Batch Lengkap`** (menuju Tab 2), menjaga agar area unggah berkas tetap proporsional di semua ukuran layar.

---

## 14. PANDUAN INGESTION WORKBOOK MAKRO BINTAN (.XLSM) & FILTER PRATINJAU PERIODE

### Pengenalan Workbook Makro Bintan (`Entry Data Pos Hujan Bintan.xlsm`)
Kabupaten Bintan mengoperasikan berkas pencatatan curah hujan harian berbasis makro Excel dengan karakteristik unik:
- **Ekstensi & Lembar Utama:** Berkas memiliki ekstensi `.xlsm` dengan lembar data operasional bernama `Data_Pos_Hujan`.
- **Struktur Kolom Horisontal (Wide Format):**
  - Baris 2 berisi header nama pos/stasiun pada Kolom C hingga T (18 pos hujan).
  - Kolom B berisi tanggal kalender observasi (`YYYY-MM-DD`).
  - Kolom C–T menyimpan angka curah hujan harian (mm) atau simbol BMKG (`-`, `TTU`, `X`, `R`).
- **Penanganan Baris Template Kosong (Trailing Blank Rows):**
  - Berkas makro ini memuat template tanggal kosong hingga akhir tahun kalender (misal 31 Desember 2026 atau 2027).
  - Parser otomatis memotong (*early stop*) baris-baris kosong tak terisi, sehingga hanya baris yang memuat data observasi valid yang dianalisis dan diajukan ke staging session.
- **Pemetaan Otoritatif 18 Pos Hujan Bintan:**
  | Kolom | Header di Sheet | ID Stasiun Otoritatif | Nama Stasiun Otoritatif |
  |:---|:---|:---|:---|
  | Col C | Pos Hujan Toapaya | `21010301A` | Pos Hujan Toapaya |
  | Col D | Pos Hujan Gunung Kijang | `21010401A` | Pos Hujan Gn. Kijang |
  | Col E | Pos Hujan Teluk Sebong | `21010601A` | Pos Hujan Teluk Sebong |
  | Col F | Pos Hujan Teluk Bintan | `21010701A` | Pos Hujan Teluk Bintan |
  | Col G | Pos Hujan Mantang | `21010901A` | Pos Hujan Mantang |
  | Col H | Pos Hujan Bintan Pesisir | `21011001A` | Pos Hujan Bintan Pesisir |
  | Col I | Pos Hujan Seri Kuala Lobam | `21011101A` | Pos Hujan Seri Kuala Lobam |
  | Col J | Pos Hujan Tambelan | `21011201A` | Pos Hujan Tambelan |
  | Col K | Pos Hujan Berakit | `21011301A` | Pos Hujan Berakit |
  | Col L | Pos Hujan Pengudang | `21011302A` | Pos Hujan Pengudang |
  | Col M | Pos Hujan Malang Rapat | `21011303A` | Pos Hujan Malang Rapat |
  | Col N | Pos Hujan Ekang Anculai | `21011304A` | Pos Hujan Ekang Anculai |
  | Col O | Pos Hujan Sri Bintan | `21011305A` | Pos Hujan Sri Bintan |
  | Col P | Pos Hujan Sebong Lagoi | `21011306A` | Pos Hujan Sebong Lagoi |
  | Col Q | Pos Hujan Tembeling | `21011307A` | Pos Hujan Tembeling |
  | Col R | Pos Hujan Penaga | `21011308A` | Pos Hujan Penaga |
  | Col S | Pos Hujan Tembeling Tanjung | `21011309A` | Pos Hujan Tembeling Tg. |
  | Col T | Pos Hujan Pengujan | `21011310A` | Pos Hujan Pengujan |

### Fitur Filter Periode Pratinjau & Diff Terfokus (Period-Aware Ingestion)
Ketika mengunggah berkas curah hujan multibulanan atau makro Bintan yang memuat ratusan/ribuan baris:
1. **Daftar Pilihan Periode Terdeteksi (Detected Periods Checkboxes):**
   - Sistem mengelompokkan data yang terdeteksi ke dalam dasarian/bulan target (misal `2026-10-das1`, `2026-10-das2`, `2026-10-das3`).
   - Operator dapat mencentang hanya periode yang hendak dikomit ke MariaDB (misal hanya Dasarian III Oktober 2026).
2. **Dropdown Filter Pratinjau Diff:**
   - Di atas tabel pratinjau perubahan (*diff table*), tersedia dropdown penyaring periode.
   - Operator dapat memfilter tampilan hanya untuk periode tertentu tanpa harus menggulir (*scrolling*) ratusan baris.
   - Badge ringkasan menampilkan: `Menampilkan X dari Y perubahan pada periode terpilih`.

---

## 15. STANDAR KANONIKAL SPI WIDE PARQUET & NAVIGASI TABEL PROBABILITAS DINAMIS

### Standarisasi Format SPI Parquet (Wide Matrix Invariant)
Seluruh berkas kanonikal SPI (`SPI_daily_30d.parquet`, `SPI_daily_90d.parquet`, `SPI_dasarian_30d.parquet`, `SPI_dasarian_90d.parquet`, dan `SPI_monthly.parquet`) disimpan dalam format **Wide Matrix**:
- **Index:** `DatetimeIndex` tanggal observasi murni (`YYYY-MM-DD`). Sistem secara otomatis mencegah dan memperbaiki korupsi `RangeIndex(0, 1, ...)` yang memicu tampilan tanggal anomali `1970-01-01`.
- **Kolom:** Tepat 52 kolom ID stasiun manual otoritatif (`21010301A`, `21710101A`, dst.). Kolom metadata seperti `station_id` atau `date` tidak diperkenankan mencemari matriks Parquet.
- **Invalidasi Cache Otomatis:** Setiap komit unggahan SPI langsung memanggil `clear_spi_cache()` sehingga data langsung tersinkronisasi ke API dan tabel dashboard secara instan tanpa perlu restart server.

### Navigasi Baru Tabel Probabilitas ECMWF (`ProbabilityDataTable`)
Mengadopsi hierarki visual setara `DailyRainfallTable.jsx`:
1. **Penyaring Resolusi (Resolution Switcher):**
   - **PROBABILITAS DASARIAN:** Menampilkan parameter operasional dasarian `pb20`, `pa150`, `pa200`, `pa300`.
   - **PROBABILITAS BULANAN:** Menampilkan parameter operasional bulanan `pa300`, `pa400`, `pa500`.
2. **Dropdown Periode Dinamis:**
   - Bersumber langsung dari database melalui endpoint `/api/v1/probability/periods`, menampilkan seluruh periode target prakiraan yang tersedia (bukan hanya daftar statis masa lalu).
3. **Indikator Vintage Aktif:**
   - Menampilkan tanggal rilis (*issue date*) dengan tag hijau `AKTIF` untuk vintage terbaru yang memenuhi batas evaluasi.
4. **Format Persentase & Badge Ambang Peringatan:**
   - Nilai probabilitas ditampilkan dalam skala persentase `0–100%`.
   - Nilai kritis ($\ge 70\%$) diberi sorotan visual (*warning badge*) sesuai bobot ancaman iklim.
   - Stasiun ARG ditampilkan dengan penanda khusus `— / Tidak tersedia (ARG)`.

---
**Pusat Pengelolaan Data Operasional DSS-PIK — Stasiun Meteorologi Kelas II Raja Haji Fisabilillah Tanjungpinang**
