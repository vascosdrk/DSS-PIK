"""
backend/ecmwf_forecast_service.py

Unified ECMWF Multi-Vintage & ENSMEAN Ingestion Service (Phase 2).
Handles both Probabilistic Forecasts (cews_forecast_snapshot, %) and
Deterministic Forecasts / ENSMEAN (cews_forecast_deterministic_snapshot, mm)
in a single atomic workflow while preserving full backward compatibility.

Key Guarantees:
1. Strict issue_date verification from workbook metadata / filename (ver_YYYY.MM.DD);
   NEVER falls back silently to datetime.now().
2. Dynamic monthly period detection (no hardcoded 6/7-month limit) with year rollover.
3. ENSMEAN Adjust priority: any header containing 'adjust' (case-insensitive) is
   ADJUSTED and takes priority over REGULAR; extra tokens (e.g. 'natuna') are ignored
   for station/region mapping; >1 ADJUSTED candidates for same target raises CONFLICT.
4. Historical/analysis columns (anlis, analisis, obs) are flagged and ignored as
   IGNORED NON-FORECAST COLUMN.
5. Three-file Dasarian release validation with shared release_group_id, uniform
   issue_date enforcement, target conflict detection, and multi-target workbook support.
6. Non-NOPOS-only canonical station mapping protecting duplicate NOPOS (e.g. 228D).
7. True atomic PyMySQL transactions (`conn.autocommit(False)` + `conn.begin()`)
   covering both tables + cews_ingestion_history, with zero partial commits.
8. Idempotent re-upload (IDENTICAL skipped) and audited reactivation after soft-void
   (REACTIVATED preserves prior void history in cews_ingestion_history).
"""

from __future__ import annotations

import csv
import hashlib
import io
import json
import logging
import re
import uuid
from collections import Counter
from datetime import date, datetime, timedelta
from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple

import openpyxl
from openpyxl.styles import Font, PatternFill

from backend.database import get_db, get_raw_connection

logger = logging.getLogger(__name__)

ECMWF_PARSER_VERSION = "2.2.0-ecmwf-unified"

OPERATIONAL_PROB_PARAMS_DASARIAN = ["pb20", "pa150", "pa200", "pa300"]
OPERATIONAL_PROB_PARAMS_BULANAN = ["pa300", "pa400", "pa500"]

INDONESIAN_MONTHS = [
    "Januari", "Februari", "Maret", "April", "Mei", "Juni",
    "Juli", "Agustus", "September", "Oktober", "November", "Desember",
]

MONTH_ABBR_MAP: Dict[str, int] = {
    "jan": 1, "januari": 1, "january": 1,
    "feb": 2, "peb": 2, "februari": 2, "february": 2,
    "mar": 3, "maret": 3, "march": 3,
    "apr": 4, "april": 4,
    "mei": 5, "may": 5,
    "jun": 6, "juni": 6, "june": 6,
    "jul": 7, "juli": 7, "july": 7,
    "agt": 8, "ags": 8, "agu": 8, "aug": 8, "agustus": 8, "august": 8,
    "sep": 9, "sept": 9, "september": 9,
    "okt": 10, "oct": 10, "oktober": 10, "october": 10,
    "nov": 11, "nop": 11, "november": 11,
    "des": 12, "dec": 12, "desember": 12, "december": 12,
}

# Patterns identifying non-forecast historical/analysis columns in EnsMean
_NON_FORECAST_PATTERN = re.compile(
    r"(?:^|\b)(anlis|analisis|analis|analysis|obs|observasi|aktual|actual)(?:\b|_)",
    re.IGNORECASE,
)

# Case-insensitive Adjust token detector (ignores extra descriptors like 'natuna')
_ADJUST_TOKEN_PATTERN = re.compile(r"\badjust(?:ed)?\b", re.IGNORECASE)


def ensure_deterministic_forecast_table() -> None:
    """Idempotently ensures `cews_forecast_deterministic_snapshot` exists."""
    sql = """
    CREATE TABLE IF NOT EXISTS cews_forecast_deterministic_snapshot (
        id                  BIGINT UNSIGNED   NOT NULL AUTO_INCREMENT,
        station_id          VARCHAR(20)       NOT NULL,
        forecast_resolution VARCHAR(20)       NOT NULL,
        issue_date          DATE              NOT NULL,
        target_year         SMALLINT UNSIGNED NOT NULL,
        target_month        TINYINT UNSIGNED  NOT NULL,
        target_dasarian     TINYINT UNSIGNED  NOT NULL DEFAULT 0,
        forecast_variable   VARCHAR(30)       NOT NULL DEFAULT 'ENSMEAN',
        value_mm            DECIMAL(8,2)      NOT NULL,
        unit                VARCHAR(10)       NOT NULL DEFAULT 'mm',
        adjustment_status   VARCHAR(20)       NOT NULL DEFAULT 'REGULAR',
        source_file         VARCHAR(255)      NOT NULL,
        source_sheet        VARCHAR(64)       NOT NULL DEFAULT 'EnsMean',
        source_column       VARCHAR(100)      NOT NULL,
        release_group_id    VARCHAR(64)       NULL,
        ingestion_batch_id  VARCHAR(64)       NULL,
        is_voided           TINYINT(1)        NOT NULL DEFAULT 0,
        void_reason         VARCHAR(255)      NULL,
        voided_by           VARCHAR(100)      NULL,
        voided_at           DATETIME          NULL,
        reactivation_count  SMALLINT UNSIGNED NOT NULL DEFAULT 0,
        reactivated_at      DATETIME          NULL,
        created_at          DATETIME          NOT NULL DEFAULT CURRENT_TIMESTAMP,
        updated_at          DATETIME          NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
        PRIMARY KEY (id),
        UNIQUE KEY uq_det_forecast_vintage (
            station_id, forecast_resolution, issue_date,
            target_year, target_month, target_dasarian, forecast_variable
        ),
        INDEX idx_det_res_target_issue (forecast_resolution, target_year, target_month, target_dasarian, issue_date),
        INDEX idx_det_vintage_batch (issue_date, release_group_id, ingestion_batch_id),
        INDEX idx_det_station_target (station_id, forecast_resolution, target_year, target_month, target_dasarian),
        INDEX idx_det_active_lookup (is_voided, forecast_resolution, target_year, target_month, target_dasarian, issue_date),
        CONSTRAINT fk_det_fc_station FOREIGN KEY (station_id) REFERENCES stations (station_id) ON UPDATE CASCADE,
        CONSTRAINT chk_det_val_nonneg CHECK (value_mm >= 0.00),
        CONSTRAINT chk_det_res_valid CHECK (forecast_resolution IN ('DASARIAN', 'BULANAN')),
        CONSTRAINT chk_det_adj_valid CHECK (adjustment_status IN ('REGULAR', 'ADJUSTED'))
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
    """
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(sql)
        conn.commit()


def extract_verified_issue_date(
    wb: openpyxl.Workbook,
    filename: str,
) -> Tuple[str, str]:
    """
    Extracts and validates issue_date from workbook metadata sheets and filename.
    NEVER falls back to datetime.now(). Raises ValueError on conflict or missing date.
    """
    workbook_issue_date_str: Optional[str] = None
    workbook_issue_source: Optional[str] = None

    for meta_sheet in ("Sheet1", "TabelPCH", "TabelPSH"):
        if meta_sheet in wb.sheetnames:
            try:
                ws_m = wb[meta_sheet]
                for r in ws_m.iter_rows(min_row=1, max_row=5, values_only=True):
                    for cell_v in (r or []):
                        if cell_v is None:
                            continue
                        cell_s = str(cell_v).strip()
                        m_iss = re.search(
                            r"(?:ver_|issue[:\s]+)(\d{4})[._-](\d{2})[._-](\d{2})",
                            cell_s,
                            re.IGNORECASE,
                        )
                        if m_iss and not workbook_issue_date_str:
                            cand = f"{m_iss.group(1)}-{m_iss.group(2)}-{m_iss.group(3)}"
                            date.fromisoformat(cand)  # strict calendar validation
                            workbook_issue_date_str = cand
                            workbook_issue_source = f"WORKBOOK_{meta_sheet}"
            except ValueError:
                raise
            except Exception:
                pass

    filename_issue_date_str: Optional[str] = None
    issue_match = (
        re.search(r"ver_(\d{4})[._-](\d{2})[._-](\d{2})", filename, re.IGNORECASE)
        or re.search(r"(?<!\d)(\d{4})[._-](\d{2})[._-](\d{2})(?!\d)", filename)
    )
    if issue_match:
        cand = f"{issue_match.group(1)}-{issue_match.group(2)}-{issue_match.group(3)}"
        try:
            date.fromisoformat(cand)
            filename_issue_date_str = cand
        except ValueError as exc:
            raise ValueError(
                f"Tanggal penerbitan pada nama berkas '{filename}' tidak valid ({cand})."
            ) from exc

    if workbook_issue_date_str and filename_issue_date_str and workbook_issue_date_str != filename_issue_date_str:
        raise ValueError(
            f"Konflik metadata issue_date terdeteksi: isi workbook menyatakan '{workbook_issue_date_str}' "
            f"({workbook_issue_source}), sedangkan nama file menyatakan '{filename_issue_date_str}'. "
            f"Harap perbaiki konsistensi berkas sebelum mengunggah."
        )

    if workbook_issue_date_str:
        return workbook_issue_date_str, workbook_issue_source or "WORKBOOK_META"
    if filename_issue_date_str:
        return filename_issue_date_str, "FILENAME_VERIFIED"

    raise ValueError(
        f"Issue date (tanggal penerbitan, misalnya pola 'ver_YYYY.MM.DD') tidak ditemukan pada metadata "
        f"workbook maupun nama berkas '{filename}'. Sistem menolak fallback otomatis ke tanggal sistem."
    )


def _strip_adjust_and_parens(header_text: str) -> str:
    """Strips parenthetical notes and adjust tokens to isolate the base period token."""
    cleaned = re.sub(r"\([^)]*\)", " ", header_text)
    cleaned = _ADJUST_TOKEN_PATTERN.sub(" ", cleaned)
    cleaned = re.sub(r"[^A-Za-z0-9\s]", " ", cleaned)
    return " ".join(cleaned.split()).strip()


def parse_period_token(
    raw_header: str,
    issue_dt: date,
    is_monthly: bool,
) -> Optional[Dict[str, Any]]:
    """
    Parses a single forecast period header (e.g. 'NovI', 'OktIII', 'Agt', 'Nov Adjust',
    'Agt (adjust natuna)') into canonical target_year, target_month, target_dasarian, period_id.
    Returns None if the token cannot be recognized as a valid period.
    """
    base = _strip_adjust_and_parens(raw_header)
    if not base:
        return None

    issue_year = issue_dt.year
    issue_month = issue_dt.month

    if is_monthly:
        tokens = [t.lower() for t in base.split()]
        m_num: Optional[int] = None
        for tok in tokens:
            if tok in MONTH_ABBR_MAP:
                m_num = MONTH_ABBR_MAP[tok]
                break
        if m_num is None:
            # Fallback prefix match for tightly joined month token
            low = base.lower()
            for m_k in sorted(MONTH_ABBR_MAP.keys(), key=len, reverse=True):
                if re.search(rf"\b{re.escape(m_k)}\b", low):
                    m_num = MONTH_ABBR_MAP[m_k]
                    break
        if m_num is None:
            return None

        # Explicit year in header if present (e.g. 'Jan 2027')
        yr_m = re.search(r"\b(20\d{2})\b", raw_header)
        if yr_m:
            t_year = int(yr_m.group(1))
        else:
            t_year = issue_year + 1 if m_num < issue_month else issue_year

        return {
            "target_year": t_year,
            "target_month": m_num,
            "target_dasarian": 0,
            "period_id": f"{t_year}-{m_num:02d}",
            "label": f"{INDONESIAN_MONTHS[m_num - 1]} {t_year}",
        }

    # Dasarian patterns: 'OktIII', 'NovI', 'MeiI', 'MeiII', 'Des II', 'Nov 3', 'Nov3'
    # Keep Roman numerals case-sensitive so trailing lowercase 'i' in 'Mei'/'Juni'/'Juli' is not consumed!
    compact = base.replace(" ", "")
    m_das = re.match(r"^([A-Za-z]+?)(III|II|I|[123])(20\d{2})?$", compact)
    if not m_das:
        return None
    m_str = m_das.group(1).lower()
    d_str = m_das.group(2).upper()
    yr_str = m_das.group(3)

    m_num = MONTH_ABBR_MAP.get(m_str)
    if m_num is None:
        return None
    t_das = 1 if d_str in ("I", "1") else (2 if d_str in ("II", "2") else 3)
    roman = "I" if t_das == 1 else ("II" if t_das == 2 else "III")

    if yr_str:
        t_year = int(yr_str)
    else:
        t_year = issue_year + 1 if m_num < issue_month else issue_year

    return {
        "target_year": t_year,
        "target_month": m_num,
        "target_dasarian": t_das,
        "period_id": f"{t_year}-{m_num:02d}-das{t_das}",
        "label": f"{INDONESIAN_MONTHS[m_num - 1]} {roman} {t_year}",
    }


def resolve_ensmean_columns(
    header_row: Sequence[Any],
    issue_dt: date,
    is_monthly: bool,
    start_col_index: int = 7,
) -> Dict[str, Any]:
    """
    Classifies and resolves all EnsMean columns starting from `start_col_index`:
    - Historical/analysis columns (anlis, analisis, obs, ...) -> ignored_non_forecast_columns
    - Columns containing 'adjust' (case-insensitive) -> ADJUSTED (extra tokens like 'natuna' ignored)
    - If both REGULAR and ADJUSTED exist for the same target period -> prioritize ADJUSTED
    - If >1 ADJUSTED candidates exist for the same target period -> record in conflicts (do NOT pick randomly)
    - Preserves original header string in `source_column`
    """
    ignored_non_forecast: List[Dict[str, Any]] = []
    unrecognized_columns: List[Dict[str, Any]] = []
    grouped: Dict[str, Dict[str, Any]] = {}
    period_order: List[str] = []

    for offset, raw_val in enumerate(header_row[start_col_index:]):
        if raw_val is None:
            continue
        col_str = str(raw_val).strip()
        if not col_str:
            continue
        col_idx = start_col_index + offset

        # 1. Non-forecast analysis/historical column check
        if _NON_FORECAST_PATTERN.search(col_str):
            ignored_non_forecast.append({
                "col_index": col_idx,
                "source_column": col_str,
                "classification": "IGNORED NON-FORECAST COLUMN",
                "reason": "Kolom analisis/observasi historis (bukan prakiraan ECMWF).",
            })
            continue

        # 2. Parse target period
        parsed = parse_period_token(col_str, issue_dt=issue_dt, is_monthly=is_monthly)
        if not parsed:
            unrecognized_columns.append({
                "col_index": col_idx,
                "source_column": col_str,
                "reason": "Header kolom tidak dikenali sebagai periode target yang valid.",
            })
            continue

        is_adjusted = bool(_ADJUST_TOKEN_PATTERN.search(col_str))
        pid = parsed["period_id"]
        if pid not in grouped:
            grouped[pid] = {"meta": parsed, "regular": [], "adjusted": []}
            period_order.append(pid)

        entry = {
            "col_index": col_idx,
            "source_column": col_str,
            "adjustment_status": "ADJUSTED" if is_adjusted else "REGULAR",
            **parsed,
        }
        if is_adjusted:
            grouped[pid]["adjusted"].append(entry)
        else:
            grouped[pid]["regular"].append(entry)

    selected_columns: List[Dict[str, Any]] = []
    skipped_regular_columns: List[Dict[str, Any]] = []
    conflicts: List[Dict[str, Any]] = []

    for pid in period_order:
        bucket = grouped[pid]
        adj_list = bucket["adjusted"]
        reg_list = bucket["regular"]

        if len(adj_list) > 1:
            conflicts.append({
                "period_id": pid,
                "label": bucket["meta"]["label"],
                "candidates": [c["source_column"] for c in adj_list],
                "reason": (
                    f"Konflik Adjust terdeteksi untuk periode {pid}: ditemukan {len(adj_list)} kolom "
                    f"Adjusted ({', '.join(c['source_column'] for c in adj_list)}). "
                    f"Sistem tidak memilih secara acak; harap klarifikasi workbook."
                ),
            })
            continue

        if len(adj_list) == 1:
            chosen = dict(adj_list[0])
            chosen["overrode_regular_columns"] = [r["source_column"] for r in reg_list]
            selected_columns.append(chosen)
            for r in reg_list:
                skipped_regular_columns.append({
                    "period_id": pid,
                    "source_column": r["source_column"],
                    "replaced_by": chosen["source_column"],
                })
        elif len(reg_list) == 1:
            chosen = dict(reg_list[0])
            chosen["overrode_regular_columns"] = []
            selected_columns.append(chosen)
        elif len(reg_list) > 1:
            conflicts.append({
                "period_id": pid,
                "label": bucket["meta"]["label"],
                "candidates": [c["source_column"] for c in reg_list],
                "reason": (
                    f"Konflik kolom Regular ganda untuk periode {pid}: "
                    f"{', '.join(c['source_column'] for c in reg_list)}."
                ),
            })

    return {
        "selected_columns": selected_columns,
        "skipped_regular_columns": skipped_regular_columns,
        "ignored_non_forecast_columns": ignored_non_forecast,
        "unrecognized_columns": unrecognized_columns,
        "conflicts": conflicts,
    }


def map_ecmwf_sheet_stations(
    ws: Any,
    master_lookup: Dict[str, Dict[str, Any]],
    add_map: Dict[str, Dict[Any, str]],
) -> Dict[str, Any]:
    """
    Maps rows of an ECMWF worksheet (Probability or EnsMean) to canonical DSS-PIK
    master stations without relying solely on NOPOS. Protects duplicate NOPOS codes
    (e.g., 228D = Duara [Lingga] and UPT Benih Pertanian [Anambas]).
    """
    raw_rows: List[Tuple[int, str, str, Tuple[Any, ...]]] = []
    nopos_freq: Counter = Counter()

    for row_idx, row in enumerate(ws.iter_rows(min_row=2, values_only=True), start=2):
        if not row or len(row) < 7 or (row[0] is None and row[1] is None):
            continue
        nopos = str(row[0]).strip().upper() if row[0] is not None else ""
        sname = str(row[1]).strip() if row[1] is not None else ""
        if not nopos and not sname:
            continue
        nopos_freq[nopos] += 1
        raw_rows.append((row_idx, nopos, sname, tuple(row)))

    # Build unique master name lookup (only names that uniquely identify 1 station)
    master_name_freq: Counter = Counter()
    master_by_name: Dict[str, str] = {}
    for mid, minfo in master_lookup.items():
        nm = " ".join(minfo["station_name"].strip().lower().split())
        master_name_freq[nm] += 1
        master_by_name[nm] = mid

    recognized_stations: List[str] = []
    station_rows: List[Tuple[int, str, str, str, Tuple[Any, ...]]] = []
    unmapped_external: List[Dict[str, Any]] = []
    duplicate_stations: List[Dict[str, Any]] = []
    ambiguous_stations: List[Dict[str, Any]] = []
    seen_sids = set()

    for row_idx, nopos, sname, row_vals in raw_rows:
        norm_sname = " ".join(sname.lower().split())
        is_duplicate_nopos = bool(nopos and nopos_freq[nopos] > 1)

        # Priority 1: Exact (NOPOS, normalized_name) pair in mapping_tambahan
        sid = add_map.get("pairs", {}).get((nopos, norm_sname))
        # Priority 2: Exact normalized_name in mapping_tambahan
        if not sid:
            sid = add_map.get("names", {}).get(norm_sname)
        # Priority 3: Exact unique master station_name
        if not sid and master_name_freq.get(norm_sname) == 1:
            sid = master_by_name[norm_sname]
        # Priority 4: NOPOS alone ONLY if NOPOS is unique in this sheet AND unique in mapping_tambahan/master
        if not sid and not is_duplicate_nopos:
            sid = add_map.get("nopos_unique", {}).get(nopos)
            if not sid and nopos in master_lookup:
                sid = nopos

        if not sid and is_duplicate_nopos:
            ambiguous_stations.append({
                "nopos": nopos,
                "name": sname,
                "row": row_idx,
                "reason": (
                    f"NOPOS '{nopos}' muncul lebih dari sekali dalam sheet dan nama '{sname}' "
                    f"tidak cocok eksak pada pasangan master/alias."
                ),
            })
            continue

        if sid and sid in master_lookup:
            if sid in seen_sids:
                duplicate_stations.append({
                    "nopos": nopos,
                    "name": sname,
                    "station_id": sid,
                    "row": row_idx,
                    "reason": "Station ID sudah dipetakan pada baris sebelumnya.",
                })
            else:
                seen_sids.add(sid)
                recognized_stations.append(sid)
                station_rows.append((row_idx, sid, nopos, sname, row_vals))
        else:
            unmapped_external.append({
                "nopos": nopos,
                "name": sname,
                "row": row_idx,
                "reason": "Pos di luar cakupan 57 stasiun master.",
            })

    missing_manual_master = [
        {"station_id": sid, "station_name": minfo["station_name"], "kabupaten": minfo["kabupaten"]}
        for sid, minfo in master_lookup.items()
        if not minfo["is_arg"] and sid not in seen_sids
    ]

    return {
        "station_rows": station_rows,
        "recognized_stations": recognized_stations,
        "summary": {
            "total_rows_in_file": len(raw_rows),
            "matched_stations_count": len(recognized_stations),
            "unmapped_external_count": len(unmapped_external),
            "duplicate_stations_count": len(duplicate_stations),
            "ambiguous_stations_count": len(ambiguous_stations),
            "missing_master_stations_count": len(missing_manual_master),
            "unmapped_details": unmapped_external,
            "duplicate_details": duplicate_stations,
            "ambiguous_details": ambiguous_stations,
            "missing_master_stations": missing_manual_master,
        },
    }


def _find_ensmean_sheet_name(wb: openpyxl.Workbook) -> Optional[str]:
    for s in wb.sheetnames:
        if s.strip().lower() == "ensmean":
            return s
    return None


def _load_existing_probability_maps(
    unique_years: List[int],
    fc_resolution: str,
    issue_date_str: str,
) -> Tuple[Dict[Tuple[Any, ...], Optional[float]], Dict[Tuple[Any, ...], List[Tuple[str, Optional[float]]]]]:
    exact_map: Dict[Tuple[Any, ...], Optional[float]] = {}
    other_map: Dict[Tuple[Any, ...], List[Tuple[str, Optional[float]]]] = {}
    if not unique_years:
        return exact_map, other_map
    try:
        with get_db() as conn:
            with conn.cursor() as cur:
                fmt_y = ",".join(["%s"] * len(unique_years))
                cur.execute(
                    f"""
                    SELECT station_id, forecast_resolution, target_year, target_month, target_dasarian,
                           issue_date, forecast_parameter, probability_value
                    FROM cews_forecast_snapshot
                    WHERE target_year IN ({fmt_y}) AND forecast_resolution = %s
                    """,
                    unique_years + [fc_resolution],
                )
                for r in cur.fetchall():
                    r_iss = r["issue_date"].strftime("%Y-%m-%d") if hasattr(r["issue_date"], "strftime") else str(r["issue_date"])
                    r_val = float(r["probability_value"]) if r["probability_value"] is not None else None
                    r_res = str(r.get("forecast_resolution", fc_resolution)).strip().upper()
                    key = (
                        r["station_id"], r_res, r["target_year"], r["target_month"],
                        r["target_dasarian"], r["forecast_parameter"],
                    )
                    if r_iss == issue_date_str:
                        exact_map[key] = r_val
                    else:
                        other_map.setdefault(key, []).append((r_iss, r_val))
    except Exception as exc:
        logger.warning("Could not load existing cews_forecast_snapshot for diff: %s", exc)
    return exact_map, other_map


def _load_existing_deterministic_maps(
    unique_years: List[int],
    fc_resolution: str,
    issue_date_str: str,
) -> Tuple[Dict[Tuple[Any, ...], Dict[str, Any]], Dict[Tuple[Any, ...], List[Tuple[str, Optional[float]]]]]:
    exact_map: Dict[Tuple[Any, ...], Dict[str, Any]] = {}
    other_map: Dict[Tuple[Any, ...], List[Tuple[str, Optional[float]]]] = {}
    if not unique_years:
        return exact_map, other_map
    try:
        with get_db() as conn:
            with conn.cursor() as cur:
                fmt_y = ",".join(["%s"] * len(unique_years))
                cur.execute(
                    f"""
                    SELECT station_id, forecast_resolution, target_year, target_month, target_dasarian,
                           issue_date, forecast_variable, value_mm, adjustment_status, source_column,
                           is_voided, void_reason, voided_by, voided_at
                    FROM cews_forecast_deterministic_snapshot
                    WHERE target_year IN ({fmt_y}) AND forecast_resolution = %s
                    """,
                    unique_years + [fc_resolution],
                )
                for r in cur.fetchall():
                    r_iss = r["issue_date"].strftime("%Y-%m-%d") if hasattr(r["issue_date"], "strftime") else str(r["issue_date"])
                    r_val = float(r["value_mm"]) if r["value_mm"] is not None else None
                    r_res = str(r.get("forecast_resolution", fc_resolution)).strip().upper()
                    key = (
                        r["station_id"], r_res, r["target_year"], r["target_month"],
                        r["target_dasarian"], r["forecast_variable"],
                    )
                    if r_iss == issue_date_str:
                        exact_map[key] = {
                            "value_mm": r_val,
                            "adjustment_status": r.get("adjustment_status"),
                            "source_column": r.get("source_column"),
                            "is_voided": int(r.get("is_voided") or 0),
                            "void_reason": r.get("void_reason"),
                            "voided_by": r.get("voided_by"),
                            "voided_at": r["voided_at"].isoformat() if hasattr(r.get("voided_at"), "isoformat") else r.get("voided_at"),
                        }
                    elif int(r.get("is_voided") or 0) == 0:
                        other_map.setdefault(key, []).append((r_iss, r_val))
    except Exception as exc:
        logger.warning("Could not load existing cews_forecast_deterministic_snapshot for diff: %s", exc)
    return exact_map, other_map


def parse_ecmwf_workbook_unified(
    file_bytes: bytes,
    filename: str,
    forecast_type: str = "DASARIAN",
    release_group_id: Optional[str] = None,
    register_session: bool = True,
) -> Dict[str, Any]:
    """
    Unified parser reading BOTH Probabilistic sheets (pb20/pa150/pa200/pa300 or
    pa300/pa400/pa500) AND Deterministic sheet (EnsMean) from a single ECMWF workbook.
    """
    from backend.ingestion_service import (
        _STAGING_SESSIONS,
        get_additional_mapping_lookup,
        get_master_station_lookup,
    )

    wb = openpyxl.load_workbook(io.BytesIO(file_bytes), data_only=True, read_only=True)
    try:
        master_lookup = get_master_station_lookup()
        add_map = get_additional_mapping_lookup()

        is_monthly = (
            ("BULAN" in forecast_type.upper())
            or ("bulanan" in filename.lower())
            or any(s in ["pa400", "pa500"] for s in wb.sheetnames)
        )
        active_sheets = OPERATIONAL_PROB_PARAMS_BULANAN if is_monthly else OPERATIONAL_PROB_PARAMS_DASARIAN
        valid_prob_sheets = [s for s in active_sheets if s in wb.sheetnames]
        ensmean_sheet_name = _find_ensmean_sheet_name(wb)

        if not valid_prob_sheets and not ensmean_sheet_name:
            raise ValueError(
                "Workbook tidak memiliki sheet probabilitas operasional (pb20, pa150..pa500) maupun sheet EnsMean."
            )

        # Strict verified issue_date (NO datetime.now() fallback)
        issue_date_str, issue_date_source = extract_verified_issue_date(wb, filename)
        issue_dt = date.fromisoformat(issue_date_str)

        # Confirm resolution from reference sheet header
        ref_sheet_name = (
            "pb20" if "pb20" in wb.sheetnames
            else ("pa300" if "pa300" in wb.sheetnames else (valid_prob_sheets[0] if valid_prob_sheets else ensmean_sheet_name))
        )
        ws_ref = wb[ref_sheet_name]
        ref_header = [c for c in next(ws_ref.iter_rows(min_row=1, max_row=1, values_only=True))]
        ref_period_cols = [c for c in ref_header[7:] if c is not None and str(c).strip() != ""]

        if ref_period_cols and not is_monthly:
            first_clean = _strip_adjust_and_parens(str(ref_period_cols[0])).lower()
            if first_clean in MONTH_ABBR_MAP:
                is_monthly = True
                active_sheets = OPERATIONAL_PROB_PARAMS_BULANAN
                valid_prob_sheets = [s for s in active_sheets if s in wb.sheetnames]

        fc_resolution = "BULANAN" if is_monthly else "DASARIAN"
        target_type = "PROBABILITAS_BULANAN" if is_monthly else "PROBABILITAS_DASARIAN"
        eff_release_group_id = release_group_id or f"ECMWF_{'BLN' if is_monthly else 'DAS'}_{issue_date_str}"

        # ------------------------------------------------------------------
        # 1. PARSE PROBABILISTIC SHEETS
        # ------------------------------------------------------------------
        prob_col_meta: List[Dict[str, Any]] = []
        prob_periods_detected: List[Dict[str, Any]] = []
        prob_station_mapping: Dict[str, Any] = {}
        prob_entries: List[Dict[str, Any]] = []
        anomalies: List[Dict[str, Any]] = []
        warnings_list: List[str] = []

        if valid_prob_sheets:
            prob_ref_ws = wb[valid_prob_sheets[0]]
            prob_header = [c for c in next(prob_ref_ws.iter_rows(min_row=1, max_row=1, values_only=True))]
            prob_map_res = map_ecmwf_sheet_stations(prob_ref_ws, master_lookup, add_map)
            prob_station_mapping = prob_map_res["summary"]

            for offset, raw_c in enumerate(prob_header[7:]):
                if raw_c is None or str(raw_c).strip() == "":
                    continue
                col_str = str(raw_c).strip()
                if _NON_FORECAST_PATTERN.search(col_str):
                    continue
                parsed = parse_period_token(col_str, issue_dt=issue_dt, is_monthly=is_monthly)
                if not parsed:
                    continue
                prob_col_meta.append({
                    "col_index": 7 + offset,
                    "col_name": col_str,
                    "horizon_index": len(prob_col_meta) + 1,
                    **parsed,
                })
                prob_periods_detected.append({
                    "period_id": parsed["period_id"],
                    "label": parsed["label"],
                    "target_year": parsed["target_year"],
                    "target_month": parsed["target_month"],
                    "target_dasarian": parsed["target_dasarian"],
                    "horizon": f"Bulan {len(prob_col_meta)}" if is_monthly else f"Dasarian {len(prob_col_meta)}",
                    "stations_count": len(prob_map_res["recognized_stations"]),
                })

            prob_years = sorted({m["target_year"] for m in prob_col_meta})
            exact_prob_map, other_prob_map = _load_existing_probability_maps(prob_years, fc_resolution, issue_date_str)

            for sheet_name in valid_prob_sheets:
                ws_p = wb[sheet_name]
                # Map rows per sheet (guarantees independence even if row order differs)
                sheet_map = map_ecmwf_sheet_stations(ws_p, master_lookup, add_map)
                param_name = sheet_name.strip()
                for _ridx, sid, _nopos, sname, row_vals in sheet_map["station_rows"]:
                    for meta in prob_col_meta:
                        c_idx = meta["col_index"]
                        val = row_vals[c_idx] if c_idx < len(row_vals) else None
                        prob_val: Optional[float] = None
                        is_rejected = False
                        if val is not None and str(val).strip() != "":
                            try:
                                f_v = float(val)
                                if f_v < 0 or f_v > 100:
                                    is_rejected = True
                                    anomalies.append({
                                        "dataset": "PROBABILITAS",
                                        "station_id": sid,
                                        "station_name": sname,
                                        "sheet": sheet_name,
                                        "period_id": meta["period_id"],
                                        "raw_value": val,
                                        "reason": f"Nilai probabilitas di luar rentang 0-100% ({f_v})",
                                    })
                                else:
                                    prob_val = round(f_v, 2)
                            except (TypeError, ValueError):
                                is_rejected = True
                                anomalies.append({
                                    "dataset": "PROBABILITAS",
                                    "station_id": sid,
                                    "station_name": sname,
                                    "sheet": sheet_name,
                                    "period_id": meta["period_id"],
                                    "raw_value": str(val),
                                    "reason": "Nilai non-numerik tidak valid",
                                })

                        key = (sid, fc_resolution, meta["target_year"], meta["target_month"], meta["target_dasarian"], param_name)
                        if is_rejected:
                            change_type, old_val, diff_val = "REJECTED", None, None
                        elif key in exact_prob_map:
                            old_val = exact_prob_map[key]
                            if (prob_val is not None and old_val is not None and abs(prob_val - old_val) < 1e-4) or (prob_val is None and old_val is None):
                                change_type, diff_val = "IDENTICAL", 0.0
                            else:
                                change_type = "UPDATED"
                                diff_val = round(prob_val - old_val, 2) if (prob_val is not None and old_val is not None) else None
                        elif key in other_prob_map:
                            sorted_v = sorted(other_prob_map[key], key=lambda x: x[0], reverse=True)
                            old_val = sorted_v[0][1]
                            change_type = "NEW VINTAGE"
                            diff_val = round(prob_val - old_val, 2) if (prob_val is not None and old_val is not None) else None
                        else:
                            change_type, old_val, diff_val = "NEW", None, None

                        prob_entries.append({
                            "station_id": sid,
                            "station_name": master_lookup[sid]["station_name"],
                            "forecast_resolution": fc_resolution,
                            "target_year": meta["target_year"],
                            "target_month": meta["target_month"],
                            "target_dasarian": meta["target_dasarian"],
                            "issue_date": issue_date_str,
                            "forecast_issue_date": issue_date_str,
                            "forecast_parameter": param_name,
                            "indicator": param_name,
                            "probability_value": prob_val,
                            "new_value": prob_val,
                            "old_value": old_val,
                            "diff": diff_val,
                            "period_id": meta["period_id"],
                            "target_period": meta["period_id"],
                            "period_label": meta["label"],
                            "source_file": filename,
                            "release_group_id": eff_release_group_id,
                            "change_type": change_type,
                        })

        # ------------------------------------------------------------------
        # 2. PARSE DETERMINISTIC SHEET (EnsMean) WITH ADJUST PRIORITY
        # ------------------------------------------------------------------
        det_entries: List[Dict[str, Any]] = []
        det_periods_detected: List[Dict[str, Any]] = []
        det_station_mapping: Dict[str, Any] = {}
        ensmean_column_resolution: Dict[str, Any] = {
            "selected_columns": [],
            "skipped_regular_columns": [],
            "ignored_non_forecast_columns": [],
            "unrecognized_columns": [],
            "conflicts": [],
        }

        if ensmean_sheet_name:
            ws_e = wb[ensmean_sheet_name]
            e_header = [c for c in next(ws_e.iter_rows(min_row=1, max_row=1, values_only=True))]
            ensmean_column_resolution = resolve_ensmean_columns(e_header, issue_dt=issue_dt, is_monthly=is_monthly)
            det_map_res = map_ecmwf_sheet_stations(ws_e, master_lookup, add_map)
            det_station_mapping = det_map_res["summary"]

            for conf in ensmean_column_resolution["conflicts"]:
                anomalies.append({
                    "dataset": "ENSMEAN",
                    "sheet": ensmean_sheet_name,
                    "period_id": conf["period_id"],
                    "candidates": conf["candidates"],
                    "reason": conf["reason"],
                    "severity": "CONFLICT",
                })

            sel_cols = ensmean_column_resolution["selected_columns"]
            for idx_c, col_meta in enumerate(sel_cols, start=1):
                det_periods_detected.append({
                    "period_id": col_meta["period_id"],
                    "label": col_meta["label"],
                    "target_year": col_meta["target_year"],
                    "target_month": col_meta["target_month"],
                    "target_dasarian": col_meta["target_dasarian"],
                    "source_column": col_meta["source_column"],
                    "adjustment_status": col_meta["adjustment_status"],
                    "horizon": f"Bulan {idx_c}" if is_monthly else f"Dasarian {idx_c}",
                    "stations_count": len(det_map_res["recognized_stations"]),
                })

            det_years = sorted({m["target_year"] for m in sel_cols})
            exact_det_map, other_det_map = _load_existing_deterministic_maps(det_years, fc_resolution, issue_date_str)

            for _ridx, sid, _nopos, sname, row_vals in det_map_res["station_rows"]:
                for col_meta in sel_cols:
                    c_idx = col_meta["col_index"]
                    val = row_vals[c_idx] if c_idx < len(row_vals) else None
                    val_mm: Optional[float] = None
                    is_rejected = False
                    if val is None or str(val).strip() == "":
                        # Never impute missing forecast value as 0
                        continue
                    try:
                        f_v = float(val)
                        if f_v < 0.0:
                            is_rejected = True
                            anomalies.append({
                                "dataset": "ENSMEAN",
                                "station_id": sid,
                                "station_name": sname,
                                "sheet": ensmean_sheet_name,
                                "period_id": col_meta["period_id"],
                                "source_column": col_meta["source_column"],
                                "raw_value": val,
                                "reason": f"Nilai ENSMEAN negatif tidak valid ({f_v} mm)",
                            })
                        else:
                            val_mm = round(f_v, 2)
                    except (TypeError, ValueError):
                        is_rejected = True
                        anomalies.append({
                            "dataset": "ENSMEAN",
                            "station_id": sid,
                            "station_name": sname,
                            "sheet": ensmean_sheet_name,
                            "period_id": col_meta["period_id"],
                            "source_column": col_meta["source_column"],
                            "raw_value": str(val),
                            "reason": "Nilai ENSMEAN non-numerik tidak valid",
                        })

                    key = (sid, fc_resolution, col_meta["target_year"], col_meta["target_month"], col_meta["target_dasarian"], "ENSMEAN")
                    prev_void_meta: Optional[Dict[str, Any]] = None

                    if is_rejected:
                        change_type, old_val, diff_val = "REJECTED", None, None
                    elif key in exact_det_map:
                        ex = exact_det_map[key]
                        old_val = ex["value_mm"]
                        if ex["is_voided"] == 1:
                            change_type = "REACTIVATED"
                            diff_val = round(val_mm - old_val, 2) if (val_mm is not None and old_val is not None) else None
                            prev_void_meta = {
                                "previous_value_mm": old_val,
                                "previous_void_reason": ex["void_reason"],
                                "previous_voided_by": ex["voided_by"],
                                "previous_voided_at": ex["voided_at"],
                            }
                        elif (
                            val_mm is not None
                            and old_val is not None
                            and abs(val_mm - old_val) < 1e-4
                            and ex["adjustment_status"] == col_meta["adjustment_status"]
                            and ex["source_column"] == col_meta["source_column"]
                        ):
                            change_type, diff_val = "IDENTICAL", 0.0
                        else:
                            change_type = "UPDATED"
                            diff_val = round(val_mm - old_val, 2) if (val_mm is not None and old_val is not None) else None
                    elif key in other_det_map:
                        sorted_v = sorted(other_det_map[key], key=lambda x: x[0], reverse=True)
                        old_val = sorted_v[0][1]
                        change_type = "NEW VINTAGE"
                        diff_val = round(val_mm - old_val, 2) if (val_mm is not None and old_val is not None) else None
                    else:
                        change_type, old_val, diff_val = "NEW", None, None

                    det_entries.append({
                        "station_id": sid,
                        "station_name": master_lookup[sid]["station_name"],
                        "forecast_resolution": fc_resolution,
                        "target_year": col_meta["target_year"],
                        "target_month": col_meta["target_month"],
                        "target_dasarian": col_meta["target_dasarian"],
                        "issue_date": issue_date_str,
                        "forecast_variable": "ENSMEAN",
                        "value_mm": val_mm,
                        "unit": "mm",
                        "adjustment_status": col_meta["adjustment_status"],
                        "source_file": filename,
                        "source_sheet": ensmean_sheet_name,
                        "source_column": col_meta["source_column"],
                        "release_group_id": eff_release_group_id,
                        "period_id": col_meta["period_id"],
                        "target_period": col_meta["period_id"],
                        "period_label": col_meta["label"],
                        "old_value": old_val,
                        "diff": diff_val,
                        "previous_void_meta": prev_void_meta,
                        "change_type": change_type,
                    })
        else:
            warnings_list.append("Sheet 'EnsMean' tidak ditemukan pada workbook; hanya data Probabilitas yang diproses.")

        # ------------------------------------------------------------------
        # 3. CROSS-CHECK COVERAGE DIFFERENCE (WARNING ONLY — NEVER REJECT OR FILL ZERO)
        # ------------------------------------------------------------------
        prob_pids = [p["period_id"] for p in prob_periods_detected]
        det_pids = [p["period_id"] for p in det_periods_detected]
        if prob_pids and det_pids and set(prob_pids) != set(det_pids):
            only_prob = sorted(set(prob_pids) - set(det_pids))
            only_det = sorted(set(det_pids) - set(prob_pids))
            warnings_list.append(
                f"Perbedaan cakupan target periode antara sheet Probabilitas ({len(prob_pids)} periode) dan "
                f"sheet EnsMean ({len(det_pids)} periode). Hanya di Probabilitas: {only_prob}; "
                f"Hanya di EnsMean: {only_det}. Seluruh data valid masing-masing sheet tetap diproses tanpa membuat record fiktif."
            )

        # Merge unique periods_detected across both sheets
        seen_pids = set()
        combined_periods: List[Dict[str, Any]] = []
        for p in prob_periods_detected + det_periods_detected:
            if p["period_id"] not in seen_pids:
                seen_pids.add(p["period_id"])
                combined_periods.append(p)

        # Aggregate counts (Probabilitas counts preserved for legacy IngestionPreviewResponse compatibility + ENSMEAN breakdown)
        prob_counts = Counter(e["change_type"] for e in prob_entries)
        det_counts = Counter(e["change_type"] for e in det_entries)
        has_adjust_conflicts = len(ensmean_column_resolution["conflicts"]) > 0

        diff_samples = [
            e for e in prob_entries if e["change_type"] in ("UPDATED", "NEW VINTAGE", "REJECTED")
        ][:80]
        if not diff_samples:
            diff_samples = prob_entries[:80]

        det_diff_samples = [
            e for e in det_entries if e["change_type"] in ("UPDATED", "NEW VINTAGE", "REACTIVATED", "REJECTED")
        ][:80]
        if not det_diff_samples:
            det_diff_samples = det_entries[:80]

        file_sha = hashlib.sha256(file_bytes).hexdigest()
        staging_token = f"TOKEN_PROB_{uuid.uuid4().hex[:12]}_{datetime.now().strftime('%Y%m%d%H%M%S')}"

        summary_payload = {
            "total_records": len(prob_entries),
            "total_stations_recognized": prob_station_mapping.get("matched_stations_count", det_station_mapping.get("matched_stations_count", 0)),
            "unmapped_external_count": prob_station_mapping.get("unmapped_external_count", 0),
            "duplicate_stations_count": prob_station_mapping.get("duplicate_stations_count", 0),
            "ambiguous_stations_count": prob_station_mapping.get("ambiguous_stations_count", 0),
            "missing_master_stations_count": prob_station_mapping.get("missing_master_stations_count", 0),
            "new_records": prob_counts["NEW"],
            "new_vintage_records": prob_counts["NEW VINTAGE"],
            "updated_records": prob_counts["UPDATED"],
            "identical_records": prob_counts["IDENTICAL"],
            "rejected_records": prob_counts["REJECTED"],
            "invalid_records": prob_counts["REJECTED"],
            "deterministic_summary": {
                "sheet_found": bool(ensmean_sheet_name),
                "total_records": len(det_entries),
                "new_records": det_counts["NEW"],
                "new_vintage_records": det_counts["NEW VINTAGE"],
                "updated_records": det_counts["UPDATED"],
                "identical_records": det_counts["IDENTICAL"],
                "reactivated_records": det_counts["REACTIVATED"],
                "rejected_records": det_counts["REJECTED"],
                "adjusted_columns_used": [
                    c["source_column"] for c in ensmean_column_resolution["selected_columns"]
                    if c["adjustment_status"] == "ADJUSTED"
                ],
                "ignored_non_forecast_columns": ensmean_column_resolution["ignored_non_forecast_columns"],
                "adjust_conflicts": ensmean_column_resolution["conflicts"],
            },
            "valid_sheets": valid_prob_sheets,
            "ensmean_sheet": ensmean_sheet_name,
            "release_group_id": eff_release_group_id,
            "warnings": warnings_list,
            "has_adjust_conflicts": has_adjust_conflicts,
            "requires_update_confirmation": (
                prob_counts["UPDATED"] > 0
                or det_counts["UPDATED"] > 0
                or det_counts["REACTIVATED"] > 0
            ),
        }

        session_obj = {
            "data_type": target_type,
            "filename": filename,
            "filenames": [filename],
            "file_sha256": file_sha,
            "parser_version": ECMWF_PARSER_VERSION,
            "forecast_issue_date": issue_date_str,
            "issue_date_source": issue_date_source,
            "forecast_type": target_type,
            "forecast_resolution": fc_resolution,
            "release_group_id": eff_release_group_id,
            "entries": prob_entries,
            "deterministic_entries": det_entries,
            "periods_detected": combined_periods,
            "prob_periods_detected": prob_periods_detected,
            "det_periods_detected": det_periods_detected,
            "station_mapping_summary": prob_station_mapping or det_station_mapping,
            "det_station_mapping_summary": det_station_mapping,
            "ensmean_column_resolution": ensmean_column_resolution,
            "warnings": warnings_list,
            "anomalies": anomalies,
            "created_at": datetime.now(),
            "summary": summary_payload,
        }

        if register_session:
            _STAGING_SESSIONS[staging_token] = session_obj

        return {
            "staging_token": staging_token,
            "data_type": target_type,
            "filename": filename,
            "file_sha256": file_sha,
            "parser_version": ECMWF_PARSER_VERSION,
            "forecast_issue_date": issue_date_str,
            "issue_date_source": issue_date_source,
            "forecast_resolution": fc_resolution,
            "release_group_id": eff_release_group_id,
            "periods_detected": combined_periods,
            "prob_periods_detected": prob_periods_detected,
            "det_periods_detected": det_periods_detected,
            "station_mapping_summary": prob_station_mapping or det_station_mapping,
            "ensmean_column_resolution": ensmean_column_resolution,
            "summary": summary_payload,
            "warnings": warnings_list,
            "anomalies": anomalies[:100],
            "diff_samples": diff_samples,
            "deterministic_diff_samples": det_diff_samples,
            "requires_confirmation": True,
            "requires_update_confirmation": summary_payload["requires_update_confirmation"],
            "has_adjust_conflicts": has_adjust_conflicts,
            "_session_obj": session_obj if not register_session else None,
        }
    finally:
        wb.close()


def parse_ecmwf_dasarian_release(
    files_list: Sequence[Tuple[str, bytes]],
) -> Dict[str, Any]:
    """
    Validates and parses a multi-file ECMWF Dasarian release (1-3 workbooks) as a
    single release_group_id:
    - All files must have identical verified issue_date.
    - Every file must be DASARIAN with identifiable target period(s) from workbook headers.
    - No conflicting duplicate target periods across files in the same release.
    - Multi-target dasarian workbooks (>1 target column in a file) remain supported.
    - If ANY file fails validation or has Adjust conflict, rejects the entire batch.
    """
    from backend.ingestion_service import _STAGING_SESSIONS

    if not files_list:
        raise ValueError("Minimal satu workbook ECMWF dasarian harus diunggah.")

    parsed_parts: List[Dict[str, Any]] = []
    issue_dates = set()
    seen_prob_targets: Dict[str, str] = {}
    seen_det_targets: Dict[str, str] = {}
    combined_sha = hashlib.sha256()

    for fname, fbytes in files_list:
        combined_sha.update(hashlib.sha256(fbytes).digest())
        part = parse_ecmwf_workbook_unified(
            file_bytes=fbytes,
            filename=fname,
            forecast_type="PROBABILITAS_DASARIAN",
            register_session=False,
        )
        if part["forecast_resolution"] != "DASARIAN":
            raise ValueError(
                f"Berkas '{fname}' terdeteksi sebagai resolusi {part['forecast_resolution']}, "
                f"bukan DASARIAN. Seluruh berkas dalam satu rangkaian penerbitan dasarian harus beresolusi DASARIAN."
            )
        if not part["periods_detected"]:
            raise ValueError(f"Target periode dasarian tidak dapat diidentifikasi dari header berkas '{fname}'.")
        if part["has_adjust_conflicts"]:
            raise ValueError(
                f"Konflik kolom Adjust pada berkas '{fname}': "
                f"{part['ensmean_column_resolution']['conflicts']}"
            )

        issue_dates.add(part["forecast_issue_date"])
        if len(issue_dates) > 1:
            raise ValueError(
                f"Konflik issue_date antarfile dalam satu rangkaian penerbitan dasarian: "
                f"{sorted(issue_dates)}. Seluruh workbook dalam satu penerbitan harus memiliki issue_date yang sama."
            )

        for p in part["prob_periods_detected"]:
            pid = p["period_id"]
            if pid in seen_prob_targets:
                raise ValueError(
                    f"Konflik target periode Probabilitas '{pid}' ditemukan ganda pada berkas "
                    f"'{seen_prob_targets[pid]}' dan '{fname}'."
                )
            seen_prob_targets[pid] = fname

        for p in part["det_periods_detected"]:
            pid = p["period_id"]
            if pid in seen_det_targets:
                raise ValueError(
                    f"Konflik target periode ENSMEAN '{pid}' ditemukan ganda pada berkas "
                    f"'{seen_det_targets[pid]}' dan '{fname}'."
                )
            seen_det_targets[pid] = fname

        parsed_parts.append(part)

    shared_issue = next(iter(issue_dates))
    release_group_id = f"ECMWF_DAS_{shared_issue}"

    all_prob_entries: List[Dict[str, Any]] = []
    all_det_entries: List[Dict[str, Any]] = []
    all_periods: List[Dict[str, Any]] = []
    all_warnings: List[str] = []
    all_anomalies: List[Dict[str, Any]] = []
    filenames: List[str] = []
    seen_pids = set()

    for part in parsed_parts:
        sess = part["_session_obj"]
        filenames.append(part["filename"])
        for e in sess["entries"]:
            e["release_group_id"] = release_group_id
            all_prob_entries.append(e)
        for e in sess["deterministic_entries"]:
            e["release_group_id"] = release_group_id
            all_det_entries.append(e)
        for p in part["periods_detected"]:
            if p["period_id"] not in seen_pids:
                seen_pids.add(p["period_id"])
                all_periods.append(p)
        all_warnings.extend(part["warnings"])
        all_anomalies.extend(part["anomalies"])

    prob_counts = Counter(e["change_type"] for e in all_prob_entries)
    det_counts = Counter(e["change_type"] for e in all_det_entries)
    merged_fname = " + ".join(filenames)
    file_sha = combined_sha.hexdigest()
    staging_token = f"TOKEN_PROB_REL_{uuid.uuid4().hex[:10]}_{datetime.now().strftime('%Y%m%d%H%M%S')}"

    summary_payload = {
        "files_count": len(filenames),
        "filenames": filenames,
        "release_group_id": release_group_id,
        "total_records": len(all_prob_entries),
        "total_stations_recognized": max((p["summary"]["total_stations_recognized"] for p in parsed_parts), default=0),
        "new_records": prob_counts["NEW"],
        "new_vintage_records": prob_counts["NEW VINTAGE"],
        "updated_records": prob_counts["UPDATED"],
        "identical_records": prob_counts["IDENTICAL"],
        "rejected_records": prob_counts["REJECTED"],
        "invalid_records": prob_counts["REJECTED"],
        "deterministic_summary": {
            "total_records": len(all_det_entries),
            "new_records": det_counts["NEW"],
            "new_vintage_records": det_counts["NEW VINTAGE"],
            "updated_records": det_counts["UPDATED"],
            "identical_records": det_counts["IDENTICAL"],
            "reactivated_records": det_counts["REACTIVATED"],
            "rejected_records": det_counts["REJECTED"],
        },
        "warnings": all_warnings,
        "has_adjust_conflicts": False,
        "requires_update_confirmation": (
            prob_counts["UPDATED"] > 0 or det_counts["UPDATED"] > 0 or det_counts["REACTIVATED"] > 0
        ),
    }

    _STAGING_SESSIONS[staging_token] = {
        "data_type": "PROBABILITAS_DASARIAN",
        "filename": merged_fname,
        "filenames": filenames,
        "is_dasarian_release_batch": True,
        "files_count": len(filenames),
        "file_sha256": file_sha,
        "parser_version": ECMWF_PARSER_VERSION,
        "forecast_issue_date": shared_issue,
        "issue_date_source": parsed_parts[0]["issue_date_source"],
        "forecast_type": "PROBABILITAS_DASARIAN",
        "forecast_resolution": "DASARIAN",
        "release_group_id": release_group_id,
        "entries": all_prob_entries,
        "deterministic_entries": all_det_entries,
        "periods_detected": all_periods,
        "station_mapping_summary": parsed_parts[0]["station_mapping_summary"],
        "warnings": all_warnings,
        "anomalies": all_anomalies,
        "created_at": datetime.now(),
        "summary": summary_payload,
    }

    return {
        "staging_token": staging_token,
        "data_type": "PROBABILITAS_DASARIAN",
        "filename": merged_fname,
        "filenames": filenames,
        "file_sha256": file_sha,
        "parser_version": ECMWF_PARSER_VERSION,
        "forecast_issue_date": shared_issue,
        "forecast_resolution": "DASARIAN",
        "release_group_id": release_group_id,
        "periods_detected": all_periods,
        "station_mapping_summary": parsed_parts[0]["station_mapping_summary"],
        "summary": summary_payload,
        "warnings": all_warnings,
        "anomalies": all_anomalies[:100],
        "diff_samples": all_prob_entries[:80],
        "deterministic_diff_samples": all_det_entries[:80],
        "requires_confirmation": True,
        "requires_update_confirmation": summary_payload["requires_update_confirmation"],
        "has_adjust_conflicts": False,
    }


def commit_ecmwf_unified_session(
    session: Dict[str, Any],
    prob_entries_to_commit: List[Dict[str, Any]],
    det_entries_to_commit: List[Dict[str, Any]],
    selected_periods_list: List[str],
    batch_id: str,
    operator: str = "OPERATOR_BMKG",
    rejected_count: int = 0,
    allow_update_existing: bool = False,
    _inject_failure_hook: Optional[Callable[[str], None]] = None,
) -> Dict[str, Any]:
    """
    Atomically commits Probabilistic entries (`cews_forecast_snapshot`), Deterministic
    ENSMEAN entries (`cews_forecast_deterministic_snapshot`), and audit trail
    (`cews_ingestion_history`) inside a SINGLE PyMySQL transaction
    (`conn.autocommit(False)` + `conn.begin()`).

    Zero partial commit: if either dataset insert/update fails, the entire transaction
    is rolled back cleanly.
    """
    if session.get("summary", {}).get("has_adjust_conflicts"):
        raise ValueError(
            "Commit ditolak: terdapat konflik kolom Adjust pada sheet EnsMean yang belum diklarifikasi."
        )

    # Enforce complete 3-file release when committing a multi-file Dasarian release batch
    if session.get("is_dasarian_release_batch") and int(session.get("files_count", 0)) != 3:
        raise ValueError(
            f"Commit penerbitan dasarian lengkap wajib terdiri dari 3 workbook yang valid "
            f"(ditemukan {session.get('files_count', 0)} file). Tidak diperbolehkan partial release."
        )

    fc_resolution = session.get("forecast_resolution") or (
        "BULANAN" if "BULAN" in str(session.get("data_type", "")).upper() else "DASARIAN"
    )
    release_group_id = session.get("release_group_id")
    fname = session.get("filename", "ecmwf_upload.xlsx")

    # Enforce explicit confirmation for UPDATED / REACTIVATED records
    has_updates = any(e.get("change_type") == "UPDATED" for e in prob_entries_to_commit) or any(
        e.get("change_type") in ("UPDATED", "REACTIVATED") for e in det_entries_to_commit
    )
    if has_updates and not allow_update_existing:
        prob_entries_to_commit = [e for e in prob_entries_to_commit if e.get("change_type") != "UPDATED"]
        det_entries_to_commit = [
            e for e in det_entries_to_commit if e.get("change_type") not in ("UPDATED", "REACTIVATED")
        ]

    conn = get_raw_connection()
    conn.autocommit(False)
    conn.begin()
    try:
        with conn.cursor() as cur:
            prob_written = 0
            det_written = 0
            det_reactivated = 0

            # 1. Commit Probabilistic Snapshot
            for e in prob_entries_to_commit:
                if e.get("probability_value") is None or e.get("change_type") in ("IDENTICAL", "REJECTED"):
                    continue
                if _inject_failure_hook:
                    _inject_failure_hook("before_prob_insert")
                cur.execute(
                    """
                    INSERT INTO cews_forecast_snapshot
                    (station_id, forecast_resolution, target_year, target_month, target_dasarian,
                     issue_date, forecast_parameter, probability_value, source_file,
                     release_group_id, ingestion_batch_id, snapshot_timestamp)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, CURRENT_TIMESTAMP)
                    ON DUPLICATE KEY UPDATE
                        probability_value = VALUES(probability_value),
                        source_file = VALUES(source_file),
                        release_group_id = VALUES(release_group_id),
                        ingestion_batch_id = VALUES(ingestion_batch_id),
                        snapshot_timestamp = CURRENT_TIMESTAMP;
                    """,
                    (
                        e["station_id"], fc_resolution, e["target_year"], e["target_month"], e["target_dasarian"],
                        e["issue_date"], e["forecast_parameter"], e["probability_value"],
                        e.get("source_file", fname)[:255], release_group_id, batch_id,
                    ),
                )
                prob_written += 1

            # 2. Commit Deterministic ENSMEAN Snapshot (including audited reactivation after void)
            reactivation_audit_records: List[Dict[str, Any]] = []
            for e in det_entries_to_commit:
                if e.get("value_mm") is None or e.get("change_type") in ("IDENTICAL", "REJECTED"):
                    continue
                if _inject_failure_hook:
                    _inject_failure_hook("before_det_insert")

                is_reactivation = e.get("change_type") == "REACTIVATED"
                if is_reactivation:
                    det_reactivated += 1
                    reactivation_audit_records.append({
                        "action": "REACTIVATE_AFTER_VOID",
                        "station_id": e["station_id"],
                        "forecast_resolution": fc_resolution,
                        "issue_date": e["issue_date"],
                        "period_id": e["period_id"],
                        "new_value_mm": e["value_mm"],
                        "source_column": e["source_column"],
                        "adjustment_status": e["adjustment_status"],
                        **(e.get("previous_void_meta") or {}),
                    })
                    cur.execute(
                        """
                        INSERT INTO cews_forecast_deterministic_snapshot
                        (station_id, forecast_resolution, issue_date, target_year, target_month, target_dasarian,
                         forecast_variable, value_mm, unit, adjustment_status, source_file, source_sheet,
                         source_column, release_group_id, ingestion_batch_id, is_voided, reactivation_count, reactivated_at)
                        VALUES (%s, %s, %s, %s, %s, %s, 'ENSMEAN', %s, 'mm', %s, %s, %s, %s, %s, %s, 0, 1, CURRENT_TIMESTAMP)
                        ON DUPLICATE KEY UPDATE
                            value_mm = VALUES(value_mm),
                            adjustment_status = VALUES(adjustment_status),
                            source_file = VALUES(source_file),
                            source_sheet = VALUES(source_sheet),
                            source_column = VALUES(source_column),
                            release_group_id = VALUES(release_group_id),
                            ingestion_batch_id = VALUES(ingestion_batch_id),
                            is_voided = 0,
                            void_reason = NULL,
                            voided_by = NULL,
                            voided_at = NULL,
                            reactivation_count = reactivation_count + 1,
                            reactivated_at = CURRENT_TIMESTAMP;
                        """,
                        (
                            e["station_id"], fc_resolution, e["issue_date"], e["target_year"], e["target_month"],
                            e["target_dasarian"], e["value_mm"], e["adjustment_status"],
                            e.get("source_file", fname)[:255], e.get("source_sheet", "EnsMean"),
                            e["source_column"], release_group_id, batch_id,
                        ),
                    )
                else:
                    cur.execute(
                        """
                        INSERT INTO cews_forecast_deterministic_snapshot
                        (station_id, forecast_resolution, issue_date, target_year, target_month, target_dasarian,
                         forecast_variable, value_mm, unit, adjustment_status, source_file, source_sheet,
                         source_column, release_group_id, ingestion_batch_id)
                        VALUES (%s, %s, %s, %s, %s, %s, 'ENSMEAN', %s, 'mm', %s, %s, %s, %s, %s, %s)
                        ON DUPLICATE KEY UPDATE
                            value_mm = VALUES(value_mm),
                            adjustment_status = VALUES(adjustment_status),
                            source_file = VALUES(source_file),
                            source_sheet = VALUES(source_sheet),
                            source_column = VALUES(source_column),
                            release_group_id = VALUES(release_group_id),
                            ingestion_batch_id = VALUES(ingestion_batch_id);
                        """,
                        (
                            e["station_id"], fc_resolution, e["issue_date"], e["target_year"], e["target_month"],
                            e["target_dasarian"], e["value_mm"], e["adjustment_status"],
                            e.get("source_file", fname)[:255], e.get("source_sheet", "EnsMean"),
                            e["source_column"], release_group_id, batch_id,
                        ),
                    )
                det_written += 1

            # 3. Record Unified Audit Trail in cews_ingestion_history (same transaction!)
            new_total = sum(1 for e in prob_entries_to_commit if e.get("change_type") in ("NEW", "NEW VINTAGE"))
            updated_total = sum(1 for e in prob_entries_to_commit if e.get("change_type") == "UPDATED")
            identical_total = sum(1 for e in prob_entries_to_commit if e.get("change_type") == "IDENTICAL")

            det_new_total = sum(1 for e in det_entries_to_commit if e.get("change_type") in ("NEW", "NEW VINTAGE"))
            det_upd_total = sum(1 for e in det_entries_to_commit if e.get("change_type") in ("UPDATED", "REACTIVATED"))
            det_id_total = sum(1 for e in det_entries_to_commit if e.get("change_type") == "IDENTICAL")

            audit_items = [
                {
                    "dataset": "PROBABILITAS",
                    "station_id": e["station_id"],
                    "forecast_resolution": fc_resolution,
                    "issue_date": e["issue_date"],
                    "target_year": e["target_year"],
                    "target_month": e["target_month"],
                    "target_dasarian": e["target_dasarian"],
                    "forecast_parameter": e["forecast_parameter"],
                    "probability_value": e.get("probability_value"),
                    "old_value": e.get("old_value"),
                    "change_type": e.get("change_type", "NEW"),
                }
                for e in prob_entries_to_commit
            ] + [
                {
                    "dataset": "ENSMEAN",
                    "station_id": e["station_id"],
                    "forecast_resolution": fc_resolution,
                    "issue_date": e["issue_date"],
                    "target_year": e["target_year"],
                    "target_month": e["target_month"],
                    "target_dasarian": e["target_dasarian"],
                    "forecast_variable": "ENSMEAN",
                    "value_mm": e.get("value_mm"),
                    "adjustment_status": e.get("adjustment_status"),
                    "source_column": e.get("source_column"),
                    "old_value": e.get("old_value"),
                    "change_type": e.get("change_type", "NEW"),
                }
                for e in det_entries_to_commit
            ] + reactivation_audit_records

            cur.execute(
                """
                INSERT INTO cews_ingestion_history
                (batch_id, data_type, file_name, file_sha256, target_period,
                 total_records, new_records, updated_records, identical_records, rejected_records,
                 parser_version, status, operator, batch_items_json)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 'COMMITTED', %s, %s);
                """,
                (
                    batch_id,
                    session.get("data_type", "PROBABILITAS_DASARIAN"),
                    fname[:255],
                    session.get("file_sha256"),
                    json.dumps(selected_periods_list),
                    len(prob_entries_to_commit) + len(det_entries_to_commit),
                    new_total + det_new_total,
                    updated_total + det_upd_total,
                    identical_total + det_id_total,
                    rejected_count,
                    ECMWF_PARSER_VERSION,
                    operator,
                    json.dumps(audit_items, default=str),
                ),
            )

        conn.commit()
        return {
            "batch_id": batch_id,
            "release_group_id": release_group_id,
            "prob_written": prob_written,
            "det_written": det_written,
            "det_reactivated": det_reactivated,
            "new_total": new_total + det_new_total,
            "updated_total": updated_total + det_upd_total,
            "identical_total": identical_total + det_id_total,
        }
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


# ==============================================================================
# PHASE 3 — DETERMINISTIC (ENSMEAN) READ API, MULTI-VINTAGE, EXPORT & VOID
# ==============================================================================

def _parse_target_period_id(period_id: str, resolution_hint: Optional[str] = None) -> Tuple[str, int, int, int, str, str]:
    """Parses period_id ('2026-11-das3' or '2026-11') into (resolution, year, month, dasarian, start_str, end_str)."""
    from backend.period_service import get_dasarian_dates

    pid = (period_id or "").strip()
    if not pid:
        raise ValueError("Parameter period_id wajib diisi (contoh: '2026-11-das1' atau '2026-11').")

    if "-das" in pid.lower():
        parts = pid.lower().split("-")
        if len(parts) < 3:
            raise ValueError(f"Format period_id dasarian tidak valid: '{period_id}'")
        t_year = int(parts[0])
        t_month = int(parts[1])
        t_das = int(parts[2].replace("das", ""))
        if t_das not in (1, 2, 3):
            raise ValueError(f"Nilai dasarian harus 1, 2, atau 3: '{period_id}'")
        res = "DASARIAN"
        t_start_dt, t_end_dt = get_dasarian_dates(t_year, t_month, f"das{t_das}")
    else:
        parts = pid.split("-")
        if len(parts) < 2:
            raise ValueError(f"Format period_id bulanan tidak valid: '{period_id}'")
        t_year = int(parts[0])
        t_month = int(parts[1])
        t_das = 0
        res = "BULANAN"
        t_start_dt = date(t_year, t_month, 1)
        next_m = t_month + 1 if t_month < 12 else 1
        next_y = t_year if t_month < 12 else t_year + 1
        t_end_dt = date(next_y, next_m, 1) - timedelta(days=1)

    if resolution_hint:
        rh = resolution_hint.strip().upper()
        if rh in ("DASARIAN", "BULANAN") and rh != res:
            raise ValueError(
                f"Ketidaksesuaian resolusi: period_id '{period_id}' adalah {res}, sedangkan parameter resolution='{rh}'."
            )

    return res, t_year, t_month, t_das, t_start_dt.strftime("%Y-%m-%d"), t_end_dt.strftime("%Y-%m-%d")


def _select_cutoff_aware_vintage(
    available_vintages: List[str],
    requested_issue_date: Optional[str] = None,
    cutoff_date: Optional[str] = None,
) -> Optional[str]:
    """
    Cutoff-aware vintage selection (strictly without system-date fallback):
    - If requested_issue_date is specified: must exist in available_vintages and (if cutoff_date set) <= cutoff_date.
    - If cutoff_date is specified: MAX(issue_date) WHERE issue_date <= cutoff_date.
    - Otherwise: newest available vintage (available_vintages[0], descending).
    """
    if not available_vintages:
        return None
    if cutoff_date:
        eligible = [v for v in available_vintages if v <= cutoff_date]
    else:
        eligible = list(available_vintages)

    if not eligible:
        return None
    if requested_issue_date:
        req = requested_issue_date.strip()
        if req in eligible:
            return req
        return None
    return eligible[0]


def get_deterministic_periods_list() -> Dict[str, Any]:
    """Returns distinct available target periods for ENSMEAN (DASARIAN & BULANAN) excluding voided records."""
    dasarian_list: List[Dict[str, Any]] = []
    bulanan_list: List[Dict[str, Any]] = []

    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT forecast_resolution, target_year, target_month, target_dasarian,
                       COUNT(DISTINCT issue_date) AS vintage_count,
                       MAX(issue_date) AS latest_issue_date,
                       COUNT(DISTINCT station_id) AS stations_count
                FROM cews_forecast_deterministic_snapshot
                WHERE is_voided = 0
                GROUP BY forecast_resolution, target_year, target_month, target_dasarian
                ORDER BY target_year DESC, target_month DESC, target_dasarian DESC
            """)
            for r in cur.fetchall():
                res = str(r["forecast_resolution"]).upper()
                y, m, d = int(r["target_year"]), int(r["target_month"]), int(r["target_dasarian"])
                latest_iss = r["latest_issue_date"].strftime("%Y-%m-%d") if hasattr(r["latest_issue_date"], "strftime") else str(r["latest_issue_date"])
                if res == "DASARIAN":
                    roman = "I" if d == 1 else ("II" if d == 2 else "III")
                    dasarian_list.append({
                        "period_id": f"{y}-{m:02d}-das{d}",
                        "label": f"{INDONESIAN_MONTHS[m - 1]} {roman} {y}",
                        "target_year": y,
                        "target_month": m,
                        "target_dasarian": d,
                        "vintage_count": int(r["vintage_count"]),
                        "latest_issue_date": latest_iss,
                        "stations_count": int(r["stations_count"]),
                    })
                else:
                    bulanan_list.append({
                        "period_id": f"{y}-{m:02d}",
                        "label": f"{INDONESIAN_MONTHS[m - 1]} {y}",
                        "target_year": y,
                        "target_month": m,
                        "target_dasarian": 0,
                        "vintage_count": int(r["vintage_count"]),
                        "latest_issue_date": latest_iss,
                        "stations_count": int(r["stations_count"]),
                    })

    return {
        "dasarian": dasarian_list,
        "bulanan": bulanan_list,
        "total_dasarian_periods": len(dasarian_list),
        "total_bulanan_periods": len(bulanan_list),
    }


def get_deterministic_forecast_data(
    period_id: str,
    resolution: Optional[str] = None,
    issue_date: Optional[str] = None,
    cutoff_date: Optional[str] = None,
    station_id: Optional[str] = None,
    kabupaten: Optional[str] = None,
    page: int = 1,
    page_size: int = 60,
) -> Dict[str, Any]:
    """
    Returns cutoff-aware ECMWF ENSMEAN (deterministic rainfall forecast, mm) across
    canonical 57 master stations (52 manual + 5 ARG marked is_arg=True, value_mm=None).
    Strictly excludes voided records (`is_voided = 0`).
    """
    from backend.data_service import get_station_metadata_df
    from backend.ingestion_service import ARG_STATION_IDS

    res, t_year, t_month, t_das, t_start, t_end = _parse_target_period_id(period_id, resolution_hint=resolution)

    available_vintages: List[str] = []
    selected_issue: Optional[str] = None
    station_det_map: Dict[str, Dict[str, Any]] = {}

    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT DISTINCT issue_date
                FROM cews_forecast_deterministic_snapshot
                WHERE forecast_resolution = %s
                  AND target_year = %s AND target_month = %s AND target_dasarian = %s
                  AND is_voided = 0
                ORDER BY issue_date DESC
                """,
                (res, t_year, t_month, t_das),
            )
            available_vintages = [
                r["issue_date"].strftime("%Y-%m-%d") if hasattr(r["issue_date"], "strftime") else str(r["issue_date"])
                for r in cur.fetchall()
            ]
            selected_issue = _select_cutoff_aware_vintage(
                available_vintages,
                requested_issue_date=issue_date,
                cutoff_date=cutoff_date,
            )

            if selected_issue:
                cur.execute(
                    """
                    SELECT station_id, value_mm, unit, adjustment_status,
                           source_column, source_file, source_sheet,
                           release_group_id, ingestion_batch_id, reactivation_count
                    FROM cews_forecast_deterministic_snapshot
                    WHERE forecast_resolution = %s
                      AND target_year = %s AND target_month = %s AND target_dasarian = %s
                      AND issue_date = %s
                      AND is_voided = 0
                    """,
                    (res, t_year, t_month, t_das, selected_issue),
                )
                for r in cur.fetchall():
                    sid = str(r["station_id"]).strip().upper()
                    station_det_map[sid] = {
                        "value_mm": float(r["value_mm"]) if r["value_mm"] is not None else None,
                        "unit": r.get("unit") or "mm",
                        "adjustment_status": r.get("adjustment_status") or "REGULAR",
                        "source_column": r.get("source_column"),
                        "source_file": r.get("source_file"),
                        "source_sheet": r.get("source_sheet") or "EnsMean",
                        "release_group_id": r.get("release_group_id"),
                        "ingestion_batch_id": r.get("ingestion_batch_id"),
                        "reactivation_count": int(r.get("reactivation_count") or 0),
                    }

    meta_df = get_station_metadata_df()
    all_rows: List[Dict[str, Any]] = []
    manual_total = 0
    manual_available = 0
    adjusted_count = 0
    regular_count = 0

    stn_filter = station_id.strip().upper() if station_id else None
    kab_filter = kabupaten.strip().lower() if kabupaten else None

    for _, mr in meta_df.iterrows():
        sid = str(mr["station_id"]).strip().upper()
        sname = str(mr["station_name"]).strip()
        kab = str(mr["regency"]).strip() if mr.get("regency") is not None else ""
        is_arg = sid.endswith("B") or "ARG" in sname.upper() or sid in ARG_STATION_IDS

        if not is_arg:
            manual_total += 1
            if sid in station_det_map and station_det_map[sid]["value_mm"] is not None:
                manual_available += 1
                if station_det_map[sid]["adjustment_status"] == "ADJUSTED":
                    adjusted_count += 1
                else:
                    regular_count += 1

        if stn_filter and sid != stn_filter:
            continue
        if kab_filter and kab_filter not in kab.lower():
            continue

        det = station_det_map.get(sid) if not is_arg else None
        all_rows.append({
            "station_id": sid,
            "station_name": sname,
            "kabupaten": kab,
            "is_arg": is_arg,
            "forecast_resolution": res,
            "target_period": period_id,
            "issue_date": selected_issue if det else None,
            "forecast_variable": "ENSMEAN",
            "value_mm": det["value_mm"] if det else None,
            "unit": det["unit"] if det else "mm",
            "adjustment_status": det["adjustment_status"] if det else None,
            "source_column": det["source_column"] if det else None,
            "source_file": det["source_file"] if det else None,
            "release_group_id": det["release_group_id"] if det else None,
            "reactivation_count": det["reactivation_count"] if det else 0,
        })

    all_rows.sort(key=lambda r: (r["kabupaten"], r["station_name"]))
    total_records = len(all_rows)
    page_size = max(5, min(page_size, 100))
    total_pages = max(1, (total_records + page_size - 1) // page_size) if total_records > 0 else 1
    page = max(1, min(page, total_pages))
    page_rows = all_rows[(page - 1) * page_size : page * page_size]

    completeness_pct = round((manual_available / manual_total) * 100.0, 2) if manual_total > 0 else 0.0
    eligible_vintages = [v for v in available_vintages if not cutoff_date or v <= cutoff_date]

    return {
        "meta": {
            "period_id": period_id,
            "resolution": res,
            "target_start": t_start,
            "target_end": t_end,
            "unit": "mm",
            "forecast_variable": "ENSMEAN",
            "active_vintage_issue": selected_issue,
            "requested_issue_date": issue_date,
            "cutoff_date": cutoff_date,
            "available_vintages": available_vintages,
            "eligible_vintages": eligible_vintages,
            "total_records": total_records,
            "page": page,
            "page_size": page_size,
            "total_pages": total_pages,
            "completeness": {
                "manual_stations_total": manual_total,
                "manual_stations_available": manual_available,
                "manual_stations_missing": max(0, manual_total - manual_available),
                "completeness_pct": completeness_pct,
                "adjusted_count": adjusted_count,
                "regular_count": regular_count,
            },
        },
        "data": page_rows,
    }


def get_deterministic_vintages(
    resolution: Optional[str] = None,
    period_id: Optional[str] = None,
    cutoff_date: Optional[str] = None,
    include_voided: bool = False,
) -> Dict[str, Any]:
    """Lists available ENSMEAN vintages with resolution, target period, cutoff, and void filtering."""
    clauses = []
    params: List[Any] = []

    if not include_voided:
        clauses.append("is_voided = 0")
    if resolution:
        clauses.append("forecast_resolution = %s")
        params.append(resolution.strip().upper())
    if period_id:
        res_p, ty, tm, td, _, _ = _parse_target_period_id(period_id, resolution_hint=resolution)
        clauses.append("forecast_resolution = %s AND target_year = %s AND target_month = %s AND target_dasarian = %s")
        params.extend([res_p, ty, tm, td])
    if cutoff_date:
        clauses.append("issue_date <= %s")
        params.append(cutoff_date.strip())

    where_sql = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                f"""
                SELECT issue_date, forecast_resolution, release_group_id,
                       COUNT(*) AS total_rows,
                       COUNT(DISTINCT station_id) AS stations_count,
                       COUNT(DISTINCT CONCAT(target_year, '-', LPAD(target_month, 2, '0'), '-', target_dasarian)) AS target_periods_count,
                       SUM(CASE WHEN adjustment_status = 'ADJUSTED' THEN 1 ELSE 0 END) AS adjusted_rows,
                       SUM(CASE WHEN is_voided = 1 THEN 1 ELSE 0 END) AS voided_rows,
                       MAX(source_file) AS sample_source_file
                FROM cews_forecast_deterministic_snapshot
                {where_sql}
                GROUP BY issue_date, forecast_resolution, release_group_id
                ORDER BY issue_date DESC, forecast_resolution ASC
                """,
                tuple(params),
            )
            vintages = []
            for r in cur.fetchall():
                vintages.append({
                    "issue_date": r["issue_date"].strftime("%Y-%m-%d") if hasattr(r["issue_date"], "strftime") else str(r["issue_date"]),
                    "forecast_resolution": r["forecast_resolution"],
                    "release_group_id": r["release_group_id"],
                    "total_rows": int(r["total_rows"]),
                    "stations_count": int(r["stations_count"]),
                    "target_periods_count": int(r["target_periods_count"]),
                    "adjusted_rows": int(r["adjusted_rows"] or 0),
                    "voided_rows": int(r["voided_rows"] or 0),
                    "sample_source_file": r["sample_source_file"],
                })

    return {
        "total": len(vintages),
        "cutoff_date": cutoff_date,
        "include_voided": include_voided,
        "vintages": vintages,
    }


def get_deterministic_vintage_detail(
    issue_date: str,
    resolution: Optional[str] = None,
    period_id: Optional[str] = None,
    include_voided: bool = False,
) -> Dict[str, Any]:
    """Returns detailed target-period breakdown for a single ENSMEAN vintage issue_date."""
    date.fromisoformat(issue_date.strip())  # validate ISO format
    clauses = ["issue_date = %s"]
    params: List[Any] = [issue_date.strip()]

    if not include_voided:
        clauses.append("is_voided = 0")
    if resolution:
        clauses.append("forecast_resolution = %s")
        params.append(resolution.strip().upper())
    if period_id:
        res_p, ty, tm, td, _, _ = _parse_target_period_id(period_id, resolution_hint=resolution)
        clauses.append("forecast_resolution = %s AND target_year = %s AND target_month = %s AND target_dasarian = %s")
        params.extend([res_p, ty, tm, td])

    where_sql = " AND ".join(clauses)
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                f"""
                SELECT forecast_resolution, target_year, target_month, target_dasarian,
                       adjustment_status, source_column, source_file, release_group_id,
                       ingestion_batch_id,
                       COUNT(*) AS stations_count,
                       MIN(value_mm) AS min_mm,
                       MAX(value_mm) AS max_mm,
                       AVG(value_mm) AS avg_mm,
                       SUM(CASE WHEN is_voided = 1 THEN 1 ELSE 0 END) AS voided_count
                FROM cews_forecast_deterministic_snapshot
                WHERE {where_sql}
                GROUP BY forecast_resolution, target_year, target_month, target_dasarian,
                         adjustment_status, source_column, source_file, release_group_id, ingestion_batch_id
                ORDER BY forecast_resolution, target_year, target_month, target_dasarian
                """,
                tuple(params),
            )
            targets = []
            for r in cur.fetchall():
                res = str(r["forecast_resolution"]).upper()
                y, m, d = int(r["target_year"]), int(r["target_month"]), int(r["target_dasarian"])
                pid = f"{y}-{m:02d}-das{d}" if res == "DASARIAN" else f"{y}-{m:02d}"
                targets.append({
                    "period_id": pid,
                    "forecast_resolution": res,
                    "adjustment_status": r["adjustment_status"],
                    "source_column": r["source_column"],
                    "source_file": r["source_file"],
                    "release_group_id": r["release_group_id"],
                    "ingestion_batch_id": r["ingestion_batch_id"],
                    "stations_count": int(r["stations_count"]),
                    "min_mm": round(float(r["min_mm"]), 2) if r["min_mm"] is not None else None,
                    "max_mm": round(float(r["max_mm"]), 2) if r["max_mm"] is not None else None,
                    "avg_mm": round(float(r["avg_mm"]), 2) if r["avg_mm"] is not None else None,
                    "voided_count": int(r["voided_count"] or 0),
                })

    return {
        "issue_date": issue_date.strip(),
        "total_targets": len(targets),
        "targets": targets,
    }


def get_deterministic_completeness(
    period_id: str,
    resolution: Optional[str] = None,
    issue_date: Optional[str] = None,
    cutoff_date: Optional[str] = None,
) -> Dict[str, Any]:
    """Returns overall and per-regency completeness metrics for ENSMEAN on a target period."""
    payload = get_deterministic_forecast_data(
        period_id=period_id,
        resolution=resolution,
        issue_date=issue_date,
        cutoff_date=cutoff_date,
        page=1,
        page_size=100,
    )
    by_kab: Dict[str, Dict[str, int]] = {}
    missing_stations: List[Dict[str, str]] = []
    for row in payload["data"]:
        if row["is_arg"]:
            continue
        kab = row["kabupaten"] or "Lainnya"
        by_kab.setdefault(kab, {"total": 0, "available": 0, "missing": 0, "adjusted": 0, "regular": 0})
        by_kab[kab]["total"] += 1
        if row["value_mm"] is not None:
            by_kab[kab]["available"] += 1
            if row["adjustment_status"] == "ADJUSTED":
                by_kab[kab]["adjusted"] += 1
            else:
                by_kab[kab]["regular"] += 1
        else:
            by_kab[kab]["missing"] += 1
            missing_stations.append({
                "station_id": row["station_id"],
                "station_name": row["station_name"],
                "kabupaten": kab,
            })

    by_regency = [
        {
            "kabupaten": k,
            **v,
            "completeness_pct": round((v["available"] / v["total"]) * 100.0, 2) if v["total"] > 0 else 0.0,
        }
        for k, v in sorted(by_kab.items())
    ]

    return {
        "period_id": payload["meta"]["period_id"],
        "resolution": payload["meta"]["resolution"],
        "active_vintage_issue": payload["meta"]["active_vintage_issue"],
        "cutoff_date": cutoff_date,
        "summary": payload["meta"]["completeness"],
        "by_kabupaten": by_regency,
        "missing_stations": missing_stations,
    }


def get_deterministic_history(
    limit: int = 50,
    issue_date: Optional[str] = None,
    resolution: Optional[str] = None,
) -> Dict[str, Any]:
    """Returns ENSMEAN ingestion, void, and reactivation history from cews_ingestion_history."""
    safe_limit = max(1, min(int(limit), 200))
    clauses = [
        "(data_type IN ('PROBABILITAS_DASARIAN', 'PROBABILITAS_BULANAN', 'ENSMEAN_VOID', 'ENSMEAN_REACTIVATE'))"
    ]
    params: List[Any] = []
    if resolution:
        res_u = resolution.strip().upper()
        if res_u == "DASARIAN":
            clauses.append("(data_type IN ('PROBABILITAS_DASARIAN', 'ENSMEAN_VOID', 'ENSMEAN_REACTIVATE'))")
        elif res_u == "BULANAN":
            clauses.append("(data_type IN ('PROBABILITAS_BULANAN', 'ENSMEAN_VOID', 'ENSMEAN_REACTIVATE'))")

    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                f"""
                SELECT batch_id, data_type, file_name, target_period,
                       total_records, new_records, updated_records, identical_records, rejected_records,
                       status, operator, cancellation_reason, created_at
                FROM cews_ingestion_history
                WHERE {' AND '.join(clauses)}
                ORDER BY created_at DESC
                LIMIT %s
                """,
                tuple(params + [safe_limit]),
            )
            items = []
            for r in cur.fetchall():
                if issue_date and issue_date.strip() not in str(r.get("file_name") or "") and issue_date.strip() not in str(r.get("target_period") or ""):
                    # Keep ENSMEAN_VOID/REACTIVATE rows matching issue_date via file_name/batch_id
                    if r["data_type"] in ("PROBABILITAS_DASARIAN", "PROBABILITAS_BULANAN"):
                        # Convert YYYY-MM-DD to YYYY.MM.DD check for filename
                        dot_d = issue_date.strip().replace("-", ".")
                        if dot_d not in str(r.get("file_name") or ""):
                            continue
                items.append({
                    "batch_id": r["batch_id"],
                    "data_type": r["data_type"],
                    "file_name": r["file_name"],
                    "target_period": r["target_period"],
                    "total_records": int(r["total_records"] or 0),
                    "new_records": int(r["new_records"] or 0),
                    "updated_records": int(r["updated_records"] or 0),
                    "identical_records": int(r["identical_records"] or 0),
                    "rejected_records": int(r["rejected_records"] or 0),
                    "status": r["status"],
                    "operator": r["operator"],
                    "reason": r.get("cancellation_reason"),
                    "created_at": r["created_at"].isoformat() if hasattr(r.get("created_at"), "isoformat") else str(r.get("created_at")),
                })

    return {"total": len(items), "history": items}


def export_deterministic_forecast_data(
    period_id: str,
    file_format: str = "csv",
    resolution: Optional[str] = None,
    issue_date: Optional[str] = None,
    cutoff_date: Optional[str] = None,
    station_id: Optional[str] = None,
    station_ids: Optional[List[str]] = None,
    kabupaten: Optional[str] = None,
) -> Tuple[bytes, str, str]:
    """Exports cutoff-aware ENSMEAN deterministic forecast data as CSV or XLSX."""
    payload = get_deterministic_forecast_data(
        period_id=period_id,
        resolution=resolution,
        issue_date=issue_date,
        cutoff_date=cutoff_date,
        station_id=station_id,
        kabupaten=kabupaten,
        page=1,
        page_size=100,
    )
    rows = payload["data"]
    if station_ids:
        sid_set = {s.strip().upper() for s in station_ids if s and s.strip()}
        if sid_set:
            rows = [r for r in rows if str(r.get("station_id", "")).strip().upper() in sid_set]
    meta = payload["meta"]
    res_slug = meta["resolution"].lower()
    iss_slug = meta["active_vintage_issue"] or "none"
    headers = [
        "station_id", "station_name", "kabupaten", "is_arg",
        "forecast_resolution", "target_period", "issue_date",
        "forecast_variable", "value_mm", "unit",
        "adjustment_status", "source_column", "source_file",
    ]

    fmt = (file_format or "csv").lower().strip()
    if fmt == "xlsx":
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = f"ENSMEAN_{meta['resolution']}"
        ws.append(headers)
        header_fill = PatternFill(start_color="1E3A8A", end_color="1E3A8A", fill_type="solid")
        header_font = Font(color="FFFFFF", bold=True)
        for col_idx in range(1, len(headers) + 1):
            cell = ws.cell(row=1, column=col_idx)
            cell.fill = header_fill
            cell.font = header_font
        for r in rows:
            ws.append([r.get(h) for h in headers])
        buf = io.BytesIO()
        wb.save(buf)
        filename = f"DSS_PIK_ENSMEAN_{res_slug}_{period_id}_ver_{iss_slug}.xlsx"
        return (
            buf.getvalue(),
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            filename,
        )

    out = io.StringIO()
    writer = csv.writer(out)
    writer.writerow(headers)
    for r in rows:
        writer.writerow(["" if r.get(h) is None else r.get(h) for h in headers])
    filename = f"DSS_PIK_ENSMEAN_{res_slug}_{period_id}_ver_{iss_slug}.csv"
    return out.getvalue().encode("utf-8-sig"), "text/csv; charset=utf-8", filename


def void_deterministic_forecast(
    issue_date: str,
    reason: str,
    forecast_resolution: str,
    target_period: Optional[str] = None,
    station_id: Optional[str] = None,
    batch_id: Optional[str] = None,
    operator: str = "OPERATOR_BMKG",
) -> Dict[str, Any]:
    """
    Soft-voids matching ENSMEAN records in `cews_forecast_deterministic_snapshot`
    (`is_voided = 1`) with full audit logging in `cews_ingestion_history`.
    Completely isolated: NEVER modifies `cews_forecast_snapshot`.
    """
    if not reason or not reason.strip():
        raise ValueError("Alasan pembatalan ENSMEAN wajib diisi.")
    if not issue_date or not issue_date.strip():
        raise ValueError("issue_date wajib diisi untuk pembatalan ENSMEAN.")
    date.fromisoformat(issue_date.strip())

    res = (forecast_resolution or "").strip().upper()
    if res not in ("DASARIAN", "BULANAN"):
        raise ValueError("forecast_resolution wajib bernilai 'DASARIAN' atau 'BULANAN'.")

    clauses = ["issue_date = %s", "forecast_resolution = %s", "is_voided = 0"]
    params: List[Any] = [issue_date.strip(), res]

    if target_period:
        _, ty, tm, td, _, _ = _parse_target_period_id(target_period, resolution_hint=res)
        clauses.append("target_year = %s AND target_month = %s AND target_dasarian = %s")
        params.extend([ty, tm, td])
    if station_id:
        clauses.append("station_id = %s")
        params.append(station_id.strip().upper())
    if batch_id:
        clauses.append("ingestion_batch_id = %s")
        params.append(batch_id.strip())

    where_sql = " AND ".join(clauses)
    conn = get_raw_connection()
    conn.autocommit(False)
    conn.begin()
    try:
        with conn.cursor() as cur:
            cur.execute(
                f"""
                UPDATE cews_forecast_deterministic_snapshot
                SET is_voided = 1,
                    void_reason = %s,
                    voided_by = %s,
                    voided_at = CURRENT_TIMESTAMP
                WHERE {where_sql}
                """,
                tuple([reason.strip(), operator] + params),
            )
            voided_count = cur.rowcount

            b_id = f"VOID_ENSMEAN_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:6].upper()}"
            audit_payload = [{
                "action": "ENSMEAN_SOFT_VOID",
                "issue_date": issue_date.strip(),
                "forecast_resolution": res,
                "target_period": target_period,
                "station_id": station_id.strip().upper() if station_id else None,
                "source_batch_id": batch_id,
                "records_voided": voided_count,
                "reason": reason.strip(),
                "operator": operator,
            }]
            cur.execute(
                """
                INSERT INTO cews_ingestion_history
                (batch_id, data_type, file_name, target_period, total_records, new_records,
                 updated_records, identical_records, rejected_records, parser_version, status,
                 operator, cancellation_reason, batch_items_json)
                VALUES (%s, 'ENSMEAN_VOID', %s, %s, %s, 0, %s, 0, 0, %s, 'VOIDED', %s, %s, %s);
                """,
                (
                    b_id,
                    f"ensmean_{res.lower()}_ver_{issue_date.strip()}",
                    json.dumps([target_period] if target_period else [f"ALL_{res}"]),
                    voided_count,
                    voided_count,
                    ECMWF_PARSER_VERSION,
                    operator,
                    reason.strip(),
                    json.dumps(audit_payload),
                ),
            )
        conn.commit()
        return {
            "status": "SUCCESS",
            "audit_batch_id": b_id,
            "records_voided": voided_count,
            "issue_date": issue_date.strip(),
            "forecast_resolution": res,
            "target_period": target_period,
            "operator": operator,
        }
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def reactivate_deterministic_forecast(
    issue_date: str,
    reason: str,
    forecast_resolution: str,
    target_period: Optional[str] = None,
    station_id: Optional[str] = None,
    batch_id: Optional[str] = None,
    operator: str = "OPERATOR_BMKG",
) -> Dict[str, Any]:
    """
    Safely reactivates previously soft-voided ENSMEAN records (`is_voided = 0`,
    `reactivation_count += 1`) while archiving prior void metadata to `cews_ingestion_history`.
    Zero duplicate key risk; completely isolated from `cews_forecast_snapshot`.
    """
    if not reason or not reason.strip():
        raise ValueError("Alasan reaktivasi ENSMEAN wajib diisi.")
    if not issue_date or not issue_date.strip():
        raise ValueError("issue_date wajib diisi untuk reaktivasi ENSMEAN.")
    date.fromisoformat(issue_date.strip())

    res = (forecast_resolution or "").strip().upper()
    if res not in ("DASARIAN", "BULANAN"):
        raise ValueError("forecast_resolution wajib bernilai 'DASARIAN' atau 'BULANAN'.")

    clauses = ["issue_date = %s", "forecast_resolution = %s", "is_voided = 1"]
    params: List[Any] = [issue_date.strip(), res]

    if target_period:
        _, ty, tm, td, _, _ = _parse_target_period_id(target_period, resolution_hint=res)
        clauses.append("target_year = %s AND target_month = %s AND target_dasarian = %s")
        params.extend([ty, tm, td])
    if station_id:
        clauses.append("station_id = %s")
        params.append(station_id.strip().upper())
    if batch_id:
        clauses.append("ingestion_batch_id = %s")
        params.append(batch_id.strip())

    where_sql = " AND ".join(clauses)
    conn = get_raw_connection()
    conn.autocommit(False)
    conn.begin()
    try:
        with conn.cursor() as cur:
            # Archive previous void metadata before reactivation
            cur.execute(
                f"""
                SELECT station_id, target_year, target_month, target_dasarian,
                       value_mm, void_reason, voided_by, voided_at
                FROM cews_forecast_deterministic_snapshot
                WHERE {where_sql}
                """,
                tuple(params),
            )
            prior_voided = [
                {
                    "action": "ENSMEAN_REACTIVATE",
                    "station_id": r["station_id"],
                    "target_year": r["target_year"],
                    "target_month": r["target_month"],
                    "target_dasarian": r["target_dasarian"],
                    "value_mm": float(r["value_mm"]) if r["value_mm"] is not None else None,
                    "previous_void_reason": r["void_reason"],
                    "previous_voided_by": r["voided_by"],
                    "previous_voided_at": r["voided_at"].isoformat() if hasattr(r.get("voided_at"), "isoformat") else r.get("voided_at"),
                    "reactivation_reason": reason.strip(),
                    "operator": operator,
                }
                for r in cur.fetchall()
            ]

            cur.execute(
                f"""
                UPDATE cews_forecast_deterministic_snapshot
                SET is_voided = 0,
                    void_reason = NULL,
                    voided_by = NULL,
                    voided_at = NULL,
                    reactivation_count = reactivation_count + 1,
                    reactivated_at = CURRENT_TIMESTAMP
                WHERE {where_sql}
                """,
                tuple(params),
            )
            reactivated_count = cur.rowcount

            b_id = f"REACT_ENSMEAN_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:6].upper()}"
            cur.execute(
                """
                INSERT INTO cews_ingestion_history
                (batch_id, data_type, file_name, target_period, total_records, new_records,
                 updated_records, identical_records, rejected_records, parser_version, status,
                 operator, cancellation_reason, batch_items_json)
                VALUES (%s, 'ENSMEAN_REACTIVATE', %s, %s, %s, 0, %s, 0, 0, %s, 'COMMITTED', %s, %s, %s);
                """,
                (
                    b_id,
                    f"ensmean_{res.lower()}_ver_{issue_date.strip()}",
                    json.dumps([target_period] if target_period else [f"ALL_{res}"]),
                    reactivated_count,
                    reactivated_count,
                    ECMWF_PARSER_VERSION,
                    operator,
                    reason.strip(),
                    json.dumps(prior_voided, default=str),
                ),
            )
        conn.commit()
        return {
            "status": "SUCCESS",
            "audit_batch_id": b_id,
            "records_reactivated": reactivated_count,
            "issue_date": issue_date.strip(),
            "forecast_resolution": res,
            "target_period": target_period,
            "operator": operator,
        }
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

