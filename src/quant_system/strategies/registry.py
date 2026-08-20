"""Strategy registry and discovery factory."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from quant_system.strategies.ai_enhanced_ml import AIEnhancedMLEquityStrategy
from quant_system.strategies.base import BaseStrategy
from quant_system.strategies.equity_momentum import EquityDualMomentumStrategy
from quant_system.strategies.ml_equity import MLEquityStrategy
from quant_system.strategies.options_spreads import DirectionalSpreadStrategy
from quant_system.strategies.options_straddle import IntradayStraddleDecayStrategy


class StrategyRegistry:
    """Central registry mapping strategy names to strategy class factories."""

    _REGISTRY: dict[str, type[BaseStrategy]] = {
        "EquityDualMomentum": EquityDualMomentumStrategy,
        "IntradayATMStraddle": IntradayStraddleDecayStrategy,
        "DirectionalVerticalSpreads": DirectionalSpreadStrategy,
        "MLEquityStrategy": MLEquityStrategy,
        "AIEnhancedMLEquity": AIEnhancedMLEquityStrategy,
    }

    @classmethod
    def register(cls, name: str, strategy_cls: type[BaseStrategy]) -> None:
        cls._REGISTRY[name] = strategy_cls

    @classmethod
    def create(cls, name: str, params: Mapping[str, Any] | None = None) -> BaseStrategy:
        if name not in cls._REGISTRY:
            raise KeyError(f"Unknown strategy '{name}'. Registered: {list(cls._REGISTRY.keys())}")
        return cls._REGISTRY[name](name=name, params=params)

    @classmethod
    def list_strategies(cls) -> list[str]:
        return list(cls._REGISTRY.keys())
