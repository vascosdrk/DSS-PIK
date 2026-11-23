# PHASE 7.3 — UNIFIED LAUNCHER & MULTI-CLIENT LAN ACCESS REPORT
**Project**: Decision Support System Peringatan Iklim (DSS-PIK)  
**Institusi**: BMKG Stasiun Meteorologi Kelas II Raja Haji Fisabilillah Tanjungpinang  
**Tanggal Implementasi**: 22 November 2026  
**Baseline**: Phase 7.2 → Phase 7.3

---

## 1. ROOT CAUSE ANALISIS (STARTUP & MULTI-CLIENT LAN)

Melalui audit langsung terhadap server, jaringan, firewall, dan kode sumber, ditemukan akar masalah berikut:

1. **Fragmentasi Launcher & Ketiadaan Auto-Start MariaDB**:
   - Terdapat 6 skrip launcher operasional terpisah di root (`run_cews.bat`, `stop_cews.bat`, `run_cews_lan.bat`, `stop_cews_lan.bat`, `run_cews_prod.bat`, `stop_cews_prod.bat`).
   - `run_cews_prod.bat` melakukan binding pada `127.0.0.1:8000` (memblokir seluruh akses LAN), sementara `run_cews.bat` menjalankan Vite dev server port `5173`.
   - MariaDB 13.0 pada komputer server (`C:\Program Files\MariaDB 13.0\bin\mariadbd.exe`) berjalan sebagai binary standalone tanpa Windows Service terdaftar; launcher lama gagal menyalakan MariaDB saat kondisi OFF.
   - `stop_cews_lan.bat` langsung menjalankan `taskkill /F /PID` pada port 8000 tanpa verifikasi kepemilikan proses.
2. **Kendala Jaringan, Firewall, & Profil Wi-Fi Windows**:
   - Profil jaringan Wi-Fi aktif (`SM1-Fisabilillah`, IPv4 `192.168.1.72/24`) berada pada kategori **`Public`**.
   - Belum tersedia rule Inbound Windows Defender Firewall khusus DSS-PIK TCP port `8000` untuk subnet internal (`LocalSubnet`); hanya terdapat rule otomatis `python.exe` yang terbatas pada profil `Public` dan path Python lokal tertentu.
   - Proses audit berjalan non-elevated (`IsAdministrator=False`), sehingga pembuatan rule firewall baru memerlukan eksekusi satu kali oleh Administrator (perintah lengkap ditampilkan otomatis oleh `DSS-PIK.bat` dan pada Bagian 5).
3. **Isolasi Sesi & Concurrency Multi-User**:
   - `backend/auth.py` sebelumnya membuat token sesi tanpa unique identifier (`jti`), sehingga dua operator yang login pada detik yang sama memperoleh string token identik. Kini setiap login menghasilkan UUID `jti` unik per sesi/browser.
   - `backend/main.py` ditingkatkan dengan `threading.RLock()` (`_CACHE_LOCK`) untuk akses baca/muat cache SPI Parquet dan `threading.Lock()` (`_REGIONAL_WRITE_LOCK`) untuk serialisasi aman operasi simpan keputusan wilayah.
   - `frontend/.env.example` dibersihkan dari nilai hardcoded `http://127.0.0.1:8000` (menjadi `VITE_API_BASE_URL=` kosong untuk same-origin dinamis), dan `frontend/src/App.jsx` menghapus fallback string `http://127.0.0.1:8000` pada diagnostik koneksi.

---

## 2. ARSITEKTUR SEBELUM VS SESUDAH

| Aspek | Sebelum (Phase 7.2) | Sesudah (Phase 7.3) |
|---|---|---|
| **Entry Point Operator** | 6 file `.bat` terpisah (`run_cews*`, `stop_cews*`) | **1 file tunggal**: `DSS-PIK.bat` (auto-START saat OFF, menu STATUS/STOP/RESTART saat ON) |
| **Deteksi & Start MariaDB** | Hanya cek port 3306, gagal jika OFF | Deteksi otomatis MariaDB aktif → Windows Service → standalone `mariadbd.exe` / `mysqld.exe` + verifikasi query `cews_db` |
| **Shutdown & Port Guard** | `taskkill /F` pada port 8000 tanpa cek ownership | Verifikasi ketat ownership proses (`uvicorn` + `backend.main:app`), deteksi port conflict asing tanpa mematikan aplikasi lain, graceful shutdown + state/lock cleanup |
| **Serving Frontend** | Campuran Vite `:5173` vs FastAPI `:8000` | Tunggal satu origin melalui FastAPI `:8000` (`CEWS_SERVE_FRONTEND=true`) dari `frontend/dist/` |
| **Multi-User Session** | Stateless HMAC tanpa `jti` | Stateless HMAC dengan `jti` UUID4 unik per login; logout PC B tidak memengaruhi sesi PC C |
| **Concurrency Guard** | Hanya `_REFRESH_EVALUATE_LOCK` | Ditambah `_CACHE_LOCK` (RLock) & `_REGIONAL_WRITE_LOCK` (Lock) |

---

## 3. MEKANISME START, STOP, RESTART, & STATUS (`DSS-PIK.bat`)

- **Lokasi**: `DSS-PIK.bat` (root repository) + `backend/unified_launcher.py` (orchestrator internal).
- **Double-Click saat OFF**:
  1. Resolve `ROOT_DIR` otomatis (bebas hardcoded path).
  2. Cek dependensi Python inti, `.env`, dan kesegaran `frontend/dist/index.html`.
  3. Verifikasi MariaDB `cews_db` (otomatis start jika mati).
  4. Jalankan Uvicorn `0.0.0.0:8000` (`CEWS_ENV=production`, `CEWS_SERVE_FRONTEND=true`, `CEWS_ENABLE_DOCS=false`, `CEWS_COOKIE_SECURE=false`).
  5. Polling `/health` hingga `HTTP 200` + verifikasi `/` melayani HTML `HTTP 200`.
  6. Deteksi IPv4 LAN aktif (`192.168.1.72` pada adapter `Wi-Fi`), buka browser default PC Server ke `http://127.0.0.1:8000/`, dan tampilkan URL client + menu kontrol interaktif.
- **Double-Click saat ON**:
  - Tidak membuat instance ganda (idempotent). Menampilkan status berjalan dan menu: `[1] Buka Browser`, `[2] Restart`, `[3] Stop`, `[4] Refresh Status`, `[0] Tutup jendela (server tetap jalan)`.
- **Mode CLI**: `DSS-PIK.bat start|stop|restart|status [--no-browser] [--non-interactive]`.
- **Log Runtime**: `logs/runtime/launcher_unified.log` dan `logs/runtime/backend_lan.log`.

---

## 4. STATUS INFRASTRUKTUR & JARINGAN AKTUAL

- **MariaDB**: `13.0.2-MariaDB` (`C:\Program Files\MariaDB 13.0\bin\mariadbd.exe`, port `3306`, database `cews_db`, 57 stasiun). Shared instance tidak dimatikan saat STOP DSS-PIK.
- **Backend & Frontend Serving**: FastAPI + Uvicorn `0.0.0.0:8000` melayani production build `frontend/dist/` (`index-BRK1kGL_.js`, 693 KB).
- **Interface & URL LAN Aktual**:
  - Adapter aktif: `Wi-Fi` (`SM1-Fisabilillah`, IPv4 `192.168.1.72/24`, profil Windows `Public`).
  - URL PC Server: `http://127.0.0.1:8000`
  - URL PC Client (LAN): `http://192.168.1.72:8000`

---

## 5. KONFIGURASI FIREWALL & KEAMANAN LAN

1. **Firewall Rule Khusus DSS-PIK (Jalankan 1x di PowerShell *Run as Administrator*)**:
   ```powershell
   # 1. Ubah profil Wi-Fi kantor ke Private (opsional namun sangat disarankan)
   Set-NetConnectionProfile -InterfaceAlias "Wi-Fi" -NetworkCategory Private

   # 2. Tambah rule Inbound khusus DSS-PIK Port 8000 hanya untuk LocalSubnet
   netsh advfirewall firewall add rule name="DSS-PIK LAN Server (TCP 8000)" dir=in action=allow protocol=TCP localport=8000 remoteip=LocalSubnet profile=private,domain
   ```
   *Catatan*: MariaDB port `3306` **tidak perlu** dan **dilarang** dibuka ke LAN/publik.
2. **Catatan Keamanan HTTP Plain LAN**:
   - Komunikasi LAN saat ini menggunakan HTTP plain (`http://192.168.1.72:8000`). HTTP plain tidak mengenkripsi kredensial login maupun trafik API di udara/kabel, sehingga **hanya layak digunakan pada jaringan Wi-Fi/LAN internal kantor yang terpercaya**. Untuk hardening operasional lanjutan, disarankan memasang reverse proxy lokal (Nginx/Caddy) dengan TLS internal (`CEWS_COOKIE_SECURE=true`).

---

## 6. HASIL PENGUJIAN END-TO-END

### Test Group A — Unified Launcher
| ID | Skenario | Status | Bukti Aktual |
|---|---|---:|---|
| A1 | Startup dari kondisi semua service OFF (termasuk MariaDB) | `PARTIAL (CODE VERIFIED)` | Jalur auto-start MariaDB standalone (`mariadbd.exe`) telah diimplementasikan & diverifikasi deteksinya; instance MariaDB produksi (`PID 18412`) sengaja tidak dimatikan demi keamanan data operasional. |
| A2 | Startup saat MariaDB sudah ON | `PASS` | `DSS-PIK.bat start --no-browser` → MariaDB terdeteksi (`57 stasiun`), Uvicorn start (PID 6824 / 10316), `/health` 200 OK. |
| A3 | Double-click / start berulang (idempotency) | `PASS` | Start kedua melaporkan `DSS-PIK sudah aktif (PID 6824). Tidak membuat instance ganda.` |
| A4 | Backend menerima request | `PASS` | `GET /health` → `200 OK`, `{"status":"ok","service":"cews-api","database":"connected"}`. |
| A5 | Frontend production dimuat via FastAPI | `PASS` | `GET /` → `200 OK` HTML + `/assets/index-BRK1kGL_.js` → `200 OK` (693.292 bytes). |
| A6 | Browser otomatis terbuka | `PASS (MECHANISM VERIFIED)` | Menggunakan `webbrowser.open` + fallback PowerShell `Start-Process` (dilewati dengan `--no-browser` pada test otomatis). |
| A7 | Port 8000 digunakan aplikasi lain | `PASS` | Mock foreign PID `999999` terdeteksi sebagai `port_conflict=True` tanpa mematikan proses asing. |
| A8 | Koneksi MariaDB gagal | `PASS` | Mock port `33999` mengembalikan `db_ok=False` dengan pesan error diagnostik jelas. |
| A9 | Dependency / frontend build hilang | `PASS` | Teruji nyata pada missing `jsonschema` (lalu dilonggarkan jadi opsional) dan mock missing `frontend/dist/index.html`. |
| A10 | STOP & RESTART berjalan bersih | `PASS` | `restart` menghentikan PID 6824, menyalakan PID 8196, lalu `stop` menghentikan PID 10316 dengan bersih. |
| A11 | Shutdown tidak mematikan proses non-DSS-PIK | `PASS` | MariaDB `PID 18412` tetap berjalan utuh sepanjang siklus `stop`/`restart`. |
| A12 | Portabilitas setelah pindah direktori | `PASS (STATIC VERIFIED)` | `DSS-PIK.bat` memakai `%~dp0` dan `unified_launcher.py` memakai `Path(__file__).resolve().parent.parent` (nol hardcoded path). |

### Test Group B — Multi-Client LAN
| ID | Skenario | Status | Bukti Aktual |
|---|---|---:|---|
| B1 | Akses lokal `http://127.0.0.1:8000` | `PASS` | `/health=200`, `/=200`, JS bundle `200`. |
| B2 | Akses dari server via LAN IP `http://192.168.1.72:8000` | `PASS` | `/health=200`, `/=200`, JS bundle `200`. |
| B3 | Akses fisik dari PC B | `NOT TESTED` | Perangkat fisik PC B tidak tersedia di sesi pengujian otomatis. Ikuti Panduan Uji Client di Bagian 7. |
| B4 | Akses fisik dari PC C | `NOT TESTED` | Perangkat fisik PC C tidak tersedia di sesi pengujian otomatis. Ikuti Panduan Uji Client di Bagian 7. |
| B5 | Simultaneous login beberapa operator | `PASS (SIMULATED ON LAN IP)` | Token sesi terpisah berhasil diterbitkan dan diverifikasi bersamaan pada `192.168.1.72:8000`. |
| B6 | API & asset frontend berjalan di client | `PASS` | Seluruh endpoint memakai same-origin relative path (`API_BASE_URL=''`), asset JS termuat penuh via LAN IP. |
| B7 | Cookie/session isolation | `PASS` | `jti` unik per login (`ced7c064 != f1984775`). |
| B8 | Refresh & logout independen | `PASS` | `POST /api/v1/auth/logout` pada sesi PC B tidak memengaruhi validitas `/api/v1/auth/me` sesi PC C. |
| B9 | Concurrent read (6 client simultan) | `PASS` | 6 thread simultan mengakses `/auth/me`, `/periods`, `/hth`, `/early-warning-table` (57 stasiun), `/detail`, `/ingestion/latest-status`, `/publications/sih3/preview` → semua `200 OK`, `valid=True`. |
| B10 | Concurrent write & pengendalian konflik | `PASS (LOCK VERIFIED)` | `_REGIONAL_WRITE_LOCK`, `_CACHE_LOCK`, dan `_REFRESH_EVALUATE_LOCK` (HTTP 409) terpasang dan lulus kompilasi + regresi. |
| B11 | Restart server & reconnect client | `PASS` | Setelah `DSS-PIK.bat restart`, endpoint kembali melayani `200 OK` tanpa error. |
| B12 | Firewall / security verification | `PARTIAL (ADMIN ACTION NEEDED)` | Rule firewall khusus `DSS-PIK LAN Server (TCP 8000)` belum terpasang karena shell non-Admin; perintah Administrator sudah disediakan. |

---

## 7. PANDUAN OPERATOR & PENGUJIAN DARI PC CLIENT (PC B & PC C)

### A. Panduan Operator Harian (PC Server)
1. Double-click **`DSS-PIK.bat`** di folder root proyek.
2. Tunggu 5–10 detik hingga browser terbuka otomatis ke `http://127.0.0.1:8000/`.
3. Catat alamat **`URL Client`** yang tampil di terminal (misal `http://192.168.1.72:8000`) untuk dibagikan ke PC operator lain.
4. Pilih `[0]` bila ingin menutup jendela terminal sambil membiarkan server tetap berjalan, atau `[3]` untuk menghentikan server di akhir shift.

### B. Checklist Pengujian Fisik di Kantor (PC B & PC C)
1. Pastikan PC Server (A), PC B, dan PC C terhubung pada Wi-Fi/LAN kantor yang sama (dan fitur *AP/Client Isolation* pada router/access point dalam keadaan OFF).
2. Pada PC Server (A), jalankan perintah firewall Administrator pada Bagian 5 (1 kali saja).
3. Pada PC B, buka Chrome/Edge → akses `http://192.168.1.72:8000/health` → pastikan muncul `{"status":"ok","service":"cews-api","database":"connected"}`.
4. Buka `http://192.168.1.72:8000/` pada PC B dan PC C secara bersamaan → login di kedua PC.
5. Verifikasi peta Leaflet, tabel 57 stasiun, Station Detail Drawer, dan Data Center termuat normal di kedua PC.
6. Logout di PC B → refresh halaman di PC C → pastikan PC C **tetap login** dan tidak terganggu.
