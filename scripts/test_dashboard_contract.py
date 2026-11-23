#!/usr/bin/env python3
"""
Backward-compatibility runner for test_dashboard_contract.py
"""
import sys
from pathlib import Path

target = (Path(__file__).resolve().parent / "../tests/integration/test_dashboard_contract.py").resolve()
with open(target, "r", encoding="utf-8") as tf:
    code = compile(tf.read(), str(target), "exec")
    exec(code, globals())
