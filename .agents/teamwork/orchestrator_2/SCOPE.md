# Scope: Standalone Windows Executable Installer (QuantOS_Setup.exe)

## Architecture
QuantOS Windows Setup is a self-contained, single-file Windows executable (`QuantOS_Setup.exe`) that encapsulates:
1. Application Payload: Pre-compiled QuantOS binaries (`quantos.exe` or standalone bundle generated via PyInstaller/Nuitka/Inno Setup), runtime configuration assets, web UI templates, and static resources.
2. Setup Engine & Runtime Bootstrapper:
   - Dynamic host inspection for prerequisites (VC++ 2015-2022 x64 Redistributable and Microsoft Edge WebView2 Evergreen).
   - Network fetch engine restricted to official Microsoft download endpoints with offline fallback guidance.
   - Unattended silent installer executor (`/quiet /norestart`).
   - Smart drive selection logic (preferring D:\QuantOS if D: exists and has space, fallback to C:\QuantOS, custom path override).
   - Scaffolding of runtime isolation layout (`data/`, `logs/`, `tmp/`), starter `.env` configuration file, Windows Desktop shortcut (`QuantOS.lnk`), and Start Menu entry.
3. Pre-Flight Diagnostics Engine:
   - Non-blocking post-install validation running localhost 127.0.0.1 socket binding, Decimal ledger invariant arithmetic, folder write access, hardware detection (NPU/GPU/AVX2).
   - Output logging to `logs/setup_diagnostics.log`.
   - Green-badge readiness UI with 1-click launch trigger.
4. Clean Uninstaller:
   - Registers in Windows Add/Remove Programs, removes application files, shortcuts, leaves optional user data with confirmation.

## Feature Inventory
| # | Feature | Description | Milestone | Source |
|---|---------|-------------|-----------|--------|
| 1 | Standalone Setup Executable | Produces `dist/QuantOS_Setup.exe` with bundled binaries | M1 | ORIGINAL_REQUEST §R1 |
| 2 | VC++ Redistributable Detection | Checks registry keys / files for VC++ 2015-2022 x64 | M2 | ORIGINAL_REQUEST §R2 |
| 3 | WebView2 Evergreen Detection | Checks registry keys / installed runtimes for Edge WebView2 | M2 | ORIGINAL_REQUEST §R2 |
| 4 | Official MS Download & Silent Install | Fetches runtimes from verified MS URLs and runs silent install | M2 | ORIGINAL_REQUEST §R2 |
| 5 | Network Fallback & Offline Guidance | Clear non-technical offline error instructions, retry without crash | M5 | ORIGINAL_REQUEST §R5 |
| 6 | Smart Drive Selection & Sandbox | Detects D: vs C: drives, creates isolated runtime subdirs | M3 | ORIGINAL_REQUEST §R3 |
| 7 | Starter .env Generation | Generates clean starter `.env` with documentation and defaults | M3 | ORIGINAL_REQUEST §R3 |
| 8 | Windows Shortcuts | Creates Desktop and Start Menu shortcuts to quantos.exe | M3 | ORIGINAL_REQUEST §R3 |
| 9 | Pre-flight Loopback Binding | Validates 127.0.0.1 socket bind | M4 | ORIGINAL_REQUEST §R4 |
| 10| Pre-flight Decimal Arithmetic | Validates exact Decimal accounting invariant | M4 | ORIGINAL_REQUEST §R4 |
| 11| Pre-flight Hardware Detection | Detects Qualcomm Hexagon NPU, GPU, AVX2 CPU capabilities | M4 | ORIGINAL_REQUEST §R4 |
| 12| Setup Diagnostics Log & Badge | Writes `logs/setup_diagnostics.log` and presents green-badge UI | M4 | ORIGINAL_REQUEST §R4 |
| 13| Clean Uninstallation | Cleanly uninstalls binaries and shortcuts | M5 | ORIGINAL_REQUEST Acceptance |
| 14| Automated E2E Regression Tests | Automated tests in `tests/test_windows_installer.py` | M6 | ORIGINAL_REQUEST Acceptance |

## Milestones
| # | Name | Scope | Dependencies | Status |
|---|------|-------|-------------|--------|
| M0 | Survey & Grounding | Map existing codebase, packaging, installer scripts | none | IN_PROGRESS |
| M1 | Installer Packaging & Build Script | Build script producing `QuantOS_Setup.exe` | M0 | PLANNED |
| M2 | Prerequisite Engine & MS Download | VC++ & WebView2 detection, download, silent install | M0 | PLANNED |
| M3 | Drive Isolation & Scaffolding | Drive selection, directories, starter .env, shortcuts | M0 | PLANNED |
| M4 | Pre-Flight Diagnostics Engine | Socket, Decimal, hardware checks, diagnostics log | M0 | PLANNED |
| M5 | UI Polish, Network Fallback & Uninstaller | Error handling, offline mode, clean uninstaller | M1, M2, M3, M4 | PLANNED |
| M6 | Automated E2E Test Suite & Gates | Comprehensive test suite, ruff, mypy, audits | M1-M5 | PLANNED |

## Code Layout
- `scripts/build-windows-release.ps1`: Primary release build and packaging script.
- `installer/`: Inno Setup / packaging scripts, installer definition, embedded resources, icons.
- `src/quant_system/installer/` or `installer/scripts/`: Setup runtime helpers, diagnostics module, prerequisite verification scripts.
- `tests/test_windows_installer.py`: Automated tests for installer mechanics, prerequisite detection, fallback, scaffolding, diagnostics, uninstaller.
