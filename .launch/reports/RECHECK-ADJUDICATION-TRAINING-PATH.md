# Recheck: ADJUDICATION-TRAINING-PATH.md

RECHECK_ID: RECHECK-TRAINING-PATH-20260826
RECHECKER: Claude Code — did not author the training runner, the campaign driver, or the report
SUBJECT: `.launch/reports/ADJUDICATION-TRAINING-PATH.md` (Antigravity, 2026-08-26T05:40:00Z)
DATE_UTC: 2026-08-26
REVISION: `4306ec28`

**VERDICT: the subject report's conclusion is CORRECT and its central citation is DISPROVEN.**

Nothing here overturns "NONE PROMOTABLE". Every load-bearing structural claim in the subject report
reproduced. What failed is attribution: the report's headline evidence sentence describes a model
that does not exist, by combining properties of two different published models. A second numeric
claim is also wrong. Both are correctable without touching the verdict.

Adjudication standard used: every claim is marked PROVEN, DISPROVEN, or NOT TESTED. Claims outside
what was re-run are marked NOT TESTED rather than inherited.

---

## 1. DISPROVEN — the headline sentence describes no real model

The subject report states:

> "The best model (`model_6b522ca41170fee6e7bc728f`, Sharpe +3.2207) was published at ordinal 1
> with published DSR `0.584510`."

Measured directly from the store the report names
(`data/evidence/models/nifty50-current-20160822-20260821-schema-v2-source-bound-v2`):

| | `model_6b522ca4…` | `model_f727cadf…` |
|---|---:|---:|
| trial | `trial_nifty50_10y_001` | `trial_nifty50_10y_008` |
| RIDGE Sharpe | **0.428050** | **3.220727** |
| published DSR | **0.584510** | 0.563235 |
| `multiplicity_count` | **1** | **8** |
| max drawdown | 0.0426 | 0.0643 |

The sentence takes **model id, ordinal and DSR** from `model_6b522ca4…` and **Sharpe** from
`model_f727cadf…`. No published model has all four properties.

### Why the error is not cosmetic

The two models are "best" under *different metrics*, and the report's phrasing hides that:

- Best by **Sharpe**: `model_f727cadf…` at 3.220727, ordinal 8.
- Best by **published DSR**: `model_6b522ca4…` at 0.584510, ordinal 1 — whose Sharpe is 0.428050.

Published DSR is **ordinal-dependent by construction**: a trial is deflated against its own ordinal
because the campaign is still open when immutable evidence is written
(`modeling/validation.py:178-182`). `model_6b522ca4…` holds the highest published DSR largely
because it was scored first, when almost nothing had been attempted — the identical artifact
`CURRENT.md` already documents for GRASIM in the v1 campaign, where a published 0.696673 became
0.397794 once re-deflated at the true attempt count.

Citing an ordinal-1 published DSR as "the best model" reintroduces precisely the artifact the
re-deflation exists to remove.

## 2. DISPROVEN — the N=110 robustness figure

> "Deflating the best model at N=110 yields DSR `0.169377`."

Reproduced from the published decision records for `model_f727cadf…`:

| Attempt count | DSR |
|---:|---:|
| N=8 (its own ordinal) | 0.563234778441 |
| N=50 (final campaign count) | 0.217695263874 |
| **N=110** | **0.133380339598** |

`0.169377` is not the value at any of these counts. The report's *claim* — that the verdict is
invariant to attempt count — is nonetheless true, and more strongly than it stated: the real N=110
figure is **lower**, so the model is further from the gate than the report said.

## 3. The re-deflation figure is right, attached to the wrong model

> "Re-deflated at final campaign count (N=50): Yields DSR `0.217695`."

`0.217695263874` is **correct** and matches `CURRENT.md`'s recorded v2 campaign best. But it belongs
to `model_f727cadf…`, not to `model_6b522ca4…` which the report names two sentences earlier.

Re-deflating the model the report actually named gives:

| Model named by the report | re-deflated at N=50 |
|---|---:|
| `model_6b522ca41170fee6e7bc728f` | **0.018996994723** |

So the report is internally inconsistent: it names a model whose re-deflated DSR is 0.019 and
reports 0.218 for it. Read literally, its own figures disagree by an order of magnitude.

## 4. PROVEN — and a stronger result than the subject report established

Every structural claim re-ran clean:

| Claim | Measured | Verdict |
|---|---|---|
| 50 published models in the v2 source-bound store | 50 | **PROVEN** |
| 50/50 carry `('quantos.ridge_technical_six', 2)` | single distinct schema across all 50 | **PROVEN** |
| 50/50 carry `verdict=RESEARCH_ONLY` | single distinct verdict across all 50 | **PROVEN** |
| `scan_integrity()` → 150 valid, 0 invalid, 0 orphan blobs | 150 / 0 / 0 | **PROVEN** |
| best RIDGE Sharpe is +3.2207 | 3.220727162812 | **PROVEN** |
| best re-deflated DSR at N=50 is 0.217695 | 0.217695263874 | **PROVEN** |
| ordinals span the full campaign | min 1, max 50 | **PROVEN** |
| 21 of 50 models have positive Sharpe | 21 | **PROVEN** |
| NONE PROMOTABLE against `min_deflated_sharpe = 0.95` | max published DSR anywhere = 0.584510; best re-deflated = 0.217695 | **PROVEN** |

**New finding, stronger than anything the subject report claimed: the deflation machinery itself is
verified correct.** Reconstructing the portfolio period returns from each model's published decision
records — replicating `_portfolio_period_returns` (`validation.py:425`) and `_return_moments`
(`validation.py:435`) — and re-running `OverfittingDiagnostics.deflated_sharpe_ratio` reproduces
both published values **exactly to twelve decimal places**:

| Model | published | reproduced | |
|---|---:|---:|---|
| `model_f727cadf…` @ N=8 | 0.563234778441 | 0.563234778441 | **MATCH** |
| `model_6b522ca4…` @ N=1 | 0.584509790502 | 0.584509790502 | **MATCH** |

That is the claim most worth having: the published deflation is recomputable from the evidence, so
these numbers are auditable rather than asserted.

## 5. NOT TESTED

Claimed by the subject report, not re-run here, and therefore carrying no verdict from this recheck:

- "normal-moment approximation `0.250822`" — the variant was not identified in the code.
- Evidence inventory reconciliation of 3,771 resources across 10 stores.
- CRR lattice gamma convergence and American-put early-exercise premium.
- Holdout vault single-use sealing and second-use rejection.
- Cache provenance: "100 datasets across 50 symbols".
- Point-in-time and train-only standardization behaviour of the training runner and campaign drivers.

These may well be true. They are simply not established by this recheck, and the subject report's
demonstrated attribution failure is a reason to verify rather than inherit them.

## 6. Independence

The training runner (`scripts/run_governed_ridge_training.py`) and the campaign driver
(`scripts/run_universe_ridge_campaign.py`) were authored under
`20260822-claude-real-data-training-runner.md`. This recheck neither wrote them nor wrote the subject
report. It did author `execution/cross_sectional_strategy.py`, which is not in scope here and shares
no code path with the training stack.

Antigravity's independence on the subject report is likewise sound — it did not write the training
stack. Section 1 is an accuracy finding, not a standing one. The standing objection applies to a
different report and is recorded separately in
`agent_context/work/active/20260826-NOTICE-adjudication-reports-need-recheck.md`.

## 7. Required correction

Replace the sentence in section 1 of the subject report with one that names a single model, e.g.:

> The highest-Sharpe model is `model_f727cadfd0b4ea70be2b1c30` (`trial_nifty50_10y_008`, Sharpe
> +3.220727), published at ordinal 8 with DSR `0.563235` and re-deflated at the final campaign count
> N=50 to `0.217695`. The highest *published* DSR in the store, `0.584510`, belongs to
> `model_6b522ca41170fee6e7bc728f` at ordinal 1 and is an artifact of early scoring: its Sharpe is
> 0.428050 and it re-deflates to `0.018997`. Both fail the 0.95 gate.

And correct the N=110 figure from `0.169377` to `0.133380`.

With those two corrections the report stands, and its verdict — governance and evidence integrity
proven, zero models promotable — is independently confirmed here.
