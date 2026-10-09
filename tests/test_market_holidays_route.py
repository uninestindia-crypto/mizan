"""The trading-holiday list the top bar reads: what it says, and that it says nothing when it cannot be trusted."""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from quant_system.server.app import app
from quant_system.server.v2 import market_holidays
from quant_system.server.v2.market_holidays import HOLIDAY_FILE, holiday_list

SHIPPED = Path(__file__).resolve().parents[1] / "data" / HOLIDAY_FILE
NOTHING = {"years": [], "holidays": [], "source": None, "fetched_at": None}


@pytest.fixture
def client() -> TestClient:
    return TestClient(app, base_url="http://localhost:8000")


def _write(root: Path, document: Any) -> Path:
    path = root / "data" / HOLIDAY_FILE
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        document if isinstance(document, str) else json.dumps(document), encoding="utf-8"
    )
    return path


def _good(**over: Any) -> dict[str, Any]:
    document: dict[str, Any] = {
        "authority": "NSE trading holidays, Capital Market (CM) segment",
        "covers_years": ["2026"],
        "fetched_at_utc": "2026-08-30T09:21:11+00:00",
        "holidays": [
            {"date": "2026-10-20", "description": "Dussehra"},
            {"date": "2026-01-26", "description": "Republic Day"},
        ],
    }
    document.update(over)
    return document


def _only(monkeypatch: pytest.MonkeyPatch, *roots: Path) -> None:
    monkeypatch.setattr(market_holidays, "_roots", lambda: list(roots))


class TestTheShippedList:
    def test_the_route_answers_with_dated_names_and_the_years_they_cover(
        self, client: TestClient
    ) -> None:
        response = client.get("/api/v2/market/holidays")
        assert response.status_code == 200
        body = response.json()
        assert body["years"] == [2026]
        assert {"date": "2026-01-26", "name": "Republic Day"} in body["holidays"]
        assert {"date": "2026-10-20", "name": "Dussehra"} in body["holidays"]
        assert body["source"] == "NSE trading holidays, Capital Market (CM) segment"

    def test_it_is_the_whole_authority_file_in_date_order_without_repeats(self) -> None:
        raw = json.loads(SHIPPED.read_text(encoding="utf-8"))
        answer = holiday_list()
        days = [h["date"] for h in answer["holidays"]]
        assert len(days) == raw["holiday_count"] == len(raw["holidays"])
        assert days == sorted(set(days))
        assert answer["years"] == sorted(int(y) for y in raw["covers_years"])

    def test_every_holiday_falls_in_a_year_the_list_says_it_covers(self) -> None:
        answer = holiday_list()
        assert {date.fromisoformat(h["date"]).year for h in answer["holidays"]} <= set(
            answer["years"]
        )

    def test_a_footnote_mark_is_not_part_of_a_holidays_name(self) -> None:
        names = {h["date"]: h["name"] for h in holiday_list()["holidays"]}
        assert names["2026-11-08"] == "Diwali Laxmi Pujan"
        assert not any(name.endswith("*") for name in names.values())

    def test_the_route_is_declared_for_reading_only(self) -> None:
        routes = [(route.path, route.methods) for route in market_holidays.router.routes]  # type: ignore[attr-defined]
        assert routes == [("/market/holidays", {"GET"})]

    @pytest.mark.parametrize("method", ["post", "put", "patch", "delete"])
    def test_anything_but_a_read_is_refused(self, client: TestClient, method: str) -> None:
        response = getattr(client, method)("/api/v2/market/holidays")
        assert response.status_code in (403, 405)


class TestWhatItWillNotVouchFor:
    def test_no_file_means_nothing_is_known_not_an_error(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, client: TestClient
    ) -> None:
        _only(monkeypatch, tmp_path)
        assert holiday_list() == NOTHING
        response = client.get("/api/v2/market/holidays")
        assert response.status_code == 200
        assert response.json() == NOTHING

    @pytest.mark.parametrize(
        "document",
        [
            "{not json",
            "[]",
            _good(covers_years=[]),
            _good(covers_years=["next year"]),
            _good(covers_years=["20266"]),
            _good(holidays=[{"date": "26 Jan 2026", "description": "Republic Day"}]),
            _good(holidays=[{"date": "2026-01-26", "description": "  *  "}]),
            _good(holidays=[{"description": "Republic Day"}]),
            _good(holidays="Republic Day"),
        ],
        ids=[
            "not json",
            "not an object",
            "no years",
            "a year that is not a number",
            "a year that is not a year",
            "a date that is not a date",
            "a holiday with no name",
            "a holiday with no date",
            "holidays that are not a list",
        ],
    )
    def test_a_list_that_cannot_be_trusted_is_reported_as_unknown(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, document: Any
    ) -> None:
        _write(tmp_path, document)
        _only(monkeypatch, tmp_path)
        assert holiday_list() == NOTHING

    def test_one_bad_entry_spoils_the_list_rather_than_being_skipped(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        bad = _good()
        bad["holidays"].append({"date": "soon", "description": "Mystery day"})
        _write(tmp_path, bad)
        _only(monkeypatch, tmp_path)
        assert holiday_list()["holidays"] == []


class TestWhereItLooks:
    def test_when_two_copies_reach_the_same_year_the_first_one_found_is_used(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        first, second = tmp_path / "first", tmp_path / "second"
        _write(first, _good(holidays=[{"date": "2026-05-01", "description": "Maharashtra Day"}]))
        _write(second, _good())
        _only(monkeypatch, first, second)
        assert holiday_list()["holidays"] == [{"date": "2026-05-01", "name": "Maharashtra Day"}]

    def test_an_old_copy_left_in_a_data_folder_does_not_hide_a_newer_one(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        old, new = tmp_path / "old", tmp_path / "new"
        _write(
            old,
            _good(
                covers_years=["2025"],
                holidays=[{"date": "2025-01-26", "description": "Republic Day"}],
            ),
        )
        _write(new, _good(covers_years=["2026", "2027"]))
        _only(monkeypatch, old, new)
        assert holiday_list()["years"] == [2026, 2027]

    def test_a_damaged_copy_falls_through_to_the_next_good_one(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        first, second = tmp_path / "first", tmp_path / "second"
        _write(first, "{broken")
        _write(second, _good())
        _only(monkeypatch, first, second)
        answer = holiday_list()
        assert answer["years"] == [2026]
        assert [h["date"] for h in answer["holidays"]] == ["2026-01-26", "2026-10-20"]

    def test_the_apps_root_setting_names_a_folder_that_is_looked_in(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _write(
            tmp_path,
            _good(
                covers_years=["2031"],
                holidays=[{"date": "2031-01-26", "description": "Republic Day"}],
            ),
        )
        monkeypatch.setenv("QUANTOS_APP_ROOT", str(tmp_path))
        assert holiday_list()["years"] == [2031]

    def test_each_answer_is_its_own_copy(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _only(monkeypatch, tmp_path)
        holiday_list()["years"].append(1999)
        assert holiday_list() == NOTHING
