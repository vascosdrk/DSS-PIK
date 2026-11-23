"""
backend/period_service.py
DSS-PIK Real-Time & Manual Period Management Service (Paket 1)
Stasiun Meteorologi Raja Haji Fisabilillah — BMKG Kepulauan Riau

Principles:
1. Dynamic Dasarian Calendar based on real-time Asia/Jakarta (WIB) clock.
   - Dasarian I: 1–10
   - Dasarian II: 11–20
   - Dasarian III: 21–end of month (28, 29, 30, or 31)
2. Dual Operating Modes:
   - Mode A (Otomatis / Real-Time): Automatically follows server calendar in Asia/Jakarta.
   - Mode B (Manual / Pilihan Petugas): Explicit officer selection stored server-side.
   - Revertible back to Real-Time anytime.
3. Rolling 10-Dasarian Window:
   - 9 preceding dasarians + 1 active dasarian (exact 10 periods, chronological).
4. Decoupled Calendar Period from Data Readiness:
   - Calendar period is based on real-time clock or manual selection.
   - Data readiness audits actual cews_rainfall_daily and SPI Parquet availability.
   - If observations lag behind cutoff, clear warning status (LAGGING/DATA TERTINGGAL) is issued.
   - No zero-fill, no auto-hijau, no future data leakage.
"""

import json
import calendar
from datetime import datetime, date, timedelta, timezone
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple
import pandas as pd
import numpy as np

from backend.database import get_db
from backend.decision_engine import (
    evaluate_pdkm_full,
    evaluate_pdcht_full,
    arbitrate_final_synthesis
)
from config.paths import (
    PATH_SPI_AUTHORITATIVE,
    PATH_SPI_PARQUET_DASARIAN_90D,
    PATH_STATION_METADATA
)

ROOT_DIR = Path(__file__).resolve().parent.parent
SNAPSHOTS_DIR = ROOT_DIR / "data" / "processed" / "evaluation" / "snapshots"
MANIFEST_PATH = SNAPSHOTS_DIR / "periods_manifest.json"
CONFIG_PATH = ROOT_DIR / "data" / "operational" / "period_config.json"

WIB = timezone(timedelta(hours=7))

ARG_STATION_IDS = {'21010603B', '21010802B', '21020402B', '21040101B', '21710501B'}

MONTH_NAMES_ID = {
    1: "Januari", 2: "Februari", 3: "Maret", 4: "April", 5: "Mei", 6: "Juni",
    7: "Juli", 8: "Agustus", 9: "September", 10: "Oktober", 11: "November", 12: "Desember"
}

MONTH_ABBR_ID = {
    1: "Jan", 2: "Feb", 3: "Mar", 4: "Apr", 5: "Mei", 6: "Jun",
    7: "Jul", 8: "Agu", 9: "Sep", 10: "Okt", 11: "Nov", 12: "Des"
}

DAS_ROMAN = {"das1": "I", "das2": "II", "das3": "III"}


# ==============================================================================
# 1. CALENDAR UTILITIES (WIB / ASIA/JAKARTA)
# ==============================================================================

def get_current_server_time_wib() -> datetime:
    """Return current server time in Asia/Jakarta (WIB, UTC+7)."""
    return datetime.now(WIB)


def get_last_day_of_month(year: int, month: int) -> int:
    """Return last day of month considering leap years."""
    return calendar.monthrange(year, month)[1]


def date_to_dasarian(d: date) -> Tuple[int, int, str]:
    """Convert a calendar date to (year, month, dasarian_str)."""
    if d.day <= 10:
        das = "das1"
    elif d.day <= 20:
        das = "das2"
    else:
        das = "das3"
    return (d.year, d.month, das)


def format_period_label(year: int, month: int, das: str) -> str:
    """Format e.g. Dasarian II September 2026."""
    return f"Dasarian {DAS_ROMAN.get(das, 'I')} {MONTH_NAMES_ID[month]} {year}"


def get_dasarian_date_range(year: int, month: int, das: str) -> str:
    """Return human readable date range e.g. 11–20 September 2026."""
    m_name = MONTH_NAMES_ID[month]
    if das == "das1":
        return f"1–10 {m_name} {year}"
    elif das == "das2":
        return f"11–20 {m_name} {year}"
    else:
        last_d = get_last_day_of_month(year, month)
        return f"21–{last_d} {m_name} {year}"


def get_dasarian_dates(year: int, month: int, das: str) -> Tuple[date, date]:
    """Return (target_start, target_end) date objects."""
    if das == "das1":
        return date(year, month, 1), date(year, month, 10)
    elif das == "das2":
        return date(year, month, 11), date(year, month, 20)
    else:
        last_d = get_last_day_of_month(year, month)
        return date(year, month, 21), date(year, month, last_d)


def get_observation_cutoff_date(year: int, month: int, das: str) -> date:
    """
    Authoritative Cutoff Dates:
    - Dasarian I (1–10): cutoff is last day of previous month
    - Dasarian II (11–20): cutoff is day 10 of current month
    - Dasarian III (21–end): cutoff is day 20 of current month
    """
    if das == "das1":
        if month == 1:
            prev_y, prev_m = year - 1, 12
        else:
            prev_y, prev_m = year, month - 1
        last_d = get_last_day_of_month(prev_y, prev_m)
        return date(prev_y, prev_m, last_d)
    elif das == "das2":
        return date(year, month, 10)
    else:
        return date(year, month, 20)


def get_forecast_issue_date(year: int, month: int, das: str) -> date:
    """
    Issue date for ECMWF forecast:
    - Dasarian I: 2 days before start
    - Dasarian II: 9th of month
    - Dasarian III: 19th of month
    """
    if das == "das1":
        cutoff = get_observation_cutoff_date(year, month, das)
        return cutoff - timedelta(days=1)
    elif das == "das2":
        return date(year, month, 9)
    else:
        return date(year, month, 19)


def get_prev_dasarian_label(year: int, month: int, das: str) -> str:
    """Label for previous dasarian rainfall column e.g. CH Das I Sep (mm)."""
    prev_y, prev_m, prev_das = get_previous_dasarian(year, month, das)
    rom = DAS_ROMAN.get(prev_das, "I")
    abbr = MONTH_ABBR_ID.get(prev_m, "")
    return f"CH Das {rom} {abbr} (mm)"


def get_spi_target_date_for_period(period_id: str) -> Optional[str]:
    """
    Mandated Temporal Mapping:
    - Target Dasarian I -> SPI Dasarian III prev month (YYYY-PrevMo-21)
    - Target Dasarian II -> SPI Dasarian I same month (YYYY-MM-01)
    - Target Dasarian III -> SPI Dasarian II same month (YYYY-MM-11)
    """
    try:
        parts = period_id.strip().split("-")
        year = int(parts[0])
        month = int(parts[1])
        das = parts[2].lower()
        if das == "das2":
            return f"{year:04d}-{month:02d}-01"
        elif das == "das3":
            return f"{year:04d}-{month:02d}-11"
        elif das == "das1":
            if month == 1:
                prev_year, prev_month = year - 1, 12
            else:
                prev_year, prev_month = year, month - 1
            return f"{prev_year:04d}-{prev_month:02d}-21"
    except Exception:
        return None
    return None


def get_previous_dasarian(year: int, month: int, das: str) -> Tuple[int, int, str]:
    """Get the immediate prior dasarian tuple."""
    if das == "das3":
        return (year, month, "das2")
    elif das == "das2":
        return (year, month, "das1")
    else:
        if month == 1:
            return (year - 1, 12, "das3")
        else:
            return (year, month - 1, "das3")


def get_next_dasarian(year: int, month: int, das: Any) -> Tuple[int, int, str]:
    """Get the immediate next dasarian tuple."""
    das_str = str(das).lower().strip()
    if das_str in ("das1", "1"):
        return (year, month, "das2")
    elif das_str in ("das2", "2"):
        return (year, month, "das3")
    else:
        if month == 12:
            return (year + 1, 1, "das1")
        else:
            return (year, month + 1, "das1")


def generate_10_dasarian_window(year: int, month: int, das: str) -> List[Tuple[int, int, str]]:
    """
    Generates exact 10 dasarians ending at (year, month, das):
    9 preceding dasarians + 1 active dasarian, sorted chronologically.
    """
    window = [(year, month, das)]
    curr_y, curr_m, curr_d = year, month, das
    for _ in range(9):
        curr_y, curr_m, curr_d = get_previous_dasarian(curr_y, curr_m, curr_d)
        window.insert(0, (curr_y, curr_m, curr_d))
    return window


# ==============================================================================
# 2. SERVER-SIDE CONFIGURATION PERSISTENCE
# ==============================================================================

def get_period_config() -> Dict[str, Any]:
    """
    Load persistent period configuration from server JSON.
    Guarantees consistency across localhost and LAN clients.
    """
    if CONFIG_PATH.exists():
        try:
            with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                cfg = json.load(f)
                mode = cfg.get("mode", "auto")
                pid = cfg.get("manual_period_id")
                return {
                    "mode": mode if mode in ("auto", "manual") else "auto",
                    "manual_period_id": pid,
                    "updated_at": cfg.get("updated_at"),
                    "updated_by": cfg.get("updated_by", "system")
                }
        except Exception as e:
            print(f"[Warning] Failed to read period_config.json: {e}")
    return {"mode": "auto", "manual_period_id": None, "updated_at": None, "updated_by": "default"}


def set_period_config(mode: str, manual_period_id: Optional[str] = None, operator_name: str = "operator") -> Dict[str, Any]:
    """
    Persist period selection server-side atomically.
    mode: 'auto' (real-time) or 'manual'
    manual_period_id: e.g. '2026-09-das2' (required if mode is manual)
    """
    CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    clean_mode = "manual" if mode == "manual" else "auto"
    clean_pid = manual_period_id.strip() if manual_period_id else None

    # Validate PID format if manual
    if clean_mode == "manual":
        if not clean_pid:
            clean_mode = "auto"
        else:
            parts = clean_pid.split("-")
            if len(parts) != 3 or parts[2].lower() not in ("das1", "das2", "das3"):
                clean_mode = "auto"
                clean_pid = None

    now_iso = get_current_server_time_wib().isoformat()
    config_data = {
        "mode": clean_mode,
        "manual_period_id": clean_pid if clean_mode == "manual" else None,
        "updated_at": now_iso,
        "updated_by": operator_name
    }

    # Write atomically
    temp_path = CONFIG_PATH.with_suffix(".tmp")
    with open(temp_path, "w", encoding="utf-8") as f:
        json.dump(config_data, f, indent=2)
    temp_path.replace(CONFIG_PATH)

    return config_data


# ==============================================================================
# 3. ACTIVE PERIOD & 10-DASARIAN WINDOW
# ==============================================================================

def get_active_period() -> Dict[str, Any]:
    """
    Resolve active period considering server time and configuration mode.
    """
    cfg = get_period_config()
    server_now = get_current_server_time_wib()
    mode = cfg.get("mode", "auto")
    manual_pid = cfg.get("manual_period_id")

    if mode == "manual" and manual_pid:
        try:
            parts = manual_pid.split("-")
            year = int(parts[0])
            month = int(parts[1])
            das = parts[2].lower()
            pid = f"{year:04d}-{month:02d}-{das}"
        except Exception:
            # Fallback to real-time auto
            year, month, das = date_to_dasarian(server_now.date())
            pid = f"{year:04d}-{month:02d}-{das}"
            mode = "auto"
    else:
        year, month, das = date_to_dasarian(server_now.date())
        pid = f"{year:04d}-{month:02d}-{das}"
        mode = "auto"

    t_start, t_end = get_dasarian_dates(year, month, das)
    c_cutoff = get_observation_cutoff_date(year, month, das)
    f_issue = get_forecast_issue_date(year, month, das)

    return {
        "period_id": pid,
        "year": year,
        "month": month,
        "dasarian": das,
        "label": format_period_label(year, month, das),
        "date_range": get_dasarian_date_range(year, month, das),
        "target_start": t_start.strftime("%Y-%m-%d"),
        "target_end": t_end.strftime("%Y-%m-%d"),
        "observation_cutoff": c_cutoff.strftime("%Y-%m-%d"),
        "forecast_issue": f_issue.strftime("%Y-%m-%d"),
        "prev_dasarian_label": get_prev_dasarian_label(year, month, das),
        "mode": mode,
        "server_time": server_now.isoformat(),
        "server_date": server_now.strftime("%Y-%m-%d"),
    }


def get_10_dasarian_window_items() -> Tuple[str, str, List[Dict[str, Any]]]:
    """
    Builds the 10-dasarian window ending at current active period.
    Returns (active_period_id, mode, list_of_period_items).
    """
    active = get_active_period()
    act_pid = active["period_id"]
    mode = active["mode"]

    window_tuples = generate_10_dasarian_window(active["year"], active["month"], active["dasarian"])

    # Load any future target dasarians stored in cews_forecast_snapshot
    stored_fc_tuples = set()
    try:
        with get_db() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT DISTINCT target_year, target_month, target_dasarian 
                    FROM cews_forecast_snapshot 
                    WHERE target_dasarian IN (1, 2, 3)
                    ORDER BY target_year, target_month, target_dasarian
                """)
                for r in cur.fetchall():
                    stored_fc_tuples.add((r["target_year"], r["target_month"], f"das{r['target_dasarian']}"))
    except Exception:
        pass

    # Ensure at least the upcoming 3 dasarians from active period are present
    curr_y, curr_m, curr_d = active["year"], active["month"], active["dasarian"]
    upcoming_tuples = []
    for _ in range(3):
        curr_y, curr_m, curr_d = get_next_dasarian(curr_y, curr_m, curr_d)
        upcoming_tuples.append((curr_y, curr_m, curr_d))

    def tuple_key(t):
        y, m, d = t
        d_num = int(d.replace("das", "")) if isinstance(d, str) else int(d)
        return (y, m, d_num)

    all_set = set(window_tuples).union(stored_fc_tuples).union(upcoming_tuples)
    all_tuples = sorted(list(all_set), key=tuple_key)
    
    # Load existing snapshots metadata from disk/manifest
    manifest_map = {}
    if MANIFEST_PATH.exists():
        try:
            with open(MANIFEST_PATH, "r", encoding="utf-8") as f:
                for item in json.load(f):
                    manifest_map[item["period_id"]] = item
        except Exception:
            pass

    act_key = tuple_key((active["year"], active["month"], active["dasarian"]))

    periods_items = []
    for y, m, d in all_tuples:
        is_fc = tuple_key((y, m, d)) > act_key
        pid = f"{y:04d}-{m:02d}-{d}"
        t_start, t_end = get_dasarian_dates(y, m, d)
        c_cutoff = get_observation_cutoff_date(y, m, d)
        f_issue = get_forecast_issue_date(y, m, d)
        lbl = f"{format_period_label(y, m, d)} [Prakiraan]" if is_fc else format_period_label(y, m, d)
        d_range = get_dasarian_date_range(y, m, d)
        prev_lbl = get_prev_dasarian_label(y, m, d)

        # Check if snapshot file exists
        snap_file = SNAPSHOTS_DIR / f"{pid}.json"
        has_snap = snap_file.exists()
        
        summary = {"total": 57, "awas": 0, "siaga": 0, "waspada": 0, "aman": 0, "incomplete": 0}
        has_complete = False

        if has_snap:
            try:
                with open(snap_file, "r", encoding="utf-8") as f:
                    s_data = json.load(f)
                    raw_s = s_data.get("summary", {})
                    summary = {
                        "total": int(raw_s.get("total", raw_s.get("TOTAL", 57))),
                        "awas": int(raw_s.get("awas", raw_s.get("AWAS", 0))),
                        "siaga": int(raw_s.get("siaga", raw_s.get("SIAGA", 0))),
                        "waspada": int(raw_s.get("waspada", raw_s.get("WASPADA", 0))),
                        "aman": int(raw_s.get("aman", raw_s.get("AMAN", raw_s.get("normal", raw_s.get("NORMAL", 0))))),
                        "incomplete": int(raw_s.get("incomplete", raw_s.get("INCOMPLETE", 0))),
                    }
                    has_complete = bool(s_data.get("has_complete_data", True))
            except Exception:
                pass
        elif pid in manifest_map:
            raw_s = manifest_map[pid].get("summary", {})
            summary = {
                "total": int(raw_s.get("total", raw_s.get("TOTAL", 57))),
                "awas": int(raw_s.get("awas", raw_s.get("AWAS", 0))),
                "siaga": int(raw_s.get("siaga", raw_s.get("SIAGA", 0))),
                "waspada": int(raw_s.get("waspada", raw_s.get("WASPADA", 0))),
                "aman": int(raw_s.get("aman", raw_s.get("AMAN", raw_s.get("normal", raw_s.get("NORMAL", 0))))),
                "incomplete": int(raw_s.get("incomplete", raw_s.get("INCOMPLETE", 0))),
            }
            has_complete = bool(manifest_map[pid].get("has_complete_data", True))
        else:
            # Unsnapshotted period -> default incomplete summary
            summary = {"total": 57, "awas": 0, "siaga": 0, "waspada": 0, "aman": 0, "incomplete": 57}
            has_complete = False

        is_def = (pid == act_pid)

        periods_items.append({
            "period_id": pid,
            "label": lbl,
            "date_range": d_range,
            "target_start": t_start.strftime("%Y-%m-%d"),
            "target_end": t_end.strftime("%Y-%m-%d"),
            "observation_cutoff": c_cutoff.strftime("%Y-%m-%d"),
            "forecast_issue": f_issue.strftime("%Y-%m-%d"),
            "prev_dasarian_label": prev_lbl,
            "is_default": is_def,
            "is_forecast": is_fc,
            "has_complete_data": has_complete,
            "has_snapshot": has_snap,
            "summary": summary
        })

    return act_pid, mode, periods_items


# ==============================================================================
# 4. DECOUPLED DATA READINESS AUDIT
# ==============================================================================

def get_period_readiness_analysis(target_period_id: Optional[str] = None) -> Dict[str, Any]:
    """
    Decoupled data readiness audit.
    Calendar period is determined by system/manual.
    Readiness is determined by actual DB observation dates, SPI Parquet, and ECMWF.
    """
    active = get_active_period()
    pid = (target_period_id or active["period_id"]).strip()

    try:
        parts = pid.split("-")
        year = int(parts[0])
        month = int(parts[1])
        das = parts[2].lower()
    except Exception:
        year, month, das = active["year"], active["month"], active["dasarian"]
        pid = active["period_id"]

    label = format_period_label(year, month, das)
    date_range = get_dasarian_date_range(year, month, das)
    c_cutoff = get_observation_cutoff_date(year, month, das)
    c_cutoff_str = c_cutoff.strftime("%Y-%m-%d")
    spi_target_date = get_spi_target_date_for_period(pid)
    f_issue = get_forecast_issue_date(year, month, das).strftime("%Y-%m-%d")

    # 1. Query latest observation in cews_rainfall_daily
    max_obs_date = None
    total_stns = 57
    latest_stns_count = 0
    with get_db() as conn:
        with conn.cursor() as cur:
            # Only consider actual physical observations on or before server current date (ignoring spurious future anomaly dates)
            cur.execute("""
                SELECT 
                    MAX(observation_date) AS max_date,
                    COUNT(DISTINCT station_id) AS total_stations
                FROM cews_rainfall_daily
                WHERE observation_date <= CURDATE()
                  AND obs_status IN ('OBSERVED_VALID', 'OBSERVED_ZERO', 'TTU', 'CORRECTED');
            """)
            db_res = cur.fetchone()
            if db_res and db_res["max_date"]:
                max_obs_date = db_res["max_date"]
                cur.execute("""
                    SELECT COUNT(DISTINCT station_id) as cnt
                    FROM cews_rainfall_daily
                    WHERE observation_date = %s;
                """, (max_obs_date,))
                latest_stns_count = cur.fetchone()["cnt"]

    max_obs_str = max_obs_date.strftime("%Y-%m-%d") if max_obs_date else "TIDAK_TERSEDIA"

    # 2. Query station data breakdown specifically on cutoff date
    status_counts = {"OBSERVED_VALID": 0, "OBSERVED_ZERO": 0, "TTU": 0, "MISSING": 0, "NO_RECORD": 0}
    cutoff_stns_data = 0
    cutoff_stns_missing = 0

    if max_obs_date:
        with get_db() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT 
                        s.station_id,
                        r.obs_status,
                        r.rainfall_mm
                    FROM stations s
                    LEFT JOIN cews_rainfall_daily r 
                        ON s.station_id = r.station_id AND r.observation_date = %s
                """, (c_cutoff_str,))
                cutoff_rows = cur.fetchall()

        total_stns = len(cutoff_rows)
        for r in cutoff_rows:
            st = r["obs_status"]
            if st is None:
                status_counts["NO_RECORD"] += 1
                cutoff_stns_missing += 1
            elif st in ("OBSERVED_VALID", "VALID"):
                status_counts["OBSERVED_VALID"] += 1
                cutoff_stns_data += 1
            elif st == "OBSERVED_ZERO":
                status_counts["OBSERVED_ZERO"] += 1
                cutoff_stns_data += 1
            elif st == "TTU":
                status_counts["TTU"] += 1
                cutoff_stns_data += 1
            elif "MISSING" in st:
                status_counts["MISSING"] += 1
                cutoff_stns_missing += 1
            else:
                status_counts["NO_RECORD"] += 1
                cutoff_stns_missing += 1

    # 3. SPI Availability
    spi_30_ok = False
    spi_90_ok = False
    if spi_target_date:
        try:
            df30 = pd.read_parquet(PATH_SPI_AUTHORITATIVE)
            dt_target = pd.to_datetime(spi_target_date)
            spi_30_ok = (dt_target in df30.index) or any(d <= dt_target for d in df30.index)
        except Exception:
            pass

        try:
            df90 = pd.read_parquet(PATH_SPI_PARQUET_DASARIAN_90D)
            dt_target = pd.to_datetime(spi_target_date)
            spi_90_ok = (dt_target in df90.index) or any(d <= dt_target for d in df90.index)
        except Exception:
            pass

    # 4. Forecast Availability
    fc_ok = False
    try:
        td_num = int(das.replace("das", ""))
        with get_db() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT COUNT(*) as cnt 
                    FROM cews_forecast_snapshot 
                    WHERE target_year = %s AND target_month = %s AND target_dasarian = %s;
                """, (year, month, td_num))
                cnt_row = cur.fetchone()
                fc_ok = bool(cnt_row and cnt_row["cnt"] > 0)
    except Exception:
        pass

    # 5. Synthesize Readiness & Lagging Status
    is_lagging = False
    reasons = []
    coverage_pct = round((cutoff_stns_data / total_stns) * 100.0, 1) if total_stns > 0 else 0.0

    if not max_obs_date:
        status = "NOT_READY"
        reasons.append("Tidak ada data observasi di database cews_rainfall_daily.")
    elif max_obs_date < c_cutoff:
        is_lagging = True
        status = "LAGGING"
        days_lag = (c_cutoff - max_obs_date).days
        reasons.append(
            f"Data observasi curah hujan di database (terakhir {max_obs_str}) tertinggal {days_lag} hari "
            f"dari batas cutoff evaluasi {c_cutoff_str} untuk {label}."
        )
        reasons.append("Evaluasi operasional belum lengkap. Input curah hujan harian terbaru diperlukan.")
    else:
        # Observations up to cutoff date exist
        if cutoff_stns_data >= 50 and spi_30_ok:
            status = "READY"
            reasons.append(f"Data observasi curah hujan lengkap ({cutoff_stns_data}/{total_stns} stasiun) pada cutoff {c_cutoff_str}.")
            reasons.append(f"Data SPI 30D tersedia untuk tanggal target {spi_target_date}.")
        elif cutoff_stns_data >= 30:
            status = "PARTIAL"
            reasons.append(f"Sebagian data stasiun tersedia ({cutoff_stns_data}/{total_stns} stasiun) pada cutoff {c_cutoff_str}.")
            if not spi_30_ok:
                reasons.append(f"Data SPI 30D belum tersedia pada tanggal target {spi_target_date}.")
        else:
            status = "NOT_READY"
            reasons.append(f"Cakupan observasi belum mencukupi ({cutoff_stns_data}/{total_stns} stasiun) pada cutoff {c_cutoff_str}.")

    # Format warning message if lagging or not ready
    warning_message = None
    if is_lagging:
        warning_message = (
            f"Perhatian Operasional: Periode aktif ({label}) lebih baru daripada data observasi terakhir "
            f"di database ({max_obs_str}). Hasil evaluasi berstatus data parsial/belum lengkap."
        )
    elif status == "PARTIAL":
        warning_message = f"Peringatan: Evaluasi {label} berjalan dengan data parsial ({coverage_pct}% stasiun lengkap)."

    return {
        "active_period_id": pid,
        "active_period_label": label,
        "active_period_range": date_range,
        "selection_mode": active["mode"],
        "server_time": active["server_time"],
        "latest_observation_date": max_obs_str,
        "latest_observation_station_count": latest_stns_count,
        "total_stations": total_stns,
        "observation_cutoff_date": c_cutoff_str,
        "stations_with_data_on_cutoff": cutoff_stns_data,
        "stations_with_missing_on_cutoff": cutoff_stns_missing,
        "cutoff_status_counts": status_counts,
        "coverage_percentage": coverage_pct,
        "spi_target_date": spi_target_date,
        "forecast_issue_date": f_issue,
        "spi_30d_available": spi_30_ok,
        "spi_90d_available": spi_90_ok,
        "forecast_available": fc_ok,
        "evaluation_readiness_status": status,
        "is_lagging": is_lagging,
        "readiness_reasons": reasons,
        "warning_message": warning_message,
        # Backward compatibility fields
        "candidate_period_id": pid,
        "candidate_period_label": label,
    }


# ==============================================================================
# 5. DYNAMIC PREVIEW SNAPSHOT FOR UNSNAPSHOTTED PERIODS
# ==============================================================================

def generate_dynamic_snapshot_for_period(period_id: str) -> Dict[str, Any]:
    """
    Constructs an authoritative on-the-fly preview snapshot for a period that
    does not have a pre-saved snapshot JSON file.
    Does NOT overwrite any historical snapshots.
    Honors:
    - Zero lookahead bias
    - Strict observation cutoff
    - Honest partial evaluation (no zero-fill, no auto-hijau)
    - ARG policy (HTH only, exempt from SPI)
    """
    parts = period_id.strip().split("-")
    year = int(parts[0])
    month = int(parts[1])
    das = parts[2].lower()

    label = format_period_label(year, month, das)
    date_range = get_dasarian_date_range(year, month, das)
    t_start, t_end = get_dasarian_dates(year, month, das)
    is_forecast_period = t_end > get_current_server_time_wib().date()
    c_cutoff = get_observation_cutoff_date(year, month, das)
    c_cutoff_str = c_cutoff.strftime("%Y-%m-%d")
    f_issue = get_forecast_issue_date(year, month, das).strftime("%Y-%m-%d")
    prev_das_lbl = get_prev_dasarian_label(year, month, das)
    spi_target_date = get_spi_target_date_for_period(period_id)

    # 1. Fetch stations master
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT station_id, station_name, kabupaten, province, region,
                       latitude, longitude, elevation_m, nozom_prov
                FROM stations
                ORDER BY kabupaten, station_name
            """)
            stations = cur.fetchall()

            # Query observation status on cutoff date
            cur.execute("""
                SELECT station_id, obs_status, rainfall_mm, observation_date
                FROM cews_rainfall_daily
                WHERE observation_date = %s
            """, (c_cutoff_str,))
            cutoff_obs = {r["station_id"]: r for r in cur.fetchall()}

            # Query latest rain date (rainfall >= 1.0mm) up to cutoff date
            cur.execute("""
                SELECT station_id, MAX(observation_date) as last_rain
                FROM cews_rainfall_daily
                WHERE observation_date <= %s AND rainfall_mm >= 1.0
                GROUP BY station_id
            """, (c_cutoff_str,))
            last_rain_map = {r["station_id"]: r["last_rain"].strftime("%Y-%m-%d") for r in cur.fetchall() if r["last_rain"]}

            # Query latest recorded observation date per station up to cutoff
            cur.execute("""
                SELECT station_id, MAX(observation_date) as max_date
                FROM cews_rainfall_daily
                WHERE observation_date <= %s
                GROUP BY station_id
            """, (c_cutoff_str,))
            latest_obs_map = {r["station_id"]: r["max_date"].strftime("%Y-%m-%d") for r in cur.fetchall() if r["max_date"]}

    # 2. SPI Data (Dasarian 30D & 90D)
    # If the target date is in the DataFrame, use it; otherwise, use the latest available date <= target_date
    spi30_row = None
    actual_spi30_date = None
    if spi_target_date:
        try:
            df30 = pd.read_parquet(PATH_SPI_AUTHORITATIVE)
            dt = pd.to_datetime(spi_target_date)
            if dt in df30.index:
                spi30_row = df30.loc[dt]
                actual_spi30_date = spi_target_date
            else:
                prior_dates = [d for d in df30.index if d <= dt]
                if prior_dates:
                    best_d = max(prior_dates)
                    spi30_row = df30.loc[best_d]
                    actual_spi30_date = best_d.strftime("%Y-%m-%d") if hasattr(best_d, "strftime") else str(best_d)[:10]
        except Exception as e:
            print(f"[Warning] Failed to load SPI 30D parquet: {e}")

    spi90_row = None
    actual_spi90_date = None
    if spi_target_date:
        try:
            df90 = pd.read_parquet(PATH_SPI_PARQUET_DASARIAN_90D)
            dt = pd.to_datetime(spi_target_date)
            if dt in df90.index:
                spi90_row = df90.loc[dt]
                actual_spi90_date = spi_target_date
            else:
                prior_dates = [d for d in df90.index if d <= dt]
                if prior_dates:
                    best_d = max(prior_dates)
                    spi90_row = df90.loc[best_d]
                    actual_spi90_date = best_d.strftime("%Y-%m-%d") if hasattr(best_d, "strftime") else str(best_d)[:10]
        except Exception as e:
            print(f"[Warning] Failed to load SPI 90D parquet: {e}")

    # 3. Forecast snapshot probabilities (latest eligible vintage for target period)
    fc_prob_map = {}
    fc_monthly_map = {}
    try:
        t_das_int = int(das.replace("das", ""))
        with get_db() as conn:
            with conn.cursor() as cur:
                # 3a. Dasarian probabilities
                cur.execute("""
                    SELECT issue_date, station_id, forecast_parameter, probability_value
                    FROM cews_forecast_snapshot
                    WHERE target_year = %s AND target_month = %s AND target_dasarian = %s
                      AND forecast_resolution = 'DASARIAN'
                    ORDER BY issue_date DESC
                """, (year, month, t_das_int))
                fc_rows = cur.fetchall()
                if fc_rows:
                    distinct_iss = []
                    for r in fc_rows:
                        if r["issue_date"] not in distinct_iss:
                            distinct_iss.append(r["issue_date"])
                    eligible_iss = [iss for iss in distinct_iss if iss <= c_cutoff] if not is_forecast_period else distinct_iss
                    selected_iss = eligible_iss[0] if eligible_iss else None
                    if selected_iss is not None:
                        f_issue = selected_iss.strftime("%Y-%m-%d") if hasattr(selected_iss, "strftime") else str(selected_iss)
                        for r in fc_rows:
                            if r["issue_date"] == selected_iss:
                                s_id = str(r["station_id"]).strip().upper()
                                if s_id not in fc_prob_map:
                                    fc_prob_map[s_id] = {}
                                fc_prob_map[s_id][r["forecast_parameter"]] = float(r["probability_value"]) if r["probability_value"] is not None else None

                # 3b. Monthly probabilities
                cur.execute("""
                    SELECT issue_date, station_id, forecast_parameter, probability_value
                    FROM cews_forecast_snapshot
                    WHERE target_year = %s AND target_month = %s AND target_dasarian IN (0, 1)
                      AND forecast_resolution = 'BULANAN'
                    ORDER BY issue_date DESC
                """, (year, month))
                fm_rows = cur.fetchall()
                if fm_rows:
                    distinct_m_iss = []
                    for r in fm_rows:
                        if r["issue_date"] not in distinct_m_iss:
                            distinct_m_iss.append(r["issue_date"])
                    eligible_m_iss = [iss for iss in distinct_m_iss if iss <= c_cutoff] if not is_forecast_period else distinct_m_iss
                    selected_m_iss = eligible_m_iss[0] if eligible_m_iss else None
                    if selected_m_iss is not None:
                        for r in fm_rows:
                            if r["issue_date"] == selected_m_iss:
                                s_id = str(r["station_id"]).strip().upper()
                                if s_id not in fc_monthly_map:
                                    fc_monthly_map[s_id] = {}
                                fc_monthly_map[s_id][r["forecast_parameter"]] = float(r["probability_value"]) if r["probability_value"] is not None else None
    except Exception:
        pass

    items = []
    summary_counts = {"TOTAL": len(stations), "NORMAL": 0, "WASPADA": 0, "SIAGA": 0, "AWAS": 0, "INCOMPLETE": 0}

    for s in stations:
        sid = s["station_id"]
        is_arg = sid in ARG_STATION_IDS
        c_row = cutoff_obs.get(sid)
        last_rain = last_rain_map.get(sid)
        last_obs = latest_obs_map.get(sid, "TIDAK_TERSEDIA")

        # HTH calculation:
        # If observation is not available on cutoff date, HTH is uncertain / None
        hth_days = None
        hth_uncertain = True
        hth_category = "TIDAK_TERSEDIA"

        if c_row is not None and c_row.get("obs_status") in ("OBSERVED_VALID", "OBSERVED_ZERO", "TTU", "CORRECTED"):
            # We have valid observation on cutoff date!
            # Calculate consecutive days with rainfall < 1.0mm backwards from cutoff
            hth_uncertain = False
            if last_rain:
                try:
                    lr_dt = datetime.strptime(last_rain, "%Y-%m-%d").date()
                    hth_days = max(0, (c_cutoff - lr_dt).days)
                except Exception:
                    hth_days = 0
            else:
                hth_days = 30  # Fallback if never rained in record window

            if hth_days <= 20:
                hth_category = "0 - 20 Hari"
            elif hth_days <= 30:
                hth_category = "21 - 30 Hari"
            elif hth_days <= 60:
                hth_category = "31 - 60 Hari"
            else:
                hth_category = "> 60 Hari"

        # SPI
        s_val_30 = None
        s_val_90 = None
        if not is_arg:
            if spi30_row is not None and sid in spi30_row.index and pd.notna(spi30_row[sid]):
                s_val_30 = float(spi30_row[sid])
            if spi90_row is not None and sid in spi90_row.index and pd.notna(spi90_row[sid]):
                s_val_90 = float(spi90_row[sid])

        # Probability indicators from active forecast snapshot
        stn_probs = fc_prob_map.get(sid, {})
        stn_m_probs = fc_monthly_map.get(sid, {})
        pb20_val = None if is_arg else stn_probs.get("pb20", stn_probs.get("prob_below20"))
        pa150_val = None if is_arg else stn_probs.get("pa150", stn_probs.get("prob_above150"))
        pa200_val = None if is_arg else stn_probs.get("pa200", stn_probs.get("prob_above200"))
        pa300_val = None if is_arg else stn_probs.get("pa300", stn_probs.get("prob_above300"))
        pm300_val = None if is_arg else stn_m_probs.get("pa300", stn_m_probs.get("prob_month_above300"))
        pm400_val = None if is_arg else stn_m_probs.get("pa400", stn_m_probs.get("prob_month_above400"))
        pm500_val = None if is_arg else stn_m_probs.get("pa500", stn_m_probs.get("prob_month_above500"))

        # Evaluate PDKM & PDCHT using authoritative decision engine
        # SPI 90D is the authoritative drought indicator; SPI 30D is purely informational
        d_res = evaluate_pdkm_full(
            hth_days=hth_days,
            pb20=pb20_val,
            spi_val=s_val_90,
            hth_uncertain=hth_uncertain,
            is_arg=is_arg,
            target_label=label
        )
        r_res = evaluate_pdcht_full(
            pa150=pa150_val,
            pa200=pa200_val,
            pa300=pa300_val,
            pm300=pm300_val,
            pm400=pm400_val,
            pm500=pm500_val,
            is_arg=is_arg,
            target_label=label
        )
        synth = arbitrate_final_synthesis(d_res, r_res)

        eval_complete = synth["evaluation_complete"]
        if is_arg and hth_days is not None:
            eval_complete = True
            eval_status = "COMPLETE"
        elif eval_complete:
            eval_status = "COMPLETE"
        elif synth["final_level"] > 0:
            eval_status = "PARTIAL"
        else:
            eval_status = "INCOMPLETE"

        lvl_up = synth["final_status"].upper()
        if eval_status == "INCOMPLETE":
            summary_counts["INCOMPLETE"] += 1
        elif lvl_up in summary_counts:
            summary_counts[lvl_up] += 1
        else:
            summary_counts["NORMAL"] += 1

        items.append({
            "station_id": sid,
            "station_name": s["station_name"],
            "kabupaten": s["kabupaten"],
            "latitude": float(s["latitude"]),
            "longitude": float(s["longitude"]),
            "target_warning_period": label,
            "target_period_start": t_start.strftime("%Y-%m-%d"),
            "target_period_end": t_end.strftime("%Y-%m-%d"),
            "hazard_type": synth["hazard_type"],
            "warning_level": synth["final_status"],
            "pdkm_status": d_res["status"],
            "pdkm_level": d_res["level"],
            "pdkm_reasons": d_res["reasons"],
            "pdcht_status": r_res["status"],
            "pdcht_level": r_res["level"],
            "pdcht_reasons": r_res["reasons"],
            "confidence_level": "MEDIUM" if eval_complete else "LOW",
            "data_quality_status": "VALID" if eval_complete else "DATA_PARSIAL",
            "updated_at": get_current_server_time_wib().isoformat(),
            "is_arg": is_arg,
            "evaluation_status": eval_status,
            "prev_dasarian_rainfall_mm": None,
            "prev_dasarian_label": prev_das_lbl,
            "spi_value": s_val_30,
            "spi_value_90d": s_val_90,
            "spi_evidence_date": actual_spi30_date or spi_target_date,
            "spi_evidence_date_90d": actual_spi90_date or spi_target_date,
            "spi_validation_status": "VERIFIED" if s_val_30 is not None else ("TIDAK_TERSEDIA_ARG" if is_arg else "DATA_KOSONG"),
            "spi_validation_status_90d": "VERIFIED" if s_val_90 is not None else ("TIDAK_TERSEDIA_ARG" if is_arg else "DATA_KOSONG"),
            "warning_reasons": synth["reason"],
            "narrative": synth["reason"],
            "last_observation_date": last_obs,
            "hth_days": hth_days,
            "hth_days_current": hth_days,
            "hth_category": hth_category,
            "hth_uncertain": hth_uncertain,
            "last_rain_date": last_rain,
            "forecast_pb20": pb20_val,
            "forecast_pa150": pa150_val,
            "forecast_pa200": pa200_val,
            "forecast_pa300": pa300_val,
            "monthly_pa300": pm300_val,
            "monthly_pa400": pm400_val,
            "monthly_pa500": pm500_val,
        })

    has_comp = (summary_counts["INCOMPLETE"] == 0)

    return {
        "period_id": period_id,
        "label": label,
        "date_range": date_range,
        "dataset_type": "operational_dynamic_preview",
        "observation_cutoff": c_cutoff_str,
        "forecast_issue": f_issue,
        "target_start": t_start.strftime("%Y-%m-%d"),
        "target_end": t_end.strftime("%Y-%m-%d"),
        "prev_dasarian_label": prev_das_lbl,
        "summary": summary_counts,
        "has_complete_data": has_comp,
        "is_candidate_preview": True,
        "items": items,
        "meta": {
            "total": len(items),
            "period_id": period_id,
            "period_label": label,
            "date_range": date_range,
            "dataset_type": "operational_dynamic_preview",
            "observation_cutoff": c_cutoff_str,
            "forecast_issue": f_issue,
            "target_period_start": t_start.strftime("%Y-%m-%d"),
            "target_period_end": t_end.strftime("%Y-%m-%d"),
            "prev_dasarian_label": prev_das_lbl,
        }
    }
