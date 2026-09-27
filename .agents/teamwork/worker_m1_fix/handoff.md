# Handoff Report — worker_m1_fix (M1 Defect Repairs & Hardening)

## 1. Observation

1. **mypy error in `test_ranking_engine.py`**:
   - Running `uv run mypy src/quant_system/research_xs_monthly/ranking.py tests/test_xs_portfolio_alpha/test_ranking_engine.py` prior to the fix reported:
     ```
     tests\test_xs_portfolio_alpha\test_ranking_engine.py:22: error: Unused "type: ignore" comment  [unused-ignore]
     tests\test_xs_portfolio_alpha\test_ranking_engine.py:23: error: Unused "type: ignore" comment  [unused-ignore]
     pyproject.toml: note: unused section(s): module = ['yaml.*']
     Found 2 errors in 1 file (checked 2 source files)
     ```
   - Discrepancy confirmed: `quant_system` is typed, so `# type: ignore[import-untyped]` was redundant and failed under `warn_unused_ignores = true`.

2. **CAPM market return length mismatch & silent fallback**:
   - In `src/quant_system/research_xs_monthly/ranking.py`, `FactorConfig.min_history_bars` was `63`.
   - When a stock had 63 bars, `w_effective` became `min(63, 62) = 62`, creating a 62-session market return vector.
   - For stocks with $\ge 64$ bars, `compute_idiosyncratic_volatility` sliced `window + 1 = 64` bars, producing 63 returns.
   - Line 222: `len(market_returns) != len(returns)` evaluated to `True` ($62 \neq 63$), triggering the fallback to total realized volatility and $\beta = 1.0$ for all established stocks in the universe.

3. **Window truncation and fail-closed violations**:
   - In `compute_intermediate_momentum` and `compute_short_term_reversion`, `if abs(idx_start) > len(valid_bars): idx_start = 0` silently clamped lookback windows to index 0 instead of returning `None`.
   - For example, with `window=63, lag=21` (requiring 85 bars), a 70-bar series computed a truncated 48-session return `0.48` rather than failing closed.

4. **Non-finite/NaN exceptions and signal inversion**:
   - Decision bars containing `Decimal('NaN')` crashed with `decimal.InvalidOperation` on relational comparisons (`<= Decimal(0)`).
   - In IEEE-754 float arithmetic, `float('nan') <= 0.0` evaluated to `False`, allowing `NaN` prices to bypass validation, contaminate equal-weighted universe market returns, corrupt cross-sectional z-score standardization (`np.mean` and `np.std` becoming `NaN`), and sort corrupted stocks to rank #1.

5. **Post-Fix Verification Tool Results**:
   - `uv run pytest tests/test_xs_portfolio_alpha/test_ranking_engine.py -v`:
     `11 passed in 0.20s` (exit code 0).
   - `uv run pytest tests/test_xs_portfolio_alpha/ -v`:
     `116 passed in 1.69s` (exit code 0).
   - `uv run ruff check src/quant_system/research_xs_monthly/ranking.py tests/test_xs_portfolio_alpha/test_ranking_engine.py`:
     `All checks passed!` (exit code 0).
   - `uv run mypy src/quant_system/research_xs_monthly/ranking.py tests/test_xs_portfolio_alpha/test_ranking_engine.py`:
     `Success: no issues found in 2 source files` (exit code 0).
   - `powershell -ExecutionPolicy Bypass -File scripts/audit-agent-claims.ps1`:
     `RESULT: PASS - every workspace has a visible claim and every claim resolves.` (exit code 0).
   - `powershell -ExecutionPolicy Bypass -File scripts/audit-disk-layout.ps1`:
     `RESULT: PASS - no stray QuantOS directories.` (exit code 0).

## 2. Logic Chain

1. **CAPM Length Slicing & Alignment**:
   - Observation 2 showed that heterogeneous history lengths produced an array length disparity between `market_returns` and `returns`.
   - Setting `min_history_bars: int = 64` in `FactorConfig` guarantees that every admitted constituent has at least 64 bars (63 returns).
   - In `compute_idiosyncratic_volatility`, dynamically slicing `tail_bars = valid_bars[-(len(market_returns) + 1):]` whenever `market_returns` is provided ensures that `len(returns) == len(market_returns)` exactly, regardless of whether a constituent has 64, 100, 252, or 2520 bars.
   - Verified in `test_heterogeneous_history_lengths_capm_regression`: Symbols with 64, 100, and 120 bars all successfully execute CAPM regression with distinct betas and idio-vols without fallback to $\beta = 1.0$.

2. **Window Sizing & Strict Fail-Closed Behavior**:
   - To compute a $W$-session return with lag $L$, exactly $W + L + 1$ closing bars are mathematically required (bar $T-L$ and bar $T-L-W$).
   - Replacing `len(valid_bars) < window` with `len(valid_bars) < window + lag + 1: return None` and removing `idx_start = 0` eliminates silent window truncation.
   - Verified in `test_insufficient_history_for_lagged_momentum_fails_closed`: `window=63, lag=21` fails closed on 70 and 84 bars, and succeeds only at $\ge 85$ bars.

3. **Safe Decimal & Finite Validation**:
   - Helper `_is_finite_positive_decimal(val)` safely checks `not (val.is_nan() or val.is_infinite()) and val > Decimal(0)` inside a `try/except` block, preventing `decimal.InvalidOperation`.
   - In `compute_factor_components` and `rank_universe`, `open`, `high`, `low`, and `close` are validated with `_is_finite_positive_decimal`, and `high >= low` is verified.
   - Factor kernels verify `math.isfinite(c)` and `c > 0.0`.
   - In `rank_universe`, non-finite scores are filtered out prior to universe z-score standardisation and sorting, preventing NaN pollution and preserving strict weak ordering in sorting.
   - Verified in `test_fail_closed_rejection_of_nan_and_infinite_prices`: Decision-bar and historical NaNs fail closed, corrupted names are excluded, and legitimate stocks preserve their rank without inversion.

4. **Performance & Typing**:
   - Pre-computing universe `mean_v` and `std_v` outside the symbol loop in `rank_universe` reduces linear z-scoring from $O(N^2)$ to $O(N)$.
   - Removing redundant `# type: ignore[import-untyped]` comments resolves the mypy errors and achieves exit code 0.

## 3. Caveats

- **Universe market returns**: In `rank_universe`, market returns are calculated as the equal-weighted mean of all eligible constituents with valid historical closes over the effective volatility window. If fewer than 2 constituents qualify, `market_returns` is set to `None`, triggering the safe fallback to total realized volatility ($\beta = 1.0$).
- **Single-constituent execution**: Standalone factor component computation (without `market_returns` supplied) uses total realized volatility ($\beta = 1.0$) as designed by specification.
- **Holdout quarantine**: The chronological holdout partition (2025-08-14 to 2026-08-21) remains strictly quarantined and untouched.

## 4. Conclusion

All six defects and requirements identified by the Reviewer and Challenger agents have been completely and genuinely resolved:
1. CAPM residual volatility length alignment operates correctly across heterogeneous histories without silent fallback to $\beta = 1.0$.
2. Momentum and reversion lookback windows enforce strict fail-closed sizing ($W + L + 1$) without window truncation.
3. Safe Decimal validation and finite float checks prevent crashes and NaN contamination.
4. Mypy and ruff exit cleanly with 0 errors.
5. Linear z-scoring executes in $O(N)$ time.
6. The test suite has been expanded to 11 unit tests in `test_ranking_engine.py` and 116 tests across `tests/test_xs_portfolio_alpha/`, all passing 100%.

## 5. Verification Method

To independently verify the implementation:
1. **Unit Test Suite**:
   ```powershell
   uv run pytest tests/test_xs_portfolio_alpha/test_ranking_engine.py -v
   ```
   *Expected output*: `11 passed in ~0.20s`, exit code 0.

2. **Full Alpha Test Suite**:
   ```powershell
   uv run pytest tests/test_xs_portfolio_alpha/ -v
   ```
   *Expected output*: `116 passed in ~1.7s`, exit code 0.

3. **Linter & Style Check**:
   ```powershell
   uv run ruff check src/quant_system/research_xs_monthly/ranking.py tests/test_xs_portfolio_alpha/test_ranking_engine.py
   ```
   *Expected output*: `All checks passed!`, exit code 0.

4. **Type Check**:
   ```powershell
   uv run mypy src/quant_system/research_xs_monthly/ranking.py tests/test_xs_portfolio_alpha/test_ranking_engine.py
   ```
   *Expected output*: `Success: no issues found in 2 source files`, exit code 0.

5. **Agent Claim & Disk Layout Audits**:
   ```powershell
   powershell -ExecutionPolicy Bypass -File scripts/audit-agent-claims.ps1
   powershell -ExecutionPolicy Bypass -File scripts/audit-disk-layout.ps1
   ```
   *Expected output*: Both report `RESULT: PASS`, exit code 0.
