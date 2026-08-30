# Active work: repair the two P1 findings from the recheck

STATUS: COMPLETED
OWNER: Claude Code
TOOL: Claude Code
STARTED_UTC: 2026-08-30T00:00:00Z
STARTING_REVISION: fbedfdd2
WORKTREE_OR_BRANCH: D:\quant_system on main

## Objective

Close the two P1 findings in `.launch/reports/RED-TEAM-20260830-P1-REPAIRS.md`, both of which came
from my own repairs interacting rather than from any single one:

- **P1-A** Every carried session fails reconciliation and now exits 7. The carry replay calls
  `ledger.process_fill` directly, bypassing `PaperPilotEngine._fills`, so `end_session` check (b)
  compares ledger positions against net fills and mismatches on every carried holding. Check (a)
  is unaffected: it reads `ledger.transactions`, which does include the carry fills.
- **P1-B** The total-drawdown kill switch is not persisted. A breach halts one session and is
  forgotten the next morning, while the same session's refused exits retain the losing book and
  `sessions_held` resets to 1.

Also closing Claim 8 residual 2 (P2), because leaving it makes the P1-B repair hollow: the peak is
seeded from `ledger_funding()`, a **cost** figure, and `update_peaks` is reachable only from
`evaluate_order`, so a hold session never marks. A book that rose 25% and fell 20% showed no
drawdown at all.

## Non-goals

- The remaining 14 P2s and 7 P3s, including the three false commit-message claims. Those are
  corrections to record, not repairs, and belong in separate work.
- Re-enabling the scheduled task. It stays disabled.
- Live-money routing. Unchanged and still excluded.

## Owned paths

- src/quant_system/execution/paper_pilot.py (see the notice below)
- src/quant_system/execution/paper_portfolio.py
- scripts/run_paper_pilot_session.py (founder-instructed override, notice already raised)
- tests/test_paper_pilot_carried_session.py (new)
- tests/test_paper_portfolio.py
- agent_context/work/active/20260830-claude-recheck-p1-repairs.md

## Blockers and conflicts

`20260826-antigravity-paper-trade-live-market-testing.md` is ACTIVE and claims **both**
`scripts/run_paper_pilot_session.py` and `src/quant_system/execution/paper_pilot.py`. The existing
notice covers only the script; a second notice at
`agent_context/work/active/20260830-NOTICE-paper-pilot-engine-edited-under-antigravity-claim.md`
covers the engine.

`PORTFOLIO_SCHEMA_VERSION` moves 2 -> 3. Still no migration: no state file has ever been written.

## Current step

Implementing.

## Commands and outcomes

```
ruff check . / ruff format .   -> clean, 510 files
mypy src                       -> Success, 141 source files
pytest -q                      -> 1166 passed (was 1157)
```

Both P1s reproduced on the old path and closed on the new one, in one run:

```
OLD (ledger.process_fill direct): reconciled=False
    POSITION_MISMATCH for ACME: Ledger 100 != Carried 0 + Net Fills 0
    POSITION_MISMATCH for BETA: Ledger 500 != Carried 0 + Net Fills 0
NEW (engine.carry_in_positions): reconciled=True
```

## Repaired

| Finding | Repair |
|---|---|
| P1-A | `PaperPilotEngine.carry_in_positions` seeds the ledger *and* records the opening quantity. `end_session` check (b) reconciles against `carried + net fills today`, and a carried name the ledger no longer holds is checked for being sold to exactly flat. Carried fills stay out of `_fills`, so today's fee total and trade count are not inflated by costs paid earlier |
| P1-B | `risk_halted` / `halted_on` / `halt_reason` persist in the portfolio, sticky, cleared only by a human. The runner refuses to trade when halted and exits 8 |
| Claim 8 residual 2 (P2) | `session_peak_equity` is now `max(governor peak, reconciliation.total_equity)`, so a hold session's marked equity enters the high-water mark instead of a cost figure |

## Design notes

Two options were rejected for P1-A. Recording the carry fills in `_fills` would reconcile, and would
report positions opened weeks ago as today's trades — inflating `total_fees_paid`,
`total_trades_count` and `total_fills_count`. Reconciling only when flat would delete the invariant
on exactly the sessions that need it.

For P1-B, auto-clearing was rejected because a switch that resets itself is not a switch, and
auto-liquidating was rejected because going to cash is a rule nobody measured — the same reasoning
that removed the score floor. Refusing to trade and requiring a human is the honest middle.

## Observed, not repaired

`end_session` raises `LedgerInvariantViolation` when a held position has no closing price, refusing
to substitute an average price. Correct behaviour, but it means a carried name that leaves the
universe — index reconstitution, a suspension — would crash the session rather than report. Worth a
finding of its own; not repaired here because inventing a mark is exactly what the ledger refuses.

Claim 8 residual 3 (P2) is **not** closed: the drawdown is still evaluated only inside
`evaluate_order`, so a hold session with no orders never tests it. `update_peaks` raises the peak
and does not check the breach. Closing it needs an equity-mark evaluation path on the governor.

## Still open

The remaining 14 P2s and 7 P3s, including the three false commit-message claims recorded in
`.launch/reports/RED-TEAM-20260830-P1-REPAIRS.md` section 12.1. The scheduled task stays disabled.

## Next safe action

Correct the three false claims in the record, then commission a third recheck. Do not re-enable the
schedule before that recheck.
