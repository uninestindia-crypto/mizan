# NSE Execution Craft (Local Copy)
See original: `d:\quant_system\.agents\skills\nse-execution-craft\SKILL.md`

Model the executable trade, not the chart. Exchange rules, taxes, contract metadata, and broker behavior are effective-dated inputs rather than timeless constants.

Key rules:
- Circuit locks: check volume > 0, high != low, no fills during locks.
- Decimal arithmetic for cash, fees, taxes, positions, P&L.
- Reject invalid inputs: zero/negative quantities, missing prices.
- Adversarial tests: market gaps, locked quotes, zero liquidity, corporate actions.
