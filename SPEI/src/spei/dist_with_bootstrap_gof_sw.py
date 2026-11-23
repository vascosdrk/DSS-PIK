"""
Distribution fitting module for drought indices calculation.

This module implements robust parameter estimation for probability distributions
used in drought index calculations (SPI, SPEI, SGI, SSFI, SSMI).

FRAMEWORK AND ENHANCEMENTS
==========================

This implementation extends the original distribution fitting approach (Vonk, 2025)
with a comprehensive multi-stage parameter estimation framework based on Wang et al. (2022).

Original Approach (Vonk, 2025):
    - Simple scipy.fit() with scale=std(data) for all distributions
    - Basic zero probability as empirical ratio: p0 = (count of zeros) / (total count)
    - No extrapolation bounds on PPF values

Enhanced Approach (Based on Wang et al., 2022):
    - Multi-stage parameter estimation combining:
        1. L-moments method (lmoments3 package) for initial parameter estimates
        2. Method of Moments (MoM) as fallback for limited data cases
        3. Maximum Likelihood Estimation (MLE) using Nelder-Mead optimization
        4. Tiered fallback strategy ensuring robustness across varying data characteristics

    - Zero-probability calculation using centroid formula (Stagge et al., 2013):
        p0 = (m + 1) / (2 * (n + 1))
        where m = number of zero values, n = total number of observations
        This replaces the simple empirical ratio and provides better tail behavior.

    - PPF (quantile function) output bounded to [-3, 3] per Stagge et al. (2013):
        Ensures reasonable extrapolation limits (approximately once in 741 years)
        for SPI/SPEI drought classification.

PARAMETER ESTIMATION CASES
==========================

The framework handles four distinct cases:

Case 1: No zeros in data (n_non_zero = n, p0_val = 0)
    - Standard MLE fitting on full dataset
    - L-moments for initial parameters
    - Most reliable scenario with full data

Case 2: Zeros present with sufficient non-zero data (n_non_zero > 3)
    - Zero-adjustment: append min(data) * 0.01 to prevent fitting gaps (Wang et al., 2022)
            - L-moments fitting on positive data only (Stagge et al., 2013)
            - Stagge et al. (2013) formula for zero probability
Case 3: Zeros present with limited non-zero data (1 <= n_non_zero <= 3)
    - Zero-adjustment applied with small-value technique
    - Method of Moments for initial parameters
    - Nelder-Mead MLE optimization
    - Fallback to scipy.fit if MLE fails
    - Rare but handled gracefully

Case 4: All values are zero (n_non_zero = 0)
    - Parameters set to NaN
    - p0_val = 1.0 (probability of zero is certain)
    - Index-level handling in SI class

MULTI-STAGE FITTING STRATEGY
============================

Stage 1: Primary MLE using Nelder-Mead
    - Uses lmoments3.nnlf() for negative log-likelihood
    - Initial parameters from L-moments or MoM
    - Optimization method: Nelder-Mead (robust for non-smooth objectives)

Stage 2: Fallback to L-moments
    - If MLE convergence fails
    - Direct L-moment parameter extraction
    - Supported distributions: Gamma, Weibull, Gumbel, Pearson3

Stage 3: scipy.fit() with initial parameters
    - If L-moments unavailable or fails
    - Uses scipy.stats.fit() with shape parameters initialized
    - Maximum likelihood estimation via scipy

Stage 4: scipy.fit() without parameters
    - Final fallback for unfamiliar distributions
    - Relies on scipy's internal optimization

Stage 5: Initial parameters as final fit (non-MLE)
    - Last resort if all numerical optimization fails
    - Ensures always return some parameters rather than fail

SUPPORTED DISTRIBUTIONS
=======================

L-moments available for:
    - Gamma (gamma)
    - Weibull (weibull_min)
    - Gumbel (gumbel_r)
    - Pearson3 (pearson3)
    - GEV / Generalized Extreme Value (genextreme)

MoM implementation for:
    - Lognormal (lognorm)
    - Fisk / Log-logistic (fisk)
    - All above distributions as backup

REFERENCES
==========

    - Stagge, J.H., L.M. Tallaksen, L. Gudmundsson, A.F. Van Loon, and K. Stahl (2013)
        "Candidate Distributions for Climatological Drought Indices (SPI and SPEI)"
        DOI: 10.1002/joc.4267

    - Wang, H., Y. Liu, H. Jiao, S. Ouyang, X. Li, Z. Qin, H. Zhang, S. Shen, and J. Hao (2022)
        "An improved daily standardized precipitation index dataset for mainland China from 1961 to 2018"
        Scientific Data, 9, 201. DOI: 10.1038/s41597-022-01201-z

    - Vonk, M. A. (2025)
        "SPEI: A Python package for calculating and visualizing drought indices"
        Journal of Open Source Software, 10(111), 8454
        DOI: 10.21105/joss.08454

    - Lee, C., Seo, J., Won, J., & Kim, S. (2023).
        "Optimal probability distribution and applicable minimum time-scale for daily
        standardized precipitation index time series in South Korea." Atmosphere, 14(8), 1292.
        DOI: 10.3390/atmos14081292

    - Zhao, R., Wang, H., Zhan, C., Hu, S., Ma, M., & Dong, Y. (2020).
        "Comparative analysis of probability distributions for the Standardized
        Precipitation Index and drought evolution in China during 1961–2015." Theoretical
        and Applied Climatology, 139, 1363-1377. DOI: 10.1007/s00704-019-03050-0

CONTRIBUTOR ENHANCEMENTS
========================

    - Hayu Nur Mahron (hayu.mahron@bmkg.go.id)
      Implementation of Wang et al. (2022) framework with multi-stage fitting,
      Stagge formula integration, and PPF bounds for Indonesian precipitation data
"""

from dataclasses import dataclass, field
from typing import Literal

import numpy as np
import pandas as pd
from numpy import std
from pandas import Series
from scipy import optimize

from ._typing import ContinuousDist

import logging

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


def shapiro_wilk_rejection_frequency(p_values, alpha: float = 0.05) -> dict:
    """Summarize S-W rejection frequency across independently tested SPI groups.

    This mirrors the aggregation reported by Stagge et al. (2015): for each
    candidate distribution, calculate one S-W p-value per independent fitted
    group (e.g. station x accumulation period x calendar day), then calculate
    the percentage with p < alpha. Do not pass the raw daily SPI observations
    here; pass the list of p-values returned by ``shapiro_wilk_test``.
    """
    if not 0.0 < alpha < 1.0:
        raise ValueError("alpha must be between 0 and 1")

    values = np.asarray(list(p_values) if not isinstance(p_values, np.ndarray) else p_values,
                        dtype=float).ravel()
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


def _weibull_negloglik(params, data):
    c, scale = params
    if scale <= 0 or c <= 0: # Shape parameter c must also be positive
        return np.inf
    from scipy.stats import weibull_min
    return -np.sum(weibull_min.logpdf(data, c=c, scale=scale))

def _gamma_negloglik(params, data):
    a, scale = params
    if a <= 0 or scale <= 0:
        return np.inf
    from scipy.stats import gamma
    return -np.sum(gamma.logpdf(data, a=a, scale=scale))

def _gumbel_negloglik(params, data):
    # Gumbel (right) has shape=0 in scipy extreme value family; scipy has gumbel_r (loc, scale)
    loc, scale = params
    if scale <= 0:
        return np.inf
    from scipy.stats import gumbel_r
    return -np.sum(gumbel_r.logpdf(data, loc=loc, scale=scale))

def _pearson3_negloglik(params, data):
    skew, loc, scale = params
    if scale <= 0:
        return np.inf
    from scipy.stats import pearson3
    return -np.sum(pearson3.logpdf(data, skew, loc=loc, scale=scale))

def _gev_negloglik(params, data):
    c, loc, scale = params
    if scale <= 0:
        return np.inf
    from scipy.stats import genextreme
    # scipy.genextreme takes shape c (note sign conventions with some lmoments packages)
    return -np.sum(genextreme.logpdf(data, c, loc=loc, scale=scale))

# Helper function to estimate initial parameters using method of moments
from scipy.special import gamma as gamma_func
from scipy.stats import skew, norm, shapiro
from scipy.optimize import root_scalar

# Helper function to estimate Weibull parameters using method of moments
def estimate_weibull_moments(data):
    mean = data.mean()
    var = data.var(ddof=1)
    if mean <= 0 or var <= 0:
        # Fallback values if mean or variance are non-positive
        return 1.0, 0.0, data.std(ddof=1)
    r = var / mean**2

    # Define function for root finding to solve for shape parameter c
    def func(k):
        return (gamma_func(1 + 2/k) / (gamma_func(1 + 1/k)**2)) - 1 - r
    try:
        # Find root of func in interval [0.1, 10]
        sol = root_scalar(func, bracket=[0.5, 10], method='brentq')
        c = sol.root
    except Exception:
        # Fallback shape parameter if root finding fails
        c = 1.0
    # Calculate scale parameter from mean and shape
    scale = mean / gamma_func(1 + 1/c)
    return c, scale

# Helper function to estimate Gumbel parameters using method of moments
def estimate_gumbel_moments(data):
    mean = data.mean()
    std = data.std(ddof=1)
    gamma_const = 0.5772156649  # Euler-Mascheroni constant
    # Scale parameter estimated from std deviation
    scale = std * np.sqrt(6) / np.pi
    # Location parameter estimated from mean and scale
    loc = mean - gamma_const * scale
    return loc, scale

# Helper function to estimate Pearson3 parameters using method of moments
def estimate_pearson3_moments(data):
    mean = data.mean()
    std = data.std(ddof=1)
    skewness = skew(data)
    if skewness == 0:
        # Avoid division by zero in skewness
        skewness = 1e-6
    loc = np.min(data)  # Location estimated as minimum of data
    return skewness, loc, std

# Helper function to estimate GEV parameters using method of moments
def estimate_gev_moments(data):
    mean = data.mean()
    var = data.var(ddof=1)
    sample_skew = skew(data)

    # Theoretical skewness function of shape parameter c
    def skewness_func(c):
        num = gamma_func(1 - 3*c) - 3*gamma_func(1 - c)*gamma_func(1 - 2*c) + 2*gamma_func(1 - c)**3
        den = (gamma_func(1 - 2*c) - gamma_func(1 - c)**2)**(3/2)
        return num / den

    # Objective function for root finding: difference between theoretical and sample skewness
    def objective(c):
        return skewness_func(c) - sample_skew

    try:
        # Find shape parameter c in interval [-0.5, 0.5]
        sol = root_scalar(objective, bracket=[-0.3, 0.3], method='brentq')
        c = sol.root
    except Exception:
        # Fallback shape parameter if root finding fails
        c = 0.1

    # Calculate scale parameter sigma from variance and shape
    sigma = abs(c) * np.sqrt(var / (gamma_func(1-2*c)-gamma_func(1-c)**2))
    # Calculate location parameter mu from mean, scale, and shape
    mu = mean - (sigma / c) * (gamma_func(1 - c) - 1)
    return c, mu, sigma

def estimate_lognorm_moments(data):
    """
    Estimate Lognormal parameters (shape=sigma, loc, scale=exp(mu))
    using method of moments from sample mean and variance.
    """
    mean = np.mean(data)
    var = np.var(data, ddof=1)
    if mean <= 0 or var <= 0:
        return 1.0, 0.0, 1.0

    # Moment relationships:
    # mean = exp(mu + sigma^2 / 2)
    # var = (exp(sigma^2) - 1) * exp(2mu + sigma^2)
    sigma2 = np.log(1 + var / mean**2)
    sigma = np.sqrt(sigma2)
    mu = np.log(mean) - 0.5 * sigma2
    scale = np.exp(mu)
    return sigma, 0.0, scale

def estimate_fisk_moments(data):
    """
    Estimate Fisk (Log-logistic) parameters using method of moments.
    The distribution has shape c, loc, scale.
    """
    mean = np.mean(data)
    var = np.var(data, ddof=1)
    if mean <= 0 or var <= 0:
        return 1.0, 0.0, 1.0

    # Theoretical mean and var for fisk(c, loc=0, scale=s):
    # mean = s * (π/c) / sin(π/c)  for c > 1
    # var = s^2 * [ (2π/c) / sin(2π/c) - (π/c / sin(π/c))^2 ]  for c > 2
    # We solve for c numerically, then s from mean.

    def func(c):
        if c <= 2.01:
            return 1e6  # avoid invalid
        term1 = (2 * np.pi / c) / np.sin(2 * np.pi / c)
        term2 = ((np.pi / c) / np.sin(np.pi / c))**2
        theo_var_ratio = term1 - term2
        return theo_var_ratio - (var / mean**2)

    try:
        sol = root_scalar(func, bracket=[2.05, 50], method="brentq")
        c = sol.root
    except Exception:
        c = 5.0  # fallback

    scale = mean * np.sin(np.pi / c) * c / np.pi
    return c, 0.0, scale


@dataclass
class Dist:
    """A wrapper around scipy continuous distributions for drought indices.

    This class provides distribution fitting and evaluation for SPI, SPEI, SGI,
    SSFI, and SSMI calculations. It extends the original Vonk (2025) implementation
    with a comprehensive multi-stage parameter estimation framework based on
    Wang et al. (2022).

    FITTING APPROACH
    ================

    Original (Vonk, 2025):
        - Simple scipy.fit() with scale=std(data)
        - Basic handling of p0 = (count of zeros) / (total observations)

    Enhanced (Wang et al., 2022 framework):
        - Multi-stage fitting: L-moments → MLE (Nelder-Mead) → scipy.fit() → fallback
        - Stagge et al. (2013) zero probability formula: p0 = (m+1) / (2(n+1))
        - Zero-adjustment small value technique to prevent fitting gaps
        - PPF bounds [-3, 3] per Stagge et al. (2013) recommendations

    The multi-stage approach ensures robust parameter estimation across:
        - Full datasets (Case 1)
        - Datasets with zeros and sufficient positive data (Case 2)
        - Datasets with zeros and limited positive data (Case 3)
        - Edge cases with all zeros or no data (Case 4)

    ATTRIBUTES
    ==========

    data : pandas.Series
        The input data for fitting (typically daily precipitation, streamflow, etc.)

    dist : scipy.stats.rv_continuous
        The target probability distribution from scipy.stats to fit

    prob_zero : bool, default=False
        If True, handle zero-inflated data using Stagge et al. (2013) formula

    data_window : pandas.Series | None, default=None
        Optional subset of data for localized fitting (e.g., for rolling windows)

    loc : float
        Location parameter of fitted distribution

    scale : float
        Scale parameter of fitted distribution

    pars : list[float] | None
        Additional shape parameters (if applicable for distribution)

    p0 : float
        Probability of zero values (computed if prob_zero=True)

    REFERENCES
    ==========

    - Vonk, M.A. (2025): SPEI - A Python package for calculating and visualizing
      drought indices. Journal of Open Source Software, 10(111), 8454.
      DOI: 10.21105/joss.08454

    - Wang et al. (2022): An improved daily standardized precipitation index dataset
      for mainland China from 1961 to 2018. Scientific Data, 9, 201.
      DOI: 10.1038/s41597-022-01201-z

    - Stagge et al. (2013): Candidate Distributions for Climatological Drought
      Indices (SPI and SPEI). International Journal of Climatology, 33(14), 2585-2597.
      DOI: 10.1002/joc.4267


    """

    data: Series = field(init=True, repr=False)
    dist: ContinuousDist = field(init=True, repr=False)
    prob_zero: bool = field(default=False, init=True, repr=True)
    data_window: Series | None = field(default=None, init=True, repr=False)

    loc: float = field(init=False, repr=True)
    scale: float = field(init=False, repr=True)
    pars: list[float] | None = field(init=False, repr=False)
    p0: float = field(init=False, repr=False, default=0.0)

    def __post_init__(self):
        # select fitting data (data_window overrides)
        data_fit = self.data_window if self.data_window is not None else self.data

        # Call the new fitting method that mimics utilsPY.py
        self.pars, self.loc, self.scale, self.p0 = self.fit_dist(
            data=data_fit,
            dist=self.dist,
            prob_zero=self.prob_zero
        )

    @staticmethod
    def fit_dist(
        data: Series, dist: ContinuousDist, prob_zero: bool
    ) -> tuple[list[float] | None, float, float, float]:
        """
        Fits a probability distribution to data using multi-stage parameter estimation.

        This method implements the framework from Wang et al. (2022) extending
        Vonk (2025) with robust handling of edge cases and various data characteristics.

        ESTIMATION STRATEGY
        ===================

        The fitting process follows a hierarchical approach:

        1. DATA VALIDATION & ZERO HANDLING
           - Count zero values and estimate p0 using Stagge et al. (2013) formula
           - Identify case: (1) no zeros, (2) zeros + sufficient data, 
                            (3) zeros + limited data, (4) all zeros
           - Apply zero-adjustment (Wang et al., 2022): append min(positive_data) * 0.01
             to prevent artificial gaps in tail fitting

        2. INITIAL PARAMETER ESTIMATION
           - L-moments method (lmoments3 package) for distributions: gamma, weibull, gumbel, pearson3, gev
           - Method of Moments (MoM) fallback for: lognorm, fisk, or when L-moments fails
           - scipy.fit() as final fallback for arbitrary distributions

        3. MAXIMUM LIKELIHOOD ESTIMATION (Primary)
           - Algorithm: Nelder-Mead optimization (robust for non-smooth problems)
           - Objective: Minimize negative log-likelihood via lmoments3.nnlf()
           - Uses initial parameters from Stage 2

        4. FALLBACK CHAIN (if MLE fails)
           a) L-moments refitting (if not already tried)
           b) scipy.fit() with initial parameters
           c) scipy.fit() without parameters
           d) Use initial parameters as final fit (non-MLE)

        PARAMETER ESTIMATION CASES
        ==========================

        Case 1: No zeros (n_non_zero = n, p0_val = 0)
            - Standard scenario: full data used for fitting
            - MLE on complete positive dataset
            - L-moments for initialization
            - Returns: loc, scale, pars from MLE

        Case 2: Zeros present, sufficient non-zero data (n_non_zero > 3)
            - Typical for daily precipitation data
            - Zero-adjustment applied: positive_data + [min(positive_data)*0.01]
            - Fitting on positive data only (consistent with Stagge et al., 2013)
            - p0 computed from zero count using Stagge formula
            - Returns: loc, scale, pars from MLE; p0 from Stagge formula

        Case 3: Zeros present, limited non-zero data (1 <= n_non_zero <= 3)
            - Edge case with mostly zeros
            - Zero-adjustment still applied for stability
            - MoM used instead of L-moments for robustness
            - Nelder-Mead MLE on small sample
            - May require fallback chain
            - Returns: loc, scale, pars with warnings logged

        Case 4: All values are zero (n_non_zero = 0)
            - Degenerate case: p0 = 1.0
            - Parameters set to NaN
            - Handled at SI class level (no index-level SPI values computed)

        REFERENCES
        ==========

        Wang et al. (2022):
            Framework for multi-stage fitting with zero adjustment

        Stagge et al. (2013):
            Distribution candidate selection for drought indices

        Vonk (2025):
            Original scipy.fit() based implementation

        Parameters
        ----------
        data : pandas.Series
            The input data for fitting.
        dist : scipy.stats.rv_continuous
            The continuous distribution to be fitted.
        prob_zero : bool
            If True, calculate zero probability using Stagge formula.

        Returns
        -------
        tuple
            (pars, loc, scale, p0_val)
            where:
            - pars: list of shape parameters (or None if only loc/scale)
            - loc: location parameter
            - scale: scale parameter
            - p0_val: probability of zero (0.0 if prob_zero=False)
        """
        arr = np.asarray(data.dropna(), dtype=float)
        n = arr.size

        if n == 0:
            return None, np.nan, np.nan, 0.0 # p0 is 0 if no data

        m = int(np.sum(arr == 0.0)) # Number of zeros
        n_non_zero = n - m # Number of non-zero values

        # Calculate p0 using Stagge et al. (2013) centroid formula
        # p0 = (m + 1) / (2 * (n + 1))  (centroid of zero mass)
        p0_val = ((m + 1.0) / (2.0 * (n + 1.0))) if prob_zero and m > 0 else 0.0

        # Parameter estimation follows four cases based on zero values presence
        # Case 4: All values are zero
        if p0_val > 0 and n_non_zero == 0:
            logger.debug(f"Case 4: All values are zero for {dist.name}. Parameters set to NaN.")
            return None, np.nan, np.nan, p0_val

        # Data for fitting (only positive values for distributions like Gamma, Weibull)
        pos_data_original = arr[arr > 0.0]
        
        if pos_data_original.size == 0:
            logger.debug(f"No positive data for fitting {dist.name}. Parameters set to NaN.")
            return None, np.nan, np.nan, p0_val

        # Prepare data for fitting, potentially appending a small value
        data_for_fitting = pos_data_original       # faster computing
        name = getattr(dist, 'name', None)

        # Add a small value close to zero to prevent gaps in the data
        # Reference: Wang et al. (2022) "An improved daily standardized precipitation
        # index dataset for mainland China from 1961 to 2018"
        # https://doi.org/10.1038/s41597-022-01201-z
        # This is applied for Case 1 and Case 3 where zeros exist and non-zero data is used
        if prob_zero and p0_val > 0 and n_non_zero > 0 and name in ['gamma', 'weibull_min', 'genextreme', 'pearson3', 'gumbel_r', 'lognorm', 'fisk']:
            if pos_data_original.size > 0:
                data_for_fitting = np.concatenate((pos_data_original, [np.min(pos_data_original) * 0.01]))
            # else: data_for_fitting remains empty, handled by previous check
        
        # Ensure data_for_fitting is not empty after potential modifications
        if data_for_fitting.size == 0:
            logger.debug(f"No valid data for fitting after preprocessing for {dist.name}. Parameters set to NaN.")
            return None, np.nan, np.nan, p0_val

        # Initial parameter estimation using L-moments when available
        initial_params = None
        if lm_distr is not None:
            lm_map = {
                'gamma': 'gam',
                'weibull_min': 'wei',
                'gumbel_r': 'gum',
                'pearson3': 'pe3',
                'genextreme': 'gev',
            }
            lm_name = lm_map.get(name, None)

            if lm_name is None:
                # Skip L-moment fitting for distributions not supported by lmoments3
                logger.debug(f"L-moment fitting not supported for {name}, skipping.")
            else:
                if hasattr(lm_distr, lm_name):
                    lm_func = getattr(lm_distr, lm_name)
                    try:
                        lm_pars = lm_func.lmom_fit(data_for_fitting)  # Use data_for_fitting
                        # --- assign parameter arrays by distribution type ---
                        if name == 'gamma':
                            initial_params = np.asarray([lm_pars['a'], lm_pars['scale']])
                        elif name == 'weibull_min':
                            initial_params = np.asarray([lm_pars['c'], lm_pars['scale']])
                        elif name == 'gumbel_r':
                            initial_params = np.asarray([lm_pars['loc'], lm_pars['scale']])
                        elif name == 'pearson3':
                            initial_params = np.asarray([lm_pars['skew'], lm_pars['loc'], lm_pars['scale']])
                        elif name == 'genextreme':
                            initial_params = np.asarray([-lm_pars['c'], lm_pars['loc'], lm_pars['scale']])

                        logger.debug(f"L-moment initial params for {name}: {initial_params}")

                    except Exception as e:
                        logger.warning(f"L-moment fitting failed for {name}: {e}. Trying method of moments or scipy default.")
                        initial_params = None

                # Retry L-moments fitting for case with no zero values
            if initial_params is None and p0_val == 0 and lm_name is not None:
                try:
                    lm_func = getattr(lm_distr, lm_name)
                    lm_pars = lm_func.lmom_fit(pos_data_original)  # Use pos_data_original directly

                    if name == 'gamma':
                        initial_params = np.asarray([lm_pars['a'], lm_pars['scale']])
                    elif name == 'weibull_min':
                        initial_params = np.asarray([lm_pars['c'], lm_pars['scale']])
                    elif name == 'gumbel_r':
                        initial_params = np.asarray([lm_pars['loc'], lm_pars['scale']])
                    elif name == 'pearson3':
                        initial_params = np.asarray([lm_pars['skew'], lm_pars['loc'], lm_pars['scale']])
                    elif name == 'genextreme':
                        initial_params = np.asarray([-lm_pars['c'], lm_pars['loc'], lm_pars['scale']])

                    logger.debug(f"Retry L-moment fitting (no zeros) for {name}: {initial_params}")

                except Exception as e:
                    logger.warning(f"L-moment retry failed for {name}: {e}")
                    initial_params = None

        else:
            logger.warning("lmoments3 not installed. Falling back to method of moments or scipy default for initial parameters.")

        # Case 3: Fallback to Method of Moments for insufficient non-zero data (1 <= n_non_zero <= 3)
        if initial_params is None and (p0_val > 0 and 1 <= n_non_zero <= 3):
            logger.debug(f"Case 3: Insufficient non-zero data for {name}. Using Method of Moments for initial guess.")
            if name == 'gamma':
                # Calculate mean and variance from data
                m1 = data_for_fitting.mean()
                v1 = data_for_fitting.var(ddof=1)
                # Method of moments estimates for gamma shape and scale
                a0 = m1 * m1 / v1 if v1 > 0 else 1.0
                scale0 = v1 / m1 if m1 > 0 else 1.0
                # Include loc=0 as gamma in scipy has shape, loc, scale
                initial_params = np.asarray([a0, scale0])
            elif name == 'weibull_min':
                # Estimate Weibull shape, scale using method of moments helper
                c0, scale0 = estimate_weibull_moments(data_for_fitting)
                initial_params = np.asarray([c0, scale0])
            elif name == 'gumbel_r':
                # Estimate Gumbel location and scale using method of moments helper
                loc0, scale0 = estimate_gumbel_moments(data_for_fitting)
                initial_params = np.asarray([loc0, scale0])
            elif name == 'pearson3':
                # Estimate Pearson3 skewness, location, scale using method of moments helper
                skew0, loc0, scale0 = estimate_pearson3_moments(data_for_fitting)
                initial_params = np.asarray([skew0, loc0, scale0])
            elif name == 'genextreme':
                # Estimate GEV shape, location, scale using method of moments helper
                c0, loc0, scale0 = estimate_gev_moments(data_for_fitting)
                initial_params = np.asarray([c0, loc0, scale0])
            elif name == 'lognorm':
                sigma0, loc0, scale0 = estimate_lognorm_moments(data_for_fitting)
                initial_params = np.asarray([sigma0, loc0, scale0])
            elif name == 'fisk':
                c0, loc0, scale0 = estimate_fisk_moments(data_for_fitting)
                initial_params = np.asarray([c0, loc0, scale0])
            else:
                # For other distributions, use scipy's fit method to get initial parameters
                try:
                    fit_tuple = dist.fit(data_for_fitting)
                    initial_params = np.asarray(fit_tuple)
                except Exception:
                    # If fitting fails, set initial_params to None
                    initial_params = None
        
        # Maximum Likelihood Estimation using Nelder-Mead optimization
        fitted_pars = None
        fitted_loc = np.nan
        fitted_scale = np.nan
        def _parse_fit_tuple(fit_tup):
            if len(fit_tup) == 2:
                return None, float(fit_tup[0]), float(fit_tup[1])
            elif len(fit_tup) == 3:
                return [float(fit_tup[0])], float(fit_tup[1]), float(fit_tup[2])
            else:
                *pars_list, loc_f, scale_f = fit_tup
                pars_list = [float(x) for x in pars_list] if pars_list else None
                return pars_list, float(loc_f), float(scale_f)

        # Step 1: Primary MLE estimation using Nelder-Mead method
        try:
            if name == 'gamma':
                def _obj_fn(x):
                    a, scale = x
                    return lm_distr.gam.nnlf(data_for_fitting, a=a, loc=0.0, scale=scale)

            elif name == 'weibull_min':
                def _obj_fn(x):
                    c, scale = x
                    return lm_distr.wei.nnlf(data_for_fitting, c=c, loc=0.0, scale=scale)

            elif name == 'gumbel_r':
                def _obj_fn(x):
                    loc, scale = x
                    return lm_distr.gum.nnlf(data_for_fitting, loc=loc, scale=scale)

            elif name == 'pearson3':
                def _obj_fn(x):
                    skew, loc, scale = x
                    return lm_distr.pe3.nnlf(data_for_fitting, skew=skew, loc=loc, scale=scale)

            elif name == 'genextreme':
                def _obj_fn(x):
                    # lmoments3 uses the opposite sign convention for c compared to SciPy.
                    c, loc, scale = x
                    return lm_distr.gev.nnlf(data_for_fitting, c=c, loc=loc, scale=scale)
                
            elif name == 'lognorm':
                def _obj_fn(x):
                    s, loc, scale = x
                    from scipy.stats import lognorm
                    return -np.sum(lognorm.logpdf(data_for_fitting, s, loc=0.0, scale=scale)) # loc=0.0 fixed for 2 params
                
            elif name == 'fisk':
                def _obj_fn(x):
                    c, loc, scale = x
                    from scipy.stats import fisk
                    return -np.sum(fisk.logpdf(data_for_fitting, c, loc=0.0, scale=scale)) # loc=0.0 fixed for 2 params
                
            else:
                raise RuntimeError(f"{name} not handled in nnlf-based MLE block")

            # Perform MLE optimization using Nelder-Mead
            # Ensure proper length of initial parameters
            if name in ['lognorm', 'fisk']:
                if initial_params is None or len(initial_params) != 3:
                    # fallback to method of moments if incomplete
                    if name == 'lognorm':
                        initial_params = np.asarray(estimate_lognorm_moments(data_for_fitting))
                    else:
                        initial_params = np.asarray(estimate_fisk_moments(data_for_fitting))

            res = optimize.minimize(_obj_fn, x0=initial_params, method='Nelder-Mead')

            # Extract results if optimization was successful
            if res.success and np.all(np.isfinite(res.x)):
                if name == 'gamma':
                    fitted_pars = [float(res.x[0])]
                    fitted_loc = 0.0
                    fitted_scale = float(res.x[1])

                elif name == 'weibull_min':
                    fitted_pars = [float(res.x[0])]
                    fitted_loc = 0.0
                    fitted_scale = float(res.x[1])

                elif name == 'gumbel_r':
                    fitted_pars = None
                    fitted_loc = float(res.x[0])
                    fitted_scale = float(res.x[1])

                elif name == 'pearson3':
                    fitted_pars = [float(res.x[0])]
                    fitted_loc = float(res.x[1])
                    fitted_scale = float(res.x[2])

                elif name == 'genextreme':
                    fitted_pars = [float(res.x[0])]
                    fitted_loc = float(res.x[1])
                    fitted_scale = float(res.x[2])

                elif name == 'lognorm':
                    # Lognormal shape, loc, scale
                    fitted_pars = [float(res.x[0])]     # shape (σ)
                    fitted_loc = float(res.x[1])        # loc fixed at 0.0
                    fitted_scale = float(res.x[2])      # scale = exp(μ)

                elif name == 'fisk':
                    # Fisk (log-logistic) shape, loc, scale
                    fitted_pars = [float(res.x[0])]     # shape (c)
                    fitted_loc = float(res.x[1])        # loc fixed at 0.0
                    fitted_scale = float(res.x[2])      # scale (s)
            else:
                raise RuntimeError(f"Nelder–Mead MLE failed for {name}")

        # Step 2: If MLE fails, fallback to L-moments
        except Exception as e_mle:
            logger.warning(f"MLE failed for {name}: {e_mle}. Trying L-moments fallback")

            lm_success = False
            if lm_distr is not None:
                lm_map = {
                    'gamma': 'gam', 'weibull_min': 'wei', 'gumbel_r': 'gum',
                    'pearson3': 'pe3'
                }
                lm_name = lm_map.get(name, None)
                if lm_name is not None and hasattr(lm_distr, lm_name):
                    try:
                        lm_func = getattr(lm_distr, lm_name)
                        lm_pars = lm_func.lmom_fit(data_for_fitting)
                        if name == 'gamma':
                            fitted_pars = [lm_pars['a']]
                            fitted_loc = 0.0
                            fitted_scale = lm_pars['scale']
                        elif name == 'weibull_min':
                            fitted_pars = [lm_pars['c']]
                            fitted_loc = 0.0
                            fitted_scale = lm_pars['scale']
                        elif name == 'gumbel_r':
                            fitted_pars = None
                            fitted_loc = lm_pars['loc']
                            fitted_scale = lm_pars['scale']
                        elif name == 'pearson3':
                            fitted_pars = [lm_pars['skew']]
                            fitted_loc = lm_pars['loc']
                            fitted_scale = lm_pars['scale']
                        # elif name == 'genextreme':
                        #     fitted_pars = [-lm_pars['c']]
                        #     fitted_loc = lm_pars['loc']
                        #     fitted_scale = lm_pars['scale']
                        lm_success = True
                        logger.info(f"L-moments fallback succeeded for {name}.")
                    except Exception as e_lmom:
                        logger.warning(f"L-moment fitting failed for {name}: {e_lmom}. Proceeding to scipy.fit().")

                else:
                    logger.debug(f"L-moments fallback not supported for {name}, skipping to scipy.fit().")

            # If L-moments also fail or unsupported, fallback to scipy.fit()
            if not lm_success:

                # Step 3: Try scipy.fit() (without forcing shape params as initials)
                # scipy.fit positional args can be interpreted as fixed shape parameters,
                # so we avoid passing initial_params as positional arguments.
                try:
                    fit_kwargs = {}

                    # Distribusi dengan support [0, +inf): kunci loc=0
                    if name in ['gamma', 'weibull_min', 'lognorm', 'fisk']:
                        fit_kwargs = {'floc': 0.0}

                    # Distribusi dengan support real-valued: biarkan loc bebas
                    elif name in ['gumbel_r', 'pearson3', 'genextreme']:
                        fit_kwargs = {}

                    if fit_kwargs or name in ['gumbel_r', 'pearson3', 'genextreme']:
                        fit_tuple = dist.fit(data_for_fitting, **fit_kwargs)
                        fitted_pars, fitted_loc, fitted_scale = _parse_fit_tuple(fit_tuple)
                        logger.info(f"scipy.fit succeeded for {name}.")
                        lm_success = True
                    else:
                        logger.debug(f"No fitting rule defined for {name}. Skipping scipy.fit.")

                except Exception as e_fit:
                    logger.warning(
                        f"scipy.fit failed for {name}: {e_fit}. Using initial_params as fallback."
                    )

            # Step 4: Final fallback to initial_params if all fitting methods failed
            if not lm_success and initial_params is not None:
                try:
                    if name in ['gamma', 'weibull_min']:
                        fitted_pars = [float(initial_params[0])]
                        fitted_loc = 0.0
                        fitted_scale = float(initial_params[1])

                    elif name in ['lognorm', 'fisk', 'pearson3', 'genextreme']:
                        fitted_pars = [float(initial_params[0])]
                        fitted_loc = float(initial_params[1])
                        fitted_scale = float(initial_params[2])

                    elif name == 'gumbel_r':
                        fitted_pars = []
                        fitted_loc = float(initial_params[0])
                        fitted_scale = float(initial_params[1])

                    logger.info(f"Using initial_params as final fallback for {name}.")
                    lm_success = True

                except Exception as e_fallback:
                    logger.error(
                        f"Final fallback using initial_params failed for {name}: {e_fallback}"
                    )
                    if initial_params is not None:
                        if name == 'gamma':
                            fitted_pars = [float(initial_params[0])]
                            fitted_loc = 0.0
                            fitted_scale = float(initial_params[1])
                        elif name == 'weibull_min':
                            fitted_pars = [float(initial_params[0])]
                            fitted_loc = 0.0
                            fitted_scale = float(initial_params[1])
                        elif name == 'gumbel_r':
                            fitted_pars = None
                            fitted_loc = float(initial_params[0])
                            fitted_scale = float(initial_params[1])
                        elif name == 'pearson3':
                            fitted_pars = [float(initial_params[0])]
                            fitted_loc = float(initial_params[1])
                            fitted_scale = float(initial_params[2])
                        elif name == 'genextreme':
                            fitted_pars = [float(initial_params[0])]
                            fitted_loc = float(initial_params[1])
                            fitted_scale = float(initial_params[2])
                        else:
                            # Generic fallback
                            if len(initial_params) >= 2:
                                fitted_pars = list(initial_params[:-2]) or None
                                fitted_loc = float(initial_params[-2])
                                fitted_scale = float(initial_params[-1])
                            else:
                                fitted_pars = None
                                fitted_loc = np.nan
                                fitted_scale = np.nan

                        logger.warning(f"Using initial_params as final fit (non-MLE) for {name}.")
                    else:
                        fitted_pars, fitted_loc, fitted_scale = None, np.nan, np.nan
                        logger.error(f"No valid initial_params available for {name}. Cannot fit distribution.")

        return fitted_pars, fitted_loc, fitted_scale, p0_val


    def cdf(self) -> Series:
        """Compute the cumulative density function (CDF) for the fitted distribution.

        COMPARISON WITH ORIGINAL VONK IMPLEMENTATION
        =============================================

        Original (Vonk, 2025):
            - Simple scipy.fit() based CDF
            - Basic zero handling: cdf = p0 + (1 - p0) * cdf
            - Direct empirical p0 = count(zeros) / n

        Enhanced (Wang et al., 2022 framework):
            - Multi-stage MLE optimized parameters (see fit_dist method)
            - Stagge et al. (2013) zero probability formula
            - Improved tail behavior for drought index calculation

        ZERO-INFLATED DATA HANDLING
        ===========================

        When prob_zero=True, the CDF is scaled according to:

            F_adjusted = p0 + (1 - p0) * F_continuous

        where:
            - p0 = (m+1)/(2(n+1)) from Stagge et al. (2013)
            - F_continuous = fitted distribution CDF
            - m = count of zero values
            - n = total observations

        For zero values specifically:
            - F(x=0) = (m+1)/(2(n+1)) [centroid of zero mass]
            
        This approach ensures proper probability mass at zero while preserving
        monotonicity and behavior in the continuous region [0, ∞).

        RETURNS
        =======
        
        pandas.Series
            CDF values in range [0, 1] with the same index as the original data.
            Values are NaN where input data is NaN.
        """
        data = self.data
        if self.pars is not None:
            vals = self.dist.cdf(data.values, *self.pars, loc=self.loc, scale=self.scale)
        elif getattr(self.dist, 'numargs', 0) == 0 and not np.isnan(self.loc):
            vals = self.dist.cdf(data.values, loc=self.loc, scale=self.scale)
        else:
            vals = np.full(len(data), np.nan)

        vals = np.asarray(vals, dtype=float)

        if self.prob_zero:
            m = (self.data == 0.0).sum()
            n = len(self.data)

            mask_zero = (data.values == 0.0)
            vals = self.p0 + (1.0 - self.p0) * vals
            vals[mask_zero] = (m + 1.0) / (2.0 * (n + 1.0))  # center of mass for zeros (m + 1.0) / (2.0 * (n + 1.0)) 

        return Series(vals, index=data.index, dtype=float)

    def pdf(self) -> Series:
        """Compute the probability density function (PDF) for the fitted distribution.

        COMPARISON WITH ORIGINAL VONK IMPLEMENTATION
        =============================================

        Original (Vonk, 2025):
            - Simple PDF from fitted scipy distribution
            - Basic zero handling: pdf = p0 + (1 - p0) * pdf
            - Sorted values for monotonicity

        Enhanced (Wang et al., 2022 framework):
            - Multi-stage MLE optimized parameters (see fit_dist method)
            - Stagge et al. (2013) zero probability formula
            - Improved numerical stability for MLE-fitted parameters

        ZERO-INFLATED DATA HANDLING
        ===========================

        When prob_zero=True, the PDF includes zero mass:

            f(x) = p0 * δ(x) + (1 - p0) * f_continuous(x)

        where:
            - δ(x) = Dirac delta at x=0
            - p0 = (m+1)/(2(n+1)) from Stagge et al. (2013)
            - f_continuous = fitted distribution PDF

        For zero values specifically:
            - PDF(x=0) = (m+1)/(2(n+1)) [mass point representation]
            
        RETURNS
        =======
        
        pandas.Series
            PDF values with the same index as the original data (sorted).
            Values are NaN where input data is NaN or invalid.
        """
        data_pdf = self.data.sort_values()
        if self.pars is not None:
            pdf = self.dist.pdf(data_pdf.values, *self.pars, loc=self.loc, scale=self.scale)
        else:
            pdf = self.dist.pdf(data_pdf.values, loc=self.loc, scale=self.scale)

        pdf = np.asarray(pdf, dtype=float)

        if self.prob_zero:
            m = (self.data == 0.0).sum()
            n = len(self.data)

            mask_zero = (data_pdf.values == 0.0)
            pdf = self.p0 + (1.0 - self.p0) * pdf
            pdf[mask_zero] = (m + 1.0) / (2.0 * (n + 1.0))  # center of mass for zeros (m + 1.0) / (2.0 * (n + 1.0)) 

        return Series(pdf, index=data_pdf.index, dtype=float)

    def ppf(self, q: float) -> Series:
        """Compute the percent point function (inverse CDF / quantile function).
        
        The output is bounded to [-3, 3] following Stagge et al. (2013) recommendation.
        
        Reference:
            - Stagge et al. (2013) "Candidate Distributions for Climatological Drought
              Indices (SPI and SPEI)" DOI: 10.1002/joc.4267
        
        The likelihood of accumulated precipitation exceeding these bounds on a given
        day of the year is approximately 0.14% or about once in 741 years. This is a
        reasonable extrapolation limit for a 30-year reference period. Events beyond
        these bounds are not removed but are marked as <-3 or >3 to indicate extreme
        values that cannot be accurately quantified (analogous to 'below detection
        limit' designations in laboratory measurements).
        
        Parameters
        ----------
        q : float
            Quantile value between 0 and 1.
        
        Returns
        -------
        pandas.Series
            PPF values clipped to [-3, 3] with the same index as the original data.
        """
        if self.prob_zero:
            # For zero-inflated data, map quantiles below p0 to zero
            q = np.asarray(q, dtype=float)
            out = np.full(self.data.shape, np.nan, dtype=float)
            mask_zero = q <= self.p0
            out[mask_zero] = 0.0
            mask_cont = q > self.p0
            if np.any(mask_cont):
                q_cont = (q[mask_cont] - self.p0) / (1.0 - self.p0)
                if self.pars is not None:
                    out[mask_cont] = self.dist.ppf(q_cont, *self.pars, loc=self.loc, scale=self.scale)
                else:
                    out[mask_cont] = self.dist.ppf(q_cont, loc=self.loc, scale=self.scale)
            out = np.clip(out, -3, 3)
            return Series(out, index=self.data.index, dtype=float)
        else:
            if self.pars is not None:
                ppf_vals = self.dist.ppf(q, *self.pars, loc=self.loc, scale=self.scale)
            else:
                ppf_vals = self.dist.ppf(q, loc=self.loc, scale=self.scale)
            ppf_vals = np.clip(ppf_vals, -3, 3)
            return Series(ppf_vals, index=self.data.index, dtype=float)

    @staticmethod
    def _gof_statistic(
        data: np.ndarray, dist, pars, loc: float, scale: float,
        condition_positive: bool = True,
    ) -> tuple[float, float]:
        """Return KS D and Anderson-Darling A^2 statistics.

        When testing precipitation amounts, the continuous component represents
        X | X > 0. Its CDF is therefore conditionally normalized above zero. For
        distributions already supported on [0, infinity), this changes nothing.
        """
        x = np.sort(np.asarray(data, dtype=float))
        n = x.size
        if n < 1:
            return float("nan"), float("nan")

        shape_args = tuple(pars) if pars is not None else ()
        cdf_args = (*shape_args, loc, scale)
        u = np.asarray(dist.cdf(x, *cdf_args), dtype=float)
        if not np.all(np.isfinite(u)):
            return float("nan"), float("nan")

        if condition_positive:
            f0 = float(dist.cdf(0.0, *cdf_args))
            survival_at_zero = 1.0 - f0
            if not np.isfinite(survival_at_zero) or survival_at_zero <= 1e-12:
                return float("nan"), float("nan")
            # CDF of the fitted continuous distribution conditional on X > 0.
            u = (u - f0) / survival_at_zero

        # Two-sided KS statistic, using the fitted model CDF.
        u_ks = np.clip(u, 0.0, 1.0)
        i = np.arange(1, n + 1, dtype=float)
        d_plus = np.max(i / n - u_ks)
        d_minus = np.max(u_ks - (i - 1.0) / n)
        ks_d = float(max(d_plus, d_minus))

        # Classical Anderson-Darling statistic for a continuous distribution.
        # Clipping avoids log(0) when fitted CDF values are numerically at 0 or 1.
        eps = np.finfo(float).eps
        u_ad = np.clip(u, eps, 1.0 - eps)
        ad_a2 = float(-n - np.sum((2.0 * i - 1.0) * (np.log(u_ad) + np.log1p(-u_ad[::-1]))) / n)
        return ks_d, ad_a2

    @staticmethod
    def _fit_gof_sample(data: np.ndarray, dist, add_small_value: bool = False):
        """Refit a bootstrap sample using this module's staged fitting routine."""
        sample = np.asarray(data, dtype=float)
        sample = sample[np.isfinite(sample)]
        sample = sample[sample > 0.0]
        if sample.size < 3:
            raise ValueError("Too few positive bootstrap values to refit distribution")

        # Match the small-value adjustment used by fit_dist when the original
        # SPI series contains zeros. Only positive-support SPI fits should rely
        # on this adjustment; it is applied here to the same candidate families.
        name = getattr(dist, "name", None)
        if add_small_value and name in {
            "gamma", "weibull_min", "genextreme", "pearson3",
            "gumbel_r", "lognorm", "fisk"
        }:
            sample = np.concatenate((sample, [float(np.min(sample)) * 0.01]))

        # prob_zero=False prevents a second zero correction; sample consists of
        # positive values, including the pseudo-observation above when applicable.
        pars, loc, scale, _ = Dist.fit_dist(pd.Series(sample), dist, prob_zero=False)
        if not np.isfinite(loc) or not np.isfinite(scale) or scale <= 0:
            raise ValueError("Invalid bootstrap parameter estimate")
        if pars is not None and not np.all(np.isfinite(pars)):
            raise ValueError("Invalid bootstrap shape parameter estimate")
        return pars, float(loc), float(scale)

    def goodness_of_fit(self, n_boot: int = 999, random_state: int | None = None) -> dict:
        """Assess fit with parametric-bootstrap-calibrated KS and AD tests.

        The empirical test sample is the positive component when ``prob_zero``
        is enabled, matching the module's SPI fitting convention. Each bootstrap
        replicate is generated from the fitted continuous distribution and the
        distribution is refitted before the KS and AD statistics are recomputed.
        This refitting step is essential: ordinary KS p-values are not calibrated
        when parameters are estimated from the same observations.

        Parameters
        ----------
        n_boot : int, default=999
            Number of successful parametric bootstrap replicates. For production
            use, 999 or more is recommended; 199 is useful for quick diagnostics.
        random_state : int or None
            Seed for reproducibility.

        Returns
        -------
        dict
            Includes observed statistics, bootstrap p-values, successful bootstrap
            count, and number of observations used in the tests.
        """
        if n_boot < 1:
            raise ValueError("n_boot must be at least 1")

        raw = np.asarray(self.data.dropna(), dtype=float)
        # This test follows the module's existing SPI convention: goodness of fit
        # is evaluated on the positive precipitation component only.
        arr = raw[np.isfinite(raw) & (raw > 0.0)]

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

        ks_obs, ad_obs = self._gof_statistic(
            arr, self.dist, self.pars, self.loc, self.scale, condition_positive=True
        )
        result["KS_statistic"] = ks_obs
        result["AD_statistic"] = ad_obs
        if not np.isfinite(ks_obs) or not np.isfinite(ad_obs):
            return result

        shape_args = tuple(self.pars) if self.pars is not None else ()
        rng = np.random.default_rng(random_state)
        ks_boot = []
        ad_boot = []
        # The continuous component is fitted to positive precipitation. For
        # SPI families whose support includes non-positive values, rejection
        # sampling keeps the generated continuous sample on the same positive
        # domain as the observations being tested.
        # SPI zero probability is handled separately from its continuous
        # positive-precipitation component.
        add_small_value = bool(self.prob_zero and np.any(raw == 0.0))
        max_draw_rounds = 1000
        prior_log_level = logger.level
        logger.setLevel(logging.ERROR)  # avoid emitting fallback logs for every replicate
        try:
            for _ in range(n_boot):
                try:
                    draws = []
                    n_collected = 0
                    rounds = 0
                    while n_collected < arr.size and rounds < max_draw_rounds:
                        need = arr.size - n_collected
                        candidate = np.asarray(
                            self.dist.rvs(
                                *shape_args, loc=self.loc, scale=self.scale,
                                size=max(need * 2, 32), random_state=rng
                            ),
                            dtype=float,
                        ).ravel()
                        candidate = candidate[np.isfinite(candidate) & (candidate > 0.0)]
                        if candidate.size:
                            draws.append(candidate)
                            n_collected += candidate.size
                        rounds += 1
                    if n_collected < arr.size:
                        continue
                    sim = np.concatenate(draws)[:arr.size]

                    boot_pars, boot_loc, boot_scale = self._fit_gof_sample(
                        sim, self.dist, add_small_value=add_small_value
                    )
                    ks_b, ad_b = self._gof_statistic(
                        sim, self.dist, boot_pars, boot_loc, boot_scale, condition_positive=True
                    )
                    if np.isfinite(ks_b) and np.isfinite(ad_b):
                        ks_boot.append(ks_b)
                        ad_boot.append(ad_b)
                except (ValueError, FloatingPointError, OverflowError, RuntimeError):
                    # Failed/non-convergent refits are excluded and reflected in n_boot_valid.
                    continue
                except Exception as exc:
                    logger.debug("Goodness-of-fit bootstrap replicate failed: %s", exc)
                    continue
        finally:
            logger.setLevel(prior_log_level)

        b_valid = len(ks_boot)
        result["n_boot_valid"] = b_valid
        result["bootstrap_success_rate"] = float(b_valid / n_boot)
        if b_valid:
            # Add-one correction avoids returning a zero Monte Carlo p-value.
            result["KS_pvalue"] = float((1 + np.sum(np.asarray(ks_boot) >= ks_obs)) / (b_valid + 1))
            result["AD_pvalue"] = float((1 + np.sum(np.asarray(ad_boot) >= ad_obs)) / (b_valid + 1))
        return result

    def ks_test(
        self,
        method: Literal["auto", "exact", "approx", "asymp"] = "auto",
        n_boot: int = 999,
        random_state: int | None = None,
    ) -> float:
        """Return a parametric-bootstrap-calibrated KS p-value.

        ``method`` is retained for backward API compatibility; it is no longer
        used because calibration comes from the parametric bootstrap, not the
        classical KS reference distribution. Call ``goodness_of_fit`` once to
        obtain both KS and Anderson-Darling results efficiently.
        """
        return float(self.goodness_of_fit(n_boot=n_boot, random_state=random_state)["KS_pvalue"])

    def ad_test(self, n_boot: int = 999, random_state: int | None = None) -> float:
        """Return a parametric-bootstrap-calibrated Anderson-Darling p-value."""
        return float(self.goodness_of_fit(n_boot=n_boot, random_state=random_state)["AD_pvalue"])

    def shapiro_wilk_test(
        self,
        spi_values: Series | np.ndarray | None = None,
        zero_mask: Series | np.ndarray | None = None,
        alpha: float = 0.05,
        random_state: int | None = None,
        replace_zero_with_normal: bool = True,
        clip: tuple[float, float] | None = (-3.0, 3.0),
    ) -> dict:
        """Test the normality of the *resulting SPI values* using Shapiro-Wilk.

        This implements the S-W part of Stagge et al. (2015). It is a different
        diagnostic from KS/AD: KS and AD in ``goodness_of_fit`` test the fitted
        continuous rainfall distribution, whereas this test checks the SPI values
        after the fitted CDF has been transformed with the standard-normal PPF.

        Parameters
        ----------
        spi_values : pandas.Series, numpy.ndarray, or None
            SPI values from the current fitted distribution. If None, SPI is
            calculated as norm.ppf(self.cdf()). For comparisons across candidate
            distributions, each candidate must use its own transformed SPI values.
        zero_mask : array-like of bool, optional
            True where the *original accumulated precipitation* equals zero.
            If omitted and spi_values is None, this is inferred from self.data
            when zero handling is enabled. If spi_values are supplied, inference
            is attempted only when their length/index matches self.data. Passing
            this mask explicitly is safest when testing externally calculated SPI.
        alpha : float, default=0.05
            Significance level used for the reject_normality output.
        random_state : int or None
            Seed controlling the artificial normal values for zero precipitation.
        replace_zero_with_normal : bool, default=True
            Following Stagge et al. (2015), replace the tied SPI values associated
            with zero accumulated precipitation by random N(0, 1) draws before
            testing. Set False only for sensitivity checks or a different method.
        clip : tuple[float, float] or None, default=(-3, 3)
            Optional clipping of observed/derived SPI values. The default follows
            the paper's proposed SPI bounds. Use None if the SPI series has
            intentionally not been bounded.

        Returns
        -------
        dict
            S-W statistic/p-value, rejection decision, sample counts, and summary
            moments. A p-value >= alpha means that normality was not rejected;
            it does not prove that the SPI values are standard normal.

        Notes
        -----
        Test each independent fitted group separately (for example, a fixed
        calendar day across years when the implementation fits 365 distributions).
        Do not automatically test one full rolling daily SPI time series: its
        serial autocorrelation violates the independence assumption. S-W also
        tests normality in general, not exactly mean=0 and standard deviation=1;
        inspect spi_mean and spi_std as additional diagnostics.
        """
        if not 0.0 < alpha < 1.0:
            raise ValueError("alpha must be between 0 and 1")
        if clip is not None and (len(clip) != 2 or clip[0] >= clip[1]):
            raise ValueError("clip must be None or a (lower, upper) tuple with lower < upper")

        # If not supplied, derive index values from this fitted CDF.
        spi_index = None
        if spi_values is None:
            cdf_values = np.asarray(self.cdf(), dtype=float)
            spi_index = self.data.index
            eps = np.finfo(float).eps
            spi_arr = np.asarray(norm.ppf(np.clip(cdf_values, eps, 1.0 - eps)), dtype=float)
            inferred_zero = (
                np.asarray(self.data, dtype=float) == 0.0
                if self.prob_zero else np.zeros(len(self.data), dtype=bool)
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
                        self.data.eq(0.0).reindex(spi_index).fillna(False).to_numpy(dtype=bool)
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
        if clip is not None and spi_arr.size:
            spi_arr = np.clip(spi_arr, clip[0], clip[1])

        n_zero = int(np.sum(zmask))
        n_positive = int(spi_arr.size - n_zero)
        n_replaced = 0
        spi_for_test = spi_arr.copy()

        # If the continuous component has too few observations, a normality
        # test cannot meaningfully evaluate its fitted distribution.
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
                "message": "At least 3 non-zero accumulated-precipitation samples are required for the S-W diagnostic.",
            }

        if replace_zero_with_normal and n_zero > 0:
            rng = np.random.default_rng(random_state)
            spi_for_test[zmask] = rng.standard_normal(n_zero)
            n_replaced = n_zero

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

    def aic(self) -> dict:
        """
        Compute both log-likelihood-based and MSE-based Akaike Information Criterion (AIC)
        for the fitted distribution.

        Returns
        -------
        dict
            {
                'AIC_loglik': float,
                'AIC_mse': float
            }

        Notes
        -----
        - AIC(loglik) = -2 ln(L) + 2m   (Stagge et al. 2013; Lee et al. 2023).
            Reference: Lee, C., Seo, J., Won, J., & Kim, S. (2023). Optimal
            probability distribution and applicable minimum time-scale for daily
            standardized precipitation index time series in South Korea. Atmosphere,
            14(8), 1292. DOI: 10.3390/atmos14081292
        - AIC(MSE)    = n ln(MSE) + 2m  (Zhao et al. 2020).
            Reference: Zhao, R., Wang, H., Zhan, C., Hu, S., Ma, M., & Dong, Y. (2020).
            Comparative analysis of probability distributions for the Standardized
            Precipitation Index and drought evolution in China during 1961–2015.
            Theoretical and Applied Climatology, 139, 1363-1377. DOI: 10.1007/s00704-019-03050-0
        - Supports zero-inflated data when prob_zero=True.
        """

        data = np.asarray(self.data.dropna())
        n = np.sum(data > 0) if self.prob_zero else len(data)

        if n < 3:
            return {'AIC_loglik': np.nan, 'AIC_mse': np.nan}

        # 1. PERBAIKAN PENGHITUNGAN PARAMETER (m)
        m = 0
        name = getattr(self.dist, 'name', None)
        
        # Hitung parameter shape jika ada
        if self.pars is not None:
            m += len(self.pars)
            args = (*self.pars, self.loc, self.scale)
        else:
            args = (self.loc, self.scale)
            
        # Hitung parameter scale (selalu diestimasi)
        m += 1 
        
        # Hitung parameter loc (hanya jika TIDAK dikunci di 0)
        # Gamma, weibull_min, lognorm, fisk dikunci di floc=0 pada fitting kita
        if name not in ['gamma', 'weibull_min', 'lognorm', 'fisk']:
            m += 1 

        # Jika prob_zero=True, p0 adalah parameter yang diestimasi dari data
        # if self.prob_zero:
        #     m += 1

        aic_loglik = np.nan
        aic_mse = np.nan

        # 2. PERBAIKAN LOG-LIKELIHOOD UNTUK NILAI NOL
        try:
            if self.prob_zero:
                x_zero = data == 0.0
                x_pos = data > 0

                # Dikalikan dengan jumlah hari yang curah hujannya nol
                num_zeros = np.sum(x_zero)
                ll_zero = num_zeros * np.log(np.clip(self.p0, 1e-12, 1.0)) if num_zeros > 0 else 0.0
                
                pdf_pos = self.dist.pdf(data[x_pos], *args)
                ll_pos = np.sum(np.log(np.clip((1 - self.p0) * pdf_pos, 1e-12, None))) if np.any(x_pos) else 0.0
                
                loglik = ll_zero + ll_pos
            else:
                pdf_vals = self.dist.pdf(data, *args)
                loglik = np.sum(np.log(np.clip(pdf_vals, 1e-12, None)))

            aic_loglik = -2 * loglik + 2 * m

        except Exception as e:
            logger.warning(f"AIC(loglik) failed for {self.dist.name}: {e}")

        # AIC based on MSE (Zhao et al. 2020)
        try:
            sorted_data = np.sort(data)
            n_eff = len(sorted_data)
            F_emp = np.arange(1, n_eff + 1) / (n_eff + 1)

            # Fitted CDF
            if self.pars is not None:
                F_fit = self.dist.cdf(sorted_data, *self.pars, loc=self.loc, scale=self.scale)
            else:
                F_fit = self.dist.cdf(sorted_data, loc=self.loc, scale=self.scale)

            # Apply zero-inflation correction
            if self.prob_zero:
                F_fit = self.p0 + (1.0 - self.p0) * F_fit

            # Compute mean squared error between empirical and fitted CDFs
            mse = np.mean((F_emp - F_fit) ** 2)
            mse = np.clip(mse, 1e-12, None)

            # AIC(MSE) = n ln(MSE) + 2m
            aic_mse = n * np.log(mse) + 2 * m

        except Exception as e:
            logger.warning(f"AIC(MSE) failed for {self.dist.name}: {e}")

        return {'AIC_loglik': aic_loglik, 'AIC_mse': aic_mse}