# Independent Review & Adversarial Challenge Report — reviewer_m1_2
**Milestone**: M1 (R1 Multi-Factor Composite Ranking Engine)  
**Target Code**: `src/quant_system/research_xs_monthly/ranking.py`, `tests/test_xs_portfolio_alpha/test_ranking_engine.py`  
**Reviewer**: `reviewer_m1_2` (Roles: reviewer, critic)  
**Date**: 2026-09-25T10:12:00Z  
**Verdict**: **`REQUEST_CHANGES`**

---

## Executive Summary

An objective and adversarial examination of `src/quant_system/research_xs_monthly/ranking.py` and `tests/test_xs_portfolio_alpha/test_ranking_engine.py` was conducted. While `worker_m1` has constructed a well-structured engine with passing unit tests (`8 passed in 0.25s`), zero `ruff` linter violations, and zero `mypy` typing errors, deep mathematical stress-testing revealed **two Critical defects** and **two Major defects** in the core mathematical kernels that invalidate the claim of robust point-in-time cross-sectional factor ranking:

1. **Critical Defect 1 (Silent Bypass of CAPM Regression)**: When universe constituents have unequal history lengths (e.g. one symbol has 63 bars while others have $\ge 64$ bars), `w_effective` shrinks to 62, creating a 62-session market return vector. Because all symbols with $\ge 64$ bars calculate 63 returns, line 222 detects an array length mismatch ($62 \ne 63$) and **silently falls back to total realized volatility with $\beta = 1.0$ for the vast majority of the universe**.
2. **Critical Defect 2 (Window Truncation & Fail-Closed Violation in Momentum/Reversion)**: If history is shorter than `window + lag + 1` sessions, lines 151-152 and 184-185 clamp `idx_start = 0`. Instead of failing closed and returning `None`, the kernels calculate a return over an arbitrarily truncated window (e.g. 48 sessions when 85 are requested), destroying cross-sectional comparability.
3. **Major Defect 3 (Unhandled NaN / Non-Finite Floats)**: Neither bar prices nor returns are checked for `math.isfinite()`. An unhandled `NaN` price or score bypasses `< 0` checks and poisons `np.mean` and `np.std` in cross-sectional z-score standardization, turning the entire universe score vector into all-NaN and corrupting Python Timsort order.
4. **Moderate Defect 4 (Unchecked Calendar Date Alignment)**: Slicing by array offset (`-(w_effective + 1):`) in market return estimation assumes all symbols traded on identical calendar dates without verifying date equality.

Because these defects directly compromise the mathematical soundness, cross-sectional comparability, and fail-closed integrity required by the QuantOS Financial Model Craft protocol, the review verdict is **`REQUEST_CHANGES`**.

---

## 1. Observation

### 1.1 Baseline Verification Results
The verification commands mandated by the dispatch instructions were executed:
1. `uv run pytest tests/test_xs_portfolio_alpha/test_ranking_engine.py -v`:
   ```
   ============================== 8 passed in 0.25s ==============================
   ```
2. `uv run ruff check src/quant_system/research_xs_monthly/ranking.py tests/test_xs_portfolio_alpha/test_ranking_engine.py`:
   ```
   All checks passed!
   ```
3. `uv run mypy src/quant_system/research_xs_monthly/ranking.py tests/test_xs_portfolio_alpha/test_ranking_engine.py`:
   ```
   Success: no issues found in 2 source files
   ```

### 1.2 Direct Code Observations & Counter-Examples

#### Observation 1: Array Length Mismatch & Silent Fallback in CAPM Regression
In `src/quant_system/research_xs_monthly/ranking.py`:
- Line 58, 63:
  ```python
  volatility_window: int = 63
  min_history_bars: int = 63
  ```
- Lines 380-383:
  ```python
  w_vol = self.config.volatility_window
  min_bars = min(len(vb) for vb in valid_bars_by_sym.values())
  w_effective = min(w_vol, min_bars - 1)
  ```
- Lines 387-396:
  ```python
  tail = vbars[-(w_effective + 1) :]
  closes = [float(b.close) for b in tail]
  rets = [(closes[t] - closes[t - 1]) / closes[t - 1] for t in range(1, len(closes))]
  if len(rets) == w_effective:
      sym_returns.append(rets)
  if sym_returns:
      market_returns = [
          float(np.mean([sym_returns[s][t] for s in range(len(sym_returns))]))
          for t in range(w_effective)
      ]
  ```
- Line 310:
  ```python
  vol_res = compute_idiosyncratic_volatility(
      valid_bars,
      as_of_date,
      market_returns=market_returns,
      window=self.config.volatility_window, # hardcoded 63!
  )
  ```
- Lines 212-225:
  ```python
  tail_bars = valid_bars[-(window + 1) :] if len(valid_bars) >= window + 1 else valid_bars
  closes = [float(b.close) for b in tail_bars]
  ...
  returns = [(closes[t] - closes[t - 1]) / closes[t - 1] for t in range(1, len(closes))]
  ...
  if market_returns is None or len(market_returns) != len(returns):
      tot_vol = float(np.std(returns, ddof=1))
      tot_vol = max(tot_vol, 1e-6)
      return (tot_vol, 1.0)
  ```

**Stress-Test Counter-Example**:
When ranking a universe where 1 symbol has 63 bars and 9 symbols have 100 bars:
```python
engine = MultiFactorRankingEngine()
ranked = engine.rank_universe(as_of, list(bars_dict.keys()), bars_dict)
for r in ranked:
    print(r.symbol, "beta:", r.components.market_beta, "idio_vol:", r.components.idiosyncratic_volatility_63)
```
**Observed Output**:
```
SYM1:  beta=1.30555, idio_vol=0.000100 (true residual vol via CAPM)
SYM2:  beta=1.00000, idio_vol=0.000260 (total vol fallback, CAPM bypassed!)
SYM3:  beta=1.00000, idio_vol=0.000260 (total vol fallback, CAPM bypassed!)
...
SYM10: beta=1.00000, idio_vol=0.000260 (total vol fallback, CAPM bypassed!)
```
**Impact**: 90% of the universe had their CAPM regression silently aborted and replaced with total volatility and beta=1.0 due to an unhandled off-by-one length mismatch.

#### Observation 2: Window Truncation Instead of Fail-Closed in Momentum and Reversion
In `src/quant_system/research_xs_monthly/ranking.py`:
- Lines 147-158 (`compute_intermediate_momentum`):
  ```python
  idx_end = -1 - lag
  if abs(idx_end) > len(valid_bars):
      return None
  idx_start = -1 - lag - window
  if abs(idx_start) > len(valid_bars):
      idx_start = 0  # <--- SILENT WINDOW TRUNCATION!
  
  c_end = float(valid_bars[idx_end].close)
  c_start = float(valid_bars[idx_start].close)
  if c_start <= 0.0 or c_end <= 0.0:
      return None
  return (c_end - c_start) / c_start
  ```
- Lines 180-190 (`compute_short_term_reversion`):
  ```python
  idx_end = -1 - lag
  if abs(idx_end) > len(valid_bars):
      return None
  idx_start = -1 - lag - window
  if abs(idx_start) > len(valid_bars):
      idx_start = 0  # <--- SILENT WINDOW TRUNCATION!
  ```

**Stress-Test Counter-Example**:
When requesting a 63-session momentum with 21-session lag (`window=63, lag=21`, requiring $63 + 21 + 1 = 85$ bars) on a series with 70 bars:
```python
ret = compute_intermediate_momentum(bars_70, as_of, window=63, lag=21)
print(ret) # Outputs: 0.48
```
**Impact**: Rather than returning `None`, the function silently calculated a 48-session return between bar 0 and bar 48, presenting it as a 63-session momentum score.

#### Observation 3: Lack of Non-Finite Protection and Z-Score Poisoning
In `src/quant_system/research_xs_monthly/ranking.py`:
- Lines 156, 188, 214 check `c <= 0.0`. In IEEE 754 floating-point arithmetic, `float('nan') <= 0.0` evaluates to `False`.
- If a bar price contains `NaN` or a return produces `NaN`, `compute_intermediate_momentum` returns `NaN`.
- In `rank_universe` lines 417-422:
  ```python
  moms = [comp.intermediate_momentum_21_63 for comp in preliminary.values()]
  mean_m = float(np.mean(moms))
  std_m = float(np.std(moms))
  ```
  If a single constituent contains `NaN`, `np.mean` and `np.std` evaluate to `NaN`.
- In step 5, sorting `candidates.sort(key=lambda item: (-item[1], item[0]))` with `NaN` keys violates strict weak ordering, producing non-deterministic permutation rankings.

---

## 2. Logic Chain

1. **Premise 1 (QuantOS Financial Model Craft Law)**: Financial calculations must fail closed on invalid, incomplete, or out-of-bounds data; they must never fill missing data with favorable defaults or silent truncations (`financial-model-craft/SKILL.md` § Non-negotiable invariants).
2. **Premise 2 (Discrete Return Timing)**: To compute $W$ discrete period returns or look back $W$ sessions from bar $T$, an array of closing prices must contain at least $W + \text{lag} + 1$ elements. An array of length $W$ contains only $W - 1$ return intervals.
3. **Step 1**: In `ranking.py`, `FactorConfig.min_history_bars` is set to 63, allowing stocks with 63 bars into universe ranking. When a 63-bar stock is present, `w_effective` drops to $63 - 1 = 62$, creating a 62-session market return vector (Observation 1).
4. **Step 2**: Slicing in `compute_idiosyncratic_volatility` uses `window = 63` and extracts 64 bars ($63+1$) for every stock with $\ge 64$ bars, producing 63 individual returns.
5. **Step 3**: Line 222 compares the lengths: `len(market_returns) != len(returns)` ($62 \ne 63$). Because they do not match, the CAPM OLS regression is aborted, and total volatility is substituted for all stocks with $\ge 64$ bars (Observation 1).
6. **Step 4**: Furthermore, lines 151-152 clamp `idx_start = 0` whenever `abs(idx_start) > len(valid_bars)` instead of returning `None`, silently returning returns over truncated windows (Observation 2).
7. **Step 5**: Because `worker_m1` tested only homogeneous universes where every symbol had exactly $n=64$ bars, none of the 8 unit tests in `test_ranking_engine.py` exercised these heterogeneous or boundary paths.
8. **Conclusion**: The ranking engine fails to deliver sound, robust, and comparable CAPM residual volatility and momentum factor scores under heterogeneous data conditions. Changes must be requested.

---

## 3. Caveats

- **No Code Changes**: In adherence to the reviewer role constraints ("Review-only — do NOT modify implementation code"), no production files were modified by this agent.
- **Unit Test Integrity**: No integrity violations (hardcoded test outputs or dummy facades) were detected in `worker_m1`'s work. The code is genuinely implemented, but contains algorithmic and boundary design flaws.
- **Cache Ingestion Scope**: Upstox market cache dataset blobs were not present in the local workspace directory, so end-to-end evaluation was verified on synthetic multi-instrument fixture matrices.

---

## 4. Conclusion & Verdict

**Verdict**: **`REQUEST_CHANGES`**

### Required Action Items for Worker:

1. **Fix History Window & Array Length Sizing**:
   - In `FactorConfig`, update `min_history_bars: int = 64` (or dynamically enforce `len(valid_bars) >= window + lag + 1`).
   - In `compute_idiosyncratic_volatility`, ensure that `returns` is computed over exactly `window` sessions by requiring `len(valid_bars) >= window + 1`. If `len(valid_bars) < window + 1`, fail closed and return `None`.
   - In `rank_universe`, compute `market_returns` strictly over `self.config.volatility_window` sessions. If an eligible symbol does not have `volatility_window + 1` bars, exclude it during Step 1.
2. **Eliminate Silent Window Truncation (Fail Closed)**:
   - In `compute_intermediate_momentum`:
     ```python
     needed_bars = 1 + lag + window
     if len(valid_bars) < needed_bars:
         return None
     ```
     Remove `if abs(idx_start) > len(valid_bars): idx_start = 0`. If `abs(idx_start) > len(valid_bars)`, return `None`.
   - In `compute_short_term_reversion`:
     ```python
     needed_bars = 1 + lag + window
     if len(valid_bars) < needed_bars:
         return None
     ```
     Remove `idx_start = 0` clamping; return `None`.
3. **Guard Against Non-Finite and NaN Values**:
   - Check `math.isfinite(c)` for all price inputs. If non-finite, fail closed (`return None`).
   - In `compute_idiosyncratic_volatility`, verify `math.isfinite(ret)` on all computed returns.
   - In `rank_universe`, filter out any symbol whose score is non-finite before standardizing z-scores or sorting candidates.
4. **Expand Unit Test Suite in `test_ranking_engine.py`**:
   - Add a test verifying universe ranking with mixed bar counts (e.g. 64 bars vs 100 bars) proving that CAPM residual volatility is computed for all eligible symbols without fallback to beta=1.0.
   - Add a test verifying that `lag > 0` with insufficient history returns `None` rather than a truncated window return.
   - Add a test verifying fail-closed rejection of `NaN` prices.

---

## 5. Verification Method

To independently reproduce and verify the findings:
1. Run the heterogeneous universe stress-test script:
   ```powershell
   uv run python -c "
   from datetime import date, timedelta
   from decimal import Decimal
   from quant_system.research_xs_monthly.bars import Bar
   from quant_system.research_xs_monthly.ranking import MultiFactorRankingEngine

   start = date(2025, 1, 1)
   def make_bars(sym, n):
       return [Bar(sym, start + timedelta(days=i), Decimal(str(100+i*0.5)), Decimal(str(101+i*0.5)), Decimal(str(99+i*0.5)), Decimal(str(100+i*0.5)), 1000) for i in range(n)]

   b_dict = {'SYM1': make_bars('SYM1', 63)}
   as_of = b_dict['SYM1'][-1].exchange_date
   for k in range(2, 6):
       sym = f'SYM{k}'
       full = make_bars(sym, 100)
       delta = as_of - full[-1].exchange_date
       b_dict[sym] = [Bar(sym, b.exchange_date + delta, b.open, b.high, b.low, b.close, b.volume) for b in full]

   engine = MultiFactorRankingEngine()
   ranked = engine.rank_universe(as_of, list(b_dict.keys()), b_dict)
   for r in ranked:
       print(r.symbol, 'beta:', r.components.market_beta, 'idio_vol:', r.components.idiosyncratic_volatility_63)
   "
   ```
   **Expected Failure**: SYM2..SYM5 have `beta: 1.0` and fallback total volatility instead of CAPM residual volatility.
2. Run the lag truncation stress-test script:
   ```powershell
   uv run python -c "
   from datetime import date
   from tests.test_xs_portfolio_alpha.test_ranking_engine import _generate_bars
   from quant_system.research_xs_monthly.ranking import compute_intermediate_momentum

   bars_70 = _generate_bars('SYM', date(2025, 1, 1), [100.0 + i for i in range(70)])
   ret = compute_intermediate_momentum(bars_70, bars_70[-1].exchange_date, window=63, lag=21)
   print('Calculated return for 70 bars when 85 needed:', ret)
   "
   ```
   **Expected Failure**: Computes a truncated return `0.48` instead of returning `None`.
3. Standard test suite pass check:
   ```powershell
   uv run pytest tests/test_xs_portfolio_alpha/test_ranking_engine.py -v
   uv run ruff check src/quant_system/research_xs_monthly/ranking.py tests/test_xs_portfolio_alpha/test_ranking_engine.py
   uv run mypy src/quant_system/research_xs_monthly/ranking.py tests/test_xs_portfolio_alpha/test_ranking_engine.py
   ```
