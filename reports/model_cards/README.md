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
| [noise-control](noise-control.md) | Random predictions on the identical pipeline — a calibration device, not a strategy | **NOT A CANDIDATE — and it outscored both real models at hold 3** |

## The one-line result

**Nothing here is promotable, and nothing here is close.** The best deflated Sharpe across every
model on this page is `0.3944` (TimesFM 2.5, hold 3) against a gate of `0.95` — and that figure was
scored against 6 declared trials when the budget is now 9; re-deflated at 9 it is `0.3126`. Random
predictions scored `0.4197` on the same folds, so **the best real model on this page is still beaten
by noise** at the hold where it actually trades.

*Updated 2026-09-13. This previously read "the best deflated Sharpe is 0.2466 (Mizan flagship)" and
"the best short-horizon number produced by a real model is 0.1914". Trials 7-9 superseded both. The
conclusion did not change.*

## Standing prohibitions that apply to every card

- **No live-money routing.** Nothing in this repository has ever placed an order, by design.
- **No promotion.** Every model carries `verdict = RESEARCH_ONLY`, which is the machinery's own
  label, not a certification.
- **Do not re-run a campaign to improve a number.** Each additional trial spends a multiplicity
  ordinal and deflates every future candidate harder.
