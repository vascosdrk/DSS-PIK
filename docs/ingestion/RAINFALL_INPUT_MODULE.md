# DSS-PIK — Modul Input Data Curah Hujan (V2)

**Status**: Aktif di Lingkungan Pengembangan Lokal (`backend/rainfall_ingestion_v2.py` & `frontend/src/components/RainfallInputModal.jsx`)  
**Versi Parser**: `1.2.0` + Rainfall V2 Multi-Format Engine  
**Database Lokal**: MariaDB 11.4.10 (`cews_db_migration_test`)

---

## 1. Arsitektur Input Baru

Modul Input Data Curah Hujan V2 memisahkan secara bersih antara **deteksi struktur workbook**, **normalisasi meteorologi per wilayah**, **pemetaan stasiun**, dan **komitmen transaksional atomik MariaDB**, sambil mempertahankan 100% kompatibilitas dengan template lama (Batam, Bintan XLSM, Tanjungpinang, dan Multi-Sheet).

```mermaid
flowchart TD
    A["Tombol INPUT DATA CH"] --> B["Tahap 1: Pilih Kabupaten/Kota (7 Wilayah)"]
    B --> C["Tahap 2: Pilih Metode Input"]
    C --> D["Upload File Excel (Multi-File)"]
    C --> E["Input Manual Multi-Tanggal"]
    D --> F["Automatic Template Detection Engine"]
    F -->|Terdeteksi| G["Pilih Periode (Dasarian / Rentang Tanggal)"]
    F -->|Tidak Dikenali| H["Mapping Wizard -> Simpan Profil Persisten"]
    H --> G
    G --> I["Parsing & Normalisasi per Wilayah (Partial-Period)"]
    E --> I
    I --> J["Tahap 4: Validasi & Diff vs MariaDB"]
    J --> K["Konfirmasi Konflik + Alasan Koreksi"]
    K --> L["Tahap 5: Transaksi Atomik MariaDB + Audit & Rollback"]
```

---

## 2. Matriks Dukungan Wilayah & Template

| Wilayah | Kode API | Template Mentah (Raw) | Template Lama (Legacy) |
|---|---|---|---|
| Kabupaten Karimun | `KARIMUN` | Ya (`RAW_KARIMUN`) | Ya (`LEGACY_MULTI_SHEET`) |
| Kabupaten Lingga (Dabo Singkep) | `LINGGA` | Ya (`RAW_LINGGA`) | Ya (`LEGACY_MULTI_SHEET`) |
| Kabupaten Natuna | `NATUNA` | Ya (`RAW_NATUNA`) | Ya (`LEGACY_MULTI_SHEET`) |
| Kabupaten Kepulauan Anambas | `ANAMBAS` | Ya (`RAW_ANAMBAS`) | Ya (`LEGACY_MULTI_SHEET`) |
| Kota Batam | `BATAM` | Tidak | Ya (`LEGACY_MULTI_SHEET`) |
| Kabupaten Bintan | `BINTAN` | Tidak | Ya (`LEGACY_BINTAN_XLSM`, `LEGACY_MULTI_SHEET`) |
| Kota Tanjungpinang | `TANJUNGPINANG` | Tidak | Ya (`LEGACY_MULTI_SHEET`) |

---

## 3. Automatic Template Detection Engine

Deteksi dilakukan berdasarkan **struktur workbook** (`detect_rainfall_template` di `backend/rainfall_ingestion_v2.py`), bukan sekadar nama file:
1. **Karimun Raw (`RAW_KARIMUN`)**: Mencari penanda `No. Stasiun Hujan` pada blok vertikal stasiun (mendukung `Lembar1` dan mengabaikan `Lembar2` kosong). Jumlah stasiun dinamis (tidak di-hardcode).
2. **Lingga Raw (`RAW_LINGGA`)**: Tanggal vertikal di kolom B, stasiun horizontal di kolom C–J, kolom penanda dasarian (K), header bertingkat/merged cells, dan deteksi konflik nama sheet vs judul dokumen (mis. sheet `SEP` vs judul `OKTOBER 2026`).
3. **Natuna Raw (`RAW_NATUNA`)**: Nama stasiun vertikal di kolom A, tanggal 1–31 horizontal di kolom B–AF, mengabaikan kolom akumulasi (AG) dan hari hujan (AH). Sheet `YYMM` (mis. `2610`) ditampilkan sebagai kandidat periode yang wajib dikonfirmasi operator.
4. **Anambas Raw (`RAW_ANAMBAS`)**: Metadata stasiun di kolom A–F (stasiun tanpa kode dicocokkan lewat nama), tanggal 1–30/31 di kolom G–AJ, mengabaikan kolom akumulasi dasarian/bulanan (AK–AN).
5. **Legacy (`LEGACY_BINTAN_XLSM`, `LEGACY_MULTI_SHEET`)**: Didelegasikan ke parser existing `parse_rainfall_excel()` di `backend/ingestion_service.py` dengan tambahan filter rentang tanggal opsional.
6. **Profil Kustom Tersimpan (`CUSTOM_MAPPED`)**: Dicocokkan otomatis melalui `structure_fingerprint` dari tabel `cews_rainfall_template_profiles`. Jika tetap tidak dikenali, status `NEEDS_MAPPING` membuka **Mapping Wizard**.

---

## 4. Aturan Normalisasi Simbol & Representasi Standar DSS-PIK

**Representasi Akhir Tabel CH & Ekspor DSS-PIK**:
- Tidak ada hujan (`0 mm`, `OBSERVED_ZERO`) → **`-`**
- Hujan tidak terukur (`TTU`) → **`TTU`** *(bukan 0 mm pada perhitungan SPI)*
- Data tidak masuk, sel pengamatan kosong, atau alat rusak (`MISSING`/`DAMAGED`) → **`9999`** *(bukan 0 mm pada perhitungan SPI)*
- Curah hujan terukur (`OBSERVED_VALID`) → nilai numerik dalam mm (mis. `12.5`)

| Wilayah | Simbol Sumber | `obs_status` | Hasil Standar DSS-PIK |
|---|---|---|---|
| Karimun (Raw) | `0` | `OBSERVED_ZERO` | `-` |
| Karimun (Raw) | `TTU` | `TTU` | `TTU` |
| Karimun (Raw) | `9999` / sel kosong | `MISSING` | `9999` |
| Lingga (Raw) | `0` | `OBSERVED_ZERO` | `-` |
| Lingga (Raw) | `-`, `9999`, sel kosong | `MISSING` | `9999` |
| Lingga (Raw) | `TTU`, `8888` | `TTU` | `TTU` |
| Natuna (Raw) | `0`, `TTU` | `TTU` | `TTU` |
| Natuna (Raw) | `-`, `9999`, sel kosong | `MISSING` | `9999` |
| Anambas (Raw) | `-` | `OBSERVED_ZERO` | `-` |
| Anambas (Raw) | `0`, `TTU` | `TTU` | `TTU` |
| Anambas (Raw) | `9999`, sel kosong | `MISSING` | `9999` |
| Legacy (7 Wilayah) | `-`, `0` | `OBSERVED_ZERO` | `-` |
| Legacy (7 Wilayah) | `TTU` | `TTU` | `TTU` |
| Legacy (7 Wilayah) | `9999`, `X`, `R` | `MISSING` / `DAMAGED` | `9999` |

**Aturan Partial-Period Import**:
- Tanggal yang tercantum dalam struktur file namun sel observasinya kosong → dinormalisasi ke `MISSING` (`9999`).
- Tanggal yang sama sekali **tidak tercantum** dalam file mentah → **tidak dibuatkan record**.

---

## 5. Database & Migration

Migration aditif (aman, non-destruktif): `database/migrations/20261125_add_rainfall_template_profiles.sql`
- `cews_rainfall_template_profiles`: Menyimpan aturan struktur workbook (`structure_fingerprint`, `sheet_rules_json`, `header_config_json`, `date_config_json`, `value_config_json`, `station_config_json`, `ignored_columns_json`, `symbol_mapping_json`, `version`).
- `cews_rainfall_station_aliases`: Menyimpan pemetaan identitas pos sumber ke master `station_id` secara terpisah dari profil template.

Tabel operasional yang digunakan bersama dengan modul existing:
- `cews_rainfall_daily` (`UNIQUE KEY uq_station_date (station_id, observation_date)`)
- `staging_rainfall_import`
- `cews_rainfall_correction_log`
- `cews_ingestion_history` (termasuk `batch_items_json` sehingga fitur rollback `cancel_ingestion_batch` tetap bekerja penuh).

---

## 6. Endpoint API V2

Semua endpoint dilindungi oleh `authentication_guard_middleware`:

| Method | Endpoint | Fungsi |
|---|---|---|
| `GET` | `/api/v1/rainfall/v2/regencies` | Daftar 7 kabupaten/kota, matriks dukungan template, dan daftar stasiun master |
| `POST` | `/api/v1/rainfall/v2/detect` | Upload 1 atau beberapa file Excel + Automatic Template Detection |
| `GET` | `/api/v1/rainfall/v2/profiles` | Daftar profil Mapping Wizard tersimpan |
| `POST` | `/api/v1/rainfall/v2/profiles` | Simpan profil Mapping Wizard + alias stasiun secara persisten |
| `POST` | `/api/v1/rainfall/v2/preview` | Parsing sesuai periode terpilih + validasi diff vs MariaDB |
| `POST` | `/api/v1/rainfall/v2/commit` | Commit transaksional atomik + audit trail + baseline fingerprint check |
| `POST` | `/api/v1/rainfall/v2/manual/preview` | Validasi & diff input manual multi-tanggal |
| `POST` | `/api/v1/rainfall/v2/manual/commit` | Commit transaksional input manual multi-tanggal |

---

## 7. SOP Operator Singkat

1. Buka menu **Pusat Data → Data Curah Hujan**, klik tombol **Input Data Curah Hujan**.
2. Pilih **Kabupaten/Kota** (1 wilayah per sesi).
3. Pilih **Upload File Excel** atau **Input Manual**.
   - **Upload**: Seret 1 atau beberapa file `.xlsx`/`.xlsm` → klik **Deteksi Format Otomatis** → konfirmasi periode (atau gunakan **Mapping Wizard** jika format baru) → klik **Pratinjau & Validasi**.
   - **Manual**: Pilih stasiun → pilih Dasarian atau Rentang Tanggal → isi nilai atau paste langsung dari Excel → klik **Pratinjau & Validasi**.
4. Periksa ringkasan (`Baru`, `Konflik`, `Identik`, `Invalid`, `TTU`, `Missing`). Jika ada `Konflik` yang ingin diperbarui, centang persetujuan dan wajib isi **Alasan Koreksi**.
5. Klik **Simpan ke Database**. Catat `Batch ID` untuk penelusuran di tab **Manajemen Data Operasional**.

---

## 8. Pengujian & Troubleshooting

Jalankan test suite lokal (pastikan MariaDB portable lokal aktif di port 3306):
```powershell
.venv\Scripts\python.exe -m pytest tests/integration/test_rainfall_input_v2.py -v
.venv\Scripts\python.exe -m pytest tests/integration/test_period_aware_ingestion_hardening.py -v
```

**Batasan yang diketahui**:
- Format biner Excel lama `.xls` (BIFF) ditolak dengan pesan jelas karena `openpyxl` hanya membaca `.xlsx`/`.xlsm`; simpan ulang file sebagai `.xlsx`.
- Empat workbook mentah asli dari daerah belum tersimpan di direktori fixture lokal sehingga pengujian parser mentah saat ini menggunakan fixture sintetis yang mereplikasi spesifikasi struktur aktual.
