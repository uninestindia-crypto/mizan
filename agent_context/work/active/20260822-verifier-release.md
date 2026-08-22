# WORK RECORD — Independent Release Verifier (final release adjudication)

STATUS: IN_PROGRESS
AGENT: Claude Code — Independent Release Verification (wrote none of this code)
STARTED_UTC: 2026-08-22
STARTING_REVISION (install root HEAD): 5067fa9e61d569bf31c5e37d83d4a8b318c7d808
BRANCH: main (install root); verification runs in a fresh DETACHED clone

## Objective

Independently adjudicate, from a clean clone, whether QuantOS's release claims are true:
all 12 slices complete, release candidate certified, 4 open program-level Majors.

## Non-goals

- No fixes, no repairs, no suggestions-as-edits. Adjudication only.
- No deletion/pruning of any workspace under D:\quant_system_workspaces\.

## OWNED_PATHS (install root)

- agent_context/work/active/20260822-verifier-release.md  (this file)
- .launch/reports/VERIFIER-RELEASE.md  (final report copy — the ONLY other install-root write)

Everything else is read-only to me. All measurement happens in my clone.

## Workspace

CLONE_PATH: D:/quant_system_workspaces/verification_clones/verify-release-9fbe01e-20260821-204442erification_cloneserify-release-9fbe01e-20260821-204442
CLONE_REVISION: 9fbe01ecf07dcdfbf2a07c835fb4109b66223d2e (detached; install-root HEAD moved 5067fa9 -> 9fbe01e during my run)
RESET: deleted .venv .coverage .mypy_cache .pytest_cache .ruff_cache tmp htmlcov dist build and all __pycache__
INSTALL: UV_PROJECT_ENVIRONMENT=.venv uv sync --frozen --extra dev --link-mode copy -> 47 packages, uv 0.12.5, CPython 3.13.15

## Claims under adjudication

1. Clean clone installs from frozen lock; full suite passes. Observe exact test count + coverage.
2. Ruff lint, ruff format --check, strict mypy all clean. Observe file counts.
3. Application secret scan reports zero candidates.
4. Every .launch/SLICE-*-EVIDENCE.md focused-suite claim reproduces.
5. Provenance: artifact-to-source tie; build-windows-release.ps1 + installer/quantos.spec reproducible.
6. Capability honesty: no live-money order path; user-facing claims match code.
7. Are the 4 open Majors in .launch/STATE.md genuinely closed?

## Verdicts settled so far

- CLAIM 1 (clean clone installs frozen; full suite passes): PROVEN for pass/fail.
  Observed: `483 passed, 1 warning in 68.64s`. Coverage TOTAL 10582 statements, 1406 missed,
  **86.71%** (not the 88.x% figures pinned in older evidence). Warning is a Starlette/httpx
  deprecation from fastapi.testclient.
- CLAIM 2 (ruff lint, ruff format --check, strict mypy clean): PROVEN.
  `ruff check .` -> All checks passed! ; `ruff format --check .` -> 279 files already formatted ;
  `mypy src launcher.py scripts` -> Success: no issues found in **112 source files**
  (LAUNCH-PROGRESS.md says 109; I observed 112).
- CLAIM 3 (application secret scan reports zero candidates): **DISPROVEN**.
  Using the exact regex from scripts/run-slice4-gates.ps1 line 68, detect-secrets 1.5.0:
  SECRET_CANDIDATE_COUNT=7 in application files ->
  src/quant_system/release/verifier.py:122 (1), src/quant_system/server/app.py:884,896,908,928 (4),
  tests/test_release_packaging.py:187,188 (2). All are "Hex High Entropy String" (hash literals),
  but the gate counts candidates and would `throw`. Gate criterion is not met at 9fbe01e.
  NOTE: the app.py hits are hardcoded `checksum_sha256=` literals with provenance="SYNTHETIC",
  status="VERIFIED" -> follow up under CLAIM 6 (capability honesty).

## Commands run (all inside the clone unless noted)

    git clone (via scripts/new-workspace-clone.ps1 -Purpose verify -Label release -Revision 9fbe01e)
    UV_PROJECT_ENVIRONMENT=.venv uv sync --frozen --extra dev --link-mode copy
    .venv/Scripts/python.exe -m pytest --cov=quant_system --cov-report=term-missing -q
    .venv/Scripts/python.exe -m coverage report --precision=2
    .venv/Scripts/python.exe -m ruff check .
    .venv/Scripts/python.exe -m ruff format --check .
    .venv/Scripts/python.exe -m mypy src launcher.py scripts
    detect-secrets scan --all-files --no-verify --exclude-files <regex from run-slice4-gates.ps1:68> .

WARNING for a successor: do NOT retype that exclusion regex by hand through a bash heredoc.
The harness collapses `\` to `\`, which silently turns `[\/]` into "forward slash only" and
produced 526 false candidates on my first attempt. Extract the line from the .ps1 file instead
(scratchpad helper: secretscan2.ps1 / secretscan3.ps1).

- CLAIM 4 (every SLICE-*-EVIDENCE focused-suite claim reproduces): PROVEN for the focused
  selections; but the DOCUMENTED SLICE GATE SCRIPTS THEMSELVES FAIL.
  Focused suites re-run in the clone:
    S1 tests/test_upstox_data.py + test_upstox_v3_acquisition.py -> 35 passed (claimed 35) OK
    S2 test_evidence_store/process_recovery/dataset_evidence -> 58 passed (claimed 58) OK
    S3 (gate script, pattern-based) -> 42 passed (evidence claims 41; suite grew) 
    S4 (gate script, 17 files) -> 138 passed (evidence claims 80 at superseded b24b4eb)
    S5 holdout+stress+promotion -> 15 passed (claimed 15) OK
    S6 test_server_api + test_server_supervisor -> 56 passed (claimed 56) OK
    S7 nse_rules+ledger+greeks+risk_governor -> 30 passed (claimed 30) OK
    S8 test_shadow_replay.py -> 25 passed (claimed 25) OK
    S9 test_realtime_shadow.py -> 12 passed (claimed 12) OK
    S10 test_paper_pilot.py -> 17 passed (claimed 17) OK
    S11 test_ui_journeys.py -> 23 passed (claimed 23) OK
    S12 test_release_packaging.py -> 16 passed (claimed 16) OK
  BUT: scripts/run-slice1..4-gates.ps1 ALL EXIT 1 at the Dead-code scan:
    src\quant_system
eleaseerifier.py:52: unused variable 'exc_info' (100% confidence)
    -> "Dead-code scan failed with exit code 3"
  They never reach the secret-scan step, which would also throw (7 candidates, CLAIM 3).
  Every one of the four documented slice gates is RED at 9fbe01e.

- CLAIM 5 (provenance: artifact tied to a source revision; reproducible artifact): **DISPROVEN**.
  a) The shipped bundle D:/quant_system/dist/QuantOS (244 files / 136,084,842 bytes = the exact
     figures SLICE-12-EVIDENCE cites) carries release-manifest.json + release.json stamping
     git_commit_sha=b5bc0617757e10919e76f40b609e11beb57eb2f6 (committed 2026-08-21 23:00:05 +0530),
     but QuantOS.exe mtime is 2026-08-20 05:27:19 - ~41h BEFORE that commit existed.
  b) Byte proof, not timestamps: substring counts inside the two executables
       clone-built quantos.exe : paper_pilot=1 realtime_shadow=1 promotion=1 quant_system.release=5
       shipped QuantOS.exe     : paper_pilot=0 realtime_shadow=0 promotion=0 quant_system.release=0
     The shipped artifact does not contain the Slice 5/9/10/12 modules it is certified for.
  c) The binding is unvalidated by construction: get_git_commit_sha() (release/sbom.py:53) returns
     $env:RELEASE_GIT_SHA verbatim if len>=7. Demonstrated: RELEASE_GIT_SHA=not-a-sha -> "not-a-sha".
     Fallback when git fails is the literal "unknown-git-revision". Nothing compares bundle bytes
     to the tree.
  d) uv_lock_sha256 is not a stable identity. Same commit 9fbe01e: install root uv.lock hashes
     9c40ebf4... (LF), a FRESH CLONE hashes 4c4a3a48... (CRLF, because .gitattributes `* text=auto`
     + core.autocrlf=true). SLICE-12-EVIDENCE pins 9c40ebf4... as the release identity.
  e) NOT reproducible. Two consecutive builds in the same clean clone/env
     (scripts/build-windows-release.ps1, exit 0 both times) differ:
       quantos.exe            c9054ea8a91ec368... != 63fc8c022bb93f21...
       _internal/base_library.zip 852474ccd9a79163... != 7c424c7387378039...
       sbom.json (generated_at) and the portable zip also differ.
       244 of 247 files identical; 3 differ.

## Next action

CLAIMS 1-5 SETTLED (1 PROVEN, 2 PROVEN, 3 DISPROVEN, 4 PROVEN-with-red-gates, 5 DISPROVEN).
NEXT: CLAIM 6 (capability honesty) - start at src/quant_system/server/app.py lines 860-940
(hardcoded checksum_sha256 / provenance="SYNTHETIC" / status="VERIFIED" responses), then grep every
order-placement path, then README + installer + UI copy. THEN CLAIM 7 (the four open Majors).
Finally write .launch/reports/VERIFIER-RELEASE.md in the clone and copy it to the install root.
