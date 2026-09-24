"""Reviewing a corporate action clears it once, correctly, in the book it belongs to.

Both paper books stop at a holding carried across a split, bonus, consolidation, demerger or rights
issue that no one has reviewed. `scripts/apply_paper_corporate_action.py` is how a person clears one
after reading the company's filing. These tests pin what it will and will not record: nothing
without `--apply`, a ratio checked against what NSE published, each action once, and every copy of
the flagship's state kept in step so a restore cannot undo a review.
"""

from __future__ import annotations

import importlib.util
import json
import os
from dataclasses import replace
from datetime import date
from decimal import Decimal
from pathlib import Path
from typing import Any
from unittest import mock

import pytest

from quant_system.execution.paper_portfolio import (
    PaperPortfolioState,
    PortfolioHolding,
    load_portfolio,
    save_portfolio,
)
from quant_system.research_xs_monthly.paper import FROZEN_RULE, unreviewed_corporate_actions

ROOT = Path(__file__).resolve().parent.parent
EX = date(2026, 10, 12)
OPENED = date(2026, 10, 5)
RECORDS = {
    "INFY": [
        {"exDate": "12-Oct-2026", "subject": "Bonus 1:1"},
        {"exDate": "20-Oct-2026", "subject": "Dividend - Rs 5 Per Share"},
    ],
    "TCS": [{"exDate": "12-Oct-2026", "subject": "Rights 3:25 @ Premium Rs 1799/-"}],
    "ABC": [{"exDate": "12-Oct-2026", "subject": "Bonus"}],
}


def _load(name: str, path: Path) -> Any:
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    # The runner loads `.env` into `os.environ` at import time; keep that out of the rest of the
    # suite, exactly as `test_paper_pilot_carried_session.py` does.
    with mock.patch.dict(os.environ, os.environ.copy(), clear=True):
        spec.loader.exec_module(module)
    return module


TOOL = _load("_apply_ca_tool", ROOT / "scripts/apply_paper_corporate_action.py")


@pytest.fixture
def books(tmp_path: Path) -> dict[str, Path]:
    records = tmp_path / "corporate-actions"
    records.mkdir()
    for symbol, entries in RECORDS.items():
        (records / f"nse-corporate-actions-{symbol}.json").write_text(
            json.dumps(entries), encoding="utf-8"
        )
    flagship = tmp_path / "paper_runs" / "portfolio_state.json"
    save_portfolio(
        flagship,
        PaperPortfolioState(
            cash=Decimal("100000.00"),
            holdings={
                "INFY": PortfolioHolding("INFY", 98, Decimal("1542.59"), OPENED, Decimal("10.00")),
                "TCS": PortfolioHolding("TCS", 41, Decimal("3553.98"), OPENED, Decimal("10.00")),
                "ABC": PortfolioHolding("ABC", 10, Decimal("100.00"), OPENED, Decimal("1.00")),
            },
            sessions_completed=3,
            sessions_held=3,
        ),
    )
    xs = tmp_path / "xs" / "state.json"
    xs.parent.mkdir()
    xs.write_text(
        json.dumps(
            {
                "rule": FROZEN_RULE,
                "open": [
                    {
                        "symbol": "INFY",
                        "entry_date": OPENED.isoformat(),
                        "entry_open": "1500",
                        "shares": 6,
                        "entry_value": "9000",
                    }
                ],
                "closed": [],
                "unresolved": [],
                "runs": [],
                "capital": "1000000",
                "cash": "991000",
            }
        ),
        encoding="utf-8",
    )
    return {
        "records": records,
        "flagship": flagship,
        "copy": tmp_path / "evidence" / "portfolio_state.json",
        "xs": xs,
    }


def _run(books: dict[str, Path], *args: str, book: str = "flagship") -> int:
    code: int = TOOL.main(
        [
            "--book",
            book,
            *args,
            "--state",
            str(books["xs" if book == "xs" else "flagship"]),
            "--evidence-copy",
            str(books["copy"]),
            "--corporate-actions-dir",
            str(books["records"]),
            "--reviewed-at",
            "2026-10-13T04:00:00Z",
        ]
    )
    return code


INFY_BONUS = ("--symbol", "INFY", "--ex-date", "2026-10-12", "--bonus", "1:1")


def test_a_dry_run_shows_the_adjustment_and_writes_nothing(books, capsys) -> None:
    before = books["flagship"].read_bytes()

    assert _run(books, *INFY_BONUS) == 0

    output = capsys.readouterr().out
    assert "shares 98 -> 196" in output
    assert "ratio matches the NSE record" in output
    assert "DRY RUN" in output
    assert books["flagship"].read_bytes() == before
    assert not books["copy"].exists()


def test_apply_adjusts_the_holding_in_every_copy(books) -> None:
    assert _run(books, *INFY_BONUS, "--apply") == 0

    for path in (
        books["flagship"],
        books["flagship"].with_suffix(".backup.json"),
        books["copy"],
    ):
        state = load_portfolio(path)
        assert state is not None, path
        assert state.holdings["INFY"].quantity == 196, path
        assert state.holdings["INFY"].average_cost == Decimal("771.295000"), path
        assert ("INFY", EX) in state.reviewed, path


def test_a_ratio_that_contradicts_nse_is_refused(books, capsys) -> None:
    before = books["flagship"].read_bytes()

    code = _run(books, "--symbol", "INFY", "--ex-date", "2026-10-12", "--bonus", "2:1", "--apply")

    assert code == 2
    assert "contradicts the NSE record" in capsys.readouterr().out
    assert books["flagship"].read_bytes() == before


def test_a_second_review_is_refused_so_a_split_is_never_applied_twice(books, capsys) -> None:
    assert _run(books, *INFY_BONUS, "--apply") == 0
    capsys.readouterr()

    assert _run(books, *INFY_BONUS, "--apply") == 2
    assert "already been reviewed" in capsys.readouterr().out
    state = load_portfolio(books["flagship"])
    assert state is not None
    assert state.holdings["INFY"].quantity == 196


def test_an_action_nse_does_not_record_is_refused(books, capsys) -> None:
    code = _run(books, "--symbol", "INFY", "--ex-date", "2026-10-13", "--bonus", "1:1", "--apply")
    assert code == 2
    assert "NSE records no split" in capsys.readouterr().out


def test_a_ratio_nse_did_not_state_is_taken_from_the_filing(books, capsys) -> None:
    code = _run(books, "--symbol", "ABC", "--ex-date", "2026-10-12", "--bonus", "1:4", "--apply")

    assert code == 0
    assert "ratio taken from the filing" in capsys.readouterr().out
    state = load_portfolio(books["flagship"])
    assert state is not None
    assert state.holdings["ABC"].quantity == 12  # 10 * 5/4 = 12.5, whole shares credited


def test_a_rights_issue_is_acknowledged_with_its_reason(books) -> None:
    code = _run(
        books,
        "--symbol",
        "TCS",
        "--ex-date",
        "2026-10-12",
        "--acknowledge",
        "rights not taken up; the entitlement lapsed",
        "--apply",
    )

    assert code == 0
    state = load_portfolio(books["flagship"])
    assert state is not None
    assert state.holdings["TCS"].quantity == 41
    [review] = [r for r in state.reviewed_actions if r.symbol == "TCS"]
    assert review.resolution == "acknowledged: rights not taken up; the entitlement lapsed"


def test_a_ratio_with_an_acknowledgement_or_neither_is_refused(books, capsys) -> None:
    both = _run(books, *INFY_BONUS, "--acknowledge", "x")
    neither = _run(books, "--symbol", "INFY", "--ex-date", "2026-10-12")
    output = capsys.readouterr().out
    assert both == neither == 2
    assert "not both" in output
    assert "give the ratio from the filing" in output


def test_the_xs_leg_is_adjusted_and_no_longer_flagged(books) -> None:
    asof = date(2026, 10, 14)
    before = json.loads(books["xs"].read_text(encoding="utf-8"))
    assert set(unreviewed_corporate_actions(before["open"], RECORDS, asof)) == {"INFY"}

    assert _run(books, *INFY_BONUS, "--apply", book="xs") == 0

    after = json.loads(books["xs"].read_text(encoding="utf-8"))
    [leg] = after["open"]
    assert leg["shares"] == 12
    assert leg["entry_open"] == "750.000000"
    assert leg["entry_value"] == "9000"
    assert leg["corporate_actions"][0]["resolution"] == "adjusted: bonus 1:1"
    assert unreviewed_corporate_actions(after["open"], RECORDS, asof) == {}


def test_a_second_xs_review_is_refused(books, capsys) -> None:
    assert _run(books, *INFY_BONUS, "--apply", book="xs") == 0
    capsys.readouterr()
    assert _run(books, *INFY_BONUS, "--apply", book="xs") == 2
    assert "already been reviewed" in capsys.readouterr().out


class _PastTheGuard(Exception):
    """Raised by the step after the corporate-action check, to prove the session reached it."""


def _session(runner: Any, monkeypatch, books: dict[str, Path]) -> None:
    monkeypatch.setattr(runner, "PORTFOLIO_STATE_PATH", books["flagship"])
    monkeypatch.setattr(runner, "_CORPORATE_ACTIONS_DIR", books["records"])
    monkeypatch.setattr(runner, "assert_upstox_usable", lambda token: None)
    monkeypatch.setattr(
        runner,
        "fetch_quotes_with_retry",
        lambda universe, access_token=None: {"INFY": {"price": Decimal("771.00")}},
    )
    # Claimed through monkeypatch so the token the runner exports does not outlive the test.
    monkeypatch.setenv("UPSTOX_ACCESS_TOKEN", "test-only-not-a-real-token")
    runner.run_paper_session(
        session_date=date(2026, 10, 14),
        output_dir=books["flagship"].parent,
        universe=["INFY", "TCS"],
        upstox_token="valid_token",
    )


def test_after_its_reviews_the_flagship_session_gets_past_the_check(books, monkeypatch) -> None:
    runner = _load("_rps_ca_review", ROOT / "scripts/run_paper_pilot_session.py")
    state = load_portfolio(books["flagship"])
    assert state is not None
    holdings = {s: h for s, h in state.holdings.items() if s != "ABC"}
    save_portfolio(books["flagship"], replace(state, holdings=holdings))

    with pytest.raises(SystemExit) as refused:
        _session(runner, monkeypatch, books)
    assert refused.value.code == 11

    assert _run(books, *INFY_BONUS, "--apply") == 0
    rights = ("--symbol", "TCS", "--ex-date", "2026-10-12", "--acknowledge", "not taken up")
    assert _run(books, *rights, "--apply") == 0

    def past_the_guard(self: Any, horizon: int) -> bool:
        raise _PastTheGuard

    monkeypatch.setattr(PaperPortfolioState, "rebalance_due", past_the_guard)
    with pytest.raises(_PastTheGuard):
        _session(runner, monkeypatch, books)
