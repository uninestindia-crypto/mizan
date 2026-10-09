"""Side by side: only companies on the same basis, and a plain note whenever the comparison is not like for like."""

from __future__ import annotations

import json
import re
from dataclasses import replace
from datetime import date
from decimal import Decimal
from pathlib import Path

from quant_system.fundamentals.compare import compare
from quant_system.fundamentals.models import QuarterFigures
from quant_system.fundamentals.service import CompanyAnalysis, FundamentalsService
from quant_system.fundamentals.store import FundamentalsStore
from tests.fundamentals.support import balance, cr, quarter, quarter_ends, with_balance

ADVICE = re.compile(
    r"\b(buy|sell|best|undervalued|overvalued|target|cheap|expensive|should)\b", re.I
)


def _rows(
    symbol: str, consolidated: bool = True, last: date = date(2024, 12, 31), growth: int = 3
) -> list[QuarterFigures]:
    ends = quarter_ends(8, last)
    items = [
        quarter(
            e,
            cr(100 + 10 * i),
            cr(growth * (i + 3)),
            cr(2),
            str(Decimal(growth * (i + 3)) / 10),
            consolidated,
            10_000_000,
        )
        for i, e in enumerate(ends)
    ]
    items[6] = with_balance(items[6], balance(ends[6], cr(400), (cr(30), cr(10))))
    return [replace(item, symbol=symbol, company_name=f"{symbol} Limited") for item in items]


def _analyses(tmp_path: Path, spec: dict[str, dict[str, object]]) -> list[CompanyAnalysis]:
    store = FundamentalsStore(None, tmp_path / "c.sqlite")
    for symbol, kwargs in spec.items():
        store.put(_rows(symbol, **kwargs))  # type: ignore[arg-type]
    service = FundamentalsService(store, lambda: date(2025, 3, 1))
    return [service.analyse(symbol, None) for symbol in spec]


def test_companies_on_the_same_basis_and_date_are_compared_line_by_line(tmp_path: Path) -> None:
    result = compare(_analyses(tmp_path, {"AAA": {}, "BBB": {"growth": 6}}))
    assert result["comparable"] is True and result["basis"] == "consolidated"
    assert [c["symbol"] for c in result["companies"]] == ["AAA", "BBB"]
    roe = next(r for r in result["rows"] if r["key"] == "roe")
    assert roe["values"]["AAA"]["value"] == 25.5 and roe["values"]["BBB"]["value"] == 51.0
    assert result["notes"] == []


def test_a_company_on_another_basis_is_left_out_of_the_lines_and_the_reason_is_given(
    tmp_path: Path,
) -> None:
    result = compare(_analyses(tmp_path, {"AAA": {}, "BBB": {"consolidated": False}, "CCC": {}}))
    by_symbol = {c["symbol"]: c for c in result["companies"]}
    assert by_symbol["BBB"]["included"] is False and "standalone" in by_symbol["BBB"]["reason"]
    assert result["comparable"] is True
    row = next(r for r in result["rows"] if r["key"] == "net_margin")
    assert set(row["values"]) == {"AAA", "CCC"}


def test_two_companies_on_different_bases_are_not_comparable_and_it_says_so(tmp_path: Path) -> None:
    result = compare(_analyses(tmp_path, {"AAA": {}, "BBB": {"consolidated": False}}))
    assert result["comparable"] is False
    assert any("not like for like" in note for note in result["notes"])


def test_different_latest_quarters_are_called_out(tmp_path: Path) -> None:
    result = compare(_analyses(tmp_path, {"AAA": {}, "BBB": {"last": date(2024, 9, 30)}}))
    assert any("different quarters" in note and "30 Sep 2024" in note for note in result["notes"])


def test_a_company_with_nothing_held_is_listed_with_its_reason(tmp_path: Path) -> None:
    analyses = _analyses(tmp_path, {"AAA": {}})
    analyses.append(
        FundamentalsService(FundamentalsStore(None, None), lambda: date(2025, 3, 1)).analyse(
            "ZZZ", None
        )
    )
    result = compare(analyses)
    empty = next(c for c in result["companies"] if c["symbol"] == "ZZZ")
    assert empty["included"] is False and "No filings held" in empty["reason"]
    assert result["comparable"] is False


def test_each_value_carries_its_unit_and_date_and_the_response_is_plain_json(
    tmp_path: Path,
) -> None:
    result = compare(_analyses(tmp_path, {"AAA": {}, "BBB": {}}))
    value = next(r for r in result["rows"] if r["key"] == "ttm_revenue")["values"]["AAA"]
    assert value["unit"] == "INR" and value["as_of"] == "2024-12-31" and value["available"] is True
    assert json.loads(json.dumps(result)) == result


def test_the_comparison_says_it_is_facts_and_never_advises(tmp_path: Path) -> None:
    result = compare(_analyses(tmp_path, {"AAA": {}, "BBB": {"growth": 6}}))
    assert "not a ranking" in result["statement"]
    assert ADVICE.search(json.dumps(result)) is None
