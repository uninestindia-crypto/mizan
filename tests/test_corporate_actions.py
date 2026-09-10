"""Back-adjustment must reproduce a continuous series, and must refuse to guess.

Written against the strings the NSE authority actually holds. The training corpus carries 250
structural actions inside the research universe alone, each currently read by the model as a genuine
±30-60% day, so a parser that silently misses a format is the same defect in a new place.
"""

from __future__ import annotations

import json
from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest

from quant_system.data.corporate_actions import (
    BarPoint,
    CorporateActionError,
    adjust_bars,
    build_adjustment_factors,
    parse_subject_factor,
)

REPO_ROOT = Path(__file__).resolve().parent.parent


def _bar(day: int, close: float, *, volume: int = 1000, month: int = 1) -> BarPoint:
    c = Decimal(str(close))
    return BarPoint(date(2026, month, day), c, c, c, c, volume)


# --- parsing ---------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("subject", "expected"),
    [
        ("Face Value Split (Sub-Division) - From Rs 10/- Per Share To Rs 2/- Per Share", "0.2"),
        ("Face Value Split (Sub-Division) - From Rs10/- Per Share To Re 1/- Per Share", "0.1"),
        ("Face Value Split (Sub-Division) - From Rs 10 /- Per Share To Rs 2/- Per Share", "0.2"),
        ("Face Value Split From Rs 10 To Re 1", "0.1"),
        ("Face Value Split (Sub-Division) - From Rs 5/- Per Share To Rs 2/- Per Share", "0.4"),
        # Abbreviated, and it carries none of the keywords a naive bucket filter would use --
        # it sits in the same "OTHER" pile as 5,497 Annual General Meetings.
        ("Fv Splt Frm Rs 10 To Rs 2", "0.2"),
    ],
)
def test_every_real_split_format_is_parsed(subject: str, expected: str) -> None:
    factor, kinds, needs = parse_subject_factor(subject)
    assert factor == Decimal(expected)
    assert "split" in kinds
    assert needs is False


@pytest.mark.parametrize(
    ("subject", "expected"),
    [
        ("Bonus 1:1", "0.5"),  # 1 new per 1 held -> half the price
        ("Bonus  1:4", "0.8"),  # double space, seen in the authority
        ("Bonus 1: 2", str(Decimal(2) / Decimal(3))),  # space after the colon
        ("Bonus 1:10 (Revised)", str(Decimal(10) / Decimal(11))),
    ],
)
def test_every_real_bonus_format_is_parsed(subject: str, expected: str) -> None:
    factor, kinds, _ = parse_subject_factor(subject)
    assert factor == Decimal(expected)
    assert "bonus" in kinds


def test_a_single_record_carrying_bonus_and_split_applies_both() -> None:
    """`Bonus 1:1/Face Value Split ... Rs 10 -> Rs 2` is one record and two price effects."""
    subject = (
        "Bonus 1:1/Face Value Split (Sub-Division) - From Rs 10/- Per Share To Rs 2/- Per Share"
    )
    factor, kinds, _ = parse_subject_factor(subject)
    assert set(kinds) == {"bonus", "split"}
    assert factor == Decimal("0.5") * Decimal("0.2")


def test_dividend_split_and_meeting_in_one_record_all_resolve() -> None:
    subject = (
        "Annual General Meeting/Dividend - Rs 10 Per Share/"
        "Face Value Split (Sub-Division) - From Rs 10/- Per Share To Rs 2/- Per Share"
    )
    factor, kinds, _ = parse_subject_factor(subject, cum_close=Decimal("100"))
    assert set(kinds) == {"dividend", "split"}
    # dividend 10 off a 100 close, then a 5:1 split
    assert factor == (Decimal("90") / Decimal("100")) * Decimal("0.2")


def test_total_return_removes_the_dividend_and_price_return_does_not() -> None:
    subject = "Dividend - Rs 5 Per Share"
    total, kinds, _ = parse_subject_factor(subject, cum_close=Decimal("100"), total_return=True)
    assert total == Decimal("0.95")
    assert kinds == ("dividend",)

    price_only, kinds_only, _ = parse_subject_factor(
        subject, cum_close=Decimal("100"), total_return=False
    )
    assert price_only == Decimal(1)
    assert kinds_only == ()


@pytest.mark.parametrize(
    "subject",
    ["Annual General Meeting", "Extra Ordinary General Meeting", "Interest Payment", "Rights"],
)
def test_actions_with_no_price_effect_produce_no_factor(subject: str) -> None:
    factor, kinds, needs = parse_subject_factor(subject)
    assert factor == Decimal(1)
    assert kinds == ()
    assert needs is False


@pytest.mark.parametrize(
    "subject", ["Demerger", "Scheme Of Demerger", "Scheme Of Arrangement Of Demerger"]
)
def test_a_ratioless_demerger_is_flagged_for_inference_not_parsed(subject: str) -> None:
    """NSE publishes no ratio for these. No arithmetic recovers it from the text."""
    factor, kinds, needs = parse_subject_factor(subject)
    assert factor == Decimal(1)
    assert kinds == ()
    assert needs is True


# --- factor construction ---------------------------------------------------------------------


def test_a_demerger_is_sized_from_the_ex_date_gap() -> None:
    bars = [_bar(1, 100.0), _bar(2, 100.0), _bar(3, 35.0), _bar(4, 34.0)]
    factors, skipped = build_adjustment_factors([(date(2026, 1, 3), "Demerger")], bars)
    assert skipped == []
    assert len(factors) == 1
    assert factors[0].source == "INFERRED"
    assert factors[0].factor == Decimal("0.35")


def test_a_small_gap_is_reported_rather_than_absorbed_into_a_fake_action() -> None:
    """Inferring from a 3% gap would fabricate a correction nothing asked for."""
    bars = [_bar(1, 100.0), _bar(2, 100.0), _bar(3, 97.0), _bar(4, 96.0)]
    factors, skipped = build_adjustment_factors([(date(2026, 1, 3), "Demerger")], bars)
    assert factors == []
    assert len(skipped) == 1
    assert "too small to size safely" in skipped[0]


def test_bars_out_of_order_are_refused() -> None:
    bars = [_bar(3, 100.0), _bar(1, 100.0)]
    with pytest.raises(CorporateActionError, match="ascending date order"):
        build_adjustment_factors([], bars)


# --- application -----------------------------------------------------------------------------


def test_back_adjustment_removes_the_discontinuity_and_leaves_real_returns_intact() -> None:
    """The whole point: a 5:1 split must stop looking like an -80% day."""
    bars = [_bar(1, 500.0), _bar(2, 505.0), _bar(3, 101.0), _bar(4, 102.0)]
    factors, _ = build_adjustment_factors(
        [(date(2026, 1, 3), "Face Value Split From Rs 10 To Rs 2")], bars
    )
    adjusted = adjust_bars(bars, factors)

    raw_gap = float(bars[2].close / bars[1].close - 1)
    adj_gap = float(adjusted[2].close / adjusted[1].close - 1)
    assert raw_gap < -0.79, "raw series really does show the artifact"
    assert abs(adj_gap) < 0.01, "adjusted series shows an ordinary day"

    # Real returns are untouched.
    assert adjusted[1].close / adjusted[0].close == bars[1].close / bars[0].close
    assert adjusted[3].close == bars[3].close, "the newest bars are never adjusted"


def test_volume_is_rescaled_inversely_to_price() -> None:
    bars = [_bar(1, 500.0, volume=1000), _bar(2, 100.0, volume=5000)]
    factors, _ = build_adjustment_factors(
        [(date(2026, 1, 2), "Face Value Split From Rs 10 To Rs 2")], bars
    )
    adjusted = adjust_bars(bars, factors)
    assert adjusted[0].close == Decimal("100")
    assert adjusted[0].volume == 5000, "a 5:1 split multiplies the historical share count by 5"
    assert adjusted[1].volume == 5000, "the newest bar is untouched"


def test_multiple_actions_compound_backwards() -> None:
    """Two splits: bars before both carry the product, bars between carry only the later one."""
    bars = [_bar(1, 400.0), _bar(2, 200.0), _bar(3, 100.0)]
    factors, _ = build_adjustment_factors(
        [
            (date(2026, 1, 2), "Face Value Split From Rs 10 To Rs 5"),
            (date(2026, 1, 3), "Face Value Split From Rs 10 To Rs 5"),
        ],
        bars,
    )
    adjusted = adjust_bars(bars, factors)
    assert adjusted[0].close == Decimal("100")  # 400 * 0.5 * 0.5
    assert adjusted[1].close == Decimal("100")  # 200 * 0.5
    assert adjusted[2].close == Decimal("100")  # untouched


def test_inferred_factors_can_be_refused() -> None:
    bars = [_bar(1, 100.0), _bar(2, 100.0), _bar(3, 35.0)]
    factors, _ = build_adjustment_factors([(date(2026, 1, 3), "Demerger")], bars)
    assert adjust_bars(bars, factors, allow_inferred=True)[0].close == Decimal("35.00")
    assert adjust_bars(bars, factors, allow_inferred=False)[0].close == Decimal("100")


# --- against the real authority ----------------------------------------------------------------


def test_the_real_heg_demerger_is_sized_and_removes_the_real_gap() -> None:
    """End to end on the event that started this: HEG, 2026-09-07, -64.3% on 3.6M shares."""
    ca = (
        REPO_ROOT
        / "data/evidence/market-cache/nifty500-refresh-20230828-20260827"
        / "corporate-actions/nse-corporate-actions-HEG.json"
    )
    records = json.loads(ca.read_text(encoding="utf-8"))
    assert any("Demerger" in str(r.get("subject", "")) for r in records), (
        "the refreshed authority must contain the demerger this test exists for"
    )

    # The real quoted closes either side of the ex-date.
    bars = [
        BarPoint(date(2026, 9, 3), *[Decimal("707.45")] * 4, 1656554),
        BarPoint(date(2026, 9, 4), *[Decimal("728.25")] * 4, 2565950),
        BarPoint(date(2026, 9, 7), Decimal("260.00"), *[Decimal("272.20")] * 3, 3615221),
        BarPoint(date(2026, 9, 8), *[Decimal("258.60")] * 4, 1334287),
    ]
    factors, skipped = build_adjustment_factors([(date(2026, 9, 7), "Demerger")], bars)
    assert skipped == []
    assert factors[0].source == "INFERRED"

    adjusted = adjust_bars(bars, factors)
    raw_gap = float(bars[2].close / bars[1].close - 1)
    adj_gap = float(adjusted[2].close / adjusted[1].close - 1)
    assert raw_gap < -0.62, f"raw gap should be the real artifact, got {raw_gap:.4f}"
    assert abs(adj_gap) < 0.06, f"adjusted gap should be an ordinary day, got {adj_gap:.4f}"
