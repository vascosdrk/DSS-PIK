"""
backend/spi_job_service.py
MariaDB-Backed Persistent Asynchronous Job Engine for DSS-PIK SPI Generator.

Eliminates Cloudflare HTTP 524 timeouts on heavy SPI Daily (fit_freq='D') runs by:
1. Accepting generation requests immediately (< 1s) and returning a persistent job_id.
2. Executing per-station si.spi() calculations asynchronously via ProcessPoolExecutor
   with real-time per-station progress and MariaDB heartbeat updates.
3. Deduplicating identical concurrent jobs (via job_key).
4. Persisting staged Parquet output to disk so results survive restarts and never
   double-write canonical Parquet files until explicit operator commit.
5. Automatically marking orphaned/stale jobs (after container restart) as FAILED
   with safe Retry support.
"""

from __future__ import annotations

import hashlib
import json
import logging
import multiprocessing
import os
import threading
import time
import uuid
from concurrent.futures import ProcessPoolExecutor, as_completed
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional

import numpy as np
import pandas as pd

from backend.database import get_db
from backend.spi_calculation_service import (
    RESOLUTION_CONFIG,
    SPI_RAW_DIR,
    _GENERATOR_SESSIONS,
    prepare_spi_preview_summary,
)
from backend.spi_calculation_worker import calculate_station_spi_worker

logger = logging.getLogger(__name__)

STAGING_PARQUET_DIR = Path(SPI_RAW_DIR) / "_staging"
STALE_HEARTBEAT_SECONDS = 300  # 5 minutes without heartbeat -> orphaned by restart
_ACTIVE_CANCEL_FLAGS: Dict[str, threading.Event] = {}
_JOB_SUBMIT_LOCK = threading.Lock()


def ensure_spi_jobs_table() -> None:
    sql = """
    CREATE TABLE IF NOT EXISTS cews_spi_generation_jobs (
        job_id                VARCHAR(64)     NOT NULL,
        job_key               VARCHAR(128)    NOT NULL,
        status                VARCHAR(20)     NOT NULL DEFAULT 'QUEUED',
        resolution            VARCHAR(20)     NOT NULL,
        timescale             INT             NOT NULL,
        request_params_json   LONGTEXT        NULL,
        total_stations        INT             NOT NULL DEFAULT 0,
        completed_stations    INT             NOT NULL DEFAULT 0,
        success_count         INT             NOT NULL DEFAULT 0,
        error_count           INT             NOT NULL DEFAULT 0,
        progress_pct          DECIMAL(5,2)    NOT NULL DEFAULT 0.00,
        current_station       VARCHAR(50)     NULL,
        stage_message         VARCHAR(255)    NULL,
        session_token         VARCHAR(64)     NULL,
        staged_parquet_path   VARCHAR(512)    NULL,
        target_parquet_path   VARCHAR(512)    NULL,
        result_summary_json   LONGTEXT        NULL,
        results_detail_json   LONGTEXT        NULL,
        sample_preview_json   LONGTEXT        NULL,
        error_message         TEXT            NULL,
        operator              VARCHAR(100)    NOT NULL DEFAULT 'OPERATOR_BMKG',
        attempt_count         INT             NOT NULL DEFAULT 1,
        heartbeat_at          DATETIME        NULL,
        started_at            DATETIME        NULL,
        finished_at           DATETIME        NULL,
        created_at            DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP,
        updated_at            DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
        PRIMARY KEY (job_id),
        INDEX idx_spi_job_status (status, created_at),
        INDEX idx_spi_job_key_status (job_key, status),
        INDEX idx_spi_job_token (session_token)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
    """
    try:
        with get_db() as conn:
            with conn.cursor() as cur:
                cur.execute(sql)
            conn.commit()
    except Exception as exc:
        logger.warning("Could not ensure cews_spi_generation_jobs table: %s", exc)


def recover_stale_spi_jobs() -> int:
    """Marks QUEUED/RUNNING jobs whose worker heartbeat expired (e.g., container restart) as FAILED."""
    ensure_spi_jobs_table()
    cutoff = (datetime.now() - timedelta(seconds=STALE_HEARTBEAT_SECONDS)).strftime("%Y-%m-%d %H:%M:%S")
    try:
        with get_db() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    UPDATE cews_spi_generation_jobs
                    SET status = 'FAILED',
                        error_message = 'Proses terhenti karena server restart atau worker tidak merespons. Gunakan tombol Coba Lagi (Retry).',
                        stage_message = 'Dihentikan (stale heartbeat)',
                        finished_at = CURRENT_TIMESTAMP
                    WHERE status IN ('QUEUED', 'RUNNING')
                      AND COALESCE(heartbeat_at, created_at) < %s
                    """,
                    (cutoff,),
                )
                affected = cur.rowcount
            conn.commit()
        return affected
    except Exception as exc:
        logger.warning("Could not recover stale SPI jobs: %s", exc)
        return 0


def _build_job_key(
    resolution: str,
    timescale: int,
    selected_stations: Optional[List[str]],
    output_start_date: Optional[str],
    output_end_date: Optional[str],
) -> str:
    payload = {
        "resolution": resolution.strip().upper(),
        "timescale": int(timescale),
        "stations": sorted(s.strip().upper() for s in (selected_stations or [])),
        "start": output_start_date or "",
        "end": output_end_date or "",
    }
    return hashlib.sha256(json.dumps(payload, sort_keys=True).encode("utf-8")).hexdigest()[:40]


def _update_job_fields(job_id: str, **fields: Any) -> None:
    if not fields:
        return
    cols = ", ".join(f"{k} = %s" for k in fields)
    vals = list(fields.values()) + [job_id]
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(f"UPDATE cews_spi_generation_jobs SET {cols} WHERE job_id = %s", tuple(vals))
        conn.commit()


def _is_job_cancelled_in_db(job_id: str) -> bool:
    ev = _ACTIVE_CANCEL_FLAGS.get(job_id)
    if ev and ev.is_set():
        return True
    try:
        with get_db() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT status FROM cews_spi_generation_jobs WHERE job_id = %s", (job_id,))
                row = cur.fetchone()
                return bool(row and row["status"] == "CANCELLED")
    except Exception:
        return False


def _run_spi_job_worker(job_id: str, params: Dict[str, Any]) -> None:
    """Background worker executing SPI calculation with per-station progress & heartbeat."""
    t_start = time.perf_counter()
    try:
        _update_job_fields(
            job_id,
            status="RUNNING",
            started_at=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            heartbeat_at=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            stage_message="Memvalidasi kesiapan stasiun & distribusi BestDist...",
        )

        preview = prepare_spi_preview_summary(
            resolution=params["resolution"],
            timescale=int(params["timescale"]),
            selected_stations=params.get("selected_stations"),
            output_start_date=params.get("output_start_date"),
            output_end_date=params.get("output_end_date"),
        )
        eligible = preview["eligible_stations"]
        if not eligible:
            raise ValueError("Tidak ada stasiun yang memenuhi syarat untuk dihitung.")

        target_sids = [e["station_id"] for e in eligible]
        dist_map = {e["station_id"]: e["dist_code"] for e in eligible}
        total_stns = len(target_sids)

        _update_job_fields(
            job_id,
            total_stations=total_stns,
            heartbeat_at=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            stage_message=f"Mengambil deret curah hujan aktif MariaDB ({total_stns} stasiun)...",
        )

        # Optimized batch fetch: omit SQL ORDER BY (avoids MariaDB filesort on 280K rows;
        # each station's series is sorted in-memory inside calculate_station_spi_worker).
        # Excludes VOID rows at query level.
        with get_db() as conn:
            with conn.cursor() as cur:
                fmt = ",".join(["%s"] * len(target_sids))
                cur.execute(
                    f"""
                    SELECT station_id, observation_date, rainfall_mm, obs_status
                    FROM cews_rainfall_daily
                    WHERE station_id IN ({fmt})
                      AND (obs_status IS NULL OR UPPER(obs_status) != 'VOID')
                    """,
                    tuple(target_sids),
                )
                rows = cur.fetchall()

        if _is_job_cancelled_in_db(job_id):
            return

        non_numeric_statuses = {"TTU", "MISSING", "DAMAGED", "VOID", "AMBIGUOUS"}
        station_series: Dict[str, Dict[str, List[Any]]] = {sid: {"dates": [], "values": []} for sid in target_sids}
        for r in rows:
            sid = r["station_id"].strip().upper()
            if sid in station_series:
                obs_st = (r.get("obs_status") or "").strip().upper()
                v = np.nan if (obs_st in non_numeric_statuses or r["rainfall_mm"] is None) else float(r["rainfall_mm"])
                station_series[sid]["dates"].append(r["observation_date"].strftime("%Y-%m-%d"))
                station_series[sid]["values"].append(v)

        n_workers = max(1, min(int(params.get("n_workers") or 4), os.cpu_count() or 2, 4))
        _update_job_fields(
            job_id,
            heartbeat_at=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            stage_message=f"Menjalankan kalkulasi si.spi ({preview['resolution']} {preview['timescale']}D, {n_workers} worker)...",
        )

        results: List[Dict[str, Any]] = []
        completed = 0
        success_cnt = 0
        error_cnt = 0

        if n_workers > 1 and total_stns > 1:
            try:
                # Explicitly use 'spawn' context on Linux Docker to avoid fork()-in-multithreaded-uvicorn deadlocks
                mp_ctx = multiprocessing.get_context("spawn")
                with ProcessPoolExecutor(max_workers=n_workers, mp_context=mp_ctx) as pool:
                    fut_to_sid = {
                        pool.submit(
                            calculate_station_spi_worker,
                            sid,
                            station_series[sid],
                            preview["resolution"],
                            int(preview["timescale"]),
                            dist_map[sid],
                        ): sid
                        for sid in target_sids
                    }
                    for fut in as_completed(fut_to_sid):
                        if _is_job_cancelled_in_db(job_id):
                            pool.shutdown(wait=False, cancel_futures=True)
                            return
                        sid = fut_to_sid[fut]
                        try:
                            res_item = fut.result()
                        except Exception as exc:
                            res_item = {"station_id": sid, "status": "ERROR", "message": f"Worker error: {exc}"}
                        results.append(res_item)
                        completed += 1
                        if res_item.get("status") == "SUCCESS":
                            success_cnt += 1
                        else:
                            error_cnt += 1
                        pct = round((completed / total_stns) * 100.0, 2)
                        _update_job_fields(
                            job_id,
                            completed_stations=completed,
                            success_count=success_cnt,
                            error_count=error_cnt,
                            progress_pct=pct,
                            current_station=sid,
                            heartbeat_at=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                            stage_message=f"Menghitung SPI: {completed}/{total_stns} stasiun selesai ({pct:.0f}%)",
                        )
            except Exception as pool_err:
                logger.warning("ProcessPoolExecutor fallback to serial for job %s: %s", job_id, pool_err)
                done_sids = {r["station_id"] for r in results}
                for sid in target_sids:
                    if sid in done_sids:
                        continue
                    if _is_job_cancelled_in_db(job_id):
                        return
                    res_item = calculate_station_spi_worker(
                        sid, station_series[sid], preview["resolution"], int(preview["timescale"]), dist_map[sid]
                    )
                    results.append(res_item)
                    completed += 1
                    if res_item.get("status") == "SUCCESS":
                        success_cnt += 1
                    else:
                        error_cnt += 1
                    pct = round((completed / total_stns) * 100.0, 2)
                    _update_job_fields(
                        job_id,
                        completed_stations=completed,
                        success_count=success_cnt,
                        error_count=error_cnt,
                        progress_pct=pct,
                        current_station=sid,
                        heartbeat_at=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                        stage_message=f"Menghitung SPI (serial): {completed}/{total_stns} stasiun ({pct:.0f}%)",
                    )
        else:
            for sid in target_sids:
                if _is_job_cancelled_in_db(job_id):
                    return
                res_item = calculate_station_spi_worker(
                    sid, station_series[sid], preview["resolution"], int(preview["timescale"]), dist_map[sid]
                )
                results.append(res_item)
                completed += 1
                if res_item.get("status") == "SUCCESS":
                    success_cnt += 1
                else:
                    error_cnt += 1
                pct = round((completed / total_stns) * 100.0, 2)
                _update_job_fields(
                    job_id,
                    completed_stations=completed,
                    success_count=success_cnt,
                    error_count=error_cnt,
                    progress_pct=pct,
                    current_station=sid,
                    heartbeat_at=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    stage_message=f"Menghitung SPI: {completed}/{total_stns} stasiun selesai ({pct:.0f}%)",
                )

        if _is_job_cancelled_in_db(job_id):
            return

        # Assemble wide DataFrame
        results_by_sid = {r["station_id"]: r for r in results}
        station_series_map = {}
        results_detail = []
        for sid in target_sids:
            r = results_by_sid.get(sid, {"station_id": sid, "status": "ERROR", "message": "Tidak ada hasil"})
            if r.get("status") == "SUCCESS" and r.get("series_data"):
                s_data = r["series_data"]
                station_series_map[sid] = pd.Series(s_data["values"], index=pd.to_datetime(s_data["dates"]), name=sid)
            results_detail.append({
                "station_id": sid,
                "status": r.get("status", "ERROR"),
                "message": r.get("message", ""),
                "total_computed": r.get("total_computed", 0),
            })

        if not station_series_map:
            raise RuntimeError("Semua stasiun gagal dihitung. Periksa kelengkapan data curah hujan.")

        df_wide = pd.DataFrame(station_series_map)
        df_wide.index.name = "date"
        df_wide = df_wide.sort_index()

        if params.get("output_start_date"):
            df_wide = df_wide[df_wide.index >= pd.to_datetime(params["output_start_date"])]
        if params.get("output_end_date"):
            df_wide = df_wide[df_wide.index <= pd.to_datetime(params["output_end_date"])]

        # Persist staged Parquet artifact to disk (survives restarts!)
        STAGING_PARQUET_DIR.mkdir(parents=True, exist_ok=True)
        session_token = f"SPI_GEN_{uuid.uuid4().hex[:12].upper()}"
        staged_path = STAGING_PARQUET_DIR / f"{session_token}.parquet"
        df_wide.to_parquet(staged_path)

        target_parquet = RESOLUTION_CONFIG[preview["resolution"]]["output_parquet"][int(preview["timescale"])]
        elapsed = round(time.perf_counter() - t_start, 2)

        summary = {
            "total_requested": total_stns,
            "success_count": success_cnt,
            "error_count": error_cnt,
            "computed_rows": len(df_wide),
            "date_range_start": df_wide.index.min().strftime("%Y-%m-%d") if not df_wide.empty else "-",
            "date_range_end": df_wide.index.max().strftime("%Y-%m-%d") if not df_wide.empty else "-",
            "elapsed_seconds": elapsed,
        }
        sample_preview = {
            "dates": [d.strftime("%Y-%m-%d") for d in df_wide.index[-5:]] if not df_wide.empty else [],
            "stations": list(df_wide.columns[:5]),
            "values": df_wide.iloc[-5:, :5].replace({np.nan: None}).to_dict(orient="records") if not df_wide.empty else [],
        }

        # Populate in-memory cache too for instant commit
        _GENERATOR_SESSIONS[session_token] = {
            "token": session_token,
            "created_at": datetime.now().isoformat(),
            "resolution": preview["resolution"],
            "timescale": int(preview["timescale"]),
            "fit_freq": preview["fit_freq"],
            "target_parquet_path": target_parquet,
            "staged_parquet_path": str(staged_path),
            "df_wide": df_wide,
            "results_detail": results_detail,
            "summary": summary,
        }

        _update_job_fields(
            job_id,
            status="SUCCEEDED",
            completed_stations=total_stns,
            success_count=success_cnt,
            error_count=error_cnt,
            progress_pct=100.0,
            session_token=session_token,
            staged_parquet_path=str(staged_path),
            target_parquet_path=str(target_parquet),
            result_summary_json=json.dumps(summary),
            results_detail_json=json.dumps(results_detail),
            sample_preview_json=json.dumps(sample_preview),
            stage_message=f"Kalkulasi SPI selesai dalam {elapsed:.1f} detik ({success_cnt}/{total_stns} stasiun).",
            heartbeat_at=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            finished_at=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        )
    except Exception as exc:
        logger.exception("SPI job %s failed", job_id)
        _update_job_fields(
            job_id,
            status="FAILED",
            error_message=str(exc)[:1000],
            stage_message="Kalkulasi SPI gagal.",
            finished_at=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        )
    finally:
        _ACTIVE_CANCEL_FLAGS.pop(job_id, None)


def submit_spi_generation_job(
    resolution: str,
    timescale: int,
    selected_stations: Optional[List[str]] = None,
    output_start_date: Optional[str] = None,
    output_end_date: Optional[str] = None,
    n_workers: int = 4,
    operator: str = "OPERATOR_BMKG",
    run_sync: bool = False,
) -> Dict[str, Any]:
    """
    Creates a persistent QUEUED job in MariaDB (or returns existing active duplicate job),
    starts the background worker thread, and immediately returns job metadata.
    """
    ensure_spi_jobs_table()
    recover_stale_spi_jobs()

    res_key = resolution.strip().upper()
    if res_key not in RESOLUTION_CONFIG:
        raise ValueError(f"Resolusi '{resolution}' tidak didukung.")
    ts = int(timescale)
    if ts not in RESOLUTION_CONFIG[res_key]["supported_timescales"]:
        raise ValueError(f"Timescale {ts} tidak didukung untuk resolusi {res_key}.")

    job_key = _build_job_key(res_key, ts, selected_stations, output_start_date, output_end_date)

    with _JOB_SUBMIT_LOCK:
        # Deduplicate identical concurrent active job
        with get_db() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT job_id, status, progress_pct, completed_stations, total_stations, stage_message
                    FROM cews_spi_generation_jobs
                    WHERE job_key = %s AND status IN ('QUEUED', 'RUNNING')
                    ORDER BY created_at DESC LIMIT 1
                    """,
                    (job_key,),
                )
                existing = cur.fetchone()
                if existing:
                    return {
                        "job_id": existing["job_id"],
                        "status": existing["status"],
                        "deduplicated": True,
                        "progress_pct": float(existing["progress_pct"] or 0),
                        "completed_stations": int(existing["completed_stations"] or 0),
                        "total_stations": int(existing["total_stations"] or 0),
                        "stage_message": existing.get("stage_message") or "Job identik sedang berjalan.",
                    }

                job_id = f"SPIJOB_{res_key}_{ts}D_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:6].upper()}"
                params = {
                    "resolution": res_key,
                    "timescale": ts,
                    "selected_stations": selected_stations,
                    "output_start_date": output_start_date,
                    "output_end_date": output_end_date,
                    "n_workers": n_workers,
                }
                now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                cur.execute(
                    """
                    INSERT INTO cews_spi_generation_jobs
                    (job_id, job_key, status, resolution, timescale, request_params_json,
                     stage_message, operator, heartbeat_at)
                    VALUES (%s, %s, 'QUEUED', %s, %s, %s, 'Menunggu eksekusi worker...', %s, %s)
                    """,
                    (job_id, job_key, res_key, ts, json.dumps(params), operator, now_str),
                )
            conn.commit()

    _ACTIVE_CANCEL_FLAGS[job_id] = threading.Event()
    if run_sync:
        _run_spi_job_worker(job_id, params)
    else:
        t = threading.Thread(target=_run_spi_job_worker, args=(job_id, params), daemon=True, name=f"spi-job-{job_id}")
        t.start()

    return {
        "job_id": job_id,
        "status": "QUEUED" if not run_sync else get_spi_job_status(job_id)["status"],
        "deduplicated": False,
        "progress_pct": 0.0,
        "completed_stations": 0,
        "total_stations": 0,
        "stage_message": "Job SPI terdaftar dan mulai diproses di latar belakang.",
    }


def get_spi_job_status(job_id: str) -> Dict[str, Any]:
    ensure_spi_jobs_table()
    recover_stale_spi_jobs()
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM cews_spi_generation_jobs WHERE job_id = %s", (job_id,))
            row = cur.fetchone()
    if not row:
        raise ValueError(f"Job SPI '{job_id}' tidak ditemukan.")

    out: Dict[str, Any] = {
        "job_id": row["job_id"],
        "status": row["status"],
        "resolution": row["resolution"],
        "timescale": int(row["timescale"]),
        "total_stations": int(row["total_stations"] or 0),
        "completed_stations": int(row["completed_stations"] or 0),
        "success_count": int(row["success_count"] or 0),
        "error_count": int(row["error_count"] or 0),
        "progress_pct": float(row["progress_pct"] or 0),
        "current_station": row.get("current_station"),
        "stage_message": row.get("stage_message") or "",
        "session_token": row.get("session_token"),
        "error_message": row.get("error_message"),
        "operator": row.get("operator"),
        "attempt_count": int(row.get("attempt_count") or 1),
        "created_at": str(row.get("created_at") or ""),
        "started_at": str(row.get("started_at") or ""),
        "finished_at": str(row.get("finished_at") or ""),
    }
    if row["status"] == "SUCCEEDED":
        out["summary"] = json.loads(row["result_summary_json"] or "{}")
        out["results_detail"] = json.loads(row["results_detail_json"] or "[]")
        out["sample_preview"] = json.loads(row["sample_preview_json"] or "{}")
    return out


def list_spi_jobs(limit: int = 20) -> List[Dict[str, Any]]:
    ensure_spi_jobs_table()
    recover_stale_spi_jobs()
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT job_id, status, resolution, timescale, total_stations, completed_stations,
                       success_count, error_count, progress_pct, stage_message, session_token,
                       error_message, operator, attempt_count, created_at, finished_at
                FROM cews_spi_generation_jobs
                ORDER BY created_at DESC
                LIMIT %s
                """,
                (limit,),
            )
            rows = cur.fetchall()
    return [
        {
            "job_id": r["job_id"],
            "status": r["status"],
            "resolution": r["resolution"],
            "timescale": int(r["timescale"]),
            "total_stations": int(r["total_stations"] or 0),
            "completed_stations": int(r["completed_stations"] or 0),
            "success_count": int(r["success_count"] or 0),
            "error_count": int(r["error_count"] or 0),
            "progress_pct": float(r["progress_pct"] or 0),
            "stage_message": r.get("stage_message") or "",
            "session_token": r.get("session_token"),
            "error_message": r.get("error_message"),
            "operator": r.get("operator"),
            "created_at": str(r.get("created_at") or ""),
            "finished_at": str(r.get("finished_at") or ""),
        }
        for r in rows
    ]


def cancel_spi_job(job_id: str) -> Dict[str, Any]:
    ensure_spi_jobs_table()
    ev = _ACTIVE_CANCEL_FLAGS.get(job_id)
    if ev:
        ev.set()
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT status FROM cews_spi_generation_jobs WHERE job_id = %s", (job_id,))
            row = cur.fetchone()
            if not row:
                raise ValueError(f"Job SPI '{job_id}' tidak ditemukan.")
            if row["status"] in ("SUCCEEDED", "FAILED", "CANCELLED"):
                return {"job_id": job_id, "status": row["status"], "message": f"Job sudah berstatus {row['status']}."}
            cur.execute(
                """
                UPDATE cews_spi_generation_jobs
                SET status = 'CANCELLED', stage_message = 'Dibatalkan oleh operator.', finished_at = CURRENT_TIMESTAMP
                WHERE job_id = %s
                """,
                (job_id,),
            )
        conn.commit()
    return {"job_id": job_id, "status": "CANCELLED", "message": "Job SPI berhasil dibatalkan."}


def retry_spi_job(job_id: str, operator: str = "OPERATOR_BMKG") -> Dict[str, Any]:
    ensure_spi_jobs_table()
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM cews_spi_generation_jobs WHERE job_id = %s", (job_id,))
            row = cur.fetchone()
    if not row:
        raise ValueError(f"Job SPI '{job_id}' tidak ditemukan.")
    if row["status"] not in ("FAILED", "CANCELLED"):
        raise ValueError(f"Hanya job FAILED atau CANCELLED yang dapat diulang (status saat ini: {row['status']}).")

    params = json.loads(row["request_params_json"] or "{}")
    return submit_spi_generation_job(
        resolution=params.get("resolution", row["resolution"]),
        timescale=int(params.get("timescale", row["timescale"])),
        selected_stations=params.get("selected_stations"),
        output_start_date=params.get("output_start_date"),
        output_end_date=params.get("output_end_date"),
        n_workers=int(params.get("n_workers") or 4),
        operator=operator,
    )
