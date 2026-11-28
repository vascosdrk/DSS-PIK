"""
tests/integration/test_phase1_forecast_schema_integrity.py

Phase 1 — Database & Data Integrity integration test suite for
DSS-PIK ECMWF Multi-Vintage & ENSMEAN schema.

All write/constraint tests run inside explicit uncommitted transactions
(autocommit=False + rollback() in finally) so zero test rows pollute
operational local data in `cews_db_migration_test`.
"""

from pathlib import Path
import pymysql
import pytest

from backend.database import get_db, get_raw_connection

MIGRATION_1 = Path("database/migrations/20261127_add_forecast_deterministic_snapshot.sql")
MIGRATION_2 = Path("database/migrations/20261127_harden_forecast_snapshot_indexes.sql")


def _execute_sql_file(sql_path: Path) -> None:
    sql_text = sql_path.read_text(encoding="utf-8")
    statements = [s.strip() for s in sql_text.split(";") if s.strip() and not all(
        line.strip().startswith("--") or line.strip() == "" for line in s.splitlines()
    )]
    with get_db() as conn:
        with conn.cursor() as cur:
            for stmt in statements:
                cur.execute(stmt)
        conn.commit()


def _get_valid_station_id() -> str:
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT station_id FROM stations ORDER BY station_id LIMIT 1")
            row = cur.fetchone()
            assert row is not None, "Master stations table must not be empty"
            return row["station_id"]


def test_01_deterministic_table_exists_and_matches_master_collation():
    """Verify table existence, engine, and exact station_id type & collation parity with stations."""
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("SHOW FULL COLUMNS FROM stations WHERE Field = 'station_id'")
            master_col = cur.fetchone()
            cur.execute("SHOW FULL COLUMNS FROM cews_forecast_deterministic_snapshot WHERE Field = 'station_id'")
            det_col = cur.fetchone()

    assert det_col is not None, "cews_forecast_deterministic_snapshot.station_id must exist"
    assert det_col["Type"] == master_col["Type"] == "varchar(20)"
    assert det_col["Collation"] == master_col["Collation"] == "utf8mb4_unicode_ci"
    assert det_col["Null"] == "NO"


def test_02_required_columns_indexes_and_constraints_present():
    """Verify all required audit/soft-void/reactivation columns, unique key, FK, and indexes exist."""
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("SHOW COLUMNS FROM cews_forecast_deterministic_snapshot")
            det_cols = {r["Field"] for r in cur.fetchall()}

            cur.execute("SHOW INDEX FROM cews_forecast_deterministic_snapshot")
            det_indexes = {r["Key_name"] for r in cur.fetchall()}

            cur.execute("SHOW COLUMNS FROM cews_forecast_snapshot")
            prob_cols = {r["Field"]: r for r in cur.fetchall()}

            cur.execute("SHOW INDEX FROM cews_forecast_snapshot")
            prob_indexes = {r["Key_name"] for r in cur.fetchall()}

    expected_det_cols = {
        "id", "station_id", "forecast_resolution", "issue_date",
        "target_year", "target_month", "target_dasarian", "forecast_variable",
        "value_mm", "unit", "adjustment_status", "source_file", "source_sheet",
        "source_column", "release_group_id", "ingestion_batch_id",
        "is_voided", "void_reason", "voided_by", "voided_at",
        "reactivation_count", "reactivated_at", "created_at", "updated_at",
    }
    assert expected_det_cols.issubset(det_cols)

    expected_det_indexes = {
        "PRIMARY",
        "uq_det_forecast_vintage",
        "idx_det_res_target_issue",
        "idx_det_vintage_batch",
        "idx_det_station_target",
        "idx_det_active_lookup",
    }
    assert expected_det_indexes.issubset(det_indexes)

    # Hardened cews_forecast_snapshot checks
    assert "release_group_id" in prob_cols
    assert "ingestion_batch_id" in prob_cols
    assert prob_cols["source_file"]["Type"] == "varchar(255)"
    assert "uq_forecast_evidence" in prob_indexes
    assert "idx_fc_res_target_issue" in prob_indexes


def test_03_migrations_are_strictly_idempotent():
    """Re-running both migrations must succeed without errors or data alteration."""
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) AS cnt, SUM(probability_value) AS sm FROM cews_forecast_snapshot")
            before = cur.fetchone()

    _execute_sql_file(MIGRATION_1)
    _execute_sql_file(MIGRATION_2)

    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) AS cnt, SUM(probability_value) AS sm FROM cews_forecast_snapshot")
            after = cur.fetchone()

    assert after["cnt"] == before["cnt"]
    assert after["sm"] == before["sm"]


def test_04_foreign_key_and_check_constraints_enforced():
    """Verify FK rejects invalid station_id and CHECK constraints reject negative mm, bad resolution, bad adjustment."""
    valid_sid = _get_valid_station_id()
    base_sql = """
        INSERT INTO cews_forecast_deterministic_snapshot
        (station_id, forecast_resolution, issue_date, target_year, target_month, target_dasarian,
         forecast_variable, value_mm, adjustment_status, source_file, source_sheet, source_column)
        VALUES (%s, %s, %s, %s, %s, %s, 'ENSMEAN', %s, %s, 'test_phase1.xlsx', 'EnsMean', 'Nov Adjust')
    """
    conn = get_raw_connection()
    conn.autocommit(False)
    conn.begin()
    try:
        with conn.cursor() as cur:
            # 1. Invalid station_id -> FK violation
            with pytest.raises(pymysql.IntegrityError):
                cur.execute(base_sql, ("INVALID_STN_999", "DASARIAN", "2026-11-17", 2026, 11, 3, 45.20, "REGULAR"))

            # 2. Negative value_mm -> CHECK chk_det_val_nonneg violation
            with pytest.raises(pymysql.OperationalError):
                cur.execute(base_sql, (valid_sid, "DASARIAN", "2026-11-17", 2026, 11, 3, -0.01, "REGULAR"))

            # 3. Invalid forecast_resolution -> CHECK chk_det_res_valid violation
            with pytest.raises(pymysql.OperationalError):
                cur.execute(base_sql, (valid_sid, "HARIAN", "2026-11-17", 2026, 11, 3, 25.00, "REGULAR"))

            # 4. Invalid adjustment_status -> CHECK chk_det_adj_valid violation
            with pytest.raises(pymysql.OperationalError):
                cur.execute(base_sql, (valid_sid, "BULANAN", "2026-10-01", 2026, 11, 0, 250.50, "NATUNA_ADJ"))
    finally:
        conn.rollback()
        conn.close()


def test_05_unique_key_multivintage_and_reactivation_after_void():
    """Verify multi-vintage inserts (>100 mm allowed), duplicate key rejection, soft-void, and reactivation."""
    valid_sid = _get_valid_station_id()
    ins_sql = """
        INSERT INTO cews_forecast_deterministic_snapshot
        (station_id, forecast_resolution, issue_date, target_year, target_month, target_dasarian,
         forecast_variable, value_mm, adjustment_status, source_file, source_sheet, source_column,
         release_group_id, ingestion_batch_id)
        VALUES (%s, %s, %s, %s, %s, %s, 'ENSMEAN', %s, %s, %s, 'EnsMean', %s, %s, %s)
    """
    conn = get_raw_connection()
    conn.autocommit(False)
    conn.begin()
    try:
        with conn.cursor() as cur:
            # Count probability rows before deterministic writes (isolation check)
            cur.execute("SELECT COUNT(*) AS cnt FROM cews_forecast_snapshot")
            prob_before = cur.fetchone()["cnt"]

            # 1. Insert vintage 1 (value_mm > 100.00 valid for deterministic mm)
            cur.execute(ins_sql, (
                valid_sid, "BULANAN", "2099-10-01", 2099, 11, 0,
                342.75, "ADJUSTED", "KEPRI_ver_2099.10.01.xlsx", "Nov Adjust",
                "ECMWF_BLN_2099-10-01", "BATCH_TEST_1"
            ))

            # 2. Insert vintage 2 for SAME target period -> must succeed (multi-vintage!)
            cur.execute(ins_sql, (
                valid_sid, "BULANAN", "2099-11-01", 2099, 11, 0,
                298.10, "REGULAR", "KEPRI_ver_2099.11.01.xlsx", "Nov",
                "ECMWF_BLN_2099-11-01", "BATCH_TEST_2"
            ))

            # 3. Duplicate same vintage + target + station -> must raise IntegrityError
            with pytest.raises(pymysql.IntegrityError):
                cur.execute(ins_sql, (
                    valid_sid, "BULANAN", "2099-10-01", 2099, 11, 0,
                    310.00, "REGULAR", "KEPRI_ver_2099.10.01.xlsx", "Nov",
                    "ECMWF_BLN_2099-10-01", "BATCH_TEST_DUP"
                ))

            # 4. Soft-void vintage 1
            cur.execute("""
                UPDATE cews_forecast_deterministic_snapshot
                SET is_voided = 1, void_reason = 'Uji void fase 1', voided_by = 'PYTEST', voided_at = CURRENT_TIMESTAMP
                WHERE station_id = %s AND forecast_resolution = 'BULANAN'
                  AND issue_date = '2099-10-01' AND target_year = 2099 AND target_month = 11 AND target_dasarian = 0
            """, (valid_sid,))
            assert cur.rowcount == 1

            # Active query must only see vintage 2
            cur.execute("""
                SELECT issue_date FROM cews_forecast_deterministic_snapshot
                WHERE station_id = %s AND forecast_resolution = 'BULANAN'
                  AND target_year = 2099 AND target_month = 11 AND target_dasarian = 0
                  AND is_voided = 0
            """, (valid_sid,))
            active_rows = cur.fetchall()
            assert len(active_rows) == 1
            assert str(active_rows[0]["issue_date"]) == "2099-11-01"

            # 5. Reactivation after void via ON DUPLICATE KEY UPDATE without duplicate key error
            cur.execute("""
                INSERT INTO cews_forecast_deterministic_snapshot
                (station_id, forecast_resolution, issue_date, target_year, target_month, target_dasarian,
                 forecast_variable, value_mm, adjustment_status, source_file, source_sheet, source_column,
                 release_group_id, ingestion_batch_id)
                VALUES (%s, 'BULANAN', '2099-10-01', 2099, 11, 0, 'ENSMEAN', 350.00, 'ADJUSTED',
                        'KEPRI_ver_2099.10.01.xlsx', 'EnsMean', 'Nov Adjust', 'ECMWF_BLN_2099-10-01', 'BATCH_REACT')
                ON DUPLICATE KEY UPDATE
                    value_mm = VALUES(value_mm),
                    adjustment_status = VALUES(adjustment_status),
                    source_column = VALUES(source_column),
                    ingestion_batch_id = VALUES(ingestion_batch_id),
                    is_voided = 0,
                    void_reason = NULL,
                    voided_by = NULL,
                    voided_at = NULL,
                    reactivation_count = reactivation_count + 1,
                    reactivated_at = CURRENT_TIMESTAMP
            """, (valid_sid,))

            cur.execute("""
                SELECT value_mm, is_voided, reactivation_count, reactivated_at
                FROM cews_forecast_deterministic_snapshot
                WHERE station_id = %s AND forecast_resolution = 'BULANAN'
                  AND issue_date = '2099-10-01' AND target_year = 2099 AND target_month = 11 AND target_dasarian = 0
            """, (valid_sid,))
            react_row = cur.fetchone()
            assert float(react_row["value_mm"]) == 350.00
            assert react_row["is_voided"] == 0
            assert react_row["reactivation_count"] == 1
            assert react_row["reactivated_at"] is not None

            # Verify cews_forecast_snapshot remained 100% isolated & untouched
            cur.execute("SELECT COUNT(*) AS cnt FROM cews_forecast_snapshot")
            assert cur.fetchone()["cnt"] == prob_before
    finally:
        conn.rollback()
        conn.close()


def test_06_existing_probability_data_and_legacy_records_preserved():
    """Verify existing probability rows and legacy anomalies remain 100% intact after Phase 1."""
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) AS cnt, MIN(id) AS mn, MAX(id) AS mx FROM cews_forecast_snapshot")
            stats = cur.fetchone()
            cur.execute("""
                SELECT source_file, COUNT(*) AS cnt
                FROM cews_forecast_snapshot
                WHERE source_file IN ('probability_monthly_integrated', 'SAFE_DEFAULT')
                GROUP BY source_file
            """)
            legacy = {r["source_file"]: r["cnt"] for r in cur.fetchall()}

            cur.execute("""
                SELECT COUNT(*) AS det_test_cnt
                FROM cews_forecast_deterministic_snapshot
                WHERE ingestion_batch_id LIKE 'BATCH_TEST_%%' OR ingestion_batch_id = 'BATCH_REACT'
            """)
            det_test_cnt = cur.fetchone()["det_test_cnt"]

    assert stats["cnt"] >= 3244
    assert stats["mn"] == 1
    assert legacy.get("probability_monthly_integrated", 0) == 510
    assert legacy.get("SAFE_DEFAULT", 0) == 40
    # Deterministic table must have 0 leaked test rows
    assert det_test_cnt == 0
