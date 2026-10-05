# Completed work: Remove classic console link and implement comprehensive in-app changelog

STATUS: COMPLETED  
OWNER: Antigravity  
TOOL: Antigravity  
STARTED_UTC: 2026-10-05T14:55:00Z  
COMPLETED_UTC: 2026-10-05T15:10:00Z  
STARTING_REVISION: 05fc70dea5e68cce24dc2140b76b868f6fb3a51b  
WORKTREE_OR_BRANCH: D:/Quant OS Project/Mizan (main)

## Objective

1. Scrap and remove the "Open the classic research console (advanced, for developers)" link and classic console references from the user-facing application (specifically `frontend/src/pages/Settings.tsx`).
2. Implement a comprehensive in-app Changelog ("everything shown what updated and what not") displaying version release history, what's new (features), fixes, improvements, and architectural boundaries/protections (what's unchanged / not updated).
3. Ensure offline-first self-contained functionality bundled with release history (v2.3.0, v2.2.0, v2.1.0, v2.0.1, v2.0.0, etc.) with real-time update notifications when newer releases are published.

## Owned paths

- `agent_context/work/completed/20261005-antigravity-remove-classic-link-and-add-changelog.md`
- `frontend/src/pages/Settings.tsx`
- `frontend/src/lib/types.ts`
- `frontend/src/lib/queries.ts`
- `src/quant_system/server/v2/router.py`
- `src/quant_system/server/v2/updates.py`
- `tests/test_updates.py`

## Non-goals

- Deleting `/classic` backend route completely if required by existing headless verification tests (keep backend route for compatibility, but eliminate it from all user-facing navigation).
- Breaking any existing API v1 or v2 contracts.

## Plan

1. Verify git clean status and active claims. [DONE]
2. Implement `/api/v2/changelog` in `src/quant_system/server/v2/updates.py` and `src/quant_system/server/v2/router.py`. [DONE]
3. Update `frontend/src/lib/types.ts` and `frontend/src/lib/queries.ts` with `ChangelogEntry` and `useChangelog()`. [DONE]
4. Update `frontend/src/pages/Settings.tsx`:
   - Scrapped and removed `[Open the classic research console (advanced, for developers)](http://127.0.0.1:8080/classic)`. [DONE]
   - Replaced classic console text references in AI settings. [DONE]
   - Added rich `ChangelogCard` displaying release versions, categories (What's new, Fixes, Improvements, Unchanged safeguards). [DONE]
5. Build frontend (`npm run build`). [DONE]
6. Run test suite, linters, and verification checks. [DONE]
7. Record completion. [DONE]

## Decision rationale

Users need full transparency into what is updated across versions without navigating to external sites when offline, while maintaining clean presentation of what was added, what was fixed, and what was intentionally preserved/not updated (such as fail-closed safety invariants, zero broker order routing, and Decimal accounting).

## Commands and outcomes

| Command | Result | Evidence/notes |
|---|---|---|
| `git status --short --branch` | PASS | Clean branch at 05fc70dea5e68cce24dc2140b76b868f6fb3a51b |
| `python scripts/release_status.py` | PASS | 0 of 3 user-visible changes since v2.3.0 |
| `.venv\Scripts\pytest.exe tests/test_updates.py` | PASS | 10 passed in 2.15s (including changelog unit and integration tests) |
| `.venv\Scripts\pytest.exe tests/test_v2_api.py tests/test_updates.py` | PASS | 32 passed in 6.51s |
| `.venv\Scripts\pytest.exe tests/test_ui_journeys.py` | PASS | 32 passed in 1.82s |
| `npm run build` | PASS | tsc type check and vite build clean in 700ms |
| `.venv\Scripts\ruff.exe check src launcher.py scripts` | PASS | All checks passed |
| `.venv\Scripts\ruff.exe format --check src launcher.py scripts tests` | PASS | 465 files already formatted |
| `.venv\Scripts\mypy.exe src launcher.py scripts` | PASS | Success: no issues found in 297 source files |

## Files changed

- `src/quant_system/server/v2/updates.py`: Added `OFFLINE_CHANGELOG` and `changelog()` method on `UpdateChecker`.
- `src/quant_system/server/v2/router.py`: Registered `/api/v2/changelog` endpoint.
- `tests/test_updates.py`: Added tests for changelog logic and endpoint.
- `frontend/src/lib/types.ts`: Added `ChangelogEntry` interface.
- `frontend/src/lib/queries.ts`: Added `useChangelog()` query hook.
- `frontend/src/pages/Settings.tsx`: Removed classic research console link and developer reference; added comprehensive `ChangelogCard` showing what was updated and what was preserved across versions.
- `src/quant_system/server/static/app/`: Rebuilt production UI assets.

## Blockers and conflicts

None.

## Stop point

Work complete; tests passing; bundle built; gates green.

## Next safe action

Ready for user verification or launch.
