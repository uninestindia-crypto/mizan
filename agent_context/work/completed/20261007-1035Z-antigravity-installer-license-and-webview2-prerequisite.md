# Active work: installer license acceptance and WebView2 prerequisite check

STATUS: COMPLETED  
OWNER: Antigravity session (founder instruction: accept terms/license & prerequisite install)  
TOOL: Antigravity  
STARTED_UTC: 2026-10-07T10:35:00Z  
STARTING_REVISION: bb59a3ac8fe23d2ac7e2e928152a0c6b98701b22  
WORKTREE_OR_BRANCH: the install root, branch `main`

## Objective

GOAL_LINE: G3

1. Add explicit Terms & Conditions and End User License Agreement (EULA) acceptance to the Windows Inno Setup installer (`installer/quant_os_setup.iss`) so installation cannot proceed without user acceptance.
2. Ensure all prerequisites are handled by the installer for factory-new laptops, specifically verifying Microsoft Edge WebView2 runtime presence on Windows and gracefully downloading/installing the WebView2 Evergreen bootstrapper if missing on stripped-down Windows versions.
3. Update static installer tests in `tests/test_windows_installer.py` to verify `LicenseFile` and WebView2 prerequisite handling.

## Owned paths

- `installer/quant_os_setup.iss`
- `installer/assets/LICENSE.txt`
- `tests/test_windows_installer.py`
- `agent_context/work/completed/20261007-1035Z-antigravity-installer-license-and-webview2-prerequisite.md`

## Non-goals

- No change to core accounting, risk governor, or execution code.
- No live order routing.
- Do not modify files claimed by other active sessions (`frontend/src/components/live/LivePrice.tsx`, `frontend/src/pages/Home.tsx`, `src/quant_system/server/v2/credentials.py`).

## Plan

1. Create `installer/assets/LICENSE.txt` with clear QuantOS & Mizan Shariah Wealth Engine EULA, Terms of Service, research disclaimer, and SEBI compliance disclosure. [DONE]
2. In `installer/quant_os_setup.iss`: [DONE]
   - Declare `LicenseFile=assets\LICENSE.txt` under `[Setup]`.
   - Add WebView2 runtime detection in Pascal `[Code]` via Windows registry check (`HKLM\SOFTWARE\WOW6432Node\Microsoft\EdgeUpdate\Clients\{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}` and per-user `HKCU`).
   - If WebView2 is absent on the machine, prompt the user and seamlessly download/run Microsoft's WebView2 Evergreen Bootstrapper (`MicrosoftEdgeWebview2Setup.exe /silent /install`), or alert with instructions if offline.
3. Update `tests/test_windows_installer.py` to assert `LicenseFile` exists, points to `assets/LICENSE.txt`, and tests the Inno setup script directives. [DONE]
4. Run static gates and unit tests (`pytest tests/test_windows_installer.py`). [DONE]
5. Build Windows installer (`scripts/build-windows-installer.ps1`). [DONE]
6. Move work record to `completed/`. [DONE]

## Current step

Work completed and verified.

## Decision rationale

- Inno Setup provides native `LicenseFile` directive in `[Setup]`. When declared, it renders the Win11 modern styled `wpLicense` wizard page with radio buttons: "I accept the agreement" / "I do not accept the agreement". The "Next" button is strictly disabled until the user explicitly agrees.
- Under the Factory-New Laptop standard (G3), Python, Node, C-extensions, and SQLite seed data are already bundled in the PyInstaller output and installer. The only missing runtime that might not exist on custom/stripped Windows 10 LTSC/Enterprise systems is Microsoft Edge WebView2 Runtime. Detecting WebView2 in Inno Setup Pascal script and silently bootstrapping it ensures true zero-dependency installation out-of-the-box.

## Commands and outcomes

| Command | Result | Evidence/notes |
|---|---|---|
| Initial audit | PASS | Verified missing `LicenseFile` and reviewed `quant_os_setup.iss` |
| `.venv\Scripts\pytest.exe tests/test_windows_installer.py` | PASS | 24/24 tests passed, including EULA acceptance and WebView2 checks |
| `.venv\Scripts\ruff.exe check tests/test_windows_installer.py` | PASS | 0 findings |
| `.venv\Scripts\ruff.exe format --check tests/test_windows_installer.py` | PASS | Clean format |
| `powershell -ExecutionPolicy Bypass -File scripts/build-windows-installer.ps1` | PASS | Built `dist\QuantOS_v2.5.0_Setup.exe` (58.9 MB) |
| `scripts/audit-disk-layout.ps1` | PASS | Exit code 0, no stray QuantOS directories |

## Files changed

- `installer/assets/LICENSE.txt`: QuantOS Desktop Studio & Mizan Shariah Wealth Engine EULA and Terms of Use
- `installer/quant_os_setup.iss`: Added `LicenseFile=assets\LICENSE.txt` to `[Setup]`, and added WebView2 runtime detection, download wizard page, and bootstrapper execution to `[Code]`
- `tests/test_windows_installer.py`: Added static tests for license acceptance and WebView2 prerequisite provisioning
- `dist/QuantOS_v2.5.0_Setup.exe`: Compiled Windows installer (58.9 MB)

## Blockers and conflicts

None.

## Stop point

Completed. Installer built and verified.

## Next safe action

Founder can run `dist\QuantOS_v2.5.0_Setup.exe` to inspect the new license acceptance wizard page and test installation.
