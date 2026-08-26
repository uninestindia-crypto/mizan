# Research design brief: the next campaign, if there is one

BRIEF_ID: RESEARCH-DESIGN-NEXT-CAMPAIGN-20260826
AUTHOR: Claude Code
DATE_UTC: 2026-08-26
STATUS: PRE-DECLARATION TEMPLATE — nothing has been fitted against this brief

This brief exists because the failure mode of the last eighteen months of work was not a bad model.
It was an experimental design in which **no model could have passed**, run nine times. Before any
further research is funded, the design has to change. This document states how, and what would have
to be true for a result to count.

---

## 1. The trap, stated as arithmetic

Every negative result in this repository is explained by one squeeze:

- **Costs punish very short holding periods.** The NSE statutory round trip is **0.2225%**. At a
  1-session hold the unconditional net return is **-0.001467, t = -24.90**; at 2 sessions,
  **-0.000738, t = -6.48**. Holds of 1-2 sessions are not marginal; they are hopeless.
- **Long holding periods starve the sample.** A 21-session hold over a ten-year window yields
  **29 independent rebalances**. The single positive point estimate ever produced — cross-sectional
  hold-21, Sharpe +0.76 — carried **t = 1.18** and could not be confirmed.

**Correction recorded 2026-08-26.** An earlier draft of this brief claimed the squeeze was
cost-driven throughout. It is not. Measured across four cost regimes
(`20260826-claude-cost-sensitivity-screen.md`), the unconditional drift **already beats the full
statutory cost from hold 5 onward**, and a *selection* edge cancels the cost term algebraically. So
the accurate statement of the trap is narrower and less flattering: costs kill holds 1-2, the sample
starves at holds >= 21, and in the workable middle the models simply **added nothing on top of a
drift that requires no model at all**. That last part is invariant to what trading costs.

Nine model variations were run inside that squeeze. All nine failed. The squeeze explains the
failures at the horizon extremes without reference to the models at all — and in the middle, where
the horizon is workable and cost is already beaten, the models were measured directly against the
do-nothing comparator and did not beat it. Neither region leaves a case that better features would
have changed the outcome.

## 2. What the gate actually demands

Annualized Sharpe required to reach `GatePolicyV1.min_deflated_sharpe = 0.95`:

| validation periods | N=3 trials | N=51 trials | N=110 trials |
|---:|---:|---:|---:|
| **63** | 5.12 | **8.13** | 8.73 |
| 126 | 3.58 | 5.65 | 6.06 |
| 252 | 2.51 | 3.96 | 4.25 |
| **504** | **1.77** | 2.79 | 2.99 |

The best Sharpe this system has ever produced on this market is **3.2207**, and at its ordinal of 8
with 63 validation periods that still only reached DSR 0.5632.

**Read the corners.** At 63 periods and 51 trials the bar is Sharpe 8.13 — no equity strategy in
public literature sustains that. At 504 periods and 3 trials the bar is **1.77**, which is ordinary.
The gate is not unreasonable. The design is what made it unreachable.

**Design implication, and it is the whole point of this brief: validation length and trial economy
buy more than model quality does.** Quadrupling the validation window and cutting trials from 51 to 3
moves the bar from 8.13 to 1.77 — a factor of 4.6. No feature engineering has ever delivered
anything close to that.

## 3. What is exhausted — do not re-run these

Recorded so a future campaign prices the search that preceded it, and so nobody spends an ordinal
rediscovering a known negative.

| Attempt | Result |
|---|---|
| Single-instrument daily, long-only, holds 2-21 | 101 governed trials, none promotable |
| NIFTY 50 v1 campaign (51 trials) | best re-deflated DSR 0.397794 |
| NIFTY 50 v2 campaign (50 trials) | best re-deflated DSR **0.217695** |
| Alternative 6-feature family | t(IC) 1.08 vs control 2.34 — worse than the family that already failed |
| Label-horizon grid (2, 5, 10, 21) | net return climbs toward zero, **never turns positive** |
| Cross-sectional, 50 names, hold 21 | Sharpe +0.76, **t = 1.18** — inconclusive |
| Cross-sectional, 423 names, hold 21 | Sharpe +0.12, **t = 0.19**, IC flips sign — did not replicate |
| Mizan 15-feature pooled cross-sectional | ordinals 1-2, Sharpe -3.24 and -0.41 |
| Mizan corrected specification, out-of-sample on 378 untouched names | selection edge **-0.000022, t = -0.07**; loses to equal-weight |

**The constant across all nine is the input: NSE daily OHLCV technicals.** That is the variable that
has never been changed, and it is the one this brief requires changing.

Note also the one thing that *did* replicate, and got stronger with more data: the **hold-2
long-short loss**, t = -5.68 on 50 names becoming **t = -7.85** on 423. Strengthening with more data
is what a real effect looks like. The real, replicated, statistically robust finding of this research
programme is that this strategy class loses money at short horizons on this market.

## 4. Binding design rules for any next campaign

A campaign that violates any of these should not be started.

**R1 — Change the input, not the model.** A new feature family on NSE daily OHLCV is refused by this
brief. Section 3 shows the input is the exhausted variable. Acceptable changes: a different asset
class, a different market, intraday microstructure, fundamentals, or any data source whose cost
structure differs from 0.2225% per round trip.

**R2 — Declare the validation window before fitting, and make it >= 252 periods.** Below that the
required Sharpe exceeds anything the literature supports. If the data cannot supply 252 independent
periods at the intended horizon, the horizon or the data is wrong — not the model.

**R3 — Budget the trials before starting, and keep N small.** Declare the maximum number of trials
in writing before the first fit. A 50-name sweep costs 50 ordinals and, per the table, roughly
doubles the required Sharpe. Prefer 3 well-motivated trials to 50 exploratory ones. Every ordinal is
spent permanently and raises the bar for all future work in this repository.

**R4 — Name the honest comparator before fitting.** The Mizan out-of-sample screen only became
interpretable when equal-weight was placed beside it: +0.65% looked fine until the benchmark earned
+0.66% with no model at all. Declare the do-nothing comparator in advance. A strategy that does not
beat it has no result regardless of its absolute numbers.

**R5 — Declare the stopping rule in advance, symmetrically.** State before fitting what result ends
the campaign. It must stop on a positive as readily as on a negative. Stopping on negatives and
continuing on positives is how false positives are manufactured, and this repository has already
caught itself reasoning that way once.

**R6 — Screen ungoverned before spending an ordinal.** Every cheap screen so far cost nothing and
answered the question. Governed trials are for candidates already believed, not for exploration.

**R7 — Hold out data that never informed the hypothesis.** `modeling/holdout.py` supports a one-shot
final holdout that has never been opened. It stays closed until a candidate clears every prior gate.

## 5. Directions ranked by remaining evidence

Ranked by what the existing evidence does and does not rule out. None is endorsed; the ranking is
about which is not yet disproven.

1. ~~**A different cost regime.**~~ **RUN AND FALSIFIED, 2026-08-26** — see
   `agent_context/work/completed/20260826-claude-cost-sensitivity-screen.md`. This was ranked first
   on the reasoning that cost was the binding constraint. It was measured instead of assumed, and
   the reasoning is wrong on both halves. (a) The unconditional drift already beats the full
   statutory round trip from **hold 5 onward** (net +0.001511, t = +5.27), so cost only dominates at
   holds 1-2. (b) More decisively, a **selection edge is algebraically invariant to cost**: both arms
   of the comparison are averages of the same cost-shifted targets, so the constant cancels in the
   difference — demonstrated identical to nine decimal places across 0.2225%, 0.05%, 0.02% and zero.
   Mizan's -0.000022 selection edge is -0.000022 at **zero** cost. No cost regime gives a model an
   edge it does not have. Cheaper trading remains relevant only to strategies operating at holds
   1-2, where the one replicated effect on this market is a **loss**.
2. **Fundamentals / lower-frequency data.** Naturally long-horizon, so cost drag amortises, and
   uncorrelated with everything tried. Constraint: ten years of quarterly data gives ~40 periods,
   which fails R2. Would need a wide cross-section to compensate.
3. **Intraday microstructure.** The one replicated effect lives at short horizons. Constraint: it
   replicated as a *loss*, and short horizons are where costs dominate — so this only makes sense
   combined with direction 1.
4. **A different market.** Cleanest test of whether the negative is about the model class or about
   NSE specifically. Constraint: new data acquisition, new authorities, new cost model.

**Explicitly not recommended: another feature family on NSE daily bars.** That is direction zero, it
has been run nine times, and R1 refuses it.

## 6. Pre-declaration template

Copy this into a work record and complete it **before the first fit**. An incomplete field is a
reason not to start.

```
CAMPAIGN_ID:
HYPOTHESIS (one sentence, falsifiable):
DATA SOURCE (and why it is not NSE daily OHLCV):
COST MODEL (round-trip %, and its authority):
HORIZON (sessions):
VALIDATION PERIODS (must be >= 252):
MAX TRIALS (ordinal budget, binding):
REQUIRED SHARPE at that (periods, trials) to reach DSR 0.95:
HONEST COMPARATOR (the do-nothing benchmark):
STOPPING RULE ON A NEGATIVE:
STOPPING RULE ON A POSITIVE:
UNGOVERNED SCREEN RUN FIRST? (y/n, and its result):
HOLDOUT: closed until ____
```

## 7. The default, if none of this is funded

Research on this market and this model class is closed, and that is a conclusion rather than a pause.
The platform is the asset: governed acquisition, point-in-time features, cost-aware labels, purged
folds, multiplicity accounting, and a promotion gate that has now correctly refused **every** model
put in front of it — 101 governed trials, two Mizan trials, and one strategy that tried to reach an
execution surface without a verdict at all.

A system that says no correctly, 104 times, is the durable result of this work.
