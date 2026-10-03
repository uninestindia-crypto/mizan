# Active work: daily_pipeline builds one governor and shares it between two backtests

STATUS: ACTIVE  
OWNER: Claude Code session (founder instruction 2026-09-29: give each backtest engine in
`scripts/daily_pipeline.py` its own risk governor)  
TOOL: Claude Code  
STARTED_UTC: 2026-09-29T10:00:00Z  
STARTING_REVISION: `63941c583cb40c4c1fbda3af8bca15d4df1a0ac6` (main; the defect was measured at
`e787ac462`, and `scripts/daily_pipeline.py` is byte-identical between the two)  
WORKTREE_OR_BRANCH: `D:\quant_system` on `main`, shared checkout, no worktree created. Claims are
exact and disjoint from every other active record (checked below).

## Objective

`run_daily_pipeline()` builds one `PreTradeRiskGovernor` and passes it to both
`BacktestEngine`s. The ML run trips the governor's kill switch, so the momentum baseline is refused
on every order. Its published `momentum_cagr_pct`, `momentum_sharpe_ratio` and
`momentum_max_drawdown_pct` are artifacts of the shared governor, not measurements of the strategy.
Give each engine a fresh governor built from the same `RiskLimits`. Prove it with a failing-first
regression test in a new file.

## Owned paths

- `scripts/daily_pipeline.py`. Grep of every active record for `daily_pipeline` finds only
  `20260821-claude-check-tests-casebody.md` (owns `tests/test_daily_pipeline.py`, not the script)
  and a passing mention in `20260822-claude-h2-l2-repair.md:260`. No record lists the script.
- `tests/test_daily_pipeline_governor_isolation.py` (new)
- `agent_context/work/active/20260929-1000Z-claude-daily-pipeline-governor-per-engine.md` (this)
- `agent_context/work/active/20260929-NOTICE-daily-pipeline-momentum-figures-were-artifacts.md`
  (new, only if a record or report cites the old figures)

## Non-goals

- **`tests/test_daily_pipeline.py`** is claimed by `20260821-claude-check-tests-casebody.md`
  (HANDOFF_REQUIRED). Not edited.
- **`src/quant_system/backtest/engine.py`** is claimed by
  `20260929-0431Z-claude-backtest-engine-held-position-marks.md` (branch
  `claude/magical-taussig-9dceb1`, ACTIVE, uncommitted in that worktree). Not edited.
- **`src/quant_system/risk/governor.py`** is owned by `20260822-claude-money-paths-remainder.md`
  (IN_PROGRESS). Not edited.
- The ML run's own kill-switch trip. It comes from the engine never calling `reset_session_peak`, so
  `max_daily_drawdown_pct` behaves as a whole-run trailing drawdown. Tracked separately. Not fixed
  here, so the ML figures are expected to be unchanged by this repair.
- No commit, merge, push, or staging without founder approval.
- No edit to any existing report, record, or `logs/daily_runs/` output.

## Plan

1. Startup sequence, claim check, this record. DONE.
2. Baseline: run `run_daily_pipeline(target_date=date(2026, 9, 29), output_dir=<scratch>)` at the
   unrepaired script, and count governor refusals per engine. IN PROGRESS.
3. Write the regression test first and show it fails on the unrepaired script.
4. Repair `scripts/daily_pipeline.py`: one fresh `PreTradeRiskGovernor(limits=risk_limits)` per
   engine, one shared `RiskLimits`.
5. Show the test passes; re-run the pipeline and record the changed momentum figures.
6. Mutation-check the test: re-share the governor and confirm it fails again.
7. Search `logs/daily_runs/` and every active record for citations of these momentum figures. File a
   notice, never an edit.
8. Gates: ruff, ruff format --check, mypy, pytest forwards and reverse, both audits, craft checkers.

## Current step

Step 2.

## Decision rationale

Established by reading the code at `63941c583`:

- `scripts/daily_pipeline.py:136` builds `governor`; `:152` and `:175` pass that object to
  `ml_engine` and `mom_engine`.
- `PreTradeRiskGovernor` holds mutable per-run state: `_is_killed`, `_daily_peak_equity`,
  `_all_time_peak_equity`, `_kill_events` (`risk/governor.py:46-54`). `evaluate_order` calls
  `update_peaks` first (`:195`) and refuses on `_is_killed` (`:199`). So the second run inherits both
  a latched switch and the first run's peaks.
- `RiskLimits` is a configuration object, not state, so one instance can be shared safely. The
  governor is the thing that must not be.

Repair shape: build `RiskLimits` once, then `PreTradeRiskGovernor(limits=risk_limits)` inline at each
`BacktestEngine(...)` construction. No helper, no new parameter, no change to the summary schema.

Test shape: observe the governors each engine actually receives, without editing the engine.
Wrap `BacktestEngine.__init__` at class level from the test to record `risk_governor`, then assert
the two governors are distinct objects, share equal limits, and that the momentum governor did not
begin with a latched switch. A second assertion checks the behavioural consequence directly: the
momentum engine's governor must record no kill event that predates its own first order. The exact
form is settled after the baseline shows what is observable.

## Commands and outcomes

| Command | Result | Evidence/notes |
|---|---|---|
| `git status --short --branch`, `git worktree list`, `git branch --list` | PASS | main ahead 2 of origin; 6 worktrees, 13 non-default branches; install root has other agents' uncommitted records and ~1500 modified `data/evidence/market-cache` files, all untouched |
| read all 121 active records for `daily_pipeline` / `daily_runs` | PASS | no record claims the script |
| read `20260929-0431Z-...held-position-marks.md` and its two notices from the magical-taussig worktree | PASS | it names this defect as its "observed, not repaired" item 2 and says the momentum run is unchanged by its own repair |

## Files changed

- this record

## Blockers and conflicts

- The install-root copy of `20260929-0431Z-claude-backtest-engine-held-position-marks.md` does not
  exist. That record lives only in the magical-taussig worktree (uncommitted), so from the install
  root it claims nothing, per PROTOCOL 8.1. I treat it as binding regardless, because the worktree
  and branch are registered and the record names the path. Not my record to fix.

## Stop point

Record filed. No source edited.

## Next safe action

Capture the baseline run and refusal counts.
