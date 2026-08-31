"""The daily peak and the trailing peak must mean different things.

`PreTradeRiskGovernor` seeded `_daily_peak_equity` and `_all_time_peak_equity` from the same
`initial_equity`, and `reset_session_peak` -- the method that exists to set the daily peak at each
open -- had **no caller anywhere in the repository**. That was harmless only while nothing passed a
carried figure.

Once the paper runner began passing the persisted all-time peak as `initial_equity`, to make the
total-drawdown switch work across sessions, the **daily** check inherited it. A 4% limit was then
measuring multi-session declines: `TOTAL_MAX_DRAWDOWN_BREACHED` became unreachable, every breach at
5%, 10%, 14% or 20% below the peak reported the daily reason, and a session that opened flat and
never moved intraday could halt the book on its first order -- which is the exit, so the losing
position was then held with nothing able to sell it.

Simulated over 4,000 random paths, the old seeding halted **4,000 of 4,000** within 250 sessions at
a median of session 18, always on the daily rule. With the peaks separated it is 3,032 of 4,000 at a
median of session 106, always on the total rule -- the switch that was meant to govern a
multi-session decline.
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

from quant_system.core.domain import Order, OrderType, Side
from quant_system.risk.checks import RiskLimits
from quant_system.risk.governor import PreTradeRiskGovernor

AT = datetime(2026, 8, 31, 9, 15, tzinfo=UTC)
LIMITS = RiskLimits(max_daily_drawdown_pct=0.04, max_total_drawdown_pct=0.12)

PEAK = Decimal("1000000.00")


def _order() -> Order:
    return Order(
        order_id="o1",
        symbol="ACME",
        side=Side.SELL,
        quantity=10,
        order_type=OrderType.MARKET,
        created_at=AT,
    )


def _decide(governor: PreTradeRiskGovernor, equity: Decimal):
    return governor.evaluate_order(
        _order(),
        current_equity=equity,
        current_cash=equity,
        positions={},
        current_quote=None,
        current_prices={},
    )


def test_a_session_opening_below_its_all_time_peak_is_not_a_daily_drawdown() -> None:
    """The exact defect: 4.5% below the all-time high, flat intraday, and it used to halt.

    Asserted on the drawdown rules rather than on approval, because an order can be refused for
    reasons that have nothing to do with this -- a missing valuation price, for one. What must be
    true is that neither drawdown rule fires and the kill switch stays open.
    """
    opening = Decimal("954998.50")  # 4.5% below PEAK, inside the 12% total limit
    governor = PreTradeRiskGovernor(
        limits=LIMITS, initial_equity=opening, all_time_peak_equity=PEAK
    )

    decision = _decide(governor, opening)

    assert "DRAWDOWN" not in (decision.reason or ""), f"refused with: {decision.reason}"
    assert governor.is_killed is False


def test_the_daily_limit_still_fires_on_a_real_intraday_decline() -> None:
    """Separating the peaks must not disarm the daily rule, only point it at the right baseline."""
    opening = Decimal("1000000.00")
    governor = PreTradeRiskGovernor(
        limits=LIMITS, initial_equity=opening, all_time_peak_equity=PEAK
    )

    decision = _decide(governor, Decimal("955000.00"))  # 4.5% below *today's open*

    assert decision.approved is False
    assert "DAILY_DRAWDOWN_LIMIT_BREACHED" in (decision.reason or "")


def test_the_total_limit_is_reachable() -> None:
    """It was not. Every multi-session breach reported the daily reason first."""
    opening = Decimal("870000.00")  # 13% below the all-time peak, flat intraday
    governor = PreTradeRiskGovernor(
        limits=LIMITS, initial_equity=opening, all_time_peak_equity=PEAK
    )

    decision = _decide(governor, opening)

    assert decision.approved is False
    assert "TOTAL_MAX_DRAWDOWN_BREACHED" in (decision.reason or ""), (
        f"expected the total-drawdown rule to fire, got {decision.reason}"
    )


def test_a_multi_session_decline_reports_the_total_rule_at_every_depth() -> None:
    """At 5%, 10%, 14% and 20% the old seeding always said DAILY. None of those is a daily move."""
    reasons = {}
    for fraction in ("0.95", "0.90", "0.86", "0.80"):
        opening = (PEAK * Decimal(fraction)).quantize(Decimal("0.01"))
        governor = PreTradeRiskGovernor(
            limits=LIMITS, initial_equity=opening, all_time_peak_equity=PEAK
        )
        decision = _decide(governor, opening)
        reason = (decision.reason or "").split(":")[0]
        reasons[fraction] = reason if "DRAWDOWN" in reason else "NO_DRAWDOWN_BREACH"

    assert reasons == {
        "0.95": "NO_DRAWDOWN_BREACH",  # 5% down, inside the 12% total limit
        "0.90": "NO_DRAWDOWN_BREACH",  # 10% down, still inside
        "0.86": "TOTAL_MAX_DRAWDOWN_BREACHED",  # 14% down
        "0.80": "TOTAL_MAX_DRAWDOWN_BREACHED",  # 20% down
    }, reasons


def test_a_carried_peak_below_today_s_open_does_not_weaken_the_total_check() -> None:
    """The carried figure is a floor, not a replacement, or the total check could go slack."""
    opening = Decimal("1500000.00")
    governor = PreTradeRiskGovernor(
        limits=LIMITS, initial_equity=opening, all_time_peak_equity=Decimal("900000.00")
    )

    assert governor.all_time_peak_equity == opening


def test_omitting_the_trailing_peak_keeps_the_old_single_argument_behaviour() -> None:
    """A portfolio with no history has one peak, and every existing caller relies on that."""
    governor = PreTradeRiskGovernor(limits=LIMITS, initial_equity=PEAK)

    assert governor.daily_peak_equity == PEAK
    assert governor.all_time_peak_equity == PEAK


def test_an_overnight_gap_is_not_a_daily_drawdown() -> None:
    """The defect, three rounds running, and what `reset_session_peak` exists to prevent.

    A baseline taken from the previous close turns an overnight gap into a "daily" drawdown with
    zero intraday movement: the 4% rule fires on the first order, that order is the exit, the
    losing book is retained, and the halt persists so every later session refuses.

    Anchoring to the first live mark is the fix. The trailing peak keeps the real high-water mark,
    so the 12% rule still sees the gap -- which is correct: it is a genuine loss against capital,
    just not an intraday one.
    """
    previous_close = Decimal("1000000.00")
    after_a_5pc_gap = Decimal("950000.00")

    stale = PreTradeRiskGovernor(
        limits=LIMITS, initial_equity=previous_close, all_time_peak_equity=previous_close
    )
    assert "DAILY_DRAWDOWN_LIMIT_BREACHED" in (_decide(stale, after_a_5pc_gap).reason or ""), (
        "seeding from the previous close should reproduce the defect; if it no longer does, this "
        "test has stopped exercising what it exists to catch"
    )

    anchored = PreTradeRiskGovernor(
        limits=LIMITS, initial_equity=previous_close, all_time_peak_equity=previous_close
    )
    anchored.reset_session_peak(after_a_5pc_gap)  # the first live mark of the session

    decision = _decide(anchored, after_a_5pc_gap)
    assert "DAILY" not in (decision.reason or ""), (
        f"a gap with no intraday movement tripped the daily rule: {decision.reason}"
    )
    assert anchored.all_time_peak_equity == previous_close, (
        "anchoring the daily peak must not lower the trailing peak; the 12% rule still measures "
        "the gap against the real high-water mark"
    )


def test_the_runner_anchors_the_daily_peak_before_it_places_any_order() -> None:
    """`reset_session_peak` had no caller anywhere in the repository through three rounds.

    Anchoring must also happen before the order loops, not at the end-of-step snapshot: the exits
    and entries run first within a step, so a baseline set afterwards is set too late to matter.
    """
    import ast
    from pathlib import Path

    source = (
        Path(__file__).resolve().parent.parent / "scripts/run_paper_pilot_session.py"
    ).read_text(encoding="utf-8")
    tree = ast.parse(source)

    calls = [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "reset_session_peak"
    ]
    assert calls, "nothing calls reset_session_peak; the daily baseline is the previous close"

    # What it is anchored *to*, with local names resolved.
    #
    # Reading the argument unresolved is not enough: `anchor_equity = marked_opening_equity` one
    # line above the call satisfies a check on the argument's spelling while reproducing the defect
    # exactly. That mutant survived this test until resolution was added, which is the same failure
    # the round-five tests had at scale -- thirteen string-preserving mutants, none caught.
    assignments = {
        target.id: ast.unparse(node.value)
        for node in ast.walk(tree)
        if isinstance(node, ast.Assign)
        for target in node.targets
        if isinstance(target, ast.Name)
    }

    def resolve(expression: str, depth: int = 0) -> str:
        if depth < 4 and expression in assignments:
            return resolve(assignments[expression], depth + 1)
        return expression

    for call in calls:
        argument = resolve(ast.unparse(call.args[0])) if call.args else ""
        assert "marked_opening_equity" not in argument, (
            f"the daily peak is anchored to {argument!r}, which is the boot-time mark -- the "
            "previous close at 09:00, and the defect this call exists to remove."
        )
        # Both permitted sources are now named functions with behavioural tests of their own:
        # `equity_marked_at` values the book at the marks it is given, and `anchor_to_reuse` returns
        # today's persisted baseline or nothing. This assertion pins which of them the runner uses;
        # what each one *does* is driven elsewhere, because a source check cannot establish that.
        assert "equity_marked_at" in argument or "anchor_to_reuse" in argument, (
            f"the daily peak is anchored to {argument!r}; it must come from equity marked at the "
            "first live quote, or from the anchor this session already persisted today."
        )

    # And that it is reachable. `if False and ...` keeps the call on the same line while disabling
    # it, which a line-position check alone cannot see.
    guarding = [
        ast.unparse(node.test)
        for node in ast.walk(tree)
        if isinstance(node, ast.If)
        and any(
            isinstance(inner, ast.Call)
            and isinstance(inner.func, ast.Attribute)
            and inner.func.attr == "reset_session_peak"
            for inner in ast.walk(node)
        )
    ]
    assert guarding, "the anchor is not guarded at all; it would re-anchor on every step"
    # Two call sites now, and they carry different guards for different reasons: the in-loop one is
    # gated on the once-per-session flag, and the restart path is gated on the persisted anchor
    # belonging to today. Both are conditions about *when* to anchor; an unconditional call, or one
    # disabled by a constant, is what must not pass.
    # Whether each guard is *effective* is driven by `test_a_restart_reuses_only_todays_anchor`:
    # a source check can see that a condition exists, never that it decides anything.
    assert all("daily_peak_anchored" in test or "persisted_anchor" in test for test in guarding), (
        f"an anchor call is guarded by {guarding!r}. Each must be conditional on the session it "
        "belongs to, so it neither re-anchors every step nor is switched off by a constant."
    )

    anchor_line = min(call.lineno for call in calls)
    proposal_lines = [
        node.lineno
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "submit_proposal"
    ]
    assert proposal_lines, "no orders are submitted; this check has gone blind"
    assert anchor_line < min(proposal_lines), (
        f"the daily peak is anchored at line {anchor_line}, after the first order at "
        f"line {min(proposal_lines)}. The exit is the first order of a rebalance, so a late "
        "baseline is set after the decision it was supposed to govern."
    )


def test_the_anchor_equity_is_marked_at_the_supplied_prices() -> None:
    """Driven, not read. The defect is *which* marks are supplied, so the arithmetic must be exact.

    Computed from the boot-time quote map this is the previous close, which is how an overnight gap
    became a "daily" drawdown. The function itself must value the book at whatever marks it is
    given, and fall back to a position's own cost only when it has no mark at all.
    """
    import importlib.util
    import os
    from dataclasses import dataclass
    from pathlib import Path
    from unittest import mock

    spec = importlib.util.spec_from_file_location(
        "_rps_equity", Path(__file__).resolve().parent.parent / "scripts/run_paper_pilot_session.py"
    )
    assert spec and spec.loader
    runner = importlib.util.module_from_spec(spec)
    with mock.patch.dict(os.environ, os.environ.copy(), clear=True):
        spec.loader.exec_module(runner)

    @dataclass
    class _Position:
        quantity: int
        average_price: Decimal

    positions = {
        "ACME": _Position(100, Decimal("1000.00")),
        "BETA": _Position(50, Decimal("200.00")),
    }
    cash = Decimal("50000.00")

    # Yesterday's close: 100*1000 + 50*200 = 110,000, plus cash.
    at_close = runner.equity_marked_at(
        cash, positions, {"ACME": Decimal("1000.00"), "BETA": Decimal("200.00")}
    )
    assert at_close == Decimal("160000.00")

    # A 5% overnight gap down must produce a different number, or the daily rule cannot tell the
    # two apart -- which is precisely the defect.
    after_gap = runner.equity_marked_at(
        cash, positions, {"ACME": Decimal("950.00"), "BETA": Decimal("190.00")}
    )
    assert after_gap == Decimal("154500.00")
    assert after_gap < at_close

    # A position with no mark is valued at its own cost, never dropped: dropping it would understate
    # equity and make the drawdown look larger than it is.
    partial = runner.equity_marked_at(cash, positions, {"ACME": Decimal("950.00")})
    assert partial == Decimal("155000.00")
