# Panduan Operasional Petugas: Generator Peta Resmi BMKG, Batas Administratif SHP & ZOM, serta Ekspor JSON Terstandarisasi
**Sistem:** Decision Support System Peringatan Iklim Kepulauan Riau (DSS-PIK)  
**Institusi:** BMKG Stasiun Meteorologi Kelas II Raja Haji Fisabilillah Tanjungpinang  
**Status Operasional:** Final Refinement — Single Modal, Pemulihan Peta Terpisah PDKM & PDCHT Berbasis SHP Administratif, Integrasi ZOM, dan Ekspor JSON

---

## 1. Prinsip Utama & Arsitektur Tunggal

Sesuai arahan operasional BMKG Stasiun Meteorologi Kelas II Raja Haji Fisabilillah Tanjungpinang, DSS-PIK **TIDAK** menambah menu navigasi baru atau memulihkan halaman terpisah. Seluruh alur penetapan keputusan peringatan wilayah, pembuatan peta resmi (PDKM dan PDCHT terpisah dalam format JPG A4 Landscape), dan ekspor data JSON terpusat pada satu modal operasional:

$$\boxed{\textbf{Generator Peta Resmi BMKG \& Ekspor JSON (OfficialMapModal)}}$$

### Struktur Navigasi Utama Aplikasi (Tepat 3 Menu Konsisten)
Navigasi utama DSS-PIK pada bilah header aplikasi secara ketat menyajikan tepat 3 menu utama:
1. **Peringatan Dini** (`Dashboard`): Peta Leaflet interaktif dengan layer administratif dan 14 poligon ZOM, tabel HTH, indikator stasiun, dan KPI operasional.
2. **Data** (`Data Center`): Monitoring data curah hujan harian, tabel SPI multi-skala, dan probabilitas prakiraan iklim.
3. **Kamus** (`Kamus Istilah`): Glosarium istilah meteorologi, kriteria ambang batas, dan ketentuan regulasi iklim BMKG.

---

## 2. Alur Kerja Petugas Setiap Dasarian

### Langkah 1 — Membuka Modal Generator Peta Resmi
1. Pada menu utama **Peringatan Dini**, periksa periode dasarian aktif pada bar kontrol operasional (misalnya `Dasarian II September 2026 (2026-09-das2)`).
2. Klik tombol **`Peta Resmi`** pada panel header operasional.
3. Jendela modal **Generator Peta Resmi & Ekspor JSON — BMKG** akan terbuka.

### Langkah 2 — Evaluasi 7 Kabupaten/Kota dalam Satu Daftar Terpadu
Sistem menampilkan seluruh **7 kabupaten/kota** Kepulauan Riau dalam satu daftar tunggal tanpa tab pemisah atau *scope selector* global:
- **Kabupaten Bintan** (Kode BPS: 21.01)
- **Kabupaten Karimun** (Kode BPS: 21.02)
- **Kabupaten Natuna** (Kode BPS: 21.03)
- **Kabupaten Lingga** (Kode BPS: 21.04)
- **Kabupaten Kepulauan Anambas** (Kode BPS: 21.05)
- **Kota Batam** (Kode BPS: 21.71)
- **Kota Tanjungpinang** (Kode BPS: 21.72)

Setiap kartu wilayah menyajikan informasi pendukung keputusan:
- **Cakupan Pos Hujan**: Jumlah pos valid vs total stasiun, serta persentase ketersediaan data.
- **Rekomendasi DSS-PIK**: Rekomendasi objektif Decision Engine untuk ancaman PDKM (Kekeringan) dan PDCHT (Curah Hujan Tinggi).
- **Indikator Pemicu**: Daftar stasiun dan kondisi pemicu (HTH, SPI-30, probabilitas curah hujan dasarian/bulanan).

### Langkah 3 — Penetapan Jenis Peringatan dan Tingkat Klasifikasi per Wilayah
Petugas menentukan status pada masing-masing kartu wilayah secara independen:
1. **Pilih Jenis Peringatan (`warning_type`)**:
   - `PDKM (Kekeringan)`: Mengaktifkan ancaman kekeringan meteorologis.
   - `PDCHT (Curah Hujan Tinggi)`: Mengaktifkan ancaman curah hujan tinggi / banjir.
   - `Tidak Ada Peringatan (AMAN)`: Menandakan kondisi aman atau data kurang.
2. **Tentukan Tingkat Klasifikasi (`final_level`)**:
   - Jika memilih `PDKM` atau `PDCHT`: Pilih dari dropdown tingkat bahaya: `WASPADA`, `SIAGA`, atau `AWAS`.
   - Jika memilih `Tidak Ada Peringatan (AMAN)`: Tingkat klasifikasi otomatis terkunci pada `AMAN` (atau `DATA KURANG` jika cakupan data $< 50\%$).
3. **Terapkan Rekomendasi Otomatis (Opsional)**:
   - Klik tombol **`Terapkan Rekomendasi DSS`** pada bilah asisten di bagian atas untuk mengisi rekomendasi objektif engine ke seluruh 7 wilayah secara otomatis.
4. **Honest Data Sufficiency**: Apabila suatu wilayah memiliki data $< 50\%$ dan tidak ada pos yang memicu peringatan, sistem secara tegas menetapkan status **`INSUFFICIENT_DATA`** (abu-abu/putih pada peta), dan **tidak pernah** mengubahnya secara sepihak menjadi `AMAN` (mencegah *False Green*).

### Langkah 4 — Penyesuaian Manual / Override Petugas (Human-in-the-Loop)
1. Apabila petugas memiliki pertimbangan sinoptik regional, analisis citra radar Hang Nadim, atau laporan observasi BPBD/lapangan, petugas berwenang menetapkan status berbeda dari rekomendasi DSS-PIK.
2. Begitu pilihan petugas berbeda dari rekomendasi DSS, sistem secara otomatis:
   - Menampilkan badge oranye **`Override Manual`**.
   - Membuka kolom isian **`Alasan Penyesuaian`** (wajib diisi minimal 5 karakter, misalnya: *"Pertumbuhan awan konvektif terpantau signifikan di radar Hang Nadim"*).
3. Tombol ekspor dan generasi peta dinonaktifkan sementara sampai alasan penyesuaian yang valid telah diisi.

---

## 3. Tiga Tombol Keluaran Utama (Keluaran Peringatan Dini)

Di bagian bawah daftar 7 wilayah, tersedia panel aksi **Keluaran Peringatan Dini** dengan tiga tombol utama:

```
[ Peta PDKM (JPG) ]      [ Peta PDCHT (JPG) ]      [ Ekspor JSON ]
```

### Keluaran 1 — Peta Peringatan Dini Kekeringan Meteorologis / PDKM (Format JPG)
1. Klik tombol **`Peta PDKM (JPG)`**.
2. Sistem me-render peta resmi menggunakan **template resmi lama PDKM BMKG** (`04. Peta PDKM_Agustus II 26.jpg`) berukuran A4 Landscape (1653 $\times$ 1170 piksel pada 150 DPI):
   - **Judul Resmi**: `PETA PERINGATAN DINI / KEKERINGAN METEOROLOGIS`.
   - **Visual Bersih**: Tanpa badge callout buatan; pewarnaan poligon pulau mengikuti batas administrasi kabupaten/kota.
   - **Aturan Pewarnaan PDKM**:
     - Wilayah berstatus PDKM `WASPADA` diberi warna Kuning (`#FFFF00`).
     - Wilayah berstatus PDKM `SIAGA` diberi warna Oranye (`#FFA500`).
     - Wilayah berstatus PDKM `AWAS` diberi warna Merah (`#FF0000`).
     - Wilayah yang tidak berstatus PDKM (termasuk yang berstatus PDCHT atau AMAN) diberi warna Hijau (`#33FF00`) sebagai kategori Aman / Tidak Ada Peringatan Kekeringan.
     - Wilayah dengan data kurang diberi warna Putih (`#FFFFFF`).
   - **Presisi Batas Wilayah**: Menggunakan rasterisasi poligon resmi `KEPRI.shp` / `kepri_kabkot.geojson`. Pemisahan antara Kabupaten Bintan dan Kota Tanjungpinang strictly mengikuti batas resmi tanpa kebocoran warna (*zero bleed*).

### Keluaran 2 — Peta Peringatan Dini Curah Hujan Tinggi / PDCHT (Format JPG)
1. Klik tombol **`Peta PDCHT (JPG)`**.
2. Sistem me-render peta resmi menggunakan **template resmi lama PDCHT BMKG** (`01. Peta Lampiran PDCI_Das II Jan 25.jpg`) berukuran A4 Landscape (1653 $\times$ 1170 piksel pada 150 DPI):
   - **Judul Resmi**: `PETA PERINGATAN DINI / CURAH HUJAN TINGGI`.
   - **Visual Bersih**: Tanpa badge callout buatan; pewarnaan poligon pulau mengikuti batas administrasi kabupaten/kota.
   - **Aturan Pewarnaan PDCHT**:
     - Wilayah berstatus PDCHT `WASPADA` diberi warna Kuning (`#FFFF00`).
     - Wilayah berstatus PDCHT `SIAGA` diberi warna Oranye (`#FFA500`).
     - Wilayah berstatus PDCHT `AWAS` diberi warna Merah (`#FF0000`).
     - Wilayah yang tidak berstatus PDCHT (termasuk yang berstatus PDKM atau AMAN) diberi warna Hijau (`#33FF00`) sebagai kategori Aman / Tidak Ada Peringatan Curah Hujan Tinggi.
     - Wilayah dengan data kurang diberi warna Putih (`#FFFFFF`).

### Keluaran 3 — Ekspor Data Terstandarisasi (Format JSON)
1. Klik tombol **`Ekspor JSON`**.
2. Dokumen JSON terstandarisasi dibentuk dan divalidasi terhadap skema resmi `docs/schemas/sih3_regional_warning.schema.json`.
3. Modal pratinjau JSON terbuka menyajikan:
   - Status validasi: `✓ Valid (Skema Peringatan Dini v1.0.0)`.
   - Ringkasan metrik: 7 wilayah, jumlah PDKM aktif, PDCHT aktif, aman, data kurang.
   - Tombol **`Salin JSON`**: Menyalin payload JSON ke clipboard.
   - Tombol **`Unduh Berkas JSON`**: Mengunduh file `PERINGATAN_DINI_KEPRI_{period_id}_{timestamp}.json`.
4. **Struktur Data Terstandarisasi**:
   - `triggered_conditions`: Memuat objek indikator terstruktur `{indicator, value, unit, operator, threshold, period, station_code, station_name}`.
   - `operator_decision`: Memuat status keputusan final, timestamp, petugas, dan `override_reason`.
   - Dokumen contoh tersedia di direktori `docs/schemas/examples/`.

---

## 4. Integrasi Spasial SHP Administratif & Zona Musim (ZOM)

### Lapisan Spasial pada Peta Interaktif Dashboard
Peta Leaflet pada dashboard utama menyajikan layer kontrol:
- **Layer Batas Kabupaten/Kota** (`data/reference/boundaries/kepri_kabkot.geojson`): 7 poligon kabupaten/kota dengan warna status dinamis.
- **Layer Batas Kecamatan** (`data/reference/boundaries/kepri_kecamatan.geojson`): 59 batas kecamatan.
- **Layer Zona Musim (ZOM)** (`data/reference/boundaries/kepri_zom.geojson`): 14 poligon ZOM Provinsi Kepulauan Riau (Kepri_01 s/d Kepri_14).

### Hasil Spatial Join 57 Pos Hujan Master terhadap Poligon ZOM
Endpoint `GET /api/v1/geo/zom-analysis` melakukan *point-in-polygon spatial join*:
- **56 stasiun** jatuh tepat di dalam poligon ZOM resmi.
- **1 stasiun** yaitu **Stamet Tarempa** (`21050101A` / Koordinat: 106.2167°BT, 3.2167°LU) berada pada titik pulau kecil di luar poligon ZOM yang telah disederhanakan.
- **Aturan Integritas Data**: Sistem secara jujur melaporkan status Stamet Tarempa sebagai `"Belum terpetakan / Tidak masuk poligon ZOM"` dengan catatan fallback resmi ke `KEPRI_12`, tanpa memanipulasi koordinat stasiun atau geometri referensi BMKG.

---

## 5. Matriks Ringkasan Skenario Verifikasi Operasional

| Skenario | Kondisi Keputusan Petugas | Output Peta PDKM (JPG) | Output Peta PDCHT (JPG) | Dokumen JSON |
| :---: | :--- | :--- | :--- | :--- |
| **A** | PDKM aktif di Bintan (WASPADA), Natuna (SIAGA), Anambas (AWAS); lainnya AMAN. | Bintan Kuning, Natuna Oranye, Anambas Merah; lainnya Hijau. Template PDKM resmi. | Seluruh 7 wilayah Hijau (Aman / Tidak ada peringatan PDCHT). Template PDCHT resmi. | Valid. PDKM aktif pada 3 wilayah. `warnings` berisi 3 entri PDKM. |
| **B** | PDCHT aktif di Bintan (SIAGA), Natuna (AWAS), Lingga (WASPADA); lainnya AMAN. | Seluruh 7 wilayah Hijau (Aman / Tidak ada peringatan PDKM). Template PDKM resmi. | Bintan Oranye, Natuna Merah, Lingga Kuning; lainnya Hijau. Template PDCHT resmi. | Valid. PDCHT aktif pada 3 wilayah. `warnings` berisi 3 entri PDCHT. |
| **C** | Silang Wilayah: Bintan (PDKM WASPADA), Natuna (PDCHT SIAGA), Lingga (PDKM SIAGA), Anambas (PDCHT AWAS). | Bintan Kuning, Lingga Oranye; Natuna & Anambas Hijau; lainnya Hijau. | Natuna Oranye, Anambas Merah; Bintan & Lingga Hijau; lainnya Hijau. | Valid. Memuat rincian PDKM dan PDCHT pada wilayah masing-masing secara independen. |
| **D** | Seluruh 7 kabupaten/kota berstatus AMAN. | Seluruh 7 wilayah Hijau (`#33FF00`). | Seluruh 7 wilayah Hijau (`#33FF00`). | Valid. `warnings: []`. Status tiap wilayah AMAN. |
| **E** | Wilayah data kurang ($<50\%$ valid stasiun, misal Lingga) tanpa stasiun pemicu. | Lingga Putih (`#FFFFFF` / Data Kurang); lainnya sesuai status. | Lingga Putih (`#FFFFFF` / Data Kurang); lainnya sesuai status. | Valid. `data_status: INSUFFICIENT_DATA`. Pencegahan *False Green*. |

---
*Dokumen ini merupakan Standar Operasional Prosedur resmi bagi Forecaster dan Teknisi Data BMKG Stasiun Meteorologi Kelas II Raja Haji Fisabilillah Tanjungpinang dalam mengoperasikan DSS-PIK.*
