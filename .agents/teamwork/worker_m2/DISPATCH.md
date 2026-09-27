# Dispatch: worker_m2 (Milestone 2 - R2 Staggered Tranche Portfolio Ledger)

**Agent**: worker_m2
**Role**: teamwork_preview_worker
**Working Directory**: D:\quant_system\.agents\teamwork\worker_m2
**Parent**: orchestrator_1 (ef790e51-c69c-48ef-8a68-d5526ac54caf)
**Timestamp**: 2026-09-25T16:06:00+05:30

## MANDATORY
You MUST read:
1. `D:\quant_system\.agents\teamwork\ORIGINAL_REQUEST.md`
2. `D:\quant_system\.agents\teamwork\PROJECT.md`
3. `D:\quant_system\.agents\skills\nse-execution-craft\SKILL.md`
4. `D:\quant_system\.agents\skills\financial-model-craft\SKILL.md`

## MANDATORY INTEGRITY WARNING
DO NOT CHEAT. All implementations must be genuine. DO NOT hardcode test results, create dummy/facade implementations, or circumvent the intended task. A teamwork_preview_auditor will independently verify your work. Integrity violations WILL be detected and your work WILL be rejected.

## Owned Files
- `src/quant_system/research_xs_monthly/tranche_ledger.py`
- `tests/test_xs_portfolio_alpha/test_tranche_ledger.py`

## Mission & Tasks
1. Implement `src/quant_system/research_xs_monthly/tranche_ledger.py`:
   - 4 autonomous weekly tranches (staggered weekly, rebalanced every 5 sessions, held for 21 sessions).
   - Capital allocation: 25% max capital per tranche. Total portfolio leverage strictly <= 100% (<= 1.0000) at all times across all 4 tranches.
   - Top quintile selection (15-20% of universe, ~84 names) ranked by `MultiFactorRankingEngine.rank_universe`.
   - Next-open (T+1) execution fill pricing with circuit-lock checks (volume == 0 or high == low).
   - Full 0.224% round-trip statutory fee model (11.2 bps entry + 11.2 bps exit) in exact Decimal math.
   - Clean typed dataclasses: `TranchePosition`, `Tranche`, `TrancheRebalanceResult`, `LedgerNAV`.
   - Class `StaggeredTrancheLedger(initial_capital: Decimal, num_tranches: int = 4)` with methods:
     * `rebalance_tranche(...) -> TrancheRebalanceResult`
     * `mark_to_market(as_of_date: date, current_prices: dict[str, Decimal]) -> LedgerNAV`
     * `total_exposure() -> Decimal`
     * `total_statutory_fees() -> Decimal`
2. Implement unit tests in `tests/test_xs_portfolio_alpha/test_tranche_ledger.py`:
   - Test 4-tranche autonomous capital allocation (25% each).
   - Test next-open (T+1) execution pricing and cash accounting.
   - Test 0.224% round-trip fee deductions on entry and exit.
   - Test circuit-lock protections on buys and sells.
   - Test leverage invariant proof: exposure strictly <= 1.0000 under all price movements and rebalances.
   - Test mark-to-market NAV calculation with mixed open/close prices and cash balance.
3. Verification:
   - `uv run pytest tests/test_xs_portfolio_alpha/test_tranche_ledger.py -v`
   - `uv run pytest tests/test_xs_portfolio_alpha/test_e2e_acceptance.py -v`
   - `uv run ruff check src/quant_system/research_xs_monthly/tranche_ledger.py tests/test_xs_portfolio_alpha/test_tranche_ledger.py`
   - `uv run mypy src/quant_system/research_xs_monthly/tranche_ledger.py tests/test_xs_portfolio_alpha/test_tranche_ledger.py`
4. Write 5-component handoff report to `D:\quant_system\.agents\teamwork\worker_m2\handoff.md`.
5. Report completion to orchestrator via `send_message`.
