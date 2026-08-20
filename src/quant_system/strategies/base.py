"""Abstract Base Strategy interface and protocol definitions."""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Any

from quant_system.core.domain import Position, PriceBar, Signal


@dataclass(frozen=True, slots=True)
class MarketContext:
    """Encapsulates available historical and point-in-time state provided to a strategy on every tick/bar."""

    current_time: datetime
    current_bars: Mapping[str, PriceBar]
    historical_bars: Mapping[str, Sequence[PriceBar]]
    current_positions: Mapping[str, Position]
    available_cash: Decimal
    extra_data: Mapping[str, Any]


class BaseStrategy(ABC):
    """Abstract base class that all quant trading strategies must implement."""

    def __init__(self, name: str, params: Mapping[str, Any] | None = None) -> None:
        self.name: str = name
        self.params: dict[str, Any] = dict(params or {})

    @abstractmethod
    def generate_signals(self, ctx: MarketContext) -> list[Signal]:
        """Calculates trading signals given current market context with zero lookahead."""
        raise NotImplementedError
