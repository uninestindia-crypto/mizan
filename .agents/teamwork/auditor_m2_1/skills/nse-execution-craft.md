# NSE Execution Craft
Design, implement, test, or review Indian NSE equity, futures, and options execution simulations, paper brokers, transaction-cost models, calendars, contract metadata, or broker reconciliation.

## Key Rules
- Model the executable trade, not the chart.
- Never silently apply today's fee, tax, lot-size, or expiry rules to historical trades.
- Bar backtests must never fill at a price unavailable after the decision timestamp (e.g. next-open execution).
- Check circuit locks, zero volume, illiquid-bar cases.
- Use exact decimal/fixed-point arithmetic for cash, fees, taxes, premium, settlement.
