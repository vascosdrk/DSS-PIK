"""
Diagnostic and Data Evaluation Service for CEWS BMKG Kepulauan Riau (Pass A)
Provides read-only quality control and spatial contextual comparisons without altering Decision Engine logic.
"""

import os
import math
import pandas as pd
import numpy as np
from typing import Optional, Dict, Any, List
import sys
from pathlib import Path

# Canonical paths from central config
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from config.paths import (
    PATH_STATION_METADATA,
    PATH_RAINFALL_DAILY,
    PATH_HTH_DAILY,
    PATH_CURRENT_WARNING
)

BASE_DIR = str(_PROJECT_ROOT)
META_PATH = str(PATH_STATION_METADATA)
# Use corrected symbols extended dataset for Dasarian III September 2026 evaluation
HTH_DAILY_PATH = str(_PROJECT_ROOT / "data" / "processed" / "rainfall" / "final_rainfall_daily_period_extended_review_symbols_fixed_20261022.parquet")
CW_PARQUET_PATH = str(PATH_CURRENT_WARNING)

_META_DF = None
_HTH_DF = None
_CW_DF = None
_HTH_LATEST_MAP = {}
CUTOFF_DATE = pd.to_datetime("2026-09-20").date()


def _ensure_data_loaded():
    global _META_DF, _HTH_DF, _CW_DF, _HTH_LATEST_MAP
    if _META_DF is None and os.path.exists(META_PATH):
        try:
            df_m = pd.read_parquet(META_PATH)
            df_m["station_id_upper"] = df_m["station_id"].astype(str).str.strip().str.upper()
            _META_DF = df_m
        except Exception as e:
            print(f"[Warning] Failed to pre-load station metadata parquet: {e}")

    if _CW_DF is None and os.path.exists(CW_PARQUET_PATH):
        try:
            df_c = pd.read_parquet(CW_PARQUET_PATH)
            df_c["station_id_upper"] = df_c["station_id"].astype(str).str.strip().str.upper()
            _CW_DF = df_c
            for _, row in df_c.iterrows():
                sid = row["station_id_upper"]
                h_col = "hth_days_current" if "hth_days_current" in row else ("hth_days" if "hth_days" in row else None)
                u_col = "hth_uncertain" if "hth_uncertain" in row else None
                o_col = "last_observation_date" if "last_observation_date" in row else None
                _HTH_LATEST_MAP[sid] = {
                    "hth_days": int(row[h_col]) if (h_col and pd.notnull(row[h_col])) else None,
                    "hth_uncertain": bool(row[u_col]) if (u_col and pd.notnull(row[u_col])) else False,
                    "last_obs_date": str(row[o_col]) if (o_col and pd.notnull(row[o_col])) else None,
                    "last_rain_date": str(row["last_rain_date"]) if ("last_rain_date" in row and pd.notnull(row["last_rain_date"])) else None
                }
        except Exception as e:
            print(f"[Warning] Failed to pre-load current warning parquet: {e}")

    if _HTH_DF is None and os.path.exists(HTH_DAILY_PATH):
        try:
            df_h = pd.read_parquet(HTH_DAILY_PATH)
            df_h["station_id_upper"] = df_h["station_id"].astype(str).str.strip().str.upper()
            df_h["date_dt"] = pd.to_datetime(df_h["date"]).dt.date
            # Strictly limit to observation cutoff date: 2026-09-20
            df_h = df_h[df_h["date_dt"] <= CUTOFF_DATE].copy()
            _HTH_DF = df_h

            # Pre-compute last rain date (rainfall_mm >= 1.0 mm) for each station
            rain_df = df_h[df_h["rainfall_mm"] >= 1.0]
            if not rain_df.empty:
                last_rain_map = rain_df.groupby("station_id_upper")["date_dt"].max().to_dict()
                for sid, lr_date in last_rain_map.items():
                    d_str = lr_date.strftime("%Y-%m-%d")
                    if sid in _HTH_LATEST_MAP:
                        if not _HTH_LATEST_MAP[sid].get("last_rain_date"):
                            _HTH_LATEST_MAP[sid]["last_rain_date"] = d_str
                    else:
                        _HTH_LATEST_MAP[sid] = {"last_rain_date": d_str}
        except Exception as e:
            print(f"[Warning] Failed to pre-load daily rainfall parquet: {e}")


def get_last_rain_date(station_id: str) -> Optional[str]:
    """Retrieve the last recorded rain date (rainfall >= 1.0 mm) for a station."""
    _ensure_data_loaded()
    sid_upper = station_id.strip().upper()
    info = _HTH_LATEST_MAP.get(sid_upper)
    if info and info.get("last_rain_date"):
        return info.get("last_rain_date")
    if _HTH_DF is not None:
        rain_rows = _HTH_DF[(_HTH_DF["station_id_upper"] == sid_upper) & (_HTH_DF["rainfall_mm"] >= 1.0)]
        if not rain_rows.empty:
            max_dt = rain_rows["date_dt"].max()
            d_str = max_dt.strftime("%Y-%m-%d") if hasattr(max_dt, "strftime") else str(max_dt)
            if sid_upper in _HTH_LATEST_MAP:
                _HTH_LATEST_MAP[sid_upper]["last_rain_date"] = d_str
            return d_str
    return None


def get_station_rainfall_history(
    station_id: str,
    days: int = 15,
    cutoff_date: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None
) -> Dict[str, Any]:
    """
    Retrieve consecutive daily rainfall records for a station for a date range or last N days.
    Prioritizes live MariaDB (cews_rainfall_daily) so new observations/corrections appear immediately,
    with robust fallback to canonical daily rainfall parquet.
    """
    import datetime
    sid_upper = station_id.strip().upper()

    # Try live MariaDB first
    try:
        from backend.database import get_db
        with get_db() as conn:
            with conn.cursor() as cur:
                # 1. Determine date range
                if start_date and end_date:
                    s_date = datetime.date.fromisoformat(start_date)
                    e_date = datetime.date.fromisoformat(end_date)
                    is_custom = True
                elif cutoff_date:
                    e_date = datetime.date.fromisoformat(cutoff_date)
                    s_date = e_date - datetime.timedelta(days=days - 1)
                    is_custom = False
                else:
                    cur.execute("SELECT MAX(observation_date) as max_d FROM cews_rainfall_daily WHERE station_id = %s;", (sid_upper,))
                    row = cur.fetchone()
                    e_date = row['max_d'] if row and row['max_d'] else datetime.date.today()
                    s_date = e_date - datetime.timedelta(days=days - 1)
                    is_custom = False

                # 2. Query lookback window for accurate running HTH calculation (up to 120 days prior)
                pre_start = s_date - datetime.timedelta(days=120)
                cur.execute("""
                    SELECT observation_date, rainfall_mm, obs_status, original_symbol
                    FROM cews_rainfall_daily
                    WHERE station_id = %s AND observation_date BETWEEN %s AND %s
                    ORDER BY observation_date ASC;
                """, (sid_upper, pre_start, e_date))
                all_rows = cur.fetchall()

                # Running HTH (consecutive days with valid obs and CH < 1.0 mm; missing/damaged/ambiguous marks uncertain; rain breaks streak)
                running_hth = {}
                counter = 0
                hth_uncertain = False
                for r in all_rows:
                    d = r["observation_date"]
                    rf = float(r["rainfall_mm"]) if r["rainfall_mm"] is not None else None
                    status = r["obs_status"]
                    if status in ("MISSING", "DAMAGED", "AMBIGUOUS", "VOID") or rf is None:
                        # Streak is uncertain: do not assume rain or dry, do not reset to 0
                        hth_uncertain = True
                    elif rf >= 1.0:
                        counter = 0
                        hth_uncertain = False
                    else:
                        counter += 1
                    running_hth[d] = {"days": counter, "uncertain": hth_uncertain}

                # Map records in [s_date, e_date]
                row_map = {r["observation_date"]: r for r in all_rows if s_date <= r["observation_date"] <= e_date}
                records = []
                cur_d = s_date
                while cur_d <= e_date:
                    d_str = cur_d.strftime("%Y-%m-%d")
                    r = row_map.get(cur_d)
                    if r is not None:
                        rf = float(r["rainfall_mm"]) if r["rainfall_mm"] is not None else None
                        obs_st = r["obs_status"]
                        orig_sym = r.get("original_symbol")
                    else:
                        rf = None
                        obs_st = "MISSING"
                        orig_sym = "X"

                    hth_info = running_hth.get(cur_d, {"days": 0, "uncertain": False})
                    hth = hth_info["days"]
                    hth_un = hth_info["uncertain"]

                    if obs_st in ("MISSING", "DAMAGED", "AMBIGUOUS") or rf is None:
                        if obs_st == "DAMAGED":
                            status_desc = "Alat Rusak"
                        elif obs_st == "AMBIGUOUS":
                            status_desc = "Perlu Verifikasi"
                        else:
                            status_desc = "Tidak tersedia"
                    elif obs_st == "TTU":
                        status_desc = "TTU (Jejak Hujan)"
                    elif rf < 1.0:
                        status_desc = "Hari Tanpa Hujan"
                    else:
                        status_desc = f"Hujan ({rf:.1f} mm)"

                    records.append({
                        "date": d_str,
                        "rainfall_mm": rf,
                        "status": status_desc,
                        "obs_status": obs_st,
                        "original_symbol": orig_sym,
                        "hth_days": hth,
                        "hth_uncertain": hth_un,
                    })
                    cur_d += datetime.timedelta(days=1)

                p_start = records[0]["date"] if records else None
                p_end = records[-1]["date"] if records else None

                return {
                    "station_id": station_id,
                    "period_start": p_start,
                    "period_end": p_end,
                    "total_days": len(records),
                    "is_custom_range": is_custom,
                    "cutoff_date": cutoff_date,
                    "data": records,
                }
    except Exception as db_err:
        pass

    # Parquet fallback logic
    _ensure_data_loaded()
    if _HTH_DF is None or _HTH_DF.empty:
        return {
            "station_id": station_id,
            "period_start": None,
            "period_end": None,
            "total_days": 0,
            "is_custom_range": False,
            "cutoff_date": cutoff_date,
            "data": [],
        }

    stn_df = _HTH_DF[_HTH_DF["station_id_upper"] == sid_upper].sort_values("date_dt")
    if start_date and end_date:
        s_d = pd.to_datetime(start_date).date()
        e_d = pd.to_datetime(end_date).date()
        recent_df = stn_df[(stn_df["date_dt"] >= s_d) & (stn_df["date_dt"] <= e_d)]
        is_custom = True
    elif cutoff_date is not None:
        try:
            c_date = pd.to_datetime(cutoff_date).date()
            stn_df = stn_df[stn_df["date_dt"] <= c_date]
        except Exception:
            pass
        recent_df = stn_df.tail(days)
        is_custom = False
    else:
        recent_df = stn_df.tail(days)
        is_custom = False

    if recent_df.empty:
        return {
            "station_id": station_id,
            "period_start": None,
            "period_end": None,
            "total_days": 0,
            "is_custom_range": is_custom,
            "cutoff_date": cutoff_date,
            "data": [],
        }

    records = []
    has_hth_col = "hth_value" in stn_df.columns

    running_hth_map = {}
    if not has_hth_col:
        counter = 0
        for _, row in stn_df.iterrows():
            rf_val = row["rainfall_mm"]
            if pd.isnull(rf_val):
                counter = 0
            elif rf_val >= 1.0:
                counter = 0
            else:
                counter += 1
            running_hth_map[row["date_dt"]] = counter

    for _, row in recent_df.iterrows():
        d_val = row["date_dt"].strftime("%Y-%m-%d") if hasattr(row["date_dt"], "strftime") else str(row["date_dt"])
        rf = float(row["rainfall_mm"]) if pd.notnull(row["rainfall_mm"]) else None
        if has_hth_col and pd.notnull(row["hth_value"]):
            hth = int(row["hth_value"])
        else:
            hth = running_hth_map.get(row["date_dt"], 0)

        sym = str(row.get("original_symbol", "")) if "original_symbol" in row else None
        obs_st = "OBSERVED_VALID" if (rf is not None and rf >= 1.0) else ("OBSERVED_ZERO" if (rf is not None and rf == 0.0) else ("TTU" if sym == "TTU" else "MISSING"))

        if rf is None:
            status_desc = "Tidak tersedia"
        elif obs_st == "TTU":
            status_desc = "TTU (Jejak Hujan)"
        elif rf < 1.0:
            status_desc = "Hari Tanpa Hujan"
        else:
            status_desc = f"Hujan ({rf:.1f} mm)"

        records.append({
            "date": d_val,
            "rainfall_mm": rf,
            "status": status_desc,
            "obs_status": obs_st,
            "original_symbol": sym,
            "hth_days": hth,
        })

    p_start = records[0]["date"] if records else None
    p_end = records[-1]["date"] if records else None

    return {
        "station_id": station_id,
        "period_start": p_start,
        "period_end": p_end,
        "total_days": len(records),
        "is_custom_range": is_custom,
        "cutoff_date": cutoff_date,
        "data": records,
    }


def get_hth_category(hth_days: Optional[int]) -> str:
    """
    Standard CEWS HTH thresholds:
    0–20 hari: NORMAL
    21–30 hari: WASPADA
    31–60 hari: SIAGA
    >60 hari: AWAS
    """
    if hth_days is None:
        return "NORMAL"
    if hth_days <= 20:
        return "NORMAL"
    elif hth_days <= 30:
        return "WASPADA"
    elif hth_days <= 60:
        return "SIAGA"
    else:
        return "AWAS"


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:

    """Calculate Great Circle distance in km between two lat/lon coordinates."""
    R = 6371.0
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlam = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2.0)**2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlam / 2.0)**2
    return 2.0 * R * math.asin(math.sqrt(a))


def evaluate_station(
    station_id: str,
    current_record: Dict[str, Any],
    all_stations_map: List[Dict[str, Any]]
) -> Dict[str, Any]:
    """
    Perform Pass A Diagnostic Evaluation for a single station.
    Answers:
      1. Apakah HTH pada current warning konsisten dengan output pipeline HTH?
      2. Apakah station mapping yang digunakan benar?
      3. Apakah terdapat missing observation yang relevan?
      4. Kapan hujan signifikan terakhir (>=1 mm) tercatat?
      5. Bagaimana kondisi 3-5 station terdekat sebagai konteks spasial?
      6. Apakah terdapat mismatch faktual yang perlu ditinjau?
    """
    _ensure_data_loaded()

    sid_upper = station_id.strip().upper()
    cur_lat = float(current_record["latitude"])
    cur_lon = float(current_record["longitude"])
    cur_hth = int(current_record["hth_days_current"]) if current_record.get("hth_days_current") is not None else None

    # 1. Station Mapping Diagnostic (Master Authority: station_metadata.parquet)
    station_match = False
    coord_match = False
    meta_name = None
    if _META_DF is not None:
        meta_row = _META_DF[_META_DF["station_id_upper"] == sid_upper]
        if len(meta_row) > 0:
            station_match = True
            m = meta_row.iloc[0]
            meta_name = m.get("station_name")
            m_lat = float(m["latitude"])
            m_lon = float(m["longitude"])
            lat_diff = abs(cur_lat - m_lat)
            lon_diff = abs(cur_lon - m_lon)
            # Coordinate tolerance <= 1e-5
            coord_match = (lat_diff <= 1e-5) and (lon_diff <= 1e-5)

    mapping_diagnostic = {
        "station_match": station_match,
        "coordinate_match": coord_match
    }

    # 2. HTH Diagnostic (Lineage: hth_daily_2021_2025.parquet)
    pipe_info = _HTH_LATEST_MAP.get(sid_upper)
    has_pipeline = pipe_info is not None
    pipe_hth = pipe_info.get("hth_days") if has_pipeline else None
    hth_match = (cur_hth == pipe_hth) if (cur_hth is not None and pipe_hth is not None) else False

    recent_rainfall = []
    missing_days = 0
    last_rain_date_str = None
    days_since = None

    src_start = "2026-08-21"
    src_end = "2026-09-20"

    if _HTH_DF is not None:
        stn_all = _HTH_DF[
            (_HTH_DF["station_id_upper"] == sid_upper) &
            (_HTH_DF["date_dt"] <= CUTOFF_DATE)
        ].sort_values("date_dt")
        stn_slice = stn_all.tail(30)

        missing_days = int(stn_slice["is_missing"].sum()) if len(stn_slice) > 0 else 0
        if len(stn_slice) > 0:
            src_start = str(stn_slice["date_dt"].min())
            src_end = str(stn_slice["date_dt"].max())

        # Find last rain event >= 1.0 mm
        rain_events = stn_all[(stn_all["rainfall_mm"] >= 1.0) & (~stn_all["is_missing"])]
        if len(rain_events) > 0:
            last_rain_dt = rain_events.iloc[-1]["date_dt"]
            last_rain_date_str = str(last_rain_dt)
            max_dt = stn_slice["date_dt"].max() if len(stn_slice) > 0 else CUTOFF_DATE
            days_since = (max_dt - last_rain_dt).days
        elif pipe_info and pipe_info.get("last_rain_date"):
            last_rain_date_str = pipe_info.get("last_rain_date")
            days_since = pipe_info.get("days_since_last_rain")

        for _, r in stn_slice.iterrows():
            recent_rainfall.append({
                "date": str(r["date"])[:10],
                "rainfall_mm": round(float(r["rainfall_mm"]), 1) if pd.notnull(r["rainfall_mm"]) else 0.0,
                "is_missing": bool(r["is_missing"]),
                "hth_days": 0
            })
    elif pipe_info:
        last_rain_date_str = pipe_info.get("last_rain_date")
        days_since = pipe_info.get("days_since_last_rain")

    hth_diagnostic = {
        "current_warning_hth": cur_hth,
        "pipeline_hth": pipe_hth,
        "match": hth_match,
        "last_rain_date": last_rain_date_str,
        "days_since_last_rain": days_since,
        "missing_observation_days": missing_days,
        "source_period_start": src_start,
        "source_period_end": src_end
    }

    # 3. Diagnostic Status Determination
    # Strictly: CONSISTENT | REVIEW_REQUIRED | INSUFFICIENT_DATA
    reasons = []
    if not station_match or not coord_match:
        eval_status = "REVIEW_REQUIRED"
        if not station_match:
            reasons.append("Stasiun tidak ditemukan pada master metadata station_metadata.parquet.")
        if not coord_match:
            reasons.append("Koordinat latitude/longitude berbeda secara signifikan (>1e-5) dengan metadata master.")
    elif not has_pipeline or pipe_hth is None:
        eval_status = "INSUFFICIENT_DATA"
        reasons.append(f"Data pipeline HTH tidak ditemukan pada cutoff observasi {src_end}.")
    elif not hth_match:
        eval_status = "REVIEW_REQUIRED"
        reasons.append(f"Ketidaksesuaian nilai: HTH Current Warning ({cur_hth} hari) != HTH Pipeline ({pipe_hth} hari).")
    else:
        eval_status = "CONSISTENT"
        reasons.append(f"Nilai HTH Current Warning ({cur_hth} hari) konsisten dengan HTH Pipeline ({pipe_hth} hari).")
        if last_rain_date_str:
            reasons.append(f"Hujan signifikan terakhir (>=1.0 mm) tercatat pada {last_rain_date_str} ({days_since} hari sebelum cutoff observasi).")
        if missing_days == 0:
            reasons.append(f"Data observasi lengkap (0 hari missing pada deret observasi {src_start} s/d {src_end}).")
        else:
            reasons.append(f"Terdapat {missing_days} hari observasi missing pada deret observasi {src_start} s/d {src_end}.")

    # Spatial context notice (Section 10 & 26: never a rule)
    reasons.append("Perbedaan kondisi terhadap pos terdekat ditampilkan sebagai konteks spasial dan tidak digunakan sebagai rule validasi.")

    # 4. Nearest Stations (Top 5, Haversine, Distance ASC)
    candidates = []
    for other in all_stations_map:
        other_id = other["station_id"].strip().upper()
        if other_id == sid_upper:
            continue
        try:
            o_lat = float(other["latitude"])
            o_lon = float(other["longitude"])
            dist = haversine_km(cur_lat, cur_lon, o_lat, o_lon)
            candidates.append((dist, other))
        except (ValueError, TypeError):
            continue

    candidates.sort(key=lambda x: x[0])
    nearest_stations = []
    for dist, o in candidates[:5]:
        o_hth = int(o["hth_days_current"]) if o.get("hth_days_current") is not None else None
        o_sid = str(o["station_id"]).strip().upper()
        o_lr = _HTH_LATEST_MAP.get(o_sid, {}).get("last_rain_date")
        nearest_stations.append({
            "station_id": o["station_id"],
            "station_name": o["station_name"],
            "kabupaten": o.get("kabupaten", ""),
            "distance_km": round(dist, 2),
            "hth_days_current": o_hth,
            "warning_level": o["warning_level"],
            "data_quality_status": o.get("data_quality_status", "VALID"),
            "last_rain_date": o_lr
        })

    # Assemble Final Standard Contract
    return {
        "station": {
            "station_id": current_record["station_id"],
            "station_name": current_record["station_name"],
            "kabupaten": current_record["kabupaten"],
            "latitude": cur_lat,
            "longitude": cur_lon
        },
        "current_state": {
            "warning_level": current_record["warning_level"],
            "hazard_type": current_record.get("hazard_type", "NORMAL"),
            "hth_days_current": cur_hth,
            "hth_uncertain": bool(current_record.get("hth_uncertain", False)),
            "data_quality_status": current_record.get("data_quality_status", "VALID"),
            "confidence_level": current_record.get("confidence_level", "MEDIUM"),
            "last_observation_date": str(current_record.get("last_observation_date", "2025-12-31"))
        },
        "hth_diagnostic": hth_diagnostic,
        "mapping_diagnostic": mapping_diagnostic,
        "nearest_stations": nearest_stations,
        "evaluation": {
            "status": eval_status,
            "reasons": reasons
        },
        "observation_diagnostics": {
            "latest_hth_pipeline_value": pipe_hth,
            "last_rain_date": last_rain_date_str,
            "missing_observation_days": missing_days,
            "source_available": has_pipeline,
            "recent_rainfall": recent_rainfall
        }
    }
