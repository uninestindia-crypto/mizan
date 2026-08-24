# Repair the remaining API/shadow/paper findings

TASK_ID: 20260823-claude-api-shadow-paper-remainder
AGENT: Claude Code (Opus 5)
STATUS: IN_PROGRESS
STARTED_UTC: 2026-08-23
STARTING_REVISION: bcad1dc (main, install root)
WORKTREE_OR_BRANCH: D:\quant_system on main (shared checkout)

## Objective

Founder-directed: repair what remains open in
`agent_context/work/active/20260822-redteam-api-shadow-paper.md`.

## What remains, verified individually at bcad1dc

| # | Sev | Finding | State |
|---|---|---|---|
| S8-M3 | Major | `broker_write_calls` is a plain attribute never incremented, and `ShadowSessionAudit` has no `__post_init__` guard, unlike Slice 9's report | open — 0 increments, 0 `__post_init__` |
| S8-M4 | Minor | float `bid_size` silently truncated (3.9 -> 3) while float prices are refused | open — `replay_feed.py:297` |
| S10-M2 | Major | `total_slippage_cost` structurally 0.00 in the reconciliation report | open |
| S10-M3 | Major | no 15:30 IST enforcement; a fill executes on a Sunday at 03:02 | open — zero IST/market-hours tokens in either module |
| S10-M4 | Major | AC-62 staleness guard dead by default: `eval_time = current_time or book.timestamp` makes age 0 | open — `orderbook_sim.py:225` |
| S10-M5 | Minor | 1-paisa ROUND_UP slippage floor: 5 bps configured becomes 100 bps at price 1.00 | open |
| S10-M6 | Minor | idempotency conflict check ignores `decision_at`, `strategy_name`, `model_artifact_id` | open |
| S10-M7 | Minor | crossed/wide-spread guards vanish when one side has zero displayed size | open |

Already closed and NOT re-touched: S8-B1, S8-B2, S8-B3, S8-M1, S8-M2 (antigravity round);
S9-B1, S9-B2, S9-B3, S9-M1, S9-M2, S9-M3 and S10-B1 (this session, earlier).

## Slice 6 — deliberately out of scope, with reasons

The Red Team record lists three Slice 6 items under **"UNDER INVESTIGATION (read, not yet
reproduced)"**, not as confirmed findings:

1. `/api/holdout/evaluate`, `/api/data/ingest`, `/api/training/governed-ridge`,
   `/api/shadow/status`, `/api/paper-pilot/order` return hardcoded fabricated results.
2. supervisor idempotency key not bound to endpoint or payload.
3. `testserver`/`testclient` accepted in the production Host allowlist.

Item 1 is confirmed present (`status="FILLED"` literal, `sharpe_ratio=1.84` literal), but repairing
it is not a finding fix — it is replacing the entire mocked product layer with real engine calls,
which is slice-sized work touching every Slice 11 endpoint. It needs its own contract and its own
adjudication, not a quiet inclusion in a repair batch. Items 2 and 3 are unreproduced as written.

Recorded here so the omission is deliberate and visible rather than silent.

## Owned paths

Checked against every active record. The three records claiming `src/quant_system/execution/**`
are all `STATUS: COMPLETE`, and each names specific new files — `governed_strategy.py`,
`bar_history.py`, `maturity.py`, `realtime_shadow.py`. **None of the files below is claimed.**

- `src/quant_system/execution/shadow_models.py` (S8-M3)
- `src/quant_system/execution/shadow_replay.py` (S8-M3)
- `src/quant_system/execution/replay_feed.py` (S8-M4)
- `src/quant_system/execution/paper_pilot.py` (S10-M2, M3, M4, M6)
- `src/quant_system/execution/orderbook_sim.py` (S10-M4, M5, M7)
- `tests/test_shadow_replay.py`, `tests/test_paper_pilot.py`

Not touched: `realtime_shadow.py`, `governed_strategy.py`, `bar_history.py`, `maturity.py` —
another agent's completed work, and none of these findings lives there.

## Plan

Per finding: verify it reproduces, write the failing regression, repair, re-run.
Then full suite, ruff, mypy, both audits, and a notice for the in-flight adjudication.

## Outcome — all eight repaired, each failing-first

**S8-M3** — `ShadowSessionAudit` gained a `__post_init__` refusing a non-zero `broker_write_calls`
and a non-read-only mode, matching Slice 9's `ShadowAuditReport`. The invariant now lives on the
record, so no construction path bypasses it.

**S8-M4** — new `_parse_size` rejects float sizes with `CORRUPTED_PAYLOAD`, as `_parse_decimal`
already did for prices. The same payload was strict about prices and lax about depth, and depth
drives fill simulation.

**S10-M2** — the cost model is deliberately passed `slippage_bps=0.0` because slippage is already
in `vwap_price`, so `breakdown.slippage` was structurally zero and the report summed zeros. The
engine now records `sim_result.total_slippage` per fill and sums that.

**S10-M3** — added an NSE session guard: weekends and anything outside 09:15-15:30 IST are refused
with `OUTSIDE_MARKET_SESSION`. The exchange holiday calendar is **not** modelled, which is why the
reason names the session rather than claiming the day was a trading day.

**S10-M4** — `eval_time = current_time or book.timestamp` made quote age identically zero whenever
a caller omitted the clock, silently disabling AC-62. A missing evaluation time is now a typed
refusal, not a pass.

**S10-M5** — rounding per-unit slippage UP to a whole paisa imposed a floor: 5 bps on a 1.00 ask
became 1.00%. The effective price now rounds to the nearest paisa, and `slippage_per_unit` reports
what was actually charged (`effective_price - book_price`) rather than the pre-rounding intent, so
the S10-M2 total is self-consistent with the fills.

**S10-M6** — the idempotency conflict check now also compares `decision_at`, `strategy_name` and
`model_artifact_id`. Those identify *which* decision this is; without them two different decisions
sharing a `proposal_id` replayed as one.

**S10-M7** — a book with one side missing yields `spread_pct = None`, which silently skipped the
crossed, locked and wide-spread guards. An incomplete book is now refused
(`INCOMPLETE_BOOK_SPREAD_UNDETERMINED`), checked **after** the liquidity guards so the more
specific zero-liquidity reason still wins when it is the order's own side that is empty.

### Three pre-existing expectations encoded S10-M5

`test_orderbook_simulator_adverse_slippage_and_vwap` and two assertions in
`test_paper_pilot_basic_buy_and_sell_lifecycle` pinned prices produced by the round-up-a-whole-paisa
behaviour — one comment literally read "1.501 -> rounded up 1.51". They were corrected to the
nearest-paisa values, each with the reason written into the test body. VWAP was unchanged by the
repair; only the per-level prices and the slippage total moved.

That makes five pre-existing tests found asserting a defect across this session. All are named in
the records rather than quietly amended.

## Gate

| Gate | Result |
|---|---|
| `pytest tests/ -q` | **808 passed**, 1 warning |
| `pytest` paper_pilot + shadow_replay | 54 passed |
| `ruff check .` | All checks passed! |
| `ruff format --check .` | 334 files already formatted |
| `mypy src launcher.py scripts` | Success, 128 source files |

## Not claimed

Not certified. No Red Team recheck and no clean-clone Verifier has adjudicated these. Measured in a
shared checkout with other agents committing concurrently.

The Slice 6 items remain deliberately out of scope for the reasons recorded above; the mocked
endpoint layer in particular needs its own contract, not inclusion in a repair batch.

## Next safe action

Await adjudication.
