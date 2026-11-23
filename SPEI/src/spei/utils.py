import logging
from calendar import isleap

from typing import Literal
import pandas as pd
import numpy as np
from numpy import array, clip, nan
from packaging.version import parse as parse_version
from pandas import (
    DataFrame,
    DatetimeIndex,
    Grouper,
    Index,
    Series,
    Timedelta,
    concat,
    infer_freq,
    to_datetime,
)

pd_version = parse_version(__import__("pandas").__version__)

# Scale mapping: timescale identifier (nominal days) -> window length in dasarians
dasarian_windows: dict[int, int] = {
    10: 1,   # 1 dasarian (~10 days)
    20: 2,   # 2 dasarians (~20 days)
    30: 3,   # 3 dasarians (~30 days / 1 month)
    60: 6,   # 6 dasarians (~60 days / 2 months)
    90: 9,   # 9 dasarians (~90 days / 3 months)
    120: 12, # 12 dasarians (~120 days / 4 months)
    180: 18, # 18 dasarians (~180 days / 6 months)
    270: 27, # 27 dasarians (~270 days / 9 months)
    360: 36, # 36 dasarians (~360 days / 12 months / 1 year)
}

# Alias for backward compatibility
DASARIAN_WINDOWS = dasarian_windows

# Scale mapping: timescale identifier (nominal days) -> window length in months
monthly_windows: dict[int, int] = {
    30: 1,    # ~1 month (SPI-1)
    60: 2,    # ~2 months (SPI-2)
    90: 3,    # ~3 months (SPI-3)
    120: 4,   # ~4 months (SPI-4)
    180: 6,   # ~6 months (SPI-6)
    270: 9,   # ~9 months (SPI-9)
    360: 12,  # ~12 months / 1 year (SPI-12)
    720: 24,  # ~24 months / 2 years (SPI-24)
}

# Alias for backward compatibility
MONTHLY_WINDOWS = monthly_windows



def get_expected_dasarian_days(ts: pd.Timestamp) -> int:
    """Calculate expected calendar days in a standard BMKG dasarian (10-day dekad).

    - Dasarian 1 (dates 1–10, labeled YYYY-MM-01): 10 days
    - Dasarian 2 (dates 11–20, labeled YYYY-MM-11): 10 days
    - Dasarian 3 (dates 21–end of month, labeled YYYY-MM-21): 8–11 days depending on month & leap year.
    """
    ts = pd.Timestamp(ts)
    y, m, d = ts.year, ts.month, ts.day
    if d in (1, 11):
        return 10
    from calendar import monthrange
    _, last_day = monthrange(y, m)
    return last_day - 20


def canonical_dasarian_calendar(start_date: pd.Timestamp, end_date: pd.Timestamp) -> DatetimeIndex:
    """Generate canonical 36-dekad-per-year DatetimeIndex between start and end dates.

    Guarantees exactly 36 dasarian labels (days 1, 11, and 21) for every complete calendar year.
    """
    start_ts = pd.Timestamp(start_date)
    end_ts = pd.Timestamp(end_date)
    start_dekad_d = 1 if start_ts.day <= 10 else 11 if start_ts.day <= 20 else 21
    start_dekad = pd.Timestamp(year=start_ts.year, month=start_ts.month, day=start_dekad_d)

    end_dekad_d = 1 if end_ts.day <= 10 else 11 if end_ts.day <= 20 else 21
    end_dekad = pd.Timestamp(year=end_ts.year, month=end_ts.month, day=end_dekad_d)

    dates = []
    for y in range(start_dekad.year, end_dekad.year + 1):
        for m in range(1, 13):
            for d in (1, 11, 21):
                ts = pd.Timestamp(year=y, month=m, day=d)
                if start_dekad <= ts <= end_dekad:
                    dates.append(ts)
    return DatetimeIndex(dates)


def get_expected_month_days(ts: pd.Timestamp) -> int:
    """Calculate expected calendar days in a calendar month.

    Feb: 28 or 29 days (depending on leap year).
    Apr, Jun, Sep, Nov: 30 days.
    Jan, Mar, May, Jul, Aug, Oct, Dec: 31 days.
    """
    ts = pd.Timestamp(ts)
    from calendar import monthrange
    return monthrange(ts.year, ts.month)[1]


def canonical_monthly_calendar(start_date: pd.Timestamp, end_date: pd.Timestamp) -> DatetimeIndex:
    """Generate canonical 12-month-per-year DatetimeIndex between start and end dates (at YYYY-MM-01 00:00:00)."""
    start_ts = pd.Timestamp(start_date)
    end_ts = pd.Timestamp(end_date)
    start_month = pd.Timestamp(year=start_ts.year, month=start_ts.month, day=1)
    end_month = pd.Timestamp(year=end_ts.year, month=end_ts.month, day=1)
    return pd.date_range(start_month, end_month, freq="MS")


def is_valid_dasarian_labels(index: Index | DatetimeIndex) -> bool:
    """Check if all timestamps are valid canonical BMKG dasarian labels.

    Valid dasarian labels must be:
    - Timezone-naive datetime labels.
    - Exact midnight timestamps (00:00:00).
    - Days strictly in {1, 11, 21}.
    - Minimum spacing between consecutive labels of at least 7 days (shortest dekad is 8 days).

    Unlike is_dasarian_index, this validates label correctness rather than cadence completeness.
    """
    if not isinstance(index, DatetimeIndex):
        try:
            index = DatetimeIndex(to_datetime(index))
        except Exception:
            return False
    if len(index) == 0:
        return False
    if index.tz is not None:
        return False
    if (
        (index.hour != 0).any()
        or (index.minute != 0).any()
        or (index.second != 0).any()
        or (index.microsecond != 0).any()
    ):
        return False
    days = set(index.day)
    if not days.issubset({1, 11, 21}):
        return False
    if len(index) >= 2:
        diffs = Series(index).diff().dropna()
        if (diffs < Timedelta(days=7)).any():
            return False
    return True


def is_dasarian_index(index: Index | DatetimeIndex) -> bool:
    """Check if index follows BMKG standard dasarian calendar cadence (days 1, 11, and 21 at midnight).

    Parameters
    ----------
    index : pandas.Index or pandas.DatetimeIndex
        Time series index to check.

    Returns
    -------
    bool
        True if the index exhibits dasarian cadence, False otherwise.
    """
    if not is_valid_dasarian_labels(index):
        return False

    if not isinstance(index, DatetimeIndex):
        index = DatetimeIndex(to_datetime(index))

    days = set(index.day)
    if len(index) >= 2:
        diffs = Series(index).diff().dropna()
        median_diff = diffs.median()

        # Disambiguate monthly series:
        # A monthly series has ONLY day 1 (days == {1}) and median diff >= 25 days (~30 days).
        # We must NOT confidently infer dasarian cadence for a monthly series solely because its dates are on day 1.
        if days == {1} and median_diff >= Timedelta(days=25):
            return False

        # If days contains 11 or 21, it is uniquely dasarian (monthly never has day 11 or 21).
        # For general cadence, median diff up to 35 days (sparse dasarian with occasional missing dekad)
        # is accepted if day 11 or 21 is present.
        if median_diff > Timedelta(days=35) and not (days & {11, 21}):
            return False

    elif len(index) == 1:
        # Single date: day 11 or 21 is uniquely dasarian; day 1 is ambiguous (could be monthly)
        if index[0].day not in (11, 21):
            return False

    return True


def is_valid_monthly_labels(index: Index | DatetimeIndex) -> bool:
    """Check if all timestamps are valid canonical monthly labels.

    Valid monthly labels must be:
    - Timezone-naive datetime labels.
    - Exact midnight timestamps (00:00:00).
    - Days strictly on the 1st of the month (day == 1).
    - Minimum spacing between consecutive labels of at least 25 days.
    """
    if not isinstance(index, DatetimeIndex):
        try:
            index = DatetimeIndex(to_datetime(index))
        except Exception:
            return False
    if len(index) == 0:
        return False
    if index.tz is not None:
        return False
    if (
        (index.hour != 0).any()
        or (index.minute != 0).any()
        or (index.second != 0).any()
        or (index.microsecond != 0).any()
        or (getattr(index, "nanosecond", Series(0, index=range(len(index)))) != 0).any()
    ):
        return False
    days = set(index.day)
    if not days.issubset({1}):
        return False
    if len(index) >= 2:
        diffs = Series(index).diff().dropna()
        if (diffs < Timedelta(days=25)).any():
            return False
    return True


def is_monthly_index(index: Index | DatetimeIndex) -> bool:
    """Check if index follows canonical monthly calendar cadence (1st of month, median interval 28-31 days)."""
    if not is_valid_monthly_labels(index):
        return False
    if not isinstance(index, DatetimeIndex):
        index = DatetimeIndex(to_datetime(index))
    if len(index) >= 2:
        diffs = Series(index).diff().dropna()
        median_diff = diffs.median()
        if not (Timedelta(days=25) <= median_diff <= Timedelta(days=35)):
            return False
    return True


def to_dasarian(
    data: Series | DataFrame,
    min_valid_fraction: float | None = None,
    min_valid_days: int | None = None,
    agg_func: Literal["sum", "mean"] = "sum",
) -> Series | DataFrame:
    """Aggregate daily precipitation/hydro-meteorological data into dasarian (10-day dekad) totals.

    Uses BMKG (Indonesian Agency for Meteorology, Climatology, and Geophysics) standard calendar definitions:
    - Dasarian 1: Dates 1–10 (labeled `YYYY-MM-01`)
    - Dasarian 2: Dates 11–20 (labeled `YYYY-MM-11`)
    - Dasarian 3: Dates 21–end of month (labeled `YYYY-MM-21`, covering 8–11 days depending on month & leap year).

    Parameters
    ----------
    data : pandas.Series or pandas.DataFrame
        Daily observations indexed by a DatetimeIndex (or datetime-like strings).
        Can be a 1D Series (single station) or 2D DataFrame (multi-station matrix).
    min_valid_fraction : float or None, default=None
        Minimum fraction of expected calendar days required per dasarian (0.0 to 1.0).
        If both min_valid_fraction and min_valid_days are None, defaults to 1.0 (strict operational completeness).
    min_valid_days : int or None, default=None
        Minimum number of valid (non-NaN) daily records required per dasarian.
        Supported for backward compatibility. If specified and min_valid_fraction is None,
        uses min_valid_days directly.
    agg_func : Literal["sum", "mean"], default="sum"
        Aggregation function:
        - "sum": For flux/cumulative variables such as rainfall/precipitation (used in SPI/DSPI).
        - "mean": For state/average variables such as temperature, groundwater, or streamflow.

    Returns
    -------
    pandas.Series or pandas.DataFrame
        Dasarian-aggregated data sorted chronologically with exactly 36 dasarians per calendar year.
        Bins failing coverage requirements are returned as NaN. Missing dekads are preserved as NaN.
    """
    if not isinstance(data, (Series, DataFrame)):
        raise TypeError(f"Expected pandas.Series or pandas.DataFrame, got {type(data)}")

    data = data.copy()
    if not isinstance(data.index, DatetimeIndex):
        data.index = DatetimeIndex(to_datetime(data.index))

    if data.index.has_duplicates:
        raise ValueError("Duplicated indices found in input daily data. Please remove or aggregate them.")

    if not data.index.is_monotonic_increasing:
        logging.info("Sorting input daily series chronologically before dasarian aggregation")
        data = data.sort_index()

    if data.empty:
        return data

    from calendar import monthrange
    start_ts = data.index.min()
    end_ts = data.index.max()
    start_dekad_d = 1 if start_ts.day <= 10 else 11 if start_ts.day <= 20 else 21
    start_dekad = pd.Timestamp(year=start_ts.year, month=start_ts.month, day=start_dekad_d)
    end_dekad_d = 1 if end_ts.day <= 10 else 11 if end_ts.day <= 20 else 21
    end_dekad = pd.Timestamp(year=end_ts.year, month=end_ts.month, day=end_dekad_d)
    canonical_idx = canonical_dasarian_calendar(start_dekad, end_dekad)

    # Reindex input to complete daily calendar range to ensure missing days are accounted for
    last_day_of_month = monthrange(end_dekad.year, end_dekad.month)[1]
    daily_end = pd.Timestamp(year=end_dekad.year, month=end_dekad.month, day=last_day_of_month if end_ts.day > 20 else min(end_ts.day, 20 if end_ts.day > 10 else 10))
    full_daily_idx = pd.date_range(start_dekad, max(end_ts, daily_end), freq="D")
    if len(full_daily_idx) != len(data.index) or not data.index.equals(full_daily_idx):
        data = data.reindex(full_daily_idx)

    idx = data.index
    dekad = clip((idx.day - 1) // 10, 0, 2)
    labels = to_datetime(idx.strftime("%Y-%m-01")) + pd.to_timedelta(dekad * 10, unit="D")

    # Determine coverage policy
    if min_valid_fraction is None and min_valid_days is None:
        eff_fraction = 1.0
    else:
        eff_fraction = min_valid_fraction

    grouped = data.groupby(labels)
    counts = grouped.count()
    if agg_func == "sum":
        sums = grouped.sum(min_count=1)
    elif agg_func == "mean":
        sums = grouped.mean()
    else:
        sums = grouped.agg(agg_func)

    res = sums.reindex(canonical_idx)
    counts = counts.reindex(canonical_idx).fillna(0)

    # Apply dekad-specific coverage thresholds
    for dekad_ts in canonical_idx:
        exp_days = get_expected_dasarian_days(dekad_ts)
        if eff_fraction is not None:
            req_days = int(np.ceil(exp_days * eff_fraction))
            if min_valid_days is not None:
                req_days = max(req_days, int(min_valid_days))
        elif min_valid_days is not None:
            req_days = int(min_valid_days)
        else:
            req_days = exp_days

        if isinstance(res, DataFrame):
            mask = counts.loc[dekad_ts] < req_days
            res.loc[dekad_ts, mask] = nan
        else:
            if counts.loc[dekad_ts] < req_days:
                res.loc[dekad_ts] = nan

    return res


# Common aliases
to_dekad = to_dasarian
daily_to_dasarian = to_dasarian
daily_to_dekad = to_dasarian


def rolling_dasarian(
    data: Series | DataFrame,
    timescale: int = 1,
    min_periods: int | None = None,
    agg_func: Literal["sum", "mean"] = "sum",
) -> Series | DataFrame:
    """Compute trailing rolling accumulation or mean over dasarian windows.

    Parameters
    ----------
    data : pandas.Series or pandas.DataFrame
        Dasarian time series or matrix (e.g., from `to_dasarian`).
    timescale : int, default=1
        Rolling window length. Can be specified either as:
        - Number of dasarians (e.g., 1, 2, 3, 6, 9, 12, 18, 36), OR
        - Timescale identifier in days matching BMKG conventions (e.g.,
          10 -> 1 dasarian, 20 -> 2 dasarians, 30 -> 3 dasarians, 60 -> 6, 90 -> 9, etc.).
    min_periods : int or None, default=None
        Minimum number of valid observations required in window.
        Defaults to the window length (strict rolling).
    agg_func : Literal["sum", "mean"], default="sum"
        Aggregation function ("sum" for precipitation, "mean" for indices).

    Returns
    -------
    pandas.Series or pandas.DataFrame
        Trailing rolled dasarian time series or matrix reindexed to canonical calendar.
    """
    if not isinstance(data, (Series, DataFrame)):
        raise TypeError(f"Expected pandas.Series or pandas.DataFrame, got {type(data)}")

    data = data.copy()
    if not isinstance(data.index, DatetimeIndex):
        data.index = DatetimeIndex(to_datetime(data.index))

    # Timezone-aware check: dasarian canonical calendar labels must be timezone-naive
    if data.index.tz is not None:
        raise ValueError(
            "Timezone-aware index detected. Dasarian calendar labels must be timezone-naive "
            "canonical midnight timestamps (days 1, 11, 21 at 00:00:00)."
        )

    # Time component check: must be midnight (00:00:00)
    has_non_midnight = (
        (data.index.hour != 0)
        | (data.index.minute != 0)
        | (data.index.second != 0)
        | (data.index.microsecond != 0)
        | (data.index.nanosecond != 0)
    )
    if has_non_midnight.any():
        bad_ts = data.index[has_non_midnight][0]
        raise ValueError(
            f"Input index contains non-midnight timestamp '{bad_ts}'. "
            "Dasarian labels must be exact canonical calendar labels at midnight (00:00:00) on days 1, 11, or 21."
        )

    # Duplicate check
    if data.index.has_duplicates:
        raise ValueError("Duplicate timestamps found in dasarian input series.")

    # Day-of-month check
    days = set(data.index.day)
    if not days.issubset({1, 11, 21}):
        invalid_days = sorted(days - {1, 11, 21})
        raise ValueError(
            "Input index contains timestamps that are not valid BMKG dasarian labels "
            f"(expected days 1, 11, or 21; found days {invalid_days})."
        )

    if not data.index.is_monotonic_increasing:
        logging.info("Sorting input dasarian series chronologically")
        data = data.sort_index()

    if data.empty:
        return data

    if timescale in dasarian_windows:
        w = dasarian_windows[timescale]
    else:
        w = int(timescale)

    if min_periods is None:
        min_periods = w

    # Reindex to canonical dasarian calendar to prevent compressing gaps
    start_ts = data.index.min()
    end_ts = data.index.max()
    start_dekad_d = 1 if start_ts.day <= 10 else 11 if start_ts.day <= 20 else 21
    end_dekad_d = 1 if end_ts.day <= 10 else 11 if end_ts.day <= 20 else 21
    start_dekad = pd.Timestamp(year=start_ts.year, month=start_ts.month, day=start_dekad_d)
    end_dekad = pd.Timestamp(year=end_ts.year, month=end_ts.month, day=end_dekad_d)
    canonical_idx = canonical_dasarian_calendar(start_dekad, end_dekad)

    if len(canonical_idx) != len(data.index) or not data.index.equals(canonical_idx):
        data = data.reindex(canonical_idx)

    return data.rolling(w, min_periods=min_periods).agg(agg_func)


rolling_dekad = rolling_dasarian


def to_monthly(
    data: Series | DataFrame,
    min_valid_fraction: float | None = None,
    min_valid_days: int | None = None,
    agg_func: Literal["sum", "mean"] = "sum",
) -> Series | DataFrame:
    """Aggregate daily precipitation/hydro-meteorological data into monthly totals.

    Labels each month at month-start (`YYYY-MM-01 00:00:00`) following standard WMO calendar conventions.

    Parameters
    ----------
    data : pandas.Series or pandas.DataFrame
        Daily observations indexed by a DatetimeIndex (or datetime-like strings).
        Can be a 1D Series (single station) or 2D DataFrame (multi-station matrix).
    min_valid_fraction : float or None, default=None
        Minimum fraction of expected calendar days required per month (0.0 to 1.0).
        If both min_valid_fraction and min_valid_days are None, defaults to 1.0 (strict operational completeness).
    min_valid_days : int or None, default=None
        Minimum number of valid (non-NaN) daily records required per month.
        If specified and min_valid_fraction is None, uses min_valid_days directly.
    agg_func : Literal["sum", "mean"], default="sum"
        Aggregation function:
        - "sum": For flux/cumulative variables such as rainfall/precipitation (used in SPI/DSPI).
        - "mean": For state/average variables such as temperature, groundwater, or streamflow.

    Returns
    -------
    pandas.Series or pandas.DataFrame
        Monthly-aggregated data sorted chronologically with exactly 12 months per calendar year.
        Months failing coverage requirements are returned as NaN. Missing months are preserved as NaN.
    """
    if not isinstance(data, (Series, DataFrame)):
        raise TypeError(f"Expected pandas.Series or pandas.DataFrame, got {type(data)}")

    data = data.copy()
    if not isinstance(data.index, DatetimeIndex):
        data.index = DatetimeIndex(to_datetime(data.index))

    if data.index.has_duplicates:
        raise ValueError("Duplicated indices found in input daily data. Please remove or aggregate them.")

    if not data.index.is_monotonic_increasing:
        logging.info("Sorting input daily series chronologically before monthly aggregation")
        data = data.sort_index()

    if data.empty:
        return data

    from calendar import monthrange
    start_ts = data.index.min()
    end_ts = data.index.max()
    start_month = pd.Timestamp(year=start_ts.year, month=start_ts.month, day=1)
    end_month = pd.Timestamp(year=end_ts.year, month=end_ts.month, day=1)
    canonical_idx = canonical_monthly_calendar(start_month, end_month)

    # Reindex input to complete daily calendar range to ensure missing days are accounted for
    last_day_of_month = monthrange(end_month.year, end_month.month)[1]
    daily_end = pd.Timestamp(year=end_month.year, month=end_month.month, day=last_day_of_month)
    full_daily_idx = pd.date_range(start_month, daily_end, freq="D")
    if len(full_daily_idx) != len(data.index) or not data.index.equals(full_daily_idx):
        data = data.reindex(full_daily_idx)

    idx = data.index
    labels = to_datetime(idx.strftime("%Y-%m-01"))

    # Determine coverage policy
    if min_valid_fraction is None and min_valid_days is None:
        eff_fraction = 1.0
    else:
        eff_fraction = min_valid_fraction

    grouped = data.groupby(labels)
    counts = grouped.count()
    if agg_func == "sum":
        sums = grouped.sum(min_count=1)
    elif agg_func == "mean":
        sums = grouped.mean()
    else:
        sums = grouped.agg(agg_func)

    res = sums.reindex(canonical_idx)
    counts = counts.reindex(canonical_idx).fillna(0)

    # Apply month-specific coverage thresholds
    for month_ts in canonical_idx:
        exp_days = get_expected_month_days(month_ts)
        if eff_fraction is not None:
            req_days = int(np.ceil(exp_days * eff_fraction))
            if min_valid_days is not None:
                req_days = max(req_days, int(min_valid_days))
        elif min_valid_days is not None:
            req_days = int(min_valid_days)
        else:
            req_days = exp_days

        if isinstance(res, DataFrame):
            mask = counts.loc[month_ts] < req_days
            res.loc[month_ts, mask] = nan
        else:
            if counts.loc[month_ts] < req_days:
                res.loc[month_ts] = nan

    return res


# Common aliases
to_month = to_monthly
daily_to_monthly = to_monthly
daily_to_month = to_monthly


def rolling_monthly(
    data: Series | DataFrame,
    timescale: int = 1,
    min_periods: int | None = None,
    agg_func: Literal["sum", "mean"] = "sum",
) -> Series | DataFrame:
    """Compute trailing rolling accumulation or mean over monthly windows.

    Parameters
    ----------
    data : pandas.Series or pandas.DataFrame
        Monthly time series or matrix (e.g., from `to_monthly`).
    timescale : int, default=1
        Rolling window length. Can be specified either as:
        - Number of months (e.g., 1, 2, 3, 6, 9, 12, 18, 24), OR
        - Timescale identifier in nominal days matching standard conventions (e.g.,
          30 -> 1 month, 60 -> 2 months, 90 -> 3 months, 120 -> 4, 180 -> 6, 270 -> 9, 360 -> 12, etc.).
    min_periods : int or None, default=None
        Minimum number of valid observations required in window.
        Defaults to the window length (strict rolling).
    agg_func : Literal["sum", "mean"], default="sum"
        Aggregation function ("sum" for precipitation, "mean" for indices).

    Returns
    -------
    pandas.Series or pandas.DataFrame
        Trailing rolled monthly time series or matrix reindexed to canonical calendar.
    """
    if not isinstance(data, (Series, DataFrame)):
        raise TypeError(f"Expected pandas.Series or pandas.DataFrame, got {type(data)}")

    data = data.copy()
    if not isinstance(data.index, DatetimeIndex):
        data.index = DatetimeIndex(to_datetime(data.index))

    # Timezone-aware check: monthly canonical calendar labels must be timezone-naive
    if data.index.tz is not None:
        raise ValueError(
            "Timezone-aware index detected. Monthly calendar labels must be timezone-naive "
            "canonical midnight timestamps (day 1 at 00:00:00)."
        )

    # Time component check: must be midnight (00:00:00)
    has_non_midnight = (
        (data.index.hour != 0)
        | (data.index.minute != 0)
        | (data.index.second != 0)
        | (data.index.microsecond != 0)
        | (data.index.nanosecond != 0)
    )
    if has_non_midnight.any():
        bad_ts = data.index[has_non_midnight][0]
        raise ValueError(
            f"Input index contains non-midnight timestamp '{bad_ts}'. "
            "Monthly labels must be exact canonical calendar labels at midnight (00:00:00) on day 1."
        )

    # Duplicate check
    if data.index.has_duplicates:
        raise ValueError("Duplicate timestamps found in monthly input series.")

    # Day-of-month check
    days = set(data.index.day)
    if not days.issubset({1}):
        invalid_days = sorted(days - {1})
        raise ValueError(
            "Input index contains timestamps that are not valid month-start labels "
            f"(expected day 1; found days {invalid_days})."
        )

    if not data.index.is_monotonic_increasing:
        logging.info("Sorting input monthly series chronologically")
        data = data.sort_index()

    if data.empty:
        return data

    if timescale in monthly_windows:
        w = monthly_windows[timescale]
    else:
        w = int(timescale)

    if min_periods is None:
        min_periods = w

    # Reindex to canonical monthly calendar to prevent compressing gaps
    start_month = pd.Timestamp(year=data.index.min().year, month=data.index.min().month, day=1)
    end_month = pd.Timestamp(year=data.index.max().year, month=data.index.max().month, day=1)
    canonical_idx = canonical_monthly_calendar(start_month, end_month)

    if len(canonical_idx) != len(data.index) or not data.index.equals(canonical_idx):
        data = data.reindex(canonical_idx)

    return data.rolling(w, min_periods=min_periods).agg(agg_func)


rolling_month = rolling_monthly


def dasarian_window_group_yearly_df(dfval: DataFrame, period: int) -> DataFrame:
    """Pad a cyclic rolling calibration window across the 36 dasarian positions.

    Wraps across the year boundary (period dasarians from end of year before Jan 1,
    and period dasarians from start of year after Dec 21) preserving exact dekad identities.

    Parameters
    ----------
    dfval : pandas.DataFrame
        DataFrame grouped per year with index as dasarian dates in year 2000.
    period : int
        Half window length in dasarian units (number of adjacent dasarians on each side).

    Returns
    -------
    pandas.DataFrame
        Cyclic-padded DataFrame for rolling calibration window.
    """
    if len(dfval) == 0:
        return dfval

    period = int(period)
    if period <= 0:
        return dfval

    top_vals = dfval.iloc[-period:].values
    bottom_vals = dfval.iloc[:period].values

    top_index = [
        pd.Timestamp(year=1999, month=ts.month, day=ts.day)
        for ts in dfval.index[-period:]
    ]
    bottom_index = [
        pd.Timestamp(year=2001, month=ts.month, day=ts.day)
        for ts in dfval.index[:period]
    ]
    full_index = DatetimeIndex(top_index + list(dfval.index) + bottom_index)

    res = DataFrame(nan, index=full_index, columns=dfval.columns, dtype=float)
    res.iloc[:period] = top_vals
    res.iloc[period : period + len(dfval)] = dfval.values
    res.iloc[period + len(dfval) :] = bottom_vals
    return res


def validate_series(series: Series) -> Series:
    series = series.copy()

    if not isinstance(series, Series):
        if isinstance(series, DataFrame):
            if len(series.columns) == 1:
                logging.warning(
                    "Please convert series of type pandas.DataFrame to a"
                    "pandas.Series using DataFrame.squeeze(). Now done automatically."
                )
                series = series.squeeze()
            else:
                raise TypeError(
                    "Please provide a pandas.Series instead of a pandas.DataFrame"
                )
        else:
            raise TypeError(f"Please provide a Pandas Series instead of {type(series)}")

    index = validate_index(series.index)
    series = series.reindex(index, copy=True)
    if not series.index.is_monotonic_increasing:
        logging.info("Sorting input series chronologically")
        series = series.sort_index()

    return series


def validate_index(index: Index) -> DatetimeIndex:
    index = index.copy()

    if not isinstance(index, DatetimeIndex):
        logging.info(
            f"Expected the index to be a DatetimeIndex. Automatically converted "
            f"{type(index)} using pd.to_datetime(Index)"
        )
        index = DatetimeIndex(to_datetime(index))

    if index.has_duplicates:
        msg = (
            "Duplicated indices found. Please remove them. For instance by"
            " using `series = "
            "series.loc[~series.index.duplicated(keep='first/last')]`"
        )
        logging.error(msg)
        raise ValueError(msg)

    return index


def infer_frequency(index: Index | DatetimeIndex) -> str:

    """Infer frequency from time series index."""

    index = validate_index(index)

    if is_dasarian_index(index):
        logging.info("Inferred dasarian (dekad) cadence from index; using daily frequency 'D' (36 calendar dekads)")
        return "D"

    if is_monthly_index(index):
        logging.info("Inferred monthly cadence from index; using monthly frequency 'MS'")
        return "MS"

    inf_freq = infer_freq(index)

    if inf_freq is None:
        logging.info(
            "Could not infer frequency from index, using monthly frequency instead"
        )
        inf_freq = "MS" if pd_version >= parse_version("2.2.0") else "M"
    else:
        logging.info(f"Inferred frequency '{inf_freq}' from index")

    if "W-" in inf_freq:
        logging.info(f"Converted frequncy weekly '{inf_freq}' to 'W'")
        inf_freq = "W"

    return inf_freq



def group_yearly_df(series: Series) -> DataFrame:
    """Group Series per year in a DataFrame.

    This function groups a time series by year, creating a DataFrame where each
    column corresponds to a year (as int). The index of the DataFrame is set to
    the corresponding dates (in the year 2000).

    Parameters:
    -----------
    series : pd.Series
        A pandas Series with a DateTime index.

    Returns:
    --------
    pd.DataFrame
    """
    strfstr: str = "%m-%d %H:%M:%S"
    grs = {}
    freq = "YE" if pd_version >= parse_version("2.2.0") else "Y"
    for year_timestamp, gry in series.groupby(Grouper(freq=freq)):
        index = validate_index(gry.index)
        gry.index = to_datetime(
            "2000-" + index.strftime(strfstr), format="%Y-" + strfstr
        )
        year = getattr(year_timestamp, "year")  # type: str
        grs[year] = gry
    return concat(grs, axis=1)


def get_data_series(group_df: DataFrame) -> Series:
    """Transform grouped dataframe by yearly values back to time series."""
    strfstr: str = "%m-%d %H:%M:%S"
    index = validate_index(group_df.index)
    idx = array(
        [(f"{col}-" + index.strftime(strfstr)).tolist() for col in group_df.columns]
    ).flatten()
    # remove illegal 29 february for non leap years created by group_yearly_df
    boolidx = ~array(
        [
            (x.split(" ")[0].split("-", 1)[1] == "02-29")
            and not isleap(int(x.split(" ")[0].split("-")[0]))
            for x in idx
        ]
    )

    dt_idx = to_datetime(idx[boolidx], format="%Y-" + strfstr)
    values = group_df.transpose().values.flatten()[boolidx]
    return Series(values, index=dt_idx, dtype=float).dropna()


def daily_window_group_yearly_df(dfval: DataFrame, period: int) -> DataFrame:
    """Fill a period of daily values in grouped by yearly DataFrame to get
    cyclic rolling window.
    """
    dfval_window_index_start = [
        dfval.index[0] + Timedelta(value=-i, unit="D")
        for i in reversed(range(1, period + 1))
    ]
    dfval_window_index_end = [
        dfval.index[-1] + Timedelta(value=i, unit="D") for i in range(1, period + 1)
    ]
    dfval_window_index = DatetimeIndex(
        dfval_window_index_start + dfval.index.to_list() + dfval_window_index_end
    )

    dfval_window = DataFrame(
        nan, index=dfval_window_index, columns=dfval.columns, dtype=float
    )
    dfval_window.loc[dfval.index, dfval.columns] = dfval.values
    dfval_window.iloc[:period] = dfval.iloc[-period:].values
    dfval_window.iloc[-period:] = dfval.iloc[:period].values
    return dfval_window
