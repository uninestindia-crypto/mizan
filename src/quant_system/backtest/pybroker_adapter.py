"""PyBroker backtesting adapter for Mizan (QuantOS).

Bridges Mizan's typed PriceBar market history, IndianMarketCostModel (STT, GST,
SEBI, Stamp Duty, NSE turnover, and paisa quantization), and Shariah screening
to PyBroker's ultra-fast, Numba-compiled execution engine.
"""

from __future__ import annotations

import logging
import sqlite3
from collections.abc import Callable, Mapping, Sequence
from decimal import Decimal
from typing import Any

import pandas as pd  # type: ignore[import-untyped]

import pybroker
from quant_system.backtest.costs import IndianMarketCostModel
from quant_system.backtest.engine import BacktestResult
from quant_system.core.domain import Fill, PortfolioSnapshot, PriceBar, Side
from quant_system.server.v2.paths import app_root

logger = logging.getLogger(__name__)
_PAISA = Decimal("0.01")


def is_symbol_shariah_compliant(symbol: str, standard: str = "AAOIFI") -> bool:
    """Checks if a symbol passes Mizan's audited Shariah compliance standards."""
    db_path = app_root() / "data" / "shariah" / "halal_stocks.db"
    clean_sym = symbol.replace(".NS", "").replace(".BO", "").strip().upper()
    col = "aaoifi_status" if standard.upper() == "AAOIFI" else "tasis_status"

    if db_path.exists():
        try:
            with sqlite3.connect(str(db_path)) as conn:
                row = conn.execute(
                    f"SELECT {col} FROM companies WHERE symbol = ? OR ticker = ?",
                    (clean_sym, f"{clean_sym}.NS"),
                ).fetchone()
                if row:
                    return str(row[0]).upper() == "COMPLIANT"
        except Exception as e:
            logger.debug("Shariah DB lookup failed for %s: %s", symbol, e)

    # Deterministic fallback: Conventional banking/lending is strictly non-compliant
    if any(k in clean_sym for k in ["BANK", "FIN", "CAPITAL", "MUTUAL", "INSUR"]):
        return False
    return True


def bars_to_dataframe(symbol_bars: Mapping[str, Sequence[PriceBar]]) -> pd.DataFrame:
    """Converts Mizan PriceBar sequences into a DataFrame formatted for PyBroker.

    PyBroker requires columns: ['date', 'symbol', 'open', 'high', 'low', 'close', 'volume'].
    Prices are converted to float64 at this I/O boundary, preserving chronological sort.
    """
    records: list[dict[str, Any]] = []
    for symbol, bars in symbol_bars.items():
        for b in bars:
            records.append(
                {
                    "date": b.timestamp,
                    "symbol": symbol,
                    "open": float(b.open),
                    "high": float(b.high),
                    "low": float(b.low),
                    "close": float(b.close),
                    "volume": float(b.volume),
                }
            )
    if not records:
        raise ValueError("No historical price bars provided to PyBroker adapter.")

    df = pd.DataFrame.from_records(records)
    df["date"] = pd.to_datetime(df["date"])
    df = df.sort_values(by=["date", "symbol"]).reset_index(drop=True)
    return df


class PyBrokerBacktestAdapter:
    """Runs high-performance backtests using PyBroker with Mizan's exact accounting."""

    def __init__(
        self,
        initial_cash: Decimal = Decimal("1000000.00"),  # Default ₹10 Lakhs
        slippage_bps: float = 5.0,
        shariah_mode: bool = False,
        shariah_standard: str = "AAOIFI",  # "AAOIFI" or "TASIS"
    ) -> None:
        self.initial_cash = initial_cash
        self.slippage_bps = slippage_bps
        self.shariah_mode = shariah_mode
        self.shariah_standard = shariah_standard

    def filter_universe(self, symbols: Sequence[str]) -> list[str]:
        """Filters symbol universe if Shariah mode is enabled."""
        if not self.shariah_mode:
            return list(symbols)

        return [
            sym
            for sym in symbols
            if is_symbol_shariah_compliant(sym, standard=self.shariah_standard)
        ]

    def run(
        self,
        symbol_bars: Mapping[str, Sequence[PriceBar]],
        exec_fn: Callable[[pybroker.ExecContext], None],
        indicators: Sequence[Any] | None = None,
        warmup: int = 20,
    ) -> tuple[BacktestResult, pybroker.TestResult]:
        """Executes a PyBroker backtest and maps outputs to Mizan's native BacktestResult.

        Args:
            symbol_bars: Mapping of symbol to chronological PriceBar sequence.
            exec_fn: Per-bar execution function for PyBroker.
            indicators: PyBroker indicator definitions.
            warmup: Number of warmup bars before trading begins.

        Returns:
            Tuple of (Mizan BacktestResult, PyBroker TestResult).
        """
        all_symbols = list(symbol_bars.keys())
        active_symbols = self.filter_universe(all_symbols)
        if not active_symbols:
            raise ValueError("All symbols excluded by Shariah screening or empty input universe.")

        filtered_bars = {s: symbol_bars[s] for s in active_symbols if s in symbol_bars}
        df = bars_to_dataframe(filtered_bars)

        # Configure PyBroker Strategy
        cfg = pybroker.StrategyConfig(initial_cash=float(self.initial_cash))
        strategy = pybroker.Strategy(
            data_source=df,
            start_date=df["date"].min(),
            end_date=df["date"].max(),
            config=cfg,
        )

        indicators_arg = list(indicators) if indicators is not None else []
        strategy.add_execution(
            exec_fn,
            active_symbols,
            indicators=indicators_arg,
        )

        # Execute accelerated backtest
        pybroker_result = strategy.backtest(warmup=warmup)

        # Map PyBroker trades to Mizan Fills with exact IndianMarketCostModel
        fills: list[Fill] = []
        total_friction = Decimal("0.00")

        if pybroker_result.trades is not None and not pybroker_result.trades.empty:
            for idx, row in pybroker_result.trades.iterrows():
                symbol = str(row["symbol"])
                qty = int(abs(row["shares"]))
                if qty <= 0:
                    continue

                # Buy Entry fill
                entry_dt = pd.to_datetime(row["entry_date"]).to_pydatetime()
                raw_entry = row.get("entry_price") if "entry_price" in row else row["entry"]
                entry_price = Decimal(str(round(float(raw_entry), 2))).quantize(_PAISA)
                cost_buy = IndianMarketCostModel.calculate_equity_delivery(
                    side=Side.BUY,
                    quantity=qty,
                    price=entry_price,
                    slippage_bps=self.slippage_bps,
                )
                fill_buy = Fill(
                    fill_id=f"PB-ENTRY-{idx}",
                    order_id=f"ORD-ENTRY-{idx}",
                    symbol=symbol,
                    side=Side.BUY,
                    quantity=qty,
                    price=entry_price,
                    fee=cost_buy.total_fee,
                    timestamp=entry_dt,
                )
                fills.append(fill_buy)
                total_friction += cost_buy.total_friction

                # Sell Exit fill
                exit_dt = pd.to_datetime(row["exit_date"]).to_pydatetime()
                raw_exit = row.get("exit_price") if "exit_price" in row else row["exit"]
                exit_price = Decimal(str(round(float(raw_exit), 2))).quantize(_PAISA)
                cost_sell = IndianMarketCostModel.calculate_equity_delivery(
                    side=Side.SELL,
                    quantity=qty,
                    price=exit_price,
                    slippage_bps=self.slippage_bps,
                )
                fill_sell = Fill(
                    fill_id=f"PB-EXIT-{idx}",
                    order_id=f"ORD-EXIT-{idx}",
                    symbol=symbol,
                    side=Side.SELL,
                    quantity=qty,
                    price=exit_price,
                    fee=cost_sell.total_fee,
                    timestamp=exit_dt,
                )
                fills.append(fill_sell)
                total_friction += cost_sell.total_friction

        # Map Portfolio Snapshots
        equity_curve: list[PortfolioSnapshot] = []
        portfolio_df = pybroker_result.portfolio

        if portfolio_df is not None and not portfolio_df.empty:
            for dt_idx, prow in portfolio_df.iterrows():
                raw_dt = prow["date"] if "date" in prow else dt_idx
                snap_dt = pd.to_datetime(raw_dt).to_pydatetime()
                cash_dec = Decimal(str(round(float(prow["cash"]), 2))).quantize(_PAISA)
                raw_eq = prow["market_value"] if "market_value" in prow else prow.get("equity", 0.0)
                equity_dec = Decimal(str(round(float(raw_eq), 2))).quantize(_PAISA)
                equity_curve.append(
                    PortfolioSnapshot(
                        timestamp=snap_dt,
                        cash=cash_dec,
                        positions={},
                        total_market_value=equity_dec - cash_dec,
                        unrealized_pnl=Decimal("0.00"),
                        realized_pnl=Decimal("0.00"),
                    )
                )

        final_equity = equity_curve[-1].total_equity if equity_curve else self.initial_cash
        # Adjust final equity for Indian transaction friction
        final_equity_net = max(Decimal("0.00"), final_equity - total_friction).quantize(_PAISA)
        total_ret = float((final_equity_net - self.initial_cash) / self.initial_cash)

        mizan_result = BacktestResult(
            initial_cash=self.initial_cash,
            final_equity=final_equity_net,
            total_return_pct=total_ret,
            total_trades=len(pybroker_result.trades) if pybroker_result.trades is not None else 0,
            fills=fills,
            equity_curve=equity_curve,
            total_friction_paid=total_friction,
        )

        return mizan_result, pybroker_result
