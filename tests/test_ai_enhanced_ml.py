"""Unit tests for AIEnhancedMLEquityStrategy."""

from datetime import date, datetime
from decimal import Decimal

from quant_system.data.loader import SyntheticDataGenerator
from quant_system.strategies.ai_enhanced_ml import AIEnhancedMLEquityStrategy
from quant_system.strategies.base import MarketContext
from quant_system.strategies.registry import StrategyRegistry


def test_ai_enhanced_ml_strategy_creation_via_registry() -> None:
    strategy = StrategyRegistry.create("AIEnhancedMLEquity", params={"top_n": 2})
    assert isinstance(strategy, AIEnhancedMLEquityStrategy)
    assert strategy.name == "AIEnhancedMLEquity"


def test_ai_enhanced_ml_strategy_signal_generation() -> None:
    strategy = AIEnhancedMLEquityStrategy(
        name="TestAIEnhancedML",
        params={"train_window": 30, "top_n": 2, "confidence_threshold": 0.50},
    )

    bars_infy = SyntheticDataGenerator.generate_equity_bars(
        symbol="INFY",
        start_date=date(2025, 1, 1),
        days=70,
        initial_price=1000.0,
        seed=42,
    )
    bars_tcs = SyntheticDataGenerator.generate_equity_bars(
        symbol="TCS",
        start_date=date(2025, 1, 1),
        days=70,
        initial_price=3500.0,
        seed=43,
    )

    ctx = MarketContext(
        current_time=datetime(2025, 3, 11, 9, 15),
        current_bars={"INFY": bars_infy.bars[-1], "TCS": bars_tcs.bars[-1]},
        historical_bars={"INFY": bars_infy.bars, "TCS": bars_tcs.bars},
        current_positions={},
        available_cash=Decimal("1000000.00"),
        extra_data={},
    )

    signals = strategy.generate_signals(ctx)
    assert isinstance(signals, list)
    # The fixture is fully deterministic, so the count is asserted rather than assumed. Without
    # this the property checks below would silently stop running if the strategy ever produced
    # no signals, and the test would still pass.
    assert len(signals) == 1

    misattributed = [s for s in signals if s.strategy_name != "TestAIEnhancedML"]
    assert misattributed == [], f"signals must carry the strategy name, got {misattributed[:3]}"

    unweighted = [s for s in signals if s.target_weight is None]
    assert unweighted == [], f"every signal needs a target weight, got {unweighted[:3]}"

    over_cap = [s for s in signals if s.target_weight is not None and s.target_weight > 0.35]
    assert over_cap == [], f"target weight must respect the 0.35 cap, got {over_cap[:3]}"
