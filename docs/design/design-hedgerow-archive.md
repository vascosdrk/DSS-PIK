# DESIGN SYSTEM DSS-PIK BMKG: HEDGEROW
## BMKG Stasiun Meteorologi Kelas I Raja Haji Fisabilillah Tanjungpinang

Dokumen ini adalah **Locked Design System** untuk Decision Support System Peringatan Iklim (DSS-PIK) Kepulauan Riau, dibangun di atas fondasi tema **Hedgerow** (Nutlope/Hallmark) dan disesuaikan secara presisi untuk kebutuhan operasional forecaster dan analis iklim BMKG.

---

### 1. Filosofi & Karakter Visual
- **Genre**: Editorial / Field Guide (Utilitarian, Precise, Calm, Restrained).
- **Nuansa**: Technical operational dashboard, bukan template generic SaaS atau AI-generated dashboard.
- **Surface**: Square, flat, hairlines (`1px` solid rules), zero drop-shadows yang melayang tidak tentu arah.
- **Controls**: Pill controls bertaraf presisi tinggi (`radius: 999px`) dengan kontras aksen chartreuse/moss.

---

### 2. Design Tokens (Spesifikasi Hedgerow Asli)

```css
:root {
  /* Surfaces / Paper */
  --color-paper: oklch(24% 0.052 158);       /* #1b2f25 - Primary Leaf-Green Canvas */
  --color-paper-2: oklch(19.5% 0.045 158);   /* #15251d - Inset Well / Darker Band */
  --color-paper-3: oklch(29.5% 0.05 158);    /* #223c30 - Elevated Surface / Card */
  --color-paper-4: oklch(34% 0.055 158);     /* #2a493a - Highlight Surface / Table Row Hover */

  /* Inks & Typography */
  --color-ink: oklch(93% 0.022 88);          /* #f6f1e8 - Primary Cream Ink */
  --color-ink-2: oklch(81% 0.035 150);       /* #c2d8cc - Secondary Technical Text */
  --color-muted: oklch(69% 0.045 150);       /* #9cb9a9 - Labels, Table Heads, Captions */

  /* Hairline Rules */
  --color-rule: oklch(35% 0.05 158);         /* #305141 - Structural 1px Rule */
  --color-rule-subtle: oklch(28% 0.04 158);  /* Subdued Hairline */

  /* Sinyal & Aksen */
  --color-accent: oklch(87% 0.19 118);       /* #d6f738 - Chartreuse Signal */
  --color-accent-2: oklch(92% 0.13 118);     /* Chartreuse Hover */
  --color-accent-deep: oklch(46% 0.12 128);  /* Deep Moss Green */
  --color-accent-ink: oklch(22% 0.05 158);   /* Dark Leaf-Green Ink for Buttons */
  --color-focus: oklch(92% 0.13 118);        /* High-Visibility Focus Outline */

  /* Tipografi */
  --font-display: "Prata", Georgia, serif;
  --font-body: "Manrope", ui-sans-serif, system-ui, sans-serif;
  --font-mono: "IBM Plex Mono", Consolas, monospace;

  /* Geometri */
  --radius-card: 0px;
  --radius-pill: 999px;
  --rule-hair: 1px;
}
```

---

### 3. Semantic Warning Colors (Standar Operasional BMKG)
Semantik tingkat peringatan BMKG wajib konsisten di seluruh dashboard (KPI, Peta, Tabel, Drawer, Modal):
- **AWAS**: Merah operasional (`#ef4444` / `oklch(55% 0.22 25)`).
- **SIAGA**: Oranye operasional (`#f97316` / `oklch(68% 0.19 50)`).
- **WASPADA**: Kuning/Amber operasional (`#eab308` / `oklch(78% 0.16 80)` atau Biru untuk PDCHT).
- **AMAN / NORMAL**: Hijau tenang operasional (`#10b981` / `oklch(65% 0.15 145)`).
- **INCOMPLETE / DATA PARSIAL**: Abu-abu netral (`#94a3b8` / `oklch(50% 0.02 150)`).

---

### 4. Komponen Kunci Dashboard

#### A. Header Institusional
- Menampilkan logo resmi BMKG (`/bmkg-logo.png`).
- Judul: `DSS-PIK` dalam font `Prata` (aksen chartreuse).
- Subjudul: *"Decision Support System Peringatan Iklim Kepri • Stasiun Meteorologi Raja Haji Fisabilillah Tanjungpinang"*.
- Menu navigasi tab berbentuk pill control bersih: **Peringatan Dini**, **Data Center**, **Kamus Istilah**.
- Tombol aksi utama: **Segarkan & Evaluasi** berbentuk pill bergaris chartreuse yang berubah menjadi solid chartreuse saat di-hover.

#### B. KPI Cards
- Menggunakan tipografi angka `Prata` display 400 berukuran besar (2.1rem) yang elegan dan mudah dibaca cepat.
- Latar kartu flat (`var(--color-paper-3)`) tanpa rounded corners berlebihan (`border-radius: 0`).
- Border tipis `1px solid var(--color-rule)` dengan aksen warna semantik pada angka dan border kiri.

#### C. Dual Hazard Selector (PDKM vs PDCHT)
- Pemisahan visual tegas antara **PDKM (Kekeringan Meteorologis)** dengan tone amber/warm dan **PDCHT (Curah Hujan Tinggi)** dengan tone blue/cool.
- Seluruh metrik KPI, peta, marker, dan tabel secara responsif mengikuti bahaya yang sedang aktif.

#### D. Peta Interaktif Leaflet
- Bingkai peta menyatu rapi dengan ground Hedgerow.
- Marker status peringatan dengan warna semantik operasional yang kontras terhadap basemap.
- Popup informasi stasiun yang bersih dan tabular tanpa dekorasi berlebihan.

#### E. Station Detail Drawer
- Bergaya dossier / field guide teknis.
- Menampilkan identitas stasiun, koordinat, ZOM, elevasi, dan riwayat HTH.
- Urutan evaluasi PDKM kanonikal:
  1. **Hari Tanpa Hujan (HTH)**
  2. **SPI 90D (Parameter Utama PDKM)**
  3. **SPI 30D (Indikator Pendukung)**
  4. **Pb20 (Peluang CH < 20 mm)**
- Evaluasi PDCHT: Pa150, Pa200, Pa300 dan probabilitas bulanan Pm300/400/500.

#### F. Data Center & Tabel
- Tabel dirancang seperti *still log* teknis dengan angka tabular `IBM Plex Mono`.
- Baris tabel dipisahkan oleh garis rambut `1px` halus, dengan highlight baris aktif bernuansa kertas Hedgerow (`var(--color-paper-4)`).

---

### 5. Aturan Anti-AI-Slop
1. Dilarang menggunakan backdrop-blur / glassmorphism dekoratif.
2. Dilarang menggunakan gradient warna-warni acak pada teks atau tombol.
3. Dilarang menggunakan drop-shadow mengambang berlebihan.
4. Gunakan elipsis sejati (`…`) alih-alih tiga titik (`...`).
5. Jangan gunakan huruf kapital berlebihan (all-caps) dengan letter-spacing renggang untuk teks biasa.
6. Seluruh halaman baru atau pembaruan komponen wajib mematuhi aturan desain dalam dokumen ini.

