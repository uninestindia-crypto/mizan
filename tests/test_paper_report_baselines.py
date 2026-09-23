"""The daily report has to say what the book returned *against the market*, like with like.

A book that prints only its own P&L can lose to holding the index for weeks and read as fine.
That is not hypothetical here: measured on `trial_mizan_h11_003` the flagship's Sharpe was +0.167
against BUY_AND_HOLD +1.404 and PREVIOUS_SIGN +1.631, while its own deflated Sharpe climbed across
three trials -- the whole board rose and the model rose least. Nothing in the daily report showed
that, so it stayed invisible between governed trials.

A comparison that is present but unlike is its own failure. On 2026-09-21 the first version of this
table set the book's 21 Sep mark against NIFTY 50's 18 Sep close, against a fully invested index
while the book held 15% cash, and printed +1.87 pp as selection; against its own universe over the
same dates the picks were about +0.6 pp. It also set an equal-weight figure for the names held
that day against the book's lifetime return, so sizing appeared to cost 0.9 pp.

These test the properties that make the comparison trustworthy: a missing input reports
`unavailable` instead of a fabricated zero; the book and the index are read on the same dates; the
market leg is scaled to the book's exposure; the picking line is the subtraction it claims to be;
and the sizing rows compare the same names over the same span.
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

from quant_system.execution.paper_portfolio import EquityMark


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


def _marks(*closes: tuple[str, str, str]) -> dict[date, EquityMark]:
    """(date, equity, invested) triples as the portfolio records them at each close."""
    return {
        date.fromisoformat(on): EquityMark(
            on=date.fromisoformat(on), equity=Decimal(equity), invested=Decimal(invested)
        )
        for on, equity, invested in closes
    }


#: Friday 28 Aug is the last close before a book that starts on Monday 31 Aug. 11 Sep is +3.00%.
NIFTY = {
    "2026-08-28": 24000.0,
    "2026-08-31": 24240.0,
    "2026-09-10": 24480.0,
    "2026-09-11": 24720.0,
}
FIRST = date(2026, 8, 31)
MARKET_ROWS = (
    "NIFTY 50 buy-and-hold",
    "This book, same dates",
    "Market at this book's exposure",
    "Picking and costs",
)


def _baselines(**overrides: Any) -> list[dict[str, str]]:
    arguments: dict[str, Any] = {
        "initial_capital": Decimal("1000000.00"),
        "final_equity": Decimal("1000000.00"),
        "session_date": date(2026, 9, 11),
        "positions": {},
        "marks": {},
        "index_name": "NIFTY 50",
        "index_by_date": NIFTY,
        "inception_on": FIRST,
        "equity_marks": _marks(("2026-09-11", "1000000.00", "1000000.00")),
    }
    arguments.update(overrides)
    rows: list[dict[str, str]] = _runner().session_baselines(**arguments)
    return rows


def test_the_book_line_is_measured_against_initial_capital() -> None:
    rows = _baselines(final_equity=Decimal("986270.18"))
    assert _row(rows, "This book")["return_pct"] == "-1.3730"


def test_the_book_and_the_index_are_read_on_the_same_dates() -> None:
    """The index ends a session behind the book, so the book is read at the index's last close.

    Today the book is -5%, but on 11 Sep, the index's latest close, it was +1%. Setting today's -5%
    against the index's +3% would print a gap that belongs to no single window.
    """
    rows = _baselines(
        final_equity=Decimal("950000.00"),
        session_date=date(2026, 9, 14),
        equity_marks=_marks(
            ("2026-09-11", "1010000.00", "1010000.00"),
            ("2026-09-14", "950000.00", "950000.00"),
        ),
    )

    assert _row(rows, "This book")["return_pct"] == "-5.0000"
    assert _row(rows, "NIFTY 50 buy-and-hold")["return_pct"] == "+3.0000"
    same_dates = _row(rows, "This book, same dates")
    assert same_dates["return_pct"] == "+1.0000"
    assert "2026-09-11 close" in same_dates["note"]
    assert "the book is also marked 2026-09-14" in same_dates["note"]
    # Fully invested, so the market leg is the index itself: +1 - 3 = -2.
    assert _row(rows, "Picking and costs")["return_pct"] == "-2.0000"


def test_the_market_is_scaled_to_the_books_exposure() -> None:
    """A book 80% in stocks cannot fall as far as a fully invested index; that gap is not skill."""
    rows = _baselines(
        equity_marks=_marks(
            ("2026-08-31", "1000000.00", "800000.00"),
            ("2026-09-11", "1000000.00", "800000.00"),
        ),
    )

    assert _row(rows, "NIFTY 50 buy-and-hold")["return_pct"] == "+3.0000"
    market = _row(rows, "Market at this book's exposure")
    assert market["return_pct"] == "+2.4000"
    assert "80.0% average invested" in market["note"]
    assert _row(rows, "Picking and costs")["return_pct"] == "-2.4000"


def test_the_picking_line_is_the_subtraction_it_claims_to_be() -> None:
    rows = _baselines(
        final_equity=Decimal("1010000.00"),
        equity_marks=_marks(("2026-09-11", "1010000.00", "505000.00")),
    )
    # Book +1.00%; index +3.00% at 50% invested is +1.50%; picking and costs -0.50 points.
    assert _row(rows, "This book, same dates")["return_pct"] == "+1.0000"
    assert _row(rows, "Market at this book's exposure")["return_pct"] == "+1.5000"
    assert _row(rows, "Picking and costs")["return_pct"] == "-0.5000"


def test_against_nifty_50_the_picking_line_says_the_universes_differ() -> None:
    """Part of any gap to NIFTY 50 is large companies against the NIFTY 500 the book picks from."""
    note = _row(_baselines(), "Picking and costs")["note"]
    assert "not the NIFTY 500 this book picks from" in note
    assert "weights its names equally" in note


def test_against_its_own_universe_only_the_weighting_caveat_remains() -> None:
    """The NIFTY 500 index weights by size and the book equally; that tilt is not picking."""
    rows = _baselines(index_name="NIFTY 500")

    assert _row(rows, "NIFTY 500 buy-and-hold")["return_pct"] == "+3.0000"
    note = _row(rows, "Picking and costs")["note"]
    assert "not the NIFTY 500" not in note
    assert "weights its names equally" in note
    assert "NIFTY 50 buy-and-hold" not in [row["baseline"] for row in rows]


def test_the_index_starts_from_its_last_close_before_the_first_session() -> None:
    """The book starts from its capital before its first trade, so the index starts there too.

    A book whose first session is Tuesday 1 Sep is measured against the index from Monday's close.
    """
    rows = _baselines(inception_on=date(2026, 9, 1))
    # 24720 / 24240 - 1, from Monday 31 Aug's close.
    assert _row(rows, "NIFTY 50 buy-and-hold")["return_pct"] == "+1.9802"
    assert "the close before 2026-09-01" in _row(rows, "NIFTY 50 buy-and-hold")["note"]


def test_the_index_base_skips_back_over_a_weekend() -> None:
    """Monday's book starts from Friday's close; an exact lookup of Sunday found nothing."""
    rows = _baselines(inception_on=FIRST)
    assert _row(rows, "NIFTY 50 buy-and-hold")["return_pct"] == "+3.0000"


def test_a_missing_index_series_reports_unavailable_rather_than_zero() -> None:
    """The property that matters. A fabricated 0.00% would read as 'the market went nowhere'."""
    rows = _baselines(final_equity=Decimal("950000.00"), index_by_date={})
    for name in MARKET_ROWS:
        row = _row(rows, name)
        assert row["return_pct"] == "unavailable", name
        assert "no cached NIFTY 50 closes" in row["note"]


def test_on_its_first_day_the_book_has_no_index_close_to_compare_yet() -> None:
    """The index is refreshed before the open, so on day one it ends the day before the book."""
    rows = _baselines(
        session_date=date(2026, 9, 11),
        inception_on=date(2026, 9, 11),
        index_by_date={key: value for key, value in NIFTY.items() if key < "2026-09-11"},
    )
    for name in MARKET_ROWS:
        assert _row(rows, name)["return_pct"] == "unavailable", name
    assert "no close yet on or after the book's first session" in _row(rows, MARKET_ROWS[0])["note"]


def test_no_index_close_before_the_first_session_is_unavailable() -> None:
    rows = _baselines(inception_on=FIRST, index_by_date={"2026-09-11": 24720.0})
    assert _row(rows, "NIFTY 50 buy-and-hold")["return_pct"] == "unavailable"
    assert "before the book's first session" in _row(rows, "NIFTY 50 buy-and-hold")["note"]


def test_a_book_older_than_its_history_is_compared_from_its_first_recorded_close() -> None:
    """Never from its capital: such a book had long since left it before the first mark."""
    rows = _baselines(
        final_equity=Decimal("999900.00"),
        inception_on=None,
        equity_marks=_marks(
            ("2026-09-10", "990000.00", "990000.00"),
            ("2026-09-11", "999900.00", "999900.00"),
        ),
    )
    # Book 990,000 -> 999,900 is +1.00%; the index 24480 -> 24720 is +0.9804%.
    same_dates = _row(rows, "This book, same dates")
    assert same_dates["return_pct"] == "+1.0000"
    assert "Rs 990000.00 to Rs 999900.00" in same_dates["note"]
    assert _row(rows, "NIFTY 50 buy-and-hold")["return_pct"] == "+0.9804"
    assert _row(rows, "Picking and costs")["return_pct"] == "+0.0196"


def test_a_book_older_than_its_history_with_one_close_is_unavailable() -> None:
    rows = _baselines(inception_on=None)
    assert _row(rows, "Picking and costs")["return_pct"] == "unavailable"
    assert "predates its equity history" in _row(rows, "Picking and costs")["note"]


def test_equal_weight_exposes_a_book_that_overweighted_its_loser() -> None:
    """Same names, same span, equal rupees. The gap between the two rows is the sizing alone."""
    rows = _baselines(
        positions={
            "LOSER": _Position(900, Decimal("1.00")),
            "WINNER": _Position(100, Decimal("1.00")),
        },
        marks={"LOSER": Decimal("0.50"), "WINNER": Decimal("1.50")},
    )
    # 900 at -50% and 100 at +50% is 600 back from 1,000: -40% as sized. Equal rupees average the
    # two legs to zero.
    assert _row(rows, "Held names, as sized")["return_pct"] == "-40.0000"
    assert _row(rows, "Held names, equal-weight")["return_pct"] == "+0.0000"


def test_the_sizing_rows_ignore_the_books_realized_history() -> None:
    """They cover the names held now; a realized loss elsewhere in the book is not sizing."""
    rows = _baselines(
        final_equity=Decimal("900000.00"),
        positions={"X": _Position(100, Decimal("10.00"))},
        marks={"X": Decimal("11.00")},
    )
    assert _row(rows, "This book")["return_pct"] == "-10.0000"
    assert _row(rows, "Held names, as sized")["return_pct"] == "+10.0000"
    assert _row(rows, "Held names, equal-weight")["return_pct"] == "+10.0000"


def test_an_unmarked_holding_is_named_and_excluded_never_silently_zeroed() -> None:
    """Same rule the XS book applies to an unpriced entitlement, for the same reason."""
    rows = _baselines(
        positions={
            "PRICED": _Position(100, Decimal("10.00")),
            "UNPRICED": _Position(100, Decimal("10.00")),
        },
        marks={"PRICED": Decimal("11.00")},
    )
    equal_weight = _row(rows, "Held names, equal-weight")
    assert "UNPRICED" in equal_weight["note"]
    assert "1 unmarked and excluded" in equal_weight["note"]
    # The one priced leg is +10%. Averaging the unpriced leg in at zero would have halved it, and
    # valuing it at cost would have diluted the sized figure the same way.
    assert equal_weight["return_pct"] == "+10.0000"
    assert _row(rows, "Held names, as sized")["return_pct"] == "+10.0000"


def test_an_empty_book_has_no_held_names_and_says_so() -> None:
    rows = _baselines(positions={}, marks={})
    for name in ("Held names, as sized", "Held names, equal-weight"):
        assert _row(rows, name)["return_pct"] == "unavailable"
        assert "no held name" in _row(rows, name)["note"]


def test_non_positive_capital_refuses_rather_than_dividing_by_it() -> None:
    rows = _baselines(initial_capital=Decimal("0.00"), final_equity=Decimal("0.00"))
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
    rows = _baselines(final_equity=Decimal("986270.18"), index_by_date={})
    assert _row(rows, "Cash")["return_pct"] == "+0.0000"
