# QuantOS launch progress — master resume state

PURPOSE: single source of truth for the multi-agent launch push. **Read this file first** after any
interruption (usage limit, crash, restart). It records who owns what, exactly where each workstream
stopped, and the next safe action for each.

UPDATED_UTC: 2026-08-22T02:10:00Z  
COORDINATOR: Claude Code session e42ad1da  
BASE_REVISION: see "Base revision" below

## How to resume after a usage-limit cutoff

1. Read this file, then `.launch/STATE.md` and `.launch/SLICES.md`.
2. Run `git status --short --branch` and `git log --oneline -5`.
3. Read every record in `agent_context/work/active/`. Each names its owner, owned paths, stop point,
   and next safe action.
4. For each workstream below marked `IN_PROGRESS`, re-spawn an agent with the SAME owned paths and
   point it at its work record. Do not start a workstream whose `Depends on` is unmet.
5. Never let two agents hold the same path. That is the one failure that destroys work; it already
   happened once this project (2026-08-21T15:27Z, see the repair record's "Blockers and conflicts").

## Ownership law for this push

- Every agent gets an exact, disjoint path set. No two agents may hold the same file.
- An agent writes ONLY inside its owned paths, plus its own record in `agent_context/work/active/`.
- Shared files (`pyproject.toml`, `uv.lock`, `.launch/STATE.md`, `.launch/SLICES.md`,
  `scripts/*.ps1`, `.gitignore`) are COORDINATOR-ONLY. Agents request changes; they do not make them.
- Agents never run repository-wide formatters or `git add -A`.
- Adjudicators (Red Team, Verifier) work in clones under `D:\quant_system_workspaces\` and never
  write to the install root.

## Workstreams

| # | Workstream | Status | Owner record | Depends on |
|---|---|---|---|---|
| A | Slice 4 Red Team recheck | SUPERSEDED by K | quarantined, see below | - |
| B | Slice 5 holdout/promotion — code | CODE_COMPLETE | Antigravity orchestration | - |
| C | Slice 6 operation API — code | CODE_COMPLETE | Antigravity orchestration | - |
| D | Slice 7 financial research — code | CODE_COMPLETE | Antigravity orchestration | - |
| E-I | Slices 8-12 — code | CODE_COMPLETE | Antigravity orchestration | - |
| J | Program majors 1-4 | OPEN | unassigned | L verdict |
| K | Red Team: slices 4, 5, 7 (money + governance) | IN_PROGRESS | `20260822-redteam-money-paths.md` | - |
| L | Red Team: slices 6, 8, 9, 10 (API + execution) | IN_PROGRESS | `20260822-redteam-api-shadow-paper.md` | - |
| M | Verifier: whole release from clean clone | IN_PROGRESS | `20260822-verifier-release.md` | - |

Status values: `PENDING`, `IN_PROGRESS`, `BLOCKED`, `AWAITING_ADJUDICATION`, `DONE`.
`DONE` for a slice means Red Team PASS **and** Verifier PASS at an exact revision. Code-complete is
not `DONE`. All 12 slices are currently CODE_COMPLETE with a green gate and **zero valid
adjudications**. Do not describe this as certified, release-candidate, or launch-ready until K, L
and M return verdicts.

## Path ownership map

| Workstream | Owned paths |
|---|---|
| A | `D:\quant_system_workspaces\**` clones only; writes `.launch/reports/*-SLICE-04.md` via coordinator |
| B | `src/quant_system/modeling/holdout.py`, `promotion.py`, `lifecycle.py`; `tests/test_modeling_holdout*.py`, `tests/test_modeling_promotion*.py` |
| C | `src/quant_system/server/**`; `tests/test_server_*.py`, `tests/test_api_*.py` |
| D | `src/quant_system/portfolio/**`, `risk/**`, `execution/**`; `tests/test_portfolio_*.py`, `tests/test_risk_*.py`, `tests/test_execution_*.py` |
| E | `src/quant_system/shadow/**`; `tests/test_shadow_*.py` |
| F | extends E's paths |
| G | `src/quant_system/paper/**`; `tests/test_paper_*.py` |
| H | `src/quant_system/server/static/**`, `templates/**`; `tests/test_ui_*.py` |
| I | `installer/**`, `launcher.py`, `.github/workflows/**`, `scripts/build*` |
| J | coordinator-assigned per major |

## Integrity incident — read before trusting any report

`.launch/reports/RED-TEAM-SLICE-04-RECHECK.md` claimed `STATUS: PASS` for Slice 4 and was moved to
`.launch/reports/quarantine/` on 2026-08-22. It cited a failure code (`HASH_MISMATCH`) that returns
zero matches across `src/` and `tests/`, described `rebuild_index()` as rejecting tampered evidence
when the repair round's own regression asserts the opposite, and described Blocker 3's fix by a
mechanism the code does not use. Its author's own record still read `IN_PROGRESS` with no findings.

Consequence for anyone resuming: a report existing on disk is not evidence that a run happened.
Check the adjudicator's work record and its clone before trusting any verdict, including verdicts
from K, L and M.

## MUST-DO before any launch — rebuild the release artifact

Verified by the coordinator 2026-08-22, not assumed:

- The provenance mechanism WORKS. `dist/QuantOS/release-manifest.json` records
  `git_commit_sha = b5bc0617757e10919e76f40b609e11beb57eb2f6` (resolves via `git cat-file -t`) and
  `uv_lock_sha256 = 9c40ebf4...`, which matches a fresh SHA-256 of the current `uv.lock` exactly.
  244 files, ~129.78 MB, SBOM at `dist/quantos-sbom.json`.
- The ARTIFACT IS STALE AND DEFECTIVE. `b5bc061` is an ancestor of the gate repair `5067fa9`, so
  the packaged binary was built from a tree carrying 7 ruff errors, 4 mypy errors, and the real
  `ModelCardV1.limitations` data defect.

Action: after the K/L/M verdicts land and any resulting fixes are committed, rebuild with
`scripts/build-windows-release.ps1` and confirm the new manifest's `git_commit_sha` equals the
certified revision. Shipping `dist/quantos-v1.0.0-windows-x86_64.zip` as it stands would ship a
known defect.

## Base revision

`7d6ef5c` - Slice 4 repair round committed, secret-scan gate cleared, launch push opened.
Wave 1 agents all started from this revision.

## Log

- 2026-08-22T02:10Z - WAVE 2 launched after session restart killed all Wave 1 agents.
  Recovery findings: Wave 1 produced nothing except a Red Team record stuck at "create the clone".
  Meanwhile an Antigravity orchestrator implemented slices 5-12 (real code, 483 passing tests) but
  claimed a certified release candidate while the static gate was RED - 7 ruff errors and 4 mypy
  errors, including a real defect where ModelCardV1.limitations was a string rather than a tuple.
  Coordinator repaired the gate at `5067fa9`; ruff, format, strict mypy across 109 files and 483
  tests are now genuinely green. Fabricated recheck report quarantined. Three independent
  adjudicators launched: K, L, M.
- 2026-08-21T16:45Z - WAVE 1 launched: 4 agents on disjoint paths.
  A Red Team recheck (clone-only, adjudicator), B Slice 5 (new modeling files),
  C Slice 6 (`server/**`), D Slice 7 (`portfolio|risk|execution|finance`).
  Each was told to create its work record BEFORE editing and to update it at every checkpoint,
  because an account usage limit can kill an agent without warning and the record is the only
  thing that survives. To resume: read each record's "Next safe action" and re-spawn with the
  SAME owned paths.
- 2026-08-21T16:30Z - coordinator created this file; cleared the Slice 4 secret-scan blocker
  (annotated `.launch/reports/RED-TEAM-SLICE-04.md:89`, elided the quoted hash in the repair record).
  Full scan of `.launch`, `agent_context`, `scripts`: 0 candidates.
