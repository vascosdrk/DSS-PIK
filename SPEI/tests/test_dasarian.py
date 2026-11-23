"""Automated test suite for BMKG Dasarian (10-day dekad) aggregation, rolling accumulation, and DSPI calculation."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest
from scipy.stats import gamma, weibull_min, pearson3

import spei
from spei.utils import (
    dasarian_windows,
    is_dasarian_index,
    to_dasarian,
    to_dekad,
    rolling_dasarian,
    rolling_dekad,
    infer_frequency,
)

from spei.si import SI, spi


def test_is_dasarian_index():
    """Verify detection of BMKG dasarian calendar cadence (days 1, 11, 21)."""
    # 1. Valid dasarian dates
    das_dates = pd.DatetimeIndex([
        "2020-01-01", "2020-01-11", "2020-01-21",
        "2020-02-01", "2020-02-11", "2020-02-21",
    ])
    assert is_dasarian_index(das_dates) is True

    # 2. Daily dates
    daily_dates = pd.date_range("2020-01-01", "2020-01-15", freq="D")
    assert is_dasarian_index(daily_dates) is False

    # 3. Monthly dates (only 1st of month)
    monthly_dates = pd.date_range("2020-01-01", "2020-12-01", freq="MS")
    assert is_dasarian_index(monthly_dates) is False

    # 4. Empty index
    assert is_dasarian_index(pd.DatetimeIndex([])) is False


def test_to_dasarian_calendar_definitions():
    """Verify BMKG standard calendar grouping:
    - Dasarian 1: Dates 1–10 (labeled YYYY-MM-01)
    - Dasarian 2: Dates 11–20 (labeled YYYY-MM-11)
    - Dasarian 3: Dates 21–end (labeled YYYY-MM-21)
    """
    # Test a leap year month (Feb 2020: 29 days) and a 31-day month (Jan 2020)
    dates = pd.date_range("2020-01-01", "2020-02-29", freq="D")
    s = pd.Series(1.0, index=dates)

    das = to_dasarian(s, min_valid_days=1)
    assert len(das) == 6
    assert list(das.index) == [
        pd.Timestamp("2020-01-01"),
        pd.Timestamp("2020-01-11"),
        pd.Timestamp("2020-01-21"),
        pd.Timestamp("2020-02-01"),
        pd.Timestamp("2020-02-11"),
        pd.Timestamp("2020-02-21"),
    ]

    # Jan 1-10: 10 days
    assert das.loc["2020-01-01"] == 10.0
    # Jan 11-20: 10 days
    assert das.loc["2020-01-11"] == 10.0
    # Jan 21-31: 11 days
    assert das.loc["2020-01-21"] == 11.0
    # Feb 1-10: 10 days
    assert das.loc["2020-02-01"] == 10.0
    # Feb 11-20: 10 days
    assert das.loc["2020-02-11"] == 10.0
    # Feb 21-29 (leap): 9 days
    assert das.loc["2020-02-21"] == 9.0


def test_to_dasarian_min_valid_days():
    """Verify min_valid_days parameter filters out periods with excessive missing data."""
    dates = pd.date_range("2021-01-01", "2021-01-31", freq="D")
    s = pd.Series(2.0, index=dates)
    # Set 6 days of Jan 1-10 to NaN (only 4 valid days remaining)
    s.iloc[0:6] = np.nan

    # min_valid_days=5 -> Dasarian 1 fails, should be NaN
    res_strict = to_dasarian(s, min_valid_days=5)
    assert np.isnan(res_strict.iloc[0])
    assert res_strict.iloc[1] == 20.0

    # min_valid_days=4 -> Dasarian 1 succeeds with 4 * 2.0 = 8.0
    res_lenient = to_dasarian(s, min_valid_days=4)
    assert res_lenient.iloc[0] == 8.0


def test_to_dasarian_dataframe_multi_station():
    """Verify to_dasarian works seamlessly on multi-station DataFrame matrices."""
    dates = pd.date_range("2022-01-01", "2022-12-31", freq="D")
    df = pd.DataFrame({
        "station_A": np.full(len(dates), 5.0),
        "station_B": np.full(len(dates), 10.0),
    }, index=dates)

    das_df = to_dasarian(df)
    assert isinstance(das_df, pd.DataFrame)
    assert das_df.shape == (36, 2)
    assert das_df.columns.tolist() == ["station_A", "station_B"]
    assert das_df["station_A"].iloc[0] == 50.0
    assert das_df["station_B"].iloc[0] == 100.0


def test_rolling_dasarian_mapping():
    """Verify timescale mapping from days to dasarian window lengths."""
    dates = pd.date_range("2010-01-01", "2024-12-31", freq="D")
    s = pd.Series(1.0, index=dates)
    das = to_dasarian(s)
    assert len(das) == 540

    # Check nominal day timescales match dasarian windows
    for days, window in dasarian_windows.items():
        rolled_by_days = rolling_dasarian(das, timescale=days)
        rolled_by_window = rolling_dasarian(das, timescale=window)
        pd.testing.assert_series_equal(rolled_by_days, rolled_by_window)
        # Check window lengths
        assert len(rolled_by_days.dropna()) == 540 - window + 1



def test_dekad_spi_calculation_on_real_station(prec_34010701a):
    """End-to-end verification of 36-dekad SPI calculation on Station 34010701a."""
    # 1. Aggregate daily series to dasarian
    das_precip = to_dasarian(prec_34010701a, min_valid_days=1)
    assert len(das_precip) == 540
    assert is_dasarian_index(das_precip.index) is True

    # 2. Rolling dasarian at scale 30 (3 dasarians ~ 1 month)
    rolled_30 = rolling_dasarian(das_precip, timescale=30).dropna()
    assert len(rolled_30) == 538

    # 3. Calculate Dekad SPI with Gamma distribution on pre-aggregated data
    dekad_spi_gamma = spi(rolled_30, dist=gamma, prob_zero=True)
    assert isinstance(dekad_spi_gamma, pd.Series)
    assert len(dekad_spi_gamma) == 538
    assert np.isfinite(dekad_spi_gamma).sum() >= 530
    # No residual infinities
    assert not np.isinf(dekad_spi_gamma).any()

    # 4. Universal Cara 2: Direct call on daily series with fit_freq="dekad" and timescale=30
    spi_direct_dekad = spi(prec_34010701a, dist=gamma, timescale=30, fit_freq="dekad", prob_zero=True)
    assert len(spi_direct_dekad) == len(dekad_spi_gamma)
    np.testing.assert_allclose(spi_direct_dekad.values, dekad_spi_gamma.values, rtol=1e-5)

    # 5. fit_freq="dasarian" produces identical output
    spi_direct_dasarian = spi(prec_34010701a, dist=gamma, timescale=30, fit_freq="dasarian", prob_zero=True)
    pd.testing.assert_series_equal(spi_direct_dekad, spi_direct_dasarian)


def test_aliases_consistency():
    """Verify that aliases to_dekad, daily_to_dasarian, and rolling_dekad match."""
    assert to_dekad is to_dasarian
    assert rolling_dekad is rolling_dasarian


def test_to_dasarian_missing_dekad_preserved_as_nan():
    """Verify that completely missing calendar dekads are preserved as NaN in the canonical 36-dekad index."""
    # Jan to March 2020 (total 9 dekads expected)
    dates = pd.date_range("2020-01-01", "2020-03-31", freq="D")
    s = pd.Series(5.0, index=dates)
    # Drop all days of Feb 11 to Feb 20 (Dekad 5)
    s = s.drop(pd.date_range("2020-02-11", "2020-02-20", freq="D"))

    das = to_dasarian(s, min_valid_days=1)
    # Must preserve exactly 9 dekads
    assert len(das) == 9
    assert pd.Timestamp("2020-02-11") in das.index
    assert np.isnan(das.loc["2020-02-11"])
    # Other dekads must be valid
    assert das.loc["2020-02-01"] == 50.0
    assert das.loc["2020-02-21"] == 45.0  # 9 days in Feb leap year * 5


def test_to_dasarian_leap_year_days():
    """Verify leap year handling in get_expected_dasarian_days and to_dasarian."""
    from spei.utils import get_expected_dasarian_days

    # Leap year Feb dekad 3 has 9 days (Feb 21-29)
    assert get_expected_dasarian_days(pd.Timestamp("2020-02-21")) == 9
    # Non-leap year Feb dekad 3 has 8 days (Feb 21-28)
    assert get_expected_dasarian_days(pd.Timestamp("2021-02-21")) == 8
    # 31-day months have 11 days (Jan 21-31)
    assert get_expected_dasarian_days(pd.Timestamp("2020-01-21")) == 11
    # 30-day months have 10 days (Apr 21-30)
    assert get_expected_dasarian_days(pd.Timestamp("2020-04-21")) == 10


def test_to_dasarian_coverage_fraction():
    """Verify min_valid_fraction coverage requirements across dekads of different lengths."""
    dates = pd.date_range("2021-01-21", "2021-01-31", freq="D")  # 11 days
    s = pd.Series(10.0, index=dates)
    # Leave 9 valid days out of 11 (2 NaNs) -> fraction = 9/11 = 0.818
    s.iloc[0:2] = np.nan

    # min_valid_fraction=0.85 requires ceil(11 * 0.85) = 10 days -> should fail (NaN)
    res_fail = to_dasarian(s, min_valid_fraction=0.85)
    assert np.isnan(res_fail.iloc[0])

    # min_valid_fraction=0.80 requires ceil(11 * 0.80) = 9 days -> should pass (9 * 10 = 90)
    res_pass = to_dasarian(s, min_valid_fraction=0.80)
    assert res_pass.iloc[0] == 90.0


def test_rolling_dasarian_gap_preservation():
    """Verify that rolling accumulation does not compress missing dekads."""
    dates = pd.DatetimeIndex([
        "2020-01-01", "2020-01-11", "2020-01-21",
        "2020-02-01", "2020-02-11", "2020-02-21",
        "2020-03-01", "2020-03-11", "2020-03-21",
    ])
    s = pd.Series(10.0, index=dates)
    # Introduce gap at 2020-02-11
    s.loc["2020-02-11"] = np.nan

    # 3-dekad rolling sum (approx 1 month)
    rolled = rolling_dasarian(s, timescale=3)
    # Window containing 2020-02-11 must be NaN:
    # 2020-02-11 window (01-21, 02-01, 02-11) -> NaN
    # 2020-02-21 window (02-01, 02-11, 02-21) -> NaN
    # 2020-03-01 window (02-11, 02-21, 03-01) -> NaN
    assert np.isnan(rolled.loc["2020-02-11"])
    assert np.isnan(rolled.loc["2020-02-21"])
    assert np.isnan(rolled.loc["2020-03-01"])
    # 2020-03-11 window (02-21, 03-01, 03-11) has all 3 valid values -> 30.0
    assert rolled.loc["2020-03-11"] == 30.0


def test_dekad_fit_window_cyclic_wrapping():
    """Verify that rolling calibration window (fit_window > 0) wraps cyclically across 36 dekads."""
    dates = pd.date_range("2010-01-01", "2024-12-31", freq="D")
    rng = np.random.default_rng(42)
    daily_precip = pd.Series(rng.gamma(1.5, 4.0, size=len(dates)), index=dates)

    # Cara 2 with fit_window=3 dasarians (~1 month calibration window)
    res_fw3 = spi(daily_precip, dist=gamma, timescale=30, fit_freq="dekad", fit_window=3, prob_zero=True)
    assert len(res_fw3) == 538
    assert np.isfinite(res_fw3).sum() >= 530
    assert not np.isinf(res_fw3).any()


def test_rolling_dasarian_absent_index_vs_explicit_nan_equivalence():
    """Verify that an input series missing dekad timestamps produces the same result as one with explicit NaN timestamps."""
    full_dates = pd.DatetimeIndex([
        "2020-01-01", "2020-01-11", "2020-01-21",
        "2020-02-01", "2020-02-11", "2020-02-21",
        "2020-03-01", "2020-03-11", "2020-03-21",
    ])
    # Series A: Explicit NaN at 2020-02-11
    s_explicit_nan = pd.Series(10.0, index=full_dates)
    s_explicit_nan.loc["2020-02-11"] = np.nan

    # Series B: 2020-02-11 is completely absent from the index
    s_absent_dekad = s_explicit_nan.dropna()

    rolled_a = rolling_dasarian(s_explicit_nan, timescale=3)
    rolled_b = rolling_dasarian(s_absent_dekad, timescale=3)

    # Both must produce identical canonical 9-dekad index with identical NaN placements
    pd.testing.assert_series_equal(rolled_a, rolled_b)
    assert np.isnan(rolled_b.loc["2020-02-11"])
    assert np.isnan(rolled_b.loc["2020-02-21"])
    assert np.isnan(rolled_b.loc["2020-03-01"])
    assert rolled_b.loc["2020-03-11"] == 30.0


def test_rolling_dasarian_invalid_dates_and_duplicates():
    """Verify that rolling_dasarian validates calendar constraints strictly."""
    # Duplicate timestamps
    dup_dates = pd.DatetimeIndex(["2020-01-01", "2020-01-01", "2020-01-11"])
    s_dup = pd.Series([1.0, 2.0, 3.0], index=dup_dates)
    with pytest.raises(ValueError, match="(?i)duplicate"):
        rolling_dasarian(s_dup, timescale=3)

    # Non-dekad day (e.g. 15th)
    bad_dates = pd.DatetimeIndex(["2020-01-01", "2020-01-15", "2020-01-21"])
    s_bad = pd.Series([1.0, 2.0, 3.0], index=bad_dates)
    with pytest.raises(ValueError, match="not valid BMKG dasarian labels"):
        rolling_dasarian(s_bad, timescale=3)


def test_direct_dasarian_si_absent_index_safety():
    """Verify SI initialization on a dasarian series missing dekads preserves canonical timeline."""
    full_dates = pd.DatetimeIndex([
        "2010-01-01", "2010-01-11", "2010-01-21",
        "2010-02-01", "2010-02-11", "2010-02-21",
        "2010-03-01", "2010-03-11", "2010-03-21",
    ])
    s_explicit = pd.Series(20.0, index=full_dates)
    s_explicit.loc["2010-02-11"] = np.nan
    s_absent = s_explicit.dropna()

    si_explicit = SI(s_explicit, dist=gamma, timescale=3, fit_freq="dekad", prob_zero=True)
    si_absent = SI(s_absent, dist=gamma, timescale=3, fit_freq="dekad", prob_zero=True)

    pd.testing.assert_series_equal(si_explicit.series, si_absent.series)


# ==============================================================================
# SECTION 5 & 6: FIX D & D2 REGRESSION TESTS — DASARIAN DETECTION & TIMESTAMPS
# ==============================================================================


def test_d1_input_a_complete_daily_series_single_aggregation():
    """Test D1 (Input A): Complete daily series with fit_freq='dekad' aggregates to dasarians exactly once."""
    dates = pd.date_range("2020-01-01", "2020-12-31", freq="D")
    daily_s = pd.Series(5.0, index=dates)

    si = SI(daily_s, dist=gamma, timescale=0, fit_freq="dekad", prob_zero=True)

    # 2020 is leap year (366 days), exactly 36 dasarians
    assert len(si.series) == 36
    # Each dekad 1 and 2 has 10 days * 5.0 = 50.0
    assert si.series.loc["2020-01-01"] == 50.0
    assert si.series.loc["2020-01-11"] == 50.0
    # Jan dekad 3 has 11 days * 5.0 = 55.0
    assert si.series.loc["2020-01-21"] == 55.0


def test_d2_input_b_sparse_pre_aggregated_dasarian_series():
    """Test D2 (Input B): Sparse pre-aggregated dasarian input is not re-aggregated and preserves gaps."""
    # Pre-aggregated dekad totals with missing dekad at 2020-02-01
    das_dates = pd.DatetimeIndex([
        "2020-01-01", "2020-01-11", "2020-01-21",
        # 2020-02-01 is missing entirely
        "2020-02-11", "2020-02-21",
        "2020-03-01", "2020-03-11", "2020-03-21",
    ])
    vals = [10.0, 20.0, 30.0, 40.0, 50.0, 60.0, 70.0, 80.0]
    sparse_s = pd.Series(vals, index=das_dates)

    # Reference calculation using rolling_dasarian with timescale=2
    ref_rolled = rolling_dasarian(sparse_s, timescale=2).dropna()

    si = SI(sparse_s, dist=gamma, timescale=2, fit_freq="dekad", prob_zero=True)

    # 1. No second daily aggregation was performed (original values were preserved, not summed as 1-day daily rain)
    # 2. Results match the reference canonical rolling calculation
    pd.testing.assert_series_equal(si.series, ref_rolled)

    # 3. Gap at 2020-02-01 caused 2020-02-11 rolling window (which needs 2020-02-01 and 2020-02-11) to be NaN
    assert "2020-02-11" not in si.series.index
    # 2020-02-21 has both 2020-02-11 and 2020-02-21 available: 40 + 50 = 90
    assert si.series.loc["2020-02-21"] == 90.0


def test_d3_input_c_monthly_data_distinction_and_explicit_policy():
    """Test D3 (Input C): Monthly series labeled on day 1 is not inferred as dasarian, but explicit fit_freq is respected."""
    monthly_dates = pd.date_range("2015-01-01", periods=36, freq="MS")
    monthly_s = pd.Series(100.0, index=monthly_dates)

    # Automatic inference: must NOT infer dasarian cadence
    assert is_dasarian_index(monthly_s.index) is False
    inf_freq = infer_frequency(monthly_s.index)
    assert inf_freq in ("MS", "M")

    # Explicit fit_freq='dekad': treats day 1 labels as pre-aggregated dasarian dekad 1 without re-aggregating
    si_explicit = SI(monthly_s, dist=gamma, timescale=0, fit_freq="dekad", prob_zero=True)
    assert si_explicit._is_dasarian is True
    # Values are preserved as dekad 1 totals, not re-aggregated as daily rainfall
    assert si_explicit.series.loc["2015-01-01"] == 100.0


def test_d4_non_midnight_timestamps_rejected_by_rolling_dasarian():
    """Test D4: rolling_dasarian rejects non-midnight, timezone-aware, and invalid timestamps."""
    # 1. Valid midnight timestamps succeed
    valid_dates = pd.DatetimeIndex(["2020-01-01 00:00:00", "2020-01-11 00:00:00", "2020-01-21 00:00:00"])
    s_valid = pd.Series([10.0, 20.0, 30.0], index=valid_dates)
    res_valid = rolling_dasarian(s_valid, timescale=1)
    assert len(res_valid) == 3

    # 2. Single non-midnight label (2020-01-01 12:00:00) raises ValueError
    bad_dates = pd.DatetimeIndex(["2020-01-01 12:00:00", "2020-01-11 00:00:00", "2020-01-21 00:00:00"])
    s_bad = pd.Series([10.0, 20.0, 30.0], index=bad_dates)
    with pytest.raises(ValueError, match="non-midnight"):
        rolling_dasarian(s_bad, timescale=1)

    # 3. Non-midnight across complete index raises ValueError
    all_noon = valid_dates + pd.Timedelta(hours=12)
    s_noon = pd.Series([10.0, 20.0, 30.0], index=all_noon)
    with pytest.raises(ValueError, match="non-midnight"):
        rolling_dasarian(s_noon, timescale=1)

    # 4. Timezone-aware index raises ValueError
    s_tz = pd.Series([10.0, 20.0, 30.0], index=valid_dates.tz_localize("UTC"))
    with pytest.raises(ValueError, match="Timezone-aware"):
        rolling_dasarian(s_tz, timescale=1)

    # 5. Invalid day-of-month (e.g. day 15) raises ValueError
    s_invalid_day = pd.Series([10.0, 20.0, 30.0], index=pd.DatetimeIndex(["2020-01-01", "2020-01-15", "2020-01-21"]))
    with pytest.raises(ValueError, match="not valid BMKG dasarian labels"):
        rolling_dasarian(s_invalid_day, timescale=1)

    # 6. Duplicate timestamps raise ValueError
    s_dup = pd.Series([10.0, 20.0, 30.0], index=pd.DatetimeIndex(["2020-01-01", "2020-01-01", "2020-01-11"]))
    with pytest.raises(ValueError, match="Duplicate"):
        rolling_dasarian(s_dup, timescale=1)





