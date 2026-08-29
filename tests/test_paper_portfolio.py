"""Tests for the paper portfolio that persists between sessions.

The behaviour under guard: before this, every weekday built a fresh engine from `initial_cash`,
bought ~55 names at the open and closed them at 15:30 - paying a full round trip daily by
construction, and rebalancing far more often than the horizon the model was measured at.

Two properties carry the weight here. Carrying positions into a fresh ledger must reconstruct cash
*exactly*, or the portfolio drifts a little every session; and corrupt state must refuse to load
rather than silently reset, because an unattended weekday schedule has nobody to notice.
"""

from __future__ import annotations

import json
from datetime import UTC, date, datetime
from decimal import Decimal

import pytest

from quant_system.core.domain import Fill, Side
from quant_system.core.ledger import DecimalLedger
from quant_system.execution.paper_portfolio import (
    PORTFOLIO_SCHEMA_VERSION,
    PaperPortfolioError,
    PaperPortfolioState,
    PortfolioHolding,
    load_portfolio,
    save_portfolio,
    state_from_ledger,
)

AT = datetime(2026, 8, 31, 9, 15, tzinfo=UTC)


def _state(**overrides) -> PaperPortfolioState:
    base = {
        "cash": Decimal("93570.50"),
        "holdings": {
            "INFY": PortfolioHolding("INFY", 98, Decimal("1542.59"), date(2026, 8, 17)),
            "TCS": PortfolioHolding("TCS", 41, Decimal("3553.98"), date(2026, 8, 17)),
        },
        "realized_pnl": Decimal("1240.00"),
        "total_fees": Decimal("828.12"),
        "sessions_completed": 4,
        "sessions_since_rebalance": 4,
    }
    base.update(overrides)
    return PaperPortfolioState(**base)


# --------------------------------------------------------------------------------------------
# Carrying positions into a fresh ledger.
# --------------------------------------------------------------------------------------------


def test_replaying_carried_positions_reconstructs_cash_exactly() -> None:
    """Any drift here compounds every session, so it must be exact, not close."""
    state = _state()
    ledger = DecimalLedger(initial_cash=state.ledger_funding(), allow_short=False)
    for fill in state.carry_forward_fills(AT):
        ledger.process_fill(fill)
    assert ledger.cash == state.cash


def test_replaying_carried_positions_reconstructs_quantities_and_basis() -> None:
    state = _state()
    ledger = DecimalLedger(initial_cash=state.ledger_funding(), allow_short=False)
    for fill in state.carry_forward_fills(AT):
        ledger.process_fill(fill)
    assert {s: p.quantity for s, p in ledger.positions.items()} == {"INFY": 98, "TCS": 41}
    assert ledger.positions["INFY"].average_price == Decimal("1542.59")


def test_a_carried_position_can_then_be_sold() -> None:
    """The whole point: without the replay a sell is refused as a short."""
    state = _state()
    ledger = DecimalLedger(initial_cash=state.ledger_funding(), allow_short=False)
    for fill in state.carry_forward_fills(AT):
        ledger.process_fill(fill)
    ledger.process_fill(
        Fill("s1", "o1", "INFY", Side.SELL, 98, Decimal("1560.00"), Decimal("170.00"), AT)
    )
    assert "INFY" not in ledger.positions


def test_selling_a_name_never_held_is_still_refused() -> None:
    """The replay must not become a way to short by accident."""
    state = _state()
    ledger = DecimalLedger(initial_cash=state.ledger_funding(), allow_short=False)
    for fill in state.carry_forward_fills(AT):
        ledger.process_fill(fill)
    with pytest.raises(ValueError, match="short selling is disabled"):
        ledger.process_fill(
            Fill("s2", "o2", "WIPRO", Side.SELL, 10, Decimal("100.00"), Decimal("1.00"), AT)
        )


def test_carry_forward_charges_no_fee() -> None:
    """The cost was paid on the session that opened the position; charging it again is invented."""
    assert all(fill.fee == Decimal("0.00") for fill in _state().carry_forward_fills(AT))


def test_carry_forward_fills_are_identifiable_as_such() -> None:
    """A session report must be able to separate carried positions from today's trades."""
    assert all(fill.fill_id.startswith("carry_") for fill in _state().carry_forward_fills(AT))


def test_an_empty_portfolio_carries_nothing_and_funds_only_cash() -> None:
    empty = PaperPortfolioState(cash=Decimal("1000000.00"))
    assert empty.carry_forward_fills(AT) == []
    assert empty.ledger_funding() == Decimal("1000000.00")


# --------------------------------------------------------------------------------------------
# Rebalancing at the model's horizon, not daily.
# --------------------------------------------------------------------------------------------


def test_an_empty_portfolio_always_rebalances() -> None:
    """Otherwise a fresh install would hold nothing for ever."""
    assert PaperPortfolioState(cash=Decimal("1000000.00")).rebalance_due(11) is True


def test_a_held_portfolio_waits_for_the_horizon() -> None:
    """The screen held 10 sessions before re-ranking; the card declares 11."""
    assert _state(sessions_since_rebalance=4).rebalance_due(11) is False
    assert _state(sessions_since_rebalance=10).rebalance_due(11) is False
    assert _state(sessions_since_rebalance=11).rebalance_due(11) is True


# --------------------------------------------------------------------------------------------
# Persistence must fail closed.
# --------------------------------------------------------------------------------------------


def test_state_survives_a_save_and_load_round_trip(tmp_path) -> None:
    path = tmp_path / "portfolio.json"
    save_portfolio(path, _state())
    loaded = load_portfolio(path)
    assert loaded is not None
    assert loaded.cash == Decimal("93570.50")
    assert loaded.holdings["INFY"].quantity == 98
    assert loaded.holdings["INFY"].opened_on == date(2026, 8, 17)
    assert loaded.sessions_since_rebalance == 4


def test_no_state_file_yet_is_not_an_error(tmp_path) -> None:
    assert load_portfolio(tmp_path / "absent.json") is None


def test_tampered_state_is_refused_rather_than_reset(tmp_path) -> None:
    """Resetting would silently discard a running position and report a clean session."""
    path = tmp_path / "portfolio.json"
    save_portfolio(path, _state())
    document = json.loads(path.read_text(encoding="utf-8"))
    document["payload"]["cash"] = "99999999.00"
    path.write_text(json.dumps(document), encoding="utf-8")
    with pytest.raises(PaperPortfolioError, match="does not match its own hash"):
        load_portfolio(path)


def test_truncated_state_is_refused(tmp_path) -> None:
    path = tmp_path / "portfolio.json"
    save_portfolio(path, _state())
    path.write_text(
        path.read_text(encoding="utf-8")[: len(path.read_text()) // 2], encoding="utf-8"
    )
    with pytest.raises(PaperPortfolioError, match="not valid JSON"):
        load_portfolio(path)


def test_state_from_a_future_schema_is_refused(tmp_path) -> None:
    path = tmp_path / "portfolio.json"
    save_portfolio(path, _state())
    document = json.loads(path.read_text(encoding="utf-8"))
    document["payload"]["schema_version"] = PORTFOLIO_SCHEMA_VERSION + 1
    from quant_system.data.market_data_evidence import canonical_sha256

    document["state_hash"] = canonical_sha256(document["payload"])
    path.write_text(json.dumps(document), encoding="utf-8")
    with pytest.raises(PaperPortfolioError, match="expected"):
        load_portfolio(path)


def test_a_short_holding_cannot_be_constructed() -> None:
    with pytest.raises(PaperPortfolioError, match="long-only"):
        PortfolioHolding("AAA", -5, Decimal("100.00"), date(2026, 8, 17))


# --------------------------------------------------------------------------------------------
# Rolling the session forward.
# --------------------------------------------------------------------------------------------


def test_a_surviving_position_keeps_its_original_open_date() -> None:
    """Age drives when it next rebalances, so surviving a session must not reset it."""
    rolled = state_from_ledger(
        _state(),
        cash=Decimal("50000.00"),
        positions={"INFY": (98, Decimal("1542.59")), "LT": (10, Decimal("3600.00"))},
        session_date=date(2026, 8, 31),
        realized_pnl=Decimal("1240.00"),
        fees_paid=Decimal("120.00"),
        rebalanced=False,
    )
    assert rolled.holdings["INFY"].opened_on == date(2026, 8, 17)
    assert rolled.holdings["LT"].opened_on == date(2026, 8, 31)


def test_holding_a_session_advances_the_rebalance_clock() -> None:
    rolled = state_from_ledger(
        _state(sessions_since_rebalance=4),
        cash=Decimal("50000.00"),
        positions={"INFY": (98, Decimal("1542.59"))},
        session_date=date(2026, 8, 31),
        realized_pnl=Decimal("0.00"),
        fees_paid=Decimal("0.00"),
        rebalanced=False,
    )
    assert rolled.sessions_since_rebalance == 5
    assert rolled.sessions_completed == 5


def test_rebalancing_resets_the_clock_and_stamps_the_date() -> None:
    rolled = state_from_ledger(
        _state(sessions_since_rebalance=11),
        cash=Decimal("50000.00"),
        positions={"LT": (10, Decimal("3600.00"))},
        session_date=date(2026, 8, 31),
        realized_pnl=Decimal("2000.00"),
        fees_paid=Decimal("500.00"),
        rebalanced=True,
    )
    assert rolled.sessions_since_rebalance == 0
    assert rolled.last_rebalance_on == date(2026, 8, 31)


def test_fees_accumulate_across_sessions() -> None:
    rolled = state_from_ledger(
        _state(total_fees=Decimal("828.12")),
        cash=Decimal("50000.00"),
        positions={"INFY": (98, Decimal("1542.59"))},
        session_date=date(2026, 8, 31),
        realized_pnl=Decimal("0.00"),
        fees_paid=Decimal("171.88"),
        rebalanced=False,
    )
    assert rolled.total_fees == Decimal("1000.00")


def test_a_closed_position_drops_out_of_the_carried_state() -> None:
    rolled = state_from_ledger(
        _state(),
        cash=Decimal("400000.00"),
        positions={"TCS": (41, Decimal("3553.98")), "INFY": (0, Decimal("1542.59"))},
        session_date=date(2026, 8, 31),
        realized_pnl=Decimal("1500.00"),
        fees_paid=Decimal("300.00"),
        rebalanced=True,
    )
    assert set(rolled.holdings) == {"TCS"}
