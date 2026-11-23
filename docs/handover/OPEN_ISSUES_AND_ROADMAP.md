# OPEN ISSUES & ROADMAP — DSS-PIK BMKG KEPULAUAN RIAU
**Inventarisasi Temuan Audit, Technical Debt, Mitigasi Risiko, dan Rekomendasi Rencana Pengembangan**  
**Institusi**: BMKG Stasiun Meteorologi Kelas II Raja Haji Fisabilillah Tanjungpinang  
**Status**: `VERIFIED CURRENT` (November 2026)

---

## 1. KLASIFIKASI TEMUAN AUDIT & TECHNICAL DEBT

Berdasarkan audit menyeluruh terhadap kode sumber, skema database, pengujian otomatis, dan file konfigurasi, berikut adalah daftar temuan operasional yang dikelompokkan berdasarkan tingkat urgensi:

### A. TEMUAN MINOR / OPERASIONAL (OPERATIONAL CONSIDERATIONS)

1. **Format Pemicu Kondisi pada Integrasi Eksternal (WordPress)**
   - *Kondisi*: Pada Phase 7.1, skema JSON terstandar menyeragamkan elemen `kecamatan[].recommendations.*.triggered_conditions` menjadi *array of objects* (berisi `indicator`, `value`, `unit`, `operator`, `threshold`, `period`, `station_code`, `station_name`, `description`). Pada format legacy terdahulu, kecamatan menggunakan *array of strings*.
   - *Status*: `RESOLVED IN DSS-PIK / COMPATIBILITY NOTE FOR WORDPRESS`.
   - *Mitigasi*: Jika parser WordPress pihak ketiga mengalami kendala rendering tabel pemicu tingkat kecamatan, plugin WordPress cukup membaca atribut `.description` dari objek pemicu.

2. **Status Rekaman Publikasi pada Tabel `cews_sih3_publications`**
   - *Kondisi*: Tabel `cews_sih3_publications` di MariaDB saat ini masih berisi `0` baris. Ekspor dan pratinjau JSON saat ini menghasilkan status `"Aktif"` (atau `"DRAFT"` secara dinamis).
   - *Status*: `NORMAL OPERATIONAL BEHAVIOR`.
   - *Penjelasan*: Hal ini wajar karena publikasi resmi formal (`APPROVE` -> `PUBLISH`) membutuhkan otorisasi pejabat berwenang secara bertahap saat sistem mulai beroperasi penuh.

3. **Ketergantungan Jalur Jaringan HTTP Plain pada LAN Kantor**
   - *Kondisi*: Server LAN FastAPI beroperasi pada protokol `http://` tanpa enkripsi TLS/HTTPS lokal.
   - *Status*: `ACCEPTED RISK FOR ISOLATED OFFICE LAN`.
   - *Mitigasi*: Untuk pengoperasian di jaringan kantor tertutup (isolated office LAN), hal ini aman dan memadai. Jika di kemudian hari sistem ingin diakses melalui jaringan publik atau lintas instansi, disarankan menambahkan reverse proxy Nginx/Caddy dengan sertifikat SSL/TLS.

4. **Ketiadaan Version Control Git Lokal pada Folder Kerja**
   - *Kondisi*: Direktori kerja saat ini tidak memiliki subdirektori `.git` lokal (proyek diposisikan sebagai standalone production export workspace).
   - *Status*: `MANAGED VIA PORTABLE BACKUP SCRIPTS`.
   - *Mitigasi*: Prosedur snapshot dan migrasi dikelola menggunakan script `prepare_dss_pik_migration.bat` dan backup terjadwal.

---

## 2. PEKERJAAN YANG SENGAJA DITUNDA (DEFERRED WORK)

1. **Otomatisasi Reverse Proxy HTTPS**:
   - Ditunda hingga sistem dipindahkan ke komputer server permanen di ruang operasional kantor BMKG.
2. **Sinkronisasi Otomatis API BMKG Pusat (Push/Pull Otomatis)**:
   - Saat ini input data operasional menggunakan model *Human-in-the-Loop* melalui Ingestion Wizard Excel di Data Center untuk menjamin kontrol kualitas forecaster sebelum data masuk ke database. Integrasi API otomatis penuh ditunda untuk fase pengembangan lanjutan setelah sistem LAN stabil.
3. **Penyimpanan Cloud Eksternal**:
   - Sistem dirancang dengan prinsip *Local-First* agar tetap dapat beroperasi tanpa ketergantungan internet saat terjadi pemadaman jaringan di pulau terluar Kepulauan Riau.

---

## 3. REKOMENDASI RENCANA PENGEMBANGAN BERIKUTNYA (MAX 5 REKOMENDASI)

Berdasarkan prioritas arsitektural dan kebutuhan operasional stasiun, berikut adalah **5 rekomendasi strategis** untuk tahap pengembangan selanjutnya:

### 1. Penyerahan Paket & Migrasi Fisik ke Server Kantor BMKG (Workstation/Server Deployment)
- **Tujuan**: Menyerahkan paket `releases/DSS-PIK_TECHNICIAN_HANDOVER_Phase7_4_20261122.zip` dan backup terpisah `C:\DSS_PIK_BACKUPS\backup_20261122_124358\` kepada teknisi IT BMKG setelah spesifikasi server dikonfirmasi (`TECHNICIAN_REQUIREMENTS.md`).
- **Langkah Pelaksanaan**:
  1. Konfirmasi OS, hardware, IP/DNS internal, dan kebijakan firewall/HTTPS server kantor.
  2. Ekstrak paket handover, buat `.env` baru (`README_SECRETS_PROVISIONING.md`), dan restore `cews_db`.
  3. Jalankan `setup_dss_pik_new_pc.bat`, jalankan `DSS-PIK.bat`, aktifkan LAN / reverse proxy, dan selesaikan `TECHNICIAN_CHECKLIST.md`.

### 2. Implementasi Reverse Proxy Lokal dengan HTTPS (Nginx / Caddy)
- **Tujuan**: Mengamankan transmisi kredensial login operator dan data operasional pada jaringan LAN kantor menggunakan sertifikat TLS lokal (misal menggunakan *mkcert* atau sertifikat internal BMKG).
- **Manfaat**: Mencegah potensi *packet sniffing* pada jaringan Wi-Fi bersama dan mengaktifkan fitur browser modern yang mensyaratkan *Secure Context* (HTTPS).

### 3. Pembangunan Modul Verifikasi Keberhasilan Prakiraan (Forecast Verification / Skill Score)
- **Tujuan**: Menambahkan tab evaluasi verifikasi pada Data Center untuk membandingkan secara otomatis antara probabilitas ECMWF (Pa/PM) yang diprakirakan dengan data curah hujan observasi aktual yang terjadi di kemudian hari.
- **Metrik Analisis**: Brier Score, Reliability Diagram, dan Relative Operating Characteristic (ROC).

### 4. Notifikasi Otomatis Terjadwal (Email / Telegram Bot Alert)
- **Tujuan**: Mengirimkan ringkasan peringatan dini secara otomatis kepada kepala stasiun, koordinator observasi, dan stakeholder daerah ketika status wilayah mencapai level `SIAGA` atau `AWAS`.
- **Implementasi**: Service latar belakang terjadwal yang membaca status publikasi aktif tanpa membebani thread utama FastAPI.

### 5. Adaptor Parser Khusus Integrasi WordPress (WordPress Plugin Helper)
- **Tujuan**: Menyediakan skrip pembantu (helper snippet/shortcode) pada WordPress yang secara otomatis memetakan objek `triggered_conditions` terbaru ke tabel HTML ringkas di situs web resmi BMKG.
- **Manfaat**: Memastikan transisi dari skema lama ke skema terstandar baru di sisi WordPress berjalan mulus tanpa mengubah inti kode portal.

---
*Rekomendasi di atas bersifat usulan strategis untuk pengembangan lanjutan dan tidak mengubah status baseline sistem saat ini.*


---

## Phase 8.0 Roadmap Update — Dockerization & Ubuntu Server Production (2026-11-22)

- **Completed (Phase 8.0)**: Official architecture documentation, permanent `.agents/rules/dss-pik-architecture.md`, `Dockerfile`, `.dockerignore`, `compose.yaml`, `.env.docker.example`, and Ubuntu deployment strategy.
- **Pending Blocker**: Install **Docker Desktop for Windows** (WSL2 is already enabled: `Default Version: 2`) to execute local Docker image build and isolated `:18000` staging verification.
- **Next Milestones**: Local Docker test (`127.0.0.1:18000`) -> Private Git repo & versioned release tag -> Authorized BMKG Office Ubuntu Server deployment. See `docs/deployment/DOCKERIZATION_ROADMAP.md`.

- **Completed (Phase 8.2.2)**: Resolved Docker bridge NAT HTTP 403 via `CEWS_DOCKER_LOCAL_ONLY=true`; verified `http://127.0.0.1:18000` (HTTP 200) and **42/42 tests PASSED** without weakening LAN security. Ready for Phase 8.3 (private Git repo, versioned release tag, Ubuntu Server production prep).

- **Completed (Phase 8.3)**: Packaged `v1.0.0` production release at `F:\TNJ\paper\DSS_PIK_PRODUCTION_RELEASE`. Remaining: handoff to BMKG IT technician for Ubuntu Server installation, reverse proxy/TLS, `ufw` firewall, and multi-PC LAN acceptance.
