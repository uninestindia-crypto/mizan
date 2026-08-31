# Active work: survive a network blip, tell the truth when you do not, and actually refresh

STATUS: COMPLETED
OWNER: Claude Code
TOOL: Claude Code
STARTED_UTC: 2026-08-31T15:05:00Z
STARTING_REVISION: e853376a
WORKTREE_OR_BRANCH: D:\quant_system on main

## Objective

Three defects, two of which I introduced today, found by running the pilot live:

1. **A single mid-session quote timeout ends the trading day.** At 14:21:11 one SSL handshake
   timed out, every batch in that poll failed, and the `QuoteFeedError` I added for *startup*
   refusal killed a session that had been running since 12:17. The 3-second request timeout makes
   occasional failures expected rather than exceptional.
2. **The crash reported success.** The unhandled `QuoteFeedError` still produced
   `Session Concluded & Reconciled: SUCCESS` and exit 0. Third occurrence of this class today.
3. **The bar refresh is a permanent no-op.** `process_target` returns the cached result when the
   symbol is in the catalog, never checking whether its dates reach `to_date`, so features are
   permanently one session stale. The staleness guard counts calendar days and passed on its exact
   boundary.

## Non-goals

- The four round-four items. Next.
- Re-running today's session. It ended at 14:21 with 97 real Upstox-priced holdings and its record
  stands as a truncated session, which is what it was.

## Owned paths

- scripts/run_paper_pilot_session.py
- scripts/run_scheduled_paper_session.py
- scripts/ingest_all_market_data.py
- tests/test_paper_pilot_carried_session.py
- tests/test_scheduled_paper_session.py
- agent_context/work/active/20260831-claude-quote-resilience-and-refresh.md

## Blockers and conflicts

A peer session is committing to `run_paper_pilot_session.py` concurrently (`88b78b9d`,
`416f560c`). Re-read the file immediately before editing and after; do not assume the tree is as
last seen.

## Current step

Implementing.

## Commands and outcomes

```
ruff check . / ruff format .  -> clean, 526 files
mypy src                      -> Success, 141 source files
pytest -q                     -> 1181 passed (was 1179)
all three entry points        -> import clean
```

Trading-session staleness, exercised against the real holiday authority:

```
Fri bar, Mon run  (nothing missed): missed=0 -> PASS
Thu bar, Mon run  (Friday missing): missed=1 -> REFUSE
Wed bar, Mon run  (Thu+Fri missing): missed=2 -> REFUSE
```

The middle row is the exact case that passed on 2026-08-31.

## Repaired

| # | Repair |
|---|---|
| 1 | A failed poll skips the interval and retries. `MAX_CONSECUTIVE_QUOTE_FAILURES = 5` (~2.5 min at a 30s interval) before the session gives up, so a dead feed is still fatal but a handshake timeout is not. Per-batch timeout 3s -> 15s |
| 2 | The loop's exception handler records `session_abort_reason` instead of falling through silently. The payload carries `aborted` / `abort_reason`, the banner reads `[PAPER PILOT ABORTED]`, and the exit code is 10. The session still closes and reconciles -- an abrupt exit would leave the book unpersisted |
| 3 | `IngestionSupervisor._is_current` compares the catalogued `received_end` against `to_date`, so a symbol whose bars stop short is re-fetched. The staleness guard counts **trading sessions** via the holiday authority, `MAX_MISSED_SESSIONS = 0` |

## Note on 1 and 2

Both were mine, introduced earlier today. The refusal in 1 was correct at startup and wrong applied
per-poll; 2 is the third instance of "a failure path reports success" found in a single day, which
is the pattern rather than three accidents.

## Still open

The four round-four items, round four's own P2s, and the `QuotaOS-DailyAutoSync` behaviour of
committing whatever is in the tree -- it swept a half-written adjudication and a mid-edit working
tree today.

## Next safe action

The four round-four items, then round five against everything since `46c7bb67`.
