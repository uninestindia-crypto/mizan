# Original User Request

## 2026-09-25T09:39:47Z

Build and rigorously validate a multi-instrument cross-sectional ranking strategy across the liquid 423-name NSE research universe, transitioning from single-name directional predictions to an investable, cost-surviving portfolio alpha system.

Working directory: D:\quant_system  
Integrity mode: development

## Requirements

### R1. Multi-Factor Composite Ranking Engine
Compute point-in-time cross-sectional rankings across all eligible names in `data/authorities/nse-research-universe-liquid-10y.csv` at each decision close. The composite ranking must combine intermediate-term momentum (21–63 sessions), short-term mean-reversion dampening (3–5 sessions), and idiosyncratic volatility scaling, strictly using data available at decision close T.

### R2. Staggered Tranche Portfolio Ledger
Construct and maintain a 4-tranche weekly-rebalanced portfolio ledger (each tranche held for 21 trading sessions). Each weekly rebalance must invest in the top-ranked quintile (15–20% of liquid universe) with next-open execution (T+1), incorporating the full 0.224% round-trip statutory fee model and ensuring total portfolio leverage never exceeds 100%.

### R3. Factor Monotonicity and Long-Short Diagnostic
Run a parallel, zero-capital long-short diagnostic across universe deciles (Q1 through Q10) to audit factor monotonicity. Measure and output rank information coefficients (Spearman rank IC) and spread returns between top and bottom deciles across all validation periods.

### R4. Multiplicity Accounting and Noise Benchmarking
Pre-declare the validation evaluation budget and benchmark the resulting strategy against:
- `CASH` / No-trade baseline;
- `ALWAYS_TRADE` broad market benchmark;
- An identical-configuration 30-seed pseudo-random NOISE control.

## Acceptance Criteria

### Statistical & Financial Validity
- [ ] Strategy achieves a positive net annualized Sharpe ratio strictly after deducting 0.224% round-trip transaction costs.
- [ ] Average cross-sectional Spearman rank Information Coefficient (IC) is positive with statistical significance (`t > 2.0`).
- [ ] Decile returns demonstrate monotonicity: Top decile (Q1) annualized return exceeds bottom decile (Q10) annualized return.
- [ ] Strategy deflated Sharpe ratio exceeds the median of the 30-seed NOISE control at the 21-session holding horizon.

### Engineering & Governance Invariants
- [ ] Zero look-ahead leakage: Execution strictly at next-session open (T+1) based on information up to decision close (T); point-in-time corporate actions strictly applied or skipped.
- [ ] Capital preservation invariant: Tranche ledger total capital exposure strictly `<= 1.0` at all timestamps.
- [ ] Full automated test suite passes (`pytest tests/`, `ruff check`, `mypy`), and claim/disk layout audits exit 0.
- [ ] The final chronological holdout partition is strictly quarantined and untouched during development and tuning.

## 2026-09-25T10:00:06Z

Requested team: Full multi-agent team (parallel specialized roles: installer architect, prerequisite download engineer, UI/UX polish, and independent verification tester)

Build a production-grade, zero-friction standalone Windows Executable Installer (QuantOS_Setup.exe) that installs, configures, and validates QuantOS on any clean Windows 10/11 laptop without requiring prior Python, Git, or developer tooling. The installer packages the complete pre-compiled application binaries offline, dynamically detects and silently installs missing Windows prerequisites (VC++ 2015-2022 Redistributable and WebView2 runtime), configures an isolated drive sandbox layout, registers desktop shortcuts, and performs automated pre-flight self-diagnostics before initial launch.

Working directory: D:\quant_system
Integrity mode: development

## Requirements

### R1. Standalone Windows Executable Installer
Package the complete QuantOS desktop platform binaries into a standalone, single-file Windows setup executable (QuantOS_Setup.exe) that runs on standard Windows 10 and 11 64-bit systems without pre-installed development dependencies.

### R2. Automated Prerequisite Detection & Silent Installation
Inspect the host operating system for required system runtimes prior to file extraction. If Microsoft Visual C++ 2015-2022 Redistributable (x64) or Microsoft Edge WebView2 Evergreen Runtime is missing, download the official installer directly from Microsoft endpoints and execute unattended silent installations (/quiet /norestart) with clear user progress indication.

### R3. Drive Isolation & Environment Scaffolding
Provide smart installation drive selection (preferring a secondary drive such as D:\QuantOS if available, or C:\QuantOS if only C: exists) while allowing custom path selection. Automatically create isolated runtime subdirectories (data/, logs/, tmp/), generate a starter .env configuration file with documented placeholders, and create Desktop and Start Menu shortcuts pointing to quantos.exe.

### R4. Integrated Pre-Flight System Diagnostics
At the conclusion of setup, run an automated non-blocking health check verifying localhost loopback socket binding (127.0.0.1), Decimal ledger invariant arithmetic, folder write access, and hardware detection (Qualcomm Hexagon NPU, GPU, and AVX2 CPU capabilities). Present a clean green-badge readiness summary with a 1-click "Launch QuantOS" button.

### R5. Controlled Network Infrastructure & Graceful Fallback
Restrict external network requests exclusively to verified official Microsoft runtime download URLs. If network access is unavailable and a prerequisite is missing, display clear, non-technical instructions and provide an offline retry mechanism without crashing or corrupting the installation.

## Acceptance Criteria

### Installer Build & Packaging
- [ ] Running the build script (scripts/build-windows-release.ps1 or dedicated packaging command) produces a valid, signed or authenticated QuantOS_Setup.exe in dist/.
- [ ] The generated setup executable runs on clean Windows 10/11 x64 systems without requiring an active Python or Git installation.

### Prerequisite Detection & Silent Setup
- [ ] Prerequisite detection accurately identifies when VC++ Redistributable or WebView2 are absent.
- [ ] Missing runtimes are successfully downloaded from verified official Microsoft endpoints and installed unattended without user reboot prompt.
- [ ] If all prerequisites are already present, the installer skips downloading and proceeds immediately to application setup.

### Directory Layout & Sandboxing
- [ ] The application and all subfolders (data/, logs/, tmp/) are created on the target drive with zero unintended files written to other drives.
- [ ] A starter .env file is generated in the installation root with default keys and instructions.
- [ ] A valid Windows Desktop shortcut (QuantOS.lnk) and Start Menu entry are created pointing directly to quantos.exe.

### Automated Pre-Flight Diagnostics
- [ ] Executing the post-install diagnostic check verifies local loopback binding (127.0.0.1), Decimal invariant reconciliation, and hardware detection, logging full output to logs/setup_diagnostics.log.
- [ ] The installer displays a visual completion screen with green checkmarks and a functional 1-click launch trigger.

### Automated Test Suite
- [ ] Automated end-to-end regression tests verify prerequisite detection logic, download fallback handling, directory structure generation, and uninstaller clean removal.
- [ ] All existing repository unit and static tests pass without regressions (ruff check ., mypy).

## 2026-09-25T10:37:52Z

This is a single self-contained fix; keep it small and focused.
Build a production-grade Windows setup installer (`QuantOS_v1.0.0_Setup.exe`) that packages the zero-console QuantOS Desktop Studio (`quantos-studio.exe`) as the primary consumer desktop application, enforces strict drive isolation (zero C: drive leakage), creates desktop shortcuts to Studio, preserves user research evidence on uninstall, and verifies cryptographic integrity via SBOM and release manifest.

Working directory: D:\quant_system
Integrity mode: development

## Requirements

### R1. Desktop Studio Multi-Binary Release Bundle
Package both `quantos-studio.exe` (windowed GUI host with WebView2 and clean auto-shutdown) and `quantos.exe` (engine/server) into `dist/quantos`, including all server static web assets, configuration templates, and runtime dependencies.

### R2. Consumer-Grade Drive-Isolated Setup Wizard
Provide a standalone, single-file installer executable (`QuantOS_v1.0.0_Setup.exe`) that:
- Allows selecting the installation directory and defaults to non-C: drives if available.
- Enforces 100% drive isolation by initializing local `tmp/`, `data/`, and `logs/` directories.
- Creates a Windows Desktop shortcut pointing exclusively to Desktop Studio (`quantos-studio.exe`) for a zero-console consumer launch experience.
- Bundles a safe uninstaller (`uninstall.bat`) that cleanly removes application binaries and Python runtime caches while strictly preserving all user research evidence, datasets, and logs.

### R3. Automated Packaging & Verification Pipeline
Update the release build and verification pipeline to:
- Compile both Studio and Engine executables into the release bundle.
- Compile the setup wizard into the standalone setup executable.
- Generate an SBOM tied to `uv.lock` and a SHA-256 release manifest covering all packaged files.
- Pass clean-sandbox staging, drive isolation checks, and evidence preservation verification.

## Acceptance Criteria

### Binary & Packaging Integrity
- [ ] `dist/quantos/quantos-studio.exe` and `dist/quantos/quantos.exe` build successfully and are present in the distribution bundle.
- [ ] `dist/QuantOS_v1.0.0_Setup.exe` builds as a standalone executable containing the full installation payload.
- [ ] `sbom.json` correctly binds to the current `uv.lock` SHA-256 and records all package dependencies.
- [ ] `release-manifest.json` and `MANIFEST.sha256` accurately record SHA-256 hashes of all files in the release bundle.

### User Experience & Drive Isolation
- [ ] The installer provides a GUI folder selector, verifies available disk space, and installs without requiring administrator privileges.
- [ ] Launching the installed desktop shortcut opens QuantOS Desktop Studio in a dedicated application window with zero visible terminal/console window.
- [ ] All runtime temporary files, caches, and logs stay strictly confined to the installation directory on the target drive.
- [ ] Closing the Desktop Studio window cleanly shuts down the application and background server process with no orphaned background tasks.
- [ ] Running the uninstaller removes program binaries and Python caches but leaves `data/` and `logs/` untouched.

### Automated Test Gates
- [ ] `pytest tests/test_release_packaging.py` passes 100% (all 16+ tests).
- [ ] `pytest tests/test_quantos_studio.py` passes 100%.
- [ ] `scripts/audit-disk-layout.ps1` and `scripts/audit-agent-claims.ps1` exit 0 with zero violations.

