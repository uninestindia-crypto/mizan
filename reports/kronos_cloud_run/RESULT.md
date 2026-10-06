# Short-horizon trial 10 (Kronos zero-shot, hold 3): result

**Verdict: `RESEARCH_ONLY`.** The candidate loses money after real costs and fails the pre-declared gate by a wide
margin. Nothing is promotable. This was the expected outcome: the declaration's prior, written before any forecast
existed, was "expect it to fail".

Declaration: `reports/kronos_trial/TRIAL-LEDGER.md`. Compute scope: `AMENDMENT-1.md` (Kronos-small, one sample path,
fixed by the declared timing rule before any forecast). Scored once, on 2026-10-06, by `scripts/run_kronos_trial.py`
unmodified. Raw numbers: `results-kronos.json`. Forecasts: `kronos-forecasts.json`, SHA-256
`59170064241c2bf0d087530a635a617e106758e73d0f7c111c086f06b41a0a9c`, which the results file also records.

## What was scored

| | |
|---|---|
| Model | `NeoQuasar/Kronos-small` with `Kronos-Tokenizer-base`, zero-shot, one sampled path, T 1.0, top-p 0.9 |
| Names / dates | 45 names, 529 decision dates, 2024-07-01 to 2026-08-17 |
| Decisions scored | 23,637. The other 168 of the 23,805 forecasts have no label under the governed label path; the ledger's declared cause is decisions near an unsized corporate action, and they were not itemised here. 0 scored decisions lacked a forecast |
| Rule | Long when the forecast open-to-open return exceeds 0.224% (the round trip cost); otherwise cash. Hold 3 sessions |
| Costs | Dated NSE statutory costs on raw executable opens, imported unchanged from the short-horizon harness |
| Multiplicity | DSR deflated against 10 trials |

## Result

| Strategy | Sharpe | Net return, total | Hit rate | Trades | Exposure | Max drawdown |
|---|---:|---:|---:|---:|---:|---:|
| **CANDIDATE (Kronos-small)** | **-0.444** | **-6.65%** | 47.2% | 11,725 | 49.6% | 12.9% |
| CANDIDATE_ANY_POSITIVE (diagnostic) | -0.487 | -7.51% | 47.2% | 12,459 | 52.7% | 13.7% |
| **CASH** | **0.000** | 0.00% | - | 0 | 0% | 0% |
| ALWAYS_TRADE | -0.956 | -22.35% | 46.6% | 23,637 | 100% | 29.1% |
| PREVIOUS_SIGN | -1.160 | -14.64% | 45.5% | 11,838 | 50.1% | 17.9% |
| NOISE-K, 30 seeds (same rule) | best -0.606, median -0.954 | | | | | |

| Gate and checks (declared) | Value | Requirement | |
|---|---:|---:|---|
| Candidate deflated Sharpe (10 trials) | **0.0134** | 0.95 or more | **fail** |
| Max drawdown | 0.129 | 0.15 or less | pass |
| Trades | 11,725 | 5 or more | pass |
| Candidate Sharpe beats every NOISE-K seed | -0.444 vs best -0.606 | yes | pass |
| Candidate Sharpe beats ALWAYS_TRADE | -0.444 vs -0.956 | yes | pass |

PASS needed all of them. The gate failed, so the verdict is `RESEARCH_ONLY`.

## How to read it

- **Two of the checks passed, and that does not mean there is an edge.** The candidate is less negative than the
  noise control and than always trading, but every one of those loses money after costs, and the candidate loses
  to doing nothing (CASH, Sharpe 0). "Beats the controls" here means "loses less than controls that also lose".
- **Declared diagnostics, never verdict-bearing:**
  - Cross-sectional rank IC between forecast and realised net return: mean +0.0159 over 177 non-overlapping dates,
    **t = 1.32**, not significant.
  - Top-quintile selection edge over the equal-weight mean: +0.000236 per decision over 177 non-overlapping dates,
    **t = 0.45**, indistinguishable from zero.
  - Both point slightly above zero without being distinguishable from it. That is weak information in the
    forecast that does not survive a 0.224% round trip.
- **This tests one configuration.** The declared rule picked the smallest configuration because the larger ones
  did not fit the compute budget. So this is Kronos-small with a single sampled path. It says nothing about
  Kronos-base or averaged paths, and the declaration forbids trying them after a result.

## Disclosed limits, all stated before the result in `AMENDMENT-1.md` or the ledger

- **Platform.** This run is Linux x86_64 with 4 vCPU, not the declaration's native-ARM64 Windows machine. Code,
  weights and library versions are identical and hash-verified, but a different CPU can change floating-point
  results and the seeded draws, so it is not guaranteed bit-identical to a laptop run. It is the same trial, scored
  once.
- **The holdout is spent.** The window includes the final 252 sessions the short-horizon program reserved as its
  unseen holdout. Anyone who reads this result has seen them.
- **Contamination bound is the authors' statement.** Every scored target is dated after Kronos's stated
  pre-training cutoff (June 2024). If the real cutoff were later, contamination could only have flattered this
  result, and it still failed.
- **Survivorship and liquidity selection** in the 45-name subset favour the candidate, and are inherited from
  trials 1-9. A negative under a favourable bias is a stronger negative.
- **Multiplicity.** This is ordinal 10 of the family. Trials 1-9 were published at 9 and would each read lower
  against 10. None of them passed at 9, so none passes at 10.

## What follows

Nothing, by declaration: no second model size, no other hold, no threshold search, no fine-tuning. Any further
attempt is ordinal 11 with its own dated declaration. No order exists on any path here, and neither laptop paper
book was touched.
