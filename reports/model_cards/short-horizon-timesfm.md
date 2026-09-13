# Model card — `google/timesfm-3.0-pytorch` zero-shot (holds 1, 2, 3)

## Identity

| | |
|---|---|
| Arm | `timesfm` — pretrained foundation model, **zero-shot, no fine-tuning** |
| Checkpoint | `google/timesfm-3.0-pytorch`, loaded via `TimesFM3Forecaster.from_pretrained` |
| Results | `reports/short_horizon/results-timesfm.json` |
| Forecasts | `reports/short_horizon/timesfm-forecasts.json` (~20 MB, checkpointed JSONL, resumable) |
| Feasibility | `reports/short_horizon/TIMESFM-FEASIBILITY.md` |
| Licence | `timesfm-non-commercial-license-v1.0` |
| Verdict | **`RESEARCH_ONLY`** at every hold |

## Licence boundary — binding, not advisory

The checkpoint is licensed for **research and non-commercial use**; the licence **prohibits
production deployment and revenue generation**. This experiment is personal research within that
licence, with **no live-money routing**. Any QuantOS path toward live money cannot route through
these weights as licensed — a commercial grant from Google would be a separate agreement.

## What it is

The pretrained checkpoint run **without fine-tuning**, producing a 3-step forecast per decision via
`predict_batch(horizon=3)`. One generation pass serves all three holds: hold *h* reads
`predicted_return_by_hold[h]`. An earlier version read the 1-step forecast for every hold — a bug
that would have made all three arms the same experiment; it is fixed and the per-hold selection is
explicit.

Everything downstream is **identical to the ridge arm** — same folds, same universe, same abstention
grid, same costs, same holdout. Only the prediction source differs, which is what makes the two arms
comparable.

## Data and timing

| | |
|---|---|
| Feature store | `data/evidence/feature-store/mizan-adjusted-v1/mizan_feature_store.csv.gz` |
| Corporate-action authority | `e68c8e1c2b7fec3a7840cdef06a189e602cd78771a747cf145a1fafe02ecff0a` |
| Universe | 45 names, identical to the ridge arm |
| Walk-forward | 11 chronological folds, purged and embargoed |
| Reserved holdout | 252 sessions, untouched until frozen |
| **Missing predictions** | **0** — every decision had a forecast; verified, not assumed |
| Code revision | `2e28d76e43e2d85015003798d810d1365d6b94b7-dirty` |

**Pretraining-overlap uncertainty is unresolved and must travel with these numbers.** The checkpoint
was pretrained on undisclosed data that may include this period and these instruments. Nothing here
can exclude that, so a *positive* result would have been uninterpretable. The result is negative,
which is the one case where the overlap risk does not matter — overlap could only have helped.

Future covariates are not used. Only information available at prediction time enters the forecast.

## Results — fails at every hold

| Hold | DSR | Gate | Sharpe | Trades | Exposure | Hit rate | Max DD |
|---:|---:|---|---:|---:|---:|---:|---:|
| 1 | 0.023189 | **FAIL** | -0.2357 | 58 | 0.0009 | 0.4655 | 0.0203 |
| 2 | 0.004270 | **FAIL** | -0.4533 | 289 | 0.0046 | 0.4498 | 0.0741 |
| 3 | 0.191369 | **FAIL** | +0.1456 | 35,425 | 0.5690 | 0.4985 | 0.5658 |

Hold 3 is the **best number any real model produced in this program** — and it is still less than
half of what the [noise control](noise-control.md) scored (`0.4197`) on the same folds. Without that
control, `0.1914` could have been misread as a faint signal. It is not.

Hit rate is below 50% at every hold. At hold 2 the model is worse than the ridge on every column.

## Reproduce

```bash
.venv/Scripts/python.exe scripts/generate_timesfm_forecasts.py
```

```bash
.venv/Scripts/python.exe scripts/run_short_horizon_experiment.py --arm timesfm
```

Generation is resumable: it checkpoints to JSONL and tolerates a torn final line, after an early
version lost 27 minutes of work by writing only at the end.

## Known failures and limitations

- **Fails the gate at every hold.** Zero-shot TimesFM 3.0 does not beat a simple ridge here, and
  neither beats randomness on the headline metric. That is the direct answer to the pre-declared
  comparison.
- **Pretraining overlap cannot be excluded** (see above).
- Runs on CPU. A bounded Snapdragon Hexagon NPU feasibility test was conducted and the NPU path was
  **not taken** — see `reports/short_horizon/NPU-FEASIBILITY.md`. CPU execution is retained.
- No fine-tuning was attempted, by design: the pre-declared comparison was zero-shot.

## Must not be used for

Live-money routing, production deployment, revenue generation (licence), promotion, or any claim of
short-horizon edge.
