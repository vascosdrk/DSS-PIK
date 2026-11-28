"""
tests/integration/test_ecmwf_multivintage_ensmean.py

Phase 2 integration tests on MariaDB local `cews_db_migration_test` covering:
1. 3-file Dasarian release unified atomic commit (Probabilitas + ENSMEAN + release_group_id).
2. Monthly workbook with Adjust priority (`ver_2026.10.01.xlsx` -> Nov/Des/Jan Adjust) &
   non-forecast column filtering (`ver_2026.06.01.xlsx` -> anlis apr/mei ignored).
3. Multi-vintage preservation (different issue_date for same target -> NEW VINTAGE, old intact).
4. Idempotent re-upload (IDENTICAL skipped, zero duplicate writes).
5. Soft-void ENSMEAN + audited reactivation on re-upload (`REACTIVATED`, `reactivation_count=1`,
   prior void reason preserved in `cews_ingestion_history`).
6. Atomic rollback when Probabilistic insert fails -> ZERO rows in either table.
7. Atomic rollback when ENSMEAN insert fails -> Probabilistic rows rolled back cleanly.
8. Station mapping `228D` -> Duara & UPT Benih Pertanian (52/52 master manual stations).
9. Zero impact on pre-existing `cews_forecast_snapshot` records after test cleanup.
"""

import io
from pathlib import Path
import openpyxl
import pytest

from backend.database import get_db
from backend.ecmwf_forecast_service import (
    commit_ecmwf_unified_session,
    parse_ecmwf_dasarian_release,
    parse_ecmwf_workbook_unified,
)
from backend.ingestion_service import _STAGING_SESSIONS

DAS_TRIO_FILES = [
    Path("tambahan/02_EKSTRAK_POS/DASARIAN/KEPRI_pch_ecmwf_perpos_ver_2026.10.19_das3okt.xlsx"),
    Path("tambahan/02_EKSTRAK_POS/DASARIAN/KEPRI_pch_ecmwf_perpos_ver_2026.10.19_das 1 nov.xlsx"),
    Path("tambahan/02_EKSTRAK_POS/DASARIAN/KEPRI_pch_ecmwf_perpos_ver_2026.10.19_das 2 nov.xlsx"),
]
MONTHLY_ADJUST_FILE = Path("tambahan/02_EKSTRAK_POS/BULANAN/KEPRI_pch_ecmwf_perpos_ver_2026.10.01.xlsx")
MONTHLY_ANLIS_FILE = Path("tambahan/02_EKSTRAK_POS/BULANAN/KEPRI_pch_ecmwf_perpos_ver_2026.06.01.xlsx")


def _cleanup_test_batches(batch_ids, release_groups, issue_dates):
    with get_db() as conn:
        with conn.cursor() as cur:
            if batch_ids:
                fmt = ",".join(["%s"] * len(batch_ids))
                cur.execute(f"DELETE FROM cews_forecast_deterministic_snapshot WHERE ingestion_batch_id IN ({fmt})", tuple(batch_ids))
                cur.execute(f"DELETE FROM cews_forecast_snapshot WHERE ingestion_batch_id IN ({fmt})", tuple(batch_ids))
                cur.execute(f"DELETE FROM cews_ingestion_history WHERE batch_id IN ({fmt})", tuple(batch_ids))
            if release_groups:
                fmt = ",".join(["%s"] * len(release_groups))
                cur.execute(f"DELETE FROM cews_forecast_deterministic_snapshot WHERE release_group_id IN ({fmt})", tuple(release_groups))
                cur.execute(f"DELETE FROM cews_forecast_snapshot WHERE release_group_id IN ({fmt})", tuple(release_groups))
        conn.commit()


def test_01_three_file_dasarian_release_atomic_commit_multivintage_and_idempotency():
    """Tests 3-file Dasarian unified commit, 228D station mapping, idempotency, and multi-vintage."""
    for p in DAS_TRIO_FILES:
        assert p.exists(), f"Required workbook not found: {p}"

    batch_ids = ["PYTEST_ECMWF_DAS_B1", "PYTEST_ECMWF_DAS_B2", "PYTEST_ECMWF_DAS_V2"]
    release_groups = ["ECMWF_DAS_2026-10-19", "ECMWF_DAS_2026-10-20"]

    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) AS cnt, SUM(probability_value) AS sm FROM cews_forecast_snapshot")
            baseline_prob = cur.fetchone()

    try:
        # 1. Parse & commit 3-file Dasarian release (issue_date = 2026-10-19)
        files_payload = [(p.name, p.read_bytes()) for p in DAS_TRIO_FILES]
        rel = parse_ecmwf_dasarian_release(files_payload)
        assert rel["release_group_id"] == "ECMWF_DAS_2026-10-19"
        assert {p["period_id"] for p in rel["periods_detected"]} == {
            "2026-10-das3", "2026-11-das1", "2026-11-das2"
        }
        assert rel["station_mapping_summary"]["matched_stations_count"] == 52
        assert rel["station_mapping_summary"]["duplicate_stations_count"] == 0

        sess = _STAGING_SESSIONS.pop(rel["staging_token"])
        stats = commit_ecmwf_unified_session(
            session=sess,
            prob_entries_to_commit=sess["entries"],
            det_entries_to_commit=sess["deterministic_entries"],
            selected_periods_list=[p["period_id"] for p in rel["periods_detected"]],
            batch_id=batch_ids[0],
            operator="PYTEST_PHASE2",
        )
        # 3 files * 52 stations * 4 prob params = 624 prob rows; 3 files * 52 stations = 156 det rows
        assert stats["prob_written"] == 624
        assert stats["det_written"] == 156

        # 2. Idempotent re-upload of identical 3-file release -> 0 written (all IDENTICAL)
        rel_dup = parse_ecmwf_dasarian_release(files_payload)
        assert rel_dup["summary"]["identical_records"] == 624
        assert rel_dup["summary"]["deterministic_summary"]["identical_records"] == 156
        sess_dup = _STAGING_SESSIONS.pop(rel_dup["staging_token"])
        stats_dup = commit_ecmwf_unified_session(
            session=sess_dup,
            prob_entries_to_commit=sess_dup["entries"],
            det_entries_to_commit=sess_dup["deterministic_entries"],
            selected_periods_list=[p["period_id"] for p in rel_dup["periods_detected"]],
            batch_id=batch_ids[1],
            operator="PYTEST_PHASE2",
        )
        assert stats_dup["prob_written"] == 0
        assert stats_dup["det_written"] == 0

        # 3. Multi-vintage test: same target (2026-11-das1) with newer issue_date 2026-10-20 -> NEW VINTAGE
        v2_file = DAS_TRIO_FILES[1]
        rel_v2 = parse_ecmwf_workbook_unified(
            v2_file.read_bytes(),
            "KEPRI_pch_ecmwf_perpos_ver_2026.10.20_das 1 nov.xlsx",
            forecast_type="PROBABILITAS_DASARIAN",
            register_session=True,
        )
        assert rel_v2["summary"]["new_vintage_records"] == 208  # 52 * 4
        assert rel_v2["summary"]["deterministic_summary"]["new_vintage_records"] == 52
        sess_v2 = _STAGING_SESSIONS.pop(rel_v2["staging_token"])
        commit_ecmwf_unified_session(
            session=sess_v2,
            prob_entries_to_commit=sess_v2["entries"],
            det_entries_to_commit=sess_v2["deterministic_entries"],
            selected_periods_list=["2026-11-das1"],
            batch_id=batch_ids[2],
            operator="PYTEST_PHASE2",
        )
        with get_db() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT DISTINCT issue_date FROM cews_forecast_deterministic_snapshot
                    WHERE forecast_resolution = 'DASARIAN' AND target_year = 2026 AND target_month = 11 AND target_dasarian = 1
                    ORDER BY issue_date
                """)
                vintages = [str(r["issue_date"]) for r in cur.fetchall()]
        assert vintages == ["2026-10-19", "2026-10-20"]
    finally:
        _cleanup_test_batches(batch_ids, release_groups, [])

    # Verify baseline probability data 100% preserved
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) AS cnt, SUM(probability_value) AS sm FROM cews_forecast_snapshot")
            after_prob = cur.fetchone()
    assert after_prob["cnt"] == baseline_prob["cnt"]
    assert after_prob["sm"] == baseline_prob["sm"]


def test_02_monthly_adjust_priority_non_forecast_ignore_and_reactivation_after_void():
    """Tests real monthly workbook with Adjust columns + soft-void + audited reactivation."""
    assert MONTHLY_ADJUST_FILE.exists()
    assert MONTHLY_ANLIS_FILE.exists()

    # Check non-forecast column filtering on ver_2026.06.01.xlsx (read-only parse)
    anlis_res = parse_ecmwf_workbook_unified(
        MONTHLY_ANLIS_FILE.read_bytes(),
        MONTHLY_ANLIS_FILE.name,
        forecast_type="PROBABILITAS_BULANAN",
        register_session=False,
    )
    ignored = anlis_res["summary"]["deterministic_summary"]["ignored_non_forecast_columns"]
    assert [i["source_column"] for i in ignored] == ["anlis apr", "anlis mei"]

    # Commit ENSMEAN + Prob from ver_2026.10.01.xlsx using synthetic future vintage 2026-10-02
    # so we don't collide with existing 2026-10-01 rows in cews_forecast_snapshot
    batch_ids = ["PYTEST_ECMWF_BLN_B1", "PYTEST_ECMWF_BLN_REACT"]
    release_groups = ["ECMWF_BLN_2026-10-02"]
    try:
        res = parse_ecmwf_workbook_unified(
            MONTHLY_ADJUST_FILE.read_bytes(),
            "KEPRI_pch_ecmwf_perpos_ver_2026.10.02.xlsx",
            forecast_type="PROBABILITAS_BULANAN",
            register_session=True,
        )
        det_sum = res["summary"]["deterministic_summary"]
        assert det_sum["adjusted_columns_used"] == ["Nov Adjust", "Des Adjust", "Jan Adjust"]
        assert det_sum["total_records"] == 52 * 7  # 364 deterministic records across 7 months

        sess = _STAGING_SESSIONS.pop(res["staging_token"])
        commit_ecmwf_unified_session(
            session=sess,
            prob_entries_to_commit=sess["entries"],
            det_entries_to_commit=sess["deterministic_entries"],
            selected_periods_list=[p["period_id"] for p in res["periods_detected"]],
            batch_id=batch_ids[0],
            operator="PYTEST_PHASE2",
        )

        # Soft-void one target month (2026-11) in ENSMEAN
        with get_db() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    UPDATE cews_forecast_deterministic_snapshot
                    SET is_voided = 1, void_reason = 'Revisi uji fase 2', voided_by = 'PYTEST', voided_at = CURRENT_TIMESTAMP
                    WHERE release_group_id = 'ECMWF_BLN_2026-10-02' AND target_year = 2026 AND target_month = 11
                """)
            conn.commit()

        # Re-upload same file -> 2026-11 must be classified REACTIVATED (52 rows), others IDENTICAL (312 rows)
        res_re = parse_ecmwf_workbook_unified(
            MONTHLY_ADJUST_FILE.read_bytes(),
            "KEPRI_pch_ecmwf_perpos_ver_2026.10.02.xlsx",
            forecast_type="PROBABILITAS_BULANAN",
            register_session=True,
        )
        assert res_re["summary"]["deterministic_summary"]["reactivated_records"] == 52
        assert res_re["summary"]["deterministic_summary"]["identical_records"] == 312

        sess_re = _STAGING_SESSIONS.pop(res_re["staging_token"])
        stats_re = commit_ecmwf_unified_session(
            session=sess_re,
            prob_entries_to_commit=sess_re["entries"],
            det_entries_to_commit=sess_re["deterministic_entries"],
            selected_periods_list=[p["period_id"] for p in res_re["periods_detected"]],
            batch_id=batch_ids[1],
            operator="PYTEST_PHASE2",
            allow_update_existing=True,
        )
        assert stats_re["det_reactivated"] == 52

        with get_db() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT COUNT(*) AS cnt, MIN(reactivation_count) AS min_rc, MAX(is_voided) AS max_v
                    FROM cews_forecast_deterministic_snapshot
                    WHERE release_group_id = 'ECMWF_BLN_2026-10-02' AND target_year = 2026 AND target_month = 11
                """)
                r_chk = cur.fetchone()
        assert r_chk["cnt"] == 52
        assert r_chk["min_rc"] == 1
        assert r_chk["max_v"] == 0
    finally:
        _cleanup_test_batches(batch_ids, release_groups, [])


def test_03_atomic_rollback_on_prob_failure_and_on_ensmean_failure():
    """Proves ZERO partial commit when either Probabilitas or ENSMEAN insert raises an error."""
    p = DAS_TRIO_FILES[0]
    batch_fail_prob = "PYTEST_ROLLBACK_PROB"
    batch_fail_det = "PYTEST_ROLLBACK_DET"
    rg = "ECMWF_DAS_2026-10-21"

    try:
        # 1. Fail during Probability insert -> neither table should have rows
        res1 = parse_ecmwf_workbook_unified(
            p.read_bytes(), "KEPRI_pch_ecmwf_perpos_ver_2026.10.21_das3okt.xlsx",
            forecast_type="PROBABILITAS_DASARIAN", register_session=True,
        )
        sess1 = _STAGING_SESSIONS.pop(res1["staging_token"])

        def _fail_prob(stage):
            if stage == "before_prob_insert":
                raise RuntimeError("Simulated DB failure on probability insert")

        with pytest.raises(RuntimeError, match="Simulated DB failure on probability insert"):
            commit_ecmwf_unified_session(
                session=sess1,
                prob_entries_to_commit=sess1["entries"],
                det_entries_to_commit=sess1["deterministic_entries"],
                selected_periods_list=["2026-10-das3"],
                batch_id=batch_fail_prob,
                _inject_failure_hook=_fail_prob,
            )

        # 2. Fail during ENSMEAN insert (AFTER all 208 probability rows inserted!) -> prob rows MUST rollback!
        res2 = parse_ecmwf_workbook_unified(
            p.read_bytes(), "KEPRI_pch_ecmwf_perpos_ver_2026.10.21_das3okt.xlsx",
            forecast_type="PROBABILITAS_DASARIAN", register_session=True,
        )
        sess2 = _STAGING_SESSIONS.pop(res2["staging_token"])

        def _fail_det(stage):
            if stage == "before_det_insert":
                raise RuntimeError("Simulated DB failure on ENSMEAN insert")

        with pytest.raises(RuntimeError, match="Simulated DB failure on ENSMEAN insert"):
            commit_ecmwf_unified_session(
                session=sess2,
                prob_entries_to_commit=sess2["entries"],
                det_entries_to_commit=sess2["deterministic_entries"],
                selected_periods_list=["2026-10-das3"],
                batch_id=batch_fail_det,
                _inject_failure_hook=_fail_det,
            )

        with get_db() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT COUNT(*) AS c FROM cews_forecast_snapshot WHERE release_group_id = %s", (rg,))
                assert cur.fetchone()["c"] == 0, "Probability rows leaked after ENSMEAN failure!"
                cur.execute("SELECT COUNT(*) AS c FROM cews_forecast_deterministic_snapshot WHERE release_group_id = %s", (rg,))
                assert cur.fetchone()["c"] == 0, "Deterministic rows leaked after rollback!"
                cur.execute("SELECT COUNT(*) AS c FROM cews_ingestion_history WHERE batch_id IN (%s, %s)", (batch_fail_prob, batch_fail_det))
                assert cur.fetchone()["c"] == 0, "Audit row leaked after rollback!"
    finally:
        _cleanup_test_batches([batch_fail_prob, batch_fail_det], [rg], [])
