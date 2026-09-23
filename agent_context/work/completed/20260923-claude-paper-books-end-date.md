# Completed work: record the founder's answer on the paper books, and their end date

STATUS: COMPLETED. SUPERSEDED the same day by
`agent_context/work/active/20260923-claude-paper-books-stop-fix-restart.md`: the founder amended the
decision to stop both books at once, and the NOTICE below was renamed
`20260923-NOTICE-paper-books-stopped-for-fixes.md`.  
OWNER: Claude Code session, on founder instruction  
TOOL: Claude Code  
STARTED_UTC: 2026-09-23T10:24:57Z  
STARTING_REVISION: 525b39978ead92f29aacd43a9da3c28ea3a02216  
WORKTREE_OR_BRANCH: `D:\quant_system`, `main` (shared checkout; new files plus one status line only)

## Objective

The founder asked why the two Rs 10L paper books are losing, then why they are run at all, then
said: "yes record it and set the end date". Record that answer as a decision every agent works to:
the paper books are a test of the system, not evidence about the strategy (Decision 2 of
`agent_context/decisions/20260901-two-open-paper-pilot-decisions.md`, option C), and both books end
after XS-Monthly's first exit is processed.

## Owned paths

- `agent_context/work/completed/20260923-claude-paper-books-end-date.md` (this record)
- `agent_context/decisions/20260923-paper-books-system-test-end-date.md` (new)
- `agent_context/work/active/20260923-NOTICE-paper-books-end-6-oct.md` (new, standing until the end
  sequence completes)
- `agent_context/decisions/20260901-two-open-paper-pilot-decisions.md`: the `STATUS` line only.
  The raising record (`work/completed/20260901-1030Z-claude-seven-item-sweep.md`) is completed and
  no active record claims this file.
- `reports/paper_books_20260923/` (new: the analysis script and its captured output)

## Non-goals

- No code change to any runner, report or dashboard. `scripts/run_paper_pilot_session.py` and the
  XS watch are claimed by other active records.
- No change to Windows scheduled tasks. Switching them off is a founder action, or an agent's with
  the founder's explicit go-ahead on the day.
- No change to book state: `logs/paper_runs/**`, `logs/xs_monthly_new/**`, `data/evidence/paper/**`.
- No edit to `agent_context/CURRENT.md` (claimed by `20260820-codex-slice4-ridge-training.md` and
  `20260821-claude-ci-workflow.md`) or to `.launch/`.
- No commit. The founder has not asked for one.

## Plan

1. Startup checks: git state, worktrees, branches, `.launch/STATE.md`, `DISK-LAYOUT.md`, claims on
   the paths above. DONE.
2. Create this record. DONE.
3. Save the loss analysis with input hashes under `reports/paper_books_20260923/`. DONE.
4. Write the decision record. DONE.
5. Mark Decision 2 answered in the 1 Sep decision's `STATUS` line. DONE.
6. Write the standing NOTICE. DONE.
7. Run `scripts/audit-agent-claims.ps1` and `scripts/audit-disk-layout.ps1`; complete. DONE.

## Current step

Complete.

## Decision rationale

The founder chose option C of the 1 Sep decision in substance: the books observe the system, not
the strategy. Evidence that the books cannot be strategy evidence: 101 governed trials and seven
screens found no edge after costs (`CURRENT.md`); the flagship runs `trial_mizan_h11_002`, ridge
Sharpe -0.410755, DSR 0.175990 against a 0.95 gate, `RESEARCH_ONLY`
(`logs/paper_runs/live_paper_status.json` `model_provenance`); it never re-weights at rebalance
(1 Sep decision, R6-08), so it is not the measured strategy; and two trades in three weeks cannot
separate skill from luck.

End date chosen as XS-Monthly's first exit, because that close path (exit at the open, the 0.224%
round-trip cost charged once, HEG sent to `unresolved`) is the main piece of the system neither
book has exercised on live data. The flagship has exercised entry (2026-08-31) and a rebalance
(2026-09-21), both reconciled at 0.00 paisa.

The exit date is derived, not assumed: `settle_positions` exits at `calendar[pos_of[entry] + 21]`
(`src/quant_system/research_xs_monthly/paper.py:316`); entry 2026-09-02 plus 21 NSE sessions, with
2026-09-14 and 2026-10-02 closed per `data/authorities/nse-trading-holidays.json`, is
**Mon 2026-10-05**. The cache XS reads is refreshed only by the flagship's 09:00 scheduled run
(`scripts/run_scheduled_paper_session.py:45`; no other script refreshes it, and
`scripts/daily_auto_sync.ps1` stages only `data/evidence` and `data/authorities`), and a refresh
reaches the previous session (the 2026-09-21 refresh ended at 2026-09-18). So the first run able to
close the cohort is XS on **Tue 2026-10-06** after that morning's refresh.

The end order matters. `latest_signal` enters at the newest cached bar
(`paper.py:230,243`) and the runner reopens only when that entry is later than the last exit
(`scripts/run_xs_monthly_paper_watch.py`, `if signal["entry_date"] > last_exit`). With the cache
ending 2026-10-05 the closing run cannot reopen; with any later bar it closes and opens a new
99-name cohort in the same pass. So the flagship task (the only refresher) is switched off after
its 6 Oct session, before any refresh past 5 Oct, and XS is run after that.

Rejected: ending immediately (the XS close path would never be tested); ending on the flagship's
next rebalance (it adds nothing the 21 Sep rebalance did not test); adding a stop guard to the
runners (claimed paths, and more than was asked); editing `CURRENT.md` (claimed; the NOTICE is the
protocol's channel to every agent).

## Commands and outcomes

| Command | Result | Evidence/notes |
|---|---|---|
| `git status --short --branch`; `git worktree list`; `git branch --list` | clean at `525b3997` | 2 codex worktrees and 10 non-default branches, none touching these paths |
| `.venv\Scripts\python.exe reports\paper_books_20260923\loss_decomp.py` | PASS, exit 0 | Flagship rebuilt from its fills to Rs 988,174.15, equal to the status file; output with input SHA-256 in `output.txt` |
| `.venv\Scripts\ruff.exe format` / `check` / `format --check` on `loss_decomp.py` only | PASS | No repo-wide formatter run |
| `Get-ScheduledTask QuantOS-XSMonthly-PaperWatch` | finding | Last result `0x800710E0` (refused); `DisallowStartIfOnBatteries=True`, `StartWhenAvailable=False`, `WakeToRun=False`; last successful run 2026-09-17 |
| `powershell -ExecutionPolicy Bypass -File scripts/audit-agent-claims.ps1` | PASS, exit 0 | Every workspace has a visible claim and every claim resolves |
| `powershell -ExecutionPolicy Bypass -File scripts/audit-disk-layout.ps1 -Fast` | PASS, exit 0 | No stray QuantOS directories |

Loss decomposition, measured 2026-09-23 from the books' own state files:

- Shown: flagship -11,825.85 (-1.18%, marked 2026-09-21) + XS -37,754.46 (-3.78%, marked at the
  2026-09-16 open) = -49,580.31 on Rs 20L.
- Flagship: price moves -9,174.70 (including 1,107.73 slippage in fills) and fees -2,651.15.
- XS: -28,329.46 on 98 priced legs; -9,425.00 is HEG at cost, excluded from equity because its
  HEG Graphite entitlement is unpriced. At the 2026-09-18 close the 98 legs were -9,151.47.
- Market: NIFTY 50 -3.99% to its 2026-09-15 low; NIFTY 500 equal-weight -3.72%. The market alone
  accounts for about 37.6k of the 37.5k of price losses; stock picking was +5.2k (flagship, +0.61 pp
  against the NIFTY 500) and -4.5k (XS, -0.53 pp, in a window where last month's winners fell more
  than its losers).

## Files changed

- `agent_context/decisions/20260923-paper-books-system-test-end-date.md`: the decision, end
  sequence, closing checklist and pre-end actions.
- `agent_context/decisions/20260901-two-open-paper-pilot-decisions.md`: `STATUS` line only
  (Decision 2 answered; Decision 1 still open).
- `agent_context/work/active/20260923-NOTICE-paper-books-end-6-oct.md`: standing notice to the
  owners of the paper-book paths and the `CURRENT.md` claimants.
- `reports/paper_books_20260923/loss_decomp.py` and `output.txt`: the reproducible analysis.
- This record.

## Blockers and conflicts

- The XS scheduled task is being refused by Windows. The end sequence needs one XS run after the
  6 Oct refresh: on AC power at 16:00, or started by hand. Founder action.
- `CURRENT.md` does not yet mention the decision; its claimants are addressed by the NOTICE.

## Stop point

All files written; both audits pass. Nothing committed: the working tree holds the one modified
decision file and four new paths listed above.

## Next safe action

On Tue 2026-10-06, follow the end sequence in
`agent_context/decisions/20260923-paper-books-system-test-end-date.md`.
