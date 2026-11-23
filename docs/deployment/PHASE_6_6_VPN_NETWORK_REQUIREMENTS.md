# PHASE 6.6 — VPN & NETWORK REQUIREMENTS (ADMINISTRATOR BMKG)

Dokumen ini berisi kebutuhan infrastruktur yang harus disiapkan oleh Administrator Jaringan BMKG:

1. **VPN Institusi BMKG**:
   - Akses remote operator wajib melalui VPN resmi BMKG sebelum mengakses server.
2. **Firewall Allowlist**:
   - **Buka**: Port `443` (HTTPS Reverse Proxy) hanya untuk subnet kantor & subnet VPN BMKG.
   - **Tutup dari Publik/LAN**: Port `3306` (MariaDB), `8000` (FastAPI/Uvicorn), dan `5173` (Vite Dev).
3. **DNS Internal & Sertifikat TLS**:
   - Sediakan hostname internal (contoh: `dss-pik.bmkg-kepri.internal`) yang mengarah ke Private IP server.
   - Pasang sertifikat TLS/HTTPS pada Reverse Proxy (IIS ARR atau Nginx for Windows) yang mem-proxy `https://<hostname>/` ke `http://127.0.0.1:8000/`.

