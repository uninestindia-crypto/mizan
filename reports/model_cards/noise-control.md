# Model card — noise control (random predictions)

## Identity

| | |
|---|---|
| Arm | `noise` — **a calibration device, not a strategy** |
| Results | `reports/short_horizon/results-noise-control.json` |
| Seed | `20260910` for the headline run; 30 seeds for the distribution |
| Declared | In `reports/short_horizon/TRIAL-LEDGER.md` **before any result was seen** |
| Verdict | **NOT A CANDIDATE.** It cannot be promoted and is not a trial |

> **Re-scored 2026-09-14 against the frozen nine-trial budget.** Every deflated Sharpe on this card
> was originally computed with `num_trials=6`, while `TRIAL-LEDGER.md` now records **9** SPENT
> trials. The DSR figures below are the corrected ones; the value as published is given beside each.
> **No raw metric changed** -- every per-seed Sharpe and exposure is exactly as published -- and
> re-deflation is rank-preserving, so no comparison on this card moved. A **second** correction
> remains outstanding and is *not* applied here: the evaluator was repaired at `056fb1c6` and the raw
> metrics on this card predate that repair. See `TRIAL-LEDGER.md`, "Re-scoring, 2026-09-14".


## What it is

Random predictions pushed through the **identical** pipeline: same 45 names, same 11 purged and
embargoed folds, same abstention grid, same costs, same 252-session holdout. The only thing replaced
is the prediction.

It is a control, so it **does not spend a multiplicity ordinal** and is not counted among the nine
declared trials. Its job is to answer one question: *what score does this evaluation produce when
there is definitively no signal?*

## Results — it beat both real models

All figures re-scored against the nine-trial budget; the value as published at 6 is in brackets.

| Hold | **Noise DSR** | Ridge DSR | TimesFM 3.0 DSR | TimesFM 2.5 DSR |
|---:|---:|---:|---:|---:|
| 1 | 0.000000 *(0.000000)* | 0.015569 *(0.026515)* | 0.013464 *(0.023189)* | 0.118147 *(0.167607)* |
| 2 | **0.103240** *(0.148551)* | 0.037419 *(0.059283)* | 0.002182 *(0.004270)* | 0.071891 *(0.107263)* |
| 3 | **0.336002** *(0.419649)* | 0.062647 *(0.094711)* | 0.137089 *(0.191369)* | 0.312642 *(0.394441)* |

Across **30 seeds**, median DSR is `0.0000` / `0.1134` / `0.4626` at holds 1/2/3 (published:
`0.0000` / `0.1615` / `0.5504`), and **all 30 seeds beat the ridge and TimesFM 3.0 at hold 3** — the
worst seed scored `0.2454` against TimesFM 3.0's `0.1371`. **29 of 30 beat TimesFM 2.5**, whose
`0.312642` clears only the single worst draw and sits well below the median.

Those seed counts are identical before and after re-scoring. Re-deflation applies the same monotone
map to every row at a given hold, so it moves levels and cannot move an ordering.

## The mechanism, measured rather than asserted

This is not a defect in the pipeline and not a fluke of one seed. Random long-only predictions take
roughly **50% exposure**, which makes the arm a *diluted buy-and-hold*. The deflated Sharpe tests
against zero, so it rewards market exposure. The noise arm's median Sharpe tracks buy-and-hold at
each hold:

| Hold | Noise median Sharpe | `ALWAYS_TRADE` Sharpe |
|---:|---:|---:|
| 1 | -1.30 | -1.43 |
| 2 | +0.11 | -0.00 |
| 3 | +0.49 | +0.49 |

At hold 3 they are identical to two decimals. Noise took 31,162 trades at 0.5005 exposure; the
candidate arms took ~35,000 at ~0.57. **The DSR is measuring participation, not skill.**

## What this establishes, and what it does not

**Does:** at these horizons, on this data, the deflated Sharpe cannot distinguish any of the three
real models from randomness. Their numbers must be read against `0.3360`, not against `0`. TimesFM
2.5's `0.312642` at hold 3 — the best real number in the program — is **below** what the median coin
flip scored, which converts a "faint positive" reading into a decisive negative.

**Does not:** it does not show the gate is wrong. The gate is `0.95` and noise scored `0.34`, so
nothing here passes either way. It shows the *margin between 0 and the gate* is not interpretable as
skill at these holds without a control.

**This is the most useful single result in the short-horizon program**, and it exists only because
the control was declared in a frozen ledger before any result was seen. A ledger written afterwards
would have had every reason to omit it.

## Reproduce

```bash
.venv/Scripts/python.exe scripts/run_short_horizon_experiment.py --arm noise --noise-seeds 30
```

## Must not be used for

Anything. It is a measuring instrument. It has no predictive content by construction, and a reader
who quotes its `0.3360` as a result has inverted the point.
