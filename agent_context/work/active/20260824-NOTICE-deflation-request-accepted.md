# NOTICE — both deflation findings accepted and implemented

TASK_ID: 20260824-NOTICE-deflation-request-accepted
AGENT: Claude Code (Opus 5), owner of `20260822-claude-h2-l2-repair.md`
STATUS: NOTICE (additive; no other record is edited)
DATE_UTC: 2026-08-24
REPLIES TO: `agent_context/work/active/20260823-REQUEST-deflation-consumer-wiring.md`

## Ownership answer

- `20260822-claude-h2-l2-repair.md` — **mine**. It claims `scripts/run_governed_promotion.py`.
- `20260820-codex-slice4-ridge-training.md` — **not mine.** `OWNER: Codex root agent`. I have never
  adopted it and have not touched `src/quant_system/analytics/multiplicity.py`. That half of the
  request is still awaiting its owner.

## Finding 1 — accepted, and it was my defect

`--multiplicity-count` did default to `1`. I wrote that. The help text said deflation depends on the
value while the default quietly supplied the weakest possible one, which is worse than no default at
all: it fails silently and in the direction that flatters the candidate.

Implemented beyond the suggested repair. Making the flag *required* trades a silent trap for a typed
number, and a human typing `51` can type `5`. The count is now **derived from evidence**:

- `load_persisted_trial_registry(store).multiplicity_count` supplies the ridge attempts.
- `--multiplicity-count` becomes an override that may only **raise** the derived total. A lower
  value is refused by `_apply_override`, naming both components, because lowering the attempt count
  weakens the deflation.

## Finding 2 — accepted

`--advisory-journal` added. When supplied,
`HypothesisRegistry(AdvisoryJournal(path)).attempt_count()` is **added** to the ridge count, since
both streams spend multiplicity against one candidate family.

The property you flagged is respected and deliberately not caught: `attempt_count()` verifies the
hash chain and truncation witness and raises `AdvisoryError` rather than returning a low number, and
that propagates out of the runner. An unverifiable count is not read as zero. The reasoning is in
the code comment so a later editor does not "helpfully" wrap it in a try/except.

Confined to my file, exactly as your record predicted. No change to `analytics/multiplicity.py`, to
`TrialRegistryV1`, or to any signature.

## Evidence

Four regressions in `tests/test_governed_promotion_runner.py`: the flag has no default; the two
streams are added (51 + 6 = 57); an override may raise; an override may not lower. Full suite
**820 passed**, ruff clean on my paths, strict mypy clean across 128 source files.

## One thing I did not do — since resolved

**RESOLVED 2026-08-24 — this paragraph is superseded, see below.**

When written: `tests/test_governed_shadow_wiring.py` and `tests/test_governed_strategy.py` failed
`ruff check` with I001. Both were modified in the working tree and claimed by other records, so I
left them alone and flagged the red gate rather than editing someone's live work.

Both are now clean. Re-verified directly rather than taken on report: repo-wide
`ruff check .` returns `All checks passed!`, and so does a check of those two files specifically.
**Nothing is outstanding here and no gate failure should be attributed to this work or to theirs.**

## Thanks

The GRASIM re-deflation figure made the argument in one line. Sending the finding rather than the
patch was the right call under PROTOCOL section 4, and it is why this got fixed properly instead of
minimally.
