"""Holding periods as facts: the 12-month date, how long a lot has been held, and no tax figures at all."""

from __future__ import annotations

import json
import re
from datetime import date

import pytest

from quant_system.server.v2.holding_periods import (
    HOLDING_PERIOD_NOTE,
    holding_period,
    twelve_months_after,
)
from quant_system.server.v2.portfolio_accounts import positions


@pytest.mark.parametrize(
    ("bought", "expected"),
    [
        (date(2024, 3, 10), date(2025, 3, 10)),
        (date(2023, 12, 31), date(2024, 12, 31)),
        (date(2024, 2, 29), date(2025, 2, 28)),
        (date(2023, 2, 28), date(2024, 2, 28)),
    ],
)
def test_the_twelve_month_date_is_the_same_day_a_year_on_and_28_february_for_a_leap_day(
    bought: date, expected: date
) -> None:
    assert twelve_months_after(bought) == expected


def test_a_lot_is_long_term_only_after_its_twelve_month_date() -> None:
    on_the_day = holding_period("2024-03-10", date(2025, 3, 10))
    next_day = holding_period("2024-03-10", date(2025, 3, 11))
    assert on_the_day is not None and on_the_day["is_long_term"] is False
    assert next_day is not None and next_day["is_long_term"] is True


def test_the_leap_day_edge_is_decided_one_way_and_stated() -> None:
    # Bought 29 Feb 2024: the 12-month date is 28 Feb 2025; 28 Feb 2025 is not yet past it, 1 Mar 2025 is.
    assert holding_period("2024-02-29", date(2025, 2, 28))["is_long_term"] is False  # type: ignore[index]
    assert holding_period("2024-02-29", date(2025, 3, 1))["is_long_term"] is True  # type: ignore[index]
    assert holding_period("2024-02-29", date(2025, 3, 1))["long_term_on"] == "2025-02-28"  # type: ignore[index]


def test_days_held_counts_calendar_days_and_never_goes_below_zero() -> None:
    assert holding_period("2024-01-01", date(2024, 1, 31))["days_held"] == 30  # type: ignore[index]
    assert holding_period("2024-02-01", date(2024, 1, 1))["days_held"] == 0  # type: ignore[index]


def test_an_unreadable_date_gives_no_lot_rather_than_a_guess() -> None:
    assert holding_period("not a date", date(2025, 1, 1)) is None


def test_the_note_says_these_are_facts_and_points_to_current_rules() -> None:
    assert (
        HOLDING_PERIOD_NOTE
        == "Holding periods are shown as facts. Check current tax rules or ask an adviser."
    )


def test_no_tax_rate_or_amount_appears_anywhere_in_a_lot() -> None:
    text = json.dumps(holding_period("2024-03-10", date(2026, 10, 7))) + HOLDING_PERIOD_NOTE
    assert re.search(r"\d\s*%|tax_|rate|amount|payable|stcg|ltcg", text, re.I) is None


def _row(holding_id: int, account: int, quantity: int, bought: str) -> dict[str, object]:
    return {
        "id": holding_id,
        "account_id": account,
        "account_name": f"Account {account}",
        "symbol": "AAA",
        "name": "Alpha",
        "quantity": quantity,
        "cost": 100.0 * quantity,
        "value": 120.0 * quantity,
        "close": 120.0,
        "lot": holding_period(bought, date(2026, 10, 7)),
    }


def test_each_position_lists_its_buy_lots_across_accounts() -> None:
    rows = [_row(1, 1, 10, "2024-03-10"), _row(2, 2, 5, "2026-08-01")]
    position = positions(rows)[0]
    lots = position["lots"]
    assert [(lot["holding_id"], lot["account_id"], lot["quantity"]) for lot in lots] == [
        (1, 1, 10),
        (2, 2, 5),
    ]
    assert [lot["is_long_term"] for lot in lots] == [True, False]
    assert lots[0]["account_name"] == "Account 1" and lots[0]["long_term_on"] == "2025-03-10"
    assert position["lots_note"] == HOLDING_PERIOD_NOTE


def test_lots_are_in_buy_date_order_oldest_first() -> None:
    rows = [_row(1, 1, 10, "2026-08-01"), _row(2, 1, 5, "2024-03-10")]
    assert [lot["holding_id"] for lot in positions(rows)[0]["lots"]] == [2, 1]
