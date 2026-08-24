# NOTICE: untyped ValueError escapes governed evaluation on a two-point return series

STATUS: **REPAIRED at `ac47d7c` by another agent; independently verified here 2026-08-24.**
Retained as the finding record. Originally a NOTICE for the owners of
`src/quant_system/analytics/multiplicity.py` and `src/quant_system/modeling/validation.py`.  
RAISED_BY: Claude Code — real-data training runner  
RAISED_UTC: 2026-08-22T20:10:00Z  
REVISION: `8045575`  
SEVERITY: proposed **Blocker** — a legal real-data input crashes a governed evaluation with an
exception no caller can type-match, and the outcome is decided by floating-point rounding.

This is an additive notice. PROTOCOL §3 forbids editing another agent's record, and
`analytics/multiplicity.py` is claimed by `20260820-codex-slice4-ridge-training.md` while
`modeling/validation.py` is claimed by that record and by
`20260821-1048Z-claude-slice4-redteam-repair.md`. **Nothing was changed in either file.**

## CLOSED — repaired and independently verified

`ac47d7c fix(modeling): repair DSR two-point boundary`. I did not write that repair, so this
verification is independent of it, though not a substitute for a Red Team pass.

Both halves of the suggested direction landed. The guard now compares against the Pearson bound with
a relative and absolute tolerance, and raises a typed
`MultiplicityError(MultiplicityFailureCode.MOMENT_CONSTRAINT_INVALID)` instead of a bare
`ValueError`.

Verified against the exact cases this notice recorded:

| Case | Before | Now | `kurt - bound` |
|---|---|---|---|
| 29×`0.0` + 1×`0.05` | **REJECTED** | ACCEPTED, DSR 0.228402 | `-7.105e-15` |
| 62×`0.0` + 1×`0.0123456789` | accepted | ACCEPTED, DSR 0.245463 | `+7.105e-15` |
| two-point p=0.10 | see correction below | ACCEPTED, DSR 0.286697 | `+0.000e+00` |
| two-point p=0.30 | — | ACCEPTED, DSR 0.292213 | `+0.000e+00` |
| two-point p=0.50 | — | ACCEPTED, DSR 0.294801 | `+0.000e+00` |

And the guard still does its actual job: `skewness=2.0, kurtosis=1.0` — four below the bound, a
genuinely impossible pair — is refused with `MOMENT_CONSTRAINT_INVALID`. The tolerance admits the
exact-tie class without admitting real inconsistency, which was the whole question.

### Correction: how much of the two-point space actually fired

An earlier version of this section said p=0.10 was "rejected per peer sweep". **That was wrong, and
it was my error to write it** — I took a peer's figure and recorded it as established without
measuring it. `quant-system-bf` then corrected their own claim: they had computed
`kurt - skew**2` and compared to 1, whereas the guard evaluates `kurtosis < 1.0 + skewness**2`, and
those two round differently.

Measured here directly against the pre-repair condition, two-point series over p = 0.01..0.99:

- **39 of 99 would have fired — 39.4% of the legitimate two-point parameter space.**
- p=0.10 was **not** among them.
- bf's independent run gave 37 of 99 with a partly different p-list.

The disagreement in the exact list is the most useful part. Both runs test the same mathematical
class, and both find roughly the same *proportion* firing, but they disagree on *which* p values —
because the outcome is decided by float residue in a particular series construction, not by p. That
is direct evidence for the framing this notice already argued: the guard was classifying an exact
tie by rounding noise.

The finding was therefore **stronger** than either notice originally stated. This was never a rare
boundary tie; it rejected roughly two fifths of a legitimate class. Only the specific p value was
wrong.

The original notice follows unchanged, as the record of what was found and why.

## What happens

`evaluate_governed_ridge_fold` -> `deflate_ridge_report` -> `OverfittingDiagnostics.deflated_sharpe_ratio`
-> `_validate_dsr_inputs` raises a bare `ValueError`:

```
ValueError: kurtosis is inconsistent with the supplied skewness
```

Guard: `analytics/multiplicity.py:92` — `if kurtosis < 1.0 + skewness**2: raise ValueError(...)`.
Inputs: `modeling/validation.py:_return_moments` (population moments, `m3/m2**1.5` and `m4/m2**2`).

## STRENGTHENED 2026-08-23 — this is an exact identity, not a near miss

Corroborated and sharpened by `20260823-NOTICE-dsr-boundary-corroborated-second-record.md`
(agent quant-system-0c), then re-verified independently here before amending.

The original framing below said a two-point series "lands exactly on" the boundary and that float
rounding decides. That understates it. **For any two-point distribution, `kurtosis - skewness**2 = 1`
is an exact algebraic identity.** The bound `kurtosis >= 1 + skewness**2` holds for every
distribution, with equality *if and only if* the distribution is two-point.

Verified here across varying probability, values and sample size:

| n | p(high) | low | high | skewness | kurtosis | kurt - skew² |
|---:|---:|---:|---:|---:|---:|---:|
| 100 | 0.50 | 0.0 | 1.0 | 0.000000 | 1.000000 | **1.000000000000** |
| 100 | 0.30 | -2.5 | 7.25 | 0.872872 | 1.761905 | **1.000000000000** |
| 63 | 0.02 | 0.0 | 0.0123 | 7.747008 | 61.016129 | **1.000000000000** |
| 40 | 0.33 | 5.0 | -3.0 | -0.747265 | 1.558405 | **1.000000000000** |
| 1000 | 0.44 | 0.001 | -0.002 | -0.254025 | 1.064528 | **1.000000000000** |

Three-point, for contrast: `kurt - skew² = 1.528679`, strictly greater.

**Why this changes the repair.** `multiplicity.py:92` tests a *strict* inequality against an *exact
tie*, for an entire legitimate class of input — not for a value that happens to land near a limit.
A comparison tolerance is therefore not a workaround; it is the correct implementation of the
constraint the guard is trying to express. The `-7.105e-15` / `+7.105e-15` measurements recorded
below are exactly what that predicts, rather than the surprise they were originally written up as.

**Scope discipline.** No later change made this reachable; it has been reachable since `6a17d5e`.
Where downstream work raises the multiplicity count, that changes the *number of draws* against an
untyped crash, not the failure mode, and not whether the deflation is reached. State it that way if
citing this.

## Why the guard is reachable, and why it is a boundary problem

For any real sample, `kurtosis >= skewness**2 + 1` holds mathematically, with **equality exactly
when the series takes only two distinct values**. A validation return series is two-point whenever
the candidate takes a position at one distinct outcome level and is flat otherwise —
`_portfolio_period_returns` (`validation.py:402`) writes `0.0` for every period with no `UP`
prediction, so this is not exotic, it is the common shape of a low-activity candidate.

At that boundary the comparison is decided by float rounding, not by the data. Measured:

| series | skewness | kurtosis | bound `1+s²` | `kurt - bound` | rejected |
|---|---:|---:|---:|---:|---|
| 62×`0.0` + 1×`0.0123456789` | +7.747008 | 61.016129 | 61.016129 | `+7.105e-15` | no |
| 62×`0.0` + 1×`-0.00987` | -7.747008 | 61.016129 | 61.016129 | `+1.421e-14` | no |
| **29×`0.0` + 1×`0.05`** | **+5.199469** | **28.034483** | **28.034483** | **`-7.105e-15`** | **YES** |
| 60×`0.0` + `0.01,0.02,-0.015` | +2.092680 | 26.087295 | 5.379311 | large | no |

Identical mathematical situation, opposite outcomes, decided at the 15th decimal place.

## Observed in a real run

NIFTY 50 campaign, 2024-01-01..2025-12-31, evidence store `tmp/real-training-evidence`. One
constituent (the name processed immediately after `SBIN`, multiplicity ordinal 41) crashed the
sweep. 41 trials had already been committed; names 41-50 never ran until the driver was patched to
catch it.

## Why this is worse than a rejection

The stack already handles the *adjacent* case correctly and deliberately: zero variance raises a
typed `ModelingError(DEGENERATE_RETURN_SERIES)` with a docstring explaining exactly why publishing a
0.5 probability for a non-trading candidate would be wrong. The two-point case is one step away and
escapes as an untyped `ValueError`.

Consequences:

1. No caller can distinguish it from a genuine bug. `run_governed_ridge_training.py` catches
   `ModelingError` and `EvidenceError`; this passes through both.
2. It is not in `ModelingFailureCode`, so it cannot appear in `failure_codes` on a trial outcome as
   itself. `run_persisted_ridge_trial` does commit a terminal FAILED outcome before re-raising, so
   the evidence store stays consistent — but the recorded code is the generic
   `TRIAL_EXECUTION_FAILED`, which loses the diagnosis.
3. Reproducibility is not guaranteed. Two runs over data differing in the last bits could disagree
   about whether the same candidate is evaluable.

## What this notice does NOT claim

It does not claim the guard is wrong. `kurtosis < 1 + skewness**2` genuinely indicates impossible
moments and should be rejected when it reflects a real inconsistency. The finding is that a
**mathematically valid** boundary input is being classified by float noise, and that the failure is
untyped.

## Suggested direction, for the owners to accept or reject

Not implemented here — these are their files.

- Compare against the bound with a small relative tolerance so exact-equality two-point series are
  admitted rather than rejected by rounding, and
- give the genuinely-inconsistent case a typed `ModelingFailureCode` so it fails closed the way
  `DEGENERATE_RETURN_SERIES` already does, instead of raising `ValueError`.

Whether a two-point series *should* yield a publishable deflated Sharpe at all is a research
question, not a coding one. If the answer is no, the right outcome is still a typed rejection.

## Reproduction

```bash
uv run python -c "
def moments(v):
    n=len(v); m=sum(v)/n; d=[x-m for x in v]
    s2=sum(x**2 for x in d)/n
    return (sum(x**3 for x in d)/n)/s2**1.5, (sum(x**4 for x in d)/n)/s2**2
sk,ku = moments([0.0]*29+[0.05])
print(sk, ku, 1.0+sk**2, ku < 1.0+sk**2)
"
```

Prints `True` for the rejection condition on a series that is mathematically at equality.

## Evidence in the store

`tmp/real-training-evidence`, multiplicity ordinal 41, terminal outcome committed `FAILED` with
`TRIAL_EXECUTION_FAILED`. That trial start and outcome are immutable and count toward the campaign
multiplicity, which is correct.
