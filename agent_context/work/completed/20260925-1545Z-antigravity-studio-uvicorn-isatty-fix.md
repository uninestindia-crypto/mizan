# Active work: QuantOS Studio zero-console uvicorn isatty crash fix

STATUS: COMPLETED  
OWNER: Antigravity  
TOOL: Antigravity  
STARTED_UTC: 2026-09-25T15:45:00Z  
COMPLETED_UTC: 2026-09-25T15:52:00Z  
STARTING_REVISION: c270017b3b6a9d8130ad57d157886985ca4f70d5  
WORKTREE_OR_BRANCH: D:\quant_system on main; shared checkout with disjoint claims

## Objective

Fix the `AttributeError: 'NoneType' object has no attribute 'isatty'` / `ValueError: Unable to configure formatter 'default'` crash when launching `quantos_studio.py` in zero-console / windowed / pythonw mode where `sys.stdout` and `sys.stderr` are `None`.

## Owned paths

- `agent_context/work/completed/20260925-1545Z-antigravity-studio-uvicorn-isatty-fix.md`
- `quantos_studio.py`
- `tests/test_quantos_studio.py`

## Non-goals

- No live-money routing or changes to trading logic.
- No modifications to financial models or risk governors.
- No changes to repository-wide logging outside QuantOS Desktop Studio host.

## Plan

1. Reproduce the exact crash when `sys.stdout` and `sys.stderr` are `None`. [COMPLETED]
2. Implement safe standard stream initialization in `quantos_studio.py` ensuring `sys.stdin`, `sys.stdout`, and `sys.stderr` are never `None`, providing `isatty()`, `write()`, and `flush()` capabilities, and redirecting studio console output to `logs/studio_stdio.log` or safe null streams. [COMPLETED]
3. Configure `uvicorn.Config` in `quantos_studio.py` with `log_config=None` so uvicorn does not attempt to instantiate colorized console stream handlers against `sys.stdout`/`sys.stderr`. [COMPLETED]
4. Route uvicorn and app loggers to the dedicated file logger in `setup_studio_logging`. [COMPLETED]
5. Add unit tests in `tests/test_quantos_studio.py` verifying that `quantos_studio` safely initializes streams and configures uvicorn when `sys.stdout` and `sys.stderr` are `None`. [COMPLETED]
6. Run `pytest tests/test_quantos_studio.py` and run linter/type checks (`ruff check`, `mypy`). [COMPLETED]

## Current step

Work completed. All unit tests, packaging tests, static typing, and layout audits verified green.

## Decision rationale

In Windows GUI/windowed mode (`pythonw.exe` or PyInstaller `console=False`), the operating system runs the process without a console, leaving `sys.stdout = None` and `sys.stderr = None`.
Uvicorn's `DefaultFormatter` (`ColourizedFormatter`) checks `sys.stdout.isatty()`, raising `AttributeError: 'NoneType' object has no attribute 'isatty'` which causes `logging.config.dictConfig` to fail with `ValueError: Unable to configure formatter 'default'`.
Furthermore, standard `logging.StreamHandler()` and any `print()` statement will fail if `sys.stdout` or `sys.stderr` is `None`.
Fixes implemented:
1. Created `NullStream` class implementing `write()`, `writelines()`, `read()`, `readline()`, `flush()`, `isatty() -> False`, and `encoding="utf-8"`.
2. Created `ensure_safe_std_streams(app_root=None)` and invoked it at module import, in `configure_drive_isolation()`, in `run_studio()`, and in `__main__`. When `app_root` is available, standard output and errors are captured cleanly in `app_root / "logs" / "studio_stdio.log"`.
3. Configured `uvicorn.Config` with `log_config=None` and `use_colors=False` in `quantos_studio.py`, preventing uvicorn from executing default console `dictConfig`.
4. Enhanced `setup_studio_logging(app_root)` to ensure `app_root / "logs"` exists and attached the studio file handler to `uvicorn`, `uvicorn.error`, and `uvicorn.access`.
5. Added comprehensive regression tests in `tests/test_quantos_studio.py`.

## Commands and outcomes

| Command | Result | Evidence/notes |
|---|---|---|
| `uv run python -c "import sys; sys.stdout = None; import uvicorn; uvicorn.Config('quant_system.server.app:app')"` | REPRODUCED | Exact traceback reproduced: `AttributeError: 'NoneType' object has no attribute 'isatty'` -> `ValueError: Unable to configure formatter 'default'` |
| `uv run pytest tests/test_quantos_studio.py` | PASS | All 10 tests passed in 3.87s |
| `uv run pytest tests/test_release_packaging.py` | PASS | All 19 tests passed in 3.36s |
| `uv run ruff check quantos_studio.py tests/test_quantos_studio.py` | PASS | All checks passed |
| `uv run ruff format --check quantos_studio.py tests/test_quantos_studio.py` | PASS | 2 files already formatted |
| `$env:PYTHONPATH="src"; uv run mypy src quantos_studio.py tests/test_quantos_studio.py` | PASS | Success: no issues found in 163 source files |
| `audit-agent-claims.ps1` | PASS | All claims and worktrees resolve cleanly |
| `audit-disk-layout.ps1` | PASS | Drive isolation law maintained; 0 stray dirs |

## Files changed

- `quantos_studio.py`: added `NullStream`, `ensure_safe_std_streams()`, `log_config=None` in `uvicorn.Config`, and routed uvicorn loggers to `studio.log`.
- `tests/test_quantos_studio.py`: added 5 regression unit tests for `NullStream`, stream safety replacement, stdio log redirection, uvicorn config initialization, and uvicorn logging routing.
- `agent_context/work/completed/20260925-1545Z-antigravity-studio-uvicorn-isatty-fix.md`: completed work record

## Blockers and conflicts

None on owned paths.

## Stop point

Bug fixed, verified with unit tests, ruff, mypy, and repository audits.

## Next safe action

User can launch `quantos_studio.py` directly, via `pythonw`, or through PyInstaller windowed executable without encountering the `isatty` error.
