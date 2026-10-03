# Active work: BacktestEngine must mark held positions for the risk governor

STATUS: ACTIVE  
OWNER: Claude Code session (founder instruction 2026-09-28: repair the engine's governor call so a
second concurrent position is not refused)  
TOOL: Claude Code  
STARTED_UTC: 2026-09-29T04:31:05Z  
STARTING_REVISION: `e787ac462fe9c9d188ab8974109c3bdbd59b46b2` (main)  
WORKTREE_OR_BRANCH: `D:\quant_system\.claude\worktrees\magical-taussig-9dceb1` on branch `claude/magical-taussig-9dceb1` (from main `e787ac462`)

Workspace note: the Claude desktop app created this worktree at session start, before this record
could exist, and placed it under the install root's `.claude\worktrees\`, not under
`quant_system_workspaces\worktrees\`. It was not made with `new-workspace-clone.ps1`. It will not be
moved while this session works in it.

Claim-visibility note: PROTOCOL 8.1 makes the install-root copy of this record authoritative. At
first the desktop app's worktree hook refused a write to
`D:\quant_system\agent_context\work\active\` from this session ("Edits there do not land on this
session's branch and may corrupt the user's primary working copy"), so this record was written in
the worktree only. On founder instruction in chat (2026-09-29, "copy the record and notices to the
install root"), this record and both notices were then copied to the install root as three new,
additive files by a plain file copy, at 2026-09-29T09:59Z or later. Nothing else in the install root
was touched or staged. The two copies are byte-identical at copy time. After that, the install-root
copy is the authoritative claim and this one travels with the branch.

## Objective

`BacktestEngine.run()` passes the risk governor a quote for the ordered symbol only. With another
symbol already held, the governor fails closed with `PORTFOLIO_VALUATION_UNAVAILABLE`, so every
BUY placed while another position is open is refused. Make the engine supply marks for held symbols
(the current bar closes) through the governor's existing `current_prices` parameter, without
weakening the fail-closed check. Add a regression test that holds two positions at once. Measure
every caller before and after the change, and record any result that moves.

## Owned paths

- `src/quant_system/backtest/engine.py` (no active record claims it by path; checked 2026-09-29)
- `tests/test_backtest_engine_concurrent_positions.py` (new)
- `agent_context/work/active/20260929-0431Z-claude-backtest-engine-held-position-marks.md` (this)
- `agent_context/work/active/20260929-NOTICE-backtest-engine-held-marks-*.md` (new notices, if needed)

## Non-goals

- **No edit to `src/quant_system/risk/governor.py`.** It is owned by
  `20260822-claude-money-paths-remainder.md` (IN_PROGRESS, awaiting adjudication), and
  `20260903-hermes-xs-monthly-screen-new.md` and `20260925-1510Z-orchestrator-xs-portfolio-alpha.md`
  list it as do-not-touch. Its R-3 repair already accepts `current_prices`, so the fix belongs in
  the engine.
- No edit to `tests/test_backtest_engine.py` (owned by `20260821-claude-loop-in-test-legacy.md`).
- No edit to callers: `server/app.py`, `server/supervisor.py`, `analytics/optimizer.py`,
  `scripts/daily_pipeline.py`, `examples/*.py`. They are measured, not changed.
- No edit to the retail-redesign worktree or branch (`claude/retail-redesign`).
- No merge to `main`, no commit, and no push without founder instruction.
- No change to the engine's other behaviour: order sizing, the unchecked SELL path, the fill-time
  cash rejection, and the snapshot's cost fallback all stay as they are. Adjacent defects found
  along the way are recorded here, not repaired.

## Plan

1. Startup sequence, claim check, this record. DONE (worktree copy; install-root copy pending).
2. Reproduce the defect at `e787ac462` and capture baseline numbers for every caller. DONE.
3. Repair `engine.py` so held symbols are marked at the current bar close. Omit any held symbol that
   has no bar at `t`, so the governor still refuses rather than valuing it at cost. DONE.
4. Write the regression tests: two concurrent positions; a top-up while another position is held;
   the fail-closed refusal when a held symbol has no bar at `t`. Prove each one binds. DONE.
5. Re-measure every caller and record every result that changes. DONE (table below).
6. Full suite in both orders, ruff, ruff format, mypy, and both audits. IN PROGRESS.
7. File notices for records whose pinned numbers or comments this change invalidates. DONE
   (worktree copies; install-root copies pending with this record).

## Current step

Step 6.

## Decision rationale

Established so far:

- `PreTradeRiskGovernor.evaluate_order` (`risk/governor.py:185-425`) values held positions in its
  leverage check (step 9, `:360-392`). The traded symbol is valued from its own quote. Every other
  held symbol must come from the optional `current_prices` mapping. If any is missing, a non-SELL
  order is refused with `PORTFOLIO_VALUATION_UNAVAILABLE`. That is the R-3 repair, recorded in
  `20260823-NOTICE-money-paths-remainder-repaired.md`.
- `BacktestEngine.run` (`backtest/engine.py:196-202`) never passes `current_prices`.
- The engine's own snapshot (`engine.py:136-140`) falls back to `pos.average_price` for a held
  symbol with no bar at `t`. Passing those snapshot marks to the governor would bring R-3 back
  (valuing at cost) and weaken the fail-closed check. The marks must therefore come from
  `current_bars` only.

Repair (`engine.py`, one map and one keyword argument): after the strategy's signals, the engine
builds `held_marks = {sym: current_bars[sym].close for sym in positions if sym in current_bars}` and
passes it as `current_prices`. `ledger.positions` returns a copy, and fills happen only at the start
of a bar, so the map is valid for every order in the bar. The governor, its checks and its limits are
unchanged. The traded symbol is still valued from its own quote, which the governor already
prefers over a supplied mark.

Rejected alternatives:

- Mark a held symbol with no bar at `t` at its last observed close. That is a real, point-in-time
  price, but it is stale and a policy choice. It would loosen a check the founder asked to keep
  fail-closed. With this repair, a BUY on a day when any held symbol has no bar is still refused.
  Every synthetic caller has aligned calendars, so no measured result depends on this. It only
  matters for real data with suspensions or listing gaps.
- Pass the snapshot's marks. Killed by mutation; see below.
- Edit the governor. Not needed, and the governor is owned by another record.

## Evidence

Reproduction at `e787ac462` (scratch script, worktree code confirmed by `quant_system.__file__`):
two flat symbols, BUY AAA (0.1) at bar 5, BUY BBB (0.1) at bar 10. Fills: AAA only. The BBB decision
was `PORTFOLIO_VALUATION_UNAVAILABLE: no market price supplied for held position(s) AAA; leverage
cannot be determined`, with `current_prices` empty.

Regression tests, `tests/test_backtest_engine_concurrent_positions.py`, proved in scratch copies of
the tree (pytest's `pythonpath = ["src", "."]` rules out PYTHONPATH swaps):

| Engine | second symbol | top-up while another held | held symbol with no bar still blocks |
|---|---|---|---|
| `e787ac462` (defect) | **FAIL** | **FAIL** | pass |
| naive mutant: snapshot marks with cost fallback | pass | pass | **FAIL** (`'AAA' not in {'AAA': Decimal('106.05')}`) |
| this repair | pass | pass | pass |

The third test is the fail-closed guard. It passes on the defect because the defect never supplied
a price, and it is what kills the naive fix.

## Results that change (every caller, before = `e787ac462`, after = this repair)

Measured by one harness that wraps `BacktestEngine.run` and the governor at class level for
observation only, and calls each caller's own function. All callers use `SyntheticDataGenerator`
with fixed seeds, so every difference is the repair. `PORTFOLIO_VALUATION_UNAVAILABLE` refusals
fall to **0** in every run after the repair.

| Caller (strategy) | Trades | Final equity | Return | Sharpe | Max DD | Valuation refusals |
|---|---|---|---|---|---|---|
| `/api/v1/backtest/run` UI default, and `supervisor._run_backtest_task` default (EquityDualMomentum, 5 symbols, 120 d) | **6 -> 13** | 963,915.37 -> 958,339.56 | -3.6085% -> -4.1660% | -4.2139 -> -4.4113 | 3.8224% -> 4.3788% | 22 -> 0 |
| route, MLEquityStrategy | 11 -> 18 | 1,007,721.60 -> 996,742.94 | **+0.7722% -> -0.3257%** | -2.3796 -> -2.9494 | 1.2270% -> 1.8212% | 9 -> 0 |
| route, MizanStrategy | 9 -> 18 | 948,017.17 -> 945,846.20 | -5.1983% -> -5.4154% | -4.6621 -> -4.1278 | 5.7516% -> 5.9677% | 22 -> 0 |
| route, DirectionalVerticalSpreads / IntradayATMStraddle | 0 -> 0 | unchanged | | | | 0 -> 0 |
| `scripts/daily_pipeline.py`, ML run | 4 -> 7 | 932,667.02 -> 932,083.85 | -6.7333% -> -6.7916% | -4.5477 -> -4.5344 | 6.7333% -> 6.7916% | 3 -> 0 |
| `scripts/daily_pipeline.py`, momentum run | 0 -> 0 | unchanged (governor already latched, see below) | | | | 0 -> 0 |
| `examples/run_equity_backtest.py` | 4 -> 9 | 959,786.97 -> 959,357.03 | -4.0213% -> -4.0643% | -2.7848 -> -2.7413 | 4.0213% -> 4.0643% | 17 -> 0 |
| `examples/run_ml_equity_backtest.py` | 14 -> 30 | 999,740.30 -> 978,177.88 | -0.0260% -> -2.1822% | -1.1382 -> -1.2239 | 5.1486% -> 6.6120% | 49 -> 0 |
| `StrategyGridOptimizer`, EquityDualMomentum `top_n=1` | 12 -> 16 | 966,846.18 -> 964,941.69 | -3.3154% -> -3.5058% | -6.0058 -> -6.1497 | 3.3817% -> 3.5722% | 3 -> 0 |
| same, `top_n=2` | 8 -> 12 | 954,473.01 -> 956,676.86 | -4.5527% -> -4.3323% | -5.1395 -> -4.9758 | 4.5527% -> 4.3323% | 10 -> 0 |
| same, `top_n=3` | same as the route default row | | | | | |

The grid's Sharpe ranking is unchanged (`top_n` 3 > 2 > 1). Even `top_n=1` was affected. A rotation
emits the exit of the old name and the BUY of the new one on the same bar. The BUY was judged while
the old name was still held, so it was refused, and entry slipped to a later bar.

The maximum number of concurrent positions did not change in any run (3 for the route default),
because several BUYs on one bar while flat were always approved. What changed is every top-up,
rotation and re-entry placed while something else was held.

Not measured, deliberately: `examples/run_upstox_and_ai_pipeline.py` and the route with
`AIEnhancedMLEquity`. Their default advisory panel is `ClaudeCLIAdvisor`, which calls an external
model under the founder's account for each decision. The example also fetches from Upstox when a
token is present, and its results are not deterministic. Both use the same engine path, so they are
affected in the same way.

No persisted report cites these synthetic numbers except the one pinned below (Blockers).
`logs/daily_runs/` is gitignored runtime output and was not rewritten.

## Observed, not repaired (out of scope; filed as separate task suggestions)

1. **The engine never calls `reset_session_peak`.** In a backtest, `max_daily_drawdown_pct`
   (0.03 by default) acts as a whole-run trailing drawdown that latches the kill switch. Of the 11
   order-placing runs above, 9 trip it themselves, before and after this repair, and log 51-356
   `KILL_SWITCH_ACTIVE` refusals. One more (daily_pipeline momentum) inherits a tripped switch. Only
   route/MLEquityStrategy never latches. This caps how much of the repair's effect any result shows.
2. **`scripts/daily_pipeline.py` shares one governor between its two backtests.** The ML run trips
   the kill switch, so the momentum baseline is refused on every order (276 `KILL_SWITCH_ACTIVE`,
   0 trades). Its published momentum figures are artifacts.
3. The engine's snapshot still marks a held symbol with no bar at `t` at average cost, the same
   pattern the ledger's L-2 repair removed. It affects equity curves only on data with gaps; no
   synthetic caller has gaps.
4. Same-bar BUYs are each judged against the same pre-order cash and positions. A fill that cash
   cannot cover is dropped silently by `except ValueError: pass` (`engine.py:121-123`).

## Commands and outcomes

| Command | Result | Evidence/notes |
|---|---|---|
| `git status --short --branch`, `git worktree list`, `git branch --list` | PASS | 6 worktrees, 14 local branches; install root has other agents' uncommitted records, untouched |
| grep active records for `backtest/engine.py`, `risk/governor.py` | PASS | governor.py owned by `20260822-claude-money-paths-remainder.md`; engine.py unclaimed by path |
| Write this record to the install root | REFUSED by desktop-app worktree hook | worktree copy written instead; guard not bypassed |
| scratch `repro_second_position.py` at `e787ac462` | DEFECT REPRODUCED | AAA filled; BBB refused `PORTFOLIO_VALUATION_UNAVAILABLE` |
| scratch `measure_callers.py before` / `after` | PASS | 13 engine runs each; table above |
| `pytest tests/test_backtest_engine_concurrent_positions.py` | 3 passed | worktree, with the repair |
| same 3 tests in scratch copies: `e787ac462` / naive mutant / repair | 2 fail / 1 fails / 0 fail | each test binds |
| redesign parity test, snapshot in scratch, both engines | 1 passed each | their worktree untouched |
| `ruff check .` | PASS | All checks passed |
| `ruff format --check .` | PASS | 766 files already formatted |
| `mypy src launcher.py scripts` (strict) | PASS | Success: no issues found in 218 source files |
| `MYPYPATH=src mypy tests/test_backtest_engine_concurrent_positions.py` (strict) | PASS | 1 source file |
| `node scripts/check-tests.mjs tests/test_backtest_engine_concurrent_positions.py` | PASS | test-craft clean |
| `audit-disk-layout.ps1` (install-root copy) | PASS | lists both `.claude\worktrees\*` worktrees as STRAY, informational |
| `audit-agent-claims.ps1` (install-root copy), before the copy | FAIL, 3 findings | this worktree and branch unclaimed, because this record could not be written there; `claude/retail-redesign` unclaimed |
| copy record + 2 notices to install root, founder instruction | PASS | `cp -n` after confirming none of the 3 names existed; SHA-256 identical; `git diff --cached` empty; no other install-root file touched |
| `audit-agent-claims.ps1`, after the copy | FAIL, 1 finding (not mine) | worktree claim resolves. Branch claim first missed because the audit reads only the first line of `WORKTREE_OR_BRANCH:` and mine wrapped onto a second; fixed to one line and re-synced. Remaining: `claude/retail-redesign` unclaimed, and that record's `WORKTREE_OR_BRANCH:` line wraps the same way. Their record, not edited |
| `pytest tests/` forward, first attempt | NOT COMPLETED | process ended when the session paused at about 53%; every result before that passed |

## Files changed

- `src/quant_system/backtest/engine.py`: `held_marks` passed to the governor as `current_prices`
- `tests/test_backtest_engine_concurrent_positions.py` (new): 3 regression tests
- this record, `20260929-NOTICE-backtest-engine-held-marks-changes-journey-backtest-count.md`,
  `20260929-NOTICE-backtest-engine-held-marks-for-governor-and-lab-owners.md` (worktree copies)

## Blockers and conflicts

- **Claim visibility.** Resolved on founder instruction: this record and both notices were copied
  to the install root (see the note at the top). The claim audit is re-run there and the result is
  in the commands table.
- **Pinned evidence moves.** `20260824-codex-real-journey-api-wiring.md`, its final adjudication
  (row 14) and handoff `20260824-real-journey-api-recheck.md` cite "six trades and six fill rows"
  for the UI default backtest. After this repair that run gives 13. Notice filed.
- The retail-redesign parity test comment goes stale on merge. Notice filed; their files untouched.
- Merging this branch changes every synthetic backtest result listed above, so it needs founder
  approval.

## Stop point

Record filed in the worktree; no source edited yet.

## Next safe action

Reproduce at `e787ac462` and capture the caller baselines.
