# Slice 09 Evidence — Read-Only Real-Time Shadow

STATUS: PASS  
DATE: 2026-08-22  
PRIMARY ACS: AC-20, AC-50, AC-61, AC-66, AC-67, AC-68, AC-69, AC-70

## Outcome

Slice 9 implements the complete read-only real-time market data quote intake with Upstox V3 streaming integration and shadow execution engine (`UpstoxLiveFeed` and `RealtimeShadowRunner`). Incoming quotes are strictly evaluated against the point-in-time freshness budget and clock drift thresholds. Any latency breach, network disconnect, auth expiry, timeout, or quote quality defect halts immediately with explicit typed codes. Zero broker write endpoints are exposed, and `broker_orders_submitted == 0` is strictly enforced.

## Contracts Proved

- **Zero Order Endpoint Exposure (AC-61)**:
  - Both `UpstoxLiveFeed` and `RealtimeShadowRunner` have zero broker order methods (`place_order`, `submit_order`, `submit_broker_order` do not exist).
  - `ShadowAuditReport` asserts `broker_orders_submitted == 0` and raises `ValueError` if tampered.
- **Freshness Budget Enforcement (AC-20, AC-62)**:
  - Quote latency exceeding `freshness_budget_seconds` (5.0s) immediately triggers `SHADOW_HALTED` with `STALE_QUOTE`.
- **Clock Drift Budget Enforcement**:
  - Quote timestamp in the future exceeding `max_clock_drift_seconds` (1.0s) immediately triggers `SHADOW_HALTED` with `CLOCK_DRIFT`.
- **Network & Disconnect Handling (AC-68)**:
  - Transport disconnect transitions session to `OFFLINE` with `DISCONNECTED`.
  - Feed message timeout transitions session to `SHADOW_HALTED` with `FEED_TIMEOUT`.
- **Authentication Lifecycle (AC-22, AC-68)**:
  - Missing or expired access token transitions session to `UNAUTHORIZED` with `AUTH_EXPIRED`.
- **Payload Quality & Schema Drift**:
  - HTML error pages and malformed JSON payloads raise `LiveFeedMalformedError`.
  - Crossed quotes (`ask < bid`) and negative prices raise `LiveFeedQualityError` (`CROSSED_QUOTE`).
- **Pre-Trade Risk Gating (AC-55, AC-66)**:
  - Decisions are evaluated with `PreTradeRiskGovernor`. Breached limits produce `REJECTED_BY_RISK` shadow proposals without interrupting valid session flow.
- **Matured Outcome Attribution (AC-61, AC-66)**:
  - Open shadow entries mature against subsequent market quotes, calculating gross P&L, regulatory fees via `IndianMarketCostModel`, and net P&L.
- **Deterministic Cryptographic Audit Replay (AC-73, AC-74)**:
  - Identical live quote sequences produce byte-identical canonical `audit_hash` values across separate runs.

## Test Execution Evidence

Focused Slice 9 test suite (`tests/test_realtime_shadow.py`):

```text
============================= test session starts =============================
platform win32 -- Python 3.13.15, pytest-9.1.1, pluggy-1.6.0
rootdir: D:\quant_system
configfile: pyproject.toml
plugins: anyio-4.14.2, cov-7.1.0
collected 12 items

tests/test_realtime_shadow.py::test_zero_broker_order_endpoint_exposure PASSED [  8%]
tests/test_realtime_shadow.py::test_quote_parsing_valid_upstox_payload PASSED [ 16%]
tests/test_realtime_shadow.py::test_quote_parsing_rejects_html_and_malformed PASSED [ 25%]
tests/test_realtime_shadow.py::test_quote_parsing_rejects_crossed_quotes PASSED [ 33%]
tests/test_realtime_shadow.py::test_freshness_budget_enforcement_halts_on_stale_quote PASSED [ 41%]
tests/test_realtime_shadow.py::test_clock_drift_enforcement_halts_on_future_timestamp PASSED [ 50%]
tests/test_realtime_shadow.py::test_unauthorized_token_expiry_halts_immediately PASSED [ 58%]
tests/test_realtime_shadow.py::test_streaming_disconnect_transitions_to_offline PASSED [ 66%]
tests/test_realtime_shadow.py::test_streaming_timeout_halts_session PASSED [ 75%]
tests/test_realtime_shadow.py::test_realtime_shadow_session_successful_flow PASSED [ 83%]
tests/test_realtime_shadow.py::test_risk_rejection_in_shadow_mode PASSED [ 91%]
tests/test_realtime_shadow.py::test_deterministic_audit_replay_hash PASSED [100%]

============================= 12 passed in 0.19s ==============================
```

## Failure Injection Matrix

| Test Case | Injected Fault | Expected State | Expected Halt Reason | Result |
|---|---|---|---|---|
| `test_freshness_budget_enforcement_halts_on_stale_quote` | Quote latency = 6.0s (> 5.0s budget) | `SHADOW_HALTED` | `STALE_QUOTE` | PASS |
| `test_clock_drift_enforcement_halts_on_future_timestamp` | Quote timestamp +2.5s in future (> 1.0s max drift) | `SHADOW_HALTED` | `CLOCK_DRIFT` | PASS |
| `test_unauthorized_token_expiry_halts_immediately` | Empty / expired access token | `UNAUTHORIZED` | `AUTH_EXPIRED` | PASS |
| `test_streaming_disconnect_transitions_to_offline` | Network transport socket disconnect | `OFFLINE` | `DISCONNECTED` | PASS |
| `test_streaming_timeout_halts_session` | Heartbeat / quote stream timeout | `SHADOW_HALTED` | `FEED_TIMEOUT` | PASS |
| `test_quote_parsing_rejects_html_and_malformed` | HTML 502 gateway / corrupted JSON | N/A (raises exception) | `LiveFeedMalformedError` | PASS |
| `test_quote_parsing_rejects_crossed_quotes` | Crossed quote (`ask < bid`) | N/A (raises exception) | `CROSSED_QUOTE` | PASS |
| `test_zero_broker_order_endpoint_exposure` | Method scan & non-zero order count tamper | N/A (raises ValueError) | `broker_orders_submitted == 0` | PASS |

## Explicit Limits

- Broker order endpoints are not callable or accessible; live order execution is rejected.
- Paper trading pilot execution simulation is reserved for Slice 10.
- All real-time shadow operations execute in `SHADOW_READ_ONLY` mode.
