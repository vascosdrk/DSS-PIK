# DSS-PIK PRE-OPERATIONAL VERIFICATION CHECKLIST
**Sistem:** Decision Support System Peringatan Iklim Kepulauan Riau (DSS-PIK)  
**Institusi:** BMKG Stasiun Meteorologi Kelas II Raja Haji Fisabilillah Tanjungpinang  
**Dokumen:** Panduan Checklist Operasional Pra-Ingestion Data  
**Versi:** 2.0 (November 2026)  

---

## 1. TUJUAN CHECKLIST

Checklist ini wajib dijalankan oleh Tim Operasional/Prakirawan Iklim BMKG dan Administrator Sistem sebelum:
1. Memulai sesi operasional penerbitan buletin peringatan dini iklim dasarian.
2. Melakukan ingestion pembaruan data curah hujan dan prakiraan cuaca terbaru.
3. Melakukan ekspor peta JPG dan rilis JSON integrasi SIH3 Pemerintah Provinsi Kepulauan Riau.

---

## 2. CHECKLIST 10 PILAR KESIAPAN OPERASIONAL

| No | Pilar Pemeriksaan | Komponen / Parameter yang Diuji | Nilai Rujukan Standar | Status (V / X) |
| :---: | :--- | :--- | :--- | :---: |
| **1** | **Infrastruktur & Layanan** | MariaDB Daemon (Port 3306) | Berjalan & merespon query | [ ] |
| | | Backend FastAPI (Port 8000) | `GET /health` mengembalikan `status: ok` | [ ] |
| | | Web GIS Frontend (Port 5173) | Vite dev server siap melayani UI | [ ] |
| **2** | **Integritas Basis Data** | Tabel `cews_rainfall_daily` | 286.085 baris historis utuh | [ ] |
| | | Tabel `stations` | 57 stasiun terdaftar | [ ] |
| | | Tabel `cews_period_snapshot` | Snapshot dasarian valid | [ ] |
| | | Tabel `cews_forecast_snapshot` | Probabilitas ECMWF terisi | [ ] |
| **3** | **Data Parquet Kanonikal** | `final_rainfall_daily.parquet` | Ada di `data/raw/rainfall/` | [ ] |
| | | `observation_daily.parquet` | Ada di `data/raw/rainfall/` | [ ] |
| | | SPI Harian, Dasarian, Bulanan | Parquet lengkap di `data/raw/spi/` | [ ] |
| **4** | **Jaringan Stasiun Master** | Metadata 57 Stasiun | `data/reference/stations/station_metadata.parquet` | [ ] |
| | | Sebaran 7 Kabupaten/Kota | Batam, Bintan, Karimun, Lingga, Natuna, Anambas, Tanjungpinang | [ ] |
| **5** | **Aset Spasial & Batas** | Shapefile Batas KEPRI | `data/reference/PETA/KEPRI.shp` & kelengkapannya | [ ] |
| | | Batas Kabupaten/Kota | `data/reference/boundaries/kepri_kabkot.geojson` | [ ] |
| | | Batas Zona Musim (ZOM) | `data/reference/boundaries/kepri_zom.geojson` | [ ] |
| **6** | **Template Resmi BMKG** | Template PDKM | `04. Peta PDKM_Agustus II 26.jpg` di `map_templates/` | [ ] |
| | | Template PDCHT | `01. Peta Lampiran PDCI_Das II Jan 25.jpg` di `map_templates/` | [ ] |
| **7** | **Decision Engine** | Algoritma PDKM | HTH ≥ 21 hari + SPI-30d ≤ -1.0 + Prob ≤ 30% | [ ] |
| | | Algoritma PDCHT | Curah Hujan Dasarian > 150/200/300 mm + Prob > 70% | [ ] |
| | | Aturan Multi-Hazard | Evaluasi independen tanpa konflik status | [ ] |
| **8** | **Generator Peta Resmi** | Pilihan Moda Single-Hazard | Tab terpisah PDKM dan PDCHT pada `OfficialMapModal.jsx` | [ ] |
| | | Resolusi & Pewarnaan Poligon | 300 DPI, pewarnaan presisi berbasis shapefile administrasi | [ ] |
| **9** | **Ekspor JSON SIH3** | Struktur Schema JSON | 7 Kabupaten/Kota dengan rincian kecamatan, zom, rekomendasi | [ ] |
| | | File Pointer Terkini | Terupdate ke `data/output/sih3/sih3_regional_warning_latest.json` | [ ] |
| **10**| **UI Navigation Invariant**| 3 Tab Menu Utama | Hanya ada menu `Peringatan Dini`, `Data`, dan `Kamus` | [ ] |

---

## 3. PROSEDUR OPERASIONAL STANDAR (SOP) EKSEKUSI

### Langkah 1: Pemeriksaan Otomatis (Pre-Flight Script)
Jalankan script verifikasi mandiri sebelum memulai aplikasi:
```bash
python scripts/audit_pre_cleanup.py
```
*Pastikan seluruh file kanonikal berstatus `[OK]` dan row count basis data sesuai standar.*

### Langkah 2: Menjalankan Sistem DSS-PIK
Gunakan launcher resmi DSS-PIK untuk memulai seluruh layanan:
```bash
python -m backend.launcher start
```
*Perintah ini secara otomatis:*
1. Memeriksa ketersediaan port dan membersihkan proses zombie yang menggantung.
2. Memverifikasi konektivitas basis data MariaDB.
3. Menjalankan Backend FastAPI pada `http://127.0.0.1:8000`.
4. Menjalankan Frontend Vite pada `http://127.0.0.1:5173`.
5. Membuka dashboard Web GIS pada browser default.

### Langkah 3: Pemeriksaan Status Layanan
Untuk memastikan kedua layanan berstatus sehat:
```bash
python -m backend.launcher status
```

### Langkah 4: Pengujian Regresi Cepat (Opsional / Berkala)
Untuk memastikan seluruh fungsi generator peta dan kalkulasi warning tidak mengalami regresi:
```bash
pytest tests/integration/test_official_map_modal_and_sih3_export.py -v
```

### Langkah 5: Penghentian Layanan yang Aman (Graceful Shutdown)
Setelah operasional selesai:
```bash
python -m backend.launcher stop
```

---

## 4. PENANGANAN ANOMALI (TROUBLESHOOTING)

| Gejala Kendala | Kemungkinan Penyebab | Tindakan Penyelesaian |
| :--- | :--- | :--- |
| **Frontend berhenti dengan exit code 1 / Port 5173 in use** | Ada proses Node/Vite sebelumnya yang masih mengunci port. | Jalankan `python -m backend.launcher stop` kemudian `python -m backend.launcher start`. Launcher otomatis membunuh tree process pada port tersebut. |
| **Backend gagal terhubung ke MariaDB** | Service MariaDB belum berjalan pada port 3306. | Pastikan `mariadbd.exe` aktif. Cek dengan `tasklist \| findstr mariadbd`. |
| **Pewarnaan poligon peta tidak muncul** | File shapefile `KEPRI.shp` tergeser atau tidak terbaca oleh Cartopy/GeoPandas. | Pastikan 4 file shapefile (`.shp`, `.shx`, `.dbf`, `.prj`) ada di `data/reference/PETA/`. |
| **Peta PDKM/PDCHT tertukar template** | Parameter `hazard_type` tidak sesuai saat generate. | Pastikan memilih jenis peta yang benar (PDKM untuk kekeringan, PDCHT untuk curah hujan tinggi) pada modal generator. |

