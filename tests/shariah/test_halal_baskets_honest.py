"""Baskets show what is known (names, weights, screening, sample prices) and no invented performance or history."""

import json
import sqlite3
from pathlib import Path
from typing import Any

import aiosqlite
import pytest
import pytest_asyncio
from httpx import AsyncClient

from quant_system.shariah.schemas.basket import BasketExportRequest
from quant_system.shariah.services.basket_service import (
    BASKET_DEFINITIONS,
    get_all_baskets,
    get_basket_by_id,
)
from quant_system.shariah.services.broker_export_service import export_basket_orders

BASKET_IDS = [
    "halal-tech-giants",
    "shariah-high-growth-champions",
    "green-ethical-infrastructure",
    "nifty-shariah-25",
]
SUMMARY_PERFORMANCE_KEYS = [
    "expected_cagr",
    "expected_sharpe",
    "cagr",
    "sharpe_ratio",
    "annualized_volatility",
    "max_drawdown",
]
TEAR_SHEET_KEYS = [*SUMMARY_PERFORMANCE_KEYS, "beta", "risk_free_rate"]
PERFORMANCE_KEYS = set(TEAR_SHEET_KEYS)
NOT_COMPUTED = {
    "status": "NOT_COMPUTED",
    "message": "QuantOS has not back-tested this basket, so no return or risk figure is shown.",
}


def numeric_performance_values(node: Any) -> list[tuple[str, Any]]:
    """Every number found under a performance field name, anywhere in a response."""
    if isinstance(node, dict):
        here = [
            (k, v) for k, v in node.items() if k in PERFORMANCE_KEYS and isinstance(v, (int, float))
        ]
        return here + [
            found for value in node.values() for found in numeric_performance_values(value)
        ]
    if isinstance(node, list):
        return [found for item in node for found in numeric_performance_values(item)]
    return []


def fixture_company(sample_companies: list[dict[str, Any]], ticker: str) -> dict[str, Any]:
    return next(row for row in sample_companies if row["ticker"] == ticker)


def shown_and_stored_screening(
    body: dict[str, Any], sample_companies: list[dict[str, Any]]
) -> tuple[list[tuple[str, str, str, str]], list[tuple[str, str, str, str]]]:
    """What a basket shows for each stock, and what the sample row stores for it."""
    by_ticker = {row["ticker"]: row for row in sample_companies}
    shown = [
        (c["ticker"], c["aaoifi_status"], c["tasis_status"], c["data_status"])
        for c in body["constituents"]
    ]
    stored = [
        (
            c["ticker"],
            by_ticker[c["ticker"]]["aaoifi_status"],
            by_ticker[c["ticker"]]["tasis_status"],
            "UNVERIFIED_SAMPLE",
        )
        for c in body["constituents"]
    ]
    return shown, stored


def weights_and_sample_prices(
    body: dict[str, Any], sample_companies: list[dict[str, Any]]
) -> list[tuple[float, float]]:
    by_ticker = {row["ticker"]: row for row in sample_companies}
    return [(c["weight"], by_ticker[c["ticker"]]["current_price"]) for c in body["constituents"]]


@pytest_asyncio.fixture
async def db_without_kec(tmp_path: Path, test_db_path: str) -> Any:
    """A copy of the test database in which one basket stock is not in the sample."""
    copy = tmp_path / "without_kec.db"
    source = sqlite3.connect(test_db_path)
    target = sqlite3.connect(copy)
    source.backup(target)
    target.execute("DELETE FROM companies WHERE ticker = 'KEC.NS'")
    target.commit()
    source.close()
    target.close()
    async with aiosqlite.connect(copy) as conn:
        conn.row_factory = aiosqlite.Row
        yield conn


@pytest.mark.asyncio
async def test_no_numeric_performance_field_is_left_in_the_basket_list(client: AsyncClient) -> None:
    body = (await client.get("/api/v1/baskets")).json()

    assert numeric_performance_values(body) == []


@pytest.mark.parametrize("basket_id", BASKET_IDS)
@pytest.mark.asyncio
async def test_no_numeric_performance_field_is_left_in_a_basket_detail(
    client: AsyncClient, basket_id: str
) -> None:
    body = (await client.get(f"/api/v1/baskets/{basket_id}")).json()

    assert numeric_performance_values(body) == []


@pytest.mark.parametrize("key", SUMMARY_PERFORMANCE_KEYS)
@pytest.mark.asyncio
async def test_each_performance_field_in_the_list_is_present_and_empty(
    client: AsyncClient, key: str
) -> None:
    body = (await client.get("/api/v1/baskets")).json()

    assert [basket[key] for basket in body] == [None, None, None, None]


@pytest.mark.parametrize("key", TEAR_SHEET_KEYS)
@pytest.mark.asyncio
async def test_each_performance_field_in_a_tear_sheet_is_present_and_empty(
    client: AsyncClient, key: str
) -> None:
    body = (await client.get("/api/v1/baskets/halal-tech-giants")).json()

    assert body["tear_sheet"][key] is None


@pytest.mark.asyncio
async def test_the_basket_says_in_words_that_performance_is_not_computed(
    client: AsyncClient,
) -> None:
    listed = (await client.get("/api/v1/baskets")).json()
    detail = (await client.get("/api/v1/baskets/nifty-shariah-25")).json()

    assert [basket["performance"] for basket in listed] == [NOT_COMPUTED] * 4
    assert detail["performance"] == NOT_COMPUTED
    assert detail["tear_sheet"]["performance"] == NOT_COMPUTED


@pytest.mark.parametrize("basket_id", BASKET_IDS)
@pytest.mark.asyncio
async def test_no_rebalance_is_claimed_that_nobody_recorded(
    client: AsyncClient, basket_id: str
) -> None:
    body = (await client.get(f"/api/v1/baskets/{basket_id}")).json()

    assert body["rebalance_history"] == []
    assert body["rebalance_logs"] == []
    assert body["history_status"] == "NONE_RECORDED"
    assert body["history_message"] == "No rebalances have been recorded yet."


@pytest.mark.parametrize(
    "phrase",
    [
        "Verified full AAOIFI",
        "Quarterly Rebalancing",
        "Semi-Annual",
        "Annual Compliance Audit",
        "titanship",
        "2026-09-30",
        "2026-06-30",
        "2026-03-31",
    ],
)
@pytest.mark.parametrize("basket_id", BASKET_IDS)
@pytest.mark.asyncio
async def test_the_written_rebalance_entries_are_gone(
    client: AsyncClient, basket_id: str, phrase: str
) -> None:
    text = (await client.get(f"/api/v1/baskets/{basket_id}")).text

    assert phrase not in text


@pytest.mark.parametrize("key", ["expected_cagr", "expected_sharpe", "max_drawdown", "beta"])
def test_the_typed_performance_constants_are_gone_from_the_definitions(key: str) -> None:
    assert [basket for basket in BASKET_DEFINITIONS if key in basket] == []


@pytest.mark.parametrize("key", ["rebalance_logs", "default_price"])
def test_the_typed_history_and_prices_are_gone_from_the_definitions(key: str) -> None:
    as_text = json.dumps(BASKET_DEFINITIONS)

    assert f'"{key}"' not in as_text


@pytest.mark.parametrize("basket_id", BASKET_IDS)
@pytest.mark.asyncio
async def test_a_basket_still_lists_its_constituents_and_weights(
    client: AsyncClient, oracle: Any, basket_id: str
) -> None:
    expected = next(b for b in oracle.get_thematic_baskets() if b["id"] == basket_id)

    body = (await client.get(f"/api/v1/baskets/{basket_id}")).json()

    assert [(c["ticker"], c["weight"]) for c in body["constituents"]] == [
        (c["ticker"], c["weight"]) for c in expected["constituents"]
    ]
    assert body["constituent_count"] == len(expected["constituents"])


@pytest.mark.parametrize("basket_id", BASKET_IDS)
@pytest.mark.asyncio
async def test_a_basket_still_shows_each_stocks_screened_status_and_how_sure_it_is(
    client: AsyncClient, sample_companies: list[dict[str, Any]], basket_id: str
) -> None:
    body = (await client.get(f"/api/v1/baskets/{basket_id}")).json()

    shown, stored = shown_and_stored_screening(body, sample_companies)

    assert shown == stored


@pytest.mark.asyncio
async def test_a_price_from_the_sample_is_shown_and_labelled_as_a_sample(
    client: AsyncClient, sample_companies: list[dict[str, Any]]
) -> None:
    body = (await client.get("/api/v1/baskets/halal-tech-giants")).json()

    tcs = next(c for c in body["constituents"] if c["ticker"] == "TCS.NS")
    sample = fixture_company(sample_companies, "TCS.NS")
    assert (tcs["current_price"], tcs["market_cap"], tcs["price_status"]) == (
        sample["current_price"],
        sample["market_cap"],
        "SAMPLE",
    )


@pytest.mark.parametrize("basket_id", BASKET_IDS)
@pytest.mark.asyncio
async def test_without_the_sample_there_is_no_price_and_no_screened_status(basket_id: str) -> None:
    detail = await get_basket_by_id(basket_id, None)

    assert detail is not None
    assert {(c.current_price, c.market_cap, c.price_status) for c in detail.constituents} == {
        (None, None, "NOT_AVAILABLE")
    }
    assert {(c.aaoifi_status, c.tasis_status, c.data_status) for c in detail.constituents} == {
        (None, None, None)
    }


@pytest.mark.parametrize("typed_price", ["4210.5", "1890.2", "5890", "7650"])
@pytest.mark.asyncio
async def test_the_prices_that_were_typed_into_the_code_are_not_served(typed_price: str) -> None:
    listed = await get_all_baskets(None)

    assert typed_price not in json.dumps([basket.model_dump() for basket in listed])


@pytest.mark.asyncio
async def test_a_stock_missing_from_the_sample_has_no_price_and_blanks_the_totals(
    db_without_kec: aiosqlite.Connection,
) -> None:
    detail = await get_basket_by_id("green-ethical-infrastructure", db_without_kec)

    assert detail is not None
    kec = next(c for c in detail.constituents if c.ticker == "KEC.NS")
    assert (kec.current_price, kec.price_status, kec.aaoifi_status) == (None, "NOT_AVAILABLE", None)
    assert (detail.minimum_investment, detail.latest_valuation) == (None, None)
    assert (detail.dividend_yield, detail.weighted_purification_ratio) == (None, None)


@pytest.mark.asyncio
async def test_yield_and_purification_are_the_weighted_figures_from_the_screening_rows(
    client: AsyncClient, sample_companies: list[dict[str, Any]]
) -> None:
    body = (await client.get("/api/v1/baskets/halal-tech-giants")).json()

    rows = [
        (c["weight"], fixture_company(sample_companies, c["ticker"])) for c in body["constituents"]
    ]
    total_weight = sum(weight for weight, _ in rows)
    assert body["dividend_yield"] == pytest.approx(
        sum(weight * row["dividend_yield"] for weight, row in rows) / total_weight
    )
    assert body["weighted_purification_ratio"] == pytest.approx(
        sum(weight * row["purification_ratio"] for weight, row in rows) / total_weight
    )
    assert body["tear_sheet"]["dividend_yield"] == body["dividend_yield"]


@pytest.mark.asyncio
async def test_yield_and_purification_are_empty_when_there_are_no_screening_rows() -> None:
    detail = await get_basket_by_id("halal-tech-giants", None)

    assert detail is not None
    assert (detail.dividend_yield, detail.weighted_purification_ratio) == (None, None)
    assert (detail.minimum_investment, detail.latest_valuation) == (None, None)


@pytest.mark.asyncio
async def test_the_sample_value_of_one_share_each_is_the_sum_of_the_sample_prices(
    client: AsyncClient, sample_companies: list[dict[str, Any]]
) -> None:
    body = (await client.get("/api/v1/baskets/halal-tech-giants")).json()

    prices = weights_and_sample_prices(body, sample_companies)
    assert body["minimum_investment"] == pytest.approx(sum(price for _, price in prices), abs=0.01)
    assert body["latest_valuation"] == pytest.approx(
        sum(w * price for w, price in prices), abs=0.01
    )


@pytest.mark.asyncio
async def test_an_order_sheet_is_refused_when_a_share_has_no_price() -> None:
    with pytest.raises(ValueError, match="no price") as refusal:
        await export_basket_orders("halal-tech-giants", BasketExportRequest(), None)

    assert "TCS" in str(refusal.value)


@pytest.mark.asyncio
async def test_an_order_sheet_built_on_sample_prices_says_so_and_that_nothing_is_placed(
    client: AsyncClient,
) -> None:
    response = await client.post(
        "/api/v1/baskets/halal-tech-giants/export", json={"capital": 50000}
    )

    body = response.json()
    joined = " ".join(body["warnings"])
    assert response.status_code == 200
    assert body["order_count"] == 5
    assert "sample prices" in joined
    assert "does not place orders" in joined


@pytest.mark.asyncio
async def test_an_order_sheet_names_the_stock_that_has_no_price(
    db_without_kec: aiosqlite.Connection,
) -> None:
    with pytest.raises(ValueError, match="KEC"):
        await export_basket_orders(
            "green-ethical-infrastructure", BasketExportRequest(), db_without_kec
        )


@pytest.mark.asyncio
async def test_the_tax_calculator_no_longer_invents_a_purification_ratio(
    client: AsyncClient,
) -> None:
    response = await client.post(
        "/api/v1/baskets/tax-calculator", json={"investment_amount": 100000.0}
    )

    assert response.status_code == 200
    assert response.json()["estimated_dividend_purification_ratio"] is None
