"""Retail trading charges: NSE statutory rules by trade date plus the user's own broker charges.

Statutory lines (STT, exchange transaction charge, SEBI fee, stamp duty, GST on those) come from
:class:`~quant_system.analytics.nse_rules.NSERuleEngine`, which applies the rate in force on the
trade date and names the rule it used. Broker lines come from the user's settings, because
brokerage and depository (DP) charges differ by broker; GST at 18% applies to them too.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field
from datetime import date
from decimal import ROUND_HALF_UP, Decimal

from quant_system.analytics.nse_rules import FeeComponent, MarketSegment, NSERuleEngine
from quant_system.core.domain import Side

_PAISA = Decimal("0.01")
_GST_RATE = Decimal("0.18")
_ENGINE = NSERuleEngine()

_SEGMENT_COMPONENTS = (
    FeeComponent.STT,
    FeeComponent.EXCHANGE_TURNOVER,
    FeeComponent.SEBI_TURNOVER,
    FeeComponent.STAMP_DUTY,
    FeeComponent.GST,
)


def first_fully_priced_date(segment: MarketSegment, rules_engine: NSERuleEngine = _ENGINE) -> date:
    """Earliest trade date on which every statutory component has an effective rule.

    Before it (stamp duty became a uniform national rate on 2020-07-01) no dated rule exists, so a
    trade cannot be priced exactly and the lab refuses to place it.
    """
    earliest: list[date] = []
    for component in _SEGMENT_COMPONENTS:
        dates = [
            r.effective_from
            for r in rules_engine.rules
            if r.component == component and r.segment == segment
        ]
        if not dates:
            raise ValueError(f"No {component.value} rule exists for {segment.value}")
        earliest.append(min(dates))
    return max(earliest)


COSTS_COVERED_FROM: date = first_fully_priced_date(MarketSegment.EQUITY_DELIVERY)


@dataclass(frozen=True, slots=True)
class BrokerCharges:
    """What the user's broker charges, from Settings. Defaults are a zero-brokerage delivery broker."""

    delivery_per_order: Decimal = Decimal("0")
    intraday_per_order: Decimal = Decimal("20")
    fno_per_order: Decimal = Decimal("20")
    dp_charge_per_sell: Decimal = Decimal("0")

    def __post_init__(self) -> None:
        for name in (
            "delivery_per_order",
            "intraday_per_order",
            "fno_per_order",
            "dp_charge_per_sell",
        ):
            value = getattr(self, name)
            if not isinstance(value, Decimal) or value < 0 or value > Decimal("1000"):
                raise ValueError(f"{name} must be a Decimal between 0 and 1000")

    def per_order(self, segment: MarketSegment) -> Decimal:
        if segment == MarketSegment.EQUITY_DELIVERY:
            return self.delivery_per_order
        if segment == MarketSegment.EQUITY_INTRADAY:
            return self.intraday_per_order
        return self.fno_per_order


@dataclass(frozen=True, slots=True)
class ChargeLine:
    label: str
    amount: Decimal
    rule_id: str


@dataclass(frozen=True, slots=True)
class ChargeBreakdown:
    trade_date: date
    segment: MarketSegment
    side: Side
    quantity: int
    price: Decimal
    turnover: Decimal
    lines: tuple[ChargeLine, ...] = field(default_factory=tuple)

    @property
    def total(self) -> Decimal:
        return sum((line.amount for line in self.lines), Decimal("0.00"))


class RetailCostModel:
    """Prices one fill. Raises ``ValueError`` for a trade date the rule catalog cannot price."""

    def __init__(
        self, broker: BrokerCharges | None = None, engine: NSERuleEngine | None = None
    ) -> None:
        self.broker = broker or BrokerCharges()
        self.engine = engine or _ENGINE

    def charges(
        self,
        side: Side,
        quantity: int,
        price: Decimal,
        trade_date: date,
        segment: MarketSegment = MarketSegment.EQUITY_DELIVERY,
    ) -> ChargeBreakdown:
        statutory = self.engine.calculate_costs(segment, side, quantity, price, trade_date)
        ids = statutory.applied_rule_ids
        lines = [
            ChargeLine("Securities transaction tax (STT)", statutory.stt, ids["STT"]),
            ChargeLine(
                "Exchange transaction charge", statutory.exchange_turnover, ids["EXCHANGE_TURNOVER"]
            ),
            ChargeLine("SEBI turnover fee", statutory.sebi_charges, ids["SEBI_TURNOVER"]),
            ChargeLine("Stamp duty", statutory.stamp_duty, ids["STAMP_DUTY"]),
            ChargeLine("GST on exchange and SEBI charges", statutory.gst, ids["GST"]),
        ]
        brokerage = self.broker.per_order(segment)
        dp = (
            self.broker.dp_charge_per_sell
            if (side == Side.SELL and segment == MarketSegment.EQUITY_DELIVERY)
            else Decimal("0")
        )
        if brokerage > 0:
            lines.append(
                ChargeLine("Brokerage (your broker)", _paise(brokerage), "SETTINGS-BROKERAGE")
            )
        if dp > 0:
            lines.append(
                ChargeLine("Depository (DP) charge (your broker)", _paise(dp), "SETTINGS-DP")
            )
        broker_gst = _paise((brokerage + dp) * _GST_RATE)
        if broker_gst > 0:
            lines.append(ChargeLine("GST on broker charges", broker_gst, "GST-18-BROKER"))
        return ChargeBreakdown(
            trade_date=trade_date,
            segment=segment,
            side=side,
            quantity=quantity,
            price=price,
            turnover=statutory.turnover,
            lines=tuple(
                line
                for line in lines
                if line.amount != 0 or line.rule_id.startswith(("STT", "EXCH"))
            ),
        )

    def fee(self, side: Side, quantity: int, price: Decimal, trade_date: date) -> Decimal:
        return self.charges(side, quantity, price, trade_date).total


def total(lines: Iterable[ChargeLine]) -> Decimal:
    return sum((line.amount for line in lines), Decimal("0.00"))


def _paise(value: Decimal) -> Decimal:
    return value.quantize(_PAISA, rounding=ROUND_HALF_UP)
