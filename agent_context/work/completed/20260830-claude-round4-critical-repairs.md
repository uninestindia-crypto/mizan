# Active work: the two blockers round four found in tomorrow's session path

STATUS: COMPLETED
OWNER: Claude Code
TOOL: Claude Code
STARTED_UTC: 2026-08-31T03:50:00Z
STARTING_REVISION: 46c7bb67
WORKTREE_OR_BRANCH: D:\quant_system on main

## Objective

The founder needs the pilot running automatically at today's open (2026-08-31, 09:00 IST). Round
four (`.launch/reports/RED-TEAM-20260830-ROUND4.md`) reached claim 6 of 8 before an API limit and
DISPROVED claim 5 with two blockers.

## What round four proved about today specifically

**Session 1 completes.** The adjudicator drove the real `run_paper_session` end to end -- the first
time anyone has -- and it reconciled, persisted a valid schema-v3 file, advanced the hold clock and
set the peak. Today's run is not at risk. The failure arrives at **session 11**, the first
rebalance.

## Repaired

| Finding | Repair |
|---|---|
| P1-1 | `initial_equity` was `portfolio.ledger_funding()` -- cash + holdings **at cost** + carried fees, invariant to market price. The 4% daily rule therefore measured cumulative unrealized loss since inception, and a 5.63% drift over ten sessions with zero intraday movement halted the book on its first exit. Now seeded from equity **marked at the session open**, using the quotes already fetched before the governor is built |
| P1-2 | A halting session reconciles perfectly, so `main()` printed `[PAPER PILOT SUCCESS]` and exited 0 for the session that permanently stopped the pilot. The payload now carries a `risk` block; the banner distinguishes a halt; the exit code is 9 |
| (compounding) | `run_scheduled_paper_session.cmd` never propagated `%ERRORLEVEL%`, so Task Scheduler recorded `LastTaskResult: 0` for every run -- including a Saturday refusal that returned 2. Now `endlocal & exit /b %RC%` |

## Evidence

Round four's own session-11 scenario, re-tested against both seedings:

```
OLD  initial_equity=ledger_funding() [cost]  -> killed=True  reason=DAILY_DRAWDOWN_LIMIT_BREACHED
NEW  initial_equity=marked opening equity    -> killed=False reason=MISSING_PRICE_FOR_RISK_VALUATION
NEW  genuine 4.5% intraday fall              -> killed=True  reason=DAILY_DRAWDOWN_LIMIT_BREACHED
```

The multi-session drift no longer trips the daily rule; a real intraday fall still does.

```
ruff check . / ruff format .  -> clean, 519 files
mypy src                      -> Success, 141 source files
pytest -q                     -> 1176 passed (was 1173)
```

## Note on my own previous repair

`46c7bb67` claimed to fix exactly this defect and its commit message describes it accurately -- "a
session that opened 4% below its all-time high and never moved intraday halted the book on its
first order". The fix separated the two peaks correctly and then seeded the daily one from a cost
figure, so the described failure survived unchanged. The separation was necessary and insufficient.

## Still open

Round four's claims 7 and 8 were never reached, and its P2s/P3s stand: the unpriced-quote fallback
to a hardcoded Rs 1000.00 labelled as a real exchange price (P2-1), the capital table not balancing
by the carried entry fees (P2-4), the loose AST detector (P2-3), and the `max()` floor weakening
the total switch (P2-2). Earlier rounds' P2s and the three false commit-message claims also stand.

## Next safe action

Resume round four at claim 7, and commission round five against these repairs. Today's run proceeds
on the founder's informed decision, not on a clean adjudication.
