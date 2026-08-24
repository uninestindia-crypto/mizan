# Work record: governed feature-window independent QA retry at 81f4f1b

STATUS: HALTED_ON_FINDING

OWNER: Codex independent Red Team retry

STARTED_UTC: 2026-08-24T11:00:18Z

STARTING_REVISION: `81f4f1be41b54421e0d2f845c086dd791fb88889`

WORKSPACE: `D:\quant_system_workspaces\verification_clones\redteam-governed-feature-window-retry-codex-81f4f1b-20260824-110126`

SCRATCH: `D:\quant_system_workspaces\scratch\qa-governed-feature-window-retry-81f4f1b-20260824-codex`

## Objective and outcome

Independently recheck the governed feature-window repair through public APIs without modifying
product source or existing tests. The first corrected product probe reproduced a silent Blocker:
`evaluate_governed_ridge_fold` accepted a schema-v1 trial start with a schema-v2 feature dataset
and returned a model ID and evaluation hash. Testing stopped under the user's explicit condition.

## Owned artifacts

- `.launch/reports/RED-TEAM-GOVERNED-FEATURE-WINDOW-RECHECK-RETRY.md`
- This completed work record
- The exact workspace and scratch paths above

## Conflicts preserved

The stopped agent's active record
`agent_context/work/active/20260824-codex-socrates-redteam-feature-window-81f4f1b.md` and every path
it claims were left untouched. No other agent artifact was staged, edited, removed, or adopted.

## Commands and evidence

- Canonical clone script created the exact detached verification clone.
- `uv sync --frozen --extra dev --link-mode copy` exited `0`.
- Corrected public API probe exited `0` and returned
  `model_1f225af58a4e19d614e4c852` plus evaluation hash
  `1f225af58a4e19d614e4c852e737a7a5616da48551e455aa28c9233abc5a21c7` despite schema versions
  `1` and `2`.
- Runtime log and machine-readable coverage ledger remain in the owned scratch path.
- No product source or existing test was changed.
- No command was running or stuck at retirement.

## Stop point and next safe action

The revision is blocked at the exported evaluator's trial/dataset schema boundary. Repair must be
performed independently, followed by a fresh clean-clone recheck of all 30 explicitly untested
items listed in the retry report.
