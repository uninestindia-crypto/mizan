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
- `src/quant_system/modeling/preprocessing.py`
- `src/quant_system/modeling/ridge.py`
- `src/quant_system/modeling/validation.py`
- `src/quant_system/modeling/metrics.py`
- `src/quant_system/modeling/training_evidence.py`
- `src/quant_system/modeling/errors.py`
- `src/quant_system/modeling/__init__.py`
- `tests/modeling_training_fixtures.py`
- `tests/test_modeling_preprocessing.py`
- `tests/test_modeling_ridge.py`
- `tests/test_modeling_trials.py`
- `tests/test_modeling_validation.py`
- `tests/test_modeling_training_replay.py`
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
2. IN PROGRESS - implement the vertical training/evaluation journey and evidence adapters.
3. IN PROGRESS - add failing-first tests, provider replay, and dangerous mutation evidence.
4. PENDING - run the exact gate, Red Team, repairs, and independent clean-state verification.
5. PENDING - certify Slice 4 and hand off Slice 5 final-holdout work.

## Current step

Candidate implementation and four mutation kills are complete. Prepare an exact candidate commit
for independent Red Team and clean-clone verification.

## Evidence so far

- Exact local gate: Ruff format 191 files; strict Mypy 81 source files; 235 tests; 5,580
  statements / 630 missed / 88.71%; 68 focused modeling tests; vulture, zero secret candidates,
  Code Craft, and Test Craft clean.
- Independent-root replay pinned equal start, model, and outcome manifest hashes.
- Four raw mutations killed and restored: score equality, validation leakage, success-only
  multiplicity, and trial-start-after-fit. See `.launch/reports/MUTATION-SLICE-04.md`.
- No holdout was opened and every model evidence record remains `RESEARCH_ONLY` with
  `UNCALIBRATED_SCORE` outputs.

## Files changed

- Added governed trial, preprocessing, ridge, metric, validation, and persistence contracts under
  `src/quant_system/modeling/` and exported them through the modeling package.
- Added six Slice 4 test/fixture files, the exact gate script, frozen contract, and mutation report.

## Blockers and conflicts

No current blocker. Existing unowned files and automated pipeline artifacts will be preserved.
