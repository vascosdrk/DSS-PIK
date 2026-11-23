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
    from .dist import Dist
except ImportError:
    try:
        from spei.dist import Dist
    except ImportError:
        from dist import Dist  # type: ignore[no-redef]

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
    n_shape = len(model.pars) if model.pars is not None else 0
    n_scale = 1
    n_location = 0 if name in FIXED_ZERO_LOCATION else 1
    return int(n_shape + n_scale + n_location)


def _conditional_aic(
    model: Dist,
    raw_data: pd.Series,
    *,
    prob_zero: bool,
) -> tuple[float, float, int, float]:
    """Calculate AIC from the fitted positive-precipitation likelihood.

    For candidate distributions with support below zero (e.g. Gumbel or
    Pearson-III), normalize the fitted density conditional on X > 0.
    AIC_positive = -2 * loglik_positive_conditional + 2 * k.

    Returns (AIC, log_likelihood, parameter_count, log_likelihood_positive).
    """
    cal_data = model.data_window if getattr(model, "data_window", None) is not None else raw_data
    values = np.asarray(pd.Series(cal_data).dropna(), dtype=float)
    values = values[np.isfinite(values)]
    zeros = values == 0.0
    positive = values > 0.0
    x = values[positive]
    n_zero = int(np.sum(zeros))
    n_pos = int(x.size)
    k = _parameter_count(model)

    if n_pos < 3 or not np.isfinite(model.loc) or not np.isfinite(model.scale) or model.scale <= 0:
        return np.nan, np.nan, k, np.nan

    args = _model_args(model)
    try:
        log_pdf = np.asarray(model.dist.logpdf(x, *args), dtype=float)
        f0 = float(model.dist.cdf(0.0, *args))
        survival0 = 1.0 - f0
        if not np.isfinite(survival0) or survival0 <= 0.0:
            return np.nan, np.nan, k, np.nan

        log_cond_pdf = log_pdf - np.log(survival0)
        if not np.all(np.isfinite(log_cond_pdf)):
            return np.nan, np.nan, k, np.nan

        loglik_positive = float(np.sum(log_cond_pdf))
        aic = float(-2.0 * loglik_positive + 2.0 * k)
        return aic, loglik_positive, k, loglik_positive
    except (ValueError, FloatingPointError, OverflowError, TypeError):
        return np.nan, np.nan, k, np.nan


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
    valid_mask = np.isfinite(q)
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
) -> pd.DataFrame:
    """Rank eligible candidates deterministically by parameter count and AIC.

    Receives only candidates that satisfy eligibility requirements (finite AIC,
    valid parameters, and passing GoF where required). Applies the two-parameter
    preference strictly among eligible candidates, ordering two-parameter models
    first (by AIC ascending, then distribution name ascending for tie-breaks),
    followed by three-parameter models (similarly ordered).
    """
    valid = rows.loc[np.isfinite(rows["AIC"].to_numpy(dtype=float))].copy()
    if valid.empty:
        return pd.DataFrame()

    if prefer_two_parameters:
        two_param = valid.loc[valid["n_parameters"] == 2].sort_values(
            ["AIC", "distribution"], kind="mergesort"
        )
        other_param = valid.loc[valid["n_parameters"] != 2].sort_values(
            ["AIC", "distribution"], kind="mergesort"
        )
        ranked = pd.concat([two_param, other_param], ignore_index=True)
    else:
        ranked = valid.sort_values(["AIC", "distribution"], kind="mergesort").reset_index(drop=True)

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
            "AIC": np.nan,
            "loglik": np.nan,
            "loglik_positive_conditional": np.nan,
            "delta_AIC": np.nan,
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
            )
            models[label] = model
            aic, loglik, n_params, loglik_pos = _conditional_aic(
                model, series, prob_zero=prob_zero
            )
            base_row.update({
                "n_parameters": n_params,
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
                "pseudo_obs_added": model.pseudo_obs_added,
                "small_sample_warning": model.small_sample_warning,
                "AIC": aic,
                "loglik": loglik,
                "loglik_positive_conditional": loglik_pos,
            })

            # SPI series from model.cdf() evaluated on target observations
            spi_values = _spi_from_fitted_model(
                model, series, prob_zero=prob_zero, clip=sw_clip
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

            # SPI Anderson-Darling normality test (Lee et al. adaptation on SPI values)
            spi_clean = spi_values.dropna().to_numpy(dtype=float)
            spi_clean = spi_clean[np.isfinite(spi_clean)]
            spi_ad_stat = np.nan
            spi_ad_crit = np.nan
            spi_ad_pass = None
            if spi_clean.size >= 8:
                try:
                    ad_res = stats.anderson(spi_clean, dist="norm")
                    spi_ad_stat = float(ad_res.statistic)
                    # Index 2 corresponds to 5% significance level [15%, 10%, 5%, 2.5%, 1%]
                    spi_ad_crit = float(ad_res.critical_values[2])
                    spi_ad_pass = bool(spi_ad_stat < spi_ad_crit)
                except Exception as e_ad:
                    logger.debug("SPI AD normality test failed for %s: %s", label, e_ad)

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
            })
        except Exception as exc:
            base_row["error"] = f"{type(exc).__name__}: {exc}"
            logger.warning("Candidate %s failed: %s", label, exc)
        row_by_label[label] = base_row

    comparison = pd.DataFrame(list(row_by_label.values()))
    valid_aic = comparison[np.isfinite(comparison["AIC"].to_numpy(dtype=float))].copy()
    if valid_aic.empty:
        raise RuntimeError("All candidate fits failed or produced invalid AIC values.")

    min_aic = float(valid_aic["AIC"].min())
    comparison["delta_AIC"] = comparison["AIC"] - min_aic
    comparison.loc[~np.isfinite(comparison["AIC"]), "delta_AIC"] = np.nan
    comparison["AIC_competitive"] = comparison["delta_AIC"] < delta_aic_threshold

    # Stage 2: GoF testing
    if gof_scope == "all":
        candidates_to_test = list(valid_aic.sort_values("AIC")["distribution"])
    elif gof_scope == "competitive":
        candidates_to_test = list(
            comparison.loc[comparison["AIC_competitive"], "distribution"]
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
        table = pd.DataFrame([row_by_label[label] for label in candidate_map])
        table["delta_AIC"] = table["AIC"] - min_aic
        table.loc[~np.isfinite(table["AIC"]), "delta_AIC"] = np.nan
        table["AIC_competitive"] = table["delta_AIC"] < delta_aic_threshold
        return table

    comparison = current_table()

    def passing_candidates(frame: pd.DataFrame, competitive_only: bool) -> pd.DataFrame:
        mask = frame["gof_pass"].eq(True) & np.isfinite(frame["AIC"])
        if competitive_only:
            mask &= frame["AIC_competitive"]
        return frame.loc[mask].copy()

    # In competitive GoF mode, if fewer than 2 candidates pass, test remaining candidates in AIC order
    # until 2 passing candidates are found or all candidates are tested.
    competitive_pass = passing_candidates(comparison, competitive_only=True)
    if gof_scope == "competitive":
        untested = comparison.loc[
            np.isfinite(comparison["AIC"])
            & (~comparison["distribution"].isin(tested))
        ].sort_values(["AIC", "distribution"], kind="mergesort")

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

    if gof_scope == "none":
        eligible = comparison.loc[comparison["AIC_competitive"] & np.isfinite(comparison["AIC"])].copy()
        if eligible.empty:
            eligible = valid_aic.copy()
        ranked = _rank_rows(eligible, prefer_two_parameters=prefer_two_parameters)
        chosen_label = str(ranked.iloc[0]["distribution"])
        selection_status = "selected_by_aic_only"
        reason = (
            f"Selected by AIC; Delta AIC < {delta_aic_threshold:g} defines the competitive set. "
            "KS/AD bootstrap tests were disabled."
        )
        if len(ranked) >= 2:
            alt_label = str(ranked.iloc[1]["distribution"])
            alt_status = "selected_by_aic_only"
            alt_reason = (
                f"Alternative candidate from competitive set (Delta AIC < {delta_aic_threshold:g}) "
                "ranked #2 by AIC/parameter preference with bootstrap tests disabled."
            )
        else:
            alt_status = "no_alternative_available"
            alt_reason = "No eligible second candidate available in competitive set."
        gof_adequate = None

    elif not competitive_pass.empty:
        ranked_comp = _rank_rows(competitive_pass, prefer_two_parameters=prefer_two_parameters)
        chosen_label = str(ranked_comp.iloc[0]["distribution"])
        selection_status = "selected_within_delta_aic_and_gof_acceptable"
        reason = (
            f"Selected from candidates with Delta AIC < {delta_aic_threshold:g} that were not "
            f"rejected by either bootstrap KS or AD at alpha={alpha:g}. "
        )
        chosen_row_temp = comparison.loc[comparison["distribution"] == chosen_label].iloc[0]
        if prefer_two_parameters and int(chosen_row_temp["n_parameters"]) == 2:
            reason += "A two-parameter candidate was available and was prioritized."
        else:
            reason += "Lowest AIC among eligible competitive candidates was selected."
        gof_adequate = True

        if len(ranked_comp) >= 2:
            alt_label = str(ranked_comp.iloc[1]["distribution"])
            alt_status = "selected_within_delta_aic_and_gof_acceptable"
            alt_reason = (
                f"Alternative candidate also in competitive set (Delta AIC < {delta_aic_threshold:g}) "
                f"passing bootstrap KS and AD at alpha={alpha:g}."
            )
        else:
            outside_pass = all_pass.loc[~all_pass["distribution"].isin([chosen_label])]
            if not outside_pass.empty:
                ranked_out = _rank_rows(outside_pass, prefer_two_parameters=False)
                alt_label = str(ranked_out.iloc[0]["distribution"])
                alt_status = "fallback_outside_delta_aic"
                alt_reason = (
                    "Only one competitive candidate passed GoF. Alternative candidate is the lowest-AIC "
                    f"model outside the competitive set (Delta AIC >= {delta_aic_threshold:g}) passing both bootstrap tests."
                )
            else:
                alt_status = "no_alternative_available"
                alt_reason = "No second candidate passed both KS and AD bootstrap tests."

    elif not all_pass.empty:
        ranked_all = _rank_rows(all_pass, prefer_two_parameters=False)
        chosen_label = str(ranked_all.iloc[0]["distribution"])
        selection_status = "fallback_outside_delta_aic"
        reason = (
            f"No candidate within Delta AIC < {delta_aic_threshold:g} passed both bootstrap tests. "
            "Selected the lowest-AIC candidate among models that passed both KS and AD, "
            "even though it lies outside the initial competitive set."
        )
        gof_adequate = True
        if len(ranked_all) >= 2:
            alt_label = str(ranked_all.iloc[1]["distribution"])
            alt_status = "fallback_outside_delta_aic"
            alt_reason = (
                "Alternative candidate is the second lowest-AIC model passing bootstrap KS and AD, "
                "outside the initial Delta AIC competitive set."
            )
        else:
            alt_status = "no_alternative_available"
            alt_reason = "Only one candidate across all tested models passed bootstrap GoF."

    else:
        eligible = comparison.loc[comparison["AIC_competitive"] & np.isfinite(comparison["AIC"])].copy()
        if eligible.empty:
            eligible = valid_aic.copy()
        ranked = _rank_rows(eligible, prefer_two_parameters=prefer_two_parameters)
        chosen_label = str(ranked.iloc[0]["distribution"])
        selection_status = "provisional_no_candidate_passed_gof"
        reason = (
            "No tested candidate produced usable KS/AD results passing both tests. "
            "This is a provisional recommendation based on the AIC competitive set and "
            "parameter-count preference; inspect fitting and bootstrap diagnostics."
        )
        gof_adequate = False
        if len(ranked) >= 2:
            alt_label = str(ranked.iloc[1]["distribution"])
            alt_status = "provisional_no_candidate_passed_gof"
            alt_reason = (
                "Provisional alternative candidate based on AIC competitive set and parameter preference, "
                "as no candidate passed both bootstrap tests."
            )
        else:
            alt_status = "no_alternative_available"
            alt_reason = "No second candidate available in competitive set."

    comparison = current_table().sort_values(
        ["AIC", "distribution"], kind="mergesort", na_position="last"
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
        "delta_AIC": float(chosen_row["delta_AIC"]),
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
        "alternative_delta_AIC": float(alt_row["delta_AIC"]) if alt_row is not None else np.nan,
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


def summarize_candidate_diagnostics(
    details: pd.DataFrame,
    *,
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

    n_groups_total = int(details["group_id"].nunique())
    records: list[dict[str, Any]] = []

    for label, group in details.groupby("distribution", dropna=False):
        n_params = int(pd.to_numeric(group["n_parameters"], errors="coerce").dropna().iloc[0]) if "n_parameters" in group.columns and not group["n_parameters"].dropna().empty else 2

        # Fit coverage
        fit_status_col = group.get("fit_status", pd.Series(dtype=object))
        n_fit_success = int(np.sum(fit_status_col == "success"))
        n_fit_failed = int(len(group) - n_fit_success)
        fit_coverage_pct = float(100.0 * n_fit_success / n_groups_total) if n_groups_total > 0 else 0.0

        # AIC coverage
        aic_vals = pd.to_numeric(group.get("AIC", pd.Series(dtype=float)), errors="coerce")
        aic_valid = aic_vals[np.isfinite(aic_vals)]
        n_aic_valid = int(aic_valid.size)
        aic_coverage_pct = float(100.0 * n_aic_valid / n_groups_total) if n_groups_total > 0 else 0.0

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
        aic_win_rate_pct = float(100.0 * aic_win_count / n_groups_total) if n_groups_total > 0 else 0.0

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
        meets_target = bool(np.isfinite(spi_ad_pass_ratio) and spi_ad_pass_ratio >= normality_ratio_threshold)

        record: dict[str, Any] = {
            "distribution": label,
            "n_parameters": n_params,
            "n_groups_total": n_groups_total,
            "n_fit_success": n_fit_success,
            "n_fit_failed": n_fit_failed,
            "fit_coverage_pct": fit_coverage_pct,
            "n_AIC_valid": n_aic_valid,
            "AIC_coverage_pct": aic_coverage_pct,
            "n_SW_tested": n_sw_tested,
            "n_SW_rejected": n_sw_rejected,
            "SW_rejection_frequency_pct": sw_rej_pct,
            "SW_nonrejection_ratio": sw_nonrej_ratio,
            "mean_delta_AIC": mean_delta,
            "median_delta_AIC": median_delta,
            "aic_competitive_pct": aic_comp_pct,
            "aic_win_rate_pct": aic_win_rate_pct,
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
    """
    if candidate_summary.empty:
        raise ValueError("candidate_summary is empty.")

    df = candidate_summary.copy()
    min_pct = min_valid_group_fraction * 100.0
    eligible_mask = (df["fit_coverage_pct"] >= min_pct) & (df["AIC_coverage_pct"] >= min_pct)
    eligible = df.loc[eligible_mask].copy()

    coverage_ok = True
    if eligible.empty:
        coverage_ok = False
        eligible = df.loc[df["n_AIC_valid"] > 0].copy()
        if eligible.empty:
            eligible = df.copy()

    any_meets_normality = bool(
        (eligible["meets_90pct_normality_target"] == True).any()
    )

    if ranking_method == "hierarchical":
        # Partition into tiers based on normality target and coverage
        tier_list = []
        for _, row in eligible.iterrows():
            meets_norm = bool(row["meets_90pct_normality_target"])
            mean_d = float(row["mean_delta_AIC"]) if np.isfinite(row["mean_delta_AIC"]) else 999.0
            is_comp = mean_d < delta_aic_threshold
            n_p = int(row["n_parameters"])

            if any_meets_normality:
                tier = 1 if meets_norm else 2
            else:
                tier = 1  # all in tier 1 under provisional status

            # Rank score tuple for sorting:
            # tier (lower better),
            # is_competitive (True/0 before False/1),
            # prefer 2-parameter if competitive (0 before 1),
            # mean_delta_AIC (ascending),
            # SW_nonrejection_ratio (descending -> negate),
            # SPI_AD_group_pass_ratio (descending -> negate),
            # distribution name (ascending for deterministic tie-break)
            comp_rank = 0 if is_comp else 1
            param_rank = 0 if (prefer_two_parameters and is_comp and n_p == 2) else 1
            sw_score = -float(row["SW_nonrejection_ratio"]) if np.isfinite(row["SW_nonrejection_ratio"]) else 0.0
            ad_score = -float(row["SPI_AD_group_pass_ratio"]) if np.isfinite(row["SPI_AD_group_pass_ratio"]) else 0.0

            tier_list.append((
                tier, comp_rank, param_rank, mean_d, sw_score, ad_score, str(row["distribution"])
            ))

        sorted_indices = sorted(range(len(eligible)), key=lambda i: tier_list[i])
        ranked_df = eligible.iloc[sorted_indices].reset_index(drop=True)
        ranked_df.insert(0, "global_rank", np.arange(1, len(ranked_df) + 1))

        best_label = str(ranked_df.iloc[0]["distribution"])
        alt_label = str(ranked_df.iloc[1]["distribution"]) if len(ranked_df) >= 2 else None

        if not coverage_ok:
            best_status = "provisional_insufficient_group_coverage"
            alt_status = "provisional_insufficient_group_coverage" if alt_label else None
            reason = f"No candidate met the minimum valid group coverage fraction ({min_valid_group_fraction:.0%})."
        elif not any_meets_normality:
            best_status = "provisional_normality_target_not_met"
            alt_status = "provisional_normality_target_not_met" if alt_label else None
            reason = (
                f"No candidate met the {normality_ratio_threshold:.0%} normality pass ratio target. "
                "Recommendation is provisional based on relative Delta AIC and SW diagnostics."
            )
        else:
            best_status = "accepted"
            alt_status = "accepted" if alt_label else None
            reason = f"Ranked #1 via hierarchical criteria meeting {normality_ratio_threshold:.0%} normality target."

    else:  # consensus_rank (Borda count across criteria)
        df_eval = eligible.copy()
        df_eval["rank_aic"] = df_eval["mean_delta_AIC"].rank(ascending=True)
        df_eval["rank_sw"] = df_eval["SW_rejection_frequency_pct"].rank(ascending=True)
        df_eval["rank_ad"] = df_eval["SPI_AD_group_pass_ratio"].rank(ascending=False)
        df_eval["consensus_score"] = (df_eval["rank_aic"] + df_eval["rank_sw"] + df_eval["rank_ad"]) / 3.0
        ranked_df = df_eval.sort_values(
            ["consensus_score", "mean_delta_AIC", "distribution"], kind="mergesort"
        ).reset_index(drop=True)
        ranked_df.insert(0, "global_rank", np.arange(1, len(ranked_df) + 1))

        best_label = str(ranked_df.iloc[0]["distribution"])
        alt_label = str(ranked_df.iloc[1]["distribution"]) if len(ranked_df) >= 2 else None
        best_status = "consensus_rank_user_option"
        alt_status = "consensus_rank_user_option" if alt_label else None
        reason = "Ranked #1 using complementary consensus / Borda score across Delta AIC, SW, and SPI AD."

    return {
        "global_ranking": ranked_df,
        "best_distribution": best_label,
        "alternative_distribution": alt_label,
        "best_selection_status": best_status,
        "alternative_selection_status": alt_status,
        "normality_target_met_by_any_candidate": any_meets_normality,
        "selection_reason": reason,
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
    min_valid_group_fraction: float = 0.80,
    normality_ratio_threshold: float = 0.90,
    ranking_method: Literal["hierarchical", "consensus_rank"] = "hierarchical",
) -> dict[str, Any]:
    """Run automatic selection for independent fitting groups and compute global rankings.

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

    recommendations = pd.DataFrame(all_recommendations)
    details = pd.concat(all_details, ignore_index=True) if all_details else pd.DataFrame()

    if not details.empty:
        candidate_summary = summarize_candidate_diagnostics(
            details,
            alpha=alpha,
            delta_aic_threshold=delta_aic_threshold,
            normality_ratio_threshold=normality_ratio_threshold,
        )
        agg_rank = rank_aggregated_candidates(
            candidate_summary,
            min_valid_group_fraction=min_valid_group_fraction,
            delta_aic_threshold=delta_aic_threshold,
            normality_ratio_threshold=normality_ratio_threshold,
            prefer_two_parameters=prefer_two_parameters,
            ranking_method=ranking_method,
        )
        global_ranking = agg_rank["global_ranking"]
        best_dist = agg_rank["best_distribution"]
        alt_dist = agg_rank["alternative_distribution"]
        best_status = agg_rank["best_selection_status"]
        alt_status = agg_rank["alternative_selection_status"]
        normality_met = agg_rank["normality_target_met_by_any_candidate"]
        reason = agg_rank["selection_reason"]
    else:
        candidate_summary = pd.DataFrame()
        global_ranking = pd.DataFrame()
        best_dist = None
        alt_dist = None
        best_status = "no_valid_groups"
        alt_status = None
        normality_met = False
        reason = "No groups could be evaluated."

    return {
        "recommendations": recommendations,
        "details": details,
        "candidate_summary": candidate_summary,
        "global_ranking": global_ranking,
        "best_distribution": best_dist,
        "alternative_distribution": alt_dist,
        "best_selection_status": best_status,
        "alternative_selection_status": alt_status,
        "normality_target_met_by_any_candidate": normality_met,
        "selection_reason": reason,
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
