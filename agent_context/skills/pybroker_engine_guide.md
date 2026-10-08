# PyBroker Accelerated Research Engine & Agent Guide for Mizan

This document defines the architecture, non-negotiable laws, and developer interface for using the **PyBroker** engine within Mizan (QuantOS).

---

## 1. Core Purpose

PyBroker provides Mizan with an ultra-fast, Numba-compiled quantitative backtesting and machine learning research kernel. While Mizan's `DecimalLedger` and `PreTradeRiskGovernor` govern live paper trading, cash accounts, and regulatory risk, PyBroker provides:
- **10x–100x Faster Parameter Sweeps & Backtests**: Through compiled `@njit(cache=True)` vectorized kernels (`src/pybroker/vect.py`).
- **Walkforward Machine Learning**: Native rolling train/test splits that strictly eliminate lookahead bias (`src/pybroker/model.py`).
- **Hyperparameter Optimization**: Built-in Optuna Bayesian search (`src/pybroker/optimize.py`).
- **Monte Carlo Bootstrapping**: Evaluating strategy metric confidence intervals (`src/pybroker/eval.py`).

---

## 2. Non-Negotiable Engineering Laws

When writing or modifying PyBroker code in Mizan, every AI agent and developer must enforce these rules:

1. **Zero Lookahead Bias**:
   - Every array visible to a strategy must be pre-sliced `[:end_index]`.
   - Never use negative indexing into unsliced arrays (`arr[-1]` on an un-sliced series silently wraps to the end of time — the future).
   - Any new indicator kernel must pass the **bump-last-bar check**: changing only the final input bar must leave all earlier output values bit-identical.

2. **Pandas Boundary Discipline**:
   - Pandas is an I/O format only. It is used when ingesting Mizan's `PriceBar` data or exporting `TestResult`.
   - Never construct `pd.Series` or call `.rolling()`, `.ewm()`, `.shift()`, or `.apply()` inside indicators or per-bar execution functions. All inner-loop math must be pure NumPy + Numba.

3. **Every Compiled Kernel is `@njit(cache=True)`**:
   - No object mode, no bare `@njit`. Kernels in `vect.py` must stay strictly JIT-compiled with disk caching.

4. **Money Precision**:
   - Cash balances, portfolio valuations, and share counts use `Decimal` at the transaction boundary. Vectorized prices, indicators, and signals use `float64`.

5. **Indian Market Regulatory Costs**:
   - When running Indian equity strategies, wrap executions with Mizan's `IndianMarketCostModel` (`src/quant_system/backtest/costs.py` and `pybroker_adapter.py`) to account for STT (0.1%), NSE turnover charges (0.00345%), SEBI fees, Stamp duty (0.015%), 18% GST on brokerage, and paisa rounding.

6. **Shariah Universe Filtering**:
   - In Mizan Shariah Mode, candidate universes must first be filtered through Mizan's AAOIFI or TASIS screener (`src/quant_system/shariah/screening.py`) before passing symbols to PyBroker.

---

## 3. Available Agent Skills in Mizan

The following specialized skills are installed in `.agents/skills/` and `skills/`:
- `pybroker-strategy-creator`: Designing rule-based per-bar execution strategies.
- `pybroker-indicator-creator`: Writing custom `@njit` vectorized technical indicators.
- `pybroker-model-trainer`: Training Walkforward ML models (scikit-learn, XGBoost, PyTorch) with zero leakage.
- `pybroker-optimize`: Running Optuna hyperparameter optimization.
- `pybroker-multi-interval`: Mixing multi-timeframe intervals (e.g. 1m bars with 1D indicators).
- `pybroker-rotational-trading`: Implementing momentum ranking and dynamic portfolio rotation.
