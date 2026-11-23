"""
Database Connection Module for CEWS Backend API
Climate Early Warning System (CEWS) BMKG Kepulauan Riau
"""

import os
import pymysql
from contextlib import contextmanager
from typing import Generator

DB_HOST = os.environ.get("CEWS_DB_HOST", "127.0.0.1")
DB_PORT = int(os.environ.get("CEWS_DB_PORT", 3306))
DB_USER = os.environ.get("CEWS_DB_USER", "root")
DB_PASSWORD = os.environ.get("CEWS_DB_PASSWORD", "")
DB_NAME = os.environ.get("CEWS_DB_NAME", "cews_db")


def get_raw_connection():
    return pymysql.connect(
        host=DB_HOST,
        port=DB_PORT,
        user=DB_USER,
        password=DB_PASSWORD,
        database=DB_NAME,
        charset="utf8mb4",
        cursorclass=pymysql.cursors.DictCursor,
        autocommit=True
    )


@contextmanager
def get_db() -> Generator[pymysql.Connection, None, None]:
    conn = None
    try:
        conn = get_raw_connection()
        yield conn
    finally:
        if conn and conn.open:
            conn.close()


def check_db_health() -> bool:
    try:
        with get_db() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT 1")
                res = cur.fetchone()
                return res is not None
    except Exception as e:
        print(f"[DB HEALTH ERROR] Failed to connect to MariaDB: {e}")
        return False
