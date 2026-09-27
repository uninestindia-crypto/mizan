---
name: financial-model-craft
description: Design, implement, test, or review QuantOS financial calculations and research economics where transaction costs, P&L, portfolio accounting, risk metrics, stress tests, reconciliation, or promotion evidence can change the result.
---

# Financial Model Craft Summary
- Non-negotiable invariants:
  - Exact Decimal arithmetic for money, rates, fees, capital, leverage.
  - Next-bar execution (orders at close T, fills at open T+1).
  - Explicit 0.224% round-trip statutory fee model (0.112% entry + 0.112% exit).
  - Total portfolio exposure strictly <= 1.0000 at all times.
  - Accurate P&L reconciliation and mark-to-market.
