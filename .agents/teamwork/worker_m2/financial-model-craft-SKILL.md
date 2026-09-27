# Financial Model Craft (Local Copy)
Source: D:\quant_system\.agents\skills\financial-model-craft\SKILL.md

A financial result is acceptable only when its timing, units, costs, accounting identities, and evidence make the same economic claim. A plausible number is not a reconciled model.

## Non-negotiable invariants
- Define economic timing before formulas: decision, order, fill, valuation, settlement, and realization times. Never use a price or rule unavailable at its applicable time.
- Use `Decimal`, integer paise, or validated canonical decimal strings for money, prices, rates, quantities with fractional units, and exact gate comparisons.
- Bind every changeable fee, tax, calendar, lot, tick, expiry, settlement, benchmark, and risk rule to an effective-dated authority.
- Calculate and retain each friction component separately. Apply its own legal basis, side, segment, rate, cap, minimum, and rounding order before summing the total.
- Preserve one accounting path from order/proposal through fills, component costs, cash, position, realized/unrealized P&L, equity, metrics, and export.
- Completed ledgers reconcile exactly to the paisa. A tolerance, residual plug, float comparison, or silent write-off cannot turn a mismatch into success.
- Separate gross return, modeled friction, net return, cash P&L, and percentage return.
