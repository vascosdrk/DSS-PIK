<#
.SYNOPSIS
    DSS-PIK Safe Windows Defender Firewall Manager (Least-Privilege, Scoped Rule Only).
.DESCRIPTION
    Manages ONLY the dedicated inbound rule "DSS-PIK - LAN Access" for TCP port 8000.
    - NEVER changes Windows Wi-Fi NetworkCategory (Public stays Public).
    - NEVER disables Windows Defender Firewall.
    - NEVER modifies or deletes firewall rules belonging to other applications.
    - NEVER opens MariaDB port 3306 to LAN.
    - Prevents duplicate rules by removing stale "DSS-PIK - LAN Access" rules before creation.
#>
param(
    [Parameter(Mandatory = $true)]
    [ValidateSet("status", "enable", "disable", "rollback")]
    [string]$Action,

    [string]$RuleName = "DSS-PIK - LAN Access",
    [int]$LocalPort = 8000,
    [string]$InterfaceAlias = "",
    [string]$RemoteAddress = "",
    [string]$ProfileName = "",
    [string]$ProgramPath = ""
)

$ErrorActionPreference = "Stop"

function Test-IsAdministrator {
    $id = [Security.Principal.WindowsIdentity]::GetCurrent()
    $pr = New-Object Security.Principal.WindowsPrincipal($id)
    return $pr.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
}

if ($Action -eq "status") {
    $fwProfiles = Get-NetFirewallProfile | Select-Object Name, Enabled, DefaultInboundAction
    $rules = @(Get-NetFirewallRule -DisplayName $RuleName -ErrorAction SilentlyContinue)
    $ruleInfo = @()
    foreach ($r in $rules) {
        $enabledStr = "$($r.Enabled)"
        $ruleInfo += [PSCustomObject]@{
            Name        = $r.Name
            DisplayName = $r.DisplayName
            Enabled     = $enabledStr
            Direction   = "$($r.Direction)"
            Action      = "$($r.Action)"
            Profile     = "$($r.Profile)"
        }
    }
    $out = [PSCustomObject]@{
        is_admin          = (Test-IsAdministrator)
        rule_name         = $RuleName
        rule_count        = $rules.Count
        rule_exists       = ($rules.Count -gt 0)
        rule_enabled      = (@($rules | Where-Object { "$($_.Enabled)" -eq "True" }).Count -gt 0)
        rules             = $ruleInfo
        firewall_profiles = @($fwProfiles | ForEach-Object { @{ Name = $_.Name; Enabled = [bool]$_.Enabled } })
    }
    $out | ConvertTo-Json -Depth 5 -Compress
    exit 0
}

# Mutating actions require Administrator privileges
if (-not (Test-IsAdministrator)) {
    Write-Error "Hak Administrator diperlukan untuk aksi firewall '$Action'. Jalankan dengan persetujuan UAC Administrator."
    exit 5
}

if ($Action -eq "enable") {
    if (-not $RemoteAddress -or $RemoteAddress -match '^(Any|\*|0\.0\.0\.0/0)$') {
        Write-Error "RemoteAddress tidak boleh kosong atau 'Any'/'0.0.0.0/0'. Gunakan IP client spesifik atau subnet lokal (mis. 192.168.1.0/24)."
        exit 2
    }
    if (-not $ProfileName -or $ProfileName -notin @("Public", "Private", "Domain")) {
        Write-Error "ProfileName harus salah satu dari: Public, Private, Domain (diterima: '$ProfileName')."
        exit 2
    }

    # Prevent duplicate rules: remove ONLY existing rules with exact DSS-PIK DisplayName
    $existing = @(Get-NetFirewallRule -DisplayName $RuleName -ErrorAction SilentlyContinue)
    if ($existing.Count -gt 0) {
        $existing | Remove-NetFirewallRule -ErrorAction Stop
    }

    $remoteList = @($RemoteAddress -split ',' | ForEach-Object { $_.Trim() } | Where-Object { $_ -ne '' })
    $params = @{
        DisplayName   = $RuleName
        Description   = "DSS-PIK BMKG Tanjungpinang - Scoped LAN Access (TCP $LocalPort, Least Privilege)"
        Direction     = "Inbound"
        Protocol      = "TCP"
        LocalPort     = $LocalPort
        Action        = "Allow"
        RemoteAddress = $remoteList
        Profile       = $ProfileName
        Enabled       = "True"
    }
    if ($InterfaceAlias) {
        $params["InterfaceAlias"] = $InterfaceAlias
    }
    if ($ProgramPath -and (Test-Path -LiteralPath $ProgramPath)) {
        $params["Program"] = $ProgramPath
    }

    New-NetFirewallRule @params | Out-Null
    Write-Output "OK: Rule '$RuleName' berhasil dibuat dan diaktifkan (Port=$LocalPort, Profile=$ProfileName, Interface=$InterfaceAlias, Remote=$($remoteList -join ','))."
    exit 0
}

if ($Action -eq "disable") {
    $existing = @(Get-NetFirewallRule -DisplayName $RuleName -ErrorAction SilentlyContinue)
    if ($existing.Count -eq 0) {
        Write-Output "OK: Rule '$RuleName' tidak ditemukan (sudah nonaktif)."
        exit 0
    }
    $existing | Disable-NetFirewallRule -ErrorAction Stop
    Write-Output "OK: Rule '$RuleName' berhasil dinonaktifkan (aturan aplikasi lain tidak diubah)."
    exit 0
}

if ($Action -eq "rollback") {
    $existing = @(Get-NetFirewallRule -DisplayName $RuleName -ErrorAction SilentlyContinue)
    if ($existing.Count -eq 0) {
        Write-Output "OK: Rule '$RuleName' sudah tidak ada (rollback selesai)."
        exit 0
    }
    $existing | Remove-NetFirewallRule -ErrorAction Stop
    Write-Output "OK: Rule '$RuleName' berhasil dihapus (rollback ke kondisi sebelum Phase 7.3.1)."
    exit 0
}
