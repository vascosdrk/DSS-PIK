import logging
from dataclasses import dataclass, field
from typing import Any, Literal

import numpy as np
from numpy import ceil, interp, linspace, nan
import pandas as pd
from pandas import DataFrame, DatetimeIndex, Grouper, Series, Timedelta, Timestamp, to_datetime
from scipy.stats import beta, fisk, gamma, genextreme, norm, rankdata

from ._typing import ContinuousDist
from .dist import Dist
from .utils import (
    canonical_monthly_calendar,
    dasarian_windows,
    daily_window_group_yearly_df,
    dasarian_window_group_yearly_df,
    get_data_series,
    group_yearly_df,
    infer_frequency,
    is_dasarian_index,
    is_monthly_index,
    is_valid_dasarian_labels,
    is_valid_monthly_labels,
    monthly_windows,
    rolling_dasarian,
    rolling_dekad,
    rolling_monthly,
    to_dasarian,
    to_dekad,
    to_monthly,
    validate_series,
)




def sgi(
    series: Series,
    timescale: int = 0,
    fit_freq: str | None = None,
) -> Series:
    """Method to compute the Standardized Groundwater Index. Uses
    the normal scores transform to calculate the cumulative density function.

    Parameters
    ----------
    series: pandas.Series
        Pandas time series of the groundwater levels. Time series index
        should be a pandas DatetimeIndex.
    fit_freq : str, optional, default=None
        Frequency for fitting the distribution. Default is None in which case
        the frequency of the series is inferred. If this fails a monthly
        frequency is used.

    Returns
    -------
    pandas.Series

    References
    ----------
    Bloomfield, J. P. and Marchant, B. P.: Analysis of
    groundwater drought building on the standardised precipitation index
    approach. Hydrol. Earth Syst. Sci., 17, 4769-4787, 2013.
    """

    mock_dist = norm
    sgi_obj = SI(
        series=series,
        dist=mock_dist,
        timescale=timescale,
        fit_freq=fit_freq,
        fit_window=0,
        prob_zero=False,
        normal_scores_transform=True,
        agg_func="mean",
    )
    return sgi_obj.norm_ppf()


def spi(
    series: Series,
    dist: ContinuousDist = gamma,
    timescale: int = 0,
    fit_freq: str | None = None,
    fit_window: int = 0,
    prob_zero: bool = True,
    method: Literal["centroid", "median"] = "centroid",
    all_zero_policy: Literal["stagge", "wang"] = "stagge",
    fitting_policy: Literal["standard", "wang"] = "standard",
    small_sample_policy: Literal["strict", "augmented", "pseudo_observation_experimental"] = "strict",
    clip: tuple[float, float] | None = None,
    min_valid_fraction: float | None = None,
    min_valid_days: int | None = None,
) -> Series:
    """Method to compute the Standardized Precipitation Index.

    Parameters
    ----------
    series: pandas.Series
        Pandas time series of the precipitation. Time series index
        should be a pandas DatetimeIndex.
    dist: scipy.stats.rv_continuous
        Continuous probability distribution from scipy.stats.
        Gamma is recommended for standard SPI.
    timescale : int, optional, default=0
        Size of the moving window over which the series is summed. If zero, no
        summation is performed over the time series.
    fit_freq : str, optional, default=None
        Frequency for fitting the distribution. Default is None in which case
        the frequency of the series is inferred.
    fit_window : int, optional, default=0
        Window size for fitting data in fit_freq frequency's unit. Default is 0.
        When larger than zero, a rolling window is used to fit distributions.
    prob_zero : bool, default=True
        Option to apply zero-inflation adjustment following Stagge et al. (2013/2015).
    method : Literal["centroid", "median"], default="centroid"
        Standardization method:
        - "centroid": Classical SPI (Stagge et al., 2013).
        - "median": Modified SPI (M-SPI) per Gül & Güçlü (2025).
    all_zero_policy : Literal["stagge", "wang"], default="stagge"
        Behavior when all calibration observations are zero:
        - "stagge": centroid probability 0.5 resulting in SPI 0.0.
        - "wang": NaN output matching Wang et al. (2022) reference code.
    fitting_policy : Literal["standard", "wang"], default="standard"
        - "standard": Actual unaugmented observational data.
        - "wang": Adds min(positive_data)*0.01 for Gamma when zeros exist.
    small_sample_policy : Literal["strict", "augmented", "pseudo_observation_experimental"], default="strict"
        Policy for handling small positive samples (n_pos <= 3):
        - "strict": Strict baseline using only actual observational data.
        - "augmented": Augmented evaluation adding min*0.01 pseudo-observation.
    clip : tuple[float, float] or None, default=None
        Optional bounds on standardized SPI values (e.g. (-3.0, 3.0)).
        Defaults to None for unclipped SPI.
    min_valid_fraction : float or None, default=None
        Minimum fraction of valid days required per dasarian or month when fit_freq="dekad" or "monthly" on daily data.
        Default None uses strict completeness (1.0).
    min_valid_days : int or None, default=None
        Minimum number of valid daily observations required per dasarian or month. Supported for backward compatibility.

    Returns
    -------
    pandas.Series
    """

    spi_obj = SI(
        series=series,
        dist=dist,
        timescale=timescale,
        fit_freq=fit_freq,
        fit_window=fit_window,
        prob_zero=prob_zero,
        normal_scores_transform=False,
        agg_func="sum",
        method=method,
        all_zero_policy=all_zero_policy,
        fitting_policy=fitting_policy,
        small_sample_policy=small_sample_policy,
        clip=clip,
        min_valid_fraction=min_valid_fraction,
        min_valid_days=min_valid_days,
    )
    spi_obj.fit_distribution()
    return spi_obj.norm_ppf()


def spei(
    series: Series,
    dist: ContinuousDist = fisk,
    timescale: int = 0,
    fit_freq: str | None = None,
    fit_window: int = 0,
    prob_zero: bool = False,
    clip: tuple[float, float] | None = None,
) -> Series:
    """Method to compute the Standardized Precipitation Evaporation Index.

    Parameters
    ----------
    series: pandas.Series
        Pandas time series of climatic water balance (precipitation - PET).
    dist: scipy.stats.rv_continuous
        Continuous distribution (Fisk/log-logistic, GEV, PearsonIII, etc.).
    timescale : int, optional, default=0
        Rolling window size.
    fit_freq : str, optional, default=None
    fit_window : int, optional, default=0
    prob_zero : bool, default=False
        Should be False for signed water-balance data.
    clip : tuple[float, float] or None, default=None

    Returns
    -------
    pandas.Series
    """

    spei_obj = SI(
        series=series,
        dist=dist,
        timescale=timescale,
        fit_freq=fit_freq,
        fit_window=fit_window,
        prob_zero=prob_zero,
        normal_scores_transform=False,
        agg_func="sum",
        clip=clip,
    )
    spei_obj.fit_distribution()
    return spei_obj.norm_ppf()


def ssfi(
    series: Series,
    dist: ContinuousDist = genextreme,
    timescale: int = 0,
    fit_freq: str | None = None,
    fit_window: int = 0,
    prob_zero: bool = True,
    clip: tuple[float, float] | None = None,
) -> Series:
    """Method to compute the Standardized StreamFlow Index."""
    ssfi_obj = SI(
        series=series,
        dist=dist,
        timescale=timescale,
        fit_freq=fit_freq,
        fit_window=fit_window,
        prob_zero=prob_zero,
        normal_scores_transform=False,
        agg_func="mean",
        clip=clip,
    )
    ssfi_obj.fit_distribution()
    return ssfi_obj.norm_ppf()


def ssmi(
    series: Series,
    dist: ContinuousDist = beta,
    timescale: int = 0,
    fit_freq: str | None = None,
    fit_window: int = 0,
    prob_zero: bool = True,
    clip: tuple[float, float] | None = None,
) -> Series:
    """Method to compute the Standardized Soil Moisture Index."""
    ssmi_obj = SI(
        series=series,
        dist=dist,
        timescale=timescale,
        fit_freq=fit_freq,
        fit_window=fit_window,
        prob_zero=prob_zero,
        normal_scores_transform=False,
        agg_func="mean",
        clip=clip,
    )
    ssmi_obj.fit_distribution()
    return ssmi_obj.norm_ppf()


@dataclass
class SI:
    """Standardized Index Class."""

    series: Series = field(repr=False)
    dist: ContinuousDist
    timescale: int = 0
    fit_freq: str | None = field(default=None)
    fit_window: int = field(default=0)
    prob_zero: bool = field(default=False)
    normal_scores_transform: bool = field(default=False)
    agg_func: Literal["sum", "mean"] = "sum"
    method: Literal["centroid", "median"] = "centroid"
    all_zero_policy: Literal["stagge", "wang"] = "stagge"
    fitting_policy: Literal["standard", "wang"] = "standard"
    small_sample_policy: Literal["strict", "augmented", "pseudo_observation_experimental"] = "strict"
    clip: tuple[float, float] | None = None
    min_valid_fraction: float | None = field(default=None)
    min_valid_days: int | None = field(default=None)
    _grouped_year: DataFrame = field(init=False, repr=False, compare=False)
    _dist_dict: dict[Any, Dist] = field(
        default_factory=dict, init=False, repr=False, compare=False
    )
    _is_dasarian: bool = field(init=False, repr=False, default=False)
    _is_monthly: bool = field(init=False, repr=False, default=False)

    def __post_init__(self) -> None:
        """Post initializes the SI class and performs data validation and accumulation."""
        self.series = validate_series(self.series)
        is_das_req = str(self.fit_freq).lower() in ("dekad", "dasarian")
        is_das_labels = is_valid_dasarian_labels(self.series.index)
        is_das = is_dasarian_index(self.series.index)

        is_mon_req = str(self.fit_freq).lower() in ("monthly", "month")
        is_mon_labels = is_valid_monthly_labels(self.series.index)
        is_mon = is_monthly_index(self.series.index)

        # If dasarian/dekad frequency is explicitly requested:
        if is_das_req:
            if is_das_labels:
                # Pre-aggregated dasarian series (even if sparse/irregular)
                logging.info(
                    "Explicit fit_freq='%s' provided with valid dasarian calendar labels; treating as pre-aggregated dasarian series.",
                    self.fit_freq,
                )
                is_das = True
            else:
                # Daily observations: aggregate to dasarian totals
                logging.info(
                    "fit_freq='%s' requested on daily series; automatically aggregating to dasarian totals.",
                    self.fit_freq,
                )
                self.series = to_dasarian(
                    self.series,
                    min_valid_fraction=self.min_valid_fraction,
                    min_valid_days=self.min_valid_days,
                    agg_func=self.agg_func,
                )
                is_das = True
            self.fit_freq = "D"
            self._is_dasarian = True
            self._is_monthly = False
        elif is_mon_req:
            if is_mon_labels or is_mon:
                logging.info(
                    "Explicit fit_freq='%s' provided with valid monthly calendar labels; treating as pre-aggregated monthly series.",
                    self.fit_freq,
                )
                is_mon = True
            else:
                # Daily observations requested with monthly frequency
                if self.timescale == 0:
                    logging.info(
                        "fit_freq='%s' requested on daily pre-accumulated series (timescale=0); sampling month-end values.",
                        self.fit_freq,
                    )
                    start_month = pd.Timestamp(year=self.series.index.min().year, month=self.series.index.min().month, day=1)
                    end_month = pd.Timestamp(year=self.series.index.max().year, month=self.series.index.max().month, day=1)
                    labels = to_datetime(self.series.index.strftime("%Y-%m-01"))
                    self.series = self.series.groupby(labels).last()
                    canonical_idx = canonical_monthly_calendar(start_month, end_month)
                    self.series = self.series.reindex(canonical_idx)
                else:
                    logging.info(
                        "fit_freq='%s' requested on daily series; automatically aggregating to monthly totals.",
                        self.fit_freq,
                    )
                    self.series = to_monthly(
                        self.series,
                        min_valid_fraction=self.min_valid_fraction,
                        min_valid_days=self.min_valid_days,
                        agg_func=self.agg_func,
                    )
                is_mon = True
            self.fit_freq = "MS"
            self._is_dasarian = False
            self._is_monthly = True
        else:
            self._is_dasarian = is_das
            self._is_monthly = is_mon_labels or is_mon

        if self.fit_freq is None:
            if is_das:
                logging.info("Inferred dasarian (dekad) cadence; setting fit_freq to 'D'")
                inferred = "D"
            elif is_mon_labels or is_mon:
                logging.info("Inferred monthly cadence; setting fit_freq to 'MS'")
                inferred = "MS"
            else:
                inferred = infer_frequency(self.series.index)
                # If inference fell back to monthly because of missing days, check daily cadence
                if inferred in ("MS", "M") and len(self.series.index) > 2:
                    diffs = Series(self.series.index).diff().dropna()
                    if (diffs == Timedelta(days=1)).mean() > 0.5:
                        logging.info("Series has daily cadence with missing dates; setting fit_freq to 'D'")
                        inferred = "D"
            self.fit_freq = inferred
        elif is_das_req:
            self.fit_freq = "D"
        elif is_mon_req:
            self.fit_freq = "MS"

        # Rolling accumulation
        if self.timescale > 0:
            if is_das:
                self.series = (
                    rolling_dasarian(
                        self.series, timescale=self.timescale, agg_func=self.agg_func
                    )
                    .dropna()
                    .copy()
                )
            elif is_mon_req or (self._is_monthly and (is_mon_labels or is_mon)):
                self.series = (
                    rolling_monthly(
                        self.series, timescale=self.timescale, agg_func=self.agg_func
                    )
                    .dropna()
                    .copy()
                )
            else:
                if str(self.fit_freq).upper() == "D":
                    full_idx = DatetimeIndex(
                        pd.date_range(self.series.index.min(), self.series.index.max(), freq="D")
                    )
                    if len(full_idx) != len(self.series.index):
                        self.series = self.series.reindex(full_idx)
                self.series = (
                    self.series.rolling(self.timescale, min_periods=self.timescale)
                    .agg(self.agg_func)
                    .dropna()
                    .copy()
                )

        self._grouped_year = group_yearly_df(series=self.series)


        if self.fit_window > 0:
            if self.fit_window < 3:
                logging.error(
                    "Window should be larger than 2. Setting the window value to 3."
                )
                self.fit_window = 3
            elif self.fit_window % 2 == 0:
                logging.error(
                    f"Window should be odd. Setting the window value to {self.fit_window + 1}"
                )
                self.fit_window += 1

    def fit_distribution(self) -> None:
        """Fit distribution on the time series per fit_frequency and/or fit_window."""
        if self.normal_scores_transform:
            logging.info("Using normal-scores-transform. No distribution is fitted.")

        elif self.fit_window > 0:
            is_das = getattr(self, "_is_dasarian", False) or is_dasarian_index(self.series.index)
            if not is_das and self.fit_freq not in ("d", "w", "D", "W"):
                raise ValueError(
                    "Frequency fit_freq must be 'D' or 'W', not "
                    f"'{self.fit_freq}', if a fit_window is provided."
                )

            logging.info("Using rolling window method")
            window = self.fit_window
            half_window = window // 2

            if is_das:
                period = half_window
                dfval_window = dasarian_window_group_yearly_df(
                    dfval=self._grouped_year, period=period
                )
            elif self.fit_freq in ("W", "w"):
                period = Timedelta(value=half_window, unit="W").days
                window = period * 2 + 1
                dfval_window = daily_window_group_yearly_df(
                    dfval=self._grouped_year, period=period
                )
            else:
                period = half_window
                dfval_window = daily_window_group_yearly_df(
                    dfval=self._grouped_year, period=period
                )

            for dfval_rwindow in dfval_window.rolling(
                window=window, min_periods=window, closed="right"
            ):
                if len(dfval_rwindow) < window:
                    continue
                # For an odd window, the exact center element is at index period
                date = dfval_rwindow.index[period]
                data = get_data_series(dfval_rwindow.loc[[date]])
                data_window = get_data_series(dfval_rwindow)
                fd = Dist(
                    data=data,
                    dist=self.dist,
                    prob_zero=self.prob_zero,
                    data_window=data_window,
                    all_zero_policy=self.all_zero_policy,
                    fitting_policy=self.fitting_policy,
                    small_sample_policy=self.small_sample_policy,
                )
                self._dist_dict[date] = fd
        else:
            logging.info("Using groupby fit by frequency method")
            for date, grval in self._grouped_year.groupby(
                Grouper(freq=str(self.fit_freq))
            ):
                if grval.dropna(how="all").empty:
                    continue
                data = get_data_series(grval)
                fd = Dist(
                    data=data,
                    dist=self.dist,
                    prob_zero=self.prob_zero,
                    data_window=None,
                    all_zero_policy=self.all_zero_policy,
                    fitting_policy=self.fitting_policy,
                    small_sample_policy=self.small_sample_policy,
                )
                self._dist_dict[date] = fd

    def cdf(self) -> Series:
        """Compute the cumulative density function."""
        if self.normal_scores_transform:
            cdf = self.cdf_nsf()
        else:
            cdf = Series(nan, index=self.series.index, dtype=float)
            for k in self._dist_dict:
                cdf_k = self._dist_dict[k].cdf()
                cdf.loc[cdf_k.index] = cdf_k.values

        return cdf

    def pdf(self) -> Series:
        """Compute the probability density function."""
        if self.normal_scores_transform:
            pdf = self.cdf().diff()
        else:
            pdf = Series(nan, index=self.series.index, dtype=float)
            for k in self._dist_dict:
                pdf_k = self._dist_dict[k].pdf()
                pdf.loc[pdf_k.index] = pdf_k.values
        return pdf

    def cdf_nsf(self) -> Series:
        """Compute the cumulative density function using the Normal Scores Transform with tie handling."""
        logging.info("Using the normal scores transform")
        cdf = Series(nan, index=self.series.index, dtype=float)
        for _, grval in self._grouped_year.groupby(Grouper(freq=str(self.fit_freq))):
            data = get_data_series(grval)
            n = len(data)
            if n == 0:
                continue
            ranks = rankdata(data.values, method="average")
            cdf_vals = (ranks - 0.5) / n
            cdf.loc[data.index] = cdf_vals
        return cdf

    def ppf(self, q: float) -> Series:
        """Calculate the percentile point function."""
        ppf = Series(nan, index=self.series.index, dtype=float)
        if self.normal_scores_transform:
            cdf = self.cdf_nsf()
            for _, grval in self._grouped_year.groupby(
                Grouper(freq=str(self.fit_freq))
            ):
                data = get_data_series(grval).sort_values()
                cdf_i = cdf.loc[data.index]
                ppf.loc[data.index] = interp(
                    x=q,
                    xp=cdf_i.values.astype(float),
                    fp=data.values.astype(float),
                )
        else:
            for k in self._dist_dict:
                ppf_k = self._dist_dict[k].ppf(q=q)
                ppf.loc[ppf_k.index] = ppf_k.values
        return ppf

    def norm_ppf(self) -> Series:
        """Transform cumulative probabilities to standard normal values (SPI/SPEI)."""
        eps = 1e-15
        if self.method == "centroid":
            logging.info("Using centroid method for SPI calculation")
            cdf = self.cdf()
            clipped_cdf = np.clip(cdf.values, eps, 1.0 - eps)
            vals = norm.ppf(clipped_cdf, loc=0, scale=1)
            vals = np.where(np.isinf(vals), nan, vals)
            if self.clip is not None:
                vals = np.clip(vals, self.clip[0], self.clip[1])
            ppf = Series(vals, index=self.series.index, dtype=float)
        elif self.method == "median":
            logging.info("Using median method for M-SPI calculation (LOCAL shift factors per group)")
            ppf = Series(nan, index=self.series.index, dtype=float)
            for k in self._dist_dict:
                dist_obj = self._dist_dict[k]
                cdf_k = dist_obj.cdf()
                pos_data_local = dist_obj.data[dist_obj.data > 0.0]

                if len(pos_data_local) >= 2:
                    std_local = pos_data_local.std(ddof=1)
                    if std_local > 0:
                        sf_local = (pos_data_local.mean() - pos_data_local.median()) / std_local
                    else:
                        sf_local = 0.0
                else:
                    sf_local = 0.0

                clipped_k = np.clip(cdf_k.values, eps, 1.0 - eps)
                vals_k = norm.ppf(clipped_k, loc=0, scale=1) + sf_local
                vals_k = np.where(np.isinf(vals_k), nan, vals_k)
                if self.clip is not None:
                    vals_k = np.clip(vals_k, self.clip[0], self.clip[1])
                ppf.loc[cdf_k.index] = vals_k

        else:
            raise ValueError(
                f"Unknown method '{self.method}'. Must be one of: 'centroid', 'median'"
            )

        return ppf

    def get_dist(self, date: Timestamp) -> Dist:
        """Retrieve the fitted distribution object for a specific date."""
        for k in self._dist_dict:
            dist_obj = self._dist_dict[k]
            if date in dist_obj.data.index:
                return dist_obj

        raise KeyError("Date not found in distributions")

    def get_diagnostics(self) -> DataFrame:
        """Extract group-level calibration and fitting diagnostic records."""
        records = []
        for grp_key, dist_obj in self._dist_dict.items():
            cal_day = grp_key.strftime("%m-%d") if hasattr(grp_key, "strftime") else str(grp_key)
            pars_valid = bool(
                np.isfinite(dist_obj.loc)
                and np.isfinite(dist_obj.scale)
                and dist_obj.scale > 0
                and (dist_obj.pars is None or np.all(np.isfinite(dist_obj.pars)))
            )
            cdf_s = dist_obj.cdf()
            cdf_valid = bool(pars_valid and not cdf_s.dropna().empty and np.all(np.isfinite(cdf_s.dropna())))

            rec = {
                "timescale": f"{self.timescale}D" if self.timescale > 0 else "raw",
                "group_id": str(grp_key),
                "calendar_day": cal_day,
                "distribution": getattr(self.dist, "name", str(self.dist)),
                "n_raw": getattr(dist_obj, "n_valid", 0) + getattr(dist_obj, "n_missing", 0),
                "n_missing": getattr(dist_obj, "n_missing", 0),
                "n_valid": getattr(dist_obj, "n_valid", 0),
                "n_zero": getattr(dist_obj, "n_zero", 0),
                "n_positive": getattr(dist_obj, "n_positive", 0),
                "is_all_zero": getattr(dist_obj, "all_zero_group", False),
                "is_constant": bool(getattr(dist_obj, "fit_status", "") == "constant_sample"),
                "n_fitting": getattr(dist_obj, "n_fitting", 0),
                "pseudo_obs_added": getattr(dist_obj, "pseudo_obs_added", False),
                "fitting_policy": dist_obj.fitting_policy,
                "small_sample_policy": getattr(dist_obj, "small_sample_policy", "strict"),
                "init_method": getattr(dist_obj, "init_method", "none"),
                "fit_method": dist_obj.fit_method,
                "converged": dist_obj.converged,
                "negloglik": dist_obj.negloglik,
                "is_mle": getattr(dist_obj, "is_mle", False),
                "aic_comparable": getattr(dist_obj, "aic_comparable", False),
                "aic_incomparable_reason": getattr(
                    dist_obj, "aic_incomparable_reason", "none"
                ),
                "optimizer_attempts": getattr(dist_obj, "optimizer_attempts", 0),
                "optimizer_failed_attempts": getattr(
                    dist_obj, "optimizer_failed_attempts", 0
                ),
                "optimizer_nfev": getattr(dist_obj, "optimizer_nfev", 0),
                "optimization_seconds": getattr(dist_obj, "optimization_seconds", 0.0),
                "initialization_seconds": getattr(
                    dist_obj, "initialization_seconds", 0.0
                ),
                "scipy_initialization_seconds": getattr(
                    dist_obj, "scipy_initialization_seconds", 0.0
                ),
                "total_fit_seconds": getattr(dist_obj, "total_fit_seconds", 0.0),
                "fallback_used": getattr(dist_obj, "fallback_used", False),
                "parameters_valid": pars_valid,
                "cdf_valid": cdf_valid,
                "cdf_status": getattr(dist_obj, "cdf_status", "not_evaluated"),
                "cdf_failure_reason": getattr(dist_obj, "cdf_failure_reason", "none"),
                "fit_status": getattr(dist_obj, "fit_status", "none"),
                "small_sample_warning": getattr(dist_obj, "small_sample_warning", False),
            }
            records.append(rec)
        return DataFrame(records)

    def select_optimal_distribution(
        self,
        candidates: Any | None = None,
        *,
        prefer_two_parameters: bool = True,
        alpha: float = 0.05,
        delta_aic_threshold: float = 2.0,
        n_boot: int = 199,
        gof_scope: Literal["all", "competitive", "none"] = "competitive",
        random_state: int | None = 42,
        sw_clip: tuple[float, float] | None = None,
        all_zero_policy: Literal["stagge", "wang"] | None = None,
        small_sample_policy: Literal["strict", "augmented", "pseudo_observation_experimental"] = "strict",
        min_valid_group_fraction: float = 0.80,
        normality_ratio_threshold: float = 0.90,
        ranking_method: Literal["hierarchical", "consensus_rank"] = "hierarchical",
        information_criterion: Literal["AIC", "AICc"] = "AIC",
    ) -> dict[str, Any]:
        """Evaluate candidate distributions across calendar groups and recommend #1 and #2.

        Uses the same calendar grouping and rolling calibration window structure
        as SI.fit_distribution(). Does NOT mutate self.dist, self._dist_dict, or
        the SPI values generated by subsequent calls to si.spi(). ``AIC`` is the
        backward-compatible default; ``AICc`` uses the number of positive
        calibration observations and stays undefined when n_positive <= k + 1.
        """
        try:
            from . import model_selection
        except ImportError:
            import model_selection as model_selection_fallback

            model_selection = model_selection_fallback  # type: ignore[misc]

        groups: dict[Any, Any] = {}

        if self.fit_window > 0:
            is_das = getattr(self, "_is_dasarian", False) or is_dasarian_index(self.series.index)
            if not is_das and self.fit_freq not in ("d", "w", "D", "W"):
                raise ValueError(
                    "Frequency fit_freq must be 'D' or 'W', not "
                    f"'{self.fit_freq}', if a fit_window is provided."
                )

            window = self.fit_window
            half_window = window // 2

            if is_das:
                period = half_window
                dfval_window = dasarian_window_group_yearly_df(
                    dfval=self._grouped_year, period=period
                )
            elif self.fit_freq in ("W", "w"):
                period = Timedelta(value=half_window, unit="W").days
                window = period * 2 + 1
                dfval_window = daily_window_group_yearly_df(
                    dfval=self._grouped_year, period=period
                )
            else:
                period = half_window
                dfval_window = daily_window_group_yearly_df(
                    dfval=self._grouped_year, period=period
                )

            for dfval_rwindow in dfval_window.rolling(
                window=window, min_periods=window, closed="right"
            ):
                if len(dfval_rwindow) < window:
                    continue
                date = dfval_rwindow.index[period]
                data = get_data_series(dfval_rwindow.loc[[date]])
                data_window = get_data_series(dfval_rwindow)
                groups[date] = (data, data_window)
        else:
            for date, grval in self._grouped_year.groupby(
                Grouper(freq=str(self.fit_freq))
            ):
                if grval.dropna(how="all").empty:
                    continue
                data = get_data_series(grval)
                groups[date] = data

        az_policy = all_zero_policy if all_zero_policy is not None else self.all_zero_policy
        res = model_selection.select_models_by_group(
            groups=groups,
            candidates=candidates,
            prob_zero=self.prob_zero,
            alpha=alpha,
            delta_aic_threshold=delta_aic_threshold,
            prefer_two_parameters=prefer_two_parameters,
            n_boot=n_boot,
            gof_scope=gof_scope,
            min_bootstrap_success=0.80,
            random_state=random_state,
            sw_clip=sw_clip,
            all_zero_policy=az_policy,
            fitting_policy=self.fitting_policy,
            small_sample_policy=small_sample_policy,
            min_valid_group_fraction=min_valid_group_fraction,
            normality_ratio_threshold=normality_ratio_threshold,
            ranking_method=ranking_method,
            information_criterion=information_criterion,
        )

        return {
            "best_distribution": res["best_distribution"],
            "alternative_distribution": res["alternative_distribution"],
            "selection_status": res["best_selection_status"],
            "best_selection_status": res["best_selection_status"],
            "alternative_selection_status": res["alternative_selection_status"],
            "candidate_summary": res["candidate_summary"],
            "global_ranking": res["global_ranking"],
            "recommendations": res["recommendations"],
            "details": res["details"],
            "normality_target_met_by_any_candidate": res["normality_target_met_by_any_candidate"],
            "selection_reason": res["selection_reason"],
            "ranking_method": res["ranking_method"],
            "ranking_results": res["ranking_results"],
            "ranking_comparison": res["ranking_comparison"],
            "agreement_summary": res["agreement_summary"],
            "information_criterion": res["information_criterion"],
        }


def generate_nan_diagnostic_summary(diagnostics_df: DataFrame) -> DataFrame:
    """Aggregate group-level diagnostics by timescale and candidate distribution."""
    if diagnostics_df.empty:
        return DataFrame(columns=[
            "timescale", "distribution", "n_groups", "n_success", "n_nan",
            "n_all_zero", "n_constant", "n_insufficient_sample",
            "n_optimizer_failed", "n_invalid_parameter", "n_invalid_cdf",
            "n_other_failure", "nan_percentage"
        ])

    rows = []
    for (t_scale, dist_name), grp in diagnostics_df.groupby(["timescale", "distribution"], sort=False):
        n_groups = len(grp)
        n_all_zero = int((grp["fit_status"] == "all_zero").sum())
        n_constant = int((grp["fit_status"] == "constant_sample").sum())
        n_insufficient = int(grp["fit_status"].isin([
            "insufficient_sample",
            "insufficient_positive_sample",
            "insufficient_effective_sample",
        ]).sum())
        n_opt_failed = int((grp["fit_status"] == "optimizer_failed").sum())
        n_inv_param = int((grp["fit_status"] == "invalid_parameters").sum())
        n_inv_cdf = int((grp["fit_status"] == "conditional_cdf_invalid").sum())

        # Success means fit_status == "success" and parameters and CDF are valid
        n_success = int((
            (grp["fit_status"] == "success") & grp["parameters_valid"] & grp["cdf_valid"]
        ).sum())
        n_nan = n_groups - n_success
        n_other = n_nan - (n_all_zero + n_constant + n_insufficient + n_opt_failed + n_inv_param + n_inv_cdf)

        nan_pct = float(100.0 * n_nan / n_groups) if n_groups > 0 else 0.0

        rows.append({
            "timescale": str(t_scale),
            "distribution": str(dist_name),
            "n_groups": n_groups,
            "n_success": n_success,
            "n_nan": n_nan,
            "n_all_zero": n_all_zero,
            "n_constant": n_constant,
            "n_insufficient_sample": n_insufficient,
            "n_optimizer_failed": n_opt_failed,
            "n_invalid_parameter": n_inv_param,
            "n_invalid_cdf": n_inv_cdf,
            "n_other_failure": max(n_other, 0),
            "nan_percentage": nan_pct,
        })
    return DataFrame(rows)
