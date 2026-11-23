# DEVELOPMENT HISTORY — DSS-PIK BMKG KEPULAUAN RIAU
**Kronologi Komprehensif Rekayasa Perangkat Lunak & Siklus Pengembangan Sistem**  
**Institusi**: BMKG Stasiun Meteorologi Kelas II Raja Haji Fisabilillah Tanjungpinang  
**Status**: `VERIFIED CURRENT` (November 2026)

---

## 1. RINGKASAN MATRIKS FASE PENGEMBANGAN

| Phase | Tujuan Utama | Implementasi Kunci | Modul / File Terkait | Hasil Validasi | Status | Catatan Teknis |
|---|---|---|---|---|:---:|---|
| **Phase 1** | Fondasi Arsitektur & Kontrak Data | Perancangan skema MariaDB, kontrak JSON dasar, dan integrasi time series pengamatan 57 stasiun. | `backend/database.py`, `backend/schemas.py`, `database/schema.sql` | 57 stasiun terdaftar di database, data harian 2021–2025 termuat. | `COMPLETE` | Membangun baseline relasional awal. |
| **Phase 2** | Prototipe Decision Engine & Ingestion | Implementasi awal engine evaluasi HTH, perhitungan dasar SPI, dan parsing file Excel curah hujan harian. | `backend/decision_engine.py`, `backend/ingestion_service.py` | Engine mampu mengklasifikasikan HTH stasiun ke 4 kelas peringatan. | `COMPLETE` | SPI 30D awalnya dijadikan pertimbangan aktif sebelum dipisahkan. |
| **Phase 3** | Visualisasi Dasbor & WebGIS Awal | Pembuatan UI React SPA dengan Leaflet untuk visualisasi sebaran spasial stasiun dan KPI metrik. | `frontend/src/App.jsx`, `frontend/src/components/MapLeaflet.jsx` | Peta Leaflet menampilkan 57 titik stasiun dan tabel peringatan dini. | `COMPLETE` | Awalnya menggunakan tema dasar dan kartu metrik sederhana. |
| **Phase 4** | Integrasi SPI 90D & Dual-Hazard Baseline | Penetapan SPI 90D sebagai parameter utama PDKM, isolasi SPI 30D sebagai pendukung informasional, integrasi Pb20 (>70%), dan formulasi PDCHT berbasis probabilitas dasarian/bulanan ECMWF. | `backend/decision_engine.py`, `test_phase4_decision_engine.py` | 9 skenario pengujian unit lulus 100%. Bukit Langkap dievaluasi akurat. | `COMPLETE` | Menghilangkan anomali masking SPI 30D terhadap kekeringan jangka menengah. |
| **Phase 4.1** | Dual-Hazard Consistency Reconciliation | Arbitrase sintesis dual-hazard tingkat stasiun, penanganan status parsial/inkomplit (NULL != 0), dan sinkronisasi KPI dasbor dengan priority card. | `backend/decision_engine.py`, `backend/evaluation.py`, `test_phase41_regression.py` | 16 skenario pengujian regresi lulus. KPI sinkron dengan tabel. | `COMPLETE` | Menetapkan aturan: jika salah satu bahaya tidak lengkap dan tidak ada pemicu bahaya lain, status menjadi `INCOMPLETE`. |
| **Phase 4.2** | Validasi Konsistensi Dasbor & Detail Stasiun | Penyelarasan skema endpoint detail stasiun dengan snapshot dasbor, pencegahan regresi status Bukit Langkap (AWAS), dan pengujian isolasi SPI 90D. | `backend/main.py`, `test_phase42_consistency.py` | 4 skenario pengujian konsistensi backend-API-frontend lulus 100%. | `COMPLETE` | Menjadi baseline resmi Decision Engine stasiun. |
| **Phase 5** | Hallmark Design Engine & Redesain Visual | Evaluasi tema visual menggunakan Hallmark Skill. Eksperimen tema Hedgerow (`frontend/src/hedgerow-theme.css`) dan penetapan tema final **Cobalt** dengan aksen **BMKG Atmospheric Gradients**. | `frontend/src/cobalt-theme.css`, `frontend/src/components/Header.jsx`, `LoginPage.jsx` | Antarmuka solid white, kontras tinggi, keterbacaan data numerik JetBrains Mono, logo resmi BMKG terpasang. | `COMPLETE` | Prinsip: *Readability > Visual Decoration*. Label Manual/ARG dihapus demi ketenangan kognitif operator. |
| **Phase 6.0** | Resolusi Wilayah 59 Kecamatan & Generator Peta | Peningkatan granularitas keputusan dari level kabupaten/kota ke 59 kecamatan. Pembangunan generator peta resmi BMKG JPG (1653x1170 px) dengan masker shapefile batas administrasi presisi. | `backend/regional_warning_service.py`, `backend/map_generator.py`, `OfficialMapModal.jsx` | Peta JPG resmi BMKG ter-render akurat dengan inset Kepulauan Anambas dan Natuna. | `COMPLETE` | Operator dapat menetapkan peringatan per kecamatan dan mengunduh peta siap publikasi. |
| **Phase 6.11** | Akses Multi-User Jaringan Lokal (LAN) | Penataan backend FastAPI agar mendengarkan pada interface wildcard `0.0.0.0:8000`, penyajian frontend production build langsung dari FastAPI, konfigurasi CORS dinamis LAN IP, dan session auth lintas perangkat. | `backend/main.py`, `frontend/src/config.js`, `run_cews_lan.bat` | Komputer client (B dan C) berhasil login dan mengoperasikan sistem melalui IP LAN server Komputer A. | `COMPLETE` | Menghilangkan ketergantungan pada port dev Vite 5173 di lingkungan operasional. |
| **Phase 6.11.1–4** | Hardening LAN Launcher & Auto Browser Launch | Penyempurnaan launcher Windows `run_cews_lan.bat`: deteksi otomatis IP LAN aktif, polling HTTP health check `/health` hingga siap, dan peluncuran browser Windows otomatis tepat satu kali. | `run_cews_lan.bat`, `stop_cews_lan.bat` | Server menyala dengan 1 worker Uvicorn terkelola, browser Komputer A terbuka otomatis ke dasbor. | `COMPLETE` | Masalah silent crash dan kegagalan peluncuran browser terselesaikan tuntas. |
| **Phase 6.12** | Perampingan Repositori & Audit Dependensi | Audit menyeluruh struktur file proyek, pembersihan temporary cache/artefak duplikat (mengurangi repositori dari 5.828 menjadi 1.766 file), penguncian dependensi ke `requirements-lock.txt`, dan standarisasi path portabel. | `requirements.txt`, `requirements-lock.txt`, `docs/maintenance/` | Ukuran repositori terpangkas menjadi ~260 MB, siap disalin ke komputer operasional baru. | `COMPLETE` | Menghilangkan ketergantungan absolute hardcoded path komputer pengembang lama. |
| **Phase 6.13** | Gladi Bersih Migrasi & Verifikasi Integritas | Uji coba simulasi pemindahan folder proyek, verifikasi konektivitas MariaDB lokal, pembuatan skrip verifikasi dependensi dan integritas file Parquet. | `docs/deployment/PHASE_6_13_*` | Integritas 34 berkas Parquet dan MariaDB terverifikasi utuh tanpa korupsi data. | `COMPLETE` | Prosedur checklist migrasi tervalidasi. |
| **Phase 6.14** | Pematangan Deployment Komputer Baru | Penyusunan skrip penyiapan otomatis workstation baru (`setup_dss_pik_new_pc.bat`), skrip persiapan migrasi (`prepare_dss_pik_migration.bat`), dan panduan instalasi offline. | `setup_dss_pik_new_pc.bat`, `prepare_dss_pik_migration.bat`, `docs/deployment/PHASE_6_14_*` | Prosedur transfer folder dan restore database siap dijalankan di kantor BMKG. | `COMPLETE` | Seluruh mekanisme portabilitas terdokumentasi rapi. |
| **Phase 7** | Pembaruan Threshold PDCHT, Rearrangement UI & Peta | 1. Ambang batas pemicu probabilitas PDCHT (Pa150-300, PM300-500) diubah dari `> 70%` menjadi `> 50%` (PDKM Pb20 tetap > 70%).<br>2. Grafik tren SPI dipindahkan dari tab Status ke Ringkasan Statistik pada Drawer.<br>3. Pembaruan layout peta resmi BMKG: penyesuaian baris judul periode dasarian dan legenda klasifikasi 4 kelas. | `backend/decision_engine.py`, `backend/map_generator.py`, `StationDetailDrawer.jsx` | 35 pengujian regresi lulus. Ambang > 50% memicu status PDCHT secara presisi. | `COMPLETE` | Penyelarasan dengan ketentuan teknis terbaru klimatologi BMKG. |
| **Phase 7.1** | Standardisasi Skema JSON Berbasis Keputusan | Refactoring keluaran utama JSON peringatan dini menjadi skema kanonikal 10 field root berorientasi keputusan tingkat 59 Kecamatan dan 7 Kabupaten/Kota. Penyeragaman array-of-objects pada `triggered_conditions`, proteksi `INSUFFICIENT_DATA`, dan validasi 18-point Quality Control. | `backend/regional_warning_service.py`, `docs/schemas/sih3_regional_warning.schema.json`, `test_standardized_decision_json.py` | 6 pengujian komprehensif JSON lulus. Payload terbebas dari NaN/Infinity dan memenuhi standar RFC 8259. | `COMPLETE` | Atribut terlarang root `stations` dan `data_completeness` berhasil dihilangkan dari payload keputusan. |
| **Phase 7.2** | Koreksi Identitas Resmi Institusi (Kelas II) | Koreksi nomenklatur institusi dari "Kelas I" menjadi **"BMKG Stasiun Meteorologi Kelas II Raja Haji Fisabilillah Tanjungpinang"** secara menyeluruh pada konfigurasi backend, frontend, skema JSON, generator peta, template Excel, dan dokumen aktif. | `backend/config.py`, `frontend/src/config.js`, `backend/regional_warning_service.py`, `backend/main.py` | Uji otomatis `test_07_institution_identity_single_source_of_truth_and_qc` lulus. 0 kemunculan "Kelas I" pada komponen aktif. | `COMPLETE` | Ditegakkan melalui *Single Source of Truth* konfigurasi terpusat. |

---

## 2. DETAIL EVOLUSI FITUR UTAMA

### A. Evolusi Indikator PDKM (Kekeringan)
Pada awal perancangan (Phase 1–2), parameter SPI 30-harian sempat digunakan bersama HTH dan Pb20. Namun, audit klimatologis menunjukkan bahwa fluktuasi jangka pendek SPI 30D sering kali menutupi (*masking*) defisit neraca air tanah yang terakumulasi. Pada Phase 4, dilakukan perombakan mendasar:
- **SPI 90D** ditetapkan sebagai indikator utama kekeringan defisit menengah.
- **SPI 30D** diisolasi fungsinya hanya sebagai indikator konteks informasional pendukung (tidak memiliki hak suara dalam menaikkan/menurunkan level peringatan).
- Nilai ambang SPI 90D: `<= -1.00` (Waspada), `<= -1.50` (Siaga), `<= -2.00` (Awas).
- Nilai ambang Pb20: `> 70%` (hanya dapat memicu level Waspada).

### B. Evolusi Threshold PDCHT (Curah Hujan Tinggi)
Sebelum Phase 7, indikator probabilitas curah hujan ekstrem ECMWF (dasarian Pa150, Pa200, Pa300 dan bulanan PM300, PM400, PM500) menggunakan ambang peluang `> 70%`. Pada Phase 7, dilakukan penyesuaian aturan operasional BMKG:
- Ambang batas seluruh kelas probabilitas PDCHT diturunkan menjadi **`> 50%`**.
- Evaluasi dasarian dan bulanan disintesis menggunakan aturan level maksimum (`max(dasarian, bulanan)`).

### C. Evolusi Format Output JSON Publikasi
Sistem keluaran data JSON DSS-PIK mengalami beberapa iterasi penyempurnaan:
1. *Iterasi Awal (Legacy WordPress)*: JSON difokuskan pada ringkasan stasiun dengan 5 root field dan format triggered conditions berupa teks string.
2. *Iterasi Phase 6.0*: Penambahan data 59 kecamatan namun sempat memuat field redundant di root (`stations`, `data_completeness`).
3. *Iterasi Final Phase 7.1–7.2 (Standardized Decision-Based Schema)*:
   - Tepat **10 atribut root**: `schema_version`, `system`, `institution`, `publication`, `source`, `generated_at`, `period`, `province`, `kecamatan`, `regions`.
   - 59 kecamatan masing-masing memiliki 11 atribut lengkap, termasuk `hazard_assessments` (8 atribut), `recommendations` (dengan array of objects terstruktur 9 kunci), dan `final_decision` (7 atribut).
   - Menjamin bahwa jika operator melakukan override, `recommended_level` asli tidak termutasi, dan rekomendasi yang dibatalkan otomatis dikeluarkan dari array `warnings`.

---
*Dokumen ini disusun berdasarkan rekonstruksi data commit, kode program aktual, dan arsip laporan resmi per November 2026.*
