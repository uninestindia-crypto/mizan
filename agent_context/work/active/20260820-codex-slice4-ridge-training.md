# Active work: Slice 4 governed ridge fold

STATUS: ACTIVE  
DISCOVERED_UTC: 2026-08-20T12:09:31Z  
OWNER: Codex root agent  
TOOL: Codex  
STARTED_UTC: 2026-08-20T12:09:31Z  
STARTING_REVISION: `e6002d2bd73759beb8e4cb5a8354b2eb0e77f8f6`  
WORKTREE_OR_BRANCH: `D:\quant_system` on `main`

## Objective

Implement Slice 4: one deterministic governed ridge fold with train-only preprocessing,
immutable start/outcome trial evidence, four timing/cost-aligned baselines, predictive and trading
metrics, multiplicity accounting, and reproducible hashes.

## Owned paths

- `src/quant_system/modeling/trials.py`
- `src/quant_system/modeling/persisted_trials.py`
- `src/quant_system/modeling/preprocessing.py`
- `src/quant_system/modeling/ridge.py`
- `src/quant_system/modeling/rows.py`
- `src/quant_system/modeling/partitions.py`
- `src/quant_system/modeling/evidence.py`
- `src/quant_system/modeling/validation.py`
- `src/quant_system/modeling/metrics.py`
- `src/quant_system/modeling/training_evidence.py`
- `src/quant_system/modeling/errors.py`
- `src/quant_system/modeling/__init__.py`
- `src/quant_system/analytics/multiplicity.py`
- `src/quant_system/evidence/store.py`
- `tests/modeling_training_fixtures.py`
- `tests/test_modeling_preprocessing.py`
- `tests/test_modeling_ridge.py`
- `tests/test_modeling_trials.py`
- `tests/test_modeling_validation.py`
- `tests/test_modeling_training_replay.py`
- `tests/test_modeling_partitions.py`
- `tests/test_modeling_metrics.py`
- `tests/test_multiplicity.py`
- `scripts/run-slice4-gates.ps1`
- `.launch/SLICE-04-CONTRACT.md`
- `.launch/SLICE-04-EVIDENCE.md`
- `.launch/reports/*SLICE-04*.md`
- `.launch/STATE.md`
- `.launch/SLICES.md`
- `.launch/COMMANDS.md`
- `agent_context/CURRENT.md`
- `agent_context/work/active/20260820-codex-slice4-ridge-training.md`
- `agent_context/work/completed/20260820-codex-slice4-ridge-training.md`

## Non-goals

- Opening or evaluating the final holdout, promotion beyond `RESEARCH_ONLY`, calibration claims,
  live inference, APIs, UI, or broker writes.
- Adding model families or features beyond the accepted six-feature ridge contract.
- Selecting official effective-dated NSE fee/tax rules; Slice 4 consumes the immutable cost-bound
  labels from Slice 3.

## Plan

1. COMPLETE - freeze exact trial, preprocessing, ridge, prediction, baseline, metric, and
   failure contracts.
2. COMPLETE - implement the vertical training/evaluation journey and evidence adapters.
3. COMPLETE - add failing-first tests, provider replay, and dangerous mutation evidence.
4. IN PROGRESS - run the exact gate, Red Team, repairs, and independent clean-state verification.
5. PENDING - certify Slice 4 and hand off Slice 5 final-holdout work.

## Current step

The exact `8d09ec4` recheck found six Blockers. Failing-first regressions and local repairs now cover
all six. The local full suite and focused suite pass; update evidence, commit an exact candidate,
then request fresh Red Team and independent clean-state verification.

## Evidence so far

- Exact local gate: Ruff format 191 files; strict Mypy 81 source files; 235 tests; 5,580
  statements / 630 missed / 88.71%; 68 focused modeling tests; vulture, zero secret candidates,
  Code Craft, and Test Craft clean.
- Exact repaired gate: Ruff format 194 inputs; strict Mypy 82 source files; 236 tests; 5,678
  statements / 646 missed / 88.62%; 69 focused modeling tests; vulture, zero application secret
  candidates, Code Craft, and Test Craft clean.
- Independent-root replay pinned equal start, model, and outcome manifest hashes.
- Five raw mutations killed and restored: score equality, validation leakage, success-only
  multiplicity, trial-start-after-fit, and removal of persisted multiplicity authority. See
  `.launch/reports/MUTATION-SLICE-04.md`.
- The original Red Team Major was reproduced: a second persisted attempt could reset its ordinal
  and evaluated multiplicity to one. Repair revision `bbd1f36` derives both from fully verified
  start/outcome evidence and validates the next ordinal atomically during evidence commit.
- No holdout was opened and every model evidence record remains `RESEARCH_ONLY` with
  `UNCALIBRATED_SCORE` outputs.
- Failing-first adversarial regressions now prove exact-int rejection, resumable start/model
  publication, model-bound success evidence, canonical chronological multi-symbol ordering,
  equal-weight simultaneous portfolio aggregation, and sampling-aware DSR.
- Current restored gate: Ruff format 196 inputs; strict Mypy 82 source files; 254 repository tests;
  5,806 statements / 661 missed / 88.62%; 80 focused modeling tests; vulture, zero application
  secret candidates, Code Craft, and Test Craft clean.

## Files changed

- Added governed trial, preprocessing, ridge, metric, validation, and persistence contracts under
  `src/quant_system/modeling/` and exported them through the modeling package.
- Added six Slice 4 test/fixture files, the exact gate script, frozen contract, and mutation report.

## Blockers and conflicts

- Repaired pending independent adjudication: Python booleans entered exact-int trial fields and
  poisoned persisted replay.
- Repaired pending independent adjudication: interrupted model/outcome publication had no
  supported recovery transition.
- Repaired pending independent adjudication: DSR ignored sampling uncertainty and moments.
- Repaired pending independent adjudication: dataset and fold orders contradicted for multiple
  instruments.
- Repaired pending independent adjudication: simultaneous instruments were compounded as separate
  full-capital periods and concentration was hardcoded.
- Repaired pending independent adjudication: successful outcomes did not resolve verified model
  evidence and manifest aliases were accepted.
- Existing unowned files and automated pipeline artifacts will be preserved.
