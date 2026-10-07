"""The "Update and restart" button over HTTP: it starts only what the update check found, and says how it went."""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from quant_system.server.v2 import router, update_routes
from quant_system.server.v2.updater import UpdateInstaller
from quant_system.server.v2.updates import REPOSITORY, UpdateChecker
from tests import test_copilot_routes as _routes
from tests.test_update_install import NAME, SUMS_NAME, Downloads, Inline, Launches

client = _routes.client
headers = _routes.headers
lab = _routes.lab

BASE = f"https://github.com/{REPOSITORY}/releases/download/v2.6.0"
BODY = b"MZ" + b"program " * 5000


def _release() -> dict[str, Any]:
    return {
        "tag_name": "v2.6.0",
        "assets": [
            {"name": NAME, "browser_download_url": f"{BASE}/{NAME}"},
            {"name": SUMS_NAME, "browser_download_url": f"{BASE}/{SUMS_NAME}"},
        ],
    }


@pytest.fixture()
def launched(
    client: TestClient, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> tuple[Downloads, Launches]:
    sums = f"{hashlib.sha256(BODY).hexdigest()}  {NAME}\n".encode()
    served = Downloads({f"{BASE}/{NAME}": BODY, f"{BASE}/{SUMS_NAME}": sums})
    handed = Launches()
    fake = UpdateInstaller(
        tmp_path / "u", opener=served, launch=handed, spawn=Inline(), windows=True
    )
    monkeypatch.setattr(update_routes, "_installer", fake)
    return served, handed


def test_before_anything_is_pressed_the_update_is_idle(
    client: TestClient, launched: tuple[Downloads, Launches]
) -> None:
    assert client.get("/api/v2/updates/install").json()["state"] == "idle"


def test_with_no_newer_release_there_is_nothing_to_install_and_it_says_so(
    client: TestClient, headers: dict[str, str], launched: tuple[Downloads, Launches]
) -> None:
    router.services().updates = UpdateChecker("2.6.0", _release)
    response = client.post("/api/v2/updates/install", headers=headers)
    assert response.status_code == 409 and "no newer version" in response.json()["error"]["message"]
    assert launched[1].paths == []


def test_pressing_the_button_downloads_checks_and_hands_over_the_installer(
    client: TestClient, headers: dict[str, str], launched: tuple[Downloads, Launches]
) -> None:
    router.services().updates = UpdateChecker("2.5.0", _release)
    response = client.post("/api/v2/updates/install", headers=headers)
    assert response.status_code == 202
    assert client.get("/api/v2/updates/install").json()["state"] == "installing"
    assert [p.name for p in launched[1].paths] == [NAME]


def test_a_request_cannot_name_a_different_file_to_download(
    client: TestClient, headers: dict[str, str], launched: tuple[Downloads, Launches]
) -> None:
    router.services().updates = UpdateChecker("2.5.0", _release)
    client.post(
        "/api/v2/updates/install",
        json={"installer_url": "https://evil.example/x.exe"},
        headers=headers,
    )
    assert launched[0].asked == [f"{BASE}/{SUMS_NAME}", f"{BASE}/{NAME}"]


def test_the_button_needs_the_apps_own_page_token(
    client: TestClient, launched: tuple[Downloads, Launches]
) -> None:
    router.services().updates = UpdateChecker("2.5.0", _release)
    assert client.post("/api/v2/updates/install").status_code in (400, 403)
    assert launched[1].paths == []
