"""The entitlement must survive the whole journey, not just the marking function.

The capability to decline to value a leg already existed -- ``settle_positions`` accepted an
``unpriced_entitlements`` map and ``tests/test_xs_monthly_unpriced_entitlement.py`` pinned its
behaviour. Nothing called it. The scheduled runner passed no map, summed ``market_value`` with a
``"0"`` default, and would have run the leg through the closing path at maturity, turning an
unevidenced mark into realized cash.

These tests cover the four places the value could still be lost: building the map from the issuer
authority, excluding rather than zeroing it in equity, refusing to close it at maturity, and letting
the book keep rebalancing anyway.
"""

from __future__ import annotations

import json
from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path
from typing import Any

import pytest

from quant_system.research_xs_monthly.bars import Bar
from quant_system.research_xs_monthly.paper import (
    book_value,
    load_unpriced_entitlements,
    settle_positions,
)
from quant_system.research_xs_monthly.screen import ScreenError

SESSIONS = 70
ENTRY_INDEX = 55
GAP_INDEX = 60
START = date(2026, 8, 3)


def _bars(symbol: str, prices: list[float], start: date = START) -> list[Bar]:
    """One bar per consecutive day at the given opens, with a real high/low spread.

    The spread is load-bearing. ``screen._is_locked`` treats ``high == low`` as a circuit lock and
    ``forward_net`` then refuses to close the leg, so a flat-bar fixture can only ever exercise the
    open-mark path -- which is why the maturity defect survived the existing tests.
    """
    out: list[Bar] = []
    for offset, price in enumerate(prices):
        value = Decimal(str(price))
        out.append(
            Bar(
                symbol=symbol,
                exchange_date=start + timedelta(days=offset),
                open=value,
                high=value * Decimal("1.01"),
                low=value * Decimal("0.99"),
                close=value,
                volume=1000,
            )
        )
    return out


def _authority(
    tmp_path: Path, *, ex_offset: int = GAP_INDEX, resulting: str = "HEGGRAPHITE"
) -> Path:
    path = tmp_path / "entitlements.json"
    path.write_text(
        json.dumps(
            {
                "schema_id": "quantos.demerger_entitlements",
                "schema_version": 1,
                "entitlements": [
                    {
                        "symbol": "HEG",
                        "ex_date": (START + timedelta(days=ex_offset)).isoformat(),
                        "resulting_symbol": resulting,
                        "ratio": "1",
                        "filing_url": "https://example.invalid/filing",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    return path


def _book(entry_index: int = ENTRY_INDEX) -> tuple[list[dict[str, Any]], dict[str, list[Bar]]]:
    heg = _bars("HEG", [725.0] * GAP_INDEX + [257.0] * (SESSIONS - GAP_INDEX))
    stable = _bars("STABLE", [100.0] * SESSIONS)
    entry_on = heg[entry_index].exchange_date.isoformat()
    positions: list[dict[str, Any]] = [
        {
            "symbol": "HEG",
            "entry_date": entry_on,
            "entry_open": "725",
            "shares": 13,
            "entry_value": "9425",
        },
        {
            "symbol": "STABLE",
            "entry_date": entry_on,
            "entry_open": "100",
            "shares": 90,
            "entry_value": "9000",
        },
    ]
    return positions, {"HEG": heg, "STABLE": stable}


# --- building the map from the issuer authority ------------------------------------------------


def test_a_leg_held_across_the_ex_date_is_flagged(tmp_path: Path) -> None:
    positions, bars = _book()
    flagged = load_unpriced_entitlements(positions, bars, _authority(tmp_path))
    assert set(flagged) == {"HEG"}
    assert "ENTITLEMENT_UNPRICED" in flagged["HEG"]
    assert "HEGGRAPHITE" in flagged["HEG"], "the reason must name what the holder actually received"


def test_an_event_that_predates_entry_is_not_flagged(tmp_path: Path) -> None:
    """The entry price already reflects an action that happened before the book bought in."""
    positions, bars = _book()
    authority = _authority(tmp_path, ex_offset=ENTRY_INDEX - 5)
    assert load_unpriced_entitlements(positions, bars, authority) == {}


def test_a_priced_resulting_company_is_still_refused_but_says_why(tmp_path: Path) -> None:
    """A different limitation, reported differently: the data exists, this book's shape does not."""
    positions, bars = _book()
    bars["HEGGRAPHITE"] = _bars("HEGGRAPHITE", [400.0] * SESSIONS)
    flagged = load_unpriced_entitlements(positions, bars, _authority(tmp_path))
    assert "ENTITLEMENT_NOT_REPRESENTABLE" in flagged["HEG"]


def test_a_missing_authority_raises_rather_than_returning_an_empty_map(tmp_path: Path) -> None:
    """An empty map is indistinguishable from "no corporate actions occurred".

    Returning one silently is precisely the failure mode that froze the corporate-action authority
    for weeks: a failed fetch wrote an empty list and every later read trusted it.
    """
    positions, bars = _book()
    with pytest.raises(ScreenError, match="MISSING_AUTHORITY"):
        load_unpriced_entitlements(positions, bars, tmp_path / "absent.json")


def test_a_wrong_schema_raises(tmp_path: Path) -> None:
    positions, bars = _book()
    path = tmp_path / "bad.json"
    path.write_text(
        json.dumps({"schema_id": "something.else", "entitlements": []}), encoding="utf-8"
    )
    with pytest.raises(ScreenError, match="BAD_AUTHORITY"):
        load_unpriced_entitlements(positions, bars, path)


# --- equity must exclude, never zero -------------------------------------------------------------


def test_equity_excludes_the_unpriced_leg_instead_of_adding_zero() -> None:
    positions, bars = _book()
    settled = settle_positions(positions, bars, unpriced_entitlements={"HEG": "unpriced"})
    valued = book_value(settled["open"], settled["unresolved"])

    assert valued["priced_market_value"] == Decimal(90) * Decimal("100"), (
        "only STABLE is valuable, and it is valued in full"
    )
    assert valued["unpriced_at_cost"] == Decimal("9425"), "the committed capital is still reported"
    assert [item["symbol"] for item in valued["unpriced"]] == ["HEG"]


def test_the_old_defaulting_sum_and_the_new_split_disagree_by_the_measured_amount() -> None:
    """Pins the size of the correction to the figure in the loss diagnosis.

    13 x 257 = 3,341 is what the defaulting sum credited the HEG leg with while calling the
    remaining 6,084 of entry cost a loss. The repair does not move that 3,341 somewhere else -- it
    declines to state any number for the leg at all.
    """
    positions, bars = _book()
    plain = settle_positions(positions, bars)
    old_style = sum(
        (Decimal(str(leg.get("market_value", "0"))) for leg in plain["open"]), Decimal(0)
    )
    flagged = settle_positions(positions, bars, unpriced_entitlements={"HEG": "unpriced"})
    new_style = book_value(flagged["open"], flagged["unresolved"])["priced_market_value"]

    assert old_style - new_style == Decimal("3341")


def test_book_value_refuses_a_leg_missing_market_value_even_without_the_flag() -> None:
    """Defence in depth: the exclusion keys off the absent value, not only off the flag."""
    valued = book_value([{"symbol": "X", "shares": 1, "entry_value": "100"}])
    assert valued["priced_market_value"] == Decimal(0)
    assert valued["unpriced_at_cost"] == Decimal("100")


# --- maturity: the leg must not close at a price it cannot be valued at --------------------------


def _matured_book() -> tuple[list[dict[str, Any]], dict[str, list[Bar]]]:
    """Entry early enough that a 21-session hold has matured inside the fixture calendar."""
    return _book(entry_index=20)


def test_a_matured_unpriced_leg_is_not_closed() -> None:
    positions, bars = _matured_book()
    settled = settle_positions(positions, bars, unpriced_entitlements={"HEG": "unpriced"})

    assert [leg["symbol"] for leg in settled["closed"]] == ["STABLE"], (
        "closing HEG would convert an unevidenced mark into realized cash, permanently"
    )
    assert [leg["symbol"] for leg in settled["unresolved"]] == ["HEG"]


def test_the_unresolved_leg_pays_no_proceeds_and_states_its_cost() -> None:
    positions, bars = _matured_book()
    settled = settle_positions(positions, bars, unpriced_entitlements={"HEG": "unpriced"})
    leg = settled["unresolved"][0]

    assert "proceeds" not in leg, "no cash was received, so none may be credited"
    assert "net" not in leg and "net_cash" not in leg
    assert "market_value" not in leg
    assert leg["entry_value"] == "9425"
    assert leg["matured_on"]
    assert leg["unpriced"] is True


def test_the_unresolved_leg_leaves_open_so_the_book_can_rebalance() -> None:
    """The runner opens new positions only when ``state["open"]`` is empty.

    A leg that stayed open forever would stop the book rebalancing, silently and indefinitely --
    a worse outcome than the mispricing, and one nothing would have reported.
    """
    positions, bars = _matured_book()
    settled = settle_positions(positions, bars, unpriced_entitlements={"HEG": "unpriced"})
    assert settled["open"] == []


def test_without_the_flag_a_matured_leg_still_closes_normally() -> None:
    positions, bars = _matured_book()
    settled = settle_positions(positions, bars)
    assert {leg["symbol"] for leg in settled["closed"]} == {"HEG", "STABLE"}
    assert settled["unresolved"] == []
