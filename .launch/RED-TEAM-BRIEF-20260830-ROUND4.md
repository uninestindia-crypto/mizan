# Red Team brief — round four: the risk-governor repairs (2026-08-30)

STATUS: OPEN
AUTHOR OF THE WORK UNDER TEST: Claude Code. **You did not write any of it.**

## This one executes tomorrow morning

The scheduled task `QuantOS Mizan Paper Session` is **enabled** and fires **Monday 31 Aug 2026 at
09:00 IST**, running the code you are adjudicating. Triage accordingly: a defect that produces a
wrong or fabricated session *tomorrow* outranks anything structural.

No live money is at risk — nothing in this repository has ever placed an order, and the paper
surface cannot. What is at risk is the integrity of the record the session writes, and the
portfolio state it persists for every session after it.

## The pattern, three rounds deep

| Round | Report | Outcome |
|---|---|---|
| 1 | `RED-TEAM-20260829-LIVE-PAPER-PATH.md` | 8 P1 |
| 2 | `RED-TEAM-20260830-P1-REPAIRS.md` | round-1 repairs held; **2 new P1s created by them** |
| 3 | `RED-TEAM-20260830-ROUND3.md` | round-2 repairs held; **3 new P1s created by them** |
| 4 | this brief | ? |

Every round, the repairs closed what they aimed at and created something new by composing with code
they did not touch. **Assume that again.** A defect that exists only because of `46c7bb67` is worth
more than a fresh sweep.

## Commit in scope

`46c7bb67` — `PreTradeRiskGovernor.__init__` gains `all_time_peak_equity`; the runner passes today's
opening equity as `initial_equity`; `scripts/clear_paper_halt.py`; two replaced tests.

Earlier commits are in scope only for **regression**.

## Known-open, do not spend time rediscovering

- Round 3's 5 P2 / 8 P3 and the earlier rounds' P2s.
- The three false commit-message claims in round 2 section 12.1. **Still uncorrected.**
- The drawdown is evaluated only inside `evaluate_order`, so a hold session with no orders never
  tests it. `reset_session_peak` still has no caller.
- `QuantOS-DailyAutoSync` runs `git add -A` and committed a half-written adjudication as
  `bd996541`.
- The 12% total switch is expected to trip eventually (3032/4000 paths in the author's simulation).
  That is the switch working. Only report it if the *frequency or reason* is wrong.

## Claims to adjudicate — PROVEN / DISPROVEN / NOT TESTED

Write the skeleton with every claim `NOT TESTED` as your **first** action, then rewrite each section
the moment you finish it. Three earlier runs hit API limits; the two that wrote incrementally
survived, the one that batched produced nothing.

1. **The governor change is safe for every other caller.** `PreTradeRiskGovernor` is a shared risk
   contract. Find every construction site in `src/`, `scripts/`, `tests/` and the server. Does the
   new parameter change behaviour for any of them? Is the `max(init_eq, all_time_peak_equity)` floor
   right, or does it mask a caller that wanted a lower trailing peak?

2. **The daily limit now measures the day.** Verify independently — do not trust the author's
   simulation. Confirm the daily rule fires on a genuine intraday decline and does not fire on a
   multi-session one, and that `TOTAL_MAX_DRAWDOWN_BREACHED` is reachable at the right depth.

3. **`clear_paper_halt.py` cannot lose or corrupt the book.** Attack it: a halted portfolio with
   holdings, a corrupt file, a missing file, a file that becomes unreadable mid-run, concurrent use
   with a running session, a portfolio that is not halted. Can it ever write a state the session
   then refuses, or silently drop a holding?

4. **The two replaced tests are worth something.** The AST detector on `session_peak_equity` and
   `test_reconciliation_can_actually_report_failure`. Revert each repair and confirm they fail. An
   AST detector that matches too loosely is worse than none.

5. **Tomorrow's session completes correctly.** Walk the whole path the scheduled task will take at
   09:00 with the real state on disk: no `portfolio_state.json` exists yet, so this is a first run.
   Does it reconcile, persist a v3 file, and report honestly? What is the first thing that goes
   wrong, and on which session?

6. **The first-run and second-run boundary.** Session 1 writes state; session 2 reads it. Is
   anything wrong across that boundary — the peak, the halt, the hold clock, the entry fees?

7. **Regression against rounds 2 and 3.** Re-verify what they proved: carry-forward P&L nets both
   legs, cash exact, hold exactly 10, both round-2 P1s still closed, the `INITIALIZED` guard, v2
   files refused.

8. **Anything `46c7bb67` introduced, overstated, or broke.** Check its commit message against what
   the code does — round 2 found three false claims in the author's messages, and round 3 found the
   message reasoned about the wrong switch throughout.

## Rules

- Cite file:line and paste raw command output. An assertion without evidence is NOT TESTED.
- Do not repair anything. Report.
- Rank P1 Critical / P2 Major / P3 Minor.
- If an earlier round's finding was wrong, say so. They are evidence, not scripture.
- Do not modify anything under `data/evidence/` or `logs/paper_runs/`.
- Write to `.launch/reports/RED-TEAM-20260830-ROUND4.md`.
