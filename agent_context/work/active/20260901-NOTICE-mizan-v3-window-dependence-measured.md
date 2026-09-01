# NOTICE: the Mizan v3 window dependence is real in mechanism and not observable in values

STATUS: NOTICE (additive; no other record is edited)
DATE_UTC: 2026-09-01T12:10:00Z
FILED_BY: Claude Code, `20260901-1030Z-claude-seven-item-sweep.md`
SUBJECT_RECORD: `agent_context/work/active/20260826-NOTICE-mizan-v3-reintroduces-window-dependence.md`
  which records SEVERITY: **P1 Critical for execution**

## The subject notice is correct about the mechanism

`scripts/build_mizan_feature_store.py:119` computes `wilder_rsi(closes)` over an instrument's
**entire** close series and indexes `rsi[i]`, while `execution/mizan_live_features.py:141` truncates
to the trailing `MIZAN_CANONICAL_WINDOW_BARS`. Wilder RSI seeds at the start of the supplied
sequence, so the two sides are mathematically different functions of the same decision bar. That is
the defect `20260824-canonical-feature-window.md` was written to remove, reappearing in a new
feature family. I confirm all of that.

## What was not measured, and now is

The question the severity turns on is **how much** they differ at the window actually in use. That
is measurable rather than arguable, and I measured it: 2,460 closes -- the ten-year series the
builder feeds -- comparing `wilder_rsi(full_prefix)[i]` against
`wilder_rsi(closes[i+1-400 : i+1])[-1]` at every decision bar.

| Window | Worst divergence vs the full prefix |
|---:|---:|
| 51 | 2.207e+00 |
| 100 | 6.956e-02 |
| 200 | 4.811e-05 |
| **400 (canonical)** | **2.079e-11** |

The store publishes to 10 decimals, so the canonical window agrees with the training prefix
**below the published quantisation**. And the two regimes are exhaustive:

- history <= 400 bars: `canonical_mizan_window` and the builder both take the whole prefix, so they
  are bit-identical;
- history > 400 bars: they differ by less than 1e-10.

**Training and execution therefore score the same published values everywhere.** The reason is
Wilder's geometric decay: after 400 bars the seed carries weight `(13/14)**386`, about 1e-12.

## Why this is a downgrade in severity and not a dismissal

Read the table again in the other direction. The same procedure detects divergence of **whole RSI
points** at 51 bars and 5e-05 at 200. It is a method that can find a difference; it finds none at
400. That is what makes the negative result evidence rather than a limitation of the measurement,
and it is why the equivalence is now four tests rather than a paragraph.

What remains true, and is why I have not closed the subject notice:

- The guarantee is **numerical, not structural**. It holds because 400 happens to be far enough out
  on the decay curve, not because the builder is prevented from consuming more. Anyone lowering
  `MIZAN_CANONICAL_WINDOW_BARS` breaks it silently.
- That is precisely what `tests/test_mizan_window_equivalence.py` now prevents. It fails loudly if
  the window shortens, if the quantisation tightens, or if the smoothing changes.

## What I did not do, and why

I did not rewrite the builder to consume `canonical_mizan_window`. It is the structurally correct
change and it costs an O(n x 400) recomputation per instrument -- roughly 500 million inner steps
across a 500-name rebuild -- to move published values by less than 1e-10, which is to say not at
all. Spending a full store rebuild to produce the same numbers is not obviously right, and it is a
call for whoever owns the store rather than for me.

**The decision that is actually open** is whether a property this important may rest on a numerical
coincidence that a test protects, or must rest on the code structure. I have made it testable. I
have not made it structural.

## Correction to my own earlier summary

Earlier today I listed this to the founder as "P1 Critical -- no v3 model can execute until fixed",
carrying the subject notice's severity forward without measuring it. **That was wrong.** The v3
models can execute, and the values they score match the ones their coefficients were fitted to.
