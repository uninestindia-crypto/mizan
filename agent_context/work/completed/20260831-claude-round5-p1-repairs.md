# Active work: the five P1 findings from round five

STATUS: COMPLETED
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

## Commands and outcomes

```
ruff check . / ruff format .  -> clean, 531 files
mypy src                      -> Success, 141 source files
pytest -q                     -> 1191 passed (was 1184)
```

All five P1s repaired, each mutation-tested before being claimed:

| # | Mutants | Result |
|---|---:|---|
| F7 | 1 | all killed |
| F1 | 2 | all killed |
| F23 | 4 | all killed |
| F4 | 3 | all killed |
| F20 | 4 | all killed |

## The lesson this round, recorded because it is worth more than the fixes

**Seven tests in this sequence passed while being worthless**, and mutation testing is the only
thing that has ever caught one. F23's test took six attempts: it allowlisted names rather than
resolving them; matched `priced` as a substring of `unpriced`; joined every guard in a loop and
resolved identifiers until an unrelated chain satisfied it; expanded definitions into a blob where
`in base_market` leaked in from elsewhere; and asked a question narrow enough to be decidable but
missed a universe reaching the loop through an intermediate.

Every failure had the same shape: reaching for a general static analysis where a **located
assertion** would do. What ships for F23 asserts four specific facts and kills four mutants. F20's
first test checked *where* `reset_session_peak` is called but not *what* it is called with or
whether it is reachable -- two more mutants survived until both were asserted directly.

The rule going forward: assert the specific thing that must be true, in the place it must be true,
and run the mutants before claiming the test works.

## Repaired

| # | Repair |
|---|---|
| F7 | `refresh_bars` passes `--summary-file` into its own cache; all-market summary restored to 3,359 entries |
| F1 | A failed quote **batch** fails the poll; remaining chunks still attempted. Transport failure and genuine absence are now distinguished, and the comment citing a non-existent coverage gate is gone |
| F23 | `priced` drives every quote lookup; the entry loop skips a selected name with no quote |
| F4 | `executed_rebalance` requires a non-empty book and an entry fill, not exits alone. A flat book after a rebalance is logged as an error |
| F20 | `reset_session_peak` finally has a caller: the daily peak anchors to the first live mark, before any order. Three rounds after the defect was first reported |

## Still open

Round five's 15 P2 / 9 P3, and its largest `NOT PROBED`: `portfolio_state.json` has no lock and no
compare-and-swap, and `/api/control/start` permits two sessions -- the second to finish would
silently discard the first's entire trading day.

## Next safe action

Round six, against everything since `a6f3e6f1`.
