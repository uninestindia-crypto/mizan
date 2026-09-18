# QuantOS Platform Overview

## 🎯 What is QuantOS?

**QuantOS** is an institutional-grade, modular **Quantitative Trading, Research, and Risk Management System**. It is designed to bridge the gap between academic quantitative finance, systematic alpha generation, and production-grade execution with strict risk governance.

Built for **NSE India** cash equities and NIFTY **derivatives (options/futures)**, QuantOS provides an end-to-end framework: from raw market data ingestion and feature engineering to zero-lookahead backtesting, portfolio optimization, and desktop analytics.

> ### ⚠️ What this document is
>
> **This is a design document. Parts of the architecture below are intended rather than built.**
> Sections that describe unbuilt capability are marked **NOT IMPLEMENTED** inline, and the diagrams
> show the designed shape rather than the shipped one.
>
> `README.md` is the authority on what actually exists, and it says plainly:
>
> * **No live-money order routing**, by design — `broker_orders_submitted` is enforced as zero on the shadow surface.
> * **No US equities.** The instrument contract accepts NSE cash equities only.
> * **No fundamental scoring.** There is no balance-sheet, earnings, or valuation factor model.
> * **No profitable model.** 101 governed trials and seven pre-declared screens found no edge that survives real costs; best deflated Sharpe 0.398 against a 0.95 gate.
>
> This banner exists because this file previously advertised US equities and a fundamental factor
> engine, directly contradicting `README.md` in the same repository. That was program Major #4, which
> was corrected in `README.md` and `docs/ARCHITECTURE.md` at `5a0447b` and missed here.

---

## 🏛️ Core Design Invariants

QuantOS is engineered around four uncompromising institutional principles:

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                            QuantOS Core Invariants                          │
├─────────────────────────┬──────────────────────────┬────────────────────────┤
│  Exact Decimal Precision │  Strict Pre-Trade Risk   │ Zero Lookahead Engine  │
│  No floating-point      │  Every trade validated   │ Fills at Next Open;   │
│  penny leaks / rounding │  by RiskGovernor before  │ strict bar-close       │
│  errors in accounting   │  reaching the broker     │ signal calculation     │
└─────────────────────────┴──────────────────────────┴────────────────────────┘
```

1. **Exact Decimal Accounting**:
   Financial ledger calculations (cash balance, margin buffers, realized/unrealized P&L, commissions, slippage, and statutory taxes like STT, GST, Stamp Duty) are calculated using Python's `Decimal` fixed-point arithmetic to guarantee zero floating-point accumulation drift.

2. **Strict Pre-Trade Risk Governance**:
   No strategy or algorithm can place orders directly to the market. Every order proposal must pass through the `PreTradeRiskGovernor`, which enforces max position sizing, leverage limits, portfolio concentration bounds, bid-ask spread checks, and hard circuit breaker kill-switches.

3. **Deterministic Zero-Lookahead Backtesting**:
   Signals generated at bar $t$ (using data up to bar $t$ close) are strictly filled on bar $t+1$ open. Same-bar fills and retroactive data snooping are physically impossible within the execution state machine.

4. **Multi-Source Alpha (Technical + Fundamental + Sentiment)** — *partly implemented*:
   Alpha generation is designed not to be confined to price indicators. **Built today:** statistical technical indicators, Black-Scholes Greeks and IV surfaces, macro regime feeds (NIFTY, India VIX), and AI/LLM multi-agent advisory consensus. **NOT IMPLEMENTED:** fundamental balance-sheet factors — no such module exists.

---

## 🧩 The Triad of Quantitative Alpha

QuantOS integrates all three primary pillars of modern systematic finance:

```mermaid
graph TD
    subgraph Market_Data [Data Feeds]
        P[Price & Tick Feeds (OHLCV, Level 2)]
        F[Fundamental Feeds (10-K, Balance Sheets, Ratios)]
        N[News & Sentiment Feeds (Headlines, Filings, Transcripts)]
    end

    subgraph Alpha_Engine [QuantOS Feature & Alpha Layer]
        P --> TA[Technical & Volatility Alpha<br/>• Moving Averages, RSI, ATR<br/>• Black-Scholes Greeks & IV Surface]
        F --> FA[Fundamental & Factor Alpha<br/>• Value: P/E, P/B, EV/EBITDA<br/>• Quality: ROE, Debt/Equity, F-Score<br/>• Growth: YoY Revenue, Margins]
        N --> SA[Sentiment & NLP Alpha<br/>• News Headline Sentiment<br/>• LLM Multi-Agent Advisors<br/>• arXiv Research RAG Engine]
    end

    subgraph Fusion [Multi-Factor Signal Engine]
        TA --> S[QuantOS Strategy Engine<br/>• Rolling Ridge Classifiers<br/>• Dual Momentum<br/>• Intraday Volatility Straddles<br/>• AI-Enhanced Multi-Agent Fusion]
        FA --> S
        SA --> S
    end

    subgraph Execution [Portfolio & Risk Gate]
        S --> PO[Portfolio Sizer & Allocator<br/>• Volatility Parity & Kelly Sizing<br/>• Markowitz / Risk-Parity Optimizer]
        PO --> RG[Pre-Trade Risk Governor]
        RG --> PB[Paper & Live Execution Engine]
    end
```

### 1. Technical & Quantitative Volatility Alpha
* Moving average crossovers, Exponential Smoothers, Relative Strength Index (RSI), Average True Range (ATR), and Bollinger Bands.
* **Options & Derivatives**: High-precision Black-Scholes pricing engine, full Greeks calculations ($\Delta, \Gamma, \Theta, \text{Vega}, \text{Rho}$), and Implied Volatility (IV) surface solvers.

### 2. Fundamental Factor Alpha ("Quantamental") — **NOT IMPLEMENTED**

> None of the factors below exist in the codebase. Verified by search: there is no Piotroski F-Score,
> no PEAD, no analyst revisions, no P/E and no price-to-book anywhere under `src/`, and no
> `quant_system.alpha.fundamental` module. `README.md` states the same boundary. This section
> describes intended design only; see `docs/DATA_AND_ALPHA_ROADMAP.md`, which is explicitly a roadmap.

* Systematic factor screening across large asset universes:
  * **Value**: Price-to-Earnings ($P/E$), Price-to-Book ($P/B$), Enterprise Value to EBITDA ($EV/EBITDA$).
  * **Quality & Solvency**: Return on Equity ($ROE$), Piotroski $F$-Score, Debt-to-Equity ($D/E$), Operating Margins.
  * **Earnings Quality & Momentum**: Post-Earnings Announcement Drift (PEAD), analyst revisions, and revenue surprise scoring.

### 3. Sentiment, News & AI Multi-Agent Advisory
* **NLP News & Sentiment Analysis** — **NOT IMPLEMENTED**: no news, polarity or social-sentiment module exists under `src/quant_system/`. Intended design only.
* **LLM Multi-Agent Advisory Consensus**: Interfacing with AI advisors (e.g. Claude, Codex, Antigravity agents) that evaluate macro conditions, earnings call transcripts, and market regimes to adjust strategy weights or veto high-risk setups.
* **Academic RAG Engine**: Retrieval-Augmented Generation connecting to research papers (via arXiv) to validate theoretical alpha models against historical literature.

---

## 📊 Platform Subsystems Breakdown

| Subsystem | Module Path | Purpose |
| :--- | :--- | :--- |
| **Core Primitives** | `quant_system.core` | `Decimal` ledger, instruments, tick/bar models, orders, fills, and portfolio positions. |
| **Data Engine** | `quant_system.data` | Upstox API live/historical data client, synthetic generators, multi-timeframe bar aggregators, option chain parsers. |
| **Alpha & Factors** | `quant_system.alpha` | Technical indicators, Black-Scholes Greeks, IV surfaces, factor z-scoring, and AI multi-agent advisors. |
| **Strategy Engine** | `quant_system.strategies` | Base strategy contracts, Momentum strategies, ML Rolling Ridge Classifiers, Options Intraday Straddles, and Directional Spreads. |
| **Portfolio & Allocation**| `quant_system.portfolio` | Position sizing (Fixed Fractional, Volatility Parity, Half-Kelly), Markowitz Mean-Variance, and Risk-Parity optimizers. |
| **Risk Governor** | `quant_system.risk` | Hard pre-trade checks, leverage enforcement, maximum drawdown circuit breakers, and liquidity guards. |
| **Backtest Engine** | `quant_system.backtest` | Event-driven simulation with realistic Indian market friction (STT, GST, Stamp Duty, Exchange fees, Slippage) and Holdout Vault partitions. |
| **Analytics & Tearsheets**| `quant_system.analytics` | Comprehensive risk metrics (Sharpe, Sortino, Calmar, Max Drawdown, VaR/CVaR), Monte Carlo simulation, and Deflated Sharpe Ratio (Bailey & de Prado). |
| **Research & RAG** | `quant_system.research` | ArXiv quantitative paper fetcher, vector embeddings, and LLM semantic retrieval. |
| **Server & Desktop UI** | `quant_system.server` | FastAPI backend serving REST APIs, real-time diagnostics, and an interactive dark-mode HTML5/JS dashboard. |

---

## 🚦 Getting Started

1. **Launch the Desktop Application & Web Interface**:
   ```bash
   python launcher.py
   ```
   *Runs hardware diagnostics, establishes isolated storage, boots the FastAPI server, and launches the browser interface.*

2. **Run End-to-End Test Suite**:
   ```bash
   pytest tests/ -v
   ```

3. **Run Backtesting Examples**:
   ```bash
   # Equity Dual Momentum Backtest
   python examples/run_equity_backtest.py

   # NIFTY 50 Intraday Options Straddle Backtest
   python examples/run_options_straddle.py
   ```
