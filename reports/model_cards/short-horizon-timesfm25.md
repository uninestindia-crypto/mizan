# Model card — `google/timesfm-2.5-200m-pytorch` zero-shot (holds 1, 2, 3)

## Identity

| | |
|---|---|
| Arm | `timesfm` run against the 2.5 checkpoint — pretrained, **zero-shot, no fine-tuning** |
| Checkpoint | `google/timesfm-2.5-200m-pytorch`, via `TimesFM_2p5_200M_torch.from_pretrained` |
| Results | `reports/short_horizon/results-timesfm25.json` |
| Forecasts | `reports/short_horizon/timesfm25-forecasts.json` (88,385 rows, 45 names, 1,967 dates) |
| Ledger | `reports/short_horizon/TRIAL-LEDGER.md` — trials **7, 8, 9**, declared 2026-09-12 **before any 2.5 result existed** |
| Multiplicity | Budget now **9**. Runner scored at 6; both bases reported below |
| Licence | **Apache-2.0** |
| Verdict | **`RESEARCH_ONLY`** at every hold |

## Licence — why this card exists at all

The [3.0 card](short-horizon-timesfm.md) covers `timesfm-non-commercial-license-v1.0` weights, which
prohibit production deployment and revenue generation. This arm exists to test whether a
**commercially usable** checkpoint performs. Upstream METADATA states the split: source code
Apache-2.0, weights **up to 2.5** Apache-2.0, 3.0 weights non-commercial.

No licence grant is claimed, recorded or relied on anywhere in this work. Apache-2.0 needs none.

## What it is

The pretrained 2.5 checkpoint run **without fine-tuning**, producing a 3-step forecast per decision.
One generation pass serves all three holds: hold *h* reads `predicted_return_by_hold[h]`.

Everything downstream is **identical to the 3.0 and ridge arms** — same 45 names, same 11 purged and
embargoed folds, same already-spent C1 abstention grid, same costs, same 252-session holdout. Only
the checkpoint differs, which is what makes the arms comparable.

The generator takes `--checkpoint` rather than hardcoding one, so the 3.0 arm behind trials 4-6
stays reproducible from the same script. It **refuses** a non-default checkpoint paired with the
default output path: that combination would resume from the 3.0 partial file and silently emit a
mixed-checkpoint forecast set over the top of published evidence.

## Results — better than 3.0 at every hold, and still failing

| Hold | DSR (as scored, 6) | DSR (re-deflated, 9) | Gate | Sharpe | Trades | Exposure | Hit rate | Max DD |
|---:|---:|---:|---|---:|---:|---:|---:|---:|
| 1 | 0.167607 | **0.118147** | **FAIL** | +0.1146 | 380 | 0.006 | — | 0.040 |
| 2 | 0.107263 | **0.071891** | **FAIL** | +0.0201 | 9,419 | 0.151 | — | 0.309 |
| 3 | 0.394441 | **0.312642** | **FAIL** | +0.3518 | 29,791 | 0.479 | 0.4972 | 0.534 |

Against the 3.0 arm on the identical basis of 6:

| Hold | 3.0 DSR | **2.5 DSR** | 3.0 Sharpe | **2.5 Sharpe** |
|---:|---:|---:|---:|---:|
| 1 | 0.023189 | **0.167607** | -0.2357 | **+0.1146** |
| 2 | 0.004270 | **0.107263** | -0.4533 | **+0.0201** |
| 3 | 0.191369 | **0.394441** | +0.1456 | **+0.3518** |

**The Apache-2.0 checkpoint is the better forecaster on this data.** Positive Sharpe at all three
holds where 3.0 was negative at two. This contradicted the prior written into Amendment 4 before the
run, and is recorded as a correction rather than restated as an expectation.

## Why it is still not a result

**1. The gate.** Best is 0.394441 against `min_deflated_sharpe = 0.95`. Not close at any hold.

**2. The [noise control](noise-control.md) still wins where it counts.** Same basis of 6:

| Hold | **Noise median** | 2.5 | Winner |
|---:|---:|---:|---|
| 1 | 0.000000 | **0.167607** | 2.5 |
| 2 | **0.148551** *(median of 30: 0.1615)* | 0.107263 | **noise** |
| 3 | **0.419649** *(median of 30: 0.5504)* | 0.394441 | **noise** |

Noise beats 2.5 at **both holds where the candidate actually trades**. At hold 3 the candidate sits
above the worst of 30 random draws (0.3197) and below their median.

**3. The trivial baselines.** At hold 3: `BUY_AND_HOLD` +0.4947 and `PREVIOUS_SIGN` +0.4400 against
the candidate's +0.3518. Beaten by holding everything, and by repeating yesterday's sign.

## Hold 1 — the only trial in this program where a real model beat noise

It is not evidence of skill, and the mechanism says why:

- The candidate abstained on **99.4%** of decisions — 380 trades out of 108,623, exposure 0.006.
- Sharpe +0.1146 against `CASH` at exactly 0.0000. It is a cash position with a slight tilt.
- `BUY_AND_HOLD` at hold 1 is **-1.4320**. The noise arm sat at ~50% exposure through that decline
  and earned a negative Sharpe, which floors its DSR at 0.0000.

So hold 1 records the abstention rule declining to trade a falling market while the control traded
it. That is the C1 grid working as designed. It says nothing about whether the forecaster ranks
names correctly, and it must not be quoted as if it did.

## Reproduce

```bash
.venv/Scripts/python.exe scripts/generate_timesfm_forecasts.py --checkpoint google/timesfm-2.5-200m-pytorch --out reports/short_horizon/timesfm25-forecasts.json
```

```bash
.venv/Scripts/python.exe scripts/run_short_horizon_experiment.py --arm timesfm --timesfm-forecasts reports/short_horizon/timesfm25-forecasts.json --out reports/short_horizon/results-timesfm25.json
```

Generation took 183.5 min for 88,385 forecasts on the reference machine.

## Known failures and limitations

- **Fails the gate at every hold**, by 2.4x at best. No threshold was weakened to obtain a pass.
- **Beaten by its own noise control at holds 2 and 3.** The deflated Sharpe tests against zero, so at
  ~50% long-only exposure it rewards market participation rather than skill.
- **The DSRs above were scored against 6 trials while the budget is 9.**
  `run_short_horizon_experiment.py:63` hardcodes `DECLARED_TRIALS = 6`; it is a claimed path and was
  not edited. The re-deflated column is the honest figure under the current budget.
- **Pretraining contamination is unquantified and cuts one way.** The model card establishes no
  exhaustive pretraining cutoff, and the evaluation window is 2018-2026. If the corpus overlaps it,
  part of this "forecast" is recall — a bias that flatters the candidate. Per the ledger's
  **TimesFM specifics**: a negative result stays informative under that bias, a positive one would
  need genuine out-of-sample confirmation before it meant anything. This result is negative.
- The 45-name subset is turnover-ranked and so liquid-biased by construction, which favours the cost
  model. It failed anyway.
- 9 of the ledger's trials are spent. A tenth inherits ordinal 10 and a harsher deflation.

## Must not be used for

Live-money routing, promotion, or any claim of short-horizon edge. The permissive licence removes a
legal obstacle; it does not create a result.
