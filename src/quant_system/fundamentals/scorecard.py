"""A list of plain facts about a company, each with the rule of thumb behind it.

Statuses describe a fact against a rule, never a person's decision:
OK means the figure is inside the rule of thumb, WATCH means it is outside it, INFO means it is a fact with no rule
that applies on its own (a price ratio, a margin), NOT_AVAILABLE means it could not be worked out and says why.
Nothing here says what to do with a stock.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from decimal import Decimal
from typing import Final

from quant_system.fundamentals import fmt
from quant_system.fundamentals.metric_types import Metric, Metrics
from quant_system.fundamentals.series import Series

OK: Final = "OK"
WATCH: Final = "WATCH"
INFO: Final = "INFO"
NOT_AVAILABLE: Final = "NOT_AVAILABLE"
STATUSES: Final = (OK, WATCH, INFO, NOT_AVAILABLE)
HEADER: Final = (
    "Rules of thumb for reading a company, not advice. "
    "Whether a stock suits you depends on your goals."
)

MIN_PROFITABLE: Final = 6
MIN_COVER: Final = Decimal(3)
MAX_BORROWINGS: Final = Decimal(1)
MIN_ROE: Final = Decimal(12)
ZERO: Final = Decimal(0)

RULES: Final = {
    "profitable_quarters": "Rule of thumb: profit in at least 6 of the last 8 quarters.",
    "growth": "Rule of thumb: not lower than a year ago.",
    "interest_cover": "Rule of thumb: profit before interest and tax at least 3 times the interest bill.",
    "debt_to_equity": "Rule of thumb: borrowings of 1 times the owners' money or less. This varies a lot by industry.",
    "roe": "Rule of thumb: profit of 12% or more of the owners' money.",
    "margin": "Margins differ a lot between industries, so they are read against similar companies.",
    "price": (
        "Price ratios are read against similar companies and the company's own past; "
        "a low or a high number does not say more on its own."
    ),
}


@dataclass(frozen=True)
class Fact:
    key: str
    status: str
    sentence: str
    rule: str
    metric: str


@dataclass(frozen=True)
class Scorecard:
    header: str
    facts: tuple[Fact, ...]
    counts: dict[str, int]


Maker = Callable[[Metric], tuple[str, str]]


def _signed(metric: Metric) -> str:
    assert metric.value is not None
    return fmt.percent(metric.value, 0, signed=True)


def _growth(subject: str, against: str) -> Maker:
    def make(metric: Metric) -> tuple[str, str]:
        assert metric.value is not None
        status = OK if metric.value >= ZERO else WATCH
        return status, f"{subject} changed {_signed(metric)} against {against}."

    return make


def _profitable(metric: Metric) -> tuple[str, str]:
    assert metric.value is not None
    count, out_of = int(metric.value), int(metric.extra["out_of"])
    held = int(metric.extra["quarters_held"])
    status = OK if count >= MIN_PROFITABLE * held // out_of else WATCH
    if held == out_of:
        return status, f"Profit in {count} of the last {out_of} quarters."
    return status, f"Profit in {count} of the {held} quarters held, out of the last {out_of}."


def _cover(metric: Metric) -> tuple[str, str]:
    assert metric.value is not None
    status = OK if metric.value >= MIN_COVER else WATCH
    return (
        status,
        f"Profit before interest and tax covered the interest bill {fmt.times(metric.value)} times.",
    )


def _borrowings(metric: Metric) -> tuple[str, str]:
    assert metric.value is not None
    status = OK if metric.value <= MAX_BORROWINGS else WATCH
    return status, f"Borrowings are {fmt.times(metric.value)} times the owners' money."


def _roe(metric: Metric) -> tuple[str, str]:
    assert metric.value is not None
    status = OK if metric.value >= MIN_ROE else WATCH
    text = f"Profit over the last four quarters was {fmt.percent(metric.value)} of the owners' money (approximate)."
    return status, text


def _margin(what: str) -> Maker:
    def make(metric: Metric) -> tuple[str, str]:
        assert metric.value is not None
        rupees = fmt.times(metric.value, 0)
        return (
            INFO,
            f"Out of every Rs 100 of sales, Rs {rupees} was left as {what} over the last four quarters.",
        )

    return make


def _price_ratio(metric: Metric) -> tuple[str, str]:
    assert metric.value is not None
    return INFO, f"{metric.period}: {fmt.times(metric.value)} times."


def _pe(metric: Metric) -> tuple[str, str]:
    assert metric.value is not None and metric.inputs
    price = metric.inputs[0]
    when = fmt.day(price.period_end)
    text = (
        f"At the last close of {fmt.inr(price.value)} ({when}), the price was {fmt.times(metric.value, 0)} times "
        "the earnings per share of the last four quarters."
    )
    return INFO, text


def _pb(metric: Metric) -> tuple[str, str]:
    assert metric.value is not None and metric.inputs
    when = fmt.day(metric.inputs[0].period_end)
    return (
        INFO,
        f"At the last close ({when}), the price was {fmt.times(metric.value)} times the owners' money per share.",
    )


def _yield(metric: Metric) -> tuple[str, str]:
    assert metric.value is not None
    return (
        INFO,
        f"Earnings over the last four quarters were {fmt.percent(metric.value, 1)} of the price.",
    )


# key -> (rule of thumb, sentence maker). Order is the order a person reads them in.
PLAN: Final[dict[str, tuple[str, Maker]]] = {
    "profitable_quarters": (RULES["profitable_quarters"], _profitable),
    "profit_growth_quarter": (RULES["growth"], _growth("Profit", "the same quarter a year ago")),
    "profit_growth_ttm": (
        RULES["growth"],
        _growth("Profit over the last four quarters", "the four quarters before"),
    ),
    "revenue_growth_quarter": (RULES["growth"], _growth("Sales", "the same quarter a year ago")),
    "revenue_growth_ttm": (
        RULES["growth"],
        _growth("Sales over the last four quarters", "the four quarters before"),
    ),
    "net_margin": (RULES["margin"], _margin("profit")),
    "operating_margin": (
        RULES["margin"],
        _margin("operating profit (before interest and other income)"),
    ),
    "interest_cover": (RULES["interest_cover"], _cover),
    "debt_to_equity": (RULES["debt_to_equity"], _borrowings),
    "roe": (RULES["roe"], _roe),
    "pe": (RULES["price"], _pe),
    "pb": (RULES["price"], _pb),
    "earnings_yield": (RULES["price"], _yield),
}
NO_INTEREST = "No interest cost was filed in the last four quarters."


def _fact(key: str, metric: Metric, rule: str, make: Maker) -> Fact:
    if metric.value is None:
        if metric.extra.get("code") == "NO_FINANCE_COSTS":
            return Fact(key, INFO, NO_INTEREST, rule, key)
        return Fact(
            key, NOT_AVAILABLE, f"{metric.label}: not available. {metric.reason}", rule, key
        )
    status, sentence = make(metric)
    return Fact(key, status, sentence, rule, key)


def _leading(series: Series, stale: bool) -> list[Fact]:
    latest = series.latest
    if latest is None:
        return []
    facts = []
    if stale:
        text = f"The newest filing held is for the quarter ended {fmt.day(latest.period_end)}, more than 18 months ago."
        facts.append(
            Fact("data_age", WATCH, text, "Figures older than 18 months are labelled old.", "")
        )
    filed = f" and was filed on {fmt.day(latest.filed_on)}" if latest.filed_on else ""
    text = f"The latest quarter held ended {fmt.day(latest.period_end)}{filed}."
    facts.append(Fact("latest_quarter", INFO, text, "", ""))
    return facts


def build_scorecard(metrics: Metrics, series: Series, stale: bool) -> Scorecard:
    """The facts for one company. `stale` is decided by the caller from its own clock."""
    facts = _leading(series, stale)
    facts += [
        _fact(key, metrics[key], rule, make) for key, (rule, make) in PLAN.items() if key in metrics
    ]
    counts = {status: sum(1 for fact in facts if fact.status == status) for status in STATUSES}
    return Scorecard(HEADER, tuple(facts), counts)
