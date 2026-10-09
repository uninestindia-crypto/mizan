# Active work: Sync remote feature branches into main and cut release v3.1.0

STATUS: ACTIVE  
OWNER: Antigravity, founder session  
TOOL: Antigravity  
STARTED_UTC: 2026-10-09T13:10:00Z  
STARTING_REVISION: `09cfa6b0a4bd15a54a88b82095f558556a33fa1e`  
WORKTREE_OR_BRANCH: the install root, branch `main`.

## Objective

GOAL_LINE: G2 (One unified application, two modes), G3 (Factory-new laptop), G7 (Releases reach the founder).

Founder instruction, 2026-10-09: "option B i want that so the updated work can be realesed on github as new version 3.1"
Synchronize all completed remote branches (`claude/dazzling-brown-yn5qu3` [PR #5: Kronos trial 11] and
`claude/wonderful-wozniak-6ek6zl` [Shariah mode, filing proofs, local Copilot chats, AI settings, updater])
along with local completed Broker View Phase 1 into `main`, resolve all merge conflicts, pass all verification
gates, and cut release v3.1.0 via `scripts/release.ps1`.

## Owned paths

- `agent_context/work/active/20261009-1310Z-antigravity-sync-branches-and-release-v3.1.md`
- Conflicted reconciliation paths in `frontend/`, `src/quant_system/server/v2/`, `installer/`, `scripts/`, `tests/`
- Release metadata and changelog for v3.1.0

## Non-goals

- Re-running or altering already-declared Kronos trials.
- Overwriting or breaking the cloud paper trading setup.
- Modifying remote branch pointers destructively (no force pushes).

## Plan

1. Safely snapshot and preserve current uncommitted local changes (Broker View Phase 1 & Qlib riskmodel) on a dedicated branch `feature/broker-view-phase1-and-qlib`.
2. Merge `origin/claude/dazzling-brown-yn5qu3` (PR #5) into `main` (0 conflicts verified).
3. Merge `origin/claude/wonderful-wozniak-6ek6zl` into `main`, resolving all 17 conflicting files cleanly and preserving both v3.0.0 features (Quant-SLM, hardware acceleration, window lifecycle) and wozniak features (Shariah mode, filing proof, in-app updater, AI provider choices, local copilot history).
4. Integrate local Broker View Phase 1 and Qlib riskmodel.
5. Run full gate suite: Ruff, strict Mypy, Pytest, frontend Vitest/typecheck, secret scan, audit scripts.
6. Cut release v3.1.0 with `scripts/release.ps1 -Version 3.1.0`.
