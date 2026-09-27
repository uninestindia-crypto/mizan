# Dispatch: worker_m2_fix (Milestone 2 Iteration 2 Refinements)

**Agent**: worker_m2_fix
**Role**: teamwork_preview_worker
**Working Directory**: D:\quant_system\.agents\teamwork\worker_m2_fix
**Parent**: orchestrator_1 (ef790e51-c69c-48ef-8a68-d5526ac54caf)
**Timestamp**: 2026-09-25T20:47:00+05:30

## MANDATORY
Read:
1. `D:\quant_system\.agents\teamwork\ORIGINAL_REQUEST.md`
2. `D:\quant_system\.agents\teamwork\PROJECT.md`
3. `D:\quant_system\.agents\teamwork\reviewer_m2_2\handoff.md`
4. `D:\quant_system\.agents\teamwork\challenger_m2_2\handoff.md`

## MANDATORY INTEGRITY WARNING
DO NOT CHEAT. All implementations must be genuine. DO NOT hardcode test results, create dummy/facade implementations, or circumvent the intended task. A teamwork_preview_auditor will independently verify your work. Integrity violations WILL be detected and your work WILL be rejected.

## Owned Files
- `src/quant_system/research_xs_monthly/tranche_ledger.py`
- `tests/test_xs_portfolio_alpha/test_tranche_ledger.py`

## Mission & Tasks
Reviews from `reviewer_m2_2` and `challenger_m2_2` identified specific edge-case defects in `src/quant_system/research_xs_monthly/tranche_ledger.py`:
1. **Fix Circuit-Lock `None == None` Evaluation**:
   In `rebalance_tranche` (around lines 172 and 197), `highs.get(sym) == lows.get(sym)` returns `True` when `sym` is omitted from both dicts (or when `highs={}` and `lows={}`).
   Replace with:
   ```python
   if highs is not None and lows is not None:
       h = highs.get(sym)
       l = lows.get(sym)
       if h is not None and l is not None and h == l:
           is_locked = True
   ```
   and similarly for candidate buys.
2. **Deduplicate `selected_symbols`**:
   At the start of `rebalance_tranche`, deduplicate:
   ```python
   selected_symbols = list(dict.fromkeys(selected_symbols))
   ```
   This prevents duplicate entries from deducting cash multiple times and overwriting `new_positions[sym]`.
3. **Safe Positive Exit Pricing**:
   In exit liquidation loop:
   ```python
   p_exit = open_prices[sym]
   if p_exit <= Decimal("0.00"):
       continue
   ```
4. **Strict Lookahead Protection**:
   Update `if execution_date <= decision_date: raise ValueError(...)`.
5. **Add Regression Tests in `tests/test_xs_portfolio_alpha/test_tranche_ledger.py`**:
   - Test rebalance with empty `highs={}` and `lows={}` dicts (stocks must NOT be locked).
   - Test partial high/low dicts where only some stocks have quotes.
   - Test duplicate symbols in `selected_symbols` preserving cash and single allocation.
   - Test non-positive exit prices safely held as locked.
   - Test `execution_date <= decision_date` raises `ValueError`.
6. **Verify**:
   - `uv run pytest tests/test_xs_portfolio_alpha/test_tranche_ledger.py -v`
   - `uv run pytest tests/test_xs_portfolio_alpha/test_e2e_acceptance.py -v`
   - `uv run ruff check src/quant_system/research_xs_monthly/tranche_ledger.py tests/test_xs_portfolio_alpha/test_tranche_ledger.py`
   - `uv run mypy src/quant_system/research_xs_monthly/tranche_ledger.py tests/test_xs_portfolio_alpha/test_tranche_ledger.py`
7. Write 5-component handoff report to `D:\quant_system\.agents\teamwork\worker_m2_fix\handoff.md`.
8. Send completion message to orchestrator via `send_message`.
