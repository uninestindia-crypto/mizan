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
   - **Deterministic Dual-Standard Shariah Screener**:
     - **AAOIFI Standard** (Global): Debt, cash & receivables ratios $< 33\%$, non-operating interest income $< 5\%$.
     - **TASIS Standard** (Domestic India): Total assets denominator aligned with Indian scholarly consensus.
   - **Curated Thematic Halal Baskets**:
     - *Halal Tech Giants*, *Shariah High-Growth Champions*, *Ethical Infrastructure*, and *NIFTY Shariah 25*.
     - 1-Click order sheet exports formatted for **Zerodha CNC**, **Upstox**, **Groww**, and **AngelOne**.
   - **Cryptographic Dividend Purification Ledger**:
     - Calculates exact Rupee charity deductions from non-operating interest income.
     - Sequential **SHA-256 cryptographic hash chaining** ensuring immutable audit receipts.
   - **Equity Zakat Calculator**:
     - Dual-method calculation: Active Trader ($100\%$ NLV) vs Long-term Investor (Zakatable net working assets) calibrated to the Indian Silver Nisab ($\text{₹}53,550.00$).
   - **Halal Wealth Academy & Demat Guides**:
     - Foundational Fiqh modules (Musharakah/Mudarabah) and zero-interest, cash-only Demat account setup instructions.

---

## 🏛️ Architecture & Unified Repository Structure

```
mizan/
├── configs/                     # YAML risk limits & strategy configs
├── client/                      # Cross-platform Flutter client (Android, iOS, Windows, Web)
├── data/
│   ├── cuantos2/                # QuantOS state and SQLite market index
│   └── shariah/                 # Pre-audited halal_stocks.db & DuckDB analytics
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
    ├── shariah/                 # 160/160 Shariah test suite
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
