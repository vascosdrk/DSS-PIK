"""
CEWS BMKG Kepulauan Riau — Multi-Period REST API (v1.2)
Serving Historical 10-Dasarian Snapshots & Operational Warnings via MariaDB / JSON Cache
"""

import re
import os
import sys
import json
import threading
from datetime import datetime, date, timedelta
from typing import Optional, List, Dict, Any
from pathlib import Path

from fastapi import FastAPI, HTTPException, Query, status, Depends, Response, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, FileResponse

from backend.database import get_db, check_db_health
from backend.auth import (
    authenticate_user,
    create_session_token,
    decode_session_token,
    extract_token_from_request,
    get_current_user,
    SESSION_COOKIE_NAME,
    SESSION_DURATION_SECONDS,
)
from fastapi import UploadFile, File, Form
from backend.schemas import (
    OperationalSummaryResponse,
    SpiVoidRequest,
    SpiVoidResponse,
    ProbabilityVoidRequest,
    ProbabilityVoidResponse,
    LatestDataStatusResponse,
    IngestionBatchListResponse,
    BatchCancelRequest,
    BatchCancelResponse,
    RecordCorrectionRequest,
    RecordCorrectionResponse,
    RecordVoidRequest,
    RecordVoidResponse,
    ForecastVintagesResponse,
    ForecastVintageItem,
    StationSpiTrendResponse,
    IngestionPreviewResponse,
    IngestionCommitRequest,
    IngestionCommitResponse,
    IngestionHistoryResponse,
    HealthResponse,
    CurrentWarningResponse,
    CurrentWarningMeta,
    CurrentWarningItem,
    StationDetailResponse,
    ForecastEvidenceItem,
    WarningHistoryResponse,
    WarningHistoryItem,
    HthTableResponse,
    HthTableItem,
    HthTableMeta,
    StationEvaluationResponse,
    NearestStationItem,
    PeriodsResponse,
    PeriodItem,
    PeriodSummary,
    RainfallColumnItem,
    RainfallColumnsResponse,
    RainfallDailyRow,
    RainfallDailyTableMeta,
    RainfallDailyTableResponse,
    RainfallHistoryResponse,
    RainfallHistoryRecordItem,
    RainfallStationMasterItem,
    RainfallStationsResponse,
    RainfallInputEntry,
    RainfallInputPreviewItem,
    RainfallInputPreviewRequest,
    RainfallInputPreviewResponse,
    RainfallInputCommitRequest,
    RainfallInputCommitResponse,
    LoginRequest,
    LoginResponse,
    UserMeResponse,
    LogoutResponse,
    StationDetailedInfoResponse,
    SpiTableResponse,
    ProbabilityTableResponse,
    MapGenerateRequest,
    MapGenerateResponse,
    MapJsonExportRequest,
    MapJsonExportResponse,
    PeriodReadinessResponse,
    PeriodSelectRequest,
    RegionalWarningDecisionRequest,
    RegionalBulkInitRequest,
    SIH3PublicationPreviewRequest,
    SIH3ValidatePayloadRequest,
    SIH3WorkflowActionRequest,
)
from backend.evaluation import get_last_rain_date, get_hth_category, evaluate_station, get_station_rainfall_history, haversine_km
from backend.data_service import (
    get_station_detailed_info,
    get_spi_data,
    export_spi_data,
    get_probability_data,
    export_probability_data,
    export_rainfall_data,
)
from config.paths import PATH_STATION_METADATA, PATH_SPI_AUTHORITATIVE, PATH_SPI_PARQUET_DASARIAN_90D
from backend.decision_engine import evaluate_pdkm_full, evaluate_pdcht_full, arbitrate_final_synthesis, STATUS_TO_LEVEL
from backend.map_generator import generate_official_warning_map, list_generated_maps, OUTPUT_DIR as MAPS_OUTPUT_DIR
from backend.period_service import (
    get_period_readiness_analysis,
    get_active_period,
    get_10_dasarian_window_items,
    set_period_config,
    generate_dynamic_snapshot_for_period,
    get_current_server_time_wib,
)
import pandas as pd
import numpy as np

ARG_STATION_IDS = {'21010603B', '21010802B', '21020402B', '21040101B', '21710501B'}
DEFAULT_PERIOD_ID = "2026-09-das2"

ROOT_DIR = Path(__file__).resolve().parent.parent
SNAPSHOTS_DIR = ROOT_DIR / "data" / "processed" / "evaluation" / "snapshots"
MANIFEST_PATH = SNAPSHOTS_DIR / "periods_manifest.json"

_PERIODS_MANIFEST: Optional[List[Dict[str, Any]]] = None
_SNAPSHOTS_CACHE: Dict[str, Dict[str, Any]] = {}
_STATIONS_META_CACHE: Dict[str, Dict[str, Any]] = {}
_SPI_PARQUET_DF: Optional[pd.DataFrame] = None
_SPI_90D_PARQUET_DF: Optional[pd.DataFrame] = None
_CACHE_LOCK = threading.RLock()
_REGIONAL_WRITE_LOCK = threading.Lock()


def get_operational_spi_parquet_df() -> pd.DataFrame:
    global _SPI_PARQUET_DF
    with _CACHE_LOCK:
        if _SPI_PARQUET_DF is None:
            df = pd.read_parquet(PATH_SPI_AUTHORITATIVE)
            df.index = pd.to_datetime(df.index).strftime("%Y-%m-%d")
            _SPI_PARQUET_DF = df
        return _SPI_PARQUET_DF


def get_operational_spi_90d_parquet_df() -> pd.DataFrame:
    global _SPI_90D_PARQUET_DF
    with _CACHE_LOCK:
        if _SPI_90D_PARQUET_DF is None:
            df = pd.read_parquet(PATH_SPI_PARQUET_DASARIAN_90D)
            df.index = pd.to_datetime(df.index).strftime("%Y-%m-%d")
            _SPI_90D_PARQUET_DF = df
        return _SPI_90D_PARQUET_DF


def get_spi_target_date_for_period(period_id: str) -> Optional[str]:
    """
    Mandated Temporal Mapping:
    - Target Dasarian I suatu bulan -> SPI Dasarian III bulan sebelumnya (YYYY-PrevMo-21)
    - Target Dasarian II -> SPI Dasarian I bulan yang sama (YYYY-MM-01)
    - Target Dasarian III -> SPI Dasarian II bulan yang sama (YYYY-MM-11)
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
                prev_year = year - 1
                prev_month = 12
            else:
                prev_year = year
                prev_month = month - 1
            return f"{prev_year:04d}-{prev_month:02d}-21"
    except Exception:
        return None
    return None


def enrich_snapshot_with_parquet_spi(snap: Dict[str, Any]) -> Dict[str, Any]:
    """
    Enriches in-memory snapshot with active operational SPI 30D and 90D Parquet data
    using the mandated temporal mapping.
    Maintains 5 ARG stations strictly as null / None (no zero-fill).
    SPI 30D serves as the authoritative input to the Decision Engine (PDKM).
    SPI 90D is an informative companion indicator.
    """
    pid = snap.get("period_id", "")
    target_date = get_spi_target_date_for_period(pid)
    if not target_date:
        return snap

    spi_df = get_operational_spi_parquet_df()
    spi90_df = get_operational_spi_90d_parquet_df()

    has_date = target_date in spi_df.index
    spi_row = spi_df.loc[target_date] if has_date else None
    actual_spi30_date = target_date if has_date else None
    if not has_date and not spi_df.empty:
        prior_dates = [d for d in spi_df.index if d <= target_date]
        if prior_dates:
            best_d = max(prior_dates)
            spi_row = spi_df.loc[best_d]
            actual_spi30_date = best_d

    has_date_90 = target_date in spi90_df.index
    spi90_row = spi90_df.loc[target_date] if has_date_90 else None
    actual_spi90_date = target_date if has_date_90 else None
    if not has_date_90 and not spi90_df.empty:
        prior_dates_90 = [d for d in spi90_df.index if d <= target_date]
        if prior_dates_90:
            best_d_90 = max(prior_dates_90)
            spi90_row = spi90_df.loc[best_d_90]
            actual_spi90_date = best_d_90

    summary_counts = {
        "TOTAL": len(snap.get("items", [])),
        "NORMAL": 0,
        "WASPADA": 0,
        "SIAGA": 0,
        "AWAS": 0,
        "INCOMPLETE": 0
    }

    is_unverified_date = target_date in ("2026-09-21", "2026-10-01")

    for it in snap.get("items", []):
        sid = str(it["station_id"]).strip().upper()
        is_arg = bool(it.get("is_arg", False) or sid in ARG_STATION_IDS)
        it["is_arg"] = is_arg

        if is_arg:
            it["spi_value"] = None
            it["spi_value_90d"] = None
            it["spi_condition"] = "NORMAL"
            it["spi_condition_90d"] = "NORMAL"
            it["spi_evidence_date"] = target_date
            it["spi_validation_status"] = "TIDAK_TERSEDIA_ARG"
            it["spi_validation_status_90d"] = "TIDAK_TERSEDIA_ARG"
            it["spi_source"] = "data/raw/spi/dasarian/SPI_all_30d.parquet (tidak tersedia / ARG)"
            it["spi_source_90d"] = "data/raw/spi/dasarian/SPI_all_90d.parquet (tidak tersedia / ARG)"
            # ARG evaluation based on HTH per system policy
            target_label = snap.get("label", pid)
            d_res = evaluate_pdkm_full(
                hth_days=it.get("hth_days"),
                pb20=None,
                spi_val=None,
                hth_uncertain=bool(it.get("hth_uncertain", False)),
                is_arg=True,
                target_label=target_label
            )
            it["pdkm_level"] = d_res["status"]
            it["pdcht_level"] = "NORMAL"
            it["hazard_type"] = "DROUGHT" if d_res["level"] > 0 else "NORMAL"
            it["warning_level"] = d_res["status"]
            it["warning_reasons"] = d_res["reasons"]
            it["narrative"] = d_res["reasons"]
            it["evaluation_complete"] = d_res["evaluation_complete"]
            it["evaluation_status"] = "COMPLETE" if d_res["evaluation_complete"] else "INCOMPLETE"

            lvl = it.get("warning_level", "NORMAL").upper()
            if it.get("evaluation_status") == "INCOMPLETE":
                summary_counts["INCOMPLETE"] += 1
            elif lvl in summary_counts:
                summary_counts[lvl] += 1
            else:
                summary_counts["NORMAL"] += 1
            continue

        # Pos Hujan Manual (52 stations)
        s_val = None
        if spi_row is not None and sid in spi_row.index:
            raw_v = spi_row[sid]
            if pd.notna(raw_v):
                s_val = float(raw_v)

        s_val_90 = None
        if spi90_row is not None and sid in spi90_row.index:
            raw_v_90 = spi90_row[sid]
            if pd.notna(raw_v_90):
                s_val_90 = float(raw_v_90)

        it["spi_value"] = s_val
        it["spi_value_90d"] = s_val_90
        it["spi_condition"] = "DRY" if (s_val is not None and s_val <= -1.0) else "NORMAL"
        it["spi_condition_90d"] = "DRY" if (s_val_90 is not None and s_val_90 <= -1.0) else "NORMAL"
        it["spi_evidence_date"] = actual_spi30_date or target_date
        it["spi_evidence_date_90d"] = actual_spi90_date or target_date
        it["spi_source"] = "data/raw/spi/dasarian/SPI_all_30d.parquet"
        it["spi_source_90d"] = "data/raw/spi/dasarian/SPI_all_90d.parquet"

        status_30 = "NOT_VERIFIED" if is_unverified_date else ("VERIFIED" if s_val is not None else "DATA_KOSONG")
        status_90 = "NOT_VERIFIED" if is_unverified_date else ("VERIFIED" if s_val_90 is not None else "DATA_KOSONG")
        it["spi_validation_status"] = status_30
        it["spi_validation_status_90d"] = status_90

        # Re-evaluate PDKM, PDCHT, and Final Status using Authoritative Decision Engine
        # SPI 90D is the authoritative drought indicator; SPI 30D is purely informational
        target_label = snap.get("label", pid)
        d_res = evaluate_pdkm_full(
            hth_days=it.get("hth_days"),
            pb20=it.get("forecast_pb20"),
            spi_val=s_val_90,
            hth_uncertain=bool(it.get("hth_uncertain", False)),
            is_arg=is_arg,
            target_label=target_label
        )
        r_res = evaluate_pdcht_full(
            pa150=it.get("forecast_pa150"),
            pa200=it.get("forecast_pa200"),
            pa300=it.get("forecast_pa300"),
            pm300=it.get("monthly_pa300"),
            pm400=it.get("monthly_pa400"),
            pm500=it.get("monthly_pa500"),
            is_arg=is_arg,
            target_label=target_label
        )
        synth = arbitrate_final_synthesis(d_res, r_res)

        if is_unverified_date and status_30 == "NOT_VERIFIED":
            it["data_quality_status"] = "UNCERTAIN"

        it["pdkm_status"] = d_res["status"]
        it["pdkm_level"] = d_res["level"]
        it["pdkm_reasons"] = d_res["reasons"]
        it["pdcht_status"] = r_res["status"]
        it["pdcht_level"] = r_res["level"]
        it["pdcht_reasons"] = r_res["reasons"]
        it["hazard_type"] = synth["hazard_type"]
        it["warning_level"] = synth["final_status"]
        it["warning_reasons"] = synth["reason"]
        it["narrative"] = synth["reason"]
        it["evaluation_complete"] = synth["evaluation_complete"]
        it["updated_at"] = format_wib_iso(get_current_server_time_wib())
        if synth["evaluation_complete"]:
            it["evaluation_status"] = "COMPLETE"
        elif synth["final_level"] > 0:
            it["evaluation_status"] = "PARTIAL"
        else:
            it["evaluation_status"] = "INCOMPLETE"

        lvl_up = synth["final_status"].upper()
        if lvl_up in summary_counts:
            summary_counts[lvl_up] += 1
        else:
            summary_counts["NORMAL"] += 1

    snap["summary"] = summary_counts
    snap["spi_source"] = "data/raw/spi/dasarian/SPI_all_30d.parquet"
    snap["spi_source_90d"] = "data/raw/spi/dasarian/SPI_all_90d.parquet"
    snap["spi_evidence_date"] = target_date
    return snap


def get_periods_manifest() -> List[Dict[str, Any]]:
    global _PERIODS_MANIFEST
    if _PERIODS_MANIFEST is None:
        if MANIFEST_PATH.exists():
            try:
                with open(MANIFEST_PATH, "r", encoding="utf-8") as f:
                    _PERIODS_MANIFEST = json.load(f)
            except Exception as e:
                print(f"[Warning] Failed to load periods_manifest.json: {e}")
                _PERIODS_MANIFEST = []
        else:
            _PERIODS_MANIFEST = []
    return _PERIODS_MANIFEST


def get_period_snapshot(period_id: Optional[str] = None) -> Dict[str, Any]:
    global _SNAPSHOTS_CACHE
    if not period_id or not isinstance(period_id, str):
        active_info = get_active_period()
        pid = active_info["period_id"]
    else:
        pid = period_id.strip()

    if pid in _SNAPSHOTS_CACHE:
        return _SNAPSHOTS_CACHE[pid]

    target_file = SNAPSHOTS_DIR / f"{pid}.json"
    if target_file.exists():
        try:
            with open(target_file, "r", encoding="utf-8") as f:
                snap = json.load(f)
                enriched = enrich_snapshot_with_parquet_spi(snap)
                _SNAPSHOTS_CACHE[pid] = enriched
                return enriched
        except Exception as e:
            print(f"[Error] Failed to read snapshot {target_file}: {e}")

    # Honest dynamic evaluation for unsnapshotted period (no fake data copying)
    try:
        snap = generate_dynamic_snapshot_for_period(pid)
        enriched = enrich_snapshot_with_parquet_spi(snap)
        _SNAPSHOTS_CACHE[pid] = enriched
        return enriched
    except Exception as e:
        print(f"[Error] Failed to generate dynamic snapshot for {pid}: {e}")

    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail=f"Evaluation snapshot for period '{pid}' not found."
    )


def get_station_meta_dict() -> Dict[str, Dict[str, Any]]:
    global _STATIONS_META_CACHE
    if not _STATIONS_META_CACHE:
        try:
            with get_db() as conn:
                with conn.cursor() as cur:
                    cur.execute("""
                        SELECT station_id, station_name, kabupaten, province, region,
                               latitude, longitude, elevation_m, nozom_prov
                        FROM stations
                    """)
                    for row in cur.fetchall():
                        sid = str(row["station_id"]).strip().upper()
                        _STATIONS_META_CACHE[sid] = row
        except Exception as e:
            print(f"[Warning] Failed to load stations metadata from DB: {e}")
    return _STATIONS_META_CACHE


CEWS_ENV = os.environ.get("CEWS_ENV", "development").strip().lower()
IS_PRODUCTION = CEWS_ENV == "production"
ENABLE_DOCS = os.environ.get("CEWS_ENABLE_DOCS", "false" if IS_PRODUCTION else "true").strip().lower() == "true"
COOKIE_SECURE = os.environ.get("CEWS_COOKIE_SECURE", "true" if IS_PRODUCTION else "false").strip().lower() == "true"
SERVE_FRONTEND = os.environ.get("CEWS_SERVE_FRONTEND", "true" if IS_PRODUCTION else "false").strip().lower() == "true"

from backend.config import INSTITUTION_NAME

app = FastAPI(
    title="Climate Early Warning System (CEWS) API",
    description=f"Operational and Multi-Period Historical REST API for {INSTITUTION_NAME} Climate Early Warning System.",
    version="1.2.0",
    docs_url="/docs" if ENABLE_DOCS else None,
    redoc_url="/redoc" if ENABLE_DOCS else None,
    openapi_url="/openapi.json" if ENABLE_DOCS else None,
)

# ==============================================================================
# CORS MIDDLEWARE (Environment Allowlist in Production + Localhost/LAN in Dev)
# ==============================================================================
_env_cors = os.environ.get("CEWS_CORS_ORIGINS", "").strip()
if _env_cors:
    ALLOWED_ORIGINS = [o.strip().rstrip("/") for o in _env_cors.split(",") if o.strip() and o.strip() != "*"]
else:
    ALLOWED_ORIGINS = [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:8000",
        "http://127.0.0.1:8000",
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ]

LAN_ORIGIN_REGEX = (
    None
    if _env_cors
    else r"^https?://(localhost|127\.0\.0\.1|192\.168\.\d+\.\d+|10\.\d+\.\d+\.\d+|172\.(1[6-9]|2\d|3[01])\.\d+\.\d+)(:\d+)?$"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_origin_regex=LAN_ORIGIN_REGEX,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ==============================================================================
# LAN ACCESS GUARD MIDDLEWARE (PHASE 7.3.1 DEFENSE-IN-DEPTH)
# ==============================================================================
from backend.lan_firewall_service import is_client_ip_allowed

@app.middleware("http")
async def lan_access_guard_middleware(request: Request, call_next):
    client_host = request.client.host if request.client else ""
    x_real_ip = request.headers.get("x-real-ip") if hasattr(request, "headers") else None
    allowed, reason = is_client_ip_allowed(client_host, forwarded_real_ip=x_real_ip)
    if not allowed:
        return JSONResponse(
            status_code=status.HTTP_403_FORBIDDEN,
            content={"detail": reason},
        )
    return await call_next(request)


# ==============================================================================
# AUTHENTICATION GUARD MIDDLEWARE
# ==============================================================================
@app.middleware("http")
async def authentication_guard_middleware(request: Request, call_next):
    # Always allow CORS preflight requests
    if request.method == "OPTIONS":
        return await call_next(request)

    path = request.url.path

    # Public paths that do not require an active session
    public_paths = {
        "/health",
        "/api/v1/auth/login",
        "/api/v1/publications/sih3/latest.json",
    }
    if ENABLE_DOCS:
        public_paths.update({"/docs", "/redoc", "/openapi.json"})

    # If public, map download, geo layers, or outside API namespace, allow without auth
    if path in public_paths or path.startswith("/api/v1/maps/download/") or path.startswith("/api/v1/geo/layers/") or not path.startswith("/api/v1/"):
        return await call_next(request)

    def _create_401_response(detail: str) -> JSONResponse:
        origin = request.headers.get("origin")
        resp_headers = {"WWW-Authenticate": "Bearer"}
        if origin and (origin in ALLOWED_ORIGINS or (LAN_ORIGIN_REGEX and re.match(LAN_ORIGIN_REGEX, origin))):
            resp_headers["Access-Control-Allow-Origin"] = origin
            resp_headers["Access-Control-Allow-Credentials"] = "true"
            resp_headers["Access-Control-Allow-Headers"] = "*"
            resp_headers["Access-Control-Allow-Methods"] = "*"
        return JSONResponse(
            status_code=status.HTTP_401_UNAUTHORIZED,
            content={"detail": detail},
            headers=resp_headers
        )

    # For all protected /api/v1/* routes, verify session
    token = extract_token_from_request(request)
    if not token:
        return _create_401_response("Autentikasi diperlukan. Sesi tidak ditemukan atau belum login.")

    user_payload = decode_session_token(token)
    if not user_payload:
        return _create_401_response("Sesi tidak valid atau telah kedaluwarsa. Silakan login kembali.")

    request.state.user = user_payload
    return await call_next(request)



def format_wib_iso(dt_val: Optional[datetime]) -> str:
    """
    Convert UTC database DATETIME to WIB ISO 8601 string (+07:00).
    """
    if not dt_val:
        return ""
    if isinstance(dt_val, str):
        return dt_val
    dt_wib = dt_val + timedelta(hours=7)
    return dt_wib.strftime("%Y-%m-%dT%H:%M:%S+07:00")


def format_date_str(d_val: Any) -> str:
    if not d_val:
        return ""
    if isinstance(d_val, (date, datetime)):
        return d_val.strftime("%Y-%m-%d")
    return str(d_val)


# ==============================================================================
# 1. HEALTH CHECK ENDPOINT
# ==============================================================================
@app.get("/health", response_model=HealthResponse, tags=["System Health"])
def health_check():
    db_ok = check_db_health()
    if not db_ok:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Database connectivity failed."
        )
    return HealthResponse(
        status="ok",
        service="cews-api",
        database="connected"
    )


# ==============================================================================
# 1B. AUTHENTICATION ENDPOINTS (TAHAP 3)
# ==============================================================================
@app.post(
    "/api/v1/auth/login",
    response_model=LoginResponse,
    tags=["Authentication"],
    summary="Login operator with username and password",
    description="Validates operator credentials against secure hashed configuration and sets signed HttpOnly session cookie.",
)
def login(payload: LoginRequest, response: Response):
    if not authenticate_user(payload.username, payload.password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Username atau kata sandi tidak valid.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    clean_user = payload.username.strip()
    token = create_session_token(clean_user)
    response.set_cookie(
        key=SESSION_COOKIE_NAME,
        value=token,
        max_age=SESSION_DURATION_SECONDS,
        httponly=True,
        samesite="lax",
        secure=COOKIE_SECURE,
        path="/",
    )
    return LoginResponse(
        success=True,
        username=clean_user,
        role="OPERATOR_CEWS",
        token=token,
        message="Login berhasil. Sesi telah diaktifkan."
    )


@app.post(
    "/api/v1/auth/logout",
    response_model=LogoutResponse,
    tags=["Authentication"],
    summary="Logout and terminate active session",
    description="Clears signed session cookie from client.",
)
def logout(response: Response):
    response.delete_cookie(
        key=SESSION_COOKIE_NAME,
        path="/",
        httponly=True,
        samesite="lax",
    )
    return LogoutResponse(
        success=True,
        message="Sesi berhasil diakhiri."
    )


@app.get(
    "/api/v1/auth/me",
    response_model=UserMeResponse,
    tags=["Authentication"],
    summary="Check current operator session state",
    description="Returns current operator identity if authenticated, otherwise returns HTTP 401.",
)
def get_me(request: Request, current_user: dict = Depends(get_current_user)):
    token = extract_token_from_request(request)
    return UserMeResponse(
        authenticated=True,
        username=current_user["username"],
        role="OPERATOR_CEWS",
        token=token,
        message="Sesi aktif dan valid."
    )



# ==============================================================================
# 2. PERIODS ENDPOINT (10-DASARIAN WINDOW)
# ==============================================================================
@app.get(
    "/api/v1/periods",
    response_model=PeriodsResponse,
    tags=["Operational Warnings"],
    summary="Get List of Available 10-Dasarian Evaluation Periods",
    description="Returns the rolling 10-dasarian evaluation window up to the current operational period."
)
def list_periods():
    act_pid, mode, periods_items = get_10_dasarian_window_items()
    act = get_active_period()
    items = []
    for p in periods_items:
        items.append(PeriodItem(
            period_id=p["period_id"],
            label=p["label"],
            date_range=p["date_range"],
            target_start=p["target_start"],
            target_end=p["target_end"],
            observation_cutoff=p["observation_cutoff"],
            forecast_issue=p["forecast_issue"],
            prev_dasarian_label=p.get("prev_dasarian_label", "CH Dasarian Sebelumnya (mm)"),
            is_default=bool(p.get("is_default", False)),
            is_forecast=bool(p.get("is_forecast", False)),
            has_complete_data=bool(p.get("has_complete_data", True)),
            has_snapshot=bool(p.get("has_snapshot", True)),
            summary=PeriodSummary(**p["summary"]),
        ))
    return PeriodsResponse(
        active_period_id=act["period_id"],
        mode=act["mode"],
        server_time=act["server_time"],
        server_date=act["server_date"],
        total_periods=len(items),
        periods=items,
    )


@app.post(
    "/api/v1/periods/select",
    response_model=PeriodsResponse,
    tags=["Operational Warnings"],
    summary="Select Active Evaluation Period (Auto / Manual)",
    description="Switches between Real-Time Automatic mode and Manual Officer selection. Persists server-side."
)
def select_period_endpoint(payload: PeriodSelectRequest, request: Request):
    global _SNAPSHOTS_CACHE
    operator_name = "operator"
    # Attempt to read authenticated username from token if present
    auth_header = request.headers.get("Authorization")
    cookie_token = request.cookies.get(SESSION_COOKIE_NAME)
    token = None
    if auth_header and auth_header.startswith("Bearer "):
        token = auth_header[7:].strip()
    elif cookie_token:
        token = cookie_token.strip()
    if token:
        sess = decode_session_token(token)
        if sess and "sub" in sess:
            operator_name = sess["sub"]

    set_period_config(payload.mode, payload.period_id, operator_name)
    _SNAPSHOTS_CACHE.clear()

    return list_periods()


_REFRESH_EVALUATE_LOCK = threading.Lock()


@app.post(
    "/api/v1/warnings/refresh-evaluate",
    tags=["Operational Warnings"],
    summary="Segarkan & Evaluasi Ulang Seluruh Data Operasional & Decision Engine",
    description="Membersihkan cache in-memory, memuat ulang data observasi harian, SPI parquet, dan probabilitas ECMWF, mengevaluasi ulang Decision Engine secara deterministik tanpa restart server."
)
def refresh_and_evaluate_warnings(
    period_id: Optional[str] = Query(None, description="Periode evaluasi yang akan disegarkan, default ke periode aktif"),
    current_user: dict = Depends(get_current_user)
):
    if not _REFRESH_EVALUATE_LOCK.acquire(blocking=False):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Proses Segarkan & Evaluasi sedang berjalan oleh operator lain. Silakan tunggu beberapa detik."
        )
    try:
        global _SNAPSHOTS_CACHE, _PERIODS_MANIFEST, _SPI_PARQUET_DF, _SPI_90D_PARQUET_DF
        # 1. Clear all in-memory caches
        _SNAPSHOTS_CACHE.clear()
        _PERIODS_MANIFEST = None
        _SPI_PARQUET_DF = None
        _SPI_90D_PARQUET_DF = None

        # 2. Determine target period
        active_obj = get_active_period()
        target_pid = period_id or (active_obj.get("period_id") if isinstance(active_obj, dict) else str(active_obj))

        # 3. Regenerate dynamic snapshot and re-run Decision Engine
        snap = get_period_snapshot(target_pid)
        items = snap.get("items", [])
        
        valid_spi30 = sum(1 for it in items if it.get("spi_value") is not None)
        valid_spi90 = sum(1 for it in items if it.get("spi_value_90d") is not None)
        valid_hth = sum(1 for it in items if it.get("hth_days") is not None)
        
        summary = snap.get("summary", {})
        
        return {
            "success": True,
            "message": f"Data operasional dan Decision Engine periode {target_pid} berhasil disegarkan dan dievaluasi ulang.",
            "period_id": target_pid,
            "period_label": snap.get("label"),
            "evaluated_at": format_wib_iso(get_current_server_time_wib()),
            "stations_total": len(items),
            "stats": {
                "valid_hth": valid_hth,
                "valid_spi_30d": valid_spi30,
                "valid_spi_90d": valid_spi90,
                "active_awas": summary.get("AWAS", 0),
                "active_siaga": summary.get("SIAGA", 0),
                "active_waspada": summary.get("WASPADA", 0),
                "normal": summary.get("NORMAL", 0),
                "incomplete": summary.get("INCOMPLETE", 0)
            }
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Gagal melakukan evaluasi ulang data operasional: {e}"
        )
    finally:
        _REFRESH_EVALUATE_LOCK.release()


@app.get(
    "/api/v1/periods/readiness",
    response_model=PeriodReadinessResponse,
    tags=["Operational Warnings"],
    summary="Audit Data Availability and Candidate Period Readiness (Paket 1 & 2)",
    description="Analyzes real-time observation cutoff dates, data lag, SPI availability, forecast issue date, and station completeness."
)
def get_period_readiness_endpoint(period_id: Optional[str] = Query(None, description="Candidate Period ID to audit")):
    try:
        data = get_period_readiness_analysis(period_id)
        return PeriodReadinessResponse(**data)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Gagal melakukan audit kesiapan periode: {e}"
        )


# ==============================================================================
# 3. CURRENT WARNING MAP ENDPOINT (CONTRACT A)
# ==============================================================================
@app.get(
    "/api/v1/current-warning",
    response_model=CurrentWarningResponse,
    tags=["Operational Warnings"],
    summary="Get Active Current Warnings for Map View (Contract A)"
)
def get_current_warning_map(
    period_id: Optional[str] = Query(None, description="Evaluation Period ID e.g. 2026-09-das2"),
    kabupaten: Optional[str] = Query(None, description="Filter by Kabupaten / Kota"),
    warning_level: Optional[str] = Query(None, description="Filter by Warning Level: NORMAL, WASPADA, SIAGA, AWAS"),
    hazard_type: Optional[str] = Query(None, description="Filter by Hazard Type: NORMAL, DROUGHT, HEAVY_RAIN"),
):
    snap = get_period_snapshot(period_id)
    raw_items = snap.get("items", [])

    items = []
    for it in raw_items:
        if kabupaten and kabupaten.strip().upper() != "ALL":
            if it["kabupaten"].strip().upper() != kabupaten.strip().upper():
                continue
        if warning_level and warning_level.strip().upper() != "ALL":
            wl = warning_level.strip().upper()
            it_wl = it["warning_level"].strip().upper()
            if wl in ("NORMAL", "AMAN"):
                if it_wl not in ("NORMAL", "AMAN"):
                    continue
            else:
                if it_wl != wl:
                    continue
        if hazard_type and hazard_type.strip().upper() != "ALL":
            ht = hazard_type.strip().upper()
            it_ht = it["hazard_type"].strip().upper()
            if it_ht != ht:
                continue

        is_arg = bool(it.get("is_arg", False) or it["station_id"] in ARG_STATION_IDS)
        eval_status = str(it.get("evaluation_status", "COMPLETE" if is_arg else "INCOMPLETE"))

        items.append(CurrentWarningItem(
            station_id=it["station_id"],
            station_name=it["station_name"],
            kabupaten=it["kabupaten"],
            latitude=float(it["latitude"]),
            longitude=float(it["longitude"]),
            target_warning_period=it.get("target_warning_period") or it.get("period_label") or snap.get("label", ""),
            target_period_start=it.get("target_period_start") or it.get("target_start") or snap.get("target_start", ""),
            target_period_end=it.get("target_period_end") or it.get("target_end") or snap.get("target_end", ""),
            hazard_type=it["hazard_type"],
            warning_level=it["warning_level"],
            confidence_level=it.get("confidence_level", "HIGH"),
            data_quality_status=it.get("data_quality_status", "VALID"),
            updated_at=it.get("updated_at") or format_wib_iso(get_current_server_time_wib()),
            is_arg=is_arg,
            evaluation_status=eval_status,
            prev_dasarian_rainfall_mm=it.get("prev_dasarian_rainfall_mm"),
            prev_dasarian_label=it.get("prev_dasarian_label", snap.get("prev_dasarian_label")),
            spi_value=None if is_arg else (float(it["spi_value"]) if it.get("spi_value") is not None else None),
            spi_value_90d=None if is_arg else (float(it["spi_value_90d"]) if it.get("spi_value_90d") is not None else None),
            spi_evidence_date=it.get("spi_evidence_date") or snap.get("spi_evidence_date"),
            spi_validation_status=it.get("spi_validation_status"),
            spi_validation_status_90d=it.get("spi_validation_status_90d"),
        ))

    meta = CurrentWarningMeta(
        total=len(items),
        period_id=snap["period_id"],
        period_label=snap["label"],
        date_range=snap["date_range"],
        dataset_type="operational_simulation",
        observation_cutoff=snap["observation_cutoff"],
        forecast_issue=snap["forecast_issue"],
        target_period_start=snap["target_start"],
        target_period_end=snap["target_end"],
        prev_dasarian_label=snap.get("prev_dasarian_label"),
    )

    return CurrentWarningResponse(meta=meta, data=items)


# ==============================================================================
# 4. STATION DETAIL ENDPOINT (CONTRACT B & C)
# ==============================================================================
@app.get(
    "/api/v1/stations/{station_id}/detail",
    response_model=StationDetailResponse,
    tags=["Station Details"],
    summary="Get Complete Active Warning Detail for a Specific Station (Contract B & C)"
)
def get_station_detail(
    station_id: str,
    period_id: Optional[str] = Query(None, description="Evaluation Period ID e.g. 2026-09-das2"),
):
    sid = station_id.strip().upper()
    snap = get_period_snapshot(period_id)

    stn_item = None
    for it in snap.get("items", []):
        if it["station_id"].strip().upper() == sid:
            stn_item = it
            break

    if not stn_item:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Station with ID '{sid}' not found in period '{period_id}' evaluation snapshot."
        )

    meta_dict = get_station_meta_dict()
    stn_meta = meta_dict.get(sid, {})

    is_arg = bool(stn_item.get("is_arg", False) or sid in ARG_STATION_IDS)
    trigger_reason = stn_item.get("warning_reasons") or stn_item.get("narrative") or "Tidak ada kondisi peringatan dini terpenuhi."
    if is_arg:
        trigger_reason = (
            "Stasiun ARG. Evaluasi periode ini menggunakan data Hari Tanpa Hujan (HTH) yang tersedia. "
            "Data SPI dan probabilitas prakiraan tidak tersedia untuk stasiun ini, sehingga status peringatan lengkap belum dapat ditentukan."
        )

    parts = snap["period_id"].split("-")
    t_year = int(parts[0])
    t_month = int(parts[1])
    t_das = int(parts[2].replace("das", ""))

    evidence_items = []
    if not is_arg:
        if stn_item.get("forecast_pb20") is not None:
            evidence_items.append(ForecastEvidenceItem(
                forecast_parameter="prob_below20",
                probability_value=float(stn_item["forecast_pb20"]),
                issue_date=snap["forecast_issue"],
                source_file="ECMWF Dasarian Probability",
            ))
        if stn_item.get("forecast_pa150") is not None:
            evidence_items.append(ForecastEvidenceItem(
                forecast_parameter="prob_above150",
                probability_value=float(stn_item["forecast_pa150"]),
                issue_date=snap["forecast_issue"],
                source_file="ECMWF Dasarian Probability",
            ))
        if stn_item.get("forecast_pa200") is not None:
            evidence_items.append(ForecastEvidenceItem(
                forecast_parameter="prob_above200",
                probability_value=float(stn_item["forecast_pa200"]),
                issue_date=snap["forecast_issue"],
                source_file="ECMWF Dasarian Probability",
            ))
        if stn_item.get("forecast_pa300") is not None:
            evidence_items.append(ForecastEvidenceItem(
                forecast_parameter="prob_above300",
                probability_value=float(stn_item["forecast_pa300"]),
                issue_date=snap["forecast_issue"],
                source_file="ECMWF Dasarian Probability",
            ))
        if stn_item.get("monthly_pa300") is not None:
            evidence_items.append(ForecastEvidenceItem(
                forecast_parameter="prob_month_above300",
                probability_value=float(stn_item["monthly_pa300"]),
                issue_date=snap["forecast_issue"],
                source_file="ECMWF Monthly Probability",
            ))
        if stn_item.get("monthly_pa400") is not None:
            evidence_items.append(ForecastEvidenceItem(
                forecast_parameter="prob_month_above400",
                probability_value=float(stn_item["monthly_pa400"]),
                issue_date=snap["forecast_issue"],
                source_file="ECMWF Monthly Probability",
            ))
        if stn_item.get("monthly_pa500") is not None:
            evidence_items.append(ForecastEvidenceItem(
                forecast_parameter="prob_month_above500",
                probability_value=float(stn_item["monthly_pa500"]),
                issue_date=snap["forecast_issue"],
                source_file="ECMWF Monthly Probability",
            ))

    # Compute top 5 nearest stations from snapshot for spatial context
    cur_lat = float(stn_item["latitude"])
    cur_lon = float(stn_item["longitude"])
    candidates = []
    for other in snap.get("items", []):
        other_id = other["station_id"].strip().upper()
        if other_id == sid:
            continue
        try:
            o_lat = float(other["latitude"])
            o_lon = float(other["longitude"])
            dist = haversine_km(cur_lat, cur_lon, o_lat, o_lon)
            candidates.append((dist, other))
        except (ValueError, TypeError):
            continue

    candidates.sort(key=lambda x: x[0])
    nearest_items = []
    for dist, o in candidates[:5]:
        o_hth = int(o["hth_days"]) if o.get("hth_days") is not None else None
        o_sid = str(o["station_id"]).strip().upper()
        o_lr = o.get("last_rain_date") or get_last_rain_date(o_sid)
        nearest_items.append(NearestStationItem(
            station_id=o["station_id"],
            station_name=o["station_name"],
            kabupaten=o.get("kabupaten", ""),
            distance_km=round(dist, 2),
            hth_days_current=o_hth,
            warning_level=o.get("warning_level", "NORMAL"),
            data_quality_status=o.get("data_quality_status", "VALID"),
            last_rain_date=o_lr,
        ))

    # Compute SPI Harian (Cutoff Date) and SPI Bulanan (Previous Completed Month)
    cutoff_date = snap.get("observation_cutoff")
    v_daily_30d = None
    v_daily_90d = None
    daily_condition = None
    if not is_arg and cutoff_date:
        try:
            from backend.data_service import get_cached_spi_df
            df_h30 = get_cached_spi_df("HARIAN", "30D")
            df_h90 = get_cached_spi_df("HARIAN", "90D")
            if cutoff_date in df_h30.index and sid in df_h30.columns:
                val = df_h30.loc[cutoff_date, sid]
                v_daily_30d = round(float(val), 2) if pd.notnull(val) else None
            if cutoff_date in df_h90.index and sid in df_h90.columns:
                val = df_h90.loc[cutoff_date, sid]
                v_daily_90d = round(float(val), 2) if pd.notnull(val) else None
            if v_daily_30d is not None:
                daily_condition = "DRY" if v_daily_30d <= -1.0 else "NORMAL"
        except Exception:
            pass

    m_year = t_year if t_month > 1 else t_year - 1
    m_month = t_month - 1 if t_month > 1 else 12
    monthly_date_ref = f"{m_year}-{m_month:02d}-01"
    months_id = {1: "Jan", 2: "Feb", 3: "Mar", 4: "Apr", 5: "Mei", 6: "Jun", 7: "Jul", 8: "Agu", 9: "Sep", 10: "Okt", 11: "Nov", 12: "Des"}
    monthly_label_ref = f"{months_id.get(m_month, str(m_month))} {m_year}"
    v_monthly = None
    monthly_condition = None
    if not is_arg:
        try:
            from backend.data_service import get_cached_spi_df
            df_mon = get_cached_spi_df("BULANAN", "30D")
            if monthly_date_ref in df_mon.index and sid in df_mon.columns:
                val = df_mon.loc[monthly_date_ref, sid]
                v_monthly = round(float(val), 2) if pd.notnull(val) else None
                if v_monthly is not None:
                    monthly_condition = "DRY" if v_monthly <= -1.0 else "NORMAL"
        except Exception:
            pass

    return StationDetailResponse(
        station_id=stn_item["station_id"],
        station_name=stn_item["station_name"],
        kabupaten=stn_item["kabupaten"],
        province=stn_meta.get("province", "Kepulauan Riau"),
        region=stn_meta.get("region", "KEPRI"),
        latitude=float(stn_item["latitude"]),
        longitude=float(stn_item["longitude"]),
        elevation_m=float(stn_meta["elevation_m"]) if stn_meta.get("elevation_m") is not None else None,
        nozom_prov=stn_meta.get("nozom_prov"),

        target_year=t_year,
        target_month=t_month,
        target_dasarian=t_das,
        target_warning_period=stn_item.get("target_warning_period") or stn_item.get("period_label") or snap.get("label", ""),
        target_period_start=stn_item.get("target_period_start") or stn_item.get("target_start") or snap.get("target_start", ""),
        target_period_end=stn_item.get("target_period_end") or stn_item.get("target_end") or snap.get("target_end", ""),

        hazard_type=stn_item["hazard_type"],
        warning_level=stn_item["warning_level"],
        pdkm_status=stn_item.get("pdkm_status", "NORMAL"),
        pdkm_level=stn_item.get("pdkm_level", 0),
        pdkm_reasons=stn_item.get("pdkm_reasons"),
        pdcht_status=stn_item.get("pdcht_status", "NORMAL"),
        pdcht_level=stn_item.get("pdcht_level", 0),
        pdcht_reasons=stn_item.get("pdcht_reasons"),
        trigger_reason=trigger_reason,
        confidence_level=stn_item.get("confidence_level", "HIGH"),
        data_quality_status=stn_item.get("data_quality_status", "VALID"),

        spi_condition="DRY" if (stn_item.get("spi_value") is not None and stn_item["spi_value"] <= -1.0) else "NORMAL",
        probability_support=False if is_arg else bool(
            (float(stn_item["forecast_pb20"]) > 70 if stn_item.get("forecast_pb20") is not None else False) or
            (float(stn_item["forecast_pa150"]) > 50 if stn_item.get("forecast_pa150") is not None else False)
        ),
        hth_days_current=int(stn_item["hth_days"]) if stn_item.get("hth_days") is not None else int(stn_item.get("hth_days_current") or 0),
        hth_uncertain=False,

        spi_value=None if is_arg else (float(stn_item["spi_value"]) if stn_item.get("spi_value") is not None else None),
        spi_value_90d=None if is_arg else (float(stn_item["spi_value_90d"]) if stn_item.get("spi_value_90d") is not None else None),
        spi_condition_90d="DRY" if (stn_item.get("spi_value_90d") is not None and stn_item["spi_value_90d"] <= -1.0) else "NORMAL",
        spi_evidence_date=stn_item.get("spi_evidence_date") or snap.get("spi_evidence_date"),
        spi_validation_status=stn_item.get("spi_validation_status"),
        spi_validation_status_90d=stn_item.get("spi_validation_status_90d"),
        spi_daily_30d=v_daily_30d,
        spi_daily_90d=v_daily_90d,
        spi_daily_evidence_date=cutoff_date,
        spi_daily_condition=daily_condition,
        spi_monthly_value=v_monthly,
        spi_monthly_evidence_month=monthly_label_ref,
        spi_monthly_condition=monthly_condition,
        prob_below20=None if is_arg else (float(stn_item["forecast_pb20"]) if stn_item.get("forecast_pb20") is not None else None),
        prob_ch_lt20_dasarian_1=None,
        prob_ch_lt20_dasarian_2=None,
        prob_above150=None if is_arg else (float(stn_item["forecast_pa150"]) if stn_item.get("forecast_pa150") is not None else None),
        prob_above200=None if is_arg else (float(stn_item["forecast_pa200"]) if stn_item.get("forecast_pa200") is not None else None),
        prob_above300=None if is_arg else (float(stn_item["forecast_pa300"]) if stn_item.get("forecast_pa300") is not None else None),
        prob_month_above300=None if is_arg else (float(stn_item["monthly_pa300"]) if stn_item.get("monthly_pa300") is not None else None),
        prob_month_above400=None if is_arg else (float(stn_item["monthly_pa400"]) if stn_item.get("monthly_pa400") is not None else None),
        prob_month_above500=None if is_arg else (float(stn_item["monthly_pa500"]) if stn_item.get("monthly_pa500") is not None else None),

        last_observation_period=f"Dasarian {t_das} {t_month:02d} {t_year}",
        last_observation_date=snap["observation_cutoff"],
        updated_at=stn_item.get("updated_at") or format_wib_iso(get_current_server_time_wib()),

        is_arg=is_arg,
        evaluation_status=stn_item["evaluation_status"],
        ch_dasarian_2_mm=stn_item.get("prev_dasarian_rainfall_mm"),
        prev_dasarian_rainfall_mm=stn_item.get("prev_dasarian_rainfall_mm"),
        prev_dasarian_label=stn_item.get("prev_dasarian_label", snap.get("prev_dasarian_label")),
        narrative=stn_item.get("narrative"),

        forecast_evidence=evidence_items,
        nearest_stations=nearest_items,
    )


# ==============================================================================
# 5. WARNING HISTORY TIMELINE ENDPOINT (CONTRACT D - READ-ONLY)
# ==============================================================================
@app.get(
    "/api/v1/stations/{station_id}/history",
    response_model=WarningHistoryResponse,
    tags=["Historical Ledger"],
    summary="Get Dasarian Historical Warning Ledger for a Station (Contract D)"
)
def get_station_history(station_id: str):
    sid = station_id.strip().upper()

    try:
        with get_db() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT station_name, kabupaten FROM stations WHERE station_id = %s", (sid,))
                stn = cur.fetchone()
                if not stn:
                    raise HTTPException(
                        status_code=status.HTTP_404_NOT_FOUND,
                        detail=f"Station with ID '{sid}' not found."
                    )

                sql_hist = """
                SELECT 
                    station_id, period_start, period_end, year, month, dasarian,
                    hazard_type, warning_level, trigger_reason, spi_condition,
                    probability_support, data_quality_status, confidence_level,
                    hth_days_max, hth_uncertain, spi_value, prob_below20,
                    prob_ch_lt20_dasarian_1, prob_ch_lt20_dasarian_2,
                    prob_above150, prob_above200, prob_above300,
                    prob_month_above300, prob_month_above400,
                    prob_month_above500, evaluated_at
                FROM cews_warning_history
                WHERE station_id = %s
                ORDER BY period_start DESC
                """
                cur.execute(sql_hist, (sid,))
                hist_rows = cur.fetchall()

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Database error while querying station history: {e}"
        )

    items = []
    for h in hist_rows:
        items.append(WarningHistoryItem(
            station_id=h["station_id"],
            period_start=format_date_str(h["period_start"]),
            period_end=format_date_str(h["period_end"]),
            year=int(h["year"]),
            month=int(h["month"]),
            dasarian=int(h["dasarian"]),
            hazard_type=h["hazard_type"],
            warning_level=h["warning_level"],
            trigger_reason=h["trigger_reason"],
            spi_condition=h["spi_condition"],
            probability_support=bool(h["probability_support"]),
            data_quality_status=h["data_quality_status"],
            confidence_level=h["confidence_level"],
            hth_days_max=int(h["hth_days_max"]),
            hth_uncertain=bool(h["hth_uncertain"]),
            spi_value=float(h["spi_value"]) if h["spi_value"] is not None else None,
            prob_below20=float(h["prob_below20"]) if h["prob_below20"] is not None else None,
            prob_ch_lt20_dasarian_1=float(h["prob_ch_lt20_dasarian_1"]) if h.get("prob_ch_lt20_dasarian_1") is not None else None,
            prob_ch_lt20_dasarian_2=float(h["prob_ch_lt20_dasarian_2"]) if h.get("prob_ch_lt20_dasarian_2") is not None else None,
            prob_above150=float(h["prob_above150"]) if h["prob_above150"] is not None else None,
            prob_above200=float(h["prob_above200"]) if h["prob_above200"] is not None else None,
            prob_above300=float(h["prob_above300"]) if h["prob_above300"] is not None else None,
            prob_month_above300=float(h["prob_month_above300"]) if h.get("prob_month_above300") is not None else None,
            prob_month_above400=float(h["prob_month_above400"]) if h["prob_month_above400"] is not None else None,
            prob_month_above500=float(h["prob_month_above500"]) if h["prob_month_above500"] is not None else None,
            evaluated_at=format_wib_iso(h["evaluated_at"]),
        ))

    return WarningHistoryResponse(
        station_id=sid,
        station_name=stn["station_name"],
        kabupaten=stn["kabupaten"],
        total_records=len(items),
        data=items
    )


# ==============================================================================
# 6. HTH TABLE ENDPOINT
# ==============================================================================
@app.get(
    "/api/v1/hth",
    response_model=HthTableResponse,
    tags=["HTH Monitoring"],
    summary="Retrieve HTH data for all 57 stations",
    description="Returns current HTH days, explicit HTH category (0-20 NORMAL, 21-30 WASPADA, 31-60 SIAGA, >60 AWAS), CEWS warning level, and last rain date.",
)
def get_hth_table(
    period_id: Optional[str] = Query(None, description="Evaluation Period ID e.g. 2026-09-das2"),
    kabupaten: Optional[str] = Query(None, description="Filter by Kabupaten"),
    warning_level: Optional[str] = Query(None, description="Filter by Warning Level"),
):
    snap = get_period_snapshot(period_id)
    raw_items = snap.get("items", [])

    items = []
    for it in raw_items:
        if kabupaten and kabupaten.strip().upper() != "ALL":
            if it["kabupaten"].strip().upper() != kabupaten.strip().upper():
                continue
        if warning_level and warning_level.strip().upper() != "ALL":
            wl = warning_level.strip().upper()
            it_wl = it["warning_level"].strip().upper()
            if wl in ("NORMAL", "AMAN"):
                if it_wl not in ("NORMAL", "AMAN"):
                    continue
            else:
                if it_wl != wl:
                    continue

        hth_val = it.get("hth_days")
        cat = get_hth_category(hth_val) if hth_val is not None else None
        is_arg = bool(it.get("is_arg", False) or it["station_id"] in ARG_STATION_IDS)
        eval_status = str(it.get("evaluation_status", "COMPLETE" if is_arg else "INCOMPLETE"))

        # SPI and probabilities: strictly None for ARG stations (scientific integrity)
        spi_val = float(it["spi_value"]) if (not is_arg and it.get("spi_value") is not None) else None
        spi_val_90 = float(it["spi_value_90d"]) if (not is_arg and it.get("spi_value_90d") is not None) else None
        pb20 = float(it["forecast_pb20"]) if (not is_arg and it.get("forecast_pb20") is not None) else None
        pa150 = float(it["forecast_pa150"]) if (not is_arg and it.get("forecast_pa150") is not None) else None
        pa200 = float(it["forecast_pa200"]) if (not is_arg and it.get("forecast_pa200") is not None) else None
        pa300 = float(it["forecast_pa300"]) if (not is_arg and it.get("forecast_pa300") is not None) else None
        m_pa300 = float(it["monthly_pa300"]) if (not is_arg and it.get("monthly_pa300") is not None) else None
        m_pa400 = float(it["monthly_pa400"]) if (not is_arg and it.get("monthly_pa400") is not None) else None
        m_pa500 = float(it["monthly_pa500"]) if (not is_arg and it.get("monthly_pa500") is not None) else None

        reason_text = it.get("warning_reasons") or it.get("trigger_reason")
        if not reason_text:
            if is_arg:
                reason_text = "Evaluasi berbasis HTH saja (ARG)"
            elif it["warning_level"].upper() in ("NORMAL", "AMAN"):
                reason_text = "Seluruh indikator dalam batas aman"
            else:
                reason_text = it["warning_level"]

        stn_type = "Stasiun ARG" if is_arg else "Pos Hujan Manual"

        items.append(HthTableItem(
            station_id=it["station_id"],
            station_name=it["station_name"],
            kabupaten=it["kabupaten"],
            latitude=float(it["latitude"]) if it.get("latitude") is not None else None,
            longitude=float(it["longitude"]) if it.get("longitude") is not None else None,
            hth_days_current=hth_val,
            hth_category=cat,
            hth_uncertain=False,
            data_quality_status=it.get("data_quality_status", "VALID"),
            confidence_level=it.get("confidence_level", "HIGH"),
            warning_level=it["warning_level"],
            hazard_type=it["hazard_type"],
            pdkm_status=it.get("pdkm_status") if it.get("pdkm_status") is not None else (it.get("pdkm_level") if isinstance(it.get("pdkm_level"), str) else "NORMAL"),
            pdkm_level=it.get("pdkm_level") if isinstance(it.get("pdkm_level"), int) else STATUS_TO_LEVEL.get(str(it.get("pdkm_level", "NORMAL")).upper(), 0),
            pdkm_reasons=it.get("pdkm_reasons"),
            pdcht_status=it.get("pdcht_status") if it.get("pdcht_status") is not None else (it.get("pdcht_level") if isinstance(it.get("pdcht_level"), str) else "NORMAL"),
            pdcht_level=it.get("pdcht_level") if isinstance(it.get("pdcht_level"), int) else STATUS_TO_LEVEL.get(str(it.get("pdcht_level", "NORMAL")).upper(), 0),
            pdcht_reasons=it.get("pdcht_reasons"),
            last_observation_date=snap["observation_cutoff"],
            last_rain_date=it.get("last_rain_date"),
            ch_dasarian_2_mm=it.get("prev_dasarian_rainfall_mm"),
            prev_dasarian_rainfall_mm=it.get("prev_dasarian_rainfall_mm"),
            prev_dasarian_label=it.get("prev_dasarian_label", snap.get("prev_dasarian_label")),
            is_arg=is_arg,
            evaluation_status=eval_status,
            station_type=stn_type,
            spi_value=spi_val,
            spi_value_90d=spi_val_90,
            spi_condition_90d=it.get("spi_condition_90d"),
            spi_evidence_date=it.get("spi_evidence_date") or snap.get("spi_evidence_date"),
            spi_validation_status=it.get("spi_validation_status"),
            spi_validation_status_90d=it.get("spi_validation_status_90d"),
            prob_below20=pb20,
            prob_above150=pa150,
            prob_above200=pa200,
            prob_above300=pa300,
            prob_month_above300=m_pa300,
            prob_month_above400=m_pa400,
            prob_month_above500=m_pa500,
            trigger_reason=reason_text,
        ))

    items.sort(key=lambda x: (x.hth_days_current if x.hth_days_current is not None else -1, x.station_name), reverse=True)

    return HthTableResponse(
        meta=HthTableMeta(
            total=len(items),
            observation_cutoff=snap["observation_cutoff"],
            period_id=snap["period_id"],
            period_label=snap["label"],
            prev_dasarian_label=snap.get("prev_dasarian_label"),
        ),
        data=items
    )


@app.get(
    "/api/v1/early-warning-table",
    response_model=HthTableResponse,
    tags=["Early Warning Table"],
    summary="Retrieve Early Warning Table data for all 57 stations",
    description="Full early warning table dataset with HTH, SPI-30d, Pb20, Pa150/200/300, Monthly Probabilities, and Trigger Reasons.",
)
def get_early_warning_table(
    period_id: Optional[str] = Query(None, description="Evaluation Period ID e.g. 2026-09-das2"),
    kabupaten: Optional[str] = Query(None, description="Filter by Kabupaten"),
    warning_level: Optional[str] = Query(None, description="Filter by Warning Level"),
):
    return get_hth_table(period_id=period_id, kabupaten=kabupaten, warning_level=warning_level)


@app.get(
    "/api/v1/hth-table",
    response_model=HthTableResponse,
    tags=["HTH Monitoring"],
    summary="Retrieve HTH data for all 57 stations (Alias)",
    description="Alias for /api/v1/hth and /api/v1/early-warning-table for backward compatibility.",
)
def get_hth_table_alias(
    period_id: Optional[str] = Query(None, description="Evaluation Period ID e.g. 2026-09-das2"),
    kabupaten: Optional[str] = Query(None, description="Filter by Kabupaten"),
    warning_level: Optional[str] = Query(None, description="Filter by Warning Level"),
):
    return get_hth_table(period_id=period_id, kabupaten=kabupaten, warning_level=warning_level)


# ==============================================================================
# 7. RAINFALL HISTORY ENDPOINT
# ==============================================================================
@app.get(
    "/api/v1/stations/{station_id}/rainfall-history",
    response_model=RainfallHistoryResponse,
    tags=["HTH Monitoring"],
    summary="Get recent consecutive daily rainfall observations for a station",
    description="Returns consecutive daily rainfall observations and dry spell counts for at least one dasarian or custom date range.",
)
def get_station_rainfall_history_endpoint(
    station_id: str,
    period_id: Optional[str] = Query(None, description="Evaluation Period ID e.g. 2026-09-das2"),
    days: int = Query(15, ge=5, le=365, description="Number of recent calendar days if custom date range is omitted"),
    start_date: Optional[str] = Query(None, description="Custom start date (YYYY-MM-DD)"),
    end_date: Optional[str] = Query(None, description="Custom end date (YYYY-MM-DD)"),
):
    sid = station_id.strip().upper()
    try:
        with get_db() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT station_id, station_name, kabupaten FROM stations WHERE station_id = %s", (sid,))
                stn = cur.fetchone()
                if not stn:
                    raise HTTPException(
                        status_code=status.HTTP_404_NOT_FOUND,
                        detail=f"Station with ID '{sid}' not found in active database."
                    )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Database error while querying station metadata: {e}"
        )

    # Validate custom date range if supplied
    if start_date or end_date:
        if not (start_date and end_date):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Kedua parameter 'start_date' dan 'end_date' harus diisi untuk rentang tanggal kustom."
            )
        try:
            s_dt = date.fromisoformat(start_date)
            e_dt = date.fromisoformat(end_date)
            if s_dt > e_dt:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Tanggal awal (start_date) tidak boleh melebihi tanggal akhir (end_date)."
                )
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Format tanggal tidak valid. Gunakan format YYYY-MM-DD."
            )

    snap = get_period_snapshot(period_id)
    cutoff = snap.get("observation_cutoff")

    res = get_station_rainfall_history(
        sid,
        days=days,
        cutoff_date=cutoff,
        start_date=start_date,
        end_date=end_date
    )
    res["station_name"] = stn["station_name"]
    res["kabupaten"] = stn["kabupaten"]
    return res


# ==============================================================================
# 8. DIAGNOSTIC EVALUATION ENDPOINT
# ==============================================================================
@app.get(
    "/api/v1/stations/{station_id}/evaluation",
    response_model=StationEvaluationResponse,
    tags=["Diagnostic Evaluation"],
    summary="Diagnostic data quality evaluation for a station",
    description="Performs read-only diagnostic checks comparing current warning HTH with pipeline source and spatial neighbors.",
)
def get_station_evaluation(
    station_id: str,
    period_id: Optional[str] = Query(None, description="Evaluation Period ID e.g. 2026-09-das2"),
):
    sid = station_id.strip().upper()
    snap = get_period_snapshot(period_id)
    raw_items = snap.get("items", [])

    target_item = None
    for it in raw_items:
        if it["station_id"].strip().upper() == sid:
            target_item = it
            break

    if not target_item:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Station with ID '{sid}' not found in period '{period_id}' evaluation."
        )

    target_record = {
        "station_id": target_item["station_id"],
        "station_name": target_item["station_name"],
        "kabupaten": target_item["kabupaten"],
        "latitude": float(target_item["latitude"]),
        "longitude": float(target_item["longitude"]),
        "warning_level": target_item["warning_level"],
        "hazard_type": target_item["hazard_type"],
        "hth_days_current": int(target_item["hth_days"]) if target_item.get("hth_days") is not None else 0,
        "hth_uncertain": False,
        "data_quality_status": target_item.get("data_quality_status", "VALID"),
        "confidence_level": target_item.get("confidence_level", "HIGH"),
        "last_observation_date": snap["observation_cutoff"],
    }

    all_stations_list = [
        {
            "station_id": r["station_id"],
            "station_name": r["station_name"],
            "kabupaten": r["kabupaten"],
            "latitude": float(r["latitude"]),
            "longitude": float(r["longitude"]),
            "warning_level": r["warning_level"],
            "hazard_type": r["hazard_type"],
            "hth_days_current": int(r["hth_days"]) if r.get("hth_days") is not None else 0,
            "data_quality_status": r.get("data_quality_status", "VALID"),
        }
        for r in raw_items
    ]

    eval_result = evaluate_station(sid, target_record, all_stations_list)
    return eval_result


# ==============================================================================
# 9. DAILY RAINFALL TABLE ENDPOINTS (MIRRORING HARIAN SHEET)
# ==============================================================================
HARIAN_COLUMNS_PATH = Path(__file__).resolve().parent.parent / "data" / "reference" / "stations" / "harian_station_columns.json"
_HARIAN_COLUMNS_CACHE: Optional[List[Dict[str, Any]]] = None


def get_harian_station_columns(master_only: bool = True) -> List[Dict[str, Any]]:
    global _HARIAN_COLUMNS_CACHE
    if _HARIAN_COLUMNS_CACHE is None:
        if HARIAN_COLUMNS_PATH.exists():
            try:
                with open(HARIAN_COLUMNS_PATH, "r", encoding="utf-8") as f:
                    _HARIAN_COLUMNS_CACHE = json.load(f)
            except Exception as e:
                print(f"[Warning] Failed to load harian_station_columns.json: {e}")
                _HARIAN_COLUMNS_CACHE = []
        else:
            _HARIAN_COLUMNS_CACHE = []
    if master_only:
        return [c for c in _HARIAN_COLUMNS_CACHE if c.get("in_master_57", True) is True]
    return _HARIAN_COLUMNS_CACHE


@app.get(
    "/api/v1/rainfall/columns",
    response_model=RainfallColumnsResponse,
    tags=["Daily Rainfall Data"],
    summary="Get column metadata mirroring Timeseries_Kepri.xls sheet HARIAN",
    description="Returns identity date columns and all 58 station columns in exact Excel order.",
)
def get_rainfall_columns():
    cols_data = get_harian_station_columns()
    station_cols = [
        RainfallColumnItem(
            col_idx=c["col_idx"],
            region=c["region"],
            harian_name=c["harian_name"],
            station_id=c["station_id"],
            master_name=c.get("master_name"),
            in_master_57=bool(c.get("in_master_57", True)),
            notes=c.get("notes")
        )
        for c in cols_data
    ]
    return RainfallColumnsResponse(
        total_columns=len(station_cols) + 4,
        date_columns=["Tahun", "Bulan", "Tanggal", "Dasarian"],
        station_columns=station_cols
    )


@app.get(
    "/api/v1/rainfall/daily-table",
    response_model=RainfallDailyTableResponse,
    tags=["Daily Rainfall Data"],
    summary="Get daily rainfall table mirroring sheet HARIAN from MariaDB",
    description="Returns paginated wide-format rows of daily rainfall across all 58 station columns with date filtering.",
)
def get_rainfall_daily_table(
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(30, ge=10, le=100, description="Page size (number of calendar dates)"),
    year: Optional[int] = Query(None, description="Filter by year (e.g. 2026)"),
    month: Optional[int] = Query(None, ge=1, le=12, description="Filter by month (1–12)"),
    dasarian: Optional[int] = Query(None, ge=1, le=3, description="Filter by dasarian (1, 2, or 3)"),
    start_date: Optional[str] = Query(None, description="Start date (YYYY-MM-DD)"),
    end_date: Optional[str] = Query(None, description="End date (YYYY-MM-DD)"),
    order: str = Query("desc", description="Sort order for dates ('desc' or 'asc')"),
):
    cols_data = get_harian_station_columns()
    sort_dir = "ASC" if order.strip().lower() == "asc" else "DESC"

    conditions = []
    params = []

    if year is not None:
        conditions.append("year = %s")
        params.append(year)
    if month is not None:
        conditions.append("month = %s")
        params.append(month)
    if dasarian is not None:
        if dasarian == 1:
            conditions.append("day BETWEEN 1 AND 10")
        elif dasarian == 2:
            conditions.append("day BETWEEN 11 AND 20")
        elif dasarian == 3:
            conditions.append("day BETWEEN 21 AND 31")
    if start_date:
        conditions.append("observation_date >= %s")
        params.append(start_date)
    if end_date:
        conditions.append("observation_date <= %s")
        params.append(end_date)

    where_sql = ("WHERE " + " AND ".join(conditions)) if conditions else ""

    offset = (page - 1) * page_size

    try:
        with get_db() as conn:
            with conn.cursor() as cur:
                # 1. Count total distinct dates
                count_sql = f"SELECT COUNT(DISTINCT observation_date) as total FROM cews_rainfall_daily {where_sql}"
                cur.execute(count_sql, tuple(params))
                total_records = cur.fetchone()["total"]

                total_pages = max(1, (total_records + page_size - 1) // page_size) if total_records > 0 else 1

                if total_records == 0:
                    station_cols = [RainfallColumnItem(**c) for c in cols_data]
                    meta = RainfallDailyTableMeta(
                        total_records=0,
                        page=page,
                        page_size=page_size,
                        total_pages=1,
                        year=year,
                        month=month,
                        dasarian=dasarian,
                        start_date=start_date,
                        end_date=end_date,
                    )
                    return RainfallDailyTableResponse(meta=meta, columns=station_cols, data=[])

                # 2. Query distinct dates for current page
                date_sql = f"""
                SELECT DISTINCT observation_date, year, month, day
                FROM cews_rainfall_daily
                {where_sql}
                ORDER BY observation_date {sort_dir}
                LIMIT %s OFFSET %s
                """
                page_params = tuple(params) + (page_size, offset)
                cur.execute(date_sql, page_params)
                page_dates = cur.fetchall()

                date_list = [r["observation_date"] for r in page_dates]
                if not date_list:
                    station_cols = [RainfallColumnItem(**c) for c in cols_data]
                    meta = RainfallDailyTableMeta(
                        total_records=total_records,
                        page=page,
                        page_size=page_size,
                        total_pages=total_pages,
                        year=year,
                        month=month,
                        dasarian=dasarian,
                        start_date=start_date,
                        end_date=end_date,
                    )
                    return RainfallDailyTableResponse(meta=meta, columns=station_cols, data=[])

                # 3. Query all station observations for these dates
                format_placeholders = ",".join(["%s"] * len(date_list))
                obs_sql = f"""
                SELECT station_id, observation_date, rainfall_mm, obs_status, original_symbol
                FROM cews_rainfall_daily
                WHERE observation_date IN ({format_placeholders})
                """
                cur.execute(obs_sql, tuple(date_list))
                obs_rows = cur.fetchall()

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Database error while querying daily rainfall table: {e}"
        )

    # 4. Organize by date and station
    obs_by_date: Dict[str, Dict[str, Any]] = {}
    for r in obs_rows:
        d_key = r["observation_date"].strftime("%Y-%m-%d") if hasattr(r["observation_date"], "strftime") else str(r["observation_date"])
        s_id = str(r["station_id"]).strip().upper()
        if d_key not in obs_by_date:
            obs_by_date[d_key] = {}
        obs_by_date[d_key][s_id] = {
            "rainfall_mm": float(r["rainfall_mm"]) if r["rainfall_mm"] is not None else None,
            "obs_status": r["obs_status"],
            "original_symbol": r["original_symbol"]
        }

    # 5. Build wide-format rows
    wide_rows = []
    for d_row in page_dates:
        dt = d_row["observation_date"]
        d_str = dt.strftime("%Y-%m-%d") if hasattr(dt, "strftime") else str(dt)
        y = int(d_row["year"])
        m = int(d_row["month"])
        day_num = int(d_row["day"])
        das_num = 1 if day_num <= 10 else (2 if day_num <= 20 else 3)

        stn_dict = {}
        for col in cols_data:
            s_id = col["station_id"]
            if col.get("in_master_57", True):
                stn_data = obs_by_date.get(d_str, {}).get(s_id)
                if stn_data:
                    stn_dict[s_id] = stn_data
                else:
                    stn_dict[s_id] = {
                        "rainfall_mm": None,
                        "obs_status": "MISSING",
                        "original_symbol": "X"
                    }
            else:
                # Tanjung Riau Kota Batam (unmapped non-master column in Excel)
                stn_dict[s_id] = {
                    "rainfall_mm": None,
                    "obs_status": "MISSING",
                    "original_symbol": "X"
                }

        wide_rows.append(RainfallDailyRow(
            date=d_str,
            year=y,
            month=m,
            day=day_num,
            dasarian=das_num,
            stations=stn_dict
        ))

    station_cols = [
        RainfallColumnItem(
            col_idx=c["col_idx"],
            region=c["region"],
            harian_name=c["harian_name"],
            station_id=c["station_id"],
            master_name=c.get("master_name"),
            in_master_57=bool(c.get("in_master_57", True)),
            notes=c.get("notes")
        )
        for c in cols_data
    ]

    meta = RainfallDailyTableMeta(
        total_records=total_records,
        page=page,
        page_size=page_size,
        total_pages=total_pages,
        year=year,
        month=month,
        dasarian=dasarian,
        start_date=start_date,
        end_date=end_date,
    )

    return RainfallDailyTableResponse(
        meta=meta,
        columns=station_cols,
        data=wide_rows
    )


# ==============================================================================
# 10. RAINFALL DATA INPUT ENDPOINTS & MASTER STATIONS
# ==============================================================================
_PARQUET_MASTER_STATIONS_CACHE: Optional[List[Dict[str, Any]]] = None


def get_master_stations_from_parquet() -> List[Dict[str, Any]]:
    """
    Load master station list (57 stations: 52 manual pos hujan + 5 ARG) from
    canonical station_metadata.parquet. Caches result in memory to avoid repeated I/O.
    """
    global _PARQUET_MASTER_STATIONS_CACHE
    if _PARQUET_MASTER_STATIONS_CACHE is not None:
        return _PARQUET_MASTER_STATIONS_CACHE

    parquet_path = PATH_STATION_METADATA
    if not parquet_path.exists():
        raise FileNotFoundError(f"File referensi stasiun master '{parquet_path.name}' tidak ditemukan pada direktori referensi.")

    try:
        df = pd.read_parquet(parquet_path)
    except Exception as e:
        raise RuntimeError(f"Gagal membaca file referensi '{parquet_path.name}': {e}")

    if df.empty or len(df) == 0:
        raise ValueError("File 'station_metadata.parquet' kosong atau tidak memuat data stasiun.")

    stns = []
    for _, r in df.iterrows():
        sid_raw = str(r["station_id"]).strip()
        sid = sid_raw.upper()
        sname = str(r["station_name"]).strip()
        regency = str(r["regency"]).strip() if pd.notnull(r["regency"]) else ""
        province = str(r["province"]).strip() if pd.notnull(r["province"]) else "Kepulauan Riau"
        region = str(r["region"]).strip() if pd.notnull(r["region"]) else "Region I"
        lat = float(r["latitude"])
        lon = float(r["longitude"])
        elev = float(r["elevation_m"]) if pd.notnull(r["elevation_m"]) else None
        nozom = str(r["NOZOM_PROV"]).strip() if ("NOZOM_PROV" in r and pd.notnull(r["NOZOM_PROV"])) else None

        is_arg = sid.endswith("B") or "ARG" in sname.upper()
        stn_type = "Stasiun ARG" if is_arg else "Pos Hujan Manual"

        stns.append({
            "station_id": sid,
            "station_name": sname,
            "kabupaten": regency,
            "regency": regency,
            "province": province,
            "region": region,
            "latitude": lat,
            "longitude": lon,
            "elevation_m": elev,
            "station_type": stn_type,
            "is_arg": is_arg,
            "nozom_prov": nozom,
        })

    # Sort deterministically: Region -> Kabupaten -> Station Name
    stns.sort(key=lambda s: (s["region"] or "", s["kabupaten"] or "", s["station_name"]))
    _PARQUET_MASTER_STATIONS_CACHE = stns
    return _PARQUET_MASTER_STATIONS_CACHE


@app.get(
    "/api/v1/stations/master",
    response_model=RainfallStationsResponse,
    tags=["Stations Master"],
    summary="Get all master stations from station_metadata.parquet",
    description="Returns all 57 master stations (52 manual + 5 ARG) from canonical station_metadata.parquet.",
)
def get_master_stations():
    try:
        raw_list = get_master_stations_from_parquet()
        items = [RainfallStationMasterItem(**s) for s in raw_list]
        return RainfallStationsResponse(
            total=len(items),
            source_file="station_metadata.parquet",
            stations=items
        )
    except FileNotFoundError as fe:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"File referensi stasiun tidak ditemukan: {fe}"
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Gagal memuat metadata stasiun: {e}"
        )


@app.get(
    "/api/v1/rainfall/input/stations",
    response_model=RainfallStationsResponse,
    tags=["Rainfall Data Input"],
    summary="Get all master stations for rainfall data input form",
    description="Alias endpoint for /api/v1/stations/master reading from canonical station_metadata.parquet.",
)
def get_rainfall_input_stations():
    return get_master_stations()


@app.get(
    "/api/v1/rainfall/input/current-values",
    tags=["Rainfall Data Input"],
    summary="Get current observation values in DB for specific dates",
    description="Returns existing observations mapped by station_id and date.",
)
def get_current_rainfall_values(
    start_date: str = Query(..., description="Start date (YYYY-MM-DD)"),
    end_date: str = Query(..., description="End date (YYYY-MM-DD)"),
):
    try:
        s_dt = date.fromisoformat(start_date)
        e_dt = date.fromisoformat(end_date)
        if s_dt > e_dt:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="start_date must be less than or equal to end_date."
            )
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid date format. Use YYYY-MM-DD."
        )

    try:
        with get_db() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT station_id, observation_date, rainfall_mm, obs_status, original_symbol
                    FROM cews_rainfall_daily
                    WHERE observation_date BETWEEN %s AND %s;
                """, (start_date, end_date))
                rows = cur.fetchall()
                result = {}
                for r in rows:
                    sid = r["station_id"]
                    d_str = r["observation_date"].strftime("%Y-%m-%d")
                    if sid not in result:
                        result[sid] = {}
                    result[sid][d_str] = {
                        "rainfall_mm": float(r["rainfall_mm"]) if r["rainfall_mm"] is not None else None,
                        "obs_status": r["obs_status"],
                        "original_symbol": r["original_symbol"]
                    }
                return {"start_date": start_date, "end_date": end_date, "data": result}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Database error while querying current observations: {e}"
        )


@app.post(
    "/api/v1/rainfall/input/validate-preview",
    response_model=RainfallInputPreviewResponse,
    tags=["Rainfall Data Input"],
    summary="Validate input batch and preview changes against current database",
    description="Validates station IDs, date boundaries, numeric values, and categorizes entries into NEW, IDENTICAL, DIFF, and INVALID.",
)
def validate_preview_rainfall_input(payload: RainfallInputPreviewRequest):
    if not payload.entries:
        return RainfallInputPreviewResponse(
            total_submitted=0,
            total_valid=0,
            total_new=0,
            total_identical=0,
            total_diff=0,
            total_invalid=0,
            items=[]
        )

    # Maximum batch limit safety
    if len(payload.entries) > 2000:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Batch size {len(payload.entries)} exceeds safety limit of 2000 entries."
        )

    try:
        valid_stations = {s["station_id"]: s for s in get_master_stations_from_parquet()}
        with get_db() as conn:
            with conn.cursor() as cur:
                # Extract unique pairs for batch query
                pairs = [(e.station_id.strip().upper(), e.observation_date.strip()) for e in payload.entries]
                existing_map = {}
                chunk_size = 500
                for i in range(0, len(pairs), chunk_size):
                    chunk = pairs[i:i + chunk_size]
                    format_strings = ','.join(['(%s, %s)'] * len(chunk))
                    flat_args = [item for pair in chunk for item in pair]
                    cur.execute(
                        f"SELECT station_id, observation_date, rainfall_mm, obs_status FROM cews_rainfall_daily WHERE (station_id, observation_date) IN ({format_strings});",
                        flat_args
                    )
                    for row in cur.fetchall():
                        key = (row["station_id"], row["observation_date"].strftime("%Y-%m-%d"))
                        existing_map[key] = row

                results = []
                counts = {"NEW": 0, "IDENTICAL": 0, "DIFF": 0, "INVALID": 0}
                seen_keys = set()

                for e in payload.entries:
                    sid = e.station_id.strip().upper()
                    d_str = e.observation_date.strip()
                    rf_in = e.rainfall_mm
                    obs_in = e.obs_status.strip().upper()

                    # 1. Station verification
                    if sid not in valid_stations:
                        results.append(RainfallInputPreviewItem(
                            station_id=sid,
                            date=d_str,
                            category="INVALID",
                            reason=f"Stasiun '{sid}' tidak terdaftar pada master DSS-PIK."
                        ))
                        counts["INVALID"] += 1
                        continue

                    stn_name = valid_stations[sid]["station_name"]

                    # 2. Date verification
                    try:
                        d_obj = date.fromisoformat(d_str)
                        if d_obj.year < 1981 or d_obj > date.today() + timedelta(days=31):
                            results.append(RainfallInputPreviewItem(
                                station_id=sid,
                                station_name=stn_name,
                                date=d_str,
                                category="INVALID",
                                reason=f"Tanggal {d_str} di luar rentang kalender yang diperbolehkan."
                            ))
                            counts["INVALID"] += 1
                            continue
                    except ValueError:
                        results.append(RainfallInputPreviewItem(
                            station_id=sid,
                            station_name=stn_name,
                            date=d_str,
                            category="INVALID",
                            reason=f"Format tanggal '{d_str}' tidak valid (gunakan YYYY-MM-DD)."
                        ))
                        counts["INVALID"] += 1
                        continue

                    # 3. Value & status verification
                    if obs_in not in ("OBSERVED_VALID", "OBSERVED_ZERO", "TTU", "MISSING", "CORRECTED"):
                        results.append(RainfallInputPreviewItem(
                            station_id=sid,
                            station_name=stn_name,
                            date=d_str,
                            category="INVALID",
                            reason=f"Status observasi '{obs_in}' tidak valid."
                        ))
                        counts["INVALID"] += 1
                        continue

                    if rf_in is not None and rf_in < 0:
                        results.append(RainfallInputPreviewItem(
                            station_id=sid,
                            station_name=stn_name,
                            date=d_str,
                            category="INVALID",
                            reason=f"Nilai curah hujan tidak boleh negatif ({rf_in} mm)."
                        ))
                        counts["INVALID"] += 1
                        continue

                    # 4. Intra-batch duplicate check
                    key = (sid, d_str)
                    if key in seen_keys:
                        results.append(RainfallInputPreviewItem(
                            station_id=sid,
                            station_name=stn_name,
                            date=d_str,
                            category="INVALID",
                            reason="Duplikasi pasangan stasiun dan tanggal dalam satu batch input."
                        ))
                        counts["INVALID"] += 1
                        continue
                    seen_keys.add(key)

                    # 5. Check against DB
                    existing = existing_map.get(key)
                    if not existing:
                        results.append(RainfallInputPreviewItem(
                            station_id=sid,
                            station_name=stn_name,
                            date=d_str,
                            category="NEW",
                            new_value=rf_in,
                            new_status=obs_in
                        ))
                        counts["NEW"] += 1
                    else:
                        old_rf = float(existing["rainfall_mm"]) if existing["rainfall_mm"] is not None else None
                        old_st = existing["obs_status"]

                        val_same = (old_rf == rf_in) or (old_rf is None and rf_in is None)
                        status_same = (old_st == obs_in)

                        if val_same and status_same:
                            results.append(RainfallInputPreviewItem(
                                station_id=sid,
                                station_name=stn_name,
                                date=d_str,
                                category="IDENTICAL",
                                old_value=old_rf,
                                new_value=rf_in,
                                old_status=old_st,
                                new_status=obs_in
                            ))
                            counts["IDENTICAL"] += 1
                        else:
                            results.append(RainfallInputPreviewItem(
                                station_id=sid,
                                station_name=stn_name,
                                date=d_str,
                                category="DIFF",
                                old_value=old_rf,
                                new_value=rf_in,
                                old_status=old_st,
                                new_status=obs_in
                            ))
                            counts["DIFF"] += 1

                total_valid = counts["NEW"] + counts["IDENTICAL"] + counts["DIFF"]
                return RainfallInputPreviewResponse(
                    total_submitted=len(payload.entries),
                    total_valid=total_valid,
                    total_new=counts["NEW"],
                    total_identical=counts["IDENTICAL"],
                    total_diff=counts["DIFF"],
                    total_invalid=counts["INVALID"],
                    items=results
                )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Preview error: {e}")


@app.post(
    "/api/v1/rainfall/input/commit",
    response_model=RainfallInputCommitResponse,
    tags=["Rainfall Data Input"],
    summary="Commit validated rainfall entries to MariaDB in an atomic transaction",
    description="Saves new/corrected rainfall records to cews_rainfall_daily, records staging in staging_rainfall_import, and logs corrections to cews_rainfall_correction_log.",
)
def commit_rainfall_input(payload: RainfallInputCommitRequest):
    if not payload.entries:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No entries provided to commit.")

    valid_station_ids = {s["station_id"] for s in get_master_stations_from_parquet()}
    for e in payload.entries:
        sid = e.station_id.strip().upper()
        if sid not in valid_station_ids:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Stasiun '{sid}' tidak terdaftar pada master stasiun DSS-PIK."
            )

    conn = None
    try:
        from backend.database import get_raw_connection
        conn = get_raw_connection()
        conn.autocommit = False
        with conn.cursor() as cur:
            # 1. Fetch current DB state for these keys to detect any DIFF requiring confirmation
            pairs = [(e.station_id.strip().upper(), e.observation_date.strip()) for e in payload.entries]
            existing_map = {}
            chunk_size = 500
            for i in range(0, len(pairs), chunk_size):
                chunk = pairs[i:i + chunk_size]
                format_strings = ','.join(['(%s, %s)'] * len(chunk))
                flat_args = [item for pair in chunk for item in pair]
                cur.execute(
                    f"SELECT station_id, observation_date, rainfall_mm, obs_status FROM cews_rainfall_daily WHERE (station_id, observation_date) IN ({format_strings});",
                    flat_args
                )
                for row in cur.fetchall():
                    key = (row["station_id"], row["observation_date"].strftime("%Y-%m-%d"))
                    existing_map[key] = row

            # Validate DIFF authorization
            diff_entries = []
            for e in payload.entries:
                sid = e.station_id.strip().upper()
                d_str = e.observation_date.strip()
                key = (sid, d_str)
                if key in existing_map:
                    ex = existing_map[key]
                    old_rf = float(ex["rainfall_mm"]) if ex["rainfall_mm"] is not None else None
                    old_st = ex["obs_status"]
                    val_same = (old_rf == e.rainfall_mm) or (old_rf is None and e.rainfall_mm is None)
                    status_same = (old_st == e.obs_status)
                    if not (val_same and status_same):
                        diff_entries.append((e, old_rf, old_st))

            if diff_entries and not payload.confirm_overwrite:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Terdapat {len(diff_entries)} data yang berbeda dengan database. Pengguna harus mengonfirmasi penimpaan (confirm_overwrite=True) sebelum menyimpan."
                )

            # 2. Execute Staging & Storage inside transaction
            saved_count = 0
            new_count = 0
            corrected_count = 0
            skipped_identical = 0
            b_id = payload.batch_id or f"BATCH_MANUAL_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

            for e in payload.entries:
                sid = e.station_id.strip().upper()
                d_str = e.observation_date.strip()
                d_obj = date.fromisoformat(d_str)
                rf_val = e.rainfall_mm
                obs_st = e.obs_status.strip().upper()
                orig_sym = e.original_symbol or (str(rf_val) if rf_val is not None else ("TTU" if obs_st == "TTU" else "X"))

                is_obs = 0 if obs_st == "MISSING" else 1
                is_mis = 1 if obs_st == "MISSING" else 0
                data_qual = "MISSING" if obs_st == "MISSING" else "OBSERVED"

                key = (sid, d_str)
                ex = existing_map.get(key)

                # Staging row
                cur.execute("""
                    INSERT INTO staging_rainfall_import
                    (import_batch_id, station_id, observation_date, rainfall_mm, obs_status, original_symbol, data_quality, is_observed, is_missing, is_gap_filled, rainfall_source, year, month, day, validation_status)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, 0, 'MANUAL_INPUT', %s, %s, %s, 'COMMITTED');
                """, (b_id, sid, d_str, rf_val, obs_st, orig_sym, data_qual, is_obs, is_mis, d_obj.year, d_obj.month, d_obj.day))

                if not ex:
                    # NEW INSERT
                    cur.execute("""
                        INSERT INTO cews_rainfall_daily
                        (station_id, observation_date, rainfall_mm, obs_status, original_symbol, data_quality, is_observed, is_missing, is_gap_filled, rainfall_source)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, 0, 'MANUAL_INPUT');
                    """, (sid, d_str, rf_val, obs_st, orig_sym, data_qual, is_obs, is_mis))
                    new_count += 1
                    saved_count += 1
                else:
                    old_rf = float(ex["rainfall_mm"]) if ex["rainfall_mm"] is not None else None
                    old_st = ex["obs_status"]
                    val_same = (old_rf == rf_val) or (old_rf is None and rf_val is None)
                    status_same = (old_st == obs_st)

                    if val_same and status_same:
                        skipped_identical += 1
                    else:
                        # CORRECTION / OVERWRITE
                        reason_text = payload.correction_reason or "Koreksi nilai observasi manual"
                        approved_user = payload.approved_by or "OPERATOR_CEWS"
                        cur.execute("""
                            INSERT INTO cews_rainfall_correction_log
                            (station_id, observation_date, old_rainfall_mm, new_rainfall_mm, old_obs_status, new_obs_status, reason, approved_by, corrected_at)
                            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, NOW());
                        """, (sid, d_str, old_rf, rf_val if rf_val is not None else 0.0, old_st, obs_st, reason_text, approved_user))

                        cur.execute("""
                            UPDATE cews_rainfall_daily
                            SET rainfall_mm = %s, obs_status = %s, original_symbol = %s, data_quality = %s, is_observed = %s, is_missing = %s, updated_at = NOW()
                            WHERE station_id = %s AND observation_date = %s;
                        """, (rf_val, obs_st, orig_sym, data_qual, is_obs, is_mis, sid, d_str))
                        corrected_count += 1
                        saved_count += 1

            conn.commit()
            return RainfallInputCommitResponse(
                success=True,
                batch_id=b_id,
                total_saved=saved_count,
                new_count=new_count,
                corrected_count=corrected_count,
                skipped_identical_count=skipped_identical,
                message=f"Berhasil menyimpan {saved_count} observasi ({new_count} data baru, {corrected_count} terkoreksi, {skipped_identical} identik dilewati)."
            )
    except HTTPException:
        if conn:
            conn.rollback()
        raise
    except Exception as e:
        if conn:
            conn.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Terjadi kesalahan saat menyimpan data (transaksi dibatalkan): {e}"
        )
    finally:
        if conn and conn.open:
            conn.close()


# ==============================================================================
# 11. DATA CENTER ENDPOINTS & DATA DOWNLOAD
# ==============================================================================
@app.get(
    "/api/v1/stations/{station_id}/info",
    response_model=StationDetailedInfoResponse,
    tags=["Station Details"],
    summary="Get Detailed Station Information & Operating Metrics (Informasi Pos)",
    description="Returns metadata from station_metadata.parquet merged with operational observation statistics from cews_rainfall_daily.",
)
def get_station_info_endpoint(station_id: str):
    try:
        return get_station_detailed_info(station_id)
    except ValueError as ve:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(ve))
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Gagal mengambil informasi stasiun: {e}"
        )


@app.get(
    "/api/v1/spi/data",
    response_model=SpiTableResponse,
    tags=["SPI Data Center"],
    summary="Get SPI Data Table across 4 modes (Dasarian/Harian, 30d/90d)",
    description="Returns wide-format SPI observations matching raw parquet datasets.",
)
def get_spi_data_endpoint(
    period_type: str = Query("DASARIAN", description="SPI Period Type: DASARIAN or DAILY"),
    timescale: str = Query("30D", description="Accumulation timescale: 30D or 90D"),
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(30, ge=5, le=100, description="Page size"),
    order: str = Query("desc", description="Sort order: desc or asc"),
    start_date: Optional[str] = Query(None, description="Start date filter (YYYY-MM-DD)"),
    end_date: Optional[str] = Query(None, description="End date filter (YYYY-MM-DD)"),
    station_id: Optional[str] = Query(None, description="Filter single station ID"),
):
    try:
        return get_spi_data(
            period_type=period_type,
            timescale=timescale,
            page=page,
            page_size=page_size,
            order=order,
            start_date=start_date,
            end_date=end_date,
            station_id=station_id,
        )
    except FileNotFoundError as fe:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(fe))
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Gagal memuat data SPI: {e}"
        )


@app.get(
    "/api/v1/spi/download",
    tags=["SPI Data Center"],
    summary="Download SPI Data in CSV or XLSX format",
)
def download_spi_endpoint(
    period_type: str = Query("DASARIAN", description="DASARIAN or DAILY"),
    timescale: str = Query("30D", description="30D or 90D"),
    file_format: Optional[str] = Query(None, description="csv or xlsx"),
    format: Optional[str] = Query(None, description="csv or xlsx"),
    start_date: Optional[str] = Query(None),
    end_date: Optional[str] = Query(None),
    stations: Optional[str] = Query(None, description="Comma-separated station IDs"),
    station_ids: Optional[str] = Query(None, description="Comma-separated station IDs"),
):
    try:
        fmt = (format or file_format or "csv").lower().strip()
        raw_stns = station_ids or stations
        stn_list = [s.strip() for s in raw_stns.split(",")] if raw_stns else None
        content, media_type, filename = export_spi_data(
            period_type=period_type,
            timescale=timescale,
            file_format=fmt,
            start_date=start_date,
            end_date=end_date,
            station_ids=stn_list,
        )
        return Response(
            content=content,
            media_type=media_type,
            headers={
                "Content-Disposition": f'attachment; filename="{filename}"',
                "Access-Control-Expose-Headers": "Content-Disposition",
            }
        )
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Gagal mengekspor data SPI: {e}")


@app.get(
    "/api/v1/probability/periods",
    tags=["Probability Data Center"],
    summary="Get List of Available Probability Forecast Periods",
    description="Returns available distinct target forecast periods from cews_forecast_snapshot categorized by DASARIAN and BULANAN with vintages."
)
def get_probability_periods_endpoint():
    from backend.data_service import get_probability_periods_list
    return get_probability_periods_list()


@app.get(
    "/api/v1/probability/data",
    response_model=ProbabilityTableResponse,
    tags=["Probability Data Center"],
    summary="Get Forecast Probability Dataset",
    description="Returns ECMWF dasarian and monthly probability forecasts across stations.",
)
def get_probability_data_endpoint(
    period_id: Optional[str] = Query(None, description="Period ID e.g. 2026-09-das2"),
    station_id: Optional[str] = Query(None, description="Filter single station ID"),
    issue_date: Optional[str] = Query(None, description="Filter specific forecast issue date"),
    page: int = Query(1, ge=1),
    page_size: int = Query(60, ge=5, le=100),
):
    try:
        return get_probability_data(
            period_id=period_id,
            station_id=station_id,
            issue_date=issue_date,
            page=page,
            page_size=page_size,
        )
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Gagal memuat data probabilitas: {e}")


@app.get(
    "/api/v1/probability/download",
    tags=["Probability Data Center"],
    summary="Download Forecast Probability Dataset in CSV or XLSX format",
)
def download_probability_endpoint(
    period_id: str = Query(None),
    file_format: Optional[str] = Query(None, description="csv or xlsx"),
    format: Optional[str] = Query(None, description="csv or xlsx"),
    stations: Optional[str] = Query(None, description="Comma-separated station IDs"),
    station_ids: Optional[str] = Query(None, description="Comma-separated station IDs"),
    parameters: Optional[str] = Query(None, description="Comma-separated parameter names"),
    issue_date: Optional[str] = Query(None, description="Filter specific forecast issue date"),
):
    try:
        fmt = (format or file_format or "csv").lower().strip()
        raw_stns = station_ids or stations
        stn_list = [s.strip() for s in raw_stns.split(",")] if raw_stns else None
        param_list = [p.strip() for p in parameters.split(",")] if parameters else None
        content, media_type, filename = export_probability_data(
            period_id=period_id,
            file_format=fmt,
            station_ids=stn_list,
            parameters=param_list,
            issue_date=issue_date,
        )
        return Response(
            content=content,
            media_type=media_type,
            headers={
                "Content-Disposition": f'attachment; filename="{filename}"',
                "Access-Control-Expose-Headers": "Content-Disposition",
            }
        )
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Gagal mengekspor data probabilitas: {e}")


@app.get(
    "/api/v1/rainfall/download",
    tags=["Rainfall Monitoring"],
    summary="Download Daily Rainfall Observation Dataset in CSV or XLSX format",
)
def download_rainfall_endpoint(
    file_format: Optional[str] = Query(None, description="csv or xlsx"),
    format: Optional[str] = Query(None, description="csv or xlsx"),
    start_date: Optional[str] = Query(None, description="Start date (YYYY-MM-DD)"),
    end_date: Optional[str] = Query(None, description="End date (YYYY-MM-DD)"),
    stations: Optional[str] = Query(None, description="Comma-separated station IDs"),
    station_ids: Optional[str] = Query(None, description="Comma-separated station IDs"),
):
    try:
        fmt = (format or file_format or "csv").lower().strip()
        raw_stns = station_ids or stations
        stn_list = [s.strip() for s in raw_stns.split(",")] if raw_stns else None
        content, media_type, filename = export_rainfall_data(
            file_format=fmt,
            start_date=start_date,
            end_date=end_date,
            station_ids=stn_list,
        )
        return Response(
            content=content,
            media_type=media_type,
            headers={
                "Content-Disposition": f'attachment; filename="{filename}"',
                "Access-Control-Expose-Headers": "Content-Disposition",
            }
        )
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Gagal mengekspor data curah hujan: {e}")


# ==============================================================================
# 12. OFFICIAL MAP GENERATION ENDPOINTS (PAKET 4)
# ==============================================================================
@app.post(
    "/api/v1/maps/generate",
    response_model=MapGenerateResponse,
    tags=["Official Warning Maps"],
    summary="Generate Official PDKM or PDCHT Warning Map (Paket 4)",
    description="Renders high-res PNG & PDF based on explicit operator status choices for 7 Kepri regencies."
)
def generate_map_endpoint(payload: MapGenerateRequest):
    try:
        # Resolve period label
        period_title = payload.period_id
        manifest = get_periods_manifest()
        for p in manifest:
            if p["period_id"] == payload.period_id:
                period_title = p["label"]
                break

        res = generate_official_warning_map(
            map_type=payload.map_type,
            period_title=period_title,
            period_id=payload.period_id,
            regency_status=payload.regency_status,
            regency_decisions=payload.regency_decisions,
            kecamatan_decisions=payload.kecamatan_decisions,
            operator_name=payload.operator_name,
            notes=payload.notes,
        )
        return MapGenerateResponse(**res)
    except FileNotFoundError as fe:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(fe))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Gagal menghasilkan peta resmi: {e}")


@app.post(
    "/api/v1/maps/generate-json",
    response_model=MapJsonExportResponse,
    tags=["Official Warning Maps"],
    summary="Generate and Validate Standardized SIH3 JSON Warning Payload",
    description="Builds, validates, and exports standardized SIH3 JSON with chosen scope or unified decisions."
)
@app.post(
    "/api/v1/maps/export-json",
    response_model=MapJsonExportResponse,
    tags=["Official Warning Maps"],
    summary="Export Standardized SIH3 JSON Warning Payload (Alias)",
)
def generate_map_json_endpoint(payload: MapJsonExportRequest):
    from backend.regional_warning_service import build_map_modal_sih3_json
    try:
        res = build_map_modal_sih3_json(
            period_id=payload.period_id,
            scope=payload.scope,
            pdkm_status=payload.pdkm_status,
            pdcht_status=payload.pdcht_status,
            regency_decisions=payload.regency_decisions,
            kecamatan_decisions=payload.kecamatan_decisions,
            override_reasons=payload.override_reasons,
            analysis_notes=payload.analysis_notes,
            valid_from=payload.valid_from,
            valid_until=payload.valid_until,
            operator_name=payload.operator_name,
            publish=payload.publish,
        )
        return MapJsonExportResponse(**res)
    except ValueError as ve:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(ve))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Gagal menghasilkan JSON SIH3: {e}")


@app.get(
    "/api/v1/maps/download/{filename}",
    tags=["Official Warning Maps"],
    summary="Download Generated Map or JSON File (JPG, PNG, PDF, or JSON)",
)
def download_map_file(filename: str):
    file_path = MAPS_OUTPUT_DIR / filename
    if not file_path.exists():
        # Also check sih3 output dir if json
        sih3_path = MAPS_OUTPUT_DIR.parent / "sih3" / filename
        if sih3_path.exists():
            file_path = sih3_path
        else:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"File '{filename}' tidak ditemukan.")
    
    if filename.lower().endswith(".pdf"):
        media_type = "application/pdf"
    elif filename.lower().endswith(".json"):
        media_type = "application/json"
    elif filename.lower().endswith((".jpg", ".jpeg")):
        media_type = "image/jpeg"
    else:
        media_type = "image/png"

    return FileResponse(
        path=str(file_path),
        media_type=media_type,
        filename=filename,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'}
    )


@app.get(
    "/api/v1/maps/history",
    tags=["Official Warning Maps"],
    summary="Get List of Previously Generated Official Maps",
)
def get_map_history_endpoint():
    try:
        maps = list_generated_maps()
        return {"total": len(maps), "items": maps}
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


# ==============================================================================
# 12.1. SPATIAL BOUNDARY & ZOM GEOJSON ENDPOINTS
# ==============================================================================
@app.get(
    "/api/v1/geo/layers/{layer_name}",
    tags=["Geo Data"],
    summary="Get GeoJSON Administrative or Climate Boundaries (kabkot, kecamatan, zom)",
)
def get_geo_layer(layer_name: str):
    name = layer_name.lower().strip()
    file_map = {
        "kabkot": "kepri_kabkot.geojson",
        "kabupaten": "kepri_kabkot.geojson",
        "kecamatan": "kepri_kecamatan.geojson",
        "zom": "kepri_zom.geojson",
    }
    if name not in file_map:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Layer '{layer_name}' tidak ditemukan.")

    layer_file = ROOT_DIR / "data" / "reference" / "boundaries" / file_map[name]
    if not layer_file.exists():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"File layer '{file_map[name]}' belum tersedia.")

    return FileResponse(
        path=str(layer_file),
        media_type="application/geo+json",
        filename=file_map[name],
    )


@app.get(
    "/api/v1/geo/zom-analysis",
    tags=["Geo Data"],
    summary="Spatial Join Analysis of 57 Master Stations across 14 ZOM Polygons with Climate Distribution",
)
def get_zom_spatial_analysis_endpoint(period_id: Optional[str] = Query(None)):
    from backend.zom_service import get_zom_spatial_analysis
    try:
        return get_zom_spatial_analysis(period_id=period_id)
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Gagal memproses analisis spasial ZOM: {e}")



if __name__ == "__main__":
    import uvicorn
    uvicorn.run("backend.main:app", host="127.0.0.1", port=8000, reload=True)



# ==============================================================================
# SPI TREND & UNIFIED OPERATIONAL DATA INGESTION ENDPOINTS
# ==============================================================================
@app.get(
    "/api/v1/stations/{station_id}/spi-trend",
    response_model=StationSpiTrendResponse,
    tags=["SPI Analysis"],
    summary="Get comprehensive SPI time series trend (Harian, Dasarian, Bulanan)",
    description="Returns synchronized historical SPI series for line chart visualization with standard threshold lines.",
)
def get_station_spi_trend_endpoint(
    station_id: str,
    months: int = Query(12, description="Lookback window in months (default 12)"),
):
    from backend.data_service import get_station_spi_trend
    try:
        return get_station_spi_trend(station_id, months=months)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Gagal mengambil data tren SPI: {e}"
        )


@app.post(
    "/api/v1/ingestion/preview",
    response_model=IngestionPreviewResponse,
    tags=["Operational Data Ingestion"],
    summary="Parse and preview operational data upload without modifying database",
    description="Detects file structure, parses records, validates stations/dates, and checks differences against current DB/Parquet storage.",
)
async def preview_ingestion_file(
    file: Optional[UploadFile] = File(None, description="Uploaded Excel (.xlsx) or Parquet file"),
    files: Optional[List[UploadFile]] = File(None, description="Uploaded Excel (.xlsx) or Parquet files"),
    data_type: Optional[str] = Form(None, description="Optional override: CURAH_HUJAN, SPI_HARIAN, SPI_DASARIAN, SPI_BULANAN, PROBABILITAS_DASARIAN, PROBABILITAS_BULANAN"),
    dataset_type: Optional[str] = Form(None, description="Alias for data_type"),
    timescale: Optional[str] = Form("30D", description="Timescale for SPI (30D or 90D)"),
):
    from backend.ingestion_service import (
        detect_file_type,
        parse_rainfall_excel,
        parse_spi_parquet,
        parse_spi_bulanan_excel,
        parse_probability_excel,
    )

    try:
        target_file = file
        if not target_file and files and len(files) > 0:
            target_file = files[0]

        if not target_file:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Tidak ada berkas yang diunggah untuk diproses."
            )

        file_bytes = await target_file.read()
        filename = target_file.filename or "uploaded_file"

        raw_type = (data_type or dataset_type or "").strip().upper()
        if raw_type in ("RAINFALL_DAILY", "CURAH_HUJAN"):
            detected_type = "CURAH_HUJAN"
        elif raw_type in ("SPI_HARIAN", "SPI_DAILY"):
            detected_type = "SPI_HARIAN"
        elif raw_type in ("SPI_DASARIAN",):
            detected_type = "SPI_DASARIAN"
        elif raw_type in ("SPI_BULANAN", "SPI_MONTHLY"):
            detected_type = "SPI_BULANAN"
        elif raw_type in ("PROBABILITAS_DASARIAN", "PROBABILITY_DASARIAN"):
            detected_type = "PROBABILITAS_DASARIAN"
        elif raw_type in ("PROBABILITAS_BULANAN", "PROBABILITY_BULANAN"):
            detected_type = "PROBABILITAS_BULANAN"
        elif raw_type and raw_type not in ("AUTO", "AUTO_DETECT"):
            detected_type = raw_type
        else:
            detected_type = detect_file_type(filename, file_bytes)

        ts = (timescale or "30D").strip().upper()

        if detected_type in ("CURAH_HUJAN", "RAINFALL_DAILY"):
            return parse_rainfall_excel(file_bytes, filename)
        elif detected_type == "SPI_HARIAN":
            return parse_spi_parquet(file_bytes, filename, period_type="HARIAN", timescale=ts)
        elif detected_type == "SPI_DASARIAN":
            return parse_spi_parquet(file_bytes, filename, period_type="DASARIAN", timescale=ts)
        elif detected_type == "SPI_BULANAN":
            return parse_spi_bulanan_excel(file_bytes, filename)
        elif detected_type in ("PROBABILITAS_DASARIAN", "PROBABILITY_DASARIAN", "PROBABILITAS_BULANAN", "PROBABILITY_BULANAN"):
            forecast_type = "PROBABILITAS_BULANAN" if "BULAN" in detected_type else "PROBABILITAS_DASARIAN"
            return parse_probability_excel(file_bytes, filename, forecast_type=forecast_type)
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Format berkas '{filename}' tidak dikenali sebagai format template operasional yang didukung."
            )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Gagal memproses file: {e}"
        )


@app.post(
    "/api/v1/ingestion/commit",
    response_model=IngestionCommitResponse,
    tags=["Operational Data Ingestion"],
    summary="Commit staged upload batch to operational storage atomically",
    description="Applies validated changes to MariaDB / Parquet storage with transactional safety, logging, and period synchronization.",
)
def commit_ingestion_endpoint(payload: IngestionCommitRequest):
    from backend.ingestion_service import commit_ingestion_session
    try:
        res = commit_ingestion_session(
            staging_token=payload.staging_token,
            confirm_overwrite=payload.confirm_overwrite,
            selected_periods=payload.selected_periods,
            explicit_update_consent=payload.explicit_update_consent,
            approval_scope=payload.approval_scope,
            operator=payload.operator or "OPERATOR_BMKG"
        )
        return res
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Gagal menyimpan data ingestion: {e}"
        )


@app.get(
    "/api/v1/ingestion/history",
    response_model=IngestionHistoryResponse,
    tags=["Operational Data Ingestion"],
    summary="Get recent data ingestion history and audit trail",
)
def get_ingestion_history_endpoint(limit: int = Query(50, ge=1, le=200)):
    from backend.ingestion_service import get_ingestion_history_list
    try:
        items = get_ingestion_history_list(limit=limit)
        return {"total": len(items), "items": items}
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Gagal mengambil riwayat ingestion: {e}"
        )


@app.get(
    "/api/v1/ingestion/latest-status",
    response_model=LatestDataStatusResponse,
    tags=["Operational Data Ingestion"],
    summary="Get live operational status of all canonical data storages",
)
def get_latest_data_status_endpoint():
    from backend.ingestion_service import get_latest_data_status
    try:
        return get_latest_data_status()
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Gagal mengambil status data operasional: {e}"
        )


@app.get(
    "/api/v1/ingestion/batches",
    response_model=IngestionBatchListResponse,
    tags=["Operational Data Ingestion"],
    summary="Get list of ingestion batches with filtering",
)
def get_ingestion_batches_endpoint(
    data_type: Optional[str] = Query(None),
    batch_status: Optional[str] = Query(None, alias="status"),
    start_date: Optional[str] = Query(None),
    end_date: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
):
    from backend.ingestion_service import get_ingestion_batches
    try:
        return get_ingestion_batches(
            data_type=data_type,
            status=batch_status,
            start_date=start_date,
            end_date=end_date,
            limit=limit,
            offset=offset
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Gagal mengambil daftar batch: {e}"
        )


@app.get(
    "/api/v1/ingestion/batch/{batch_id}",
    tags=["Operational Data Ingestion"],
    summary="Get detailed information and audit records of a specific batch",
)
def get_batch_detail_endpoint(batch_id: str):
    from backend.ingestion_service import get_batch_details
    try:
        return get_batch_details(batch_id)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Gagal mengambil detail batch: {e}"
        )


@app.post(
    "/api/v1/ingestion/batch/{batch_id}/cancel",
    response_model=BatchCancelResponse,
    tags=["Operational Data Ingestion"],
    summary="Safely rollback/cancel an ingestion batch with audit logging",
)
def cancel_batch_endpoint(batch_id: str, payload: BatchCancelRequest):
    from backend.ingestion_service import cancel_ingestion_batch
    try:
        return cancel_ingestion_batch(
            batch_id=batch_id,
            reason=payload.reason,
            operator=payload.operator or "OPERATOR_BMKG"
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Gagal membatalkan batch: {e}"
        )


@app.post(
    "/api/v1/ingestion/record/correct",
    response_model=RecordCorrectionResponse,
    tags=["Operational Data Ingestion"],
    summary="Correct a single observation record with audit logging",
)
def correct_record_endpoint(payload: RecordCorrectionRequest):
    from backend.ingestion_service import correct_rainfall_record
    try:
        return correct_rainfall_record(
            station_id=payload.station_id,
            observation_date=payload.date,
            new_rainfall_mm=payload.new_rainfall_mm,
            reason=payload.reason,
            operator=payload.operator or "OPERATOR_BMKG"
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Gagal mengoreksi rekor observasi: {e}"
        )


@app.post(
    "/api/v1/ingestion/record/void",
    response_model=RecordVoidResponse,
    tags=["Operational Data Ingestion"],
    summary="Void a single observation record with audit logging",
)
def void_record_endpoint(payload: RecordVoidRequest):
    from backend.ingestion_service import void_rainfall_record
    try:
        return void_rainfall_record(
            station_id=payload.station_id,
            observation_date=payload.date,
            reason=payload.reason,
            operator=payload.operator or "OPERATOR_BMKG"
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Gagal membatalkan/void rekor observasi: {e}"
        )


@app.get(
    "/api/v1/forecast/vintages",
    response_model=ForecastVintagesResponse,
    tags=["Operational Forecast Vintages"],
    summary="List available forecast vintages from cews_forecast_snapshot",
)
def get_forecast_vintages_endpoint(
    target_year: Optional[int] = Query(None),
    target_month: Optional[int] = Query(None),
    target_dasarian: Optional[int] = Query(None),
):
    from backend.ingestion_service import get_forecast_vintages
    try:
        vintages = get_forecast_vintages(
            target_year=target_year,
            target_month=target_month,
            target_dasarian=target_dasarian
        )
        return {"total": len(vintages), "vintages": vintages}
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Gagal mengambil vintage prakiraan: {e}"
        )


@app.get(
    "/api/v1/ingestion/operational-summary",
    response_model=OperationalSummaryResponse,
    tags=["Operational Data Ingestion"],
    summary="Get high-level operational statistics and KPI counts",
)
def get_operational_summary_endpoint():
    from backend.ingestion_service import get_operational_summary
    try:
        return get_operational_summary()
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Gagal mengambil ringkasan operasional: {e}"
        )


@app.post(
    "/api/v1/ingestion/spi/void",
    response_model=SpiVoidResponse,
    tags=["Operational Data Ingestion"],
    summary="Void/nullify an erroneous SPI observation record with audit logging",
)
def void_spi_record_endpoint(payload: SpiVoidRequest):
    from backend.ingestion_service import void_spi_record
    try:
        return void_spi_record(
            station_id=payload.station_id,
            period_type=payload.period_type,
            timescale=payload.timescale,
            date_str=payload.date,
            reason=payload.reason,
            operator=payload.operator or "OPERATOR_BMKG"
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Gagal membatalkan/void rekor SPI: {e}"
        )


@app.post(
    "/api/v1/ingestion/probability/void",
    response_model=ProbabilityVoidResponse,
    tags=["Operational Data Ingestion"],
    summary="Void/delete forecast probability records with audit logging",
)
def void_probability_record_endpoint(payload: ProbabilityVoidRequest):
    from backend.ingestion_service import void_probability_record
    try:
        return void_probability_record(
            issue_date=payload.issue_date,
            target_period=payload.target_period,
            station_id=payload.station_id,
            forecast_parameter=payload.forecast_parameter,
            reason=payload.reason,
            operator=payload.operator or "OPERATOR_BMKG"
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Gagal membatalkan/void rekor probabilitas: {e}"
        )


@app.get(
    "/api/v1/ingestion/corrections-log",
    tags=["Operational Data Ingestion"],
    summary="Get unified audit history of manual record corrections and void operations",
)
def get_corrections_log_endpoint(limit: int = Query(100, ge=1, le=500)):
    from backend.ingestion_service import get_correction_and_void_logs
    try:
        return get_correction_and_void_logs(limit=limit)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Gagal mengambil riwayat koreksi dan pembatalan: {e}"
        )


# ==============================================================================
# REGIONAL WARNING MANAGEMENT & SIH3 PUBLICATION ENDPOINTS (FASE II - VII)
# ==============================================================================

@app.get(
    "/api/v1/warnings/regional/mapping",
    tags=["Regional Warnings & SIH3 Publication"],
    summary="Get verified canonical station-to-regency mapping across 7 Kabupaten/Kota of Kepulauan Riau",
)
def get_regional_station_mapping_endpoint():
    from backend.regional_warning_service import get_verified_station_region_mapping
    try:
        return get_verified_station_region_mapping()
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Gagal memverifikasi pemetaan stasiun ke wilayah: {e}",
        )


@app.get(
    "/api/v1/warnings/regional/recommendations",
    tags=["Regional Warnings & SIH3 Publication"],
    summary="Compute regional PDKM & PDCHT recommendations and merge active operator decisions per Kabupaten/Kota",
)
def get_regional_recommendations_endpoint(
    period_id: Optional[str] = Query(None, description="Target Dasarian period ID, e.g. 2026-09-das2"),
    min_coverage_pct: float = Query(50.0, ge=0.0, le=100.0, description="Minimum station coverage percentage"),
):
    from backend.regional_warning_service import compute_regional_recommendations
    try:
        return compute_regional_recommendations(
            period_id=period_id,
            min_coverage_pct=min_coverage_pct,
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Gagal menghitung rekomendasi peringatan wilayah: {e}",
        )


@app.get(
    "/api/v1/warnings/kecamatan/recommendations",
    tags=["Regional Warnings & SIH3 Publication"],
    summary="Compute kecamatan PDKM & PDCHT recommendations across 59 kecamatan of Kepulauan Riau",
)
def get_kecamatan_recommendations_endpoint(
    period_id: Optional[str] = Query(None, description="Target Dasarian period ID, e.g. 2026-09-das2"),
    min_coverage_pct: float = Query(50.0, ge=0.0, le=100.0, description="Minimum station coverage percentage"),
):
    from backend.regional_warning_service import compute_kecamatan_recommendations
    try:
        return compute_kecamatan_recommendations(
            period_id=period_id,
            min_coverage_pct=min_coverage_pct,
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Gagal menghitung rekomendasi tingkat kecamatan: {e}",
        )


@app.get(
    "/api/v1/warnings/regional/decisions",
    tags=["Regional Warnings & SIH3 Publication"],
    summary="Get saved regional operator decisions and audit trail for a given period",
)
def get_regional_decisions_endpoint(
    period_id: Optional[str] = Query(None),
    region_code: Optional[str] = Query(None),
):
    from backend.regional_warning_service import get_regional_decisions_and_audit, resolve_canonical_region
    try:
        res = get_regional_decisions_and_audit(period_id=period_id)
        if region_code:
            reg_meta = resolve_canonical_region(region_code)
            target_rc = reg_meta["region_code"] if reg_meta else region_code
            res["decisions"] = [d for d in res["decisions"] if d.get("region_code") == target_rc]
            res["audit_trail"] = [a for a in res["audit_trail"] if a.get("region_code") == target_rc]
            res["total_decisions"] = len(res["decisions"])
        return res
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Gagal mengambil keputusan peringatan wilayah: {e}",
        )


@app.get(
    "/api/v1/warnings/regional/{region_code}",
    tags=["Regional Warnings & SIH3 Publication"],
    summary="Get detailed regional recommendation, station evidence, and operator decision for a specific Kabupaten/Kota",
)
def get_single_regional_warning_endpoint(
    region_code: str,
    period_id: Optional[str] = Query(None),
    min_coverage_pct: float = Query(50.0, ge=0.0, le=100.0),
):
    from backend.regional_warning_service import (
        compute_regional_recommendations,
        get_regional_decisions_and_audit,
        resolve_canonical_region,
    )
    try:
        canonical = resolve_canonical_region(region_code)
        if not canonical:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Wilayah '{region_code}' tidak ditemukan dalam daftar 7 Kabupaten/Kota Kepulauan Riau.",
            )
        rec_data = compute_regional_recommendations(
            period_id=period_id,
            min_coverage_pct=min_coverage_pct,
        )
        target_reg = next(
            (r for r in rec_data["regions"] if r["region_code"] == canonical["region_code"]),
            None,
        )
        audit_data = get_regional_decisions_and_audit(period_id=rec_data["period_id"])
        reg_decisions = [d for d in audit_data["decisions"] if d.get("region_code") == canonical["region_code"]]
        reg_audits = [a for a in audit_data["audit_trail"] if a.get("region_code") == canonical["region_code"]]
        return {
            "period_id": rec_data["period_id"],
            "evaluation_period": rec_data["evaluation_period"],
            "observation_cutoff_date": rec_data["observation_cutoff_date"],
            "forecast_issue_date": rec_data["forecast_issue_date"],
            "region": target_reg,
            "decisions": reg_decisions,
            "audit_trail": reg_audits,
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Gagal mengambil detail peringatan wilayah {region_code}: {e}",
        )


@app.post(
    "/api/v1/warnings/regional/decision",
    tags=["Regional Warnings & SIH3 Publication"],
    summary="Save or override regional warning decision for a specific region and hazard (PDKM or PDCHT)",
)
def post_regional_warning_decision_endpoint(payload: RegionalWarningDecisionRequest):
    from backend.regional_warning_service import save_regional_warning_decision
    try:
        h_code = payload.hazard_code or payload.hazard_type or ""
        raw_mode = payload.decision_mode or payload.decision_source or "DSS_RECOMMENDATION"
        if raw_mode == "DSS_RECOMMENDED":
            raw_mode = "DSS_RECOMMENDATION"
        with _REGIONAL_WRITE_LOCK:
            return save_regional_warning_decision(
                period_id=payload.period_id or "",
                region_code=payload.region_code,
                hazard_code=h_code,
                decision_mode=raw_mode,
                final_level=payload.final_level,
                override_reason=payload.override_reason,
                analysis_notes=payload.analysis_notes,
                narrative=payload.narrative,
                valid_from=payload.valid_from,
                valid_until=payload.valid_until,
                operator=payload.operator or "klimatkepri",
            )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Gagal menyimpan penetapan peringatan wilayah: {e}",
        )


@app.post(
    "/api/v1/warnings/regional/decisions/bulk-init",
    tags=["Regional Warnings & SIH3 Publication"],
    summary="Confirm and initialize all 7 Kabupaten/Kota decisions from DSS recommendations",
)
def post_regional_bulk_init_endpoint(payload: RegionalBulkInitRequest):
    from backend.regional_warning_service import save_bulk_regional_decisions_from_recommendations
    try:
        with _REGIONAL_WRITE_LOCK:
            return save_bulk_regional_decisions_from_recommendations(
                period_id=payload.period_id or "",
                valid_from=payload.valid_from,
                valid_until=payload.valid_until,
                operator=payload.operator or "klimatkepri",
            )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Gagal menginisialisasi penetapan seluruh wilayah: {e}",
        )


@app.post(
    "/api/v1/publications/sih3/preview",
    tags=["Regional Warnings & SIH3 Publication"],
    summary="Generate preview of SIH3 standardized JSON payload and validate against JSON Schema",
)
def preview_sih3_publication_endpoint(payload: SIH3PublicationPreviewRequest):
    from backend.regional_warning_service import (
        build_sih3_publication_json,
        validate_sih3_json_payload,
        get_sih3_publication_history,
    )
    try:
        history = get_sih3_publication_history(period_id=payload.period_id, limit=1)
        latest_pub = history["items"][0] if history["items"] else None

        pub_status = latest_pub["status"] if latest_pub else "Aktif"
        rev = int(latest_pub["revision"]) if latest_pub else 1

        json_doc = build_sih3_publication_json(
            period_id=payload.period_id,
            valid_from=payload.valid_from or (latest_pub["valid_from"] if latest_pub else None),
            valid_until=payload.valid_until or (latest_pub["valid_until"] if latest_pub else None),
            publication_status=pub_status,
            revision=rev,
            publication_id=latest_pub["publication_id"] if latest_pub else None,
            approved_by=latest_pub.get("approved_by") if latest_pub else None,
            published_by=payload.operator or (latest_pub.get("published_by") if latest_pub else None),
            published_at_iso=latest_pub.get("published_at") if latest_pub else None,
            revision_reason=latest_pub.get("revision_reason") if latest_pub else None,
        )
        validation = validate_sih3_json_payload(json_doc)
        return {
            "status": "SUCCESS",
            "period_id": json_doc["source"]["period_id"],
            "validation": validation,
            "payload": json_doc,
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Gagal membuat preview JSON SIH3: {e}",
        )


@app.post(
    "/api/v1/publications/sih3/validate",
    tags=["Regional Warnings & SIH3 Publication"],
    summary="Validate an explicit or generated SIH3 JSON payload against sih3_regional_warning.schema.json",
)
def validate_sih3_publication_endpoint(req: SIH3ValidatePayloadRequest):
    from backend.regional_warning_service import (
        build_sih3_publication_json,
        validate_sih3_json_payload,
    )
    try:
        if req.payload is not None:
            target_doc = req.payload
        else:
            target_doc = build_sih3_publication_json(
                period_id=req.period_id,
                valid_from=req.valid_from,
                valid_until=req.valid_until,
                publication_status="Aktif",
                revision=1,
            )
        validation = validate_sih3_json_payload(target_doc)
        return {
            "status": "VALID" if validation["valid"] else "INVALID",
            "validation": validation,
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Gagal memvalidasi JSON SIH3: {e}",
        )


@app.post(
    "/api/v1/publications/sih3/workflow",
    tags=["Regional Warnings & SIH3 Publication"],
    summary="Execute SIH3 publication workflow transition (SAVE_DRAFT, SUBMIT_REVIEW, APPROVE, PUBLISH)",
)
def execute_sih3_workflow_endpoint(req: SIH3WorkflowActionRequest):
    from backend.regional_warning_service import execute_publication_workflow
    try:
        return execute_publication_workflow(
            period_id=req.period_id or "",
            action=req.action,
            valid_from=req.valid_from,
            valid_until=req.valid_until,
            operator=req.operator or "klimatkepri",
            revision_reason=req.revision_reason or req.notes,
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Gagal menjalankan workflow publikasi SIH3: {e}",
        )


@app.post(
    "/api/v1/publications/sih3/publish",
    tags=["Regional Warnings & SIH3 Publication"],
    summary="Publish an APPROVED SIH3 warning snapshot to public storage and latest.json",
)
def publish_sih3_warning_endpoint(req: SIH3WorkflowActionRequest):
    from backend.regional_warning_service import execute_publication_workflow
    try:
        return execute_publication_workflow(
            period_id=req.period_id or "",
            action="PUBLISH",
            valid_from=req.valid_from,
            valid_until=req.valid_until,
            operator=req.operator or "klimatkepri",
            revision_reason=req.revision_reason or req.notes,
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Gagal menerbitkan JSON SIH3: {e}",
        )


@app.get(
    "/api/v1/publications/sih3/history",
    tags=["Regional Warnings & SIH3 Publication"],
    summary="List SIH3 publication workflow revisions and history",
)
def get_sih3_publication_history_endpoint(
    period_id: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=200),
):
    from backend.regional_warning_service import get_sih3_publication_history
    try:
        return get_sih3_publication_history(period_id=period_id, limit=limit)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Gagal mengambil riwayat publikasi SIH3: {e}",
        )


@app.get(
    "/api/v1/publications/sih3/latest.json",
    tags=["Regional Warnings & SIH3 Publication"],
    summary="Read-only public endpoint returning the latest PUBLISHED SIH3 Regional Warning JSON for WordPress integration",
)
def get_latest_published_sih3_json_endpoint(
    period_id: Optional[str] = Query(None, description="Optional period filter (returns only PUBLISHED)"),
):
    from backend.regional_warning_service import get_latest_published_sih3_json
    try:
        doc = get_latest_published_sih3_json(period_id=period_id)
        return JSONResponse(
            content=doc,
            headers={
                "Cache-Control": "public, max-age=60",
                "Access-Control-Allow-Origin": "*",
            },
        )
    except LookupError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Gagal mengambil publikasi SIH3 terbaru: {e}",
        )


@app.get(
    "/api/v1/publications/sih3/{publication_id}/json",
    tags=["Regional Warnings & SIH3 Publication"],
    summary="Download or inspect a specific SIH3 publication snapshot JSON by publication_id",
)
def get_sih3_publication_by_id_endpoint(
    publication_id: str,
    revision: Optional[int] = Query(None),
):
    from backend.regional_warning_service import get_sih3_publication_json_by_id
    try:
        return get_sih3_publication_json_by_id(publication_id, revision=revision)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Gagal mengambil JSON publikasi '{publication_id}': {e}",
        )



# ==============================================================================
# MANUAL SPI GENERATOR ENDPOINTS
# ==============================================================================
from pydantic import BaseModel

class SpiGeneratorPreviewRequest(BaseModel):
    resolution: str  # 'HARIAN', 'DASARIAN', 'BULANAN'
    timescale: int   # 30 or 90
    selected_stations: Optional[List[str]] = None
    output_start_date: Optional[str] = None
    output_end_date: Optional[str] = None

class SpiGeneratorExecuteRequest(BaseModel):
    resolution: str
    timescale: int
    selected_stations: Optional[List[str]] = None
    output_start_date: Optional[str] = None
    output_end_date: Optional[str] = None
    n_workers: Optional[int] = 4

class SpiGeneratorCommitRequest(BaseModel):
    session_token: str
    operator_notes: Optional[str] = "Pembaruan SPI otomatis via SPI Generator"

@app.get(
    "/api/v1/spi/generator/options",
    tags=["SPI Generator"],
    summary="Get configuration options and stations readiness for SPI Generator"
)
def get_spi_generator_options_endpoint(
    current_user: Optional[Dict[str, Any]] = Depends(get_current_user)
):
    from backend.spi_calculation_service import get_generator_readiness_options
    try:
        return get_generator_readiness_options()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Gagal mengambil opsi generator: {e}")

@app.post(
    "/api/v1/spi/generator/preview",
    tags=["SPI Generator"],
    summary="Preview SPI calculation feasibility before execution"
)
def post_spi_generator_preview_endpoint(
    req: SpiGeneratorPreviewRequest,
    current_user: Optional[Dict[str, Any]] = Depends(get_current_user)
):
    from backend.spi_calculation_service import prepare_spi_preview_summary
    try:
        return prepare_spi_preview_summary(
            resolution=req.resolution,
            timescale=req.timescale,
            selected_stations=req.selected_stations,
            output_start_date=req.output_start_date,
            output_end_date=req.output_end_date
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.post(
    "/api/v1/spi/generator/execute",
    tags=["SPI Generator"],
    summary="Run parallel SPI calculation using Joblib and store in staging session"
)
def post_spi_generator_execute_endpoint(
    req: SpiGeneratorExecuteRequest,
    current_user: Optional[Dict[str, Any]] = Depends(get_current_user)
):
    from backend.spi_calculation_service import execute_spi_generation
    try:
        return execute_spi_generation(
            resolution=req.resolution,
            timescale=req.timescale,
            selected_stations=req.selected_stations,
            output_start_date=req.output_start_date,
            output_end_date=req.output_end_date,
            n_workers=req.n_workers or 4
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Kalkulasi SPI gagal: {e}")

@app.post(
    "/api/v1/spi/generator/commit",
    tags=["SPI Generator"],
    summary="Atomically commit staged SPI calculation into canonical Parquet storage"
)
def post_spi_generator_commit_endpoint(
    req: SpiGeneratorCommitRequest,
    current_user: Optional[Dict[str, Any]] = Depends(get_current_user)
):
    from backend.spi_calculation_service import commit_spi_generation_session
    try:
        return commit_spi_generation_session(
            session_token=req.session_token,
            operator_notes=req.operator_notes
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Gagal commit hasil SPI: {e}")


# ==============================================================================
# RAINFALL DATA INPUT MODULE V2 (AUTO TEMPLATE DETECTION, MULTI-FORMAT & MANUAL)
# ==============================================================================
@app.get(
    "/api/v1/rainfall/v2/regencies",
    tags=["Rainfall Input V2"],
    summary="List 7 Kepri regencies with template support matrix and master stations",
)
def rainfall_v2_regencies():
    from backend.rainfall_ingestion_v2 import get_regencies_metadata
    try:
        return {"regencies": get_regencies_metadata()}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Gagal memuat daftar wilayah: {e}")


@app.post(
    "/api/v1/rainfall/v2/detect",
    tags=["Rainfall Input V2"],
    summary="Upload one or more Excel files for a regency and run automatic template detection",
)
async def rainfall_v2_detect(
    regency_code: str = Form(..., description="Regency code: KARIMUN, LINGGA, NATUNA, ANAMBAS, BATAM, BINTAN, TANJUNGPINANG"),
    files: List[UploadFile] = File(..., description="One or more Excel files (.xlsx, .xlsm)"),
):
    from backend.rainfall_ingestion_v2 import create_detect_batch_session
    try:
        payload = []
        for f in files:
            content = await f.read()
            payload.append((f.filename or "uploaded.xlsx", content))
        return create_detect_batch_session(regency_code=regency_code, files_payload=payload)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Gagal mendeteksi format berkas: {e}")


@app.get(
    "/api/v1/rainfall/v2/profiles",
    tags=["Rainfall Input V2"],
    summary="List saved custom rainfall template profiles",
)
def rainfall_v2_list_profiles(regency_code: Optional[str] = Query(None)):
    from backend.rainfall_ingestion_v2 import list_template_profiles
    try:
        return {"profiles": list_template_profiles(regency_code=regency_code)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Gagal memuat profil template: {e}")


@app.post(
    "/api/v1/rainfall/v2/profiles",
    tags=["Rainfall Input V2"],
    summary="Save a new persistent custom template mapping profile and optional station aliases",
)
def rainfall_v2_save_profile(payload: Dict[str, Any]):
    from backend.rainfall_ingestion_v2 import save_template_profile
    try:
        return save_template_profile(
            profile_name=payload.get("profile_name", "Profil Kustom"),
            regency_code=payload["regency_code"],
            structure_fingerprint=payload["structure_fingerprint"],
            sheet_rules=payload.get("sheet_rules", {}),
            header_config=payload.get("header_config", {}),
            date_config=payload.get("date_config", {}),
            value_config=payload.get("value_config", {}),
            station_config=payload.get("station_config", {}),
            ignored_columns=payload.get("ignored_columns", []),
            symbol_mapping=payload.get("symbol_mapping", {}),
            station_aliases=payload.get("station_aliases"),
            operator=payload.get("operator", "OPERATOR_BMKG"),
        )
    except (KeyError, ValueError) as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Gagal menyimpan profil template: {e}")


@app.post(
    "/api/v1/rainfall/v2/preview",
    tags=["Rainfall Input V2"],
    summary="Parse selected files with confirmed periods and compare against MariaDB",
)
def rainfall_v2_preview(payload: Dict[str, Any]):
    from backend.rainfall_ingestion_v2 import preview_batch_session
    try:
        return preview_batch_session(
            batch_session_id=payload["batch_session_id"],
            file_configs=payload.get("files", []),
        )
    except (KeyError, ValueError) as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Gagal membuat pratinjau batch: {e}")


@app.post(
    "/api/v1/rainfall/v2/commit",
    tags=["Rainfall Input V2"],
    summary="Atomically commit previewed rainfall batch to MariaDB with audit logging",
)
def rainfall_v2_commit(payload: Dict[str, Any]):
    from backend.rainfall_ingestion_v2 import commit_batch_session
    try:
        return commit_batch_session(
            batch_session_id=payload["batch_session_id"],
            confirm_conflicts=bool(payload.get("confirm_conflicts", False)),
            correction_reason=payload.get("correction_reason", ""),
            operator=payload.get("operator") or "OPERATOR_BMKG",
        )
    except (KeyError, ValueError) as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Gagal menyimpan batch curah hujan: {e}")


@app.post(
    "/api/v1/rainfall/v2/manual/preview",
    tags=["Rainfall Input V2"],
    summary="Validate and preview multi-date manual rainfall input for a station",
)
def rainfall_v2_manual_preview(payload: Dict[str, Any]):
    from backend.rainfall_ingestion_v2 import preview_manual_input_v2
    try:
        return preview_manual_input_v2(
            regency_code=payload["regency_code"],
            station_id=payload["station_id"],
            rows=payload.get("rows", []),
        )
    except (KeyError, ValueError) as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Gagal memvalidasi input manual: {e}")


@app.post(
    "/api/v1/rainfall/v2/manual/commit",
    tags=["Rainfall Input V2"],
    summary="Atomically commit validated multi-date manual rainfall input to MariaDB",
)
def rainfall_v2_manual_commit(payload: Dict[str, Any]):
    from backend.rainfall_ingestion_v2 import commit_manual_input_v2
    try:
        return commit_manual_input_v2(
            regency_code=payload["regency_code"],
            station_id=payload["station_id"],
            rows=payload.get("rows", []),
            confirm_conflicts=bool(payload.get("confirm_conflicts", False)),
            correction_reason=payload.get("correction_reason", ""),
            operator=payload.get("operator") or "OPERATOR_BMKG",
            baseline_fingerprint=payload.get("baseline_fingerprint"),
        )
    except (KeyError, ValueError) as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Gagal menyimpan input manual: {e}")


# ==============================================================================
# PRODUCTION SPA STATIC SERVING (Served only when CEWS_SERVE_FRONTEND=true)
# ==============================================================================
if SERVE_FRONTEND:
    from fastapi.staticfiles import StaticFiles
    from fastapi.responses import FileResponse

    _FRONTEND_DIST = Path(__file__).resolve().parent.parent / "frontend" / "dist"
    _ASSETS_DIR = _FRONTEND_DIST / "assets"
    if _ASSETS_DIR.exists():
        app.mount("/assets", StaticFiles(directory=str(_ASSETS_DIR)), name="frontend_assets")

    @app.get("/{full_path:path}", include_in_schema=False)
    def serve_spa_fallback(full_path: str):
        if full_path.startswith("api/") or full_path in ("health", "docs", "redoc", "openapi.json"):
            raise HTTPException(status_code=404, detail="Not found")
        candidate = _FRONTEND_DIST / full_path
        if full_path and candidate.is_file():
            return FileResponse(str(candidate))
        index_file = _FRONTEND_DIST / "index.html"
        if index_file.exists():
            return FileResponse(
                str(index_file),
                headers={"Cache-Control": "no-cache, no-store, must-revalidate"},
            )
        raise HTTPException(status_code=404, detail="Frontend production build not found. Run 'npm --prefix frontend run build'.")
