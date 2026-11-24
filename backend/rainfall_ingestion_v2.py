"""
backend/rainfall_ingestion_v2.py
Modular Rainfall Data Input Engine (v2):
- 7 Regency Registry & Template Support Matrix
- Automatic Template Detection Engine (structure-based, independent per file)
- 4 Raw Excel Parsers (Karimun, Lingga/Dabo Singkep, Natuna, Anambas)
- Legacy Compatibility Adapter (Batam, Bintan XLSM, Tanjungpinang, Multi-Sheet)
- Persistent Template Profiles & Station Aliases in MariaDB
- Region-Aware Canonical Symbol Normalization (OBSERVED_ZERO, TTU, MISSING, NOT_PROVIDED, UNRECOGNIZED)
- Partial-Period Import & Multi-File Batch Staging / Transactional Commit
- Multi-Date Manual Input (reusing canonical normalization & MariaDB audit pipeline)
"""

from __future__ import annotations

import calendar
import hashlib
import io
import json
import logging
import re
import uuid
from datetime import date, datetime, timedelta
from typing import Any, Dict, List, Optional, Set, Tuple

import openpyxl
import pandas as pd

from backend.database import get_db, get_raw_connection
from backend.ingestion_service import (
    INDONESIAN_MONTHS,
    MONTH_ABBR_MAP,
    PARSER_VERSION,
    SYMBOL_MAP as LEGACY_SYMBOL_MAP,
    date_to_dasarian_info,
    ensure_ingestion_history_table,
    get_master_station_lookup,
    parse_rainfall_excel,
)

logger = logging.getLogger(__name__)

MAX_UPLOAD_BYTES = 25 * 1024 * 1024  # 25 MB safety limit per file
SESSION_TTL_SECONDS = 3600  # 1 hour

# In-memory TTL store for multi-file detect/preview sessions
_BATCH_SESSIONS: Dict[str, Dict[str, Any]] = {}


def _cleanup_expired_sessions() -> None:
    now = datetime.now()
    expired = [
        sid
        for sid, s in _BATCH_SESSIONS.items()
        if (now - s.get("created_at", now)).total_seconds() > SESSION_TTL_SECONDS
    ]
    for sid in expired:
        _BATCH_SESSIONS.pop(sid, None)


# ==============================================================================
# 1. REGENCY REGISTRY & TEMPLATE SUPPORT MATRIX
# ==============================================================================
REGENCY_REGISTRY: Dict[str, Dict[str, Any]] = {
    "KARIMUN": {
        "code": "KARIMUN",
        "label": "Kabupaten Karimun",
        "master_regency": "Kab. Karimun",
        "supports_raw": True,
        "supports_legacy": True,
        "raw_template_kind": "RAW_KARIMUN",
    },
    "LINGGA": {
        "code": "LINGGA",
        "label": "Kabupaten Lingga (Dabo Singkep)",
        "master_regency": "Kab. Lingga",
        "supports_raw": True,
        "supports_legacy": True,
        "raw_template_kind": "RAW_LINGGA",
    },
    "NATUNA": {
        "code": "NATUNA",
        "label": "Kabupaten Natuna",
        "master_regency": "Kab. Natuna",
        "supports_raw": True,
        "supports_legacy": True,
        "raw_template_kind": "RAW_NATUNA",
    },
    "ANAMBAS": {
        "code": "ANAMBAS",
        "label": "Kabupaten Kepulauan Anambas",
        "master_regency": "Kab. Kepulauan Anambas",
        "supports_raw": True,
        "supports_legacy": True,
        "raw_template_kind": "RAW_ANAMBAS",
    },
    "BATAM": {
        "code": "BATAM",
        "label": "Kota Batam",
        "master_regency": "Kota Batam",
        "supports_raw": False,
        "supports_legacy": True,
        "raw_template_kind": None,
    },
    "BINTAN": {
        "code": "BINTAN",
        "label": "Kabupaten Bintan",
        "master_regency": "Kab. Bintan",
        "supports_raw": False,
        "supports_legacy": True,
        "raw_template_kind": None,
    },
    "TANJUNGPINANG": {
        "code": "TANJUNGPINANG",
        "label": "Kota Tanjungpinang",
        "master_regency": "Kota Tanjung Pinang",
        "supports_raw": False,
        "supports_legacy": True,
        "raw_template_kind": None,
    },
}

# Region-specific symbol normalization profiles (DSS-PIK Standardized Rules)
REGION_SYMBOL_PROFILES: Dict[str, Dict[str, Tuple[Optional[float], str]]] = {
    "RAW_KARIMUN": {
        "0": (0.0, "OBSERVED_ZERO"),
        "0.0": (0.0, "OBSERVED_ZERO"),
        "0,0": (0.0, "OBSERVED_ZERO"),
        "TTU": (0.0, "TTU"),
        "T.T.U": (0.0, "TTU"),
        "9999": (None, "MISSING"),
        "ALAT RUSAK": (None, "DAMAGED"),
        "R": (None, "DAMAGED"),
    },
    "RAW_LINGGA": {
        "0": (0.0, "OBSERVED_ZERO"),
        "0.0": (0.0, "OBSERVED_ZERO"),
        "0,0": (0.0, "OBSERVED_ZERO"),
        "-": (None, "MISSING"),
        "TTU": (0.0, "TTU"),
        "T.T.U": (0.0, "TTU"),
        "8888": (0.0, "TTU"),
        "9999": (None, "MISSING"),
        "ALAT RUSAK": (None, "DAMAGED"),
        "R": (None, "DAMAGED"),
    },
    "RAW_NATUNA": {
        "0": (0.0, "TTU"),
        "0.0": (0.0, "TTU"),
        "0,0": (0.0, "TTU"),
        "-": (None, "MISSING"),
        "TTU": (0.0, "TTU"),
        "T.T.U": (0.0, "TTU"),
        "9999": (None, "MISSING"),
        "ALAT RUSAK": (None, "DAMAGED"),
        "R": (None, "DAMAGED"),
    },
    "RAW_ANAMBAS": {
        "-": (0.0, "OBSERVED_ZERO"),
        "0": (0.0, "TTU"),
        "0.0": (0.0, "TTU"),
        "0,0": (0.0, "TTU"),
        "TTU": (0.0, "TTU"),
        "T.T.U": (0.0, "TTU"),
        "9999": (None, "MISSING"),
        "ALAT RUSAK": (None, "DAMAGED"),
        "R": (None, "DAMAGED"),
    },
    "LEGACY_STANDARD": {
        "-": (0.0, "OBSERVED_ZERO"),
        "0": (0.0, "OBSERVED_ZERO"),
        "0.0": (0.0, "OBSERVED_ZERO"),
        "0,0": (0.0, "OBSERVED_ZERO"),
        "TTU": (0.0, "TTU"),
        "T.T.U": (0.0, "TTU"),
        "9999": (None, "MISSING"),
        "X": (None, "MISSING"),
        "NO DATA": (None, "MISSING"),
        "R": (None, "DAMAGED"),
        "ALAT RUSAK": (None, "DAMAGED"),
    },
    "MANUAL_CANONICAL": {
        "0": (0.0, "OBSERVED_ZERO"),
        "0.0": (0.0, "OBSERVED_ZERO"),
        "-": (0.0, "OBSERVED_ZERO"),
        "NIHIL": (0.0, "OBSERVED_ZERO"),
        "TTU": (0.0, "TTU"),
        "T": (0.0, "TTU"),
        "T.T.U": (0.0, "TTU"),
        "8888": (0.0, "TTU"),
        "X": (None, "MISSING"),
        "MISSING": (None, "MISSING"),
        "NO DATA": (None, "MISSING"),
        "9999": (None, "MISSING"),
        "R": (None, "DAMAGED"),
        "ALAT RUSAK": (None, "DAMAGED"),
    },
}


def format_standard_display(rainfall_mm: Optional[float], obs_status: str) -> str:
    """
    Official DSS-PIK Standardized Table Representation:
      - OBSERVED_ZERO (0 mm, tidak ada hujan) -> '-'
      - TTU (hujan tidak terukur)             -> 'TTU'
      - MISSING / DAMAGED / VOID              -> '9999'
      - OBSERVED_VALID                        -> numeric mm string (e.g. '12.5')
    """
    st = (obs_status or "").strip().upper()
    if st == "OBSERVED_ZERO":
        return "-"
    if st == "TTU":
        return "TTU"
    if st in ("MISSING", "DAMAGED", "VOID"):
        return "9999"
    if rainfall_mm is not None:
        if float(rainfall_mm) == 0.0 and st != "OBSERVED_VALID":
            return "-"
        return f"{float(rainfall_mm):.1f}" if float(rainfall_mm).is_integer() else str(round(float(rainfall_mm), 2))
    return "9999"

MONTH_NAME_TO_NUM = {
    "jan": 1, "januari": 1, "january": 1,
    "feb": 2, "februari": 2, "february": 2,
    "mar": 3, "maret": 3, "march": 3,
    "apr": 4, "april": 4,
    "mei": 5, "may": 5,
    "jun": 6, "juni": 6, "june": 6,
    "jul": 7, "juli": 7, "july": 7,
    "ags": 8, "agt": 8, "aug": 8, "agustus": 8, "august": 8,
    "sep": 9, "sept": 9, "september": 9,
    "okt": 10, "oct": 10, "oktober": 10, "october": 10,
    "nov": 11, "november": 11,
    "des": 12, "dec": 12, "desember": 12, "december": 12,
}

SUMMARY_ROW_KEYWORDS = (
    "jumlah", "total", "rata", "rata-rata", "average", "avg", "maks", "max",
    "min", "hari hujan", "hh", "akumulasi", "dasarian", "keterangan", "catatan",
)

# Built-in aliases per regency to match raw workbook names cleanly to master station_id
RAW_STATION_ALIASES: Dict[str, Dict[str, str]] = {
    "KARIMUN": {
        "stamet tbk": "21020302A",
        "stamet raja haji abdullah": "21020302A",
        "raja haji abdullah": "21020302A",
        "stasiun meteorologi raja haji abdullah": "21020302A",
        "kapling tebing": "21020301A",
        "kantor lurah kapling tebing": "21020301A",
        "bpp sememal": "21020401A",
        "sememal": "21020401A",
        "tanjung batu": "21020201A",
        "uptd bbi tanjung batu": "21020201A",
        "kundur utara": "21020701A",
        "kantor camat kundur utara": "21020701A",
        "pulau buru": "21020601A",
        "buru": "21020601A",
        "kantor bpp kecamatan buru": "21020601A",
        "moro": "21020101A",
        "kantor camat moro": "21020101A",
        "arg tanjung balai karimun": "21020402B",
    },
    "LINGGA": {
        "dabo singkep": "21040101A",
        "stamet dabo singkep": "21040101A",
        "dabo": "21040101A",
        "dinas pertanian lingga": "21040203A",
        "dinas pertanian kab. lingga": "21040203A",
        "dinas pertanian": "21040203A",
        "bukit langkap": "21040201A",
        "resun": "21040202A",
        "duara": "21040501A",
        "bukit belah raya": "21040402A",
        "bukit belah": "21040402A",
        "sungai buluh": "21040401A",
        "arg singkep": "21040101B",
        "arg tj. harapan": "21040101B",
        "arg tanjung harapan": "21040101B",
    },
    "NATUNA": {
        "stamet ranai": "21030701A",
        "stamet ranai natuna": "21030701A",
        "ranai": "21030701A",
        "padang meliso": "21031801A",
        "bunguran timur laut": "21031501A",
        "tanjung": "21031501A",
        "bunguran utara kelarik": "21030801A",
        "kelarik": "21030801A",
        "bunguran tengah harapan jaya": "21031601A",
        "harapan jaya": "21031601A",
        "sabang mawang": "21031101A",
        "pulau tiga sabang mawang": "21031101A",
        "sabang barat": "21030401A",
        "hilir": "21030601A",
        "melia": "21030901A",
        "sedanau": "21030501A",
        "sedanau kp balau": "21030501A",
        "air payang": "21031001A",
        "batubi": "21032001A",
        "teluk buton": "21030802A",
        "selemut": "21031802A",
        "selemut cemaga": "21031802A",
        "mekar jaya": "21030502A",
    },
    "ANAMBAS": {
        "stamet tarempa": "21050101A",
        "tarempa": "21050101A",
        "stasiun meteorologi tarempa": "21050101A",
        "bukit padi": "21050501A",
        "upt benih pertanian": "21050501A",
        "upt benih pertanian bukit padi": "21050501A",
        "langir": "21050201A",
        "pos hujan langir": "21050201A",
    },
}


# ==============================================================================
# 2. PERSISTENT PROFILE & ALIAS TABLES (SAFE ADDITIVE INIT)
# ==============================================================================
def ensure_v2_profile_tables() -> None:
    sql_profiles = """
    CREATE TABLE IF NOT EXISTS cews_rainfall_template_profiles (
        profile_id VARCHAR(64) NOT NULL,
        profile_name VARCHAR(150) NOT NULL,
        regency_code VARCHAR(32) NOT NULL,
        template_kind VARCHAR(50) NOT NULL DEFAULT 'CUSTOM_MAPPED',
        structure_fingerprint VARCHAR(64) NOT NULL,
        sheet_rules_json LONGTEXT NULL,
        header_config_json LONGTEXT NULL,
        date_config_json LONGTEXT NULL,
        value_config_json LONGTEXT NULL,
        station_config_json LONGTEXT NULL,
        ignored_columns_json LONGTEXT NULL,
        symbol_mapping_json LONGTEXT NULL,
        version VARCHAR(20) NOT NULL DEFAULT '1.0.0',
        created_by VARCHAR(100) NOT NULL DEFAULT 'OPERATOR_BMKG',
        created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
        updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
        PRIMARY KEY (profile_id),
        INDEX idx_regency_fp (regency_code, structure_fingerprint),
        INDEX idx_fingerprint (structure_fingerprint)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
    """
    sql_aliases = """
    CREATE TABLE IF NOT EXISTS cews_rainfall_station_aliases (
        id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
        regency_code VARCHAR(32) NOT NULL,
        source_code VARCHAR(64) NULL,
        source_name_norm VARCHAR(150) NOT NULL,
        station_id VARCHAR(50) NOT NULL,
        created_by VARCHAR(100) NOT NULL DEFAULT 'OPERATOR_BMKG',
        created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
        updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
        PRIMARY KEY (id),
        UNIQUE KEY uq_regency_alias (regency_code, source_name_norm),
        INDEX idx_station_id (station_id)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
    """
    try:
        with get_db() as conn:
            with conn.cursor() as cur:
                cur.execute(sql_profiles)
                cur.execute(sql_aliases)
            conn.commit()
    except Exception as exc:
        logger.warning("Could not ensure v2 rainfall profile tables: %s", exc)


def get_regency_stations(regency_code: str) -> List[Dict[str, Any]]:
    rc = regency_code.strip().upper()
    if rc not in REGENCY_REGISTRY:
        raise ValueError(f"Wilayah '{regency_code}' tidak dikenali.")
    target_master_reg = REGENCY_REGISTRY[rc]["master_regency"].lower()
    master = get_master_station_lookup()
    stations = [
        info
        for info in master.values()
        if (info.get("kabupaten") or "").strip().lower() == target_master_reg
    ]
    stations.sort(key=lambda x: x["station_name"])
    return stations


def get_regencies_metadata() -> List[Dict[str, Any]]:
    master = get_master_station_lookup()
    out = []
    for code, cfg in REGENCY_REGISTRY.items():
        target = cfg["master_regency"].lower()
        stns = [
            {
                "station_id": s["station_id"],
                "station_name": s["station_name"],
                "kabupaten": s["kabupaten"],
                "is_arg": s["is_arg"],
            }
            for s in master.values()
            if (s.get("kabupaten") or "").strip().lower() == target
        ]
        stns.sort(key=lambda x: x["station_name"])
        out.append({
            "code": code,
            "label": cfg["label"],
            "master_regency": cfg["master_regency"],
            "supports_raw": cfg["supports_raw"],
            "supports_legacy": cfg["supports_legacy"],
            "stations_count": len(stns),
            "stations": stns,
        })
    return out


def _load_db_station_aliases(regency_code: str) -> Dict[str, str]:
    aliases: Dict[str, str] = {}
    try:
        ensure_v2_profile_tables()
        with get_db() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT source_code, source_name_norm, station_id FROM cews_rainfall_station_aliases WHERE regency_code = %s",
                    (regency_code.upper(),),
                )
                for row in cur.fetchall():
                    if row.get("source_name_norm"):
                        aliases[row["source_name_norm"].strip().lower()] = row["station_id"].strip().upper()
                    if row.get("source_code"):
                        aliases[row["source_code"].strip().upper()] = row["station_id"].strip().upper()
    except Exception as exc:
        logger.warning("Could not load DB station aliases: %s", exc)
    return aliases


def save_template_profile(
    profile_name: str,
    regency_code: str,
    structure_fingerprint: str,
    sheet_rules: Dict[str, Any],
    header_config: Dict[str, Any],
    date_config: Dict[str, Any],
    value_config: Dict[str, Any],
    station_config: Dict[str, Any],
    ignored_columns: List[Any],
    symbol_mapping: Dict[str, str],
    station_aliases: Optional[List[Dict[str, str]]] = None,
    operator: str = "OPERATOR_BMKG",
    template_kind: str = "CUSTOM_MAPPED",
) -> Dict[str, Any]:
    ensure_v2_profile_tables()
    rc = regency_code.strip().upper()
    if rc not in REGENCY_REGISTRY:
        raise ValueError(f"Wilayah '{regency_code}' tidak valid.")

    profile_id = f"PROF_{rc}_{uuid.uuid4().hex[:10].upper()}"
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO cews_rainfall_template_profiles (
                    profile_id, profile_name, regency_code, template_kind, structure_fingerprint,
                    sheet_rules_json, header_config_json, date_config_json, value_config_json,
                    station_config_json, ignored_columns_json, symbol_mapping_json, version, created_by
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, '1.0.0', %s)
                """,
                (
                    profile_id,
                    profile_name.strip() or f"Profil {rc}",
                    rc,
                    template_kind,
                    structure_fingerprint,
                    json.dumps(sheet_rules),
                    json.dumps(header_config),
                    json.dumps(date_config),
                    json.dumps(value_config),
                    json.dumps(station_config),
                    json.dumps(ignored_columns),
                    json.dumps(symbol_mapping),
                    operator,
                ),
            )
            if station_aliases:
                for al in station_aliases:
                    sname = _norm_name(al.get("source_name", ""))
                    sid = (al.get("station_id") or "").strip().upper()
                    scode = (al.get("source_code") or "").strip().upper() or None
                    if sname and sid:
                        cur.execute(
                            """
                            INSERT INTO cews_rainfall_station_aliases
                                (regency_code, source_code, source_name_norm, station_id, created_by)
                            VALUES (%s, %s, %s, %s, %s)
                            ON DUPLICATE KEY UPDATE
                                source_code = VALUES(source_code),
                                station_id = VALUES(station_id),
                                created_by = VALUES(created_by),
                                updated_at = CURRENT_TIMESTAMP
                            """,
                            (rc, scode, sname, sid, operator),
                        )
        conn.commit()
    return {
        "profile_id": profile_id,
        "profile_name": profile_name,
        "regency_code": rc,
        "template_kind": template_kind,
        "structure_fingerprint": structure_fingerprint,
    }


def list_template_profiles(regency_code: Optional[str] = None) -> List[Dict[str, Any]]:
    ensure_v2_profile_tables()
    with get_db() as conn:
        with conn.cursor() as cur:
            if regency_code:
                cur.execute(
                    "SELECT * FROM cews_rainfall_template_profiles WHERE regency_code = %s ORDER BY updated_at DESC",
                    (regency_code.strip().upper(),),
                )
            else:
                cur.execute("SELECT * FROM cews_rainfall_template_profiles ORDER BY updated_at DESC")
            rows = cur.fetchall()
    out = []
    for r in rows:
        out.append({
            "profile_id": r["profile_id"],
            "profile_name": r["profile_name"],
            "regency_code": r["regency_code"],
            "template_kind": r["template_kind"],
            "structure_fingerprint": r["structure_fingerprint"],
            "sheet_rules": json.loads(r["sheet_rules_json"] or "{}"),
            "header_config": json.loads(r["header_config_json"] or "{}"),
            "date_config": json.loads(r["date_config_json"] or "{}"),
            "value_config": json.loads(r["value_config_json"] or "{}"),
            "station_config": json.loads(r["station_config_json"] or "{}"),
            "ignored_columns": json.loads(r["ignored_columns_json"] or "[]"),
            "symbol_mapping": json.loads(r["symbol_mapping_json"] or "{}"),
            "version": r["version"],
            "created_by": r["created_by"],
            "created_at": str(r["created_at"]),
            "updated_at": str(r["updated_at"]),
        })
    return out


def _find_profile_by_fingerprint(regency_code: str, fingerprint: str) -> Optional[Dict[str, Any]]:
    try:
        ensure_v2_profile_tables()
        with get_db() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT * FROM cews_rainfall_template_profiles
                    WHERE regency_code = %s AND structure_fingerprint = %s
                    ORDER BY updated_at DESC LIMIT 1
                    """,
                    (regency_code.strip().upper(), fingerprint),
                )
                r = cur.fetchone()
        if not r:
            return None
        return {
            "profile_id": r["profile_id"],
            "profile_name": r["profile_name"],
            "regency_code": r["regency_code"],
            "template_kind": r["template_kind"],
            "structure_fingerprint": r["structure_fingerprint"],
            "sheet_rules": json.loads(r["sheet_rules_json"] or "{}"),
            "header_config": json.loads(r["header_config_json"] or "{}"),
            "date_config": json.loads(r["date_config_json"] or "{}"),
            "value_config": json.loads(r["value_config_json"] or "{}"),
            "station_config": json.loads(r["station_config_json"] or "{}"),
            "ignored_columns": json.loads(r["ignored_columns_json"] or "[]"),
            "symbol_mapping": json.loads(r["symbol_mapping_json"] or "{}"),
            "version": r["version"],
        }
    except Exception as exc:
        logger.warning("Profile lookup failed: %s", exc)
        return None


# ==============================================================================
# 3. REGION-AWARE CANONICAL NORMALIZATION & STATION MATCHING
# ==============================================================================
def _norm_name(text: Any) -> str:
    if text is None:
        return ""
    s = str(text).strip().lower()
    s = re.sub(r"^\d+[\s._-]+", "", s)
    s = re.sub(r"[^a-z0-9\s]", " ", s)
    return " ".join(s.split())


def normalize_rainfall_value(
    raw_val: Any,
    profile_key: str = "MANUAL_CANONICAL",
    custom_symbol_map: Optional[Dict[str, str]] = None,
    blank_as_missing: bool = False,
) -> Tuple[Optional[float], str, str]:
    """
    Canonical region-aware meteorological value normalizer.
    Returns (rainfall_mm, obs_status, original_symbol).

    Statuses:
      - NOT_PROVIDED  : blank / None / whitespace when blank_as_missing=False (skipped)
      - OBSERVED_ZERO : explicit 0 mm observation -> standardized display '-'
      - OBSERVED_VALID: positive rainfall > 0 mm  -> numeric mm
      - TTU           : trace rainfall            -> standardized display 'TTU'
      - MISSING       : explicit missing or blank observation cell -> standardized display '9999'
      - DAMAGED       : damaged instrument marker -> standardized display '9999'
      - INVALID       : negative numeric value
      - UNRECOGNIZED  : unknown non-numeric text (flagged for operator review)
    """
    if raw_val is None or (isinstance(raw_val, str) and raw_val.strip() == ""):
        if blank_as_missing:
            return None, "MISSING", "9999"
        return None, "NOT_PROVIDED", ""

    # Build active symbol map
    active_map: Dict[str, Tuple[Optional[float], str]] = dict(
        REGION_SYMBOL_PROFILES.get(profile_key, REGION_SYMBOL_PROFILES["MANUAL_CANONICAL"])
    )
    if custom_symbol_map:
        for sym, target_status in custom_symbol_map.items():
            k = str(sym).strip().upper()
            st = str(target_status).strip().upper()
            if st == "OBSERVED_ZERO":
                active_map[k] = (0.0, "OBSERVED_ZERO")
            elif st == "TTU":
                active_map[k] = (0.0, "TTU")
            elif st == "MISSING":
                active_map[k] = (None, "MISSING")
            elif st == "DAMAGED":
                active_map[k] = (None, "DAMAGED")
            elif st == "NOT_PROVIDED":
                active_map[k] = (None, "NOT_PROVIDED")

    # Numeric Excel cells must still check special numeric codes (e.g. 0, 8888, 9999)
    if isinstance(raw_val, (int, float)) and not isinstance(raw_val, bool):
        if pd.isna(raw_val):
            return None, "NOT_PROVIDED", ""
        if raw_val < 0:
            return float(raw_val), "INVALID", str(raw_val)
        # Check integer string key first (e.g. "0", "8888", "9999")
        if float(raw_val).is_integer():
            int_key = str(int(raw_val))
            if int_key in active_map:
                rf, st = active_map[int_key]
                return rf, st, int_key
        float_key = str(round(float(raw_val), 2))
        if float_key in active_map:
            rf, st = active_map[float_key]
            return rf, st, float_key
        val = round(float(raw_val), 2)
        if val == 0.0:
            return 0.0, "OBSERVED_ZERO", "0"
        return val, "OBSERVED_VALID", str(raw_val)

    s_val = str(raw_val).strip()
    s_upper = s_val.upper()

    if s_upper in active_map:
        rf, st = active_map[s_upper]
        return rf, st, s_val

    # Try numeric string (supports comma decimal)
    try:
        f_val = float(s_val.replace(",", "."))
        if pd.isna(f_val):
            return None, "NOT_PROVIDED", ""
        if f_val < 0:
            return f_val, "INVALID", s_val
        if f_val.is_integer() and str(int(f_val)) in active_map:
            rf, st = active_map[str(int(f_val))]
            return rf, st, s_val
        val = round(f_val, 2)
        if val == 0.0:
            if "0" in active_map:
                rf, st = active_map["0"]
                return rf, st, s_val
            return 0.0, "OBSERVED_ZERO", s_val
        return val, "OBSERVED_VALID", s_val
    except ValueError:
        return None, "UNRECOGNIZED", s_val


def match_station_for_regency(
    regency_code: str,
    raw_code: Optional[str],
    raw_name: Optional[str],
    regency_stations: List[Dict[str, Any]],
    db_aliases: Dict[str, str],
    station_overrides: Optional[Dict[str, str]] = None,
) -> Tuple[Optional[str], str]:
    """
    Matches a source station code/name to a master station_id within the target regency.
    Never invents a station code.
    Returns (station_id_or_None, match_method).
    """
    rc = regency_code.strip().upper()
    valid_ids = {s["station_id"].upper(): s for s in regency_stations}
    code_clean = re.sub(r"[^A-Z0-9]", "", (raw_code or "").strip().upper())
    name_norm = _norm_name(raw_name)

    # 0. Operator overrides from current preview session
    if station_overrides:
        for k in (raw_code, raw_name, name_norm, code_clean):
            if k and k in station_overrides and station_overrides[k].upper() in valid_ids:
                return station_overrides[k].upper(), "OPERATOR_OVERRIDE"

    # 1. Exact station_id match
    if code_clean and code_clean in valid_ids:
        return code_clean, "EXACT_CODE"

    # 2. DB persistent alias match
    if code_clean and code_clean in db_aliases and db_aliases[code_clean] in valid_ids:
        return db_aliases[code_clean], "SAVED_ALIAS_CODE"
    if name_norm and name_norm in db_aliases and db_aliases[name_norm] in valid_ids:
        return db_aliases[name_norm], "SAVED_ALIAS_NAME"

    # 3. Built-in regency alias match
    builtin = RAW_STATION_ALIASES.get(rc, {})
    if name_norm:
        for alias_k, sid in builtin.items():
            if _norm_name(alias_k) == name_norm and sid in valid_ids:
                return sid, "BUILTIN_ALIAS_EXACT"

    # 4. Exact master station_name match
    if name_norm:
        for sid, info in valid_ids.items():
            if _norm_name(info["station_name"]) == name_norm:
                return sid, "EXACT_NAME"

    # 5. Substring match (only if uniquely matches 1 station in regency)
    if name_norm and len(name_norm) >= 4:
        candidates = set()
        for sid, info in valid_ids.items():
            m_norm = _norm_name(info["station_name"])
            if name_norm in m_norm or m_norm in name_norm:
                candidates.add(sid)
        for alias_k, sid in builtin.items():
            a_norm = _norm_name(alias_k)
            if (name_norm in a_norm or a_norm in name_norm) and sid in valid_ids:
                candidates.add(sid)
        if len(candidates) == 1:
            return next(iter(candidates)), "SUBSTRING_UNIQUE"
        if len(candidates) > 1:
            return None, "AMBIGUOUS_NAME"

    return None, "UNMAPPED"


def _compute_dasarian_bounds(year: int, month: int, dasarian: int) -> Tuple[date, date]:
    last_day = calendar.monthrange(year, month)[1]
    if dasarian == 1:
        return date(year, month, 1), date(year, month, 10)
    if dasarian == 2:
        return date(year, month, 11), date(year, month, 20)
    return date(year, month, 21), date(year, month, last_day)


def _extract_sheet_preview(ws, max_rows: int = 15, max_cols: int = 15) -> List[List[str]]:
    grid = []
    for r_idx, row in enumerate(ws.iter_rows(min_row=1, max_row=max_rows, max_col=max_cols, values_only=True), start=1):
        grid.append(["" if v is None else str(v)[:40] for v in row])
    return grid


def _compute_structure_fingerprint(wb) -> str:
    """Computes a structural fingerprint independent of filename or observation values."""
    sig_parts = []
    for sn in wb.sheetnames[:8]:
        ws = wb[sn]
        merged_cnt = len(ws.merged_cells.ranges) if hasattr(ws, "merged_cells") else 0
        header_tokens = []
        for r in ws.iter_rows(min_row=1, max_row=10, max_col=15, values_only=True):
            row_toks = [
                re.sub(r"\d+", "#", str(c).strip().lower())[:20]
                for c in (r or [])
                if c is not None and str(c).strip()
            ]
            if row_toks:
                header_tokens.append("|".join(row_toks[:8]))
        sig_parts.append(f"M{merged_cnt}::" + ";".join(header_tokens[:5]))
    return hashlib.sha256("||".join(sig_parts).encode("utf-8")).hexdigest()[:32]


# ==============================================================================
# 4. AUTOMATIC TEMPLATE DETECTION ENGINE
# ==============================================================================
def _inspect_karimun_raw(wb) -> Optional[Dict[str, Any]]:
    for sn in wb.sheetnames:
        ws = wb[sn]
        found_marker = 0
        for row in ws.iter_rows(min_row=1, max_row=120, max_col=12, values_only=True):
            for cell in (row or []):
                if cell is not None and "no. stasiun hujan" in str(cell).strip().lower():
                    found_marker += 1
        if found_marker >= 1:
            return {
                "template_kind": "RAW_KARIMUN",
                "template_label": "Template Mentah Karimun (Blok Stasiun Vertikal)",
                "is_raw": True,
                "target_sheet": sn,
                "station_blocks_detected": found_marker,
                "period_confirmation_required": True,
                "suggested_year": None,
                "suggested_month": None,
                "suggested_dasarian": None,
                "metadata_conflicts": [
                    "Metadata bulan dan tahun tidak tersedia lengkap pada file mentah Karimun. Operator wajib memilih bulan, tahun, dan dasarian."
                ],
                "confidence": "HIGH",
            }
    return None


def _inspect_lingga_raw(wb) -> Optional[Dict[str, Any]]:
    for sn in wb.sheetnames:
        ws = wb[sn]
        # Check for vertical dates/day numbers in col B (idx 1) and horizontal stations across C..J (idx 2..9)
        top_text = []
        for r in ws.iter_rows(min_row=1, max_row=8, max_col=14, values_only=True):
            for c in (r or []):
                if c is not None:
                    top_text.append(str(c).strip())
        joined_top = " ".join(top_text).lower()

        has_tanggal_col_b = False
        has_dasarian_col = False
        header_row_idx = None
        for r_idx, r in enumerate(ws.iter_rows(min_row=1, max_row=12, max_col=14, values_only=True), start=1):
            vals = [str(c).strip().lower() if c is not None else "" for c in (r or [])]
            if len(vals) > 1 and ("tgl" in vals[1] or "tanggal" in vals[1]):
                has_tanggal_col_b = True
                header_row_idx = r_idx
            if any("dasarian" in v or "das" == v for v in vals[8:]):
                has_dasarian_col = True

        # Count numeric day values 1..31 in col B below header
        day_hits = 0
        if header_row_idx:
            for r in ws.iter_rows(min_row=header_row_idx + 1, max_row=header_row_idx + 35, min_col=2, max_col=2, values_only=True):
                v = r[0] if r else None
                if isinstance(v, (datetime, date)) or (isinstance(v, (int, float)) and 1 <= int(v) <= 31):
                    day_hits += 1

        if has_tanggal_col_b and day_hits >= 2 and (has_dasarian_col or "lingga" in joined_top or "dabo" in joined_top or sn.strip().lower() in MONTH_NAME_TO_NUM):
            sheet_month = MONTH_NAME_TO_NUM.get(sn.strip().lower())
            title_month = None
            title_year = None
            for m_name, m_num in MONTH_NAME_TO_NUM.items():
                if len(m_name) >= 4 and re.search(rf"\b{m_name}\b", joined_top):
                    title_month = m_num
                    break
            m_yr = re.search(r"\b(20\d{2})\b", joined_top)
            if m_yr:
                title_year = int(m_yr.group(1))

            conflicts = []
            if sheet_month and title_month and sheet_month != title_month:
                conflicts.append(
                    f"Konflik periode terdeteksi: nama worksheet '{sn}' ({INDONESIAN_MONTHS[sheet_month - 1]}) "
                    f"berbeda dengan judul dokumen ({INDONESIAN_MONTHS[title_month - 1]} {title_year or ''}). "
                    "Konfirmasi bulan & tahun wajib dilakukan operator."
                )

            return {
                "template_kind": "RAW_LINGGA",
                "template_label": "Template Mentah Lingga / Dabo Singkep (Stasiun Horizontal)",
                "is_raw": True,
                "target_sheet": sn,
                "period_confirmation_required": True,
                "suggested_year": title_year,
                "suggested_month": title_month or sheet_month,
                "suggested_dasarian": None,
                "metadata_conflicts": conflicts,
                "confidence": "HIGH",
            }
    return None


def _inspect_anambas_raw(wb) -> Optional[Dict[str, Any]]:
    for sn in wb.sheetnames:
        ws = wb[sn]
        # Anambas: station metadata in cols A-F (idx 0..5), days 1..30/31 in cols G-AJ (idx 6..36)
        day_header_row = None
        for r_idx, r in enumerate(ws.iter_rows(min_row=1, max_row=12, max_col=42, values_only=True), start=1):
            vals = list(r or [])
            if len(vals) >= 16:
                seq = []
                for c in vals[6:16]:
                    try:
                        seq.append(int(float(str(c).strip())))
                    except Exception:
                        seq.append(-1)
                if seq == list(range(1, 11)):
                    day_header_row = r_idx
                    break
        if day_header_row:
            top_text = " ".join(
                str(c).strip()
                for r in ws.iter_rows(min_row=1, max_row=day_header_row, max_col=15, values_only=True)
                for c in (r or [])
                if c is not None
            )
            m_yr = re.search(r"\b(20\d{2})\b", top_text)
            sug_year = int(m_yr.group(1)) if m_yr else None
            sug_month = MONTH_NAME_TO_NUM.get(sn.strip().lower())
            if not sug_month:
                for m_name, m_num in MONTH_NAME_TO_NUM.items():
                    if len(m_name) >= 4 and re.search(rf"\b{m_name}\b", top_text.lower()):
                        sug_month = m_num
                        break
            return {
                "template_kind": "RAW_ANAMBAS",
                "template_label": "Template Mentah Kepulauan Anambas (Matriks Horizontal G-AJ)",
                "is_raw": True,
                "target_sheet": sn,
                "period_confirmation_required": True,
                "suggested_year": sug_year,
                "suggested_month": sug_month,
                "suggested_dasarian": None,
                "metadata_conflicts": [],
                "confidence": "HIGH",
            }
    return None


def _inspect_natuna_raw(wb) -> Optional[Dict[str, Any]]:
    for sn in wb.sheetnames:
        ws = wb[sn]
        # Natuna: station names in col A (idx 0), days 1..31 in cols B..AF (idx 1..31)
        day_header_row = None
        for r_idx, r in enumerate(ws.iter_rows(min_row=1, max_row=10, max_col=36, values_only=True), start=1):
            vals = list(r or [])
            if len(vals) >= 11:
                seq = []
                for c in vals[1:11]:
                    try:
                        seq.append(int(float(str(c).strip())))
                    except Exception:
                        seq.append(-1)
                if seq == list(range(1, 11)):
                    day_header_row = r_idx
                    break
        if day_header_row:
            sug_year = None
            sug_month = None
            conflicts = []
            m_yymm = re.fullmatch(r"(\d{2})(\d{2})", sn.strip())
            if m_yymm:
                yy, mm = int(m_yymm.group(1)), int(m_yymm.group(2))
                if 1 <= mm <= 12:
                    sug_year = 2000 + yy
                    sug_month = mm
                    conflicts.append(
                        f"Nama worksheet '{sn}' terdeteksi sebagai kandidat periode {INDONESIAN_MONTHS[mm - 1]} {sug_year}, "
                        "namun belum terverifikasi. Operator wajib mengonfirmasi bulan dan tahun."
                    )
            return {
                "template_kind": "RAW_NATUNA",
                "template_label": "Template Mentah Natuna (Matriks Stasiun Vertikal, Tanggal B-AF)",
                "is_raw": True,
                "target_sheet": sn,
                "period_confirmation_required": True,
                "suggested_year": sug_year,
                "suggested_month": sug_month,
                "suggested_dasarian": None,
                "metadata_conflicts": conflicts,
                "confidence": "HIGH",
            }
    return None


def _inspect_legacy_template(wb) -> Optional[Dict[str, Any]]:
    for sn in wb.sheetnames:
        if sn.strip().lower() == "data_pos_hujan":
            return {
                "template_kind": "LEGACY_BINTAN_XLSM",
                "template_label": "Template Lama Bintan (Macro Data_Pos_Hujan)",
                "is_raw": False,
                "target_sheet": sn,
                "period_confirmation_required": False,
                "suggested_year": None,
                "suggested_month": None,
                "suggested_dasarian": None,
                "metadata_conflicts": [],
                "confidence": "HIGH",
            }
    matched_legacy_sheets = 0
    for sn in wb.sheetnames[:10]:
        ws = wb[sn]
        for r in ws.iter_rows(min_row=1, max_row=2, max_col=4, values_only=True):
            hdr = [str(c).strip().lower() if c is not None else "" for c in (r or [])]
            if len(hdr) >= 2 and hdr[0] in ("tanggal", "date", "tanggal input") and (
                hdr[1] in ("ch", "curah_hujan", "curah hujan", "rainfall", "rr") or "ch" in hdr[1]
            ):
                matched_legacy_sheets += 1
                break
    if matched_legacy_sheets >= 1:
        return {
            "template_kind": "LEGACY_MULTI_SHEET",
            "template_label": f"Template Lama Multi-Sheet ({len(wb.sheetnames)} sheet)",
            "is_raw": False,
            "target_sheet": wb.sheetnames[0],
            "period_confirmation_required": False,
            "suggested_year": None,
            "suggested_month": None,
            "suggested_dasarian": None,
            "metadata_conflicts": [],
            "confidence": "HIGH",
        }
    return None


def detect_rainfall_template(
    file_bytes: bytes,
    filename: str,
    regency_code: str,
) -> Dict[str, Any]:
    """
    Automatic Template Detection Engine (structure-based, never relies solely on filename).
    Evaluates regency support matrix and saved persistent profiles.
    """
    rc = regency_code.strip().upper()
    if rc not in REGENCY_REGISTRY:
        raise ValueError(f"Wilayah '{regency_code}' tidak dikenali.")
    reg_cfg = REGENCY_REGISTRY[rc]

    fn_low = filename.lower()
    if fn_low.endswith(".xls") and not fn_low.endswith(".xlsx") and not fn_low.endswith(".xlsm"):
        return {
            "filename": filename,
            "status": "UNSUPPORTED_FORMAT",
            "template_kind": None,
            "template_label": "Format .xls (BIFF) tidak didukung",
            "is_raw": False,
            "error_reason": "Format Excel biner lama (.xls) tidak didukung oleh openpyxl. Simpan ulang sebagai .xlsx atau .xlsm.",
            "metadata_conflicts": [],
        }

    try:
        wb = openpyxl.load_workbook(io.BytesIO(file_bytes), data_only=True)
    except Exception as exc:
        return {
            "filename": filename,
            "status": "CORRUPT_FILE",
            "template_kind": None,
            "template_label": "Berkas rusak / tidak dapat dibaca",
            "is_raw": False,
            "error_reason": f"Gagal membuka workbook Excel: {exc}",
            "metadata_conflicts": [],
        }

    try:
        fingerprint = _compute_structure_fingerprint(wb)
        sheetnames = list(wb.sheetnames)
        first_ws = wb[sheetnames[0]] if sheetnames else None
        preview_grid = _extract_sheet_preview(first_ws) if first_ws else []

        # Ordered structural detectors:
        # 1. Explicit Bintan Macro (Data_Pos_Hujan) FIRST so its Col-B vertical dates never collide with Lingga raw
        # 2. Specific raw formats (Karimun, Anambas, Natuna, Lingga)
        # 3. Legacy multi-sheet
        has_bintan_sheet = any(s.strip().lower() == "data_pos_hujan" for s in sheetnames)
        detected = (
            _inspect_legacy_template(wb) if has_bintan_sheet else None
        ) or (
            _inspect_karimun_raw(wb)
            or _inspect_anambas_raw(wb)
            or _inspect_natuna_raw(wb)
            or _inspect_lingga_raw(wb)
            or _inspect_legacy_template(wb)
        )

        # Fallback to saved persistent custom profile by structure fingerprint
        if not detected:
            saved_prof = _find_profile_by_fingerprint(rc, fingerprint)
            if saved_prof:
                detected = {
                    "template_kind": "CUSTOM_MAPPED",
                    "profile_id": saved_prof["profile_id"],
                    "template_label": f"Profil Kustom Tersimpan: {saved_prof['profile_name']}",
                    "is_raw": True,
                    "target_sheet": saved_prof["sheet_rules"].get("sheet_name") or sheetnames[0],
                    "period_confirmation_required": True,
                    "suggested_year": None,
                    "suggested_month": None,
                    "suggested_dasarian": None,
                    "metadata_conflicts": [],
                    "confidence": "HIGH",
                }

        if not detected:
            return {
                "filename": filename,
                "status": "NEEDS_MAPPING",
                "template_kind": None,
                "template_label": "Format belum dikenali (Memerlukan Mapping Wizard)",
                "is_raw": True,
                "structure_fingerprint": fingerprint,
                "sheetnames": sheetnames,
                "preview_grid": preview_grid,
                "error_reason": "Struktur workbook tidak cocok dengan 4 template mentah, template lama, maupun profil tersimpan. Gunakan Mapping Wizard.",
                "metadata_conflicts": [],
            }

        # Enforce Regency Support Matrix
        tk = detected["template_kind"]
        if detected["is_raw"] and not reg_cfg["supports_raw"]:
            return {
                "filename": filename,
                "status": "UNSUPPORTED_FOR_REGENCY",
                "template_kind": tk,
                "template_label": detected["template_label"],
                "is_raw": True,
                "structure_fingerprint": fingerprint,
                "sheetnames": sheetnames,
                "error_reason": (
                    f"Wilayah {reg_cfg['label']} saat ini hanya mendukung Template Lama (legacy). "
                    f"Berkas terdeteksi sebagai {detected['template_label']}."
                ),
                "metadata_conflicts": detected.get("metadata_conflicts", []),
            }

        if detected["is_raw"] and tk != "CUSTOM_MAPPED" and reg_cfg["raw_template_kind"] and tk != reg_cfg["raw_template_kind"]:
            return {
                "filename": filename,
                "status": "REGENCY_TEMPLATE_MISMATCH",
                "template_kind": tk,
                "template_label": detected["template_label"],
                "is_raw": True,
                "structure_fingerprint": fingerprint,
                "sheetnames": sheetnames,
                "error_reason": (
                    f"Format berkas terdeteksi sebagai {detected['template_label']}, "
                    f"tidak sesuai dengan wilayah terpilih ({reg_cfg['label']})."
                ),
                "metadata_conflicts": detected.get("metadata_conflicts", []),
            }

        return {
            "filename": filename,
            "status": "DETECTED",
            "structure_fingerprint": fingerprint,
            "sheetnames": sheetnames,
            "preview_grid": preview_grid,
            **detected,
        }
    finally:
        wb.close()


# ==============================================================================
# 5. FOUR RAW EXCEL PARSERS + CUSTOM PROFILE PARSER + LEGACY ADAPTER
# ==============================================================================
def _is_summary_text(val: Any) -> bool:
    if val is None:
        return False
    low = str(val).strip().lower()
    return any(low.startswith(k) or f" {k}" in low for k in SUMMARY_ROW_KEYWORDS)


def _parse_day_number(val: Any, target_year: int, target_month: int) -> Optional[date]:
    if val is None:
        return None
    if isinstance(val, datetime):
        return val.date()
    if isinstance(val, date):
        return val
    if isinstance(val, (int, float)) and not isinstance(val, bool):
        if pd.isna(val):
            return None
        d_int = int(val)
        last_d = calendar.monthrange(target_year, target_month)[1]
        if 1 <= d_int <= last_d:
            return date(target_year, target_month, d_int)
        return None
    s = str(val).strip()
    if re.fullmatch(r"\d{1,2}", s):
        d_int = int(s)
        last_d = calendar.monthrange(target_year, target_month)[1]
        if 1 <= d_int <= last_d:
            return date(target_year, target_month, d_int)
    try:
        dt = pd.to_datetime(s, errors="coerce")
        if pd.notnull(dt):
            return dt.date()
    except Exception:
        pass
    return None


def parse_raw_karimun(
    file_bytes: bytes,
    filename: str,
    year: int,
    month: int,
    dasarian: Optional[int],
    regency_stations: List[Dict[str, Any]],
    db_aliases: Dict[str, str],
    station_overrides: Optional[Dict[str, str]] = None,
) -> Dict[str, Any]:
    """
    Parser for Karimun Raw Workbook:
    - Lembar1 / Lembar2 (skip empty sheets)
    - Multi-station vertical blocks identified by 'No. Stasiun Hujan'
    - Dynamic station count (no hardcoding to 7)
    - Vertical dates, CH values in adjacent column
    - Partial-period import: blank cells / missing days do NOT create records
    """
    wb = openpyxl.load_workbook(io.BytesIO(file_bytes), data_only=True)
    master = get_master_station_lookup()
    start_bound, end_bound = (
        _compute_dasarian_bounds(year, month, dasarian)
        if dasarian in (1, 2, 3)
        else (date(year, month, 1), date(year, month, calendar.monthrange(year, month)[1]))
    )

    entries: List[Dict[str, Any]] = []
    unmapped_stations: List[Dict[str, Any]] = []
    anomalies: List[Dict[str, Any]] = []
    recognized_sids: Set[str] = set()
    out_of_range = 0
    seen_keys: Set[Tuple[str, str]] = set()

    for sn in wb.sheetnames:
        ws = wb[sn]
        rows = list(ws.iter_rows(values_only=True))
        if not rows:
            continue

        # Locate all station blocks by scanning for 'No. Stasiun Hujan'
        block_starts: List[Tuple[int, int]] = []  # (row_idx, col_idx)
        for r_idx, row in enumerate(rows):
            for c_idx, cell in enumerate(row or []):
                if cell is not None and "no. stasiun hujan" in str(cell).strip().lower():
                    block_starts.append((r_idx, c_idx))

        if not block_starts:
            continue

        # Group blocks by column band so side-by-side or stacked blocks both work
        col_groups: Dict[int, List[int]] = {}
        for r_idx, c_idx in block_starts:
            col_groups.setdefault(c_idx, []).append(r_idx)

        for base_col, r_indices in col_groups.items():
            r_indices.sort()
            for idx_pos, start_r in enumerate(r_indices):
                end_r = r_indices[idx_pos + 1] if idx_pos + 1 < len(r_indices) else len(rows)

                # Extract station code & name near start_r
                raw_code = ""
                raw_name = ""
                for dr in range(0, min(4, end_r - start_r)):
                    row = rows[start_r + dr]
                    label = str(row[base_col]).strip().lower() if base_col < len(row) and row[base_col] is not None else ""
                    val_candidates = [
                        str(row[c]).strip()
                        for c in range(base_col + 1, min(len(row), base_col + 5))
                        if row[c] is not None and str(row[c]).strip() not in ("", ":")
                    ]
                    if "no. stasiun" in label and val_candidates:
                        raw_code = val_candidates[0]
                    elif ("nama" in label or "pos" in label or "stasiun" in label) and "no." not in label and val_candidates:
                        raw_name = val_candidates[0]

                sid, method = match_station_for_regency(
                    "KARIMUN", raw_code, raw_name, regency_stations, db_aliases, station_overrides
                )
                if not sid:
                    unmapped_stations.append({
                        "sheet": sn,
                        "source_code": raw_code,
                        "source_name": raw_name or f"Block@R{start_r + 1}C{base_col + 1}",
                        "reason": method,
                    })
                    continue
                recognized_sids.add(sid)

                # Find date header row inside block
                date_col = base_col
                ch_col = base_col + 1
                data_start = start_r + 2
                for r_i in range(start_r + 1, min(start_r + 8, end_r)):
                    row = rows[r_i]
                    for c_i in range(base_col, min(len(row), base_col + 5)):
                        txt = str(row[c_i]).strip().lower() if row[c_i] is not None else ""
                        if txt in ("tgl", "tanggal", "date"):
                            date_col = c_i
                            data_start = r_i + 1
                        elif any(k in txt for k in ("ch", "curah hujan", "hujan", "mm", "rr")):
                            ch_col = c_i

                for r_i in range(data_start, end_r):
                    row = rows[r_i]
                    if not row or date_col >= len(row):
                        continue
                    raw_d = row[date_col]
                    if _is_summary_text(raw_d):
                        break
                    d_obj = _parse_day_number(raw_d, year, month)
                    if not d_obj:
                        continue
                    if d_obj < start_bound or d_obj > end_bound:
                        out_of_range += 1
                        continue

                    raw_v = row[ch_col] if ch_col < len(row) else None
                    rf_mm, obs_status, orig_sym = normalize_rainfall_value(raw_v, "RAW_KARIMUN", blank_as_missing=True)
                    if obs_status == "NOT_PROVIDED":
                        continue

                    obs_str = d_obj.isoformat()
                    if (sid, obs_str) in seen_keys:
                        anomalies.append({"sheet": sn, "row": r_i + 1, "type": "DUPLICATE_KEY", "station_id": sid, "date": obs_str})
                        continue
                    seen_keys.add((sid, obs_str))

                    p_id, p_lbl, _, _, _ = date_to_dasarian_info(d_obj)
                    entries.append({
                        "station_id": sid,
                        "station_name": master[sid]["station_name"],
                        "kabupaten": master[sid]["kabupaten"],
                        "observation_date": obs_str,
                        "rainfall_mm": rf_mm,
                        "obs_status": obs_status,
                        "original_symbol": orig_sym,
                        "period_id": p_id,
                        "period_label": p_lbl,
                        "source_file": filename,
                        "template_kind": "RAW_KARIMUN",
                    })
    wb.close()
    return {
        "entries": entries,
        "recognized_stations": sorted(recognized_sids),
        "unmapped_stations": unmapped_stations,
        "anomalies": anomalies,
        "out_of_range_count": out_of_range,
    }


def parse_raw_lingga(
    file_bytes: bytes,
    filename: str,
    year: int,
    month: int,
    dasarian: Optional[int],
    regency_stations: List[Dict[str, Any]],
    db_aliases: Dict[str, str],
    station_overrides: Optional[Dict[str, str]] = None,
    target_sheet: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Parser for Lingga / Dabo Singkep Raw Workbook:
    - Multi-row headers & merged cells
    - Dates vertically in col B (idx 1)
    - Horizontal stations in cols C..J (dynamically bounded before Dasarian marker column)
    - Ignores Dasarian marker col and bottom accumulation table
    - Symbols: 0->OBSERVED_ZERO, '-'->MISSING, 8888->TTU, 9999->MISSING
    """
    wb = openpyxl.load_workbook(io.BytesIO(file_bytes), data_only=True)
    sn = target_sheet if target_sheet in wb.sheetnames else wb.sheetnames[0]
    ws = wb[sn]
    rows = list(ws.iter_rows(values_only=True))
    master = get_master_station_lookup()

    start_bound, end_bound = (
        _compute_dasarian_bounds(year, month, dasarian)
        if dasarian in (1, 2, 3)
        else (date(year, month, 1), date(year, month, calendar.monthrange(year, month)[1]))
    )

    # Locate header row with Tanggal in col B (idx 1)
    header_row_idx = 0
    for r_idx, row in enumerate(rows[:12]):
        val_b = str(row[1]).strip().lower() if len(row) > 1 and row[1] is not None else ""
        if "tgl" in val_b or "tanggal" in val_b:
            header_row_idx = r_idx
            break

    # Collect station columns starting at col C (idx 2) until Dasarian/Akumulasi column
    col_station_map: Dict[int, str] = {}
    unmapped_stations: List[Dict[str, Any]] = []
    recognized_sids: Set[str] = set()

    max_cols = max((len(r) for r in rows[header_row_idx:header_row_idx + 3]), default=0)
    for c_idx in range(2, max_cols):
        # Combine multi-row header text for this column
        hdr_parts = []
        for hr in range(header_row_idx, min(header_row_idx + 3, len(rows))):
            v = rows[hr][c_idx] if c_idx < len(rows[hr]) else None
            if v is not None and str(v).strip():
                hdr_parts.append(str(v).strip())
        hdr_text = " ".join(hdr_parts).strip()
        if not hdr_text:
            continue
        low = hdr_text.lower()
        if any(k in low for k in ("dasarian", "jumlah", "total", "rata", "akumulasi", "keterangan")):
            continue

        sid, method = match_station_for_regency(
            "LINGGA", hdr_text, hdr_text, regency_stations, db_aliases, station_overrides
        )
        if sid:
            col_station_map[c_idx] = sid
            recognized_sids.add(sid)
        else:
            unmapped_stations.append({"sheet": sn, "source_code": "", "source_name": hdr_text, "reason": method})

    entries: List[Dict[str, Any]] = []
    anomalies: List[Dict[str, Any]] = []
    seen_keys: Set[Tuple[str, str]] = set()
    out_of_range = 0

    for r_idx in range(header_row_idx + 1, len(rows)):
        row = rows[r_idx]
        if not row or len(row) <= 1:
            continue
        raw_d = row[1]
        if _is_summary_text(raw_d) or (len(row) > 0 and _is_summary_text(row[0])):
            break  # Stop at bottom accumulation table
        d_obj = _parse_day_number(raw_d, year, month)
        if not d_obj:
            continue
        if d_obj < start_bound or d_obj > end_bound:
            out_of_range += 1
            continue

        obs_str = d_obj.isoformat()
        p_id, p_lbl, _, _, _ = date_to_dasarian_info(d_obj)
        for c_idx, sid in col_station_map.items():
            raw_v = row[c_idx] if c_idx < len(row) else None
            rf_mm, obs_status, orig_sym = normalize_rainfall_value(raw_v, "RAW_LINGGA", blank_as_missing=True)
            if obs_status == "NOT_PROVIDED":
                continue
            if (sid, obs_str) in seen_keys:
                anomalies.append({"sheet": sn, "row": r_idx + 1, "type": "DUPLICATE_KEY", "station_id": sid, "date": obs_str})
                continue
            seen_keys.add((sid, obs_str))
            entries.append({
                "station_id": sid,
                "station_name": master[sid]["station_name"],
                "kabupaten": master[sid]["kabupaten"],
                "observation_date": obs_str,
                "rainfall_mm": rf_mm,
                "obs_status": obs_status,
                "original_symbol": orig_sym,
                "period_id": p_id,
                "period_label": p_lbl,
                "source_file": filename,
                "template_kind": "RAW_LINGGA",
            })

    wb.close()
    return {
        "entries": entries,
        "recognized_stations": sorted(recognized_sids),
        "unmapped_stations": unmapped_stations,
        "anomalies": anomalies,
        "out_of_range_count": out_of_range,
    }


def parse_raw_natuna(
    file_bytes: bytes,
    filename: str,
    year: int,
    month: int,
    dasarian: Optional[int],
    regency_stations: List[Dict[str, Any]],
    db_aliases: Dict[str, str],
    station_overrides: Optional[Dict[str, str]] = None,
    target_sheet: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Parser for Natuna Raw Workbook:
    - Station names vertically in col A (idx 0)
    - Days 1..31 horizontally in cols B..AF (idx 1..31)
    - Ignores col AG (accumulation) and col AH (rain days)
    - Symbols: 0->OBSERVED_ZERO, '-'->MISSING
    """
    wb = openpyxl.load_workbook(io.BytesIO(file_bytes), data_only=True)
    sn = target_sheet if target_sheet in wb.sheetnames else wb.sheetnames[0]
    ws = wb[sn]
    rows = list(ws.iter_rows(values_only=True))
    master = get_master_station_lookup()

    start_bound, end_bound = (
        _compute_dasarian_bounds(year, month, dasarian)
        if dasarian in (1, 2, 3)
        else (date(year, month, 1), date(year, month, calendar.monthrange(year, month)[1]))
    )
    last_day_of_month = calendar.monthrange(year, month)[1]

    # Locate day header row (1..10 starting at col B)
    day_header_row = 0
    day_col_map: Dict[int, int] = {}  # col_idx -> day_num
    for r_idx, row in enumerate(rows[:10]):
        temp_map = {}
        for c_idx in range(1, min(len(row), 33)):  # B..AF (max 31 days -> idx 1..31)
            val = row[c_idx]
            try:
                d_num = int(float(str(val).strip()))
                if 1 <= d_num <= 31:
                    temp_map[c_idx] = d_num
            except Exception:
                pass
        if len(temp_map) >= 10:
            day_header_row = r_idx
            day_col_map = temp_map
            break

    entries: List[Dict[str, Any]] = []
    unmapped_stations: List[Dict[str, Any]] = []
    anomalies: List[Dict[str, Any]] = []
    recognized_sids: Set[str] = set()
    seen_keys: Set[Tuple[str, str]] = set()
    out_of_range = 0

    # Determine which day columns actually have observation data across the sheet
    # (dates completely absent in the file do NOT generate records; blank cells on active dates -> 9999)
    active_natuna_days: Set[int] = set()
    for r_idx in range(day_header_row + 1, len(rows)):
        row = rows[r_idx]
        if not row or row[0] is None or str(row[0]).strip() == "" or _is_summary_text(row[0]):
            continue
        for c_idx, day_num in day_col_map.items():
            v = row[c_idx] if c_idx < len(row) else None
            if v is not None and str(v).strip() != "":
                active_natuna_days.add(day_num)

    for r_idx in range(day_header_row + 1, len(rows)):
        row = rows[r_idx]
        if not row or row[0] is None or str(row[0]).strip() == "":
            continue
        raw_name = str(row[0]).strip()
        if _is_summary_text(raw_name):
            continue

        sid, method = match_station_for_regency(
            "NATUNA", None, raw_name, regency_stations, db_aliases, station_overrides
        )
        if not sid:
            unmapped_stations.append({"sheet": sn, "source_code": "", "source_name": raw_name, "reason": method})
            continue
        recognized_sids.add(sid)

        for c_idx, day_num in day_col_map.items():
            if day_num > last_day_of_month or day_num not in active_natuna_days:
                continue
            d_obj = date(year, month, day_num)
            if d_obj < start_bound or d_obj > end_bound:
                out_of_range += 1
                continue
            raw_v = row[c_idx] if c_idx < len(row) else None
            rf_mm, obs_status, orig_sym = normalize_rainfall_value(raw_v, "RAW_NATUNA", blank_as_missing=True)
            if obs_status == "NOT_PROVIDED":
                continue
            obs_str = d_obj.isoformat()
            if (sid, obs_str) in seen_keys:
                continue
            seen_keys.add((sid, obs_str))
            p_id, p_lbl, _, _, _ = date_to_dasarian_info(d_obj)
            entries.append({
                "station_id": sid,
                "station_name": master[sid]["station_name"],
                "kabupaten": master[sid]["kabupaten"],
                "observation_date": obs_str,
                "rainfall_mm": rf_mm,
                "obs_status": obs_status,
                "original_symbol": orig_sym,
                "period_id": p_id,
                "period_label": p_lbl,
                "source_file": filename,
                "template_kind": "RAW_NATUNA",
            })

    wb.close()
    return {
        "entries": entries,
        "recognized_stations": sorted(recognized_sids),
        "unmapped_stations": unmapped_stations,
        "anomalies": anomalies,
        "out_of_range_count": out_of_range,
    }


def parse_raw_anambas(
    file_bytes: bytes,
    filename: str,
    year: int,
    month: int,
    dasarian: Optional[int],
    regency_stations: List[Dict[str, Any]],
    db_aliases: Dict[str, str],
    station_overrides: Optional[Dict[str, str]] = None,
    target_sheet: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Parser for Anambas Raw Workbook:
    - Station metadata in cols A-F (idx 0..5); stations without code matched by name
    - Days 1..30/31 in cols G-AJ (idx 6..36)
    - Ignores cols AK-AM (dasarian accumulations) and AN (monthly accumulation)
    - Symbols: '-'->OBSERVED_ZERO, 0->TTU, 9999->MISSING
    """
    wb = openpyxl.load_workbook(io.BytesIO(file_bytes), data_only=True)
    sn = target_sheet if target_sheet in wb.sheetnames else wb.sheetnames[0]
    ws = wb[sn]
    rows = list(ws.iter_rows(values_only=True))
    master = get_master_station_lookup()

    start_bound, end_bound = (
        _compute_dasarian_bounds(year, month, dasarian)
        if dasarian in (1, 2, 3)
        else (date(year, month, 1), date(year, month, calendar.monthrange(year, month)[1]))
    )
    last_day_of_month = calendar.monthrange(year, month)[1]

    day_header_row = 0
    day_col_map: Dict[int, int] = {}
    for r_idx, row in enumerate(rows[:12]):
        temp_map = {}
        for c_idx in range(6, min(len(row), 37)):  # G..AJ (idx 6..36 max)
            val = row[c_idx]
            try:
                d_num = int(float(str(val).strip()))
                if 1 <= d_num <= 31:
                    temp_map[c_idx] = d_num
            except Exception:
                pass
        if len(temp_map) >= 10:
            day_header_row = r_idx
            day_col_map = temp_map
            break

    entries: List[Dict[str, Any]] = []
    unmapped_stations: List[Dict[str, Any]] = []
    anomalies: List[Dict[str, Any]] = []
    recognized_sids: Set[str] = set()
    seen_keys: Set[Tuple[str, str]] = set()
    out_of_range = 0

    # Determine active day columns with at least one explicit observation in Anambas sheet
    active_anambas_days: Set[int] = set()
    for r_idx in range(day_header_row + 1, len(rows)):
        row = rows[r_idx]
        if not row:
            continue
        meta_cells = [str(row[c]).strip() if c < len(row) and row[c] is not None else "" for c in range(6)]
        if not any(meta_cells) or any(_is_summary_text(m) for m in meta_cells if m):
            continue
        for c_idx, day_num in day_col_map.items():
            v = row[c_idx] if c_idx < len(row) else None
            if v is not None and str(v).strip() != "":
                active_anambas_days.add(day_num)

    for r_idx in range(day_header_row + 1, len(rows)):
        row = rows[r_idx]
        if not row:
            continue
        meta_cells = [str(row[c]).strip() if c < len(row) and row[c] is not None else "" for c in range(6)]
        if not any(meta_cells):
            continue
        if any(_is_summary_text(m) for m in meta_cells if m):
            continue

        # Detect code-like cell (e.g. 21050101A) and match station name across A..F
        raw_code = ""
        text_candidates = []
        for m in meta_cells:
            if not m:
                continue
            if re.fullmatch(r"\d{7,9}[A-Za-z]?", m):
                raw_code = m
            elif not re.fullmatch(r"\d+", m):
                text_candidates.append(m)

        if not raw_code and not text_candidates:
            continue

        sid = None
        method = "UNMAPPED"
        # Try code first, then each non-numeric metadata cell in A..F
        if raw_code:
            sid, method = match_station_for_regency(
                "ANAMBAS", raw_code, text_candidates[0] if text_candidates else "", regency_stations, db_aliases, station_overrides
            )
        if not sid:
            for cand in text_candidates:
                sid, method = match_station_for_regency(
                    "ANAMBAS", None, cand, regency_stations, db_aliases, station_overrides
                )
                if sid:
                    break
        raw_name = text_candidates[0] if text_candidates else ""
        if not sid:
            unmapped_stations.append({"sheet": sn, "source_code": raw_code, "source_name": raw_name, "reason": method})
            continue
        recognized_sids.add(sid)

        for c_idx, day_num in day_col_map.items():
            if day_num > last_day_of_month or day_num not in active_anambas_days:
                continue
            d_obj = date(year, month, day_num)
            if d_obj < start_bound or d_obj > end_bound:
                out_of_range += 1
                continue
            raw_v = row[c_idx] if c_idx < len(row) else None
            rf_mm, obs_status, orig_sym = normalize_rainfall_value(raw_v, "RAW_ANAMBAS", blank_as_missing=True)
            if obs_status == "NOT_PROVIDED":
                continue
            obs_str = d_obj.isoformat()
            if (sid, obs_str) in seen_keys:
                continue
            seen_keys.add((sid, obs_str))
            p_id, p_lbl, _, _, _ = date_to_dasarian_info(d_obj)
            entries.append({
                "station_id": sid,
                "station_name": master[sid]["station_name"],
                "kabupaten": master[sid]["kabupaten"],
                "observation_date": obs_str,
                "rainfall_mm": rf_mm,
                "obs_status": obs_status,
                "original_symbol": orig_sym,
                "period_id": p_id,
                "period_label": p_lbl,
                "source_file": filename,
                "template_kind": "RAW_ANAMBAS",
            })

    wb.close()
    return {
        "entries": entries,
        "recognized_stations": sorted(recognized_sids),
        "unmapped_stations": unmapped_stations,
        "anomalies": anomalies,
        "out_of_range_count": out_of_range,
    }


def parse_custom_mapped_profile(
    file_bytes: bytes,
    filename: str,
    regency_code: str,
    profile: Dict[str, Any],
    year: int,
    month: int,
    dasarian: Optional[int],
    regency_stations: List[Dict[str, Any]],
    db_aliases: Dict[str, str],
    station_overrides: Optional[Dict[str, str]] = None,
) -> Dict[str, Any]:
    """Generic parser driven by a persistent Mapping Wizard profile."""
    wb = openpyxl.load_workbook(io.BytesIO(file_bytes), data_only=True)
    sn = profile.get("sheet_rules", {}).get("sheet_name") or wb.sheetnames[0]
    ws = wb[sn] if sn in wb.sheetnames else wb[wb.sheetnames[0]]
    rows = list(ws.iter_rows(values_only=True))
    master = get_master_station_lookup()

    start_bound, end_bound = (
        _compute_dasarian_bounds(year, month, dasarian)
        if dasarian in (1, 2, 3)
        else (date(year, month, 1), date(year, month, calendar.monthrange(year, month)[1]))
    )
    orientation = profile.get("date_config", {}).get("orientation", "VERTICAL")
    header_row = int(profile.get("header_config", {}).get("header_row", 1)) - 1
    date_col = int(profile.get("date_config", {}).get("date_col", 1)) - 1
    station_col = int(profile.get("station_config", {}).get("station_col", 1)) - 1
    value_col = int(profile.get("value_config", {}).get("value_col", 2)) - 1
    fixed_station_id = (profile.get("station_config", {}).get("fixed_station_id") or "").strip().upper()
    ignored_cols = set(int(c) - 1 for c in profile.get("ignored_columns", []))
    sym_map = profile.get("symbol_mapping", {})

    entries: List[Dict[str, Any]] = []
    unmapped_stations: List[Dict[str, Any]] = []
    recognized_sids: Set[str] = set()
    out_of_range = 0

    if orientation == "VERTICAL":
        for r_idx in range(header_row + 1, len(rows)):
            row = rows[r_idx]
            if not row or date_col >= len(row):
                continue
            if _is_summary_text(row[date_col]):
                break
            d_obj = _parse_day_number(row[date_col], year, month)
            if not d_obj:
                continue
            if d_obj < start_bound or d_obj > end_bound:
                out_of_range += 1
                continue
            if fixed_station_id and fixed_station_id in master:
                sid = fixed_station_id
            else:
                raw_st = str(row[station_col]).strip() if station_col < len(row) and row[station_col] is not None else ""
                sid, method = match_station_for_regency(
                    regency_code, raw_st, raw_st, regency_stations, db_aliases, station_overrides
                )
                if not sid:
                    unmapped_stations.append({"sheet": sn, "source_code": "", "source_name": raw_st, "reason": method})
                    continue
            recognized_sids.add(sid)
            raw_v = row[value_col] if value_col < len(row) else None
            rf_mm, obs_status, orig_sym = normalize_rainfall_value(raw_v, "MANUAL_CANONICAL", sym_map)
            if obs_status == "NOT_PROVIDED":
                continue
            p_id, p_lbl, _, _, _ = date_to_dasarian_info(d_obj)
            entries.append({
                "station_id": sid,
                "station_name": master[sid]["station_name"],
                "kabupaten": master[sid]["kabupaten"],
                "observation_date": d_obj.isoformat(),
                "rainfall_mm": rf_mm,
                "obs_status": obs_status,
                "original_symbol": orig_sym,
                "period_id": p_id,
                "period_label": p_lbl,
                "source_file": filename,
                "template_kind": "CUSTOM_MAPPED",
            })
    else:
        # HORIZONTAL: days across columns in header_row, station names in station_col
        last_d = calendar.monthrange(year, month)[1]
        day_cols: Dict[int, int] = {}
        if header_row < len(rows):
            for c_idx, cell in enumerate(rows[header_row]):
                if c_idx in ignored_cols or c_idx == station_col:
                    continue
                try:
                    dn = int(float(str(cell).strip()))
                    if 1 <= dn <= last_d:
                        day_cols[c_idx] = dn
                except Exception:
                    pass
        for r_idx in range(header_row + 1, len(rows)):
            row = rows[r_idx]
            if not row or station_col >= len(row) or row[station_col] is None:
                continue
            raw_st = str(row[station_col]).strip()
            if not raw_st or _is_summary_text(raw_st):
                continue
            sid, method = match_station_for_regency(
                regency_code, raw_st, raw_st, regency_stations, db_aliases, station_overrides
            )
            if not sid:
                unmapped_stations.append({"sheet": sn, "source_code": "", "source_name": raw_st, "reason": method})
                continue
            recognized_sids.add(sid)
            for c_idx, dn in day_cols.items():
                d_obj = date(year, month, dn)
                if d_obj < start_bound or d_obj > end_bound:
                    out_of_range += 1
                    continue
                raw_v = row[c_idx] if c_idx < len(row) else None
                rf_mm, obs_status, orig_sym = normalize_rainfall_value(raw_v, "MANUAL_CANONICAL", sym_map)
                if obs_status == "NOT_PROVIDED":
                    continue
                p_id, p_lbl, _, _, _ = date_to_dasarian_info(d_obj)
                entries.append({
                    "station_id": sid,
                    "station_name": master[sid]["station_name"],
                    "kabupaten": master[sid]["kabupaten"],
                    "observation_date": d_obj.isoformat(),
                    "rainfall_mm": rf_mm,
                    "obs_status": obs_status,
                    "original_symbol": orig_sym,
                    "period_id": p_id,
                    "period_label": p_lbl,
                    "source_file": filename,
                    "template_kind": "CUSTOM_MAPPED",
                })
    wb.close()
    return {
        "entries": entries,
        "recognized_stations": sorted(recognized_sids),
        "unmapped_stations": unmapped_stations,
        "anomalies": [],
        "out_of_range_count": out_of_range,
    }


def parse_legacy_via_existing(
    file_bytes: bytes,
    filename: str,
    regency_code: str,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Delegates to the validated legacy parse_rainfall_excel() parser to guarantee
    100% backward compatibility for Batam, Bintan, Tanjungpinang, and legacy templates,
    applying optional date range filtering.
    """
    from backend.ingestion_service import _STAGING_SESSIONS

    legacy_res = parse_rainfall_excel(file_bytes, filename)
    token = legacy_res.get("staging_token")
    session_data = _STAGING_SESSIONS.pop(token, {}) if token else {}
    raw_entries = session_data.get("entries", [])

    reg_stations = {s["station_id"].upper() for s in get_regency_stations(regency_code)}
    filtered = []
    out_of_range = 0
    for e in raw_entries:
        # Filter out blank None rows from legacy template that represent empty future rows
        if e.get("obs_status") == "MISSING" and e.get("original_symbol") in ("None", "", None):
            continue
        obs_d = e["observation_date"]
        if start_date and obs_d < start_date:
            out_of_range += 1
            continue
        if end_date and obs_d > end_date:
            out_of_range += 1
            continue
        # Note: Tanjungpinang legacy workbook historically bundles Bintan + Tanjungpinang;
        # keep all matched stations from the legacy file if regency is TANJUNGPINANG or BINTAN,
        # otherwise restrict to selected regency if station belongs to it.
        if regency_code.upper() not in ("TANJUNGPINANG", "BINTAN") and e["station_id"].upper() not in reg_stations:
            continue
        item = dict(e)
        item["source_file"] = filename
        item["template_kind"] = "LEGACY"
        filtered.append(item)

    return {
        "entries": filtered,
        "recognized_stations": sorted(set(e["station_id"] for e in filtered)),
        "unmapped_stations": [
            {"sheet": s, "source_code": "", "source_name": s, "reason": "UNRECOGNIZED_SHEET"}
            for s in legacy_res.get("summary", {}).get("unrecognized_stations", [])
        ],
        "anomalies": legacy_res.get("anomalies", []),
        "out_of_range_count": out_of_range,
        "legacy_date_range": legacy_res.get("summary", {}).get("date_range", {}),
    }


# ==============================================================================
# 6. MULTI-FILE DETECT, PREVIEW, DIFF & TRANSACTIONAL COMMIT
# ==============================================================================
def create_detect_batch_session(
    regency_code: str,
    files_payload: List[Tuple[str, bytes]],
) -> Dict[str, Any]:
    _cleanup_expired_sessions()
    rc = regency_code.strip().upper()
    if rc not in REGENCY_REGISTRY:
        raise ValueError(f"Wilayah '{regency_code}' tidak valid.")
    if not files_payload:
        raise ValueError("Minimal satu berkas Excel harus diunggah.")

    batch_session_id = f"DETECT_{rc}_{uuid.uuid4().hex[:12]}"
    file_records = []

    for idx, (fname, fbytes) in enumerate(files_payload):
        file_id = f"F{idx + 1}_{uuid.uuid4().hex[:6]}"
        if len(fbytes) > MAX_UPLOAD_BYTES:
            det = {
                "filename": fname,
                "status": "FILE_TOO_LARGE",
                "template_kind": None,
                "template_label": "Ukuran berkas melebihi batas 25 MB",
                "is_raw": False,
                "error_reason": f"Ukuran berkas {len(fbytes) / (1024 * 1024):.1f} MB melebihi batas maksimum 25 MB.",
                "metadata_conflicts": [],
            }
        else:
            det = detect_rainfall_template(fbytes, fname, rc)

        file_records.append({
            "file_id": file_id,
            "filename": fname,
            "file_size_bytes": len(fbytes),
            "file_sha256": hashlib.sha256(fbytes).hexdigest(),
            "file_bytes": fbytes,
            "detection": det,
        })

    _BATCH_SESSIONS[batch_session_id] = {
        "batch_session_id": batch_session_id,
        "regency_code": rc,
        "regency_label": REGENCY_REGISTRY[rc]["label"],
        "files": {fr["file_id"]: fr for fr in file_records},
        "created_at": datetime.now(),
        "preview": None,
    }

    return {
        "batch_session_id": batch_session_id,
        "regency_code": rc,
        "regency_label": REGENCY_REGISTRY[rc]["label"],
        "files": [
            {
                "file_id": fr["file_id"],
                "filename": fr["filename"],
                "file_size_bytes": fr["file_size_bytes"],
                **fr["detection"],
            }
            for fr in file_records
        ],
    }


def _compare_entries_against_db(entries: List[Dict[str, Any]]) -> Tuple[List[Dict[str, Any]], Dict[str, int], str]:
    """
    Compares parsed/manual entries against cews_rainfall_daily in MariaDB.
    Categorizes every entry as NEW, IDENTICAL, CONFLICT, or INVALID.
    Also tracks counts for MISSING, TTU, UNRECOGNIZED.
    """
    counts = {
        "total": len(entries),
        "new": 0,
        "identical": 0,
        "conflict": 0,
        "invalid": 0,
        "missing": 0,
        "ttu": 0,
        "unrecognized": 0,
    }
    valid_pairs = [
        (e["station_id"], e["observation_date"])
        for e in entries
        if e.get("obs_status") not in ("INVALID", "UNRECOGNIZED", "NOT_PROVIDED")
    ]
    existing_map: Dict[Tuple[str, str], Dict[str, Any]] = {}

    if valid_pairs:
        with get_db() as conn:
            with conn.cursor() as cur:
                chunk_size = 500
                for i in range(0, len(valid_pairs), chunk_size):
                    chunk = valid_pairs[i:i + chunk_size]
                    fmt = ",".join(["(%s, %s)"] * len(chunk))
                    flat = [x for pair in chunk for x in pair]
                    cur.execute(
                        f"SELECT station_id, observation_date, rainfall_mm, obs_status "
                        f"FROM cews_rainfall_daily WHERE (station_id, observation_date) IN ({fmt})",
                        flat,
                    )
                    for r in cur.fetchall():
                        k = (r["station_id"].upper(), r["observation_date"].strftime("%Y-%m-%d"))
                        existing_map[k] = r

    enriched = []
    for e in entries:
        item = dict(e)
        st = item["obs_status"]
        rf = item["rainfall_mm"]
        item["display_value"] = format_standard_display(rf, st)

        if st == "MISSING":
            counts["missing"] += 1
        elif st == "TTU":
            counts["ttu"] += 1

        if st in ("INVALID", "UNRECOGNIZED"):
            item["change_type"] = "INVALID"
            item["old_rainfall_mm"] = None
            item["old_obs_status"] = None
            item["diff"] = None
            counts["invalid"] += 1
            if st == "UNRECOGNIZED":
                counts["unrecognized"] += 1
            enriched.append(item)
            continue

        k = (item["station_id"].upper(), item["observation_date"])
        ex = existing_map.get(k)
        if not ex:
            item["change_type"] = "NEW"
            item["old_rainfall_mm"] = None
            item["old_obs_status"] = None
            item["diff"] = None
            counts["new"] += 1
        else:
            old_rf = float(ex["rainfall_mm"]) if ex["rainfall_mm"] is not None else None
            old_st = ex["obs_status"]
            item["old_rainfall_mm"] = old_rf
            item["old_obs_status"] = old_st

            same_rf = (old_rf == rf) or (old_rf is None and rf is None)
            same_st = (old_st == st)
            if same_rf and same_st:
                item["change_type"] = "IDENTICAL"
                item["diff"] = 0.0 if (rf is not None and old_rf is not None) else None
                counts["identical"] += 1
            else:
                item["change_type"] = "CONFLICT"
                item["diff"] = round(rf - old_rf, 2) if (rf is not None and old_rf is not None) else None
                counts["conflict"] += 1

        enriched.append(item)

    sorted_ex = sorted(
        (k[0], k[1], float(v["rainfall_mm"]) if v["rainfall_mm"] is not None else None, str(v["obs_status"]))
        for k, v in existing_map.items()
    )
    baseline_fp = hashlib.sha256(repr(sorted_ex).encode("utf-8")).hexdigest()
    return enriched, counts, baseline_fp


def preview_batch_session(
    batch_session_id: str,
    file_configs: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """
    Parses each included file in the batch using its detected/custom template & chosen period,
    merges records safely, compares against MariaDB, and returns full preview.
    """
    _cleanup_expired_sessions()
    if batch_session_id not in _BATCH_SESSIONS:
        raise ValueError("Sesi deteksi berkas tidak ditemukan atau sudah kedaluwarsa. Unggah ulang berkas.")

    session = _BATCH_SESSIONS[batch_session_id]
    rc = session["regency_code"]
    regency_stations = get_regency_stations(rc)
    db_aliases = _load_db_station_aliases(rc)

    all_entries: List[Dict[str, Any]] = []
    file_summaries = []
    global_seen: Set[Tuple[str, str]] = set()
    cross_file_duplicates = 0

    for fcfg in file_configs:
        fid = fcfg.get("file_id")
        if not fcfg.get("include", True):
            continue
        fr = session["files"].get(fid)
        if not fr:
            continue

        det = fr["detection"]
        tk = fcfg.get("template_kind_override") or det.get("template_kind")
        profile_id = fcfg.get("profile_id") or det.get("profile_id")
        overrides = fcfg.get("station_overrides") or {}
        fbytes = fr["file_bytes"]
        fname = fr["filename"]

        try:
            if tk == "RAW_KARIMUN":
                parsed = parse_raw_karimun(
                    fbytes, fname, int(fcfg["year"]), int(fcfg["month"]), fcfg.get("dasarian"),
                    regency_stations, db_aliases, overrides,
                )
            elif tk == "RAW_LINGGA":
                parsed = parse_raw_lingga(
                    fbytes, fname, int(fcfg["year"]), int(fcfg["month"]), fcfg.get("dasarian"),
                    regency_stations, db_aliases, overrides, det.get("target_sheet"),
                )
            elif tk == "RAW_NATUNA":
                parsed = parse_raw_natuna(
                    fbytes, fname, int(fcfg["year"]), int(fcfg["month"]), fcfg.get("dasarian"),
                    regency_stations, db_aliases, overrides, det.get("target_sheet"),
                )
            elif tk == "RAW_ANAMBAS":
                parsed = parse_raw_anambas(
                    fbytes, fname, int(fcfg["year"]), int(fcfg["month"]), fcfg.get("dasarian"),
                    regency_stations, db_aliases, overrides, det.get("target_sheet"),
                )
            elif tk == "CUSTOM_MAPPED" or profile_id:
                profs = [p for p in list_template_profiles(rc) if p["profile_id"] == profile_id]
                if not profs:
                    raise ValueError(f"Profil mapping '{profile_id}' tidak ditemukan.")
                parsed = parse_custom_mapped_profile(
                    fbytes, fname, rc, profs[0], int(fcfg["year"]), int(fcfg["month"]), fcfg.get("dasarian"),
                    regency_stations, db_aliases, overrides,
                )
            elif tk in ("LEGACY_BINTAN_XLSM", "LEGACY_MULTI_SHEET"):
                parsed = parse_legacy_via_existing(
                    fbytes, fname, rc, fcfg.get("start_date"), fcfg.get("end_date")
                )
            else:
                raise ValueError(f"Template berkas '{fname}' belum teridentifikasi atau tidak didukung.")

            file_entries = []
            for e in parsed["entries"]:
                k = (e["station_id"], e["observation_date"])
                if k in global_seen:
                    cross_file_duplicates += 1
                    continue
                global_seen.add(k)
                file_entries.append(e)

            all_entries.extend(file_entries)
            dates_present = sorted(set(e["observation_date"] for e in file_entries))
            file_summaries.append({
                "file_id": fid,
                "filename": fname,
                "template_kind": tk,
                "status": "PARSED",
                "records_count": len(file_entries),
                "recognized_stations_count": len(parsed["recognized_stations"]),
                "unmapped_stations": parsed["unmapped_stations"],
                "anomalies_count": len(parsed["anomalies"]),
                "out_of_range_count": parsed.get("out_of_range_count", 0),
                "date_coverage": {
                    "start": dates_present[0] if dates_present else None,
                    "end": dates_present[-1] if dates_present else None,
                    "days_count": len(dates_present),
                },
            })
        except Exception as exc:
            file_summaries.append({
                "file_id": fid,
                "filename": fname,
                "template_kind": tk,
                "status": "PARSE_ERROR",
                "error": str(exc),
                "records_count": 0,
                "recognized_stations_count": 0,
                "unmapped_stations": [],
                "anomalies_count": 0,
                "out_of_range_count": 0,
                "date_coverage": {"start": None, "end": None, "days_count": 0},
            })

    enriched, counts, baseline_fp = _compare_entries_against_db(all_entries)
    dates_all = sorted(set(e["observation_date"] for e in enriched))

    session["preview"] = {
        "entries": enriched,
        "counts": counts,
        "baseline_fingerprint": baseline_fp,
        "file_summaries": file_summaries,
        "cross_file_duplicates": cross_file_duplicates,
        "date_range": {"start": dates_all[0] if dates_all else None, "end": dates_all[-1] if dates_all else None},
    }

    return {
        "batch_session_id": batch_session_id,
        "regency_code": rc,
        "regency_label": session["regency_label"],
        "counts": counts,
        "cross_file_duplicates": cross_file_duplicates,
        "date_range": session["preview"]["date_range"],
        "file_summaries": file_summaries,
        "preview_rows": enriched[:300],
        "total_preview_rows": len(enriched),
    }


def _commit_entries_to_mariadb(
    entries: List[Dict[str, Any]],
    source_label: str,
    file_name_label: str,
    file_sha256: str,
    confirm_conflicts: bool,
    correction_reason: str,
    operator: str,
    baseline_fingerprint: Optional[str] = None,
    regency_code: str = "",
) -> Dict[str, Any]:
    """
    Shared atomic transactional commit to MariaDB used by BOTH Batch Upload v2 and Manual Input v2.
    Writes to:
      - staging_rainfall_import
      - cews_rainfall_daily
      - cews_rainfall_correction_log (for CONFLICT updates with mandatory reason)
      - cews_ingestion_history (with batch_items_json so existing batch rollback works)
    """
    ensure_ingestion_history_table()

    # Re-verify baseline fingerprint if provided (concurrency protection)
    if baseline_fingerprint:
        _, _, current_fp = _compare_entries_against_db(entries)
        if current_fp != baseline_fingerprint:
            raise ValueError(
                "Data di database berubah sejak pratinjau dibuat. Harap muat ulang pratinjau sebelum menyimpan."
            )

    conflict_entries = [e for e in entries if e.get("change_type") == "CONFLICT"]
    new_entries = [e for e in entries if e.get("change_type") == "NEW"]
    invalid_entries = [e for e in entries if e.get("change_type") == "INVALID"]
    identical_entries = [e for e in entries if e.get("change_type") == "IDENTICAL"]

    if conflict_entries and confirm_conflicts and not (correction_reason or "").strip():
        raise ValueError("Alasan koreksi wajib diisi saat menyetujui pembaruan data konflik.")

    if conflict_entries and not confirm_conflicts:
        if not new_entries:
            raise ValueError(
                f"Terdapat {len(conflict_entries)} data konflik dengan database. Centang persetujuan pembaruan konflik dan isi alasan koreksi."
            )
        to_write = list(new_entries)
        rejected_count = len(conflict_entries) + len(invalid_entries)
    else:
        to_write = list(new_entries) + list(conflict_entries)
        rejected_count = len(invalid_entries)

    if not to_write:
        raise ValueError("Tidak ada data baru atau perubahan yang valid untuk disimpan.")

    batch_id = f"BATCH_CH_{regency_code or 'KEPRI'}_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:4].upper()}"
    conn = get_raw_connection()
    conn.autocommit = False

    added_cnt = 0
    updated_cnt = 0
    missing_cnt = 0
    damaged_cnt = 0
    audit_items = []

    try:
        with conn.cursor() as cur:
            for e in to_write:
                sid = e["station_id"].upper()
                d_str = e["observation_date"]
                d_obj = date.fromisoformat(d_str)
                rf_val = e["rainfall_mm"]
                obs_st = e["obs_status"]
                orig_sym = (e.get("original_symbol") or "")[:20]

                if obs_st == "MISSING":
                    missing_cnt += 1
                elif obs_st == "DAMAGED":
                    damaged_cnt += 1

                is_obs = 0 if obs_st in ("MISSING", "DAMAGED") else 1
                is_mis = 1 if obs_st in ("MISSING", "DAMAGED") else 0
                data_qual = "DAMAGED" if obs_st == "DAMAGED" else ("MISSING" if obs_st == "MISSING" else "OBSERVED")

                # 1. Staging table
                cur.execute(
                    """
                    INSERT INTO staging_rainfall_import
                    (import_batch_id, station_id, observation_date, rainfall_mm, obs_status, original_symbol,
                     data_quality, is_observed, is_missing, is_gap_filled, rainfall_source, year, month, day, validation_status)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, 0, %s, %s, %s, %s, 'COMMITTED')
                    """,
                    (
                        batch_id, sid, d_str, rf_val, obs_st, orig_sym,
                        data_qual, is_obs, is_mis, source_label, d_obj.year, d_obj.month, d_obj.day,
                    ),
                )

                ch_type = e.get("change_type", "NEW")
                if ch_type == "NEW":
                    cur.execute(
                        """
                        INSERT INTO cews_rainfall_daily
                        (station_id, observation_date, rainfall_mm, obs_status, original_symbol,
                         data_quality, is_observed, is_missing, is_gap_filled, rainfall_source)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, 0, %s)
                        ON DUPLICATE KEY UPDATE
                            rainfall_mm = VALUES(rainfall_mm),
                            obs_status = VALUES(obs_status),
                            original_symbol = VALUES(original_symbol),
                            data_quality = VALUES(data_quality),
                            is_observed = VALUES(is_observed),
                            is_missing = VALUES(is_missing),
                            updated_at = CURRENT_TIMESTAMP
                        """,
                        (sid, d_str, rf_val, obs_st, orig_sym, data_qual, is_obs, is_mis, source_label),
                    )
                    added_cnt += 1
                else:
                    # CONFLICT -> log to cews_rainfall_correction_log & update
                    cur.execute(
                        """
                        INSERT INTO cews_rainfall_correction_log
                        (station_id, observation_date, old_rainfall_mm, new_rainfall_mm,
                         old_obs_status, new_obs_status, reason, approved_by, corrected_at)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, CURRENT_TIMESTAMP)
                        """,
                        (
                            sid, d_str, e.get("old_rainfall_mm"), rf_val,
                            e.get("old_obs_status"), obs_st, correction_reason.strip(), operator,
                        ),
                    )
                    cur.execute(
                        """
                        UPDATE cews_rainfall_daily
                        SET rainfall_mm = %s, obs_status = %s, original_symbol = %s,
                            data_quality = %s, is_observed = %s, is_missing = %s,
                            rainfall_source = %s, updated_at = CURRENT_TIMESTAMP
                        WHERE station_id = %s AND observation_date = %s
                        """,
                        (rf_val, obs_st, orig_sym, data_qual, is_obs, is_mis, source_label, sid, d_str),
                    )
                    updated_cnt += 1

                audit_items.append({
                    "station_id": sid,
                    "observation_date": d_str,
                    "rainfall_mm": rf_val,
                    "old_rainfall_mm": e.get("old_rainfall_mm"),
                    "obs_status": obs_st,
                    "old_obs_status": e.get("old_obs_status"),
                    "change_type": "UPDATED" if ch_type == "CONFLICT" else "NEW",
                })

            dates_w = [e["observation_date"] for e in to_write]
            periods_w = sorted(set(e["period_id"] for e in to_write if e.get("period_id")))
            scope_json = json.dumps({
                "regency_code": regency_code,
                "confirm_conflicts": confirm_conflicts,
                "correction_reason": correction_reason,
                "source": source_label,
                "periods": periods_w,
            })

            cur.execute(
                """
                INSERT INTO cews_ingestion_history
                (batch_id, data_type, file_name, file_sha256, date_range_start, date_range_end, target_period,
                 total_records, new_records, updated_records, identical_records, rejected_records,
                 missing_records, damaged_records, invalid_records, parser_version, approval_scope,
                 status, operator, notes, batch_items_json)
                VALUES (%s, 'CURAH_HUJAN', %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 'COMMITTED', %s, %s, %s)
                """,
                (
                    batch_id, file_name_label[:255], file_sha256[:64],
                    min(dates_w), max(dates_w), json.dumps(periods_w),
                    len(to_write), added_cnt, updated_cnt, len(identical_entries), rejected_count,
                    missing_cnt, damaged_cnt, len(invalid_entries), PARSER_VERSION, scope_json,
                    operator, correction_reason or f"Input CH {regency_code}",
                    json.dumps(audit_items, default=str),
                ),
            )
        conn.commit()
    except Exception as exc:
        conn.rollback()
        raise RuntimeError(f"Transaksi penyimpanan dibatalkan (rollback): {exc}")
    finally:
        conn.close()

    # Clear runtime caches to ensure immediate UI visibility
    for mod_clear in ("backend.data_service", "backend.main"):
        try:
            if mod_clear == "backend.data_service":
                from backend.data_service import clear_spi_cache
                clear_spi_cache()
            else:
                from backend.main import _SNAPSHOTS_CACHE
                _SNAPSHOTS_CACHE.clear()
        except Exception:
            pass

    return {
        "success": True,
        "batch_id": batch_id,
        "regency_code": regency_code,
        "records_added": added_cnt,
        "records_updated": updated_cnt,
        "records_identical_skipped": len(identical_entries),
        "records_rejected": rejected_count,
        "total_saved": added_cnt + updated_cnt,
        "operator": operator,
        "message": f"Berhasil menyimpan {added_cnt + updated_cnt} observasi ({added_cnt} baru, {updated_cnt} koreksi, {len(identical_entries)} identik dilewati).",
    }


def commit_batch_session(
    batch_session_id: str,
    confirm_conflicts: bool = False,
    correction_reason: str = "",
    operator: str = "OPERATOR_BMKG",
) -> Dict[str, Any]:
    _cleanup_expired_sessions()
    if batch_session_id not in _BATCH_SESSIONS:
        raise ValueError("Sesi batch tidak ditemukan atau sudah kedaluwarsa.")
    session = _BATCH_SESSIONS[batch_session_id]
    prev = session.get("preview")
    if not prev:
        raise ValueError("Pratinjau belum dijalankan untuk sesi ini.")

    fnames = [fs["filename"] for fs in prev["file_summaries"] if fs["status"] == "PARSED"]
    combined_sha = hashlib.sha256("|".join(sorted(fnames)).encode("utf-8")).hexdigest()

    result = _commit_entries_to_mariadb(
        entries=prev["entries"],
        source_label="FILE_UPLOAD_V2",
        file_name_label=", ".join(fnames) or "batch_upload.xlsx",
        file_sha256=combined_sha,
        confirm_conflicts=confirm_conflicts,
        correction_reason=correction_reason,
        operator=operator,
        baseline_fingerprint=prev["baseline_fingerprint"],
        regency_code=session["regency_code"],
    )
    _BATCH_SESSIONS.pop(batch_session_id, None)
    return result


# ==============================================================================
# 7. MULTI-DATE MANUAL INPUT (USING SAME CANONICAL ENGINE)
# ==============================================================================
def preview_manual_input_v2(
    regency_code: str,
    station_id: str,
    rows: List[Dict[str, Any]],
) -> Dict[str, Any]:
    rc = regency_code.strip().upper()
    sid = station_id.strip().upper()
    reg_stations = {s["station_id"].upper(): s for s in get_regency_stations(rc)}
    if sid not in reg_stations:
        raise ValueError(f"Stasiun '{sid}' tidak termasuk dalam wilayah {rc}.")
    stn_info = reg_stations[sid]

    parsed_entries = []
    seen_dates: Set[str] = set()
    for r in rows:
        d_str = (r.get("observation_date") or "").strip()
        raw_val = r.get("raw_value")
        rf_mm, obs_status, orig_sym = normalize_rainfall_value(raw_val, "MANUAL_CANONICAL")
        if obs_status == "NOT_PROVIDED":
            continue  # Blank row does NOT create a record

        try:
            d_obj = date.fromisoformat(d_str)
        except ValueError:
            parsed_entries.append({
                "station_id": sid,
                "station_name": stn_info["station_name"],
                "kabupaten": stn_info["kabupaten"],
                "observation_date": d_str,
                "rainfall_mm": None,
                "obs_status": "INVALID",
                "original_symbol": str(raw_val),
                "period_id": "",
                "period_label": "",
                "validation_note": "Format tanggal tidak valid (gunakan YYYY-MM-DD).",
            })
            continue

        if d_str in seen_dates:
            parsed_entries.append({
                "station_id": sid,
                "station_name": stn_info["station_name"],
                "kabupaten": stn_info["kabupaten"],
                "observation_date": d_str,
                "rainfall_mm": rf_mm,
                "obs_status": "INVALID",
                "original_symbol": orig_sym,
                "period_id": "",
                "period_label": "",
                "validation_note": "Tanggal duplikat dalam input manual.",
            })
            continue
        seen_dates.add(d_str)

        p_id, p_lbl, _, _, _ = date_to_dasarian_info(d_obj)
        parsed_entries.append({
            "station_id": sid,
            "station_name": stn_info["station_name"],
            "kabupaten": stn_info["kabupaten"],
            "observation_date": d_str,
            "rainfall_mm": rf_mm,
            "obs_status": obs_status,
            "original_symbol": orig_sym,
            "period_id": p_id,
            "period_label": p_lbl,
            "source_file": "MANUAL_INPUT",
            "template_kind": "MANUAL",
        })

    enriched, counts, baseline_fp = _compare_entries_against_db(parsed_entries)
    return {
        "regency_code": rc,
        "station_id": sid,
        "station_name": stn_info["station_name"],
        "counts": counts,
        "baseline_fingerprint": baseline_fp,
        "items": enriched,
    }


def commit_manual_input_v2(
    regency_code: str,
    station_id: str,
    rows: List[Dict[str, Any]],
    confirm_conflicts: bool = False,
    correction_reason: str = "",
    operator: str = "OPERATOR_BMKG",
    baseline_fingerprint: Optional[str] = None,
) -> Dict[str, Any]:
    prev = preview_manual_input_v2(regency_code, station_id, rows)
    return _commit_entries_to_mariadb(
        entries=prev["items"],
        source_label="MANUAL_INPUT_V2",
        file_name_label=f"MANUAL_{regency_code.upper()}_{station_id.upper()}",
        file_sha256=hashlib.sha256(json.dumps(rows, sort_keys=True).encode("utf-8")).hexdigest(),
        confirm_conflicts=confirm_conflicts,
        correction_reason=correction_reason,
        operator=operator,
        baseline_fingerprint=baseline_fingerprint,
        regency_code=regency_code.upper(),
    )
