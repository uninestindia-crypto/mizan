"""A paper holding carried across a corporate action is found, not silently marked.

Live quotes are never back-adjusted, so a ledger holding pre-action shares at a pre-action cost
marks a 1:1 bonus as a 50% loss and a demerger as the parent's whole fall. HEG's 2026-09-07 demerger
put a Rs 6,124 phantom loss into the XS book that way. Every subject line below is copied from the
NSE records the scheduled refresh stores.
"""

from __future__ import annotations

import importlib.util
import json
import os
from datetime import date
from decimal import Decimal
from pathlib import Path
from typing import Any
from unittest import mock

import pytest

from quant_system.execution.corporate_action_guard import (
    HeldThroughAction,
    load_nse_corporate_actions,
    structural_actions_on_holdings,
)
from quant_system.execution.paper_portfolio import PortfolioHolding

OPENED = date(2026, 9, 2)
TODAY = date(2026, 9, 21)


def _found(subject: str, ex_date: str = "07-Sep-2026", opened: date = OPENED) -> list:
    return structural_actions_on_holdings(
        {"HEG": opened}, TODAY, {"HEG": [{"exDate": ex_date, "subject": subject}]}
    )


def test_the_heg_demerger_that_cost_the_xs_book_is_found() -> None:
    [action] = _found("Demerger")
    assert action.symbol == "HEG"
    assert action.ex_date == date(2026, 9, 7)
    assert action.unsized == ("demerger",)
    assert action.sized == ()


def test_a_bonus_is_found_with_its_ratio_sized() -> None:
    [action] = _found("Bonus 1:1")
    assert action.sized == ("bonus",)
    assert action.unsized == ()


def test_a_split_is_found_with_its_ratio_sized() -> None:
    [action] = _found(
        "Face Value Split (Sub-Division) - From Rs 10/- Per Share To Rs 2/- Per Share"
    )
    assert action.sized == ("split",)


def test_a_rights_issue_is_found_as_unsized() -> None:
    """NSE prints the ratio but not the subscription price that sizes a rights issue."""
    [action] = _found("Rights 3:25 @ Premium Rs 1799/-")
    assert action.unsized == ("rights",)


def test_a_scheme_of_demerger_is_found() -> None:
    [action] = _found(" Scheme Of Demerger")
    assert "demerger" in action.unsized


def test_dividends_meetings_and_buybacks_cannot_make_the_share_count_wrong() -> None:
    for subject in (
        "Dividend - Rs 3.40 Per Share",
        "Annual General Meeting/Dividend - Rs 22.50 Per Share",
        "Annual General Meeting",
        "Buy Back",
    ):
        assert _found(subject) == [], subject


def test_an_action_on_the_day_the_holding_opened_was_already_in_its_price() -> None:
    assert _found("Bonus 1:1", ex_date="02-Sep-2026") == []


def test_an_action_before_the_holding_opened_is_ignored() -> None:
    """HEG's 2024 split is in its record; a 2026 holding was bought at post-split prices."""
    subject = "Face Value Split (Sub-Division) - From Rs 10/- Per Share To Rs 2/- Per Share"
    assert _found(subject, ex_date="18-Oct-2024") == []


def test_an_action_after_today_has_not_happened_yet() -> None:
    assert _found("Bonus 1:1", ex_date="22-Sep-2026") == []


def test_an_action_on_today_is_already_in_effect() -> None:
    [action] = _found("Bonus 1:1", ex_date="21-Sep-2026")
    assert action.ex_date == TODAY


def test_a_record_without_a_usable_ex_date_is_not_guessed() -> None:
    for ex_date in ("-", "", "2026-09-07", None):
        assert _found("Bonus 1:1", ex_date=ex_date) == [], ex_date  # type: ignore[arg-type]


def test_the_same_action_listed_twice_is_reported_once() -> None:
    record = {"exDate": "07-Sep-2026", "subject": "Demerger"}
    found = structural_actions_on_holdings({"HEG": OPENED}, TODAY, {"HEG": [record, dict(record)]})
    assert len(found) == 1


def test_only_held_names_are_examined() -> None:
    records = {"OTHER": [{"exDate": "07-Sep-2026", "subject": "Demerger"}]}
    assert structural_actions_on_holdings({"HEG": OPENED}, TODAY, records) == []


def test_the_description_names_the_symbol_the_dates_and_the_kind() -> None:
    [action] = _found("Demerger")
    text = action.describe()
    assert "HEG" in text and "2026-09-02" in text and "2026-09-07" in text and "demerger" in text


def test_a_missing_record_file_is_reported_missing_not_empty(tmp_path) -> None:
    """'No record' is not 'no corporate action'; the ee1b0cb3 repair removed exactly that reading."""
    (tmp_path / "nse-corporate-actions-HEG.json").write_text(
        json.dumps([{"exDate": "07-Sep-2026", "subject": "Demerger"}]), encoding="utf-8"
    )
    records, missing = load_nse_corporate_actions(tmp_path, ["HEG", "ABSENT"])
    assert missing == ["ABSENT"]
    assert "ABSENT" not in records
    assert records["HEG"][0]["subject"] == "Demerger"


def test_symbols_with_an_ampersand_load_under_their_own_name(tmp_path) -> None:
    (tmp_path / "nse-corporate-actions-M&M.json").write_text("[]", encoding="utf-8")
    records, missing = load_nse_corporate_actions(tmp_path, ["M&M"])
    assert records == {"M&M": []}
    assert missing == []


def test_an_unreadable_or_malformed_file_is_reported_missing(tmp_path) -> None:
    (tmp_path / "nse-corporate-actions-BAD.json").write_text("{not json", encoding="utf-8")
    (tmp_path / "nse-corporate-actions-OBJ.json").write_text('{"data": []}', encoding="utf-8")
    _records, missing = load_nse_corporate_actions(tmp_path, ["BAD", "OBJ"])
    assert missing == ["BAD", "OBJ"]


def test_findings_are_frozen_values() -> None:
    [action] = _found("Demerger")
    assert isinstance(action, HeldThroughAction)
    assert hash(action) == hash(HeldThroughAction(*_fields(action)))


def _fields(action: HeldThroughAction) -> tuple:
    return (
        action.symbol,
        action.opened_on,
        action.ex_date,
        action.subject,
        action.sized,
        action.unsized,
    )


# --------------------------------------------------------------------------------------------
# Wired into the flagship runner: the session refuses before anything trades.
# --------------------------------------------------------------------------------------------


def _runner() -> Any:
    spec = importlib.util.spec_from_file_location(
        "_rps_corporate_actions",
        Path(__file__).resolve().parent.parent / "scripts/run_paper_pilot_session.py",
    )
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    # The runner loads `.env` into `os.environ` at import time; keep that out of the rest of the
    # suite, exactly as `test_paper_pilot_carried_session.py` does.
    with mock.patch.dict(os.environ, os.environ.copy(), clear=True):
        spec.loader.exec_module(module)
    return module


def test_a_session_refuses_to_trade_a_book_carried_across_a_demerger(tmp_path, monkeypatch) -> None:
    """The flagship had no check at all; a demerged holding would have been marked at the fall."""
    runner = _runner()
    runs_dir = tmp_path / "paper_runs"
    runs_dir.mkdir()
    state_path = runs_dir / "portfolio_state.json"
    monkeypatch.setattr(runner, "PORTFOLIO_STATE_PATH", state_path)
    records = tmp_path / "corporate-actions"
    records.mkdir()
    (records / "nse-corporate-actions-HEG.json").write_text(
        json.dumps([{"exDate": "07-Sep-2026", "subject": "Demerger"}]), encoding="utf-8"
    )
    monkeypatch.setattr(runner, "_CORPORATE_ACTIONS_DIR", records)
    book = runner.PaperPortfolioState(
        cash=Decimal("990575.00"),
        holdings={
            "HEG": PortfolioHolding(
                "HEG", 13, Decimal("725.00"), date(2026, 9, 2), Decimal("10.00")
            )
        },
        sessions_completed=5,
        sessions_held=5,
    )
    runner.save_portfolio(state_path, book)
    before = state_path.read_bytes()
    monkeypatch.setattr(runner, "assert_upstox_usable", lambda token: None)
    monkeypatch.setattr(
        runner,
        "fetch_quotes_with_retry",
        lambda universe, access_token=None: {"HEG": {"price": Decimal("250.00")}},
    )
    # Claimed through monkeypatch so the token the runner exports does not outlive the test; see
    # `test_paper_pilot_carried_session.py` for the failure that caused.
    monkeypatch.setenv("UPSTOX_ACCESS_TOKEN", "test-only-not-a-real-token")

    with pytest.raises(SystemExit) as refused:
        runner.run_paper_session(
            session_date=date(2026, 9, 21),
            output_dir=runs_dir,
            universe=["HEG"],
            upstox_token="valid_token",
        )

    assert refused.value.code == 11
    assert state_path.read_bytes() == before
