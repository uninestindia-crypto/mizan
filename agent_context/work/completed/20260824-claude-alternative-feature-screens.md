# Feature-family screens: three pre-declared looks, all negative

STATUS: COMPLETE — research screens, **NOT governed evidence**  
OWNER: Claude Code — feature research  
DATE_UTC: 2026-08-24  
REVISION: `bd03b6e`

## Why this record exists even though nothing was published

Three screens were run against the real cached ten-year NIFTY 50 data. None wrote to an
`EvidenceStore`, none spent a multiplicity ordinal, none published a model. **They are still a search
over the same data, and an unrecorded search is invisible multiplicity.** Anyone who later screens
one of these families without knowing this happened would be taking a second look while believing it
was a first. That is what this record prevents.

## The request, and the hazard in it

The instruction was to try a different feature set and "do till you are not satisfied". That is a
*stopping rule*, and a stopping rule of "keep going until the number pleases me" makes every reported
number a selected maximum. So each family was declared before it was run, run to completion whatever
it showed, and reported either way.

## Screen 1 — a genuinely different feature family

The v1/v2 family is close-only: three overlapping returns, RSI, distance-to-SMA, ATR. It ignores the
open, the intraday high/low structure, and volume entirely. Declared before running, same 21-bar
window so the comparison is *different information from the same window*:

`gap_open`, `close_location`, `range_expansion_14`, `volume_z_20`, `dollar_volume_ratio`,
`price_position_20`.

| Metric | Result |
|---|---:|
| Mean validation IC | +0.00732 |
| t (IC / cross-name SE) | **+1.08** |
| Positive IC | 31 of 50 |

Not significant.

### A bug in the screen that inflated its own result

The first run reported t = **1.53**. The cache holds two verified DATASET resources per symbol; I
counted both. They are the same series, perfectly correlated, so they contribute no independent
information — but they doubled n and shrank the cross-name standard error by sqrt(2). Deduplicating
by symbol gives 50 names and t = 1.08. **A 40% inflation of my own headline number, from a
bookkeeping artifact, in a screen whose entire purpose was to be sceptical.** Recorded because it is
the second time in two days that a number of mine needed correcting after it was written down.

## Screen 2 — the existing family as a control

Same screen, same split, same data, but the *existing* v1/v2 close-only family. This calibrates the
instrument: it answers whether t = 1.08 is good or bad in this setup.

| Family | Mean IC | t | Positive |
|---|---:|---:|---:|
| New range/volume six | +0.00732 | +1.08 | 31/50 |
| **Existing v1/v2 close-only six** | **+0.01556** | **+2.34** | **35/50** |

**The new family is worse than the one that already failed.** That is the direct answer to "try a
different feature set": tried, pre-declared, and it does not improve on what exists.

The control also produced something more useful than the screen it was controlling for. The existing
family has a *detectable gross* signal (t = 2.34) yet produced nothing promotable across 101
governed trials. Best names' gross top-half edge was about 0.2%, against a measured 0.224% round
trip. That suggested a sharper diagnosis than "no edge": an edge roughly equal to its cost.

## Screen 3 — testing that diagnosis, which falsified it

The diagnosis makes a falsifiable prediction. Round-trip cost is *fixed* per trade; edge should grow
with holding period; so net edge should improve with horizon. Grid declared in advance — holds 2, 5,
10, 21 — labels **net** of the 0.224% round trip, all four reported.

| Hold | Mean IC | t(IC) | Mean net return | t(net) |
|---:|---:|---:|---:|---:|
| 2 | +0.01556 | +2.34 | -0.002100 | **-13.57** |
| 5 | +0.00650 | +0.60 | -0.001900 | -3.72 |
| 10 | +0.00668 | +0.44 | -0.002117 | -1.99 |
| 21 | +0.01905 | +0.93 | -0.000264 | -0.13 |

Net return does climb toward zero as the fixed cost amortises, which is consistent with the cost
story. But it **never becomes positive**. At hold 21 it is `-0.000264` with t = `-0.13`:
indistinguishable from zero, not profitable. Meanwhile the IC's significance collapses from 2.34 to
under 1.

**So the diagnosis is wrong.** "Real edge buried by costs" predicts a positive net edge once costs
are amortised. Removing the cost drag revealed nothing underneath. The gross IC at hold 2 is most
likely short-horizon microstructure that does not survive as tradeable return.

## Conclusion, and why stopping here is the disciplined answer rather than the tired one

Three pre-declared looks, all negative:

1. A genuinely different feature family is **worse** than the existing one.
2. The existing family's gross signal does not survive costs at any horizon tested.
3. Extending the horizon removes the cost drag and yields **zero**, not profit.

I am not satisfied — a positive result would be more satisfying. But "keep going until satisfied" is
precisely the stopping rule that manufactures false positives, and three consistent negatives is
information, not an invitation to look a fourth time. Each additional look raises the chance that
noise is mistaken for signal, and nothing here suggests a fourth would differ.

**Nothing here justifies building feature schema v3.** Extending the governed contract to accommodate
a family that screens worse than the incumbent would spend real engineering and real multiplicity on
a hypothesis the cheap test already rejected. That was the point of screening before governing.

## What would justify another look

Not another feature family on the same data. The invariant across all of this is a single-instrument,
daily, long-only, two-to-twenty-one session frame. A genuinely different attempt would change the
frame — a cross-sectional design that ranks names against each other rather than modelling each
alone, which the governed dataset contract cannot currently express
(`modeling/labels.py:135` is single-instrument). That is a modelling-contract change, not a feature
change, and it should be costed as one.

## Reproduction

`C:/.../scratchpad/screen_range_volume.py`, `screen_control_v2.py`, `screen_horizon.py`, run with
`PYTHONPATH=.` from the install root against
`data/evidence/market-cache/nifty50-current-20160822-20260821/store`. Scratch files, not committed;
the numbers above are the record.
