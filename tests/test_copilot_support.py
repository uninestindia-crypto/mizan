"""The Copilot's supporting pieces: the halal data source, provider keys, background jobs, and error passthrough."""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from quant_system.copilot.factpack import build_fact_pack
from quant_system.copilot.providers import build_models, default_model, provider_status
from quant_system.copilot.registry import Param, ToolRegistry, ToolSpec, UserFacingError
from quant_system.copilot.sources import SqliteShariahSource
from quant_system.copilot.tools import default_registry
from quant_system.copilot.verify import VerifyOptions, verify_stock
from quant_system.copilot.verify_jobs import MAX_RUNNING, TooBusyError, VerifyJobs
from quant_system.copilot.verify_summary import VerificationResult
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
    assert "Restart QuantOS" in str(raised.value) and "sqlite" not in str(raised.value).lower()
    registry = default_registry(make_context(shariah=broken))
    result = registry.call("shariah_check", {"symbol": "AAA"})
    assert not result.ok and "Restart QuantOS" in (result.error or "")


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


def _work(models: list[StubModel]) -> object:
    pack = build_fact_pack(default_registry(make_context()), "AAA")

    def work(on_opinion: object) -> VerificationResult:
        return verify_stock(models, pack, VerifyOptions(recheck=False), on_opinion)  # type: ignore[arg-type]

    return work


def test_a_finished_job_reports_done_with_its_result_and_full_progress() -> None:
    jobs = VerifyJobs(spawn=_Inline())
    job_id = jobs.start(
        _work([StubModel("p0", opinion_json()), StubModel("p1", opinion_json())]), 2
    )  # type: ignore[arg-type]
    found = jobs.get(job_id)
    assert (
        found is not None
        and found["status"] == "done"
        and found["progress"] == {"done": 2, "total": 2}
    )
    assert found["result"]["symbol"] == "AAA" and found["error"] is None


def test_a_job_that_crashes_reports_a_plain_failure_and_not_the_exception() -> None:
    def crash(_on: object) -> VerificationResult:
        raise RuntimeError("boom at /secret/path")

    jobs = VerifyJobs(spawn=_Inline())
    found = jobs.get(jobs.start(crash, 3))  # type: ignore[arg-type]
    assert found is not None and found["status"] == "failed" and "/secret/path" not in str(found)
    assert "Accounts and keys" in str(found["error"])


def test_an_unknown_job_is_none() -> None:
    assert VerifyJobs(spawn=_Inline()).get("nope") is None


def test_only_a_few_jobs_run_at_once() -> None:
    jobs = VerifyJobs(spawn=lambda _task: None)  # never finishes
    started = [jobs.start(_work([]), 1) for _ in range(MAX_RUNNING)]  # type: ignore[arg-type]
    assert len(set(started)) == MAX_RUNNING
    with pytest.raises(TooBusyError):
        jobs.start(_work([]), 1)  # type: ignore[arg-type]


def test_finished_jobs_are_forgotten_after_a_while() -> None:
    now = [0.0]
    jobs = VerifyJobs(clock=lambda: now[0], spawn=_Inline())
    old = jobs.start(_work([StubModel("p0", opinion_json())]), 1)  # type: ignore[arg-type]
    now[0] = 99999.0
    jobs.start(_work([StubModel("p0", opinion_json())]), 1)  # type: ignore[arg-type]
    assert jobs.get(old) is None


# ------------------------------------------------------------------------------------- error passthrough


def test_a_tool_can_refuse_with_a_message_already_written_for_the_person() -> None:
    def refuse(_args: object) -> object:
        raise UserFacingError("Add some holdings first, on the Portfolio screen.")

    spec = ToolSpec("t", "T", "d", (Param("symbol", "str", "s"),), refuse)  # type: ignore[arg-type]
    result = ToolRegistry([spec]).call("t", {"symbol": "X"})
    assert not result.ok and result.error == "Add some holdings first, on the Portfolio screen."
