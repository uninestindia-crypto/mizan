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
| Scope amendment (2026-09-10) | 0 | Declaring a computable universe is not a trial; it fixes the data both arms see, before any result |
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
| 1 | QuantOS short-horizon (ridge) | 1 | **SPENT** | Sharpe -0.2162; -0.000049/decision; 379 trades at 0.6% exposure; DSR **0.026515** vs 0.95; beats cash: **NO** -> `RESEARCH_ONLY` | 2026-09-10 |
| 2 | QuantOS short-horizon (ridge) | 2 | **SPENT** | Sharpe -0.0888; -0.000052/decision; 755 trades at 1.2% exposure; DSR **0.059283** vs 0.95; beats cash: **NO** -> `RESEARCH_ONLY` | 2026-09-10 |
| 3 | QuantOS short-horizon (ridge) | 3 | **SPENT** | Sharpe -0.0041; -0.000006/decision; 35,150 trades at 56.5% exposure; DSR **0.094711** vs 0.95; beats cash: **NO** -> `RESEARCH_ONLY` | 2026-09-10 |
| 4 | TimesFM 3.0 zero-shot | 1 | DECLARED | — | 2026-09-10 |
| 5 | TimesFM 3.0 zero-shot | 2 | DECLARED | — | 2026-09-10 |
| 6 | TimesFM 3.0 zero-shot | 3 | DECLARED | — | 2026-09-10 |
| C1 | Abstention threshold grid | all | DECLARED | — | 2026-09-10 |

## Amendment 3, 2026-09-10: a noise control, declared before the TimesFM result exists

While dry-running the TimesFM evaluation path with **randomly generated** forecasts, the candidate
reached **DSR 0.3876** at hold 3 and **0.1866** at hold 2. That run used 5 names and looser fold
settings, so it is not comparable to the declared configuration -- but it is a warning that the
deflated Sharpe at these sample sizes is noisy enough for pure noise to score in the same range as
this repository's best-ever result (`0.397794`).

A number that noise can reach is not evidence, and the only way to know where that line sits is to
measure it on the **identical** configuration. So a **noise control** is declared here, now, before
any real TimesFM number exists:

| Control | Definition |
|---|---|
| `NOISE` | The identical harness, identical 45-name subset, identical folds, costs and abstention grid, driven by pseudo-random forecasts from a fixed seed |
| Purpose | Establish what DSR this configuration awards to a forecaster with **no information at all** |
| Trials consumed | **Zero** |

**Why it costs no trial.** A control is not a candidate. `CASH`, `BUY_AND_HOLD` and `PREVIOUS_SIGN`
are already scored on every trial and consume nothing, because none of them could ever be promoted.
`NOISE` is the same kind of object: it exists to calibrate the yardstick, and it is not eligible for
promotion under any outcome. Counting it as a trial would deflate the real candidates for the crime
of being measured carefully.

**What it can and cannot do.** It cannot rescue a failing candidate, and it is not a threshold to
clear instead of the gate -- `GatePolicyV1.min_deflated_sharpe = 0.95` is unchanged and unchallenged.
It can only make a *passing-looking* number interpretable, by showing whether the configuration hands
out similar numbers to a forecaster that knows nothing.

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

## Amendment, 2026-09-10: the computable scope, declared before any TimesFM trial ran

TimesFM 3.0 was measured at **~116 ms per series per decision** and **2.57 GB peak memory**
(`TIMESFM-FEASIBILITY.md`). The full universe over the full history is about **33 days of compute**,
which is not runnable here.

A scope had to be chosen. It is declared **now**, before any TimesFM trial has produced a number, so
it cannot be selected on an outcome:

| Declared scope | Value |
|---|---|
| Universe | The **50 highest-median-turnover names** in `nse-research-universe-liquid-10y.csv` |
| History | **Full** — the whole cached window, no truncation |
| Estimated cost | 50 x 2,427 x 0.116 s ~ **3.9 hours** for the TimesFM arm |
| Applies to | **Both** arms. The simple model is restricted to the identical subset |

**Why universe rather than history.** This repository's own evidence says the thin dimension is
regime coverage, not cross-sectional breadth: the cross-sectional screen reached t = 1.18 on 29
rebalances and needed *more years*, not more names. Truncating history to buy names would spend the
scarce resource to buy the abundant one.

**Why both arms are restricted.** The simple model runs on the full universe in minutes and could
have used it. Letting it would confound model quality with sample size, and the comparison — which is
the entire point of the study — would be uninterpretable. Identical data or no comparison.

**Disclosed biases of this subset**, both of which favour a positive result and neither of which is
correctable from this cache:

- **Liquidity selection is not point-in-time.** Median turnover is computed over the whole window, so
  a name that became liquid late is included from the start. Liquidity is not the predicted variable,
  which limits the damage, but it is a look-ahead and it is not zero.
- **Survivorship**, inherited from the universe file itself: active listings only, so anything that
  delisted inside the window is absent.

Both must travel with every number the short-horizon study produces.

## Amendment 2, 2026-09-10: the subset is 45 names, not 50, and why

The declared rule was "the 50 highest-median-turnover names in the research universe". Executing it
produced **45**, and the shortfall is a data-availability fact rather than a choice.

The governed label path requires a **universe-bound** acquisition -- one carrying a point-in-time
historical universe authority. Without it `build_label_dataset` refuses the instrument, correctly:
a label that cannot be bound to the membership true at its decision time is not point-in-time.

The governed store holds **50 acquisitions, all 50 universe-bound**. Of those, **45** are also in
`nse-research-universe-liquid-10y.csv`. The intersection is the subset. The five excluded (ETERNAL,
HDFCLIFE, JIOFIN, MAXHEALTH, SBILIFE) fail the research universe's own >= 9.5-year history filter.

**A selection defect caught while implementing this, worth recording.** The first implementation
picked each symbol's acquisition by *longest history* and then filtered for universe authority. Some
symbols carry two datasets where the longer one is **unbound**, so that ordering silently dropped
RELIANCE, HDFCBANK, ICICIBANK, SBIN and 22 others -- reducing the subset to **19 names**, and
dropping exactly the largest names the turnover rule exists to select. The fix is to select the
longest acquisition *among the bound ones*, which is what `train_mizan.governed_acquisitions` already
did. Both this experiment and the forecast generator now use that one selector, because two scripts
disagreeing about the subset would mean the two arms were not evaluating the same experiment.

No trial is added or removed by this amendment. The budget remains six.

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
