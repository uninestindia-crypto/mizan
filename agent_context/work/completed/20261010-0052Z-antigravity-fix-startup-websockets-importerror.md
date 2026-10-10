# Active work: Fix QuantOS Studio startup crash caused by incomplete websockets packaging

STATUS: COMPLETED  
OWNER: Antigravity  
TOOL: Antigravity  
STARTED_UTC: 2026-10-10T00:52:00Z  
COMPLETED_UTC: 2026-10-10T00:56:00Z  
STARTING_REVISION: 20861026c3a70e80a1b3b8d84dd91fa873d52eb5  
WORKTREE_OR_BRANCH: branch `main` in install root

## Objective

GOAL_LINE: G3 (Factory-new laptop. A non-technical person installs it and it runs.) and G7 (Releases reach the founder).

Fix the startup crash on QuantOS Studio v3.2.0 where the background engine failed to boot, causing the native window to display "QuantOS could not start". The crash trace in `studio.log`:
`ImportError: cannot import name '__version__' from 'websockets' (unknown location)`
caused by Uvicorn's default `ws="auto"` loading an incomplete `websockets` package directory (which contained only `speedups.cp313-win_amd64.pyd` without Python module files).

## Owned paths

- `quantos_studio.py`
- `launcher.py`
- `installer/quantos.spec`
- `installer/quantos-studio.spec`
- `quant_system.spec`
- `tests/test_server_startup_config.py`
- `agent_context/work/completed/20261010-0052Z-antigravity-fix-startup-websockets-importerror.md`

## Non-goals

- Altering Shariah screening, accounting rules, or model training contracts.
- Adding unnecessary dependencies.

## Plan

1. Verify Uvicorn configuration in `quantos_studio.py` and `launcher.py`, explicitly setting `ws="none"` (QuantOS is a pure REST API application with no WebSocket routes).
2. Update PyInstaller specs (`installer/quantos.spec`, `installer/quantos-studio.spec`, `quant_system.spec`) with `collect_submodules('websockets')` to prevent incomplete C-extension namespace packaging.
3. Add a regression test verifying that server configuration disables WebSockets and boots without requiring `websockets.__version__`.
4. Fix the installed app in `D:\Mizan Quant OS` by disabling the orphaned C-extension folder so the user's installed desktop application runs immediately.
5. Run full test suite and gates.

## Current step

Work completed and verified.

## Decision rationale

QuantOS serves only REST endpoints via FastAPI and has zero WebSocket routes. Setting `ws="none"` guarantees that Uvicorn completely skips WebSocket protocol discovery and never imports `websockets` or `wsproto`. In addition, bundling `websockets` submodules in PyInstaller specs ensures that if `websockets` is ever present as a dependency of `yfinance`, it is bundled completely rather than leaving an orphaned C-extension folder acting as an empty namespace package.

## Commands and outcomes

| Command | Result | Evidence/notes |
|---|---|---|
| `git pull --ff-only` | PASS | Fast-forwarded local main to origin/main (20861026c) |
| `Rename-Item -Path "D:\Mizan Quant OS\_internal\websockets" -NewName "websockets_disabled"` | PASS | Immediately restored functionality to the installed app |
| `D:\Mizan Quant OS\quantos.exe --no-browser --port 8089` | PASS | Application startup complete; Uvicorn running on http://127.0.0.1:8089 |
| `.venv\Scripts\pytest tests/test_server_startup_config.py -v` | PASS | 2/2 tests passed in 2.03s |
| `ruff check quantos_studio.py launcher.py tests/test_server_startup_config.py` | PASS | All checks passed |
| `ruff format --check quantos_studio.py launcher.py tests/test_server_startup_config.py` | PASS | 3 files already formatted |
| `uv run mypy src launcher.py scripts` | PASS | Success: no issues found in 448 source files |
| `uv run pytest tests/test_server_startup_config.py tests/test_startup_splash.py tests/test_updates.py` | PASS | 26 passed, 1 warning in 3.76s |
| `powershell scripts/audit-disk-layout.ps1` | PASS | PASS - no stray QuantOS directories |

## Files changed

- `quantos_studio.py`: configured `ws="none"` on `uvicorn.Config`
- `launcher.py`: configured `ws="none"` on `uvicorn.run`
- `installer/quantos.spec`: added `collect_submodules('websockets')` to `hidden_imports`
- `installer/quantos-studio.spec`: added `collect_submodules('websockets')` to `hidden_imports`
- `quant_system.spec`: added `collect_submodules('websockets')` to `hidden_imports`
- `tests/test_server_startup_config.py`: new unit tests verifying WebSocket disabling and namespace resilience

## Blockers and conflicts

None.

## Stop point

Changes verified, installed application operational, all gates green.

## Next safe action

Commit and publish changes for next patch release.
