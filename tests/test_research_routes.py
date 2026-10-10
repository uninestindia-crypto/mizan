"""``/api/v2/research``: the replies the Research screen reads, the plain-language refusals, and the anti-forgery guard on writes."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from quant_system.research import embedding_onnx, research_service
from quant_system.research.embedding_gemma import EmbeddingGemmaProvider
from quant_system.research.research_service import ResearchService
from quant_system.server.app import app as real_app
from quant_system.server.v2 import router as v2_router
from quant_system.server.v2.research_routes import router, set_service

BASE = "/api/v2/research"


@pytest.fixture
def service(tmp_path: Path) -> Iterator[ResearchService]:
    pretend = ResearchService(
        tmp_path / "model",
        tmp_path / "library.json",
        provider_factory=lambda _: EmbeddingGemmaProvider(mode="synthetic"),
        downloader=lambda model_dir, **kwargs: None,
    )
    set_service(pretend)
    yield pretend
    set_service(None)


@pytest.fixture
def client(service: ResearchService) -> TestClient:
    app = FastAPI()
    app.add_exception_handler(v2_router.V2Error, v2_router.v2_error_handler)
    app.include_router(router, prefix="/api/v2")
    return TestClient(app)


def test_the_routes_are_exactly_these() -> None:
    found = {
        (method, route.path)
        for route in router.routes
        for method in getattr(route, "methods", set())
    }
    assert found == {
        ("GET", "/research/status"),
        ("POST", "/research/search"),
        ("POST", "/research/setup"),
        ("POST", "/research/setup/cancel"),
    }


def test_the_routes_are_part_of_the_running_app() -> None:
    assert {
        "/api/v2/research/status",
        "/api/v2/research/search",
        "/api/v2/research/setup",
        "/api/v2/research/setup/cancel",
    } <= set(real_app.openapi()["paths"])


def test_status_shape(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        research_service, "real_model_status", lambda model_dir=None: "NEEDS_DOWNLOAD"
    )
    body = client.get(f"{BASE}/status").json()
    assert set(body) == {"engine", "library", "setup"}
    assert set(body["engine"]) == {"state", "by_meaning", "label", "download_mb"}
    assert body["engine"]["state"] == "NEEDS_DOWNLOAD" and body["engine"]["download_mb"] == 330
    assert body["library"] == {"papers": 5}
    assert set(body["setup"]) == {"state", "percent", "mb_done", "mb_total", "message", "error"}


def test_search_shape(client: TestClient) -> None:
    body = client.post(
        f"{BASE}/search", json={"question": "deflated Sharpe ratio overfitting"}
    ).json()
    assert set(body) == {"question", "results", "engine", "library", "notes"}
    assert body["results"][0]["title"].startswith("The Deflated Sharpe Ratio")
    assert set(body["engine"]) == {"by_meaning", "label"}


def test_an_empty_question_is_refused_in_plain_words(client: TestClient) -> None:
    response = client.post(f"{BASE}/search", json={"question": "   "})
    assert response.status_code == 422
    error = response.json()["error"]
    assert error["code"] == "EMPTY_QUESTION" and error["message"].startswith(
        "Type a question first"
    )


def test_setup_start_and_cancel_reply_with_the_progress_shape(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        research_service, "real_model_status", lambda model_dir=None: "NEEDS_DOWNLOAD"
    )
    started = client.post(f"{BASE}/setup").json()
    assert set(started) == {"state", "percent", "mb_done", "mb_total", "message", "error"}
    cancelled = client.post(f"{BASE}/setup/cancel").json()
    assert set(cancelled) == set(started)


def test_a_copy_without_the_runtime_gets_a_plain_conflict(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        research_service, "real_model_status", lambda model_dir=None: "NOT_INSTALLED"
    )
    monkeypatch.setattr(embedding_onnx, "runtime_available", lambda: False)
    response = client.post(f"{BASE}/setup")
    assert response.status_code == 409 and response.json()["error"]["code"] == "NOT_AVAILABLE"


@pytest.mark.parametrize(
    ("method", "path"),
    [("post", f"{BASE}/search"), ("post", f"{BASE}/setup"), ("post", f"{BASE}/setup/cancel")],
)
def test_every_write_is_refused_without_the_anti_forgery_header(method: str, path: str) -> None:
    client = TestClient(real_app, base_url="http://localhost:8000")
    response: Any = getattr(client, method)(path)
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "CSRF_TOKEN_MISSING"
