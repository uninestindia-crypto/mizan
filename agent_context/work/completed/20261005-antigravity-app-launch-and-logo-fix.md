# Completed work: QuantOS desktop app launch lifecycle and shortcut logo repairs

STATUS: COMPLETED
OWNER: Antigravity root agent
TOOL: Antigravity
STARTED_UTC: 2026-10-05T15:05:00Z
COMPLETED_UTC: 2026-10-05T15:20:00Z
REVISION: 05fc70dea
WORKTREE_OR_BRANCH: `d:\Quant OS Project\Mizan` on branch `main`

## Root Causes Identified

1. **Why the application didn't open after closing ("clicking cut"):**
   - In `quantos_studio.py`, closing the window triggered `sys.exit(0)`. In Python, `sys.exit(0)` only raises `SystemExit` on the main thread and waits for all non-daemon threads and .NET CLR threads (from pywebview's WinForms / pythonnet host) to join.
   - Because background workers / CLR threads remained active, the process did not terminate at the OS level and remained running invisibly as a zombie process (e.g. PID 10076).
   - This zombie process continued holding the single-instance mutex (`Local\QuantOS.Desktop.SingleInstance`).
   - On every subsequent launch, `acquire_single_instance()` failed because the mutex was still held. The launcher called `focus_existing_window()`, but since the window was already closed, no window existed to focus, and the new instance immediately called `sys.exit(0)` without opening anything.
   - Additionally, on fresh installations `data/shariah/halal_stocks.db` was created as an empty 4KB file, causing recurring `sqlite3.OperationalError: no such table: companies` errors on every health check.

2. **Why the logo did not appear on Desktop / Start Menu shortcuts:**
   - In `installer/quant_os_setup.iss`, shortcut entries specified `IconFilename: "{app}\assets\quantos.ico"`.
   - However, `[Files]` only extracted `{#SourceDir}\*` (which placed assets in `_internal\assets`, not in `{app}\assets\`).
   - Consequently, `{app}\assets\quantos.ico` did not exist on disk after installation.
   - Windows Explorer failed to locate the icon path specified in the `.lnk` file and fell back to the default blank/white document icon.

## Changes Implemented

1. **Hard Clean Exit & Close Watchdog (`quantos_studio.py` & `src/quant_system/shell/native_window.py`):**
   - Replaced `sys.exit(0)` with `os._exit(0)` in `quantos_studio.py`'s shutdown sequence, ensuring the Windows OS kernel immediately terminates the process, closes all handles, and frees mutexes and ports.
   - Added a window closed watchdog in `run_native_window`: if the WinForms event loop doesn't return within 2.5 seconds of `win.events.closed`, it triggers `os._exit(0)`.
   - Implemented `cleanup_zombie_instances()` and self-healing single-instance recovery in `quantos_studio.py`: if the mutex is held but no window titled "QuantOS" is found after 1.5 seconds, it terminates the headless zombie and acquires the lock instead of stranding the user.

2. **Auto-populating Shariah Seed Database (`src/quant_system/shariah/core/config.py`):**
   - Added `ensure_shariah_database()` in `config.py`: automatically detects missing or empty (<10KB) SQLite databases and copies the bundled seed database from `_internal/data/shariah/halal_stocks.db` or initializes tables with `init_db()`.
   - Set `QUANTOS_APP_ROOT` environment variable in `launcher.py` and `quantos_studio.py` to prevent path confusion.

3. **Logo & Asset Staging (`installer/quant_os_setup.iss` & `scripts/build-windows-release.ps1`):**
   - Updated `quant_os_setup.iss` to explicitly install `Source: "assets\*"; DestDir: "{app}\assets"`, `Source: "..\data\shariah\*"; DestDir: "{app}\data\shariah"`, and updated `UninstallDisplayIcon` to `{app}\assets\quantos.ico`.
   - Updated `scripts/build-windows-release.ps1` to stage visual assets and seed data into `dist\quantos\assets` and `dist\quantos\data\shariah`.
   - Updated existing shortcuts on the user's desktop to point to the valid icon at `D:\Quant OS Project\QuantOS\assets\quantos.ico,0` and refreshed Windows shell icon cache.

## Verification

- `pytest tests/test_native_window.py`: 26/26 passed.
- Full test suite: 1,521 passed in 96.6s.
- `ruff check` and `ruff format --check`: 100% clean.
- `mypy`: clean across all modified files.
- Rebuilt installer: `dist\QuantOS_v2.3.0_Setup.exe` (58.4 MB) compiled successfully with bundled icon assets and seed database.
- Installed app updated: `quantos-studio.exe` and `assets\quantos.ico` verified in `D:\Quant OS Project\QuantOS`.
