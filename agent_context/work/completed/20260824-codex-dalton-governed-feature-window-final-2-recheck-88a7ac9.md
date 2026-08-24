# Retired work: governed feature-window final-2 independent recheck at 88a7ac9

STATUS: RETIRED

OWNER: Codex / Dalton independent Red Team

TOOL: Codex

STARTED_UTC: 2026-08-24T12:00:00Z

ENDING_REVISION_TESTED: `88a7ac988114267a0d44203587a57b680717bf3b`

WORKTREE_OR_BRANCH: detached canonical clone at
`D:\quant_system_workspaces\verification_clones\redteam-governed-feature-window-final-2-dalton-88a7ac9-20260824-113944`;
no branch.

ARTIFACT_DIRECTORY:
`D:\quant_system_workspaces\scratch\qa-governed-feature-window-final-2-88a7ac9-20260824-codex-dalton`

## Objective

Independently recheck exact repair revision `88a7ac988114267a0d44203587a57b680717bf3b`.
First rerun the evaluator schema mismatch and reversed-kernel reproductions, then execute all 28
follow-up public API, legacy evidence, runner, determinism, scale, regression, static, and
repository-audit targets.

## Owned paths

- `agent_context/work/active/20260824-codex-dalton-governed-feature-window-final-2-recheck-88a7ac9.md`
  (retired by this record)
- `agent_context/work/completed/20260824-codex-dalton-governed-feature-window-final-2-recheck-88a7ac9.md`
- `.launch/reports/RED-TEAM-GOVERNED-FEATURE-WINDOW-RECHECK-FINAL-2.md`
- `D:\quant_system_workspaces\scratch\qa-governed-feature-window-final-2-88a7ac9-20260824-codex-dalton\**`
- `D:\quant_system_workspaces\verification_clones\redteam-governed-feature-window-final-2-dalton-88a7ac9-*\**`

## Non-goals honored

- No product-source or existing-test edits, repairs, formatting, staging, or commits.
- No reuse, editing, adoption, retirement, deletion, movement, or execution inside any prior
  record, report, clone, or scratch path.
- No model promotion, relabelling, live provider mutation, broker route, or broker write.
- No staging or commit of another agent's modified, untracked, branch, worktree, or report artifact.

## Plan outcome

1. Repository/skill startup, active claims, release state, quarantine policy, worktrees, branches,
   and dirty paths were read.
2. Unique canonical clone and external evidence ledger were created after the visible claim.
3. Both prior reproductions returned the required typed errors without identities/feature values.
4. All 28 follow-up items were executed; no requested correctness issue was reproduced.
5. Focused/full/reversed pytest, Ruff, Mypy, real runner, and both audits were executed.
6. The unique report was written and this record alone was retired.

## Commands and outcomes

| Command | Exit | Outcome |
|---|---:|---|
| `new-workspace-clone.ps1 -Purpose redteam -Label governed-feature-window-final-2-dalton -Revision 88a7ac9...` | 0 | Exact detached clone created. |
| `uv sync --frozen --extra dev --link-mode copy` | 0 | Locked dev environment created. |
| Fresh evaluator reproduction | 0 | `TRAINING_INPUT_MISMATCH`; no evaluation/model identity. |
| Fresh reverse-kernel reproduction | 0 | `RECORD_ORDER_INVALID`; no feature vector. |
| Fresh window/boundary probe | 0 | All assertions observed, including 21/60/120 identity, 20/21/22, availability, order, duplicates, concurrency, and 10,000-bar kernel/strategy scale. |
| Fresh schema/evidence probe | 0 | Coherent legacy multiplicity readable; all current/legacy execution and binding mismatches refused with typed outcomes. |
| `run_governed_shadow_session.py --evidence-root D:\quant_system\tmp\real-training-evidence` | 3 | Missing schema identity refused; no session/order; evidence tree unchanged. |
| Focused pytest | 0 | `114 passed in 4.19s`. |
| Full pytest | 0 | `869 passed, 1 warning in 56.60s`. |
| Reversed 71-file pytest | 0 | `869 passed, 1 warning in 46.14s`. |
| `ruff check .` | 0 | No lint finding. |
| `mypy src scripts/run_governed_shadow_session.py` | 0 | No issue in 122 source files. |
| `audit-agent-claims.ps1` | 0 | Claims resolved. |
| `audit-disk-layout.ps1` | 0 | Canonical layout retained. |

## Files changed

- `.launch/reports/RED-TEAM-GOVERNED-FEATURE-WINDOW-RECHECK-FINAL-2.md`
- `agent_context/work/completed/20260824-codex-dalton-governed-feature-window-final-2-recheck-88a7ac9.md`
- External scratch evidence and probes under the unique artifact directory.

Product source and existing tests changed by this reviewer: none.

## Decision rationale

Runtime evidence came only from the exact detached revision. Ordinary mismatched fixtures were used
at public boundaries. The real evidence store was read directly with before/after hashes because the
runner is read-only and its no-session/no-order claim required side-effect evidence.

## Blockers and conflicts

- No blocker remains for the requested matrix.
- Prior stopped and active records/workspaces remain untouched.
- The install root still contains unrelated modified/untracked work owned by other agents; none was
  staged or committed here.

## Stop point

Report written, 30-item audit ledger terminal with no failed/blocked item, unique active record
retired, product/tests unchanged.

## Next safe action

Read `.launch/reports/RED-TEAM-GOVERNED-FEATURE-WINDOW-RECHECK-FINAL-2.md`. Any expansion into live
feeds, promoted current evidence, paper/live ordering, alternate platforms, or a 10,000-row governed
training acquisition requires a new uniquely claimed scope.
