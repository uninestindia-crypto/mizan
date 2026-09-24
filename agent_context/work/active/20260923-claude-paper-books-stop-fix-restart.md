# Active work: stop the paper books, fix what they exposed, prepare a fresh restart

STATUS: ACTIVE (unblocked 2026-09-24: founder chose to build the adjustment tool and add the guard to XS)  
OWNER: Claude Code session, on founder instruction  
TOOL: Claude Code  
STARTED_UTC: 2026-09-23T11:05:00Z  
STARTING_REVISION: 525b39978ead92f29aacd43a9da3c28ea3a02216  
WORKTREE_OR_BRANCH: `D:\quant_system`, `main` (shared checkout; no other agent active in the last
6 hours; explicit paths staged only)  
FOLLOWS: `agent_context/work/completed/20260923-claude-paper-books-end-date.md`

## Objective

Founder instruction, 2026-09-23, after reviewing why the Rs 20L paper books lose money:
"yes go ahead, stop them and start fixing". This amends the decision recorded an hour earlier
(end on 6 Oct) to: stop both books now, keep their records, fix what they exposed, then restart
fresh at Rs 10L each as a labelled system test.

## Owned paths

Records:

- `agent_context/work/active/20260923-claude-paper-books-stop-fix-restart.md` (this record)
- `agent_context/decisions/20260923-paper-books-system-test-end-date.md` (my uncommitted file,
  rewritten for the amended decision)
- `agent_context/work/active/20260923-NOTICE-paper-books-end-6-oct.md`, renamed to
  `20260923-NOTICE-paper-books-stopped-for-fixes.md` (my uncommitted file)
- `agent_context/decisions/20260901-two-open-paper-pilot-decisions.md`: `STATUS` line only
- `agent_context/work/completed/20260923-claude-paper-books-end-date.md`: a forward pointer only
- `reports/paper_books_20260923/` (adds the archive manifest)
- `logs/archive/paper-books-20260923/` (new, gitignored copies of both books' records)

Code paths are added here, each before its first edit. Every one is claimed by an older active
record, so each edit is made on founder instruction and announced in the NOTICE.

F1 (report compares like with like):

- `src/quant_system/execution/paper_portfolio.py`: schema v6 records `inception_on` and one closing
  equity mark per completed session; v3-v5 files migrate. Money path; named in NOTICEs under
  `20260821-1048Z-claude-slice4-redteam-repair.md` (HANDOFF_REQUIRED; its pending conditions
  concern modeling and evidence files, not this one) and listed do-not-touch by Hermes.
- `tests/test_paper_portfolio.py`: v6 round-trip and migration tests, added alongside.
- `scripts/run_paper_pilot_session.py`: `session_baselines` and its call site, the report section,
  and passing the closing equity to `state_from_ledger`.
- `tests/test_paper_report_baselines.py`: rewritten to the corrected semantics, keeping each old
  test's intent.
- `scripts/ingest_macro_regimes.py` (unclaimed): adds the NIFTY 500 index, the book's own
  universe, as a benchmark series. `NSE_INDEX|Nifty 500` verified against the provider on
  2026-09-23: HTTP 200, 15 daily closes 2026-09-01..2026-09-22.

F2 (re-weight at rebalance):

- `scripts/run_paper_pilot_session.py`: `reweight_orders`, the rebalance step that calls it, and the
  drift report's wording.
- `tests/test_paper_rebalance_reweight.py` (new).

F5 (corporate actions on held names):

- `src/quant_system/data/held_corporate_actions.py` (new) and
  `tests/test_held_corporate_actions.py` (new).
- `scripts/run_paper_pilot_session.py`: the start-of-session check that refuses to trade across one.

F5 follow-up, founder instruction 2026-09-24 ("yes build the tool and add it to XS"):

- `src/quant_system/data/held_corporate_actions.py`: ratio parsing, the NSE cross-check, and
  share and cost adjustment arithmetic.
- `src/quant_system/execution/paper_portfolio.py`: schema v7 records each reviewed corporate
  action, so an adjustment and its record are one hash-protected write and cannot be applied twice.
- `scripts/run_paper_pilot_session.py`: the guard skips reviewed actions, its refusal names the
  tool, and the report lists reviewed actions.
- `scripts/apply_paper_corporate_action.py` (new): the tool, for both books. Dry run by default;
  `--apply` writes.
- `src/quant_system/research_xs_monthly/paper.py` and `scripts/run_xs_monthly_paper_watch.py`: XS
  legs held across a structural action in the NSE records are unpriced until reviewed, beside the
  hand-kept demerger list. Hermes Agent's claim; founder instruction.
- `reports/paper_books_20260923/xs_exit_replay.py`: mirrors any new XS flags if the runner's
  behaviour changes.
- Tests: `tests/test_held_corporate_actions.py`, `tests/test_paper_portfolio.py`,
  `tests/test_apply_paper_corporate_action.py` (new), and an XS test file.

F4 (scheduling):

- `scripts/configure_paper_book_tasks.ps1` (new): applies the corrected settings to
  `QuantOS Mizan Paper Session` and `QuantOS-XSMonthly-PaperWatch`, and enables them only with
  `-Enable`. It changes settings only; the actions, triggers and principals stay as their owners
  registered them. The XS task is Hermes Agent's; the settings change is on founder instruction
  and announced in the NOTICE.

## Non-goals

- No new model, retrain, or change to model weights or the XS rule.
- No restart of either book. That needs the fixes verified and the founder's go-ahead.
- No deletion of any book record. Copies are archived; the live files stay as frozen.
- No change to `CURRENT.md` or `.launch/`.

## Plan

1. Stop both books: disable the three Windows tasks. DONE, see below.
2. Archive copies of both books' records with a SHA-256 manifest. DONE.
3. Rewrite the decision and NOTICE for the amended plan; point the 1 Sep decision at it; commit
   the records (founder asked for the commit). DONE, `7c63df15`.
4. Fixes, in order (status in the table below):
   - F1: session report baselines compare like with like.
   - F2: rebalance resets held names to target weight (the measured strategy).
   - F3: XS exit path checked by replaying past data through the runner on a scratch copy.
   - F4: scheduling: XS refused on battery; a session running past midnight blocks the next day.
   - F5: demerger entitlements with no price (HEG Graphite).
5. Restart checklist for the founder. PENDING the founder's answers.

## Current step

5. F1-F5 done, including the review tool and the XS guard. Waiting on the founder: two Windows settings,
and the restart go-ahead.

## Fix status

| Fix | Status | Evidence |
|---|---|---|
| F1 report compares like with like | DONE | Portfolio schema v6 records `inception_on` and one `EquityMark` (equity, invested) per completed session. The report reads the book and the index on the same dates, scales the index to the book's average invested share, benchmarks against the NIFTY 500 index (NIFTY 50 fallback, with a caveat), and states the size-weighting tilt. The sizing rows compare the held names only. Recomputed on the stopped flagship's archived marks, 21 Sep: old report "Selection vs NIFTY 50 +1.87 pp"; new report "Picking and costs +1.2456 pp" against the NIFTY 500 index at 85.5% invested, over the same dates. The weighting caveat explains the rest; equal-weight picks were +0.61 pp |
| F3 XS exit replay | DONE | `reports/paper_books_20260923/xs_exit_replay.py`, output `xs_exit_replay_output.txt`: both cases ALL CHECKS PASSED through the real runner in scratch state |
| F4 scheduling | DONE (settings); two founder items | The 22 Sep loss: the 21 Sep session slept from ~15:01 to the 22 Sep 09:00 wake, finished 10 s after the trigger, and `MultipleInstances=IgnoreNew` dropped the new run. `scripts/configure_paper_book_tasks.ps1` applied and verified `Queue` on the session task. On the XS task it set battery start allowed, no stop on unplug, start-when-available, wake-to-run and `Queue`. All three tasks remain `Disabled`. Unresolved: 23 Sep had no trigger and no late start although start-when-available is set. Task Scheduler history (`Microsoft-Windows-TaskScheduler/Operational`) is disabled, so the cause is unconfirmed; enabling it is a system setting, the founder's call. The lid-close sleep that stops a session mid-afternoon is also a Windows power setting for the founder. Noted, not changed: the XS task runs through Hermes' `uv run`, which re-installs the editable package into the shared `.venv` on every run (observed in its `task.log`) |
| F2 re-weight at rebalance | DONE | `reweight_orders` is the pure rule: trim or top up held, still-selected names to equal weight, with a 10% band, no second order while one is open, no sale of a selected name to zero, and top-ups sharing 95% of cash in rank order. `reweight_plan(engine, ...)` reads open orders, fills and cash from the engine; a partly filled buy reserves only its remainder. The session loop submits the plan after the entry loop and after the daily drawdown anchor. A first version submitted from a helper defined above the anchor, and `test_risk_governor_session_peaks` caught it. 18 tests: 13 on the rule, 5 against a real `PaperPilotEngine` (a trim fills to target; no second order while one is open; nothing further once at target; cash promised to an open buy is not spent twice; a partial fill reserves only its remainder). The drift report's "permanent" wording is corrected. Not exercised end to end: a full rebalance loop has no harness in the suite, so the first restart rebalance is its live test; its log lines are `[REWEIGHT PROPOSAL SUBMITTED]`. Observed, not changed: an order submitted before its own symbol has any quote is risk-checked only at first fill, without held-position prices, so it is always refused once the book holds anything (`PORTFOLIO_VALUATION_UNAVAILABLE`). The runner never submits for an unquoted name, so it does not bite here |
| F5 corporate actions on held names | DONE, including the founder's 2026-09-24 choice | Detection: both books read every structural action NSE published for their names from the stored records (`data/held_corporate_actions.py`, moved from `execution/` so XS imports nothing from execution). The flagship exits 11 before trading; XS leaves the leg unvalued, the hand-kept authority taking precedence. Review: `scripts/apply_paper_corporate_action.py --book flagship|xs` is a dry run unless `--apply`. It checks the ratio against NSE's record (a contradiction is refused; a ratio NSE did not state is taken from the filing and noted), applies a split, consolidation or bonus keeping total cost (whole shares; a dropped fraction is stated), or records `--acknowledge "reason"`, and refuses a second review of the same action. Flagship: schema v7 `reviewed_actions` is written in the same hash-protected save as the holding, to all three copies, with compare-and-swap. XS: the review is stored on the leg, and `settle_positions` now carries it through open, closed and unresolved. The session report and JSON list reviewed actions on held names. Tests: `test_held_corporate_actions` 31, `test_paper_portfolio` 69 (v7), `test_apply_paper_corporate_action` 11 (one drives a real session from exit 11 to past the check), `test_xs_monthly_corporate_actions` 8. The XS replay was rerun with the NSE flags predicted: HEG is the only name flagged on real data, and ALL CHECKS PASSED. Still open: pricing a demerger's new shares once they list (HEG Graphite) |

## Decision rationale

Waiting until 6 Oct only bought one live run of XS's exit path, which can be exercised now by
replaying past data. Restarting after fixes gives clean books; it does not make them profitable,
because the same models still carry no edge (101 governed trials; flagship DSR 0.175990 against
0.95). So the restart is labelled a system test with an end date, per the 23 Sep decision's rule
for any paper book.

## Commands and outcomes

| Command | Result | Evidence/notes |
|---|---|---|
| `Get-CimInstance Win32_Process` filtered on the paper runners | none running | Checked before disabling |
| `Disable-ScheduledTask` for `QuantOS Mizan Paper Session`, `QuantOS Trigger Verification`, `QuantOS-XSMonthly-PaperWatch` | PASS | All three `Disabled`; the three supervisors were already `Disabled`; only `QuantOS-DailyAutoSync` (git, 23:00) remains `Ready` |
| Archive copy of both books | PASS | 86 files, 3,192,592 bytes, each copy SHA-256 verified; `reports/paper_books_20260923/archive-manifest.json`; committed `7c63df15` |
| `pytest tests/test_paper_report_baselines.py tests/test_paper_portfolio.py` | PASS | 78 passed |
| `pytest tests/test_paper_pilot_carried_session.py` (end-to-end runner) | PASS | 64 passed in 654 s |
| `pytest` on `test_research_paper_exemption`, `test_risk_governor_session_peaks`, `test_xs_monthly_paper_watch`, `test_macro_cache_guard`, `test_scheduled_paper_session`, `test_live_universe_robustness`, `test_corporate_actions`, `test_ingest_corporate_action_authority` | PASS | 107 + 107 passed |
| `ruff check .`; `ruff format --check .`; `mypy src launcher.py scripts` | PASS | 707 files formatted; mypy strict clean on 210 source files |
| Provider check, `NSE_INDEX\|Nifty 500` | PASS | HTTP 200, 15 daily closes 2026-09-01..09-22. Four guesses at an equal-weight NIFTY 500 key returned HTTP 400; not pursued further |
| `reports/paper_books_20260923/xs_exit_replay.py` | PASS | Case A (exit on the last cached day): 98/98 closed at the 09-18 open, cost 0.224% once, HEG unresolved, cash reconciles, no reopen. Case B: same, plus a 99-leg cohort reopened at the 09-18 open |
| `pytest tests/` (full suite, after F1/F3/F4) | PASS | 1632 passed in 755 s |
| `pytest tests/` (full suite, after F2/F5) | PASS | 1670 passed in 752 s; `ruff check .`, `ruff format --check .` (710 files) and `mypy src launcher.py scripts` (211 files) clean |
| `scripts/audit-agent-claims.ps1`; `scripts/audit-disk-layout.ps1 -Fast` | PASS | both exit 0 |
| `pytest tests/` (full suite, after the review tool and XS guard) | PASS | 1710 passed in 816 s, plus `test_an_adjusted_holding_still_replays_to_exact_cash` added after collection (70 portfolio tests pass); `ruff check .`, `ruff format --check .` and `mypy src launcher.py scripts` (212 files) clean; both audits exit 0 |

## Files changed

- To be listed at completion.

## Blockers and conflicts

- Every code path in F1-F5 is claimed by an older active record (Antigravity paper pilot, Hermes
  XS watch, and five Claude records). Edited on founder instruction with a NOTICE, per repository
  precedent (`20260829-claude-live-mizan-feature-provider.md`, founder override).
- `QuantOS-DailyAutoSync` pushes `main` at 23:00, so commits made here reach `origin` tonight.

## Stop point

Books stopped and archived. F1, F3 and F4 were committed separately; F2 and F5 in one commit, because
both edit the runner. All three paper-book tasks are `Disabled`. The full suite and repo-wide
ruff and strict mypy pass. The working tree is clean after the F2/F5 commit.

## Next safe action

When the founder says restart, run the decision's restart checklist:

1. Move the live state into `logs/archive/paper-books-20260923/` and verify it against the manifest.
2. Run `scripts/configure_paper_book_tasks.ps1 -Enable`.
3. Start both books fresh. The flagship needs `--force-new-portfolio` only if old session reports
   remain in `logs/paper_runs/`.

Nothing restarts without the founder's go-ahead.
