"""The XS paper watch declines to value a leg held across an unreviewed structural action.

Until 2026-09-24 the XS book knew only the demergers someone typed into a one-entry authority. It now
reads every split, bonus, consolidation, demerger and rights issue NSE published for its names, and a
leg carried across one is left unvalued -- as HEG was -- until a person reviews it with
`scripts/apply_paper_corporate_action.py --book xs`. The review is stored on the leg, so it must
survive every settle; a leg that lost it would be flagged again, and a second review of a split
would apply it twice.
"""

from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

from quant_system.research_xs_monthly.bars import Bar
from quant_system.research_xs_monthly.paper import settle_positions, unreviewed_corporate_actions

START = date(2026, 8, 3)
SESSIONS = 70
#: Late enough that a 21-session hold has not matured, so the leg stays open and is marked.
ENTRY = START + timedelta(days=55)
EX_DATE = START + timedelta(days=60)
ASOF = START + timedelta(days=SESSIONS - 1)


def _nse(day: date) -> str:
    return day.strftime("%d-%b-%Y")


def _bars(symbol: str, price: float = 100.0) -> list[Bar]:
    value = Decimal(str(price))
    return [
        Bar(
            symbol=symbol,
            exchange_date=START + timedelta(days=offset),
            open=value,
            # A bar with no range reads as circuit-locked, and the rule never forces an exit on one.
            high=value + 1,
            low=value - 1,
            close=value,
            volume=1000,
        )
        for offset in range(SESSIONS)
    ]


def _universe() -> dict[str, list[Bar]]:
    """Two names: the calendar needs at least two to count a session."""
    return {"SPLITCO": _bars("SPLITCO"), "QUIET": _bars("QUIET")}


def _leg(symbol: str, entry: date = ENTRY, **extra: object) -> dict[str, object]:
    return {
        "symbol": symbol,
        "entry_date": entry.isoformat(),
        "entry_open": "100",
        "shares": 90,
        "entry_value": "9000",
        **extra,
    }


RECORDS = {"SPLITCO": [{"exDate": _nse(EX_DATE), "subject": "Bonus 1:1"}]}


def test_a_leg_held_across_a_published_bonus_is_flagged() -> None:
    flags = unreviewed_corporate_actions([_leg("SPLITCO"), _leg("QUIET")], RECORDS, ASOF)

    assert set(flags) == {"SPLITCO"}
    assert flags["SPLITCO"].startswith("CORPORATE_ACTION_NOT_REVIEWED")
    assert "--book xs" in flags["SPLITCO"]


def test_a_leg_entered_after_the_action_is_priced_normally() -> None:
    assert unreviewed_corporate_actions([_leg("SPLITCO", entry=EX_DATE)], RECORDS, ASOF) == {}


def test_a_reviewed_leg_is_not_flagged_again() -> None:
    reviewed = _leg("SPLITCO", corporate_actions=[{"ex_date": EX_DATE.isoformat()}])
    assert unreviewed_corporate_actions([reviewed], RECORDS, ASOF) == {}


def test_a_flagged_leg_is_left_unvalued_rather_than_marked_at_the_halved_price() -> None:
    positions = [_leg("SPLITCO"), _leg("QUIET")]
    bars = {"SPLITCO": _bars("SPLITCO"), "QUIET": _bars("QUIET")}
    flags = unreviewed_corporate_actions(positions, RECORDS, ASOF)

    settled = settle_positions(positions, bars, unpriced_entitlements=flags)

    by_symbol = {leg["symbol"]: leg for leg in settled["open"]}
    assert by_symbol["SPLITCO"]["unpriced"] is True
    assert "market_value" not in by_symbol["SPLITCO"]
    assert "market_value" in by_symbol["QUIET"]


def test_a_review_survives_an_open_settle() -> None:
    review = {"ex_date": EX_DATE.isoformat(), "resolution": "adjusted: bonus 1:1"}
    positions = [_leg("SPLITCO", corporate_actions=[review])]

    settled = settle_positions(positions, _universe())

    assert settled["open"][0]["corporate_actions"] == [review]


def test_a_review_survives_the_close() -> None:
    review = {"ex_date": EX_DATE.isoformat(), "resolution": "adjusted: bonus 1:1"}
    early = START + timedelta(days=10)
    positions = [_leg("SPLITCO", entry=early, corporate_actions=[review])]

    settled = settle_positions(positions, _universe())

    assert settled["closed"][0]["corporate_actions"] == [review]


def test_a_review_survives_an_unresolved_maturity() -> None:
    review = {"ex_date": EX_DATE.isoformat(), "resolution": "acknowledged: x"}
    early = START + timedelta(days=10)
    positions = [_leg("SPLITCO", entry=early, corporate_actions=[review])]

    settled = settle_positions(positions, _universe(), unpriced_entitlements={"SPLITCO": "held"})

    assert settled["unresolved"][0]["corporate_actions"] == [review]


def test_a_leg_with_no_review_gains_no_empty_record() -> None:
    settled = settle_positions([_leg("QUIET")], _universe())
    assert "corporate_actions" not in settled["open"][0]
