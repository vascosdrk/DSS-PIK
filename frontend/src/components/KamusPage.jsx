import React, { useState, useMemo } from 'react';
import { INSTITUTION_SHORT_NAME } from '../config';
import { 
  BookOpen, 
  Search, 
  HelpCircle, 
  ChevronDown, 
  ChevronUp,
  AlertTriangle,
  Flame,
  ShieldCheck,
  Droplets,
  CloudRain,
  Activity,
  Layers,
  Info
} from 'lucide-react';

export default function KamusPage() {
  const [searchQuery, setSearchQuery] = useState('');
  const [activeGroupFilter, setActiveGroupFilter] = useState('ALL'); // 'ALL' | 'UMUM' | 'OPERASIONAL'
  const [expandedItems, setExpandedItems] = useState({});

  // Only two main groups: "Istilah Umum" & "Operasional DSS-PIK"
  const glossaryItems = [
    // =========================================================================
    // 1. ISTILAH UMUM
    // =========================================================================
    {
      id: 'curah-hujan',
      group: 'UMUM',
      groupLabel: 'Istilah Umum',
      term: 'Curah Hujan (CH)',
      shortDesc: 'Ketinggian air hujan yang terkumpul dalam satuan milimeter (mm).',
      content: 'Curah hujan adalah ketebalan lapisan air yang jatuh di atas permukaan tanah datar seluas 1 meter persegi dengan asumsi tidak terjadi penguapan (evaporasi), peresapan (infiltrasi), maupun pengaliran (limpasan). 1 milimeter (mm) curah hujan setara dengan 1 liter air pada luasan 1 meter persegi. BMKG mengklasifikasikan intensitas curah hujan harian menjadi: Berawan/Kering (0.0 mm), Hujan Sangat Ringan (< 5 mm/hari), Hujan Ringan (5–20 mm/hari), Hujan Sedang (20–50 mm/hari), Hujan Lebat (50–100 mm/hari), Hujan Sangat Lebat (100–150 mm/hari), dan Hujan Ekstrem (> 150 mm/hari).'
    },
    {
      id: 'dasarian',
      group: 'UMUM',
      groupLabel: 'Istilah Umum',
      term: 'Dasarian',
      shortDesc: 'Satuan periode waktu klimatologis berdurasi 10 hari.',
      content: 'Dalam satu bulan kalender terbagi menjadi 3 dasarian: Dasarian I (tanggal 1–10), Dasarian II (tanggal 11–20), dan Dasarian III (tanggal 21 hingga hari terakhir bulan, yaitu 28/29, 30, atau 31). Dasarian merupakan satuan waktu standar analisis dan prakiraan iklim operasional BMKG di seluruh Indonesia.'
    },
    {
      id: 'hth-umum',
      group: 'UMUM',
      groupLabel: 'Istilah Umum',
      term: 'Hari Tanpa Hujan (HTH)',
      shortDesc: 'Jumlah hari berturut-turut di mana tidak terjadi hujan atau curah hujan < 1.0 mm.',
      content: 'Hari Tanpa Hujan (HTH) adalah indikator empiris untuk memantau durasi periode kering. Hari dengan curah hujan < 1.0 mm (termasuk 0.0 mm dan TTU) dihitung sebagai hari tanpa hujan yang menambah durasi HTH. Apabila terjadi hujan terukur ≥ 1.0 mm pada suatu hari, maka deret HTH terputus dan perhitungan direset kembali menjadi 0 hari pada hari berikutnya.'
    },
    {
      id: 'spi-umum',
      group: 'UMUM',
      groupLabel: 'Istilah Umum',
      term: 'Standardized Precipitation Index (SPI)',
      shortDesc: 'Indeks standar deviasi anomali curah hujan relatif terhadap distribusi historis jangka panjang.',
      content: 'SPI adalah indeks meteorologi probabilitas yang dikembangkan oleh McKee et al. (1993) dan direkomendasikan oleh World Meteorological Organization (WMO) untuk pemantauan kekeringan. Nilai SPI merefleksikan deviasi standar surplus atau defisit curah hujan terhadap rata-rata historis (berbasis distribusi gamma). Nilai SPI negatif menunjukkan kondisi lebih kering dari normal klimatologis, sedangkan nilai positif menunjukkan kondisi lebih basah dari normal. BMKG mengklasifikasikan SPI: Amat Sangat Basah (SPI > 2.00), Sangat Basah (1.50 s.d. 2.00), Basah (1.00 s.d. 1.49), Normal (-0.99 s.d. 0.99), Agak Kering (-1.49 s.d. -1.00), Sangat Kering (-1.99 s.d. -1.50), dan Amat Sangat Kering (SPI <= -2.00).'
    },
    {
      id: 'probabilitas-prakiraan',
      group: 'UMUM',
      groupLabel: 'Istilah Umum',
      term: 'Probabilitas Prakiraan Curah Hujan',
      shortDesc: 'Peluang kejadian curah hujan melampaui atau berada di bawah ambang batas tertentu (0–100%).',
      content: 'Prakiraan berbasis ensemble numerik ECMWF (European Centre for Medium-Range Weather Forecasts) yang menghasilkan peluang persentase (0% hingga 100%) untuk berbagai ambang batas akumulasi hujan, baik resolusi dasarian (pb20, pa150, pa200, pa300) maupun akumulasi bulanan (>300 mm, >400 mm, >500 mm). Skala probabilitas ini digunakan sebagai faktor pemicu objektif pada Decision Engine.'
    },
    {
      id: 'observasi-prakiraan',
      group: 'UMUM',
      groupLabel: 'Istilah Umum',
      term: 'Observasi vs Prakiraan Iklim',
      shortDesc: 'Perbedaan mendasar antara data faktual terukur dan estimasi model numerik masa depan.',
      content: 'Data Observasi adalah data fisik curah hujan terukur dari penakar hujan di permukaan tanah (pos manual atau ARG) yang telah berlangsung hingga tanggal cutoff. Data Prakiraan adalah hasil pemodelan atmosfer numerik untuk periode masa depan yang belum terjadi (misalnya dasarian berikutnya). DSS-PIK menggabungkan data observasi terkini dengan prakiraan probabilistik untuk menghasilkan peringatan dini yang akurat.'
    },
    {
      id: 'pos-manual-arg',
      group: 'UMUM',
      groupLabel: 'Istilah Umum',
      term: 'Pos Hujan Manual vs Stasiun ARG',
      shortDesc: 'Dua tipe instrumen pemantauan curah hujan di wilayah Kepulauan Riau.',
      content: 'Pos Hujan Manual (52 pos) menggunakan penakar tipe Observatorium (OBS) berdiameter corong 100 cm² yang dicatat secara manual setiap pukul 07.00 WS oleh pengamat pos kerja sama BMKG. Stasiun Automatic Rain Gauge / ARG (5 stasiun) menggunakan sensor tipping-bucket digital otomatis yang mengirimkan data via telemetri seluler/satelit. Stasiun ARG baru yang belum memiliki rekam jejak panjang dievaluasi secara khusus untuk menjaga integritas ilmiah.'
    },
    {
      id: 'zom-kepri',
      group: 'UMUM',
      groupLabel: 'Istilah Umum',
      term: 'Zona Musim (ZOM)',
      shortDesc: 'Wilayah yang memiliki pola curah hujan dengan batas yang jelas antara periode basah dan kering.',
      content: 'BMKG menetapkan Zona Musim (ZOM) berdasarkan pola distribusi curah hujan rata-rata 30 tahun. Wilayah Kepulauan Riau sebagian besar tergolong wilayah Ekuatorial / Non-ZOM dengan pola hujan dwipuncak (bimodal) yang dipengaruhi oleh angin monsun, monsun barat, monsun timur, dan konvergensi antar-tropis (ITCZ).'
    },

    // =========================================================================
    // =========================================================================
    // 2. OPERASIONAL DSS-PIK
    // =========================================================================
    {
      id: 'pdkm-definisi',
      group: 'OPERASIONAL',
      groupLabel: 'Operasional DSS-PIK',
      term: 'PDKM (Peringatan Dini Kekeringan Meteorologis)',
      shortDesc: 'Sistem peringatan dini potensi kekeringan meteorologis berbasis evaluasi independen 3 indikator: HTH, Probabilitas CH Rendah (pb20), dan SPI 30D.',
      content: 'PDKM mendeteksi potensi kelangkaan air dan kekeringan meteorologis di Kepulauan Riau dengan mengevaluasi tiga indikator utama secara independen:\n' +
        '1. Hari Tanpa Hujan (HTH) dari observasi harian terkini.\n' +
        '2. Probabilitas Curah Hujan Rendah (pb20: peluang CH dasarian < 20 mm) dari ensemble ECMWF.\n' +
        '3. Standardized Precipitation Index 30 Hari (SPI 30D Dasarian) sebagai acuan akumulasi defisit curah hujan.\n\n' +
        'Status akhir PDKM dihitung dengan prinsip kewaspadaan tertinggi: status_pdkm = max(level_hth, level_prob, level_spi).'
    },
    {
      id: 'pdkm-aturan',
      group: 'OPERASIONAL',
      groupLabel: 'Operasional DSS-PIK',
      term: 'Aturan Evaluasi Independen & Ambang Batas PDKM',
      shortDesc: 'Ambang batas objektif untuk HTH, Probabilitas CH Rendah, SPI 30D, serta formula penggabungan status_pdkm.',
      content: 'Setiap indikator kekeringan dievaluasi secara mandiri (independen) tanpa saling mengunci:\n\n' +
        '• Indikator 1: Hari Tanpa Hujan (HTH)\n' +
        '  - HTH >= 61 hari → AWAS (Level 3, Merah)\n' +
        '  - 31 <= HTH < 61 hari → SIAGA (Level 2, Oranye)\n' +
        '  - 21 <= HTH < 31 hari → WASPADA (Level 1, Kuning)\n' +
        '  - HTH < 21 hari → HIJAU / NORMAL (Level 0, Aman)\n\n' +
        '• Indikator 2: Probabilitas Curah Hujan Rendah (pb20)\n' +
        '  - Jika forecast CH dasarian < 20 mm dan peluang > 70% (pb20 > 70.0%) → WASPADA (Level 1, Kuning)\n' +
        '  - Selain itu (pb20 <= 70.0%) → HIJAU / NORMAL (Level 0, Aman)\n' +
        '  * Catatan: Probabilitas rendah semata dibatasi maksimum menghasilkan status WASPADA (tidak boleh langsung memicu SIAGA/AWAS tanpa data observasi).\n\n' +
        '• Indikator 3: Standardized Precipitation Index (SPI 30D - Acuan Otoritatif)\n' +
        '  - SPI <= -2.00 → AWAS (Level 3, Kekeringan Ekstrem)\n' +
        '  - -2.00 < SPI <= -1.50 → SIAGA (Level 2, Kekeringan Sangat Parah)\n' +
        '  - -1.50 < SPI <= -1.00 → WASPADA (Level 1, Kekeringan Sedang)\n' +
        '  - SPI > -1.00 → HIJAU / NORMAL (Level 0, Normal / Basah)\n\n' +
        '• Penggabungan Status PDKM:\n' +
        '  status_pdkm = max(level_hth, level_prob, level_spi)\n' +
        '  Sistem menyimpan seluruh pemicu aktif yang terbukti melampaui ambang batas, bukan hanya pemicu tertinggi.'
    },
    {
      id: 'pdcht-definisi',
      group: 'OPERASIONAL',
      groupLabel: 'Operasional DSS-PIK',
      term: 'PDCHT (Peringatan Dini Curah Hujan Tinggi)',
      shortDesc: 'Sistem peringatan dini potensi curah hujan lebat dan ekstrem berbasis probabilitas ECMWF dasarian dan bulanan.',
      content: 'PDCHT mendeteksi potensi curah hujan ekstrem yang berisiko menimbulkan bencana hidrometeorologis basah (banjir, tanah longsor, genangan air). Evaluasi dilakukan secara independen terhadap dua skala waktu: prakiraan probabilitas dasarian (pa150, pa200, pa300) dan prakiraan akumulasi bulanan (>300 mm, >400 mm, >500 mm). Status akhir PDCHT mengambil nilai tertinggi: status_pdcht = max(level_dasarian, level_bulanan).'
    },
    {
      id: 'pdcht-aturan',
      group: 'OPERASIONAL',
      groupLabel: 'Operasional DSS-PIK',
      term: 'Aturan Evaluasi Independen & Ambang Batas PDCHT',
      shortDesc: 'Ambang probabilitas ketat lebih dari 50% (> 50.0%) untuk probabilitas dasarian dan bulanan.',
      content: 'Setiap skala waktu PDCHT dievaluasi secara mandiri menggunakan ambang batas ketat > 50.0%:\n\n' +
        '• Skala Dasarian (Peluang Akumulasi 10 Hari):\n' +
        '  - pa300 > 50.0% (Peluang CH > 300 mm/dasarian) → AWAS (Level 3, Merah)\n' +
        '  - pa200 > 50.0% (Peluang CH > 200 mm/dasarian) → SIAGA (Level 2, Oranye)\n' +
        '  - pa150 > 50.0% (Peluang CH > 150 mm/dasarian) → WASPADA (Level 1, Kuning)\n' +
        '  - Selain itu → HIJAU / NORMAL (Level 0, Aman)\n\n' +
        '• Skala Bulanan (Peluang Akumulasi 1 Bulan):\n' +
        '  - Peluang CH Bulanan > 500 mm > 50.0% → AWAS (Level 3, Merah)\n' +
        '  - Peluang CH Bulanan > 400 mm > 50.0% → SIAGA (Level 2, Oranye)\n' +
        '  - Peluang CH Bulanan > 300 mm > 50.0% → WASPADA (Level 1, Kuning)\n' +
        '  - Selain itu → HIJAU / NORMAL (Level 0, Aman)\n\n' +
        '• Penggabungan Status PDCHT:\n' +
        '  status_pdcht = max(level_dasarian, level_bulanan)\n' +
        '  Ambang bersifat ketat (> 50.0%). Nilai persis 50.0% tidak memicu peringatan.'
    },
    {
      id: 'sintesis-status-akhir',
      group: 'OPERASIONAL',
      groupLabel: 'Operasional DSS-PIK',
      term: 'Prinsip Sintesis Status Akhir (Worst-Case Safety)',
      shortDesc: 'Penggabungan status akhir sistem: status_final = max(status_pdkm, status_pdcht) dengan atribusi hazard transparan.',
      content: 'Sintesis status akhir stasiun dan kabupaten menerapkan prinsip kehati-hatian maksimal (worst-case safety):\n\n' +
        '1. Rumus Sintesis: status_akhir = max(status_pdkm, status_pdcht)\n' +
        '2. Atribusi Tipe Ancaman (Hazard Type):\n' +
        '   • Jika status_pdkm > status_pdcht: Bahaya KEKERINGAN (DROUGHT)\n' +
        '   • Jika status_pdcht > status_pdkm: Bahaya CURAH HUJAN TINGGI (HEAVY_RAIN)\n' +
        '   • Jika status_pdkm == status_pdcht > 0: Bahaya GANDA (MULTI_HAZARD), misalnya WASPADA kekeringan sekaligus WASPADA hujan lebat\n' +
        '   • Jika keduanya Level 0: KONDISI NORMAL (NORMAL / AMAN)\n' +
        '3. Seluruh detail pemicu dari kedua instrumen tetap disimpan dan ditampilkan transparan pada panel rincian stasiun.'
    },
    {
      id: 'spi-peran-dasarian-bulanan',
      group: 'OPERASIONAL',
      groupLabel: 'Operasional DSS-PIK',
      term: 'Peran Multi-Skala SPI: Dasarian (30D/90D), Harian, dan Bulanan',
      shortDesc: 'SPI Dasarian 30D sebagai pemicu utama PDKM; 90D sebagai pendamping; Harian dan Bulanan sebagai pemantauan konteks.',
      content: 'DSS-PIK membagi peran indikator SPI secara terstruktur berdasarkan resolusi dan fungsinya:\n\n' +
        '1. SPI Dasarian 30D (Pemicu Utama PDKM):\n' +
        '   Merupakan satu-satunya instrumen SPI yang memicu status level peringatan kekeringan PDKM (Waspada, Siaga, Awas) pada Decision Engine. Merefleksikan respons cepat defisit kebasahan 30 hari terhadap distribusi historis.\n\n' +
        '2. SPI Dasarian 90D (Indikator Pendamping):\n' +
        '   Berfungsi sebagai indikator pendamping jangka menengah (3 bulan) untuk memantau tren kekeringan hidrologis. Nilai ini ditampilkan sebagai konteks dan TIDAK memicu status PDKM secara mandiri.\n\n' +
        '3. SPI Harian (30D & 90D - Monitoring Real-Time):\n' +
        '   Dihitung setiap hari dengan jendela berjalan 30 dan 90 hari berdasarkan tanggal observasi terakhir. Berfungsi memantau dinamika kebasahan harian secara langsung sebelum periode dasarian berakhir.\n\n' +
        '4. SPI Bulanan (1 Bulan - Monitoring Klimatologis):\n' +
        '   Resolusi kalender bulanan (Januari–Desember) yang digunakan untuk membandingkan anomali iklim antar-tahun dan analisis klimatologis jangka panjang wilayah Kepulauan Riau.'
    },
    {
      id: 'spi-ambang-batas-resmi',
      group: 'OPERASIONAL',
      groupLabel: 'Operasional DSS-PIK',
      term: 'Klasifikasi & Ambang Batas Resmi SPI BMKG',
      shortDesc: 'Standar deviasi anomali presipitasi BMKG dari kondisi Sangat Basah hingga Amat Sangat Kering.',
      content: 'BMKG menetapkan klasifikasi baku nilai Standardized Precipitation Index (SPI) sebagai berikut:\n\n' +
        '• SPI <= -2.00 : Amat Sangat Kering (Memicu Status AWAS pada PDKM)\n' +
        '• -1.99 s.d. -1.50 : Sangat Kering (Memicu Status SIAGA pada PDKM)\n' +
        '• -1.49 s.d. -1.00 : Agak Kering (Memicu Status WASPADA pada PDKM)\n' +
        '• -0.99 s.d. +0.99 : Normal (Kondisi Aman / Wajar)\n' +
        '• +1.00 s.d. +1.49 : Agak Basah (Indikasi Surplus Curah Hujan Ringan)\n' +
        '• +1.50 s.d. +1.99 : Sangat Basah (Surplus Curah Hujan Signifikan)\n' +
        '• SPI >= +2.00 : Amat Sangat Basah (Surplus Ekstrem)\n\n' +
        'Seluruh batas ini dievaluasi secara presisi numerik floating-point tanpa pembulatan prematur.'
    },
    {
      id: 'spi-tren-chart-panduan',
      group: 'OPERASIONAL',
      groupLabel: 'Operasional DSS-PIK',
      term: 'Panduan Membaca Grafik Tren SPI Stasiun',
      shortDesc: 'Prinsip visualisasi deret waktu SPI: garis ambang batas dan larangan interpolasi palsu atas data kosong.',
      content: 'Grafik Tren SPI pada panel stasiun dirancang dengan kaidah visualisasi data ilmiah:\n\n' +
        '1. Garis Ambang Batas:\n' +
        '   Garis horizontal putus-putus ditampilkan pada nilai -1.00 (Kuning/Waspada), -1.50 (Oranye/Siaga), dan -2.00 (Merah/Awas) sebagai acuan visual instan.\n\n' +
        '2. Pemutusan Garis pada Data Kosong (No False Interpolation):\n' +
        '   Jika terdapat tanggal observasi di mana nilai SPI bernilai null atau missing, garis grafik akan terputus (disjoint) dan TIDAK ditarik garis lurus semu di antara titik yang terpisah. Hal ini mencegah petugas menyimpulkan tren keliru dari data yang tidak ada.\n\n' +
        '3. Pilihan Skala:\n' +
        '   Petugas dapat beralih antara tampilan Dasarian (30D & 90D), Harian (30D & 90D), dan Bulanan, serta memilih rentang waktu 6, 12, atau 24 bulan terakhir.'
    },
    {
      id: 'arg-spi-kebijakan',
      group: 'OPERASIONAL',
      groupLabel: 'Operasional DSS-PIK',
      term: 'Perlakuan Stasiun ARG pada Parameter SPI',
      shortDesc: 'Konsistensi status "Tidak Tersedia (ARG)" dan evaluasi murni berbasis observasi HTH aktual.',
      content: 'Wilayah Kepulauan Riau memiliki 5 stasiun Automatic Rain Gauge (ARG): ARG Daik Lingga, ARG Dabo, ARG Ranai, ARG Bandara Tambelan, dan ARG Tembeling.\n\n' +
        '1. Nilai SPI Berstatus NULL / Strip (—):\n' +
        '   Stasiun ARG baru tidak memiliki rekam jejak observasi historis jangka panjang (minimum 20–30 tahun) yang disyaratkan untuk fitting distribusi gamma SPI. Oleh karena itu, nilai SPI untuk stasiun ARG harus berstatus NULL / Tidak Tersedia, dan DILARANG diisi nilai 0.00 atau diklasifikasikan sebagai NORMAL palsu.\n\n' +
        '2. Evaluasi Berbasis HTH Aktual:\n' +
        '   Keputusan peringatan dini untuk stasiun ARG dievaluasi secara murni berdasarkan observasi Hari Tanpa Hujan (HTH) aktual. Jika HTH >= 21 hari, stasiun ARG tetap menghasilkan peringatan dini yang valid.'
    },
    {
      id: 'ingestion-alur-operasional',
      group: 'OPERASIONAL',
      groupLabel: 'Operasional DSS-PIK',
      term: 'Alur Operasional Ingestion Data Baru',
      shortDesc: 'Prosedur pembaruan data berkala per awal dasarian: unggah, deteksi, pratinjau diff, komitmen transaksional, dan audit.',
      content: 'Pembaruan data operasional dilakukan oleh petugas BMKG setiap awal dasarian melalui modul Pusat Input Data:\n\n' +
        '1. Pemilihan Kategori atau Deteksi Otomatis:\n' +
        '   Sistem mendukung 6 format dataset: Curah Hujan Harian (.xlsx/.xls), SPI Harian (.parquet), SPI Dasarian (.parquet), SPI Bulanan (.xlsx), Probabilitas Dasarian (.xlsx), dan Probabilitas Bulanan (.xlsx).\n\n' +
        '2. Validasi & Pratinjau Diff (Dry-Run):\n' +
        '   Sebelum disimpan ke database, sistem menghitung perbandingan (diff): jumlah baris baru, baris yang ditimpa, baris identik, rentang tanggal, dan mendeteksi anomali (nilai negatif, typo kode pos, nilai probabilitas > 100%).\n\n' +
        '3. Komitmen Transaksional Atomik:\n' +
        '   Data hanya disimpan setelah operator mencantumkan nama, alasan pembaruan, dan menandai persetujuan konfirmasi. Proses penyimpanan menerapkan transaksi atomik (commit atau rollback) sehingga tidak ada data yang tersimpan setengah jalan.\n\n' +
        '4. Sinkronisasi Kesiapan Periode & Log Audit:\n' +
        '   Penyimpanan data baru secara otomatis memperbarui status kesiapan periode dasarian dan mencatat riwayat transaksi ke dalam tabel audit yang tidak dapat dihapus.'
    },
    {
      id: 'data-parsial-incomplete',
      group: 'OPERASIONAL',
      groupLabel: 'Operasional DSS-PIK',
      term: 'Perlakuan Data Parsial, Tidak Lengkap, & Kebijakan ARG',
      shortDesc: 'Aturan integritas data: larangan zero-fill, larangan auto-hijau, evaluasi parsial jujur, dan perlakuan stasiun ARG.',
      content: 'Sistem menerapkan prinsip integritas data ketat berikut:\n\n' +
        '1. Larangan Zero-Fill: Data kosong (null/NaN/—) TIDAK PERNAH dikonversi menjadi nol (0.0). Mengubah data kosong menjadi nol merupakan pelanggaran integritas ilmiah.\n\n' +
        '2. Larangan Auto-Hijau: Jika data indikator wajib belum lengkap, sistem TIDAK BOLEH otomatis memberikan label NORMAL/HIJAU (Aman). Status aman hanya boleh diberikan jika seluruh parameter wajib telah diverifikasi lengkap dan terbukti di bawah ambang bahaya.\n\n' +
        '3. Evaluasi Parsial yang Jujur: Jika suatu indikator yang tersedia telah terbukti melampaui ambang bahaya (misal HTH >= 31 hari atau SPI <= -1.50), status peringatan (SIAGA/AWAS/WASPADA) tetap ditampilkan secara jujur dengan catatan eksplisit "Evaluasi Parsial: parameter lain belum tersedia". Hal ini mencegah bahaya nyata terabaikan hanya karena kelambatan transmisi data pendamping.\n\n' +
        '4. Status TIDAK LENGKAP (INCOMPLETE): Diberikan apabila tidak ada indikator yang memicu bahaya namun ada input utama yang tidak tersedia, sehingga status aman belum dapat dipastikan.\n\n' +
        '5. Kebijakan Stasiun ARG: 5 stasiun Automatic Rain Gauge dievaluasi berbasis data Hari Tanpa Hujan (HTH) observasi sesuai kebijakan operasional. Stasiun ARG tidak dipaksa memiliki SPI atau probabilitas prakiraan jika data historis/modelnya belum dialokasikan. Apabila data HTH-nya valid, evaluasi stasiun ARG berstatus LENGKAP (COMPLETE).'
    },
    {
      id: 'missing-ttu-aturan',
      group: 'OPERASIONAL',
      groupLabel: 'Operasional DSS-PIK',
      term: 'Aturan Interpretasi Missing Data dan Hujan Tidak Terukur (TTU)',
      shortDesc: 'Perlakuan integritas data curah hujan harian pada deret HTH.',
      content: '• Missing Data (X / M / —): Data observasi tidak tercatat atau transmisi sensor terputus. Missing data memutus perhitungan deret HTH secara konservatif untuk menghindari penumpukan hari kering palsu, dan dicatat dengan status UNCERTAIN.\n\n' +
        '• TTU (Tidak Terukur / Trace): Hujan faktual terjadi tetapi ketinggian air di bawah 0.5 mm sehingga tidak dapat diukur presisi oleh gelas ukur. Dalam database numerik, TTU bernilai 0.0 mm dan TIDAK memutus deret Hari Tanpa Hujan (HTH terus bertambah).\n\n' +
        '• Hujan Terukur (>= 1.0 mm): Mengakhiri dan mereset deret Hari Tanpa Hujan (HTH kembali menjadi 0).'
    },
    {
      id: 'spi-30d-vs-90d',
      group: 'OPERASIONAL',
      groupLabel: 'Operasional DSS-PIK',
      term: 'SPI 30D (Otoritatif) vs SPI 90D (Pendamping)',
      shortDesc: 'Pemisahan hierarki peran SPI 30D (Authoritative Basis) dan SPI 90D (Informative Companion).',
      content: '• SPI 30D (Authoritative Basis): Standardized Precipitation Index akumulasi 30 hari resolusi dasarian merupakan indikator otoritatif tunggal yang memicu status PDKM (Waspada, Siaga, Awas).\n\n' +
        '• SPI 90D (Informative Companion): Standardized Precipitation Index akumulasi 90 hari (3 bulan) berfungsi sebagai pendamping informatif untuk memantau dinamika iklim jangka menengah, namun tidak dapat menggantikan peran otoritatif SPI 30D.'
    },
    {
      id: 'cara-membaca-tabel',
      group: 'OPERASIONAL',
      groupLabel: 'Operasional DSS-PIK',
      term: 'Cara Membaca Tabel Peringatan Dini & Indikator Stasiun',
      shortDesc: 'Panduan menafsirkan kolom evaluasi pada tabel pemantauan operasional.',
      content: '1. Kolom HTH (Hari Tanpa Hujan): Jumlah hari berturut-turut tanpa hujan terukur (>=1 mm) hingga tanggal cutoff observasi.\n' +
        '2. Kolom pb20: Peluang curah hujan dasarian target < 20 mm dari ensemble ECMWF (skala 0–100%). Menghasilkan WASPADA jika > 70%.\n' +
        '3. Kolom SPI 30D (Otoritatif): Nilai Standardized Precipitation Index dasarian yang menjadi acuan keputusan resmi PDKM.\n' +
        '4. Kolom SPI 90D (Pendamping): Nilai SPI 3 bulanan untuk pemantauan tren dinamika jangka menengah.\n' +
        '5. Kolom Status PDKM: Hasil evaluasi kekeringan: max(level_hth, level_prob, level_spi).\n' +
        '6. Kolom pa150, pa200, pa300: Peluang curah hujan dasarian melampaui 150, 200, atau 300 mm dari ensemble ECMWF.\n' +
        '7. Kolom Status PDCHT: Hasil evaluasi curah hujan tinggi: max(level_dasarian, level_bulanan).\n' +
        '8. Status Gabungan (Overall Level): Tingkat ancaman tertinggi antara PDKM dan PDCHT (worst-case safety).\n' +
        '9. Status Evaluasi (Evaluation Status): Menunjukkan COMPLETE (Lengkap), PARTIAL (Evaluasi Parsial dengan Peringatan Aktif), atau INCOMPLETE (Data Belum Lengkap).'
    },
    {
      id: 'cutoff-dan-periode',
      group: 'OPERASIONAL',
      groupLabel: 'Operasional DSS-PIK',
      term: 'Jendela Waktu & Cutoff Observasi Dasarian',
      shortDesc: 'Ketentuan batas waktu data observasi terhadap periode target peringatan.',
      content: 'Peringatan dini dievaluasi dan diterbitkan sebelum periode target dimulai. Sebagai contoh, untuk target Peringatan Dini Dasarian II September 2026 (11–20 September), cutoff observasi adalah tanggal 10 September 2026 pukul 23.59 WIB (akhir Dasarian I September). Seluruh data observasi yang digunakan adalah data faktual hingga tanggal cutoff tersebut, dipadukan dengan prakiraan ECMWF yang terbit terdekat sebelum periode target.'
    }
  ];

  const toggleExpand = (id) => {
    setExpandedItems((prev) => ({ ...prev, [id]: !prev[id] }));
  };

  const filteredItems = useMemo(() => {
    return glossaryItems.filter((item) => {
      if (activeGroupFilter !== 'ALL' && item.group !== activeGroupFilter) {
        return false;
      }
      if (searchQuery.trim()) {
        const q = searchQuery.toLowerCase().trim();
        const matchTerm = item.term.toLowerCase().includes(q);
        const matchDesc = item.shortDesc.toLowerCase().includes(q);
        const matchContent = item.content.toLowerCase().includes(q);
        if (!matchTerm && !matchDesc && !matchContent) return false;
      }
      return true;
    });
  }, [activeGroupFilter, searchQuery]);

  // Separate filtered items into the two primary groups
  const umumItems = useMemo(() => {
    return filteredItems.filter((it) => it.group === 'UMUM');
  }, [filteredItems]);

  const operasionalItems = useMemo(() => {
    return filteredItems.filter((it) => it.group === 'OPERASIONAL');
  }, [filteredItems]);

  return (
    <div className="kamus-page-wrapper">
      {/* 1. Header Banner */}
      <div className="kamus-header-banner">
        <div className="kamus-header-left">
          <div className="kamus-badge-pill">
            <BookOpen size={16} />
            <span>Referensi Resmi DSS-PIK</span>
          </div>
          <h2 className="kamus-main-title">Kamus Istilah & Ketentuan Sistem</h2>
          <p className="kamus-main-desc">
            Panduan resmi terminologi meteorologi/klimatologi dan ketentuan operasional Decision Engine aktif di {INSTITUTION_SHORT_NAME}.
          </p>
        </div>
      </div>

      {/* 2. Search & Group Filter Bar */}
      <div className="kamus-search-card">
        <div className="kamus-search-box">
          <Search size={16} className="kamus-search-icon" />
          <input
            type="text"
            placeholder="Cari istilah, singkatan, rumus, atau ketentuan operasional..."
            className="kamus-search-input"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
          />
          {searchQuery && (
            <button
              type="button"
              className="btn-clear-search"
              onClick={() => setSearchQuery('')}
              title="Hapus pencarian"
            >
              &times;
            </button>
          )}
        </div>

        {/* Group Filter Tabs: Only "Semua", "Istilah Umum", "Operasional DSS-PIK" */}
        <div className="kamus-categories-row" role="tablist">
          <button
            type="button"
            className={`kamus-cat-pill ${activeGroupFilter === 'ALL' ? 'active' : ''}`}
            onClick={() => setActiveGroupFilter('ALL')}
          >
            <span>Semua Istilah</span>
          </button>
          <button
            type="button"
            className={`kamus-cat-pill ${activeGroupFilter === 'UMUM' ? 'active' : ''}`}
            onClick={() => setActiveGroupFilter('UMUM')}
          >
            <Droplets size={14} />
            <span>Istilah Umum</span>
          </button>
          <button
            type="button"
            className={`kamus-cat-pill ${activeGroupFilter === 'OPERASIONAL' ? 'active' : ''}`}
            onClick={() => setActiveGroupFilter('OPERASIONAL')}
          >
            <Activity size={14} />
            <span>Operasional DSS-PIK</span>
          </button>
        </div>
      </div>

      {/* 3. Glossary Items Displayed in Exactly Two Sections */}
      <div className="kamus-items-container">
        <div className="kamus-results-meta">
          <span>Menampilkan <strong>{filteredItems.length}</strong> istilah terdaftar</span>
          {searchQuery && (
            <span className="search-filter-tag">Pencarian: "{searchQuery}"</span>
          )}
        </div>

        {filteredItems.length === 0 ? (
          <div className="kamus-empty-state">
            <HelpCircle size={32} className="text-muted" />
            <p className="empty-title">Tidak ada istilah yang cocok</p>
            <p className="empty-desc">Coba gunakan kata kunci lain atau pilih "Semua Istilah".</p>
          </div>
        ) : (
          <div className="kamus-two-groups-wrapper">
            {/* GROUP 1: ISTILAH UMUM */}
            {(activeGroupFilter === 'ALL' || activeGroupFilter === 'UMUM') && umumItems.length > 0 && (
              <section className="kamus-section-group" aria-labelledby="section-istilah-umum">
                <div className="kamus-group-header">
                  <div className="kamus-group-header-left">
                    <Droplets size={18} className="text-blue" />
                    <h3 id="section-istilah-umum" className="kamus-group-title">Istilah Umum</h3>
                  </div>
                  <span className="badge-count-pill">{umumItems.length} Istilah</span>
                </div>

                <div className="kamus-accordion-list">
                  {umumItems.map((item) => {
                    const isExpanded = expandedItems[item.id] !== false; // default expanded
                    return (
                      <div key={item.id} className="kamus-card-item">
                        <div
                          className="kamus-card-header"
                          onClick={() => toggleExpand(item.id)}
                          role="button"
                          tabIndex={0}
                        >
                          <div className="kamus-card-title-group">
                            <span className="kamus-group-badge badge-umum">Umum</span>
                            <h4 className="kamus-term-title">{item.term}</h4>
                          </div>

                          <div className="flex-align gap-2">
                            <span className="kamus-short-desc text-muted">{item.shortDesc}</span>
                            <button type="button" className="btn-toggle-kamus">
                              {isExpanded ? <ChevronUp size={15} /> : <ChevronDown size={15} />}
                            </button>
                          </div>
                        </div>

                        {isExpanded && (
                          <div className="kamus-card-body">
                            <p className="kamus-full-content" style={{ whiteSpace: 'pre-line' }}>{item.content}</p>
                          </div>
                        )}
                      </div>
                    );
                  })}
                </div>
              </section>
            )}

            {/* GROUP 2: OPERASIONAL DSS-PIK */}
            {(activeGroupFilter === 'ALL' || activeGroupFilter === 'OPERASIONAL') && operasionalItems.length > 0 && (
              <section className="kamus-section-group" aria-labelledby="section-operasional-dsspik">
                <div className="kamus-group-header">
                  <div className="kamus-group-header-left">
                    <Activity size={18} className="text-forest" />
                    <h3 id="section-operasional-dsspik" className="kamus-group-title">Operasional DSS-PIK</h3>
                  </div>
                  <span className="badge-count-pill">{operasionalItems.length} Ketentuan</span>
                </div>

                <div className="kamus-accordion-list">
                  {operasionalItems.map((item) => {
                    const isExpanded = expandedItems[item.id] !== false; // default expanded
                    return (
                      <div key={item.id} className="kamus-card-item">
                        <div
                          className="kamus-card-header"
                          onClick={() => toggleExpand(item.id)}
                          role="button"
                          tabIndex={0}
                        >
                          <div className="kamus-card-title-group">
                            <span className="kamus-group-badge badge-operasional">Operasional</span>
                            <h4 className="kamus-term-title">{item.term}</h4>
                          </div>

                          <div className="flex-align gap-2">
                            <span className="kamus-short-desc text-muted">{item.shortDesc}</span>
                            <button type="button" className="btn-toggle-kamus">
                              {isExpanded ? <ChevronUp size={15} /> : <ChevronDown size={15} />}
                            </button>
                          </div>
                        </div>

                        {isExpanded && (
                          <div className="kamus-card-body">
                            <p className="kamus-full-content" style={{ whiteSpace: 'pre-line' }}>{item.content}</p>
                          </div>
                        )}
                      </div>
                    );
                  })}
                </div>
              </section>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
