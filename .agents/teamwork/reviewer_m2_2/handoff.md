# Milestone 2 (R2) Review & Adversarial Challenge Report: Staggered Tranche Portfolio Ledger

**Reviewer Agent**: `reviewer_m2_2`  
**Roles**: Reviewer, Adversarial Critic  
**Date**: 2026-09-25T10:48:00Z  
**Verdict**: **REQUEST_CHANGES**  
**Overall Risk Assessment**: **MEDIUM-HIGH** (2 functional defects identified in edge cases / accounting)

---

## 1. Executive Summary

We conducted an independent quality review and adversarial stress-testing of `src/quant_system/research_xs_monthly/tranche_ledger.py` and its accompanying test suite `tests/test_xs_portfolio_alpha/test_tranche_ledger.py`.

The core architecture, 4-tranche autonomous weekly staggered structure, integer share purchasing (`//`), next-open (T+1) execution timing, and exact 0.224% round-trip statutory fee model (11.2 bps entry + 11.2 bps exit) are well-conceived and mostly implemented with sound Decimal precision.

However, adversarial edge-case analysis surfaced **two significant defects**:
1. **Critical/Major Edge-Case Defect**: `highs.get(sym) == lows.get(sym)` evaluates to `True` (`None == None`) when a symbol is omitted from `highs` and `lows` dictionaries (or when `highs={}` and `lows={}` are passed). This falsely classifies every omitted stock as circuit-locked, preventing all candidate purchases and blocking liquidation of all existing positions.
2. **Major Accounting Defect**: If `selected_symbols` contains duplicate symbols, the rebalance loop deducts cash and charges fees multiple times while silently overwriting `new_positions[sym]`, resulting in instantaneous and permanent capital destruction.

Because of these findings, our verdict is **REQUEST_CHANGES** with concrete, minimal fix recommendations provided below.

---

## 2. Review & Adversarial Findings

### [Critical / Major] Finding 1: False Circuit-Lock Trigger on Missing Symbols via `None == None`

- **What**: When `highs` and `lows` dictionaries are provided to `rebalance_tranche` but do not contain a specific symbol (or when empty dicts `highs={}` and `lows={}` are supplied), `highs.get(sym)` returns `None` and `lows.get(sym)` returns `None`. Because `None == None` is `True` in Python, the code treats the stock as circuit-locked.
- **Where**: `src/quant_system/research_xs_monthly/tranche_ledger.py`, lines 172–173 (exit liquidation) and lines 197–198 (entry filter):
  ```python
  # Line 172-173 (Exit liquidation):
  if highs is not None and lows is not None and highs.get(sym) == lows.get(sym):
      is_locked = True

  # Line 197-198 (Entry filtering):
  if highs is not None and lows is not None and highs.get(sym) == lows.get(sym):
      continue
  ```
- **Why this is a problem**:
  1. On entry: Any symbol whose high/low prices are not in the dictionary (e.g. if the caller only passes high/low for flagged symbols, or passes `highs={}` and `lows={}`) is erroneously deemed locked and skipped from purchasing.
  2. On exit: Any held position whose symbol is not in `highs` and `lows` is marked `is_locked = True`, preventing liquidation and trapping the position indefinitely.
  3. In contrast, the volume check correctly handles missing keys using `volumes.get(sym, 1) == 0` (defaulting to 1, i.e. not locked).
- **Reproduction**:
  ```python
  # Passing highs={} and lows={} blocks all buys:
  l = StaggeredTrancheLedger(Decimal("100000"))
  res = l.rebalance_tranche(0, date(2024, 1, 1), date(2024, 1, 2), ["INFY"], {"INFY": Decimal("100")}, highs={}, lows={})
  # Output: res.bought_symbols == []  (INFY skipped because None == None)
  ```
- **Suggested Fix**:
  Require that the symbol actually exists in the dictionaries:
  ```python
  # Exit liquidation (line 172):
  if highs is not None and lows is not None and sym in highs and sym in lows and highs[sym] == lows[sym]:
      is_locked = True

  # Entry filtering (line 197):
  if highs is not None and lows is not None and sym in highs and sym in lows and highs[sym] == lows[sym]:
      continue
  ```

---

### [Major] Finding 2: Cash Destruction and Silent Overwrite on Duplicate `selected_symbols`

- **What**: If `selected_symbols` contains duplicate symbols (e.g. `["INFY", "INFY"]`), `rebalance_tranche` deducts cash and charges statutory fees for each instance, but overwrites `new_positions[sym]` with only the final iteration's position quantity.
- **Where**: `src/quant_system/research_xs_monthly/tranche_ledger.py`, lines 189–224:
  ```python
  capital_per_stock = cash / Decimal(len(eligible_buys))
  for sym in eligible_buys:
      ...
      qty = int(capital_per_stock // effective_price)
      if qty > 0:
          cost = qty * p_open
          fee = (cost * self.FEE_ONE_WAY).quantize(Decimal("0.01"))
          if cash >= (cost + fee):
              cash -= (cost + fee)
              period_fees += fee
              new_positions[sym] = TranchePosition(...)
              bought_symbols.append(sym)
  ```
- **Why this is a problem**:
  With `initial_capital = Decimal("100000.00")` (Tranche cash = 25,000.00) and `selected_symbols = ["INFY", "INFY"]` at price 100.00:
  - Iteration 1 buys 124 shares, sets `positions['INFY'] = 124`, cash becomes 12,586.11.
  - Iteration 2 buys 124 shares, overwrites `positions['INFY'] = 124`, cash becomes 172.22.
  - Total NAV collapses from 25,000.00 to 12,572.22. Exactly 12,413.89 rupees in portfolio capital evaporates into nothingness without any position backing it.
- **Reproduction**:
  ```python
  l = StaggeredTrancheLedger(Decimal("100000"))
  res = l.rebalance_tranche(0, date(2024, 1, 1), date(2024, 1, 2), ["INFY", "INFY"], {"INFY": Decimal("100")})
  # Cash left: 172.22, Quantity held: 124 shares. Total NAV = 12,572.22 (50% loss!).
  ```
- **Suggested Fix**:
  Deduplicate `selected_symbols` at the beginning of `rebalance_tranche` while preserving ranking order:
  ```python
  # At top of rebalance_tranche:
  selected_symbols = list(dict.fromkeys(selected_symbols))
  ```

---

### [Minor] Finding 3: Execution Date Look-Ahead Check Allows Same-Day Execution

- **What**: Line 158 checks `if execution_date < decision_date: raise ValueError(...)`.
- **Where**: `src/quant_system/research_xs_monthly/tranche_ledger.py`, line 157–158:
  ```python
  if execution_date < decision_date:
      raise ValueError(f"Execution date {execution_date} cannot precede decision date {decision_date}")
  ```
- **Why**: Requirement R2 and PROJECT.md §3 specify "Next-Open Execution (T+1): Fill orders at session T+1 open price". Allowing `execution_date == decision_date` permits same-day rebalance if called mistakenly.
- **Suggested Fix**: Change condition to:
  ```python
  if execution_date <= decision_date:
      raise ValueError(f"Execution date {execution_date} must be strictly after decision date {decision_date}")
  ```

---

## 3. Adversarial Stress-Test Matrix

| # | Stress Scenario | Input / Condition | Expected Behavior | Actual Behavior | Result |
|---|-----------------|-------------------|-------------------|-----------------|--------|
| 1 | Empty `highs`/`lows` dicts | `highs={}, lows={}` | Missing high/low treated as unconstrained (not locked) | `None == None` triggers, all buys skipped, all sells locked | **FAIL** (Finding 1) |
| 2 | Partial `highs`/`lows` dicts | `highs={'TCS': 100}, lows={'TCS': 90}`, `symbols=['TCS', 'INFY']` | INFY has no lock data, traded normally | INFY has `None == None`, skipped as locked | **FAIL** (Finding 1) |
| 3 | Duplicate symbol list | `selected_symbols=['INFY', 'INFY']` | Deduplicate symbols or accumulate shares | Deducts cash twice, overwrites position once; capital lost | **FAIL** (Finding 2) |
| 4 | Zero / Negative Capital | `StaggeredTrancheLedger(Decimal("0.00"))` | Fail closed with `ValueError` | Raises `ValueError("Initial capital must be strictly positive")` | **PASS** |
| 5 | Micro-Capital (< 1 Rupee) | `initial_capital = Decimal("0.01")` | Quantizes to 0.00 cash, no division by zero | Handles 0.00 cash safely, 0 buys, 0 exposure | **PASS** |
| 6 | Empty price dict in rebalance | `open_prices = {}` | No trades, safe fallback to entry price, exposure valid | 0 buys, positions carried over, exposure <= 1.0000 | **PASS** |
| 7 | Empty price dict in MTM | `current_prices = {}` in `mark_to_market` | Evaluates positions at entry/current price | Correctly returns `LedgerNAV` with total_exposure <= 1.0000 | **PASS** |
| 8 | Extreme Surge (+300%) | Prices jump from 100.00 to 400.00 | NAV increases, exposure strictly <= 1.0000 | Total exposure <= 1.0000 | **PASS** |
| 9 | Extreme Crash (-90%) | Prices collapse from 100.00 to 10.00 | NAV decreases, exposure strictly <= 1.0000 | Total exposure <= 1.0000 | **PASS** |
| 10 | Exact 0.224% Fee Model | Round-trip entry at 100.00, exit at 100.00 | 11.2 bps on entry, 11.2 bps on exit, paise quantization | Symmetric fees, exact cash reconciliation | **PASS** |
| 11 | Integer Share Rounding | Odd price 777.77, capital per stock 8,333.33 | Strict integer quantity, cash >= 0 | `qty = 10` (int), non-negative cash | **PASS** |
| 12 | Backward Execution Date | `execution_date < decision_date` | Fail closed with `ValueError` | Raises `ValueError` | **PASS** |

---

## 4. Integrity Check

Under adversarial critic protocols, we verified source code and test files for integrity violations:
- **Hardcoded test results or expected outputs embedded in source code**: None found. Real generic arithmetic is implemented.
- **Dummy or facade implementations**: None found. Full stateful subledgers are maintained.
- **Shortcuts bypassing the intended task**: None found.
- **Fabricated verification outputs or logs**: None found. All test runs were executed live and verified.
- **Evidence of self-certifying work**: None found.

Integrity Status: **PASS** (Zero integrity violations). The identified defects are authentic logic and edge-case bugs.

---

## 5. Verification Results

We independently ran all required verification commands:

1. **Unit Test Suite**:
   ```powershell
   uv run pytest tests/test_xs_portfolio_alpha/test_tranche_ledger.py -v
   ```
   *Result*: **30 passed in 0.24s** (Exit Code 0).

2. **End-to-End Acceptance Suite**:
   ```powershell
   uv run pytest tests/test_xs_portfolio_alpha/test_e2e_acceptance.py -v
   ```
   *Result*: **105 passed in 1.88s** (Exit Code 0).

3. **Linter Check**:
   ```powershell
   uv run ruff check src/quant_system/research_xs_monthly/tranche_ledger.py tests/test_xs_portfolio_alpha/test_tranche_ledger.py
   ```
   *Result*: **All checks passed!** (Exit Code 0).

4. **Static Type Check**:
   ```powershell
   uv run mypy src/quant_system/research_xs_monthly/tranche_ledger.py tests/test_xs_portfolio_alpha/test_tranche_ledger.py
   ```
   *Result*: **Success: no issues found in 2 source files** (Exit Code 0).

*Note on test results*: While existing tests pass 100%, the existing test suites only test circuit locks where the symbol is explicitly present in both `highs` and `lows` dictionaries with identical values. Neither suite tests the case where `highs` and `lows` are passed but omit some or all symbols, nor do they test duplicate symbols in `selected_symbols`.

---

## 6. 5-Component Handoff Report

### 1. Observation
- `src/quant_system/research_xs_monthly/tranche_ledger.py`:
  * Lines 172–173: `if highs is not None and lows is not None and highs.get(sym) == lows.get(sym): is_locked = True`
  * Lines 197–198: `if highs is not None and lows is not None and highs.get(sym) == lows.get(sym): continue`
  * Direct execution: `highs={}; lows={}; sym='INFY'; highs.get(sym) == lows.get(sym)` yields `True`.
  * Lines 189–224: `eligible_buys` retains duplicate symbols from `selected_symbols`. Running with `['INFY', 'INFY']` results in cash deduction of 24,827.78 but positions only holding 124 shares (worth 12,400.00), wiping out 12,413.89 in NAV.
- Static verification commands (`pytest`, `ruff`, `mypy`) all completed with exit code 0.

### 2. Logic Chain
1. Requirement R2 and user instructions explicitly require handling edge cases: "Check edge cases: zero division, empty price dicts, circuit locks on both buys and sells, zero capital."
2. The current circuit lock implementation tests equality `highs.get(sym) == lows.get(sym)`. When a symbol is not present in both dicts, both `.get()` calls return `None`, and `None == None` evaluates to `True`.
3. This creates a severe false positive: any stock without explicit high/low quotes is treated as locked at limit. If a caller provides empty dictionaries `highs={}` and `lows={}`, 100% of candidate stocks are rejected and 100% of held positions are frozen.
4. Furthermore, because `selected_symbols` is not deduplicated, duplicate symbols cause double cash deduction and single position overwrite, violating the fundamental accounting identity `total_nav == cash + positions_value`.
5. Therefore, despite all existing tests passing, the code possesses critical defects under realistic operational edge cases and cannot be approved in its current form.

### 3. Caveats
- Intra-holding-period corporate actions (e.g. stock splits occurring during the 21-session holding period) are assumed to be handled upstream by adjusted bar prices before passing into `rebalance_tranche` and `mark_to_market`.
- Market impact and liquidity slippage beyond the statutory 0.224% fee model are excluded by design per R2 specifications.

### 4. Conclusion
We issue a verdict of **REQUEST_CHANGES**. The worker must implement the following two mandatory fixes and add corresponding unit tests:
1. Fix circuit-lock logic in `src/quant_system/research_xs_monthly/tranche_ledger.py` lines 172 and 197 to verify `sym in highs and sym in lows` before comparing equality.
2. Deduplicate `selected_symbols` in `rebalance_tranche` (`list(dict.fromkeys(selected_symbols))`) to prevent duplicate execution and cash destruction.
3. (Recommended) Strengthen line 157 to enforce `execution_date <= decision_date` rejection.
4. Add regression unit tests in `tests/test_xs_portfolio_alpha/test_tranche_ledger.py` covering:
   - Rebalance with empty `highs={}` and `lows={}` dicts.
   - Rebalance with `highs`/`lows` containing only a subset of symbols.
   - Rebalance with duplicate symbols in `selected_symbols`.

### 5. Verification Method
To independently verify the fixes once implemented:
```powershell
# 1. Run all unit tests
uv run pytest tests/test_xs_portfolio_alpha/test_tranche_ledger.py -v

# 2. Run full e2e acceptance suite
uv run pytest tests/test_xs_portfolio_alpha/test_e2e_acceptance.py -v

# 3. Verify edge cases via Python CLI
uv run python -c "from decimal import Decimal; from datetime import date; from quant_system.research_xs_monthly.tranche_ledger import StaggeredTrancheLedger; l = StaggeredTrancheLedger(Decimal('100000')); res = l.rebalance_tranche(0, date(2024,1,1), date(2024,1,2), ['INFY'], {'INFY': Decimal('100')}, highs={}, lows={}); assert 'INFY' in res.bought_symbols, 'Failed: empty highs/lows blocked trade'"

uv run python -c "from decimal import Decimal; from datetime import date; from quant_system.research_xs_monthly.tranche_ledger import StaggeredTrancheLedger; l = StaggeredTrancheLedger(Decimal('100000')); res = l.rebalance_tranche(0, date(2024,1,1), date(2024,1,2), ['INFY', 'INFY'], {'INFY': Decimal('100')}); assert l.mark_to_market(date(2024,1,2), {'INFY': Decimal('100')}).total_nav > Decimal('24000'), 'Failed: duplicate symbols destroyed cash'"

# 4. Run static checks
uv run ruff check src/quant_system/research_xs_monthly/tranche_ledger.py tests/test_xs_portfolio_alpha/test_tranche_ledger.py
uv run mypy src/quant_system/research_xs_monthly/tranche_ledger.py tests/test_xs_portfolio_alpha/test_tranche_ledger.py
```
**Invalidation conditions**:
- Any trade blocked when `highs={}` and `lows={}` are passed.
- Any capital loss when duplicate symbols are provided in `selected_symbols`.
- Any test failure in `pytest`.
