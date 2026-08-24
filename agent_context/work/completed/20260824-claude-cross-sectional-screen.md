# Cross-sectional screen: the first positive point estimate, and why it is not a result

STATUS: COMPLETE — research screen, **NOT governed evidence**  
OWNER: Claude Code — feature research  
DATE_UTC: 2026-08-24  
REVISION: `9436b8d`  
PRIOR SCREENS: `20260824-claude-alternative-feature-screens.md` (three, all negative)

## The frame change

101 governed trials and three screens all shared one frame: model each instrument alone, long-or-flat
on its own score. Under that frame a name's return is dominated by the market factor, so a per-name
model spends most of its variance on something it cannot separate from the index.

A cross-sectional design asks a different question — not "will INFY rise?" but "will INFY rise more
than its peers today?" — and cancels the common factor by construction. It is the standard equity
quant frame and the one variable never moved here.

Declared before running: 50 cached NIFTY 50 names over ten years; the **incumbent** v1/v2 six
(deliberately, since it beat the range/volume family — using the weaker one would confound a frame
test with a feature test); every feature cross-sectionally z-scored within each date; split **by
date**, never by row, because a row-wise split leaks the cross-section; equal-weight long the top 10;
holds 2 and 21; 0.224% charged per name per rebalance.

## Results, both holds, as declared

| Hold | Construction | Mean net | t | Sharpe | Rebalances |
|---:|---|---:|---:|---:|---:|
| 2 | long top 10 (validated rule) | -0.000868 | -1.09 | -0.70 | 307 |
| 2 | long-short (diagnostic) | -0.003505 | **-5.68** | -3.64 | 307 |
| 2 | cross-sectional IC | +0.02105 | 1.67 | | |
| 21 | **long top 10 (validated rule)** | **+0.009365** | **+1.18** | **+0.76** | **29** |
| 21 | long-short (diagnostic) | +0.007606 | +1.04 | +0.67 | 29 |
| 21 | cross-sectional IC | +0.04494 | 1.07 | | |

**At hold 21 the cross-sectional long-only portfolio is the first positive point estimate produced in
this entire line of work**: +0.94% net per 21-session period, Sharpe +0.76.

## Why it is not a result

**It is not significant.** t = 1.18 on 29 rebalances. At the same effect size, reaching t = 2.0 would
need about 83 rebalances — roughly **4.5 more years** of non-overlapping 21-session periods than the
ten-year cache contains. The sample is not close to sufficient, and no amount of re-slicing this data
creates the missing years.

**The most significant number in the grid says the strategy loses.** The hold-2 long-short result is
t = **-5.68**, nearly five times more significant than the hold-21 positive. Reading the +0.76 as the
finding while ignoring a much stronger negative one row above it would be cherry-picking by horizon.

**The sign flips with horizon.** A real cross-sectional momentum effect should be reasonably stable
across nearby holding periods. Strongly negative at 2 sessions and mildly positive at 21 is the
signature of noise, not of an effect.

## The asymmetry I am refusing

The previous record stopped after three negative screens and argued that stopping was disciplined:
consistent negatives are information, and a fourth look mostly raises the chance of mistaking noise
for signal. That argument does not become invalid because a result finally came out positive.

Stopping when results are negative and continuing when one turns positive is exactly the asymmetry
that manufactures false positives. It is the same mechanism as a stopping rule of "iterate until
satisfied", wearing a more respectable hat. So this screen is reported and closed on the same terms
as the three before it, and the positive point estimate is recorded as **insufficient evidence**, not
as encouragement.

## What this does and does not change

It does **not** justify a multi-instrument governed dataset contract. That change is real work —
`modeling/labels.py:135` binds every feature row to one acquisition manifest, so a cross-sectional
contract touches the dataset, label, fold and evidence identity paths — and the case for spending it
rests on a t of 1.18.

What it does change is the honest ranking of untried directions. Every single-name variation tested
is flatly negative; the cross-sectional frame at a monthly horizon is the only one that is merely
**inconclusive**. If the founder wants one more attempt, this is the direction with the least bad
evidence behind it — and the correct next step is more independent data, not more looks at this data.
A different universe, a different market, or a genuine out-of-sample period would test it. Re-slicing
these ten years would not.

## Search accounting

This is screen 4 (two configurations, holds 2 and 21). Together with the three prior screens, six
pre-declared configurations have now been evaluated against this same cached data outside the
governed store. None spent a multiplicity ordinal, and all are recorded so a later campaign can price
the search that preceded it.

## Reproduction

`scratchpad/screen_cross_sectional.py`, run with `PYTHONPATH=.` from the install root against
`data/evidence/market-cache/nifty50-current-20160822-20260821/store`.
