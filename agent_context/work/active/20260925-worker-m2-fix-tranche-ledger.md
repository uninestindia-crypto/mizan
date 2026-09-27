# Active work: worker-m2-fix tranche ledger edge-case refinements

STATUS: COMPLETED  
OWNER: worker_m2_fix  
TOOL: Antigravity  
STARTED_UTC: 2026-09-25T15:18:00Z  
COMPLETED_UTC: 2026-09-25T15:23:00Z  
STARTING_REVISION: c270017b3b6a9d8130ad57d157886985ca4f70d5  
WORKTREE_OR_BRANCH: D:\quant_system main

## Objective

Fix edge-case defects identified by reviewer_m2_2 and challenger_m2_2 in `src/quant_system/research_xs_monthly/tranche_ledger.py`:
1. Prevent false circuit lock when `sym` is omitted from `highs` and `lows` (or when `highs={}` and `lows={}` are passed), avoiding `None == None` evaluating to `True`.
2. Deduplicate `selected_symbols` at the entry of `rebalance_tranche` to prevent double-charging cash and fees while overwriting positions.
3. Guard exit pricing against non-positive prices (`p_exit <= Decimal("0.00")`), treating them as unexecutable/locked.
4. Strengthen lookahead check in `rebalance_tranche` to require `execution_date > decision_date` (`execution_date <= decision_date` raises `ValueError`).
5. Add comprehensive regression tests in `tests/test_xs_portfolio_alpha/test_tranche_ledger.py`.
6. Verify with pytest, ruff, mypy.

## Owned paths

- `src/quant_system/research_xs_monthly/tranche_ledger.py`
- `tests/test_xs_portfolio_alpha/test_tranche_ledger.py`

## Non-goals

- Refactoring other modules (`ranking.py`, `bars.py`, `diagnostics.py`).
- Changing interface signatures or contracts outside R2 scope.
- Deleting or modifying other agents' active records.

## Plan

1. Read existing implementations in `src/quant_system/research_xs_monthly/tranche_ledger.py` and `tests/test_xs_portfolio_alpha/test_tranche_ledger.py`. [COMPLETED]
2. Initialize BRIEFING.md and progress.md in `.agents/teamwork/worker_m2_fix/`. [COMPLETED]
3. Implement the fixes in `tranche_ledger.py`:
   - Circuit-lock check in exit and entry loops: require `sym in highs and sym in lows` (or `h_price is not None and l_price is not None and h_price == l_price`). [COMPLETED]
   - Deduplicate `selected_symbols`: `selected_symbols = list(dict.fromkeys(selected_symbols))`. [COMPLETED]
   - Exit pricing check: `p_exit <= Decimal("0.00")` -> skip liquidation / keep position locked. [COMPLETED]
   - Lookahead protection: `execution_date <= decision_date` -> `raise ValueError`. [COMPLETED]
4. Add unit and regression tests in `tests/test_xs_portfolio_alpha/test_tranche_ledger.py`. [COMPLETED]
5. Run tests, linter, type-checker. [COMPLETED]
6. Write handoff report and notify orchestrator. [IN_PROGRESS]

## Current step

Writing handoff report and completing task.

## Decision rationale

- Circuit locks must only fire when high and low prices are actually present in the provided dicts and are equal. If high/low are absent, missing, or empty dicts are passed, the stock is not price-locked (volume locks are separate).
- Duplicate symbols in ranking selection are deduplicated in first-seen order (`dict.fromkeys`) before calculating capital allocation per stock so cash is never deducted twice for one position allotment.
- Non-positive exit prices do not reduce cash or generate negative proceeds; such positions remain held/locked until a valid price is observed.
- Next-open execution strictly requires `execution_date > decision_date`.

## Commands and outcomes

| Command | Result | Evidence/notes |
|---|---|---|
| `uv run pytest tests/test_xs_portfolio_alpha/test_tranche_ledger.py -v` | PASS | 35 passed in 0.21s (including 5 new regression tests) |
| `uv run pytest tests/test_xs_portfolio_alpha/test_e2e_acceptance.py -v` | PASS | 105 passed in 1.92s |
| `uv run pytest tests/test_xs_portfolio_alpha/test_tranche_ledger_adversarial.py -v` | PASS | 22 passed in 0.13s |
| `uv run pytest tests/test_xs_portfolio_alpha/ -v` | PASS | 173 passed in 1.69s |
| `uv run ruff check src/quant_system/research_xs_monthly/tranche_ledger.py tests/test_xs_portfolio_alpha/test_tranche_ledger.py` | PASS | All checks passed! |
| `uv run mypy src/quant_system/research_xs_monthly/tranche_ledger.py tests/test_xs_portfolio_alpha/test_tranche_ledger.py` | PASS | Success: no issues found in 2 source files |
| `powershell scripts/audit-agent-claims.ps1` | PASS | Exit 0 |
| `powershell scripts/audit-disk-layout.ps1` | PASS | Exit 0 |

## Files changed

- `src/quant_system/research_xs_monthly/tranche_ledger.py`: Implemented circuit-lock check fix (`h_price is not None and l_price is not None and h_price == l_price`), deduplication of `selected_symbols` via `list(dict.fromkeys(selected_symbols))`, safe positive exit prices (`if p_exit <= Decimal("0.00"): continue`), and strict lookahead check (`execution_date <= decision_date`).
- `tests/test_xs_portfolio_alpha/test_tranche_ledger.py`: Added 5 regression tests covering empty highs/lows dicts, partial highs/lows dicts, duplicate symbols in `selected_symbols`, non-positive exit prices, and same-day lookahead rejection.

## Blockers and conflicts

None.

## Stop point

All fixes and regression tests implemented, statically verified, and passing 100%.

## Next safe action

Handoff to orchestrator and reviewers for Milestone 2 approval.
