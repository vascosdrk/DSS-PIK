"""
backend/data_service.py
Service layer for DSS-PIK Data Center:
1. Station Information & Metadata (Informasi Pos)
2. SPI Data Center (Dasarian 30d/90d, Harian 30d/90d)
3. Forecast Probability Data Center
4. Unified Data Download & Export Engine (CSV & XLSX)
"""

import io
import csv
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Optional, List, Dict, Any, Tuple
import pandas as pd
import openpyxl
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side

from backend.database import get_db
from config.paths import PATH_STATION_METADATA

ROOT_DIR = Path(__file__).resolve().parent.parent
SPI_RAW_DIR = ROOT_DIR / "data" / "raw" / "spi"
SNAPSHOTS_DIR = ROOT_DIR / "data" / "processed" / "evaluation" / "snapshots"

# In-memory cache for Parquet files to avoid re-reading on every request
_SPI_PARQUET_CACHE: Dict[str, pd.DataFrame] = {}
_STATION_META_DF_CACHE: Optional[pd.DataFrame] = None


def get_station_metadata_df() -> pd.DataFrame:
    global _STATION_META_DF_CACHE
    if _STATION_META_DF_CACHE is None:
        if PATH_STATION_METADATA.exists():
            _STATION_META_DF_CACHE = pd.read_parquet(PATH_STATION_METADATA)
        else:
            raise FileNotFoundError("station_metadata.parquet not found")
    return _STATION_META_DF_CACHE


# ==============================================================================
# 1. STATION INFORMATION & DETAILED OBSERVATION STATS (INFORMASI POS)
# ==============================================================================
def get_station_detailed_info(station_id: str) -> Dict[str, Any]:
    """
    Retrieves station metadata and computed observation metrics from MariaDB.
    Only computes operating metrics within the station's actual active window
    (from first available observation date to last available observation date).
    """
    sid = station_id.strip().upper()
    meta_df = get_station_metadata_df()

    match_meta = meta_df[meta_df["station_id"].astype(str).str.strip().str.upper() == sid]
    if match_meta.empty:
        raise ValueError(f"Station ID '{sid}' not found in canonical metadata.")

    meta_row = match_meta.iloc[0]
    sname = str(meta_row["station_name"]).strip()
    kab = str(meta_row["regency"]).strip() if pd.notnull(meta_row["regency"]) else ""
    prov = str(meta_row["province"]).strip() if pd.notnull(meta_row["province"]) else "Kepulauan Riau"
    lat = float(meta_row["latitude"])
    lon = float(meta_row["longitude"])
    elev = float(meta_row["elevation_m"]) if pd.notnull(meta_row["elevation_m"]) else None
    nozom = str(meta_row["NOZOM_PROV"]).strip() if ("NOZOM_PROV" in meta_row and pd.notnull(meta_row["NOZOM_PROV"])) else None

    is_arg = sid.endswith("B") or "ARG" in sname.upper()
    station_type = "Stasiun ARG" if is_arg else "Pos Hujan Manual"

    # Query MariaDB for physical observations for this station
    # Query MariaDB for physical observations for this station (Paket 3 Semantics)
    query_sql = """
        SELECT 
            MIN(observation_date) AS first_obs_date,
            MAX(observation_date) AS last_obs_date,
            COUNT(*) AS total_records,
            SUM(CASE WHEN rainfall_mm >= 1.0 AND obs_status IN ('OBSERVED_VALID', 'VALID') THEN 1 ELSE 0 END) AS rain_days_count,
            SUM(CASE WHEN (rainfall_mm = 0.0 OR obs_status = 'OBSERVED_ZERO') AND obs_status != 'TTU' AND original_symbol != 'TTU' AND obs_status NOT LIKE 'MISSING%%' THEN 1 ELSE 0 END) AS dry_zero_days,
            SUM(CASE WHEN rainfall_mm > 0.0 AND rainfall_mm < 1.0 AND obs_status IN ('OBSERVED_VALID', 'VALID') THEN 1 ELSE 0 END) AS dry_sub1mm_days,
            SUM(CASE WHEN obs_status = 'TTU' OR original_symbol = 'TTU' THEN 1 ELSE 0 END) AS ttu_days,
            SUM(CASE WHEN obs_status LIKE 'MISSING%%' OR original_symbol IN ('X', 'M') THEN 1 ELSE 0 END) AS explicit_missing_days
        FROM cews_rainfall_daily
        WHERE station_id = %s;
    """

    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(query_sql, (sid,))
            obs_row = cur.fetchone()

    first_date_val = obs_row["first_obs_date"]
    last_date_val = obs_row["last_obs_date"]
    first_str = first_date_val.strftime("%Y-%m-%d") if hasattr(first_date_val, "strftime") else (str(first_date_val) if first_date_val else None)
    last_str = last_date_val.strftime("%Y-%m-%d") if hasattr(last_date_val, "strftime") else (str(last_date_val) if last_date_val else None)

    total_records = int(obs_row["total_records"] or 0)
    rain_days = int(obs_row["rain_days_count"] or 0)
    dry_zero = int(obs_row["dry_zero_days"] or 0)
    dry_sub1mm = int(obs_row["dry_sub1mm_days"] or 0)
    ttu_count = int(obs_row["ttu_days"] or 0)
    explicit_missing = int(obs_row["explicit_missing_days"] or 0)

    # Calculate actual calendar days between first and last date
    calendar_days = 0
    completeness_pct = 0.0
    unrecorded_days = 0
    total_missing = 0
    valid_count = 0
    total_dry_days = dry_zero + dry_sub1mm + ttu_count

    if first_date_val and last_date_val:
        calendar_days = (last_date_val - first_date_val).days + 1
        unrecorded_days = max(0, calendar_days - total_records)
        total_missing = explicit_missing + unrecorded_days
        valid_count = rain_days + dry_zero + dry_sub1mm + ttu_count
        if calendar_days > 0:
            completeness_pct = round((valid_count / calendar_days) * 100, 2)

    # Compute running HTH backwards from last_date_val with uncertainty
    running_hth = 0
    hth_uncertain = False
    last_rain_date = None

    if last_date_val:
        cutoff_history = last_date_val - timedelta(days=120)
        sql_recent = """
            SELECT observation_date, rainfall_mm, obs_status, original_symbol
            FROM cews_rainfall_daily
            WHERE station_id = %s AND observation_date >= %s
            ORDER BY observation_date DESC;
        """
        with get_db() as conn:
            with conn.cursor() as cur:
                cur.execute(sql_recent, (sid, cutoff_history))
                recent_rows = {r["observation_date"]: r for r in cur.fetchall()}

        curr_date = last_date_val
        while curr_date >= cutoff_history:
            row = recent_rows.get(curr_date)
            if not row:
                hth_uncertain = True
            else:
                st = str(row.get("obs_status", "")).upper()
                sym = str(row.get("original_symbol", "")).upper()
                rf = float(row.get("rainfall_mm", 0.0)) if row.get("rainfall_mm") is not None else None

                if "MISSING" in st or sym in ('X', 'M'):
                    hth_uncertain = True
                elif rf is not None and rf >= 1.0:
                    last_rain_date = curr_date.strftime("%Y-%m-%d")
                    break
                elif rf is not None and rf < 1.0:
                    running_hth += 1
                elif st == "TTU" or sym == "TTU":
                    running_hth += 1
            curr_date -= timedelta(days=1)

    return {
        "station_id": sid,
        "station_name": sname,
        "station_type": station_type,
        "is_arg": is_arg,
        "kabupaten": kab,
        "province": prov,
        "latitude": lat,
        "longitude": lon,
        "elevation_m": elev,
        "nozom_prov": nozom,
        "first_observation_date": first_str,
        "last_observation_date": last_str,
        "operating_calendar_days": calendar_days,
        "total_records": total_records,
        "valid_count": valid_count,
        "rain_days_count": rain_days,
        "dry_days_count": total_dry_days,
        "dry_zero_days_count": dry_zero,
        "dry_sub1mm_days_count": dry_sub1mm,
        "ttu_count": ttu_count,
        "explicit_missing_count": explicit_missing,
        "unrecorded_days_count": unrecorded_days,
        "missing_count": total_missing,
        "completeness_pct": completeness_pct,
        "running_hth": running_hth,
        "hth_uncertain": hth_uncertain,
        "last_rain_date": last_rain_date,
    }


# ==============================================================================
# 2. SPI DATA CENTER
# ==============================================================================
def clear_spi_cache():
    """Clears the in-memory SPI cache upon data update."""
    global _SPI_PARQUET_CACHE
    _SPI_PARQUET_CACHE.clear()


def _resolve_spi_parquet_path(period_type: str, timescale: str) -> Path:
    pt = period_type.strip().upper()
    ts = timescale.strip().upper()

    if "BULAN" in pt:
        filename = "SPI_monthly_90d.parquet" if ("90" in ts or "3" in ts and "BULAN" in ts and "1" not in ts) else "SPI_monthly.parquet"
        target = SPI_RAW_DIR / "bulanan" / filename
        # If 90d requested but not yet generated, fallback gracefully to SPI_monthly.parquet if 90d doesn't exist
        if not target.exists() and filename == "SPI_monthly_90d.parquet":
            target = SPI_RAW_DIR / "bulanan" / "SPI_monthly.parquet"
    elif "DAS" in pt:
        filename = "SPI_all_30d.parquet" if "30" in ts else "SPI_all_90d.parquet"
        target = SPI_RAW_DIR / "dasarian" / filename
    else:
        filename = "SPI_all_30d.parquet" if "30" in ts else "SPI_all_90d.parquet"
        target = SPI_RAW_DIR / "harian" / filename

    if not target.exists():
        raise FileNotFoundError(f"SPI dataset not found: {target.as_posix()}")
    return target


def get_cached_spi_df(period_type: str, timescale: str) -> pd.DataFrame:
    key = f"{period_type.upper()}_{timescale.upper()}"
    if key not in _SPI_PARQUET_CACHE:
        parquet_path = _resolve_spi_parquet_path(period_type, timescale)
        df = pd.read_parquet(parquet_path)

        # Check if index is a RangeIndex (integer) - this happens if a dataset was dumped without index
        if isinstance(df.index, pd.RangeIndex):
            if "date" in df.columns:
                df.index = pd.to_datetime(df["date"])
                df = df.drop(columns=["date"])
            else:
                logger.error(f"SPI Parquet {parquet_path} has RangeIndex and no date column! Rejecting.")
                raise ValueError(f"Corrupted SPI dataset at {parquet_path}: Missing date index.")
        elif not isinstance(df.index, pd.DatetimeIndex):
            df.index = pd.to_datetime(df.index)

        # Drop any metadata columns that might have crept in from accidental long-format dumps
        meta_cols_to_drop = [c for c in df.columns if str(c).strip().lower() in {
            "station_id", "station_name", "date", "ref_date", "period_id", "target_period",
            "year", "month", "scale", "indicator", "spi_value", "new_value", "old_value",
            "diff", "source_sheet", "change_type"
        }]
        if meta_cols_to_drop:
            df = df.drop(columns=meta_cols_to_drop)

        # Filter out invalid 1970 dates (which indicate corrupt 0-epoch nanosecond conversions)
        valid_mask = df.index.year > 1970
        df = df[valid_mask]

        # Convert index to YYYY-MM-DD strings
        df.index = df.index.strftime("%Y-%m-%d")
        df.index.name = "date"
        _SPI_PARQUET_CACHE[key] = df
    return _SPI_PARQUET_CACHE[key]


def get_spi_data(
    period_type: str = "DASARIAN",
    timescale: str = "30D",
    page: int = 1,
    page_size: int = 30,
    order: str = "desc",
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    station_id: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Returns wide-format SPI table rows matching raw workbook structure,
    properly mapping station metadata and keeping missing values as None.
    """
    spi_df = get_cached_spi_df(period_type, timescale)
    meta_df = get_station_metadata_df()

    # Filter by dates
    date_mask = pd.Series(True, index=spi_df.index)
    if start_date:
        date_mask &= (spi_df.index >= start_date)
    if end_date:
        date_mask &= (spi_df.index <= end_date)

    filtered_df = spi_df[date_mask]

    # Sort
    ascending = (order.lower() == "asc")
    filtered_df = filtered_df.sort_index(ascending=ascending)

    total_records = len(filtered_df)
    page_size = max(5, min(page_size, 100))
    total_pages = max(1, (total_records + page_size - 1) // page_size) if total_records > 0 else 1
    page = max(1, min(page, total_pages))

    start_idx = (page - 1) * page_size
    end_idx = start_idx + page_size
    page_df = filtered_df.iloc[start_idx:end_idx]

    # Build column list (52 manual stations that have SPI + 5 ARG stations marked as unavailable)
    columns_info = []
    station_cols_in_parquet = set(spi_df.columns.astype(str).str.strip().str.upper())

    # Order columns by metadata order
    for _, mr in meta_df.iterrows():
        sid = str(mr["station_id"]).strip().upper()
        sname = str(mr["station_name"]).strip()
        kab = str(mr["regency"]).strip() if pd.notnull(mr["regency"]) else ""
        is_arg = sid.endswith("B") or "ARG" in sname.upper()
        has_spi = sid in station_cols_in_parquet

        # If filtered by single station, check match
        if station_id and station_id.strip().upper() != sid:
            continue

        columns_info.append({
            "station_id": sid,
            "station_name": sname,
            "kabupaten": kab,
            "is_arg": is_arg,
            "has_spi": has_spi,
            "status": "AVAILABLE" if has_spi else ("ARG_UNAVAILABLE" if is_arg else "NOT_IN_SPI_SOURCE"),
        })

    # Build row items
    rows = []
    months_id = [
        "Januari", "Februari", "Maret", "April", "Mei", "Juni",
        "Juli", "Agustus", "September", "Oktober", "November", "Desember"
    ]
    for dt_str, r_series in page_df.iterrows():
        stn_vals = {}
        for col_info in columns_info:
            sid = col_info["station_id"]
            if col_info["has_spi"] and sid in r_series.index:
                val = r_series[sid]
                stn_vals[sid] = float(val) if pd.notnull(val) else None
            else:
                stn_vals[sid] = None

        # Build Indonesian period label
        try:
            dt_obj = datetime.strptime(str(dt_str), "%Y-%m-%d")
            if "BULAN" in period_type.upper():
                period_label = f"{months_id[dt_obj.month - 1]} {dt_obj.year}"
            elif "DAS" in period_type.upper():
                das_num = 1 if dt_obj.day <= 10 else (2 if dt_obj.day <= 20 else 3)
                das_roman = "I" if das_num == 1 else ("II" if das_num == 2 else "III")
                period_label = f"Dasarian {das_roman} {months_id[dt_obj.month - 1]} {dt_obj.year}"
            else:
                period_label = f"{dt_obj.day} {months_id[dt_obj.month - 1]} {dt_obj.year}"
        except Exception:
            period_label = str(dt_str)

        rows.append({
            "date": dt_str,
            "period_label": period_label,
            "stations": stn_vals,
        })

    return {
        "meta": {
            "period_type": period_type.upper(),
            "timescale": timescale.upper(),
            "total_records": total_records,
            "page": page,
            "page_size": page_size,
            "total_pages": total_pages,
            "order": order.lower(),
            "start_date": start_date,
            "end_date": end_date,
            "station_id": station_id,
        },
        "columns": columns_info,
        "data": rows,
    }


def get_station_spi_trend(station_id: str, months: int = 12) -> Dict[str, Any]:
    """
    Returns SPI time-series for a given station across Harian, Dasarian, and Bulanan.
    Never interpolates across missing values.
    For ARG stations, returns null arrays and is_arg=True.
    """
    sid = station_id.strip().upper()
    meta_df = get_station_metadata_df()
    match = meta_df[meta_df["station_id"].astype(str).str.strip().str.upper() == sid]
    if match.empty:
        raise ValueError(f"Station ID '{sid}' not found in canonical metadata.")

    sname = str(match.iloc[0]["station_name"]).strip()
    is_arg = sid.endswith("B") or "ARG" in sname.upper() or sid in {"21010802B", "21010603B", "21020402B", "21710501B", "21040101B"}

    thresholds = {
        "kering": -1.00,
        "sangat_kering": -1.50,
        "ekstrem_kering": -2.00,
    }

    if is_arg:
        return {
            "station_id": sid,
            "station_name": sname,
            "is_arg": True,
            "message": "Data SPI tidak tersedia untuk stasiun ARG (Automatic Rain Gauge).",
            "harian": {"dates": [], "spi_30d": [], "spi_90d": []},
            "dasarian": {"dates": [], "spi_30d": [], "spi_90d": []},
            "bulanan": {"dates": [], "spi": []},
            "thresholds": thresholds,
        }

    cutoff_start = (datetime.now() - timedelta(days=months * 31)).strftime("%Y-%m-%d")

    # 1. Harian SPI
    try:
        df_h_30 = get_cached_spi_df("HARIAN", "30D")
        df_h_90 = get_cached_spi_df("HARIAN", "90D")
        common_h_dates = sorted(list(set(df_h_30.index).intersection(df_h_90.index)))
        h_dates = [d for d in common_h_dates if d >= cutoff_start]
        h_spi_30 = [float(df_h_30.loc[d, sid]) if (sid in df_h_30.columns and pd.notnull(df_h_30.loc[d, sid])) else None for d in h_dates]
        h_spi_90 = [float(df_h_90.loc[d, sid]) if (sid in df_h_90.columns and pd.notnull(df_h_90.loc[d, sid])) else None for d in h_dates]
    except Exception as e:
        h_dates, h_spi_30, h_spi_90 = [], [], []

    # 2. Dasarian SPI
    try:
        df_d_30 = get_cached_spi_df("DASARIAN", "30D")
        df_d_90 = get_cached_spi_df("DASARIAN", "90D")
        common_d_dates = sorted(list(set(df_d_30.index).intersection(df_d_90.index)))
        d_dates = [d for d in common_d_dates if d >= cutoff_start]
        d_spi_30 = [float(df_d_30.loc[d, sid]) if (sid in df_d_30.columns and pd.notnull(df_d_30.loc[d, sid])) else None for d in d_dates]
        d_spi_90 = [float(df_d_90.loc[d, sid]) if (sid in df_d_90.columns and pd.notnull(df_d_90.loc[d, sid])) else None for d in d_dates]
    except Exception as e:
        d_dates, d_spi_30, d_spi_90 = [], [], []

    # 3. Bulanan SPI
    try:
        df_m = get_cached_spi_df("BULANAN", "30D")
        m_dates = sorted([d for d in df_m.index if d >= cutoff_start or d >= "2021-01-01"])
        m_spi = [float(df_m.loc[d, sid]) if (sid in df_m.columns and pd.notnull(df_m.loc[d, sid])) else None for d in m_dates]
    except Exception as e:
        m_dates, m_spi = [], []

    return {
        "station_id": sid,
        "station_name": sname,
        "is_arg": False,
        "harian": {"dates": h_dates, "spi_30d": h_spi_30, "spi_90d": h_spi_90},
        "dasarian": {"dates": d_dates, "spi_30d": d_spi_30, "spi_90d": d_spi_90},
        "bulanan": {"dates": m_dates, "spi": m_spi},
        "thresholds": thresholds,
    }


# ==============================================================================
# 3. PROBABILITY DATA CENTER
# ==============================================================================
def select_eligible_vintage(
    available_vintages: List[str],
    requested_issue_date: Optional[str] = None,
    evaluation_cutoff_date: Optional[str] = None,
) -> Optional[str]:
    """
    Selects the active forecast vintage according to:
    selected_vintage = MAX(issue_date) WHERE issue_date <= evaluation_cutoff_date.
    Vintages published strictly after evaluation_cutoff_date are never used when cutoff is specified.
    Expects available_vintages sorted in descending order (newest first).
    """
    if not available_vintages:
        return None
    if requested_issue_date and requested_issue_date in available_vintages:
        return requested_issue_date
    if evaluation_cutoff_date:
        eligible = [v for v in available_vintages if v <= evaluation_cutoff_date]
        if eligible:
            return eligible[0]
        return None
    return available_vintages[0]


def get_probability_data(
    period_id: Optional[str] = None,
    station_id: Optional[str] = None,
    issue_date: Optional[str] = None,
    cutoff_date: Optional[str] = None,
    page: int = 1,
    page_size: int = 60,
) -> Dict[str, Any]:
    """
    Returns probability data across 57 master stations for the target evaluation period
    (pb20, pa150, pa200, pa300 for dasarian; pa300, pa400, pa500 for monthly),
    queried authoritatively from cews_forecast_snapshot (with fallback to cews_period_snapshot).
    Supports multi-vintage selection (latest eligible vintage selected by default).
    Exempts 5 ARG stations strictly with NULL.
    """
    from backend.period_service import get_dasarian_dates

    pid = (period_id or "2026-10-das3").strip()
    
    # 1. Parse resolution & target parameters
    if "-das" in pid:
        parts = pid.split("-")
        t_year = int(parts[0])
        t_month = int(parts[1])
        t_das = int(parts[2].replace("das", ""))
        resolution = "DASARIAN"
        t_start_dt, t_end_dt = get_dasarian_dates(t_year, t_month, f"das{t_das}")
    else:
        parts = pid.split("-")
        t_year = int(parts[0])
        t_month = int(parts[1])
        t_das = 1
        resolution = "BULANAN"
        t_start_dt = date(t_year, t_month, 1)
        next_m = t_month + 1 if t_month < 12 else 1
        next_y = t_year if t_month < 12 else t_year + 1
        t_end_dt = date(next_y, next_m, 1) - timedelta(days=1)

    t_start = t_start_dt.strftime("%Y-%m-%d")
    t_end = t_end_dt.strftime("%Y-%m-%d")

    available_vintages: List[str] = []
    selected_issue: Optional[str] = None
    station_param_map: Dict[str, Dict[str, Optional[float]]] = {}
    found_in_forecast_snapshot = False

    # 2. Query cews_forecast_snapshot for available vintages isolated by forecast_resolution
    with get_db() as conn:
        with conn.cursor() as cur:
            if resolution == "DASARIAN":
                cur.execute("""
                    SELECT DISTINCT issue_date 
                    FROM cews_forecast_snapshot 
                    WHERE target_year = %s AND target_month = %s AND target_dasarian = %s
                      AND forecast_resolution = 'DASARIAN'
                    ORDER BY issue_date DESC
                """, (t_year, t_month, t_das))
            else:
                cur.execute("""
                    SELECT DISTINCT issue_date 
                    FROM cews_forecast_snapshot 
                    WHERE target_year = %s AND target_month = %s AND (target_dasarian = 1 OR target_dasarian = 0)
                      AND forecast_resolution = 'BULANAN'
                    ORDER BY issue_date DESC
                """, (t_year, t_month))
            
            rows = cur.fetchall()
            if rows:
                found_in_forecast_snapshot = True
                available_vintages = [
                    r["issue_date"].strftime("%Y-%m-%d") if hasattr(r["issue_date"], "strftime") else str(r["issue_date"])
                    for r in rows
                ]
                selected_issue = select_eligible_vintage(
                    available_vintages,
                    requested_issue_date=issue_date,
                    evaluation_cutoff_date=cutoff_date,
                )

                if selected_issue:
                    # Query parameters for selected vintage strictly scoped by forecast_resolution
                    if resolution == "DASARIAN":
                        cur.execute("""
                            SELECT station_id, forecast_parameter, probability_value
                            FROM cews_forecast_snapshot
                            WHERE target_year = %s AND target_month = %s AND target_dasarian = %s
                              AND issue_date = %s AND forecast_resolution = 'DASARIAN'
                        """, (t_year, t_month, t_das, selected_issue))
                    else:
                        cur.execute("""
                            SELECT station_id, forecast_parameter, probability_value
                            FROM cews_forecast_snapshot
                            WHERE target_year = %s AND target_month = %s AND (target_dasarian = 0 OR target_dasarian = 1)
                              AND issue_date = %s AND forecast_resolution = 'BULANAN'
                        """, (t_year, t_month, selected_issue))

                    for r in cur.fetchall():
                        sid = str(r["station_id"]).strip().upper()
                        if sid not in station_param_map:
                            station_param_map[sid] = {}
                        val = float(r["probability_value"]) if r["probability_value"] is not None else None
                        station_param_map[sid][r["forecast_parameter"]] = val

    # 3. Fallback to cews_period_snapshot if not found in cews_forecast_snapshot
    if not found_in_forecast_snapshot:
        with get_db() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT station_id, forecast_issue, target_start, target_end,
                           forecast_pb20, forecast_pa150, forecast_pa200, forecast_pa300,
                           monthly_pa300, monthly_pa400, monthly_pa500
                    FROM cews_period_snapshot
                    WHERE period_id = %s
                """, (pid,))
                p_rows = cur.fetchall()
                if p_rows:
                    first_r = p_rows[0]
                    if first_r.get("forecast_issue"):
                        f_iss = first_r["forecast_issue"]
                        selected_issue = f_iss.strftime("%Y-%m-%d") if hasattr(f_iss, "strftime") else str(f_iss)
                        available_vintages = [selected_issue]
                    if first_r.get("target_start"):
                        t_start = first_r["target_start"].strftime("%Y-%m-%d") if hasattr(first_r["target_start"], "strftime") else str(first_r["target_start"])
                    if first_r.get("target_end"):
                        t_end = first_r["target_end"].strftime("%Y-%m-%d") if hasattr(first_r["target_end"], "strftime") else str(first_r["target_end"])

                    for r in p_rows:
                        sid = str(r["station_id"]).strip().upper()
                        station_param_map[sid] = {
                            "pb20": float(r["forecast_pb20"]) if r.get("forecast_pb20") is not None else None,
                            "pa150": float(r["forecast_pa150"]) if r.get("forecast_pa150") is not None else None,
                            "pa200": float(r["forecast_pa200"]) if r.get("forecast_pa200") is not None else None,
                            "pa300": float(r["forecast_pa300"]) if r.get("forecast_pa300") is not None else None,
                            "monthly_pa300": float(r["monthly_pa300"]) if r.get("monthly_pa300") is not None else None,
                            "monthly_pa400": float(r["monthly_pa400"]) if r.get("monthly_pa400") is not None else None,
                            "monthly_pa500": float(r["monthly_pa500"]) if r.get("monthly_pa500") is not None else None,
                        }

    # 4. Canonical station master mapping (57 stations)
    from backend.ingestion_service import ARG_STATION_IDS

    meta_df = get_station_metadata_df().copy()
    if "kabupaten" not in meta_df.columns and "regency" in meta_df.columns:
        meta_df["kabupaten"] = meta_df["regency"]

    items = []
    
    # Filter station_id if provided
    single_sid = station_id.strip().upper() if (station_id and station_id.strip().upper() != "ALL") else None

    # Canonical order: kabupaten ASC, station_name ASC
    sort_col = "kabupaten" if "kabupaten" in meta_df.columns else "regency"
    sorted_meta = meta_df.sort_values(by=[sort_col, "station_name"])
    
    for _, row in sorted_meta.iterrows():
        sid = str(row["station_id"]).strip().upper()
        if single_sid and sid != single_sid:
            continue

        is_arg = (sid in ARG_STATION_IDS) or bool(row.get("is_arg", False))
        sname = str(row["station_name"]).strip()
        kab = str(row.get("kabupaten", row.get("regency", ""))).strip()

        p_dict = station_param_map.get(sid, {})

        if is_arg:
            pb20 = pa150 = pa200 = pa300 = pm300 = pm400 = pm500 = None
        elif resolution == "DASARIAN":
            pb20 = p_dict.get("pb20", p_dict.get("prob_below20"))
            pa150 = p_dict.get("pa150", p_dict.get("prob_above150"))
            pa200 = p_dict.get("pa200", p_dict.get("prob_above200"))
            pa300 = p_dict.get("pa300", p_dict.get("prob_above300"))
            pm300 = pm400 = pm500 = None
        else:
            pb20 = pa150 = pa200 = pa300 = None
            pm300 = p_dict.get("pa300", p_dict.get("monthly_pa300", p_dict.get("prob_month_above300")))
            pm400 = p_dict.get("pa400", p_dict.get("monthly_pa400", p_dict.get("prob_month_above400")))
            pm500 = p_dict.get("pa500", p_dict.get("monthly_pa500", p_dict.get("prob_month_above500")))

        items.append({
            "period_id": pid,
            "station_id": sid,
            "station_name": sname,
            "kabupaten": kab,
            "is_arg": is_arg,
            "forecast_issue": selected_issue or "TIDAK_TERSEDIA",
            "target_start": t_start,
            "target_end": t_end,
            "prob_below20": pb20,
            "prob_above150": pa150,
            "prob_above200": pa200,
            "prob_above300": pa300,
            "prob_month_above300": pm300,
            "prob_month_above400": pm400,
            "prob_month_above500": pm500,
            "source": "ECMWF Ensemble Probability",
        })

    total_records = len(items)
    page_size = max(5, min(page_size, 100))
    total_pages = max(1, (total_records + page_size - 1) // page_size) if total_records > 0 else 1
    page = max(1, min(page, total_pages))
    offset = (page - 1) * page_size
    paginated_items = items[offset:offset + page_size]

    active_stations_with_data = sum(
        1 for sid, m in station_param_map.items()
        if any(v is not None for v in m.values())
    )

    return {
        "meta": {
            "period_id": pid,
            "station_id": station_id,
            "resolution": resolution,
            "active_vintage_issue": selected_issue,
            "available_vintages": available_vintages,
            "available_stations_count": active_stations_with_data,
            "total_records": total_records,
            "page": page,
            "page_size": page_size,
            "total_pages": total_pages,
        },
        "data": paginated_items,
    }


# ==============================================================================
# 4. UNIFIED DATA DOWNLOAD ENGINE (CSV & XLSX)
# ==============================================================================
def export_rainfall_data(
    file_format: str = "csv",
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    station_ids: Optional[List[str]] = None,
) -> Tuple[bytes, str, str]:
    """
    Exports daily rainfall observations in Excel wide spreadsheet format or CSV.
    """
    where_parts = []
    params: List[Any] = []

    if start_date:
        where_parts.append("observation_date >= %s")
        params.append(start_date)
    if end_date:
        where_parts.append("observation_date <= %s")
        params.append(end_date)

    sid_filter = [s.strip().lower() for s in (station_ids or []) if s.strip()]
    if sid_filter:
        placeholders = ",".join(["%s"] * len(sid_filter))
        where_parts.append(f"LOWER(station_id) IN ({placeholders})")
        params.extend(sid_filter)

    where_sql = ("WHERE " + " AND ".join(where_parts)) if where_parts else ""

    meta_df = get_station_metadata_df()
    meta_sids_map = {str(s).strip().lower(): s for s in meta_df["station_id"].tolist()}
    if sid_filter:
        target_stations = [meta_sids_map[s] for s in sid_filter if s in meta_sids_map]
    else:
        target_stations = meta_df["station_id"].tolist()

    # Query distinct dates
    with get_db() as conn:
        with conn.cursor() as cur:
            date_sql = f"""
                SELECT DISTINCT observation_date, year, month, day
                FROM cews_rainfall_daily
                {where_sql}
                ORDER BY observation_date ASC
                LIMIT 10000
            """
            cur.execute(date_sql, tuple(params))
            date_rows = cur.fetchall()

            if not date_rows:
                # Return empty file with headers
                date_list = []
                obs_rows = []
            else:
                date_list = [r["observation_date"] for r in date_rows]
                # Query observations
                dt_placeholders = ",".join(["%s"] * len(date_list))
                obs_sql = f"""
                    SELECT station_id, observation_date, rainfall_mm, obs_status, original_symbol
                    FROM cews_rainfall_daily
                    WHERE observation_date IN ({dt_placeholders})
                """
                obs_params = list(date_list)
                if sid_filter:
                    stn_placeholders = ",".join(["%s"] * len(sid_filter))
                    obs_sql += f" AND LOWER(station_id) IN ({stn_placeholders})"
                    obs_params.extend(sid_filter)

                cur.execute(obs_sql, tuple(obs_params))
                obs_rows = cur.fetchall()

    # Organize obs map: (date_str, station_id_lower) -> display_str
    obs_map: Dict[Tuple[str, str], str] = {}
    for r in obs_rows:
        d_str = r["observation_date"].strftime("%Y-%m-%d")
        sid = str(r["station_id"]).strip().lower()
        if r.get("original_symbol") == "TTU" or r.get("obs_status") == "TTU":
            val_str = "TTU"
        elif r.get("rainfall_mm") is not None:
            val_str = f"{float(r['rainfall_mm']):.1f}"
        elif r.get("original_symbol"):
            val_str = str(r["original_symbol"])
        else:
            val_str = "X"
        obs_map[(d_str, sid)] = val_str

    # Build Header
    station_names = dict(zip(meta_df["station_id"], meta_df["station_name"]))
    header = ["Tanggal", "Tahun", "Bulan", "Hari", "Dasarian"] + [f"{sid} - {station_names.get(sid, sid)}" for sid in target_stations]

    rows_data = []
    for dr in date_rows:
        dt = dr["observation_date"]
        d_str = dt.strftime("%Y-%m-%d")
        y = dr["year"]
        m = dr["month"]
        d = dr["day"]
        das = 1 if d <= 10 else (2 if d <= 20 else 3)
        row = [d_str, y, m, d, das]
        for sid in target_stations:
            val = obs_map.get((d_str, str(sid).strip().lower()), "X")
            row.append(val)
        rows_data.append(row)

    fmt = file_format.lower()
    timestamp_str = datetime.now().strftime("%Y%m%d_%H%M")
    filename = f"dss_pik_curah_hujan_{timestamp_str}.{fmt}"

    if fmt == "xlsx":
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = "Curah Hujan Harian"

        # Add Title Row
        from backend.config import INSTITUTION_NAME
        ws.append([f"DATA CURAH HUJAN HARIAN — DSS-PIK {INSTITUTION_NAME.upper()}"])
        ws.append([f"Diekspor pada: {datetime.now().strftime('%Y-%m-%d %H:%M:%S WIB')}"])
        ws.append([])
        ws.append(header)

        # Style Header
        header_fill = PatternFill(start_color="1E3A8A", end_color="1E3A8A", fill_type="solid")
        header_font = Font(name="Calibri", size=10, bold=True, color="FFFFFF")
        for col_idx in range(1, len(header) + 1):
            cell = ws.cell(row=4, column=col_idx)
            cell.fill = header_fill
            cell.font = header_font
            cell.alignment = Alignment(horizontal="center", vertical="center")

        for r in rows_data:
            ws.append(r)

        output = io.BytesIO()
        wb.save(output)
        return output.getvalue(), "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", filename
    else:
        output_str = io.StringIO()
        writer = csv.writer(output_str)
        writer.writerow(header)
        for r in rows_data:
            writer.writerow(r)
        return output_str.getvalue().encode("utf-8"), "text/csv; charset=utf-8", filename


def export_spi_data(
    period_type: str = "DASARIAN",
    timescale: str = "30D",
    file_format: str = "csv",
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    station_ids: Optional[List[str]] = None,
) -> Tuple[bytes, str, str]:
    """
    Exports SPI data in wide format for all or selected stations to CSV or XLSX.
    """
    spi_df = get_cached_spi_df(period_type, timescale)
    meta_df = get_station_metadata_df()

    date_mask = pd.Series(True, index=spi_df.index)
    if start_date:
        date_mask &= (spi_df.index >= start_date)
    if end_date:
        date_mask &= (spi_df.index <= end_date)

    filtered_df = spi_df[date_mask].sort_index(ascending=True)

    sid_filter = [s.strip().lower() for s in (station_ids or []) if s.strip()]
    meta_sids_map = {str(s).strip().lower(): s for s in meta_df["station_id"].tolist()}
    if sid_filter:
        target_stations = [meta_sids_map[s] for s in sid_filter if s in meta_sids_map]
    else:
        target_stations = meta_df["station_id"].tolist()

    station_names = dict(zip(meta_df["station_id"], meta_df["station_name"]))
    header = ["Tanggal"] + [f"{sid} - {station_names.get(sid, sid)}" for sid in target_stations]

    rows_data = []
    for dt_str, r_series in filtered_df.iterrows():
        row = [dt_str]
        for sid in target_stations:
            if sid in r_series.index:
                val = r_series[sid]
                row.append(round(float(val), 2) if pd.notnull(val) else "—")
            else:
                row.append("—")
        rows_data.append(row)

    fmt = file_format.lower()
    timestamp_str = datetime.now().strftime("%Y%m%d_%H%M")
    filename = f"dss_pik_spi_{period_type.lower()}_{timescale.lower()}_{timestamp_str}.{fmt}"

    if fmt == "xlsx":
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = f"SPI_{period_type}_{timescale}"

        from backend.config import INSTITUTION_NAME
        ws.append([f"DATA SPI {period_type.upper()} ({timescale.upper()}) — DSS-PIK {INSTITUTION_NAME.upper()}"])
        ws.append([f"Diekspor pada: {datetime.now().strftime('%Y-%m-%d %H:%M:%S WIB')}"])
        ws.append([])
        ws.append(header)

        header_fill = PatternFill(start_color="1E3A8A", end_color="1E3A8A", fill_type="solid")
        header_font = Font(name="Calibri", size=10, bold=True, color="FFFFFF")
        for col_idx in range(1, len(header) + 1):
            cell = ws.cell(row=4, column=col_idx)
            cell.fill = header_fill
            cell.font = header_font
            cell.alignment = Alignment(horizontal="center", vertical="center")

        for r in rows_data:
            ws.append(r)

        output = io.BytesIO()
        wb.save(output)
        return output.getvalue(), "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", filename
    else:
        output_str = io.StringIO()
        writer = csv.writer(output_str)
        writer.writerow(header)
        for r in rows_data:
            writer.writerow(r)
        return output_str.getvalue().encode("utf-8"), "text/csv; charset=utf-8", filename


def export_probability_data(
    period_id: str = "2026-10-das3",
    file_format: str = "csv",
    station_ids: Optional[List[str]] = None,
    parameters: Optional[List[str]] = None,
    issue_date: Optional[str] = None,
) -> Tuple[bytes, str, str]:
    """
    Exports forecast probability data across stations to CSV or XLSX.
    """
    prob_res = get_probability_data(period_id=period_id, issue_date=issue_date, page=1, page_size=200)
    items = prob_res["data"]

    sid_filter = set(s.strip().upper() for s in (station_ids or []) if s.strip())
    if sid_filter:
        items = [it for it in items if str(it["station_id"]).strip().upper() in sid_filter]

    header = [
        "Periode",
        "ID Stasiun",
        "Nama Stasiun",
        "Kabupaten",
        "Jenis",
        "Tanggal Terbit",
        "pb20 (<20mm) [%]",
        "pa150 (>150mm) [%]",
        "pa200 (>200mm) [%]",
        "pa300 (>300mm) [%]",
        "Bulanan >300mm [%]",
        "Bulanan >400mm [%]",
        "Bulanan >500mm [%]",
        "Sumber",
    ]

    rows_data = []
    for it in items:
        row = [
            it["period_id"],
            it["station_id"],
            it["station_name"],
            it["kabupaten"],
            "ARG" if it.get("is_arg") else "Manual",
            it["forecast_issue"],
            f"{it['prob_below20']:.0f}%" if it.get("prob_below20") is not None else "—",
            f"{it['prob_above150']:.0f}%" if it.get("prob_above150") is not None else "—",
            f"{it['prob_above200']:.0f}%" if it.get("prob_above200") is not None else "—",
            f"{it['prob_above300']:.0f}%" if it.get("prob_above300") is not None else "—",
            f"{it['prob_month_above300']:.0f}%" if it.get("prob_month_above300") is not None else "—",
            f"{it['prob_month_above400']:.0f}%" if it.get("prob_month_above400") is not None else "—",
            f"{it['prob_month_above500']:.0f}%" if it.get("prob_month_above500") is not None else "—",
            it["source"],
        ]
        rows_data.append(row)

    fmt = file_format.lower()
    timestamp_str = datetime.now().strftime("%Y%m%d_%H%M")
    filename = f"dss_pik_probabilitas_{period_id}_{timestamp_str}.{fmt}"

    if fmt == "xlsx":
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = "Probabilitas Prakiraan"

        from backend.config import INSTITUTION_NAME
        ws.append([f"DATA PROBABILITAS PRAKIRAAN ({period_id}) — DSS-PIK {INSTITUTION_NAME.upper()}"])
        ws.append([f"Diekspor pada: {datetime.now().strftime('%Y-%m-%d %H:%M:%S WIB')}"])
        ws.append([])
        ws.append(header)

        header_fill = PatternFill(start_color="1E3A8A", end_color="1E3A8A", fill_type="solid")
        header_font = Font(name="Calibri", size=10, bold=True, color="FFFFFF")
        for col_idx in range(1, len(header) + 1):
            cell = ws.cell(row=4, column=col_idx)
            cell.fill = header_fill
            cell.font = header_font
            cell.alignment = Alignment(horizontal="center", vertical="center")

        for r in rows_data:
            ws.append(r)

        output = io.BytesIO()
        wb.save(output)
        return output.getvalue(), "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", filename
    else:
        output_str = io.StringIO()
        writer = csv.writer(output_str)
        writer.writerow(header)
        for r in rows_data:
            writer.writerow(r)
        return output_str.getvalue().encode("utf-8"), "text/csv; charset=utf-8", filename


def get_probability_periods_list() -> Dict[str, Any]:
    """
    Returns available distinct target forecast periods from cews_forecast_snapshot,
    categorized by DASARIAN and BULANAN, with available vintages.
    """
    months_id = [
        "Januari", "Februari", "Maret", "April", "Mei", "Juni",
        "Juli", "Agustus", "September", "Oktober", "November", "Desember"
    ]
    dasarian_periods = []
    bulanan_periods = []

    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT forecast_resolution, target_year, target_month, target_dasarian, 
                       GROUP_CONCAT(DISTINCT DATE_FORMAT(issue_date, '%Y-%m-%d') ORDER BY issue_date DESC) as vintages,
                       COUNT(*) as record_count
                FROM cews_forecast_snapshot
                GROUP BY forecast_resolution, target_year, target_month, target_dasarian
                ORDER BY target_year DESC, target_month DESC, target_dasarian DESC
            """)
            rows = cur.fetchall()
            for r in rows:
                res = str(r["forecast_resolution"]).upper()
                yr = int(r["target_year"])
                mo = int(r["target_month"])
                das = int(r["target_dasarian"])
                v_list = str(r["vintages"]).split(",") if r["vintages"] else []

                if res == "DASARIAN":
                    pid = f"{yr}-{mo:02d}-das{das}"
                    das_roman = "I" if das == 1 else ("II" if das == 2 else "III")
                    label = f"Dasarian {das_roman} {months_id[mo - 1]} {yr}"
                    dasarian_periods.append({
                        "period_id": pid,
                        "label": label,
                        "resolution": "DASARIAN",
                        "year": yr,
                        "month": mo,
                        "dasarian": das,
                        "available_vintages": v_list,
                        "latest_vintage": v_list[0] if v_list else None,
                        "record_count": r["record_count"],
                    })
                else:
                    pid = f"{yr}-{mo:02d}"
                    label = f"{months_id[mo - 1]} {yr}"
                    bulanan_periods.append({
                        "period_id": pid,
                        "label": label,
                        "resolution": "BULANAN",
                        "year": yr,
                        "month": mo,
                        "available_vintages": v_list,
                        "latest_vintage": v_list[0] if v_list else None,
                        "record_count": r["record_count"],
                    })

    return {
        "status": "success",
        "dasarian": dasarian_periods,
        "bulanan": bulanan_periods,
        "all": dasarian_periods + bulanan_periods,
    }
