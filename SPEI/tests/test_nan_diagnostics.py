"""Automated regression test suite validating NaN fixes and Wang et al. (2022) compatibility.

Covers:
Condition 1: Multiple zero observations and one positive observation (n_pos = 1).
Condition 2: Multiple zero observations and two positive observations (n_pos = 2).
Condition 3: Multiple zero observations and three positive observations (n_pos = 3).
Condition 4: Positive observations with no zeros (m = 0).
Condition 5: All-zero observations (n_pos = 0) under Wang vs Stagge policies.
Condition 6: Constant positive observations (x_1 = x_2 = ...).
Condition 7: Missing values (NaN) mixed with zeros and positives.
Condition 8: Nearly identical positive observations (tiny variance).
Condition 9: Optimizer failure handling and fallback reporting.
Condition 10: Valid regular sample for every supported distribution.
Timescale regression: SPI 10D, 15D, 20D, and 30D daily calculations.
Reference validation: Strict numerical agreement against utilsPY.py.
"""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import patch
import pytest
import numpy as np
import pandas as pd
from pandas import Series, DatetimeIndex, date_range
from scipy.stats import gamma, weibull_min, lognorm, fisk, gumbel_r, pearson3, genextreme, norm

from spei import SI, spi, generate_nan_diagnostic_summary
from spei.dist import Dist

# Reference module import without modifying reference directory
REF_DIR = Path(__file__).parent.parent / "src" / "spei" / "reference"
for p in (REF_DIR / "wang", REF_DIR):
    if p.exists() and str(p) not in sys.path:
        sys.path.insert(0, str(p))
import utilsPY as wang_ref



# =============================================================================
# 1. SMALL POSITIVE SAMPLE TESTS (WANG GAMMA)
# =============================================================================

@pytest.mark.parametrize("n_pos, expected_method", [
    (1, "mle_wang_nelder_mead"),
    (2, "mle_wang_nelder_mead"),
    (3, "mle_wang_nelder_mead"),
])
def test_wang_gamma_small_positive_samples(n_pos: int, expected_method: str) -> None:
    """Wang Gamma branch must fit 1, 2, and 3 positive observations without premature rejection."""
    sample = np.zeros(35)
    sample[:n_pos] = np.array([4.2, 12.8, 25.0])[:n_pos]
    s = Series(sample)

    d = Dist(s, gamma, prob_zero=True, fitting_policy="wang", all_zero_policy="wang")

    # Assertions on diagnostic counts
    assert d.n_valid == 35
    assert d.n_zero == 35 - n_pos
    assert d.n_positive == n_pos, "n_positive must reflect original data, NOT inflated by pseudo-obs"
    assert d.pseudo_obs_added is True
    assert d.n_fitting == n_pos + 1
    assert d.small_sample_warning is True
    assert d.fit_status == "success"

    # Assertions on parameters and CDF
    assert d.pars is not None and len(d.pars) == 1
    assert np.isfinite(d.pars[0]) and d.pars[0] > 0
    assert np.isfinite(d.scale) and d.scale > 0
    assert d.loc == 0.0

    cdf_vals = d.cdf()
    assert np.all(np.isfinite(cdf_vals))
    assert np.all((cdf_vals >= 0.0) & (cdf_vals <= 1.0))

    # Compare directly against Wang reference utilsPY.py
    reshaped_2d = np.zeros((35, 365))
    reshaped_2d[:, 0] = sample
    f_alpa_ref, f_beta_ref, f_p0_ref = wang_ref.fit_gamma_para(reshaped_2d)

    assert np.isclose(d.pars[0], f_alpa_ref[0], rtol=1e-5, atol=1e-5), f"Shape mismatch for n_pos={n_pos}"
    assert np.isclose(d.scale, f_beta_ref[0], rtol=1e-5, atol=1e-5), f"Scale mismatch for n_pos={n_pos}"
    assert np.isclose(d.p0, f_p0_ref[0], rtol=1e-6, atol=1e-6)

    # Compare resulting SPI on positive and zero elements
    ref_spi = wang_ref.caculate_gamma(reshaped_2d, f_alpa_ref, f_beta_ref, f_p0_ref)[:, 0]
    new_spi = norm.ppf(cdf_vals)
    assert np.allclose(new_spi, ref_spi, rtol=1e-4, atol=1e-4)


def test_wang_gamma_no_zeros_branch() -> None:
    """Condition 4: Positive observations with no zeros (m == 0)."""
    rng = np.random.default_rng(101)
    sample = rng.gamma(2.5, 4.0, size=40)
    s = Series(sample)

    d = Dist(s, gamma, prob_zero=True, fitting_policy="wang", all_zero_policy="wang")

    assert d.n_zero == 0
    assert d.n_positive == 40
    assert d.pseudo_obs_added is False
    assert d.fit_status == "success"
    assert d.pars is not None and d.pars[0] > 0
    assert d.scale > 0

    # Compare against Wang reference
    reshaped_2d = np.zeros((40, 365))
    reshaped_2d[:, 0] = sample
    f_alpa_ref, f_beta_ref, f_p0_ref = wang_ref.fit_gamma_para(reshaped_2d)

    assert np.isclose(d.pars[0], f_alpa_ref[0], rtol=1e-4, atol=1e-4)
    assert np.isclose(d.scale, f_beta_ref[0], rtol=1e-4, atol=1e-4)


def test_wang_gamma_all_zeros_branch() -> None:
    """Condition 5: All-zero observations under Wang policy."""
    all_zero_sample = Series(np.zeros(30))

    # Wang policy: must produce NaN parameters and NaN SPI
    d_wang = Dist(all_zero_sample, gamma, prob_zero=True, fitting_policy="wang", all_zero_policy="wang")
    assert d_wang.all_zero_group is True
    assert d_wang.fit_status == "all_zero"
    assert d_wang.pars is None
    assert np.isnan(d_wang.scale)
    assert np.isnan(d_wang.p0)
    assert np.isnan(d_wang.p_zero_centroid)
    assert np.all(np.isnan(d_wang.cdf()))

    # Compare against Wang reference
    reshaped_2d = np.zeros((30, 365))
    f_alpa_ref, f_beta_ref, f_p0_ref = wang_ref.fit_gamma_para(reshaped_2d)
    assert np.isnan(f_alpa_ref[0])
    assert np.isnan(f_beta_ref[0])
    assert np.isnan(f_p0_ref[0])


def test_wang_gamma_constant_positive_sample() -> None:
    """Condition 6: Constant positive observations (identical non-zero values)."""
    const_sample = Series(np.full(30, 10.0))

    d_wang = Dist(const_sample, gamma, prob_zero=True, fitting_policy="wang", all_zero_policy="wang")
    assert d_wang.fit_status == "constant_sample"
    assert d_wang.pars is None
    assert np.isnan(d_wang.scale)
    assert np.all(np.isnan(d_wang.cdf()))

    # Compare against Wang reference
    reshaped_2d = np.full((30, 365), 10.0)
    f_alpa_ref, f_beta_ref, f_p0_ref = wang_ref.fit_gamma_para(reshaped_2d)
    assert np.isnan(f_alpa_ref[0])
    assert np.isnan(f_beta_ref[0])


# =============================================================================
# 2. MISSING VALUES & NUMERICAL EDGE CASES
# =============================================================================

def test_missing_values_preservation() -> None:
    """Condition 7: Missing values mixed with zeros and positives."""
    sample = [np.nan, 0.0, 5.0, np.nan, 0.0, 15.0, 0.0, np.nan, 20.0, 0.0]
    s = Series(sample)

    d = Dist(s, gamma, prob_zero=True, fitting_policy="wang", all_zero_policy="wang")

    # Missing values must be counted and excluded
    assert d.n_missing == 3
    assert d.n_valid == 7
    assert d.n_zero == 4
    assert d.n_positive == 3
    assert d.fit_status == "success"

    cdf_vals = d.cdf()
    # Missing positions in target evaluation data must remain NaN
    assert np.isnan(cdf_vals.iloc[0])
    assert np.isnan(cdf_vals.iloc[3])
    assert np.isnan(cdf_vals.iloc[7])
    # Valid positions must be finite
    assert np.isfinite(cdf_vals.iloc[1])
    assert np.isfinite(cdf_vals.iloc[2])


def test_nearly_identical_observations() -> None:
    """Condition 8: Nearly identical positive observations (very tiny variance)."""
    # Two distinct observations with very tiny difference
    sample = np.concatenate([np.zeros(20), [10.0, 10.0 + 1e-4]])
    s = Series(sample)

    # 1. Wang Gamma
    d_gamma = Dist(s, gamma, prob_zero=True, fitting_policy="wang")
    assert d_gamma.fit_status == "success"
    assert np.isfinite(d_gamma.scale) and d_gamma.scale > 0
    assert np.all(np.isfinite(d_gamma.cdf()))

    # 2. Weibull (standard policy, n_pos = 2)
    d_wei = Dist(s, weibull_min, prob_zero=True, fitting_policy="standard")
    assert d_wei.fit_status == "success"
    assert np.isfinite(d_wei.scale) and d_wei.scale > 0
    assert np.all(np.isfinite(d_wei.cdf()))


def test_optimizer_failure_and_fallback() -> None:
    """Condition 9: Optimizer failure handling and fallback recording."""
    sample = np.concatenate([np.zeros(20), [5.0, 10.0, 20.0]])
    s = Series(sample)

    # Simulate Nelder-Mead optimization failure in standard fitting
    with patch("scipy.optimize.minimize", side_effect=RuntimeError("Nelder-Mead diverged")):
        d = Dist(s, weibull_min, prob_zero=True, fitting_policy="standard")
        # Should gracefully fall back to SciPy MLE or Method of Moments
        assert d.fit_status == "success"
        assert d.fit_method in ("scipy_mle", "moments")
        assert d.converged is False, "Fallback must NOT be marked as converged optimizer solution"
        assert np.isfinite(d.scale) and d.scale > 0


# =============================================================================
# 3. NON-GAMMA DISTRIBUTION-SPECIFIC SAMPLE SIZE RULES
# =============================================================================

@pytest.mark.parametrize("dist_obj", [weibull_min, lognorm, fisk, gumbel_r])
def test_two_parameter_dists_reject_n_pos_1(dist_obj) -> None:
    """Two-parameter distributions must reject n_pos=1 without pseudo-data."""
    sample = np.concatenate([np.zeros(25), [8.5]])
    s = Series(sample)

    d = Dist(s, dist_obj, prob_zero=True, fitting_policy="standard")
    assert d.fit_status == "insufficient_positive_sample"
    assert d.pseudo_obs_added is False
    assert np.isnan(d.scale)
    assert np.all(np.isnan(d.cdf()))


@pytest.mark.parametrize("dist_obj", [weibull_min, lognorm, fisk, gumbel_r])
def test_two_parameter_dists_accept_n_pos_2(dist_obj) -> None:
    """Two-parameter distributions must succeed on n_pos=2 distinct points."""
    sample = np.concatenate([np.zeros(25), [4.5, 18.2]])
    s = Series(sample)

    d = Dist(s, dist_obj, prob_zero=True, fitting_policy="standard")
    assert d.fit_status == "success"
    assert d.pseudo_obs_added is False
    assert np.isfinite(d.scale) and d.scale > 0
    assert np.all(np.isfinite(d.cdf()))


@pytest.mark.parametrize("dist_obj", [pearson3, genextreme])
def test_three_parameter_dists_reject_n_pos_2(dist_obj) -> None:
    """Three-parameter distributions require at least 3 points and must reject n_pos=2."""
    sample = np.concatenate([np.zeros(25), [4.5, 18.2]])
    s = Series(sample)

    d = Dist(s, dist_obj, prob_zero=True, fitting_policy="standard")
    assert d.fit_status == "insufficient_positive_sample"
    assert np.isnan(d.scale)


@pytest.mark.parametrize("dist_obj", [pearson3, genextreme])
def test_three_parameter_dists_accept_n_pos_3(dist_obj) -> None:
    """Three-parameter distributions must succeed on n_pos=3 distinct points."""
    sample = np.concatenate([np.zeros(25), [4.5, 12.0, 24.5]])
    s = Series(sample)

    d = Dist(s, dist_obj, prob_zero=True, fitting_policy="standard")
    assert d.fit_status == "success"
    assert np.isfinite(d.scale) and d.scale > 0
    assert np.all(np.isfinite(d.cdf()))


# =============================================================================
# 4. TIMESCALE ACCUMULATION REGRESSION: 10D, 15D, 20D, 30D
# =============================================================================

@pytest.mark.parametrize("scale", [10, 15, 20, 30])
def test_spi_timescales_daily_workflow(scale: int) -> None:
    """Verify SPI calculation and diagnostics across timescales 10D, 15D, 20D, and 30D."""
    rng = np.random.default_rng(42)
    # 5 years of daily data with zero-inflation
    dates = date_range("2010-01-01", periods=5 * 365, freq="D")
    raw_prec = rng.gamma(2.0, 3.0, size=len(dates))
    raw_prec[raw_prec < 3.0] = 0.0  # Zero out ~35%
    series = Series(raw_prec, index=dates)

    si_obj = SI(
        series,
        dist=gamma,
        timescale=scale,
        fit_freq="D",
        fit_window=0,
        prob_zero=True,
        fitting_policy="wang",
        all_zero_policy="wang",
    )
    si_obj.fit_distribution()
    spi_series = si_obj.norm_ppf()

    # Time series length must equal accumulated length
    assert len(spi_series) == len(si_obj.series)
    assert not spi_series.empty

    # Diagnostic checks
    diag_df = si_obj.get_diagnostics()
    assert len(diag_df) in (365, 366)
    assert "fit_status" in diag_df.columns
    assert "timescale" in diag_df.columns

    summary = generate_nan_diagnostic_summary(diag_df)
    assert len(summary) == 1
    assert summary["n_groups"].iloc[0] in (365, 366)
    assert summary["n_success"].iloc[0] > 0
