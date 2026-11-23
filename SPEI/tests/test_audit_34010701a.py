"""Automated test suite specifically addressing the audit of daily SPI distribution fitting.

Validates the 8 conditions specified in Section 7 of the audit:
Condition 1: Sample with many zeros and many positive values (standard mixed climate).
Condition 2: Sample with many zeros and only 1 positive value (n_pos = 1).
Condition 3: Sample with many zeros and 2 positive values (n_pos = 2).
Condition 4: Sample with all zero observations (n_pos = 0).
Condition 5: Sample with constant positive values (zero variance).
Condition 6: Sample with purely positive values and adequate variance.
Condition 7: Sample containing missing values (NaN).
Condition 8: Optimization failure and invalid parameter handling.

Verifies:
- Parameter count and mapping for every supported candidate distribution.
- Accurate fit_status and failure reasons.
- Positive scale and valid parameter bounds.
- Separation of p_zero_mass from p_zero_centroid.
- NaN handling consistent with underlying causes.
- Strict baseline vs experimental pseudo-observation policy behaviors.
"""

from __future__ import annotations

import pytest
import numpy as np
import pandas as pd
from pandas import Series
from scipy.stats import gumbel_r, gamma, weibull_min, lognorm, fisk, pearson3, genextreme, norm
from unittest.mock import patch

from spei.dist import Dist
from spei.si import SI, spi


# =============================================================================
# CONDITION 1: MANY ZEROS AND MANY POSITIVES (STANDARD MIXED SAMPLE)
# =============================================================================

@pytest.mark.parametrize("dist_obj, expected_params", [
    (gumbel_r, 2),
    (gamma, 2),
    (weibull_min, 2),
    (lognorm, 2),
    (fisk, 2),
    (pearson3, 3),
    (genextreme, 3),
])
def test_condition_1_many_zeros_many_positives(dist_obj, expected_params):
    """Mixed sample with 20 zeros and 20 positive values has adequate data for all distributions."""
    rng = np.random.default_rng(42)
    pos_data = rng.gamma(2.0, 5.0, size=20) + 1.0
    sample = np.concatenate([np.zeros(20), pos_data])
    s = Series(sample)

    d = Dist(s, dist_obj, prob_zero=True, small_sample_policy="strict")

    assert d.n_valid == 40
    assert d.n_zero == 20
    assert d.n_positive == 20
    assert d.n_fitting == 20
    assert d.pseudo_obs_added is False
    assert d.fit_status == "success"
    assert d.scale > 0.0

    # Verify parameter mapping per distribution
    if dist_obj == gumbel_r:
        assert d.pars is None
        assert np.isfinite(d.loc) and np.isfinite(d.scale)
    elif dist_obj in [gamma, weibull_min, lognorm, fisk]:
        assert d.pars is not None and len(d.pars) == 1
        assert d.loc == 0.0  # Fixed location for 2-parameter distributions
        assert np.isfinite(d.scale)
    elif dist_obj in [pearson3, genextreme]:
        assert d.pars is not None and len(d.pars) == 1
        assert np.isfinite(d.loc) and np.isfinite(d.scale)

    # Check separation of p_zero_mass (m / (n + 1)) and p_zero_centroid ((m + 1) / (2(n + 1)))
    expected_mass = 20.0 / (40.0 + 1.0)
    expected_centroid = (20.0 + 1.0) / (2.0 * (40.0 + 1.0))
    assert np.isclose(d.p_zero_mass, expected_mass, rtol=1e-5)
    assert np.isclose(d.p_zero_centroid, expected_centroid, rtol=1e-5)
    assert not np.isclose(d.p_zero_mass, d.p_zero_centroid)

    # CDF should be strictly within [0, 1]
    cdf_vals = d.cdf()
    assert np.all(np.isfinite(cdf_vals))
    assert np.all((cdf_vals >= 0.0) & (cdf_vals <= 1.0))


# =============================================================================
# CONDITION 2: MANY ZEROS AND ONLY ONE POSITIVE VALUE (n_pos = 1)
# =============================================================================

@pytest.mark.parametrize("dist_obj", [gumbel_r, weibull_min, lognorm, fisk])
def test_condition_2_one_positive_strict_vs_experimental(dist_obj):
    """Under strict policy, 2-parameter distributions reject n_pos = 1 as insufficient.
    Under experimental pseudo-observation policy, an extra pseudo-observation allows fitting."""
    sample = np.zeros(30)
    sample[5] = 15.0
    s = Series(sample)

    # 1. Strict baseline policy
    d_strict = Dist(s, dist_obj, prob_zero=True, small_sample_policy="strict")
    assert d_strict.n_positive == 1
    assert d_strict.pseudo_obs_added is False
    assert d_strict.fit_status == "insufficient_positive_sample"
    cdf_strict = d_strict.cdf()
    assert cdf_strict.isna().all()

    # 2. Augmented policy (and legacy alias backward compatibility)
    d_exp = Dist(s, dist_obj, prob_zero=True, small_sample_policy="augmented")
    assert d_exp.n_positive == 1
    assert d_exp.pseudo_obs_added is True
    assert d_exp.n_fitting == 2
    assert d_exp.small_sample_warning is True
    assert d_exp.fit_status == "success"
    assert d_exp.scale > 0.0

    cdf_exp = d_exp.cdf()
    assert np.all(np.isfinite(cdf_exp))
    assert np.all((cdf_exp >= 0.0) & (cdf_exp <= 1.0))

    # Also test legacy alias
    d_legacy = Dist(s, dist_obj, prob_zero=True, small_sample_policy="pseudo_observation_experimental")
    assert d_legacy.fit_status == "success"


@pytest.mark.parametrize("dist_obj", [pearson3, genextreme])
def test_condition_2_three_param_dists_reject_one_positive(dist_obj):
    """3-parameter distributions must reject n_pos = 1 even with 1 pseudo-obs because 2 < 3."""
    sample = np.zeros(30)
    sample[10] = 20.0
    s = Series(sample)

    d_exp = Dist(s, dist_obj, prob_zero=True, small_sample_policy="augmented")
    assert d_exp.fit_status in ["insufficient_positive_sample", "insufficient_effective_sample"]
    assert d_exp.cdf().isna().all()


# =============================================================================
# CONDITION 3: MANY ZEROS AND TWO POSITIVE VALUES (n_pos = 2)
# =============================================================================

def test_condition_3_two_positives_two_param_dists():
    """2-parameter distributions like Gumbel-R have 2 data points, enough for 2 parameters."""
    sample = np.zeros(30)
    sample[3] = 8.0
    sample[18] = 25.0
    s = Series(sample)

    d_strict = Dist(s, gumbel_r, prob_zero=True, small_sample_policy="strict")
    assert d_strict.n_positive == 2
    assert d_strict.pseudo_obs_added is False
    assert d_strict.fit_status == "success"
    assert d_strict.scale > 0.0
    assert np.isfinite(d_strict.loc)
    assert np.all(np.isfinite(d_strict.cdf()))


@pytest.mark.parametrize("dist_obj", [pearson3, genextreme])
def test_condition_3_two_positives_three_param_dists(dist_obj):
    """3-parameter distributions fail on n_pos = 2 under strict (2 < 3), but succeed with pseudo-obs (3 >= 3)."""
    sample = np.zeros(30)
    sample[5] = 10.0
    sample[20] = 30.0
    s = Series(sample)

    # Strict: insufficient sample for 3 parameters
    d_strict = Dist(s, dist_obj, prob_zero=True, small_sample_policy="strict")
    assert d_strict.fit_status == "insufficient_positive_sample"
    assert d_strict.cdf().isna().all()

    # Augmented: n_fitting = 3 allows 3 parameters to fit
    d_exp = Dist(s, dist_obj, prob_zero=True, small_sample_policy="augmented")
    assert d_exp.pseudo_obs_added is True
    assert d_exp.n_fitting == 3
    assert d_exp.fit_status == "success"
    assert d_exp.scale > 0.0
    assert np.all(np.isfinite(d_exp.cdf()))


# =============================================================================
# CONDITION 4: ALL-ZERO SAMPLE (n_pos = 0)
# =============================================================================

def test_condition_4_all_zero_sample_wang_vs_stagge():
    """All-zero samples: Stagge policy assigns centroid 0.5; Wang policy marks all_zero with NaN."""
    s = Series(np.zeros(25))

    # Stagge policy sets p_zero_centroid = 0.5 and CDF = 0.5 (SPI = 0.0)
    d_stagge = Dist(s, gamma, prob_zero=True, all_zero_policy="stagge")
    assert d_stagge.n_positive == 0
    assert d_stagge.all_zero_group is True
    assert d_stagge.fit_status == "all_zero"
    assert d_stagge.p_zero_centroid == 0.5
    cdf_stagge = d_stagge.cdf()
    assert np.allclose(cdf_stagge, 0.5)
    assert np.allclose(norm.ppf(cdf_stagge), 0.0)

    # Wang policy treats pure all-zero group as degenerate NaN in CDF
    d_wang = Dist(s, gamma, prob_zero=True, all_zero_policy="wang")
    assert d_wang.n_positive == 0
    assert d_wang.all_zero_group is True
    assert d_wang.fit_status == "all_zero"
    assert np.isnan(d_wang.p_zero_centroid)
    assert d_wang.cdf().isna().all()


# =============================================================================
# CONDITION 5: CONSTANT POSITIVE OBSERVATIONS (ZERO VARIANCE)
# =============================================================================

@pytest.mark.parametrize("dist_obj", [gumbel_r, gamma, weibull_min])
def test_condition_5_constant_positive_sample(dist_obj):
    """When all positive observations are identical, MLE cannot identify scale/shape; must flag constant_sample."""
    sample = np.zeros(25)
    sample[5:15] = 12.5  # 10 identical positive values
    s = Series(sample)

    d = Dist(s, dist_obj, prob_zero=True)
    assert d.fit_status == "constant_sample"
    assert d.cdf().isna().all()


# =============================================================================
# CONDITION 6: ADEQUATE POSITIVE VARIATION
# =============================================================================

@pytest.mark.parametrize("dist_obj", [gumbel_r, gamma, weibull_min, lognorm, fisk, pearson3, genextreme])
def test_condition_6_adequate_positive_variation(dist_obj):
    """All candidate distributions fit reliably when positive observations have adequate spread."""
    rng = np.random.default_rng(123)
    data = rng.weibull(1.5, size=40) * 15.0 + 0.5
    s = Series(data)

    d = Dist(s, dist_obj, prob_zero=False)
    assert d.fit_status == "success"
    assert d.scale > 0.0
    assert np.isfinite(d.loc)
    assert np.all(np.isfinite(d.cdf()))


# =============================================================================
# CONDITION 7: MISSING VALUES (NaN) IN INPUT DATA
# =============================================================================

def test_condition_7_missing_values_handled_cleanly():
    """Missing values must be excluded from valid count, not causing silent corruption."""
    sample = np.array([np.nan, 0.0, 0.0, 10.0, np.nan, 25.0, 0.0, 40.0, np.nan, 5.0])
    s = Series(sample)

    d = Dist(s, gumbel_r, prob_zero=True)
    assert len(s) == 10
    assert d.n_missing == 3
    assert d.n_valid == 7
    assert d.n_zero == 3
    assert d.n_positive == 4
    assert d.fit_status == "success"


# =============================================================================
# CONDITION 8: OPTIMIZER FAILURE & FALLBACK REPORTING
# =============================================================================

def test_condition_8_optimizer_failure_and_fallback_reporting():
    """When MLE fails, fallback is clearly reported; when all routines fail, optimizer_failed is flagged."""
    sample = np.concatenate([np.zeros(10), np.array([5.0, 12.0, 19.0, 28.0])])
    s = Series(sample)

    # Sub-case A: MLE Nelder-Mead fails, but moments fallback succeeds -> fit_method must be 'moments'
    with patch("spei.dist.optimize.minimize") as mock_opt, \
         patch("spei.dist.lm_distr", None), \
         patch.object(gumbel_r, "fit", side_effect=Exception("SciPy fit failed")):
        mock_opt.return_value.success = False
        mock_opt.return_value.x = np.array([np.nan, np.nan])

        d_fallback = Dist(s, gumbel_r, prob_zero=True)
        assert d_fallback.fit_status == "success"
        assert d_fallback.fit_method == "moments", "Fallback method must be accurately marked as 'moments'"
        assert d_fallback.converged is False

    # Sub-case B: All routines fail including moments -> fit_status must be 'optimizer_failed'
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
# STATION 34010701a VALIDATION (USING tests/data/34010701a.csv)
# =============================================================================

def test_station_34010701a_csv_dataset(prec_34010701a):
    """Validate that station 34010701a.csv loads properly with expected properties."""
    assert len(prec_34010701a) == 5479
    assert prec_34010701a.index.min() == pd.Timestamp("2010-01-01")
    assert prec_34010701a.index.max() == pd.Timestamp("2024-12-31")
    assert (prec_34010701a >= 0.0).all(), "Rainfall data must be non-negative"
    zero_ratio = (prec_34010701a == 0.0).mean()
    assert 0.50 < zero_ratio < 0.75, f"Expected 50-75% zero days, got {zero_ratio:.2%}"


def test_station_34010701a_spi_calculation(prec_34010701a):
    """Test 10-day rolling SPI on station 34010701a data with strict and augmented policies."""
    # Rolling 10-day cumulative precipitation
    rolled_10 = prec_34010701a.rolling(10, min_periods=10).sum().dropna()
    assert len(rolled_10) == 5479 - 10 + 1

    # 1. Strict operational policy with Gamma distribution
    res_strict = spi(
        rolled_10,
        dist=gamma,
        prob_zero=True,
        small_sample_policy="strict",
        all_zero_policy="wang",
    )
    assert isinstance(res_strict, Series)
    assert len(res_strict) == len(rolled_10)
    # Most values should be finite
    finite_mask = np.isfinite(res_strict)
    assert finite_mask.mean() > 0.95

    # 2. Augmented policy allows fitting across transition windows
    res_aug = spi(
        rolled_10,
        dist=gamma,
        prob_zero=True,
        small_sample_policy="augmented",
        all_zero_policy="stagge",
    )
    assert isinstance(res_aug, Series)
    # With stagge policy and augmented, finite fraction should be even higher
    assert np.isfinite(res_aug).mean() >= finite_mask.mean()

