"""A rebalance brings held names that stay selected back to equal weight.

The entry loop only ever bought names the book did not hold, so a name that stayed in the selection
was never trimmed or topped up. Its weight drifted for as long as it stayed selected, and because a
book that still contained the selection submitted no orders, `evaluate_order` -- the only place the
30% per-name limit is enforced -- never ran: a book 90% in one name passed every check (R6-08). The
measured strategy equal-weights every selected name at every rebalance. On 2026-09-21 the flagship
carried 20 names through its rebalance at whatever weight they had drifted to.

`reweight_orders` is that rule in integer shares, with a tolerance band so it does not pay statutory
costs to move a few hundred rupees. These tests pin what it trades, what it refuses to trade, and
that it never doubles an order still open or spends cash it does not have.
"""

from __future__ import annotations

import importlib.util
import os
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from typing import Any
from unittest import mock

from quant_system.core.domain import Fill, OrderStatus, OrderType, Quote, Side
from quant_system.execution.orderbook_sim import OrderBookSnapshot
from quant_system.execution.paper_pilot import PaperPilotEngine, PaperProposal
from quant_system.risk.checks import RiskLimits
from quant_system.risk.governor import PreTradeRiskGovernor


def _runner() -> Any:
    spec = importlib.util.spec_from_file_location(
        "_rps_reweight",
        Path(__file__).resolve().parent.parent / "scripts/run_paper_pilot_session.py",
    )
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    # The runner loads `.env` into `os.environ` at import time; keep that out of the rest of the
    # suite, exactly as `test_paper_pilot_carried_session.py` does.
    with mock.patch.dict(os.environ, os.environ.copy(), clear=True):
        spec.loader.exec_module(module)
    return module


RUNNER = _runner()


@dataclass(frozen=True)
class _Position:
    quantity: int
    average_price: Decimal = Decimal("1.00")


def _orders(**overrides: Any) -> list[tuple[str, Side, int]]:
    """Rs 10,000 per name at Rs 100 a share is a 100-share target; the band is Rs 1,000."""
    arguments: dict[str, Any] = {
        "selected": ["ALPHA"],
        "positions": {"ALPHA": _Position(100)},
        "marks": {"ALPHA": Decimal("100.00")},
        "allocation": Decimal("10000.00"),
        "available_cash": Decimal("1000000.00"),
        "open_order_symbols": set(),
    }
    arguments.update(overrides)
    orders: list[tuple[str, Side, int]] = RUNNER.reweight_orders(**arguments)
    return orders


def test_a_name_already_at_its_target_is_left_alone() -> None:
    assert _orders() == []


def test_drift_inside_the_band_is_not_worth_paying_to_correct() -> None:
    # 105 and 95 shares are Rs 500 from target; 110 is exactly the Rs 1,000 band.
    for held in (105, 95, 110, 90):
        assert _orders(positions={"ALPHA": _Position(held)}) == [], held


def test_an_overweight_name_is_trimmed_to_its_target() -> None:
    assert _orders(positions={"ALPHA": _Position(150)}) == [("ALPHA", Side.SELL, 50)]


def test_an_underweight_name_is_topped_up_to_its_target() -> None:
    assert _orders(positions={"ALPHA": _Position(50)}) == [("ALPHA", Side.BUY, 50)]


def test_the_book_that_was_ninety_percent_one_name_is_brought_back() -> None:
    """R6-08: every check passed while one name held 90% of the book against a 30% limit."""
    orders = _orders(
        selected=["BIG", "MID", "SMALL"],
        positions={"BIG": _Position(900), "MID": _Position(50), "SMALL": _Position(50)},
        marks={sym: Decimal("100.00") for sym in ("BIG", "MID", "SMALL")},
        allocation=Decimal("30000.00"),
        available_cash=Decimal("0.00"),
    )
    # BIG is trimmed from 900 to its 300-share target at once. MID and SMALL need topping up and the
    # book has no cash yet, so they wait for the trim to fill and are sized on a later step.
    assert orders == [("BIG", Side.SELL, 600)]


def test_a_top_up_is_capped_by_the_cash_it_can_pay_for() -> None:
    # 95% of Rs 2,000 buys 19 shares, the same buffer the entry loop keeps.
    orders = _orders(positions={"ALPHA": _Position(50)}, available_cash=Decimal("2000.00"))
    assert orders == [("ALPHA", Side.BUY, 19)]


def test_top_ups_share_one_cash_budget_in_rank_order() -> None:
    """The cash does not move until a fill, so two top-ups must not both spend it."""
    orders = _orders(
        selected=["FIRST", "SECOND"],
        positions={"FIRST": _Position(50), "SECOND": _Position(50)},
        marks={"FIRST": Decimal("100.00"), "SECOND": Decimal("100.00")},
        available_cash=Decimal("6000.00"),
    )
    # 95% of Rs 6,000 is Rs 5,700: FIRST's 50 shares take Rs 5,000, SECOND gets the 7 left.
    assert orders == [("FIRST", Side.BUY, 50), ("SECOND", Side.BUY, 7)]


def test_a_trim_is_never_capped_by_cash() -> None:
    orders = _orders(positions={"ALPHA": _Position(150)}, available_cash=Decimal("0.00"))
    assert orders == [("ALPHA", Side.SELL, 50)]


def test_a_name_with_an_order_still_open_is_never_doubled() -> None:
    """Orders fill on the next step's quote; re-sizing before then would place the trade twice."""
    assert _orders(positions={"ALPHA": _Position(150)}, open_order_symbols={"ALPHA"}) == []
    assert _orders(positions={"ALPHA": _Position(50)}, open_order_symbols={"ALPHA"}) == []


def test_a_name_the_book_does_not_hold_is_left_to_the_entry_loop() -> None:
    assert _orders(positions={}) == []


def test_a_held_name_no_longer_selected_is_left_to_the_exit_loop() -> None:
    orders = _orders(
        selected=["ALPHA"],
        positions={"ALPHA": _Position(100), "GONE": _Position(500)},
        marks={"ALPHA": Decimal("100.00"), "GONE": Decimal("100.00")},
    )
    assert orders == []


def test_a_name_without_a_mark_is_not_sized_against_an_invented_price() -> None:
    assert _orders(positions={"ALPHA": _Position(150)}, marks={}) == []
    assert _orders(positions={"ALPHA": _Position(150)}, marks={"ALPHA": Decimal("0")}) == []


def test_a_target_under_one_share_never_sells_a_selected_name_to_zero() -> None:
    """At Rs 12,000 a share against a Rs 10,000 allocation, floor sizing says zero shares.

    The entry rule skips such a name. Selling a held, still-selected name to nothing would execute
    an exit the screen never made, so it keeps its one share.
    """
    orders = _orders(positions={"ALPHA": _Position(1)}, marks={"ALPHA": Decimal("12000.00")})
    assert orders == []


# --------------------------------------------------------------------------------------------
# The same rule wired to a real engine: what is in flight is read from the engine itself.
# --------------------------------------------------------------------------------------------

T0 = datetime(2026, 10, 7, 9, 20, tzinfo=UTC)


def _engine_holding(
    cash: str = "1000000.00", permissive: bool = False, **held: int
) -> PaperPilotEngine:
    """An engine that carried `held` shares of each name in at Rs 100, then opened the session.

    `permissive` lifts the per-name weight limit and the cash buffer, for a test about what an
    open order reserves rather than about whether the risk governor would admit it.
    """
    governor = (
        PreTradeRiskGovernor(limits=RiskLimits(max_position_weight=1.0, min_cash_buffer_pct=0.0))
        if permissive
        else None
    )
    engine = PaperPilotEngine(
        initial_cash=Decimal(cash), risk_governor=governor, session_id="reweight_test"
    )
    engine.carry_in_positions(
        [
            Fill(
                fill_id=f"carry_{symbol}",
                order_id=f"carry_order_{symbol}",
                symbol=symbol,
                side=Side.BUY,
                quantity=quantity,
                price=Decimal("100.00"),
                fee=Decimal("0.00"),
                timestamp=T0 - timedelta(days=1),
            )
            for symbol, quantity in held.items()
        ]
    )
    engine.start_session(session_date=T0.date(), timestamp=T0)
    return engine


def _quote(symbol: str, seconds: int, size: int = 100000) -> Quote:
    return Quote(
        symbol=symbol,
        timestamp=T0 + timedelta(seconds=seconds),
        bid=Decimal("99.95"),
        ask=Decimal("100.05"),
        bid_size=size,
        ask_size=size,
        last_price=Decimal("100.00"),
    )


def _submit(
    engine: PaperPilotEngine, step: int = 1, **overrides: Any
) -> list[tuple[str, Side, int]]:
    """Plan through the runner, then submit the way its session loop does."""
    arguments: dict[str, Any] = {
        "selected": ["ALPHA"],
        "marks": {"ALPHA": Decimal("100.00"), "BETA": Decimal("100.00")},
        "allocation": Decimal("10000.00"),
    }
    arguments.update(overrides)
    planned: list[tuple[str, Side, int]] = RUNNER.reweight_plan(engine, **arguments)
    for symbol, side, quantity in planned:
        _order, decision = engine.submit_proposal(
            PaperProposal(
                proposal_id=f"prop_test_{step}_{symbol}_{'TOPUP' if side is Side.BUY else 'TRIM'}",
                symbol=symbol,
                side=side,
                quantity=quantity,
                order_type=OrderType.MARKET,
                decision_at=T0 + timedelta(seconds=step),
                strategy_name="Mizan_Alpha_Reweight",
            )
        )
        assert decision.approved, decision.reason
    return planned


def test_an_overweight_carried_name_is_trimmed_to_target_by_a_real_fill() -> None:
    engine = _engine_holding(ALPHA=150)

    assert _submit(engine) == [("ALPHA", Side.SELL, 50)]
    engine.process_quote(_quote("ALPHA", 2))

    assert engine.positions["ALPHA"].quantity == 100


def test_a_second_step_before_the_fill_places_nothing() -> None:
    """The order from step 1 is still open at step 2; sizing again would sell 100, not 50."""
    engine = _engine_holding(ALPHA=150)
    _submit(engine, step=1)

    assert _submit(engine, step=2) == []


def test_once_filled_the_name_is_at_target_and_left_alone() -> None:
    engine = _engine_holding(ALPHA=150)
    _submit(engine, step=1)
    engine.process_quote(_quote("ALPHA", 2))

    assert _submit(engine, step=3) == []


def test_cash_promised_to_an_open_buy_is_not_spent_twice() -> None:
    """Rs 5,000 of cash with a Rs 4,000 buy still open leaves Rs 1,000 for the top-up, not Rs 5,000."""
    engine = _engine_holding(cash="10000.00", ALPHA=50)
    engine.submit_proposal(
        PaperProposal(
            proposal_id="prop_entry_BETA",
            symbol="BETA",
            side=Side.BUY,
            quantity=40,
            order_type=OrderType.MARKET,
            decision_at=T0,
        )
    )

    # 95% of Rs 1,000 buys 9 shares at Rs 100. Without the subtraction it would have bought 47.
    assert _submit(engine) == [("ALPHA", Side.BUY, 9)]


def test_a_partly_filled_buy_reserves_only_what_it_has_still_to_buy() -> None:
    engine = _engine_holding(cash="10000.00", permissive=True, ALPHA=50)
    # Both names are quoted before anything is submitted, as the runner does on every step. The
    # governor refuses a buy while any held name is unpriced, and an order submitted before its own
    # name has a quote is only risk-checked at its first fill.
    engine.process_quote(_quote("ALPHA", 1))
    engine.process_quote(_quote("BETA", 1))
    order, decision = engine.submit_proposal(
        PaperProposal(
            proposal_id="prop_entry_BETA",
            symbol="BETA",
            side=Side.BUY,
            quantity=40,
            order_type=OrderType.MARKET,
            decision_at=T0 + timedelta(seconds=2),
        )
    )
    assert decision.approved, decision.reason
    # Ten shares of depth against a 40-share order: the engine fills ten and keeps 30 open.
    thin = OrderBookSnapshot.from_levels(
        symbol="BETA",
        timestamp=T0 + timedelta(seconds=3),
        bids=[(Decimal("99.95"), 10)],
        asks=[(Decimal("100.05"), 10)],
    )
    fills = engine.process_quote(thin)
    assert sum(fill.quantity for fill in fills) == 10
    assert engine.orders[order.order_id].status is OrderStatus.PARTIALLY_FILLED

    # 30 shares are still to buy: about Rs 3,000 promised against about Rs 3,998 of cash. Counting
    # the full 40 would promise Rs 4,000 -- more than the cash -- and allow no top-up at all.
    assert _submit(engine, step=4) == [("ALPHA", Side.BUY, 9)]
