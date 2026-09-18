# Active work: the symlink guard does not see Windows junctions, and `recover()` escapes through one

STATUS: COMPLETED (verified, **uncommitted**, and not independently adjudicated)  
OWNER: Claude Code (Opus 5)  
TOOL: Claude Code  
STARTED_UTC: 2026-09-18T11:37:02Z  
STARTING_REVISION: `b6b1c93da2de9b10f5d804e46ed95645044e2918`  
WORKTREE_OR_BRANCH: `D:\quant_system`, branch `claude/evidence-reject-reparse-points` (shared
checkout). Branch is mine; per PROTOCOL §8.3 nobody else should remove it.

## Authorization

Founder instruction, 2026-09-18: "now fix S2", following the `evidence/store.py` audit earlier in
this session. `src/quant_system/evidence/store.py` and `io.py` sit under five active claims (listed
under "Blockers and conflicts"); without this instruction neither is mine to touch.

## A correction to my own audit, made before anything else

The audit that produced S2 reported it as **"an observation, not a vulnerability"** and said: *"I
could not construct an escape, and the finding should not be read as one."* That reasoning was that
`_contained_path` resolves and re-checks containment behind every `reject_symlink` call.

**That was wrong, and the error was mine.** `recover()` (`store.py:186-201`) builds `staging_root`
and `quarantine` directly from `self.root`, not through `_contained_path`, so `reject_symlink` is
the *only* containment guard on that path. Demonstrated on a scratch store whose
`quarantine/staging` was a junction to a sibling directory:

```
recover() -> quarantined_staging_count = 1
inside  root  quarantine/: ['staging']
OUTSIDE the root         : ['stagedwork-aba62d97b8ca49c8a9d1914da8b14050']
content escaped intact   : 'staged evidence'
```

The store reported a successful quarantine while writing staged evidence **outside its configured
root**, bytes intact. This is a containment escape, not a naming inconsistency, and the severity in
the audit is hereby raised.

## Objective

`reject_symlink` must refuse every reparse point, not only the subset `Path.is_symlink()` reports.

On Windows — this project's stated build target — `Path.is_symlink()` returns `False` for a junction
created with `mklink /J`. Measured on this machine: the junction's `st_file_attributes` is `0x410`
with `FILE_ATTRIBUTE_REPARSE_POINT` (`0x400`) set and `st_reparse_tag` `0xa0000003`
(`IO_REPARSE_TAG_MOUNT_POINT`), while `is_symlink()` is `False`. Creating a **symlink** on this
machine raised `OSError` for want of `SeCreateSymbolicLinkPrivilege`; creating the **junction**
required no privilege at all. So the redirection an unprivileged user can actually create on the
target platform is precisely the one the guard does not see.

## Owned paths

- `src/quant_system/evidence/io.py` (`reject_symlink` only)
- `tests/test_evidence_reparse_points.py` (new)
- `agent_context/work/active/20260918-1137Z-claude-reject-reparse-points.md` (this file)
- `agent_context/work/active/20260918-NOTICE-reparse-point-guard-under-five-claims.md` (new notice)

## Non-goals

- **No change to `recover()`, `_contained_path`, or any other function.** Repairing the guard closes
  this escape at every call site at once. Routing `recover()` through `_contained_path` as well would
  be defence in depth and is worth considering, but it is a second change to a claimed file and was
  not what was authorized. Recorded under "Next safe action" instead.
- No change to `list_verified`, `list_manifests`, `commit`, `_publish`, `set_active`, or the lease.
- No repository-wide formatter, generator, or `git add -A`.
- No merge or push unless separately instructed.

## Plan

1. Reproduce the escape and correct the audit's severity. — DONE
2. Verify the detection mechanism on a real junction. — DONE
3. File this record before editing (PROTOCOL §2, §8.1). — DONE
4. Write failing-first regressions, including the `recover()` escape itself. — DONE
5. Prove they fail at `b6b1c93d`. — DONE
6. Repair `reject_symlink`. — DONE
7. Prove they pass and the escape is closed. — DONE
8. Full gate: ruff, format, strict mypy, full suite forward, craft, both audits. — DONE
9. File the NOTICE for the claim holders. — DONE

## Current step

All nine steps are done. Every gate in the table below is green.

## Decision rationale

**Why the attribute bit and not `st_reparse_tag`.** Testing the tag would require enumerating which
tags are dangerous, and the list is open-ended — junctions, mount points, OneDrive placeholders,
dedup, WSL, and whatever Windows adds next. `FILE_ATTRIBUTE_REPARSE_POINT` is the property the guard
actually wants: *this directory entry is a redirection.* Refusing all of them is the fail-closed
reading, and evidence paths have no legitimate need for any reparse point.

**Why not resolve-and-compare.** `path.resolve() != path` would catch redirection but also fires on
ordinary things — a root given as a relative path, `8.3` short names, a case difference — so it would
reject healthy stores. The attribute bit tests the actual condition rather than a proxy for it.

**Missing paths must stay silent.** `reject_symlink` is called on paths that may not exist —
`read_bounded` calls it before opening, and relies on `FileNotFoundError` from the *open* to produce
its own typed message. `Path.is_symlink()` returns `False` for a missing path rather than raising, so
the new check swallows `OSError` and returns, preserving that exactly.

**Portability.** `st_file_attributes` exists only on Windows `os.stat_result`, so it is read with
`getattr(..., 0)`; `stat.FILE_ATTRIBUTE_REPARSE_POINT` is defined on every platform in CPython's
`stat` module (verified: `0x400`). On POSIX the new branch is therefore inert and `is_symlink()`
keeps doing the work.

## Commands and outcomes

| Command | Result | Evidence/notes |
|---|---|---|
| `recover()` against a junctioned `quarantine/staging` | **ESCAPE REPRODUCED** | `quarantined_staging_count=1`, content written outside the root with bytes intact |
| Detection probe on a real junction | **CONFIRMED** | `is_symlink()=False`, `st_file_attributes=0x410`, REPARSE bit set, tag `0xa0000003` |
| `os.lstat` on a missing path | **FileNotFoundError** | the guard must swallow this and return |
| `pytest tests/test_evidence_reparse_points.py` **before** the repair | **2 failed, 2 passed** | Failing-first. The two passes are the over-rejection and missing-path guards, which must hold in both states |
| `pytest tests/test_evidence_reparse_points.py` **after** | **4 passed** | |
| Five neighbouring evidence suites | **70 passed** | store, publish atomicity, committed integrity, catalog entries, modeling tamper |
| Escape demonstration re-run after the repair | **CLOSED** | `recover()` raises `EvidenceIntegrityError: reparse points are forbidden in evidence paths: staging`; OUTSIDE empty; staged dir left in place |
| `ruff check .` / `ruff format --check .` | **PASS** | 695 files |
| `mypy src launcher.py scripts` | **PASS** | 210 source files |
| `node scripts/check-code.mjs` | **BASELINE** | 1,082 findings / 174 files (357 checked, was 356). `io.py` contributes 0 |
| `node scripts/check-tests.mjs` | **BASELINE** | 87 findings / 24 files (120 checked, was 119). The new file contributes 0 |
| `scripts/audit-agent-claims.ps1` / `audit-disk-layout.ps1` | **PASS / PASS** | exit 0 / exit 0 |
| `pytest tests/ -q` (full, forward) | **PASS** | **1,605 passed in 672.53s**, exit 0. Baseline at `b6b1c93d` was 1,601; +4 is exactly the new file and no other test changed state. Run against the final tree — an earlier run was stopped because it predated the test-file edits |
| `pytest tests/test_evidence_process_recovery.py` | **6 passed** | `recover()` has no production caller; it is exercised only by tests, so the change from "silently moves" to "raises" breaks no caller |
| `pytest` reverse file order | **NOT RUN** | CI's separate job; do not cite this as reverse-order verified |

## Craft findings raised by this work, and how each was resolved

The first draft of the test file added three findings (87 -> 90). Two were fixed rather than
annotated, because the checker's objection was correct:

- Two `no-assertion` cases proved only that a call did not throw. Folded into
  `test_the_guard_separates_a_junction_from_an_ordinary_entry`, which asserts **both** sides — a
  repair that rejected everything would have passed the one-sided version — and into
  `test_a_missing_path_still_reports_absence_rather_than_a_reparse_error`, which asserts through
  `read_bounded` that an absent file still reports `is missing` rather than a reparse error. That is
  the contract the swallowed `OSError` actually protects.
- One `skipped-test` on the `pytest.skip` inside `_make_junction` is annotated, not removed: it is
  conditional on the filesystem supporting junctions, never fires on CI, and the alternative is a red
  suite on a machine that cannot exercise the case. The annotation had to sit on the line
  immediately above the `pytest.skip` — `check-tests.mjs:248-252` looks only at that line and the
  flagged one, which cost two wrong placements to discover.

Net effect on the baseline: **zero**.

## Files changed

- `src/quant_system/evidence/io.py`: `reject_symlink` now refuses any entry carrying
  `FILE_ATTRIBUTE_REPARSE_POINT`, with the rationale in the docstring; `import stat` added.
- `tests/test_evidence_reparse_points.py` (new): 4 cases — the guard refusing a junction, the
  `recover()` escape driven through the public API, the accept/refuse discrimination, and the
  missing-path contract asserted through `read_bounded`.
- `agent_context/work/active/20260918-NOTICE-reparse-point-guard-under-five-claims.md` (new).

## Blockers and conflicts

`src/quant_system/evidence/io.py` and `store.py` are claimed by five ACTIVE records. Editing is
authorized by founder instruction only; an additive NOTICE will name the exact change (PROTOCOL §3
forbids editing their records, §8.4 makes a notice the channel).

- `20260820-codex-slice4-ridge-training.md`
- `20260822-claude-h2-l2-repair.md`
- `20260822-redteam-money-paths.md`
- `20260822-NOTICE-h2-l2-repair-affects-money-paths-redteam.md`
- `20260911-NOTICE-governed-datasets-exceed-store-limits.md`

**CI cannot verify this work.** The gate is red for billing — see
`20260918-NOTICE-ci-billing-failure-has-recurred.md`. Every figure below is a local measurement by
one agent on one machine, which is the thing CI exists to stop anyone relying on.

## Stop point

Repair applied, the escape demonstrated closed through the public API, every gate green, and the
NOTICE filed.

The `data/evidence` churn in the tree is not mine and was left alone.
`scripts/daily_auto_sync.ps1` stages an allowlist of `data/evidence` and `data/authorities` only
(`:39-42`, `git add -- $OwnedPaths` at `:110`), so the 23:00 sweep will not pick them up.

**Committed on founder instruction as `263ee286` on branch `claude/evidence-reject-reparse-points`,
cut from `main` at `b6b1c93d`.** Exactly four paths were staged by name — PROTOCOL §4 forbids
`git add -A` in a shared checkout — and the `data/evidence` churn in the tree was left untouched
(0 of it staged, checked). The commit is 4 files, 496 insertions, 0 deletions.

A follow-up commit `d787a733` recorded the branch and hash in this record and the NOTICE.

**Fast-forwarded into `main` and pushed on founder instruction, 2026-09-18: `b6b1c93d..d787a733`.**
No merge commit; `main` was in sync with `origin/main` at `b6b1c93d` and the branch was 2 ahead /
0 behind. Re-verified on `main` before pushing: 69 passed across the new regression,
`test_evidence_store.py`, `test_evidence_process_recovery.py` and the catalog-entry suite; ruff
clean; strict mypy clean over 210 files. The NOTICE carries the `WORKTREE_OR_BRANCH` claim so `scripts/audit-agent-claims.ps1`
can see the branch with this record in `work/completed/` — the trap that made that audit exit 1
during the S1 repair earlier today.

## Next safe action

Nothing is required. Open items, none of them blocking:

Open, none of it blocking:

- **`recover()` should also route its paths through `_contained_path`**, so containment there does
  not rest on a single guard. Repairing `reject_symlink` closes the demonstrated escape, but
  `recover()` remains the one place in the store where a path is built without the
  resolve-and-recheck that backs every other call site. A second change to a claimed file, not
  authorized here.
- **No independent adjudication.** I wrote the repair, its tests, and the demonstration that
  motivates it, so I cannot certify any of them. The escape and its closure are both reproducible
  from this record.
- **CI has verified none of this** — the gate is red for billing
  (`20260918-NOTICE-ci-billing-failure-has-recurred.md`). Reverse file order has never been run
  against this change by anyone.
