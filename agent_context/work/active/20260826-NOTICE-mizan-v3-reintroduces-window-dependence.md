# NOTICE: the Mizan v3 feature family reintroduces the window-dependence defect schema v2 closed

FILED_UTC: 2026-08-26
FILED_BY: Claude Code
STATUS: NOTICE (additive; no other record is edited)
SEVERITY: **P1 Critical for execution.** Not a defect in any published research result.
SUBJECT: `quantos.mizan_crosssectional_fifteen` v1, `scripts/build_mizan_feature_store.py`,
         `modeling/pooled.MIZAN_WINDOW_BARS`

## What was found

`agent_context/decisions/20260824-canonical-feature-window.md` exists because Wilder RSI-14 and
ATR-14 **seed at the start of the supplied sequence**, so training's expanding prefix and execution's
retained prefix produced different values for the same decision bar. The fix was schema v2: consume
exactly the trailing 21 point-in-time-available bars, enforced at the shared kernel boundary "so the
two sides cannot diverge by accident".

**The v3 Mizan family reintroduced the same defect.**
`scripts/build_mizan_feature_store.py:119` calls `wilder_rsi(closes)` on the **entire** close series
and then indexes `rsi[i]`, so `rsi_14_centered` at any decision bar is a function of how much history
was supplied. Its own docstring states the causality property ("index i is a function of
closes[: i + 1]") but that is precisely the problem: it depends on everything before i, not on a
bounded window.

## Measurement

Worst-case `|RSI(window) - RSI(full series)|` over **300 random series across three volatility
regimes**, converted to the feature the model consumes (`rsi/100 - 0.5`) and expressed against that
feature's own published standardization scale (`0.12234317`, from the Mizan model manifest):

| window fed | worst RSI error | worst feature error | **in feature standard deviations** |
|---:|---:|---:|---:|
| **51** (`MIZAN_WINDOW_BARS`) | 3.005e+00 | 3.005e-02 | **2.46e-01 sd** |
| 75 | 5.225e-01 | 5.225e-03 | 4.27e-02 sd |
| 100 | 7.640e-02 | 7.640e-04 | 6.24e-03 sd |
| 150 | 2.756e-03 | 2.756e-05 | 2.25e-04 sd |
| 200 | 4.940e-05 | 4.940e-07 | 4.04e-06 sd |
| 300 | 3.046e-08 | 3.046e-10 | 2.49e-09 sd |
| 373 | 9.692e-11 | 9.692e-13 | 7.92e-12 sd |
| **400** | 2.095e-11 | 2.095e-13 | **1.71e-12 sd** |
| 500 | 2.842e-14 | 2.842e-16 | 2.32e-15 sd |

**At the declared window of 51 bars the feature is wrong by up to a quarter of its own standard
deviation** — from nothing but how much history happened to be retained.

### The decay is analytic, so this is not an empirical accident

Wilder RSI is an EMA with `alpha = 1/14`, so the seed's influence decays as `(13/14)^n`:

| n | `(13/14)^n` |
|---:|---:|
| 51 | 2.283e-02 |
| 200 | 3.656e-07 |
| 373 | 9.888e-13 |
| 400 | 1.337e-13 |

The measured errors track this exactly. The convergence point is a property of the estimator, not of
the sample.

## Why `MIZAN_WINDOW_BARS = 51` is the wrong number

51 = 50 warmup + the decision bar, sized for the **longest explicit trailing window** (the 50-session
SMA). That reasoning is correct for `sma_50_distance`, which is a plain mean over a bounded window
and is exactly reproducible from 51 bars. It is wrong for `rsi_14_centered`, which is recursive and
has no bounded window at all.

The constant sizes the family by its longest *explicit* window while one member has an *implicit*
unbounded one.

## Consequences

**1. Execution from a 51-bar window would silently produce wrong features.** This was live: my own
`execution/cross_sectional_strategy.py` hardcoded `CROSS_SECTIONAL_WINDOW_BARS = 21` while citing
`MIZAN_WINDOW_BARS` in the same comment — wrong twice over. Corrected to import the constant, and
this notice is why the constant itself now needs revising.

**2. A trailing-400 rule reproduces the published store everywhere — verified, and better than I
first predicted.** I initially wrote that rows between ~50 and ~400 bars into each series would be
irreproducible. **That was wrong, and is withdrawn.** A "trailing *up to* 400 bars" rule takes
`closes[max(0, i-399) : i+1]`, which for early rows *is* the full prefix — exactly what training
used. So it matches training identically below 400 bars and converges to it above.

Verified against the real published store for RELIANCE (2,427 published rows, 2,479 cached bars).
`rsi_14_centered`, published vs recomputed:

| date | bars in | published | full-prefix diff | **w=400 diff** | w=51 diff |
|---|---:|---:|---:|---:|---:|
| 2016-11-04 | 51 | -0.1847649710 | +4.44e-11 | **+4.44e-11** | +4.44e-11 |
| 2017-01-16 | 101 | +0.0519681680 | +4.77e-11 | **+4.77e-11** | +4.29e-03 |
| 2017-06-13 | 201 | -0.0585424412 | -2.49e-11 | **-2.49e-11** | **+1.20e-02** |
| 2018-01-17 | 351 | -0.0119864658 | -4.15e-11 | **-4.15e-11** | +8.54e-04 |
| 2018-06-14 | 451 | +0.2320319001 | +1.31e-11 | **+1.31e-11** | +1.03e-02 |
| 2021-09-30 | 1266 | +0.2080252111 | -8.11e-12 | **-8.22e-12** | -5.16e-04 |
| 2026-08-21 | 2479 | +0.0220907240 | +1.47e-11 | **+1.47e-11** | **+1.29e-02** |

The residual ~1e-11 on every row is the store's own 10-decimal CSV rounding, not disagreement.

Two things are established by this table. The **full-prefix reproduction is exact**, which confirms
the training computation is understood correctly. And **w=400 is exact at every sampled date**, from
51 bars in to 2,479 — while **w=51 is wrong by up to 1.29e-02**, roughly a tenth of that feature's
standard deviation, on real data rather than simulated.

**3. No published research result is invalidated.** Training and the out-of-sample screen both fed
full prefixes, so both sides were internally consistent. The defect is a barrier to *execution*, and
to any future claim that execution reproduces training. It does not change Mizan's measured selection
edge of -0.000022, and both Mizan models remain RESEARCH_ONLY on other grounds entirely.

## Required repair before any Mizan model can execute

Adopt a canonical window for v3 the way `20260824-canonical-feature-window.md` did for v2, sized by
the **recursive** member rather than the longest explicit one. `400` is the defensible choice:
worst-case error `1.71e-12 sd`, below float noise, with analytic backing at `(13/14)^400 = 1.34e-13`.

That is a change to the v3 schema contract and to `MIZAN_WINDOW_BARS`, so it belongs to whoever owns
the schema, not to this notice. The alternative — carrying RSI state across calls — is rejected on
the same grounds v2 rejected it: state that travels between training and execution is exactly what
lets the two diverge.

## Standing lesson

v2 closed this defect for the six-feature family, and a new family reopened it four days later
because the constant was sized by inspection of the feature list rather than by the estimator's
mathematics. A schema declaring a fixed window should be required to **prove** each member is
reproducible from it. Nothing currently enforces that, and no test would have caught this.
