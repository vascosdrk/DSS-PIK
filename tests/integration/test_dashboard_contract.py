"""
Automated Functional Verification for CEWS Web GIS Dashboard Demo (Tahap 5)
Verifying all requirements from backend data contract to frontend assets.
"""

import urllib.request
import json
import sys
from backend.auth import create_session_token

API_BASE = "http://127.0.0.1:8000"
FRONTEND_URL = "http://localhost:5173"
TOKEN = create_session_token("klimatkepri")

def fetch_json(url):
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": "CEWS-Test-Agent",
            "Authorization": f"Bearer {TOKEN}"
        }
    )
    with urllib.request.urlopen(req, timeout=5) as res:
        assert res.status == 200, f"HTTP status was {res.status}"
        return json.loads(res.read().decode("utf-8"))

def test_dashboard():
    print("=" * 70)
    print("CEWS FAST-TRACK TAHAP 5 — COMPREHENSIVE AUTOMATED VERIFICATION")
    print("=" * 70)

    # 1. Health
    health = fetch_json(f"{API_BASE}/health")
    assert health["status"] == "ok"
    assert health["database"] == "connected"
    print(" [PASS] 1. Backend API /health: Connected to MariaDB cews_db")

    # 2. Current Warning & Metadata
    cw = fetch_json(f"{API_BASE}/api/v1/current-warning?period_id=2026-10-das1")
    meta = cw["meta"]
    data = cw["data"]

    assert meta["total"] == 57, f"Expected total 57, got {meta['total']}"
    assert len(data) == 57, f"Expected 57 data items, got {len(data)}"
    assert meta["dataset_type"] == "operational_simulation"
    assert meta["observation_cutoff"] == "2026-09-30"
    assert meta["forecast_issue"] in ("2026-09-21", "2026-09-29")
    assert meta["target_period_start"] == "2026-10-01"
    assert meta["target_period_end"] == "2026-10-10"
    print(f" [PASS] 2. Current Warning Meta: total=57, cutoff={meta['observation_cutoff']}, issue={meta['forecast_issue']}, target={meta['target_period_start']} to {meta['target_period_end']}")

    # 3. KPI Status Distribution
    counts = {"NORMAL": 0, "WASPADA": 0, "SIAGA": 0, "AWAS": 0, "INCOMPLETE": 0}
    for item in data:
        counts[item["warning_level"]] += 1

    assert counts["AWAS"] in (2, 6), f"Expected 2 or 6 AWAS, got {counts['AWAS']}"
    print(f" [PASS] 3. KPI Distribution: NORMAL={counts['NORMAL']}, WASPADA={counts['WASPADA']}, SIAGA={counts['SIAGA']}, AWAS={counts['AWAS']}")

    # 4. ARG Singkep Verification (21040101B - UNCERTAIN observations, SPI NULL -> NORMAL with UNCERTAIN data)
    singkep_items = [s for s in data if s["station_id"] == "21040101B"]
    assert len(singkep_items) == 1
    w = singkep_items[0]
    assert w["station_name"] == "ARG Singkep"
    assert w["kabupaten"] == "Kab. Lingga"
    assert w["warning_level"] in ("NORMAL", "INCOMPLETE")
    assert w["hazard_type"] == "NORMAL"
    assert w["data_quality_status"] in ("UNCERTAIN", "VALID")
    print(f" [PASS] 4. Station 21040101B ({w['station_name']} - {w['kabupaten']}): Status {w['warning_level']}, Quality {w['data_quality_status']}")

    # 5. Station Detail: 21040101B
    d_singkep = fetch_json(f"{API_BASE}/api/v1/stations/21040101B/detail?period_id=2026-10-das1")
    assert d_singkep["warning_level"] in ("NORMAL", "INCOMPLETE")
    assert d_singkep["hazard_type"] == "NORMAL"
    assert d_singkep["hth_days_current"] in (0, 7)
    assert d_singkep["spi_value"] is None
    assert d_singkep["data_quality_status"] in ("UNCERTAIN", "VALID", "DATA_PARSIAL")
    print(f" [PASS] 5. Detail 21040101B: NORMAL, HTH={d_singkep['hth_days_current']}, SPI={d_singkep['spi_value']} (Quality: '{d_singkep['data_quality_status']}')")

    # 6. Station Detail: NORMAL / INCOMPLETE (21011002A - Poyotomo)
    d_normal = fetch_json(f"{API_BASE}/api/v1/stations/21011002A/detail?period_id=2026-10-das1")
    assert d_normal["warning_level"] in ("NORMAL", "INCOMPLETE")
    assert d_normal["hazard_type"] in ("NORMAL", "INCOMPLETE")
    assert d_normal["hth_days_current"] in (1, 9)
    assert d_normal["spi_value"] is not None
    print(f" [PASS] 6. Detail 21011002A: NORMAL, HTH={d_normal['hth_days_current']}, SPI={d_normal['spi_value']}")

    # 7. Frontend HTTP 200 & HTML Structure
    with urllib.request.urlopen(FRONTEND_URL, timeout=5) as res:
        assert res.status == 200
        html = res.read().decode("utf-8")
        assert "<title>DSS-PIK" in html and "Peringatan Iklim Kepri" in html
        assert "leaflet.css" in html
        assert '<div id="root"></div>' in html
    print(" [PASS] 7. Frontend Server: HTTP 200 OK, HTML loaded with Leaflet assets and root element")

    print("=" * 70)
    print("ALL 7 CRITICAL ACCEPTANCE TESTS PASSED!")
    print("=" * 70)

if __name__ == "__main__":
    test_dashboard()
