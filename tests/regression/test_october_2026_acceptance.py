import pytest
import pandas as pd
import numpy as np
import datetime
import os, sys

from pathlib import Path

# Find project root dynamically
_SEARCH = Path(__file__).resolve()
_PROJECT_ROOT = None
while _SEARCH.parent != _SEARCH:
    if (_SEARCH / "config").exists() and (_SEARCH / "data").exists():
        _PROJECT_ROOT = _SEARCH
        break
    _SEARCH = _SEARCH.parent

if _PROJECT_ROOT and str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from config.paths import (
    PATH_RAINFALL_DAILY,
    PATH_SPI_AUTHORITATIVE,
    PATH_CURRENT_WARNING
)

BASE_DIR = str(_PROJECT_ROOT)

from pipeline.generate_cews_decision_engine import evaluate_pdkm, evaluate_pdcht, arbitrate_decision

def test_fixed_rules_pdkm():
    # 1. Strict > 70 boundary check
    res_70 = evaluate_pdkm(hth=25, pb20=70.0, spi=-0.5, spi_severity_enabled=True)
    assert res_70['pdkm_level'] == "NORMAL", "pb20 = 70.0 must NOT trigger WASPADA"
    
    res_70_1 = evaluate_pdkm(hth=25, pb20=70.01, spi=-0.5, spi_severity_enabled=True)
    assert res_70_1['pdkm_level'] == "WASPADA", "pb20 = 70.01 MUST trigger WASPADA"
    
    # 2. HTH alone cannot trigger
    res_hth_only = evaluate_pdkm(hth=65, pb20=np.nan, spi=-0.5, spi_severity_enabled=True)
    assert res_hth_only['pdkm_level'] == "NORMAL"
    assert res_hth_only['data_quality_status'] == "INCOMPLETE"
    
    # 3. pb20 alone cannot trigger
    res_pb20_only = evaluate_pdkm(hth=5, pb20=85.0, spi=-0.5, spi_severity_enabled=True)
    assert res_pb20_only['pdkm_level'] == "NORMAL"
    
    # 4. SPI independent trigger
    res_spi_awas = evaluate_pdkm(hth=5, pb20=20.0, spi=-2.05, spi_severity_enabled=True)
    assert res_spi_awas['pdkm_level'] == "AWAS"
    
    res_spi_siaga = evaluate_pdkm(hth=5, pb20=20.0, spi=-1.75, spi_severity_enabled=True)
    assert res_spi_siaga['pdkm_level'] == "SIAGA"
    
    res_spi_waspada = evaluate_pdkm(hth=5, pb20=20.0, spi=-1.25, spi_severity_enabled=True)
    assert res_spi_waspada['pdkm_level'] == "WASPADA"

def test_fixed_rules_pdcht():
    # 1. Strict > 70 boundary
    assert evaluate_pdcht(pa150=70.0)['pdcht_level'] == "NORMAL"
    assert evaluate_pdcht(pa150=70.1)['pdcht_level'] == "WASPADA"
    assert evaluate_pdcht(pa200=70.1)['pdcht_level'] == "SIAGA"
    assert evaluate_pdcht(pa300=70.1)['pdcht_level'] == "AWAS"
    assert evaluate_pdcht(pm300=70.1)['pdcht_level'] == "WASPADA"
    assert evaluate_pdcht(pm400=70.1)['pdcht_level'] == "SIAGA"
    assert evaluate_pdcht(pm500=70.1)['pdcht_level'] == "AWAS"

def test_temporal_lineage_and_constraints():
    # 1. No rainfall observation after 2026-09-30
    frd = pd.read_parquet(PATH_RAINFALL_DAILY)
    frd['date'] = pd.to_datetime(frd['date'])
    max_rain_date = frd['date'].max()
    assert max_rain_date <= pd.Timestamp('2026-09-30'), f"Rainfall observation exceeds 2026-09-30: {max_rain_date}"
    assert max_rain_date == pd.Timestamp('2026-08-25'), f"Expected latest rainfall observation 2026-08-25, got {max_rain_date}"

    # 2. SPI evidence date <= 2026-09-30
    spi_df = pd.read_parquet(PATH_SPI_AUTHORITATIVE)
    spi_df.index = pd.to_datetime(spi_df.index)
    spi_evidence = spi_df.index[spi_df.index <= '2026-09-30'].max()
    assert spi_evidence <= pd.Timestamp('2026-09-30')

    # 3. SPI current cycle uses expected Sep III evidence (2026-09-21)
    assert spi_evidence == pd.Timestamp('2026-09-21'), f"Expected 2026-09-21, got {spi_evidence}"

    # 4. Target warning dates
    target_start = pd.Timestamp('2026-10-01')
    target_end = pd.Timestamp('2026-10-10')
    assert (target_end - target_start).days == 9

    # 5. Promoted Current Warning Artifact Check
    cw = pd.read_parquet(PATH_CURRENT_WARNING)
    assert len(cw) == 57, f"Expected 57 current warning records, got {len(cw)}"
    assert cw['station_id'].nunique() == 57, "Duplicate station_ids found in current warning"
    t_start = pd.to_datetime(cw['target_period_start'])
    assert t_start.dt.year.unique().tolist() == [2026]

    # 6. Unexplained deltas = 0
    assert (cw['warning_level'].isna()).sum() == 0, "Missing warning levels"


if __name__ == "__main__":
    test_fixed_rules_pdkm()
    test_fixed_rules_pdcht()
    test_temporal_lineage_and_constraints()
    print("ALL ACCEPTANCE TESTS PASSED!")
