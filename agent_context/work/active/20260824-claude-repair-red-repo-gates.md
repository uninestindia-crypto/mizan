# Repair the two red repository gates

TASK_ID: 20260824-claude-repair-red-repo-gates
AGENT: Claude Code (Opus 5)
STATUS: IN_PROGRESS
STARTED_UTC: 2026-08-24
STARTING_REVISION: `726e98b` (main, after the codex/real-journey-api merge)
WORKTREE_OR_BRANCH: D:\quant_system on main

## Objective

Founder-directed: repair the two repository gates left red after the merge —
`ruff format --check` (10 files) and `mypy src launcher.py scripts` (3 errors in 2 files).

## Ownership, established before editing

All 12 failing files are **clean in git** — committed by their owners, not uncommitted in-flight
edits. That materially changes the risk: reformatting a file someone has open and unsaved could
destroy work; reformatting a committed file cannot.

Claims were checked against **declared owned paths**, not mere mentions. My first grep matched my
own integration record because it *names* these files in its gate-attribution section; that was a
false positive and is why the check was redone.

| Class | Files | Basis for editing |
|---|---|---|
| **Unclaimed** | `scripts/cached_nifty50_io.py`, `scripts/run_cached_nifty50_ridge_campaign.py`, `tests/test_governed_bundle_binding.py`, `tests/test_governed_execution_majors.py` | no active record declares them |
| **Claimed by COMPLETE records** | `scripts/run_governed_shadow_session.py`, `src/quant_system/modeling/features.py`, `tests/test_governed_shadow_wiring.py`, `tests/test_governed_strategy.py` | PROTOCOL 5 — a COMPLETE record's paths are releasable; adopted for formatting only |
| **Claimed by an ACTIVE record** | `src/quant_system/modeling/__init__.py`, `persisted_trials.py`, `trials.py`, `tests/test_modeling_ridge.py` | all four claimed by `20260820-codex-slice4-ridge-training` (STATUS: ACTIVE) — see below |

### The Codex-claimed four

`20260820-codex-slice4-ridge-training.md` still reads `STATUS: ACTIVE`. Its owner has been
unreachable across this session; two peer sessions independently reported the same. The founder
stated they had resolved the Codex situation and then directed these gates be fixed.

Proceeding on that founder instruction, which PROTOCOL 8.3 accepts as the alternative to an owner
recording COMPLETED. Recording it explicitly because the claim is still visible as ACTIVE on disk,
and an auditor seeing these files change under a live claim deserves to find the reason here rather
than infer it. **Changes to those four are formatting only — no behaviour, no logic.**

## The mypy errors are real, not incidental

Both stem from annotations that defeat the checker rather than describe the code:

- `run_cached_nifty50_ridge_campaign.py:279` — `def _trial_start(...) -> object:`, so every use of
  the result is unchecked. That is what produces the two downstream errors at `:307` and `:335`.
- `cached_nifty50_io.py:188` — `results: Sequence[object]`, while the sibling function at `:229`
  already types the same data as `Sequence[universe_runner.InstrumentResult]`.

Annotating a value `object` silences the checker on every subsequent use of it. Both files are
unclaimed, so these are repaired properly rather than suppressed.

## Non-goals

- No repository-wide formatter run. Files are formatted by explicit path only, so nothing outside
  the failing set can be touched.
- No behaviour change to any Codex-claimed file.

## Outcome — both gates green

### mypy: three `object` annotations, not two

The reported "3 errors in 2 files" came from **three** lazy annotations, and the third was only
visible after fixing the first two:

1. `run_cached_nifty50_ridge_campaign.py:279` — `def _trial_start(...) -> object`
2. `cached_nifty50_io.py:188` — `results: Sequence[object]`
3. `run_cached_nifty50_ridge_campaign.py:330` — `def _successful_result(..., start: object, ...)`

Fixing 1 and 2 left one error, which I initially misread as a caller problem. It was not: the
`start` at the failing line is a *parameter* of a different function that was independently
annotated `object`. Annotating a value `object` silences the checker on every downstream use, so
each one hid the next. All three now carry `RidgeTrialStartV1` /
`Sequence[universe_runner.InstrumentResult]` — repaired, not suppressed. No `type: ignore` added.

### format: I fixed one file, not ten — corrected after measuring

`ruff format` was run against the ten failing paths only, never repository-wide, because PROTOCOL 4
forbids that while other agents are active and this checkout has several.

But the diff tells a different story from the tool output. Ruff reported "11 files reformatted",
yet `git diff` shows **only `src/quant_system/modeling/trials.py`** actually changed among the ten.
The other nine are byte-identical to HEAD.

The explanation is that the tree moved under me. HEAD advanced from my merge commit `726e98b`
through `9436b8d` to `c804e74` *while this task was running*, carrying other agents' commits —
`fix(modeling): canonicalize governed feature window` and
`fix(modeling): reject unordered feature windows` among them. Those owners fixed their own files
concurrently.

So my actual contribution to the format gate is **one file**, and nine were resolved by the people
who owned them. Recorded because the tool output would support a larger claim and the diff does
not, and the diff is the evidence.

### A defect I introduced and caught

Adding the `RidgeTrialStartV1` import broke ruff's import sort. Fixing that with `--fix` risked a
worse problem: these scripts import sibling modules that only resolve *after* a
`sys.path.insert`, so a reordering that hoisted an import above that line would pass every static
gate and fail at runtime. Verified by actually importing both modules afterwards rather than
trusting the linter — ruff placed the import correctly within the `noqa: E402` block, and
`_trial_start.__annotations__['return']` reads `RidgeTrialStartV1` at runtime.

## Gate

| Gate | Result |
|---|---|
| `ruff check .` | All checks passed! |
| `ruff format --check .` | **393 files already formatted** |
| `mypy src launcher.py scripts` | **Success, 138 source files** |
| Full suite, normal order | **929 passed** |
| Full suite, reverse file order | **929 passed** |
| (re-verified at `c804e74` after HEAD moved twice mid-task) | ruff clean, 394 formatted, mypy 138 |
| `audit-agent-claims.ps1` | PASS |
| `audit-disk-layout.ps1` | PASS |

Every gate this session can run is now green on the merged tree, which was not true before.

## Still not certified

Two gates named by the merge precondition remain unrunnable here: the OpenAPI contract gate has no
script in `scripts/`, and the real-browser gate needs a live server and browser harness. The
`474795f` PASS still certifies that revision, not this tree. A fresh adjudication of the merged
revision is still required before release use.

## Next safe action

Adjudication of the merged revision by a separate verifier, covering the two gates above.
