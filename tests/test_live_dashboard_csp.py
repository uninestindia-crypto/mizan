"""The live dashboard must run under the app's own Content-Security-Policy.

`/live` carried one 18,000-character inline `<script>`, five inline `onclick=` handlers and a Google
Fonts link. The app sends `script-src 'self'`, which refuses all of them, so under the app (and so
under the desktop Studio) none of the page ran: the clock read `--:--:-- IST` and every panel said
"Loading..." forever. The standalone dashboard script sends no policy, which is why it kept working
and the defect went unseen. These tests pin the invariant that makes the page runnable, rather than
a particular layout.
"""

from __future__ import annotations

import importlib
import json
import re
from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from quant_system.server.app import app
from quant_system.server.ui.live_dashboard import HTML_DASHBOARD

# `quant_system.server` re-exports the FastAPI object under the name `app`, so import the module.
app_module = importlib.import_module("quant_system.server.app")
SCRIPT_URL = "/static/live_dashboard.js"


@pytest.fixture()
def client() -> Iterator[TestClient]:
    with TestClient(app, base_url="http://localhost:8000") as test_client:
        yield test_client


def test_the_page_has_no_inline_script_and_loads_one_from_the_app() -> None:
    inline = re.findall(r"<script(?![^>]*\bsrc=)[^>]*>(.*?)</script>", HTML_DASHBOARD, re.S)
    assert [body for body in inline if body.strip()] == []
    assert f'<script src="{SCRIPT_URL}"' in HTML_DASHBOARD


def test_the_page_has_no_inline_event_handlers() -> None:
    assert re.findall(r"\son[a-z]+\s*=", HTML_DASHBOARD) == []


def test_the_page_loads_nothing_from_another_host() -> None:
    assert re.findall(r'(?:src|href)="https?://', HTML_DASHBOARD) == []


def test_the_app_serves_the_script_it_asks_for(client: TestClient) -> None:
    response = client.get(SCRIPT_URL)
    assert response.status_code == 200
    assert "javascript" in response.headers["content-type"]
    assert "updateDashboard" in response.text


def test_the_policy_the_page_must_satisfy_is_the_policy_the_app_sends(client: TestClient) -> None:
    policy = client.get("/live").headers["content-security-policy"]
    assert "script-src 'self'" in policy and "unsafe-inline" not in policy.split("style-src")[0]


def test_the_script_answers_a_refusal_as_a_refusal_not_as_success() -> None:
    script = Path(app_module.STATIC_DIR / "live_dashboard.js").read_text(encoding="utf-8")
    assert "alert(" not in script
    assert "res.ok" in script and "refused" in script


def test_every_status_url_the_script_polls_is_served_by_the_app(client: TestClient) -> None:
    script = (app_module.STATIC_DIR / "live_dashboard.js").read_text(encoding="utf-8")
    urls = re.findall(r'(?:STATUS_URL|XS_STATUS_URL)\s*=\s*"([^"]+)"', script)
    assert sorted(urls) == ["/api/paper-pilot/live-status", "/api/xs-monthly/status"]
    for url in urls:
        assert client.get(url).status_code == 200, url


@pytest.fixture()
def xs_state(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setattr(app_module, "PROJECT_ROOT", tmp_path)
    directory = tmp_path / "logs" / "xs_monthly_new" / "paper_watch"
    directory.mkdir(parents=True)
    return directory / "state.json"


def test_the_xs_status_is_the_watch_state_as_written(client: TestClient, xs_state: Path) -> None:
    xs_state.write_text(json.dumps({"capital": 1000000, "open": []}), encoding="utf-8")
    assert client.get("/api/xs-monthly/status").json() == {"capital": 1000000, "open": []}


def test_the_xs_status_says_not_running_when_there_is_no_state(
    client: TestClient, xs_state: Path
) -> None:
    body = client.get("/api/xs-monthly/status").json()
    assert body["status"] == "NOT_RUNNING"


def test_the_xs_status_reports_a_corrupt_state_instead_of_crashing(
    client: TestClient, xs_state: Path
) -> None:
    xs_state.write_text("{not json", encoding="utf-8")
    body = client.get("/api/xs-monthly/status").json()
    assert body["status"] == "ERROR" and body["error"]


def test_the_script_hides_the_controls_the_app_cannot_serve(client: TestClient) -> None:
    """The app serves no control endpoint, so the page must discover that rather than show buttons
    that can only fail. The supervised dashboard answers this probe; the app does not."""
    assert client.get("/api/control/available").json() == {"available": False}
    script = (app_module.STATIC_DIR / "live_dashboard.js").read_text(encoding="utf-8")
    assert "/api/control/available" in script and "controls-panel" in script
    assert 'id="controls-panel"' in HTML_DASHBOARD
