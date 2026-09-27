# Worker M1 Fix Dispatch Note
Assigned to worker_m1_fix.

## 2026-09-25T10:12:21Z
You are worker_m1_fix.
Your working directory is: D:\quant_system\.agents\teamwork\worker_m1_fix

MANDATORY: You MUST read D:\quant_system\.agents\teamwork\ORIGINAL_REQUEST.md before doing anything else.
Read D:\quant_system\.agents\teamwork\PROJECT.md for architecture, contracts, and code layout.

MANDATORY INTEGRITY WARNING:
DO NOT CHEAT. All implementations must be genuine. DO NOT hardcode test results, create dummy/facade implementations, or circumvent the intended task. A teamwork_preview_auditor will independently verify your work. Integrity violations WILL be detected and your work WILL be rejected.

Reviews and challenges from Iteration 1 found specific critical defects in `src/quant_system/research_xs_monthly/ranking.py` and `tests/test_xs_portfolio_alpha/test_ranking_engine.py`. Read the detailed findings in:
- `D:\quant_system\.agents\teamwork\reviewer_m1_1\handoff.md`
- `D:\quant_system\.agents\teamwork\reviewer_m1_2\handoff.md`
- `D:\quant_system\.agents\teamwork\challenger_m1_2\handoff.md`

Your tasks:
1. Fix CAPM Residual Volatility length alignment in `ranking.py`:
   - In `FactorConfig`, update `min_history_bars: int = 64` (requiring at least 64 bars for 63 return sessions).
   - In `compute_idiosyncratic_volatility`, when `market_returns` is provided, slice `tail_bars = valid_bars[-(len(market_returns) + 1):]` so that `len(returns) == len(market_returns)` exactly. This completely prevents established stocks from silently falling back to total volatility and beta=1.0.
2. Fix Window Sizing and Fail-Closed Behavior:
   - In `compute_intermediate_momentum` and `compute_short_term_reversion`: require `len(valid_bars) < window + lag + 1: return None`.
   - Remove `if abs(idx_start) > len(valid_bars): idx_start = 0`. Never silently truncate lookback windows!
3. Robust Finite & Positive Validation (Prevent Crashes & Contamination):
   - Implement a safe helper:
     ```python
     def _is_finite_positive_decimal(val: Decimal) -> bool:
         try:
             return not (val.is_nan() or val.is_infinite()) and val > Decimal(0)
         except Exception:
             return False
     ```
   - In `compute_factor_components` and `rank_universe`, validate `open`, `high`, `low`, and `close` using `_is_finite_positive_decimal`, and check `last_bar.high >= last_bar.low`.
   - In `compute_intermediate_momentum`, `compute_short_term_reversion`, and `compute_idiosyncratic_volatility`, check `math.isfinite(c)` and `c > 0.0`.
   - In `rank_universe`, filter out any symbol with non-finite score before computing universe mean/std, preventing NaN contamination of the ranking.
4. Fix Unused Type Ignores in Tests:
   - In `tests/test_xs_portfolio_alpha/test_ranking_engine.py`, remove the redundant `# type: ignore[import-untyped]` comments on lines 22-23 so `mypy` exits with 0 errors.
5. Performance Optimization:
   - In `rank_universe`, compute `mean_v` and `std_v` outside the symbol loop for `linear_zscore`.
6. Expand Unit Tests in `tests/test_xs_portfolio_alpha/test_ranking_engine.py`:
   - Add test verifying heterogeneous history lengths (64 bars vs 100 bars) proving CAPM residual volatility is computed for all eligible symbols without fallback to beta=1.0.
   - Add test verifying that `lag > 0` with insufficient history returns `None` rather than a truncated window return.
   - Add test verifying fail-closed rejection of `Decimal('NaN')` and `float('nan')` without throwing `decimal.InvalidOperation` or inverting ranking.
7. Verification:
   - `uv run pytest tests/test_xs_portfolio_alpha/test_ranking_engine.py -v`
   - `uv run pytest tests/test_xs_portfolio_alpha/ -v`
   - `uv run ruff check src/quant_system/research_xs_monthly/ranking.py tests/test_xs_portfolio_alpha/test_ranking_engine.py`
   - `uv run mypy src/quant_system/research_xs_monthly/ranking.py tests/test_xs_portfolio_alpha/test_ranking_engine.py`
8. Write 5-component handoff report to `D:\quant_system\.agents\teamwork\worker_m1_fix\handoff.md`.
9. Send completion message to orchestrator via send_message.
