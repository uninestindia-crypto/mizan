"""AI-Enhanced Machine Learning Strategy combining rolling statistical alpha with multi-agent consensus."""

from __future__ import annotations

from collections.abc import Mapping
from decimal import Decimal
from typing import Any

import numpy as np

from quant_system.alpha.ai_advisor import MultiAgentConsensusEngine
from quant_system.alpha.technical import TechnicalIndicators
from quant_system.core.domain import Side, Signal
from quant_system.strategies.base import BaseStrategy, MarketContext
from quant_system.strategies.ml_equity import MLEquityStrategy, RollingRidgeClassifier


class AIEnhancedMLEquityStrategy(BaseStrategy):
    """Integrates statistical ML probability with multi-agent (Claude/Codex/Antigravity) consensus.

    Pipeline:
    1. Feature Engineering: Returns, RSI, SMA distance, ATR.
    2. Rolling Statistical Classifier: Computes zero-lookahead direction probability.
    3. Multi-Agent AI Advisory: Evaluates technical context, checks for divergence/vetoes,
       and calculates conviction-based position weight multipliers.
    """

    def __init__(
        self,
        name: str = "AIEnhancedMLEquityStrategy",
        params: Mapping[str, Any] | None = None,
        consensus_engine: MultiAgentConsensusEngine | None = None,
    ) -> None:
        default_params = {
            "train_window": 60,
            "top_n": 2,
            "confidence_threshold": 0.52,
            "l2_penalty": 1.0,
            "require_ai_confirmation": True,
        }
        if params:
            default_params.update(params)
        super().__init__(name=name, params=default_params)
        self.consensus_engine = consensus_engine or MultiAgentConsensusEngine()

    def generate_signals(self, ctx: MarketContext) -> list[Signal]:
        signals: list[Signal] = []
        train_window = int(self.params["train_window"])
        top_n = int(self.params["top_n"])
        threshold = float(self.params["confidence_threshold"])
        l2_penalty = float(self.params["l2_penalty"])
        require_ai = bool(self.params["require_ai_confirmation"])

        candidate_scores: dict[str, float] = {}
        candidate_weights: dict[str, float] = {}
        candidate_opinions: dict[str, str] = {}

        for symbol, bars in ctx.historical_bars.items():
            n_bars = len(bars)
            if n_bars < train_window + 22:
                continue

            # Build zero-lookahead training dataset
            X_train: list[list[float]] = []
            y_train: list[float] = []

            start_i = max(20, n_bars - train_window - 1)
            for i in range(start_i, n_bars - 1):
                feat = MLEquityStrategy._extract_feature_vector(bars, i)
                if feat is None:
                    continue
                fwd_ret = float(bars[i + 1].close) - float(bars[i].close)
                X_train.append(feat)
                y_train.append(1.0 if fwd_ret > 0 else -1.0)

            if len(X_train) < 20:
                continue

            # Fit rolling classifier
            model = RollingRidgeClassifier(l2_penalty=l2_penalty)
            model.fit(np.array(X_train), np.array(y_train))

            # Evaluate latest bar
            curr_feat = MLEquityStrategy._extract_feature_vector(bars, n_bars - 1)
            if curr_feat is None:
                continue

            prob_up = model.predict_score(np.array(curr_feat))

            if prob_up > threshold:
                closes = [float(b.close) for b in bars]
                curr_p = closes[-1]
                rsi_series = TechnicalIndicators.rsi([Decimal(str(c)) for c in closes], period=14)
                sma_series = TechnicalIndicators.sma([Decimal(str(c)) for c in closes], period=20)
                atr_series = TechnicalIndicators.atr(bars, period=14)

                tech_summary = {
                    "current_price": curr_p,
                    "rsi": rsi_series[-1] if rsi_series else 50.0,
                    "sma_distance_pct": (curr_p - sma_series[-1]) / curr_p if sma_series else 0.0,
                    "atr_normalized": (atr_series[-1] / curr_p) if atr_series else 0.02,
                    "return_5d": curr_feat[1],
                    "model_prob_up": prob_up,
                }

                # Query AI multi-agent consensus
                ai_opinion = self.consensus_engine.evaluate(
                    symbol=symbol,
                    quant_side=Side.BUY,
                    quant_strength=prob_up,
                    technical_summary=tech_summary,
                )

                # Skip if vetoed by AI advisory layer
                if require_ai and (
                    ai_opinion.action_bias == "VETO" or ai_opinion.weight_multiplier <= 0.0
                ):
                    continue

                candidate_scores[symbol] = prob_up * ai_opinion.confidence
                candidate_weights[symbol] = ai_opinion.weight_multiplier
                candidate_opinions[symbol] = ai_opinion.rationale

        # Rank and pick top N assets
        sorted_candidates = sorted(candidate_scores.items(), key=lambda x: x[1], reverse=True)
        selected_symbols = {sym for sym, _ in sorted_candidates[:top_n]}

        base_weight = 1.0 / max(1, len(selected_symbols)) if selected_symbols else 0.0

        for sym in selected_symbols:
            mult = candidate_weights.get(sym, 1.0)
            final_weight = min(0.35, base_weight * mult)
            signals.append(
                Signal(
                    symbol=sym,
                    side=Side.BUY,
                    strength=candidate_scores[sym],
                    timestamp=ctx.current_time,
                    strategy_name=self.name,
                    target_weight=final_weight,
                )
            )

        # Generate EXIT signals for currently held positions no longer selected
        for held_sym, pos in ctx.current_positions.items():
            if pos.quantity > 0 and held_sym not in selected_symbols:
                signals.append(
                    Signal(
                        symbol=held_sym,
                        side=None,  # Exit to Flat
                        strength=0.0,
                        timestamp=ctx.current_time,
                        strategy_name=self.name,
                        target_weight=0.0,
                    )
                )

        return signals
