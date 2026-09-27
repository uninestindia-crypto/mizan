# financial-model-craft methodology dump
Source: d:\quant_system\.agents\skills\financial-model-craft\SKILL.md

Key Non-negotiable Invariants:
1. Define economic timing before formulas: decision, order, fill, valuation, settlement, and realization times. Never use a price or rule unavailable at its applicable time.
2. Use Decimal, integer paise, or validated canonical decimal strings for money, prices, rates, quantities with fractional units, and exact gate comparisons. Never round-trip a binary float into exact accounting state.
3. Bind every changeable fee, tax, calendar, lot, tick, expiry, settlement, benchmark, and risk rule to an effective-dated authority.
4. Calculate and retain each friction component separately. Apply its own legal basis, side, segment, rate, cap, minimum, and rounding order before summing the total.
5. Preserve one accounting path from order/proposal through fills, component costs, cash, position, realized/unrealized P&L, equity, metrics, and export.
6. Stable idempotency key. Duplicate or replayed events cannot post twice; conflicting duplicates and out-of-order events fail closed.
7. Validate an event completely before mutation. Every rejected or failed event is an atomic no-op.
8. Completed ledgers reconcile exactly to the paisa. Reconciliation independently rebuilds cash, positions, lots, fees, P&L, and equity from authoritative events.
9. Separate gross return, modeled friction, net return, cash P&L, and percentage return.
10. Evaluate candidate and baselines under identical timing, universe, fill, cost, capital, and risk assumptions.
