# Active work: the integrity scanner skips what the read path refuses

STATUS: COMPLETED (verified, **uncommitted**, and not independently adjudicated)  
OWNER: Claude Code (Opus 5)  
TOOL: Claude Code  
STARTED_UTC: 2026-09-17T12:57:53Z  
STARTING_REVISION: `6ca45e1062cadb6e210cff240a9a01691e2e69b7`  
WORKTREE_OR_BRANCH: `D:\quant_system` (shared checkout). Audited and repaired on `main`; the work was
then committed on branch `claude/evidence-scanner-catalog-entry`, cut on founder instruction
("commit this"). The branch is mine. **It is not merged into `main` and not pushed** — neither was
instructed.

**The branch was cut at `9b12dd8c`, not at the `STARTING_REVISION` above.** The automated evidence
checkpoint `9b12dd8c sync: evidence checkpoint [2026-09-18 10:43:09 UTC]` landed on `main` partway
through this session. Checked rather than assumed: it touches **2,026 files, every one under
`data/`, 0 outside**, so no source or test file moved and every gate figure in this record still
describes the code being committed. The §8.4 safety measurement was re-taken at `9b12dd8c` because
the evidence tree itself changed underneath it — see the last two rows of the command table.

## Authorization

Founder instruction, 2026-09-17: "fix S1", following a line-by-line audit of
`src/quant_system/evidence/store.py` in this session that found and demonstrated the defect.

`src/quant_system/evidence/store.py` carries **five** ACTIVE claims (listed under "Blockers and
conflicts"). Without this instruction the path is not mine to touch. The repository has existing
precedent for this arrangement — `20260910-claude-ci-gate-green.md` repaired paths under other
claims on explicit founder instruction, and `20260915-0900Z-claude-paper-report-baselines.md` did
the same for `scripts/run_paper_pilot_session.py`.

## Objective

`EvidenceStore.rebuild_index()` / `scan_integrity()` must not report a store clean when
`list_verified()` cannot read it.

`_scan_resource_type` silently skips a non-directory entry in a catalog directory
(`store.py:285-286`, `if not resource_directory.is_dir(): continue`), while `list_manifests`
(`:160-163`) and `list_verified` (`:179-182`) treat the identical condition as a fatal
`EvidenceIntegrityError`. The scanner is therefore **more permissive than the read path it exists to
certify**, so a stray file in a catalog directory yields a clean integrity report on a store that
cannot be listed.

Demonstrated in this session on a fresh store with one stray file in `models/`:

```
rebuild_index() / scan_integrity():
   valid   : 0
   invalid : 0   <-- the stray file is NOT counted
   orphans : 0
   => reports a CLEAN store

list_verified(MODEL) on the same store:
   EvidenceIntegrityError: evidence catalog contains a non-directory entry: stray.txt
```

## Owned paths

- `src/quant_system/evidence/store.py` (`_scan_resource_type` only — no other function)
- `tests/test_evidence_integrity_scan_catalog_entries.py` (new)
- `agent_context/work/active/20260917-1257Z-claude-integrity-scanner-non-directory-entry.md` (this file)
- `agent_context/work/active/20260917-NOTICE-integrity-scanner-repair-under-five-claims.md` (new notice)

## Non-goals

- **No change to `list_manifests` or `list_verified`.** Their behaviour is the correct one; the
  scanner is being brought up to it, not the reverse. Relaxing the reader would be the wrong
  direction and would weaken a guarantee other records depend on.
- No change to `_publish`, `commit`, `set_active`, `recover`, or the lease.
- No change to `reject_symlink` or the Windows-junction observation (S2 in the audit). That is a
  separate finding with no demonstrated escape, and it is not what was authorized.
- No repository-wide formatter, generator, or `git add -A`.
- No commit or push unless separately instructed.

## Plan

1. Measure whether the change moves any pinned evidence number. — DONE
2. File this record before editing (PROTOCOL §2, §8.1). — DONE
3. Add a failing-first regression test (SLICES rule 3). — IN PROGRESS
4. Prove it fails against the unmodified code.
5. Apply the one-line repair.
6. Prove the test passes and the demonstration inverts.
7. Run the full gate: ruff, ruff format, strict mypy, full suite forward, craft checkers, both audits.
8. File the NOTICE for the five claim holders.

## Current step

Steps 1-6 and 8 are done. Step 7 is complete except the full forward suite, which is running at this
tree; the table below records it as NOT RUN until it returns, and this record must not be read as
green until that row is filled.

## Decision rationale

**Why the scanner is the side that moves.** `list_verified` refusing a catalog it cannot fully read
is the fail-closed behaviour this store is built on. The defect is that `scan_integrity` — the
function an operator or adjudicator runs to *confirm* health — is blind to a condition that breaks
reads. Reporting it as `invalid` makes the scanner's verdict a lower bound on readability, which is
the only useful direction for an integrity check.

**Why `invalid` rather than raising.** `_scan_resource_type` deliberately catches
`EvidenceIntegrityError` per resource (`:289`) and records the id in `invalid` so that one bad
resource does not hide the state of every other one. A stray entry belongs in exactly the same
bucket for exactly that reason. Raising would make `scan_integrity` unable to report on a store with
one stray file, which is worse than the current behaviour rather than better.

**Scope check against pinned evidence (PROTOCOL §8.4).** `.launch/reports/ADJUDICATION-TRAINING-PATH-20260911.md`
pins `scan_integrity()` returning "9 valid, 0 invalid, 0 orphan blobs" for `mizan-v1`, and other
records cite similar figures. Measured before editing: **103 catalog directories across
`data/evidence/`, 0 stray non-directory entries.** The repair therefore changes no committed store's
scan result and invalidates no pinned number. This is recorded because it is the precondition that
makes the change safe to merge, not because it was assumed.

**Symlinks were checked and are already consistent.** A symlink entry is not skipped: the scanner
reaches `open_verified` -> `_resource_directory` -> `_contained_path`, whose per-component
`reject_symlink` raises `EvidenceIntegrityError`, which `:289` catches and records as `invalid`.
Only the non-directory case diverges, so only it is changed.

## Commands and outcomes

| Command | Result | Evidence/notes |
|---|---|---|
| Stray-entry scan over `data/evidence/**` | **PASS** | 103 catalog directories, **0** stray non-directory entries; no pinned `scan_integrity` figure moves |
| Demonstration on a scratch store | **DEFECT REPRODUCED** | `scan_integrity` 0 valid/0 invalid/0 orphans while `list_verified` raises `EvidenceIntegrityError` |
| `pytest tests/test_evidence_integrity_scan_catalog_entries.py` **before** the repair | **13 failed, 1 passed** | Failing-first, as SLICES rule 3 requires. The 1 pass is the false-positive guard, which must pass in both states |
| `pytest tests/test_evidence_integrity_scan_catalog_entries.py` **after** | **14 passed** | 0.18s |
| `pytest` on the four neighbouring evidence suites | **56 passed** | `test_evidence_store.py`, `test_evidence_publish_atomicity.py`, `test_committed_evidence_integrity.py`, `test_modeling_evidence_tamper.py` |
| Demonstration re-run after the repair | **INVERTED** | `0 valid, 1 invalid ('stray.txt')`; `list_verified` still raises, unchanged |
| `mizan-v1` `scan_integrity()` after the repair | **UNCHANGED** | `valid=9 invalid=0 orphan=0`, matching the figure pinned in `.launch/reports/ADJUDICATION-TRAINING-PATH-20260911.md` |
| `ruff check .` | **PASS** | All checks passed |
| `ruff format --check .` | **PASS** | 691 files already formatted |
| `mypy src launcher.py scripts` | **PASS** | Success, 210 source files |
| `node scripts/check-code.mjs` | **UNCHANGED** | 1,082 findings / 174 files (356 checked, was 355). `src/quant_system/evidence/store.py` contributes 0 |
| `node scripts/check-tests.mjs` | **UNCHANGED** | 87 findings / 24 files (119 test files checked, was 118). The new test file contributes 0 |
| `scripts/audit-agent-claims.ps1` | **PASS** | exit 0 |
| `scripts/audit-disk-layout.ps1` | **PASS** | exit 0 |
| `pytest tests/ -q` (full, forward) | **PASS** | **1,601 passed in 824.59s**, exit 0. Baseline at session start on `6ca45e10` was 1,587 in 729.16s; +14 is exactly the regression file and no other test changed state |
| `pytest` reverse file order | **NOT RUN** | CI runs it as a separate job. Not run here; do not cite this work as reverse-order verified |
| Stray-entry scan, **re-run at `9b12dd8c`** | **PASS** | 103 catalog directories, **0** stray entries — unchanged after the 2,026-file evidence sync landed mid-session |
| `mizan-v1` `scan_integrity()`, **re-run at `9b12dd8c`** | **PASS** | `valid=9 invalid=0 orphan=0`, still matching the pinned adjudication figure |

## Files changed

- `src/quant_system/evidence/store.py`: one branch in `_scan_resource_type` — a non-directory catalog
  entry is recorded in `invalid` instead of skipped — plus a comment recording why it is recorded
  rather than raised.
- `tests/test_evidence_integrity_scan_catalog_entries.py` (new): 14 cases. The defect across all six
  catalog types, the scan/reader agreement property, proof that a stray entry does not hide the
  resources beside it (the reason for `invalid` over raising), and a false-positive guard.
- `agent_context/work/active/20260917-NOTICE-integrity-scanner-repair-under-five-claims.md` (new).

## Blockers and conflicts

`src/quant_system/evidence/store.py` is claimed by five ACTIVE records. Editing it is authorized by
founder instruction only; an additive NOTICE will be filed naming the exact change so each owner can
see it (PROTOCOL §3 forbids editing their records; §8.4 makes an additive notice the channel).

- `20260820-codex-slice4-ridge-training.md`
- `20260822-NOTICE-h2-l2-repair-affects-money-paths-redteam.md`
- `20260822-claude-h2-l2-repair.md`
- `20260822-redteam-money-paths.md`
- `20260911-NOTICE-governed-datasets-exceed-store-limits.md`

No pinned evidence number is invalidated — see the measurement above.

## Stop point

Repair applied, regression proven failing-first then passing, static gate and both audits green, and
the NOTICE filed. **Nothing is committed.** The working tree carries the three files under "Files
changed" plus this record, on top of the pre-existing `data/evidence` churn that was present at
session start and is not mine.

The full forward suite returned **1,601 passed, exit 0**. Every gate in the table above is green.

**The working tree is not clean and nothing is committed.** It carries the three files under "Files
changed" plus this record, on top of the pre-existing `data/evidence` churn that was present at
session start and is not mine. `scripts/daily_auto_sync.ps1` stages an allowlist of
`data/evidence` and `data/authorities` only (line 39-42, `git add -- $OwnedPaths` at :110), so the
23:00 sweep will **not** pick these files up. They persist until someone commits them deliberately.

## Next safe action

A claim owner or the founder decides whether to commit. If committed, note for whoever does:

**This change makes the CI forward-test job marginally worse, and that job is already red.** Run
`35178804781` at `6ca45e10` failed with "The job has exceeded the maximum execution time of 30m0s"
on `Tests (forward order)`, while reverse passed in 17m3s. The 14 added cases cost ~95s locally
(729s -> 825s, +13%). They are not the cause of the timeout and removing them would not fix it, but
they do consume headroom on a job that has none. The CI budget is the pre-existing problem; this is
a reason to address it, not a reason to withhold the repair.

Not done, and deliberately left to the founder or an owner:

- **No commit and no push.** Not instructed, and `store.py` is under five claims.
- **No independent adjudication.** I wrote the repair and its test, so I cannot certify them. The
  demonstration is reproducible from this record by anyone who wants to check it.
- **S2 from the same audit is untouched** — `reject_symlink` does not reject Windows junctions
  (`Path.is_symlink()` returns False for one, and `mklink /J` needs no privilege while `os.symlink`
  raised `OSError` on this machine). No escape was demonstrated: `_contained_path` resolves and
  re-checks containment, and the manifest-identity check at `store.py:138-139` catches an
  inside-root junction. Recorded as an observation about a guard that does not do what its name
  says on the target platform, not as a vulnerability, and not repaired here because it was not
  what was authorized.
