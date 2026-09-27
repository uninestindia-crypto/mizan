# Financial Model Craft
Design, implement, test, or review QuantOS financial calculations and research economics where transaction costs, P&L, portfolio accounting, risk metrics, stress tests, reconciliation, or promotion evidence can change the result.

## Non-negotiable invariants
- Define economic timing before formulas: decision, order, fill, valuation, settlement, and realization times.
- Use Decimal, integer paise, or validated canonical decimal strings for money, prices, rates, quantities.
- Bind every changeable fee, tax, calendar, lot, tick, expiry to an effective-dated authority.
- Calculate and retain each friction component separately.
- Preserve one accounting path from order through fills, component costs, cash, position, realized/unrealized P&L, equity, metrics.
- Every accepted economic event has a stable idempotency key. Duplicate/replayed events cannot post twice.
- Completed ledgers reconcile exactly to the paisa.
- Separate gross return, modeled friction, net return, cash P&L.
- Evaluate candidate and baselines under identical timing, universe, fill, cost, capital, and risk assumptions.
