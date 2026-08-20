"""Tests for BarAggregator, BarSeries methods, and HoldoutVault partitioning."""

from datetime import date, datetime, timedelta
from decimal import Decimal

import pytest

from quant_system.backtest.holdout import HoldoutVault
from quant_system.core.domain import PriceBar
from quant_system.data.bars import BarAggregator
from quant_system.data.loader import SyntheticDataGenerator


def test_bar_aggregator_resample_5min_and_hourly() -> None:
    base_time = datetime(2025, 1, 1, 9, 15)
    minute_bars = []

    for i in range(60):
        t = base_time + timedelta(minutes=i)
        minute_bars.append(
            PriceBar(
                symbol="INFY",
                timestamp=t,
                open=Decimal("1500.00") + Decimal(i),
                high=Decimal("1505.00") + Decimal(i),
                low=Decimal("1495.00") + Decimal(i),
                close=Decimal("1502.00") + Decimal(i),
                volume=1000,
            )
        )

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
    w = series.window(datetime(2025, 1, 5, 0, 0), datetime(2025, 1, 10, 23, 59))
    assert len(w) > 0
    for b in w:
        assert datetime(2025, 1, 5, 0, 0) <= b.timestamp <= datetime(2025, 1, 10, 23, 59)


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

    for b in partition.discovery_bars:
        assert b.timestamp.date() < split
    for b in partition.out_of_sample_bars:
        assert b.timestamp.date() >= split


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
