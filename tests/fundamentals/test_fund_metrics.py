"""The metrics, worked on small series whose arithmetic is stated in each test so it can be checked by hand."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from quant_system.fundamentals.metric_types import Metric, PriceQuote
from quant_system.fundamentals.metrics import compute_metrics
from quant_system.fundamentals.models import QuarterFigures
from quant_system.fundamentals.series import Series, build_series
from tests.fundamentals.support import balance, cr, quarter, quarter_ends, with_balance

ENDS_8 = [
    date(2023, 3, 31), date(2023, 6, 30), date(2023, 9, 30), date(2023, 12, 31),
    date(2024, 3, 31), date(2024, 6, 30), date(2024, 9, 30), date(2024, 12, 31),
]  # fmt: skip
# Oldest to newest, in crore. Profit is a multiple of 3 so the tax (a third of profit) is a whole number.
REVENUE = [100, 110, 120, 130, 140, 150, 160, 170]
PROFIT = [9, 12, 15, 18, 21, 24, 27, 30]
EPS = ["0.9", "1.2", "1.5", "1.8", "2.1", "2.4", "2.7", "3.0"]
PRICE = PriceQuote(Decimal("800"), date(2026, 10, 6))


def _eight(
    finance: int | None = 2, profits: list[int] | None = None, shares: int = 10_000_000
) -> Series:
    profits = profits or PROFIT
    items = [
        quarter(
            end, cr(rev), cr(prof), cr(finance) if finance is not None else None, eps, shares=shares
        )
        for end, rev, prof, eps in zip(ENDS_8, REVENUE, profits, EPS, strict=True)
    ]
    return build_series(items)


def _with_more_shares_from_september() -> list[QuarterFigures]:
    """The eight quarters, with 10 per cent more shares from the quarter ended 30 Sep 2024."""
    rows = zip(ENDS_8, REVENUE, PROFIT, EPS, strict=True)
    return [
        quarter(end, cr(rev), cr(prof), cr(2), eps, shares=_shares_for(end))
        for end, rev, prof, eps in rows
    ]


def _shares_for(end: date) -> int:
    return 10_000_000 if end < date(2024, 9, 30) else 11_000_000


def _all_losses() -> list[QuarterFigures]:
    losses = [-9, -12, -15, -18, -21, -24, -27, -30]
    return [
        quarter(e, cr(100), cr(p), None, str(Decimal(p) / 10))
        for e, p in zip(ENDS_8, losses, strict=True)
    ]


def _with_sheet(series: Series, on: date = date(2024, 9, 30)) -> Series:
    """The same quarters, with a balance sheet on one of them: owners' equity 400 crore, borrowings 30 + 10 crore."""
    items = [slot.quarter for slot in series.slots if slot.quarter is not None]
    sheet = balance(on, cr(400), (cr(30), cr(10)))
    return build_series([with_balance(q, sheet) if q.period_end == on else q for q in items])


def _value(metrics: dict[str, Metric], key: str, places: int = 4) -> Decimal | None:
    found = metrics[key].value
    return None if found is None else round(found, places)


def test_sales_and_profit_over_the_last_four_quarters_are_added_up() -> None:
    # Revenue 140 + 150 + 160 + 170 = 620 crore. Profit 21 + 24 + 27 + 30 = 102 crore.
    metrics = compute_metrics(_eight(), None)
    assert metrics["ttm_revenue"].value == Decimal(cr(620))
    assert metrics["ttm_net_profit"].value == Decimal(cr(102))
    assert metrics["ttm_revenue"].as_of == date(2024, 12, 31)


def test_earnings_per_share_over_four_quarters_is_the_sum_of_the_four() -> None:
    # 2.1 + 2.4 + 2.7 + 3.0 = 10.2
    metrics = compute_metrics(_eight(), None)
    assert metrics["ttm_eps"].value == Decimal("10.2") and not metrics["ttm_eps"].approximate


def test_eps_is_called_approximate_when_the_share_count_changed() -> None:
    items = _with_more_shares_from_september()
    metric = compute_metrics(build_series(items), None)["ttm_eps"]
    assert metric.approximate and "number of shares changed" in metric.note


def test_growth_of_the_latest_quarter_is_against_the_same_quarter_a_year_earlier() -> None:
    # Sales 170 against 130: 170 / 130 - 1 = 30.7692%. Profit 30 against 18: (30 - 18) / 18 = 66.6667%.
    metrics = compute_metrics(_eight(), None)
    assert _value(metrics, "revenue_growth_quarter") == Decimal("30.7692")
    assert _value(metrics, "profit_growth_quarter") == Decimal("66.6667")


def test_growth_of_the_last_four_quarters_is_against_the_four_before_a_year_earlier() -> None:
    # Sales 620 against 100 + 110 + 120 + 130 = 460: 620 / 460 - 1 = 34.7826%.
    # Profit 102 against 9 + 12 + 15 + 18 = 54: (102 - 54) / 54 = 88.8889%.
    metrics = compute_metrics(_eight(), None)
    assert _value(metrics, "revenue_growth_ttm") == Decimal("34.7826")
    assert _value(metrics, "profit_growth_ttm") == Decimal("88.8889")
    assert metrics["profit_growth_ttm"].as_of == date(
        2024, 12, 31
    )  # as of the latest quarter, not the one compared with


def test_the_three_year_change_needs_sixteen_quarters() -> None:
    assert compute_metrics(_eight(), None)["profit_change_3y"].value is None
    items = [
        quarter(end, cr(100 + 10 * i), cr(3 * (i + 3))) for i, end in enumerate(quarter_ends(16))
    ]
    metrics = compute_metrics(build_series(items), None)
    # Sales 220 + 230 + 240 + 250 = 940 against 100 + 110 + 120 + 130 = 460: 104.3478%.
    # Profit 45 + 48 + 51 + 54 = 198 against 9 + 12 + 15 + 18 = 54: 266.6667%.
    assert _value(metrics, "revenue_change_3y") == Decimal("104.3478")
    assert _value(metrics, "profit_change_3y") == Decimal("266.6667")


def test_margins_are_taken_over_the_last_four_quarters() -> None:
    # Net: 102 / 620 = 16.4516%. Operating: profit before tax 28 + 32 + 36 + 40 = 136, plus finance costs 4 x 2 = 8,
    # is 144; 144 / 620 = 23.2258%.
    metrics = compute_metrics(_eight(), None)
    assert _value(metrics, "net_margin") == Decimal("16.4516")
    assert _value(metrics, "operating_margin") == Decimal("23.2258")


def test_operating_margin_is_not_worked_out_when_finance_costs_are_not_filed() -> None:
    metric = compute_metrics(_eight(finance=None), None)["operating_margin"]
    assert metric.value is None and "finance costs" in metric.reason.lower()


def test_profitable_quarters_are_counted_in_the_last_eight() -> None:
    losing = [9, 12, -5, 18, 21, 24, 27, 30]
    metrics = compute_metrics(_eight(profits=losing), None)
    assert metrics["profitable_quarters"].value == 7
    assert metrics["profitable_quarters"].extra == {"out_of": 8, "quarters_held": 8}
    assert compute_metrics(_eight(), None)["profitable_quarters"].value == 8


def test_interest_cover_is_profit_before_interest_and_tax_over_interest() -> None:
    # (profit before tax 136 + finance costs 8) / 8 = 18 times.
    assert compute_metrics(_eight(), None)["interest_cover"].value == Decimal(18)


def test_a_company_with_no_interest_bill_has_no_interest_cover_and_says_so() -> None:
    metric = compute_metrics(_eight(finance=0), None)["interest_cover"]
    assert metric.value is None and metric.extra == {"code": "NO_FINANCE_COSTS"}
    assert "no interest" in metric.reason.lower()


def test_debt_and_return_on_equity_use_the_latest_balance_sheet() -> None:
    # Borrowings 30 + 10 = 40 crore over owners' equity 400 crore = 0.1 times. Profit 102 / 400 = 25.5%.
    metrics = compute_metrics(_with_sheet(_eight()), None)
    assert metrics["debt_to_equity"].value == Decimal("0.1")
    assert metrics["roe"].value == Decimal("25.5") and metrics["roe"].approximate


def test_balance_sheet_ratios_say_why_when_no_balance_sheet_is_held() -> None:
    metrics = compute_metrics(_eight(), None)
    assert metrics["debt_to_equity"].value is None and "balance sheet" in metrics["roe"].reason


def test_a_balance_sheet_more_than_nine_months_before_the_latest_quarter_is_not_used() -> None:
    old = _with_sheet(_eight(), on=date(2023, 12, 31))
    metric = compute_metrics(old, None)["roe"]
    assert metric.value is None and "31 Dec 2023" in metric.reason


def test_price_ratios_use_the_platform_close_and_state_both_dates() -> None:
    # P/E 800 / 10.2 = 78.4314. Earnings yield 10.2 / 800 = 1.275%.
    # Book value per share: 400 crore over 1 crore shares = 400, so P/B = 800 / 400 = 2.
    metrics = compute_metrics(_with_sheet(_eight()), PRICE)
    assert _value(metrics, "pe") == Decimal("78.4314")
    assert metrics["earnings_yield"].value == Decimal("1.275")
    assert metrics["pb"].value == Decimal(2)
    assert "6 Oct 2026" in metrics["pe"].period and "31 Dec 2024" in metrics["pe"].period


def test_no_price_means_no_price_ratio_and_a_plain_reason() -> None:
    metrics = compute_metrics(_eight(), None)
    assert metrics["pe"].value is None and "price" in metrics["pe"].reason.lower()


def test_a_loss_making_company_has_no_price_to_earnings() -> None:
    items = _all_losses()
    metrics = compute_metrics(build_series(items), PRICE)
    assert metrics["pe"].value is None and "zero or negative" in metrics["pe"].reason


def test_four_quarters_are_needed_for_a_four_quarter_figure() -> None:
    short = build_series([quarter(end, cr(100), cr(9)) for end in ENDS_8[-3:]])
    metric = compute_metrics(short, None)["ttm_revenue"]
    assert metric.value is None and "four" in metric.reason.lower()


def test_a_gap_in_the_last_four_quarters_stops_the_four_quarter_figures() -> None:
    items = [quarter(end, cr(100), cr(9)) for end in ENDS_8 if end != date(2024, 6, 30)]
    metrics = compute_metrics(build_series(items), None)
    assert metrics["ttm_revenue"].value is None and "30 Jun 2024" in metrics["ttm_revenue"].reason


def test_growth_from_a_loss_is_not_given_as_a_percentage() -> None:
    profits = [9, 12, 15, -18, 21, 24, 27, 30]
    metric = compute_metrics(_eight(profits=profits), None)["profit_growth_quarter"]
    assert metric.value is None and "zero or a loss" in metric.reason


def test_every_input_carries_its_tag_period_filing_date_link_and_hash() -> None:
    metric = compute_metrics(_eight(), None)["ttm_net_profit"]
    assert len(metric.inputs) == 4
    first = metric.inputs[0]
    assert first.tag == "ProfitOrLossAttributableToOwnersOfParent" and first.sha256
    assert (
        first.source_url.startswith("https://nsearchives.nseindia.com/")
        and first.filed_on is not None
    )
    assert first.period.startswith("Three months ended")


def test_every_metric_has_a_plain_label_and_a_formula_in_words() -> None:
    metrics = compute_metrics(_with_sheet(_eight()), PRICE)
    assert all(m.label and m.formula for m in metrics.values())
    assert "pe" in metrics and "profitable_quarters" in metrics


def test_a_metric_that_cannot_be_worked_out_never_has_a_value() -> None:
    metrics = compute_metrics(build_series([]), PRICE)
    assert all(m.value is None and m.reason for m in metrics.values())


@pytest.mark.parametrize("key", ["ttm_revenue", "net_margin", "roe", "pe"])
def test_values_are_exact_decimals_never_floats(key: str) -> None:
    value = compute_metrics(_with_sheet(_eight()), PRICE)[key].value
    assert isinstance(value, Decimal)
