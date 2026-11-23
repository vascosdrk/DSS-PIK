"""Automated unit and regression test suite for the Master Task DSPI.

Validates all 18 conditions specified in Section 10 of the Master Task:
Condition 1: Sample with many zeros and many positive values.
Condition 2: Sample with many zeros and only 1 positive value (n_pos = 1).
Condition 3: Sample with many zeros and 2 positive values (n_pos = 2).
Condition 4: Sample with many zeros and 3 positive values (n_pos = 3).
Condition 5: Sample without zeros and adequate variation (m = 0).
Condition 6: Sample with all zero observations (n_pos = 0).
Condition 7: Sample with constant positive values (zero variance).
Condition 8: Sample with missing values (NaN).
Condition 9: Sample with negative precipitation values (must raise ValueError).
Condition 10: Optimizer failure or invalid parameter handling.
Condition 11: Gumbel-R distribution parameterized strictly with two parameters (loc, scale).
Condition 12: Pearson III and GEV sample size constraints (reject n_pos < 3).
Condition 13: Mode Wang Gamma versus utilsPY reference agreement (zero diff).
Condition 14: Mode standard-strict baseline behavior.
Condition 15: Mode standard with pseudo-observation experimental behavior.
Condition 16: SPI calculation from pre-accumulated series without re-accumulation (timescale=0).
Condition 17: Leap year handling and calendar grouping consistency.
Condition 18: Consistency of NaN counts between diagnostics, CDF, and final SPI.
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

from spei.si import SI, spi, generate_nan_diagnostic_summary
from spei.dist import Dist

REF_DIR = Path(__file__).parent.parent / "src" / "spei" / "reference"
for p in (REF_DIR / "wang", REF_DIR):
    if p.exists() and str(p) not in sys.path:
        sys.path.insert(0, str(p))
import utilsPY as wang_ref



# =============================================================================
# CONDITION 1: MANY ZEROS AND MANY POSITIVE VALUES
# =============================================================================

@pytest.mark.parametrize("dist_obj", [gamma, weibull_min, gumbel_r, lognorm, fisk, pearson3, genextreme])
def test_condition_1_many_zeros_many_positives(dist_obj):
    """Mixed sample with 20 zeros and 20 positive values has adequate data for all distributions."""
    rng = np.random.default_rng(42)
    pos = rng.gamma(2.0, 5.0, size=20) + 1.0
    sample = np.concatenate([np.zeros(20), pos])
    s = Series(sample)

    d = Dist(s, dist_obj, prob_zero=True, small_sample_policy="strict")
    assert d.fit_status == "success"
    assert d.scale > 0.0
    assert np.all(np.isfinite(d.cdf()))
    assert np.all((d.cdf() >= 0.0) & (d.cdf() <= 1.0))
    # Verify separation of zero-mass and centroid
    assert np.isclose(d.p_zero_mass, 20.0 / 41.0)
    assert np.isclose(d.p_zero_centroid, 21.0 / 82.0)


# =============================================================================
# CONDITION 2: MANY ZEROS AND ONLY 1 POSITIVE VALUE (n_pos = 1)
# =============================================================================

@pytest.mark.parametrize("dist_obj", [gumbel_r, weibull_min, lognorm, fisk])
def test_condition_2_one_positive_strict_vs_experimental(dist_obj):
    """Strict baseline rejects n_pos = 1 as underdetermined; experimental pseudo-obs allows fitting."""
    sample = np.zeros(25)
    sample[10] = 18.5
    s = Series(sample)

    # Strict: must fail with insufficient_positive_sample
    d_strict = Dist(s, dist_obj, prob_zero=True, small_sample_policy="strict")
    assert d_strict.fit_status == "insufficient_positive_sample"
    assert d_strict.cdf().isna().all()

    # Experimental: adds pseudo-obs min*0.01, allowing 2-parameter fit
    d_exp = Dist(s, dist_obj, prob_zero=True, small_sample_policy="pseudo_observation_experimental")
    assert d_exp.fit_status == "success"
    assert d_exp.pseudo_obs_added is True
    assert d_exp.scale > 0.0
    assert np.all(np.isfinite(d_exp.cdf()))


# =============================================================================
# CONDITION 3: MANY ZEROS AND 2 POSITIVE VALUES (n_pos = 2)
# =============================================================================

def test_condition_3_two_positives_two_param_vs_three_param():
    """2-parameter distributions succeed on n_pos = 2; 3-parameter distributions fail under strict."""
    sample = np.zeros(30)
    sample[5] = 12.0
    sample[15] = 28.0
    s = Series(sample)

    # 2-parameter (Gumbel-R) succeeds
    d_gumbel = Dist(s, gumbel_r, prob_zero=True, small_sample_policy="strict")
    assert d_gumbel.fit_status == "success"
    assert np.all(np.isfinite(d_gumbel.cdf()))

    # 3-parameter (Pearson III) fails under strict (2 < 3)
    d_pe3 = Dist(s, pearson3, prob_zero=True, small_sample_policy="strict")
    assert d_pe3.fit_status == "insufficient_positive_sample"
    assert d_pe3.cdf().isna().all()


# =============================================================================
# CONDITION 4: MANY ZEROS AND 3 POSITIVE VALUES (n_pos = 3)
# =============================================================================

@pytest.mark.parametrize("dist_obj", [gamma, weibull_min, gumbel_r, pearson3, genextreme])
def test_condition_4_three_positives_all_succeed(dist_obj):
    """3 positive distinct values provide enough degrees of freedom for both 2- and 3-parameter dists."""
    sample = np.concatenate([np.zeros(25), [6.0, 15.0, 32.0]])
    s = Series(sample)

    d = Dist(s, dist_obj, prob_zero=True, small_sample_policy="strict")
    assert d.fit_status == "success"
    assert d.scale > 0.0
    assert np.all(np.isfinite(d.cdf()))


# =============================================================================
# CONDITION 5: SAMPLE WITHOUT ZEROS (m = 0)
# =============================================================================

def test_condition_5_no_zeros_branch():
    """When m = 0, no zero adjustment is made; p_zero_mass = 0.0 and no pseudo-obs added."""
    rng = np.random.default_rng(99)
    sample = rng.gamma(3.0, 4.0, size=35) + 2.0
    s = Series(sample)

    d = Dist(s, gamma, prob_zero=True, fitting_policy="wang")
    assert d.n_zero == 0
    assert d.n_positive == 35
    assert d.pseudo_obs_added is False
    assert d.p_zero_mass == 0.0
    assert d.fit_status == "success"


# =============================================================================
# CONDITION 6: ALL ZERO OBSERVATIONS (n_pos = 0)
# =============================================================================

def test_condition_6_all_zero_observations():
    """All-zero calibration group handled consistently according to policy."""
    s = Series(np.zeros(30))

    # Stagge policy assigns centroid 0.5 -> SPI = 0.0
    d_stagge = Dist(s, gamma, prob_zero=True, all_zero_policy="stagge")
    assert d_stagge.fit_status == "all_zero"
    assert d_stagge.p_zero_centroid == 0.5
    assert np.allclose(norm.ppf(d_stagge.cdf()), 0.0)

    # Wang policy sets degenerate NaN
    d_wang = Dist(s, gamma, prob_zero=True, all_zero_policy="wang")
    assert d_wang.fit_status == "all_zero"
    assert np.isnan(d_wang.p_zero_centroid)
    assert d_wang.cdf().isna().all()


# =============================================================================
# CONDITION 7: CONSTANT POSITIVE VALUES
# =============================================================================

def test_condition_7_constant_positive_values():
    """Positive observations with zero variance cannot identify scale/shape; must flag constant_sample."""
    sample = np.zeros(25)
    sample[5:15] = 14.2
    s = Series(sample)

    d = Dist(s, weibull_min, prob_zero=True)
    assert d.fit_status == "constant_sample"
    assert d.cdf().isna().all()


# =============================================================================
# CONDITION 8: MISSING VALUES (NaN)
# =============================================================================

def test_condition_8_missing_values_handled_cleanly():
    """Missing values must be excluded from valid observations without silent index corruption."""
    sample = np.array([np.nan, 0.0, 5.0, np.nan, 12.0, 0.0, 20.0, np.nan])
    s = Series(sample)

    d = Dist(s, gamma, prob_zero=True)
    assert len(s) == 8
    assert d.n_missing == 3
    assert d.n_valid == 5
    assert d.n_zero == 2
    assert d.n_positive == 3
    assert d.fit_status == "success"


# =============================================================================
# CONDITION 9: NEGATIVE PRECIPITATION VALUES (MUST BE REJECTED)
# =============================================================================

def test_condition_9_negative_precipitation_rejected():
    """Precipitation data cannot contain materially negative values; ValueError must be raised."""
    sample = np.array([0.0, 5.0, -2.5, 12.0])
    s = Series(sample)

    with pytest.raises(ValueError, match="Precipitation data must be non-negative"):
        Dist(s, gamma, prob_zero=True)


# =============================================================================
# CONDITION 10: OPTIMIZER FAILURE & FALLBACK REPORTING
# =============================================================================

def test_condition_10_optimizer_failure_and_fallback():
    """When Nelder-Mead fails, moments fallback is accurately marked; when all fail, optimizer_failed is flagged."""
    sample = np.concatenate([np.zeros(10), np.array([4.0, 11.0, 19.0, 30.0])])
    s = Series(sample)

    # Fallback reporting
    with patch("spei.dist.optimize.minimize") as mock_opt, \
         patch("spei.dist.lm_distr", None), \
         patch.object(gumbel_r, "fit", side_effect=Exception("SciPy fit failed")):
        mock_opt.return_value.success = False
        mock_opt.return_value.x = np.array([np.nan, np.nan])

        d_fb = Dist(s, gumbel_r, prob_zero=True)
        assert d_fb.fit_status == "success"
        assert d_fb.fit_method == "moments"
        assert d_fb.converged is False

    # Complete failure
    with patch("spei.dist.optimize.minimize") as mock_opt, \
         patch("spei.dist.lm_distr", None), \
         patch.object(gumbel_r, "fit", side_effect=Exception("SciPy fit failed")), \
         patch("spei.dist.estimate_gumbel_moments", return_value=(np.nan, -1.0)):
        mock_opt.return_value.success = False
        mock_opt.return_value.x = np.array([np.nan, np.nan])

        d_fail = Dist(s, gumbel_r, prob_zero=True)
        assert d_fail.fit_status in ["optimizer_failed", "invalid_parameters"]
        assert d_fail.cdf().isna().all()


# =============================================================================
# CONDITION 11: GUMBEL-R STRICT TWO-PARAMETER FORMULATION
# =============================================================================

def test_condition_11_gumbel_r_two_parameters():
    """Gumbel-R must strictly have loc and scale (no extra shape parameters)."""
    sample = np.concatenate([np.zeros(15), np.array([5.0, 12.0, 18.0, 25.0, 35.0])])
    s = Series(sample)

    d = Dist(s, gumbel_r, prob_zero=True)
    assert d.pars is None
    assert np.isfinite(d.loc)
    assert np.isfinite(d.scale) and d.scale > 0.0


# =============================================================================
# CONDITION 12: PEARSON III & GEV SAMPLE SIZE CONSTRAINTS
# =============================================================================

@pytest.mark.parametrize("dist_obj", [pearson3, genextreme])
def test_condition_12_three_parameter_sample_constraints(dist_obj):
    """3-parameter distributions must reject n_pos = 1 and n_pos = 2 under strict baseline."""
    s1 = Series(np.concatenate([np.zeros(20), [15.0]]))
    s2 = Series(np.concatenate([np.zeros(20), [10.0, 25.0]]))

    d1 = Dist(s1, dist_obj, prob_zero=True, small_sample_policy="strict")
    assert d1.fit_status == "insufficient_positive_sample"
    assert d1.cdf().isna().all()

    d2 = Dist(s2, dist_obj, prob_zero=True, small_sample_policy="strict")
    assert d2.fit_status == "insufficient_positive_sample"
    assert d2.cdf().isna().all()


# =============================================================================
# CONDITION 13: WANG GAMMA VERSUS UTILS_PY NUMERICAL AGREEMENT
# =============================================================================

def test_condition_13_wang_gamma_versus_utilspy():
    """Mode Wang Gamma must produce identical numerical parameters and SPI compared to utilsPY."""
    sample = np.concatenate([np.zeros(15), [4.2, 11.5, 22.0, 38.0]])
    s = Series(sample)

    # Package Wang mode
    d_pkg = Dist(s, gamma, prob_zero=True, fitting_policy="wang", all_zero_policy="wang")
    pkg_cdf = d_pkg.cdf()
    pkg_spi = norm.ppf(pkg_cdf)

    # utilsPY reference
    reshaped_2d = np.zeros((len(sample), 365))
    reshaped_2d[:, 0] = sample
    f_alpa, f_beta, f_p0 = wang_ref.fit_gamma_para(reshaped_2d)
    w_spi = wang_ref.caculate_gamma(reshaped_2d, f_alpa, f_beta, f_p0)[:, 0]

    assert np.isclose(d_pkg.pars[0], f_alpa[0], rtol=1e-5, atol=1e-5)
    assert np.isclose(d_pkg.scale, f_beta[0], rtol=1e-5, atol=1e-5)
    assert np.isclose(d_pkg.p0, f_p0[0], rtol=1e-6, atol=1e-6)
    assert np.allclose(pkg_spi, w_spi, rtol=1e-4, atol=1e-4)


# =============================================================================
# CONDITION 14: STANDARD-STRICT BASELINE
# =============================================================================

def test_condition_14_standard_strict_mode():
    """Standard-strict mode never adds pseudo-observations and enforces rigorous identification."""
    sample = np.zeros(30)
    sample[5] = 15.0  # n_pos = 1
    s = Series(sample)

    d = Dist(s, gamma, prob_zero=True, fitting_policy="standard", small_sample_policy="strict")
    assert d.pseudo_obs_added is False
    assert d.fit_status == "insufficient_positive_sample"
    assert d.cdf().isna().all()


# =============================================================================
# CONDITION 15: STANDARD EXPERIMENTAL PSEUDO-OBSERVATION
# =============================================================================

def test_condition_15_standard_experimental_mode():
    """Experimental mode adds pseudo-observation min*0.01 for 1 <= n_pos <= 3 with transparent metadata."""
    sample = np.zeros(30)
    sample[5] = 15.0  # n_pos = 1
    s = Series(sample)

    d = Dist(s, gamma, prob_zero=True, fitting_policy="standard", small_sample_policy="pseudo_observation_experimental")
    assert d.pseudo_obs_added is True
    assert d.small_sample_warning is True
    assert d.n_fitting == 2
    assert d.fit_status == "success"
    assert np.all(np.isfinite(d.cdf()))


# =============================================================================
# CONDITION 16: PRE-ACCUMULATED SERIES WITHOUT RE-ACCUMULATION (timescale=0)
# =============================================================================

def test_condition_16_timescale_zero_preaccumulated():
    """timescale=0 prevents re-accumulation of already rolled series."""
    rng = np.random.default_rng(77)
    dates = date_range("2015-01-01", periods=1000, freq="D")
    raw_s = Series(rng.gamma(2.0, 3.0, size=len(dates)), index=dates)
    rolled_10 = raw_s.rolling(10, min_periods=10).sum().dropna()

    si_obj = SI(rolled_10, dist=gamma, timescale=0, fit_freq="D", prob_zero=True)
    # Length of series inside SI must remain identical to input rolled_10
    assert len(si_obj.series) == len(rolled_10)
    assert np.allclose(si_obj.series.values, rolled_10.values)


# =============================================================================
# CONDITION 17: LEAP YEAR HANDLING & CALENDAR GROUPING CONSISTENCY
# =============================================================================

def test_condition_17_leap_year_calendar_grouping():
    """Daily grouping respects leap day (Feb 29), yielding 366 distinct calendar groups across leap cycles."""
    # 8-year span covering leap years 2012 and 2016
    dates = date_range("2012-01-01", "2019-12-31", freq="D")
    s = Series(np.ones(len(dates)) * 5.0, index=dates)

    si_obj = SI(s, dist=gamma, timescale=0, fit_freq="D", prob_zero=False)
    si_obj.fit_distribution()
    diag = si_obj.get_diagnostics()

    assert len(diag) == 366
    assert "02-29" in diag["calendar_day"].values
    # Check that Feb 29 has 2 observations (2012 and 2016)
    row_feb29 = diag[diag["calendar_day"] == "02-29"].iloc[0]
    assert row_feb29["n_valid"] == 2


# =============================================================================
# CONDITION 18: NaN CONSISTENCY BETWEEN DIAGNOSTICS, CDF, AND SPI
# =============================================================================

def test_condition_18_nan_consistency_across_pipeline():
    """NaN count in final SPI must match exact calendar group failures in diagnostics."""
    rng = np.random.default_rng(123)
    # 4 years daily data
    dates = date_range("2011-01-01", periods=4 * 365, freq="D")
    raw = rng.gamma(2.0, 4.0, size=len(dates))
    # Make calendar day "08-25" have only 1 positive value across the 4 years
    series = Series(raw, index=dates)
    mask_aug25 = (series.index.month == 8) & (series.index.day == 25)
    # Zero out all except year 2011
    series.loc[mask_aug25 & (series.index.year != 2011)] = 0.0
    series.loc[mask_aug25 & (series.index.year == 2011)] = 15.0

    si_obj = SI(series, dist=gumbel_r, timescale=0, fit_freq="D", prob_zero=True, small_sample_policy="strict")
    si_obj.fit_distribution()
    spi_res = si_obj.norm_ppf()
    diag = si_obj.get_diagnostics()

    # In diagnostics, 08-25 must have fit_status == "insufficient_positive_sample"
    aug25_row = diag[diag["calendar_day"] == "08-25"].iloc[0]
    assert aug25_row["fit_status"] == "insufficient_positive_sample"
    assert aug25_row["n_positive"] == 1

    # In SPI output, exactly the occurrences of 08-25 (n=4) and 02-29 (n=1, single leap year) are NaN
    nan_dates = spi_res[spi_res.isna()].index
    assert len(nan_dates) == 5
    assert set(nan_dates.strftime("%m-%d")) == {"08-25", "02-29"}
