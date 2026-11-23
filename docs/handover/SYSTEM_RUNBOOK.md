# SYSTEM RUNBOOK — DSS-PIK BMKG TANJUNGPINANG
## Panduan Pemeliharaan & Prosedur Operasional Standar (SOP) Harian

---

## 1. PROSEDUR STARTUP & SHUTDOWN

### A. Memulai Sistem (Startup)
1. **Langkah 1**: Pastikan layanan basis data MariaDB aktif pada port `3306`.
2. **Langkah 2**: Klik ganda file:
   `run_cews.bat`
   *Skrip ini akan secara otomatis:*
   - Memverifikasi port `3306` (MariaDB).
   - Menjalankan Backend FastAPI pada port `8000` (`0.0.0.0:8000`).
   - Melakukan polling HTTP health check ke `http://127.0.0.1:8000/api/health`.
   - Menjalankan Frontend Vite pada port `5173` (`0.0.0.0:5173`).
   - Menyimpan Process ID pada `logs/runtime/backend.pid` dan `logs/runtime/frontend.pid`.
   - Membuka browser web default secara otomatis ke `http://localhost:5173/`.

### B. Menghentikan Sistem (Shutdown)
1. Klik ganda file:
   `stop_cews.bat`
   *Skrip ini akan secara deterministik menghentikan proses backend (Uvicorn), frontend (Node/Vite), dan proses anak melalui tree-kill tanpa mematikan MariaDB.*

---

## 2. HEALTH CHECK & MONITORING KESEHATAN SISTEM

| Layanan | Endpoint / Metode Verifikasi | Respon Normal |
|---|---|---|
| **API Backend** | `GET http://localhost:8000/api/health` | `{"status": "ok", "database": "connected"}` |
| **Periode Aktif** | `GET http://localhost:8000/api/evaluation-period` | JSON periode aktif (misal `2026-10-3`) |
| **Peringatan Stasiun** | `GET http://localhost:8000/api/current-warning` | Array 57 stasiun lengkap dengan status PDKM & PDCHT |
| **Status Wilayah** | `GET http://localhost:8000/api/regional-warnings` | Agregasi 7 kabupaten/kota |
| **Log Runtime** | Periksa berkas `logs/runtime/backend.log` | Tidak ada pesan traceback kritis |

---

## 3. PROSEDUR REFRESH & EVALUASI OPERASIONAL

Saat data curah hujan harian terbaru selesai diunggah atau dasarian baru dimulai:

1. Buka dashboard pada browser: `http://localhost:5173/`.
2. Pada bagian kanan atas header, klik tombol **"Segarkan & Evaluasi"**.
3. Sistem akan mengirim request ke endpoint `POST /api/refresh-all`.
4. Backend akan:
   - Menghitung ulang Hari Tanpa Hujan (HTH) berdasarkan observasi database.
   - Membaca nilai SPI 90D dan SPI 30D terbaru dari Parquet.
   - Menghubungkan ensemble probabilitas ECMWF (Pb20, Pa150, Pa200, Pa300, PM300, PM400, PM500).
   - Menjalankan sintesis Decision Engine PDKM, PDCHT, dan Dual-Hazard.
   - Menyimpan snapshot evaluasi ke tabel `cews_current_warning` dan `cews_warning_history`.
5. Tampilan kartu KPI, tabel, dan peta Leaflet akan otomatis diperbarui secara reaktif.

---

## 4. PEMELIHARAAN DATA & BACKUP RUTIN

### A. Backup Harian MariaDB
Jalankan dump terkompresi secara periodik:
```cmd
mysqldump -u root -p cews_db > backup_cews_db_%date:~10,4%%date:~4,2%%date:~7,2%.sql
```

### B. Backup Berkas Parquet SPI
Lakukan pencadangan berkala terhadap direktori:
- `data/raw/spi/dasarian/`
- `data/reference/spi_distributions/`

Simpan salinan cadangan pada drive terpisah.

---

## 5. PANDUAN PEMECAHAN MASALAH (TROUBLESHOOTING)

### Masalah 1: "Database connection failed" atau Backend Error 500
- **Penyebab**: Layanan MariaDB mati atau port 3306 diblokir.
- **Tindakan**: Buka `services.msc`, cari layanan MariaDB, lalu klik **Restart**. Periksa kecocokan kredensial pada berkas `.env`.

### Masalah 2: Port 8000 atau Port 5173 Bentrok (Port In Use)
- **Gejala**: Backend atau frontend gagal start dengan kode error `EADDRINUSE` atau `Errno 10048`.
- **Tindakan**:
  1. Jalankan `stop_cews.bat` untuk membersihkan proses zombie.
  2. Jika masih terkunci, identifikasi PID yang menduduki port:
     ```cmd
     netstat -ano | findstr :8000
     taskkill /F /PID <PID_TERDETEKSI>
     ```

### Masalah 3: Nilai SPI 90D Kosong / NULL pada Beberapa Pos
- **Penyebab**: Data historis stasiun tersebut belum lengkap pada dasarian terkait atau observasi belum mencukupi panjang rekaman minimal distribusi BestDist.
- **Tindakan**: Ini adalah **perilaku wajar kelengkapan observasi**, bukan kerusakan generator. Sistem secara otomatis menandai stasiun dengan kelengkapan `PARTIAL` (jika HTH memicu bahaya) atau `INCOMPLETE` (jika HTH aman).

### Masalah 4: Tampilan Peta Kosong / Tidak Memuat Marker
- **Penyebab**: Koneksi Leaflet tile provider lambat atau API `/api/current-warning` belum selesai merespons.
- **Tindakan**: Lakukan hard refresh browser (`Ctrl + F5`). Pastikan koneksi internet aktif untuk memuat tile OpenStreetMap, atau gunakan tile cache lokal jika dioperasikan pada intranet tertutup.

