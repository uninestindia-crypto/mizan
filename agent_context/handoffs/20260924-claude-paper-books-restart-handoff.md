# Handoff: restart the paper books as a system test

STATUS: BLOCKED on founder decisions (see "Next safe action")  
FROM: Claude Code session  
TO: unassigned; the same session continues if the founder answers here  
DATE_UTC: 2026-09-24T06:25:00Z  
ACTIVE_RECORD: `agent_context/work/active/20260923-claude-paper-books-stop-fix-restart.md`

## Objective and acceptance criteria

Restart both paper books fresh at Rs 10L each as a labelled system test, per
`agent_context/decisions/20260923-paper-books-system-test-end-date.md`, once its restart checklist
holds and the founder says go.

## Completed

- Both books stopped. The three paper-book Windows tasks are `Disabled`, confirmed 2026-09-24 11:50
  IST. Their records are archived with a hash manifest (`7c63df15`).
- F1: the report compares the book and the market over the same dates, at the book's exposure,
  against the NIFTY 500 index (`c1a7a2bd`).
- F2: re-weighting at rebalance (`8f49c7c7`).
- F3: XS exit replay on real data, all checks passing (`43f27b89`).
- F4: task settings corrected but left disabled (`196c2b8b`).
- F5: the flagship refuses to trade a holding carried across a split, bonus, demerger or rights
  issue (`8f49c7c7`).
- Full suite 1670 passed; ruff and strict mypy clean; both audits pass.

## In progress

- Nothing half-done. Five local commits are not pushed; the nightly `QuantOS-DailyAutoSync` pushes
  `main` when it runs.

## Files and ownership

- All committed. See the active record's owned paths and the commits above.

## Verification

| Command | Result | Notes |
|---|---|---|
| `pytest tests/` | PASS | 1670 passed in 752 s |
| `ruff check .`; `ruff format --check .`; `mypy src launcher.py scripts` | PASS | 710 files; 211 source files |
| `reports/paper_books_20260923/xs_exit_replay.py` | PASS | ALL CHECKS PASSED |

## Known failures and risks

- A full rebalance loop has no test harness; the first restart rebalance is the live test of F2's
  wiring. Watch the log for `[REWEIGHT PROPOSAL SUBMITTED]`.
- Corporate-action records are fetched up to the day before a run, so an action on the session day
  is caught the following session.
- 23 Sep's missed run is unexplained, because Task Scheduler history is off.

## Exact stop point

`8f49c7c7` committed; the working tree was clean. Waiting on the founder.

## Next safe action

1. Founder decisions:
   - F5(a): a tool to adjust a split or bonus holding, or refusal-only.
   - F5(b): the same guard for the XS book.
   - Two Windows settings: turn on Task Scheduler history, and set the lid-close action on AC.
2. Then run the decision's restart checklist:
   - move the live state into `logs/archive/paper-books-20260923/` and verify it against the
     manifest;
   - run `powershell -ExecutionPolicy Bypass -File scripts/configure_paper_book_tasks.ps1 -Enable`;
   - the first flagship session starts a pristine book. It needs `--force-new-portfolio` only if old
     session reports remain in `logs/paper_runs/`.

## Do not do

- Do not re-enable the tasks or run a session before the founder's go-ahead.
- Do not delete anything under `logs/paper_runs/`, `logs/xs_monthly_new/` or the archive.
- Do not cite the stopped books' P&L as model performance.
