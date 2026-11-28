import React, { useState, useMemo } from 'react';
import { INSTITUTION_SHORT_NAME } from '../config';
import {
  BookOpen,
  Search,
  HelpCircle,
  ChevronDown,
  ChevronUp,
  Droplets,
  Activity,
} from 'lucide-react';

export default function KamusPage() {
  const [searchQuery, setSearchQuery] = useState('');
  const [activeGroupFilter, setActiveGroupFilter] = useState('ALL'); // 'ALL' | 'UMUM' | 'OPERASIONAL'
  const [expandedItems, setExpandedItems] = useState({});

  // Dua kategori utama: "Istilah Umum" & "Istilah Operasional"
  const glossaryItems = [
    // =========================================================================
    // 1. ISTILAH UMUM
    // =========================================================================
    {
      id: 'dss-pik',
      group: 'UMUM',
      groupLabel: 'Istilah Umum',
      term: 'DSS-PIK (Decision Support System Peringatan Iklim)',
      shortDesc: 'Sistem pendukung keputusan operasional BMKG untuk pemantauan dan peringatan dini iklim Kepulauan Riau.',
      content: 'DSS-PIK adalah sistem pendukung keputusan berbasis data observasi curah hujan harian, indeks SPI multi-skala, dan prakiraan iklim ECMWF multi-vintage untuk menghasilkan rekomendasi peringatan dini kekeringan meteorologis (PDKM) dan curah hujan tinggi (PDCHT) di 57 pos pengamatan wilayah Provinsi Kepulauan Riau.'
    },
    {
      id: 'bmkg',
      group: 'UMUM',
      groupLabel: 'Istilah Umum',
      term: 'BMKG (Badan Meteorologi, Klimatologi, dan Geofisika)',
      shortDesc: 'Lembaga pemerintah nonkementerian yang menyelenggarakan tugas di bidang meteorologi, klimatologi, kualitas udara, dan geofisika.',
      content: 'Di wilayah Kepulauan Riau, layanan operasional peringatan dini iklim diselenggarakan oleh BMKG Stasiun Meteorologi Kelas II Raja Haji Fisabilillah Tanjungpinang sebagai unit pelaksana teknis resmi.'
    },
    {
      id: 'data-center',
      group: 'UMUM',
      groupLabel: 'Istilah Umum',
      term: 'Data Center (Pusat Data DSS-PIK)',
      shortDesc: 'Ruang kerja terpadu untuk melihat, memperbarui, mengelola, dan mengekspor dataset operasional DSS-PIK.',
      content: 'Data Center menghimpun empat modul utama: Data Curah Hujan (MariaDB), Data SPI (Parquet), Data Probabilitas & Deterministik ECMWF (MariaDB), serta Manajemen Data Operasional (Kelola Data, Riwayat Batch, dan Kelola Vintage). Seluruh ekspor berkas resmi dilayani melalui Pusat Unduh Data.'
    },
    {
      id: 'pos-pengamatan',
      group: 'UMUM',
      groupLabel: 'Istilah Umum',
      term: 'Pos Pengamatan (Pos Hujan Manual vs Stasiun ARG)',
      shortDesc: '57 titik pengamatan master di Kepulauan Riau yang terdiri atas 52 pos hujan manual dan 5 stasiun ARG.',
      content: 'Pos Hujan Manual (52 pos) menggunakan penakar tipe Observatorium (OBS) berdiameter corong 100 cm² yang dicatat secara manual setiap pukul 07.00 WS oleh pengamat pos kerja sama BMKG. Stasiun Automatic Rain Gauge / ARG (5 stasiun: ARG Daik Lingga, ARG Dabo, ARG Ranai, ARG Bandara Tambelan, dan ARG Tembeling) menggunakan sensor tipping-bucket digital otomatis via telemetri. Stasiun ARG yang belum memiliki deret historis panjang dievaluasi secara khusus berbasis HTH aktual untuk menjaga integritas ilmiah.'
    },
    {
      id: 'curah-hujan',
      group: 'UMUM',
      groupLabel: 'Istilah Umum',
      term: 'Curah Hujan (CH)',
      shortDesc: 'Ketinggian air hujan yang terkumpul dalam satuan milimeter (mm).',
      content: 'Curah hujan adalah ketebalan lapisan air yang jatuh di atas permukaan tanah datar seluas 1 meter persegi dengan asumsi tidak terjadi penguapan (evaporasi), peresapan (infiltrasi), maupun limpasan. 1 mm curah hujan setara dengan 1 liter air per meter persegi. Klasifikasi intensitas harian BMKG: Berawan/Kering (0.0 mm), Hujan Sangat Ringan (< 5 mm/hari), Hujan Ringan (5–20 mm/hari), Hujan Sedang (20–50 mm/hari), Hujan Lebat (50–100 mm/hari), Hujan Sangat Lebat (100–150 mm/hari), dan Hujan Ekstrem (> 150 mm/hari).'
    },
    {
      id: 'spi-umum',
      group: 'UMUM',
      groupLabel: 'Istilah Umum',
      term: 'Standardized Precipitation Index (SPI)',
      shortDesc: 'Indeks standar deviasi anomali curah hujan relatif terhadap distribusi historis jangka panjang.',
      content: 'SPI adalah indeks meteorologi probabilitas (McKee et al., 1993; standar WMO) untuk pemantauan kekeringan dan kebasahan. Nilai SPI negatif menunjukkan kondisi lebih kering dari normal klimatologis, sedangkan nilai positif menunjukkan kondisi lebih basah. Klasifikasi BMKG: Amat Sangat Basah (SPI >= +2.00), Sangat Basah (+1.50 s.d. +1.99), Agak Basah (+1.00 s.d. +1.49), Normal (-0.99 s.d. +0.99), Agak Kering (-1.49 s.d. -1.00), Sangat Kering (-1.99 s.d. -1.50), dan Amat Sangat Kering (SPI <= -2.00).'
    },
    {
      id: 'ecmwf',
      group: 'UMUM',
      groupLabel: 'Istilah Umum',
      term: 'ECMWF (European Centre for Medium-Range Weather Forecasts)',
      shortDesc: 'Pusat pemodelan cuaca dan iklim numerik global yang menjadi sumber data prakiraan curah hujan DSS-PIK.',
      content: 'Keluaran model ensemble ECMWF diolah BMKG ke dalam workbook prakiraan per pos pengamatan untuk wilayah Kepulauan Riau. Setiap workbook memuat dua produk sekaligus: Prakiraan Probabilitas (%) dan Prakiraan Deterministik (mm).'
    },
    {
      id: 'prakiraan-probabilitas',
      group: 'UMUM',
      groupLabel: 'Istilah Umum',
      term: 'Prakiraan Probabilitas (%)',
      shortDesc: 'Informasi peluang kejadian curah hujan berdasarkan parameter ambang batas prakiraan ECMWF (0–100%).',
      content: 'Prakiraan Probabilitas (%) menyatakan peluang persentase (0% hingga 100%) terjadinya curah hujan di bawah atau di atas ambang batas tertentu pada resolusi Dasarian (pb20, pa150, pa200, pa300) maupun Bulanan (>300 mm, >400 mm, >500 mm). Nilai probabilitas ini digunakan sebagai faktor pemicu objektif pada Decision Engine PDKM dan PDCHT.'
    },
    {
      id: 'prakiraan-deterministik',
      group: 'UMUM',
      groupLabel: 'Istilah Umum',
      term: 'Prakiraan Deterministik (mm)',
      shortDesc: 'Nilai prakiraan curah hujan numerik dalam satuan milimeter (mm) yang bersumber dari sheet EnsMean pada workbook ECMWF.',
      content: 'Prakiraan Deterministik (mm) menyajikan estimasi kuantitatif jumlah curah hujan (dalam satuan milimeter) untuk setiap pos pengamatan dan periode target (Dasarian maupun Bulanan). Data ini dibaca otomatis dari sheet EnsMean pada workbook ECMWF yang sama dengan data Probabilitas, dan pada antarmuka pengguna DSS-PIK disajikan dengan istilah resmi "Deterministik (mm)".'
    },
    {
      id: 'dasarian',
      group: 'UMUM',
      groupLabel: 'Istilah Umum',
      term: 'Dasarian',
      shortDesc: 'Satuan periode waktu klimatologis berdurasi sekitar 10 hari (3 dasarian per bulan).',
      content: 'Dalam satu bulan kalender terbagi menjadi 3 dasarian: Dasarian I (tanggal 1–10), Dasarian II (tanggal 11–20), dan Dasarian III (tanggal 21 hingga hari terakhir bulan: 28/29, 30, atau 31). Dasarian merupakan satuan waktu standar analisis dan peringatan dini iklim operasional BMKG.'
    },
    {
      id: 'bulanan',
      group: 'UMUM',
      groupLabel: 'Istilah Umum',
      term: 'Bulanan',
      shortDesc: 'Satuan periode waktu satu bulan kalender penuh (Januari–Desember).',
      content: 'Resolusi Bulanan digunakan untuk prakiraan curah hujan akumulasi bulanan (Probabilitas >300, >400, >500 mm dan Deterministik mm) serta pemantauan anomali SPI bulanan jangka panjang.'
    },
    {
      id: 'vintage-penerbitan',
      group: 'UMUM',
      groupLabel: 'Istilah Umum',
      term: 'Vintage / Penerbitan',
      shortDesc: 'Versi penerbitan prakiraan ECMWF yang diidentifikasi berdasarkan tanggal terbit (Issue Date).',
      content: 'Satu periode target dapat memiliki beberapa versi prakiraan yang diterbitkan pada tanggal berbeda. Setiap versi tersebut disebut Vintage (Penerbitan). Penyimpanan multi-vintage memungkinkan operator melihat prakiraan terbaru maupun meninjau ulang prakiraan historis yang berlaku pada tanggal evaluasi tertentu.'
    },
    {
      id: 'pdkm-umum',
      group: 'UMUM',
      groupLabel: 'Istilah Umum',
      term: 'PDKM (Peringatan Dini Kekeringan Meteorologis)',
      shortDesc: 'Peringatan dini potensi kekeringan meteorologis berbasis evaluasi independen HTH, Probabilitas pb20, dan SPI 30D.',
      content: 'PDKM mendeteksi potensi defisit curah hujan dan kekeringan meteorologis dengan mengevaluasi tiga indikator secara independen: Hari Tanpa Hujan (HTH), Probabilitas Curah Hujan Rendah (pb20 < 20 mm), dan SPI 30D Dasarian. Status akhir PDKM menggunakan prinsip kewaspadaan tertinggi: status_pdkm = max(level_hth, level_prob, level_spi).'
    },
    {
      id: 'pdcht-umum',
      group: 'UMUM',
      groupLabel: 'Istilah Umum',
      term: 'PDCHT (Peringatan Dini Curah Hujan Tinggi)',
      shortDesc: 'Peringatan dini potensi curah hujan lebat dan ekstrem berbasis probabilitas ECMWF dasarian dan bulanan.',
      content: 'PDCHT mendeteksi potensi curah hujan tinggi yang berisiko memicu bencana hidrometeorologis basah (banjir, genangan, longsor). Evaluasi dilakukan secara independen pada probabilitas dasarian (pa150, pa200, pa300) dan bulanan (>300, >400, >500 mm) dengan rumus status_pdcht = max(level_dasarian, level_bulanan).'
    },
    {
      id: 'hth-umum',
      group: 'UMUM',
      groupLabel: 'Istilah Umum',
      term: 'Hari Tanpa Hujan (HTH)',
      shortDesc: 'Jumlah hari berturut-turut tanpa hujan terukur atau curah hujan < 1.0 mm.',
      content: 'Hari dengan curah hujan < 1.0 mm (termasuk 0.0 mm dan TTU) dihitung sebagai hari tanpa hujan yang menambah durasi HTH. Apabila terjadi hujan terukur >= 1.0 mm pada suatu hari, deret HTH terputus dan kembali menjadi 0 hari.'
    },
    {
      id: 'observasi-prakiraan',
      group: 'UMUM',
      groupLabel: 'Istilah Umum',
      term: 'Observasi vs Prakiraan Iklim',
      shortDesc: 'Perbedaan antara data faktual terukur di permukaan dan estimasi model numerik masa depan.',
      content: 'Data Observasi adalah hasil pengukuran fisik curah hujan di pos manual/ARG hingga tanggal cutoff. Data Prakiraan adalah estimasi model numerik ECMWF untuk periode mendatang. DSS-PIK memadukan observasi terkini dengan prakiraan untuk menghasilkan rekomendasi peringatan dini.'
    },
    {
      id: 'zom-kepri',
      group: 'UMUM',
      groupLabel: 'Istilah Umum',
      term: 'Zona Musim (ZOM)',
      shortDesc: 'Wilayah yang memiliki batas jelas antara periode musim hujan dan kemarau berdasarkan rata-rata 30 tahun.',
      content: 'Sebagian besar wilayah Kepulauan Riau tergolong wilayah Ekuatorial / Non-ZOM dengan pola hujan dwipuncak (bimodal) yang dipengaruhi oleh dinamika monsun dan konvergensi antar-tropis (ITCZ).'
    },

    // =========================================================================
    // 2. ISTILAH OPERASIONAL
    // =========================================================================
    {
      id: 'issue-date',
      group: 'OPERASIONAL',
      groupLabel: 'Istilah Operasional',
      term: 'Issue Date',
      shortDesc: 'Tanggal resmi penerbitan prakiraan ECMWF (bukan periode target).',
      content: 'Issue Date adalah tanggal ketika paket prakiraan ECMWF diterbitkan (misalnya 2026-10-19). Issue Date harus selalu dibedakan secara tegas dari Target Period (periode masa depan yang diprakirakan). Sistem membaca Issue Date secara terverifikasi dari metadata/nama berkas workbook tanpa fallback tanggal sistem.'
    },
    {
      id: 'target-period',
      group: 'OPERASIONAL',
      groupLabel: 'Istilah Operasional',
      term: 'Target Period (Periode Target)',
      shortDesc: 'Periode waktu masa depan yang menjadi sasaran prakiraan atau evaluasi peringatan dini.',
      content: 'Target Period menyatakan rentang waktu yang diprakirakan, misalnya 2026-11-das1 (Dasarian I November 2026) untuk resolusi Dasarian atau 2026-11 (November 2026) untuk resolusi Bulanan. Target Period selalu dibedakan dari Issue Date.'
    },
    {
      id: 'cutoff-evaluasi',
      group: 'OPERASIONAL',
      groupLabel: 'Istilah Operasional',
      term: 'Cutoff Evaluasi',
      shortDesc: 'Batas tanggal referensi untuk menyaring observasi dan memilih vintage prakiraan yang sah pada tanggal tersebut.',
      content: 'Pada evaluasi peringatan dini dan penelusuran historis, Cutoff Evaluasi memastikan sistem hanya menggunakan data observasi hingga tanggal batas tersebut serta memilih vintage ECMWF terbaru yang memiliki Issue Date <= Cutoff Evaluasi (tanpa mengambil penerbitan masa depan).'
    },
    {
      id: 'multi-vintage',
      group: 'OPERASIONAL',
      groupLabel: 'Istilah Operasional',
      term: 'Multi-Vintage',
      shortDesc: 'Kemampuan menyimpan dan menelusuri lebih dari satu versi penerbitan prakiraan untuk periode target yang sama.',
      content: 'Dengan arsitektur Multi-Vintage, unggahan penerbitan baru untuk periode target yang sama tidak menimpa sejarah penerbitan lama. Operator dapat membandingkan vintage aktif (terbaru) maupun vintage historis melalui filter Penerbitan (Vintage) dan Cutoff Evaluasi.'
    },
    {
      id: 'adjusted-regular-source-col',
      group: 'OPERASIONAL',
      groupLabel: 'Istilah Operasional',
      term: 'Adjusted, Regular, dan Source Column',
      shortDesc: 'Aturan prioritas pembacaan kolom Deterministik (mm) dan pencatatan nama kolom sumber asli.',
      content: '• Adjusted: Kolom pada sheet EnsMean yang header-nya mengandung kata "adjust" (case-insensitive). Apabila tersedia kolom Adjusted dan Regular untuk periode target yang sama, sistem SELALU memprioritaskan kolom Adjusted.\n' +
        '• Regular: Kolom prakiraan standar yang digunakan apabila tidak tersedia kolom Adjusted untuk periode target tersebut.\n' +
        '• Source Column: Nama header kolom asli dari workbook Excel yang disimpan utuh di database sebagai jejak audit (misalnya "Nov Adjust" atau "Nov"). Jika terdapat lebih dari satu kandidat Adjusted untuk target yang sama, sistem menandai konflik dan memblokir penyimpanan.'
    },
    {
      id: 'release-group',
      group: 'OPERASIONAL',
      groupLabel: 'Istilah Operasional',
      term: 'Release Group',
      shortDesc: 'Pengelompokan berkas dalam satu penerbitan ECMWF (Dasarian = 3 workbook; Bulanan = 1 workbook).',
      content: '• Dasarian: Satu penerbitan wajib terdiri atas 3 file workbook yang valid dengan Issue Date identik dan tanpa konflik periode target, digabung dalam satu Release Group (release_group_id). Partial release (< 3 file) ditolak saat penyimpanan.\n' +
        '• Bulanan: Satu penerbitan menggunakan 1 file workbook dengan cakupan bulan target yang dibaca secara dinamis dari header workbook.'
    },
    {
      id: 'batch-ingestion-preview-commit',
      group: 'OPERASIONAL',
      groupLabel: 'Istilah Operasional',
      term: 'Batch Ingestion, Pratinjau Data, dan Komit / Penyimpanan Data',
      shortDesc: 'Tiga pilar kendali mutu setiap sesi unggah data operasional di DSS-PIK.',
      content: '• Batch Ingestion: Satu sesi pemasukan data yang memiliki identitas unik (batch_id), hash SHA-256 berkas, nama operator, dan catatan audit.\n' +
        '• Pratinjau Data (Dry-Run): Pemeriksaan sebelum simpan yang menampilkan Issue Date, periode terdeteksi, jumlah baris baru/update/identik, status Probabilitas & Deterministik, deteksi kolom Adjust, serta peringatan.\n' +
        '• Komit / Penyimpanan Data: Eksekusi penyimpanan transaksional atomik setelah operator menyetujui pratinjau. Jika terjadi kegagalan di tengah proses, seluruh transaksi dibatalkan (rollback) agar tidak terjadi data parsial.'
    },
    {
      id: 'kelola-koreksi-pembatalan-aktifkan',
      group: 'OPERASIONAL',
      groupLabel: 'Istilah Operasional',
      term: 'Kelola Data, Koreksi Data, Pembatalan Data, dan Aktifkan Kembali',
      shortDesc: 'Standar istilah pengelolaan data operasional dan perbedaan mekanisme antar dataset.',
      content: '• Kelola Data: Menu terpadu di Manajemen Data Operasional untuk merawat data Curah Hujan, SPI, dan Prakiraan ECMWF.\n' +
        '• Koreksi Data: Memperbaiki nilai/status catatan yang keliru (misalnya koreksi angka curah hujan harian) dengan mencatat nilai lama, nilai baru, alasan, dan operator.\n' +
        '• Pembatalan Data: Menonaktifkan atau membatalkan catatan/batch yang tidak sah. Mekanisme backend berbeda sesuai karakter dataset: Curah Hujan menandai status VOID, SPI menullifikasi nilai pada skala terisolasi, Probabilitas menganulir snapshot terpilih, sedangkan Deterministik menggunakan mekanisme Soft-Void (is_voided = 1).\n' +
        '• Aktifkan Kembali: Memulihkan catatan/vintage yang sebelumnya dibatalkan (pada modul yang mendukung pemulihan/reaktivasi seperti Curah Hujan dan Deterministik) dengan tetap menyimpan jejak audit pembatalan sebelumnya.'
    },
    {
      id: 'kelola-vintage-soft-void',
      group: 'OPERASIONAL',
      groupLabel: 'Istilah Operasional',
      term: 'Kelola Vintage, Batalkan Vintage, Aktifkan Kembali Vintage, dan Soft-Void',
      shortDesc: 'Pengelolaan siklus hidup penerbitan ECMWF secara terisolasi tanpa menghapus riwayat audit.',
      content: '• Kelola Vintage: Panel untuk meninjau daftar penerbitan (vintage) Probabilitas dan Deterministik serta melakukan pembatalan atau pemulihan.\n' +
        '• Batalkan Vintage: Membatalkan penerbitan ECMWF tertentu berdasarkan Issue Date, resolusi, dan (opsional) periode target atau pos. Pembatalan vintage Deterministik terisolasi penuh dan tidak memengaruhi data Probabilitas.\n' +
        '• Aktifkan Kembali Vintage: Mengaktifkan kembali vintage Deterministik yang sebelumnya dibatalkan tanpa menimbulkan duplikasi kunci unik.\n' +
        '• Soft-Void: Mekanisme teknis internal pada tabel Deterministik yang menandai baris dengan is_voided = 1 sehingga tidak tampil di tabel aktif maupun Pusat Unduh Data, namun tetap tersimpan aman untuk jejak audit dan dapat diaktifkan kembali.'
    },
    {
      id: 'riwayat-audit-pengelolaan',
      group: 'OPERASIONAL',
      groupLabel: 'Istilah Operasional',
      term: 'Riwayat dan Audit Pengelolaan Data',
      shortDesc: 'Catatan permanen seluruh aktivitas ingestion, koreksi, pembatalan, dan pemulihan data.',
      content: 'Setiap aksi penyimpanan batch, Koreksi Data, Pembatalan Data, Batalkan Vintage, dan Aktifkan Kembali Vintage direkam otomatis beserta identitas operator, waktu (WIB), nilai lama/baru, dan alasan operasional. Catatan audit ini tidak dihapus demi akuntabilitas layanan BMKG.'
    },
    {
      id: 'pusat-unduh-format',
      group: 'OPERASIONAL',
      groupLabel: 'Istilah Operasional',
      term: 'Pusat Unduh Data & Format Berkas (CSV, XLSX, Parquet)',
      shortDesc: 'Satu pintu ekspor resmi berbasis ketersediaan data aktual beserta peran format berkas.',
      content: '• Pusat Unduh Data: Modul tunggal untuk mengekspor Curah Hujan (CH), Indeks SPI, dan Prakiraan ECMWF (Probabilitas % dan Deterministik mm). Seluruh rentang tanggal, periode target, dan daftar vintage dibaca langsung dari database aktual, serta otomatis mengecualikan data/vintage yang dibatalkan.\n' +
        '• XLSX (Microsoft Excel): Format spreadsheet dengan header dan tata letak rapi untuk pelaporan operasional.\n' +
        '• CSV (Comma-Separated Values, UTF-8): Format teks tabular standar untuk analisis statistik atau integrasi sistem lain.\n' +
        '• Parquet: Format penyimpanan kolumnar berkinerja tinggi yang digunakan sebagai penyimpanan kanonikal deret waktu Indeks SPI.'
    },
    {
      id: 'status-kelengkapan-data',
      group: 'OPERASIONAL',
      groupLabel: 'Istilah Operasional',
      term: 'Status Kelengkapan Data',
      shortDesc: 'Indikator cakupan ketersediaan data pos pengamatan dan kelengkapan parameter evaluasi.',
      content: 'Menunjukkan jumlah pos pengamatan yang memiliki data aktual terhadap total pos master (misalnya 52/52 pos manual untuk prakiraan ECMWF atau cakupan pos harian CH). Sistem tidak pernah mengisi data kosong dengan angka nol dan menampilkan status kelengkapan secara transparan.'
    },
    {
      id: 'alur-operasional-dss-pik',
      group: 'OPERASIONAL',
      groupLabel: 'Istilah Operasional',
      term: 'Ringkasan 6 Alur Operasional DSS-PIK',
      shortDesc: 'Panduan langkah ringkas untuk input CH, input ECMWF, Generator SPI, kelola vintage, koreksi/pembatalan, dan ekspor.',
      content: '1. Input / Pembaruan Data Curah Hujan (CH):\n' +
        '   Buka Data Center → Data Curah Hujan → Input Data Curah Hujan → pilih Kabupaten/Kota → pilih metode (Upload Excel atau Input Manual) → periksa Pratinjau & konflik → otorisasi & simpan.\n\n' +
        '2. Input / Pembaruan Data Probabilitas & Deterministik (ECMWF):\n' +
        '   Buka Data Center → Data Probabilitas & Deterministik → Input / Pembaruan Data → Tahap 1 pilih resolusi (Dasarian = 3 workbook / Bulanan = 1 workbook) → Tahap 2 unggah berkas → Tahap 3 tinjau ringkasan Probabilitas (%) & Deterministik (mm) beserta deteksi kolom Adjust → Tahap 4 otorisasi & simpan atomik → Tahap 5 hasil.\n\n' +
        '3. Generator SPI:\n' +
        '   Buka Data Center → Data SPI → Generator SPI → pilih resolusi (Harian/Dasarian/Bulanan) dan skala akumulasi (30D/90D) → pratinjau hasil perhitungan → jalankan & simpan ke penyimpanan Parquet kanonikal.\n\n' +
        '4. Pengelolaan Vintage ECMWF:\n' +
        '   Buka Manajemen Data Operasional → Kelola Vintage ECMWF (atau tombol Kelola Vintage pada tabel ECMWF) → tinjau daftar penerbitan aktif/historis → gunakan Batalkan Vintage atau Aktifkan Kembali Vintage (untuk Deterministik) dengan alasan audit.\n\n' +
        '5. Koreksi dan Pembatalan Data:\n' +
        '   Buka Manajemen Data Operasional → Kelola Data (Koreksi & Pembatalan) → pilih dataset (Kelola Data Curah Hujan, Kelola Data SPI, atau Kelola Prakiraan ECMWF) → lakukan Koreksi Data atau Pembatalan Data disertai alasan → pantau pada Riwayat dan Audit Pengelolaan Data.\n\n' +
        '6. Ekspor Dataset melalui Pusat Unduh Data:\n' +
        '   Klik Pusat Unduh Data di bagian kanan atas Data Center → pilih kategori (Curah Hujan, Indeks SPI, atau Prakiraan ECMWF) → sesuaikan filter aktual (tanggal / resolusi / jenis data / periode target / vintage / pos) → pilih format XLSX atau CSV → klik Unduh.'
    },
    {
      id: 'pdkm-aturan',
      group: 'OPERASIONAL',
      groupLabel: 'Istilah Operasional',
      term: 'Aturan Evaluasi Independen & Ambang Batas PDKM',
      shortDesc: 'Ambang batas objektif untuk HTH, Probabilitas pb20, SPI 30D, serta formula penggabungan status_pdkm.',
      content: 'Setiap indikator kekeringan dievaluasi secara mandiri (independen):\n\n' +
        '• Indikator 1: Hari Tanpa Hujan (HTH)\n' +
        '  - HTH >= 61 hari → AWAS (Level 3)\n' +
        '  - 31 <= HTH < 61 hari → SIAGA (Level 2)\n' +
        '  - 21 <= HTH < 31 hari → WASPADA (Level 1)\n' +
        '  - HTH < 21 hari → HIJAU / NORMAL (Level 0)\n\n' +
        '• Indikator 2: Probabilitas Curah Hujan Rendah (pb20)\n' +
        '  - pb20 > 70.0% → WASPADA (Level 1; maksimum WASPADA tanpa observasi)\n' +
        '  - pb20 <= 70.0% → HIJAU / NORMAL (Level 0)\n\n' +
        '• Indikator 3: SPI 30D Dasarian (Acuan Otoritatif)\n' +
        '  - SPI <= -2.00 → AWAS (Level 3)\n' +
        '  - -2.00 < SPI <= -1.50 → SIAGA (Level 2)\n' +
        '  - -1.50 < SPI <= -1.00 → WASPADA (Level 1)\n' +
        '  - SPI > -1.00 → HIJAU / NORMAL (Level 0)\n\n' +
        '• Penggabungan: status_pdkm = max(level_hth, level_prob, level_spi).'
    },
    {
      id: 'pdcht-aturan',
      group: 'OPERASIONAL',
      groupLabel: 'Istilah Operasional',
      term: 'Aturan Evaluasi Independen & Ambang Batas PDCHT',
      shortDesc: 'Ambang probabilitas ketat lebih dari 50% (> 50.0%) untuk probabilitas dasarian dan bulanan.',
      content: 'Setiap skala waktu PDCHT dievaluasi secara mandiri menggunakan ambang ketat > 50.0%:\n\n' +
        '• Skala Dasarian:\n' +
        '  - pa300 > 50.0% → AWAS (Level 3)\n' +
        '  - pa200 > 50.0% → SIAGA (Level 2)\n' +
        '  - pa150 > 50.0% → WASPADA (Level 1)\n\n' +
        '• Skala Bulanan:\n' +
        '  - Peluang CH Bulanan > 500 mm > 50.0% → AWAS (Level 3)\n' +
        '  - Peluang CH Bulanan > 400 mm > 50.0% → SIAGA (Level 2)\n' +
        '  - Peluang CH Bulanan > 300 mm > 50.0% → WASPADA (Level 1)\n\n' +
        '• Penggabungan: status_pdcht = max(level_dasarian, level_bulanan). Nilai tepat 50.0% tidak memicu peringatan.'
    },
    {
      id: 'sintesis-status-akhir',
      group: 'OPERASIONAL',
      groupLabel: 'Istilah Operasional',
      term: 'Prinsip Sintesis Status Akhir (Worst-Case Safety)',
      shortDesc: 'Penggabungan status_final = max(status_pdkm, status_pdcht) dengan atribusi hazard transparan.',
      content: '1. Rumus Sintesis: status_akhir = max(status_pdkm, status_pdcht).\n' +
        '2. Atribusi Ancaman: DROUGHT (jika PDKM > PDCHT), HEAVY_RAIN (jika PDCHT > PDKM), MULTI_HAZARD (jika keduanya setara > 0), atau NORMAL (jika keduanya Level 0).\n' +
        '3. Seluruh pemicu aktif dari kedua instrumen ditampilkan transparan pada rincian stasiun.'
    },
    {
      id: 'spi-peran-dasarian-bulanan',
      group: 'OPERASIONAL',
      groupLabel: 'Istilah Operasional',
      term: 'Peran Multi-Skala SPI: Dasarian (30D/90D), Harian, dan Bulanan',
      shortDesc: 'SPI Dasarian 30D sebagai pemicu utama PDKM; 90D sebagai pendamping; Harian & Bulanan sebagai konteks.',
      content: '1. SPI Dasarian 30D (Acuan Otoritatif): Satu-satunya skala SPI yang memicu status PDKM (Waspada, Siaga, Awas).\n' +
        '2. SPI Dasarian 90D (Pendamping Informatif): Memantau tren kekeringan jangka menengah (3 bulan), tidak memicu PDKM secara mandiri.\n' +
        '3. SPI Harian (30D & 90D): Pemantauan dinamika kebasahan harian secara langsung sebelum periode dasarian berakhir.\n' +
        '4. SPI Bulanan (1 Bulan): Analisis klimatologis jangka panjang antar-tahun.'
    },
    {
      id: 'data-parsial-incomplete',
      group: 'OPERASIONAL',
      groupLabel: 'Istilah Operasional',
      term: 'Perlakuan Data Parsial, Tidak Lengkap, & Kebijakan ARG',
      shortDesc: 'Larangan zero-fill, larangan auto-hijau, evaluasi parsial jujur, dan kebijakan 5 stasiun ARG.',
      content: '1. Larangan Zero-Fill: Data kosong (null/NaN/—) tidak pernah diubah menjadi 0.0.\n' +
        '2. Larangan Auto-Hijau: Indikator wajib yang belum lengkap tidak boleh otomatis dilabeli NORMAL/HIJAU.\n' +
        '3. Evaluasi Parsial: Jika salah satu indikator tersedia sudah melampaui ambang bahaya, peringatan tetap ditampilkan dengan catatan Evaluasi Parsial.\n' +
        '4. Status INCOMPLETE: Diberikan bila tidak ada indikator bahaya namun input utama belum lengkap.\n' +
        '5. Kebijakan ARG: 5 stasiun ARG dievaluasi murni berbasis HTH observasi; nilai SPI berstatus NULL/Tidak Tersedia dan dilarang diisi 0.00 palsu.'
    },
    {
      id: 'missing-ttu-aturan',
      group: 'OPERASIONAL',
      groupLabel: 'Istilah Operasional',
      term: 'Aturan Normalisasi TTU dan Kode 9999 / Missing Data',
      shortDesc: 'Interpretasi resmi TTU (0.0 mm) dan 9999 / Missing (NaN) sesuai sumber data dan kebijakan sistem.',
      content: 'Sesuai aturan normalisasi data curah hujan DSS-PIK:\n\n' +
        '• TTU (Tidak Terukur / Trace): Hujan terjadi dengan tinggi < 0.5 mm sehingga tidak terukur presisi. Dinormalisasi menjadi 0.0 mm dan TIDAK memutus deret Hari Tanpa Hujan (HTH).\n' +
        '• OBSERVED_ZERO (0 / -): Tidak ada hujan terukur (0.0 mm).\n' +
        '• 9999 / MISSING / DAMAGED / AMBIGUOUS: Menandakan data tidak tersedia, rusak, atau tidak pasti. Dalam pengolahan numerik diperlakukan sebagai NaN (bukan nol) dan memutus deret HTH secara konservatif.\n' +
        '• VOID: Catatan yang dibatalkan dikecualikan dari analisis aktif dan ekspor.\n' +
        '• Catatan SPI: Penanganan nilai NaN/9999 pada perhitungan SPI tetap mengikuti acuan package SPEI dan ketentuan teknis resmi yang telah disahkan pada sistem.'
    },
    {
      id: 'cara-membaca-tabel',
      group: 'OPERASIONAL',
      groupLabel: 'Istilah Operasional',
      term: 'Cara Membaca Tabel Peringatan Dini & Indikator Stasiun',
      shortDesc: 'Panduan singkat menafsirkan kolom utama pada tabel evaluasi operasional.',
      content: '1. HTH: Jumlah hari berturut-turut tanpa hujan terukur (>= 1.0 mm) hingga tanggal cutoff.\n' +
        '2. pb20: Peluang CH dasarian < 20 mm (memicu WASPADA PDKM jika > 70.0%).\n' +
        '3. SPI 30D (Otoritatif) & SPI 90D (Pendamping): Anomali kebasahan/kekeringan 30 dan 90 hari.\n' +
        '4. pa150, pa200, pa300 & Bulanan >300/>400/>500 mm: Peluang CH tinggi (memicu PDCHT jika > 50.0%).\n' +
        '5. Status Gabungan (Overall Level): Tingkat bahaya tertinggi antara PDKM dan PDCHT.\n' +
        '6. Status Evaluasi: COMPLETE (Lengkap), PARTIAL (Parsial dengan peringatan aktif), atau INCOMPLETE (Belum lengkap).'
    },
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

  const umumItems = useMemo(
    () => filteredItems.filter((it) => it.group === 'UMUM'),
    [filteredItems]
  );

  const operasionalItems = useMemo(
    () => filteredItems.filter((it) => it.group === 'OPERASIONAL'),
    [filteredItems]
  );

  return (
    <div className="kamus-page-wrapper">
      {/* 1. Header Banner */}
      <div className="kamus-header-banner">
        <div className="kamus-header-left">
          <div className="kamus-badge-pill">
            <BookOpen size={16} />
            <span>Referensi Resmi DSS-PIK</span>
          </div>
          <h2 className="kamus-main-title">Kamus</h2>
          <p className="kamus-main-desc">
            Referensi resmi istilah umum meteorologi/klimatologi serta istilah dan alur operasional DSS-PIK di {INSTITUTION_SHORT_NAME}.
          </p>
        </div>
      </div>

      {/* 2. Search & Group Filter Bar */}
      <div className="kamus-search-card">
        <div className="kamus-search-box">
          <Search size={16} className="kamus-search-icon" />
          <input
            type="text"
            placeholder="Cari istilah, singkatan, ambang batas, atau alur operasional..."
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

        {/* Filter Kategori: Semua, Istilah Umum, Istilah Operasional */}
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
            <span>Istilah Operasional</span>
          </button>
        </div>
      </div>

      {/* 3. Glossary Items Displayed in Two Sections */}
      <div className="kamus-items-container">
        <div className="kamus-results-meta">
          <span>
            Menampilkan <strong>{filteredItems.length}</strong> istilah terdaftar
          </span>
          {searchQuery && (
            <span className="search-filter-tag">Pencarian: &quot;{searchQuery}&quot;</span>
          )}
        </div>

        {filteredItems.length === 0 ? (
          <div className="kamus-empty-state">
            <HelpCircle size={32} className="text-muted" />
            <p className="empty-title">Tidak ada istilah yang cocok</p>
            <p className="empty-desc">Coba gunakan kata kunci lain atau pilih &quot;Semua Istilah&quot;.</p>
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
                    const isExpanded = expandedItems[item.id] !== false;
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
                            <p className="kamus-full-content" style={{ whiteSpace: 'pre-line' }}>
                              {item.content}
                            </p>
                          </div>
                        )}
                      </div>
                    );
                  })}
                </div>
              </section>
            )}

            {/* GROUP 2: ISTILAH OPERASIONAL */}
            {(activeGroupFilter === 'ALL' || activeGroupFilter === 'OPERASIONAL') &&
              operasionalItems.length > 0 && (
                <section className="kamus-section-group" aria-labelledby="section-istilah-operasional">
                  <div className="kamus-group-header">
                    <div className="kamus-group-header-left">
                      <Activity size={18} className="text-forest" />
                      <h3 id="section-istilah-operasional" className="kamus-group-title">
                        Istilah Operasional
                      </h3>
                    </div>
                    <span className="badge-count-pill">{operasionalItems.length} Istilah</span>
                  </div>

                  <div className="kamus-accordion-list">
                    {operasionalItems.map((item) => {
                      const isExpanded = expandedItems[item.id] !== false;
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
                              <p className="kamus-full-content" style={{ whiteSpace: 'pre-line' }}>
                                {item.content}
                              </p>
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
