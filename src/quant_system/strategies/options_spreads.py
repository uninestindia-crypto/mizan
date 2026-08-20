"""Directional Vertical Spreads (Bull Call Spread / Bear Put Spread) strategy."""

from __future__ import annotations

from collections.abc import Mapping
from decimal import Decimal
from typing import Any

from quant_system.core.domain import Side, Signal
from quant_system.data.option_chain import OptionChain
from quant_system.strategies.base import BaseStrategy, MarketContext


class DirectionalSpreadStrategy(BaseStrategy):
    """Executes defined-risk 2-leg vertical spreads (Bull Call or Bear Put) based on underlying directional bias."""

    def __init__(
        self,
        name: str = "DirectionalVerticalSpreads",
        params: Mapping[str, Any] | None = None,
    ) -> None:
        default_params = {
            "spread_width_points": 100,
            "max_risk_pct": 0.02,
        }
        if params:
            default_params.update(params)
        super().__init__(name=name, params=default_params)

    def generate_signals(self, ctx: MarketContext) -> list[Signal]:
        signals: list[Signal] = []
        chain: OptionChain | None = ctx.extra_data.get("option_chain")
        bias: str | None = ctx.extra_data.get("directional_bias")  # "BULLISH" or "BEARISH"

        if not chain or not bias or ctx.current_positions:
            return signals

        atm_strike = chain.atm_strike
        width = Decimal(str(self.params["spread_width_points"]))

        if bias == "BULLISH":
            # Bull Call Spread: Buy ATM Call, Sell OTM Call (ATM + width)
            buy_strike = atm_strike
            sell_strike = atm_strike + width

            buy_leg = chain.strikes.get(buy_strike)
            sell_leg = chain.strikes.get(sell_strike)

            if buy_leg and buy_leg.call and sell_leg and sell_leg.call:
                signals.append(
                    Signal(
                        symbol=buy_leg.call.symbol,
                        side=Side.BUY,
                        strength=1.0,
                        timestamp=ctx.current_time,
                        strategy_name=self.name,
                        metadata={"leg": "LONG_CALL", "strike": str(buy_strike)},
                    )
                )
                signals.append(
                    Signal(
                        symbol=sell_leg.call.symbol,
                        side=Side.SELL,
                        strength=1.0,
                        timestamp=ctx.current_time,
                        strategy_name=self.name,
                        metadata={"leg": "SHORT_CALL", "strike": str(sell_strike)},
                    )
                )

        elif bias == "BEARISH":
            # Bear Put Spread: Buy ATM Put, Sell OTM Put (ATM - width)
            buy_strike = atm_strike
            sell_strike = atm_strike - width

            buy_leg = chain.strikes.get(buy_strike)
            sell_leg = chain.strikes.get(sell_strike)

            if buy_leg and buy_leg.put and sell_leg and sell_leg.put:
                signals.append(
                    Signal(
                        symbol=buy_leg.put.symbol,
                        side=Side.BUY,
                        strength=1.0,
                        timestamp=ctx.current_time,
                        strategy_name=self.name,
                        metadata={"leg": "LONG_PUT", "strike": str(buy_strike)},
                    )
                )
                signals.append(
                    Signal(
                        symbol=sell_leg.put.symbol,
                        side=Side.SELL,
                        strength=1.0,
                        timestamp=ctx.current_time,
                        strategy_name=self.name,
                        metadata={"leg": "SHORT_PUT", "strike": str(sell_strike)},
                    )
                )

        return signals
