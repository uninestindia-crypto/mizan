"""Tests for exact Decimal double-entry ledger accounting and reconciliation."""

from datetime import datetime
from decimal import Decimal

import pytest

from quant_system.core.domain import Fill, Side
from quant_system.core.ledger import DecimalLedger


def test_ledger_initial_state() -> None:
    ledger = DecimalLedger(initial_cash=Decimal("500000.00"))
    assert ledger.cash == Decimal("500000.00")
    assert len(ledger.positions) == 0
    assert len(ledger.transactions) == 0
    assert ledger.reconcile() is True


def test_ledger_buy_sell_realized_pnl() -> None:
    ledger2 = DecimalLedger(initial_cash=Decimal("200000.00"))
    now = datetime(2025, 1, 1, 10, 0)

    # Buy 100 INFY @ 1500, fee = 20
    buy_fill = Fill(
        fill_id="f1",
        order_id="o1",
        symbol="INFY",
        side=Side.BUY,
        quantity=100,
        price=Decimal("1500.00"),
        fee=Decimal("20.00"),
        timestamp=now,
    )
    ledger2.process_fill(buy_fill)
    assert ledger2.cash == Decimal("49980.00")
    assert ledger2.positions["INFY"].quantity == 100
    assert ledger2.positions["INFY"].average_price == Decimal("1500.00")

    # Sell 50 INFY @ 1600, fee = 10
    sell_fill = Fill(
        fill_id="f2",
        order_id="o2",
        symbol="INFY",
        side=Side.SELL,
        quantity=50,
        price=Decimal("1600.00"),
        fee=Decimal("10.00"),
        timestamp=now,
    )
    ledger2.process_fill(sell_fill)

    # Revenue = 50 * 1600 = 80,000 - 10 = 79,990 net cash inflow
    # Cash = 49,980 + 79,990 = 129,970.00
    assert ledger2.cash == Decimal("129970.00")
    assert ledger2.positions["INFY"].quantity == 50
    # Realized PnL = (1600 - 1500)*50 - 10 fee = 5000 - 10 = 4990
    assert ledger2.realized_pnl == Decimal("4990.00")
    assert ledger2.reconcile() is True

    # Test snapshot
    snapshot = ledger2.get_portfolio_snapshot(
        current_prices={"INFY": Decimal("1650.00")},
        timestamp=now,
    )
    assert snapshot.total_equity == Decimal("129970.00") + (Decimal("1650.00") * Decimal(50))


def test_ledger_short_selling_and_cover() -> None:
    ledger = DecimalLedger(initial_cash=Decimal("500000.00"), allow_short=True)
    now = datetime(2025, 1, 1, 10, 0)

    # Short 50 NIFTY24500CE @ 200, fee = 20
    sell_short_fill = Fill(
        fill_id="f_short_1",
        order_id="o_short_1",
        symbol="NIFTY24500CE",
        side=Side.SELL,
        quantity=50,
        price=Decimal("200.00"),
        fee=Decimal("20.00"),
        timestamp=now,
    )
    ledger.process_fill(sell_short_fill)
    # Cash inflow = 50 * 200 - 20 = 9980
    assert ledger.cash == Decimal("509980.00")
    assert ledger.positions["NIFTY24500CE"].quantity == -50
    assert ledger.positions["NIFTY24500CE"].average_price == Decimal("200.00")

    # Cover short at 100, fee = 20
    cover_fill = Fill(
        fill_id="f_cover_1",
        order_id="o_cover_1",
        symbol="NIFTY24500CE",
        side=Side.BUY,
        quantity=50,
        price=Decimal("100.00"),
        fee=Decimal("20.00"),
        timestamp=now,
    )
    ledger.process_fill(cover_fill)
    # Cash outflow = 50 * 100 + 20 = 5020
    # Remaining cash = 509,980 - 5020 = 504,960.00
    assert ledger.cash == Decimal("504960.00")
    assert "NIFTY24500CE" not in ledger.positions
    # Realized PnL = (200 - 100)*50 - 20 = 4980
    assert ledger.realized_pnl == Decimal("4980.00")
    assert ledger.reconcile() is True


def test_ledger_prevents_negative_cash_and_naked_sell() -> None:
    ledger = DecimalLedger(initial_cash=Decimal("1000.00"))
    now = datetime(2025, 1, 1, 10, 0)

    # Buy costing more than cash
    buy_fill = Fill(
        fill_id="f1",
        order_id="o1",
        symbol="INFY",
        side=Side.BUY,
        quantity=100,
        price=Decimal("1500.00"),
        fee=Decimal("20.00"),
        timestamp=now,
    )
    with pytest.raises(ValueError, match="cash would drop below zero"):
        ledger.process_fill(buy_fill)

    # Sell without holding position
    sell_fill = Fill(
        fill_id="f2",
        order_id="o2",
        symbol="TCS",
        side=Side.SELL,
        quantity=10,
        price=Decimal("3500.00"),
        fee=Decimal("10.00"),
        timestamp=now,
    )
    with pytest.raises(ValueError, match="Cannot sell 10 of TCS"):
        ledger.process_fill(sell_fill)
