"""The fundamentals API through the real app, over a fixture market store, with a fake NSE and a fixed date."""

from __future__ import annotations

import json
import re
from collections.abc import Iterator
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from quant_system.fundamentals import fmt
from quant_system.fundamentals import runtime as fundamentals_runtime
from quant_system.fundamentals.extract import extract_quarter
from quant_system.fundamentals.jobs import FundamentalsJobs
from quant_system.fundamentals.runtime import Runtime
from quant_system.fundamentals.service import FundamentalsService
from quant_system.fundamentals.store import FundamentalsStore
from quant_system.server.app import app
from quant_system.server.v2 import fundamentals_routes, router
from tests import test_v2_api as _api
from tests.fundamentals.fakes import FakeNse
from tests.fundamentals.jobs_support import Held
from tests.fundamentals.support import FRESH, cr, fixture_bytes, listing_row
from tests.fundamentals.support import fund_rows as _rows

client = _api.client
data_folder = _api.data_folder
headers = _api.headers
ready = _api.ready

ADVICE = re.compile(
    r"\b(buy|sell|best|undervalued|overvalued|target|cheap|expensive|should)\b", re.I
)


class Fixture:
    def __init__(self, tmp_path: Path, today: date) -> None:
        self.nse = FakeNse({})
        self.held = Held()
        self.store = FundamentalsStore(None, tmp_path / "fund.sqlite")
        now = lambda: datetime(2026, 10, 7, tzinfo=UTC)  # noqa: E731
        self.runtime = Runtime(
            FundamentalsService(self.store, lambda: today),
            FundamentalsJobs(self.store, lambda: self.nse, now, self.held),
        )


@pytest.fixture()
def fund(client: TestClient, tmp_path: Path) -> Iterator[Fixture]:
    made = Fixture(tmp_path, FRESH)
    app.dependency_overrides[fundamentals_routes.runtime] = lambda: made.runtime
    yield made
    app.dependency_overrides.pop(fundamentals_routes.runtime, None)


def _error(response: Any) -> dict[str, Any]:
    return dict(response.json()["error"])


# ---------------------------------------------------------------------------------------------- one company


def test_a_company_with_filings_returns_figures_a_scorecard_and_proof(
    ready: TestClient, fund: Fixture
) -> None:
    fund.store.put(_rows("AAA"))
    body = ready.get("/api/v2/fundamentals/AAA").json()
    assert (
        body["data_status"] == "VERIFIED_FILING"
        and body["latest_quarter"]["period_end"] == "2020-12-31"
    )
    assert body["metrics"]["ttm_revenue"]["value"] == cr(620)
    proof = body["metrics"]["ttm_net_profit"]["inputs"][0]
    assert (
        proof["tag"]
        and proof["filing_url"].startswith("https://")
        and proof["sha256"]
        and proof["filed_on"]
    )
    assert (
        body["scorecard"]["header"].startswith("Rules of thumb")
        and body["scorecard"]["counts"]["OK"] >= 1
    )


def test_the_price_ratios_use_the_platform_close_and_state_the_price_date(
    ready: TestClient, fund: Fixture
) -> None:
    fund.store.put(_rows("AAA"))
    close = router.services().index.symbol_info("AAA")["snapshot"]["close"]
    body = ready.get("/api/v2/fundamentals/aaa").json()
    assert body["price"]["close"] == pytest.approx(float(close)) and body["price"]["as_of"]
    pe = body["metrics"]["pe"]
    assert pe["value"] == pytest.approx(float(close) / 10.2, abs=0.01)
    assert (
        fmt.day(date.fromisoformat(body["price"]["as_of"])) in pe["period"]
        and "31 Dec 2020" in pe["period"]
    )


def test_a_company_with_nothing_held_is_not_available_and_says_so(
    ready: TestClient, fund: Fixture
) -> None:
    body = ready.get("/api/v2/fundamentals/BBB").json()
    assert (
        body["data_status"] == "NOT_AVAILABLE"
        and "No filings held for this company yet" in body["data_notice"]
    )


def test_figures_older_than_eighteen_months_are_stale(ready: TestClient, tmp_path: Path) -> None:
    old = Fixture(tmp_path / "old", date(2026, 10, 7))
    old.store.put(_rows("AAA"))
    app.dependency_overrides[fundamentals_routes.runtime] = lambda: old.runtime
    try:
        body = ready.get("/api/v2/fundamentals/AAA").json()
    finally:
        app.dependency_overrides.pop(fundamentals_routes.runtime, None)
    assert body["data_status"] == "STALE" and "more than 18 months" in body["data_notice"]


def test_works_before_market_data_is_connected_minus_the_price_figures(
    client: TestClient, fund: Fixture
) -> None:
    fund.store.put(_rows("AAA"))
    body = client.get("/api/v2/fundamentals/AAA").json()
    assert body["data_status"] == "VERIFIED_FILING" and body["price"] is None
    assert (
        body["metrics"]["pe"]["value"] is None
        and "Market data is not connected" in body["metrics"]["pe"]["reason"]
    )


def test_a_bad_symbol_gets_one_plain_sentence_in_the_apps_error_format(
    client: TestClient, fund: Fixture
) -> None:
    response = client.get("/api/v2/fundamentals/BAD$SYM")
    error = _error(response)
    assert response.status_code == 422 and error["code"] == "BAD_REQUEST"
    assert error["message"] == "Use letters and numbers only for the stock symbol, for example TCS."


# ------------------------------------------------------------------------------------------ compare and screen


def test_compare_puts_two_to_four_companies_side_by_side(ready: TestClient, fund: Fixture) -> None:
    fund.store.put(_rows("AAA") + _rows("BBB", step=6))
    body = ready.get("/api/v2/fundamentals/compare", params={"symbols": "AAA,BBB"}).json()
    assert body["comparable"] is True and [c["symbol"] for c in body["companies"]] == ["AAA", "BBB"]
    roe = next(r for r in body["rows"] if r["key"] == "roe")["values"]
    assert roe["AAA"]["value"] == 25.5 and roe["BBB"]["value"] == 51.0


@pytest.mark.parametrize(
    "symbols", ["AAA", "AAA,BBB,AAA,DDD,NIFTYBEES,XYZ", "AAA,,", "AAA,BAD$", ""]
)
def test_compare_needs_two_to_four_valid_symbols_and_says_so(
    client: TestClient, fund: Fixture, symbols: str
) -> None:
    response = client.get("/api/v2/fundamentals/compare", params={"symbols": symbols})
    assert response.status_code == 422 and _error(response)["message"].startswith(
        "Pick two to four stocks"
    )


def test_screen_applies_only_the_filters_chosen_and_says_what_it_did(
    ready: TestClient, fund: Fixture
) -> None:
    fund.store.put(_rows("AAA") + _rows("BBB", step=6))
    body = ready.get(
        "/api/v2/fundamentals/screen",
        params={"min_roe_pct": 30, "sort": "roe_pct", "order": "desc"},
    ).json()
    assert [r["symbol"] for r in body["results"]] == ["BBB"]
    assert body["statement"] == "These are filters you chose, not a recommendation."
    assert body["filters_applied"][0]["filter"] == "min_roe_pct" and body["considered"] == 2
    assert body["excluded_by_filters"] == 1 and body["excluded_missing_data"] == 0


def test_screen_with_no_data_held_returns_an_honest_empty_answer(
    client: TestClient, fund: Fixture
) -> None:
    body = client.get("/api/v2/fundamentals/screen").json()
    assert body["considered"] == 0 and body["results"] == [] and body["filters_applied"] == []


@pytest.mark.parametrize(
    "params",
    [
        {"sort": "best_first"},
        {"order": "up"},
        {"limit": 101},
        {"limit": 0},
        {"min_roe_pct": "lots"},
        {"min_profitable_quarters": 9},
        {"sector": "x"},
    ],
)
def test_screen_refuses_what_it_cannot_use_in_the_apps_plain_format(
    client: TestClient, fund: Fixture, params: dict[str, Any]
) -> None:
    response = client.get("/api/v2/fundamentals/screen", params=params)
    error = _error(response)
    assert (
        response.status_code == 422
        and error["code"] == "BAD_REQUEST"
        and "[" not in error["message"]
    )


def test_nothing_a_route_says_contains_a_word_of_advice(ready: TestClient, fund: Fixture) -> None:
    fund.store.put(_rows("AAA") + _rows("BBB"))
    answers = [
        ready.get("/api/v2/fundamentals/AAA").json(),
        ready.get("/api/v2/fundamentals/compare", params={"symbols": "AAA,BBB"}).json(),
        ready.get("/api/v2/fundamentals/screen", params={"max_pe": 500}).json(),
    ]
    text = json.dumps([{k: v for k, v in a.items() if k != "statement"} for a in answers])
    assert ADVICE.search(text) is None


# ------------------------------------------------------------------------------------------------- jobs


def _nse_with_tcs(fund: Fixture) -> None:
    sep, dec = (
        listing_row(period_end=date(2024, 9, 30)),
        listing_row(period_end=date(2024, 12, 31), filed_on=date(2025, 1, 9)),
    )
    fund.nse.rows["TCS"] = [sep, dec]
    fund.nse.files[sep.xbrl_url] = fixture_bytes("tcs_2024-09-30_consolidated_trimmed.xml")
    fund.nse.files[dec.xbrl_url] = fixture_bytes("tcs_2024-12-31_consolidated_trimmed.xml")


def test_a_fetch_is_accepted_runs_in_the_background_and_ends_done(
    client: TestClient, headers: dict[str, str], fund: Fixture
) -> None:
    _nse_with_tcs(fund)
    started = client.post("/api/v2/fundamentals/fetch", json={"symbol": "tcs"}, headers=headers)
    assert started.status_code == 202
    job = started.json()["job_id"]
    assert client.get(f"/api/v2/fundamentals/jobs/{job}").json()["status"] == "running"
    fund.held.run()
    done = client.get(f"/api/v2/fundamentals/jobs/{job}").json()
    assert (
        done["status"] == "done"
        and done["done"] == done["total"] == 2
        and done["message"] == "Read 2 of 2 filings for TCS."
    )
    assert client.get("/api/v2/fundamentals/TCS").json()["series"]["held"] == 2


def test_a_second_fetch_while_one_runs_is_turned_away(
    client: TestClient, headers: dict[str, str], fund: Fixture
) -> None:
    assert (
        client.post(
            "/api/v2/fundamentals/fetch", json={"symbol": "TCS"}, headers=headers
        ).status_code
        == 202
    )
    again = client.post("/api/v2/fundamentals/fetch", json={"symbol": "INFY"}, headers=headers)
    assert again.status_code == 429 and _error(again)["code"] == "TOO_BUSY"
    assert "already reading" in _error(again)["message"]


def test_a_fetch_can_be_stopped_and_reads_nothing_more(
    client: TestClient, headers: dict[str, str], fund: Fixture
) -> None:
    _nse_with_tcs(fund)
    job = client.post("/api/v2/fundamentals/fetch", json={"symbol": "TCS"}, headers=headers).json()[
        "job_id"
    ]
    stopped = client.delete(f"/api/v2/fundamentals/jobs/{job}", headers=headers)
    assert stopped.status_code == 200 and stopped.json() == {"cancelled": True}
    fund.held.run()
    assert fund.nse.fetched == []
    assert client.get(f"/api/v2/fundamentals/jobs/{job}").json()["status"] == "cancelled"


def test_a_refusal_from_nse_is_reported_in_plain_words_through_the_job(
    client: TestClient, headers: dict[str, str], fund: Fixture
) -> None:
    from quant_system.shariah.filings.nse_client import FilingsBlocked

    fund.nse.fail_with = FilingsBlocked()
    job = client.post("/api/v2/fundamentals/fetch", json={"symbol": "TCS"}, headers=headers).json()[
        "job_id"
    ]
    fund.held.run()
    ended = client.get(f"/api/v2/fundamentals/jobs/{job}").json()
    assert ended["status"] == "failed" and ended["message"].endswith("Try again later.")


def test_a_bad_symbol_to_fetch_and_an_unknown_job_are_plain_errors(
    client: TestClient, headers: dict[str, str], fund: Fixture
) -> None:
    bad = client.post(
        "/api/v2/fundamentals/fetch", json={"symbol": "not a symbol!"}, headers=headers
    )
    assert bad.status_code == 422 and _error(bad)["code"] == "INVALID_SYMBOL"
    assert client.get("/api/v2/fundamentals/jobs/nope").status_code == 404
    assert client.delete("/api/v2/fundamentals/jobs/nope", headers=headers).status_code == 404


def test_starting_or_stopping_a_fetch_needs_the_security_token(
    client: TestClient, fund: Fixture
) -> None:
    assert client.post("/api/v2/fundamentals/fetch", json={"symbol": "TCS"}).status_code == 403
    assert fund.nse.listed == []


def test_a_bank_is_reported_as_a_layout_not_read_through_the_api(
    client: TestClient, fund: Fixture
) -> None:
    bank = extract_quarter(
        fixture_bytes("hdfcbank_2024-09-30_consolidated_trimmed.xml"),
        listing_row(symbol="HDFCBANK", flag="B"),
        "2026-10-07T00:00:00Z",
    )
    fund.store.put([bank])
    body = client.get("/api/v2/fundamentals/HDFCBANK").json()
    assert body["data_status"] == "NOT_AVAILABLE" and body["read_status"] == "FORMAT_NOT_READ"
    assert "bank" in body["data_notice"].lower() and body["series"]["held"] == 0


def test_the_apps_own_runtime_works_with_no_snapshot_and_no_saved_filings(
    client: TestClient, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(fundamentals_runtime, "REPO_ROOT", tmp_path / "no-checkout")
    fundamentals_runtime.forget_runtimes()
    try:
        body = client.get("/api/v2/fundamentals/TCS").json()
        screen = client.get("/api/v2/fundamentals/screen").json()
    finally:
        fundamentals_runtime.forget_runtimes()
    assert (
        body["data_status"] == "NOT_AVAILABLE"
        and "No filings held for this company yet" in body["data_notice"]
    )
    assert screen["considered"] == 0 and screen["data_dates"]["snapshot_built_on"] is None
