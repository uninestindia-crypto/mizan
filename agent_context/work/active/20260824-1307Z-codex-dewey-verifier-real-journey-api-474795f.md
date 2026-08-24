# Active work: independent final real-journey API verification at 474795f

STATUS: ACTIVE  
OWNER: Codex / Dewey Release Verification  
TOOL: Codex  
STARTED_UTC: 2026-08-24T13:07:00Z  
STARTING_REVISION: `3d003e724b9bcfd963d655377a05ff6ed11bd289`  
TARGET_REVISION: `474795f3ad6287bdec3b7deaa677a54b537f28c7`  
WORKTREE_OR_BRANCH: detached canonical verification clone to be created at
`D:\quant_system_workspaces\verification_clones\verify-real-journey-api-final-474795f-20260824-130801`;
no branch.

SCRATCH_PATH:
`D:\quant_system_workspaces\scratch\qa-real-journey-api-474795f-20260824-codex-dewey`

REPORT_PATH:
`D:\quant_system\agent_context\reports\20260824-dewey-verifier-real-journey-api-474795f.md`

## Objective

Independently certify exact remote revision `474795f3ad6287bdec3b7deaa677a54b537f28c7`
on `codex/real-journey-api` from a fresh canonical detached clone. Adjudicate all fourteen targets
in `agent_context/handoffs/20260824-real-journey-api-recheck.md`, reproduce the concrete failures
from both prior verifier reports on the new head, run every required clean-state/static/runtime/
browser/repository gate, preserve raw evidence, and return PASS or BLOCKED without repair.

## Owned paths

- `agent_context/work/active/20260824-1307Z-codex-dewey-verifier-real-journey-api-474795f.md`
- `agent_context/work/completed/20260824-1307Z-codex-dewey-verifier-real-journey-api-474795f.md`
- `agent_context/reports/20260824-dewey-verifier-real-journey-api-474795f.md` (new)
- `D:\quant_system_workspaces\verification_clones\verify-real-journey-api-final-474795f-20260824-130801\**`
- `D:\quant_system_workspaces\scratch\qa-real-journey-api-474795f-20260824-codex-dewey\**`

This verifier owns no product source, existing test, dependency, lockfile, branch, campaign,
modeling, execution, runtime evidence, launch-state, handoff, decision, or other agent path.

## Non-goals

- No product or existing-test edits, fixes, formatting, staging, commits, merges, rebases, branch
  changes, workspace removal, or repair suggestions.
- No writes to modeling, execution, the NIFTY50/schema-v2 campaign or its runtime artifacts, or any
  other agent's record, report, worktree, clone, scratch root, or owned path.
- No provider credential use, live-money action, model promotion, training, or broker write.
- No reuse of prior verifier outcomes as current evidence.

## Plan

1. COMPLETE - complete required startup, command discovery, dirty-path inspection, and create
   the exact predeclared canonical clone and scratch ledger.
2. COMPLETE - prove authoritative remote branch and detached clone identity; clear ambient state;
   perform a frozen fresh dependency install.
3. IN PROGRESS - independently rerun all fourteen handoff targets and both prior reports' concrete
   public-boundary failures, including restart durability, cancellation races, and chart rendering.
4. PENDING - run focused 127, full 903 normal/reverse, Ruff, format, Mypy 125, Node, OpenAPI,
   changed-path security/secrets, Git, claim, and layout gates.
5. PENDING - browser-inspect 1280x720 and 390x844 light/dark, run one real local backtest, and
   recheck native chart rendering, page overflow, control sizes, console, and security logs.
6. PENDING - write the immutable report, retire this record, run final audits, and return PASS or
   BLOCKED.

## Current step

Run full pytest in normal and reverse file order after the clean focused suite passed 127 tests.

## Decision rationale

The install root is dirty with active server, release, feature-window, and runtime training work,
and two live worktrees/branches are registered. A unique detached clone plus unique external
scratch evidence prevents stale state and concurrent work from contaminating certification.

## Commands and outcomes

| Command | Result | Evidence/notes |
|---|---|---|
| Required AGENTS startup sequence | COMPLETE | Read required context/release/protocol/layout files, all active records, every dirty path, worktrees, and branches. |
| Launch-readiness recorder self-test | UNUSABLE | Failed 5/16 because `/bin/bash` is unavailable; repository-native commands and raw logs will be used. |
| `git status --short --branch` | DIRTY, PRESERVED | Sixteen untracked paths, all treated as other agents' work. |
| `git worktree list` / `git branch --list` | INSPECTED | Two live feature worktrees/branches plus install-root main; all left untouched. |
| `new-workspace-clone.ps1 -Purpose verify -Label real-journey-api-final -Revision 474795f...` | CREATED | Script emitted canonical detached clone `...-20260824-130801`; its timestamp was one second later than the planned `130800`, so this claim was corrected before any clone-local task command. |
| Authoritative `git ls-remote`; detached checkout identity | EXACT | Remote branch and clone HEAD both `474795f3ad6287bdec3b7deaa677a54b537f28c7`; detached, clean. |
| `uv sync --frozen --extra dev --link-mode copy` | PASS | Fresh `.venv`; 47 packages, uv 0.12.5, CPython 3.13.15. |
| Focused server/API/UI suite | PASS | 127 passed, one third-party warning in 40.02s. |

## Files changed

- This active work record only.

## Blockers and conflicts

None. Every owned path is unique and disjoint; product source remains read-only.

## Stop point

Clean clone, scratch ledger, frozen environment, and focused suite complete.

## Next safe action

Run the full normal/reverse suites, then all public-boundary and browser checks.
