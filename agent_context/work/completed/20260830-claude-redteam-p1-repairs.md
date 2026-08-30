# Active work: repair the remaining P1 findings in the live paper path

STATUS: COMPLETED
OWNER: Claude Code
TOOL: Claude Code
STARTED_UTC: 2026-08-30T00:00:00Z
STARTING_REVISION: 2d5f6d31
WORKTREE_OR_BRANCH: D:\quant_system on main

## Objective

Repair the seven P1 findings left open by `.launch/reports/RED-TEAM-20260829-LIVE-PAPER-PATH.md`
after P1-1 was closed at `2d5f6d31`. In report order:

- P1-2 cross-session round trips report realized P&L inflated by the entry-side statutory cost
- P1-3 executed hold is 12 sessions against a measured 10, from two compounding off-by-ones
- P1-4 a rebalance session where no name clears the score floor liquidates the whole book
- P1-5 `per_name_alloc` is sized from a constant, not the persisted portfolio
- P1-6 the holiday guard runs on the holiday and blocks the trading day after it
- P1-7 `--skip-refresh` bypasses all three data guards and still trades and persists state
- P1-8 the total-drawdown kill switch resets every session

Plus the P2s that share a root cause: P2-3 (cumulative realized P&L overwritten), P2-6 (an
unmeasured score threshold), P2-9 (SUCCESS banner on a failed reconciliation).

## Non-goals

- Live-money routing. Unchanged and still excluded.
- The claim-1/2/6/8 documentation corrections. Separate, cheaper work.
- Re-running any campaign or spending a multiplicity ordinal.

## Owned paths

- src/quant_system/execution/paper_portfolio.py
- scripts/run_paper_pilot_session.py (founder-instructed override, see the notice from 2026-08-30)
- scripts/run_scheduled_paper_session.py
- tests/test_paper_portfolio.py
- tests/test_scheduled_paper_session.py (new)
- agent_context/work/active/20260830-claude-redteam-p1-repairs.md

## Blockers and conflicts

Same overlap as the previous task: `20260826-antigravity-paper-trade-live-market-testing.md` is
ACTIVE and claims `scripts/run_paper_pilot_session.py`. The notice raised at
`agent_context/work/active/20260830-NOTICE-paper-pilot-session-edited-under-antigravity-claim.md`
already records the override and is not duplicated here.

`PORTFOLIO_SCHEMA_VERSION` moves 1 -> 2. No migration is written because no state file has ever
been produced: `logs/paper_runs/portfolio_state.json` does not exist, and every artifact under
`logs/paper_runs/` predates the persistence commit `b3e626b5`.

## Current step

Implementing P1-2 and P2-3.

## Commands and outcomes

```
.venv/Scripts/python.exe -m ruff check .        -> All checks passed!
.venv/Scripts/python.exe -m ruff format .       -> 502 files formatted
.venv/Scripts/python.exe -m mypy src            -> Success: no issues found in 141 source files
.venv/Scripts/python.exe -m pytest -q           -> 1153 passed (was 1135)
scripts/run_paper_pilot_session.py --help       -> import chain clean
scripts/run_scheduled_paper_session.py --help   -> import chain clean, no --skip-refresh
```

Trading-day guard exercised directly against the real authority:

```
2026-08-29 Sat: refused - NSE does not trade at weekends
2026-08-31 Mon: TRADING
2026-10-02 Fri: refused - NSE trading holiday: Mahatma Gandhi Jayanti
2027-03-01 Mon: refused - authority covers ['2026'] and not 2027
```

## Repaired

| Finding | Repair |
|---|---|
| P1-2 | `PortfolioHolding.entry_fee` carried; the replay charges it; `ledger_funding` covers it so cash stays exact. A cross-session round trip now reports 9538.00, the same as the same-session one |
| P2-3 | `state_from_ledger` accumulates realized P&L; the parameter is renamed `session_realized_pnl` so the caller cannot pass the wrong thing silently |
| P1-3 | `rebalance_due` converts the card's horizon to the measured hold; the counter is `sessions_held`, set to 1 on the rebalance session. Executed hold is now 10, pinned by a simulation through the real functions |
| P1-4 | The invented score floor is gone -- the screen applies none. Liquidation is additionally gated on a non-empty selection, so "sell everything" is not reachable by the selection merely failing |
| P1-5 | Sizing base is `portfolio.ledger_funding()`, not the `initial_cash` constant |
| P1-6 | `require_trading_day` decides from `data/authorities/nse-trading-holidays.json`, fetched from the NSE public API. Fails closed on an absent calendar or an uncovered year |
| P1-7 | `--skip-refresh` removed rather than fixed; a rehearsal leaving identical artifacts is not a rehearsal |
| P1-8 | `peak_equity` persists and is monotonic; the governor is seeded with it |
| P2-6 | Score floor removed (same repair as P1-4) |
| P2-9 | The SUCCESS banner and exit 0 are conditional; the hardcoded "0.00 Paisa Discrepancy" prints the real figure |
| 5.2 | The entry loop is explicitly gated on `rebalancing` rather than relying on `top_picks` being empty |
| 5.4 | Exits are proposed before entries in the same step, so proceeds fund the entries |

## Still open

- 5.3 (P2) neither loop is idempotent across the ~25 steps in a session. Degrades to duplicate
  rejected orders rather than a short, because the ledger and the engine both refuse the oversell.
- 5.5 (P2) a crash mid-loop still advances the portfolio and resets the rebalance clock.
- The claim-1/2/6/8 documentation corrections, and P2-1, P2-2, P2-5, P2-7, P2-8, P2-10, P2-11.
- The scheduled task stays **disabled** until a fresh adjudication, not merely until these land.

## Files changed

- `src/quant_system/execution/paper_portfolio.py` (schema v2)
- `scripts/run_paper_pilot_session.py`, `scripts/run_scheduled_paper_session.py`
- `data/authorities/nse-trading-holidays.json` (new)
- `tests/test_paper_portfolio.py`, `tests/test_scheduled_paper_session.py` (new)

## Next safe action

Correct the overstated claims from Claims 1, 2, 6 and 8, none of which change behaviour, then
commission a fresh independent recheck. Do not re-enable the schedule before that recheck.
