# Mizan (QuantOS) ⚖️

**Institutional-Grade Quantitative Trading OS & Dual-Standard Shariah-Compliant Wealth Engine**

Mizan unifies advanced quantitative research, backtesting, risk governance, and live paper-trading with an ethical, dual-standard (**AAOIFI** & **TASIS**) Shariah compliance framework for Indian equities (NSE/BSE).

---

## 🌟 Operating Modes (User-Configurable)

During initial setup or anytime in **Settings**, users can select their preferred operating mode:

1. **Standard QuantOS Mode**:
   - Institutional quantitative trading, backtesting (zero lookahead bias), strategy lab, and paper books.
   - Unconstrained screening across the full NIFTY 500 universe.
   - Rigorous Decimal accounting, pre-trade risk governor, and cost-aware execution models.

2. **Mizan Shariah Mode (Ethical / Halal)**:
   - **Status: working prototype on a 39-company illustrative sample. Not live, not audited.** The figures are
     hand-entered, every result is labelled `UNVERIFIED_SAMPLE`, no scholar has reviewed the rules, and a result is a
     screening aid, not a fatwa. How it works, with every threshold: [docs/HALAL_METHODOLOGY.md](docs/HALAL_METHODOLOGY.md).
     What exists and what is only a vision: [docs/HALAL_WHITE_PAPER.md](docs/HALAL_WHITE_PAPER.md).
   - **Deterministic Dual-Standard Shariah Screener** (AAOIFI-style and TASIS-style):
     - **AAOIFI-style** (market-value basis): debt, cash & receivables each under 33% of the 36-month average market
       capitalisation, impermissible income under 5% of revenue. Which published standard text these limits come from
       is an open question (see the methodology page).
     - **TASIS-style** (book-value basis): the same limits against total assets.
     - A sector test: banking and insurance, alcohol, tobacco, gambling and cinemas are screened out. Pork and weapons
       are **not** screened.
   - **Curated Thematic Halal Baskets**:
     - *Halal Tech Giants*, *Shariah High-Growth Champions*, *Green & Ethical Infrastructure*, and *NIFTY Shariah 25*.
     - They list stocks, weights and each stock's sample screening. No return, risk figure or rebalance history is
       shown, because none has been computed or recorded.
     - Order-sheet export formatted for **Zerodha CNC**, **Upstox**, **Groww**, and **AngelOne**. QuantOS does not
       place orders, and the sheet uses sample prices.
   - **Hash-chained Dividend Purification Ledger**:
     - Calculates the Rupee amount to give away from the sample's non-operating income ratio.
     - Each entry is chained to the one before it with SHA-256, so an edit made after the entry was written is
       detected. New entries (hash version 2) cover the id, ticker, gross dividend, ratio, payable
       amount and time; older entries cover only the id and the amount.
   - **Equity Zakat Calculator**:
     - Two methods: active trader (portfolio value plus cash) and long-term investor (zakatable net working assets
       per share). The nisab is a fixed, undated figure of Rs 53,550 (595 g of silver at Rs 90 a gram); you can
       enter your own.
   - **Halal Wealth Academy & Demat Guides**:
     - Foundational fiqh modules and cash-only Demat setup steps. A scholar has not reviewed the content.

---

## 🏛️ Architecture & Unified Repository Structure

```
mizan/
├── configs/                     # YAML risk limits & strategy configs
├── client/                      # Cross-platform Flutter client (Android, iOS, Windows, Web)
├── data/
│   ├── cuantos2/                # QuantOS state and SQLite market index
│   └── shariah/                 # Sample halal_stocks.db (39 hand-entered companies, UNVERIFIED_SAMPLE) & DuckDB analytics
├── frontend/                    # Apple-grade React 19 + Vite + Tailwind desktop/web UI
├── installer/                   # Inno Setup Windows installer definitions
├── src/quant_system/
│   ├── core/                    # Exact Decimal financial primitives, ledger, models
│   ├── data/                    # Market data downloaders, NSE symbol change tracking
│   ├── market/                  # Rename-aware historical bar stitching & market index
│   ├── modeling/                # Mizan cross-sectional ranking engine
│   ├── risk/                    # Pre-trade risk governor & circuit breakers
│   ├── server/                  # FastAPI high-performance local engine (API v2)
│   ├── shariah/                 # Shariah compliance, screening, baskets, zakat, purification
│   └── strategies/              # Quant strategies & backtest engine
└── tests/
    ├── shariah/                 # Shariah test suite
    └── unit & integration/      # Comprehensive QuantOS test suites
```

---

## 🚀 Quickstart

### 1. Install Python Environment
```bash
uv pip install -e .
```

### 2. Run the Full Test Gate
```bash
pytest tests/ -v
pytest tests/shariah/ -v
```

### 3. Launch Desktop Studio / Server
```bash
python -m quant_system.launcher
```
Interactive API documentation: `http://127.0.0.1:8777/docs`.

---

## 🛡️ Trust & Security

- **Strict Local Trust Boundary**: Bound to loopback with anti-CSRF ephemeral tokens and Host header verification.
- **Hermetic & Deterministic**: Zero live-money execution routing; shadow and paper execution models verified invariant-safe.
