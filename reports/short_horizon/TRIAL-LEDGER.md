# Short-horizon experiment: frozen trial ledger

**Frozen 2026-09-10, before any result was seen.** Every model, horizon and parameter trial is
counted here whether or not it is published, because an unrecorded search is invisible multiplicity
to whoever screens this family next — and because this repository has already had to correct a
headline number once for exactly that reason.

The rule that makes this binding: **a trial not listed here cannot be added after a result is
seen.** Adding one is a new declaration, dated, with the reason stated, and it deflates everything
that follows.

## Budget

| Family | Declared trials | Notes |
|---|---:|---|
| QuantOS short-horizon model — holds {1, 2, 3} | 3 | One model class, one feature contract, three horizons |
| TimesFM 3.0 zero-shot — holds {1, 2, 3} | 3 | Frozen checkpoint, no fine-tuning |
| Abstention threshold grid | 1 grid | Declared **once**, applied identically to all six trials. Calibrated on training/validation partitions only |
| **Total** | **6 published trials + 1 calibration grid** | |
| Governed Mizan retrain | 1 ordinal | Separate study, separate ledger entry — see the work record |

## Pre-declared design

Declared in full before the first run, so that nothing below can be chosen after seeing an outcome.

| Element | Declaration |
|---|---|
| Holds | Exactly 1, 2 and 3 sessions held after entry |
| Execution convention | Decision at session close `k`; entry at open `k+1`; exit at open `k+horizon`. `horizon_sessions ∈ {2,3,4}` for holds {1,2,3} — **proven** against the real label builder in `tests/test_short_horizon_mapping.py`, not asserted |
| Universe | `data/authorities/nse-research-universe-liquid-10y.csv`, 423 names. Survivorship-biased by construction (active listings only); the bias favours the candidate and is disclosed with every result |
| Costs | Effective-dated NSE statutory rules via `cached_nifty50_costs.research_cost_engine`, quoted on **raw executable opens** at a realistic quantity |
| Validation | Chronological walk-forward, purged, with embargo ≥ horizon for overlapping labels |
| Preprocessing | Fitted on each training partition only. Imputation, scaling and any threshold are learned state |
| Abstention | A cash/no-trade rule, calibrated on training/validation partitions only, and part of the candidate rather than a post-hoc filter |
| Final holdout | A chronological tail, **untouched** until a candidate is frozen, then evaluated exactly once |
| Gates | Existing `GatePolicyV1`. Thresholds are not adjusted to obtain a pass |
| Separation | No result here may move Flagship or XS-Monthly, and neither book's history is altered |

## Why the abstention rule is one grid and not one per hold

Calibrating a separate threshold per horizon would be three more trials, and the three horizons are
not independent — they share a universe, a feature contract and largely overlapping decision dates.
Three per-hold thresholds would find the best of nine combinations while reporting the multiplicity
of three.

One grid, applied identically, costs one declaration and keeps the six published trials
interpretable. If a per-hold threshold later looks necessary, that is a new declaration with its own
cost, made in the open.

## Ledger

Entries are appended as trials execute. `SPENT` means the trial ran and its result is counted
whatever it was; a disappointing result does not return the ordinal.

| # | Family | Hold | Status | Result | Recorded |
|---|---|---:|---|---|---|
| 1 | QuantOS short-horizon | 1 | DECLARED | — | 2026-09-10 |
| 2 | QuantOS short-horizon | 2 | DECLARED | — | 2026-09-10 |
| 3 | QuantOS short-horizon | 3 | DECLARED | — | 2026-09-10 |
| 4 | TimesFM 3.0 zero-shot | 1 | DECLARED | — | 2026-09-10 |
| 5 | TimesFM 3.0 zero-shot | 2 | DECLARED | — | 2026-09-10 |
| 6 | TimesFM 3.0 zero-shot | 3 | DECLARED | — | 2026-09-10 |
| C1 | Abstention threshold grid | all | DECLARED | — | 2026-09-10 |

## Search that already happened, and must be priced in

This study does not start from zero multiplicity. The repository has already screened this market
extensively, and a future reader deflating these six trials against six attempts would be
understating the search. Prior work, from `agent_context/CURRENT.md`:

| Prior study | Trials |
|---|---:|
| Per-instrument governed campaigns (v1, then v2 under schema v2) | 101 governed ordinals |
| Pre-declared ungoverned screens (feature families, hold grids, cross-sectional) | 7 screens |
| Mizan pooled cross-sectional | 1 ordinal |

**Every one of those found no edge that survives real costs.** The strongest deflated Sharpe across
all of it is `0.397794` against a `0.95` gate. That prior is the honest starting position for this
study, and a short-horizon result would have to be strong to overcome it — short horizons face the
worst version of the cost problem in this repository, because a 0.224% round trip is about 1.1 basis
points per session over 21 sessions and about **22 basis points per session over one**.

Stating that up front is not pessimism. It is the reason the abstention rule is part of the
candidate: a short-horizon strategy that cannot decline to trade is paying that spread on every
decision.

## TimesFM specifics

| Item | Declaration |
|---|---|
| Checkpoint | `google/timesfm-3.0-pytorch`, **pinned**; the resolved revision hash is recorded with the results |
| Package | `timesfm==3.0.2` |
| Framework | `torch==2.14.0` (wheel tag `cp313-cp313-win_amd64` — see the NPU report; this environment is emulated x86-64) |
| Environment | Isolated: `D:\quant_system_workspaces\scratch\timesfm-probe-20260910`. **Not** the QuantOS `.venv`, so `uv.lock` and `pyproject.toml` are untouched |
| Fine-tuning | **None.** Zero-shot only, as declared |
| Licence | TimesFM 3.0's default licence is non-commercial / non-production. Used here for the founder's **personal, non-production research** within that licence. No live-money routing, and no commercial decision-making. Version 2.5 is Apache-2.0 and is the route to investigate if this ever needs a commercial path |
| Future covariates | Only inputs genuinely known at prediction time may be supplied. A covariate whose value is published after the decision timestamp is leakage regardless of what the model does with it |

### Pretraining-overlap uncertainty, stated rather than assumed away

The TimesFM model card does not establish one exhaustive pretraining cutoff for all its data, and
NSE daily equity history is public. A retrospective test on 2016–2026 NSE bars therefore **cannot be
assumed uncontaminated**: some of this exact price history may sit in the model's pretraining
corpus.

This is not fatal to the comparison, but it changes what the comparison can claim:

- A **negative** result stays informative. If a model that may have memorised the data still cannot
  beat costs, that is strong evidence against the strategy.
- A **positive** result is not evidence of forecasting skill on unseen data. It would need genuine
  out-of-sample confirmation — a forward period after the model was published, or a market the
  pretraining corpus plausibly excludes — before it could support anything.

That asymmetry is declared here, before any number exists, so it cannot be quietly dropped if the
result comes out favourable.
