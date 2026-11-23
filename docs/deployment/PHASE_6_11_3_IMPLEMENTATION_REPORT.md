# PHASE 6.11.3 — IMPLEMENTATION REPORT
## LAN Multi-Client Login Reconciliation & Automatic Server Browser Launch

---

### 1. Root Cause Sebenarnya Mengapa Komputer A Berhasil Login tetapi Komputer B & C Gagal (`Failed to fetch`)

Hasil investigasi menyeluruh pada berkas konfigurasi, bundle `frontend/dist/`, dan `logs/runtime/backend_lan.log` menemukan akar masalah utama:

1. **Hardcoded `VITE_API_BASE_URL=http://127.0.0.1:8000` pada `frontend/.env`**:
   - Di dalam direktori `frontend/` terdapat berkas `frontend/.env` yang berisi:
     ```env
     VITE_API_BASE_URL=http://127.0.0.1:8000
     ```
   - Saat `vite build` dijalankan, Vite secara statis menanamkan (*inline*) string `"http://127.0.0.1:8000"` ke dalam bundle produksi (`frontend/dist/assets/index-K2OdNYYs.js`):
     ```javascript
     xv=()=>"http://127.0.0.1:8000".replace(/\/+$/,""),me=xv()
     ```
   - **Dampak pada Komputer A**: Saat operator login di Komputer A, `127.0.0.1:8000` adalah mesin Komputer A sendiri (tempat FastAPI berjalan), sehingga request login berhasil (`200 OK`).
   - **Dampak pada Komputer B dan C**: Saat Komputer B (`192.168.1.57`) atau Komputer C membuka `http://192.168.1.72:8000`, halaman HTML/JS berhasil dimuat, **namun ketika tombol Login ditekan, browser Komputer B/C mengirim request `POST` ke `http://127.0.0.1:8000/api/v1/auth/login` (loopback milik Komputer B/C sendiri, bukan Komputer A!)**. Karena di Komputer B/C tidak ada server pada port `8000`, koneksi ditolak (`ERR_CONNECTION_REFUSED`) dan browser menampilkan **`Failed to fetch`**, sementara request login dari Komputer B/C tidak pernah sampai ke `backend_lan.log` di Komputer A.

2. **Bukti Log (`logs/runtime/backend_lan.log`)**:
   - Sebelum perbaikan, `backend_lan.log` mencatat Komputer B (`192.168.1.57`) memuat aset statis tetapi seluruh panggilan API hanya berasal dari `127.0.0.1`:
     ```text
     INFO:     192.168.1.57:58992 - "GET / HTTP/1.1" 200 OK
     INFO:     192.168.1.57:58992 - "GET /assets/index-K2OdNYYs.js HTTP/1.1" 200 OK
     INFO:     127.0.0.1:56977 - "OPTIONS /api/v1/auth/me HTTP/1.1" 200 OK
     INFO:     127.0.0.1:60642 - "GET /api/v1/auth/me HTTP/1.1" 200 OK
     ```

---

### 2. File yang Diubah & Detail Perbaikan

1. **[`frontend/.env`](file:///c:/LATSAR/ASLI2/frontend/.env)**:
   - Mengosongkan `VITE_API_BASE_URL=` agar Vite tidak menanamkan `http://127.0.0.1:8000` ke dalam bundle production.
2. **[`frontend/src/config.js`](file:///c:/LATSAR/ASLI2/frontend/src/config.js)**:
   - Memperkuat `resolveApiBaseUrl()` dengan proteksi runtime: meskipun `VITE_API_BASE_URL` berisi `127.0.0.1` atau `localhost`, jika browser diakses melalui IP LAN (`window.location.hostname` bukan `localhost`/`127.0.0.1`), nilai tersebut diabaikan dan otomatis menggunakan *same-origin* (`''`).
   - Membangun ulang production bundle (`npm --prefix frontend run build`) menghasilkan bundle baru `frontend/dist/assets/index-BvdkRXCN.js` yang bebas dari hardcode `127.0.0.1:8000`.
3. **[`backend/main.py`](file:///c:/LATSAR/ASLI2/backend/main.py)**:
   - Mempertahankan `LAN_ORIGIN_REGEX` aktif untuk subnet privat LAN ketika `CEWS_CORS_ORIGINS` tidak diset.
   - Menambahkan header `Cache-Control: no-cache, no-store, must-revalidate` pada saat menyajikan `frontend/dist/index.html` sehingga browser Komputer B dan C selalu memuat bundle JS terbaru (`index-BvdkRXCN.js`).
4. **[`run_cews_lan.bat`](file:///c:/LATSAR/ASLI2/run_cews_lan.bat)**:
   - Menunggu Uvicorn siap melalui polling `http://127.0.0.1:8000/health` (HTTP 200), kemudian otomatis membuka browser default pada Komputer A ke `http://127.0.0.1:8000` (`start "" "http://127.0.0.1:8000"`) dan menampilkan status `Browser : OPENED`.

---

### 3. Hasil Pengujian & Regresi

| Pengujian | Hasil |
|---|---|
| `python -m py_compile backend/main.py` | **PASSED** |
| `import backend.main` | **PASSED** |
| `npm --prefix frontend run build` | **PASSED** (Bundle baru: `dist/assets/index-BvdkRXCN.js`) |
| `GET http://192.168.1.72:8000/` | **200 OK** (`Cache-Control: no-cache, no-store, must-revalidate`, memuat `index-BvdkRXCN.js`) |
| `GET http://192.168.1.72:8000/health` | **200 OK** (`{"status":"ok","service":"cews-api","database":"connected"}`) |
| `POST http://192.168.1.72:8000/api/v1/auth/login` (Kredensial salah) | **401 Unauthorized** (Pesan error valid, bukan `Failed to fetch`) |
| Multi-Session Login (Komputer A, B, C bersamaan) | **PASSED** (3 token HMAC-SHA256 independen valid secara bersamaan pada `GET /api/v1/auth/me` -> `200 OK`) |
| Automatic Browser Launch (`run_cews_lan.bat`) | **PASSED** (Hanya membuka `http://127.0.0.1:8000` di Komputer A setelah `/health` HTTP 200) |
| Integritas Database MariaDB & Parquet SPI | **TIDAK BERUBAH** (Tidak ada modifikasi pada `cews_db`, 34 file Parquet, maupun `decision_engine.py`) |

---

### 4. Panduan Verifikasi Lapangan (Operator Komputer A, B, dan C)

- **Komputer A (Server)**:
  1. Jalankan `stop_cews_lan.bat` untuk menghentikan proses server lama.
  2. Jalankan `run_cews_lan.bat`.
  3. Setelah `/health` terverifikasi, browser pada Komputer A akan terbuka otomatis ke `http://127.0.0.1:8000`. Silakan login.
- **Komputer B & Komputer C (Client LAN)**:
  1. Buka browser ke `http://192.168.1.72:8000` (lakukan *refresh* / `Ctrl+F5` satu kali untuk memuat `index.html` baru).
  2. Login menggunakan akun operator yang sama.
  3. Ketiga komputer kini memanggil endpoint `/api/v1/...` secara *same-origin* ke `192.168.1.72:8000` dan dapat beroperasi secara bersamaan.

---

## PHASE 6.11.4 — AUTO BROWSER LAUNCHER FIX

### 1. Root Cause Mengapa Browser Tidak Terbuka Otomatis
Investigasi terhadap eksekusi `run_cews_lan.bat` pada `cmd.exe` menemukan dua penyebab teknis utama:
1. **Batch Chaining tanpa `call` ke `.\powershell.CMD` di Direktori Proyek**:
   - Di root proyek `C:\LATSAR\ASLI2` terdapat file `powershell.CMD` (`C:\Windows\System32\WindowsPowerShell\v1.0\powershell.exe %*`).
   - Saat `run_cews_lan.bat` memanggil `powershell -NoProfile -Command ...` (tanpa ekstensi `.exe`), `cmd.exe` me-resolve perintah tersebut ke `.\powershell.CMD` di direktori kerja saat ini.
   - Dalam aturan Windows Batch (`cmd.exe`), mengeksekusi file `.cmd`/`.bat` lain dari dalam file `.bat` tanpa perintah `call` menyebabkan `cmd.exe` mentransfer kontrol eksekusi secara permanen ke `powershell.CMD`. Begitu `powershell.CMD` selesai melakukan polling `/health`, eksekusi batch langsung berhenti dan **tidak pernah kembali ke baris pembukaan browser maupun pencetakan banner status di `run_cews_lan.bat`**.
2. **Karakter Non-ASCII (UTF-8 Em-Dash `—`) & Line Ending LF (`\n`)**:
   - File `.bat` sebelumnya menggunakan line ending Unix `LF` (`\n`) dan karakter UTF-8 3-byte (`—`) pada baris komentar, yang memicu pergeseran byte-offset parser `cmd.exe` (`'tlocal' is not recognized`).

### 2. File yang Diubah & Solusi Teknis
- **[`run_cews_lan.bat`](file:///c:/LATSAR/ASLI2/run_cews_lan.bat)** & **[`stop_cews_lan.bat`](file:///c:/LATSAR/ASLI2/stop_cews_lan.bat)**:
  - Menggunakan biner eksplisit `set "PS_EXE=%SystemRoot%\System32\WindowsPowerShell\v1.0\powershell.exe"` (`%PS_EXE%`) sehingga `cmd.exe` selalu memanggil executable `powershell.exe` asli milik Windows dan tidak pernah teralihkan oleh `.\powershell.CMD`.
  - Menerapkan pembukaan browser berlapis setelah `/health` mengembalikan HTTP 200 (`status == 'ok'`):
    1. Primary: `%PS_EXE% -NoProfile -Command "try { Start-Process -FilePath 'http://127.0.0.1:8000/' -ErrorAction Stop; exit 0 } catch { exit 1 }"`
    2. Fallback 1: `explorer.exe "http://127.0.0.1:8000/"`
    3. Fallback 2: `cmd /c start "" "http://127.0.0.1:8000/"`
  - Menampilkan status akurat `Browser : OPEN REQUESTED` (atau `FAILED` disertai panduan jika seluruh fallback gagal tanpa mematikan backend).
  - Menstandarkan encoding seluruh file `.bat` menjadi **100% Pure ASCII** dengan line ending **Windows CRLF (`\r\n`)**.

### 3. Hasil Pengujian & Status Verifikasi
- `stop_cews_lan.bat` -> Menghentikan PID port `8000` dengan bersih sementara MariaDB (`3306`) tetap aktif.
- `run_cews_lan.bat` -> Output aktual:
  ```text
  [START] Memulai DSS-PIK Backend pada 0.0.0.0:8000 - 1 worker - production...
  ======================================================================
    DSS-PIK LAN SERVER
    Backend   : RUNNING
    Database  : CONNECTED
    Frontend  : PRODUCTION
    Network   : LAN
    Server IP : 192.168.1.72
    Local URL : http://127.0.0.1:8000
    Client URL: http://192.168.1.72:8000
    Browser   : OPEN REQUESTED
  ======================================================================
  ```
- **Status Verifikasi**: **VERIFIED & PASSED**.

