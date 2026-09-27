# Milestone 2 (R2) Handoff Report: Staggered Tranche Portfolio Ledger

## 1. Observation
- Target requirements: Deliver R2 Staggered Tranche Portfolio Ledger maintaining 4 autonomous weekly tranches, 25% max capital per tranche, 21-session holding period, 5-session weekly stagger, top quintile selection, next-open (T+1) execution pricing, circuit-lock protection (volume == 0 or high == low), exact 0.224% round-trip statutory fee model (11.2 bps entry + 11.2 bps exit), and total portfolio leverage strictly <= 1.0000 at all times.
- Created `src/quant_system/research_xs_monthly/tranche_ledger.py` containing:
  * Typed dataclasses: `TranchePosition`, `Tranche`, `TrancheRebalanceResult`, `LedgerNAV`.
  * Core ledger class `StaggeredTrancheLedger(initial_capital: Decimal, num_tranches: int = 4)` with methods:
    - `rebalance_tranche(...) -> TrancheRebalanceResult`
    - `mark_to_market(as_of_date: date, current_prices: dict[str, Decimal]) -> LedgerNAV`
    - `total_exposure() -> Decimal`
    - `total_statutory_fees() -> Decimal`
  * Helper function `select_top_quintile(ranked_symbols: Sequence[Any], top_fraction: float = 0.20) -> list[str]`.
- Created comprehensive test suite `tests/test_xs_portfolio_alpha/test_tranche_ledger.py` containing 30 unit tests covering:
  * 4-tranche autonomous weekly capital allocation (25% each) and cash isolation across subledgers.
  * Next-open (T+1) execution fill pricing and fail-closed lookahead prevention (`execution_date < decision_date` rejected).
  * Exact 0.224% round-trip statutory fee deductions on entry and exit (`FEE_ONE_WAY = Decimal("0.00112")`, `FEE_ROUND_TRIP = Decimal("0.00224")`).
  * Circuit-lock protections on buys (skipped from entry when volume == 0 or high == low) and sells (carried over when locked).
  * Capital preservation invariant proof: total exposure strictly <= 1.0000 under nominal, surge (+300%), and crash (-90%) conditions.
  * Mark-to-market NAV calculation with mixed open/close prices, missing price fallbacks, and exact paisa cash reconciliation.
  * Top quintile selection scaling: 20% on 423 names yields 84 names, supporting both strings and `RankedSymbol` objects.
  * Integer share rounding (`//`) guaranteeing no fractional shares are ever created.
- Verification test executions:
  * `uv run pytest tests/test_xs_portfolio_alpha/test_tranche_ledger.py -v`: 30 passed in 0.30s.
  * `uv run pytest tests/test_xs_portfolio_alpha/test_e2e_acceptance.py -v`: 105 passed in 1.69s.
  * Total combined tests: 135 passed in 1.69s.
  * `uv run ruff check src/quant_system/research_xs_monthly/tranche_ledger.py tests/test_xs_portfolio_alpha/test_tranche_ledger.py`: "All checks passed!".
  * `uv run mypy src/quant_system/research_xs_monthly/tranche_ledger.py tests/test_xs_portfolio_alpha/test_tranche_ledger.py`: "Success: no issues found in 2 source files".
  * `scripts/audit-agent-claims.ps1`: "RESULT: PASS - every workspace has a visible claim and every claim resolves."

## 2. Logic Chain
1. The project requirement (ORIGINAL_REQUEST R2 & PROJECT.md §3) specifies a staggered tranche portfolio ledger dividing capital into autonomous weekly subledgers.
2. In `StaggeredTrancheLedger.__init__`, capital is divided into `num_tranches` (default 4) equal partitions `tranche_capital = (initial_capital / Decimal(num_tranches)).quantize(Decimal("0.01"))`. Each tranche has its own isolated cash balance and position book.
3. In `rebalance_tranche`, trades execute strictly on `execution_date` using `open_prices` (T+1 open), preventing look-ahead leakage. Any attempt where `execution_date < decision_date` raises a `ValueError`.
4. Positions are protected against circuit-locked illiquidity: on entry, symbols with `volume == 0` or `high == low` are filtered out; on exit, locked positions are carried over into `new_positions` rather than forcibly liquidated at artificial prices.
5. Exact Decimal fee accounting calculates `fee = (proceeds * FEE_ONE_WAY).quantize(Decimal("0.01"))` on exit and `fee = (cost * FEE_ONE_WAY).quantize(Decimal("0.01"))` on entry, deducting fees atomically from cash and tracking `_total_statutory_fees`.
6. Cash availability bounds stock purchases: `qty = int(capital_per_stock // effective_price)`, ensuring cash balance is always non-negative.
7. Since cash >= 0 and position quantities >= 0, `total_exposure = positions_value / (cash + positions_value) <= 1.0000` is mathematically guaranteed across all market movements.
8. The opaque-box E2E acceptance tests (`tests/test_xs_portfolio_alpha/test_e2e_acceptance.py`) seamlessly import `src.quant_system.research_xs_monthly.tranche_ledger` and 105/105 tests pass.

## 3. Caveats
- Historical corporate actions (splits, rights, demergers) between decision and execution dates must be applied upstream in market bar ingestion or price dict inputs before passing to `rebalance_tranche`.
- Execution fill prices assume fills occur at the session open price; market impact and slippage beyond the 0.224% statutory fee model are not modeled in this module.

## 4. Conclusion
Milestone 2 (R2: Staggered Tranche Portfolio Ledger) is fully implemented, verified, and ready for integration. All interface contracts, financial invariants, fee models, circuit lock safeguards, and capital preservation constraints are satisfied with zero regressions and clean static analysis.

## 5. Verification Method
To independently verify this implementation:
```powershell
# 1. Run unit tests for tranche ledger
uv run pytest tests/test_xs_portfolio_alpha/test_tranche_ledger.py -v

# 2. Run e2e acceptance suite
uv run pytest tests/test_xs_portfolio_alpha/test_e2e_acceptance.py -v

# 3. Run linting
uv run ruff check src/quant_system/research_xs_monthly/tranche_ledger.py tests/test_xs_portfolio_alpha/test_tranche_ledger.py

# 4. Run type checker
uv run mypy src/quant_system/research_xs_monthly/tranche_ledger.py tests/test_xs_portfolio_alpha/test_tranche_ledger.py

# 5. Run agent claims audit
powershell -ExecutionPolicy Bypass -File scripts/audit-agent-claims.ps1
```
Invalidation conditions:
- Any test failure in `test_tranche_ledger.py` or `test_e2e_acceptance.py`.
- Any static type error or lint error.
- Any violation where total exposure > 1.0000.
