"""Choosing which filing to read: the newest balance sheet NSE lists, consolidated before standalone."""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass

from quant_system.shariah.filings.models import FilingFigures, ReadStatus, ResultRow
from quant_system.shariah.filings.nse_client import FilingsNotFound

MAX_CANDIDATES = 3
NOTHING_LISTED = "NSE lists no results filing for this company that QuantOS can read."
NO_SHEET = "None of the newest filings NSE lists for this company carries a balance sheet."


@dataclass(frozen=True)
class Selection:
    """What was found for a company. `figures` is None when nothing could even be fetched."""

    figures: FilingFigures | None
    read_status: ReadStatus
    note: str
    tried: int


def rank_candidates(rows: Sequence[ResultRow]) -> list[ResultRow]:
    """Ind AS corporate filings, in the order to try them.

    Periods that normally carry a balance sheet (half year and year end) come first, newest first, then the
    rest as a fallback. For one period the consolidated filing comes before the standalone one, and a later
    re-filing comes before an earlier one. This only orders the tries: the filing's own contents decide
    whether it has a balance sheet.
    """
    eligible = [row for row in rows if row.format_kind == "IND_AS"]
    return sorted(
        eligible,
        key=lambda r: (
            not r.carries_balance_sheet_hint,
            -r.period_end.toordinal(),
            not r.consolidated,
            -(r.filed_on.toordinal() if r.filed_on else 0),
        ),
    )


def _newest(rows: Sequence[ResultRow]) -> ResultRow:
    return max(rows, key=lambda r: (r.period_end, r.filed_on or r.period_end))


def _look_at_other_format(
    rows: Sequence[ResultRow], fetch: Callable[[ResultRow], FilingFigures]
) -> Selection:
    """A bank, lender or older-format company: read its newest filing once so the proof can say what was seen.

    A company is judged by its newest filing, so a lender that once filed in the ordinary layout is not read
    from an old filing.
    """
    if not rows:
        return Selection(None, ReadStatus.NO_BALANCE_SHEET, NOTHING_LISTED, 0)
    try:
        figures = fetch(_newest(rows))
    except FilingsNotFound:
        return Selection(None, ReadStatus.FORMAT_NOT_READ, NOTHING_LISTED, 1)
    return Selection(figures, figures.read_status, figures.read_note, 1)


def select_filing(
    rows: Sequence[ResultRow],
    fetch: Callable[[ResultRow], FilingFigures],
    max_candidates: int = MAX_CANDIDATES,
) -> Selection:
    """Read the newest filing that carries a balance sheet, walking back at most `max_candidates` filings.

    Errors from `fetch` other than "NSE no longer has this filing" (a block, no answer) are not swallowed.
    """
    candidates = rank_candidates(rows)
    if not candidates or _newest(rows).format_kind != "IND_AS":
        return _look_at_other_format(rows, fetch)
    tried = 0
    first_blank: FilingFigures | None = None
    blank_periods = set()
    for candidate in candidates:
        if tried >= max_candidates:
            break
        if candidate.period_end in blank_periods:
            continue
        tried += 1
        try:
            figures = fetch(candidate)
        except FilingsNotFound:
            continue
        if figures.read_status is ReadStatus.NO_BALANCE_SHEET:
            first_blank = first_blank or figures
            blank_periods.add(candidate.period_end)
            continue
        return Selection(figures, figures.read_status, figures.read_note, tried)
    return Selection(first_blank, ReadStatus.NO_BALANCE_SHEET, NO_SHEET, tried)
