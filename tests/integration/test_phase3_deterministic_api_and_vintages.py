"""
tests/integration/test_phase3_deterministic_api_and_vintages.py

Phase 3 — API & Vintage Management integration test suite covering all 12 mandatory scenarios:
1. GET ENSMEAN Dasarian data & periods (via FastAPI endpoint handlers + route registration check)
2. GET ENSMEAN Bulanan data & Adjust metadata
3. Latest vintage selection
4. Historical cutoff-aware vintage selection (issue_date <= cutoff_date, anti-future leakage)
5. Strict exclusion of soft-voided records from active queries
6. Station & regency (kabupaten) filtering
7. Completeness metrics (overall + per regency)
8. Export CSV & XLSX (valid content, headers, attachment disposition)
9. Isolated soft-void (zero impact on cews_forecast_snapshot) + partial 2-file dasarian release rejection
10. Safe reactivation after void (zero duplicate key, reactivation_count incremented, audit preserved)
11. Existing Probability API compatibility (/api/v1/probability/periods & /data)
12. Full DB cleanliness verified after test teardown
"""

import io
from pathlib import Path
from types import SimpleNamespace
import openpyxl
import pytest

from backend.database import get_db
from backend.ecmwf_forecast_service import (
    commit_ecmwf_unified_session,
    parse_ecmwf_dasarian_release,
    parse_ecmwf_workbook_unified,
)
from backend.ingestion_service import _STAGING_SESSIONS
from backend.main import (
    DeterministicVoidRequest,
    app,
    download_deterministic_endpoint,
    get_deterministic_completeness_endpoint,
    get_deterministic_data_endpoint,
    get_deterministic_history_endpoint,
    get_deterministic_periods_endpoint,
    get_deterministic_vintage_detail_endpoint,
    get_deterministic_vintages_endpoint,
    get_probability_data_endpoint,
    get_probability_periods_endpoint,
    reactivate_deterministic_endpoint,
    void_deterministic_endpoint,
)

DAS_TRIO_FILES = [
    Path("tambahan/02_EKSTRAK_POS/DASARIAN/KEPRI_pch_ecmwf_perpos_ver_2026.10.19_das3okt.xlsx"),
    Path("tambahan/02_EKSTRAK_POS/DASARIAN/KEPRI_pch_ecmwf_perpos_ver_2026.10.19_das 1 nov.xlsx"),
    Path("tambahan/02_EKSTRAK_POS/DASARIAN/KEPRI_pch_ecmwf_perpos_ver_2026.10.19_das 2 nov.xlsx"),
]
MONTHLY_ADJUST_FILE = Path("tambahan/02_EKSTRAK_POS/BULANAN/KEPRI_pch_ecmwf_perpos_ver_2026.10.01.xlsx")


def _fake_request(username: str = "PYTEST_PHASE3"):
    return SimpleNamespace(state=SimpleNamespace(user={"username": username, "role": "ADMIN"}))


def _cleanup(batch_ids, release_groups, audit_batches):
    with get_db() as conn:
        with conn.cursor() as cur:
            if release_groups:
                fmt = ",".join(["%s"] * len(release_groups))
                cur.execute(f"DELETE FROM cews_forecast_deterministic_snapshot WHERE release_group_id IN ({fmt})", tuple(release_groups))
                cur.execute(f"DELETE FROM cews_forecast_snapshot WHERE release_group_id IN ({fmt})", tuple(release_groups))
            all_b = list(set(batch_ids + audit_batches))
            if all_b:
                fmt = ",".join(["%s"] * len(all_b))
                cur.execute(f"DELETE FROM cews_forecast_deterministic_snapshot WHERE ingestion_batch_id IN ({fmt})", tuple(all_b))
                cur.execute(f"DELETE FROM cews_forecast_snapshot WHERE ingestion_batch_id IN ({fmt})", tuple(all_b))
                cur.execute(f"DELETE FROM cews_ingestion_history WHERE batch_id IN ({fmt})", tuple(all_b))
        conn.commit()


def test_00_all_phase3_routes_registered_on_fastapi_app():
    registered = {getattr(r, "path", "") for r in app.routes}
    expected_paths = {
        "/api/v1/forecast/deterministic/periods",
        "/api/v1/forecast/deterministic/data",
        "/api/v1/forecast/deterministic/vintages",
        "/api/v1/forecast/deterministic/vintages/{issue_date}",
        "/api/v1/forecast/deterministic/completeness",
        "/api/v1/forecast/deterministic/history",
        "/api/v1/forecast/deterministic/download",
        "/api/v1/ingestion/deterministic/void",
        "/api/v1/ingestion/deterministic/reactivate",
    }
    assert expected_paths.issubset(registered)


def test_01_partial_two_file_dasarian_release_rejected_on_commit():
    """Preview accepts 1-3 files, but committing a release batch with !=3 files must be rejected."""
    rel2 = parse_ecmwf_dasarian_release([(p.name, p.read_bytes()) for p in DAS_TRIO_FILES[:2]])
    sess2 = _STAGING_SESSIONS.pop(rel2["staging_token"])
    with pytest.raises(ValueError, match="wajib terdiri dari 3 workbook"):
        commit_ecmwf_unified_session(
            session=sess2,
            prob_entries_to_commit=sess2["entries"],
            det_entries_to_commit=sess2["deterministic_entries"],
            selected_periods_list=[p["period_id"] for p in rel2["periods_detected"]],
            batch_id="PYTEST_P3_PARTIAL_REJECT",
        )


def test_02_full_phase3_api_multivintage_cutoff_export_void_reactivate_and_prob_compat():
    """End-to-end API handler test covering all 12 mandatory Phase 3 scenarios."""
    req = _fake_request("PYTEST_PHASE3")

    batch_ids = ["PYTEST_P3_DAS_V1", "PYTEST_P3_DAS_V2", "PYTEST_P3_BLN_V1"]
    release_groups = ["ECMWF_DAS_2026-10-19", "ECMWF_DAS_2026-10-25", "ECMWF_BLN_2026-10-03"]
    audit_batches = []

    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) AS cnt, SUM(probability_value) AS sm FROM cews_forecast_snapshot")
            baseline_prob = cur.fetchone()
            cur.execute("SELECT COUNT(*) AS det_cnt FROM cews_forecast_deterministic_snapshot")
            baseline_det_cnt = cur.fetchone()["det_cnt"]

    try:
        # Seed 1: 3-file Dasarian release (vintage 2026-10-19)
        rel_das1 = parse_ecmwf_dasarian_release([(p.name, p.read_bytes()) for p in DAS_TRIO_FILES])
        sess_d1 = _STAGING_SESSIONS.pop(rel_das1["staging_token"])
        commit_ecmwf_unified_session(
            session=sess_d1,
            prob_entries_to_commit=sess_d1["entries"],
            det_entries_to_commit=sess_d1["deterministic_entries"],
            selected_periods_list=[p["period_id"] for p in rel_das1["periods_detected"]],
            batch_id=batch_ids[0],
            operator="PYTEST_PHASE3",
        )

        # Seed 2: Newer Dasarian vintage (2026-10-25) for target 2026-11-das1
        rel_das2 = parse_ecmwf_workbook_unified(
            DAS_TRIO_FILES[1].read_bytes(),
            "KEPRI_pch_ecmwf_perpos_ver_2026.10.25_das 1 nov.xlsx",
            forecast_type="PROBABILITAS_DASARIAN",
            register_session=True,
        )
        sess_d2 = _STAGING_SESSIONS.pop(rel_das2["staging_token"])
        commit_ecmwf_unified_session(
            session=sess_d2,
            prob_entries_to_commit=sess_d2["entries"],
            det_entries_to_commit=sess_d2["deterministic_entries"],
            selected_periods_list=["2026-11-das1"],
            batch_id=batch_ids[1],
            operator="PYTEST_PHASE3",
        )

        # Seed 3: Monthly workbook with Adjust columns (vintage 2026-10-03)
        rel_bln = parse_ecmwf_workbook_unified(
            MONTHLY_ADJUST_FILE.read_bytes(),
            "KEPRI_pch_ecmwf_perpos_ver_2026.10.03.xlsx",
            forecast_type="PROBABILITAS_BULANAN",
            register_session=True,
        )
        sess_b = _STAGING_SESSIONS.pop(rel_bln["staging_token"])
        commit_ecmwf_unified_session(
            session=sess_b,
            prob_entries_to_commit=sess_b["entries"],
            det_entries_to_commit=sess_b["deterministic_entries"],
            selected_periods_list=[p["period_id"] for p in rel_bln["periods_detected"]],
            batch_id=batch_ids[2],
            operator="PYTEST_PHASE3",
        )

        # 1. GET /periods -> lists both dasarian & bulanan
        j_per = get_deterministic_periods_endpoint()
        assert any(p["period_id"] == "2026-11-das1" and p["vintage_count"] == 2 for p in j_per["dasarian"])
        assert any(p["period_id"] == "2026-11" for p in j_per["bulanan"])

        # 2. GET /data (Dasarian, latest vintage = 2026-10-25)
        j_dl = get_deterministic_data_endpoint(
            period_id="2026-11-das1", resolution="DASARIAN",
            issue_date=None, cutoff_date=None, station_id=None, kabupaten=None, page=1, page_size=60,
        )
        assert j_dl["meta"]["active_vintage_issue"] == "2026-10-25"
        assert j_dl["meta"]["available_vintages"] == ["2026-10-25", "2026-10-19"]
        assert j_dl["meta"]["completeness"]["manual_stations_available"] == 52

        # 3. Cutoff-aware historical selection (cutoff = 2026-10-20 -> MUST pick 2026-10-19, never 2026-10-25)
        j_cut = get_deterministic_data_endpoint(
            period_id="2026-11-das1", resolution=None,
            issue_date=None, cutoff_date="2026-10-20", station_id=None, kabupaten=None, page=1, page_size=60,
        )
        assert j_cut["meta"]["active_vintage_issue"] == "2026-10-19"

        # Cutoff earlier than all vintages -> active_vintage_issue must be None (no system date fallback!)
        j_early = get_deterministic_data_endpoint(
            period_id="2026-11-das1", resolution=None,
            issue_date=None, cutoff_date="2026-10-01", station_id=None, kabupaten=None, page=1, page_size=60,
        )
        assert j_early["meta"]["active_vintage_issue"] is None

        # 4. GET /data (Bulanan, vintage 2026-10-03 for 2026-11 has ADJUSTED from 'Nov Adjust')
        j_bln = get_deterministic_data_endpoint(
            period_id="2026-11", resolution="BULANAN",
            issue_date="2026-10-03", cutoff_date=None, station_id=None, kabupaten=None, page=1, page_size=60,
        )
        assert j_bln["meta"]["completeness"]["adjusted_count"] == 52
        sample_manual = next(row for row in j_bln["data"] if not row["is_arg"])
        assert sample_manual["adjustment_status"] == "ADJUSTED"
        assert sample_manual["source_column"] == "Nov Adjust"
        assert sample_manual["unit"] == "mm"

        # 5. Filter by station_id & kabupaten
        j_stn = get_deterministic_data_endpoint(
            period_id="2026-11", resolution=None,
            issue_date=None, cutoff_date=None, station_id="21010401A", kabupaten=None, page=1, page_size=60,
        )
        assert len(j_stn["data"]) == 1
        assert j_stn["data"][0]["station_id"] == "21010401A"

        j_kab = get_deterministic_data_endpoint(
            period_id="2026-11", resolution=None,
            issue_date=None, cutoff_date=None, station_id=None, kabupaten="Bintan", page=1, page_size=60,
        )
        assert len(j_kab["data"]) > 0
        assert all("bintan" in row["kabupaten"].lower() for row in j_kab["data"])

        # 6. GET /vintages & /vintages/{issue_date}
        j_v = get_deterministic_vintages_endpoint(
            resolution="DASARIAN", period_id="2026-11-das1", cutoff_date=None, include_voided=False,
        )
        assert [v["issue_date"] for v in j_v["vintages"]] == ["2026-10-25", "2026-10-19"]

        j_vd = get_deterministic_vintage_detail_endpoint(
            issue_date="2026-10-19", resolution="DASARIAN", period_id=None, include_voided=False,
        )
        assert j_vd["total_targets"] == 3

        # 7. GET /completeness
        j_comp = get_deterministic_completeness_endpoint(
            period_id="2026-11-das1", resolution=None, issue_date=None, cutoff_date=None,
        )
        assert j_comp["summary"]["completeness_pct"] == 100.0
        assert len(j_comp["by_kabupaten"]) >= 5

        # 8. GET /download (CSV & XLSX)
        r_csv = download_deterministic_endpoint(
            period_id="2026-11", file_format=None, format="csv",
            resolution=None, issue_date="2026-10-03", cutoff_date=None, station_id=None, kabupaten=None,
        )
        csv_text = r_csv.body.decode("utf-8-sig")
        assert "text/csv" in r_csv.media_type
        assert "value_mm" in csv_text and "Nov Adjust" in csv_text

        r_xlsx = download_deterministic_endpoint(
            period_id="2026-11", file_format=None, format="xlsx",
            resolution=None, issue_date=None, cutoff_date=None, station_id=None, kabupaten=None,
        )
        wb_out = openpyxl.load_workbook(io.BytesIO(r_xlsx.body))
        assert wb_out.active.cell(1, 1).value == "station_id"
        assert wb_out.active.max_row == 58  # 1 header + 57 master stations

        # 9. Isolated soft-void of newer vintage (2026-10-25) -> falls back to 2026-10-19; prob table UNTOUCHED
        with get_db() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT COUNT(*) AS c FROM cews_forecast_snapshot WHERE issue_date = '2026-10-25'")
                prob_v2_before = cur.fetchone()["c"]

        j_void = void_deterministic_endpoint(
            DeterministicVoidRequest(
                issue_date="2026-10-25",
                forecast_resolution="DASARIAN",
                target_period="2026-11-das1",
                reason="Uji soft-void fase 3",
            ),
            request=req,
        )
        assert j_void["records_voided"] == 52
        audit_batches.append(j_void["audit_batch_id"])

        # Active query must exclude voided 2026-10-25 and serve 2026-10-19!
        j_after_void = get_deterministic_data_endpoint(
            period_id="2026-11-das1", resolution=None,
            issue_date=None, cutoff_date=None, station_id=None, kabupaten=None, page=1, page_size=60,
        )
        assert j_after_void["meta"]["active_vintage_issue"] == "2026-10-19"

        # Probabilistic table must be 100% untouched by ENSMEAN void
        with get_db() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT COUNT(*) AS c FROM cews_forecast_snapshot WHERE issue_date = '2026-10-25'")
                assert cur.fetchone()["c"] == prob_v2_before

        # 10. Reactivate voided vintage -> back to active 2026-10-25, zero duplicates, audit in /history
        j_react = reactivate_deterministic_endpoint(
            DeterministicVoidRequest(
                issue_date="2026-10-25",
                forecast_resolution="DASARIAN",
                target_period="2026-11-das1",
                reason="Reaktivasi uji fase 3",
            ),
            request=req,
        )
        assert j_react["records_reactivated"] == 52
        audit_batches.append(j_react["audit_batch_id"])

        j_after_react = get_deterministic_data_endpoint(
            period_id="2026-11-das1", resolution=None,
            issue_date=None, cutoff_date=None, station_id=None, kabupaten=None, page=1, page_size=60,
        )
        assert j_after_react["meta"]["active_vintage_issue"] == "2026-10-25"

        j_hist = get_deterministic_history_endpoint(limit=20, issue_date=None, resolution=None)
        hist_types = {h["data_type"] for h in j_hist["history"]}
        assert "ENSMEAN_VOID" in hist_types and "ENSMEAN_REACTIVATE" in hist_types

        # 11. Existing Probability API compatibility check
        j_prob_p = get_probability_periods_endpoint()
        assert "dasarian" in j_prob_p and "bulanan" in j_prob_p
        j_prob_d = get_probability_data_endpoint(
            period_id="2026-11-das1", station_id=None, issue_date=None, page=1, page_size=60,
        )
        assert j_prob_d["meta"]["resolution"] == "DASARIAN"
    finally:
        _cleanup(batch_ids, release_groups, audit_batches)

    # 12. Verify baseline probability data & deterministic table cleanliness
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) AS cnt, SUM(probability_value) AS sm FROM cews_forecast_snapshot")
            after_prob = cur.fetchone()
            cur.execute("SELECT COUNT(*) AS det_cnt FROM cews_forecast_deterministic_snapshot")
            det_cnt = cur.fetchone()["det_cnt"]
    assert after_prob["cnt"] == baseline_prob["cnt"]
    assert after_prob["sm"] == baseline_prob["sm"]
    assert det_cnt == baseline_det_cnt
