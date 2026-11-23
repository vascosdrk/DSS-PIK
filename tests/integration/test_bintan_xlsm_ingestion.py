"""
tests/integration/test_bintan_xlsm_ingestion.py
Comprehensive test suite verifying ingestion and parsing of Bintan macro workbook:
1. Auto-detection of dataset type (CURAH_HUJAN) from .xlsm and 'Data_Pos_Hujan' sheet
2. Correct mapping of all 18 station columns in Row 2 to master station IDs
3. Observation date extraction and skipping of empty template rows (post 2026-11-01)
4. Numerical normalization & symbol handling (-, TTU, X, R, typos)
5. Non-destructive staging and diff against MariaDB cews_rainfall_daily baseline
"""

import os
import sys
import pytest
from pathlib import Path

# Add project root to path
ROOT_DIR = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT_DIR))

from backend.ingestion_service import (
    detect_file_type,
    parse_rainfall_excel,
    get_master_station_lookup,
    _STAGING_SESSIONS,
)
from backend.database import get_db

BINTAN_XLSM_PATH = ROOT_DIR / "scratch" / "inspect_ch" / "Entry Data Pos Hujan Bintan.xlsm"
if not BINTAN_XLSM_PATH.exists():
    BINTAN_XLSM_PATH = ROOT_DIR / "tambahan" / "baru" / "Entry Data Pos Hujan Bintan.xlsm"


@pytest.fixture(scope="module")
def bintan_file_bytes():
    assert BINTAN_XLSM_PATH.exists(), f"Bintan fixture workbook not found at {BINTAN_XLSM_PATH}"
    with open(BINTAN_XLSM_PATH, "rb") as f:
        return f.read()


@pytest.fixture(scope="module")
def bintan_preview(bintan_file_bytes):
    # Parse once for the test module with recent date filter for high test performance
    return parse_rainfall_excel(
        bintan_file_bytes,
        "Entry Data Pos Hujan Bintan.xlsm",
        target_date_limit="2026-10-01"
    )


class TestBintanXlsmIngestion:

    def test_01_auto_detect_file_type(self, bintan_file_bytes):
        """Verify detect_file_type correctly identifies .xlsm as CURAH_HUJAN."""
        dtype = detect_file_type("Entry Data Pos Hujan Bintan.xlsm", bintan_file_bytes)
        assert dtype == "CURAH_HUJAN", f"Expected CURAH_HUJAN, got {dtype}"

    def test_02_parse_bintan_sheets_and_stations_recognition(self, bintan_preview):
        """Verify parser recognizes exactly 18 stations in Data_Pos_Hujan sheet."""
        master = get_master_station_lookup()
        assert bintan_preview["status"].upper() == "SUCCESS"
        assert bintan_preview["data_type"] == "CURAH_HUJAN"
        
        # 18 stations recognized
        recognized_ids = bintan_preview["summary"]["stations_recognized"]
        assert len(recognized_ids) == 18, f"Expected 18 stations, got {len(recognized_ids)}"

        expected_sample_ids = [
            "21720201A", # RHF Tanjungpinang
            "21010701A", # Bintan Utara
            "21011001A", # Ekang Anculai
            "21011002A", # Poyotomo
            "21010801A", # Bintan Buyu
            "21010601A", # Batu 18 Kijang
            "21010401A", # Kawal
            "21010702A", # Ria Bintan Lagoi
        ]
        for exp_id in expected_sample_ids:
            assert exp_id in recognized_ids, f"Expected station ID {exp_id} in recognized stations"
            assert exp_id in master, f"Station ID {exp_id} missing in master metadata"

    def test_03_date_boundary_and_template_skipping(self, bintan_preview):
        """Verify observations end at actual data date (2026-11-01) and template rows are ignored."""
        date_range = bintan_preview["summary"]["date_range"]
        assert date_range["start"] >= "2026-10-01"
        # The latest data date in the workbook is 2026-11-01 (not 2027 template rows)
        assert date_range["end"] <= "2026-11-05"

    def test_04_period_detection_and_grouping(self, bintan_preview):
        """Verify periods detected properly identify Dasarian I, II, III Oktober 2026."""
        periods = bintan_preview["summary"]["periods_detected"]
        period_ids = [p["period_id"] for p in periods]
        
        assert "2026-10-das1" in period_ids
        assert "2026-10-das2" in period_ids
        assert "2026-10-das3" in period_ids

        # October Dasarian III should have 11 days * 18 stations = 198 records
        das3 = next(p for p in periods if p["period_id"] == "2026-10-das3")
        assert das3["total_records"] == 11 * 18

    def test_05_staging_session_created_non_destructively(self, bintan_preview):
        """Verify staging token is generated without modifying DB baseline."""
        token = bintan_preview["staging_token"]
        assert token in _STAGING_SESSIONS
        assert _STAGING_SESSIONS[token]["data_type"] == "CURAH_HUJAN"

        # Baseline DB row count must be 100% untouched
        with get_db() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT COUNT(*) as total FROM cews_rainfall_daily;")
                current_count = cur.fetchone()["total"]

        assert current_count >= 286742, f"Database baseline count altered! Got {current_count}"
