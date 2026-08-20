"""Intraday ATM Straddle decay / Delta-Neutral options writing strategy."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import time
from decimal import Decimal
from typing import Any

from quant_system.core.domain import Side, Signal
from quant_system.data.option_chain import OptionChain
from quant_system.strategies.base import BaseStrategy, MarketContext


class IntradayStraddleDecayStrategy(BaseStrategy):
    """Sells an ATM Call and ATM Put at 09:20 AM IST to capture intraday theta decay, with individual stop-losses."""

    def __init__(
        self,
        name: str = "IntradayATMStraddle",
        params: Mapping[str, Any] | None = None,
    ) -> None:
        default_params = {
            "underlying": "NIFTY",
            "entry_time": time(9, 20),
            "exit_time": time(15, 15),
            "stop_loss_pct": 0.25,  # 25% stop loss on each leg
            "target_decay_pct": 0.50,  # 50% combined profit target
        }
        if params:
            default_params.update(params)
        super().__init__(name=name, params=default_params)
        self._entered_today = False

    def generate_signals(self, ctx: MarketContext) -> list[Signal]:
        signals: list[Signal] = []
        chain: OptionChain | None = ctx.extra_data.get("option_chain")
        if not chain:
            return signals

        curr_t = ctx.current_time.time()
        entry_t = self.params["entry_time"]
        exit_t = self.params["exit_time"]

        # Reset daily entry flag at morning open
        if curr_t < entry_t:
            self._entered_today = False
            return signals

        # Entry window: at or immediately after entry_time if not already entered
        if entry_t <= curr_t < exit_t and not self._entered_today and not ctx.current_positions:
            atm_strike = chain.atm_strike
            strike_data = chain.strikes.get(atm_strike)

            if strike_data and strike_data.call and strike_data.put:
                sl_mult = Decimal(str(1.0 + self.params["stop_loss_pct"]))

                # Short Call signal
                signals.append(
                    Signal(
                        symbol=strike_data.call.symbol,
                        side=Side.SELL,
                        strength=1.0,
                        timestamp=ctx.current_time,
                        strategy_name=self.name,
                        stop_loss=strike_data.call.mid_price * sl_mult,
                        metadata={"leg": "CALL", "strike": str(atm_strike)},
                    )
                )

                # Short Put signal
                signals.append(
                    Signal(
                        symbol=strike_data.put.symbol,
                        side=Side.SELL,
                        strength=1.0,
                        timestamp=ctx.current_time,
                        strategy_name=self.name,
                        stop_loss=strike_data.put.mid_price * sl_mult,
                        metadata={"leg": "PUT", "strike": str(atm_strike)},
                    )
                )
                self._entered_today = True

        # Mandatory squared-off exit at 15:15 IST
        elif curr_t >= exit_t and ctx.current_positions:
            for symbol, pos in ctx.current_positions.items():
                if pos.quantity != 0:
                    signals.append(
                        Signal(
                            symbol=symbol,
                            side=None,  # Square off
                            strength=0.0,
                            timestamp=ctx.current_time,
                            strategy_name=self.name,
                            metadata={"reason": "INTRADAY_TIME_SQUAREOFF"},
                        )
                    )

        return signals
