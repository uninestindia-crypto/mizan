"""Choosing one basis per company, de-duplicating, marking gaps, and never mixing consolidated with standalone."""

from __future__ import annotations

from dataclasses import replace
from datetime import date, timedelta

from quant_system.fundamentals.models import QuarterFigures, ReadStatus
from quant_system.fundamentals.series import build_series
from tests.fundamentals.support import quarter, quarter_ends

D24_12, D24_09, D24_06, D24_03 = (
    date(2024, 12, 31),
    date(2024, 9, 30),
    date(2024, 6, 30),
    date(2024, 3, 31),
)
D23_12, D23_09, D23_06, D23_03 = (
    date(2023, 12, 31),
    date(2023, 9, 30),
    date(2023, 6, 30),
    date(2023, 3, 31),
)


def _q(end: date, consolidated: bool = True, profit: int = 100) -> QuarterFigures:
    return quarter(end, revenue=1000, profit=profit, consolidated=consolidated)


def _failed(item: QuarterFigures) -> QuarterFigures:
    return replace(
        item, status=ReadStatus.TIE_OUT_FAILED, note="The filing does not agree with itself."
    )


def test_the_series_runs_oldest_to_newest_and_ends_at_the_latest_quarter() -> None:
    series = build_series([_q(D24_09), _q(D24_12), _q(D24_06)])
    assert [slot.period_end for slot in series.slots] == [D24_06, D24_09, D24_12]
    assert series.latest is not None and series.latest.period_end == D24_12
    assert series.consolidated is True and series.gaps == ()


def test_consolidated_is_preferred_when_the_latest_quarter_has_one() -> None:
    series = build_series(
        [_q(D24_12, True), _q(D24_12, False), _q(D24_09, True), _q(D24_09, False)]
    )
    assert series.consolidated is True
    assert {slot.quarter.consolidated for slot in series.slots if slot.quarter} == {True}


def test_standalone_is_used_when_there_is_no_consolidated_for_the_latest_quarter() -> None:
    series = build_series([_q(D24_12, False), _q(D24_09, False), _q(D24_09, True)])
    assert series.consolidated is False
    assert [slot.period_end for slot in series.slots] == [D24_09, D24_12]
    assert all(slot.quarter and not slot.quarter.consolidated for slot in series.slots)


def test_the_two_bases_are_never_mixed_even_when_that_would_fill_a_gap() -> None:
    series = build_series([_q(D24_12, True), _q(D24_09, False), _q(D24_06, True)])
    assert series.consolidated is True
    assert series.gaps == (D24_09,)
    assert [slot.quarter is not None for slot in series.slots] == [True, False, True]


def test_a_missing_quarter_inside_the_run_is_a_marked_gap() -> None:
    series = build_series([_q(D24_12), _q(D24_09), _q(D24_03)])
    assert series.gaps == (D24_06,)
    assert len(series.slots) == 4 and series.slots[1].quarter is None


def test_quarters_before_the_first_one_held_are_not_gaps() -> None:
    series = build_series([_q(D24_12), _q(D24_09)])
    assert series.gaps == () and len(series.slots) == 2


def test_a_later_filing_for_the_same_quarter_replaces_the_earlier_one() -> None:
    earlier = _q(D24_09, profit=100)
    later = replace(_q(D24_09, profit=250), filed_on=earlier.filed_on + timedelta(days=30))
    series = build_series([later, earlier])
    assert len(series.slots) == 1 and series.slots[0].quarter == later


def test_a_quarter_that_failed_its_checks_is_listed_apart_and_leaves_a_gap() -> None:
    series = build_series([_q(D24_12), _failed(_q(D24_09)), _q(D24_06)])
    assert series.gaps == (D24_09,)
    assert [item.period_end for item in series.excluded] == [D24_09]
    assert series.excluded[0].note.startswith("The filing does not agree")


def test_the_run_is_cut_to_the_last_sixteen_quarters() -> None:
    ends = quarter_ends(20)
    series = build_series([_q(end) for end in ends])
    assert len(series.slots) == 16
    assert series.slots[-1].period_end == ends[-1] and series.slots[0].period_end == ends[4]


def test_a_company_with_nothing_usable_has_an_empty_series_and_says_why() -> None:
    bank = replace(
        _q(D24_09), status=ReadStatus.FORMAT_NOT_READ, note="This company is a bank.", lines={}
    )
    series = build_series([bank])
    assert series.slots == () and series.latest is None
    assert series.unread is not None and series.unread.note == "This company is a bank."


def test_an_empty_list_gives_an_empty_series() -> None:
    series = build_series([])
    assert series.slots == () and series.unread is None and series.consolidated is None


def test_standalone_is_shown_with_a_note_when_the_newest_consolidated_filing_failed() -> None:
    series = build_series([_failed(_q(D24_12, True)), _q(D24_12, False), _q(D24_09, False)])
    assert series.consolidated is False
    assert any("consolidated" in note.lower() for note in series.notes)


def test_offsets_count_back_from_the_latest_quarter() -> None:
    series = build_series([_q(D24_12), _q(D24_09), _q(D24_06), _q(D24_03), _q(D23_12)])
    assert series.at(0) is not None and series.at(0).period_end == D24_12  # type: ignore[union-attr]
    assert series.at(4) is not None and series.at(4).period_end == D23_12  # type: ignore[union-attr]
    assert series.at(5) is None
    assert series.run(0, 4) is not None and len(series.run(0, 4) or []) == 4
    assert series.run(2, 4) is None
