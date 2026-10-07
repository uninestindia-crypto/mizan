"""Safe reading of an NSE results filing (XBRL), standard library only.

The file is untrusted. It is refused before parsing if it is too large, is not plain UTF-8, or declares a
DOCTYPE or an ENTITY, so there is nothing to expand and nothing external to fetch. Contexts are found from the
filing's own dates, never from the names NSE happens to use for them.
"""

from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Final

MAX_XBRL_BYTES: Final = 8 * 1024 * 1024
_UNSAFE: Final = re.compile(r"<!\s*(?:DOCTYPE|ENTITY|ELEMENT|ATTLIST|NOTATION)", re.IGNORECASE)
_ENCODING: Final = re.compile(r"""^\s*<\?xml[^>]*?encoding\s*=\s*["']([^"']+)["']""", re.IGNORECASE)
_NUMBER: Final = re.compile(r"[+-]?(?:[0-9]+(?:\.[0-9]*)?|\.[0-9]+)")
_DIMENSION_TAGS: Final = frozenset({"scenario", "segment", "explicitMember", "typedMember"})
_RUPEE_UNITS: Final = frozenset({"INR", "INR/shares"})
_NIL: Final = "{http://www.w3.org/2001/XMLSchema-instance}nil"
_XLINK_HREF: Final = "{http://www.w3.org/1999/xlink}href"
START_TAG: Final = "DateOfStartOfReportingPeriod"
END_TAG: Final = "DateOfEndOfReportingPeriod"

UNSAFE_MESSAGE: Final = "This filing file could not be read safely."
TOO_LARGE_MESSAGE: Final = "This filing file is too large, so it could not be read safely."
MALFORMED_MESSAGE: Final = "This filing file could not be read."


class XbrlError(ValueError):
    """The file cannot be read. The message is plain language."""


@dataclass(frozen=True, order=True)
class Period:
    """A balance-sheet date (start is None) or a stretch of time, as the filing itself dates it."""

    start: date | None
    end: date


@dataclass(frozen=True)
class Reading:
    """One figure as filed. `problem` is a plain phrase when the figure is present but unusable."""

    value: Decimal | None
    decimals: str | None
    problem: str | None


@dataclass(frozen=True)
class _Fact:
    tag: str
    context: str
    text: str
    unit: str | None
    decimals: str | None
    nil: bool


@dataclass(frozen=True)
class _Context:
    start: date | None
    end: date | None
    dimensional: bool


def parse_decimal(text: str) -> Decimal | None:
    """A plain decimal number, or None. No exponents, separators, NaN, infinity or non-ASCII digits."""
    cleaned = text.strip()
    if len(cleaned) > 40 or not _NUMBER.fullmatch(cleaned):
        return None
    return Decimal(cleaned)


def _parse_date(text: str) -> date | None:
    try:
        return date.fromisoformat(text.strip()[:10])
    except ValueError:
        return None


def _usable(stated: dict[str, date]) -> bool:
    """The filing gives both a start and an end for the context, and they are in order."""
    return START_TAG in stated and END_TAG in stated and stated[START_TAG] <= stated[END_TAG]


def _local(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def _guard(data: bytes) -> None:
    if len(data) > MAX_XBRL_BYTES:
        raise XbrlError(TOO_LARGE_MESSAGE)
    if b"\x00" in data:
        raise XbrlError(UNSAFE_MESSAGE)
    try:
        text = data.decode("utf-8-sig")
    except UnicodeDecodeError:
        raise XbrlError(UNSAFE_MESSAGE) from None
    declared = _ENCODING.match(text)
    if declared and declared.group(1).strip().lower().replace("_", "-") not in {"utf-8", "utf8"}:
        raise XbrlError(UNSAFE_MESSAGE)
    if _UNSAFE.search(text):
        raise XbrlError(UNSAFE_MESSAGE)


def _read_context(element: ET.Element) -> _Context:
    start = end = None
    for node in element.iter():
        name = _local(node.tag)
        if name == "startDate":
            start = _parse_date(node.text or "")
        elif name in ("endDate", "instant"):
            end = _parse_date(node.text or "")
    dimensional = any(_local(node.tag) in _DIMENSION_TAGS for node in element.iter())
    return _Context(start, end, dimensional)


def _read_unit(element: ET.Element) -> str:
    parts = [(node.text or "").strip().rsplit(":", 1)[-1] for node in element.iter()
             if _local(node.tag) == "measure"]  # fmt: skip
    return "/".join(parts)


class XbrlDocument:
    """The facts of one filing, indexed by tag and by the period the filing itself gives them."""

    def __init__(self, root: ET.Element) -> None:
        contexts: dict[str, _Context] = {}
        units: dict[str, str] = {}
        facts: list[_Fact] = []
        self.schema_ref: str | None = None
        for element in root:
            name = _local(element.tag)
            if name == "context":
                contexts[element.get("id", "")] = _read_context(element)
            elif name == "unit":
                units[element.get("id", "")] = _read_unit(element)
            elif name == "schemaRef":
                self.schema_ref = element.get(_XLINK_HREF)
            elif element.get("contextRef") is not None:
                facts.append(self._fact(element, units))
        self._facts = facts
        self._contexts = contexts
        self._periods = self._resolve_periods(contexts, facts)
        self.tags: frozenset[str] = frozenset(fact.tag for fact in facts)
        self._index: dict[tuple[str, Period], list[_Fact]] = {}
        for fact in facts:
            period = self._periods.get(fact.context)
            if period is not None:
                self._index.setdefault((fact.tag, period), []).append(fact)

    @staticmethod
    def _fact(element: ET.Element, units: dict[str, str]) -> _Fact:
        unit_id = element.get("unitRef")
        return _Fact(
            tag=_local(element.tag),
            context=element.get("contextRef", ""),
            text=(element.text or "").strip(),
            unit=units.get(unit_id) if unit_id is not None else None,
            decimals=element.get("decimals"),
            nil=element.get(_NIL, "").lower() == "true",
        )

    @staticmethod
    def _resolve_periods(contexts: dict[str, _Context], facts: list[_Fact]) -> dict[str, Period]:
        """A context's period is its own dates, unless the filing states the period for that context.

        NSE files often declare the year-to-date context with the quarter's dates and give the true start
        in a DateOfStartOfReportingPeriod fact that sits in that context.
        """
        declared: dict[str, dict[str, date]] = {}
        for fact in facts:
            if fact.tag in (START_TAG, END_TAG) and (when := _parse_date(fact.text)):
                declared.setdefault(fact.context, {})[fact.tag] = when
        periods: dict[str, Period] = {}
        for ident, context in contexts.items():
            if context.dimensional or context.end is None:
                continue
            stated = declared.get(ident, {})
            use_stated = context.start is not None and _usable(stated)
            start, end = (
                (stated[START_TAG], stated[END_TAG]) if use_stated else (context.start, context.end)
            )
            periods[ident] = Period(start, end)
        return periods

    def read_number(self, tag: str, period: Period) -> Reading:
        facts = self._index.get((tag, period), [])
        if not facts:
            return Reading(None, None, None)
        outcomes = [self._classify(fact) for fact in facts]
        problems = [problem for value, problem in outcomes if value is None]
        values = {value for value, _ in outcomes if value is not None}
        if len(values) == 1 and not problems:
            return Reading(next(iter(values)), facts[0].decimals, None)
        if values:
            return Reading(None, None, "is filed twice with different values")
        return Reading(None, None, problems[0])

    @staticmethod
    def _classify(fact: _Fact) -> tuple[Decimal | None, str | None]:
        if fact.nil or not fact.text:
            return None, "is left empty"
        if fact.unit not in _RUPEE_UNITS:
            return None, "is not filed in Indian rupees"
        value = parse_decimal(fact.text)
        return (value, None) if value is not None else (None, "is not a valid number")

    def read_text(self, tag: str) -> str | None:
        texts = self.read_texts(tag)
        return texts[0] if texts else None

    def read_texts(self, tag: str) -> list[str]:
        return [fact.text for fact in self._facts if fact.tag == tag and fact.text and not fact.nil]

    def has_instant(self, end: date) -> bool:
        wanted = Period(None, end)
        return any(period == wanted for _, period in self._index)

    def duration_periods(self, end: date) -> list[Period]:
        """Distinct durations ending on `end`, longest first."""
        found = {p for p in self._periods.values() if p.start is not None and p.end == end}
        return sorted(found, key=lambda period: period.start or end)

    def declared_period_ends(self) -> set[date]:
        return {d for text in self.read_texts(END_TAG) if (d := _parse_date(text)) is not None}


def parse_xbrl(data: bytes) -> XbrlDocument:
    """Parse a filing. Raises XbrlError (plain message) for anything unsafe or unreadable."""
    _guard(data)
    try:
        root = ET.fromstring(data)
    except (ET.ParseError, ValueError, RecursionError):
        raise XbrlError(MALFORMED_MESSAGE) from None
    return XbrlDocument(root)
