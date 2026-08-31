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
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from pathlib import Path

import pytest

from quant_system.core.domain import Fill, OrderType, Side
from quant_system.execution.orderbook_sim import OrderBookSnapshot
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


def _governor_kwargs_resolved() -> dict[str, str]:
    """The runner's `PreTradeRiskGovernor(...)` arguments, with local names resolved.

    Resolution is the whole point. The previous version of this check read the *unresolved*
    expression: at `46c7bb67` the defect was written as `opening_equity = ledger_funding()` then
    `initial_equity=opening_equity`, so `ast.unparse` returned `'opening_equity'` and a search for
    "ledger_funding" passed against the very commit it named. Following a name back to what it was
    assigned is the difference between checking spelling and checking meaning.
    """
    source = (
        Path(__file__).resolve().parent.parent / "scripts/run_paper_pilot_session.py"
    ).read_text(encoding="utf-8")
    tree = ast.parse(source)

    call = next(
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "PreTradeRiskGovernor"
    )
    enclosing = next(
        fn
        for fn in ast.walk(tree)
        if isinstance(fn, ast.FunctionDef) and any(n is call for n in ast.walk(fn))
    )
    assignments: dict[str, ast.expr] = {
        target.id: node.value
        for node in ast.walk(enclosing)
        if isinstance(node, ast.Assign)
        for target in node.targets
        if isinstance(target, ast.Name)
    }

    def resolve(expression: ast.expr, depth: int = 0) -> str:
        if isinstance(expression, ast.Name) and expression.id in assignments and depth < 5:
            return resolve(assignments[expression.id], depth + 1)
        return ast.unparse(expression)

    return {kw.arg: resolve(kw.value) for kw in call.keywords if kw.arg}


def test_the_daily_peak_is_wired_to_marked_equity_not_a_cost_figure() -> None:
    """Kills four mutants the previous two versions of this test both survived.

    `initial_equity` must trace back to equity marked at this session's open. Seeded from
    `ledger_funding()` -- cash + holdings at cost + fees, invariant to price -- the 4% *daily* rule
    measures cumulative unrealized loss since inception, and a book 5.63% down over ten sessions
    with zero intraday movement halts on its first order. That order is the exit, so the losing
    book is then held with nothing able to sell it.
    """
    kwargs = _governor_kwargs_resolved()
    seed = kwargs.get("initial_equity", "")

    assert "ledger_funding" not in seed, (
        f"the daily peak is seeded from a cost figure: {seed!r}. It must be equity marked at the "
        "session open, or the daily rule measures the whole unrealized loss since inception."
    )
    assert "peak_equity" not in seed, (
        f"the daily peak is seeded from the carried all-time peak: {seed!r}. That is the original "
        "defect: the daily rule then measures a multi-session decline."
    )
    assert "opening_marks" in seed or "marked" in seed, (
        f"the daily peak does not trace back to marked equity: {seed!r}"
    )


def test_the_trailing_peak_still_carries_across_sessions() -> None:
    """Separating the peaks must not drop the carried one, or the 12% rule resets every morning."""
    trailing = _governor_kwargs_resolved().get("all_time_peak_equity", "")

    assert "peak_equity" in trailing, (
        f"the trailing peak no longer carries the persisted high-water mark: {trailing!r}. The "
        "total-drawdown switch would then measure from today and never trip."
    )


def test_a_risk_halt_is_reported_as_a_halt_not_a_success() -> None:
    """A halting session reconciles perfectly, so `reconciled` alone said SUCCESS and exited 0.

    It refuses every order rather than mis-booking one, which is exactly why the reconciliation
    passes. On an unattended weekday schedule that green exit was the operator's only signal that
    the pilot had permanently stopped.
    """
    source = (
        Path(__file__).resolve().parent.parent / "scripts/run_paper_pilot_session.py"
    ).read_text(encoding="utf-8")

    assert '"kill_switch_active": governor.is_killed' in source, (
        "the session payload no longer carries the kill-switch state, so no caller can see a halt"
    )
    assert "HALTED BY RISK KILL SWITCH" in source, "the banner cannot distinguish a halt"
    assert "return 9" in source, "a halting session must not exit 0"


def test_the_scheduler_wrapper_propagates_the_exit_code() -> None:
    """Task Scheduler recorded LastTaskResult 0 for every run, whatever the session returned.

    Confirmed against the real task: a Saturday run that must have returned 2 from the trading-day
    guard was recorded as 0. The one place an operator would look for trouble always showed
    success.
    """
    wrapper = (
        Path(__file__).resolve().parent.parent / "scripts/run_scheduled_paper_session.cmd"
    ).read_text(encoding="utf-8")

    assert "exit /b %RC%" in wrapper, (
        "the wrapper swallows the session's exit code; every scheduled run will look successful"
    )


# --------------------------------------------------------------------------------------------
# One quote source. The pilot uses Upstox or it does not trade.
# --------------------------------------------------------------------------------------------


def test_there_is_no_secondary_quote_source() -> None:
    """The Upstox token expired 2026-08-23 and eight days of sessions ran on a Yahoo scraper.

    The log said `Upstox API Token : CONFIGURED` throughout, because the check tested that the
    string was non-empty rather than that it worked. Any name missing from both feeds was priced at
    a flat Rs 1000.00 and labelled `REAL_NSE_ESTIMATE`. A record whose provenance is not what it
    claims is worse than no record.

    Checked against the parsed tree, not the raw text. A substring search cannot tell code from a
    comment, and the comment recording this history names the very strings being banned -- which is
    the third time in this file's history that a text search has stood in for a semantic one.
    """
    source = (
        Path(__file__).resolve().parent.parent / "scripts/run_paper_pilot_session.py"
    ).read_text(encoding="utf-8")
    tree = ast.parse(source)

    literals = {
        node.value
        for node in ast.walk(tree)
        if isinstance(node, ast.Constant) and isinstance(node.value, str)
    }
    names = {node.id for node in ast.walk(tree) if isinstance(node, ast.Name)} | {
        target.id
        for node in ast.walk(tree)
        if isinstance(node, ast.Assign)
        for target in node.targets
        if isinstance(target, ast.Name)
    }

    assert not any("yahoo" in text.lower() for text in literals), "a second quote source is back"
    assert "REAL_NSE_ESTIMATE" not in literals, "prices are being estimated and labelled as real"
    assert "DEFAULT_NIFTY_PRICES" not in names, "the hardcoded price table is back"
    assert not any(
        isinstance(node, ast.FunctionDef) and "nse_quote" in node.name for node in ast.walk(tree)
    ), "the fallback scraper is back"


def test_an_expired_token_stops_the_session_at_startup(monkeypatch) -> None:
    """Presence is not validity, and an unattended schedule has nobody to spot the difference."""
    import importlib.util
    import os
    from unittest import mock

    spec = importlib.util.spec_from_file_location(
        "_rps", Path(__file__).resolve().parent.parent / "scripts/run_paper_pilot_session.py"
    )
    assert spec and spec.loader
    runner = importlib.util.module_from_spec(spec)
    # The runner loads `.env` into `os.environ` at import time. Executing it inside a snapshot keeps
    # that out of the rest of the suite -- without this it set UPSTOX_ACCESS_TOKEN for every later
    # test, and two Upstox tests that require an absent token failed depending on ordering.
    with mock.patch.dict(os.environ, os.environ.copy(), clear=True):
        spec.loader.exec_module(runner)

    # A structurally valid JWT whose expiry is in the past.
    import base64 as _b64
    import json as _json

    def _token(exp: int) -> str:
        head = _b64.urlsafe_b64encode(b'{"alg":"HS256"}').decode().rstrip("=")
        body = _b64.urlsafe_b64encode(_json.dumps({"exp": exp}).encode()).decode().rstrip("=")
        return f"{head}.{body}.signature"

    with pytest.raises(runner.QuoteFeedError, match="expired"):
        runner.assert_upstox_usable(_token(1_755_000_000))  # 2025-08-12

    # Both are cleared explicitly: `resolve_upstox_token` treats "" as absent and falls through to
    # the environment, so a developer machine with either token in `.env` would otherwise decide
    # the result of this assertion.
    monkeypatch.delenv("UPSTOX_ACCESS_TOKEN", raising=False)
    monkeypatch.delenv("UPSTOX_ANALYTICS_TOKEN", raising=False)
    with pytest.raises(runner.QuoteFeedError, match="no Upstox token"):
        runner.assert_upstox_usable("")

    with pytest.raises(runner.QuoteFeedError, match="not a JWT"):
        runner.assert_upstox_usable("plainly-not-a-token")

    # The analytics token is preferred over the access token, and preferred even when the access
    # token has expired -- which is the whole point of it. Upstox issues the analytics token for
    # about a year while the access token dies at 03:30 IST the morning after issue, so a session
    # on an unattended schedule must not abort merely because nobody refreshed the daily one.
    future = int(datetime.now(UTC).timestamp()) + 86_400 * 300
    monkeypatch.setenv("UPSTOX_ACCESS_TOKEN", _token(1_755_000_000))  # long expired
    monkeypatch.setenv("UPSTOX_ANALYTICS_TOKEN", _token(future))
    runner.assert_upstox_usable()  # must not raise
    resolved, source = runner.resolve_upstox_token()
    assert source == "UPSTOX_ANALYTICS_TOKEN"
    assert resolved == _token(future)

    # With no analytics token, the expired access token still stops the session, and the message
    # names the variable that failed rather than a generic "token".
    monkeypatch.delenv("UPSTOX_ANALYTICS_TOKEN", raising=False)
    with pytest.raises(runner.QuoteFeedError, match="UPSTOX_ACCESS_TOKEN expired"):
        runner.assert_upstox_usable()

    # An explicit argument still overrides both, so `--upstox-token` is unaffected.
    monkeypatch.setenv("UPSTOX_ANALYTICS_TOKEN", _token(future))
    _, explicit_source = runner.resolve_upstox_token("supplied-directly")
    assert explicit_source == "explicit --upstox-token"

    # A revoked or mis-pasted analytics token is caught by the same expiry rule, not waved through
    # for being the preferred class.
    monkeypatch.setenv("UPSTOX_ANALYTICS_TOKEN", _token(1_755_000_000))
    with pytest.raises(runner.QuoteFeedError, match="UPSTOX_ANALYTICS_TOKEN expired"):
        runner.assert_upstox_usable()


def test_net_pnl_is_equity_minus_capital_not_realized_plus_unrealized() -> None:
    """The identity the live tile and the session report both depend on.

    `realized + unrealized` **excludes the statutory fees already paid**. Measured live on
    2026-08-31 it reported -205.88 against a true -1,279.94, with the fees tile beside it showing
    1,074.06 -- the exact gap. Both numbers were on screen and did not reconcile, and the headline
    understated the loss by precisely the cost of trading.

    Equity minus capital cannot double-count: a closed lot's fees are already inside
    `realized_pnl`, so subtracting `total_fees_paid` from that sum would charge them twice.
    """
    engine = PaperPilotEngine(initial_cash=Decimal("1000000.00"), allow_short=False)
    engine.start_session(session_date=SESSION_DATE, timestamp=AT)

    def book(at: datetime) -> OrderBookSnapshot:
        return OrderBookSnapshot.from_levels(
            symbol="ACME",
            timestamp=at,
            bids=[(Decimal("999.75"), 10_000)],
            asks=[(Decimal("1000.25"), 10_000)],
            last_price=Decimal("1000.00"),
        )

    engine.process_quote(book(AT))
    engine.submit_proposal(
        PaperProposal(
            proposal_id="buy1",
            symbol="ACME",
            side=Side.BUY,
            quantity=100,
            order_type=OrderType.MARKET,
            decision_at=AT,
        )
    )
    # A second quote a minute later: the simulator models queue priority, so an order submitted
    # against the current book does not fill on that same book.
    later = AT + timedelta(minutes=1)
    fills = engine.process_quote(book(later), current_time=later)
    assert fills, "the order never filled, so there is no fee and this test proves nothing"

    report = engine.end_session(timestamp=CLOSE, close_prices={"ACME": Decimal("1000.00")})

    assert report.total_fees_paid > Decimal("0.00"), "no fee was charged; this proves nothing"

    naive = report.total_realized_pnl + report.total_unrealized_pnl
    correct = report.total_equity - report.initial_cash

    assert correct == naive - report.total_fees_paid, (
        "the two definitions should differ by exactly the fees paid on the open position"
    )
    assert correct < naive, "equity-based P&L must be the more conservative of the two"


# --------------------------------------------------------------------------------------------
# A network blip must not end the trading day, and an abort must not report success.
# --------------------------------------------------------------------------------------------


def test_a_transient_quote_failure_does_not_end_the_session() -> None:
    """One SSL handshake timeout killed a session that had been trading for two hours.

    The `QuoteFeedError` refusal was written for *startup*, where an unusable feed means the
    session must not begin. Applied to every poll, it made a routine network blip fatal -- and the
    3-second per-batch timeout made blips ordinary rather than exceptional.
    """
    source = (
        Path(__file__).resolve().parent.parent / "scripts/run_paper_pilot_session.py"
    ).read_text(encoding="utf-8")
    tree = ast.parse(source)

    names = {
        target.id
        for node in ast.walk(tree)
        if isinstance(node, ast.Assign)
        for target in node.targets
        if isinstance(target, ast.Name)
    }
    assert "MAX_CONSECUTIVE_QUOTE_FAILURES" in names, (
        "no tolerance for a failed poll: a single timeout will end the day again"
    )
    assert "_QUOTE_TIMEOUT_SECONDS" in names, "the per-batch timeout is still hardcoded"

    # The loop must catch the refusal rather than let it unwind the session.
    handlers = [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.ExceptHandler)
        and isinstance(node.type, ast.Name)
        and node.type.id == "QuoteFeedError"
    ]
    assert handlers, "the trading loop does not catch QuoteFeedError, so one poll failure is fatal"


def test_an_aborted_session_is_not_reported_as_a_success() -> None:
    """The 14:21 abort printed `Session Concluded & Reconciled: SUCCESS` and exited 0.

    Third occurrence of this class in one day. The session must still close and reconcile -- an
    abrupt exit would leave the book unpersisted -- but nothing downstream may call it clean.
    """
    source = (
        Path(__file__).resolve().parent.parent / "scripts/run_paper_pilot_session.py"
    ).read_text(encoding="utf-8")
    tree = ast.parse(source)

    literals = {
        node.value
        for node in ast.walk(tree)
        if isinstance(node, ast.Constant) and isinstance(node.value, str)
    }
    assert "aborted" in literals, "the result payload does not carry an abort flag"
    assert "[PAPER PILOT ABORTED]" in literals, "the banner cannot distinguish an abort"

    returns = {
        node.value.value
        for node in ast.walk(tree)
        if isinstance(node, ast.Return)
        and isinstance(node.value, ast.Constant)
        and isinstance(node.value.value, int)
    }
    assert 10 in returns, "an aborted session must not exit 0"


def test_a_partial_quote_batch_failure_fails_the_poll() -> None:
    """The tolerance added yesterday did not cover the case that actually happened.

    `fetch_upstox_live_quotes` raised only when it got **nothing**, so a poll that lost a chunk
    returned normally and the caller reset `consecutive_quote_failures` to zero. Live on
    2026-08-31 at 13:29 and 13:44 two chunks failed -- 300 of 500 symbols missing, twice -- and the
    session priced the absent names from quotes minutes old, because the previous values simply
    stayed in `base_market`.

    A chunk that errored tells us nothing about its symbols and must be retried. A symbol missing
    from a response that otherwise succeeded is genuinely unquotable and retrying changes nothing.
    Only the first is a failure of the poll, and the test drives exactly that split.
    """
    import importlib.util
    import os
    import urllib.request
    from unittest import mock

    spec = importlib.util.spec_from_file_location(
        "_rps_partial",
        Path(__file__).resolve().parent.parent / "scripts/run_paper_pilot_session.py",
    )
    assert spec and spec.loader
    runner = importlib.util.module_from_spec(spec)
    with mock.patch.dict(os.environ, os.environ.copy(), clear=True):
        spec.loader.exec_module(runner)

    symbols = [f"SYM{n:03d}" for n in range(150)]  # two chunks at chunk_size 100
    runner.UPSTOX_INSTRUMENT_KEYS = {s: f"NSE_EQ|{s}" for s in symbols}

    calls = {"n": 0}

    def one_good_chunk_then_a_timeout(*_args, **_kwargs):
        calls["n"] += 1
        if calls["n"] == 1:
            raise TimeoutError("_ssl.c:1015: The handshake operation timed out")
        raise TimeoutError("_ssl.c:1015: The handshake operation timed out")

    with mock.patch.object(urllib.request, "urlopen", one_good_chunk_then_a_timeout):
        with pytest.raises(runner.QuoteFeedError, match="quote batches failed"):
            runner.fetch_upstox_live_quotes(symbols, access_token="t")

    assert calls["n"] == 2, (
        "a failed chunk stopped the loop; the remaining batches must still be attempted so the "
        "error can say how much of the feed was lost"
    )


def _runner_tree() -> ast.Module:
    return ast.parse(
        (Path(__file__).resolve().parent.parent / "scripts/run_paper_pilot_session.py").read_text(
            encoding="utf-8"
        )
    )


def _assigned(name: str) -> str:
    """The expression a module-level-visible local is assigned, rendered."""
    return next(
        ast.unparse(node.value)
        for node in ast.walk(_runner_tree())
        if isinstance(node, ast.Assign)
        for target in node.targets
        if isinstance(target, ast.Name) and target.id == name
    )


def test_quote_lookups_are_pinned_to_the_symbols_the_feed_returned() -> None:
    """Two missing quotes out of five hundred aborted the session before a single order.

    `KeyError: '360ONE'` on 2026-08-31. Removing the fabricated price table was right -- it invented
    a flat Rs 1000.00 and labelled it a real exchange price -- but every consumer that silently
    depended on it was left indexing `base_market` by every universe member. Fixing the *cause* of
    that day's missing symbol left the crash itself in place.

    **These are four located facts, not an analysis.** Five attempts at a general "is this lookup
    guarded?" check were each wrong in a new way: one allowlisted names instead of resolving them;
    one matched `priced` as a substring of `unpriced`; one joined every guard in a loop and resolved
    identifiers until an unrelated chain satisfied it; one expanded definitions into a blob where
    `in base_market` leaked in from elsewhere. Each passed, and each was worthless. Asserting the
    specific things that must be true is decidable, and it is what the entry-loop check already did
    correctly.
    """
    tree = _runner_tree()

    # 1. The filtered list really filters.
    assert "in base_market" in _assigned("priced"), (
        f"`priced` is assigned {_assigned('priced')!r}, which does not filter by quote membership"
    )

    # 2. The intraday panels rank only what was priced.
    assert "priced" in _assigned("sorted_gainers"), (
        f"`sorted_gainers` is built from {_assigned('sorted_gainers')!r}; ranking the whole "
        "universe reintroduces the lookup that crashed the session"
    )

    # 3. The returns loop iterates the filtered list.
    returns_loop = next(
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.For)
        and any(
            isinstance(inner, ast.Subscript)
            and isinstance(inner.value, ast.Name)
            and inner.value.id == "base_market"
            for inner in ast.walk(node)
        )
        and "quote_state" in ast.unparse(node)
    )
    assert ast.unparse(returns_loop.iter) == "priced", (
        f"the intraday returns loop iterates {ast.unparse(returns_loop.iter)!r}, not `priced`"
    )

    # 4. The entry loop refuses to size a pick it has no price for.
    entry_loop = next(
        node
        for node in ast.walk(tree)
        # startswith, not `in`: the exit loop's iterable also mentions `top_picks`.
        if isinstance(node, ast.For) and ast.unparse(node.iter).startswith("top_picks")
    )
    guards = [
        ast.unparse(statement.test)
        for statement in ast.walk(entry_loop)
        if isinstance(statement, ast.If)
        and any(isinstance(inner, ast.Continue) for inner in ast.walk(statement))
    ]
    assert any("not in base_market" in guard for guard in guards), (
        f"the entry loop has no membership guard before it prices a pick; its skip conditions are "
        f"{guards}. A selected name the feed did not return would be indexed blindly."
    )


def test_a_rebalance_that_only_exits_is_not_a_completed_rebalance() -> None:
    """Every exit filled, every entry skipped as unaffordable, book flat -- and it counted.

    `total_fills_count > 0` was satisfied by the exits alone, so the pilot went 100% to cash, paid a
    full exit round trip, reset the hold clock and stamped `last_rebalance_on`. Going to cash is not
    a rule the screen contains; it cannot be the outcome that marks one as executed.

    Located rather than analysed: the flag's definition is read from the source and its three
    required parts asserted. The behaviour itself is pinned by `test_paper_portfolio.py`, which
    drives `state_from_ledger` with the flag both ways.
    """
    tree = _runner_tree()
    definition = next(
        ast.unparse(node.value)
        for node in ast.walk(tree)
        if isinstance(node, ast.Assign)
        for target in node.targets
        if isinstance(target, ast.Name) and target.id == "executed_rebalance"
    )

    assert "engine.positions" in definition, (
        f"`executed_rebalance` is {definition!r}. It does not require the book to hold anything, so "
        "a rebalance that sold everything and bought nothing still counts as executed."
    )
    assert "entry_fills" in definition, (
        f"`executed_rebalance` is {definition!r}. Exits alone must not satisfy it."
    )
    assert "total_fills_count" not in definition, (
        "the total fill count includes exits, which is exactly what made an all-exits rebalance "
        "look complete"
    )

    entry_fills = next(
        ast.unparse(node.value)
        for node in ast.walk(tree)
        if isinstance(node, ast.Assign)
        for target in node.targets
        if isinstance(target, ast.Name) and target.id == "entry_fills"
    )
    assert "Side.BUY" in entry_fills and "carry_" in entry_fills, (
        f"`entry_fills` is {entry_fills!r}; it must count today's buys only, not the carry-forward "
        "replay, which would make every held session look like it entered."
    )
