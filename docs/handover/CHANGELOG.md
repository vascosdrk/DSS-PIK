# CHANGELOG — DSS-PIK BMKG TANJUNGPINANG
## Catatan Perkembangan & Riwayat Rilis Teknis (Phase 1 s.d. Phase 5.2)

---

## [Phase 1–3] — Fondasi Sistem, Ingestion & Dashboard Operasional
- **Tujuan**: Membangun fondasi sistem peringatan dini iklim otomatis untuk BMKG Kepulauan Riau.
- **Perubahan Utama**:
  - Perancangan skema database MariaDB (`cews_db`) dengan tabel stasiun (`stations`), curah hujan harian (`cews_rainfall_daily`), dan probabilitas prakiraan (`cews_forecast_snapshot`).
  - Implementasi ingestion data curah hujan harian multi-stasiun (Manual dan ARG) dengan normalisasi kode stasiun.
  - Implementasi pipeline perhitungan SPI dasarian, bulanan, dan harian berbasis distribusi Pearson III dan Gamma (BestDist).
  - Pembangunan antarmuka Web GIS interaktif berbasis React dan Leaflet.
- **Hasil**: Fondasi operasional berjalan; data curah hujan 1981-2026 tersimpan; visualisasi peta sebaran stasiun aktif.

---

## [Phase 4] — Integrasi SPI 90D Primer PDKM
- **Tujuan**: Menyelaraskan evaluasi kekeringan meteorologis dengan standar operasional klimatologi BMKG.
- **Perubahan Utama**:
  - Mengintegrasikan berkas `SPI_all_90d.parquet` sebagai parameter utama evaluasi PDKM menggantikan ketergantungan tunggal pada SPI 30D.
  - Menetapkan SPI 30D sebagai parameter pendukung informasional (tidak memengaruhi level sintesis).
  - Memperbarui `backend/decision_engine.py` untuk membaca dan mengevaluasi ambang:
    - SPI 90D <= -1.00 (Waspada)
    - SPI 90D <= -1.50 (Siaga)
    - SPI 90D <= -2.00 (Awas)
- **Hasil**: Evaluasi PDKM mencerminkan kondisi kekeringan jangka menengah dengan akurat.

---

## [Phase 4.1] — Rekonsiliasi Dual-Hazard & Sinkronisasi Waktu
- **Tujuan**: Menghilangkan inkonsistensi antara hasil Decision Engine, filter cutoff observasi, dan tampilan antarmuka.
- **Perubahan Utama**:
  - Pemisahan kanonikal status bahaya: `pdkm_status` dan `pdcht_status` dievaluasi dan dilaporkan secara independen.
  - Penegasan status `MULTI_HAZARD` jika kedua jenis bahaya aktif pada stasiun yang sama.
  - Rekonsiliasi filter cutoff tanggal observasi harian: Observasi difilter dengan batas `<= CURRENT_DATE` dan status valid (`OBSERVED_VALID`, `OBSERVED_ZERO`), mengabaikan data anomali masa depan.
  - Pembuatan uji regresi `test_phase41_regression.py` (16 pengujian).
- **Hasil**: 16/16 uji regresi lulus; tidak ada kontradiksi status bahaya antara API dan UI.

---

## [Phase 4.2] — Final Decision Engine & Dashboard Reconciliation
- **Tujuan**: Penyelarasan menyeluruh kelengkapan data, kartu KPI, filter, marker peta, dan drawer detail stasiun.
- **Perubahan Utama**:
  - Penerapan kebijakan `PARTIAL` (peringatan tetap aktif meski parameter pendukung hilang) dan `INCOMPLETE` (data kurang saat kondisi normal).
  - Standarisasi cakupan stasiun konsisten menjadi **57 Stasiun** di seluruh komponen (menghilangkan penyebutan manual/ARG).
  - Sinkronisasi reaktif filter PDKM/PDCHT terhadap 6 kartu KPI, tabel HTH, dan warna marker peta.
  - Penyusunan `test_phase42_consistency.py` (4 pengujian integrasi).
- **Hasil**: Seluruh 20 pengujian (Phase 4.1 + 4.2) lulus 100%.

---

## [Phase 5] — Integrasi Hallmark & Eksplorasi Tema Hedgerow
- **Tujuan**: Meningkatkan kualitas visual antarmuka menjadi dashboard operasional kelas profesional menggunakan Hallmark Design Engine.
- **Perubahan Utama**:
  - Integrasi repository upstream Hallmark ke dalam workspace (`vendor/hallmark-upstream/` commit `52328cb3129135499e4e178d4864ee90029dea2b`).
  - Pembuatan Agent Skill Hallmark pada `.agents/skills/hallmark/SKILL.md`.
  - Eksplorasi tema visual *Hedgerow* (editorial deep green dengan tipografi Prata/Manrope).
  - Evaluasi pengguna: Nuansa hijau terlalu mendominasi dan kurang mencerminkan identitas meteorologi/klimatologi BMKG.
- **Hasil**: Toolset Hallmark terpasang permanen sebagai aset desain proyek; tema Hedgerow diarsipkan ke `frontend/src/hedgerow-theme.css`.

---

## [Phase 5.1 & 5.2] — Cobalt Theme & Refinement Gradien Atmosferik BMKG
- **Tujuan**: Redesign visual menyeluruh berbasis tema **Cobalt** yang diperkaya gradien atmosferik biru-kehijauan khas BMKG dengan fokus mutlak pada keterbacaan data.
- **Perubahan Utama**:
  - Pembuatan stylesheet utama `frontend/src/cobalt-theme.css` sebagai *Source of Truth* visual.
  - Tipografi: Space Grotesk (Heading & Display), Inter (Body & Label), JetBrains Mono (Nilai Numerik, Tanggal & Kode).
  - Header: Gradien biru laut BMKG (`#0f2744` s.d. `#165b7e`) dengan teks kontras tinggi putih bersih (`#ffffff`), subjudul biru es (`#bae6fd`), dan border tipis cyan-teal.
  - Permukaan Data: Seluruh kartu KPI, sel tabel, modal dialog, dan Station Detail Drawer menggunakan latar belakang solid putih kontras tinggi (`#ffffff`) tanpa gradien yang mengaburkan teks.
  - Logo Resmi BMKG: Terpasang dengan resolusi tinggi pada Header dan Halaman Login (ukuran 72px, terpusat rapi).
  - Halaman Login: Pembersihan elemen tidak perlu; judul `DSS-PIK` terpusat; subjudul resmi teratur; tombol login gradien biru BMKG.
- **Hasil**:
  - `npm --prefix frontend run build` sukses 100% (`Exit Code: 0`).
  - 20/20 Pytest regression tests tetap lulus 100%.
  - Tampilan modern, bersih, terbaca sangat jelas, dan memiliki identitas kelembagaan BMKG yang kuat.

---

## [Phase 6.0] — Resolusi Pemetaan & Penetapan Peringatan Dini Tingkat Kecamatan (59 Kecamatan)
- **Tanggal Rilis**: November 2026
- **Tujuan**: Mengupgrade sistem penetapan peringatan dini iklim dan output peta resmi BMKG dari level Kabupaten/Kota menjadi **level Kecamatan (59 Kecamatan se-Provinsi Kepulauan Riau)** sesuai permintaan operasional BMKG.
- **Perubahan Utama**:
  1. **Pemetaan Spasial 59 Kecamatan**:
     - Menggunakan batas resmi shapefile `data/reference/PETA/KEPRI.shp` dan `data/reference/boundaries/kepri_kecamatan.geojson`.
     - 57 stasiun BMKG dipetakan secara spasial (*spatial join*) ke dalam 59 kecamatan (35 kecamatan memiliki pos hujan langsung, 24 kecamatan mewarisi status kabupaten induknya).
     - *Catatan Analisis Kewilayahan*: Kecamatan Belat di Kabupaten Karimun tercatat menyatu di dalam poligon Kecamatan Kundur Utara sesuai basis data Kode BPS 2010 pada shapefile referensi.
  2. **Mesin Pemetaan & Rasterisasi Peta Resmi (`backend/map_generator.py`)**:
     - Implementasi `get_kecamatan_masks()`: Mempartisi daratan tiap kabupaten menjadi mask piksel kecamatan independen.
     - Pewarnaan presisi per kecamatan pada peta resmi A4 Landscape 150 DPI (1653×1170) tanpa kebocoran piksel batas wilayah.
     - Mendukung variasi status dalam satu kabupaten (misal: sebagian kecamatan WASPADA/Kuning dan sebagian AMAN/Hijau).
  3. **Ekspor JSON Terstandarisasi (`backend/regional_warning_service.py`)**:
     - Memperbarui payload JSON SIH3 (`/api/v1/maps/generate-json`): Menyertakan struktur `"kecamatan"` (59 objek lengkap) di samping mempertahankan `"regions"` (7 kabupaten/kota) untuk backward compatibility.
  4. **Antarmuka Interaktif Operator (`frontend/src/components/OfficialMapModal.jsx`)**:
     - **Tab Navigasi Wilayah**: Tab bar instan 7 Kabupaten/Kota (`Batam`, `Bintan`, `Karimun`, `Anambas`, `Lingga`, `Natuna`, `Tanjungpinang`) + Tab `Semua (59)`.
     - **Fitur Konfirmasi Wilayah**: Tombol *"Konfirmasi Status [Wilayah]"* dengan badge centang ($\checkmark$) visual di tab kabupaten/kota yang sudah diverifikasi.
     - **Single Unified Dropdown**: Pemilihan status per kecamatan disederhanakan menjadi 1 dropdown terpadu (*PDKM*, *PDCHT*, atau *AMAN*).
     - **Aksi Cepat & Massal**: Opsi *"Set Semua"* untuk menerapkan status seragam pada seluruh kecamatan di wilayah yang sedang aktif.
     - **Perbaikan Keterguliran (*Scroll Fix*)**: Menjaga modal berukuran lapang (`88vh`, max `1100px`) dengan tombol *"Revisi / Gulir Ke Atas"* agar daftar kecamatan tetap dapat diakses dan diedit kembali setelah peta dihasilkan.
  5. **Endpoint API Baru**:
     - `GET /api/v1/warnings/kecamatan/recommendations`: Menghitung dan menyajikan rekomendasi PDKM/PDCHT 59 kecamatan.
- **Hasil**:
  - `npm --prefix frontend run build` sukses 100% tanpa error.
  - Server FastAPI dan generator peta memproses dan merender peta JPG serta dokumen JSON tingkat kecamatan secara presisi.

