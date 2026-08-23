"""Tests for the governed promotion runner's refusal rules.

These cover the pure configuration guards only. The acquisition stages need a real provider and
are deliberately not faked here — this runner has no synthetic path, and adding one in a test
would be the first step towards giving it one.
"""

from __future__ import annotations

import argparse
import sys
from datetime import UTC, date, datetime
from pathlib import Path

import pytest

_SCRIPTS = str(Path(__file__).resolve().parent.parent / "scripts")
if _SCRIPTS not in sys.path:
    sys.path.insert(0, _SCRIPTS)

import run_governed_promotion as r  # noqa: E402
import run_governed_ridge_training as t  # noqa: E402


def _args(**overrides: object) -> argparse.Namespace:
    base = argparse.Namespace(
        train_to_date=date(2025, 9, 30),
        holdout_from_date=date(2025, 10, 15),
        to_date=date(2025, 12, 31),
        min_holdout_gap_days=7,
    )
    for key, value in overrides.items():
        setattr(base, key, value)
    return base


def test_valid_windows_are_accepted() -> None:
    r._refuse_leaky_windows(_args())


def test_training_window_overlapping_the_holdout_is_refused() -> None:
    """The fit must stop before the holdout opens, or the holdout is not a holdout."""
    with pytest.raises(t.ConfigurationRefused, match="overlapping windows leak"):
        r._refuse_leaky_windows(
            _args(train_to_date=date(2025, 10, 20), holdout_from_date=date(2025, 10, 15))
        )


def test_identical_boundaries_are_refused() -> None:
    """Touching windows are still leakage: the last fitted session opens a label into the holdout."""
    with pytest.raises(t.ConfigurationRefused, match="overlapping windows leak"):
        r._refuse_leaky_windows(
            _args(train_to_date=date(2025, 10, 15), holdout_from_date=date(2025, 10, 15))
        )


def test_insufficient_maturation_gap_is_refused() -> None:
    """A label opened on the last training session must mature before the holdout opens."""
    with pytest.raises(t.ConfigurationRefused, match="calendar days separate"):
        r._refuse_leaky_windows(
            _args(train_to_date=date(2025, 10, 1), holdout_from_date=date(2025, 10, 3))
        )


def test_holdout_after_the_data_window_is_refused() -> None:
    with pytest.raises(t.ConfigurationRefused, match="falls after --to-date"):
        r._refuse_leaky_windows(
            _args(holdout_from_date=date(2026, 6, 1), to_date=date(2025, 12, 31))
        )


class _Session:
    def __init__(self, exchange_date: date) -> None:
        self.exchange_date = exchange_date
        self.close_at = datetime(
            exchange_date.year, exchange_date.month, exchange_date.day, 10, 0, tzinfo=UTC
        )


class _Calendar:
    def __init__(self, dates: list[date]) -> None:
        self.sessions = [_Session(d) for d in dates]


def test_holdout_opens_on_the_first_session_on_or_after_the_requested_date() -> None:
    calendar = _Calendar([date(2025, 10, 10), date(2025, 10, 17), date(2025, 10, 24)])
    close = r._session_close_on_or_after(calendar, date(2025, 10, 15))  # type: ignore[arg-type]
    assert close.date() == date(2025, 10, 17)


def test_no_session_on_or_after_the_holdout_date_is_refused() -> None:
    calendar = _Calendar([date(2025, 10, 10)])
    with pytest.raises(t.ConfigurationRefused, match="no exchange session"):
        r._session_close_on_or_after(calendar, date(2025, 12, 1))  # type: ignore[arg-type]
