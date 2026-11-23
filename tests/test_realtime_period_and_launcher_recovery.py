"""
tests/test_realtime_period_and_launcher_recovery.py
Automated Verification Suite for DSS-PIK:
- Paket 1: Dynamic Dasarian Calendar, Real-time & Manual Modes, 10-Dasarian Window, Decoupled Readiness
- Paket 2: Standardized Windows Launchers (run_cews.bat, buka_dashboard.bat)
- Paket 3: Repository File Structure, Baselines, and Checksums
"""

import os
import sys
import json
import hashlib
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
import pytest
import pymysql

ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR))

from backend.period_service import (
    date_to_dasarian,
    get_last_day_of_month,
    format_period_label,
    get_dasarian_dates,
    get_observation_cutoff_date,
    get_forecast_issue_date,
    get_spi_target_date_for_period,
    get_previous_dasarian,
    get_next_dasarian,
    generate_10_dasarian_window,
    get_period_config,
    set_period_config,
    get_active_period,
    get_10_dasarian_window_items,
    get_period_readiness_analysis,
    generate_dynamic_snapshot_for_period,
    CONFIG_PATH,
    SNAPSHOTS_DIR
)
from config.paths import (
    PATH_SPI_AUTHORITATIVE,
    PATH_SPI_PARQUET_DASARIAN_90D,
    RAW_DATA_DIR
)


# ==============================================================================
# 1. CALENDAR UTILITIES & LEAP YEAR TESTS
# ==============================================================================

def test_calendar_boundary_and_leap_years():
    """Verify exact dasarian mapping on boundary days and leap years."""
    # Boundary days for September 2026
    assert date_to_dasarian(date(2026, 9, 1)) == (2026, 9, "das1")
    assert date_to_dasarian(date(2026, 9, 10)) == (2026, 9, "das1")
    assert date_to_dasarian(date(2026, 9, 11)) == (2026, 9, "das2")
    assert date_to_dasarian(date(2026, 9, 20)) == (2026, 9, "das2")
    assert date_to_dasarian(date(2026, 9, 21)) == (2026, 9, "das3")
    assert date_to_dasarian(date(2026, 9, 30)) == (2026, 9, "das3")

    # Boundary days for October 2026
    assert date_to_dasarian(date(2026, 10, 1)) == (2026, 10, "das1")
    assert date_to_dasarian(date(2026, 10, 10)) == (2026, 10, "das1")
    assert date_to_dasarian(date(2026, 10, 11)) == (2026, 10, "das2")
    assert date_to_dasarian(date(2026, 10, 20)) == (2026, 10, "das2")
    assert date_to_dasarian(date(2026, 10, 21)) == (2026, 10, "das3")
    assert date_to_dasarian(date(2026, 10, 28)) == (2026, 10, "das3")
    assert date_to_dasarian(date(2026, 10, 31)) == (2026, 10, "das3")

    # February Leap Year (2024: 29 days)
    assert get_last_day_of_month(2024, 2) == 29
    assert date_to_dasarian(date(2024, 2, 29)) == (2024, 2, "das3")
    t_start, t_end = get_dasarian_dates(2024, 2, "das3")
    assert t_start == date(2024, 2, 21)
    assert t_end == date(2024, 2, 29)

    # February Common Year (2025/2026: 28 days)
    assert get_last_day_of_month(2026, 2) == 28
    assert date_to_dasarian(date(2026, 2, 28)) == (2026, 2, "das3")
    t_start, t_end = get_dasarian_dates(2026, 2, "das3")
    assert t_start == date(2026, 2, 21)
    assert t_end == date(2026, 2, 28)


def test_previous_and_next_dasarian():
    """Verify dasarian arithmetic across month and year transitions."""
    # Intramonth transitions
    assert get_previous_dasarian(2026, 9, "das3") == (2026, 9, "das2")
    assert get_previous_dasarian(2026, 9, "das2") == (2026, 9, "das1")
    assert get_next_dasarian(2026, 9, "das1") == (2026, 9, "das2")
    assert get_next_dasarian(2026, 9, "das2") == (2026, 9, "das3")

    # Month transitions
    assert get_previous_dasarian(2026, 10, "das1") == (2026, 9, "das3")
    assert get_next_dasarian(2026, 9, "das3") == (2026, 10, "das1")

    # Year transitions
    assert get_previous_dasarian(2027, 1, "das1") == (2026, 12, "das3")
    assert get_next_dasarian(2026, 12, "das3") == (2027, 1, "das1")


def test_10_dasarian_window_generation():
    """Verify that exactly 10 chronological dasarians ending at active period are generated."""
    # Active: 2026-10-das3 (October Dasarian III)
    w_oct3 = generate_10_dasarian_window(2026, 10, "das3")
    assert len(w_oct3) == 10
    assert w_oct3[-1] == (2026, 10, "das3")
    assert w_oct3[0] == (2026, 7, "das3")  # 9 preceding periods

    # Verify monotonic chronological order
    pids = [f"{y:04d}-{m:02d}-{d}" for y, m, d in w_oct3]
    expected = [
        "2026-07-das3",
        "2026-08-das1", "2026-08-das2", "2026-08-das3",
        "2026-09-das1", "2026-09-das2", "2026-09-das3",
        "2026-10-das1", "2026-10-das2", "2026-10-das3"
    ]
    assert pids == expected

    # Active: 2026-09-das2 (September Dasarian II)
    w_sep2 = generate_10_dasarian_window(2026, 9, "das2")
    assert len(w_sep2) == 10
    assert w_sep2[-1] == (2026, 9, "das2")
    assert w_sep2[0] == (2026, 6, "das2")


def test_spi_temporal_mapping_rules():
    """Verify mandated temporal mapping from target dasarian to SPI reference dates."""
    # Target Dasarian I -> SPI Dasarian III prev month (21st)
    assert get_spi_target_date_for_period("2026-10-das1") == "2026-09-21"
    assert get_spi_target_date_for_period("2027-01-das1") == "2026-12-21"

    # Target Dasarian II -> SPI Dasarian I same month (1st)
    assert get_spi_target_date_for_period("2026-09-das2") == "2026-09-01"
    assert get_spi_target_date_for_period("2026-10-das2") == "2026-10-01"

    # Target Dasarian III -> SPI Dasarian II same month (11th)
    assert get_spi_target_date_for_period("2026-09-das3") == "2026-09-11"
    assert get_spi_target_date_for_period("2026-10-das3") == "2026-10-11"


# ==============================================================================
# 2. SERVER-SIDE CONFIGURATION & MODE SWITCHING
# ==============================================================================

def test_server_side_config_persistence():
    """Verify setting and reading period mode and manual period server-side."""
    initial_cfg = get_period_config()

    try:
        # Set to manual mode with explicit period
        cfg_manual = set_period_config("manual", "2026-09-das2", operator_name="test_operator")
        assert cfg_manual["mode"] == "manual"
        assert cfg_manual["manual_period_id"] == "2026-09-das2"
        assert cfg_manual["updated_by"] == "test_operator"

        # Verify active period resolution in manual mode
        act = get_active_period()
        assert act["mode"] == "manual"
        assert act["period_id"] == "2026-09-das2"
        assert act["label"] == "Dasarian II September 2026"

        # Switch back to auto mode (real-time calendar)
        cfg_auto = set_period_config("auto", operator_name="test_operator")
        assert cfg_auto["mode"] == "auto"
        assert cfg_auto["manual_period_id"] is None

        # Verify active period follows real-time calendar dynamically
        from backend.period_service import get_current_server_time_wib
        now_wib = get_current_server_time_wib().date()
        y_now, m_now, d_now = date_to_dasarian(now_wib)
        expected_auto_pid = f"{y_now:04d}-{m_now:02d}-{d_now}"

        act_auto = get_active_period()
        assert act_auto["mode"] == "auto"
        assert act_auto["period_id"] == expected_auto_pid

    finally:
        # Restore initial configuration
        set_period_config(initial_cfg.get("mode", "auto"), initial_cfg.get("manual_period_id"), "restore")


# ==============================================================================
# 3. DECOUPLED DATA READINESS & LAGGING AUDIT
# ==============================================================================

def test_decoupled_readiness_audit_historical_vs_lagging():
    """Verify that historical periods are ready/partial while periods with future cutoff are marked LAGGING."""
    # 1. Historical Period 2026-09-das2 (Cutoff 2026-09-10; observations exist up to 2026-10-11)
    readiness_sep2 = get_period_readiness_analysis("2026-09-das2")
    assert readiness_sep2["active_period_id"] == "2026-09-das2"
    assert readiness_sep2["observation_cutoff_date"] == "2026-09-10"
    assert readiness_sep2["is_lagging"] is False
    assert readiness_sep2["evaluation_readiness_status"] in ("READY", "PARTIAL")
    assert readiness_sep2["latest_observation_date"] == "2026-10-11"

    # 2. Lagging Period 2026-10-das3 (Cutoff 2026-10-20; but DB max observation is 2026-10-11)
    readiness_oct3 = get_period_readiness_analysis("2026-10-das3")
    assert readiness_oct3["active_period_id"] == "2026-10-das3"
    assert readiness_oct3["observation_cutoff_date"] == "2026-10-20"
    assert readiness_oct3["latest_observation_date"] == "2026-10-11"
    # Observations in DB (2026-10-11) lag behind cutoff (2026-10-20) by 9 days!
    assert readiness_oct3["is_lagging"] is True
    assert readiness_oct3["evaluation_readiness_status"] == "LAGGING"
    assert readiness_oct3["warning_message"] is not None
    assert "tertinggal" in readiness_oct3["warning_message"].lower() or "lebih baru" in readiness_oct3["warning_message"].lower()


def test_dynamic_preview_snapshot_integrity():
    """Verify that dynamic preview for unsnapshotted period returns 57 stations without corrupting historical snapshots."""
    # Ensure pre-existing snapshot exists before
    snap_sep2_path = SNAPSHOTS_DIR / "2026-09-das2.json"
    assert snap_sep2_path.exists()
    sep2_mtime_before = snap_sep2_path.stat().st_mtime

    # Generate preview for unsnapshotted period 2026-10-das3
    preview = generate_dynamic_snapshot_for_period("2026-10-das3")
    assert preview["period_id"] == "2026-10-das3"
    assert preview["dataset_type"] == "operational_dynamic_preview"
    assert preview["meta"]["total"] == 57
    assert len(preview["items"]) == 57

    # Verify no zero-fill on missing SPI
    pos_manual_items = [s for s in preview["items"] if not s["is_arg"]]
    assert len(pos_manual_items) == 52
    # Verify ARG policy
    arg_items = [s for s in preview["items"] if s["is_arg"]]
    assert len(arg_items) == 5
    for a in arg_items:
        assert a["spi_value"] is None

    # Verify historical snapshot on disk was NOT overwritten
    sep2_mtime_after = snap_sep2_path.stat().st_mtime
    assert sep2_mtime_before == sep2_mtime_after


# ==============================================================================
# 4. DATABASE & PARQUET BASELINES
# ==============================================================================

def test_database_baseline_preservation():
    """Verify baseline row counts in MariaDB cews_db."""
    conn = pymysql.connect(
        host=os.getenv("DB_HOST", "127.0.0.1"),
        user=os.getenv("DB_USER", "root"),
        password=os.getenv("DB_PASSWORD", ""),
        database=os.getenv("DB_NAME", "cews_db"),
        port=int(os.getenv("DB_PORT", 3306))
    )
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM cews_rainfall_daily")
            cnt_daily = cur.fetchone()[0]
            assert cnt_daily == 286085, f"Expected 286,085 daily rainfall rows, got {cnt_daily}"

            cur.execute("SELECT COUNT(*) FROM cews_warning_history")
            cnt_hist = cur.fetchone()[0]
            assert cnt_hist == 2052, f"Expected 2,052 warning history rows, got {cnt_hist}"

            cur.execute("SELECT COUNT(*) FROM stations")
            cnt_stns = cur.fetchone()[0]
            assert cnt_stns == 57, f"Expected 57 stations, got {cnt_stns}"
    finally:
        conn.close()


def test_spi_parquet_checksums():
    """Verify MD5 checksums of all 4 SPI Parquet files."""
    spi_files = {
        "SPI_all_30d.parquet (dasarian)": (RAW_DATA_DIR / "spi" / "dasarian" / "SPI_all_30d.parquet", "503f28589fc2cce6dc06771a932d89f2"),
        "SPI_all_90d.parquet (dasarian)": (RAW_DATA_DIR / "spi" / "dasarian" / "SPI_all_90d.parquet", "b87b4d32fa45aa554b7510f034d538ad"),
        "SPI_all_30d.parquet (harian)": (RAW_DATA_DIR / "spi" / "harian" / "SPI_all_30d.parquet", "2996dce038b1afeeb28d018789044f58"),
        "SPI_all_90d.parquet (harian)": (RAW_DATA_DIR / "spi" / "harian" / "SPI_all_90d.parquet", "44a079d76c1bda1a762b4e4d62b8b936"),
    }
    for name, (path, expected_md5) in spi_files.items():
        assert path.exists(), f"File {name} does not exist at {path}"
        actual_md5 = hashlib.md5(path.read_bytes()).hexdigest()
        assert actual_md5 == expected_md5, f"MD5 mismatch for {name}: expected {expected_md5}, got {actual_md5}"


# ==============================================================================
# 5. LAUNCHER BATCH SCRIPTS
# ==============================================================================

def test_standardized_launcher_files():
    """Verify presence, syntax structure, and isolation of simplified Windows launchers."""
    run_cews = ROOT_DIR / "run_cews.bat"
    stop_cews = ROOT_DIR / "stop_cews.bat"

    # Exactly 2 launchers must exist in root
    assert run_cews.exists(), "run_cews.bat must exist in root"
    assert stop_cews.exists(), "stop_cews.bat must exist in root"

    # Redundant/legacy launchers must NOT be in root
    buka_dash = ROOT_DIR / "buka_dashboard.bat"
    run_demo = ROOT_DIR / "run_cews_demo.bat"
    buka_cews = ROOT_DIR / "buka_dashboard_cews.bat"
    stop_demo = ROOT_DIR / "stop_cews_demo.bat"

    assert not buka_dash.exists(), "buka_dashboard.bat must be archived away from root"
    assert not run_demo.exists(), "run_cews_demo.bat must be archived away from root"
    assert not buka_cews.exists(), "buka_dashboard_cews.bat must be archived away from root"
    assert not stop_demo.exists(), "stop_cews_demo.bat must be archived away from root"

    # Verify they are archived in backups/launcher_archive
    launcher_archive = ROOT_DIR / "backups" / "launcher_archive"
    assert (launcher_archive / "buka_dashboard.bat").exists()
    assert (launcher_archive / "run_cews_demo.bat").exists()
    assert (launcher_archive / "buka_dashboard_cews.bat").exists()
    assert (launcher_archive / "stop_cews_demo.bat").exists()

    # Verify run_cews.bat structure (starts services AND opens browser)
    txt_run = run_cews.read_text(encoding="utf-8")
    assert "%~dp0" in txt_run
    assert "0.0.0.0" in txt_run
    assert "8000" in txt_run
    assert "5173" in txt_run
    assert "logs\\runtime" in txt_run
    assert "http://localhost:5173/" in txt_run
    assert "start " in txt_run

    # Verify stop_cews.bat structure (PID targeted termination, MariaDB preserved)
    txt_stop = stop_cews.read_text(encoding="utf-8")
    assert "%~dp0" in txt_stop
    assert ":8000" in txt_stop
    assert ":5173" in txt_stop
    assert "taskkill /F /T /PID" in txt_stop
    assert "MariaDB" in txt_stop


def test_frontend_build_artifacts():
    """Verify that frontend dist directory contains valid production build."""
    dist_html = ROOT_DIR / "frontend" / "dist" / "index.html"
    assert dist_html.exists(), "Frontend build index.html must exist in frontend/dist"
    assert dist_html.stat().st_size > 500

