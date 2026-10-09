"""The 36-month average market value, on small price series whose answers can be checked by hand."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import numpy as np
import pytest

from quant_system.shariah.services.proof_market import (
    MAX_LEADING_GAP_DAYS,
    MAX_PRICE_AGE_DAYS,
    average_market_value,
    months_before,
)
from tests.shariah.proof_service_fixtures import Prices, three_prices

TODAY = date(2025, 1, 7)


def test_the_value_is_the_average_close_times_the_filed_shares_in_crore() -> None:
    result = average_market_value("TCS", three_prices(), 3_620_000_000, TODAY)
    assert result.reason is None and result.value is not None
    assert result.value.average_cr == Decimal(
        "72400"
    )  # 200 average close x 3.62 billion shares = Rs 72,400 crore
    assert result.value.shares_in_issue == 3_620_000_000


def test_the_label_says_which_prices_and_how_many_shares_it_used() -> None:
    result = average_market_value("TCS", three_prices(), 3_620_000_000, TODAY)
    assert result.value is not None
    assert result.value.label == (
        "Average close of ₹200.00 from 10 Jan 2022 to 6 Jan 2025 (3 trading days), "
        "times 3,62,00,00,000 shares"
    )


def test_prices_before_the_window_are_left_out() -> None:
    old = Prices(
        ["2020-01-01", *three_prices().dates],
        np.array([9_999.0, 100.0, 200.0, 300.0], dtype=np.float64),
    )
    result = average_market_value("TCS", old, 1_000_000, TODAY)
    assert result.value is not None and result.value.average_cr == Decimal(
        "20"
    )  # 200 x 10 lakh shares = Rs 20 crore


def test_a_bad_closing_price_is_skipped_not_counted_as_zero() -> None:
    prices = Prices(
        ["2022-01-10", "2022-06-01", "2023-07-03", "2025-01-06"],
        np.array([100.0, float("nan"), -5.0, 300.0], dtype=np.float64),
    )
    result = average_market_value("TCS", prices, 1_000_000, TODAY)
    assert result.value is not None and result.value.average_cr == Decimal(
        "20"
    )  # (100 + 300) / 2 = 200, times 10 lakh shares


def test_a_missing_share_count_gives_a_reason_and_no_value() -> None:
    result = average_market_value("TCS", three_prices(), None, TODAY)
    assert result.value is None and "share count" in (result.reason or "")


def test_no_price_history_gives_a_reason_and_no_value() -> None:
    result = average_market_value("TCS", None, 1_000_000, TODAY)
    assert result.value is None and "no price history for TCS" in (result.reason or "")


def test_a_history_shorter_than_the_window_is_refused_and_says_where_it_starts() -> None:
    short = Prices(["2023-06-01", "2025-01-06"], np.array([100.0, 300.0], dtype=np.float64))
    result = average_market_value("TCS", short, 1_000_000, TODAY)
    assert result.value is None
    assert "only from 1 Jun 2023" in (result.reason or "") and "36 months" in (result.reason or "")


def test_prices_that_stop_long_ago_are_refused_as_too_old() -> None:
    result = average_market_value("TCS", three_prices(), 1_000_000, date(2026, 10, 7))
    assert result.value is None and "too old" in (result.reason or "")


@pytest.mark.parametrize(
    ("first_day", "accepted"),
    [("2022-01-06", True), ("2022-02-20", True), ("2022-02-21", False)],
)
def test_the_first_price_may_be_a_few_weeks_after_the_window_opens(
    first_day: str, accepted: bool
) -> None:
    assert MAX_LEADING_GAP_DAYS == 45  # 2022-01-06 + 45 days is 2022-02-20
    prices = Prices([first_day, "2025-01-06"], np.array([100.0, 100.0], dtype=np.float64))
    assert (average_market_value("TCS", prices, 1_000_000, TODAY).value is not None) is accepted


def test_the_newest_price_may_be_up_to_a_year_old_and_no_older() -> None:
    assert MAX_PRICE_AGE_DAYS == 366
    prices = Prices(["2021-01-05", "2024-01-05"], np.array([100.0, 100.0], dtype=np.float64))
    assert average_market_value("TCS", prices, 1_000_000, date(2025, 1, 5)).value is not None
    assert average_market_value("TCS", prices, 1_000_000, date(2025, 1, 7)).value is None


def test_prices_dated_after_today_are_never_used() -> None:
    future = Prices(
        [*three_prices().dates, "2025-06-01"],
        np.array([100.0, 200.0, 300.0, 9_000.0], dtype=np.float64),
    )
    result = average_market_value("TCS", future, 1_000_000, TODAY)
    assert result.value is not None and result.value.average_cr == Decimal("20")


@pytest.mark.parametrize(
    ("day", "months", "expected"),
    [
        (date(2025, 1, 6), 36, date(2022, 1, 6)),
        (date(2024, 2, 29), 12, date(2023, 2, 28)),
        (date(2025, 3, 31), 1, date(2025, 2, 28)),
    ],
)
def test_months_before_clamps_to_the_end_of_a_shorter_month(
    day: date, months: int, expected: date
) -> None:
    assert months_before(day, months) == expected
