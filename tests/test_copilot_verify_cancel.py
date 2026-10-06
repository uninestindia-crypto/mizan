"""Stopping a second opinion really stops it: no new AI calls, the slot is freed, and a late answer changes nothing."""

from __future__ import annotations

from typing import Any

import pytest
from fastapi.testclient import TestClient

from quant_system.copilot import verify
from quant_system.copilot.factpack import build_fact_pack
from quant_system.copilot.tools import default_registry
from quant_system.copilot.verify import VerifyOptions, verify_stock
from quant_system.copilot.verify_jobs import CANCELLED_TEXT, MAX_RUNNING, TooBusyError, VerifyJobs
from quant_system.server.v2 import copilot_routes
from tests import test_copilot_routes as _routes
from tests.copilot_fakes import FakeNews, StubModel, make_context, opinion_json

client = _routes.client  # the same app, folders and fake keys as the route tests
headers = _routes.headers
lab = _routes.lab
ready = _routes.ready

PICK = "Ranked 3rd of 40 by the platform's model."
STOPPED = "You stopped this check."
GONE = "That second opinion is no longer available. Start it again."


def _pack() -> Any:
    return build_fact_pack(default_registry(make_context(news=FakeNews())), "AAA")


class _Done:
    def as_dict(self) -> dict[str, Any]:
        return {"symbol": "AAA"}


def _held() -> tuple[VerifyJobs, list[Any]]:
    """Jobs whose work is only started when the test says so."""
    held: list[Any] = []
    return VerifyJobs(spawn=held.append), held


def _idle(_on_opinion: Any, _cancelled: Any) -> Any:
    return _Done()


# ------------------------------------------------------------------------------------- the panel stops asking


def test_a_second_opinion_stopped_before_it_starts_never_asks_any_model() -> None:
    panel = [StubModel(f"p{i}", opinion_json()) for i in range(3)]
    options = VerifyOptions(pick_context=PICK, cancelled=lambda: True)
    result = verify_stock(panel, _pack(), options)
    assert [m.calls for m in panel] == [[], [], []]
    assert result.answered == 0 and result.consensus == "NONE"


def test_stopping_part_way_through_leaves_the_calls_still_waiting_unasked(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        verify, "MAX_PARALLEL", 1
    )  # one call at a time, so the others are still queued
    stopped: list[bool] = []

    def respond(_system: str, _user: str) -> str:
        stopped.append(True)  # the person clicks Cancel while the first call is out
        return opinion_json()

    model = StubModel("p0", respond)
    options = VerifyOptions(pick_context=PICK, recheck=True, cancelled=lambda: bool(stopped))
    verify_stock([model], _pack(), options)
    assert len(model.calls) == 1


def test_a_call_that_was_skipped_says_the_person_stopped_it() -> None:
    result = verify_stock(
        [StubModel("p0", opinion_json())], _pack(), VerifyOptions(cancelled=lambda: True)
    )
    assert result.verdicts[0].blind.error == STOPPED and not result.verdicts[0].blind.ok


# ------------------------------------------------------------------------------------- the job


def test_a_stopped_job_reads_cancelled_with_a_plain_sentence_and_no_result() -> None:
    jobs, _held_tasks = _held()
    job_id = jobs.start(_idle, 3)
    assert jobs.cancel(job_id) is True
    found = jobs.get(job_id)
    assert found is not None and found["status"] == "cancelled" and found["result"] is None
    assert found["error"] == CANCELLED_TEXT == STOPPED


def test_stopping_twice_changes_nothing_and_stopping_an_unknown_job_is_refused() -> None:
    jobs, _held_tasks = _held()
    job_id = jobs.start(_idle, 3)
    assert (jobs.cancel(job_id), jobs.cancel(job_id)) == (True, True)
    found = jobs.get(job_id)
    assert found is not None and found["status"] == "cancelled"
    assert jobs.cancel("nope") is False


def test_a_job_that_had_already_finished_keeps_its_result() -> None:
    jobs = VerifyJobs(spawn=lambda task: task())
    job_id = jobs.start(_idle, 3)
    assert jobs.cancel(job_id) is True
    found = jobs.get(job_id)
    assert found is not None and found["status"] == "done" and found["result"] == {"symbol": "AAA"}


def test_a_stopped_job_stops_counting_toward_the_limit_at_once() -> None:
    jobs, _held_tasks = _held()
    started = [jobs.start(_idle, 1) for _ in range(MAX_RUNNING)]
    with pytest.raises(TooBusyError):
        jobs.start(_idle, 1)
    jobs.cancel(started[0])
    assert jobs.start(_idle, 1) not in started


def test_cancelling_and_restarting_over_and_over_never_locks_the_person_out() -> None:
    jobs, _held_tasks = _held()
    first = [jobs.start(_idle, 1) for _ in range(MAX_RUNNING)]
    assert [jobs.cancel(job_id) for job_id in first] == [True] * MAX_RUNNING
    second = [jobs.start(_idle, 1) for _ in range(MAX_RUNNING)]
    assert [jobs.cancel(job_id) for job_id in second] == [True] * MAX_RUNNING
    assert len([jobs.start(_idle, 1) for _ in range(MAX_RUNNING)]) == MAX_RUNNING


def test_work_that_has_not_started_when_the_job_is_stopped_never_runs() -> None:
    jobs, held = _held()
    ran: list[bool] = []

    def work(_on_opinion: Any, _cancelled: Any) -> Any:
        ran.append(True)
        return _Done()

    job_id = jobs.start(work, 1)
    jobs.cancel(job_id)
    held[0]()
    assert ran == []


@pytest.mark.parametrize("late", ["result", "failure"])
def test_an_answer_that_arrives_after_the_stop_cannot_overwrite_it(late: str) -> None:
    jobs, held = _held()
    ids: list[str] = []

    def work(_on_opinion: Any, _cancelled: Any) -> Any:
        jobs.cancel(ids[0])  # stopped while the AI services are still thinking
        if late == "failure":
            raise RuntimeError("late failure")
        return _Done()

    ids.append(jobs.start(work, 3))
    held[0]()
    found = jobs.get(ids[0])
    assert found is not None and found["status"] == "cancelled" and found["result"] is None
    assert found["error"] == STOPPED and found["progress"]["done"] == 0


def test_the_work_is_told_when_its_job_has_been_stopped() -> None:
    jobs, held = _held()
    ids: list[str] = []
    seen: list[bool] = []

    def work(_on_opinion: Any, cancelled: Any) -> Any:
        seen.append(cancelled())
        jobs.cancel(ids[0])
        seen.append(cancelled())
        return _Done()

    ids.append(jobs.start(work, 1))
    held[0]()
    assert seen == [False, True]


def test_work_is_also_told_to_stop_once_the_job_is_past_its_deadline() -> None:
    now = [0.0]
    held: list[Any] = []
    jobs = VerifyJobs(clock=lambda: now[0], spawn=held.append, deadline=10.0)
    seen: list[bool] = []

    def work(_on_opinion: Any, cancelled: Any) -> Any:
        now[0] = 11.0
        seen.append(cancelled())
        return _Done()

    jobs.start(work, 1)
    held[0]()
    assert seen == [True]


# ------------------------------------------------------------------------------------- over the wire


def _start(client: TestClient, headers: dict[str, str]) -> str:
    body = {"symbol": "AAA", "providers": ["openai"], "recheck": False}
    response = client.post("/api/v2/copilot/verify", json=body, headers=headers)
    assert response.status_code == 202
    return str(response.json()["job_id"])


def _run_all(tasks: list[Any]) -> None:
    for task in tasks:
        task()


def _cancel(client: TestClient, headers: dict[str, str], job_id: str) -> Any:
    return client.delete(f"/api/v2/copilot/verify/{job_id}", headers=headers)


@pytest.fixture()
def held_jobs(client: TestClient, monkeypatch: pytest.MonkeyPatch, lab: _routes.Lab) -> list[Any]:
    """Second opinions whose work waits for the test. Asks for ``client`` so it is set up after the app's own."""
    assert client
    jobs, held = _held()
    monkeypatch.setattr(copilot_routes, "_jobs", jobs)
    lab.models["openai"] = StubModel("openai", opinion_json())
    return held


@pytest.mark.usefixtures("held_jobs")
def test_the_cancel_route_stops_the_job_and_the_progress_route_says_so(
    ready: TestClient, headers: dict[str, str]
) -> None:
    job_id = _start(ready, headers)
    first, again = _cancel(ready, headers, job_id), _cancel(ready, headers, job_id)
    assert (first.status_code, first.json()) == (200, {"cancelled": True})
    assert (again.status_code, again.json()) == (200, {"cancelled": True})
    found = ready.get(f"/api/v2/copilot/verify/{job_id}").json()
    assert found["status"] == "cancelled" and found["error"] == STOPPED and found["result"] is None


@pytest.mark.usefixtures("held_jobs")
def test_cancelling_a_second_opinion_that_is_not_there_is_a_plain_not_found(
    ready: TestClient, headers: dict[str, str]
) -> None:
    response = _cancel(ready, headers, "nope")
    error = response.json()["error"]
    assert (response.status_code, error["code"], error["message"]) == (404, "NOT_FOUND", GONE)


def test_cancelling_needs_the_security_token(ready: TestClient, held_jobs: list[Any]) -> None:
    response = ready.delete("/api/v2/copilot/verify/anything")
    assert response.status_code in (400, 403) and held_jobs == []


def test_a_stopped_run_never_asks_the_ai_and_three_stops_do_not_block_the_fourth_start(
    ready: TestClient, headers: dict[str, str], held_jobs: list[Any], lab: _routes.Lab
) -> None:
    ids = [_start(ready, headers) for _ in range(MAX_RUNNING)]
    assert [_cancel(ready, headers, job_id).status_code for job_id in ids] == [200] * MAX_RUNNING
    assert _start(ready, headers)
    _run_all(held_jobs[:MAX_RUNNING])  # the stopped work is finally picked up
    assert lab.models["openai"].calls == []
