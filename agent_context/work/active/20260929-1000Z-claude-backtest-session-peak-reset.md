# Active work: BacktestEngine never resets the risk governor's daily peak

STATUS: BLOCKED (founder decided the semantics; implementation waits on a governor change; no source edited)  
OWNER: Claude Code session (founder brief 2026-09-29)  
TOOL: Claude Code  
STARTED_UTC: 2026-09-29T10:00:00Z  
STARTING_REVISION: `63941c583cb40c4c1fbda3af8bca15d4df1a0ac6` (main; defect first measured at `e787ac462`)  
WORKTREE_OR_BRANCH: `D:\quant_system` on `main` for reading and this record only. No workspace exists
yet. If implementation is approved, it is made with `scripts/new-workspace-clone.ps1` (or on the
`claude/magical-taussig-9dceb1` branch after coordination, see Blockers), and this record is updated
with the path and branch **before** the workspace is created.

## Objective

`BacktestEngine.run()` (`src/quant_system/backtest/engine.py`) never calls
`PreTradeRiskGovernor.reset_session_peak()` (`src/quant_system/risk/governor.py:95`). The daily peak
only ratchets upward for the whole run, so `RiskLimits.max_daily_drawdown_pct` (0.03 default) acts as
a whole-run trailing drawdown. The first breach calls `trigger_kill_switch`, nothing ever calls
`reset_kill_switch`, and every later BUY is refused `KILL_SWITCH_ACTIVE`. SELLs still go through
because the engine never risk-checks exits. Brief measured 9 of 11 order-placing caller runs tripping
this once and logging 51-356 refusals. The paper pilot got its caller in the round-5 F20 repair
(`scripts/run_paper_pilot_session.py:1793`, `:1877`); the backtest engine never did.

Deliverable, once the founder has decided the semantics: a repair in the engine, failing-first
regression tests in a new test file, every caller re-measured before and after, notices where a
pinned number moves.

## Owned paths

Claimed now (record only):

- `agent_context/work/active/20260929-1000Z-claude-backtest-session-peak-reset.md` (this)

Claimed only after founder approval and after the engine claim below is resolved:

- `tests/test_backtest_engine_session_peak.py` (new; name not yet taken, checked 2026-09-29)
- `src/quant_system/backtest/engine.py` **only** through coordination with
  `20260929-0431Z-claude-backtest-engine-held-position-marks.md`, which claims it (see Blockers)

## Non-goals

- No edit to `src/quant_system/risk/governor.py` (owned by `20260822-claude-money-paths-remainder.md`;
  `20260903-hermes-xs-monthly-screen-new.md` and `20260925-1510Z-orchestrator-xs-portfolio-alpha.md`
  list it do-not-touch). `reset_session_peak`, `reset_kill_switch` and `kill_events` are used as they
  are.
- No edit to `tests/test_backtest_engine.py` (owned by `20260821-claude-loop-in-test-legacy.md`).
- No edit to callers: `server/app.py`, `server/supervisor.py`, `scripts/daily_pipeline.py`,
  `examples/*.py`, `analytics/optimizer.py`. They are measured, not changed.
- No edit to the held-marks branch's files, to `claude/retail-redesign`, or to any other agent's
  worktree.
- No commit, merge or push without founder approval.
- Not the held-position marks defect (`PORTFOLIO_VALUATION_UNAVAILABLE`); that is the other record's.

## Founder decisions (chat, 2026-09-29)

| # | Question | Decision |
|---|---|---|
| 1 | What the daily peak resets to at the first bar of each new date | **Session-open mark**: value the book at that bar's open, after the open fills, and reset the peak to it. Mirrors the paper pilot's F20 rule. Rejected: previous close (counts overnight gaps), no reset (fixes nothing) |
| 2 | Does a daily-limit halt end at the next session | **Yes.** A daily halt lifts at the next date's reset. A total-drawdown halt and a manual halt latch for the run. The engine tells them apart by reason prefix `DAILY_DRAWDOWN_LIMIT_BREACHED` unless the governor gains a typed category |
| 3 | `KillSwitchEvent` timestamps and the resume audit trail | **Wait for a governor change.** Rejected: an engine-side simulated-time log, and leaving wall-clock stamps. This pauses the repair |

## Plan

1. Startup sequence, claim check, this record. DONE.
2. Read the governor, engine, callers and the paper pilot's precedent. DONE.
3. Ask the founder the three semantics questions. DONE (table above).
4. File a notice to the governor's owner asking for the change decision 3 waits on. DONE
   (`20260929-NOTICE-backtest-session-peak-reset-needs-governor-halt-timestamps.md`).
5. **PAUSED until the governor stamps halts with simulated time and records resets, and until the
   held-marks branch merges or its owner agrees in writing.** Then, in a workspace made with
   `scripts/new-workspace-clone.ps1`, named in this record first:
   1. Baseline-measure every caller on the base the repair lands on. The held-marks repair moves
      every caller, so a baseline taken now would not be the right "before".
   2. Write failing-first tests in `tests/test_backtest_engine_session_peak.py`; prove each binds with
      a mutant: open-mark reset; a 4% intraday loss still trips; a daily halt lifts next session; a
      total halt stays latched; the reset does not lower `all_time_peak_equity`.
   3. Implement in `backtest/engine.py`; re-measure; record every result that changes.
   4. Gates: ruff, ruff format --check, mypy, pytest forward and reverse, both audits.
   5. Notice to `20260824-codex-real-journey-api-wiring.md` if the UI default trade count moves.

## Current step

Paused at step 5. Waiting on the governor's owner and on the held-marks merge. Nothing to do here
until one of those changes.

## Decision rationale

Findings so far, from code read at `63941c583`:

- **Every synthetic bar is its own calendar date.** `SyntheticDataGenerator.generate_equity_bars`
  (`data/loader.py:36-72`) emits one bar per `timedelta(days=1)` from 09:15, weekends included.
  `BacktestEngine.run` judges orders at that bar's close against `snapshot.total_equity`, and
  `evaluate_order` calls `update_peaks(current_equity)` first. If the peak were reset to
  `snapshot.total_equity` at the first bar of each new date, then on daily bars the reset happens on
  every bar, the peak equals the equity being judged, and `daily_dd` is 0.0 on every order. The
  daily limit would become unreachable in every synthetic backtest. "Reset at the first bar of each
  new date" is only meaningful if the baseline is something other than that bar's own close: the
  previous session's close, or the session's open mark. That is the real content of question 1.
- The total-drawdown limit (`max_total_drawdown_pct`, 0.10) is a separate trailing check on
  `_all_time_peak_equity`, which `reset_session_peak` only ever raises. Resetting the daily peak
  leaves the total check intact, so a run that bleeds slowly still latches on TOTAL.
- `trigger_kill_switch` stamps `KillSwitchEvent.timestamp` with `datetime.now(UTC)` unless a
  timestamp is passed, and `evaluate_order` does not pass one. `_kill_events` is therefore wall-clock
  time in a backtest, not simulated time. `reset_kill_switch` records no event at all. An
  unlatch-at-next-session design has no audit trail of the unlatch unless the engine records one, and
  correcting the halt timestamps needs a governor change I am not allowed to make (question 3).
- The paper pilot precedent (`run_paper_pilot_session.py:1861-1884`) anchors the daily peak to the
  **first live mark of the session**, deliberately not to the previous close, because an overnight
  gap is not an intraday drawdown. It also refuses to unlatch: a tripped switch persists until a
  human runs `scripts/clear_paper_halt.py`, with the stated reasoning that auto-resetting "would make
  the switch decorative". A backtest that unlatches on the next date departs from that on purpose,
  which is why it is a founder decision and not mine.

Rejected for now: any implementation before the founder answers, since it changes every synthetic
backtest result and a wrong guess would be repaired twice.

## Commands and outcomes

| Command | Result | Evidence/notes |
|---|---|---|
| `git status --short --branch`, `git worktree list`, `git branch --list` | PASS | 6 worktrees, 14 local branches; install root carries other agents' uncommitted records and data, untouched |
| read `AGENTS.md`, `PROTOCOL.md`, `DISK-LAYOUT.md`, `CURRENT.md`, `.launch/STATE.md`, `.launch/SLICES.md` | PASS | T2, P5; live-money routing excluded |
| read `governor.py`, `engine.py`, `checks.py`, paper pilot F20 code, session-peak tests | PASS | see Decision rationale |
| read held-marks record in `.claude/worktrees/magical-taussig-9dceb1` (read-only) | PASS | its own record says 9 of 11 runs latch, before and after |
| no source, test, or other agent's file edited | PASS | this record is the only write |

## Files changed

- `agent_context/work/active/20260929-1000Z-claude-backtest-session-peak-reset.md` (new, this record)

## Blockers and conflicts

- **Founder decision pending:** daily-peak reset baseline; whether a daily halt ends at the next
  session while a total-drawdown halt latches; `KillSwitchEvent` timestamps. Asked in chat.
- **`src/quant_system/backtest/engine.py` is claimed** by
  `20260929-0431Z-claude-backtest-engine-held-position-marks.md`, which lives only in its worktree
  (`D:\quant_system\.claude\worktrees\magical-taussig-9dceb1`, branch `claude/magical-taussig-9dceb1`,
  uncommitted diff of +7 lines in `run()`). Its install-root copy was refused by the desktop app's
  worktree hook, so under PROTOCOL 8.1 it is a claim other agents cannot see from here. Both changes
  touch the same loop. I will not edit `engine.py` until that branch merges or its owner agrees in
  writing. Its measurements also cap mine: it reports that with held marks repaired, callers still
  trip the daily limit, so my "before" for each caller must be taken on the same base it uses.
- **Pinned number:** `20260824-codex-real-journey-api-wiring.md` pins six trades for the UI default
  backtest. The held-marks record already says that moves (6 -> 13); this change would move it again.
  A notice follows once numbers exist.
- `.launch/STATE.md` and `CURRENT.md` are claimed elsewhere and are not touched.

## Stop point

Record filed. No code written. About to ask the founder the three questions.

## Next safe action

Wait for the founder's answers; then update this record with them, name the workspace and branch
here, and only then create it.
