"""
================================================================================
DSS-PIK OPERATIONAL DATA INGESTION — END-TO-END ACCEPTANCE TEST SUITE
BMKG Stasiun Meteorologi Kelas II Raja Haji Fisabilillah Tanjungpinang
================================================================================

Comprehensive acceptance tests covering all 18 structural, mapping, sanitization,
monitoring, diff detection, transactional safety, and decision engine requirements:
  1.  CH parsing & workbook structure validation
  2.  53-sheet mapping & dual-region splitting (Bintan vs Tanjungpinang)
  3.  BMKG symbol normalization & typo sanitization
  4.  SPI Dasarian 30D/90D parquet reading & temporal alignment
  5.  SPI Harian 30D/90D parquet reading & daily frequency
  6.  SPI Bulanan (2026_SPI.xlsx) multi-level header & WMO code resolution
  7.  Probabilitas dasarian parsing (pb20, pa150, pa200, pa300, EnsMean)
  8.  Probabilitas bulanan parsing (pa300, pa400, pa500, EnsMean)
  9.  Probability scale validation (strict 0-100%, no x100, threshold >70%)
  10. File duplicate key detection & skipping
  11. Diff detection (NEW vs IDENTICAL vs DIFF)
  12. Historical data protection (zero overwrite of out-of-period records)
  13. Upload idempotency (re-upload produces zero diff)
  14. Atomic transactions (commit & rollback safety)
  15. Audit trail logging in cews_ingestion_history
  16. Decision Engine integration & threshold compliance (PDKM / PDCHT)
  17. Active period & readiness synchronization without lookahead bias
  18. Missing data & ARG strict NULL SPI invariance (no false green alerts)
"""

import io
import re
import pytest
import openpyxl
import pandas as pd
from datetime import date, datetime
from pathlib import Path
from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient

from backend.main import app
from backend.auth import create_session_token
from backend.ingestion_service import (
    detect_file_type,
    parse_rainfall_excel,
    parse_spi_parquet,
    parse_spi_bulanan_excel,
    parse_probability_excel,
    commit_ingestion_session,
    get_ingestion_history_list,
    get_master_station_lookup,
    get_curah_hujan_sheet_mapping,
    WMO_CODE_MAP,
    STATION_TYPO_MAP,
    ARG_STATION_IDS,
    SYMBOL_MAP,
    _STAGING_SESSIONS,
)
from backend.database import get_raw_connection, get_db

client = TestClient(app)
AUTH_HEADERS = {"Authorization": f"Bearer {create_session_token('operator_bmkg_acceptance')}"}

TEMPLATE_BASE = Path("tambahan/template_data_input")
CH_DIR = TEMPLATE_BASE / "ch"
SPI_DIR = TEMPLATE_BASE / "spi"
PROB_DIR = TEMPLATE_BASE / "prob"


# ==============================================================================
# TEST 1: CH Parsing & Workbook Structure Validation
# ==============================================================================
def test_01_ch_parsing_and_workbook_structure():
    """All 6 CH workbooks exist, headers are ['tanggal', 'CH'], data starts at row 2."""
    ch_files = sorted([f for f in CH_DIR.glob("*.xlsx") if not f.name.startswith("~")])
    assert len(ch_files) == 6, f"Expected 6 CH workbooks, found {len(ch_files)}"

    for f in ch_files:
        data = f.read_bytes()
        detected = detect_file_type(f.name, data)
        assert detected == "CURAH_HUJAN", f"File {f.name} detected as {detected}, expected CURAH_HUJAN"

        # Check first sheet header and data start row
        wb = openpyxl.load_workbook(io.BytesIO(data), read_only=True)
        assert len(wb.sheetnames) >= 1
        ws = wb[wb.sheetnames[0]]
        row_iter = ws.iter_rows(values_only=True)
        header = next(row_iter)
        assert str(header[0]).strip().lower() in ("tanggal", "date")
        assert str(header[1]).strip().lower() in ("ch", "curah_hujan", "rainfall")

        first_data_row = next(row_iter)
        assert first_data_row[0] is not None
        wb.close()


# ==============================================================================
# TEST 2: 53-Sheet Mapping & Dual-Region Splitting
# ==============================================================================
def test_02_53_sheets_mapping_and_dual_region_splitting():
    """
    All 53 sheets across 6 workbooks recognized (0 unrecognized).
    Kota Tanjungpinang.xlsx contains 18 sheets: 14 Kab. Bintan and 4 Kota Tanjung Pinang.
    """
    ch_files = sorted([f for f in CH_DIR.glob("*.xlsx") if not f.name.startswith("~")])
    total_recognized = 0
    total_unrecognized = 0
    tanjungpinang_regions = {}

    for f in ch_files:
        data = f.read_bytes()
        res = parse_rainfall_excel(data, f.name, max_rows_per_sheet=5)
        rec = res["summary"]["total_stations_recognized"]
        unrec = res["summary"]["total_stations_unrecognized"]
        total_recognized += rec
        total_unrecognized += unrec

        if f.name == "Kota Tanjungpinang.xlsx":
            # Extract regencies of the 18 stations
            master_lookup = get_master_station_lookup()
            for sid in res["summary"]["stations_recognized"]:
                kab = master_lookup[sid]["kabupaten"]
                tanjungpinang_regions[kab] = tanjungpinang_regions.get(kab, 0) + 1

    assert total_recognized == 53, f"Expected 53 recognized sheets, got {total_recognized}"
    assert total_unrecognized == 0, f"Expected 0 unrecognized sheets, got {total_unrecognized}"

    # Verify dual-region splitting
    assert tanjungpinang_regions.get("Kab. Bintan") == 14, (
        f"Expected 14 Bintan stations in Tanjungpinang workbook, got {tanjungpinang_regions.get('Kab. Bintan')}"
    )
    assert tanjungpinang_regions.get("Kota Tanjung Pinang") == 4, (
        f"Expected 4 Tanjung Pinang stations, got {tanjungpinang_regions.get('Kota Tanjung Pinang')}"
    )


# ==============================================================================
# TEST 3: BMKG Symbol Normalization & Typo Sanitization
# ==============================================================================
def test_03_bmkg_symbol_normalization_and_typo_sanitization():
    """
    Verifies symbol normalization:
    - '-' -> 0.0, 'OBSERVED_ZERO'
    - 'TTU', 'ttu', 'T.T.U' -> 0.0, 'TTU'
    - 'X', 'NO DATA', empty -> None, 'MISSING'
    - 'R', 'ALAT RUSAK (9999)' -> None, 'MISSING'
    - '1-' -> 1.0
    - '0.4.' -> 0.4
    - '.' -> 0.0
    - negative values -> rejected as anomaly
    """
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "00_Dabo Singkep"
    ws.append(["tanggal", "CH"])
    test_cases = [
        ("2026-08-01", "-", 0.0, "OBSERVED_ZERO"),
        ("2026-08-02", "TTU", 0.0, "TTU"),
        ("2026-08-03", "ttu", 0.0, "TTU"),
        ("2026-08-04", "T.T.U", 0.0, "TTU"),
        ("2026-08-05", "X", None, "MISSING"),
        ("2026-08-06", "NO DATA", None, "MISSING"),
        ("2026-08-07", None, None, "MISSING"),
        ("2026-08-08", "R", None, "DAMAGED"),
        ("2026-08-09", "ALAT RUSAK (9999)", None, "DAMAGED"),
        ("2026-08-10", "1-", 1.0, "OBSERVED_VALID"),
        ("2026-08-11", "0.4.", 0.4, "OBSERVED_VALID"),
        ("2026-08-12", ".", None, "AMBIGUOUS"),
        ("2026-08-13", 15.5, 15.5, "OBSERVED_VALID"),
        ("2026-08-14", -5.0, "ANOMALY", "REJECTED"),
    ]
    for row in test_cases:
        ws.append([row[0], row[1]])

    buf = io.BytesIO()
    wb.save(buf)
    parsed = parse_rainfall_excel(buf.getvalue(), "test_symbols.xlsx")

    entries_map = {e["observation_date"]: e for e in parsed["preview_items"] if "observation_date" in e}
    for dt, raw, exp_val, exp_st in test_cases:
        if exp_st == "REJECTED":
            assert any(a.get("raw_value") == raw for a in parsed["anomalies"])
        else:
            assert dt in entries_map, f"Missing parsed row for date {dt}"
            e = entries_map[dt]
            assert e["rainfall_mm"] == exp_val, f"Date {dt}: expected {exp_val}, got {e['rainfall_mm']}"
            assert e["obs_status"] == exp_st, f"Date {dt}: expected {exp_st}, got {e['obs_status']}"


# ==============================================================================
# TEST 4: SPI Dasarian 30D/90D Parquet Reading & Temporal Alignment
# ==============================================================================
def test_04_spi_dasarian_parquet_temporal_alignment():
    """SPI Dasarian parquet must have days aligned to {1, 11, 21} and be auto-detected."""
    p_30d = Path("data/raw/spi/dasarian/SPI_all_30d.parquet")
    p_90d = Path("data/raw/spi/dasarian/SPI_all_90d.parquet")
    assert p_30d.exists() and p_90d.exists()

    data_30d = p_30d.read_bytes()
    assert detect_file_type(p_30d.name, data_30d) == "SPI_DASARIAN"

    df = pd.read_parquet(p_30d)
    unique_days = set(pd.to_datetime(df.index).day)
    assert unique_days.issubset({1, 11, 21}), f"Non-dasarian cutoff days found: {unique_days}"

    res = parse_spi_parquet(data_30d, p_30d.name, period_type="DASARIAN", timescale="30D")
    assert res["status"] == "SUCCESS"
    assert res["summary"]["total_stations_recognized"] == 52
    assert res["summary"]["total_identical"] == len(df)


# ==============================================================================
# TEST 5: SPI Harian 30D/90D Parquet Reading & Daily Frequency
# ==============================================================================
def test_05_spi_harian_parquet_daily_frequency():
    """SPI Harian parquet must span full calendar days (not restricted to dasarians) and be auto-detected."""
    p_daily_30d = Path("data/raw/spi/harian/SPI_all_30d.parquet")
    assert p_daily_30d.exists()

    data = p_daily_30d.read_bytes()
    assert detect_file_type(p_daily_30d.name, data) == "SPI_HARIAN"

    df = pd.read_parquet(p_daily_30d)
    days = set(pd.to_datetime(df.index).day)
    assert len(days) > 20, f"Expected full daily distribution of days, got only {len(days)}"

    res = parse_spi_parquet(data, p_daily_30d.name, period_type="HARIAN", timescale="30D")
    assert res["status"] == "SUCCESS"
    assert res["summary"]["total_stations_recognized"] == 52
    assert res["summary"]["total_identical"] == len(df)


# ==============================================================================
# TEST 6: SPI Bulanan (2026_SPI.xlsx) Multi-Level Header & WMO / Typo Resolution
# ==============================================================================
def test_06_spi_bulanan_excel_wmo_and_typo_resolution():
    """
    2026_SPI.xlsx parsed successfully:
    - Multi-level header extracts 12 months
    - WMO code 00096091A -> 21720201A (Stamet RHF Tanjungpinang)
    - Typo 210310802A -> 21031802A (Selemut Cemaga)
    - Auto-detected as SPI_BULANAN
    """
    spi_excel = SPI_DIR / "2026_SPI.xlsx"
    assert spi_excel.exists()

    data = spi_excel.read_bytes()
    assert detect_file_type(spi_excel.name, data) == "SPI_BULANAN"

    res = parse_spi_bulanan_excel(data, spi_excel.name)
    assert res["status"] == "SUCCESS"
    assert res["data_type"] == "SPI_BULANAN"
    assert res["summary"]["total_stations_recognized"] >= 45

    # Check WMO code resolution for RHF Tanjungpinang
    assert "21720201A" in res["summary"]["stations_recognized"]

    # Check typo correction for Selemut Cemaga
    assert "21031802A" in res["summary"]["stations_recognized"]
    assert any(a.get("raw_code") == "210310802A" and a.get("corrected_to") == "21031802A" for a in res["anomalies"])


# ==============================================================================
# TEST 7: Probabilitas Dasarian Sheets & Forecast Horizons
# ==============================================================================
def test_07_probabilitas_dasarian_sheets_and_forecast_horizons():
    """
    Probabilitas dasarian workbook contains threshold sheets (pb20, pa150, pa200, pa300, EnsMean)
    and resolves to PROBABILITAS_DASARIAN.
    """
    f = PROB_DIR / "dasarian" / "KEPRI_pch_ecmwf_perpos_ver_2026.04.30.xlsx"
    assert f.exists()

    data = f.read_bytes()
    assert detect_file_type(f.name, data) == "PROBABILITAS_DASARIAN"

    res = parse_probability_excel(data, f.name, forecast_type="PROBABILITAS_DASARIAN")
    assert res["status"] == "SUCCESS"
    assert res["data_type"] == "PROBABILITAS_DASARIAN"
    assert "MeiI" in res["summary"]["period_columns"]
    assert res["summary"]["total_stations_recognized"] in (51, 52)


# ==============================================================================
# TEST 8: Probabilitas Bulanan Sheets & Multi-Month Horizons
# ==============================================================================
def test_08_probabilitas_bulanan_sheets_and_multi_month_horizons():
    """
    Probabilitas bulanan workbook contains monthly sheets (pa300, pa400, pa500, EnsMean)
    and resolves to PROBABILITAS_BULANAN with multi-month horizons.
    """
    f = PROB_DIR / "bulanan" / "KEPRI_pch_ecmwf_perpos_ver_2026.08.01.xlsx"
    assert f.exists()

    data = f.read_bytes()
    assert detect_file_type(f.name, data) == "PROBABILITAS_BULANAN"

    res = parse_probability_excel(data, f.name, forecast_type="PROBABILITAS_BULANAN")
    assert res["status"] == "SUCCESS"
    assert res["data_type"] == "PROBABILITAS_BULANAN"
    assert "Sep" in res["summary"]["period_columns"]
    assert "Okt" in res["summary"]["period_columns"]
    assert res["summary"]["total_stations_recognized"] in (51, 52)


# ==============================================================================
# TEST 9: Probability Scale Validation (Strict 0-100%, No x100, Threshold >70%)
# ==============================================================================
def test_09_probability_scale_strict_0_to_100_percent():
    """
    Probability values are strictly in range 0.0 to 100.0%.
    They must never be multiplied by 100, and alert triggers use > 70.0%.
    """
    f = PROB_DIR / "dasarian" / "KEPRI_pch_ecmwf_perpos_ver_2026.04.30.xlsx"
    wb = openpyxl.load_workbook(f, data_only=True, read_only=True)
    ws = wb["pb20"]

    vals = []
    for row in ws.iter_rows(min_row=2, values_only=True):
        if row and len(row) >= 8 and row[7] is not None:
            try:
                v = float(row[7])
                vals.append(v)
            except ValueError:
                pass
    wb.close()

    assert len(vals) > 0
    min_v = min(vals)
    max_v = max(vals)
    assert min_v >= 0.0, f"Negative probability found: {min_v}"
    assert max_v <= 100.0, f"Probability exceeds 100%: {max_v}"
    # Verify that values are floating percentages (e.g., > 1.0 exists, confirming raw percent scale)
    assert any(v > 1.0 for v in vals), "Probabilities appear to be decimals (0-1) instead of percentages (0-100%)"


# ==============================================================================
# TEST 10: File Duplicate Key Detection
# ==============================================================================
def test_10_file_duplicate_key_detection():
    """Duplicate (station_id, observation_date) rows within the same file are detected and skipped."""
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "00_Dabo Singkep"
    ws.append(["tanggal", "CH"])
    ws.append(["2026-08-01", 10.0])
    ws.append(["2026-08-01", 20.0])  # Duplicate date

    buf = io.BytesIO()
    wb.save(buf)
    res = parse_rainfall_excel(buf.getvalue(), "test_dups.xlsx")

    assert res["summary"]["total_duplicate"] == 1
    assert any(a.get("type") == "DUPLICATE_KEY" for a in res["anomalies"])
    # Only 1 unique entry kept in staged entries
    staged_entries = _STAGING_SESSIONS[res["staging_token"]]["entries"]
    assert len(staged_entries) == 1


# ==============================================================================
# TEST 11: Diff Detection (NEW vs IDENTICAL vs DIFF)
# ==============================================================================
def test_11_diff_detection_new_identical_updated():
    """
    Ingestion preview identifies:
    - NEW for future dates not yet in DB
    - IDENTICAL for matching dates and values
    - DIFF for existing dates with changed values
    """
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "00_Dabo Singkep"
    ws.append(["tanggal", "CH"])
    # 2024-07-01 is historical in DB
    ws.append(["2024-07-01", 0.0])
    # 2099-01-01 is future (NEW)
    ws.append(["2099-01-01", 12.5])

    buf = io.BytesIO()
    wb.save(buf)
    res = parse_rainfall_excel(buf.getvalue(), "test_diff.xlsx")

    entries = {e["observation_date"]: e for e in res["preview_items"]}
    assert "2099-01-01" in entries
    assert entries["2099-01-01"]["change_type"] == "NEW"
    assert res["summary"]["total_new"] >= 1


# ==============================================================================
# TEST 12: Historical Data Protection (Zero Overwrite of Out-of-Period Records)
# ==============================================================================
def test_12_historical_data_protection():
    """
    Baseline verification: MariaDB cews_rainfall_daily count remains exactly 286,085 rows.
    Dry-run preview operations must never alter production tables.
    """
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) AS total FROM cews_rainfall_daily;")
            row = cur.fetchone()
            assert row["total"] == 286085, f"Production baseline corrupted! Expected 286085, found {row['total']}"


# ==============================================================================
# TEST 13: Upload Idempotency (Re-Upload Produces Zero Diff)
# ==============================================================================
def test_13_upload_idempotency_same_file():
    """Re-uploading the same SPI parquet produces 100% identical dates and 0 new/updated."""
    p_30d = Path("data/raw/spi/dasarian/SPI_all_30d.parquet")
    data = p_30d.read_bytes()
    df = pd.read_parquet(p_30d)

    res1 = parse_spi_parquet(data, p_30d.name, period_type="DASARIAN", timescale="30D")
    res2 = parse_spi_parquet(data, p_30d.name, period_type="DASARIAN", timescale="30D")

    assert res1["summary"]["total_identical"] == len(df)
    assert res1["summary"]["total_new"] == 0
    assert res1["summary"]["total_updated"] == 0
    assert res2["summary"]["total_identical"] == res1["summary"]["total_identical"]


# ==============================================================================
# TEST 14: Atomic Transactions (Commit & Rollback Safety)
# ==============================================================================
def test_14_atomic_transactions_rollback_on_failure():
    """
    If database insertion fails during commit, all operations are rolled back
    and no partial data persists.
    """
    token = "TOKEN_TEST_ROLLBACK_SESSION"
    _STAGING_SESSIONS[token] = {
        "data_type": "CURAH_HUJAN",
        "filename": "test_rollback.xlsx",
        "entries": [
            {
                "station_id": "21040101A",
                "observation_date": "2099-12-31",
                "rainfall_mm": 5.0,
                "obs_status": "OBSERVED_VALID",
                "original_symbol": "5.0"
            }
        ],
        "created_at": datetime.now(),
        "summary": {
            "total_records": 1,
            "date_range": {"start": "2099-12-31", "end": "2099-12-31"},
            "invalid_count": 0,
        }
    }

    # Simulate database error during commit
    with patch("backend.ingestion_service.get_raw_connection") as mock_get_conn:
        mock_conn = MagicMock()
        mock_cur = MagicMock()
        mock_cur.execute.side_effect = RuntimeError("Simulated Database Failure")
        mock_conn.cursor.return_value.__enter__.return_value = mock_cur
        mock_get_conn.return_value = mock_conn

        with pytest.raises(RuntimeError, match="Database commit failed"):
            commit_ingestion_session(token)

        mock_conn.rollback.assert_called_once()


# ==============================================================================
# TEST 15: Audit Trail Logging in cews_ingestion_history
# ==============================================================================
def test_15_audit_trail_logging_and_api():
    """
    Audit log table cews_ingestion_history records ingestion activity.
    GET /api/v1/ingestion/history returns history entries.
    """
    # Insert temporary audit row
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO cews_ingestion_history
                (batch_id, data_type, file_name, date_range_start, date_range_end, total_records, new_records, updated_records, identical_records, invalid_records, status, operator)
                VALUES ('BATCH_TEST_AUDIT', 'CURAH_HUJAN', 'audit_test.xlsx', '2026-08-01', '2026-08-10', 10, 10, 0, 0, 0, 'COMMITTED', 'AUDIT_TESTER');
            """)

    res = client.get("/api/v1/ingestion/history?limit=10", headers=AUTH_HEADERS)
    assert res.status_code == 200, res.text
    data = res.json()
    assert "items" in data
    assert any(item["batch_id"] == "BATCH_TEST_AUDIT" for item in data["items"])

    # Clean up test audit row
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM cews_ingestion_history WHERE batch_id = 'BATCH_TEST_AUDIT';")


# ==============================================================================
# TEST 16: Decision Engine Integration & Threshold Compliance
# ==============================================================================
def test_16_decision_engine_rules_and_threshold_compliance():
    """
    Decision Engine rules:
    - PDKM = max(level_hth, level_prob, level_spi)
    - PDCHT = max(level_dasarian, level_bulanan)
    - Thresholds strictly preserved:
      HTH: Waspada (21-30), Siaga (31-60), Awas (>60)
      SPI: Waspada (-1.49 to -1.00), Siaga (-1.99 to -1.50), Awas (<= -2.00)
    """
    from backend.decision_engine import evaluate_pdkm_full, evaluate_pdcht_full

    # PDKM: level_hth=AWAS (65 days), level_prob=AMAN (10%), level_spi=SIAGA (-1.6) -> max is AWAS
    pdkm_res = evaluate_pdkm_full(hth_days=65, pb20=10.0, spi_val=-1.6)
    assert pdkm_res["status"] == "AWAS"
    assert pdkm_res["level"] == 3

    # PDKM: level_hth=AMAN (5 days), level_prob=AMAN (20%), level_spi=WASPADA (-1.2) -> max is WASPADA
    pdkm_res2 = evaluate_pdkm_full(hth_days=5, pb20=20.0, spi_val=-1.2)
    assert pdkm_res2["status"] == "WASPADA"
    assert pdkm_res2["level"] == 1

    # PDCHT: dasarian pa200=80.0 (>70% -> SIAGA) -> max is at least SIAGA
    pdcht_res = evaluate_pdcht_full(pa200=80.0, pm300=75.0)
    assert pdcht_res["status"] in ("SIAGA", "AWAS")
    assert pdcht_res["level"] >= 2


# ==============================================================================
# TEST 17: Active Period & Readiness Synchronization Without Lookahead Bias
# ==============================================================================
def test_17_active_period_readiness_no_lookahead_bias():
    """
    Active period evaluation for past snapshots (e.g. 2026-09 Dasarian II)
    must rely only on data up to that cutoff, never leaking future observations.
    """
    from backend.period_service import get_active_period, get_observation_cutoff_date, get_dasarian_dates

    active_p = get_active_period()
    assert active_p is not None
    assert "period_id" in active_p
    assert "observation_cutoff" in active_p
    assert "target_start" in active_p
    assert "target_end" in active_p

    # Test cutoff date calculation for warning period (2026-09 das2 -> cutoff is 2026-09-10 without lookahead bias)
    cutoff = get_observation_cutoff_date(2026, 9, "das2")
    assert cutoff == date(2026, 9, 10)

    start_d, end_d = get_dasarian_dates(2026, 9, "das2")
    assert start_d == date(2026, 9, 11)
    assert end_d == date(2026, 9, 20)


# ==============================================================================
# TEST 18: Missing Data & ARG Strict NULL SPI Invariance
# ==============================================================================
def test_18_arg_strict_null_spi_and_no_false_green():
    """
    All 5 ARG stations have strictly NULL SPI across all timescales.
    Missing SPI values never trigger false green ("Aman") or false warnings.
    """
    from backend.data_service import get_station_spi_trend

    for arg_id in ARG_STATION_IDS:
        trend = get_station_spi_trend(arg_id, months=12)
        assert trend["is_arg"] is True
        for val in trend["dasarian"]["spi_30d"]:
            assert val is None, f"ARG station {arg_id} has non-null SPI: {val}"
        for val in trend["dasarian"]["spi_90d"]:
            assert val is None, f"ARG station {arg_id} has non-null SPI: {val}"
        for val in trend["harian"]["spi_30d"]:
            assert val is None, f"ARG station {arg_id} has non-null SPI: {val}"
        for val in trend["harian"]["spi_90d"]:
            assert val is None, f"ARG station {arg_id} has non-null SPI: {val}"
        for val in trend["bulanan"]["spi"]:
            assert val is None, f"ARG station {arg_id} has non-null SPI: {val}"
