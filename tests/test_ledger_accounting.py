"""Tests for exact Decimal double-entry ledger accounting, FIFO lots, idempotency, and reconciliation."""

from datetime import datetime
from decimal import Decimal

import pytest

from quant_system.core.domain import Fill, Side
from quant_system.core.ledger import (
    CashFlowEvent,
    DecimalLedger,
    IdempotencyConflictError,
    LedgerInvariantViolation,
)


def test_ledger_initial_state() -> None:
    """Verifies pristine ledger initialization."""
    ledger = DecimalLedger(initial_cash=Decimal("500000.00"))
    assert ledger.cash == Decimal("500000.00")
    assert len(ledger.positions) == 0
    assert len(ledger.transactions) == 0
    assert len(ledger.lots) == 0
    assert ledger.realized_pnl == Decimal("0.00")
    assert ledger.reconcile() is True
    assert len(ledger.state_hash) == 64


def test_ledger_rejects_binary_float() -> None:
    """Non-negotiable invariant: binary floats must be strictly rejected."""
    with pytest.raises(TypeError, match="Binary float forbidden"):
        DecimalLedger(initial_cash=500000.0)  # type: ignore

    now = datetime(2025, 1, 1, 10, 0)

    with pytest.raises(TypeError, match="Binary float forbidden"):
        Fill(
            fill_id="f_bad",
            order_id="o_bad",
            symbol="INFY",
            side=Side.BUY,
            quantity=10,
            price=1500.0,  # type: ignore
            fee=Decimal("20.00"),
            timestamp=now,
        )

    with pytest.raises(TypeError, match="Binary float forbidden"):
        Fill(
            fill_id="f_bad2",
            order_id="o_bad2",
            symbol="INFY",
            side=Side.BUY,
            quantity=10,
            price=Decimal("1500.00"),
            fee=20.0,  # type: ignore
            timestamp=now,
        )


def test_ledger_buy_sell_fifo_realized_pnl() -> None:
    """Verifies multi-lot BUYs followed by partial FIFO SELLs and realized P&L."""
    ledger = DecimalLedger(initial_cash=Decimal("200000.00"))
    now = datetime(2025, 1, 1, 10, 0)

    # Lot 1: Buy 50 INFY @ 1000, fee = 10 -> Cash outflow = 50,010
    f1 = Fill(
        fill_id="f1",
        order_id="o1",
        symbol="INFY",
        side=Side.BUY,
        quantity=50,
        price=Decimal("1000.00"),
        fee=Decimal("10.00"),
        timestamp=now,
    )
    ledger.process_fill(f1)
    assert ledger.cash == Decimal("149990.00")
    assert ledger.positions["INFY"].quantity == 50
    assert ledger.positions["INFY"].average_price == Decimal("1000.00")
    assert len(ledger.lots["INFY"]) == 1

    # Lot 2: Buy 50 INFY @ 1200, fee = 10 -> Cash outflow = 60,010
    f2 = Fill(
        fill_id="f2",
        order_id="o2",
        symbol="INFY",
        side=Side.BUY,
        quantity=50,
        price=Decimal("1200.00"),
        fee=Decimal("10.00"),
        timestamp=now,
    )
    ledger.process_fill(f2)
    assert ledger.cash == Decimal("89980.00")
    assert ledger.positions["INFY"].quantity == 100
    # Weighted avg price = (50*1000 + 50*1200)/100 = 1100.00
    assert ledger.positions["INFY"].average_price == Decimal("1100.00")
    assert len(ledger.lots["INFY"]) == 2

    # Sell 75 INFY @ 1400, fee = 20 (FIFO: 50 from Lot 1 @ 1000, 25 from Lot 2 @ 1200)
    # Revenue = 75 * 1400 = 105,000 - 20 = 104,980 net cash inflow
    # Realized PnL = (1400 - 1000)*50 - 10 (entry fee) + (1400 - 1200)*25 - 5 (pro-rata entry fee) - 20 (exit fee) = 24,965.00
    f3 = Fill(
        fill_id="f3",
        order_id="o3",
        symbol="INFY",
        side=Side.SELL,
        quantity=75,
        price=Decimal("1400.00"),
        fee=Decimal("20.00"),
        timestamp=now,
    )
    ledger.process_fill(f3)

    assert ledger.cash == Decimal("89980.00") + Decimal("104980.00")  # 194,960.00
    assert ledger.realized_pnl == Decimal("24965.00")
    assert ledger.positions["INFY"].quantity == 25
    assert ledger.positions["INFY"].average_price == Decimal("1200.00")
    assert len(ledger.lots["INFY"]) == 1
    assert ledger.lots["INFY"][0].quantity == 25
    assert ledger.lots["INFY"][0].entry_price == Decimal("1200.00")
    assert ledger.lots["INFY"][0].entry_fee == Decimal("5.00")
    assert ledger.reconcile() is True


def test_ledger_position_flip_long_to_short() -> None:
    """Verifies atomic position flip from Long 30 to Short 20 when selling 50 shares."""
    ledger = DecimalLedger(initial_cash=Decimal("100000.00"), allow_short=True)
    now = datetime(2025, 1, 1, 10, 0)

    # Buy 30 TCS @ 3000, fee = 10
    ledger.process_fill(
        Fill(
            fill_id="f_flip_1",
            order_id="o_flip_1",
            symbol="TCS",
            side=Side.BUY,
            quantity=30,
            price=Decimal("3000.00"),
            fee=Decimal("10.00"),
            timestamp=now,
        )
    )
    assert ledger.positions["TCS"].quantity == 30

    # Sell 50 TCS @ 3500, fee = 20 (closes 30 long, opens 20 short)
    # Realized PnL on 30 long = (3500 - 3000)*30 - 10 (entry fee) - 20 (exit fee) = 15,000 - 30 = 14,970.00
    # Net cash inflow = 50 * 3500 - 20 = 175,000 - 20 = 174,980.00
    ledger.process_fill(
        Fill(
            fill_id="f_flip_2",
            order_id="o_flip_2",
            symbol="TCS",
            side=Side.SELL,
            quantity=50,
            price=Decimal("3500.00"),
            fee=Decimal("20.00"),
            timestamp=now,
        )
    )

    assert ledger.positions["TCS"].quantity == -20
    assert ledger.positions["TCS"].average_price == Decimal("3500.00")
    assert ledger.realized_pnl == Decimal("14970.00")
    assert len(ledger.lots["TCS"]) == 1
    assert ledger.lots["TCS"][0].side == Side.SELL
    assert ledger.lots["TCS"][0].quantity == 20
    assert ledger.reconcile() is True


def test_ledger_idempotency_and_conflict_detection() -> None:
    """Verifies that replaying an event is a no-op, while conflicting payload raises error."""
    ledger = DecimalLedger(initial_cash=Decimal("100000.00"))
    now = datetime(2025, 1, 1, 10, 0)
    fill = Fill(
        fill_id="f_idemp_1",
        order_id="o_idemp_1",
        symbol="SBIN",
        side=Side.BUY,
        quantity=100,
        price=Decimal("800.00"),
        fee=Decimal("15.00"),
        timestamp=now,
    )

    tx1 = ledger.process_fill(fill)
    initial_tx_count = len(ledger.transactions)
    initial_cash = ledger.cash

    # Replay exact same fill
    tx2 = ledger.process_fill(fill)
    assert tx1.tx_id == tx2.tx_id
    assert len(ledger.transactions) == initial_tx_count
    assert ledger.cash == initial_cash

    # Conflicting fill with same fill_id but different quantity
    conflicting_fill = Fill(
        fill_id="f_idemp_1",
        order_id="o_idemp_1",
        symbol="SBIN",
        side=Side.BUY,
        quantity=200,  # Conflict!
        price=Decimal("800.00"),
        fee=Decimal("15.00"),
        timestamp=now,
    )
    with pytest.raises(IdempotencyConflictError, match="differing payload"):
        ledger.process_fill(conflicting_fill)

    # State must be completely unmodified after error
    assert len(ledger.transactions) == initial_tx_count
    assert ledger.cash == initial_cash


def test_ledger_atomic_validation_before_mutation() -> None:
    """Verifies that a failed fill is an atomic no-op leaving balances and lots untouched."""
    ledger = DecimalLedger(initial_cash=Decimal("5000.00"))
    now = datetime(2025, 1, 1, 10, 0)
    hash_before = ledger.state_hash

    # Overdraft fill (needs 10,000 + 20 but only have 5,000)
    f_oversized = Fill(
        fill_id="f_over",
        order_id="o_over",
        symbol="RELIANCE",
        side=Side.BUY,
        quantity=10,
        price=Decimal("1000.00"),
        fee=Decimal("20.00"),
        timestamp=now,
    )
    with pytest.raises(ValueError, match="cash would drop below zero"):
        ledger.process_fill(f_oversized)

    assert ledger.cash == Decimal("5000.00")
    assert len(ledger.positions) == 0
    assert len(ledger.transactions) == 0
    assert ledger.state_hash == hash_before


def test_ledger_external_cash_flows() -> None:
    """Verifies external deposits, withdrawals, and overdraft prevention."""
    ledger = DecimalLedger(initial_cash=Decimal("10000.00"))
    now = datetime(2025, 1, 1, 10, 0)

    # Deposit 50,000
    dep = CashFlowEvent(
        event_id="dep_1",
        amount=Decimal("50000.00"),
        timestamp=now,
        description="Bank wire deposit",
    )
    ledger.process_cash_flow(dep)
    assert ledger.cash == Decimal("60000.00")

    # Withdraw 20,000
    wd = CashFlowEvent(
        event_id="wd_1",
        amount=Decimal("-20000.00"),
        timestamp=now,
        description="Bank withdrawal",
    )
    ledger.process_cash_flow(wd)
    assert ledger.cash == Decimal("40000.00")

    # Overdraft withdrawal
    wd_bad = CashFlowEvent(
        event_id="wd_bad",
        amount=Decimal("-50000.00"),
        timestamp=now,
        description="Illegal overdraft withdrawal",
    )
    with pytest.raises(LedgerInvariantViolation, match="drop below zero"):
        ledger.process_cash_flow(wd_bad)

    assert ledger.cash == Decimal("40000.00")
    assert ledger.reconcile() is True


# -------------------------------------------------------------------------
# Ring 5: L-2 regression — a snapshot must not fabricate a mark
# -------------------------------------------------------------------------


def test_portfolio_snapshot_refuses_to_mark_a_position_without_a_price() -> None:
    """L-2: a missing price silently marked the position to its own cost.

    Unrealized P&L for that symbol came out exactly 0.00 and total market value was wrong,
    with no signal to the caller, while the method promised an exact mark-to-market.
    """
    ledger = DecimalLedger(initial_cash=Decimal("200000.00"))
    now = datetime(2025, 1, 1, 10, 0)
    ledger.process_fill(
        Fill(
            fill_id="f_l2",
            order_id="o_l2",
            symbol="INFY",
            side=Side.BUY,
            quantity=50,
            price=Decimal("1000.00"),
            fee=Decimal("10.00"),
            timestamp=now,
        )
    )

    with pytest.raises(LedgerInvariantViolation, match="INFY"):
        ledger.get_portfolio_snapshot(current_prices={}, timestamp=now)


def test_portfolio_snapshot_marks_normally_when_the_price_is_supplied() -> None:
    """The repair must not refuse a snapshot that can actually be computed."""
    ledger = DecimalLedger(initial_cash=Decimal("200000.00"))
    now = datetime(2025, 1, 1, 10, 0)
    ledger.process_fill(
        Fill(
            fill_id="f_l2b",
            order_id="o_l2b",
            symbol="INFY",
            side=Side.BUY,
            quantity=50,
            price=Decimal("1000.00"),
            fee=Decimal("10.00"),
            timestamp=now,
        )
    )

    snapshot = ledger.get_portfolio_snapshot(
        current_prices={"INFY": Decimal("1100.00")}, timestamp=now
    )
    assert snapshot.total_market_value == Decimal("55000.00")
    assert snapshot.unrealized_pnl == Decimal("5000.00")
