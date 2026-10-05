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

    import io
    import json as _json

    calls = {"n": 0}

    class _Response(io.BytesIO):
        def __enter__(self):
            return self

        def __exit__(self, *_exc):
            return False

    def one_good_chunk_then_a_timeout(*_args, **_kwargs):
        """Chunk 1 genuinely succeeds. Chunk 2 times out.

        Both branches used to raise, so there was no good chunk and the test could not distinguish
        `if failed_chunks:` from `if failed_chunks and not results:` -- the mutant that reproduces
        the original defect exactly. The test that gates this behaviour could not see its own
        scenario.
        """
        calls["n"] += 1
        if calls["n"] == 1:
            body = {
                "status": "success",
                "data": {
                    f"NSE_EQ|{s}": {"last_price": 100.0 + n, "volume": 1000}
                    for n, s in enumerate(symbols[:100])
                },
            }
            return _Response(_json.dumps(body).encode())
        raise TimeoutError("_ssl.c:1015: The handshake operation timed out")

    with mock.patch.object(urllib.request, "urlopen", one_good_chunk_then_a_timeout):
        with pytest.raises(runner.QuoteFeedError, match="quote batches failed") as raised:
            runner.fetch_upstox_live_quotes(symbols, access_token="t")

    assert calls["n"] == 2, (
        "a failed chunk stopped the loop; the remaining batches must still be attempted so the "
        "error can say how much of the feed was lost"
    )
    # The half that *did* arrive is what makes this a partial failure rather than a total one.
    # Without this the assertion above passes against a loader that returned 100 good quotes and
    # called the poll a success.
    assert "100 of 150 symbols returned" in str(raised.value), (
        f"the error must report the partial coverage it actually got: {raised.value}"
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

    # The entry loop's own guard is not asserted here any more. It was, and the assertion was
    # defeated by `if sym not in base_market and False:` -- which keeps every string intact while
    # disabling the check. `test_a_selected_name_with_no_quote_is_sized_at_zero` drives
    # `entry_quantity` instead, which no string-preserving edit can satisfy.


def test_a_held_name_with_no_quote_does_not_kill_the_session_at_close() -> None:
    """It killed it *after* a full day of trading, and after the abort handler.

    `DecimalLedger` refuses to mark a held position it has no price for -- correctly; it will not
    fabricate a market value. But `final_prices` was built only from quoted names, so one held name
    the feed omitted raised `LedgerInvariantViolation` at `end_session`: the fills had happened, no
    report was written, and `save_portfolio` was never reached. Two of five hundred names were
    unquoted on 2026-08-31 and 97 are now held.

    Marking at cost reports zero unrealized P&L for that name rather than a number nobody can
    source, and the name is returned so the session can say which marks are real.
    """
    import importlib.util
    import os
    from unittest import mock

    spec = importlib.util.spec_from_file_location(
        "_rps_marks", Path(__file__).resolve().parent.parent / "scripts/run_paper_pilot_session.py"
    )
    assert spec and spec.loader
    runner = importlib.util.module_from_spec(spec)
    with mock.patch.dict(os.environ, os.environ.copy(), clear=True):
        spec.loader.exec_module(runner)

    state = _carried()
    engine = _engine(state)
    engine.start_session(session_date=SESSION_DATE, timestamp=AT)

    # ACME is quoted; BETA is not -- exactly the shape that aborted the session.
    quoted = {"ACME": Decimal("1010.00")}
    marks, fell_back = runner.marks_for_open_positions(quoted, engine.positions)

    assert fell_back == ["BETA"], f"expected BETA to be named as unmarked, got {fell_back}"
    assert marks["BETA"] == engine.positions["BETA"].average_price, (
        "an unquoted holding must be marked at its own cost, so its unrealized P&L is zero"
    )

    report = engine.end_session(timestamp=CLOSE, close_prices=marks)
    assert report.reconciled, f"reconciliation failed: {report.reconciliation_errors}"


def test_marks_are_not_invented_for_names_that_are_not_held() -> None:
    """The fallback covers open positions only; it is not a general price fabricator."""
    import importlib.util
    import os
    from unittest import mock

    spec = importlib.util.spec_from_file_location(
        "_rps_marks2", Path(__file__).resolve().parent.parent / "scripts/run_paper_pilot_session.py"
    )
    assert spec and spec.loader
    runner = importlib.util.module_from_spec(spec)
    with mock.patch.dict(os.environ, os.environ.copy(), clear=True):
        spec.loader.exec_module(runner)

    marks, fell_back = runner.marks_for_open_positions({"ACME": Decimal("1010.00")}, {})

    assert marks == {"ACME": Decimal("1010.00")}
    assert fell_back == []


def test_http_200_without_a_success_payload_is_a_failed_chunk() -> None:
    """A 200 carrying an error body used to fall through in silence.

    `if data.get("status") == "success" and "data" in data:` simply did not match, the loop moved
    on, and the poll returned whatever the other chunks had -- so the consecutive-failure counter
    reset on the very poll that lost 100 of 150 symbols.

    **The discriminating case needs one good chunk and one bad one.** A first version of this test
    used a single chunk and asserted only the exception *type*; both the fixed and the broken code
    raise there, because when every chunk is bad `results` is empty and the older
    "no quotes for any" guard fires instead. It passed against a faithful reproduction of the
    defect. Mutation caught it; nothing else would have.
    """
    import importlib.util
    import io
    import json as _json
    import os
    import urllib.request
    from unittest import mock

    spec = importlib.util.spec_from_file_location(
        "_rps_200", Path(__file__).resolve().parent.parent / "scripts/run_paper_pilot_session.py"
    )
    assert spec and spec.loader
    runner = importlib.util.module_from_spec(spec)
    with mock.patch.dict(os.environ, os.environ.copy(), clear=True):
        spec.loader.exec_module(runner)

    symbols = [f"SYM{n:03d}" for n in range(150)]  # two chunks at chunk_size 100
    runner.UPSTOX_INSTRUMENT_KEYS = {s: f"NSE_EQ|{s}" for s in symbols}

    good = {
        "status": "success",
        "data": {
            f"NSE_EQ|{sym}": {
                "last_price": 100.0,
                "ohlc": {"high": 101.0, "low": 99.0, "close": 100.0},
                "volume": 50_000,
            }
            for sym in symbols[:100]
        },
    }
    # An error envelope that still carries a `data` key. Without this case a check on `status`
    # alone looks equivalent, because every other bad shape fails later on `data["data"]` anyway --
    # this is the one where a status-only test would parse an error body as quotes.
    bad = {
        "status": "error",
        "errors": [{"message": "too many requests"}],
        "data": {f"NSE_EQ|{sym}": {"last_price": 0.0} for sym in symbols[100:]},
    }

    class _Response(io.BytesIO):
        def __enter__(self):
            return self

        def __exit__(self, *_exc):
            return False

    calls = {"n": 0}

    def first_good_then_an_error_envelope(*_args, **_kwargs):
        calls["n"] += 1
        return _Response(_json.dumps(good if calls["n"] == 1 else bad).encode())

    with mock.patch.object(urllib.request, "urlopen", first_good_then_an_error_envelope):
        with pytest.raises(runner.QuoteFeedError, match="quote batches failed"):
            runner.fetch_upstox_live_quotes(symbols, access_token="t")

    assert calls["n"] == 2, "both chunks must be attempted"


def test_a_well_formed_empty_success_is_absence_not_transport_failure() -> None:
    """The other side of the same split, and it must not consume the retry budget."""
    import importlib.util
    import io
    import json as _json
    import os
    import urllib.request
    from unittest import mock

    spec = importlib.util.spec_from_file_location(
        "_rps_empty", Path(__file__).resolve().parent.parent / "scripts/run_paper_pilot_session.py"
    )
    assert spec and spec.loader
    runner = importlib.util.module_from_spec(spec)
    with mock.patch.dict(os.environ, os.environ.copy(), clear=True):
        spec.loader.exec_module(runner)

    symbols = ["SYM001", "SYM002"]
    runner.UPSTOX_INSTRUMENT_KEYS = {s: f"NSE_EQ|{s}" for s in symbols}

    class _Response(io.BytesIO):
        def __enter__(self):
            return self

        def __exit__(self, *_exc):
            return False

    with mock.patch.object(
        urllib.request,
        "urlopen",
        lambda *_a, **_k: _Response(_json.dumps({"status": "success", "data": {}}).encode()),
    ):
        with pytest.raises(runner.QuoteFeedError, match="no quotes for any"):
            runner.fetch_upstox_live_quotes(symbols, access_token="t")


def _runner_module():
    import importlib.util
    import os
    from unittest import mock

    spec = importlib.util.spec_from_file_location(
        "_rps_rule", Path(__file__).resolve().parent.parent / "scripts/run_paper_pilot_session.py"
    )
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    with mock.patch.dict(os.environ, os.environ.copy(), clear=True):
        spec.loader.exec_module(module)
    return module


def test_a_rebalance_counts_only_when_the_book_became_the_selection() -> None:
    """Every shape that has been wrong, driven through the real rule.

    `total_fills_count > 0` was satisfied by the exits alone; `bool(entry_fills)` by one fill of
    four, leaving 76.3% in cash after paying to get there. Coverage answers all of them.
    """
    runner = _runner_module()
    picks = {f"P{n}" for n in range(4)}

    assert runner.rebalance_executed(picks, set()) is False, "all exits, nothing bought"
    assert runner.rebalance_executed(picks, {"P0"}) is False, "one entry of four is 25%"
    assert runner.rebalance_executed(picks, picks) is True, "a re-rank that keeps everything"

    hundred = {f"N{n}" for n in range(100)}
    truncated = set(list(hundred)[:97])  # three names too expensive for one share
    assert runner.rebalance_executed(hundred, truncated) is True, (
        "integer share truncation legitimately drops the priciest names; 97 of 100 is the "
        "portfolio the model chose"
    )

    assert runner.rebalance_executed(set(), set()) is False, "no selection is not a rebalance"


def test_the_runner_decides_the_rebalance_flag_with_that_rule() -> None:
    """Located, because a behavioural test of the rule cannot see the runner ignoring it.

    The rule above is decidable and strong; this is the narrow, decidable half that pins the runner
    to it. A mutant reverting the flag to `bool(entry_fills)` changes only this line, and nothing
    behavioural would catch it.
    """
    definition = next(
        ast.unparse(node.value)
        for node in ast.walk(_runner_tree())
        if isinstance(node, ast.Assign)
        for target in node.targets
        if isinstance(target, ast.Name) and target.id == "executed_rebalance"
    )
    assert "rebalance_executed(" in definition, (
        f"`executed_rebalance` is {definition!r}; it must come from the shared rule, not be "
        "recomputed inline where it can drift back to counting fills"
    )


def test_a_restart_reuses_only_todays_anchor() -> None:
    """Driven, because a guard's presence is checkable from source and its effect is not.

    `daily_anchor_on != session_date` keeps every string a located assertion looks for while
    inverting the decision -- it survived that assertion, and this is what kills it.
    """
    runner = _runner_module()
    today, yesterday = date(2026, 9, 1), date(2026, 8, 31)

    todays = PaperPortfolioState(
        cash=Decimal("50000.00"),
        daily_anchor_on=today,
        daily_anchor_equity=Decimal("1000000.00"),
    )
    assert runner.anchor_to_reuse(todays, today) == Decimal("1000000.00")

    stale = PaperPortfolioState(
        cash=Decimal("50000.00"),
        daily_anchor_on=yesterday,
        daily_anchor_equity=Decimal("1000000.00"),
    )
    assert runner.anchor_to_reuse(stale, today) is None, (
        "yesterday's baseline must not govern today; the daily rule would measure from the wrong "
        "morning"
    )

    never = PaperPortfolioState(cash=Decimal("50000.00"))
    assert runner.anchor_to_reuse(never, today) is None

    zeroed = PaperPortfolioState(
        cash=Decimal("50000.00"), daily_anchor_on=today, daily_anchor_equity=Decimal("0.00")
    )
    assert runner.anchor_to_reuse(zeroed, today) is None, "a zero baseline disables the daily rule"


def test_a_selected_name_with_no_quote_is_sized_at_zero() -> None:
    """The entry guard, driven rather than located.

    `if sym not in base_market and False:` keeps the guard's text intact while disabling it, and
    that mutant survived the located assertion. Sizing is the decision that actually matters.
    """
    runner = _runner_module()
    marks = {"ACME": Decimal("100.00")}
    allocation = Decimal("9500.00")
    cash = Decimal("500000.00")

    assert runner.entry_quantity("ACME", marks, allocation, cash) == 95
    assert runner.entry_quantity("MISSING", marks, allocation, cash) == 0, (
        "a name the feed did not return has no price to size against; it must not be entered"
    )
    assert runner.entry_quantity("ZERO", {"ZERO": Decimal("0.00")}, allocation, cash) == 0
    assert (
        runner.entry_quantity("PRICEY", {"PRICEY": Decimal("48600.00")}, allocation, cash) == 0
    ), "one share costs more than the allocation, which is how a dear name drops out"

    # Cash-bound rather than allocation-bound.
    assert runner.entry_quantity("ACME", marks, allocation, Decimal("1000.00")) == 9


# --------------------------------------------------------------------------------------------
# A payload that cannot be priced is skipped, not stamped as a real exchange price. (R6-02, R6-15)
# --------------------------------------------------------------------------------------------


def _quote_runner():
    import importlib.util
    import os
    from unittest import mock

    spec = importlib.util.spec_from_file_location(
        "_rps_quotes", Path(__file__).resolve().parent.parent / "scripts/run_paper_pilot_session.py"
    )
    assert spec and spec.loader
    runner = importlib.util.module_from_spec(spec)
    with mock.patch.dict(os.environ, os.environ.copy(), clear=True):
        spec.loader.exec_module(runner)
    return runner


_GOOD_QUOTE = {
    "last_price": 1010.25,
    "ohlc": {"high": 1020.0, "low": 1000.0, "close": 1005.0},
    "volume": 500000,
    "depth": {"buy": [{"price": 1010.10}], "sell": [{"price": 1010.40}]},
}


@pytest.mark.parametrize(
    "bad_last_price",
    [
        pytest.param({"last_price": 0}, id="explicit zero"),
        pytest.param({"last_price": 0.0}, id="explicit zero float"),
        pytest.param({}, id="absent altogether"),
        pytest.param({"last_price": None}, id="null"),
        pytest.param({"last_price": -12.5}, id="negative"),
        pytest.param({"last_price": "N/A"}, id="non-numeric string"),
        pytest.param({"last_price": True}, id="a bool, which is an int in Python"),
    ],
)
def test_a_payload_with_no_usable_price_is_skipped(bad_last_price) -> None:
    """It used to become Rs 0.00 stamped `UPSTOX_LIVE_FEED`.

    For a *held* name that silently removes the position's whole value from the marked equity, the
    risk baseline and the session report at once.
    """
    runner = _quote_runner()
    payload = {**_GOOD_QUOTE, **bad_last_price}
    if "last_price" not in bad_last_price:
        payload.pop("last_price")

    assert runner.parse_quote_payload(payload) is None


def test_a_good_payload_is_still_priced_and_still_labelled() -> None:
    """The guard must not be a refusal of everything."""
    runner = _quote_runner()

    parsed = runner.parse_quote_payload(_GOOD_QUOTE)

    assert parsed is not None
    assert parsed["price"] == Decimal("1010.25")
    assert parsed["previous_close"] == Decimal("1005.00")
    assert parsed["source"] == "UPSTOX_LIVE_FEED"
    assert parsed["spread"] == Decimal("0.30")


def test_a_negative_depth_price_does_not_end_the_session(caplog) -> None:
    """`OrderBookSnapshot.from_levels` refuses a negative bid -- and that killed the whole day.

    One zero-priced name anywhere in the 500 aborted the session two minutes in. Ten such mornings
    consume the model's entire ten-session hold without the book ever being marked to a real close.
    """
    runner = _quote_runner()
    payload = {**_GOOD_QUOTE, "depth": {"buy": [{"price": -0.02}], "sell": [{"price": 1010.40}]}}

    parsed = runner.parse_quote_payload(payload)

    assert parsed is not None, "a bad depth level must not discard an otherwise usable quote"
    assert parsed["price"] == Decimal("1010.25")
    assert parsed["spread"] == Decimal("0.05"), "an unusable ladder falls back to the floor spread"
    assert all(value > 0 for value in parsed.values() if isinstance(value, Decimal))


def test_a_deeper_usable_level_is_taken_when_the_best_one_is_not() -> None:
    runner = _quote_runner()
    payload = {
        **_GOOD_QUOTE,
        "depth": {
            "buy": [{"price": 0}, {"price": 1009.00}],
            "sell": [{"price": -1}, {"price": 1011.00}],
        },
    }

    parsed = runner.parse_quote_payload(payload)

    assert parsed is not None
    assert parsed["spread"] == Decimal("2.00")


def test_missing_ohlc_falls_back_to_the_traded_price_not_to_zero() -> None:
    """`ohlc.get("high", price)` was already right; a zero high would misstate the day's range."""
    runner = _quote_runner()

    parsed = runner.parse_quote_payload({"last_price": 1010.25})

    assert parsed is not None
    assert parsed["high"] == parsed["low"] == parsed["previous_close"] == Decimal("1010.25")


def test_an_absent_volume_does_not_invent_one() -> None:
    """It defaulted to 100000 -- a fabricated liquidity figure that sizes the simulated book."""
    runner = _quote_runner()

    parsed = runner.parse_quote_payload({"last_price": 1010.25})

    assert parsed is not None
    assert parsed["volume"] == 0
    assert parsed["depth"] >= 100


def test_a_skipped_symbol_is_reported_to_the_operator(caplog) -> None:
    """Silently dropping a name is how the Rs 0.00 defect stayed invisible for a week.

    Nothing downstream can distinguish "the feed omitted it" from "we refused its payload", so the
    refusal has to be said out loud where an unattended schedule leaves a record.
    """
    import io
    import json as _json
    import logging
    import urllib.request
    from unittest import mock

    runner = _quote_runner()
    symbols = ["GOODNAME", "ZEROPRICE"]
    runner.UPSTOX_INSTRUMENT_KEYS = {s: f"NSE_EQ|{s}" for s in symbols}

    class _Response(io.BytesIO):
        def __enter__(self):
            return self

        def __exit__(self, *_exc):
            return False

    body = {
        "status": "success",
        "data": {
            "NSE_EQ|GOODNAME": {"last_price": 1010.25, "volume": 1000},
            "NSE_EQ|ZEROPRICE": {"last_price": 0, "volume": 1000},
        },
    }

    with caplog.at_level(logging.WARNING):
        with mock.patch.object(
            urllib.request, "urlopen", lambda *_a, **_k: _Response(_json.dumps(body).encode())
        ):
            results = runner.fetch_upstox_live_quotes(symbols, access_token="t")

    assert set(results) == {"GOODNAME"}, "the unpriceable name must not be in the marks"
    assert "ZEROPRICE" in caplog.text
    assert "could not be priced" in caplog.text


# --------------------------------------------------------------------------------------------
# The opening fetch gets the same retry budget the loop has. (R6-19)
# --------------------------------------------------------------------------------------------


def test_a_transient_failure_at_startup_does_not_lose_the_day() -> None:
    """One chunk of five timing out during the handshake used to end the session before it began.

    That is the failure that actually ended 2026-08-31. A transient failure at 09:00 is not more
    meaningful than the same failure at 09:05, where the loop already tolerates five of them.
    """
    runner = _quote_runner()
    slept: list[float] = []
    calls = {"n": 0}

    def flaky(_universe, access_token=None):
        calls["n"] += 1
        if calls["n"] < 3:
            raise runner.QuoteFeedError("_ssl.c:1015: The handshake operation timed out")
        return {"ACME": {"price": Decimal("1010.25")}}

    result = runner.fetch_quotes_with_retry(
        ["ACME"], access_token="t", fetch=flaky, sleep=slept.append
    )

    assert result == {"ACME": {"price": Decimal("1010.25")}}
    assert calls["n"] == 3, "it must actually retry, not swallow the failure"
    assert slept == [5.0, 5.0], "it must wait between attempts rather than hammering the provider"


def test_a_feed_that_is_genuinely_down_still_ends_the_session() -> None:
    """The budget is a tolerance for a blip, not permission to open a session with no marks."""
    runner = _quote_runner()

    def always_fails(_universe, access_token=None):
        raise runner.QuoteFeedError("connection refused")

    with pytest.raises(runner.QuoteFeedError, match="failed 5 times in a row"):
        runner.fetch_quotes_with_retry(
            ["ACME"], access_token="t", fetch=always_fails, sleep=lambda _s: None
        )


def test_the_startup_budget_is_the_same_number_as_the_loop_budget() -> None:
    """Two different tolerances for the same failure would be a decision nobody made."""
    runner = _quote_runner()
    calls = {"n": 0}

    def counted(_universe, access_token=None):
        calls["n"] += 1
        raise runner.QuoteFeedError("down")

    with pytest.raises(runner.QuoteFeedError):
        runner.fetch_quotes_with_retry(
            ["ACME"], access_token="t", fetch=counted, sleep=lambda _s: None
        )

    assert calls["n"] == runner.MAX_CONSECUTIVE_QUOTE_FAILURES


def test_a_first_attempt_that_works_does_not_wait_at_all() -> None:
    """The common case must not pay for the rare one: 09:00 is the tightest moment of the day."""
    runner = _quote_runner()
    slept: list[float] = []

    runner.fetch_quotes_with_retry(
        ["ACME"],
        access_token="t",
        fetch=lambda _u, access_token=None: {"ACME": {"price": Decimal("1.00")}},
        sleep=slept.append,
    )

    assert slept == []


# --------------------------------------------------------------------------------------------
# The flat-book alarm describes what happened, not a loss that did not occur. (R6-09, R6-11)
# --------------------------------------------------------------------------------------------


def test_a_session_that_opened_flat_is_not_told_it_paid_for_exits() -> None:
    """The one message this used to print stated a financial event that had not occurred.

    On a first session that started flat and could not enter, no exit filled and nothing was paid.
    On an unattended schedule this is the operator's alarm text.
    """
    runner = _quote_runner()

    message = runner.flat_book_alarm(opened_holding=0, exit_fills=0, exit_fees=Decimal("0.00"))

    assert "nothing was paid" in message
    assert "round trip" not in message
    assert "exit costs" not in message


def test_a_session_that_sold_everything_is_told_what_it_paid() -> None:
    runner = _quote_runner()

    message = runner.flat_book_alarm(opened_holding=97, exit_fills=97, exit_fees=Decimal("1115.75"))

    assert "97 exit(s) filled" in message
    assert "1115.75" in message


def test_a_book_that_vanished_without_selling_is_a_reconciliation_question() -> None:
    """Held at the open, flat at the close, and no exit filled: the fills do not explain it."""
    runner = _quote_runner()

    message = runner.flat_book_alarm(opened_holding=97, exit_fills=0, exit_fees=Decimal("0.00"))

    assert "reconciliation" in message
    assert "was paid" not in message


def test_an_unquoted_holding_contributes_its_cost_to_the_anchor_not_zero() -> None:
    """R6-11: an unquoted holding contributing zero anchors the day's drawdown baseline too low.

    A baseline below true equity means the first real mark looks like a gain, and a genuine decline
    from the true opening value is measured from the wrong place entirely.
    """
    runner = _quote_runner()

    class _Position:
        def __init__(self, quantity: int, average_price: Decimal) -> None:
            self.quantity = quantity
            self.average_price = average_price

    positions = {
        "ACME": _Position(100, Decimal("500.00")),
        "BETA": _Position(50, Decimal("200.00")),  # no quote for this one
    }

    equity = runner.equity_marked_at(Decimal("10000.00"), positions, {"ACME": Decimal("600.00")})

    assert equity == Decimal("80000.00"), (
        "10,000 cash + 100x600 quoted + 50x200 at cost; a zero contribution would give 70,000"
    )


# --------------------------------------------------------------------------------------------
# Concentration drift is reported, because nothing else can see it. (R6-08)
# --------------------------------------------------------------------------------------------


class _Pos:
    def __init__(self, quantity: int, average_price: Decimal) -> None:
        self.quantity = quantity
        self.average_price = average_price


def test_a_book_ninety_percent_in_one_name_is_reported() -> None:
    """`evaluate_order` is the only enforcement point and it never runs when nothing is submitted.

    A book that still contains the selection submits no orders, so a 90% position against a
    declared 30% limit passed every check the session made.
    """
    runner = _quote_runner()
    positions = {"BHARTIARTL": _Pos(900, Decimal("1000.00")), "TCS": _Pos(10, Decimal("1000.00"))}
    marks = {"BHARTIARTL": Decimal("1000.00"), "TCS": Decimal("1000.00")}

    drifted = runner.weight_drift_report(Decimal("90000.00"), positions, marks, 0.30)

    assert [sym for sym, _ in drifted] == ["BHARTIARTL"]
    assert drifted[0][1] > Decimal("0.85")


def test_an_equal_weighted_book_reports_no_drift() -> None:
    """The report must not fire on the state the strategy actually intends."""
    runner = _quote_runner()
    positions = {f"N{i:02d}": _Pos(10, Decimal("1000.00")) for i in range(20)}
    marks = {sym: Decimal("1000.00") for sym in positions}

    assert runner.weight_drift_report(Decimal("10000.00"), positions, marks, 0.30) == []


def test_weights_are_measured_against_equity_including_cash() -> None:
    """`max_position_weight` divides by total equity; measuring against the invested amount alone
    would report a fully invested book and a 5%-cash book as equally concentrated."""
    runner = _quote_runner()
    positions = {"ACME": _Pos(100, Decimal("1000.00"))}  # Rs 100,000 invested
    marks = {"ACME": Decimal("1000.00")}

    # Against Rs 400,000 of equity that is 25%, under a 30% limit.
    assert runner.weight_drift_report(Decimal("300000.00"), positions, marks, 0.30) == []
    # Against Rs 100,000 of equity it is 100%.
    assert runner.weight_drift_report(Decimal("0.00"), positions, marks, 0.30) != []


def test_an_unquoted_position_is_weighted_at_cost_rather_than_skipped() -> None:
    runner = _quote_runner()
    positions = {"BETA": _Pos(100, Decimal("1000.00"))}

    drifted = runner.weight_drift_report(Decimal("0.00"), positions, {}, 0.30)

    assert [sym for sym, _ in drifted] == ["BETA"]


def test_an_empty_book_reports_nothing_and_does_not_divide_by_zero() -> None:
    runner = _quote_runner()

    assert runner.weight_drift_report(Decimal("0.00"), {}, {}, 0.30) == []


def test_the_worst_offender_is_reported_first() -> None:
    """The message truncates to five names, so the order has to be the useful one."""
    runner = _quote_runner()
    positions = {"BIG": _Pos(60, Decimal("1000.00")), "MID": _Pos(35, Decimal("1000.00"))}
    marks = {"BIG": Decimal("1000.00"), "MID": Decimal("1000.00")}

    drifted = runner.weight_drift_report(Decimal("5000.00"), positions, marks, 0.30)

    assert [sym for sym, _ in drifted] == ["BIG", "MID"]


def test_a_response_keyed_by_symbol_is_matched() -> None:
    """The form the provider actually returns.

    Measured live on 2026-09-01: the request carries `NSE_EQ|INE002A01018` and the response is
    keyed `NSE_EQ:RELIANCE`. The primary lookup hit 0 of 10 and the fallback hit 10 of 10, so this
    is the path every quote in the pilot takes.
    """
    import io
    import json as _json
    import urllib.request
    from unittest import mock

    runner = _quote_runner()
    runner.UPSTOX_INSTRUMENT_KEYS = {"RELIANCE": "NSE_EQ|INE002A01018"}

    class _Response(io.BytesIO):
        def __enter__(self):
            return self

        def __exit__(self, *_exc):
            return False

    body = {"status": "success", "data": {"NSE_EQ:RELIANCE": {"last_price": 1309.0, "volume": 10}}}
    with mock.patch.object(
        urllib.request, "urlopen", lambda *_a, **_k: _Response(_json.dumps(body).encode())
    ):
        results = runner.fetch_upstox_live_quotes(["RELIANCE"], access_token="t")

    assert results["RELIANCE"]["price"] == Decimal("1309.00")


def test_a_response_keyed_by_isin_is_also_matched() -> None:
    """Kept, because the provider has not promised which form it returns."""
    import io
    import json as _json
    import urllib.request
    from unittest import mock

    runner = _quote_runner()
    runner.UPSTOX_INSTRUMENT_KEYS = {"RELIANCE": "NSE_EQ|INE002A01018"}

    class _Response(io.BytesIO):
        def __enter__(self):
            return self

        def __exit__(self, *_exc):
            return False

    body = {
        "status": "success",
        "data": {"NSE_EQ|INE002A01018": {"last_price": 1309.0, "volume": 10}},
    }
    with mock.patch.object(
        urllib.request, "urlopen", lambda *_a, **_k: _Response(_json.dumps(body).encode())
    ):
        results = runner.fetch_upstox_live_quotes(["RELIANCE"], access_token="t")

    assert results["RELIANCE"]["price"] == Decimal("1309.00")


def test_a_closed_market_ladder_does_not_produce_a_spread_of_the_whole_share_price() -> None:
    """Real, measured, and not hypothetical.

    At 17:00 IST on 2026-09-01 the live provider returned a top-of-book bid of 0.0 for all ten
    instruments requested -- 90 of 100 depth levels priced at zero. The previous computation,
    `best_ask - best_bid`, therefore produced a spread equal to the entire share price: RELIANCE
    1309.00 rather than 0.05. That spread builds the simulated order book, and the pilot's opening
    fetch runs at 09:00, before the 09:15 open, when the ladder looks exactly like this.
    """
    runner = _quote_runner()
    payload = {
        "last_price": 1309.0,
        "depth": {
            "buy": [{"quantity": 0, "price": 0.0, "orders": 0}],
            "sell": [{"quantity": 0, "price": 0.0, "orders": 0}],
        },
    }

    parsed = runner.parse_quote_payload(payload)

    assert parsed is not None
    assert parsed["spread"] == Decimal("0.05")
    assert parsed["price"] == Decimal("1309.00")


# --------------------------------------------------------------------------------------------
# Red Team Round 7 P1 Blockers and Runner Call-Site Mutant Killers (R7-01, R7-02, R7-08, R7-09)
# --------------------------------------------------------------------------------------------


def test_rebalance_executed_checks_coverage_boundary_and_purity_and_zero_fills() -> None:
    """Kills M3, and validates R7-02 zero-fills and book purity guards."""
    runner = _runner_module()
    hundred = {f"N{n}" for n in range(100)}

    # Boundary at 80%: 79% must fail, 80% must pass (kills M3)
    held_79 = {f"N{n}" for n in range(79)}
    held_80 = {f"N{n}" for n in range(80)}
    assert runner.rebalance_executed(hundred, held_79) is False
    assert runner.rebalance_executed(hundred, held_80) is True

    # Zero fills when orders were submitted (R7-02)
    assert runner.rebalance_executed(hundred, hundred, orders_submitted=24, total_fills=0) is False
    assert runner.rebalance_executed(hundred, hundred, orders_submitted=24, total_fills=20) is True

    # Book purity: held book contains lots of unwanted old names (R7-02)
    selected_2 = {"AXISBANK", "ITC"}
    held_4 = {"AXISBANK", "ITC", "RELIANCE", "TCS"}
    assert runner.rebalance_executed(selected_2, held_4) is False


def test_governor_allows_sell_order_even_when_unquoted_position_held() -> None:
    """R7-01: An unquoted holding must not prevent de-risking exit orders."""
    from quant_system.core.domain import Order, OrderType, Position, Quote, Side
    from quant_system.risk.governor import PreTradeRiskGovernor, RiskLimits

    gov = PreTradeRiskGovernor(limits=RiskLimits(max_portfolio_leverage=1.0))
    positions = {
        "RELIANCE": Position(symbol="RELIANCE", quantity=100, average_price=Decimal("2000.00")),
        "TCS": Position(symbol="TCS", quantity=50, average_price=Decimal("3000.00")),
    }
    sell_order = Order(
        order_id="ord_exit_rel",
        symbol="RELIANCE",
        side=Side.SELL,
        order_type=OrderType.LIMIT,
        quantity=100,
        limit_price=Decimal("2050.00"),
        created_at=datetime.now(UTC),
    )
    quote = Quote(
        symbol="RELIANCE",
        timestamp=datetime.now(UTC),
        bid=Decimal("2050.00"),
        ask=Decimal("2051.00"),
    )
    decision = gov.evaluate_order(
        order=sell_order,
        current_equity=Decimal("500000.00"),
        current_cash=Decimal("150000.00"),
        positions=positions,
        current_quote=quote,
        current_prices={"RELIANCE": Decimal("2050.00")},  # TCS is missing
    )
    assert decision.approved is True, f"Exit order was refused: {decision.reason}"


def test_missing_state_file_fails_closed_when_past_sessions_exist(tmp_path, monkeypatch) -> None:
    """R7-09: An absent state file with existing session reports must refuse to invent a fresh Rs 10 lakh book."""
    runner = _runner_module()

    runs_dir = tmp_path / "paper_runs"
    runs_dir.mkdir(parents=True, exist_ok=True)
    past_report = runs_dir / "paper_session_20260901_153000_IST.json"
    past_report.write_text("{}", encoding="utf-8")

    fake_state_path = runs_dir / "portfolio_state.json"
    monkeypatch.setattr(runner, "PORTFOLIO_STATE_PATH", fake_state_path)
    monkeypatch.setattr(runner, "assert_upstox_usable", lambda token: None)
    monkeypatch.setattr(
        runner,
        "fetch_quotes_with_retry",
        lambda universe, access_token=None: {"INFY": {"price": Decimal("1500.00")}},
    )
    # `run_paper_session` exports its token to the process environment
    # (`run_paper_pilot_session.py:896`). Claiming it through monkeypatch first means the
    # prior state -- here, absent -- is recorded and restored at teardown. Without this the
    # token outlived the test and every later test saw one: `UpstoxClient(access_token="")`
    # treats "" as falsy and falls through to `os.getenv("UPSTOX_ACCESS_TOKEN")`, so the two
    # tests asserting PROVIDER_UNAUTHORIZED without a token got DATASET_EMPTY instead.
    monkeypatch.setenv("UPSTOX_ACCESS_TOKEN", "test-only-not-a-real-token")

    with pytest.raises(runner.PaperPortfolioError, match="Missing portfolio state"):
        runner.run_paper_session(
            session_date=date(2026, 9, 2),
            output_dir=runs_dir,
            universe=["INFY"],
            upstox_token="test_mock_token",
            force_new_portfolio=False,
        )


def test_halted_portfolio_refuses_trading_at_startup(tmp_path, monkeypatch, caplog) -> None:
    """Kills M6: if portfolio.risk_halted is True, runner must exit 8.

    Hermetic: stubs load_mizan_cross_section with a minimal valid cross-section so the
    rebalance branch exercises the startup halt check without reading real evidence caches.
    Guards EvidenceStore.list_verified so any accidental call to real evidence fails fast.
    """
    import logging

    runner = _runner_module()
    caplog.set_level(logging.ERROR, logger=runner.logger.name)

    def _fail_on_real_evidence(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("this test must not read real evidence")

    monkeypatch.setattr(runner.EvidenceStore, "list_verified", _fail_on_real_evidence)

    features_by_symbol: dict[str, dict[str, str]] = {"INFY": {}}
    stub_cross_section = (
        features_by_symbol,
        runner.CrossSectionCoverage(
            requested=("INFY",),
            scored=("INFY",),
            skipped_short_history=(),
            skipped_not_computable=(),
        ),
    )

    def _stub_load_mizan_cross_section(*_args: object, **_kwargs: object) -> object:
        return stub_cross_section

    monkeypatch.setattr(runner, "load_mizan_cross_section", _stub_load_mizan_cross_section)

    runs_dir = tmp_path / "paper_runs"
    runs_dir.mkdir(parents=True, exist_ok=True)
    state_path = runs_dir / "portfolio_state.json"
    monkeypatch.setattr(runner, "PORTFOLIO_STATE_PATH", state_path)

    halted_state = runner.PaperPortfolioState(
        cash=Decimal("500000.00"),
        risk_halted=True,
        halted_on=date(2026, 9, 1),
        halt_reason="TRAILING_DRAWDOWN_KILL_SWITCH",
    )
    runner.save_portfolio(state_path, halted_state)

    monkeypatch.setattr(runner, "assert_upstox_usable", lambda token: None)
    monkeypatch.setattr(
        runner,
        "fetch_quotes_with_retry",
        lambda universe, access_token=None: {"INFY": {"price": Decimal("1500.00")}},
    )
    # `run_paper_session` exports its token to the process environment
    # (`run_paper_pilot_session.py:896`). Claiming it through monkeypatch first means the
    # prior state -- here, absent -- is recorded and restored at teardown. Without this the
    # token outlived the test and every later test saw one: `UpstoxClient(access_token="")`
    # treats "" as falsy and falls through to `os.getenv("UPSTOX_ACCESS_TOKEN")`, so the two
    # tests asserting PROVIDER_UNAUTHORIZED without a token got DATASET_EMPTY instead.
    monkeypatch.setenv("UPSTOX_ACCESS_TOKEN", "test-only-not-a-real-token")

    with pytest.raises(SystemExit) as exc:
        runner.run_paper_session(
            session_date=date(2026, 9, 2),
            output_dir=runs_dir,
            universe=["INFY"],
            upstox_token="valid_token",
        )
    assert exc.value.code == 8
    assert "REFUSING TO TRADE" in caplog.text


def test_concurrent_portfolio_write_during_session_detected_at_save(tmp_path) -> None:
    """Kills M1 & M10: state_hash_on_disk at load prevents clobbering concurrent state write."""
    runner = _runner_module()
    runs_dir = tmp_path / "paper_runs"
    runs_dir.mkdir(parents=True, exist_ok=True)
    state_path = runs_dir / "portfolio_state.json"

    initial_state = runner.PaperPortfolioState(cash=Decimal("1000000.00"))
    runner.save_portfolio(state_path, initial_state)
    load_hash = runner.state_hash_on_disk(state_path)

    # Concurrent session writes to state_path
    concurrent_state = runner.PaperPortfolioState(cash=Decimal("950000.00"), sessions_completed=1)
    runner.save_portfolio(state_path, concurrent_state)

    # Attempting to save with the original load_hash must raise PaperPortfolioError
    my_updated_state = runner.PaperPortfolioState(cash=Decimal("900000.00"), sessions_completed=1)
    with pytest.raises(runner.PaperPortfolioError, match="changed since this session loaded it"):
        runner.save_portfolio(state_path, my_updated_state, expected_prior_hash=load_hash)
