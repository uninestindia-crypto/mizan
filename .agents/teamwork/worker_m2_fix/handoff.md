# Handoff Report: Milestone 2 Tranche Ledger Edge-Case Refinements

**Agent**: worker_m2_fix  
**Roles**: implementer, qa, specialist  
**Date**: 2026-09-25T20:53:00+05:30  
**Target Files**:
- `src/quant_system/research_xs_monthly/tranche_ledger.py`
- `tests/test_xs_portfolio_alpha/test_tranche_ledger.py`
**Status**: COMPLETED  

---

## 1. Observation

1. **Defect 1 (`None == None` circuit-lock false trigger)**:
   In `src/quant_system/research_xs_monthly/tranche_ledger.py`:
   - Prior code (lines 172-173 and 197-198):
     ```python
     if highs is not None and lows is not None and highs.get(sym) == lows.get(sym):
     ```
   - When a symbol was omitted from `highs` and `lows` (or when `highs={}` and `lows={}` were passed), `highs.get(sym)` returned `None` and `lows.get(sym)` returned `None`. Because `None == None` evaluates to `True`, unquoted or omitted stocks were falsely classified as circuit locked, blocking all buys and preventing liquidation on exit.
2. **Defect 2 (Duplicate `selected_symbols` cash destruction)**:
   - Prior code iterated over `eligible_buys` containing duplicates from `selected_symbols`. Cash was deducted on each iteration while `new_positions[sym]` was overwritten, permanently destroying portfolio equity without corresponding shares.
3. **Defect 3 (Non-positive exit prices driving cash negative)**:
   - Prior exit liquidation did not verify `p_exit > Decimal("0.00")`. A price `<= 0.00` resulted in zero or negative proceeds, deducting from cash balance.
4. **Defect 4 (Same-day execution permitted)**:
   - Prior check `if execution_date < decision_date:` allowed `execution_date == decision_date`, failing to strictly enforce next-session (T+1) execution.
5. **Tool Commands and Results**:
   - `uv run pytest tests/test_xs_portfolio_alpha/test_tranche_ledger.py -v`: 35 passed in 0.21s (all 30 baseline tests + 5 new regression tests).
   - `uv run pytest tests/test_xs_portfolio_alpha/test_e2e_acceptance.py -v`: 105 passed in 1.92s.
   - `uv run pytest tests/test_xs_portfolio_alpha/test_tranche_ledger_adversarial.py -v`: 22 passed in 0.13s.
   - `uv run pytest tests/test_xs_portfolio_alpha/ -v`: 173 passed in 1.69s (100% pass rate).
   - `uv run ruff check src/quant_system/research_xs_monthly/tranche_ledger.py tests/test_xs_portfolio_alpha/test_tranche_ledger.py`: All checks passed!
   - `uv run mypy src/quant_system/research_xs_monthly/tranche_ledger.py tests/test_xs_portfolio_alpha/test_tranche_ledger.py`: Success: no issues found in 2 source files.
   - `scripts/audit-agent-claims.ps1`: Exit 0 (PASS - every workspace has a visible claim and every claim resolves).
   - `scripts/audit-disk-layout.ps1`: Exit 0 (PASS - no stray QuantOS directories).

---

## 2. Logic Chain

1. From Observation 1, checking equality without verifying key presence causes `None == None` to be `True`. We repaired both exit (lines 174-178) and entry (lines 203-207) checks to retrieve `h_price = highs.get(sym)` and `l_price = lows.get(sym)` and assert `if h_price is not None and l_price is not None and h_price == l_price:`. This guarantees that omitted or empty dictionaries never trigger a lock.
2. From Observation 2, we added `selected_symbols = list(dict.fromkeys(selected_symbols))` at the top of `rebalance_tranche`. This preserves ranking order while guaranteeing uniqueness, ensuring each symbol receives exactly one capital allocation, is bought once, and reconciles cash precisely.
3. From Observation 3, in the exit liquidation loop, we added `if p_exit <= Decimal("0.00"): continue`. This skips selling if the exit price is non-positive or corrupted, leaving the existing position safely intact/held without deducting cash.
4. From Observation 4, we tightened the lookahead guard to `if execution_date <= decision_date: raise ValueError(...)`. This strictly enforces that execution occurs on session T+1 or later.
5. In `tests/test_xs_portfolio_alpha/test_tranche_ledger.py`, we added 5 regression tests explicitly validating:
   - `test_circuit_lock_empty_highs_lows_dicts_never_locks_symbols`: verifies empty dicts do not block buys or sells.
   - `test_circuit_lock_partial_highs_lows_dicts_behavior`: verifies partial dicts only lock matching symbols and permit unquoted symbols.
   - `test_rebalance_duplicate_symbols_preserves_cash_and_single_allocation`: verifies duplicate inputs retain exact cash accounting without double deduction.
   - `test_rebalance_non_positive_exit_prices_safely_held_as_locked`: verifies non-positive exit prices carry over positions without reducing cash.
   - `test_rebalance_lookahead_same_day_execution_rejected`: verifies same-day rebalance is rejected.
6. From Observation 5, all 173 tests in `tests/test_xs_portfolio_alpha/` pass cleanly with zero linting or type violations, and claim/disk layout audits pass.

---

## 3. Caveats

1. Upstream data feeds are assumed to provide valid session dates; non-trading days/weekends are filtered by the calendar builder.
2. The ledger tracks cash and positions in memory; persistence to disk is handled by the calling driver and evidence stores.
3. No other caveats.

---

## 4. Conclusion

All 4 defects identified during Milestone 2 adversarial review and challenge are resolved in `src/quant_system/research_xs_monthly/tranche_ledger.py`. Five comprehensive regression unit tests have been added to `tests/test_xs_portfolio_alpha/test_tranche_ledger.py`. All 173 portfolio alpha tests, Ruff, Mypy, and repository audit scripts pass with zero errors. Milestone 2 is ready for approval.

---

## 5. Verification Method

To independently verify the changes:

```powershell
# 1. Run all unit tests for tranche ledger (including the 5 new regression tests)
uv run pytest tests/test_xs_portfolio_alpha/test_tranche_ledger.py -v

# 2. Run full e2e acceptance suite
uv run pytest tests/test_xs_portfolio_alpha/test_e2e_acceptance.py -v

# 3. Run all tests in the package
uv run pytest tests/test_xs_portfolio_alpha/ -v

# 4. Verify static typing and style
uv run ruff check src/quant_system/research_xs_monthly/tranche_ledger.py tests/test_xs_portfolio_alpha/test_tranche_ledger.py
uv run mypy src/quant_system/research_xs_monthly/tranche_ledger.py tests/test_xs_portfolio_alpha/test_tranche_ledger.py

# 5. Run audit scripts
powershell -ExecutionPolicy Bypass -File scripts/audit-agent-claims.ps1
powershell -ExecutionPolicy Bypass -File scripts/audit-disk-layout.ps1
```

**Invalidation conditions**:
- Any failure in `pytest`.
- Candidate buy skipped when `highs={}` and `lows={}` are passed.
- Cash loss when duplicate symbols are provided in `selected_symbols`.
- Negative cash when exit price is non-positive.
- `execution_date <= decision_date` does not raise `ValueError`.
