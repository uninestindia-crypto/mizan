# Red Team adjudication — API boundary, shadow replay, realtime shadow, paper pilot

TASK_ID: 20260822-redteam-api-shadow-paper
AGENT: Claude Code (Opus 5) — INDEPENDENT Red Team adjudicator
ROLE: Adjudicator. Did not author any code under test.
STATUS: IN_PROGRESS
STARTED_UTC: 2026-08-22T00:00Z
STARTING_REVISION: 5067fa9e61d569bf31c5e37d83d4a8b318c7d808 (main)
TOOL: Claude Code

## Objective

Break, not review, the API trust boundary and the execution simulation. Adjudicate:
- Slice 6: `src/quant_system/server/**` (API, security, supervisor, schemas)
- Slice 8: `src/quant_system/execution/{shadow_replay,shadow_models,replay_feed}.py`
- Slice 9: `src/quant_system/execution/realtime_shadow.py`, `src/quant_system/data/live_feed.py`
- Slice 10: `src/quant_system/execution/{paper_pilot,orderbook_sim}.py`

Verdict PASS or BLOCKED, no middle.

## Non-goals

- Slices 4, 5, 7 (modeling, promotion, money/greeks/ledger) — concurrent Red Team agent
  `20260822-redteam-money-paths` owns those. Stay out.
- No fixes. No source modification anywhere.

## Owned paths (install root)

- `agent_context/work/active/20260822-redteam-api-shadow-paper.md` (this file)
- `.launch/reports/RED-TEAM-API-SHADOW-PAPER.md` (final report, single write at end)

Nothing else in the install root will be written.

## Workspace

WORKTREE_OR_BRANCH: clone via `scripts/new-workspace-clone.ps1 -Purpose redteam -Label apishadow`
CLONE_PATH: `D:\quant_system_workspaceserification_clones
edteam-apishadow-5067fa9-20260821-204358` (detached at 5067fa9)

## Plan

1. Create this record (DONE).
2. Read AGENTS.md, PROTOCOL.md, DISK-LAYOUT.md, LAUNCH-PROGRESS.md, .launch/STATE.md,
   .launch/SLICES.md, quarantine README, SLICE-06/08/09/10 contracts+evidence. (in progress)
3. Create clone; `$env:UV_PROJECT_ENVIRONMENT=".venv"; uv sync --frozen --extra dev --link-mode copy`.
4. Baseline: confirm gate genuinely green, record exact figures.
5. Attack families in order:
   A. Trust boundary: CORS/Host allowlist variants (evil.com, localhost.evil.com,
      127.0.0.1.evil.com, LOCALHOST case, trailing dot, [::1], missing Host, duplicate Host,
      Origin: null, punycode/unicode lookalikes). Prefix/suffix/`in` matching = Blocker.
   B. Idempotency + races: same request id concurrently from N threads; cancel-during-start,
      double cancel, cancel-after-complete, real worker process kill.
   C. Zero broker writes: module surface inspection for order-submitting methods across
      slices 8-10; attempt to reach any such path.
   D. Event integrity: stale, duplicate, out-of-order, replayed, clock-skewed events;
      typed halt reasons; duplicate-event P&L double count.
   E. Fill realism (Slice 10): zero liquidity, crossed quotes (ask<bid), wide spreads,
      partial fills, displayed-qty limits; price improvement; decision-bar fill (look-ahead).
   F. Money: any float touching money in these paths; costs reconcile to paise in Decimal.
   G. Input boundaries on all API schemas.
   H. Assumption archaeology across the four slices' diffs.
6. Write report in clone, copy to install root.

## Current step

Step 5 — attacking. Baseline gate confirmed GREEN in the clone: `483 passed, 1 warning in 57.21s` (exit 0).

## Findings so far

### CONFIRMED (reproduced with captured output)

**S8-B1 (Blocker) - every ReplayQuoteFeed integrity guard is bypassed by the sibling input type.**
`replay_feed.py:261-262` `if isinstance(raw, ReplayQuote): return raw` skips
`_validate_quote_invariants` entirely. Probe p02 output: mapping payloads halt correctly
(CROSSED_BOOK / ZERO_LIQUIDITY / CORRUPTED_PAYLOAD); the identical violations delivered as
`ReplayQuote` are ACCEPTED: ask<bid, bid=0/ask=0, bid=-5, bid_size=-7/ask_size=-9, bid=NaN/ask=NaN.
`ReplayQuote` is a documented Slice-8 input in SLICE-08-CONTRACT.md.

**S8-B2 (Blocker) - `ShadowSessionAudit.reconciled` is the literal `True` (`shadow_replay.py:381`).**
`ledger.reconcile()` is called once (`:315`) inside `_finalize_completed_session()`, result
discarded, and that method is skipped on every HALTED/OFFLINE path. Probe p04b: ledger corrupted by
+123456.78, feed halted -> `audit.reconciled=True`, `audit.final_cash=1123456.78`,
`initial+sum(deltas)=1000000.00`, unexplained 123456.78, while `ledger.reconcile()` RAISES.

**S8-B3 (Major/Blocker) - audit_hash collision.** `_build_audit` hashes 8 scalars and omits
`halt_reason`, fills, prices, fees, proposals. Probe p03b C5: CROSSED_BOOK halt and DUPLICATE_TICK
halt produce identical digest e687dc38bf709b82f2d5e538912c52395bae71ffae3539d617f3bd854564369e.

**S8-M1 (Major) - untyped exceptions escape `run()`.** `_handle_feed_error` catches only
`ReplayFeedError`. p03b C1: crossed-book ReplayQuote -> ValueError escapes run(), no audit,
engine.status left RUNNING. p02: naive-vs-aware timestamps -> TypeError; garbage ISO string ->
ValueError; non-numeric bid_size -> ValueError; each leaves feed.state=STREAMING, halt_reason=None.

**S8-M2 (Major) - staleness guard skipped across interleaved symbols.** `_check_staleness` returns
early when symbols differ. p02: INFY t0 / TCS t0 / INFY t0+2h with max_stale=60s ACCEPTED; same gap
without the interleaved TCS halts STALE_QUOTE.

**S8-M3 (Major) - `broker_write_calls` is a plain mutable attribute never incremented**
(`'broker_write_calls +=' in source == False`); `ShadowSessionAudit` has no `__post_init__` guard,
unlike Slice 9's `ShadowAuditReport`. `engine.broker_write_calls = 7` -> audit reports 7, no error.

**S8-M4 (Minor) - float `bid_size` silently truncated** (3.9 -> 3) while float prices are refused.

### CONFIRMED - Slice 9 (probes p05 / p05b)

**S9-B1 (Blocker) - decision-bar execution.** `realtime_shadow.py:369` books the hypothetical fill at
`domain_quote.ask` of the SAME quote that produced the signal. Zero latency, no next-quote
requirement. Slice 8's contract calls same-quote fills "structurally impossible"; Slice 9 does only
that. p05 E3: 3 quotes -> 3 APPROVED proposals, each filled at that quote's own ask.

**S9-B2 (Blocker) - P&L double counted; positions never close on maturity.** p05b E7:
cost 3180, open position 30 @ average_price 111.0 (true weighted 106), MTM 3315,
true unrealised 135.00, `runner.current_equity - init = 135.00`, and `matured_outcomes` net P&L
75.28 booked on top as if the trades had closed. `average_price=price` (`:426`) overwrites cost
basis instead of weighting.

**S9-B3 (Blocker) - `read_quote()` silently drops every quote but `records[0]`** (`live_feed.py:571`).
p05 E2: a 3-instrument `feeds` message parses to 3 records, `read_quote()` returns 1, B and C
vanish with no error, no counter, no log.

**S9-M1 (Major) - fabricated zero-liquidity book from an LTP-only payload.** `_parse_feed_entry`
defaults missing bid/ask to `0`. p05 E1: `{"feeds":{"NSE_EQ|X":{"ltp":1845.5,"timestamp":...}}}`
parses to a valid `LiveQuoteRecord` with bid=0 ask=0 mid=0. Runner step 3 has no zero-liquidity
check; the order is then refused as REJECTED_BY_RISK, i.e. attributed to risk rather than data
quality.

**S9-M2 (Major) - replayed/duplicate live quotes accepted, book P&L again.** p05 E4: 3 byte-identical
quotes -> 3 decisions, 30 shares, 2 matured outcomes at -12.24 each from ONE market event.

**S9-M3 (Major) - out-of-order live quotes accepted inside the freshness window.** p05b E5b:
event_at 09:15:03 -> 09:15:00 -> 09:15:04, no halt (`ShadowHaltReason` has no out-of-order code);
the stale replay tick fabricated outcomes of +3983.60 then -4017.01.

### CONFIRMED - Slice 10 (probe p06)

**S10-B1 (Blocker) - pre-trade risk governor fully bypassed.** `paper_pilot.py:374-425`: when the
symbol has no cached price and the order is MARKET, `evaluate_order` is never called and the
proposal is stamped `RISK_APPROVED`. p06 F1: 9000-share BUY on a fresh session -> approved=True
reason='RISK_APPROVED' order_value=0.00; the identical order WITH a price ->
approved=False reason='POSITION_WEIGHT_LIMIT_EXCEEDED: 90.00% > 25.00%'. It then fills 9000 @ 100.05
leaving 90.14% concentration against `max_position_weight=0.25`.

**S10-M1 (Major) - LIMIT orders fill worse than their limit.** Slippage is added after the price
gate. p06 F2: BUY LIMIT 100.00 fills @ 100.05; SELL LIMIT 100.00 fills @ 99.95.

**S10-M2 (Major) - `total_slippage_cost` in `SessionReconciliationReport` is structurally 0.00.**
p06 F4: fill 100.05 vs book 100.00 (0.05/share charged) yet report.total_slippage_cost = 0.00.

**S10-M3 (Major) - no 15:30 IST enforcement exists.** p06 F5: tokens 15:30 / IST / Asia/Kolkata /
session_end_time / market_close / tzinfo all absent from both modules; a fill executes on Sunday
2026-08-23 at 03:02.

**S10-M4 (Major) - AC-62 staleness guard is dead by default.** `validate_quote` uses
`eval_time = current_time or book.timestamp`, so age is 0 unless the caller passes current_time.
p06 F6: a 5-day-old book FILLS when current_time is omitted; REJECTED with STALE_QUOTE_AGE when
supplied.

**S10-M5 (Minor) - 1-paisa ROUND_UP slippage floor.** p06 F3: 5 bps configured -> 100 bps effective
at price 1.00, 200 bps at 0.50.

**S10-M6 (Minor) - idempotency conflict check ignores decision_at, strategy_name, model_artifact_id.**

**S10-M7 (Minor) - crossed/wide-spread guards vanish when one side has zero displayed size**
(`from_quote` drops the level, `spread_pct` becomes None, checks 5-7 skipped).

### UNDER INVESTIGATION (read, not yet reproduced)
- S6 `/api/holdout/evaluate`, `/api/data/ingest`, `/api/training/governed-ridge`,
  `/api/shadow/status`, `/api/paper-pilot/order` return hardcoded fabricated results.
- S6 supervisor idempotency key not bound to endpoint or payload.
- S6 `testserver`/`testclient` accepted in the production Host allowlist.

## Commands and outcomes

| Command | Result | Evidence/notes |
|---|---|---|
| `git rev-parse HEAD` (install root) | PASS | `5067fa9e61d569bf31c5e37d83d4a8b318c7d808` |
| `git worktree list` | PASS | only `D:/quant_system 5067fa9 [main]` |
| `new-workspace-clone.ps1 -Purpose redteam -Label apishadow` | PASS | clone at `redteam-apishadow-5067fa9-20260821-204358`, HEAD 5067fa9 |
| `uv sync --frozen --extra dev --link-mode copy` | PASS | exit 0 |
| `uv run --frozen python -m pytest -q` (clone) | PASS | **483 passed, 1 warning in 57.21s**, exit 0 — gate genuinely green before attack |

## Files changed

- `agent_context/work/active/20260822-redteam-api-shadow-paper.md`: this record.

## Blockers and conflicts

None yet.

## Stop point

Families A (trust boundary p01), B (Slice 8 p02/p03b/p04b), Slice 9 (p05/p05b) and Slice 10 (p06)
complete.
Probes live under the session scratchpad directory `.../scratchpad/probes/`.

## Next safe action

Run probe p07: Slice 6 API. (a) TestClient host/origin/CSRF matrix against the live app;
(b) hardcoded-response endpoints /api/holdout/evaluate, /api/data/ingest,
/api/training/governed-ridge, /api/shadow/status, /api/paper-pilot/order;
(c) supervisor idempotency-key hijack across endpoints; (d) concurrent same-key submits;
(e) cancel-during-completion race; (f) real worker process kill. Then write the report.
