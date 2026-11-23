# PHASE 6.14 — TROUBLESHOOTING GUIDE (PANDUAN PENANGANAN KENDALA)

---

### 1. `[ERROR] MariaDB tidak aktif di port 3306` saat menjalankan `run_cews_lan.bat`
- **Penyebab**: Service MariaDB belum berjalan.
- **Solusi**: Buka `services.msc` atau jalankan PowerShell Administrator: `Start-Service MariaDB` (atau `net start MariaDB`).

### 2. `[ERROR] Port 8000 sudah digunakan`
- **Penyebab**: Instance DSS-PIK sebelumnya masih berjalan di latar belakang.
- **Solusi**: Jalankan `stop_cews_lan.bat`, lalu jalankan kembali `run_cews_lan.bat`.

### 3. Komputer B / C Tidak Dapat Membuka `http://<IP-LAN-SERVER>:8000`
- **Penyebab**: Windows Firewall pada Komputer Server (Komputer A) memblokir port `8000` atau profil Wi-Fi masih `Public`.
- **Solusi**:
  1. Ubah profil jaringan Wi-Fi/LAN di Komputer A menjadi **Private**.
  2. Jalankan PowerShell Administrator di Komputer A:
     ```powershell
     New-NetFirewallRule -DisplayName "DSS-PIK LAN Port 8000" -Direction Inbound -Protocol TCP -LocalPort 8000 -RemoteAddress LocalSubnet -Action Allow -Profile Private
     ```
  3. Jalankan `powershell -ExecutionPolicy Bypass -File scripts\check_dss_pik_lan.ps1` untuk memeriksa IP LAN terbaru Komputer A.

### 4. Gagal Koneksi Database (`Access denied for user` di `logs\runtime\backend_lan.log`)
- **Penyebab**: `CEWS_DB_PASSWORD` atau `CEWS_DB_USER` pada berkas `.env` belum sesuai dengan akun MariaDB di komputer baru.
- **Solusi**: Perbarui `.env`, lalu restart server dengan `stop_cews_lan.bat` dan `run_cews_lan.bat`.

### 5. Browser Komputer A Tidak Terbuka Otomatis
- **Penyebab**: Belum ada browser default yang terdaftar di Windows.
- **Solusi**: Server tetap berjalan normal; buka browser secara manual ke `http://127.0.0.1:8000/`.

