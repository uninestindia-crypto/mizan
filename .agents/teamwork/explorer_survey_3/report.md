# Survey Report: Factor Monotonicity (R3), Multiplicity Accounting & Noise Benchmarking (R4), and Test/Verification Infrastructure

**Agent**: `explorer_survey_3`  
**Working Directory**: `D:\quant_system\.agents\teamwork\explorer_survey_3`  
**Date**: 2026-09-25  
**Target Milestone**: Multi-Instrument Cross-Sectional Ranking Strategy Survey  

---

## Executive Summary

This report delivers the technical investigation into **R3 (Factor Monotonicity and Long-Short Diagnostic)**, **R4 (Multiplicity Accounting and Noise Benchmarking)**, and the **Repository Test & Verification Infrastructure** for QuantOS.

1. **R3 (Factor Monotonicity & Long-Short Diagnostic)**:
   - Evaluates cross-sectional ranking across the 423 names in `data/authorities/nse-research-universe-liquid-10y.csv`.
   - Divides the ranked eligible universe into 10 deciles ($Q1$ to $Q10$, ~42 names per decile) with deterministic tie-breaking.
   - Calculates per-rebalance Spearman rank Information Coefficient ($IC$) between composite factor scores and forward 21-session returns, and aggregates $IC$ across rebalances to verify mean $IC > 0$ and $t > 2.0$.
   - Tracks decile portfolio returns net of the 0.224% round-trip statutory cost model to verify strict monotonicity ($R_{\text{ann}}(Q1) > R_{\text{ann}}(Q10)$) and evaluates zero-capital dollar-neutral spread returns ($R_{Q1} - R_{Q10}$).

2. **R4 (Multiplicity Accounting & Noise Benchmarking)**:
   - Pre-declares evaluation budget via `TRIAL-LEDGER.md` enforced at runtime via `require_declared_trials` in `src/quant_system/research_short_horizon/ledger.py`.
   - Benchmarks strategy performance against three baselines under identical timing, universe, fill conventions, and cost models:
     * `CASH`: Zero return baseline (exposure 0.0, Sharpe 0.0).
     * `ALWAYS_TRADE`: Broad market baseline re-entering every eligible name on each rebalance date, paying the full 0.224% round-trip statutory cost.
     * `NOISE`: 30-seed pseudo-random Gaussian noise control on the identical staggered tranche and rebalance machinery.
   - Computes Deflated Sharpe Ratio (DSR) using Bailey & Lopez de Prado (2014) in `src/quant_system/analytics/multiplicity.py`, strictly using non-overlapping portfolio periods for sample length $T$ and matching annualization factors, and proves strategy DSR exceeds the median DSR of the 30-seed NOISE control.

3. **Test & Verification Infrastructure**:
   - Production test harness uses `pytest` (1,519+ tests currently passing forwards and in reverse file order to catch hidden state leaks).
   - Strict `mypy` typing across 208+ source files with zero errors.
   - `ruff` linting and formatting enforcing strict Python 3.12/3.13 standards.
   - Operational integrity audits `scripts/audit-agent-claims.ps1` and `scripts/audit-disk-layout.ps1` both verified passing (exit 0).
   - Comprehensive unit and E2E testing framework designed for all statistical, financial, and architectural acceptance criteria.

---

## 1. Investigation of R3: Factor Monotonicity and Long-Short Diagnostic

### 1.1 Universe and Scoring Context
- **Authority**: `data/authorities/nse-research-universe-liquid-10y.csv` defines 423 liquid NSE equities with $\ge 9.5$ years of trading history and median daily turnover $\ge 5$ crore INR (SME and PCA excluded).
- **Survivorship Bias Law**: The universe consists of currently active listings. A positive backtest result is weak evidence because the bias pushes favorably; a negative result is strong because the strategy failed despite favorable survival bias.
- **Point-in-Time Constraint**: For any decision close $T$, only bars with `available_at <= T` (specifically exchange dates $\le T$) are consumable.

### 1.2 Decile Portfolios ($Q1$ to $Q10$) Construction
At each rebalance close $T$:
1. **Eligibility Filtering**:
   - Symbols must have valid, continuous bar history over the required lookback (e.g., 21 to 63 sessions for intermediate momentum, 5 sessions for short-term dampening, 21 sessions for idiosyncratic volatility scaling).
   - Base close must be strictly positive (`close > 0`).
   - If universe coverage falls below `MIN_COVERAGE_FRAC` (e.g. 70%), the engine abstains fail-closed (`ScreenError("INSUFFICIENT_DATA")`).
2. **Composite Factor Scoring & Ranking**:
   - Composite score $S_{i, T}$ is calculated for each eligible name $i$.
   - Names are sorted in descending order of score: $S_{(1), T} \ge S_{(2), T} \ge \dots \ge S_{(N_T), T}$.
   - **Deterministic Tie-Breaking**: When two scores are equal, ties break lexicographically by symbol name (e.g., `test_cross_sectional_strategy.py:335`). This guarantees identical selection across independent runs.
3. **Decile Partitioning Math**:
   - Let $N_T$ be the total number of scored names at date $T$ ($N_T \approx 423$).
   - Exact integer bin boundaries are computed via cumulative quantile boundaries:
     $$\text{boundary}(k) = \text{round}\left( \frac{k \cdot N_T}{10} \right) \quad \text{for } k = 0, 1, \dots, 10$$
   - Decile $Q_k$ contains indices from $\text{boundary}(k-1)$ to $\text{boundary}(k)$:
     * $Q_1$ (Top decile, highest factor scores): top 10% (ranks 1 to ~42).
     * $Q_2$: next 10% (ranks ~43 to ~84).
     * $\dots$
     * $Q_{10}$ (Bottom decile, lowest factor scores): bottom 10% (ranks ~382 to 423).
   - This exact integer boundary guarantees:
     $$\sum_{k=1}^{10} |Q_k| = N_T \quad \text{and} \quad Q_j \cap Q_k = \emptyset \quad (j \ne k)$$

### 1.3 Execution and Decile Tracking
- **Execution Timing**: Next-session open ($T+1$ Open) entry; exit at $T+H$ Open ($H=21$ trading sessions).
- **Statutory Friction**: 0.224% round-trip statutory cost model (`COST_RATIO = Decimal("0.00224")`).
- **Locked / Illiquid Session Handling**:
  - If a constituent has $\text{Volume} = 0$ or $\text{High} == \text{Low}$ (circuit limit) on entry or exit date, the constituent is excluded from that period's fill (`skipped_locked += 1`) without fabricating an unexecutable price.
- **Decile Return Calculation**:
  - Each decile $Q_k$ is equal-weighted across its valid constituents:
    $$R_{Q_k, p} = \frac{1}{|Q_k^{\text{valid}}|} \sum_{i \in Q_k^{\text{valid}}} \left[ \frac{\text{Open}_{i, T_p+H} - \text{Open}_{i, T_p+1}}{\text{Open}_{i, T_p+1}} - 0.00224 \right]$$
  - The return series $\{R_{Q_k, p}\}_{p=1}^P$ is tracked across all validation rebalance periods for each of the 10 deciles.

### 1.4 Monotonicity Verification
- **Annualized Return per Decile**:
  $$R_{\text{ann}}(Q_k) = \left( \frac{1}{P} \sum_{p=1}^P R_{Q_k, p} \right) \times \left( \frac{252}{H} \right)$$
- **Acceptance Criterion**:
  $$R_{\text{ann}}(Q_1) > R_{\text{ann}}(Q_{10})$$
  (Top decile annualized return strictly exceeds bottom decile annualized return).
- **Rank Monotonicity Metric**:
  Compute Spearman rank correlation between the decile index vector $(1, 2, \dots, 10)$ and the decile annualized return vector $(R_{\text{ann}}(Q_1), \dots, R_{\text{ann}}(Q_{10}))$. A monotonically decreasing return profile produces a rank correlation near $-1.0$.

### 1.5 Calculation of Spearman Rank Information Coefficient (IC) and t-statistic
- **Cross-Sectional Rank IC per Rebalance $p$**:
  For all universe names $i$ with valid forward returns at rebalance $p$:
  * Let $S_{i, p}$ be the composite factor score at decision close $T_p$.
  * Let $F_{i, p}$ be the realized forward return from $T_p+1$ open to $T_p+H$ open.
  * Compute ordinal ranks $r(S_{i, p})$ and $r(F_{i, p})$.
  * Compute Spearman rank correlation:
    $$IC_p = \frac{\sum_{i=1}^{M_p} (r(S_{i, p}) - \bar{r}_S)(r(F_{i, p}) - \bar{r}_F)}{\sqrt{\sum_{i=1}^{M_p} (r(S_{i, p}) - \bar{r}_S)^2 \sum_{i=1}^{M_p} (r(F_{i, p}) - \bar{r}_F)^2}}$$
  * Existing implementation reference: `src/quant_system/research_xs_monthly/screen.py:255-267` computes Pearson correlation over float ranks (`_pearson_on_floats(_ranks(scores), _ranks(forwards))`).
- **IC Aggregation across $P$ Rebalances**:
  * Mean Information Coefficient:
    $$\overline{IC} = \frac{1}{P} \sum_{p=1}^P IC_p$$
  * Sample Standard Deviation of IC:
    $$s_{IC} = \sqrt{\frac{1}{P - 1} \sum_{p=1}^P (IC_p - \overline{IC})^2}$$
  * Standard Error:
    $$SE(IC) = \frac{s_{IC}}{\sqrt{P}}$$
  * t-statistic:
    $$t_{IC} = \frac{\overline{IC}}{SE(IC)} = \frac{\overline{IC} \cdot \sqrt{P}}{s_{IC}}$$
- **Acceptance Criterion**:
  $$\overline{IC} > 0 \quad \text{and} \quad t_{IC} > 2.0$$

### 1.6 Measurement of Top-Bottom Decile Spread Returns
- **Zero-Capital Long-Short Spread per Rebalance**:
  $$\text{Spread}_p = R_{Q1, p} - R_{Q10, p}$$
- **Dollar-Neutral Long-Short Diagnostic Return**:
  $$R_{\text{LS}, p} = \frac{1}{2} (R_{Q1, p} - R_{Q10, p})$$
- **Spread Statistics**:
  * Mean net spread per period: $\overline{\text{Spread}} = \frac{1}{P} \sum_{p=1}^P \text{Spread}_p$.
  * Annualized spread return: $\overline{\text{Spread}} \times (252 / H)$.
  * Spread volatility: $s_{\text{Spread}} \times \sqrt{252 / H}$.
  * Spread Sharpe Ratio: $SR_{\text{Spread}} = \frac{\overline{\text{Spread}}}{s_{\text{Spread}}} \times \sqrt{252 / H}$.
  * Spread t-statistic: $t_{\text{Spread}} = \frac{\overline{\text{Spread}} \cdot \sqrt{P}}{s_{\text{Spread}}}$.

---

## 2. Investigation of R4: Multiplicity Accounting and Noise Benchmarking

### 2.1 Pre-Declared Evaluation Budget
- **Governing Law**: Every parameter search, feature variation, universe subset, or horizon evaluated consumes a multiplicity ordinal. Searching without pre-declaring is hidden multiplicity that manufactures false discoveries.
- **QuantOS Ledger Architecture**:
  * `reports/.../TRIAL-LEDGER.md` is the immutable authority for declared trials.
  * In code: `src/quant_system/research_short_horizon/ledger.py` implements:
    ```python
    def require_declared_trials(declared: int, ledger_path: Path | None = None) -> int:
        actual = declared_spent_trials(ledger_path)
        if declared != actual:
            raise ValueError(f"declared multiplicity count {declared} disagrees with ledger ({actual})")
    ```
  * At runtime, before executing any trial or computing any metric, the runner calls `require_declared_trials(DECLARED_TRIALS)`. A discrepancy fails closed immediately.
  * Controls (`NOISE`) and calibration grids (`C1`) do not consume multiplicity ordinals because they cannot promote.

### 2.2 Benchmarking Suite
To prevent market drift, broad beta, or random luck from masquerading as alpha, the candidate strategy is scored over the **identical decision dates and universe** against three baselines:

1. **`CASH` (No-Trade / Risk-Free Baseline)**:
   - Return: $0.000000$.
   - Exposure: $0.0$.
   - Trades: $0$.
   - Sharpe: $0.0$.
   - Proves whether the strategy produces positive net economic value after deducting transaction fees.

2. **`ALWAYS_TRADE` (Broad Market Benchmark)**:
   - Re-enters every eligible name in the research universe on every rebalance date with equal weighting.
   - Held for the identical $H=21$ horizon.
   - Pays the full 0.224% round-trip statutory cost on every rebalance.
   - Why not classic "Buy-and-Hold": Passive buy-and-hold pays transaction costs only twice over a 10-year span. `ALWAYS_TRADE` turns over every rebalance, providing the exact friction-adjusted market baseline to determine whether active stock selection adds value over naive full-market participation.

3. **30-Seed Pseudo-Random `NOISE` Control**:
   - Structure: 30 independent runs ($s = 0, \dots, 29$) using pseudo-random Gaussian predictions:
     $$\hat{y}_{i, T}^{(s)} \sim \mathcal{N}(0, \sigma_{\text{returns}}^2)$$
     Seeded deterministically via `Random(NOISE_SEED + H * 1000 + s)` where `NOISE_SEED = 20260910`.
   - Pipeline Parity:
     Passed through the **identical execution engine**:
     * Same 4-tranche staggered ledger (each tranche held 21 sessions, 25% capital allocation, total leverage $\le 100\%$).
     * Same walk-forward validation folds, embargo, and purging.
     * Same $T+1$ open entry, $T+21$ open exit, and 0.224% statutory cost.
     * Same top-quintile selection logic.
   - Distribution Statistics:
     Across the 30 seeds, compute order statistics:
     * Sharpe: `sharpe_min`, `sharpe_median`, `sharpe_max`.
     * Deflated Sharpe Ratio: `dsr_min`, `dsr_median`, `dsr_p90`, `dsr_max`.
   - Benchmark Requirement:
     The candidate strategy's Deflated Sharpe Ratio must strictly exceed the median DSR of the 30-seed NOISE control at the 21-session holding horizon:
     $$\text{DSR}_{\text{candidate}} > \text{Median}(\text{DSR}_{\text{NOISE\_seeds}})$$

### 2.3 Deflated Sharpe Ratio (DSR) Calculation & Inspection of `analytics/multiplicity.py`

#### 2.3.1 Mathematical Formulation (Bailey & Lopez de Prado 2014)
`src/quant_system/analytics/multiplicity.py` implements the Deflated Sharpe Ratio:

1. **De-annualize the estimated Sharpe ratio**:
   $$A = \sqrt{\text{periods\_per\_year}}$$
   $$\widehat{SR} = \frac{\text{estimated\_sharpe}}{A}$$
2. **Compute null trial standard deviation**:
   If empirical cross-trial dispersion is unavailable:
   $$\sigma_0 = \frac{1}{\sqrt{T - 1}}$$
   where $T = \text{sample\_length\_bars}$ (number of non-overlapping portfolio periods).
3. **Compute selection benchmark (Expected Maximum of $N$ standard normals)**:
   For $N = \text{num\_trials}$:
   $$\mu_{\max} \approx (1 - \gamma) \Phi^{-1}\left(1 - \frac{1}{N}\right) + \gamma \Phi^{-1}\left(1 - \frac{1}{N \cdot e}\right)$$
   where $\gamma \approx 0.5772156649015329$ is the Euler-Mascheroni constant and $\Phi^{-1}$ is `NormalDist().inv_cdf`.
   The selection benchmark is:
   $$SR^* = \sigma_0 \cdot \mu_{\max}$$
4. **Compute variance term with skewness and kurtosis correction**:
   $$V = 1 - \gamma_3 \widehat{SR} + \left( \frac{\gamma_4 - 1}{4} \right) \widehat{SR}^2$$
   where $\gamma_3 = \text{skewness}$ and $\gamma_4 = \text{kurtosis}$.
5. **Compute test statistic and DSR probability**:
   $$z = \frac{(\widehat{SR} - SR^*) \cdot \sqrt{T - 1}}{\sqrt{V}}$$
   $$DSR = \Phi(z) = \text{NormalDist().cdf}(z) \in [0.0, 1.0]$$

#### 2.3.2 Critical Repository Invariants and Historical Defect Repairs
Inspection of `analytics/multiplicity.py`, `research_short_horizon/evaluation.py`, and `reports/short_horizon/TRIAL-LEDGER.md` reveals three vital invariants:

1. **DSR is a probability, NOT a Sharpe ratio**:
   DSR represents the probability that the true Sharpe exceeds the selection benchmark given the multiple testing burden ($N$ trials) and non-normal sampling variance.
2. **Sample Length $T$ must be independent portfolio periods**:
   In overlapping holding periods (e.g. daily decision dates with 21-day holds), counting raw decision dates ($T \approx 2,173$) instead of completed non-overlapping portfolio periods ($T \approx 2,173 / 21 \approx 103$) artificially shrinks sampling error by $\sqrt{21} \approx 4.58\times$. This was identified and repaired in `evaluation.py:216-238`.
   `scored_periods = max(candidate.portfolio_periods, 3)` must be used.
3. **Annualization consistency**:
   `periods_per_year` must match the period compounding basis: $\text{round}(252 / H)$ (i.e. $12$ for $H=21$).
4. **Pearson Moment Constraint Guard**:
   Pearson's inequality requires $\gamma_4 \ge 1 + \gamma_3^2$.
   Following commit `ac47d7c`, the guard in `multiplicity.py:100-106` uses an envelope tolerance:
   `_PEARSON_BOUND_REL_TOLERANCE = 64.0 * sys.float_info.epsilon`
   This prevents floating-point rounding from crashing legitimate two-point distributions while strictly rejecting impossible moments.

---

## 3. Test & Verification Infrastructure

### 3.1 Repository Test Harness, Linting, and Typing
The repository enforces a rigorous verification pipeline mirrored in `.github/workflows/ci.yml` and `scripts/run-gates.ps1`:

| Tool | Configuration | Surface / Scope | Status |
|---|---|---|---|
| **pytest** | `pytest>=8.0.0`, `pytest-cov`, `addopts = "-ra -v --basetemp=tmp/pytest"` | `tests/` (1,519+ tests) | **100% PASSING** |
| **Execution order** | Forward order (`pytest tests/ -q`) and Reverse order (`pytest @files -q`) | All `test_*.py` files | **100% PASSING** |
| **ruff check** | Rules `E, F, I, W, UP, B, C4`, target `py312`, line-length 100 | Entire repository (excluding `.venv`, `.agents`, `tmp`) | **CLEAN (0 errors)** |
| **ruff format** | `ruff format --check .` | Entire repository | **CLEAN (0 errors)** |
| **mypy** | Strict mode: `disallow_untyped_defs=True`, `warn_return_any=True` | `src launcher.py scripts` (208+ files) | **CLEAN (0 errors)** |
| **Craft checkers** | Node.js checkers `scripts/check-code.mjs` and `check-tests.mjs` | `src/` and `tests/` (0 sleep in tests, 0 unannotated loops) | **CLEAN (0 errors)** |

### 3.2 Audit Scripts Verification
Both governance audit scripts were executed directly in PowerShell:

1. **`scripts/audit-agent-claims.ps1`**:
   - Cross-references registered Git worktrees and non-default local branches against active work records in `agent_context/work/active/`.
   - Verified Output:
     ```
     Claims naming a workspace: OK
     Registered worktrees: OK (3 registered worktrees verified)
     Local branches: OK (10 local branches verified)
     RESULT: PASS - every workspace has a visible claim and every claim resolves.
     ```
   - Exit code: `0`.

2. **`scripts/audit-disk-layout.ps1`**:
   - Verifies compliance with `agent_context/DISK-LAYOUT.md` (only `D:\quant_system` and `D:\quant_system_workspaces` at drive root).
   - Verified Output:
     ```
     Canonical roots: OK (D:\quant_system 7.2 GB, D:\quant_system_workspaces 7.8 GB)
     Workspace buckets: verification_clones (19), worktrees (3), scratch (12), archive (0)
     Registered Git worktrees: OK
     RESULT: PASS - no stray QuantOS directories.
     ```
   - Exit code: `0`.

### 3.3 Acceptance Criteria Testing & Verification Architecture
The following testing matrix outlines how every acceptance criterion will be verified by unit and E2E test suites in `tests/test_xs_portfolio_alpha.py`:

```
+----------------------------------------------------------------------------------------------------+
| ACCEPTANCE CRITERIA VERIFICATION MATRIX                                                            |
+------------------------------------+--------------------------------+------------------------------+
| Requirement / Criterion            | Unit Test Verification         | E2E Validation Verification  |
+------------------------------------+--------------------------------+------------------------------+
| Net Annualized Sharpe > 0          | Test net return deduction:     | Run complete 4-tranche       |
| after 0.224% round-trip costs      | gross - 0.00224 per round trip | backtest across validation   |
|                                    | on synthetic trade fixtures;   | partition; assert Sharpe > 0 |
|                                    | test tranche compounding math. | after full friction model.   |
+------------------------------------+--------------------------------+------------------------------+
| Average Spearman rank IC > 0       | Test calc_spearman_rank_ic on  | Assert mean cross-sectional  |
| with statistical significance      | perfect (1.0), inverse (-1.0), | rank IC > 0 and t > 2.0      |
| (t > 2.0)                          | and zero correlation; test     | across all validation dates. |
|                                    | t-statistic formula.           |                              |
+------------------------------------+--------------------------------+------------------------------+
| Factor Monotonicity:               | Test decile allocation: 10     | Execute decile analysis on   |
| R_ann(Q1) > R_ann(Q10)             | equal disjoint bins across 423 | validation data; assert      |
|                                    | names; test spread return math | R_ann(Q1) > R_ann(Q10) and   |
|                                    | and zero-capital long-short.   | negative rank correlation.   |
+------------------------------------+--------------------------------+------------------------------+
| Strategy DSR > Median of           | Test DSR formula against Bailey| Execute 30-seed NOISE control|
| 30-seed NOISE control at           | & Lopez de Prado fixtures; test| on identical ledger; verify  |
| 21-session holding horizon         | random gaussian noise generator| candidate DSR > median NOISE |
|                                    | and order statistics.          | DSR at H=21 horizon.         |
+------------------------------------+--------------------------------+------------------------------+
| Zero look-ahead leakage &          | Test feature computation cutoff| Audit bar timestamps and fill|
| next-open execution (T+1)          | at close T; test fill strictly | session indices; assert zero |
|                                    | at open T+1.                   | same-day close execution.    |
+------------------------------------+--------------------------------+------------------------------+
| Capital preservation invariant     | Test tranche ledger sum <= 1.0 | Continuous assertion: total  |
| (leverage <= 1.0)                  | across staggered entries and   | exposure <= 1.0 at every bar |
|                                    | exits under stress conditions. | throughout backtest history. |
+------------------------------------+--------------------------------+------------------------------+
| Quarantined final holdout          | Test partition slicer ensures  | Assert holdout partition     |
| partition untouched                | final 252 sessions are reserved| (final 252 sessions) is      |
|                                    | and inaccessible to folds.     | strictly quarantined.        |
+------------------------------------+--------------------------------+------------------------------+
| Static gates & audits clean        | Test craft checker self-tests; | Run ruff, mypy, pytest,      |
|                                    | test audit scripts parsing.    | audit-agent-claims, layout.  |
+------------------------------------+--------------------------------+------------------------------+
```

---

## 4. Key Decisions & Recommendations for Implementation

1. **Decile Partitioning**:
   Use integer-exact binning: `[int(Decimal(k) * Decimal(N) / Decimal(10)) for k in range(11)]` so deciles partition the 423 names into 10 disjoint subsets of 42–43 names each.
2. **IC Computation**:
   Compute cross-sectional Spearman rank IC on every rebalance date across all scored universe names with valid forward returns. If rebalances are overlapping (e.g. weekly rebalance with 21-day holding period), report both the per-rebalance $t$-statistic and the non-overlapping effective degrees of freedom.
3. **Multiplicity Enforcement**:
   Wire `require_declared_trials` to the strategy evaluation runner. Refuse to execute or publish results if the declared multiplicity count does not match `TRIAL-LEDGER.md`.
4. **NOISE Control Execution**:
   Run 30 independent draws of Gaussian predictions seeded with `NOISE_SEED + 21 * 1000 + seed`, pass through the identical 4-tranche staggered ledger, and extract the median DSR to benchmark against the candidate DSR.
5. **Strict Decimal Accounting**:
   Keep cash, positions, lot values, fees, and returns in exact `Decimal` throughout `src/quant_system/portfolio/` and `src/quant_system/research_xs_monthly/`.

---
*Report prepared by `explorer_survey_3` for orchestrator synthesis and implementation planning.*
