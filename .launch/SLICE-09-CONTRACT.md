# Slice 9 Contract — Read-Only Real-Time Shadow

STATUS: FROZEN FOR IMPLEMENTATION  
DATE: 2026-08-22  
PRIMARY ACS: AC-20, AC-50, AC-61, AC-66, AC-67, AC-68, AC-69, AC-70

## Inputs and Integration Boundary

- A valid candidate model/strategy evaluated in `SHADOW_READ_ONLY` mode.
- Upstox V3 streaming market-data feed intake (`UpstoxLiveFeed`) providing point-in-time `LiveQuoteRecord` instances.
- Point-in-time timestamp triple on every quote: `event_at` (exchange/feed event time, UTC-aware), `provider_at` (provider timestamp, UTC-aware), and `received_at` (local ingestion time, UTC-aware).
- Injected transport dependencies (`LiveFeedDependencies`) enabling deterministic testing and network simulation.

## Invariants and Behavioral Rules

1. **Zero Order Endpoint Exposure (AC-61)**:
   - Neither `UpstoxLiveFeed` nor `RealtimeShadowRunner` exposes any order placement, modification, cancellation, or broker write endpoints.
   - Broker order traffic is strictly zero (`broker_orders_submitted == 0`). Any non-zero order count violates the invariant and fails closed.

2. **Freshness Budget Enforcement (AC-20, AC-62)**:
   - Every incoming quote latency is evaluated: `latency = (received_at - event_at).total_seconds()`.
   - If `latency > freshness_budget_seconds` (default 5.0s), the quote is classified as `STALE`. The session halts immediately, transitioning to `SHADOW_HALTED` with typed reason `STALE_QUOTE`.
   - Stale data is never permitted to generate a shadow decision or proposal.

3. **Clock Drift Enforcement**:
   - If quote timestamp is in the future relative to local clock by more than `max_clock_drift_seconds` (default 1.0s), the session halts immediately, transitioning to `SHADOW_HALTED` with typed reason `CLOCK_DRIFT`.

4. **Network & Disconnect Handling (AC-68)**:
   - If streaming transport disconnect occurs, state transitions to `OFFLINE` with halt reason `DISCONNECTED`.
   - If feed heartbeat/stream times out, state transitions to `SHADOW_HALTED` with halt reason `FEED_TIMEOUT`.
   - No automatic synthetic data or unverified cache substitution is allowed upon disconnect.

5. **Authentication Expiry (AC-22, AC-68)**:
   - If access token is absent, invalid, or expired, state transitions immediately to `UNAUTHORIZED` with halt reason `AUTH_EXPIRED`.

6. **Pre-Trade Risk Gating (AC-55, AC-66)**:
   - Every hypothetical trading decision is evaluated against `PreTradeRiskGovernor` (position weight limits, daily drawdown, leverage, maximum spread).
   - If approved: `ShadowProposal` is marked `APPROVED` with `risk_approved = True`.
   - If rejected: `ShadowProposal` is marked `REJECTED_BY_RISK` with `risk_approved = False` and typed rejection reason.
   - If kill switch is active: session halts immediately with `RISK_KILL_SWITCH`.

7. **Matured Outcome Attribution (AC-61, AC-66)**:
   - Approved shadow entries track theoretical execution and mark-to-market.
   - When subsequent fresh quotes arrive, open positions mature, recording exact gross P&L, regulatory friction (STT, exchange turnover, SEBI, GST, stamp duty via `IndianMarketCostModel`), and net P&L.

8. **Cryptographic Audit Hashing (AC-73, AC-74)**:
   - Session completion or halt produces an immutable `ShadowAuditReport` with canonical SHA-256 digest (`audit_hash`) over all decisions, matured outcomes, latencies, and zero-order invariant evidence.
   - Replaying identical quote sequences produces byte-identical audit hashes.

## Explicit Limits

- Live broker write routing is forbidden.
- Paper trading order matching / partial fills / execution queue belongs to Slice 10.
- `SHADOW_READ_ONLY` is the sole permitted execution mode for this slice.
