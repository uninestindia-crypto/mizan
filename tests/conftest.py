"""Shared fixtures for Quant System tests."""

from datetime import date, datetime
from decimal import Decimal

import pytest

from quant_system.core.domain import PriceBar, Quote
from quant_system.data.loader import SyntheticDataGenerator


@pytest.fixture
def sample_bars() -> list[PriceBar]:
    series = SyntheticDataGenerator.generate_equity_bars(
        symbol="INFY",
        start_date=date(2025, 1, 1),
        days=60,
        initial_price=1500.0,
        seed=42,
    )
    return series.bars


@pytest.fixture
def sample_quote() -> Quote:
    return Quote(
        symbol="INFY",
        timestamp=datetime(2025, 1, 1, 9, 15),
        bid=Decimal("1500.00"),
        ask=Decimal("1500.50"),
        bid_size=1000,
        ask_size=1200,
        last_price=Decimal("1500.25"),
    )
