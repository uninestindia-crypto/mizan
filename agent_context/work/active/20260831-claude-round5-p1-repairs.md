# Active work: the five P1 findings from round five

STATUS: ACTIVE
OWNER: Claude Code
TOOL: Claude Code
STARTED_UTC: 2026-08-31T17:15:00Z
STARTING_REVISION: a6f3e6f1
WORKTREE_OR_BRANCH: D:\quant_system on main

## Objective

Close all five P1s in `.launch/reports/RED-TEAM-20260831-ROUND5.md`, in order of when they bite.
Four of the five are composition defects created by this batch of repairs.

| # | Finding | Bites |
|---|---|---|
| F7 | `refresh_bars` omits `--summary-file`, so the NIFTY500 refresh overwrites the all-market ingestion summary. 3,359 entries replaced by 500, already committed in `e853376a` | **tomorrow 09:00, daily** |
| F1 | A partial quote failure returns normally and resets `consecutive_quote_failures`, so a poll losing 60% of the feed counts as a success. Happened live twice today | tomorrow, silently |
| F23 | `base_market[sym]` at `:1052` is still unguarded; two missing quotes abort the session | tomorrow, loudly |
| F4 | `total_fills_count > 0` is satisfied by exits alone, so an all-exits-no-entries rebalance records as completed | session 11 |
| F20 | "Marked at the session open" is the last trade price at boot, which at 09:00 is the previous close. An overnight gap trips the daily rule with zero intraday movement | session 11 |

Plus the round-five finding against my own guard: the resolving AST test is defeated by an
annotated assignment, because `ast.AnnAssign` is not `ast.Assign` and resolution silently falls
back to the variable's own name.

## Non-goals

- Round five's 15 P2 / 9 P3.
- The concurrency hole on `portfolio_state.json` -- no lock, no compare-and-swap. Real, and the
  report's own largest `NOT PROBED` item. Separate work.

## Owned paths

- scripts/run_scheduled_paper_session.py
- scripts/run_paper_pilot_session.py
- data/evidence/market-analysis/all-market-ingestion-summary.json (restore only)
- tests/test_paper_pilot_carried_session.py
- tests/test_scheduled_paper_session.py
- agent_context/work/active/20260831-claude-round5-p1-repairs.md

## Current step

F7.
