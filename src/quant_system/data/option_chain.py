"""Option chain data models, strike grids, open interest, and implied volatility containers."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal

from quant_system.core.domain import InstrumentType


@dataclass(frozen=True, slots=True)
class OptionContract:
    """A single European or American option contract."""

    symbol: str
    underlying: str
    strike: Decimal
    expiry: date
    option_type: InstrumentType  # OPTION_CALL or OPTION_PUT
    bid: Decimal
    ask: Decimal
    last_price: Decimal
    volume: int
    open_interest: int
    implied_volatility: float | None = None
    delta: float | None = None
    gamma: float | None = None
    theta: float | None = None
    vega: float | None = None

    @property
    def mid_price(self) -> Decimal:
        return (self.bid + self.ask) / Decimal("2")


@dataclass(frozen=True, slots=True)
class OptionStrike:
    """Paired call and put contract at a specific strike price."""

    strike: Decimal
    call: OptionContract | None
    put: OptionContract | None

    @property
    def straddle_price(self) -> Decimal | None:
        if self.call and self.put:
            return self.call.mid_price + self.put.mid_price
        return None


@dataclass(frozen=True, slots=True)
class OptionChain:
    """Full snapshot of an option chain for an underlying at a given timestamp."""

    underlying: str
    spot_price: Decimal
    timestamp: datetime
    expiry: date
    strikes: Mapping[Decimal, OptionStrike]

    @property
    def atm_strike(self) -> Decimal:
        """Finds the strike closest to the underlying spot price."""
        if not self.strikes:
            raise ValueError(f"No strikes found in option chain for {self.underlying}")
        return min(self.strikes.keys(), key=lambda k: abs(k - self.spot_price))

    @property
    def total_call_oi(self) -> int:
        return sum(s.call.open_interest for s in self.strikes.values() if s.call)

    @property
    def total_put_oi(self) -> int:
        return sum(s.put.open_interest for s in self.strikes.values() if s.put)

    @property
    def put_call_ratio(self) -> float:
        call_oi = self.total_call_oi
        if call_oi == 0:
            return 0.0
        return float(self.total_put_oi) / float(call_oi)

    @property
    def max_pain_strike(self) -> Decimal:
        """Calculates the Max Pain strike (where option buyers lose maximum money / sellers pay minimum)."""
        if not self.strikes:
            return self.spot_price

        min_loss = Decimal("Infinity")
        max_pain = self.atm_strike

        for test_strike in self.strikes.keys():
            total_loss = Decimal("0")
            for strike_price, pair in self.strikes.items():
                if pair.call and test_strike > strike_price:
                    total_loss += (test_strike - strike_price) * Decimal(pair.call.open_interest)
                if pair.put and test_strike < strike_price:
                    total_loss += (strike_price - test_strike) * Decimal(pair.put.open_interest)

            if total_loss < min_loss:
                min_loss = total_loss
                max_pain = test_strike

        return max_pain
