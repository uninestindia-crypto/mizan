# Red Team governed feature-window recheck — final-2

Date: 2026-08-24
Reviewer: Codex / Dalton, independent of the repair author
Exact tested revision: `88a7ac988114267a0d44203587a57b680717bf3b`
Finding count: 0 Blocker, 0 Major, 0 Minor

## Release verdict

`READY FOR PHASE-1 BASELINE ONLY` for this narrowly defined feature-window audit. This is not a
whole-product or deployment verdict; no launch authorization follows from it.

## Progress dashboard

The external coverage ledger contains 30 items: 30 observed expected outcomes, 0 failed, 0 blocked,
and 0 unexecuted. Audit completion and verified item coverage are both 100.00% for this explicitly
bounded matrix. The generated dashboard is
`D:\quant_system_workspaces\scratch\qa-governed-feature-window-final-2-88a7ac9-20260824-codex-dalton\coverage-dashboard.md`.

## Product topology and scope

The tested topology consists of the exported Python feature kernel, governed training builders and
evaluator, immutable trial/model evidence adapters, governed execution bundle/strategy, the real
shadow-session CLI, and repository verification scripts. Web, packaged desktop, mobile, broker, and
live-feed surfaces were not inferred into this repair-specific scope.

## Critical journey summary

The critical journey was one financial decision flowing through trailing-window feature creation,
training identity, model publication identity, execution scoring, and fail-closed historical
evidence loading. Happy paths, minimum/one-bar boundaries, invalid order/duplicates, unavailable
data, legacy/current mismatches, persistence reconstruction, concurrency, scale, and runner side
effects were all executed. Detailed evidence follows below.

## Defects by severity

No P0–P4 defect was reproduced in the requested matrix. The non-product harness setup errors are
disclosed in the external raw log and were removed by constructing coherent public fixtures; they
did not change any product or existing test file.

## Consumer experience

N/T. This is a public Python API and CLI correctness recheck, not a rendered consumer-interface
audit. CLI refusal text and exit behavior were observed; visual, accessibility, and usability scores
would be unsupported.

## Blockers, assumptions, and blind spots

There was no blocker to the 30 requested items. The principal assumption is that the intended
canonical contract is the trailing 21 chronological point-in-time bars and schema v2, as stated in
the task and repository contracts. Residual blind spots are enumerated in `NOT PROBED`.

## Prioritized repair plan

No repair is proposed because this run reproduced no correctness defect. If future evidence breaks
one of these boundaries, first preserve the typed reproduction, then repair the smallest responsible
kernel/binding boundary and rerun this 30-item matrix plus the full and reverse-order suites.

## Approval request

No Phase 2 repair approval is requested. No product repairs were made. Additional work requires a
new scope or a newly reproduced defect.

## Outcome

No correctness issue was observed in the requested 30-check matrix: the two prior reproductions
closed with their required typed errors and all 28 follow-up items produced the specified behavior.
This is a bounded independent recheck, not a claim that untested environments or future inputs are
defect-free.

The product source and existing tests remained read-only. All custom probes and generated evidence
are outside product source at:

`D:\quant_system_workspaces\scratch\qa-governed-feature-window-final-2-88a7ac9-20260824-codex-dalton`

The clean detached verification clone is:

`D:\quant_system_workspaces\verification_clones\redteam-governed-feature-window-final-2-dalton-88a7ac9-20260824-113944`

`git rev-parse HEAD` returned the exact requested hash. `git status --short --branch` in the clone
returned only `## HEAD (no branch)` after the run. The clone's target commit changed
`src/quant_system/modeling/features.py`, `tests/test_governed_feature_window.py`, and the repair
author's work record; this reviewer changed none of them.

The stopped Socrates claim and all prior records, reports, clones, and scratch paths were observed
as conflicts/exclusions and were not edited, adopted, retired, removed, or used.

## Required prior reproductions

| Reproduction | Public boundary | Exact observed result | Prohibited output |
|---|---|---|---|
| v1 trial over v2 feature dataset | `evaluate_governed_ridge_fold` | `TRAINING_INPUT_MISMATCH` | `evaluation_identity_returned=false`; `model_identity_returned=false` |
| reversed chronological 21-bar input | `compute_feature_values` | `RECORD_ORDER_INVALID` | `feature_vector_returned=false` |

Both probe processes exited `0`, meaning the probes observed exactly those conditions.

## Follow-up matrix: 28 of 28 executed

### Canonical window, boundaries, availability, order, determinism, and scale

| Item | Exact observation |
|---|---|
| 21/60/120 feature identity | Canonical JSON-byte SHA-256 was identical at all lengths: `470b2e249a4242873d80e9e30b6d86ee82f06601d7aa46c5f5d7d7ac1a2c16bc`. |
| 21/60/120 execution feature-and-score identity | Combined feature/score byte SHA-256 was identical at all lengths: `c2958d75078522f121f70609e926cc5162c645cf401e2f4a9726292161951bc7`. |
| 21/60/120 acquisition-length training identity | Final training row decision/features/input hash was byte-identical: `093052aff0fd1e4ffb1447365171c83c02c83f9e48b48f08dc3d4ae23dcbd280`. |
| 20 bars | Kernel and training returned `INSUFFICIENT_HISTORY`; execution returned zero signals. |
| 21 bars | Training emitted one row; execution emitted one signal. |
| 22 bars | Training emitted two rows; the final row equaled an independent computation over bars 2–22. |
| Execution availability | A 22nd bar whose `available_at` followed the decision was excluded; feature values and score remained identical to the 21 available bars. |
| Training availability | A bar unavailable at its feature decision returned `POINT_IN_TIME_VIOLATION`. |
| Reverse ordering at execution | The execution adapter normalized available bars by date and produced the same score/features as chronological input. |
| Reverse ordering at kernel/training | Kernel reproduction returned `RECORD_ORDER_INVALID`; focused `test_record_order_change_is_rejected` exercised training rejection. |
| Duplicate dates | Kernel and coherent training acquisition returned `RECORD_ORDER_INVALID`; execution raised `GovernedExecutionError` containing `duplicate exchange dates`. |
| Repeated/concurrent determinism | 32 feature calls and 32 execution calls across eight threads were byte-identical within each result set. |
| 10,000-bar scale | Kernel result and execution score equaled the trailing-21 result. Measured kernel time `0.004927s`; strategy time `0.008292s` on this host. |

The 10,000-bar scale item intentionally targets the kernel and strategy public surfaces. A coherent
10,000-row governed daily acquisition cannot be constructed through `HistoricalDailyRequest`: the
public data contract rejects daily requests exceeding the Upstox ten-year retrieval limit before
the training builder is reached. That attempted extension is listed under `NOT PROBED` rather than
being silently treated as training evidence.

### Legacy/current schema boundaries

| Boundary | Fixture | Typed outcome |
|---|---|---|
| Historical multiplicity | Coherent v1 trial start + schema-less pre-v2 model publication + successful outcome | Registry reconstructed with `multiplicity_count=1`, schema `quantos.ridge_technical_six` v1. |
| Schema-less model identity | Ordinary pre-v2 model metadata | `GovernedExecutionError`: missing `feature_schema_id`; no identity returned. |
| Explicit v1 execution bundle | v1 identity + matching fitted/preprocessing/card fields | `GovernedExecutionError`: incompatible feature schema; no bundle returned. |
| Current rows → current dataset | One ordinary feature row relabelled v1 inside a v2 dataset | `DATASET_INTEGRITY_INVALID`. |
| Current dataset → v1 trial | v2 feature dataset supplied to v1 trial/registry | `TRAINING_INPUT_MISMATCH`; no evaluation returned. |
| v1 trial → current publication | Current evaluation presented with a v1 trial claim | `TRAINING_INPUT_MISMATCH`; no publication returned. |
| Persisted reconstruction mismatch | v1 trial + current-schema model publication + matching terminal outcome | `MULTIPLICITY_INVALID`; no registry returned. |
| Publication relabelling | Current evaluation presented under legacy schema | `TRAINING_INPUT_MISMATCH`; no publication returned. |
| Publication → execution bundle | Current publication identity deliberately changed to v1 | `GovernedExecutionError`: incompatible feature schema; no bundle returned. |

This establishes the intended split: coherent historical v1/schema-less evidence remains readable
for attempt multiplicity, but neither schema-less nor explicit v1 evidence is executable under the
canonical-window v2 contract.

## Real evidence runner

Exact command from the detached clone:

```powershell
.\.venv\Scripts\python.exe scripts\run_governed_shadow_session.py --evidence-root D:\quant_system\tmp\real-training-evidence
```

Exact process exit code: `3`.

Raw output:

```text
evidence store                    : D:\quant_system\tmp\real-training-evidence
published models                  : 40
selected model                    : model_b0e4e7dc4c30e2ca534b1e6c (trial trial_uni_018)
verdict in evidence               : RESEARCH_ONLY
published DSR                     : 0.696672616037
score_threshold                   : -0.13382 (from the trial start, not a default)
model symbol                      : GRASIM (from verified published decisions)
fitted state                      : intercept=-0.133819951338 hash=64969ae663e261d0...
preprocessing                     : state_hash=51a4f7746a546332...
binding                           : OK

REFUSED BY GOVERNED EXECUTION
  model_id            : model_b0e4e7dc4c30e2ca534b1e6c
  trial_id            : trial_uni_018
  verdict in evidence : RESEARCH_ONLY
  deflated_sharpe     : 0.696672616037
  multiplicity_count  : 18
  refusal             : model evidence is missing an identity field: 'feature_schema_id'

Governance failed closed. No session ran, and no artifact was relabelled or promoted to
make one run.
```

Read-only before/after evidence-store snapshots were identical:

| Scope | Before | After |
|---|---|---|
| Entire evidence tree | 425 files, 519456 bytes, `4a671f73160712ca656f7702dad6d1709395420d3e55ecd09c4e9dea415789f5` | identical |
| `sessions/` | exists, 0 files, empty SHA-256 `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` | identical |
| `orders/` | absent, 0 files | identical |

No session or order was created.

## Repository command evidence

All commands below ran from the exact detached clone unless a different working directory is shown.

| Command | Exit | Raw summary |
|---|---:|---|
| `uv sync --frozen --extra dev --link-mode copy` | 0 | Python 3.13.15 environment; 47 packages installed from the lock. |
| `.\.venv\Scripts\python.exe -m pytest -q tests\test_governed_feature_window.py tests\test_governed_bundle_binding.py tests\test_modeling_features.py tests\test_modeling_validation.py tests\test_modeling_trials.py tests\test_governed_strategy.py tests\test_governed_shadow_wiring.py` | 0 | `114 passed in 4.19s` |
| `.\.venv\Scripts\python.exe -m pytest -q` | 0 | `869 passed, 1 warning in 56.60s` |
| `$testFiles=@(Get-ChildItem tests -Filter test_*.py -File -Recurse \| Sort-Object FullName -Descending \| ForEach-Object FullName); .\.venv\Scripts\python.exe -m pytest -q $testFiles` | 0 | `REVERSED_FILE_COUNT=71`; `869 passed, 1 warning in 46.14s` |
| `.\.venv\Scripts\python.exe -m ruff check .` | 0 | `All checks passed!` |
| `.\.venv\Scripts\python.exe -m mypy src scripts\run_governed_shadow_session.py` | 0 | `Success: no issues found in 122 source files` |
| `powershell -ExecutionPolicy Bypass -File scripts\audit-agent-claims.ps1` from `D:\quant_system` | 0 | Every workspace had a visible resolving claim. |
| `powershell -ExecutionPolicy Bypass -File scripts\audit-disk-layout.ps1` from `D:\quant_system` | 0 | No stray QuantOS directories. |

The sole test warning in both whole-suite runs was the dependency warning
`StarletteDeprecationWarning` from FastAPI's installed `testclient.py` about deprecated
`starlette.testclient` use with `httpx`; it did not fail a test.

## Startup, isolation, and exact commands

The startup sequence re-read `AGENTS.md`, `agent_context/README.md`, `CURRENT.md`, `PROTOCOL.md`,
`DISK-LAYOUT.md`, `.launch/STATE.md`, `.launch/SLICES.md`, every active-work record, all registered
worktrees/branches, and `.launch/reports/quarantine/README.md`. Existing install-root changes were
treated as other agents' work.

The unique install-root record was created before this canonical clone command:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/new-workspace-clone.ps1 -Purpose redteam -Label governed-feature-window-final-2-dalton -Revision 88a7ac988114267a0d44203587a57b680717bf3b
```

The deterministic discovery helper scanned 572 files. A fresh 30-item coverage ledger recorded
30 observed expected outcomes, zero failed items, and zero blocked items. External evidence records,
logs, discovery output, and probe source remain in the unique scratch directory named above.

## Twelve Red Team families

| Family | Attack exercised | Result |
|---|---|---|
| 1. Type boundaries | Ordinary v1/v2 and schema-less identity substitutions | Typed refusals; no leaked identities/bundles. |
| 2. Numeric boundaries | 20/21/22 bars and exact Decimal feature/score bytes | Minimum and one-bar transitions behaved as specified. |
| 3. Empty/missing | Fewer than 21 bars and absent schema identity | Empty execution result for insufficient history; missing identity failed closed. |
| 4. Temporal/point-in-time | Bar unavailable at decision/training cutoff | Future execution bar excluded; training returned `POINT_IN_TIME_VIOLATION`. |
| 5. Ordering/duplicates | Reversed bars and duplicate dates across kernel/training/execution | Strict typed rejection at kernel/training; execution duplicate refusal; reverse execution normalization. |
| 6. Identity/binding | Row→dataset→trial→publication→bundle | Every deliberate mismatch was rejected before downstream identity use. |
| 7. Persistence/reconstruction | Coherent legacy history and mismatched persisted model link | Legacy multiplicity readable; mismatched reconstruction `MULTIPLICITY_INVALID`. |
| 8. Authorization/governance | Real `RESEARCH_ONLY` evidence at shadow runner | Exit `3`; no relabelling, session, or order. |
| 9. Determinism/concurrency | Repeats and 32 concurrent calls | Byte-identical within feature and score result sets. |
| 10. Scale/resource | 10,000 bars at kernel/strategy | Trailing-21 equivalence with measured millisecond runtimes. |
| 11. State leakage/test order | Full suite in normal and reverse file order | Same 869-test count and zero failures in both orders. |
| 12. Repository hygiene | Ruff, Mypy, claim audit, disk-layout audit, clean clone status | Every command exited `0`; no product/test mutation. |

## Findings

No `FINDING` record was opened because no requested correctness property deviated from its expected
behavior. Consequently there is no severity, affected path, or repair recommendation to report.

## NOT PROBED

- NOT TESTED — a 10,000-row governed *training acquisition*: the public
  `HistoricalDailyRequest` rejects a daily range longer than ten years before
  `build_feature_dataset` can run. The requested 10,000-bar kernel/strategy scale path was tested.
- NOT TESTED — Linux/macOS, other Python versions, alternative NumPy/BLAS builds, CPU architectures,
  timezone/locale variants, and cross-process concurrency.
- NOT TESTED — a genuinely promoted current-v2 model from the real evidence directory; the available
  selected evidence is historical/schema-less and `RESEARCH_ONLY`, so the real runner correctly
  stopped before session construction.
- NOT TESTED — live market feed connectivity, market-hours session execution, broker connectivity,
  paper/live order routing, fills, fees, or real-money behavior. No authorization for those effects
  was inferred.
- NOT TESTED — property-based fuzzing beyond the named boundary/mismatch fixtures, deliberate disk or
  process fault injection, memory profiling, and histories larger than 10,000 bars.
- NOT TESTED — browser/UI, packaged launcher, mobile, accessibility, and visual journeys; they are
  outside this governed feature-window public-API recheck.
