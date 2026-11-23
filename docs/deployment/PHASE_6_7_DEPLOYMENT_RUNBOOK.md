# PHASE 6.7 — DEPLOYMENT RUNBOOK

## Menjalankan Production Server
```cmd
run_cews_prod.bat
```
Log tersimpan di `logs\runtime\backend_prod.log`.

## Menghentikan Production Server
```cmd
stop_cews_prod.bat
```

## Verifikasi Kesehatan Layanan
```powershell
Invoke-RestMethod -Uri http://127.0.0.1:8000/health
```
Pastikan mengembalikan `{"status":"ok","service":"cews-api","database":"connected"}`.

