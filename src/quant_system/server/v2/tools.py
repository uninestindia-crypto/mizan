"""Calculators: trade charges and break-even, position size, options payoff."""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import date
from decimal import ROUND_DOWN, ROUND_HALF_UP, Decimal
from typing import Any, Literal

import numpy as np

from quant_system.analytics.greeks import BlackScholes
from quant_system.analytics.nse_rules import MarketSegment
from quant_system.core.domain import InstrumentType, Side
from quant_system.lab.costs import BrokerCharges, ChargeBreakdown, RetailCostModel

Segment = Literal["delivery", "intraday", "futures", "options"]
SEGMENTS: dict[str, MarketSegment] = {
    "delivery": MarketSegment.EQUITY_DELIVERY,
    "intraday": MarketSegment.EQUITY_INTRADAY,
    "futures": MarketSegment.EQUITY_FUTURES,
    "options": MarketSegment.EQUITY_OPTIONS,
}
_PAISA = Decimal("0.01")


class ToolError(ValueError):
    """Input a calculator cannot work with, explained for the user."""


def _lines(breakdown: ChargeBreakdown) -> list[dict[str, Any]]:
    return [
        {"label": c.label, "amount": float(c.amount), "rule_id": c.rule_id} for c in breakdown.lines
    ]


def trade_costs(
    segment: Segment,
    buy_price: Decimal,
    sell_price: Decimal,
    quantity: int,
    trade_date: date,
    broker: BrokerCharges,
) -> dict[str, Any]:
    if quantity <= 0:
        raise ToolError("Quantity must be at least 1.")
    if buy_price <= 0 or sell_price <= 0:
        raise ToolError("Prices must be above zero.")
    market_segment = SEGMENTS[segment]
    model = RetailCostModel(broker)
    try:
        buy = model.charges(Side.BUY, quantity, buy_price, trade_date, market_segment)
        sell = model.charges(Side.SELL, quantity, sell_price, trade_date, market_segment)
    except ValueError as err:
        raise ToolError(
            f"NSE charges for {trade_date:%d %b %Y} are not defined in QuantOS's rule catalog "
            "(exact rules start on 1 Jul 2020)."
        ) from err
    gross = (sell_price - buy_price) * Decimal(quantity)
    charges = buy.total + sell.total
    net = gross - charges
    breakeven = _breakeven_price(model, market_segment, buy_price, buy.total, quantity, trade_date)
    turnover = buy.turnover + sell.turnover
    return {
        "segment": segment,
        "trade_date": trade_date.isoformat(),
        "quantity": quantity,
        "buy": {
            "price": float(buy_price),
            "turnover": float(buy.turnover),
            "lines": _lines(buy),
            "total": float(buy.total),
        },
        "sell": {
            "price": float(sell_price),
            "turnover": float(sell.turnover),
            "lines": _lines(sell),
            "total": float(sell.total),
        },
        "gross_pnl": float(gross),
        "charges": float(charges),
        "net_pnl": float(net),
        "charges_pct_of_turnover": float(charges / turnover) if turnover else 0.0,
        "breakeven_price": float(breakeven),
        "breakeven_move_pct": float(breakeven / buy_price - 1),
    }


def _breakeven_price(
    model: RetailCostModel,
    segment: MarketSegment,
    buy_price: Decimal,
    buy_charges: Decimal,
    quantity: int,
    trade_date: date,
) -> Decimal:
    """Lowest sell price (to the paisa) at which net P&L is not negative."""

    def net(price: Decimal) -> Decimal:
        sell = model.charges(Side.SELL, quantity, price, trade_date, segment).total
        return (price - buy_price) * Decimal(quantity) - buy_charges - sell

    low, high = buy_price, buy_price * Decimal("1.5") + Decimal("1")
    while net(high) < 0:
        high *= 2
    for _ in range(80):
        mid = ((low + high) / 2).quantize(_PAISA, rounding=ROUND_HALF_UP)
        if mid in (low, high):
            break
        if net(mid) >= 0:
            high = mid
        else:
            low = mid
    return high.quantize(_PAISA)


def position_size(
    capital: Decimal, risk_pct: Decimal, entry: Decimal, stop: Decimal, lot_size: int = 1
) -> dict[str, Any]:
    if capital <= 0 or entry <= 0 or stop <= 0:
        raise ToolError("Capital, entry and stop must be above zero.")
    if not Decimal("0") < risk_pct <= Decimal("100"):
        raise ToolError("Risk per trade must be between 0 and 100%.")
    if lot_size < 1:
        raise ToolError("Lot size must be at least 1.")
    per_share = abs(entry - stop)
    if per_share == 0:
        raise ToolError("The stop must differ from the entry price.")
    risk_amount = capital * risk_pct / Decimal("100")
    by_risk = (
        int((risk_amount / per_share / lot_size).to_integral_value(rounding=ROUND_DOWN)) * lot_size
    )
    by_capital = int((capital / entry / lot_size).to_integral_value(rounding=ROUND_DOWN)) * lot_size
    quantity = min(by_risk, by_capital)
    return {
        "direction": "long" if stop < entry else "short",
        "risk_amount": float(risk_amount),
        "risk_per_share": float(per_share),
        "stop_distance_pct": float(per_share / entry),
        "quantity": quantity,
        "capital_used": float(entry * quantity),
        "capital_used_pct": float(entry * quantity / capital),
        "max_loss": float(per_share * quantity),
        "limited_by_capital": by_capital < by_risk,
    }


@dataclass(frozen=True, slots=True)
class OptionLeg:
    kind: Literal["call", "put"]
    side: Literal["buy", "sell"]
    strike: float
    premium: float
    lots: int
    lot_size: int

    @property
    def signed_quantity(self) -> int:
        return self.lots * self.lot_size * (1 if self.side == "buy" else -1)


def options_payoff(
    legs: list[OptionLeg],
    spot: float,
    days_to_expiry: int,
    volatility: float,
    rate: float = 0.07,
    points: int = 241,
) -> dict[str, Any]:
    if not 1 <= len(legs) <= 4:
        raise ToolError("Use between 1 and 4 legs.")
    if spot <= 0 or not 0 < volatility < 5 or days_to_expiry < 0:
        raise ToolError(
            "Spot must be above zero, volatility between 0% and 500%, days not negative."
        )
    for leg in legs:
        if leg.strike <= 0 or leg.premium < 0 or leg.lots < 1 or leg.lot_size < 1:
            raise ToolError(
                "Each leg needs a strike above zero, a premium of zero or more, and lots."
            )
    strikes = [leg.strike for leg in legs]
    low = max(0.01, min(spot * 0.7, min(strikes) * 0.9))
    high = max(spot * 1.3, max(strikes) * 1.1)
    grid = np.linspace(low, high, points)
    years = days_to_expiry / 365.0
    expiry = np.zeros_like(grid)
    today = np.zeros_like(grid)
    for leg in legs:
        q = leg.signed_quantity
        intrinsic = (
            np.maximum(grid - leg.strike, 0.0)
            if leg.kind == "call"
            else np.maximum(leg.strike - grid, 0.0)
        )
        expiry += q * (intrinsic - leg.premium)
        option_type = (
            InstrumentType.OPTION_CALL if leg.kind == "call" else InstrumentType.OPTION_PUT
        )
        values = [
            BlackScholes.calculate_greeks(
                float(x), leg.strike, years, volatility, rate, option_type
            ).price
            for x in grid
        ]
        today += q * (np.array(values) - leg.premium)
    call_slope = sum(leg.signed_quantity for leg in legs if leg.kind == "call")
    at_zero = sum(
        leg.signed_quantity * ((max(leg.strike, 0.0) if leg.kind == "put" else 0.0) - leg.premium)
        for leg in legs
    )
    finite = np.append(expiry, at_zero)
    greeks = _position_greeks(legs, spot, years, volatility, rate)
    return {
        "grid": [
            [round(float(x), 2), round(float(e), 2), round(float(t), 2)]
            for x, e, t in zip(grid, expiry, today, strict=True)
        ],
        "breakevens": _zero_crossings(grid, expiry),
        "max_profit": None if call_slope > 0 else round(float(finite.max()), 2),
        "max_loss": None if call_slope < 0 else round(float(finite.min()), 2),
        "net_premium": round(sum(leg.signed_quantity * leg.premium for leg in legs), 2),
        "greeks": greeks,
    }


def _zero_crossings(grid: np.ndarray, values: np.ndarray) -> list[float]:
    out: list[float] = []
    for i in range(len(grid) - 1):
        a, b = values[i], values[i + 1]
        if a == 0:
            out.append(round(float(grid[i]), 2))
        elif a * b < 0:
            out.append(round(float(grid[i] + (grid[i + 1] - grid[i]) * (-a) / (b - a)), 2))
    return sorted(set(out))


def _position_greeks(
    legs: list[OptionLeg], spot: float, years: float, volatility: float, rate: float
) -> dict[str, float]:
    total = {"delta": 0.0, "gamma": 0.0, "theta": 0.0, "vega": 0.0}
    for leg in legs:
        option_type = (
            InstrumentType.OPTION_CALL if leg.kind == "call" else InstrumentType.OPTION_PUT
        )
        g = BlackScholes.calculate_greeks(spot, leg.strike, years, volatility, rate, option_type)
        q = leg.signed_quantity
        total["delta"] += q * g.delta
        total["gamma"] += q * g.gamma
        total["theta"] += q * g.theta
        total["vega"] += q * g.vega
    return {k: round(v, 4) if math.isfinite(v) else 0.0 for k, v in total.items()}
