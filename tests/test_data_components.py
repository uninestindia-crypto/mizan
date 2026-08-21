"""Tests for BarAggregator, BarSeries methods, and HoldoutVault partitioning."""

from datetime import date, datetime, timedelta
from decimal import Decimal

import pytest

from quant_system.backtest.holdout import HoldoutVault
from quant_system.core.domain import PriceBar
from quant_system.data.bars import BarAggregator
from quant_system.data.loader import SyntheticDataGenerator


def _minute_bar(base_time: datetime, offset: int) -> PriceBar:
    """One synthetic minute bar, offset minutes after base_time."""
    return PriceBar(
        symbol="INFY",
        timestamp=base_time + timedelta(minutes=offset),
        open=Decimal("1500.00") + Decimal(offset),
        high=Decimal("1505.00") + Decimal(offset),
        low=Decimal("1495.00") + Decimal(offset),
        close=Decimal("1502.00") + Decimal(offset),
        volume=1000,
    )


def test_bar_aggregator_resample_5min_and_hourly() -> None:
    base_time = datetime(2025, 1, 1, 9, 15)
    minute_bars = [_minute_bar(base_time, i) for i in range(60)]
    assert len(minute_bars) == 60

    # 5-minute aggregation: 60 1-min bars -> 12 5-min bars
    bars_5m = BarAggregator.resample(minute_bars, 5)
    assert len(bars_5m) == 12
    assert bars_5m[0].open == minute_bars[0].open
    assert bars_5m[0].close == minute_bars[4].close
    assert bars_5m[0].volume == 5000

    # 60-minute aggregation: 60 1-min bars -> 2 bucket bars (09:00 bucket from 09:15-09:59, 10:00 bucket from 10:00-10:14)
    bars_60m = BarAggregator.resample(minute_bars, 60)
    assert len(bars_60m) == 2


def test_bar_series_window_and_properties() -> None:
    series = SyntheticDataGenerator.generate_equity_bars(
        symbol="INFY",
        start_date=date(2025, 1, 1),
        days=30,
        initial_price=1500.0,
        seed=42,
    )

    assert series.start_time is not None
    assert series.end_time is not None
    assert len(series.closes) == 30
    assert len(series.highs) == 30
    assert len(series.lows) == 30
    assert len(series.opens) == 30
    assert len(series.volumes) == 30

    # Test window query
    window_start = datetime(2025, 1, 5, 0, 0)
    window_end = datetime(2025, 1, 10, 23, 59)
    w = series.window(window_start, window_end)
    assert len(w) > 0

    outside = [b for b in w if not window_start <= b.timestamp <= window_end]
    assert outside == [], f"window returned bars outside its bounds: {outside[:3]}"


def test_holdout_vault_partition() -> None:
    series = SyntheticDataGenerator.generate_equity_bars(
        symbol="INFY",
        start_date=date(2025, 1, 1),
        days=50,
        initial_price=1500.0,
        seed=42,
    )

    split = date(2025, 1, 25)
    partition = HoldoutVault.partition(series.bars, split)

    assert len(partition.discovery_bars) > 0
    assert len(partition.out_of_sample_bars) > 0
    assert len(partition.discovery_bars) + len(partition.out_of_sample_bars) == 50
    assert len(partition.manifest_hash) == 64  # SHA-256 hex string

    leaked_into_discovery = [b for b in partition.discovery_bars if b.timestamp.date() >= split]
    assert leaked_into_discovery == [], (
        f"discovery must hold only pre-split bars, got {leaked_into_discovery[:3]}"
    )

    leaked_into_holdout = [b for b in partition.out_of_sample_bars if b.timestamp.date() < split]
    assert leaked_into_holdout == [], (
        f"holdout must hold only post-split bars, got {leaked_into_holdout[:3]}"
    )


def test_holdout_vault_invalid_split() -> None:
    series = SyntheticDataGenerator.generate_equity_bars(
        symbol="INFY",
        start_date=date(2025, 1, 1),
        days=10,
        initial_price=1500.0,
        seed=42,
    )

    # Split before dataset
    with pytest.raises(ValueError, match="Partition produced empty set"):
        HoldoutVault.partition(series.bars, date(2024, 1, 1))
