import pytest
from backend.spi_calculation_service import execute_spi_generation

def test_serial_vs_parallel_numerical_equality():
    sids = ["21010401A", "21010402A"]
    res_s = execute_spi_generation("DASARIAN", 30, selected_stations=sids, n_workers=1)
    res_p = execute_spi_generation("DASARIAN", 30, selected_stations=sids, n_workers=2)
    
    from backend.spi_calculation_service import _GENERATOR_SESSIONS
    df_s = _GENERATOR_SESSIONS[res_s["session_token"]]["df_wide"]
    df_p = _GENERATOR_SESSIONS[res_p["session_token"]]["df_wide"]
    
    assert list(df_s.columns) == list(df_p.columns)
    assert len(df_s) == len(df_p)
    diff = (df_s - df_p).abs().max().max()
    assert diff == 0.0 or diff < 1e-6

