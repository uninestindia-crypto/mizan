"""Reading what Upstox sends: exact numbers, strict rows, and nothing kept that is not shown."""

from __future__ import annotations

import json
from decimal import Decimal
from typing import Any

import pytest

from quant_system.broker_view.upstox_parse import (
    ReplyUnreadable,
    load_reply,
    parse_funds,
    parse_holdings,
    parse_positions,
)
from tests.broker_fakes import holding, position, success


def body(data: Any) -> bytes:
    return success(data).body


def test_a_holding_is_read_with_exact_decimals_and_only_the_fields_that_are_shown() -> None:
    parsed = parse_holdings(body([holding()]))
    row = parsed.rows[0]
    assert parsed.skipped == 0
    assert (row.symbol, row.exchange, row.isin) == ("TCS", "NSE", "INE467B01029")
    assert (row.quantity, row.t1_quantity) == (10, 0)
    assert row.average_price == Decimal("3400.0")
    assert row.last_price == Decimal("3500.5")
    assert row.close_price == Decimal("3480.0")
    fields = set(row.__slots__)
    assert not fields & {
        "company_name",
        "instrument_token",
        "product",
        "haircut",
        "collateral_quantity",
    }


def test_the_broker_name_for_the_symbol_is_read_from_either_spelling() -> None:
    row = {k: v for k, v in holding().items() if k != "trading_symbol"} | {"tradingsymbol": "tcs"}
    assert parse_holdings(body([row])).rows[0].symbol == "TCS"


def test_our_own_sums_are_exact_not_floating_point() -> None:
    row = parse_holdings(body([holding(quantity=3, average_price=0.1, last_price=0.3)])).rows[0]
    assert row.invested == Decimal("0.3")
    assert row.value == Decimal("0.9")
    assert row.pnl == Decimal("0.6")


@pytest.mark.parametrize(
    "bad",
    [
        {"quantity": 2.5},
        {"quantity": -1},
        {"quantity": True},
        {"quantity": "10"},
        {"quantity": None},
        {"average_price": -1},
        {"average_price": "3400"},
        {"last_price": 0},
        {"last_price": 1e30},
        {"trading_symbol": "tcs; drop"},
        {"trading_symbol": ""},
        {"trading_symbol": 7},
        {"exchange": "NSE<script>"},
    ],
)
def test_a_row_that_fails_any_check_is_skipped_and_counted_never_guessed(
    bad: dict[str, Any],
) -> None:
    parsed = parse_holdings(body([holding(**bad), holding("INFY")]))
    assert [r.symbol for r in parsed.rows] == ["INFY"]
    assert parsed.skipped == 1


def test_a_row_that_is_not_an_object_is_skipped() -> None:
    parsed = parse_holdings(body([1, "x", None, holding()]))
    assert len(parsed.rows) == 1 and parsed.skipped == 3


def test_an_isin_that_is_not_one_is_dropped_but_the_row_is_kept() -> None:
    row = parse_holdings(body([holding(isin="not an isin")])).rows[0]
    assert row.isin is None


def test_a_missing_close_price_is_allowed_and_means_no_move_for_today() -> None:
    row = parse_holdings(body([holding(close_price=None)])).rows[0]
    assert row.close_price is None and row.today is None


def test_recently_bought_shares_are_kept_apart_from_the_ones_in_the_demat() -> None:
    row = parse_holdings(body([holding(quantity=0, t1_quantity=4)])).rows[0]
    assert (row.quantity, row.t1_quantity, row.value) == (0, 4, Decimal(0))
    assert row.arriving_value == Decimal("14002.0")


@pytest.mark.parametrize(
    "raw",
    [
        b"",
        b"not json",
        b"[]",
        b"null",
        b'{"status": "error", "data": []}',
        b'{"data": []}',
        b'{"status": "success", "data": {"not": "a list"}}',
        b'{"status": "success", "data": [NaN]}',
        b'{"status": "success", "data": [{"quantity": Infinity}]}',
    ],
)
def test_a_reply_that_is_not_a_success_with_a_list_is_unreadable_as_a_whole(raw: bytes) -> None:
    with pytest.raises(ReplyUnreadable):
        parse_holdings(raw)


def test_a_very_deeply_nested_reply_is_unreadable_not_a_crash() -> None:
    with pytest.raises(ReplyUnreadable):
        load_reply(b"[" * 100000)


def test_a_position_is_read_with_its_product_in_words() -> None:
    rows = parse_positions(
        body(
            [
                position(product="I"),
                position("A", product="D"),
                position("B", product="MTF"),
                position("C", product="X"),
            ]
        )
    ).rows
    assert [r.product for r in rows] == ["Intraday", "Delivery", "Margin trading", "Other"]


def test_a_position_keeps_its_sign_and_a_squared_off_one_is_still_listed() -> None:
    parsed = parse_positions(body([position(quantity=-5), position("B", quantity=0)]))
    assert [r.quantity for r in parsed.rows] == [-5, 0]


def test_a_position_with_symbol_containing_spaces_is_accepted_and_a_bad_one_is_skipped() -> None:
    parsed = parse_positions(body([position("NIFTY 25000 CE 28 OCT"), position("bad;symbol")]))
    assert [r.symbol for r in parsed.rows] == ["NIFTY 25000 CE 28 OCT"]
    assert parsed.skipped == 1


def test_an_odd_optional_figure_on_a_position_becomes_missing_not_a_skipped_row() -> None:
    row = parse_positions(body([position(pnl="x", realised=None)])).rows[0]
    assert row.pnl is None and row.realised is None and row.unrealised == Decimal("50.0")


def test_cash_is_read_from_the_equity_block_or_from_the_top_level() -> None:
    nested = parse_funds(body({"equity": {"available_margin": 12000.5, "used_margin": 3000}}))
    flat = parse_funds(body({"available_margin": 12000.5, "used_margin": 3000}))
    assert nested == flat
    assert (nested.available, nested.in_use) == (Decimal("12000.5"), Decimal(3000))


@pytest.mark.parametrize("data", [{}, [], None, {"equity": {}}, {"available_margin": "lots"}])
def test_cash_with_nothing_readable_is_unreadable(data: Any) -> None:
    with pytest.raises(ReplyUnreadable):
        parse_funds(body(data))


def test_a_huge_number_is_refused_rather_than_carried_into_the_sums() -> None:
    raw = json.dumps({"status": "success", "data": [holding()]}).replace("3500.5", "1e400").encode()
    parsed = parse_holdings(raw)
    assert parsed.rows == () and parsed.skipped == 1
