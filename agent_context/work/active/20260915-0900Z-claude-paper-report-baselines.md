# Active work: baselines in the daily paper report

STATUS: ACTIVE  
OWNER: Claude Code (Opus 5)  
TOOL: Claude Code  
STARTED_UTC: 2026-09-15T09:00:00Z  
STARTING_REVISION: 692fb5c7627510f028dfeb5af06cbfb9d8318b80  
WORKTREE_OR_BRANCH: `D:\quant_system`, branches `main` and `claude/paper-report-baselines`
  (shared checkout). The branch was cut at `692fb5c7` on founder instruction to commit, and carries
  exactly one commit, `a85c4b8f`, which was then fast-forwarded into `main` on founder instruction
  to merge. **It is fully merged and holds nothing `main` does not.** It is mine and safe to delete;
  deletion is not done without being asked (PROTOCOL §8.3).

## Authorization

Founder instruction, 2026-09-15: "add the baselines to the daily paper report", following a
measurement in this session showing the flagship model's Sharpe (+0.167 on
`trial_mizan_h11_003`) losing to BUY_AND_HOLD (+1.404) and PREVIOUS_SIGN (+1.631) while its own
DSR rose across three trials. The daily report prints only the book's own P&L, so that comparison
is invisible between governed trials.

This authorization is what permits editing `scripts/run_paper_pilot_session.py`, which carries two
ACTIVE claims (see "Blockers and conflicts"). Without it the path is not mine to touch.

## Objective

Every daily paper session report states what the book returned **against the alternatives**, over
the book's own holding window, net of fees — so a book that is losing to doing nothing says so on
the day rather than at the next governed trial.

Reporting only. **No** change to what the book trades, to the model, to any risk limit, or to any
number the book acts on.

## Owned paths

- `agent_context/work/active/20260915-0900Z-claude-paper-report-baselines.md` (this file)
- `scripts/run_paper_pilot_session.py` (report writer and one new pure helper only)
- `tests/test_paper_report_baselines.py` (new)

## Non-goals

- **No edit to any file under `logs/`.** Saved history is not rewritten; the change takes effect
  on the next session that writes a report.
- No change to the dashboard (`src/quant_system/server/ui/live_dashboard.py`) — separate claim,
  separate surface. The baselines go into the session JSON so a later dashboard change can read
  them without re-deriving.
- No change to order generation, selection, sizing, the hold clock, or `rebalance_executed`.
- No retraining, no new trial, no multiplicity ordinal, no model promotion.
- No repository-wide formatter, generator, or `git add -A`.

## Baselines chosen, and why these

Computed over the holding window (earliest open lot → this session's close), all net-of-fee where
the book is, all from data already in memory at report time. No new I/O in the close path.

| Baseline | Answers | Source |
|---|---|---|
| This book | actual | `reconciliation` |
| Equal-weight the same names | did *sizing* help? | lot entry prices + close marks |
| NIFTY 50 buy-and-hold | did any of this beat the market? | cached `macro_NIFTY50` series |
| Cash | did trading beat not trading? | 0.00% by definition |

`book − NIFTY 50` is printed as the selection line, because that is the number Gate 1B turns on.

**PREVIOUS_SIGN and EQUITY_DUAL_MOMENTUM are deliberately excluded.** Both are per-instrument
signal rules that need a decision history this runner does not keep; inventing a portfolio
construction for them here would produce a number that does not correspond to the one
`modeling/validation.py` reports under the same name. A baseline that disagrees with the governed
one is worse than no baseline.

Any baseline whose inputs are missing prints `unavailable` with the reason. It is never defaulted
to zero, and never omitted silently — same rule as the unpriced-entitlement handling in
`20260914-claude-paper-book-accounting-repairs.md`.

## Plan

1. File this record. — DONE
2. File the PROTOCOL §3 notice naming the two claims crossed. — DONE
3. Pure helper `session_baselines(...)` beside `weight_drift_report`. — DONE
4. Section 4 in the Markdown report; `baselines` key in the session JSON. — DONE
5. Tests, ruff, mypy, `audit-agent-claims.ps1`, `audit-disk-layout.ps1`. — **DONE, all green**
6. Move to `completed/` and reconcile. — pending the first report written by this code.

## Current step

Step 5 complete; nothing staged and nothing committed. Holding at step 6 until the 2026-09-16
session writes the first report carrying the section, because a report nobody has read is not
evidence that it renders.

## Commands and outcomes

| Command | Result |
|---|---|
| `pytest tests/test_paper_report_baselines.py -q` | **9 passed** |
| `pytest tests/ -q -k "paper or pilot or portfolio or dashboard"` | **265 passed**, 1322 deselected, 8m44s |
| `ruff check` on both changed files | All checks passed |
| `ruff format --check` on both changed files | 2 files already formatted |
| `mypy src launcher.py scripts` | **Success, 210 source files** |
| `scripts/audit-agent-claims.ps1` | **PASS**, exit 0 |
| `scripts/audit-disk-layout.ps1` | **PASS**, exit 0 |

Rendered against the real flagship book (intraday marks, 2026-09-15 14:46 IST), window
2026-08-31..2026-09-11, to confirm the section produces meaningful output rather than only passing
its own tests:

| Baseline | Return % |
|---|---:|
| This book | -3.0905 |
| Equal-weight, same names | -3.0828 |
| NIFTY 50 buy-and-hold | -2.8334 |
| Cash | +0.0000 |
| **Selection vs NIFTY 50** | **-0.2571** |

The selection line is the point of the work: on this window the book's picking cost 0.26 percentage
points against simply holding the index, and weight drift accounts for less than a basis point of
the gap. Neither figure was visible anywhere in the daily report before this.

## Files changed

- `scripts/run_paper_pilot_session.py` (+213/-2): `session_baselines`, `_closest_on_or_before`,
  `_pct`; `baselines` key in the session JSON; new report section 2, old sections 2 and 3
  renumbered to 3 and 4.
- `tests/test_paper_report_baselines.py` (new, 9 cases).

## Concurrency hazard observed, and how it was handled

A live session was running throughout this work: PID 15780,
`scripts/run_scheduled_paper_session.py --universe-name NIFTY500`, started 11:49:23 IST, trading
loop through the 15:30 close. `run_scheduled_paper_session.py:306` spawns
`run_paper_pilot_session.py` as a **subprocess**, and that subprocess had already started and
compiled the module before this work began — so editing the file on disk cannot reach the running
process, and today's report is written by the old code.

This was checked rather than assumed, because `CURRENT.md` records a 25-minute run killed by
exactly this pattern on 2026-09-10. The new code first runs tomorrow, 2026-09-16 — which is the
session the hold clock says is the first rebalance (`sessions_held` 9 → 10, horizon 11), so the
first report carrying baselines is also the first report carrying fills.

## Blockers and conflicts

`scripts/run_paper_pilot_session.py` is claimed by two ACTIVE records:

- `20260826-antigravity-paper-trade-live-market-testing.md` (OWNER: Antigravity) — lists it in
  OWNED_PATHS.
- `20260914-claude-paper-book-accounting-repairs.md` (OWNER: Claude Code) — lists it in
  OWNED_PATHS; its "Current step" reads Complete but STATUS is still ACTIVE.

Neither record is edited by this work. A notice is filed instead
(`20260915-NOTICE-paper-report-baselines-under-two-claims.md`), per PROTOCOL §3 and §8.4.

**Nothing this change writes is pinned as evidence by either record.** It adds a report section and
a JSON key; it changes no test count, coverage figure, manifest hash, or any number the book acts
on.

## Next safe action

Finish step 5. If any gate fails, repair before moving the record.
