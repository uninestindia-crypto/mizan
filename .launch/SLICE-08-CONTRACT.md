# Slice 08 Contract — Recorded Shadow Replay

STATUS: FROZEN FOR IMPLEMENTATION  
DATE: 2026-08-22

## Purpose

Slice 8 establishes the governed, read-only shadow execution engine driven by recorded historical
quote streams (`ReplayQuoteFeed` and `ShadowReplayEngine`). It verifies that model candidates in the
`SHADOW` lifecycle state generate attributable decision proposals under realistic simulated latency
and pre-trade risk controls without capital risk or live broker write capability.

## Inputs

- Recorded quote sequence conforming to `ReplayQuote` or canonical JSON/mapping schemas with exact
  `Decimal` bid and ask prices, non-negative integer sizes, monotonic timestamps, and provenance
  metadata (`QuoteProvenance`).
- Model candidate in an approved promotion state (`target_state == "SHADOW"`). Unapproved model
  states (`RESEARCH_ONLY`, `REJECT`) are refused at preflight (AC-67).
- Immutable pre-trade risk policy (`RiskLimits`) and `PreTradeRiskGovernor`.
- Configured economic timing: `decision_latency` (default: 10ms) and `execution_latency` (default: 5ms),
  ensuring decisions and fills execute strictly post-quote.

## Non-Negotiable Invariants

1. **Zero Broker Write Capability (AC-1, AC-61)**:
   - Execution mode is strictly `SHADOW_READ_ONLY`.
   - Live broker order endpoints, credentials for order placement, and write routes are non-existent.
   - All executions are simulated internal accounting transitions against incoming quote feeds.

2. **Strict Point-in-Time Sequencing and Latency (AC-53, AC-62)**:
   - A strategy decision is computed on quote $Q_i$ at time $T_{Q_i}$ with decision timestamp
     $T_{\text{dec}} = T_{Q_i} + \text{latency}_{\text{dec}}$.
   - Order submission occurs at $T_{\text{order}} = T_{\text{dec}}$.
   - Simulated fill execution can ONLY match on a subsequent quote $Q_j$ ($j > i$) where
     $T_{Q_j} \ge T_{\text{order}} + \text{latency}_{\text{exec}}$. Same-quote fills and negative
     latency lookahead are structurally impossible.

3. **Strict Fail-Closed Stream Integrity (AC-20, AC-65, AC-68)**:
   - Out-of-order timestamps ($T_k < T_{k-1}$) fail closed with `OUT_OF_ORDER_TIMESTAMP`.
   - Duplicate ticks (identical symbol, timestamp, bid, and ask) fail closed with `DUPLICATE_TICK`.
   - Corrupted payloads (negative price, negative size, non-finite values, binary floats, schema
     omissions) fail closed with `CORRUPTED_PAYLOAD` or `SCHEMA_VIOLATION`.
   - Crossed books ($\text{ask} < \text{bid}$) and zero liquidity ($\text{bid} = 0, \text{ask} = 0$)
     fail closed with `CROSSED_BOOK` and `ZERO_LIQUIDITY`.
   - Quote gaps exceeding `max_allowed_staleness_seconds` fail closed with `STALE_QUOTE`.
   - Disconnection or interrupted stream transitions session to `OFFLINE` or `HALTED` without
     synthetic substitution (AC-68).

4. **Exact Decimal Accounting and Indian Market Costs (AC-49, AC-56)**:
   - Cash, prices, quantities, and P&L use exact `Decimal` arithmetic quantized to paise ($\text{₹}0.01$).
   - Full regulatory friction breakdown (brokerage, STT, exchange turnover, SEBI charges, stamp duty,
     GST, slippage) is computed and stored per fill using `IndianMarketCostModel`.
   - Ledgers reconcile exactly ($\text{Initial Cash} + \sum \Delta \text{Cash} = \text{Current Cash}$).

5. **Auditable Proposal Lifecycle and Matured Attribution (AC-66, AC-72)**:
   - Every proposal records unique ID, session ID, model ID, quote provenance sequence, decision time,
     order time, side, quantity, risk decision, fill details, and rejection/cancellation reasons.
   - Proposals distinguish `PENDING`, `FILLED`, `REJECTED`, `CANCELLED`, and `UNPROCESSED`.
   - Matured market outcomes (realized return and price at horizon quote $Q_{i+N}$) are attributed to
     filled proposals.
   - Sessions emit a canonical `ShadowSessionAudit` with SHA-256 digest enabling exact deterministic
     replay verification.

## Explicit Limits

- Real-time websocket live network streaming and connection management belong to Slice 9.
- Orderbook depth walking and quote-driven partial fill modeling belong to Slice 10.
- Slice 8 establishes the immutable foundation for reproducible offline quote replay.
