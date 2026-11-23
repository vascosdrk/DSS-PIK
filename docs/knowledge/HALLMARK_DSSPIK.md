# DOKUMENTASI PROJECT KNOWLEDGE: INTEGRASI HALLMARK & TEMA HEDGEROW
## DSS-PIK BMKG STASIUN METEOROLOGI KELAS II RAJA HAJI FISABILILLAH TANJUNGPINANG

Dokumen ini adalah referensi permanen integrasi Hallmark ke dalam repositori DSS-PIK BMKG Tanjungpinang.

---

### 1. Sumber Resmi & Metadata Upstream
- **Repository Resmi**: [https://github.com/Nutlope/hallmark](https://github.com/Nutlope/hallmark)
- **Website Resmi**: [https://www.usehallmark.com/](https://www.usehallmark.com/)
- **Commit SHA Upstream**: `52328cb3129135499e4e178d4864ee90029dea2b`
- **Tanggal Komit Upstream**: `2026-11-03T09:00:59Z`
- **Lisensi**: MIT License (Nutlope / Hallmark)
- **Lokasi Vendor Upstream**: `vendor/hallmark-upstream/`

---

### 2. Lokasi Skill Project
- **Direktori Skill**: `.agents/skills/hallmark/`
- **File Utama Instruksi**: `.agents/skills/hallmark/SKILL.md`
- **Skrip Operasional**: `.agents/skills/hallmark/scripts/` (termasuk `sloplint.mjs`, `theme.mjs`, `capture.mjs`)
- **Referensi Tema & Genre**: `.agents/skills/hallmark/references/` (termasuk `themes/hedgerow.md`)

---

### 3. Tema Terpilih: HEDGEROW (Editorial / Dark Leaf-Green Paper)
Karakteristik desain Hedgerow diadaptasi untuk dashboard meteorologi operasional BMKG:
- **Genre**: Editorial / Field Guide (Utilitarian, Precise, Calm, Restrained).
- **Ground / Paper**:
  - `--color-paper`: `oklch(24% 0.052 158)` (deep leaf-green, bukan hitam generik atau abu-abu SaaS).
  - `--color-paper-2`: `oklch(19.5% 0.045 158)` (well / darker band).
  - `--color-paper-3`: `oklch(29.5% 0.05 158)` (elevated surface / lighter card).
- **Ink / Typography**:
  - `--color-ink`: `oklch(93% 0.022 88)` (cream ink).
  - `--color-ink-2`: `oklch(81% 0.035 150)` (secondary text).
  - `--color-muted`: `oklch(69% 0.045 150)` (metadata / table heads / captions).
- **Aturan / Rules**:
  - `--color-rule`: `oklch(35% 0.05 158)` (1px hairline border / divider).
- **Aksen & Sinyal**:
  - `--color-accent`: `oklch(87% 0.19 118)` (chartreuse signal).
  - `--color-accent-deep`: `oklch(46% 0.12 128)` (moss green untuk kontras di latar terang/cream).
- **Tipografi**:
  - Display / Headings: `Prata`, Georgia, serif (high-contrast, editorial).
  - Body & UI: `Manrope`, system-ui, sans-serif (clean, highly readable technical text).
  - Monospace Data: `IBM Plex Mono`, monospace (angka tabular, koordinat, ID stasiun, metrik).
- **Surface & Geometri**:
  - Card & input: `--radius-card: 0` (flat, square, no floating shadows, no rounded bubbles).
  - Control pills: `--radius-pill: 999px` (chartreuse pill buttons & badges).
  - Depth: Menggunakan kontras nilai kertas (paper steps), bukan drop-shadow kabur.

---

### 4. Semantic Status Peringatan BMKG (Wajib Dipertahankan)
Meskipun tema Hedgerow mendominasi atmosfer visual, semantik peringatan operasional BMKG dipertahankan secara tegas:
- **AWAS**: Merah operasional (`oklch(55% 0.22 25)` / `#dc2626`).
- **SIAGA**: Oranye operasional (`oklch(68% 0.19 50)` / `#ea580c`).
- **WASPADA**: Kuning/Amber operasional (`oklch(78% 0.16 80)` / `#d97706` atau Biru untuk PDCHT).
- **AMAN / NORMAL**: Hijau tenang (`oklch(65% 0.15 145)` / `#16a34a`).
- **INCOMPLETE / DATA PARSIAL**: Abu-abu netral (`oklch(50% 0.02 150)` / `#64748b`).

---

### 5. Skrip Audit & Anti-AI-Slop (Sloplint)
Untuk menjalankan audit kualitas desain dan mendeteksi anti-pattern AI-slop:
```powershell
node .agents/skills/hallmark/scripts/sloplint.mjs frontend/src/ --genre editorial --scope app
```

---

### 6. Aturan Khusus Pengembangan Frontend DSS-PIK
Setiap pekerjaan visual pada frontend DSS-PIK wajib membaca:
1. `.agents/skills/hallmark/SKILL.md`
2. `design.md`
3. `docs/knowledge/HALLMARK_DSSPIK.md`
4. Dilarang mengubah logika `decision_engine.py`, `period_service.py`, skema database MariaDB, atau Parquet.

