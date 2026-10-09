"""Reading a company's quarterly filings from NSE through an injected client, one request at a time.

The same code serves the developer's snapshot builder and the in-app fetch, so they cannot disagree. It never
retries and never swallows a refusal from NSE: those reach the caller, which stops and says so in plain words.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Protocol

from quant_system.fundamentals.extract import extract_quarter
from quant_system.fundamentals.models import QuarterFigures
from quant_system.shariah.filings.models import ResultRow
from quant_system.shariah.filings.nse_client import FilingsNotFound

QUARTERLY = "Quarterly"
Clock = Callable[[], datetime]
Progress = Callable[[int, int], None]
Stop = Callable[[], bool]
Keep = Callable[[QuarterFigures], None]


class ResultsSource(Protocol):
    """What the real NSE filings client offers, and all this module needs of it."""

    def list_results(self, symbol: str) -> list[ResultRow]: ...

    def fetch_xbrl(self, url: str) -> bytes: ...


@dataclass(frozen=True)
class Hooks:
    """What a caller may attach: progress after each filing, a way to stop between filings, and a place to keep each
    filing the moment it is read (so a refusal from NSE half way through loses nothing already read)."""

    progress: Progress | None = None
    stop: Stop | None = None
    keep: Keep | None = None


@dataclass
class CompanyRead:
    quarters: list[QuarterFigures] = field(default_factory=list)
    skipped: int = 0
    planned: int = 0


def _newest(rows: Sequence[ResultRow]) -> ResultRow:
    return max(rows, key=lambda r: (r.period_end, r.filed_on or r.period_end))


def plan_rows(rows: Sequence[ResultRow], count: int) -> list[ResultRow]:
    """The filings to read, newest first: one basis (consolidated when the newest quarter has one), `count` at most.

    A company whose newest filing is not in the ordinary layout (a bank, a lender) plans only that filing, so the
    reason it is not read can be recorded with its proof.
    """
    quarterly = [row for row in rows if row.period_kind == QUARTERLY]
    if not quarterly:
        return [_newest(rows)] if rows else []
    newest = _newest(quarterly)
    if newest.format_kind != "IND_AS":
        return [newest]
    ordinary = [row for row in quarterly if row.format_kind == "IND_AS"]
    latest = max(row.period_end for row in ordinary)
    basis = any(row.consolidated for row in ordinary if row.period_end == latest)
    best: dict[tuple[int, int], ResultRow] = {}
    for row in ordinary:
        key = (row.period_end.year, row.period_end.month)
        if row.consolidated == basis and (key not in best or _newest([best[key], row]) is row):
            best[key] = row
    return sorted(best.values(), key=lambda r: r.period_end, reverse=True)[:count]


def _stamp(now: Clock) -> str:
    return now().astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def read_row(source: ResultsSource, row: ResultRow, now: Clock) -> QuarterFigures:
    """Fetch and read one filing. Raises FilingsNotFound, FilingsBlocked or FilingsUnavailable from the client."""
    data = source.fetch_xbrl(row.xbrl_url)
    return extract_quarter(data, row, _stamp(now))


def read_company(
    source: ResultsSource, symbol: str, count: int, now: Clock, hooks: Hooks = Hooks()
) -> CompanyRead:
    """List what NSE has for the company, then read the planned filings one at a time."""
    planned = plan_rows(source.list_results(symbol), count)
    result = CompanyRead(planned=len(planned))
    for done, row in enumerate(planned, start=1):
        if hooks.stop is not None and hooks.stop():
            break
        try:
            item = read_row(source, row, now)
        except FilingsNotFound:
            result.skipped += 1
        else:
            result.quarters.append(item)
            if hooks.keep is not None:
                hooks.keep(item)
        if hooks.progress is not None:
            hooks.progress(done, len(planned))
    return result
