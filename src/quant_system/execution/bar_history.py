"""Supply point-in-time bar history to execution surfaces.

A governed model is fitted on ``PointInTimeBar`` history under strict availability discipline, but
``MarketContext.historical_bars`` carries ``PriceBar``, which has no ``available_at``. A model
scored on bars whose availability cannot be established has no defensible claim to being
point-in-time at the moment that matters — the decision. So execution surfaces carry
``PointInTimeBar`` through a typed ``extra_data`` key instead. See
``agent_context/decisions/20260822-point-in-time-bars-at-execution.md``.

This module provides that history. The engine takes a :class:`BarHistoryProvider` rather than an
``EvidenceStore``, so the runner never learns about evidence storage and the wiring stays testable
without one.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from datetime import datetime
from typing import Protocol

from quant_system.data.market_data import HistoricalAcquisition, PointInTimeBar

__all__ = ["AcquisitionBarHistory", "BarHistoryProvider"]


class BarHistoryProvider(Protocol):
    """Return the bars for one symbol that were available by ``decision_time``."""

    def __call__(self, symbol: str, decision_time: datetime) -> Sequence[PointInTimeBar]: ...


class AcquisitionBarHistory:
    """Serve point-in-time bars from governed acquisitions, keyed by symbol.

    The acquisitions are the same evidence that produced the training data, so a model scores live
    on history of the same provenance it was fitted on rather than on a quote-feed reconstruction.

    Filtering happens here because the decision record specifies history "filtered to
    ``available_at <= decision_time``" at the boundary. ``GovernedModelStrategy`` filters again on
    receipt: a provider is an injection point, and a third-party provider must not be able to leak
    a not-yet-available bar into a scored feature row.
    """

    def __init__(self, acquisitions: Iterable[HistoricalAcquisition]) -> None:
        by_symbol: dict[str, list[PointInTimeBar]] = {}
        for acquisition in acquisitions:
            for record in acquisition.records:
                by_symbol.setdefault(record.symbol, []).append(record)
        self._bars: Mapping[str, tuple[PointInTimeBar, ...]] = {
            symbol: tuple(sorted(records, key=lambda bar: bar.exchange_date))
            for symbol, records in by_symbol.items()
        }

    @property
    def symbols(self) -> tuple[str, ...]:
        return tuple(sorted(self._bars))

    def __call__(self, symbol: str, decision_time: datetime) -> Sequence[PointInTimeBar]:
        return tuple(bar for bar in self._bars.get(symbol, ()) if bar.available_at <= decision_time)
