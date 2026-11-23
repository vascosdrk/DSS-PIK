# CLIMATE EARLY WARNING SYSTEM (CEWS) - SYSTEM DOCUMENTATION
**Status**: Development / Data Preparation Phase
**Base Concept**: Peraturan BMKG Nomor 9 Tahun 2019 tentang Penyediaan dan Penyebaran Peringatan Dini Iklim

Dokumen ini adalah rangkuman lengkap arsitektur data, konsep indikator, dan rincian teknis dari semua dataset yang telah dipersiapkan untuk modul *Decision Engine* CEWS.

---

## 1. ARSITEKTUR METADATA & SPASIAL (CORE)
Sebagai fondasi dari seluruh sistem CEWS, resolusi lokasi stasiun dilakukan untuk memastikan setiap data dari sumber yang berbeda dapat disatukan (di-*merge*) secara akurat.

*   **`station_metadata.parquet`**: Master metadata stasiun hujan yang valid. Menyimpan `station_id` (sebagai primary key), nama stasiun, latitude, longitude, dan hierarki wilayah (Provinsi/Kabupaten).
*   **`mapping_tambahan.xlsx`**: *Lookup table* untuk stasiun-stasiun yang format penulisan namanya berbeda di file *raw* (misal: "Stasiun Meteorologi RHF" -> "21720201a").
*   **Mekanisme Mapping (3-Level Resolution)**:
    1.  **Exact Match**: Pencocokan langsung dengan `station_id`.
    2.  **Reference Match**: Pencocokan string nama stasiun menggunakan variasi di `mapping_tambahan.xlsx`.
    3.  **Spatial Haversine Match**: Pencocokan berbasis koordinat (Latitude/Longitude) jika jarak antar stasiun < 1 km (*Spatial Match*), atau > 1 km (*Spatial Warning*).

---

## 2. DATABASE UTAMA (RAINFALL)
**Dataset**: `cews_integrated_2021_2025.parquet`

**Konsep**: 
Menyimpan data observasi curah hujan harian dari stasiun-stasiun pengamatan. Database ini telah digabungkan dengan master metadata sehingga memiliki dimensi spasial yang lengkap.

**Komponen Teknis**:
*   **Granularitas**: Harian per Stasiun.
*   **Field Utama**: `date`, `station_id`, `rainfall` (curah hujan harian dalam mm), `province`, `kabupaten`, `latitude`, `longitude`.

---

## 3. INDIKATOR HARI TANPA HUJAN (HTH)
**Dataset**: 
1. `hth_daily_2021_2025.parquet` (Daily Tracking)
2. `hth_monthly_snapshot_2021_2025.parquet` (Monthly Aggregation)

**Konsep (BMKG No. 9 / 2019)**: 
Peringatan Dini Kekeringan Meteorologis ditetapkan salah satunya berdasarkan deret Hari Tanpa Hujan (HTH). Hari tanpa hujan didefinisikan sebagai curah hujan < 1.0 mm/hari berturut-turut.

**Komponen Teknis**:
*   *Algorithm*: Mendeteksi deret consecutive (*streak*) nilai *rainfall* < 1 mm menggunakan validasi berbasis *shift* di Pandas. Nilai deret di-reset menjadi 0 saat curah hujan >= 1 mm.
*   **Field Utama (Daily)**: `current_streak` (jumlah hari tanpa hujan pada tanggal tersebut), `kriteria_hth` (kategorisasi HTH seperti "Sangat Pendek", "Menengah", "Ekstrem", dsb.).

---

## 4. STANDARDIZED PRECIPITATION INDEX (SPI)
**Dataset**: `spi_cews_2021_2025.parquet`

**Konsep (BMKG No. 9 / 2019)**:
SPI digunakan untuk menentukan tingkat keparahan kekeringan meteorologis. Merupakan indeks deviasi dari curah hujan rata-rata jangka panjang. 

**Komponen Teknis**:
*   **Granularitas**: Bulanan per Stasiun.
*   **Field Utama**: `target_year`, `target_month`, `spi_1`, `spi_3`, dll. (Tergantung rentang akumulasi bulan).
*   **Integrasi**: SPI digunakan bersama dengan HTH dan Probabilitas Hujan untuk mengeluarkan *Alert* Kekeringan gabungan di tingkat dasarian atau bulanan.

---

## 5. PROBABILITAS CURAH HUJAN DASARIAN
**Dataset**: `probability_rainfall_dasarian_2025.parquet`

**Konsep (BMKG No. 9 / 2019)**:
Data prediksi (berbasis luaran model misal ECMWF) mengenai peluang curah hujan akan berada di bawah (BELOW) atau di atas (ABOVE) ambang batas tertentu pada periode dasarian (10 harian).

**Komponen Teknis**:
*   **Granularitas**: Dasarian (1, 2, 3) per Stasiun per Bulan.
*   **Threshold (BELOW)**: 50mm (Indikator Kekeringan).
*   **Threshold (ABOVE)**: 50mm, 150mm, 200mm, 300mm (Indikator Hujan Lebat).
*   **Indikator Turunan**: 
    *   `dasarian_dryness_indicator` (True jika prob BELOW 50mm > 70%).
    *   `dasarian_heavy_rain_indicator` (True jika prob ABOVE >150mm > 70%).

---

## 6. PROBABILITAS CURAH HUJAN BULANAN
**Dataset**: `probability_rainfall_monthly_2021_2025.parquet`

**Konsep (BMKG No. 9 / 2019)**:
Sama dengan probabilitas dasarian, namun direpresentasikan sebagai prospek iklim bulanan. Digunakan sebagai *outlook* potensi kekeringan maupun banjir jangka menengah.

**Komponen Teknis**:
*   **Granularitas**: Bulanan per Stasiun.
*   **Threshold (BELOW)**: 50mm, 100mm, 150mm.
*   **Threshold (ABOVE)**: 50mm, 100mm, 150mm, 200mm, 300mm, 400mm, 500mm.
*   **Indikator Turunan**: 
    *   `monthly_dryness_indicator` (True jika prob BELOW threshold tertentu > 70%).
    *   `monthly_heavy_rain_indicator` (True jika prob ABOVE threshold tertentu > 70%).

---

## 7. CEWS DECISION ENGINE (TAHAP BERIKUTNYA)
Semua dataset di atas siap digabungkan (*joined*) di tingkat Stasiun, Bulan, atau Dasarian untuk engine pengambil keputusan (Decision Engine). 

**Aturan Keputusan Gabungan (Contoh Penerapan):**
*   **Awas Kekeringan**: Jika HTH > 60 Hari (Ekstrem) **DAN** Probabilitas Dasarian Curah Hujan < 50mm adalah > 70%.
*   **Waspada Curah Hujan Tinggi**: Jika SPI menunjukkan kondisi basah **DAN** Probabilitas Dasarian/Bulanan Curah Hujan Lebat (ABOVE) adalah > 70%.
