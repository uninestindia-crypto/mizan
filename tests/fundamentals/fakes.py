"""A stand-in for NSE's filings client: canned listings and canned files, counting every request. Never the network."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field

from quant_system.shariah.filings.models import ResultRow
from quant_system.shariah.filings.nse_client import FilingsNotFound


@dataclass
class FakeNse:
    """`rows` is what NSE lists per symbol; `files` maps a filing link to its bytes. A link with no file is "gone"."""

    rows: dict[str, list[ResultRow]]
    files: dict[str, bytes] = field(default_factory=dict)
    fail_with: Exception | None = None
    on_fetch: Callable[[str], None] | None = None
    listed: list[str] = field(default_factory=list)
    fetched: list[str] = field(default_factory=list)

    def list_results(self, symbol: str) -> list[ResultRow]:
        self.listed.append(symbol)
        if self.fail_with is not None:
            raise self.fail_with
        return list(self.rows.get(symbol, []))

    def fetch_xbrl(self, url: str) -> bytes:
        self.fetched.append(url)
        if self.on_fetch is not None:
            self.on_fetch(url)
        if url not in self.files:
            raise FilingsNotFound(detail="answer 404")
        return self.files[url]
