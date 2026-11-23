"""
DSS-PIK Safe LAN Firewall & Access Policy Service (Phase 7.3.1)
BMKG Stasiun Meteorologi Kelas II Raja Haji Fisabilillah Tanjungpinang

Defense-in-Depth LAN Access Control:
1. Portable policy stored in config/lan_access_policy.json (no secrets, zero hardcoded paths/IPs).
2. Application-level client IP / CIDR enforcement (loopback 127.0.0.1/::1 always allowed).
3. Scoped Windows Defender Firewall management via scripts/dss_pik_firewall.ps1:
   - Rule DisplayName: "DSS-PIK - LAN Access"
   - Direction: Inbound, Protocol: TCP, LocalPort: 8000, Action: Allow
   - Scoped to approved InterfaceAlias, approved RemoteAddress (client IPs or CIDR subnet),
     approved Profile (WITHOUT changing Wi-Fi Public -> Private), and dynamic Program (sys.executable).
   - UAC elevation requested ONLY when operator explicitly enables/disables/rolls back firewall rule.
"""

from __future__ import annotations

import datetime
import ipaddress
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

ROOT_DIR = Path(__file__).resolve().parent.parent
POLICY_FILE = ROOT_DIR / "config" / "lan_access_policy.json"
FIREWALL_SCRIPT = ROOT_DIR / "scripts" / "dss_pik_firewall.ps1"
RULE_NAME = "DSS-PIK - LAN Access"
DEFAULT_PORT = int(os.environ.get("CEWS_PORT", "8000"))

CREATE_NO_WINDOW = 0x08000000 if os.name == "nt" else 0

_POLICY_CACHE: Optional[Dict[str, Any]] = None
_POLICY_CACHE_MTIME: float = -1.0


def default_policy() -> Dict[str, Any]:
    return {
        "lan_enabled": False,
        "approved_network_name": None,
        "approved_interface_alias": None,
        "approved_server_ip": None,
        "approved_subnet": None,
        "approved_remote_addresses": [],
        "approved_profile": None,
        "approved_program": None,
        "rule_name": RULE_NAME,
        "local_port": DEFAULT_PORT,
        "updated_at": None,
    }


def load_lan_policy(use_cache: bool = False) -> Dict[str, Any]:
    global _POLICY_CACHE, _POLICY_CACHE_MTIME
    if not POLICY_FILE.is_file():
        return default_policy()
    try:
        mtime = POLICY_FILE.stat().st_mtime
        if use_cache and _POLICY_CACHE is not None and mtime == _POLICY_CACHE_MTIME:
            return _POLICY_CACHE
        data = json.loads(POLICY_FILE.read_text(encoding="utf-8"))
        merged = default_policy()
        merged.update(data if isinstance(data, dict) else {})
        _POLICY_CACHE = merged
        _POLICY_CACHE_MTIME = mtime
        return merged
    except Exception:
        return default_policy()


def save_lan_policy(policy: Dict[str, Any]) -> None:
    global _POLICY_CACHE, _POLICY_CACHE_MTIME
    POLICY_FILE.parent.mkdir(parents=True, exist_ok=True)
    policy["updated_at"] = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    tmp = POLICY_FILE.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(policy, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    tmp.replace(POLICY_FILE)
    _POLICY_CACHE = dict(policy)
    _POLICY_CACHE_MTIME = POLICY_FILE.stat().st_mtime


def validate_remote_addresses(raw_entries: List[str]) -> Tuple[bool, List[str], str]:
    """
    Validate a list of IPv4 addresses or CIDR subnets.
    Strictly rejects 'Any', '*', '0.0.0.0/0', or invalid entries.
    """
    cleaned: List[str] = []
    for item in raw_entries:
        token = item.strip()
        if not token:
            continue
        if token.lower() in ("any", "*", "0.0.0.0/0", "::/0"):
            return False, [], f"Alamat remote '{token}' ditolak demi prinsip least privilege (tidak boleh Any/0.0.0.0/0)."
        try:
            if "/" in token:
                net = ipaddress.ip_network(token, strict=False)
                if net.prefixlen < 16:
                    return False, [], f"Subnet '{token}' terlalu luas (prefix minimal /16)."
                cleaned.append(str(net))
            else:
                addr = ipaddress.ip_address(token)
                cleaned.append(str(addr))
        except ValueError:
            return False, [], f"Format IP/subnet tidak valid: '{token}'."
    if not cleaned:
        return False, [], "Minimal satu IP client atau subnet lokal yang valid harus ditentukan."
    # Deduplicate preserving order
    unique = list(dict.fromkeys(cleaned))
    return True, unique, "OK"


_DOCKER_GATEWAY_CACHE: Optional[str] = None
_DOCKER_GATEWAY_CHECKED: bool = False


def detect_docker_host_gateway() -> Optional[str]:
    """
    Dynamically detect the single exact IPv4 default gateway of a Linux Docker
    container by reading /proc/net/route (destination 00000000).
    Returns None on non-Linux hosts or if no private IPv4 gateway is found.
    """
    global _DOCKER_GATEWAY_CACHE, _DOCKER_GATEWAY_CHECKED
    if _DOCKER_GATEWAY_CHECKED:
        return _DOCKER_GATEWAY_CACHE
    _DOCKER_GATEWAY_CHECKED = True
    route_file = Path("/proc/net/route")
    if not route_file.is_file():
        return None
    try:
        for line in route_file.read_text(encoding="utf-8").splitlines()[1:]:
            parts = line.strip().split()
            if len(parts) >= 3 and parts[1] == "00000000":
                gw_hex = parts[2]
                if len(gw_hex) == 8:
                    octets = [str(int(gw_hex[i:i + 2], 16)) for i in (6, 4, 2, 0)]
                    candidate = ".".join(octets)
                    addr = ipaddress.ip_address(candidate)
                    if addr.is_private and not addr.is_loopback:
                        _DOCKER_GATEWAY_CACHE = candidate
                        return candidate
    except Exception:
        pass
    return None


def is_docker_local_only_mode() -> bool:
    """Return True only when explicit CEWS_DOCKER_LOCAL_ONLY=true is configured."""
    return os.environ.get("CEWS_DOCKER_LOCAL_ONLY", "").strip().lower() == "true"


def get_trusted_proxy_networks() -> List[ipaddress._BaseNetwork]:
    """Parse CEWS_TRUSTED_PROXY_CIDRS (comma-separated CIDRs). Empty by default."""
    raw = os.environ.get("CEWS_TRUSTED_PROXY_CIDRS", "").strip()
    if not raw:
        return []
    nets: List[ipaddress._BaseNetwork] = []
    for token in raw.split(","):
        t = token.strip()
        if not t:
            continue
        try:
            nets.append(ipaddress.ip_network(t, strict=False))
        except ValueError:
            continue
    return nets


def is_trusted_proxy_ip(peer_ip: str) -> bool:
    """Return True only if the direct TCP peer IP belongs to CEWS_TRUSTED_PROXY_CIDRS."""
    if not peer_ip:
        return False
    ip_str = peer_ip.strip()
    if ip_str.startswith("::ffff:"):
        ip_str = ip_str[7:]
    try:
        addr = ipaddress.ip_address(ip_str)
    except ValueError:
        return False
    for net in get_trusted_proxy_networks():
        if addr in net:
            return True
    return False


def is_client_ip_allowed(
    client_ip: str,
    policy: Optional[Dict[str, Any]] = None,
    docker_gateway_override: Optional[str] = None,
    forwarded_real_ip: Optional[str] = None,
) -> Tuple[bool, str]:
    """
    Application-level defense-in-depth check called by FastAPI middleware.
    - Uses ONLY the verified TCP peer IP unless peer_ip is explicitly in
      CEWS_TRUSTED_PROXY_CIDRS (e.g., internal Docker Nginx reverse proxy that
      overwrites X-Real-IP with $remote_addr). Arbitrary X-Forwarded-For headers
      from untrusted peers are NEVER honored.
    - Loopback (127.0.0.1, ::1) is ALWAYS allowed.
    - When CEWS_DOCKER_LOCAL_ONLY=true, ONLY the single dynamically detected
      Docker bridge host gateway IP is additionally allowed (host port must be
      bound strictly to 127.0.0.1:<port>). All other IPs remain blocked.
    - Non-loopback IPs otherwise require lan_enabled=True AND membership in
      approved_remote_addresses.
    """
    if not client_ip:
        return False, "Alamat IP client tidak terdeteksi."

    effective_ip = client_ip.strip()
    if forwarded_real_ip and is_trusted_proxy_ip(effective_ip):
        effective_ip = forwarded_real_ip.strip()

    ip_str = effective_ip
    if ip_str.startswith("::ffff:"):
        ip_str = ip_str[7:]
    try:
        addr = ipaddress.ip_address(ip_str)
    except ValueError:
        return False, f"Alamat IP client tidak valid: {ip_str}"

    if addr.is_loopback:
        return True, "loopback"

    if is_docker_local_only_mode():
        gw_ip = docker_gateway_override if docker_gateway_override is not None else detect_docker_host_gateway()
        if gw_ip:
            try:
                if addr == ipaddress.ip_address(gw_ip):
                    return True, f"docker_local_gateway:{gw_ip}"
            except ValueError:
                pass

    pol = policy if policy is not None else load_lan_policy(use_cache=True)
    if not pol.get("lan_enabled"):
        return False, "Akses LAN DSS-PIK sedang dinonaktifkan oleh operator server."

    allowed_list = pol.get("approved_remote_addresses") or []
    for entry in allowed_list:
        try:
            if "/" in str(entry):
                if addr in ipaddress.ip_network(str(entry), strict=False):
                    return True, f"matched_subnet:{entry}"
            else:
                if addr == ipaddress.ip_address(str(entry)):
                    return True, f"matched_ip:{entry}"
        except ValueError:
            continue

    return False, f"Alamat IP client ({ip_str}) tidak termasuk dalam daftar akses LAN yang disetujui."


def detect_active_network() -> Dict[str, Any]:
    """Dynamically detect active physical LAN/Wi-Fi adapter, IPv4, CIDR subnet, gateway, and profile."""
    info: Dict[str, Any] = {
        "interface_alias": "",
        "interface_desc": "",
        "ipv4": "127.0.0.1",
        "prefix_length": 24,
        "subnet_cidr": "",
        "gateway": "",
        "network_name": "",
        "network_category": "Public",
        "python_exe": sys.executable,
    }
    try:
        ps = (
            "$cfg = Get-NetIPConfiguration | Where-Object { "
            "$_.IPv4Address.IPAddress -and $_.IPv4Address.IPAddress -ne '127.0.0.1' "
            "-and $_.IPv4Address.IPAddress -notlike '169.254.*' "
            "-and $_.InterfaceAlias -notmatch 'Loopback|vEthernet|OpenVPN|Bluetooth|WSL|VMware|VirtualBox|Tailscale' "
            "} | Sort-Object -Property @{Expression={if($_.InterfaceAlias -match 'Wi-Fi|Ethernet'){0}else{1}}} | Select-Object -First 1; "
            "if ($cfg) { "
            "$prof = Get-NetConnectionProfile -InterfaceAlias $cfg.InterfaceAlias -ErrorAction SilentlyContinue | Select-Object -First 1; "
            "@{alias=$cfg.InterfaceAlias; desc=$cfg.InterfaceDescription; ip=$cfg.IPv4Address.IPAddress; "
            "prefix=[int]$cfg.IPv4Address.PrefixLength; gw=($cfg.IPv4DefaultGateway.NextHop -as [string]); "
            "net_name=($prof.Name -as [string]); net_cat=($prof.NetworkCategory -as [string])} | ConvertTo-Json -Compress }"
        )
        res = subprocess.run(
            ["powershell", "-NoProfile", "-Command", ps],
            capture_output=True,
            text=True,
            timeout=8,
            creationflags=CREATE_NO_WINDOW,
        )
        raw = (res.stdout or "").strip()
        if raw:
            d = json.loads(raw)
            info["interface_alias"] = str(d.get("alias") or "")
            info["interface_desc"] = str(d.get("desc") or "")
            info["ipv4"] = str(d.get("ip") or "127.0.0.1")
            info["prefix_length"] = int(d.get("prefix") or 24)
            info["gateway"] = str(d.get("gw") or "")
            info["network_name"] = str(d.get("net_name") or "")
            info["network_category"] = str(d.get("net_cat") or "Public")
            if info["ipv4"] != "127.0.0.1":
                net = ipaddress.ip_network(f"{info['ipv4']}/{info['prefix_length']}", strict=False)
                info["subnet_cidr"] = str(net)
    except Exception:
        pass
    return info


def check_network_drift(policy: Dict[str, Any], current_net: Dict[str, Any]) -> List[str]:
    """Detect whether Wi-Fi SSID, interface, IP, or subnet changed since LAN was approved."""
    drifts: List[str] = []
    if not policy.get("lan_enabled"):
        return drifts
    if policy.get("approved_network_name") and current_net.get("network_name") and policy["approved_network_name"] != current_net["network_name"]:
        drifts.append(
            f"Jaringan berubah dari '{policy['approved_network_name']}' ke '{current_net['network_name']}'."
        )
    if policy.get("approved_interface_alias") and current_net.get("interface_alias") and policy["approved_interface_alias"] != current_net["interface_alias"]:
        drifts.append(
            f"Interface berubah dari '{policy['approved_interface_alias']}' ke '{current_net['interface_alias']}'."
        )
    if policy.get("approved_subnet") and current_net.get("subnet_cidr") and policy["approved_subnet"] != current_net["subnet_cidr"]:
        drifts.append(
            f"Subnet berubah dari '{policy['approved_subnet']}' ke '{current_net['subnet_cidr']}'."
        )
    if policy.get("approved_server_ip") and current_net.get("ipv4") and policy["approved_server_ip"] != current_net["ipv4"]:
        drifts.append(
            f"IP server berubah dari '{policy['approved_server_ip']}' ke '{current_net['ipv4']}'."
        )
    return drifts


def get_firewall_status() -> Dict[str, Any]:
    """Read-only inspection of DSS-PIK Windows Defender Firewall rule (no Admin needed)."""
    fallback = {
        "is_admin": False,
        "rule_name": RULE_NAME,
        "rule_count": 0,
        "rule_exists": False,
        "rule_enabled": False,
        "rules": [],
        "firewall_profiles": [],
    }
    if not FIREWALL_SCRIPT.is_file():
        return fallback
    try:
        res = subprocess.run(
            [
                "powershell",
                "-NoProfile",
                "-ExecutionPolicy",
                "Bypass",
                "-File",
                str(FIREWALL_SCRIPT),
                "-Action",
                "status",
                "-RuleName",
                RULE_NAME,
            ],
            capture_output=True,
            text=True,
            timeout=10,
            creationflags=CREATE_NO_WINDOW,
        )
        raw = (res.stdout or "").strip()
        if raw:
            return json.loads(raw)
    except Exception:
        pass
    return fallback


def build_manual_admin_command(
    action: str,
    interface_alias: str = "",
    remote_addresses: Optional[List[str]] = None,
    profile_name: str = "",
    program_path: str = "",
) -> str:
    parts = [
        "powershell -NoProfile -ExecutionPolicy Bypass",
        f'-File "{FIREWALL_SCRIPT}"',
        f"-Action {action}",
        f'-RuleName "{RULE_NAME}"',
        f"-LocalPort {DEFAULT_PORT}",
    ]
    if action == "enable":
        if interface_alias:
            parts.append(f'-InterfaceAlias "{interface_alias}"')
        if remote_addresses:
            parts.append(f'-RemoteAddress "{",".join(remote_addresses)}"')
        if profile_name:
            parts.append(f'-ProfileName "{profile_name}"')
        if program_path:
            parts.append(f'-ProgramPath "{program_path}"')
    return " ".join(parts)


def run_firewall_action(
    action: str,
    interface_alias: str = "",
    remote_addresses: Optional[List[str]] = None,
    profile_name: str = "",
    program_path: str = "",
    allow_uac_prompt: bool = True,
) -> Tuple[bool, str]:
    """
    Execute scripts/dss_pik_firewall.ps1 for enable/disable/rollback.
    - If already Administrator: runs directly.
    - If non-Administrator and allow_uac_prompt=True: launches elevated PowerShell via UAC RunAs
      (operator sees explicit Windows UAC prompt).
    - If non-Administrator and allow_uac_prompt=False: returns exact manual Admin command.
    """
    fw_stat = get_firewall_status()
    is_admin = bool(fw_stat.get("is_admin"))

    ps_args = [
        "-NoProfile",
        "-ExecutionPolicy",
        "Bypass",
        "-File",
        str(FIREWALL_SCRIPT),
        "-Action",
        action,
        "-RuleName",
        RULE_NAME,
        "-LocalPort",
        str(DEFAULT_PORT),
    ]
    if action == "enable":
        if interface_alias:
            ps_args += ["-InterfaceAlias", interface_alias]
        if remote_addresses:
            ps_args += ["-RemoteAddress", ",".join(remote_addresses)]
        if profile_name:
            ps_args += ["-ProfileName", profile_name]
        if program_path:
            ps_args += ["-ProgramPath", program_path]

    if is_admin:
        res = subprocess.run(
            ["powershell"] + ps_args,
            capture_output=True,
            text=True,
            timeout=15,
            creationflags=CREATE_NO_WINDOW,
        )
        msg = (res.stdout or res.stderr or "").strip()
        return res.returncode == 0, msg

    manual_cmd = build_manual_admin_command(
        action=action,
        interface_alias=interface_alias,
        remote_addresses=remote_addresses,
        profile_name=profile_name,
        program_path=program_path,
    )
    if not allow_uac_prompt:
        return False, f"Memerlukan hak Administrator. Jalankan manual (Run as Administrator):\n  {manual_cmd}"

    # Request explicit UAC elevation via Start-Process -Verb RunAs -Wait
    escaped_args = " ".join(
        f'\\"{a}\\"' if (" " in a or "," in a) else a for a in ps_args
    )
    elevate_cmd = (
        f"$p = Start-Process -FilePath 'powershell.exe' -ArgumentList \"{escaped_args}\" "
        f"-Verb RunAs -Wait -PassThru; exit $p.ExitCode"
    )
    try:
        res = subprocess.run(
            ["powershell", "-NoProfile", "-Command", elevate_cmd],
            capture_output=True,
            text=True,
            timeout=60,
        )
        if res.returncode == 0:
            return True, f"Aksi firewall '{action}' berhasil diterapkan dengan otorisasi Administrator."
        return False, (
            f"Otorisasi Administrator dibatalkan atau gagal (exit {res.returncode}).\n"
            f"Perintah manual (Run as Administrator):\n  {manual_cmd}"
        )
    except Exception as exc:
        return False, f"Gagal meminta elevasi UAC ({exc}).\nPerintah manual:\n  {manual_cmd}"


def run_lan_diagnostics() -> Dict[str, Any]:
    net = detect_active_network()
    pol = load_lan_policy(use_cache=False)
    fw = get_firewall_status()
    drifts = check_network_drift(pol, net)
    return {
        "network": net,
        "policy": pol,
        "firewall": fw,
        "drifts": drifts,
    }
