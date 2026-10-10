"""The Copilot's read-only tool for a company's own filed results: what it returns, and that it only states facts."""

from __future__ import annotations

import json
import re
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

import pytest

from quant_system.copilot.registry import ToolContext, ToolResult
from quant_system.copilot.tools import default_registry
from quant_system.fundamentals import runtime as fundamentals_runtime
from quant_system.fundamentals.jobs import FundamentalsJobs
from quant_system.fundamentals.metric_types import PriceQuote
from quant_system.fundamentals.runtime import Runtime
from quant_system.fundamentals.service import FundamentalsService
from quant_system.fundamentals.store import FundamentalsStore
from quant_system.fundamentals.views import company_view
from tests.copilot_fakes import make_context
from tests.fundamentals.fakes import FakeNse
from tests.fundamentals.jobs_support import Held
from tests.fundamentals.support import FRESH, fund_rows

ADVICE = re.compile(
    r"\b(buy|sell|best|undervalued|overvalued|target|cheap|expensive|should)\b", re.I
)
CHANGE_WORDS = ("order", "buy", "sell", "place", "delete", "save", "write")
PRICE = PriceQuote(Decimal("102"), date(2021, 2, 26))


def _service(
    tmp_path: Path, today: date, symbols: tuple[str, ...] = ("AAA",)
) -> FundamentalsService:
    store = FundamentalsStore(None, tmp_path / "t.sqlite")
    for symbol in symbols:
        store.put(fund_rows(symbol))
    return FundamentalsService(store, lambda: today)


def _call(ctx: ToolContext, symbol: str = "AAA") -> ToolResult:
    return default_registry(ctx).call("filing_fundamentals", {"symbol": symbol})


def _ctx(service: FundamentalsService) -> ToolContext:
    return make_context(fundamentals=lambda symbol: company_view(service.analyse(symbol, PRICE)))


def test_the_tool_returns_facts_with_the_period_and_the_filing_date(tmp_path: Path) -> None:
    result = _call(_ctx(_service(tmp_path, FRESH)))
    assert result.ok and result.summary == "AAA: results from filings (verified filing)"
    data: dict[str, Any] = result.data
    assert data["data_status"] == "VERIFIED_FILING" and data["basis"].startswith("Consolidated")
    assert (
        data["latest_filing"]["quarter_ended"] == "2020-12-31"
        and data["latest_filing"]["filed_on"] == "2021-01-20"
    )
    assert (
        data["latest_filing"]["link"].startswith("https://")
        and data["latest_filing"]["fingerprint"]
    )
    assert (
        data["figures"]["ttm_revenue"]["value"] == 6_200_000_000
        and data["figures"]["ttm_revenue"]["as_of"] == "2020-12-31"
    )


def test_percentages_are_under_names_that_say_percent_points_and_estimates_are_marked(
    tmp_path: Path,
) -> None:
    figures = _call(_ctx(_service(tmp_path, FRESH))).data["figures"]
    assert figures["roe"]["value_pct"] == 25.5 and figures["roe"]["approximate"] is True
    assert figures["net_margin"]["value_pct"] == pytest.approx(16.45, abs=0.01)
    assert "value" not in figures["roe"] and figures["debt_to_equity"]["unit"] == "times"


def test_what_cannot_be_worked_out_is_listed_with_its_reason_and_never_filled_in(
    tmp_path: Path,
) -> None:
    service = _service(tmp_path, FRESH)
    ctx = make_context(fundamentals=lambda symbol: company_view(service.analyse(symbol, None)))
    pe = _call(ctx).data["figures"]["pe"]
    assert "value" not in pe and "Market data is not connected" in pe["not_available"]


def test_the_scorecard_carries_each_rule_of_thumb_and_the_header(tmp_path: Path) -> None:
    card = _call(_ctx(_service(tmp_path, FRESH))).data["scorecard"]
    assert card["header"].startswith("Rules of thumb for reading a company, not advice")
    roe = next(f for f in card["facts"] if "owners' money (approximate)" in f["sentence"])
    assert (
        roe["status"] == "OK"
        and roe["rule"] == "Rule of thumb: profit of 12% or more of the owners' money."
    )


def test_old_filings_are_called_old(tmp_path: Path) -> None:
    result = _call(_ctx(_service(tmp_path, date(2026, 10, 7))))
    assert (
        result.data["data_status"] == "STALE"
        and "more than 18 months" in result.data["data_notice"]
    )
    assert result.summary.endswith("(stale)")


def test_a_company_with_nothing_held_is_reported_as_such_not_invented(tmp_path: Path) -> None:
    result = _call(_ctx(_service(tmp_path, FRESH)), "ZZZ")
    assert result.ok and result.data["data_status"] == "NOT_AVAILABLE"
    assert (
        "No filings held for this company yet" in result.data["data_notice"]
        and result.data["latest_filing"] is None
    )
    assert all("not_available" in entry for entry in result.data["figures"].values())


def test_a_symbol_that_is_not_one_is_refused_in_plain_words(tmp_path: Path) -> None:
    result = _call(_ctx(_service(tmp_path, FRESH)), "not a symbol!")
    assert (
        not result.ok
        and result.error
        == "That is not a valid stock symbol. Use letters and numbers only, for example TCS."
    )


def test_the_whole_answer_fits_what_the_model_is_given_without_being_cut(tmp_path: Path) -> None:
    result = _call(_ctx(_service(tmp_path, FRESH)))
    text = result.for_prompt()
    assert len(json.dumps(result.data)) < 6000 and json.loads(text) == json.loads(
        json.dumps(result.data, default=str)
    )


def test_no_word_of_advice_is_in_anything_the_tool_returns(tmp_path: Path) -> None:
    result = _call(_ctx(_service(tmp_path, FRESH)))
    assert ADVICE.search(json.dumps(result.data)) is None


def test_without_a_supplied_lookup_the_tool_reads_the_apps_own_store(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    service = _service(tmp_path, FRESH)
    held = Held()
    jobs = FundamentalsJobs(
        service.store, lambda: FakeNse({}), lambda: datetime(2026, 10, 7, tzinfo=UTC), held
    )
    monkeypatch.setattr(fundamentals_runtime, "default_runtime", lambda: Runtime(service, jobs))
    result = _call(make_context())
    assert (
        result.ok
        and result.data["data_status"] == "VERIFIED_FILING"
        and result.data["price"] is None
    )


def test_the_tool_cannot_change_anything_and_is_only_asked_for_a_symbol() -> None:
    spec = next(
        s for s in default_registry(make_context()).catalog() if s["name"] == "filing_fundamentals"
    )
    assert spec["label"] == "Company results from filings"
    assert not [w for w in CHANGE_WORDS if w in spec["name"]]
