# Handoff: end the paper-book system test on 2026-10-28

STATUS: READY_FOR_ADOPTION: the test runs unattended until its end on 2026-10-28  
FROM: Claude Code session  
TO: unassigned; the same session continues if the founder answers here  
DATE_UTC: 2026-09-24T06:25:00Z  
ACTIVE_RECORD: none. The fixes and restart are complete in
`agent_context/work/completed/20260923-claude-paper-books-stop-fix-restart.md`. Standing notice:
`agent_context/work/active/20260924-NOTICE-paper-books-system-test-running.md`

## Objective and acceptance criteria

End the restarted system test and report on it. The test ends Wed 2026-10-28 (session 22), once
XS's first cohort has exited at the 2026-10-27 open and the flagship has made its 2026-10-12 and
2026-10-27 rebalances. The hard stop is Mon 2026-11-09. The closing report scores the system, not
the P&L:

- every trading day ran, or has a recorded reason;
- every flagship session reconciled at 0.00 paisa;
- both rebalances re-weighted held names (`[REWEIGHT PROPOSAL SUBMITTED]` in the logs);
- XS closed its cohort at the exit open, with cost charged once and cash reconciling;
- every corporate action was caught and reviewed.

## Completed

- Both books stopped. The three paper-book Windows tasks are `Disabled`, confirmed 2026-09-24 11:50
  IST. Their records are archived with a hash manifest (`7c63df15`).
- F1: the report compares the book and the market over the same dates, at the book's exposure,
  against the NIFTY 500 index (`c1a7a2bd`).
- F2: re-weighting at rebalance (`8f49c7c7`).
- F3: XS exit replay on real data, all checks passing (`43f27b89`).
- F4: task settings corrected but left disabled (`196c2b8b`).
- F5: the flagship refuses to trade a holding carried across a split, bonus, demerger or rights
  issue (`8f49c7c7`). Then, on the founder's 2026-09-24 choice:
  - the review tool `scripts/apply_paper_corporate_action.py`, for both books;
  - the same detection for XS legs;
  - flagship schema v7 `reviewed_actions`.
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
- XS reports each closed leg's research return (`net`) from the cached bars, not from the adjusted
  leg. After a reviewed split the cash is right (whole shares x exit price), but that `net` is
  only as consistent across the split as the cache is.
- An order submitted before its own symbol has any quote is risk-checked only at first fill,
  without held-position prices, so it is refused whenever the book holds anything
  (`PORTFOLIO_VALUATION_UNAVAILABLE`). The runner never submits for an unquoted name, so this
  does not bite today.

## Exact stop point

Restarted 2026-09-24 about 17:45 IST:

- Old state was verified and moved (85 files, all unchanged since the stop).
- The morning refresh was rehearsed: bars to 2026-09-23 and the NIFTY 500 series fetched.
- All three tasks are enabled, and neither book has a state file yet.

First runs: the flagship at 2026-09-25 09:00, XS at 16:00 the same day.

## Next safe action

- Check each morning's session report, or `logs/trigger_verification.log`.
- On an exit 11, or an XS leg unvalued for `CORPORATE_ACTION_NOT_REVIEWED`, review the action with
  `scripts/apply_paper_corporate_action.py`.
- On 2026-10-28, after XS processes its exit, get the founder's go-ahead. Then disable the three
  tasks and write the closing report against the criteria above.

## Do not do

- Do not re-enable the tasks or run a session before the founder's go-ahead.
- Do not delete anything under `logs/paper_runs/`, `logs/xs_monthly_new/` or the archive.
- Do not cite the stopped books' P&L as model performance.
