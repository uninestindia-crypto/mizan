# Cost sensitivity screen: would cheaper trading rescue any of this?

STATUS: COMPLETE
AGENT: Claude Code
DATE_UTC: 2026-08-26
STARTING_REVISION: `4306ec28`
TYPE: **Ungoverned screen.** No evidence store written, no multiplicity ordinal spent, no model
published. Recorded because an unrecorded search is invisible multiplicity to whoever screens the
same question next.

## Why this was run

`.launch/RESEARCH-DESIGN-BRIEF-NEXT-CAMPAIGN.md` section 5 ranked "a different cost regime" as the
**highest-value next direction**, on the reasoning that the 0.2225% NSE round trip was the binding
constraint behind every negative result. The cheapest possible test of that reasoning is to recompute
the already-measured signals at lower cost levels rather than to fit anything new.

**The reasoning was wrong, and this screen falsifies it.** The brief has been corrected.

## Finding 1 — cost does dominate at very short horizons, and only there

Re-ran `scripts/screen_mizan_horizon.py`'s measurement across four cost regimes, adding the
t-statistics the original screen did not compute. Unconditional drift: hold every name for N
sessions, non-overlapping windows, NIFTY 50 current constituents 2016-2026.

| HOLD | N | GROSS | SD | net @0.2225% | t | net @0.05% | t | net @0.02% | t | net @0% | t |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 1 | 119,243 | +0.000758 | 0.0204 | -0.001467 | **-24.90** | +0.000258 | +4.37 | +0.000558 | +9.46 | +0.000758 | +12.85 |
| 2 | 59,598 | +0.001487 | 0.0278 | -0.000738 | **-6.48** | +0.000987 | +8.66 | +0.001287 | +11.29 | +0.001487 | +13.05 |
| 5 | 23,846 | +0.003736 | 0.0443 | **+0.001511** | **+5.27** | +0.003236 | +11.29 | +0.003536 | +12.33 | +0.003736 | +13.03 |
| 10 | 11,899 | +0.007448 | 0.0614 | +0.005223 | +9.28 | +0.006948 | +12.34 | +0.007248 | +12.87 | +0.007448 | +13.23 |
| 21 | 5,638 | +0.015955 | 0.0923 | +0.013730 | +11.17 | +0.015455 | +12.58 | +0.015755 | +12.82 | +0.015955 | +12.98 |
| 63 | 1,877 | +0.048932 | 0.1687 | +0.046707 | +12.00 | +0.048432 | +12.44 | +0.048732 | +12.52 | +0.048932 | +12.57 |
| 252 | 433 | +0.238439 | 0.4883 | +0.236214 | +10.07 | +0.237939 | +10.14 | +0.238239 | +10.15 | +0.238439 | +10.16 |

Cost is a constant shift per period, so it moves the mean and leaves the standard deviation
untouched; every t in a row shares one standard error.

**The "cost dominates" story is true only at holds 1-2.** From hold 5 onward the unconditional drift
already beats the full statutory round trip, at t = +5.27 and rising. Cheaper trading flips holds 1
and 2 positive but changes nothing about the horizons where research actually operated.

### This drift is beta, and it is survivorship-inflated. Do not read it as an opportunity.

The cache is `nifty50-current` — **today's** constituents, back-filled ten years. Companies that fell
out of the index are absent, so the measured drift is upward-biased by construction. The honest
reading of a t = +13 unconditional drift is "the surviving members of a large-cap index went up over
a decade", which requires no model and is not a finding.

It is also the direct explanation of why equal-weight beat Mizan out of sample: the drift is real
enough to look like performance, and capturing it needs no model at all.

## Finding 2 — the selection edge is algebraically invariant to cost

This is the decisive result.

`scripts/screen_mizan_out_of_sample.py:100` builds every target as:

```python
opens[i + 1 + HOLD_SESSIONS] / opens[i + 1] - 1.0 - ROUND_TRIP_COST
```

Both arms then average those same targets — line 202 over the top 20% by model score, line 203 over
all names — and line 209 takes the difference. So:

```
edge = mean(top-K net) - mean(all net)
     = (mean(top-K gross) - c) - (mean(all gross) - c)
     = mean(top-K gross) - mean(all gross)
```

**The cost term cancels exactly.** Demonstrated numerically on the same construction:

| cost charged | top-20% net | equal-wt net | SELECTION EDGE |
|---|---:|---:|---:|
| 0.2225% (NSE) | +0.126627 | +0.005389 | **+0.121237245** |
| 0.05% | +0.128352 | +0.007114 | **+0.121237245** |
| 0.02% | +0.128652 | +0.007414 | **+0.121237245** |
| 0.00% | +0.128852 | +0.007614 | **+0.121237245** |

Both absolute columns move with cost. The edge is identical to nine decimal places.

**Therefore Mizan's measured selection edge of -0.000022 (t = -0.07) is exactly -0.000022 at every
cost level, including zero.** Free trading does not rescue it. There is no cost regime in which a
model with no selection edge acquires one.

## What this changes

- **Direction 1 of the research design brief is demoted**, from highest-value to a narrow special
  case. Corrected in `.launch/RESEARCH-DESIGN-BRIEF-NEXT-CAMPAIGN.md` section 5.
- A cheaper cost regime remains relevant to exactly one thing: strategies operating at **holds 1-2**,
  where cost genuinely is the binding constraint. Note that the only replicated effect this
  repository ever found lives at that horizon and is a **loss** (hold-2 long-short, t = -5.68 on 50
  names strengthening to **-7.85** on 423).
- The trap described in the brief's section 1 needs restating. It is not "costs demand long horizons
  and long horizons starve the sample". At holds >= 5 costs are already beaten. The real position is
  simpler and worse: **the model adds nothing on top of a drift that requires no model**, and that is
  invariant to what trading costs.

## Correction to my own prior reasoning

I proposed this calculation while telling the founder that costs were the binding constraint and
that this was the highest-value next step. The calculation cost about ten minutes and showed the
premise was false. Recorded rather than quietly dropped, because the brief's own rule R5 requires
that a screen end a direction on its result rather than on whether the result was the hoped-for one.

The screen was still worth running: it converted an assumption that was steering the next campaign
into a measured negative, for no ordinal and no fitting.

## Reproduction

Cost sweep: `scratchpad/cost_sweep.py` against
`data/evidence/market-cache/nifty50-current-20160822-20260821/store`, 50 symbols, non-overlapping
windows. Cancellation: the algebra above, plus the numerical demonstration reproduced in this record.

## Next safe action

None arising. This closes "would cheaper trading help" as a question. The remaining directions in the
brief (fundamentals, a different market, intraday combined with low cost) are unaffected, except that
the intraday direction can no longer lean on cost reduction alone as its rationale.
