"""Public news headlines for a stock, read from Google News' RSS feed. No key and no account are needed.

Headlines are *untrusted outside text*: they are cleaned, capped and only ever shown as data. The feed is read with a
size cap, and any document that declares a DOCTYPE or an entity is refused, because that is how XML expansion
attacks are built. Each headline also gets a rough tone from a small published word list. It is a keyword count, so
it is labelled as rough; the AI second opinion reads the headlines properly.
"""

from __future__ import annotations

import re
import threading
import time
import urllib.request
import xml.etree.ElementTree as ET
from collections.abc import Callable
from datetime import UTC
from email.utils import parsedate_to_datetime
from typing import Any
from urllib.parse import quote

__all__ = ["GoogleNewsSource", "NewsError", "headline_tone", "parse_feed"]

FEED = "https://news.google.com/rss/search?q={query}&hl=en-IN&gl=IN&ceid=IN:en"
MAX_BYTES = 1_000_000
TITLE_CHARS = 200
CACHE_SECONDS = 600.0
CACHE_ENTRIES = 64
Fetch = Callable[[str, float], bytes]

# Control characters and the invisible direction marks that can make text read differently from how it is stored.
_CONTROL = re.compile("[\x00-\x1f\x7f\u200b-\u200f\u202a-\u202e\u2066-\u2069]")
_WORDS = re.compile(r"[a-z]+")
_POSITIVE = frozenset(
    "surge surges surged jump jumps jumped rally rallies rallied gain gains gained rise rises rose soar soars soared "
    "beat beats upgrade upgrades upgraded win wins won bag bags record strong growth profit profits buyback "
    "dividend approval approved expands expansion boost boosts".split()
)
_NEGATIVE = frozenset(
    "fall falls fell plunge plunges plunged slump slumps slumped drop drops dropped loss losses probe fraud downgrade "
    "downgrades downgraded penalty fined default defaults resigns resigned raid raids lawsuit ban banned cut cuts "
    "weak miss misses missed decline declines declined tumble tumbles tumbled warning warns crash scam".split()
)


class NewsError(Exception):
    """The feed could not be read safely. The message is for logs; the person is told something plainer."""


def fetch_capped(url: str, timeout: float) -> bytes:
    request = urllib.request.Request(url, headers={"User-Agent": "QuantOS/2.0"})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        data: bytes = response.read(MAX_BYTES + 1)
    if len(data) > MAX_BYTES:
        raise NewsError("the news feed was larger than the allowed size")
    return data


def _clean(text: str | None, limit: int = TITLE_CHARS) -> str:
    return " ".join(_CONTROL.sub(" ", text or "").split())[:limit]


def headline_tone(title: str) -> str:
    """POSITIVE, NEGATIVE or NEUTRAL from a keyword count. Rough on purpose: it cannot read context or sarcasm."""
    words = _WORDS.findall(title.lower())
    score = sum(w in _POSITIVE for w in words) - sum(w in _NEGATIVE for w in words)
    return "POSITIVE" if score > 0 else "NEGATIVE" if score < 0 else "NEUTRAL"


def _link(raw: str | None) -> str | None:
    link = (raw or "").strip()
    return link if link.lower().startswith(("https://", "http://")) else None


def _published(raw: str | None) -> str | None:
    try:
        when = parsedate_to_datetime((raw or "").strip())
    except (TypeError, ValueError):
        return None
    return when.astimezone(UTC).date().isoformat() if when.tzinfo else when.date().isoformat()


def _split_source(title: str, source: str) -> tuple[str, str]:
    """Google News writes ``Headline - Outlet``. Take the outlet out of the headline when it is repeated."""
    head, sep, tail = title.rpartition(" - ")
    if sep and (not source or tail.strip().lower() == source.lower()):
        return head.strip(), source or tail.strip()
    return title, source


def _item(node: ET.Element) -> dict[str, Any] | None:
    raw_title = _clean(node.findtext("title"), TITLE_CHARS + 60)
    title, source = _split_source(raw_title, _clean(node.findtext("source"), 80))
    if not title:
        return None
    return {
        "title": title[:TITLE_CHARS],
        "source": source or None,
        "link": _link(node.findtext("link")),
        "published": _published(node.findtext("pubDate")),
        "tone": headline_tone(title),
    }


def parse_feed(data: bytes, limit: int = 10) -> list[dict[str, Any]]:
    if len(data) > MAX_BYTES:
        raise NewsError("the news feed was larger than the allowed size")
    lowered = data.lower()
    if b"<!doctype" in lowered or b"<!entity" in lowered:
        raise NewsError("the news feed declared a document type, which is refused")
    try:
        root = ET.fromstring(data)
    except ET.ParseError as error:
        raise NewsError("the news feed was not valid XML") from error
    seen: set[str] = set()
    items: list[dict[str, Any]] = []
    for node in root.findall("./channel/item"):
        item = _item(node)
        if item is None or item["title"].lower() in seen:
            continue
        seen.add(item["title"].lower())
        items.append(item)
    return items[:limit]


class GoogleNewsSource:
    """``headlines(query)`` for the news tool. Results are cached briefly so a whole panel costs one fetch."""

    def __init__(
        self,
        fetch: Fetch = fetch_capped,
        *,
        limit: int = 10,
        timeout: float = 10.0,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._fetch = fetch
        self._limit = limit
        self._timeout = timeout
        self._clock = clock
        self._lock = threading.Lock()
        self._cache: dict[str, tuple[float, list[dict[str, Any]]]] = {}

    def headlines(self, query: str) -> list[dict[str, Any]]:
        key = " ".join(query.lower().split())
        with self._lock:
            hit = self._cache.get(key)
        if hit and self._clock() - hit[0] < CACHE_SECONDS:
            return [dict(item) for item in hit[1]]
        url = FEED.format(query=quote(f'"{_clean(query, 80)}" NSE stock', safe=""))
        items = parse_feed(self._fetch(url, self._timeout), self._limit)
        with self._lock:
            if len(self._cache) >= CACHE_ENTRIES:
                self._cache.pop(next(iter(self._cache)))
            self._cache[key] = (self._clock(), items)
        return [dict(item) for item in items]
