"""Liveness and readiness: what a monitor, or a person on a bad morning, reads to learn what is wrong."""

from __future__ import annotations

import json
from collections.abc import Iterator
from datetime import date
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from quant_system.server.app import app
from quant_system.server.v2 import health, paths, router
from tests.market_fixtures import build_standard_store

TODAY = date(2026, 10, 5)


def _calendar(folder: Path, years: list[int]) -> None:
    (folder / "authorities").mkdir(parents=True, exist_ok=True)
    (folder / "authorities" / "nse-trading-holidays.json").write_text(
        json.dumps({"covers_years": [str(y) for y in years], "holidays": []}), encoding="utf-8"
    )


# ---------------------------------------------------------------------------- the calendar


def test_a_calendar_with_plenty_of_time_left_is_fine(tmp_path: Path) -> None:
    _calendar(tmp_path, [2026, 2027])
    check = health.holiday_calendar_check(tmp_path, TODAY)
    assert check.status == "ok" and "2027" in check.detail


def test_a_calendar_about_to_run_out_warns_in_words(tmp_path: Path) -> None:
    _calendar(tmp_path, [2026])
    check = health.holiday_calendar_check(tmp_path, TODAY)
    assert check.status == "degraded"
    assert "31 Dec 2026" in check.detail and "87 days" in check.detail
    assert "refuse to run" in check.detail


def test_the_warning_starts_exactly_ninety_days_out(tmp_path: Path) -> None:
    _calendar(tmp_path, [2026])
    assert (
        health.holiday_calendar_check(tmp_path, date(2026, 10, 2)).status == "degraded"
    )  # 90 days
    assert health.holiday_calendar_check(tmp_path, date(2026, 10, 1)).status == "ok"  # 91 days


def test_a_calendar_that_does_not_cover_this_year_fails(tmp_path: Path) -> None:
    _calendar(tmp_path, [2026])
    check = health.holiday_calendar_check(tmp_path, date(2027, 1, 4))
    assert check.status == "fail" and "does not cover 2027" in check.detail


@pytest.mark.parametrize("content", [None, "{not json", json.dumps({"holidays": []})])
def test_a_missing_or_broken_calendar_is_degraded_not_a_crash(
    tmp_path: Path, content: str | None
) -> None:
    if content is not None:
        (tmp_path / "authorities").mkdir()
        (tmp_path / "authorities" / "nse-trading-holidays.json").write_text(
            content, encoding="utf-8"
        )
    assert health.holiday_calendar_check(tmp_path, TODAY).status == "degraded"


def test_no_connected_data_means_no_calendar() -> None:
    assert health.holiday_calendar_check(None, TODAY).status == "degraded"


# ---------------------------------------------------------------------------------- the data


def test_fresh_prices_are_ok_and_old_prices_are_degraded() -> None:
    assert health.market_data_check("2026-10-02", TODAY).status == "ok"
    old = health.market_data_check("2026-08-21", TODAY)
    assert old.status == "degraded" and "out of date" in old.detail
    assert health.market_data_check(None, TODAY).status == "degraded"


def test_the_overall_status_is_the_worst_check() -> None:
    ok = health.Check("a", "ok", "")
    warn = health.Check("b", "degraded", "")
    bad = health.Check("c", "fail", "")
    assert health.rollup([ok]) == "ok"
    assert health.rollup([ok, warn]) == "degraded"
    assert health.rollup([ok, warn, bad]) == "fail"


# ------------------------------------------------------------------------------- the routes


@pytest.fixture()
def client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[TestClient]:
    monkeypatch.setenv("QUANTOS_APP_ROOT", str(tmp_path / "app"))
    monkeypatch.setattr(paths, "fixed_drive_roots", lambda: [])
    monkeypatch.setattr(paths, "_user_folders", lambda: [])
    monkeypatch.setattr(paths, "data_scan", paths.DataFolderScan())
    router.reset_services()
    with TestClient(app, base_url="http://localhost:8000") as test_client:
        yield test_client
    router.reset_services()


def test_liveness_needs_no_data_and_no_token(client: TestClient) -> None:
    response = client.get("/api/v2/health/live")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok" and body["version"] and body["time_utc"].endswith("+00:00")


def test_a_fresh_install_is_degraded_but_up(client: TestClient) -> None:
    response = client.get("/api/v2/health/ready")
    assert response.status_code == 200  # a probe must not restart an app that is merely empty
    body = response.json()
    assert body["status"] == "degraded"
    by_name = {c["name"]: c for c in body["checks"]}
    assert by_name["state_store"]["status"] == "ok"
    assert by_name["market_index"]["status"] == "degraded"
    assert by_name["market_data"]["status"] == "degraded"


def test_with_data_connected_the_index_check_is_ok(client: TestClient, tmp_path: Path) -> None:
    folder = tmp_path / "workspace" / "data"
    build_standard_store(folder)
    token = client.get("/api/v1/csrf-token").json()["csrf_token"]
    headers = {"X-CSRF-Token": token}
    client.post("/api/v2/data/folder", json={"path": str(folder)}, headers=headers)
    client.post("/api/v2/data/index/build", headers=headers)
    router.services().job.wait(60)
    body = client.get("/api/v2/health/ready").json()
    by_name = {c["name"]: c for c in body["checks"]}
    assert by_name["market_index"]["status"] == "ok"
    assert "Indexed 4 symbols" in by_name["market_index"]["detail"]
    assert by_name["market_data"]["status"] == "degraded"  # the fixture's prices are from 2021


def test_an_unreadable_state_store_is_the_one_thing_that_returns_503(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    def broken() -> None:
        raise RuntimeError("database disk image is malformed")

    monkeypatch.setattr(router.services().state, "settings", broken)
    response = client.get("/api/v2/health/ready")
    assert response.status_code == 503
    body = response.json()
    assert body["status"] == "fail"
    assert any("malformed" in c["detail"] for c in body["checks"])


def test_the_probes_are_reachable_without_the_csrf_token(client: TestClient) -> None:
    """A read-only probe must work for a monitor that has never made a request before."""
    assert client.get("/api/v2/health/live").status_code == 200
    assert client.get("/api/v2/health/ready").status_code == 200
