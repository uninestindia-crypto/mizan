# Handoff Report: Empirical Verification of CAPM Length Alignment and NaN Robustness (M1)

**Agent**: challenger_m1_3  
**Working Directory**: `D:\quant_system\.agents\teamwork\challenger_m1_3`  
**Target Module**: `src/quant_system/research_xs_monthly/ranking.py`  
**Verdict**: **APPROVE**  
**Date**: 2026-09-25T10:30:00Z  

---

## 1. Observation

Direct empirical observations from independent stress harnesses, test execution, static analysis, and fault injection:

1. **CAPM Residual Volatility Alignment with Heterogeneous Histories**:
   - In `src/quant_system/research_xs_monthly/ranking.py` (`compute_idiosyncratic_volatility`, lines 224–228):
     ```python
     if market_returns is not None:
         needed_bars = len(market_returns) + 1
         if len(valid_bars) < needed_bars:
             return None
         tail_bars = valid_bars[-needed_bars:]
     ```
     `tail_bars` is dynamically sliced to `len(market_returns) + 1`, ensuring `len(returns) == len(market_returns)` exactly for any admitted constituent having $\ge \text{needed\_bars}$.
   - **Empirical Test Universe 1 (63, 64, 100, 252 bars)**:
     - Synthetic test universe constructed with non-zero variance market returns and varied history horizons:
       * `SYM_63` (63 bars): Filtered out in Step 1 (`min_history_bars = 64`), failing closed.
       * `SYM_64` (64 bars): Executed CAPM OLS regression cleanly, yielding `market_beta = 1.1478`, `idio_vol = 0.001628`.
       * `SYM_100` (100 bars): Executed CAPM OLS regression cleanly, yielding `market_beta = 0.3525`, `idio_vol = 0.001930`.
       * `SYM_252` (252 bars): Executed CAPM OLS regression cleanly, yielding `market_beta = 1.4997`, `idio_vol = 0.001913`.
     - Zero symbols fell back to `beta = 1.0`.
   - **Empirical Test Universe 2 (8 Heterogeneous Histories: 64, 75, 100, 150, 200, 252, 350, 500 bars)**:
     - All 8 symbols ranked successfully with distinct regression betas:
       * `SYM_350`: Beta `0.8494`, IdioVol `0.00259`, Rank 1
       * `SYM_200`: Beta `-0.4639`, IdioVol `0.00444`, Rank 2
       * `SYM_100`: Beta `0.3518`, IdioVol `0.00096`, Rank 3
       * `SYM_75`: Beta `1.6616`, IdioVol `0.00273`, Rank 4
       * `SYM_252`: Beta `1.4135`, IdioVol `0.00202`, Rank 5
       * `SYM_150`: Beta `1.9217`, IdioVol `0.00205`, Rank 6
       * `SYM_500`: Beta `1.7067`, IdioVol `0.00211`, Rank 7
       * `SYM_64`: Beta `0.5592`, IdioVol `0.00179`, Rank 8
     - Zero symbols fell back to `beta = 1.0`.
   - **Standalone Beta Accuracy Benchmark**:
     - Tested `compute_factor_components` directly with injected betas (1.8, 0.6, 1.2):
       * `SYM_64`: computed beta `1.8000` (expected 1.80)
       * `SYM_100`: computed beta `0.6000` (expected 0.60)
       * `SYM_252`: computed beta `1.2000` (expected 1.20)
     - Error $< 10^{-4}$, none fell back to `beta = 1.0`.

2. **Decimal('NaN') and float('nan') Protections & Fail-Closed Behavior**:
   - **Decision Bar Fault Injection**:
     - Tested decision bars on `as_of_date` containing:
       * `close = Decimal('NaN')`: returned `None` (no exception)
       * `open = Decimal('NaN')`: returned `None` (no exception)
       * `high = Decimal('NaN')`: returned `None` (no exception)
       * `low = Decimal('NaN')`: returned `None` (no exception)
       * `close = Decimal('sNaN')`: returned `None` (no exception)
       * `close = Decimal('Infinity')`: returned `None` (no exception)
       * `close = Decimal('-Infinity')`: returned `None` (no exception)
       * `close = float('nan')`: returned `None` (no exception)
     - `_is_finite_positive_decimal` safely caught all invalid Decimal and float operations inside `try/except` without raising `decimal.InvalidOperation`.
   - **Historical Bar Fault Injection**:
     - Injected `Decimal('NaN')`, `float('nan')`, `Decimal('Infinity')`, and `float('inf')` at:
       * Index 0 (start of momentum window)
       * Index 20/30 (middle of volatility estimation window)
       * Index 60 (inside 5-day reversion window)
     - All calls to `compute_intermediate_momentum`, `compute_short_term_reversion`, `compute_idiosyncratic_volatility`, and `compute_factor_components` returned `None` and failed closed.

3. **Universe Ranking Integrity Under Corrupted Inputs**:
   - Evaluated a universe of 16 symbols containing 3 legitimate clean stocks (`SYM_TOP`, `SYM_MID`, `SYM_LOW`) and 13 corrupted stocks:
     1. `CORRUPT_DEC_NAN_DEC` (Decision bar close Decimal('NaN'))
     2. `CORRUPT_DEC_NAN_START` (History start close Decimal('NaN'))
     3. `CORRUPT_DEC_NAN_MID` (History middle close Decimal('NaN'))
     4. `CORRUPT_FLOAT_NAN_MID` (History middle close float('nan'))
     5. `CORRUPT_FLOAT_NAN_DEC` (Decision bar close float('nan'))
     6. `CORRUPT_DEC_INF` (History middle close Decimal('Infinity'))
     7. `CORRUPT_DEC_NEG_INF` (History middle close Decimal('-Infinity'))
     8. `CORRUPT_FLOAT_INF` (History middle close float('inf'))
     9. `CORRUPT_FLOAT_NEG_INF` (History middle close float('-inf'))
     10. `CORRUPT_CROSSED` (Decision bar high < low)
     11. `CORRUPT_ZERO_PRICE` (Decision bar close == 0)
     12. `CORRUPT_NEG_PRICE` (History middle close == -10)
     13. `CORRUPT_CIRCUIT_LOCKED` (Decision bar volume == 0, high == low)
   - Results:
     * `rank_universe` executed with zero unhandled exceptions.
     * Output contained exactly 3 ranked symbols: `['SYM_TOP', 'SYM_MID', 'SYM_LOW']`.
     * All 13 corrupted symbols were completely excluded.
     * The composite scores, ranks, betas, and idiosyncratic volatilities of the 3 clean symbols matched their clean baseline **down to 6 decimal places** (`SYM_TOP` rank 1 score 6650.352170, `SYM_MID` rank 2 score -943.694732, `SYM_LOW` rank 3 score -5706.657437).
     * Zero ranking inversion or metric pollution occurred.

4. **Test Suite, Static Analysis & Audits**:
   - `uv run pytest tests/test_xs_portfolio_alpha/test_ranking_engine.py -v`:
     `11 passed in 0.18s` (exit code 0)
   - `uv run pytest tests/test_xs_portfolio_alpha/ -v`:
     `116 passed in 2.10s` (exit code 0)
   - `uv run ruff check src/quant_system/research_xs_monthly/ranking.py tests/test_xs_portfolio_alpha/test_ranking_engine.py`:
     `All checks passed!` (exit code 0)
   - `uv run mypy src/quant_system/research_xs_monthly/ranking.py tests/test_xs_portfolio_alpha/test_ranking_engine.py`:
     `Success: no issues found in 2 source files` (exit code 0)
   - `powershell -ExecutionPolicy Bypass -File scripts/audit-agent-claims.ps1`:
     `RESULT: PASS - every workspace has a visible claim and every claim resolves.` (exit code 0)

---

## 2. Logic Chain

1. **CAPM Vector Length Slicing Logic**:
   - In previous iterations, `market_returns` was computed using `w_effective` derived from the shortest history in the universe, while constituent returns were sliced using a fixed lookback window. When history was heterogeneous, array lengths diverged (`len(market_returns) != len(returns)`), silently triggering fallback to total realized volatility and `beta = 1.0`.
   - The current implementation sets `needed_bars = len(market_returns) + 1` whenever `market_returns` is provided. Slicing `tail_bars = valid_bars[-needed_bars:]` guarantees that `len(returns) == len(market_returns)` mathematically across any number of historical bars ($\ge 64$).
   - Observation 1 confirmed this empirically across 64, 100, 252, and 500-bar histories: regression executed with actual betas without fallback to 1.0.

2. **Fail-Closed Decimal and IEEE-754 NaN Validation Logic**:
   - Standard relational operators (`<`, `<=`) on `Decimal('NaN')` raise `decimal.InvalidOperation`. In Python float arithmetic, comparisons with `float('nan')` evaluate to `False`, allowing NaNs to bypass simple `<= 0.0` filters.
   - The implementation introduced `_is_finite_positive_decimal(val)` which safely wraps `not (val.is_nan() or val.is_infinite()) and val > Decimal(0)` inside a `try/except` block.
   - Factor kernels explicitly verify `math.isfinite(c)` and `c > 0.0` for all historical prices.
   - Observation 2 confirmed that decision-bar and historical NaNs/Infs fail closed (return `None`) without throwing exceptions.

3. **Universe Ranking Integrity Logic**:
   - In Step 1 of `rank_universe`, invalid symbols are excluded prior to universe aggregation.
   - In Step 2, `sym_returns` filters out any symbol where `closes` contains non-finite or non-positive values, and `market_returns` is only adopted if all its elements are strictly finite.
   - In Step 4, only symbols with finite factor components are admitted into the z-scoring stage, preventing NaN pollution of `mean` and `std`.
   - Observation 3 confirmed that injecting 13 malformed/corrupted symbols into a universe left the clean symbols completely unharmed and in their true rank order.

---

## 3. Caveats

- **Universe market return quorum**: If fewer than 2 valid symbols qualify in `rank_universe`, `market_returns` is set to `None`, triggering the designed fallback to total realized volatility ($\beta = 1.0$).
- **Standalone execution**: Calling `compute_factor_components` without passing `market_returns` uses total realized volatility ($\beta = 1.0$), which is the documented contract for single-asset evaluation without a universe context.
- **Holdout quarantine**: The chronological holdout partition (2025-08-14 to 2026-08-21) remains strictly quarantined and untouched.

---

## 4. Conclusion

**Verdict: APPROVE**

The M1 Multi-Factor Composite Ranking Engine (`src/quant_system/research_xs_monthly/ranking.py`) has completely and genuinely resolved both reported defects:
1. CAPM residual volatility length mismatch is resolved: symbols with heterogeneous histories (64, 100, 252, 500 bars) execute CAPM regression without falling back to $\beta = 1.0$.
2. Decimal('NaN'), float('nan'), and infinite price protections operate correctly: malformed bars fail closed without unhandled exceptions and with zero corruption or inversion of universe rankings.
3. The codebase passes all 116 tests, 0 ruff errors, 0 mypy errors, and passes agent claim audits.

---

## 5. Verification Method

To independently reproduce all empirical findings:

1. **Verify CAPM Heterogeneous Histories (64, 100, 252 bars)**:
   ```powershell
   uv run python -c "
   import math
   from datetime import date, timedelta
   from decimal import Decimal
   import numpy as np
   from quant_system.research_xs_monthly.bars import Bar
   from quant_system.research_xs_monthly.ranking import MultiFactorRankingEngine, FactorConfig

   start = date(2024, 1, 1)
   calendar = []
   d = start
   while len(calendar) < 300:
       if d.weekday() < 5:
           calendar.append(d)
       d += timedelta(days=1)
   as_of = calendar[-1]

   np.random.seed(123)
   m_rets = [0.01 * math.sin(i / 4.0) + 0.005 * np.random.randn() for i in range(300)]

   def make_bars(sym, n_bars, beta):
       sub_cal = calendar[-n_bars:]
       sub_m = m_rets[-n_bars:]
       p = 100.0
       prices = [p]
       for i in range(1, n_bars):
           r = beta * sub_m[i] + 0.002 * np.random.randn()
           p = p * (1.0 + r)
           prices.append(p)
       return [
           Bar(sym, dt, Decimal(str(round(px, 4))), Decimal(str(round(px + 1.0, 4))),
               Decimal(str(round(max(px - 1.0, 0.01), 4))), Decimal(str(round(px, 4))), 100000)
           for dt, px in zip(sub_cal, prices)
       ]

   bars_by_sym = {'SYM_64': make_bars('SYM_64', 64, 1.5), 'SYM_100': make_bars('SYM_100', 100, 0.5), 'SYM_252': make_bars('SYM_252', 252, 2.0)}
   engine = MultiFactorRankingEngine(FactorConfig())
   rankings = engine.rank_universe(as_of, list(bars_by_sym.keys()), bars_by_sym)
   for r in rankings:
       assert r.components.market_beta != 1.0, f'{r.symbol} fell back to 1.0!'
       print(r.symbol, 'Beta:', r.components.market_beta, 'IdioVol:', r.components.idiosyncratic_volatility_63)
   print('CAPM VERIFICATION SUCCESS')
   "
   ```

2. **Verify Universe Ranking Integrity Under 13 Corrupted Symbols**:
   Execute the empirical corruption harness documented in Section 1 (Obs 3).

3. **Run Unit and Full Suite Tests**:
   ```powershell
   uv run pytest tests/test_xs_portfolio_alpha/test_ranking_engine.py -v
   uv run pytest tests/test_xs_portfolio_alpha/ -v
   ```

4. **Run Static Analysis and Agent Claim Audits**:
   ```powershell
   uv run ruff check src/quant_system/research_xs_monthly/ranking.py tests/test_xs_portfolio_alpha/test_ranking_engine.py
   uv run mypy src/quant_system/research_xs_monthly/ranking.py tests/test_xs_portfolio_alpha/test_ranking_engine.py
   powershell -ExecutionPolicy Bypass -File scripts/audit-agent-claims.ps1
   ```
