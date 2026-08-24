# Completed work: typed DSR two-point boundary repair

STATUS: COMPLETED
OWNER: Codex (founder-directed adoption)
TOOL: Codex
STARTED_UTC: 2026-08-24T10:00:09Z
COMPLETED_UTC: 2026-08-24T10:14:55Z
STARTING_REVISION: `412c21722ec0d44a18e73f26937a1d950a36a197`
HEAD_AT_COMPLETION: `deccec176c3791c010238f54452dacd00e212b14`
WORKTREE_OR_BRANCH: `D:\quant_system` on `main` (shared checkout; exact-path claim)

## Adoption authority

`src/quant_system/analytics/multiplicity.py` and its original test are claimed by
`20260820-codex-slice4-ridge-training.md`, still marked `ACTIVE` after four days. Two independent
notices (`20260822-NOTICE-dsr-two-point-boundary-crash.md` and
`20260823-NOTICE-dsr-boundary-corroborated-second-record.md`) independently reproduce a live
Blocker, ask the founder/coordinator to reassign the path, and state that neither author may touch
it. The immediately preceding founder exchange ended by requesting that reassignment; the founder
then instructed this Codex session to `continue`. This record treats that as explicit authorization
to adopt only the narrow DSR boundary repair. The original record is preserved and not edited.

## Objective

Make the Pearson moment-bound validation numerically correct for the exact-equality two-point
class, and make genuinely impossible moments fail through the governed typed failure contract
instead of escaping as a bare `ValueError`.

## Owned paths

- `src/quant_system/analytics/multiplicity.py`
- `src/quant_system/analytics/errors.py` (new)
- `src/quant_system/analytics/__init__.py`
- `src/quant_system/modeling/errors.py`
- `src/quant_system/modeling/validation.py`
- `tests/test_dsr_boundary.py` (new)
- `tests/test_multiplicity.py`
- `tests/test_modeling_validation.py`
- `tests/test_dsr_boundary.py` (new end-to-end persisted failure-code proof)
- `agent_context/work/active/20260824-codex-dsr-boundary-typed-repair.md`
- `agent_context/work/completed/20260824-codex-dsr-boundary-typed-repair.md`

## Shared-checkout boundary

The checkout contained staged execution changes and tests owned by
`20260823-claude-redteam-repair-b1-b3.md`; their owner committed and pushed them as `deccec1` while
this repair was running. This record did not edit, format, stage, reset, or otherwise touch them.
Verification stayed focused on owned paths plus read-only broader checks.

### Resolution of the concurrent UNKNOWN_OWNER observation

`20260824-UNKNOWN_OWNER-modeling-validation-cause-assertion.md` appeared during this run after a
second Codex continuation observed file timestamps moving. The changes it names are owned by this
record: this Codex session added the `__cause__` assertion, removed the now-redundant per-code
branch after the general analytics exception was narrowed to `MultiplicityError`, and removed the
temporary craft annotation before inlining the one-use row-index helper. The founder's `continue`
authorization and this record's pre-existing exact-path claim cover those edits. The UNKNOWN_OWNER
record is preserved and not edited; this section is the requested visible identification.

## Non-goals

- No change to DSR formulas, annualization, multiplicity counts, promotion thresholds, or the
  already-correct deflation-consumer wiring.
- No change to whether a mathematically valid two-point series is eligible for DSR; this repair
  only stops binary rounding from misclassifying exact equality.
- No generic conversion of every analytics `ValueError` into a modeling failure.
- No modification of the original owner record or either notice.

## Frozen contract

- Pearson's inequality is `kurtosis >= 1 + skewness**2`, with equality for a two-point
  distribution.
- A computed shortfall within a scale-aware multiple of binary64 machine epsilon is equality and
  must pass.
- A larger shortfall is impossible input and raises a typed analytics failure.
- The governed modeling adapter translates that specific failure to a stable
  `ModelingFailureCode`; it does not catch unrelated `ValueError` exceptions.
- A real two-point p=0.10 fixture must fail before the implementation change, pass after it, and a
  deliberately impossible moment pair must still fail.

## Plan

1. COMPLETE - write unit, governed-path, and persisted-outcome regressions.
2. COMPLETE - add scale-aware boundary comparison and typed analytics error.
3. COMPLETE - translate the typed error at the modeling boundary.
4. COMPLETE - mutation-kill tolerance removal and typed-translation removal.
5. COMPLETE - focused/full tests, static/craft checks, and both repository audits.

## Current step

Implementation, behavioral verification, repository audits, and final owned-diff review are
complete.

## Decision rationale

The analytics package cannot import `modeling.errors` without reversing the existing dependency
(`modeling.validation` already imports analytics). A typed analytics exception keeps dependency
direction one-way; `modeling.validation` translates only that exact code into the governed
`ModelingError` required by persisted trial outcomes. Making the analytics exception a
`ValueError` subclass preserves compatibility for callers that already reject invalid numeric
inputs via `except ValueError` while adding a stable machine-readable code.

The tolerance will be expressed in multiples of `sys.float_info.epsilon` and scaled by the Pearson
bound magnitude, rather than as an unexplained decimal. This is statistical floating-point logic,
not exact accounting state; the financial/model skills permit binary float under an explicit
tolerance and replay contract.

## Commands and outcomes

| Command | Result | Evidence/notes |
|---|---|---|
| Startup sequence and claim audit | PASS | install-root worktree only; `main`; staged execution changes preserved |
| Tolerance removal mutation | KILLED | four valid two-point parameter cases failed with `MOMENT_CONSTRAINT_INVALID` |
| Modeling translation removal mutation | KILLED | the governed regression failed on an escaping `MultiplicityError` |
| `pytest` focused DSR/modeling suites | PASS | 34 passed |
| `pytest -q --basetemp=tmp/pytest-codex-dsr-boundary` | PASS | 854 passed, one dependency deprecation warning |
| Ruff lint / format on owned Python | PASS | all checks passed; 8 files formatted |
| Mypy analytics + modeling | PASS | 29 source files |
| Repository-wide Mypy | PASS | 129 source files |
| Code Craft / Test Craft on owned paths | PASS | zero findings |
| Package import check | PASS | analytics and modeling import without a cycle |
| Agent-claims / disk-layout audits | PASS | every workspace claimed; no stray QuantOS paths |
| Repository-wide Ruff lint / format | OUTSIDE-SCOPE RED | only `tests/test_governed_execution_majors.py`, committed concurrently at `deccec1` by another active record, has import-order drift; owned files are clean |

## Files changed

- `src/quant_system/analytics/errors.py`: typed, `ValueError`-compatible multiplicity failure.
- `src/quant_system/analytics/multiplicity.py`: scale-aware Pearson-bound comparison and typed
  impossible-moment rejection.
- `src/quant_system/analytics/__init__.py`: public exports for the analytics failure contract.
- `src/quant_system/modeling/errors.py`: `MOMENT_CONSTRAINT_INVALID` governed failure code.
- `src/quant_system/modeling/validation.py`: translate typed analytics failures while preserving
  their cause; inline a one-use row-index helper to remain within the code-profile threshold.
- `tests/test_multiplicity.py`: two-point boundary matrix, one-ULP boundary, and impossible-pair
  regressions.
- `tests/test_modeling_validation.py`: typed translation and cause-preservation regression.
- `tests/test_dsr_boundary.py`: governed two-point and persisted terminal-code regressions.
- This work record.

## Blockers and conflicts

None for this repair. Repository-wide Ruff remains red solely on another agent's concurrently
committed `tests/test_governed_execution_majors.py`; this record did not edit or format that file.

## Stop point

Production and regression changes are implemented; the 854-test shared-checkout suite, strict
Mypy, owned Ruff/craft checks, and both repository audits are green. Nothing has been staged or
committed by this record.

## Next safe action

If the founder asks for a commit, stage only the eight owned Python/test paths and this completed
record; do not fold in the separate UNKNOWN_OWNER record. Independent recheck remains required
before citing this author-repaired Blocker as release-certified.
