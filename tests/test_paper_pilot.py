"""Comprehensive test suite for Slice 10: Quote-Driven Paper Pilot.

Verifies:
1. Top-of-book and L2 market depth execution matching with depth walking.
2. Conservative adverse slippage, spread deduction, and exact friction breakdown.
3. Queue priority delay, partial fill allocations, and remainder queueing.
4. Stable idempotency keys and atomic ledger mutations (no double posting).
5. Exchange and market rule checks (crossed, locked, wide, stale, out-of-order, tick, lot, liquidity).
6. Pre-trade risk gating (cash, concentration, naked short, kill switch).
7. Clean session-end cancellation of open simulated orders and penny-exact daily reconciliation.
8. Multi-session paper campaign and deterministic replay.
9. Options contract execution with exact regulatory friction.
"""

from datetime import UTC, date, datetime, timedelta
from decimal import Decimal

import pytest

from quant_system.core.domain import (
    Order,
    OrderStatus,
    OrderType,
    Quote,
    Side,
)
from quant_system.execution.orderbook_sim import (
    OrderBookSimConfig,
    OrderBookSimulator,
    OrderBookSnapshot,
)
from quant_system.execution.paper_pilot import (
    PaperPilotEngine,
    PaperProposal,
    SessionStatus,
)
from quant_system.risk.checks import RiskLimits
from quant_system.risk.governor import PreTradeRiskGovernor

_PAISA = Decimal("0.01")


def test_orderbook_snapshot_creation_and_properties() -> None:
    now = datetime(2025, 1, 1, 9, 15, tzinfo=UTC)
    book = OrderBookSnapshot.from_levels(
        symbol="INFY",
        timestamp=now,
        bids=[(Decimal("1500.00"), 100), (Decimal("1499.50"), 200)],
        asks=[(Decimal("1500.50"), 150), (Decimal("1501.00"), 300)],
        last_price=Decimal("1500.25"),
    )

    assert book.symbol == "INFY"
    assert book.best_bid_price == Decimal("1500.00")
    assert book.best_ask_price == Decimal("1500.50")
    assert book.spread == Decimal("0.50")
    assert book.mid_price == Decimal("1500.25")
    assert book.total_bid_depth == 300
    assert book.total_ask_depth == 450
    assert not book.is_crossed
    assert not book.is_locked


def test_orderbook_snapshot_from_quote() -> None:
    now = datetime(2025, 1, 1, 9, 15, tzinfo=UTC)
    quote = Quote(
        symbol="TCS",
        timestamp=now,
        bid=Decimal("3500.00"),
        ask=Decimal("3501.00"),
        bid_size=50,
        ask_size=75,
        last_price=Decimal("3500.50"),
    )
    book = OrderBookSnapshot.from_quote(quote)
    assert book.top_bid is not None and book.top_bid.price == Decimal("3500.00")
    assert book.top_bid.quantity == 50
    assert book.top_ask is not None and book.top_ask.price == Decimal("3501.00")
    assert book.top_ask.quantity == 75


def test_orderbook_simulator_adverse_slippage_and_vwap() -> None:
    config = OrderBookSimConfig(
        slippage_bps=Decimal("10.0"),  # 10 bps
        allow_depth_walking=True,
    )
    sim = OrderBookSimulator(config)
    order_time = datetime(2025, 1, 1, 9, 15, 0, tzinfo=UTC)
    quote_time = datetime(2025, 1, 1, 9, 15, 1, tzinfo=UTC)

    # Buy order of 200 INFY
    order = Order(
        order_id="o_buy",
        symbol="INFY",
        side=Side.BUY,
        quantity=200,
        order_type=OrderType.MARKET,
        created_at=order_time,
    )

    # Level 1: 100 @ 1500.00, Level 2: 200 @ 1501.00
    book = OrderBookSnapshot.from_levels(
        symbol="INFY",
        timestamp=quote_time,
        bids=[(Decimal("1499.00"), 500)],
        asks=[(Decimal("1500.00"), 100), (Decimal("1501.00"), 200)],
    )

    result = sim.simulate_fill(order, book, current_time=quote_time)
    assert result.is_executable is True
    assert result.status == OrderStatus.FILLED
    assert result.filled_quantity == 200
    assert result.unfilled_quantity == 0

    # Allocations: 100 @ Level 1, 100 @ Level 2
    assert len(result.allocations) == 2
    # Level 1: 1500.00 + 10bps (1.50) = 1501.50
    assert result.allocations[0].effective_price == Decimal("1501.50")
    assert result.allocations[0].matched_quantity == 100
    # Level 2: 1501.00 + 10bps (1.501 -> rounded up 1.51) = 1502.51
    assert result.allocations[1].effective_price == Decimal("1502.51")
    assert result.allocations[1].matched_quantity == 100

    # Total VWAP = (100 * 1501.50 + 100 * 1502.51) / 200 = 1502.005 -> 1502.00
    assert result.vwap_price == Decimal("1502.00")
    assert result.total_slippage == Decimal("301.00")


def test_orderbook_simulator_partial_fill_against_depth() -> None:
    config = OrderBookSimConfig(slippage_bps=Decimal("5.0"), allow_depth_walking=True)
    sim = OrderBookSimulator(config)
    order_time = datetime(2025, 1, 1, 9, 15, 0, tzinfo=UTC)
    quote_time = datetime(2025, 1, 1, 9, 15, 1, tzinfo=UTC)

    # Buy order of 500 INFY (only 250 available in total depth)
    order = Order(
        order_id="o_large",
        symbol="INFY",
        side=Side.BUY,
        quantity=500,
        order_type=OrderType.MARKET,
        created_at=order_time,
    )

    book = OrderBookSnapshot.from_levels(
        symbol="INFY",
        timestamp=quote_time,
        bids=[(Decimal("1499.00"), 500)],
        asks=[(Decimal("1500.00"), 100), (Decimal("1501.00"), 150)],
    )

    result = sim.simulate_fill(order, book, current_time=quote_time)
    assert result.is_executable is True
    assert result.status == OrderStatus.PARTIALLY_FILLED
    assert result.filled_quantity == 250
    assert result.unfilled_quantity == 250


def test_orderbook_simulator_market_rule_validations() -> None:
    sim = OrderBookSimulator(
        OrderBookSimConfig(
            max_spread_pct=Decimal("0.02"),
            max_quote_age_seconds=5.0,
            tick_size=Decimal("0.05"),
            lot_size=25,
        )
    )
    now = datetime(2025, 1, 1, 9, 15, 0, tzinfo=UTC)
    later = now + timedelta(seconds=1)

    # 1. Point-in-time invariant: Quote earlier than order
    order = Order(
        order_id="o1",
        symbol="NIFTY",
        side=Side.BUY,
        quantity=25,
        order_type=OrderType.MARKET,
        created_at=later,
    )
    book_early = OrderBookSnapshot.from_levels(
        symbol="NIFTY",
        timestamp=now,  # earlier than order created_at
        bids=[(Decimal("24000.00"), 50)],
        asks=[(Decimal("24005.00"), 50)],
    )
    res_pit = sim.simulate_fill(order, book_early, current_time=later)
    assert res_pit.is_executable is False
    assert res_pit.rejection_reason == "QUOTE_NOT_LATER_THAN_ORDER_CREATION"

    # 2. Stale quote
    order_ok = Order(
        order_id="o2",
        symbol="NIFTY",
        side=Side.BUY,
        quantity=25,
        order_type=OrderType.MARKET,
        created_at=now - timedelta(seconds=10),
    )
    book_stale = OrderBookSnapshot.from_levels(
        symbol="NIFTY",
        timestamp=now - timedelta(seconds=8),
        bids=[(Decimal("24000.00"), 50)],
        asks=[(Decimal("24005.00"), 50)],
    )
    res_stale = sim.simulate_fill(order_ok, book_stale, current_time=now)
    assert res_stale.status == OrderStatus.REJECTED
    assert "STALE_QUOTE" in (res_stale.rejection_reason or "")

    # 3. Invalid Lot Size
    order_bad_lot = Order(
        order_id="o3",
        symbol="NIFTY",
        side=Side.BUY,
        quantity=30,  # Not multiple of 25
        order_type=OrderType.MARKET,
        created_at=now,
    )
    book_ok = OrderBookSnapshot.from_levels(
        symbol="NIFTY",
        timestamp=later,
        bids=[(Decimal("24000.00"), 50)],
        asks=[(Decimal("24005.00"), 50)],
    )
    res_lot = sim.simulate_fill(order_bad_lot, book_ok, current_time=later)
    assert res_lot.status == OrderStatus.REJECTED
    assert "INVALID_LOT_SIZE" in (res_lot.rejection_reason or "")

    # 4. Invalid Tick Size
    order_bad_tick = Order(
        order_id="o4",
        symbol="NIFTY",
        side=Side.BUY,
        quantity=25,
        order_type=OrderType.LIMIT,
        created_at=now,
        limit_price=Decimal("24005.03"),  # Not multiple of 0.05
    )
    res_tick = sim.simulate_fill(order_bad_tick, book_ok, current_time=later)
    assert res_tick.status == OrderStatus.REJECTED
    assert "INVALID_TICK_SIZE" in (res_tick.rejection_reason or "")

    # 5. Crossed Book
    book_crossed = OrderBookSnapshot.from_levels(
        symbol="NIFTY",
        timestamp=later,
        bids=[(Decimal("24010.00"), 50)],
        asks=[(Decimal("24000.00"), 50)],  # Ask < Bid
    )
    res_crossed = sim.simulate_fill(order_ok, book_crossed, current_time=later)
    assert res_crossed.status == OrderStatus.REJECTED
    assert "CROSSED_BOOK" in (res_crossed.rejection_reason or "")

    # 6. Wide Spread
    book_wide = OrderBookSnapshot.from_levels(
        symbol="NIFTY",
        timestamp=later,
        bids=[(Decimal("23000.00"), 50)],
        asks=[(Decimal("25000.00"), 50)],  # > 2% spread
    )
    res_wide = sim.simulate_fill(order_ok, book_wide, current_time=later)
    assert res_wide.status == OrderStatus.REJECTED
    assert "SPREAD_TOO_WIDE" in (res_wide.rejection_reason or "")

    # 7. Zero Liquidity
    book_zero = OrderBookSnapshot.from_levels(
        symbol="NIFTY",
        timestamp=later,
        bids=[(Decimal("24000.00"), 50)],
        asks=[],  # No asks
    )
    res_zero = sim.simulate_fill(order_ok, book_zero, current_time=later)
    assert res_zero.status == OrderStatus.REJECTED
    assert "ZERO_LIQUIDITY_ASK_DEPTH_EMPTY" in (res_zero.rejection_reason or "")


def test_paper_pilot_basic_buy_and_sell_lifecycle() -> None:
    engine = PaperPilotEngine(initial_cash=Decimal("1000000.00"), session_id="session_01")
    t0 = datetime(2025, 1, 1, 9, 15, 0, tzinfo=UTC)
    session_dt = date(2025, 1, 1)

    engine.start_session(session_date=session_dt, timestamp=t0)
    assert engine.session_status == SessionStatus.ACTIVE
    assert engine.cash == Decimal("1000000.00")

    # Submit Buy Proposal
    p1 = PaperProposal(
        proposal_id="prop_01",
        symbol="INFY",
        side=Side.BUY,
        quantity=100,
        order_type=OrderType.MARKET,
        decision_at=t0,
    )
    order_sub, decision = engine.submit_proposal(p1)
    assert decision.approved is True
    assert order_sub.status == OrderStatus.SUBMITTED

    # Process Quote later than decision
    t1 = t0 + timedelta(seconds=1)
    quote1 = Quote(
        symbol="INFY",
        timestamp=t1,
        bid=Decimal("1500.00"),
        ask=Decimal("1500.50"),
        bid_size=200,
        ask_size=200,
        last_price=Decimal("1500.25"),
    )
    fills = engine.process_quote(quote1)
    assert len(fills) == 1
    assert fills[0].quantity == 100
    assert fills[0].symbol == "INFY"
    # Buy fill price = 1500.50 + 5bps slippage (0.76) = 1501.26
    assert fills[0].price == Decimal("1501.26")
    assert engine.positions["INFY"].quantity == 100
    assert engine.orders[order_sub.order_id].status == OrderStatus.FILLED
    assert engine.ledger.reconcile() is True

    # Submit Sell Proposal to exit
    t2 = t1 + timedelta(minutes=5)
    p2 = PaperProposal(
        proposal_id="prop_02",
        symbol="INFY",
        side=Side.SELL,
        quantity=100,
        order_type=OrderType.MARKET,
        decision_at=t2,
    )
    order_sell, dec_sell = engine.submit_proposal(p2)
    assert dec_sell.approved is True

    t3 = t2 + timedelta(seconds=1)
    quote2 = Quote(
        symbol="INFY",
        timestamp=t3,
        bid=Decimal("1550.00"),
        ask=Decimal("1550.50"),
        bid_size=200,
        ask_size=200,
        last_price=Decimal("1550.25"),
    )
    fills_sell = engine.process_quote(quote2)
    assert len(fills_sell) == 1
    assert fills_sell[0].quantity == 100
    # Sell fill price = 1550.00 - 5bps slippage (0.78) = 1549.22
    assert fills_sell[0].price == Decimal("1549.22")
    assert "INFY" not in engine.positions  # Fully closed
    assert engine.orders[order_sell.order_id].status == OrderStatus.FILLED

    # Realized P&L check: (1549.22 - 1501.26)*100 - sell_fee - buy_fee
    assert engine.ledger.realized_pnl > Decimal("4000.00")

    # Close session and verify independent reconciliation
    t_end = datetime(2025, 1, 1, 15, 30, 0, tzinfo=UTC)
    report = engine.end_session(timestamp=t_end, close_prices={"INFY": Decimal("1550.00")})
    assert report.reconciled is True
    assert report.discrepancy_paisa == Decimal("0.00")
    assert report.orders_submitted == 2
    assert report.orders_filled == 2
    assert report.orders_cancelled == 0
    assert report.open_orders_remaining == 0


def test_paper_pilot_sequential_partial_fills() -> None:
    risk_gov = PreTradeRiskGovernor(
        limits=RiskLimits(max_position_weight=1.0, min_cash_buffer_pct=0.0)
    )
    engine = PaperPilotEngine(
        initial_cash=Decimal("2000000.00"),
        risk_governor=risk_gov,
        session_id="session_partial",
    )
    t0 = datetime(2025, 1, 1, 9, 15, 0, tzinfo=UTC)
    engine.start_session(session_date=date(2025, 1, 1), timestamp=t0)

    # Order 300 shares
    p = PaperProposal(
        proposal_id="prop_large",
        symbol="TCS",
        side=Side.BUY,
        quantity=300,
        order_type=OrderType.MARKET,
        decision_at=t0,
    )
    order, _ = engine.submit_proposal(p)

    # Quote 1: only 100 available in depth
    t1 = t0 + timedelta(seconds=1)
    book1 = OrderBookSnapshot.from_levels(
        symbol="TCS",
        timestamp=t1,
        bids=[(Decimal("3499.00"), 100)],
        asks=[(Decimal("3500.00"), 100)],
    )
    fills1 = engine.process_quote(book1)
    assert len(fills1) == 1
    assert fills1[0].quantity == 100
    assert engine.orders[order.order_id].status == OrderStatus.PARTIALLY_FILLED
    assert engine.positions["TCS"].quantity == 100

    # Quote 2: 150 available in depth
    t2 = t1 + timedelta(seconds=2)
    book2 = OrderBookSnapshot.from_levels(
        symbol="TCS",
        timestamp=t2,
        bids=[(Decimal("3500.00"), 100)],
        asks=[(Decimal("3501.00"), 150)],
    )
    fills2 = engine.process_quote(book2)
    assert len(fills2) == 1
    assert fills2[0].quantity == 150
    assert engine.orders[order.order_id].status == OrderStatus.PARTIALLY_FILLED
    assert engine.positions["TCS"].quantity == 250

    # Quote 3: 100 available in depth -> fills remaining 50
    t3 = t2 + timedelta(seconds=2)
    book3 = OrderBookSnapshot.from_levels(
        symbol="TCS",
        timestamp=t3,
        bids=[(Decimal("3501.00"), 100)],
        asks=[(Decimal("3502.00"), 100)],
    )
    fills3 = engine.process_quote(book3)
    assert len(fills3) == 1
    assert fills3[0].quantity == 50
    assert engine.orders[order.order_id].status == OrderStatus.FILLED
    assert engine.positions["TCS"].quantity == 300

    # Reconcile session
    report = engine.end_session(timestamp=t3 + timedelta(hours=1))
    assert report.reconciled is True
    assert report.orders_filled == 1
    assert report.orders_partially_filled == 0
    assert report.total_fills_count == 3


def test_paper_pilot_session_end_cancellation_of_unfilled_remainder() -> None:
    engine = PaperPilotEngine(initial_cash=Decimal("1000000.00"), session_id="session_cancel")
    t0 = datetime(2025, 1, 1, 9, 15, 0, tzinfo=UTC)
    engine.start_session(session_date=date(2025, 1, 1), timestamp=t0)

    # Order 80 shares. Sized to pass pre-trade risk once priced: 80 * 2501 = 200,080, which is
    # 20.0% of equity against max_position_weight 0.25. This previously ordered 500 shares
    # (1,250,500 = 125% of equity, more than the account's entire cash) and still reached the
    # book, because an unpriced MARKET order skipped risk entirely (S10-B1). The order was
    # resized when that bypass was closed; the behaviour under test — partial fill, then
    # cancellation of the unfilled remainder at session end — is unchanged.
    p = PaperProposal(
        proposal_id="prop_cancel_test",
        symbol="RELIANCE",
        side=Side.BUY,
        quantity=80,
        order_type=OrderType.MARKET,
        decision_at=t0,
    )
    order, _ = engine.submit_proposal(p)

    # Ask depth is only 30, so 30 fill and 50 remain
    t1 = t0 + timedelta(seconds=1)
    book1 = OrderBookSnapshot.from_levels(
        symbol="RELIANCE",
        timestamp=t1,
        bids=[(Decimal("2500.00"), 100)],
        asks=[(Decimal("2501.00"), 30)],
    )
    engine.process_quote(book1)
    assert engine.orders[order.order_id].status == OrderStatus.PARTIALLY_FILLED
    assert engine.positions["RELIANCE"].quantity == 30

    # End session with 50 remaining unfilled
    t_end = datetime(2025, 1, 1, 15, 30, 0, tzinfo=UTC)
    report = engine.end_session(timestamp=t_end, close_prices={"RELIANCE": Decimal("2510.00")})

    assert report.reconciled is True
    # Order transitioned to CANCELLED cleanly
    assert engine.orders[order.order_id].status == OrderStatus.CANCELLED
    assert report.orders_cancelled == 1
    assert report.open_orders_remaining == 0
    # Position remains 30
    assert report.open_positions["RELIANCE"] == 30


def test_paper_pilot_idempotency_and_duplicate_handling() -> None:
    engine = PaperPilotEngine(initial_cash=Decimal("1000000.00"), session_id="session_idempotent")
    t0 = datetime(2025, 1, 1, 9, 15, 0, tzinfo=UTC)
    engine.start_session(session_date=date(2025, 1, 1), timestamp=t0)

    p1 = PaperProposal(
        proposal_id="prop_idem_1",
        symbol="INFY",
        side=Side.BUY,
        quantity=50,
        order_type=OrderType.MARKET,
        decision_at=t0,
    )

    # First submission
    order1, dec1 = engine.submit_proposal(p1)
    assert dec1.approved is True
    assert order1.status == OrderStatus.SUBMITTED

    # Duplicate submission with identical fields -> Returns cached result, no extra orders
    order2, dec2 = engine.submit_proposal(p1)
    assert order2.order_id == order1.order_id
    assert dec2.reason == dec1.reason
    assert len(engine.orders) == 1

    # Conflicting submission with same ID but different quantity -> Fails closed
    p_conflict = PaperProposal(
        proposal_id="prop_idem_1",
        symbol="INFY",
        side=Side.BUY,
        quantity=100,  # Different!
        order_type=OrderType.MARKET,
        decision_at=t0,
    )
    with pytest.raises(ValueError, match="Idempotency conflict"):
        engine.submit_proposal(p_conflict)

    # Replayed out-of-order quote does not double-post
    t1 = t0 + timedelta(seconds=1)
    quote1 = Quote(
        symbol="INFY",
        timestamp=t1,
        bid=Decimal("1500.00"),
        ask=Decimal("1500.50"),
        bid_size=100,
        ask_size=100,
    )
    fills1 = engine.process_quote(quote1)
    assert len(fills1) == 1
    cash_after_fill = engine.cash

    # Replay same quote again
    fills_replayed = engine.process_quote(quote1)
    assert len(fills_replayed) == 0
    assert engine.cash == cash_after_fill  # Zero double posting


def test_paper_pilot_risk_gating_and_kill_switch() -> None:
    # Set low cash buffer to trigger risk limits
    risk_limits = RiskLimits(
        max_position_weight=0.20,  # 20% max in one stock
        min_cash_buffer_pct=0.05,
    )
    gov = PreTradeRiskGovernor(limits=risk_limits)
    engine = PaperPilotEngine(
        initial_cash=Decimal("100000.00"),
        risk_governor=gov,
        session_id="session_risk",
    )
    t0 = datetime(2025, 1, 1, 9, 15, 0, tzinfo=UTC)
    engine.start_session(session_date=date(2025, 1, 1), timestamp=t0)

    # 1. Position weight violation: Try to buy 50 TCS @ 3500 = ₹1,75,000 > 20% of 100k
    p_oversize = PaperProposal(
        proposal_id="prop_oversize",
        symbol="TCS",
        side=Side.BUY,
        quantity=50,
        order_type=OrderType.LIMIT,
        limit_price=Decimal("3500.00"),
        decision_at=t0,
    )
    order_rej, dec_rej = engine.submit_proposal(p_oversize)
    assert dec_rej.approved is False
    assert "POSITION_WEIGHT_LIMIT_EXCEEDED" in dec_rej.reason
    assert order_rej.status == OrderStatus.REJECTED
    assert len(engine.fills) == 0
    assert engine.cash == Decimal("100000.00")

    # 2. Kill switch halt
    engine.halt_session(reason="MONITORING_ALERT_DRAWDOWN", timestamp=t0 + timedelta(minutes=10))
    assert engine.session_status == SessionStatus.HALTED

    # Any proposal during halt is rejected
    p_during_halt = PaperProposal(
        proposal_id="prop_halted",
        symbol="INFY",
        side=Side.BUY,
        quantity=10,
        order_type=OrderType.MARKET,
        decision_at=t0 + timedelta(minutes=11),
    )
    order_halt, dec_halt = engine.submit_proposal(p_during_halt)
    assert dec_halt.approved is False
    assert order_halt.status == OrderStatus.REJECTED


def test_paper_pilot_options_derivatives_execution() -> None:
    risk_gov = PreTradeRiskGovernor(limits=RiskLimits(allow_naked_short=True))
    sim_cfg = OrderBookSimConfig(lot_size=25, tick_size=Decimal("0.05"))
    engine = PaperPilotEngine(
        initial_cash=Decimal("500000.00"),
        risk_governor=risk_gov,
        sim_config=sim_cfg,
        allow_short=True,
        session_id="session_options",
    )
    t0 = datetime(2025, 1, 1, 9, 15, 0, tzinfo=UTC)
    engine.start_session(session_date=date(2025, 1, 1), timestamp=t0)

    # Short 50 contracts (2 lots of 25) of NIFTY 24500 CE
    p_opt = PaperProposal(
        proposal_id="prop_opt_short",
        symbol="NIFTY24500CE",
        side=Side.SELL,
        quantity=50,
        order_type=OrderType.MARKET,
        decision_at=t0,
    )
    order_opt, dec_opt = engine.submit_proposal(p_opt)
    assert dec_opt.approved is True

    t1 = t0 + timedelta(seconds=1)
    quote_opt = Quote(
        symbol="NIFTY24500CE",
        timestamp=t1,
        bid=Decimal("200.00"),
        ask=Decimal("200.50"),
        bid_size=100,
        ask_size=100,
        last_price=Decimal("200.25"),
    )
    fills = engine.process_quote(quote_opt)
    assert len(fills) == 1
    assert fills[0].fee >= Decimal("20.00")  # Options flat brokerage
    assert engine.positions["NIFTY24500CE"].quantity == -50
    assert engine.cash > Decimal("500000.00")  # Premium collected minus fees
    assert engine.ledger.reconcile() is True


def test_paper_pilot_deterministic_multi_session_campaign_and_replay() -> None:
    # Run a 2-session campaign and prove deterministic replay
    def run_campaign() -> tuple[Decimal, int, int]:
        eng = PaperPilotEngine(initial_cash=Decimal("1000000.00"), session_id="camp_sess")
        # Session 1
        t1_start = datetime(2025, 1, 1, 9, 15, tzinfo=UTC)
        eng.start_session(session_date=date(2025, 1, 1), timestamp=t1_start)

        p1 = PaperProposal(
            proposal_id="c1_p1",
            symbol="INFY",
            side=Side.BUY,
            quantity=100,
            order_type=OrderType.MARKET,
            decision_at=t1_start,
        )
        eng.submit_proposal(p1)
        eng.process_quote(
            Quote(
                symbol="INFY",
                timestamp=t1_start + timedelta(seconds=1),
                bid=Decimal("1500.00"),
                ask=Decimal("1500.50"),
                bid_size=500,
                ask_size=500,
            )
        )
        rep1 = eng.end_session(
            timestamp=t1_start + timedelta(hours=6), close_prices={"INFY": Decimal("1520.00")}
        )
        assert rep1.reconciled is True

        # Session 2
        t2_start = datetime(2025, 1, 2, 9, 15, tzinfo=UTC)
        eng.start_session(session_date=date(2025, 1, 2), timestamp=t2_start)
        p2 = PaperProposal(
            proposal_id="c1_p2",
            symbol="INFY",
            side=Side.SELL,
            quantity=100,
            order_type=OrderType.MARKET,
            decision_at=t2_start,
        )
        eng.submit_proposal(p2)
        eng.process_quote(
            Quote(
                symbol="INFY",
                timestamp=t2_start + timedelta(seconds=1),
                bid=Decimal("1530.00"),
                ask=Decimal("1530.50"),
                bid_size=500,
                ask_size=500,
            )
        )
        rep2 = eng.end_session(
            timestamp=t2_start + timedelta(hours=6), close_prices={"INFY": Decimal("1530.00")}
        )
        assert rep2.reconciled is True

        return eng.cash, len(eng.fills), len(eng.audit_log)

    res1 = run_campaign()
    res2 = run_campaign()

    assert res1 == res2
    assert res1[0] > Decimal("1000000.00")  # Profit made and identical to the paisa


def test_limit_order_execution_boundaries() -> None:
    engine = PaperPilotEngine(initial_cash=Decimal("1000000.00"), session_id="session_limit")
    t0 = datetime(2025, 1, 1, 9, 15, 0, tzinfo=UTC)
    engine.start_session(session_date=date(2025, 1, 1), timestamp=t0)

    # 1. Limit Buy below ask: Limit price 1495.00, Ask is 1500.00 -> Should NOT execute
    p_low = PaperProposal(
        proposal_id="p_limit_low",
        symbol="INFY",
        side=Side.BUY,
        quantity=50,
        order_type=OrderType.LIMIT,
        limit_price=Decimal("1495.00"),
        decision_at=t0,
    )
    order_low, dec_low = engine.submit_proposal(p_low)
    assert dec_low.approved is True

    t1 = t0 + timedelta(seconds=1)
    book1 = OrderBookSnapshot.from_levels(
        symbol="INFY",
        timestamp=t1,
        bids=[(Decimal("1499.00"), 100)],
        asks=[(Decimal("1500.00"), 100)],
    )
    fills1 = engine.process_quote(book1)
    assert len(fills1) == 0
    assert engine.orders[order_low.order_id].status == OrderStatus.SUBMITTED

    # 2. Market moves down: Ask drops to 1495.00 -> Should execute now!
    t2 = t1 + timedelta(seconds=2)
    book2 = OrderBookSnapshot.from_levels(
        symbol="INFY",
        timestamp=t2,
        bids=[(Decimal("1494.50"), 100)],
        asks=[(Decimal("1495.00"), 100)],
    )
    fills2 = engine.process_quote(book2)
    assert len(fills2) == 1
    assert fills2[0].quantity == 50
    assert engine.orders[order_low.order_id].status == OrderStatus.FILLED


def test_paper_pilot_session_halt_and_recovery() -> None:
    engine = PaperPilotEngine(initial_cash=Decimal("1000000.00"), session_id="session_halt_rec")
    t0 = datetime(2025, 1, 1, 9, 15, 0, tzinfo=UTC)
    engine.start_session(session_date=date(2025, 1, 1), timestamp=t0)

    # Submit an order
    p1 = PaperProposal(
        proposal_id="p_halt_1",
        symbol="INFY",
        side=Side.BUY,
        quantity=50,
        order_type=OrderType.MARKET,
        decision_at=t0,
    )
    order1, _ = engine.submit_proposal(p1)
    assert order1.status == OrderStatus.SUBMITTED

    # Trigger halt
    t_halt = t0 + timedelta(seconds=5)
    engine.halt_session(reason="CIRCUIT_BREAKER", timestamp=t_halt)
    assert engine.session_status == SessionStatus.HALTED
    # Open order was cancelled automatically
    assert engine.orders[order1.order_id].status == OrderStatus.CANCELLED

    # Resume session
    t_resume = t_halt + timedelta(minutes=15)
    engine.resume_session(timestamp=t_resume)
    assert engine.session_status == SessionStatus.ACTIVE

    # New order can now be submitted
    p2 = PaperProposal(
        proposal_id="p_halt_2",
        symbol="INFY",
        side=Side.BUY,
        quantity=25,
        order_type=OrderType.MARKET,
        decision_at=t_resume,
    )
    order2, dec2 = engine.submit_proposal(p2)
    assert dec2.approved is True
    assert order2.status == OrderStatus.SUBMITTED


def test_paper_pilot_mark_to_market_unrealized_pnl_reconciliation() -> None:
    engine = PaperPilotEngine(initial_cash=Decimal("1000000.00"), session_id="session_mtm")
    t0 = datetime(2025, 1, 1, 9, 15, 0, tzinfo=UTC)
    engine.start_session(session_date=date(2025, 1, 1), timestamp=t0)

    # Buy INFY @ 1500
    p = PaperProposal(
        proposal_id="p_mtm_1",
        symbol="INFY",
        side=Side.BUY,
        quantity=100,
        order_type=OrderType.MARKET,
        decision_at=t0,
    )
    engine.submit_proposal(p)
    engine.process_quote(
        Quote(
            symbol="INFY",
            timestamp=t0 + timedelta(seconds=1),
            bid=Decimal("1500.00"),
            ask=Decimal("1500.00"),
            bid_size=100,
            ask_size=100,
        )
    )

    # Close session with closing price of ₹1600 (+100 gain per share)
    t_close = datetime(2025, 1, 1, 15, 30, 0, tzinfo=UTC)
    report = engine.end_session(
        timestamp=t_close,
        close_prices={"INFY": Decimal("1600.00")},
    )

    assert report.reconciled is True
    assert report.open_positions["INFY"] == 100
    # Unrealized PnL = (1600.00 - 1500.75)*100 = ~9925
    assert report.total_unrealized_pnl > Decimal("9000.00")
    assert report.total_equity == report.final_cash + (Decimal("1600.00") * Decimal(100))


def test_adversarial_zero_or_negative_inputs() -> None:
    now = datetime(2025, 1, 1, 9, 15, tzinfo=UTC)

    # Negative proposal quantity
    with pytest.raises(ValueError, match="quantity must be positive"):
        PaperProposal(
            proposal_id="bad_qty",
            symbol="INFY",
            side=Side.BUY,
            quantity=-10,
            order_type=OrderType.MARKET,
            decision_at=now,
        )

    # Empty proposal ID
    with pytest.raises(ValueError, match="proposal_id cannot be empty"):
        PaperProposal(
            proposal_id="",
            symbol="INFY",
            side=Side.BUY,
            quantity=10,
            order_type=OrderType.MARKET,
            decision_at=now,
        )

    # Zero limit price
    with pytest.raises(ValueError, match="Limit price must be positive"):
        PaperProposal(
            proposal_id="bad_price",
            symbol="INFY",
            side=Side.BUY,
            quantity=10,
            order_type=OrderType.LIMIT,
            limit_price=Decimal("0.00"),
            decision_at=now,
        )


def test_independent_ledger_reconciliation_tamper_detection() -> None:
    engine = PaperPilotEngine(initial_cash=Decimal("500000.00"), session_id="session_tamper")
    t0 = datetime(2025, 1, 1, 9, 15, 0, tzinfo=UTC)
    engine.start_session(session_date=date(2025, 1, 1), timestamp=t0)

    # Deliberately mutate cash in ledger
    engine.ledger._cash = Decimal("499999.00")  # ₹1 discrepancy

    with pytest.raises(RuntimeError, match="Ledger reconciliation mismatch"):
        engine.ledger.reconcile()


# -------------------------------------------------------------------------
# Ring 5: S10-B1 regression — staged orders must face risk before they fill
# -------------------------------------------------------------------------


def test_unpriced_market_order_faces_risk_before_it_fills() -> None:
    """S10-B1: an unpriced MARKET order skipped evaluate_order entirely and was stamped approved.

    Position weight cannot be computed without a price, so the check was skipped rather than
    deferred. The order then filled at 90% concentration against a 25% limit.
    """
    engine = PaperPilotEngine(initial_cash=Decimal("1000000.00"), session_id="session_s10b1")
    t0 = datetime(2025, 1, 1, 9, 15, 0, tzinfo=UTC)
    engine.start_session(session_date=date(2025, 1, 1), timestamp=t0)

    # Fresh session: no cached price for INFY, and a MARKET order carries no limit price,
    # so the order value is unknowable at submission time.
    oversize = PaperProposal(
        proposal_id="prop_s10b1",
        symbol="INFY",
        side=Side.BUY,
        quantity=9000,
        order_type=OrderType.MARKET,
        decision_at=t0,
    )
    order, decision = engine.submit_proposal(oversize)
    assert decision.approved is True, "submission is staged, not yet judged on value"
    assert order.status == OrderStatus.SUBMITTED

    # The quote supplies the missing price. 9000 * ~100 = ~900,000 of 1,000,000 equity = ~90%,
    # far beyond max_position_weight 0.25, so the deferred check must now refuse it.
    t1 = t0 + timedelta(seconds=1)
    fills = engine.process_quote(
        Quote(
            symbol="INFY",
            timestamp=t1,
            bid=Decimal("100.00"),
            ask=Decimal("100.05"),
            bid_size=20000,
            ask_size=20000,
            last_price=Decimal("100.02"),
        )
    )

    assert fills == [], "a staged order must not fill without passing pre-trade risk"
    final_order = engine.orders[order.order_id]
    assert final_order.status == OrderStatus.REJECTED
    assert "POSITION_WEIGHT" in (final_order.rejection_reason or ""), (
        f"rejection must name the limit that refused it; got {final_order.rejection_reason!r}"
    )
    assert engine.positions.get("INFY") is None
