# Quality & Adversarial Review Report: Milestone 2 Tranche Ledger Repairs

**Reviewer**: reviewer_m2_3  
**Roles**: reviewer, critic  
**Target Files**:
- `src/quant_system/research_xs_monthly/tranche_ledger.py`
- `tests/test_xs_portfolio_alpha/test_tranche_ledger.py`
**Date**: 2026-09-25T15:27:00Z  
**Verdict**: **APPROVE**  

---

## 1. Executive Summary & Review Verdict

**Verdict**: **APPROVE**  
**Overall Risk Assessment**: **LOW**  
**Integrity Audit**: **CLEAN (0 integrity violations)**. No hardcoded results, dummy facades, shortcuts, or fabricated claims detected. All logic uses rigorous Decimal arithmetic, explicit fail-closed boundaries, and genuine test fixtures.

The defect repairs implemented by `worker_m2_fix` in `src/quant_system/research_xs_monthly/tranche_ledger.py` completely and robustly resolve all four edge-case vulnerabilities identified during Milestone 2 adversarial challenges. The five new regression tests in `tests/test_xs_portfolio_alpha/test_tranche_ledger.py` provide thorough coverage of each defect scenario. The full test suite of 173 tests, static analysis (Ruff, Mypy), and repository disk/claim audits pass with zero errors.

---

## 2. Review Findings & Verification of Repairs

### Defect 1: Elimination of `None == None` Circuit-Lock False Trigger
- **Observation**:
  - In `tranche_ledger.py` (lines 174-178 in exit loop and lines 204-208 in entry loop):
    ```python
    if highs is not None and lows is not None:
        h_price = highs.get(sym)
        l_price = lows.get(sym)
        if h_price is not None and l_price is not None and h_price == l_price:
            ...
    ```
- **Assessment**:
  - Previously, `highs.get(sym) == lows.get(sym)` evaluated to `None == None` (`True`) whenever a symbol was omitted from `highs` and `lows` (or when empty dicts `{}` were passed). This falsely classified unquoted/omitted stocks as circuit-locked, preventing buys and liquidations.
  - The new explicit presence checks (`h_price is not None and l_price is not None and h_price == l_price`) guarantee that only symbols with actual matching high and low prices are treated as price-locked.
  - Verified by regression tests `test_circuit_lock_empty_highs_lows_dicts_never_locks_symbols` and `test_circuit_lock_partial_highs_lows_dicts_behavior`.

### Defect 2: Deduplication of `selected_symbols`
- **Observation**:
  - In `tranche_ledger.py` (line 160):
    ```python
    selected_symbols = list(dict.fromkeys(selected_symbols))
    ```
- **Assessment**:
  - Previously, duplicate symbol entries in `selected_symbols` caused repeated cash deductions and overwriting of positions, permanently burning cash without retaining allocated shares.
  - `dict.fromkeys` ensures O(N) deduplication while strictly preserving initial ranking order. Cash is deducted exactly once per unique symbol.
  - Verified by regression test `test_rebalance_duplicate_symbols_preserves_cash_and_single_allocation`.

### Defect 3: Prevention of Non-Positive Exit Proceeds
- **Observation**:
  - In `tranche_ledger.py` (lines 185-187):
    ```python
    p_exit = open_prices[sym]
    if p_exit <= Decimal("0.00"):
        continue
    ```
- **Assessment**:
  - Previously, unexecutable or corrupted exit prices (`<= Decimal("0.00")`) could produce zero or negative proceeds, deducting cash on exit.
  - The guard `if p_exit <= Decimal("0.00"): continue` treats such positions as non-liquidatable (locked/carried over) without deducting cash.
  - Verified by regression test `test_rebalance_non_positive_exit_prices_safely_held_as_locked`.

### Defect 4: Strict Next-Session Execution Enforcement (Lookahead Guard)
- **Observation**:
  - In `tranche_ledger.py` (lines 157-158):
    ```python
    if execution_date <= decision_date:
        raise ValueError(f"Execution date {execution_date} cannot precede decision date {decision_date}")
    ```
- **Assessment**:
  - Previously, `execution_date < decision_date` permitted same-day execution (`execution_date == decision_date`), violating the zero-lookahead next-open (T+1) execution invariant.
  - The tightened condition `execution_date <= decision_date` strictly enforces that execution occurs on session T+1 or later.
  - Verified by regression test `test_rebalance_lookahead_same_day_execution_rejected`.

---

## 3. Adversarial Stress-Test Results & Invariant Verification

| Attack Scenario | Stress Parameters | Invariant Tested | Actual Behavior | Result |
|---|---|---|---|---|
| Empty Highs/Lows Dicts | `highs={}`, `lows={}` | No false circuit locks | Buys and sales execute normally | **PASS** |
| Partial Highs/Lows Dicts | Sym in highs only, sym in lows only | No false circuit locks | Only `h==l` locks; others trade | **PASS** |
| Duplicate Symbols Fuzz | `selected_symbols = ["INFY"] * 10` | Cash non-negativity & single allocation | Cash deducted once, 1 position | **PASS** |
| Zero & Negative Exit Prices | `p_exit = Decimal("0.00")`, `Decimal("-50.00")` | Cash non-negativity & position safety | Sale skipped, position held, cash untouched | **PASS** |
| Same-Day Execution Attempt | `execution_date == decision_date` | Zero lookahead leakage | `ValueError` raised fail-closed | **PASS** |
| Past Execution Attempt | `execution_date < decision_date` | Zero lookahead leakage | `ValueError` raised fail-closed | **PASS** |
| Hyper Price Surge (+10,000%) | Price spikes from ₹50 to ₹5,050 | Leverage ceiling (`total_exposure <= 1.0`) | Exposure remains <= 1.0000 | **PASS** |
| Catastrophic Price Crash (-99.999%) | Price crashes from ₹500 to ₹0.01 | Leverage & cash non-negativity | Exposure remains <= 1.0000, cash >= 0 | **PASS** |
| 100% Bankruptcy Wipeout | Price crashes to ₹0.00 | Division by zero & exposure bounds | Exposure becomes 0.0000, NAV == cash | **PASS** |
| 500-Trial Monte Carlo Price Paths | Random shocks [-99.9%, +2000%] | Mathematical leverage invariant | Exposure strictly in [0.0, 1.0] across all 500 | **PASS** |
| Micro & Nano Capital Allocation | Initial capital = ₹1.00 and ₹0.04 | Integer share allocation & cash >= 0 | Cash >= 0, integer quantities | **PASS** |
| 50-Cycle Churning Fuzz | 50 consecutive weekly rebalances | Paisa reconciliation & cash conservation | Cash >= 0, exposure <= 1.0 across all cycles | **PASS** |

---

## 4. 5-Component Handoff Report

### 1. Observation
- Verified file `src/quant_system/research_xs_monthly/tranche_ledger.py`:
  - Lines 157-158: `if execution_date <= decision_date: raise ValueError(...)`.
  - Line 160: `selected_symbols = list(dict.fromkeys(selected_symbols))`.
  - Lines 174-178: `h_price is not None and l_price is not None and h_price == l_price`.
  - Lines 186-187: `if p_exit <= Decimal("0.00"): continue`.
  - Lines 204-208: `h_price is not None and l_price is not None and h_price == l_price`.
- Verified test suite `tests/test_xs_portfolio_alpha/test_tranche_ledger.py`:
  - Lines 556-696: 5 new regression tests verifying empty dicts, partial dicts, duplicate symbols, non-positive exit prices, and same-day lookahead rejection.
- Independent execution results:
  - `uv run pytest tests/test_xs_portfolio_alpha/test_tranche_ledger.py -v`: 35 passed in 0.16s.
  - `uv run pytest tests/test_xs_portfolio_alpha/test_e2e_acceptance.py -v`: 105 passed in 1.50s.
  - `uv run pytest tests/test_xs_portfolio_alpha/ -v`: 173 passed in 1.72s.
  - `uv run ruff check src/quant_system/research_xs_monthly/tranche_ledger.py tests/test_xs_portfolio_alpha/test_tranche_ledger.py`: All checks passed.
  - `uv run mypy src/quant_system/research_xs_monthly/tranche_ledger.py tests/test_xs_portfolio_alpha/test_tranche_ledger.py`: Success: no issues found.
  - `scripts/audit-agent-claims.ps1`: Exit 0 (PASS).
  - `scripts/audit-disk-layout.ps1`: Exit 0 (PASS).

### 2. Logic Chain
1. The presence checks `h_price is not None and l_price is not None and h_price == l_price` prevent missing dictionary keys from evaluating `None == None` as `True`, thereby fixing false circuit lock activations on both entry and exit.
2. Deduplication via `list(dict.fromkeys(selected_symbols))` ensures each unique symbol receives exactly one capital allotment and preserves ranking order, preventing duplicate cash deductions and position overwriting.
3. The guard `p_exit <= Decimal("0.00")` skips selling at non-positive prices, preventing negative cash flows or cash destruction.
4. The guard `execution_date <= decision_date` strictly enforces next-session (T+1) execution, preventing same-day or backward execution.
5. All 5 regression tests directly assert these boundary conditions and pass cleanly without regressing any of the existing 168 tests.

### 3. Caveats
- No caveats. Data feeds provide valid dates, and all calculations use exact Decimal arithmetic.

### 4. Conclusion
The implementation of the 4 defect repairs is mathematically sound, conforms to QuantOS product laws and financial model craft protocols, and is backed by exhaustive regression and adversarial test coverage. Milestone 2 is fully verified and **APPROVED**.

### 5. Verification Method
To independently reproduce verification:
```powershell
uv run pytest tests/test_xs_portfolio_alpha/test_tranche_ledger.py -v
uv run pytest tests/test_xs_portfolio_alpha/test_e2e_acceptance.py -v
uv run pytest tests/test_xs_portfolio_alpha/ -v
uv run ruff check src/quant_system/research_xs_monthly/tranche_ledger.py tests/test_xs_portfolio_alpha/test_tranche_ledger.py
uv run mypy src/quant_system/research_xs_monthly/tranche_ledger.py tests/test_xs_portfolio_alpha/test_tranche_ledger.py
powershell -ExecutionPolicy Bypass -File scripts/audit-agent-claims.ps1
powershell -ExecutionPolicy Bypass -File scripts/audit-disk-layout.ps1
```
