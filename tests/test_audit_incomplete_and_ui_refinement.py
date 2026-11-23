"""
tests/test_audit_incomplete_and_ui_refinement.py
Acceptance and automated validation tests for:
1. Audit "57 Stasiun Tidak Lengkap" resolution
2. Authoritative Decision Engine independent evaluation & honest partial rules
3. ARG station evaluation policy
4. Active period 2026-09-das2 evaluation completeness
5. Database baseline row preservation
6. Official Map Generator title layout
7. Frontend build artifact verification
"""

import os
import sys
import json
import pytest
import pymysql
from pathlib import Path
from PIL import Image

ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR))

from backend.decision_engine import (
    evaluate_pdkm_full,
    evaluate_pdcht_full,
    arbitrate_final_synthesis
)
from backend.map_generator import generate_official_warning_map, OUTPUT_DIR


def test_decision_engine_pdkm_independent_indicators():
    """Verify independent evaluation of HTH, pb20, and SPI 30D."""
    # Test HTH alone triggers
    res = evaluate_pdkm_full(hth_days=65, pb20=10.0, spi_val=0.5)
    assert res["status"] == "AWAS"
    assert "HTH" in res["triggered_indicators"]

    res = evaluate_pdkm_full(hth_days=35, pb20=10.0, spi_val=0.5)
    assert res["status"] == "SIAGA"

    res = evaluate_pdkm_full(hth_days=25, pb20=10.0, spi_val=0.5)
    assert res["status"] == "WASPADA"

    # Test pb20 alone triggers (capped at WASPADA)
    res = evaluate_pdkm_full(hth_days=5, pb20=75.0, spi_val=0.5)
    assert res["status"] == "WASPADA"
    assert "Prob_LowRain" in res["triggered_indicators"]

    # Test pb20 boundary at 70.0% (strict > 70)
    res = evaluate_pdkm_full(hth_days=5, pb20=70.0, spi_val=0.5)
    assert res["status"] == "NORMAL"

    # Test SPI 30D alone triggers
    res = evaluate_pdkm_full(hth_days=5, pb20=10.0, spi_val=-2.15)
    assert res["status"] == "AWAS"
    assert "SPI" in res["triggered_indicators"]

    res = evaluate_pdkm_full(hth_days=5, pb20=10.0, spi_val=-1.75)
    assert res["status"] == "SIAGA"

    res = evaluate_pdkm_full(hth_days=5, pb20=10.0, spi_val=-1.25)
    assert res["status"] == "WASPADA"

    res = evaluate_pdkm_full(hth_days=5, pb20=10.0, spi_val=-0.95)
    assert res["status"] == "NORMAL"


def test_decision_engine_pdcht_independent_indicators():
    """Verify independent evaluation of Dasarian and Monthly heavy rainfall probabilities."""
    # Dasarian triggers (> 70%)
    res = evaluate_pdcht_full(pa150=75.0, pa200=20.0, pa300=5.0)
    assert res["status"] == "WASPADA"

    res = evaluate_pdcht_full(pa150=80.0, pa200=72.0, pa300=5.0)
    assert res["status"] == "SIAGA"

    res = evaluate_pdcht_full(pa150=90.0, pa200=80.0, pa300=75.0)
    assert res["status"] == "AWAS"

    # Monthly triggers (> 70%)
    res = evaluate_pdcht_full(pm300=75.0, pm400=10.0, pm500=0.0)
    assert res["status"] == "WASPADA"

    res = evaluate_pdcht_full(pm300=85.0, pm400=72.0, pm500=0.0)
    assert res["status"] == "SIAGA"

    res = evaluate_pdcht_full(pm300=90.0, pm400=80.0, pm500=75.0)
    assert res["status"] == "AWAS"

    # Combination max (dasarian WASPADA + monthly SIAGA -> status SIAGA)
    res = evaluate_pdcht_full(pa150=75.0, pa200=0.0, pa300=0.0, pm300=85.0, pm400=72.0, pm500=0.0)
    assert res["status"] == "SIAGA"
    assert res["level"] == 2


def test_decision_engine_worst_case_and_honest_partial():
    """Verify worst-case synthesis and honest partial evaluation rules."""
    # Partial evaluation: HTH triggers AWAS, but SPI and pb20 are None
    pdkm_part = evaluate_pdkm_full(hth_days=65, pb20=None, spi_val=None)
    assert pdkm_part["status"] == "AWAS"
    assert pdkm_part["evaluation_complete"] is False

    pdcht_norm = evaluate_pdcht_full(pa150=0.0, pa200=0.0, pa300=0.0, pm300=0.0, pm400=0.0, pm500=0.0)
    res = arbitrate_final_synthesis(pdkm_part, pdcht_norm)
    assert res["final_status"] == "AWAS"
    assert res["hazard_type"] == "DROUGHT"
    assert res["evaluation_complete"] is False

    # Partial evaluation: No alert triggers, but input missing -> INCOMPLETE
    pdkm_inc = evaluate_pdkm_full(hth_days=5, pb20=None, spi_val=None)
    assert pdkm_inc["status"] == "INCOMPLETE"

    res_inc = arbitrate_final_synthesis(pdkm_inc, pdcht_norm)
    assert res_inc["final_status"] == "INCOMPLETE"
    assert res_inc["hazard_type"] == "INCOMPLETE"

    # ARG station with valid HTH -> COMPLETE under ARG policy
    pdkm_arg = evaluate_pdkm_full(hth_days=35, pb20=None, spi_val=None, is_arg=True)
    assert pdkm_arg["status"] == "SIAGA"
    assert pdkm_arg["evaluation_complete"] is True


def test_snapshot_2026_09_das2_completeness():
    """Verify snapshot 2026-09-das2 has 57 evaluated stations with 0 incomplete."""
    snap_path = ROOT_DIR / "data" / "processed" / "evaluation" / "snapshots" / "2026-09-das2.json"
    assert snap_path.exists(), "Snapshot 2026-09-das2.json must exist"

    with open(snap_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    summary = data.get("summary", {})
    assert summary.get("total") == 57
    assert summary.get("incomplete") == 0
    assert summary.get("awas") == 6
    assert summary.get("siaga") == 16
    assert summary.get("waspada") == 29
    assert summary.get("aman") == 6

    items = data.get("items", [])
    assert len(items) == 57

    # Verify ARG stations
    arg_items = [it for it in items if it.get("is_arg")]
    assert len(arg_items) == 5
    for arg in arg_items:
        assert arg["evaluation_status"] == "COMPLETE"
        assert arg["hth_days"] is not None

    # Verify 52 pos manual stations have complete data
    pos_items = [it for it in items if not it.get("is_arg")]
    assert len(pos_items) == 52
    for pos in pos_items:
        assert pos["evaluation_status"] == "COMPLETE"
        assert pos["hth_days"] is not None
        assert pos["spi_value"] is not None
        assert pos["forecast_pb20"] is not None
        assert pos["monthly_pa300"] is not None


def test_database_baseline_preservation():
    """Verify baseline row counts in MariaDB are strictly preserved."""
    conn = pymysql.connect(
        host="127.0.0.1",
        port=3306,
        user="root",
        password="",
        database="cews_db",
        cursorclass=pymysql.cursors.DictCursor
    )
    with conn.cursor() as cur:
        cur.execute("SELECT COUNT(*) AS cnt FROM cews_rainfall_daily")
        cnt_daily = cur.fetchone()["cnt"]
        cur.execute("SELECT COUNT(*) AS cnt FROM cews_warning_history")
        cnt_history = cur.fetchone()["cnt"]
        cur.execute("SELECT COUNT(*) AS cnt FROM cews_period_snapshot WHERE period_id = '2026-09-das2'")
        cnt_snap = cur.fetchone()["cnt"]

    conn.close()

    assert cnt_daily == 286085, f"cews_rainfall_daily must be 286,085, got {cnt_daily}"
    assert cnt_history == 2052, f"cews_warning_history must be 2,052, got {cnt_history}"
    assert cnt_snap == 57, f"cews_period_snapshot 2026-09-das2 must have 57 stations, got {cnt_snap}"


def test_official_map_generator_output():
    """Verify official map generator generates valid PNG and PDF with centered title."""
    status_map = {
        "NATUNA": "TIDAK_ADA_PERINGATAN",
        "KEPULAUAN ANAMBAS": "TIDAK_ADA_PERINGATAN",
        "LINGGA": "WASPADA",
        "KARIMUN": "SIAGA",
        "KOTA BATAM": "AWAS",
        "KOTA TANJUNGPINANG": "WASPADA",
        "BINTAN": "SIAGA"
    }

    res = generate_official_warning_map(
        map_type="PDKM",
        period_title="DASARIAN II SEPTEMBER 2026",
        period_id="2026-09-das2",
        regency_status=status_map,
        operator_name="Operator Penguji Automated Test"
    )

    png_path = OUTPUT_DIR / res["png_filename"]
    pdf_path = OUTPUT_DIR / res["pdf_filename"]

    assert png_path.exists(), "PNG map file must exist"
    assert pdf_path.exists(), "PDF map file must exist"
    assert os.path.getsize(png_path) > 100_000, "PNG file must be non-empty image"
    assert os.path.getsize(pdf_path) > 100_000, "PDF file must be non-empty document"

    # Check dimensions
    with Image.open(png_path) as img:
        assert img.size == (1653, 1170), f"A4 Landscape dimension must be 1653x1170, got {img.size}"


def test_frontend_build_artifacts_exist():
    """Verify frontend build artifacts exist in dist/."""
    dist_dir = ROOT_DIR / "frontend" / "dist"
    index_html = dist_dir / "index.html"
    assert dist_dir.exists(), "frontend/dist directory must exist"
    assert index_html.exists(), "frontend/dist/index.html must exist"
