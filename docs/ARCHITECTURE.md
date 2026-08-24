# QuantOS Technical Architecture

This document details the software architecture, data pipelines, domain models, execution lifecycles, and risk enforcement mechanisms powering **QuantOS**.

---

## 🏛️ High-Level System Architecture

```
                                 ┌─────────────────────────┐
                                 │   Upstox / Synthetic   │
                                 │   Market Data Feeds     │
                                 └────────────┬────────────┘
                                              │ Bars, Ticks, Chains
                                              ▼
                                 ┌─────────────────────────┐
                                 │   Data Engine & Vault   │
                                 │ • Multi-TF Aggregator   │
                                 │ • Holdout Partitioner   │
                                 └────────────┬────────────┘
                                              │ Clean BarSeries
                                              ▼
    ┌─────────────────────────────────────────────────────────────────────────────────┐
    │                            Alpha & Signal Generation                            │
    │  ┌───────────────────────┐ ┌───────────────────────┐ ┌───────────────────────┐  │
    │  │ Technical & Greeks    │ │ Fundamental Factors   │ │ Sentiment & AI Agents │  │
    │  │ • RSI, EMA, ATR, BB   │ │ • PLANNED, NOT BUILT  │ │ • Claude / Codex LLM │  │
    │  │ • BS Greeks, IV Solver│ │ • no P/E, ROE, EV/EBIT│ │ • arXiv RAG Retrieval │  │
    │  │ • Volatility Surface  │ │ • no earnings data    │ │ • FinBERT: planned    │  │
    │  └───────────┬───────────┘ └───────────┬───────────┘ └───────────┬───────────┘  │
    └──────────────┼─────────────────────────┼─────────────────────────┼──────────────┘
                   │                         │                         │
                   └─────────────────────────┼─────────────────────────┘
                                             ▼
                               ┌───────────────────────────┐
                               │     Strategy Engine       │
                               │ • Dual Momentum           │
                               │ • ML Ridge Classifiers    │
                               │ • Options Straddles       │
                               │ • Directional Spreads     │
                               └─────────────┬─────────────┘
                                             │ Signal (BUY/SELL/HOLD)
                                             ▼
                               ┌───────────────────────────┐
                               │   Portfolio Construction  │
                               │ • Volatility Parity Sizer │
                               │ • Half-Kelly Criterion    │
                               │ • Risk Parity / Markowitz │
                               └─────────────┬─────────────┘
                                             │ Order Proposals (Target Qty)
                                             ▼
                               ┌───────────────────────────┐
                               │  Pre-Trade Risk Governor  │
                               │ • Max Capital / Position  │
                               │ • Leverage & Margin Guard │
                               │ • Max Drawdown Breaker    │
                               │ • Spread & Liquidity Test │
                               └─────────────┬─────────────┘
                                             │ Approved Orders
                                             ▼
                               ┌───────────────────────────┐
                               │  Execution & Backtester   │
                               │ • Order State Machine     │
                               │ • Zero-Lookahead Fills    │
                               │ • Indian Cost Model       │
                               │   (STT, GST, Stamp, Slip) │
                               └─────────────┬─────────────┘
                                             │ Executed Fills
                                             ▼
                               ┌───────────────────────────┐
                               │   Exact Decimal Ledger    │
                               │ • Cash & Equity Balance   │
                               │ • Realized / Unrealized   │
                               │ • Position State Machine  │
                               └─────────────┬─────────────┘
                                             │ Equity Curves & Trades
                                             ▼
                               ┌───────────────────────────┐
                               │    Analytics & Engine     │
                               │ • Sharpe / Sortino / VaR  │
                               │ • Deflated Sharpe (DSR)   │
                               │ • Monte Carlo Simulation  │
                               │ • HTML Tearsheet Reports  │
                               └───────────────────────────┘
```

---

## 1. Domain Models & Core Ledger (`quant_system.core`)

### Exact Decimal Precision
All monetary operations (prices, cash balances, transaction fees, tax liabilities, margins) strictly use Python's built-in `Decimal` with standardized rounding modes (`ROUND_HALF_UP` / `ROUND_HALF_EVEN`). No raw floating-point arithmetic is permitted in ledger calculations.

### Core Domain Primitives
* `Instrument`: Encapsulates ticker, asset class (`EQUITY`, `OPTION`, `FUTURE`), tick size, lot size, currency, and derivative properties (strike, expiration, call/put).
* `Order`: Represents trade intent (`MARKET`, `LIMIT`, `STOP`) with strict lifecycle states: `PENDING` $\rightarrow$ `SUBMITTED` $\rightarrow$ `FILLED` / `REJECTED` / `CANCELLED`.
* `Fill`: Immutable execution record containing fill price, executed quantity, timestamp, execution fees, and tax breakdown.
* `Position`: Tracks real-time inventory, weighted average entry price, total volume traded, and unrealized mark-to-market P&L.
* `DecimalLedger`: Double-entry accounting system maintaining cash, margin locks, realized gains, and portfolio equity over time.

---

## 2. Market Data Architecture (`quant_system.data`)

* **Multi-Timeframe Aggregator (`BarAggregator`)**: Resamples tick data or 1-minute bars into 5-minute, 15-minute, hourly, or daily OHLCV bars without forward leakage.
* **Option Chain Engine (`OptionChain`)**: Normalizes call and put chains across strikes and expiries, calculating strike-by-strike moneyness, implied volatilities, and Greeks.
* **Holdout Vault (`HoldoutVault`)**: Enforces strict chronological data splitting (e.g. 70% In-Sample training, 30% Out-of-Sample validation) to protect against p-hacking and overfitting.
* **Brokers & Feeds (`UpstoxClient`, `SyntheticDataGenerator`)**: Native OAuth2 connectivity to Upstox API for Indian markets (NSE/BSE) alongside deterministic geometric Brownian motion / jump-diffusion synthetic generators.

---

## 3. Alpha & Feature Engineering (`quant_system.alpha`)

* **Technical Indicators (`technical.py`)**: Vectorized SMA, EMA, RSI, ATR, Bollinger Bands, and rate-of-change momentum.
* **Derivatives Mathematics (`greeks.py`, `surface.py`)**:
  * Analytical Black-Scholes-Merton option pricing and complete Greeks ($\Delta, \Gamma, \Theta, \mathcal{V}, \rho$).
  * High-speed Brent/Newton-Raphson Implied Volatility root-finder.
  * 2D Implied Volatility surface interpolator over moneyness and time-to-expiration.
* **AI Multi-Agent Advisory Consensus (`ai_advisor.py`)**:
  * Multi-agent consensus engine synthesizing independent opinions from Claude, Codex, and Antigravity agents.
  * Soft vetoes, confidence multipliers, and qualitative sentiment assessments based on macro regimes.

---

## 4. Pre-Trade Risk Governor (`quant_system.risk`)

Every trade proposal is intercepted by the `PreTradeRiskGovernor` before reaching the broker or backtest engine.

```python
# The Pre-Trade Risk Pipeline
proposal = PositionProposal(symbol="RELIANCE", target_qty=500, price=Decimal("2950.00"))
approval = risk_governor.evaluate(proposal, current_portfolio_state)

if not approval.is_approved:
    logger.warning(f"Trade rejected: {approval.rejection_reason}")
```

### Risk Checks:
1. **Max Position Sizing**: Disallows single positions exceeding a percentage of total portfolio equity.
2. **Gross Portfolio Leverage**: Blocks orders that would push portfolio leverage above safety thresholds (e.g. $1.5\times$).
3. **Daily Loss Circuit Breaker**: Freezes all trading if daily drawdown crosses configured risk thresholds (e.g. $-3\%$).
4. **Bid-Ask Spread Protection**: Rejects market orders on illiquid instruments where spread exceeds permissible bounds.
5. **Emergency Kill-Switch**: Immediate operational state toggle that liquidates open positions and halts trade execution.

---

## 5. Event-Driven Backtest Engine (`quant_system.backtest`)

### Execution Invariants:
* **Zero-Lookahead Fill Timing**: Strategies inspect prices up to bar $t$ (market close). Fills are executed at the Open price of bar $t+1$.
* **Realistic Friction Model (`IndianMarketCostModel`)**:
  * STT (Securities Transaction Tax: 0.1% delivery, 0.025% intraday, 0.0625% options sell)
  * Exchange Turnover Fees (NSE transaction charges)
  * SEBI Turnover Charges & Stamp Duty
  * GST (18% on brokerage and transaction charges)
  * Dynamic Volume-Weighted Slippage

---

## 6. Portfolio Optimization & Multiplicity Analytics (`quant_system.portfolio`, `analytics`)

* **Position Sizing**:
  * Fixed Fractional (% of equity)
  * Volatility Parity (Inverse ATR/volatility sizing)
  * Half-Kelly Criterion (Optimal geometric growth with drawdown dampening)
* **Portfolio Optimization**:
  * Markowitz Mean-Variance (Maximum Sharpe ratio frontier)
  * Hierarchical Risk Parity / Equal Risk Contribution (ERC)
* **Statistical Multiplicity Testing**:
  * **Deflated Sharpe Ratio (DSR)**: Adjusts the observed Sharpe ratio for multiple hypothesis testing, sample length, skewness, and kurtosis (Bailey & Lopez de Prado).
  * **Monte Carlo Block Bootstrap**: Resamples return distributions to calculate probabilistic maximum drawdowns and VaR at 95% and 99% confidence levels.

---

## 7. Desktop API & Interactive Interface (`quant_system.server`, `launcher.py`)

* **FastAPI Server**: Lightweight asynchronous REST API exposing backtest triggers, options calculators, risk controls, and system diagnostics.
* **Hardware & Storage Sandbox**:
  * `launcher.py` guarantees 100% drive-isolated storage (all logs, caches, and artifacts are confined to the installation drive with zero $C:\backslash$ disk leaks).
  * Native 64-bit hardware validation and self-healing diagnostic tests.
* **Modern Web Dashboard**: Real-time interactive UI for visualizing equity curves, drawdown waterfalls, Greeks heatmaps, and running one-click backtests.
