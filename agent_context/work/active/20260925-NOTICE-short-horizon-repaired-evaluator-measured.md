# NOTICE: short-horizon trials re-measured on repaired evaluator

STATUS: NOTICE (additive; no other record is edited)  
OWNER: Antigravity, filer  
FILED_UTC: 2026-09-25T09:35:00Z  
FOR: `20260910-1615Z-claude-mizan-correction-and-short-horizon-program.md` (STATUS `ACTIVE`), which owns
  `reports/short_horizon/` and `src/quant_system/research_short_horizon/**`  
AUTHORIZATION: Founder direction via `/grill-me` design alignment, 2026-09-25. Resolves the outstanding
  recommendation in `agent_context/work/active/20260914-NOTICE-short-horizon-evaluator-repaired-invalidates-ledger-numbers.md`  
FILED UNDER: PROTOCOL §8.4 — reporting exact re-measurements of evidence previously invalidated by an
  evaluator repair, written to parallel artifacts without mutating historical claims.

## What was executed

All nine pre-declared trials (Ridge, TimesFM 3.0, and TimesFM 2.5 at holds 1, 2, and 3) plus the 30-seed
NOISE control were executed via `scripts/run_short_horizon_experiment.py` through the repaired evaluator
(`056fb1c6`).

Outputs were written to parallel artifacts:
- `reports/short_horizon/repaired_results-ridge.json`
- `reports/short_horizon/repaired_results-timesfm.json`
- `reports/short_horizon/repaired_results-timesfm25.json`
- `reports/short_horizon/repaired_results-noise-control.json`
- Comprehensive report: `reports/short_horizon/REPAIRED-EVALUATOR-COMPARISON.md`

## Headline Re-measured Figures (num_trials = 9)

| # | Arm | Hold | Pre-Repair DSR (9) | **Repaired DSR (9)** | Pre Sharpe | **Repaired Sharpe** | Repaired Trades | Repaired Expo |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| 1 | Ridge | 1 | 0.015569 | **0.032517** | -0.2162 | **-0.1383** | 22 | 0.000 |
| 2 | Ridge | 2 | 0.037419 | **0.014507** | -0.0888 | **-0.2828** | 55 | 0.001 |
| 3 | Ridge | 3 | 0.062647 | **0.021964** | -0.0041 | **-0.2110** | 17,961 | 0.289 |
| 4 | TimesFM 3.0 | 1 | 0.013464 | **0.020693** | -0.2357 | **-0.2214** | 50 | 0.001 |
| 5 | TimesFM 3.0 | 2 | 0.002182 | **0.001668** | -0.4533 | **-0.6043** | 6,965 | 0.112 |
| 6 | TimesFM 3.0 | 3 | 0.137089 | **0.177228** | +0.1456 | **+0.2538** | 29,471 | 0.473 |
| 7 | TimesFM 2.5 | 1 | 0.118147 | **0.123855** | +0.1146 | **+0.1556** | 124 | 0.002 |
| 8 | TimesFM 2.5 | 2 | 0.071891 | **0.010728** | +0.0201 | **-0.3327** | 11,037 | 0.177 |
| 9 | TimesFM 2.5 | 3 | 0.312642 | **0.183082** | +0.3518 | **+0.2633** | 22,257 | 0.358 |

### 30-Seed NOISE Control Re-measurement

- **Hold 1**: DSR min 0.0000 / **median 0.0000** / max 0.0004
- **Hold 2**: DSR min 0.0204 / **median 0.0712** / max 0.2062
- **Hold 3**: DSR min 0.5099 / **median 0.6728** / max 0.8298

## Key Adjudication Findings

1. **Gate Verdict**: All 9 trials remain **`RESEARCH_ONLY`**. The best candidate DSR is `0.183082`
   (TimesFM 2.5 at Hold 3) vs gate `0.95`.
2. **Noise Dominance**: At Hold 3, all 30 noise seeds beat every candidate. Even the minimum noise draw
   (`0.5099`) substantially exceeds the best candidate (`0.1831`).
3. **Hold 2 Reversal**: TimesFM 2.5 at Hold 2 flipped from positive Sharpe (`+0.0201`) to negative
   (`-0.3327`), confirming that past look-ahead in pooled threshold calibration created a false positive.
4. **Holdout Quarantined**: The 252-session holdout was preserved untouched. No trial ordinal was added.
