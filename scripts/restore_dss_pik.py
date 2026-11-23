r"""
scripts/restore_dss_pik.py
Safe Database Restore & Parquet Checksum Verification Script for DSS-PIK Migration.
- Checks MariaDB connection
- Protects existing populated `cews_db` from accidental overwrite (requires explicit confirmation or --force)
- Restores SQL dump from latest or specified backup directory
- Verifies all 34 Parquet files against SHA-256 manifest
"""

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from dotenv import load_dotenv
load_dotenv(ROOT_DIR / ".env")

DB_HOST = os.environ.get("CEWS_DB_HOST", "127.0.0.1")
DB_PORT = int(os.environ.get("CEWS_DB_PORT", "3306"))
DB_NAME = os.environ.get("CEWS_DB_NAME", "cews_db")
DB_USER = os.environ.get("CEWS_DB_USER", "root")
DB_PASS = os.environ.get("CEWS_DB_PASSWORD", "")
BACKUP_BASE = Path(os.environ.get("CEWS_BACKUP_DIR", r"C:\DSS_PIK_BACKUPS"))


def find_mariadb_client() -> str:
    for candidate in ("mariadb", "mysql"):
        found = shutil.which(candidate)
        if found:
            return found
    for base in (Path("C:/Program Files"), Path("C:/Program Files (x86)"), Path("C:/")):
        if base.exists():
            for folder in sorted(base.glob("MariaDB*"), reverse=True):
                for exe in ("mariadb.exe", "mysql.exe"):
                    p = folder / "bin" / exe
                    if p.is_file():
                        return str(p)
    for extra in (Path("C:/xampp/mysql/bin/mysql.exe"),):
        if extra.is_file():
            return str(extra)
    raise FileNotFoundError("mariadb / mysql client binary not found.")


def compute_sha256(file_path: Path) -> str:
    h = hashlib.sha256()
    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def verify_parquets(manifest_path: Path) -> bool:
    if not manifest_path.exists():
        print(f"[WARNING] Manifest SHA-256 tidak ditemukan di {manifest_path}")
        return False
    data = json.loads(manifest_path.read_text(encoding="utf-8"))
    files = data.get("files", [])
    ok_count = 0
    for item in files:
        rel_path = ROOT_DIR / item["path"]
        if not rel_path.exists():
            print(f"[ERROR] File Parquet hilang: {item['path']}")
            return False
        actual_sha = compute_sha256(rel_path)
        if actual_sha != item["sha256"]:
            print(f"[ERROR] Checksum mismatch pada {item['path']}")
            return False
        ok_count += 1
    print(f"[OK] Verifikasi SHA-256 berhasil: {ok_count}/{len(files)} file Parquet identik dan utuh.")
    return True


def check_existing_db_data() -> int:
    import pymysql
    conn = pymysql.connect(host=DB_HOST, port=DB_PORT, user=DB_USER, password=DB_PASS)
    try:
        with conn.cursor() as cur:
            cur.execute(f"CREATE DATABASE IF NOT EXISTS `{DB_NAME}` CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci;")
            cur.execute(f"USE `{DB_NAME}`;")
            cur.execute("SHOW TABLES LIKE 'stations';")
            if not cur.fetchone():
                return 0
            cur.execute("SELECT COUNT(*) FROM stations;")
            row = cur.fetchone()
            return int(row[0]) if row else 0
    finally:
        conn.close()


def main():
    parser = argparse.ArgumentParser(description="DSS-PIK Safe Database Restore & Parquet Validator")
    parser.add_argument("--backup-dir", type=str, default=None, help="Path ke folder backup spesifik")
    parser.add_argument("--verify-only", action="store_true", help="Hanya verifikasi database & Parquet tanpa restore")
    parser.add_argument("--force", action="store_true", help="Izinkan restore meskipun database sudah berisi data")
    args = parser.parse_args()

    # Locate backup directory
    target_dir = Path(args.backup_dir) if args.backup_dir else None
    if not target_dir and BACKUP_BASE.exists():
        backups = sorted([d for d in BACKUP_BASE.iterdir() if d.is_dir() and d.name.startswith("backup_")])
        if backups:
            target_dir = backups[-1]

    if target_dir and (target_dir / "parquet_sha256_manifest.json").exists():
        verify_parquets(target_dir / "parquet_sha256_manifest.json")
    else:
        parquets = list((ROOT_DIR / "data").rglob("*.parquet"))
        print(f"[INFO] Ditemukan {len(parquets)} file Parquet di folder data/.")

    existing_stations = check_existing_db_data()
    print(f"[INFO] Database `{DB_NAME}` saat ini memiliki {existing_stations} stasiun terdaftar.")

    if args.verify_only:
        return

    if not target_dir or not target_dir.exists():
        print("[ERROR] Direktori backup tidak ditemukan untuk proses restore.")
        sys.exit(1)

    sql_files = list(target_dir.glob("*.sql"))
    if not sql_files:
        print(f"[ERROR] Tidak ada file .sql di dalam {target_dir}")
        sys.exit(1)

    if existing_stations > 0 and not args.force:
        ans = input(f"[KONFIRMASI] Database `{DB_NAME}` sudah memiliki data ({existing_stations} stasiun). Timpa dengan backup? (ketik 'YA' untuk melanjutkan): ")
        if ans.strip().upper() != "YA":
            print("[BATAL] Restore database dibatalkan untuk melindungi data yang ada.")
            return

    client_bin = find_mariadb_client()
    sql_file = sql_files[0]
    print(f"[RESTORE] Memulihkan `{DB_NAME}` dari {sql_file.name}...")
    env = os.environ.copy()
    if DB_PASS:
        env["MYSQL_PWD"] = DB_PASS
    with open(sql_file, "rb") as f_in:
        res = subprocess.run(
            [client_bin, f"--host={DB_HOST}", f"--port={DB_PORT}", f"--user={DB_USER}", DB_NAME],
            stdin=f_in,
            stderr=subprocess.PIPE,
            env=env,
        )
    if res.returncode != 0:
        raise RuntimeError(f"Restore gagal: {res.stderr.decode(errors='ignore')}")
    print(f"[OK] Restore database `{DB_NAME}` selesai. Total stasiun: {check_existing_db_data()}")


if __name__ == "__main__":
    main()

