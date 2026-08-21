# Slice 10 Contract — Quote-Driven Paper Pilot

STATUS: FROZEN FOR IMPLEMENTATION  
DATE: 2026-08-21

## Inputs & Invariants

- **Orderbook Depth Simulation**: Consumes top-of-book and L2 market depth quotes (`bid`, `bid_size`, `ask`, `ask_size`).
- **Realistic Fill Dynamics**: Simulates queue priority delay, adverse price slippage proportional to participation rate, and partial fill allocations against available book depth.
- **Atomic Double-Entry Ledger Mutation**: Fills execute against the paper portfolio ledger with stable idempotency keys, updating positions, cash, and statutory fees in exact Decimal units.
- **Session Lifecycle & Daily Reconciliation**: Unfilled simulated limit orders cancel at session close (15:30 IST), and daily mark-to-market ledger states reconcile to the paisa.
