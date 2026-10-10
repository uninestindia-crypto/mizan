"""The screen: filters the caller chooses, counted and explained, with nothing ranked as better."""

from __future__ import annotations

import json
import re
from dataclasses import replace
from datetime import date
from decimal import Decimal
from pathlib import Path

from quant_system.fundamentals.metric_types import PriceQuote
from quant_system.fundamentals.models import QuarterFigures
from quant_system.fundamentals.screen import Filters, screen
from quant_system.fundamentals.service import CompanyAnalysis, FundamentalsService
from quant_system.fundamentals.store import FundamentalsStore
from tests.fundamentals.support import balance, cr, quarter, quarter_ends, with_balance

TODAY = date(2025, 3, 1)
ADVICE = re.compile(
    r"\b(buy|sell|best|undervalued|overvalued|recommend\w*|target|cheap|expensive|should)\b", re.I
)
PRICES = {
    "AAA": PriceQuote(Decimal("800"), date(2025, 2, 28)),
    "CCC": PriceQuote(Decimal("100"), date(2025, 2, 27)),
}


def _company(
    symbol: str, profits: list[int], sheet: tuple[int, int, int] | None, last: int = 8
) -> list[QuarterFigures]:
    ends = quarter_ends(8)[8 - last :]
    items = [
        quarter(end, cr(100 + 10 * i), cr(p), cr(2), str(Decimal(p) / 10), shares=10_000_000)
        for i, (end, p) in enumerate(zip(ends, profits[8 - last :], strict=True))
    ]
    if sheet is not None:
        equity, debt_a, debt_b = sheet
        items[-2] = with_balance(items[-2], balance(ends[-2], cr(equity), (cr(debt_a), cr(debt_b))))
    return [replace(item, symbol=symbol, company_name=f"{symbol} Limited") for item in items]


def _found(tmp_path: Path) -> list[CompanyAnalysis]:
    store = FundamentalsStore(None, tmp_path / "f.sqlite")
    steady = [9, 12, 15, 18, 21, 24, 27, 30]
    store.put(_company("AAA", steady, (400, 30, 10)))  # D/E 0.1, ROE 25.5%
    store.put(
        _company("BBB", [9, -12, 15, -18, 21, -24, 27, 30], None)
    )  # 5 profitable quarters, no balance sheet
    store.put(_company("CCC", steady, (1000, 90, 60)))  # D/E 0.15, ROE 10.2%
    store.put(_company("DDD", steady, None, last=3))  # only three quarters held
    store.put_industry(
        {
            "AAA": "Information Technology",
            "BBB": "Metals & Mining",
            "CCC": "Information Technology",
        },
        "2025-02-01",
    )
    return FundamentalsService(store, lambda: TODAY).analyse_all(PRICES.get)


def _symbols(result: dict[str, object]) -> list[str]:
    return [row["symbol"] for row in result["results"]]  # type: ignore[index, union-attr]


def test_without_filters_every_company_is_listed_and_none_is_ranked(tmp_path: Path) -> None:
    result = screen(_found(tmp_path), Filters(), "symbol", "asc", 100)
    assert _symbols(result) == ["AAA", "BBB", "CCC", "DDD"]
    assert result["considered"] == 4 and result["matched"] == 4 and result["filters_applied"] == []


def test_it_always_says_these_are_the_callers_filters_and_not_a_recommendation(
    tmp_path: Path,
) -> None:
    result = screen(_found(tmp_path), Filters(min_roe_pct=Decimal(15)), "symbol", "asc", 100)
    assert result["statement"] == "These are filters you chose, not a recommendation."


def test_a_filter_on_steady_profit_keeps_the_companies_that_meet_it(tmp_path: Path) -> None:
    result = screen(_found(tmp_path), Filters(min_profitable_quarters=8), "symbol", "asc", 100)
    assert _symbols(result) == ["AAA", "CCC"]
    # BBB has 5 of 8 (fails the filter); DDD holds only three quarters (no figure to filter on).
    assert result["excluded_by_filters"] == 1 and result["excluded_missing_data"] == 1


def test_a_company_with_no_figure_to_filter_on_is_excluded_for_missing_data_not_for_failing(
    tmp_path: Path,
) -> None:
    result = screen(_found(tmp_path), Filters(min_roe_pct=Decimal(15)), "symbol", "asc", 100)
    assert _symbols(result) == ["AAA"]
    assert result["excluded_missing_data"] == 2 and result["excluded_by_filters"] == 1
    assert result["missing_by_filter"] == {"min_roe_pct": 2}


def test_filters_combine_and_each_one_is_listed_in_plain_words(tmp_path: Path) -> None:
    filters = Filters(
        min_roe_pct=Decimal(5), max_debt_to_equity=Decimal("0.12"), min_interest_cover=Decimal(3)
    )
    result = screen(_found(tmp_path), filters, "symbol", "asc", 100)
    assert _symbols(result) == ["AAA"]
    applied = {item["filter"]: item["plain"] for item in result["filters_applied"]}  # type: ignore[attr-defined]
    assert applied["max_debt_to_equity"] == "Borrowings of at most 0.12 times the owners' money"
    assert applied["min_roe_pct"] == "Profit of at least 5% of the owners' money (approximate)"
    assert applied["min_interest_cover"] == "Profit covers the interest bill at least 3 times"


def test_a_price_filter_uses_the_platform_close_and_drops_stocks_with_no_earnings_or_no_price(
    tmp_path: Path,
) -> None:
    result = screen(_found(tmp_path), Filters(max_pe=Decimal(90)), "symbol", "asc", 100)
    # AAA: 800 / 10.2 = 78.4 (kept). CCC: 100 / 10.2 = 9.8 (kept). BBB and DDD have no price here.
    assert _symbols(result) == ["AAA", "CCC"]


def test_growth_filter_uses_profit_over_four_quarters_against_the_four_before(
    tmp_path: Path,
) -> None:
    result = screen(
        _found(tmp_path), Filters(min_ttm_profit_growth_pct=Decimal(80)), "symbol", "asc", 100
    )
    assert _symbols(result) == ["AAA", "CCC"]  # 102 against 54 is +88.9%
    none = screen(
        _found(tmp_path), Filters(min_ttm_profit_growth_pct=Decimal(90)), "symbol", "asc", 100
    )
    assert _symbols(none) == []


def test_the_industry_filter_matches_part_of_a_name_without_regard_to_case(tmp_path: Path) -> None:
    result = screen(_found(tmp_path), Filters(sector="information tech"), "symbol", "asc", 100)
    assert _symbols(result) == ["AAA", "CCC"]
    assert result["excluded_missing_data"] == 1  # DDD has no industry group on record


def test_results_are_sorted_by_the_field_the_caller_names_with_missing_values_last(
    tmp_path: Path,
) -> None:
    up = screen(_found(tmp_path), Filters(), "roe_pct", "asc", 100)
    assert _symbols(up) == ["CCC", "AAA", "BBB", "DDD"]
    down = screen(_found(tmp_path), Filters(), "roe_pct", "desc", 100)
    assert _symbols(down) == ["AAA", "CCC", "BBB", "DDD"]


def test_the_list_is_cut_at_the_limit_but_the_match_count_is_the_whole(tmp_path: Path) -> None:
    result = screen(_found(tmp_path), Filters(), "symbol", "asc", 2)
    assert _symbols(result) == ["AAA", "BBB"] and result["matched"] == 4 and result["returned"] == 2


def test_each_result_carries_its_dates_and_how_old_its_data_is(tmp_path: Path) -> None:
    row = screen(_found(tmp_path), Filters(), "symbol", "asc", 1)["results"][0]  # type: ignore[index]
    assert row["latest_quarter"] == "2024-12-31" and row["data_status"] == "VERIFIED_FILING"
    assert row["scorecard_counts"]["OK"] >= 1 and row["roe_pct"] == 25.5


def test_the_response_states_the_data_dates(tmp_path: Path) -> None:
    dates = screen(_found(tmp_path), Filters(), "symbol", "asc", 100)["data_dates"]  # type: ignore[index]
    assert dates["newest_filing"] == "2024-12-31" and dates["oldest_latest_quarter"] == "2024-12-31"


def test_no_word_of_advice_appears_anywhere_in_a_screen_response(tmp_path: Path) -> None:
    filters = Filters(
        min_roe_pct=Decimal(5), max_pe=Decimal(90), sector="tech", min_profitable_quarters=6
    )
    answer = screen(_found(tmp_path), filters, "pe", "asc", 100)
    # The one required sentence says "not a recommendation"; it is a denial, so it is checked on its own below.
    text = json.dumps({key: value for key, value in answer.items() if key != "statement"})
    assert (
        ADVICE.search(text) is None
        and answer["statement"] == "These are filters you chose, not a recommendation."
    )
