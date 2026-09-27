# Handoff Report: M2 Tranche Ledger Circuit-Lock Stress Testing & Scale Benchmark

**Agent**: challenger_m2_2  
**Role**: Empirical Challenger (critic, specialist)  
**Target Module**: `src/quant_system/research_xs_monthly/tranche_ledger.py`  
**Verdict**: **REJECT** (Blocking until 1 Critical and 2 High defects are addressed)  
**Timestamp**: 2026-09-25T11:05:00Z  

---

## 1. Observation

### 1.1 Verbatim Code Observations
In `src/quant_system/research_xs_monthly/tranche_ledger.py`:

1. **Lines 169–174**:
   ```python
   # 1. Liquidate existing positions
   for sym, pos in list(tranche.positions.items()):
       is_locked = False
       if volumes is not None and volumes.get(sym, 1) == 0:
           is_locked = True
       if highs is not None and lows is not None and highs.get(sym) == lows.get(sym):
           is_locked = True
   ```
   and **Lines 195–198**:
   ```python
       if volumes is not None and volumes.get(sym, 1) == 0:
           continue
       if highs is not None and lows is not None and highs.get(sym) == lows.get(sym):
           continue
       eligible_buys.append(sym)
   ```
   When `highs` and `lows` dictionaries are passed but do not contain `sym` (e.g. unquoted, delisted, partial dictionary, or empty `{}`), `highs.get(sym)` evaluates to `None` and `lows.get(sym)` evaluates to `None`. In Python:
   ```python
   None == None  # Evaluates to True
   ```
   As a direct consequence, `highs.get(sym) == lows.get(sym)` evaluates to `True`, triggering `is_locked = True` on exit and skipping entry!

2. **Lines 179–186**:
   ```python
       if sym in open_prices:
           p_exit = open_prices[sym]
           proceeds = pos.quantity * p_exit
           fee = (proceeds * self.FEE_ONE_WAY).quantize(Decimal("0.01"))
           cash += (proceeds - fee)
           period_fees += fee
           sold_symbols.append(sym)
           del new_positions[sym]
   ```
   Unlike entry checks (line 193: `if open_prices[sym] <= Decimal("0.00"): continue`), exit liquidation performs no positivity or finiteness check on `p_exit`. If `open_prices[sym]` is negative (e.g. corrupted bar or negative synthetic price), `proceeds` is negative and `cash` is subtracted, driving cash balance negative.

3. **Lines 202–224**:
   ```python
   if eligible_buys and cash > Decimal("0.00"):
       capital_per_stock = cash / Decimal(len(eligible_buys))
       for sym in eligible_buys:
           p_open = open_prices[sym]
           ...
           if cash >= (cost + fee):
               cash -= (cost + fee)
               period_fees += fee
               new_positions[sym] = TranchePosition(...)
               bought_symbols.append(sym)
   ```
   `eligible_buys` is not deduplicated. If `selected_symbols` contains duplicates (e.g. `['INFY', 'INFY']`), cash is deducted on every loop iteration, but `new_positions[sym]` is overwritten. The capital spent on duplicate iterations vanishes from portfolio NAV.

4. **Line 86**:
   ```python
   k = int(len(ranked_symbols) * top_fraction)
   ```
   For universe sizes `N in [1, 4]` and default `top_fraction = 0.20`:
   `int(1 * 0.20) = 0`, `int(2 * 0.20) = 0`, `int(3 * 0.20) = 0`, `int(4 * 0.20) = 0`.
   The function returns `[]` for any universe smaller than 5 symbols.

### 1.2 Empirical Execution Output
Executed reproducible harness `D:\quant_system\tmp\stress_harness_m2_2.py` via Python 3.13:

```text
--- Running Test 1: Multi-Session Circuit Lock Stress Testing ---
1A. Volume == 0 lock for 3 consecutive periods:
    - Retained: LOCK_A (624 shares), LOCK_B (624 shares) through Periods 1, 2, 3.
    - Not sold or dropped. Fictitious liquidation proceeds = 0.
    - Period 4 lock lift: cleanly liquidated at market open.
1B. High == Low lock for 3 consecutive periods:
    - Retained: LIMIT_DOWN_1, LIMIT_DOWN_2 across 3 consecutive periods.
    - Not sold or dropped. Exposure <= 1.0000 maintained.
1C. Defect: missing_highs_lows_none_equal_none_vulnerability:
    - vulnerability_present: True
    - detail: highs.get(sym) == lows.get(sym) evaluates None == None as True when sym is missing from both dicts.
    - Liquid stock 'UNLOCKED_STOCK' could not be sold and remained locked in positions: ['UNLOCKED_STOCK'].

--- Running Test 2: Scale Benchmark (423 names, 50 rebalances) ---
{
  "status": "PASS",
  "universe_size": 423,
  "num_rebalances": 50,
  "total_duration_sec": 2.7779,
  "avg_rebalance_ms": 9.356,
  "max_rebalance_ms": 18.96,
  "avg_mark_to_market_ms": 1.468,
  "max_mark_to_market_ms": 2.624,
  "peak_memory_mb": 0.373,
  "final_nav": "9803237.02",
  "final_cash": "243761.57",
  "final_positions_value": "9559475.45",
  "final_exposure": "0.9751345836581639642943163278",
  "total_statutory_fees": "254852.18",
  "max_observed_exposure": 0.976809,
  "min_observed_exposure": 0.242405,
  "avg_circuit_locked_per_step": 7.88
}

--- Running Test 3: Degenerate Input Suite ---
- empty_open_prices_buy: bought = [], cash preserved, exposure = 0.
- empty_open_prices_exit: sold = [], positions safely retained.
- zero_capital_init: raises ValueError: "Initial capital must be strictly positive, got 0.00".
- negative_capital_init: raises ValueError: "Initial capital must be strictly positive, got -500.00".
- single_stock_top_quintile_truncation: len=1 -> [], len=2 -> [], len=3 -> [], len=4 -> [], len=5 -> 1.
- single_stock_direct_rebalance: bought=['SOLO'], qty=99, tranche_exposure=0.9911, total_exposure=0.2476 <= 1.0000.
- nan_price_buy: raises decimal.InvalidOperation (fail-closed).
- nan_price_exit: raises decimal.InvalidOperation, positions intact (atomic rollback).
- inf_price_buy: bought=[], skipped safely.
- inf_price_exit: raises decimal.InvalidOperation, positions intact.
- neg_price_exit_vulnerability: True, new_cash = "-1101.35".
- duplicate_selected_symbols_vulnerability: True, cash remaining = "973.12" (Rs 12,013.44 destroyed).
```

---

## 2. Logic Chain

1. **Premise 1**: Circuit lock detection on entry and exit is designed to test if a symbol is locked at its price band (`high == low`) or has zero trading volume (`volume == 0`).
2. **Observation**: Lines 172 and 197 evaluate `highs.get(sym) == lows.get(sym)` without checking whether `highs.get(sym)` is `None`.
3. **Inference 1**: In Python, when a key `sym` is absent from both dictionaries, `dict.get(sym)` returns `None`, and `None == None` evaluates to `True`.
4. **Deduction 1 (Defect 1 - Critical)**: When caller passes incomplete `highs`/`lows` maps (or `{}`), every missing symbol is falsely classified as circuit-locked. On exit, positions are permanently trapped and never liquidated. On entry, valid candidate symbols are silently excluded.
5. **Premise 2**: QuantOS financial laws and line 104 require cash balance `>= 0` at all times without borrowed capital or leverage violations.
6. **Observation**: Line 179 permits liquidation at negative `p_exit`, computing negative proceeds and deducting cash.
7. **Deduction 2 (Defect 2 - High)**: A negative exit price drives cash negative (`-1101.35`), directly violating the cash non-negativity invariant and creating artificial leverage in `mark_to_market`.
8. **Premise 3**: Accounting integrity requires that money deducted from cash must be accounted for in asset quantity and portfolio NAV.
9. **Observation**: Lines 202–224 iterate through `eligible_buys` without deduplication, repeatedly deducting `cost + fee` from cash while overwriting `new_positions[sym]`.
10. **Deduction 3 (Defect 3 - High)**: Duplicate candidate symbols cause cash to be paid multiple times for the same single position allotment, permanently destroying portfolio equity.
11. **Scale and Multi-Session Correctness**: When valid price and lock data are provided, multi-session retention functions correctly (locked positions are held without fictitious liquidation for 3+ consecutive periods), and scale performance is stellar (9.36 ms / rebalance, 0.373 MB peak RAM, exposure strictly <= 1.0000 across 50 cycles of 423 names).
12. **Conclusion**: Because Defects 1, 2, and 3 invalidate core execution and financial accounting guarantees in edge/production conditions, the implementation cannot be approved in its current state.

---

## 3. Caveats

1. The scale benchmark was executed using synthetic price drift paths over 423 names and 50 weekly rebalances, which mimics realistic turnover and circuit lock frequencies (~1.9%), but does not re-replay historical 10-year tick bars.
2. The benchmark measured in-memory ledger operations; disk I/O for bar loading is outside the scope of `tranche_ledger.py`.
3. `select_top_quintile` behavior on small universes (< 5) is mathematically consistent with `int(N * 0.20)`, but may surprise callers expecting at least 1 stock.
4. No caveats regarding the defects: Defects 1, 2, and 3 are 100% reproducible and algebraically proven.

---

## 4. Conclusion & Recommended Action

**Verdict: REJECT**

The implementation in `src/quant_system/research_xs_monthly/tranche_ledger.py` demonstrates excellent performance, strict Decimal arithmetic, and proper retention under nominal circuit locks. However, it must be **REJECTED** until the worker agent applies the following 3 necessary corrections:

1. **Fix Defect 1 (Critical)**:
   In `rebalance_tranche` (lines 172 and 197), change the circuit lock check from:
   ```python
   if highs is not None and lows is not None and highs.get(sym) == lows.get(sym):
   ```
   to:
   ```python
   if highs is not None and lows is not None:
       h = highs.get(sym)
       l = lows.get(sym)
       if h is not None and l is not None and h == l:
           is_locked = True
   ```
   and similarly for candidate buys at line 197.

2. **Fix Defect 2 (High)**:
   In `rebalance_tranche` (line 179), require that exit prices are strictly positive:
   ```python
   if sym in open_prices:
       p_exit = open_prices[sym]
       if p_exit <= Decimal("0.00"):
           # Treat unpriced or non-positive exit as locked/unexecutable
           continue
   ```

3. **Fix Defect 3 (High)**:
   In `rebalance_tranche` (line 190), deduplicate candidate symbols:
   ```python
   selected_symbols = list(dict.fromkeys(selected_symbols))
   ```

---

## 5. Verification Method

### How to independently reproduce:

1. **Execute standalone empirical harness**:
   ```powershell
   .venv\Scripts\python D:\quant_system\tmp\stress_harness_m2_2.py
   ```
   Verify that all benchmark metrics and defect flags are reported.

2. **Run existing pytest suite**:
   ```powershell
   .venv\Scripts\pytest tests/test_xs_portfolio_alpha/ -q
   ```
   Verify all 168 tests pass.

3. **Invalidation condition**:
   This rejection is invalidated when:
   - `highs.get(sym) is not None and lows.get(sym) is not None and highs.get(sym) == lows.get(sym)` is checked, so passing `{}` does not lock liquid names.
   - Non-positive exit prices cannot drive cash negative.
   - Duplicate candidate symbols cannot destroy cash.
