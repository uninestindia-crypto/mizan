# Active work: Mīzān — one pooled cross-sectional governed model

STATUS: COMPLETE — Mizan trained at two horizons; NOT promotable; negative skill measured  
OWNER: Claude Code — Mīzān model build  
TOOL: Claude Code  
STARTED_UTC: 2026-08-25T15:00:00Z  
STARTING_REVISION: `5127cf48`  
WORKTREE_OR_BRANCH: `D:\quant_system` on `main`

## Objective

Establish **Mīzān** as the single governed model identity of this system, and train it once as a
pooled cross-sectional model over the liquid NSE research universe using the multi-dimensional
feature family (macro regime, volume/money-flow, volatility estimators, cross-sectional ranks) that
the six-feature contract structurally could not express.

Founder instruction, 2026-08-25: one model, named Mīzān, trained on all available data, for launch.

## Why pooled rather than per-name

Every prior campaign trained one model per instrument and spent one multiplicity ordinal per name —
51 trials, then 50. Deflation correctly punishes that: searching N names finds the tail of a noise
distribution by construction. A single pooled model ranking names against each other on the same
date spends **one** ordinal, so the `GatePolicyV1.min_deflated_sharpe = 0.95` gate is reachable
rather than arithmetically out of reach.

This is also the frame `agent_context/CURRENT.md` identifies as the only untried direction with
non-negative evidence, and the one the governed dataset contract could not previously express.

## Founder authorization for claimed paths

`20260820-codex-slice4-ridge-training.md` is STATUS: ACTIVE and owns `rows.py`, `ridge.py`,
`preprocessing.py`, `trials.py`, and `modeling/__init__.py`. Contact was attempted — `ListAgents`
shows no session matching that owner. The founder authorized proceeding on 2026-08-25.

Per PROTOCOL §7 a handoff audit accompanies this record:
`agent_context/handoffs/20260825-1500Z-claude-mizan-slice4-claim-audit.md`. That record is **not**
edited by me. Changes to claimed paths are **additive** — v1 and v2 feature schemas remain valid and
the 50 existing published models remain auditable.

## Owned paths

New:
- `scripts/build_mizan_feature_store.py`
- `scripts/train_mizan.py`
- `src/quant_system/modeling/pooled.py`
- `tests/test_mizan_pooled.py`
- `data/evidence/feature-store/mizan/**`
- `data/evidence/models/mizan-*/**`

Modified (additively):
- `src/quant_system/modeling/rows.py` — schema v3 identity + schema-aware feature-name check
- `src/quant_system/modeling/ridge.py` — size regularizer by actual feature count
- `src/quant_system/modeling/preprocessing.py` — generic feature count
- `src/quant_system/modeling/labels.py` — permit a pooled multi-instrument feature dataset
- `src/quant_system/modeling/features.py` — pooled dataset assembly

## Non-goals

- Live-money order routing. Excluded by product law; unchanged.
- Promotion beyond what the gate actually returns. If Mīzān fails `GATE_DEFLATED_SHARPE`, that is
  the result and it gets reported as the result.
- Retraining or invalidating the 50 existing schema-v2 models.
- Renaming `RidgeFittedStateV1` or the v1/v2 schema ids. Those are baked into published manifest
  hashes; renaming them would break the audit trail of existing evidence for cosmetic gain.

## Defects found in the inherited data, before any training

| Finding | Measured |
|---|---|
| Duplicate rows in the prebuilt multidim store | **111,941 of 246,554** (date, symbol) pairs appear exactly twice — ~45% of 358,495 rows. Same duplicate-DATASET-per-symbol artifact recorded in `20260824-claude-alternative-feature-screens.md` |
| Metadata overstates coverage | `feature_store_metadata.json` says `total_symbols: 161`; the CSV holds **113** distinct symbols |
| Universe overlap | Only **85** of those 113 survive the 423-name liquid-universe filter |
| Targets are optimistic | `fwd_ret_*` enters at the same close that produced the signal, with zero cost. The governed contract is next-open entry with real NSE statutory costs |

Consequence: the prebuilt store is **not** consumed. It is rebuilt deduplicated across the research
universe, and labels come from the governed cost-aware path, not from `fwd_ret_*`.

## Feature causality — verified before use

Read `scripts/build_multidim_feature_store.py:120-195` line by line. All predictive features use
trailing or same-bar-close windows: `sma_20`/`sma_50` and `vol_zscore` exclude the current bar;
`ret_*` and `nifty_ret_5d` look back; `gk_vol`/`park_vol`/`mf_multiplier` use bar *i*'s own OHLC;
cross-sectional ranks use only the contemporaneous cross-section. The forward-looking columns
(`fwd_ret_*`, `fwd_alpha_5d`, `fwd_nifty_5d`) are targets and are excluded from the feature family.

## Result

Feature store: **1,015,831 rows, 423 symbols, 2,427 dates**, deduplicated
(`data/evidence/feature-store/mizan`).

Trained study: **43 instruments pooled, 104,232 feature rows, 104,146 governed label rows, 2,422
decision dates**; train 93,224 / validation 10,836, embargo 2. Threshold `-0.112503` (training base
rate, train-only). **`multiplicity_count = 1`.** Store: `data/evidence/models/mizan-pooled-v1`,
`model_43740a3a3fc47d68705fc1c5`, trial state `SUCCEEDED`, `verdict=RESEARCH_ONLY`.

| Strategy | Sharpe | Accuracy | Trades | Max DD | Total return |
|---|---:|---:|---:|---:|---:|
| **MIZAN (RIDGE)** | **-3.2427** | 0.5404 | 3,957 | 0.4294 | -0.4157 |
| NO_TRADE | 0.0000 | 0.5708 | 0 | 0.0000 | 0.0000 |
| BUY_AND_HOLD | -3.2890 | 0.4292 | 10,836 | 0.3991 | -0.3882 |
| PREVIOUS_SIGN | -4.1483 | 0.5096 | 4,657 | 0.5144 | -0.5047 |
| EQUITY_DUAL_MOMENTUM | -3.1996 | 0.4953 | 4,904 | 0.4047 | -0.3905 |

**Deflated Sharpe `0.000902785392` against a `0.95` gate. NOT PROMOTABLE.** Verified directly
against `GatePolicyV1(policy_id=...)`: `PASSES GATE: False`.

## What the numbers actually say

Every strategy that trades loses, and they all lose by roughly the same amount. That is the
signature of **cost domination, not of a bad model**. The governed label contract holds a position
for `LABEL_HORIZON_SESSIONS_V1 = 2` sessions and charges a real 0.224% statutory round trip. A
strategy evaluated on every one of 252 validation sessions therefore pays that round trip up to 252
times. BUY_AND_HOLD -- which is not a strategy at all, just "always long" -- loses 38.8% here for
exactly that reason.

Mizan is the second-best board entry and still loses 41.6%. Its 54.0% accuracy is below the 57.1%
obtained by never trading. **The only non-losing strategy is NO_TRADE.**

So the honest reading is not "Mizan has no edge" but something more specific and more useful: **no
signal in this family produces enough gross edge to survive a 2-session round trip at 0.224%.**
That is a property of the horizon and the cost model, and it applies to every baseline equally.

## What was NOT achieved, stated plainly

The founder asked for training on all the data. The feature store covers all **423** liquid names,
but the trained study covers **43**. The reason is a hard governed constraint, not a shortcut:

- `modeling/labels.py` refuses to build labels from an acquisition with no
  `historical_universe_authority`.
- Only **50 acquisitions in the entire repository** carry one, all in the NIFTY 50 cache. The
  all-market cache (3,267 symbols) has **zero** -- it was ingested before the research universe
  existed, so nothing bound it.
- Of those 50: 5 have no features in the store (ETERNAL, HDFCLIFE, JIOFIN, MAXHEALTH, SBILIFE), and
  2 more (RELIANCE, TECHM) sit on their own session calendars and cannot share a pooled fold.

Closing that gap needs a governed re-acquisition pass binding every name to one universe snapshot.
That reaches the provider, so it was not launched unilaterally.


## Why Mizan loses — measured, not inferred (2026-08-26)

`scripts/diagnose_mizan_loss.py` decomposes every governed label row into gross and net:

| | Per 2-session hold |
|---|---:|
| Mean **gross** return | **+0.000776** (+0.0776%) |
| Mean **cost** (real NSE statutory round trip) | **+0.002225** (+0.2225%) |
| Gross as a multiple of cost | **0.349x** |

**45 of 45 symbols have a positive gross mean. 0 of 45 have a positive net mean.**

`scripts/screen_mizan_horizon.py` then characterizes the execution contract itself — unconditional
average return of holding every name N sessions, against a cost charged once per round trip. No
model selects anything; no evidence store is written; **no multiplicity ordinal is spent**.

| Hold | Mean gross | Net | Gross/Cost | Annualized net |
|---:|---:|---:|---:|---:|
| **2** (the governed contract) | +0.001487 | **-0.000738** | **0.67x** | **-8.9%** |
| 3 | +0.002229 | +0.000004 | 1.00x | +0.0% |
| 5 | +0.003736 | +0.001511 | 1.68x | +7.9% |
| 21 | +0.015955 | +0.013730 | 7.17x | +17.8% |
| 63 | +0.048932 | +0.046707 | 21.99x | +20.0% |

**Break-even is at 3 sessions. `LABEL_HORIZON_SESSIONS_V1 = 2` sits below it.** The governed label
contract is loss-making before any model exists, which is why every baseline on Mizan's board also
lost and only NO_TRADE broke even.

Do **not** read the +17.8% at hold 21 as alpha. It is beta on current NIFTY 50 constituents over a
rising decade, with severe survivorship bias. The only claim it supports is that at longer holds a
model has positive material to select from; at hold 2 it has none.

### The correct next step is the horizon, not more data or more features

`LABEL_HORIZON_SESSIONS_V1` is referenced in `rows.py` (definition), `partitions.py`, `holdout.py`,
`validation.py`, and documented in `execution/maturity.py`. The horizon itself is hardcoded in
`labels.py:175-178` as `ordinal + 1` (entry) and `ordinal + 2` (exit). Making it configurable is a
bounded change, but it alters the governed execution contract for the whole system, not just Mizan,
so it is a founder decision rather than an implementation detail.


## Horizon made configurable, and Mizan retrained (ordinal 2)

`LABEL_HORIZON_SESSIONS_V1` is now a parameter rather than a hardcoded 2, threaded through
`labels.py`, `partitions.py`, `validation.py`, `cached_nifty50_costs.py` and
`run_governed_ridge_training.py`. The default is unchanged and
`label_contract_version_for(2)` returns the original string verbatim, so every existing label
dataset hashes exactly as before. A non-default horizon declares itself as
`next-open-net-return-h{N}-v1` rather than silently reusing the old contract identity.

Pre-declared rule, stated before the run: **take the shortest horizon with at least a 3x margin over
cost.** That is 10 sessions held, `--horizon-sessions 11` (3.35x). One shot, not a sweep.

| | ordinal 1 (1 session held) | **ordinal 2 (10 sessions held)** |
|---|---:|---:|
| MIZAN Sharpe | -3.2427 | **-0.4108** |
| MIZAN total return | -0.4157 | **-0.3157** |
| BUY_AND_HOLD | -3.2890 / -0.3882 | **+0.6920 / +0.2200** |
| PREVIOUS_SIGN | -4.1483 / -0.5047 | **+0.7932 / +0.2493** |
| NO_TRADE | 0.0000 | 0.0000 |
| Deflated Sharpe | 0.000903 | **0.175990** |

**The cost diagnosis is confirmed.** BUY_AND_HOLD moved from -38.8% to **+22.0%** on identical data
and an identical universe; the only change was how long a position is held. The 1-session contract
was destroying roughly 60 points of return in fees.

**And it falsifies the more comfortable reading of ordinal 1.** At ordinal 1 everything lost, so the
model's own skill was unmeasurable -- the cost drag masked it. With the drag removed the environment
is profitable and **Mizan still loses 31.6% while simply holding earns 22.0%**. Its accuracy (49.20%)
is below NO_TRADE (49.69%) and below BUY_AND_HOLD (50.31%).

So the honest conclusion is worse than "no edge": **the 15-feature linear ridge has negative skill on
this universe.** It is not that costs were hiding a good model; costs were hiding a bad one. More
instruments cannot repair negative skill -- that is a model-class problem, not a sample-size problem.

Deflated Sharpe 0.175990 against a 0.95 gate. **Still NOT PROMOTABLE**, and now also beaten by
buy-and-hold, which removes any argument for deploying it.

### Caveat that must travel with the ordinal-2 numbers

At a 10-session hold, consecutive decision dates have **overlapping holding windows**, so the 10,836
validation rows are not 10,836 independent observations. Purging and embargo (11 sessions) separate
train from validation, but they do not de-overlap labels *within* validation. Treat the ordinal-2
Sharpe as directionally informative and its significance as overstated.

## Why training on all 3,267 NSE symbols is the wrong move — measured

`scripts/screen_mizan_horizon.py` run against the full all-market cache:

| Universe | Mean gross, 2-session hold | Win rate | Annualized net |
|---|---:|---:|---:|
| NIFTY 50 (governed) | +0.1487% | 47.1% | -8.9% |
| **All 3,267 NSE** | **+0.5545%** | **44.4%** | **+51.8%** |

The all-market mean is **3.7x higher while the win rate is LOWER**. A distribution whose average
rises as its hit rate falls is one whose mean is carried by a thin right tail -- which is precisely
the shape survivorship bias produces. The cache holds **active listings only**: every company that
delisted, was suspended, or went to zero over the decade is absent by construction.

Training on it would produce headline numbers far better than anything above, and they would be
artifacts. The Rs 5 crore liquidity filter and the 423-name research universe exist to prevent this.


## The features DO predict — Mizan is pointed the wrong way (2026-08-26)

`scripts/screen_mizan_feature_ic.py` computes each feature's cross-sectional information
coefficient against the forward 10-session net return. All fifteen are reported; selecting the best
would be the exact error deflation exists to punish. Ungoverned diagnostic, no ordinal spent.

**8 of 14 measurable features are significant at |t| > 2, and every one of them is NEGATIVE:**

| Feature | Mean IC | t |
|---|---:|---:|
| sma_50_distance | -0.02588 | **-5.63** |
| rsi_14_centered | -0.02375 | **-5.33** |
| return_1 | -0.01700 | -4.33 |
| return_21 | -0.01792 | -4.07 |
| return_5 / cs_rank_momentum_5 | -0.01603 | -3.81 |
| sma_20_distance | -0.01649 | -3.76 |
| money_flow_multiplier | -0.01332 | -3.68 |

A negative IC on every trend and momentum measure means this universe **mean-reverts** at a
10-session horizon: names that rose recently underperform next. That is a real, consistent signal.

**Mizan gets 5 of those 8 signs backwards.** Comparing the ordinal-2 fitted coefficients against the
measured IC direction: 3 agree, **5 disagree**, including the three strongest momentum features. A
long-only model that scores high on recent strength therefore buys precisely the names about to
underperform, which is why its accuracy (49.20%) sits *below* random rather than at it.

Two causes, both specification errors rather than data problems:

1. **Severe collinearity.** `return_5` and `cs_rank_momentum_5` are the same underlying quantity;
   `rsi_14_centered`, `sma_20_distance` and `sma_50_distance` all measure trend. Ridge distributes
   weight unstably across collinear columns and signs flip.
2. **Three features carry no cross-sectional information at all.** `india_vix_level`,
   `india_vix_change_5` and `nifty_return_5` are market-wide values, identical for every name on a
   given date. They cannot rank a cross-section. They only add noise and collinearity. This is a
   design error I introduced in the v3 family.

### Why this does NOT license building a reversion model on this data

The ICs were measured on the whole 2016-2026 window. Specifying a model *because* of them and then
testing it on the same window is in-sample fitting -- the same mechanism as sweeping thresholds until
one publishes. The finding is a **hypothesis**, not a result.

The honest test needs data that did not produce the hypothesis. Two candidates exist:

- the **380 liquid names outside the governed 43**, which need the universe-authority re-binding
  described above -- this is the real value of the wider universe: independent validation, not more
  training rows;
- the **final holdout**, which `modeling/holdout.py` supports and which has never been opened. It is
  one-shot and should be spent on a candidate that is actually believed, not on a first attempt.

## Next safe action

Nothing here is promotable, so no promotion, bundle, or shadow session may be attempted from this
model. `active/` and `bundles/` in `data/evidence/models/mizan-pooled-v1` are empty and must stay
empty until a model actually clears the gate.

If the cost-domination reading is to be tested, the cheap next step is a **label-horizon screen
outside the governed store** -- no ordinal spent -- before any contract change to
`LABEL_HORIZON_SESSIONS_V1`. Do not open a second governed Mizan trial to test a horizon; that
spends ordinal 2 to learn something a screen answers for free.
