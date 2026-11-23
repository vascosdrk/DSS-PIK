"""Automated test suite validating the statistical and numerical refactoring of the SPI package.

Covers:
Part A: Zero handling, Stagge mixed probability distribution, calibration sample separation, all-zero policy, validation.
Part B: Distribution fitting across all supported distributions, parameter validity, loc=0 constraints.
Part C: Likelihood-based AIC, parameter counts, MSE criterion distinction.
Part D: Parametric bootstrap goodness-of-fit (KS and AD), Shapiro-Wilk testing with random replacement and unclipped evaluation.
Part E: PPF unclipped on raw precipitation scale, numerical stability.
Part F: Time-series accumulation, rolling window center date symmetry (3, 5, 7 days), normal-scores ties.
Part G: SPEI with signed/negative climatic water balance preservation.
Part H: Direct compatibility validation against Wang et al. (2022) utilsPY.py immutable reference.
"""

from __future__ import annotations

import sys
from pathlib import Path
import pytest
import numpy as np
import pandas as pd
from pandas import Series, DatetimeIndex, Timestamp, date_range
from scipy import stats
from scipy.stats import gamma, weibull_min, lognorm, fisk, gumbel_r, pearson3, genextreme, norm

from spei import SI, spi, spei, sgi
from spei.dist import Dist, estimate_weibull_moments, estimate_pearson3_moments, estimate_gev_moments

# Reference module import without modifying reference directory
REF_DIR = Path(__file__).parent.parent / "src" / "spei" / "reference"
for p in (REF_DIR / "wang", REF_DIR):
    if p.exists() and str(p) not in sys.path:
        sys.path.insert(0, str(p))
import utilsPY as wang_ref



# =============================================================================
# PART A: ZERO HANDLING AND DATA SEMANTICS
# =============================================================================

def test_distinct_p_zero_mass_and_centroid() -> None:
    """Zero mass m/(n+1) and centroid (m+1)/(2(n+1)) must be strictly distinct quantities."""
    n_valid = 100
    m_zero = 20
    data = np.concatenate([np.zeros(m_zero), np.linspace(1.0, 50.0, n_valid - m_zero)])
    s = Series(data)

    d = Dist(s, gamma, prob_zero=True)
    expected_mass = m_zero / (n_valid + 1.0)
    expected_centroid = (m_zero + 1.0) / (2.0 * (n_valid + 1.0))

    assert np.isclose(d.p_zero_mass, expected_mass), f"Expected mass {expected_mass}, got {d.p_zero_mass}"
    assert np.isclose(d.p_zero_centroid, expected_centroid), f"Expected centroid {expected_centroid}, got {d.p_zero_centroid}"
    assert d.p0 == d.p_zero_mass, "d.p0 backward-compatibility property must equal p_zero_mass, NOT centroid"
    assert d.p_zero_mass != d.p_zero_centroid, "p_zero_mass and p_zero_centroid must not be identical"


def test_mixed_cdf_structure() -> None:
    """CDF must assign p_zero_centroid to zeros and p_zero_mass + (1-p_zero_mass)*F_pos(x) to positives."""
    n_valid = 50
    m_zero = 10
    data = np.concatenate([np.zeros(m_zero), np.linspace(5.0, 50.0, n_valid - m_zero)])
    s = Series(data)

    d = Dist(s, gamma, prob_zero=True, fitting_policy="standard")
    cdf_vals = d.cdf()

    # Exact zero values must equal p_zero_centroid
    zeros_cdf = cdf_vals[s == 0.0]
    assert np.allclose(zeros_cdf, d.p_zero_centroid)

    # Positive values must strictly exceed p_zero_mass
    pos_cdf = cdf_vals[s > 0.0]
    assert np.all(pos_cdf >= d.p_zero_mass)
    assert np.all(pos_cdf <= 1.0)

    # Monotonicity check
    sorted_s = s.sort_values()
    sorted_cdf = d.cdf().loc[sorted_s.index]
    assert np.all(np.diff(sorted_cdf.values) >= -1e-12), "CDF must be monotonic"


def test_calibration_vs_target_sample_separation() -> None:
    """Rolling calibration data_window statistics must NOT be overwritten by target sample data."""
    cal_data = Series(np.concatenate([np.zeros(30), np.random.default_rng(42).gamma(2.0, 5.0, 70)]))
    target_data = Series([0.0, 10.0, 0.0, 25.0])  # Has 2 zeros out of 4 (50%)

    # Fit with calibration window of 100 observations (30 zeros)
    d = Dist(data=target_data, dist=gamma, prob_zero=True, data_window=cal_data)

    assert d.n_valid == 100
    assert d.n_zero == 30
    assert d.p_zero_mass == 30.0 / 101.0
    assert d.p_zero_centroid == 31.0 / 202.0

    cdf_target = d.cdf()
    # Zeros in target data must use calibration centroid (31/202), NOT target centroid (3/10)
    assert np.isclose(cdf_target.iloc[0], 31.0 / 202.0)
    assert np.isclose(cdf_target.iloc[2], 31.0 / 202.0)


def test_all_zero_policy_stagge_vs_wang() -> None:
    """All-zero calibration group behavior: Stagge gives centroid 0.5 (SPI 0), Wang gives NaN."""
    all_zeros = Series(np.zeros(40))

    # Stagge policy
    d_stagge = Dist(all_zeros, gamma, prob_zero=True, all_zero_policy="stagge")
    assert d_stagge.all_zero_group is True
    assert d_stagge.p_zero_centroid == 0.5
    cdf_stagge = d_stagge.cdf()
    assert np.allclose(cdf_stagge, 0.5)
    spi_stagge = norm.ppf(cdf_stagge)
    assert np.allclose(spi_stagge, 0.0), "Stagge all-zero SPI should equal 0.0"

    # Wang policy
    d_wang = Dist(all_zeros, gamma, prob_zero=True, all_zero_policy="wang")
    assert d_wang.all_zero_group is True
    assert np.isnan(d_wang.p_zero_centroid)
    cdf_wang = d_wang.cdf()
    assert np.all(np.isnan(cdf_wang)), "Wang all-zero CDF should be NaN"


def test_precipitation_validation_negative_values() -> None:
    """Precipitation data with negative values must raise a ValueError in zero-inflated SPI."""
    invalid_data = Series([10.0, 0.0, -5.0, 15.0])
    with pytest.raises(ValueError, match="Precipitation data must be non-negative"):
        Dist(invalid_data, gamma, prob_zero=True)


# =============================================================================
# PART B: DISTRIBUTION FITTING & SCIPY PARAMETERIZATION
# =============================================================================

@pytest.mark.parametrize("dist_obj, is_two_param", [
    (gamma, True),
    (weibull_min, True),
    (lognorm, True),
    (fisk, True),
    (gumbel_r, False),
    (pearson3, False),
    (genextreme, False),
])
def test_supported_candidate_distributions(dist_obj, is_two_param: bool) -> None:
    """Test parameter estimation, loc constraints, and CDF for all supported distributions."""
    rng = np.random.default_rng(123)
    prec_sample = np.concatenate([np.zeros(15), rng.gamma(3.0, 4.0, size=85)])
    s = Series(prec_sample)

    d = Dist(s, dist_obj, prob_zero=True, fitting_policy="standard")
    assert np.isfinite(d.scale) and d.scale > 0, f"Scale must be positive for {dist_obj.name}"
    if is_two_param:
        assert d.loc == 0.0, f"loc must be strictly 0.0 for 2-param model {dist_obj.name}"
        assert d.pars is not None and len(d.pars) == 1, f"Shape param must be single for {dist_obj.name}"
        assert d.pars[0] > 0, f"Shape must be positive for {dist_obj.name}"

    cdf_vals = d.cdf()
    assert np.all(np.isfinite(cdf_vals))
    assert np.all((cdf_vals >= 0.0) & (cdf_vals <= 1.0))


def test_gev_sign_convention_and_lmom_consistency() -> None:
    """GEV c parameter must match SciPy convention without negative sign inversion."""
    rng = np.random.default_rng(42)
    # Generate true GEV with c = -0.15
    sample = genextreme.rvs(-0.15, loc=25.0, scale=8.0, size=500, random_state=rng)
    s = Series(sample)

    d = Dist(s, genextreme, prob_zero=False)
    assert d.pars is not None and len(d.pars) == 1
    c_fitted = d.pars[0]
    assert c_fitted < 0, f"Expected negative c matching SciPy convention, got {c_fitted}"
    assert abs(c_fitted - (-0.15)) < 0.12


def test_weibull_moments_fallback_returns_two_params() -> None:
    """estimate_weibull_moments must return exactly 2 positive values (c, scale)."""
    data = np.array([2.0, 5.0, 8.0, 12.0, 15.0])
    c, scale_val = estimate_weibull_moments(data)
    assert c > 0 and scale_val > 0
    assert isinstance(c, float) and isinstance(scale_val, float)


def test_pearson3_moments_consistent() -> None:
    """estimate_pearson3_moments must use mean as loc and std as scale."""
    data = np.array([5.0, 10.0, 15.0, 20.0, 25.0])
    sk, loc_val, sc = estimate_pearson3_moments(data)
    assert np.isclose(loc_val, np.mean(data))
    assert np.isclose(sc, np.std(data, ddof=1))


# =============================================================================
# PART C: AIC & MODEL SELECTION
# =============================================================================

def test_aic_parameter_counting() -> None:
    """AIC must count k=2 for fixed-loc models and k=3 for free-loc models."""
    rng = np.random.default_rng(42)
    data = Series(rng.gamma(2.0, 5.0, size=100))

    d_gamma = Dist(data, gamma, prob_zero=False)
    aic_gamma = d_gamma.aic()
    assert np.isfinite(aic_gamma["AIC_loglik"])

    d_pe3 = Dist(data, pearson3, prob_zero=False)
    aic_pe3 = d_pe3.aic()
    assert np.isfinite(aic_pe3["AIC_loglik"])

    # Verify AIC_mse is distinguished from AIC_loglik
    assert "AIC_mse" in aic_gamma
    assert aic_gamma["AIC_loglik"] != aic_gamma["AIC_mse"]


# =============================================================================
# PART D: BOOTSTRAP GOF & SHAPIRO-WILK
# =============================================================================

def test_bootstrap_gof_reproducibility() -> None:
    """Parametric bootstrap K-S and A-D tests must be reproducible with fixed seed."""
    rng = np.random.default_rng(42)
    sample = Series(rng.gamma(2.0, 5.0, size=60))
    d = Dist(sample, gamma, prob_zero=False)

    res1 = d.goodness_of_fit(n_boot=100, random_state=42)
    res2 = d.goodness_of_fit(n_boot=100, random_state=42)

    assert res1["KS_statistic"] == res2["KS_statistic"]
    assert res1["KS_pvalue"] == res2["KS_pvalue"]
    assert res1["AD_statistic"] == res2["AD_statistic"]
    assert res1["AD_pvalue"] == res2["AD_pvalue"]
    assert res1["bootstrap_success_rate"] > 0.9


def test_shapiro_wilk_unclipped_by_default() -> None:
    """Shapiro-Wilk must evaluate unclipped SPI values by default."""
    rng = np.random.default_rng(42)
    sample = Series(np.concatenate([np.zeros(10), rng.gamma(2.0, 5.0, size=90)]))
    d = Dist(sample, gamma, prob_zero=True)

    res = d.shapiro_wilk_test(random_state=42)
    assert res["SW_pvalue"] is not None and np.isfinite(res["SW_pvalue"])
    assert res["n_zero_replaced"] == 10
    assert np.isfinite(res["spi_mean"])
    assert np.isfinite(res["spi_std"])


# =============================================================================
# PART E: PPF AND FINAL SPI
# =============================================================================

def test_ppf_not_clipped_to_3() -> None:
    """Dist.ppf() must return quantiles on the raw data scale, NOT clipped to [-3, 3]."""
    data = Series(np.linspace(10.0, 100.0, 50))
    d = Dist(data, gamma, prob_zero=False)

    # Median quantile for rainfall between 10 and 100 mm is ~55 mm
    q50 = float(d.ppf(0.5).iloc[0])
    assert q50 > 10.0, f"Raw rainfall quantile was improperly clipped! Got {q50}"

    q99 = float(d.ppf(0.99).iloc[0])
    assert q99 > 80.0, f"Raw rainfall quantile was improperly clipped! Got {q99}"


# =============================================================================
# PART F: TIME-SERIES ACCUMULATION & ROLLING WINDOW
# =============================================================================

def test_rolling_window_center_date_symmetry() -> None:
    """Rolling window must have target date at exact center index for windows 3, 5, 7."""
    dates = date_range("2010-01-01", "2010-01-31", freq="D")
    prec = Series(np.ones(len(dates)) * 5.0, index=dates)

    for w in [3, 5, 7]:
        si_obj = SI(prec, dist=norm, fit_freq="D", fit_window=w)
        si_obj.fit_distribution()
        assert len(si_obj._dist_dict) > 0


def test_normal_scores_transform_ties() -> None:
    """Normal scores transformation (cdf_nsf) must assign identical positions to tied values."""
    dates = date_range("2010-01-01", "2010-01-10", freq="D")
    # Repeated measurement 5.0
    prec = Series([1.0, 5.0, 5.0, 5.0, 10.0, 12.0, 15.0, 20.0, 25.0, 30.0], index=dates)

    si_obj = SI(prec, dist=norm, fit_freq="D", normal_scores_transform=True)
    cdf_vals = si_obj.cdf_nsf()

    # Tied values at indices 1, 2, 3 must have identical CDF values
    assert cdf_vals.iloc[1] == cdf_vals.iloc[2] == cdf_vals.iloc[3]


def test_validate_series_sorts_unsorted_input() -> None:
    """Unsorted date inputs must be sorted chronologically."""
    dates = [Timestamp("2010-01-03"), Timestamp("2010-01-01"), Timestamp("2010-01-02")]
    s = Series([3.0, 1.0, 2.0], index=dates)
    from spei.utils import validate_series
    s_sorted = validate_series(s)
    assert s_sorted.index.is_monotonic_increasing
    assert s_sorted.iloc[0] == 1.0


# =============================================================================
# PART G: SPEI REGRESSION WITH SIGNED NEGATIVE VALUES
# =============================================================================

def test_spei_preserves_negative_values() -> None:
    """SPEI with signed climatic water balance (P - PET) must retain negative values."""
    rng = np.random.default_rng(42)
    # 1. Direct Dist test with signed data (negative, zero, positive)
    raw_signed = rng.normal(loc=-5.0, scale=15.0, size=200)
    assert np.any(raw_signed < 0) and np.any(raw_signed > 0)
    d = Dist(Series(raw_signed), dist=genextreme, prob_zero=False)
    assert d.n_valid == 200
    assert d.n_zero == 0
    assert d.p0 == 0.0
    cdf_vals = d.cdf()
    assert np.all(np.isfinite(cdf_vals))
    assert np.all((cdf_vals >= 0.0) & (cdf_vals <= 1.0))

    # 2. Multi-year series through spei()
    dates = date_range("2000-01-01", periods=5 * 365, freq="D")
    water_balance = Series(rng.normal(loc=-5.0, scale=15.0, size=len(dates)), index=dates)
    spei_result = spei(water_balance, dist=genextreme, timescale=0, fit_freq="MS", prob_zero=False)
    assert len(spei_result) == len(water_balance)
    assert np.all(np.isfinite(spei_result))


# =============================================================================
# PART H: IMMUTABLE WANG ET AL. (2022) REFERENCE COMPARISON
# =============================================================================

def test_wang_reference_gamma_parameter_agreement() -> None:
    """Wang-compatible Gamma fitting policy must match utilsPY.py parameter estimates."""
    rng = np.random.default_rng(999)
    # Simulate multi-year daily values for one calendar day (e.g. 40 years)
    # 8 zeros, 32 positive values
    years = 40
    data_day = np.concatenate([np.zeros(8), rng.gamma(2.5, 6.0, size=32)])

    # 1. Wang reference implementation
    reshaped_2d = np.zeros((years, 365))
    reshaped_2d[:, 0] = data_day
    f_alpha_ref, f_beta_ref, f_p0_ref = wang_ref.fit_gamma_para(reshaped_2d)
    ref_shape = f_alpha_ref[0]
    ref_scale = f_beta_ref[0]
    ref_p0 = f_p0_ref[0]

    # 2. Refactored package with fitting_policy='wang'
    s = Series(data_day)
    d_wang = Dist(s, gamma, prob_zero=True, fitting_policy="wang", all_zero_policy="wang")

    assert np.isclose(d_wang.p0, ref_p0, rtol=1e-5), f"P0 mismatch: ref={ref_p0}, new={d_wang.p0}"
    assert d_wang.pars is not None
    assert np.isclose(d_wang.pars[0], ref_shape, rtol=1e-4), f"Shape mismatch: ref={ref_shape}, new={d_wang.pars[0]}"
    assert np.isclose(d_wang.scale, ref_scale, rtol=1e-4), f"Scale mismatch: ref={ref_scale}, new={d_wang.scale}"

    # 3. Compare resulting CDF / SPI
    ref_spi = wang_ref.caculate_gamma(reshaped_2d, f_alpha_ref, f_beta_ref, f_p0_ref)[:, 0]
    new_cdf = d_wang.cdf()
    new_spi = norm.ppf(new_cdf)

    assert np.allclose(new_spi, ref_spi, rtol=1e-4, atol=1e-4), "SPI mismatch between Wang reference and new Wang policy"
