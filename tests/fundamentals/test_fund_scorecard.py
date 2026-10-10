"""The scorecard: plain facts, each with the rule of thumb behind it, and not one word of advice."""

from __future__ import annotations

import re
from datetime import date
from decimal import Decimal

import pytest

from quant_system.fundamentals.metric_types import Metrics, PriceQuote
from quant_system.fundamentals.metrics import compute_metrics
from quant_system.fundamentals.scorecard import HEADER, Scorecard, build_scorecard
from quant_system.fundamentals.series import build_series
from tests.fundamentals.support import balance, cr, quarter, quarter_ends, with_balance

ENDS = quarter_ends(8)
PRICE = PriceQuote(Decimal("800"), date(2026, 10, 6))
ADVICE = re.compile(
    r"\b(buy|sell|best|undervalued|overvalued|recommend\w*|target|cheap|expensive|should)\b", re.I
)


def _card(
    profits: tuple[int, ...] = (9, 12, 15, 18, 21, 24, 27, 30),
    finance: int = 2,
    sheet: tuple[int, int, int] | None = (400, 30, 10),
    price: PriceQuote | None = PRICE,
    stale: bool = False,
) -> tuple[Scorecard, Metrics]:
    items = [
        quarter(end, cr(100 + 10 * i), cr(p), cr(finance), str(Decimal(p) / 10), shares=10_000_000)
        for i, (end, p) in enumerate(zip(ENDS, profits, strict=True))
    ]
    if sheet is not None:
        equity, current, noncurrent = sheet
        items[6] = with_balance(
            items[6], balance(ENDS[6], cr(equity), (cr(current), cr(noncurrent)))
        )
    series = build_series(items)
    metrics = compute_metrics(series, price)
    return build_scorecard(metrics, series, stale), metrics


def _all_text(card: Scorecard, metrics: Metrics) -> list[str]:
    facts = [text for fact in card.facts for text in (fact.sentence, fact.rule)]
    notes = [
        text
        for metric in metrics.values()
        for text in (metric.label, metric.formula, metric.note, metric.reason, metric.period)
    ]
    return [card.header, *facts, *notes]


def _fact(card: Scorecard, key: str) -> tuple[str, str]:
    found = next(f for f in card.facts if f.key == key)
    return found.status, found.sentence


def test_the_header_says_these_are_rules_of_thumb_and_not_advice() -> None:
    card, _ = _card()
    assert card.header == HEADER
    assert HEADER == (
        "Rules of thumb for reading a company, not advice. "
        "Whether a stock suits you depends on your goals."
    )


def test_steady_profit_is_stated_as_a_count_and_checked_against_a_rule() -> None:
    assert _fact(_card()[0], "profitable_quarters") == ("OK", "Profit in 8 of the last 8 quarters.")
    mixed = _card(profits=(9, -12, 15, -18, 21, -24, 27, 30))[0]
    assert _fact(mixed, "profitable_quarters") == ("WATCH", "Profit in 5 of the last 8 quarters.")


def test_profit_growth_is_stated_with_its_sign_and_what_it_is_compared_with() -> None:
    card, _ = _card()
    assert _fact(card, "profit_growth_quarter") == (
        "OK",
        "Profit changed +67% against the same quarter a year ago.",
    )
    assert _fact(card, "profit_growth_ttm")[1] == (
        "Profit over the last four quarters changed +89% against the four quarters before."
    )


def test_falling_profit_is_a_watch_item_not_a_verdict() -> None:
    falling = _card(profits=(30, 27, 24, 21, 18, 15, 12, 9))[0]
    status, sentence = _fact(falling, "profit_growth_quarter")
    assert (
        status == "WATCH" and sentence == "Profit changed -57% against the same quarter a year ago."
    )


def test_borrowings_are_compared_with_the_owners_money() -> None:
    assert _fact(_card()[0], "debt_to_equity") == (
        "OK",
        "Borrowings are 0.1 times the owners' money.",
    )
    heavy = _card(sheet=(100, 90, 60))[0]
    assert _fact(heavy, "debt_to_equity") == (
        "WATCH",
        "Borrowings are 1.5 times the owners' money.",
    )


def test_interest_cover_has_a_rule_of_three_times() -> None:
    assert _fact(_card()[0], "interest_cover")[0] == "OK"
    # Profit before tax 136 + finance costs 4 x 40 = 296, over 160 = 1.85 times.
    status, sentence = _fact(_card(finance=40)[0], "interest_cover")
    assert status == "WATCH" and "1.9 times" in sentence


def test_no_interest_bill_is_stated_as_a_fact() -> None:
    status, sentence = _fact(_card(finance=0)[0], "interest_cover")
    assert status == "INFO" and sentence == "No interest cost was filed in the last four quarters."


def test_return_on_equity_is_called_approximate_and_checked_against_a_rule() -> None:
    status, sentence = _fact(_card()[0], "roe")
    assert status == "OK" and "26%" in sentence and "approximate" in sentence.lower()
    assert _fact(_card(sheet=(1000, 30, 10))[0], "roe")[0] == "WATCH"


@pytest.mark.parametrize("key", ["pe", "pb", "earnings_yield"])
def test_price_ratios_are_information_only_and_never_a_verdict(key: str) -> None:
    card, _ = _card()
    assert _fact(card, key)[0] == "INFO"


def test_the_price_to_earnings_sentence_states_the_price_and_its_date() -> None:
    card, _ = _card()
    assert _fact(card, "pe")[1] == (
        "At the last close of Rs 800 (6 Oct 2026), the price was 78 times the earnings per share "
        "of the last four quarters."
    )


def test_each_fact_carries_the_rule_of_thumb_behind_it() -> None:
    card, _ = _card()
    rules = {f.key: f.rule for f in card.facts}
    assert rules["roe"].startswith("Rule of thumb:") and "12%" in rules["roe"]
    assert "similar companies" in rules["pe"]


def test_what_cannot_be_worked_out_is_listed_as_not_available_with_the_reason() -> None:
    card, _ = _card(sheet=None, price=None)
    status, sentence = _fact(card, "roe")
    assert status == "NOT_AVAILABLE" and "balance sheet" in sentence
    assert (
        _fact(card, "pe")[0] == "NOT_AVAILABLE"
        and "Market data is not connected" in _fact(card, "pe")[1]
    )


def test_old_figures_are_flagged_first() -> None:
    card, _ = _card(stale=True)
    assert card.facts[0].key == "data_age" and card.facts[0].status == "WATCH"
    assert "more than 18 months" in card.facts[0].sentence


def test_the_date_of_the_latest_quarter_is_always_stated() -> None:
    card, _ = _card()
    assert any(f.key == "latest_quarter" and "31 Dec 2024" in f.sentence for f in card.facts)


def test_the_counts_add_up_to_the_facts() -> None:
    card, _ = _card()
    assert sum(card.counts.values()) == len(card.facts)
    assert set(card.counts) == {"OK", "WATCH", "INFO", "NOT_AVAILABLE"}


@pytest.mark.parametrize(
    "scenario",
    [
        {},
        {"profits": (30, 27, 24, 21, 18, 15, 12, 9)},
        {"profits": (-9, -12, -15, -18, -21, -24, -27, -30)},
        {"finance": 0},
        {"finance": 40, "sheet": (100, 90, 60)},
        {"sheet": None, "price": None},
        {"stale": True},
    ],
)
def test_no_word_of_advice_appears_anywhere_in_any_generated_text(
    scenario: dict[str, object],
) -> None:
    card, metrics = _card(**scenario)  # type: ignore[arg-type]
    assert [w for w in _all_text(card, metrics) if ADVICE.search(w)] == []


@pytest.mark.parametrize("scenario", [{}, {"sheet": None, "price": None}, {"stale": True}])
def test_every_sentence_ends_with_a_full_stop_and_has_no_code_words(
    scenario: dict[str, object],
) -> None:
    card, _ = _card(**scenario)  # type: ignore[arg-type]
    sentences = [f.sentence for f in card.facts]
    assert all(s.endswith(".") for s in sentences)
    assert not [s for s in sentences if re.search(r"[a-z]+_[a-z]+|None|null|\bTTM\b", s)]
