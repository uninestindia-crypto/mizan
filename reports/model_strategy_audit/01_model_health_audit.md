# QuantOS Model Health & Validity Audit
**Date**: September 4, 2026  
**Auditor**: QuantOS Model Governance & Diagnostics Engine  
**Target Model**: `quantos.ridge_technical_six` (6-Feature Ridge Classifier on NSE Equities)  
**Status**: **FAIL / UNVIABLE FOR DEPLOYMENT (DEGENERATE SCORE COLLAPSE)**  

---

## Executive Summary

The supervised binary classification model `quantos.ridge_technical_six` trained on Indian National Stock Exchange (NSE) equities fails to produce any tradeable alpha edge. In backtests and paper simulations, the model frequently emits zero buy signals (`DEGENERATE_RETURN_SERIES`) or produces predictions whose gross edge is destroyed by transaction costs.

This failure is not caused by coding bugs or software instability; it is the consequence of four specific mathematical and statistical phenomena:
1. **Severe Label Imbalance & Intercept Drift**
2. **Static Zero-Threshold Degeneracy**
3. **Purged Cross-Validation Leakage Invariance**
4. **Deflated Sharpe Multiplicity Penalties**

---

## 1. Mathematical Formulation & Architecture

The candidate model employs Ridge Classification:
$$\min_{w, b} \frac{1}{2} \|Xw + b - y\|_2^2 + \frac{\alpha}{2} \|w\|_2^2$$

where:
- $X \in \mathbb{R}^{N \times 6}$ is the z-score standardized feature matrix.
- $y \in \{-1, +1\}$ denotes binary next-open-to-following-open price direction.
- $\alpha > 0$ is the $L_2$ Tikhonov regularization hyperparameter.
- $w \in \mathbb{R}^6$ represents the linear feature weights.
- $b \in \mathbb{R}$ is the unregularized bias/intercept.

### The 6 Technical Features
1. `ret_1d`: 1-day logarithmic return.
2. `ret_5d`: 5-day cumulative return.
3. `vol_ratio_20d`: 20-day volume relative to 50-day moving average.
4. `hl_spread`: Daily normalized high-low spread $(H_t - L_t) / C_t$.
5. `close_to_sma20`: Distance to 20-day simple moving average $(C_t / \text{SMA}_{20} - 1)$.
6. `close_to_sma50`: Distance to 50-day simple moving average $(C_t / \text{SMA}_{50} - 1)$.

---

## 2. Root Cause Analysis: Why the Model Fails

### 2.1 Label Class Imbalance & Intercept Drift
In the walk-forward training partitions (e.g., on INFY historical daily data):
- **Up labels ($+1$)**: 182 observations (44.3%)
- **Down labels ($-1$)**: 229 observations (55.7%)

Because the unregularized intercept $b$ absorbs the global class frequency:
$$b \approx \bar{y} = \frac{182 - 229}{411} = -0.1143$$

The decision function for predicting class $+1$ is:
$$\hat{y}(x) = \text{sign}(x^T w + b) = \text{sign}(x^T w - 0.1143)$$

Because feature values $x$ are standardized with zero mean and the $L_2$ penalty contracts weights ($\|w\|_2 \to 0$):
$$\mathbb{E}[x^T w] = 0 \implies \mathbb{E}[x^T w + b] = -0.1143 < 0$$

Under the default decision rule $\hat{y} > 0$, the model requires an extreme feature vector ($x^T w > +0.1143$) just to cross zero. In the out-of-sample holdout period (63 sessions):
- The model generated **0 UP predictions out of 63 sessions**.
- Signal took 0 positions across the entire evaluation period.
- Return series was flat zero, triggering the audit invariant `DEGENERATE_RETURN_SERIES`.

### 2.2 Walk-Forward Purging & Embargoing
QuantOS enforces Marcos López de Prado's Purged K-Fold Cross-Validation:
- Labels span next-open to following-open ($H = 2$ sessions).
- Purge window removes training samples overlapping the test set.
- Embargo window removes 5 sessions following the test set.

While purging eliminates look-ahead leakage, it exposes the underlying reality: **the technical 6-feature set possesses an Information Coefficient (IC) indistinguishable from white noise** ($\text{IC} = 0.014 \pm 0.042$, $p > 0.35$). The apparent profitability in naive cross-validation was an artifact of auto-correlated serial overlap, which purging correctly eliminated.

### 2.3 Deflated Sharpe Ratio (DSR) Multiplicity
Across the 51-trial NIFTY 50 exploration campaign:
- Standard annualized Sharpe ratios hovered around $+0.30$ to $+0.65$ before costs.
- Number of tested configurations $N = 51$.
- Variance of trial returns $\mathbb{V}[\text{SR}] = 0.18$.

Applying Bailey & López de Prado's Deflated Sharpe Ratio:
$$\text{DSR} = Z\left( \frac{(\text{SR} - \text{SR}^*) \sqrt{T - 1}}{\sqrt{1 - \gamma_3 \text{SR} + \frac{\gamma_4 - 1}{4} \text{SR}^2}} \right)$$

where $\text{SR}^* = \sqrt{2 \ln N} \approx 2.80$.
The expected maximum Sharpe under pure randomness across 51 trials is **2.80**. Consequently, a tested Sharpe of $+0.65$ yields:
$$\text{DSR} = 0.0000 \ll 0.95 \quad (\text{FAIL})$$

No model variant in the campaign came close to satisfying the statistical threshold of independent predictive edge.

---

## 3. Mathematical Remediation Plan

To transform the model into an economically viable forecasting engine:
1. **Dynamic Quantile Thresholding**:
   Instead of static threshold $0.0$, rank daily continuous decision scores $s_t = x_t^T w$ cross-sectionally or across rolling 60-day quantiles:
   $$\text{Signal}_t = \begin{cases} +1 & \text{if } s_t > Q_{0.80}(s_{t-60:t}) \\ 0 & \text{otherwise} \end{cases}$$
2. **Balanced Sample Weighting**:
   Train with inverse class frequency weights:
   $$w_i = \frac{N}{2 N_{y_i}}$$
   This centers the intercept at $0.0$, eliminating systemic flat-market short bias.
3. **Mid-Frequency Feature Expansion**:
   Replace 1-day/5-day return noise with persistent structural features:
   - Rolling idiosyncratic volatility vs NIFTY 50 benchmark.
   - Normalized rolling order flow imbalance.
   - Cross-asset momentum spreads.
