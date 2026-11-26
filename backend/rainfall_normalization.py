"""
backend/rainfall_normalization.py
Single source of truth for converting MariaDB cews_rainfall_daily observations
into deterministic numeric rainfall values for downstream hydrometeorological
processing (SPI Daily, SPI Dasarian, SPI Bulanan, and related numeric analyses).

Operational Policy (DSS-PIK):
- TTU (Hujan Tidak Terukur / trace) remains stored as obs_status='TTU' /
  original_symbol='TTU' in MariaDB and displayed/exported as 'TTU' in the
  Rainfall Table, but is treated as 0.0 mm in all numeric processing.
- OBSERVED_ZERO ('-') -> 0.0 mm.
- OBSERVED_VALID / CORRECTED -> actual numeric rainfall_mm.
- MISSING, MISSING_INTERNAL, DAMAGED, AMBIGUOUS -> np.nan (never coerced to 0.0,
  even if legacy rows carry a numeric rainfall_mm value).
- VOID -> excluded from numeric calculations (returns np.nan if passed directly;
  also filtered via is_excluded_obs_status / SQL WHERE clause).
- Unknown or NULL obs_status -> fail-safe validation (never blindly accepted).
"""

from __future__ import annotations

import math
from typing import Any, Dict, Iterable, List, Optional

import numpy as np

# Statuses that must always map to NaN regardless of legacy numeric rainfall_mm
NON_NUMERIC_STATUSES = frozenset({
    "MISSING",
    "MISSING_INTERNAL",
    "DAMAGED",
    "AMBIGUOUS",
    "VOID",
})

# Statuses representing valid zero rainfall in numeric calculations
ZERO_NUMERIC_STATUSES = frozenset({
    "TTU",
    "OBSERVED_ZERO",
})

# Statuses whose numeric rainfall_mm column carries an observed measurement
MEASURED_NUMERIC_STATUSES = frozenset({
    "OBSERVED_VALID",
    "CORRECTED",
})

# Legacy sentinel values (e.g., 8888 = TTU, 9999 = MISSING) that are never valid mm
_LEGACY_SENTINEL_THRESHOLD = 8888.0


def is_excluded_obs_status(obs_status: Optional[str]) -> bool:
    """Returns True if the observation status must be completely excluded (VOID)."""
    return (obs_status or "").strip().upper() == "VOID"


def normalize_rainfall_for_numeric(
    rainfall_mm: Any,
    obs_status: Optional[str],
) -> float:
    """
    Deterministically converts a single cews_rainfall_daily record into a float
    (mm) or np.nan for numeric processing without mutating source DB records.
    """
    st = (obs_status or "").strip().upper()

    # 1. Explicit non-numeric / excluded statuses (including any MISSING* variant)
    if st in NON_NUMERIC_STATUSES or st.startswith("MISSING"):
        return float("nan")

    # 2. Operational zero-equivalent statuses (TTU and OBSERVED_ZERO)
    if st in ZERO_NUMERIC_STATUSES:
        return 0.0

    # 3. Measured numeric statuses
    if st in MEASURED_NUMERIC_STATUSES:
        return _parse_valid_numeric_mm(rainfall_mm)

    # 4. NULL / empty status: do NOT blindly accept; reject NULL/negative/sentinel values
    if not st:
        return float("nan")

    # 5. Any unrecognized status: fail-safe to NaN
    return float("nan")


def _parse_valid_numeric_mm(rainfall_mm: Any) -> float:
    if rainfall_mm is None:
        return float("nan")
    try:
        val = float(rainfall_mm)
    except (TypeError, ValueError):
        return float("nan")
    if math.isnan(val) or math.isinf(val):
        return float("nan")
    if val < 0.0 or val >= _LEGACY_SENTINEL_THRESHOLD:
        return float("nan")
    return val


def build_station_numeric_series(
    rows: Iterable[Dict[str, Any]],
    target_station_ids: Iterable[str],
) -> Dict[str, Dict[str, List[Any]]]:
    """
    Groups MariaDB cews_rainfall_daily rows into per-station date/value lists
    using normalize_rainfall_for_numeric(). VOID records are excluded entirely.
    """
    station_series: Dict[str, Dict[str, List[Any]]] = {
        str(sid).strip().upper(): {"dates": [], "values": []}
        for sid in target_station_ids
    }
    for r in rows:
        sid = str(r.get("station_id") or "").strip().upper()
        if sid not in station_series:
            continue
        obs_st = r.get("obs_status")
        if is_excluded_obs_status(obs_st):
            continue
        obs_date = r["observation_date"]
        d_str = obs_date.strftime("%Y-%m-%d") if hasattr(obs_date, "strftime") else str(obs_date)[:10]
        val = normalize_rainfall_for_numeric(r.get("rainfall_mm"), obs_st)
        station_series[sid]["dates"].append(d_str)
        station_series[sid]["values"].append(val if not math.isnan(val) else np.nan)
    return station_series


def evaluate_output_date_range_compliance(
    actual_start: Optional[str],
    actual_end: Optional[str],
    requested_start: Optional[str],
    requested_end: Optional[str],
    output_rows: int,
    resolution: str = "HARIAN",
) -> Dict[str, Any]:
    """
    Evaluates whether the generated SPI output covers the requested date range.
    Returns structured metadata and a clear warning message when truncated/incomplete.
    """
    req_start = (requested_start or "").strip() or None
    req_end = (requested_end or "").strip() or None
    act_start = actual_start if (actual_start and actual_start != "-") else None
    act_end = actual_end if (actual_end and actual_end != "-") else None
    res_key = (resolution or "HARIAN").strip().upper()

    warnings_list: List[str] = []
    if output_rows <= 0 or not act_start or not act_end:
        warnings_list.append(
            "Tidak ada baris output SPI yang terbentuk pada rentang tanggal yang diminta."
        )
    else:
        if req_end and act_end < req_end:
            if res_key == "HARIAN":
                warnings_list.append(
                    f"Tanggal akhir output aktual ({act_end}) lebih awal daripada tanggal akhir yang diminta ({req_end}). "
                    f"Periksa kelengkapan data curah hujan harian MariaDB pada rentang {act_end} s.d. {req_end}."
                )
            else:
                warnings_list.append(
                    f"Tanggal akhir output aktual ({act_end}) lebih awal daripada batas akhir filter ({req_end}) "
                    f"untuk resolusi {res_key}."
                )
        if req_start and act_start > req_start and res_key == "HARIAN":
            warnings_list.append(
                f"Tanggal awal output aktual ({act_start}) lebih lambat daripada tanggal awal yang diminta ({req_start})."
            )

    compliant = len(warnings_list) == 0
    return {
        "requested_start_date": req_start,
        "requested_end_date": req_end,
        "output_date_count": int(output_rows),
        "date_range_compliant": compliant,
        "date_range_status": "MATCH" if compliant else "INCOMPLETE",
        "date_range_warning": " ".join(warnings_list) if warnings_list else None,
    }
