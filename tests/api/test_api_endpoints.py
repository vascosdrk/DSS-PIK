#!/usr/bin/env python3
"""
Test Suite for CEWS FastAPI Backend Endpoints
Climate Early Warning System (CEWS) BMKG Kepulauan Riau
Fast-Track Tahap 4 Acceptance Validation
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

import json
import urllib.request
import urllib.error
from backend.auth import create_session_token

BASE_URL = "http://127.0.0.1:8000"
TOKEN = create_session_token("klimatkepri")


def http_get(path):
    url = f"{BASE_URL}{path}"
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": "CEWS-TestRunner/1.0",
            "Authorization": f"Bearer {TOKEN}"
        }
    )
    try:
        with urllib.request.urlopen(req, timeout=5) as resp:
            status = resp.status
            body = resp.read().decode("utf-8")
            return status, json.loads(body)
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8")
        try:
            parsed = json.loads(body)
        except Exception:
            parsed = body
        return e.code, parsed


def run_tests():
    print("==================================================")
    print("CEWS BACKEND API ACCEPTANCE TEST SUITE")
    print(f"Target Base URL: {BASE_URL}")
    print("==================================================")

    # 1. TEST /health
    print("\n[TEST 1] GET /health")
    code, data = http_get("/health")
    print(f"  HTTP Status: {code}")
    print(f"  Response: {data}")
    assert code == 200, f"Expected 200, got {code}"
    assert data.get("status") == "ok", f"Expected status 'ok', got {data.get('status')}"
    assert data.get("database") == "connected", f"Expected database 'connected', got {data.get('database')}"
    print("  -> PASS: Health check endpoint working and database connected.")

    # 2. TEST /api/v1/current-warning
    print("\n[TEST 2] GET /api/v1/current-warning (Contract A Map View)")
    code, data = http_get("/api/v1/current-warning?period_id=2026-09-das2")
    print(f"  HTTP Status: {code}")
    meta = data.get("meta", {})
    records = data.get("data", [])
    print(f"  Meta: {meta}")
    print(f"  Total records returned: {len(records)} (meta.total={meta.get('total')})")
    assert code == 200, f"Expected 200, got {code}"
    assert len(records) == 57, f"Expected 57 records, got {len(records)}"
    assert meta.get("total") == 57, f"Expected meta.total 57, got {meta.get('total')}"

    # Distribution Check
    levels = {}
    for r in records:
        lvl = r["warning_level"]
        levels[lvl] = levels.get(lvl, 0) + 1
    print(f"  Warning Level Distribution: {levels}")
    assert levels.get("NORMAL", 0) == 6, f"Expected 6 NORMAL, got {levels.get('NORMAL')}"
    assert levels.get("WASPADA", 0) == 29, f"Expected 29 WASPADA, got {levels.get('WASPADA')}"
    assert levels.get("SIAGA", 0) == 16, f"Expected 16 SIAGA, got {levels.get('SIAGA')}"
    assert levels.get("AWAS", 0) == 6, f"Expected 6 AWAS, got {levels.get('AWAS')}"
    print("  -> PASS: Map endpoint returns 57 stations with verified distribution (6 NORMAL, 29 WASPADA, 16 SIAGA, 6 AWAS).")

    # Test Filter
    print("\n[TEST 2B] GET /api/v1/current-warning?warning_level=NORMAL&period_id=2026-09-das2")
    code, data_f = http_get("/api/v1/current-warning?warning_level=NORMAL&period_id=2026-09-das2")
    assert code == 200
    w_recs = data_f.get("data", [])
    print(f"  Filtered count: {len(w_recs)}")
    assert len(w_recs) == 6, f"Expected 6 records, got {len(w_recs)}"
    print("  -> PASS: Optional query filter working correctly.")

    # 3. TEST /api/v1/stations/{station_id}/detail for NORMAL station
    print("\n[TEST 3] GET /api/v1/stations/21010403A/detail (Sample NORMAL Station - Galang Batang)")
    code, norm_data = http_get("/api/v1/stations/21010403A/detail?period_id=2026-09-das2")
    print(f"  HTTP Status: {code}")
    print(f"  Station: {norm_data.get('station_name')} ({norm_data.get('station_id')})")
    print(f"  Warning Level: {norm_data.get('warning_level')} | Hazard: {norm_data.get('hazard_type')}")
    print(f"  HTH: {norm_data.get('hth_days_current')} | SPI: {norm_data.get('spi_value')}")
    assert code == 200
    assert norm_data["station_id"] == "21010403A"
    assert norm_data["warning_level"] == "NORMAL"
    assert norm_data["hazard_type"] == "NORMAL"
    assert norm_data["hth_days_current"] == 9
    assert round(norm_data["spi_value"], 2) == -0.96
    print("  -> PASS: NORMAL station detail matches MariaDB exactly.")

    # 4. TEST /api/v1/stations/{station_id}/detail for ARG Singkep (NORMAL ARG Station)
    print("\n[TEST 4] GET /api/v1/stations/21040101B/detail (ARG Singkep Station)")
    code, wasp_data = http_get("/api/v1/stations/21040101B/detail?period_id=2026-09-das2")
    print(f"  HTTP Status: {code}")
    print(f"  Station: {wasp_data.get('station_name')} ({wasp_data.get('station_id')}) in {wasp_data.get('kabupaten')}")
    print(f"  Warning Level: {wasp_data.get('warning_level')} | Hazard: {wasp_data.get('hazard_type')}")
    print(f"  Data Quality Status: {wasp_data.get('data_quality_status')}")
    print(f"  HTH: {wasp_data.get('hth_days_current')} | SPI: {wasp_data.get('spi_value')}")
    print(f"  Trigger Reason: {wasp_data.get('trigger_reason')[:100]}...")
    assert code == 200
    assert wasp_data["station_id"] == "21040101B"
    assert wasp_data["warning_level"] == "NORMAL"
    assert wasp_data["hth_days_current"] == 9
    assert wasp_data["spi_value"] is None, f"Expected null SPI, got {wasp_data['spi_value']}"
    assert isinstance(wasp_data["forecast_evidence"], list)
    print("  -> PASS: ARG Singkep station detail matches MariaDB exactly (NORMAL, HTH=9, pb20=null).")

    # 5. TEST /api/v1/stations/INVALID/detail (404 Handling)
    print("\n[TEST 5] GET /api/v1/stations/INVALID_ID/detail (404 Error Handling)")
    code, err_data = http_get("/api/v1/stations/INVALID_ID/detail")
    print(f"  HTTP Status: {code}")
    print(f"  Response: {err_data}")
    assert code == 404, f"Expected 404, got {code}"
    assert "not found" in str(err_data).lower()
    print("  -> PASS: Invalid station returns proper HTTP 404 (no 500 error).")

    # 6. TEST /api/v1/stations/{station_id}/history (Contract D Timeline)
    print("\n[TEST 6] GET /api/v1/stations/21720201A/history (Historical Timeline)")
    code, hist_data = http_get("/api/v1/stations/21720201A/history")
    print(f"  HTTP Status: {code}")
    recs = hist_data.get("data", [])
    print(f"  Station: {hist_data.get('station_name')} | Total historical dasarians: {len(recs)}")
    if recs:
        print(f"  Latest Dasarian: {recs[0]['period_start']} to {recs[0]['period_end']} -> Level: {recs[0]['warning_level']}")
        print(f"  Oldest Dasarian: {recs[-1]['period_start']} to {recs[-1]['period_end']} -> Level: {recs[-1]['warning_level']}")
    assert code == 200
    assert len(recs) == 36, f"Expected 36 dasarians for 2025, got {len(recs)}"
    assert recs[0]["period_start"] > recs[-1]["period_start"], "History should be sorted period_start DESC"
    print("  -> PASS: Historical timeline endpoint returns all 36 dasarians sorted period_start DESC.")

    # 7. Swagger Documentation check
    print("\n[TEST 7] GET /docs (Swagger Documentation)")
    req = urllib.request.Request(f"{BASE_URL}/docs")
    with urllib.request.urlopen(req, timeout=5) as resp:
        print(f"  HTTP Status: {resp.status}")
        assert resp.status == 200
    print("  -> PASS: Swagger interactive API documentation active at /docs.")

    print("\n==================================================")
    print("ALL FAST-TRACK TAHAP 4 ACCEPTANCE TESTS: 100% PASS")
    print("==================================================")


if __name__ == "__main__":
    run_tests()
