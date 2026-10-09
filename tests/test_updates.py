"""The update notice: compares versions, never raises, and only ever reads."""

from __future__ import annotations

import re
from typing import Any

import pytest

from quant_system import __version__
from quant_system.server.v2 import updates
from quant_system.server.v2.updates import UpdateChecker, is_newer, parse_version


def _release(tag: str, **extra: Any) -> dict[str, Any]:
    return {
        "tag_name": tag,
        "html_url": f"https://github.com/o/r/releases/tag/{tag}",
        "body": "## What's new\n- Paper trading",
        "published_at": "2026-10-05T00:00:00Z",
        "assets": [{"name": "quantos-sbom.json"}, {"name": "QuantOS_v2.1.0_Setup.exe"}],
        **extra,
    }


def test_versions_compare_as_numbers_not_text() -> None:
    assert parse_version("v2.10.0") == (2, 10, 0) and parse_version("2.1.0") == (2, 1, 0)
    assert parse_version("v2.1.0-beta") is None and parse_version("latest") is None
    assert is_newer("v2.10.0", "2.9.9") and not is_newer("2.1.0", "2.1.0")
    assert not is_newer("2.0.9", "2.1.0") and not is_newer("garbage", "2.1.0")


def test_a_newer_release_is_reported_with_its_page_notes_and_installer() -> None:
    result = UpdateChecker("2.0.1", lambda: _release("v2.1.0")).check()
    assert result["update_available"] is True and result["latest"] == "2.1.0"
    assert result["url"].endswith("/v2.1.0") and "Paper trading" in result["notes"]
    assert result["installer"] == "QuantOS_v2.1.0_Setup.exe" and result["checked"] is True


def test_the_same_or_an_older_release_is_not_an_update() -> None:
    assert UpdateChecker("2.1.0", lambda: _release("v2.1.0")).check()["update_available"] is False
    assert UpdateChecker("2.2.0", lambda: _release("v2.1.0")).check()["update_available"] is False


def test_drafts_prereleases_and_odd_tags_are_never_offered() -> None:
    for release in (
        _release("v9.9.9", draft=True),
        _release("v9.9.9", prerelease=True),
        _release("nightly"),
    ):
        result = UpdateChecker("2.0.1", lambda release=release: release).check()  # type: ignore[misc]
        assert result["update_available"] is False and result["checked"] is True


def test_a_failed_check_is_quiet_and_retried_soon_not_hours_later() -> None:
    calls = {"n": 0}

    def flaky() -> dict[str, Any] | None:
        calls["n"] += 1
        if calls["n"] == 1:
            raise RuntimeError("offline")
        return _release("v2.1.0")

    checker = UpdateChecker("2.0.1", flaky)
    first = checker.check()
    assert (
        first["checked"] is False and first["update_available"] is False
    )  # no exception, no noise
    assert checker.check()["checked"] is False and calls["n"] == 1  # cached for the moment
    assert checker.check(force=True)["update_available"] is True and calls["n"] == 2


def test_a_good_answer_is_cached_for_hours(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = {"n": 0}

    def fetch() -> dict[str, Any] | None:
        calls["n"] += 1
        return _release("v2.1.0")

    checker = UpdateChecker("2.0.1", fetch)
    checker.check()
    checker.check()
    assert calls["n"] == 1
    monkeypatch.setattr(updates.time, "monotonic", lambda: 10**9)
    checker.check()
    assert calls["n"] == 2  # expired


def test_the_github_cli_is_the_fallback_for_a_private_repository(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(updates, "_public_api", lambda repository: None)  # 404 on a private repo
    monkeypatch.setattr(updates, "_github_cli", lambda repository: _release("v2.1.0"))
    assert updates.fetch_latest_release("o/r") == _release("v2.1.0")
    monkeypatch.setattr(updates, "_github_cli", lambda repository: None)
    assert updates.fetch_latest_release("o/r") is None


def test_the_endpoint_never_errors_even_when_nothing_answers(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Any
) -> None:
    from fastapi.testclient import TestClient

    from quant_system.server.app import app
    from quant_system.server.v2 import router

    monkeypatch.setenv("QUANTOS_APP_ROOT", str(tmp_path / "app"))
    router.reset_services()
    monkeypatch.setattr(updates, "fetch_latest_release", lambda repository="": None)
    with TestClient(app, base_url="http://localhost:8000") as client:
        body = client.get("/api/v2/update").json()
    router.reset_services()
    assert body["update_available"] is False and body["checked"] is False
    assert body["current"]


def test_changelog_returns_history_and_identifies_current_version() -> None:
    checker = UpdateChecker(__version__)
    entries = checker.changelog()
    assert len(entries) >= 6
    assert entries[0]["version"] == __version__
    assert entries[0]["is_current"] is True
    assert len(entries[0]["whats_new"]) > 0
    assert len(entries[0]["unchanged_protections"]) > 0
    assert entries[1]["version"] != __version__
    assert entries[1]["is_current"] is False


def _release_note_lines() -> list[str]:
    keys = ("whats_new", "fixes", "improvements", "unchanged_protections")
    entries = UpdateChecker("2.5.0").changelog()
    return [line for entry in entries for key in keys for line in entry.get(key, [])]


def test_the_release_notes_a_person_reads_do_not_use_the_developers_word_cli() -> None:
    lines = _release_note_lines()
    assert len(lines) > 20
    assert [line for line in lines if re.search(r"\bCLI\b", line)] == []
    assert "Install and sign in to several AI apps with one click" in lines


def test_changelog_api_endpoint(monkeypatch: pytest.MonkeyPatch, tmp_path: Any) -> None:
    from fastapi.testclient import TestClient

    from quant_system.server.app import app
    from quant_system.server.v2 import router

    monkeypatch.setenv("QUANTOS_APP_ROOT", str(tmp_path / "app"))
    router.reset_services()
    with TestClient(app, base_url="http://localhost:8000") as client:
        res = client.get("/api/v2/changelog")
        assert res.status_code == 200
        data = res.json()
        assert isinstance(data, list)
        assert len(data) >= 6
        assert data[0]["version"] == __version__
        assert data[0]["is_current"] is True
        assert data[0]["whats_new"]
        assert data[1]["version"] != __version__
        assert data[1]["is_current"] is False
    router.reset_services()


def test_the_update_check_asks_the_repository_the_releases_are_published_in(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """It once asked an older repository, so an installed app could never see a new release."""
    asked: list[str] = []

    def fake_urlopen(request: Any, timeout: float = 0) -> Any:
        asked.append(request.full_url)
        raise OSError("no network in tests")

    monkeypatch.setattr(updates.urllib.request, "urlopen", fake_urlopen)
    assert updates._public_api(updates.REPOSITORY) is None
    assert asked == ["https://api.github.com/repos/uninestindia-crypto/mizan/releases/latest"]
