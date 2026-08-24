# Red Team governed feature-window final recheck

## 1. Release verdict

BLOCKED at exact revision `8f29564680c3563e8694ad486429c068242738ab` by one reproduced
silent financial-feature ordering failure.

The prior evaluator mismatch is no longer reproducible: a schema-v1 trial with a schema-v2 feature
dataset raised typed `TRAINING_INPUT_MISMATCH` before any model or evaluation identity was returned.
The next required ordering attack broke the exported feature kernel, so the user-mandated stop
condition prevented the remaining model, evidence-runner, regression, and static targets from
running.

Audit disposition coverage is 100.00% because every ledger item has an explicit terminal result;
verified coverage is 5.33%, with 94.66% remaining. Counts: 2 verified, 1 failed, 28 blocked. Run
milestones after this report is registered: 4/7 (57.14%), with final-build identity, post-final-change
full regression, and repair approval intentionally absent.

Tested environment:

- Detached clean clone:
  `D:\quant_system_workspaces\verification_clones\redteam-governed-feature-window-final-recheck-dalton-8f29564-20260824-112501`
- External evidence:
  `D:\quant_system_workspaces\scratch\qa-governed-feature-window-final-recheck-8f29564-20260824-codex-dalton`
- Windows, CPython 3.13.15, frozen 47-package development environment
- Product source and existing tests remained read-only

FINDING   Exported six-feature kernel silently computes a different model input from reversed chronological bars

FAMILY    Input boundaries; Data integrity; Assumption archaeology

REPRO     Run this exact retained public-API probe from the detached clone:

```powershell
Set-Location 'D:\quant_system_workspaces\verification_clones\redteam-governed-feature-window-final-recheck-dalton-8f29564-20260824-112501'
$env:PYTHONPATH='src;.'
.\.venv\Scripts\python.exe 'D:\quant_system_workspaces\scratch\qa-governed-feature-window-final-recheck-8f29564-20260824-codex-dalton\probe_kernel_ordering.py'
```

The probe creates 21 ordinary valid point-in-time bars, computes the public
`quant_system.modeling.compute_feature_values` result oldest-first, reverses the same tuple, and
calls the same exported API again.

OBSERVED  The function returned six plausible values for the reversed sequence and raised no
`ModelingError`. The probe deliberately exited `3` after detecting the wrong acceptance. Every
feature changed:

```json
{
  "actual": "values returned",
  "chronological_values": {
    "atr_14_normalized": "0.101864029338",
    "return_1": "-0.116071428571",
    "return_10": "0.053191489362",
    "return_5": "-0.029411764706",
    "rsi_14_centered": "-0.016022425963",
    "sma_20_distance": "-0.039898989899"
  },
  "first_date": "2025-01-30",
  "last_date": "2025-01-02",
  "reversed_values": {
    "atr_14_normalized": "0.098722980718",
    "return_1": "-0.038461538462",
    "return_10": "0.063829787234",
    "return_5": "0.030927835052",
    "rsi_14_centered": "-0.002891112912",
    "sma_20_distance": "-0.03"
  },
  "values_are_equal": false,
  "values_returned": true
}
```

EXPECTED  A typed `ModelingError` with `RECORD_ORDER_INVALID`, matching the strict chronological
contract already enforced by `build_feature_dataset`, and no feature values returned. Normalizing
inside the kernel would also avoid a wrong answer, but the existing training contract chooses typed
refusal for unordered or duplicate records.

BLAST     Direct callers of the exported financial-model kernel can silently receive a different
six-feature vector for the same bars. Those values can alter standardization, ridge score, model
decision, feature evidence, or any external consumer that reasonably treats an exported governed
kernel as fail-closed. The current training builder rejects nonascending records and the current
execution strategy sorts available records, so those two inspected callers are guarded; that does
not retract the wrong result already returned to other public callers. Affected paths are
`src/quant_system/modeling/features.py:270-318` and the package export in
`src/quant_system/modeling/__init__.py`. The missing validation is visible beside the existing
strict validator at `src/quant_system/modeling/features.py:147-156`.

SEVERITY  Blocker

## 2. Prior Blocker reproduction outcome

Exact command:

```powershell
Set-Location 'D:\quant_system_workspaces\verification_clones\redteam-governed-feature-window-final-recheck-dalton-8f29564-20260824-112501'
$env:PYTHONPATH='src;.'
.\.venv\Scripts\python.exe 'D:\quant_system_workspaces\scratch\qa-governed-feature-window-final-recheck-8f29564-20260824-codex-dalton\probe_evaluator_schema_mismatch.py'
```

Exit code `0`. Raw product result:

```json
{
  "error_code": "TRAINING_INPUT_MISMATCH",
  "evaluation_identity_returned": false,
  "feature_dataset_schema": [
    "quantos.ridge_technical_six",
    2
  ],
  "model_identity_returned": false,
  "trial_schema": [
    "quantos.ridge_technical_six",
    1
  ]
}
```

This checks only the exact prior evaluator mismatch. It does not infer success for adjacent schema
boundaries that were not executed.

## 3. Exact commands and raw summaries

- Startup identity:

  ```powershell
  git status --short --branch
  git rev-parse HEAD
  git worktree list
  git branch --list
  ```

  Install-root HEAD was exactly `8f29564680c3563e8694ad486429c068242738ab`. Existing modified
  and untracked paths were attributed to their visible owners and left untouched.
- Canonical clone:

  ```powershell
  powershell -ExecutionPolicy Bypass -File scripts/new-workspace-clone.ps1 -Purpose redteam -Label governed-feature-window-final-recheck-dalton -Revision 8f29564680c3563e8694ad486429c068242738ab
  ```

  Exit code `0`; detached clone path is listed above. Final clone status remained `## HEAD (no
  branch)` with no changed path.
- Frozen environment:

  ```powershell
  uv sync --frozen --extra dev --link-mode copy
  ```

  Exit code `0`; CPython 3.13.15; 47 packages installed; `quant-system==1.0.0` sourced from the
  exact clone.
- Structural discovery scanned 570 repository files. The first ledger initialization included an
  unsupported `--phase audit` argument and exited `2` before creating a ledger; rerunning the same
  initialization without that flag succeeded. This was a QA-harness invocation error, not a
  product outcome.
- Evaluator mismatch probe: exit code `0`; typed result shown above.
- Reversed-kernel probe: exit code `3`; raw wrong result shown in the finding. It reproduced once
  in one attempt; there was no variability.
- Mandatory retirement audits, run after product testing stopped:

  ```powershell
  powershell -ExecutionPolicy Bypass -File scripts/audit-agent-claims.ps1
  powershell -ExecutionPolicy Bypass -File scripts/audit-disk-layout.ps1
  ```

  Both exited `0`. The claims audit reported every workspace/branch claim resolved. The layout
  audit reported the install/workspace roots and all workspace buckets canonical, with no stray
  QuantOS directory.
- Final machine ledger summary: `Inventory items: 31`; `Audit completion: 100.00%`;
  `Verified coverage: 5.33%`; `Remaining item coverage to release: 94.66%`;
  status counts `verified=2, failed=1, blocked=28`; audit-ledger validation exited `0`.
- No focused tests, full suite, reversed suite, Ruff, Mypy, real evidence runner, determinism
  batch, or scale batch was started. No command was running or stuck at report time, and no process
  required termination.

COVERAGE  Families run: 1 (input boundaries), 8 (data integrity), and 12 (assumption archaeology).
Public product probes attempted: 2. Administrative read-only audits: 2. Runtime targets:
`evaluate_governed_ridge_fold` and `compute_feature_values`. Source targets inspected included the
exact repair diff, feature dataset builder, execution strategy, schema/evidence boundaries, runner,
and focused tests. Verified items: prior evaluator mismatch and repository ownership/layout audits.
Failed item: public-kernel chronology handling. All other inventory entries were blocked by the
explicit stop-on-correctness-issue instruction.

## 4. Progress dashboard

The external `coverage-dashboard.md` records 31 items, 100.00% audit disposition, 5.33% verified
coverage, 94.66% remaining item coverage, 2 verified items, 1 failed item, and 28 blocked items.
Coverage differs by surface: evaluator mismatch and repository administration were observed;
feature-kernel ordering failed; training, execution, persistence, runner, scale, regression, and
static surfaces were blocked after the finding.

## 5. Product topology and scope

The discovered scope contains the exported six-feature kernel, governed feature dataset builder,
ridge fold evaluator, immutable trial/evidence reconstruction, model publication, execution bundle,
governed strategy, real shadow-session runner, focused/full test suites, static gates, and workspace
audits. Only the evaluator, feature kernel, and administrative audits reached runtime. This was a
Windows local API/CLI audit; no visual desktop or browser surface was in the requested feature-window
scope.

## 6. Critical journey results

| Journey | Role/platform | Happy path | Failure/recovery | Persistence/downstream | Evidence |
|---|---|---|---|---|---|
| Trial/dataset schema mismatch | Training caller / Windows Python | N/A | Typed refusal observed before identities | No model/evaluation identity returned | `evidence/records/evaluator-schema-mismatch.json` |
| Chronological feature calculation | Model caller / Windows Python | Chronological vector observed | Reversed input silently accepted | Six wrong values returned; downstream scoring risk | `evidence/records/kernel-ordering.json` |
| Real legacy evidence execution | Operator / Windows CLI | NOT TESTED | NOT TESTED | Session/order effects NOT TESTED | None; halted |

## 7. Defects by severity

`GFWR-FINAL-001` is the sole reproduced defect: Red Team severity **Blocker**, corresponding to a
P1 critical financial-model integrity failure in the audit-report scale because the wrong answer is
silent and can feed a governed model. Preconditions, exact steps, expected/actual behavior, impact,
recurrence, evidence, and affected paths are all in the finding block above. No fix was attempted.

## 8. Consumer experience scorecard

The relevant consumer is a model/training integrator. Trust and correctness score `0/5` for the
reversed-input state because the API returns plausible data without an actionable error. All visual,
accessibility, navigation, and rendered-experience dimensions are `N/T`; this scoped recheck did not
launch a user interface.

## 9. Compatibility, accessibility, performance, and resilience

Windows CPython 3.13.15 was the only executed runtime. Accessibility and browser/desktop
compatibility were not applicable to the two public-kernel probes. Concurrency, 10,000-bar
performance, reversed test ordering, failure injection, and non-Windows compatibility are untested
because product testing stopped on the finding.

## 10. Blockers, assumptions, and blind spots

The direct blocker is the silent acceptance of nonchronological input at the exported kernel. The
expected typed outcome is derived from the kernel's documented oldest-first contract, QuantOS's
fail-closed financial-model laws, and the same module's `RECORD_ORDER_INVALID` behavior at the
training boundary. The principal blind spot is the 28-item halted matrix, especially real-runner
side effects and full regression.

## 11. Prioritized repair plan

No repair is authorized or performed by this independent run. The implementation owner should make
the public kernel reject or deterministically normalize nonchronological input, add a failing-first
public-API regression including duplicate dates, and then commission a fresh independent run of all
28 blocked items. The independent recheck must rerun this exact reproduction before the wider
matrix and full regression.

## 12. Approval request

Phase 1 stopped on a confirmed defect. No product repairs were made. Any repair phase requires
explicit authorization and must remain separate from this independent evidence.

## NOT PROBED

Every item below is **NOT TESTED** at `8f29564680c3563e8694ad486429c068242738ab` because the
reversed-kernel reproduction activated the required stop condition:

1. **NOT TESTED** — Final six-feature values for 21, 60, and 120 chronological bars.
2. **NOT TESTED** — Execution-score identity for 21, 60, and 120 chronological bars.
3. **NOT TESTED** — Training final-row identity across 21, 60, and 120 acquisition lengths.
4. **NOT TESTED** — Fewer-than-21 kernel/training/execution behavior.
5. **NOT TESTED** — Exactly-21 kernel and training behavior.
6. **NOT TESTED** — 22-bar one-bar trailing-window movement.
7. **NOT TESTED** — Execution exclusion of unavailable bars.
8. **NOT TESTED** — Training typed behavior for unavailable bars.
9. **NOT TESTED** — Execution normalization/refusal of out-of-order bars.
10. **NOT TESTED** — Duplicate-date behavior at kernel, training, and execution boundaries.
11. **NOT TESTED** — Pre-v2 and schema-less historical multiplicity reconstruction.
12. **NOT TESTED** — Schema-less model-identity construction refusal for execution.
13. **NOT TESTED** — Explicit schema-v1 execution-bundle refusal.
14. **NOT TESTED** — Model-publication resistance to v1/v2 relabelling.
15. **NOT TESTED** — Persisted-trial legacy/current schema reconstruction binding.
16. **NOT TESTED** — Feature-row/feature-dataset schema mismatch.
17. **NOT TESTED** — Persisted trial-start/feature-dataset schema mismatch.
18. **NOT TESTED** — Trial-start/model-publication schema mismatch.
19. **NOT TESTED** — Model-publication/execution-bundle missing, wrong-ID, wrong-version, and
    wrong-type schema fixtures.
20. **NOT TESTED** — Real evidence runner exact output and exit code against
    `tmp/real-training-evidence`.
21. **NOT TESTED** — Whether the real evidence runner creates any session or order side effect.
22. **NOT TESTED** — Repeated and concurrent feature/score determinism.
23. **NOT TESTED** — 10,000-bar retained-history identity and measured runtime.
24. **NOT TESTED** — All other ordinary mismatches and actionable typed outcomes.
25. **NOT TESTED** — Focused governed feature/schema/evidence pytest selection.
26. **NOT TESTED** — Full repository pytest suite.
27. **NOT TESTED** — Full pytest suite in reversed test-file order.
28. **NOT TESTED** — Ruff and strict Mypy.

Also not probed: provider failure injection, live credentials/providers, live broker routing,
authorization/tenancy, security exploit payloads, money-posting paths outside model multiplicity,
desktop/browser human journeys, non-Windows platforms, and production-scale behavior beyond the
unexecuted 10,000-bar target.
