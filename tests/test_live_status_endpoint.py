"""`/api/paper-pilot/live-status` must actually answer. (P2 notice, 2026-08-29)

The endpoint referenced `json` and `PROJECT_ROOT`, neither of which existed in the module, so every
call raised `NameError` -- unconditionally, on a route the live dashboard polls. It has since been
repaired, and nothing tested it, so the repair could regress as quietly as the defect arrived.

Driven against the real application, not a mock of it.
"""

from __future__ import annotations

import importlib
import json

import pytest
from fastapi.testclient import TestClient

from quant_system.server.app import app

# `from quant_system.server import app` binds the FastAPI instance the package re-exports, not the
# module that defines it. The handler's missing names live in the module.
app_module = importlib.import_module("quant_system.server.app")


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


def test_the_endpoint_answers_rather_than_raising(client: TestClient) -> None:
    """A NameError here surfaced as a 500 on every poll of the live dashboard."""
    response = client.get("/api/paper-pilot/live-status")

    assert response.status_code == 200
    assert isinstance(response.json(), dict)


def test_a_present_status_file_is_returned(tmp_path, monkeypatch, client: TestClient) -> None:
    runs = tmp_path / "logs" / "paper_runs"
    runs.mkdir(parents=True)
    (runs / "live_paper_status.json").write_text(
        json.dumps({"status": "RUNNING", "cash": "145520.31", "fills_count": 0}), encoding="utf-8"
    )
    monkeypatch.setattr(app_module, "PROJECT_ROOT", tmp_path)

    body = client.get("/api/paper-pilot/live-status").json()

    assert body["status"] == "RUNNING"
    assert body["cash"] == "145520.31"


def test_no_session_is_reported_as_not_running_rather_than_as_an_error(
    tmp_path, monkeypatch, client: TestClient
) -> None:
    """An idle weekend must not look like a broken service."""
    monkeypatch.setattr(app_module, "PROJECT_ROOT", tmp_path)

    body = client.get("/api/paper-pilot/live-status").json()

    assert body["status"] == "NOT_RUNNING"


def test_a_corrupt_status_file_is_reported_rather_than_crashing(
    tmp_path, monkeypatch, client: TestClient
) -> None:
    runs = tmp_path / "logs" / "paper_runs"
    runs.mkdir(parents=True)
    (runs / "live_paper_status.json").write_text("{ truncated", encoding="utf-8")
    monkeypatch.setattr(app_module, "PROJECT_ROOT", tmp_path)

    body = client.get("/api/paper-pilot/live-status").json()

    assert body["status"] == "ERROR"
    assert body["error"]


def test_the_names_the_handler_needs_exist_in_its_module() -> None:
    """The defect exactly: two names referenced in the handler, defined nowhere in the module."""
    assert hasattr(app_module, "json")
    assert hasattr(app_module, "PROJECT_ROOT")
    assert (app_module.PROJECT_ROOT / "pyproject.toml").is_file(), (
        f"PROJECT_ROOT resolves to {app_module.PROJECT_ROOT}, which is not the repository root; "
        "the status file would be looked for in the wrong place"
    )
