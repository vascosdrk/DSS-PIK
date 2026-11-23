# FRONTEND VISUAL SYSTEM — DSS-PIK BMKG KEPULAUAN RIAU
## Spesifikasi Desain Antarmuka, Token Warna & Sistem Tema Cobalt Phase 5.2

---

## 1. FILOSOFI DESAIN & PRINSIP UTAMA

Desain antarmuka DSS-PIK dirancang berdasarkan prinsip utama:
> **READABILITY & DATA DENSITY OVER DECORATION**  
> *(Keterbacaan & Kepadatan Data Lebih Utama daripada Dekorasi)*

Sebagai sistem pemantauan dan peringatan dini operasional di lingkungan BMKG, setiap angka, status, tanggal, dan alasan peringatan harus dapat dibaca dalam hitungan detik oleh operator dinas tanpa distraksi estetika berlebih.

---

## 2. INTEGRASI HALLMARK & SEJARAH TEMA

- **Design Engine**: [Hallmark](https://github.com/Nutlope/hallmark)
- **Status Repository Upstream**: Tersimpan di `vendor/hallmark-upstream/` (Commit SHA: `52328cb3129135499e4e178d4864ee90029dea2b`).
- **Skill Terintegrasi**: `.agents/skills/hallmark/SKILL.md`.
- **Evolusi Desain**:
  - *Tahap Awal*: Antarmuka SaaS konvensional generik.
  - *Phase 5 (Hedgerow)*: Eksplorasi tema editorial hijau pekat (`#132a13`, `#0d1f12`). Kurang cocok untuk ruang operasional klimatologi karena terlalu gelap dan aksen chartreuse bersaing dengan data.
  - *Phase 5.1 & 5.2 (Cobalt + BMKG Atmospheric Gradients)*: **TEMA AKTIF SAAT INI**. Bersih, terang, tenang, berbasis biru kobalt dengan aksen gradien biru-kehijauan atmosferik khas BMKG.

---

## 3. BERKAS SOURCE OF TRUTH DESAIN

1. **`frontend/src/cobalt-theme.css`**: Berkas CSS tunggal yang mengontrol seluruh token variabel, komponen header, kartu KPI, tabel, peta, laci detail, dan modal.
2. **`frontend/index.html`**: Pemuatan font Google:
   - `Space Grotesk`: Heading dan Brand Title
   - `Inter`: Body text, navigasi, dan label form
   - `JetBrains Mono`: Seluruh nilai numerik, SPI, curah hujan, koordinat, dan timestamp
3. **`frontend/public/bmkg-logo.png`**: Logo resmi BMKG beresolusi tinggi.

---

## 4. SISTEM TOKEN WARNA (DESIGN TOKENS)

### A. Nuansa Atmosferik BMKG (Atmospheric Gradients)
```css
/* Atmospheric Canvas Wash */
--bmkg-sky-wash: radial-gradient(at 15% 15%, rgba(14, 165, 233, 0.035) 0px, transparent 55%),
                 radial-gradient(at 85% 85%, rgba(20, 184, 166, 0.035) 0px, transparent 55%),
                 linear-gradient(180deg, rgba(241, 245, 249, 0.6) 0%, rgba(248, 250, 252, 1) 320px);

/* Deep Marine Header Gradient */
--bmkg-header-grad: linear-gradient(135deg, #0f2744 0%, #173860 30%, #1e4b82 70%, #165b7e 100%);

/* Hairline Cyan-Teal Border */
--bmkg-header-border: linear-gradient(90deg, #38bdf8 0%, #2dd4bf 50%, #3b82f6 100%);

/* Institutional Banner Wash */
--bmkg-banner-wash: linear-gradient(90deg, #f0f9ff 0%, #f0fdfa 40%, #ffffff 80%);
```

### B. Warna Semantik Status Peringatan BMKG (Wajib Konsisten)
| Status | Latar Belakang (Badge) | Warna Teks | Border | HEX Primer |
|---|---|---|---|---|
| **AWAS** | `#fef2f2` | `#991b1b` | `#f87171` | `#dc2626` (Red) |
| **SIAGA** | `#fff7ed` | `#9a3412` | `#fb923c` | `#ea580c` (Orange) |
| **WASPADA** | `#fefce8` | `#854d0e` | `#facc15` | `#eab308` (Amber) |
| **NORMAL / AMAN** | `#f0fdf4` | `#166534` | `#4ade80` | `#16a34a` (Green) |
| **INCOMPLETE / PARTIAL** | `#f8fafc` | `#475569` | `#cbd5e1` | `#64748b` (Slate) |

---

## 5. SPESIFIKASI KOMPONEN UTAMA

### A. Institutional Header
- **Latar Belakang**: `--bmkg-header-grad` (Deep Marine Navy ke Teal Wash).
- **Teks Judul (`DSS-PIK`)**: Putih murni (`#ffffff`), font Space Grotesk, tebal 700.
- **Teks Subjudul**: Biru es cerah (`#bae6fd`), font Inter, kontras tinggi.
- **Navigasi Tab Kapsul**:
  - Tab Aktif: Latar solid putih (`#ffffff`), teks biru laut (`#0369a1`), tebal 700.
  - Tab Inaktif: Teks ice blue (`#e0f2fe`), transparan dengan hover efek halus.
- **Metadata (Cakupan Wilayah & Pembaruan)**:
  - Label: Cyan cerah (`#7dd3fc`), uppercase.
  - Nilai: Putih bersih (`#ffffff`), font JetBrains Mono.

### B. Halaman Login (Login Card)
- **Latar Belakang Layar**: Radial gradient deep marine navy (`#0f2744`) dengan aksen radial glow lembut.
- **Permukaan Kartu**: Solid White (`#ffffff`), sudut membulat 16px, border atas aksen gradien tipis 3px.
- **Logo BMKG**: Berada di atas, tinggi 72px, drop shadow lembut, terpusat.
- **Hierarki Teks**:
  1. `DSS-PIK` (Terpusat, Space Grotesk, warna `#0f2744`)
  2. `Decision Support System Peringatan Iklim Kepri` (Warna `#1e3a8a`, font-weight 600)
  3. `Stasiun Meteorologi Raja Haji Fisabilillah` (Warna `#64748b`, font-weight 500)
- **Tombol Masuk**: Gradien biru laut BMKG (`#0284c7` ke `#0369a1`), font tebal, efek hover elevasi halus.

### C. Kartu KPI Operasional
- **Permukaan**: 100% Solid White (`#ffffff`) untuk mencegah kelelahan mata.
- **Garis Aksen Atas**: Ketebalan 2px sesuai warna semantik masing-masing kartu.
- **Angka Metrik**: Font JetBrains Mono berukuran besar (`1.85rem`), kontras tinggi terhadap latar putih.

### D. Tabel Peringatan Dini & Station Detail Drawer
- Seluruh baris data menggunakan latar putih solid dengan baris alternate abu-abu sangat muda (`#f8fafc`).
- Hover baris: Soft Sky Wash (`#f0f9ff`).
- Laci detail stasiun: Header bergradien biru BMKG halus, isi drawer berupa kartu-kartu putih bersih dengan label parameter jelas dan nilai monospaced terstruktur.

---

## 6. LARANGAN DESAIN BAGI PENGEMBANG / AI BERIKUTNYA

1. **DILARANG** mengembalikan tema visual menjadi gelap menyeluruh (*all-dark/Hedgerow*) tanpa instruksi pengguna.
2. **DILARANG** menempatkan gradien atau gambar latar langsung di belakang angka KPI, isi sel tabel, atau teks alasan peringatan yang dapat menurunkan rasio kontras WCAG.
3. **DILARANG** mengubah font data numerik dari `JetBrains Mono` menjadi font proporsional, karena font tabular monospaced wajib untuk konsistensi pembacaan data klimatologi.
4. **DILARANG** memodifikasi warna semantik status operasional (Merah = Awas, Oranye = Siaga, Kuning = Waspada, Hijau = Normal).

