"""Automatic probability-distribution selection for SPI fitting.

This module is designed to sit beside ``dist.py`` in the same package.
It separates the responsibilities of fitting one candidate distribution (Dist)
from comparing candidates and recommending a model.

Selection policy
----------------
1. Fit every candidate and calculate a comparable log-likelihood AIC for the
   positive-precipitation component. For distributions whose support extends
   below zero, the likelihood is conditional on X > 0.
2. Calculate Delta AIC against the lowest AIC.
3. Use candidates with Delta AIC < ``delta_aic_threshold`` as the initial
   competitive set.
4. Test K-S and Anderson-Darling using Dist.goodness_of_fit(), which performs
   parametric-bootstrap calibration and refits each bootstrap sample.
5. Among competitive candidates that are not rejected by either test, prefer a
   two-parameter model when requested; otherwise choose the lowest-AIC candidate.
6. If no competitive candidate passes both tests, evaluate remaining candidates
   in AIC order until a candidate passes. If none passes, return a provisional
   recommendation explicitly flagged as such.
7. Shapiro-Wilk is applied to transformed SPI values for every candidate. Its
   rejection frequency is primarily intended as a batch-level diagnostic across
   independent fitted groups, not as a hard single-group selection threshold.

Important methodological notes
------------------------------
- Supply one independent fitting group at a time, e.g. accumulated rainfall for
  one station, one SPI time scale, and one calendar day across reference years.
- Do not use Shapiro-Wilk directly on a full rolling SPI time series with serial
  autocorrelation.
- For a fair KS/AD rejection-frequency comparison across candidates, set
  ``gof_scope='all'``. The default ``'competitive'`` scope is faster and tests
  the Delta-AIC shortlist first.
- AIC comparison is most defensible when the fitted parameter estimates are MLEs.
  Dist supports a fallback chain, but currently does not expose a public flag
  indicating which estimation stage produced each final fit.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any, Literal
import logging

import numpy as np
import pandas as pd
from scipy import stats

try:  # Expected usage: this file is a sibling of dist.py in the same package.
    from .dist import Dist, _MIN_CONDITIONAL_SURVIVAL
except ImportError:
    try:
        from spei.dist import Dist, _MIN_CONDITIONAL_SURVIVAL
    except ImportError:
        from dist import Dist, _MIN_CONDITIONAL_SURVIVAL  # type: ignore[import-not-found, no-redef]

logger = logging.getLogger(__name__)

# These are the distributions currently handled by the supplied Dist.fit_dist().
# Users can pass a custom mapping to select_best_distribution().
DEFAULT_CANDIDATES: dict[str, Any] = {
    "gamma": stats.gamma,
    "weibull_min": stats.weibull_min,
    "gumbel_r": stats.gumbel_r,
    "lognorm": stats.lognorm,
    "fisk": stats.fisk,
    "pearson3": stats.pearson3,
    "genextreme": stats.genextreme,
}

# These families are fitted with location fixed at zero by the current Dist API.
# This list also follows the parameter-count logic in Dist.aic().
FIXED_ZERO_LOCATION = {"gamma", "weibull_min", "lognorm", "fisk"}

GofScope = Literal["all", "competitive", "none"]
InformationCriterion = Literal["AIC", "AICc"]


def _as_clean_series(data: pd.Series | Sequence[float] | np.ndarray) -> pd.Series:
    """Convert input to a finite, non-negative precipitation Series."""
    if isinstance(data, pd.Series):
        series = pd.to_numeric(data, errors="coerce").astype(float).dropna().copy()
    else:
        values = np.asarray(data, dtype=float).ravel()
        values = values[np.isfinite(values)]
        series = pd.Series(values, dtype=float)

    values = series.to_numpy(dtype=float)
    if not values.size:
        raise ValueError("Input data contains no finite observations.")
    if np.any(values < 0):
        raise ValueError("SPI precipitation data must be non-negative; negative values found.")
    return series


def _normalise_candidates(
    candidates: Mapping[str, Any] | Sequence[Any] | None,
) -> dict[str, Any]:
    """Return a stable {label: scipy.stats distribution} mapping."""
    if candidates is None:
        return dict(DEFAULT_CANDIDATES)
    if isinstance(candidates, Mapping):
        normalised = {str(name): dist for name, dist in candidates.items()}
    else:
        normalised = {
            str(getattr(dist, "name", f"candidate_{i + 1}")): dist
            for i, dist in enumerate(candidates)
        }
    if not normalised:
        raise ValueError("At least one candidate distribution is required.")
    for label, dist in normalised.items():
        if not hasattr(dist, "cdf") or not hasattr(dist, "rvs"):
            raise TypeError(f"Candidate {label!r} is not a scipy.stats-like distribution.")
    return normalised


def _model_args(model: Dist) -> tuple[float, ...]:
    shapes = tuple(model.pars) if model.pars is not None else ()
    return (*shapes, float(model.loc), float(model.scale))


def _parameter_count(model: Dist) -> int:
    """Count distribution parameters using the convention in Dist.aic()."""
    name = getattr(model.dist, "name", "")
    # Count the family's free shape parameters, not the length of a possibly
    # failed fitted vector. This keeps Pearson III and GEV at k=3 even when a
    # fit fails before ``pars`` is populated.
    n_shape = int(
        getattr(
            model.dist,
            "numargs",
            len(model.pars) if model.pars is not None else 0,
        )
    )
    n_scale = 1
    n_location = 0 if name in FIXED_ZERO_LOCATION else 1
    return int(n_shape + n_scale + n_location)


def _conditional_aic(
    model: Dist,
    raw_data: pd.Series,
    *,
    prob_zero: bool,
) -> tuple[float, float, int, float, bool, str]:
    """Calculate AIC from the fitted positive-precipitation likelihood.

    For candidate distributions with support below zero (e.g. Gumbel or
    Pearson-III), normalize the fitted density conditional on X > 0.
    AIC_positive = -2 * loglik_positive_conditional + 2 * k.

    Returns (AIC, log_likelihood, parameter_count, log_likelihood_positive, aic_comparable, aic_incomparable_reason).
    """
    result = _conditional_information_criteria(model, raw_data, prob_zero=prob_zero)
    return (
        result["AIC"],
        result["loglik"],
        result["n_parameters"],
        result["loglik_positive_conditional"],
        result["aic_comparable"],
        result["aic_incomparable_reason"],
    )


def _conditional_information_criteria(
    model: Dist,
    raw_data: pd.Series,
    *,
    prob_zero: bool,
) -> dict[str, Any]:
    """Evaluate AIC and AICc from the likelihood used for fitting.

    For zero-inflated precipitation, ``n_observations_ic`` is the number of
    strictly positive calibration observations in the conditional likelihood.
    For an unconditional fit it is the number of finite calibration values.
    AICc is intentionally undefined when ``n <= k + 1``; it is never replaced
    by AIC.
    """
    cal_data = model.data_window if getattr(model, "data_window", None) is not None else raw_data
    values = np.asarray(pd.Series(cal_data).dropna(), dtype=float)
    values = values[np.isfinite(values)]
    x = values[values > 0.0] if prob_zero else values
    n_obs = int(x.size)
    k = _parameter_count(model)

    is_comp = getattr(model, "aic_comparable", False)
    incomp_reason = getattr(model, "aic_incomparable_reason", "none")

    base = {
        "AIC": np.nan,
        "AICc": np.nan,
        "loglik": np.nan,
        "loglik_positive_conditional": np.nan,
        "n_parameters": k,
        "n_observations_ic": n_obs,
        "aic_comparable": False,
        "aicc_comparable": False,
        "aic_incomparable_reason": incomp_reason,
        "aicc_incomparable_reason": incomp_reason,
    }

    if (
        n_obs < k
        or not np.isfinite(model.loc)
        or not np.isfinite(model.scale)
        or model.scale <= 0
    ):
        reason = incomp_reason if incomp_reason != "none" else "insufficient_sample"
        base["aic_incomparable_reason"] = reason
        base["aicc_incomparable_reason"] = reason
        return base

    args = _model_args(model)
    try:
        log_pdf = np.asarray(model.dist.logpdf(x, *args), dtype=float)
        if not np.all(np.isfinite(log_pdf)):
            base["aic_incomparable_reason"] = "invalid_support"
            base["aicc_incomparable_reason"] = "invalid_support"
            return base

        condition_positive = bool(
            prob_zero and getattr(model, "conditional_positive", True)
        )
        if condition_positive:
            logsf0 = float(model.dist.logsf(0.0, *args))
            if (
                not np.isfinite(logsf0)
                or logsf0 > 1e-12
                or logsf0 < float(np.log(_MIN_CONDITIONAL_SURVIVAL))
            ):
                base["aic_incomparable_reason"] = "invalid_survival_at_zero"
                base["aicc_incomparable_reason"] = "invalid_survival_at_zero"
                return base
        else:
            logsf0 = 0.0

        log_cond_pdf = log_pdf - logsf0
        if not np.all(np.isfinite(log_cond_pdf)):
            base["aic_incomparable_reason"] = "non_finite_conditional_likelihood"
            base["aicc_incomparable_reason"] = "non_finite_conditional_likelihood"
            return base

        loglik_positive = float(np.sum(log_cond_pdf))
        aic = float(-2.0 * loglik_positive + 2.0 * k)
        aicc = (
            float(aic + (2.0 * k * (k + 1.0)) / (n_obs - k - 1.0))
            if n_obs > k + 1
            else np.nan
        )
        base.update(
            {
                "AIC": aic,
                "AICc": aicc,
                "loglik": loglik_positive,
                "loglik_positive_conditional": loglik_positive,
                "aic_comparable": bool(is_comp),
                "aicc_comparable": bool(is_comp and np.isfinite(aicc)),
                "aic_incomparable_reason": incomp_reason,
                "aicc_incomparable_reason": (
                    incomp_reason
                    if not is_comp
                    else "none"
                    if np.isfinite(aicc)
                    else "aicc_undefined_n_le_k_plus_1"
                ),
            }
        )
        return base
    except (ValueError, FloatingPointError, OverflowError, TypeError) as err:
        reason = f"likelihood_exception_{type(err).__name__}"
        base["aic_incomparable_reason"] = reason
        base["aicc_incomparable_reason"] = reason
        return base


def standard_normal_anderson(
    z_values: np.ndarray,
    alpha: float = 0.05,
) -> tuple[float, float, bool]:
    """Anderson-Darling goodness-of-fit test against standard normal N(0, 1) with fixed parameters.

    Under Case 0 (fixed parameters mu=0, sigma=1):
        A^2 = -n - (1/n) * sum_{i=1}^n (2i - 1) * [ln(Phi(z_i)) + ln(1 - Phi(z_{n+1-i}))]

    Critical values for Case 0 (Stephens 1974):
    - alpha=0.10: 1.933
    - alpha=0.05: 2.492
    - alpha=0.025: 3.070
    - alpha=0.01: 3.857

    Returns (statistic, critical_value, passes_test).
    """
    z = np.sort(np.asarray(z_values, dtype=float))
    z = z[np.isfinite(z)]
    n = z.size
    if n < 3:
        return np.nan, np.nan, False

    u = stats.norm.cdf(z)
    eps = np.finfo(float).eps
    u = np.clip(u, eps, 1.0 - eps)
    i = np.arange(1, n + 1, dtype=float)
    a2 = float(-n - np.sum((2.0 * i - 1.0) * (np.log(u) + np.log(1.0 - u[::-1]))) / n)

    crit_map = {0.10: 1.933, 0.05: 2.492, 0.025: 3.070, 0.01: 3.857}
    crit = crit_map.get(alpha, 2.492)
    return a2, crit, bool(a2 < crit)


def _spi_from_fitted_model(
    model: Dist,
    raw_data: pd.Series,
    *,
    prob_zero: bool,
    clip: tuple[float, float] | None = None,
) -> pd.Series:
    """Transform the fitted model's CDF to standard-normal SPI using model.cdf().

    Uses Dist.cdf() as the single source of truth, preserving the mixture
    rule for positive precipitation and the plotting-position centroid for
    exact zeros, while respecting any all-zero group policy.
    """
    q_series = model.cdf().reindex(raw_data.index)
    q = q_series.to_numpy(dtype=float)

    eps = np.finfo(float).eps
    # Only mathematically valid probabilities may reach norm.ppf.  Clipping is
    # for exact 0/1 tail protection, not a repair for an invalid CDF.
    valid_mask = np.isfinite(q) & (q >= 0.0) & (q <= 1.0)
    spi = np.full(q.shape, np.nan, dtype=float)
    if np.any(valid_mask):
        spi[valid_mask] = stats.norm.ppf(np.clip(q[valid_mask], eps, 1.0 - eps))
        if clip is not None:
            spi[valid_mask] = np.clip(spi[valid_mask], clip[0], clip[1])
    return pd.Series(spi, index=raw_data.index, name="SPI", dtype=float)


def _derive_seed(seed_sequence: np.random.SeedSequence) -> int:
    return int(seed_sequence.generate_state(1, dtype=np.uint32)[0])


def _test_candidate_gof(
    model: Dist,
    *,
    n_boot: int,
    random_state: int | None,
) -> dict[str, Any]:
    """Run the user's bootstrap KS/AD API and normalize its output fields."""
    if n_boot < 1:
        return {
            "KS_statistic": np.nan,
            "KS_pvalue": np.nan,
            "AD_statistic": np.nan,
            "AD_pvalue": np.nan,
            "n_test": int(np.sum(np.asarray(model.data, dtype=float) > 0.0)),
            "n_boot_requested": 0,
            "n_boot_valid": 0,
            "bootstrap_success_rate": np.nan,
        }
    try:
        return model.goodness_of_fit(n_boot=n_boot, random_state=random_state)
    except Exception as exc:  # Keep one failed candidate from stopping the shortlist.
        logger.warning("KS/AD bootstrap failed for %s: %s", model.dist.name, exc)
        return {
            "KS_statistic": np.nan,
            "KS_pvalue": np.nan,
            "AD_statistic": np.nan,
            "AD_pvalue": np.nan,
            "n_test": int(np.sum(np.asarray(model.data, dtype=float) > 0.0)),
            "n_boot_requested": int(n_boot),
            "n_boot_valid": 0,
            "bootstrap_success_rate": 0.0,
        }


def _gof_is_usable_and_passes(
    row: Mapping[str, Any],
    *,
    alpha: float,
    min_bootstrap_success: float,
) -> tuple[bool, bool]:
    """Return (test_is_usable, both KS and AD do not reject)."""
    p_ks = row.get("KS_pvalue", np.nan)
    p_ad = row.get("AD_pvalue", np.nan)
    success = row.get("bootstrap_success_rate", np.nan)
    n_valid = row.get("n_boot_valid", 0)
    usable = (
        np.isfinite(p_ks)
        and np.isfinite(p_ad)
        and np.isfinite(success)
        and success >= min_bootstrap_success
        and n_valid > 0
    )
    passes = bool(usable and p_ks >= alpha and p_ad >= alpha)
    return bool(usable), passes


def _rank_rows(
    rows: pd.DataFrame,
    *,
    prefer_two_parameters: bool,
    information_criterion: InformationCriterion = "AIC",
) -> pd.DataFrame:
    """Rank eligible candidates deterministically by parameter count and AIC.

    Receives only candidates that satisfy eligibility requirements (finite AIC,
    valid parameters, and passing GoF where required). Prioritizes candidates with
    official comparable AIC over non-comparable fallbacks. Applies the two-parameter
    preference strictly among eligible candidates, ordering two-parameter models
    first (by AIC ascending, then distribution name ascending for tie-breaks),
    followed by three-parameter models (similarly ordered).
    """
    criterion_col = information_criterion
    comparable_col = "aic_comparable" if information_criterion == "AIC" else "aicc_comparable"
    if comparable_col in rows.columns:
        valid_comp = rows.loc[
            rows[comparable_col].eq(True)
            & np.isfinite(pd.to_numeric(rows[criterion_col], errors="coerce"))
        ].copy()
        if not valid_comp.empty:
            valid = valid_comp
        else:
            valid = rows.loc[
                np.isfinite(pd.to_numeric(rows[criterion_col], errors="coerce"))
            ].copy()
    else:
        valid = rows.loc[
            np.isfinite(pd.to_numeric(rows[criterion_col], errors="coerce"))
        ].copy()

    if valid.empty:
        return pd.DataFrame()

    if prefer_two_parameters:
        two_param = valid.loc[valid["n_parameters"] == 2].sort_values(
            [criterion_col, "distribution"], kind="mergesort"
        )
        other_param = valid.loc[valid["n_parameters"] != 2].sort_values(
            [criterion_col, "distribution"], kind="mergesort"
        )
        ranked = pd.concat([two_param, other_param], ignore_index=True)
    else:
        ranked = valid.sort_values(
            [criterion_col, "distribution"], kind="mergesort"
        ).reset_index(drop=True)

    return ranked


def _choose_from_rows(
    rows: pd.DataFrame,
    *,
    prefer_two_parameters: bool,
) -> str:
    """Choose lowest-AIC row, preserving backward compatibility."""
    ranked = _rank_rows(rows, prefer_two_parameters=prefer_two_parameters)
    if ranked.empty:
        raise ValueError("No candidate has a valid AIC value.")
    return str(ranked.iloc[0]["distribution"])


def _add_delta_information_criteria(
    frame: pd.DataFrame,
    *,
    delta_threshold: float,
) -> pd.DataFrame:
    """Add official Delta AIC/AICc without treating a singleton as a win."""
    table = frame.copy()
    for criterion, comparable_col in (
        ("AIC", "aic_comparable"),
        ("AICc", "aicc_comparable"),
    ):
        values = pd.to_numeric(table.get(criterion, np.nan), errors="coerce")
        comparable = table.get(
            comparable_col, pd.Series(False, index=table.index, dtype=bool)
        ).fillna(False).astype(bool)
        valid = comparable & np.isfinite(values)
        n_comparable = int(valid.sum())
        count_col = (
            "n_comparable_candidates"
            if criterion == "AIC"
            else "n_AICc_comparable_candidates"
        )
        status_col = f"{criterion}_comparison_status"
        delta_col = f"delta_{criterion}"
        competitive_col = f"{criterion}_competitive"
        table[count_col] = n_comparable
        if n_comparable >= 2:
            minimum = float(values.loc[valid].min())
            table[delta_col] = np.where(valid, values - minimum, np.nan)
            table[competitive_col] = valid & (table[delta_col] < delta_threshold)
            table[status_col] = np.where(
                valid, "comparable", "candidate_incomparable"
            )
        else:
            table[delta_col] = np.nan
            table[competitive_col] = False
            table[status_col] = "insufficient_comparable_candidates"
    return table


def select_best_distribution(
    data: pd.Series | Sequence[float] | np.ndarray,
    candidates: Mapping[str, Any] | Sequence[Any] | None = None,
    *,
    data_window: pd.Series | Sequence[float] | np.ndarray | None = None,
    prob_zero: bool = True,
    alpha: float = 0.05,
    delta_aic_threshold: float = 2.0,
    prefer_two_parameters: bool = True,
    n_boot: int = 199,
    gof_scope: GofScope = "competitive",
    min_bootstrap_success: float = 0.80,
    random_state: int | None = 42,
    sw_clip: tuple[float, float] | None = None,
    fitting_policy: Literal["standard", "wang"] = "standard",
    small_sample_policy: Literal["strict", "augmented", "pseudo_observation_experimental"] = "strict",
    all_zero_policy: Literal["stagge", "wang"] = "stagge",
    information_criterion: InformationCriterion = "AIC",
) -> dict[str, Any]:
    """Fit candidate distributions and return Best (#1) and Alternative (#2) recommendations.

    Parameters
    ----------
    data:
        Target observations of accumulated precipitation for one station ×
        timescale × calendar day across years.
    candidates:
        Mapping ``{label: scipy.stats distribution}``. Defaults to standard
        candidates (gamma, weibull_min, gumbel_r, lognorm, fisk, pearson3, genextreme).
    data_window:
        Optional calibration window observations (when fit_window > 0). If provided,
        parameter estimation and AIC evaluation use data_window, while transformed
        SPI series is evaluated on the target observations in data.
    prob_zero:
        Enable zero-mass handling implemented by Dist.
    alpha:
        Significance level for bootstrap KS/AD and normality diagnostics.
    delta_aic_threshold:
        Candidates with Delta AIC strictly below this threshold form the competitive set.
        Default 2 follows Burnham & Anderson (2002).
    prefer_two_parameters:
        Within eligible candidates, prioritize two-parameter distributions.
    n_boot:
        Number of parametric-bootstrap replicates requested for GoF testing.
    gof_scope:
        ``'competitive'``: test AIC shortlist first; if fewer than 2 candidates pass,
        progressively test remaining candidates in AIC order until 2 pass or all tested.
        ``'all'``: run bootstrap KS/AD for every candidate.
        ``'none'``: skip KS/AD and select using AIC and parameter count only.
    min_bootstrap_success:
        Minimum fraction of valid bootstrap refits for a KS/AD result to be usable.
    random_state:
        Seed for reproducible zero replacements and bootstrap samples.
    sw_clip:
        Optional clipping for transformed SPI before S-W test. Default is None.
    fitting_policy:
        Distribution fitting policy ('standard' or 'wang').
    small_sample_policy:
        Policy for handling small sample sizes ('strict', 'augmented', or legacy 'pseudo_observation_experimental').
    all_zero_policy:
        Policy for all-zero groups ('stagge' or 'wang').
    information_criterion:
        Official competitive-set criterion. ``'AIC'`` preserves the historical
        default; ``'AICc'`` uses the positive calibration sample size and never
        substitutes AIC when AICc is undefined.
    """
    if not 0.0 < alpha < 1.0:
        raise ValueError("alpha must be between 0 and 1.")
    if delta_aic_threshold <= 0:
        raise ValueError("delta_aic_threshold must be > 0.")
    if not 0.0 <= min_bootstrap_success <= 1.0:
        raise ValueError("min_bootstrap_success must be between 0 and 1.")
    if gof_scope not in {"all", "competitive", "none"}:
        raise ValueError("gof_scope must be 'all', 'competitive', or 'none'.")
    if n_boot < 1 and gof_scope != "none":
        raise ValueError("n_boot must be >= 1 unless gof_scope='none'.")
    if information_criterion not in {"AIC", "AICc"}:
        raise ValueError("information_criterion must be 'AIC' or 'AICc'.")

    criterion_col = information_criterion
    criterion_comparable_col = (
        "aic_comparable" if information_criterion == "AIC" else "aicc_comparable"
    )

    series = _as_clean_series(data)
    window_series = _as_clean_series(data_window) if data_window is not None else None
    eval_series = window_series if window_series is not None else series

    candidate_map = _normalise_candidates(candidates)
    n_zero = int(np.sum(series.to_numpy(dtype=float) == 0.0))
    n_positive = int(np.sum(series.to_numpy(dtype=float) > 0.0))
    n_pos_cal = int(np.sum(eval_series.to_numpy(dtype=float) > 0.0))

    if n_pos_cal < 3:
        raise ValueError(
            f"At least 3 positive accumulated-rainfall samples are required; found {n_pos_cal}."
        )

    # Master seed root: derive fair shared seed for S-W zero-replacement across candidates,
    # and separate independent seeds for each candidate's bootstrap GoF.
    seed_root = np.random.SeedSequence(random_state)
    sw_zero_seed = _derive_seed(seed_root.spawn(1)[0])
    candidate_seed_sequences = seed_root.spawn(max(1, len(candidate_map)))
    seed_map: dict[str, int] = {}
    for i, label in enumerate(candidate_map):
        seed_map[label] = _derive_seed(candidate_seed_sequences[i])

    models: dict[str, Dist] = {}
    row_by_label: dict[str, dict[str, Any]] = {}

    # Stage 1: fit all candidates and compute AIC, S-W, and SPI Anderson-Darling diagnostics.
    for label, distribution in candidate_map.items():
        base_row: dict[str, Any] = {
            "distribution": label,
            "scipy_distribution": getattr(distribution, "name", label),
            "n_parameters": np.nan,
            "parameters": None,
            "loc": np.nan,
            "scale": np.nan,
            "p0": np.nan,
            "converged": False,
            "optimizer_attempts": 0,
            "optimizer_failed_attempts": 0,
            "optimizer_nfev": 0,
            "optimization_seconds": 0.0,
            "initialization_seconds": 0.0,
            "scipy_initialization_seconds": 0.0,
            "total_fit_seconds": 0.0,
            "fallback_used": False,
            "AIC": np.nan,
            "AICc": np.nan,
            "loglik": np.nan,
            "loglik_positive_conditional": np.nan,
            "is_mle": False,
            "aic_comparable": False,
            "aic_incomparable_reason": "none",
            "official_AIC": np.nan,
            "official_AICc": np.nan,
            "delta_AIC": np.nan,
            "delta_AICc": np.nan,
            "n_observations_ic": n_pos_cal,
            "aicc_comparable": False,
            "aicc_incomparable_reason": "none",
            "n_comparable_candidates": 0,
            "n_AICc_comparable_candidates": 0,
            "AIC_comparison_status": "not_evaluated",
            "AICc_comparison_status": "not_evaluated",
            "n_positive": n_pos_cal,
            "n_fitting": n_pos_cal,
            "KS_statistic": np.nan,
            "KS_pvalue": np.nan,
            "AD_statistic": np.nan,
            "AD_pvalue": np.nan,
            "n_test": n_pos_cal,
            "n_boot_requested": 0,
            "n_boot_valid": 0,
            "bootstrap_success_rate": np.nan,
            "gof_tested": False,
            "gof_usable": False,
            "gof_pass": None,
            "SW_statistic": np.nan,
            "SW_pvalue": np.nan,
            "SW_reject_normality": None,
            "SW_spi_mean": np.nan,
            "SW_spi_std": np.nan,
            "SW_n_replaced_zero": 0,
            "SPI_AD_statistic": np.nan,
            "SPI_AD_critical_value": np.nan,
            "SPI_AD_pass": None,
            "SPI_AD_tested": False,
            "n_finite_spi": 0,
            "n_nan_spi": int(len(series)),
            "spi_status": "not_evaluated",
            "spi_failure_reason": "none",
            "error": None,
        }
        try:
            model = Dist(
                data=series,
                dist=distribution,
                prob_zero=prob_zero,
                data_window=window_series,
                fitting_policy=fitting_policy,
                small_sample_policy=small_sample_policy,
                all_zero_policy=all_zero_policy,
            )
            models[label] = model
            ic = _conditional_information_criteria(
                model, series, prob_zero=prob_zero
            )
            base_row.update({
                "n_parameters": ic["n_parameters"],
                "parameters": repr({
                    "shape": model.pars,
                    "loc": float(model.loc),
                    "scale": float(model.scale),
                }),
                "loc": float(model.loc),
                "scale": float(model.scale),
                "p0": float(model.p0),
                "fit_status": model.fit_status,
                "fit_method": model.fit_method,
                "converged": getattr(model, "converged", False),
                "optimizer_attempts": getattr(model, "optimizer_attempts", 0),
                "optimizer_failed_attempts": getattr(model, "optimizer_failed_attempts", 0),
                "optimizer_nfev": getattr(model, "optimizer_nfev", 0),
                "optimization_seconds": getattr(model, "optimization_seconds", 0.0),
                "initialization_seconds": getattr(model, "initialization_seconds", 0.0),
                "scipy_initialization_seconds": getattr(model, "scipy_initialization_seconds", 0.0),
                "total_fit_seconds": getattr(model, "total_fit_seconds", 0.0),
                "fallback_used": getattr(model, "fallback_used", False),
                "pseudo_obs_added": model.pseudo_obs_added,
                "small_sample_warning": model.small_sample_warning,
                "AIC": ic["AIC"],
                "AICc": ic["AICc"],
                "loglik": ic["loglik"],
                "loglik_positive_conditional": ic["loglik_positive_conditional"],
                "is_mle": model.is_mle,
                "aic_comparable": ic["aic_comparable"],
                "aic_incomparable_reason": ic["aic_incomparable_reason"],
                "aicc_comparable": ic["aicc_comparable"],
                "aicc_incomparable_reason": ic["aicc_incomparable_reason"],
                "official_AIC": ic["AIC"] if ic["aic_comparable"] else np.nan,
                "official_AICc": ic["AICc"] if ic["aicc_comparable"] else np.nan,
                "n_observations_ic": ic["n_observations_ic"],
                "n_positive": getattr(model, "n_positive", n_pos_cal),
                "n_fitting": getattr(model, "n_fitting", n_pos_cal),
            })

            # SPI series from model.cdf() evaluated on target observations
            spi_values = _spi_from_fitted_model(
                model, series, prob_zero=prob_zero, clip=sw_clip
            )
            spi_array = spi_values.to_numpy(dtype=float)
            n_finite_spi = int(np.isfinite(spi_array).sum())
            n_nan_spi = int((~np.isfinite(spi_array)).sum())
            spi_status = "success" if n_finite_spi == len(spi_array) else "partial_or_failed"
            spi_failure_reason = (
                "none"
                if n_nan_spi == 0
                else getattr(model, "cdf_failure_reason", "non_finite_spi")
                if n_finite_spi == 0
                else "input_or_group_values_not_transformed"
            )

            # S-W test using fair group-level zero replacement seed
            sw = model.shapiro_wilk_test(
                spi_values=spi_values,
                zero_mask=(series == 0.0),
                alpha=alpha,
                random_state=sw_zero_seed,
                replace_zero_with_normal=prob_zero,
                clip=sw_clip,
            )

            # SPI Anderson-Darling standard normality test (testing against standard normal N(0, 1))
            spi_clean = spi_values.dropna().to_numpy(dtype=float)
            spi_clean = spi_clean[np.isfinite(spi_clean)]
            spi_ad_stat = np.nan
            spi_ad_crit = np.nan
            spi_ad_pass = None
            if spi_clean.size >= 8:
                try:
                    spi_ad_stat, spi_ad_crit, spi_ad_pass = standard_normal_anderson(
                        spi_clean, alpha=alpha
                    )
                except Exception as e_ad:
                    logger.debug("SPI AD standard normality test failed for %s: %s", label, e_ad)

            base_row.update({
                "SW_statistic": sw.get("SW_statistic", np.nan),
                "SW_pvalue": sw.get("SW_pvalue", np.nan),
                "SW_reject_normality": sw.get("reject_normality"),
                "SW_spi_mean": sw.get("spi_mean", np.nan),
                "SW_spi_std": sw.get("spi_std", np.nan),
                "SW_n_replaced_zero": sw.get("n_zero_replaced", 0),
                "SPI_AD_statistic": spi_ad_stat,
                "SPI_AD_critical_value": spi_ad_crit,
                "SPI_AD_pass": spi_ad_pass,
                "SPI_AD_tested": bool(spi_clean.size >= 8 and np.isfinite(spi_ad_stat)),
                "n_finite_spi": n_finite_spi,
                "n_nan_spi": n_nan_spi,
                "spi_status": spi_status,
                "spi_failure_reason": spi_failure_reason,
            })
        except Exception as exc:
            base_row["error"] = f"{type(exc).__name__}: {exc}"
            logger.warning("Candidate %s failed: %s", label, exc)
        row_by_label[label] = base_row

    comparison = _add_delta_information_criteria(
        pd.DataFrame(list(row_by_label.values())),
        delta_threshold=delta_aic_threshold,
    )
    comparison["information_criterion"] = information_criterion
    comparison["criterion_value"] = comparison[criterion_col]
    comparison["delta_IC"] = comparison[f"delta_{criterion_col}"]
    comparison["IC_competitive"] = comparison[f"{criterion_col}_competitive"]
    comparison["ic_comparable"] = comparison[criterion_comparable_col]

    valid_any_aic = comparison[
        np.isfinite(pd.to_numeric(comparison[criterion_col], errors="coerce"))
    ].copy()
    if valid_any_aic.empty:
        raise RuntimeError(
            f"All candidate fits failed or produced invalid {criterion_col} values."
        )

    comparable_aic = comparison[
        comparison[criterion_comparable_col].eq(True)
        & np.isfinite(pd.to_numeric(comparison[criterion_col], errors="coerce"))
    ].copy()
    official_comparison_sufficient = len(comparable_aic) >= 2

    # Stage 2: GoF testing
    if gof_scope == "all":
        candidates_to_test = list(valid_any_aic.sort_values(criterion_col)["distribution"])
    elif gof_scope == "competitive":
        candidates_to_test = list(
            comparison.loc[comparison["IC_competitive"], "distribution"]
        )
    else:
        candidates_to_test = []

    tested: set[str] = set()

    def test_gof_for_label(label: str) -> None:
        if label in tested or label not in models:
            return
        gof = _test_candidate_gof(
            models[label], n_boot=n_boot, random_state=seed_map[label]
        )
        row_by_label[label].update(gof)
        row_by_label[label]["gof_tested"] = True
        usable, passed = _gof_is_usable_and_passes(
            row_by_label[label], alpha=alpha,
            min_bootstrap_success=min_bootstrap_success,
        )
        row_by_label[label]["gof_usable"] = usable
        row_by_label[label]["gof_pass"] = passed if usable else None
        tested.add(label)

    for label in candidates_to_test:
        test_gof_for_label(str(label))

    def current_table() -> pd.DataFrame:
        table = _add_delta_information_criteria(
            pd.DataFrame([row_by_label[label] for label in candidate_map]),
            delta_threshold=delta_aic_threshold,
        )
        table["information_criterion"] = information_criterion
        table["criterion_value"] = table[criterion_col]
        table["delta_IC"] = table[f"delta_{criterion_col}"]
        table["IC_competitive"] = table[f"{criterion_col}_competitive"]
        table["ic_comparable"] = table[criterion_comparable_col]
        return table

    comparison = current_table()

    def passing_candidates(frame: pd.DataFrame, competitive_only: bool) -> pd.DataFrame:
        mask = (
            frame["gof_pass"].eq(True)
            & frame[criterion_comparable_col].eq(True)
            & np.isfinite(pd.to_numeric(frame[criterion_col], errors="coerce"))
        )
        if competitive_only:
            mask &= frame["IC_competitive"]
        return frame.loc[mask].copy()

    # In competitive GoF mode, if fewer than 2 candidates pass, test remaining candidates in AIC order
    # until 2 passing candidates are found or all candidates are tested.
    competitive_pass = passing_candidates(comparison, competitive_only=True)
    if gof_scope == "competitive":
        untested = comparison.loc[
            np.isfinite(pd.to_numeric(comparison[criterion_col], errors="coerce"))
            & (~comparison["distribution"].isin(tested))
        ].sort_values([criterion_col, "distribution"], kind="mergesort")

        for label in untested["distribution"].astype(str):
            if len(passing_candidates(comparison, competitive_only=False)) >= 2:
                break
            test_gof_for_label(label)
            comparison = current_table()

        competitive_pass = passing_candidates(comparison, competitive_only=True)

    all_pass = passing_candidates(comparison, competitive_only=False)

    alt_label: str | None = None
    alt_status: str | None = None
    alt_reason: str | None = None

    if not official_comparison_sufficient:
        provisional_pool = comparable_aic if not comparable_aic.empty else valid_any_aic
        ranked = _rank_rows(
            provisional_pool,
            prefer_two_parameters=prefer_two_parameters,
            information_criterion=information_criterion,
        )
        chosen_label = str(ranked.iloc[0]["distribution"])
        selection_status = "provisional_insufficient_comparison"
        reason = (
            f"Only {len(comparable_aic)} candidate(s) had comparable {criterion_col}; "
            "at least two are required for an official Delta IC comparison."
        )
        gof_adequate = None
        if len(ranked) >= 2:
            alt_label = str(ranked.iloc[1]["distribution"])
            alt_status = "provisional_insufficient_comparison"
            alt_reason = "Provisional alternative; no official competitive set exists."
        else:
            alt_status = "no_alternative_available"
            alt_reason = "No second comparable candidate is available."

    elif gof_scope == "none":
        eligible = comparison.loc[
            comparison["IC_competitive"]
            & np.isfinite(pd.to_numeric(comparison[criterion_col], errors="coerce"))
        ].copy()
        if eligible.empty:
            eligible = comparable_aic.copy() if not comparable_aic.empty else valid_any_aic.copy()
        ranked = _rank_rows(
            eligible,
            prefer_two_parameters=prefer_two_parameters,
            information_criterion=information_criterion,
        )
        chosen_label = str(ranked.iloc[0]["distribution"])
        selection_status = "selected_by_information_criterion_only"
        reason = (
            f"Selected by {criterion_col}; Delta {criterion_col} < {delta_aic_threshold:g} "
            "defines the competitive set. "
            "KS/AD bootstrap tests were disabled."
        )
        if len(ranked) >= 2:
            alt_label = str(ranked.iloc[1]["distribution"])
            alt_status = "selected_by_information_criterion_only"
            alt_reason = (
                f"Alternative candidate from competitive set (Delta {criterion_col} < "
                f"{delta_aic_threshold:g}) ranked #2 by IC/parameter preference with "
                "bootstrap tests disabled."
            )
        else:
            alt_status = "no_alternative_available"
            alt_reason = "No eligible second candidate available in competitive set."
        gof_adequate = None

    elif not competitive_pass.empty:
        ranked_comp = _rank_rows(
            competitive_pass,
            prefer_two_parameters=prefer_two_parameters,
            information_criterion=information_criterion,
        )
        chosen_label = str(ranked_comp.iloc[0]["distribution"])
        selection_status = "selected_within_delta_aic_and_gof_acceptable"
        reason = (
            f"Selected from candidates with Delta {criterion_col} < {delta_aic_threshold:g} that were not "
            f"rejected by either bootstrap KS or AD at alpha={alpha:g}. "
        )
        chosen_row_temp = comparison.loc[comparison["distribution"] == chosen_label].iloc[0]
        if prefer_two_parameters and int(chosen_row_temp["n_parameters"]) == 2:
            reason += "A two-parameter candidate was available and was prioritized."
        else:
            reason += f"Lowest {criterion_col} among eligible competitive candidates was selected."
        gof_adequate = True

        if len(ranked_comp) >= 2:
            alt_label = str(ranked_comp.iloc[1]["distribution"])
            alt_status = "selected_within_delta_aic_and_gof_acceptable"
            alt_reason = (
                f"Alternative candidate also in competitive set (Delta {criterion_col} < {delta_aic_threshold:g}) "
                f"passing bootstrap KS and AD at alpha={alpha:g}."
            )
        else:
            outside_pass = all_pass.loc[~all_pass["distribution"].isin([chosen_label])]
            if not outside_pass.empty:
                ranked_out = _rank_rows(
                    outside_pass,
                    prefer_two_parameters=False,
                    information_criterion=information_criterion,
                )
                alt_label = str(ranked_out.iloc[0]["distribution"])
                alt_status = "fallback_outside_delta_aic"
                alt_reason = (
                    f"Only one competitive candidate passed GoF. Alternative candidate is the lowest-{criterion_col} "
                    f"model outside the competitive set (Delta {criterion_col} >= {delta_aic_threshold:g}) "
                    "passing both bootstrap tests."
                )
            else:
                alt_status = "no_alternative_available"
                alt_reason = "No second candidate passed both KS and AD bootstrap tests."

    elif not all_pass.empty:
        ranked_all = _rank_rows(
            all_pass,
            prefer_two_parameters=False,
            information_criterion=information_criterion,
        )
        chosen_label = str(ranked_all.iloc[0]["distribution"])
        selection_status = "fallback_outside_delta_aic"
        reason = (
            f"No candidate within Delta {criterion_col} < {delta_aic_threshold:g} passed both bootstrap tests. "
            f"Selected the lowest-{criterion_col} candidate among models that passed both KS and AD, "
            "even though it lies outside the initial competitive set."
        )
        gof_adequate = True
        if len(ranked_all) >= 2:
            alt_label = str(ranked_all.iloc[1]["distribution"])
            alt_status = "fallback_outside_delta_aic"
            alt_reason = (
                f"Alternative candidate is the second lowest-{criterion_col} model passing bootstrap KS and AD, "
                "outside the initial Delta AIC competitive set."
            )
        else:
            alt_status = "no_alternative_available"
            alt_reason = "Only one candidate across all tested models passed bootstrap GoF."

    else:
        eligible = comparison.loc[
            comparison["IC_competitive"]
            & np.isfinite(pd.to_numeric(comparison[criterion_col], errors="coerce"))
        ].copy()
        if eligible.empty:
            eligible = comparable_aic.copy() if not comparable_aic.empty else valid_any_aic.copy()
        ranked = _rank_rows(
            eligible,
            prefer_two_parameters=prefer_two_parameters,
            information_criterion=information_criterion,
        )
        chosen_label = str(ranked.iloc[0]["distribution"])
        selection_status = "provisional_no_candidate_passed_gof"
        reason = (
            "No tested candidate produced usable KS/AD results passing both tests. "
            f"This is a provisional recommendation based on the {criterion_col} competitive set and "
            "parameter-count preference; inspect fitting and bootstrap diagnostics."
        )
        gof_adequate = False
        if len(ranked) >= 2:
            alt_label = str(ranked.iloc[1]["distribution"])
            alt_status = "provisional_no_candidate_passed_gof"
            alt_reason = (
                f"Provisional alternative candidate based on {criterion_col} competitive set and parameter preference, "
                "as no candidate passed both bootstrap tests."
            )
        else:
            alt_status = "no_alternative_available"
            alt_reason = "No second candidate available in competitive set."

    comparison = current_table().sort_values(
        [criterion_col, "distribution"], kind="mergesort", na_position="last"
    ).reset_index(drop=True)

    chosen_row = comparison.loc[comparison["distribution"] == chosen_label].iloc[0]
    alt_row = (
        comparison.loc[comparison["distribution"] == alt_label].iloc[0]
        if alt_label is not None
        else None
    )

    recommendation = {
        "distribution": chosen_label,
        "scipy_distribution": chosen_row["scipy_distribution"],
        "n_parameters": int(chosen_row["n_parameters"]),
        "AIC": float(chosen_row["AIC"]),
        "AICc": float(chosen_row["AICc"]) if np.isfinite(chosen_row["AICc"]) else np.nan,
        "delta_AIC": float(chosen_row["delta_AIC"]) if np.isfinite(chosen_row["delta_AIC"]) else np.nan,
        "delta_AICc": float(chosen_row["delta_AICc"]) if np.isfinite(chosen_row["delta_AICc"]) else np.nan,
        "information_criterion": information_criterion,
        "criterion_value": float(chosen_row[criterion_col]),
        "delta_IC": float(chosen_row["delta_IC"]) if np.isfinite(chosen_row["delta_IC"]) else np.nan,
        "n_comparable_candidates": int(chosen_row["n_comparable_candidates"]),
        "n_AICc_comparable_candidates": int(chosen_row["n_AICc_comparable_candidates"]),
        "is_mle": bool(chosen_row.get("is_mle", False)),
        "aic_comparable": bool(chosen_row.get("aic_comparable", False)),
        "aic_incomparable_reason": str(chosen_row.get("aic_incomparable_reason", "none")),
        "official_AIC": float(chosen_row["official_AIC"]) if np.isfinite(chosen_row.get("official_AIC", np.nan)) else np.nan,
        "official_AICc": float(chosen_row["official_AICc"]) if np.isfinite(chosen_row.get("official_AICc", np.nan)) else np.nan,
        "loc": float(chosen_row["loc"]),
        "scale": float(chosen_row["scale"]),
        "parameters": chosen_row["parameters"],
        "p0": float(chosen_row["p0"]),
        "KS_pvalue": float(chosen_row["KS_pvalue"]) if np.isfinite(chosen_row["KS_pvalue"]) else np.nan,
        "AD_pvalue": float(chosen_row["AD_pvalue"]) if np.isfinite(chosen_row["AD_pvalue"]) else np.nan,
        "SW_pvalue": float(chosen_row["SW_pvalue"]) if np.isfinite(chosen_row["SW_pvalue"]) else np.nan,
        "SW_reject_normality": chosen_row["SW_reject_normality"],
        "SPI_AD_statistic": float(chosen_row["SPI_AD_statistic"]) if np.isfinite(chosen_row["SPI_AD_statistic"]) else np.nan,
        "SPI_AD_pass": chosen_row["SPI_AD_pass"],
        "gof_adequate": gof_adequate,
        "selection_status": selection_status,
        "reason": reason,

        "alternative_distribution": alt_label,
        "alternative_scipy_distribution": alt_row["scipy_distribution"] if alt_row is not None else None,
        "alternative_n_parameters": int(alt_row["n_parameters"]) if alt_row is not None else None,
        "alternative_AIC": float(alt_row["AIC"]) if alt_row is not None else np.nan,
        "alternative_AICc": float(alt_row["AICc"]) if alt_row is not None and np.isfinite(alt_row["AICc"]) else np.nan,
        "alternative_delta_AIC": float(alt_row["delta_AIC"]) if alt_row is not None and np.isfinite(alt_row["delta_AIC"]) else np.nan,
        "alternative_delta_AICc": float(alt_row["delta_AICc"]) if alt_row is not None and np.isfinite(alt_row["delta_AICc"]) else np.nan,
        "alternative_criterion_value": float(alt_row[criterion_col]) if alt_row is not None else np.nan,
        "alternative_delta_IC": float(alt_row["delta_IC"]) if alt_row is not None and np.isfinite(alt_row["delta_IC"]) else np.nan,
        "alternative_is_mle": bool(alt_row.get("is_mle", False)) if alt_row is not None else None,
        "alternative_aic_comparable": bool(alt_row.get("aic_comparable", False)) if alt_row is not None else None,
        "alternative_aic_incomparable_reason": str(alt_row.get("aic_incomparable_reason", "none")) if alt_row is not None else None,
        "alternative_official_AIC": float(alt_row["official_AIC"]) if alt_row is not None and np.isfinite(alt_row.get("official_AIC", np.nan)) else np.nan,
        "alternative_official_AICc": float(alt_row["official_AICc"]) if alt_row is not None and np.isfinite(alt_row.get("official_AICc", np.nan)) else np.nan,
        "alternative_loc": float(alt_row["loc"]) if alt_row is not None else np.nan,
        "alternative_scale": float(alt_row["scale"]) if alt_row is not None else np.nan,
        "alternative_parameters": alt_row["parameters"] if alt_row is not None else None,
        "alternative_p0": float(alt_row["p0"]) if alt_row is not None else np.nan,
        "alternative_KS_pvalue": float(alt_row["KS_pvalue"]) if alt_row is not None and np.isfinite(alt_row["KS_pvalue"]) else np.nan,
        "alternative_AD_pvalue": float(alt_row["AD_pvalue"]) if alt_row is not None and np.isfinite(alt_row["AD_pvalue"]) else np.nan,
        "alternative_SW_pvalue": float(alt_row["SW_pvalue"]) if alt_row is not None and np.isfinite(alt_row["SW_pvalue"]) else np.nan,
        "alternative_SW_reject_normality": alt_row["SW_reject_normality"] if alt_row is not None else None,
        "alternative_SPI_AD_statistic": float(alt_row["SPI_AD_statistic"]) if alt_row is not None and np.isfinite(alt_row["SPI_AD_statistic"]) else np.nan,
        "alternative_SPI_AD_pass": alt_row["SPI_AD_pass"] if alt_row is not None else None,
        "alternative_selection_status": alt_status,
        "alternative_reason": alt_reason,

        "alpha": float(alpha),
        "delta_aic_threshold": float(delta_aic_threshold),
        "gof_scope": gof_scope,
        "n_boot": int(n_boot if gof_scope != "none" else 0),
        "n_observations": int(len(series)),
        "n_positive": n_positive,
        "n_zero": n_zero,
    }

    return {
        "recommendation": recommendation,
        "comparison": comparison,
        "models": models,
        "selected_model": models[chosen_label],
        "alternative_model": models.get(alt_label) if alt_label is not None else None,
    }


def _evaluate_candidate_status(
    row: pd.Series | None,
    *,
    min_valid_group_fraction: float = 0.80,
    normality_ratio_threshold: float = 0.90,
    is_primary: bool = True,
) -> tuple[str, str]:
    """Determine statistical qualification status and rationale for a candidate."""
    if row is None:
        return "no_alternative_available", "No alternative candidate available."

    min_pct = min_valid_group_fraction * 100.0
    fit_cov = float(row.get("fit_coverage_pct", 0.0))
    aic_cov = float(
        row.get(
            "IC_comparable_coverage_pct",
            row.get("AIC_comparable_coverage_pct", row.get("AIC_coverage_pct", 0.0)),
        )
    )
    meets_norm = bool(row.get("meets_90pct_normality_target", False))
    ad_ratio = float(row.get("SPI_AD_group_pass_ratio", np.nan))
    dist_name = str(row.get("distribution", "candidate"))

    if fit_cov < min_pct or aic_cov < min_pct:
        status = "provisional_insufficient_group_coverage"
        reason = (
            f"{dist_name} has insufficient group coverage (fit: {fit_cov:.1f}%, comparable IC: {aic_cov:.1f}% "
            f"vs required {min_pct:.0f}%)."
        )
    elif not meets_norm:
        if is_primary:
            status = "provisional_normality_target_not_met"
            reason = (
                f"{dist_name} did not meet the {normality_ratio_threshold:.0%} normality target "
                f"(achieved {ad_ratio:.1%} pass ratio across groups)."
            )
        else:
            status = "ranked_alternative_not_fully_qualified"
            reason = (
                f"Ranked as alternative (#2), but does not independently meet the {normality_ratio_threshold:.0%} "
                f"normality target (achieved {ad_ratio:.1%} pass ratio across groups)."
            )
    else:
        status = "accepted"
        if is_primary:
            reason = f"{dist_name} satisfies both group coverage ({fit_cov:.1f}%) and normality target ({ad_ratio:.1%})."
        else:
            reason = (
                f"Ranked as alternative (#2) and independently satisfies both group coverage ({fit_cov:.1f}%) "
                f"and normality target ({ad_ratio:.1%})."
            )
    return status, reason


def summarize_candidate_diagnostics(
    details: pd.DataFrame,
    *,
    n_groups_requested: int | None = None,
    alpha: float = 0.05,
    delta_aic_threshold: float = 2.0,
    normality_ratio_threshold: float = 0.90,
) -> pd.DataFrame:
    """Aggregate diagnostic metrics across independent fitting groups.

    Computes comprehensive fit success rates, AIC coverage, Delta AIC distribution,
    Shapiro-Wilk rejection frequency, precipitation GoF (KS/AD) rejection frequency,
    and SPI Anderson-Darling normality pass ratio (adapted from Lee et al. 2023).
    """
    required = {"distribution", "group_id"}
    missing = required - set(details.columns)
    if missing:
        raise ValueError(f"details is missing required columns: {sorted(missing)}")

    if n_groups_requested is not None:
        n_groups_total = int(n_groups_requested)
    else:
        n_groups_total = int(details["group_id"].nunique())
    records: list[dict[str, Any]] = []

    labels = details["distribution"].drop_duplicates()
    n_candidates = int(len(labels))

    def _common_groups(
        value_col: str,
        comparable_col: str,
    ) -> set[Any]:
        if n_candidates < 2 or value_col not in details.columns:
            return set()
        values = pd.to_numeric(details[value_col], errors="coerce")
        if comparable_col in details.columns:
            comparable = details[comparable_col].fillna(False).astype(bool)
        else:
            comparable = pd.Series(True, index=details.index, dtype=bool)
        valid_rows = details.loc[comparable & np.isfinite(values), ["group_id", "distribution"]]
        counts = valid_rows.groupby("group_id")["distribution"].nunique()
        return set(counts.index[counts == n_candidates])

    common_aic_groups = _common_groups("AIC", "aic_comparable")
    common_aicc_groups = _common_groups("AICc", "aicc_comparable")

    for label, group in details.groupby("distribution", dropna=False):
        n_params = int(pd.to_numeric(group["n_parameters"], errors="coerce").dropna().iloc[0]) if "n_parameters" in group.columns and not group["n_parameters"].dropna().empty else 2

        # Fit coverage
        fit_status_col = group.get("fit_status", pd.Series(dtype=object))
        n_fit_success = int(np.sum(fit_status_col == "success"))
        n_fit_failed = int(len(group) - n_fit_success)
        fit_coverage_pct = float(100.0 * n_fit_success / n_groups_total) if n_groups_total > 0 else 0.0

        # Non-evaluable & evaluable fit coverage
        non_evaluable_count = int(np.sum(fit_status_col.isin(["not_evaluable", "insufficient_positive_sample", "insufficient_effective_sample"])))
        n_evaluable = max(0, int(len(group) - non_evaluable_count))
        evaluable_fit_coverage_pct = float(100.0 * n_fit_success / n_evaluable) if n_evaluable > 0 else 0.0

        # AIC coverage (valid and comparable)
        aic_vals = pd.to_numeric(group.get("AIC", pd.Series(dtype=float)), errors="coerce")
        aic_valid = aic_vals[np.isfinite(aic_vals)]
        n_aic_valid = int(aic_valid.size)
        aic_coverage_pct = float(100.0 * n_aic_valid / n_groups_total) if n_groups_total > 0 else 0.0

        aic_comp_col = (
            group["aic_comparable"].fillna(False).astype(bool)
            if "aic_comparable" in group.columns
            else pd.Series(True, index=group.index, dtype=bool)
        )
        n_aic_comparable = int(np.sum(aic_comp_col & np.isfinite(aic_vals)))
        aic_comparable_coverage_pct = float(100.0 * n_aic_comparable / n_groups_total) if n_groups_total > 0 else 0.0

        # Delta AIC metrics
        delta_vals = pd.to_numeric(group.get("delta_AIC", pd.Series(dtype=float)), errors="coerce")
        delta_valid = delta_vals[np.isfinite(delta_vals)]
        mean_delta = float(delta_valid.mean()) if delta_valid.size else np.nan
        median_delta = float(delta_valid.median()) if delta_valid.size else np.nan
        aic_comp_pct = (
            float(100.0 * np.sum(delta_valid < delta_aic_threshold) / delta_valid.size)
            if delta_valid.size else np.nan
        )
        aic_win_count = int(np.sum(np.isclose(delta_valid, 0.0, atol=1e-8))) if delta_valid.size else 0
        aic_win_rate_pct = (
            float(100.0 * aic_win_count / delta_valid.size)
            if delta_valid.size
            else np.nan
        )
        common_aic_mask = group["group_id"].isin(common_aic_groups)
        common_delta_aic = delta_vals[common_aic_mask & np.isfinite(delta_vals)]

        # AICc is a separate criterion and is never backfilled from AIC.
        aicc_vals = pd.to_numeric(
            group.get("AICc", pd.Series(np.nan, index=group.index, dtype=float)),
            errors="coerce",
        )
        aicc_valid = aicc_vals[np.isfinite(aicc_vals)]
        aicc_comp_col = (
            group["aicc_comparable"].fillna(False).astype(bool)
            if "aicc_comparable" in group.columns
            else pd.Series(False, index=group.index, dtype=bool)
        )
        n_aicc_comparable = int(np.sum(aicc_comp_col & np.isfinite(aicc_vals)))
        aicc_comparable_coverage_pct = (
            float(100.0 * n_aicc_comparable / n_groups_total)
            if n_groups_total > 0
            else 0.0
        )
        delta_aicc_vals = pd.to_numeric(
            group.get("delta_AICc", pd.Series(np.nan, index=group.index, dtype=float)),
            errors="coerce",
        )
        delta_aicc_valid = delta_aicc_vals[np.isfinite(delta_aicc_vals)]
        common_aicc_mask = group["group_id"].isin(common_aicc_groups)
        common_delta_aicc = delta_aicc_vals[
            common_aicc_mask & np.isfinite(delta_aicc_vals)
        ]
        aicc_win_count = int(
            np.sum(np.isclose(delta_aicc_valid, 0.0, atol=1e-8))
        )

        # Shapiro-Wilk diagnostics
        sw_p = pd.to_numeric(group.get("SW_pvalue", pd.Series(dtype=float)), errors="coerce")
        sw_p = sw_p[np.isfinite(sw_p)]
        n_sw_tested = int(sw_p.size)
        n_sw_rejected = int(np.sum(sw_p < alpha))
        sw_rej_pct = float(100.0 * n_sw_rejected / n_sw_tested) if n_sw_tested else np.nan
        sw_nonrej_ratio = float(1.0 - sw_rej_pct / 100.0) if np.isfinite(sw_rej_pct) else np.nan

        # KS and AD GoF on positive precipitation component
        ks_p = pd.to_numeric(group.get("KS_pvalue", pd.Series(dtype=float)), errors="coerce")
        ks_p = ks_p[np.isfinite(ks_p)]
        n_ks_tested = int(ks_p.size)
        ks_rej_pct = float(100.0 * np.sum(ks_p < alpha) / n_ks_tested) if n_ks_tested else np.nan

        ad_p = pd.to_numeric(group.get("AD_pvalue", pd.Series(dtype=float)), errors="coerce")
        ad_p = ad_p[np.isfinite(ad_p)]
        n_ad_tested = int(ad_p.size)
        ad_rej_pct = float(100.0 * np.sum(ad_p < alpha) / n_ad_tested) if n_ad_tested else np.nan

        # SPI Anderson-Darling normality test (Lee et al. adaptation across calendar groups)
        spi_ad_pass_col = group.get("SPI_AD_pass", pd.Series(dtype=object))
        valid_spi_ad = spi_ad_pass_col.dropna()
        n_spi_ad_tested = int(valid_spi_ad.size)
        n_spi_ad_pass = int(np.sum(valid_spi_ad.astype(bool)))
        spi_ad_pass_ratio = float(n_spi_ad_pass / n_spi_ad_tested) if n_spi_ad_tested else np.nan
        if n_spi_ad_tested > 0:
            meets_target = bool(np.isfinite(spi_ad_pass_ratio) and spi_ad_pass_ratio >= normality_ratio_threshold)
        elif n_sw_tested > 0:
            meets_target = bool(np.isfinite(sw_nonrej_ratio) and sw_nonrej_ratio >= normality_ratio_threshold)
        else:
            meets_target = False

        record: dict[str, Any] = {
            "distribution": label,
            "n_parameters": n_params,
            "n_groups_requested": n_groups_total,
            "n_groups_total": n_groups_total,
            "n_total_groups": n_groups_total,
            "n_groups_evaluable": n_evaluable,
            "n_fit_success": n_fit_success,
            "n_fit_failed": n_fit_failed,
            "n_converged": int(group.get("converged", pd.Series(False, index=group.index)).fillna(False).astype(bool).sum()),
            "fit_method_counts": group.get("fit_method", pd.Series("unknown", index=group.index)).fillna("unknown").value_counts().to_dict(),
            "fit_coverage_pct": fit_coverage_pct,
            "evaluable_fit_coverage_pct": evaluable_fit_coverage_pct,
            "n_AIC_valid": n_aic_valid,
            "AIC_coverage_pct": aic_coverage_pct,
            "n_AIC_comparable": n_aic_comparable,
            "n_comparable_groups": n_aic_comparable,
            "AIC_comparable_coverage_pct": aic_comparable_coverage_pct,
            "aic_incomparable_reason_counts": group.get("aic_incomparable_reason", pd.Series("unknown", index=group.index)).fillna("unknown").value_counts().to_dict(),
            "n_AICc_valid": int(aicc_valid.size),
            "AICc_coverage_pct": float(100.0 * aicc_valid.size / n_groups_total) if n_groups_total > 0 else 0.0,
            "n_AICc_comparable": n_aicc_comparable,
            "AICc_comparable_coverage_pct": aicc_comparable_coverage_pct,
            "n_SW_tested": n_sw_tested,
            "n_SW_rejected": n_sw_rejected,
            "SW_rejection_frequency_pct": sw_rej_pct,
            "SW_nonrejection_ratio": sw_nonrej_ratio,
            "mean_delta_AIC": mean_delta,
            "median_delta_AIC": median_delta,
            "n_delta_AIC": int(delta_valid.size),
            "mean_delta_AIC_denominator": int(delta_valid.size),
            "n_common_AIC_groups": int(len(common_aic_groups)),
            "mean_delta_AIC_common": float(common_delta_aic.mean()) if common_delta_aic.size else np.nan,
            "median_delta_AIC_common": float(common_delta_aic.median()) if common_delta_aic.size else np.nan,
            "mean_delta_AICc": float(delta_aicc_valid.mean()) if delta_aicc_valid.size else np.nan,
            "median_delta_AICc": float(delta_aicc_valid.median()) if delta_aicc_valid.size else np.nan,
            "n_delta_AICc": int(delta_aicc_valid.size),
            "mean_delta_AICc_denominator": int(delta_aicc_valid.size),
            "n_common_AICc_groups": int(len(common_aicc_groups)),
            "mean_delta_AICc_common": float(common_delta_aicc.mean()) if common_delta_aicc.size else np.nan,
            "median_delta_AICc_common": float(common_delta_aicc.median()) if common_delta_aicc.size else np.nan,
            "aic_competitive_pct": aic_comp_pct,
            "aic_win_rate_pct": aic_win_rate_pct,
            "aic_win_count": aic_win_count,
            "aic_win_rate_denominator": int(delta_valid.size),
            "aicc_win_count": aicc_win_count,
            "aicc_win_rate_pct": float(100.0 * aicc_win_count / delta_aicc_valid.size) if delta_aicc_valid.size else np.nan,
            "aicc_win_rate_denominator": int(delta_aicc_valid.size),
            "n_finite_spi": int(pd.to_numeric(group.get("n_finite_spi", 0), errors="coerce").fillna(0).sum()) if "n_finite_spi" in group.columns else 0,
            "n_nan_spi": int(pd.to_numeric(group.get("n_nan_spi", 0), errors="coerce").fillna(0).sum()) if "n_nan_spi" in group.columns else 0,
            "spi_failure_reason_counts": group.get("spi_failure_reason", pd.Series("unknown", index=group.index)).fillna("unknown").value_counts().to_dict(),
            "optimization_seconds": float(pd.to_numeric(group["optimization_seconds"], errors="coerce").fillna(0).sum()) if "optimization_seconds" in group.columns else np.nan,
            "initialization_seconds": float(pd.to_numeric(group["initialization_seconds"], errors="coerce").fillna(0).sum()) if "initialization_seconds" in group.columns else np.nan,
            "scipy_initialization_seconds": float(pd.to_numeric(group["scipy_initialization_seconds"], errors="coerce").fillna(0).sum()) if "scipy_initialization_seconds" in group.columns else np.nan,
            "n_KS_tested": n_ks_tested,
            "KS_rejection_frequency_pct": ks_rej_pct,
            "n_AD_tested": n_ad_tested,
            "AD_rejection_frequency_pct": ad_rej_pct,
            "n_SPI_AD_tested": n_spi_ad_tested,
            "SPI_AD_pass_count": n_spi_ad_pass,
            "SPI_AD_group_pass_ratio": spi_ad_pass_ratio,
            "meets_90pct_normality_target": meets_target,
        }
        records.append(record)

    summary_df = pd.DataFrame.from_records(records)
    return summary_df.sort_values(
        ["mean_delta_AIC", "SW_rejection_frequency_pct"], na_position="last"
    ).reset_index(drop=True)


def rank_aggregated_candidates(
    candidate_summary: pd.DataFrame,
    *,
    min_valid_group_fraction: float = 0.80,
    delta_aic_threshold: float = 2.0,
    normality_ratio_threshold: float = 0.90,
    prefer_two_parameters: bool = True,
    ranking_method: Literal["hierarchical", "consensus_rank"] = "hierarchical",
    consensus_criteria: Sequence[str] | None = None,
    information_criterion: InformationCriterion = "AIC",
) -> dict[str, Any]:
    """Perform global evaluation and ranking of candidates across all groups.

    Parameters
    ----------
    candidate_summary:
        DataFrame output from summarize_candidate_diagnostics.
    min_valid_group_fraction:
        Minimum group coverage required for official ranking (default 0.80 = 80%).
    delta_aic_threshold:
        Threshold for aggregate Delta AIC competitiveness (default 2.0).
    normality_ratio_threshold:
        Normality target ratio (default 0.90 = 90% pass ratio across groups).
    prefer_two_parameters:
        Prioritize 2-parameter distributions among competitive models.
    ranking_method:
        'hierarchical' (default transparent rule-based ranking) or 'consensus_rank'.
    consensus_criteria:
        Optional sequence of mandatory criteria column names for consensus ranking
        (e.g., ['mean_delta_AIC', 'SW_rejection_frequency_pct', 'SPI_AD_group_pass_ratio']).
        Defaults to active criteria available in candidate_summary.
    """
    if candidate_summary.empty:
        raise ValueError("candidate_summary is empty.")
    if information_criterion not in {"AIC", "AICc"}:
        raise ValueError("information_criterion must be 'AIC' or 'AICc'.")

    df = candidate_summary.copy()
    min_pct = min_valid_group_fraction * 100.0
    comparable_coverage_col = f"{information_criterion}_comparable_coverage_pct"
    if comparable_coverage_col not in df.columns:
        if information_criterion == "AIC" and "AIC_coverage_pct" in df.columns:
            # Compatibility for summaries created before comparability metadata
            # existed. New summaries always provide the explicit column.
            df[comparable_coverage_col] = df["AIC_coverage_pct"]
        else:
            df[comparable_coverage_col] = 0.0
    df["IC_comparable_coverage_pct"] = df[comparable_coverage_col]

    mean_delta_col = f"mean_delta_{information_criterion}"
    common_delta_col = f"mean_delta_{information_criterion}_common"
    common_count_col = f"n_common_{information_criterion}_groups"
    common_fraction = 0.0
    if common_count_col in df.columns and "n_total_groups" in df.columns and not df.empty:
        total = float(pd.to_numeric(df["n_total_groups"], errors="coerce").max())
        common_n = float(pd.to_numeric(df[common_count_col], errors="coerce").max())
        common_fraction = common_n / total if total > 0 else 0.0
    use_common_population = bool(
        common_delta_col in df.columns
        and df[common_delta_col].notna().sum() >= 2
        and common_fraction >= min_valid_group_fraction
    )
    ranking_delta_col = common_delta_col if use_common_population else mean_delta_col
    if ranking_delta_col not in df.columns:
        df[ranking_delta_col] = np.nan
    df["mean_delta_IC"] = pd.to_numeric(df[ranking_delta_col], errors="coerce")
    df["ranking_delta_metric"] = ranking_delta_col
    comparison_population_status = (
        "common_complete_case"
        if use_common_population
        else "candidate_specific_sensitivity_common_coverage_insufficient"
    )

    eligible_mask = (
        (df["fit_coverage_pct"] >= min_pct)
        & (df[comparable_coverage_col] >= min_pct)
    )
    eligible = df.loc[eligible_mask].copy()

    coverage_ok = True
    if eligible.empty:
        coverage_ok = False
        n_comp_col = f"n_{information_criterion}_comparable"
        if n_comp_col not in df.columns and information_criterion == "AIC":
            n_comp_col = "n_AIC_valid"
        n_comp_values = (
            pd.to_numeric(df[n_comp_col], errors="coerce")
            if n_comp_col in df.columns
            else pd.Series(0, index=df.index, dtype=float)
        )
        eligible = df.loc[n_comp_values > 0].copy()
        if eligible.empty:
            eligible = df.copy()

    any_meets_normality = bool(
        (eligible["meets_90pct_normality_target"] == True).any()
    )

    if ranking_method == "hierarchical":
        tier_list = []
        for _, row in eligible.iterrows():
            meets_norm = bool(row["meets_90pct_normality_target"])
            mean_d = float(row["mean_delta_IC"]) if np.isfinite(row["mean_delta_IC"]) else 999.0
            is_comp = mean_d < delta_aic_threshold
            n_p = int(row["n_parameters"])

            comp_rank = 0 if is_comp else 1
            param_rank = 0 if (prefer_two_parameters and is_comp and n_p == 2) else 1
            normality_rank = 0 if meets_norm else 1
            sw_score = -float(row["SW_nonrejection_ratio"]) if np.isfinite(row["SW_nonrejection_ratio"]) else 0.0
            ad_score = -float(row["SPI_AD_group_pass_ratio"]) if np.isfinite(row["SPI_AD_group_pass_ratio"]) else 0.0

            tier_list.append((
                comp_rank,
                param_rank,
                mean_d,
                normality_rank,
                sw_score,
                ad_score,
                str(row["distribution"]),
            ))

        sorted_indices = sorted(range(len(eligible)), key=lambda i: tier_list[i])
        ranked_df = eligible.iloc[sorted_indices].reset_index(drop=True)
        ranked_df.insert(0, "global_rank", np.arange(1, len(ranked_df) + 1))

        best_label = str(ranked_df.iloc[0]["distribution"])
        alt_label = str(ranked_df.iloc[1]["distribution"]) if len(ranked_df) >= 2 else None

        best_row = ranked_df.iloc[0]
        best_status, best_reason = _evaluate_candidate_status(
            best_row,
            min_valid_group_fraction=min_valid_group_fraction,
            normality_ratio_threshold=normality_ratio_threshold,
            is_primary=True,
        )
        if alt_label is not None:
            alt_row = ranked_df.iloc[1]
            alt_status, alt_reason = _evaluate_candidate_status(
                alt_row,
                min_valid_group_fraction=min_valid_group_fraction,
                normality_ratio_threshold=normality_ratio_threshold,
                is_primary=False,
            )
        else:
            alt_status = "no_alternative_available"
            alt_reason = "No eligible second candidate available."

        reason = f"Ranked #1 via hierarchical criteria. {best_reason}"

    else:  # consensus_rank (Borda count across criteria)
        df_eval = eligible.copy()

        # Determine configured consensus criteria:
        if consensus_criteria is not None:
            active_criteria = list(consensus_criteria)
        else:
            # Default active criteria based on configured and tested diagnostics:
            # - mean_delta_AIC is always mandatory for official observational AIC ranking
            # - SW_rejection_frequency_pct is mandatory if Shapiro-Wilk diagnostics were tested
            # - SPI_AD_group_pass_ratio is mandatory if SPI Anderson-Darling tests were tested
            active_criteria = ["mean_delta_IC"]
            if (
                "SW_rejection_frequency_pct" in df_eval.columns
                and bool(df_eval["SW_rejection_frequency_pct"].notna().any())
            ):
                active_criteria.append("SW_rejection_frequency_pct")
            if (
                "SPI_AD_group_pass_ratio" in df_eval.columns
                and bool(df_eval["SPI_AD_group_pass_ratio"].notna().any())
            ):
                active_criteria.append("SPI_AD_group_pass_ratio")

        # Multi-criteria consensus ranking requires at least 2 active criteria (e.g. AIC and at least one normality metric)
        if len(active_criteria) < 2 or not any(
            c in active_criteria for c in ("mean_delta_IC", "mean_delta_AIC", "mean_delta_AICc")
        ):
            has_sufficient_criteria = False
        else:
            has_sufficient_criteria = True

        def _check_consensus_eligibility(row: pd.Series) -> tuple[bool, str]:
            if not has_sufficient_criteria:
                return False, "provisional_diagnostics_unavailable"
            missing_reasons = []
            for crit in active_criteria:
                val = row.get(crit, np.nan)
                if not np.isfinite(val):
                    if crit in ("mean_delta_IC", "mean_delta_AIC", "mean_delta_AICc"):
                        missing_reasons.append("missing_mean_delta_aic")
                    elif crit == "SW_rejection_frequency_pct":
                        missing_reasons.append("missing_sw_metric")
                    elif crit == "SPI_AD_group_pass_ratio":
                        missing_reasons.append("missing_spi_ad_metric")
                    else:
                        missing_reasons.append(f"missing_{crit}")
            if len(missing_reasons) > 1:
                return False, "missing_required_consensus_metrics"
            elif len(missing_reasons) == 1:
                return False, missing_reasons[0]
            return True, "none"

        elig_results = [_check_consensus_eligibility(r) for _, r in df_eval.iterrows()]
        df_eval["consensus_eligible"] = [res[0] for res in elig_results]
        df_eval["consensus_ineligible_reason"] = [res[1] for res in elig_results]

        complete_mask = df_eval["consensus_eligible"].astype(bool)
        pool = df_eval.loc[complete_mask].copy()
        incomplete = df_eval.loc[~complete_mask].copy()

        if pool.empty:
            if not incomplete.empty:
                incomplete["rank_aic"] = np.nan
                incomplete["rank_sw"] = np.nan
                incomplete["rank_ad"] = np.nan
                incomplete["consensus_score"] = np.nan
                incomplete.insert(0, "global_rank", np.nan)
                ranked_df = incomplete.sort_values(
                    ["mean_delta_IC", "distribution"], na_position="last", kind="mergesort"
                ).reset_index(drop=True)
            else:
                ranked_df = df_eval.copy()
                ranked_df["rank_aic"] = np.nan
                ranked_df["rank_sw"] = np.nan
                ranked_df["rank_ad"] = np.nan
                ranked_df["consensus_score"] = np.nan
                ranked_df.insert(0, "global_rank", np.nan)

            best_label = None
            alt_label = None
            best_status = "provisional_insufficient_consensus_metrics"
            alt_status = "no_alternative_available"
            crit_names = ", ".join(active_criteria)
            reason = f"No candidate has complete mandatory consensus metrics ({crit_names})."
        else:
            # Score strictly within the common pool of complete candidates
            component_ranks = []
            ic_rank_col = next(
                (
                    c
                    for c in ("mean_delta_IC", "mean_delta_AIC", "mean_delta_AICc")
                    if c in active_criteria
                ),
                None,
            )
            if ic_rank_col is not None:
                pool["rank_aic"] = pool[ic_rank_col].rank(ascending=True, method="average")
                component_ranks.append(pool["rank_aic"])
            else:
                pool["rank_aic"] = np.nan

            if "SW_rejection_frequency_pct" in active_criteria:
                pool["rank_sw"] = pool["SW_rejection_frequency_pct"].rank(ascending=True, method="average")
                component_ranks.append(pool["rank_sw"])
            else:
                pool["rank_sw"] = np.nan

            if "SPI_AD_group_pass_ratio" in active_criteria:
                pool["rank_ad"] = pool["SPI_AD_group_pass_ratio"].rank(ascending=False, method="average")
                component_ranks.append(pool["rank_ad"])
            else:
                pool["rank_ad"] = np.nan

            pool["consensus_score"] = sum(component_ranks) / float(len(component_ranks))

            sorted_pool = pool.sort_values(
                ["consensus_score", "mean_delta_IC", "distribution"],
                ascending=[True, True, True],
                kind="mergesort",
            ).reset_index(drop=True)
            sorted_pool.insert(0, "global_rank", np.arange(1, len(sorted_pool) + 1))

            if not incomplete.empty:
                incomplete["rank_aic"] = np.nan
                incomplete["rank_sw"] = np.nan
                incomplete["rank_ad"] = np.nan
                incomplete["consensus_score"] = np.nan
                incomplete.insert(0, "global_rank", np.nan)
                ranked_df = pd.concat([sorted_pool, incomplete], ignore_index=True)
            else:
                ranked_df = sorted_pool

            best_row = sorted_pool.iloc[0]
            best_label = str(best_row["distribution"])
            alt_label = str(sorted_pool.iloc[1]["distribution"]) if len(sorted_pool) >= 2 else None

            best_status, best_reason = _evaluate_candidate_status(
                best_row,
                min_valid_group_fraction=min_valid_group_fraction,
                normality_ratio_threshold=normality_ratio_threshold,
                is_primary=True,
            )
            if best_status == "accepted":
                best_status = "consensus_rank_user_option"

            if alt_label is not None:
                alt_row = sorted_pool.iloc[1]
                alt_status, alt_reason = _evaluate_candidate_status(
                    alt_row,
                    min_valid_group_fraction=min_valid_group_fraction,
                    normality_ratio_threshold=normality_ratio_threshold,
                    is_primary=False,
                )
                if alt_status == "accepted":
                    alt_status = "consensus_rank_user_option"
            else:
                alt_status = "no_alternative_available"
                alt_reason = "No eligible second candidate available."

            c_score_val = float(best_row["consensus_score"]) if np.isfinite(best_row.get("consensus_score", np.nan)) else np.nan
            c_score_str = f"{c_score_val:.2f}" if np.isfinite(c_score_val) else "N/A"
            criteria_str = ", ".join([c for c in ["rank_aic", "rank_sw", "rank_ad"] if pool[c].notna().any()])
            reason = f"Ranked #1 using complementary consensus / Borda score ({c_score_str}) across {criteria_str}. {best_reason}"

    if best_label is not None and best_status in {
        "accepted",
        "consensus_rank_user_option",
    }:
        best_ranked = ranked_df.loc[ranked_df["distribution"] == best_label]
        best_mean_delta = (
            float(best_ranked.iloc[0]["mean_delta_IC"])
            if not best_ranked.empty
            and np.isfinite(best_ranked.iloc[0].get("mean_delta_IC", np.nan))
            else np.nan
        )
        if not np.isfinite(best_mean_delta):
            best_status = "provisional_insufficient_comparison"
            reason += " Aggregate mean Delta IC is unavailable."
        elif best_mean_delta >= delta_aic_threshold:
            best_status = "provisional_no_aggregate_competitive_candidate"
            reason += (
                f" No candidate has aggregate mean Delta IC below "
                f"{delta_aic_threshold:g}."
            )
        elif (
            len(eligible) >= 2
            and comparison_population_status != "common_complete_case"
        ):
            best_status = "provisional_common_comparison_coverage_insufficient"
            reason += (
                " Common complete-case coverage is below the configured "
                "threshold; candidate-specific results are sensitivity summaries."
            )

    # Aggregate wall-clock totals are retained in ``candidate_summary`` for
    # performance auditing.  Ranking outputs intentionally omit them so a
    # fixed seed produces byte-for-byte stable decision table.
    ranked_df = ranked_df.drop(
        columns=[
            "optimization_seconds",
            "initialization_seconds",
            "scipy_initialization_seconds",
        ],
        errors="ignore",
    )

    return {
        "global_ranking": ranked_df,
        "best_distribution": best_label,
        "alternative_distribution": alt_label,
        "best_selection_status": best_status,
        "alternative_selection_status": alt_status,
        "normality_target_met_by_any_candidate": any_meets_normality,
        "selection_reason": reason,
        "information_criterion": information_criterion,
        "comparison_population_status": comparison_population_status,
        "common_comparison_fraction": common_fraction,
        "ranking_delta_metric": ranking_delta_col,
    }


def select_models_by_group(
    groups: Mapping[Any, pd.Series | tuple[pd.Series, pd.Series] | Sequence[float] | np.ndarray],
    candidates: Mapping[str, Any] | Sequence[Any] | None = None,
    *,
    prob_zero: bool = True,
    alpha: float = 0.05,
    delta_aic_threshold: float = 2.0,
    prefer_two_parameters: bool = True,
    n_boot: int = 199,
    gof_scope: GofScope = "competitive",
    min_bootstrap_success: float = 0.80,
    random_state: int | None = 42,
    sw_clip: tuple[float, float] | None = None,
    fitting_policy: Literal["standard", "wang"] = "standard",
    small_sample_policy: Literal["strict", "augmented", "pseudo_observation_experimental"] = "strict",
    all_zero_policy: Literal["stagge", "wang"] = "stagge",
    min_valid_group_fraction: float = 0.80,
    normality_ratio_threshold: float = 0.90,
    ranking_method: Literal["hierarchical", "consensus_rank"] = "hierarchical",
    consensus_criteria: Sequence[str] | None = None,
    information_criterion: InformationCriterion = "AIC",
) -> dict[str, Any]:
    """Run automatic selection for independent fitting groups and compute global rankings.

    Computes both 'hierarchical' and 'consensus_rank' global distribution rankings
    from the single underlying group-level evaluation.

    Parameters
    ----------
    groups:
        Mapping of ``{group_id: rainfall_series}`` or ``{group_id: (target_series, window_series)}``.
    candidates:
        Mapping of candidate distributions.
    prob_zero:
        Enable zero-mass handling.
    alpha:
        Significance level for hypothesis tests.
    delta_aic_threshold:
        Threshold for competitive Delta AIC set.
    prefer_two_parameters:
        Prioritize 2-parameter distributions among competitive models.
    n_boot:
        Number of bootstrap refits for GoF testing.
    gof_scope:
        Bootstrap testing scope ('competitive', 'all', or 'none').
    min_bootstrap_success:
        Minimum fraction of valid bootstrap refits.
    random_state:
        Seed for reproducible evaluation.
    sw_clip:
        Clipping range for Shapiro-Wilk SPI values (default None).
    fitting_policy:
        Distribution fitting policy.
    small_sample_policy:
        Small sample policy.
    min_valid_group_fraction:
        Minimum group coverage required for aggregate ranking.
    normality_ratio_threshold:
        Normality target pass ratio (default 0.90).
    ranking_method:
        Global ranking method ('hierarchical' or 'consensus_rank').
    """
    if not isinstance(groups, Mapping) or not groups:
        raise ValueError("groups must be a non-empty mapping of group_id to data series.")

    all_recommendations: list[dict[str, Any]] = []
    all_details: list[pd.DataFrame] = []
    candidate_map = _normalise_candidates(candidates)

    root = np.random.SeedSequence(random_state)
    group_seeds = root.spawn(len(groups))

    for idx, (group_id, group_input) in enumerate(groups.items()):
        group_seed = _derive_seed(group_seeds[idx])
        if isinstance(group_input, tuple) and len(group_input) == 2:
            data_target, data_window = group_input
        else:
            data_target = group_input
            data_window = None

        try:
            result = select_best_distribution(
                data=data_target,
                data_window=data_window,
                candidates=candidate_map,
                prob_zero=prob_zero,
                alpha=alpha,
                delta_aic_threshold=delta_aic_threshold,
                prefer_two_parameters=prefer_two_parameters,
                n_boot=n_boot,
                gof_scope=gof_scope,
                min_bootstrap_success=min_bootstrap_success,
                random_state=group_seed,
                sw_clip=sw_clip,
                fitting_policy=fitting_policy,
                small_sample_policy=small_sample_policy,
                all_zero_policy=all_zero_policy,
                information_criterion=information_criterion,
            )
            rec = dict(result["recommendation"])
            rec["group_id"] = str(group_id)
            all_recommendations.append(rec)
            detail = result["comparison"].copy()
            detail.insert(0, "group_id", str(group_id))
            all_details.append(detail)
        except Exception as exc:
            logger.warning("Group %r selection failed: %s", group_id, exc)
            status_val = "not_evaluable" if ("required" in str(exc).lower() or "positive" in str(exc).lower()) else "selection_failed"
            all_recommendations.append({
                "group_id": str(group_id),
                "distribution": None,
                "alternative_distribution": None,
                "selection_status": status_val,
                "reason": f"{type(exc).__name__}: {exc}",
            })
            # Preserve group representation in details for coverage accounting
            p_rows = []
            for c_lbl, c_dist in candidate_map.items():
                p_rows.append({
                    "group_id": str(group_id),
                    "distribution": c_lbl,
                    "scipy_distribution": getattr(c_dist, "name", c_lbl),
                    "n_parameters": np.nan,
                    "parameters": None,
                    "loc": np.nan,
                    "scale": np.nan,
                    "p0": np.nan,
                    "fit_status": status_val,
                    "fit_method": "none",
                    "converged": False,
                    "pseudo_obs_added": False,
                    "small_sample_warning": False,
                    "AIC": np.nan,
                    "AICc": np.nan,
                    "loglik": np.nan,
                    "loglik_positive_conditional": np.nan,
                    "is_mle": False,
                    "aic_comparable": False,
                    "aic_incomparable_reason": status_val,
                    "official_AIC": np.nan,
                    "official_AICc": np.nan,
                    "delta_AIC": np.nan,
                    "delta_AICc": np.nan,
                    "aicc_comparable": False,
                    "aicc_incomparable_reason": status_val,
                    "n_observations_ic": 0,
                    "n_comparable_candidates": 0,
                    "n_AICc_comparable_candidates": 0,
                    "AIC_comparison_status": "insufficient_comparable_candidates",
                    "AICc_comparison_status": "insufficient_comparable_candidates",
                    "n_positive": 0,
                    "n_fitting": 0,
                    "AIC_competitive": False,
                    "AICc_competitive": False,
                    "information_criterion": information_criterion,
                    "criterion_value": np.nan,
                    "delta_IC": np.nan,
                    "IC_competitive": False,
                    "ic_comparable": False,
                    "KS_statistic": np.nan,
                    "KS_pvalue": np.nan,
                    "AD_statistic": np.nan,
                    "AD_pvalue": np.nan,
                    "n_test": 0,
                    "n_boot_requested": 0,
                    "n_boot_valid": 0,
                    "bootstrap_success_rate": np.nan,
                    "gof_tested": False,
                    "gof_usable": False,
                    "gof_pass": None,
                    "SW_statistic": np.nan,
                    "SW_pvalue": np.nan,
                    "SW_reject_normality": None,
                    "SW_spi_mean": np.nan,
                    "SW_spi_std": np.nan,
                    "SW_n_replaced_zero": 0,
                    "SPI_AD_statistic": np.nan,
                    "SPI_AD_critical_value": np.nan,
                    "SPI_AD_pass": None,
                    "SPI_AD_tested": False,
                    "n_finite_spi": 0,
                    "n_nan_spi": 0,
                    "spi_status": "failed",
                    "spi_failure_reason": status_val,
                    "error": f"{type(exc).__name__}: {exc}",
                })
            all_details.append(pd.DataFrame(p_rows))

    recommendations = pd.DataFrame(all_recommendations)
    details = pd.concat(all_details, ignore_index=True) if all_details else pd.DataFrame()

    if not details.empty:
        candidate_summary = summarize_candidate_diagnostics(
            details,
            n_groups_requested=len(groups),
            alpha=alpha,
            delta_aic_threshold=delta_aic_threshold,
            normality_ratio_threshold=normality_ratio_threshold,
        )
        # Always evaluate both ranking methods from the single evaluation pass
        hier_rank = rank_aggregated_candidates(
            candidate_summary,
            min_valid_group_fraction=min_valid_group_fraction,
            delta_aic_threshold=delta_aic_threshold,
            normality_ratio_threshold=normality_ratio_threshold,
            prefer_two_parameters=prefer_two_parameters,
            ranking_method="hierarchical",
            information_criterion=information_criterion,
        )
        cons_rank = rank_aggregated_candidates(
            candidate_summary,
            min_valid_group_fraction=min_valid_group_fraction,
            delta_aic_threshold=delta_aic_threshold,
            normality_ratio_threshold=normality_ratio_threshold,
            prefer_two_parameters=prefer_two_parameters,
            ranking_method="consensus_rank",
            consensus_criteria=consensus_criteria,
            information_criterion=information_criterion,
        )

        ranking_results = {
            "hierarchical": hier_rank,
            "consensus_rank": cons_rank,
        }

        # Build ranking_comparison table
        hier_df = hier_rank["global_ranking"][["distribution", "global_rank"]].rename(columns={"global_rank": "hierarchical_rank"})
        cons_cols = ["distribution", "global_rank"]
        if "consensus_score" in cons_rank["global_ranking"].columns:
            cons_cols.append("consensus_score")
        cons_df = cons_rank["global_ranking"][cons_cols].rename(columns={"global_rank": "consensus_rank"})

        comparison_df = candidate_summary.merge(hier_df, on="distribution", how="left")
        comparison_df = comparison_df.merge(cons_df, on="distribution", how="left")
        comparison_df["rank_difference"] = comparison_df["consensus_rank"] - comparison_df["hierarchical_rank"]

        comparison_df["hierarchical_selected"] = np.where(
            comparison_df["hierarchical_rank"] == 1,
            "selected_best",
            np.where(comparison_df["hierarchical_rank"] == 2, "selected_alternative", "not_selected")
        )
        comparison_df["consensus_selected"] = np.where(
            comparison_df["consensus_rank"] == 1,
            "selected_best",
            np.where(comparison_df["consensus_rank"] == 2, "selected_alternative", "not_selected")
        )

        hier_status_map = {}
        if hier_rank["best_distribution"] is not None:
            hier_status_map[hier_rank["best_distribution"]] = hier_rank["best_selection_status"]
        if hier_rank["alternative_distribution"] is not None:
            hier_status_map[hier_rank["alternative_distribution"]] = hier_rank["alternative_selection_status"]

        cons_status_map = {}
        if cons_rank["best_distribution"] is not None:
            cons_status_map[cons_rank["best_distribution"]] = cons_rank["best_selection_status"]
        if cons_rank["alternative_distribution"] is not None:
            cons_status_map[cons_rank["alternative_distribution"]] = cons_rank["alternative_selection_status"]

        comparison_df["hierarchical_status"] = comparison_df["distribution"].map(
            lambda d: hier_status_map.get(d, "not_selected")
        )
        comparison_df["consensus_status"] = comparison_df["distribution"].map(
            lambda d: cons_status_map.get(d, "not_selected")
        )

        ordered_cols = [
            "distribution", "hierarchical_rank", "consensus_rank", "rank_difference",
            "n_parameters", "n_groups_requested", "n_groups_evaluable",
            "fit_coverage_pct", "AIC_coverage_pct", "AIC_comparable_coverage_pct",
            "mean_delta_AIC", "SW_nonrejection_ratio", "SPI_AD_group_pass_ratio",
            "consensus_score", "meets_90pct_normality_target",
            "hierarchical_selected", "consensus_selected",
            "hierarchical_status", "consensus_status"
        ]
        # Wall-clock diagnostics belong in ``candidate_summary`` but would make
        # the otherwise seeded ranking-comparison artifact non-deterministic.
        volatile_diagnostic_cols = {
            "optimization_seconds",
            "initialization_seconds",
            "scipy_initialization_seconds",
        }
        actual_cols = [c for c in ordered_cols if c in comparison_df.columns] + [
            c
            for c in comparison_df.columns
            if c not in ordered_cols and c not in volatile_diagnostic_cols
        ]
        ranking_comparison = comparison_df[actual_cols].sort_values("hierarchical_rank", kind="mergesort").reset_index(drop=True)

        same_best = bool(hier_rank["best_distribution"] == cons_rank["best_distribution"])
        same_alt = bool(hier_rank["alternative_distribution"] == cons_rank["alternative_distribution"])
        agreement_summary = {
            "methods_agree_on_best": same_best,
            "methods_agree_on_alternative": same_alt,
            "hierarchical_best": hier_rank["best_distribution"],
            "consensus_best": cons_rank["best_distribution"],
            "hierarchical_alternative": hier_rank["alternative_distribution"],
            "consensus_alternative": cons_rank["alternative_distribution"],
            "hierarchical_best_status": hier_rank["best_selection_status"],
            "consensus_best_status": cons_rank["best_selection_status"],
            "hierarchical_alt_status": hier_rank["alternative_selection_status"],
            "consensus_alt_status": cons_rank["alternative_selection_status"],
            "max_rank_difference": int(np.nanmax(np.abs(ranking_comparison["rank_difference"]))) if not ranking_comparison.empty and ranking_comparison["rank_difference"].notna().any() else 0,
            "disagreement_notes": None if (same_best and same_alt) else (
                f"Disagreement observed: Hierarchical chose #1={hier_rank['best_distribution']} (#2={hier_rank['alternative_distribution']}); "
                f"Consensus chose #1={cons_rank['best_distribution']} (#2={cons_rank['alternative_distribution']})."
            ),
        }

        primary = cons_rank if ranking_method == "consensus_rank" else hier_rank
        global_ranking = primary["global_ranking"]
        best_dist = primary["best_distribution"]
        alt_dist = primary["alternative_distribution"]
        best_status = primary["best_selection_status"]
        alt_status = primary["alternative_selection_status"]
        normality_met = primary["normality_target_met_by_any_candidate"]
        reason = primary["selection_reason"]
    else:
        candidate_summary = pd.DataFrame()
        global_ranking = pd.DataFrame()
        best_dist = None
        alt_dist = None
        best_status = "no_valid_groups"
        alt_status = None
        normality_met = False
        reason = "No groups could be evaluated."
        ranking_results = {
            "hierarchical": {
                "global_ranking": pd.DataFrame(),
                "best_distribution": None,
                "alternative_distribution": None,
                "best_selection_status": "no_valid_groups",
                "alternative_selection_status": None,
                "normality_target_met_by_any_candidate": False,
                "selection_reason": reason,
            },
            "consensus_rank": {
                "global_ranking": pd.DataFrame(),
                "best_distribution": None,
                "alternative_distribution": None,
                "best_selection_status": "no_valid_groups",
                "alternative_selection_status": None,
                "normality_target_met_by_any_candidate": False,
                "selection_reason": reason,
            },
        }
        ranking_comparison = pd.DataFrame()
        agreement_summary = {
            "methods_agree_on_best": True,
            "methods_agree_on_alternative": True,
            "hierarchical_best": None,
            "consensus_best": None,
            "hierarchical_alternative": None,
            "consensus_alternative": None,
            "hierarchical_best_status": "no_valid_groups",
            "consensus_best_status": "no_valid_groups",
            "hierarchical_alt_status": None,
            "consensus_alt_status": None,
            "max_rank_difference": 0,
            "disagreement_notes": None,
        }

    return {
        "recommendations": recommendations,
        "details": details,
        "candidate_summary": candidate_summary,
        "global_ranking": global_ranking,
        "best_distribution": best_dist,
        "alternative_distribution": alt_dist,
        "best_selection_status": best_status,
        "selection_status": best_status,
        "alternative_selection_status": alt_status,
        "normality_target_met_by_any_candidate": normality_met,
        "selection_reason": reason,
        "ranking_method": ranking_method,
        "ranking_results": ranking_results,
        "ranking_comparison": ranking_comparison,
        "agreement_summary": agreement_summary,
        "information_criterion": information_criterion,
    }


def save_selection_outputs(
    result: Mapping[str, Any],
    output_prefix: str,
) -> dict[str, str]:
    """Save a single-group or batch selection result to CSV files."""
    from pathlib import Path

    prefix = Path(output_prefix)
    prefix.parent.mkdir(parents=True, exist_ok=True)
    saved: dict[str, str] = {}

    if "comparison" in result:
        p = str(prefix) + "_comparison.csv"
        result["comparison"].to_csv(p, index=False)
        saved["comparison"] = p
        rec = pd.DataFrame([dict(result["recommendation"])])
        p_rec = str(prefix) + "_recommendation.csv"
        rec.to_csv(p_rec, index=False)
        saved["recommendation"] = p_rec
    elif "details" in result and "recommendations" in result:
        for key in ("recommendations", "details", "candidate_summary", "global_ranking"):
            frame = result.get(key)
            if isinstance(frame, pd.DataFrame) and not frame.empty:
                p = str(prefix) + f"_{key}.csv"
                frame.to_csv(p, index=False)
                saved[key] = p
        # Dual ranking exports
        if "ranking_results" in result and isinstance(result["ranking_results"], dict):
            for method_name, method_res in result["ranking_results"].items():
                m_frame = method_res.get("global_ranking")
                if isinstance(m_frame, pd.DataFrame) and not m_frame.empty:
                    p_m = str(prefix) + f"_global_ranking_{method_name}.csv"
                    m_frame.to_csv(p_m, index=False)
                    saved[f"global_ranking_{method_name}"] = p_m
        if "ranking_comparison" in result:
            comp_df = result.get("ranking_comparison")
            if isinstance(comp_df, pd.DataFrame) and not comp_df.empty:
                p_comp = str(prefix) + "_ranking_comparison.csv"
                comp_df.to_csv(p_comp, index=False)
                saved["ranking_comparison"] = p_comp
    else:
        raise ValueError("Unrecognized result; expected single-group or batch selection output.")
    return saved


if __name__ == "__main__":
    rng = np.random.default_rng(2026)
    example_rain = pd.Series(stats.gamma.rvs(a=2.4, scale=18.0, size=35, random_state=rng))
    example_rain.iloc[[2, 7, 18, 26]] = 0.0

    result = select_best_distribution(
        example_rain,
        prob_zero=True,
        n_boot=49,
        gof_scope="competitive",
        random_state=2026,
    )
    print("Recommendation:")
    print(result["recommendation"])
    print("\nCandidate comparison:")
    print(result["comparison"].to_string(index=False))
