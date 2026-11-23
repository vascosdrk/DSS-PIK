r"""
scripts/backup_dss_pik.py
Automated Backup & Integrity Verification Script for DSS-PIK BMKG Kepulauan Riau.
- Dumps MariaDB `cews_db` using mariadb-dump / mysqldump
- Generates SHA-256 manifest for all 34 Parquet operational & reference files
- Stores backups outside the application root (default: C:\DSS_PIK_BACKUPS)
- Applies configurable retention policy (default: 30 days)
"""

import hashlib
import json
import os
import shutil
import subprocess
from datetime import datetime, timedelta
from pathlib import Path
from dotenv import load_dotenv

ROOT_DIR = Path(__file__).resolve().parent.parent
load_dotenv(ROOT_DIR / ".env")
BACKUP_BASE = Path(os.environ.get("CEWS_BACKUP_DIR", r"C:\DSS_PIK_BACKUPS"))
RETENTION_DAYS = int(os.environ.get("CEWS_BACKUP_RETENTION_DAYS", "30"))

DB_HOST = os.environ.get("CEWS_DB_HOST", "127.0.0.1")
DB_PORT = os.environ.get("CEWS_DB_PORT", "3306")
DB_NAME = os.environ.get("CEWS_DB_NAME", "cews_db")
DB_USER = os.environ.get("CEWS_DB_USER", "root")
DB_PASS = os.environ.get("CEWS_DB_PASSWORD", "")


def find_dump_binary() -> str:
    for candidate in ("mariadb-dump", "mysqldump"):
        found = shutil.which(candidate)
        if found:
            return found
    for base in (Path("C:/Program Files"), Path("C:/Program Files (x86)"), Path("C:/")):
        if base.exists():
            for folder in sorted(base.glob("MariaDB*"), reverse=True):
                for exe in ("mariadb-dump.exe", "mysqldump.exe"):
                    p = folder / "bin" / exe
                    if p.is_file():
                        return str(p)
    for extra in (Path("C:/xampp/mysql/bin/mysqldump.exe"),):
        if extra.is_file():
            return str(extra)
    raise FileNotFoundError("mariadb-dump / mysqldump binary not found.")


def compute_sha256(file_path: Path) -> str:
    h = hashlib.sha256()
    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def run_backup():
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    target_dir = BACKUP_BASE / f"backup_{stamp}"
    target_dir.mkdir(parents=True, exist_ok=True)

    # 1. MariaDB Dump
    dump_bin = find_dump_binary()
    sql_out = target_dir / f"{DB_NAME}_{stamp}.sql"
    cmd = [
        dump_bin,
        f"--host={DB_HOST}",
        f"--port={DB_PORT}",
        f"--user={DB_USER}",
        "--single-transaction",
        "--routines",
        "--triggers",
        DB_NAME,
    ]
    env = os.environ.copy()
    if DB_PASS:
        env["MYSQL_PWD"] = DB_PASS

    with open(sql_out, "wb") as f_out:
        res = subprocess.run(cmd, stdout=f_out, stderr=subprocess.PIPE, env=env)
    if res.returncode != 0:
        raise RuntimeError(f"mariadb-dump failed: {res.stderr.decode(errors='ignore')}")

    # 2. Parquet & Reference SHA-256 Manifest + Copy
    parquet_dir = target_dir / "parquet_snapshot"
    parquet_dir.mkdir(exist_ok=True)
    manifest = []
    data_root = ROOT_DIR / "data"
    for p in sorted(data_root.rglob("*.parquet")):
        rel = p.relative_to(ROOT_DIR)
        sha = compute_sha256(p)
        manifest.append({"path": str(rel).replace("\\", "/"), "size_bytes": p.stat().st_size, "sha256": sha})
        dest = parquet_dir / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(p, dest)

    with open(target_dir / "parquet_sha256_manifest.json", "w", encoding="utf-8") as f:
        json.dump({"created_at": stamp, "total_files": len(manifest), "files": manifest}, f, indent=2)

    # 3. Retention cleanup
    cutoff = datetime.now() - timedelta(days=RETENTION_DAYS)
    for item in BACKUP_BASE.iterdir():
        if item.is_dir() and item.name.startswith("backup_"):
            try:
                dt = datetime.strptime(item.name.replace("backup_", ""), "%Y%m%d_%H%M%S")
                if dt < cutoff:
                    shutil.rmtree(item, ignore_errors=True)
            except Exception:
                pass

    print(f"[OK] Backup selesai di: {target_dir} ({len(manifest)} file Parquet + {sql_out.name})")


if __name__ == "__main__":
    run_backup()

