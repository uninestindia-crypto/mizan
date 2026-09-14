# Short-horizon comparison: a simple ridge against TimesFM 3.0, at holds of 1, 2 and 3 sessions

**Verdict: neither model has an edge. All nine declared trials are `RESEARCH_ONLY`. At every single
hold, a trivial rule — hold everything, or hold nothing — beats both models.**

*Re-scored 2026-09-14. Every deflated Sharpe below is now deflated against the frozen ledger's **nine**
SPENT trials; they were previously quoted at six. Raw metrics are unchanged and re-deflation is
rank-preserving, so no comparison in this report moved — only levels. Full before/after table and the
two corrections still outstanding: [`TRIAL-LEDGER.md`](TRIAL-LEDGER.md), "Re-scoring, 2026-09-14".*

The most important finding is not about either model. It is that **the deflated Sharpe ratio, as this
study computes it, does not measure skill for a long-only strategy in a trending market.** Thirty
random-forecast controls establish that directly. Read the noise section before reading any number
above it.

## Reproduce

```bash
.venv/Scripts/python.exe scripts/run_short_horizon_experiment.py --arm ridge --out reports/short_horizon/results-ridge.json
```

```bash
powershell -ExecutionPolicy Bypass -File scripts/supervise_timesfm_forecasts.ps1
```

```bash
.venv/Scripts/python.exe scripts/run_short_horizon_experiment.py --arm timesfm --out reports/short_horizon/results-timesfm.json
```

```bash
.venv/Scripts/python.exe scripts/run_short_horizon_experiment.py --arm noise --noise-seeds 30 --out reports/short_horizon/results-noise-control.json
```

Re-scoring the stored results against the ledger's current trial count, which runs **no trial and
spends no ordinal**:

```bash
.venv/Scripts/python.exe scripts/rescore_short_horizon_multiplicity.py --check
```

Budget and every amendment: [`TRIAL-LEDGER.md`](TRIAL-LEDGER.md). Raw results:
`results-ridge.json`, `results-timesfm.json`, `results-timesfm25.json`, `results-noise-control.json`.
Each stores its originals under `*_as_published` keys.

## The comparison

Identical 45-name subset, identical decisions, identical folds, identical dated NSE costs. **Zero
missing forecasts** in the TimesFM arm, so both models were scored on exactly the same decision set.

### Sharpe

| Hold | Ridge | TimesFM | Noise (median of 30) | Buy-and-hold | Cash |
|---:|---:|---:|---:|---:|---:|
| 1 | −0.2162 | −0.2357 | −1.3001 | −1.4340 | **0.0000** |
| 2 | −0.0888 | −0.4533 | +0.1063 | −0.0018 | **0.0000** |
| 3 | −0.0041 | +0.1456 | +0.4863 | **+0.4922** | 0.0000 |

### Deflated Sharpe against the gate

| Hold | Ridge | TimesFM | Noise median | Gate | Best verdict |
|---:|---:|---:|---:|---:|---|
| 1 | 0.0156 | 0.0135 | 0.0000 | 0.95 | `RESEARCH_ONLY` |
| 2 | 0.0374 | 0.0022 | 0.1134 | 0.95 | `RESEARCH_ONLY` |
| 3 | 0.0626 | **0.1371** | 0.4626 | 0.95 | `RESEARCH_ONLY` |

The best number in this two-arm comparison is TimesFM 3.0's **0.1371** at hold 3, against a
requirement of 0.95. It is not a near miss, and it is under a third of what the median coin flip
scored on the same data. (A third arm, TimesFM 2.5, was declared and run afterwards as trials 7-9 and
scored higher than both — `0.312642` at hold 3, still below the noise median. See the ledger.)

### The one-line summary

**At every hold, either cash or buy-and-hold beats both models:**

| Hold | Market direction | What beat both models |
|---:|---|---|
| 1 | falling hard (B&H −1.43) | **cash**, at exactly 0.0000 |
| 2 | flat (B&H −0.00) | **cash**, at exactly 0.0000 |
| 3 | rising (B&H +0.49) | **buy-and-hold**, at +0.4922 |

A model with timing skill beats cash when the market falls *and* beats the market when it rises.
Neither model does either. They lose money in the falling market and lag the rising one.

## The noise control, and why it reframes everything

30 seeds, identical configuration, pseudo-random forecasts.

| Hold | Ridge DSR | TimesFM DSR | Noise min | Noise **median** | Noise max |
|---:|---:|---:|---:|---:|---:|
| 1 | 0.0156 | 0.0135 | 0.0000 | 0.0000 | 0.0000 |
| 2 | 0.0374 | 0.0022 | 0.0363 | **0.1134** | 0.1778 |
| 3 | 0.0626 | 0.1371 | 0.2454 | **0.4626** | 0.6263 |

**At hold 3, all thirty random draws beat both models.** The worst coin flip scored 0.2454; the ridge
scored 0.0626 and TimesFM 0.1371. The median coin flip scored **0.4626** — higher than this
repository's best-ever recorded result of `0.397794`, which was itself scored against a different
search and is not directly comparable.

*The count of noise seeds beating each model is identical before and after re-scoring: the
transformation is rank-preserving. What changed is the level of every row, not the ordering.*

### The mechanism, measured

| Hold | Buy-and-hold Sharpe | Noise median Sharpe | Noise exposure |
|---:|---:|---:|---:|
| 1 | −1.4340 | −1.3001 | 0.169 |
| 2 | −0.0018 | +0.1063 | 0.459 |
| 3 | **+0.4922** | **+0.4863** | 0.500 |

The noise median tracks buy-and-hold at every hold. That is the whole explanation: **random long-only
selection at ~50% exposure is a diluted buy-and-hold.** Halving exposure scales mean and volatility
together, so the Sharpe survives almost intact.

The deflated Sharpe tests the candidate against **zero**. In a rising market every long-only rule
beats zero, including one that knows nothing. So a DSR computed this way rewards market exposure and
calls it skill.

### What this does and does not change

- **It does not weaken the gate.** `GatePolicyV1.min_deflated_sharpe = 0.95` is untouched. Nothing
  passed it. No threshold was adjusted to obtain any result here.
- **It makes a low DSR worse, not better.** The ridge at hold 3 did not merely fail the gate; it
  underperformed thirty of thirty coin flips. Its abstention rule pulled it *out* of a market that
  rose, which is worse than having no opinion.
- **It raises a checkable question about prior work, stated as a question.** The repository's
  historical best of `0.397794` sits below the noise median measured here (and that comparison is
  looser than it looks, since the two figures are deflated against different searches). That does **not**
  establish the earlier figure was drift rather than skill — it came from per-instrument campaigns
  with different exposure characteristics, and re-deriving it is outside this study's scope. It is a
  specific hypothesis someone should test rather than leave implied.

## Model-by-model

### The simple ridge

| Hold | Abstention | Exposure | Trades | Mean/decision | Total return | Max DD | Hit rate |
|---:|---:|---:|---:|---:|---:|---:|---:|
| 1 | 0.005 | 0.6% | 379 | −0.000049 | −7.34% | 0.158 | 0.475 |
| 2 | 0.008 | 1.2% | 755 | −0.000052 | −9.68% | 0.320 | 0.473 |
| 3 | 0 | 56.5% | 35,150 | −0.000006 | −18.12% | 0.747 | 0.493 |

Every mean-per-decision is negative: **cash beats the ridge at all three holds**. Hit rates sit just
below 50% at every hold, which is what no information looks like.

The abstention rule is doing something real but not useful. At holds 1 and 2 it calibrated to a
threshold that trades almost nothing (0.6%, 1.2% exposure) — correctly concluding that almost no
forecast is worth 22 basis points of round trip. At hold 3 it calibrated to **zero**, meaning it
found nothing worth abstaining on, and then lost 18% by participating.

### TimesFM 3.0 zero-shot

| Hold | Abstention | Exposure | Trades | Mean/decision | Total return | Max DD | Hit rate |
|---:|---:|---:|---:|---:|---:|---:|---:|
| 1 | 0.020 | 0.1% | 58 | −0.000007 | −0.94% | 0.020 | 0.466 |
| 2 | 0.020 | 0.5% | 289 | −0.000044 | −5.94% | 0.074 | 0.450 |
| 3 | 0 | 56.9% | 35,425 | +0.000199 | +17.93% | 0.566 | 0.499 |

Checkpoint `google/timesfm-3.0-pytorch` at revision
**`43046b85ec22d584a13f8098c2ed39c889e129c2`**, zero-shot, no fine-tuning, no covariates.

TimesFM is **worse than the ridge at holds 1 and 2** and better at hold 3. Its only positive result —
hold 3, +17.93% total return — comes with the abstention threshold at zero and 56.9% exposure, and
still lags buy-and-hold's +0.4922 Sharpe by a wide margin. Its hit rates (0.466, 0.450, 0.499) are
all at or below a coin flip.

**Without abstention TimesFM is much worse**: −1.6158 Sharpe at hold 1 against the ridge's −0.6425.
Its raw directional calls are actively harmful at the shortest horizon; the abstention rule is what
rescues the headline number, by declining to act on 99.9% of them.

## What these numbers can and cannot support

**Can:**

- Neither model class shows tradeable short-horizon edge on this universe after real NSE costs.
- The abstention rule works as designed — it correctly refuses to trade when nothing clears the
  cost — and correctly refusing to trade is not the same as making money.
- TimesFM's zero-shot forecasts carry no usable NSE short-horizon signal at these holds. A 330M
  parameter foundation model does not beat a ridge here, and both lose to a coin flip in a rising
  market.

**Cannot:**

- **The holdout is untouched.** 252 sessions were reserved before any fold was built and never read.
  No candidate was frozen because none came close to the gate, so evaluating it would spend the
  holdout for nothing. It remains available.
- **Survivorship and liquidity bias.** The universe is active listings only, and the 45-name subset
  is turnover-ranked over the whole window rather than point-in-time. Both biases favour a positive
  result, and both failed to produce one — which makes the negative stronger, not weaker.
- **The close-to-close approximation.** TimesFM predicts a close-to-close path while being scored on
  an open-to-open net return. That mismatch is real and was accepted deliberately: the alternative
  is handing the model the entry open, which is a price from after the decision. It penalises
  TimesFM to an unmeasured degree and is disclosed with every TimesFM number here.
- **Pretraining overlap.** NSE daily history is public and the TimesFM model card establishes no
  exhaustive cutoff, so contamination cannot be ruled out. Declared before the run: a negative result
  stays informative under contamination; a positive one would not have. The result is negative.

## Method, in brief

| Element | What was done |
|---|---|
| Subset | 45 names — research universe ∩ universe-bound governed acquisition, turnover-ranked. **Both arms identical** |
| Labels | Governed `build_label_dataset` on derived adjusted acquisitions: return on adjusted prices, costs on raw executable opens at dated NSE rules |
| Corporate actions | Windows spanning an action nobody could size produce **no label** |
| Holds | 1, 2, 3 sessions — mapping to `horizon_sessions` 2, 3, 4 **proven** against the real label builder, not asserted |
| Validation | 11 chronological folds, purged and embargoed by the horizon. ~1,000–2,000 rows purged and the same embargoed per trial |
| Preprocessing | Standardisation fitted on **training rows only**, per fold |
| Abstention | One grid (C1), declared once and applied identically to every published trial, calibrated on validation folds only, long-only. It was declared for the original six and was reused unchanged by trials 7-9 rather than re-calibrated |
| Holdout | 252 sessions, sliced off before any fold, never read |
| Gate | Existing `GatePolicyV1`, unchanged |

### Verification

- **Determinism**: two independent ridge runs produced bit-identical results across all three holds —
  same folds, purge/embargo counts, thresholds and metrics for all five strategies.
- **Leak control**: the harness has a test that plants the target as a feature and asserts it reports
  Sharpe > 3. A harness that cannot detect a *known* leak cannot be trusted on an unknown one.
- **Forecast coverage**: 0 missing forecasts across all three TimesFM holds, predicted in advance and
  confirmed by instrumentation added for the purpose.
- 134 tests passing; ruff and mypy clean; both repository audits PASS.

## Defects found and fixed while building this

Recorded because each produced plausible, wrong output rather than an error.

1. **Subset selector dropped the largest names.** Selecting the longest acquisition then filtering for
   universe authority cut the subset to 19 names, losing RELIANCE, HDFCBANK, ICICIBANK and SBIN.
2. **A stale run overwrote a good result.** Caught only because the payload records its own subset.
3. **Every hold was about to read the 1-step forecast**, silently testing a model nobody proposed.
4. **Missing forecasts scored as zero**, making an uninformed arm look selective. Now counted and
   reported.
5. **The generator wrote only at the end**, losing 27 minutes to a restart. Now checkpointed and
   resumable.
6. **The supervisor died on its first attempt** — PowerShell 5.1 turns a native command's stderr into
   terminating errors, and the HuggingFace warning killed it before any work happened.
