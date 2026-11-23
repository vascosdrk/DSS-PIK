"""
Comprehensive Automated Verification for CEWS Dashboard Refinement Pass
Validates HTH table endpoint, Data Evaluation diagnostic endpoint, and frontend integrity.
"""

import urllib.request
import urllib.parse
import json
import sys

API_BASE = "http://127.0.0.1:8000"
FRONTEND_URL = "http://localhost:5173"

def fetch_json(url):
    req = urllib.request.Request(url, headers={"User-Agent": "CEWS-Refinement-Test"})
    with urllib.request.urlopen(req, timeout=5) as res:
        assert res.status == 200, f"HTTP status was {res.status}"
        return json.loads(res.read().decode("utf-8"))

def test_refinement():
    print("=" * 75)
    print("CEWS DASHBOARD REFINEMENT PASS — COMPREHENSIVE AUTOMATED VERIFICATION")
    print("=" * 75)

    # 1. Health
    health = fetch_json(f"{API_BASE}/health")
    assert health["status"] == "ok"
    assert health["database"] == "connected"
    print(" [PASS] 1. Backend Health: Connected to MariaDB cews_db")

    # 2. Current Warning Baseline Preserved
    cw = fetch_json(f"{API_BASE}/api/v1/current-warning")
    data = cw["data"]
    assert len(data) == 57, f"Expected 57 stations, got {len(data)}"
    counts = {"NORMAL": 0, "WASPADA": 0, "SIAGA": 0, "AWAS": 0}
    for item in data:
        counts[item["warning_level"]] += 1
    assert counts["NORMAL"] == 57 and counts["WASPADA"] == 0
    print(f" [PASS] 2. Baseline Distribution Preserved: 57 Stations (NORMAL={counts['NORMAL']}, WASPADA={counts['WASPADA']}, SIAGA=0, AWAS=0)")

    # 3. HTH Table Endpoint
    hth = fetch_json(f"{API_BASE}/api/v1/hth")
    assert hth["meta"]["total"] == 57
    hth_list = hth["data"]
    assert len(hth_list) == 57
    # Verify default sort DESC
    top = hth_list[0]
    assert top["station_id"] == "21040101B"
    assert top["station_name"] == "ARG Singkep"
    assert top["hth_days_current"] == 24
    assert top["hth_category"] == "WASPADA"
    assert top["warning_level"] == "NORMAL"
    assert top["data_quality_status"] == "INCOMPLETE"
    assert top["last_rain_date"] == "2025-12-07"
    print(f" [PASS] 3. HTH Table Endpoint: 57 rows, sorted DESC, top={top['station_name']} (HTH={top['hth_days_current']} hr, Cat={top['hth_category']}, Level={top['warning_level']}, Rain={top['last_rain_date']})")

    # 4. Filter on HTH Table
    filtered_normal = fetch_json(f"{API_BASE}/api/v1/hth?warning_level=NORMAL")
    assert filtered_normal["meta"]["total"] == 57
    print(" [PASS] 4. HTH Table Filter: warning_level=NORMAL returns all 57 rows")

    # 5. Station Evaluation Endpoint (ARG Singkep)
    eval_res = fetch_json(f"{API_BASE}/api/v1/stations/21040101B/evaluation")
    assert eval_res["station"]["station_id"] == "21040101B"
    assert eval_res["current_state"]["warning_level"] == "NORMAL"
    assert eval_res["current_state"]["hth_days_current"] == 24
    assert eval_res["evaluation"]["status"] == "CONSISTENT"
    assert len(eval_res["evaluation"]["reasons"]) >= 2
    assert eval_res["observation_diagnostics"]["latest_hth_pipeline_value"] == 24
    assert eval_res["observation_diagnostics"]["missing_observation_days"] == 0
    assert len(eval_res["observation_diagnostics"]["recent_rainfall"]) == 31
    print(f" [PASS] 5. Data Evaluation (21040101B): Status={eval_res['evaluation']['status']}, Engine HTH=24 vs Pipeline HTH={eval_res['observation_diagnostics']['latest_hth_pipeline_value']}, Missing={eval_res['observation_diagnostics']['missing_observation_days']}")

    # 6. Nearest Stations Contextual Spatial Comparison
    nearest = eval_res["nearest_stations"]
    assert len(nearest) == 5
    top_near = nearest[0]
    assert top_near["station_id"] == "21040101A" # Stamet Dabo Singkep
    assert top_near["distance_km"] <= 1.5
    assert top_near["hth_days_current"] == 2
    assert top_near["warning_level"] == "NORMAL"
    assert top_near["last_rain_date"] == "2025-12-29"
    print(f" [PASS] 6. Spatial Context: Nearest station {top_near['station_name']} ({top_near['distance_km']} km) -> HTH={top_near['hth_days_current']} hr, Status={top_near['warning_level']}, Last Rain={top_near['last_rain_date']}")

    # 7. Frontend HTTP 200 & Title Check
    with urllib.request.urlopen(FRONTEND_URL, timeout=5) as res:
        assert res.status == 200
        html = res.read().decode("utf-8")
        assert "CEWS BMKG Kepulauan Riau" in html
    print(" [PASS] 7. Frontend Dev Server: HTTP 200 OK, refined bundle served")

    print("=" * 75)
    print("ALL 7 REFINEMENT ACCEPTANCE TESTS PASSED!")
    print("=" * 75)

if __name__ == '__main__':
    test_refinement()
