# Modular Quant System (QuantOS)

A high-performance, institutional-grade, modular Quantitative Trading & Backtesting System designed for equity and derivatives markets (specifically optimized for NSE India and US Equities).

---

## 🏛️ Architecture & Modular Pipeline

```
quant_system/
├── configs/                     # YAML risk limits & strategy configs
├── examples/                    # End-to-end runnable scripts
│   ├── run_equity_backtest.py   # Equity Dual Momentum Backtest & Tearsheet
│   └── run_options_straddle.py  # NIFTY 09:20 Intraday Straddle Simulation
├── src/quant_system/
│   ├── core/                    # Exact Decimal financial primitives, ledger, domain models
│   ├── data/                    # Market data bars, option chains, universe loaders
│   ├── alpha/                   # Technical indicators, Black-Scholes Greeks, IV surfaces
│   ├── strategies/              # BaseStrategy protocol, Equity Momentum, Options Straddles
│   ├── portfolio/               # Sizing (Kelly, Vol Parity) & capital allocation
│   ├── risk/                    # Pre-Trade Risk Governor & circuit breakers
│   ├── backtest/                # Event-driven backtester (zero lookahead) & cost models
│   ├── analytics/               # Tearsheets, Sharpe/Sortino/Calmar, Deflated Sharpe
│   └── execution/               # Deterministic paper broker & order state machine
└── tests/                       # Complete unit & integration test suite
```

---

## 🚀 Quickstart

### 1. Install dependencies
```bash
pip install -e .
```

### 2. Run Tests
```bash
pytest tests/ -v
```

### 3. Run Equity Momentum Backtest Example
```bash
python examples/run_equity_backtest.py
```

### 4. Run Options Straddle Simulation Example
```bash
python examples/run_options_straddle.py
```

---

## 📚 Detailed Documentation

Comprehensive documentation is available in the [`docs/`](file:///d:/quant_system/docs) directory:
* **[Platform Overview](file:///d:/quant_system/docs/PLATFORM_OVERVIEW.md)**: System vision, core design invariants, multi-modal alpha architecture, and subsystem guide.
* **[Technical Architecture](file:///d:/quant_system/docs/ARCHITECTURE.md)**: Deep dive into the event-driven backtest engine, exact Decimal ledger, pre-trade risk governor, and domain models.
* **[Alpha & Data Roadmap](file:///d:/quant_system/docs/DATA_AND_ALPHA_ROADMAP.md)**: Blueprint for integrating Technical, Fundamental (Quantamental), and Sentiment (NLP/LLM) alpha.

---

## 🛡️ Core Invariants

1. **Exact Decimal Accounting**: All cash, transaction costs, and portfolio values are computed using exact `Decimal` precision. No floating-point penny leaks.
2. **Strict Pre-Trade Risk**: Every trade proposal must be approved by the `RiskGovernor` before it can reach execution.
3. **No Lookahead Bias**: Fills occur on the *next bar open* after a signal is calculated at bar close. Same-bar fills are strictly rejected.
4. **Realistic Market Friction**: Models Indian STT (Securities Transaction Tax), GST, Exchange Turnover, Stamp Duty, and slippage.
5. **Multi-Modal Alpha Engine**: Unifies Price/Derivatives Technical Alpha, Fundamental Balance Sheet Factor Scoring, and AI/NLP Sentiment Feeds.
