# ==============================================================================
# DSS-PIK BMKG KEPULAUAN RIAU — LAN NETWORK & READINESS CHECK
# ==============================================================================
Write-Host "======================================================================" -ForegroundColor Cyan
Write-Host "  DSS-PIK LAN SERVER - NETWORK & READINESS CHECK" -ForegroundColor Cyan
Write-Host "======================================================================" -ForegroundColor Cyan

# 1. Deteksi IPv4 LAN aktif
$ips = Get-NetIPAddress -AddressFamily IPv4 | Where-Object {
    $_.IPAddress -ne '127.0.0.1' -and
    $_.InterfaceAlias -notlike '*Loopback*' -and
    $_.InterfaceAlias -notlike '*vEthernet*' -and
    $_.PrefixOrigin -ne 'WellKnown'
}

if ($ips.Count -eq 0) {
    Write-Host "[WARNING] Tidak ada IPv4 LAN/Wi-Fi aktif yang terdeteksi." -ForegroundColor Yellow
} else {
    foreach ($ip in $ips) {
        Write-Host "Interface : $($ip.InterfaceAlias)"
        Write-Host "Server IP : $($ip.IPAddress)/$($ip.PrefixLength)" -ForegroundColor Green
        Write-Host "Access URL: http://$($ip.IPAddress):8000" -ForegroundColor Green
        Write-Host "----------------------------------------------------------------------"
    }
}

# 2. Cek Port 8000 (Backend) & 3306 (MariaDB)
$port8000 = Get-NetTCPConnection -LocalPort 8000 -State Listen -ErrorAction SilentlyContinue
$port3306 = Get-NetTCPConnection -LocalPort 3306 -State Listen -ErrorAction SilentlyContinue

Write-Host "Backend Port 8000 : $(if ($port8000) { 'LISTENING' } else { 'NOT RUNNING' })"
Write-Host "MariaDB Port 3306 : $(if ($port3306) { 'LISTENING' } else { 'NOT RUNNING' })"

# 3. Cek Health Endpoint
try {
    $health = Invoke-RestMethod -Uri "http://127.0.0.1:8000/health" -TimeoutSec 3
    Write-Host "Health Check      : $($health.status) (DB: $($health.database))" -ForegroundColor Green
} catch {
    Write-Host "Health Check      : FAILED (Backend belum aktif atau DB mati)" -ForegroundColor Red
}

# 4. Panduan Firewall (Manual oleh Administrator)
Write-Host ""
Write-Host "Catatan Firewall (Jalankan di PowerShell Administrator jika Client gagal akses):" -ForegroundColor Yellow
Write-Host '  New-NetFirewallRule -DisplayName "DSS-PIK LAN Port 8000" -Direction Inbound -Protocol TCP -LocalPort 8000 -RemoteAddress LocalSubnet -Action Allow -Profile Private'

