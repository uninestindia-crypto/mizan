# Model cards

One card per model or rule that this repository has trained, frozen, or paper-traded. Each card
states what the thing is, what data it saw, how it was evaluated, what it scored, and an explicit
verdict **including its failures**.

| Card | What it is | Verdict |
|---|---|---|
| [mizan-flagship-h11](mizan-flagship-h11.md) | Governed pooled cross-sectional ridge, 15 features, 11-session horizon | **RESEARCH_ONLY — fails the gate; beaten by buy-and-hold and by repeat-the-previous-sign** |
| [xs-monthly-frozen](xs-monthly-frozen.md) | Frozen 21-session momentum rule, top 20%, monthly rebalance | **RESEARCH_ONLY — paper book open, below cash, one position unpriceable** |
| [short-horizon-ridge](short-horizon-ridge.md) | New QuantOS return-prediction ridge at 1/2/3-session holds | **RESEARCH_ONLY — fails the gate at every hold; beaten by the noise control** |
| [short-horizon-timesfm](short-horizon-timesfm.md) | `google/timesfm-3.0-pytorch` zero-shot at 1/2/3-session holds | **RESEARCH_ONLY — fails the gate at every hold; beaten by the noise control** |
| [short-horizon-timesfm25](short-horizon-timesfm25.md) | `google/timesfm-2.5-200m-pytorch` (**Apache-2.0**) zero-shot at 1/2/3-session holds | **RESEARCH_ONLY — better than 3.0 at every hold; still fails the gate and still beaten by the noise control where it trades** |
| [noise-control](noise-control.md) | Random predictions on the identical pipeline — a calibration device, not a strategy | **NOT A CANDIDATE — and it outscored all three real models at hold 3** |

## The one-line result

**Nothing here is promotable, and nothing here is close.** The best deflated Sharpe across every
model on this page is `0.3126` (TimesFM 2.5, hold 3) against a gate of `0.95`. Random predictions
scored `0.3360` on the same folds and the same budget, so **the best real model on this page is
still beaten by noise** at the hold where it actually trades.

*Updated 2026-09-14. Every short-horizon figure on these cards is now deflated against the frozen
ledger's **nine** SPENT trials; they were previously quoted at six, which is why this line read
`0.3944` and `0.4197` before. Raw metrics did not change and the re-deflation is rank-preserving, so
no conclusion moved. Earlier still, this read "the best deflated Sharpe is 0.2466 (Mizan flagship)"
and "the best short-horizon number produced by a real model is 0.1914"; trials 7-9 superseded both.*

**One correction on these cards is still outstanding.** The short-horizon evaluator was repaired at
`056fb1c6` and the raw metrics behind every short-horizon card predate that repair. Correcting them
means re-running the nine trials. Until that happens, read each short-horizon DSR as *an honest
deflation of a metric that is itself known to be wrong in four specific ways* —
`reports/short_horizon/TRIAL-LEDGER.md`, "Re-scoring, 2026-09-14".

## Standing prohibitions that apply to every card

- **No live-money routing.** Nothing in this repository has ever placed an order, by design.
- **No promotion.** Every model carries `verdict = RESEARCH_ONLY`, which is the machinery's own
  label, not a certification.
- **Do not re-run a campaign to improve a number.** Each additional trial spends a multiplicity
  ordinal and deflates every future candidate harder. Re-scoring existing evidence against a corrected
  budget is not a re-run and spends nothing: `scripts/rescore_short_horizon_multiplicity.py`.
