# Financial Model Craft (Local Copy)
See original: `d:\quant_system\.agents\skills\financial-model-craft\SKILL.md`

Non-negotiable invariants:
- Decimal arithmetic for money, prices, rates, capital.
- Preserve one accounting path from order through fills, component costs, cash, position, realized/unrealized P&L.
- Validate an event completely before mutation. Rejections must be atomic no-ops.
- Completed ledgers reconcile exactly to the paisa.
- Adversarial tests: stress costs, delays, gaps, missing/stale data, zero/negative capital, non-finite values.
