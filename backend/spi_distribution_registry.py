"""
backend/spi_distribution_registry.py
Registry service for loading, caching, and querying the official
Best Distribution Consensus (BestDist_Consensus) per station and scale.
Decision Support System Peringatan Iklim Kepulauan Riau (DSS-PIK)
"""

import sys
from pathlib import Path
from typing import Dict, Any, Optional, Tuple
import pandas as pd

# Add SPEI source path to sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
SPEI_SRC = PROJECT_ROOT / "SPEI" / "src"
if str(SPEI_SRC) not in sys.path:
    sys.path.insert(0, str(SPEI_SRC))

import scipy.stats as scs
try:
    import spei as si
except ImportError:
    si = None

# Distribution string to SciPy / SPEI continuous distribution object mapping
DIST_OBJECT_MAP = {
    "gam": scs.gamma,
    "wei": getattr(si, "weibull_min", scs.weibull_min) if si else scs.weibull_min,
    "gum": getattr(si, "gumbel_r", scs.gumbel_r) if si else scs.gumbel_r,
    "llg": getattr(si, "fisk", scs.fisk) if si else scs.fisk,
    "lgn": getattr(si, "lognorm", scs.lognorm) if si else scs.lognorm,
}

DIST_PRETTY_NAME = {
    "gam": "Gamma",
    "wei": "Weibull (weibull_min)",
    "gum": "Gumbel (gumbel_r)",
    "llg": "Log-Logistic (fisk)",
    "lgn": "Log-Normal (lognorm)",
}

# Cached distribution registry tables
_DIST_CACHE: Dict[str, pd.DataFrame] = {}


def get_distribution_csv_path(resolution: str) -> Path:
    res = resolution.strip().lower()
    ref_dir = PROJECT_ROOT / "data" / "reference" / "spi_distributions"
    if res in ("daily", "harian"):
        return ref_dir / "best_distribution_per_station_scale_daily.csv"
    elif res in ("dekad", "dasarian"):
        return ref_dir / "best_distribution_per_station_scale_dasarian.csv"
    elif res in ("monthly", "bulanan"):
        return ref_dir / "best_distribution_per_station_scale_monthly.csv"
    else:
        raise ValueError(f"Unknown resolution '{resolution}'. Must be 'daily', 'dasarian', or 'monthly'.")


def load_distribution_dataframe(resolution: str) -> pd.DataFrame:
    """Loads and caches the distribution CSV for a given resolution."""
    res_key = resolution.strip().lower()
    if res_key not in _DIST_CACHE:
        csv_path = get_distribution_csv_path(res_key)
        if not csv_path.exists():
            raise FileNotFoundError(f"Distribution CSV not found at {csv_path}")
        df = pd.read_csv(csv_path)
        df["Pos"] = df["Pos"].astype(str).str.strip().str.upper()
        df["Skala"] = df["Skala"].astype(int)
        df["BestDist_Consensus"] = df["BestDist_Consensus"].astype(str).str.strip().str.lower()
        _DIST_CACHE[res_key] = df
    return _DIST_CACHE[res_key]


def get_station_scale_distribution(
    station_id: str,
    resolution: str,
    timescale: int
) -> Optional[Dict[str, Any]]:
    """
    Looks up the BestDist_Consensus distribution for a given station and scale.
    Returns dict with dist_key, dist_name, dist_obj, zom or None if not found/ARG.
    """
    sid = str(station_id).strip().upper()
    df = load_distribution_dataframe(resolution)
    
    match = df[(df["Pos"] == sid) & (df["Skala"] == int(timescale))]
    if match.empty:
        return None
    
    row = match.iloc[0]
    dist_code = str(row["BestDist_Consensus"]).strip().lower()
    dist_obj = DIST_OBJECT_MAP.get(dist_code)
    
    return {
        "station_id": sid,
        "resolution": resolution,
        "timescale": int(timescale),
        "dist_code": dist_code,
        "dist_name": DIST_PRETTY_NAME.get(dist_code, dist_code.upper()),
        "dist_obj": dist_obj,
        "zom": str(row.get("ZOM", "")),
        "valid": dist_obj is not None
    }


def get_available_distributions_summary(resolution: str, timescale: int) -> Dict[str, Any]:
    """Returns summary of stations with valid distributions for the specified resolution and scale."""
    df = load_distribution_dataframe(resolution)
    scale_df = df[df["Skala"] == int(timescale)]
    
    station_map = {}
    for _, row in scale_df.iterrows():
        sid = row["Pos"]
        dist_code = row["BestDist_Consensus"]
        station_map[sid] = {
            "dist_code": dist_code,
            "dist_name": DIST_PRETTY_NAME.get(dist_code, dist_code.upper()),
            "zom": row.get("ZOM", "")
        }
        
    return {
        "resolution": resolution,
        "timescale": int(timescale),
        "total_stations_in_registry": len(station_map),
        "station_map": station_map
    }

