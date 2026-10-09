"""How much a filing's figures may be trusted when shown to a person."""

from __future__ import annotations

import calendar
from datetime import date
from enum import StrEnum

from quant_system.shariah.filings.models import FilingFigures, ReadStatus

STALE_AFTER_MONTHS = 18


class DataStatus(StrEnum):
    VERIFIED_FILING = "VERIFIED_FILING"
    STALE = "STALE"
    NOT_SCREENED = "NOT_SCREENED"


def _months_before(today: date, months: int) -> date:
    year, month = divmod(today.year * 12 + today.month - 1 - months, 12)
    day = min(today.day, calendar.monthrange(year, month + 1)[1])
    return date(year, month + 1, day)


def data_status_for(figures: FilingFigures | None, today: date) -> DataStatus:
    """VERIFIED_FILING only for a filing that read cleanly, ties out and carries its proof.

    STALE when that filing's balance sheet is more than 18 months old. Anything unreadable, partial or
    failing its own checks is NOT_SCREENED. (UNVERIFIED_SAMPLE belongs to the hand-entered rows, not here.)
    """
    if figures is None or figures.read_status is not ReadStatus.READ_OK:
        return DataStatus.NOT_SCREENED
    proof = figures.proof
    if not proof.sha256 or not proof.source_url:
        return DataStatus.NOT_SCREENED
    if not figures.tie_out or not all(check.ok for check in figures.tie_out):
        return DataStatus.NOT_SCREENED
    if proof.period_end < _months_before(today, STALE_AFTER_MONTHS):
        return DataStatus.STALE
    return DataStatus.VERIFIED_FILING
