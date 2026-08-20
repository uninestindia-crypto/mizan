"""Price bar validation, historical series containers, and time resampling."""

from __future__ import annotations

from collections.abc import Iterator, Sequence
from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal

from quant_system.core.domain import PriceBar


@dataclass
class BarSeries:
    """Ordered sequence of chronological price bars for a single asset."""

    symbol: str
    bars: list[PriceBar]

    def __len__(self) -> int:
        return len(self.bars)

    def __iter__(self) -> Iterator[PriceBar]:
        return iter(self.bars)

    def __getitem__(self, index: int) -> PriceBar:
        return self.bars[index]

    @property
    def start_time(self) -> datetime | None:
        return self.bars[0].timestamp if self.bars else None

    @property
    def end_time(self) -> datetime | None:
        return self.bars[-1].timestamp if self.bars else None

    @property
    def closes(self) -> list[Decimal]:
        return [b.close for b in self.bars]

    @property
    def highs(self) -> list[Decimal]:
        return [b.high for b in self.bars]

    @property
    def lows(self) -> list[Decimal]:
        return [b.low for b in self.bars]

    @property
    def opens(self) -> list[Decimal]:
        return [b.open for b in self.bars]

    @property
    def volumes(self) -> list[int]:
        return [b.volume for b in self.bars]

    def append(self, bar: PriceBar) -> None:
        if self.bars and bar.timestamp <= self.bars[-1].timestamp:
            raise ValueError(
                f"Non-chronological bar timestamp {bar.timestamp} <= last {self.bars[-1].timestamp}"
            )
        self.bars.append(bar)

    def window(self, start: datetime, end: datetime) -> list[PriceBar]:
        """Returns price bars within the closed interval [start, end]."""
        return [b for b in self.bars if start <= b.timestamp <= end]


class BarAggregator:
    """Aggregates higher-frequency bars (e.g. 1-minute) into higher timeframe bars (e.g. 5-minute, 15-minute, Daily)."""

    @staticmethod
    def _compute_bucket_start(ts: datetime, interval_minutes: int) -> datetime:
        """Computes the deterministic start timestamp of the aggregation bucket for a given timestamp."""
        if interval_minutes >= 1440:
            # Daily or multi-day intervals: align to midnight of the date
            days_interval = interval_minutes // 1440
            if days_interval <= 1:
                return ts.replace(hour=0, minute=0, second=0, microsecond=0)
            # Multi-day bucket from epoch
            epoch = datetime(1970, 1, 1, tzinfo=ts.tzinfo)
            day_diff = (ts.date() - epoch.date()).days
            bucket_day_diff = (day_diff // days_interval) * days_interval
            bucket_date = epoch.date() + timedelta(days=bucket_day_diff)
            return datetime.combine(bucket_date, datetime.min.time(), tzinfo=ts.tzinfo)

        # Intraday interval: bucket relative to midnight of the same day
        minutes_from_midnight = ts.hour * 60 + ts.minute
        bucket_minutes = (minutes_from_midnight // interval_minutes) * interval_minutes
        bucket_hour = bucket_minutes // 60
        bucket_min = bucket_minutes % 60
        return ts.replace(hour=bucket_hour, minute=bucket_min, second=0, microsecond=0)

    @classmethod
    def resample(cls, bars: Sequence[PriceBar], interval_minutes: int) -> list[PriceBar]:
        if not bars:
            return []
        if interval_minutes <= 0:
            raise ValueError("interval_minutes must be > 0")

        grouped: list[PriceBar] = []
        current_bucket_start: datetime | None = None
        bucket_bars: list[PriceBar] = []

        for bar in bars:
            bucket_start = cls._compute_bucket_start(bar.timestamp, interval_minutes)

            if current_bucket_start is None:
                current_bucket_start = bucket_start

            if bucket_start != current_bucket_start:
                if bucket_bars:
                    grouped.append(cls._combine_bars(bucket_bars, current_bucket_start))
                    bucket_bars = []
                current_bucket_start = bucket_start

            bucket_bars.append(bar)

        if bucket_bars and current_bucket_start is not None:
            grouped.append(cls._combine_bars(bucket_bars, current_bucket_start))

        return grouped

    @staticmethod
    def _combine_bars(bars: list[PriceBar], timestamp: datetime) -> PriceBar:
        symbol = bars[0].symbol
        open_price = bars[0].open
        high_price = max(b.high for b in bars)
        low_price = min(b.low for b in bars)
        close_price = bars[-1].close
        total_vol = sum(b.volume for b in bars)

        return PriceBar(
            symbol=symbol,
            timestamp=timestamp,
            open=open_price,
            high=high_price,
            low=low_price,
            close=close_price,
            volume=total_vol,
        )
