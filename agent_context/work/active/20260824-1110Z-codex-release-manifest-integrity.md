# Active work: release manifest integrity and reproducible-build variance

STATUS: HANDOFF_REQUIRED
OWNER: Codex
TOOL: Codex
STARTED_UTC: 2026-08-24T11:10:00Z
STARTING_REVISION: `b084d723ee2a12cc4f63a8220ed39a559929ca22`
WORKTREE_OR_BRANCH: `D:\quant_system_workspaces\worktrees\feature-release-manifest-integrity-b084d72-20260824-111030` on branch `codex/release-manifest-integrity`

## Objective

Bind the Windows release manifest to the actual checked-out commit and the SHA-256 of normalized
`uv.lock` bytes, reject arbitrary `RELEASE_GIT_SHA` input, record reproducible-build variance
truthfully, and build one fresh Windows bundle only after focused and release checks pass.

## Owned paths

- `src/quant_system/release/sbom.py`
- `src/quant_system/release/manifest.py`
- `src/quant_system/release/builder.py`
- `src/quant_system/release/verifier.py`
- `src/quant_system/release/__init__.py`
- `scripts/build-windows-release.ps1`
- `scripts/verify-clean-release.ps1`
- `installer/quantos.spec`
- `tests/test_release_packaging.py`
- `tests/test_release_integrity.py` (new)
- `agent_context/work/active/20260824-1110Z-codex-release-manifest-integrity.md`
- `agent_context/work/completed/20260824-1110Z-codex-release-manifest-integrity.md`
- `D:\quant_system_workspaces\worktrees\feature-release-manifest-integrity-b084d72-20260824-111030\build\**`
- `D:\quant_system_workspaces\worktrees\feature-release-manifest-integrity-b084d72-20260824-111030\dist\**`

## Non-goals

- No release certification, launch-state change, or alteration of another verifier's report.
- No live-money routing, model, execution, server, UI, dependency, or lockfile changes.
- No editing, staging, merging, pruning, or removal of another agent's paths, branch, or workspace.
- No claim that PyInstaller output is byte-reproducible unless repeated-build evidence proves it.

## Plan

1. COMPLETE - create the claimed worktree, inspect release implementation/history, and reproduce the verifier findings.
2. COMPLETE - add failing regressions for commit binding, normalized lock hashing, override rejection, and variance reporting.
3. COMPLETE - implement the smallest release-integrity repair and run focused/static/release checks.
4. COMPLETE - build twice for variance evidence, then rebuild one fresh Windows bundle only after checks pass.
5. COMPLETE - record exact commands/hashes, audit claims/layout, and hand off without certification language.

## Current step

Requested repair and artifact generation are complete; preserve the claimed worktree for independent
review because certification was explicitly excluded.

## Decision rationale

The install root contains live changes and one active implementation worktree. A separate branch and
canonical worktree isolate release code, tests, and generated artifacts while leaving every existing
claim untouched. The independent verifier record is evidence input only; it owns no repair path.

## Commands and outcomes

| Command | Result | Evidence/notes |
|---|---|---|
| Required startup sequence | PASS | Read governance/release state, all 36 active records, worktrees/branches, and every install-root change. |
| `git rev-parse HEAD` | PASS | `b084d723ee2a12cc4f63a8220ed39a559929ca22`. |
| `new-workspace-clone.ps1 -Kind Worktree ...` | PASS | Exact preclaimed path and branch created at `b084d72`. |
| `uv sync --frozen --extra dev --link-mode copy` | PASS | 47 packages installed from the frozen lock into the isolated worktree. |
| `RELEASE_GIT_SHA=not-a-sha ... get_git_commit_sha(...)` | FAIL (reproduced) | Returned arbitrary text `not-a-sha`. |
| Raw/normalized checkout and committed `uv.lock` hashes | FAIL then normalized match | Raw `4c4a3a...` vs `9c40eb...`; both normalized hashes `9c40eb...`. |
| Two mock-payload `build_release` runs | FAIL (reproduced) | SBOM, manifest, and ZIP hashes all differ; no variance field records that fact. |
| `pytest tests/test_release_integrity.py -q` before implementation | EXPECTED FAIL | 3/3 regressions failed on arbitrary override acceptance, raw line-ending-sensitive lock hash, and missing reproducibility state. |
| Mutated identity/hash/variance branches, then ran the new suite | EXPECTED FAIL | 6 failures proved the tests kill arbitrary override, raw lock hashing, and suppressed variance; mutations were restored. |
| `pytest tests/test_release_integrity.py -q` | PASS | 12 passed in 4.77s after implementation; includes malformed, nonexistent, and non-HEAD override cases. |
| `pytest tests/test_release_packaging.py -q -k "not release_builder_workflow"` | PASS | 15 passed, 1 deselected in 3.20s; the one clean-checkout test waits for commit. |
| PowerShell wrapper dirty-checkout probe | EXPECTED FAIL | Exit 1; builder JSON reported `DIRTY_CHECKOUT` and exact owned paths, with no fallback identity. |
| Focused Ruff / format / mypy | PASS | Ruff clean on 7 files; mypy clean on 5 release source files. |
| Code Craft / Test Craft checks | PASS | 5 release Python files and 2 release test files clean. |
| Full suite excluding the clean-checkout builder test | PASS | 877 passed, 1 deselected, 1 pre-existing Starlette warning in 56.40s. |
| Application secret scan | BASELINE FAIL, no owned-code finding | Rescan found 10 pre-existing candidates and zero in owned paths; the deterministic hash fixture uses the scanner's allowlist pragma. |
| First PyInstaller comparison build | INVALIDATED | Host reported ARM64, but PyInstaller selected `Windows-64bit-intel` and bundled `win_amd64` extensions; the draft manifest's ARM64 label was false and the reference is discarded. |
| Python build-platform regression before fix | EXPECTED FAIL | With `sysconfig.get_platform() == win-amd64`, host-based detection returned `arm64`; detection now uses the Python/PyInstaller binary platform. |
| `pytest tests/test_release_integrity.py tests/test_release_packaging.py -q` | PASS | 29 passed in 8.24s from clean commit `31ad16f...`. |
| `pytest -q` | PASS | 880 passed, 1 pre-existing Starlette warning in 48.35s. |
| Repository Ruff / strict mypy / Vulture | PASS with noted baseline | Ruff lint passed; mypy passed on 129 files; Vulture passed. Owned-path format passed; repository-wide format remains red only on unchanged `src/quant_system/modeling/trials.py`. |
| Corrected reference build command | PASS | Native PyInstaller x86-64 artifact, 248 inventory files; `NOT_MEASURED` reference manifest. |
| Fresh final build with `-ReferenceManifest` | PASS | Manifest status `VARIANCE_DETECTED`: 245/248 identical; exact differences `_internal/base_library.zip`, `quantos.exe`, `sbom.json`. |
| Independent PE and manifest validation | PASS | PE machine `0x8664` (x86-64); all 248 manifest files verified. |
| Clean release harness | PARTIAL, not certification | 8/9 passed; existing reinstall cleanup failed because `_internal` remained. No certification claim. |
| `scripts/audit-agent-claims.ps1` | PASS | Every workspace has a visible claim and every claim resolves. |
| `scripts/audit-disk-layout.ps1` | PASS | No stray QuantOS directories. |

## Final artifact evidence

- Final commit: `31ad16f5828f7a626bd77d9993dc06fd917374c7` (`commit` object, clean worktree).
- Normalized `uv.lock`: `9c40ebf470a8c7021b849f72acdb23347e49a63053ecbd59e3832337d3a27498`.
- Final manifest: `1112daf68a6b32dc63c3e46c92b5748949a845f3e088d4097dc296648cf00d17`.
- Final executable: `f5d41ecd3d4a292e4ae4f8898343059495fcfbecae4aeaeb0c84e38893ed268b`.
- Final `base_library.zip`: `f7a1d7447bcd81d115030671b07a194a148c060ea85ff154aa81aa6ddceef997`.
- Final SBOM: `b842d16bc3c56438ce4fac8910380f312c0bb2693b048ec30aa0d8e5a9b1fd35`.
- Final portable ZIP: `a0e4796e43f5610602fc0c2d604627933438b3e6c5f8ca04c4ace5d64a480a10`.
- Reference manifest: `04097d2fbf9ed19b8c6560d71efa34f73d84585cce5f9e749149582445ad8a89`.
- Reference executable: `6b7d4e5e012a1583ff960e094b03a7eca62a59521152408bfcb014eee1552e40`.
- Reference `base_library.zip`: `d74e73abbc1087a40fc2a45779328389481c6752c1f260e5b82426fd1f15e318`.
- Reference SBOM: `b029b97851ccee237e7dcced03a3d837484218e67f44c9469aa3d0412a008f46`.
- Reference portable ZIP: `03129099ea2f841dc490437389932b93fcbb3a76cc132eafc1d5d8dc53021fca`.

## Files changed

- `src/quant_system/release/sbom.py`
- `src/quant_system/release/manifest.py`
- `src/quant_system/release/builder.py`
- `src/quant_system/release/__init__.py`
- `scripts/build-windows-release.ps1`
- `installer/quantos.spec`
- `tests/test_release_packaging.py`
- `tests/test_release_integrity.py` (new)
- This active work record in the install root and branch copy.

## Blockers and conflicts

No blocker to the requested repair or artifact. Release certification remains intentionally open:
the legacy clean-release harness passed 8/9 and the repository retains unrelated pre-existing
format and secret-scan findings outside this claim. The verifier record remains read-only and owns
only its own record plus `.launch/reports/VERIFIER-RELEASE.md`.

## Stop point

The fresh x86-64 bundle and reference evidence are retained in the claimed worktree. No `.launch`
state or verifier report was changed, and no certification was claimed.

## Next safe action

An independent verifier may inspect commit `31ad16f...`, the final `dist` bundle, the reference
under `build/repro-reference-dist`, and the recorded 8/9 clean-install harness failure. Do not
certify until the remaining release-wide findings are independently resolved and rerun.
