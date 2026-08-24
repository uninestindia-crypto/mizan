# Active work: governed feature-window repair and independent recheck

STATUS: ACTIVE
OWNER: Codex — governed execution/modeling owner by founder grant
TOOL: Codex
STARTED_UTC: 2026-08-24T10:20:00Z
STARTING_REVISION: `ac47d7cc03e4aa485e2c92d7022d33de3809a1f2`
WORKTREE_OR_BRANCH: `D:\quant_system` on `main` (shared checkout; exact-path claim)

## Objective

Resolve governed-execution Blocker 2: the same decision bar currently produces different Wilder
RSI/ATR feature values when execution is served different amounts of earlier history. Establish one
explicit feature-window contract shared by training and execution, prove the former divergence and
the repaired identity, then hand the full governed execution path to an independent Red Team.

## Founder ownership grant and overlap resolution

The founder explicitly reassigned `src/quant_system/execution/**` and
`src/quant_system/modeling/**` to this agent before the governed adapter work and now directed
“complete it.” That later authority supersedes stale broad claims in the 2026-08-20/21 Slice 4
records. This record stays narrow and does not touch their evidence, launch, analytics, or work
records. The untracked `20260824-UNKNOWN_OWNER-modeling-validation-cause-assertion.md` remains
untouched.

## Owned paths

- `src/quant_system/modeling/features.py`
- `src/quant_system/modeling/__init__.py`
- `src/quant_system/modeling/rows.py`
- `src/quant_system/modeling/trials.py`
- `src/quant_system/modeling/training_evidence.py`
- `src/quant_system/modeling/persisted_trials.py`
- `src/quant_system/execution/governed_strategy.py`
- `scripts/run_governed_shadow_session.py`
- `tests/test_modeling_features.py`
- `tests/test_governed_feature_window.py` (new)
- `tests/test_governed_bundle_binding.py`
- `tests/test_governed_strategy.py`
- `tests/test_governed_execution_majors.py`
- `tests/test_governed_shadow_wiring.py`
- `tests/test_modeling_evidence_tamper.py`
- `tests/test_modeling_training_replay.py`
- `tests/test_modeling_preprocessing.py`
- `tests/test_modeling_provider_replay.py`
- `tests/test_modeling_ridge.py`
- `agent_context/decisions/20260824-canonical-feature-window.md` (new)
- `agent_context/work/active/20260824-codex-governed-feature-window-repair.md` (this file)
- `agent_context/work/completed/20260824-codex-governed-feature-window-repair.md`

## Non-goals

- Promoting any model or changing a `RESEARCH_ONLY` verdict.
- Reusing the 51-trial campaign as evidence for changed feature semantics; a feature-contract
  change invalidates arithmetic compatibility and requires a new candidate/trial.
- Changing labels, costs, folds, thresholds, the final holdout, or live-order scope.
- Editing or staging the other agent's `UNKNOWN_OWNER` record.
- Self-adjudicating the repair.

## Plan

1. DONE — reproduced history-length divergence in Wilder RSI and ATR.
2. DONE — failing public-boundary regression written and window contract recorded.
3. DONE — shared training/execution repair and v1 fail-closed binding implemented.
4. DONE — focused, mutation, static, full-suite, real-evidence-refusal, and repository audits run.
5. IN PROGRESS — commit the repair, then commission an independent Red Team recheck.

## Current step

Commit the verified repair without staging concurrent agents' records/report, then hand the exact
revision to an independent Red Team.

## Decision rationale

The selected policy is the trailing 21 available bars, enforced inside the single shared feature
kernel. It is the smallest closed window satisfying return-10, SMA-20, Wilder RSI-14, and ATR-14;
it makes values invariant to surface retention while retaining every required observation. This is
feature schema v2. Schema v1 remains loadable for historical audit but is not executable because its
expanding-prefix arithmetic is incompatible with v2 serving.

## Commands and outcomes

| Command | Result | Evidence/notes |
|---|---|---|
| Required startup sequence | RUN | HEAD `ac47d7c`; only unrelated untracked UNKNOWN_OWNER record |
| `uv run pytest -q tests/test_governed_feature_window.py` | FAIL (expected, pre-repair) | RSI `-0.055539254555` vs `-0.026943244504`; ATR `0.112724597403` vs `0.105657547632` |
| Focused governed/modeling tests | GREEN | 100 tests after explicit schema binding |
| Existing Red Team `probe_window.py` | GREEN | full-120, last-60, and last-21 values byte-identical for all six features |
| Existing `_available_window` off-by-one mutant | KILLED | 5 public-boundary failures |
| `uv run pytest -q` | GREEN | 861 tests; one third-party Starlette deprecation warning |
| Reversed test-file order | GREEN | 861 tests; same warning |
| `uv run ruff check .` | GREEN | no findings |
| `uv run mypy src scripts/run_governed_shadow_session.py` | GREEN | 122 source files |
| Real evidence runner against `tmp/real-training-evidence` | REFUSED, exit 3 | 40 verified legacy models; selected GRASIM trial 18; missing `feature_schema_id`; no session ran |
| `audit-agent-claims.ps1` | GREEN | every workspace and claim resolves |
| `audit-disk-layout.ps1` | EXTERNAL VIOLATION | unrelated `D:\quant_system_workspaces\.pytest_cache`; preserved because a concurrent verifier owns workspace artifacts |

## Files changed

- `agent_context/decisions/20260824-canonical-feature-window.md`
- `agent_context/work/active/20260824-codex-governed-feature-window-repair.md`
- `scripts/run_governed_shadow_session.py`
- `src/quant_system/execution/governed_strategy.py`
- `src/quant_system/modeling/__init__.py`
- `src/quant_system/modeling/features.py`
- `src/quant_system/modeling/persisted_trials.py`
- `src/quant_system/modeling/rows.py`
- `src/quant_system/modeling/training_evidence.py`
- `src/quant_system/modeling/trials.py`
- `tests/test_governed_bundle_binding.py`
- `tests/test_governed_execution_majors.py`
- `tests/test_governed_feature_window.py`
- `tests/test_governed_shadow_wiring.py`
- `tests/test_governed_strategy.py`
- `tests/test_modeling_evidence_tamper.py`
- `tests/test_modeling_preprocessing.py`
- `tests/test_modeling_provider_replay.py`
- `tests/test_modeling_ridge.py`
- `tests/test_modeling_training_replay.py`

## Blockers and conflicts

- Independent adjudication must be performed by a separate agent; this repair author cannot close
  its own Red Team gate.
- `src/quant_system/modeling/validation.py` is named by the concurrently discovered UNKNOWN_OWNER
  record. My interim schema edits were removed; the persisted governed boundary now owns the schema
  match without touching that file.

## Stop point

Ownership recorded before source or test edits.

## Next safe action

Stage only the files listed above, inspect the staged diff, commit, and push.
