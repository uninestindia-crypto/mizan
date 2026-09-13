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
| 4 | TimesFM 3.0 zero-shot | 1 | **SPENT** | Sharpe -0.2357; -0.000007/decision; 58 trades at 0.1% exposure; DSR **0.023189** vs 0.95; beats cash: **NO** -> `RESEARCH_ONLY` | 2026-09-11 |
| 5 | TimesFM 3.0 zero-shot | 2 | **SPENT** | Sharpe -0.4533; -0.000044/decision; 289 trades at 0.5% exposure; DSR **0.004270** vs 0.95; beats cash: **NO** -> `RESEARCH_ONLY` | 2026-09-11 |
| 6 | TimesFM 3.0 zero-shot | 3 | **SPENT** | Sharpe +0.1456; +0.000199/decision; 35,425 trades at 56.9% exposure; DSR **0.191369** vs 0.95; beats cash: **YES** (lags Buy&Hold +0.4922, Noise median DSR 0.5504) -> `RESEARCH_ONLY` | 2026-09-11 |
| C1 | Abstention threshold grid | all | **SPENT** | Calibrated on walk-forward folds; selected 0.020 for hold 1 & 2, 0.000 for hold 3 | 2026-09-11 |
| NOISE | Control — consumes **no trial** | all | **RUN** | 30 seeds, identical configuration. DSR median 0.0000 / 0.1615 / 0.5504 at holds 1/2/3. **All 30 seeds beat both models at hold 3** (worst draw 0.3197 vs ridge 0.0947, TimesFM 0.1914) | 2026-09-11 |
| 7 | TimesFM 2.5 zero-shot (Apache-2.0) | 1 | **SPENT** | Sharpe +0.1146; +0.000012/decision; 380 trades at 0.6% exposure; DSR **0.167607** vs 0.95 (**0.118147** re-deflated at 9); beats cash: **marginally** (cash 0.0000) but only by abstaining on 99.4% of decisions -> `RESEARCH_ONLY` | 2026-09-13 |
| 8 | TimesFM 2.5 zero-shot (Apache-2.0) | 2 | **SPENT** | Sharpe +0.0201; +0.000011/decision; 9,419 trades at 15.1% exposure; DSR **0.107263** vs 0.95 (**0.071891** at 9); **loses to the noise control** (median 0.1615) -> `RESEARCH_ONLY` | 2026-09-13 |
| 9 | TimesFM 2.5 zero-shot (Apache-2.0) | 3 | **SPENT** | Sharpe +0.3518; +0.000435/decision; 29,791 trades at 47.9% exposure; DSR **0.394441** vs 0.95 (**0.312642** at 9); **loses to the noise control** (median 0.5504) and to Buy&Hold +0.4947 and PreviousSign +0.4400 -> `RESEARCH_ONLY` | 2026-09-13 |

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

## NOISE CONTROL RESULT: the deflated Sharpe here is not measuring skill

30 seeds, identical subset, folds, costs and abstention grid. This is the most consequential
measurement in the study and it is about the **method**, not the models.

| Hold | Ridge DSR | Noise DSR min | Noise DSR median | Noise DSR max | Ridge Sharpe | Noise median Sharpe | Buy-and-hold Sharpe |
|---|---:|---:|---:|---:|---:|---:|---:|
| 1 | 0.0265 | 0.0000 | **0.0000** | 0.0000 | -0.2162 | -1.3001 | -1.4340 |
| 2 | 0.0593 | 0.0577 | **0.1615** | 0.2410 | -0.0888 | +0.1063 | -0.0018 |
| 3 | 0.0947 | 0.3197 | **0.5504** | 0.7063 | -0.0041 | +0.4863 | +0.4922 |

**At hold 3 all thirty noise seeds beat the ridge.** The worst random draw scored DSR 0.3197 against
the ridge's 0.0947, and the median random draw scored **0.5504** -- higher than this repository's
best-ever recorded result of `0.397794`.

### Why, measured rather than speculated

The noise median Sharpe tracks buy-and-hold at every hold:

| Hold | Buy-and-hold Sharpe | Noise median Sharpe | Noise exposure |
|---|---:|---:|---:|
| 1 | -1.4340 | -1.3001 | 0.169 |
| 2 | -0.0018 | +0.1063 | 0.459 |
| 3 | **+0.4922** | **+0.4863** | 0.500 |

Random long-only selection at ~50% exposure **is a diluted buy-and-hold**. Halving exposure scales
mean and volatility together, so the Sharpe survives almost intact. The deflated Sharpe as computed
tests the candidate against **zero** -- and in a rising market every long-only rule beats zero,
including one that knows nothing.

### What follows

1. **A DSR below the noise median is worse than it looks.** The ridge at hold 3 (0.0947) did not
   merely fail the gate; it underperformed thirty out of thirty coin flips. Its abstention rule took
   it *out* of a market that rose, which is a worse outcome than having no opinion.
2. **Buy-and-hold is the comparator that matters here**, not zero. Every result in this study is
   reported against it.
3. **This does not weaken the gate and is not an excuse.** `GatePolicyV1.min_deflated_sharpe = 0.95`
   is unchanged. Nothing passed it, nothing is promotable, and no threshold was adjusted.
4. **A question this raises about prior work, stated as a question.** The repository's historical best
   of `0.397794` sits below the noise median measured here. That does *not* establish the earlier
   figure was drift rather than skill -- it came from per-instrument campaigns with different
   exposure characteristics, and re-deriving it is outside this study. But it is a specific,
   checkable hypothesis that someone should test rather than leave implied.

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
(`TIMESFM-FEASIBILITY.md`). The full universe over the full history is about **33.1 hours of compute**
*(errata: originally noted as 33 days due to an arithmetic typo; the declared computable subset was fixed before any trial ran)*,
which is a significant resource burden on this 16 GB single-machine host.

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

## Amendment 4, 2026-09-12: a licensing-clean foundation arm, declared before any 2.5 result exists

**Trials 7, 8 and 9. Budget moves 6 -> 9 published trials.** Declared on founder instruction
(*"use the 2.5 weights instead"*, then *"Run all three holds"*), before a single 2.5 forecast has
been evaluated.

### Why a fourth amendment, and why it is not a free replication

`google/timesfm-3.0-pytorch` is licensed `timesfm-non-commercial-license-v1.0`, which prohibits
production deployment and revenue generation. `google/timesfm-2.5-200m-pytorch` is **Apache-2.0** —
upstream METADATA states the split directly: source code Apache-2.0, weights up to 2.5 Apache-2.0,
3.0 weights non-commercial. So 2.5 is the only foundation checkpoint here that could ever sit in a
commercial path.

The motivation is **licensing, not performance**, and that changes nothing about the cost. A real
model with predictive content spends an ordinal. Running 2.5 as a "control" or a "replication of
trials 4-6" to avoid three ordinals was considered and **refused**: the noise control is free only
because it has no predictive content by construction, and borrowing that exemption for a real model
is precisely the manoeuvre this ledger exists to prevent.

### What this costs the trials already spent

`multiplicity_count` for this family becomes **9**. Every short-horizon DSR already published was
scored against a smaller attempt count and will re-deflate **lower** against 9. Those published
figures are not edited and remain correct as published, at the count that existed when they were
scored — the same effect `CURRENT.md` records for GRASIM (0.696673 published, 0.397794 re-deflated
against 51). Named here in advance rather than discovered later.

### The prior, recorded before the result

Wiring was smoke-tested in a scratchpad — no repository file touched, no evaluation, no ordinal. On a
matched window (8 liquid names, 40 dates, 2026-06-29..2026-08-21, 320 forecasts each) the median
cross-sectional stdev of predictions was **0.001912** for 2.5 against **0.001498** for 3.0, both
against realised dispersion of 0.009777. 2.5 produces about 28% more spread and sits in the same
heavy-shrinkage regime.

That statistic says names can be ranked apart. It says **nothing** about whether the spread is
informative — a genuinely better model and a differently-noisy one are indistinguishable on it, which
is why the smoke deliberately computed no IC, Sharpe, hit rate or P&L.

**Stated plainly so it cannot be claimed afterwards: the honest prior is that 2.5 reproduces the 3.0
null.** 3.0, with a very similar dispersion profile, scored 0.023189 / 0.004270 / 0.191369 and lost
to the noise control at every hold. The arm is being run because a licensing-clean candidate that has
been properly tested is worth more than an untested one — not because a better number is expected.

### Binding conditions on trials 7-9

- The **same** frozen design applies: same universe, same purged and embargoed folds, same 252-session
  holdout, same cost model, and the **C1 abstention grid already spent** — no new calibration.
- The 3.0 evidence is **not** overwritten. 2.5 writes to `timesfm25-forecasts.json`. (The generator's
  `--out` default resumes from the existing `.partial.jsonl`; a default-flag 2.5 run would have
  silently produced a mixed 3.0/2.5 file.)
- The pretraining-contamination asymmetry under **TimesFM specifics** applies unchanged to 2.5: a
  negative result stays informative, a positive one is not evidence of skill on unseen data.
- A tenth trial inherits ordinal 10 and a harsher deflation. Do not sweep checkpoints.

Filed with `agent_context/work/active/20260912-NOTICE-claude-timesfm25-trials-7-9-declared.md`
against the record that owns this file. Amendment is additive; no existing row was altered.

## Result of trials 7-9, 2026-09-13: better than 3.0, and still no edge

Recorded against Amendment 4's stated prior, which was **"expect 2.5 to reproduce the 3.0 null."**
That prior was **half wrong and is not being quietly restated**.

### 2.5 beat 3.0 at every hold

| Hold | 3.0 DSR | **2.5 DSR** | 2.5 Sharpe | 3.0 Sharpe |
|---:|---:|---:|---:|---:|
| 1 | 0.023189 | **0.167607** | +0.1146 | -0.2357 |
| 2 | 0.004270 | **0.107263** | +0.0201 | -0.4533 |
| 3 | 0.191369 | **0.394441** | +0.3518 | +0.1456 |

All six figures above are on the same multiplicity basis of 6, so the comparison is like for like.
The Apache-2.0 checkpoint is a **better forecaster on this data than the non-commercial one** —
positive Sharpe at all three holds where 3.0 was negative at two. This was not expected and is
recorded because it was not.

### And it still fails, on all three independent tests

1. **The gate.** Best is 0.394441 against `min_deflated_sharpe = 0.95`. Not close at any hold.
2. **The noise control.** At the same basis of 6, noise median DSR is 0.0000 / 0.1615 / 0.5504.
   Noise **still beats 2.5 at holds 2 and 3** — the two holds where the candidate actually trades.
   At hold 3, 2.5's 0.394441 sits above the worst of 30 noise draws (0.3197) and well below their
   median.
3. **The trivial baselines.** At hold 3, where the candidate takes 29,791 positions at 47.9%
   exposure, `BUY_AND_HOLD` scores +0.4947 and `PREVIOUS_SIGN` +0.4400 against its +0.3518.

### The one place a real model finally beat the control, and why it is not a result

Hold 1 is the **only** trial in this program where a real model outscored noise: 0.167607 against a
noise median of 0.0000. The mechanism disqualifies it as evidence of skill:

- The candidate abstained on **99.4%** of decisions — 380 trades out of 108,623, exposure 0.006.
- Its Sharpe of +0.1146 is against `CASH` at exactly 0.0000. It is a cash position with a tilt.
- `BUY_AND_HOLD` at hold 1 is **-1.4320**. The noise arm sat at ~50% exposure in that decline and
  earned a negative Sharpe, which floors DSR at 0.0000.

So hold 1 says the abstention rule avoided a falling market while the control participated in it.
That is the C1 grid working as designed, not the forecaster ranking names correctly.

### Multiplicity: these numbers are quoted at 6 and the budget is now 9

`scripts/run_short_horizon_experiment.py:63` hardcodes `DECLARED_TRIALS = 6`. It is a claimed path
and was **not edited**; the figures above are reported exactly as the runner produced them, and
re-deflated beside them using the repository's own `OverfittingDiagnostics.deflated_sharpe_ratio`:

| Hold | DSR as scored (6) | DSR re-deflated (9) | Delta |
|---:|---:|---:|---:|
| 1 | 0.167607 | **0.118147** | -0.049460 |
| 2 | 0.107263 | **0.071891** | -0.035372 |
| 3 | 0.394441 | **0.312642** | -0.081799 |

The re-deflated column is the honest figure under the budget that now exists. It is **not** compared
against the noise control above, because those draws were themselves scored at 6; comparing 2.5 at 9
against noise at 6 would understate the candidate.

Every short-horizon DSR in rows 1-6 is likewise quoted at its own scoring-time count and would fall
against 9. Those rows are left exactly as their owner wrote them.

### Standing instruction

**Do not run a tenth trial.** It inherits ordinal 10, deflates everything here further, and would be
searching checkpoints for a number — the precise failure this ledger exists to prevent. The
foundation-model direction has now been tested under both a non-commercial and a permissive
checkpoint and has no edge under either.
