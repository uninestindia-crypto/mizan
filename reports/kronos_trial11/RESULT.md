# Short-horizon trial 11 (Kronos-base, five paths, hold 3): result

**Verdict: `RESEARCH_ONLY`.** The candidate ended slightly above zero after real costs, but its deflated Sharpe is 0.077
against the 0.95 the declared gate requires, so it fails the gate by a factor of twelve. Nothing is promotable. The
declaration's prior, written before any forecast existed, was "expect it to fail", and it did.

Declaration: `reports/kronos_trial11/TRIAL-LEDGER.md` (frozen before any forecast, commit `7a33c62c`). Scored once, on
2026-10-10, through `scripts/score_kronos_trial11.py`, which runs `scripts/run_kronos_trial.py` unmodified with the
multiplicity count set to 11. Raw numbers: `results-kronos-trial11.json`. Forecasts: `kronos-forecasts.json`, SHA-256
`49e4fdca09669f644364c228daa23b63a01150dd66ab041e47a880e52be54dfe`, which the results file also records. The forecasts
were produced on 2026-10-06 on a Kaggle GPU in 5.3 hours (run 355816896, private notebook), and this is the first and
only complete trial-11 run. No other run exists, so no choice between outputs was made.

## What was scored

| | |
|---|---|
| Model | `NeoQuasar/Kronos-base` (102.3M) with `Kronos-Tokenizer-base`, zero-shot, **five averaged paths**, T 1.0, top-p 0.9, top-k 0 |
| Names / dates | 45 names, 529 decision dates, 2024-07-01 to 2026-08-17 |
| Decisions scored | 23,637. The other 168 of the 23,805 forecasts have no label under the governed label path (the ledger's declared cause: decisions near an unsized corporate action), not itemised here. 0 scored decisions lacked a forecast |
| Rule | Long when the forecast open-to-open return exceeds 0.224% (the round trip cost); otherwise cash. Hold 3 sessions |
| Costs | Dated NSE statutory costs on raw executable opens, imported unchanged from the short-horizon harness |
| Multiplicity | DSR deflated against **11** trials (the console line prints "10 trials" because that label is hard-coded in the scorer; the computation and the results file use 11, and recomputing with 10 gives 0.0845, with 11 gives 0.0773, matching the file) |

## Result, next to trial 10

| Strategy | Sharpe | Net return, total | Hit rate | Trades | Exposure | Max drawdown |
|---|---:|---:|---:|---:|---:|---:|
| **CANDIDATE (Kronos-base, 5 paths)** | **+0.138** | **+1.23%** | 47.9% | 6,977 | 29.5% | 6.6% |
| *Trial 10 candidate (Kronos-small, 1 path)* | *-0.444* | *-6.65%* | *47.2%* | *11,725* | *49.6%* | *12.9%* |
| CANDIDATE_ANY_POSITIVE (diagnostic) | +0.085 | +0.67% | 47.6% | 7,442 | 31.5% | 6.8% |
| **CASH** | **0.000** | 0.00% | - | 0 | 0% | 0% |
| ALWAYS_TRADE | -0.956 | -22.35% | 46.6% | 23,637 | 100% | 29.1% |
| PREVIOUS_SIGN | -1.160 | -14.64% | 45.5% | 11,838 | 50.1% | 17.9% |
| NOISE-K, 30 seeds (same rule) | best -0.606, median -0.954 | | | | | |

The controls are identical to trial 10's, as they should be: same names, dates, labels and costs.

| Gate and checks (declared) | Trial 11 | Trial 10 | Requirement | |
|---|---:|---:|---:|---|
| Candidate deflated Sharpe | **0.0773** (11 trials) | 0.0134 (10 trials) | 0.95 or more | **fail** |
| Max drawdown | 0.066 | 0.129 | 0.15 or less | pass |
| Trades | 6,977 | 11,725 | 5 or more | pass |
| Candidate Sharpe beats every NOISE-K seed | +0.138 vs best -0.606 | -0.444 vs -0.606 | yes | pass |
| Candidate Sharpe beats ALWAYS_TRADE | +0.138 vs -0.956 | -0.444 vs -0.956 | yes | pass |

PASS needed all of them. The gate failed, so the verdict is `RESEARCH_ONLY`. Because the verdict is not a pass, there is
no `PASS_PENDING_INDEPENDENT_CHECK` and nothing is promoted.

## How to read it

- **This is the first Kronos configuration above cash, and it is not evidence of an edge.** The Sharpe is +0.138 on 176
  non-overlapping three-session periods, about 2.1 years at 84 periods a year. Treating those periods as independent
  (my arithmetic, not a declared diagnostic), that is a t-statistic of about 0.2. The total is +1.23% net over the
  whole window.
- **The ranking diagnostics did not improve; they got slightly worse.** Declared diagnostics, never verdict-bearing:
  - Cross-sectional rank IC between forecast and realised net return: mean +0.0140 over 177 non-overlapping dates,
    **t = 0.89** (trial 10: +0.0159, t = 1.32). Not significant.
  - Top-quintile selection edge over the equal-weight mean: -0.000008 per decision, **t = -0.01** (trial 10: +0.000236,
    t = 0.45). Indistinguishable from zero.
  - So the larger model with averaged paths ranked names no better than the small one with a single path. Whatever
    lifted the result from -0.444 to +0.138 was not better stock selection.
- **A likely reason, not tested here:** exposure fell from 49.6% to 29.5% and trades from 11,725 to 6,977. Averaging five
  sampled paths pulls each predicted return toward zero, so fewer forecasts clear the 0.224% hurdle, and a strategy that
  trades less pays less cost. That would improve the net result without any forecasting skill. This file does not
  establish it; it is consistent with the numbers and with the zero ranking edge.
- **"Beats the controls" still means "loses less than controls that lose".** The two controls it beats (noise and
  always-trade) are both deeply negative. The one comparison that matters, against cash, is +0.138 against 0.000 with
  a t-statistic near 0.2.
- **This tests one configuration.** Nothing here speaks for other model sizes, path counts, holds or thresholds. The
  declaration forbids trying them after a result.

## Disclosed limits, all stated before the result in the ledger

- **Platform.** Forecasts came from a Kaggle notebook: Linux x86_64, Python 3.13.15, torch 2.11.0+cu128, numpy 2.1.3,
  pandas 2.3.3, **Tesla T4 GPU**. Trial 10 ran on a CPU. Code, weights and the inputs file are hash-verified identical
  (the run's own log and the forecast file record the matching SHA-256 values), but a GPU changes floating-point
  results and so the seeded draws. This is not bit-identical to trial 10 or to a laptop run, by declaration.
- **A second look at the same data.** The window, names and labels are exactly trial 10's, and trial 10's result was
  already known. This is the same 529 dates seen through a different model, not an independent sample.
- **The holdout is spent.** The window includes the final 252 sessions the short-horizon program reserved as its
  unseen holdout. Anyone who reads this result has seen them.
- **Contamination bound is the authors' statement.** Every scored target is dated after Kronos's stated pre-training
  cutoff (June 2024). If the real cutoff were later, contamination could only have flattered this result, and it
  still failed.
- **Survivorship and liquidity selection** in the 45-name subset favour the candidate, and are inherited from earlier
  trials. A near-zero result under a favourable bias is not a positive one.
- **Multiplicity.** This is ordinal 11 of the family. Trials 1-10 were published against fewer attempts and would each
  read lower against 11. None of them passed, so none passes at 11.
- **Not independently reproduced.** No agent other than the one that ran it has re-scored this file. Nobody has been
  asked to, because nothing here would be promoted if it reproduced.

## What follows

Nothing, by declaration: no other size, path count, hold or threshold, and no fine-tuning. Any further attempt is
ordinal 12 with its own dated declaration. No order exists on any path here, and neither laptop paper book was touched.
