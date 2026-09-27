# Empirical Challenge Report: Milestone 2 Tranche Ledger Verification

**Agent**: challenger_m2_3  
**Roles**: critic, specialist  
**Date**: 2026-09-25T20:57:00+05:30  
**Target Files**:
- `src/quant_system/research_xs_monthly/tranche_ledger.py`
- `tests/test_xs_portfolio_alpha/test_tranche_ledger.py`
- `tests/test_xs_portfolio_alpha/test_challenger_m2_3_empirical.py`
**Verdict**: **APPROVE**  

---

## 1. Observation

1. **Source Code Inspection (`src/quant_system/research_xs_monthly/tranche_ledger.py`)**:
   - **Defect 1 & 2 Resolution (Circuit Lock Presence Check)**:
     Lines 174-178 (Exit check):
     ```python
     if highs is not None and lows is not None:
         h_price = highs.get(sym)
         l_price = lows.get(sym)
         if h_price is not None and l_price is not None and h_price == l_price:
             is_locked = True
     ```
     Lines 204-208 (Entry check):
     ```python
     if highs is not None and lows is not None:
         h_price = highs.get(sym)
         l_price = lows.get(sym)
         if h_price is not None and l_price is not None and h_price == l_price:
             continue
     ```
     `h_price is not None and l_price is not None` guarantees that omitted keys or empty dicts (`highs={}`, `lows={}`) do NOT evaluate `None == None` to `True`. Unquoted stocks and empty dict calls proceed normally without false circuit locks.
   - **Defect 3 Resolution (Duplicate Symbol Deduplication)**:
     Line 160:
     ```python
     selected_symbols = list(dict.fromkeys(selected_symbols))
     ```
     Deduplicates `selected_symbols` preserving insertion order prior to candidate filtering and capital distribution.
   - **Defect 4 Resolution (Non-positive Exit Price Guard)**:
     Lines 185-187:
     ```python
     p_exit = open_prices[sym]
     if p_exit <= Decimal("0.00"):
         continue
     ```
     Skips liquidation if `p_exit <= Decimal("0.00")`, preventing negative or zero proceeds from driving cash negative.
   - **Defect 5 Resolution (Strict Lookahead Guard)**:
     Lines 157-158:
     ```python
     if execution_date <= decision_date:
         raise ValueError(f"Execution date {execution_date} cannot precede decision date {decision_date}")
     ```
     Strictly raises `ValueError` for same-day (`execution_date == decision_date`) or past-day executions.

2. **Empirical Test Suite Execution Results**:
   - Authored `tests/test_xs_portfolio_alpha/test_challenger_m2_3_empirical.py` containing 15 empirical tests and stress-fuzzing harnesses targeting all 5 verification conditions.
   - Executed `uv run pytest tests/test_xs_portfolio_alpha/test_challenger_m2_3_empirical.py -v -s`:
     ```
     15 passed in 0.15s
     [Stress Fuzzing] 200 cycles executed in 0.043s. All invariants held.
     ```
   - Executed `uv run pytest tests/test_xs_portfolio_alpha/ -v`:
     ```
     188 passed in 1.90s (100% pass rate)
     ```
   - Executed `uv run ruff check tests/test_xs_portfolio_alpha/test_challenger_m2_3_empirical.py src/quant_system/research_xs_monthly/tranche_ledger.py`:
     ```
     All checks passed!
     ```
   - Executed `uv run mypy tests/test_xs_portfolio_alpha/test_challenger_m2_3_empirical.py src/quant_system/research_xs_monthly/tranche_ledger.py`:
     ```
     Success: no issues found in 2 source files
     ```
   - Executed `powershell -ExecutionPolicy Bypass -File scripts/audit-agent-claims.ps1`:
     ```
     RESULT: PASS - every workspace has a visible claim and every claim resolves.
     ```
   - Executed `powershell -ExecutionPolicy Bypass -File scripts/audit-disk-layout.ps1`:
     ```
     RESULT: PASS - no stray QuantOS directories.
     ```

---

## 2. Logic Chain

1. From Observation 1, the presence check `h_price is not None and l_price is not None` evaluates to `False` whenever either key is missing or when empty dictionaries (`highs={}`, `lows={}`) are passed. Under Observation 2, `test_empirical_empty_highs_lows_does_not_lock_buys`, `test_empirical_empty_highs_lows_does_not_lock_sells`, and `test_empirical_empty_highs_lows_with_empty_volumes` all passed with 100% fill/liquidation and zero skipped stocks.
2. From Observation 1, in partial dicts, only keys present in both `highs` and `lows` with identical values trigger `is_locked = True`. Under Observation 2, `test_empirical_partial_highs_lows_unquoted_not_locked_on_buy` and `test_empirical_partial_highs_lows_unquoted_not_locked_on_exit` confirmed that symbols with high-only, low-only, high!=low, and omitted keys are correctly traded, while only identical high==low symbols are locked.
3. From Observation 1, `selected_symbols = list(dict.fromkeys(selected_symbols))` guarantees distinct symbol entries. Under Observation 2, `test_empirical_duplicate_symbols_exact_accounting_and_no_cash_destruction` proved that when `["INFY", "INFY", "TCS", "INFY", "TCS", "TCS"]` is passed, exactly 2 positions are established with exact 50/50 capital split (12,500.00 each), single fee deduction (11.2 bps), and zero cash loss. 100-fold duplicates (`["SOLO"] * 100`) allocated exactly 1 single position without double charging.
4. From Observation 1, `if p_exit <= Decimal("0.00"): continue` halts liquidation for non-positive exit prices. Under Observation 2, `test_empirical_zero_exit_price_does_not_drain_cash`, `test_empirical_negative_exit_price_does_not_drain_cash`, and `test_empirical_mixed_exit_prices_positive_sold_non_positive_held` verified that positions with prices `<= 0.00` are retained as locked positions without liquidating at negative prices or reducing cash. Cash remained non-negative (`cash >= 0.00`) in all scenarios.
5. From Observation 1, `execution_date <= decision_date` triggers `ValueError`. Under Observation 2, `test_empirical_same_day_execution_strictly_raises_value_error` verified that same-day execution (`T == T`) raises `ValueError` and atomically preserves state (fail-closed), while `T+1` execution succeeds.
6. Under Observation 2, a 200-cycle randomized multi-dimensional stress fuzzing harness combining extreme duplicate symbol lists, corrupted negative/zero prices, partial dictionaries, and circuit locks completed in 0.043s with zero assertion errors: `cash >= Decimal("0.00")` and `total_exposure <= Decimal("1.0000")` held at every cycle.
7. Under Observation 2, all 188 unit, acceptance, adversarial, and empirical tests in `tests/test_xs_portfolio_alpha/` passed, with clean Ruff, Mypy, claim audit, and disk layout audit checks.
8. Therefore, all 4 defects are definitively resolved, mathematically sound, and empirically verified.

---

## 3. Caveats

1. The ledger operates on calendar dates passed into `rebalance_tranche`. Trading holiday / exchange calendar validation is assumed to be handled upstream by the calendar builder (`bars.py`).
2. Tranche positions with non-positive exit prices are held until a positive open price is observed or until the strategy driver forcibly writes off the asset.
3. No other caveats.

---

## 4. Conclusion

**Verdict: APPROVE**

The edge-case defects identified in Milestone 2 have been thoroughly resolved in `src/quant_system/research_xs_monthly/tranche_ledger.py`:
- Empty dicts `highs={}` and `lows={}` do NOT lock candidate buys or liquidations.
- Partial high/low dicts do NOT lock unquoted stocks.
- Duplicate candidate symbols are safely deduplicated with exact capital allocation and fee accounting.
- Non-positive exit prices cannot drive cash negative.
- Same-day execution (`execution_date <= decision_date`) strictly fails closed with `ValueError`.

All 188 automated tests pass (100%), static typing and linting pass with zero warnings, and repo governance audits pass cleanly. Milestone 2 is ready for full release.

---

## 5. Verification Method

To independently verify this evaluation:

```powershell
# 1. Run the empirical challenger test suite (15 tests + 200-cycle fuzzing)
uv run pytest tests/test_xs_portfolio_alpha/test_challenger_m2_3_empirical.py -v -s

# 2. Run the complete portfolio alpha test suite (188 tests)
uv run pytest tests/test_xs_portfolio_alpha/ -v

# 3. Verify static typing and formatting
uv run ruff check src/quant_system/research_xs_monthly/tranche_ledger.py tests/test_xs_portfolio_alpha/test_challenger_m2_3_empirical.py
uv run mypy src/quant_system/research_xs_monthly/tranche_ledger.py tests/test_xs_portfolio_alpha/test_challenger_m2_3_empirical.py

# 4. Verify repo claims and disk layout integrity
powershell -ExecutionPolicy Bypass -File scripts/audit-agent-claims.ps1
powershell -ExecutionPolicy Bypass -File scripts/audit-disk-layout.ps1
```

**Invalidation conditions**:
- Any failure in `pytest`.
- Any candidate buy skipped when `highs={}` and `lows={}` are passed.
- Cash loss when duplicate symbols are provided in `selected_symbols`.
- Negative cash when exit price is non-positive.
- `execution_date <= decision_date` does not raise `ValueError`.
