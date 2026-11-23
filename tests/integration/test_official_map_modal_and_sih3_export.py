"""
tests/integration/test_official_map_modal_and_sih3_export.py
Integration & Acceptance Tests for Simplified Regional Warning Assignment
and Dual Output Generator (Single Combined JPG Map + SIH3 JSON Export)
BMKG Stasiun Meteorologi Kelas II Raja Haji Fisabilillah Tanjungpinang

Covers the 12 Acceptance Scenarios defined in Master Prompt Section I:
1. Bintan PDKM WASPADA
2. Natuna PDCHT SIAGA
3. Mixed hazards across different regions
4. All regions AMAN
5. Manual override with mandatory justification and audit trail
6. Multi-hazard conflict display & explicit operator assignment
7. Insufficient data protection (<50% coverage remains INSUFFICIENT_DATA)
8. Single combined JPG map generation (150 DPI, 1653x1170)
9. Single JSON covering all 7 canonical regencies
10. Strict JSON schema validation against docs/schemas/sih3_regional_warning.schema.json
11. Preview vs Download payload identity
12. Application navigation invariant (strictly 3 tabs, no new pages/menus)
"""

import json
from pathlib import Path
from PIL import Image
import pytest
from fastapi.testclient import TestClient

from backend.main import app
from backend.auth import create_session_token
from backend.database import get_db
from backend.regional_warning_service import (
    CANONICAL_REGIONS,
    build_map_modal_sih3_json,
    validate_sih3_json_payload,
    ensure_regional_warning_tables,
    get_verified_station_region_mapping,
)
from backend.map_generator import generate_official_warning_map, OUTPUT_DIR as MAPS_OUTPUT_DIR
from config.paths import DOCS_DIR

client = TestClient(app)
AUTH_HEADERS = {"Authorization": f"Bearer {create_session_token('klimatkepri')}"}
TEST_PERIOD = "2026-09-das2"


def _cleanup_test_tables():
    ensure_regional_warning_tables()
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM cews_regional_warning_decisions")
            cur.execute("DELETE FROM cews_regional_decision_audit_log")
            cur.execute("DELETE FROM cews_sih3_publications")
        conn.commit()


@pytest.fixture(autouse=True)
def clean_tables_each_test():
    _cleanup_test_tables()
    yield
    _cleanup_test_tables()


def _make_synthetic_snapshot(station_overrides=None):
    mapping = get_verified_station_region_mapping()
    items = []
    for stn in mapping["stations"]:
        sid = stn["station_id"]
        is_arg = bool(stn["is_arg"])
        base_item = {
            "station_id": sid,
            "station_name": stn["station_name"],
            "kabupaten": stn["region_name"],
            "station_type": stn["station_type"],
            "is_arg": is_arg,
            "hth_days_current": 5,
            "hth_uncertain": False,
            "spi_value": 0.25,
            "spi_validation_status": None if is_arg else "VALID",
            "prob_below20": 15.0,
            "prob_above150": 10.0,
            "prob_above200": 5.0,
            "prob_above300": 1.0,
            "prob_month_above300": 12.0,
            "prob_month_above400": 4.0,
            "prob_month_above500": 1.0,
            "last_observation_date": "2026-09-10",
            "data_quality_status": "VALID",
        }
        if station_overrides and sid in station_overrides:
            base_item.update(station_overrides[sid])
        items.append(base_item)

    return {
        "period_id": TEST_PERIOD,
        "label": "Dasarian II September 2026",
        "observation_cutoff": "2026-09-10",
        "forecast_issue": "2026-08-01",
        "spi_evidence_date": "2026-09-10",
        "target_start": "2026-09-11",
        "target_end": "2026-09-20",
        "items": items,
    }


# ==============================================================================
# SCENARIO 1: Bintan PDKM WASPADA
# ==============================================================================
def test_scenario_01_bintan_pdkm_waspada():
    """Skenario 1: Bintan PDKM WASPADA tersimpan dan terevaluasi dengan benar."""
    req_body = {
        "period_id": TEST_PERIOD,
        "scope": "GABUNGAN",
        "regency_decisions": {
            "BINTAN": {"warning_type": "PDKM", "classification": "WASPADA", "override_reason": "Verifikasi HTH dan SPI Dasarian."},
            "KARIMUN": {"warning_type": None, "classification": "AMAN"},
            "KEPULAUAN ANAMBAS": {"warning_type": None, "classification": "AMAN"},
            "KOTA BATAM": {"warning_type": None, "classification": "AMAN"},
            "KOTA TANJUNGPINANG": {"warning_type": None, "classification": "AMAN"},
            "LINGGA": {"warning_type": None, "classification": "AMAN"},
            "NATUNA": {"warning_type": None, "classification": "AMAN"},
        },
        "operator_name": "Forecaster BMKG",
    }

    resp = client.post("/api/v1/maps/generate-json", json=req_body, headers=AUTH_HEADERS)
    assert resp.status_code == 200, resp.text
    res = resp.json()

    assert res["success"] is True
    bintan = next(r for r in res["payload"]["regions"] if r["sih3_polygon_key"] == "BINTAN")
    assert bintan["overall_region_status"] == "WASPADA"
    assert len(bintan["warnings"]) == 1
    assert bintan["warnings"][0]["hazard_code"] == "PDKM"
    assert bintan["warnings"][0]["final_level"] == "WASPADA"
    assert bintan["hazard_assessments"]["PDKM"]["final_level"] == "WASPADA"
    assert bintan["hazard_assessments"]["PDCHT"]["final_level"] == "AMAN"


# ==============================================================================
# SCENARIO 2: Natuna PDCHT SIAGA
# ==============================================================================
def test_scenario_02_natuna_pdcht_siaga():
    """Skenario 2: Natuna PDCHT SIAGA tersimpan dan terevaluasi dengan benar."""
    req_body = {
        "period_id": TEST_PERIOD,
        "scope": "GABUNGAN",
        "regency_decisions": {
            "BINTAN": {"warning_type": None, "classification": "AMAN"},
            "KARIMUN": {"warning_type": None, "classification": "AMAN"},
            "KEPULAUAN ANAMBAS": {"warning_type": None, "classification": "AMAN"},
            "KOTA BATAM": {"warning_type": None, "classification": "AMAN"},
            "KOTA TANJUNGPINANG": {"warning_type": None, "classification": "AMAN"},
            "LINGGA": {"warning_type": None, "classification": "AMAN"},
            "NATUNA": {"warning_type": "PDCHT", "classification": "SIAGA", "override_reason": "Probabilitas CH Dasarian > 150mm tinggi."},
        },
        "operator_name": "Forecaster BMKG",
    }

    resp = client.post("/api/v1/maps/generate-json", json=req_body, headers=AUTH_HEADERS)
    assert resp.status_code == 200, resp.text
    res = resp.json()

    natuna = next(r for r in res["payload"]["regions"] if r["sih3_polygon_key"] == "NATUNA")
    assert natuna["overall_region_status"] == "SIAGA"
    assert len(natuna["warnings"]) == 1
    assert natuna["warnings"][0]["hazard_code"] == "PDCHT"
    assert natuna["warnings"][0]["final_level"] == "SIAGA"
    assert natuna["hazard_assessments"]["PDCHT"]["final_level"] == "SIAGA"


# ==============================================================================
# SCENARIO 3: Wilayah Berbeda Memiliki Jenis Bahaya Berbeda
# ==============================================================================
def test_scenario_03_mixed_hazards_different_regions():
    """Skenario 3: Bintan PDKM, Natuna PDCHT, Lingga PDKM, Anambas PDCHT, lainnya AMAN."""
    req_body = {
        "period_id": TEST_PERIOD,
        "scope": "GABUNGAN",
        "regency_decisions": {
            "BINTAN": {"warning_type": "PDKM", "classification": "WASPADA", "override_reason": "Kekeringan lokal Bintan."},
            "NATUNA": {"warning_type": "PDCHT", "classification": "SIAGA", "override_reason": "Curah hujan lebat Natuna."},
            "LINGGA": {"warning_type": "PDKM", "classification": "SIAGA", "override_reason": "HTH ekstrem Lingga."},
            "KEPULAUAN ANAMBAS": {"warning_type": "PDCHT", "classification": "WASPADA", "override_reason": "Ancaman genangan Anambas."},
            "KARIMUN": {"warning_type": None, "classification": "AMAN"},
            "KOTA BATAM": {"warning_type": None, "classification": "AMAN"},
            "KOTA TANJUNGPINANG": {"warning_type": None, "classification": "AMAN"},
        },
        "operator_name": "Senior Meteorologist BMKG",
    }

    resp = client.post("/api/v1/maps/generate-json", json=req_body, headers=AUTH_HEADERS)
    assert resp.status_code == 200
    res = resp.json()

    regions_map = {r["sih3_polygon_key"]: r for r in res["payload"]["regions"]}

    assert regions_map["BINTAN"]["overall_region_status"] == "WASPADA"
    assert regions_map["BINTAN"]["warnings"][0]["hazard_code"] == "PDKM"

    assert regions_map["NATUNA"]["overall_region_status"] == "SIAGA"
    assert regions_map["NATUNA"]["warnings"][0]["hazard_code"] == "PDCHT"

    assert regions_map["LINGGA"]["overall_region_status"] == "SIAGA"
    assert regions_map["LINGGA"]["warnings"][0]["hazard_code"] == "PDKM"

    assert regions_map["KEPULAUAN ANAMBAS"]["overall_region_status"] == "WASPADA"
    assert regions_map["KEPULAUAN ANAMBAS"]["warnings"][0]["hazard_code"] == "PDCHT"

    assert regions_map["KARIMUN"]["overall_region_status"] == "AMAN"
    assert len(regions_map["KARIMUN"]["warnings"]) == 0


# ==============================================================================
# SCENARIO 4: Semua Wilayah AMAN
# ==============================================================================
def test_scenario_04_all_regions_aman():
    """Skenario 4: Seluruh wilayah berstatus AMAN (Tidak Ada Peringatan)."""
    req_body = {
        "period_id": TEST_PERIOD,
        "scope": "GABUNGAN",
        "regency_decisions": {r["sih3_polygon_key"]: {"warning_type": None, "classification": "AMAN"} for r in CANONICAL_REGIONS},
        "operator_name": "Petugas Piket",
    }

    resp = client.post("/api/v1/maps/generate-json", json=req_body, headers=AUTH_HEADERS)
    assert resp.status_code == 200
    res = resp.json()

    for r in res["payload"]["regions"]:
        if r["data_status"] != "INSUFFICIENT_DATA":
            assert r["overall_region_status"] == "AMAN"
        assert len(r["warnings"]) == 0

    assert res["summary"]["pdkm_active"] == 0
    assert res["summary"]["pdcht_active"] == 0


# ==============================================================================
# SCENARIO 5: Override Manual dengan Alasan Wajib dan Audit Tercatat
# ==============================================================================
def test_scenario_05_manual_override_audit():
    """Skenario 5: Override manual mewajibkan alasan penyesuaian dan tercatat pada audit trail."""
    snap = _make_synthetic_snapshot()
    req_body = {
        "period_id": TEST_PERIOD,
        "scope": "GABUNGAN",
        "regency_decisions": {
            "KOTA BATAM": {
                "warning_type": "PDCHT",
                "classification": "WASPADA",
                "override_reason": "Verifikasi citra radar cuaca mendeteksi sel badai Cb aktif di Batam Barat."
            }
        },
        "operator_name": "Forecaster Override Test",
        "snap_override": snap,
    }

    res = build_map_modal_sih3_json(
        period_id=TEST_PERIOD,
        scope="GABUNGAN",
        regency_decisions=req_body["regency_decisions"],
        operator_name="Forecaster Override Test",
        snap_override=snap,
    )

    batam = next(r for r in res["payload"]["regions"] if r["sih3_polygon_key"] == "KOTA BATAM")
    pdcht = batam["hazard_assessments"]["PDCHT"]

    assert pdcht["decision_source"] == "OPERATOR_OVERRIDE"
    assert pdcht["operator_override"] is True
    assert "citra radar cuaca" in pdcht["override_reason"]

    # Verify audit log in MariaDB
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT * FROM cews_regional_decision_audit_log WHERE period_id = %s AND region_code = '21.71' AND hazard_code = 'PDCHT'",
                (TEST_PERIOD,)
            )
            logs = cur.fetchall()
            assert len(logs) > 0
            assert "citra radar" in logs[0]["override_reason"]


# ==============================================================================
# SCENARIO 6: Konflik Multi-Bahaya Aktif dan Pilihan Operator Eksplisit
# ==============================================================================
def test_scenario_06_multi_hazard_conflict_resolution():
    """Skenario 6: Kedua rekomendasi DSS aktif pada 1 wilayah; operator menetapkan pilihan final eksplisit."""
    # Synthetic snapshot with Lingga triggering both drought (HTH=30, SPI=-1.6) and high rain (prob>150 = 75%)
    conflict_station = {
        "hth_days_current": 30,
        "spi_value": -1.6,
        "prob_below20": 80.0,
        "prob_above150": 75.0,
        "prob_above200": 60.0,
        "data_quality_status": "VALID",
    }
    snap = _make_synthetic_snapshot({
        "21040101A": conflict_station,
        "21040401A": conflict_station,
    })

    # Operator explicitly selects PDKM AWAS despite both hazards triggering
    req_body = {
        "period_id": TEST_PERIOD,
        "scope": "GABUNGAN",
        "regency_decisions": {
            "LINGGA": {
                "warning_type": "PDKM",
                "classification": "AWAS",
                "override_reason": "Operator memprioritaskan peringatan kekeringan meteorologis ekstrem (HTH 30 hari) di atas potensi CH tinggi."
            }
        },
        "snap_override": snap,
        "operator_name": "Kepala Stasiun BMKG",
    }

    res = build_map_modal_sih3_json(
        period_id=TEST_PERIOD,
        scope="GABUNGAN",
        regency_decisions=req_body["regency_decisions"],
        operator_name="Kepala Stasiun BMKG",
        snap_override=snap,
    )

    lingga = next(r for r in res["payload"]["regions"] if r["sih3_polygon_key"] == "LINGGA")
    assert lingga["overall_region_status"] == "AWAS"
    assert len(lingga["warnings"]) == 1
    assert lingga["warnings"][0]["hazard_code"] == "PDKM"
    assert lingga["warnings"][0]["final_level"] == "AWAS"


# ==============================================================================
# SCENARIO 7: Perlindungan Cakupan Data di Bawah 50% (Tidak AMAN Palsu)
# ==============================================================================
def test_scenario_07_insufficient_data_protection():
    """Skenario 7: Stasiun valid < 50% tidak boleh menjadi AMAN palsu (harus INSUFFICIENT_DATA)."""
    missing_data = {
        "hth_days_current": None,
        "spi_value": None,
        "spi_validation_status": "MISSING",
        "data_quality_status": "INCOMPLETE",
        "prob_below20": None,
        "prob_above150": None,
    }
    snap = _make_synthetic_snapshot({
        "21050101A": missing_data,
        "21050501A": missing_data,
    })

    res = build_map_modal_sih3_json(
        period_id=TEST_PERIOD,
        scope="GABUNGAN",
        regency_decisions={
            "KEPULAUAN ANAMBAS": {"warning_type": None, "classification": "AMAN"}
        },
        snap_override=snap,
    )

    anambas = next(r for r in res["payload"]["regions"] if r["sih3_polygon_key"] == "KEPULAUAN ANAMBAS")
    assert anambas["data_status"] == "INSUFFICIENT_DATA"
    assert anambas["overall_region_status"] == "INSUFFICIENT_DATA"
    assert len(anambas["warnings"]) == 0


# ==============================================================================
# SCENARIO 8: Generate Peta JPG (Satu Peta Gabungan 150 DPI)
# ==============================================================================
def test_scenario_08_generate_jpg_map():
    """Skenario 8: Menghasilkan satu peta gabungan dalam format JPG (150 DPI, 1653x1170)."""
    payload = {
        "map_type": "UNIFIED",
        "period_id": TEST_PERIOD,
        "regency_decisions": {
            "BINTAN": {"warning_type": "PDKM", "classification": "WASPADA"},
            "NATUNA": {"warning_type": "PDCHT", "classification": "SIAGA"},
            "LINGGA": {"warning_type": "PDKM", "classification": "SIAGA"},
            "KEPULAUAN ANAMBAS": {"warning_type": "PDCHT", "classification": "WASPADA"},
            "KARIMUN": {"warning_type": None, "classification": "AMAN"},
            "KOTA BATAM": {"warning_type": None, "classification": "AMAN"},
            "KOTA TANJUNGPINANG": {"warning_type": None, "classification": "AMAN"},
        },
        "operator_name": "Petugas Kartografi BMKG",
    }

    resp = client.post("/api/v1/maps/generate", json=payload, headers=AUTH_HEADERS)
    assert resp.status_code == 200, resp.text
    data = resp.json()

    assert data["success"] is True
    assert "jpg_url" in data and data["jpg_url"].startswith("/api/v1/maps/download/")
    assert data["jpg_filename"].endswith(".jpg")

    # Download and verify JPG file integrity
    res_jpg = client.get(data["jpg_url"])
    assert res_jpg.status_code == 200
    assert res_jpg.headers.get("content-type") == "image/jpeg"
    assert len(res_jpg.content) > 50000

    # Verify image dimensions
    local_jpg_path = MAPS_OUTPUT_DIR / data["jpg_filename"]
    assert local_jpg_path.exists()
    with Image.open(local_jpg_path) as im:
        assert im.format == "JPEG"
        assert im.size == (1653, 1170)


# ==============================================================================
# SCENARIO 9: Generate JSON SIH3 (Satu Dokumen 7 Wilayah)
# ==============================================================================
def test_scenario_09_generate_json_seven_regions():
    """Skenario 9: Generate JSON menghasilkan tepat 7 wilayah administrasi Kepulauan Riau."""
    req_body = {
        "period_id": TEST_PERIOD,
        "scope": "GABUNGAN",
        "regency_decisions": {
            "BINTAN": {"warning_type": "PDKM", "classification": "WASPADA"},
            "NATUNA": {"warning_type": "PDCHT", "classification": "SIAGA"},
            "LINGGA": {"warning_type": None, "classification": "AMAN"},
            "KEPULAUAN ANAMBAS": {"warning_type": None, "classification": "AMAN"},
            "KARIMUN": {"warning_type": None, "classification": "AMAN"},
            "KOTA BATAM": {"warning_type": None, "classification": "AMAN"},
            "KOTA TANJUNGPINANG": {"warning_type": None, "classification": "AMAN"},
        },
    }

    resp = client.post("/api/v1/maps/generate-json", json=req_body, headers=AUTH_HEADERS)
    assert resp.status_code == 200
    res = resp.json()

    regions = res["payload"]["regions"]
    assert len(regions) == 7
    expected_codes = {"21.01", "21.02", "21.03", "21.04", "21.05", "21.71", "21.72"}
    actual_codes = {r["region_code"] for r in regions}
    assert actual_codes == expected_codes


# ==============================================================================
# SCENARIO 10: Validasi Schema JSON SIH3
# ==============================================================================
def test_scenario_10_json_schema_validation():
    """Skenario 10: Dokumen JSON lulus validasi terhadap docs/schemas/sih3_regional_warning.schema.json."""
    req_body = {
        "period_id": TEST_PERIOD,
        "scope": "GABUNGAN",
        "regency_decisions": {
            "BINTAN": {"warning_type": "PDKM", "classification": "WASPADA"},
            "NATUNA": {"warning_type": "PDCHT", "classification": "SIAGA"},
        },
    }

    resp = client.post("/api/v1/maps/generate-json", json=req_body, headers=AUTH_HEADERS)
    assert resp.status_code == 200
    res = resp.json()

    assert res["validation"]["valid"] is True
    assert len(res["validation"]["errors"]) == 0

    val = validate_sih3_json_payload(res["payload"])
    assert val["valid"] is True


# ==============================================================================
# SCENARIO 11: Pratinjau Identik dengan Berkas Unduhan
# ==============================================================================
def test_scenario_11_preview_vs_download_identical():
    """Skenario 11: Isi payload pratinjau identik 100% dengan file JSON yang diunduh."""
    req_body = {
        "period_id": TEST_PERIOD,
        "scope": "GABUNGAN",
        "regency_decisions": {
            "BINTAN": {"warning_type": "PDKM", "classification": "WASPADA"},
            "NATUNA": {"warning_type": "PDCHT", "classification": "SIAGA"},
        },
    }

    gen_resp = client.post("/api/v1/maps/generate-json", json=req_body, headers=AUTH_HEADERS)
    assert gen_resp.status_code == 200
    gen_data = gen_resp.json()
    preview_payload = gen_data["payload"]
    fname = gen_data["download_filename"]

    # Download from endpoint
    dl_resp = client.get(f"/api/v1/maps/download/{fname}")
    assert dl_resp.status_code == 200
    downloaded_payload = dl_resp.json()

    assert preview_payload == downloaded_payload


# ==============================================================================
# SCENARIO 12: Invariant Navigasi Aplikasi (Tidak Ada Halaman/Menu Baru)
# ==============================================================================
def test_scenario_12_app_navigation_invariants():
    """Skenario 12: Memastikan navigasi aplikasi strictly 3 menu, tidak ada halaman/menu baru."""
    header_code = Path("frontend/src/components/Header.jsx").read_text(encoding="utf-8")
    assert "regional-warning" not in header_code
    assert "Peringatan Wilayah &amp; SIH3" not in header_code

    banner_code = Path("frontend/src/components/SimulationBanner.jsx").read_text(encoding="utf-8")
    assert "onOpenRegionalWarning" not in banner_code
    assert "Publikasi SIH3" not in banner_code

    rwm_path = Path("frontend/src/components/RegionalWarningManager.jsx")
    assert not rwm_path.exists(), "RegionalWarningManager.jsx must remain deleted"


# ==============================================================================
# SCENARIOS 13, 14, 15: SINGLE-HAZARD RESTORATION & HIGH-PRECISION BOUNDARIES
# ==============================================================================
def test_scenario_13_single_hazard_pdkm_restoration_and_boundary_precision():
    """
    Skenario 13: Single-Hazard PDKM Pemulihan Template Lama:
    - Bintan=WASPADA, Karimun=AMAN, Natuna=SIAGA, Lingga=AMAN, Anambas=AWAS, Batam=AMAN, Tanjungpinang=AMAN
    - Output map strictly uses legacy official PDKM template and title KEKERINGAN METEOROLOGIS
    - DO NOT render multi-hazard callout boxes.
    - All regency colors match exact administrative boundaries.
    """
    from backend.map_generator import get_regency_masks, STATUS_COLORS

    req_body = {
        "period_id": TEST_PERIOD,
        "map_type": "UNIFIED",
        "scope": "GABUNGAN",
        "regency_decisions": {
            "BINTAN": {"warning_type": "PDKM", "classification": "WASPADA"},
            "KARIMUN": {"warning_type": "NONE", "classification": "AMAN"},
            "NATUNA": {"warning_type": "PDKM", "classification": "SIAGA"},
            "LINGGA": {"warning_type": "NONE", "classification": "AMAN"},
            "KEPULAUAN ANAMBAS": {"warning_type": "PDKM", "classification": "AWAS"},
            "KOTA BATAM": {"warning_type": "NONE", "classification": "AMAN"},
            "KOTA TANJUNGPINANG": {"warning_type": "NONE", "classification": "AMAN"},
        },
        "operator_name": "Petugas Penguji",
    }
    resp = client.post("/api/v1/maps/generate", json=req_body, headers=AUTH_HEADERS)
    assert resp.status_code == 200
    data = resp.json()

    assert data["map_type"] == "PDKM"
    assert "PETA_PDKM_" in data["jpg_filename"]

    # Verify PNG output colors
    png_path = MAPS_OUTPUT_DIR / data["png_filename"]
    assert png_path.exists()
    im = Image.open(png_path)
    import numpy as np
    arr = np.array(im)
    masks = get_regency_masks(arr)

    # Check exact status colors
    assert (arr[masks["BINTAN"]] == np.array(STATUS_COLORS["WASPADA"])).all()
    assert (arr[masks["NATUNA"]] == np.array(STATUS_COLORS["SIAGA"])).all()
    assert (arr[masks["KEPULAUAN ANAMBAS"]] == np.array(STATUS_COLORS["AWAS"])).all()
    assert (arr[masks["KOTA TANJUNGPINANG"]] == np.array(STATUS_COLORS["AMAN"])).all()
    assert (arr[masks["KARIMUN"]] == np.array(STATUS_COLORS["AMAN"])).all()
    assert (arr[masks["LINGGA"]] == np.array(STATUS_COLORS["AMAN"])).all()
    assert (arr[masks["KOTA BATAM"]] == np.array(STATUS_COLORS["AMAN"])).all()


def test_scenario_14_single_hazard_pdcht_restoration_and_boundary_precision():
    """
    Skenario 14: Single-Hazard PDCHT Pemulihan Template Lama:
    - Bintan=SIAGA, Karimun=AMAN, Natuna=AWAS, Lingga=WASPADA, Anambas=AMAN, Batam=AMAN, Tanjungpinang=AMAN
    - Output map strictly uses legacy official PDCHT template and title CURAH HUJAN TINGGI
    - DO NOT render multi-hazard callout boxes.
    - All regency colors match exact administrative boundaries.
    """
    from backend.map_generator import get_regency_masks, STATUS_COLORS

    req_body = {
        "period_id": "2025-01-das2",
        "map_type": "UNIFIED",
        "scope": "GABUNGAN",
        "regency_decisions": {
            "BINTAN": {"warning_type": "PDCHT", "classification": "SIAGA"},
            "KARIMUN": {"warning_type": "NONE", "classification": "AMAN"},
            "NATUNA": {"warning_type": "PDCHT", "classification": "AWAS"},
            "LINGGA": {"warning_type": "PDCHT", "classification": "WASPADA"},
            "KEPULAUAN ANAMBAS": {"warning_type": "NONE", "classification": "AMAN"},
            "KOTA BATAM": {"warning_type": "NONE", "classification": "AMAN"},
            "KOTA TANJUNGPINANG": {"warning_type": "NONE", "classification": "AMAN"},
        },
        "operator_name": "Petugas Penguji",
    }
    resp = client.post("/api/v1/maps/generate", json=req_body, headers=AUTH_HEADERS)
    assert resp.status_code == 200
    data = resp.json()

    assert data["map_type"] == "PDCHT"
    assert "PETA_PDCHT_" in data["jpg_filename"]

    png_path = MAPS_OUTPUT_DIR / data["png_filename"]
    assert png_path.exists()
    im = Image.open(png_path)
    import numpy as np
    arr = np.array(im)
    masks = get_regency_masks(arr)

    assert (arr[masks["BINTAN"]] == np.array(STATUS_COLORS["SIAGA"])).all()
    assert (arr[masks["NATUNA"]] == np.array(STATUS_COLORS["AWAS"])).all()
    assert (arr[masks["LINGGA"]] == np.array(STATUS_COLORS["WASPADA"])).all()
    assert (arr[masks["KOTA TANJUNGPINANG"]] == np.array(STATUS_COLORS["AMAN"])).all()
    assert (arr[masks["KARIMUN"]] == np.array(STATUS_COLORS["AMAN"])).all()
    assert (arr[masks["KEPULAUAN ANAMBAS"]] == np.array(STATUS_COLORS["AMAN"])).all()
    assert (arr[masks["KOTA BATAM"]] == np.array(STATUS_COLORS["AMAN"])).all()


def test_scenario_15_tpi_vs_bintan_polygon_boundary_precision():
    """
    Skenario 15: Verifikasi Presisi Batas Polygon Kota Tanjungpinang vs Kabupaten Bintan:
    - Kota Tanjungpinang = Aman (Green: 51, 255, 0)
    - Kabupaten Bintan = Waspada (Yellow: 255, 255, 0)
    - Seluruh polygon Tanjungpinang berwarna hijau dan seluruh polygon Bintan berwarna kuning.
    - Zero bleed across administrative borders.
    """
    from backend.map_generator import get_regency_masks, STATUS_COLORS
    import numpy as np

    res = generate_official_warning_map(
        map_type="UNIFIED",
        period_title="Dasarian II September 2026",
        period_id="2026-09-das2",
        regency_decisions={
            "KOTA TANJUNGPINANG": {"warning_type": "NONE", "classification": "AMAN"},
            "BINTAN": {"warning_type": "PDKM", "classification": "WASPADA"},
        },
        operator_name="Petugas Penguji"
    )
    png_path = MAPS_OUTPUT_DIR / res["png_filename"]
    arr = np.array(Image.open(png_path))
    masks = get_regency_masks(arr)

    # Tanjungpinang mask is 100% green
    tpi_pixels = arr[masks["KOTA TANJUNGPINANG"]]
    assert len(tpi_pixels) > 200
    assert (tpi_pixels == np.array(STATUS_COLORS["AMAN"])).all()

    # Bintan mask is 100% yellow
    bintan_pixels = arr[masks["BINTAN"]]
    assert len(bintan_pixels) > 1500
    assert (bintan_pixels == np.array(STATUS_COLORS["WASPADA"])).all()

