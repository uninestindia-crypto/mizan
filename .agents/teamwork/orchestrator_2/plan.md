# Execution Plan: QuantOS Standalone Windows Executable Installer

## Overview
Build a production-grade, zero-friction standalone Windows Executable Installer (`QuantOS_Setup.exe`) that packages the complete pre-compiled application binaries offline, dynamically detects and silently installs missing Windows prerequisites (VC++ 2015-2022 Redistributable and WebView2 runtime), configures an isolated drive sandbox layout, registers desktop shortcuts, and performs automated pre-flight self-diagnostics before initial launch.

## Execution Steps

### Phase 0: Survey & Grounding (3 Parallel Explorers)
- **Explorer 1 (Packaging Architect)**: Investigate existing packaging scripts (`scripts/build_executable.ps1`, `scripts/build-windows-release.ps1`, `installer/`, `launcher.py`, PyInstaller specs, Inno Setup configurations). Map what artifacts are needed for standalone offline extraction.
- **Explorer 2 (Prerequisite Specialist)**: Map Microsoft official URLs for VC++ 2015-2022 x64 Redistributable (`vc_redist.x64.exe`) and Edge WebView2 Evergreen bootstrapper/standalone installer (`MicrosoftEdgeWebview2Setup.exe`). Detail Windows registry detection keys, silent unattended switches (`/quiet /norestart`), error codes, and offline fallback mechanisms.
- **Explorer 3 (Diagnostics & Scaffolding Engineer)**: Inspect pre-flight checks: loopback socket binding (127.0.0.1), Decimal ledger invariant arithmetic, folder write access, hardware detection (NPU/GPU/AVX2). Examine drive detection rules (preferring D:\QuantOS over C:\QuantOS), folder structure (`data/`, `logs/`, `tmp/`), starter `.env` format, and shortcut creation (.lnk).

### Phase 1: Architecture & Scope Specification (`SCOPE.md`)
- Reconcile explorer findings.
- Write formal `SCOPE.md` detailing architecture, interfaces, files owned, and milestone boundaries.
- Ensure active work record in `agent_context/work/active/` is created by a worker.

### Phase 2: Implementation & Iteration Loops
- **Milestone 1**: Installer Packaging Architecture & Standalone Executable Build Script (`scripts/build-windows-release.ps1` -> `dist/QuantOS_Setup.exe`).
- **Milestone 2**: Automated Prerequisite Detection & Silent Installation with Official Microsoft Endpoints.
- **Milestone 3**: Drive Isolation & Environment Scaffolding (smart drive selection, sandbox directories, `.env`, shortcuts).
- **Milestone 4**: Integrated Pre-Flight System Diagnostics (loopback 127.0.0.1, Decimal invariant arithmetic, hardware NPU/GPU/AVX2 detection, `logs/setup_diagnostics.log`, green-badge UI).
- **Milestone 5**: UI/UX Polish, Network Fallback, Error Handling & Clean Uninstaller.
- **Milestone 6**: End-to-End Regression Test Suite & Repository Gate Verification (`tests/test_windows_installer.py`, `ruff check`, `mypy`, disk layout & agent claims audits).

### Phase 3: Gate & Acceptance Verification
- Independent Reviewers, Challengers, and Forensic Auditor verification.
- Final report to Sentinel.
