"""One company's analysis: its data status by an injected date, its proof, and what it says when nothing is held."""

from __future__ import annotations

import json
from dataclasses import replace
from datetime import date
from decimal import Decimal
from pathlib import Path

from quant_system.fundamentals.extract import extract_quarter
from quant_system.fundamentals.metric_types import PriceQuote
from quant_system.fundamentals.models import QuarterFigures, ReadStatus
from quant_system.fundamentals.service import FundamentalsService, months_before, price_for
from quant_system.fundamentals.store import FundamentalsStore
from quant_system.fundamentals.views import company_view
from tests.fundamentals.support import (
    balance,
    cr,
    fixture_bytes,
    listing_row,
    quarter,
    quarter_ends,
    with_balance,
)

STAMP = "2026-10-07T00:00:00Z"
PRICE = PriceQuote(Decimal("800"), date(2026, 10, 6))


def _service(
    tmp_path: Path, today: date, rows: list[QuarterFigures] | None = None
) -> FundamentalsService:
    store = FundamentalsStore(None, tmp_path / "fundamentals.sqlite")
    if rows:
        store.put(rows)
    return FundamentalsService(store, lambda: today)


def _eight() -> list[QuarterFigures]:
    ends = quarter_ends(8)
    items = [
        quarter(
            end, cr(100 + 10 * i), cr(3 * (i + 3)), cr(2), str(3 * (i + 3) / 10), shares=10_000_000
        )
        for i, end in enumerate(ends)
    ]
    items[6] = with_balance(items[6], balance(ends[6], cr(400), (cr(30), cr(10))))
    return items


def _real(name: str, end: date, filed: date) -> QuarterFigures:
    return extract_quarter(fixture_bytes(name), listing_row(period_end=end, filed_on=filed), STAMP)


def test_a_company_with_nothing_held_says_no_filings_are_held_yet(tmp_path: Path) -> None:
    found = _service(tmp_path, date(2026, 10, 7)).analyse("TCS", None)
    assert found.data_status == "NOT_AVAILABLE" and found.read_status == "NO_FILINGS"
    assert "No filings held for this company yet" in found.data_notice
    assert all(not m.available for m in found.metrics.values())


def test_recent_figures_are_verified_filing(tmp_path: Path) -> None:
    found = _service(tmp_path, date(2025, 3, 1), _eight()).analyse("ABC", None)
    assert found.data_status == "VERIFIED_FILING" and found.read_status == "READ_OK"
    assert found.series.latest is not None and found.series.latest.period_end == date(2024, 12, 31)


def test_figures_older_than_eighteen_months_are_stale_by_the_injected_date(tmp_path: Path) -> None:
    found = _service(tmp_path, date(2026, 10, 7), _eight()).analyse("ABC", None)
    assert found.data_status == "STALE"
    assert "31 Dec 2024" in found.data_notice and "more than 18 months" in found.data_notice
    assert found.scorecard.facts[0].key == "data_age"


def test_the_eighteen_month_line_is_exact() -> None:
    assert months_before(date(2026, 6, 30), 18) == date(2024, 12, 30)
    assert months_before(date(2026, 8, 31), 18) == date(2025, 2, 28)


def test_a_quarter_ending_exactly_eighteen_months_before_today_is_not_stale(tmp_path: Path) -> None:
    on_the_line = _service(tmp_path / "a", date(2026, 6, 30), _eight())
    assert on_the_line.analyse("ABC", None).data_status == "VERIFIED_FILING"
    a_day_later = _service(tmp_path / "b", date(2026, 7, 1), _eight())
    assert a_day_later.analyse("ABC", None).data_status == "STALE"


def test_a_bank_is_not_available_and_says_its_layout_is_not_read(tmp_path: Path) -> None:
    bank = extract_quarter(
        fixture_bytes("hdfcbank_2024-09-30_consolidated_trimmed.xml"),
        listing_row(symbol="HDFCBANK", flag="B"),
        STAMP,
    )
    found = _service(tmp_path, date(2025, 3, 1), [bank]).analyse("HDFCBANK", None)
    assert found.data_status == "NOT_AVAILABLE" and found.read_status == "FORMAT_NOT_READ"
    assert "bank" in found.data_notice.lower()


def test_filings_that_failed_their_checks_leave_no_figures_and_say_so(tmp_path: Path) -> None:
    failed = replace(_eight()[-1], status=ReadStatus.TIE_OUT_FAILED, note="x")
    found = _service(tmp_path, date(2025, 3, 1), [failed]).analyse("ABC", None)
    assert found.read_status == "NONE_USABLE" and "none passed its own checks" in found.data_notice


def test_the_price_is_used_for_price_ratios_and_dropped_when_nothing_is_held(
    tmp_path: Path,
) -> None:
    held = _service(tmp_path, date(2025, 3, 1), _eight()).analyse("ABC", PRICE)
    assert held.metrics["pe"].value is not None and held.price == PRICE
    empty = _service(tmp_path / "empty", date(2025, 3, 1)).analyse("ABC", PRICE)
    assert empty.price is None


def test_real_tcs_filings_give_a_verified_company_with_proof(tmp_path: Path) -> None:
    sep = _real("tcs_2024-09-30_consolidated_trimmed.xml", date(2024, 9, 30), date(2024, 10, 10))
    dec = _real("tcs_2024-12-31_consolidated_trimmed.xml", date(2024, 12, 31), date(2025, 1, 9))
    view = company_view(_service(tmp_path, date(2025, 2, 1), [sep, dec]).analyse("TCS", None))
    assert view["data_status"] == "VERIFIED_FILING" and view["basis"]["consolidated"] is True
    assert view["latest_quarter"]["period_end"] == "2024-12-31" and view["series"]["held"] == 2
    assert view["metrics"]["ttm_revenue"]["value"] is None  # two quarters are not four


def test_the_view_is_plain_json_with_no_decimals_and_every_input_has_proof(tmp_path: Path) -> None:
    view = company_view(_service(tmp_path, date(2025, 3, 1), _eight()).analyse("ABC", PRICE))
    text = json.dumps(view)
    assert "Decimal" not in text
    inputs = [i for m in view["metrics"].values() for i in m["inputs"]]
    filing = [i for i in inputs if i["kind"] == "FILING"]
    assert filing and all(
        i["tag"] and i["period"] and i["filing_url"] and i["sha256"] for i in filing
    )
    assert all(i["filed_on"] for i in filing)
    assert view["metrics"]["pe"]["inputs"][0]["kind"] == "PRICE"


def test_the_view_states_the_basis_and_that_it_is_not_advice(tmp_path: Path) -> None:
    view = company_view(_service(tmp_path, date(2025, 3, 1), _eight()).analyse("ABC", None))
    assert view["basis"]["label"].startswith("Consolidated")
    assert "not advice" in view["statement"] and view["scorecard"]["header"].startswith(
        "Rules of thumb"
    )
    assert any("Lease liabilities" in line for line in view["not_covered"])


class _Index:
    def symbol_info(self, symbol: str) -> dict[str, object]:
        if symbol == "GONE":
            raise LookupError(symbol)
        if symbol == "ZERO":
            return {"snapshot": {"close": 0, "asof": "2026-10-06"}}
        if symbol == "NONE":
            return {"snapshot": None}
        return {"snapshot": {"close": 3812.5, "asof": "2026-10-06"}}


def test_a_price_is_read_from_the_platform_index() -> None:
    assert price_for(_Index(), "TCS") == PriceQuote(Decimal("3812.5"), date(2026, 10, 6))
    assert price_for(_Index(), "GONE") is None and price_for(None, "TCS") is None


def test_a_price_of_zero_or_a_missing_one_is_no_price() -> None:
    assert price_for(_Index(), "ZERO") is None and price_for(_Index(), "NONE") is None
