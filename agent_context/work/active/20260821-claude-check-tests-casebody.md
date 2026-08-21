# Active work: check-tests.mjs multi-line signature defect

STATUS: HANDOFF_REQUIRED  
OWNER: Claude Code (Opus 5) session 21d82993  
TOOL: Claude Code  
STARTED_UTC: 2026-08-21T11:05:00Z  
STARTING_REVISION: `b24b4eb`  
WORKTREE_OR_BRANCH: `D:\quant_system` on `main`

## Objective

Fix `caseBody()` in `scripts/check-tests.mjs`, which truncates a test body at the first dedented
line and therefore reports a false `no-assertion` for every multi-line Python test signature. Remove
the `test-allow` annotations that only existed to work around it.

## Owned paths

- `scripts/check-tests.mjs`
- `scripts/check-code.mjs`
- `tests/test_data_provenance.py`
- `tests/test_daily_pipeline.py`
- `tests/test_server_api.py`
- `agent_context/work/active/20260821-claude-check-tests-casebody.md`
- `agent_context/work/completed/20260821-claude-check-tests-casebody.md`

## Non-goals

- Changing the rule set, thresholds, or severity model. Only body delimitation is wrong.
- Editing modeling tests or anything claimed by `20260820-codex-slice4-ridge-training.md` or
  `20260821-0530Z-claude-slice4-certification.md`.
- Suppressing any genuine finding the corrected checker surfaces. If the fix reveals real defects,
  they get reported, not annotated away.

## Plan

1. COMPLETE - measure the fix on a scratchpad copy before touching the shared file, per
   PROTOCOL section 4 and section 8.4.
2. COMPLETE - apply the fix and prove it against a purpose-built fixture.
3. COMPLETE - remove the now-unnecessary `test-allow` annotations.
4. COMPLETE - no notification owed: the Slice 4 gate scopes are byte-identical before and after.
5. COMPLETE - repair the same encoding defect in `check-code.mjs`, whose self-test also failed.
6. PENDING - founder review, then commit.

## Current step

Both checkers repaired, both self-tests green, all gate scopes unchanged. Nothing committed.

## Decision rationale

`scripts/check-tests.mjs` is shared gate tooling. `20260821-0530Z-claude-slice4-certification.md` is
actively preparing a clean-state gate baseline and its gate runs this checker over the modeling test
files. A corrected checker scans bodies it previously truncated, so it can surface findings that
were always latent. That would change another agent's gate result mid-certification, which is
exactly the situation section 8.4 governs. Measuring on a copy first costs little and keeps the
blast radius at zero until the impact is known.

### The defect

`caseBody()` collects lines after the `case` line and breaks at the first line whose indent is at or
below the declaration's, unless that line matches `/^\s*[})\]]*\s*$/` — purely closing brackets.
Python's signature terminator is `) -> None:`, which fails that test, so the body is truncated to
the parameter list. The parameter list contains no assertion, so every multi-line Python test
signature reports `no-assertion`.

Annotation-based languages (Java, Kotlin, C#) are unaffected because their `case` line is the
annotation and the signature follows while `body.length === 0`, which the existing guard permits.

## Commands and outcomes

| Command | Result | Evidence/notes |
|---|---|---|
| Read `caseBody()` and the `LANGS` table | PASS | Confirmed the guard and why only Python is affected. |
| Both versions on `tests/` (copy vs shared) | PASS | Identical: 11 findings in 6 files. No new findings repo-wide. |
| Both versions on the 12 Slice 4 gate test files | PASS | Clean in both. No impact on the active certification. |
| Both versions on a purpose-built fixture | PASS | Original 6 findings, all multi-line signatures regardless of content. Fixed 3, exactly the genuine ones. |
| `check-tests.mjs --self-test` before | FAIL | `allow: with reason`. Pre-existing on `main`, not caused here. |
| `check-tests.mjs --self-test` after | PASS | 14 extensions, 9 languages. |
| `check-code.mjs --self-test` before | FAIL | `allow: parses with reason`. Same pre-existing encoding defect. |
| `check-code.mjs --self-test` after | PASS | 27 extensions, 18 languages. |
| `check-code.mjs` on `src/quant_system`, copy vs shared | PASS | Identical 55 findings; only the garbled output text changed. |
| `pytest` (isolated basetemp and COVERAGE_FILE) | PASS | 272 passed. |
| `ruff format --check tests/`, `ruff check tests/` | PASS | 43 files formatted, all checks passed. |
| Slice 4 Code Craft and Test Craft scopes after | PASS | Both clean, byte-identical to before. |

### The fixture proof

The corrected checker did not merely stop over-reporting. On the fixture it found a `loop-in-test`
the original could not see, because the original never scanned past the parameter list. The defect
was suppressing genuine findings, not only inventing false ones.

## Files changed

- `scripts/check-tests.mjs`: `caseBody()` now recognises a declaration tail via `DECL_TAIL`, so a
  dedented line that merely finishes a signature (`) -> None:`, `) error {`) no longer truncates the
  body. Bare-closer behaviour and every rule, threshold, and severity are unchanged. Also undid the
  double-encoded UTF-8 and made the `test-allow` regex and its self-test use `—`/`–`
  escapes so the em-dash class cannot be corrupted by a future re-encoding.
- `scripts/check-code.mjs`: same encoding repair and the same `\u` hardening for `craft-allow`. No
  structural change; it has no `caseBody` equivalent.
- `tests/test_data_provenance.py`, `tests/test_daily_pipeline.py`, `tests/test_server_api.py`:
  removed 7 `test-allow: no-assertion` annotations that existed only to work around the defect.
  These files are clean with no annotation at all, which is the proof the fix works.

## Blockers and conflicts

None. The measurement showed the Slice 4 gate scopes are byte-identical before and after, so
section 8.4 requires no notice to `20260821-0530Z-claude-slice4-certification.md`.

That agent is concurrently editing `.launch/COMMANDS.md`, `.launch/SLICES.md`, `.launch/STATE.md`,
and `.launch/SLICE-04-EVIDENCE.md` in this shared checkout. Those are its claimed paths, untouched
and unstaged here.

## Stop point

Both checkers repaired and self-testing green. Seven workaround annotations removed. Working tree
holds four modified files plus this record. Nothing staged, nothing committed.

## Next safe action

Founder review, then commit exactly `scripts/check-tests.mjs`, `scripts/check-code.mjs`, the three
test files, and this record. Do not stage any `.launch/` path.
