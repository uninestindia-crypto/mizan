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
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal

import pytest

from quant_system.core.domain import Fill, Side
from quant_system.core.ledger import DecimalLedger
from quant_system.data.held_corporate_actions import parse_bonus, parse_face_value
from quant_system.execution.paper_portfolio import (
    PORTFOLIO_SCHEMA_VERSION,
    EquityMark,
    PaperPortfolioError,
    PaperPortfolioState,
    PortfolioHolding,
    acknowledge_corporate_action,
    adjust_for_corporate_action,
    load_portfolio,
    save_portfolio,
    state_from_ledger,
)

AT = datetime(2026, 8, 31, 9, 15, tzinfo=UTC)


def _state(**overrides) -> PaperPortfolioState:
    base = {
        "cash": Decimal("93570.50"),
        "holdings": {
            "INFY": PortfolioHolding(
                "INFY", 98, Decimal("1542.59"), date(2026, 8, 17), Decimal("339.37")
            ),
            "TCS": PortfolioHolding(
                "TCS", 41, Decimal("3553.98"), date(2026, 8, 17), Decimal("324.16")
            ),
        },
        "realized_pnl": Decimal("1240.00"),
        "total_fees": Decimal("828.12"),
        "sessions_completed": 4,
        "sessions_held": 4,
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


def test_carry_forward_carries_the_original_entry_fee() -> None:
    """This test previously asserted the opposite, and the assertion was the defect.

    The reasoning was that the cost had already been paid, so charging it again would be inventing
    one. That is true of cash and false of realized P&L: the ledger attributes a lot's entry fee at
    the moment the lot closes, so a zero-fee replay did not prevent a double charge -- it dropped
    the charge altogether and inflated every cross-session round trip. Cash stays exact because
    `ledger_funding` covers the fee, which the test below pins.
    """
    fees = {fill.symbol: fill.fee for fill in _state().carry_forward_fills(AT)}
    assert fees == {"INFY": Decimal("339.37"), "TCS": Decimal("324.16")}


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


def test_a_held_portfolio_waits_for_the_measured_hold_not_the_declared_horizon() -> None:
    """The card's 11 and the screen's 10 are the same length in two conventions.

    A label horizon counts decision -> entry -> exit (`modeling/labels.py:40`), so a declared 11
    holds for 10 -- exactly what the screen measured with `opens[i + 1 + 10] / opens[i + 1]`.
    Comparing against the raw 11 held a session too long.
    """
    assert _state(sessions_held=4).rebalance_due(11) is False
    assert _state(sessions_held=9).rebalance_due(11) is False
    assert _state(sessions_held=10).rebalance_due(11) is True


def test_a_horizon_that_holds_for_nothing_is_refused() -> None:
    with pytest.raises(PaperPortfolioError, match="holds for no sessions at all"):
        _state().rebalance_due(1)


def test_the_executed_hold_is_exactly_the_screened_hold() -> None:
    """The end-to-end property, simulated through the real functions rather than asserted.

    Two independent off-by-ones used to compound here: the card's horizon was compared directly,
    and the counter lagged the true age by one. Each alone gave 11 sessions; together they gave 12
    against a measured 10. This walks sessions until the next rebalance and pins the interval.
    """
    horizon = 11
    state = PaperPortfolioState(cash=Decimal("1000000.00"))
    assert state.rebalance_due(horizon) is True  # entry session, index 0

    entry = date(2026, 8, 31)
    state = state_from_ledger(
        state,
        cash=Decimal("500000.00"),
        positions={"INFY": (100, Decimal("1500.00"))},
        session_date=entry,
        session_realized_pnl=Decimal("0.00"),
        fees_paid=Decimal("330.00"),
        rebalanced=True,
    )

    for index in range(1, 40):
        if state.rebalance_due(horizon):
            assert index == 10, (
                f"exited on session {index}, but the screen measured a 10-session hold"
            )
            break
        state = state_from_ledger(
            state,
            cash=state.cash,
            positions={"INFY": (100, Decimal("1500.00"))},
            session_date=entry + timedelta(days=index),
            session_realized_pnl=Decimal("0.00"),
            fees_paid=Decimal("0.00"),
            rebalanced=False,
        )
    else:  # pragma: no cover - only reached if the clock never fires
        pytest.fail("the portfolio never became due for a rebalance")


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
    assert loaded.sessions_held == 4


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
        session_realized_pnl=Decimal("1240.00"),
        fees_paid=Decimal("120.00"),
        rebalanced=False,
    )
    assert rolled.holdings["INFY"].opened_on == date(2026, 8, 17)
    assert rolled.holdings["LT"].opened_on == date(2026, 8, 31)


def test_holding_a_session_advances_the_rebalance_clock() -> None:
    rolled = state_from_ledger(
        _state(sessions_held=4),
        cash=Decimal("50000.00"),
        positions={"INFY": (98, Decimal("1542.59"))},
        session_date=date(2026, 8, 31),
        session_realized_pnl=Decimal("0.00"),
        fees_paid=Decimal("0.00"),
        rebalanced=False,
    )
    assert rolled.sessions_held == 5
    assert rolled.sessions_completed == 5


def test_rebalancing_resets_the_clock_and_stamps_the_date() -> None:
    rolled = state_from_ledger(
        _state(sessions_held=11),
        cash=Decimal("50000.00"),
        positions={"LT": (10, Decimal("3600.00"))},
        session_date=date(2026, 8, 31),
        session_realized_pnl=Decimal("2000.00"),
        fees_paid=Decimal("500.00"),
        rebalanced=True,
    )
    # 1, not 0: a position entered today is one session old when the next session opens, and the
    # rebalance check happens at the open.
    assert rolled.sessions_held == 1
    assert rolled.last_rebalance_on == date(2026, 8, 31)


def test_fees_accumulate_across_sessions() -> None:
    rolled = state_from_ledger(
        _state(total_fees=Decimal("828.12")),
        cash=Decimal("50000.00"),
        positions={"INFY": (98, Decimal("1542.59"))},
        session_date=date(2026, 8, 31),
        session_realized_pnl=Decimal("0.00"),
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
        session_realized_pnl=Decimal("1500.00"),
        fees_paid=Decimal("300.00"),
        rebalanced=True,
    )
    assert set(rolled.holdings) == {"TCS"}


# --------------------------------------------------------------------------------------------
# The two money defects a Red Team pass found, each pinned by the trade that exposed it.
# --------------------------------------------------------------------------------------------


def test_a_cross_session_round_trip_reports_the_same_pnl_as_a_same_session_one() -> None:
    """The identical economic trade must not be worth more for having crossed a session boundary.

    Buy 100 @ 1000.00 costing 220.00, sell 100 @ 1100.00 costing 242.00. Held within one session
    the ledger reported the truth, 9538.00. Carried across a session it reported 9758.00, inflated
    by exactly the entry fee, because the replay charged nothing and the ledger attributes a lot's
    entry cost only when that lot closes. Cash agreed in both cases, which is what made it silent.
    """
    buy = Fill("b", "ob", "INFY", Side.BUY, 100, Decimal("1000.00"), Decimal("220.00"), AT)
    sell = Fill("s", "os", "INFY", Side.SELL, 100, Decimal("1100.00"), Decimal("242.00"), AT)

    same = DecimalLedger(initial_cash=Decimal("1000000.00"), allow_short=False)
    same.process_fill(buy)
    same.process_fill(sell)

    carried = PaperPortfolioState(
        cash=Decimal("899780.00"),
        holdings={
            "INFY": PortfolioHolding(
                "INFY", 100, Decimal("1000.00"), date(2026, 8, 17), Decimal("220.00")
            )
        },
    )
    across = DecimalLedger(initial_cash=carried.ledger_funding(), allow_short=False)
    for fill in carried.carry_forward_fills(AT):
        across.process_fill(fill)
    across.process_fill(sell)

    assert across.realized_pnl == same.realized_pnl == Decimal("9538.00")
    assert across.cash == same.cash


def test_carrying_a_position_still_leaves_cash_exact_now_that_the_fee_travels() -> None:
    """The fee must be neutral to cash, or the fix for P&L would have broken the thing that worked."""
    state = _state()
    ledger = DecimalLedger(initial_cash=state.ledger_funding(), allow_short=False)
    for fill in state.carry_forward_fills(AT):
        ledger.process_fill(fill)
    assert ledger.cash == state.cash


def test_cumulative_realized_pnl_survives_an_idle_session() -> None:
    """It used to be overwritten with the session figure, so one quiet day erased the record.

    The line beside it accumulated fees correctly, which is why the asymmetry went unnoticed -- and
    the file it was written into is hash-protected and schema-versioned, so the wrong number looked
    trustworthy.
    """
    after_a_win = state_from_ledger(
        PaperPortfolioState(cash=Decimal("1000000.00")),
        cash=Decimal("1009538.00"),
        positions={},
        session_date=date(2026, 8, 26),
        session_realized_pnl=Decimal("9538.00"),
        fees_paid=Decimal("462.00"),
        rebalanced=True,
    )
    assert after_a_win.realized_pnl == Decimal("9538.00")

    idle = state_from_ledger(
        after_a_win,
        cash=Decimal("1009538.00"),
        positions={},
        session_date=date(2026, 8, 27),
        session_realized_pnl=Decimal("0.00"),
        fees_paid=Decimal("0.00"),
        rebalanced=False,
    )
    assert idle.realized_pnl == Decimal("9538.00")
    assert idle.total_fees == Decimal("462.00")


def test_a_carried_entry_fee_round_trips_through_the_state_file(tmp_path) -> None:
    path = tmp_path / "portfolio.json"
    save_portfolio(path, _state())
    loaded = load_portfolio(path)
    assert loaded is not None
    assert loaded.holdings["INFY"].entry_fee == Decimal("339.37")


def test_a_negative_entry_fee_cannot_be_constructed() -> None:
    with pytest.raises(PaperPortfolioError, match="entry fee cannot be negative"):
        PortfolioHolding("AAA", 5, Decimal("100.00"), date(2026, 8, 17), Decimal("-1.00"))


# --------------------------------------------------------------------------------------------
# The drawdown peak, which persistence made inert.
# --------------------------------------------------------------------------------------------


def test_the_equity_peak_never_falls() -> None:
    """A peak that could fall would let a drawdown be forgiven by the decline that caused it."""
    high = state_from_ledger(
        PaperPortfolioState(cash=Decimal("1000000.00")),
        cash=Decimal("1200000.00"),
        positions={},
        session_date=date(2026, 8, 26),
        session_realized_pnl=Decimal("200000.00"),
        fees_paid=Decimal("0.00"),
        rebalanced=True,
        session_peak_equity=Decimal("1200000.00"),
    )
    slump = state_from_ledger(
        high,
        cash=Decimal("900000.00"),
        positions={},
        session_date=date(2026, 8, 27),
        session_realized_pnl=Decimal("-300000.00"),
        fees_paid=Decimal("0.00"),
        rebalanced=False,
        session_peak_equity=Decimal("900000.00"),
    )
    assert slump.peak_equity == Decimal("1200000.00")


def test_the_peak_round_trips_so_a_multi_session_decline_can_trip_the_switch(tmp_path) -> None:
    path = tmp_path / "portfolio.json"
    save_portfolio(path, _state(peak_equity=Decimal("1200000.00")))
    loaded = load_portfolio(path)
    assert loaded is not None
    assert loaded.peak_equity == Decimal("1200000.00")


# --------------------------------------------------------------------------------------------
# A rebalance is recorded when it happens, not when it is intended.
# --------------------------------------------------------------------------------------------


def test_a_refused_rebalance_does_not_reset_the_hold_clock() -> None:
    """228 orders rejected, zero filled, the book unchanged -- and it was persisted as a rebalance.

    `rebalanced=rebalancing` recorded the *intent*. The clock reset and `last_rebalance_on` advanced
    on a portfolio nobody had touched, so the next real rebalance was pushed ten sessions away.
    """
    held = _state(sessions_held=10, last_rebalance_on=date(2026, 8, 17))

    refused = state_from_ledger(
        held,
        cash=held.cash,
        positions={s: (h.quantity, h.average_cost) for s, h in held.holdings.items()},
        session_date=date(2026, 9, 14),
        session_realized_pnl=Decimal("0.00"),
        fees_paid=Decimal("0.00"),
        rebalanced=False,  # what the runner now passes when nothing executed
    )

    assert refused.sessions_held == 11, "the clock must keep running, not restart"
    assert refused.last_rebalance_on == date(2026, 8, 17), "no rebalance happened to stamp"
    assert refused.rebalance_due(11) is True, "still due; the refusal did not satisfy it"


def test_a_rebalance_that_kept_everything_still_counts_as_one() -> None:
    """The case a naive "did anything fill?" fix would get wrong in the other direction.

    A rebalance whose new selection equals the current book legitimately fills nothing -- the model
    re-ranked and chose to keep what it held. That is a completed rebalance and its clock resets.
    """
    held = _state(sessions_held=10)

    kept = state_from_ledger(
        held,
        cash=held.cash,
        positions={s: (h.quantity, h.average_cost) for s, h in held.holdings.items()},
        session_date=date(2026, 9, 14),
        session_realized_pnl=Decimal("0.00"),
        fees_paid=Decimal("0.00"),
        rebalanced=True,
    )

    assert kept.sessions_held == 1
    assert kept.last_rebalance_on == date(2026, 9, 14)


# --------------------------------------------------------------------------------------------
# The daily drawdown baseline must survive a restart.
# --------------------------------------------------------------------------------------------


def test_the_daily_anchor_survives_a_restart_within_the_same_session() -> None:
    """Four starts in one day measured a 10.2% decline as three separate sub-4% ones.

    The anchor lived only in the process, so every restart re-baselined the daily rule to whatever
    equity was current: 1,000,000 -> 965,000 -> 931,000 -> 898,000, and the 4% limit never tripped.
    Three sessions were abandoned and restarted on 2026-08-31 alone, so this is a live path.
    """
    session = date(2026, 9, 1)
    morning = state_from_ledger(
        PaperPortfolioState(cash=Decimal("1000000.00")),
        cash=Decimal("1000000.00"),
        positions={},
        session_date=session,
        session_realized_pnl=Decimal("0.00"),
        fees_paid=Decimal("0.00"),
        rebalanced=False,
        daily_anchor_on=session,
        daily_anchor_equity=Decimal("1000000.00"),
    )

    assert morning.daily_anchor_on == session
    assert morning.daily_anchor_equity == Decimal("1000000.00")

    # A later start on the same day passes no anchor; the morning's must be carried, not replaced.
    after_restart = state_from_ledger(
        morning,
        cash=Decimal("931000.00"),
        positions={},
        session_date=session,
        session_realized_pnl=Decimal("-69000.00"),
        fees_paid=Decimal("0.00"),
        rebalanced=False,
    )

    assert after_restart.daily_anchor_equity == Decimal("1000000.00"), (
        "the restart re-baselined the daily rule to the reduced equity, which is how a 10.2% "
        "decline was measured as three separate sub-4% ones"
    )
    assert after_restart.daily_anchor_on == session


def test_the_anchor_round_trips_through_the_state_file(tmp_path) -> None:
    """It is only useful across restarts if it is actually persisted."""
    path = tmp_path / "portfolio.json"
    save_portfolio(
        path,
        _state(daily_anchor_on=date(2026, 9, 1), daily_anchor_equity=Decimal("1000000.00")),
    )
    loaded = load_portfolio(path)

    assert loaded is not None
    assert loaded.daily_anchor_on == date(2026, 9, 1)
    assert loaded.daily_anchor_equity == Decimal("1000000.00")


# --------------------------------------------------------------------------------------------
# Two sessions must not silently overwrite each other.
# --------------------------------------------------------------------------------------------


def test_a_concurrent_write_is_refused_rather_than_clobbered(tmp_path) -> None:
    """Two sessions ran at once and the second to finish discarded the first's whole trading day.

    16 fills, `sessions_completed` 10 to 11, one session's fees -- gone, with both reports on disk
    and no error anywhere. There is no lock, so the overlap is still possible; what this prevents is
    the loss, which is the part that cannot be recovered afterwards.
    """
    from quant_system.execution.paper_portfolio import state_hash_on_disk

    path = tmp_path / "portfolio.json"
    save_portfolio(path, _state(sessions_completed=10))

    # Session A loads.
    seen_by_a = state_hash_on_disk(path)

    # Session B finishes first and writes its day.
    save_portfolio(path, _state(sessions_completed=11, cash=Decimal("111111.11")))

    # Session A now tries to write what it believes is the next state.
    with pytest.raises(PaperPortfolioError, match="changed since this session loaded it"):
        save_portfolio(path, _state(sessions_completed=11), seen_by_a)

    # B's day survives.
    surviving = load_portfolio(path)
    assert surviving is not None
    assert surviving.cash == Decimal("111111.11")


def test_an_uncontended_write_still_succeeds(tmp_path) -> None:
    """The guard must not refuse the ordinary case of one session writing its own next state."""
    from quant_system.execution.paper_portfolio import state_hash_on_disk

    path = tmp_path / "portfolio.json"
    save_portfolio(path, _state(sessions_completed=4))
    seen = state_hash_on_disk(path)

    save_portfolio(path, _state(sessions_completed=5), seen)

    reloaded = load_portfolio(path)
    assert reloaded is not None
    assert reloaded.sessions_completed == 5


def test_a_first_run_writes_against_no_prior_file(tmp_path) -> None:
    """`None` is the real value for "there was no file", not a request to skip the check."""
    from quant_system.execution.paper_portfolio import state_hash_on_disk

    path = tmp_path / "portfolio.json"
    assert state_hash_on_disk(path) is None

    save_portfolio(path, _state(), None)
    assert load_portfolio(path) is not None

    # And a second writer that also believed the file was absent is refused.
    with pytest.raises(PaperPortfolioError, match="changed since this session loaded it"):
        save_portfolio(path, _state(cash=Decimal("222222.22")), None)


# --------------------------------------------------------------------------------------------
# Migrating a file written by an older schema.
#
# Versions 2 and 3 landed on the reasoning that no state file had ever been produced, so no
# migration was needed. That reasoning expired on 2026-08-31, when a real session wrote a v3 file
# holding 97 positions. The next morning's run refused it and exited 2 before placing an order.
# --------------------------------------------------------------------------------------------


def _write_at_version(path, state, version: int, drop=()) -> None:
    """Write `state` as an older schema would have: older version, newer fields absent."""
    from quant_system.data.market_data_evidence import canonical_sha256

    save_portfolio(path, state)
    document = json.loads(path.read_text(encoding="utf-8"))
    document["payload"]["schema_version"] = version
    for key in drop:
        document["payload"].pop(key, None)
    document["state_hash"] = canonical_sha256(document["payload"])
    path.write_text(json.dumps(document), encoding="utf-8")


V7_ADDED = ("reviewed_actions",)
V6_ADDED = ("inception_on", "equity_marks", *V7_ADDED)
V3_ABSENT = ("daily_anchor_on", "daily_anchor_equity", "last_completed_on", *V6_ADDED)
V4_ABSENT = ("last_completed_on", *V6_ADDED)
V5_ABSENT = V6_ADDED
V6_ABSENT = V7_ADDED


def test_a_v4_file_written_before_last_completed_on_still_loads(tmp_path) -> None:
    """v4 files written before v5 must migrate cleanly with last_completed_on defaulting to None."""
    path = tmp_path / "portfolio.json"
    _write_at_version(path, _state(), 4, drop=V4_ABSENT)

    loaded = load_portfolio(path)
    assert loaded is not None
    assert loaded.last_completed_on is None
    assert loaded.cash == Decimal("93570.50")


def test_a_v3_file_written_before_the_anchor_existed_still_loads(tmp_path) -> None:
    """The real 2026-09-01 abort: refusing this discards a book, it does not protect one."""
    path = tmp_path / "portfolio.json"
    _write_at_version(path, _state(), 3, drop=V3_ABSENT)

    loaded = load_portfolio(path)

    assert loaded is not None
    assert loaded.cash == Decimal("93570.50")
    assert loaded.holdings["INFY"].quantity == 98
    assert loaded.holdings["INFY"].entry_fee == Decimal("339.37")
    assert loaded.sessions_held == 4
    assert loaded.total_fees == Decimal("828.12")


def test_a_migrated_v3_file_starts_the_session_with_no_anchor(tmp_path) -> None:
    """No anchor is the correct starting state: the session takes a fresh one from its first mark.

    Inventing one from the persisted figures would baseline the day against a stale equity and
    measure a drawdown that did not happen today.
    """
    path = tmp_path / "portfolio.json"
    # A non-zero peak, because the peak is the figure a migration would most plausibly reach for,
    # and `peak_equity` defaults to 0.00 -- with the default this assertion cannot tell the two
    # apart, and a mutant seeding the anchor from the peak survives it.
    _write_at_version(path, _state(peak_equity=Decimal("1000000.00")), 3, drop=V3_ABSENT)

    loaded = load_portfolio(path)

    assert loaded is not None
    assert loaded.daily_anchor_on is None
    assert loaded.daily_anchor_equity == Decimal("0.00")
    assert loaded.peak_equity == Decimal("1000000.00")


def test_migration_does_not_bypass_the_integrity_check(tmp_path) -> None:
    """An old version is a reason to upgrade a payload, never a reason to trust one."""
    path = tmp_path / "portfolio.json"
    _write_at_version(path, _state(), 3, drop=V3_ABSENT)
    document = json.loads(path.read_text(encoding="utf-8"))
    document["payload"]["cash"] = "99999999.00"
    path.write_text(json.dumps(document), encoding="utf-8")

    with pytest.raises(PaperPortfolioError, match="does not match its own hash"):
        load_portfolio(path)


def test_a_version_with_no_migration_is_still_refused(tmp_path) -> None:
    """v2 renamed a field this loader reads. Defaulting through it would resume a wrong book."""
    path = tmp_path / "portfolio.json"
    _write_at_version(path, _state(), 2, drop=V3_ABSENT)

    with pytest.raises(PaperPortfolioError, match="no migration exists from v2"):
        load_portfolio(path)


def test_a_foreign_schema_id_is_refused_whatever_its_version(tmp_path) -> None:
    from quant_system.data.market_data_evidence import canonical_sha256

    path = tmp_path / "portfolio.json"
    save_portfolio(path, _state())
    document = json.loads(path.read_text(encoding="utf-8"))
    document["payload"]["schema_id"] = "somebody.else.ledger"
    document["state_hash"] = canonical_sha256(document["payload"])
    path.write_text(json.dumps(document), encoding="utf-8")

    with pytest.raises(PaperPortfolioError, match="declares schema"):
        load_portfolio(path)


def test_a_migrated_book_is_written_back_at_the_current_version(tmp_path) -> None:
    """Migration must be a one-off: the next morning reads a current file, not an old one again."""
    path = tmp_path / "portfolio.json"
    _write_at_version(path, _state(), 3, drop=V3_ABSENT)

    loaded = load_portfolio(path)
    assert loaded is not None
    save_portfolio(path, loaded)

    document = json.loads(path.read_text(encoding="utf-8"))
    assert document["payload"]["schema_version"] == PORTFOLIO_SCHEMA_VERSION
    assert "daily_anchor_on" in document["payload"]
    reloaded = load_portfolio(path)
    assert reloaded is not None
    assert reloaded.cash == Decimal("93570.50")


# --------------------------------------------------------------------------------------------
# An aborted session does not spend one of the model's held sessions. (R6-15, second half)
# --------------------------------------------------------------------------------------------


def test_an_aborted_session_does_not_advance_the_hold_clock() -> None:
    """A session that raised two minutes in was persisted with the counters advanced.

    Ten such mornings retire a position without a single session having marked the book to a real
    close.
    """
    previous = _state(sessions_held=4, sessions_completed=4)

    after = state_from_ledger(
        previous,
        session_completed=False,
        cash=Decimal("93570.50"),
        positions={"INFY": (98, Decimal("1542.59"))},
        session_date=date(2026, 9, 1),
        session_realized_pnl=Decimal("0.00"),
        fees_paid=Decimal("0.00"),
        rebalanced=False,
    )

    assert after.sessions_held == 4
    assert after.sessions_completed == 4


def test_an_aborted_session_still_keeps_the_ledger_facts() -> None:
    """Cash, holdings and fees happened. Discarding them would lose real fills."""
    previous = _state(sessions_held=4, sessions_completed=4)

    after = state_from_ledger(
        previous,
        session_completed=False,
        cash=Decimal("50000.00"),
        positions={"INFY": (120, Decimal("1500.00"))},
        session_date=date(2026, 9, 1),
        session_realized_pnl=Decimal("250.00"),
        fees_paid=Decimal("31.75"),
        rebalanced=False,
    )

    assert after.cash == Decimal("50000.00")
    assert after.holdings["INFY"].quantity == 120
    assert after.total_fees == previous.total_fees + Decimal("31.75")
    assert after.realized_pnl == previous.realized_pnl + Decimal("250.00")


def test_a_completed_session_still_advances_the_clock() -> None:
    """The guard must not stop the clock for every session."""
    previous = _state(sessions_held=4, sessions_completed=4)

    after = state_from_ledger(
        previous,
        cash=Decimal("93570.50"),
        positions={"INFY": (98, Decimal("1542.59"))},
        session_date=date(2026, 9, 1),
        session_realized_pnl=Decimal("0.00"),
        fees_paid=Decimal("0.00"),
        rebalanced=False,
    )

    assert after.sessions_held == 5
    assert after.sessions_completed == 5


def test_an_aborted_rebalance_does_not_stamp_the_rebalance_date() -> None:
    """`rebalanced` still wins where it is true, so the two flags cannot contradict each other."""
    previous = _state(sessions_held=9, sessions_completed=9)

    after = state_from_ledger(
        previous,
        session_completed=False,
        cash=Decimal("93570.50"),
        positions={"INFY": (98, Decimal("1542.59"))},
        session_date=date(2026, 9, 1),
        session_realized_pnl=Decimal("0.00"),
        fees_paid=Decimal("0.00"),
        rebalanced=False,
    )

    assert after.last_rebalance_on == previous.last_rebalance_on
    assert after.sessions_held == 9


def test_multiple_runs_on_the_same_date_do_not_advance_the_hold_clock() -> None:
    """R7-05: every restart on the same trading day spent another of the model's held sessions."""
    entry = date(2026, 9, 1)
    state = _state(sessions_held=2, sessions_completed=2)

    # First completion on 2026-09-01
    run1 = state_from_ledger(
        state,
        session_completed=True,
        cash=Decimal("93570.50"),
        positions={"INFY": (98, Decimal("1542.59"))},
        session_date=entry,
        session_realized_pnl=Decimal("0.00"),
        fees_paid=Decimal("0.00"),
        rebalanced=False,
    )
    assert run1.sessions_completed == 3
    assert run1.sessions_held == 3
    assert run1.last_completed_on == entry

    # Second completion (e.g. process restart) on the SAME date 2026-09-01
    run2 = state_from_ledger(
        run1,
        session_completed=True,
        cash=Decimal("93570.50"),
        positions={"INFY": (98, Decimal("1542.59"))},
        session_date=entry,
        session_realized_pnl=Decimal("0.00"),
        fees_paid=Decimal("0.00"),
        rebalanced=False,
    )
    assert run2.sessions_completed == 3, "must not advance sessions_completed again on same date"
    assert run2.sessions_held == 3, "must not advance sessions_held again on same date"
    assert run2.last_completed_on == entry

    # Third run on next trading day 2026-09-02
    next_day = date(2026, 9, 2)
    run3 = state_from_ledger(
        run2,
        session_completed=True,
        cash=Decimal("93570.50"),
        positions={"INFY": (98, Decimal("1542.59"))},
        session_date=next_day,
        session_realized_pnl=Decimal("0.00"),
        fees_paid=Decimal("0.00"),
        rebalanced=False,
    )
    assert run3.sessions_completed == 4
    assert run3.sessions_held == 4
    assert run3.last_completed_on == next_day


# --------------------------------------------------------------------------------------------
# The equity history (v6): one closing mark per completed session, and the book's first session.
#
# A report had nothing to read the book on except today, while the index it was set against is
# refreshed before the open and so always ends a session earlier. On 2026-09-21 that printed the
# gap between the book's 21 Sep mark and NIFTY 50's 18 Sep close as stock selection.
# --------------------------------------------------------------------------------------------


def _pristine() -> PaperPortfolioState:
    return PaperPortfolioState(cash=Decimal("1000000.00"))


def _close(state, on: date, equity: str, invested: str, **overrides) -> PaperPortfolioState:
    """One session's close, recorded through the same call the runner makes."""
    return state_from_ledger(
        state,
        cash=Decimal(equity) - Decimal(invested),
        positions={"INFY": (10, Decimal("1500.00"))},
        session_date=on,
        session_realized_pnl=Decimal("0.00"),
        fees_paid=Decimal("0.00"),
        rebalanced=False,
        closing_mark=EquityMark(on=on, equity=Decimal(equity), invested=Decimal(invested)),
        **overrides,
    )


def test_the_first_session_of_a_pristine_book_stamps_its_inception() -> None:
    first = date(2026, 10, 7)
    after = _close(_pristine(), first, "998000.00", "850000.00")

    assert after.inception_on == first
    assert after.equity_marks[first].equity == Decimal("998000.00")
    assert after.equity_marks[first].invested == Decimal("850000.00")


def test_the_inception_never_moves_after_the_first_session() -> None:
    first, second = date(2026, 10, 7), date(2026, 10, 8)
    after = _close(_close(_pristine(), first, "998000.00", "850000.00"), second, "1001000", "0")

    assert after.inception_on == first
    assert sorted(after.equity_marks) == [first, second]


def test_an_aborted_first_session_still_began_the_book_but_records_no_close() -> None:
    """It may have traded before aborting, so the book began; but it never reached a close."""
    first = date(2026, 10, 7)
    after = _close(_pristine(), first, "999000.00", "400000.00", session_completed=False)

    assert after.inception_on == first
    assert after.equity_marks == {}


def test_a_book_with_history_but_no_recorded_start_never_acquires_one() -> None:
    """A migrated book began before anything recorded its start.

    Stamping the first post-migration session would measure its return from a date on which it had
    already lost money -- the flagship was 1.18% down on 2026-09-21 -- and report the loss as gone.
    """
    day = date(2026, 9, 22)
    after = _close(_state(), day, "990000.00", "870000.00")

    assert after.inception_on is None
    assert after.equity_marks[day].equity == Decimal("990000.00")


def test_a_rerun_on_the_same_date_replaces_that_dates_mark() -> None:
    day = date(2026, 10, 7)
    rerun = _close(_close(_pristine(), day, "998000.00", "850000.00"), day, "997500", "849000")

    assert list(rerun.equity_marks) == [day]
    assert rerun.equity_marks[day].equity == Decimal("997500")


def test_a_mark_dated_for_another_session_is_refused() -> None:
    with pytest.raises(PaperPortfolioError, match="closing mark dated 2026-10-07"):
        state_from_ledger(
            _pristine(),
            cash=Decimal("1000000.00"),
            positions={},
            session_date=date(2026, 10, 8),
            session_realized_pnl=Decimal("0.00"),
            fees_paid=Decimal("0.00"),
            rebalanced=False,
            closing_mark=EquityMark(
                on=date(2026, 10, 7), equity=Decimal("1000000.00"), invested=Decimal("0.00")
            ),
        )


def test_a_mark_cannot_hold_more_in_positions_than_the_book_is_worth() -> None:
    day = date(2026, 10, 7)
    with pytest.raises(PaperPortfolioError, match="between zero and the equity"):
        EquityMark(on=day, equity=Decimal("100.00"), invested=Decimal("100.01"))
    with pytest.raises(PaperPortfolioError, match="between zero and the equity"):
        EquityMark(on=day, equity=Decimal("100.00"), invested=Decimal("-0.01"))
    with pytest.raises(PaperPortfolioError, match="equity must be positive"):
        EquityMark(on=day, equity=Decimal("0.00"), invested=Decimal("0.00"))


def test_exposure_is_the_share_of_equity_held_in_positions() -> None:
    mark = EquityMark(
        on=date(2026, 10, 7), equity=Decimal("1000000.00"), invested=Decimal("850000")
    )
    assert mark.exposure == Decimal("0.85")


def test_the_equity_history_round_trips_through_the_state_file(tmp_path) -> None:
    path = tmp_path / "portfolio.json"
    first, second = date(2026, 10, 7), date(2026, 10, 8)
    state = _close(
        _close(_pristine(), first, "998000.00", "850000.00"), second, "1001000", "860000"
    )
    save_portfolio(path, state)

    loaded = load_portfolio(path)

    assert loaded is not None
    assert loaded.inception_on == first
    assert loaded.equity_marks == state.equity_marks


def test_a_v5_file_written_before_the_equity_history_still_loads(tmp_path) -> None:
    """With no recorded start and no marks: unknown, which is the truth about such a book."""
    path = tmp_path / "portfolio.json"
    _write_at_version(path, _state(), 5, drop=V5_ABSENT)

    loaded = load_portfolio(path)

    assert loaded is not None
    assert loaded.inception_on is None
    assert loaded.equity_marks == {}
    assert loaded.cash == Decimal("93570.50")
    assert loaded.holdings["INFY"].quantity == 98


def test_two_marks_for_one_date_are_refused(tmp_path) -> None:
    from quant_system.data.market_data_evidence import canonical_sha256

    path = tmp_path / "portfolio.json"
    save_portfolio(path, _close(_pristine(), date(2026, 10, 7), "998000.00", "850000.00"))
    document = json.loads(path.read_text(encoding="utf-8"))
    document["payload"]["equity_marks"].append(dict(document["payload"]["equity_marks"][0]))
    document["state_hash"] = canonical_sha256(document["payload"])
    path.write_text(json.dumps(document), encoding="utf-8")

    with pytest.raises(PaperPortfolioError, match="two equity marks for 2026-10-07"):
        load_portfolio(path)


# --------------------------------------------------------------------------------------------
# Reviewed corporate actions (v7): an adjustment and its record are one write.
# --------------------------------------------------------------------------------------------

EX = date(2026, 9, 7)
REVIEWED_AT = "2026-09-24T07:00:00Z"


def test_a_bonus_doubles_the_shares_and_halves_the_cost_keeping_total_cost() -> None:
    before = _state()
    after, record = adjust_for_corporate_action(
        before,
        symbol="INFY",
        ex_date=EX,
        subject="Bonus 1:1",
        adjustment=parse_bonus("1:1"),
        reviewed_at=REVIEWED_AT,
    )
    held = after.holdings["INFY"]
    assert held.quantity == 196
    assert held.average_cost == Decimal("771.295000")
    assert held.cost_basis == before.holdings["INFY"].cost_basis
    # Not a trade: cash, fees, realized P&L, the entry fee and the open date are untouched.
    assert after.cash == before.cash
    assert after.realized_pnl == before.realized_pnl
    assert after.total_fees == before.total_fees
    assert held.entry_fee == before.holdings["INFY"].entry_fee
    assert held.opened_on == before.holdings["INFY"].opened_on
    assert record.resolution == "adjusted: bonus 1:1"
    assert after.reviewed == {("INFY", EX)}


def test_a_split_that_leaves_a_fraction_says_so() -> None:
    # 41 shares at a 3:2 face-value change is 61.5 new shares; 61 are credited.
    after, record = adjust_for_corporate_action(
        _state(),
        symbol="TCS",
        ex_date=EX,
        subject="Face Value Split",
        adjustment=parse_face_value("3:2"),
        reviewed_at=REVIEWED_AT,
    )
    assert after.holdings["TCS"].quantity == 61
    assert "0.5000 fractional share(s) not credited" in record.resolution


def test_an_acknowledgement_changes_nothing_but_the_record() -> None:
    before = _state()
    after, record = acknowledge_corporate_action(
        before,
        symbol="INFY",
        ex_date=EX,
        subject="Rights 3:25 @ Premium Rs 1799/-",
        reason="rights not taken up; the entitlement lapsed",
        reviewed_at=REVIEWED_AT,
    )
    assert after.holdings == before.holdings
    assert record.resolution == "acknowledged: rights not taken up; the entitlement lapsed"
    assert record.quantity_before == record.quantity_after == 98


def test_the_same_action_cannot_be_applied_twice() -> None:
    once, _ = adjust_for_corporate_action(
        _state(),
        symbol="INFY",
        ex_date=EX,
        subject="Bonus 1:1",
        adjustment=parse_bonus("1:1"),
        reviewed_at=REVIEWED_AT,
    )
    with pytest.raises(PaperPortfolioError, match="already been reviewed"):
        adjust_for_corporate_action(
            once,
            symbol="INFY",
            ex_date=EX,
            subject="Bonus 1:1",
            adjustment=parse_bonus("1:1"),
            reviewed_at=REVIEWED_AT,
        )
    with pytest.raises(PaperPortfolioError, match="already been reviewed"):
        acknowledge_corporate_action(
            once, symbol="INFY", ex_date=EX, subject="Bonus 1:1", reason="x", reviewed_at="t"
        )


def test_a_name_not_held_or_bought_after_the_action_cannot_be_reviewed() -> None:
    with pytest.raises(PaperPortfolioError, match="not held"):
        acknowledge_corporate_action(
            _state(), symbol="WIPRO", ex_date=EX, subject="Bonus 1:1", reason="x", reviewed_at="t"
        )
    with pytest.raises(PaperPortfolioError, match="already reflects the action"):
        acknowledge_corporate_action(
            _state(),
            symbol="INFY",
            ex_date=date(2026, 8, 17),
            subject="Bonus 1:1",
            reason="x",
            reviewed_at="t",
        )


def test_an_acknowledgement_needs_a_reason() -> None:
    with pytest.raises(PaperPortfolioError, match="needs a reason"):
        acknowledge_corporate_action(
            _state(), symbol="INFY", ex_date=EX, subject="Demerger", reason="  ", reviewed_at="t"
        )


def test_a_review_survives_the_next_session_so_it_is_never_asked_again() -> None:
    """Dropping it would let the guard stop again, and a second review would adjust twice."""
    reviewed, _ = adjust_for_corporate_action(
        _state(),
        symbol="INFY",
        ex_date=EX,
        subject="Bonus 1:1",
        adjustment=parse_bonus("1:1"),
        reviewed_at=REVIEWED_AT,
    )
    after = state_from_ledger(
        reviewed,
        cash=reviewed.cash,
        positions={"INFY": (196, Decimal("771.295000"))},
        session_date=date(2026, 9, 25),
        session_realized_pnl=Decimal("0.00"),
        fees_paid=Decimal("0.00"),
        rebalanced=False,
    )
    assert after.reviewed == {("INFY", EX)}


def test_reviewed_actions_round_trip_through_the_state_file(tmp_path) -> None:
    path = tmp_path / "portfolio.json"
    state, _ = adjust_for_corporate_action(
        _state(),
        symbol="INFY",
        ex_date=EX,
        subject="Bonus 1:1",
        adjustment=parse_bonus("1:1"),
        reviewed_at=REVIEWED_AT,
    )
    save_portfolio(path, state)

    loaded = load_portfolio(path)

    assert loaded is not None
    assert loaded.reviewed_actions == state.reviewed_actions
    assert loaded.holdings["INFY"].quantity == 196


def test_a_v6_file_keeps_its_equity_history_when_it_migrates(tmp_path) -> None:
    """Only the new field is defaulted; resetting v6's history would lose the book's start."""
    path = tmp_path / "portfolio.json"
    first = date(2026, 10, 7)
    v6 = _close(_pristine(), first, "998000.00", "850000.00")
    _write_at_version(path, v6, 6, drop=V6_ABSENT)

    loaded = load_portfolio(path)

    assert loaded is not None
    assert loaded.inception_on == first
    assert loaded.equity_marks == v6.equity_marks
    assert loaded.reviewed_actions == ()


def test_a_file_reviewing_one_action_twice_is_refused(tmp_path) -> None:
    from quant_system.data.market_data_evidence import canonical_sha256

    path = tmp_path / "portfolio.json"
    state, _ = acknowledge_corporate_action(
        _state(), symbol="INFY", ex_date=EX, subject="Demerger", reason="x", reviewed_at="t"
    )
    save_portfolio(path, state)
    document = json.loads(path.read_text(encoding="utf-8"))
    document["payload"]["reviewed_actions"].append(dict(document["payload"]["reviewed_actions"][0]))
    document["state_hash"] = canonical_sha256(document["payload"])
    path.write_text(json.dumps(document), encoding="utf-8")

    with pytest.raises(PaperPortfolioError, match="reviews the same corporate action twice"):
        load_portfolio(path)


def test_an_adjusted_holding_still_replays_to_exact_cash() -> None:
    """A cost per share like 333.333333 must not leave a paisa of drift in the next ledger."""
    for adjustment, quantity, cost in (
        (parse_bonus("2:1"), 1, "1000.00"),
        (parse_bonus("1:2"), 7, "101.37"),
        (parse_face_value("10:3"), 13, "999.99"),
    ):
        before = PaperPortfolioState(
            cash=Decimal("5000.00"),
            holdings={
                "X": PortfolioHolding(
                    "X", quantity, Decimal(cost), date(2026, 10, 1), Decimal("3.21")
                )
            },
            sessions_completed=2,
        )
        after, _ = adjust_for_corporate_action(
            before,
            symbol="X",
            ex_date=date(2026, 10, 5),
            subject="-",
            adjustment=adjustment,
            reviewed_at=REVIEWED_AT,
        )
        ledger = DecimalLedger(initial_cash=after.ledger_funding(), allow_short=False)
        for fill in after.carry_forward_fills(AT):
            ledger.process_fill(fill)
        assert ledger.cash == after.cash, adjustment.label
        assert after.holdings["X"].cost_basis == before.holdings["X"].cost_basis, adjustment.label
