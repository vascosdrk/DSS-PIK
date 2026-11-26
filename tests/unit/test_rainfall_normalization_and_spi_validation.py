"""
tests/unit/test_rainfall_normalization_and_spi_validation.py

Comprehensive unit tests for:
1. Centralized numeric rainfall normalization (backend/rainfall_normalization.py):
   - TTU -> 0.0 mm (only in numeric layer; display/export remain 'TTU')
   - OBSERVED_ZERO -> 0.0 mm
   - OBSERVED_VALID / CORRECTED -> actual numeric value
   - MISSING / MISSING_INTERNAL (even with positive rainfall_mm) / DAMAGED / AMBIGUOUS -> NaN
   - VOID -> excluded completely
   - NULL / unknown status -> fail-safe NaN
2. CH display/export preservation of 'TTU' symbol (no silent conversion to 0).
3. SPI output date-range compliance validation (MATCH vs INCOMPLETE warning).
4. Frontend SPI resolution sync & non-remounting refresh contract checks.
"""

import datetime
import math
from decimal import Decimal
from pathlib import Path
import numpy as np
import pytest

from backend.rainfall_normalization import (
    build_station_numeric_series,
    evaluate_output_date_range_compliance,
    is_excluded_obs_status,
    normalize_rainfall_for_numeric,
)
from backend.rainfall_ingestion_v2 import format_standard_display


def test_ttu_normalizes_to_zero_for_numeric_processing():
    assert normalize_rainfall_for_numeric(0.0, "TTU") == 0.0
    assert normalize_rainfall_for_numeric(None, "TTU") == 0.0
    assert normalize_rainfall_for_numeric(Decimal("0.00"), "ttu") == 0.0


def test_observed_zero_normalizes_to_zero():
    assert normalize_rainfall_for_numeric(0.0, "OBSERVED_ZERO") == 0.0
    assert normalize_rainfall_for_numeric(None, "OBSERVED_ZERO") == 0.0


def test_observed_valid_and_corrected_preserve_actual_values():
    assert normalize_rainfall_for_numeric(14.5, "OBSERVED_VALID") == 14.5
    assert normalize_rainfall_for_numeric(Decimal("0.40"), "OBSERVED_VALID") == 0.4
    assert normalize_rainfall_for_numeric(27.2, "CORRECTED") == 27.2
    assert normalize_rainfall_for_numeric(0.0, "OBSERVED_VALID") == 0.0
    assert math.isnan(normalize_rainfall_for_numeric(None, "OBSERVED_VALID"))
    assert math.isnan(normalize_rainfall_for_numeric(9999.0, "OBSERVED_VALID"))
    assert math.isnan(normalize_rainfall_for_numeric(8888.0, "OBSERVED_VALID"))


def test_missing_and_missing_internal_always_nan_even_with_positive_value():
    assert math.isnan(normalize_rainfall_for_numeric(None, "MISSING"))
    assert math.isnan(normalize_rainfall_for_numeric(0.0, "MISSING"))
    assert math.isnan(normalize_rainfall_for_numeric(15.2, "MISSING"))
    # Critical regression check for legacy MISSING_INTERNAL rows carrying numeric values
    assert math.isnan(normalize_rainfall_for_numeric(0.0, "MISSING_INTERNAL"))
    assert math.isnan(normalize_rainfall_for_numeric(Decimal("23.50"), "MISSING_INTERNAL"))
    assert math.isnan(normalize_rainfall_for_numeric(5.0, "missing_internal"))


def test_damaged_ambiguous_void_and_null_status_produce_nan():
    assert math.isnan(normalize_rainfall_for_numeric(0.0, "DAMAGED"))
    assert math.isnan(normalize_rainfall_for_numeric(12.0, "DAMAGED"))
    assert math.isnan(normalize_rainfall_for_numeric(8.0, "AMBIGUOUS"))
    assert math.isnan(normalize_rainfall_for_numeric(10.0, "VOID"))
    assert is_excluded_obs_status("VOID") is True
    assert is_excluded_obs_status("void") is True
    assert is_excluded_obs_status("TTU") is False
    # NULL or unknown status must never be blindly accepted
    assert math.isnan(normalize_rainfall_for_numeric(5.0, None))
    assert math.isnan(normalize_rainfall_for_numeric(5.0, ""))
    assert math.isnan(normalize_rainfall_for_numeric(5.0, "UNKNOWN_FLAG"))


def test_build_station_numeric_series_excludes_void_and_normalizes_all_statuses():
    rows = [
        {"station_id": "21010401A", "observation_date": datetime.date(2026, 10, 26), "rainfall_mm": Decimal("12.50"), "obs_status": "OBSERVED_VALID"},
        {"station_id": "21010401A", "observation_date": datetime.date(2026, 10, 27), "rainfall_mm": Decimal("0.00"), "obs_status": "TTU"},
        {"station_id": "21010401A", "observation_date": datetime.date(2026, 10, 28), "rainfall_mm": Decimal("0.00"), "obs_status": "OBSERVED_ZERO"},
        {"station_id": "21010401A", "observation_date": datetime.date(2026, 10, 29), "rainfall_mm": Decimal("18.40"), "obs_status": "MISSING_INTERNAL"},
        {"station_id": "21010401A", "observation_date": datetime.date(2026, 10, 30), "rainfall_mm": None, "obs_status": "VOID"},
        {"station_id": "21010401A", "observation_date": datetime.date(2026, 10, 31), "rainfall_mm": Decimal("4.20"), "obs_status": "CORRECTED"},
    ]
    grouped = build_station_numeric_series(rows, ["21010401A"])
    s = grouped["21010401A"]
    # VOID date (2026-10-30) must be excluded completely
    assert s["dates"] == ["2026-10-26", "2026-10-27", "2026-10-28", "2026-10-29", "2026-10-31"]
    assert s["values"][0] == 12.5
    assert s["values"][1] == 0.0   # TTU -> 0.0
    assert s["values"][2] == 0.0   # OBSERVED_ZERO -> 0.0
    assert np.isnan(s["values"][3])  # MISSING_INTERNAL -> NaN despite 18.40 mm
    assert s["values"][4] == 4.2   # CORRECTED -> 4.2


def test_ch_display_and_export_preserve_ttu_symbol():
    """TTU must remain displayed and exported as 'TTU', never coerced to 0."""
    assert format_standard_display(0.0, "TTU") == "TTU"
    assert format_standard_display(0.0, "OBSERVED_ZERO") == "-"
    assert format_standard_display(None, "MISSING") == "9999"
    # Verify export_rainfall_data in backend/data_service.py still maps TTU -> 'TTU'
    ds_src = Path("backend/data_service.py").read_text(encoding="utf-8")
    assert 'if obs_st == "TTU" or r.get("original_symbol") == "TTU":' in ds_src
    assert 'val_str = "TTU"' in ds_src


def test_output_date_range_compliance_validation():
    ok = evaluate_output_date_range_compliance(
        actual_start="2026-11-11",
        actual_end="2026-11-20",
        requested_start="2026-11-11",
        requested_end="2026-11-20",
        output_rows=10,
        resolution="HARIAN",
    )
    assert ok["date_range_compliant"] is True
    assert ok["date_range_status"] == "MATCH"
    assert ok["date_range_warning"] is None

    truncated = evaluate_output_date_range_compliance(
        actual_start="2026-11-11",
        actual_end="2026-11-11",
        requested_start="2026-11-11",
        requested_end="2026-11-20",
        output_rows=1,
        resolution="HARIAN",
    )
    assert truncated["date_range_compliant"] is False
    assert truncated["date_range_status"] == "INCOMPLETE"
    assert "2026-11-11" in truncated["date_range_warning"]
    assert "2026-11-20" in truncated["date_range_warning"]


def test_frontend_spi_resolution_sync_and_non_remount_contract():
    """Static contract verification for DataCenter, SpiDataTable, and SpiGeneratorModal."""
    dc = Path("frontend/src/components/DataCenter.jsx").read_text(encoding="utf-8")
    tbl = Path("frontend/src/components/SpiDataTable.jsx").read_text(encoding="utf-8")
    modal = Path("frontend/src/components/SpiGeneratorModal.jsx").read_text(encoding="utf-8")

    # 1. DataCenter passes initialResolution & initialTimescale to SpiGeneratorModal
    assert "initialResolution={generatorContext.resolution}" in dc
    assert "initialTimescale={generatorContext.timescale}" in dc
    assert "rawRes === 'DAILY' || rawRes === 'HARIAN'" in dc
    assert "rawRes === 'BULANAN'" in dc

    # 2. SpiDataTable uses refreshTrigger instead of remounting React key
    assert "key={`spi-${refreshKey}`}" not in dc
    assert "refreshTrigger={spiRefreshTrigger}" in dc
    assert "setSpiRefreshTrigger((prev) => prev + 1)" in dc
    assert "refreshTrigger = 0" in tbl
    assert "[fetchSpiData, refreshTrigger]" in tbl

    # 3. SpiGeneratorModal initializes from props and shows date-range compliance warning
    assert "initialResolution = 'DASARIAN'" in modal
    assert "initialTimescale = 30" in modal
    assert "normalizeGeneratorResolution(initialResolution)" in modal
    assert "normalizeGeneratorTimescale(initialTimescale)" in modal
    assert "Validasi Rentang Tanggal Output" in modal
    assert "TIDAK LENGKAP" in modal
    assert "date_range_compliant" in modal
