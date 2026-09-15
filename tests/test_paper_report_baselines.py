"""The daily report has to say what the book returned *against the alternatives*.

A book that prints only its own P&L can lose to holding the index for weeks and read as fine.
That is not hypothetical here: measured on `trial_mizan_h11_003` the flagship's Sharpe was +0.167
against BUY_AND_HOLD +1.404 and PREVIOUS_SIGN +1.631, while its own deflated Sharpe climbed across
three trials -- the whole board rose and the model rose least. Nothing in the daily report showed
that, so it stayed invisible between governed trials.

These test the properties that make the comparison trustworthy rather than merely present: that a
missing input reports `unavailable` instead of a fabricated zero, that the index leg tolerates the
holidays a session window lands on, and that the selection line is the subtraction it claims to be.
"""

from __future__ import annotations

import importlib.util
import os
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from pathlib import Path
from typing import Any
from unittest import mock


def _runner() -> Any:
    spec = importlib.util.spec_from_file_location(
        "_rps_baselines",
        Path(__file__).resolve().parent.parent / "scripts/run_paper_pilot_session.py",
    )
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    # The runner loads `.env` into `os.environ` at import time; keep that out of the rest of the
    # suite, exactly as `test_paper_pilot_carried_session.py` does.
    with mock.patch.dict(os.environ, os.environ.copy(), clear=True):
        spec.loader.exec_module(module)
    return module


@dataclass(frozen=True)
class _Position:
    quantity: int
    average_price: Decimal


def _row(rows: list[dict[str, str]], name: str) -> dict[str, str]:
    for row in rows:
        if row["baseline"] == name:
            return row
    raise AssertionError(f"no baseline row named {name!r} in {[r['baseline'] for r in rows]}")


NIFTY = {"2026-08-31": 24000.0, "2026-09-11": 24720.0}


def test_the_book_line_is_measured_against_initial_capital() -> None:
    rows = _runner().session_baselines(
        initial_capital=Decimal("1000000.00"),
        final_equity=Decimal("986270.18"),
        positions={"AADHARHFC": _Position(20, Decimal("467.05"))},
        marks={"AADHARHFC": Decimal("456.65")},
        nifty_by_date=NIFTY,
        window_start=date(2026, 8, 31),
        window_end=date(2026, 9, 11),
    )
    assert _row(rows, "This book")["return_pct"] == "-1.3730"


def test_equal_weight_exposes_a_book_that_overweighted_its_loser() -> None:
    """Same names, equal rupees. The gap to the book is drift the runner does not correct."""
    rows = _runner().session_baselines(
        initial_capital=Decimal("100000.00"),
        # 900 in the loser (-50%) and 100 in the winner (+50%) -> 500 + 150 = 650, from 1000.
        final_equity=Decimal("99650.00"),
        positions={
            "LOSER": _Position(900, Decimal("1.00")),
            "WINNER": _Position(100, Decimal("1.00")),
        },
        marks={"LOSER": Decimal("0.50"), "WINNER": Decimal("1.50")},
        nifty_by_date=NIFTY,
        window_start=date(2026, 8, 31),
        window_end=date(2026, 9, 11),
    )
    # Equal rupees across the two legs is flat: -50% and +50% average to zero, so the 1,000
    # invested comes back as 1,000 and the book's 350 loss is entirely its weighting.
    assert _row(rows, "Equal-weight, same names")["return_pct"] == "+0.0000"
    assert _row(rows, "This book")["return_pct"] == "-0.3500"


def test_the_index_leg_falls_back_to_the_last_close_before_a_holiday() -> None:
    """Sessions land on days the cached series has no close for; an exact lookup found nothing."""
    rows = _runner().session_baselines(
        initial_capital=Decimal("1000000.00"),
        final_equity=Decimal("1000000.00"),
        positions={},
        marks={},
        nifty_by_date=NIFTY,
        # Neither date is in the series: 09-01 falls back to 08-31, 09-14 to 09-11.
        window_start=date(2026, 9, 1),
        window_end=date(2026, 9, 14),
    )
    assert _row(rows, "NIFTY 50 buy-and-hold")["return_pct"] == "+3.0000"


def test_a_missing_index_series_reports_unavailable_rather_than_zero() -> None:
    """The property that matters. A fabricated 0.00% would read as 'the market went nowhere'."""
    rows = _runner().session_baselines(
        initial_capital=Decimal("1000000.00"),
        final_equity=Decimal("950000.00"),
        positions={"X": _Position(10, Decimal("100.00"))},
        marks={"X": Decimal("95.00")},
        nifty_by_date={},
        window_start=date(2026, 8, 31),
        window_end=date(2026, 9, 11),
    )
    index = _row(rows, "NIFTY 50 buy-and-hold")
    assert index["return_pct"] == "unavailable"
    assert "no cached NIFTY 50 close" in index["note"]
    # And the line that depends on it refuses too, rather than reporting the book's own return
    # as though the index had returned zero.
    selection = _row(rows, "Selection vs NIFTY 50")
    assert selection["return_pct"] == "unavailable"


def test_the_selection_line_is_the_subtraction_it_claims_to_be() -> None:
    rows = _runner().session_baselines(
        initial_capital=Decimal("1000000.00"),
        final_equity=Decimal("1010000.00"),
        positions={"X": _Position(10, Decimal("100.00"))},
        marks={"X": Decimal("101.00")},
        nifty_by_date=NIFTY,
        window_start=date(2026, 8, 31),
        window_end=date(2026, 9, 11),
    )
    # Book +1.00%, index +3.00% -> the picking cost two points against holding the index.
    assert _row(rows, "This book")["return_pct"] == "+1.0000"
    assert _row(rows, "NIFTY 50 buy-and-hold")["return_pct"] == "+3.0000"
    assert _row(rows, "Selection vs NIFTY 50")["return_pct"] == "-2.0000"


def test_an_unmarked_holding_is_named_and_excluded_never_silently_zeroed() -> None:
    """Same rule the XS book applies to an unpriced entitlement, for the same reason."""
    rows = _runner().session_baselines(
        initial_capital=Decimal("100000.00"),
        final_equity=Decimal("100000.00"),
        positions={
            "PRICED": _Position(100, Decimal("10.00")),
            "UNPRICED": _Position(100, Decimal("10.00")),
        },
        marks={"PRICED": Decimal("11.00")},
        nifty_by_date=NIFTY,
        window_start=date(2026, 8, 31),
        window_end=date(2026, 9, 11),
    )
    equal_weight = _row(rows, "Equal-weight, same names")
    assert "UNPRICED" in equal_weight["note"]
    assert "1 unmarked and excluded" in equal_weight["note"]
    # One priced leg at +10%, on 2,000 invested of 100,000 -> +0.20% overall, not +0.10%.
    # Averaging the unpriced leg in at zero would have halved it.
    assert equal_weight["return_pct"] == "+0.2000"


def test_an_empty_book_has_no_window_and_says_so() -> None:
    rows = _runner().session_baselines(
        initial_capital=Decimal("1000000.00"),
        final_equity=Decimal("1000000.00"),
        positions={},
        marks={},
        nifty_by_date=NIFTY,
        window_start=None,
        window_end=date(2026, 9, 11),
    )
    assert _row(rows, "NIFTY 50 buy-and-hold")["return_pct"] == "unavailable"
    assert "no holding window" in _row(rows, "NIFTY 50 buy-and-hold")["note"]
    assert _row(rows, "Equal-weight, same names")["return_pct"] == "unavailable"


def test_non_positive_capital_refuses_rather_than_dividing_by_it() -> None:
    rows = _runner().session_baselines(
        initial_capital=Decimal("0.00"),
        final_equity=Decimal("0.00"),
        positions={},
        marks={},
        nifty_by_date=NIFTY,
        window_start=date(2026, 8, 31),
        window_end=date(2026, 9, 11),
    )
    assert rows == [
        {
            "baseline": "This book",
            "answers": "actual",
            "return_pct": "unavailable",
            "note": "initial capital is not positive; every return is undefined against it",
        }
    ]


def test_cash_is_always_present_as_the_floor() -> None:
    """A book below zero paid statutory costs to lose money; that has to be visible."""
    rows = _runner().session_baselines(
        initial_capital=Decimal("1000000.00"),
        final_equity=Decimal("986270.18"),
        positions={"X": _Position(10, Decimal("100.00"))},
        marks={"X": Decimal("95.00")},
        nifty_by_date=NIFTY,
        window_start=date(2026, 8, 31),
        window_end=date(2026, 9, 11),
    )
    assert _row(rows, "Cash")["return_pct"] == "+0.0000"
