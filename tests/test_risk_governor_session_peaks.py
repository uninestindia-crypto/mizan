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
