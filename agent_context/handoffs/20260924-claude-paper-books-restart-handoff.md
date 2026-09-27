# Handoff: end the paper-book system test on 2026-10-28

STATUS: READY_FOR_ADOPTION: the test runs unattended until its end on 2026-10-28  
FROM: Claude Code session  
TO: unassigned; the same session continues if the founder answers here  
DATE_UTC: 2026-09-24T06:25:00Z  
UPDATED_UTC: 2026-09-27T23:40:53Z, the start slipped (see "Exact stop point")  
ACTIVE_RECORD: none. The fixes and restart are complete in
`agent_context/work/completed/20260923-claude-paper-books-stop-fix-restart.md`; the first days are
recorded in `agent_context/work/completed/20260928-claude-paper-books-first-days-and-end-reminder.md`.
Standing notice: `agent_context/work/active/20260924-NOTICE-paper-books-system-test-running.md`

## Objective and acceptance criteria

End the restarted system test and report on it. The test ends on Wed 2026-10-28. Both of these
must be done by then:

- XS's first cohort has exited, at the 2026-10-26 open, processed by the 10-27 run.
- The flagship has made its two rebalances, on 2026-10-13 and 2026-10-28, if its first session is
  2026-09-28.

The hard stop is Mon 2026-11-09. The closing report scores the system, not the P&L:

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
- Restarted 2026-09-24 with the tasks re-enabled (`c270017b`).

## In progress

- Nothing half-done. The nightly `QuantOS-DailyAutoSync` pushes local commits on `main`.

## Files and ownership

- All committed. See the active record's owned paths and the commits above.

## Verification

| Command | Result | Notes |
|---|---|---|
| `pytest tests/` | PASS | 1670 passed in 752 s |
| `ruff check .`; `ruff format --check .`; `mypy src launcher.py scripts` | PASS | 710 files; 211 source files |
| `reports/paper_books_20260923/xs_exit_replay.py` | PASS | ALL CHECKS PASSED |

## Known failures and risks

- **The laptop must be on mains power.** On battery with the lid closed, Windows hibernates
  ("Austerity Battery Drain Budget Exceeded", or critical battery). A hibernated machine is not
  woken by `WakeToRun`. This is how the flagship's first session, 2026-09-25, was lost.
- **XS takes its prices from the flagship's 09:00 refresh without checking that it ran.** On
  2026-09-25 it entered at the 09-23 open from a cache ending 09-23, and its marks stay as old as
  the cache.
- **The late-start fallback `QuantOS Session Supervisor` is disabled**; its last run was
  2026-09-15. On 09-25 the missed 09:00 run was started only after a reboot, at 20:16, after the
  close.
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
- All three tasks were enabled, and neither book had a state file.

At 2026-09-28 05:10 IST, before that day's runs:

- **Flagship:** no session has run and there is no portfolio file. Session 1 is due at 09:00 today.
  The 2026-09-25 session was missed; its evidence is in the decision record, section "Start
  slipped, recorded 2026-09-28". The laptop was on battery at 25%, and the founder was asked to plug
  it in.
- **XS:** 99 open legs, all entered at the 2026-09-23 open. Cash is 94,409.99, and the marks are as
  of 09-23.
- **Reminder:** a one-time reminder is set in the founder's Claude desktop app,
  `end-paper-book-test`, for 2026-10-28 18:07 IST.

## Next safe action

- Check each morning's session report, or `logs/trigger_verification.log`.
- On an exit 11, or an XS leg unvalued for `CORPORATE_ACTION_NOT_REVIEWED`, review the action with
  `scripts/apply_paper_corporate_action.py`.
- On 2026-10-28:
  - the flagship makes its second rebalance, and XS has processed its exit the evening before;
  - the reminder runs the end-of-test check read-only and asks the founder for the go-ahead;
  - then disable the three tasks and write the closing report against the criteria above.
- Each further missed flagship session moves its rebalances and the end one trading day later.

## Do not do

- Do not disable, re-enable or reconfigure the three tasks, or run a session by hand, without the
  founder's go-ahead.
- Do not delete anything under `logs/paper_runs/`, `logs/xs_monthly_new/` or the archive.
- Do not cite either book's P&L as model performance.
