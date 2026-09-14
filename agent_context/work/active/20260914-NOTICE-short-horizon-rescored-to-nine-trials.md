# NOTICE: every short-horizon DSR was re-deflated to nine trials, and your published figures moved

STATUS: NOTICE (additive; no other record is edited)
OWNER: Claude Code (Opus 5), filer
FILED_UTC: 2026-09-14T17:40:00Z
FOR: `20260910-1615Z-claude-mizan-correction-and-short-horizon-program.md` (STATUS `ACTIVE`), which
  owns `reports/short_horizon/**`, `scripts/run_short_horizon_experiment.py`,
  `src/quant_system/research_short_horizon/**` and `tests/test_short_horizon*.py`
FILER'S RECORD: `20260914-1520Z-claude-short-horizon-multiplicity-rescore.md`
AUTHORIZATION: founder instruction, 2026-09-14 — *"Re-score every short-horizon ridge, TimesFM 3.0,
  TimesFM 2.5, and noise result against the frozen nine-trial multiplicity budget. Fix the hardcoded
  declared-trial count, preserve the original raw metrics, regenerate the affected
  result/report/model-card artifacts, add regression coverage, and do not run any additional trial or
  consume a new ordinal."*
FILED UNDER: PROTOCOL §8.4 — a change that moves numbers another active record pins as evidence
  requires a notice naming the exact figures it invalidates. This is that notice.

## This is the decision the 2026-09-14 evaluator notice left to you

`20260914-NOTICE-short-horizon-evaluator-repaired-invalidates-ledger-numbers.md` said explicitly:
*"Whether re-running the nine declared trials spends new ordinals is this record's owner's call, not
the filer's."*

The founder took a **narrower** option than either the notice offered. Not a re-run: a re-deflation
of the numbers already stored, changing `num_trials` from 6 to 9 and nothing else.

**No trial was run. No ordinal was spent. No holdout was touched. No evaluator was invoked.** The
re-scoring tool imports `OverfittingDiagnostics`, `GatePolicyV1` and a ledger parser, and a test
asserts it imports nothing from `research_short_horizon.evaluation` or any training script — so it is
structurally incapable of running a trial, not merely documented as not doing so.

## The exact figures that changed

Every deflated Sharpe in `reports/short_horizon/` and `reports/model_cards/`. The originals are
preserved in each results file under `*_as_published` keys and are quoted beside the corrected value
in every table.

| # | Arm | Hold | As published (6) | Re-scored (9) | Delta |
|---|---|---:|---:|---:|---:|
| 1 | ridge | 1 | 0.026515 | **0.015569** | -0.010946 |
| 2 | ridge | 2 | 0.059283 | **0.037419** | -0.021864 |
| 3 | ridge | 3 | 0.094711 | **0.062647** | -0.032064 |
| 4 | TimesFM 3.0 | 1 | 0.023189 | **0.013464** | -0.009725 |
| 5 | TimesFM 3.0 | 2 | 0.004270 | **0.002182** | -0.002088 |
| 6 | TimesFM 3.0 | 3 | 0.191369 | **0.137089** | -0.054280 |
| 7 | TimesFM 2.5 | 1 | 0.167607 | **0.118147** | -0.049460 |
| 8 | TimesFM 2.5 | 2 | 0.107263 | **0.071891** | -0.035372 |
| 9 | TimesFM 2.5 | 3 | 0.394441 | **0.312642** | -0.081799 |
| NOISE | control | 1 | 0.000000 | 0.000000 | +0.000000 |
| NOISE | control | 2 | 0.148551 | 0.103240 | -0.045311 |
| NOISE | control | 3 | 0.419649 | 0.336002 | -0.083647 |

Noise distribution over 30 seeds, median DSR: `0.0000 / 0.1615 / 0.5504` becomes
`0.0000 / 0.1134 / 0.4626`. Worst draw at hold 3: `0.3197` becomes `0.2454`. All 90 per-seed values
were re-deflated individually and the order statistics rebuilt from them.

**The best figure in your program is now `0.312642`, not `0.394441`.**

## What was deliberately NOT touched

- **Every raw metric.** Sharpe, hit rate, trades, exposure, max drawdown, total and mean net return,
  fold counts, row counts, purge and embargo counts, the abstention grid and its thresholds, and
  every per-seed noise Sharpe are byte-identical to what you published. Verified field by field
  against `git show HEAD:` for all four files: **0 raw-metric fields changed.**
- `timesfm-forecasts.json`, `timesfm25-forecasts.json` and both `.partial.jsonl` files.
- `results-noise-control.superseded-20260911T061355.json` — a superseded archive. History is not
  re-scored.
- `src/quant_system/research_short_horizon/evaluation.py`, `abstention.py`, `horizon.py`,
  `walkforward.py`.
- Any evidence store, any paper book, anything under `logs/`.

## No conclusion moved, and that was verified rather than assumed

Re-deflation applies the same monotone map to every row at a given hold, so it is rank-preserving.
The count of noise seeds beating each model is **identical before and after** — 0/30 at hold 1; at
hold 3 all 30 beat the ridge and TimesFM 3.0 while 29 of 30 beat TimesFM 2.5. A test pins this
(`test_the_rescoring_preserves_every_comparison_against_the_control`), because it is what licenses
leaving your narrative sentences unedited while relabelling the numbers inside them.

Nothing became promotable; nothing stopped being beaten by the control.

## The correction this does NOT apply, restated so it cannot be lost

Your evaluator was repaired at `056fb1c6`. **The raw metrics above still predate that repair** —
compounded overlapping positions, pooled abstention calibration, and a DSR sample length and
annualisation that disagreed. Undoing that needs the nine trials re-run, which the instruction
forbade.

So the correct reading of every figure now in your artifacts is: *the deflation is honest at the
metrics that were actually published, and those metrics are still the output of an evaluator known to
be wrong in four specific ways.* Each results file carries
`raw_metrics_predate_evaluator_repair: "056fb1c6"` per trial, and a test asserts it is there.

**Your open decision is unchanged and is still yours:** whether to re-run the nine trials under the
repaired evaluator.

## The hardcoded count, and what changed about it

`DECLARED_TRIALS` was already `9` — `056fb1c6` set it, after the 2026-09-12 notice flagged it at `6`.
Its *value* was not the remaining problem; its *mechanism* was. It sat unconnected to the ledger for
two days across three published trials, and a CI-only test catches that after a run may already have
written a wrong number.

Added: `src/quant_system/research_short_horizon/ledger.py`, and a call to `require_declared_trials()`
as the first statement of `run()`. A constant disagreeing with the ledger now **refuses the run**.
Demonstrated, not asserted: with the constant forced to 6 and a deliberately nonexistent market-cache
path, `run()` raised on the count and never reached the path.

The constant stays an explicit literal. An unpinned parse with no declared expectation would let a
careless ledger edit silently re-score published work instead of failing.

## How the sample length was recovered, since your scorer never serialised it

Solved by inversion, and the tool refuses to write unless three independent checks agree: a unique
integer per arm and hold; consensus across all four arms (**2173 / 2172 / 2171** at holds 1/2/3); and
all **90** unrounded noise draws reproducing exactly. Your own hand-computed values for trials 7-9
(`0.118147 / 0.071891 / 0.312642`) reproduce to the digit — independent corroboration from before
this session existed.

**Two of twelve candidate rows reproduce one unit-in-the-last-place off** — ridge hold 2 (`0.059284`
vs `0.059283`) and TimesFM 2.5 hold 3 (`0.394440` vs `0.394441`). Cause: your stored Sharpe is
rounded to 6 dp and a value inside its own rounding envelope lands either side of that boundary;
demonstrated by perturbing ±5e-7. Disclosed in the ledger, the tool's output and the work record
rather than smoothed over.

## Files changed under your claim

`reports/short_horizon/results-ridge.json`, `results-timesfm.json`, `results-timesfm25.json`,
`results-noise-control.json`, `TRIAL-LEDGER.md`, `COMPARISON-REPORT.md`;
`scripts/run_short_horizon_experiment.py` (ledger binding and its docstring only — no scoring logic);
`src/quant_system/research_short_horizon/__init__.py` (re-exports). New and mine:
`src/quant_system/research_short_horizon/ledger.py`,
`scripts/rescore_short_horizon_multiplicity.py`, `tests/test_short_horizon_rescoring.py`.

Gates after the change: **1,577 passed**; ruff check and format clean across 680 files; mypy clean
across 210 files; both repository audits PASS.

## Contact

Reply in your own record or file a NOTICE back. The re-scoring is reversible: every original figure
is preserved in the results files, so restoring the published basis is mechanical if you object.
