"""Machine Learning based Equity Strategy using rolling statistical classifiers."""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from decimal import Decimal
from typing import Any

import numpy as np

from quant_system.alpha.technical import TechnicalIndicators
from quant_system.core.domain import PriceBar, Side, Signal
from quant_system.strategies.base import BaseStrategy, MarketContext


class RollingRidgeClassifier:
    """Compact, fast Ridge/Logistic classifier implemented in pure NumPy/SciPy."""

    def __init__(self, l2_penalty: float = 1.0) -> None:
        self.l2_penalty = l2_penalty
        self.weights: np.ndarray | None = None
        self.bias: float = 0.0

    def fit(self, X: np.ndarray, y: np.ndarray) -> None:
        """Fits regularized linear classification weights: y in {-1, 1}."""
        n_samples, n_features = X.shape
        if n_samples < n_features + 2:
            return

        # Add bias column
        X_ext = np.hstack([np.ones((n_samples, 1)), X])
        reg = self.l2_penalty * np.eye(n_features + 1)
        reg[0, 0] = 0.0  # Do not regularize bias

        # Closed-form Ridge solution: (X^T X + lambda*I)^(-1) X^T y
        try:
            A = X_ext.T @ X_ext + reg
            b = X_ext.T @ y
            params = np.linalg.solve(A, b)
            self.bias = float(params[0])
            self.weights = params[1:]
        except np.linalg.LinAlgError:
            self.weights = np.zeros(n_features)
            self.bias = 0.0

    def predict_score(self, x: np.ndarray) -> float:
        """Returns continuous prediction score and sigmoid probability."""
        if self.weights is None or len(self.weights) != len(x):
            return 0.5
        z = float(np.dot(self.weights, x) + self.bias)
        # Sigmoid squash
        prob = 1.0 / (1.0 + math.exp(-max(-20.0, min(20.0, z))))
        return prob


class MLEquityStrategy(BaseStrategy):
    """Equity strategy powered by a rolling, domain-specific ML model.

    Features extracted per bar:
    1. 1-day normalized return
    2. 5-day normalized return
    3. 10-day normalized return
    4. 14-period RSI (centered & scaled)
    5. Distance to 20-period SMA / Price
    6. Normalized ATR volatility
    """

    def __init__(
        self,
        name: str = "MLEquityStrategy",
        params: Mapping[str, Any] | None = None,
    ) -> None:
        default_params = {
            "train_window": 60,
            "top_n": 2,
            "confidence_threshold": 0.52,
            "l2_penalty": 1.0,
        }
        if params:
            default_params.update(params)
        super().__init__(name=name, params=default_params)

    @staticmethod
    def _extract_feature_vector(
        bars: Sequence[PriceBar],
        idx: int,
    ) -> list[float] | None:
        """Extracts engineered technical features for bar at index `idx`."""
        if idx < 20:
            return None

        sub_bars = bars[: idx + 1]
        closes = [float(b.close) for b in sub_bars]
        curr_p = closes[-1]
        if curr_p <= 0.0:
            return None

        # 1. Multi-period Returns
        ret_1 = (curr_p - closes[-2]) / closes[-2] if closes[-2] > 0 else 0.0
        ret_5 = (curr_p - closes[-6]) / closes[-6] if idx >= 5 and closes[-6] > 0 else 0.0
        ret_10 = (curr_p - closes[-11]) / closes[-11] if idx >= 10 and closes[-11] > 0 else 0.0

        # 2. RSI Factor
        rsi_series = TechnicalIndicators.rsi([Decimal(str(c)) for c in closes], period=14)
        rsi_val = (rsi_series[-1] - 50.0) / 50.0 if rsi_series else 0.0

        # 3. SMA Distance
        sma_series = TechnicalIndicators.sma([Decimal(str(c)) for c in closes], period=20)
        sma_dist = (curr_p - sma_series[-1]) / curr_p if sma_series else 0.0

        # 4. Normalized ATR
        atr_series = TechnicalIndicators.atr(sub_bars, period=14)
        atr_norm = (atr_series[-1] / curr_p) if atr_series else 0.0

        return [ret_1, ret_5, ret_10, rsi_val, sma_dist, atr_norm]

    def generate_signals(self, ctx: MarketContext) -> list[Signal]:
        signals: list[Signal] = []
        train_window = int(self.params["train_window"])
        top_n = int(self.params["top_n"])
        threshold = float(self.params["confidence_threshold"])
        l2_penalty = float(self.params["l2_penalty"])

        candidate_scores: dict[str, float] = {}

        for symbol, bars in ctx.historical_bars.items():
            n_bars = len(bars)
            if n_bars < train_window + 22:
                continue

            # Build training dataset strictly from past closed bars [0 ... n_bars - 2]
            X_train: list[list[float]] = []
            y_train: list[float] = []

            # Start index after lookback warmup
            start_i = max(20, n_bars - train_window - 1)
            for i in range(start_i, n_bars - 1):
                feat = self._extract_feature_vector(bars, i)
                if feat is None:
                    continue
                # Forward 1-bar return label (+1 if positive, -1 if negative)
                fwd_ret = float(bars[i + 1].close) - float(bars[i].close)
                label = 1.0 if fwd_ret > 0 else -1.0
                X_train.append(feat)
                y_train.append(label)

            if len(X_train) < 20:
                continue

            # Fit model on historical data
            model = RollingRidgeClassifier(l2_penalty=l2_penalty)
            model.fit(np.array(X_train), np.array(y_train))

            # Current bar feature vector (zero lookahead)
            curr_feat = self._extract_feature_vector(bars, n_bars - 1)
            if curr_feat is None:
                continue

            prob_up = model.predict_score(np.array(curr_feat))
            if prob_up > threshold:
                candidate_scores[symbol] = prob_up

        # Rank candidates by probability
        sorted_candidates = sorted(candidate_scores.items(), key=lambda x: x[1], reverse=True)
        selected_symbols = {sym for sym, _ in sorted_candidates[:top_n]}

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

        # Generate EXIT signals for currently held positions no longer meeting criteria
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
