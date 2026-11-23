# SPEI Package Enhancements & Architectural Evolution
**Version: 0.9.1 (Upgraded from Original v0.8.2 by Martin Vonk)**  
**Lead Contributor:** Hayu Nur Mahron (`hayu.mahron@bmkg.go.id`) — Badan Meteorologi, Klimatologi, dan Geofisika (BMKG)  
**Original Author:** Martin A. Vonk (`vonk.mart@gmail.com`)

---

## 1. Executive Summary

This document provides a comprehensive technical record of the structural, numerical, and statistical enhancements developed for the `spei` Python package, transforming it from a general monthly drought index utility (v0.8.2) into a state-of-the-art Daily Standardized Precipitation Index (DSPI) scientific engine (v0.9.0).

The enhancements incorporate theoretical and operational methodologies from:
1. **Wang et al. (2022)** — *An improved daily standardized precipitation index dataset for mainland China from 1961 to 2018*, Scientific Data, 9, 201. DOI: `10.1038/s41597-022-01201-z`.
2. **Stagge et al. (2015)** — *Candidate Distributions for Climatological Drought Indices (SPI and SPEI)*, International Journal of Climatology, 35(13), 4027–4040. DOI: `10.1002/joc.4267`.
3. **Burnham & Anderson (2002)** — *Model Selection and Multimodel Inference: A Practical Information-Theoretic Approach*, Springer.

---

## 2. Comprehensive Comparison: v0.8.2 (Original) vs. v0.9.0 (Enhanced)

The original package implementation is preserved in [`src/spei/reference/`](file:///Users/mahron/Data/python/SPEI/src/spei/reference/) as:
- [`dist_martinvonk.py`](file:///Users/mahron/Data/python/SPEI/src/spei/reference/dist_martinvonk.py)
- [`si_martinvonk.py`](file:///Users/mahron/Data/python/SPEI/src/spei/reference/si_martinvonk.py)
- [`utils_martinvonk.py`](file:///Users/mahron/Data/python/SPEI/src/spei/reference/utils_martinvonk.py)

The table below contrasts the original implementation against version 0.9.0:

| Feature / Capability | Original Implementation (v0.8.2, Martin Vonk) | Enhanced Scientific Engine (v0.9.0, BMKG / Current) | Scientific Rationale & Impact |
| :--- | :--- | :--- | :--- |
| **Probability Distributions** | Basic continuous distributions via generic `scipy.stats` default fitting. | 7 validated candidate distributions: Gamma, Weibull (`weibull_min`), Gumbel-R (`gumbel_r`), Lognormal (`lognorm`), Fisk (`fisk`), Pearson III (`pearson3`), GEV (`genextreme`). | Covers diverse precipitation skewness, tail weights, and arid/monsoonal climatic regimes (Stagge et al. 2015). |
| **Distribution Fitting Strategy** | Single-stage default `scipy.fit()` with initial guess `scale = std(data)`. | Multi-stage pipeline: Theoretical L-moments / Method of Moments (MM) initialization $\rightarrow$ Nelder-Mead Maximum Likelihood Estimation (MLE) $\rightarrow$ Robust fallback chain. | Prevents optimizer divergence, local minima trapping, and unrealistic parameter values. |
| **Zero-Precipitation Handling** | Empirical zero frequency: $p_0 = \frac{m}{n}$. Zero values fitted unconditionally inside continuous distribution. | Rigorous conditional-positive CDF: continuous distribution fitted strictly to $x > 0$. Zero mass $p_0 = \frac{m}{n+1}$ (Stagge et al. 2015). | Unconditional fitting of zero into positive distributions corrupts shape and scale estimation. |
| **Zero Quantile Centroid** | Hardcoded $F(0) = p_0$. Centroid and zero mass conflated. | Explicit plotting-position centroid: $p_{\text{centroid}} = \frac{m + 1}{2(n + 1)}$ for zero values: $\text{SPI}_0 = \Phi^{-1}(p_{\text{centroid}})$. | Symmetrical, unbiased normal quantile transformation for zero precipitation. |
| **Wang et al. (2022) Replication** | Not supported. | Dedicated mode `fitting_policy="wang"` reproducing Wang's exact Nelder-Mead Gamma fitting, zero-handling, and small-sample heuristics. | Achieves 100% exact numerical parity ($\text{MAE} = 0.000000$, Pearson $r = 1.000000$) with published reference datasets. |
| **Small Sample Governance** | Crashed or generated unvalidated parameters when positive samples were scarce. | Two explicit policies: <br>1. `small_sample_policy="strict"` (honest unidentifiable NaNs for $n_{\text{pos}} < 2$ or $<3$). <br>2. `small_sample_policy="augmented"` ($\min(x_{\text{pos}}) \times 0.01$, alias `"pseudo_observation_experimental"`). | Strict separation between genuine observational evidence and synthetic sensitivity heuristics. |
| **Gumbel-R Parameterization** | Unconstrained, often unstable on zero-inflated samples. | Strict 2-parameter distribution (`loc`, `scale`). Fitted conditionally on positive rainfall ($x > 0$). | Conforms to extreme-value theory without phantom shape parameters. |
| **All-Zero Calendar Handling** | Produced NaNs or uncaught runtime warnings. | Configurable `all_zero_policy` (`"wang"`, `"stagge"`, `"zero"`). Wang mode assigns exact median centroid $\Phi^{-1}(0.5) = 0.0$. | Complete stability during prolonged dry seasons and arid climate periods. |
| **Model Selection & Goodness-of-Fit** | Only basic two-sided Kolmogorov–Smirnov test (`ks_test`) against continuous distribution. | Automated information-theoretic selection (`model_selection.py`): Burnham–Anderson $\Delta\text{AIC} < 2$, Parametric Bootstrap KS and AD, and Shapiro–Wilk post-transformation normality test. | Eliminates subjective distribution choice; rigorously identifies best-fitting distributions based on empirical data. |
| **Calendar & Leap Year Handling** | Simple grouping by year assuming 365/366 day indexing; prone to phase shift across multi-year series. | Full 366-day calendar normalization (`%m-%d`) with explicit leap day handling (`isleap`, 29 February). | Prevents artificial phase shifts (which caused +3 days calendar lag in naive 365-day reshape scripts). |
| **Pre-accumulated Series (`rolled_10`)** | Not cleanly decoupled from `timescale`. | Explicit `timescale=0` mode to accept pre-accumulated rolling sums without double-summation. | Facilitates operational ingestion of pre-computed rolling rainfall series. |
| **Monthly SPI from Daily Data** | Required manual external resampling (`resample('MS')`). Direct daily call mispooled observations into non-standard groups. | Native `fit_freq="monthly"` with automatic `to_monthly()` aggregation, nominal daily timescale mapping (`timescale=90` $\to$ 3 months), and pre-rolled support (`timescale=0`). | Full parity with operational rain gauge workflows without manual pre-processing. |
| **Diagnostics & Traceability** | None. `Dist` only stored `pars, loc, scale, p0`. | Comprehensive attributes: `fit_status`, `parameters_valid`, `cdf_valid`, `pseudo_obs_added`, `loglik`, `AIC`, and summary exporter `generate_nan_diagnostic_summary()`. | Complete operational audit trail explaining the exact reason for any `NaN` values. |
| **Automated Test Coverage** | 12 basic tests in `test_si.py`. | 107 comprehensive tests across 4 test suites (`test_master_task_dspi.py`, `test_audit_34010701a.py`, `test_nan_diagnostics.py`, `test_si.py`). | 100% automated verification of edge cases, small samples, and numerical stability. |

---

## 3. Detailed Architectural Enhancements

### 3.1 Module `src/spei/dist.py`

#### 1. Multi-Stage Parameter Estimation Framework
For each candidate distribution, `Dist` implements a staged estimation pipeline:
- **Stage 1 (Theoretical Initialization):** Calculates Method of Moments (MM) or L-moments estimates on positive observations ($x > 0$).
  - Gamma: $\alpha_0 = \frac{\mu^2}{\sigma^2}$, $\beta_0 = \frac{\sigma^2}{\mu}$
  - Weibull: Shape $k$ solved via moment-ratio equation; Scale $\lambda = \frac{\mu}{\Gamma(1 + 1/k)}$
  - Gumbel-R: $\beta_0 = \frac{\sqrt{6}}{\pi} \sigma$, $\mu_0 = \mu - \gamma \beta_0$ ($\gamma \approx 0.57721566$)
  - Lognormal: $\mu_{\log} = \text{mean}(\ln x)$, $\sigma_{\log} = \text{std}(\ln x)$
  - Pearson III: Skewness-matched moments
  - GEV: Probability Weighted Moments / L-moments
- **Stage 2 (Constrained Optimization):** Nelder-Mead simplex algorithm minimizing the negative log-likelihood with bounded parameters ($\text{scale} > 0, \text{shape} > 0$).
- **Stage 3 (Validation & Fallback):** If Nelder-Mead fails to converge or yields invalid parameters, the pipeline falls back to L-moments / Method of Moments and records `fit_method="fallback_moments"` and `parameters_valid=True`.

#### 2. Isolation of Wang et al. (2022) Mode (`fitting_policy="wang"`)
The replication logic of Wang et al. (2022) is completely isolated within `_fit_wang_gamma()`:
- Only activated when `dist.name == "gamma"` and `fitting_policy == "wang"`.
- Adheres to Wang's exact Nelder-Mead objective function and parameter initial guesses.
- When $1 \le n_{\text{pos}} \le 3$, Wang adds two pseudo-observations: $\mu_{\text{pos}} \times 0.01$ and $\mu_{\text{pos}} \times 0.001$, allowing Gamma fitting even with scarce rain events.
- Never generalized to other distributions; other distributions remain strictly governed by standard statistical principles.

#### 3. Strict vs. Experimental Small-Sample Policy
- `small_sample_policy="strict"` (Default):
  - 2-parameter distributions require $n_{\text{pos}} \ge 2$.
  - 3-parameter distributions require $n_{\text{pos}} \ge 3$.
  - If $n_{\text{pos}}$ is insufficient, fitting is aborted cleanly with `fit_status="insufficient_positive_sample"`. The resulting CDF and SPI are honest `NaN` values.
- `small_sample_policy="augmented"`:
  - Appends $\min(x_{\text{pos}}) \times 0.01$ when $1 \le n_{\text{pos}} \le 3$, enabling 2-parameter fitting while setting `pseudo_obs_added=True` for auditing. Legacy alias `"pseudo_observation_experimental"` remains supported.

#### 4. Mixed Cumulative Density Function (CDF)
For positive precipitation series ($x \ge 0$), the cumulative probability $H(x)$ is computed as:
$$H(x) = p_0 + (1 - p_0) \cdot F(x; \boldsymbol{\theta})$$
where:
- $p_0 = \frac{m}{n + 1}$ ($m$ is the count of zeros, $n$ is sample size).
- $F(x; \boldsymbol{\theta})$ is the fitted continuous CDF evaluated on positive data ($x > 0$).
- For observations with $x = 0.0$, the plotting-position centroid is assigned:
  $$H(0) = p_{\text{centroid}} = \frac{m + 1}{2(n + 1)}$$
- Normal quantile transformation produces the SPI series:
  $$\text{SPI} = \Phi^{-1}(H(x))$$

---

### 3.2 Module `src/spei/si.py`

#### 1. Integration of Fitting & Small-Sample Policies
The `SI` class and `spi()` wrapper expose:
```python
spi(
    series,
    dist=gamma,
    timescale=0,
    fit_freq="D",
    fit_window=0,
    prob_zero=True,
    all_zero_policy="wang",
    fitting_policy="standard",
    small_sample_policy="strict",
)
```

#### 2. Robust Calendar Grouping & Leap-Year Preservation
- Groups data across years by calendar date (`%m-%d`, 366 unique bins).
- Preserves February 29 observations without index truncation or column misalignment.
- Accurately computes $n$, $m$, $n_{\text{pos}}$, $p_0$, and $p_{\text{centroid}}$ independently for every calendar day.

#### 3. Diagnostic Reporting API
- `get_diagnostics()`: Returns a structured pandas DataFrame summarizing parameter values, status flags, and sample counts for all calendar groups.
- `generate_nan_diagnostic_summary()`: Aggregates the root causes of all `NaN` values across the entire output time series.

---

### 3.3 New Module `model_selection.py`

The new `model_selection.py` module provides an automated, objective framework for selecting candidate distributions:

1. **Akaike Information Criterion (AIC):**
   $$\text{AIC} = 2k - 2\ln(L)$$
   computed strictly on positive conditional observations ($x > 0$).
2. **Burnham & Anderson (2002) Competitive Set:**
   Calculates $\Delta\text{AIC} = \text{AIC}_i - \min(\text{AIC})$. Candidates with $\Delta\text{AIC} < 2$ are deemed competitive. A 2-parameter model within $\Delta\text{AIC} < 2$ is preferred over a 3-parameter model to prevent overparameterization.
3. **Parametric Bootstrap Goodness-of-Fit Tests:**
   Evaluates Kolmogorov–Smirnov (KS) and Anderson–Darling (AD) statistics against a parametric bootstrap distribution of critical values.
4. **Shapiro–Wilk Normality Test:**
   Evaluates the normality of transformed SPI values ($\text{SPI} \sim \mathcal{N}(0, 1)$), testing whether the transformation successfully normalized the observed climate record.
5. **Safe Handling of Underdetermined Groups:**
   Calendar groups with $n_{\text{pos}} < 3$ are automatically assigned `selection_status="not_evaluable"` instead of crashing the batch selection pipeline.

---

### 3.4 Scientific Validation & Integration of Distribution Selection (v0.9.1 Master Prompt)

The latest enhancements integrate distribution selection across `dist.py`, `model_selection.py`, and `si.py` in accordance with Stagge et al. (2015), Lee et al. (2023), and Burnham & Anderson (2002):

#### 1. Empirical GEV Sign Convention & Skewness Derivation
- Proved empirically that `lmoments3.distr.gev.lmom_fit()` shares the exact same sign convention as `scipy.stats.genextreme` ($c > 0$ for Weibull-like bounded upper tail, $c < 0$ for Fréchet heavy tail). The sign of $c$ from `lmoments3` is strictly preserved without inversion.
- Derived the exact SciPy theoretical skewness formula for `estimate_gev_moments()`:
  $$\text{skew}(c) = -\text{sign}(c) \frac{g_3 - 3 g_1 g_2 + 2 g_1^3}{(g_2 - g_1^2)^{3/2}}, \quad g_k = \Gamma(1 + k c)$$
  achieving numerical error $< 10^{-14}$ against SciPy and robust Brentq root-finding for both positive and negative shape parameters.

#### 2. Conditional-Positive Likelihood & Degeneracy Protection
- Replaced hardcoded `conditional_positive=False` for Gumbel-R in `_fit_standard_dist()` with dynamic flag `cond_pos = bool(conditional_positive)`.
- Protected signed series (SPEI) in `Dist.__post_init__()` so that `conditional_positive` is only active when `prob_zero and conditional_positive`.
- Introduced a physical survival floor:
  $$\text{if } \ln(1 - F(0)) < -4.60517 \quad (SF(0) < 0.01) \implies \text{return } \infty$$
  preventing Nelder-Mead from driving $loc \to -\infty$ on small positive samples ($n \le 4$), which previously caused $s_0 \le 10^{-12}$ and CDF evaluation failures.
- Guaranteed that `Dist.goodness_of_fit()` passes `conditional_positive=cond_pos` to all bootstrap refits, achieving a 100% bootstrap refit success rate.

#### 3. Single-Source-of-Truth SPI Transformation
- `_spi_from_fitted_model()` directly calls `Dist.cdf()`, preserving mixture probabilities for $X > 0$ and plotting-position centroid $p_{\text{centroid}} = \frac{m+1}{2(n+1)}$ for $X = 0$.
- Changed default `sw_clip` to `None` to prevent distortion of extreme tail distributions before Shapiro–Wilk normality testing.
- Introduced deterministic `sw_zero_seed` per group to ensure identical random standard-normal draws for zero-rainfall observations across all competing candidates.

#### 4. Dual Model Recommendation (#1 Best & #2 Alternative)
- Implemented `_rank_rows()` to deterministically return both:
  - **Best Distribution (#1):** Lowest AIC or preferred 2-parameter model within the competitive set ($\Delta\text{AIC} < 2.0$) passing GoF.
  - **Alternative Distribution (#2):** Second-best eligible model from the competitive set, or lowest-AIC fallback model passing GoF outside the competitive set.
  - Stored model instances `selected_model` (#1) and `alternative_model` (#2) alongside legacy keys for backward compatibility.

#### 5. Two Deterministic Aggregate Ranking Methodologies

##### A. Hierarchical Ranking (`ranking_method="hierarchical"`, Default)
Designed strictly around Burnham & Anderson (2002) information-theoretic parsimony:
1. **Eligibility Filter:** Disqualifies distributions failing minimum group coverage (`min_valid_group_fraction = 0.80`).
2. **Normality Target Tiering:** Identifies if any candidate meets the 90% SPI normality target (Lee et al. 2023). If none meets 90%, all eligible models enter Tier 1 under `provisional_normality_target_not_met` status.
3. **Competitive Shortlist ($\Delta\text{AIC} < 2.0$):** Prioritizes candidates with mean $\Delta\text{AIC} < 2.0$.
4. **Parsimony Tie-Breaker:** Prioritizes 2-parameter models *only* if they lie within the competitive set ($\Delta\text{AIC} < 2.0$). 2-parameter models with large $\Delta\text{AIC}$ (e.g., $\Delta\text{AIC} > 10$) are never promoted over well-fitting 3-parameter models.
5. **Deterministic Tie-Break:** Sorts by mean $\Delta\text{AIC}$ ascending, S-W non-rejection ratio descending, SPI AD pass ratio descending, and distribution name alphabetically.

##### B. Consensus / Borda Ranking (`ranking_method="consensus_rank"`, User Option)
Designed for balanced operational weighting across three distinct diagnostic dimensions:
$$\text{Consensus Score} = \frac{\text{Rank}(\Delta\text{AIC}) + \text{Rank}(\text{SW Rejection}) + \text{Rank}(\text{SPI AD Pass})}{3}$$
- Directly accounts for the empirical observation that 2-parameter models (Weibull, Gumbel-R, Gamma) frequently achieve superior SPI normality (S-W rejection rates $< 7\%$) despite higher $\Delta\text{AIC}$ on skewed raw precipitation data.
- Yields **Weibull minimum as #1**, **Gumbel-R as #2**, and **Gamma as #3** on station `34010701a`.

#### 6. Native `SI.select_optimal_distribution(...)` Integration
Integrated directly into the `SI` class (`src/spei/si.py`), supporting both `fit_window=0` and rolling calibration windows `fit_window > 0` with identical calendar alignment logic as `SI.fit_distribution()`. The method is purely non-mutating: it evaluates and recommends candidates without altering `self.dist` or `_dist_dict`.

---

### 3.5 Targeted Hardening Pass: Wang AIC Eligibility, Fair Consensus Ranking, and Dasarian Safety

A final targeted hardening pass was performed to ensure statistical rigor and operational safety:

#### 1. Wang Gamma Pseudo-Observation vs Observational AIC Eligibility (`dist.py`, `model_selection.py`)
- **Mathematical Distinction:** In `_fit_wang_gamma()`, when pseudo-observations are added (`pseudo_obs_added=True`), the objective is optimized on an augmented sample ($N + 1$ or $N + 2$ data points). While the resulting parameters are valid MLEs for the augmented dataset and remain fully functional for empirical SPI calculation, the fit is **not** an ordinary MLE of the observational data ($N$).
- **Hardening Policy:** Fits with `pseudo_obs_added=True` are assigned:
  - `is_mle = False` (with respect to the observational sample)
  - `aic_comparable = False`
  - `aic_incomparable_reason = "pseudo_observation_augmented_fit"`
  - Disqualified from winning minimum AIC in official observational-data model selection.
- **Unaugmented Wang Fits:** When `pseudo_obs_added=False` and optimization converges, the fit is an exact observational MLE and remains fully `aic_comparable=True`.
- **Diagnostics Preserved:** Output records `converged`, `n_positive`, and `n_fitting` for full audit transparency.

#### 2. Fair Consensus Ranking without Silent Partial Scoring (`model_selection.py`)
- **Problem Resolved:** Averaging ranks across available metrics with `skipna=True` allowed candidates missing one or more metrics (e.g. 2 out of 3 criteria) to obtain an unfairly low (better) consensus score than complete candidates evaluated across all 3 criteria.
- **Mandatory Complete Pool:** `consensus_rank` requires a consistent, complete set of mandatory criteria (`mean_delta_AIC`, `SW_group_non_rejection_ratio`, `SPI_AD_group_pass_ratio`).
- **Ineligible Candidate Handling:** Incomplete candidates receive `consensus_score = NaN`, `global_rank = NaN`, and `consensus_eligible = False` with an explicit reason (`missing_mean_delta_aic`, `missing_sw_metric`, `missing_spi_ad_metric`, or `missing_required_consensus_metrics`). They remain visible in `global_ranking`.
- **No Fabricated Winners:** If no candidate has all mandatory criteria, `best_distribution = None` and `best_selection_status = "provisional_insufficient_consensus_metrics"`.

#### 3. Sparse Dasarian Calendar Handling & Cadence Disambiguation (`utils.py`, `si.py`)
- **Label Validity vs Cadence Completeness:** Timestamps on days 1, 11, and 21 are recognized as valid BMKG dasarian calendar labels (`is_valid_dasarian_labels`) even when intervening dekads are missing.
- **Cadence Disambiguation:** `is_dasarian_index()` conservatively classifies series with dates exclusively on day 1 and median interval $\ge 25$ days as monthly rather than dasarian.
- **Explicit Frequency Contract:** In `SI.__post_init__()`, if `fit_freq in ("dekad", "dasarian")` is explicitly requested and the index contains valid dasarian labels, it is recognized as pre-aggregated dasarian data. Redundant daily aggregation via `to_dasarian()` is bypassed, preventing double aggregation while preserving calendar gaps as `NaN`.

#### 4. Canonical Reindexing and Strict Midnight Label Validation (`utils.py`)
- **Exact Midnight Requirement:** `rolling_dasarian()` strictly requires exact midnight calendar labels (`00:00:00`) on days 1, 11, or 21.
- **Silent Row Drop Elimination:** Non-midnight timestamps (e.g. `2020-01-01 12:00:00`), timezone-aware timestamps, duplicate timestamps, or invalid days raise clear, descriptive `ValueError`s rather than silently dropping rows into `NaN` during canonical calendar reindexing.

---

### 3.6 Native Monthly SPI Architecture with Daily Ingestion & Timescale Mapping

To eliminate developer friction when working with raw rain gauge station records (`data pos hujan`), a dedicated native monthly engine is introduced mirroring the dasarian architecture:

#### 1. Daily Ingestion Contract (`fit_freq in ("monthly", "month", "m", "ms")`)
- **Automatic Aggregation:** When raw daily observations are supplied with `fit_freq="monthly"`, `SI.__post_init__()` automatically invokes `to_monthly()` to aggregate daily observations into canonical monthly sums (`MS`: `YYYY-MM-01`).
- **Pre-Aggregated / Pre-Rolled Ingestion:** If the input series already exhibits monthly cadence (`is_monthly_index()`), redundant aggregation is bypassed. When `timescale=0`, pre-accumulated monthly sums are consumed directly.
- **Pre-Rolled Daily Ingestion:** When `timescale=0` is passed alongside daily pre-accumulated rolling sums (e.g. a daily `rolled_90` series), observations are sampled at month boundaries, providing exact alignment with standard monthly reporting.

#### 2. Dual Timescale Representation (`monthly_windows`)
- Users may specify `timescale` either in **nominal days** (matching operational daily thinking: `30` $\to$ 1M, `60` $\to$ 2M, `90` $\to$ 3M, `180` $\to$ 6M, `360` $\to$ 12M) or in **direct calendar months** (`1`, `2`, `3`, `6`, `12`, `24`).
- Automatic resolution mapping ensures that `timescale=90` applies a 3-month trailing accumulation (`rolling(3)`) across the canonical monthly calendar.

#### 3. Data Completeness & Leap-Year Quality Control (`to_monthly`)
- Evaluates the true calendar length of each month (28/29 days for February, 30, and 31 days).
- Enforces configurable data completeness via `min_valid_fraction` (default `1.0` strict, or e.g. `0.80`) or `min_valid_days` (e.g. `25` days), setting incomplete months to `NaN` to prevent artificially low precipitation totals from corrupting distribution fitting.

---

## 4. Verification & Master Task Audit on Station `34010701a`

The framework underwent an exhaustive numerical validation on rain gauge station **`34010701a`** (BPP Pengasih, Kulon Progo, DIY; 2010–2024, 5,479 records):

### Key Empirical Results:
1. **Replication of Wang et al. (2022):**
   - Paired numerical comparison between `spei` (v0.9.0, `fitting_policy="wang"`) and Wang's `utilsPY.py` across 5,470 daily 10D rolling observations yielded:
     - $\text{MAE} = \mathbf{0.000000}$
     - $\text{RMSE} = \mathbf{0.000000}$
     - Pearson $r = \mathbf{1.000000}$
     - Sign agreement = $\mathbf{100.0\%}$
2. **Identification of the "Phase Shift" Bug in Naive Reshape:**
   - Demonstrates that naive reshape `reshape((-1, 365))` shifts data by 1 day per leap year, causing a **3-day calendar shift by 2020–2021** ($\text{MAE} = 0.0815$, $\text{Max Diff} = 0.7663$). Exact calendar alignment resolves the discrepancy completely.
3. **Distribution Selection Across 366 Calendar Days:**
   - Evaluated 7 candidate distributions across 366 calendar groups (10-day rolling accumulation). 356 groups had sufficient rain observations ($\ge 3$ positive events).
   - **Hierarchical Winner (#1):** Pearson III (Mean $\Delta\text{AIC} = 1.06$, AIC win rate $= 55.3\%$, competitive in $78.0\%$ of days).
   - **Alternative Winner (#2):** GEV (Mean $\Delta\text{AIC} = 11.57$, Median $= 3.59$).
   - **Consensus Winner (#1):** Weibull minimum (Consensus score $= 2.33$, S-W non-rejection $= 93.8\%$, SPI AD pass $= 50.7\%$).
4. **Localization of 90 Strict NaNs (1.65%):**
   - All 90 NaNs in the operational strict series occur on **August 25–30** across all 15 years.
   - Root cause: In 15 years of record, 14 years had 0.0 mm rain and only 1 year (2010) had rain (15.5 mm), resulting in $n_{\text{pos}} = 1$. Under strict mathematical guidelines, 2-parameter distributions correctly flag this as unidentifiable (`insufficient_positive_sample`).

---

## 5. Automated Test Suite

The package includes a comprehensive automated test suite in `tests/`:

- [`tests/test_distribution_selection_master.py`](file:///Users/mahron/Data/python/SPEI/tests/test_distribution_selection_master.py) (27 tests: GEV conventions, conditional-positive, AIC parsimony, SPI transform, SI integration, normality metrics, Tests A1–A5 for Wang AIC eligibility, and Tests C1–C7 for fair consensus ranking)
- [`tests/test_dasarian.py`](file:///tests/test_dasarian.py) (19 tests: dasarian aggregation, rolling accumulation, Tests D1–D4 for calendar cadence, sparse explicit handling, and midnight validation)
- [`tests/test_monthly.py`](file:///Users/mahron/Data/python/SPEI/tests/test_monthly.py) (9 tests: native daily-to-monthly aggregation, timescale mapping, pre-rolled input, and leap-year/data completeness thresholds)
- [`tests/test_master_task_dspi.py`](file:///Users/mahron/Data/python/SPEI/tests/test_master_task_dspi.py) (32 tests covering all 18 conditions of the Master Task)
- [`tests/test_audit_34010701a.py`](file:///Users/mahron/Data/python/SPEI/tests/test_audit_34010701a.py) (31 tests)
- [`tests/test_nan_diagnostics.py`](file:///Users/mahron/Data/python/SPEI/tests/test_nan_diagnostics.py) (25 tests)
- [`tests/test_si.py`](file:///Users/mahron/Data/python/SPEI/tests/test_si.py) (60 tests covering core SI, estimators, and distributions)
- Other modules (`test_climdex.py`, `test_knmi.py`, `test_plots.py`, `test_rai.py`, `test_spi_mspi.py`, `test_statistical_refactor.py`, `test_validate.py`, `test_version.py`)

**Execution Status:**  
```bash
pytest
======================== 265 passed in 98.42s ========================
```

---

## 6. How to Use the Operational Modes

### Mode 1 — Wang Replication (Scientific Benchmark)
```python
import spei as si
from scipy.stats import gamma

spi_wang = si.spi(
    rolled_10["34010701a"],
    dist=gamma,
    prob_zero=True,
    fit_freq="D",
    all_zero_policy="wang",
    fitting_policy="wang",
)
```

### Mode 2 — Automated Distribution Selection (`SI.select_optimal_distribution`)
```python
from spei.si import SI
from scipy.stats import gamma

si = SI(
    rolled_10["34010701a"],
    dist=gamma,
    timescale=0,
    fit_freq="D",
    prob_zero=True,
)

# Run distribution selection across calendar groups without mutating si.dist
selection = si.select_optimal_distribution(
    candidates=None,             # Default: 7 standard distributions
    prefer_two_parameters=True,  # Parsimony tie-breaker within competitive set
    delta_aic_threshold=2.0,     # Burnham & Anderson (2002)
    ranking_method="hierarchical", # or "consensus_rank"
)

print(f"Best distribution: {selection['best_distribution']}")
print(f"Alternative distribution: {selection['alternative_distribution']}")
print(f"Status: {selection['best_selection_status']}")
```

### Mode 3 — Operational Daily SPI (Strict Baseline)
```python
import spei as si
from scipy.stats import gamma  # or weibull_min / pearson3

spi_operational = si.spi(
    rolled_10["34010701a"],
    dist=gamma,
    prob_zero=True,
    fit_freq="D",
    all_zero_policy="wang",
    fitting_policy="standard",
    small_sample_policy="strict",
)
```

### Mode 4 — Operational BMKG Dasarian (36-Dekad) SPI (Direct Ingestion & Pre-Rolled)
```python
import spei as si
from scipy.stats import gamma, weibull_min

# Direct daily series input: timescale=30 maps automatically to 3 dasarians (~30 days / 1 month)
# Automatically aggregates daily observations to BMKG standard 36-dekad calendar (days 1, 11, 21)
spi_dasarian_3 = si.spi(
    s_daily,
    dist=gamma,
    timescale=30,          # or timescale=3 (dasarians)
    fit_freq="dekad",      # or "dasarian"
    prob_zero=True,
)

# Pre-aggregated / pre-rolled dasarian input: timescale=0 preserves pre-rolled sums
data_dasarian = si.to_dasarian(s_daily, min_valid_days=1)
rolled_3das = si.rolling_dasarian(data_dasarian, timescale=30)
spi_pre_rolled_das = si.spi(
    rolled_3das,
    dist=weibull_min,
    timescale=0,           # Pre-accumulated dasarian series
    fit_freq="dekad",
    prob_zero=True,
)
```

### Mode 5 — Operational Monthly SPI from Daily Data (Direct Ingestion)
```python
import spei as si
from scipy.stats import gamma

# Direct daily series input: timescale=90 maps automatically to 3 calendar months (SPI-3)
spi_monthly_3 = si.spi(
    s_daily,
    dist=gamma,
    timescale=90,          # or timescale=3 (months)
    fit_freq="monthly",    # Automatically aggregates daily -> monthly totals
    prob_zero=True,
)

# Pre-accumulated monthly input: timescale=0 preserves pre-rolled sums
spi_pre_rolled = si.spi(
    s_monthly_rolled,
    dist=gamma,
    timescale=0,           # Pre-accumulated series
    fit_freq="monthly",
    prob_zero=True,
)
```



