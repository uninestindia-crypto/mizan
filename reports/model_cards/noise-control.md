# Model card — noise control (random predictions)

## Identity

| | |
|---|---|
| Arm | `noise` — **a calibration device, not a strategy** |
| Results | `reports/short_horizon/results-noise-control.json` |
| Seed | `20260910` for the headline run; 30 seeds for the distribution |
| Declared | In `reports/short_horizon/TRIAL-LEDGER.md` **before any result was seen** |
| Verdict | **NOT A CANDIDATE.** It cannot be promoted and is not a trial |

## What it is

Random predictions pushed through the **identical** pipeline: same 45 names, same 11 purged and
embargoed folds, same abstention grid, same costs, same 252-session holdout. The only thing replaced
is the prediction.

It is a control, so it **does not spend a multiplicity ordinal** and is not counted among the six
declared trials. Its job is to answer one question: *what score does this evaluation produce when
there is definitively no signal?*

## Results — it beat both real models

| Hold | **Noise DSR** | Ridge DSR | TimesFM DSR |
|---:|---:|---:|---:|
| 1 | 0.000000 | 0.026515 | 0.023189 |
| 2 | **0.148551** | 0.059283 | 0.004270 |
| 3 | **0.419649** | 0.094711 | 0.191369 |

Across **30 seeds**, median DSR was `0.0000` / `0.1615` / `0.5504` at holds 1/2/3, and **all 30
seeds beat both models at hold 3** — the worst seed scored `0.3197` against TimesFM's `0.1914`.

## The mechanism, measured rather than asserted

This is not a defect in the pipeline and not a fluke of one seed. Random long-only predictions take
roughly **50% exposure**, which makes the arm a *diluted buy-and-hold*. The deflated Sharpe tests
against zero, so it rewards market exposure. The noise arm's median Sharpe tracks buy-and-hold at
each hold:

| Hold | Noise median Sharpe | Buy-and-hold Sharpe |
|---:|---:|---:|
| 1 | -1.30 | -1.43 |
| 2 | +0.11 | -0.00 |
| 3 | +0.49 | +0.49 |

At hold 3 they are identical to two decimals. Noise took 31,162 trades at 0.5005 exposure; the
candidate arms took ~35,000 at ~0.57. **The DSR is measuring participation, not skill.**

## What this establishes, and what it does not

**Does:** at these horizons, on this data, the deflated Sharpe cannot distinguish either real model
from randomness. Both models' numbers must be read against `0.4197`, not against `0`. TimesFM's
`0.1914` at hold 3 — the best real number in the program — is **less than half** of what noise
scored, which converts a "faint positive" reading into a decisive negative.

**Does not:** it does not show the gate is wrong. The gate is `0.95` and noise scored `0.42`, so
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
who quotes its `0.4197` as a result has inverted the point.
