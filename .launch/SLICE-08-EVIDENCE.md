# Slice 08 Evidence — Recorded Shadow Replay

STATUS: PASS  
DATE: 2026-08-22  

## Outcome

Slice 8 implements the recorded historical quote replay feed (`ReplayQuoteFeed`) and the shadow
decision engine (`ShadowReplayEngine` and `shadow_models.py`). The engine executes model candidates in
the `SHADOW` state against recorded quote streams with strict point-in-time sequencing, simulated
decision/execution latency, pre-trade risk evaluation, and exact Decimal double-entry accounting.

All execution is strictly read-only logging and attribution (`SHADOW_READ_ONLY`) with zero broker write
capability. Stream corruptions (out-of-order timestamps, duplicate ticks, crossed books, negative
prices/sizes, binary float payloads, and staleness) halt the session fail-closed with typed reasons.

## Contracts Proved

- **Zero Broker Write Capability (AC-1, AC-61)**: Proved `audit.mode == "SHADOW_READ_ONLY"` and
  `broker_write_calls == 0` with no broker endpoints or network write mutations.
- **Model Lifecycle State Gate (AC-67)**: Proved unapproved candidate states (`RESEARCH_ONLY`, `REJECT`)
  fail closed at session preflight with `MODEL_NOT_IN_SHADOW_STATE`.
- **Strict Point-in-Time Sequencing and Latency (AC-53, AC-62)**: Proved proposals execute strictly
  post-quote and fills match only on subsequent quotes arriving at or after
  $\text{order\_timestamp} + \text{execution\_latency}$.
- **Pre-Trade Risk Governor Enforcement (AC-55)**: Proved orders exceeding position concentration or
  cash buffers are rejected with exact risk limit reasons without modifying cash or positions.
- **Fail-Closed Stream Integrity (AC-20, AC-65, AC-68)**:
  - Out-of-order timestamps halt with `OUT_OF_ORDER_TIMESTAMP`.
  - Duplicate ticks halt with `DUPLICATE_TICK`.
  - Crossed books ($\text{ask} < \text{bid}$) halt with `CROSSED_BOOK`.
  - Zero liquidity ($\text{bid}=0, \text{ask}=0$) halts with `ZERO_LIQUIDITY`.
  - Binary float inputs for prices halt with `CORRUPTED_PAYLOAD`.
  - Excessive quote gaps halt with `STALE_QUOTE`.
  - Carrier drops transition to `OFFLINE` without synthetic substitution.
- **Exact Decimal Ledger Reconciliation (AC-49, AC-56)**: Proved initial cash plus transaction cash
  deltas equal final cash to the paisa ($\text{₹}0.01$) across equity delivery and derivative friction.
- **Attributable Matured Decisions (AC-66, AC-72)**: Proved filled proposals attribute subsequent
  market price movements at the maturity horizon and distinguish completed, rejected, pending, and
  cancelled proposal states.
- **Deterministic Replay (AC-74)**: Proved independent replay runs over the same quote feed yield
  identical proposals, fills, ledger balances, and audit hashes.

## Verification Evidence

All 25 tests in `tests/test_shadow_replay.py` pass cleanly:

```text
tests/test_shadow_replay.py::test_replay_feed_valid_stream PASSED
tests/test_shadow_replay.py::test_replay_feed_to_domain_quote PASSED
tests/test_shadow_replay.py::test_replay_feed_direct_quote_and_replayquote_inputs PASSED
tests/test_shadow_replay.py::test_replay_feed_schema_violation_missing_fields PASSED
tests/test_shadow_replay.py::test_replay_feed_schema_violation_unsupported_type PASSED
tests/test_shadow_replay.py::test_replay_feed_out_of_order_timestamp PASSED
tests/test_shadow_replay.py::test_replay_feed_duplicate_tick PASSED
tests/test_shadow_replay.py::test_replay_feed_crossed_book PASSED
tests/test_shadow_replay.py::test_replay_feed_zero_liquidity PASSED
tests/test_shadow_replay.py::test_replay_feed_corrupted_payload_float_rejected PASSED
tests/test_shadow_replay.py::test_replay_feed_corrupted_payload_negative_price PASSED
tests/test_shadow_replay.py::test_replay_feed_corrupted_payload_negative_size PASSED
tests/test_shadow_replay.py::test_replay_feed_max_spread_pct_breach PASSED
tests/test_shadow_replay.py::test_replay_feed_staleness_detection PASSED
tests/test_shadow_replay.py::test_replay_feed_manual_halt_and_reset PASSED
tests/test_shadow_replay.py::test_replay_feed_disconnect_simulation PASSED
tests/test_shadow_replay.py::test_shadow_replay_zero_broker_writes PASSED
tests/test_shadow_replay.py::test_shadow_replay_unapproved_model_state_halt PASSED
tests/test_shadow_replay.py::test_shadow_replay_point_in_time_sequencing_and_latency PASSED
tests/test_shadow_replay.py::test_shadow_replay_pretrade_risk_rejection PASSED
tests/test_shadow_replay.py::test_shadow_replay_options_friction_calculation PASSED
tests/test_shadow_replay.py::test_shadow_replay_exact_decimal_ledger_reconciliation PASSED
tests/test_shadow_replay.py::test_shadow_replay_matured_outcome_attribution PASSED
tests/test_shadow_replay.py::test_shadow_replay_fail_closed_on_corrupted_feed_mid_session PASSED
tests/test_shadow_replay.py::test_shadow_replay_deterministic_reproducibility PASSED

============================= 25 passed in 0.18s =============================
```

### Static & Craft Checks

| Gate | Result | Notes |
|---|---|---|
| Focused Replay Suite | PASS | 25 passed in 0.18s |
| Strict Mypy | PASS | 0 issues found in execution and test modules |
| Ruff Lint | PASS | 0 errors |
| Ruff Format | PASS | 0 files require formatting |
| Code Craft | PASS | 4 files clean (`check-code.mjs`) |
| Test Craft | PASS | 1 test file clean (`check-tests.mjs`) |

## Explicit Limits

- Real-time Upstox websocket subscriptions and clock drift monitoring belong to Slice 9.
- Dynamic orderbook depth walking and partial execution belong to Slice 10.
- Slice 8 establishes the immutable foundation for offline historical replay.
