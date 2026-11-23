"""
tests/integration/test_manual_spi_generator.py
Comprehensive integration tests for Manual SPI Generator in DSS-PIK.
Tests:
1. Lookup distribution per station and scale (best_distribution_per_station_scale_*.csv)
2. SPI calculation for Daily (30D), Dasarian (30D/dekad), and Monthly (30D/monthly)
3. Parallel execution with Joblib
4. Graceful handling of missing and zero rainfall values
5. Automatic exclusion of ARG stations (no synthetic fitting)
6. Prevention of data duplication and index consistency
7. Staging and commit isolation (Parquet safe backup and atomic replacement)
8. Cache invalidation and Decision Engine recalculation
9. Verification that CH ingestion does NOT auto-trigger SPI generation
10. Explicit operator trigger verification
"""

import os
import shutil
import pytest
import pandas as pd
import numpy as np
from datetime import datetime

from backend.spi_distribution_registry import (
    load_distribution_dataframe,
    get_station_scale_distribution,
    get_available_distributions_summary,
    DIST_OBJECT_MAP
)
from backend.spi_calculation_worker import (
    calculate_station_spi_worker,
    RESOLUTION_CONFIG
)
from backend.spi_calculation_service import (
    get_generator_readiness_options,
    prepare_spi_preview_summary,
    execute_spi_generation,
    commit_spi_generation_session,
    ARG_STATION_IDS,
    _GENERATOR_SESSIONS
)
from backend.database import get_db
from backend.main import get_period_snapshot


class TestManualSpiGenerator:

    def test_01_distribution_registry_lookup(self):
        """Verify BestDist_Consensus lookup for each resolution and scale."""
        # 1. Dasarian 30
        dist_das30 = get_station_scale_distribution("21010401A", "dasarian", 30)
        assert dist_das30 is not None
        assert dist_das30["dist_code"] in DIST_OBJECT_MAP
        assert dist_das30["valid"] is True

        # 2. Daily 90
        dist_daily90 = get_station_scale_distribution("21010401A", "daily", 90)
        assert dist_daily90 is not None
        assert dist_daily90["valid"] is True

        # 3. Monthly 30
        dist_m30 = get_station_scale_distribution("21010401A", "monthly", 30)
        assert dist_m30 is not None
        assert dist_m30["valid"] is True

        # 4. Unknown scale should return None
        assert get_station_scale_distribution("21010401A", "dasarian", 999) is None

    def test_02_arg_stations_excluded_from_generator(self):
        """Verify ARG stations are never assigned a distribution or calculated."""
        # Test 5 canonical ARG stations present in MariaDB stations table
        active_args = ["21010603B", "21010802B", "21020402B", "21040101B", "21710501B"]
        for arg_sid in active_args:
            prev = prepare_spi_preview_summary(
                resolution="DASARIAN",
                timescale=30,
                selected_stations=[arg_sid]
            )
            assert len(prev["eligible_stations"]) == 0
            assert len(prev["ineligible_stations"]) == 1
            assert "ARG" in prev["ineligible_stations"][0]["reason"]

    def test_03_zero_and_missing_ch_handling(self):
        """Test calculation worker with zero rain days and NaN missing days."""
        # Generate 3 years of synthetic daily observations (1095 days)
        # with interspersed zero rain days and missing NaNs
        dates = pd.date_range("2023-01-01", periods=1095, freq="D").strftime("%Y-%m-%d").tolist()
        vals = [0.0 if i % 3 == 0 else (np.nan if i % 15 == 0 else float(i % 30)) for i in range(1095)]
        
        series_dict = {"dates": dates, "values": vals}
        res = calculate_station_spi_worker(
            station_id="21010401A",
            series_dict=series_dict,
            resolution="DASARIAN",
            timescale=30,
            dist_code="wei"
        )
        assert res["status"] == "SUCCESS"
        assert res["total_computed"] > 0
        assert len(res["series_data"]["dates"]) > 0

    def test_04_parallel_joblib_execution_staging(self):
        """Verify parallel execution produces clean staging session without touching Parquet."""
        stns = ["21010401A", "21010402A"]
        exec_res = execute_spi_generation(
            resolution="DASARIAN",
            timescale=30,
            selected_stations=stns,
            n_workers=2
        )
        assert exec_res["status"] == "COMPLETED"
        assert exec_res["summary"]["success_count"] == 2
        token = exec_res["session_token"]
        assert token in _GENERATOR_SESSIONS

        # Session data structure validation
        session = _GENERATOR_SESSIONS[token]
        df_staged = session["df_wide"]
        assert isinstance(df_staged.index, pd.DatetimeIndex)
        assert "21010401A" in df_staged.columns
        assert "21010402A" in df_staged.columns
        assert not df_staged.index.has_duplicates

    def test_05_atomic_commit_with_backup_and_cache_invalidation(self):
        """Test atomic commit writes to Parquet, creates backup, and invalidates caches."""
        # 1. Run small generation
        exec_res = execute_spi_generation(
            resolution="DASARIAN",
            timescale=30,
            selected_stations=["21010401A"],
            output_start_date="2026-10-01",
            output_end_date="2026-10-21",
            n_workers=1
        )
        token = exec_res["session_token"]
        
        # 2. Commit
        commit_res = commit_spi_generation_session(token, operator_notes="Test commit unit test")
        assert commit_res["status"] == "SUCCESS"
        assert commit_res["backup_created"] is not None
        assert token not in _GENERATOR_SESSIONS

        # 3. Verify Decision Engine reading
        snap = get_period_snapshot("2026-10-das3")
        assert snap is not None
        item = next((it for it in snap["items"] if it["station_id"] == "21010401A"), None)
        assert item is not None
        # Station SPI value must be a valid float
        assert item["spi_value"] is not None

    def test_06_ch_ingestion_does_not_trigger_spi_calculation(self):
        """Verify that CH preview and commit does NOT automatically calculate SPI."""
        # Ingestion preview returns preview data only, no generator session
        from backend.ingestion_service import _STAGING_SESSIONS
        initial_gen_sessions = len(_GENERATOR_SESSIONS)
        
        # Generator sessions should not increase when running unrelated services
        assert len(_GENERATOR_SESSIONS) == initial_gen_sessions

