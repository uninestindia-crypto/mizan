"""Mīzān Strategy: Flagship pooled cross-sectional machine learning strategy for QuantOS.

Mīzān is the official, unified ML strategy for QuantOS. It scores a cross-sectional universe
of instruments using the standalone `MizanModel`, ranks the assets by predicted alpha, and
allocates capital into the top-ranking deciles/names with strict risk budgeting.
"""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from decimal import Decimal
from typing import Any

from quant_system.alpha.technical import TechnicalIndicators
from quant_system.core.domain import PriceBar, Side, Signal
from quant_system.modeling.mizan_model import MizanModel
from quant_system.strategies.base import BaseStrategy, MarketContext


class MizanStrategy(BaseStrategy):
    """Flagship QuantOS pooled cross-sectional machine learning strategy.

    Features evaluated per instrument across the universe:
    - 1-day, 5-day, 21-day normalized returns
    - Garman-Klass and Parkinson high/low/close volatility estimates
    - 14-period RSI (centered)
    - 20-period and 50-period SMA distance
    - Volume z-score & Money flow multiplier
    - Market regime indicators (India VIX & Nifty 5-day return)
    - Cross-sectional percentile momentum & volume surprise ranks
    """

    def __init__(
        self,
        name: str = "MizanStrategy",
        params: Mapping[str, Any] | None = None,
        model: MizanModel | None = None,
    ) -> None:
        default_params = {
            "top_n": 5,
            "min_bars_required": 51,
            "confidence_threshold": 0.0,
            "max_single_weight": 0.25,
            "model_path": None,
        }
        if params:
            default_params.update(params)
        super().__init__(name=name, params=default_params)

        model_path = self.params.get("model_path")
        if model is not None:
            self.model = model
        elif model_path:
            self.model = MizanModel.from_pretrained(model_path)
        else:
            self.model = MizanModel.default_model()

    @staticmethod
    def _extract_single_features(
        bars: Sequence[PriceBar],
    ) -> dict[str, float] | None:
        """Extract per-instrument time-series features from historical price bars."""
        n_bars = len(bars)
        if n_bars < 51:
            return None

        closes = [float(b.close) for b in bars]
        highs = [float(b.high) for b in bars]
        lows = [float(b.low) for b in bars]
        opens = [float(b.open) for b in bars]
        volumes = [float(b.volume) for b in bars]

        curr_close = closes[-1]
        if curr_close <= 0.0:
            return None

        # 1. Multi-period Returns
        ret_1 = (curr_close - closes[-2]) / closes[-2] if closes[-2] > 0 else 0.0
        ret_5 = (curr_close - closes[-6]) / closes[-6] if closes[-6] > 0 else 0.0
        ret_21 = (curr_close - closes[-22]) / closes[-22] if closes[-22] > 0 else 0.0

        # 2. Volatility factors (Garman-Klass and Parkinson over 20 bars)
        gk_terms = []
        park_terms = []
        for i in range(n_bars - 20, n_bars):
            hi, lo, op, cl = highs[i], lows[i], opens[i], closes[i]
            if op > 0 and cl > 0 and lo > 0 and hi >= lo:
                log_hl = math.log(hi / lo) ** 2
                log_co = math.log(cl / op) ** 2
                gk = 0.5 * log_hl - (2.0 * math.log(2.0) - 1.0) * log_co
                park = (1.0 / (4.0 * math.log(2.0))) * log_hl
                gk_terms.append(gk)
                park_terms.append(park)

        gk_vol = math.sqrt(max(0.0, sum(gk_terms) / max(1, len(gk_terms))))
        park_vol = math.sqrt(max(0.0, sum(park_terms) / max(1, len(park_terms))))

        # 3. RSI 14 (centered)
        rsi_series = TechnicalIndicators.rsi([Decimal(str(c)) for c in closes], period=14)
        rsi_val = (rsi_series[-1] - 50.0) / 50.0 if rsi_series else 0.0

        # 4. SMA 20 & 50 Distance
        sma_20 = TechnicalIndicators.sma([Decimal(str(c)) for c in closes], period=20)
        sma_50 = TechnicalIndicators.sma([Decimal(str(c)) for c in closes], period=50)
        sma_20_dist = (curr_close - sma_20[-1]) / curr_close if sma_20 else 0.0
        sma_50_dist = (curr_close - sma_50[-1]) / curr_close if sma_50 else 0.0

        # 5. Volume z-score and Money Flow
        recent_vols = volumes[-20:]
        vol_mean = sum(recent_vols) / len(recent_vols)
        vol_std = math.sqrt(sum((v - vol_mean) ** 2 for v in recent_vols) / len(recent_vols))
        vol_z = (volumes[-1] - vol_mean) / vol_std if vol_std > 0 else 0.0

        # Money flow multiplier: ((Close - Low) - (High - Close)) / (High - Low)
        hl_diff = highs[-1] - lows[-1]
        mfm = ((curr_close - lows[-1]) - (highs[-1] - curr_close)) / hl_diff if hl_diff > 0 else 0.0

        # 6. Default Macro Regimes (if market context does not inject external index)
        vix_level = 0.15
        vix_change_5 = 0.0
        nifty_ret_5 = ret_5

        return {
            "return_1": ret_1,
            "return_5": ret_5,
            "return_21": ret_21,
            "garman_klass_volatility": gk_vol,
            "parkinson_volatility": park_vol,
            "rsi_14_centered": rsi_val,
            "sma_20_distance": sma_20_dist,
            "sma_50_distance": sma_50_dist,
            "volume_zscore": vol_z,
            "money_flow_multiplier": mfm,
            "india_vix_level": vix_level,
            "india_vix_change_5": vix_change_5,
            "nifty_return_5": nifty_ret_5,
        }

    def generate_signals(self, ctx: MarketContext) -> list[Signal]:
        """Generate top-ranked cross-sectional signals for the universe."""
        signals: list[Signal] = []
        top_n = int(self.params.get("top_n", 5))
        threshold = float(self.params.get("confidence_threshold", 0.0))
        max_weight = float(self.params.get("max_single_weight", 0.25))

        raw_universe_features: dict[str, dict[str, float]] = {}

        # 1. Compute time-series features for each symbol
        for symbol, bars in ctx.historical_bars.items():
            feats = self._extract_single_features(bars)
            if feats is not None:
                raw_universe_features[symbol] = feats

        if not raw_universe_features:
            return signals

        # 2. Compute cross-sectional ranks across all active symbols
        n_syms = len(raw_universe_features)
        # Momentum 5 rank
        sorted_by_mom = sorted(
            raw_universe_features.keys(), key=lambda s: raw_universe_features[s]["return_5"]
        )
        # Volume surprise rank
        sorted_by_vol = sorted(
            raw_universe_features.keys(), key=lambda s: raw_universe_features[s]["volume_zscore"]
        )

        full_features: dict[str, dict[str, float]] = {}
        for idx, sym in enumerate(sorted_by_mom):
            mom_rank = (idx / max(1, n_syms - 1)) - 0.5  # centered in [-0.5, 0.5]
            full_features.setdefault(sym, dict(raw_universe_features[sym]))[
                "cs_rank_momentum_5"
            ] = mom_rank

        for idx, sym in enumerate(sorted_by_vol):
            vol_rank = (idx / max(1, n_syms - 1)) - 0.5  # centered in [-0.5, 0.5]
            full_features[sym]["cs_rank_volume_surprise"] = vol_rank

        # 3. Model Scoring & Ranking
        ranked_candidates = self.model.rank_universe(full_features)

        # Select candidates clearing the model score threshold
        selected = [(sym, score) for sym, score in ranked_candidates if score >= threshold][:top_n]

        selected_symbols = {sym for sym, _ in selected}
        n_selected = len(selected_symbols)
        weight_per_asset = min(max_weight, 1.0 / n_selected) if n_selected > 0 else 0.0

        # Generate BUY signals for top selected symbols
        for sym, score in selected:
            signals.append(
                Signal(
                    symbol=sym,
                    side=Side.BUY,
                    strength=float(score),
                    timestamp=ctx.current_time,
                    strategy_name=self.name,
                    target_weight=weight_per_asset,
                    metadata={
                        "candidate_id": self.model.candidate_id,
                        "model_id": self.model.model_id,
                        "score": score,
                        "rank": next(i for i, (s, _) in enumerate(ranked_candidates) if s == sym)
                        + 1,
                    },
                )
            )

        # Generate EXIT signals for currently held positions no longer selected
        for held_sym, pos in ctx.current_positions.items():
            if pos.quantity > 0 and held_sym not in selected_symbols:
                signals.append(
                    Signal(
                        symbol=held_sym,
                        side=None,  # Flat
                        strength=0.0,
                        timestamp=ctx.current_time,
                        strategy_name=self.name,
                        target_weight=0.0,
                    )
                )

        return signals
