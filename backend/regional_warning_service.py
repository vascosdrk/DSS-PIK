"""
backend/regional_warning_service.py
Regional Warning Management, Operator Decision Override, & SIH3 JSON Publication Engine
Decision Support System Peringatan Dini Iklim Kepulauan Riau (DSS-PIK)
BMKG Stasiun Meteorologi Kelas II Raja Haji Fisabilillah Tanjungpinang

Core Principles:
1. Canonical 7 Administrative Regions of Kepulauan Riau with verified BPS/Kemendagri
   codes (21.01 .. 21.72) and SIH3/BMKG GDB Polygon Keys (WADMKK / KABUPATEN).
2. Independent evaluation of PDKM (Kekeringan Meteorologis) and PDCHT (Curah Hujan Tinggi)
   per administrative region — NO single province-wide status, NO mixing of hazards.
3. One administrative region may simultaneously carry both PDKM and PDCHT warnings.
4. Honest Data Sufficiency:
   - Configurable coverage threshold (default: >= 50.0% valid stations in a region AND >= 1 valid station).
   - If a station triggers WASPADA/SIAGA/AWAS, worst-case safety applies immediately.
   - If NO station triggers a warning AND coverage is below threshold (or 0 valid stations),
     status is strictly INSUFFICIENT_DATA (never converted to False Green AMAN).
5. Dual Storage of Recommendations vs Operator Decisions:
   - System recommendation is always preserved alongside operator final decision.
   - Operator overrides require mandatory reason, analysis notes, operator identity, and timestamp.
6. Publication Workflow:
   - DRAFT -> REVIEW -> APPROVED -> PUBLISHED
   - Only APPROVED publications can be transitioned to PUBLISHED.
   - Modifying decisions after publication creates a new revision without overwriting history.
   - Public read-only endpoint (/api/v1/publications/sih3/latest.json) serves ONLY PUBLISHED snapshots.
"""

import json
import logging
import math
import re
from datetime import datetime, date, timedelta, timezone
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple
import pandas as pd

logger = logging.getLogger(__name__)

from backend.database import get_db, get_raw_connection
from backend.decision_engine import (
    evaluate_pdkm_full,
    evaluate_pdcht_full,
    arbitrate_final_synthesis,
    LEVEL_TO_STATUS,
    STATUS_TO_LEVEL,
)
from backend.period_service import (
    get_active_period,
    get_current_server_time_wib,
    get_dasarian_dates,
    get_observation_cutoff_date,
    format_period_label,
)
from config.paths import PATH_STATION_METADATA, DOCS_DIR

WIB = timezone(timedelta(hours=7))
SCHEMA_PATH = DOCS_DIR / "schemas" / "sih3_regional_warning.schema.json"

# ==============================================================================
# 1. CANONICAL ADMINISTRATIVE REGION REGISTRY (7 KABUPATEN / KOTA KEPRI)
# ==============================================================================
# Verified against:
# 1. data/reference/stations/station_metadata.parquet & MariaDB `stations`
# 2. data/reference/boundaries/PDCHT_Kab_202501_das1.gdb (WADMKK / KABUPATEN)
# 3. Kemendagri / BPS Kepulauan Riau Regency Codes (21.01 - 21.72)
CANONICAL_REGIONS: List[Dict[str, Any]] = [
    {
        "region_code": "21.01",
        "bps_code_compact": "2101",
        "sih3_polygon_key": "BINTAN",
        "region_name": "Kabupaten Bintan",
        "db_kabupaten_aliases": ["Kab. Bintan", "Kabupaten Bintan", "BINTAN"],
        "mapping_validation_status": "VERIFIED_GDB_AND_BPS",
        "mapping_source": "station_metadata.parquet + PDCHT_Kab_202501_das1.gdb (WADMKK='BINTAN') + Kode Kemendagri 21.01",
    },
    {
        "region_code": "21.02",
        "bps_code_compact": "2102",
        "sih3_polygon_key": "KARIMUN",
        "region_name": "Kabupaten Karimun",
        "db_kabupaten_aliases": ["Kab. Karimun", "Kabupaten Karimun", "KARIMUN"],
        "mapping_validation_status": "VERIFIED_GDB_AND_BPS",
        "mapping_source": "station_metadata.parquet + PDCHT_Kab_202501_das1.gdb (WADMKK='KARIMUN') + Kode Kemendagri 21.02",
    },
    {
        "region_code": "21.03",
        "bps_code_compact": "2103",
        "sih3_polygon_key": "NATUNA",
        "region_name": "Kabupaten Natuna",
        "db_kabupaten_aliases": ["Kab. Natuna", "Kabupaten Natuna", "NATUNA"],
        "mapping_validation_status": "VERIFIED_GDB_AND_BPS",
        "mapping_source": "station_metadata.parquet + PDCHT_Kab_202501_das1.gdb (WADMKK='NATUNA') + Kode Kemendagri 21.03",
    },
    {
        "region_code": "21.04",
        "bps_code_compact": "2104",
        "sih3_polygon_key": "LINGGA",
        "region_name": "Kabupaten Lingga",
        "db_kabupaten_aliases": ["Kab. Lingga", "Kabupaten Lingga", "LINGGA"],
        "mapping_validation_status": "VERIFIED_GDB_AND_BPS",
        "mapping_source": "station_metadata.parquet + PDCHT_Kab_202501_das1.gdb (WADMKK='LINGGA') + Kode Kemendagri 21.04",
    },
    {
        "region_code": "21.05",
        "bps_code_compact": "2105",
        "sih3_polygon_key": "KEPULAUAN ANAMBAS",
        "region_name": "Kabupaten Kepulauan Anambas",
        "db_kabupaten_aliases": ["Kab. Kepulauan Anambas", "Kabupaten Kepulauan Anambas", "KEPULAUAN ANAMBAS", "Anambas"],
        "mapping_validation_status": "VERIFIED_GDB_AND_BPS",
        "mapping_source": "station_metadata.parquet + PDCHT_Kab_202501_das1.gdb (WADMKK='KEPULAUAN ANAMBAS') + Kode Kemendagri 21.05",
    },
    {
        "region_code": "21.71",
        "bps_code_compact": "2171",
        "sih3_polygon_key": "KOTA BATAM",
        "region_name": "Kota Batam",
        "db_kabupaten_aliases": ["Kota Batam", "KOTA BATAM", "Batam"],
        "mapping_validation_status": "VERIFIED_GDB_AND_BPS",
        "mapping_source": "station_metadata.parquet + PDCHT_Kab_202501_das1.gdb (WADMKK='KOTA BATAM') + Kode Kemendagri 21.71",
    },
    {
        "region_code": "21.72",
        "bps_code_compact": "2172",
        "sih3_polygon_key": "KOTA TANJUNGPINANG",
        "region_name": "Kota Tanjungpinang",
        "db_kabupaten_aliases": ["Kota Tanjung Pinang", "Kota Tanjungpinang", "KOTA TANJUNGPINANG", "Tanjungpinang", "Tanjung Pinang"],
        "mapping_validation_status": "VERIFIED_GDB_AND_BPS",
        "mapping_source": "station_metadata.parquet + PDCHT_Kab_202501_das1.gdb (WADMKK='KOTA TANJUNGPINANG') + Kode Kemendagri 21.72",
    },
]

REGION_BY_CODE: Dict[str, Dict[str, Any]] = {r["region_code"]: r for r in CANONICAL_REGIONS}
REGION_BY_POLYGON_KEY: Dict[str, Dict[str, Any]] = {r["sih3_polygon_key"]: r for r in CANONICAL_REGIONS}
ARG_STATION_IDS = {"21010603B", "21010802B", "21020402B", "21040101B", "21710501B"}

# Configurable Data Sufficiency Policy:
# By default, at least 50.0% of authoritative stations for that hazard in a regency
# must have valid evaluation inputs before a region without triggers can be declared AMAN.
DEFAULT_MIN_COVERAGE_PCT: float = 50.0

LEVEL_COLOR_HEX = {
    "AMAN": "#33FF00",
    "NORMAL": "#33FF00",
    "WASPADA": "#FFFF00",
    "SIAGA": "#E69138",
    "AWAS": "#FF0000",
    "INSUFFICIENT_DATA": "#94A3B8",
}

HAZARD_NAMES = {
    "PDKM": "Kekeringan Meteorologis",
    "PDCHT": "Curah Hujan Tinggi",
}


# Cached station to kecamatan mapping and canonical kecamatan registry
_KECAMATAN_REGISTRY: Optional[List[Dict[str, Any]]] = None
_STATION_KECAMATAN_MAP: Optional[Dict[str, Dict[str, str]]] = None


def get_canonical_kecamatan_list() -> List[Dict[str, Any]]:
    """
    Returns the canonical 59 kecamatan of Kepulauan Riau loaded from
    data/reference/boundaries/kepri_kecamatan.geojson.
    """
    global _KECAMATAN_REGISTRY
    if _KECAMATAN_REGISTRY is not None:
        return _KECAMATAN_REGISTRY

    geojson_path = DOCS_DIR.parent / "data" / "reference" / "boundaries" / "kepri_kecamatan.geojson"
    if not geojson_path.exists():
        raise FileNotFoundError(f"Kecamatan GeoJSON not found at: {geojson_path}")

    with open(geojson_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    kec_items = []
    seen = set()
    for feat in data.get("features", []):
        props = feat.get("properties", {})
        kabkot = str(props.get("KABKOT", "")).strip().upper()
        kec = str(props.get("KECAMATAN", "")).strip().upper()
        reg_name = props.get("region_name", f"KABUPATEN {kabkot}")
        kec_id = f"{kabkot}_{kec}".replace(" ", "_")

        if kec_id in seen:
            continue
        seen.add(kec_id)

        # Find parent canonical region
        parent_reg = resolve_canonical_region(kabkot)
        parent_code = parent_reg["region_code"] if parent_reg else ""
        parent_poly = parent_reg["sih3_polygon_key"] if parent_reg else kabkot

        kec_items.append({
            "kecamatan_id": kec_id,
            "kecamatan_name": kec,
            "kabkot": kabkot,
            "parent_region_code": parent_code,
            "parent_polygon_key": parent_poly,
            "region_name": reg_name,
        })

    # Sort alphabetically by KABKOT, then KECAMATAN
    kec_items.sort(key=lambda x: (x["kabkot"], x["kecamatan_name"]))
    _KECAMATAN_REGISTRY = kec_items
    return _KECAMATAN_REGISTRY


def get_station_kecamatan_mapping() -> Dict[str, Dict[str, str]]:
    """
    Returns dictionary mapping station_id (lowercase) to {'kabkot': ..., 'kecamatan': ...}
    from data/reference/stations/station_kecamatan_mapping.json.
    """
    global _STATION_KECAMATAN_MAP
    if _STATION_KECAMATAN_MAP is not None:
        return _STATION_KECAMATAN_MAP

    map_path = DOCS_DIR.parent / "data" / "reference" / "stations" / "station_kecamatan_mapping.json"
    if map_path.exists():
        with open(map_path, "r", encoding="utf-8") as f:
            _STATION_KECAMATAN_MAP = json.load(f)
            return _STATION_KECAMATAN_MAP

    _STATION_KECAMATAN_MAP = {}
    return _STATION_KECAMATAN_MAP


def resolve_canonical_region(identifier: str) -> Optional[Dict[str, Any]]:
    """
    Deterministically resolves a region by region_code ('21.01'), compact code ('2101'),
    polygon key ('BINTAN'), or exact registered alias ('Kab. Bintan').
    Does NOT use loose fuzzy guessing.
    """
    if not identifier:
        return None
    clean = str(identifier).strip()
    if clean in REGION_BY_CODE:
        return REGION_BY_CODE[clean]
    clean_up = clean.upper()
    if clean_up in REGION_BY_POLYGON_KEY:
        return REGION_BY_POLYGON_KEY[clean_up]
    for r in CANONICAL_REGIONS:
        if clean == r["bps_code_compact"] or clean_up == r["region_name"].upper():
            return r
        for alias in r["db_kabupaten_aliases"]:
            if clean_up == alias.upper():
                return r
    return None


def resolve_region_by_station_id_prefix(station_id: str) -> Optional[Dict[str, Any]]:
    """ Resolves region from the first 4 digits of BMKG station_id (e.g. '21010401A' -> '2101'). """
    sid = str(station_id or "").strip().upper()
    if len(sid) >= 4:
        prefix4 = sid[:4]
        for r in CANONICAL_REGIONS:
            if r["bps_code_compact"] == prefix4:
                return r
    return None


# ==============================================================================
# 2. IDEMPOTENT DATABASE MIGRATIONS FOR REGIONAL WARNING & SIH3 PUBLICATION
# ==============================================================================
_TABLES_INITIALIZED = False


def ensure_regional_warning_tables():
    """
    Creates the canonical tables for Regional Warning Management, Operator Decisions,
    Audit Trail, and SIH3 Publications if they do not yet exist.
    Idempotent and non-destructive.
    """
    global _TABLES_INITIALIZED
    if _TABLES_INITIALIZED:
        return

    with get_db() as conn:
        with conn.cursor() as cur:
            # 1. Operator Regional Warning Decisions (Active State per Period + Region + Hazard)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS cews_regional_warning_decisions (
                    id                      BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
                    period_id               VARCHAR(30)     NOT NULL,
                    evaluation_period_label VARCHAR(100)    NOT NULL,
                    observation_cutoff_date DATE            NOT NULL,
                    forecast_issue_date     DATE            NULL,
                    region_code             VARCHAR(10)     NOT NULL,
                    sih3_polygon_key        VARCHAR(50)     NOT NULL,
                    region_name             VARCHAR(100)    NOT NULL,
                    hazard_code             ENUM('PDKM', 'PDCHT') NOT NULL,
                    hazard_name             VARCHAR(60)     NOT NULL,
                    recommended_level       VARCHAR(30)     NOT NULL,
                    final_level             VARCHAR(30)     NOT NULL,
                    decision_mode           ENUM('DSS_RECOMMENDATION', 'OPERATOR_OVERRIDE', 'NO_ACTIVE_WARNING') NOT NULL DEFAULT 'DSS_RECOMMENDATION',
                    operator_override       TINYINT(1)      NOT NULL DEFAULT 0,
                    override_reason         TEXT            NULL,
                    analysis_notes          TEXT            NULL,
                    narrative               TEXT            NOT NULL,
                    valid_from              DATE            NOT NULL,
                    valid_until             DATE            NOT NULL,
                    workflow_status         ENUM('DRAFT', 'REVIEW', 'APPROVED', 'PUBLISHED', 'EXPIRED') NOT NULL DEFAULT 'DRAFT',
                    station_coverage_json   LONGTEXT        NULL,
                    triggering_stations_json LONGTEXT       NULL,
                    decided_by              VARCHAR(80)     NOT NULL DEFAULT 'klimatkepri',
                    decided_at              DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    updated_at              DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                    PRIMARY KEY (id),
                    UNIQUE KEY uq_reg_warning_period_region_hazard (period_id, region_code, hazard_code),
                    KEY idx_reg_warning_period (period_id),
                    KEY idx_reg_warning_region (region_code)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
            """)

            # 2. Append-Only Decision Audit Trail Ledger
            cur.execute("""
                CREATE TABLE IF NOT EXISTS cews_regional_decision_audit_log (
                    id                      BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
                    period_id               VARCHAR(30)     NOT NULL,
                    region_code             VARCHAR(10)     NOT NULL,
                    region_name             VARCHAR(100)    NOT NULL,
                    hazard_code             VARCHAR(20)     NOT NULL,
                    action_type             VARCHAR(40)     NOT NULL,
                    recommended_level       VARCHAR(30)     NOT NULL,
                    previous_final_level    VARCHAR(30)     NULL,
                    new_final_level         VARCHAR(30)     NOT NULL,
                    decision_mode           VARCHAR(40)     NOT NULL,
                    operator_override       TINYINT(1)      NOT NULL DEFAULT 0,
                    override_reason         TEXT            NULL,
                    analysis_notes          TEXT            NULL,
                    narrative               TEXT            NULL,
                    operator                VARCHAR(80)     NOT NULL,
                    logged_at               DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    PRIMARY KEY (id),
                    KEY idx_reg_audit_period (period_id, region_code)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
            """)

            # 3. Append-Only SIH3 Publications & JSON Snapshot History
            cur.execute("""
                CREATE TABLE IF NOT EXISTS cews_sih3_publications (
                    id                      BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
                    publication_id          VARCHAR(40)     NOT NULL,
                    period_id               VARCHAR(30)     NOT NULL,
                    evaluation_period_label VARCHAR(100)    NOT NULL,
                    revision                INT UNSIGNED    NOT NULL DEFAULT 1,
                    status                  ENUM('DRAFT', 'REVIEW', 'APPROVED', 'PUBLISHED', 'EXPIRED') NOT NULL DEFAULT 'DRAFT',
                    valid_from              DATE            NOT NULL,
                    valid_until             DATE            NOT NULL,
                    observation_cutoff_date DATE            NOT NULL,
                    forecast_issue_date     DATE            NULL,
                    active_warnings_count   INT UNSIGNED    NOT NULL DEFAULT 0,
                    revision_reason         TEXT            NULL,
                    created_by              VARCHAR(80)     NOT NULL,
                    reviewed_by             VARCHAR(80)     NULL,
                    approved_by             VARCHAR(80)     NULL,
                    published_by            VARCHAR(80)     NULL,
                    generated_at            DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    reviewed_at             DATETIME        NULL,
                    approved_at             DATETIME        NULL,
                    published_at            DATETIME        NULL,
                    json_payload            LONGTEXT        NOT NULL,
                    PRIMARY KEY (id),
                    UNIQUE KEY uq_sih3_pub_id_rev (publication_id, revision),
                    KEY idx_sih3_pub_period (period_id, status),
                    KEY idx_sih3_pub_status (status, published_at)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
            """)
        conn.commit()

    _TABLES_INITIALIZED = True


# ==============================================================================
# 3. CANONICAL STATION-TO-REGION MAPPING VERIFICATION
# ==============================================================================
def get_verified_station_region_mapping() -> Dict[str, Any]:
    """
    Verifies all 57 authoritative stations in station_metadata.parquet and MariaDB `stations`
    against the 7 canonical administrative regions of Kepulauan Riau.
    Detects any discrepancy between station_id prefix, parquet regency, and DB kabupaten.
    """
    meta_df = pd.read_parquet(PATH_STATION_METADATA)
    meta_df["sid"] = meta_df["station_id"].astype(str).str.strip().str.upper()

    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT station_id, station_name, kabupaten, province, region, latitude, longitude
                FROM stations
                ORDER BY station_id
            """)
            db_rows = {str(r["station_id"]).strip().upper(): r for r in cur.fetchall()}

    mapped_stations: List[Dict[str, Any]] = []
    conflicts: List[Dict[str, Any]] = []
    region_counts: Dict[str, Dict[str, int]] = {
        r["region_code"]: {"total": 0, "manual": 0, "arg": 0} for r in CANONICAL_REGIONS
    }

    for _, row in meta_df.iterrows():
        sid = row["sid"]
        sname = str(row["station_name"]).strip()
        pq_kab = str(row["regency"]).strip()
        is_arg = sid in ARG_STATION_IDS or sid.endswith("B")
        stn_type = "ARG" if is_arg else "MANUAL"

        db_row = db_rows.get(sid)
        db_kab = str(db_row["kabupaten"]).strip() if db_row else None

        reg_from_pq = resolve_canonical_region(pq_kab)
        reg_from_db = resolve_canonical_region(db_kab) if db_kab else None
        reg_from_prefix = resolve_region_by_station_id_prefix(sid)

        conflict_reasons = []
        if not reg_from_pq:
            conflict_reasons.append(f"Regency '{pq_kab}' tidak terdaftar pada 7 wilayah kanonikal Kepri")
        if db_row is None:
            conflict_reasons.append(f"Stasiun '{sid}' tidak ditemukan pada tabel MariaDB stations")
        elif not reg_from_db or (reg_from_pq and reg_from_db["region_code"] != reg_from_pq["region_code"]):
            conflict_reasons.append(f"Ketidakcocokan kabupaten Parquet ('{pq_kab}') vs MariaDB ('{db_kab}')")
        if reg_from_pq and reg_from_prefix and reg_from_pq["region_code"] != reg_from_prefix["region_code"]:
            conflict_reasons.append(
                f"Prefiks ID stasiun '{sid[:4]}' ({reg_from_prefix['region_name']}) berbeda dari regency '{pq_kab}'"
            )

        status_str = "VERIFIED_MASTER" if not conflict_reasons else "CONFLICT_DETECTED"
        reg_info = reg_from_pq or reg_from_db or reg_from_prefix

        item = {
            "station_id": sid,
            "station_name": sname,
            "station_type": stn_type,
            "is_arg": is_arg,
            "kabupaten_db": db_kab or pq_kab,
            "region_code": reg_info["region_code"] if reg_info else "UNMAPPED",
            "bps_code_compact": reg_info["bps_code_compact"] if reg_info else "UNMAPPED",
            "sih3_polygon_key": reg_info["sih3_polygon_key"] if reg_info else "UNMAPPED",
            "region_name": reg_info["region_name"] if reg_info else pq_kab,
            "master_status": "MASTER_57",
            "mapping_validation_status": status_str,
            "mapping_source": reg_info["mapping_source"] if reg_info else "UNVERIFIED",
            "conflicts": conflict_reasons,
        }
        mapped_stations.append(item)

        if conflict_reasons:
            conflicts.append(item)
        elif reg_info:
            rc = reg_info["region_code"]
            region_counts[rc]["total"] += 1
            if is_arg:
                region_counts[rc]["arg"] += 1
            else:
                region_counts[rc]["manual"] += 1

    return {
        "total_master_stations": len(mapped_stations),
        "manual_stations_count": sum(1 for s in mapped_stations if not s["is_arg"]),
        "arg_stations_count": sum(1 for s in mapped_stations if s["is_arg"]),
        "conflicts_count": len(conflicts),
        "conflicts": conflicts,
        "regions_summary": [
            {
                **r,
                "total_stations": region_counts[r["region_code"]]["total"],
                "manual_stations": region_counts[r["region_code"]]["manual"],
                "arg_stations": region_counts[r["region_code"]]["arg"],
            }
            for r in CANONICAL_REGIONS
        ],
        "stations": mapped_stations,
    }


# ==============================================================================
# 4. REGIONAL WARNING AGGREGATION ENGINE (INDEPENDENT PDKM & PDCHT)
# ==============================================================================
def _normalize_warning_level(raw_level: Optional[str]) -> str:
    """
    Normalizes station/engine level strings:
    - 'NORMAL' / 'HIJAU' / 'AMAN' -> 'AMAN'
    - 'WASPADA' -> 'WASPADA'
    - 'SIAGA' -> 'SIAGA'
    - 'AWAS' -> 'AWAS'
    - 'INCOMPLETE' / 'TIDAK_LENGKAP' / 'INSUFFICIENT_DATA' -> 'INSUFFICIENT_DATA'
    """
    if not raw_level:
        return "INSUFFICIENT_DATA"
    up = str(raw_level).strip().upper()
    if up in ("NORMAL", "AMAN", "HIJAU", "TIDAK_ADA_PERINGATAN"):
        return "AMAN"
    if up in ("WASPADA", "SIAGA", "AWAS"):
        return up
    return "INSUFFICIENT_DATA"


def evaluate_station_hazards_item(stn_item: Dict[str, Any], period_label: str) -> Dict[str, Any]:
    """
    Evaluates a single station item from a period snapshot for PDKM and PDCHT independently
    using the authoritative Decision Engine, preserving detailed indicator trace.
    """
    sid = str(stn_item.get("station_id", "")).strip().upper()
    is_arg = bool(stn_item.get("is_arg", False) or sid in ARG_STATION_IDS or sid.endswith("B"))
    hth_days = stn_item.get("hth_days") if "hth_days" in stn_item else stn_item.get("hth_days_current")
    hth_uncertain = bool(stn_item.get("hth_uncertain", False))
    spi_val_30 = None if is_arg else stn_item.get("spi_value")
    spi_val_90 = None if is_arg else (stn_item.get("spi_value_90d") if "spi_value_90d" in stn_item else stn_item.get("spi_90d"))
    pb20 = None if is_arg else (stn_item.get("forecast_pb20") if "forecast_pb20" in stn_item else stn_item.get("prob_below20"))
    pa150 = None if is_arg else (stn_item.get("forecast_pa150") if "forecast_pa150" in stn_item else stn_item.get("prob_above150"))
    pa200 = None if is_arg else (stn_item.get("forecast_pa200") if "forecast_pa200" in stn_item else stn_item.get("prob_above200"))
    pa300 = None if is_arg else (stn_item.get("forecast_pa300") if "forecast_pa300" in stn_item else stn_item.get("prob_above300"))
    pm300 = None if is_arg else (stn_item.get("monthly_pa300") if "monthly_pa300" in stn_item else stn_item.get("prob_month_above300"))
    pm400 = None if is_arg else (stn_item.get("monthly_pa400") if "monthly_pa400" in stn_item else stn_item.get("prob_month_above400"))
    pm500 = None if is_arg else (stn_item.get("monthly_pa500") if "monthly_pa500" in stn_item else stn_item.get("prob_month_above500"))

    pdkm_eval = evaluate_pdkm_full(
        hth_days=hth_days,
        pb20=pb20,
        spi_val=spi_val_90,
        hth_uncertain=hth_uncertain,
        is_arg=is_arg,
        target_label=period_label,
    )
    pdcht_eval = evaluate_pdcht_full(
        pa150=pa150,
        pa200=pa200,
        pa300=pa300,
        pm300=pm300,
        pm400=pm400,
        pm500=pm500,
        is_arg=is_arg,
        target_label=period_label,
    )

    # Determine station validity per hazard:
    # - For PDKM: a station has valid PDKM data if at least one applicable indicator is valid
    #   (or evaluation_complete is True, or a warning level > 0 is triggered).
    #   However, if hth_uncertain is True and no indicator triggers, HTH is uncertain.
    pdkm_details = pdkm_eval.get("details", {})
    pdkm_has_valid_input = bool(
        pdkm_eval["evaluation_complete"]
        or pdkm_eval["level"] > 0
        or (
            not is_arg
            and sum(
                1
                for k in ("hth", "prob_low_rain", "spi")
                if pdkm_details.get(k, {}).get("valid", False)
            )
            >= 2
        )
    )
    # If station is explicitly INCOMPLETE with 0 valid inputs:
    if is_arg:
        pdkm_valid = bool(pdkm_details.get("hth", {}).get("valid", False) or pdkm_eval["level"] > 0)
    else:
        # Check if any indicator is valid; require complete or triggered, unless only 1 minor input missing?
        # Wait: Decision Engine sets status="INCOMPLETE" when level==0 and missing_inputs is non-empty!
        # Let's strictly respect Decision Engine: a station is valid for PDKM if pdkm_eval["evaluation_complete"] or pdkm_eval["level"] > 0.
        pdkm_valid = bool(pdkm_eval["evaluation_complete"] or pdkm_eval["level"] > 0)

    # For PDCHT: ARG stations do not model ECMWF ensemble probability, so only 52 manual stations are applicable.
    if is_arg:
        pdcht_applicable = False
        pdcht_valid = False
    else:
        pdcht_applicable = True
        pdcht_valid = bool(pdcht_eval["evaluation_complete"] or pdcht_eval["level"] > 0)

    lat_val = float(stn_item["latitude"]) if stn_item.get("latitude") is not None else None
    lon_val = float(stn_item["longitude"]) if stn_item.get("longitude") is not None else None
    elev_val = float(stn_item["elevation_m"]) if stn_item.get("elevation_m") is not None else None

    return {
        "station_id": sid,
        "station_name": stn_item.get("station_name", sid),
        "kabupaten": stn_item.get("kabupaten", ""),
        "latitude": lat_val,
        "longitude": lon_val,
        "elevation_m": elev_val,
        "is_arg": is_arg,
        "station_type": "ARG" if is_arg else "MANUAL",
        "hth_days": hth_days,
        "hth_uncertain": hth_uncertain,
        "spi_30d": spi_val_30,
        "spi_90d": spi_val_90,
        "pb20": pb20,
        "pa150": pa150,
        "pa200": pa200,
        "pa300": pa300,
        "pm300": pm300,
        "pm400": pm400,
        "pm500": pm500,
        "pdkm": {
            "status": _normalize_warning_level(pdkm_eval["status"]),
            "raw_status": pdkm_eval["status"],
            "level": pdkm_eval["level"],
            "valid": pdkm_valid,
            "evaluation_complete": pdkm_eval["evaluation_complete"],
            "missing_inputs": pdkm_eval["missing_inputs"],
            "triggered_indicators": pdkm_eval["triggered_indicators"],
            "reasons": pdkm_eval["reasons"],
        },
        "pdcht": {
            "applicable": pdcht_applicable,
            "status": _normalize_warning_level(pdcht_eval["status"]) if pdcht_applicable else "NOT_APPLICABLE_ARG",
            "raw_status": pdcht_eval["status"],
            "level": pdcht_eval["level"],
            "valid": pdcht_valid,
            "evaluation_complete": pdcht_eval["evaluation_complete"],
            "missing_inputs": pdcht_eval["missing_inputs"],
            "triggered_indicators": pdcht_eval["triggered_indicators"],
            "reasons": pdcht_eval["reasons"],
        },
    }


def aggregate_region_hazard(
    region_meta: Dict[str, Any],
    evaluated_stations: List[Dict[str, Any]],
    hazard_code: str,
    period_label: str,
    cutoff_date: str,
    forecast_issue_date: Optional[str],
    min_coverage_pct: float = DEFAULT_MIN_COVERAGE_PCT,
) -> Dict[str, Any]:
    """
    Independently aggregates either PDKM or PDCHT for a single administrative region.
    Rules:
    - Worst-case level among valid stations in the region.
    - Never assigns AMAN when data coverage is below `min_coverage_pct` (or 0 valid stations).
    - Full station & indicator provenance.
    """
    h_key = "pdkm" if hazard_code == "PDKM" else "pdcht"
    total_master = len(evaluated_stations)
    manual_count = sum(1 for s in evaluated_stations if not s["is_arg"])
    arg_count = sum(1 for s in evaluated_stations if s["is_arg"])

    if hazard_code == "PDKM":
        applicable_stations = evaluated_stations
    else:
        # PDCHT applies to manual stations with ECMWF ensemble points
        applicable_stations = [s for s in evaluated_stations if not s["is_arg"]]

    applicable_total = len(applicable_stations)
    valid_stations = [s for s in applicable_stations if s[h_key]["valid"]]
    missing_stations = [s for s in applicable_stations if not s[h_key]["valid"]]

    valid_count = len(valid_stations)
    missing_count = len(missing_stations)
    coverage_pct = round((valid_count / applicable_total) * 100.0, 1) if applicable_total > 0 else 0.0

    # Find highest triggered level across all stations in the region
    max_level = 0
    triggering_stations = []
    all_causing_indicators = []

    for s in applicable_stations:
        h_info = s[h_key]
        lvl = h_info["level"]
        if lvl > 0:
            if lvl > max_level:
                max_level = lvl
            ind_list = h_info["triggered_indicators"]
            for ind in ind_list:
                if ind not in all_causing_indicators:
                    all_causing_indicators.append(ind)
            triggering_stations.append({
                "station_id": s["station_id"],
                "station_name": s["station_name"],
                "level": LEVEL_TO_STATUS[lvl],
                "level_num": lvl,
                "indicators": ind_list,
                "reasons": h_info["reasons"],
                "input_summary": {
                    "hth_days": s["hth_days"],
                    "spi_30d": round(float(s["spi_30d"]), 2) if (s.get("spi_30d") is not None and math.isfinite(float(s["spi_30d"]))) else None,
                    "spi_90d": round(float(s["spi_90d"]), 2) if (s.get("spi_90d") is not None and math.isfinite(float(s["spi_90d"]))) else None,
                    "pb20": s["pb20"],
                    "pa150": s["pa150"],
                    "pa200": s["pa200"],
                    "pa300": s["pa300"],
                    "pm300": s["pm300"],
                    "pm400": s["pm400"],
                    "pm500": s["pm500"],
                },
            })

    # Sort triggering stations by highest level first, then name
    triggering_stations.sort(key=lambda x: (-x["level_num"], x["station_name"]))

    # Determine data sufficiency status and recommended level
    if max_level > 0:
        recommended_level = LEVEL_TO_STATUS[max_level]
        data_status = "COMPLETE" if missing_count == 0 else "PARTIAL"
        top_stns_preview = ", ".join(
            f"{t['station_name']} ({t['level']})" for t in triggering_stations[:4]
        )
        if len(triggering_stations) > 4:
            top_stns_preview += f", dan {len(triggering_stations) - 4} pos lainnya"
        default_narrative = (
            f"Peringatan Dini {HAZARD_NAMES[hazard_code]} ({hazard_code}) level {recommended_level} "
            f"di {region_meta['region_name']} untuk periode {period_label}. "
            f"Dipicu oleh {len(triggering_stations)} pos pengamatan ({top_stns_preview})."
        )
        insufficient_reason = None
    else:
        # No station triggered a warning (max_level == 0).
        # Check whether coverage is sufficient to honestly conclude AMAN!
        if valid_count == 0 or coverage_pct < min_coverage_pct:
            recommended_level = "INSUFFICIENT_DATA"
            data_status = "INSUFFICIENT_DATA"
            missing_names = ", ".join(s["station_name"] for s in missing_stations[:5])
            if len(missing_stations) > 5:
                missing_names += f" (+{len(missing_stations) - 5} pos)"
            insufficient_reason = (
                f"Cakupan data valid {hazard_code} di {region_meta['region_name']} hanya "
                f"{valid_count}/{applicable_total} pos ({coverage_pct}% < ambang minimum {min_coverage_pct}%). "
                f"Pos belum lengkap: {missing_names}."
            )
            default_narrative = (
                f"Data pengamatan/prakiraan {HAZARD_NAMES[hazard_code]} di {region_meta['region_name']} "
                f"belum mencukupi ({coverage_pct}%) untuk menetapkan status AMAN."
            )
        else:
            recommended_level = "AMAN"
            data_status = "COMPLETE" if missing_count == 0 else "PARTIAL"
            insufficient_reason = None
            default_narrative = (
                f"Tidak terdapat peringatan aktif {HAZARD_NAMES[hazard_code]} ({hazard_code}) "
                f"di {region_meta['region_name']} untuk periode {period_label} (Status: AMAN)."
            )

    return {
        "hazard_code": hazard_code,
        "hazard_name": HAZARD_NAMES[hazard_code],
        "recommended_level": recommended_level,
        "recommended_color_hex": LEVEL_COLOR_HEX.get(recommended_level, "#94A3B8"),
        "data_status": data_status,
        "insufficient_reason": insufficient_reason,
        "min_coverage_threshold_pct": min_coverage_pct,
        "station_coverage": {
            "total_master": total_master,
            "applicable_total": applicable_total,
            "manual_stations": manual_count,
            "arg_stations": arg_count,
            "valid": valid_count,
            "missing": missing_count,
            "percentage": coverage_pct,
        },
        "triggering_stations_count": len(triggering_stations),
        "triggering_stations": triggering_stations,
        "missing_stations": [
            {
                "station_id": s["station_id"],
                "station_name": s["station_name"],
                "station_type": s["station_type"],
                "missing_inputs": s[h_key]["missing_inputs"],
                "reasons": s[h_key]["reasons"],
            }
            for s in missing_stations
        ],
        "causing_indicators": all_causing_indicators,
        "evaluation_period": period_label,
        "observation_cutoff_date": cutoff_date,
        "forecast_issue_date": forecast_issue_date,
        "default_narrative": default_narrative,
    }


def compute_regional_recommendations(
    period_id: Optional[str] = None,
    snap_override: Optional[Dict[str, Any]] = None,
    min_coverage_pct: float = DEFAULT_MIN_COVERAGE_PCT,
) -> Dict[str, Any]:
    """
    Computes regional recommendations for all 7 Kabupaten/Kota of Kepulauan Riau,
    merging with any saved operator decisions for that period.
    """
    ensure_regional_warning_tables()

    if snap_override is not None:
        snap = snap_override
        pid = snap.get("period_id", period_id or "2026-09-das2")
    else:
        from backend.main import get_period_snapshot
        snap = get_period_snapshot(period_id)
        pid = snap.get("period_id", period_id or "2026-09-das2")

    period_label = snap.get("label") or snap.get("meta", {}).get("period_label") or pid
    cutoff_date = (
        snap.get("observation_cutoff")
        or snap.get("meta", {}).get("observation_cutoff")
        or "2026-09-10"
    )
    forecast_issue = (
        snap.get("forecast_issue")
        or snap.get("meta", {}).get("forecast_issue")
        or None
    )
    spi_ref_date = snap.get("spi_evidence_date")
    valid_from = (
        snap.get("target_start")
        or snap.get("meta", {}).get("target_period_start")
        or cutoff_date
    )
    valid_until = (
        snap.get("target_end")
        or snap.get("meta", {}).get("target_period_end")
        or cutoff_date
    )

    # Evaluate all 57 stations and group by canonical region_code
    stations_by_region: Dict[str, List[Dict[str, Any]]] = {
        r["region_code"]: [] for r in CANONICAL_REGIONS
    }
    for stn_raw in snap.get("items", []):
        eval_stn = evaluate_station_hazards_item(stn_raw, period_label)
        reg = resolve_canonical_region(stn_raw.get("kabupaten", "")) or resolve_region_by_station_id_prefix(
            eval_stn["station_id"]
        )
        if reg:
            stations_by_region[reg["region_code"]].append(eval_stn)

    # Load existing operator decisions for this period_id from MariaDB
    saved_decisions: Dict[Tuple[str, str], Dict[str, Any]] = {}
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT * FROM cews_regional_warning_decisions
                WHERE period_id = %s
                """,
                (pid,),
            )
            for row in cur.fetchall():
                key = (row["region_code"], row["hazard_code"])
                saved_decisions[key] = row

            # Also check latest publication record for this period
            cur.execute(
                """
                SELECT publication_id, revision, status, valid_from, valid_until,
                       active_warnings_count, created_by, approved_by, published_by,
                       generated_at, approved_at, published_at, revision_reason
                FROM cews_sih3_publications
                WHERE period_id = %s
                ORDER BY revision DESC, id DESC
                LIMIT 1
                """,
                (pid,),
            )
            latest_pub = cur.fetchone()

    regions_output: List[Dict[str, Any]] = []
    for reg_meta in CANONICAL_REGIONS:
        rc = reg_meta["region_code"]
        reg_stations = stations_by_region.get(rc, [])

        pdkm_rec = aggregate_region_hazard(
            reg_meta, reg_stations, "PDKM", period_label, cutoff_date, forecast_issue, min_coverage_pct
        )
        pdcht_rec = aggregate_region_hazard(
            reg_meta, reg_stations, "PDCHT", period_label, cutoff_date, forecast_issue, min_coverage_pct
        )

        # Merge with saved operator decisions (or default to DSS recommendation)
        hazards_merged = {}
        for h_code, h_rec in [("PDKM", pdkm_rec), ("PDCHT", pdcht_rec)]:
            saved = saved_decisions.get((rc, h_code))
            if saved:
                final_lvl = saved["final_level"]
                dec_mode = saved["decision_mode"]
                is_override = bool(saved["operator_override"])
                ov_reason = saved.get("override_reason")
                an_notes = saved.get("analysis_notes")
                narrative = saved.get("narrative") or h_rec["default_narrative"]
                decided_by = saved.get("decided_by")
                decided_at = (
                    saved["decided_at"].strftime("%Y-%m-%d %H:%M:%S")
                    if hasattr(saved.get("decided_at"), "strftime")
                    else str(saved.get("decided_at") or "")
                )
                wf_status = saved.get("workflow_status", "DRAFT")
                v_from = (
                    saved["valid_from"].strftime("%Y-%m-%d")
                    if hasattr(saved.get("valid_from"), "strftime")
                    else str(saved.get("valid_from") or valid_from)
                )
                v_until = (
                    saved["valid_until"].strftime("%Y-%m-%d")
                    if hasattr(saved.get("valid_until"), "strftime")
                    else str(saved.get("valid_until") or valid_until)
                )
                has_explicit_decision = True
            else:
                final_lvl = h_rec["recommended_level"]
                dec_mode = "DSS_RECOMMENDATION"
                is_override = False
                ov_reason = None
                an_notes = None
                narrative = h_rec["default_narrative"]
                decided_by = None
                decided_at = None
                wf_status = "DRAFT"
                v_from = valid_from
                v_until = valid_until
                has_explicit_decision = False

            hazards_merged[h_code] = {
                **h_rec,
                "final_level": final_lvl,
                "final_color_hex": LEVEL_COLOR_HEX.get(final_lvl, "#94A3B8"),
                "decision_mode": dec_mode,
                "operator_override": is_override,
                "override_reason": ov_reason,
                "analysis_notes": an_notes,
                "narrative": narrative,
                "decided_by": decided_by,
                "decided_at": decided_at,
                "workflow_status": wf_status,
                "valid_from": v_from,
                "valid_until": v_until,
                "has_explicit_decision": has_explicit_decision,
            }

        # Compute overall region data & coverage summary
        # Overall coverage uses all master stations in the region
        total_stns = len(reg_stations)
        # A station is considered valid at region summary level if its applicable hazards are valid
        valid_stns = sum(
            1
            for s in reg_stations
            if (s["pdkm"]["valid"] and (s["is_arg"] or s["pdcht"]["valid"]))
        )
        missing_stns = total_stns - valid_stns
        reg_cov_pct = round((valid_stns / total_stns) * 100.0, 1) if total_stns > 0 else 0.0

        pdkm_final = hazards_merged["PDKM"]["final_level"]
        pdcht_final = hazards_merged["PDCHT"]["final_level"]

        # Region data_status:
        if pdkm_rec["data_status"] == "INSUFFICIENT_DATA" and pdcht_rec["data_status"] == "INSUFFICIENT_DATA":
            reg_data_status = "INSUFFICIENT_DATA"
        elif pdkm_rec["data_status"] == "COMPLETE" and pdcht_rec["data_status"] == "COMPLETE":
            reg_data_status = "COMPLETE"
        elif pdkm_final in ("WASPADA", "SIAGA", "AWAS") or pdcht_final in ("WASPADA", "SIAGA", "AWAS"):
            reg_data_status = "COMPLETE" if missing_stns == 0 else "PARTIAL"
        elif pdkm_rec["data_status"] == "INSUFFICIENT_DATA" or pdcht_rec["data_status"] == "INSUFFICIENT_DATA":
            reg_data_status = "INSUFFICIENT_DATA"
        else:
            reg_data_status = "COMPLETE" if missing_stns == 0 else "PARTIAL"

        # Active warnings list for this region (supports 0, 1, or 2 simultaneous hazards)
        active_warnings = []
        for h_code in ("PDKM", "PDCHT"):
            hm = hazards_merged[h_code]
            if hm["final_level"] in ("WASPADA", "SIAGA", "AWAS"):
                active_warnings.append({
                    "hazard_code": h_code,
                    "hazard_name": hm["hazard_name"],
                    "recommended_level": hm["recommended_level"],
                    "final_level": hm["final_level"],
                    "color_hex": LEVEL_COLOR_HEX.get(hm["final_level"], "#FFFF00"),
                    "decision_source": "OPERATOR_OVERRIDE" if hm["operator_override"] else "DSS_RECOMMENDATION",
                    "operator_override": hm["operator_override"],
                    "override_reason": hm["override_reason"],
                    "analysis_notes": hm["analysis_notes"],
                    "decided_by": hm["decided_by"],
                    "decided_at": hm["decided_at"],
                    "triggering_stations": [
                        {
                            "station_id": t["station_id"],
                            "station_name": t["station_name"],
                            "level": t["level"],
                            "indicators": t["indicators"],
                        }
                        for t in hm["triggering_stations"]
                    ],
                    "narrative": hm["narrative"],
                })

        # Determine highest status for visual badge
        lvl_Order = {"INSUFFICIENT_DATA": -1, "AMAN": 0, "WASPADA": 1, "SIAGA": 2, "AWAS": 3}
        max_f = max(lvl_Order.get(pdkm_final, 0), lvl_Order.get(pdcht_final, 0))
        if max_f > 0:
            overall_status = LEVEL_TO_STATUS[max_f]
        elif pdkm_final == "INSUFFICIENT_DATA" or pdcht_final == "INSUFFICIENT_DATA":
            overall_status = "INSUFFICIENT_DATA"
        else:
            overall_status = "AMAN"

        # Decision status badge for table
        if hazards_merged["PDKM"]["has_explicit_decision"] or hazards_merged["PDCHT"]["has_explicit_decision"]:
            if hazards_merged["PDKM"]["operator_override"] or hazards_merged["PDCHT"]["operator_override"]:
                decision_badge = "PENYESUAIAN PETUGAS (OVERRIDE)"
            else:
                decision_badge = f"DITETAPKAN ({hazards_merged['PDKM']['workflow_status']})"
        else:
            decision_badge = "REKOMENDASI OTOMATIS DSS"

        regions_output.append({
            "region_code": rc,
            "bps_code_compact": reg_meta["bps_code_compact"],
            "sih3_polygon_key": reg_meta["sih3_polygon_key"],
            "region_name": reg_meta["region_name"],
            "mapping_validation_status": reg_meta["mapping_validation_status"],
            "mapping_source": reg_meta["mapping_source"],
            "data_status": reg_data_status,
            "overall_region_status": overall_status,
            "decision_status_label": decision_badge,
            "station_coverage": {
                "total": total_stns,
                "manual_stations": sum(1 for s in reg_stations if not s["is_arg"]),
                "arg_stations": sum(1 for s in reg_stations if s["is_arg"]),
                "valid": valid_stns,
                "missing": missing_stns,
                "percentage": reg_cov_pct,
            },
            "pdkm": hazards_merged["PDKM"],
            "pdcht": hazards_merged["PDCHT"],
            "active_warnings": active_warnings,
            "stations": reg_stations,
        })

    pub_meta = None
    if latest_pub:
        pub_meta = {
            "publication_id": latest_pub["publication_id"],
            "revision": latest_pub["revision"],
            "status": latest_pub["status"],
            "valid_from": (
                latest_pub["valid_from"].strftime("%Y-%m-%d")
                if hasattr(latest_pub.get("valid_from"), "strftime")
                else str(latest_pub.get("valid_from") or valid_from)
            ),
            "valid_until": (
                latest_pub["valid_until"].strftime("%Y-%m-%d")
                if hasattr(latest_pub.get("valid_until"), "strftime")
                else str(latest_pub.get("valid_until") or valid_until)
            ),
            "active_warnings_count": latest_pub["active_warnings_count"],
            "created_by": latest_pub["created_by"],
            "approved_by": latest_pub["approved_by"],
            "published_by": latest_pub["published_by"],
            "generated_at": (
                latest_pub["generated_at"].strftime("%Y-%m-%d %H:%M:%S")
                if hasattr(latest_pub.get("generated_at"), "strftime")
                else str(latest_pub.get("generated_at") or "")
            ),
            "approved_at": (
                latest_pub["approved_at"].strftime("%Y-%m-%d %H:%M:%S")
                if hasattr(latest_pub.get("approved_at"), "strftime")
                else (str(latest_pub.get("approved_at")) if latest_pub.get("approved_at") else None)
            ),
            "published_at": (
                latest_pub["published_at"].strftime("%Y-%m-%d %H:%M:%S")
                if hasattr(latest_pub.get("published_at"), "strftime")
                else (str(latest_pub.get("published_at")) if latest_pub.get("published_at") else None)
            ),
            "revision_reason": latest_pub.get("revision_reason"),
        }

    return {
        "period_id": pid,
        "evaluation_period": period_label,
        "observation_cutoff_date": cutoff_date,
        "forecast_issue_date": forecast_issue,
        "spi_reference_date": spi_ref_date,
        "default_valid_from": valid_from,
        "default_valid_until": valid_until,
        "min_coverage_threshold_pct": min_coverage_pct,
        "latest_publication": pub_meta,
        "summary": {
            "total_regions": len(regions_output),
            "pdkm_active_regions": sum(
                1 for r in regions_output if r["pdkm"]["final_level"] in ("WASPADA", "SIAGA", "AWAS")
            ),
            "pdcht_active_regions": sum(
                1 for r in regions_output if r["pdcht"]["final_level"] in ("WASPADA", "SIAGA", "AWAS")
            ),
            "multi_hazard_regions": sum(1 for r in regions_output if len(r["active_warnings"]) == 2),
            "insufficient_data_regions": sum(
                1 for r in regions_output if r["data_status"] == "INSUFFICIENT_DATA"
            ),
            "override_count": sum(
                (1 if r["pdkm"]["operator_override"] else 0) + (1 if r["pdcht"]["operator_override"] else 0)
                for r in regions_output
            ),
        },
        "regions": regions_output,
    }


def compute_kecamatan_recommendations(
    period_id: Optional[str] = None,
    snap_override: Optional[Dict[str, Any]] = None,
    min_coverage_pct: float = DEFAULT_MIN_COVERAGE_PCT,
) -> Dict[str, Any]:
    """
    Computes recommendations at KECAMATAN level (59 kecamatan across Kepulauan Riau).
    For each kecamatan:
    1. Gathers stations located in that kecamatan via station_kecamatan_mapping.
    2. If stations exist in that kecamatan, aggregates PDKM & PDCHT based on station alerts.
    3. If no station exists in that kecamatan, inherits the baseline recommendation of its parent Kabupaten/Kota.
    """
    reg_bundle = compute_regional_recommendations(
        period_id=period_id,
        snap_override=snap_override,
        min_coverage_pct=min_coverage_pct,
    )

    parent_by_kabkot = {}
    for r in reg_bundle["regions"]:
        poly = r["sih3_polygon_key"]
        parent_by_kabkot[poly] = r
        if poly == "KOTA BATAM":
            parent_by_kabkot["BATAM"] = r
        elif poly == "KOTA TANJUNGPINANG":
            parent_by_kabkot["TANJUNGPINANG"] = r
        elif poly == "KEPULAUAN ANAMBAS":
            parent_by_kabkot["KEPULAUAN ANAMBAS"] = r
            parent_by_kabkot["ANAMBAS"] = r
        elif poly == "BINTAN":
            parent_by_kabkot["BINTAN"] = r
        elif poly == "KARIMUN":
            parent_by_kabkot["KARIMUN"] = r
        elif poly == "LINGGA":
            parent_by_kabkot["LINGGA"] = r
        elif poly == "NATUNA":
            parent_by_kabkot["NATUNA"] = r

    canonical_kec = get_canonical_kecamatan_list()
    stn_mapping = get_station_kecamatan_mapping()

    # Collect evaluated stations from reg_bundle
    evaluated_stations = []
    for r in reg_bundle["regions"]:
        for stn in r.get("stations", []):
            evaluated_stations.append(stn)

    # Group stations by kecamatan_id
    stations_by_kec: Dict[str, List[Dict[str, Any]]] = {k["kecamatan_id"]: [] for k in canonical_kec}
    for stn in evaluated_stations:
        sid = str(stn.get("station_id", "")).strip().lower()
        m = stn_mapping.get(sid)
        if m:
            kab = str(m.get("kabkot", "")).strip().upper()
            kec = str(m.get("kecamatan", "")).strip().upper()
            target_id = f"{kab}_{kec}".replace(" ", "_")
            if target_id in stations_by_kec:
                stations_by_kec[target_id].append(stn)

    period_label = reg_bundle["evaluation_period"]
    cutoff_date = reg_bundle["observation_cutoff_date"]
    forecast_issue = reg_bundle.get("forecast_issue_date")

    kecamatan_output: List[Dict[str, Any]] = []
    for k_item in canonical_kec:
        kid = k_item["kecamatan_id"]
        kname = k_item["kecamatan_name"]
        kabkot = k_item["kabkot"]
        poly = k_item["parent_polygon_key"]
        p_reg = parent_by_kabkot.get(kabkot) or parent_by_kabkot.get(poly)

        stns = stations_by_kec.get(kid, [])
        if len(stns) > 0:
            pdkm_agg = aggregate_region_hazard(
                region_meta={"region_name": f"Kecamatan {kname}, {kabkot}"},
                evaluated_stations=stns,
                hazard_code="PDKM",
                period_label=period_label,
                cutoff_date=cutoff_date,
                forecast_issue_date=forecast_issue,
                min_coverage_pct=min_coverage_pct,
            )
            pdcht_agg = aggregate_region_hazard(
                region_meta={"region_name": f"Kecamatan {kname}, {kabkot}"},
                evaluated_stations=stns,
                hazard_code="PDCHT",
                period_label=period_label,
                cutoff_date=cutoff_date,
                forecast_issue_date=forecast_issue,
                min_coverage_pct=min_coverage_pct,
            )
            inherited_from_parent = False
        else:
            parent_pdkm = p_reg["pdkm"] if p_reg else {}
            parent_pdcht = p_reg["pdcht"] if p_reg else {}

            pdkm_agg = {
                "hazard_code": "PDKM",
                "hazard_name": HAZARD_NAMES["PDKM"],
                "recommended_level": parent_pdkm.get("recommended_level", "AMAN"),
                "recommended_color_hex": LEVEL_COLOR_HEX.get(parent_pdkm.get("recommended_level", "AMAN"), "#94A3B8"),
                "data_status": "INHERITED_FROM_REGENCY",
                "insufficient_reason": None,
                "station_coverage": {"total_master": 0, "applicable_total": 0, "valid": 0, "missing": 0, "percentage": 0.0},
                "triggering_stations_count": 0,
                "triggering_stations": [],
                "missing_stations": [],
                "causing_indicators": [],
                "default_narrative": f"Mengikuti status Kabupaten/Kota ({kabkot}): PDKM {parent_pdkm.get('recommended_level', 'AMAN')}.",
            }
            pdcht_agg = {
                "hazard_code": "PDCHT",
                "hazard_name": HAZARD_NAMES["PDCHT"],
                "recommended_level": parent_pdcht.get("recommended_level", "AMAN"),
                "recommended_color_hex": LEVEL_COLOR_HEX.get(parent_pdcht.get("recommended_level", "AMAN"), "#94A3B8"),
                "data_status": "INHERITED_FROM_REGENCY",
                "insufficient_reason": None,
                "station_coverage": {"total_master": 0, "applicable_total": 0, "valid": 0, "missing": 0, "percentage": 0.0},
                "triggering_stations_count": 0,
                "triggering_stations": [],
                "missing_stations": [],
                "causing_indicators": [],
                "default_narrative": f"Mengikuti status Kabupaten/Kota ({kabkot}): PDCHT {parent_pdcht.get('recommended_level', 'AMAN')}.",
            }
            inherited_from_parent = True

        kecamatan_output.append({
            "kecamatan_id": kid,
            "kecamatan_name": kname,
            "kabkot": kabkot,
            "parent_polygon_key": poly,
            "stations_count": len(stns),
            "inherited_from_parent": inherited_from_parent,
            "pdkm": pdkm_agg,
            "pdcht": pdcht_agg,
            "stations": stns,
        })

    return {
        "period_id": reg_bundle["period_id"],
        "evaluation_period": period_label,
        "total_kecamatan": len(kecamatan_output),
        "kecamatan": kecamatan_output,
        "regions": reg_bundle["regions"],
        "summary": reg_bundle["summary"],
    }


# ==============================================================================
# 5. OPERATOR DECISION PERSISTENCE & AUDIT TRAIL
# ==============================================================================
def save_regional_warning_decision(
    period_id: str,
    region_code: str,
    hazard_code: str,
    decision_mode: str,
    final_level: Optional[str] = None,
    override_reason: Optional[str] = None,
    analysis_notes: Optional[str] = None,
    narrative: Optional[str] = None,
    valid_from: Optional[str] = None,
    valid_until: Optional[str] = None,
    operator: str = "klimatkepri",
    snap_override: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Saves or updates an operator's regional warning decision for a specific
    (period_id, region_code, hazard_code) while preserving the original DSS-PIK recommendation
    and appending a permanent audit log entry.
    """
    ensure_regional_warning_tables()

    reg_meta = resolve_canonical_region(region_code)
    if not reg_meta:
        raise ValueError(f"Kode wilayah '{region_code}' tidak terdaftar dalam 7 Kabupaten/Kota Kepulauan Riau.")

    h_code = str(hazard_code or "").strip().upper()
    if h_code not in ("PDKM", "PDCHT"):
        raise ValueError(f"Kode ancaman '{hazard_code}' tidak valid. Gunakan 'PDKM' atau 'PDCHT'.")

    # Compute current authoritative recommendation for this period & region
    rec_bundle = compute_regional_recommendations(period_id=period_id, snap_override=snap_override)
    reg_rec = next((r for r in rec_bundle["regions"] if r["region_code"] == reg_meta["region_code"]), None)
    if not reg_rec:
        raise ValueError(f"Data rekomendasi untuk wilayah {reg_meta['region_name']} tidak ditemukan.")

    h_rec = reg_rec["pdkm"] if h_code == "PDKM" else reg_rec["pdcht"]
    rec_level = h_rec["recommended_level"]

    mode = str(decision_mode or "DSS_RECOMMENDATION").strip().upper()
    if mode not in ("DSS_RECOMMENDATION", "OPERATOR_OVERRIDE", "NO_ACTIVE_WARNING"):
        raise ValueError(f"Mode keputusan '{decision_mode}' tidak valid.")

    if mode == "DSS_RECOMMENDATION":
        resolved_final = rec_level
    elif mode == "NO_ACTIVE_WARNING":
        resolved_final = "AMAN"
    else:
        resolved_final = _normalize_warning_level(final_level) if final_level else rec_level

    if resolved_final not in ("AMAN", "WASPADA", "SIAGA", "AWAS", "INSUFFICIENT_DATA"):
        raise ValueError(f"Level keputusan '{resolved_final}' tidak valid.")

    # Record override status. Override reason and analysis notes are optional per operational relaxation.
    is_override = (resolved_final != rec_level) or (mode == "OPERATOR_OVERRIDE")
    if is_override:
        mode = "OPERATOR_OVERRIDE"

    v_from = (valid_from or rec_bundle["default_valid_from"]).strip()
    v_until = (valid_until or rec_bundle["default_valid_until"]).strip()
    try:
        dt_from = date.fromisoformat(v_from)
        dt_until = date.fromisoformat(v_until)
    except Exception:
        raise ValueError(f"Format masa berlaku tidak valid: {v_from} s/d {v_until} (gunakan YYYY-MM-DD).")

    if dt_from > dt_until:
        raise ValueError(f"Tanggal mulai berlaku ({v_from}) tidak boleh melebihi tanggal akhir berlaku ({v_until}).")

    final_narrative = (narrative or "").strip() or h_rec["default_narrative"]
    clean_operator = (operator or "klimatkepri").strip()

    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, final_level, workflow_status
                FROM cews_regional_warning_decisions
                WHERE period_id = %s AND region_code = %s AND hazard_code = %s
                """,
                (rec_bundle["period_id"], reg_meta["region_code"], h_code),
            )
            existing = cur.fetchone()
            prev_final = existing["final_level"] if existing else None

            cov_json = json.dumps(h_rec["station_coverage"], ensure_ascii=False)
            trig_json = json.dumps(h_rec["triggering_stations"], ensure_ascii=False)

            # Note: If a decision is modified after publication, workflow_status resets to DRAFT
            # so that a new revision must be reviewed/approved before publishing.
            cur.execute(
                """
                INSERT INTO cews_regional_warning_decisions
                (period_id, evaluation_period_label, observation_cutoff_date, forecast_issue_date,
                 region_code, sih3_polygon_key, region_name, hazard_code, hazard_name,
                 recommended_level, final_level, decision_mode, operator_override,
                 override_reason, analysis_notes, narrative, valid_from, valid_until,
                 workflow_status, station_coverage_json, triggering_stations_json, decided_by, decided_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 'DRAFT', %s, %s, %s, CURRENT_TIMESTAMP)
                ON DUPLICATE KEY UPDATE
                    evaluation_period_label = VALUES(evaluation_period_label),
                    observation_cutoff_date = VALUES(observation_cutoff_date),
                    forecast_issue_date = VALUES(forecast_issue_date),
                    recommended_level = VALUES(recommended_level),
                    final_level = VALUES(final_level),
                    decision_mode = VALUES(decision_mode),
                    operator_override = VALUES(operator_override),
                    override_reason = VALUES(override_reason),
                    analysis_notes = VALUES(analysis_notes),
                    narrative = VALUES(narrative),
                    valid_from = VALUES(valid_from),
                    valid_until = VALUES(valid_until),
                    workflow_status = 'DRAFT',
                    station_coverage_json = VALUES(station_coverage_json),
                    triggering_stations_json = VALUES(triggering_stations_json),
                    decided_by = VALUES(decided_by),
                    decided_at = CURRENT_TIMESTAMP
                """,
                (
                    rec_bundle["period_id"],
                    rec_bundle["evaluation_period"],
                    rec_bundle["observation_cutoff_date"],
                    rec_bundle["forecast_issue_date"],
                    reg_meta["region_code"],
                    reg_meta["sih3_polygon_key"],
                    reg_meta["region_name"],
                    h_code,
                    HAZARD_NAMES[h_code],
                    rec_level,
                    resolved_final,
                    mode,
                    1 if is_override else 0,
                    override_reason.strip() if override_reason else None,
                    analysis_notes.strip() if analysis_notes else None,
                    final_narrative,
                    v_from,
                    v_until,
                    cov_json,
                    trig_json,
                    clean_operator,
                ),
            )

            # Append audit log
            cur.execute(
                """
                INSERT INTO cews_regional_decision_audit_log
                (period_id, region_code, region_name, hazard_code, action_type,
                 recommended_level, previous_final_level, new_final_level,
                 decision_mode, operator_override, override_reason, analysis_notes,
                 narrative, operator, logged_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, CURRENT_TIMESTAMP)
                """,
                (
                    rec_bundle["period_id"],
                    reg_meta["region_code"],
                    reg_meta["region_name"],
                    h_code,
                    "OVERRIDE_DECISION" if is_override else "CONFIRM_RECOMMENDATION",
                    rec_level,
                    prev_final,
                    resolved_final,
                    mode,
                    1 if is_override else 0,
                    override_reason.strip() if override_reason else None,
                    analysis_notes.strip() if analysis_notes else None,
                    final_narrative,
                    clean_operator,
                ),
            )
        conn.commit()

    return {
        "status": "success",
        "period_id": rec_bundle["period_id"],
        "region_code": reg_meta["region_code"],
        "region_name": reg_meta["region_name"],
        "hazard_code": h_code,
        "recommended_level": rec_level,
        "final_level": resolved_final,
        "decision_mode": mode,
        "operator_override": is_override,
        "override_reason": override_reason.strip() if override_reason else None,
        "analysis_notes": analysis_notes.strip() if analysis_notes else None,
        "narrative": final_narrative,
        "valid_from": v_from,
        "valid_until": v_until,
        "decided_by": clean_operator,
        "workflow_status": "DRAFT",
    }


def save_bulk_regional_decisions_from_recommendations(
    period_id: str,
    valid_from: Optional[str] = None,
    valid_until: Optional[str] = None,
    operator: str = "klimatkepri",
    snap_override: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Initializes or synchronizes all 7 regions x 2 hazards (14 hazard slots) for a period,
    preserving any existing operator overrides while filling unconfirmed slots with DSS recommendations.
    """
    ensure_regional_warning_tables()
    rec_bundle = compute_regional_recommendations(period_id=period_id, snap_override=snap_override)
    v_from = valid_from or rec_bundle["default_valid_from"]
    v_until = valid_until or rec_bundle["default_valid_until"]

    saved_count = 0
    for r in rec_bundle["regions"]:
        rc = r["region_code"]
        for h_code in ("PDKM", "PDCHT"):
            hm = r["pdkm"] if h_code == "PDKM" else r["pdcht"]
            if hm["has_explicit_decision"] and hm["operator_override"]:
                # Preserve existing override, just update validity dates if provided
                save_regional_warning_decision(
                    period_id=rec_bundle["period_id"],
                    region_code=rc,
                    hazard_code=h_code,
                    decision_mode=hm["decision_mode"],
                    final_level=hm["final_level"],
                    override_reason=hm["override_reason"],
                    analysis_notes=hm["analysis_notes"],
                    narrative=hm["narrative"],
                    valid_from=v_from,
                    valid_until=v_until,
                    operator=operator,
                    snap_override=snap_override,
                )
            else:
                save_regional_warning_decision(
                    period_id=rec_bundle["period_id"],
                    region_code=rc,
                    hazard_code=h_code,
                    decision_mode="DSS_RECOMMENDATION",
                    final_level=hm["recommended_level"],
                    narrative=hm["narrative"],
                    valid_from=v_from,
                    valid_until=v_until,
                    operator=operator,
                    snap_override=snap_override,
                )
            saved_count += 1

    return {
        "status": "success",
        "period_id": rec_bundle["period_id"],
        "decisions_initialized": saved_count,
        "valid_from": v_from,
        "valid_until": v_until,
        "operator": operator,
    }


def get_regional_decisions_and_audit(period_id: Optional[str] = None) -> Dict[str, Any]:
    """Retrieves saved regional decisions and audit trail for a period."""
    ensure_regional_warning_tables()
    if not period_id:
        period_id = get_active_period()["period_id"]

    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT * FROM cews_regional_warning_decisions
                WHERE period_id = %s
                ORDER BY region_code ASC, hazard_code ASC
                """,
                (period_id,),
            )
            decisions = cur.fetchall()
            for d in decisions:
                for k in ("observation_cutoff_date", "forecast_issue_date", "valid_from", "valid_until"):
                    if d.get(k) and hasattr(d[k], "strftime"):
                        d[k] = d[k].strftime("%Y-%m-%d")
                for k in ("decided_at", "updated_at"):
                    if d.get(k) and hasattr(d[k], "strftime"):
                        d[k] = d[k].strftime("%Y-%m-%d %H:%M:%S")

            cur.execute(
                """
                SELECT * FROM cews_regional_decision_audit_log
                WHERE period_id = %s
                ORDER BY logged_at DESC, id DESC
                LIMIT 100
                """,
                (period_id,),
            )
            audits = cur.fetchall()
            for a in audits:
                if a.get("logged_at") and hasattr(a["logged_at"], "strftime"):
                    a["logged_at"] = a["logged_at"].strftime("%Y-%m-%d %H:%M:%S")

    return {
        "period_id": period_id,
        "total_decisions": len(decisions),
        "decisions": decisions,
        "audit_trail": audits,
    }


# ==============================================================================
# 6. SIH3 JSON BUILDER, SCHEMA VALIDATOR & PUBLICATION WORKFLOW ENGINE
# ==============================================================================
ACTIVE_WARNING_LEVELS = ("WASPADA", "SIAGA", "AWAS")
LEVEL_RANK = {
    "INSUFFICIENT_DATA": -1,
    "AMAN": 0,
    "NORMAL": 0,
    "WASPADA": 1,
    "SIAGA": 2,
    "AWAS": 3,
}
from backend.config import (
    INSTITUTION_NAME,
    PROVINCE_CODE,
    PROVINCE_NAME,
    SYSTEM_NAME,
)

ISO_TZ_RE = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:\d{2})$")
LEGACY_WRONG_INSTITUTION_RE = re.compile(r"Kelas\s+I(?!I)\b", re.IGNORECASE)


def _finite_or_none(val: Any, ndigits: Optional[int] = None) -> Optional[float]:
    if val is None:
        return None
    try:
        fval = float(val)
        if not math.isfinite(fval):
            return None
        return round(fval, ndigits) if ndigits is not None else fval
    except (TypeError, ValueError):
        return None


def _to_wib_iso(val: Optional[Any]) -> Optional[str]:
    """Normalizes datetime or timestamp strings into strict ISO-8601 with +07:00 timezone."""
    if val is None:
        return None
    if isinstance(val, datetime):
        dt = val.astimezone(WIB) if val.tzinfo else val.replace(tzinfo=WIB)
        return dt.isoformat(timespec="seconds")
    s = str(val).strip()
    if not s:
        return None
    if ISO_TZ_RE.match(s):
        return s
    # Handle MySQL/MariaDB 'YYYY-MM-DD HH:MM:SS' format
    m_sql = re.match(r"^(\d{4}-\d{2}-\d{2})[ T](\d{2}:\d{2}:\d{2})(?:\.\d+)?$", s)
    if m_sql:
        return f"{m_sql.group(1)}T{m_sql.group(2)}+07:00"
    try:
        dt = datetime.fromisoformat(s)
        dt = dt.astimezone(WIB) if dt.tzinfo else dt.replace(tzinfo=WIB)
        return dt.isoformat(timespec="seconds")
    except Exception:
        return None


def _build_structured_triggered_conditions(
    hazard_code: str,
    triggering_stations: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """
    Builds a uniform array of structured trigger-condition objects used identically
    at both Kecamatan and Kabupaten/Kota (Region) levels.
    Never fabricates values; uses None for unavailable fields and excludes non-finite numbers.
    """
    conditions: List[Dict[str, Any]] = []
    h_code = str(hazard_code or "").strip().upper()

    for stn in triggering_stations or []:
        scode = stn.get("station_id") or None
        sname = stn.get("station_name") or scode
        in_sum = stn.get("input_summary") or {}

        if h_code == "PDKM":
            hth_v = in_sum.get("hth_days")
            pb20_v = _finite_or_none(in_sum.get("pb20"), 1)
            spi90_v = _finite_or_none(in_sum.get("spi_90d"), 2)

            if hth_v is not None:
                try:
                    hth_int = int(hth_v)
                    if hth_int >= 21:
                        th_hth = 61 if hth_int >= 61 else (31 if hth_int >= 31 else 21)
                        conditions.append({
                            "indicator": "HTH",
                            "value": hth_int,
                            "unit": "days",
                            "operator": ">=",
                            "threshold": th_hth,
                            "period": "daily",
                            "station_code": scode,
                            "station_name": sname,
                            "description": f"Hari Tanpa Hujan (HTH) {hth_int} hari (>= {th_hth} hari)",
                        })
                except (TypeError, ValueError):
                    pass

            if pb20_v is not None and pb20_v > 70.0:
                conditions.append({
                    "indicator": "pb20",
                    "value": pb20_v,
                    "unit": "percent",
                    "operator": ">",
                    "threshold": 70.0,
                    "period": "dasarian",
                    "station_code": scode,
                    "station_name": sname,
                    "description": f"Peluang CH Dasarian < 20 mm sebesar {pb20_v:.1f}% (> 70.0%)",
                })

            if spi90_v is not None and spi90_v <= -1.0:
                th_spi = -2.0 if spi90_v <= -2.0 else (-1.5 if spi90_v <= -1.5 else -1.0)
                conditions.append({
                    "indicator": "SPI_90D",
                    "value": spi90_v,
                    "unit": "index",
                    "operator": "<=",
                    "threshold": th_spi,
                    "period": "90_days",
                    "station_code": scode,
                    "station_name": sname,
                    "description": f"SPI 90D sebesar {spi90_v:.2f} (<= {th_spi:.2f})",
                })

        elif h_code == "PDCHT":
            pa150_v = _finite_or_none(in_sum.get("pa150"), 1)
            pa200_v = _finite_or_none(in_sum.get("pa200"), 1)
            pa300_v = _finite_or_none(in_sum.get("pa300"), 1)
            pm300_v = _finite_or_none(in_sum.get("pm300"), 1)
            pm400_v = _finite_or_none(in_sum.get("pm400"), 1)
            pm500_v = _finite_or_none(in_sum.get("pm500"), 1)

            if pa300_v is not None and pa300_v > 50.0:
                conditions.append({
                    "indicator": "pa300",
                    "value": pa300_v,
                    "unit": "percent",
                    "operator": ">",
                    "threshold": 50.0,
                    "period": "dasarian",
                    "station_code": scode,
                    "station_name": sname,
                    "description": f"Peluang CH Dasarian > 300 mm sebesar {pa300_v:.1f}% (> 50.0%)",
                })
            elif pa200_v is not None and pa200_v > 50.0:
                conditions.append({
                    "indicator": "pa200",
                    "value": pa200_v,
                    "unit": "percent",
                    "operator": ">",
                    "threshold": 50.0,
                    "period": "dasarian",
                    "station_code": scode,
                    "station_name": sname,
                    "description": f"Peluang CH Dasarian > 200 mm sebesar {pa200_v:.1f}% (> 50.0%)",
                })
            elif pa150_v is not None and pa150_v > 50.0:
                conditions.append({
                    "indicator": "pa150",
                    "value": pa150_v,
                    "unit": "percent",
                    "operator": ">",
                    "threshold": 50.0,
                    "period": "dasarian",
                    "station_code": scode,
                    "station_name": sname,
                    "description": f"Peluang CH Dasarian > 150 mm sebesar {pa150_v:.1f}% (> 50.0%)",
                })

            if pm500_v is not None and pm500_v > 50.0:
                conditions.append({
                    "indicator": "pa500_monthly",
                    "value": pm500_v,
                    "unit": "percent",
                    "operator": ">",
                    "threshold": 50.0,
                    "period": "monthly",
                    "station_code": scode,
                    "station_name": sname,
                    "description": f"Peluang CH Bulanan > 500 mm sebesar {pm500_v:.1f}% (> 50.0%)",
                })
            elif pm400_v is not None and pm400_v > 50.0:
                conditions.append({
                    "indicator": "pa400_monthly",
                    "value": pm400_v,
                    "unit": "percent",
                    "operator": ">",
                    "threshold": 50.0,
                    "period": "monthly",
                    "station_code": scode,
                    "station_name": sname,
                    "description": f"Peluang CH Bulanan > 400 mm sebesar {pm400_v:.1f}% (> 50.0%)",
                })
            elif pm300_v is not None and pm300_v > 50.0:
                conditions.append({
                    "indicator": "pa300_monthly",
                    "value": pm300_v,
                    "unit": "percent",
                    "operator": ">",
                    "threshold": 50.0,
                    "period": "monthly",
                    "station_code": scode,
                    "station_name": sname,
                    "description": f"Peluang CH Bulanan > 300 mm sebesar {pm300_v:.1f}% (> 50.0%)",
                })

    return conditions


def _synthesize_entity_decision(
    entity_label: str,
    rec_p: str,
    rec_c: str,
    fin_p: str,
    fin_c: str,
    ov_reason_p: Optional[str],
    ov_reason_c: Optional[str],
    narrative_p: Optional[str],
    narrative_c: Optional[str],
    operator_name: Optional[str],
    decided_at_iso: Optional[str],
) -> Dict[str, Any]:
    """
    Deterministically constructs hazard_assessments (PDKM & PDCHT, 8 fields each),
    active warnings (0, 1, or 2 simultaneous active warnings), overall_status,
    final_decision (7 fields), and operator_decision (2 fields) while preserving
    original DSS recommendations unchanged.
    """
    rec_p = _normalize_warning_level(rec_p)
    rec_c = _normalize_warning_level(rec_c)
    fin_p = _normalize_warning_level(fin_p)
    fin_c = _normalize_warning_level(fin_c)

    ov_p = fin_p != rec_p
    ov_c = fin_c != rec_c
    clean_ov_p = str(ov_reason_p).strip() if (ov_p and ov_reason_p and str(ov_reason_p).strip()) else None
    clean_ov_c = str(ov_reason_c).strip() if (ov_c and ov_reason_c and str(ov_reason_c).strip()) else None

    narr_p = (narrative_p or "").strip() or (
        f"Evaluasi PDKM untuk {entity_label}: rekomendasi {rec_p}, keputusan final {fin_p}."
    )
    narr_c = (narrative_c or "").strip() or (
        f"Evaluasi PDCHT untuk {entity_label}: rekomendasi {rec_c}, keputusan final {fin_c}."
    )

    hazard_assessments = {
        "PDKM": {
            "hazard_code": "PDKM",
            "hazard_name": HAZARD_NAMES["PDKM"],
            "recommended_level": rec_p,
            "final_level": fin_p,
            "decision_source": "OPERATOR_OVERRIDE" if ov_p else "DSS_RECOMMENDATION",
            "operator_override": ov_p,
            "override_reason": clean_ov_p,
            "narrative": narr_p,
        },
        "PDCHT": {
            "hazard_code": "PDCHT",
            "hazard_name": HAZARD_NAMES["PDCHT"],
            "recommended_level": rec_c,
            "final_level": fin_c,
            "decision_source": "OPERATOR_OVERRIDE" if ov_c else "DSS_RECOMMENDATION",
            "operator_override": ov_c,
            "override_reason": clean_ov_c,
            "narrative": narr_c,
        },
    }

    p_active = fin_p in ACTIVE_WARNING_LEVELS
    c_active = fin_c in ACTIVE_WARNING_LEVELS

    warnings: List[Dict[str, Any]] = []
    if p_active:
        warnings.append({
            "hazard_code": "PDKM",
            "hazard_name": HAZARD_NAMES["PDKM"],
            "recommended_level": rec_p,
            "final_level": fin_p,
            "decision_source": "OPERATOR_OVERRIDE" if ov_p else "DSS_RECOMMENDATION",
            "operator_override": ov_p,
            "override_reason": clean_ov_p,
            "narrative": f"Peringatan Dini PDKM level {fin_p} di {entity_label}.",
        })
    if c_active:
        warnings.append({
            "hazard_code": "PDCHT",
            "hazard_name": HAZARD_NAMES["PDCHT"],
            "recommended_level": rec_c,
            "final_level": fin_c,
            "decision_source": "OPERATOR_OVERRIDE" if ov_c else "DSS_RECOMMENDATION",
            "operator_override": ov_c,
            "override_reason": clean_ov_c,
            "narrative": f"Peringatan Dini PDCHT level {fin_c} di {entity_label}.",
        })

    if p_active and c_active:
        overall_level = fin_p if LEVEL_RANK[fin_p] >= LEVEL_RANK[fin_c] else fin_c
        warning_type: Optional[str] = "MULTI_HAZARD"
        dec_status = "ACTIVE"
    elif p_active:
        overall_level = fin_p
        warning_type = "PDKM"
        dec_status = "ACTIVE"
    elif c_active:
        overall_level = fin_c
        warning_type = "PDCHT"
        dec_status = "ACTIVE"
    elif fin_p == "INSUFFICIENT_DATA" or fin_c == "INSUFFICIENT_DATA":
        # Never disguise INSUFFICIENT_DATA as AMAN unless explicitly overridden to AMAN on both hazards
        overall_level = "INSUFFICIENT_DATA"
        warning_type = None
        dec_status = "INSUFFICIENT_DATA"
    else:
        overall_level = "AMAN"
        warning_type = None
        dec_status = "NONE"

    is_override = bool(ov_p or ov_c)
    reasons_parts = []
    if clean_ov_p:
        reasons_parts.append(clean_ov_p)
    if clean_ov_c and clean_ov_c not in reasons_parts:
        reasons_parts.append(clean_ov_c)
    combined_ov_reason = "; ".join(reasons_parts) if reasons_parts else None

    final_decision = {
        "warning_type": warning_type,
        "level": overall_level,
        "status": dec_status,
        "is_override": is_override,
        "override_reason": combined_ov_reason,
        "operator": operator_name or "DSS-PIK",
        "decided_at": decided_at_iso,
    }
    operator_decision = {
        "decision_source": "OPERATOR_OVERRIDE" if is_override else "DSS_RECOMMENDATION",
        "override_reason": combined_ov_reason if is_override else None,
    }

    return {
        "overall_status": overall_level,
        "warnings": warnings,
        "hazard_assessments": hazard_assessments,
        "final_decision": final_decision,
        "operator_decision": operator_decision,
    }


def _generate_publication_id(period_id: str, cutoff_date: str) -> str:
    """Generates a deterministic base publication ID e.g. DSSPIK-20261101-001."""
    clean_d = re.sub(r"[^0-9]", "", cutoff_date or "")
    if len(clean_d) != 8:
        clean_d = datetime.now(WIB).strftime("%Y%m%d")
    # Derive 3-digit sequence from period_id (month + dasarian) so each period has a unique base ID
    m = re.match(r"^(\d{4})-(\d{2})-das(\d)$", str(period_id).strip(), re.IGNORECASE)
    if m:
        seq = f"{int(m.group(2)):02d}{int(m.group(3)):01d}"
    else:
        seq = "001"
    return f"DSSPIK-{clean_d}-{seq}"


def _build_standardized_decision_payload(
    rec_bundle: Dict[str, Any],
    kec_bundle: Dict[str, Any],
    publication_meta: Dict[str, Any],
    valid_from: str,
    valid_until: str,
    generated_at_iso: str,
    regency_overrides: Optional[Dict[str, Dict[str, Any]]] = None,
    kecamatan_overrides: Optional[Dict[str, Dict[str, Any]]] = None,
    default_operator: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Canonical decision-based JSON serializer for DSS-PIK.
    Produces the standardized 10-field top-level schema oriented around
    hazard assessments, DSS recommendations, operator decisions, and warning status
    across all 59 Kecamatan and 7 Kabupaten/Kota of Kepulauan Riau.
    """
    pid = rec_bundle["period_id"]
    m_p = re.match(r"^(\d{4})-(\d{1,2})-das(\d)$", str(pid).strip())
    now_wib = get_current_server_time_wib()
    year_val = int(m_p.group(1)) if m_p else now_wib.year
    month_val = int(m_p.group(2)) if m_p else now_wib.month
    das_val = int(m_p.group(3)) if m_p else 1

    reg_ov_map = regency_overrides or {}
    kec_ov_map = kecamatan_overrides or {}

    # 1. Build 7 canonical Kabupaten/Kota (regions) first so station-less kecamatan can inherit cleanly
    standard_regions: List[Dict[str, Any]] = []
    parent_decision_by_poly: Dict[str, Dict[str, Any]] = {}

    for r in rec_bundle["regions"]:
        rc = r["region_code"]
        poly = r["sih3_polygon_key"]
        rname = r["region_name"]
        cov = r["station_coverage"]
        total_stns = int(cov.get("total") or cov.get("total_master", 0))
        manual_stns = int(cov.get("manual", cov.get("manual_stations", 0)))
        arg_stns = int(cov.get("arg", cov.get("arg_stations", 0)))
        valid_stns = int(cov.get("valid", 0))
        missing_stns = int(cov.get("missing", max(0, total_stns - valid_stns)))
        cov_pct = round((valid_stns / total_stns) * 100.0, 1) if total_stns > 0 else 0.0

        rec_p = _normalize_warning_level(r["pdkm"]["recommended_level"])
        rec_c = _normalize_warning_level(r["pdcht"]["recommended_level"])

        pdkm_trig = _build_structured_triggered_conditions("PDKM", r["pdkm"].get("triggering_stations", []))
        pdcht_trig = _build_structured_triggered_conditions("PDCHT", r["pdcht"].get("triggering_stations", []))

        explicit_reg = reg_ov_map.get(poly) or reg_ov_map.get(rc) or reg_ov_map.get(rname)
        if explicit_reg is not None:
            fin_p = _normalize_warning_level(explicit_reg["fin_p"])
            fin_c = _normalize_warning_level(explicit_reg["fin_c"])
            ov_reason_p = explicit_reg.get("ov_reason_p")
            ov_reason_c = explicit_reg.get("ov_reason_c")
            op_name = explicit_reg.get("operator") or default_operator or "DSS-PIK"
            decided_at_iso = _to_wib_iso(explicit_reg.get("decided_at")) or generated_at_iso
            narr_p = explicit_reg.get("narrative_p")
            narr_c = explicit_reg.get("narrative_c")
        else:
            # Use persisted DB decisions merged in rec_bundle (which fall back to DSS recommendations)
            fin_p = _normalize_warning_level(r["pdkm"]["final_level"])
            fin_c = _normalize_warning_level(r["pdcht"]["final_level"])
            ov_reason_p = r["pdkm"].get("override_reason")
            ov_reason_c = r["pdcht"].get("override_reason")
            op_name = r["pdkm"].get("decided_by") or r["pdcht"].get("decided_by") or default_operator or "DSS-PIK"
            decided_at_iso = (
                _to_wib_iso(r["pdkm"].get("decided_at"))
                or _to_wib_iso(r["pdcht"].get("decided_at"))
                or generated_at_iso
            )
            narr_p = r["pdkm"].get("narrative")
            narr_c = r["pdcht"].get("narrative")

        synth = _synthesize_entity_decision(
            entity_label=rname,
            rec_p=rec_p,
            rec_c=rec_c,
            fin_p=fin_p,
            fin_c=fin_c,
            ov_reason_p=ov_reason_p,
            ov_reason_c=ov_reason_c,
            narrative_p=narr_p,
            narrative_c=narr_c,
            operator_name=op_name,
            decided_at_iso=decided_at_iso,
        )

        parent_decision_by_poly[poly] = {
            "fin_p": fin_p,
            "fin_c": fin_c,
            "ov_reason_p": ov_reason_p,
            "ov_reason_c": ov_reason_c,
            "operator": op_name,
            "decided_at": decided_at_iso,
            "data_status": r["data_status"],
            "has_valid_decision": synth["overall_status"] != "INSUFFICIENT_DATA",
        }

        standard_regions.append({
            "region_code": rc,
            "region_name": rname,
            "sih3_polygon_key": poly,
            "data_status": r["data_status"],
            "overall_region_status": synth["overall_status"],
            "station_coverage": {
                "total": total_stns,
                "manual_stations": manual_stns,
                "arg_stations": arg_stns,
                "valid": valid_stns,
                "missing": missing_stns,
                "percentage": cov_pct,
            },
            "warnings": synth["warnings"],
            "hazard_assessments": synth["hazard_assessments"],
            "data_coverage": {
                "total_stations": total_stns,
                "valid_stations": valid_stns,
                "coverage_percent": cov_pct,
                "coverage_percentage": cov_pct,
                "status": "INSUFFICIENT_DATA" if r["data_status"] == "INSUFFICIENT_DATA" else "SUFFICIENT",
            },
            "recommendations": {
                "PDKM": {
                    "level": rec_p,
                    "triggered_conditions": pdkm_trig,
                },
                "PDCHT": {
                    "level": rec_c,
                    "triggered_conditions": pdcht_trig,
                },
            },
            "final_decision": synth["final_decision"],
            "operator_decision": synth["operator_decision"],
        })

    # 2. Build all 59 canonical Kecamatan with explicit inheritance & INSUFFICIENT_DATA protection
    standard_kecamatan: List[Dict[str, Any]] = []
    for k_item in kec_bundle["kecamatan"]:
        kid = k_item["kecamatan_id"]
        kname = k_item["kecamatan_name"]
        kabkot = k_item["kabkot"]
        poly = k_item["parent_polygon_key"]
        stn_count = int(k_item.get("stations_count", 0))
        parent_dec = parent_decision_by_poly.get(poly)

        rec_p = _normalize_warning_level(k_item["pdkm"]["recommended_level"])
        rec_c = _normalize_warning_level(k_item["pdcht"]["recommended_level"])

        k_pdkm_trig = _build_structured_triggered_conditions("PDKM", k_item["pdkm"].get("triggering_stations", []))
        k_pdcht_trig = _build_structured_triggered_conditions("PDCHT", k_item["pdcht"].get("triggering_stations", []))

        explicit_kec = kec_ov_map.get(kid)
        if explicit_kec is not None:
            k_fin_p = _normalize_warning_level(explicit_kec["fin_p"])
            k_fin_c = _normalize_warning_level(explicit_kec["fin_c"])
            k_ov_p = explicit_kec.get("ov_reason_p")
            k_ov_c = explicit_kec.get("ov_reason_c")
            k_op = explicit_kec.get("operator") or default_operator or "DSS-PIK"
            k_dec_at = _to_wib_iso(explicit_kec.get("decided_at")) or generated_at_iso
            # Station-less kecamatan that matches parent decision reflects parent inheritance;
            # kecamatan with own stations or independent override has inherited_from_parent = False.
            if stn_count == 0 and parent_dec is not None:
                inherited = (k_fin_p == parent_dec["fin_p"] and k_fin_c == parent_dec["fin_c"])
            else:
                inherited = False
        else:
            if stn_count == 0:
                if parent_dec is not None and parent_dec["has_valid_decision"]:
                    k_fin_p = parent_dec["fin_p"]
                    k_fin_c = parent_dec["fin_c"]
                    k_ov_p = parent_dec["ov_reason_p"]
                    k_ov_c = parent_dec["ov_reason_c"]
                    k_op = parent_dec["operator"]
                    k_dec_at = parent_dec["decided_at"]
                    inherited = True
                else:
                    # Rule 5: No stations AND no valid parent decision -> strictly INSUFFICIENT_DATA
                    k_fin_p = "INSUFFICIENT_DATA"
                    k_fin_c = "INSUFFICIENT_DATA"
                    k_ov_p = None
                    k_ov_c = None
                    k_op = default_operator or "DSS-PIK"
                    k_dec_at = generated_at_iso
                    inherited = bool(parent_dec is not None)
            else:
                # Kecamatan has its own stations: use kecamatan evaluation (do not fabricate AMAN)
                k_fin_p = rec_p
                k_fin_c = rec_c
                k_ov_p = None
                k_ov_c = None
                k_op = default_operator or "DSS-PIK"
                k_dec_at = generated_at_iso
                inherited = False

        k_synth = _synthesize_entity_decision(
            entity_label=f"Kecamatan {kname}, {kabkot}",
            rec_p=rec_p,
            rec_c=rec_c,
            fin_p=k_fin_p,
            fin_c=k_fin_c,
            ov_reason_p=k_ov_p,
            ov_reason_c=k_ov_c,
            narrative_p=None,
            narrative_c=None,
            operator_name=k_op,
            decided_at_iso=k_dec_at,
        )

        standard_kecamatan.append({
            "kecamatan_id": kid,
            "kecamatan_name": kname,
            "kabkot": kabkot,
            "parent_polygon_key": poly,
            "stations_count": stn_count,
            "inherited_from_parent": inherited,
            "overall_status": k_synth["overall_status"],
            "warnings": k_synth["warnings"],
            "hazard_assessments": k_synth["hazard_assessments"],
            "recommendations": {
                "PDKM": {
                    "level": rec_p,
                    "triggered_conditions": k_pdkm_trig,
                },
                "PDCHT": {
                    "level": rec_c,
                    "triggered_conditions": k_pdcht_trig,
                },
            },
            "final_decision": k_synth["final_decision"],
        })

    # 3. Assemble exact 10-field canonical top-level document
    payload = {
        "schema_version": "1.0.0",
        "system": SYSTEM_NAME,
        "institution": INSTITUTION_NAME,
        "publication": {
            "publication_id": publication_meta["publication_id"],
            "revision": int(publication_meta["revision"]),
            "status": publication_meta["status"],
            "generated_at": generated_at_iso,
            "published_at": publication_meta["published_at"],
            "valid_from": valid_from,
            "valid_until": valid_until,
            "approved_by": publication_meta["approved_by"],
            "published_by": publication_meta["published_by"],
            "revision_reason": publication_meta["revision_reason"],
        },
        "source": {
            "period_id": pid,
            "evaluation_period": rec_bundle["evaluation_period"],
            "observation_cutoff_date": rec_bundle.get("observation_cutoff_date", valid_from),
            "forecast_issue_date": rec_bundle.get("forecast_issue_date", None),
            "spi_reference_date": rec_bundle.get("spi_reference_date", None),
            "institution": INSTITUTION_NAME,
            "system": SYSTEM_NAME,
        },
        "generated_at": generated_at_iso,
        "period": {
            "resolution": "DASARIAN",
            "year": year_val,
            "month": month_val,
            "dasarian": das_val,
            "label": rec_bundle["evaluation_period"],
            "valid_from": valid_from,
            "valid_until": valid_until,
        },
        "province": {
            "code": PROVINCE_CODE,
            "name": PROVINCE_NAME,
        },
        "kecamatan": standard_kecamatan,
        "regions": standard_regions,
    }
    return payload


def build_sih3_publication_json(
    period_id: Optional[str] = None,
    valid_from: Optional[str] = None,
    valid_until: Optional[str] = None,
    publication_status: Optional[str] = None,
    revision: Optional[int] = None,
    publication_id: Optional[str] = None,
    approved_by: Optional[str] = None,
    published_by: Optional[str] = None,
    published_at_iso: Optional[str] = None,
    revision_reason: Optional[str] = None,
    snap_override: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Constructs the standardized Decision-Based SIH3 Warning JSON payload across
    all 59 Kecamatan and 7 Kabupaten/Kota of Kepulauan Riau.
    Reads actual publication metadata from cews_sih3_publications when not explicitly supplied.
    """
    rec_bundle = compute_regional_recommendations(period_id=period_id, snap_override=snap_override)
    kec_bundle = compute_kecamatan_recommendations(period_id=rec_bundle["period_id"], snap_override=snap_override)
    pid = rec_bundle["period_id"]
    now_iso = get_current_server_time_wib().isoformat(timespec="seconds")

    latest_pub = rec_bundle.get("latest_publication")
    v_from = (valid_from or (latest_pub["valid_from"] if latest_pub else None) or rec_bundle["default_valid_from"]).strip()
    v_until = (valid_until or (latest_pub["valid_until"] if latest_pub else None) or rec_bundle["default_valid_until"]).strip()

    resolved_pub_id = publication_id or (latest_pub["publication_id"] if latest_pub else _generate_publication_id(pid, v_from))
    resolved_rev = int(revision) if revision is not None else (int(latest_pub["revision"]) if latest_pub else 1)
    resolved_status = publication_status or (latest_pub["status"] if latest_pub else "Aktif")
    resolved_approved_by = approved_by if approved_by is not None else (latest_pub.get("approved_by") if latest_pub else None)
    resolved_published_by = (
        (published_by if published_by is not None else (latest_pub.get("published_by") if latest_pub else None))
        if resolved_status == "PUBLISHED"
        else None
    )
    resolved_published_at = (
        _to_wib_iso(published_at_iso or (latest_pub.get("published_at") if latest_pub else None) or now_iso)
        if resolved_status == "PUBLISHED"
        else None
    )
    resolved_rev_reason = revision_reason if revision_reason is not None else (latest_pub.get("revision_reason") if latest_pub else None)

    publication_meta = {
        "publication_id": resolved_pub_id,
        "revision": resolved_rev,
        "status": resolved_status,
        "published_at": resolved_published_at,
        "approved_by": resolved_approved_by if resolved_status in ("APPROVED", "PUBLISHED") else None,
        "published_by": resolved_published_by,
        "revision_reason": resolved_rev_reason,
    }

    return _build_standardized_decision_payload(
        rec_bundle=rec_bundle,
        kec_bundle=kec_bundle,
        publication_meta=publication_meta,
        valid_from=v_from,
        valid_until=v_until,
        generated_at_iso=now_iso,
    )


def validate_sih3_json_payload(payload: Dict[str, Any]) -> Dict[str, Any]:
    """
    Comprehensive 18-point Quality Control & Structural Validator for standardized
    DSS-PIK Decision-Based JSON outputs:
      1. Valid JSON without NaN or Infinity (strict RFC 8259 via allow_nan=False).
      2. Exact 10 top-level fields (no root 'stations' or 'data_completeness').
      3. All 59 canonical Kepulauan Riau kecamatan present exactly once (no duplicates).
      4. All 7 canonical Kabupaten/Kota present exactly once (no duplicates).
      5. Valid parent_polygon_key relation on every kecamatan.
      6. Complete PDKM & PDCHT hazard_assessments, recommendations, warnings, final_decision.
      7. Strict consistency between overall_status / overall_region_status and final_decision.level.
      8. Warnings only contain active levels (WASPADA/SIAGA/AWAS) matching hazard_assessments.
      9. Operator override consistency (operator_override == (final_level != recommended_level)).
     10. Original recommendation immutability (recommended_level == recommendations[h].level).
     11. INSUFFICIENT_DATA never silently disguised as AMAN.
     12. ISO-8601 timestamps with explicit timezone (+07:00 or Z).
     13. Consistent structured dict objects in triggered_conditions on both kecamatan & regions.
     14. Mathematical consistency of station_coverage and data_coverage.
     15. Publication status consistency with published_at / published_by / approved_by.
    """
    errors: List[str] = []
    warnings_info: List[str] = []

    if not isinstance(payload, dict):
        return {
            "valid": False,
            "schema_version": None,
            "regions_count": 0,
            "kecamatan_count": 0,
            "active_warnings_count": 0,
            "errors": ["Payload JSON harus berupa objek (dictionary)."],
            "warnings": [],
        }

    # 1. Strict JSON serializability & No NaN / Infinity check
    try:
        serialized = json.dumps(payload, allow_nan=False, ensure_ascii=False)
        json.loads(serialized)
    except (ValueError, TypeError) as e:
        errors.append(f"Payload gagal serialisasi JSON ketat (terdapat NaN/Infinity atau tipe tidak valid): {e}")

    # 2. Top-level exact field verification
    expected_top_keys = [
        "schema_version",
        "system",
        "institution",
        "publication",
        "source",
        "generated_at",
        "period",
        "province",
        "kecamatan",
        "regions",
    ]
    actual_top_keys = set(payload.keys())
    for forbidden in ("stations", "data_completeness"):
        if forbidden in actual_top_keys:
            errors.append(f"Atribut terlarang '{forbidden}' ditemukan di root payload publikasi utama.")
    missing_top = [k for k in expected_top_keys if k not in actual_top_keys]
    extra_top = sorted(actual_top_keys - set(expected_top_keys))
    if missing_top:
        errors.append(f"Atribut top-level yang hilang: {missing_top}.")
    if extra_top:
        errors.append(f"Atribut top-level tidak dikenal: {extra_top}.")

    if payload.get("schema_version") != "1.0.0":
        errors.append(f"schema_version tidak valid: '{payload.get('schema_version')}' (wajib '1.0.0').")
    if payload.get("system") != SYSTEM_NAME:
        errors.append(f"system tidak valid: '{payload.get('system')}' (wajib '{SYSTEM_NAME}').")
    root_inst = payload.get("institution")
    if not root_inst:
        errors.append("Atribut 'institution' wajib diisi.")
    elif root_inst != INSTITUTION_NAME:
        errors.append(
            f"Atribut 'institution' tidak sesuai identitas resmi: '{root_inst}' (wajib '{INSTITUTION_NAME}')."
        )
    if isinstance(root_inst, str) and LEGACY_WRONG_INSTITUTION_RE.search(root_inst):
        errors.append("Atribut 'institution' masih menggunakan identitas lama 'Kelas I' (wajib 'Kelas II').")
    if not ISO_TZ_RE.match(str(payload.get("generated_at", ""))):
        errors.append(f"generated_at '{payload.get('generated_at')}' wajib ISO-8601 lengkap dengan zona waktu.")

    # 3. Publication metadata validation
    pub = payload.get("publication")
    if not isinstance(pub, dict):
        errors.append("Bagian 'publication' wajib tersedia.")
    else:
        req_pub = (
            "publication_id", "revision", "status", "generated_at", "published_at",
            "valid_from", "valid_until", "approved_by", "published_by", "revision_reason",
        )
        miss_pub = [k for k in req_pub if k not in pub]
        if miss_pub:
            errors.append(f"Bagian 'publication' kehilangan atribut: {miss_pub}.")
        pub_id = str(pub.get("publication_id", ""))
        if not re.match(r"^DSSPIK-\d{8}-\d{3}$", pub_id):
            errors.append(f"Format publication_id '{pub_id}' tidak sesuai pola 'DSSPIK-YYYYMMDD-NNN'.")
        rev = pub.get("revision")
        if not isinstance(rev, int) or rev < 1:
            errors.append("Nilai 'publication.revision' wajib bilangan bulat >= 1.")
        st = pub.get("status")
        if st not in ("Aktif", "DRAFT", "REVIEW", "APPROVED", "PUBLISHED", "EXPIRED"):
            errors.append(f"Status publikasi '{st}' tidak dikenal.")
        if not ISO_TZ_RE.match(str(pub.get("generated_at", ""))):
            errors.append(f"publication.generated_at '{pub.get('generated_at')}' wajib ISO-8601 dengan zona waktu.")
        if st == "PUBLISHED":
            if not pub.get("published_at") or not ISO_TZ_RE.match(str(pub.get("published_at"))):
                errors.append("Status publikasi PUBLISHED wajib memiliki published_at berformat ISO-8601 dengan zona waktu.")
            if not pub.get("published_by"):
                errors.append("Status publikasi PUBLISHED wajib memiliki published_by.")
        else:
            if pub.get("published_at") is not None and not ISO_TZ_RE.match(str(pub.get("published_at"))):
                errors.append("publication.published_at jika terisi wajib berformat ISO-8601 dengan zona waktu.")

        vf = str(pub.get("valid_from", ""))
        vu = str(pub.get("valid_until", ""))
        try:
            d_from = date.fromisoformat(vf)
            d_until = date.fromisoformat(vu)
            if d_from > d_until:
                errors.append(f"Masa berlaku tidak valid: valid_from ({vf}) > valid_until ({vu}).")
        except Exception:
            errors.append(f"Format tanggal valid_from ({vf}) atau valid_until ({vu}) harus YYYY-MM-DD.")

    # 4. Source, Period, Province validation
    src = payload.get("source")
    if not isinstance(src, dict):
        errors.append("Bagian 'source' wajib tersedia.")
    else:
        for k in ("period_id", "evaluation_period", "observation_cutoff_date", "forecast_issue_date", "spi_reference_date", "institution", "system"):
            if k not in src:
                errors.append(f"source kehilangan atribut '{k}'.")
        src_inst = src.get("institution")
        if src_inst != INSTITUTION_NAME:
            errors.append(
                f"source.institution tidak sesuai identitas resmi: '{src_inst}' (wajib '{INSTITUTION_NAME}')."
            )
        if payload.get("institution") and src_inst != payload.get("institution"):
            errors.append(
                f"source.institution ('{src_inst}') tidak identik dengan root institution ('{payload.get('institution')}')."
            )
        if isinstance(src_inst, str) and LEGACY_WRONG_INSTITUTION_RE.search(src_inst):
            errors.append("source.institution masih menggunakan identitas lama 'Kelas I' (wajib 'Kelas II').")
        if not src.get("evaluation_period"):
            errors.append("source.evaluation_period wajib diisi.")
        if not re.match(r"^\d{4}-\d{2}-\d{2}$", str(src.get("observation_cutoff_date", ""))):
            errors.append("source.observation_cutoff_date wajib berformat YYYY-MM-DD.")

    per = payload.get("period")
    if not isinstance(per, dict):
        errors.append("Bagian 'period' wajib tersedia.")
    else:
        for k in ("resolution", "year", "month", "dasarian", "label", "valid_from", "valid_until"):
            if k not in per:
                errors.append(f"period kehilangan atribut '{k}'.")
        if "period_id" in per:
            errors.append("period tidak boleh mengandung atribut 'period_id' (gunakan source.period_id).")

    prov = payload.get("province")
    if not isinstance(prov, dict) or "code" not in prov or "name" not in prov:
        errors.append("Bagian 'province' wajib memiliki atribut 'code' dan 'name'.")

    # Shared validator for hazard_assessments, recommendations, warnings, and final_decision
    valid_levels = ("AMAN", "WASPADA", "SIAGA", "AWAS", "INSUFFICIENT_DATA")
    req_trig_keys = ("indicator", "value", "unit", "operator", "threshold", "period", "station_code", "station_name", "description")

    def _validate_decision_block(entity: Dict[str, Any], label: str, overall_key: str):
        overall_val = entity.get(overall_key)
        if overall_val not in valid_levels:
            errors.append(f"{label}.{overall_key} '{overall_val}' tidak valid.")

        ha = entity.get("hazard_assessments")
        recs = entity.get("recommendations")
        w_list = entity.get("warnings")
        fdec = entity.get("final_decision")

        if not isinstance(ha, dict) or "PDKM" not in ha or "PDCHT" not in ha:
            errors.append(f"{label}.hazard_assessments wajib memiliki PDKM dan PDCHT.")
        if not isinstance(recs, dict) or "PDKM" not in recs or "PDCHT" not in recs:
            errors.append(f"{label}.recommendations wajib memiliki PDKM dan PDCHT.")
        if not isinstance(w_list, list):
            errors.append(f"{label}.warnings wajib berupa array.")
        if not isinstance(fdec, dict):
            errors.append(f"{label}.final_decision wajib berupa objek.")
            return

        for k in ("warning_type", "level", "status", "is_override", "override_reason", "operator", "decided_at"):
            if k not in fdec:
                errors.append(f"{label}.final_decision kehilangan atribut '{k}'.")

        if fdec.get("level") != overall_val:
            errors.append(f"{label}.{overall_key} ({overall_val}) tidak konsisten dengan final_decision.level ({fdec.get('level')}).")

        if fdec.get("decided_at") is not None and not ISO_TZ_RE.match(str(fdec.get("decided_at"))):
            errors.append(f"{label}.final_decision.decided_at '{fdec.get('decided_at')}' wajib ISO-8601 dengan zona waktu.")

        active_from_ha: Dict[str, str] = {}
        any_ha_override = False
        if isinstance(ha, dict):
            for h_code in ("PDKM", "PDCHT"):
                h_obj = ha.get(h_code)
                if not isinstance(h_obj, dict):
                    errors.append(f"{label}.hazard_assessments.{h_code} bukan objek.")
                    continue
                for k in ("hazard_code", "hazard_name", "recommended_level", "final_level", "decision_source", "operator_override", "override_reason", "narrative"):
                    if k not in h_obj:
                        errors.append(f"{label}.hazard_assessments.{h_code} kehilangan atribut '{k}'.")
                rec_l = h_obj.get("recommended_level")
                fin_l = h_obj.get("final_level")
                ov = bool(h_obj.get("operator_override"))
                if rec_l not in valid_levels or fin_l not in valid_levels:
                    errors.append(f"{label}.hazard_assessments.{h_code} memiliki level tidak valid (rec={rec_l}, fin={fin_l}).")
                if (rec_l != fin_l) != ov:
                    errors.append(f"{label}.hazard_assessments.{h_code}: operator_override ({ov}) tidak konsisten dengan rec ({rec_l}) vs fin ({fin_l}).")
                if ov:
                    any_ha_override = True
                if isinstance(recs, dict) and isinstance(recs.get(h_code), dict):
                    if recs[h_code].get("level") != rec_l:
                        errors.append(f"{label}: recommendations.{h_code}.level ({recs[h_code].get('level')}) != hazard_assessments.{h_code}.recommended_level ({rec_l}).")
                if fin_l in ACTIVE_WARNING_LEVELS:
                    active_from_ha[h_code] = fin_l

        if bool(fdec.get("is_override")) != any_ha_override:
            errors.append(f"{label}.final_decision.is_override ({fdec.get('is_override')}) tidak konsisten dengan hazard_assessments ({any_ha_override}).")

        if isinstance(recs, dict):
            for h_code in ("PDKM", "PDCHT"):
                r_obj = recs.get(h_code)
                if not isinstance(r_obj, dict):
                    continue
                tconds = r_obj.get("triggered_conditions")
                if not isinstance(tconds, list):
                    errors.append(f"{label}.recommendations.{h_code}.triggered_conditions wajib berupa array.")
                else:
                    for tc_idx, tc in enumerate(tconds):
                        if not isinstance(tc, dict):
                            errors.append(f"{label}.recommendations.{h_code}.triggered_conditions[{tc_idx}] wajib berupa objek, ditemukan {type(tc).__name__}.")
                        else:
                            miss_tc = [k for k in req_trig_keys if k not in tc]
                            if miss_tc:
                                errors.append(f"{label}.recommendations.{h_code}.triggered_conditions[{tc_idx}] kehilangan key: {miss_tc}.")

        if isinstance(w_list, list):
            seen_hazards = set()
            for w_idx, w in enumerate(w_list):
                if not isinstance(w, dict):
                    errors.append(f"{label}.warnings[{w_idx}] bukan objek.")
                    continue
                hc = w.get("hazard_code")
                fl = w.get("final_level")
                if hc not in ("PDKM", "PDCHT"):
                    errors.append(f"{label}.warnings[{w_idx}].hazard_code '{hc}' tidak valid.")
                if hc in seen_hazards:
                    errors.append(f"Duplikasi hazard_code '{hc}' pada {label}.warnings.")
                seen_hazards.add(hc)
                if fl not in ACTIVE_WARNING_LEVELS:
                    errors.append(f"{label}.warnings[{w_idx}].final_level '{fl}' bukan level peringatan aktif.")
                if hc in active_from_ha and active_from_ha[hc] != fl:
                    errors.append(f"{label}.warnings[{w_idx}] level ({fl}) != hazard_assessments.{hc}.final_level ({active_from_ha[hc]}).")
                if hc not in active_from_ha:
                    errors.append(f"{label}.warnings memuat {hc} padahal tidak aktif pada hazard_assessments.")
                if not w.get("narrative") or not str(w.get("narrative")).strip():
                    errors.append(f"{label}.warnings[{w_idx}].narrative tidak boleh kosong.")
            if seen_hazards != set(active_from_ha.keys()):
                errors.append(f"{label}.warnings ({sorted(seen_hazards)}) tidak sesuai hazard aktif ({sorted(active_from_ha.keys())}).")

    # 5. Regions (7 Kabupaten/Kota) validation
    regions = payload.get("regions")
    if not isinstance(regions, list):
        errors.append("Bagian 'regions' wajib berupa array.")
    else:
        if len(regions) != 7:
            errors.append(f"Jumlah wilayah dalam 'regions' harus tepat 7 kabupaten/kota, ditemukan {len(regions)}.")

        seen_codes = set()
        for idx, reg in enumerate(regions):
            if not isinstance(reg, dict):
                errors.append(f"Elemen regions[{idx}] bukan objek.")
                continue
            rc = str(reg.get("region_code", ""))
            rname = str(reg.get("region_name", ""))
            if rc not in REGION_BY_CODE:
                errors.append(f"Kode wilayah '{rc}' pada regions[{idx}] tidak terdaftar di Kepulauan Riau.")
            else:
                if rc in seen_codes:
                    errors.append(f"Duplikasi kode wilayah '{rc}' pada daftar regions.")
                seen_codes.add(rc)
                expected_name = REGION_BY_CODE[rc]["region_name"]
                if rname != expected_name:
                    errors.append(f"Nama wilayah untuk kode '{rc}' harus '{expected_name}', ditemukan '{rname}'.")

            d_status = reg.get("data_status")
            if d_status not in ("COMPLETE", "PARTIAL", "INSUFFICIENT_DATA"):
                errors.append(f"data_status '{d_status}' pada {rname} tidak valid.")

            # Mathematical consistency between station_coverage and data_coverage
            cov = reg.get("station_coverage")
            dcov = reg.get("data_coverage")
            if not isinstance(cov, dict) or any(k not in cov for k in ("total", "manual_stations", "arg_stations", "valid", "missing", "percentage")):
                errors.append(f"station_coverage pada {rname} tidak lengkap.")
            else:
                if cov["valid"] + cov["missing"] != cov["total"]:
                    errors.append(f"station_coverage {rname}: valid ({cov['valid']}) + missing ({cov['missing']}) != total ({cov['total']}).")
                if cov["manual_stations"] + cov["arg_stations"] != cov["total"]:
                    errors.append(f"station_coverage {rname}: manual ({cov['manual_stations']}) + arg ({cov['arg_stations']}) != total ({cov['total']}).")
                expected_pct = round((cov["valid"] / cov["total"]) * 100.0, 1) if cov["total"] > 0 else 0.0
                if abs(float(cov["percentage"]) - expected_pct) > 0.11:
                    errors.append(f"station_coverage {rname}: percentage ({cov['percentage']}) != expected ({expected_pct}).")

            if not isinstance(dcov, dict) or any(k not in dcov for k in ("total_stations", "valid_stations", "coverage_percent", "coverage_percentage", "status")):
                errors.append(f"data_coverage pada {rname} tidak lengkap.")
            elif isinstance(cov, dict) and all(k in cov for k in ("total", "valid", "percentage")):
                if dcov["total_stations"] != cov["total"] or dcov["valid_stations"] != cov["valid"]:
                    errors.append(f"data_coverage pada {rname} tidak konsisten dengan station_coverage.")
                if dcov["coverage_percent"] != dcov["coverage_percentage"] or float(dcov["coverage_percent"]) != float(cov["percentage"]):
                    errors.append(f"Persentase data_coverage pada {rname} tidak konsisten dengan station_coverage.")

            op_dec = reg.get("operator_decision")
            if not isinstance(op_dec, dict) or "decision_source" not in op_dec or "override_reason" not in op_dec:
                errors.append(f"operator_decision pada {rname} tidak lengkap.")

            _validate_decision_block(reg, f"regions[{rname}]", "overall_region_status")

        missing_codes = set(REGION_BY_CODE.keys()) - seen_codes
        if missing_codes:
            errors.append(f"Wilayah belum lengkap. Kode wilayah yang hilang: {sorted(missing_codes)}.")

    # 6. Kecamatan (59 Kecamatan) validation
    kec_list = payload.get("kecamatan")
    if not isinstance(kec_list, list):
        errors.append("Bagian 'kecamatan' wajib berupa array.")
    else:
        canonical_kec_ids = {k["kecamatan_id"] for k in get_canonical_kecamatan_list()}
        if len(kec_list) != len(canonical_kec_ids):
            errors.append(f"Jumlah kecamatan harus tepat {len(canonical_kec_ids)}, ditemukan {len(kec_list)}.")
        seen_kids = set()
        for idx, k_obj in enumerate(kec_list):
            if not isinstance(k_obj, dict):
                errors.append(f"Elemen kecamatan[{idx}] bukan objek.")
                continue
            kid = str(k_obj.get("kecamatan_id", ""))
            if kid not in canonical_kec_ids:
                errors.append(f"kecamatan_id '{kid}' tidak terdaftar dalam 59 kecamatan kanonikal Kepulauan Riau.")
            elif kid in seen_kids:
                errors.append(f"Duplikasi kecamatan_id '{kid}'.")
            else:
                seen_kids.add(kid)
            ppoly = str(k_obj.get("parent_polygon_key", ""))
            if ppoly not in REGION_BY_POLYGON_KEY:
                errors.append(f"kecamatan[{kid}].parent_polygon_key '{ppoly}' tidak merujuk ke 7 wilayah induk yang valid.")
            if not isinstance(k_obj.get("stations_count"), int) or k_obj.get("stations_count") < 0:
                errors.append(f"kecamatan[{kid}].stations_count wajib bilangan bulat >= 0.")
            if not isinstance(k_obj.get("inherited_from_parent"), bool):
                errors.append(f"kecamatan[{kid}].inherited_from_parent wajib boolean.")
            _validate_decision_block(k_obj, f"kecamatan[{kid}]", "overall_status")

        missing_kids = canonical_kec_ids - seen_kids
        if missing_kids:
            errors.append(f"Daftar kecamatan belum lengkap; hilang {len(missing_kids)} kecamatan: {sorted(missing_kids)[:5]}.")

    # 7. JSON Schema validation against docs/schemas/sih3_regional_warning.schema.json
    if SCHEMA_PATH.exists():
        try:
            import jsonschema
            schema_obj = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
            validator = jsonschema.Draft202012Validator(schema_obj)
            for err in validator.iter_errors(payload):
                loc = " -> ".join(str(p) for p in err.absolute_path) or "root"
                errors.append(f"[Schema: {loc}] {err.message}")
        except ImportError:
            pass
        except Exception as e:
            errors.append(f"Gagal memvalidasi JSON Schema: {e}")

    total_active_warnings = sum(
        len(r.get("warnings", [])) for r in (regions if isinstance(regions, list) else []) if isinstance(r, dict)
    )

    return {
        "valid": len(errors) == 0,
        "schema_version": payload.get("schema_version", "1.0.0"),
        "regions_count": len(regions) if isinstance(regions, list) else 0,
        "kecamatan_count": len(kec_list) if isinstance(kec_list, list) else 0,
        "active_warnings_count": total_active_warnings,
        "errors": errors,
        "warnings": warnings_info,
    }


def execute_publication_workflow(
    period_id: str,
    action: str,  # 'SAVE_DRAFT' | 'SUBMIT_REVIEW' | 'APPROVE' | 'PUBLISH'
    valid_from: Optional[str] = None,
    valid_until: Optional[str] = None,
    operator: str = "klimatkepri",
    revision_reason: Optional[str] = None,
    snap_override: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Executes the publication state machine:
      DRAFT -> REVIEW -> APPROVED -> PUBLISHED
    Rules:
    - Any transition validates the JSON contract first.
    - 'PUBLISH' is strictly blocked unless the current state is 'APPROVED' (or explicitly approved first).
    - Modifying or re-publishing after a 'PUBLISHED' version creates a new revision (revision + 1)
      without overwriting previous publication records.
    """
    ensure_regional_warning_tables()
    act = str(action or "").strip().upper()
    if act not in ("SAVE_DRAFT", "SUBMIT_REVIEW", "APPROVE", "PUBLISH"):
        raise ValueError(f"Aksi publikasi '{action}' tidak dikenal. Gunakan SAVE_DRAFT, SUBMIT_REVIEW, APPROVE, atau PUBLISH.")

    # Ensure all 14 regional hazard slots exist in DB for this period
    rec_bundle = compute_regional_recommendations(period_id=period_id, snap_override=snap_override)
    pid = rec_bundle["period_id"]
    v_from = valid_from or rec_bundle["default_valid_from"]
    v_until = valid_until or rec_bundle["default_valid_until"]

    # Check if all 14 slots are saved; if not, initialize unconfirmed ones from DSS recommendations
    unconfirmed_slots = sum(
        (0 if r["pdkm"]["has_explicit_decision"] else 1) + (0 if r["pdcht"]["has_explicit_decision"] else 1)
        for r in rec_bundle["regions"]
    )
    if unconfirmed_slots > 0:
        save_bulk_regional_decisions_from_recommendations(
            period_id=pid,
            valid_from=v_from,
            valid_until=v_until,
            operator=operator,
            snap_override=snap_override,
        )

    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT * FROM cews_sih3_publications
                WHERE period_id = %s
                ORDER BY revision DESC, id DESC
                LIMIT 1
                """,
                (pid,),
            )
            latest_pub = cur.fetchone()

    pub_id = latest_pub["publication_id"] if latest_pub else _generate_publication_id(pid, v_from)

    # Determine target revision and status transition rules
    if latest_pub is None:
        if act == "PUBLISH":
            raise ValueError(
                "Publikasi ditolak: Dokumen belum melalui tahap persetujuan (APPROVED). Lakukan Review/Approve terlebih dahulu."
            )
        target_rev = 1
        create_new_row = True
    else:
        curr_status = latest_pub["status"]
        curr_rev = int(latest_pub["revision"])
        if curr_status == "PUBLISHED":
            # Any new action after PUBLISHED creates a new revision!
            if act == "PUBLISH":
                raise ValueError(
                    "Revisi baru setelah publikasi wajib melalui tahap persetujuan (APPROVE) terlebih dahulu sebelum diterbitkan."
                )
            if not revision_reason or len(revision_reason.strip()) < 5:
                raise ValueError(
                    "Alasan revisi (revision_reason) wajib diisi minimal 5 karakter untuk membuat revisi baru setelah publikasi."
                )
            target_rev = curr_rev + 1
            create_new_row = True
        else:
            # Working on current draft/review/approved revision
            target_rev = curr_rev
            create_new_row = False
            if act == "PUBLISH" and curr_status != "APPROVED":
                raise ValueError(
                    f"Publikasi ditolak: Status saat ini adalah '{curr_status}'. Hanya dokumen berstatus 'APPROVED' yang dapat diterbitkan (PUBLISHED)."
                )

    status_map = {
        "SAVE_DRAFT": "DRAFT",
        "SUBMIT_REVIEW": "REVIEW",
        "APPROVE": "APPROVED",
        "PUBLISH": "PUBLISHED",
    }
    target_status = status_map[act]
    now_iso = get_current_server_time_wib().isoformat(timespec="seconds")

    approved_by = (
        operator
        if target_status == "APPROVED"
        else (latest_pub.get("approved_by") if latest_pub and not create_new_row else None)
    )
    published_by = operator if target_status == "PUBLISHED" else None
    published_at_iso = now_iso if target_status == "PUBLISHED" else None

    json_payload = build_sih3_publication_json(
        period_id=pid,
        valid_from=v_from,
        valid_until=v_until,
        publication_status=target_status,
        revision=target_rev,
        publication_id=pub_id,
        approved_by=approved_by,
        published_by=published_by,
        published_at_iso=published_at_iso,
        revision_reason=revision_reason or (latest_pub.get("revision_reason") if latest_pub else None),
        snap_override=snap_override,
    )

    val_res = validate_sih3_json_payload(json_payload)
    if not val_res["valid"]:
        raise ValueError("Validasi JSON SIH3 gagal: " + "; ".join(val_res["errors"]))

    payload_str = json.dumps(json_payload, ensure_ascii=False, indent=2)
    active_cnt = val_res["active_warnings_count"]

    with get_db() as conn:
        with conn.cursor() as cur:
            if create_new_row:
                cur.execute(
                    """
                    INSERT INTO cews_sih3_publications
                    (publication_id, period_id, evaluation_period_label, revision, status,
                     valid_from, valid_until, observation_cutoff_date, forecast_issue_date,
                     active_warnings_count, revision_reason, created_by, reviewed_by,
                     approved_by, published_by, generated_at, reviewed_at, approved_at,
                     published_at, json_payload)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                            CURRENT_TIMESTAMP,
                            CASE WHEN %s IN ('REVIEW', 'APPROVED', 'PUBLISHED') THEN CURRENT_TIMESTAMP ELSE NULL END,
                            CASE WHEN %s IN ('APPROVED', 'PUBLISHED') THEN CURRENT_TIMESTAMP ELSE NULL END,
                            CASE WHEN %s = 'PUBLISHED' THEN CURRENT_TIMESTAMP ELSE NULL END,
                            %s)
                    """,
                    (
                        pub_id,
                        pid,
                        rec_bundle["evaluation_period"],
                        target_rev,
                        target_status,
                        v_from,
                        v_until,
                        rec_bundle["observation_cutoff_date"],
                        rec_bundle["forecast_issue_date"],
                        active_cnt,
                        revision_reason,
                        operator,
                        operator if target_status in ("REVIEW", "APPROVED", "PUBLISHED") else None,
                        approved_by,
                        published_by,
                        target_status,
                        target_status,
                        target_status,
                        payload_str,
                    ),
                )
            else:
                cur.execute(
                    """
                    UPDATE cews_sih3_publications
                    SET status = %s,
                        valid_from = %s,
                        valid_until = %s,
                        active_warnings_count = %s,
                        revision_reason = COALESCE(%s, revision_reason),
                        reviewed_by = CASE WHEN %s = 'REVIEW' THEN %s ELSE reviewed_by END,
                        reviewed_at = CASE WHEN %s = 'REVIEW' THEN CURRENT_TIMESTAMP ELSE reviewed_at END,
                        approved_by = CASE WHEN %s = 'APPROVED' THEN %s ELSE approved_by END,
                        approved_at = CASE WHEN %s = 'APPROVED' THEN CURRENT_TIMESTAMP ELSE approved_at END,
                        published_by = CASE WHEN %s = 'PUBLISHED' THEN %s ELSE published_by END,
                        published_at = CASE WHEN %s = 'PUBLISHED' THEN CURRENT_TIMESTAMP ELSE published_at END,
                        json_payload = %s
                    WHERE id = %s
                    """,
                    (
                        target_status,
                        v_from,
                        v_until,
                        active_cnt,
                        revision_reason,
                        target_status,
                        operator,
                        target_status,
                        target_status,
                        operator,
                        target_status,
                        target_status,
                        operator,
                        target_status,
                        payload_str,
                        latest_pub["id"],
                    ),
                )

            # Sync workflow_status on cews_regional_warning_decisions for this period
            cur.execute(
                """
                UPDATE cews_regional_warning_decisions
                SET workflow_status = %s, valid_from = %s, valid_until = %s
                WHERE period_id = %s
                """,
                (target_status, v_from, v_until, pid),
            )
        conn.commit()

    return {
        "status": "success",
        "publication_id": pub_id,
        "period_id": pid,
        "revision": target_rev,
        "workflow_status": target_status,
        "valid_from": v_from,
        "valid_until": v_until,
        "active_warnings_count": active_cnt,
        "validation": val_res,
        "json_payload": json_payload,
    }


def get_sih3_publication_history(period_id: Optional[str] = None, limit: int = 50) -> Dict[str, Any]:
    """Lists publication history across all revisions without hiding superseded revisions."""
    ensure_regional_warning_tables()
    with get_db() as conn:
        with conn.cursor() as cur:
            if period_id:
                cur.execute(
                    """
                    SELECT id, publication_id, period_id, evaluation_period_label, revision, status,
                           valid_from, valid_until, observation_cutoff_date, forecast_issue_date,
                           active_warnings_count, revision_reason, created_by, reviewed_by,
                           approved_by, published_by, generated_at, reviewed_at, approved_at, published_at
                    FROM cews_sih3_publications
                    WHERE period_id = %s
                    ORDER BY revision DESC, id DESC
                    LIMIT %s
                    """,
                    (period_id, limit),
                )
            else:
                cur.execute(
                    """
                    SELECT id, publication_id, period_id, evaluation_period_label, revision, status,
                           valid_from, valid_until, observation_cutoff_date, forecast_issue_date,
                           active_warnings_count, revision_reason, created_by, reviewed_by,
                           approved_by, published_by, generated_at, reviewed_at, approved_at, published_at
                    FROM cews_sih3_publications
                    ORDER BY generated_at DESC, id DESC
                    LIMIT %s
                    """,
                    (limit,),
                )
            rows = cur.fetchall()
            for r in rows:
                for k in ("valid_from", "valid_until", "observation_cutoff_date", "forecast_issue_date"):
                    if r.get(k) and hasattr(r[k], "strftime"):
                        r[k] = r[k].strftime("%Y-%m-%d")
                for k in ("generated_at", "reviewed_at", "approved_at", "published_at"):
                    if r.get(k) and hasattr(r[k], "strftime"):
                        r[k] = r[k].strftime("%Y-%m-%d %H:%M:%S")

    return {"total": len(rows), "items": rows}


def get_sih3_publication_json_by_id(publication_id: str, revision: Optional[int] = None) -> Dict[str, Any]:
    """Retrieves the stored JSON snapshot for a specific publication_id (and optional revision)."""
    ensure_regional_warning_tables()
    with get_db() as conn:
        with conn.cursor() as cur:
            if revision is not None:
                cur.execute(
                    """
                    SELECT * FROM cews_sih3_publications
                    WHERE publication_id = %s AND revision = %s
                    LIMIT 1
                    """,
                    (publication_id, int(revision)),
                )
            else:
                cur.execute(
                    """
                    SELECT * FROM cews_sih3_publications
                    WHERE publication_id = %s
                    ORDER BY revision DESC, id DESC
                    LIMIT 1
                    """,
                    (publication_id,),
                )
            row = cur.fetchone()
            if not row:
                raise ValueError(f"Publikasi '{publication_id}' tidak ditemukan.")
            return json.loads(row["json_payload"])


def get_latest_published_sih3_json(period_id: Optional[str] = None) -> Dict[str, Any]:
    """
    Public Read-Only Contract for SIH3 WordPress Integration:
    Strictly returns ONLY publications with status = 'PUBLISHED'.
    Never leaks DRAFT, REVIEW, or unapproved internal data.
    """
    ensure_regional_warning_tables()
    with get_db() as conn:
        with conn.cursor() as cur:
            if period_id:
                cur.execute(
                    """
                    SELECT json_payload FROM cews_sih3_publications
                    WHERE status = 'PUBLISHED' AND period_id = %s
                    ORDER BY published_at DESC, revision DESC, id DESC
                    LIMIT 1
                    """,
                    (period_id,),
                )
            else:
                cur.execute(
                    """
                    SELECT json_payload FROM cews_sih3_publications
                    WHERE status = 'PUBLISHED'
                    ORDER BY published_at DESC, revision DESC, id DESC
                    LIMIT 1
                    """
                )
            row = cur.fetchone()
            if not row:
                raise LookupError("Belum ada publikasi peringatan dini berstatus PUBLISHED.")
            return json.loads(row["json_payload"])


def build_map_modal_sih3_json(
    period_id: str,
    scope: str = "GABUNGAN",
    pdkm_status: Optional[Dict[str, str]] = None,
    pdcht_status: Optional[Dict[str, str]] = None,
    regency_decisions: Optional[Dict[str, Any]] = None,
    kecamatan_decisions: Optional[Dict[str, Any]] = None,
    override_reasons: Optional[Dict[str, Any]] = None,
    analysis_notes: Optional[str] = None,
    valid_from: Optional[str] = None,
    valid_until: Optional[str] = None,
    operator_name: Optional[str] = "Petugas Operasional",
    publish: bool = False,
    snap_override: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Unified Regional & Kecamatan Decision & SIH3 JSON Publication Engine for OfficialMapModal.
    
    1. Operates on both the 7 canonical administrative regions AND 59 kecamatan of Kepulauan Riau.
    2. Supports independent per-kecamatan warning type assignment (PDKM, PDCHT, or AMAN).
    3. Retains regency-level decisions and high-level summaries for full backward compatibility.
    4. Validates against docs/schemas/sih3_regional_warning.schema.json.
    5. Exports downloadable JSON files to data/operational/maps/ and data/output/sih3/.
    """
    ensure_regional_warning_tables()
    rec_bundle = compute_regional_recommendations(period_id=period_id, snap_override=snap_override)
    kec_bundle = compute_kecamatan_recommendations(period_id=period_id, snap_override=snap_override)
    pid = rec_bundle["period_id"]
    v_from = (valid_from or rec_bundle["default_valid_from"]).strip()
    v_until = (valid_until or rec_bundle["default_valid_until"]).strip()
    op_name = (operator_name or "Petugas Operasional").strip()
    notes = (analysis_notes or f"Evaluasi penetapan peta resmi & JSON SIH3 oleh {op_name}.").strip()

    # Scope normalization
    norm_scope = (scope or "GABUNGAN").strip().upper()
    if norm_scope not in ("GABUNGAN", "PDKM", "PDCHT"):
        norm_scope = "GABUNGAN"

    pdkm_in = pdkm_status or {}
    pdcht_in = pdcht_status or {}
    ov_reasons = override_reasons or {}
    unified_in = regency_decisions or {}
    kec_decisions_in = kecamatan_decisions or {}

    def _normalize_choice(choice: Optional[str], region_data_status: str) -> str:
        s = str(choice or "").strip().upper()
        if s in ("TIDAK_ADA_PERINGATAN", "NORMAL"):
            return "INSUFFICIENT_DATA" if region_data_status == "INSUFFICIENT_DATA" else "AMAN"
        elif s in ("TIDAK_ADA_DATA", "INSUFFICIENT_DATA"):
            return "INSUFFICIENT_DATA"
        elif s in ("WASPADA", "SIAGA", "AWAS"):
            return s
        elif s == "AMAN":
            return "INSUFFICIENT_DATA" if region_data_status == "INSUFFICIENT_DATA" else "AMAN"
        return "INSUFFICIENT_DATA" if region_data_status == "INSUFFICIENT_DATA" else "AMAN"

    # Track explicit regency overrides to pass into the canonical decision-based serializer
    regency_overrides_map: Dict[str, Dict[str, Any]] = {}
    now_wib = get_current_server_time_wib()
    timestamp_export = now_wib.strftime("%Y%m%d_%H%M%S")
    timestamp_iso = now_wib.isoformat(timespec="seconds")

    # Process and record decisions for each of the 7 canonical regions
    for r in rec_bundle["regions"]:
        rc = r["region_code"]
        poly = r["sih3_polygon_key"]
        rname = r["region_name"]
        d_status = r["data_status"]

        rec_pdkm = _normalize_warning_level(r["pdkm"]["recommended_level"])
        rec_pdcht = _normalize_warning_level(r["pdcht"]["recommended_level"])

        # Check if unified per-regency decision is supplied
        u_dec = unified_in.get(poly) or unified_in.get(rc) or unified_in.get(rname)
        if u_dec and isinstance(u_dec, dict):
            raw_w_type = u_dec.get("warning_type")
            w_type_up = str(raw_w_type).strip().upper() if raw_w_type else ""
            w_type = w_type_up if w_type_up in ("PDKM", "PDCHT", "MULTI_HAZARD") else None
            cls_val = str(u_dec.get("classification") or u_dec.get("level") or "AMAN").strip().upper()
            u_ov_reason = str(u_dec.get("override_reason") or "").strip()

            if w_type == "PDKM":
                chosen_pdkm_raw = cls_val
                chosen_pdcht_raw = "INSUFFICIENT_DATA" if rec_pdcht == "INSUFFICIENT_DATA" else "AMAN"
                reason_pdkm = u_ov_reason
                reason_pdcht = u_ov_reason if chosen_pdcht_raw != rec_pdcht else ""
            elif w_type == "PDCHT":
                chosen_pdcht_raw = cls_val
                chosen_pdkm_raw = "INSUFFICIENT_DATA" if rec_pdkm == "INSUFFICIENT_DATA" else "AMAN"
                reason_pdcht = u_ov_reason
                reason_pdkm = u_ov_reason if chosen_pdkm_raw != rec_pdkm else ""
            elif w_type == "MULTI_HAZARD":
                chosen_pdkm_raw = str(u_dec.get("pdkm_level") or rec_pdkm).strip().upper()
                chosen_pdcht_raw = str(u_dec.get("pdcht_level") or rec_pdcht).strip().upper()
                reason_pdkm = u_ov_reason
                reason_pdcht = u_ov_reason
            else:  # None / AMAN / INSUFFICIENT_DATA
                if cls_val in ("INSUFFICIENT_DATA", "TIDAK_ADA_DATA"):
                    chosen_pdkm_raw = "INSUFFICIENT_DATA"
                    chosen_pdcht_raw = "INSUFFICIENT_DATA"
                elif d_status == "INSUFFICIENT_DATA" and not u_ov_reason:
                    chosen_pdkm_raw = "INSUFFICIENT_DATA"
                    chosen_pdcht_raw = "INSUFFICIENT_DATA"
                else:
                    chosen_pdkm_raw = "INSUFFICIENT_DATA" if (rec_pdkm == "INSUFFICIENT_DATA" and not u_ov_reason) else "AMAN"
                    chosen_pdcht_raw = "INSUFFICIENT_DATA" if (rec_pdcht == "INSUFFICIENT_DATA" and not u_ov_reason) else "AMAN"
                reason_pdkm = u_ov_reason
                reason_pdcht = u_ov_reason
        else:
            # Fallback to separate pdkm_status / pdcht_status dicts (or persisted DB decisions / DSS recommendations)
            chosen_pdkm_raw = pdkm_in.get(poly) or pdkm_in.get(rc) or pdkm_in.get(rname)
            chosen_pdcht_raw = pdcht_in.get(poly) or pdcht_in.get(rc) or pdcht_in.get(rname)
            reason_pdkm = ""
            if isinstance(ov_reasons, dict):
                reason_pdkm = ov_reasons.get("PDKM", {}).get(poly) if isinstance(ov_reasons.get("PDKM"), dict) else (ov_reasons.get(poly) or "")
            reason_pdcht = ""
            if isinstance(ov_reasons, dict):
                reason_pdcht = ov_reasons.get("PDCHT", {}).get(poly) if isinstance(ov_reasons.get("PDCHT"), dict) else (ov_reasons.get(poly) or "")

        # Evaluate PDKM
        if chosen_pdkm_raw:
            final_pdkm = _normalize_choice(chosen_pdkm_raw, d_status) if str(chosen_pdkm_raw).upper() != "AMAN" or not reason_pdkm else "AMAN"
        else:
            final_pdkm = _normalize_warning_level(r["pdkm"]["final_level"]) if r["pdkm"].get("has_explicit_decision") else rec_pdkm

        is_ov_pdkm = (final_pdkm != rec_pdkm)
        save_regional_warning_decision(
            period_id=pid,
            region_code=rc,
            hazard_code="PDKM",
            decision_mode="OPERATOR_OVERRIDE" if is_ov_pdkm else "DSS_RECOMMENDATION",
            final_level=final_pdkm,
            override_reason=str(reason_pdkm).strip() if (is_ov_pdkm and reason_pdkm and str(reason_pdkm).strip()) else None,
            analysis_notes=notes if is_ov_pdkm else None,
            valid_from=v_from,
            valid_until=v_until,
            operator=op_name,
            snap_override=snap_override,
        )

        # Evaluate PDCHT
        if chosen_pdcht_raw:
            final_pdcht = _normalize_choice(chosen_pdcht_raw, d_status) if str(chosen_pdcht_raw).upper() != "AMAN" or not reason_pdcht else "AMAN"
        else:
            final_pdcht = _normalize_warning_level(r["pdcht"]["final_level"]) if r["pdcht"].get("has_explicit_decision") else rec_pdcht

        is_ov_pdcht = (final_pdcht != rec_pdcht)
        save_regional_warning_decision(
            period_id=pid,
            region_code=rc,
            hazard_code="PDCHT",
            decision_mode="OPERATOR_OVERRIDE" if is_ov_pdcht else "DSS_RECOMMENDATION",
            final_level=final_pdcht,
            override_reason=str(reason_pdcht).strip() if (is_ov_pdcht and reason_pdcht and str(reason_pdcht).strip()) else None,
            analysis_notes=notes if is_ov_pdcht else None,
            valid_from=v_from,
            valid_until=v_until,
            operator=op_name,
            snap_override=snap_override,
        )

        regency_overrides_map[poly] = {
            "fin_p": final_pdkm,
            "fin_c": final_pdcht,
            "ov_reason_p": str(reason_pdkm).strip() if (is_ov_pdkm and reason_pdkm and str(reason_pdkm).strip()) else None,
            "ov_reason_c": str(reason_pdcht).strip() if (is_ov_pdcht and reason_pdcht and str(reason_pdcht).strip()) else None,
            "operator": op_name,
            "decided_at": timestamp_iso,
        }

    # Translate incoming per-kecamatan operator decisions (if supplied) into structured dual-hazard overrides
    kecamatan_overrides_map: Dict[str, Dict[str, Any]] = {}
    for k_item in kec_bundle["kecamatan"]:
        kid = k_item["kecamatan_id"]
        k_dec = kec_decisions_in.get(kid)
        if not isinstance(k_dec, dict):
            continue

        rec_p = _normalize_warning_level(k_item["pdkm"]["recommended_level"])
        rec_c = _normalize_warning_level(k_item["pdcht"]["recommended_level"])
        raw_w = k_dec.get("warning_type")
        k_wtype_up = str(raw_w).strip().upper() if raw_w else ""
        k_wtype = k_wtype_up if k_wtype_up in ("PDKM", "PDCHT", "MULTI_HAZARD") else None
        k_lvl = _normalize_warning_level(k_dec.get("classification") or k_dec.get("level") or "AMAN")
        k_ov_reason = str(k_dec.get("override_reason") or "").strip() or None

        if k_wtype == "PDKM" and k_lvl in ACTIVE_WARNING_LEVELS:
            k_fin_p = k_lvl
            k_fin_c = "INSUFFICIENT_DATA" if rec_c == "INSUFFICIENT_DATA" else "AMAN"
        elif k_wtype == "PDCHT" and k_lvl in ACTIVE_WARNING_LEVELS:
            k_fin_c = k_lvl
            k_fin_p = "INSUFFICIENT_DATA" if rec_p == "INSUFFICIENT_DATA" else "AMAN"
        elif k_wtype == "MULTI_HAZARD":
            k_fin_p = _normalize_warning_level(k_dec.get("pdkm_level") or rec_p)
            k_fin_c = _normalize_warning_level(k_dec.get("pdcht_level") or rec_c)
        elif k_lvl == "INSUFFICIENT_DATA":
            k_fin_p = "INSUFFICIENT_DATA"
            k_fin_c = "INSUFFICIENT_DATA"
        else:
            # Explicit AMAN decision by operator (or preserve INSUFFICIENT_DATA if both recommendations lack data and no override reason)
            if rec_p == "INSUFFICIENT_DATA" and rec_c == "INSUFFICIENT_DATA" and not k_ov_reason:
                k_fin_p = "INSUFFICIENT_DATA"
                k_fin_c = "INSUFFICIENT_DATA"
            else:
                k_fin_p = "AMAN"
                k_fin_c = "AMAN"

        kecamatan_overrides_map[kid] = {
            "fin_p": k_fin_p,
            "fin_c": k_fin_c,
            "ov_reason_p": k_ov_reason if k_fin_p != rec_p else None,
            "ov_reason_c": k_ov_reason if k_fin_c != rec_c else None,
            "operator": op_name,
            "decided_at": timestamp_iso,
        }

    # Resolve publication metadata dynamically from actual publication state (no hardcoded status)
    latest_pub = rec_bundle.get("latest_publication")
    if publish:
        resolved_pub_id = latest_pub["publication_id"] if latest_pub else _generate_publication_id(pid, v_from)
        resolved_rev = int(latest_pub["revision"]) if latest_pub else 1
        publication_meta = {
            "publication_id": resolved_pub_id,
            "revision": resolved_rev,
            "status": "PUBLISHED",
            "published_at": timestamp_iso,
            "approved_by": (latest_pub.get("approved_by") if latest_pub else None) or op_name,
            "published_by": op_name,
            "revision_reason": latest_pub.get("revision_reason") if latest_pub else None,
        }
    elif latest_pub:
        lp_status = latest_pub.get("status") or "Aktif"
        publication_meta = {
            "publication_id": latest_pub["publication_id"],
            "revision": int(latest_pub["revision"]),
            "status": lp_status,
            "published_at": _to_wib_iso(latest_pub.get("published_at")) if lp_status == "PUBLISHED" else None,
            "approved_by": latest_pub.get("approved_by") if lp_status in ("APPROVED", "PUBLISHED") else None,
            "published_by": latest_pub.get("published_by") if lp_status == "PUBLISHED" else None,
            "revision_reason": latest_pub.get("revision_reason"),
        }
    else:
        publication_meta = {
            "publication_id": _generate_publication_id(pid, v_from),
            "revision": 1,
            "status": "Aktif",
            "published_at": None,
            "approved_by": None,
            "published_by": None,
            "revision_reason": None,
        }

    standard_export_payload = _build_standardized_decision_payload(
        rec_bundle=rec_bundle,
        kec_bundle=kec_bundle,
        publication_meta=publication_meta,
        valid_from=v_from,
        valid_until=v_until,
        generated_at_iso=timestamp_iso,
        regency_overrides=regency_overrides_map,
        kecamatan_overrides=kecamatan_overrides_map,
        default_operator=op_name,
    )

    # Mandatory Quality Control & Structural Validation before saving or publishing
    val_res = validate_sih3_json_payload(standard_export_payload)
    if not val_res["valid"]:
        err_msg = "Validasi Quality Control JSON DSS-PIK gagal: " + "; ".join(val_res["errors"])
        logger.error(err_msg)
        raise ValueError(err_msg)

    # Output file paths
    from backend.map_generator import OUTPUT_DIR as MAPS_OUTPUT_DIR
    out_maps_dir = MAPS_OUTPUT_DIR
    out_sih3_dir = DOCS_DIR.parent / "data" / "output" / "sih3"
    out_maps_dir.mkdir(parents=True, exist_ok=True)
    out_sih3_dir.mkdir(parents=True, exist_ok=True)

    export_filename = f"PERINGATAN_DINI_KEPRI_{pid}_{timestamp_export}.json"
    target_path_maps = out_maps_dir / export_filename
    target_path_sih3 = out_sih3_dir / export_filename

    payload_json_str = json.dumps(standard_export_payload, ensure_ascii=False, indent=2, allow_nan=False)
    with open(target_path_maps, "w", encoding="utf-8") as f:
        f.write(payload_json_str)
    with open(target_path_sih3, "w", encoding="utf-8") as f:
        f.write(payload_json_str)

    standard_regions = standard_export_payload["regions"]
    standard_kecamatan = standard_export_payload["kecamatan"]
    summary = {
        "total_regions": len(standard_regions),
        "total_kecamatan": len(standard_kecamatan),
        "pdkm_active": sum(1 for r in standard_regions if r["hazard_assessments"]["PDKM"]["final_level"] in ACTIVE_WARNING_LEVELS),
        "pdcht_active": sum(1 for r in standard_regions if r["hazard_assessments"]["PDCHT"]["final_level"] in ACTIVE_WARNING_LEVELS),
        "multi_hazard": sum(1 for r in standard_regions if r["final_decision"]["warning_type"] == "MULTI_HAZARD"),
        "no_warning": sum(1 for r in standard_regions if r["overall_region_status"] == "AMAN"),
        "insufficient_data": sum(1 for r in standard_regions if r["overall_region_status"] == "INSUFFICIENT_DATA"),
        "scope": norm_scope,
        "is_published": publication_meta["status"] == "PUBLISHED",
    }

    return {
        "success": True,
        "scope": norm_scope,
        "publication_id": publication_meta["publication_id"],
        "validation": val_res,
        "summary": summary,
        "payload": standard_export_payload,
        "download_filename": export_filename,
        "json_url": f"/api/v1/maps/download/{export_filename}",
        "message": f"Data JSON Peringatan Dini berhasil diekspor dan tervalidasi: {export_filename}",
    }

