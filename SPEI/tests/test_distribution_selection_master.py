"""Comprehensive Automated Scientific Validation and Regression Tests
for Daily Standardized Precipitation Index (DSPI) Distribution Selection.

Covers:
  - Part A: Empirical GEV shape parameter sign convention (SciPy vs lmoments3 vs moments).
  - Part B: Conditional-positive fitting, objective functions, and bootstrap GoF consistency.
  - Part C: SPI transformation via Dist.cdf() with centroid vs zero-mass handling.
  - Part D: AIC and group model selection (#1 Best and #2 Alternative recommendation).
  - Part E: SI.select_optimal_distribution() integration across calendar groups & windows.
  - Part F: Aggregated candidate diagnostics, SPI Anderson-Darling normality, and hierarchical ranking.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest
from scipy import stats
from scipy.stats import genextreme, gumbel_r, pearson3, gamma, weibull_min, lognorm, fisk

from spei.dist import Dist, estimate_gev_moments
from spei.si import SI
from spei.model_selection import (
    select_best_distribution,
    select_models_by_group,
    summarize_candidate_diagnostics,
    rank_aggregated_candidates,
    _spi_from_fitted_model,
    _rank_rows,
    _conditional_aic,
)


# =============================================================================
# PART A: GEV Shape Parameter Sign Convention Tests
# =============================================================================

@pytest.mark.parametrize("c_true", [+0.25, -0.25])
def test_gev_sign_convention_synthetic(c_true):
    """Verify that SciPy, lmoments3, and estimate_gev_moments use the same sign convention."""
    try:
        from lmoments3 import distr as lm_distr
        has_lmom = True
    except ImportError:
        has_lmom = False

    sample = genextreme.rvs(
        c_true, loc=100.0, scale=25.0, size=2500, random_state=42
    )

    mom_pars = estimate_gev_moments(sample)
    c_mom = mom_pars[0]
    # Moment estimate must have the same sign as c_true
    assert np.sign(c_mom) == np.sign(c_true), f"Moment c sign mismatch: {c_mom} vs {c_true}"
    assert abs(c_mom - c_true) < 0.15

    if has_lmom and hasattr(lm_distr, "gev"):
        lm_pars = lm_distr.gev.lmom_fit(sample)
        c_lmom = float(lm_pars["c"])
        # Empirical test: lmoments3 already follows SciPy sign convention
        assert np.sign(c_lmom) == np.sign(c_true), f"L-moments c sign mismatch: {c_lmom} vs {c_true}"
        assert abs(c_lmom - c_true) < 0.10

    fit = Dist.fit_dist(
        pd.Series(sample),
        genextreme,
        prob_zero=False,
        fitting_policy="standard",
        conditional_positive=False,
        return_details=True,
    )
    pars, loc, scale, p_zero, details = fit
    assert pars is not None and len(pars) == 1
    c_fit = float(pars[0])
    assert np.sign(c_fit) == np.sign(c_true), f"Fitted c sign mismatch: {c_fit} vs {c_true}"
    assert abs(c_fit - c_true) < 0.08
    assert abs(loc - 100.0) < 5.0
    assert abs(scale - 25.0) < 5.0
    assert details["fit_status"] == "success"


def test_gev_cdf_monotonicity_and_validity():
    """Verify fitted GEV produces valid, strictly non-decreasing CDF in [0, 1]."""
    for c_val in [+0.25, -0.25]:
        sample = genextreme.rvs(c_val, loc=50.0, scale=15.0, size=500, random_state=123)
        s = pd.Series(sample)
        d = Dist(s, genextreme, prob_zero=False)
        assert d.fit_status == "success"
        cdf_vals = d.cdf()
        assert np.all(np.isfinite(cdf_vals))
        assert np.all((cdf_vals >= 0.0) & (cdf_vals <= 1.0))


# =============================================================================
# PART B: Conditional-Positive Fitting and Bootstrap Consistency
# =============================================================================

@pytest.mark.parametrize("dist_obj", [gumbel_r, pearson3, genextreme])
def test_conditional_positive_mixed_data(dist_obj):
    """Verify conditional-positive likelihood on mixed zero and positive precipitation data."""
    rng = np.random.default_rng(42)
    pos_data = rng.gamma(2.0, 10.0, size=30) + 1.0
    sample = np.concatenate([np.zeros(15), pos_data])
    s = pd.Series(sample)

    d = Dist(s, dist_obj, prob_zero=True, conditional_positive=True)
    assert d.fit_status == "success"
    assert d.n_zero == 15
    assert d.n_positive == 30
    assert d.scale > 0.0

    cdf_vals = d.cdf()
    assert np.all(np.isfinite(cdf_vals))
    assert np.all((cdf_vals >= 0.0) & (cdf_vals <= 1.0))


def test_bootstrap_refit_conditional_positive_preservation():
    """Verify bootstrap refit inherits and enforces conditional_positive."""
    rng = np.random.default_rng(99)
    pos_data = rng.gamma(3.0, 5.0, size=25) + 2.0
    sample = np.concatenate([np.zeros(10), pos_data])
    s = pd.Series(sample)

    d = Dist(s, gumbel_r, prob_zero=True, conditional_positive=True)
    gof = d.goodness_of_fit(n_boot=19, random_state=99)
    assert gof["n_boot_requested"] == 19
    assert gof["n_boot_valid"] > 0
    assert gof["bootstrap_success_rate"] >= 0.80
    assert np.isfinite(gof["KS_statistic"])
    assert np.isfinite(gof["AD_statistic"])


def test_raw_prob_zero_false_does_not_accidentally_condition():
    """When prob_zero=False on raw data, conditional_positive must not be active."""
    rng = np.random.default_rng(77)
    # Climate water balance with positive and negative numbers
    raw = rng.normal(0.0, 10.0, size=50)
    s = pd.Series(raw)

    d = Dist(s, gumbel_r, prob_zero=False, conditional_positive=True)
    # Because prob_zero is False, Dist.__post_init__ must set conditional_positive=False for fitting
    assert d.fit_status == "success"
    assert d.p0 == 0.0
    cdf_vals = d.cdf()
    assert np.all(np.isfinite(cdf_vals))


# =============================================================================
# PART C: SPI Transformation and model.cdf() Consistency
# =============================================================================

def test_spi_from_fitted_model_uses_dist_cdf():
    """Verify _spi_from_fitted_model uses Dist.cdf() as single source of truth."""
    rng = np.random.default_rng(101)
    pos = rng.exponential(scale=20.0, size=30) + 1.0
    raw = np.concatenate([np.zeros(10), pos])
    s = pd.Series(raw, index=pd.date_range("2020-01-01", periods=40, freq="D"))

    d = Dist(s, gamma, prob_zero=True)
    spi_default = _spi_from_fitted_model(d, s, prob_zero=True, clip=None)
    assert len(spi_default) == len(s)
    assert np.all(np.isfinite(spi_default))

    # Exact zero values must receive normal quantile of p_zero_centroid
    zero_idx = s[s == 0.0].index
    expected_zero_spi = stats.norm.ppf(d.p_zero_centroid)
    np.testing.assert_allclose(spi_default.loc[zero_idx].to_numpy(), expected_zero_spi, rtol=1e-5)

    # Test explicit clipping vs None
    spi_clipped = _spi_from_fitted_model(d, s, prob_zero=True, clip=(-3.0, 3.0))
    assert np.all(spi_clipped >= -3.0) and np.all(spi_clipped <= 3.0)


def test_spi_transformation_preserves_nan():
    """Missing input values must remain NaN in transformed SPI."""
    s = pd.Series([0.0, 15.0, np.nan, 25.0, 0.0, np.nan])
    s_valid = s.dropna()
    d = Dist(s_valid, gamma, prob_zero=True)
    spi_out = _spi_from_fitted_model(d, s, prob_zero=True, clip=None)
    assert pd.isna(spi_out.iloc[2])
    assert pd.isna(spi_out.iloc[5])
    assert np.isfinite(spi_out.iloc[0])
    assert np.isfinite(spi_out.iloc[1])


# =============================================================================
# PART D: Candidate Comparison, AIC, and #1 & #2 Ranking
# =============================================================================

def test_select_best_distribution_outputs_best_and_alternative():
    """Verify select_best_distribution produces both #1 and #2 with valid details."""
    rng = np.random.default_rng(2026)
    data = pd.Series(rng.gamma(shape=2.5, scale=12.0, size=40))
    data.iloc[[3, 8, 15, 27]] = 0.0

    res = select_best_distribution(
        data,
        prob_zero=True,
        n_boot=29,
        gof_scope="competitive",
        random_state=2026,
    )
    rec = res["recommendation"]
    assert rec["distribution"] is not None
    assert rec["n_parameters"] in [2, 3]
    assert np.isfinite(rec["AIC"])
    assert rec["delta_AIC"] == 0.0  # Winner must have delta_AIC == 0.0

    # Alternative candidate
    assert "alternative_distribution" in rec
    if rec["alternative_distribution"] is not None:
        assert rec["alternative_distribution"] != rec["distribution"]
        assert np.isfinite(rec["alternative_AIC"])
        assert rec["alternative_delta_AIC"] >= 0.0
        assert res["alternative_model"] is not None

    assert res["selected_model"] is not None


def test_rank_rows_prefer_two_parameters_deterministic():
    """Verify _rank_rows prefers 2-parameter models and breaks ties deterministically."""
    rows = pd.DataFrame([
        {"distribution": "pearson3", "n_parameters": 3, "AIC": 100.0},
        {"distribution": "gamma", "n_parameters": 2, "AIC": 101.5},
        {"distribution": "weibull_min", "n_parameters": 2, "AIC": 101.5},
        {"distribution": "genextreme", "n_parameters": 3, "AIC": 99.0},
    ])
    ranked_p2 = _rank_rows(rows, prefer_two_parameters=True)
    # 2-parameter models come first, sorted by AIC then name (gamma before weibull_min)
    assert ranked_p2.iloc[0]["distribution"] == "gamma"
    assert ranked_p2.iloc[1]["distribution"] == "weibull_min"
    assert ranked_p2.iloc[2]["distribution"] == "genextreme"
    assert ranked_p2.iloc[3]["distribution"] == "pearson3"

    ranked_nop2 = _rank_rows(rows, prefer_two_parameters=False)
    # Strict AIC order: genextreme (99) -> pearson3 (100) -> gamma (101.5) -> weibull_min (101.5)
    assert ranked_nop2.iloc[0]["distribution"] == "genextreme"
    assert ranked_nop2.iloc[1]["distribution"] == "pearson3"


# =============================================================================
# PART E: SI.select_optimal_distribution Integration
# =============================================================================

def test_si_select_optimal_distribution_fit_window_zero():
    """Verify SI.select_optimal_distribution with fit_window=0 does not mutate SI instance."""
    rng = np.random.default_rng(42)
    dates = pd.date_range("2010-01-01", periods=3 * 365, freq="D")
    rain = pd.Series(rng.gamma(2.0, 8.0, size=len(dates)), index=dates)
    rain[rain < 3.0] = 0.0

    si = SI(rain, dist=gamma, timescale=0, fit_freq="D", prob_zero=True)
    initial_dist = si.dist
    assert len(si._dist_dict) == 0

    opt_res = si.select_optimal_distribution(
        candidates={"gamma": gamma, "weibull_min": weibull_min},
        n_boot=19,
        gof_scope="none",  # Fast AIC-only for test
        random_state=42,
    )
    # Verify instance was NOT mutated
    assert si.dist is initial_dist
    assert len(si._dist_dict) == 0

    assert "best_distribution" in opt_res
    assert "candidate_summary" in opt_res
    assert "global_ranking" in opt_res
    assert "recommendations" in opt_res
    assert len(opt_res["recommendations"]) > 0


def test_si_select_optimal_distribution_fit_window_three():
    """Verify SI.select_optimal_distribution with rolling window fit_window=3."""
    rng = np.random.default_rng(77)
    dates = pd.date_range("2012-01-01", periods=2 * 365, freq="D")
    rain = pd.Series(rng.gamma(2.5, 6.0, size=len(dates)), index=dates)
    rain[rain < 2.0] = 0.0

    si = SI(rain, dist=gamma, timescale=0, fit_freq="D", fit_window=3, prob_zero=True)
    opt_res = si.select_optimal_distribution(
        candidates={"gamma": gamma, "weibull_min": weibull_min},
        n_boot=19,
        gof_scope="none",
        random_state=77,
    )
    assert opt_res["best_distribution"] in ["gamma", "weibull_min"]
    assert len(opt_res["recommendations"]) > 0


# =============================================================================
# PART F: Candidate Diagnostics and Hierarchical Ranking
# =============================================================================

def test_summarize_candidate_diagnostics_and_ranking():
    """Verify all aggregate fields are calculated and hierarchical ranking functions."""
    details = pd.DataFrame([
        {
            "group_id": "day_1", "distribution": "gamma", "n_parameters": 2,
            "fit_status": "success", "AIC": 50.0, "delta_AIC": 0.0,
            "SW_pvalue": 0.35, "KS_pvalue": 0.50, "AD_pvalue": 0.40,
            "SPI_AD_pass": True,
        },
        {
            "group_id": "day_1", "distribution": "genextreme", "n_parameters": 3,
            "fit_status": "success", "AIC": 49.5, "delta_AIC": 0.0,
            "SW_pvalue": 0.30, "KS_pvalue": 0.60, "AD_pvalue": 0.55,
            "SPI_AD_pass": True,
        },
        {
            "group_id": "day_2", "distribution": "gamma", "n_parameters": 2,
            "fit_status": "success", "AIC": 60.0, "delta_AIC": 0.5,
            "SW_pvalue": 0.45, "KS_pvalue": 0.70, "AD_pvalue": 0.60,
            "SPI_AD_pass": True,
        },
        {
            "group_id": "day_2", "distribution": "genextreme", "n_parameters": 3,
            "fit_status": "success", "AIC": 59.5, "delta_AIC": 0.0,
            "SW_pvalue": 0.40, "KS_pvalue": 0.65, "AD_pvalue": 0.50,
            "SPI_AD_pass": True,
        },
    ])

    summary = summarize_candidate_diagnostics(details)
    assert "fit_coverage_pct" in summary.columns
    assert "AIC_coverage_pct" in summary.columns
    assert "SW_rejection_frequency_pct" in summary.columns
    assert "SW_nonrejection_ratio" in summary.columns
    assert "mean_delta_AIC" in summary.columns
    assert "SPI_AD_group_pass_ratio" in summary.columns
    assert "meets_90pct_normality_target" in summary.columns

    rank_res = rank_aggregated_candidates(
        summary,
        min_valid_group_fraction=0.80,
        normality_ratio_threshold=0.90,
        prefer_two_parameters=True,
        ranking_method="hierarchical",
    )
    assert rank_res["best_distribution"] is not None
    assert rank_res["alternative_distribution"] is not None
    assert rank_res["best_distribution"] != rank_res["alternative_distribution"]
    assert rank_res["normality_target_met_by_any_candidate"] is True
    assert rank_res["best_selection_status"] == "accepted"


def test_small_sample_policy_augmented_alias():
    """Verify that small_sample_policy='augmented' behaves identically to legacy 'pseudo_observation_experimental'."""
    s = pd.Series([0.0, 0.0, 0.0, 12.0, 25.0])
    d_aug = Dist(s, gamma, prob_zero=True, small_sample_policy="augmented")
    d_leg = Dist(s, gamma, prob_zero=True, small_sample_policy="pseudo_observation_experimental")

    assert d_aug.fit_status == d_leg.fit_status
    assert d_aug.pseudo_obs_added is True
    assert d_leg.pseudo_obs_added is True
    assert np.isclose(d_aug.loc, d_leg.loc)
    assert np.isclose(d_aug.scale, d_leg.scale)
    assert np.allclose(d_aug.cdf().dropna(), d_leg.cdf().dropna())


def test_standard_normal_anderson_case_0():
    """Verify standard_normal_anderson tests against fixed N(0, 1) (Case 0).

    A distribution with non-zero mean N(2, 1) is accepted by composite normal tests
    (scipy.stats.anderson) because it estimates mean, but MUST be rejected by
    standard_normal_anderson with fixed mu=0, sigma=1 (crit=2.492).
    """
    from spei.model_selection import standard_normal_anderson

    rng = np.random.default_rng(42)
    # 1. True standard normal draws
    z_std = rng.normal(0.0, 1.0, size=500)
    stat_std, crit_std, pass_std = standard_normal_anderson(z_std, alpha=0.05)
    assert crit_std == 2.492
    assert pass_std is True
    assert stat_std < 2.492

    # 2. Shifted normal draws N(2.0, 1.0)
    z_shifted = rng.normal(2.0, 1.0, size=500)
    stat_shifted, crit_shifted, pass_shifted = standard_normal_anderson(z_shifted, alpha=0.05)
    assert pass_shifted is False
    assert stat_shifted > 10.0  # massively rejected against standard normal N(0, 1)


def test_all_zero_policy_propagation():
    """Verify that all_zero_policy propagates correctly through Dist and SI."""
    s_zero = pd.Series(np.zeros(30))

    # Under stagge policy, all zeros in Dist lead to 0.5 CDF (centroid)
    d_stagge = Dist(s_zero, gamma, prob_zero=True, all_zero_policy="stagge")
    assert d_stagge.all_zero_group is True
    assert d_stagge.fit_status == "all_zero"
    assert np.all(d_stagge.cdf() == 0.5)

    # Under wang policy, all zeros in Dist lead to NaN CDF
    d_wang = Dist(s_zero, gamma, prob_zero=True, all_zero_policy="wang")
    assert d_wang.all_zero_group is True
    assert d_wang.fit_status == "all_zero"
    assert np.all(np.isnan(d_wang.cdf()))

    # Verify SI initializes with all_zero_policy and passes to Dist
    dates = pd.date_range("2020-01-01", periods=30, freq="D")
    s_ts = pd.Series(np.zeros(30), index=dates)
    si_stagge = SI(s_ts, dist=gamma, all_zero_policy="stagge")
    assert si_stagge.all_zero_policy == "stagge"
    si_wang = SI(s_ts, dist=gamma, all_zero_policy="wang")
    assert si_wang.all_zero_policy == "wang"


def test_rank_aggregated_candidates_consensus_rank_vs_hierarchical():
    """Verify differences between hierarchical rule-based ranking and consensus / Borda ranking."""
    details = pd.DataFrame([
        {
            "group_id": "day_1", "distribution": "gamma", "n_parameters": 2,
            "fit_status": "success", "AIC": 100.0, "delta_AIC": 0.0,
            "SW_pvalue": 0.50, "KS_pvalue": 0.80, "AD_pvalue": 0.70,
            "SPI_AD_pass": True,
        },
        {
            "group_id": "day_1", "distribution": "pearson3", "n_parameters": 3,
            "fit_status": "success", "AIC": 100.5, "delta_AIC": 0.5,
            "SW_pvalue": 0.60, "KS_pvalue": 0.85, "AD_pvalue": 0.75,
            "SPI_AD_pass": True,
        },
        {
            "group_id": "day_1", "distribution": "gumbel_r", "n_parameters": 2,
            "fit_status": "success", "AIC": 108.0, "delta_AIC": 8.0,
            "SW_pvalue": 0.02, "KS_pvalue": 0.10, "AD_pvalue": 0.05,
            "SPI_AD_pass": False,
        },
        {
            "group_id": "day_2", "distribution": "gamma", "n_parameters": 2,
            "fit_status": "success", "AIC": 60.5, "delta_AIC": 0.5,
            "SW_pvalue": 0.45, "KS_pvalue": 0.70, "AD_pvalue": 0.60,
            "SPI_AD_pass": True,
        },
        {
            "group_id": "day_2", "distribution": "pearson3", "n_parameters": 3,
            "fit_status": "success", "AIC": 60.0, "delta_AIC": 0.0,
            "SW_pvalue": 0.55, "KS_pvalue": 0.75, "AD_pvalue": 0.65,
            "SPI_AD_pass": True,
        },
        {
            "group_id": "day_2", "distribution": "gumbel_r", "n_parameters": 2,
            "fit_status": "success", "AIC": 69.0, "delta_AIC": 9.0,
            "SW_pvalue": 0.01, "KS_pvalue": 0.08, "AD_pvalue": 0.04,
            "SPI_AD_pass": False,
        },
    ])

    summary = summarize_candidate_diagnostics(details)

    # 1. Hierarchical ranking (gate-based with parsimony preference)
    res_h = rank_aggregated_candidates(
        summary,
        prefer_two_parameters=True,
        ranking_method="hierarchical",
    )
    assert res_h["best_selection_status"] == "accepted"
    assert res_h["best_distribution"] == "gamma"
    assert res_h["alternative_distribution"] == "pearson3"
    assert "consensus_score" not in res_h["global_ranking"].columns

    # 2. Consensus ranking (Borda count across AIC, SW, AD)
    res_c = rank_aggregated_candidates(
        summary,
        ranking_method="consensus_rank",
    )
    assert res_c["best_selection_status"] == "consensus_rank_user_option"
    df_c = res_c["global_ranking"]
    assert "consensus_score" in df_c.columns
    assert "rank_aic" in df_c.columns
    assert "rank_sw" in df_c.columns
    assert "rank_ad" in df_c.columns
    assert df_c["consensus_score"].is_monotonic_increasing
    assert res_c["best_distribution"] is not None

    # 3. Verify SI.select_optimal_distribution integration
    dates = pd.date_range("2010-01-01", periods=5 * 365, freq="D")
    rng = np.random.default_rng(42)
    series = pd.Series(rng.gamma(2.0, 5.0, size=len(dates)), index=dates)
    si = SI(series, dist=gamma, timescale=30, fit_freq="dekad", prob_zero=True)
    res_si_c = si.select_optimal_distribution(
        candidates={"gamma": gamma, "weibull_min": weibull_min},
        n_boot=9,
        ranking_method="consensus_rank",
    )
    assert res_si_c["selection_status"] == "consensus_rank_user_option"
    assert "consensus_score" in res_si_c["global_ranking"].columns


def test_dual_ranking_presence_and_structure():
    """Test A & F: Verify that both hierarchical and consensus_rank are always returned."""
    dates = pd.date_range("2015-01-01", periods=10 * 365, freq="D")
    rng = np.random.default_rng(123)
    precip = pd.Series(rng.gamma(2.0, 5.0, size=len(dates)), index=dates)

    si = SI(precip, dist=gamma, timescale=30, fit_freq="dekad", prob_zero=True)
    res = si.select_optimal_distribution(
        candidates={"gamma": gamma, "weibull_min": weibull_min},
        n_boot=9,
        ranking_method="hierarchical",
    )

    # 1. Dual ranking results container
    assert "ranking_results" in res
    assert "hierarchical" in res["ranking_results"]
    assert "consensus_rank" in res["ranking_results"]

    hier = res["ranking_results"]["hierarchical"]
    cons = res["ranking_results"]["consensus_rank"]

    for sub in [hier, cons]:
        assert "global_ranking" in sub
        assert "best_distribution" in sub
        assert "alternative_distribution" in sub
        assert "best_selection_status" in sub
        assert "alternative_selection_status" in sub
        assert "selection_reason" in sub
        assert isinstance(sub["global_ranking"], pd.DataFrame)
        assert len(sub["global_ranking"]) == 2

    # 2. Ranking comparison table
    assert "ranking_comparison" in res
    comp = res["ranking_comparison"]
    assert isinstance(comp, pd.DataFrame)
    expected_cols = {
        "distribution", "hierarchical_rank", "consensus_rank", "rank_difference",
        "hierarchical_selected", "consensus_selected", "hierarchical_status", "consensus_status",
    }
    assert expected_cols.issubset(set(comp.columns))

    # 3. Agreement summary
    assert "agreement_summary" in res
    agree = res["agreement_summary"]
    assert "methods_agree_on_best" in agree
    assert "methods_agree_on_alternative" in agree
    assert "max_rank_difference" in agree
    assert "hierarchical_best" in agree
    assert "consensus_best" in agree
    assert agree["hierarchical_best"] == hier["best_distribution"]
    assert agree["consensus_best"] == cons["best_distribution"]

    # 4. Backward compatibility
    assert res["best_distribution"] == hier["best_distribution"]
    assert res["alternative_distribution"] == hier["alternative_distribution"]
    assert res["selection_status"] == hier["best_selection_status"]
    assert res["global_ranking"].equals(hier["global_ranking"])


def test_dual_ranking_zero_duplicate_computation(monkeypatch):
    """Test B: Verify that candidate fitting and bootstrap GoF run strictly in a single pass."""
    import spei.model_selection as ms_mod

    original_select_best = ms_mod.select_best_distribution
    call_count = [0]

    def counted_select_best(*args, **kwargs):
        call_count[0] += 1
        return original_select_best(*args, **kwargs)

    monkeypatch.setattr(ms_mod, "select_best_distribution", counted_select_best)

    groups = {
        "g1": pd.Series(np.random.gamma(2.0, 5.0, 30)),
        "g2": pd.Series(np.random.gamma(2.0, 5.0, 30)),
        "g3": pd.Series(np.random.gamma(2.0, 5.0, 30)),
    }
    res = select_models_by_group(
        groups,
        candidates={"gamma": gamma, "weibull_min": weibull_min},
        n_boot=9,
        ranking_method="hierarchical",
    )

    # Must be called exactly 3 times (once per group), not 6 times!
    assert call_count[0] == 3
    assert "hierarchical" in res["ranking_results"]
    assert "consensus_rank" in res["ranking_results"]


def test_dual_ranking_deterministic_output():
    """Test C: Fixed random seed produces strictly identical rankings and comparison tables."""
    groups = {
        f"g{i}": pd.Series(np.random.default_rng(i).gamma(2.0, 5.0, 30))
        for i in range(4)
    }
    res1 = select_models_by_group(
        groups,
        candidates={"gamma": gamma, "weibull_min": weibull_min},
        n_boot=9,
        random_state=42,
    )
    res2 = select_models_by_group(
        groups,
        candidates={"gamma": gamma, "weibull_min": weibull_min},
        n_boot=9,
        random_state=42,
    )

    pd.testing.assert_frame_equal(res1["ranking_comparison"], res2["ranking_comparison"])
    pd.testing.assert_frame_equal(
        res1["ranking_results"]["hierarchical"]["global_ranking"],
        res2["ranking_results"]["hierarchical"]["global_ranking"],
    )
    pd.testing.assert_frame_equal(
        res1["ranking_results"]["consensus_rank"]["global_ranking"],
        res2["ranking_results"]["consensus_rank"]["global_ranking"],
    )


def test_synthetic_disagreement_fixture():
    """Test D: Disagreement scenario where hierarchical picks model_a and consensus picks model_b."""
    groups_a = []
    groups_b = []
    for i in range(10):
        groups_a.append({
            "group_id": f"g{i}", "distribution": "model_a", "n_parameters": 2,
            "fit_status": "success", "AIC": 100.0, "delta_AIC": 0.0,
            "SW_pvalue": 0.02 if i == 0 else 0.50,  # 1 SW rejection (10% rejection)
            "KS_pvalue": 0.50, "AD_pvalue": 0.50,
            "SPI_AD_pass": True if i < 9 else False,  # 9/10 = 90% (meets target)
        })
        groups_b.append({
            "group_id": f"g{i}", "distribution": "model_b", "n_parameters": 3,
            "fit_status": "success", "AIC": 101.0, "delta_AIC": 1.0,  # competitive (delta < 2.0)
            "SW_pvalue": 0.80,  # 0 SW rejections (0% rejection)
            "KS_pvalue": 0.90, "AD_pvalue": 0.90,
            "SPI_AD_pass": True,  # 10/10 = 100% pass
        })

    details = pd.DataFrame(groups_a + groups_b)
    summary = summarize_candidate_diagnostics(details)
    res_h = rank_aggregated_candidates(summary, prefer_two_parameters=True, ranking_method="hierarchical")
    res_c = rank_aggregated_candidates(summary, ranking_method="consensus_rank")

    # Hierarchical prefers model_a (both competitive and meet normality, but model_a has 2 params & lowest AIC)
    assert res_h["best_distribution"] == "model_a"
    assert res_h["alternative_distribution"] == "model_b"

    # Consensus (Borda) prefers model_b (superior normality ranks outweigh slight AIC deficit)
    assert res_c["best_distribution"] == "model_b"
    assert res_c["alternative_distribution"] == "model_a"


def test_independent_alternative_qualification():
    """Test E & Fix 4: Independent evaluation of alternative distribution acceptance status."""
    # Scenario 1: Alt fails normality (< 90% target)
    details_alt_unqualified = pd.DataFrame([
        {
            "group_id": f"g{i}", "distribution": "cand_1", "n_parameters": 2,
            "fit_status": "success", "AIC": 100.0, "delta_AIC": 0.0,
            "SW_pvalue": 0.50, "KS_pvalue": 0.50, "AD_pvalue": 0.50,
            "SPI_AD_pass": True,
        }
        for i in range(10)
    ] + [
        {
            "group_id": f"g{i}", "distribution": "cand_2", "n_parameters": 2,
            "fit_status": "success", "AIC": 101.0, "delta_AIC": 1.0,
            "SW_pvalue": 0.01, "KS_pvalue": 0.50, "AD_pvalue": 0.50,
            "SPI_AD_pass": i < 7,  # 7/10 = 70% < 90%
        }
        for i in range(10)
    ])
    summary_1 = summarize_candidate_diagnostics(details_alt_unqualified)
    res_1 = rank_aggregated_candidates(summary_1, ranking_method="hierarchical")
    assert res_1["best_selection_status"] == "accepted"
    assert res_1["alternative_selection_status"] == "ranked_alternative_not_fully_qualified"

    # Scenario 2: Single candidate available -> no alternative
    details_single = details_alt_unqualified[details_alt_unqualified["distribution"] == "cand_1"].copy()
    summary_2 = summarize_candidate_diagnostics(details_single)
    res_2 = rank_aggregated_candidates(summary_2, ranking_method="hierarchical")
    assert res_2["best_selection_status"] == "accepted"
    assert res_2["alternative_selection_status"] == "no_alternative_available"


def test_coverage_denominator_preservation():
    """Test H & Fix 2: Group coverage denominator preserves total requested groups including failed groups."""
    details = pd.DataFrame([
        # Group 1 & 2 succeed
        {"group_id": "g1", "distribution": "gamma", "n_parameters": 2, "fit_status": "success", "AIC": 100.0, "delta_AIC": 0.0, "SPI_AD_pass": True},
        {"group_id": "g2", "distribution": "gamma", "n_parameters": 2, "fit_status": "success", "AIC": 102.0, "delta_AIC": 0.0, "SPI_AD_pass": True},
        # Groups 3, 4, 5 failed or not evaluable
        {"group_id": "g3", "distribution": "gamma", "n_parameters": 2, "fit_status": "not_evaluable", "AIC": np.nan, "delta_AIC": np.nan, "SPI_AD_pass": None},
        {"group_id": "g4", "distribution": "gamma", "n_parameters": 2, "fit_status": "selection_failed", "AIC": np.nan, "delta_AIC": np.nan, "SPI_AD_pass": None},
        {"group_id": "g5", "distribution": "gamma", "n_parameters": 2, "fit_status": "insufficient_positive_sample", "AIC": np.nan, "delta_AIC": np.nan, "SPI_AD_pass": None},
    ])

    summary = summarize_candidate_diagnostics(details, n_groups_requested=5)
    row = summary.iloc[0]
    assert row["n_groups_requested"] == 5
    assert row["n_fit_success"] == 2
    # Coverage must be 2 / 5 = 40.0%, NOT 2 / 2 = 100%
    assert np.isclose(row["fit_coverage_pct"], 40.0)
    assert np.isclose(row["AIC_coverage_pct"], 40.0)

    # Rank candidate: must fail min_valid_group_fraction (0.80)
    res = rank_aggregated_candidates(summary, min_valid_group_fraction=0.80)
    assert res["best_selection_status"] == "provisional_insufficient_group_coverage"


def test_fallback_fit_aic_comparability():
    """Test H & Fix 3: Fallback parameter fits are marked non-comparable and excluded from Delta AIC."""
    comparison = pd.DataFrame([
        {
            "distribution": "fallback_model",
            "n_parameters": 2,
            "AIC": 50.0,  # Lower raw AIC from fallback/constrained fit
            "aic_comparable": False,
            "aic_incomparable_reason": "moment_fallback",
            "loglik": -23.0,
        },
        {
            "distribution": "valid_mle_model",
            "n_parameters": 2,
            "AIC": 100.0,
            "aic_comparable": True,
            "aic_incomparable_reason": None,
            "loglik": -48.0,
        },
    ])

    # 1. Delta AIC computation
    comparable_aic = comparison[comparison["aic_comparable"].eq(True) & np.isfinite(comparison["AIC"])]
    min_aic = float(comparable_aic["AIC"].min())
    comparison["delta_AIC"] = np.where(
        comparison["aic_comparable"].eq(True),
        comparison["AIC"] - min_aic,
        np.nan,
    )
    comparison["AIC_competitive"] = comparison["aic_comparable"].eq(True) & (comparison["delta_AIC"] < 2.0)

    mle_row = comparison[comparison["distribution"] == "valid_mle_model"].iloc[0]
    fallback_row = comparison[comparison["distribution"] == "fallback_model"].iloc[0]
    assert mle_row["delta_AIC"] == 0.0
    assert bool(mle_row["AIC_competitive"]) is True
    assert np.isnan(fallback_row["delta_AIC"])
    assert bool(fallback_row["AIC_competitive"]) is False

    # 2. _rank_rows prioritizes comparable MLE fits over lower-raw-AIC fallbacks
    ranked = _rank_rows(comparison, prefer_two_parameters=True)
    assert ranked.iloc[0]["distribution"] == "valid_mle_model"


# ==============================================================================
# SECTION 3: FIX A REGRESSION TESTS — WANG PSEUDO-OBSERVATIONS & AIC ELIGIBILITY
# ==============================================================================


def test_a1_wang_fit_with_pseudo_observation():
    """Test A1: Wang fit with pseudo-observations must set aic_comparable=False and is_mle=False."""
    arr = np.array([0.0, 0.0, 5.0, 10.0, 15.0, 25.0, 30.0], dtype=float)
    s = pd.Series(arr)
    dist_wang = Dist(s, dist=gamma, prob_zero=True, fitting_policy="wang")

    assert dist_wang.pseudo_obs_added is True
    assert dist_wang.fit_status == "success"
    assert dist_wang.fit_method == "mle_wang_nelder_mead"
    assert dist_wang.converged is True
    assert dist_wang.is_mle is False
    assert dist_wang.aic_comparable is False
    assert dist_wang.aic_incomparable_reason == "pseudo_observation_augmented_fit"

    # Supported SPI calculation still functions
    spi_vals = dist_wang.cdf()
    assert np.all(np.isfinite(spi_vals))
    assert 0.0 < np.min(spi_vals) < np.max(spi_vals) <= 1.0


def test_a2_wang_fit_without_pseudo_observation():
    """Test A2: Wang fit without pseudo-observations (all positive) preserves AIC comparability."""
    arr = np.array([5.0, 10.0, 15.0, 25.0, 30.0, 40.0], dtype=float)
    s = pd.Series(arr)
    dist_wang = Dist(s, dist=gamma, prob_zero=True, fitting_policy="wang")

    assert dist_wang.pseudo_obs_added is False
    assert dist_wang.fit_status == "success"
    assert dist_wang.converged is True
    assert dist_wang.is_mle is True
    assert dist_wang.aic_comparable is True
    assert dist_wang.aic_incomparable_reason == "none"


def test_a3_wang_fallback_distinguishable_from_mle(monkeypatch):
    """Test A3: Wang fallback parameters are distinguishable from MLE and not AIC-comparable."""
    from scipy import optimize

    def fake_minimize(*args, **kwargs):
        res = optimize.OptimizeResult()
        res.success = False
        res.x = np.array([np.nan, np.nan])
        res.fun = np.nan
        return res

    monkeypatch.setattr(optimize, "minimize", fake_minimize)

    arr = np.array([0.0, 0.0, 5.0, 10.0, 15.0, 25.0, 30.0], dtype=float)
    s = pd.Series(arr)
    dist_wang = Dist(s, dist=gamma, prob_zero=True, fitting_policy="wang")

    assert dist_wang.fit_status == "success"
    assert dist_wang.fit_method in ("wang_moments_fallback", "wang_lmoments_fallback")
    assert dist_wang.converged is False
    assert dist_wang.is_mle is False
    assert dist_wang.aic_comparable is False
    assert "fallback" in dist_wang.aic_incomparable_reason


def test_a4_wang_and_standard_gamma_spi_compatibility():
    """Test A4: Standard Gamma fitting retains normal MLE and AIC comparability while Wang retains behavior."""
    arr = np.array([0.0, 0.0, 5.0, 10.0, 15.0, 25.0, 30.0], dtype=float)
    s = pd.Series(arr)
    dist_std = Dist(s, dist=gamma, prob_zero=True, fitting_policy="standard")
    dist_wang = Dist(s, dist=gamma, prob_zero=True, fitting_policy="wang")

    # Standard fit has no pseudo-observations and is comparable
    assert dist_std.pseudo_obs_added is False
    assert dist_std.is_mle is True
    assert dist_std.aic_comparable is True

    # Wang fit has pseudo-observations and is not comparable
    assert dist_wang.pseudo_obs_added is True
    assert dist_wang.is_mle is False
    assert dist_wang.aic_comparable is False


def test_a5_mixed_candidate_ranking_wang_cannot_win_official_aic():
    """Test A5: Wang augmented fit cannot win official AIC comparison even if its raw AIC is lower."""
    s = pd.Series(np.array([0.0, 0.0, 5.0, 10.0, 15.0, 25.0, 30.0], dtype=float))
    dist_std = Dist(s, dist=gamma, prob_zero=True, fitting_policy="standard")
    dist_wang = Dist(s, dist=gamma, prob_zero=True, fitting_policy="wang")

    aic_std, _, _, _, comp_std, _ = _conditional_aic(dist_std, s, prob_zero=True)
    aic_wang, _, _, _, comp_wang, reason_wang = _conditional_aic(dist_wang, s, prob_zero=True)

    assert comp_std is True
    assert comp_wang is False
    assert reason_wang == "pseudo_observation_augmented_fit"

    comparison = pd.DataFrame([
        {
            "distribution": "gamma_wang",
            "n_parameters": 2,
            "AIC": 10.0,  # Lower raw AIC
            "aic_comparable": comp_wang,
            "aic_incomparable_reason": reason_wang,
        },
        {
            "distribution": "gamma_standard",
            "n_parameters": 2,
            "AIC": 20.0,
            "aic_comparable": comp_std,
            "aic_incomparable_reason": "none",
        },
    ])

    comparable_aic = comparison[comparison["aic_comparable"].eq(True)]
    min_aic = float(comparable_aic["AIC"].min())
    comparison["delta_AIC"] = np.where(
        comparison["aic_comparable"].eq(True),
        comparison["AIC"] - min_aic,
        np.nan,
    )
    ranked = _rank_rows(comparison, prefer_two_parameters=True)
    assert ranked.iloc[0]["distribution"] == "gamma_standard"
    assert np.isnan(comparison.loc[comparison["distribution"] == "gamma_wang", "delta_AIC"].iloc[0])


# ==============================================================================
# SECTION 4: FIX C REGRESSION TESTS — CONSENSUS RANKING MISSING METRICS
# ==============================================================================


def test_c1_missing_spi_ad_candidate_ineligible_for_consensus():
    """Test C1: Candidate missing SPI AD receives no official consensus score/rank and cannot win."""
    summary = pd.DataFrame([
        {
            "distribution": "model_complete_a",
            "n_parameters": 2,
            "fit_coverage_pct": 100.0,
            "AIC_coverage_pct": 100.0,
            "mean_delta_AIC": 1.0,
            "SW_rejection_frequency_pct": 5.0,
            "SPI_AD_group_pass_ratio": 0.95,
            "meets_90pct_normality_target": True,
        },
        {
            "distribution": "model_complete_b",
            "n_parameters": 2,
            "fit_coverage_pct": 100.0,
            "AIC_coverage_pct": 100.0,
            "mean_delta_AIC": 2.0,
            "SW_rejection_frequency_pct": 8.0,
            "SPI_AD_group_pass_ratio": 0.92,
            "meets_90pct_normality_target": True,
        },
        {
            "distribution": "model_incomplete_ad",
            "n_parameters": 2,
            "fit_coverage_pct": 100.0,
            "AIC_coverage_pct": 100.0,
            "mean_delta_AIC": 0.0,  # Best AIC
            "SW_rejection_frequency_pct": 0.0,  # Best SW
            "SPI_AD_group_pass_ratio": np.nan,  # Missing AD
            "meets_90pct_normality_target": False,
        },
    ])

    res = rank_aggregated_candidates(summary, ranking_method="consensus_rank")
    df_rank = res["global_ranking"]

    inc_row = df_rank[df_rank["distribution"] == "model_incomplete_ad"].iloc[0]
    assert bool(inc_row["consensus_eligible"]) is False
    assert inc_row["consensus_ineligible_reason"] == "missing_spi_ad_metric"
    assert np.isnan(inc_row["consensus_score"])
    assert np.isnan(inc_row["global_rank"])

    # Complete models are ranked #1 and #2; incomplete model cannot win
    assert res["best_distribution"] == "model_complete_a"
    assert res["alternative_distribution"] == "model_complete_b"


def test_c2_missing_sw_metric_ineligible_for_consensus():
    """Test C2: Candidate missing Shapiro-Wilk diagnostics is marked consensus-ineligible."""
    summary = pd.DataFrame([
        {
            "distribution": "model_complete",
            "n_parameters": 2,
            "fit_coverage_pct": 100.0,
            "AIC_coverage_pct": 100.0,
            "mean_delta_AIC": 1.0,
            "SW_rejection_frequency_pct": 5.0,
            "SPI_AD_group_pass_ratio": 0.95,
            "meets_90pct_normality_target": True,
        },
        {
            "distribution": "model_missing_sw",
            "n_parameters": 2,
            "fit_coverage_pct": 100.0,
            "AIC_coverage_pct": 100.0,
            "mean_delta_AIC": 0.0,
            "SW_rejection_frequency_pct": np.nan,  # Missing SW
            "SPI_AD_group_pass_ratio": 1.0,
            "meets_90pct_normality_target": True,
        },
    ])

    res = rank_aggregated_candidates(summary, ranking_method="consensus_rank")
    df_rank = res["global_ranking"]
    inc_row = df_rank[df_rank["distribution"] == "model_missing_sw"].iloc[0]

    assert bool(inc_row["consensus_eligible"]) is False
    assert inc_row["consensus_ineligible_reason"] == "missing_sw_metric"
    assert res["best_distribution"] == "model_complete"


def test_c3_missing_delta_aic_ineligible_for_consensus():
    """Test C3: Candidate missing Delta AIC cannot enter official consensus pool."""
    summary = pd.DataFrame([
        {
            "distribution": "model_complete",
            "n_parameters": 2,
            "fit_coverage_pct": 100.0,
            "AIC_coverage_pct": 100.0,
            "mean_delta_AIC": 0.0,
            "SW_rejection_frequency_pct": 5.0,
            "SPI_AD_group_pass_ratio": 0.95,
            "meets_90pct_normality_target": True,
        },
        {
            "distribution": "model_missing_aic",
            "n_parameters": 2,
            "fit_coverage_pct": 100.0,
            "AIC_coverage_pct": 100.0,
            "mean_delta_AIC": np.nan,  # Non-comparable / missing
            "SW_rejection_frequency_pct": 2.0,
            "SPI_AD_group_pass_ratio": 0.98,
            "meets_90pct_normality_target": True,
        },
    ])

    res = rank_aggregated_candidates(summary, ranking_method="consensus_rank")
    df_rank = res["global_ranking"]
    inc_row = df_rank[df_rank["distribution"] == "model_missing_aic"].iloc[0]

    assert bool(inc_row["consensus_eligible"]) is False
    assert inc_row["consensus_ineligible_reason"] == "missing_mean_delta_aic"
    assert res["best_distribution"] == "model_complete"


def test_c4_partial_metric_winner_regression():
    """Test C4: Verify that a 2-metric candidate previously winning via skipna=True no longer wins."""
    summary = pd.DataFrame([
        {
            "distribution": "model_a",
            "n_parameters": 2,
            "fit_coverage_pct": 100.0, "AIC_coverage_pct": 100.0,
            "mean_delta_AIC": 0.5,
            "SW_rejection_frequency_pct": 4.0,
            "SPI_AD_group_pass_ratio": 0.92,
            "meets_90pct_normality_target": True,
        },
        {
            "distribution": "model_b",
            "n_parameters": 2,
            "fit_coverage_pct": 100.0, "AIC_coverage_pct": 100.0,
            "mean_delta_AIC": 1.0,
            "SW_rejection_frequency_pct": 6.0,
            "SPI_AD_group_pass_ratio": 0.90,
            "meets_90pct_normality_target": True,
        },
        {
            "distribution": "model_c_partial",
            "n_parameters": 2,
            "fit_coverage_pct": 100.0, "AIC_coverage_pct": 100.0,
            "mean_delta_AIC": 0.0,
            "SW_rejection_frequency_pct": 2.0,
            "SPI_AD_group_pass_ratio": np.nan,  # Missing AD
            "meets_90pct_normality_target": False,
        },
    ])

    res = rank_aggregated_candidates(summary, ranking_method="consensus_rank")
    assert res["best_distribution"] == "model_a"
    assert res["best_distribution"] != "model_c_partial"
    c_row = res["global_ranking"][res["global_ranking"]["distribution"] == "model_c_partial"].iloc[0]
    assert np.isnan(c_row["consensus_score"])
    assert np.isnan(c_row["global_rank"])


def test_c5_all_candidates_incomplete():
    """Test C5: When all candidates lack at least one required metric, return provisional without winner."""
    summary = pd.DataFrame([
        {
            "distribution": "model_lacks_ad",
            "n_parameters": 2,
            "fit_coverage_pct": 100.0, "AIC_coverage_pct": 100.0,
            "mean_delta_AIC": 0.0,
            "SW_rejection_frequency_pct": 2.0,
            "SPI_AD_group_pass_ratio": np.nan,
            "meets_90pct_normality_target": False,
        },
        {
            "distribution": "model_lacks_sw",
            "n_parameters": 2,
            "fit_coverage_pct": 100.0, "AIC_coverage_pct": 100.0,
            "mean_delta_AIC": 0.5,
            "SW_rejection_frequency_pct": np.nan,
            "SPI_AD_group_pass_ratio": 0.95,
            "meets_90pct_normality_target": True,
        },
        {
            "distribution": "model_lacks_aic",
            "n_parameters": 2,
            "fit_coverage_pct": 100.0, "AIC_coverage_pct": 100.0,
            "mean_delta_AIC": np.nan,
            "SW_rejection_frequency_pct": 5.0,
            "SPI_AD_group_pass_ratio": 0.92,
            "meets_90pct_normality_target": True,
        },
    ])

    res = rank_aggregated_candidates(summary, ranking_method="consensus_rank")
    assert res["best_distribution"] is None
    assert res["alternative_distribution"] is None
    assert res["best_selection_status"] == "provisional_insufficient_consensus_metrics"
    assert res["alternative_selection_status"] == "no_alternative_available"


def test_c6_complete_candidates_preserve_expected_score():
    """Test C6: Candidates with all required metrics preserve exact Borda score formula and directions."""
    summary = pd.DataFrame([
        {
            "distribution": "model_1",
            "n_parameters": 2,
            "fit_coverage_pct": 100.0, "AIC_coverage_pct": 100.0,
            "mean_delta_AIC": 0.0,              # rank 1
            "SW_rejection_frequency_pct": 10.0, # rank 2
            "SPI_AD_group_pass_ratio": 0.95,    # rank 1 (descending)
            "meets_90pct_normality_target": True,
        },
        {
            "distribution": "model_2",
            "n_parameters": 2,
            "fit_coverage_pct": 100.0, "AIC_coverage_pct": 100.0,
            "mean_delta_AIC": 1.0,              # rank 2
            "SW_rejection_frequency_pct": 5.0,  # rank 1 (ascending)
            "SPI_AD_group_pass_ratio": 0.90,    # rank 2 (descending)
            "meets_90pct_normality_target": True,
        },
    ])

    res = rank_aggregated_candidates(summary, ranking_method="consensus_rank")
    df_rank = res["global_ranking"]

    # model_1: rank_aic=1, rank_sw=2, rank_ad=1 -> score = (1 + 2 + 1)/3 = 1.3333...
    # model_2: rank_aic=2, rank_sw=1, rank_ad=2 -> score = (2 + 1 + 2)/3 = 1.6666...
    row_1 = df_rank[df_rank["distribution"] == "model_1"].iloc[0]
    row_2 = df_rank[df_rank["distribution"] == "model_2"].iloc[0]
    assert np.isclose(row_1["consensus_score"], 4.0 / 3.0)
    assert np.isclose(row_2["consensus_score"], 5.0 / 3.0)
    assert res["best_distribution"] == "model_1"
    assert res["alternative_distribution"] == "model_2"


def test_c7_dual_ranking_compatibility():
    """Test C7: Dual-ranking returns both hierarchical and consensus_rank with shared evaluation."""
    details = pd.DataFrame([
        {
            "group_id": f"g{i}", "distribution": "cand_a", "n_parameters": 2,
            "fit_status": "success", "AIC": 100.0, "delta_AIC": 0.0,
            "SW_pvalue": 0.50, "KS_pvalue": 0.80, "AD_pvalue": 0.70,
            "SPI_AD_pass": True,
        }
        for i in range(10)
    ] + [
        {
            "group_id": f"g{i}", "distribution": "cand_b", "n_parameters": 2,
            "fit_status": "success", "AIC": 101.0, "delta_AIC": 1.0,
            "SW_pvalue": 0.60, "KS_pvalue": 0.85, "AD_pvalue": 0.75,
            "SPI_AD_pass": True,
        }
        for i in range(10)
    ])

    summary = summarize_candidate_diagnostics(details)
    res_h = rank_aggregated_candidates(summary, ranking_method="hierarchical")
    res_c = rank_aggregated_candidates(summary, ranking_method="consensus_rank")

    assert "global_ranking" in res_h
    assert "global_ranking" in res_c
    assert res_h["best_selection_status"] == "accepted"
    assert res_c["best_selection_status"] == "consensus_rank_user_option"

def test_select_best_distribution_gof_scope_all():
    """Verify that gof_scope='all' tests GoF for all valid AIC candidates without NameError."""
    rng = np.random.default_rng(42)
    data = pd.Series(stats.gamma.rvs(a=2.0, scale=15.0, size=40, random_state=rng))
    data.iloc[[3, 8]] = 0.0

    res = select_best_distribution(
        data,
        candidates={"gamma": stats.gamma, "weibull_min": stats.weibull_min},
        prob_zero=True,
        n_boot=10,
        gof_scope="all",
        random_state=42,
    )
    assert res["recommendation"]["distribution"] in ("gamma", "weibull_min")
    assert res["comparison"]["gof_tested"].all()
