"""The Copilot's supporting pieces: the halal data source, provider keys, background jobs, and error passthrough."""

from __future__ import annotations

import hashlib
import sqlite3
from collections.abc import Callable
from datetime import date
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace

import pytest

from quant_system.copilot.factpack import build_fact_pack
from quant_system.copilot.providers import build_models, default_model, provider_status
from quant_system.copilot.recipes import RECIPES
from quant_system.copilot.registry import Param, ToolRegistry, ToolSpec, UserFacingError
from quant_system.copilot.sources import SqliteShariahSource
from quant_system.copilot.tools import default_registry
from quant_system.copilot.verify import VerifyOptions, verify_stock
from quant_system.copilot.verify_jobs import MAX_RUNNING, TooBusyError, VerifyJobs, Work
from quant_system.copilot.verify_opinion import Opinion
from quant_system.copilot.verify_summary import VerificationResult
from quant_system.lab.costs import BrokerCharges
from quant_system.server.v2 import copilot_wiring, router
from quant_system.server.v2.tools import trade_costs
from tests.copilot_fakes import SAMPLE_ROW, StubModel, make_context, opinion_json

CANARY = "canary-ai-value-ZZ99"


def _database(tmp_path: Path) -> Path:
    path = tmp_path / "shariah.sqlite"
    columns = ", ".join(f"{name} TEXT" for name in SAMPLE_ROW)
    with sqlite3.connect(path) as conn:
        conn.execute(f"CREATE TABLE companies ({columns})")
        conn.execute(
            f"INSERT INTO companies VALUES ({', '.join('?' for _ in SAMPLE_ROW)})",
            tuple(SAMPLE_ROW.values()),
        )
    return path


def _source(path: Path) -> SqliteShariahSource:
    return SqliteShariahSource(lambda: sqlite3.connect(path))


# ------------------------------------------------------------------------------------- halal data source


@pytest.mark.parametrize("symbol", ["AAA", "aaa", " AAA ", "AAA.NS"])
def test_a_company_is_found_by_symbol_in_any_case_or_by_its_ticker(
    tmp_path: Path, symbol: str
) -> None:
    row = _source(_database(tmp_path)).company(symbol)
    assert row is not None and row["company_name"] == "Alpha Ltd"


def test_an_unknown_company_is_none_and_the_count_is_right(tmp_path: Path) -> None:
    source = _source(_database(tmp_path))
    assert source.company("ZZZ") is None and source.company_count() == 1


def test_a_symbol_cannot_inject_sql(tmp_path: Path) -> None:
    assert _source(_database(tmp_path)).company("x' OR '1'='1") is None


def test_an_unreadable_database_becomes_a_plain_message_not_a_stack_trace(tmp_path: Path) -> None:
    broken = SqliteShariahSource(
        lambda: sqlite3.connect(tmp_path / "empty.sqlite")
    )  # no companies table
    with pytest.raises(UserFacingError) as raised:
        broken.company("AAA")
    message = "Close QuantOS, open it again and ask once more."
    assert message in str(raised.value) and "sqlite" not in str(raised.value).lower()
    registry = default_registry(make_context(shariah=broken))
    result = registry.call("shariah_check", {"symbol": "AAA"})
    assert not result.ok and message in (result.error or "")


# ------------------------------------------------------------------------------------- providers


def _keys(**saved: str) -> object:
    return lambda provider: saved.get(provider)


def test_a_provider_is_ready_only_when_it_has_a_non_blank_key_and_no_key_is_ever_returned() -> None:
    status = provider_status(_keys(openai=CANARY, groq="   "))  # type: ignore[arg-type]
    ready = {p["id"]: p["ready"] for p in status}
    assert ready["openai"] is True and ready["groq"] is False and ready["anthropic"] is False
    assert CANARY not in str(status)


def test_models_are_built_for_known_providers_with_keys_and_nothing_else() -> None:
    lookup = _keys(openai=CANARY, anthropic=CANARY)
    models = build_models(lookup, ["openai", "nonsense", "groq", "openai", "anthropic"])  # type: ignore[arg-type]
    assert [m.provider for m in models] == ["openai", "anthropic"]
    assert CANARY not in repr(models)


def test_the_chat_uses_the_first_preferred_provider_that_has_a_key() -> None:
    chosen = default_model(_keys(openai=CANARY, anthropic=CANARY))  # type: ignore[arg-type]
    assert chosen is not None and chosen.provider == "anthropic"
    assert default_model(_keys()) is None  # type: ignore[arg-type]


# ------------------------------------------------------------------------------------- background jobs


class _Inline:
    """Runs a job to completion at once, so a test needs no waiting."""

    def __call__(self, task: object) -> None:
        task()  # type: ignore[operator]


def _work(models: list[StubModel]) -> Work:
    pack = build_fact_pack(default_registry(make_context()), "AAA")

    def work(
        on_opinion: Callable[[Opinion], None], cancelled: Callable[[], bool]
    ) -> VerificationResult:
        options = VerifyOptions(recheck=False, cancelled=cancelled)
        return verify_stock(models, pack, options, on_opinion)

    return work


def test_a_finished_job_reports_done_with_its_result_and_full_progress() -> None:
    jobs = VerifyJobs(spawn=_Inline())
    job_id = jobs.start(
        _work([StubModel("p0", opinion_json()), StubModel("p1", opinion_json())]), 2
    )
    found = jobs.get(job_id)
    assert (
        found is not None
        and found["status"] == "done"
        and found["progress"] == {"done": 2, "total": 2}
    )
    assert found["result"]["symbol"] == "AAA" and found["error"] is None


def test_a_job_that_crashes_reports_a_plain_failure_and_not_the_exception() -> None:
    def crash(_on: object, _cancelled: object) -> VerificationResult:
        raise RuntimeError("boom at /secret/path")

    jobs = VerifyJobs(spawn=_Inline())
    found = jobs.get(jobs.start(crash, 3))
    assert found is not None and found["status"] == "failed" and "/secret/path" not in str(found)
    assert "Settings, then AI" in str(found["error"])


def test_an_unknown_job_is_none() -> None:
    assert VerifyJobs(spawn=_Inline()).get("nope") is None


def test_only_a_few_jobs_run_at_once() -> None:
    jobs = VerifyJobs(spawn=lambda _task: None)  # never finishes
    started = [jobs.start(_work([]), 1) for _ in range(MAX_RUNNING)]
    assert len(set(started)) == MAX_RUNNING
    with pytest.raises(TooBusyError):
        jobs.start(_work([]), 1)


def test_finished_jobs_are_forgotten_after_a_while() -> None:
    now = [0.0]
    jobs = VerifyJobs(clock=lambda: now[0], spawn=_Inline())
    old = jobs.start(_work([StubModel("p0", opinion_json())]), 1)
    now[0] = 99999.0
    jobs.start(_work([StubModel("p0", opinion_json())]), 1)
    assert jobs.get(old) is None


# ------------------------------------------------------------------------------------- error passthrough


def test_a_tool_can_refuse_with_a_message_already_written_for_the_person() -> None:
    def refuse(_args: object) -> object:
        raise UserFacingError("Add some holdings first, on the Portfolio screen.")

    spec = ToolSpec("t", "T", "d", (Param("symbol", "str", "s"),), refuse)  # type: ignore[arg-type]
    result = ToolRegistry([spec]).call("t", {"symbol": "X"})
    assert not result.ok and result.error == "Add some holdings first, on the Portfolio screen."


# ------------------------------------------------------------------------------------- recipes


def test_a_recipe_never_asks_the_model_to_say_what_looks_fine() -> None:
    text = " ".join(recipe.instructions for recipe in RECIPES)
    assert "looks fine" not in text
    assert "what the facts show and what to double-check" in text


# ------------------------------------------------------------------------------------- the app's data, as the tools see it


@pytest.fixture()
def app_data(monkeypatch: pytest.MonkeyPatch) -> SimpleNamespace:
    """The few things the wiring asks the running app for, replaced by plain stand-ins."""
    data = SimpleNamespace(holdings=[object()], ready=True, books=[])
    state = SimpleNamespace(
        settings=lambda: None, holdings=lambda: data.holdings, watchlist=lambda: []
    )
    index = SimpleNamespace(is_ready=lambda: data.ready)
    paper = SimpleNamespace(summaries=lambda _index: data.books)
    monkeypatch.setattr(
        router, "services", lambda: SimpleNamespace(state=state, index=index, paper=paper)
    )
    monkeypatch.setattr(router, "_broker", lambda _settings: BrokerCharges())
    monkeypatch.setattr(router, "_today", lambda: date(2026, 9, 28))
    return data


COST_ARGS = {"segment": "delivery", "buy_price": 100, "sell_price": 105, "quantity": 10}


def test_trading_costs_come_back_in_percent_points_not_as_fractions(
    app_data: SimpleNamespace,
) -> None:
    raw = trade_costs(
        "delivery", Decimal(100), Decimal(105), 10, date(2026, 9, 28), BrokerCharges()
    )
    result = copilot_wiring._costs(COST_ARGS)
    assert result["breakeven_move_pct"] == pytest.approx(raw["breakeven_move_pct"] * 100, abs=0.001)
    assert result["charges_pct_of_turnover"] == pytest.approx(
        raw["charges_pct_of_turnover"] * 100, abs=0.001
    )
    assert (
        0.05 < result["breakeven_move_pct"] < 5
    )  # a real break-even is a fraction of a percent, not 0.003


def test_a_position_size_comes_back_in_percent_points(app_data: SimpleNamespace) -> None:
    result = copilot_wiring._size({"capital": 100000, "risk_pct": 1, "entry": 100, "stop": 95})
    assert result["stop_distance_pct"] == pytest.approx(5.0)
    assert result["capital_used_pct"] == pytest.approx(20.0)
    assert result["quantity"] == 200


def test_a_portfolio_comes_back_in_percent_points_with_a_name_that_says_so(
    app_data: SimpleNamespace, monkeypatch: pytest.MonkeyPatch
) -> None:
    row = {"symbol": "AAA", "quantity": 5, "avg_price": 90.0, "close": 100.0, "value": 500.0}
    holding = {**row, "pnl": 50.0, "pnl_pct": 0.1111, "weight": 0.625, "vs_nifty": {"x": 1}}
    summary = {
        "totals": {"value": 800.0, "cost": 648.0, "pnl": 152.0, "pnl_pct": 0.234567},
        "warnings": ["AAA is 62% of your portfolio (above 40%)."],
        "holdings": [holding],
    }
    monkeypatch.setattr(copilot_wiring, "portfolio_summary", lambda *_args: summary)
    result = copilot_wiring._portfolio()
    assert result["totals"]["pnl_pct"] == pytest.approx(23.46)
    assert result["holdings"][0]["pnl_pct"] == pytest.approx(11.11)
    assert result["holdings"][0]["weight_pct"] == pytest.approx(62.5)
    assert "weight" not in result["holdings"][0] and "vs_nifty" not in result["holdings"][0]


def test_paper_books_come_back_in_percent_points_with_names_that_say_so(
    app_data: SimpleNamespace,
) -> None:
    app_data.books = [
        {
            "name": "Mine",
            "status": "RUNNING",
            "return": 0.0123,
            "benchmark_return": 0.01,
            "excess": 0.0023,
        }
    ]
    book = copilot_wiring._paper_books()[0]
    assert book["return_pct"] == pytest.approx(1.23)
    assert book["benchmark_return_pct"] == pytest.approx(1.0)
    assert book["excess_pct"] == pytest.approx(0.23)
    assert not {"return", "benchmark_return", "excess"} & set(book)


@pytest.mark.parametrize("quantity", [10.7, 0.5, 1e-9, float("nan"), float("inf")])
def test_a_quantity_that_is_not_a_whole_number_is_refused_not_cut_short(
    app_data: SimpleNamespace, quantity: float
) -> None:
    with pytest.raises(UserFacingError, match="whole number of shares"):
        copilot_wiring._costs({**COST_ARGS, "quantity": quantity})


def test_a_whole_quantity_written_with_a_decimal_point_is_accepted(
    app_data: SimpleNamespace,
) -> None:
    assert copilot_wiring._costs({**COST_ARGS, "quantity": 10.0})["quantity"] == 10


@pytest.mark.parametrize("bad", [float("nan"), float("inf")])
def test_numbers_that_are_not_real_numbers_get_the_plain_message(
    app_data: SimpleNamespace, bad: float
) -> None:
    with pytest.raises(UserFacingError, match="could not be used"):
        copilot_wiring._size({"capital": bad, "risk_pct": 1, "entry": 100, "stop": 95})


def test_without_market_data_the_message_names_the_settings_tab_as_the_app_does(
    app_data: SimpleNamespace,
) -> None:
    app_data.ready = False
    with pytest.raises(UserFacingError, match="Open Settings, then Market data."):
        copilot_wiring._portfolio()
    with pytest.raises(UserFacingError, match="Open Settings, then Market data."):
        copilot_wiring._paper_books()


# ------------------------------------------------------------------------------------- the halal data is only ever read


def _padded_database(path: Path, journal: str) -> Path:
    """A halal database big enough to count as populated, in the given journal mode."""
    path.parent.mkdir(parents=True, exist_ok=True)
    columns = ", ".join(f"{name} TEXT" for name in SAMPLE_ROW)
    row = {**SAMPLE_ROW, "business_summary": "x" * 20_000}
    conn = sqlite3.connect(path)
    conn.execute(f"PRAGMA journal_mode = {journal}")
    conn.execute(f"CREATE TABLE companies ({columns})")
    conn.execute(
        f"INSERT INTO companies VALUES ({', '.join('?' for _ in row)})", tuple(row.values())
    )
    conn.commit()
    conn.close()
    return path


def _fingerprint(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


@pytest.mark.parametrize("journal", ["DELETE", "WAL"])
def test_reading_the_halal_data_changes_nothing_in_the_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, journal: str
) -> None:
    path = _padded_database(tmp_path / "my data #1" / "halal.db", journal)
    monkeypatch.setattr(copilot_wiring, "_shariah_path", lambda: path)
    before = _fingerprint(path)
    source = copilot_wiring._shariah()
    row, count = source.company("AAA"), source.company_count()
    assert row is not None and row["company_name"] == "Alpha Ltd" and count == 1
    assert _fingerprint(path) == before  # the journal mode of the file was not rewritten either


def test_a_rollback_journal_database_gets_no_extra_files_beside_it(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = _padded_database(tmp_path / "halal.db", "DELETE")
    monkeypatch.setattr(copilot_wiring, "_shariah_path", lambda: path)
    copilot_wiring._shariah().company("AAA")
    assert sorted(item.name for item in tmp_path.iterdir()) == ["halal.db"]


def test_the_halal_connection_refuses_every_write(tmp_path: Path) -> None:
    path = _padded_database(tmp_path / "halal.db", "DELETE")
    with pytest.raises(sqlite3.OperationalError, match="readonly"):
        copilot_wiring._open_read_only(path).execute("DELETE FROM companies")


def test_a_missing_halal_database_is_reported_in_plain_words_and_never_created(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    missing = tmp_path / "data" / "halal.db"
    monkeypatch.setattr(copilot_wiring, "_shariah_path", lambda: missing)
    registry = default_registry(make_context(shariah=copilot_wiring._shariah()))
    result = registry.call("shariah_check", {"symbol": "AAA"})
    assert not result.ok and "could not be opened" in (result.error or "")
    assert "sqlite" not in (result.error or "").lower() and not missing.exists()


def test_the_halal_data_is_read_from_the_shariah_packages_own_path_setting(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = tmp_path / "app"
    monkeypatch.setenv("QUANTOS_APP_ROOT", str(root))
    expected = _padded_database(root / "data" / "shariah" / "halal_stocks.db", "DELETE")
    assert copilot_wiring._shariah_path() == expected
    assert copilot_wiring._shariah().company("AAA") is not None
