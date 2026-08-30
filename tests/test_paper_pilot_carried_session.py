"""A session that starts holding something must still reconcile, and a halt must outlive it.

Both P1s in `.launch/reports/RED-TEAM-20260830-P1-REPAIRS.md` came from repairs interacting rather
than from any single one, and the recheck named the structural reason neither was caught:

> no test in the suite reaches `PaperPilotEngine.end_session` with a carried position

Every repair had been tested in isolation. Nothing tested the assembled session. This file is that
missing test.

**The reconciliation break.** `end_session` check (b) reconciles `ledger.positions` against the fills
in `_fills`, which assumes the session opens flat. Since the portfolio began carrying positions the
runner replayed them straight through `ledger.process_fill`, correctly updating the ledger and never
touching `_fills`, so every session holding anything reported `POSITION_MISMATCH`. That failure was
invisible while a failed reconciliation still printed SUCCESS and exited 0; making the exit code
honest turned it into a session that could never finish green.

**The forgotten halt.** A total-drawdown breach set `_is_killed` on a governor that was rebuilt from
scratch the next morning, so the halt lasted one session -- and because the kill fires on the first
order and the first order is a SELL, the same session's exits were refused and the losing book was
retained.
"""

from __future__ import annotations

import ast
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path

import pytest

from quant_system.core.domain import Fill, OrderType, Side
from quant_system.execution.paper_pilot import (
    PaperPilotEngine,
    PaperProposal,
    SessionStatus,
)
from quant_system.execution.paper_portfolio import (
    PaperPortfolioState,
    PortfolioHolding,
    load_portfolio,
    save_portfolio,
    state_from_ledger,
)

AT = datetime(2026, 8, 31, 9, 15, tzinfo=UTC)
#: Every held name needs a closing mark: `DecimalLedger` refuses to substitute an average price
#: rather than fabricate a mark-to-market, so `end_session` raises without these.
CLOSE_PRICES = {"ACME": Decimal("1010.00"), "BETA": Decimal("1690.00")}
CLOSE = datetime(2026, 8, 31, 15, 30, tzinfo=UTC)
SESSION_DATE = date(2026, 8, 31)


def _carried() -> PaperPortfolioState:
    return PaperPortfolioState(
        cash=Decimal("50000.00"),
        holdings={
            "ACME": PortfolioHolding(
                "ACME", 100, Decimal("1000.00"), date(2026, 8, 17), Decimal("220.00")
            ),
            "BETA": PortfolioHolding(
                "BETA", 500, Decimal("1700.00"), date(2026, 8, 17), Decimal("1900.00")
            ),
        },
    )


def _engine(state: PaperPortfolioState) -> PaperPilotEngine:
    engine = PaperPilotEngine(
        initial_cash=state.ledger_funding(),
        allow_short=False,
        session_id="carried_session_test",
    )
    engine.carry_in_positions(state.carry_forward_fills(AT))
    return engine


# --------------------------------------------------------------------------------------------
# The reconciliation the live path could not pass.
# --------------------------------------------------------------------------------------------


def test_a_session_that_carries_positions_reconciles() -> None:
    """The exact break: two carried holdings, no trades, and `end_session` must come back clean."""
    state = _carried()
    engine = _engine(state)
    engine.start_session(session_date=SESSION_DATE, timestamp=AT)

    report = engine.end_session(timestamp=CLOSE, close_prices=CLOSE_PRICES)

    assert report.reconciled, f"reconciliation failed: {report.reconciliation_errors}"
    assert report.reconciliation_errors == ()


def test_the_carried_positions_are_not_counted_as_today_s_trading() -> None:
    """Recording them in `_fills` would have reconciled too, and lied about fees and trade count.

    The entry cost was paid on the session that opened the position. A session report that counted
    it again would overstate today's costs by exactly the carried fees.
    """
    engine = _engine(_carried())
    engine.start_session(session_date=SESSION_DATE, timestamp=AT)

    report = engine.end_session(timestamp=CLOSE, close_prices=CLOSE_PRICES)

    assert report.total_fills_count == 0
    assert report.total_trades_count == 0
    assert report.total_fees_paid == Decimal("0.00")
    assert engine.carried_positions == {"ACME": 100, "BETA": 500}


def test_a_session_that_trades_on_top_of_carried_positions_reconciles() -> None:
    """Carried plus filled, not carried or filled: the reconciliation has to add them."""
    state = _carried()
    engine = _engine(state)
    engine.start_session(session_date=SESSION_DATE, timestamp=AT)
    engine.process_quote(_quote("ACME", Decimal("1010.00")))
    engine.submit_proposal(
        PaperProposal(
            proposal_id="p1",
            symbol="ACME",
            side=Side.SELL,
            quantity=40,
            order_type=OrderType.MARKET,
            decision_at=AT,
        )
    )
    engine.process_quote(_quote("ACME", Decimal("1010.00")))

    report = engine.end_session(timestamp=CLOSE, close_prices=CLOSE_PRICES)

    assert report.reconciled, f"reconciliation failed: {report.reconciliation_errors}"


def test_a_session_starting_flat_still_reconciles() -> None:
    """The baseline the change must not disturb."""
    engine = PaperPilotEngine(initial_cash=Decimal("1000000.00"), allow_short=False)
    engine.start_session(session_date=SESSION_DATE, timestamp=AT)

    report = engine.end_session(timestamp=CLOSE, close_prices={})

    assert report.reconciled
    assert engine.carried_positions == {}


def test_positions_cannot_be_carried_in_once_the_session_is_open() -> None:
    """The baseline must be fixed before trading, or it could be moved to hide a mismatch."""
    state = _carried()
    engine = _engine(state)
    engine.start_session(session_date=SESSION_DATE, timestamp=AT)
    assert engine.session_status is SessionStatus.ACTIVE

    with pytest.raises(RuntimeError, match="before the session opens"):
        engine.carry_in_positions(state.carry_forward_fills(AT))


def test_a_carried_sell_is_refused() -> None:
    """The carry path must not become a way to open a short by replaying one."""
    engine = PaperPilotEngine(initial_cash=Decimal("1000000.00"), allow_short=False)

    with pytest.raises(ValueError, match="must be replayed as a BUY"):
        engine.carry_in_positions(
            [Fill("c", "co", "ACME", Side.SELL, 10, Decimal("100.00"), Decimal("0.00"), AT)]
        )


def _quote(symbol: str, price: Decimal):
    from quant_system.core.domain import Quote

    return Quote(
        symbol=symbol,
        bid=price - Decimal("0.25"),
        ask=price + Decimal("0.25"),
        bid_size=10_000,
        ask_size=10_000,
        timestamp=AT,
        last_price=price,
    )


# --------------------------------------------------------------------------------------------
# The halt that lasted one morning.
# --------------------------------------------------------------------------------------------


def test_a_halt_survives_the_session_boundary(tmp_path) -> None:
    """It used to be forgotten overnight, which makes the switch decorative."""
    halted = state_from_ledger(
        PaperPortfolioState(cash=Decimal("1000000.00")),
        cash=Decimal("856320.14"),
        positions={},
        session_date=SESSION_DATE,
        session_realized_pnl=Decimal("-143679.86"),
        fees_paid=Decimal("0.00"),
        rebalanced=False,
        session_peak_equity=Decimal("1000000.00"),
        risk_halted=True,
        halt_reason="TOTAL_DRAWDOWN_BREACH",
    )
    assert halted.risk_halted is True
    assert halted.halted_on == SESSION_DATE
    assert halted.halt_reason == "TOTAL_DRAWDOWN_BREACH"

    path = tmp_path / "portfolio.json"
    save_portfolio(path, halted)
    reloaded = load_portfolio(path)
    assert reloaded is not None
    assert reloaded.risk_halted is True
    assert reloaded.halt_reason == "TOTAL_DRAWDOWN_BREACH"


def test_a_quiet_session_does_not_lift_a_halt() -> None:
    """Sticky by design. A switch that clears itself once the market calms is not a switch."""
    halted = PaperPortfolioState(
        cash=Decimal("856320.14"),
        risk_halted=True,
        halted_on=date(2026, 8, 20),
        halt_reason="TOTAL_DRAWDOWN_BREACH",
    )
    later = state_from_ledger(
        halted,
        cash=Decimal("856320.14"),
        positions={},
        session_date=SESSION_DATE,
        session_realized_pnl=Decimal("0.00"),
        fees_paid=Decimal("0.00"),
        rebalanced=False,
        risk_halted=False,
    )
    assert later.risk_halted is True
    assert later.halted_on == date(2026, 8, 20), "the original halt date must not be overwritten"


def test_the_runner_feeds_the_peak_from_marked_equity_not_the_governor_alone() -> None:
    """A source-level detector, because the previous version of this test proved nothing.

    It asserted `max()` behaves like `max()` -- `session_peak_equity` was already a parameter, so it
    passed verbatim against the parent commit. What actually changed is *which arguments the runner
    passes*, and that is what this checks: reverting to `governor.all_time_peak_equity` alone fails
    here.

    `update_peaks` is reachable only from `evaluate_order`, and a hold session proposes no orders,
    so without the marked figure the peak moves only via `max(previous, ledger_funding())` -- a cost
    figure. A book that rose 25% during a hold and then fell 20% from that high recorded no drawdown
    at all.
    """
    source = (
        Path(__file__).resolve().parent.parent / "scripts/run_paper_pilot_session.py"
    ).read_text(encoding="utf-8")
    tree = ast.parse(source)

    calls = [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "state_from_ledger"
    ]
    assert calls, "the runner no longer calls state_from_ledger; this detector has gone blind"

    peak_args = [
        kw.value for call in calls for kw in call.keywords if kw.arg == "session_peak_equity"
    ]
    assert peak_args, "no session_peak_equity is passed, so the carried peak is whatever cost says"

    for expression in peak_args:
        rendered = ast.unparse(expression)
        assert "total_equity" in rendered, (
            "session_peak_equity is computed without marked equity "
            f"({rendered!r}). A hold session proposes no orders, so the governor's own peak never "
            "moves and the high-water mark degenerates to a cost figure."
        )


def test_reconciliation_can_actually_report_failure() -> None:
    """Guards the verdict itself, which nothing did.

    Round three found that forcing `reconciled=True` unconditionally left all 1,166 tests passing:
    every test asserted a *successful* reconciliation, so the check could have been stubbed out
    entirely and the suite would not have noticed. This drives `end_session` into a genuine
    mismatch and requires it to say so.
    """
    state = _carried()
    engine = _engine(state)
    # Move the ledger behind the engine's back, so positions and the recorded baseline disagree.
    engine.ledger.process_fill(
        Fill("x", "xo", "ACME", Side.BUY, 25, Decimal("1000.00"), Decimal("0.00"), AT)
    )
    engine.start_session(session_date=SESSION_DATE, timestamp=AT)

    report = engine.end_session(timestamp=CLOSE, close_prices=CLOSE_PRICES)

    assert report.reconciled is False
    assert any("POSITION_MISMATCH" in error for error in report.reconciliation_errors), (
        f"expected a position mismatch, got {report.reconciliation_errors}"
    )
