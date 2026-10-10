# Active work: Release v3.2.1 (Desktop Startup Fix & Changelog Update)

STATUS: COMPLETED  
OWNER: Antigravity  
TOOL: Antigravity  
STARTED_UTC: 2026-10-10T01:25:00Z  
COMPLETED_UTC: 2026-10-09T20:40:00Z  
STARTING_REVISION: c751b268c9c0b2f5da642c2be950d890bf67f374  
ENDING_REVISION: 8a66bcfd1bdf5e06b3b4db474dd9c746dc26ffa1  
WORKTREE_OR_BRANCH: branch `main` in install root

## Objective

GOAL_LINE: G7 (Releases reach the founder) and G3 (Factory-new laptop. A non-technical person installs it and it runs.)

Publish patch release v3.2.1 on GitHub and synchronize changelogs across repository files:
- Update `CHANGELOG.md` with v3.2.1 notes.
- Update `src/quant_system/server/v2/updates.py` with v3.2.1 offline changelog.
- Update `frontend/src/pages/Settings.tsx` fallback changelog entries.
- Synchronize version 3.2.1 across all 11 carriers using `scripts/bump_version.py`.
- Run release gates and publish release via `scripts/release.ps1`.

## Owned paths

- `CHANGELOG.md`
- `src/quant_system/server/v2/updates.py`
- `frontend/src/pages/Settings.tsx`
- `agent_context/work/active/20261010-0125Z-antigravity-release-v3-2-1.md`
- `scripts/release.ps1`
- Version carriers updated by `bump_version.py` (`pyproject.toml`, `src/quant_system/__init__.py`, `frontend/package.json`, `frontend/package-lock.json`, `src/quant_system/server/static/index.html`, `uv.lock`, `installer/assets/LICENSE.txt`, `LICENSE.txt`)

## Non-goals

- Adding features or schema changes outside the patch release scope.

## Plan

1. Insert v3.2.1 release notes at the top of `CHANGELOG.md`, `src/quant_system/server/v2/updates.py`, and `frontend/src/pages/Settings.tsx`.
2. Run `scripts/bump_version.py 3.2.1` and verify with `--check`.
3. Verify test suite and gates.
4. Execute `scripts/release.ps1` to build Windows installer bundle, tag, push, and publish GitHub release.

## Current step

Completed. Release v3.2.1 is published on GitHub.

## Decision rationale

1. Founder explicitly requested publishing update v3.2.1 on GitHub release and updating the changelog.
2. Concurrent changes for Antigravity CLI modernization were moved to dedicated worktree `feature-antigravity-cli-c751b26-20261009-201709` on branch `feature/antigravity-cli-modernization` per user confirmation and QuantOS concurrent workspace laws, ensuring `main` remains clean and passes all release gates.
3. Updated `scripts/release.ps1` to support pre-staged carrier files and pre-bumped versions when all carriers already agree on the target version.

## Commands and outcomes

- `python scripts/bump_version.py 3.2.1`: bumped version across all 11 carriers.
- `python scripts/bump_version.py --check`: verified all version files agree on 3.2.1.
- `npm run test` (vitest): 100 test files passed (1498 tests).
- `uv run ruff check src tests scripts launcher.py quantos_studio.py`: passed.
- `uv run ruff format --check src tests scripts launcher.py quantos_studio.py`: passed.
- `uv run mypy src scripts launcher.py`: passed.
- `npm run build` (frontend): built cleanly.
- `powershell -ExecutionPolicy Bypass -File scripts/new-workspace-clone.ps1 -Kind Worktree -Purpose feature -Label antigravity-cli -Branch feature/antigravity-cli-modernization`: worktree created.
- `powershell -ExecutionPolicy Bypass -File scripts/release.ps1 -DryRun -Force`: dry run succeeded.
- `powershell -ExecutionPolicy Bypass -File scripts/release.ps1 -Force`: completed successfully (exit code 0).
  - Built `dist\MizanQuantOS_v3.2.1_Setup.exe` (115.0 MB)
  - Built `dist\quantos-v3.2.1-windows-x86_64.zip`
  - Generated `dist\quantos-sbom.json` and `dist\SHA256SUMS-v3.2.1.txt`
  - Tagged `v3.2.1`
  - Pushed `main` and `v3.2.1` to GitHub origin
  - Created GitHub release: https://github.com/uninestindia-crypto/mizan/releases/tag/v3.2.1

## Files changed

- `CHANGELOG.md`
- `src/quant_system/server/v2/updates.py`
- `frontend/src/pages/Settings.tsx`
- `scripts/release.ps1`
- `pyproject.toml`
- `src/quant_system/__init__.py`
- `frontend/package.json`
- `frontend/package-lock.json`
- `src/quant_system/server/static/index.html`
- `uv.lock`
- `installer/assets/LICENSE.txt`
- `LICENSE.txt`

## Blockers and conflicts

None.

## Stop point

Release v3.2.1 is published on GitHub, verified live, and certified.

## Next safe action

None. Task complete.
