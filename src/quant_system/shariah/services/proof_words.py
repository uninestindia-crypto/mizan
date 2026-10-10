"""The plain sentences of a proof: amounts, percentages, one sentence per test, and what a result leaves out."""

from __future__ import annotations

from decimal import Decimal
from typing import Any

from quant_system.shariah.schemas.screening import SAMPLE_DATA_NOTICE

__all__ = [
    "NUMERATOR",
    "TITLES",
    "crore_text",
    "data_notice",
    "indian_grouping",
    "not_covered_for",
    "pct_text",
    "describe_test",
]

NUMERATOR = {
    "debt": "Debt",
    "cash": "Cash and securities",
    "receivables": "Receivables (money owed by customers)",
    "impermissible": "Interest and similar income",
}
_VERB = {"debt": "is", "cash": "are", "receivables": "are", "impermissible": "is"}
_LOW_DEFINITION = {
    "cash": "only cash and bank balances",
    "impermissible": "only the interest income the company itemises",
}
_HIGH_DEFINITION = {
    "cash": "all its investments as well",
    "impermissible": "all of its other income",
}
_DENOMINATOR = {
    ("AAOIFI", "market"): "its 36-month average market value",
    ("TASIS", "market"): "its total assets",
}
TITLES = {
    ("AAOIFI", "debt"): "Debt compared with market value",
    ("AAOIFI", "cash"): "Cash and securities compared with market value",
    ("AAOIFI", "receivables"): "Receivables compared with market value",
    ("TASIS", "debt"): "Debt compared with total assets",
    ("TASIS", "cash"): "Cash and securities compared with total assets",
    ("TASIS", "receivables"): "Receivables compared with total assets",
    ("AAOIFI", "impermissible"): "Interest and similar income compared with total income",
    ("TASIS", "impermissible"): "Interest and similar income compared with total income",
}
NOTICES = {
    "VERIFIED_FILING": (
        "Read by QuantOS from the company's own results filed on NSE, and checked only against themselves. "
        "Not audited by QuantOS or by a scholar."
    ),
    "STALE": (
        "Read from the company's results filed on NSE, but the balance sheet is more than 18 months old, so the "
        "figures may be out of date."
    ),
    "UNVERIFIED_SAMPLE": SAMPLE_DATA_NOTICE,
    "NOT_SCREENED": "QuantOS holds no company filing and no sample figures for this stock.",
}
_BASE_GAPS = (
    "No scholar has reviewed these rules or this result.",
    "This is a screening aid, not a fatwa and not financial advice.",
)
_SAMPLE_GAPS = (
    "The figures are a hand-entered sample, not read from audited filings.",
    "Not every income line has been reviewed, so a company's real mix of income may differ from what is counted here.",
)
_FILING_GAPS = (
    "The figures are read by machine from the company's own results filing and checked only against themselves. "
    "They have not been audited by QuantOS.",
    "Lease liabilities are not itemised in the results filing and are not counted as debt.",
    "The filing does not split investments into interest-bearing and other, and it does not itemise interest income "
    "unless the cash-flow statement does, so those two tests show a lower and an upper reading.",
    "The market value uses the share count in the filing and QuantOS's own daily prices. Later buybacks and new "
    "shares are not adjusted for.",
    "Business activity is judged from the company's name, its NSE industry group and the business segments in its "
    "filing, not from a full description of what it sells.",
)


def indian_grouping(value: int) -> str:
    """1300000 as 13,00,000: the last three digits, then groups of two."""
    digits = str(abs(int(value)))
    head, tail = digits[:-3], digits[-3:]
    groups: list[str] = []
    while len(head) > 2:
        groups.insert(0, head[-2:])
        head = head[:-2]
    if head:
        groups.insert(0, head)
    text = ",".join([*groups, tail]) if groups else tail
    return f"-{text}" if value < 0 else text


def crore_text(value: Decimal | float) -> str:
    amount = float(value)
    return (
        f"₹{indian_grouping(round(amount))} crore" if abs(amount) >= 1 else f"₹{amount:.2f} crore"
    )


def pct_text(pct: float) -> str:
    if pct == 0:
        return "0%"
    return f"{pct:.2f}%" if abs(pct) < 0.1 else f"{pct:.1f}%"


def data_notice(data_status: str) -> str:
    return NOTICES.get(data_status, NOTICES["NOT_SCREENED"])


def not_covered_for(data_status: str) -> list[str]:
    extra = _FILING_GAPS if data_status in ("VERIFIED_FILING", "STALE") else _SAMPLE_GAPS
    return [_BASE_GAPS[0], *extra, _BASE_GAPS[1]]


def _range(low: float, high: float) -> str:
    return (
        pct_text(high)
        if abs(high - low) < 0.005
        else f"between {pct_text(low)} and {pct_text(high)}"
    )


def _denominator(standard: str, key: str) -> str:
    return "its total income" if key == "impermissible" else _DENOMINATOR[(standard, "market")]


def describe_test(test: dict[str, Any], standard: str) -> str:
    """One plain sentence for a finished test: the figure, the limit, and where it stands."""
    key, result = str(test["key"]), str(test["result"])
    subject = f"{NUMERATOR[key]} {_VERB[key]}"
    limit = f"{test['limit_pct']:g}%"
    low, high = test["low"]["pct"], test["high"]["pct"]
    where = _denominator(standard, key)
    if result == "DEPENDS":
        return (
            f"The filing does not break this figure down. Counting {_LOW_DEFINITION.get(key, 'the lower reading')}, "
            f"{subject} {pct_text(low)} of {where} (under the {limit} limit); counting "
            f"{_HIGH_DEFINITION.get(key, 'the upper reading')} it is {pct_text(high)} (over the limit). "
            "So QuantOS cannot say which side of the limit this company is on."
        )
    figure = f"{subject} {_range(low, high)} of {where}"
    if result == "FAIL":
        return f"{figure}, over the {limit} limit."
    if result == "BORDERLINE":
        warning = f"{test['warning_pct']:g}%"
        return (
            f"{figure}, under the {limit} limit but inside the warning band ({warning} and above)."
        )
    return f"{figure}, under the {limit} limit."
