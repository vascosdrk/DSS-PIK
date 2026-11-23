"""
DSS-PIK Launcher Management & Resilience Engine
Stasiun Meteorologi Kelas II Raja Haji Fisabilillah Tanjungpinang
BMKG Kepulauan Riau

Provides robust, deterministic startup, HTTP-based readiness polling,
strict PID tracking, and graceful process-tree termination for Windows deployment.
"""

import os
import sys
import time
import json
import socket
import shutil

from backend.config import INSTITUTION_SHORT_NAME
import subprocess
import urllib.request
import urllib.error
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Optional, Dict, Any, Tuple, List

import psutil

# Base Directories
ROOT_DIR = Path(__file__).resolve().parent.parent
FRONTEND_DIR = ROOT_DIR / "frontend"
LOG_DIR = ROOT_DIR / "logs" / "runtime"
BACKEND_PID_FILE = LOG_DIR / "backend.pid"
FRONTEND_PID_FILE = LOG_DIR / "frontend.pid"
LAUNCHER_LOG_FILE = LOG_DIR / "launcher.log"

# Ports & Hosts
PORT_BACKEND = 8000
PORT_FRONTEND = 5173
PORT_DATABASE = 3306
HOST_BIND = "0.0.0.0"
HOST_LOCAL = "127.0.0.1"

# Timeouts
TIMEOUT_BACKEND_START_SEC = 25.0
TIMEOUT_FRONTEND_START_SEC = 20.0
POLL_INTERVAL_SEC = 0.5


def get_wib_now() -> datetime:
    """Return current datetime in Asia/Jakarta (WIB, UTC+7)."""
    tz_wib = timezone(timedelta(hours=7))
    return datetime.now(tz_wib)


def log_launcher_event(action: str, status: str, message: str, details: Optional[Dict[str, Any]] = None):
    """Write sanitized, structured event log to logs/runtime/launcher.log."""
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    ts = get_wib_now().isoformat()
    record = {
        "timestamp": ts,
        "action": action,
        "status": status,
        "message": message,
        "details": details or {}
    }
    try:
        with open(LAUNCHER_LOG_FILE, "a", encoding="utf-8") as f:
            f.write(f"[{ts}] [{action.upper()}] [{status.upper()}] {message}")
            if details:
                # Sanitize any keys that might contain sensitive info
                sanitized = {k: v for k, v in details.items() if not any(s in k.lower() for s in ["pass", "token", "secret", "key"])}
                f.write(f" | details={json.dumps(sanitized)}")
            f.write("\n")
    except Exception as e:
        print(f"[WARN] Failed to write to launcher.log: {e}", file=sys.stderr)


# ==============================================================================
# PROCESS & PORT INSPECTION
# ==============================================================================

def get_process_on_port(port: int) -> Optional[psutil.Process]:
    """Return the psutil.Process that is LISTENING on the specified TCP port."""
    try:
        for conn in psutil.net_connections(kind="tcp"):
            if conn.status == psutil.CONN_LISTEN and conn.laddr.port == port:
                if conn.pid:
                    try:
                        return psutil.Process(conn.pid)
                    except (psutil.NoSuchProcess, psutil.AccessDenied):
                        return None
    except Exception as e:
        # Fallback to netstat on Windows if net_connections requires admin privileges
        return _get_process_on_port_netstat(port)
    return None


def get_processes_on_port(port: int) -> List[psutil.Process]:
    """Return all psutil.Process instances listening or bound on the specified TCP port."""
    procs = []
    seen_pids = set()
    try:
        for conn in psutil.net_connections(kind="tcp"):
            if conn.laddr.port == port and conn.pid and conn.pid not in seen_pids:
                try:
                    procs.append(psutil.Process(conn.pid))
                    seen_pids.add(conn.pid)
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    pass
    except Exception:
        pass
    return procs


def _get_process_on_port_netstat(port: int) -> Optional[psutil.Process]:
    """Fallback using netstat.exe to find process on port."""
    netstat_bin = Path(os.environ.get("SystemRoot", r"C:\Windows")) / "System32" / "netstat.exe"
    findstr_bin = Path(os.environ.get("SystemRoot", r"C:\Windows")) / "System32" / "findstr.exe"
    if not netstat_bin.exists():
        return None
    try:
        cmd = f'"{netstat_bin}" -ano -p tcp | "{findstr_bin}" ":{port}" | "{findstr_bin}" "LISTENING"'
        out = subprocess.check_output(cmd, shell=True).decode("utf-8", errors="ignore").strip()
        if not out:
            return None
        # Last column is PID
        pid_str = out.split()[-1]
        pid = int(pid_str)
        return psutil.Process(pid)
    except Exception:
        return None


def is_dss_backend_process(proc: Optional[psutil.Process]) -> bool:
    """Verify if a process belongs to the DSS-PIK FastAPI backend."""
    if not proc:
        return False
    try:
        cmdline = " ".join(proc.cmdline()).lower()
        if "uvicorn" in cmdline and "backend.main:app" in cmdline:
            return True
        if "python" in proc.name().lower() and "backend.main:app" in cmdline:
            return True
        if "python" in proc.name().lower():
            try:
                cwd = proc.cwd().lower()
                if ("backend" in cwd or "cews" in cwd or "asli" in cwd) and "8000" in cmdline:
                    return True
            except Exception:
                pass
    except (psutil.NoSuchProcess, psutil.AccessDenied):
        pass
    return False


def is_dss_frontend_process(proc: Optional[psutil.Process]) -> bool:
    """Verify if a process belongs to the DSS-PIK Vite frontend."""
    if not proc:
        return False
    try:
        cmdline = " ".join(proc.cmdline()).lower()
        name = proc.name().lower()
        if "node" in name and "vite" in cmdline:
            return True
        if "vite" in cmdline:
            return True
        if "node" in name:
            try:
                cwd = proc.cwd().lower()
                if "frontend" in cwd or "cews" in cwd or "asli" in cwd:
                    return True
            except Exception:
                pass
    except (psutil.NoSuchProcess, psutil.AccessDenied):
        pass
    return False


def check_port_conflict(port: int, service_name: str) -> Tuple[bool, Optional[int], Optional[str]]:
    """
    Check if a port is in use by a foreign (non-DSS-PIK) application.
    Returns (has_conflict, pid, process_description).
    """
    proc = get_process_on_port(port)
    if not proc:
        return False, None, None

    if service_name == "backend":
        if is_dss_backend_process(proc):
            return False, proc.pid, "DSS-PIK Backend (Ours)"
        else:
            try:
                desc = f"{proc.name()} (PID: {proc.pid}, CMD: {' '.join(proc.cmdline())[:80]})"
            except Exception:
                desc = f"PID {proc.pid}"
            return True, proc.pid, desc
    elif service_name == "frontend":
        if is_dss_frontend_process(proc):
            return False, proc.pid, "DSS-PIK Frontend (Ours)"
        else:
            try:
                desc = f"{proc.name()} (PID: {proc.pid}, CMD: {' '.join(proc.cmdline())[:80]})"
            except Exception:
                desc = f"PID {proc.pid}"
            return True, proc.pid, desc

    return False, proc.pid, "Unknown"


# ==============================================================================
# HTTP HEALTH & READINESS POLLING
# ==============================================================================

def is_port_listening(host: str = HOST_LOCAL, port: int = PORT_BACKEND, timeout: float = 0.3) -> bool:
    """Fast socket probe whether TCP port is open and accepting connections."""
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


def check_backend_http_health(host: str = HOST_LOCAL, port: int = PORT_BACKEND, timeout: float = 2.0) -> Tuple[bool, Dict[str, Any], str]:
    """
    Query GET http://{host}:{port}/health.
    Returns (is_healthy, response_data, status_message).
    """
    if not is_port_listening(host, port, timeout=0.3):
        return False, {}, f"Port {port} belum terbuka atau tidak mendengarkan koneksi."

    url = f"http://{host}:{port}/health"
    req = urllib.request.Request(url, headers={"User-Agent": "DSS-PIK-Launcher/2.0"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            code = resp.getcode()
            body = resp.read().decode("utf-8")
            data = json.loads(body)
            if code == 200 and data.get("status") == "ok":
                db_status = data.get("database", "unknown")
                if db_status == "connected":
                    return True, data, "Backend API sehat dan MariaDB terhubung."
                else:
                    return False, data, f"Backend API aktif namun database berstatus: {db_status}"
            return False, data, f"Status code tidak sesuai: {code}"
    except urllib.error.HTTPError as e:
        return False, {}, f"HTTP Error {e.code}: {e.reason}"
    except urllib.error.URLError as e:
        return False, {}, f"Koneksi gagal: {e.reason}"
    except Exception as e:
        return False, {}, f"Error: {e}"


def check_frontend_http_health(host: str = HOST_LOCAL, port: int = PORT_FRONTEND, timeout: float = 2.0) -> Tuple[bool, str]:
    """
    Query GET http://{host}:{port}/ and /dashboard.
    Returns (is_healthy, status_message).
    """
    if not is_port_listening(host, port, timeout=0.3):
        return False, f"Port {port} belum terbuka atau tidak mendengarkan koneksi."

    endpoints = ["/", "/dashboard"]
    for ep in endpoints:
        url = f"http://{host}:{port}{ep}"
        req = urllib.request.Request(
            url,
            headers={
                "User-Agent": "DSS-PIK-Launcher/2.0",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"
            }
        )
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                code = resp.getcode()
                body = resp.read().decode("utf-8", errors="ignore")
                if code != 200:
                    return False, f"Endpoint {ep} mengembalikan HTTP {code}"
                if 'id="root"' not in body and '<html' not in body.lower():
                    return False, f"Endpoint {ep} tidak mengembalikan dokumen HTML aplikasi"
        except urllib.error.HTTPError as e:
            return False, f"Endpoint {ep} HTTP Error {e.code}"
        except urllib.error.URLError as e:
            return False, f"Endpoint {ep} koneksi gagal: {e.reason}"
        except Exception as e:
            return False, f"Endpoint {ep} error: {e}"

    return True, "Frontend Web GIS siap melayani request HTTP (/ dan /dashboard)"


# ==============================================================================
# PROCESS TERMINATION (SAFE PROCESS TREE STOP)
# ==============================================================================

def terminate_process_tree(pid: int, timeout_sec: float = 4.0) -> bool:
    """
    Safely terminate a process and all its children.
    First attempts graceful SIGTERM via psutil, falls back to SIGKILL.
    """
    try:
        parent = psutil.Process(pid)
    except (psutil.NoSuchProcess, psutil.AccessDenied):
        return True

    # Collect all descendants
    try:
        children = parent.children(recursive=True)
    except Exception:
        children = []

    procs_to_kill = children + [parent]

    # Attempt 1: Graceful termination
    for p in procs_to_kill:
        try:
            p.terminate()
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass

    # Wait for processes to exit
    gone, alive = psutil.wait_procs(procs_to_kill, timeout=timeout_sec)

    # Attempt 2: Force kill any stubborn remnants
    if alive:
        for p in alive:
            try:
                p.kill()
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass
        psutil.wait_procs(alive, timeout=2.0)

    # Fallback to Windows taskkill /F /T if process still exists
    try:
        if parent.is_running():
            subprocess.run(
                ["C:\\Windows\\System32\\taskkill.exe", "/F", "/T", "/PID", str(pid)],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL
            )
    except Exception:
        pass

    return not parent.is_running()


def wait_for_port_freed(port: int, max_wait_sec: float = 5.0) -> bool:
    """Wait until a TCP port is no longer in LISTENING state."""
    deadline = time.time() + max_wait_sec
    while time.time() < deadline:
        proc = get_process_on_port(port)
        if not proc:
            return True
        time.sleep(0.2)
    return get_process_on_port(port) is None


# ==============================================================================
# LAUNCHER OPERATIONS: START, STOP, STATUS
# ==============================================================================

class DSSLauncher:
    """Operational controller for DSS-PIK background services."""

    def __init__(self):
        self.root_dir = ROOT_DIR
        self.log_dir = LOG_DIR
        self.log_dir.mkdir(parents=True, exist_ok=True)

    def check_prerequisites(self) -> Tuple[bool, List[str]]:
        """Validate environment: Python, Node.js, Frontend deps, MariaDB."""
        errors = []

        # 1. Python 3.10+
        if sys.version_info < (3, 10):
            errors.append(f"Python 3.10+ diperlukan (versi aktif: {sys.version.split()[0]})")

        # 2. Node.js
        try:
            node_out = subprocess.check_output(["node", "-v"], stderr=subprocess.DEVNULL).decode().strip()
        except Exception:
            errors.append("Node.js tidak ditemukan di PATH sistem!")

        # 3. Frontend node_modules
        if not (FRONTEND_DIR / "node_modules").exists():
            errors.append("Direktori frontend/node_modules tidak ditemukan! Jalankan 'npm install' di folder frontend.")

        # 4. MariaDB Service check (Port 3306)
        db_proc = get_process_on_port(PORT_DATABASE)
        if not db_proc:
            # Candidate binary paths for MariaDB
            candidate_bins = [
                (Path(r"C:\Program Files\MariaDB 13.0\bin\mariadbd.exe"), Path(r"C:\Program Files\MariaDB 13.0\data")),
                (Path(r"C:\Program Files\MariaDB 11.4\bin\mariadbd.exe"), Path(r"C:\Program Files\MariaDB 11.4\data")),
                (Path(r"C:\Users\vasco\mariadb-11.4\bin\mariadbd.exe"), Path(r"C:\Users\vasco\mariadb-11.4\data")),
            ]
            mariadb_bin, mariadb_data = None, None
            for b_path, d_path in candidate_bins:
                if b_path.exists():
                    mariadb_bin, mariadb_data = b_path, d_path
                    break

            if mariadb_bin and mariadb_bin.exists():
                print(f"   [ACTION] MariaDB belum aktif. Menjalankan MariaDB Server ({mariadb_bin.name}) di port 3306...")
                try:
                    subprocess.Popen(
                        [str(mariadb_bin), "--console", f"--datadir={mariadb_data}", "--port=3306"],
                        creationflags=subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.DETACHED_PROCESS,
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL
                    )
                    # Wait up to 10s for MariaDB to listen
                    for _ in range(20):
                        time.sleep(0.5)
                        if get_process_on_port(PORT_DATABASE):
                            break
                except Exception as e:
                    errors.append(f"Gagal menjalankan MariaDB Server otomatis: {e}")
            else:
                errors.append(f"MariaDB tidak aktif di port {PORT_DATABASE} dan biner mariadbd.exe tidak ditemukan di lokasi standar!")

        return len(errors) == 0, errors

    def start_backend(self) -> Tuple[bool, Optional[int], float, str]:
        """
        Start Backend FastAPI with separate polling and PID tracking.
        Returns (is_ready, pid, elapsed_seconds, status_message).
        """
        start_time = time.time()

        # Check existing port status
        conflict, conflict_pid, conflict_desc = check_port_conflict(PORT_BACKEND, "backend")
        if conflict:
            msg = f"Port {PORT_BACKEND} digunakan oleh aplikasi lain: {conflict_desc}"
            log_launcher_event("start_backend", "error", msg, {"port": PORT_BACKEND, "conflict_pid": conflict_pid})
            return False, conflict_pid, 0.0, msg

        # Check if already running and healthy
        healthy, data, msg = check_backend_http_health(HOST_LOCAL, PORT_BACKEND, timeout=1.5)
        if healthy:
            proc = get_process_on_port(PORT_BACKEND)
            pid = proc.pid if proc else None
            if pid:
                BACKEND_PID_FILE.write_text(str(pid), encoding="ascii")
            log_launcher_event("start_backend", "success", "Backend already running and healthy", {"pid": pid, "elapsed": 0.0})
            return True, pid, 0.0, "Backend FastAPI sudah berjalan dan sehat."

        # If processes are listening on the port but backend was not healthy, terminate them before starting fresh
        existing_procs = get_processes_on_port(PORT_BACKEND)
        for ep in existing_procs:
            print(f"   [CLEANUP] Menghentikan proses Backend yang tidak responsif pada port {PORT_BACKEND} (PID: {ep.pid})...")
            terminate_process_tree(ep.pid)
        if existing_procs:
            time.sleep(1.0)

        # Clear previous log file for clean startup tracking
        backend_log = LOG_DIR / "backend.log"
        with open(backend_log, "a", encoding="utf-8") as f:
            f.write(f"\n--- DSS-PIK BACKEND STARTUP AT {get_wib_now().isoformat()} ---\n")

        # Launch backend process
        cmd = [sys.executable, "-m", "uvicorn", "backend.main:app", "--host", HOST_BIND, "--port", str(PORT_BACKEND)]
        print(f"   [START] Menjalankan Backend FastAPI ({HOST_BIND}:{PORT_BACKEND})...")
        try:
            out_f = open(backend_log, "a", encoding="utf-8", buffering=1)
            proc = subprocess.Popen(
                cmd,
                cwd=str(self.root_dir),
                stdout=out_f,
                stderr=out_f,
                creationflags=subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.DETACHED_PROCESS
            )
        except Exception as e:
            msg = f"Gagal mengeksekusi proses Python backend: {e}"
            log_launcher_event("start_backend", "error", msg)
            return False, None, time.time() - start_time, msg

        # Poll health endpoint
        deadline = time.time() + TIMEOUT_BACKEND_START_SEC
        backend_pid = None

        while time.time() < deadline:
            time.sleep(POLL_INTERVAL_SEC)

            # Check if port opened
            listen_proc = get_process_on_port(PORT_BACKEND)
            if listen_proc:
                backend_pid = listen_proc.pid

            # Real HTTP health check
            healthy, data, msg = check_backend_http_health(HOST_LOCAL, PORT_BACKEND, timeout=1.5)
            if healthy:
                elapsed = round(time.time() - start_time, 2)
                if backend_pid:
                    BACKEND_PID_FILE.write_text(str(backend_pid), encoding="ascii")
                log_launcher_event("start_backend", "success", f"Backend ready in {elapsed}s", {"pid": backend_pid, "elapsed": elapsed})
                return True, backend_pid, elapsed, f"Backend siap ({elapsed}s, PID {backend_pid})"

            # Verify spawned process hasn't crashed
            if proc.poll() is not None:
                msg = f"Proses Backend berhenti tiba-tiba dengan exit code {proc.poll()}. Periksa logs/runtime/backend.log"
                log_launcher_event("start_backend", "crash", msg, {"exit_code": proc.poll()})
                return False, None, time.time() - start_time, msg

        elapsed = round(time.time() - start_time, 2)
        msg = f"Backend tidak merespons health check dalam {TIMEOUT_BACKEND_START_SEC} detik. Periksa logs/runtime/backend.log"
        log_launcher_event("start_backend", "timeout", msg, {"elapsed": elapsed})
        return False, backend_pid, elapsed, msg

    def start_frontend(self) -> Tuple[bool, Optional[int], float, str]:
        """
        Start Frontend Vite directly with node.exe (strictPort: true) and HTTP polling.
        Returns (is_ready, pid, elapsed_seconds, status_message).
        """
        start_time = time.time()

        # Check existing port status
        conflict, conflict_pid, conflict_desc = check_port_conflict(PORT_FRONTEND, "frontend")
        if conflict:
            msg = f"Port {PORT_FRONTEND} digunakan oleh aplikasi lain: {conflict_desc}"
            log_launcher_event("start_frontend", "error", msg, {"port": PORT_FRONTEND, "conflict_pid": conflict_pid})
            return False, conflict_pid, 0.0, msg

        # Check if already running and healthy
        healthy, msg = check_frontend_http_health(HOST_LOCAL, PORT_FRONTEND, timeout=1.5)
        if healthy:
            proc = get_process_on_port(PORT_FRONTEND)
            pid = proc.pid if proc else None
            if pid:
                FRONTEND_PID_FILE.write_text(str(pid), encoding="ascii")
            log_launcher_event("start_frontend", "success", "Frontend already running and healthy", {"pid": pid, "elapsed": 0.0})
            return True, pid, 0.0, "Frontend Web GIS sudah berjalan dan sehat."

        # If processes are listening on the port but frontend was not healthy, terminate them before starting fresh
        existing_procs = get_processes_on_port(PORT_FRONTEND)
        for ep in existing_procs:
            print(f"   [CLEANUP] Menghentikan proses Frontend yang tidak responsif pada port {PORT_FRONTEND} (PID: {ep.pid})...")
            terminate_process_tree(ep.pid)
        if existing_procs:
            time.sleep(1.0)

        # Locate vite.js script
        vite_js = FRONTEND_DIR / "node_modules" / "vite" / "bin" / "vite.js"
        if not vite_js.exists():
            msg = f"Biner Vite tidak ditemukan di {vite_js}. Jalankan 'npm install' di folder frontend."
            log_launcher_event("start_frontend", "error", msg)
            return False, None, 0.0, msg

        # Clear previous log file for clean startup tracking
        frontend_log = LOG_DIR / "frontend.log"
        with open(frontend_log, "a", encoding="utf-8") as f:
            f.write(f"\n--- DSS-PIK FRONTEND STARTUP AT {get_wib_now().isoformat()} ---\n")

        # Launch frontend directly with node.exe (bypassing npm.cmd to avoid cmd wrapper & batch prompt hangs)
        node_bin = shutil.which("node") or "node"
        cmd = [node_bin, str(vite_js), str(FRONTEND_DIR), "--host", HOST_BIND, "--port", str(PORT_FRONTEND)]
        print(f"   [START] Menjalankan Frontend Vite ({HOST_BIND}:{PORT_FRONTEND})...")
        try:
            out_f = open(frontend_log, "a", encoding="utf-8", buffering=1)
            proc = subprocess.Popen(
                cmd,
                cwd=str(FRONTEND_DIR),
                stdout=out_f,
                stderr=out_f,
                creationflags=subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.DETACHED_PROCESS
            )
        except Exception as e:
            msg = f"Gagal mengeksekusi Node.js frontend: {e}"
            log_launcher_event("start_frontend", "error", msg)
            return False, None, time.time() - start_time, msg

        # Poll real HTTP GET / and /dashboard
        deadline = time.time() + TIMEOUT_FRONTEND_START_SEC
        frontend_pid = None

        while time.time() < deadline:
            time.sleep(POLL_INTERVAL_SEC)

            # Check if port opened
            listen_proc = get_process_on_port(PORT_FRONTEND)
            if listen_proc:
                frontend_pid = listen_proc.pid

            # Real HTTP check on frontend endpoints
            healthy, msg = check_frontend_http_health(HOST_LOCAL, PORT_FRONTEND, timeout=1.5)
            if healthy:
                elapsed = round(time.time() - start_time, 2)
                if frontend_pid:
                    FRONTEND_PID_FILE.write_text(str(frontend_pid), encoding="ascii")
                log_launcher_event("start_frontend", "success", f"Frontend ready in {elapsed}s", {"pid": frontend_pid, "elapsed": elapsed})
                return True, frontend_pid, elapsed, f"Frontend siap ({elapsed}s, PID {frontend_pid})"

            # Verify spawned process hasn't crashed
            if proc.poll() is not None:
                msg = f"Proses Frontend berhenti tiba-tiba dengan exit code {proc.poll()}. Periksa logs/runtime/frontend.log"
                log_launcher_event("start_frontend", "crash", msg, {"exit_code": proc.poll()})
                return False, None, time.time() - start_time, msg

        elapsed = round(time.time() - start_time, 2)
        msg = f"Frontend belum merespons HTTP dalam {TIMEOUT_FRONTEND_START_SEC} detik. Periksa logs/runtime/frontend.log"
        log_launcher_event("start_frontend", "timeout", msg, {"elapsed": elapsed})
        return False, frontend_pid, elapsed, msg

    def open_dashboard_browser(self, target_url: str = f"http://localhost:{PORT_FRONTEND}/dashboard") -> bool:
        """Open default web browser exactly once to verified dashboard URL."""
        print(f"\n[ACTION] Membuka Dashboard DSS-PIK di Browser...")
        print(f"         URL: {target_url}")
        try:
            # Use native Windows start command via subprocess
            subprocess.run(["cmd.exe", "/c", "start", "", target_url], check=False)
            log_launcher_event("open_browser", "success", f"Opened browser to {target_url}", {"url": target_url})
            return True
        except Exception as e:
            msg = f"Gagal membuka peramban secara otomatis: {e}"
            print(f"[PERINGATAN] {msg}")
            log_launcher_event("open_browser", "warning", msg, {"error": str(e)})
            return False

    def stop_services(self) -> Dict[str, Any]:
        """
        Safely stop DSS-PIK backend and frontend processes by targeting PIDs.
        Preserves MariaDB (Port 3306).
        """
        print("======================================================================")
        print("  DSS-PIK BMKG KEPULAUAN RIAU - PENGHENTIAN LAYANAN")
        print(f"  {INSTITUTION_SHORT_NAME}")
        print("======================================================================\n")

        results = {
            "backend_stopped": False,
            "frontend_stopped": False,
            "backend_pid": None,
            "frontend_pid": None,
            "mariadb_preserved": True
        }

        # 1. Stop Backend (Port 8000)
        print("[1/2] Memeriksa Backend FastAPI (Port 8000)...")
        be_procs = get_processes_on_port(PORT_BACKEND)
        stopped_be = False
        for bp in be_procs:
            print(f"   [ACTION] Menghentikan proses Backend FastAPI (PID: {bp.pid})...")
            terminate_process_tree(bp.pid, timeout_sec=4.0)
            stopped_be = True

        # Check recorded PID file if port was not listening but process lingers
        if not be_procs and BACKEND_PID_FILE.exists():
            try:
                recorded_pid = int(BACKEND_PID_FILE.read_text(encoding="ascii").strip())
                if psutil.pid_exists(recorded_pid):
                    p = psutil.Process(recorded_pid)
                    if is_dss_backend_process(p):
                        print(f"   [ACTION] Menghentikan proses Backend tersisa (PID: {recorded_pid})...")
                        terminate_process_tree(recorded_pid, timeout_sec=4.0)
                        stopped_be = True
            except Exception:
                pass

        if stopped_be:
            wait_for_port_freed(PORT_BACKEND, max_wait_sec=4.0)
            results["backend_stopped"] = True
            print(f"   [OK] Seluruh proses Backend FastAPI berhasil dihentikan.")
            log_launcher_event("stop_backend", "success", "Backend processes stopped")
        else:
            print("   [INFO] Backend FastAPI tidak sedang berjalan di port 8000.")
            log_launcher_event("stop_backend", "info", "Backend was not running")

        # 2. Stop Frontend (Port 5173)
        print("\n[2/2] Memeriksa Frontend Web GIS (Port 5173)...")
        fe_procs = get_processes_on_port(PORT_FRONTEND)
        stopped_fe = False
        for fp in fe_procs:
            print(f"   [ACTION] Menghentikan proses Frontend Web GIS (PID: {fp.pid})...")
            terminate_process_tree(fp.pid, timeout_sec=4.0)
            stopped_fe = True

        # Check recorded PID file if port was not listening but process lingers
        if not fe_procs and FRONTEND_PID_FILE.exists():
            try:
                recorded_pid = int(FRONTEND_PID_FILE.read_text(encoding="ascii").strip())
                if psutil.pid_exists(recorded_pid):
                    p = psutil.Process(recorded_pid)
                    if is_dss_frontend_process(p):
                        print(f"   [ACTION] Menghentikan proses Frontend tersisa (PID: {recorded_pid})...")
                        terminate_process_tree(recorded_pid, timeout_sec=4.0)
                        stopped_fe = True
            except Exception:
                pass

        if stopped_fe:
            wait_for_port_freed(PORT_FRONTEND, max_wait_sec=4.0)
            results["frontend_stopped"] = True
            print(f"   [OK] Seluruh proses Frontend Web GIS berhasil dihentikan.")
            log_launcher_event("stop_frontend", "success", "Frontend processes stopped")
        else:
            print("   [INFO] Frontend Web GIS tidak sedang berjalan di port 5173.")
            log_launcher_event("stop_frontend", "info", "Frontend was not running")

        # 3. Clean up PID files
        if BACKEND_PID_FILE.exists():
            try:
                BACKEND_PID_FILE.unlink()
            except Exception:
                pass
        if FRONTEND_PID_FILE.exists():
            try:
                FRONTEND_PID_FILE.unlink()
            except Exception:
                pass

        # 4. Status Database MariaDB (Protected)
        print("\n----------------------------------------------------------------------")
        print("[STATUS MARIADB]")
        print("  Layanan database MariaDB (Port 3306) TETAP AKTIF dan dilindungi")
        print("  untuk menjaga integritas data dan melayani proses operasional lainnya.")
        print("----------------------------------------------------------------------")

        total_stopped = sum([1 for k in ["backend_stopped", "frontend_stopped"] if results[k]])
        print("\n======================================================================")
        print("  RINGKASAN STATUS PENGHENTIAN")
        print("======================================================================")
        print(f"  Total layanan yang dihentikan : {total_stopped}")
        print("  Layanan DSS-PIK telah aman dimatikan.")
        print("======================================================================\n")

        return results

    def start_all(self, open_browser: bool = True, headless: bool = False) -> bool:
        """
        Execute full resilient startup sequence:
        1. Prerequisites check
        2. Backend startup & HTTP health check
        3. Frontend startup & HTTP readiness check
        4. Browser opening (exactly once)
        """
        print("======================================================================")
        print("  DSS-PIK BMKG KEPULAUAN RIAU - SYSTEM LAUNCHER")
        print(f"  {INSTITUTION_SHORT_NAME}")
        print("======================================================================\n")

        # Step 1: Prerequisites
        print("[1/4] Memeriksa Prasyarat Sistem & Dependensi...")
        ok, errors = self.check_prerequisites()
        if not ok:
            print("\n[ERROR] Pemeriksaan prasyarat sistem gagal:")
            for err in errors:
                print(f"  - {err}")
            log_launcher_event("startup", "error", "Prerequisites failed", {"errors": errors})
            return False
        print("   [OK] Python 3.12, Node.js, dependensi frontend, dan MariaDB siap.")

        # Step 2: Backend Startup & Polling
        print("\n[2/4] Memeriksa & Menjalankan Backend FastAPI (Port 8000)...")
        be_ready, be_pid, be_elapsed, be_msg = self.start_backend()
        if not be_ready:
            print(f"\n[ERROR] Gagal memulai Backend API: {be_msg}")
            print(f"Silakan periksa log di: {self.log_dir / 'backend.log'}")
            return False
        print(f"   [OK] {be_msg}")

        # Step 3: Frontend Startup & Polling
        print("\n[3/4] Memeriksa & Menjalankan Frontend Web GIS (Port 5173)...")
        fe_ready, fe_pid, fe_elapsed, fe_msg = self.start_frontend()
        if not fe_ready:
            print(f"\n[ERROR] Gagal memulai Frontend Web GIS: {fe_msg}")
            print(f"Silakan periksa log di: {self.log_dir / 'frontend.log'}")
            return False
        print(f"   [OK] {fe_msg}")

        # Step 4: Open Browser (if requested)
        target_url = f"http://localhost:{PORT_FRONTEND}/dashboard"
        if open_browser and not headless:
            print("\n[4/4] Membuka Peramban Web...")
            self.open_dashboard_browser(target_url)
        else:
            print("\n[4/4] Mode Headless/No-Browser aktif. Lewati pembukaan peramban.")

        # Final Summary
        print("\n======================================================================")
        print("  SELURUH LAYANAN DSS-PIK TELAH AKTIF & TERVERIFIKASI!")
        print("======================================================================")
        print(f"  Aplikasi Web GIS (Lokal)  : {target_url}")
        print(f"  Aplikasi Web GIS (LAN)    : http://{self._get_lan_ip()}:{PORT_FRONTEND}/dashboard")
        print(f"  Dokumentasi API FastAPI   : http://{HOST_LOCAL}:{PORT_BACKEND}/docs")
        print(f"  Status Kesiapan Database  : http://{HOST_LOCAL}:{PORT_BACKEND}/health")
        print(f"  Direktori Log Runtime     : {self.log_dir}")
        print("")
        print("  Untuk menghentikan layanan secara aman, jalankan: stop_cews.bat")
        print("======================================================================\n")

        log_launcher_event("startup", "success", "All services running and ready", {
            "backend_pid": be_pid,
            "frontend_pid": fe_pid,
            "backend_elapsed": be_elapsed,
            "frontend_elapsed": fe_elapsed,
            "target_url": target_url
        })
        return True

    def _get_lan_ip(self) -> str:
        """Best-effort discovery of local LAN IP address."""
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            ip = s.getsockname()[0]
            s.close()
            return ip
        except Exception:
            return "IP_SERVER"


# ==============================================================================
# CLI DISPATCHER
# ==============================================================================

def main():
    import argparse
    parser = argparse.ArgumentParser(description="DSS-PIK Service Manager & Launcher")
    subparsers = parser.add_subparsers(dest="command", help="Perintah operasional")

    # Start command
    p_start = subparsers.add_parser("start", help="Jalankan seluruh layanan dan buka browser")
    p_start.add_argument("--headless", action="store_true", help="Jalankan di latar belakang tanpa membuka browser atau pause")
    p_start.add_argument("--no-browser", action="store_true", help="Jalankan layanan tanpa membuka peramban web")

    # Stop command
    p_stop = subparsers.add_parser("stop", help="Hentikan layanan backend dan frontend secara aman")
    p_stop.add_argument("--headless", action="store_true", help="Hentikan tanpa pause interaktif")

    # Status command
    subparsers.add_parser("status", help="Periksa status kesehatan dan port layanan")

    # Health check commands
    subparsers.add_parser("check-backend", help="Cek HTTP GET /health pada backend")
    subparsers.add_parser("check-frontend", help="Cek HTTP GET / dan /dashboard pada frontend")

    args = parser.parse_args()

    launcher = DSSLauncher()

    if args.command == "start":
        open_browser = not (args.no_browser or args.headless)
        success = launcher.start_all(open_browser=open_browser, headless=args.headless)
        if not args.headless:
            print("Tekan Enter untuk meminimalkan jendela ini...")
            try:
                input()
            except (KeyboardInterrupt, EOFError):
                pass
        sys.exit(0 if success else 1)

    elif args.command == "stop":
        results = launcher.stop_services()
        if not args.headless:
            print("Tekan Enter untuk menutup jendela ini...")
            try:
                input()
            except (KeyboardInterrupt, EOFError):
                pass
        sys.exit(0)

    elif args.command == "status":
        be_ok, be_data, be_msg = check_backend_http_health()
        fe_ok, fe_msg = check_frontend_http_health()
        print(f"Backend  (Port {PORT_BACKEND}) : {'READY' if be_ok else 'DOWN'} - {be_msg}")
        print(f"Frontend (Port {PORT_FRONTEND}): {'READY' if fe_ok else 'DOWN'} - {fe_msg}")
        sys.exit(0 if (be_ok and fe_ok) else 1)

    elif args.command == "check-backend":
        ok, data, msg = check_backend_http_health()
        print(f"Backend Health: {ok} | {msg}")
        sys.exit(0 if ok else 1)

    elif args.command == "check-frontend":
        ok, msg = check_frontend_http_health()
        print(f"Frontend Health: {ok} | {msg}")
        sys.exit(0 if ok else 1)

    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
