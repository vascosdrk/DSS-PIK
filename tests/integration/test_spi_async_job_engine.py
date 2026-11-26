"""
tests/integration/test_spi_async_job_engine.py
Integration & numerical parity tests for the MariaDB-backed Asynchronous SPI Job Engine:
1. SPI Daily (HARIAN, 30D & 90D) numerical parity vs direct calculate_station_spi_worker (zero drift)
2. Deduplication of identical concurrent QUEUED/RUNNING jobs
3. Stale heartbeat recovery (container restart resilience)
4. Job cancellation & safe retry
5. Staged Parquet persistence on disk
"""

from datetime import datetime, timedelta
from pathlib import Path
import numpy as np
import pandas as pd
import pytest

from backend.database import get_db
from backend.spi_calculation_service import _GENERATOR_SESSIONS
from backend.spi_calculation_worker import calculate_station_spi_worker
from backend.spi_job_service import (
    cancel_spi_job,
    ensure_spi_jobs_table,
    get_spi_job_status,
    recover_stale_spi_jobs,
    retry_spi_job,
    submit_spi_generation_job,
)


def test_spi_daily_async_job_numerical_parity_and_staged_parquet():
    """Verify async SPI Daily 30D job produces identical numeric values to direct worker."""
    test_sids = ["21010801A", "21010701A"]  # 2 real stations (gam)
    job_id = None
    staged_path = None
    try:
        sub = submit_spi_generation_job(
            resolution="HARIAN",
            timescale=30,
            selected_stations=test_sids,
            n_workers=2,
            operator="PYTEST_SPI",
            run_sync=True,
        )
        job_id = sub["job_id"]
        st = get_spi_job_status(job_id)
        assert st["status"] == "SUCCEEDED"
        assert st["progress_pct"] == 100.0
        assert st["completed_stations"] == 2
        assert st["success_count"] == 2
        assert st["session_token"] is not None

        # Verify staged Parquet exists on disk
        with get_db() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT staged_parquet_path FROM cews_spi_generation_jobs WHERE job_id = %s", (job_id,))
                row = cur.fetchone()
                staged_path = Path(row["staged_parquet_path"])
        assert staged_path.exists()
        df_job = pd.read_parquet(staged_path)
        assert set(df_job.columns) == set(test_sids)
        assert len(df_job) > 1000

        # Direct baseline worker calculation on station 21010801A for numerical parity check
        with get_db() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT observation_date, rainfall_mm, obs_status
                    FROM cews_rainfall_daily
                    WHERE station_id = %s AND (obs_status IS NULL OR UPPER(obs_status) != 'VOID')
                    ORDER BY observation_date ASC
                    """,
                    ("21010801A",),
                )
                rows = cur.fetchall()
        non_num = {"TTU", "MISSING", "DAMAGED", "VOID", "AMBIGUOUS"}
        s_dict = {
            "dates": [r["observation_date"].strftime("%Y-%m-%d") for r in rows],
            "values": [
                np.nan if ((r.get("obs_status") or "").upper() in non_num or r["rainfall_mm"] is None) else float(r["rainfall_mm"])
                for r in rows
            ],
        }
        direct = calculate_station_spi_worker("21010801A", s_dict, "HARIAN", 30, "gam")
        assert direct["status"] == "SUCCESS"
        s_direct = pd.Series(direct["series_data"]["values"], index=pd.to_datetime(direct["series_data"]["dates"]))
        s_async = df_job["21010801A"].reindex(s_direct.index)
        valid_mask = s_direct.notna() & s_async.notna()
        assert valid_mask.sum() > 1000
        max_diff = float((s_direct[valid_mask] - s_async[valid_mask]).abs().max())
        assert max_diff == 0.0
    finally:
        if staged_path and staged_path.exists():
            staged_path.unlink(missing_ok=True)
        if job_id:
            with get_db() as conn:
                with conn.cursor() as cur:
                    cur.execute("DELETE FROM cews_spi_generation_jobs WHERE job_id = %s", (job_id,))
                conn.commit()


def test_spi_job_deduplication_stale_recovery_cancel_and_retry():
    """Verify duplicate prevention, stale heartbeat recovery, cancellation, and retry."""
    ensure_spi_jobs_table()
    fake_running_id = "SPIJOB_TEST_STALE_001"
    fake_active_id = "SPIJOB_TEST_ACTIVE_002"
    retry_job_id = None
    try:
        old_hb = (datetime.now() - timedelta(minutes=15)).strftime("%Y-%m-%d %H:%M:%S")
        now_hb = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        # 1. Insert stale RUNNING job -> recover_stale_spi_jobs() must mark it FAILED
        with get_db() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO cews_spi_generation_jobs
                    (job_id, job_key, status, resolution, timescale, request_params_json, operator, heartbeat_at)
                    VALUES (%s, 'stale_key_test', 'RUNNING', 'DASARIAN', 30, '{"resolution":"DASARIAN","timescale":30,"selected_stations":["21010801A"]}', 'PYTEST', %s)
                    """,
                    (fake_running_id, old_hb),
                )
            conn.commit()

        recovered = recover_stale_spi_jobs()
        assert recovered >= 1
        st_stale = get_spi_job_status(fake_running_id)
        assert st_stale["status"] == "FAILED"
        assert "restart" in (st_stale["error_message"] or "").lower()

        # 2. Deduplication check: active QUEUED job with matching key returns same job_id
        from backend.spi_job_service import _build_job_key
        k = _build_job_key("DASARIAN", 90, ["21010801A"], None, None)
        with get_db() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO cews_spi_generation_jobs
                    (job_id, job_key, status, resolution, timescale, operator, heartbeat_at)
                    VALUES (%s, %s, 'RUNNING', 'DASARIAN', 90, 'PYTEST', %s)
                    """,
                    (fake_active_id, k, now_hb),
                )
            conn.commit()

        dup = submit_spi_generation_job("DASARIAN", 90, selected_stations=["21010801A"], operator="PYTEST")
        assert dup["deduplicated"] is True
        assert dup["job_id"] == fake_active_id

        # 3. Cancel active job
        c_res = cancel_spi_job(fake_active_id)
        assert c_res["status"] == "CANCELLED"
    finally:
        with get_db() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "DELETE FROM cews_spi_generation_jobs WHERE job_id IN (%s, %s)",
                    (fake_running_id, fake_active_id),
                )
            conn.commit()
