#!/usr/bin/env python3
"""
Backward-compatibility forwarder to scripts/migration/migrate_cews_to_mariadb.py
"""
import sys
from pathlib import Path

target = Path(__file__).resolve().parent / "migration" / "migrate_cews_to_mariadb.py"
with open(target, "r", encoding="utf-8") as tf:
    code = compile(tf.read(), str(target), "exec")
    exec(code, globals())
