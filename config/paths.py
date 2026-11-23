"""
CEWS Path Configuration & Canonical Location Resolver
Climate Early Warning System (CEWS) BMKG Stasiun Klimatologi Kepulauan Riau

Centralizes all repository paths to guarantee portability and prevent hardcoded paths.
Supports graceful fallback between canonical target paths and legacy root locations.
"""

import os
from pathlib import Path

# Repository Root (Dynamic & Portable)
PROJECT_ROOT = Path(__file__).resolve().parent.parent

# 1. Configuration Directories
CONFIG_DIR = PROJECT_ROOT / "config"
RULES_CONFIG_DIR = CONFIG_DIR / "cews_rules"
DATABASE_CONFIG_DIR = CONFIG_DIR / "database"

# 2. Data Directories
DATA_DIR = PROJECT_ROOT / "data"

# Raw Data
RAW_DATA_DIR = DATA_DIR / "raw"
RAINFALL_RAW_DIR = RAW_DATA_DIR / "rainfall"
SPI_RAW_DIR = RAW_DATA_DIR / "spi"
FORECAST_RAW_DIR = RAW_DATA_DIR / "forecast"
FORECAST_DASARIAN_RAW_DIR = FORECAST_RAW_DIR / "dasarian"
FORECAST_MONTHLY_RAW_DIR = FORECAST_RAW_DIR / "monthly"

# Reference Data
REFERENCE_DATA_DIR = DATA_DIR / "reference"
STATIONS_REF_DIR = REFERENCE_DATA_DIR / "stations"

# Processed Data
PROCESSED_DATA_DIR = DATA_DIR / "processed"
INDICATORS_PROCESSED_DIR = PROCESSED_DATA_DIR / "indicators"
HTH_PROCESSED_DIR = PROCESSED_DATA_DIR / "hth"
FORECAST_PROCESSED_DIR = PROCESSED_DATA_DIR / "forecast"

# Operational Data
OPERATIONAL_DATA_DIR = DATA_DIR / "operational"
CURRENT_OPERATIONAL_DIR = OPERATIONAL_DATA_DIR / "current"
SNAPSHOT_OPERATIONAL_DIR = OPERATIONAL_DATA_DIR / "snapshot"

# Historical Data
HISTORICAL_DATA_DIR = DATA_DIR / "historical"
WARNINGS_HISTORICAL_DIR = HISTORICAL_DATA_DIR / "warnings"

# Archive Data
ARCHIVE_DATA_DIR = DATA_DIR / "archive"
LEGACY_SPI_ARCHIVE_DIR = ARCHIVE_DATA_DIR / "legacy_spi"
SUPERSEDED_PROCESSED_ARCHIVE_DIR = ARCHIVE_DATA_DIR / "superseded_processed"
MISC_ARCHIVE_DIR = ARCHIVE_DATA_DIR / "misc"

# 3. Reports Directories
REPORTS_DIR = PROJECT_ROOT / "reports"
OPERATIONAL_REPORTS_DIR = REPORTS_DIR / "operational"
VALIDATION_REPORTS_DIR = REPORTS_DIR / "validation"
AUDITS_REPORTS_DIR = REPORTS_DIR / "audits"
ARCHIVE_REPORTS_DIR = REPORTS_DIR / "archive"

# 4. Docs, Outputs, Logs
DOCS_DIR = PROJECT_ROOT / "docs"
OUTPUTS_DIR = PROJECT_ROOT / "outputs"
LOGS_DIR = PROJECT_ROOT / "logs"
SCRIPTS_DIR = PROJECT_ROOT / "scripts"
TESTS_DIR = PROJECT_ROOT / "tests"
PIPELINE_DIR = PROJECT_ROOT / "pipeline"
BACKEND_DIR = PROJECT_ROOT / "backend"
FRONTEND_DIR = PROJECT_ROOT / "frontend"


def resolve_path(canonical_path: Path, fallback_path: Path = None) -> Path:
    """
    Returns canonical_path if it exists; otherwise fallback_path if it exists;
    defaults to canonical_path.
    """
    if canonical_path.exists():
        return canonical_path
    if fallback_path and fallback_path.exists():
        return fallback_path
    return canonical_path


# ==============================================================================
# CANONICAL FILE PATHS (WITH FALLBACKS)
# ==============================================================================

# Reference
PATH_STATION_METADATA = resolve_path(
    STATIONS_REF_DIR / "station_metadata.parquet",
    PROJECT_ROOT / "station_metadata.parquet"
)
PATH_MAPPING_TAMBAHAN = resolve_path(
    STATIONS_REF_DIR / "mapping_tambahan.xlsx",
    PROJECT_ROOT / "mapping_tambahan.xlsx"
)

# Raw Sources
PATH_SPI_AUTHORITATIVE = resolve_path(
    SPI_RAW_DIR / "dasarian" / "SPI_all_30d.parquet",
    PROJECT_ROOT / "data" / "raw" / "spi" / "dasarian" / "SPI_all_30d.parquet"
)
PATH_SPI_PARQUET_DASARIAN_30D = PATH_SPI_AUTHORITATIVE
PATH_SPI_PARQUET_DASARIAN_90D = resolve_path(
    SPI_RAW_DIR / "dasarian" / "SPI_all_90d.parquet",
    PROJECT_ROOT / "data" / "raw" / "spi" / "dasarian" / "SPI_all_90d.parquet"
)
PATH_RAINFALL_DAILY = resolve_path(
    RAINFALL_RAW_DIR / "final_rainfall_daily.parquet",
    PROJECT_ROOT / "final_rainfall_daily.parquet"
)
PATH_OBSERVATION_DAILY = resolve_path(
    RAINFALL_RAW_DIR / "observation_daily.parquet",
    PROJECT_ROOT / "observation_daily.parquet"
)

# Operational
PATH_CURRENT_WARNING = resolve_path(
    CURRENT_OPERATIONAL_DIR / "cews_current_warning.parquet",
    PROJECT_ROOT / "cews_current_warning.parquet"
)
PATH_FORECAST_SNAPSHOT = resolve_path(
    SNAPSHOT_OPERATIONAL_DIR / "cews_forecast_snapshot.parquet",
    PROJECT_ROOT / "cews_forecast_snapshot.parquet"
)

# Historical
PATH_WARNING_HISTORY = resolve_path(
    WARNINGS_HISTORICAL_DIR / "cews_warning_history.parquet",
    PROJECT_ROOT / "cews_warning_history.parquet"
)

# Processed
PATH_INDICATOR_DATASET = resolve_path(
    INDICATORS_PROCESSED_DIR / "cews_indicator_dataset.parquet",
    PROJECT_ROOT / "cews_indicator_dataset.parquet"
)
PATH_HTH_DAILY = resolve_path(
    HTH_PROCESSED_DIR / "hth_daily.parquet",
    PROJECT_ROOT / "hth_daily.parquet"
)

# Configuration & Rules
PATH_CEWS_RULES = resolve_path(
    RULES_CONFIG_DIR / "cews_rules.xlsx",
    PROJECT_ROOT / "cews_rules.xlsx"
)
PATH_SCHEMA_SQL = resolve_path(
    DATABASE_CONFIG_DIR / "schema.sql",
    PROJECT_ROOT / "database" / "schema.sql"
)
PATH_CONFIG_YAML = resolve_path(
    CONFIG_DIR / "cews_config.yaml",
    PROJECT_ROOT / "config" / "cews_config.yaml"
)

# Operational Reports
PATH_OPERATIONAL_QC_REPORT = resolve_path(
    OPERATIONAL_REPORTS_DIR / "cews_operational_qc_report.txt",
    PROJECT_ROOT / "cews_operational_qc_report.txt"
)
PATH_DECISION_QC_REPORT = resolve_path(
    OPERATIONAL_REPORTS_DIR / "cews_decision_qc_report.txt",
    PROJECT_ROOT / "cews_decision_qc_report.txt"
)
