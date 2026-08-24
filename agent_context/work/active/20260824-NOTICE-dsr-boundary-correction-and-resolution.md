# NOTICE — correction to my p-sweep figure, and the DSR boundary Blocker is repaired

TASK_ID: 20260824-NOTICE-dsr-boundary-correction-and-resolution
AGENT: Claude Code (Opus 5)
STATUS: NOTICE (additive; no other record is edited)
DATE_UTC: 2026-08-24
CORRECTS: a figure I supplied that was folded into
`20260823-NOTICE-dsr-boundary-corroborated-second-record.md` and pushed at `d07b2e0`
CONCERNS ALSO: `20260822-NOTICE-dsr-two-point-boundary-crash.md`

Filed as a record rather than a message because the session I gave the wrong figure to
(`quant-system-0c`) is no longer running and its inbox is stale. A record outlives the session.

## 1. Correction — a figure of mine was wrong

I claimed that for a two-point distribution at `p=0.10`, `kurt - skew**2 = 0.999999999999999`, and
that the guard therefore **fired** at that value. That was wrong.

The error: I computed `kurtosis - skewness**2` and compared it to `1`. The guard evaluates
`kurtosis < 1.0 + skewness**2`. Those two forms round differently — the subtraction discards bits
the direct comparison keeps. **`p=0.10` did not fire.**

The corrected measurement, taken by importing the pre-repair module from `6a17d5e` and *calling*
it rather than reasoning about the expression:

- **37 of 99** two-point series over `p = 0.01..0.99` raised.
- Firing values included `0.04, 0.11, 0.14, 0.18, 0.19, 0.20, 0.21, 0.22, 0.24, 0.27, 0.32, 0.35`.
- `p=0.10` was **not** among them.

The finding's shape survives and is in fact stronger than either notice stated: this was not a rare
tie but roughly 37% of the legitimate two-point parameter space. Only my specific `p` value was
wrong. Any sentence in either notice resting on `p=0.10` should be read as corrected by this record.

Recorded because I verified another session's claims carefully and then introduced an error of my
own while doing it, and that error reached a committed record.

## 1b. Why two correct measurements disagreed — and why that is the real evidence

`quant-system-61` independently measured **39 of 99** where I measured **37 of 99**, with a partly
different list of firing `p`. Neither is wrong. They used a 100-sample construction; I used analytic
moments. Rather than pick a winner, I ran four constructions of the same mathematical class against
the same pre-repair module:

| construction | fired | share |
|---|---:|---:|
| A — analytic moments, values `[0, 1]` | 37/99 | 37.4% |
| B — 100-sample, values `[0, 1]` | 36/99 | 36.4% |
| C — analytic moments, values `[-3.5, 11.25]` | 40/99 | 40.4% |
| D — 1000-sample, values `[0, 1]` | 31/99 | 31.3% |
| 61's independent 100-sample | 39/99 | 39.4% |

Pairwise overlap of the firing sets is roughly half — A∩B 19, A∩C 24, A∩D 16, C∩D 15 — against set
sizes of 31 to 40. The *proportion* is stable near a third; *which* `p` values fire is not.

**Construction C is the decisive one.** Skewness and kurtosis are location- and scale-invariant, so
A and C describe the identical distribution family with identical moments. A transformation that
provably cannot change the mathematics changes which inputs get rejected. That is direct proof that
rejection was determined by float residue in the arithmetic path, not by any property of the
distribution being tested.

This is a stronger statement than either original notice made, and stronger than any single list.
It also means no list of firing `p` values should be treated as canonical — including mine.

## 2. The Blocker is repaired

`ac47d7c fix(modeling): repair DSR two-point boundary` landed after both notices were filed. It
does both halves that were asked for:

```python
pearson_bound = 1.0 + skewness**2
violates_pearson_bound = kurtosis < pearson_bound and not math.isclose(
    kurtosis,
    pearson_bound,
    rel_tol=_PEARSON_BOUND_REL_TOLERANCE,
    abs_tol=_PEARSON_BOUND_ABS_TOLERANCE,
)
...
raise MultiplicityError(MultiplicityFailureCode.MOMENT_CONSTRAINT_INVALID, ...)
```

Tolerance is `64 * sys.float_info.epsilon`. The raise is typed, so it can surface in
`failure_codes` rather than crashing a governed evaluation.

Verified against current HEAD by calling the public API:

| Check | Result |
|---|---|
| 99 two-point series, `p = 0.01..0.99` | **99 published, 0 crashed** |
| genuine violation, 0.5 below the bound | refused, `MultiplicityError` |
| genuine violation, 1e-9 below the bound | refused, `MultiplicityError` |
| test coverage | `test_two_point_moment_equality_is_not_rejected_by_binary_rounding`, `test_one_ulp_pearson_shortfall_is_treated_as_boundary_equality`, and an assertion on `MOMENT_CONSTRAINT_INVALID` |

The tolerance did not open a hole: a real violation one part in a billion below the bound is still
refused.

## 3. Trail note for whoever audits this later

I did not perform this repair and have never edited `src/quant_system/analytics/multiplicity.py`.
The founder states they handled it. Worth knowing when reading the trail:
`20260820-codex-slice4-ridge-training.md` still reads `STATUS: ACTIVE` and still lists that file
among its owned paths, so the claim was never formally released even though the file has changed.
That is an observation, not an accusation — recorded so a later reader is not puzzled by a file
moving under a live claim.

Both DSR notices can be closed RESOLVED, with the `p=0.10` detail corrected rather than carried
forward.
