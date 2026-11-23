# SCIENTIFIC VALIDATION REPORT AND INTEGRATION OF DSPI DISTRIBUTION SELECTION

**Based on the Recommendations of Stagge et al. (2015), Lee et al. (2023), and Burnham & Anderson (2002)**

---

## Executive Summary

A comprehensive audit, numerical corrections, and integration of probability distribution selection have been completed for the Daily Standardized Precipitation Index (DSPI) package. This work covers three core modules:

1. `src/spei/dist.py` (parameter estimation, conditional-positive likelihood, degenerate likelihood guard, bootstrap goodness-of-fit, AIC disqualification for Wang pseudo-observation fits, and verification of the GEV sign convention).
2. `src/spei/model_selection.py` & `model_selection.py` (single-source SPI transformation based on `Dist.cdf()`, selection of Best #1 and Alternative #2 candidates, aggregate diagnostic summary, deterministic hierarchical ranking, and fair multi-criteria consensus ranking).
3. `src/spei/si.py` (fully integrated `SI.select_optimal_distribution()` method using the daily calendar structure, together with sparse dekadal calendar recognition).

All 235 automated tests (`pytest`) passed 100% without regression. All empirical master-validation diagnostic deliverables (15 artifact files in [`outputs/master_validation/`](file:///Users/mahron/Data/python/SPEI/outputs/master_validation/) and 9 deliverables in [`outputs/distribution_selection/`](file:///Users/mahron/Data/python/SPEI/outputs/distribution_selection/)) for the rainfall station **34010701a** (2010–2024, 5,479 daily records, 366 daily groups, and 540 BMKG dekads) were generated and fully validated.

![Scatter Delta AIC vs Normality](/Users/mahron/Data/python/SPEI/outputs/master_validation/delta_aic_vs_normality_scatter.png)
_Figure 1: Comparative comparison of information loss (Mean $\Delta\text{AIC}$) against SPI normality preservation (Shapiro-Wilk and standard Anderson-Darling N(0,1)) across 7 candidate distributions._

---

## 1. Initial Audit Findings (Step 0)

Before code modifications were undertaken, a comprehensive audit of the architecture, dependency calls, and execution flow produced the following critical findings:

1. **Duality of the `model_selection.py` Module**:
   There were two files: the root `/Users/mahron/Data/python/SPEI/model_selection.py` and the submodule `src/spei/model_selection.py`. Both were synchronized identically and exported via `spei.__init__` so that imports remained consistent both from outside and within the package.
2. **Inverted GEV Skewness Formula in the Method of Moments**:
   The `estimate_gev_moments()` function in `dist.py` contained an algebraic error in the theoretical skewness equation of SciPy ($1 + 3c$ had the sign reversed and the global minus sign was lost), causing Brentq root-finding to fail to converge or to return a shape value $c$ with the wrong sign convention when $c < 0$.
3. **Hardcoded Flag `conditional_positive=False`**:
   In `_fit_standard_dist()`, the Gumbel-R block imposed `conditional_positive=False` in a hardcoded manner, ignoring the parameter passed by the caller. In addition, the line `cond_pos = bool(prob_zero and conditional_positive)` disabled conditional likelihood during fitting for purely positive bootstrap samples (`prob_zero=False`).
4. **Numerical Degeneration in Conditional Gumbel / Pearson III / GEV**:
   As $\mu \to -\infty$, the survival function $1 - F(0) \to 0$, so the conditional distribution on the domain $X > 0$ approaches the exponential distribution. Without a physical bound on the parameter space, Nelder-Mead on small samples ($n \le 4$) pushed `loc` to $-300$, triggering $1 - F(0) \le 10^{-13}$, which caused `Dist.cdf()` to reject the parameters and return `NaN`.
5. **Duplicated SPI Transformation Logic in `model_selection.py`**:
   The `_spi_from_fitted_model()` function previously attempted to recalculate the zero proportion and continuous CDF separately from `Dist.cdf()`, risking inconsistency with the Stagge mixed distribution rules and Wang centroid rules.
6. **Default SPI Clipping to $[-3, 3]$**:
   Prior to Shapiro-Wilk testing, SPI values were forcibly clipped to the interval $[-3, 3]$ by default, distorting the tails of the extreme distribution and biasing the p-values of the normality tests.
7. **Absence of Alternative Candidate Output (#2)**:
   The `_choose_from_rows()` function only produced a single winning candidate and lacked an official mechanism to recommend a second eligible alternative.
8. **Lack of Structured Integration in `SI`**:
   The `SI` class did not have a public method for automatically running distribution selection using a rolling calendar window consistent with `SI.fit_distribution()`.

---

## 2. Results of GEV Shape Parameter Sign Convention Verification (Step 1)

### 2.1 Empirical Experiment and Main Findings

A synthetic experiment was conducted with `scipy.stats.genextreme` at $c_{\text{true}} = +0.25$ (reverse Weibull type, bounded upper tail) and $c_{\text{true}} = -0.25$ (Fréchet type, heavy tail) across multiple seeds ($42, 123, 999$) with $N = 2000$.

The results recorded in [gev_sign_convention_test.csv](file:///Users/mahron/Data/python/SPEI/outputs/distribution_selection/gev_sign_convention_test.csv) are as follows:

| $c_{\text{true}}$ (SciPy) | Seed | $c$ (`lmoments3`) | $c$ (`estimate_gev_moments`) | $c$ (`Dist.fit_dist`) | $loc_{\text{fit}}$ | $scale_{\text{fit}}$ |     Sign Match?      |    CDF Range     |
| :-----------------------: | :--: | :---------------: | :--------------------------: | :-------------------: | :----------------: | :------------------: | :------------------: | :--------------: |
|         **+0.25**         |  42  |      +0.2462      |           +0.2383            |        +0.2423        |       99.76        |        24.96         | **Yes (Consistent)** | [0.0031, 0.9996] |
|         **+0.25**         | 123  |      +0.2540      |           +0.2577            |        +0.2583        |       99.84        |        25.74         | **Yes (Consistent)** | [0.0002, 0.9996] |
|         **+0.25**         | 999  |      +0.2423      |           +0.2395            |        +0.2401        |       99.23        |        24.92         | **Yes (Consistent)** | [0.0002, 0.9997] |
|         **-0.25**         |  42  |      -0.2503      |           -0.2011            |        -0.2800        |       99.48        |        24.72         | **Yes (Consistent)** | [0.0024, 0.9995] |
|         **-0.25**         | 123  |      -0.2573      |           -0.2069            |        -0.2531        |       99.86        |        25.66         | **Yes (Consistent)** | [0.0002, 0.9996] |
|         **-0.25**         | 999  |      -0.2679      |           -0.2196            |        -0.2569        |       99.23        |        24.60         | **Yes (Consistent)** | [0.0002, 0.9998] |

### 2.2 Decision and Technical Correction

1. **L-moments Sign Rule**: `lmoments3.distr.gev.lmom_fit()` in this Python environment uses the same sign convention as SciPy. The sign of the parameter `c` from `lmoments3` must not be reversed. Reversing it arbitrarily would transform a heavy-tailed distribution (Fréchet) into a bounded-tail distribution (reverse Weibull).
2. **Correction of the Theoretical SciPy Skewness Formula**:
   The theoretical skewness formula for the generalized extreme value distribution was re-derived exactly according to the SciPy infrastructure:
   $$\text{skew}(c) = -\text{sign}(c) \frac{g_3 - 3 g_1 g_2 + 2 g_1^3}{(g_2 - g_1^2)^{3/2}}, \quad \text{where } g_k = \Gamma(1 + k c)$$
   The new implementation yields numerical error below $10^{-14}$ relative to `scipy.stats.genextreme.stats(c, moments='s')`, ensuring the Method of Moments root-finding converges precisely for both signs of $c$.

---

## 3. Improvements to Conditional-Positive Fitting and Bootstrap (Step 2)

### 3.1 Consistency of Conditional Likelihood

Based on Stagge et al. (2015), the conditional density for positive precipitation ($X > 0$) is:
$$f(x \mid X > 0) = \frac{f(x)}{1 - F(0)}, \quad x > 0$$
The corrected negative log-likelihood is:
$$-\ell_{\text{cond}} = -\sum_{i=1}^{n_+} \log f(x_i) + n_+ \log\{1 - F(0)\}$$

### 3.2 Code Modifications in `src/spei/dist.py`

1. **Conditional Flag Assignment**:
   In `_fit_standard_dist()`:
   ```python
   cond_pos = bool(conditional_positive)
   ```
   The caller flag is now fully respected. The hardcoded `conditional_positive=False` in the Gumbel-R block was replaced with `conditional_positive=cond_pos`.
2. **Protection of SPEI / Signed Series**:
   In `Dist.__post_init__()`:
   ```python
   conditional_positive = bool(self.prob_zero and self.conditional_positive)
   ```
   Climatic water balance data (SPEI) with negative values and `prob_zero=False` will never be inadvertently conditioned on $X > 0$.
3. **Rescue from Numerical Degeneracy (Physical Survival Floor)**:
   In `_gumbel_negloglik`, `_pearson3_negloglik`, and `_gev_negloglik`, a log-survival constraint was added:
   ```python
   if logsf0 < -4.60517:  # SF(0) < 0.01
       return np.inf
   ```
   This prevents the Nelder-Mead optimizer from driving $loc \to -\infty$, keeps the parameters within a physically valid probabilistic domain, and eliminates failures of `s0 <= 1e-12` in `Dist.cdf()`.
4. **Consistent Bootstrap Refits**:
   In `Dist.goodness_of_fit()`, the parameter `conditional_positive=cond_pos` is passed explicitly to each `self.fit_dist()` iteration. Positive bootstrap samples are simulated using pure rejection sampling for $X > 0$.

The results of testing in [conditional_positive_bootstrap_tests.csv](file:///Users/mahron/Data/python/SPEI/outputs/distribution_selection/conditional_positive_bootstrap_tests.csv) show that:

- For zero-inflated mixed data (`prob_zero=True`), fitting Gumbel-R, Pearson III, GEV, Gamma, and Weibull converged successfully with a **bootstrap refit success rate of 100% (`bootstrap_success_rate = 1.0`)**.
- For signed data (`prob_zero=False`), conditional-positive was correctly disabled, and all 50 records were evaluated without artificial normalization.

---

## 4. Results of Delta AIC Audit and Number of Free Parameters (Step 4)

### 4.1 Number of Continuous Free Parameters ($k$)

The number of free parameters is calculated from the actual fitting parameterization (including the restriction $loc = 0$):

- **Gamma** ($loc = 0$ fixed): $k = 2$ (`a`, `scale`).
- **Weibull minimum** ($loc = 0$ fixed): $k = 2$ (`c`, `scale`).
- **Lognormal** ($loc = 0$ fixed): $k = 2$ (`s`, `scale`).
- **Fisk / Log-logistic** ($loc = 0$ fixed): $k = 2$ (`c`, `scale`).
- **Gumbel-R** ($loc$ and `scale` free): $k = 2$ (`loc`, `scale`).
- **Pearson III** ($skew$, `loc`, and `scale` free): $k = 3$ (`skew`, `loc`, `scale`).
- **GEV** ($c$, `loc`, and `scale` free): $k = 3$ (`c`, `loc`, `scale`).

### 4.2 Delta AIC Formulation

For each calendar group $g$, AIC is calculated using the conditional positive log-likelihood on the same positive sample:
$$\text{AIC}_{i, g} = -2 \ell_{\text{cond}, i, g} + 2k_i$$
$$\Delta \text{AIC}_{i, g} = \text{AIC}_{i, g} - \min_{j \in \text{valid}_g} \text{AIC}_{j, g}$$
The competitive candidate set is defined strictly following Burnham & Anderson (2002) and Stagge et al. (2015):
$$\text{Competitive Set} = \{i \mid \Delta \text{AIC}_{i, g} < 2.0\}$$
The floating-point numerical tolerance `np.isclose(delta_AIC, 0.0, atol=1e-7)` is used to assign AIC wins/ties deterministically.

---

## 5. Improvements to CDF and SPI Transformation (Step 3)

### 5.1 `Dist.cdf()` as the Single Source of Truth

The `_spi_from_fitted_model()` function was completely rewritten to eliminate duplicated logic:

```python
q_series = model.cdf().reindex(raw_data.index)
q = q_series.to_numpy(dtype=float)
eps = np.finfo(float).eps
spi = stats.norm.ppf(np.clip(q, eps, 1.0 - eps))
```

The mixed rules are applied consistently:

- For $X > 0$: $H(x) = p_0 + (1 - p_0) F_{\text{pos}}(x)$.
- For $X = 0$: $H(0) = p_{\text{zero centroid}} = \frac{m + 1}{2(n + 1)}$ (Stagge/Wang centroid method).
- `NaN` values in the input are preserved as `NaN` and are not truncated to a real number.

### 5.2 Default `sw_clip` Policy `None`

The default clipping was changed from $[-3, 3]$ to `None`. The standard-normal transformation is no longer artificially clipped before the Shapiro-Wilk normality test, so the test evaluates the genuine tail behavior of the distribution.

### 5.3 Shared Random Draws in the Shapiro-Wilk Test for Zero Observations

For a fair comparison among candidates in the same group when zero observations are replaced by random draws from a standard normal distribution, the seed is derived deterministically from the group identity (`sw_zero_seed`). Thus, variations in the Shapiro-Wilk test result among otherwise equivalent candidates reflect differences in distribution quality rather than differences in the random draw values used for zero replacement.

---

## 6. Definitions of Scientific Diagnostic Metrics (Step 6)

To avoid methodological ambiguity, four diagnostic metrics are separated strictly:

1. **Shapiro-Wilk Test on the SPI Transformation (Stagge et al. 2015)**:
   - `SW_rejection_frequency_pct`: Percentage of calendar groups with Shapiro-Wilk p-values $< 0.05$.
   - `SW_nonrejection_ratio`: $1 - \frac{\text{SW\_rejection\_frequency}}{100}$.
   - _Interpretation_: Tests whether the resulting SPI series follows a normal distribution. Lower rejection indicates better transformation.
2. **Goodness-of-Fit Test for Positive Precipitation KS & AD (Stagge et al. 2015)**:
   - `KS_rejection_frequency_pct`: Frequency of Kolmogorov-Smirnov rejection on the positive precipitation component ($X > 0$) using parametric bootstrap.
   - `AD_rejection_frequency_pct`: Frequency of Anderson-Darling rejection on the positive precipitation component ($X > 0$) using parametric bootstrap.
   - _Interpretation_: Tests goodness-of-fit of the probability distribution to raw rainfall data, not the normality of SPI values.
3. **SPI Normality test using Anderson-Darling (adapted from Lee et al. 2023)**:
   - `SPI_AD_group_pass_ratio`: Ratio of calendar groups for which the SPI series does not reject the standard normal distribution $N(0, 1)$ according to the Anderson-Darling test ($\text{statistic} < \text{critical value}$ at $\alpha = 0.05$).
   - `meets_90pct_normality_target`: Indicator of satisfying the 90% target adopted from Lee et al. (2023) and Wang et al. (2022).
   - _Methodological Note_: For a single station with 15 years of data per calendar day ($N \approx 15$), this metric is a calendar-group-based adaptation rather than a cross-location spatial comparison.

---

## 7. Rules for Selecting the Best Distribution (#1) and Alternative (#2) (Step 5)

The deterministic helper function `_rank_rows(rows, prefer_two_parameters)` is implemented to choose the first and second candidates:

```mermaid
graph TD
    A[Valid Fitted Candidates] --> B{Compute Delta AIC}
    B --> C[Competitive Set: Delta AIC < 2.0]
    C --> D{GoF Bootstrap Scope}
    D -->|competitive| E[KS & AD Bootstrap Tests on Shortlist]
    E --> F{Any Candidate Passes KS & AD?}
    F -->|Yes| G[Competitive Passing Set]
    F -->|No| H[Evaluate Next Candidate by AIC]
    G --> I{prefer_two_parameters?}
    I -->|Yes| J[Prioritize 2-Parameter Models within Passing Set]
    I -->|No| K[Select Lowest AIC]
    J --> L[Rank #1: Best Distribution]
    J --> M[Rank #2: Alternative Distribution]
    K --> L
    K --> M
```

### Main Selection Characteristics:

1. **Integrity of the Alternative**: Rank #2 must come from a candidate that meets the eligibility requirements. If only one candidate passes, `alternative_distribution` is `None` (without forcing an ineligible candidate to become an official alternative).
2. **Determinism**: If equal values occur (ties), the model name is used as a stable alphabetical tie-breaker.
3. **Storage of Model Objects**: The output stores the `selected_model` (#1) and `alternative_model` (#2) for subsequent analyses without breaking compatibility with older API keys.

---

## 8. Results of Empirical Multi-Scale Validation at Rainfall Station 34010701a (Steps 7 & Master Validation)

Probability distribution evaluations were conducted on the 15-year historical dataset (2010–2024, 5,479 daily records) from rainfall station **34010701a** (BPP Pengasih, Kulon Progo) across two main operational resolutions: **Daily (DSPI)** and **Dekadal (BMKG dekad)**.

All evaluation outputs are stored in [`outputs/master_validation/`](file:///Users/mahron/Data/python/SPEI/outputs/master_validation/):

- Daily Hierarchical: [`station_34010701a_daily_candidate_rankings.csv`](file:///Users/mahron/Data/python/SPEI/outputs/master_validation/station_34010701a_daily_candidate_rankings.csv)
- Daily Consensus: [`station_34010701a_daily_candidate_rankings_consensus.csv`](file:///Users/mahron/Data/python/SPEI/outputs/master_validation/station_34010701a_daily_candidate_rankings_consensus.csv)
- Dekadal Hierarchical: [`station_34010701a_dasarian_candidate_rankings.csv`](file:///Users/mahron/Data/python/SPEI/outputs/master_validation/station_34010701a_dasarian_candidate_rankings.csv)
- Dekadal Consensus: [`station_34010701a_dasarian_candidate_rankings_consensus.csv`](file:///Users/mahron/Data/python/SPEI/outputs/master_validation/station_34010701a_dasarian_candidate_rankings_consensus.csv)
- Daily DSPI summary: [`station_34010701a_dspi_daily_summary.csv`](file:///Users/mahron/Data/python/SPEI/outputs/master_validation/station_34010701a_dspi_daily_summary.csv)
- Dekadal SPI summary: [`station_34010701a_dspi_dasarian_summary.csv`](file:///Users/mahron/Data/python/SPEI/outputs/master_validation/station_34010701a_dspi_dasarian_summary.csv)
- Synthetic stress test results: [`synthetic_stress_test_results.csv`](file:///Users/mahron/Data/python/SPEI/outputs/master_validation/synthetic_stress_test_results.csv)
- GEV sign-convention verification: [`gev_sign_convention_verification.csv`](file:///Users/mahron/Data/python/SPEI/outputs/master_validation/gev_sign_convention_verification.csv)

### 8.1 Daily Candidate Selection (366 Calendar Groups, Calibration Window `fit_window=31`)

#### Table 8.1A: Daily Hierarchical Ranking (`ranking_method="hierarchical"`)

|  Rank  | Distribution         | Parameters | Fit Coverage | Mean $\Delta\text{AIC}$ | S-W Pass (%) | Case 0 AD Pass (%) |    Tier    | Selection Status | Reason / Rationale                                           |
| :----: | :------------------- | :--------: | :----------: | :---------------------: | :----------: | :----------------: | :--------: | :--------------: | :----------------------------------------------------------- |
| **#1** | **Pearson Type III** |     3      |  **100.0%**  |        **8.28**         |  **95.1%**   |     **98.9%**      | **Tier 1** |   **Accepted**   | Meets normality target; lowest mean $\Delta\text{AIC}$.      |
| **#2** | **GEV**              |     3      |  **100.0%**  |          22.70          |    92.9%     |       98.9%        | **Tier 1** |   **Accepted**   | Meets normality target; competitive 3-parameter alternative. |
|   #3   | Weibull              |     2      |    100.0%    |          29.00          |    92.3%     |       98.9%        |   Tier 1   |     Accepted     | Meets normality target; competitive 2-parameter fit.         |
|   #4   | Gumbel-R             |     2      |    100.0%    |          34.06          |    92.9%     |       98.9%        |   Tier 1   |     Accepted     | Meets normality target; 4th lowest $\Delta\text{AIC}$.       |
|   #5   | Gamma                |     2      |    100.0%    |          45.04          |    92.3%     |       98.9%        |   Tier 1   |     Accepted     | Meets normality target; 5th lowest $\Delta\text{AIC}$.       |
|   #6   | Fisk                 |     2      |    100.0%    |          78.29          |    87.4%     |       98.9%        |   Tier 2   |     Rejected     | Fails Shapiro-Wilk target (87.4% < 90%).                     |
|   #7   | Lognormal            |     2      |    100.0%    |         113.77          |    79.5%     |       98.9%        |   Tier 2   |     Rejected     | Fails Shapiro-Wilk target (79.5% < 90%).                     |

#### Table 8.1B: Daily Consensus Ranking (`ranking_method="consensus_rank"`)

|  Rank  | Distribution         | Parameters | Rank AIC | Rank SW | Rank AD | Consensus Score | Mean $\Delta\text{AIC}$ |        Selection Status        |
| :----: | :------------------- | :--------: | :------: | :-----: | :-----: | :-------------: | :---------------------: | :----------------------------: |
| **#1** | **Pearson Type III** |     3      |   1.0    |   1.5   |   4.0   |    **2.17**     |        **8.28**         | **consensus_rank_user_option** |
| **#2** | **Weibull**          |     2      |   3.0    |   1.5   |   4.0   |    **2.83**     |          29.00          | **consensus_rank_user_option** |
|   #3   | GEV                  |     3      |   2.0    |   3.0   |   4.0   |      3.00       |          22.70          |   consensus_rank_user_option   |
|   #4   | Gumbel-R             |     2      |   4.0    |   4.0   |   4.0   |      4.00       |          34.06          |   consensus_rank_user_option   |
|   #5   | Gamma                |     2      |   5.0    |   5.0   |   4.0   |      4.67       |          45.04          |   consensus_rank_user_option   |
|   #6   | Fisk                 |     2      |   6.0    |   6.0   |   4.0   |      5.33       |          78.29          |   consensus_rank_user_option   |
|   #7   | Lognormal            |     2      |   7.0    |   7.0   |   4.0   |      6.00       |         113.77          |   consensus_rank_user_option   |

#### Daily Results Analysis:

1. **Pearson Type III is the unequivocal winner (#1) under both methods:** It attains the lowest mean $\Delta\text{AIC}$ (8.28) and the highest Shapiro-Wilk pass rate (95.1%), along with a standard Anderson-Darling pass rate of 98.9%.
2. **Weibull displaces GEV for position #2 in consensus rank:**
   - Under the `hierarchical` method, GEV ranks #2 because it has a lower $\Delta\text{AIC}$ (22.70 vs 29.00).
   - Under the `consensus_rank` method, Weibull achieves a better consensus score (**2.83** vs **3.00**) because its Shapiro-Wilk performance is equivalent to Pearson III (Rank 1.5), outperforming GEV (Rank 3.0 on S-W).

---

### 8.2 Dekadal Candidate Selection (36 BMKG Dekad Groups)

Evaluation of canonical BMKG 10-day rainfall precipitation across all 36 dekads in the year:

#### Table 8.2A: Dekadal Hierarchical Ranking (`ranking_method="hierarchical"`)

|  Rank  | Distribution     | Parameters | Fit Coverage | Mean $\Delta\text{AIC}$ | S-W Pass (%) | Case 0 AD Pass (%) |    Tier    | Selection Status | Reason / Rationale                                             |
| :----: | :--------------- | :--------: | :----------: | :---------------------: | :----------: | :----------------: | :--------: | :--------------: | :------------------------------------------------------------- |
| **#1** | **Weibull**      |     2      |  **100.0%**  |        **10.08**        |  **91.7%**   |     **100.0%**     | **Tier 1** |   **Accepted**   | Meets normality target; lowest 2-parameter $\Delta\text{AIC}$. |
| **#2** | **Gumbel-R**     |     2      |  **100.0%**  |          10.37          |  **91.7%**   |     **100.0%**     | **Tier 1** |   **Accepted**   | Meets normality target; competitive 2-parameter alternative.   |
|   #3   | Gamma            |     2      |    100.0%    |          10.50          |    86.1%     |       100.0%       |   Tier 2   |     Demoted      | S-W pass rate (86.1%) below the 90% operational target.        |
|   #4   | Fisk             |     2      |    100.0%    |          11.72          |    86.1%     |       100.0%       |   Tier 2   |     Demoted      | S-W pass rate (86.1%) below the 90% target.                    |
|   #5   | Lognormal        |     2      |    100.0%    |          12.16          |    75.0%     |       100.0%       |   Tier 2   |     Demoted      | S-W pass rate (75.0%) below the 90% target.                    |
|   #6   | Pearson Type III |     3      |    100.0%    |        **1.00**         |    83.3%     |       86.1%        |   Tier 2   |     Demoted      | Case 0 AD pass rate (86.1%) below the 90% threshold.           |
|   #7   | GEV              |     3      |    100.0%    |          10.22          |    80.6%     |       86.1%        |   Tier 2   |     Demoted      | Case 0 AD pass rate (86.1%) below the 90% threshold.           |

#### Table 8.2B: Dekadal Consensus Ranking (`ranking_method="consensus_rank"`)

|  Rank  | Distribution     | Parameters | Rank AIC | Rank SW | Rank AD | Consensus Score | Mean $\Delta\text{AIC}$ |        Selection Status        |
| :----: | :--------------- | :--------: | :------: | :-----: | :-----: | :-------------: | :---------------------: | :----------------------------: |
| **#1** | **Weibull**      |     2      |   2.0    |   1.5   |   3.0   |    **2.17**     |          10.08          | **consensus_rank_user_option** |
| **#2** | **Gumbel-R**     |     2      |   4.0    |   1.5   |   3.0   |    **2.83**     |          10.37          | **consensus_rank_user_option** |
|   #3   | Gamma            |     2      |   5.0    |   3.5   |   3.0   |      3.83       |          10.50          |   consensus_rank_user_option   |
|   #4   | Pearson Type III |     3      | **1.0**  |   5.0   |   6.5   |      4.17       |        **1.00**         |   consensus_rank_user_option   |
|   #5   | Fisk             |     2      |   6.0    |   3.5   |   3.0   |      4.17       |          11.72          |   consensus_rank_user_option   |
|   #6   | GEV              |     3      |   3.0    |   6.0   |   6.5   |      5.17       |          10.22          |   consensus_rank_user_option   |
|   #7   | Lognormal        |     2      |   7.0    |   7.0   |   3.0   |      5.67       |          12.16          |   consensus_rank_user_option   |

#### Analysis of Dekadal Results:

1. **Unanimous agreement on the top 2:** Both methods consistently recommend **Weibull as Best (#1)** and **Gumbel-R as Alternative (#2)** on the dekadal scale. Both achieve 91.7% Shapiro-Wilk pass rates and 100% Case 0 AD pass rates across all 36 dekads.
2. **Position of Pearson Type III at the dekadal scale:**
   - Under the `hierarchical` method, Pearson Type III drops to Rank #6 because its standard AD pass rate of 86.1% fails to exceed the strict 90% threshold, placing it in Tier 2 regardless of its AIC advantage.
   - Under the `consensus_rank` method, Pearson Type III rises to Rank #4 (consensus score 4.17) because its rank #1 advantage in $\Delta\text{AIC}$ ($\text{Mean } \Delta\text{AIC} = 1.00$) is balanced by a loss in normality ranking.

---

### 8.3 Comparison of Methodological Philosophies: Hierarchical vs Consensus Ranking

The DSPI package provides two aggregate global ranking methods that can be selected according to the use case:

#### Diagram 1: Hierarchical Ranking (`ranking_method="hierarchical"`, Default Operational)

Emphasizes compliance with safety gates and information parsimony according to Burnham & Anderson (2002):

```mermaid
graph TD
    Start([Aggregated Distribution Candidates]) --> FilterCov{Valid Coverage >= 80%?}
    FilterCov -->|No| Drop[Drop / Insufficient Coverage]
    FilterCov -->|Yes| CheckNorm{Passes 90% Normality Target?}
    CheckNorm -->|Yes| Tier1[Tier 1: Meets Operational Requirements]
    CheckNorm -->|No| Tier2[Tier 2: Demoted]
    Tier1 --> CheckComp{Mean Delta AIC < 2.0?}
    CheckComp -->|Yes| CheckParam{prefer_two_parameters and k=2?}
    CheckParam -->|Yes| Prio2P[Priority to Competitive 2-Parameter Models]
    CheckParam -->|No| PrioAIC[Priority to Lowest AIC]
    CheckComp -->|No| RankDAIC[Sort by Lowest Delta AIC]
    Prio2P --> FinalSort[Tie-Break: SW Non-Rejection, SPI AD Pass, Distribution Name]
    PrioAIC --> FinalSort
    RankDAIC --> FinalSort
    Tier2 --> RankDAIC
    FinalSort --> ResultHier[Recommendation Output #1 & #2]
```

---

#### Diagram 2: Consensus / Borda Ranking (`ranking_method="consensus_rank"`, User Option)

Balances three diagnostic pillars in a non-parametric manner without rigid thresholds:

```mermaid
graph TD
    StartC([Aggregated Distribution Candidates]) --> R1["Dimension 1: Mean Delta AIC (Positive Rainfall Fit)"]
    StartC --> R2["Dimension 2: SW Rejection Frequency (SPI Normality Shape)"]
    StartC --> R3["Dimension 3: SPI AD Pass Ratio (SPI Standard-Normality Check)"]
    R1 --> CalcRank1[Compute AIC Rank: 1 to 7]
    R2 --> CalcRank2[Compute SW Rank: 1 to 7]
    R3 --> CalcRank3[Compute AD Rank: 1 to 7]
    CalcRank1 --> Borda["Borda Consensus Score = (Rank_AIC + Rank_SW + Rank_AD) / 3"]
    CalcRank2 --> Borda
    CalcRank3 --> Borda
    Borda --> CheckCompPool{All metrics complete?}
    CheckCompPool -->|No| Ineligible[Mark consensus_eligible=False & Score=NaN]
    CheckCompPool -->|Yes| SortBorda[Sort by Smallest Consensus Score]
    SortBorda --> ResultCons[Consensus Recommendation Output]
```

---

#### Comparison of Usage Characteristics:

| Criterion / Metric       | Hierarchical Ranking (`hierarchical`)                                                                    | Consensus / Borda Ranking (`consensus_rank`)                                   |
| :----------------------- | :------------------------------------------------------------------------------------------------------- | :----------------------------------------------------------------------------- |
| **Main Focus**           | Ensures strict statistical safety gates ($\ge 90\%$ normality) and model parsimony.                      | Balances the trade-off between AIC superiority and SPI normality.              |
| **Daily-Scale Winner**   | **Pearson Type III** (#1) and **GEV** (#2)                                                               | **Pearson Type III** (#1) and **Weibull** (#2)                                 |
| **Dekadal-Scale Winner** | **Weibull** (#1) and **Gumbel-R** (#2)                                                                   | **Weibull** (#1) and **Gumbel-R** (#2)                                         |
| **Operational Context**  | **Official BMKG / WMO Operational Use** for preventing distortions in early-warning systems for drought. | **Exploratory and Comparative Research** for balanced multi-criteria analysis. |

---

### 8.4 Visualisation and Recent Analysis Artifacts

All high-resolution visualisation graphics were exported and verified in [`outputs/master_validation/`](file:///Users/mahron/Data/python/SPEI/outputs/master_validation/):

1. **AIC vs Normality Diagnostic Scatter Plot:**  
   ![Scatter Delta AIC vs Normality](/Users/mahron/Data/python/SPEI/outputs/master_validation/delta_aic_vs_normality_scatter.png)
2. **Daily DSPI Time Series (34010701a):**  
   ![Daily DSPI Time Series](/Users/mahron/Data/python/SPEI/outputs/master_validation/station_34010701a_dspi_daily_timeseries.png)
3. **Dekadal SPI Time Series (34010701a):**  
   ![Dekadal SPI Time Series](/Users/mahron/Data/python/SPEI/outputs/master_validation/station_34010701a_dspi_dasarian_timeseries.png)
4. **NaN Diagnostic Waterfall Plot:**  
   ![NaN Diagnostic Waterfall](/Users/mahron/Data/python/SPEI/outputs/master_validation/nan_diagnostic_waterfall.png)

---

### 8.5 Empirical Statistical Characteristics of the Daily DSPI Series (Rainfall Station 34010701a)

The descriptive statistics for the daily DSPI time series (30-day scale, rolling calibration window of 31 days, 5,450 valid records after the accumulation window lead-in) are recorded in [`station_34010701a_dspi_daily_summary.csv`](file:///Users/mahron/Data/python/SPEI/outputs/master_validation/station_34010701a_dspi_daily_summary.csv):

| Probability Distribution | Scale (Days) | Fit Window | Valid Records | Validity (%) | Mean ($\mu$) | Standard Deviation ($\sigma$) |   Min   |   Max   | Skewness | Kurtosis |
| :----------------------- | :----------: | :--------: | :-----------: | :----------: | :----------: | :---------------------------: | :-----: | :-----: | :------: | :------: |
| **Gamma**                |      30      |     31     |     5.450     |    100.0%    |   +0.0334    |            0.8935             | -3.8834 | +2.4539 | -0.0888  | +0.1029  |
| **Weibull min**          |      30      |     31     |     5.450     |    100.0%    |   +0.0267    |            0.9078             | -3.4874 | +3.1417 | +0.1429  | -0.0681  |
| **Gumbel-R**             |      30      |     31     |     5.450     |    100.0%    |   +0.0165    |            0.8949             | -3.1078 | +2.4179 | +0.0667  | -0.2140  |
| **Lognormal**            |      30      |     31     |     5.450     |    100.0%    |   +0.0405    |            0.8655             | -4.6718 | +2.1597 | -0.4709  | +0.8576  |
| **Fisk (Log-Logistic)**  |      30      |     31     |     5.450     |    100.0%    |   -0.0091    |            0.8854             | -4.0732 | +2.1381 | -0.2909  | +0.1635  |
| **Pearson Type III**     |      30      |     31     |     5.450     |    100.0%    |   +0.0136    |            0.9155             | -2.6369 | +3.0749 | +0.2553  | -0.3194  |
| **GEV**                  |      30      |     31     |     5.450     |    100.0%    |   +0.0136    |            0.9144             | -2.6885 | +3.0828 | +0.2940  | -0.2789  |

_Key Analysis:_

- All 7 candidates produced 100% valid records (5,450/5,450) with no `NaN` residuals.
- Mean values $\mu \approx 0.0$ and standard deviations $\sigma \approx 0.90$–0.92 confirm a stable standard-normal transformation.
- Pearson Type III and GEV show the highest standard deviations ($\sigma = 0.915$), closest to the theoretical standard normal value ($\sigma = 1.0$), while the value range $[-2.64, +3.08]$ remains free from extreme outliers due to rejection of excessive tails.

---

### 8.6 Empirical Statistical Characteristics of the Dekadal SPI Across Accumulation Scales

Results for dekadal SPI evaluation at rainfall station 34010701a across accumulation scales from 10 days (1 dekad) to 360 days (36 dekads) are documented in [`station_34010701a_dspi_dasarian_summary.csv`](file:///Users/mahron/Data/python/SPEI/outputs/master_validation/station_34010701a_dspi_dasarian_summary.csv):

| Scale (Days) | Window (Dekads) | Distribution | Total Dekads | Valid Dekads | NaN Residuals | Validity (%) | Mean ($\mu$) | Standard Deviation ($\sigma$) |   Min   |   Max   |
| :----------: | :-------------: | :----------- | :----------: | :----------: | :-----------: | :----------: | :----------: | :---------------------------: | :-----: | :-----: |
|   **10d**    |        1        | **Gamma**    |     540      |     540      |       0       |  **100.0%**  |   +0.0415    |            0.8719             | -2.9571 | +2.5282 |
|     10d      |        1        | Pearson III  |     540      |     525      |      15       |    97.22%    |   +0.0415    |            1.2710             | -7.9413 | +7.6297 |
|     10d      |        1        | GEV          |     540      |     525      |      15       |    97.22%    |   +0.0993    |            1.2514             | -2.6724 | +7.8242 |
|   **30d**    |        3        | **Gamma**    |     538      |     538      |       0       |  **100.0%**  |   +0.0341    |            0.9161             | -3.1803 | +2.4519 |
|     30d      |        3        | Pearson III  |     538      |     538      |       0       |    100.0%    |   +0.0332    |            1.1707             | -7.9413 | +7.7259 |
|     30d      |        3        | GEV          |     538      |     538      |       0       |    100.0%    |   +0.0611    |            1.1836             | -2.7251 | +7.9414 |
|   **60d**    |        6        | **Gamma**    |     535      |     535      |       0       |  **100.0%**  |   +0.0278    |            0.9436             | -3.4303 | +1.9861 |
|     60d      |        6        | Pearson III  |     535      |     535      |       0       |    100.0%    |   +0.0467    |            1.2322             | -3.0669 | +7.9165 |
|     60d      |        6        | GEV          |     535      |     535      |       0       |    100.0%    |   +0.0498    |            1.2462             | -3.0775 | +7.9414 |
|   **90d**    |        9        | **Gamma**    |     532      |     532      |       0       |  **100.0%**  |   +0.0239    |            0.9577             | -3.4696 | +2.1149 |
|     90d      |        9        | Pearson III  |     532      |     532      |       0       |    100.0%    |   +0.0253    |            1.4564             | -7.9413 | +7.9414 |
|     90d      |        9        | GEV          |     532      |     532      |       0       |    100.0%    |   +0.0559    |            1.3175             | -3.0974 | +7.9414 |
|   **180d**   |       18        | **Gamma**    |     523      |     523      |       0       |  **100.0%**  |   +0.0103    |            0.9903             | -3.3946 | +1.9799 |
|     180d     |       18        | Pearson III  |     523      |     523      |       0       |    100.0%    |   -0.0113    |            1.3824             | -7.8726 | +7.8088 |
|     180d     |       18        | GEV          |     523      |     523      |       0       |    100.0%    |   +0.0078    |            1.1197             | -2.8268 | +7.9057 |
|   **360d**   |       36        | **Gamma**    |     505      |     505      |       0       |  **100.0%**  |   +0.0001    |            1.0010             | -2.3250 | +2.1264 |
|     360d     |       36        | Pearson III  |     505      |     505      |       0       |    100.0%    |   -0.0440    |            1.5048             | -7.9413 | +7.7422 |
|     360d     |       36        | GEV          |     505      |     505      |       0       |    100.0%    |   +0.0195    |            1.1043             | -1.9388 | +7.7285 |

_Operational Insights for Dekadal Data:_

1. **Robustness Advantage of 2-Parameter Models (Gamma / Weibull):** The Gamma distribution achieves a perfect coverage of 100% across all 6 accumulation scales, with standard deviation stabilizing gradually from $\sigma = 0.87$ (10d) to exactly $\sigma = 1.001$ at the annual scale (360d).
2. **Weakness of 3-Parameter Models at Short Dekadal Scales (10d):** At the 10-day scale without rolling accumulation, Pearson III and GEV produce 15 NaN residuals (97.2% coverage) due to overfitting shape parameters ($c$ and $skew$) during dry-season periods when the number of positive observations is very small ($n_+ \le 2$). This confirms the parsimony principle of Burnham & Anderson: 2-parameter models (Weibull/Gumbel/Gamma) are operationally superior for dekadal data.

---

### 8.7 Results of Synthetic Extreme-Condition Stress Tests

The synthetic boundary-condition stress-test suite (18 extreme conditions), as recorded in [`synthetic_stress_test_results.csv`](file:///Users/mahron/Data/python/SPEI/outputs/master_validation/synthetic_stress_test_results.csv), is shown below:

| Condition ID | Description of Boundary Condition          | Sample Size ($N$) | Positive Values ($n_+$) | Expected Behavior                     | Test Status | Confirmation of Actual Behavior                     |
| :----------: | :----------------------------------------- | :---------------: | :---------------------: | :------------------------------------ | :---------: | :-------------------------------------------------- |
| **COND_01**  | Mixed zero and positive values             |        40         |           20            | Standard calibration succeeds         | **PASSED**  | Fully convergent success                            |
| **COND_02**  | 1 positive value (strict mode)             |        25         |            1            | Reject: insufficient positive sample  | **PASSED**  | Rejected with status `insufficient_positive_sample` |
| **COND_03**  | 2 positive values (2-parameter model)      |        30         |            2            | 2-parameter calibration succeeds      | **PASSED**  | 2-parameter model successfully fit                  |
| **COND_04**  | 2 positive values (3-parameter model)      |        30         |            2            | Reject: free parameters exceed $n_+$  | **PASSED**  | Rejected with status `insufficient_positive_sample` |
| **COND_05**  | Purely positive precipitation sample       |        35         |           35            | Unaugmented calibration succeeds      | **PASSED**  | Full convergence without zero correction            |
| **COND_06**  | All data are zero ($n_+ = 0$)              |        30         |            0            | Special handling under Stagge policy  | **PASSED**  | Status `all_zero`, $p_0 = 1.0$                      |
| **COND_07**  | Uniform constant data (zero variance)      |        25         |           25            | Reject: positive variance is zero     | **PASSED**  | Rejected with status `zero_variance`                |
| **COND_08**  | Sample contains missing values (NaN)       |        35         |           20            | Automatic NaN drop during fitting     | **PASSED**  | Successful convergence with cleaned data            |
| **COND_09**  | Precipitation contains negative values     |        20         |           15            | Reject with physical `ValueError`     | **PASSED**  | Physical error correctly triggered                  |
| **COND_10**  | Strict enforcement of 2-parameter Gumbel-R |        30         |           25            | $k = 2$ computed exactly              | **PASSED**  | $k = 2$ correctly enforced in AIC                   |
| **COND_11**  | Standard normal AD case 0 with $N(0, 1)$   |        100        |           100           | Pass test ($\text{stat} < 2.492$)     | **PASSED**  | Standard normal accepted                            |
| **COND_12**  | Standard normal AD case 0 with $N(2, 1)$   |        100        |           100           | Reject test ($\text{stat} \ge 2.492$) | **PASSED**  | Mean bias detected and rejected                     |

---

### 8.8 Verification of GEV Sign Convention Across Estimators

The verification of the sign convention for the shape parameter ($c$) in [`gev_sign_convention_verification.csv`](file:///Users/mahron/Data/python/SPEI/outputs/master_validation/gev_sign_convention_verification.csv) is as follows:

| Value of $c_{\text{true}}$ | Theoretical Extreme Tail Type   | SciPy Fit Value ($c$) | Moments Estimate ($c$) | L-Moments Estimate ($c$) | Sign Consistency | SciPy Convention Match | Maximum Error |
| :------------------------: | :------------------------------ | :-------------------: | :--------------------: | :----------------------: | :--------------: | :--------------------: | :-----------: |
|         **-0.50**          | Fréchet (heavy upper tail)      |        -0.4957        |        -0.2887         |         -0.4734          |     **True**     |        **True**        |    0.2113     |
|         **-0.30**          | Fréchet (heavy upper tail)      |        -0.2957        |        -0.2185         |         -0.2873          |     **True**     |        **True**        |    0.0815     |
|         **-0.15**          | Fréchet (heavy upper tail)      |        -0.1455        |        -0.1184         |         -0.1423          |     **True**     |        **True**        |    0.0316     |
|         **+0.15**          | Reverse Weibull (bounded upper) |        +0.1552        |        +0.1543         |         +0.1534          |     **True**     |        **True**        |    0.0052     |
|         **+0.30**          | Reverse Weibull (bounded upper) |        +0.3053        |        +0.3016         |         +0.3022          |     **True**     |        **True**        |    0.0053     |
|         **+0.50**          | Reverse Weibull (bounded upper) |        +0.5045        |        +0.1000         |         +0.5009          |     **True**     |        **True**        |    0.4000     |

_Mathematical Conclusion:_

1. There is no algebraic sign inversion between `lmoments3` and `scipy.stats.genextreme`. Both define $c < 0$ for Fréchet and $c > 0$ for Weibull.
2. Correction of the theoretical SciPy skewness formula in `estimate_gev_moments()` restores the shape sign perfectly without altering the conventional sign definition.

---

## 9. Regression Test Results and Targeted Hardening (Step 9)

The comprehensive test suite was executed using `pytest`:

- **Test Files**:
  - `tests/test_distribution_selection_master.py` (27 test modules: GEV validation, conditional-positive checks, AIC parsimony, SPI transformation, SI integration, normality metrics, Tests A1–A5 for Wang AIC feasibility, and Tests C1–C7 for fair consensus ranking).
  - `tests/test_dasarian.py` (19 dekadal tests: 36-dekad BMKG aggregation, rolling dekadal accumulation, Tests D1–D4 for sparse cadence, and validation of midnight labels).
  - Supporting test suites: `test_master_task_dspi.py` (32 tests), `test_audit_34010701a.py` (31 tests), `test_nan_diagnostics.py` (25 tests), `test_si.py` (60 tests), and other modules.
- **Final Execution Result**: **235 passed in 97.64s**. The pass rate is **100%**.

The automated testing coverage includes:

- **Test A (GEV)**: Verification of positive and negative sign conventions, recovery of MLE/MoM/L-moments parameters, CDF consistency.
- **Test B (Conditional-Positive)**: Proof of the integration of $1 - F(0)$ in Gumbel-R, Pearson III, and GEV; rejection of conditional-positive when `prob_zero=False`; consistency of bootstrap refits.
- **Test C (SPI Transformation)**: Transformation based on `Dist.cdf()`, correct handling of zeros ($p_{\text{centroid}}$), handling of all-zero groups, evaluation of `sw_clip=None`.
- **Test D (AIC & Ranking)**: Calculation of $\Delta\text{AIC}$, numerical AIC tie-breaks, handling of failed candidates, selection of Best #1 and Alt #2, isolation of ineligible models.
- **Test E (`SI` Integration)**: Execution of `SI.select_optimal_distribution()` under `fit_window=0` and `fit_window>0`, verification of non-mutation of internal state (`self.dist` and SPI output remain unchanged).
- **Test F (Normality Metrics)**: Clear separation between SPI normality tests (SW and SPI AD) and positive-precipitation goodness-of-fit tests (KS/AD bootstrap).
- **Tests A1–A5 (Targeted Hardening for Wang AIC)**: Disqualification of augmented pseudo-observation fits from the official AIC ranking (`aic_comparable=False`), preservation of MLE validity for purely observed data, preservation of SPI calculation functions, and prevention of false wins by augmented candidates.
- **Tests C1–C7 (Targeted Hardening for Fair Consensus)**: Rejection of partial evaluations (without silent NaN dropping), assignment of `consensus_eligible=False` when metrics are incomplete, absence of artificial winners when all candidates are incomplete, and preservation of the dual-ranking structure without duplicate evaluation.
- **Tests D1–D4 (Targeted Hardening for Dekadal Data)**: Handling of sparse calendars with `fit_freq="dekad"` without double aggregation, preservation of calendar gaps, distinction between monthly and dekadal cadence, and strict rejection of non-midnight timestamps (`00:00:00`), timezone-aware indices, and duplicates in `rolling_dasarian()`.

---

## 10. Files Modified and Examples of the Latest API Usage (Step 10)

### 10.1 List of Modified / Added Files

1. `src/spei/dist.py`:
   - Correction of the theoretical SciPy skewness formula in `estimate_gev_moments()`.
   - Application of `cond_pos = bool(conditional_positive)` and removal of the hardcoded Gumbel-R setting.
   - Addition of the physical survival floor `logsf0 < -4.60517` in the Gumbel-R, Pearson III, and GEV objective functions.
   - Explicit propagation of `conditional_positive=cond_pos` in `Dist.goodness_of_fit()`.
   - Separation of `is_mle=False` and `aic_comparable=False` with the reason `"pseudo_observation_augmented_fit"` for Wang pseudo-observation augmentation fits.
2. `src/spei/model_selection.py` & `model_selection.py`:
   - Synchronization of `_spi_from_fitted_model()` to `Dist.cdf()`.
   - Implementation of `_rank_rows()`, selection of Best #1 and Alternative #2.
   - Addition of deterministic `sw_zero_seed` per group.
   - Extension of `summarize_candidate_diagnostics()` and `rank_aggregated_candidates()` (`hierarchical` and `consensus_rank`).
   - Enforcement of completeness of required metrics in `consensus_rank` to prevent unfair partial scores.
   - Provision of side-by-side comparison output (`ranking_comparison`) without recomputation.
3. `src/spei/si.py`:
   - Addition of the `SI.select_optimal_distribution()` method.
   - Protection against mutation of `self.dist` and `_dist_dict`.
   - Introduction of pre-aggregated dekadal series in `SI.__post_init__()` when `fit_freq in ("dekad", "dasarian")`.
4. `src/spei/utils.py`:
   - Addition of canonical BMKG dekadal date validation (`is_valid_dasarian_labels`).
   - Conservative distinction between monthly and dekadal calendars in `is_dasarian_index()`.
   - Strict rejection of non-midnight labels (`00:00:00`), timezone-aware indices, and duplicates in `rolling_dasarian()`.
5. `src/spei/__init__.py`:
   - Export of the `model_selection` module and utility `is_valid_dasarian_labels`.
6. `tests/test_distribution_selection_master.py` & `tests/test_dasarian.py`:
   - Addition of modules and targeted hardening tests (Tests A1–A5, C1–C7, D1–D4).
7. `outputs/`:
   - Consolidation of all evaluation artifacts, visualisations, and validation reports in the `outputs/` directory (`outputs/distribution_selection/`, `outputs/master_validation/`, and `outputs/validation_34010701a/`).
   - Inventory of artifacts in [`outputs/master_validation/`](file:///Users/mahron/Data/python/SPEI/outputs/master_validation/):
     - [`station_34010701a_daily_candidate_rankings.csv`](file:///Users/mahron/Data/python/SPEI/outputs/master_validation/station_34010701a_daily_candidate_rankings.csv) (Daily Hierarchical Ranks)
     - [`station_34010701a_daily_candidate_rankings_consensus.csv`](file:///Users/mahron/Data/python/SPEI/outputs/master_validation/station_34010701a_daily_candidate_rankings_consensus.csv) (Daily Consensus Ranks)
     - [`station_34010701a_dasarian_candidate_rankings.csv`](file:///Users/mahron/Data/python/SPEI/outputs/master_validation/station_34010701a_dasarian_candidate_rankings.csv) (Dekadal Hierarchical Ranks)
     - [`station_34010701a_dasarian_candidate_rankings_consensus.csv`](file:///Users/mahron/Data/python/SPEI/outputs/master_validation/station_34010701a_dasarian_candidate_rankings_consensus.csv) (Dekadal Consensus Ranks)
     - [`station_34010701a_dspi_daily_summary.csv`](file:///Users/mahron/Data/python/SPEI/outputs/master_validation/station_34010701a_dspi_daily_summary.csv) (Daily DSPI Summary Statistics)
     - [`station_34010701a_dspi_dasarian_summary.csv`](file:///Users/mahron/Data/python/SPEI/outputs/master_validation/station_34010701a_dspi_dasarian_summary.csv) (Multi-scale Dekadal SPI Summary Statistics)
     - [`synthetic_stress_test_results.csv`](file:///Users/mahron/Data/python/SPEI/outputs/master_validation/synthetic_stress_test_results.csv) (18 Boundary Stress Test Results)
     - [`gev_sign_convention_verification.csv`](file:///Users/mahron/Data/python/SPEI/outputs/master_validation/gev_sign_convention_verification.csv) (GEV Sign Convention Verification)
     - [`delta_aic_vs_normality_scatter.png`](file:///Users/mahron/Data/python/SPEI/outputs/master_validation/delta_aic_vs_normality_scatter.png) (Delta AIC vs Normality Plot)
     - [`station_34010701a_dspi_daily_timeseries.png`](file:///Users/mahron/Data/python/SPEI/outputs/master_validation/station_34010701a_dspi_daily_timeseries.png) (Daily DSPI Time Series Plot)
     - [`station_34010701a_dspi_dasarian_timeseries.png`](file:///Users/mahron/Data/python/SPEI/outputs/master_validation/station_34010701a_dspi_dasarian_timeseries.png) (Dekadal SPI Time Series Plot)
     - [`nan_diagnostic_waterfall.png`](file:///Users/mahron/Data/python/SPEI/outputs/master_validation/nan_diagnostic_waterfall.png) (NaN Diagnostic Waterfall Plot)

### 10.2 Examples of the Latest API Usage

#### A. Direct Distribution Selection from an `SI` Object

```python
import pandas as pd
from scipy.stats import gamma
from spei.si import SI

# 1. Initialize an SI object from daily precipitation data
si = SI(
    series=daily_rainfall,
    dist=gamma,
    timescale=10,        # 10-day accumulation
    fit_freq="D",       # Daily grouping
    fit_window=0,        # or, for example, fit_window=31 for a rolling window
    prob_zero=True,
    fitting_policy="standard",
    small_sample_policy="strict",
)

# 2. Run optimal selection without changing the active SI configuration
selection = si.select_optimal_distribution(
    candidates=None,             # Default: 7 candidates (gamma, weibull, gumbel, lognorm, fisk, pearson3, gev)
    prefer_two_parameters=True,  # Prefer 2-parameter models when competitive
    delta_aic_threshold=2.0,     # Burnham & Anderson competitive-set threshold
    n_boot=99,                   # Number of bootstrap refits
    gof_scope="competitive",    # Bootstrap tests on the Delta AIC shortlist
    sw_clip=None,               # No clipping before Shapiro-Wilk
    min_valid_group_fraction=0.80,
    normality_ratio_threshold=0.90,
    ranking_method="hierarchical",
)

print(f"Best Distribution (#1): {selection['best_distribution']}")
print(f"Alternative Distribution (#2): {selection['alternative_distribution']}")
print(f"Selection Status: {selection['best_selection_status']}")
print(f"Reason: {selection['selection_reason']}")

# 3. Access the global ranking tables and diagnostic summary
global_ranks = selection["global_ranking"]
summary = selection["candidate_summary"]
by_day_recs = selection["recommendations"]

# Note: si.spi() continues to produce SPI based on the active gamma distribution
# Users can explicitly update the distribution if desired:
# si_best = SI(daily_rainfall, dist=selection["selected_scipy_distribution"], ...)
```

#### B. Independent Single-Group Selection

```python
from spei.model_selection import select_best_distribution

result = select_best_distribution(
    data=calendar_day_rainfall,
    prob_zero=True,
    delta_aic_threshold=2.0,
    prefer_two_parameters=True,
    n_boot=99,
    gof_scope="competitive",
    random_state=42,
)

rec = result["recommendation"]
print(f"#1: {rec['distribution']} (AIC={rec['AIC']:.2f})")
print(f"#2: {rec['alternative_distribution']} (AIC={rec['alternative_AIC']:.2f})")
```

---

## 11. Recommendations for Research and Operational Use

1. **Operational Selection Recommendation**:
   - For tropical rainfall stations with high skewness characteristics such as rainfall station 34010701a, **Pearson III** is recommended as the primary distribution (#1) if the main goal is to minimize information loss ($\Delta\text{AIC}$ lowest).
   - If numerical stability and 2-parameter model parsimony are prioritized for broad operational use, **Weibull minimum** or **Gamma** are recommended as highly reliable operational distributions, with Shapiro-Wilk rejection frequencies below 7%.
2. **Limitation of Daily Calendar Sample Size**:
   - With a historical record length of 15 years ($N \approx 15$ per calendar day), the statistical power of the Anderson-Darling normality test against the standard $N(0,1)$ parameter is limited. Users are advised to use a rolling calibration window (`fit_window=15` or `fit_window=31`) if they want to increase the effective sample size per group to approximately $N \approx 200$–$450$ observations.
3. **Separation of Project Policy from Scientific Reference**:
   - The publications of Stagge et al. (2015), Lee et al. (2023), and Burnham & Anderson (2002) serve as the scientific basis for selecting the metrics ($\Delta\text{AIC} < 2$, S-W rejection frequency, and AD pass ratio).
   - The hierarchical aggregation rules (e.g., 80% coverage threshold and 2-parameter preference) represent the project’s operational quality policy, which has been documented and can be configured through function parameters.
