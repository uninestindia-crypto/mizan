# Work Record: Desktop Studio Process Lifecycle and Reopen Lock Resilience

STATUS: COMPLETED  
CREATED_UTC: 2026-10-07T10:30:00Z  
COMPLETED_UTC: 2026-10-07T10:45:00Z  
OWNER: Antigravity  
BRANCH: main  
STARTING_REVISION: bb59a3ac8fe23d2ac7e2e928152a0c6b98701b22  
GOAL_LINE: G3, G6  

## Objective
Fix the desktop application lifecycle issue where closing the application leaves lingering background threads / processes or fails to reopen upon subsequent user clicks unless manually terminated from the Task Manager:
1. Ensure closing the desktop native window causes an immediate, clean, and unblocked process termination (using Windows kernel `TerminateProcess` to avoid MSVCRT `ExitProcess`/`DLL_PROCESS_DETACH` deadlocks in pywebview/WebView2 COM apartments).
2. Explicitly release the single-instance mutex (`release_single_instance`) immediately when window close is initiated.
3. Enhance zombie instance cleanup and reopen mutex acquisition:
   - Terminate zombie process trees (`taskkill /F /T`) and synchronously wait for process exit via `WaitForSingleObject` rather than an arbitrary 0.5s sleep.
   - Retry mutex acquisition with polling/backoff (up to 3 seconds) after zombie cleanup.
   - If no visible window exists titled QuantOS or belonging to the app, ensure the newly launched instance opens cleanly so the user is never locked out from opening their desktop software.

## Scope
- `quantos_studio.py`: Process termination, mutex release, zombie cleanup retry loop, hard exit helper.
- `src/quant_system/shell/native_window.py`: `release_single_instance`, synchronous wait for zombie process termination, enhanced `focus_existing_window`, `hard_exit`.
- `tests/test_native_window.py`: Tests for new lifecycle behaviors.

## Non-Goals
- Modifying order execution or routing.
- Changing frontend UI designs.

## Owned Paths
- `quantos_studio.py`
- `src/quant_system/shell/__init__.py`
- `src/quant_system/shell/native_window.py`
- `tests/test_native_window.py`
- `agent_context/work/completed/20261007-1030Z-antigravity-studio-process-lifecycle-and-reopen-fix.md`

## Outcomes & Verification
1. `quantos_studio.py` and `native_window.py` updated with `release_single_instance`, `hard_exit`, enhanced `focus_existing_window` and process-tree cleanup.
2. All 28 tests in `tests/test_native_window.py` pass.
3. Code formatting with `ruff format` and strict typing with `mypy` pass cleanly with zero issues.
4. Compiled and tested in local QuantOS Studio binary.
