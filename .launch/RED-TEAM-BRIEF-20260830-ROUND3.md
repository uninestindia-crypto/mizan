# Red Team brief — round three: the repairs to the repairs (2026-08-30)

STATUS: OPEN
AUTHOR OF THE WORK UNDER TEST: Claude Code. **You did not write any of it.**

## Read this first: the pattern is the point

| Round | Report | Outcome |
|---|---|---|
| 1 | `.launch/reports/RED-TEAM-20260829-LIVE-PAPER-PATH.md` | 8 P1, 11 P2, 2 P3 — NOT READY |
| 2 | `.launch/reports/RED-TEAM-20260830-P1-REPAIRS.md` | Round-1 repairs held, **2 brand-new P1s created by them** — NOT READY |
| 3 | this brief | ? |

Round 2's two P1s did not exist before round 1's repairs. They were produced by two repairs
interacting: a carry-forward replay that bypassed the engine's fill log, and an honest exit code
that turned the resulting silent failure into a hard one. **Assume round 3 has the same shape.**
Your highest-value target is a defect that exists only because of `86d1769c`.

## Commit in scope

`86d1769c` — `PaperPilotEngine.carry_in_positions`, the reconciliation baseline, persisted
`risk_halted`, and `session_peak_equity` from marked equity. `PORTFOLIO_SCHEMA_VERSION` 2 -> 3.

Prior commits (`2d5f6d31`, `bb62bc58`, `c45ee6f8`) are in scope only for **regression**: did
`86d1769c` break anything round 2 proved correct?

## Known-open, do not spend time rediscovering

Recorded and deliberately not yet repaired. Confirm they are still true if cheap; do not
investigate deeply:

- The three false commit-message claims in round 2's section 12.1 (exits-before-entries is a no-op;
  P2-6 half repaired; sizing a no-op under unrealized loss). **Still uncorrected in the record.**
- Round 2's remaining 14 P2 / 7 P3.
- Claim 8 residual 3: the drawdown is evaluated only inside `evaluate_order`, so a hold session
  proposing no orders never tests it.
- `end_session` raises `LedgerInvariantViolation` when a held position has no closing price, so a
  carried name leaving the universe crashes the session. Recorded by the author, not repaired.

## Claims to adjudicate — PROVEN / DISPROVEN / NOT TESTED

Write the skeleton with every claim `NOT TESTED` as your **first** action, then rewrite each
section the moment you finish it. Two earlier runs of this task hit API limits; the one that
batched its writes produced nothing, the one that wrote incrementally survived intact.

1. **`carry_in_positions` is correct and complete.** Attack the baseline: carry a name, sell it all,
   sell more than carried, carry twice, carry a symbol also traded today, carry zero names, carry
   the same symbol in two fills. Does the reconciliation stay exact in every case?

2. **Keeping carried fills out of `_fills` did not break something else that reads `_fills`.**
   Enumerate every consumer — fees, trade counts, slippage, cost breakdowns, the audit log, the
   status file, the markdown report. Is any of them now wrong or misleading for a carried session?

3. **The `INITIALIZED` guard.** `carry_in_positions` refuses once the session is open. Is that the
   right boundary? Can the baseline be moved by any other route — a second `start_session`, a halt
   and resume, a re-used engine?

4. **The persisted halt is genuinely sticky, and refusing to trade is safe.** Exit 8 fires before
   the engine exists. Does anything the session would have done — persisting state, writing a
   report, advancing `sessions_held` — get skipped in a way that loses information or corrupts the
   file? Can a halt be cleared accidentally?

5. **`session_peak_equity = max(governor peak, reconciliation.total_equity)`.** Is
   `reconciliation.total_equity` the right quantity — does it include unrealized marks, and is it
   computable on every session? What happens when it cannot be computed?

6. **Schema v3.** The author says no migration is needed because no state file has ever been
   written. Verify that. Then check the load path: is a v2 file refused cleanly, and are the three
   new fields required or optional in a way that could silently default?

7. **The new tests can actually fail.** `tests/test_paper_pilot_carried_session.py`. Revert each
   repair mentally and confirm the corresponding test breaks. Any test that passes against the
   broken code is worthless.

8. **Regression against round 2's proven results.** Re-verify the money claims round 2 proved:
   carry-forward P&L nets both legs, no double count, hold is exactly 10, cash exact. Did
   `86d1769c` disturb any of them?

9. **Anything `86d1769c` introduced, overstated, or broke.** The open-ended one, and on this
   evidence the most likely to pay. Round 2 found the author's commit messages contained three
   false claims; check this one's against what the code does.

## Rules

- Cite file:line and paste raw command output. An assertion without evidence is NOT TESTED.
- Do not repair anything. Report.
- Rank P1 Critical / P2 Major / P3 Minor.
- If a round-2 finding was wrong, say so. It is evidence, not scripture.
- Write to `.launch/reports/RED-TEAM-20260830-ROUND3.md`.
