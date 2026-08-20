"""Tests for MLEquityStrategy and rolling ML classification."""

from datetime import date, datetime
from decimal import Decimal

import numpy as np

from quant_system.data.loader import SyntheticDataGenerator
from quant_system.strategies.base import MarketContext
from quant_system.strategies.ml_equity import MLEquityStrategy, RollingRidgeClassifier


def test_rolling_ridge_classifier_fit_and_predict() -> None:
    clf = RollingRidgeClassifier(l2_penalty=1.0)
    # Linearly separable 2D data
    X = np.array(
        [
            [1.0, 2.0],
            [2.0, 3.0],
            [-1.0, -2.0],
            [-2.0, -3.0],
        ]
    )
    y = np.array([1.0, 1.0, -1.0, -1.0])
    clf.fit(X, y)

    prob_pos = clf.predict_score(np.array([1.5, 2.5]))
    prob_neg = clf.predict_score(np.array([-1.5, -2.5]))

    assert prob_pos > 0.5
    assert prob_neg < 0.5


def test_ml_equity_strategy_signal_generation() -> None:
    strategy = MLEquityStrategy(
        name="TestMLEquity",
        params={"train_window": 30, "top_n": 1, "confidence_threshold": 0.50},
    )

    bars = SyntheticDataGenerator.generate_equity_bars(
        symbol="INFY",
        start_date=date(2025, 1, 1),
        days=70,
        initial_price=1000.0,
        seed=42,
    )

    ctx = MarketContext(
        current_time=datetime(2025, 3, 11, 9, 15),
        current_bars={"INFY": bars.bars[-1]},
        historical_bars={"INFY": bars.bars},
        current_positions={},
        available_cash=Decimal("1000000.00"),
        extra_data={},
    )

    signals = strategy.generate_signals(ctx)
    assert isinstance(signals, list)
    if signals:
        assert signals[0].symbol == "INFY"
        assert signals[0].strategy_name == "TestMLEquity"
