"""Regression tests for scientifically comparable DSPI distribution selection."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest
from scipy import optimize
from scipy.stats import fisk, gamma, genextreme, gumbel_r, lognorm, pearson3, weibull_min

import spei.dist as dist_module
from spei.dist import (
    Dist,
    _gev_negloglik,
    _gumbel_negloglik,
    _pearson3_negloglik,
)
from spei.model_selection import (
    _add_delta_information_criteria,
    _conditional_information_criteria,
    _parameter_count,
    _spi_from_fitted_model,
    rank_aggregated_candidates,
    select_best_distribution,
    summarize_candidate_diagnostics,
)
from spei.si import SI


@pytest.mark.parametrize(
    ("distribution", "expected"),
    [
        (gamma, 2),
        (weibull_min, 2),
        (gumbel_r, 2),
        (lognorm, 2),
        (fisk, 2),
        (pearson3, 3),
        (genextreme, 3),
    ],
)
def test_parameter_count_for_all_candidates(distribution, expected) -> None:
    sample = pd.Series(np.linspace(1.0, 20.0, 20))
    assert _parameter_count(Dist(sample, distribution, prob_zero=True)) == expected


def test_conditional_negative_loglikelihood_matches_manual_formula() -> None:
    data = np.array([1.0, 2.0, 4.0, 8.0])
    loc, scale = -1.5, 3.0
    expected = -float(
        np.sum(gumbel_r.logpdf(data, loc=loc, scale=scale))
        - len(data) * gumbel_r.logsf(0.0, loc=loc, scale=scale)
    )
    actual = _gumbel_negloglik(
        (loc, scale), data, conditional_positive=True
    )
    assert np.isclose(actual, expected, rtol=1e-12, atol=1e-12)

    pearson_expected = -float(
        np.sum(pearson3.logpdf(data, 1.2, loc=-1.0, scale=3.0))
        - len(data) * pearson3.logsf(0.0, 1.2, loc=-1.0, scale=3.0)
    )
    gev_expected = -float(
        np.sum(genextreme.logpdf(data, 0.2, loc=-1.0, scale=3.0))
        - len(data) * genextreme.logsf(0.0, 0.2, loc=-1.0, scale=3.0)
    )
    assert np.isclose(
        _pearson3_negloglik((1.2, -1.0, 3.0), data, True),
        pearson_expected,
        rtol=1e-12,
        atol=1e-12,
    )
    assert np.isclose(
        _gev_negloglik((0.2, -1.0, 3.0), data, True),
        gev_expected,
        rtol=1e-12,
        atol=1e-12,
    )


def test_conditional_objectives_reject_invalid_support_and_survival() -> None:
    data = np.array([1.0, 2.0, 3.0])
    assert np.isinf(_gev_negloglik((1.0, 0.0, 0.1), data, True))
    assert np.isinf(_pearson3_negloglik((2.0, -100.0, 0.1), data, True))
    assert np.isinf(_gumbel_negloglik((-100.0, 0.1), data, True))


def test_conditional_survival_above_boundary_remains_comparable(monkeypatch) -> None:
    loc = float(np.log(-np.log(0.95)))  # P(X > 0) = 0.05 for scale=1.

    def fixed_solution(fun, x0, *args, **kwargs):
        x = np.asarray([loc, 1.0])
        return optimize.OptimizeResult(
            success=True, x=x, fun=float(fun(x)), nfev=1
        )

    monkeypatch.setattr(dist_module.optimize, "minimize", fixed_solution)
    fitted = Dist(pd.Series([0.0, 1.0, 2.0, 4.0, 8.0]), gumbel_r, prob_zero=True)

    assert np.isclose(gumbel_r.sf(0.0, loc=fitted.loc, scale=fitted.scale), 0.05)
    assert fitted.is_mle is True
    assert fitted.aic_comparable is True
    assert fitted.aic_incomparable_reason == "none"


def test_scipy_fit_is_reoptimized_before_becoming_comparable(monkeypatch) -> None:
    rng = np.random.default_rng(42)
    sample = pd.Series(np.r_[np.zeros(8), rng.gamma(2.0, 4.0, size=30)])
    original_minimize = optimize.minimize
    calls = 0

    def fail_then_optimize(fun, x0, *args, **kwargs):
        nonlocal calls
        calls += 1
        if calls == 1:
            return optimize.OptimizeResult(
                success=False,
                x=np.asarray(x0, dtype=float),
                fun=float(fun(np.asarray(x0, dtype=float))),
                nfev=1,
            )
        return original_minimize(fun, x0, *args, **kwargs)

    monkeypatch.setattr(dist_module, "lm_distr", None)
    monkeypatch.setattr(dist_module.optimize, "minimize", fail_then_optimize)
    fitted = Dist(sample, gumbel_r, prob_zero=True)

    assert fitted.fit_method == "mle_nelder_mead_scipy_init"
    assert fitted.converged is True
    assert fitted.is_mle is True
    assert fitted.aic_comparable is True
    assert fitted.optimizer_attempts == 2


def test_non_mle_fallback_is_usable_but_ineligible_for_official_aic(monkeypatch) -> None:
    sample = pd.Series(np.r_[np.zeros(5), [1.0, 2.0, 4.0, 7.0, 11.0]])

    def always_fail(fun, x0, *args, **kwargs):
        x = np.asarray(x0, dtype=float)
        return optimize.OptimizeResult(
            success=False, x=x, fun=float(fun(x)), nfev=1
        )

    monkeypatch.setattr(dist_module, "lm_distr", None)
    monkeypatch.setattr(dist_module.optimize, "minimize", always_fail)
    fitted = Dist(sample, gumbel_r, prob_zero=True)

    assert fitted.fit_status == "success"
    assert fitted.fit_method in {"moments", "scipy_mle"}
    assert fitted.converged is False
    assert fitted.is_mle is False
    assert fitted.aic_comparable is False
    assert fitted.aic_incomparable_reason.startswith("non_mle_fallback_")
    assert np.isfinite(fitted.cdf()).all()


def test_aic_and_aicc_use_positive_conditional_sample_size() -> None:
    sample = pd.Series(np.r_[np.zeros(4), np.arange(1.0, 11.0)])
    fitted = Dist(sample, gamma, prob_zero=True)
    result = _conditional_information_criteria(fitted, sample, prob_zero=True)
    k = 2
    n_pos = 10
    expected_aicc = result["AIC"] + 2 * k * (k + 1) / (n_pos - k - 1)

    assert result["n_parameters"] == k
    assert result["n_observations_ic"] == n_pos
    assert np.isclose(result["AICc"], expected_aicc)
    assert result["aicc_comparable"] is True


def test_aicc_is_undefined_when_n_not_greater_than_k_plus_one() -> None:
    sample = pd.Series([1.0, 2.0, 4.0])
    fitted = Dist(sample, gamma, prob_zero=True)
    result = _conditional_information_criteria(fitted, sample, prob_zero=True)

    assert np.isfinite(result["AIC"])
    assert np.isnan(result["AICc"])
    assert result["aicc_comparable"] is False
    assert result["aicc_incomparable_reason"] == "aicc_undefined_n_le_k_plus_1"


def test_singleton_comparison_has_no_official_delta_ic() -> None:
    sample = pd.Series(np.arange(1.0, 15.0))
    result = select_best_distribution(
        sample, candidates={"gamma": gamma}, gof_scope="none"
    )
    row = result["comparison"].iloc[0]

    assert row["n_comparable_candidates"] == 1
    assert np.isnan(row["delta_AIC"])
    assert row["AIC_comparison_status"] == "insufficient_comparable_candidates"
    assert result["recommendation"]["selection_status"] == "provisional_insufficient_comparison"


def test_incomparable_candidate_cannot_set_delta_minimum() -> None:
    frame = pd.DataFrame(
        [
            {"distribution": "fallback", "AIC": 1.0, "AICc": 2.0, "aic_comparable": False, "aicc_comparable": False},
            {"distribution": "mle_a", "AIC": 10.0, "AICc": 11.0, "aic_comparable": True, "aicc_comparable": True},
            {"distribution": "mle_b", "AIC": 12.0, "AICc": 13.0, "aic_comparable": True, "aicc_comparable": True},
        ]
    )
    compared = _add_delta_information_criteria(frame, delta_threshold=2.0)

    fallback = compared.loc[compared["distribution"] == "fallback"].iloc[0]
    mle_a = compared.loc[compared["distribution"] == "mle_a"].iloc[0]
    assert np.isnan(fallback["delta_AIC"])
    assert mle_a["delta_AIC"] == 0.0
    assert compared["n_comparable_candidates"].iloc[0] == 2


def test_aic_and_aicc_competitive_sets_are_kept_separate() -> None:
    sample = pd.Series(np.r_[np.zeros(5), np.linspace(1.0, 25.0, 25)])
    candidates = {"gamma": gamma, "gumbel": gumbel_r, "pearson": pearson3}
    result_aic = select_best_distribution(
        sample, candidates=candidates, gof_scope="none", information_criterion="AIC"
    )
    result_aicc = select_best_distribution(
        sample, candidates=candidates, gof_scope="none", information_criterion="AICc"
    )

    assert np.allclose(
        result_aic["comparison"]["delta_IC"],
        result_aic["comparison"]["delta_AIC"],
        equal_nan=True,
    )
    assert np.allclose(
        result_aicc["comparison"]["delta_IC"],
        result_aicc["comparison"]["delta_AICc"],
        equal_nan=True,
    )


def test_aggregate_uses_comparable_coverage_and_explicit_denominators() -> None:
    details = pd.DataFrame(
        [
            {"group_id": "g1", "distribution": "a", "n_parameters": 2, "fit_status": "success", "AIC": 10.0, "aic_comparable": True, "delta_AIC": 0.0},
            {"group_id": "g2", "distribution": "a", "n_parameters": 2, "fit_status": "success", "AIC": 11.0, "aic_comparable": True, "delta_AIC": np.nan},
            {"group_id": "g1", "distribution": "b", "n_parameters": 3, "fit_status": "success", "AIC": 12.0, "aic_comparable": True, "delta_AIC": 2.0},
            {"group_id": "g2", "distribution": "b", "n_parameters": 3, "fit_status": "success", "AIC": 1.0, "aic_comparable": False, "delta_AIC": np.nan},
        ]
    )
    summary = summarize_candidate_diagnostics(details, n_groups_requested=2)
    b = summary.loc[summary["distribution"] == "b"].iloc[0]

    assert b["AIC_coverage_pct"] == 100.0
    assert b["AIC_comparable_coverage_pct"] == 50.0
    assert b["mean_delta_AIC_denominator"] == 1
    assert b["aic_win_rate_denominator"] == 1

    ranked = rank_aggregated_candidates(
        summary, min_valid_group_fraction=0.80, information_criterion="AIC"
    )
    assert ranked["best_distribution"] == "a"
    assert "candidate_specific_sensitivity" in ranked["comparison_population_status"]


def test_invalid_cdf_values_are_not_hidden_by_probability_clipping() -> None:
    class InvalidCdfModel:
        def cdf(self) -> pd.Series:
            return pd.Series([-0.1, 0.5, 1.1])

    raw = pd.Series([1.0, 2.0, 3.0])
    spi = _spi_from_fitted_model(InvalidCdfModel(), raw, prob_zero=True)
    assert np.isnan(spi.iloc[0])
    assert spi.iloc[1] == 0.0
    assert np.isnan(spi.iloc[2])


def test_daily_ten_day_semantics_are_rolling_not_dasarian(prec_34010701a) -> None:
    engine = SI(
        series=prec_34010701a,
        dist=gamma,
        timescale=10,
        fit_freq="D",
        prob_zero=True,
    )
    expected = prec_34010701a.rolling(10, min_periods=10).sum().dropna()
    pd.testing.assert_series_equal(engine.series, expected)
    assert engine._is_dasarian is False

