# Slice 12 Contract — Reproducible Windows Release Packaging

STATUS: FROZEN FOR IMPLEMENTATION  
DATE: 2026-08-22  
SCOPE: Standalone Windows x64 release packaging, SBOM generation, cryptographic manifests, clean installation, startup self-test, and evidence preservation.

## Inputs

- Pinned `uv.lock` dependency lockfile defining exact package versions, sources, and cryptographic checksums for all direct and transitive dependencies.
- Git repository working tree and commit SHA (`git rev-parse HEAD` or environment fallback `RELEASE_GIT_SHA`).
- PyInstaller packaging specifications (`quant_system.spec`, `installer/quantos.spec`) configured for standalone Windows x64 one-dir distribution.
- Entrypoint launcher `launcher.py` providing drive isolation, pre-flight prerequisite verification, and loopback web server binding.
- Setup Installer (`installer/setup_gui.py`, `installer/setup_installer.spec`, `installer/quant_os_setup.iss`).

## Packaging & Artifact Invariants

1. **Standalone Binary:**
   - Standalone executable `quantos.exe` (and case-insensitive `QuantOS.exe` alias) compiled for Windows x64 architecture.
   - Static assets (`src/quant_system/server/static`) and default configurations (`configs/`) bundled deterministically into the distribution root.

2. **Software Bill of Materials (SBOM):**
   - Machine-readable `sbom.json` and `quantos-sbom.json` conforming to standardized SBOM schema v1.0.0.
   - Cryptographically bound to the SHA-256 hash of `uv.lock` and the active Git commit SHA.
   - Enumerates every locked package name, version, source registry/repository, distribution hashes (wheels/sdist), and direct dependencies.

3. **Cryptographic Release Manifest:**
   - `release-manifest.json` and standard `MANIFEST.sha256` generated at build time.
   - Contains normalized POSIX relative paths, exact byte sizes, and SHA-256 checksums for all distributed files.
   - Records application name, version, Git commit SHA, `uv.lock` SHA-256, build timestamp (ISO 8601 UTC), target OS (`windows`), target architecture (`x86_64`), and total byte payload.

4. **Portable Distribution ZIP Archive:**
   - Compressed archive `quantos-v{version}-windows-x64.zip` containing the complete validated standalone distribution tree.

5. **Drive Isolation & Storage Sandbox:**
   - All runtime directories (`tmp/`, `data/`, `logs/`) reside strictly within the application installation directory on the target drive.
   - Environment variables `TEMP`, `TMP`, `TMPDIR`, `MPLCONFIGDIR`, and `PYTHONPYCACHEPREFIX` redirect to the local sandbox, guaranteeing zero unintended writes or cache leakage to `C:\` or default system user profiles.

## Clean Installation, Startup, and Uninstallation Invariants

1. **Clean Installation Staging:**
   - The release bundle installs cleanly into any target path or drive without requiring external Python runtimes or system modifications.

2. **Pre-flight Startup Diagnostics & Self-Test:**
   - Running `quantos.exe --check-prerequisites` (or `--test-mode`) executes 6 foundational diagnostic checks:
     1. Drive-isolated storage sandbox verification.
     2. 64-bit architecture verification (`platform.machine()`, `sys.maxsize`).
     3. Local loopback socket binding (`127.0.0.1`).
     4. Double-entry Decimal ledger reconciliation invariant check.
     5. Quantitative Alpha & Black-Scholes mathematical pricing engine check.
     6. UI asset availability and market data credential disclosure.
   - Returns exit code 0 when all prerequisite invariants pass.

3. **Evidence Store Preservation Invariant:**
   - Clean uninstallation safely removes application binaries (`quantos.exe`, `_internal/`, `quant_system/`) while preserving 100% of user research, datasets, ledgers, models, and evidence stores (`data/`, `logs/`, external evidence roots).
   - Every preserved evidence file retains 100% byte-for-byte SHA-256 integrity with zero data loss.

4. **Reinstallation Continuity:**
   - Reinstalling the release over an existing evidence directory allows the application to immediately resume operations and access existing immutable evidence without state corruption.

## Verification Pipeline

- `scripts/build-windows-release.ps1`: Automated build pipeline executing PyInstaller compilation, SBOM generation, release manifest creation, portable ZIP packaging, and bundle integrity validation.
- `scripts/verify-clean-release.ps1`: Automated verification gate executing all 9 release gates end-to-end:
  1. Release Manifest Cryptographic Check
  2. SBOM uv.lock Binding Verification
  3. Clean Staging Installation
  4. Engine Startup Diagnostics & Self-Test
  5. Drive Isolation & Sandbox Verification
  6. User Evidence Store Population
  7. Safe Clean Uninstallation
  8. Evidence Store Preservation Invariant
  9. Reinstallation & Evidence Continuity
- `tests/test_release_packaging.py`: Comprehensive test suite verifying spec configurations, SBOM parsing, manifest tamper detection, pre-flight diagnostics, drive isolation, evidence preservation, and installer components.

## Explicit Limits

- Windows x64 is the primary tested architecture; ARM64 remains unadvertised until separately proven with native clean-install verification.
- Live broker order routing is not included (research, backtesting, shadow replay, and quote-driven paper pilot only).
- Code signing and Windows Defender SmartScreen status are reported truthfully; unsigned builds are never described as signed.
