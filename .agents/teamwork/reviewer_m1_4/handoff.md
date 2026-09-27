# Handoff Report — reviewer_m1_4 (M1 Factor Kernel Soundness & Worker Fix Verification)

## 1. Observation

1. **Verification Command Executions**:
   - `uv run pytest tests/test_xs_portfolio_alpha/test_ranking_engine.py -v`:
     `11 passed in 0.19s`, exit code 0.
   - `uv run pytest tests/test_xs_portfolio_alpha/ -v`:
     `116 passed in 1.70s`, exit code 0.
   - `uv run ruff check src/quant_system/research_xs_monthly/ranking.py tests/test_xs_portfolio_alpha/test_ranking_engine.py`:
     `All checks passed!`, exit code 0.
   - `uv run mypy src/quant_system/research_xs_monthly/ranking.py tests/test_xs_portfolio_alpha/test_ranking_engine.py`:
     `Success: no issues found in 2 source files`, exit code 0.
   - `powershell -ExecutionPolicy Bypass -File scripts/audit-agent-claims.ps1`:
     `RESULT: PASS - every workspace has a visible claim and every claim resolves.`, exit code 0.
   - `powershell -ExecutionPolicy Bypass -File scripts/audit-disk-layout.ps1`:
     `RESULT: PASS - no stray QuantOS directories.`, exit code 0.

2. **Source Code Structure in `src/quant_system/research_xs_monthly/ranking.py`**:
   - Lines 50-55: Helper `_is_finite_positive_decimal(val)` safely checks `not (val.is_nan() or val.is_infinite()) and val > Decimal(0)` within a `try/except` block, preventing unhandled `decimal.InvalidOperation` errors.
   - Lines 137-170 (`compute_intermediate_momentum`): Requires `len(valid_bars) >= window + lag + 1` before computing return `(c_end - c_start) / c_start`. Fails closed (`None`) if history is insufficient or if prices are non-positive/non-finite.
   - Lines 172-205 (`compute_short_term_reversion`): Requires `len(valid_bars) >= window + lag + 1`, correctly evaluating recent 3-5 session returns without lookahead or window truncation.
   - Lines 207-284 (`compute_idiosyncratic_volatility`): Slices `tail_bars = valid_bars[-needed_bars:]` where `needed_bars = len(market_returns) + 1`, guaranteeing `len(returns) == len(market_returns)` across heterogeneous history lengths. Fallback to total realized volatility with $\beta = 1.0$ triggers only when `market_returns` is absent, length-mismatched, non-finite, or has variance $< 10^{-12}$.
   - Lines 484-535 (`rank_universe` standardization): Pre-computes universe cross-sectional means and standard deviations once in $O(N)$ time. Supports `ratio_zscore` (standardizing momentum and reversion before dividing by residual volatility) and `linear_zscore` (standardizing all three factors with winsorization at $\pm 3.0$ standard deviations).
   - Lines 536-548: Deterministic tie-breaking uses tuple sort key `(-item[1], item[0])`, descending by score, ascending lexicographically by symbol name.

3. **Integrity & Facade Inspection**:
   - Inspected `src/quant_system/research_xs_monthly/ranking.py` for hardcoded symbol names, test values, or shortcuts. Zero hardcoded results detected. All math uses genuine NumPy/math arithmetic.
   - Verified that all unit tests construct independent synthetic price series rather than asserting pre-baked constants.

4. **Adversarial Stress Testing Outcomes**:
   - Negative market beta: Evaluated asset with negative beta ($\beta = -1.5$, $\sigma_\epsilon = 0.000100$). Computed without sign inversion or crash.
   - Extreme return shock (+10,000% jump): Preserved finite composite score without floating-point overflow.
   - Single-asset universe: Returned rank 1 without divide-by-zero errors.
   - Zero cross-sectional variance (identical assets): Produced equal scores (0.0) and deterministically broke ties lexicographically ('A' at rank 1, 'B' at rank 2).

## 2. Logic Chain

1. **Resolution of Prior CAPM Regression Flaw**:
   - Observation 2 demonstrates that `compute_idiosyncratic_volatility` dynamically matches `needed_bars` to `len(market_returns) + 1`.
   - Because `valid_bars_by_sym` filters for `len(vbars) >= min_history_bars` (64), all constituents possess at least 64 bars.
   - Slicing `tail_bars = valid_bars[-(len(market_returns) + 1):]` ensures identical length arrays ($N = 63$) for every constituent regardless of whether total history is 64, 100, or 2520 bars.
   - Confirmed in `test_heterogeneous_history_lengths_capm_regression`: Symbols with 64, 100, and 120 bars all undergo CAPM regression without falling back to $\beta = 1.0$.

2. **Mathematical Soundness of Lookback Sizing**:
   - Sizing a return window over $W$ intervals with lag $L$ mathematically requires $W + L + 1$ closing bars (from bar $T-L-W$ to bar $T-L$).
   - Slicing at `idx_end = -1 - lag` and `idx_start = -1 - lag - window` computes exact point-in-time returns without Look-Ahead Bias.
   - Removing silent window clamping (`idx_start = 0`) guarantees fail-closed semantics when history is insufficient.

3. **Mathematical Soundness of Cross-Sectional Standardization**:
   - `ratio_zscore` normalizes momentum ($z_m$) and short reversion ($z_r$) to zero mean and unit variance before taking the difference $z_m - 0.5 z_r$. This ensures dampening operates on scale-invariant standard scores rather than raw returns of disparate magnitudes.
   - Scaling by idiosyncratic volatility divides by $\sigma_\epsilon > 0$ (floored at $10^{-6}$), penalizing high-noise speculative assets and rewarding consistent intermediate trends.
   - Pre-computation of universe moments reduces execution complexity to $O(N)$, ensuring fast runtime across 423 constituents.
   - Deterministic tie-breaking on `(-score, symbol)` establishes a strict weak ordering with reproducible ranks across all runs.

## 3. Caveats

- **Universe market return construction**: In `rank_universe`, market returns are derived as the equal-weighted return of all eligible universe names with complete history over the volatility window. If fewer than 2 constituents qualify, the engine safely falls back to total realized volatility ($\beta = 1.0$).
- **Single-name standalone calls**: Direct invocations of `compute_factor_components` without `market_returns` supplied intentionally use total realized volatility ($\beta = 1.0$), as documented in the contract.
- **Holdout quarantine**: The final 252 trading sessions (2025-08-14 to 2026-08-21) remain quarantined and were not touched during this review.

## 4. Conclusion

**Verdict: APPROVE**

The factor kernels in `src/quant_system/research_xs_monthly/ranking.py` are mathematically sound, point-in-time compliant, robust against edge cases (NaNs, infinite prices, zero variance, negative beta, extreme returns), and fully verified by unit and regression test suites. The code contains zero integrity violations, no hardcoded shortcuts, and passes all project linting, type-checking, and layout audits.

## 5. Verification Method

To independently reproduce and verify this review:

1. **Execute Ranking Engine Unit Tests**:
   ```powershell
   uv run pytest tests/test_xs_portfolio_alpha/test_ranking_engine.py -v
   ```
   *Expected outcome*: 11 passed in <0.5s, exit code 0.

2. **Execute Full XS Portfolio Alpha Test Suite**:
   ```powershell
   uv run pytest tests/test_xs_portfolio_alpha/ -v
   ```
   *Expected outcome*: 116 passed in <2.0s, exit code 0.

3. **Verify Linter and Type Checker**:
   ```powershell
   uv run ruff check src/quant_system/research_xs_monthly/ranking.py tests/test_xs_portfolio_alpha/test_ranking_engine.py
   uv run mypy src/quant_system/research_xs_monthly/ranking.py tests/test_xs_portfolio_alpha/test_ranking_engine.py
   ```
   *Expected outcome*: All checks passed / Success: no issues found, exit code 0.

4. **Verify Repository Disk Layout & Agent Claims**:
   ```powershell
   powershell -ExecutionPolicy Bypass -File scripts/audit-agent-claims.ps1
   powershell -ExecutionPolicy Bypass -File scripts/audit-disk-layout.ps1
   ```
   *Expected outcome*: Both report `RESULT: PASS`, exit code 0.
