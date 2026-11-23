# PHASE 7.3.1 — DSS-PIK SAFE LAN FIREWALL CONFIGURATION
**Project**: Decision Support System Peringatan Iklim (DSS-PIK)  
**Institusi**: BMKG Stasiun Meteorologi Kelas II Raja Haji Fisabilillah Tanjungpinang  
**Tanggal Implementasi**: 22 November 2026  
**Baseline**: Phase 7.3 → Phase 7.3.1

---

## 1. KONDISI FIREWALL & JARINGAN SEBELUM PERUBAHAN

Hasil audit baseline (tersimpan di `backups/phase_7_3_1_checkpoint/firewall_and_network_baseline.txt`):
- **Windows Defender Firewall**: Aktif (`Enabled: True`) pada seluruh 3 profil (`Domain`, `Private`, `Public`).
- **Profil Jaringan Aktif**: `SM1-Fisabilillah` pada adapter `Wi-Fi` (`Realtek RTL8852BE WiFi 6 802.11ax PCIe Adapter`), kategori **`Public`** (**TIDAK DIUBAH**).
- **Konfigurasi IPv4 Terdeteksi Dinamis**: `192.168.1.72/24`, subnet `192.168.1.0/24`, default gateway `192.168.1.1`.
- **Executable Backend Terdeteksi Dinamis**: `sys.executable` (`C:\Users\AWI User\AppData\Local\Programs\Python\Python312\python.exe`).
- **Rule Firewall Sebelumnya**: Tidak ada rule khusus `DSS-PIK - LAN Access`; hanya ada 2 rule otomatis `python.exe` yang dibiarkan utuh tanpa modifikasi.
- **MariaDB**: Berjalan lokal pada port `3306` (`PID 18412`, `cews_db`), **TIDAK** dibuka ke LAN.

---

## 2. ARSITEKTUR KEAMANAN BERLAPIS (*DEFENSE-IN-DEPTH*)

Karena Windows Firewall berbasis program hanya membatasi executable (`python.exe`) dan tidak membedakan antar-skrip Python, Phase 7.3.1 menerapkan **2 lapis pengamanan**:

1. **Lapis 1 — Windows Defender Firewall Rule Khusus (`scripts/dss_pik_firewall.ps1`)**:
   - **Display Name**: `DSS-PIK - LAN Access`
   - **Direction**: `Inbound` | **Protocol**: `TCP` | **LocalPort**: `8000` | **Action**: `Allow`
   - **InterfaceAlias**: Adapter LAN/Wi-Fi aktif yang disetujui (deteksi dinamis, mis. `Wi-Fi`)
   - **RemoteAddress**: Daftar IP client atau subnet internal spesifik yang disetujui (mis. `192.168.1.80,192.168.1.81` atau `192.168.1.0/24`) — **menolak `Any`, `*`, `0.0.0.0/0`, maupun prefix `< /16`**
   - **Profile**: Hanya profil jaringan aktif saat ini (mis. `Public`) **tanpa mengubah kategori Wi-Fi menjadi Private**
   - **Program**: Executable backend dinamis (`sys.executable`)
   - **Anti-Duplikat**: Sebelum membuat rule baru, skrip menghapus rule lama dengan `DisplayName` persis `DSS-PIK - LAN Access` saja; aturan milik aplikasi lain tidak pernah disentuh.
2. **Lapis 2 — Application-Level LAN Access Guard (`backend/main.py` & `backend/lan_firewall_service.py`)**:
   - Middleware `lan_access_guard_middleware` membaca kebijakan portabel `config/lan_access_policy.json` (tanpa password/secret).
   - Akses loopback (`127.0.0.1`, `::1`) **selalu diizinkan** agar PC Server tetap bekerja normal meski LAN dimatikan.
   - Akses non-loopback ditolak seketika dengan **`HTTP 403 Forbidden`** apabila `lan_enabled: false` atau IP client tidak cocok dengan `approved_remote_addresses`.
   - Deteksi *Network Drift* (`check_network_drift`) memperingatkan operator bila SSID Wi-Fi, interface, IP server, atau subnet berubah (mis. PC berpindah ke Wi-Fi publik lain) tanpa memperluas akses secara otomatis.

---

## 3. MEKANISME ENABLE / DISABLE / ROLLBACK MELALUI `DSS-PIK.bat`

Seluruh pengelolaan terintegrasi pada satu launcher **`DSS-PIK.bat`** (`DSS-PIK SYSTEM MANAGER`):
```text
  [1] START SYSTEM          (Tidak butuh Administrator; localhost selalu aktif)
  [2] STOP SYSTEM           (Tidak mematikan MariaDB shared atau proses asing)
  [3] RESTART SYSTEM
  [4] SYSTEM STATUS         (Menampilkan status Backend, DB, LAN Policy, FW Rule, Drift)
  [5] ENABLE LAN ACCESS     (Konfirmasi eksplisit operator + UAC Admin hanya untuk rule FW)
  [6] DISABLE LAN ACCESS    (Blokir LAN seketika tanpa mematikan backend lokal / MariaDB)
  [7] LAN DIAGNOSTICS       (Inspeksi adapter, IP, subnet, gateway, profil, & rule FW)
  [0] EXIT
```
Mode CLI:
- `DSS-PIK.bat enable-lan [--remote 192.168.1.80,192.168.1.81]`
- `DSS-PIK.bat disable-lan`
- `DSS-PIK.bat lan-diagnostics`
- `DSS-PIK.bat rollback-lan`

---

## 4. PERSYARATAN ADMINISTRATOR (OTORISASI EKSPLISIT)

- **Operasi harian lokal (`START`, `STOP`, `RESTART`, `STATUS`, `LAN DIAGNOSTICS`)**: **TIDAK** memerlukan hak Administrator.
- **Perubahan Windows Firewall (`ENABLE LAN ACCESS`, `DISABLE LAN ACCESS`, `ROLLBACK`)**: Memerlukan otorisasi Administrator Windows. Saat dijalankan dari menu `DSS-PIK.bat`, sistem hanya meminta elevasi UAC setelah operator menyetujui konfirmasi `[y/N]`.
- **Perintah Manual Administrator (jika dijalankan langsung dari PowerShell *Run as Administrator*)**:
  ```powershell
  # Enable (contoh subnet lokal terdeteksi; ganti -RemoteAddress dengan daftar IP client jika ingin lebih ketat)
  powershell -NoProfile -ExecutionPolicy Bypass -File "scripts\dss_pik_firewall.ps1" -Action enable -RuleName "DSS-PIK - LAN Access" -LocalPort 8000 -InterfaceAlias "Wi-Fi" -RemoteAddress "192.168.1.0/24" -ProfileName "Public" -ProgramPath "C:\Users\AWI User\AppData\Local\Programs\Python\Python312\python.exe"

  # Disable (hanya menonaktifkan rule DSS-PIK)
  powershell -NoProfile -ExecutionPolicy Bypass -File "scripts\dss_pik_firewall.ps1" -Action disable -RuleName "DSS-PIK - LAN Access"

  # Rollback penuh (menghapus rule DSS-PIK kembali ke kondisi sebelum Phase 7.3.1)
  powershell -NoProfile -ExecutionPolicy Bypass -File "scripts\dss_pik_firewall.ps1" -Action rollback -RuleName "DSS-PIK - LAN Access"
  ```

---

## 5. HASIL PENGUJIAN (A – L)

| Uji | Skenario | Status | Bukti Aktual |
|---|---|---:|---|
| **A** | DSS-PIK berjalan normal tanpa LAN access | `PASS` | `DSS-PIK.bat start --no-browser` dengan `lan_enabled=False` berhasil (PID 22644). |
| **B** | Browser lokal mengakses `127.0.0.1:8000` | `PASS` | `GET http://127.0.0.1:8000/health` → `200`, `GET /` → `200`. |
| **C** | Validasi least-privilege & skrip firewall khusus | `PASS (APP) / ADMIN REQUIRED (OS FW)` | `Any`, `*`, `0.0.0.0/0`, `/8` ditolak. Pembuatan rule OS Windows memerlukan otorisasi UAC Administrator (shell uji non-Admin). |
| **D** | Akses dari PC client yang diizinkan (fisik) | `NOT TESTED (PHYSICAL PC)` | Terverifikasi pada lapisan aplikasi (`192.168.1.72` → `200 OK` saat `lan_enabled=True`); uji fisik dari PC B/C dilakukan di jaringan kantor setelah rule FW diotorisasi. |
| **E** | Akses dari client tidak diizinkan ditolak | `PASS (APP LAYER)` | `is_client_ip_allowed` menolak `192.168.1.99` & `10.0.0.5` saat hanya `192.168.1.80,192.168.1.81` diizinkan; LAN IP ditolak `HTTP 403` saat `lan_enabled=False`. |
| **F** | Disable LAN blokir client tanpa matikan backend lokal | `PASS` | Setelah `disable-lan`: `192.168.1.72/health` → `HTTP 403`, sedangkan `127.0.0.1/health` tetap `HTTP 200` dan MariaDB `PID 18412` tetap berjalan. |
| **G** | Enable LAN kembali memulihkan akses | `PASS (APP LAYER)` | Setelah `enable-lan --remote 192.168.1.0/24`: `192.168.1.72/health` kembali `HTTP 200`. |
| **H** | Aplikasi lain & rule firewall lain tidak berubah | `PASS` | Seluruh profil Windows Firewall tetap `Enabled: True`; rule lain tidak dimodifikasi. |
| **I** | Tidak menyebabkan duplicate firewall rule | `PASS (SCRIPT VERIFIED)` | `scripts/dss_pik_firewall.ps1` menghapus rule `DSS-PIK - LAN Access` eksisting sebelum membuat 1 rule baru. |
| **J** | Seluruh regression tests DSS-PIK PASS | `PASS` | **36/36 passed** (`test_standardized_decision_json.py`, `test_phase4*`). |
| **K** | Perubahan dapat di-rollback | `PASS` | `DSS-PIK.bat rollback-lan` mereset `config/lan_access_policy.json` ke localhost-only dan menghapus rule `DSS-PIK - LAN Access`. |
| **L** | Profil Wi-Fi tetap sama seperti sebelum implementasi | `PASS` | `SM1-Fisabilillah (Wi-Fi)` tetap **`Public`** sebelum dan sesudah pengujian. |

---

## 6. PROSEDUR ROLLBACK, UJI PC CLIENT, & MIGRASI KE PC SERVER BARU

### A. Rollback Cepat
Jalankan `DSS-PIK.bat rollback-lan` (atau hapus rule `DSS-PIK - LAN Access` via PowerShell Admin). Profil Wi-Fi, Windows Firewall global, MariaDB, dan rule aplikasi lain tidak terdampak.

### B. Cara Menguji dari Komputer Lain (PC B & PC C)
1. Pada PC Server, buka `DSS-PIK.bat` → pilih `[5] ENABLE LAN ACCESS` → masukkan IP PC B & PC C (mis. `192.168.1.80,192.168.1.81`) atau subnet kantor (`192.168.1.0/24`) → setujui prompt UAC Administrator.
2. Dari PC B (diizinkan): buka `http://<IP_SERVER>:8000` → pastikan login & dashboard berhasil.
3. Dari PC yang tidak masuk daftar IP (jika menggunakan daftar IP spesifik): pastikan akses ditolak (`timeout` dari Firewall / `HTTP 403` dari aplikasi).
4. Di PC Server, pilih `[6] DISABLE LAN ACCESS` → pastikan PC B tidak dapat mengakses lagi sementara PC Server (`http://127.0.0.1:8000`) tetap berjalan normal.

### C. Keterbatasan Keamanan HTTP LAN
Komunikasi pada port `8000` menggunakan HTTP plain (tidak terenkripsi). Pembatasan firewall + IP allowlist mencegah akses dari jaringan asing, namun **tidak mengenkripsi trafik di Wi-Fi kantor**. Gunakan hanya pada jaringan internal BMKG, dan pertimbangkan reverse proxy HTTPS internal untuk hardening tahap berikutnya.

### D. Panduan Konfigurasi Ulang Saat Migrasi ke PC Server Baru
1. Setelah menyalin folder DSS-PIK ke PC Server kantor BMKG dan menjalankan `setup_dss_pik_new_pc.bat`, jalankan `DSS-PIK.bat`.
2. Jalankan `[7] LAN DIAGNOSTICS` — sistem akan mendeteksi otomatis adapter, IPv4, subnet, gateway, profil jaringan, dan path `python.exe` baru (tanpa hardcoded path PC lama).
3. Jalankan `[5] ENABLE LAN ACCESS` dan setujui UAC Administrator pada PC baru untuk membuat rule `DSS-PIK - LAN Access` yang sesuai dengan jaringan kantor BMKG.
