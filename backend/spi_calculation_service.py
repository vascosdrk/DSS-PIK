"""
backend/spi_calculation_service.py
Service layer and execution orchestrator for Manual SPI Generator in DSS-PIK.
Handles staging, worker dispatching via Joblib, atomic Parquet commit,
and system-wide cache invalidation.
Decision Support System Peringatan Iklim Kepulauan Riau (DSS-PIK)
"""

import os
import shutil
import uuid
from datetime import datetime, date
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple

import pandas as pd
import numpy as np
from joblib import Parallel, delayed

from backend.database import get_db
from backend.rainfall_normalization import (
    build_station_numeric_series,
    evaluate_output_date_range_compliance,
)
from backend.spi_distribution_registry import (
    get_station_scale_distribution,
    get_available_distributions_summary,
    DIST_PRETTY_NAME
)
from backend.spi_calculation_worker import (
    calculate_station_spi_worker,
    RESOLUTION_CONFIG
)
from config.paths import (
    PATH_STATION_METADATA,
    PATH_SPI_PARQUET_DASARIAN_30D,
    PATH_SPI_PARQUET_DASARIAN_90D,
    SPI_RAW_DIR
)

# In-memory staging for generated sessions before commit
_GENERATOR_SESSIONS: Dict[str, Dict[str, Any]] = {}

# 5 ARG Stations strictly exempt from SPI fitting (canonical 5 ARG in Kepri)
ARG_STATION_IDS = {
    "21010603B", "21010802B", "21020402B", "21040101B", "21710501B",
    "21020202B", "21030403B", "21050201B"
}


def get_generator_readiness_options() -> Dict[str, Any]:
    """Returns available options, scales, and station counts for the SPI Generator modal."""
    # Query rainfall date range from MariaDB
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT MIN(observation_date) as min_date, MAX(observation_date) as max_date,
                       COUNT(DISTINCT station_id) as total_stations_reporting
                FROM cews_rainfall_daily
            """)
            rf_summary = cur.fetchone()
            
            cur.execute("""
                SELECT station_id, station_name, kabupaten
                FROM stations
                ORDER BY kabupaten, station_name
            """)
            stations = cur.fetchall()

    min_date_str = rf_summary["min_date"].strftime("%Y-%m-%d") if rf_summary and rf_summary["min_date"] else "-"
    max_date_str = rf_summary["max_date"].strftime("%Y-%m-%d") if rf_summary and rf_summary["max_date"] else "-"

    stn_list = []
    for s in stations:
        sid = s["station_id"].strip().upper()
        is_arg = sid in ARG_STATION_IDS or sid.endswith("B")
        stn_list.append({
            "station_id": sid,
            "station_name": s["station_name"],
            "kabupaten": s["kabupaten"],
            "is_arg": is_arg,
            "eligible_for_spi": not is_arg
        })

    return {
        "rainfall_data_range": {
            "start_date": min_date_str,
            "end_date": max_date_str,
            "stations_reporting": rf_summary["total_stations_reporting"] if rf_summary else 0
        },
        "available_products": [
            {"resolution": "HARIAN", "label": "SPI Harian (30D)", "timescale": 30, "fit_freq": "D"},
            {"resolution": "HARIAN", "label": "SPI Harian (90D)", "timescale": 90, "fit_freq": "D"},
            {"resolution": "DASARIAN", "label": "SPI 3 Dasarian (30D)", "timescale": 30, "fit_freq": "dekad"},
            {"resolution": "DASARIAN", "label": "SPI 9 Dasarian (90D)", "timescale": 90, "fit_freq": "dekad"},
            {"resolution": "BULANAN", "label": "SPI 1 Bulan (30D)", "timescale": 30, "fit_freq": "monthly"},
            {"resolution": "BULANAN", "label": "SPI 3 Bulan (90D)", "timescale": 90, "fit_freq": "monthly"},
        ],
        "stations": stn_list
    }


def prepare_spi_preview_summary(
    resolution: str,
    timescale: int,
    selected_stations: Optional[List[str]] = None,
    output_start_date: Optional[str] = None,
    output_end_date: Optional[str] = None
) -> Dict[str, Any]:
    """
    Validates input stations, checks distribution registry availability,
    and returns a preview summary before operator triggers calculation.
    """
    res_key = resolution.strip().upper()
    if res_key not in RESOLUTION_CONFIG:
        raise ValueError(f"Resolusi '{resolution}' tidak valid. Pilih HARIAN, DASARIAN, atau BULANAN.")

    ts = int(timescale)
    if ts not in RESOLUTION_CONFIG[res_key]["supported_timescales"]:
        raise ValueError(f"Timescale {timescale} tidak valid untuk resolusi {resolution}.")

    # Load distribution registry for this resolution and scale
    dist_info = get_available_distributions_summary(
        resolution=RESOLUTION_CONFIG[res_key]["dist_file_key"],
        timescale=ts
    )
    dist_station_map = dist_info["station_map"]

    # Load master stations
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT station_id, station_name, kabupaten FROM stations ORDER BY kabupaten, station_name")
            all_stns = cur.fetchall()

    if selected_stations:
        req_set = set(str(s).strip().upper() for s in selected_stations)
        eval_stns = [s for s in all_stns if s["station_id"].strip().upper() in req_set]
    else:
        # Default: all 52 manual stations (excluding 5 ARG)
        eval_stns = [s for s in all_stns if s["station_id"].strip().upper() not in ARG_STATION_IDS]

    eligible_stations = []
    ineligible_stations = []

    for s in eval_stns:
        sid = s["station_id"].strip().upper()
        if sid in ARG_STATION_IDS:
            ineligible_stations.append({
                "station_id": sid,
                "station_name": s["station_name"],
                "kabupaten": s["kabupaten"],
                "reason": "Pos Automatic Rain Gauge (ARG) — dikecualikan dari perhitungan SPI."
            })
            continue

        if sid not in dist_station_map:
            ineligible_stations.append({
                "station_id": sid,
                "station_name": s["station_name"],
                "kabupaten": s["kabupaten"],
                "reason": f"Tidak ditemukan distribusi konsensus BestDist untuk skala {ts} di CSV referensi."
            })
            continue

        d = dist_station_map[sid]
        eligible_stations.append({
            "station_id": sid,
            "station_name": s["station_name"],
            "kabupaten": s["kabupaten"],
            "dist_code": d["dist_code"],
            "dist_name": d["dist_name"],
            "zom": d["zom"]
        })

    target_parquet = RESOLUTION_CONFIG[res_key]["output_parquet"][ts]

    return {
        "resolution": res_key,
        "timescale": ts,
        "fit_freq": RESOLUTION_CONFIG[res_key]["fit_freq"],
        "target_parquet_path": str(target_parquet.relative_to(Path(SPI_RAW_DIR).parent.parent)),
        "output_filter": {
            "start_date": output_start_date,
            "end_date": output_end_date
        },
        "summary": {
            "total_requested_stations": len(eval_stns),
            "eligible_stations_count": len(eligible_stations),
            "ineligible_stations_count": len(ineligible_stations)
        },
        "eligible_stations": eligible_stations,
        "ineligible_stations": ineligible_stations
    }


def execute_spi_generation(
    resolution: str,
    timescale: int,
    selected_stations: Optional[List[str]] = None,
    output_start_date: Optional[str] = None,
    output_end_date: Optional[str] = None,
    n_workers: int = 4
) -> Dict[str, Any]:
    """
    Executes parallel calculation using Joblib and stores the result in a staging session.
    Does NOT modify the canonical Parquet files until explicit commit.
    """
    preview = prepare_spi_preview_summary(
        resolution=resolution,
        timescale=timescale,
        selected_stations=selected_stations,
        output_start_date=output_start_date,
        output_end_date=output_end_date
    )

    eligible = preview["eligible_stations"]
    if not eligible:
        raise ValueError("Tidak ada stasiun yang memenuhi syarat untuk dihitung.")

    target_sids = [e["station_id"] for e in eligible]
    dist_map = {e["station_id"]: e["dist_code"] for e in eligible}

    # Fetch entire historical rainfall series for target stations from MariaDB
    # (Entire history is needed for valid rolling and statistical fitting)
    with get_db() as conn:
        with conn.cursor() as cur:
            format_strings = ','.join(['%s'] * len(target_sids))
            query = f"""
                SELECT station_id, observation_date, rainfall_mm, obs_status
                FROM cews_rainfall_daily
                WHERE station_id IN ({format_strings})
                  AND (obs_status IS NULL OR UPPER(obs_status) != 'VOID')
                ORDER BY station_id, observation_date ASC
            """
            cur.execute(query, tuple(target_sids))
            rows = cur.fetchall()

    # Group series by station using centralized DSS-PIK numeric normalization:
    # - TTU and OBSERVED_ZERO ('-') -> 0.0 mm in numeric processing (TTU remains 'TTU' in CH table)
    # - MISSING, MISSING_INTERNAL, DAMAGED, AMBIGUOUS -> NaN
    # - VOID -> excluded
    station_series = build_station_numeric_series(rows, target_sids)

    # Parallel calculation via Joblib with automatic Sequential fallback
    # On Windows, adaptively cap workers to 4 to prevent OS handle exhaustion
    configured_workers = max(1, min(n_workers, 4, os.cpu_count() or 2))
    
    results = []
    used_fallback = False
    
    if configured_workers > 1:
        try:
            results = Parallel(
                n_jobs=configured_workers,
                backend="loky",
                verbose=0,
                max_nbytes="50M",
                timeout=120
            )(
                delayed(calculate_station_spi_worker)(
                    station_id=sid,
                    series_dict=station_series[sid],
                    resolution=preview["resolution"],
                    timescale=preview["timescale"],
                    dist_code=dist_map[sid]
                )
                for sid in target_sids
            )
        except Exception as parallel_err:
            print(f"[Warning] Parallel calculation via loky failed ({parallel_err}). Executing serial fallback...")
            used_fallback = True
            results = []
    else:
        used_fallback = False

    # Check for any failed/unprocessed stations and calculate sequentially
    processed_sids = {r["station_id"] for r in results if r.get("status") in ("SUCCESS", "SKIPPED")}
    missing_sids = [sid for sid in target_sids if sid not in processed_sids]
    
    if missing_sids:
        if configured_workers > 1 and not used_fallback:
            print(f"[Info] Executing sequential fallback for {len(missing_sids)} unprocessed station(s)...")
        fallback_results = []
        for sid in missing_sids:
            try:
                res_single = calculate_station_spi_worker(
                    station_id=sid,
                    series_dict=station_series[sid],
                    resolution=preview["resolution"],
                    timescale=preview["timescale"],
                    dist_code=dist_map[sid]
                )
                fallback_results.append(res_single)
            except Exception as single_err:
                fallback_results.append({
                    "station_id": sid,
                    "status": "ERROR",
                    "message": f"Fallback error: {single_err}",
                    "calculated_series": None
                })
        
        # Merge results, keeping existing successes
        results_map = {r["station_id"]: r for r in results if r.get("status") == "SUCCESS"}
        for fr in fallback_results:
            results_map[fr["station_id"]] = fr
        results = [results_map[sid] for sid in target_sids if sid in results_map]

    # Assemble into a wide format DataFrame
    station_series_map = {}
    success_count = 0
    error_count = 0
    results_detail = []

    for r in results:
        sid = r["station_id"]
        status = r["status"]
        if status == "SUCCESS" and r.get("series_data"):
            s_data = r["series_data"]
            s = pd.Series(s_data["values"], index=pd.to_datetime(s_data["dates"]), name=sid)
            station_series_map[sid] = s
            success_count += 1
        else:
            error_count += 1
        results_detail.append({
            "station_id": sid,
            "status": status,
            "message": r["message"],
            "total_computed": r.get("total_computed", 0)
        })

    if not station_series_map:
        raise RuntimeError("Semua stasiun gagal dihitung. Periksa detail error pada respon.")

    df_wide = pd.DataFrame(station_series_map)
    df_wide.index.name = "date"
    df_wide = df_wide.sort_index()

    # Filter output date range if specified (without affecting the historical calculation above)
    if output_start_date:
        df_wide = df_wide[df_wide.index >= pd.to_datetime(output_start_date)]
    if output_end_date:
        df_wide = df_wide[df_wide.index <= pd.to_datetime(output_end_date)]

    actual_start = df_wide.index.min().strftime("%Y-%m-%d") if not df_wide.empty else "-"
    actual_end = df_wide.index.max().strftime("%Y-%m-%d") if not df_wide.empty else "-"
    range_check = evaluate_output_date_range_compliance(
        actual_start=actual_start,
        actual_end=actual_end,
        requested_start=output_start_date,
        requested_end=output_end_date,
        output_rows=len(df_wide),
        resolution=preview["resolution"],
    )

    session_token = f"SPI_GEN_{uuid.uuid4().hex[:12].upper()}"
    _GENERATOR_SESSIONS[session_token] = {
        "token": session_token,
        "created_at": datetime.now().isoformat(),
        "resolution": preview["resolution"],
        "timescale": preview["timescale"],
        "fit_freq": preview["fit_freq"],
        "target_parquet_path": RESOLUTION_CONFIG[preview["resolution"]]["output_parquet"][preview["timescale"]],
        "df_wide": df_wide,
        "results_detail": results_detail,
        "summary": {
            "total_requested": len(target_sids),
            "success_count": success_count,
            "error_count": error_count,
            "computed_rows": len(df_wide),
            "date_range_start": actual_start,
            "date_range_end": actual_end,
            **range_check,
        }
    }

    return {
        "session_token": session_token,
        "status": "COMPLETED",
        "summary": _GENERATOR_SESSIONS[session_token]["summary"],
        "results_detail": results_detail,
        "sample_preview": {
            "dates": [d.strftime("%Y-%m-%d") for d in df_wide.index[-5:]] if not df_wide.empty else [],
            "stations": list(df_wide.columns[:5]),
            "values": df_wide.iloc[-5:, :5].replace({np.nan: None}).to_dict(orient="records") if not df_wide.empty else []
        }
    }


import threading

_SPI_COMMIT_LOCK = threading.Lock()


def commit_spi_generation_session(session_token: str, operator_notes: Optional[str] = None) -> Dict[str, Any]:
    """
    Atomically merges generated SPI values into canonical Parquet storage,
    creates a timestamped backup, and invalidates all backend caches.
    Protected by _SPI_COMMIT_LOCK to prevent concurrent Parquet corruption.
    """
    if not _SPI_COMMIT_LOCK.acquire(blocking=False):
        raise RuntimeError("Proses commit SPI ke Parquet sedang berjalan oleh operator lain. Silakan tunggu sebentar.")
    try:
        return _commit_spi_generation_session_impl(session_token, operator_notes)
    finally:
        _SPI_COMMIT_LOCK.release()


def _commit_spi_generation_session_impl(session_token: str, operator_notes: Optional[str] = None) -> Dict[str, Any]:
    staged_file_to_cleanup: Optional[Path] = None
    if session_token in _GENERATOR_SESSIONS:
        session = _GENERATOR_SESSIONS[session_token]
        if session.get("staged_parquet_path"):
            staged_file_to_cleanup = Path(session["staged_parquet_path"])
    else:
        # Fallback: recover staged Parquet artifact from persistent MariaDB job table (survives restarts!)
        with get_db() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT resolution, timescale, staged_parquet_path, target_parquet_path
                    FROM cews_spi_generation_jobs
                    WHERE session_token = %s AND status = 'SUCCEEDED'
                    LIMIT 1
                    """,
                    (session_token,),
                )
                job_row = cur.fetchone()
        if not job_row or not job_row.get("staged_parquet_path") or not Path(job_row["staged_parquet_path"]).exists():
            raise ValueError(f"Sesi generator '{session_token}' tidak ditemukan atau telah kedaluwarsa.")
        staged_file_to_cleanup = Path(job_row["staged_parquet_path"])
        df_staged = pd.read_parquet(staged_file_to_cleanup)
        session = {
            "token": session_token,
            "resolution": job_row["resolution"],
            "timescale": int(job_row["timescale"]),
            "target_parquet_path": Path(job_row["target_parquet_path"]),
            "df_wide": df_staged,
        }

    target_path = Path(session["target_parquet_path"])
    df_new = session["df_wide"]

    # Ensure parent dir exists
    target_path.parent.mkdir(parents=True, exist_ok=True)

    # Create timestamped backup of existing canonical parquet
    backup_path = None
    if target_path.exists():
        backup_path = target_path.with_suffix(f".parquet.bak_gen_{datetime.now().strftime('%Y%m%d%H%M%S')}")
        shutil.copy2(target_path, backup_path)

    try:
        if target_path.exists():
            df_cur = pd.read_parquet(target_path)
            if not isinstance(df_cur.index, pd.DatetimeIndex):
                if "date" in df_cur.columns:
                    df_cur.index = pd.to_datetime(df_cur["date"])
                    df_cur = df_cur.drop(columns=["date"])
                else:
                    df_cur.index = pd.to_datetime(df_cur.index)

            # Drop metadata columns
            meta_cols = [c for c in df_cur.columns if str(c).strip().lower() in {
                "station_id", "station_name", "date", "ref_date", "period_id", "target_period",
                "year", "month", "scale", "indicator", "spi_value", "new_value", "old_value"
            }]
            if meta_cols:
                df_cur = df_cur.drop(columns=meta_cols)

            df_cur.columns = [str(c).strip().upper() for c in df_cur.columns]
            df_new.columns = [str(c).strip().upper() for c in df_new.columns]

            # Union of dates and columns, update values atomically
            all_dates = df_cur.index.union(df_new.index).sort_values()
            all_cols = sorted(list(set(df_cur.columns).union(set(df_new.columns))))

            df_merged = df_cur.reindex(index=all_dates, columns=all_cols)
            df_new_reindexed = df_new.reindex(index=all_dates, columns=all_cols)
            df_merged.update(df_new_reindexed)
        else:
            df_merged = df_new

        df_merged.index.name = "date"
        tmp_path = target_path.with_suffix(".parquet.tmp")
        df_merged.to_parquet(tmp_path)
        os.replace(tmp_path, target_path)

    except Exception as e:
        if backup_path and backup_path.exists():
            shutil.copy2(backup_path, target_path)
        raise RuntimeError(f"Gagal commit file Parquet: {e}")

    # Remove staging session & disk staging artifact
    _GENERATOR_SESSIONS.pop(session_token, None)
    if staged_file_to_cleanup and staged_file_to_cleanup.exists():
        try:
            staged_file_to_cleanup.unlink()
        except Exception:
            pass

    # Invalidate caches
    try:
        from backend.data_service import clear_spi_cache
        clear_spi_cache()
    except Exception:
        pass
    try:
        from backend.main import _SNAPSHOTS_CACHE
        _SNAPSHOTS_CACHE.clear()
    except Exception:
        pass
    try:
        import backend.evaluation as eval_mod
        eval_mod._META_DF = None
        eval_mod._HTH_DF = None
        eval_mod._CW_DF = None
        eval_mod._HTH_LATEST_MAP = {}
    except Exception:
        pass
    try:
        import backend.regional_warning_service as rws_mod
        if hasattr(rws_mod, '_CACHED_RECOMMENDATIONS'):
            rws_mod._CACHED_RECOMMENDATIONS.clear()
    except Exception:
        pass

    return {
        "status": "SUCCESS",
        "message": f"Dataset {session['resolution']} {session['timescale']}D berhasil disimpan ke storage kanonikal.",
        "target_parquet": str(target_path.name),
        "backup_created": str(backup_path.name) if backup_path else None,
        "committed_records": len(df_new)
    }

