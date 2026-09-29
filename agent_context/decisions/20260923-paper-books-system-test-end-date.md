# Decision: stop both paper books now, fix what they exposed, restart fresh as a system test

STATUS: ACCEPTED  
DATE: 2026-09-23  
OWNER: founder (decided); recorded by Claude Code in
`agent_context/work/active/20260923-claude-paper-books-stop-fix-restart.md`  
RESOLVES: Decision 2 of `20260901-two-open-paper-pilot-decisions.md`. The pilot will re-weight at
rebalance and its record restarts from session 1, which are option A's mechanics. Its purpose is a
test of the system, which is option C's framing. The restart discards nothing that was evidence.  
AMENDED: the same day. The first version, recorded in
`work/completed/20260923-claude-paper-books-end-date.md`, ran both books until XS-Monthly's first
exit on 6 Oct. Within the hour the founder chose to stop now instead: waiting only bought one live
run of XS's exit, which can be tested now by replaying past data.  
RELATED: `20260830-paper-surface-research-only-exemption.md`, which is why a `RESEARCH_ONLY` model
may run on paper at all

## Context

On 2026-09-23 the founder asked why the Rs 20L of virtual money (two Rs 10L books) is losing, and
then why the books are run at all. Measured the same day (`reports/paper_books_20260923/`):

- The books showed -Rs 49,580 (-2.48%). The market's fall accounts for about Rs 37.6k of the
  Rs 37.5k lost on price. Stock picking netted to about zero (+Rs 5.2k flagship, -Rs 4.5k XS). The
  flagship paid Rs 3,759 in fees and slippage. Rs 9,425 is HEG left out of XS's equity because its
  demerger entitlement is unpriced, and XS's marks were a week stale.
- The books cannot be evidence about the strategy. The research already answered that question:
  101 governed trials and seven screens found no edge after costs (`CURRENT.md`). The flagship runs
  `trial_mizan_h11_002`, ridge Sharpe -0.410755, DSR 0.175990 against the 0.95 gate. It never
  re-weights at rebalance, so it is not the strategy that was measured (1 Sep decision, R6-08).
- Running them exposed real defects, which is what they are good for.

## Decision

1. **Both books stopped on 2026-09-23.** The Windows tasks `QuantOS Mizan Paper Session`,
   `QuantOS Trigger Verification` and `QuantOS-XSMonthly-PaperWatch` are disabled. Nothing is
   deleted. Copies of every record are in `logs/archive/paper-books-20260923/`, fingerprinted in
   `reports/paper_books_20260923/archive-manifest.json`. The live files stay as the frozen final
   state.
2. **The stopped books are not evidence about the model**, for or against. Their P&L must not be
   cited as model performance anywhere. The same holds for the restarted books.
3. **Fix what they exposed before any restart:**
   - F1: the session report compares the book with the market like with like.
   - F2: a rebalance resets held names to their target weight, so the book runs the strategy that
     was measured.
   - F3: XS's exit path is exercised by replaying past data through the runner on a scratch copy.
   - F4: scheduling. XS's task was refused on battery, and a session left running past midnight
     blocked the next morning's run.
   - F5: corporate actions on held names. Widened while investigating HEG: the flagship had no
     corporate-action handling at all, so a split, bonus, demerger or rights issue on a held name
     was marked as a loss or gain that did not happen. Both books now detect every structural
     action NSE published for their names, from the records the refresh already stores. The
     flagship refuses to trade and the XS watch declines to value the leg until a person reviews
     the action. The founder chose on 2026-09-24 to build a review tool
     (`scripts/apply_paper_corporate_action.py`). It applies a split or bonus confirmed from the
     filing and cross-checked against NSE's published ratio, or records an acknowledgement with
     its reason, once. Pricing a demerger's new shares once they list (HEG Graphite) remains
     open.
4. **Restart fresh at Rs 10L each, as a system test**, when the fixes are verified and the founder
   says go. Same models as before: the flagship's frozen `trial_mizan_h11_002` weights and the XS
   frozen rule. The restart tests the fixes, not a new model, and its report shows the book next to
   the market so a market fall is not read as a model failure.
5. **The restart has an end date.** It ends when the restarted XS book's first cohort has exited
   and the flagship has completed two rebalances, about 23 trading sessions (roughly five weeks).
   Hard stop: 30 trading sessions after the restart.
6. **No profit is expected from the restart.** The same models still carry no demonstrated edge.
   A paper book meant to make money needs a new model that passes the 0.95 gate in backtests
   first.
7. **Rule for every paper book from now on:** its purpose (evidence or system test, not both), the
   decision its result could change, its benchmark, and its end date are written down before it
   starts.

## Restart checklist

The restart needs all of these, then the founder's go-ahead:

- F1-F5 done and tested, or explicitly deferred by the founder.
- Full test suite, `ruff check`, `ruff format --check` and strict mypy pass.
- The XS replay (F3) closes legs at the exit open and charges cost once. Cash reconciles to
  `capital - entries + proceeds`. An unpriced leg goes to `unresolved`, and no new cohort opens
  while the data ends on the exit day.
- The live state is moved into the archive, and the move is verified against the manifest. Both
  runners start from Rs 10,00,000 cash with no holdings.
- The three tasks are re-enabled with the F4 settings.

## Evidence

- Loss decomposition: `reports/paper_books_20260923/loss_decomp.py`; captured run with the SHA-256
  of every input in `output.txt`.
- Archive: `reports/paper_books_20260923/archive-manifest.json` (86 files, 3,192,592 bytes, each
  copy hash-verified).
- Model identity: `logs/paper_runs/live_paper_status.json` `model_provenance`.
- Research record: `agent_context/CURRENT.md`, "The research result, in one line".

## Rejected alternatives

- **Run to XS's first exit on 6 Oct** (this decision's first version). It kept two flawed books
  running for two weeks to test one path that a replay tests today.
- **Treat the books as strategy evidence** (option A of 1 Sep). It needs years of rebalances to
  tell skill from luck, for a question the research already answered.
- **Restart immediately without fixes.** It would reproduce the same defects on fresh money.
- **Restart with a retrained or new model.** Nothing passes the gate, and changing the model would
  mix a model test into a system test.

## Consequences

- No paper sessions run until the restart. The dashboard shows the frozen final state.
- QuantOS keeps its paper-execution capability (`.launch/STATE.md` scope).
- Decision 1 of 1 Sep, locking concurrent sessions, is not decided here and stays open.
- Nothing is promoted and no gate moves.

## Restarted, 2026-09-24

The founder said "restart" at 17:15 IST on 2026-09-24. The checklist above was run that evening:

- **Old state moved, not deleted.** All 85 live files of both stopped books matched their stop-time
  SHA-256 (none changed, none new). They were moved to
  `logs/archive/paper-books-20260923/at-restart/`, recorded in
  `reports/paper_books_20260923/restart-move-manifest.json`.
- **The morning refresh was rehearsed.** 499/500 names refreshed, the newest bar moved
  2026-09-18 -> 2026-09-23, and corporate-action records are current to 2026-09-23. All five index
  series were fetched, including the new NIFTY 500 (744 closes).
- **The tasks were re-enabled** with the F4 settings (`scripts/configure_paper_book_tasks.ps1
  -Enable`). XS did not run on enabling.

**The test's dates**, from the NSE holiday authority:

| | Date |
|---|---|
| Flagship session 1, a fresh Rs 10L book | Fri 2026-09-25, from the 09:00 task |
| XS first cohort | enters at the 2026-09-24 open (its first run is 2026-09-25 16:00, after that morning's refresh) |
| Flagship rebalances | 2026-10-12 (session 11) and 2026-10-27 (session 21) |
| XS first cohort exits | at the 2026-10-27 open, processed by the 2026-10-28 run |
| **Test ends** | **Wed 2026-10-28** (session 22), once both are done |
| **Hard stop** | **Mon 2026-11-09** (session 30) |

**At the end:**

1. The founder, or an agent with the founder's go-ahead that day, disables the three tasks.
2. A closing report scores the system against the checklist, not the P&L:
   - every trading day either ran or has a recorded reason;
   - every flagship session reconciled at 0.00 paisa;
   - both rebalances re-weighted;
   - XS closed its cohort with cost charged once;
   - every corporate action was caught and reviewed.
3. Nothing is deleted. The books' P&L is market plus costs, not evidence about the model.

## Start slipped, recorded 2026-09-28

The first days did not go to plan. Evidence is in
`agent_context/work/completed/20260928-claude-paper-books-first-days-and-end-reminder.md`.

- **The flagship's session 1, Fri 2026-09-25, was missed.**
  - The laptop was on battery with its lid closed. It hibernated at 00:31 on critical battery and
    stayed off until about 11:21. A hibernated machine is not woken by the task's `WakeToRun`.
  - Windows Update restarted the machine that afternoon, and it booted again at 20:08.
    `StartWhenAvailable` then ran the missed task at 20:16. That run ended (0xC000013A) before it
    reached the refresh, and it wrote nothing.
- **XS's first cohort entered at the 2026-09-23 open, one session early.**
  - Its 16:00 run on 09-25 read a cache ending 09-23, because the refresh is part of the flagship's
    09:00 run.
  - The formation used data to 09-22 only.
  - The cohort is kept as it is. Moving it would mean hand-editing the state, and it tests the same
    exit path.

The dates, if the flagship starts on Mon 2026-09-28:

| | Date |
|---|---|
| Flagship session 1 | Mon 2026-09-28 |
| Flagship rebalances | 2026-10-13 (session 11) and 2026-10-28 (session 21) |
| XS first cohort exits | at the 2026-10-26 open, processed by the 2026-10-27 run |
| **Test ends** | **Wed 2026-10-28**, unchanged: both are done that day |
| **Hard stop** | **Mon 2026-11-09**, unchanged: 30 trading sessions after the restart |

Each further missed flagship session moves its rebalances and the end one trading day later. It
does not move the hard stop. A one-time reminder in the founder's Claude desktop app
(`end-paper-book-test`, 2026-10-28 18:07 IST) runs the end-of-test check read-only and asks for the
go-ahead.

Two weaknesses this exposed are reported to the founder and not changed here:

- XS relies on the flagship's refresh and does not check that it happened.
- The late-start fallback `QuantOS Session Supervisor` is disabled; its last run was 2026-09-15.

## Start slipped again, recorded 2026-09-29

Evidence: `agent_context/work/completed/20260929-claude-flagship-startup-check-fix.md`.

- **A code fault was found and fixed** (`45f95604`). The scheduled run's pre-refresh check verified
  every dataset in the price cache, and the store grows by 499 datasets a day. It took 70 s on
  09-01 and 3 h 51 min on 09-21, so a 09:00 run could not begin its refresh until the afternoon.
  It now takes 68 s.
- **The founder chose to fix it and run the session by hand on 09-29.** It started at 10:10 and
  was lost. A user-mode process put the laptop to sleep at 10:34 (Kernel-Power 187, Start menu).
  The machine stayed off until 15:18, and the session ended without saving.
- **Result: as of 15:30 on 2026-09-29, session 1 has not happened.** The book is still a fresh
  Rs 10L. XS is unaffected and continues from its 09-23 cohort.
- **The dates now depend on when session 1 really runs.** Session 21 is the second rebalance,
  and the test ends when it and XS's exit at the 2026-10-26 open are done. The hard stop stays
  Mon 2026-11-09, which is 30 trading sessions after the restart.
- **Open founder decision: the laptop.** No script can stop an explicit Sleep. The flagship needs
  the laptop awake and on mains from 09:00 to 15:30 on trading days, or an always-on machine.
