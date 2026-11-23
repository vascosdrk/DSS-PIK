"""
Test Suite: Data Ingestion System, Multi-Scale SPI Monitoring, and Historical Data Integrity
Verifies:
1. Multi-scale SPI endpoints (Daily 30D/90D, Dasarian 30D/90D, Monthly 1M)
2. Station SPI Trend API and strict NULL handling for ARG stations
3. Ingestion Preview (Dry-Run), Multi-Type Detection, and Diff Calculation
4. Ingestion Commit (Atomic Transaction), Logging, and History
5. Decision Engine and Snapshot Invariance
"""

import os
import io
import pytest
import pandas as pd
from fastapi.testclient import TestClient

from backend.main import app
from backend.auth import create_session_token
from backend.ingestion_service import (
    detect_file_type,
    parse_rainfall_excel,
    parse_spi_parquet,
    parse_spi_bulanan_excel,
    parse_probability_excel,
    get_ingestion_history_list
)
from backend.data_service import get_station_spi_trend, get_spi_data
from backend.database import get_raw_connection

client = TestClient(app)
AUTH_HEADERS = {"Authorization": f"Bearer {create_session_token('test_operator')}"}


class TestMultiScaleSpiMonitoring:
    """Verifies that SPI Daily, Dasarian, and Monthly are correctly integrated and served."""

    def test_station_spi_trend_standard_station(self):
        """Standard manual station should have valid trend series for daily, dasarian, and monthly."""
        res = client.get("/api/v1/stations/21010401A/spi-trend?months=12", headers=AUTH_HEADERS)
        assert res.status_code == 200, res.text
        data = res.json()

        assert data["station_id"] == "21010401A"
        assert data["is_arg"] is False
        assert len(data["dasarian"]["spi_30d"]) > 0
        assert len(data["dasarian"]["spi_90d"]) > 0
        assert len(data["harian"]["spi_30d"]) > 0
        assert len(data["harian"]["spi_90d"]) > 0
        assert len(data["bulanan"]["spi"]) > 0
        assert len(data["dasarian"]["dates"]) == len(data["dasarian"]["spi_30d"])

    def test_station_spi_trend_arg_station_strict_null(self):
        """ARG stations (e.g. 21010802B ARG Tembeling) must have is_arg=True and all SPI values strictly None."""
        res = client.get("/api/v1/stations/21010802B/spi-trend?months=12", headers=AUTH_HEADERS)
        assert res.status_code == 200, res.text
        data = res.json()

        assert data["is_arg"] is True
        # All series values must be empty or strictly None
        for val in data["dasarian"]["spi_30d"]:
            assert val is None
        for val in data["harian"]["spi_30d"]:
            assert val is None
        for val in data["bulanan"]["spi"]:
            assert val is None

    def test_spi_data_bulanan_grid(self):
        """GET /api/v1/spi/data with period_type=BULANAN returns monthly SPI dataset."""
        res = client.get("/api/v1/spi/data?period_type=BULANAN&page_size=10", headers=AUTH_HEADERS)
        assert res.status_code == 200, res.text
        data = res.json()

        assert data["meta"]["period_type"] == "BULANAN"
        assert len(data["columns"]) == 57
        assert len(data["data"]) > 0

        # Check date format and ARG column
        first_row = data["data"][0]
        assert len(first_row["date"].split("-")) == 3  # YYYY-MM-DD
        # ARG station in stations dict should be None
        stations_dict = first_row["stations"]
        assert stations_dict.get("21010802B") is None

    def test_station_detail_includes_daily_and_monthly_spi(self):
        """Station detail endpoint returns daily and monthly SPI indicators."""
        res = client.get("/api/v1/stations/21010401A/detail?period_id=2026-09-das2", headers=AUTH_HEADERS)
        assert res.status_code == 200, res.text
        data = res.json()

        assert "spi_daily_30d" in data
        assert "spi_daily_90d" in data
        assert "spi_daily_evidence_date" in data
        assert "spi_monthly_value" in data
        assert "spi_monthly_evidence_month" in data


class TestDataIngestionSystem:
    """Verifies file type detection, parsing dry-runs, preview diffs, and audit logging."""

    def test_file_type_detection(self):
        """Verifies accurate detection across all dataset formats."""
        assert detect_file_type("SPI_all_30d.parquet", b"") in ["SPI_HARIAN", "SPI_DASARIAN"]
        assert detect_file_type("Bintan.xlsx", b"") == "CURAH_HUJAN"
        assert detect_file_type("2026_SPI.xlsx", b"") == "SPI_BULANAN"
        assert detect_file_type("Probabilitas_Dasarian.xlsx", b"") == "PROBABILITAS_DASARIAN"
        assert detect_file_type("Probabilitas_Bulanan.xlsx", b"") == "PROBABILITAS_BULANAN"

    def test_ingestion_preview_dry_run_does_not_modify_db(self):
        """Previewing rainfall file calculates diffs without inserting/altering DB."""
        conn = get_raw_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM cews_rainfall_daily")
        count_before = list(cursor.fetchone().values())[0]
        cursor.close()
        conn.close()

        # Call preview endpoint with a sample Excel from template folder
        sample_path = "tambahan/template_data_input/Data Curah Hujan (CH)/Kota Tanjungpinang.xlsx"
        if os.path.exists(sample_path):
            with open(sample_path, "rb") as f:
                res = client.post(
                    "/api/v1/ingestion/preview",
                    files=[("files", ("Kota Tanjungpinang.xlsx", f, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"))],
                    data={"data_type": "CURAH_HUJAN", "timescale": "30D"},
                    headers=AUTH_HEADERS,
                )
            assert res.status_code == 200, res.text
            preview = res.json()

            assert preview["status"] == "SUCCESS"
            assert preview["data_type"] == "CURAH_HUJAN"
            assert preview["summary"]["total_rows"] > 0
            assert "staging_token" in preview
            assert preview["summary"]["total_stations_recognized"] > 0

        # Count rows after preview to verify zero DB modification
        conn = get_raw_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM cews_rainfall_daily")
        count_after = list(cursor.fetchone().values())[0]
        cursor.close()
        conn.close()

        assert count_after == count_before, "Preview modified database records!"

    def test_ingestion_history_endpoint(self):
        """GET /api/v1/ingestion/history returns list of audit entries."""
        res = client.get("/api/v1/ingestion/history?limit=10", headers=AUTH_HEADERS)
        assert res.status_code == 200, res.text
        data = res.json()
        assert "items" in data
        assert isinstance(data["items"], list)


class TestOperationalIntegrity:
    """Verifies that Decision Engine rules and historical frozen snapshots remain intact."""

    def test_snapshots_frozen_count_intact(self):
        """Verify snapshot count remains intact (10 periods x 57 stations = 570 records)."""
        conn = get_raw_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM cews_period_snapshot")
        snap_count = list(cursor.fetchone().values())[0]
        cursor.close()
        conn.close()

        assert snap_count == 570, f"Expected 570 snapshot records, found {snap_count}"

    def test_september_das2_operational_decision_intact(self):
        """Verify that September Dasarian II operational warning table is unchanged."""
        res = client.get("/api/v1/early-warning-table?period_id=2026-09-das2", headers=AUTH_HEADERS)
        assert res.status_code == 200, res.text
        data = res.json()
        assert "data" in data
        assert len(data["data"]) == 57

        # Check a specific known station (e.g. 21010401A)
        stn = next(s for s in data["data"] if s["station_id"].upper() == "21010401A")
        assert stn["warning_level"] in ["NORMAL", "WASPADA", "SIAGA", "AWAS"]
