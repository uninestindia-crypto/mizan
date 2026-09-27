# Short-Horizon Program: Repaired Evaluator Re-measurement Report

DATE_UTC: 2026-09-25T09:30:00Z  
AUTHOR: Antigravity  
GOVERNANCE: QuantOS PROTOCOL §8, frozen 9-trial multiplicity budget  
STATUS: IMMUTABLE RESEARCH EVIDENCE  
ARTIFACTS:
- `reports/short_horizon/repaired_results-ridge.json`
- `reports/short_horizon/repaired_results-timesfm.json`
- `reports/short_horizon/repaired_results-timesfm25.json`
- `reports/short_horizon/repaired_results-noise-control.json`

---

## Executive Summary

On 2026-09-14, commit `056fb1c6` repaired four mathematical and portfolio-accounting defects in `src/quant_system/research_short_horizon/evaluation.py`:
1. **Capital-constrained tranche ledger**: Overlapping positions previously compounded daily cohort returns sequentially, artificially running the portfolio at up to 3x capital. The repaired ledger allocates capital across distinct non-overlapping tranches.
2. **Past-only abstention calibration**: Threshold selection was previously pooled across all validation folds and evaluated on the same rows. Calibration is now strictly past-only, with Fold 0 holding cash.
3. **DSR sample length**: Sample size previously used total distinct decision dates (`~2,172`), underestimating sampling variance by a factor of `sqrt(held_sessions)`. It now uses the true number of independent portfolio periods.
4. **DSR annualisation**: Annualisation convention was reconciled to `periods_per_year = 252 / held_sessions`.

This report provides the **authoritative side-by-side re-measurement** of all nine frozen trials (Ridge, TimesFM 3.0, and TimesFM 2.5 across holds 1, 2, and 3) plus the 30-seed NOISE control through the repaired harness.

### Key Conclusions

1. **Gate Verdict: ALL CANDIDATES REMAIN `RESEARCH_ONLY`.**
   - The best deflated Sharpe ratio across all 9 trials is **0.183082** (TimesFM 2.5 at Hold 3), well below the `GatePolicyV1.min_deflated_sharpe = 0.95` threshold.
2. **Candidates Decisively Lose to Pure Noise at Active Horizons**:
   - At Hold 3, the median 30-seed NOISE control DSR is **0.6728** (worst draw: **0.5099**).
   - **All 30 noise seeds beat every candidate** (Ridge `0.0220`, TimesFM 3.0 `0.1772`, TimesFM 2.5 `0.1831`).
   - At Hold 2, NOISE median DSR is **0.0712**, which beats Ridge (`0.0145`), TimesFM 3.0 (`0.0017`), and TimesFM 2.5 (`0.0107`).
3. **Hold 1 "Edge" is Pure Cash-Tilt**:
   - The positive Sharpe/DSR at Hold 1 for TimesFM 2.5 (`0.1239`) and Ridge (`0.0325`) results from the past-only abstention policy declining `99.8%+` of trades (exposure `<= 0.002`), effectively holding cash while the general market (`ALWAYS_TRADE`) dropped `-1.4320`.
4. **Permissive (2.5) vs Non-Commercial (3.0)**:
   - TimesFM 2.5 (Apache-2.0) consistently outperformed TimesFM 3.0 across Sharpe and DSR, but neither demonstrates genuine market-selection skill over trivial baselines.

---

## Full Side-by-Side Comparison: Pre-Repair vs Repaired

*Note: Pre-repair figures are cited from `reports/short_horizon/TRIAL-LEDGER.md` (re-scored at 9 trials on 2026-09-14). Both evaluations enforce the frozen budget of `num_trials = 9`.*

### Table 1: Deflated Sharpe Ratio (DSR) vs 0.95 Gate

| # | Arm | Hold | Pre-Repair DSR (9) | **Repaired DSR (9)** | Delta | Verdict |
|---|---|---:|---:|---:|---:|---|
| 1 | Ridge | 1 | 0.015569 | **0.032517** | +0.016948 | `RESEARCH_ONLY` |
| 2 | Ridge | 2 | 0.037419 | **0.014507** | -0.022912 | `RESEARCH_ONLY` |
| 3 | Ridge | 3 | 0.062647 | **0.021964** | -0.040683 | `RESEARCH_ONLY` |
| 4 | TimesFM 3.0 | 1 | 0.013464 | **0.020693** | +0.007229 | `RESEARCH_ONLY` |
| 5 | TimesFM 3.0 | 2 | 0.002182 | **0.001668** | -0.000514 | `RESEARCH_ONLY` |
| 6 | TimesFM 3.0 | 3 | 0.137089 | **0.177228** | +0.040139 | `RESEARCH_ONLY` |
| 7 | TimesFM 2.5 | 1 | 0.118147 | **0.123855** | +0.005708 | `RESEARCH_ONLY` |
| 8 | TimesFM 2.5 | 2 | 0.071891 | **0.010728** | -0.061163 | `RESEARCH_ONLY` |
| 9 | TimesFM 2.5 | 3 | 0.312642 | **0.183082** | -0.129560 | `RESEARCH_ONLY` |

---

### Table 2: Raw Strategy Metrics (Sharpe, Trades, Exposure, Max Drawdown)

| Arm / Hold | Pre Sharpe | **Repaired Sharpe** | Pre Trades | **Repaired Trades** | Pre Expo | **Repaired Expo** | Repaired MaxDD |
|---|---:|---:|---:|---:|---:|---:|---:|
| **Ridge Hold 1** | -0.2162 | **-0.1383** | 379 | **22** | 0.006 | **0.000** | 0.004 |
| **Ridge Hold 2** | -0.0888 | **-0.2828** | 755 | **55** | 0.012 | **0.001** | 0.009 |
| **Ridge Hold 3** | -0.0041 | **-0.2110** | 35,150 | **17,961** | 0.565 | **0.289** | 0.176 |
| **TimesFM 3.0 Hold 1** | -0.2357 | **-0.2214** | 58 | **50** | 0.001 | **0.001** | 0.009 |
| **TimesFM 3.0 Hold 2** | -0.4533 | **-0.6043** | 289 | **6,965** | 0.005 | **0.112** | 0.184 |
| **TimesFM 3.0 Hold 3** | +0.1456 | **+0.2538** | 35,425 | **29,471** | 0.569 | **0.473** | 0.164 |
| **TimesFM 2.5 Hold 1** | +0.1146 | **+0.1556** | 380 | **124** | 0.006 | **0.002** | 0.011 |
| **TimesFM 2.5 Hold 2** | +0.0201 | **-0.3327** | 9,419 | **11,037** | 0.151 | **0.177** | 0.179 |
| **TimesFM 2.5 Hold 3** | +0.3518 | **+0.2633** | 29,791 | **22,257** | 0.479 | **0.358** | 0.120 |

---

### Table 3: Repaired NOISE Control Distribution (30 Seeds)

The NOISE control runs the exact same harness, folds, cost engine, and abstention grid using Gaussian pseudo-random forecasts.

| Hold | Noise DSR Min | **Noise DSR Median** | Noise DSR P90 | Noise DSR Max | Best Model DSR | Noise vs Best Model |
|---:|---:|---:|---:|---:|---:|---|
| **1** | 0.0000 | **0.0000** | 0.0001 | 0.0004 | 0.1239 (T2.5) | Model beats noise via cash tilt |
| **2** | 0.0204 | **0.0712** | 0.1382 | 0.2062 | 0.0145 (Ridge) | **Noise beats ALL models** |
| **3** | 0.5099 | **0.6728** | 0.7794 | 0.8298 | 0.1831 (T2.5) | **Noise (min 0.5099) crushes ALL models** |

---

### Table 4: Benchmark Comparators (Hold 3)

At Hold 3, where strategies actively participate in the market:

| Strategy | Sharpe | Mean / Decision | Trades | Exposure | Max Drawdown |
|---|---:|---:|---:|---:|---:|
| `ALWAYS_TRADE` (Benchmark) | **+0.5903** | +0.001102 | 62,247 | 1.000 | 0.366 |
| `PREVIOUS_SIGN` | **+0.5748** | +0.000524 | 32,224 | 0.518 | 0.141 |
| `NOISE` (Control, sample seed) | **+0.9789** | +0.000672 | 26,895 | 0.432 | 0.117 |
| **TimesFM 2.5** (Candidate) | **+0.2633** | +0.000157 | 22,257 | 0.358 | 0.120 |
| **TimesFM 3.0** (Candidate) | **+0.2538** | +0.000210 | 29,471 | 0.473 | 0.164 |
| **Ridge** (Candidate) | **-0.2110** | -0.000163 | 17,961 | 0.289 | 0.176 |

---

## Detailed Findings and Decomposition

### 1. Capital-Constrained Compounding at Hold 3
Under the pre-repair evaluator, daily overlapping 3-session decisions compounded sequentially as if the book had unlimited leverage. With the repaired tranche ledger:
- TimesFM 2.5 Hold 3 Sharpe fell from `+0.3518` to `+0.2633`, and DSR dropped from `0.3126` to `0.1831`.
- Max drawdown was reined in (from `~0.214` unconstrained to `0.120`).
- Exposure dropped from `47.9%` to `35.8%`.

### 2. The Hold 3 Benchmark Paradox
In a rising market across the 10-year development period, `ALWAYS_TRADE` achieves Sharpe `+0.5903`. Random noise selection achieves a median DSR of `0.6728` because taking random positions at `~43-50%` exposure acts as a diversified, cost-dampened participation in market beta. Candidates like TimesFM 2.5 (`Sharpe +0.2633`) trade selectively on noisy forecast signals, incurring statutory trading costs (0.224% round trip) without selecting names that beat the broad index.

### 3. The Hold 2 Reversal
At Hold 2, TimesFM 2.5 was previously reported with a marginally positive Sharpe (`+0.0201`, DSR `0.0719`). Under the repaired past-only abstention policy and tranche accounting, TimesFM 2.5 Hold 2 dropped to negative territory (`Sharpe -0.3327`, DSR `0.0107`), confirming that the pre-repair positive was an artifact of pooled look-ahead threshold fitting.

---

## Scientific Governance and Final Verdict

- **Multiplicity Accounting**: Fully preserved at `num_trials = 9`.
- **Holdout Partition**: The 252-session holdout tail was strictly quarantined and never touched.
- **Verdict**: All nine trials are certified `RESEARCH_ONLY`.
- **Recommendation**: Close the short-horizon single-name directional track. No foundation checkpoint or ridge variant shows evidence of edge surviving Indian statutory execution costs at 1-3 session holding periods.
