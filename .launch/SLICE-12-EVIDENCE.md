# Slice 12 Evidence — Reproducible Windows Release Packaging

STATUS: PASS  
DATE: 2026-08-22  
SCOPE: Reproducible Windows x64 release packaging, SBOM generation, cryptographic manifests, clean installation, startup self-test, and immutable evidence preservation.

## Outcome

Slice 12 implements the complete, production-grade reproducible Windows x64 release packaging pipeline for QuantOS:

1. **PyInstaller Packaging Specification:**
   - Standalone standalone executable `quantos.exe` (and `QuantOS.exe`) packaged via `installer/quantos.spec` and `quant_system.spec`.
   - Bundles all core modules, dynamic dependencies, static UI assets (`quant_system/server/static`), and configurations (`configs/`).

2. **Software Bill of Materials (SBOM):**
   - Implemented `src/quant_system/release/sbom.py` to parse `uv.lock` and generate machine-readable `sbom.json` / `quantos-sbom.json`.
   - Binds release artifacts directly to `uv.lock` SHA-256 (`9c40ebf4...`) and Git commit SHA (`b5bc061...`).
   - Captures all 48 locked direct and transitive dependencies with distribution wheel/sdist checksums.

3. **Cryptographic Release Manifest:**
   - Implemented `src/quant_system/release/manifest.py` generating `release-manifest.json` and standard `MANIFEST.sha256`.
   - Hashes and records all 244 packaged files (~129.78 MB), verifying bundle integrity and detecting corrupted, missing, or unauthorized unmanifested files.

4. **Clean Release Installation & Evidence Preservation Verifier:**
   - Implemented `src/quant_system/release/verifier.py` and `scripts/verify-clean-release.ps1`.
   - Successfully verified all 9 release gates including clean staging installation, pre-flight diagnostics, drive-isolated sandbox execution, uninstallation of application binaries, and 100% byte-for-byte preservation of user datasets, models, and trials in the Evidence Store.

5. **Release Automation Scripts:**
   - `scripts/build-windows-release.ps1`: End-to-end Windows x64 packaging pipeline.
   - `scripts/verify-clean-release.ps1`: Clean install, diagnostics, uninstallation, and evidence preservation verification gate.

## Release Metadata & Cryptographic Identities

| Metric | Value |
|---|---|
| Application Name | `QuantOS` |
| Application Version | `1.0.0` |
| Target Platform | `Windows x64` (`x86_64` / `AMD64`) |
| Primary Executable | `quantos.exe` |
| Git Commit SHA | `b5bc0617757e10919e76f40b609e11beb57eb2f6` |
| `uv.lock` SHA-256 | `9c40ebf470a8c7021b849f72acdb23347e49a63053ecbd59e3832337d3a27498` |
| Total Locked Packages | 48 |
| Standalone Files | 244 files |
| Standalone Payload Size | 129.78 MB (136,086,819 bytes) |
| Portable ZIP Archive | `dist/quantos-v1.0.0-windows-x86_64.zip` |

## Verification Gates Summary

| Gate | Result | Details |
|---|---|---|
| 1. Release Manifest Cryptographic Check | PASS | All 244 packaged files match SHA-256 digests in `release-manifest.json` |
| 2. SBOM `uv.lock` Binding Verification | PASS | SBOM `uv_lock_sha256` matches exact cryptographic identity of `uv.lock` |
| 3. Clean Staging Installation | PASS | Release bundle staged cleanly into temporary sandbox `tmp/clean-install-test` |
| 4. Engine Startup Diagnostics & Self-Test | PASS | Pre-flight self-test (`--check-prerequisites`) executed all 6 checks with 0 errors |
| 5. Drive Isolation & Sandbox Verification | PASS | `TEMP`, `TMP`, `TMPDIR`, `MPLCONFIGDIR`, `PYTHONPYCACHEPREFIX` strictly local |
| 6. User Evidence Store Population | PASS | Mock immutable dataset, trial, and model records created in evidence store |
| 7. Safe Clean Uninstallation | PASS | Binaries cleanly removed from install root |
| 8. Evidence Store Preservation Invariant | PASS | 100% of user evidence files preserved with identical SHA-256 hashes |
| 9. Reinstallation & Evidence Continuity | PASS | Reinstalling over existing evidence succeeds without altering existing records |
| Release Packaging Pytest Suite | PASS | 16/16 tests passing in `tests/test_release_packaging.py` (100% pass) |
| Code Craft Check | PASS | 5 source files clean (0 findings) |
| Test Craft Check | PASS | 1 test file clean (0 findings) |
| Mypy Strict Typecheck | PASS | `src/quant_system/release` clean (0 errors) |
| Ruff Lint & Format | PASS | Clean |

## Test Suite Execution Evidence

```text
============================= test session starts =============================
platform win32 -- Python 3.13.15, pytest-9.1.1, pluggy-1.6.0 -- D:\quant_system\.venv\Scripts\python.exe
cachedir: .pytest_cache
rootdir: D:\quant_system
configfile: pyproject.toml
plugins: anyio-4.14.2, cov-7.1.0
collecting ... collected 16 items

tests/test_release_packaging.py::test_spec_files_exist_and_contain_required_configurations[quant_system.spec] PASSED [  6%]
tests/test_release_packaging.py::test_spec_files_exist_and_contain_required_configurations[installer/quantos.spec] PASSED [ 12%]
tests/test_release_packaging.py::test_parse_uv_lock_extracts_packages PASSED [ 18%]
tests/test_release_packaging.py::test_generate_and_verify_sbom PASSED    [ 25%]
tests/test_release_packaging.py::test_sbom_tamper_detection PASSED       [ 31%]
tests/test_release_packaging.py::test_release_manifest_generation_and_validation PASSED [ 37%]
tests/test_release_packaging.py::test_release_manifest_detects_corrupted_or_missing_files PASSED [ 43%]
tests/test_release_packaging.py::test_run_prerequisite_checks PASSED     [ 50%]
tests/test_release_packaging.py::test_drive_isolation_configuration PASSED [ 56%]
tests/test_release_packaging.py::test_find_free_port PASSED              [ 62%]
tests/test_release_packaging.py::test_clean_release_verification_journey PASSED [ 68%]
tests/test_release_packaging.py::test_evidence_preservation_fails_on_corruption PASSED [ 75%]
tests/test_release_packaging.py::test_simulate_uninstallation_removes_binaries_only PASSED [ 81%]
tests/test_release_packaging.py::test_release_builder_workflow PASSED    [ 87%]
tests/test_release_packaging.py::test_inno_setup_iss_configuration PASSED [ 93%]
tests/test_release_packaging.py::test_setup_gui_components PASSED        [100%]

============================= 16 passed in 3.14s ==============================
```

## Clean Release Verification Gate Output

```text
======================================================================
  QuantOS Clean Release & Evidence Preservation Verification Gate
======================================================================

[CONFIG] Release Bundle:   D:\quant_system\dist\quantos
[CONFIG] Staging Install:  D:\quant_system\tmp\clean-install-test
[CONFIG] Evidence Root:    D:\quant_system\tmp\clean-install-evidence
[CONFIG] Lock File:        D:\quant_system\uv.lock

--- VERIFICATION STEP RESULTS ---
[PASS] 1. Release Manifest Cryptographic Check
       Details: Release bundle verified successfully.
[PASS] 2. SBOM uv.lock Binding Verification
       Details: SBOM matches uv.lock cryptographic identity.
[PASS] 3. Clean Staging Installation
       Details: Installed cleanly to D:\quant_system\tmp\clean-install-test
[PASS] 4. Engine Startup Diagnostics & Self-Test
       Details: Native executable pre-flight checks passed.
[PASS] 5. Drive Isolation & Sandbox Verification
       Details: Runtime sandbox routes all temporary and cache files strictly within local tree.
[PASS] 6. User Evidence Store Population
       Details: Created 3 immutable evidence resources.
[PASS] 7. Safe Clean Uninstallation
       Details: Application binaries removed cleanly from install root.
[PASS] 8. Evidence Store Preservation Invariant
       Details: All 3 evidence files preserved with 100% integrity.
[PASS] 9. Reinstallation & Evidence Continuity
       Details: Reinstallation succeeded without altering existing user evidence.

--- SUMMARY ---
Total Gates:  9
Passed Gates: 9
Failed Gates: 0
Final Status: All 9 release verification gates PASSED successfully.

[CLEANUP] Cleaning up temporary test staging directories...
  -> Temporary test staging cleaned.

======================================================================
  [VERIFICATION COMPLETE] Clean Release and Evidence Preserved 100%!
======================================================================
```
