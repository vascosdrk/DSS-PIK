"""
tests/integration/test_regional_warning_publication.py
End-to-End Integration & Acceptance Tests for:
- Regional Warning Aggregation per Kabupaten/Kota (7 Regions of Kepulauan Riau)
- Simultaneous Multi-Hazard Support (PDKM & PDCHT independently evaluated)
- Honest Data Sufficiency & Coverage Protection (INSUFFICIENT_DATA vs False Green AMAN)
- Operator Decision Override, Mandatory Reason/Analysis Notes & Audit Trail
- Publication Workflow State Machine (DRAFT -> REVIEW -> APPROVED -> PUBLISHED)
- Revision Control after PUBLISHED (Revision N -> Revision N+1 without overwriting history)
- Public Read-Only SIH3 JSON Endpoint (/api/v1/publications/sih3/latest.json)
- JSON Schema Validation (docs/schemas/sih3_regional_warning.schema.json)
"""

import copy
import json
from pathlib import Path
import pytest
from fastapi.testclient import TestClient

from backend.main import app
from backend.database import get_db
from backend.auth import create_session_token
from backend.regional_warning_service import (
    CANONICAL_REGIONS,
    ensure_regional_warning_tables,
    get_verified_station_region_mapping,
    compute_regional_recommendations,
    save_regional_warning_decision,
    build_sih3_publication_json,
    validate_sih3_json_payload,
    execute_publication_workflow,
    get_sih3_publication_history,
    get_latest_published_sih3_json,
)

TEST_PERIOD_ID = "2026-09-das2"


def _cleanup_test_publications_and_decisions():
    """Removes any test records created during integration tests to preserve baseline DB state."""
    ensure_regional_warning_tables()
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM cews_regional_warning_decisions")
            cur.execute("DELETE FROM cews_regional_decision_audit_log")
            cur.execute("DELETE FROM cews_sih3_publications")
        conn.commit()


@pytest.fixture(autouse=True)
def clean_regional_tables():
    _cleanup_test_publications_and_decisions()
    yield
    _cleanup_test_publications_and_decisions()


def _make_synthetic_snapshot(station_overrides=None):
    """
    Creates a deterministic 57-station snapshot based on canonical station metadata
    where all stations default to complete normal observations unless overridden.
    """
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
        "period_id": TEST_PERIOD_ID,
        "label": "Dasarian II September 2026",
        "observation_cutoff": "2026-09-10",
        "forecast_issue": "2026-08-01",
        "spi_evidence_date": "2026-09-10",
        "target_start": "2026-09-11",
        "target_end": "2026-09-20",
        "items": items,
    }


def test_scenario_01_all_regions_normal():
    """Skenario 1: Seluruh 7 Kabupaten/Kota AMAN ketika seluruh indikator di bawah ambang."""
    snap = _make_synthetic_snapshot()
    res = compute_regional_recommendations(period_id=TEST_PERIOD_ID, snap_override=snap)
    assert len(res["regions"]) == 7
    assert res["summary"]["pdkm_active_regions"] == 0
    assert res["summary"]["pdcht_active_regions"] == 0
    for reg in res["regions"]:
        assert reg["pdkm"]["recommended_level"] == "AMAN"
        assert reg["pdcht"]["recommended_level"] == "AMAN"
        assert reg["overall_region_status"] == "AMAN"
        assert len(reg["active_warnings"]) == 0


def test_scenario_02_single_region_pdkm_active():
    """Skenario 2: Satu wilayah mengalami PDKM aktif (Kab. Bintan SIAGA)."""
    snap = _make_synthetic_snapshot({
        "21010401A": {
            "hth_days_current": 35,
            "spi_value": -1.65,
            "prob_below20": 78.5,
        }
    })
    res = compute_regional_recommendations(period_id=TEST_PERIOD_ID, snap_override=snap)
    bintan = next(r for r in res["regions"] if r["region_code"] == "21.01")
    assert bintan["pdkm"]["recommended_level"] == "SIAGA"
    assert bintan["pdcht"]["recommended_level"] == "AMAN"
    assert bintan["pdkm"]["triggering_stations_count"] == 1
    assert bintan["pdkm"]["triggering_stations"][0]["station_id"] == "21010401A"
    assert len(bintan["active_warnings"]) == 1
    assert bintan["active_warnings"][0]["hazard_code"] == "PDKM"
    assert bintan["active_warnings"][0]["final_level"] == "SIAGA"


def test_scenario_03_single_region_pdcht_active():
    """Skenario 3: Satu wilayah mengalami PDCHT aktif (Kab. Natuna WASPADA)."""
    snap = _make_synthetic_snapshot({
        "21030401A": {
            "prob_above150": 76.2,
            "prob_month_above300": 74.0,
        }
    })
    res = compute_regional_recommendations(period_id=TEST_PERIOD_ID, snap_override=snap)
    natuna = next(r for r in res["regions"] if r["region_code"] == "21.03")
    assert natuna["pdcht"]["recommended_level"] == "WASPADA"
    assert natuna["pdkm"]["recommended_level"] == "AMAN"
    assert natuna["pdcht"]["triggering_stations_count"] == 1
    assert len(natuna["active_warnings"]) == 1
    assert natuna["active_warnings"][0]["hazard_code"] == "PDCHT"
    assert natuna["active_warnings"][0]["final_level"] == "WASPADA"


def test_scenario_04_single_region_simultaneous_pdkm_and_pdcht():
    """Skenario 4: Satu wilayah mengalami PDKM dan PDCHT secara bersamaan di pos berbeda (Kab. Lingga)."""
    snap = _make_synthetic_snapshot({
        # Pos 21040201A memicu PDKM WASPADA
        "21040201A": {
            "hth_days_current": 24,
            "spi_value": -1.20,
            "prob_below20": 75.0,
        },
        # Pos 21040202A memicu PDCHT SIAGA
        "21040202A": {
            "prob_above150": 82.0,
            "prob_above200": 76.0,
            "prob_month_above300": 80.0,
            "prob_month_above400": 73.5,
        },
    })
    res = compute_regional_recommendations(period_id=TEST_PERIOD_ID, snap_override=snap)
    lingga = next(r for r in res["regions"] if r["region_code"] == "21.04")
    assert lingga["pdkm"]["recommended_level"] == "WASPADA"
    assert lingga["pdcht"]["recommended_level"] == "SIAGA"
    assert len(lingga["active_warnings"]) == 2
    hazard_codes = {w["hazard_code"] for w in lingga["active_warnings"]}
    assert hazard_codes == {"PDKM", "PDCHT"}
    assert res["summary"]["multi_hazard_regions"] == 1


def test_scenario_05_region_insufficient_data_never_false_green():
    """Skenario 5: Wilayah dengan cakupan stasiun valid < 50% menghasilkan INSUFFICIENT_DATA, bukan False Green AMAN."""
    # Kabupaten Kepulauan Anambas (21.05) memiliki 3 pos (21050101A, 21050501A, 21050201A). Buat 2 pos missing (cakupan 33.3% < 50%).
    missing_override = {
        "hth_days_current": None,
        "spi_value": None,
        "prob_below20": None,
        "prob_above150": None,
        "prob_above200": None,
        "prob_above300": None,
        "prob_month_above300": None,
        "prob_month_above400": None,
        "prob_month_above500": None,
    }
    snap = _make_synthetic_snapshot({
        "21050101A": missing_override,
        "21050501A": missing_override,
    })
    res = compute_regional_recommendations(period_id=TEST_PERIOD_ID, snap_override=snap, min_coverage_pct=50.0)
    anambas = next(r for r in res["regions"] if r["region_code"] == "21.05")
    assert anambas["pdkm"]["recommended_level"] == "INSUFFICIENT_DATA"
    assert anambas["pdcht"]["recommended_level"] == "INSUFFICIENT_DATA"
    assert anambas["data_status"] == "INSUFFICIENT_DATA"
    assert anambas["overall_region_status"] == "INSUFFICIENT_DATA"


def test_scenario_06_operator_override_requires_reason_and_preserves_recommendation():
    """Skenario 6: Petugas melakukan override rekomendasi DSS; wajib alasan & catatan, dan rekomendasi awal tetap tersimpan."""
    snap = _make_synthetic_snapshot()

    # Tanpa alasan override harus ditolak
    with pytest.raises(ValueError, match="override_reason"):
        save_regional_warning_decision(
            period_id=TEST_PERIOD_ID,
            region_code="21.71",
            hazard_code="PDCHT",
            decision_mode="OPERATOR_OVERRIDE",
            final_level="WASPADA",
            override_reason="",
            analysis_notes="Catatan singkat",
            operator="forecaster_test",
            snap_override=snap,
        )

    # Dengan alasan dan catatan analisis yang valid harus berhasil
    saved = save_regional_warning_decision(
        period_id=TEST_PERIOD_ID,
        region_code="21.71",
        hazard_code="PDCHT",
        decision_mode="OPERATOR_OVERRIDE",
        final_level="WASPADA",
        override_reason="Konvergensi angin lokal dan pertumbuhan awan Cb intensif di Batam.",
        analysis_notes="Ditetapkan WASPADA berdasarkan rapat evaluasi sinoptik Stamet RHF.",
        operator="forecaster_test",
        snap_override=snap,
    )
    assert saved["recommended_level"] == "AMAN"
    assert saved["final_level"] == "WASPADA"
    assert saved["operator_override"] is True

    # Pastikan hasil merge menyimpan keduanya
    merged = compute_regional_recommendations(period_id=TEST_PERIOD_ID, snap_override=snap)
    batam = next(r for r in merged["regions"] if r["region_code"] == "21.71")
    assert batam["pdcht"]["recommended_level"] == "AMAN"
    assert batam["pdcht"]["final_level"] == "WASPADA"
    assert batam["pdcht"]["operator_override"] is True


def test_scenario_07_and_08_workflow_gates_and_revision_increment():
    """
    Skenario 7 & 8:
    - Dokumen DRAFT / REVIEW tidak boleh langsung menjadi PUBLISHED tanpa APPROVED.
    - Endpoint publik /api/v1/publications/sih3/latest.json hanya mengembalikan status PUBLISHED.
    - Perubahan setelah PUBLISHED menghasilkan revisi baru (revision + 1) tanpa menghapus histori lama.
    """
    snap = _make_synthetic_snapshot()

    # 1. Simpan sebagai DRAFT
    d1 = execute_publication_workflow(
        period_id=TEST_PERIOD_ID,
        action="SAVE_DRAFT",
        operator="forecaster_test",
        snap_override=snap,
    )
    assert d1["workflow_status"] == "DRAFT"
    assert d1["revision"] == 1

    # Coba langsung PUBLISH dari DRAFT -> wajib ditolak
    with pytest.raises(ValueError, match="APPROVED"):
        execute_publication_workflow(
            period_id=TEST_PERIOD_ID,
            action="PUBLISH",
            operator="forecaster_test",
            snap_override=snap,
        )

    # Endpoint publik latest.json tidak boleh membocorkan DRAFT
    with pytest.raises(LookupError):
        get_latest_published_sih3_json(period_id=TEST_PERIOD_ID)

    # 2. Lanjut ke REVIEW -> APPROVE -> PUBLISH
    r1 = execute_publication_workflow(
        period_id=TEST_PERIOD_ID,
        action="SUBMIT_REVIEW",
        operator="forecaster_test",
        snap_override=snap,
    )
    assert r1["workflow_status"] == "REVIEW"

    a1 = execute_publication_workflow(
        period_id=TEST_PERIOD_ID,
        action="APPROVE",
        operator="koordinator_test",
        snap_override=snap,
    )
    assert a1["workflow_status"] == "APPROVED"

    p1 = execute_publication_workflow(
        period_id=TEST_PERIOD_ID,
        action="PUBLISH",
        operator="forecaster_test",
        snap_override=snap,
    )
    assert p1["workflow_status"] == "PUBLISHED"
    assert p1["revision"] == 1

    # Endpoint publik sekarang mengembalikan revisi 1 yang berstatus PUBLISHED
    pub_json_v1 = get_latest_published_sih3_json(period_id=TEST_PERIOD_ID)
    assert pub_json_v1["publication"]["status"] == "PUBLISHED"
    assert pub_json_v1["publication"]["revision"] == 1

    # 3. Skenario 8: Buat perubahan setelah PUBLISHED -> harus membentuk Revisi 2
    save_regional_warning_decision(
        period_id=TEST_PERIOD_ID,
        region_code="21.72",
        hazard_code="PDCHT",
        decision_mode="OPERATOR_OVERRIDE",
        final_level="WASPADA",
        override_reason="Pembaruan analisis radar cuaca Tanjungpinang menunjukkan sel konvektif kuat.",
        analysis_notes="Revisi peringatan wilayah Kota Tanjungpinang menjadi WASPADA.",
        operator="forecaster_test",
        snap_override=snap,
    )

    d2 = execute_publication_workflow(
        period_id=TEST_PERIOD_ID,
        action="SAVE_DRAFT",
        operator="forecaster_test",
        revision_reason="Pembaruan status PDCHT Kota Tanjungpinang menjadi WASPADA",
        snap_override=snap,
    )
    assert d2["revision"] == 2
    assert d2["workflow_status"] == "DRAFT"

    # Selama Revisi 2 masih DRAFT, endpoint publik tetap menampilkan Revisi 1 (PUBLISHED)
    still_v1 = get_latest_published_sih3_json(period_id=TEST_PERIOD_ID)
    assert still_v1["publication"]["revision"] == 1
    assert still_v1["publication"]["status"] == "PUBLISHED"

    # Approve & Publish Revisi 2
    execute_publication_workflow(
        period_id=TEST_PERIOD_ID,
        action="APPROVE",
        operator="koordinator_test",
        revision_reason="Persetujuan revisi #2 Kota Tanjungpinang",
        snap_override=snap,
    )
    p2 = execute_publication_workflow(
        period_id=TEST_PERIOD_ID,
        action="PUBLISH",
        operator="forecaster_test",
        revision_reason="Publikasi revisi #2 Kota Tanjungpinang",
        snap_override=snap,
    )
    assert p2["revision"] == 2
    assert p2["workflow_status"] == "PUBLISHED"

    # Pastikan histori menyimpan kedua revisi (Rev 1 dan Rev 2 tidak tertimpa)
    hist = get_sih3_publication_history(period_id=TEST_PERIOD_ID)
    revisions = [item["revision"] for item in hist["items"]]
    assert 1 in revisions and 2 in revisions


def test_scenario_09_json_schema_validation_catches_invalid_payload():
    """Skenario 9: Validasi JSON menolak dokumen yang tidak sesuai skema atau kehilangan wilayah."""
    snap = _make_synthetic_snapshot()
    valid_doc = build_sih3_publication_json(period_id=TEST_PERIOD_ID, snap_override=snap)
    val_ok = validate_sih3_json_payload(valid_doc)
    assert val_ok["valid"] is True
    assert len(val_ok["errors"]) == 0

    # Buat dokumen rusak: hapus 1 wilayah dan balik tanggal valid_from > valid_until
    broken_doc = copy.deepcopy(valid_doc)
    broken_doc["regions"] = broken_doc["regions"][:-1]
    broken_doc["publication"]["valid_from"] = "2026-09-25"
    broken_doc["publication"]["valid_until"] = "2026-09-11"

    val_bad = validate_sih3_json_payload(broken_doc)
    assert val_bad["valid"] is False
    assert len(val_bad["errors"]) >= 2


def test_scenario_10_rest_api_endpoints_and_public_sih3_contract():
    """Skenario 10: Pengujian endpoint REST API termasuk akses publik tanpa token ke /api/v1/publications/sih3/latest.json."""
    client = TestClient(app)
    token = create_session_token("klimatkepri")
    auth_headers = {"Authorization": f"Bearer {token}"}

    # 1. GET mapping (protected)
    r_map = client.get("/api/v1/warnings/regional/mapping", headers=auth_headers)
    assert r_map.status_code == 200
    assert r_map.json()["total_master_stations"] == 57
    assert len(r_map.json()["regions_summary"]) == 7

    # 2. GET recommendations
    r_rec = client.get(f"/api/v1/warnings/regional/recommendations?period_id={TEST_PERIOD_ID}", headers=auth_headers)
    assert r_rec.status_code == 200
    assert len(r_rec.json()["regions"]) == 7

    # 3. Sebelum ada publikasi PUBLISHED, endpoint publik mengembalikan 404 (dan dapat diakses TANPA auth header)
    r_pub_404 = client.get("/api/v1/publications/sih3/latest.json")
    assert r_pub_404.status_code == 404

    # 4. Jalankan workflow via API: APPROVE -> PUBLISH
    r_app = client.post(
        "/api/v1/publications/sih3/workflow",
        headers=auth_headers,
        json={"period_id": TEST_PERIOD_ID, "action": "APPROVE", "operator": "klimatkepri"},
    )
    assert r_app.status_code == 200
    assert r_app.json()["workflow_status"] == "APPROVED"

    r_pub = client.post(
        "/api/v1/publications/sih3/publish",
        headers=auth_headers,
        json={"period_id": TEST_PERIOD_ID, "action": "PUBLISH", "operator": "klimatkepri"},
    )
    assert r_pub.status_code == 200
    assert r_pub.json()["workflow_status"] == "PUBLISHED"

    # 5. Akses endpoint publik TANPA token autentikasi (seperti WordPress SIH3 client)
    r_latest = client.get("/api/v1/publications/sih3/latest.json")
    assert r_latest.status_code == 200
    latest_payload = r_latest.json()
    assert latest_payload["publication"]["status"] == "PUBLISHED"
    assert len(latest_payload["regions"]) == 7
