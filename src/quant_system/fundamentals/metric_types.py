"""What a metric is: a value, its plain label, the formula in words, the inputs with their proof, and its date."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from typing import Any, Final, NamedTuple

from quant_system.fundamentals.metric_words import WORDS
from quant_system.fundamentals.models import Figure, QuarterFigures

FILING: Final = "FILING"
PRICE: Final = "PRICE"
PRICE_SOURCE: Final = "QuantOS end-of-day price data"

INR: Final = "INR"
PER_SHARE: Final = "INR per share"
PERCENT: Final = "percent"
TIMES: Final = "times"
COUNT: Final = "quarters"
PER_SHARE_TAGS: Final = frozenset(
    {
        "BasicEarningsLossPerShareFromContinuingAndDiscontinuedOperations",
        "BasicEarningsLossPerShareFromContinuingOperations",
        "FaceValueOfEquityShareCapital",
    }
)


@dataclass(frozen=True)
class PriceQuote:
    """The platform's own last close for a stock and the session it is from."""

    close: Decimal
    as_of: date


@dataclass(frozen=True)
class Proof:
    """One number a metric was worked out from, and where a person can check it."""

    kind: str
    label: str
    tag: str
    value: Decimal
    unit: str
    period: str
    period_end: date
    filed_on: date | None
    source_url: str
    sha256: str


@dataclass(frozen=True)
class Metric:
    key: str
    label: str
    unit: str
    value: Decimal | None
    formula: str
    period: str
    as_of: date | None
    inputs: tuple[Proof, ...] = ()
    note: str = ""
    reason: str = ""
    approximate: bool = False
    extra: dict[str, Any] = field(default_factory=dict)

    @property
    def available(self) -> bool:
        return self.value is not None


Metrics = dict[str, Metric]


@dataclass(frozen=True)
class Text:
    """The plain words that never change for a metric."""

    label: str
    formula: str


class Span(NamedTuple):
    """The period a metric covers, in words, and the date it is as of."""

    period: str
    as_of: date | None


def build(key: str, unit: str, value: Decimal | None, span: Span) -> Metric:
    """A metric with its plain words filled in; callers add inputs and notes with `dataclasses.replace`."""
    text = WORDS[key]
    return Metric(key, text.label, unit, value, text.formula, span.period, span.as_of)


def filing_proof(quarter: QuarterFigures, key: str, label: str) -> Proof | None:
    figure = quarter.lines.get(key)
    return figure_proof(quarter, figure, label) if figure else None


def figure_proof(quarter: QuarterFigures, figure: Figure, label: str) -> Proof:
    unit = PER_SHARE if figure.tag in PER_SHARE_TAGS else INR
    return Proof(
        FILING,
        label,
        figure.tag,
        figure.value,
        unit,
        quarter.period_label,
        quarter.period_end,
        quarter.filed_on,
        quarter.source_url,
        quarter.sha256,
    )


def price_proof(price: PriceQuote) -> Proof:
    return Proof(
        PRICE,
        "Last close",
        "",
        price.close,
        PER_SHARE,
        f"Close of {price.as_of.isoformat()}",
        price.as_of,
        None,
        "",
        "",
    )


def missing(key: str, unit: str, reason: str) -> Metric:
    """A metric that cannot be worked out, with the plain reason."""
    text = WORDS[key]
    return Metric(key, text.label, unit, None, text.formula, "", None, reason=reason)
