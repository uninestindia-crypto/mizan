"""Dual Momentum and Trend-Following strategy across equity baskets."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from quant_system.alpha.technical import TechnicalIndicators
from quant_system.core.domain import Side, Signal
from quant_system.strategies.base import BaseStrategy, MarketContext


class EquityDualMomentumStrategy(BaseStrategy):
    """Strategy that ranks assets by relative momentum and requires positive absolute trend."""

    def __init__(
        self,
        name: str = "EquityDualMomentum",
        params: Mapping[str, Any] | None = None,
    ) -> None:
        default_params = {
            "lookback_fast": 20,
            "lookback_slow": 50,
            "top_n": 3,
            "volatility_lookback": 20,
        }
        if params:
            default_params.update(params)
        super().__init__(name=name, params=default_params)

    def generate_signals(self, ctx: MarketContext) -> list[Signal]:
        signals: list[Signal] = []
        fast_period = int(self.params["lookback_fast"])
        slow_period = int(self.params["lookback_slow"])
        top_n = int(self.params["top_n"])

        candidate_scores: dict[str, float] = {}

        for symbol, bars in ctx.historical_bars.items():
            if len(bars) < slow_period + 1:
                continue

            closes = [b.close for b in bars]
            curr_bar = ctx.current_bars.get(symbol)
            if not curr_bar:
                continue

            curr_close = float(curr_bar.close)

            # Fast and Slow SMAs
            smas_fast = TechnicalIndicators.sma(closes, fast_period)
            smas_slow = TechnicalIndicators.sma(closes, slow_period)

            if not smas_fast or not smas_slow:
                continue

            # Absolute trend filter: Current price > Slow SMA & Fast SMA > Slow SMA
            if curr_close > smas_slow[-1] and smas_fast[-1] > smas_slow[-1]:
                # Relative momentum: Rate of return over slow period
                mom = (curr_close - float(closes[-slow_period])) / float(closes[-slow_period])
                candidate_scores[symbol] = mom

        # Rank candidates by momentum
        sorted_candidates = sorted(candidate_scores.items(), key=lambda x: x[1], reverse=True)
        selected_symbols = {sym for sym, _ in sorted_candidates[:top_n]}

        # Generate BUY signals for selected
        weight_per_asset = 1.0 / max(1, len(selected_symbols)) if selected_symbols else 0.0

        for sym in selected_symbols:
            signals.append(
                Signal(
                    symbol=sym,
                    side=Side.BUY,
                    strength=candidate_scores[sym],
                    timestamp=ctx.current_time,
                    strategy_name=self.name,
                    target_weight=weight_per_asset,
                )
            )

        # Generate EXIT signals for currently held assets that fell out of the top N
        for held_sym, pos in ctx.current_positions.items():
            if pos.quantity > 0 and held_sym not in selected_symbols:
                signals.append(
                    Signal(
                        symbol=held_sym,
                        side=None,  # Exit / Flat
                        strength=0.0,
                        timestamp=ctx.current_time,
                        strategy_name=self.name,
                        target_weight=0.0,
                    )
                )

        return signals
