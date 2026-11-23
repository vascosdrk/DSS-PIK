# PHASE 6.14 — MARIADB VERSION & DATABASE COMPATIBILITY
**Sistem:** DSS-PIK BMKG Kepulauan Riau  
**Database:** `cews_db`  

---

## 1. Hasil Audit Skema & Konfigurasi MariaDB Aktual

| Parameter Database | Nilai Terverifikasi pada Komputer A |
|---|---|
| **Versi Server** | `13.0.2-MariaDB` (Kompatibel dengan `11.4+` dan `13.0+`) |
| **Storage Engine** | `InnoDB` pada seluruh `12` tabel + `1` View (`v_cews_current_warning_map`) |
| **Character Set & Collation** | `utf8mb4` / `utf8mb4_unicode_ci` |
| **SQL Mode** | `STRICT_TRANS_TABLES,ERROR_FOR_DIVISION_BY_ZERO,NO_AUTO_CREATE_USER,NO_ENGINE_SUBSTITUTION` |
| **Time Zone** | `SYSTEM` (`Asia/Jakarta` / WIB UTC+7) |
| **Struktur Indeks & Relasi** | `13` Tabel/View, `51` Indeks, `3` Foreign Keys, `0` Trigger, `0` Routine |

---

## 2. Catatan Kompatibilitas Penting (Generated Columns)
- Tabel `cews_rainfall_daily` memiliki kolom generated (`year`, `month`, `day`).
- Pada MariaDB `11.4+` dan `13.0+` dengan `STRICT_TRANS_TABLES`, menyertakan kolom generated pada pernyataan `INSERT` memicu Error `1906`.
- Seluruh pernyataan `INSERT INTO cews_rainfall_daily` pada `backend/ingestion_service.py` dan `backend/main.py` telah diselaraskan (tidak menulis langsung ke kolom `year`, `month`, `day`), sehingga kompatibel penuh pada MariaDB `11.4+` maupun `13.0.2`.

---

## 3. Rekomendasi Target Komputer Baru
- **Rekomendasi Utama**: Instal **MariaDB `13.0.2` (64-bit)** atau **MariaDB `11.4 LTS` (64-bit)** pada port `3306` (`127.0.0.1`).
- Gunakan opsi dump `--single-transaction --routines --triggers --events` saat backup dan pulihkan ke database ber-collation `utf8mb4_unicode_ci`.

