"""List, fetch and read one company's filing in a single call."""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime

from quant_system.shariah.filings.extract import extract_figures
from quant_system.shariah.filings.models import FilingFigures, IndustryGroup, ResultRow
from quant_system.shariah.filings.nse_client import NseFilingsClient
from quant_system.shariah.filings.selection import Selection, select_filing


def _utc_now() -> datetime:
    return datetime.now(UTC)


def read_company_filing(
    client: NseFilingsClient, symbol: str, now: Callable[[], datetime] = _utc_now
) -> Selection:
    """Ask NSE what the company filed, read the newest balance sheet, and keep the proof of it."""
    rows = client.list_results(symbol)

    def fetch(row: ResultRow) -> FilingFigures:
        data = client.fetch_xbrl(row.xbrl_url)
        stamp = now().astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
        return extract_figures(data, row, stamp)

    return select_filing(rows, fetch)


class LiveSource:
    """What the snapshot builder and the in-app fetch talk to: NSE, one polite request at a time."""

    def __init__(self, client: NseFilingsClient | None = None) -> None:
        self._client = client or NseFilingsClient()

    def read_company(self, symbol: str) -> Selection:
        return read_company_filing(self._client, symbol)

    def fetch_industry_groups(self) -> dict[str, IndustryGroup]:
        return self._client.fetch_industry_groups()
