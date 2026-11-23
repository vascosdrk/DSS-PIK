"""
Pydantic Schemas for CEWS Backend API (v1.1 Frozen)
Climate Early Warning System (CEWS) BMKG Kepulauan Riau
"""

from typing import List, Optional, Any, Dict
from pydantic import BaseModel, Field


class HealthResponse(BaseModel):
    status: str = "ok"
    service: str = "cews-api"
    database: str = "connected"


class CurrentWarningItem(BaseModel):
    station_id: str
    station_name: str
    kabupaten: str
    latitude: float
    longitude: float
    target_warning_period: str
    target_period_start: str
    target_period_end: str
    hazard_type: str
    warning_level: str
    confidence_level: str
    data_quality_status: str
    updated_at: str
    is_arg: bool = False
    evaluation_status: str = "COMPLETE"
    prev_dasarian_rainfall_mm: Optional[float] = None
    prev_dasarian_label: Optional[str] = None
    spi_value: Optional[float] = None
    spi_value_90d: Optional[float] = None
    spi_evidence_date: Optional[str] = None
    spi_validation_status: Optional[str] = None
    spi_validation_status_90d: Optional[str] = None


class CurrentWarningMeta(BaseModel):
    total: int
    period_id: str = "2026-09-das2"
    period_label: Optional[str] = "Dasarian II September 2026"
    date_range: Optional[str] = "11–20 September 2026"
    dataset_type: str = "operational_simulation"
    observation_cutoff: str = "2026-09-10"
    forecast_issue: str = "2026-09-09"
    target_period_start: str = "2026-09-11"
    target_period_end: str = "2026-09-20"
    prev_dasarian_label: Optional[str] = "CH Das I Sep (mm)"


class CurrentWarningResponse(BaseModel):
    meta: CurrentWarningMeta
    data: List[CurrentWarningItem]


class PeriodSummary(BaseModel):
    total: int
    awas: int
    siaga: int
    waspada: int
    aman: int
    incomplete: int


class PeriodItem(BaseModel):
    period_id: str
    label: str
    date_range: str
    target_start: str
    target_end: str
    observation_cutoff: str
    forecast_issue: str
    prev_dasarian_label: str
    is_default: bool = False
    is_forecast: bool = False
    has_complete_data: bool = True
    has_snapshot: bool = True
    summary: PeriodSummary


class PeriodsResponse(BaseModel):
    active_period_id: str = "2026-09-das2"
    mode: str = "auto"
    server_time: Optional[str] = None
    server_date: Optional[str] = None
    total_periods: int = 10
    periods: List[PeriodItem]


class PeriodSelectRequest(BaseModel):
    mode: str = "auto"
    period_id: Optional[str] = None


class ForecastEvidenceItem(BaseModel):
    forecast_parameter: str
    probability_value: float
    issue_date: str
    source_file: str


class NearestStationItem(BaseModel):
    station_id: str
    station_name: str
    kabupaten: str
    distance_km: float
    hth_days_current: Optional[int] = None
    warning_level: str
    data_quality_status: str
    last_rain_date: Optional[str] = None


class StationDetailResponse(BaseModel):
    station_id: str
    station_name: str
    kabupaten: str
    province: str
    region: str
    latitude: float
    longitude: float
    elevation_m: Optional[float] = None
    nozom_prov: Optional[str] = None

    target_year: int
    target_month: int
    target_dasarian: int
    target_warning_period: str
    target_period_start: str
    target_period_end: str

    hazard_type: str
    warning_level: str
    pdkm_status: Optional[str] = "NORMAL"
    pdkm_level: Optional[int] = 0
    pdkm_reasons: Optional[str] = None
    pdcht_status: Optional[str] = "NORMAL"
    pdcht_level: Optional[int] = 0
    pdcht_reasons: Optional[str] = None
    trigger_reason: str
    confidence_level: str
    data_quality_status: str

    spi_condition: str
    probability_support: bool
    hth_days_current: int
    hth_uncertain: bool

    spi_value: Optional[float] = None
    spi_value_90d: Optional[float] = None
    spi_condition_90d: Optional[str] = None
    spi_evidence_date: Optional[str] = None
    spi_validation_status: Optional[str] = None
    spi_validation_status_90d: Optional[str] = None
    spi_daily_30d: Optional[float] = None
    spi_daily_90d: Optional[float] = None
    spi_daily_evidence_date: Optional[str] = None
    spi_daily_condition: Optional[str] = None
    spi_monthly_value: Optional[float] = None
    spi_monthly_evidence_month: Optional[str] = None
    spi_monthly_condition: Optional[str] = None
    prob_below20: Optional[float] = None
    prob_ch_lt20_dasarian_1: Optional[float] = None
    prob_ch_lt20_dasarian_2: Optional[float] = None
    prob_above150: Optional[float] = None
    prob_above200: Optional[float] = None
    prob_above300: Optional[float] = None
    prob_month_above300: Optional[float] = None
    prob_month_above400: Optional[float] = None
    prob_month_above500: Optional[float] = None

    last_observation_period: str
    last_observation_date: str
    updated_at: str

    is_arg: bool = False
    evaluation_status: str = "COMPLETE"
    ch_dasarian_2_mm: Optional[float] = None
    prev_dasarian_rainfall_mm: Optional[float] = None
    prev_dasarian_label: Optional[str] = None
    narrative: Optional[str] = None

    forecast_evidence: List[ForecastEvidenceItem] = Field(default_factory=list)
    nearest_stations: List[NearestStationItem] = Field(default_factory=list)


class WarningHistoryItem(BaseModel):
    station_id: str
    period_start: str
    period_end: str
    year: int
    month: int
    dasarian: int
    hazard_type: str
    warning_level: str
    trigger_reason: str
    spi_condition: str
    probability_support: bool
    data_quality_status: str
    confidence_level: str
    hth_days_max: int
    hth_uncertain: bool
    spi_value: Optional[float] = None
    prob_below20: Optional[float] = None
    prob_ch_lt20_dasarian_1: Optional[float] = None
    prob_ch_lt20_dasarian_2: Optional[float] = None
    prob_above150: Optional[float] = None
    prob_above200: Optional[float] = None
    prob_above300: Optional[float] = None
    prob_month_above300: Optional[float] = None
    prob_month_above400: Optional[float] = None
    prob_month_above500: Optional[float] = None
    evaluated_at: str


class WarningHistoryResponse(BaseModel):
    station_id: str
    station_name: str
    kabupaten: str
    total_records: int
    data: List[WarningHistoryItem]


# ==============================================================================
# HTH TABLE & EVALUATION SCHEMAS (TAHAP 5 REFINEMENT)
# ==============================================================================

class HthTableItem(BaseModel):
    station_id: str
    station_name: str
    kabupaten: str
    hth_days_current: Optional[int] = None
    hth_category: Optional[str] = None
    hth_uncertain: bool = False
    warning_level: str
    hazard_type: str = "NORMAL"
    pdkm_status: Optional[str] = "NORMAL"
    pdkm_level: Optional[int] = 0
    pdkm_reasons: Optional[str] = None
    pdcht_status: Optional[str] = "NORMAL"
    pdcht_level: Optional[int] = 0
    pdcht_reasons: Optional[str] = None
    data_quality_status: str = "VALID"
    confidence_level: Optional[str] = "MEDIUM"
    last_observation_date: str
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    last_rain_date: Optional[str] = None
    ch_dasarian_2_mm: Optional[float] = None
    prev_dasarian_rainfall_mm: Optional[float] = None
    prev_dasarian_label: Optional[str] = None
    is_arg: bool = False
    evaluation_status: str = "COMPLETE"
    station_type: Optional[str] = "Pos Hujan Manual"
    spi_value: Optional[float] = None
    spi_value_90d: Optional[float] = None
    spi_condition_90d: Optional[str] = None
    spi_evidence_date: Optional[str] = None
    spi_validation_status: Optional[str] = None
    spi_validation_status_90d: Optional[str] = None
    spi_daily_30d: Optional[float] = None
    spi_daily_90d: Optional[float] = None
    spi_daily_evidence_date: Optional[str] = None
    spi_daily_condition: Optional[str] = None
    spi_monthly_value: Optional[float] = None
    spi_monthly_evidence_month: Optional[str] = None
    spi_monthly_condition: Optional[str] = None
    prob_below20: Optional[float] = None
    prob_above150: Optional[float] = None
    prob_above200: Optional[float] = None
    prob_above300: Optional[float] = None
    prob_month_above300: Optional[float] = None
    prob_month_above400: Optional[float] = None
    prob_month_above500: Optional[float] = None
    trigger_reason: Optional[str] = None


class HthTableMeta(BaseModel):
    total: int
    observation_cutoff: str = "2026-09-10"
    period_id: Optional[str] = "2026-09-das2"
    period_label: Optional[str] = "Dasarian II September 2026"
    prev_dasarian_label: Optional[str] = "CH Das I Sep (mm)"


class HthTableResponse(BaseModel):
    meta: HthTableMeta
    data: List[HthTableItem]



class HthDiagnostic(BaseModel):
    current_warning_hth: Optional[int] = None
    pipeline_hth: Optional[int] = None
    match: bool
    last_rain_date: Optional[str] = None
    days_since_last_rain: Optional[int] = None
    missing_observation_days: int = 0
    source_period_start: str = "2026-08-01"
    source_period_end: str = "2026-08-25"


class MappingDiagnostic(BaseModel):
    station_match: bool
    coordinate_match: bool


class EvaluationStationInfo(BaseModel):
    station_id: str
    station_name: str
    kabupaten: str
    latitude: float
    longitude: float


class EvaluationCurrentState(BaseModel):
    warning_level: str
    hazard_type: str
    hth_days_current: Optional[int] = None
    hth_uncertain: bool = False
    data_quality_status: str = "VALID"
    confidence_level: str = "MEDIUM"
    last_observation_date: str = "2026-08-25"


class DailyRainfallItem(BaseModel):
    date: str
    rainfall_mm: float
    is_missing: bool
    hth_days: int


class EvaluationObservationDiagnostics(BaseModel):
    latest_hth_pipeline_value: Optional[int] = None
    last_rain_date: Optional[str] = None
    missing_observation_days: int = 0
    source_available: bool = True
    recent_rainfall: List[DailyRainfallItem] = Field(default_factory=list)


class EvaluationResult(BaseModel):
    status: str  # "CONSISTENT" | "REVIEW_REQUIRED" | "INSUFFICIENT_DATA"
    reasons: List[str]



class StationEvaluationResponse(BaseModel):
    station: EvaluationStationInfo
    current_state: EvaluationCurrentState
    hth_diagnostic: HthDiagnostic
    mapping_diagnostic: MappingDiagnostic
    nearest_stations: List[NearestStationItem]
    evaluation: EvaluationResult
    observation_diagnostics: Optional[EvaluationObservationDiagnostics] = None


# ==============================================================================
# RAINFALL DAILY TABLE SCHEMAS (MIRRORING HARIAN SHEET)
# ==============================================================================
class RainfallColumnItem(BaseModel):
    col_idx: int
    region: str
    harian_name: str
    station_id: str
    master_name: Optional[str] = None
    in_master_57: bool = True
    notes: Optional[str] = None


class RainfallColumnsResponse(BaseModel):
    total_columns: int
    date_columns: List[str] = ["Tahun", "Bulan", "Tanggal", "Dasarian"]
    station_columns: List[RainfallColumnItem]


class RainfallCell(BaseModel):
    rainfall_mm: Optional[float] = None
    obs_status: str  # OBSERVED_VALID, OBSERVED_ZERO, TTU, MISSING
    original_symbol: Optional[str] = None


class RainfallDailyRow(BaseModel):
    date: str
    year: int
    month: int
    day: int
    dasarian: int
    stations: dict  # Dict[station_id, RainfallCell]


class RainfallDailyTableMeta(BaseModel):
    total_records: int
    page: int
    page_size: int
    total_pages: int
    year: Optional[int] = None
    month: Optional[int] = None
    dasarian: Optional[int] = None
    start_date: Optional[str] = None
    end_date: Optional[str] = None


class RainfallDailyTableResponse(BaseModel):
    meta: RainfallDailyTableMeta
    columns: List[RainfallColumnItem]
    data: List[RainfallDailyRow]


# ==============================================================================
# RAINFALL HISTORY & INPUT SCHEMAS
# ==============================================================================
class RainfallHistoryRecordItem(BaseModel):
    date: str
    rainfall_mm: Optional[float] = None
    status: str
    obs_status: Optional[str] = None
    original_symbol: Optional[str] = None
    hth_days: int


class RainfallHistoryResponse(BaseModel):
    station_id: str
    station_name: str
    kabupaten: str
    period_start: Optional[str] = None
    period_end: Optional[str] = None
    total_days: int
    is_custom_range: bool = False
    cutoff_date: Optional[str] = None
    data: List[RainfallHistoryRecordItem]


class RainfallStationMasterItem(BaseModel):
    station_id: str
    station_name: str
    kabupaten: str
    regency: Optional[str] = None
    province: Optional[str] = None
    region: Optional[str] = None
    latitude: float
    longitude: float
    elevation_m: Optional[float] = None
    station_type: Optional[str] = "Pos Hujan Manual"
    is_arg: bool = False
    nozom_prov: Optional[str] = None


class RainfallStationsResponse(BaseModel):
    total: int
    source_file: str = "station_metadata.parquet"
    stations: List[RainfallStationMasterItem]


class RainfallInputEntry(BaseModel):
    station_id: str
    observation_date: str
    rainfall_mm: Optional[float] = None
    obs_status: str = "OBSERVED_VALID"
    original_symbol: Optional[str] = None


class RainfallInputPreviewItem(BaseModel):
    station_id: str
    station_name: Optional[str] = None
    date: str
    category: str  # NEW, IDENTICAL, DIFF, INVALID
    old_value: Optional[float] = None
    new_value: Optional[float] = None
    old_status: Optional[str] = None
    new_status: Optional[str] = None
    reason: Optional[str] = None


class RainfallInputPreviewRequest(BaseModel):
    mode: str = "DAILY"  # DAILY or DASARIAN
    entries: List[RainfallInputEntry]


class RainfallInputPreviewResponse(BaseModel):
    total_submitted: int
    total_valid: int
    total_new: int
    total_identical: int
    total_diff: int
    total_invalid: int
    items: List[RainfallInputPreviewItem]


class RainfallInputCommitRequest(BaseModel):
    batch_id: str
    entries: List[RainfallInputEntry]
    confirm_overwrite: bool = False
    correction_reason: Optional[str] = "Input data observasi manual"
    approved_by: Optional[str] = "OPERATOR_CEWS"


class RainfallInputCommitResponse(BaseModel):
    success: bool
    batch_id: str
    total_saved: int
    new_count: int
    corrected_count: int
    skipped_identical_count: int
    message: str


# ==============================================================================
# AUTHENTICATION SCHEMAS (TAHAP 3)
# ==============================================================================
class LoginRequest(BaseModel):
    username: str
    password: str


class LoginResponse(BaseModel):
    success: bool
    username: str
    role: str = "OPERATOR_CEWS"
    token: Optional[str] = None
    message: str


class UserMeResponse(BaseModel):
    authenticated: bool
    username: str
    role: str = "OPERATOR_CEWS"
    token: Optional[str] = None
    message: Optional[str] = None


class LogoutResponse(BaseModel):
    success: bool
    message: str


# ==============================================================================
# DATA CENTER & DOWNLOAD SCHEMAS
# ==============================================================================
class StationDetailedInfoResponse(BaseModel):
    station_id: str
    station_name: str
    station_type: str
    is_arg: bool
    kabupaten: str
    province: str
    latitude: float
    longitude: float
    elevation_m: Optional[float] = None
    nozom_prov: Optional[str] = None
    first_observation_date: Optional[str] = None
    last_observation_date: Optional[str] = None
    operating_calendar_days: int
    total_records: int
    valid_count: int
    rain_days_count: int
    dry_days_count: int
    dry_zero_days_count: Optional[int] = 0
    dry_sub1mm_days_count: Optional[int] = 0
    ttu_count: int
    explicit_missing_count: Optional[int] = 0
    unrecorded_days_count: Optional[int] = 0
    missing_count: int
    completeness_pct: float
    running_hth: Optional[int] = None
    hth_uncertain: Optional[bool] = False
    last_rain_date: Optional[str] = None


# ==============================================================================
# OFFICIAL MAP GENERATION SCHEMAS (PAKET 4 & FINAL REFINEMENT)
# ==============================================================================
class RegencyDecisionDetail(BaseModel):
    warning_type: Optional[str] = Field(None, description="PDKM, PDCHT, or None")
    classification: str = Field("AMAN", description="WASPADA, SIAGA, AWAS, AMAN, or INSUFFICIENT_DATA")
    override_reason: Optional[str] = Field(None, description="Operator override justification")


class MapGenerateRequest(BaseModel):
    map_type: str = Field("UNIFIED", description="UNIFIED, PDKM, or PDCHT")
    period_id: str = Field(..., description="Target Period ID e.g. 2026-09-das2")
    regency_status: Optional[Dict[str, str]] = Field(default_factory=dict, description="Status per Regency (legacy flat format)")
    regency_decisions: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Per-regency hazard and classification decisions")
    kecamatan_decisions: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Per-kecamatan hazard and classification decisions (59 kecamatan)")
    operator_name: Optional[str] = Field("Petugas Operasional", description="Name of operator generating map")
    notes: Optional[str] = Field(None, description="Optional operational notes")


class MapGenerateResponse(BaseModel):
    success: bool
    map_type: str
    period_id: str
    period_title: str
    jpg_url: Optional[str] = None
    jpg_filename: Optional[str] = None
    download_jpg_url: Optional[str] = None
    png_url: Optional[str] = None
    pdf_url: Optional[str] = None
    png_filename: Optional[str] = None
    pdf_filename: Optional[str] = None
    metadata_filename: str
    created_at: str
    operator_name: str
    regency_status: Dict[str, Any]
    message: str


class MapJsonExportRequest(BaseModel):
    period_id: str = Field(..., description="Target Period ID e.g. 2026-09-das2")
    scope: str = Field("GABUNGAN", description="Lingkup JSON: GABUNGAN | PDKM | PDCHT")
    pdkm_status: Dict[str, str] = Field(default_factory=dict, description="Status PDKM 7 wilayah (BINTAN, KARIMUN, ...)")
    pdcht_status: Dict[str, str] = Field(default_factory=dict, description="Status PDCHT 7 wilayah (BINTAN, KARIMUN, ...)")
    regency_decisions: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Per-regency unified decisions (warning_type, classification, override_reason)")
    kecamatan_decisions: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Per-kecamatan unified decisions (59 kecamatan)")
    override_reasons: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Alasan override per wilayah/hazard")
    analysis_notes: Optional[str] = Field(None, description="Catatan operasional operator")
    valid_from: Optional[str] = Field(None, description="Masa berlaku mulai (YYYY-MM-DD)")
    valid_until: Optional[str] = Field(None, description="Masa berlaku akhir (YYYY-MM-DD)")
    operator_name: Optional[str] = Field("Petugas Operasional", description="Nama operator")
    publish: bool = Field(False, description="Apakah sekaligus mempublikasikan status ke SIH3?")


class MapJsonExportResponse(BaseModel):
    success: bool
    scope: str
    publication_id: str
    validation: Dict[str, Any]
    summary: Dict[str, Any]
    payload: Dict[str, Any]
    download_filename: str
    json_url: str
    message: Optional[str] = "JSON SIH3 berhasil dibuat dan tervalidasi"


# ==============================================================================
# PERIOD READINESS SCHEMAS (PAKET 2)
# ==============================================================================
class PeriodReadinessResponse(BaseModel):
    active_period_id: str
    active_period_label: str
    active_period_range: Optional[str] = None
    candidate_period_id: Optional[str] = None
    candidate_period_label: Optional[str] = None
    observation_cutoff_date: Optional[str] = None
    spi_target_date: Optional[str] = None
    forecast_issue_date: Optional[str] = None
    total_stations: int
    stations_with_data_on_cutoff: int
    stations_with_missing_on_cutoff: int
    cutoff_status_counts: Dict[str, int]
    spi_30d_available: bool
    spi_90d_available: bool
    forecast_available: bool
    evaluation_readiness_status: str  # "READY", "PARTIAL", "LAGGING", "NOT_READY"
    readiness_reasons: List[str]
    selection_mode: Optional[str] = "auto"
    server_time: Optional[str] = None
    latest_observation_date: Optional[str] = None
    latest_observation_station_count: Optional[int] = 0
    coverage_percentage: Optional[float] = 0.0
    is_lagging: Optional[bool] = False
    warning_message: Optional[str] = None


class SpiColumnItem(BaseModel):
    station_id: str
    station_name: str
    kabupaten: str
    is_arg: bool
    has_spi: bool
    status: str


class SpiTableMeta(BaseModel):
    period_type: str
    timescale: str
    total_records: int
    page: int
    page_size: int
    total_pages: int
    order: str
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    station_id: Optional[str] = None


class SpiRowItem(BaseModel):
    date: str
    stations: Dict[str, Optional[float]]


class SpiTableResponse(BaseModel):
    meta: SpiTableMeta
    columns: List[SpiColumnItem]
    data: List[SpiRowItem]


class ProbabilityItem(BaseModel):
    period_id: str
    station_id: str
    station_name: str
    kabupaten: str
    is_arg: bool
    forecast_issue: str
    target_start: str
    target_end: str
    prob_below20: Optional[float] = None
    prob_above150: Optional[float] = None
    prob_above200: Optional[float] = None
    prob_above300: Optional[float] = None
    prob_month_above300: Optional[float] = None
    prob_month_above400: Optional[float] = None
    prob_month_above500: Optional[float] = None
    source: str = "ECMWF Ensemble Probability"


class ProbabilityTableMeta(BaseModel):
    period_id: str
    station_id: Optional[str] = None
    total_records: int
    page: int
    page_size: int
    total_pages: int
    resolution: Optional[str] = None
    active_vintage_issue: Optional[str] = None
    available_vintages: List[str] = Field(default_factory=list)
    available_stations_count: Optional[int] = None


class ProbabilityTableResponse(BaseModel):
    meta: ProbabilityTableMeta
    data: List[ProbabilityItem]


# ==============================================================================
# SPI TREND & INGESTION SCHEMAS
# ==============================================================================
class SpiTrendThresholds(BaseModel):
    kering: float = -1.00
    sangat_kering: float = -1.50
    ekstrem_kering: float = -2.00


class SpiTrendHarianData(BaseModel):
    dates: List[str] = Field(default_factory=list)
    spi_30d: List[Optional[float]] = Field(default_factory=list)
    spi_90d: List[Optional[float]] = Field(default_factory=list)


class SpiTrendDasarianData(BaseModel):
    dates: List[str] = Field(default_factory=list)
    spi_30d: List[Optional[float]] = Field(default_factory=list)
    spi_90d: List[Optional[float]] = Field(default_factory=list)


class SpiTrendBulananData(BaseModel):
    dates: List[str] = Field(default_factory=list)
    spi: List[Optional[float]] = Field(default_factory=list)


class StationSpiTrendResponse(BaseModel):
    station_id: str
    station_name: str
    is_arg: bool = False
    message: Optional[str] = None
    harian: SpiTrendHarianData
    dasarian: SpiTrendDasarianData
    bulanan: SpiTrendBulananData
    thresholds: SpiTrendThresholds = Field(default_factory=SpiTrendThresholds)


class IngestionPreviewSummary(BaseModel):
    total_rows: int
    total_stations_recognized: int
    total_stations_unrecognized: int
    stations_recognized: List[str] = Field(default_factory=list)
    unrecognized_stations: List[Any] = Field(default_factory=list)
    date_range: Optional[Dict[str, Optional[str]]] = None
    total_new: int = 0
    total_new_vintage: int = 0
    total_updated: int = 0
    total_identical: int = 0
    total_duplicate: int = 0
    total_missing: int = 0
    total_damaged: int = 0
    total_ambiguous: int = 0
    total_invalid: int = 0
    periods_detected: List[Dict[str, Any]] = Field(default_factory=list)
    regency_counts: Dict[str, int] = Field(default_factory=dict)
    station_gaps: List[Dict[str, Any]] = Field(default_factory=list)
    counts_by_status: Dict[str, int] = Field(default_factory=dict)
    forecast_issue_date: Optional[str] = None
    forecast_horizon: Optional[str] = None
    forecast_type: Optional[str] = None
    sheet_used: Optional[str] = None
    target_year: Optional[int] = None
    is_year_ambiguous: bool = False
    scale_verified: Optional[str] = None
    station_mapping_summary: Optional[Dict[str, Any]] = None
    unmapped_external_stations: List[Any] = Field(default_factory=list)
    duplicate_stations: List[Any] = Field(default_factory=list)


class IngestionPreviewResponse(BaseModel):
    status: str
    data_type: str
    filename: str
    staging_token: str
    summary: IngestionPreviewSummary
    anomalies: List[Dict[str, Any]] = Field(default_factory=list)
    diff_samples: List[Dict[str, Any]] = Field(default_factory=list)
    preview_items: List[Dict[str, Any]] = Field(default_factory=list)


class IngestionCommitRequest(BaseModel):
    staging_token: str
    confirm_overwrite: bool = True
    selected_periods: Optional[List[str]] = None
    explicit_update_consent: bool = False
    approval_scope: Optional[str] = None
    operator: Optional[str] = "OPERATOR_BMKG"


class IngestionCommitResponse(BaseModel):
    batch_id: str
    data_type: str
    filename: str
    status: str
    operator: str
    timestamp: str
    total_records: int = 0
    records_added: int = 0
    records_updated: int = 0
    records_skipped: int = 0
    records_rejected: int = 0
    periods_updated: List[str] = Field(default_factory=list)
    storage_consistency: Optional[str] = "CONSISTENT"
    backup_reference: Optional[str] = None
    readiness_sync: Optional[Dict[str, Any]] = None


class IngestionHistoryItem(BaseModel):
    batch_id: str
    data_type: str
    file_name: str
    file_size_bytes: Optional[int] = None
    target_period: Optional[str] = None
    date_range_start: Optional[str] = None
    date_range_end: Optional[str] = None
    total_records: int
    new_records: int
    updated_records: int
    identical_records: int
    rejected_records: int = 0
    missing_records: int = 0
    damaged_records: int = 0
    parser_version: Optional[str] = "1.2.0"
    backup_reference: Optional[str] = None
    approval_scope: Optional[str] = None
    status: str
    operator: str
    created_at: str


class IngestionHistoryResponse(BaseModel):
    total: int
    items: List[IngestionHistoryItem]


# ==============================================================================
# OPERATIONAL DATA MANAGEMENT, LATEST STATUS & BATCH CANCEL SCHEMAS
# ==============================================================================

class CurahHujanStatus(BaseModel):
    latest_date: Optional[str] = None
    latest_dasarian: Optional[str] = None
    reported_stations: int = 0
    total_stations: int = 57
    coverage_pct: float = 0.0
    missing_stations_count: int = 0
    missing_stations: List[Dict[str, Any]] = Field(default_factory=list)
    status_label: str = "Tersedia"


class SpiStatusItem(BaseModel):
    latest_date: Optional[str] = None
    total_manual_stations: int = 52
    valid_stations_count: int = 0
    missing_stations_count: int = 0
    arg_stations_handled: int = 5
    evaluation_period: Optional[str] = None
    latest_month_year: Optional[str] = None
    status_label: str = "Tersedia"


class ProbabilitasDasarianStatus(BaseModel):
    latest_issue_date: Optional[str] = None
    target_period: Optional[str] = None
    stations_count: int = 0
    indicators_count: int = 0
    status_label: str = "Tersedia"


class ProbabilitasBulananStatus(BaseModel):
    latest_issue_date: Optional[str] = None
    target_month: Optional[str] = None
    stations_count: int = 0
    indicators_count: int = 0
    status_label: str = "Tersedia"


class LatestDataStatusResponse(BaseModel):
    status: str = "ok"
    curah_hujan: CurahHujanStatus
    spi_harian_30d: SpiStatusItem
    spi_harian_90d: SpiStatusItem
    spi_dasarian_30d: SpiStatusItem
    spi_dasarian_90d: SpiStatusItem
    spi_bulanan: SpiStatusItem
    probabilitas_dasarian: ProbabilitasDasarianStatus
    probabilitas_bulanan: ProbabilitasBulananStatus
    checked_at: str


class BatchCancelRequest(BaseModel):
    reason: str
    operator: Optional[str] = "OPERATOR_BMKG"


class BatchCancelResponse(BaseModel):
    batch_id: str
    status: str
    data_type: str
    records_reverted: int
    cancellation_reason: str
    cancelled_by: str
    message: str


class RecordCorrectionRequest(BaseModel):
    station_id: str
    date: str
    new_rainfall_mm: float
    reason: str
    operator: Optional[str] = "OPERATOR_BMKG"


class RecordCorrectionResponse(BaseModel):
    status: str
    station_id: str
    observation_date: str
    old_rainfall_mm: Optional[float] = None
    new_rainfall_mm: float
    old_obs_status: Optional[str] = None
    new_obs_status: str
    reason: str
    approved_by: str
    message: str


class RecordVoidRequest(BaseModel):
    station_id: str
    date: str
    reason: str
    operator: Optional[str] = "OPERATOR_BMKG"


class RecordVoidResponse(BaseModel):
    status: str
    station_id: str
    observation_date: str
    old_rainfall_mm: Optional[float] = None
    new_obs_status: str
    reason: str
    approved_by: str
    message: str


class IngestionBatchListItem(BaseModel):
    batch_id: str
    data_type: str
    file_name: str
    file_size_bytes: Optional[int] = None
    target_period: Optional[str] = None
    date_range_start: Optional[str] = None
    date_range_end: Optional[str] = None
    total_records: int
    new_records: int
    updated_records: int
    identical_records: int
    rejected_records: int = 0
    missing_records: int = 0
    damaged_records: int = 0
    status: str
    operator: str
    cancellation_reason: Optional[str] = None
    cancelled_by: Optional[str] = None
    cancelled_at: Optional[str] = None
    created_at: str


class IngestionBatchListResponse(BaseModel):
    total: int
    limit: int
    offset: int
    items: List[IngestionBatchListItem]


class ForecastVintageItem(BaseModel):
    target_period_id: str
    target_period_label: str
    forecast_type: str
    forecast_resolution: Optional[str] = None
    target_year: int
    target_month: int
    target_dasarian: int
    issue_date: str
    source_file: str
    stations_count: int
    parameters_count: int
    total_records: int
    is_active_vintage: bool = True
    vintage_status: str = "AKTIF (Terbaru)"
    snapshot_timestamp: Optional[str] = None


class ForecastVintagesResponse(BaseModel):
    total: int
    vintages: List[ForecastVintageItem]


class OperationalSummaryResponse(BaseModel):
    total_batches: int
    successful_batches: int
    rolled_back_batches: int
    total_new_records: int
    total_updated_records: int
    total_rejected_records: int


class SpiVoidRequest(BaseModel):
    station_id: str
    period_type: str = "DASARIAN"  # 'DASARIAN' | 'DAILY' | 'BULANAN'
    timescale: str = "30D"          # '30D' | '90D' | 'BULANAN'
    date: str                       # 'YYYY-MM-DD'
    reason: str
    operator: str = "OPERATOR_BMKG"


class SpiVoidResponse(BaseModel):
    status: str
    message: str
    station_id: str
    timescale: str
    date: str
    operator: str


class ProbabilityVoidRequest(BaseModel):
    issue_date: str
    target_period: str
    station_id: Optional[str] = None
    forecast_parameter: Optional[str] = None
    reason: str
    operator: str = "OPERATOR_BMKG"


class ProbabilityVoidResponse(BaseModel):
    status: str
    message: str
    records_voided: int
    issue_date: str
    target_period: str
    operator: str


# ==============================================================================
# REGIONAL WARNING MANAGEMENT & SIH3 PUBLICATION SCHEMAS (FASE II - V)
# ==============================================================================

class RegionalWarningDecisionRequest(BaseModel):
    period_id: Optional[str] = None
    region_code: str
    hazard_code: Optional[str] = None
    hazard_type: Optional[str] = None  # Alias for hazard_code ('PDKM' | 'PDCHT')
    decision_mode: Optional[str] = None  # 'DSS_RECOMMENDATION' | 'OPERATOR_OVERRIDE' | 'NO_ACTIVE_WARNING'
    decision_source: Optional[str] = None  # Alias for decision_mode
    final_level: Optional[str] = None
    override_reason: Optional[str] = None
    analysis_notes: Optional[str] = None
    narrative: Optional[str] = None
    valid_from: Optional[str] = None
    valid_until: Optional[str] = None
    operator: str = "klimatkepri"
    min_coverage_pct: float = 50.0


class RegionalBulkInitRequest(BaseModel):
    period_id: Optional[str] = None
    operator: str = "klimatkepri"
    valid_from: Optional[str] = None
    valid_until: Optional[str] = None
    min_coverage_pct: float = 50.0


class SIH3PublicationPreviewRequest(BaseModel):
    period_id: Optional[str] = None
    valid_from: Optional[str] = None
    valid_until: Optional[str] = None
    min_coverage_pct: float = 50.0
    operator: Optional[str] = None


class SIH3ValidatePayloadRequest(BaseModel):
    payload: Optional[Dict[str, Any]] = None
    period_id: Optional[str] = None
    valid_from: Optional[str] = None
    valid_until: Optional[str] = None
    min_coverage_pct: float = 50.0


class SIH3WorkflowActionRequest(BaseModel):
    period_id: Optional[str] = None
    action: str = "SAVE_DRAFT"  # 'SAVE_DRAFT' | 'SUBMIT_REVIEW' | 'APPROVE' | 'PUBLISH'
    operator: str = "klimatkepri"
    valid_from: Optional[str] = None
    valid_until: Optional[str] = None
    revision_reason: Optional[str] = None
    notes: Optional[str] = None
    min_coverage_pct: float = 50.0




