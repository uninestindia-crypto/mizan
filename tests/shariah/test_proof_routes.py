"""The proof, status, filing-job and coverage routes over HTTP.

Two layers: the routes alone on a small app with a fake NSE reader (every answer checked), and the real app with a
temporary app folder to prove the routes are mounted where the screens call them, that the bundled snapshot is
found where the program keeps it, and that a fetched filing is saved in the person's own data folder.
"""

from __future__ import annotations

import gzip
import shutil
import threading
from collections.abc import Callable, Iterator
from pathlib import Path
from typing import Any

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from quant_system.shariah.api.v1.router import api_router
from quant_system.shariah.filings.models import ReadStatus
from quant_system.shariah.filings.selection import Selection
from quant_system.shariah.services import proof_paths
from quant_system.shariah.services.filing_jobs import FilingJobs
from quant_system.shariah.services.proof_paths import SNAPSHOT_FILE
from quant_system.shariah.services.proof_runtime import ProofRuntime, use_runtime
from tests.shariah.proof_service_fixtures import (
    SAMPLE_ROW,
    FakeBars,
    FakeSample,
    figures_for,
    make_service,
    make_store,
    no_network,  # noqa: F401 -- a pytest fixture, applied to every test below by name
    standard_filings,
    tcs_figures,
    three_prices,
    write_snapshot,
)

pytestmark = pytest.mark.usefixtures("no_network")

BASE = "/api/v2/shariah"
EVERY_SYMBOL = ["TCS", "DRYBREW", "FOODCO", "HDFCBANK", "BROKEN", "SAMPLEONLY", "NOPE"]


class FakeNse:
    """Answers `read_company` from a script and remembers what was asked."""

    def __init__(self) -> None:
        self.asked: list[str] = []

    def read_company(self, symbol: str) -> Selection:
        self.asked.append(symbol)
        figures = tcs_figures() if symbol == "TCS" else figures_for(symbol, f"{symbol} Limited")
        return Selection(figures, ReadStatus.READ_OK, "", 1)


class Lab:
    def __init__(self, client: TestClient, nse: FakeNse, tasks: list[Callable[[], None]]) -> None:
        self.client, self.nse, self.tasks = client, nse, tasks

    def get(self, path: str) -> Any:
        return self.client.get(f"{BASE}{path}")

    def run_job(self, index: int = 0) -> None:
        self.tasks[index]()


@pytest.fixture()
def lab(tmp_path: Path) -> Iterator[Lab]:
    bars = FakeBars({s: three_prices() for s in ("TCS", "FOODCO", "DRYBREW")})
    store = make_store(tmp_path)
    service = make_service(store, FakeSample({"SAMPLEONLY": SAMPLE_ROW}), bars)
    nse, tasks = FakeNse(), []
    jobs = FilingJobs(store, lambda: nse, lambda: ["TCS", "INFY"], tasks.append)
    use_runtime(ProofRuntime(service, jobs))
    app = FastAPI()
    app.include_router(api_router, prefix=BASE)
    yield Lab(TestClient(app), nse, tasks)
    use_runtime(None)


def error_of(response: Any) -> dict[str, Any]:
    body = response.json()
    assert set(body) == {"error"}
    return dict(body["error"])


# ------------------------------------------------------------------------------------- the proof


def test_the_proof_route_answers_with_the_contracts_shape(lab: Lab) -> None:
    response = lab.get("/stocks/FOODCO/proof")
    proof = response.json()
    assert response.status_code == 200
    assert proof["symbol"] == "FOODCO" and proof["verdict"] == "COMPLIANT"
    assert proof["data_status"] == "VERIFIED_FILING" and proof["filing"]["sha256"]
    assert [s["standard"] for s in proof["standards"]] == ["AAOIFI", "TASIS"]


def test_a_stock_nothing_is_known_about_is_answered_not_screened_not_refused(lab: Lab) -> None:
    response = lab.get("/stocks/NOPE/proof")
    assert response.status_code == 200 and response.json()["verdict"] == "NOT_SCREENED"


def test_a_lower_case_symbol_finds_the_stock(lab: Lab) -> None:
    assert lab.get("/stocks/foodco/proof").json()["symbol"] == "FOODCO"


@pytest.mark.parametrize("symbol", ["bad%20symbol", "THIS-SYMBOL-IS-FAR-TOO-LONG", "a%3Cb"])
def test_a_symbol_that_cannot_be_one_is_refused_in_the_apps_plain_error_format(
    lab: Lab, symbol: str
) -> None:
    response = lab.get(f"/stocks/{symbol}/proof")
    error = error_of(response)
    assert response.status_code == 422 and error["code"] == "INVALID_SYMBOL"
    assert (
        error["message"]
        == "That is not a valid NSE company symbol. Check the spelling and try again."
    )
    assert error["request_id"].startswith("req-") and "timestamp" in error


def test_the_older_stock_routes_are_still_there_beside_the_new_one(lab: Lab) -> None:
    paths = lab.client.get("/openapi.json").json()["paths"]
    assert f"{BASE}/stocks/{{symbol}}/proof" in paths
    assert {f"{BASE}/stocks/{{ticker}}", f"{BASE}/stocks/{{ticker}}/screen"} <= set(paths)


# ------------------------------------------------------------------------------------- the status


def test_status_answers_for_each_stock_asked_about_and_nothing_else(lab: Lab) -> None:
    body = lab.get("/status?symbols=FOODCO,hdfcbank,NOPE").json()
    assert list(body) == ["statuses"] and list(body["statuses"]) == ["FOODCO", "HDFCBANK", "NOPE"]
    assert body["statuses"]["FOODCO"] == {
        "verdict": "COMPLIANT",
        "data_status": "VERIFIED_FILING",
        "short": "Passes the business test and both standards.",
        "as_of": "2024-09-30",
    }
    assert body["statuses"]["NOPE"]["verdict"] == "NOT_SCREENED"


def test_status_with_no_symbols_is_an_empty_answer(lab: Lab) -> None:
    assert lab.get("/status").json() == {"statuses": {}}
    assert lab.get("/status?symbols=,,").json() == {"statuses": {}}


@pytest.mark.parametrize("symbol", EVERY_SYMBOL)
def test_the_status_over_http_never_disagrees_with_the_proof_over_http(
    lab: Lab, symbol: str
) -> None:
    proof = lab.get(f"/stocks/{symbol}/proof").json()
    row = lab.get(f"/status?symbols={symbol}").json()["statuses"][symbol]
    assert (row["verdict"], row["data_status"]) == (proof["verdict"], proof["data_status"])


def test_two_hundred_stocks_in_one_call_are_answered_and_more_are_refused_plainly(lab: Lab) -> None:
    names = [f"S{n}" for n in range(201)]
    assert len(lab.get(f"/status?symbols={','.join(names[:200])}").json()["statuses"]) == 200
    refused = lab.get(f"/status?symbols={','.join(names)}")
    assert refused.status_code == 422 and error_of(refused)["code"] == "TOO_MANY_SYMBOLS"
    assert "at most 200" in error_of(refused)["message"]


# ------------------------------------------------------------------------------------- filing jobs


def test_fetching_a_stock_starts_a_job_and_answers_202_with_its_id(lab: Lab) -> None:
    response = lab.client.post(f"{BASE}/filings/fetch", json={"symbol": "tcs"})
    assert response.status_code == 202 and set(response.json()) == {"job_id"}
    job = lab.get(f"/filings/jobs/{response.json()['job_id']}").json()
    assert job["status"] == "running" and job["total"] == 1 and job["failures"] == []
    lab.run_job()
    done = lab.get(f"/filings/jobs/{response.json()['job_id']}").json()
    assert done["status"] == "done" and done["message"] == "Read the latest filing for TCS."
    assert set(done) == {"status", "done", "total", "message", "failures"}


@pytest.mark.parametrize(
    ("path", "body"), [("/filings/fetch", {"symbol": "INFY"}), ("/filings/refresh", None)]
)
def test_a_second_job_while_one_runs_is_a_429_with_a_plain_sentence(
    lab: Lab, path: str, body: dict[str, str] | None
) -> None:
    assert lab.client.post(f"{BASE}/filings/fetch", json={"symbol": "TCS"}).status_code == 202
    refused = lab.client.post(f"{BASE}{path}", json=body)
    assert refused.status_code == 429 and error_of(refused)["code"] == "TOO_BUSY"
    assert error_of(refused)["message"].startswith("Another filing is already being read.")


def test_a_symbol_that_cannot_be_one_starts_no_job(lab: Lab) -> None:
    response = lab.client.post(f"{BASE}/filings/fetch", json={"symbol": "no way"})
    assert response.status_code == 422 and error_of(response)["code"] == "INVALID_SYMBOL"
    assert lab.tasks == []


def test_a_fetch_without_a_symbol_is_refused(lab: Lab) -> None:
    assert lab.client.post(f"{BASE}/filings/fetch", json={}).status_code == 422


def test_refreshing_reads_what_the_app_follows_and_what_is_screened(lab: Lab) -> None:
    response = lab.client.post(f"{BASE}/filings/refresh")
    assert response.status_code == 202
    lab.run_job()
    assert lab.nse.asked == ["TCS", "INFY", "DRYBREW", "FOODCO"]
    done = lab.get(f"/filings/jobs/{response.json()['job_id']}").json()
    assert done["status"] == "done" and done["done"] == 4


def test_stopping_a_job_over_http_stops_it_and_a_new_one_can_start(lab: Lab) -> None:
    job_id = lab.client.post(f"{BASE}/filings/fetch", json={"symbol": "TCS"}).json()["job_id"]
    stopped = lab.client.delete(f"{BASE}/filings/jobs/{job_id}")
    assert stopped.status_code == 200 and stopped.json() == {"cancelled": True}
    state = lab.get(f"/filings/jobs/{job_id}").json()
    assert state["status"] == "cancelled" and state["message"].startswith("Stopped.")
    lab.run_job()
    assert lab.nse.asked == []
    assert lab.client.post(f"{BASE}/filings/fetch", json={"symbol": "INFY"}).status_code == 202


@pytest.mark.parametrize("method", ["get", "delete"])
def test_a_job_nobody_knows_is_a_404_in_plain_words(lab: Lab, method: str) -> None:
    response = getattr(lab.client, method)(f"{BASE}/filings/jobs/nope")
    assert response.status_code == 404 and error_of(response)["code"] == "NOT_FOUND"
    assert "no record of that filing job" in error_of(response)["message"]


def test_a_fetched_filing_changes_the_proof_the_next_time_it_is_asked_for(lab: Lab) -> None:
    assert lab.get("/stocks/INFY/proof").json()["verdict"] == "NOT_SCREENED"
    lab.client.post(f"{BASE}/filings/fetch", json={"symbol": "INFY"})
    lab.run_job()
    after = lab.get("/stocks/INFY/proof").json()
    assert after["data_status"] == "VERIFIED_FILING" and after["company_name"] == "INFY Limited"


# ------------------------------------------------------------------------------------- coverage


def test_coverage_says_what_is_screened_what_nse_lists_and_how_new_it_is(lab: Lab) -> None:
    body = lab.get("/filings/coverage").json()
    assert set(body) == {"screened", "total_listed", "newest_filing", "snapshot_built_on", "note"}
    assert body["screened"] == 3 and body["newest_filing"] == "2024-09-30"
    assert body["snapshot_built_on"] == "2026-10-07" and body["note"] is None
    assert isinstance(body["total_listed"], int) and body["total_listed"] > 1000


# ------------------------------------------------------------------------------------- the real app


@pytest.fixture()
def app_root(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[Path]:
    """The real app, run against a temporary app folder, with no prices loaded and no NSE."""
    from quant_system.server.v2 import paths, router, shariah_wiring

    root = tmp_path / "app"
    monkeypatch.setenv("QUANTOS_APP_ROOT", str(root))
    monkeypatch.setattr(
        proof_paths, "REPO_ROOT", tmp_path / "checkout"
    )  # no bundle unless a test places one
    monkeypatch.setattr(paths, "fixed_drive_roots", lambda: [])
    monkeypatch.setattr(paths, "_user_folders", lambda: [])
    monkeypatch.setattr(paths, "data_scan", paths.DataFolderScan())
    use_runtime(None)
    router.reset_services()
    shariah_wiring.reset_proof_runtime()
    yield root
    shariah_wiring.reset_proof_runtime()
    router.reset_services()


def secure(client: TestClient) -> dict[str, str]:
    """The anti-forgery header the real app asks of every request that changes something."""
    return {"X-CSRF-Token": client.get("/api/v1/csrf-token").json()["csrf_token"]}


def real_app(monkeypatch: pytest.MonkeyPatch, nse: FakeNse | None = None) -> TestClient:
    from quant_system.server.app import app
    from quant_system.server.v2 import shariah_wiring

    monkeypatch.setattr(shariah_wiring, "_live_source", lambda: nse or FakeNse())
    return TestClient(app, base_url="http://localhost:8000")


def place_snapshot(root: Path, filings: Any = None) -> Path:
    target = root / "data" / SNAPSHOT_FILE
    target.parent.mkdir(parents=True, exist_ok=True)
    write_snapshot(target, standard_filings() if filings is None else filings, "2026-10-07")
    return target


def test_the_routes_are_mounted_where_the_screens_call_them(
    app_root: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    place_snapshot(app_root)
    with real_app(monkeypatch) as client:
        proof = client.get(f"{BASE}/stocks/TCS/proof").json()
        assert proof["data_status"] == "STALE" or proof["data_status"] == "VERIFIED_FILING"
        assert proof["filing"]["source_url"].startswith("https://nsearchives.nseindia.com/")
        statuses = client.get(f"{BASE}/status?symbols=TCS,NOPE").json()["statuses"]
        assert statuses["NOPE"]["verdict"] == "NOT_SCREENED"
        assert client.get(f"{BASE}/filings/coverage").json()["snapshot_built_on"] == "2026-10-07"


def test_without_a_bundled_snapshot_everything_still_works_and_says_so(
    app_root: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    with real_app(monkeypatch) as client:
        coverage = client.get(f"{BASE}/filings/coverage").json()
        assert coverage["screened"] == 0 and coverage["snapshot_built_on"] is None
        assert "no bundled company filings yet" in coverage["note"]
        assert (
            client.get(f"{BASE}/status?symbols=NOPE").json()["statuses"]["NOPE"]["verdict"]
            == "NOT_SCREENED"
        )
        assert client.get(f"{BASE}/stocks/NOPE/proof").status_code == 200


def test_a_fetched_filing_is_saved_in_the_persons_own_data_folder_not_in_the_bundle(
    app_root: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    placed = place_snapshot(app_root, {})
    before = placed.read_bytes()
    with real_app(monkeypatch) as client:
        sent = client.post(f"{BASE}/filings/fetch", json={"symbol": "TCS"}, headers=secure(client))
        assert sent.status_code == 202
        state = finished(client, sent.json()["job_id"])
        assert state["status"] == "done"
        assert client.get(f"{BASE}/stocks/TCS/proof").json()["filing"]["period_end"] == "2024-09-30"
    saved = app_root / "data" / "quantos2" / "shariah_filings.sqlite"
    assert saved.is_file() and placed.read_bytes() == before  # the bundle is read only


def finished(client: TestClient, job_id: str) -> dict[str, Any]:
    """The job's state once its own thread has ended: the test joins the thread, it never waits on the clock."""
    for worker in [t for t in threading.enumerate() if t.name == "shariah-filings"]:
        worker.join(10)
    return dict(client.get(f"{BASE}/filings/jobs/{job_id}").json())


def real_snapshot() -> Path | None:
    """The real bundled snapshot in the repository."""
    repo = Path(__file__).resolve().parents[2] / "data" / SNAPSHOT_FILE
    return repo if repo.is_file() else None


def test_the_real_bundled_snapshot_serves_real_filings_through_the_real_app(
    app_root: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    snapshot = real_snapshot()
    assert snapshot is not None, "the bundled filings snapshot is missing from the repository"
    target = app_root / "data" / SNAPSHOT_FILE
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(snapshot, target)
    with gzip.open(target) as handle:
        assert handle.read(1) == b"{"
    with real_app(monkeypatch) as client:
        coverage = client.get(f"{BASE}/filings/coverage").json()
        assert coverage["screened"] > 100 and coverage["snapshot_built_on"]
        proof = client.get(f"{BASE}/stocks/TCS/proof").json()
        assert proof["filing"]["sha256"] and proof["filing"]["source_url"].startswith(
            "https://nsearchives"
        )
        assert proof["verdict"] in {"COMPLIANT", "NON_COMPLIANT", "QUESTIONABLE"}
        bank = client.get(f"{BASE}/stocks/KOTAKBANK/proof").json()
        assert bank["verdict"] == "NON_COMPLIANT" and bank["standards"] == []
        everyone = ",".join(["TCS", "INFY", "RELIANCE", "KOTAKBANK", "ITC", "NOPE"])
        rows = client.get(f"{BASE}/status?symbols={everyone}").json()["statuses"]
        assert (
            rows["KOTAKBANK"]["verdict"] == "NON_COMPLIANT"
            and rows["NOPE"]["verdict"] == "NOT_SCREENED"
        )


def test_the_wiring_names_the_price_data_now_loaded_so_a_new_download_is_noticed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from types import SimpleNamespace

    from quant_system.server.v2 import router, shariah_wiring

    index_file = tmp_path / "index-1.sqlite"
    index_file.write_bytes(b"first build")
    index = SimpleNamespace(current_path=lambda: index_file)
    monkeypatch.setattr(router, "services", lambda: SimpleNamespace(index=index))
    prices = shariah_wiring._AppBars()
    first = prices.version()
    index_file.write_bytes(b"a second, larger build")
    assert first.startswith("index-1.sqlite:") and prices.version() != first
    index.current_path = lambda: None  # type: ignore[assignment]
    assert prices.version() == "none"
