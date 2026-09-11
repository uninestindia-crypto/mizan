# Active work: turn the all-market dump into a defensible research universe

STATUS: COMPLETE — universe built; the cross-sectional hypothesis did not replicate  
OWNER: Claude Code — universe authority  
TOOL: Claude Code  
STARTED_UTC: 2026-08-25T09:00:00Z  
STARTING_REVISION: `4ee83f77`  
WORKTREE_OR_BRANCH: `D:\quant_system` on `main`

## What arrived

`data/evidence/market-cache/all-market-20160822-20260821` — **3,267 unique symbols, 4.6 million
bars**, ingested by another agent
(`20260824-2105Z-antigravity-all-market-ingestion-and-analysis.md`). This is a 65x expansion of the
cross-section over the 50 NIFTY names every prior result used, and it is the "more data, not more
models" direction I recommended.

It is also not usable as delivered, for reasons that would manufacture a false result if ignored.

## Hazards, measured

| Hazard | Measured |
|---|---|
| **Survivorship bias** | The ingestion record states the universe is "all **active** NSE listed equities". Delisted and failed companies are absent by construction. Over a ten-year window this biases every backtest optimistic |
| Listing bias | Only **1,289 of 3,267** have >= 9.5 years of history. The rest listed later, so early periods have a smaller and different cross-section |
| Untradeable segments | **437 SME** and **19 PCA** (surveillance) names. SME platform liquidity does not support the 0.224% cost model |
| Circuit locks | **718 names (22%)** have >5% circuit-locked days — days on which the quoted price is not transactable |

## The filter, declared before any result

Exclude SME and PCA segments; require >= 9.5 years of history; require median daily turnover above a
liquidity floor. Cascade:

| Filter | Names |
|---|---:|
| All profiled | 3,267 |
| >= 9.5 years history | 1,289 |
| + median turnover >= Rs 1 crore | 734 |
| + median turnover >= Rs 5 crore | 423 |
| + median turnover >= Rs 10 crore | 291 |

**Rs 5 crore is the declared floor.** At Rs 1 crore a Rs 10 lakh position is 10% of median daily
turnover, which the 0.224% statutory cost model does not remotely describe — real cost would be
dominated by spread and impact, neither of which this system models. Rs 5 crore keeps 423 names,
still **8.5x** the cross-section used so far, at a size where the cost model is arguable rather than
fictional.

## The bias that cannot be filtered away, and what it means for reading results

Survivorship cannot be removed from this cache — the delisted names are simply not in it. That has a
specific and useful consequence for interpretation:

- A **positive** result on this universe is weak evidence. The bias pushes in exactly that direction.
- A **negative** result is strong evidence. The bias was working in favour of the strategy and it
  still failed.

Any result from this universe must be reported with that asymmetry attached, not as a symmetric test.

## Owned paths

- `data/authorities/nse-research-universe-liquid-10y.csv` (new)
- `scripts/build_research_universe.py` (new)
- `agent_context/work/active/20260825-claude-expanded-universe-authority.md` (this file)

## Non-goals

- Re-running any governed campaign. This produces a universe, not evidence.
- Tuning the liquidity floor to whatever produces a nicer downstream number. It is declared above at
  Rs 5 crore with a stated reason and is not revisited after seeing results.
- Claiming the survivorship bias is handled. It is documented, not removed.

## Plan

1. COMPLETE — audit the cache; measure the hazards; declare the filter.
2. Build the universe authority, content-bound like the NIFTY 50 one.
3. COMPLETE — re-ran the already-declared cross-sectional configuration, unchanged.

## Universe built

`data/authorities/nse-research-universe-liquid-10y.csv` — **423 names**, 8.5x the cross-section used
by every prior result. Exclusions recorded by the builder:

```
profiled symbols : 3267
  dropped history < 9.5y        : 1539
  dropped turnover < Rs 5cr     : 849
  dropped segment SME           : 437
  dropped segment PCA           : 19
selected         : 423
```

## The cross-sectional hypothesis did not replicate

The only non-negative direction in this entire line of work was the 50-name cross-sectional screen at
a 21-session hold: Sharpe +0.76, t = 1.18. I recorded then that it was **not** a result, and that the
correct next step was more independent data rather than more looks at the same ten years. This is
that test. Configuration unchanged; the only translation was holding the selection *fraction* at the
top 20% rather than the absolute top 10, so a 423-name universe is not silently made 8x more
selective.

| | 50 names | **423 names** |
|---|---:|---:|
| **hold 21, long-only** Sharpe | **+0.76** | **+0.12** |
| hold 21, long-only t | +1.18 | **+0.19** |
| hold 21, long-short mean net | +0.007606 | **-0.006449** |
| hold 21, cross-sectional IC | +0.04494 | **-0.02212** |
| hold 2, long-short t | -5.68 | **-7.85** |

**The positive vanished.** Sharpe collapsed from +0.76 to +0.12 and t from 1.18 to 0.19. The
long-short construction flipped from positive to negative, and the cross-sectional IC flipped sign
too. On 8.5x the evidence, the effect is gone.

**The one thing that replicated is the loss.** The hold-2 long-short result did not weaken with more
data — it got *stronger*, from t = -5.68 to **t = -7.85**. That is what a real effect looks like when
you add data, and the real effect here is that the strategy reliably loses at short horizons.

## Why this is a strong negative rather than an inconclusive one

The universe is survivorship-biased by construction — active listings only. The bias pushes results
in the strategy's favour. It failed anyway, and its one apparent success disappeared when the
cross-section widened. A negative under a favourable bias is stronger evidence than a negative under
a neutral one.

## What this closes

The cross-sectional frame was the last untried direction and the only one with non-negative evidence
behind it. It has now been tested on 8.5x the names with an unchanged configuration and did not
replicate. Combined with 101 governed trials and six prior screens, there is no remaining untested
variation of this model class on this market that the existing evidence recommends.

Adding more data did the job it was supposed to do: it killed a result that was never real.
