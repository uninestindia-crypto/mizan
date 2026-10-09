"""The plain label and the formula in words for every metric. Nothing here is advice; each is a description."""

from __future__ import annotations

from typing import Final, NamedTuple


class Words(NamedTuple):
    label: str
    formula: str


WORDS: Final = {
    "ttm_revenue": Words(
        "Sales over the last four quarters",
        "Revenue from operations, added up over the four most recent quarters",
    ),
    "ttm_net_profit": Words(
        "Profit over the last four quarters",
        "Profit for the company's owners, added up over the four most recent quarters",
    ),
    "ttm_eps": Words(
        "Earnings per share over the last four quarters",
        "Basic earnings per share, added up over the four most recent quarters",
    ),
    "revenue_growth_quarter": Words(
        "Sales against the same quarter a year ago",
        "(sales this quarter - sales in the same quarter a year earlier) / sales in the same quarter a year earlier",
    ),
    "profit_growth_quarter": Words(
        "Profit against the same quarter a year ago",
        "(profit this quarter - profit in the same quarter a year earlier) / profit in the same quarter a year earlier",
    ),
    "revenue_growth_ttm": Words(
        "Sales over four quarters against the four quarters a year before",
        "(sales over the last four quarters - sales over the same four quarters a year earlier) / the latter",
    ),
    "profit_growth_ttm": Words(
        "Profit over four quarters against the four quarters a year before",
        "(profit over the last four quarters - profit over the same four quarters a year earlier) / the latter",
    ),
    "revenue_change_3y": Words(
        "Sales over four quarters against the same four quarters three years ago",
        "(sales over the last four quarters - sales over the same four quarters three years earlier) / the latter",
    ),
    "profit_change_3y": Words(
        "Profit over four quarters against the same four quarters three years ago",
        "(profit over the last four quarters - profit over the same four quarters three years earlier) / the latter",
    ),
    "net_margin": Words(
        "Profit as a share of sales",
        "profit over the last four quarters / sales over the last four quarters",
    ),
    "operating_margin": Words(
        "Operating profit as a share of sales",
        "(sales - expenses other than finance costs) / sales, over the last four quarters",
    ),
    "profitable_quarters": Words(
        "Quarters with a profit in the last eight",
        "the number of the last eight quarters in which profit for the owners was above zero",
    ),
    "interest_cover": Words(
        "How many times profit covers the interest bill",
        "(profit before tax + finance costs) / finance costs, over the last four quarters",
    ),
    "debt_to_equity": Words(
        "Borrowings compared with the owners' money",
        "(current borrowings + non-current borrowings) / equity of the owners, at the balance-sheet date",
    ),
    "roe": Words(
        "Profit as a share of the owners' money",
        "profit over the last four quarters / equity of the owners at the latest balance-sheet date",
    ),
    "pe": Words(
        "Price compared with earnings (P/E)",
        "the platform's last close / earnings per share over the last four quarters",
    ),
    "earnings_yield": Words(
        "Earnings as a share of the price",
        "earnings per share over the last four quarters / the platform's last close",
    ),
    "pb": Words(
        "Price compared with the owners' money per share (P/B)",
        "the platform's last close / (equity of the owners / shares in issue), at the latest balance-sheet date",
    ),
}
NUMBER_WORDS: Final = {1: "one", 2: "two", 4: "four", 8: "eight", 16: "sixteen"}
