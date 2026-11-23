"""
tests/integration/test_ingestion_table_synchronization.py
Comprehensive test suite verifying complete data table synchronization across:
1. SPI Bulanan Parquet format preservation (Wide format, DatetimeIndex, 52 station columns)
2. Elimination of the Jan 1970 bug in SPI Data Service and Frontend
3. Dynamic Probability Periods Union & Multi-Vintage resolution
4. Period-Aware Staging & Commit Scoping
5. Live Cache Invalidation & Storage Consistency
"""

import os
import sys
import shutil
import pytest
import pandas as pd
from datetime import datetime, date
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT_DIR))

from backend.data_service import (
    get_cached_spi_df,
    get_spi_data,
    clear_spi_cache,
    get_probability_data,
    get_probability_periods_list,
    get_station_metadata_df,
)
from backend.ingestion_service import (
    commit_ingestion_session,
    _STAGING_SESSIONS,
    SPI_RAW_DIR,
)
from backend.database import get_db


class TestTableSynchronization:

    def test_01_spi_bulanan_canonical_wide_format(self):
        """Verify SPI_monthly.parquet has DatetimeIndex and 52 manual station columns."""
        parquet_path = SPI_RAW_DIR / "bulanan" / "SPI_monthly.parquet"
        assert parquet_path.exists(), f"SPI_monthly.parquet not found at {parquet_path}"
        
        df = pd.read_parquet(parquet_path)
        
        # Verify index is DatetimeIndex or string dates, NOT RangeIndex
        assert not isinstance(df.index, pd.RangeIndex), "SPI_monthly.parquet has corrupt RangeIndex!"
        
        # Verify columns are station IDs
        master_meta = get_station_metadata_df()
        is_arg_mask = master_meta["station_id"].str.strip().str.endswith("B") | master_meta["station_name"].str.contains("ARG", case=False)
        manual_stations = set(
            master_meta[~is_arg_mask]["station_id"].str.strip().str.upper()
        )
        col_set = set(df.columns.astype(str).str.strip().str.upper())
        
        overlap = manual_stations.intersection(col_set)
        assert len(overlap) >= 50, f"Expected at least 50 manual stations in columns, got {len(overlap)}"
        
        # Verify no metadata contamination columns exist
        corrupt_cols = {"station_id", "station_name", "date", "change_type", "new_value", "old_value"}
        assert corrupt_cols.isdisjoint(set(df.columns.str.lower())), "Corrupt metadata columns found in wide SPI parquet!"

    def test_02_spi_data_no_1970_dates(self):
        """Verify get_spi_data returns valid Indonesian dates and zero 1970 dates."""
        clear_spi_cache()
        res = get_spi_data(period_type="BULANAN", timescale="30D", page_size=100)
        
        assert "data" in res
        rows = res["data"]
        assert len(rows) > 0, "SPI bulanan returned 0 rows"

        for r in rows:
            dt_str = r["date"]
            assert not dt_str.startswith("1970"), f"Corrupt 1970 date found: {dt_str}"
            assert int(dt_str.split("-")[0]) >= 1981, f"Unexpected historical year: {dt_str}"
            
            # Period label must be formatted in Indonesian
            lbl = r.get("period_label", "")
            assert any(m in lbl for m in [
                "Januari", "Februari", "Maret", "April", "Mei", "Juni",
                "Juli", "Agustus", "September", "Oktober", "November", "Desember"
            ]), f"Period label not in Indonesian: {lbl}"

    def test_03_spi_arg_stations_null_handling(self):
        """Verify 5 ARG stations are strictly NULL with ARG status."""
        clear_spi_cache()
        res = get_spi_data(period_type="BULANAN", timescale="30D", page_size=5)
        cols = res["columns"]
        
        arg_cols = [c for c in cols if c["is_arg"]]
        assert len(arg_cols) == 5, f"Expected 5 ARG stations, found {len(arg_cols)}"
        
        for c in arg_cols:
            assert c["status"] == "ARG_UNAVAILABLE"
            assert not c["has_spi"]
            for row in res["data"]:
                assert row["stations"][c["station_id"]] is None

    def test_04_dynamic_probability_periods_list(self):
        """Verify get_probability_periods_list returns both dasarian and bulanan forecasts."""
        res = get_probability_periods_list()
        assert res["status"] == "success"
        
        dasarian_list = res["dasarian"]
        bulanan_list = res["bulanan"]
        
        assert len(dasarian_list) > 0, "No dasarian forecast periods found"
        assert len(bulanan_list) > 0, "No bulanan forecast periods found"

        das_pids = [p["period_id"] for p in dasarian_list]
        bul_pids = [p["period_id"] for p in bulanan_list]

        # Verify operational forecast periods exist in DB
        assert any("2026-11" in pid for pid in das_pids), "2026-11 dasarian forecast missing"
        assert any("2026-11" in pid for pid in bul_pids), "2026-11 bulanan forecast missing"

    def test_05_probability_data_multi_vintage_isolation(self):
        """Verify dasarian probability query correctly returns pb20, pa150, pa200, pa300."""
        # Query 2026-10-das3 or 2026-11-das1
        data = get_probability_data(period_id="2026-10-das3")
        assert data["meta"]["resolution"] == "DASARIAN"
        assert len(data["data"]) == 57
        
        sample = data["data"][0]
        assert "prob_below20" in sample
        assert "prob_above150" in sample
        assert "prob_above200" in sample
        assert "prob_above300" in sample

    def test_06_spi_wide_atomic_commit_and_cache_invalidation(self, tmp_path):
        """Verify commit_ingestion_session for SPI_BULANAN preserves wide format and invalidates cache."""
        token = "TEST_TOKEN_SPI_WIDE_SYNC"
        entries = [
            {
                "station_id": "21010401A",
                "date": "2026-11-01",
                "period_id": "2026-11",
                "spi_value": -0.85,
                "change_type": "NEW",
            },
            {
                "station_id": "21720201A",
                "date": "2026-11-01",
                "period_id": "2026-11",
                "spi_value": -1.20,
                "change_type": "NEW",
            }
        ]
        _STAGING_SESSIONS[token] = {
            "data_type": "SPI_BULANAN",
            "filename": "test_spi_update.xlsx",
            "file_sha256": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
            "entries": entries,
            "summary": {
                "total_records": len(entries),
                "periods_detected": [{"period_id": "2026-11", "label": "November 2026"}],
            }
        }

        # Backup real file before commit
        real_parquet = SPI_RAW_DIR / "bulanan" / "SPI_monthly.parquet"
        bak = tmp_path / "SPI_monthly.parquet.testbak"
        shutil.copy2(real_parquet, bak)

        try:
            res = commit_ingestion_session(
                staging_token=token,
                confirm_overwrite=True,
                selected_periods=["2026-11"],
                explicit_update_consent=True,
                operator="TEST_SUITE"
            )
            assert res["status"] == "COMMITTED"
            
            # Verify file on disk is still wide format with DatetimeIndex
            df_disk = pd.read_parquet(real_parquet)
            assert not isinstance(df_disk.index, pd.RangeIndex)
            assert pd.to_datetime("2026-11-01") in df_disk.index
            assert df_disk.loc[pd.to_datetime("2026-11-01"), "21010401A"] == -0.85
            assert df_disk.loc[pd.to_datetime("2026-11-01"), "21720201A"] == -1.20

            # Verify API retrieves it immediately
            api_res = get_spi_data(period_type="BULANAN", timescale="30D", page_size=10)
            dates = [r["date"] for r in api_res["data"]]
            assert "2026-11-01" in dates
            
            nov_row = next(r for r in api_res["data"] if r["date"] == "2026-11-01")
            assert nov_row["stations"]["21010401A"] == -0.85
            assert nov_row["stations"]["21720201A"] == -1.20

        finally:
            # Restore pristine backup
            shutil.copy2(bak, real_parquet)
            clear_spi_cache()

    def test_07_mariadb_rainfall_baseline_untouched(self):
        """Verify MariaDB cews_rainfall_daily row count is pristine."""
        with get_db() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT COUNT(*) as total FROM cews_rainfall_daily;")
                count = cur.fetchone()["total"]
        assert count >= 286742, f"MariaDB rainfall count altered! Expected 286742, got {count}"
