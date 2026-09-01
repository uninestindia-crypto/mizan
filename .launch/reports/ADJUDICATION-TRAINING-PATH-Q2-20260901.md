# Adjudication: Q2 of the training-path brief, answered with the true return-series moments

DATE_UTC: 2026-09-01
BY: Claude Code, `20260901-1030Z-claude-seven-item-sweep.md`
BRIEF: `.launch/ADJUDICATION-BRIEF-TRAINING-PATH.md`, question 2
REVISION: `2adf2f88`

## Independence, stated first

I did **not** write the training runner, either campaign driver, the promotion pipeline, or any of
the research results. Everything below is read from the evidence store, not from any record.

What I am not: an independent *tool*. The brief was prepared by a Claude Code session and this is
another one. A verdict from a different vendor's agent, or a human, remains worth more than this.
**This is not a PASS and does not certify the training path.** It closes one question.

## What Q2 asked

The brief answered Q2 -- "is the `0.217695` re-deflation real, or only a claim?" -- by approximating
the return-series moments as normal (`skew=0, kurt=3`), because "the return series are not in the
manifests". It reported `0.250826` and flagged the result as accurate to about two decimals.

**The return series are recoverable.** Each MODEL manifest carries 315 decision records; 63 of them
carry `strategy_id="RIDGE"` with a `realized_net_return` per period. That is the candidate's own
realised series, so the true moments are computable and the approximation is unnecessary.

## Method, and the check that validates it

For each of the 50 published models: take the 63 RIDGE `realized_net_return` values, compute the
annualised Sharpe and the sample skewness and kurtosis, and call
`OverfittingDiagnostics.deflated_sharpe_ratio` directly.

Before trusting any re-deflation, recompute each model **at its own stored ordinal** and compare to
its published figure:

```
worst |recomputed at own ordinal - published| over 50 models : 2.38e-03
```

Agreement to three decimals on every model. The reconstruction is sound.

### The estimator, identified rather than assumed

My first pass used the population standard deviation and produced a best Sharpe of `+3.2466`
against `CURRENT.md`'s `+3.2207`. That is not a discrepancy to wave through: the ratio is
`0.99202`, and `sqrt(62/63) = 0.99203`. The pipeline uses the **sample** standard deviation.
Switching estimators reproduces `+3.2207` exactly and tightens the method check from 5.85e-03 to
2.38e-03.

## Result

| Attempts deflated against | Best DSR, true moments | What is included |
|---:|---:|---|
| 50 | **0.218377** | the v2 campaign only -- what was actually used |
| 101 | 0.141623 | + the 51-trial v1 campaign |
| 104 | 0.139001 | + the 3 INFY trials |
| 110 | 0.134091 | + the 6 pre-declared ungoverned screens |

**`CURRENT.md`'s headline `0.217695` is corroborated.** True-moment computation gives `0.218377`, a
difference of 6.8e-04. The brief's `0.250826` was its own normal approximation, off by 0.033 --
exactly the two-decimal accuracy it declared, and the reason it asked for this check.

The identification is also confirmed: the figure belongs to `model_f727cadfd0b4ea70be2b1c30`,
Sharpe `+3.2207`, drawn at **ordinal 8** while its published DSR was `0.563235`. The best model
after re-deflation is not the best model as published, which is the trap the brief warned about.

### The moments are strongly non-normal, and it barely matters

```
best model true skewness : +1.7365     (normal approximation assumed 0.0)
best model true kurtosis : 12.0879     (normal approximation assumed 3.0)
```

Kurtosis of 12 on 63 observations is a fat-tailed series, and the normal approximation was
materially wrong about the distribution. It was nonetheless nearly right about the DSR, because the
gap to a 0.95 gate is far larger than the correction. That is worth stating in both directions: the
approximation was lucky in its conclusion and wrong in its inputs, and a future case with a smaller
margin should not lean on it.

## Section 3 of the brief, re-read independently

Every corroboration reproduced exactly from the store:

| Claim | Read from the store |
|---|---|
| 50 published models | **50** MODEL resources verified |
| every model schema v2 | one distinct schema: `('quantos.ridge_technical_six', 2)` |
| verdict RESEARCH_ONLY | **50 of 50** |
| nothing promotable | **0 of 50** reach 0.95, at any attempt count in the table above |
| max published DSR `0.584510` | **0.584510** |
| median published DSR `0.017352` | **0.017352** |
| ordinals 1..50, one each | min 1, max 50, **50 distinct** |
| validation length 63 | 63 on every model, **zero** empty series |

## What this does not close

- **Q3, point-in-time honesty.** Unchanged. An intact store proves nothing was altered after
  publication; it does not prove publication was correct.
- **Q1's remaining gap.** The determinism evidence still covers one instrument over four
  repetitions and never visits a failure path.
- **Q5.** The brief author's own contributions remain unreviewed by anyone independent of them.
- **The verdict.** Nothing here promotes anything. `0.218377` against a `0.95` gate is the same
  conclusion the campaign reached, now resting on the raw series rather than on an approximation.

## Evidence inventory, re-verified

`scripts/evidence_manifest.py --check` at the start of this work reported drift:

```
DRIFT against the committed inventory
  present now but not recorded : 1300
  recorded but absent now      : 0
```

**Additions only, zero removals.** 1,250 are the 2026-09-01 NIFTY 500 refresh committed at
`09ff0f85`, and 50 are new datasets in the NIFTY 50 refresh store. Nothing recorded has gone
missing, which is the direction that would matter. Inventory regenerated and the round trip
verified:

```
OK: 5077 resources match the committed inventory
```

The brief recorded 3,771 resources across 10 stores at `38d8c81d`; it is now 5,077 across 16, the
difference being subsequent scheduled refreshes.

One correction to my own working note: I briefly read the check as under-reporting the drift,
because it prints a count and then only the first five examples, and I had counted the examples. The
tool reported 1,300 correctly. No defect; my measure was wrong.
