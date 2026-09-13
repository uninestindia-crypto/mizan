"""An open leg whose corporate action nobody sized must not be marked as if it were worthless.

The defect
----------
``settle_positions`` marked every open leg as ``shares * latest_open``. When a corporate action falls
inside the holding window that arithmetic multiplies the **pre-event** share count by the
**post-event** quote, which silently asserts that whatever the holder received in exchange -- shares
in a demerged entity, say -- is worth nothing.

HEG is the real case. Its 2026-09-07 demerger entitled one resulting-company share per HEG share. The
resulting company has no price anywhere in this repository: it listed after the market cache's window
closed. Marking 13 shares at the post-demerger quote booked about INR 6,084 of "loss" that no evidence
supports, and that single position was larger than the book's entire displayed result.

Three treatments are all wrong, and the tests below pin the fourth:

- mark at the post-event quote on unchanged shares -> asserts the entitlement is worthless
- reverse the loss                                 -> asserts it is worth exactly the quote drop
- invent a price                                   -> fabricates evidence

The only defensible treatment is to carry it as an **unpriced asset**: say the position exists, say
its entry cost, and say plainly that it cannot be valued from available data.
"""

from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

from quant_system.research_xs_monthly.bars import Bar
from quant_system.research_xs_monthly.paper import settle_positions

REASON = "DEMERGER_ENTITLEMENT_UNPRICED: resulting company has no price in this repository"


def _bars(symbol: str, prices: list[float], start: date = date(2026, 8, 3)) -> list[Bar]:
    """One bar per consecutive day at the given opens."""
    out: list[Bar] = []
    for offset, price in enumerate(prices):
        value = Decimal(str(price))
        out.append(
            Bar(
                symbol=symbol,
                exchange_date=start + timedelta(days=offset),
                open=value,
                high=value,
                low=value,
                close=value,
                volume=1000,
            )
        )
    return out


SESSIONS = 70
"""The screen refuses a calendar shorter than 64 sessions, so the fixture must clear that."""

ENTRY_INDEX = 55
"""Entry late enough that a 21-session hold has not matured, so the legs stay *open* and get marked.

The whole defect lives in the open-leg marking path; a matured leg exits at a real price and never
reaches it.
"""

GAP_INDEX = 60
"""Where HEG's demerger gap falls -- after entry, before the latest bar, i.e. inside the window."""


def _book(hold: int = 21):
    """A two-name book: HEG gaps like the real demerger, STABLE does not."""
    heg = _bars("HEG", [725.0] * GAP_INDEX + [257.0] * (SESSIONS - GAP_INDEX))
    stable = _bars("STABLE", [100.0] * SESSIONS)
    bars = {"HEG": heg, "STABLE": stable}
    entry_on = heg[ENTRY_INDEX].exchange_date.isoformat()
    positions = [
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
    return positions, bars, hold


def test_without_the_flag_the_old_behaviour_is_unchanged() -> None:
    """Existing callers pass nothing and must see exactly what they saw before."""
    positions, bars, hold = _book()
    result = settle_positions(positions, bars, hold=hold)
    legs = {leg["symbol"]: leg for leg in result["open"]}

    # Compared as Decimal, not as text: the book stores whatever `str(Decimal)` produced, so
    # "3341.0" and "3341" are the same number written two ways and only one of them is the value
    # under test.
    assert Decimal(legs["HEG"]["market_value"]) == Decimal(13) * Decimal("257")
    assert "unpriced" not in legs["HEG"]
    assert Decimal(legs["STABLE"]["market_value"]) == Decimal(90) * Decimal("100")


def test_a_flagged_leg_is_not_valued_at_all() -> None:
    """The correction: no market_value, no unrealized, and the reason stated."""
    positions, bars, hold = _book()
    result = settle_positions(positions, bars, hold=hold, unpriced_entitlements={"HEG": REASON})
    legs = {leg["symbol"]: leg for leg in result["open"]}

    assert legs["HEG"]["unpriced"] is True
    assert legs["HEG"]["unpriced_reason"] == REASON
    assert "market_value" not in legs["HEG"], (
        "a value must be absent, not zero -- a consumer summing market_value must skip it, "
        "not silently add nothing"
    )
    assert "unrealized" not in legs["HEG"]
    assert legs["HEG"]["entry_value"] == "9425", "the capital committed is still reported"
    assert legs["HEG"]["shares"] == 13


def test_the_gross_mark_is_removed_too() -> None:
    """``gross_mark`` is a price ratio and carries the same false claim as ``market_value``.

    Leaving it would let a reader recover the -64.6% "return" the exclusion exists to refuse.
    """
    positions, bars, hold = _book()
    plain = settle_positions(positions, bars, hold=hold)
    flagged = settle_positions(positions, bars, hold=hold, unpriced_entitlements={"HEG": REASON})
    plain_heg = next(leg for leg in plain["open"] if leg["symbol"] == "HEG")
    flagged_heg = next(leg for leg in flagged["open"] if leg["symbol"] == "HEG")

    assert float(plain_heg["gross_mark"]) < -0.6, "the fixture must reproduce the real gap"
    assert "gross_mark" not in flagged_heg


def test_other_legs_are_untouched() -> None:
    """The refusal must be surgical. One unpriceable name cannot blank the rest of the book."""
    positions, bars, hold = _book()
    plain = settle_positions(positions, bars, hold=hold)
    flagged = settle_positions(positions, bars, hold=hold, unpriced_entitlements={"HEG": REASON})
    plain_stable = next(leg for leg in plain["open"] if leg["symbol"] == "STABLE")
    flagged_stable = next(leg for leg in flagged["open"] if leg["symbol"] == "STABLE")

    assert plain_stable == flagged_stable


def test_the_excluded_loss_is_the_one_the_diagnosis_measured() -> None:
    """Ties the fixture to the real finding rather than to an invented number.

    13 shares x 725 entry = 9,425; 13 x 257 = 3,341; the difference is 6,084 -- the figure the loss
    diagnosis attributed to HEG. That is the amount this change stops the book from asserting.
    """
    positions, bars, hold = _book()
    plain = settle_positions(positions, bars, hold=hold)
    heg = next(leg for leg in plain["open"] if leg["symbol"] == "HEG")

    assert Decimal(heg["entry_value"]) == Decimal("9425")
    assert Decimal(heg["market_value"]) == Decimal("3341")
    assert Decimal(heg["unrealized"]) == Decimal("-6084")


def test_a_flag_for_a_symbol_the_book_does_not_hold_changes_nothing() -> None:
    positions, bars, hold = _book()
    baseline = settle_positions(positions, bars, hold=hold)
    with_noise = settle_positions(
        positions, bars, hold=hold, unpriced_entitlements={"NOTHELD": REASON}
    )
    assert baseline == with_noise
