"""
DSS-PIK Unified Operational Launcher & Service Manager
BMKG Stasiun Meteorologi Kelas II Raja Haji Fisabilillah Tanjungpinang

Single entry point for START, STOP, RESTART, and STATUS of DSS-PIK:
- Auto-detects project root dynamically (zero hardcoded paths)
- Validates Python environment, .env, MariaDB (auto-starts if installed & stopped),
  database connectivity (cews_db), and frontend production bundle (frontend/dist)
- Starts FastAPI/Uvicorn on 0.0.0.0:8000 with CEWS_SERVE_FRONTEND=true
- Enforces process-ownership verification, port-conflict detection, stale PID/lock
  cleanup, idempotent startup, and graceful shutdown (never kills unrelated apps)
- Auto-detects active IPv4 LAN address and launches default browser on server PC
"""

from __future__ import annotations

import argparse
import ctypes
import datetime
import json
import os
import re
import signal
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
import webbrowser
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from dotenv import load_dotenv

ROOT_DIR = Path(__file__).resolve().parent.parent
load_dotenv(ROOT_DIR / ".env")

from backend.config import INSTITUTION_NAME, SYSTEM_NAME  # noqa: E402
from backend.lan_firewall_service import (  # noqa: E402
    RULE_NAME as LAN_RULE_NAME,
    check_network_drift,
    detect_active_network,
    get_firewall_status,
    load_lan_policy,
    run_firewall_action,
    run_lan_diagnostics,
    save_lan_policy,
    validate_remote_addresses,
)

RUNTIME_DIR = ROOT_DIR / "logs" / "runtime"
STATE_FILE = RUNTIME_DIR / "dss_pik_state.json"
LOCK_FILE = RUNTIME_DIR / "dss_pik_startup.lock"
BACKEND_LOG = RUNTIME_DIR / "backend_lan.log"
MARIADB_LOG = RUNTIME_DIR / "mariadb_managed.log"
LAUNCHER_LOG = RUNTIME_DIR / "launcher_unified.log"

FRONTEND_DIST_INDEX = ROOT_DIR / "frontend" / "dist" / "index.html"
FRONTEND_SRC_DIR = ROOT_DIR / "frontend" / "src"

BIND_HOST = "0.0.0.0"
BIND_PORT = int(os.environ.get("CEWS_PORT", "8000"))
DB_HOST = os.environ.get("CEWS_DB_HOST", "127.0.0.1")
DB_PORT = int(os.environ.get("CEWS_DB_PORT", "3306"))
DB_NAME = os.environ.get("CEWS_DB_NAME", "cews_db")
DB_USER = os.environ.get("CEWS_DB_USER", "root")
DB_PASSWORD = os.environ.get("CEWS_DB_PASSWORD", "")

STARTUP_TIMEOUT_SEC = 25
DB_STARTUP_TIMEOUT_SEC = 25
SHUTDOWN_GRACE_SEC = 6

# Windows process creation flags
CREATE_NEW_PROCESS_GROUP = 0x00000200
DETACHED_PROCESS = 0x00000008
CREATE_NO_WINDOW = 0x08000000


def _now_str() -> str:
    return datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def log_event(level: str, msg: str, echo: bool = True) -> None:
    RUNTIME_DIR.mkdir(parents=True, exist_ok=True)
    line = f"[{_now_str()}] [{level}] {msg}"
    try:
        with open(LAUNCHER_LOG, "a", encoding="utf-8") as fh:
            fh.write(line + "\n")
    except Exception:
        pass
    if echo:
        print(f"[{level}] {msg}")


# ==============================================================================
# PROCESS INSPECTION & OWNERSHIP VERIFICATION (WINDOWS-SAFE)
# ==============================================================================
def is_pid_alive(pid: Optional[int]) -> bool:
    if not pid or pid <= 0:
        return False
    if os.name == "nt":
        PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
        STILL_ACTIVE = 259
        kernel32 = ctypes.windll.kernel32
        handle = kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, int(pid))
        if not handle:
            return False
        try:
            exit_code = ctypes.c_ulong()
            if kernel32.GetExitCodeProcess(handle, ctypes.byref(exit_code)):
                return exit_code.value == STILL_ACTIVE
            return False
        finally:
            kernel32.CloseHandle(handle)
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False


def get_process_info(pid: int) -> Dict[str, Any]:
    """Return {'pid', 'name', 'cmdline', 'exe'} for a Windows PID."""
    info: Dict[str, Any] = {"pid": pid, "name": "", "cmdline": "", "exe": ""}
    if not is_pid_alive(pid):
        return info
    try:
        ps_cmd = (
            f"$p = Get-CimInstance Win32_Process -Filter 'ProcessId={int(pid)}' "
            f"-ErrorAction SilentlyContinue; "
            f"if ($p) {{ @{{pid=$p.ProcessId;name=$p.Name;cmdline=$p.CommandLine;exe=$p.ExecutablePath}} | ConvertTo-Json -Compress }}"
        )
        res = subprocess.run(
            ["powershell", "-NoProfile", "-Command", ps_cmd],
            capture_output=True,
            text=True,
            timeout=6,
            creationflags=CREATE_NO_WINDOW if os.name == "nt" else 0,
        )
        raw = (res.stdout or "").strip()
        if raw:
            parsed = json.loads(raw)
            info["name"] = str(parsed.get("name") or "")
            info["cmdline"] = str(parsed.get("cmdline") or "")
            info["exe"] = str(parsed.get("exe") or "")
    except Exception:
        pass
    return info


def is_dss_pik_backend_process(pid: int) -> bool:
    """Strictly verify that a PID belongs to DSS-PIK's uvicorn backend."""
    if not is_pid_alive(pid):
        return False
    info = get_process_info(pid)
    cmd = info.get("cmdline", "").lower()
    name = info.get("name", "").lower()
    if "python" in name and "uvicorn" in cmd and "backend.main:app" in cmd:
        return True
    return False


def is_mariadb_process(pid: int) -> bool:
    if not is_pid_alive(pid):
        return False
    info = get_process_info(pid)
    name = info.get("name", "").lower()
    return name in ("mariadbd.exe", "mysqld.exe")


def get_listening_pids(port: int) -> List[int]:
    """Return all unique PIDs currently LISTENING on TCP port."""
    pids: List[int] = []
    try:
        res = subprocess.run(
            ["netstat", "-ano", "-p", "TCP"],
            capture_output=True,
            text=True,
            timeout=6,
            creationflags=CREATE_NO_WINDOW if os.name == "nt" else 0,
        )
        pattern = re.compile(rf":({port})\s+\S+\s+LISTENING\s+(\d+)", re.IGNORECASE)
        for line in (res.stdout or "").splitlines():
            m = pattern.search(line)
            if m:
                pid = int(m.group(2))
                if pid > 0 and pid not in pids:
                    pids.append(pid)
    except Exception:
        pass
    return pids


# ==============================================================================
# STATE & LOCK MANAGEMENT (STALE CLEANUP)
# ==============================================================================
def load_state() -> Dict[str, Any]:
    if not STATE_FILE.exists():
        return {}
    try:
        return json.loads(STATE_FILE.read_text(encoding="utf-8"))
    except Exception:
        return {}


def save_state(state: Dict[str, Any]) -> None:
    RUNTIME_DIR.mkdir(parents=True, exist_ok=True)
    tmp = STATE_FILE.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(state, indent=2, ensure_ascii=False), encoding="utf-8")
    tmp.replace(STATE_FILE)


def clear_state() -> None:
    try:
        if STATE_FILE.exists():
            STATE_FILE.unlink()
    except Exception:
        pass


def acquire_startup_lock() -> bool:
    RUNTIME_DIR.mkdir(parents=True, exist_ok=True)
    if LOCK_FILE.exists():
        try:
            lock_data = json.loads(LOCK_FILE.read_text(encoding="utf-8"))
            lock_pid = int(lock_data.get("pid", 0))
            lock_ts = float(lock_data.get("ts", 0))
            if is_pid_alive(lock_pid) and (time.time() - lock_ts) < 60:
                return False
            # Stale lock -> remove
            log_event("INFO", f"Membersihkan stale startup lock (PID {lock_pid}).")
            LOCK_FILE.unlink(missing_ok=True)
        except Exception:
            LOCK_FILE.unlink(missing_ok=True)
    try:
        LOCK_FILE.write_text(
            json.dumps({"pid": os.getpid(), "ts": time.time()}),
            encoding="utf-8",
        )
        return True
    except Exception:
        return False


def release_startup_lock() -> None:
    try:
        LOCK_FILE.unlink(missing_ok=True)
    except Exception:
        pass


# ==============================================================================
# HEALTH CHECKS, DATABASE DETECTION & AUTO-START
# ==============================================================================
def check_http_health(host: str = "127.0.0.1", port: int = BIND_PORT, timeout: float = 2.5) -> Tuple[bool, Optional[Dict[str, Any]]]:
    url = f"http://{host}:{port}/health"
    try:
        with urllib.request.urlopen(url, timeout=timeout) as resp:
            if resp.status == 200:
                data = json.loads(resp.read().decode("utf-8"))
                if data.get("status") == "ok" and data.get("service") == "cews-api":
                    return True, data
    except Exception:
        pass
    return False, None


def check_frontend_served(host: str = "127.0.0.1", port: int = BIND_PORT, timeout: float = 3.0) -> bool:
    url = f"http://{host}:{port}/"
    try:
        with urllib.request.urlopen(url, timeout=timeout) as resp:
            if resp.status == 200:
                body = resp.read(2048).decode("utf-8", errors="ignore").lower()
                return "<html" in body or "<!doctype html" in body
    except Exception:
        pass
    return False


def check_database_ready() -> Tuple[bool, str]:
    """Verify MariaDB accepts connection AND cews_db responds to a valid query."""
    try:
        import pymysql

        conn = pymysql.connect(
            host=DB_HOST,
            port=DB_PORT,
            user=DB_USER,
            password=DB_PASSWORD,
            database=DB_NAME,
            charset="utf8mb4",
            connect_timeout=3,
            read_timeout=3,
        )
        try:
            with conn.cursor() as cur:
                cur.execute("SELECT COUNT(*) FROM stations")
                row = cur.fetchone()
                cnt = row[0] if row else 0
            return True, f"connected ({DB_NAME}, {cnt} stasiun)"
        finally:
            conn.close()
    except Exception as exc:
        return False, str(exc)


def _find_mariadb_windows_service() -> Optional[str]:
    try:
        ps = (
            "Get-Service | Where-Object { $_.Name -match 'maria|mysql' -or $_.DisplayName -match 'maria|mysql' } "
            "| Select-Object -First 1 -ExpandProperty Name"
        )
        res = subprocess.run(
            ["powershell", "-NoProfile", "-Command", ps],
            capture_output=True,
            text=True,
            timeout=6,
            creationflags=CREATE_NO_WINDOW if os.name == "nt" else 0,
        )
        svc = (res.stdout or "").strip()
        return svc or None
    except Exception:
        return None


def _find_mariadb_executable() -> Tuple[Optional[Path], Optional[Path]]:
    """Locate standalone mariadbd.exe / mysqld.exe and its data directory."""
    candidates: List[Path] = []
    for base in (Path("C:/Program Files"), Path("C:/Program Files (x86)"), Path("C:/")):
        if base.exists():
            for folder in sorted(base.glob("MariaDB*"), reverse=True):
                for exe_name in ("mariadbd.exe", "mysqld.exe"):
                    p = folder / "bin" / exe_name
                    if p.is_file():
                        candidates.append(p)
    for extra in (
        Path("C:/xampp/mysql/bin/mysqld.exe"),
        Path("C:/laragon/bin/mysql"),
    ):
        if extra.is_file():
            candidates.append(extra)
        elif extra.is_dir():
            for p in sorted(extra.rglob("mysqld.exe"), reverse=True):
                candidates.append(p)

    for exe in candidates:
        data_dir = exe.parent.parent / "data"
        if data_dir.is_dir():
            return exe, data_dir
        return exe, None
    return None, None


def ensure_mariadb_running() -> Tuple[bool, bool, Optional[int], str]:
    """
    Ensure MariaDB is running and cews_db is queryable.
    Returns: (ok, managed_by_launcher, managed_pid, detail_message)
    """
    ok, msg = check_database_ready()
    if ok:
        log_event("OK", f"MariaDB sudah aktif: {msg}")
        return True, False, None, msg

    # Port 3306 might be listening while DB credentials/schema failed
    db_pids = get_listening_pids(DB_PORT)
    if db_pids:
        log_event("ERROR", f"Port {DB_PORT} aktif (PID {db_pids}), tetapi koneksi ke '{DB_NAME}' gagal: {msg}")
        return False, False, None, f"Koneksi MariaDB gagal: {msg}"

    log_event("INFO", f"MariaDB tidak aktif pada port {DB_PORT}. Mendeteksi instalasi lokal...")

    # Method 1: Windows Service
    svc_name = _find_mariadb_windows_service()
    if svc_name:
        log_event("INFO", f"Mencoba mengaktifkan Windows Service '{svc_name}'...")
        res = subprocess.run(
            ["powershell", "-NoProfile", "-Command", f"Start-Service -Name '{svc_name}' -ErrorAction Stop"],
            capture_output=True,
            text=True,
            timeout=15,
            creationflags=CREATE_NO_WINDOW if os.name == "nt" else 0,
        )
        if res.returncode == 0:
            for _ in range(DB_STARTUP_TIMEOUT_SEC * 2):
                time.sleep(0.5)
                ok, msg = check_database_ready()
                if ok:
                    log_event("OK", f"Windows Service '{svc_name}' aktif: {msg}")
                    return True, False, None, msg
        else:
            err = (res.stderr or res.stdout or "").strip()
            log_event("WARN", f"Gagal menyalakan service '{svc_name}' (mungkin butuh Administrator): {err}")

    # Method 2: Standalone mariadbd.exe / mysqld.exe
    exe, data_dir = _find_mariadb_executable()
    if exe:
        cmd = [str(exe), "--console"]
        if data_dir:
            cmd.append(f"--datadir={data_dir}")
        cmd.append(f"--port={DB_PORT}")
        log_event("INFO", f"Menjalankan MariaDB standalone: {exe}")
        RUNTIME_DIR.mkdir(parents=True, exist_ok=True)
        with open(MARIADB_LOG, "a", encoding="utf-8") as logf:
            logf.write(f"\n=== MariaDB Start {_now_str()} ===\n")
            proc = subprocess.Popen(
                cmd,
                stdout=logf,
                stderr=logf,
                cwd=str(exe.parent),
                creationflags=(CREATE_NEW_PROCESS_GROUP | DETACHED_PROCESS | CREATE_NO_WINDOW)
                if os.name == "nt"
                else 0,
            )
        for _ in range(DB_STARTUP_TIMEOUT_SEC * 2):
            time.sleep(0.5)
            if proc.poll() is not None:
                log_event("ERROR", f"MariaDB berhenti tak terduga (exit code {proc.returncode}). Periksa {MARIADB_LOG}")
                return False, False, None, f"MariaDB gagal start (exit {proc.returncode})"
            ok, msg = check_database_ready()
            if ok:
                log_event("OK", f"MariaDB standalone siap (PID {proc.pid}): {msg}")
                return True, True, proc.pid, msg
        log_event("ERROR", f"Timeout menunggu MariaDB siap dalam {DB_STARTUP_TIMEOUT_SEC} detik.")
        return False, True, proc.pid, "Timeout koneksi MariaDB"

    log_event(
        "ERROR",
        "Instalasi MariaDB tidak ditemukan dan port 3306 tidak aktif. "
        "Pastikan MariaDB 11+/13+ terinstal dan database cews_db tersedia.",
    )
    return False, False, None, "MariaDB tidak ditemukan"


# ==============================================================================
# NETWORK & FIREWALL DIAGNOSTICS
# ==============================================================================
def detect_lan_ipv4() -> Tuple[str, str]:
    """Return (ipv4_address, adapter_alias) for active physical LAN/Wi-Fi interface."""
    try:
        ps = (
            "$ip = Get-NetIPAddress -AddressFamily IPv4 | Where-Object { "
            "$_.IPAddress -ne '127.0.0.1' -and $_.IPAddress -notlike '169.254.*' "
            "-and $_.AddressState -eq 'Preferred' "
            "-and $_.InterfaceAlias -notmatch 'Loopback|vEthernet|OpenVPN|Bluetooth|WSL|VMware|VirtualBox|Tailscale' "
            "} | Sort-Object -Property @{Expression={if($_.InterfaceAlias -match 'Wi-Fi|Ethernet'){0}else{1}}} "
            "| Select-Object -First 1 InterfaceAlias, IPAddress; "
            "if ($ip) { @{ip=$ip.IPAddress; alias=$ip.InterfaceAlias} | ConvertTo-Json -Compress }"
        )
        res = subprocess.run(
            ["powershell", "-NoProfile", "-Command", ps],
            capture_output=True,
            text=True,
            timeout=6,
            creationflags=CREATE_NO_WINDOW if os.name == "nt" else 0,
        )
        raw = (res.stdout or "").strip()
        if raw:
            d = json.loads(raw)
            if d.get("ip"):
                return str(d["ip"]), str(d.get("alias") or "LAN")
    except Exception:
        pass

    # Fallback via UDP socket routing table (no packet sent)
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("192.168.1.1", 80))
        ip = s.getsockname()[0]
        s.close()
        if ip and not ip.startswith("127."):
            return ip, "LAN"
    except Exception:
        pass
    return "127.0.0.1", "Loopback"


def get_network_profile_info() -> Dict[str, Any]:
    """Read active Windows network category and dedicated DSS-PIK firewall status."""
    info = {"profile_name": "", "category": "Unknown", "has_dss_rule": False}
    try:
        ps = (
            "$p = Get-NetConnectionProfile | Select-Object -First 1 Name, NetworkCategory; "
            "$r = Get-NetFirewallRule -DisplayName 'DSS-PIK*' -ErrorAction SilentlyContinue | Select-Object -First 1 DisplayName; "
            "@{name=($p.Name -as [string]); cat=($p.NetworkCategory -as [string]); has_rule=([bool]$r)} | ConvertTo-Json -Compress"
        )
        res = subprocess.run(
            ["powershell", "-NoProfile", "-Command", ps],
            capture_output=True,
            text=True,
            timeout=6,
            creationflags=CREATE_NO_WINDOW if os.name == "nt" else 0,
        )
        raw = (res.stdout or "").strip()
        if raw:
            d = json.loads(raw)
            info["profile_name"] = d.get("name") or ""
            info["category"] = d.get("cat") or "Unknown"
            info["has_dss_rule"] = bool(d.get("has_rule"))
    except Exception:
        pass
    return info


# ==============================================================================
# FRONTEND & DEPENDENCY VALIDATION
# ==============================================================================
def validate_dependencies() -> Tuple[bool, List[str]]:
    errors: List[str] = []
    for mod in ("fastapi", "uvicorn", "pymysql", "pandas", "dotenv", "bcrypt"):
        try:
            __import__(mod)
        except ImportError:
            errors.append(f"Modul Python '{mod}' tidak terpasang. Jalankan: pip install -r requirements-lock.txt")

    if not (ROOT_DIR / ".env").is_file():
        errors.append("Berkas konfigurasi '.env' tidak ditemukan di root repository.")

    if not FRONTEND_DIST_INDEX.is_file():
        errors.append(
            "Frontend production build tidak ditemukan (frontend/dist/index.html). "
            "Jalankan: npm --prefix frontend run build"
        )
    return len(errors) == 0, errors


def check_frontend_freshness() -> Tuple[bool, str]:
    """Check whether frontend/dist/index.html is up-to-date with frontend/src."""
    if not FRONTEND_DIST_INDEX.is_file():
        return False, "frontend/dist/index.html tidak ditemukan"
    dist_mtime = FRONTEND_DIST_INDEX.stat().st_mtime
    newest_src = 0.0
    newest_file = ""
    if FRONTEND_SRC_DIR.is_dir():
        for p in FRONTEND_SRC_DIR.rglob("*"):
            if p.is_file() and ".bak_" not in p.name:
                mt = p.stat().st_mtime
                if mt > newest_src:
                    newest_src = mt
                    newest_file = p.name
    idx_src = ROOT_DIR / "frontend" / "index.html"
    if idx_src.is_file() and idx_src.stat().st_mtime > newest_src:
        newest_src = idx_src.stat().st_mtime
        newest_file = "frontend/index.html"

    if newest_src > dist_mtime + 2.0:
        return False, f"Source '{newest_file}' lebih baru daripada frontend/dist (pertimbangkan: npm --prefix frontend run build)"
    return True, "Production build sesuai dengan source terbaru"


# ==============================================================================
# CORE OPERATIONS: INSPECT, START, STOP, RESTART
# ==============================================================================
def inspect_runtime() -> Dict[str, Any]:
    """Inspect current runtime status without modifying anything."""
    state = load_state()
    state_pid = state.get("backend_pid")
    port_pids = get_listening_pids(BIND_PORT)

    healthy, health_payload = check_http_health("127.0.0.1", BIND_PORT)
    dss_pids = [p for p in port_pids if is_dss_pik_backend_process(p)]
    foreign_pids = [p for p in port_pids if p not in dss_pids]

    # Clean stale state if state_pid is dead and no DSS-PIK process is running
    if state_pid and not is_pid_alive(state_pid) and not dss_pids:
        clear_state()
        state = {}

    running_pid = dss_pids[0] if dss_pids else (state_pid if (state_pid and is_dss_pik_backend_process(state_pid)) else None)
    db_ok, db_msg = check_database_ready()
    lan_ip, adapter = detect_lan_ipv4()
    net_info = get_network_profile_info()

    return {
        "running": bool(running_pid and healthy),
        "backend_pid": running_pid,
        "port_conflict": bool(foreign_pids and not dss_pids),
        "foreign_pids": foreign_pids,
        "health_ok": healthy,
        "health_payload": health_payload,
        "db_ok": db_ok,
        "db_msg": db_msg,
        "lan_ip": lan_ip,
        "adapter": adapter,
        "local_url": f"http://127.0.0.1:{BIND_PORT}",
        "lan_url": f"http://{lan_ip}:{BIND_PORT}",
        "net_info": net_info,
        "state": state,
    }


def _open_browser_url(url: str) -> str:
    try:
        if webbrowser.open(url, new=2):
            return "OPEN REQUESTED"
    except Exception:
        pass
    try:
        res = subprocess.run(
            ["powershell", "-NoProfile", "-Command", f"Start-Process -FilePath '{url}' -ErrorAction Stop"],
            capture_output=True,
            timeout=5,
            creationflags=CREATE_NO_WINDOW if os.name == "nt" else 0,
        )
        if res.returncode == 0:
            return "OPEN REQUESTED"
    except Exception:
        pass
    return "FAILED"


def _terminate_verified_pid(pid: int, label: str) -> bool:
    """Gracefully terminate a verified PID (SIGTERM / CTRL_BREAK, then forced PID tree if needed)."""
    if not is_pid_alive(pid):
        return True
    log_event("STOP", f"Menghentikan {label} (PID {pid}) secara graceful...")
    try:
        if os.name == "nt":
            os.kill(pid, signal.CTRL_BREAK_EVENT)
        else:
            os.kill(pid, signal.SIGTERM)
    except Exception:
        pass

    deadline = time.time() + SHUTDOWN_GRACE_SEC
    while time.time() < deadline:
        if not is_pid_alive(pid):
            log_event("OK", f"{label} (PID {pid}) berhenti secara graceful.")
            return True
        time.sleep(0.3)

    # Graceful timeout -> terminate ONLY this exact verified PID tree
    log_event("WARN", f"{label} (PID {pid}) belum berhenti dalam {SHUTDOWN_GRACE_SEC}s, mengakhiri PID spesifik...")
    subprocess.run(
        ["taskkill", "/PID", str(pid), "/T", "/F"],
        capture_output=True,
        timeout=8,
        creationflags=CREATE_NO_WINDOW if os.name == "nt" else 0,
    )
    time.sleep(0.5)
    return not is_pid_alive(pid)


def start_dss_pik(open_browser: bool = True) -> int:
    if not acquire_startup_lock():
        log_event("WARN", "Proses startup DSS-PIK lain sedang berjalan. Mohon tunggu sebentar.")
        return 1

    try:
        print("=" * 72)
        print(f"  {SYSTEM_NAME} — UNIFIED LAUNCHER")
        print(f"  {INSTITUTION_NAME}")
        print(f"  Root Workspace : {ROOT_DIR}")
        print("=" * 72)

        # 1. Check current runtime (idempotent + port conflict guard)
        status = inspect_runtime()
        if status["port_conflict"]:
            fp = status["foreign_pids"][0]
            finfo = get_process_info(fp)
            log_event(
                "ERROR",
                f"PORT CONFLICT: Port {BIND_PORT} sedang digunakan aplikasi lain "
                f"(PID={fp}, Name='{finfo['name']}', Cmd='{finfo['cmdline'][:90]}'). "
                f"DSS-PIK tidak akan menghentikan proses milik aplikasi lain.",
            )
            return 2

        if status["running"]:
            log_event("OK", f"DSS-PIK sudah aktif (PID {status['backend_pid']}). Tidak membuat instance ganda.")
            print_status_banner(status, browser_status="SKIPPED (Already Running)")
            if open_browser:
                _open_browser_url(status["local_url"] + "/")
            return 0

        # 2. Validate Python deps, .env, and frontend production build
        deps_ok, dep_errors = validate_dependencies()
        if not deps_ok:
            for err in dep_errors:
                log_event("ERROR", err)
            return 3

        fresh_ok, fresh_msg = check_frontend_freshness()
        if fresh_ok:
            log_event("OK", f"Frontend production build siap: {fresh_msg}")
        else:
            log_event("WARN", f"Frontend build notice: {fresh_msg}")

        # 3. Ensure MariaDB is running and cews_db is queryable
        db_ok, mariadb_managed, mariadb_pid, db_msg = ensure_mariadb_running()
        if not db_ok:
            log_event("ERROR", f"Database belum siap: {db_msg}")
            return 4

        # 4. Launch Uvicorn Production LAN Server
        RUNTIME_DIR.mkdir(parents=True, exist_ok=True)
        env = os.environ.copy()
        env["CEWS_ENV"] = "production"
        env["CEWS_SERVE_FRONTEND"] = "true"
        env["CEWS_ENABLE_DOCS"] = "false"
        env["CEWS_COOKIE_SECURE"] = "false"
        env["PYTHONUNBUFFERED"] = "1"

        cmd = [
            sys.executable,
            "-m",
            "uvicorn",
            "backend.main:app",
            "--host",
            BIND_HOST,
            "--port",
            str(BIND_PORT),
            "--workers",
            "1",
        ]
        log_event("START", f"Menjalankan FastAPI/Uvicorn pada {BIND_HOST}:{BIND_PORT} (production + SPA serving)...")
        with open(BACKEND_LOG, "a", encoding="utf-8") as logf:
            logf.write(f"\n=== DSS-PIK Backend Start {_now_str()} ===\n")
            proc = subprocess.Popen(
                cmd,
                cwd=str(ROOT_DIR),
                env=env,
                stdout=logf,
                stderr=logf,
                creationflags=(CREATE_NEW_PROCESS_GROUP | DETACHED_PROCESS | CREATE_NO_WINDOW)
                if os.name == "nt"
                else 0,
            )

        # 5. Wait for /health HTTP 200 & frontend HTTP 200
        ready = False
        health_data: Optional[Dict[str, Any]] = None
        for _ in range(STARTUP_TIMEOUT_SEC * 2):
            time.sleep(0.5)
            if proc.poll() is not None:
                log_event("ERROR", f"Backend berhenti tak terduga (exit code {proc.returncode}).")
                break
            ok_h, h_data = check_http_health("127.0.0.1", BIND_PORT)
            if ok_h:
                ready = True
                health_data = h_data
                break

        if not ready:
            log_event("ERROR", f"Backend gagal merespons /health dalam {STARTUP_TIMEOUT_SEC} detik. Melakukan recovery...")
            if is_pid_alive(proc.pid):
                _terminate_verified_pid(proc.pid, "Failed DSS-PIK Backend")
            _print_log_tail(BACKEND_LOG, 20)
            return 5

        fe_ok = check_frontend_served("127.0.0.1", BIND_PORT)
        if not fe_ok:
            log_event("WARN", "Endpoint /health OK, tetapi frontend SPA pada '/' tidak mengembalikan HTML 200.")

        # 6. Persist verified state
        save_state(
            {
                "backend_pid": proc.pid,
                "backend_cmdline": " ".join(cmd),
                "started_at": _now_str(),
                "host": BIND_HOST,
                "port": BIND_PORT,
                "root_dir": str(ROOT_DIR),
                "mariadb_managed": mariadb_managed,
                "mariadb_pid": mariadb_pid,
            }
        )

        # 7. Open browser automatically on Server PC
        browser_status = "SKIPPED (--no-browser)"
        if open_browser:
            browser_status = _open_browser_url(f"http://127.0.0.1:{BIND_PORT}/")

        final_status = inspect_runtime()
        log_event(
            "OK",
            f"DSS-PIK berhasil dijalankan (PID {proc.pid}) | Local: {final_status['local_url']} | LAN: {final_status['lan_url']}",
        )
        print_status_banner(final_status, browser_status=browser_status)
        return 0
    finally:
        release_startup_lock()


def stop_dss_pik() -> int:
    status = inspect_runtime()
    state = status.get("state") or {}
    stopped_any = False

    # 1. Stop verified DSS-PIK backend PIDs (never touch foreign processes)
    target_pids: List[int] = []
    if status.get("backend_pid") and is_dss_pik_backend_process(status["backend_pid"]):
        target_pids.append(status["backend_pid"])
    for p in get_listening_pids(BIND_PORT):
        if p not in target_pids and is_dss_pik_backend_process(p):
            target_pids.append(p)

    if not target_pids:
        if status.get("port_conflict"):
            log_event(
                "WARN",
                f"Port {BIND_PORT} digunakan aplikasi lain (PID {status['foreign_pids']}). Tidak dihentikan oleh DSS-PIK.",
            )
        else:
            log_event("INFO", "Tidak ada proses backend DSS-PIK yang sedang berjalan.")
    else:
        for pid in target_pids:
            _terminate_verified_pid(pid, "DSS-PIK Backend")
            stopped_any = True

    # 2. Only stop MariaDB if dedicated & started by this launcher
    if state.get("mariadb_managed") and state.get("mariadb_pid"):
        mpid = int(state["mariadb_pid"])
        if is_mariadb_process(mpid):
            log_event("STOP", f"Menghentikan MariaDB yang dikelola launcher (PID {mpid})...")
            _terminate_verified_pid(mpid, "Managed MariaDB")
    else:
        log_event("INFO", "MariaDB tetap aktif (shared / sudah berjalan sebelum launcher).")

    clear_state()
    if stopped_any:
        log_event("OK", "Layanan DSS-PIK berhasil dihentikan secara bersih.")
    return 0


def restart_dss_pik(open_browser: bool = False) -> int:
    log_event("INFO", "Memulai ulang layanan DSS-PIK (RESTART)...")
    stop_dss_pik()
    time.sleep(1.0)
    return start_dss_pik(open_browser=open_browser)


def _print_log_tail(path: Path, lines: int = 20) -> None:
    if not path.is_file():
        return
    try:
        content = path.read_text(encoding="utf-8", errors="ignore").splitlines()
        print("-" * 72)
        for ln in content[-lines:]:
            print("  " + ln)
        print("-" * 72)
    except Exception:
        pass


def print_status_banner(status: Dict[str, Any], browser_status: Optional[str] = None) -> None:
    pol = load_lan_policy(use_cache=False)
    fw = get_firewall_status()
    active_net = detect_active_network()
    drifts = check_network_drift(pol, active_net)

    lan_policy_on = bool(pol.get("lan_enabled"))
    fw_rule_on = bool(fw.get("rule_enabled"))
    remote_scope = ", ".join(pol.get("approved_remote_addresses") or []) or "-"

    print("=" * 72)
    print(f"  {SYSTEM_NAME} — SYSTEM MANAGER & LAN STATUS")
    print(f"  Institusi  : {INSTITUTION_NAME}")
    print(f"  Backend    : {'RUNNING (PID ' + str(status['backend_pid']) + ')' if status['running'] else 'STOPPED'}")
    print(f"  Database   : {'CONNECTED — ' + status['db_msg'] if status['db_ok'] else 'DISCONNECTED — ' + status['db_msg']}")
    print(f"  Frontend   : PRODUCTION SPA (Served via FastAPI :{BIND_PORT})")
    print(f"  Adapter    : {active_net['interface_alias'] or status['adapter']} ({active_net['ipv4']}/{active_net['prefix_length']})")
    print(f"  NetProfile : {active_net['network_name'] or '-'} ({active_net['network_category']}) [TIDAK DIUBAH]")
    print(f"  URL Server : {status['local_url']}")
    if lan_policy_on:
        print(f"  LAN Policy : ENABLED (Scope: {remote_scope})")
        print(f"  URL Client : {status['lan_url']}   <-- Khusus IP/Subnet disetujui")
    else:
        print("  LAN Policy : DISABLED (Localhost Only — 127.0.0.1)")
    fw_label = "ENABLED" if fw_rule_on else ("DISABLED" if fw.get("rule_exists") else "NOT INSTALLED")
    print(f"  FW Rule    : {LAN_RULE_NAME} [{fw_label}]")
    if browser_status:
        print(f"  Browser    : {browser_status}")
    if drifts:
        print("-" * 72)
        print("  [PERINGATAN PERUBAHAN JARINGAN / NETWORK DRIFT]")
        for d in drifts:
            print(f"  * {d}")
        print("  * Evaluasi ulang melalui menu [5] ENABLE LAN ACCESS atau nonaktifkan [6].")
    print("-" * 72)
    print(f"  Log Backend: {BACKEND_LOG}")
    print(f"  Log Manager: {LAUNCHER_LOG}")
    print("=" * 72)


def print_lan_diagnostics() -> int:
    diag = run_lan_diagnostics()
    net = diag["network"]
    pol = diag["policy"]
    fw = diag["firewall"]
    drifts = diag["drifts"]
    st = inspect_runtime()

    print("=" * 72)
    print("  DSS-PIK — LAN DIAGNOSTICS (PHASE 7.3.1)")
    print("=" * 72)
    print(f"  Backend (8000)      : {'RUNNING (PID ' + str(st['backend_pid']) + ')' if st['running'] else 'STOPPED'}")
    print(f"  MariaDB (3306)      : {'CONNECTED' if st['db_ok'] else 'DISCONNECTED'} (Lokal 127.0.0.1, TIDAK dibuka ke LAN)")
    print(f"  Adapter Aktif       : {net['interface_alias']} ({net['interface_desc']})")
    print(f"  IPv4 / Subnet       : {net['ipv4']}/{net['prefix_length']} -> Subnet {net['subnet_cidr'] or '-'}")
    print(f"  Default Gateway     : {net['gateway'] or '-'}")
    print(f"  Network Profile     : {net['network_name'] or '-'} ({net['network_category']}) [Asli Windows, tidak diubah]")
    print(f"  Backend Executable  : {net['python_exe']}")
    print("-" * 72)
    fw_profs = ", ".join(f"{p['Name']}={'ON' if p['Enabled'] else 'OFF'}" for p in fw.get("firewall_profiles") or [])
    print(f"  Windows Firewall    : {fw_profs or 'Unknown'}")
    print(f"  Rule '{LAN_RULE_NAME}': Exists={fw['rule_exists']}, Enabled={fw['rule_enabled']}, Count={fw['rule_count']}")
    print(f"  App LAN Policy      : {'ENABLED' if pol.get('lan_enabled') else 'DISABLED'}")
    print(f"  Approved Remotes    : {', '.join(pol.get('approved_remote_addresses') or []) or '(kosong)'}")
    print(f"  Approved Profile    : {pol.get('approved_profile') or '-'}")
    print(f"  Approved Network    : {pol.get('approved_network_name') or '-'}")
    if drifts:
        print("-" * 72)
        print("  [NETWORK DRIFT TERDETEKSI]")
        for d in drifts:
            print(f"  ! {d}")
    print("=" * 72)
    return 0


def enable_lan_access_flow(
    remote_arg: Optional[str] = None,
    auto_confirm: bool = False,
    allow_uac: bool = True,
) -> int:
    net = detect_active_network()
    if net["ipv4"] == "127.0.0.1" or not net["interface_alias"]:
        log_event("ERROR", "Tidak ada adapter LAN/Wi-Fi IPv4 aktif yang terdeteksi.")
        return 1

    print("=" * 72)
    print("  DSS-PIK — ENABLE LAN ACCESS (LEAST-PRIVILEGE FIREWALL)")
    print("=" * 72)
    print(f"  Adapter Aktif   : {net['interface_alias']}")
    print(f"  Jaringan        : {net['network_name'] or '-'} (Profile: {net['network_category']} — TIDAK diubah)")
    print(f"  IP Server       : {net['ipv4']} | Subnet terdeteksi: {net['subnet_cidr']}")
    print(f"  Port Lokal      : TCP {BIND_PORT} (MariaDB 3306 tetap tertutup)")
    print(f"  Program Target  : {net['python_exe']}")
    print(f"  Nama Rule       : {LAN_RULE_NAME}")
    print("-" * 72)

    if remote_arg:
        raw_remotes = [x.strip() for x in remote_arg.split(",") if x.strip()]
    else:
        print("  Tentukan perangkat client yang diizinkan (DILARANG 'Any' atau '0.0.0.0/0'):")
        print(f"  - Tekan ENTER untuk memakai subnet lokal saat ini: {net['subnet_cidr']}")
        print("  - Atau ketik daftar IP client dipisahkan koma (misal: 192.168.1.80,192.168.1.81)")
        try:
            user_in = input("  IP/Subnet diizinkan: ").strip()
        except (EOFError, KeyboardInterrupt):
            return 1
        raw_remotes = [x.strip() for x in user_in.split(",") if x.strip()] if user_in else [net["subnet_cidr"]]

    ok_val, valid_remotes, err_msg = validate_remote_addresses(raw_remotes)
    if not ok_val:
        log_event("ERROR", err_msg)
        return 2

    if not auto_confirm:
        print(f"\n  Konfirmasi: Aktifkan akses LAN untuk [{', '.join(valid_remotes)}] pada '{net['interface_alias']}'?")
        print("  * Profil Wi-Fi TIDAK akan diubah.")
        print("  * Hanya rule khusus 'DSS-PIK - LAN Access' yang dibuat (UAC Admin akan diminta).")
        try:
            ans = input("  Setujui dan lanjutkan? [y/N]: ").strip().lower()
        except (EOFError, KeyboardInterrupt):
            return 1
        if ans not in ("y", "ya", "yes"):
            log_event("INFO", "Aktivasi LAN dibatalkan oleh operator.")
            return 0

    policy = load_lan_policy(use_cache=False)
    policy.update(
        {
            "lan_enabled": True,
            "approved_network_name": net["network_name"],
            "approved_interface_alias": net["interface_alias"],
            "approved_server_ip": net["ipv4"],
            "approved_subnet": net["subnet_cidr"],
            "approved_remote_addresses": valid_remotes,
            "approved_profile": net["network_category"],
            "approved_program": net["python_exe"],
            "rule_name": LAN_RULE_NAME,
            "local_port": BIND_PORT,
        }
    )
    save_lan_policy(policy)
    log_event("OK", f"Kebijakan aplikasi LAN disimpan (lan_enabled=True, remotes={valid_remotes}).")

    fw_ok, fw_msg = run_firewall_action(
        action="enable",
        interface_alias=net["interface_alias"],
        remote_addresses=valid_remotes,
        profile_name=net["network_category"],
        program_path=net["python_exe"],
        allow_uac_prompt=allow_uac,
    )
    if fw_ok:
        log_event("OK", fw_msg)
        return 0
    log_event("WARN", f"Kebijakan aplikasi aktif, tetapi rule Windows Firewall belum diterapkan:\n{fw_msg}")
    return 5


def disable_lan_access_flow(auto_confirm: bool = False, allow_uac: bool = True) -> int:
    if not auto_confirm:
        print("\n  Konfirmasi: Nonaktifkan akses LAN DSS-PIK?")
        print("  * Backend lokal (127.0.0.1:8000) dan MariaDB tetap berjalan normal.")
        print("  * Hanya rule 'DSS-PIK - LAN Access' yang dinonaktifkan.")
        try:
            ans = input("  Lanjutkan? [y/N]: ").strip().lower()
        except (EOFError, KeyboardInterrupt):
            return 1
        if ans not in ("y", "ya", "yes"):
            log_event("INFO", "Penonaktifan LAN dibatalkan oleh operator.")
            return 0

    # Immediately block non-loopback requests at app middleware layer (no restart needed)
    policy = load_lan_policy(use_cache=False)
    policy["lan_enabled"] = False
    save_lan_policy(policy)
    log_event("OK", "Akses LAN dinonaktifkan pada lapisan aplikasi (localhost 127.0.0.1 tetap aktif).")

    fw = get_firewall_status()
    if fw.get("rule_exists") and fw.get("rule_enabled"):
        fw_ok, fw_msg = run_firewall_action(action="disable", allow_uac_prompt=allow_uac)
        if fw_ok:
            log_event("OK", fw_msg)
        else:
            log_event("WARN", f"Akses LAN sudah diblokir oleh aplikasi, namun penonaktifan rule Firewall memerlukan Admin:\n{fw_msg}")
            return 5
    else:
        log_event("INFO", f"Rule Firewall '{LAN_RULE_NAME}' sudah nonaktif / tidak terpasang.")
    return 0


def rollback_lan_access_flow(allow_uac: bool = True) -> int:
    policy = load_lan_policy(use_cache=False)
    policy.update(
        {
            "lan_enabled": False,
            "approved_remote_addresses": [],
            "approved_network_name": None,
            "approved_interface_alias": None,
            "approved_server_ip": None,
            "approved_subnet": None,
            "approved_profile": None,
            "approved_program": None,
        }
    )
    save_lan_policy(policy)
    log_event("OK", "Kebijakan LAN di-reset ke default aman (localhost only).")

    fw = get_firewall_status()
    if fw.get("rule_exists"):
        fw_ok, fw_msg = run_firewall_action(action="rollback", allow_uac_prompt=allow_uac)
        if fw_ok:
            log_event("OK", fw_msg)
            return 0
        log_event("WARN", fw_msg)
        return 5
    log_event("OK", f"Rule Firewall '{LAN_RULE_NAME}' tidak ada; rollback selesai.")
    return 0


def interactive_menu(auto_started: bool = False) -> int:
    """Unified interactive UX menu (DSS-PIK SYSTEM MANAGER)."""
    while True:
        status = inspect_runtime()
        if not auto_started:
            print_status_banner(status)
        auto_started = False

        print("\nDSS-PIK SYSTEM MANAGER")
        print("  [1] START SYSTEM")
        print("  [2] STOP SYSTEM")
        print("  [3] RESTART SYSTEM")
        print("  [4] SYSTEM STATUS")
        print("  [5] ENABLE LAN ACCESS")
        print("  [6] DISABLE LAN ACCESS")
        print("  [7] LAN DIAGNOSTICS")
        print("  [0] EXIT (Tutup Jendela Ini; Server Tetap Jalan jika Aktif)")

        try:
            choice = input("\nPilih opsi [0-7]: ").strip()
        except (EOFError, KeyboardInterrupt):
            return 0

        if choice == "0":
            return 0
        elif choice == "1":
            start_dss_pik(open_browser=True)
        elif choice == "2":
            stop_dss_pik()
        elif choice == "3":
            restart_dss_pik(open_browser=False)
        elif choice == "4":
            continue
        elif choice == "5":
            enable_lan_access_flow(allow_uac=True)
        elif choice == "6":
            disable_lan_access_flow(allow_uac=True)
        elif choice == "7":
            print_lan_diagnostics()


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="DSS-PIK Unified System Manager")
    parser.add_argument(
        "action",
        nargs="?",
        default="auto",
        choices=[
            "auto",
            "start",
            "stop",
            "restart",
            "status",
            "enable-lan",
            "disable-lan",
            "lan-diagnostics",
            "rollback-lan",
        ],
        help="Action to execute (default: auto UX mode)",
    )
    parser.add_argument("--no-browser", action="store_true", help="Do not launch browser automatically")
    parser.add_argument("--non-interactive", action="store_true", help="Exit immediately after action without menu")
    parser.add_argument("--remote", type=str, default=None, help="Approved client IP(s) or CIDR subnet for enable-lan")
    parser.add_argument("--yes", action="store_true", help="Skip interactive confirmation prompt")
    parser.add_argument("--no-uac", action="store_true", help="Do not trigger Windows UAC prompt; print Admin command instead")
    args = parser.parse_args(argv)

    if args.action == "status":
        st = inspect_runtime()
        print_status_banner(st)
        return 0 if st["running"] else 1

    if args.action == "start":
        return start_dss_pik(open_browser=not args.no_browser)

    if args.action == "stop":
        return stop_dss_pik()

    if args.action == "restart":
        return restart_dss_pik(open_browser=not args.no_browser)

    if args.action == "lan-diagnostics":
        return print_lan_diagnostics()

    if args.action == "enable-lan":
        return enable_lan_access_flow(
            remote_arg=args.remote,
            auto_confirm=args.yes,
            allow_uac=not args.no_uac,
        )

    if args.action == "disable-lan":
        return disable_lan_access_flow(
            auto_confirm=args.yes,
            allow_uac=not args.no_uac,
        )

    if args.action == "rollback-lan":
        return rollback_lan_access_flow(allow_uac=not args.no_uac)

    # Default 'auto' (Double-click UX):
    # - If OFF -> automatically START, then display DSS-PIK SYSTEM MANAGER menu
    # - If ON  -> show STATUS + DSS-PIK SYSTEM MANAGER menu without duplicate instance
    st = inspect_runtime()
    if not st["running"]:
        rc = start_dss_pik(open_browser=not args.no_browser)
        if args.non_interactive:
            return rc
        if rc != 0:
            try:
                input("\nTekan ENTER untuk menutup jendela...")
            except (EOFError, KeyboardInterrupt):
                pass
            return rc
        return interactive_menu(auto_started=True)
    else:
        if args.non_interactive:
            print_status_banner(st)
            return 0
        return interactive_menu(auto_started=False)


if __name__ == "__main__":
    sys.exit(main())
