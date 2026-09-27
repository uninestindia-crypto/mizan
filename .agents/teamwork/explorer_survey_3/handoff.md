# Handoff Report — explorer_survey_3

**Agent**: `explorer_survey_3`  
**Working Directory**: `D:\quant_system\.agents\teamwork\explorer_survey_3`  
**Date**: 2026-09-25  
**Type**: Hard Handoff (Investigation & Survey Complete)  

---

## 1. Observation

1. **Universe Authority**:
   - `data/authorities/nse-research-universe-liquid-10y.csv` lines 8-432 contains exactly 423 symbols meeting $\ge 9.5$ years active history and median daily turnover $\ge 5$ crore INR.
   - Header (lines 3-7) notes:
     ```
     # SURVIVORSHIP BIAS: the source universe is ACTIVE listings only, so companies that
     # delisted or failed inside the window are absent. This cannot be corrected from this
     # cache. Read results asymmetrically: a positive result is weak evidence because the
     # bias pushes that way; a negative result is strong because the bias favoured the
     # strategy and it still failed.
     ```

2. **Existing Cross-Sectional Screen Stack**:
   - `src/quant_system/research_xs_monthly/screen.py` implements point-in-time cross-sectional scoring and execution:
     * Line 30: `COST_RATIO: Final = Decimal("0.00224")` (0.224% statutory round-trip friction).
     * Line 153-174: `forward_net(...)` skips locked bars where `bar.volume == 0 or bar.high == bar.low`.
     * Lines 255-267: Information Coefficient ($IC$) computation:
       `ic = _pearson_on_floats(_ranks([s for s, _ in fwd_all]), _ranks([f for _, f in fwd_all]))`.
     * Lines 288-296: Aggregation of $IC$ mean and t-statistic:
       `ic_t = mean_ic / (sd / sqrt(len(ic_values))) if sd > 0 else None`.
     * Lines 348-416: `run_long_short(...)` computes zero-capital long-short returns.

3. **Multiplicity Accounting & Deflated Sharpe Ratio**:
   - `src/quant_system/analytics/multiplicity.py:20-68`:
     * Implements `OverfittingDiagnostics.deflated_sharpe_ratio(...)` (Bailey & Lopez de Prado 2014).
     * Lines 49-67: de-annualizes Sharpe using `periods_per_year`, calculates expected max normal under `num_trials`, adjusts variance for skewness and kurtosis, and returns normal CDF probability in $[0.0, 1.0]$.
     * Lines 99-110: verifies Pearson moment inequality `kurtosis >= 1.0 + skewness**2` with tolerance `64.0 * sys.float_info.epsilon`.
   - `src/quant_system/research_short_horizon/ledger.py:123-144`:
     * Implements `require_declared_trials(declared, ledger_path)` which verifies that `declared` equals the exact number of `SPENT` numbered trials in `TRIAL-LEDGER.md`. Discrepancies fail closed immediately.
   - `scripts/run_short_horizon_experiment.py:401-446`:
     * Generates a 30-seed pseudo-random NOISE control where forecasts are drawn from $\mathcal{N}(0, \sigma^2)$ seeded with `NOISE_SEED + hold * 1000 + seed`. Evaluates each seed on the identical pipeline to compute order statistics (`dsr_min`, `dsr_median`, `dsr_max`, `sharpe_median`).

4. **Test & Verification Infrastructure**:
   - `pyproject.toml` pins pytest to `tests/`, `pythonpath = ["src", "."]`, `--basetemp=tmp/pytest`.
   - `.github/workflows/ci.yml` runs parallel jobs: `static` (ruff lint, ruff format, strict mypy), `tests` (forward and reverse file order), `craft` (Node.js craft checkers, claim & disk audits), and aggregated `gates`.
   - Command executions verified locally:
     * `powershell -ExecutionPolicy Bypass -File scripts/audit-agent-claims.ps1` returned: `RESULT: PASS - every workspace has a visible claim and every claim resolves.` (Exit 0).
     * `powershell -ExecutionPolicy Bypass -File scripts/audit-disk-layout.ps1` returned: `RESULT: PASS - no stray QuantOS directories.` (Exit 0).
     * `uv run ruff check src/quant_system/research_xs_monthly src/quant_system/analytics` exited 0 (All checks passed).
     * `uv run mypy src/quant_system/research_xs_monthly src/quant_system/analytics` exited 0 (Success: no issues found).
     * `uv run pytest tests/test_multiplicity.py tests/test_cross_sectional_strategy.py -q` passed (52 passed in 0.78s).
     * `uv run pytest tests/test_short_horizon_rescoring.py -q` passed (48 passed in 0.39s).

---

## 2. Logic Chain

1. **R3 Decile Monotonicity**:
   - From (1), the universe contains 423 liquid names. From (2), `screen.py` ranks names and selects the top fraction (e.g. top 20%). For R3, this must be generalized into 10 deciles ($Q1$ to $Q10$, ~42 names each).
   - From (2), `forward_net` applies 0.224% round-trip costs and handles circuit locks. By running this across all 10 decile portfolios, we can compute annualized net returns $R_{\text{ann}}(Q_k)$ for $k=1..10$.
   - Monotonicity requires $R_{\text{ann}}(Q1) > R_{\text{ann}}(Q10)$, and rank correlation between decile numbers $(1..10)$ and returns to be negative.
   - Long-short spread return is computed directly as $R_{Q1, p} - R_{Q10, p}$.
   - Spearman rank IC is computed across all scored names at each rebalance and aggregated into mean IC and t-statistic $t = \frac{\overline{IC} \sqrt{P}}{s_{IC}}$. The acceptance criterion requires $t > 2.0$.

2. **R4 Multiplicity Accounting and Noise Benchmarking**:
   - From (3), QuantOS enforces that evaluation budgets are pre-declared and frozen in `TRIAL-LEDGER.md`. Runtime code verifies `require_declared_trials` before running.
   - From (3), `multiplicity.py` computes DSR as a probability using Bailey & Lopez de Prado (2014), where sample length $T$ must be independent portfolio periods (not overlapping decision dates), and annualization must match.
   - From (3), the 30-seed NOISE control runs through the identical staggered tranche ledger and rebalance machinery. The candidate DSR must exceed the median DSR of these 30 random noise runs at the 21-session horizon to rule out data-mining bias.
   - Benchmarking against `CASH` (0% return) and `ALWAYS_TRADE` (broad market rebalanced with 0.224% cost) ensures economic validity and isolates selection skill from market beta.

3. **Verification Integrity**:
   - From (4), all audit scripts (`audit-agent-claims`, `audit-disk-layout`) and static gates (`ruff`, `mypy`) are operational and currently passing. New code and tests must strictly preserve these green gates.

---

## 3. Caveats

1. **Survivorship Bias**: As documented in the universe file, the 423 names are active listings today. Delisted or bankrupt names over the 10-year period are absent from this cache. This bias cannot be corrected from this dataset; results must be interpreted asymmetrically (a negative result is decisive, while a positive result requires cautious qualification).
2. **Overlapping Rebalance Autocorrelation**: If weekly rebalances are used with a 21-session holding horizon, successive holding periods overlap by ~16 sessions. In that regime, raw sample standard error of IC underestimates true sampling error unless Newey-West HAC standard errors (with lag 4) or independent non-overlapping calendar slices are evaluated.

---

## 4. Conclusion

The architectural, statistical, and operational foundations for implementing R3 (Factor Monotonicity & Long-Short Diagnostic) and R4 (Multiplicity Accounting & Noise Benchmarking) are fully established and clear:
- Decile construction should divide the 423 names into 10 disjoint bins of 42–43 names each, breaking ties lexicographically by symbol name.
- Spearman rank IC and decile spread returns ($Q1 - Q10$) must be evaluated across rebalances net of 0.224% round-trip costs.
- The evaluation budget must be pre-declared in `reports/.../TRIAL-LEDGER.md` and enforced via `require_declared_trials`.
- Strategy DSR must be evaluated against the median DSR of a 30-seed NOISE control run on the identical 4-tranche ledger machinery.
- All code must comply with Decimal accounting, strict Mypy, Ruff, and pass claim/disk audits.

---

## 5. Verification Method

To independently verify these findings, run:

1. **Static and Claim Audits**:
   ```powershell
   powershell -ExecutionPolicy Bypass -File scripts/audit-agent-claims.ps1
   powershell -ExecutionPolicy Bypass -File scripts/audit-disk-layout.ps1
   ```
   *Expected outcome*: Both exit code 0, 0 unclaimed workspaces, 0 stray directories.

2. **Linting and Type Checking**:
   ```powershell
   uv run ruff check src/quant_system/research_xs_monthly src/quant_system/analytics
   uv run mypy src/quant_system/research_xs_monthly src/quant_system/analytics
   ```
   *Expected outcome*: 0 errors, clean output.

3. **Multiplicity and Cross-Sectional Strategy Tests**:
   ```powershell
   uv run pytest tests/test_multiplicity.py tests/test_cross_sectional_strategy.py -v
   uv run pytest tests/test_short_horizon_rescoring.py -v
   ```
   *Expected outcome*: 100 tests pass in < 2 seconds.
