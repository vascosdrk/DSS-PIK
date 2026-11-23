import pytest
from fastapi.testclient import TestClient
from backend.main import app
from backend.auth import create_session_token

@pytest.fixture
def client():
    return TestClient(app)

@pytest.fixture
def auth_headers():
    token = create_session_token("admin")
    return {"Authorization": f"Bearer {token}"}

def test_refresh_evaluate_endpoint_unauthorized(client):
    res = client.post("/api/v1/warnings/refresh-evaluate")
    assert res.status_code == 401

def test_refresh_evaluate_endpoint_success(client, auth_headers):
    res = client.post("/api/v1/warnings/refresh-evaluate?period_id=2026-11-das1", headers=auth_headers)
    assert res.status_code == 200
    data = res.json()
    assert data["success"] is True
    assert data["period_id"] == "2026-11-das1"
    assert data["stations_total"] == 57
    stats = data["stats"]
    assert stats["valid_spi_30d"] == 38
    assert stats["valid_spi_90d"] == 18
    assert stats["valid_hth"] >= 40

def test_early_warning_table_spi_integration(client, auth_headers):
    res = client.get("/api/v1/early-warning-table?period_id=2026-11-das1", headers=auth_headers)
    assert res.status_code == 200
    data = res.json()
    items = data.get("data", [])
    assert len(items) == 57
    
    # 52 manual stations and 5 ARG
    arg_items = [i for i in items if i.get("is_arg")]
    manual_items = [i for i in items if not i.get("is_arg")]
    assert len(arg_items) == 5
    assert len(manual_items) == 52

    # ARG stations must strictly have None for SPI
    for a in arg_items:
        assert a.get("spi_value") is None
        assert a.get("spi_value_90d") is None

    # Check manual stations with SPI
    valid_spi30 = [m for m in manual_items if m.get("spi_value") is not None]
    valid_spi90 = [m for m in manual_items if m.get("spi_value_90d") is not None]
    assert len(valid_spi30) == 38
    assert len(valid_spi90) == 18

def test_regional_recommendations_integration(client, auth_headers):
    res = client.get("/api/v1/warnings/regional/recommendations?period_id=2026-11-das1", headers=auth_headers)
    assert res.status_code == 200
    data = res.json()
    regions = data.get("regions", [])
    assert len(regions) == 7
    reg_names = [r["region_name"] for r in regions]
    assert "Kabupaten Bintan" in reg_names
    assert "Kota Tanjungpinang" in reg_names
    assert "Kota Batam" in reg_names

