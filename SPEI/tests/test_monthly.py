"""Automated test suite for Monthly SPI aggregation, timescale mapping, and calculation."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest
from scipy.stats import gamma, weibull_min

import spei
from spei.utils import (
    canonical_monthly_calendar,
    get_expected_month_days,
    is_monthly_index,
    is_valid_monthly_labels,
    monthly_windows,
    MONTHLY_WINDOWS,
    rolling_monthly,
    rolling_month,
    to_monthly,
    to_month,
    daily_to_monthly,
    daily_to_month,
)
from spei.si import SI, spi


def test_is_monthly_index():
    """Verify detection of canonical monthly calendar cadence (1st of month)."""
    # 1. Valid monthly dates
    monthly_dates = pd.date_range("2020-01-01", "2020-12-01", freq="MS")
    assert is_valid_monthly_labels(monthly_dates) is True
    assert is_monthly_index(monthly_dates) is True

    # 2. Daily dates
    daily_dates = pd.date_range("2020-01-01", "2020-01-15", freq="D")
    assert is_valid_monthly_labels(daily_dates) is False
    assert is_monthly_index(daily_dates) is False

    # 3. Dasarian dates (days 1, 11, 21)
    das_dates = pd.DatetimeIndex([
        "2020-01-01", "2020-01-11", "2020-01-21",
        "2020-02-01", "2020-02-11", "2020-02-21",
    ])
    assert is_valid_monthly_labels(das_dates) is False
    assert is_monthly_index(das_dates) is False

    # 4. Empty index
    assert is_monthly_index(pd.DatetimeIndex([])) is False

    # 5. Non-midnight timestamps
    bad_time_dates = pd.DatetimeIndex(["2020-01-01 12:00:00", "2020-02-01 12:00:00"])
    assert is_valid_monthly_labels(bad_time_dates) is False
    assert is_monthly_index(bad_time_dates) is False


def test_to_monthly_calendar_definitions():
    """Verify monthly aggregation properly counts days in leap year Feb and 30/31-day months."""
    dates = pd.date_range("2020-01-01", "2020-04-30", freq="D")
    s = pd.Series(1.0, index=dates)

    monthly = to_monthly(s)
    assert len(monthly) == 4
    assert list(monthly.index) == [
        pd.Timestamp("2020-01-01"),
        pd.Timestamp("2020-02-01"),
        pd.Timestamp("2020-03-01"),
        pd.Timestamp("2020-04-01"),
    ]

    # Jan: 31 days
    assert monthly.loc["2020-01-01"] == 31.0
    # Feb (leap 2020): 29 days
    assert monthly.loc["2020-02-01"] == 29.0
    # Mar: 31 days
    assert monthly.loc["2020-03-01"] == 31.0
    # Apr: 30 days
    assert monthly.loc["2020-04-01"] == 30.0

    # Test non-leap year Feb (2021)
    dates_2021 = pd.date_range("2021-02-01", "2021-02-28", freq="D")
    s_2021 = pd.Series(2.0, index=dates_2021)
    monthly_2021 = to_monthly(s_2021)
    assert monthly_2021.loc["2021-02-01"] == 28.0 * 2.0


def test_to_monthly_min_valid_days_and_fraction():
    """Verify min_valid_days and min_valid_fraction coverage filtering."""
    # Jan 2021 has 31 days; drop 6 days -> 25 valid days remain
    dates = pd.date_range("2021-01-01", "2021-01-31", freq="D")
    s = pd.Series(2.0, index=dates)
    s.iloc[0:6] = np.nan

    # min_valid_days=26 -> fails, should be NaN
    res_strict = to_monthly(s, min_valid_days=26)
    assert np.isnan(res_strict.iloc[0])

    # min_valid_days=25 -> succeeds with 25 * 2.0 = 50.0
    res_lenient = to_monthly(s, min_valid_days=25)
    assert res_lenient.iloc[0] == 50.0

    # min_valid_fraction=0.85 requires ceil(31 * 0.85) = 27 days -> fails
    res_frac_strict = to_monthly(s, min_valid_fraction=0.85)
    assert np.isnan(res_frac_strict.iloc[0])

    # min_valid_fraction=0.80 requires ceil(31 * 0.80) = 25 days -> succeeds
    res_frac_ok = to_monthly(s, min_valid_fraction=0.80)
    assert res_frac_ok.iloc[0] == 50.0


def test_to_monthly_dataframe_multi_station():
    """Verify to_monthly works on 2D DataFrame matrices."""
    dates = pd.date_range("2022-01-01", "2022-12-31", freq="D")
    df = pd.DataFrame({
        "station_A": np.full(len(dates), 2.0),
        "station_B": np.full(len(dates), 5.0),
    }, index=dates)

    monthly_df = to_monthly(df)
    assert isinstance(monthly_df, pd.DataFrame)
    assert monthly_df.shape == (12, 2)
    assert monthly_df.columns.tolist() == ["station_A", "station_B"]
    # January: 31 days
    assert monthly_df["station_A"].iloc[0] == 31.0 * 2.0
    assert monthly_df["station_B"].iloc[0] == 31.0 * 5.0
    # February: 28 days (non-leap 2022)
    assert monthly_df["station_A"].iloc[1] == 28.0 * 2.0
    assert monthly_df["station_B"].iloc[1] == 28.0 * 5.0


def test_rolling_monthly_mapping():
    """Verify timescale mapping from nominal days to month counts."""
    dates = pd.date_range("2010-01-01", "2024-12-31", freq="D")
    s = pd.Series(1.0, index=dates)
    monthly = to_monthly(s)
    assert len(monthly) == 180  # 15 years * 12 months

    # Check nominal day timescales match month window lengths
    for days, window in monthly_windows.items():
        rolled_by_days = rolling_monthly(monthly, timescale=days)
        rolled_by_window = rolling_monthly(monthly, timescale=window)
        pd.testing.assert_series_equal(rolled_by_days, rolled_by_window)
        assert len(rolled_by_days.dropna()) == 180 - window + 1


def test_monthly_spi_direct_daily(prec_34010701a):
    """Verify direct daily call with fit_freq='monthly' matches manual to_monthly + rolling + spi."""
    # Method 1: Manual pipeline (to_monthly -> rolling_monthly(3) -> spi)
    monthly_precip = to_monthly(prec_34010701a, min_valid_fraction=0.80)
    rolled_3m = rolling_monthly(monthly_precip, timescale=3).dropna()
    spi_manual = spi(rolled_3m, dist=gamma, timescale=0, fit_freq="MS", prob_zero=True)

    # Method 2: Direct universal call on daily series with timescale=90 and fit_freq="monthly"
    spi_direct = spi(
        prec_34010701a,
        dist=gamma,
        timescale=90,
        fit_freq="monthly",
        prob_zero=True,
        min_valid_fraction=0.80,
    )

    # Output lengths and values must be identical
    assert len(spi_direct) == len(spi_manual)
    pd.testing.assert_index_equal(spi_direct.index, spi_manual.index)
    np.testing.assert_allclose(spi_direct.values, spi_manual.values, rtol=1e-5)


def test_monthly_spi_timescale_equivalence(prec_34010701a):
    """Verify timescale=90 and timescale=3 yield identical results under fit_freq='monthly'."""
    spi_days = spi(prec_34010701a, dist=gamma, timescale=90, fit_freq="monthly", prob_zero=True, min_valid_fraction=0.80)
    spi_months = spi(prec_34010701a, dist=gamma, timescale=3, fit_freq="monthly", prob_zero=True, min_valid_fraction=0.80)

    pd.testing.assert_series_equal(spi_days, spi_months)


def test_monthly_spi_pre_rolled(prec_34010701a):
    """Verify pre-rolled input works for both pre-rolled monthly data and pre-rolled daily data."""
    # 1. Pre-rolled monthly series (timescale=0)
    m_prec = to_monthly(prec_34010701a, min_valid_fraction=0.80)
    r_3m = rolling_monthly(m_prec, timescale=3).dropna()
    spi_prerolled_m = spi(r_3m, dist=gamma, timescale=0, fit_freq="monthly", prob_zero=True)
    assert len(spi_prerolled_m) == len(r_3m)
    assert not np.isinf(spi_prerolled_m).any()

    # 2. Pre-rolled daily series (timescale=0 on daily series):
    # If user pre-rolls daily series over 90 days, sampling month-end aligns with monthly SPI-3
    daily_rolled_90 = prec_34010701a.rolling(90, min_periods=90).sum().dropna()
    spi_prerolled_d = spi(daily_rolled_90, dist=gamma, timescale=0, fit_freq="monthly", prob_zero=True)
    # Output must be monthly
    assert is_monthly_index(spi_prerolled_d.index) is True
    assert not np.isinf(spi_prerolled_d).any()


def test_aliases_consistency():
    """Verify function and dictionary aliases consistency."""
    assert to_month is to_monthly
    assert daily_to_monthly is to_monthly
    assert daily_to_month is to_monthly
    assert rolling_month is rolling_monthly
    assert MONTHLY_WINDOWS is monthly_windows
