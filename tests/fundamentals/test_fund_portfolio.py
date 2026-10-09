"""Fundamentals across a portfolio: weights, sectors, a weighted P/E that is a harmonic mean, and who has no data."""

from __future__ import annotations

import json
import re
from dataclasses import replace
from datetime import date
from decimal import Decimal
from pathlib import Path

from quant_system.fundamentals.metric_types import PriceQuote
from quant_system.fundamentals.models import QuarterFigures
from quant_system.fundamentals.portfolio_view import portfolio_fundamentals
from quant_system.fundamentals.service import CompanyAnalysis, FundamentalsService
from quant_system.fundamentals.store import FundamentalsStore
from tests.fundamentals.support import balance, cr, quarter, quarter_ends, with_balance

ADVICE = re.compile(
    r"\b(buy|sell|best|undervalued|overvalued|target|cheap|expensive|should)\b", re.I
)
TODAY = date(2025, 3, 1)


def _rows(symbol: str, profit_step: int = 3) -> list[QuarterFigures]:
    ends = quarter_ends(8)
    items = [
        quarter(
            e,
            cr(100 + 10 * i),
            cr(profit_step * (i + 3)),
            cr(2),
            str(Decimal(profit_step * (i + 3)) / 10),
            shares=10_000_000,
        )
        for i, e in enumerate(ends)
    ]
    items[6] = with_balance(items[6], balance(ends[6], cr(400), (cr(30), cr(10))))
    return [replace(item, symbol=symbol, company_name=f"{symbol} Limited") for item in items]


def _analyses(tmp_path: Path, prices: dict[str, str]) -> dict[str, CompanyAnalysis]:
    store = FundamentalsStore(None, tmp_path / "p.sqlite")
    for symbol in ("AAA", "BBB", "CCC", "EEE"):
        store.put(_rows(symbol))
    store.put_industry(
        {"AAA": "Information Technology", "BBB": "Metals", "CCC": "Information Technology"},
        "2025-01-01",
    )
    service = FundamentalsService(store, lambda: TODAY)
    quotes = {s: PriceQuote(Decimal(p), date(2025, 2, 28)) for s, p in prices.items()}
    symbols = ["AAA", "BBB", "CCC", "EEE", "NODATA", "XXX"]
    return {s: service.analyse(s, quotes.get(s)) for s in symbols}


def _position(symbol: str, weight: float, **extra: object) -> dict[str, object]:
    return {
        "symbol": symbol,
        "name": f"{symbol} Limited",
        "weight": weight,
        "value": weight * 1_000_000,
        **extra,
    }


def _positions_weighing(weights: list[float]) -> list[dict[str, object]]:
    names = ["AAA", "BBB", "CCC", "EEE", "NODATA", "XXX"]
    return [_position(s, w) for s, w in zip(names, weights, strict=True)]


def _view(
    tmp_path: Path, positions: list[dict[str, object]], prices: dict[str, str] | None = None
) -> dict[str, object]:
    # TTM earnings per share is 10.2 for every company here, so a price of 102 is a P/E of 10 and 306 is 30.
    found = _analyses(tmp_path, prices or {"AAA": "102", "BBB": "306", "CCC": "102"})
    return portfolio_fundamentals(positions, found, {"account": "all", "name": "All accounts"})


def test_the_weighted_average_pe_is_a_harmonic_mean_on_holdings_that_have_earnings(
    tmp_path: Path,
) -> None:
    # AAA weight 0.5 at 10 times, BBB weight 0.3 at 30 times: 0.8 / (0.5 / 10 + 0.3 / 30) = 13.33, not the plain 18.75.
    view = _view(tmp_path, [_position("AAA", 0.5), _position("BBB", 0.3), _position("NODATA", 0.2)])
    average = view["weighted_average_pe"]
    assert round(average["value"], 2) == 13.33 and average["method"] == "harmonic mean"  # type: ignore[index]
    assert average["holdings_included"] == 2 and average["weight_included_pct"] == 80.0  # type: ignore[index]


def test_the_top_five_weight_is_the_share_of_the_five_largest_positions(tmp_path: Path) -> None:
    weights = [0.30, 0.25, 0.15, 0.12, 0.10, 0.08]
    view = _view(tmp_path, _positions_weighing(weights))
    assert view["holdings_count"] == 6 and view["top5_weight_pct"] == 92.0


def test_weight_by_industry_group_adds_up_and_names_what_is_not_known(tmp_path: Path) -> None:
    view = _view(
        tmp_path,
        [
            _position("AAA", 0.5),
            _position("BBB", 0.3),
            _position("CCC", 0.1),
            _position("EEE", 0.1),
        ],
    )
    sectors = {row["sector"]: row["weight_pct"] for row in view["sector_weights"]}  # type: ignore[attr-defined]
    assert sectors == {"Information Technology": 60.0, "Metals": 30.0, "Industry not known": 10.0}
    assert view["sector_weights"][0]["sector"] == "Information Technology"  # type: ignore[index]


def test_holdings_with_no_data_are_counted_and_named(tmp_path: Path) -> None:
    view = _view(tmp_path, [_position("AAA", 0.8), _position("NODATA", 0.2)])
    assert view["without_data_count"] == 1 and view["without_data"] == ["NODATA"]
    row = next(h for h in view["holdings"] if h["symbol"] == "NODATA")  # type: ignore[attr-defined]
    assert row["data_status"] == "NOT_AVAILABLE" and row["scorecard_counts"]["OK"] == 0


def test_each_holding_has_its_headline_figures_and_scorecard_counts(tmp_path: Path) -> None:
    view = _view(tmp_path, [_position("AAA", 1.0)])
    row = view["holdings"][0]  # type: ignore[index]
    assert row["roe_pct"] == 25.5 and row["debt_to_equity"] == 0.1 and row["pe"] == 10.0
    assert row["profitable_quarters"] == 8 and row["weight_pct"] == 100.0
    assert set(row["scorecard_counts"]) == {"OK", "WATCH", "INFO", "NOT_AVAILABLE"}
    assert row["industry"] == "Information Technology" and row["latest_quarter"] == "2024-12-31"


def test_a_holding_without_a_price_value_has_no_weight_and_stays_out_of_the_weights(
    tmp_path: Path,
) -> None:
    view = _view(
        tmp_path,
        [_position("AAA", 1.0), {"symbol": "EEE", "name": "EEE", "weight": None, "value": None}],
    )
    assert view["holdings_without_value"] == ["EEE"]
    assert view["top5_weight_pct"] == 100.0


def test_no_holdings_gives_an_empty_but_valid_answer(tmp_path: Path) -> None:
    view = _view(tmp_path, [])
    assert (
        view["holdings_count"] == 0
        and view["weighted_average_pe"]["value"] is None
        and view["holdings"] == []
    )  # type: ignore[index]


def test_the_scope_the_prices_and_the_filing_dates_are_stated_in_plain_words(
    tmp_path: Path,
) -> None:
    view = _view(tmp_path, [_position("AAA", 1.0)])
    assert view["scope"] == {"account": "all", "name": "All accounts"}
    assert "last close" in view["weights_note"] and "own filings" in view["statement"]  # type: ignore[operator]
    assert view["data_dates"]["price_date"] == "2025-02-28"  # type: ignore[index]


def test_the_view_is_plain_json_and_never_advises(tmp_path: Path) -> None:
    view = _view(tmp_path, [_position("AAA", 0.6), _position("BBB", 0.4)])
    text = json.dumps(view)
    assert ADVICE.search(text) is None and "Decimal" not in text
