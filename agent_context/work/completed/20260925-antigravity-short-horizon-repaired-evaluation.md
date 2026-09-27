# Completed work: short-horizon repaired evaluator re-measurement

STATUS: COMPLETED  
OWNER: Antigravity  
TOOL: Antigravity  
STARTED_UTC: 2026-09-25T08:38:00Z  
COMPLETED_UTC: 2026-09-25T09:40:00Z  
STARTING_REVISION: c270017b3b6a9d8130ad57d157886985ca4f70d5  
WORKTREE_OR_BRANCH: D:\quant_system on main  

## Objective

Re-measure the nine declared short-horizon research trials (Ridge, TimesFM 3.0, and TimesFM 2.5 across holds 1, 2, and 3) plus the 30-seed NOISE control using the repaired evaluator (`056fb1c6`), which introduced:
1. A capital-constrained tranche ledger in `score_decisions` preventing overlapping positions from multiplying capital up to 3x.
2. Past-only abstention calibration (folds scored against past folds only; fold 0 in cash).
3. Sample length derived from independent non-overlapping portfolio periods.
4. Annualization consistent with `252 / held_sessions`.
5. Renaming `BUY_AND_HOLD` to `ALWAYS_TRADE`.

Preserve all pre-repair historical evidence and write outputs to distinct parallel files. Publish a side-by-side comparative analysis and formal notice detailing the exact impact on Sharpe, DSR, trade count, exposure, drawdown, and comparison against the repaired noise benchmark.

## Owned paths

- `reports/short_horizon/repaired_results-ridge.json`
- `reports/short_horizon/repaired_results-timesfm.json`
- `reports/short_horizon/repaired_results-timesfm25.json`
- `reports/short_horizon/repaired_results-noise-control.json`
- `reports/short_horizon/REPAIRED-EVALUATOR-COMPARISON.md`
- `agent_context/work/active/20260925-NOTICE-short-horizon-repaired-evaluator-measured.md`
- `agent_context/work/completed/20260925-antigravity-short-horizon-repaired-evaluation.md`

## Non-goals

- No new trials declared; no multiplicity budget expansion beyond the frozen 9 trials.
- No editing or overwriting of existing `results-*.json` or `TRIAL-LEDGER.md` (claimed by other records).
- No modification of the untouched 252-session holdout.
- No live-money trading (T4 excluded).

## Plan & Execution

1. Create active-work record claiming exact output paths. (**DONE**)
2. Execute Ridge arm (holds 1, 2, 3) to `reports/short_horizon/repaired_results-ridge.json`. (**DONE**)
3. Execute TimesFM 3.0 arm (holds 1, 2, 3) to `reports/short_horizon/repaired_results-timesfm.json`. (**DONE**)
4. Execute TimesFM 2.5 arm (holds 1, 2, 3) to `reports/short_horizon/repaired_results-timesfm25.json`. (**DONE**)
5. Execute Noise control (30 seeds across holds 1, 2, 3) to `reports/short_horizon/repaired_results-noise-control.json`. (**DONE**)
6. Compile comprehensive comparative report `reports/short_horizon/REPAIRED-EVALUATOR-COMPARISON.md`. (**DONE**)
7. File additive notice `agent_context/work/active/20260925-NOTICE-short-horizon-repaired-evaluator-measured.md`. (**DONE**)

## Decision rationale

- Re-measuring the pre-declared trials on the repaired harness recovers the true empirical metrics without inflating the search space or spending new multiplicity ordinals, as recommended by `20260914-NOTICE-short-horizon-evaluator-repaired-invalidates-ledger-numbers.md`.
- Parallel output files preserve the historical audit trail and prevent file collision with other active claims per PROTOCOL §8.

## Commands and outcomes

| Command | Result | Evidence/notes |
|---|---|---|
| `uv run python scripts/run_short_horizon_experiment.py --help` | PASS | Exit 0, CLI flags verified |
| `uv run python scripts/run_short_horizon_experiment.py --arm ridge --out reports/short_horizon/repaired_results-ridge.json` | PASS | Exit 0, task-70. Hold 1/2/3 evaluated |
| `uv run python scripts/run_short_horizon_experiment.py --arm timesfm --timesfm-forecasts reports/short_horizon/timesfm-forecasts.json --out reports/short_horizon/repaired_results-timesfm.json` | PASS | Exit 0, task-74. Hold 1/2/3 evaluated |
| `uv run python scripts/run_short_horizon_experiment.py --arm timesfm --timesfm-forecasts reports/short_horizon/timesfm25-forecasts.json --out reports/short_horizon/repaired_results-timesfm25.json` | PASS | Exit 0, task-78. Hold 1/2/3 evaluated |
| `uv run python scripts/run_short_horizon_experiment.py --arm noise --noise-seeds 30 --out reports/short_horizon/repaired_results-noise-control.json` | PASS | Exit 0, task-82. 30 seeds evaluated |
| `scripts/audit-agent-claims.ps1` | PASS | Verified claims integrity |
| `scripts/audit-disk-layout.ps1` | PASS | Verified disk layout rules |

## Files changed

- `reports/short_horizon/repaired_results-ridge.json`: Created with repaired Ridge evaluations.
- `reports/short_horizon/repaired_results-timesfm.json`: Created with repaired TimesFM 3.0 evaluations.
- `reports/short_horizon/repaired_results-timesfm25.json`: Created with repaired TimesFM 2.5 evaluations.
- `reports/short_horizon/repaired_results-noise-control.json`: Created with 30-seed repaired noise control evaluations.
- `reports/short_horizon/REPAIRED-EVALUATOR-COMPARISON.md`: Comprehensive comparative synthesis and breakdown.
- `agent_context/work/active/20260925-NOTICE-short-horizon-repaired-evaluator-measured.md`: Formal notification under PROTOCOL §8.4.
- `agent_context/work/completed/20260925-antigravity-short-horizon-repaired-evaluation.md`: Completed task record.

## Blockers and conflicts

None. All owned paths were distinct, unshared, and non-destructive.

## Stop point

All four evaluation runs completed, artifacts verified, comparative report written, and official notice posted.

## Next safe action

Synthesize final findings with the founder and determine future strategic direction (e.g. closing short-horizon directional modeling, or focusing on cross-sectional multi-instrument ranking).
