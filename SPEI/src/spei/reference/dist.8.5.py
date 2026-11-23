"""
Distribution fitting module for drought indices calculation.

This module implements robust parameter estimation and goodness-of-fit evaluation
for probability distributions used in drought index calculations (SPI, SPEI, SGI,
SSFI, SSMI).

SCIENTIFIC FOUNDATIONS
======================

The implementation incorporates methodologies from:
1. Stagge, J.H., L.M. Tallaksen, L. Gudmundsson, A.F. Van Loon, and K. Stahl (2015):
   "Candidate Distributions for Climatological Drought Indices (SPI and SPEI)"
   International Journal of Climatology, 35(13), 4027-4040. DOI: 10.1002/joc.4267.
   - Weibull plotting-position zero mass and centroid formula.
   - Truncated/conditional distribution for positive precipitation: F(x|X>0) = (F(x) - F(0))/(1 - F(0)).
   - Parametric-bootstrap goodness-of-fit tests (Kolmogorov-Smirnov and Anderson-Darling).
   - Shapiro-Wilk test on transformed SPI with N(0,1) replacement for discrete zero mass.

2. Wang, H., Y. Liu, H. Jiao, S. Ouyang, X. Li, Z. Qin, H. Zhang, S. Shen, and J. Hao (2022):
   "An improved daily standardized precipitation index dataset for mainland China from 1961 to 2018"
   Scientific Data, 9, 201. DOI: 10.1038/s41597-022-01201-z.
   - Daily SPI calculation with Gamma distribution.
   - Zero probability estimation and small-value pseudo-observation handling.

3. Vonk, M. A. (2025):
   "SPEI: A Python package for calculating and visualizing drought indices"
   Journal of Open Source Software, 10(111), 8454. DOI: 10.21105/joss.08454.
   - Core package architecture and interface.

ZERO-INFLATION & MIXED DISTRIBUTION MODEL
=========================================

For zero-inflated variables like accumulated precipitation, the mixed cumulative
distribution function H(x) is defined as:

    H(x) = p_zero_centroid                          if x == 0
    H(x) = p_zero_mass + (1 - p_zero_mass) * F_pos(x)  if x > 0

where for n valid calibration observations and m zero observations:
    p_zero_mass     = m / (n + 1)
    p_zero_centroid = (m + 1) / (2 * (n + 1))

Notice that p_zero_mass is the discrete probability mass assigned to zero in the
mixture model, whereas p_zero_centroid is the plotting-position centroid assigned
to exact-zero observations to place them at the midpoint of the zero mass interval
[0, p_zero_mass]. They are strictly distinct quantities.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import logging
from typing import Any, Literal
import warnings

import numpy as np
import pandas as pd
from pandas import Series
from scipy import optimize
from scipy.special import gamma as gamma_func
from scipy.stats import gamma as gamma_dist, norm, shapiro, skew

from ._typing import ContinuousDist

try:
    from lmoments3 import distr as lm_distr
except ImportError:
    lm_distr = None
    logging.warning("lmoments3 not found. L-moment fitting will not be available.")

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
if not logger.handlers:
    handler = logging.StreamHandler()
    formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
    handler.setFormatter(formatter)
    logger.addHandler(handler)


# -----------------------------------------------------------------------------
# Negative Log-Likelihood Helper Functions
# -----------------------------------------------------------------------------

def _gamma_negloglik(params: tuple[float, float], data: np.ndarray) -> float:
    a, scale = params
    if a <= 0.0 or scale <= 0.0:
        return np.inf
    from scipy.stats import gamma
    ll = np.sum(gamma.logpdf(data, a=a, loc=0.0, scale=scale))
    return -float(ll) if np.isfinite(ll) else np.inf


def _weibull_negloglik(params: tuple[float, float], data: np.ndarray) -> float:
    c, scale = params
    if c <= 0.0 or scale <= 0.0:
        return np.inf
    from scipy.stats import weibull_min
    ll = np.sum(weibull_min.logpdf(data, c=c, loc=0.0, scale=scale))
    return -float(ll) if np.isfinite(ll) else np.inf


def _lognorm_negloglik(params: tuple[float, float], data: np.ndarray) -> float:
    s, scale = params
    if s <= 0.0 or scale <= 0.0:
        return np.inf
    from scipy.stats import lognorm
    ll = np.sum(lognorm.logpdf(data, s=s, loc=0.0, scale=scale))
    return -float(ll) if np.isfinite(ll) else np.inf


def _fisk_negloglik(params: tuple[float, float], data: np.ndarray) -> float:
    c, scale = params
    if c <= 0.0 or scale <= 0.0:
        return np.inf
    from scipy.stats import fisk
    ll = np.sum(fisk.logpdf(data, c=c, loc=0.0, scale=scale))
    return -float(ll) if np.isfinite(ll) else np.inf


def _gumbel_negloglik(
    params: tuple[float, float],
    data: np.ndarray,
    conditional_positive: bool = False,
) -> float:
    loc, scale = params
    if scale <= 0.0:
        return np.inf
    from scipy.stats import gumbel_r
    logpdf_vals = gumbel_r.logpdf(data, loc=loc, scale=scale)
    if not np.all(np.isfinite(logpdf_vals)):
        return np.inf
    ll = float(np.sum(logpdf_vals))
    if conditional_positive:
        logsf0 = float(gumbel_r.logsf(0.0, loc=loc, scale=scale))
        if not np.isfinite(logsf0) or logsf0 >= 0.0:
            return np.inf
        ll -= len(data) * logsf0
    return -ll if np.isfinite(ll) else np.inf


def _pearson3_negloglik(
    params: tuple[float, float, float],
    data: np.ndarray,
    conditional_positive: bool = False,
) -> float:
    skew_val, loc, scale = params
    if scale <= 0.0:
        return np.inf
    from scipy.stats import pearson3
    logpdf_vals = pearson3.logpdf(data, skew_val, loc=loc, scale=scale)
    if not np.all(np.isfinite(logpdf_vals)):
        return np.inf
    ll = float(np.sum(logpdf_vals))
    if conditional_positive:
        logsf0 = float(pearson3.logsf(0.0, skew_val, loc=loc, scale=scale))
        if not np.isfinite(logsf0) or logsf0 >= 0.0:
            return np.inf
        ll -= len(data) * logsf0
    return -ll if np.isfinite(ll) else np.inf


def _gev_negloglik(
    params: tuple[float, float, float],
    data: np.ndarray,
    conditional_positive: bool = False,
) -> float:
    c, loc, scale = params
    if scale <= 0.0:
        return np.inf
    # SciPy genextreme parameterization check for support: 1 - c * (x - loc) / scale > 0
    if abs(c) > 1e-12:
        support_arg = 1.0 - c * (data - loc) / scale
        if np.any(support_arg <= 0.0):
            return np.inf
    from scipy.stats import genextreme
    logpdf_vals = genextreme.logpdf(data, c, loc=loc, scale=scale)
    if not np.all(np.isfinite(logpdf_vals)):
        return np.inf
    ll = float(np.sum(logpdf_vals))
    if conditional_positive:
        logsf0 = float(genextreme.logsf(0.0, c, loc=loc, scale=scale))
        if not np.isfinite(logsf0) or logsf0 >= 0.0:
            return np.inf
        ll -= len(data) * logsf0
    return -ll if np.isfinite(ll) else np.inf


# -----------------------------------------------------------------------------
# Method of Moments Helper Functions
# -----------------------------------------------------------------------------

def estimate_weibull_moments(data: np.ndarray) -> tuple[float, float]:
    """Estimate two-parameter Weibull (c, scale) with loc=0 via Method of Moments."""
    from scipy.optimize import root_scalar
    mean = float(np.mean(data))
    var = float(np.var(data, ddof=1))
    if mean <= 0.0 or var <= 0.0:
        return 1.0, max(float(np.std(data, ddof=1)), 1.0)
    r = var / (mean**2)

    def func(k: float) -> float:
        return (gamma_func(1.0 + 2.0 / k) / (gamma_func(1.0 + 1.0 / k) ** 2)) - 1.0 - r

    try:
        sol = root_scalar(func, bracket=[0.2, 20.0], method="brentq")
        c = float(sol.root)
    except Exception:
        c = 1.0
    scale = float(mean / gamma_func(1.0 + 1.0 / c))
    return c, max(scale, 1e-6)


def estimate_gumbel_moments(data: np.ndarray) -> tuple[float, float]:
    """Estimate Gumbel right parameters (loc, scale) via Method of Moments."""
    mean = float(np.mean(data))
    std = float(np.std(data, ddof=1))
    euler_mascheroni = 0.57721566490153286
    scale = max(float(std * np.sqrt(6.0) / np.pi), 1e-6)
    loc = float(mean - euler_mascheroni * scale)
    return loc, scale


def estimate_pearson3_moments(data: np.ndarray) -> tuple[float, float, float]:
    """Estimate Pearson III parameters (skew, loc, scale) via Method of Moments.

    In SciPy's pearson3 parameterization:
        Mean = loc
        Std  = scale
        Skew = skew
    """
    mean = float(np.mean(data))
    std = max(float(np.std(data, ddof=1)), 1e-6)
    sample_skew = float(skew(data, bias=False))
    if not np.isfinite(sample_skew) or abs(sample_skew) < 1e-6:
        sample_skew = 1e-5 if sample_skew >= 0 else -1e-5
    return sample_skew, mean, std


def estimate_lognorm_moments(data: np.ndarray) -> tuple[float, float]:
    """Estimate two-parameter Lognormal (shape=sigma, scale=exp(mu)) with loc=0."""
    mean = float(np.mean(data))
    var = float(np.var(data, ddof=1))
    if mean <= 0.0 or var <= 0.0:
        return 1.0, 1.0
    sigma2 = np.log1p(var / (mean**2))
    sigma = float(np.sqrt(max(sigma2, 1e-6)))
    mu = float(np.log(mean) - 0.5 * sigma2)
    scale = float(np.exp(mu))
    return sigma, max(scale, 1e-6)


def estimate_fisk_moments(data: np.ndarray) -> tuple[float, float]:
    """Estimate two-parameter Fisk (shape=c, scale=s) with loc=0 via Method of Moments."""
    from scipy.optimize import root_scalar
    mean = float(np.mean(data))
    var = float(np.var(data, ddof=1))
    if mean <= 0.0 or var <= 0.0:
        return 2.5, 1.0

    def func(c: float) -> float:
        if c <= 2.01:
            return 1e6
        term1 = (2.0 * np.pi / c) / np.sin(2.0 * np.pi / c)
        term2 = ((np.pi / c) / np.sin(np.pi / c)) ** 2
        return (term1 - term2) - (var / (mean**2))

    try:
        sol = root_scalar(func, bracket=[2.05, 50.0], method="brentq")
        c = float(sol.root)
    except Exception:
        c = 3.0
    scale = float(mean * np.sin(np.pi / c) * c / np.pi)
    return c, max(scale, 1e-6)


def estimate_gev_moments(data: np.ndarray) -> tuple[float, float, float]:
    """Estimate GEV parameters (c, loc, scale) matching SciPy's genextreme convention."""
    from scipy.optimize import root_scalar
    mean = float(np.mean(data))
    var = float(np.var(data, ddof=1))
    std = float(np.std(data, ddof=1))
    sample_skew = float(skew(data, bias=False))

    def skewness_func(k: float) -> float:
        num = (
            gamma_func(1.0 - 3.0 * k)
            - 3.0 * gamma_func(1.0 - k) * gamma_func(1.0 - 2.0 * k)
            + 2.0 * (gamma_func(1.0 - k) ** 3)
        )
        den = (gamma_func(1.0 - 2.0 * k) - gamma_func(1.0 - k) ** 2) ** 1.5
        return num / den

    def objective(k: float) -> float:
        return skewness_func(k) - sample_skew

    c_est = 0.0
    try:
        sol = root_scalar(objective, bracket=[-0.3, 0.3], method="brentq")
        k_sol = float(sol.root)
        c_est = -k_sol  # SciPy c = -k
    except Exception:
        c_est = -0.1 if sample_skew > 0 else 0.1

    k = -c_est
    try:
        denom = gamma_func(1.0 - 2.0 * k) - gamma_func(1.0 - k) ** 2
        if denom > 0:
            scale_est = abs(k) * np.sqrt(var / denom)
            loc_est = mean - (scale_est / k) * (gamma_func(1.0 - k) - 1.0)
        else:
            raise ValueError
    except Exception:
        scale_est = max(float(std * np.sqrt(6.0) / np.pi), 1e-6)
        loc_est = float(mean - 0.5772156649 * scale_est)
        c_est = 0.0

    return float(c_est), float(loc_est), max(float(scale_est), 1e-6)


# -----------------------------------------------------------------------------
# Shapiro-Wilk Rejection Frequency Utility
# -----------------------------------------------------------------------------

def shapiro_wilk_rejection_frequency(p_values: Any, alpha: float = 0.05) -> dict:
    """Summarize Shapiro-Wilk rejection frequency across independently tested SPI groups."""
    if not 0.0 < alpha < 1.0:
        raise ValueError("alpha must be between 0 and 1")

    values = np.asarray(
        list(p_values) if not isinstance(p_values, np.ndarray) else p_values,
        dtype=float,
    ).ravel()
    values = values[np.isfinite(values)]
    n_tested = int(values.size)
    n_rejected = int(np.sum(values < alpha))
    return {
        "alpha": float(alpha),
        "n_tested": n_tested,
        "n_rejected": n_rejected,
        "rejection_frequency": float(n_rejected / n_tested) if n_tested else np.nan,
        "rejection_frequency_pct": float(100.0 * n_rejected / n_tested) if n_tested else np.nan,
    }


# -----------------------------------------------------------------------------
# Fitting Helpers: Wang Gamma and Standard Multi-Distribution Estimation
# -----------------------------------------------------------------------------

def _fit_wang_gamma(
    arr: np.ndarray,
    prob_zero: bool,
    all_zero_policy: Literal["stagge", "wang"],
    n_raw: int,
    n_missing: int,
) -> tuple[list[float] | None, float, float, float, dict[str, Any]]:
    """Fit Gamma distribution according to exact Wang et al. (2022) logic.

    Reproduces all 6 branches of fit_gamma_para in utilsPY.py:
    1. Empty calibration group -> NaN
    2. Constant sample -> NaN
    3. All zero calibration group -> NaN (under all_zero_policy='wang')
    4. Zeros exist and n_pos > 3 -> add min*0.01 pseudo-observation, L-moments init + Nelder-Mead MLE
    5. No zeros (m == 0) -> L-moments init + Nelder-Mead MLE
    6. Zeros exist and 1 <= n_pos <= 3 -> add min*0.01 pseudo-observation, MoM init + Nelder-Mead MLE
    """
    n = arr.size
    if n == 0:
        details = {
            "fit_status": "insufficient_effective_sample",
            "fit_method": "none",
            "init_method": "none",
            "converged": False,
            "negloglik": np.nan,
            "n_raw": n_raw,
            "n_missing": n_missing,
            "n_valid": 0,
            "n_zero": 0,
            "n_positive": 0,
            "n_fitting": 0,
            "pseudo_obs_added": False,
            "small_sample_warning": False,
            "is_all_zero": False,
            "is_constant": False,
        }
        return None, np.nan, np.nan, 0.0, details

    if prob_zero:
        if np.any(arr < -1e-6):
            raise ValueError(
                f"Precipitation data must be non-negative; min={np.min(arr)}"
            )
        arr = np.where((arr < 0.0) & (arr >= -1e-6), 0.0, arr)
        m = int(np.sum(arr == 0.0))
        n_pos = n - m
        p_zero_mass = float(m / (n + 1.0))
        pos_data = arr[arr > 0.0]

        if n_pos == 0:
            p0_out = np.nan if all_zero_policy == "wang" else p_zero_mass
            details = {
                "fit_status": "all_zero",
                "fit_method": "all_zero",
                "init_method": "none",
                "converged": False,
                "negloglik": np.nan,
                "n_raw": n_raw,
                "n_missing": n_missing,
                "n_valid": n,
                "n_zero": m,
                "n_positive": 0,
                "n_fitting": 0,
                "pseudo_obs_added": False,
                "small_sample_warning": False,
                "is_all_zero": True,
                "is_constant": False,
            }
            return None, np.nan, np.nan, p0_out, details
    else:
        m = 0
        n_pos = n
        p_zero_mass = 0.0
        pos_data = arr

    # Constant sample check
    if pos_data.size > 1 and (float(np.max(pos_data)) - float(np.min(pos_data))) <= 1e-12:
        details = {
            "fit_status": "constant_sample",
            "fit_method": "constant_sample",
            "init_method": "none",
            "converged": False,
            "negloglik": np.nan,
            "n_raw": n_raw,
            "n_missing": n_missing,
            "n_valid": n,
            "n_zero": m,
            "n_positive": n_pos,
            "n_fitting": pos_data.size,
            "pseudo_obs_added": False,
            "small_sample_warning": False,
            "is_all_zero": False,
            "is_constant": True,
        }
        return None, np.nan, np.nan, p_zero_mass, details

    pseudo_obs_added = False
    small_sample_warning = False
    init_method = "none"

    if prob_zero and m > 0:
        now = np.append(pos_data, float(np.min(pos_data)) * 0.01)
        pseudo_obs_added = True
        mean_val = float(np.mean(now))
        var_val = float(np.var(now))  # ddof=0 per Wang utilsPY.py
        shape_guess = float(mean_val ** 2 / var_val) if var_val > 0 else 1.0
        rate_guess = float(mean_val / var_val) if var_val > 0 else 1.0
        if n_pos > 3:
            # Wang branch 3: zeros exist, n_pos > 3 -> L-moments
            init_method = "lmoments"
            if lm_distr is not None and hasattr(lm_distr, "gam"):
                try:
                    lm_pars = lm_distr.gam.lmom_fit(now)
                    x0 = np.asarray([float(lm_pars["a"]), float(lm_pars["scale"])])
                except Exception:
                    x0 = np.asarray([max(shape_guess, 0.1), max(var_val / mean_val if mean_val > 0 else 1.0, 1e-6)])
                    init_method = "wang_moments"
            else:
                x0 = np.asarray([max(shape_guess, 0.1), max(var_val / mean_val if mean_val > 0 else 1.0, 1e-6)])
                init_method = "wang_moments"
        else:
            # Wang branch 5: zeros exist, 1 <= n_pos <= 3 -> Method of Moments
            init_method = "wang_moments"
            small_sample_warning = True
            x0 = np.asarray([shape_guess, rate_guess])
    else:
        # Wang branch 4: no zeros
        if pos_data.size < 2:
            details = {
                "fit_status": "insufficient_positive_sample" if prob_zero else "insufficient_effective_sample",
                "fit_method": "none",
                "init_method": "none",
                "converged": False,
                "negloglik": np.nan,
                "n_raw": n_raw,
                "n_missing": n_missing,
                "n_valid": n,
                "n_zero": 0,
                "n_positive": n_pos,
                "n_fitting": pos_data.size,
                "pseudo_obs_added": False,
                "small_sample_warning": True,
                "is_all_zero": False,
                "is_constant": False,
            }
            return None, np.nan, np.nan, p_zero_mass, details

        now = pos_data
        mean_val = float(np.mean(now))
        var_val = max(float(np.var(now)), 1e-6)
        mean_val = max(mean_val, 1e-6)
        shape_guess = float(mean_val ** 2 / var_val)
        rate_guess = float(mean_val / var_val)
        init_method = "lmoments"
        if lm_distr is not None and hasattr(lm_distr, "gam") and now.size >= 4:
            try:
                lm_pars = lm_distr.gam.lmom_fit(now)
                x0 = np.asarray([float(lm_pars["a"]), float(lm_pars["scale"])])
            except Exception:
                x0 = np.asarray([max(shape_guess, 0.1), max(var_val / mean_val, 1e-6)])
                init_method = "wang_moments"
        else:
            x0 = np.asarray([max(shape_guess, 0.1), max(var_val / mean_val, 1e-6)])
            init_method = "wang_moments"

    # Nelder-Mead MLE Optimization
    def _obj_wang(x):
        if x[0] <= 0.0 or x[1] <= 0.0:
            return 1e12
        lp = gamma_dist.logpdf(now, a=x[0], scale=x[1])
        return -float(np.sum(lp)) if np.all(np.isfinite(lp)) else 1e12

    with np.errstate(all="ignore"), warnings.catch_warnings():
        warnings.filterwarnings("ignore", category=RuntimeWarning)
        res = optimize.minimize(_obj_wang, x0=x0, method="Nelder-Mead")

    if res.success and res.x[0] > 0 and res.x[1] > 0 and np.isfinite(res.fun):
        fitted_pars = [float(res.x[0])]
        fitted_loc = 0.0
        fitted_scale = float(res.x[1])
        fit_method = "mle_wang_nelder_mead"
        converged = True
        negloglik = float(res.fun)
        fit_status = "success"
    else:
        # Fallback following Wang's procedure
        if init_method == "wang_moments":
            scale_fb = float(var_val / mean_val) if mean_val > 0 and var_val > 0 else 1.0
            shape_fb = float(shape_guess) if shape_guess > 0 else 1.0
            fitted_pars = [shape_fb]
            fitted_loc = 0.0
            fitted_scale = scale_fb
            fit_method = "wang_moments_fallback"
            converged = False
            negloglik = float(_obj_wang((shape_fb, scale_fb)))
            fit_status = "success"
        elif init_method == "lmoments" and x0[0] > 0 and x0[1] > 0:
            fitted_pars = [float(x0[0])]
            fitted_loc = 0.0
            fitted_scale = float(x0[1])
            fit_method = "wang_lmoments_fallback"
            converged = False
            negloglik = float(_obj_wang((x0[0], x0[1])))
            fit_status = "success"
        else:
            fitted_pars = None
            fitted_loc = np.nan
            fitted_scale = np.nan
            fit_method = "none"
            converged = False
            negloglik = np.nan
            fit_status = "optimizer_failed"

    details = {
        "fit_status": fit_status,
        "fit_method": fit_method,
        "init_method": init_method,
        "converged": converged,
        "negloglik": negloglik,
        "n_raw": n_raw,
        "n_missing": n_missing,
        "n_valid": n,
        "n_zero": m,
        "n_positive": n_pos,
        "n_fitting": int(now.size),
        "pseudo_obs_added": pseudo_obs_added,
        "small_sample_warning": small_sample_warning,
        "is_all_zero": False,
        "is_constant": False,
    }
    return fitted_pars, fitted_loc, fitted_scale, p_zero_mass, details


def _fit_standard_dist(
    arr: np.ndarray,
    dist: ContinuousDist,
    prob_zero: bool,
    conditional_positive: bool,
    all_zero_policy: Literal["stagge", "wang"],
    n_raw: int,
    n_missing: int,
) -> tuple[list[float] | None, float, float, float, dict[str, Any]]:
    """Fit a probability distribution using multi-stage parameter estimation."""
    n = arr.size
    if n == 0:
        details = {
            "fit_status": "insufficient_effective_sample",
            "fit_method": "none",
            "init_method": "none",
            "converged": False,
            "negloglik": np.nan,
            "n_raw": n_raw,
            "n_missing": n_missing,
            "n_valid": 0,
            "n_zero": 0,
            "n_positive": 0,
            "n_fitting": 0,
            "pseudo_obs_added": False,
            "small_sample_warning": False,
            "is_all_zero": False,
            "is_constant": False,
        }
        return None, np.nan, np.nan, 0.0, details

    if prob_zero:
        if np.any(arr < -1e-6):
            raise ValueError(
                f"Precipitation data must be non-negative; min={np.min(arr)}"
            )
        arr = np.where((arr < 0.0) & (arr >= -1e-6), 0.0, arr)
        m = int(np.sum(arr == 0.0))
        n_pos = n - m
        p_zero_mass = float(m / (n + 1.0))
        pos_data = arr[arr > 0.0]

        if n_pos == 0:
            p0_out = np.nan if all_zero_policy == "wang" else p_zero_mass
            details = {
                "fit_status": "all_zero",
                "fit_method": "all_zero",
                "init_method": "none",
                "converged": False,
                "negloglik": np.nan,
                "n_raw": n_raw,
                "n_missing": n_missing,
                "n_valid": n,
                "n_zero": m,
                "n_positive": 0,
                "n_fitting": 0,
                "pseudo_obs_added": False,
                "small_sample_warning": False,
                "is_all_zero": True,
                "is_constant": False,
            }
            return None, np.nan, np.nan, p0_out, details
    else:
        m = 0
        n_pos = n
        p_zero_mass = 0.0
        pos_data = arr

    data_for_fitting = pos_data
    name = getattr(dist, "name", None)

    # Constant sample check
    if data_for_fitting.size > 1 and (float(np.max(data_for_fitting)) - float(np.min(data_for_fitting))) <= 1e-12:
        details = {
            "fit_status": "constant_sample",
            "fit_method": "constant_sample",
            "init_method": "none",
            "converged": False,
            "negloglik": np.nan,
            "n_raw": n_raw,
            "n_missing": n_missing,
            "n_valid": n,
            "n_zero": m,
            "n_positive": n_pos,
            "n_fitting": data_for_fitting.size,
            "pseudo_obs_added": False,
            "small_sample_warning": False,
            "is_all_zero": False,
            "is_constant": True,
        }
        return None, np.nan, np.nan, p_zero_mass, details

    # Distribution-specific minimum sample size
    min_sample_size = 3 if name in ["pearson3", "genextreme"] else 2
    if data_for_fitting.size < min_sample_size:
        status = "insufficient_positive_sample" if prob_zero else "insufficient_effective_sample"
        details = {
            "fit_status": status,
            "fit_method": "none",
            "init_method": "none",
            "converged": False,
            "negloglik": np.nan,
            "n_raw": n_raw,
            "n_missing": n_missing,
            "n_valid": n,
            "n_zero": m,
            "n_positive": n_pos,
            "n_fitting": data_for_fitting.size,
            "pseudo_obs_added": False,
            "small_sample_warning": bool(n_pos <= 3),
            "is_all_zero": False,
            "is_constant": False,
        }
        return None, np.nan, np.nan, p_zero_mass, details

    initial_params = None
    init_method = "none"

    if lm_distr is not None and data_for_fitting.size >= 4:
        lm_map = {
            "gamma": "gam",
            "weibull_min": "wei",
            "gumbel_r": "gum",
            "pearson3": "pe3",
            "genextreme": "gev",
        }
        lm_name = lm_map.get(name, None)
        if lm_name is not None and hasattr(lm_distr, lm_name):
            try:
                lm_func = getattr(lm_distr, lm_name)
                lm_pars = lm_func.lmom_fit(data_for_fitting)
                if name == "gamma" and lm_pars["a"] > 0 and lm_pars["scale"] > 0:
                    initial_params = np.asarray([float(lm_pars["a"]), float(lm_pars["scale"])])
                    init_method = "lmoments"
                elif name == "weibull_min" and lm_pars["c"] > 0 and lm_pars["scale"] > 0:
                    initial_params = np.asarray([float(lm_pars["c"]), float(lm_pars["scale"])])
                    init_method = "lmoments"
                elif name == "gumbel_r" and lm_pars["scale"] > 0:
                    initial_params = np.asarray([float(lm_pars["loc"]), float(lm_pars["scale"])])
                    init_method = "lmoments"
                elif name == "pearson3" and lm_pars["scale"] > 0:
                    initial_params = np.asarray([float(lm_pars["skew"]), float(lm_pars["loc"]), float(lm_pars["scale"])])
                    init_method = "lmoments"
                elif name == "genextreme" and lm_pars["scale"] > 0:
                    initial_params = np.asarray([float(lm_pars["c"]), float(lm_pars["loc"]), float(lm_pars["scale"])])
                    init_method = "lmoments"
            except Exception as e:
                logger.debug("L-moment initialization failed for %s: %s", name, e)
                initial_params = None

    if initial_params is None:
        if name == "gamma":
            m1 = float(np.mean(data_for_fitting))
            v1 = float(np.var(data_for_fitting, ddof=1))
            a0 = (m1 * m1 / v1) if v1 > 0 else 1.0
            scale0 = (v1 / m1) if m1 > 0 else 1.0
            initial_params = np.asarray([max(a0, 0.1), max(scale0, 1e-6)])
            init_method = "moments"
        elif name == "weibull_min":
            c0, scale0 = estimate_weibull_moments(data_for_fitting)
            initial_params = np.asarray([c0, scale0])
            init_method = "moments"
        elif name == "lognorm":
            s0, scale0 = estimate_lognorm_moments(data_for_fitting)
            initial_params = np.asarray([s0, scale0])
            init_method = "moments"
        elif name == "fisk":
            c0, scale0 = estimate_fisk_moments(data_for_fitting)
            initial_params = np.asarray([c0, scale0])
            init_method = "moments"
        elif name == "gumbel_r":
            loc0, scale0 = estimate_gumbel_moments(data_for_fitting)
            initial_params = np.asarray([loc0, scale0])
            init_method = "moments"
        elif name == "pearson3":
            skew0, loc0, scale0 = estimate_pearson3_moments(data_for_fitting)
            initial_params = np.asarray([skew0, loc0, scale0])
            init_method = "moments"
        elif name == "genextreme":
            c0, loc0, scale0 = estimate_gev_moments(data_for_fitting)
            initial_params = np.asarray([c0, loc0, scale0])
            init_method = "moments"
        elif name == "norm":
            initial_params = np.asarray([float(np.mean(data_for_fitting)), float(np.std(data_for_fitting, ddof=1))])
            init_method = "moments"

    cond_pos = bool(prob_zero and conditional_positive)
    if name == "gamma":
        def _obj_fn(x):
            return _gamma_negloglik((x[0], x[1]), data_for_fitting)
    elif name == "weibull_min":
        def _obj_fn(x):
            return _weibull_negloglik((x[0], x[1]), data_for_fitting)
    elif name == "lognorm":
        def _obj_fn(x):
            return _lognorm_negloglik((x[0], x[1]), data_for_fitting)
    elif name == "fisk":
        def _obj_fn(x):
            return _fisk_negloglik((x[0], x[1]), data_for_fitting)
    elif name == "gumbel_r":
        def _obj_fn(x):
            return _gumbel_negloglik((x[0], x[1]), data_for_fitting, conditional_positive=cond_pos)
    elif name == "pearson3":
        def _obj_fn(x):
            return _pearson3_negloglik((x[0], x[1], x[2]), data_for_fitting, conditional_positive=cond_pos)
    elif name == "genextreme":
        def _obj_fn(x):
            return _gev_negloglik((x[0], x[1], x[2]), data_for_fitting, conditional_positive=cond_pos)
    else:
        _obj_fn = None

    fitted_pars: list[float] | None = None
    fitted_loc = np.nan
    fitted_scale = np.nan
    mle_success = False
    fit_method = "none"
    converged = False
    negloglik = np.nan

    # Step 1: Nelder-Mead MLE Optimization
    if initial_params is not None and _obj_fn is not None:
        try:
            with np.errstate(all="ignore"), warnings.catch_warnings():
                warnings.filterwarnings("ignore", category=RuntimeWarning)
                res = optimize.minimize(_obj_fn, x0=initial_params, method="Nelder-Mead")

            if res.success and np.all(np.isfinite(res.x)) and np.isfinite(res.fun):
                if name in ["gamma", "weibull_min", "lognorm", "fisk"]:
                    if res.x[0] > 0 and res.x[1] > 0:
                        fitted_pars = [float(res.x[0])]
                        fitted_loc = 0.0
                        fitted_scale = float(res.x[1])
                        mle_success = True
                elif name == "gumbel_r":
                    if res.x[1] > 0:
                        fitted_pars = None
                        fitted_loc = float(res.x[0])
                        fitted_scale = float(res.x[1])
                        mle_success = True
                elif name in ["pearson3", "genextreme"]:
                    if res.x[2] > 0 and np.isfinite(res.x[0]) and np.isfinite(res.x[1]):
                        fitted_pars = [float(res.x[0])]
                        fitted_loc = float(res.x[1])
                        fitted_scale = float(res.x[2])
                        mle_success = True

                if mle_success:
                    fit_method = "mle_nelder_mead"
                    converged = True
                    negloglik = float(res.fun)
        except Exception as e:
            logger.debug("Nelder-Mead MLE failed for %s: %s", name, e)

    # Step 2: Fallback to L-moments (if data size >= 4)
    if not mle_success and lm_distr is not None and data_for_fitting.size >= 4:
        lm_map = {
            "gamma": "gam",
            "weibull_min": "wei",
            "gumbel_r": "gum",
            "pearson3": "pe3",
            "genextreme": "gev",
        }
        lm_name = lm_map.get(name, None)
        if lm_name is not None and hasattr(lm_distr, lm_name):
            try:
                lm_func = getattr(lm_distr, lm_name)
                lm_pars = lm_func.lmom_fit(data_for_fitting)
                if name in ["gamma", "weibull_min"]:
                    p_key = "a" if name == "gamma" else "c"
                    if lm_pars[p_key] > 0 and lm_pars["scale"] > 0:
                        fitted_pars = [float(lm_pars[p_key])]
                        fitted_loc = 0.0
                        fitted_scale = float(lm_pars["scale"])
                        mle_success = True
                elif name == "gumbel_r" and lm_pars["scale"] > 0:
                    fitted_pars = None
                    fitted_loc = float(lm_pars["loc"])
                    fitted_scale = float(lm_pars["scale"])
                    mle_success = True
                elif name in ["pearson3", "genextreme"] and lm_pars["scale"] > 0:
                    shape_key = "skew" if name == "pearson3" else "c"
                    fitted_pars = [float(lm_pars[shape_key])]
                    fitted_loc = float(lm_pars["loc"])
                    fitted_scale = float(lm_pars["scale"])
                    mle_success = True

                if mle_success:
                    fit_method = "lmoments"
                    converged = False
                    if _obj_fn is not None:
                        ptup = (fitted_pars[0], fitted_scale) if fitted_pars and name in ["gamma", "weibull_min"] else (fitted_loc, fitted_scale) if name == "gumbel_r" else (fitted_pars[0], fitted_loc, fitted_scale)
                        negloglik = float(_obj_fn(ptup))
            except Exception as e_lm:
                logger.debug("L-moments fallback failed for %s: %s", name, e_lm)

    # Step 3: Fallback to scipy.stats fit() (works for n >= 2)
    if not mle_success:
        try:
            fit_kwargs: dict[str, Any] = {}
            if name in ["gamma", "weibull_min", "lognorm", "fisk"]:
                fit_kwargs = {"floc": 0.0}
            with np.errstate(all="ignore"), warnings.catch_warnings():
                warnings.filterwarnings("ignore", category=RuntimeWarning)
                fit_tuple = dist.fit(data_for_fitting, **fit_kwargs)

            if len(fit_tuple) == 2:
                sp_pars = None
                sp_loc = float(fit_tuple[0])
                sp_scale = float(fit_tuple[1])
            elif len(fit_tuple) == 3:
                sp_pars = [float(fit_tuple[0])]
                sp_loc = float(fit_tuple[1])
                sp_scale = float(fit_tuple[2])
            else:
                *pars_l, sp_loc_val, sp_scale_val = fit_tuple
                sp_pars = [float(x) for x in pars_l]
                sp_loc = float(sp_loc_val)
                sp_scale = float(sp_scale_val)

            if np.isfinite(sp_loc) and np.isfinite(sp_scale) and sp_scale > 0:
                if sp_pars is None or np.all(np.isfinite(sp_pars)):
                    fitted_pars = sp_pars
                    fitted_loc = sp_loc
                    fitted_scale = sp_scale
                    mle_success = True
                    fit_method = "scipy_mle"
                    converged = False
                    if _obj_fn is not None:
                        ptup = (fitted_pars[0], fitted_scale) if fitted_pars and name in ["gamma", "weibull_min", "lognorm", "fisk"] else (fitted_loc, fitted_scale) if name == "gumbel_r" else (fitted_pars[0], fitted_loc, fitted_scale) if fitted_pars else (fitted_loc, fitted_scale)
                        negloglik = float(_obj_fn(ptup))
        except Exception as e_scipy:
            logger.debug("scipy.stats fit failed for %s: %s", name, e_scipy)

    # Step 4: Fallback to Method of Moments parameters
    if not mle_success and initial_params is not None:
        try:
            if name in ["gamma", "weibull_min", "lognorm", "fisk"]:
                if initial_params[0] > 0 and initial_params[1] > 0:
                    fitted_pars = [float(initial_params[0])]
                    fitted_loc = 0.0
                    fitted_scale = float(initial_params[1])
                    mle_success = True
            elif name == "gumbel_r" and initial_params[1] > 0:
                fitted_pars = None
                fitted_loc = float(initial_params[0])
                fitted_scale = float(initial_params[1])
                mle_success = True
            elif name in ["pearson3", "genextreme"] and initial_params[2] > 0:
                fitted_pars = [float(initial_params[0])]
                fitted_loc = float(initial_params[1])
                fitted_scale = float(initial_params[2])
                mle_success = True

            if mle_success:
                fit_method = "moments"
                converged = False
                if _obj_fn is not None:
                    ptup = (fitted_pars[0], fitted_scale) if fitted_pars and name in ["gamma", "weibull_min", "lognorm", "fisk"] else (fitted_loc, fitted_scale) if name == "gumbel_r" else (fitted_pars[0], fitted_loc, fitted_scale) if fitted_pars else (fitted_loc, fitted_scale)
                    negloglik = float(_obj_fn(ptup))
        except Exception:
            pass

    if mle_success and np.isfinite(fitted_scale) and fitted_scale > 0:
        fit_status = "success"
    else:
        fit_status = "optimizer_failed"
        fitted_pars = None
        fitted_loc = np.nan
        fitted_scale = np.nan
        fit_method = "none"
        converged = False
        negloglik = np.nan

    details = {
        "fit_status": fit_status,
        "fit_method": fit_method,
        "init_method": init_method,
        "converged": converged,
        "negloglik": negloglik,
        "n_raw": n_raw,
        "n_missing": n_missing,
        "n_valid": n,
        "n_zero": m,
        "n_positive": n_pos,
        "n_fitting": int(data_for_fitting.size),
        "pseudo_obs_added": False,
        "small_sample_warning": bool(n_pos <= 3),
        "is_all_zero": False,
        "is_constant": False,
    }
    return fitted_pars, fitted_loc, fitted_scale, p_zero_mass, details


# -----------------------------------------------------------------------------
# Main Distribution Wrapper Class: Dist
# -----------------------------------------------------------------------------

@dataclass
class Dist:
    """Wrapper around continuous probability distributions for drought indices.

    Supports SPI, SPEI, SGI, SSFI, and SSMI calculations with:
    - Distinct zero-mass (p_zero_mass) and plotting-position centroid (p_zero_centroid).
    - Separation of calibration sample (data_window) and evaluation sample (data).
    - Standard vs. Wang-compatible fitting policies.
    - Conditional-positive distribution model for positive precipitation.
    - Parametric-bootstrap K-S and A-D goodness-of-fit testing.
    - Shapiro-Wilk normality testing on resulting SPI values.
    """

    data: Series = field(init=True, repr=False)
    dist: ContinuousDist = field(init=True, repr=False)
    prob_zero: bool = field(default=False, init=True, repr=True)
    data_window: Series | None = field(default=None, init=True, repr=False)
    fitting_policy: Literal["standard", "wang"] = field(default="standard", init=True, repr=True)
    conditional_positive: bool = field(default=True, init=True, repr=True)
    all_zero_policy: Literal["stagge", "wang"] = field(default="stagge", init=True, repr=True)

    loc: float = field(init=False, repr=True)
    scale: float = field(init=False, repr=True)
    pars: list[float] | None = field(init=False, repr=False)
    p0: float = field(init=False, repr=False, default=0.0)
    p_zero_mass: float = field(init=False, repr=False, default=0.0)
    p_zero_centroid: float = field(init=False, repr=False, default=0.0)
    n_valid: int = field(init=False, repr=False, default=0)
    n_zero: int = field(init=False, repr=False, default=0)
    n_positive: int = field(init=False, repr=False, default=0)
    fit_method: str = field(init=False, repr=False, default="none")
    converged: bool = field(init=False, repr=False, default=False)
    negloglik: float = field(init=False, repr=False, default=np.nan)
    all_zero_group: bool = field(init=False, repr=False, default=False)

    fit_status: str = field(init=False, repr=True, default="none")
    init_method: str = field(init=False, repr=False, default="none")
    n_missing: int = field(init=False, repr=False, default=0)
    n_fitting: int = field(init=False, repr=False, default=0)
    pseudo_obs_added: bool = field(init=False, repr=False, default=False)
    small_sample_warning: bool = field(init=False, repr=False, default=False)

    def __post_init__(self) -> None:
        cal_series = self.data_window if self.data_window is not None else self.data
        raw_vals = pd.to_numeric(cal_series, errors="coerce")
        self.n_missing = int(np.sum(~np.isfinite(raw_vals)))
        arr = np.asarray(cal_series.dropna(), dtype=float)
        arr = arr[np.isfinite(arr)]
        self.n_valid = int(arr.size)

        if self.prob_zero:
            # Validate precipitation data: cannot have materially negative values
            if np.any(arr < -1e-6):
                raise ValueError(
                    f"Precipitation data must be non-negative for zero-inflated SPI; "
                    f"found negative values with min = {np.min(arr)}."
                )
            # Clamp tiny negative floating-point noise to exact zero
            arr = np.where((arr < 0.0) & (arr >= -1e-6), 0.0, arr)
            self.n_zero = int(np.sum(arr == 0.0))
            self.n_positive = self.n_valid - self.n_zero

            if self.n_valid > 0:
                self.p_zero_mass = float(self.n_zero / (self.n_valid + 1.0))
                self.p_zero_centroid = float((self.n_zero + 1.0) / (2.0 * (self.n_valid + 1.0)))
            else:
                self.p_zero_mass = 0.0
                self.p_zero_centroid = 0.5

            # Retain p0 for backward compatibility; p0 represents zero-mass probability
            self.p0 = self.p_zero_mass

            # Check all-zero calibration sample
            if self.n_valid > 0 and self.n_positive == 0:
                self.all_zero_group = True
                self.pars = None
                self.loc = np.nan
                self.scale = np.nan
                self.fit_method = "all_zero"
                self.fit_status = "all_zero"
                self.init_method = "none"
                self.converged = True
                self.negloglik = np.nan
                self.n_fitting = 0
                self.pseudo_obs_added = False
                self.small_sample_warning = False
                if self.all_zero_policy == "stagge":
                    self.p_zero_centroid = 0.5
                else:  # "wang"
                    self.p_zero_centroid = np.nan
                    self.p_zero_mass = np.nan
                    self.p0 = np.nan
                return
        else:
            self.n_zero = 0
            self.n_positive = self.n_valid
            self.p_zero_mass = 0.0
            self.p_zero_centroid = 0.0
            self.p0 = 0.0

        # Fit continuous distribution
        fitted_pars, fitted_loc, fitted_scale, _, details = self.fit_dist(
            data=cal_series,
            dist=self.dist,
            prob_zero=self.prob_zero,
            fitting_policy=self.fitting_policy,
            conditional_positive=self.conditional_positive,
            all_zero_policy=self.all_zero_policy,
            return_details=True,
        )

        self.pars = fitted_pars
        self.loc = fitted_loc
        self.scale = fitted_scale
        self.fit_method = str(details.get("fit_method", "none"))
        self.converged = bool(details.get("converged", False))
        self.negloglik = float(details.get("negloglik", np.nan))
        self.fit_status = str(details.get("fit_status", "none"))
        self.init_method = str(details.get("init_method", "none"))
        self.n_fitting = int(details.get("n_fitting", 0))
        self.pseudo_obs_added = bool(details.get("pseudo_obs_added", False))
        self.small_sample_warning = bool(details.get("small_sample_warning", False))

    @staticmethod
    def fit_dist(
        data: Series,
        dist: ContinuousDist,
        prob_zero: bool,
        fitting_policy: Literal["standard", "wang"] = "standard",
        conditional_positive: bool = True,
        all_zero_policy: Literal["stagge", "wang"] = "stagge",
        return_details: bool = False,
    ) -> tuple[list[float] | None, float, float, float] | tuple[list[float] | None, float, float, float, dict[str, Any]]:
        """Fits a probability distribution using multi-stage parameter estimation."""
        arr = np.asarray(data.dropna(), dtype=float)
        arr = arr[np.isfinite(arr)]
        raw_vals = pd.to_numeric(data, errors="coerce")
        n_raw = len(data)
        n_missing = int(np.sum(~np.isfinite(raw_vals)))

        dist_name = getattr(dist, "name", None)
        if fitting_policy == "wang" and dist_name == "gamma":
            pars, loc, scale, p0_out, details = _fit_wang_gamma(
                arr=arr,
                prob_zero=prob_zero,
                all_zero_policy=all_zero_policy,
                n_raw=n_raw,
                n_missing=n_missing,
            )
        else:
            pars, loc, scale, p0_out, details = _fit_standard_dist(
                arr=arr,
                dist=dist,
                prob_zero=prob_zero,
                conditional_positive=conditional_positive,
                all_zero_policy=all_zero_policy,
                n_raw=n_raw,
                n_missing=n_missing,
            )

        if return_details:
            return pars, loc, scale, p0_out, details
        return pars, loc, scale, p0_out

    def cdf(self) -> Series:
        """Compute the cumulative density function (CDF) for the target observations."""
        data = self.data
        if self.all_zero_group:
            if self.all_zero_policy == "stagge":
                vals = np.where(data.values == 0.0, 0.5, np.nan)
            else:
                vals = np.full(len(data), np.nan)
            return Series(vals, index=data.index, dtype=float)

        if not np.isfinite(self.loc) or not np.isfinite(self.scale) or self.scale <= 0:
            return Series(np.full(len(data), np.nan), index=data.index, dtype=float)

        shape_args = tuple(self.pars) if self.pars is not None else ()
        cdf_args = (*shape_args, self.loc, self.scale)

        raw_cdf = self.dist.cdf(data.values, *cdf_args)
        raw_cdf = np.asarray(raw_cdf, dtype=float)
        data_valid = np.isfinite(data.values)
        if not np.all(np.isfinite(raw_cdf[data_valid])):
            return Series(np.full(len(data), np.nan), index=data.index, dtype=float)

        if self.prob_zero:
            # Conditional positive CDF F_pos(x) = (F(x) - F(0)) / (1 - F(0))
            if self.conditional_positive:
                f0 = float(self.dist.cdf(0.0, *cdf_args))
                s0 = float(self.dist.sf(0.0, *cdf_args))
                if not np.isfinite(s0) or s0 <= 1e-12:
                    return Series(np.full(len(data), np.nan), index=data.index, dtype=float)
                if f0 > 0.0:
                    pos_cdf = np.clip((raw_cdf - f0) / s0, 0.0, 1.0)
                else:
                    pos_cdf = np.clip(raw_cdf, 0.0, 1.0)
            else:
                pos_cdf = np.clip(raw_cdf, 0.0, 1.0)

            # Mixture model: H(x) = p_zero_mass + (1 - p_zero_mass) * F_pos(x) for x > 0
            # H(0) = p_zero_centroid for x == 0
            vals = self.p_zero_mass + (1.0 - self.p_zero_mass) * pos_cdf
            mask_zero = (data.values == 0.0)
            vals[mask_zero] = self.p_zero_centroid
            # Preserve NaNs from input data
            vals[np.isnan(data.values)] = np.nan
        else:
            vals = raw_cdf
            vals[np.isnan(data.values)] = np.nan

        return Series(vals, index=data.index, dtype=float)

    def pdf(self) -> Series:
        """Compute the probability density function (PDF) for the target observations."""
        data_pdf = self.data.sort_values()
        if self.all_zero_group or not np.isfinite(self.loc) or not np.isfinite(self.scale) or self.scale <= 0:
            return Series(np.full(len(data_pdf), np.nan), index=data_pdf.index, dtype=float)

        shape_args = tuple(self.pars) if self.pars is not None else ()
        cdf_args = (*shape_args, self.loc, self.scale)

        raw_pdf = np.asarray(self.dist.pdf(data_pdf.values, *cdf_args), dtype=float)

        if self.prob_zero:
            if self.conditional_positive:
                f0 = float(self.dist.cdf(0.0, *cdf_args))
                s0 = float(self.dist.sf(0.0, *cdf_args))
                if np.isfinite(s0) and s0 > 1e-12 and f0 > 0.0:
                    raw_pdf = raw_pdf / s0

            pdf_vals = (1.0 - self.p_zero_mass) * raw_pdf
            mask_zero = (data_pdf.values == 0.0)
            pdf_vals[mask_zero] = self.p_zero_centroid
            pdf_vals[np.isnan(data_pdf.values)] = np.nan
        else:
            pdf_vals = raw_pdf
            pdf_vals[np.isnan(data_pdf.values)] = np.nan

        return Series(pdf_vals, index=data_pdf.index, dtype=float)

    def ppf(self, q: float | np.ndarray) -> Series:
        """Compute the percent point function (inverse CDF / quantile function).

        Returns quantiles in original data units (e.g. mm of precipitation).
        Raw data quantiles are NEVER arbitrarily clipped to [-3, 3].
        """
        shape_args = tuple(self.pars) if self.pars is not None else ()
        cdf_args = (*shape_args, self.loc, self.scale)

        if not np.isfinite(self.loc) or not np.isfinite(self.scale) or self.scale <= 0:
            return Series(np.full(len(self.data), np.nan), index=self.data.index, dtype=float)

        q_arr = np.asarray(q, dtype=float)
        is_scalar = q_arr.ndim == 0
        if is_scalar:
            q_arr = np.full(len(self.data), float(q), dtype=float)

        out = np.full(q_arr.shape, np.nan, dtype=float)

        if self.prob_zero:
            mask_zero = q_arr <= self.p_zero_mass
            out[mask_zero] = 0.0
            mask_pos = q_arr > self.p_zero_mass
            if np.any(mask_pos):
                q_pos = (q_arr[mask_pos] - self.p_zero_mass) / (1.0 - self.p_zero_mass)
                if self.conditional_positive:
                    f0 = float(self.dist.cdf(0.0, *cdf_args))
                    s0 = float(self.dist.sf(0.0, *cdf_args))
                    if np.isfinite(s0) and s0 > 1e-12 and f0 > 0.0:
                        q_pos = np.clip(f0 + q_pos * s0, 0.0, 1.0)
                out[mask_pos] = self.dist.ppf(q_pos, *cdf_args)
        else:
            out = np.asarray(self.dist.ppf(q_arr, *cdf_args), dtype=float)

        return Series(out, index=self.data.index, dtype=float)

    def aic(self) -> dict[str, float]:
        """Compute log-likelihood-based and MSE-based Akaike Information Criterion."""
        cal_series = self.data_window if self.data_window is not None else self.data
        data = np.asarray(cal_series.dropna(), dtype=float)
        data = data[np.isfinite(data)]

        if self.all_zero_group or not np.isfinite(self.loc) or not np.isfinite(self.scale) or self.scale <= 0:
            return {"AIC_loglik": np.nan, "AIC_mse": np.nan}

        shape_args = tuple(self.pars) if self.pars is not None else ()
        cdf_args = (*shape_args, self.loc, self.scale)
        name = getattr(self.dist, "name", None)

        # Count free continuous parameters estimated
        k = 0
        if self.pars is not None:
            k += len(self.pars)
        k += 1  # scale parameter
        if name not in ["gamma", "weibull_min", "lognorm", "fisk"]:
            k += 1  # loc parameter (if not fixed at 0.0)

        # 1. Likelihood-based AIC on positive component
        aic_loglik = np.nan
        try:
            if self.prob_zero:
                pos_data = data[data > 0.0]
                if pos_data.size >= 3:
                    log_pdf = np.asarray(self.dist.logpdf(pos_data, *cdf_args), dtype=float)
                    if np.all(np.isfinite(log_pdf)):
                        ll = float(np.sum(log_pdf))
                        if self.conditional_positive:
                            logsf0 = float(self.dist.logsf(0.0, *cdf_args))
                            if np.isfinite(logsf0) and logsf0 < 0.0:
                                ll -= len(pos_data) * logsf0
                        aic_loglik = float(-2.0 * ll + 2.0 * k)
            else:
                if data.size >= 3:
                    log_pdf = np.asarray(self.dist.logpdf(data, *cdf_args), dtype=float)
                    if np.all(np.isfinite(log_pdf)):
                        ll = float(np.sum(log_pdf))
                        aic_loglik = float(-2.0 * ll + 2.0 * k)
        except Exception as e:
            logger.debug("AIC_loglik computation failed for %s: %s", name, e)

        # 2. MSE-based AIC criterion (Zhao et al. 2020)
        aic_mse = np.nan
        try:
            eval_data = data[data > 0.0] if self.prob_zero else data
            n_eval = len(eval_data)
            if n_eval >= 3:
                sorted_eval = np.sort(eval_data)
                f_emp = np.arange(1, n_eval + 1, dtype=float) / (n_eval + 1.0)
                raw_cdf = np.asarray(self.dist.cdf(sorted_eval, *cdf_args), dtype=float)
                if self.prob_zero and self.conditional_positive:
                    f0 = float(self.dist.cdf(0.0, *cdf_args))
                    s0 = float(self.dist.sf(0.0, *cdf_args))
                    if np.isfinite(s0) and s0 > 1e-12 and f0 > 0.0:
                        f_fit = np.clip((raw_cdf - f0) / s0, 0.0, 1.0)
                    else:
                        f_fit = np.clip(raw_cdf, 0.0, 1.0)
                else:
                    f_fit = np.clip(raw_cdf, 0.0, 1.0)

                mse = float(np.mean((f_emp - f_fit) ** 2))
                mse = max(mse, 1e-12)
                aic_mse = float(n_eval * np.log(mse) + 2.0 * k)
        except Exception as e_mse:
            logger.debug("AIC_mse computation failed for %s: %s", name, e_mse)

        return {"AIC_loglik": aic_loglik, "AIC_mse": aic_mse}

    @staticmethod
    def _gof_statistic(
        data: np.ndarray,
        dist: ContinuousDist,
        pars: list[float] | None,
        loc: float,
        scale: float,
        condition_positive: bool = True,
    ) -> tuple[float, float]:
        """Compute KS D and Anderson-Darling A2 statistics for a positive sample."""
        x = np.sort(np.asarray(data, dtype=float))
        n = x.size
        if n < 3 or not np.isfinite(loc) or not np.isfinite(scale) or scale <= 0:
            return float("nan"), float("nan")

        shape_args = tuple(pars) if pars is not None else ()
        cdf_args = (*shape_args, loc, scale)
        u = np.asarray(dist.cdf(x, *cdf_args), dtype=float)
        if not np.all(np.isfinite(u)):
            return float("nan"), float("nan")

        if condition_positive:
            f0 = float(dist.cdf(0.0, *cdf_args))
            s0 = float(dist.sf(0.0, *cdf_args))
            if not np.isfinite(s0) or s0 <= 1e-12:
                return float("nan"), float("nan")
            if f0 > 0.0:
                u = (u - f0) / s0

        u_ks = np.clip(u, 0.0, 1.0)
        i = np.arange(1, n + 1, dtype=float)
        d_plus = np.max(i / n - u_ks)
        d_minus = np.max(u_ks - (i - 1.0) / n)
        ks_d = float(max(d_plus, d_minus))

        eps = np.finfo(float).eps
        u_ad = np.clip(u, eps, 1.0 - eps)
        ad_a2 = float(
            -n - np.sum((2.0 * i - 1.0) * (np.log(u_ad) + np.log1p(-u_ad[::-1]))) / n
        )
        return ks_d, ad_a2

    def goodness_of_fit(
        self,
        n_boot: int = 999,
        random_state: int | None = None,
    ) -> dict[str, Any]:
        """Assess fit quality with parametric-bootstrap K-S and A-D tests."""
        if n_boot < 1:
            raise ValueError("n_boot must be at least 1")

        cal_series = self.data_window if self.data_window is not None else self.data
        raw = np.asarray(cal_series.dropna(), dtype=float)
        raw = raw[np.isfinite(raw)]
        arr = raw[raw > 0.0] if self.prob_zero else raw

        result = {
            "KS_statistic": np.nan,
            "KS_pvalue": np.nan,
            "AD_statistic": np.nan,
            "AD_pvalue": np.nan,
            "n_test": int(arr.size),
            "n_boot_requested": int(n_boot),
            "n_boot_valid": 0,
            "bootstrap_success_rate": 0.0,
        }

        if arr.size < 3 or not np.isfinite(self.loc) or not np.isfinite(self.scale) or self.scale <= 0:
            return result

        cond_pos = bool(self.prob_zero and self.conditional_positive)
        ks_obs, ad_obs = self._gof_statistic(
            arr, self.dist, self.pars, self.loc, self.scale, condition_positive=cond_pos
        )
        result["KS_statistic"] = ks_obs
        result["AD_statistic"] = ad_obs
        if not np.isfinite(ks_obs) or not np.isfinite(ad_obs):
            return result

        shape_args = tuple(self.pars) if self.pars is not None else ()
        cdf_args = (*shape_args, self.loc, self.scale)
        rng = np.random.default_rng(random_state)
        ks_boot: list[float] = []
        ad_boot: list[float] = []

        prior_level = logger.level
        logger.setLevel(logging.ERROR)
        try:
            for _ in range(n_boot):
                try:
                    draws: list[np.ndarray] = []
                    n_collected = 0
                    rounds = 0
                    while n_collected < arr.size and rounds < 1000:
                        need = arr.size - n_collected
                        candidate = np.asarray(
                            self.dist.rvs(
                                *cdf_args,
                                size=max(need * 2, 32),
                                random_state=rng,
                            ),
                            dtype=float,
                        ).ravel()
                        candidate = candidate[np.isfinite(candidate)]
                        if cond_pos:
                            candidate = candidate[candidate > 0.0]
                        if candidate.size:
                            draws.append(candidate)
                            n_collected += candidate.size
                        rounds += 1

                    if n_collected < arr.size:
                        continue
                    sim = np.concatenate(draws)[: arr.size]

                    boot_pars, boot_loc, boot_scale, _ = self.fit_dist(
                        Series(sim),
                        self.dist,
                        prob_zero=False,
                        fitting_policy="standard",
                        conditional_positive=False,
                    )
                    if not np.isfinite(boot_loc) or not np.isfinite(boot_scale) or boot_scale <= 0:
                        continue

                    ks_b, ad_b = self._gof_statistic(
                        sim, self.dist, boot_pars, boot_loc, boot_scale,
                        condition_positive=cond_pos,
                    )
                    if np.isfinite(ks_b) and np.isfinite(ad_b):
                        ks_boot.append(ks_b)
                        ad_boot.append(ad_b)
                except Exception:
                    continue
        finally:
            logger.setLevel(prior_level)

        b_valid = len(ks_boot)
        result["n_boot_valid"] = b_valid
        result["bootstrap_success_rate"] = float(b_valid / n_boot)
        if b_valid > 0:
            result["KS_pvalue"] = float((1 + np.sum(np.asarray(ks_boot) >= ks_obs)) / (b_valid + 1))
            result["AD_pvalue"] = float((1 + np.sum(np.asarray(ad_boot) >= ad_obs)) / (b_valid + 1))

        return result

    def ks_test(
        self,
        method: Literal["auto", "exact", "approx", "asymp"] = "auto",
        n_boot: int = 999,
        random_state: int | None = None,
    ) -> float:
        """Return parametric-bootstrap-calibrated K-S p-value."""
        return float(self.goodness_of_fit(n_boot=n_boot, random_state=random_state)["KS_pvalue"])

    def ad_test(self, n_boot: int = 999, random_state: int | None = None) -> float:
        """Return parametric-bootstrap-calibrated Anderson-Darling p-value."""
        return float(self.goodness_of_fit(n_boot=n_boot, random_state=random_state)["AD_pvalue"])

    def shapiro_wilk_test(
        self,
        spi_values: Series | np.ndarray | None = None,
        zero_mask: Series | np.ndarray | None = None,
        alpha: float = 0.05,
        random_state: int | None = None,
        replace_zero_with_normal: bool = True,
        clip: tuple[float, float] | None = None,
    ) -> dict[str, Any]:
        """Test normality of the resulting SPI values using Shapiro-Wilk."""
        if not 0.0 < alpha < 1.0:
            raise ValueError("alpha must be between 0 and 1")
        if clip is not None and (len(clip) != 2 or clip[0] >= clip[1]):
            raise ValueError("clip must be None or a (lower, upper) tuple with lower < upper")

        spi_index = None
        if spi_values is None:
            cdf_series = self.cdf()
            spi_index = self.data.index
            eps = 1e-15
            clipped_cdf = np.clip(np.asarray(cdf_series, dtype=float), eps, 1.0 - eps)
            spi_arr = np.asarray(norm.ppf(clipped_cdf), dtype=float)
            inferred_zero = (
                np.asarray(self.data, dtype=float) == 0.0
                if self.prob_zero
                else np.zeros(len(self.data), dtype=bool)
            )
        else:
            if isinstance(spi_values, Series):
                spi_index = spi_values.index
                spi_arr = np.asarray(spi_values, dtype=float)
            else:
                spi_arr = np.asarray(spi_values, dtype=float).ravel()
            inferred_zero = np.zeros(spi_arr.size, dtype=bool)
            if zero_mask is None and self.prob_zero and spi_arr.size == len(self.data):
                if isinstance(spi_values, Series) and isinstance(self.data, Series):
                    inferred_zero = (
                        self.data.eq(0.0)
                        .reindex(spi_index)
                        .fillna(False)
                        .to_numpy(dtype=bool)
                    )
                else:
                    inferred_zero = np.asarray(self.data, dtype=float) == 0.0

        if zero_mask is None:
            zmask = np.asarray(inferred_zero, dtype=bool)
        elif isinstance(zero_mask, Series):
            if spi_index is not None:
                zmask = zero_mask.reindex(spi_index).fillna(False).to_numpy(dtype=bool)
            else:
                zmask = zero_mask.to_numpy(dtype=bool)
        else:
            zmask = np.asarray(zero_mask, dtype=bool).ravel()

        if spi_arr.ndim != 1:
            spi_arr = spi_arr.ravel()
        if zmask.size != spi_arr.size:
            raise ValueError(
                f"zero_mask length ({zmask.size}) must match SPI values length ({spi_arr.size})"
            )

        finite = np.isfinite(spi_arr)
        spi_arr = spi_arr[finite]
        zmask = zmask[finite]

        n_zero = int(np.sum(zmask))
        n_positive = int(spi_arr.size - n_zero)
        n_replaced = 0
        spi_for_test = spi_arr.copy()

        if replace_zero_with_normal and n_zero > 0 and n_positive < 3:
            return {
                "SW_statistic": np.nan,
                "SW_pvalue": np.nan,
                "reject_normality": None,
                "alpha": float(alpha),
                "n_test": int(spi_arr.size),
                "n_positive_precip": n_positive,
                "n_zero_precip": n_zero,
                "n_zero_replaced": 0,
                "spi_mean": float(np.mean(spi_arr)) if spi_arr.size else np.nan,
                "spi_std": float(np.std(spi_arr, ddof=1)) if spi_arr.size > 1 else np.nan,
                "message": (
                    "At least 3 non-zero accumulated-precipitation samples are required "
                    "for the S-W diagnostic."
                ),
            }

        if replace_zero_with_normal and n_zero > 0:
            rng = np.random.default_rng(random_state)
            spi_for_test[zmask] = rng.standard_normal(n_zero)
            n_replaced = n_zero

        if clip is not None and spi_for_test.size:
            spi_for_test = np.clip(spi_for_test, clip[0], clip[1])

        if spi_for_test.size < 3:
            return {
                "SW_statistic": np.nan,
                "SW_pvalue": np.nan,
                "reject_normality": None,
                "alpha": float(alpha),
                "n_test": int(spi_for_test.size),
                "n_positive_precip": n_positive,
                "n_zero_precip": n_zero,
                "n_zero_replaced": n_replaced,
                "spi_mean": float(np.mean(spi_for_test)) if spi_for_test.size else np.nan,
                "spi_std": float(np.std(spi_for_test, ddof=1)) if spi_for_test.size > 1 else np.nan,
                "message": "Shapiro-Wilk requires at least 3 finite values.",
            }

        sw_result = shapiro(spi_for_test)
        p_value = float(sw_result.pvalue)
        return {
            "SW_statistic": float(sw_result.statistic),
            "SW_pvalue": p_value,
            "reject_normality": bool(p_value < alpha),
            "alpha": float(alpha),
            "n_test": int(spi_for_test.size),
            "n_positive_precip": n_positive,
            "n_zero_precip": n_zero,
            "n_zero_replaced": n_replaced,
            "spi_mean": float(np.mean(spi_for_test)),
            "spi_std": float(np.std(spi_for_test, ddof=1)),
            "random_state": random_state,
            "message": None,
        }