#!/usr/bin/env python3
"""
Backward-compatibility runner for test_october_2026_acceptance.py
"""
import sys
from pathlib import Path

target = (Path(__file__).resolve().parent / "../tests/regression/test_october_2026_acceptance.py").resolve()
with open(target, "r", encoding="utf-8") as tf:
    code = compile(tf.read(), str(target), "exec")
    exec(code, globals())
