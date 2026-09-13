# Model card — short-horizon QuantOS ridge (holds 1, 2, 3)

## Identity

| | |
|---|---|
| Arm | `ridge` — the newly trained QuantOS short-horizon candidate |
| Results | `reports/short_horizon/results-ridge.json` |
| Ledger | `reports/short_horizon/TRIAL-LEDGER.md` — **frozen before any result was seen** |
| Gate policy | `short-horizon-research-v1`, `min_deflated_sharpe = 0.95`, `max_drawdown = 0.15` |
| Multiplicity | 6 declared trials, `multiplicity_count = 6` — ledger honoured |
| Verdict | **`RESEARCH_ONLY`** at every hold |

## What it is

A ridge return-prediction model scored cross-sectionally, long only, holding **exactly 1, 2 or 3
trading sessions after entry**. The repository's decision/entry/exit convention maps a held-session
count to a label horizon as `hold + 1` (`HOLD_TO_HORIZON_SESSIONS = {1:2, 2:3, 3:4}`) — decide on
bar *t*, enter at the open of *t+1*, exit at the open of *t+1+hold*. That mapping is pinned by
`tests/test_short_horizon_mapping.py`, because getting it wrong silently shifts every return by a
session.

An **abstention/cash rule** is calibrated on the walk-forward validation folds only, from a single
declared threshold grid; the holdout is never touched during calibration.

## Data and timing

| | |
|---|---|
| Feature store | `data/evidence/feature-store/mizan-adjusted-v1/mizan_feature_store.csv.gz` |
| Corporate-action authority | `e68c8e1c2b7fec3a7840cdef06a189e602cd78771a747cf145a1fafe02ecff0a` |
| Universe | 45 names — research-universe names holding a universe-bound governed acquisition, turnover-ranked |
| Walk-forward | 11 chronological folds, purged and embargoed (1,980 rows each at hold 3) |
| Reserved holdout | **252 sessions, untouched until the candidate was frozen** |
| Code revision | `eae79270894cbe4fc8403142ee90168201a8f555-dirty` (honestly marked dirty) |

## Results — fails at every hold

| Hold | DSR | Gate | Sharpe | Trades | Exposure | Hit rate | Max DD |
|---:|---:|---|---:|---:|---:|---:|---:|
| 1 | 0.026515 | **FAIL** | -0.2162 | 379 | 0.0061 | 0.4749 | 0.1576 |
| 2 | 0.059283 | **FAIL** | -0.0888 | 755 | 0.0121 | 0.4728 | 0.3202 |
| 3 | 0.094711 | **FAIL** | -0.0041 | 35,150 | 0.5645 | 0.4927 | 0.7472 |

Baselines on the same folds at hold 3: `CASH` 0.0000, `BUY_AND_HOLD` **+0.4922**,
`PREVIOUS_SIGN` **+0.4359**. The candidate's -0.0041 loses to all three.

**Hit rate is below 50% at every hold.** At holds 1 and 2 the abstention rule suppresses almost all
trading (0.6% and 1.2% exposure); at hold 3 it calibrates to a threshold of 0 and stops abstaining
at all, which is why exposure jumps to 56%.

## The decisive comparison

The [noise control](noise-control.md) — random predictions through the identical pipeline — scored
**0.4197** at hold 3 against this model's **0.0947**. Randomness beat the model by 4.4x on the
headline metric, on the same folds and the same data.

## Reproduce

```bash
.venv/Scripts/python.exe scripts/run_short_horizon_experiment.py --arm ridge
```

## Known failures and limitations

- **Fails the gate at every hold, by more than an order of magnitude.** No threshold was weakened to
  obtain a pass, and none should be.
- **Beaten by its own noise control.** See that card for the mechanism: the deflated Sharpe tests
  against zero, so at ~50% long-only exposure it rewards market participation rather than skill.
- The 45-name subset is turnover-ranked, so it is liquid-biased by construction — a bias that favours
  the strategy's cost model, and it failed anyway.
- 6 of the ledger's trials are spent. A seventh inherits ordinal 7 and a harsher deflation.

## Must not be used for

Live-money routing, promotion, or any claim of short-horizon edge.
