# NOTICE: the backtest session-peak repair is paused on a governor change

STATUS: NOTICE (additive; no other record is edited)  
FROM: `20260929-1000Z-claude-backtest-session-peak-reset.md` (Claude Code)  
TO: `20260822-claude-money-paths-remainder.md` (owner of `risk/governor.py`, IN_PROGRESS),
`20260929-0431Z-claude-backtest-engine-held-position-marks.md` (claims `backtest/engine.py`),
`20260929-1000Z-claude-daily-pipeline-governor-per-engine.md` (FYI), and
`20260824-codex-real-journey-api-wiring.md` (FYI, pinned number)  
DATE_UTC: 2026-09-29

## What was decided, and by whom

Founder decisions, given in chat on 2026-09-29 for the defect that `BacktestEngine.run()` never calls
`PreTradeRiskGovernor.reset_session_peak()` (so `max_daily_drawdown_pct` acts as a whole-run
trailing drawdown, and the first breach latches the kill switch for the rest of the run):

1. The daily peak resets at the first bar of each new date to the **session-open mark** (the book
   valued at that bar's open, after the open fills). Not to the bar's own close: measured by probe,
   that approves a 4% one-bar loss, because synthetic bars are one per calendar date and the reset
   would land on every bar.
2. A **daily-limit halt lifts at the next session's reset**. A total-drawdown halt and a manual halt
   stay latched for the rest of the run.
3. Halt timestamps and the audit trail **wait for a governor change**. The engine will not keep its
   own log in the meantime.

Decision 3 is why the engine repair is paused. Nothing in `engine.py` or `governor.py` has been
edited by this record.

## What the governor's owner is asked to consider

This record cannot edit `risk/governor.py`. These are requests, not instructions, and the owner may
decline or reshape any of them. Each lists what it could break, measured at `63941c583`.

1. **Stamp halts with the order's time.** `evaluate_order` calls `trigger_kill_switch(...)` at
   `governor.py:216` and `:240` without a `timestamp`, so `KillSwitchEvent.timestamp` is
   `datetime.now(UTC)`. In a backtest that is wall-clock time, not simulated time. Passing
   `timestamp=order.created_at` fixes it. Watch: `created_at` can be naive
   (`tests/test_risk_governor.py:105` builds `datetime(2025, 1, 1, 11, 0)`), while the default is
   timezone-aware UTC. `get_state` serialises with `isoformat()` and `restore_state` reads
   `fromisoformat()`, which round-trips either, but code that compares two event times would meet
   both.
2. **Leave a trace when the switch is reset.** `reset_kill_switch()` (`:91`) records nothing, so a
   halt that lifts is invisible afterwards. **Do not append the resume to `_kill_events`.**
   `scripts/run_paper_pilot_session.py:2445`, `:2574`, `:2660` and `:2756` read
   `governor.kill_events[-1].reason` as the halt reason, and `tests/test_risk_governor.py:128`
   asserts `len(gov.kill_events) == 1`. A resume in that list would change what `[-1]` means after a
   `PaperPilot.resume_session`. A separate list avoids that. It would need serialising in
   `get_state` and tolerating its absence in `restore_state`, because older snapshots do not have it.
3. **Optional: a typed halt category.** Decision 2 needs the engine to tell a DAILY halt from a
   TOTAL or manual one. Today the only handle is the reason string beginning
   `DAILY_DRAWDOWN_LIMIT_BREACHED`, which is exactly the kind of string coupling this repository
   has been bitten by. A typed field would remove it. If the owner declines, the engine will match
   the prefix and its regression test will pin that coupling.

## What moves when this lands

- The engine repair is then made in `backtest/engine.py`, after
  `20260929-0431Z-claude-backtest-engine-held-position-marks.md` merges or its owner agrees in
  writing. That record's own measurements say 9 of 11 order-placing caller runs latch the kill switch
  before and after its repair, so the results below are large.
- Every synthetic backtest result changes, because runs that were refused for hundreds of bars will
  trade. Numbers will be measured, per caller, before and after, and recorded.
- `20260824-codex-real-journey-api-wiring.md` pins six trades for the UI default backtest. The
  held-marks record already reports 6 -> 13 for that run. This change can move it again; a second
  notice follows with the measured figure.
- `20260929-1000Z-claude-daily-pipeline-governor-per-engine.md`: its ML run's own kill-switch trip
  is the defect above and is unchanged by giving each engine its own governor. Its post-repair ML
  figures stay artifacts of that latch until this lands.

## Contact

Reply with your own uniquely named record in `agent_context/work/active/`.
