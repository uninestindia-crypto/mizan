"""Unit tests for Mizan's PyBrokerBacktestAdapter and Indian cost integration."""

from __future__ import annotations

from datetime import datetime, timedelta
from decimal import Decimal

import pytest

# PyBroker's data layer needs the optional research extra (alpaca-py); the standard install does not have it.
pytest.importorskip("alpaca", reason="the optional research extra (alpaca-py) is not installed")

import pybroker  # noqa: E402
from quant_system.backtest.pybroker_adapter import (  # noqa: E402
    PyBrokerBacktestAdapter,
    bars_to_dataframe,
)
from quant_system.core.domain import PriceBar  # noqa: E402


def _make_dummy_bars(symbol: str, count: int = 50) -> list[PriceBar]:
    base_dt = datetime(2025, 1, 1, 9, 15)
    bars: list[PriceBar] = []
    base_price = Decimal("100.00")
    for i in range(count):
        dt = base_dt + timedelta(days=i)
        p = base_price + Decimal(str(i * 0.5))
        bars.append(
            PriceBar(
                symbol=symbol,
                timestamp=dt,
                open=p,
                high=p + Decimal("2.00"),
                low=p - Decimal("1.00"),
                close=p + Decimal("0.50"),
                volume=1000 + i * 10,
            )
        )
    return bars


def test_bars_to_dataframe() -> None:
    bars = _make_dummy_bars("RELIANCE", count=10)
    df = bars_to_dataframe({"RELIANCE": bars})
    assert len(df) == 10
    assert list(df.columns) == ["date", "symbol", "open", "high", "low", "close", "volume"]
    assert df["symbol"].iloc[0] == "RELIANCE"
    assert df["close"].iloc[0] == 100.50


def test_pybroker_adapter_execution() -> None:
    bars = _make_dummy_bars("TCS", count=40)
    adapter = PyBrokerBacktestAdapter(
        initial_cash=Decimal("100000.00"),
        slippage_bps=5.0,
        shariah_mode=False,
    )

    def dummy_exec(ctx: pybroker.ExecContext) -> None:
        if not ctx.long_pos() and ctx.bars >= 22:
            ctx.buy_shares = 10
            ctx.hold_bars = 5

    mizan_res, pb_res = adapter.run(
        symbol_bars={"TCS": bars},
        exec_fn=dummy_exec,
        warmup=20,
    )

    assert mizan_res.initial_cash == Decimal("100000.00")
    assert mizan_res.final_equity > Decimal("0.00")
    assert mizan_res.total_friction_paid > Decimal("0.00")
    assert len(mizan_res.fills) > 0
    assert len(mizan_res.equity_curve) > 0
    assert pb_res is not None


def test_pybroker_adapter_shariah_filtering() -> None:
    adapter = PyBrokerBacktestAdapter(
        initial_cash=Decimal("500000.00"),
        shariah_mode=True,
        shariah_standard="AAOIFI",
    )

    # Filter universe should retain INFY (tech) and exclude HDFCBANK (interest banking)
    compliant = adapter.filter_universe(["INFY", "HDFCBANK"])
    assert "INFY" in compliant
    assert "HDFCBANK" not in compliant
