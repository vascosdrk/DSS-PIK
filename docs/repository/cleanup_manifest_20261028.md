# MANIFEST PERAPIAN STRUKTUR BERKAS REPOSITORY (FINAL CLEANUP)
**DSS-PIK BMKG Stasiun Meteorologi Kelas I Raja Haji Fisabilillah Tanjungpinang**  
**Tanggal**: 28 Oktober 2026  
**Status**: 100% Selesai & Terverifikasi Aman

---

## 1. INVENTARISASI STRUKTUR DIREKTORI REPOSITORY

| Direktori | Deskripsi & Peran Arsitektur | Kebijakan Perapian & Keamanan |
| :--- | :--- | :--- |
| `backend/` | Source code FastAPI, router, database, engine, dan period service | **Pertahankan 100%**. Seluruh endpoint operasional aktif dipertahankan. |
| `frontend/` | Source code UI React, Leaflet GIS, komponen, dan Vite build | **Pertahankan 100%**. Panel periode 2-tier dan responsif tanpa overflow. |
| `config/` | Konfigurasi jalur file kanonikal (`paths.py`) dan parameter sistem | **Pertahankan 100%**. Jalur direktori portabel berbasis `%PROJECT_ROOT%`. |
| `data/raw/` | Dataset observasi curah hujan mentah dan SPI Parquet | **DIKUNCI / FROZEN**. Larangan modifikasi destruktif pada seluruh file sumber. |
| `data/processed/` | Dataset hasil olahan, deret HTH, dan snapshot evaluasi | **Pertahankan**. 10 snapshot historis utuh; preview dinamis on-the-fly. |
| `data/operational/` | Konfigurasi periode aktif (`period_config.json`) dan output peta | **Aktif**. Konfigurasi auto/manual tersimpan di server. Default: `auto`. |
| `data/historical/` | Rekam jejak arsip peringatan dini operasional | **DIKUNCI / FROZEN**. Larangan modifikasi baris historis. |
| `docs/` | Dokumentasi arsitektur, serah terima, dan data lineage | **Diperbarui**. Panduan 2 launcher utama & serah terima operasional. |
| `logs/runtime/` | Direktori log runtime proses backend dan frontend | **Aktif**. Menampung `backend.log` dan `frontend.log` secara aman. |
| `pipeline/` | Skrip batch data processing dan engine keputusan | **Pertahankan 100%**. `pipeline/generate_cews_decision_engine.py` kanonikal. |
| `reports/validation/`| Laporan teknis validasi, audit, dan quality control | **Diperbarui**. Menyimpan laporan final perapian dan validasi. |
| `scratch/` | Skrip audit, verifikasi sementara, dan utilitas pengujian | **Dibersihkan**. File gambar sementara diarsipkan ke `backups/archive/`. |
| `tests/` | Suite pengujian otomatis (unit, regression, integration) | **Diperbarui**. 38 tes otomatis lulus 100%. |
| `backups/` | Cadangan kode sebelum modifikasi & arsip launcher lama | **Pertahankan**. Menampung `launcher_archive/` dan backup historis. |

---

## 2. AUDIT & PENYEDERHANAAN ROOT REPOSITORY

Sesuai arahan master prompt, seluruh pengoperasian sistem disederhanakan menjadi tepat **DUA** launcher utama pada root repository:

### A. Berkas Operasional pada Root Proyek (Tepat 2 Launcher)

| Nama File di Root | Tipe | Peran & Deskripsi Operasional |
| :--- | :---: | :--- |
| `run_cews.bat` | **LAUNCHER UTAMA (START)** | Menjalankan MariaDB, FastAPI (8000), Vite (5173), memeriksa kesehatan `/health`, dan **membuka browser tepat 1 kali** ke `http://localhost:5173/`. Anti-duplikasi instance. |
| `stop_cews.bat` | **LAUNCHER UTAMA (STOP)** | Menghentikan backend dan frontend secara aman berbasis port/PID target (`taskkill /F /T /PID`). **Melindungi MariaDB** agar tidak dimatikan paksa. |
| `powershell.cmd` | Script Helper | Helper eksekusi shell PowerShell untuk kompatibilitas Windows terminal. |
| `.env` & `.env.example` | Konfigurasi | Environment database dan JWT secret. Kredensial tidak pernah dicatat ke file log. |
| `.gitignore` | Konfigurasi Git | Mengabaikan node_modules, cache, dist, dan file sensitif. |
| `README.md` | Dokumentasi | Dokumentasi ringkas pengenalan repositori. |

### B. Berkas yang Diarsipkan dari Root ke Folder Backups

| Nama File Semula | Lokasi Baru | Alasan & Justifikasi Teknis |
| :--- | :--- | :--- |
| `buka_dashboard.bat` | `backups/launcher_archive/` | Redundan; fungsionalitas pembuka browser telah disatukan langsung ke dalam `run_cews.bat`. |
| `buka_dashboard_cews.bat`| `backups/launcher_archive/` | Redundan; wrapper lama diarsipkan untuk kebersihan root. |
| `run_cews_demo.bat` | `backups/launcher_archive/` | Redundan; seluruh proses eksekusi dialihkan ke launcher resmi `run_cews.bat`. |
| `stop_cews_demo.bat` | `backups/launcher_archive/` | Berisiko tinggi (mematikan seluruh `python.exe` & `node.exe` tanpa isolasi PID). Digantikan oleh `stop_cews.bat`. |
| `generate_cews_decision_engine.py` | `backups/archive/` | Duplikat dari `pipeline/generate_cews_decision_engine.py` (MD5 identik: `d98bf69fb710a0554d1884eb0766b4bf`). Import test telah diarahkan ke pipeline. |
| Temporary PNG renders | `backups/archive/scratch_renders/` | File output render visual sementara dari `scratch/` diarsipkan agar scratch bersih. |

---

## 3. PERBAIKAN UI PANEL PERIODE (2-TIER RESPONSIVE LAYOUT)

Penyebab visual overflow sebelumnya adalah struktur 1-baris datar pada `.period-selector-container` dengan `max-width: 500px` dan `white-space: nowrap` yang memaksakan judul label, badge `[MODE MANUAL]`, tombol `[Ikuti Waktu Real-time]`, badge status data, dan dropdown selector berada dalam satu baris horizontal (> 700px).

Solusi yang telah diimplementasikan:
1. **Tier 1 (Header Status Bar)**:
   - Sisi Kiri: Label `PERIODE PERINGATAN DINI` + Badge Mode (`[Real-Time]` atau `[Mode Manual]`).
   - Sisi Kanan: Tombol `[Ikuti Waktu Real-time]` (hanya saat mode manual) + Badge Kesiapan Data (`[Terverifikasi]` atau `[Data Parsial]`).
   - Menggunakan `display: flex; justify-content: space-between; flex-wrap: wrap;`.
2. **Tier 2 (Full-Width Dropdown Dasarian)**:
   - Dropdown selektor dasarian memanfaatkan 100% lebar kontainer secara proporsional.
   - Pilihan mencakup 10 dasarian aktif (misal `Dasarian II September 2026`) serta opsi custom `➕ Pilih Periode Dasarian Lain...`.
3. **Responsi Bebas Overflow**:
   - Menghapus aturan CSS override yang kaku (`max-width: 500px`).
   - Kontainer menggunakan `flex: 1 1 380px; min-width: 0; max-width: 580px;` sehingga menyesuaikan secara fleksibel dengan kartu metadata cutoff observasi dan tombol generator peta tanpa pemotongan teks atau scrollbar horizontal yang tidak diinginkan.

---

## 4. VERIFIKASI INTEGRITAS BASELINE DATA OPERASIONAL

Pemeriksaan integritas sebelum dan sesudah perapian membuktikan **tidak ada pengurangan, penimpaan, atau distorsi data**:

1. **Database MariaDB (`cews_db`)**:
   - `cews_rainfall_daily`: **286.085 baris** (100% utuh).
   - `cews_warning_history`: **2.052 baris** (100% utuh).
   - `stations`: **57 stasiun** (100% utuh).
   - `cews_period_snapshot`: **570 baris** (100% utuh di 10 periode).

2. **File Sumber SPI Parquet (4 File)**:
   - `data/raw/spi/dasarian/SPI_all_30d.parquet`: 291.596 bytes | MD5: `503f28589fc2cce6dc06771a932d89f2`
   - `data/raw/spi/dasarian/SPI_all_90d.parquet`: 293.494 bytes | MD5: `b87b4d32fa45aa554b7510f034d538ad`
   - `data/raw/spi/harian/SPI_all_30d.parquet`: 2.763.280 bytes | MD5: `2996dce038b1afeeb28d018789044f58`
   - `data/raw/spi/harian/SPI_all_90d.parquet`: 2.786.050 bytes | MD5: `44a079d76c1bda1a762b4e4d62b8b936`

3. **Snapshot Historis Evaluasi**:
   - 10 snapshot evaluasi historis pada `data/processed/evaluation/snapshots/` (`2026-06-das2.json` s.d. `2026-09-das2.json`) tetap utuh dan terkunci.

4. **Pengujian Regresi Otomatis (38 Tes)**:
   - `tests/test_audit_incomplete_and_ui_refinement.py`: 7/7 PASSED (100%).
   - `tests/test_realtime_period_and_launcher_recovery.py`: 11/11 PASSED (100%).
   - `tests/regression/test_october_2026_acceptance.py`: 3/3 PASSED (100%).
   - `tests/integration/test_dashboard_contract.py`: 1/1 PASSED (100%).
   - `tests/api/test_api_endpoints.py`: 7/7 PASSED (100%).
   - `tests/test_audit_incomplete_and_ui_refinements.py`: 16/16 PASSED (100%).
   - **Total**: 38/38 Tes Berstatus **PASS (100%)**.
