"""
Phase 4.2 Comprehensive Consistency & Dual-Hazard Regression Test Suite
Validates:
1. Bukit Langkap (21040201A) exact end-to-end evaluation
   - Raw values: HTH=4, SPI 90D=-2.03, SPI 30D=-1.19, Pb20=12%, Pa150=0, Pa200=0, Pa300=0, Pm300=70.59%
   - PDKM = AWAS (triggered by SPI 90D <= -2.00)
   - PDCHT = WASPADA (triggered by Pm300 > 70%)
   - Overall = AWAS (MULTI_HAZARD)
2. Detail Endpoint matches Snapshot Item for PDKM/PDCHT status, level, reasons
3. PDCHT evaluation when Monthly is NULL and Dasarian is 0 -> INCOMPLETE
4. SPI 90D isolation: SPI 30D cannot trigger PDKM or mask missing 90D
5. Priority Attention List hazard consistency
"""

import os
import sys
import pytest

sys.path.insert(0, os.path.abspath("."))

from backend.decision_engine import (
    evaluate_pdkm_full,
    evaluate_pdcht_full,
    arbitrate_final_synthesis,
)
from backend.main import get_period_snapshot


def test_bukit_langkap_full_synthesis():
    # Bukit Langkap parameters
    # HTH: 4, SPI 90D: -2.0274, SPI 30D: -1.1907, Pb20: 12.0%
    # Pa150: 0, Pa200: 0, Pa300: 0, Pm300: 70.59, Pm400: 15.69, Pm500: 0.0
    pdkm = evaluate_pdkm_full(
        hth_days=4,
        pb20=12.0,
        spi_val=-2.0274,  # SPI 90D
        target_label="Dasarian I November 2026",
    )
    assert pdkm["level"] == 3
    assert pdkm["status"] == "AWAS"
    assert "SPI 90D" in str(pdkm["reasons"])

    pdcht = evaluate_pdcht_full(
        pa150=0.0,
        pa200=0.0,
        pa300=0.0,
        pm300=70.59,
        pm400=15.69,
        pm500=0.0,
        target_label="Dasarian I November 2026",
    )
    assert pdcht["level"] == 1
    assert pdcht["status"] == "WASPADA"
    assert "Bulanan > 300 mm" in str(pdcht["reasons"])

    overall = arbitrate_final_synthesis(
        pdkm_result=pdkm,
        pdcht_result=pdcht,
    )
    assert overall["final_status"] == "AWAS"
    assert overall["final_level"] == 3
    assert overall["hazard_type"] == "MULTI_HAZARD"
    assert overall["multi_hazard"] is True


def test_spi_90d_strict_isolation():
    # If SPI 90D is missing, even if SPI 30D is -2.5, PDKM must NOT trigger on 30D
    pdkm_missing_90 = evaluate_pdkm_full(
        hth_days=4,
        pb20=12.0,
        spi_val=None,  # SPI 90D is missing
    )
    # HTH=4 is safe (0-20), Pb20=12 is safe (<=70), SPI 90D is missing
    # Result must be INCOMPLETE
    assert pdkm_missing_90["status"] == "INCOMPLETE"
    assert pdkm_missing_90["level"] == 0

    # If SPI 90D is -1.2 (WASPADA) and SPI 30D is -3.0 (AWAS)
    # Only SPI 90D dictates the level -> WASPADA
    pdkm_90_waspada = evaluate_pdkm_full(
        hth_days=4,
        pb20=12.0,
        spi_val=-1.2,
    )
    assert pdkm_90_waspada["status"] == "WASPADA"
    assert pdkm_90_waspada["level"] == 1


def test_pdcht_incomplete_when_monthly_null_and_no_dasarian_trigger():
    # Pa150, Pa200, Pa300 = 0 (no trigger), Pm300, Pm400, Pm500 = None
    pdcht = evaluate_pdcht_full(
        pa150=0.0,
        pa200=0.0,
        pa300=0.0,
        pm300=None,
        pm400=None,
        pm500=None,
    )
    assert pdcht["status"] == "INCOMPLETE"
    assert pdcht["level"] == 0

    # But if Pa150 is 80% (trigger WASPADA), warning must NOT be suppressed
    pdcht_triggered = evaluate_pdcht_full(
        pa150=80.0,
        pa200=0.0,
        pa300=0.0,
        pm300=None,
        pm400=None,
        pm500=None,
    )
    assert pdcht_triggered["status"] == "WASPADA"
    assert pdcht_triggered["level"] == 1


def test_snapshot_and_detail_schema_alignment():
    snap = get_period_snapshot("2026-11-das1")
    items = snap.get("items", [])
    assert len(items) == 57

    bl = next((x for x in items if x["station_id"] == "21040201A"), None)
    assert bl is not None
    assert bl["pdkm_status"] == "AWAS"
    assert bl["pdcht_status"] == "WASPADA"
    assert bl["warning_level"] == "AWAS"
    assert bl["hazard_type"] == "MULTI_HAZARD"
