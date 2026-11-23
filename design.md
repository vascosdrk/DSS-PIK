# LOCKED DESIGN SYSTEM DSS-PIK BMKG: COBALT
## BMKG Stasiun Meteorologi Kelas II Raja Haji Fisabilillah Tanjungpinang

**Versi:** 2.0 (Phase 5.1 — Hallmark Cobalt Modern-Minimal)  
**Status:** Locked Design System  
**Arsip Tema Sebelumnya:** [`docs/design/design-hedgerow-archive.md`](docs/design/design-hedgerow-archive.md)

---

### 1. Karakter Visual & Filosofi
- **Genre**: Modern-Minimal / Technical Operational Register.
- **Tone**: Engineered, precise, calm, high-contrast, uncluttered, utilitarian.
- **Atmosfer**: Clean cool-white surface dengan tipografi teknis yang mudah dibaca forecaster dan operator iklim BMKG selama shift operasional panjang.
- **Prinsip Kontras**: Menggunakan aksen *Electric Cobalt Blue* secara hemat (maksimal 5% dari luas visual) untuk menandai fokus, navigasi aktif, dan tombol tindakan primer.
- **Geometri**: Hairlines halus (`1px`), border radius terukur (`4px` untuk kartu dan input, `999px` untuk pill controls), tanpa drop-shadow mengambang berlebihan.

---

### 2. Design Tokens (Spesifikasi Resmi Cobalt)

```css
:root {
  /* Surfaces / Paper (Cool Engineered Light Ground) */
  --color-paper: oklch(98.5% 0.005 250);        /* #f8fafc - Primary Canvas */
  --color-paper-2: oklch(96.5% 0.008 252);      /* #f1f5f9 - Secondary Toolbar / Inset Well */
  --color-paper-3: oklch(100% 0 0);             /* #ffffff - Card & Surface Ground */
  --color-paper-4: oklch(94% 0.012 252);        /* #e2e8f0 - Row Hover & Elevated State */

  /* Inks & Text (High Contrast Technical Readability) */
  --color-ink: oklch(22% 0.028 260);            /* #0f172a - Main Charcoal Ink */
  --color-ink-2: oklch(36% 0.024 258);          /* #334155 - Secondary Technical Text */
  --color-muted: oklch(52% 0.02 256);           /* #64748b - Metadata, Table Heads, Captions */

  /* Hairlines & Dividers */
  --color-rule: oklch(90% 0.01 252);            /* #e2e8f0 - Subtle Hairline Rule */
  --color-rule-2: oklch(84% 0.014 252);         /* #cbd5e1 - Distinct Boundary Divider */

  /* Primary Accent: Electric Cobalt Blue */
  --color-accent: oklch(56% 0.20 256);          /* #2563eb - Electric Cobalt */
  --color-accent-2: oklch(48% 0.22 256);        /* #1d4ed8 - Cobalt Hover */
  --color-accent-wash: oklch(96% 0.025 256);    /* Subtle Cobalt Tint for Active Rows/Tags */
  --color-accent-ink: #ffffff;                  /* White on Cobalt */
  --color-focus: oklch(56% 0.20 256);           /* Focus Ring */

  /* Typography Stack */
  --font-display: "Space Grotesk", system-ui, sans-serif;
  --font-body: "Inter", system-ui, sans-serif;
  --font-mono: "JetBrains Mono", Consolas, monospace;

  /* Geometry & Restraint */
  --radius-card: 4px;
  --radius-input: 4px;
  --radius-pill: 999px;
  --rule-hair: 1px;
}
```

---

### 3. Semantik Status Peringatan BMKG (Wajib Invariant)
Semantik tingkat peringatan BMKG dipertahankan secara tegas namun tidak mendominasi seluruh kartu, melainkan berupa aksen status line, badge, atau teks numerik:
- **AWAS**: Merah operasional (`#dc2626` / teks `#b91c1c` / bg `#fef2f2`).
- **SIAGA**: Oranye operasional (`#ea580c` / teks `#c2410c` / bg `#fff7ed`).
- **WASPADA**: Kuning/Amber operasional (`#d97706` / teks `#b45309` / bg `#fffbeb`).
- **NORMAL / AMAN**: Hijau operasional (`#16a34a` / teks `#15803d` / bg `#f0fdf4`).
- **INCOMPLETE / DATA PARSIAL**: Abu-abu netral (`#64748b` / teks `#475569` / bg `#f8fafc`).

---

### 4. Arsitektur Komponen

#### A. Header Institusional Resmi BMKG
- Berlatar belakang putih bersih (`var(--color-paper-3)`) dengan border bawah tipis `1px solid var(--color-rule)`.
- Memuat logo resmi BMKG resolusi tinggi (`/bmkg-logo.png`).
- Judul: `DSS-PIK` dalam font `Space Grotesk` 700.
- Subjudul: *"Decision Support System Peringatan Iklim Kepri • Stasiun Meteorologi Raja Haji Fisabilillah Tanjungpinang"*.
- Menu navigasi tab berbentuk pill control bersih dengan active state cobalt (`Peringatan Dini`, `Data Center`, `Kamus Istilah`).
- Tombol aksi utama: **Segarkan & Evaluasi** berbentuk pill solid electric cobalt (`#2563eb`).

#### B. Period & System Information Banner
- Format horizontal ringkas yang menyajikan target periode, cutoff data observasi, dan waktu pembaruan sistem.
- Dropdown periode dengan border hairline yang rapi dan focus ring cobalt.

#### C. KPI Cards
- Angka statistik besar dan tegas menggunakan font monospace `JetBrains Mono` (28–36px) agar angka mudah terbaca dan tidak bergeser.
- Latar kartu putih (`#ffffff`) dengan border hairline `1px solid var(--color-rule)` dan aksen warna semantik pada angka.

#### D. Dual Hazard Selector (PDKM vs PDCHT)
- Pemisahan visual tegas antara PDKM (Kekeringan Meteorologis) dan PDCHT (Curah Hujan Tinggi).
- Active state ditandai dengan pill cobalt yang bersih.

#### E. Peta Interaktif Leaflet & Daftar Prioritas
- Peta berbingkai rapi menyatu dengan surface Cobalt.
- Daftar Titik Perhatian Khusus menggunakan kartu berlatar terang dengan penanda badge pill semantik dan navigasi cepat ke drawer stasiun.

#### F. Station Detail Drawer
- Bergaya dossier teknis terang dengan hierarki visual yang jelas:
  1. HTH (Hari Tanpa Hujan).
  2. SPI 90D (Parameter Utama PDKM).
  3. SPI 30D (Indikator Pendukung).
  4. Pb20 (Peluang CH < 20 mm).
- Evaluasi PDCHT: Pa150, Pa200, Pa300 dan probabilitas bulanan Pm300/400/500.

#### G. Data Center & Tabel
- Tabel dirancang presisi dengan header cool-gray bertingkat, angka rata kanan dalam font monospace `JetBrains Mono`, dan sticky column untuk nama stasiun.

---

### 5. Aturan Anti-AI-Slop & Kualitas
1. Dilarang menggunakan font serif (Prata telah dihapus sepenuhnya).
2. Dilarang menggunakan latar belakang hijau gelap atau aksen neon/chartreuse.
3. Dilarang menggunakan efek glassmorphism, blur berlebih, atau gradient warna-warni.
4. Gunakan elipsis sejati (`…`).
5. Aksen cobalt dibatasi maksimal 5% dari luas visual.
