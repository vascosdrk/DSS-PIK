# PHASE 6.11 — PANDUAN AKSES MULTI-USER JARINGAN LAN KANTOR (DSS-PIK)
**Prinsip Utama:** Satu Server (Komputer A), Satu Database (`cews_db`), Satu Sumber Data Parquet, Banyak Komputer Pengguna (Client B, C, dst.).

---

## 1. Arsitektur LAN DSS-PIK
- **Komputer A (Server Utama)**: Menjalankan MariaDB (`127.0.0.1:3306`), Backend FastAPI + Frontend Production (`0.0.0.0:8000`, 1 worker), Decision Engine, SPI Generator, dan seluruh file Parquet.
- **Komputer B, C, dst. (Client)**: Cukup membuka browser (Chrome/Edge/Firefox) di jaringan Wi-Fi/LAN kantor yang sama ke alamat `http://<IP-LAN-KOMPUTER-A>:8000`. Tidak perlu instalasi Python, Node.js, MariaDB, atau menyalin file Parquet.

## 2. Cara Menjalankan Server (Komputer A)
1. Pastikan MariaDB aktif di port `3306`.
2. Klik ganda atau jalankan dari terminal:
   ```cmd
   run_cews_lan.bat
   ```
3. Terminal akan menampilkan IP LAN dan URL akses, contoh:
   `Access URL (Client): http://192.168.1.100:8000`

## 3. Cara Mengakses & Login (Komputer B, C, dst.)
1. Pastikan komputer terhubung ke Wi-Fi/LAN kantor yang sama dengan Komputer A.
2. Buka browser dan ketik alamat URL yang tampil di Komputer A (misal `http://192.168.1.100:8000`).
3. Login menggunakan akun operator bersama (`klimatkepri`).
4. **Multi-Session**: Banyak komputer dapat login bersamaan dengan akun yang sama. Logout di satu komputer tidak mengeluarkan komputer lainnya.

## 4. Konfigurasi Windows Firewall (Hanya Jika Client Gagal Terhubung)
Jalankan PowerShell **sebagai Administrator** di Komputer A untuk mengizinkan port `8000` khusus dari subnet LAN lokal (`LocalSubnet`) pada profil `Private`:
```powershell
New-NetFirewallRule -DisplayName "DSS-PIK LAN Port 8000" -Direction Inbound -Protocol TCP -LocalPort 8000 -RemoteAddress LocalSubnet -Action Allow -Profile Private
```
**Jangan** membuka port `3306` (MariaDB) atau `5173` (Vite).

## 5. Cara Menghentikan Server & Backup
- Menghentikan server: jalankan `stop_cews_lan.bat` (atau `CTRL+C` pada terminal).
- Backup rutin: jalankan `python scripts/backup_dss_pik.py`.
- **Batasan**: Jika Komputer A mati atau Wi-Fi/LAN terputus, client tidak dapat mengakses DSS-PIK hingga Komputer A kembali menyala.

## 6. Checklist Singkat Operator Kantor
- [ ] MariaDB aktif di Komputer A.
- [ ] `run_cews_lan.bat` berjalan dan menampilkan `Access URL`.
- [ ] Client B/C dapat membuka halaman login via IP Komputer A.
- [ ] Setelah operator mengunggah CH / menjalankan SPI Generator, operator lain menekan **Segarkan & Evaluasi** untuk melihat data terbaru.

