# Active work: repair the three P1 findings from round three

STATUS: COMPLETED
OWNER: Claude Code
TOOL: Claude Code
STARTED_UTC: 2026-08-30T00:00:00Z
STARTING_REVISION: bd996541
WORKTREE_OR_BRANCH: D:\quant_system on main

## Objective

Close the three P1s in `.launch/reports/RED-TEAM-20260830-ROUND3.md`. The founder needs the paper
session to run at Monday's open, so these are on the critical path.

- **P1-A (root)** The 4% *daily* drawdown limit is measured against the **all-time** peak, because
  `PreTradeRiskGovernor.__init__` seeds `_daily_peak_equity` and `_all_time_peak_equity` from the
  same `initial_equity`, `reset_session_peak` has zero callers repo-wide, and `bb62bc58` began
  passing the persisted all-time peak. `TOTAL_MAX_DRAWDOWN_BREACHED` is unreachable: at 5%, 10%,
  14% and 20% below peak the reason is always the daily one. A session that opened flat and moved
  0% intraday halts the pilot.
- **P1-B** The halt recovery documented at `run_paper_pilot_session.py:786-792` is impossible: the
  state file is hash-protected, so the hand-edit it instructs is refused. The only working route is
  deleting the file, which silently invents a fresh portfolio.
- **P1-C** Ratcheting `peak_equity` on marked close equity makes the halt near-certain — 3995/4000
  paths within 250 sessions, median 30. This is a **consequence of P1-A**: once the daily limit
  measures from the session open, a rising all-time peak governs only the 12% total check, which is
  the intended semantics.

Also closing two P2s about my own tests, because the recheck found the same class twice:
`test_the_peak_records_marked_equity_not_only_cost` passes verbatim against the parent commit, and
forcing `reconciled=True` unconditionally leaves all 1166 tests passing.

## Non-goals

- The remaining P2s and P3s from all three rounds.
- The `QuantOS-DailyAutoSync` process problem (it committed a half-written report as `bd996541`).
  Real, and separate from the code.
- Live-money routing. Unchanged and still excluded.

## Owned paths

- src/quant_system/risk/governor.py (unclaimed by any active record; verified before editing)
- scripts/run_paper_pilot_session.py (founder-instructed override, notices already raised)
- scripts/clear_paper_halt.py (new)
- tests/test_risk_governor_session_peaks.py (new)
- tests/test_paper_pilot_carried_session.py
- agent_context/work/active/20260830-claude-round3-p1-repairs.md

## Decision rationale

`reset_session_peak` exists and is correct; it simply has no caller. Rather than add a caller inside
the engine — which would fix the daily peak but leave `__init__` still conflating the two — the
constructor gains an explicit `all_time_peak_equity`. The two peaks then mean what their names say
at every point in the lifecycle, which is the property whose absence produced this defect.

## Current step

Implementing.

## Commands and outcomes

```
ruff check . / ruff format .  -> clean, 516 files
mypy src                      -> Success, 141 source files
pytest -q                     -> 1173 passed (was 1166)
```

Round three's own experiment, re-run against both seedings:

```
OLD (both peaks = all-time)    halted 4000/4000 | median session  18 | {'DAILY_DRAWDOWN_LIMIT_BREACHED': 4000}
NEW (daily = session open)     halted 3032/4000 | median session 106 | {'TOTAL_MAX_DRAWDOWN_BREACHED': 3032}
```

The daily rule no longer fires on a multi-session decline, and the total rule -- previously
unreachable -- is the one that governs. `clear_paper_halt.py` exercised end to end on a halted
portfolio: halt cleared, holdings/realized P&L/peak/session count all unchanged.

## Repaired

| Finding | Repair |
|---|---|
| P1-A | `PreTradeRiskGovernor.__init__` takes `all_time_peak_equity` separately. The runner passes today's opening equity as `initial_equity` and the carried high-water mark as the trailing peak, so the 4% rule measures intraday and the 12% rule measures multi-session |
| P1-B | `scripts/clear_paper_halt.py`: prints the halt and the book, requires `--i-have-reviewed-the-book`, rewrites with a valid hash, then reloads to prove the write is readable and the book unchanged. The runner's message points at it and warns against hand-editing or deleting |
| P1-C | Follows from P1-A. A rising peak now governs only the 12% total check, which is its intended meaning |
| P2 (worthless test) | `test_the_peak_records_marked_equity_not_only_cost` replaced with an AST detector on the runner's actual call; the old one asserted `max()` behaves like `max()` and passed against the parent commit |
| P2 (unguarded verdict) | `test_reconciliation_can_actually_report_failure` drives a genuine mismatch, so stubbing `reconciled=True` no longer leaves the suite green |

## Residual risk, stated plainly

Under the corrected rule the 12% total switch still trips on 3032 of 4000 simulated paths within 250
sessions. That is **not** a defect: a 12% trailing drawdown on a model whose measured Sharpe is
negative is the switch doing its job. It does mean the pilot should be expected to halt eventually,
and the halt is now recoverable rather than terminal.

Not closed: the drawdown is still evaluated only inside `evaluate_order`, so a hold session
proposing no orders never tests it. `reset_session_peak` still has no caller -- the constructor now
does its work, and the method is left rather than removed because it is the right hook for an
intraday reset if one is ever needed.

## Still open

Round three's 5 P2 / 8 P3, the earlier rounds' P2s, the three false commit-message claims, and the
`QuantOS-DailyAutoSync` process problem: it committed a half-written adjudication as `bd996541`.

## Next safe action

None of this has been independently adjudicated. A fourth recheck is the correct next step; the
founder's decision to run at Monday's open is separate and informed.
