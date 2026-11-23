"""
backend/spi_calculation_worker.py
Pure calculation worker for executing SPEI per-station calculations.
Designed to be spawned safely in Joblib parallel processes.
Decision Support System Peringatan Iklim Kepulauan Riau (DSS-PIK)
"""

import sys
from pathlib import Path
from typing import Dict, Any, Optional, Tuple, List
import warnings

# Add SPEI source path to sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
SPEI_SRC = PROJECT_ROOT / "SPEI" / "src"
if str(SPEI_SRC) not in sys.path:
    sys.path.insert(0, str(SPEI_SRC))

import numpy as np
import pandas as pd
import scipy.stats as scs

warnings.filterwarnings("ignore", category=RuntimeWarning)
warnings.filterwarnings("ignore", category=UserWarning)

try:
    import spei as si
except ImportError:
    si = None


# Supported resolutions definition
RESOLUTION_CONFIG = {
    "HARIAN": {
        "fit_freq": "D",
        "supported_timescales": [30, 90],
        "dist_file_key": "daily",
        "output_parquet": {
            30: PROJECT_ROOT / "data" / "raw" / "spi" / "harian" / "SPI_all_30d.parquet",
            90: PROJECT_ROOT / "data" / "raw" / "spi" / "harian" / "SPI_all_90d.parquet",
        }
    },
    "DASARIAN": {
        "fit_freq": "dekad",
        "supported_timescales": [30, 90],
        "dist_file_key": "dasarian",
        "output_parquet": {
            30: PROJECT_ROOT / "data" / "raw" / "spi" / "dasarian" / "SPI_all_30d.parquet",
            90: PROJECT_ROOT / "data" / "raw" / "spi" / "dasarian" / "SPI_all_90d.parquet",
        }
    },
    "BULANAN": {
        "fit_freq": "monthly",
        "supported_timescales": [30, 90],
        "dist_file_key": "monthly",
        "output_parquet": {
            30: PROJECT_ROOT / "data" / "raw" / "spi" / "bulanan" / "SPI_monthly.parquet",
            90: PROJECT_ROOT / "data" / "raw" / "spi" / "bulanan" / "SPI_monthly_90d.parquet",
        }
    }
}


def calculate_station_spi_worker(
    station_id: str,
    series_dict: Dict[str, Any],  # {"dates": [...], "values": [...]}
    resolution: str,
    timescale: int,
    dist_code: str
) -> Dict[str, Any]:
    """
    Worker function executed in parallel.
    Takes station CH time series, applies SPEI si.spi(), and returns calculation results.
    """
    sid = str(station_id).strip().upper()
    try:
        if si is None:
            return {
                "station_id": sid,
                "status": "ERROR",
                "message": "Module spei is not available.",
                "calculated_series": None
            }

        # Distribution lookup
        dist_code = str(dist_code).strip().lower()
        dist_map = {
            "gam": scs.gamma,
            "wei": getattr(si, "weibull_min", scs.weibull_min),
            "gum": getattr(si, "gumbel_r", scs.gumbel_r),
            "llg": getattr(si, "fisk", scs.fisk),
            "lgn": getattr(si, "lognorm", scs.lognorm),
        }
        dist_obj = dist_map.get(dist_code)
        if dist_obj is None:
            return {
                "station_id": sid,
                "status": "SKIPPED",
                "message": f"Distribusi '{dist_code}' tidak dikenali.",
                "calculated_series": None
            }

        dates = pd.to_datetime(series_dict["dates"])
        vals = [float(v) if v is not None and not np.isnan(v) else np.nan for v in series_dict["values"]]
        
        s = pd.Series(vals, index=dates, name=sid)
        # Sort and ensure complete daily frequency without lookahead or data distortion
        s = s.sort_index()
        s = s[~s.index.duplicated(keep="last")]
        s = s.asfreq("D")

        # Check data sufficiency
        valid_count = s.notna().sum()
        if valid_count < (timescale * 2):
            return {
                "station_id": sid,
                "status": "SKIPPED",
                "message": f"Jumlah observasi CH tidak mencukupi ({valid_count} hari valid, butuh minimal {timescale * 2}).",
                "calculated_series": None
            }

        res_key = resolution.strip().upper()
        fit_freq = RESOLUTION_CONFIG[res_key]["fit_freq"]

        # Run authoritative SPEI computation
        spi_res = si.spi(
            s,
            dist=dist_obj,
            prob_zero=True,
            timescale=int(timescale),
            fit_freq=fit_freq,
            all_zero_policy="stagge",
            fitting_policy="standard",
            small_sample_policy="augmented"
        )

        # Output formatting
        # Clean extreme values beyond [-4.0, +4.0] and clean NaNs
        spi_clean = spi_res.replace([np.inf, -np.inf], np.nan)
        
        # Format index as string YYYY-MM-DD
        spi_clean.index = pd.to_datetime(spi_clean.index).strftime("%Y-%m-%d")

        return {
            "station_id": sid,
            "status": "SUCCESS",
            "message": f"Berhasil dihitung ({spi_clean.notna().sum()} record)",
            "dist_used": dist_code,
            "timescale": timescale,
            "fit_freq": fit_freq,
            "total_computed": int(spi_clean.notna().sum()),
            "series_data": {
                "dates": list(spi_clean.index),
                "values": [round(float(v), 4) if pd.notna(v) else None for v in spi_clean.values]
            }
        }

    except Exception as e:
        return {
            "station_id": sid,
            "status": "ERROR",
            "message": f"Gagal kalkulasi: {str(e)}",
            "calculated_series": None
        }

