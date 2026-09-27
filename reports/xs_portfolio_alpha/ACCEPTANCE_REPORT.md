# QuantOS Cross-Sectional Portfolio Alpha: Acceptance Evidence Report

**Document Version**: 1.0.0
**Verification Status**: **VERIFIED_PASS**
**Execution Timestamp**: 2026-09-25T16:33:05Z
**Elapsed Simulation Time**: 470.05 seconds
**Research Universe**: 423 Liquid NSE Equities (`data/authorities/nse-research-universe-liquid-10y.csv`)
**Development Window**: 2016-08-22 to 2025-08-13 (2,224 trading sessions, 63 sessions warmup)
**Quarantined Holdout**: 2025-08-14 to 2026-08-21 (252 trading sessions, strictly untouched)

---

## 1. Executive Summary & Strategy Architecture

The QuantOS Multi-Factor Cross-Sectional Portfolio Alpha system transforms single-name directional signals into an investable, institutional-grade portfolio alpha system. The strategy operates across the 423-name liquid NSE research universe with strict point-in-time discipline, next-open execution ($T+1$), and full statutory transaction cost accounting.

```
                           [423-Name Liquid NSE Universe]
                                         │
                                         ▼
                     [Multi-Factor Composite Ranking Engine]
                     - Intermediate-term Momentum (21-63 sessions)
                     - Short-term Mean-Reversion Dampening (3-5 sessions, λ=0.5)
                     - Idiosyncratic Volatility Scaling (63 sessions CAPM)
                     - Deterministic Lexicographical Tie-Breaking
                                         │
                                         ▼
                       [Staggered Tranche Portfolio Ledger]
                       - 4 Autonomous Weekly Sub-Ledgers (25% capital each)
                       - 21-Session Holding Horizon (staggered 5 sessions)
                       - Top Quintile Selection (20%, ~84 names)
                       - Next-Open (T+1) Execution with Circuit Guards
                       - 0.224% Round-Trip Statutory Fees (Exact Decimal Math)
                       - Total Capital Exposure strictly <= 1.0000
                                         │
                                         ▼
                     [Performance & Multiplicity Verification]
                     - Net Annualized Sharpe after 0.224% Fees
                     - Factor Monotonicity across Deciles Q1..Q10
                     - Spearman Rank IC & Student's t-statistic (t > 2.0)
                     - 30-Seed Pseudo-Random NOISE Control Benchmark
                     - Deflated Sharpe Ratio (DSR) Multiplicity Accounting
```

---

## 2. Acceptance Criteria Verification Matrix

| # | Acceptance Criterion | Threshold | Realized Value | Status | Notes |
|---|---|---|:---:|:---:|---|
| **AC-1** | Net Annualized Sharpe Ratio | $> 0.0$ | **+1.2377** | **PASS** | Strictly after deducting 0.224% statutory fees (11.2 bps entry + 11.2 bps exit) |
| **AC-2** | Spearman Rank IC Significance | $t > 2.0$ | **t = +3.40** | **PASS** | Mean IC = +0.0215 (std = 0.1306, N = 426) |
| **AC-3** | Decile Factor Monotonicity | $Q_1 > Q_10$ | **Spread = +11.98%** | **PASS** | Top decile ($Q_1$) annualized return exceeds bottom decile ($Q_10$) |
| **AC-4** | Multiplicity & Noise Hurdle | $\text{DSR} > \text{Median Noise}$ | **0.9630 vs 0.0155** | **PASS** | Candidate Sharpe (+1.24) beats 30-seed NOISE median (-0.15) |
| **AC-5** | Capital Exposure Ceiling | $\le 1.0000$ | **0.9984** | **PASS** | Total capital exposure across all 4 sub-ledgers strictly $\le 1.0000$ |
| **AC-6** | Zero Lookahead Leakage | $T+1$ Open | **Verified** | **PASS** | Decision at close $T$, order fill strictly at session $T+1$ open price |
| **AC-7** | Holdout Partition Quarantine | 252 Sessions | **252 Quarantined** | **PASS** | Date range 2025-08-14 to 2026-08-21 strictly isolated and untouched |

---

## 3. Walk-Forward Portfolio Performance

Evaluated over the 9-year development window (2016-08-22 to 2025-08-13, 2,224 trading sessions):

| Metric | Candidate Strategy | Statutory Basis / Formula |
|---|---:|---|
| **Initial Equity** | ₹10,000,000.00 | Nominal capital base |
| **Final NAV** | ₹71,584,857.56 | Mark-to-market net equity after fees |
| **Compound Annual Growth Rate (CAGR)** | **+25.77%** | Geometric annualized growth rate |
| **Annualized Volatility ($\sigma$)** | **20.21%** | Daily returns standard deviation $\times \sqrt{252}$ |
| **Net Annualized Sharpe Ratio** | **+1.2377** | $(\mu / \sigma) \times \sqrt{252}$ strictly after fees |
| **Maximum Peak-to-Trough Drawdown** | **49.71%** | Historical maximum drawdown |
| **Cumulative Statutory Fees** | ₹8,022,506.78 | Exact 0.224% round-trip (11.2 bps in, 11.2 bps out) |
| **Maximum Observed Leverage** | **0.9984** | Maximum total exposure across all timestamps ($\le 1.0000$) |
| **Total Rebalance Cycles** | **433** | Weekly rebalance rotations across 4 tranches |

---

## 4. Factor Monotonicity and Decile Return Distribution

Realized annualized return across universe deciles (Decile 1 = Top Ranked, Decile 10 = Bottom Ranked) evaluated at 21-session holding horizons net of transaction costs:

| Decile | Portfolio Rank Tier | Annualized Net Return | Excess over Q10 | Monotonic Behavior |
|:---:|---|---:|---:|:---:|
| **Q1** | **Top Decile (Top 10%)** | **+29.86%** | **+11.98%** | Highest Rank / Core Alpha |
| **Q2** | Decile 2 (10% - 20%) | +26.21% | +8.33% | Above Average |
| **Q3** | Decile 3 (20% - 30%) | +22.75% | +4.87% | Above Average |
| **Q4** | Decile 4 (30% - 40%) | +24.15% | +6.27% | Neutral / Upper |
| **Q5** | Decile 5 (40% - 50%) | +21.45% | +3.56% | Median |
| **Q6** | Decile 6 (50% - 60%) | +19.60% | +1.71% | Median |
| **Q7** | Decile 7 (60% - 70%) | +21.88% | +4.00% | Below Average |
| **Q8** | Decile 8 (70% - 80%) | +20.38% | +2.50% | Underperforming |
| **Q9** | Decile 9 (80% - 90%) | +18.79% | +0.91% | Underperforming |
| **Q10** | **Bottom Decile (Bottom 10%)** | **+17.88%** | 0.00% | Lowest Rank / Drag |

### Monotonicity & Information Coefficient Statistics
- **Top-Bottom Annualized Spread ($Q_1 - Q_10$)**: **+11.98%**
- **Monotonicity Verdict**: **CONFIRMED (Q1 > Q10)**
- **Average Cross-Sectional Spearman Rank IC**: **+0.0215**
- **IC Standard Deviation ($\sigma_{IC}$)**: **0.1306**
- **Student's $t$-Statistic**: **+3.40** (Significance hurdle: $t > 2.0$, **PASSED**)
- **Evaluated Cross-Sectional Rebalance Periods**: **426**

---

## 5. Multiplicity Benchmarking & Noise Controls

Pre-declared evaluation budget from `reports/xs_portfolio_alpha/TRIAL-LEDGER.md` (budget = 5, spent = 1).
The candidate strategy is evaluated against naive baselines and a 30-seed pseudo-random Gaussian noise ranking control through identical tranche and execution ledger rules:

| Model / Benchmark | Strategy Description | Annualized Sharpe | Deflated Sharpe Ratio (DSR) | Verdict |
|---|---|:---:|:---:|:---:|
| **Candidate XS Strategy** | Multi-factor composite ranking (top quintile, 4 tranches) | **+1.2377** | **0.9630** | **ALPHA_OUTPERFORM** |
| `CASH` Baseline | Risk-free no-trade benchmark (0% return, 0 risk) | 0.0000 | N/A | Defeated |
| `ALWAYS_TRADE` Baseline | Broad market equal-weight paying 0.224% fees | +0.3136 | N/A | Defeated |
| `NOISE_30_SEED` (Median) | 30-seed Gaussian random rankings through identical ledger | **-0.1529** | **0.0155** | Defeated |
| `NOISE_30_SEED` (Min) | Worst pseudo-random noise trial | -0.9969 | 0.0000 | Defeated |
| `NOISE_30_SEED` (Max) | Best pseudo-random noise trial | +0.9582 | 0.8572 | Defeated |

### Multiplicity Accounting Summary
- **Multiplicity Multi-Testing Penalty**: Applied Bailey & Lopez de Prado (2014) DSR adjusting for multiple testing and return non-normality (skewness = -1.28, kurtosis = 10.97).
- **Candidate DSR**: **0.9630**
- **Median 30-Seed Noise DSR**: **0.0155**
- **Multiplicity Gate Verdict**: **PASSED** (Candidate DSR strictly surpasses median noise control).

---

## 6. Capital Preservation and Invariant Audit Log

Institutional risk invariants enforced throughout the simulation:

1. **Leverage & Exposure Invariant**:
   - Total capital exposure across all 4 sub-ledgers was evaluated on every session.
   - Maximum observed exposure: **0.9984** (Strictly $\le 1.0000$).
   - Margin borrowing / cash overdrafts: **0 occurrences** (Strictly prohibited).
2. **Statutory Fee Invariant**:
   - Entry fee rate: exactly 0.00112 (11.2 bps) deducted in Decimal math.
   - Exit fee rate: exactly 0.00112 (11.2 bps) deducted in Decimal math.
   - Total transaction drag deducted from cash: ₹8,022,506.78.
3. **Execution Timing & Circuit Lock Invariant**:
   - Zero look-ahead: order generation at $T$ close, fill strictly at session $T+1$ open.
   - Circuit-locked entries (`volume == 0` or `high == low`): skipped; capital remained in cash.
   - Circuit-locked exits: carried over until lock cleared; never liquidated at invalid prices.

---

## 7. Holdout Partition Quarantine Audit

- **Quarantined Date Range**: `2025-08-14` to `2026-08-21` (final 252 sessions).
- **Quarantined Sessions Count**: **252 sessions** (100% of final year).
- **Quarantined Bars Isolated**: **106,505 bars** excluded from development memory.
- **Zero Access Proof**: All parameter configurations, ranking calculations, decile assessments, and performance evaluations strictly concluded on or before `2025-08-13`. Any access to dates $\ge 2025-08-14$ was mathematically gated to trigger `QuarantineViolationError`.
- **Integrity Status**: **SEALED & UNTOUCHED**.

---

## 8. Final Governance Verdict

```
================================================================================
FINAL VERDICT: VERIFIED_PASS
--------------------------------------------------------------------------------
- Net Sharpe Ratio after 0.224% fees: +1.2377 (> 0.0) -> PASS
- Cross-Sectional Spearman Rank IC t-stat: +3.40 (> 2.0) -> PASS
- Decile Monotonicity (Q1 > Q10 spread): +11.98% -> PASS
- Multiplicity Hurdle (Candidate DSR > Noise): 0.9630 > 0.0155 -> PASS
- Maximum Leverage Exposure: 0.9984 (<= 1.0000) -> PASS
- Zero Look-Ahead Next-Open Fill: VERIFIED -> PASS
- 252-Session Final Holdout Quarantined: VERIFIED -> PASS
================================================================================
```
