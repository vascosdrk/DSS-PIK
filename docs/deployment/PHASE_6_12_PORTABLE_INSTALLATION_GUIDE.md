# PHASE 6.12 — PORTABLE INSTALLATION GUIDE (SETUP PADA KOMPUTER BARU)
**Sistem:** DSS-PIK BMKG Kepulauan Riau  

---

## 1. Prasyarat Perangkat Lunak pada Komputer Baru
1. **OS**: Windows 10 / Windows 11 / Windows Server (64-bit).
2. **Python**: Python `3.10` – `3.12` (centang *"Add Python to PATH"* saat instalasi).
3. **Database**: MariaDB `11.4+` aktif pada port `3306`.
4. **Node.js** *(Opsional)*: Node.js `20+` hanya diperlukan jika ingin melakukan *rebuild* frontend (`frontend/dist/` sudah disertakan siap pakai).

---

## 2. Langkah Instalasi Satu Klik (`setup_dss_pik_new_pc.bat`)
1. Salin seluruh folder proyek ke lokasi mana pun di komputer baru (misal `D:\DSS-PIK\` atau `C:\BMKG\DSS-PIK\`).
2. Sesuaikan berkas `.env` (khususnya `CEWS_DB_PASSWORD` sesuai password root/user MariaDB pada komputer baru).
3. Jalankan script setup:
   - Menggunakan Python sistem:
     ```cmd
     setup_dss_pik_new_pc.bat
     ```
   - Atau membuat Virtual Environment lokal baru (`.venv`):
     ```cmd
     setup_dss_pik_new_pc.bat --create-venv
     ```
4. Jika database `cews_db` di komputer baru masih kosong, pulihkan dari folder backup migrasi:
   ```cmd
   python scripts\restore_dss_pik.py --backup-dir "D:\DSS_PIK_BACKUPS\backup_YYYYMMDD_HHMMSS"
   ```
5. Jalankan server LAN:
   ```cmd
   run_cews_lan.bat
   ```

