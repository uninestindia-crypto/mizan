# Red Team governed feature-window recheck retry

Revision: `81f4f1be41b54421e0d2f845c086dd791fb88889`

Result: BLOCKED by one reproduced silent correctness failure.

Verification clone: `D:\quant_system_workspaces\verification_clones\redteam-governed-feature-window-retry-codex-81f4f1b-20260824-110126`

External evidence: `D:\quant_system_workspaces\scratch\qa-governed-feature-window-retry-81f4f1b-20260824-codex`

FINDING   Exported governed ridge evaluator silently accepts a schema-v1 trial with a schema-v2 feature dataset

FAMILY    Data integrity; Assumption archaeology

REPRO     From PowerShell, run the retained public-API probe against the clean detached clone:

```powershell
Set-Location 'D:\quant_system_workspaces\verification_clones\redteam-governed-feature-window-retry-codex-81f4f1b-20260824-110126'
$env:PYTHONPATH='src;.'
.\.venv\Scripts\python.exe 'D:\quant_system_workspaces\scratch\qa-governed-feature-window-retry-81f4f1b-20260824-codex\probe_schema_evaluator_mismatch.py'
```

The probe obtains `governed_training_journey()`, uses `dataclasses.replace` to change only
`journey.start.feature_schema_version` from `2` to the public
`FEATURE_SCHEMA_VERSION_V1`, constructs the corresponding public `TrialRegistryV1`, and calls
the exported `quant_system.modeling.evaluate_governed_ridge_fold` with the unchanged schema-v2
feature dataset, labels, and fold.

OBSERVED  Exit code `0`; no exception. Raw stdout:

```json
{
  "actual": "evaluation accepted",
  "evaluation_hash": "1f225af58a4e19d614e4c852e737a7a5616da48551e455aa28c9233abc5a21c7",
  "feature_dataset_schema": [
    "quantos.ridge_technical_six",
    2
  ],
  "model_id": "model_1f225af58a4e19d614e4c852",
  "trial_schema": [
    "quantos.ridge_technical_six",
    1
  ]
}
```

EXPECTED  A typed `ModelingError` with `TRAINING_INPUT_MISMATCH` before fitting, with no
evaluation hash or model identity returned. Schema identity is required to agree between trial
start and feature dataset at every public governed boundary.

BLAST     Any direct caller of the exported evaluator can silently obtain a governed-looking
evaluation, model ID, fitted state, metrics, and evaluation hash from incompatible trial and
feature-dataset schema identities. Later checks in the persisted-trial/publication path do not
erase the already returned in-memory result. Affected paths are
`src/quant_system/modeling/validation.py:92` and
`src/quant_system/modeling/validation.py:210`; the API is exported from
`src/quant_system/modeling/__init__.py:107` and `:182`. The repair added the omitted comparison
only to `src/quant_system/modeling/training_evidence.py:103` and `:182`, downstream of this
public evaluator boundary.

SEVERITY  Blocker

## Exact commands and outcomes

- `git status --short --branch` in the install root reported `main...origin/main`, one modified
  work record, and multiple untracked records/reports owned by other agents. None were edited,
  staged, removed, or used.
- `git rev-parse HEAD` returned
  `81f4f1be41b54421e0d2f845c086dd791fb88889`.
- `git worktree list` and `git branch --list` were run during startup; every listed workspace and
  non-default branch was treated as live.
- Every install-root active record was read. The stopped record
  `agent_context/work/active/20260824-codex-socrates-redteam-feature-window-81f4f1b.md` was
  recorded as a conflict. Its paths were not entered, edited, adopted, retired, moved, or removed.
- Clone command:

  ```powershell
  powershell -ExecutionPolicy Bypass -File scripts/new-workspace-clone.ps1 -Purpose redteam -Label governed-feature-window-retry-codex -Revision 81f4f1be41b54421e0d2f845c086dd791fb88889
  ```

  Exit code `0`; created the detached clone named above at the exact revision.
- Environment command: `uv sync --frozen --extra dev --link-mode copy`. Exit code `0`; resolved
  and installed 47 packages with Python 3.13.15, including `quant-system==1.0.0` from the clone.
- Structural discovery inventoried 564 repository files and 30 requested QA targets before the
  evaluator-specific target was added.
- The first probe invocation omitted `PYTHONPATH`, exited `1` at import with
  `ModuleNotFoundError` for the test fixture package, and did not reach product code. This was a
  harness error and is not the finding.
- Corrected product command:

  ```powershell
  $env:PYTHONPATH='src;.'; .\.venv\Scripts\python.exe 'D:\quant_system_workspaces\scratch\qa-governed-feature-window-retry-81f4f1b-20260824-codex\probe_schema_evaluator_mismatch.py'
  ```

  Exit code `0`; raw stdout is reproduced in the finding. Raw log:
  `D:\quant_system_workspaces\scratch\qa-governed-feature-window-retry-81f4f1b-20260824-codex\evidence\logs\schema-evaluator-mismatch.log`.
- Evidence-ledger raw summary after the stop condition: `Inventory items: 31`,
  `Audit completion: 100.00%`, `Verified coverage: 0.00%`,
  `Status counts: not_started=0, in_progress=0, passed=0, failed=1, blocked=30`,
  `Run milestones: 3/7`. “Audit completion” here means every item has an explicit terminal ledger
  disposition; it does not mean verified coverage.
- No command was running or stuck at finalization. No process was terminated.

COVERAGE  Families run: 8 (data integrity) and 12 (assumption archaeology). Probes attempted: one
harness invocation that did not reach product code and one corrected public-API execution. Runtime
target: `quant_system.modeling.evaluate_governed_ridge_fold`. Source targets inspected:
feature construction, training rows, trial/evidence reconstruction, publication binding,
execution bundle/strategy, runner, the exact repair diff, and existing focused tests. Runtime
result: one Blocker; 0% verified target coverage because the user-required stop condition prevented
the remaining 30 targets from running.

## NOT PROBED

Every item below is **NOT TESTED** at this revision because the first product probe reproduced a
correctness failure and the user required the run to stop rather than continue or repair:

1. **NOT TESTED** — Final six-feature values are byte-identical for 21, 60, and 120 chronological bars.
2. **NOT TESTED** — Execution score is byte-identical for 21, 60, and 120 chronological bars.
3. **NOT TESTED** — Training final row uses the same trailing 21 observations across acquisition lengths.
4. **NOT TESTED** — Fewer than 21 bars fails or abstains with the documented typed outcome.
5. **NOT TESTED** — Exactly 21 bars computes one canonical feature vector.
6. **NOT TESTED** — One bar above minimum advances the trailing window by exactly one bar.
7. **NOT TESTED** — Execution excludes unavailable bars before selecting the trailing 21.
8. **NOT TESTED** — Training handles unavailable bars with explicit point-in-time semantics.
9. **NOT TESTED** — Execution ordering produces deterministic chronological trailing-window behavior.
10. **NOT TESTED** — Public feature kernel handles non-chronological input safely.
11. **NOT TESTED** — Duplicate exchange dates fail closed at governed public boundaries.
12. **NOT TESTED** — Pre-v2 and schema-less persisted evidence remains readable for historical multiplicity.
13. **NOT TESTED** — Schema-less model identity construction fails closed for execution.
14. **NOT TESTED** — Explicit schema-v1 model evidence is rejected by the execution bundle.
15. **NOT TESTED** — Current publication cannot relabel a v2 evaluation as legacy or vice versa.
16. **NOT TESTED** — Persisted-trial reconstruction binds legacy/current model schema to its trial.
17. **NOT TESTED** — Feature row and feature dataset schema identities agree.
18. **NOT TESTED** — Persisted trial entry rejects feature-dataset/trial-start schema disagreement.
19. **NOT TESTED** — Trial start and model publication schema identities agree.
20. **NOT TESTED** — Published model schema identity agrees with execution bundle requirements.
21. **NOT TESTED** — Real evidence runner gives exact legacy-schema refusal and stable exit code.
22. **NOT TESTED** — Real evidence runner creates no session or order side effect; whether any session
    or order would be created by this revision was not established.
23. **NOT TESTED** — Repeated and concurrent feature/score calls are deterministic.
24. **NOT TESTED** — A 10,000-bar retained history remains bounded to the canonical 21-bar calculation.
25. **NOT TESTED** — All other ordinary mismatches yield actionable typed outcomes without silent fallback.
26. **NOT TESTED** — Focused governed feature/schema/evidence pytest selection.
27. **NOT TESTED** — Full repository pytest suite.
28. **NOT TESTED** — Full pytest suite in reversed test-file order.
29. **NOT TESTED** — Ruff and strict Mypy.
30. **NOT TESTED** — Repository agent-claims and disk-layout audits at finalization.

Failure injection beyond the ordinary mismatch, authorization/tenancy, concurrent mutations,
state-machine misuse, money/counting paths outside model multiplicity, security payloads, human UI
flows, production-scale datasets beyond the listed 10,000-bar target, live providers, live broker
routing, and non-Windows platforms were also not tested.
