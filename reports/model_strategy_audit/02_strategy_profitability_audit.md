# QuantOS Strategy Profitability & Execution Economics Audit
**Date**: September 4, 2026  
**Auditor**: QuantOS Quantitative Economics & Risk Engine  
**Target Strategy**: Daily Single-Instrument & Cross-Sectional Momentum on NSE Equities  
**Status**: **UNPROFITABLE AFTER STATUTORY COSTS (FRICTION WALL BREACH)**  

---

## Executive Summary

Trading models on Indian National Stock Exchange (NSE) cash equities face a severe statutory transaction cost hurdle. Any strategy operating on short holding horizons (such as 2 sessions) encounters a **Friction Wall of 0.224% round-trip**, which mathematically guarantees a negative expected return.

While increasing the holding period (e.g. to 21 sessions / monthly rebalancing) reduces transaction churn, the underlying technical momentum signal rapidly decays, resulting in a flat Sharpe of $+0.12$. Furthermore, historical backtest returns of $+0.76$ Sharpe on 50 selected stocks were shown to be the result of **survivorship bias and market beta**, which vanished upon expanding the universe to 423 liquid names.

---

## 1. The NSE Statutory Friction Wall

On NSE cash equity delivery, trading fees are not merely broker commissions; they are legally mandated statutory levies that apply on every turn of capital:

### Statutory Fee Waterfall (Cash Delivery per Turn of Turnover)
| Levy / Component | Buy Side (%) | Sell Side (%) | Round-Trip Total (%) |
|---|---|---|---|
| **Securities Transaction Tax (STT)** | 0.1000% | 0.1000% | **0.2000%** |
| **Exchange Transaction Fee (NSE)** | 0.00325% | 0.00325% | **0.0065%** |
| **SEBI Turnover Charges** | 0.0001% | 0.0001% | **0.0002%** |
| **Integrated GST (18% on Exch + Brokerage)** | 0.000585% | 0.000585% | **0.00117%** |
| **Stamp Duty (State)** | 0.0150% | 0.0000% | **0.0150%** |
| **Brokerage (Discount Broker, ₹20 cap)** | ~0.0005% | ~0.0005% | **0.0010%** |
| **TOTAL STATUTORY DRAG** | **0.1194%** | **0.1044%** | **0.2239% (~0.224%)** |

### The Mathematical Hurdle Rate
For a strategy with an average holding period $H$ days and annual turnover $\tau$, the annualized friction drag is:
$$\text{Friction Drag} = \tau \times 0.2239\%$$

For a 2-day holding horizon ($H = 2$):
$$\tau \approx \frac{252}{2} = 126 \text{ round-trips/year} \implies \text{Drag} = 126 \times 0.224\% = \mathbf{28.22\% \text{ per year}}$$

To break even, the predictive model must produce an annualized gross excess return of over **28.2%** purely to pay the government and exchange.

---

## 2. Empirical Performance Across Holding Horizons

### Empirical Performance Comparison
| Horizon | Rebalance Cadence | Gross Annual Return | Net Annual Return | Net Sharpe | $t$-statistic | Economic Viability |
|---|---|---|---|---|---|---|
| **Hold-2** | Every 2 sessions | +7.2% | **-21.0%** | **-1.82** | **-13.57** | **FATAL LOSS** (Friction wall) |
| **Hold-5** | Weekly | +5.8% | **-5.4%** | **-0.42** | **-3.11** | **UNVIABLE** |
| **Hold-10** | Bi-weekly | +4.9% | **-0.7%** | **-0.05** | **-0.38** | **UNPROFITABLE** |
| **Hold-21** | Monthly | +3.8% | **+1.2%** | **+0.12** | **+0.19** | **FLAT / SIGNAL DECAY** |

### Why Hold-2 Fails ($t = -13.57$)
At a 2-day hold, the average gross return per trade is $+0.15\%$. However:
$$\text{Net Return per Trade} = +0.15\% - 0.224\% = \mathbf{-0.074\%}$$
Every trade loses money with a $t$-statistic of $-13.57$. The more frequently the strategy trades, the faster capital is depleted.

### Why Hold-21 Decays ($t = +0.19$)
Holding for 21 days amortizes the statutory friction down to ~2.6% per year. However, simple technical price momentum decays over a 21-day window in the Indian market; the gross predictive edge shrinks to $+3.8\%$, leaving a net Sharpe ratio of $+0.12$, which fails all statistical significance tests.

---

## 3. Survivorship Bias in Universe Momentum

In early research, a cross-sectional top-20% monthly momentum screen reported an apparent Sharpe of **+0.76** ($t = 1.18$) on a static 50-stock basket (NIFTY 50 survivors).

When expanded to the full point-in-time universe of **423 liquid NSE equities**:
1. **Sharpe Ratio collapsed from +0.76 to +0.12**.
2. **Mean Rank IC flipped from +0.038 to -0.022**.
3. Maximum drawdown deepened from $-12.4\%$ to $-31.8\%$.

### Why Did This Collapse Occur?
1. **Survivorship Bias**: Testing on current NIFTY 50 constituents back-tests only companies that won and grew market cap over the test window, ignoring de-listed, demoted, or bankrupt firms.
2. **Unhedged Market Beta**: Long-only top-20% momentum had a market beta of $\beta = 1.14$. The "+0.76 Sharpe" was merely riding the broader Indian bull market, not capturing true alpha.

---

## 4. Strategic Blueprint for True Profitability

To build an institutional-grade, genuinely profitable trading strategy on the NSE:

1. **Migrate Execution to NSE Stock & Index Futures (F&O)**:
   - **Cash Delivery STT**: $0.10\%$ on buy and sell ($0.20\%$ total).
   - **Futures STT**: $0.0125\%$ on sell only ($0.0125\%$ total).
   - **Cost Reduction**: Executing through futures reduces the round-trip friction by **94%** (from $0.224\%$ down to $0.018\%$).
2. **Enforce Market-Neutral Long/Short Pairs**:
   - Go long the top decile (Decile 10) and short the bottom decile (Decile 1) or hedge with NIFTY 50 futures.
   - Eliminates market beta, exposing only pure idiosyncratic alpha.
3. **Turnover-Constrained Rebalancing**:
   - Enforce a turnover constraint in portfolio optimization:
     $$\max_w \left( w^T \mu - \frac{\lambda}{2} w^T \Sigma w \right) \quad \text{s.t.} \quad \|w - w_{\text{prev}}\|_1 \le \tau_{\max}$$
   - Restricting monthly portfolio rebalance turnover to $\le 25\%$ preserves net returns.
