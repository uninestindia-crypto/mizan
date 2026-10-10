"""All the metrics for one company, from its series and the platform's last close. Pure: no clock, files or network."""

from __future__ import annotations

from quant_system.fundamentals.metric_types import Metrics, PriceQuote
from quant_system.fundamentals.metrics_balance import balance_metrics
from quant_system.fundamentals.metrics_earnings import earnings_metrics
from quant_system.fundamentals.series import Series

__all__ = ["compute_metrics"]


def compute_metrics(series: Series, price: PriceQuote | None) -> Metrics:
    """Every metric, available or not. One that cannot be worked out has no value and a plain reason."""
    earnings = earnings_metrics(series)
    return {**earnings, **balance_metrics(series, price, earnings)}
