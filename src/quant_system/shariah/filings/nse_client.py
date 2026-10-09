"""A polite, narrow client for NSE's public results filings.

It only talks to two NSE hosts over HTTPS, never follows a redirect to another host, never retries, reads at most
8 MB per answer, and waits between requests. Only filings that NSE's own list handed out can be fetched.
Every failure has a plain-language message that says what to do next.
"""

from __future__ import annotations

import csv
import io
import json
import re
import time
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import date
from typing import Any, Final, Protocol
from urllib.parse import quote, urljoin, urlsplit

import httpx

from quant_system.shariah.filings.models import (
    SYMBOL_PATTERN,
    IndustryGroup,
    ResultRow,
    clean_text,
    normalize_symbol,
)

MAX_RESPONSE_BYTES: Final = 8 * 1024 * 1024
MIN_PAUSE_SECONDS: Final = 1.2
DEFAULT_PAUSE_SECONDS: Final = 1.5
REQUEST_TIMEOUT_SECONDS: Final = 30.0
MAX_REDIRECTS: Final = 3
ALLOWED_HOSTS: Final = frozenset({"www.nseindia.com", "nsearchives.nseindia.com"})
LIST_URL: Final = "https://www.nseindia.com/api/corporates-financial-results"
INDUSTRY_URL: Final = (
    "https://nsearchives.nseindia.com/content/indices/ind_niftytotalmarket_list.csv"
)
PERIODS: Final = ("Quarterly", "Half-Yearly")
HEADERS: Final = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "en-US,en;q=0.9",
    "Referer": "https://www.nseindia.com/",
}
_URL_SHAPE: Final = re.compile(r"https://[a-z0-9.-]+(?:/[A-Za-z0-9._~%/?=&+-]*)?")
_ISIN: Final = re.compile(r"[A-Z0-9]{12}")
_MONTHS: Final = {m: i for i, m in enumerate(
    ("jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"), 1
)}  # fmt: skip
_REDIRECTS: Final = frozenset({301, 302, 303, 307, 308})
_BLOCKED: Final = frozenset({401, 403, 429})
_UNREADABLE: Final = "NSE sent an answer QuantOS could not read. Try again later."
_TOO_LARGE: Final = "This NSE answer is too large for QuantOS to read, so it was skipped."


class FilingsError(Exception):
    """Base of every error here. `str(error)` is a plain sentence a person can act on."""

    default_message = "Something went wrong reading NSE's filings. Try again later."

    def __init__(self, message: str | None = None, detail: str = "") -> None:
        self.message = message or self.default_message
        #: For developer logs only (a status number, an error name). Never shown to a person.
        self.detail = detail
        super().__init__(self.message)


class InvalidSymbol(FilingsError):
    default_message = "That is not a valid NSE company symbol. Check the spelling and try again."


class FilingsBlocked(FilingsError):
    default_message = (
        "NSE is not letting QuantOS read this company's filings right now. Try again later."
    )


class FilingsUnavailable(FilingsError):
    default_message = "NSE did not answer. Check your internet connection and try again."


class FilingsNotFound(FilingsError):
    default_message = "NSE no longer has this filing. Try again later."


class FilingsRefused(FilingsError):
    default_message = (
        "QuantOS only opens filings that NSE lists on its own website, so this link was not opened."
    )


class TransportError(Exception):
    """The request did not complete (no connection, timeout)."""


class ResponseTooLarge(TransportError):
    """The answer was bigger than the allowed size."""


@dataclass(frozen=True)
class TransportResponse:
    status: int
    headers: Mapping[str, str]
    body: bytes


class Transport(Protocol):
    def get(
        self, url: str, headers: Mapping[str, str], timeout: float, max_bytes: int
    ) -> TransportResponse: ...


class HttpxTransport:
    """The default transport. It never follows redirects and stops reading at `max_bytes`."""

    def __init__(self, transport: httpx.BaseTransport | None = None) -> None:
        self._transport = transport
        self._client: httpx.Client | None = None

    def get(
        self, url: str, headers: Mapping[str, str], timeout: float, max_bytes: int
    ) -> TransportResponse:
        if self._client is None:
            self._client = httpx.Client(transport=self._transport, follow_redirects=False)
        try:
            with self._client.stream(
                "GET", url, headers=dict(headers), timeout=timeout
            ) as response:
                body = bytearray()
                for chunk in response.iter_bytes():
                    body.extend(chunk)
                    if len(body) > max_bytes:
                        raise ResponseTooLarge("The answer was too large.")
                seen = {name.lower(): value for name, value in response.headers.items()}
                return TransportResponse(response.status_code, seen, bytes(body))
        except httpx.HTTPError as error:
            raise TransportError(type(error).__name__) from None


def _checked_url(url: str) -> str:
    """The URL if it is plain HTTPS to one of the two NSE hosts, else FilingsRefused."""
    try:
        host = urlsplit(url).hostname
    except ValueError:
        host = None
    if not _URL_SHAPE.fullmatch(url) or host not in ALLOWED_HOSTS:
        raise FilingsRefused
    return url


def _allowed_or_none(url: object) -> str | None:
    try:
        return _checked_url(url) if isinstance(url, str) else None
    except FilingsRefused:
        return None


def _parse_nse_date(text: object) -> date | None:
    parts = str(text or "").strip().split(" ")[0].split("-")
    if len(parts) != 3 or parts[1].lower() not in _MONTHS:
        return None
    try:
        return date(int(parts[2]), _MONTHS[parts[1].lower()], int(parts[0]))
    except ValueError:
        return None


def _flag(item: Mapping[str, Any]) -> str:
    value = str(item.get("bank") or "N").strip().upper()
    return value if value in ("N", "B", "F") else "X"


def _parse_row(item: object, symbol: str, period: str) -> ResultRow | None:
    if not isinstance(item, dict):
        return None
    ended = _parse_nse_date(item.get("toDate"))
    url = _allowed_or_none(item.get("xbrl"))
    shown = str(item.get("symbol") or symbol).strip().upper()
    if ended is None or url is None or shown != symbol or not url.lower().endswith(".xml"):
        return None
    isin = str(item.get("isin") or "").strip().upper()
    kind = re.sub(r"[\s-]", "", str(item.get("indAs") or "")).lower()
    return ResultRow(
        symbol=symbol,
        company_name=clean_text(item.get("companyName") or "", 200),
        isin=isin if _ISIN.fullmatch(isin) else "",
        period_end=ended,
        relating_to=clean_text(item.get("relatingTo") or "", 40),
        period_kind=period,
        consolidated=str(item.get("consolidated") or "").strip().lower() == "consolidated",
        audited=str(item.get("audited") or "").strip().lower() == "audited",
        ind_as=kind.startswith("indas"),
        lender_flag=_flag(item),
        filed_on=_parse_nse_date(item.get("filingDate")),
        xbrl_url=url,
        detail_url=_allowed_or_none(item.get("resultDetailedDataLink")),
    )


class NseFilingsClient:
    def __init__(
        self,
        transport: Transport | None = None,
        sleep: Callable[[float], None] = time.sleep,
        clock: Callable[[], float] = time.monotonic,
        pause_seconds: float = DEFAULT_PAUSE_SECONDS,
    ) -> None:
        self._transport: Transport = transport or HttpxTransport()
        self._sleep = sleep
        self._clock = clock
        self.pause_seconds = max(pause_seconds, MIN_PAUSE_SECONDS)
        self._last_request: float | None = None
        self._listed: set[str] = set()

    def list_results(self, symbol: str) -> list[ResultRow]:
        """The company's Quarterly and Half-Yearly filings, merged, newest information first as NSE sends it."""
        wanted = normalize_symbol(symbol)
        if wanted is None:
            raise InvalidSymbol
        rows: dict[str, ResultRow] = {}
        for period in PERIODS:
            for row in self._list_period(wanted, period):
                rows.setdefault(row.xbrl_url, row)
        self._listed.update(rows)
        return list(rows.values())

    def fetch_xbrl(self, url: str) -> bytes:
        """One filing's file. Only a link NSE's own list returned, on an allowed host, is opened."""
        if _allowed_or_none(url) is None or url not in self._listed:
            raise FilingsRefused
        return self._get(url)

    def fetch_industry_groups(self) -> dict[str, IndustryGroup]:
        """NSE's industry group for each stock, from the public Nifty Total Market list."""
        body = self._get(INDUSTRY_URL)
        try:
            reader = csv.DictReader(io.StringIO(body.decode("utf-8-sig")))
            needed = {"Company Name", "Industry", "Symbol", "ISIN Code"}
            if not needed <= set(reader.fieldnames or ()):
                raise FilingsUnavailable(_UNREADABLE)
            groups = _industry_groups(reader)
        except (UnicodeDecodeError, csv.Error):
            raise FilingsUnavailable(_UNREADABLE) from None
        if not groups:
            raise FilingsUnavailable(_UNREADABLE)
        return groups

    def _list_period(self, symbol: str, period: str) -> list[ResultRow]:
        query = f"index=equities&symbol={quote(symbol, safe='-')}&period={period}"
        try:
            body = self._get(f"{LIST_URL}?{query}")
            items = json.loads(body)
        except FilingsNotFound:
            raise FilingsUnavailable from None
        except ValueError:
            raise FilingsUnavailable(_UNREADABLE) from None
        if not isinstance(items, list):
            raise FilingsUnavailable(_UNREADABLE)
        rows = (_parse_row(item, symbol, period) for item in items)
        return [row for row in rows if row is not None]

    def _get(self, url: str) -> bytes:
        current = _checked_url(url)
        host = urlsplit(current).hostname
        for _ in range(MAX_REDIRECTS + 1):
            response = self._send(current)
            if response.status not in _REDIRECTS:
                return self._body(response)
            target = _checked_url(urljoin(current, response.headers.get("location", "")))
            if urlsplit(target).hostname != host:
                raise FilingsRefused
            current = target
        raise FilingsRefused("NSE sent QuantOS in a circle, so this link was not opened.")

    def _send(self, url: str) -> TransportResponse:
        if self._last_request is not None:
            wait = self.pause_seconds - (self._clock() - self._last_request)
            if wait > 0:
                self._sleep(wait)
        try:
            return self._transport.get(url, HEADERS, REQUEST_TIMEOUT_SECONDS, MAX_RESPONSE_BYTES)
        except ResponseTooLarge:
            raise FilingsRefused(_TOO_LARGE) from None
        except TransportError as error:
            raise FilingsUnavailable(detail=str(error)) from None
        finally:
            self._last_request = self._clock()

    @staticmethod
    def _body(response: TransportResponse) -> bytes:
        if response.status in _BLOCKED:
            raise FilingsBlocked(detail=f"answer {response.status}")
        if response.status == 404:
            raise FilingsNotFound(detail="answer 404")
        if response.status != 200:
            raise FilingsUnavailable(detail=f"answer {response.status}")
        if len(response.body) > MAX_RESPONSE_BYTES:
            raise FilingsRefused(_TOO_LARGE)
        return response.body


def _industry_groups(reader: csv.DictReader[str]) -> dict[str, IndustryGroup]:
    groups: dict[str, IndustryGroup] = {}
    for record in reader:
        symbol = (record.get("Symbol") or "").strip().upper()
        industry = clean_text(record.get("Industry") or "", 80)
        isin = (record.get("ISIN Code") or "").strip().upper()
        if SYMBOL_PATTERN.fullmatch(symbol) and industry:
            name = clean_text(record.get("Company Name") or "", 200)
            groups[symbol] = IndustryGroup(name, industry, isin if _ISIN.fullmatch(isin) else "")
    return groups
