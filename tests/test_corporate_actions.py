"""Back-adjustment must correct only what the provider left uncorrected.

Two wrong premises have been held here in turn, and most of these tests exist to keep either from
coming back.

**Wrong premise 1: "the manifest says RAW, so every published action needs applying."** False for
this provider. Measured across the 423-name research universe, 212 of 212 published-ratio structural
actions already show an ex-date gap of ~1.0. Applying the ratio on top is not a no-op, it is
destructive -- TATASTEEL's 10:1 split became a **+945%** day.

**Wrong premise 2: "a ratio-less action can be sized from its ex-date gap when the gap is big."**
Also false. A gap is the corporate action *plus* whatever the market did that day, and the two
cannot be separated. On the real corpus that rule would have inferred an **upward** correction for
NMDC (+71.0%), BAJAJELEC (+32.2%) and SCI (+30.0%) -- erasing genuine moves and inventing fake ones.

The contract is therefore: score the ex-date gap against *both* provider hypotheses in log-return
space and apply a published ratio only when the data says it is missing; never size a ratio-less
action from price, but accept one a caller validated against independent evidence; and treat
dividends as a return-definition choice rather than a repair. Anything unsized is reported as
unresolved so consumers refuse the window instead of publishing a fabricated return.
"""

from __future__ import annotations

import json
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path

import pytest

from quant_system.data.adjustment_provenance import (
    ADJUSTMENT_METHOD_V1,
    ADJUSTMENT_METHOD_VERSION_V1,
    AdjustmentBasis,
    AdjustmentReference,
    AdjustmentStatus,
    UnresolvedAction,
    spans_unresolved,
)
from quant_system.data.corporate_actions import (
    AdjustmentPlan,
    BarPoint,
    CorporateActionError,
    ValidatedFactor,
    adjust_bars,
    build_adjustment_factors,
    parse_subject_factor,
)

REPO_ROOT = Path(__file__).resolve().parent.parent
SPLIT_10_TO_1 = "Face Value Split (Sub-Division) - From Rs 10/- Per Share To Re 1/- Per Share"


def _bar(day: int, close: float, *, volume: int = 1000, open_: float | None = None) -> BarPoint:
    c = Decimal(str(close))
    o = Decimal(str(open_)) if open_ is not None else c
    return BarPoint(date(2026, 1, day), o, c, c, c, volume)


# --- parsing: the text layer, unchanged ----------------------------------------------------


@pytest.mark.parametrize(
    ("subject", "expected"),
    [
        ("Face Value Split (Sub-Division) - From Rs 10/- Per Share To Rs 2/- Per Share", "0.2"),
        ("Face Value Split (Sub-Division) - From Rs10/- Per Share To Re 1/- Per Share", "0.1"),
        ("Face Value Split (Sub-Division) - From Rs 10 /- Per Share To Rs 2/- Per Share", "0.2"),
        ("Face Value Split From Rs 10 To Re 1", "0.1"),
        # Abbreviated, and it carries none of the keywords a naive bucket filter would use --
        # it sits in the same "OTHER" pile as 5,497 Annual General Meetings.
        ("Fv Splt Frm Rs 10 To Rs 2", "0.2"),
    ],
)
def test_every_real_split_format_is_parsed(subject: str, expected: str) -> None:
    parsed = parse_subject_factor(subject)
    assert parsed.structural == Decimal(expected)
    assert parsed.dividend == Decimal(1)
    assert "split" in parsed.kinds


@pytest.mark.parametrize(
    ("subject", "expected"),
    [
        ("Bonus 1:1", "0.5"),
        ("Bonus  1:4", "0.8"),
        ("Bonus 1: 2", str(Decimal(2) / Decimal(3))),
        ("Bonus 1:10 (Revised)", str(Decimal(10) / Decimal(11))),
    ],
)
def test_every_real_bonus_format_is_parsed(subject: str, expected: str) -> None:
    parsed = parse_subject_factor(subject)
    assert parsed.structural == Decimal(expected)
    assert "bonus" in parsed.kinds


def test_structural_and_dividend_are_reported_separately_not_multiplied_together() -> None:
    """They are treated differently downstream, so collapsing them loses the distinction.

    A record like this is common in the authority and was previously returned as one number, which
    made it impossible to gap-verify the split without also gap-verifying the dividend.
    """
    subject = (
        "Annual General Meeting/Dividend - Rs 10 Per Share/"
        "Face Value Split (Sub-Division) - From Rs 10/- Per Share To Rs 2/- Per Share"
    )
    parsed = parse_subject_factor(subject, cum_close=Decimal("100"))
    assert parsed.structural == Decimal("0.2")
    assert parsed.dividend == Decimal("90") / Decimal("100")
    assert set(parsed.kinds) == {"dividend", "split"}
    assert parsed.combined == Decimal("0.2") * (Decimal("90") / Decimal("100"))


def test_price_return_leaves_the_dividend_alone() -> None:
    subject = "Dividend - Rs 5 Per Share"
    total = parse_subject_factor(subject, cum_close=Decimal("100"), total_return=True)
    assert total.dividend == Decimal("0.95")

    price_only = parse_subject_factor(subject, cum_close=Decimal("100"), total_return=False)
    assert price_only.dividend == Decimal(1)
    assert price_only.kinds == ()


@pytest.mark.parametrize(
    "subject",
    ["Annual General Meeting", "Extra Ordinary General Meeting", "Interest Payment"],
)
def test_actions_with_no_price_effect_produce_no_factor(subject: str) -> None:
    parsed = parse_subject_factor(subject)
    assert parsed.structural == Decimal(1)
    assert parsed.dividend == Decimal(1)
    assert parsed.kinds == ()
    assert parsed.needs_inference is False


@pytest.mark.parametrize(
    "subject",
    [
        "Rights",
        "Rights 1:26 @ Premium Rs 817/-",
        "Rights 3:25 @ Premium Rs 1799/-",
        "Rights Issue",
    ],
)
def test_a_rights_issue_is_unresolved_rather_than_ignored(subject: str) -> None:
    """A rights issue moves the price, and this parser cannot size it. It must fail closed.

    **This test replaces one that asserted the opposite.** ``"Rights"`` used to sit in the
    ``test_actions_with_no_price_effect_produce_no_factor`` list above, asserting
    ``needs_inference is False`` -- so the suite actively certified the defect as correct behaviour,
    and 90 passing tests, ruff and mypy could not see it.

    The premise was simply false. A rights issue sold at a discount dilutes the existing holding: the
    theoretical ex-rights price is below the cum price by an amount set by the subscription price and
    the ratio. NSE publishes the ratio (``1:26``) but sizing the move also needs the subscription
    price, which the subject line does not reliably carry -- so the action is *recognised and
    refused*, never silently sized and never silently skipped.

    Found by independent adjudication, 2026-09-11: 39 rights issues in the research universe were
    invisible to both the factor path and the unresolved path, so returns measured straight through
    an ex-rights gap were published as if real (reproduced on HCC 2025-12-05, gap -22.94%).
    """
    parsed = parse_subject_factor(subject)
    assert parsed.structural == Decimal(1), "it must not be sized from the text"
    assert parsed.dividend == Decimal(1)
    assert parsed.needs_inference is True, (
        "a recognised-but-unsizeable structural action must be reported unresolved, so that "
        "spans_unresolved() refuses every window crossing it"
    )


# --- rights issues: the four real reproductions from the 2026-09-11 adjudication ---------------
#
# DEFECT-1 (P1) of `.launch/reports/ADJUDICATION-CORPORATE-ACTIONS-20260911.md`. A rights issue
# matched no hint, so it produced no factor *and* no unresolved record: `spans_unresolved` returned
# `False` and the ex-rights gap was published as a real return. The adjudicator reproduced it on
# four symbols against the committed authorities and the all-market cache.
#
# The subject lines below are verbatim from
# `data/evidence/market-cache/all-market-20160822-20260821/corporate-actions/`, and each gap was
# re-measured from that cache by this session before the test was written. The bars are synthetic
# but sized to reproduce the real gap, so the test pins the behaviour without requiring a 4.6M-bar
# cache to be present.

RIGHTS_REPRODUCTIONS = [
    # (symbol, verbatim subject, prev close, ex-date open, gap the adjudication measured)
    ("BHARTIARTL", " Rights 19:67 @ Premium Rs 215 Per Share", "342.95", "319.00", "-6.98%"),
    ("HCC", "Rights 277:630 @ Premium Rs 11.50/-", "25.94", "19.99", "-22.94%"),
    ("CCAVENUE", "Rights 67:267 @ Premium Rs 9/-", "100.00", "90.99", "-9.01%"),
    ("INTELLECT", " Rights 5:22 @ Premium Rs 81/-", "100.00", "91.04", "-8.96%"),
]


def _rights_bars(prev_close: str, ex_open: str) -> list[BarPoint]:
    return [
        _bar(1, float(prev_close)),
        _bar(2, float(prev_close)),
        _bar(3, float(ex_open), open_=float(ex_open)),
        _bar(4, float(ex_open)),
    ]


def _reference_with(plan: AdjustmentPlan) -> AdjustmentReference:
    """A minimal provenance reference carrying one plan's unresolved actions.

    Built through the same mapping `adjusted_acquisition` uses, so this exercises the real consumer
    contract rather than a parallel one.
    """
    return AdjustmentReference(
        method=ADJUSTMENT_METHOD_V1,
        method_version=ADJUSTMENT_METHOD_VERSION_V1,
        status=AdjustmentStatus.ADJUSTED,
        basis=AdjustmentBasis.TOTAL_RETURN,
        authority_id="nse-corporate-actions-TEST",
        authority_content_hash="1" * 64,
        authority_source_url="https://www.nseindia.com/api/corporates-corporateActions",
        authority_publication_date=date(2026, 9, 14),
        code_revision="a4cfa22e",
        derived_at=datetime(2026, 9, 14, 12, 0, 0, tzinfo=UTC),
        source_dataset_id="dset_test",
        source_manifest_hash="f" * 64,
        factors=(),
        unresolved=tuple(
            UnresolvedAction(ex_date=item.ex_date, reason=item.reason, subject=item.subject)
            for item in plan.unresolved
        ),
    )


@pytest.mark.parametrize(
    ("symbol", "subject", "prev_close", "ex_open", "gap"),
    RIGHTS_REPRODUCTIONS,
    ids=[case[0] for case in RIGHTS_REPRODUCTIONS],
)
def test_the_adjudicated_rights_issues_are_refused_not_published(
    symbol: str, subject: str, prev_close: str, ex_open: str, gap: str
) -> None:
    """Each of the four adjudicated cases must produce an unresolved record and no factor.

    HCC is the one that matters most: **-22.94% in a single session**, published as a real return.
    That is the same class of error as the HEG demerger that started the whole corporate-action
    correction, one third the size, and it was still in the data months after HEG was fixed.

    Note what is *not* asserted: nothing here sizes the rights issue. The theoretical ex-rights price
    needs the subscription price, which the subject line does not carry even when it prints the
    ratio. Refusal is the correct outcome, not a placeholder for a better one.
    """
    bars = _rights_bars(prev_close, ex_open)
    plan = build_adjustment_factors([(date(2026, 1, 3), subject)], bars)

    observed = Decimal(ex_open) / Decimal(prev_close) - 1
    assert f"{float(observed):+.2%}" == gap, "the fixture must reproduce the measured gap"

    assert plan.factors == (), f"{symbol}: a rights issue is never sized from its own gap"
    assert len(plan.unresolved) == 1, f"{symbol}: the action must be recorded, not dropped"
    assert plan.unresolved[0].ex_date == date(2026, 1, 3)
    assert plan.unresolved[0].subject == subject.strip()
    adjusted = adjust_bars(bars, plan.factors)
    assert [b.close for b in adjusted] == [b.close for b in bars], "prices are left exactly alone"


@pytest.mark.parametrize(
    ("symbol", "subject", "prev_close", "ex_open", "gap"),
    RIGHTS_REPRODUCTIONS,
    ids=[case[0] for case in RIGHTS_REPRODUCTIONS],
)
def test_a_window_spanning_an_adjudicated_rights_issue_is_refused(
    symbol: str, subject: str, prev_close: str, ex_open: str, gap: str
) -> None:
    """The guarantee the adjudication actually disproved, asserted end to end.

    C4 of the brief: *"windows spanning an unresolved action are dropped, not published with a
    fabricated return."* It held for demergers and failed for rights issues, because the refusal is
    driven by the unresolved record and no rights issue ever produced one. This test walks the whole
    consumer contract -- plan -> `UnresolvedAction` -> `spans_unresolved` -- rather than stopping at
    the parser, so it fails if any link is broken, not only the first.
    """
    plan = build_adjustment_factors(
        [(date(2026, 1, 3), subject)], _rights_bars(prev_close, ex_open)
    )
    reference = _reference_with(plan)

    assert spans_unresolved(reference, after=date(2026, 1, 2), through=date(2026, 1, 4)) is True, (
        f"{symbol}: a window holding across the ex-rights date must be refused"
    )
    assert spans_unresolved(reference, after=date(2026, 1, 3), through=date(2026, 1, 4)) is False, (
        "the window is half-open: an ex-date at `after` is already reflected in that price"
    )
    assert spans_unresolved(reference, after=date(2026, 1, 1), through=date(2026, 1, 2)) is False, (
        "a window entirely before the action is untouched -- fail-closed must stay targeted"
    )


def test_a_rights_issue_bundled_with_a_sized_bonus_still_refuses_the_window() -> None:
    """The rights defect one level deeper, found by this session rather than by the adjudication.

    The repair that closed DEFECT-1 asked ``structural_hinted and not structural_sized`` -- a single
    question about the whole subject line. So *any* sized component vouched for every other one, and
    a record carrying a bonus **and** a rights issue sized the bonus, reported nothing unresolved,
    and published the ex-rights gap exactly as before.

    Measured over the whole all-market cache (3,359 symbol files, 19,941 records) at the time of
    writing: **0 of 255 rights records bundle with a sized structural action**, so no published
    number was ever affected by this. It is fixed because the corpus is not the specification -- the
    guarantee has to hold for whatever NSE publishes next, and a fail-closed rule that depends on
    issuers never combining two effects in one subject line is not fail-closed.
    """
    bars = [_bar(1, 100.0), _bar(2, 100.0), _bar(3, 46.0, open_=46.0), _bar(4, 46.0)]
    plan = build_adjustment_factors(
        [(date(2026, 1, 3), "Bonus 1:1/Rights 1:5 @ Premium Rs 100")], bars
    )

    assert [item.ex_date for item in plan.unresolved] == [date(2026, 1, 3)], (
        "the rights issue must be refused even though the bonus in the same record was sized"
    )
    assert spans_unresolved(
        _reference_with(plan), after=date(2026, 1, 2), through=date(2026, 1, 4)
    ), "and the refusal must reach the consumer contract, not stop at the parser"


def test_the_refusal_says_something_true_about_a_rights_issue() -> None:
    """A correct refusal for a false stated reason is still a defective audit trail.

    Every one of the four adjudicated cases was refused as ``RATIO_NOT_PUBLISHED`` -- *"no usable
    ratio could be parsed from this action"* -- against a subject line that prints ``Rights 19:67``.
    The ratio is published. What NSE does not publish is the subscription price that turns it into a
    theoretical ex-rights price. The next step in this workflow is a human opening the filing to look
    for the missing piece, and that reader was being sent after the wrong one.
    """
    bars = _rights_bars("342.95", "319.00")
    rights = build_adjustment_factors(
        [(date(2026, 1, 3), " Rights 19:67 @ Premium Rs 215 Per Share")], bars
    )
    assert rights.unresolved[0].reason == "RIGHTS_NOT_SIZEABLE"
    assert "subscription price" in rights.unresolved[0].detail
    assert "no usable ratio" not in rights.unresolved[0].detail, (
        "the ratio 19:67 is printed in the subject line"
    )
    assert "not proof of the amount" in rights.unresolved[0].detail, (
        "the refusal still says why the gap cannot stand in for the size"
    )

    demerger = build_adjustment_factors([(date(2026, 1, 3), "Demerger")], bars)
    assert demerger.unresolved[0].reason == "RATIO_NOT_PUBLISHED", (
        "the demerger code is unchanged: a demerger really does publish no ratio"
    )


def test_a_record_with_two_unsized_actions_reports_both() -> None:
    """A real record from the corpus, carrying two different unsized effects at once.

    TVSMOTOR 2025-08-25 is ``Scheme Of Arrangement - Bonus Ncrps 4:1``. Both halves are recognised
    and neither is sizeable: ``_BONUS_RE`` wants ``Bonus a:b`` and cannot read ``Bonus Ncrps 4:1``,
    and a scheme of arrangement publishes no ratio at all. The two refusals have different reasons,
    so collapsing them to whichever was checked first would drop a real finding from the audit trail.

    This is the one record in the 423-name research universe that exercises the path, and it is the
    reason the code enumerates every unsized component rather than reporting only the first.
    """
    bars = [_bar(1, 100.0), _bar(2, 100.0), _bar(3, 100.0), _bar(4, 100.0)]
    plan = build_adjustment_factors(
        [(date(2026, 1, 3), "Scheme Of Arrangement - Bonus Ncrps 4:1")], bars
    )

    assert plan.factors == ()
    unresolved = plan.unresolved[0]
    assert unresolved.reason == "MULTIPLE_UNSIZED_ACTIONS", (
        "two components refused for different reasons must not be reported as one of them"
    )
    assert "no a:b ratio could be read" in unresolved.detail, "the bonus half is named"
    assert "no usable ratio could be parsed" in unresolved.detail, "the scheme half is named"
    assert spans_unresolved(
        _reference_with(plan), after=date(2026, 1, 2), through=date(2026, 1, 4)
    ), "and the window is refused"


def test_a_structural_action_alongside_a_dividend_is_still_unresolved() -> None:
    """The old rule used ``not kinds``, so a sized dividend suppressed an unsized structural action.

    A single NSE record routinely carries both. Pricing the dividend and declaring the demerger
    resolved is the same class of silent pass-through as the rights defect.
    """
    parsed = parse_subject_factor(
        "Dividend - Rs 10/- Per Share/Scheme Of Arrangement", cum_close=Decimal("1000")
    )
    assert "dividend" in parsed.kinds, "the dividend is still priced"
    assert parsed.needs_inference is True, "the unsized structural action still refuses the window"


def test_a_buyback_is_not_swept_into_unresolved() -> None:
    """Fail-closed must stay targeted, or it refuses windows for no reason.

    A tender-offer buyback has a record date but no ex-date price adjustment. 140 exist in the
    research universe; treating them as unresolved would discard 140 windows to no purpose.
    """
    parsed = parse_subject_factor("Buy Back of Shares")
    assert parsed.needs_inference is False


@pytest.mark.parametrize(
    "subject", ["Demerger", "Scheme Of Demerger", "Scheme Of Arrangement Of Demerger"]
)
def test_a_ratioless_demerger_is_flagged_for_inference(subject: str) -> None:
    parsed = parse_subject_factor(subject)
    assert parsed.structural == Decimal(1)
    assert parsed.kinds == ()
    assert parsed.needs_inference is True


# --- the regression that matters ------------------------------------------------------------


def test_an_already_adjusted_split_is_refused_not_applied_again() -> None:
    """The +945% bug. This is the single most important test in the file.

    The bars either side of the ex-date show an ordinary +1% day, so the provider has already
    applied the 10:1 ratio. Applying it again would scale ten years of history by 0.1.
    """
    bars = [_bar(1, 100.0), _bar(2, 101.0, open_=101.0), _bar(3, 102.0)]
    factors, skipped = build_adjustment_factors([(date(2026, 1, 2), SPLIT_10_TO_1)], bars)

    assert factors == [], "a split the provider already applied must not be applied twice"
    assert len(skipped) == 1
    assert "already applied by the provider" in skipped[0]

    unchanged = adjust_bars(bars, factors)
    assert [b.close for b in unchanged] == [b.close for b in bars]


def test_a_genuinely_unapplied_split_is_still_corrected() -> None:
    """The check must not become a blanket refusal: a real -90% gap is a real split."""
    bars = [_bar(1, 1000.0), _bar(2, 100.0, open_=100.0), _bar(3, 101.0)]
    factors, skipped = build_adjustment_factors([(date(2026, 1, 2), SPLIT_10_TO_1)], bars)

    assert len(factors) == 1
    assert factors[0].factor == Decimal("0.1")
    assert factors[0].source == "PARSED"
    adjusted = adjust_bars(bars, factors)
    assert adjusted[0].close == Decimal("100.0")
    assert abs(float(adjusted[1].close / adjusted[0].close - 1)) < 0.01


def test_a_dividend_is_applied_without_gap_verification() -> None:
    """No gap can distinguish "already applied" from "correctly quoted" for a payout."""
    bars = [_bar(1, 100.0), _bar(2, 99.0, open_=99.0), _bar(3, 99.5)]
    factors, _ = build_adjustment_factors(
        [(date(2026, 1, 2), "Dividend - Rs 1 Per Share")], bars, total_return=True
    )
    assert len(factors) == 1
    assert factors[0].kinds == ("dividend",)
    assert factors[0].factor == Decimal("99") / Decimal("100")


def test_price_return_basis_produces_no_dividend_factor() -> None:
    bars = [_bar(1, 100.0), _bar(2, 99.0, open_=99.0), _bar(3, 99.5)]
    factors, _ = build_adjustment_factors(
        [(date(2026, 1, 2), "Dividend - Rs 1 Per Share")], bars, total_return=False
    )
    assert factors == []


def test_a_combined_record_gap_verifies_the_split_but_keeps_the_dividend() -> None:
    """The reason the components are parsed apart, exercised end to end."""
    subject = "Dividend - Rs 1 Per Share/" + SPLIT_10_TO_1
    bars = [_bar(1, 100.0), _bar(2, 99.0, open_=99.0), _bar(3, 99.5)]
    factors, skipped = build_adjustment_factors([(date(2026, 1, 2), subject)], bars)

    kinds = [k for f in factors for k in f.kinds]
    assert kinds == ["dividend"], "the split is already applied; the dividend is still a choice"
    assert any("already applied by the provider" in s for s in skipped)


# --- the blind band: why an absolute tolerance in factor space was wrong -----------------------
#
# The previous rule applied a published factor when |observed - factor| <= 0.20. That test cannot
# separate its two hypotheses whenever |1 - factor| <= 0.40, because one observation then satisfies
# both -- and it broke the tie toward "not applied", double-adjusting a series the provider had
# already fixed. Measured on the 423-name research universe, 57 of 212 published-ratio actions
# (27%) fell in that band, every one of them a bonus, and the corpus says the provider had applied
# all 57.


@pytest.mark.parametrize(
    ("subject", "factor_text", "name"),
    [
        ("Bonus 1:10", "0.909090909", "ICICIBANK 2017-06-20"),
        ("Bonus 1:5", "0.833333333", "NTPC 2019-03-19"),
        ("Bonus 1:4", "0.8", "PFC 2023-09-21"),
        ("Bonus 1:3", "0.75", "POWERGRID 2021-07-29"),
        ("Bonus 1:2", "0.666666667", "LT 2017-07-13"),
    ],
)
def test_a_bonus_the_provider_already_applied_is_not_applied_a_second_time(
    subject: str, factor_text: str, name: str
) -> None:
    """Each of these sat in the old rule's blind band and would have been double-adjusted."""
    bars = [_bar(1, 100.0), _bar(2, 100.5, open_=100.5), _bar(3, 101.0)]
    plan = build_adjustment_factors([(date(2026, 1, 2), subject)], bars)

    assert plan.factors == (), f"{name}: a +0.5% gap is not the published ratio {factor_text}"
    assert plan.unresolved == ()
    assert any("already applied by the provider" in note for note in plan.notes)
    assert [b.close for b in adjust_bars(bars, plan.factors)] == [b.close for b in bars]


@pytest.mark.parametrize(
    ("subject", "ex_open"),
    [("Bonus 1:10", 90.9), ("Bonus 1:5", 83.3), ("Bonus 1:2", 66.7)],
)
def test_a_bonus_the_provider_did_not_apply_is_still_caught(subject: str, ex_open: float) -> None:
    """The other side of the same rule: it must not become a blanket refusal."""
    bars = [_bar(1, 100.0), _bar(2, ex_open, open_=ex_open), _bar(3, ex_open)]
    plan = build_adjustment_factors([(date(2026, 1, 2), subject)], bars)

    assert len(plan.factors) == 1, "a gap matching the published ratio must still be corrected"
    assert plan.factors[0].source == "PARSED"
    adjusted = adjust_bars(bars, plan.factors)
    assert abs(float(adjusted[1].close / adjusted[0].close - 1)) < 0.01


def test_a_gap_matching_neither_hypothesis_is_unresolved_not_forced() -> None:
    """A -40% gap on a 1:10 bonus is neither 'already applied' nor the published ratio."""
    bars = [_bar(1, 100.0), _bar(2, 60.0, open_=60.0), _bar(3, 60.0)]
    plan = build_adjustment_factors([(date(2026, 1, 2), "Bonus 1:10")], bars)

    assert plan.factors == ()
    assert [item.reason for item in plan.unresolved] == ["MATCHES_NEITHER_HYPOTHESIS"]


def test_a_structural_action_with_no_ex_date_bar_is_unresolved() -> None:
    """Neither hypothesis can be scored without the gap, so neither may be assumed."""
    bars = [_bar(1, 100.0), _bar(3, 100.0)]
    plan = build_adjustment_factors([(date(2026, 1, 2), SPLIT_10_TO_1)], bars)

    assert plan.factors == ()
    assert [item.reason for item in plan.unresolved] == ["NO_EX_DATE_BAR"]


# --- demergers: what the provider really does leave behind ------------------------------------


def test_a_demerger_is_never_sized_from_the_ex_date_gap() -> None:
    """The gap is the action plus the day's market movement. It cannot separate the two."""
    bars = [_bar(1, 100.0), _bar(2, 100.0), _bar(3, 35.0, open_=35.0), _bar(4, 34.0)]
    plan = build_adjustment_factors([(date(2026, 1, 3), "Demerger")], bars)
    assert plan.factors == ()
    assert [item.reason for item in plan.unresolved] == ["RATIO_NOT_PUBLISHED"]
    assert "not proof of the amount" in plan.unresolved[0].detail


def test_a_positive_gap_demerger_is_not_turned_into_an_upward_correction() -> None:
    """The case that condemned gap inference, from the real corpus.

    NMDC's 2022-10-27 demerger ex-date shows **+71.0%**. A demerger cannot raise the parent's price,
    so that gap is market movement, a provider adjustment, or both. The previous rule inferred a
    factor of 1.71 from it -- scaling six years of prior history *up* by 71%, erasing a genuine move
    and inventing a fake one in its place. BAJAJELEC (+32.2%) and SCI (+30.0%) sat in the same trap.
    """
    bars = [_bar(1, 100.0), _bar(2, 100.0), _bar(3, 171.0, open_=171.0), _bar(4, 170.0)]
    plan = build_adjustment_factors([(date(2026, 1, 3), "Demerger")], bars)
    assert plan.factors == (), "no upward 'correction' may be manufactured from a positive gap"
    assert plan.unresolved[0].reason == "RATIO_NOT_PUBLISHED"
    adjusted = adjust_bars(bars, plan.factors)
    assert [b.close for b in adjusted] == [b.close for b in bars], "prices are left exactly alone"


def test_a_small_gap_demerger_is_also_unresolved_rather_than_ignored() -> None:
    """A 3% gap is not proof of a 3% entitlement, and it is not proof of no entitlement either."""
    bars = [_bar(1, 100.0), _bar(2, 100.0), _bar(3, 97.0, open_=97.0), _bar(4, 96.0)]
    plan = build_adjustment_factors([(date(2026, 1, 3), "Demerger")], bars)
    assert plan.factors == ()
    assert len(plan.unresolved) == 1, "the event is recorded so consumers can refuse the window"


def test_an_independently_validated_demerger_factor_is_applied_and_labelled() -> None:
    """The one admissible route: a size established outside the gap."""
    bars = [_bar(1, 100.0), _bar(2, 100.0), _bar(3, 35.0, open_=35.0), _bar(4, 34.0)]
    plan = build_adjustment_factors(
        [(date(2026, 1, 3), "Demerger")],
        bars,
        validated_factors={
            date(2026, 1, 3): ValidatedFactor(
                Decimal("0.35"), "RESULTCO first open INR 65.00, entitlement 1:1 per filing"
            )
        },
    )
    assert len(plan.factors) == 1
    assert plan.factors[0].source == "VALIDATED"
    assert plan.factors[0].factor == Decimal("0.35")
    assert "RESULTCO first open" in plan.factors[0].detail
    assert plan.unresolved == ()


def test_a_validated_factor_must_name_its_evidence() -> None:
    with pytest.raises(CorporateActionError, match="corroborating evidence"):
        ValidatedFactor(Decimal("0.35"), "   ")


def test_a_supplied_factor_matching_no_action_is_reported_not_applied() -> None:
    """A validated factor on the wrong date must not silently adjust the series."""
    bars = [_bar(1, 100.0), _bar(2, 100.0), _bar(3, 35.0, open_=35.0)]
    plan = build_adjustment_factors(
        [(date(2026, 1, 3), "Demerger")],
        bars,
        validated_factors={date(2026, 1, 2): ValidatedFactor(Decimal("0.5"), "wrong date")},
    )
    assert plan.factors == ()
    assert any("matched no ratio-less action" in note for note in plan.notes)
    assert plan.unresolved[0].ex_date == date(2026, 1, 3)


def test_bars_out_of_order_are_refused() -> None:
    with pytest.raises(CorporateActionError, match="ascending date order"):
        build_adjustment_factors([], [_bar(3, 100.0), _bar(1, 100.0)])


# --- application mechanics ---------------------------------------------------------------------


def _validated(on: date, factor: str) -> dict[date, ValidatedFactor]:
    return {on: ValidatedFactor(Decimal(factor), "RESULTCO first open, entitlement per filing")}


def test_back_adjustment_removes_the_discontinuity_and_leaves_real_returns_intact() -> None:
    bars = [_bar(1, 500.0), _bar(2, 505.0), _bar(3, 101.0, open_=101.0), _bar(4, 102.0)]
    plan = build_adjustment_factors(
        [(date(2026, 1, 3), "Demerger")],
        bars,
        validated_factors=_validated(date(2026, 1, 3), "0.2"),
    )
    adjusted = adjust_bars(bars, plan.factors)

    assert float(bars[2].close / bars[1].close - 1) < -0.79
    assert abs(float(adjusted[2].close / adjusted[1].close - 1)) < 0.02
    assert adjusted[1].close / adjusted[0].close == bars[1].close / bars[0].close
    assert adjusted[3].close == bars[3].close, "the newest bars are never adjusted"


def test_volume_is_rescaled_inversely_to_price() -> None:
    bars = [_bar(1, 500.0, volume=1000), _bar(2, 100.0, open_=100.0, volume=5000)]
    plan = build_adjustment_factors(
        [(date(2026, 1, 2), "Demerger")],
        bars,
        validated_factors=_validated(date(2026, 1, 2), "0.2"),
    )
    adjusted = adjust_bars(bars, plan.factors)
    assert adjusted[0].close == Decimal("100.0")
    assert adjusted[0].volume == 5000
    assert adjusted[1].volume == 5000, "the newest bar is untouched"


def test_validated_factors_can_be_refused() -> None:
    """A consumer that will only trust the authority's own published ratios can say so."""
    bars = [_bar(1, 100.0), _bar(2, 100.0), _bar(3, 35.0, open_=35.0)]
    plan = build_adjustment_factors(
        [(date(2026, 1, 3), "Demerger")],
        bars,
        validated_factors=_validated(date(2026, 1, 3), "0.35"),
    )
    assert adjust_bars(bars, plan.factors, allow_validated=True)[0].close == Decimal("35.00")
    assert adjust_bars(bars, plan.factors, allow_validated=False)[0].close == Decimal("100")


# --- against the real authority and the real bars -----------------------------------------------


def test_the_real_heg_demerger_is_left_unresolved_because_nothing_prices_the_entitlement() -> None:
    """End to end on the event that started this: HEG, 2026-09-07, -64.3% on 3.6M shares.

    The entitlement is one HEG Graphite share per HEG share, per the company filing. HEG Graphite
    is **not in this repository's market cache** -- it listed after the cache window closed -- so
    nothing here can price the entitlement. The -64.3% gap is therefore not evidence of a -64.3%
    loss, and it is not evidence of the entitlement's value either. Unresolved is the only honest
    verdict, and it is what lets the paper book disclose an unpriced asset instead of booking a
    fabricated loss or a fabricated recovery.
    """
    ca = (
        REPO_ROOT
        / "data/evidence/market-cache/nifty500-refresh-20230828-20260827"
        / "corporate-actions/nse-corporate-actions-HEG.json"
    )
    records = json.loads(ca.read_text(encoding="utf-8"))
    assert any("Demerger" in str(r.get("subject", "")) for r in records)

    bars = [
        BarPoint(date(2026, 9, 3), *[Decimal("707.45")] * 4, 1656554),
        BarPoint(date(2026, 9, 4), *[Decimal("728.25")] * 4, 2565950),
        BarPoint(date(2026, 9, 7), Decimal("260.00"), *[Decimal("272.20")] * 3, 3615221),
        BarPoint(date(2026, 9, 8), *[Decimal("258.60")] * 4, 1334287),
    ]
    plan = build_adjustment_factors([(date(2026, 9, 7), "Demerger")], bars)
    assert plan.factors == ()
    assert [item.reason for item in plan.unresolved] == ["RATIO_NOT_PUBLISHED"]

    adjusted = adjust_bars(bars, plan.factors)
    assert [b.close for b in adjusted] == [b.close for b in bars], "raw prices are preserved"


@pytest.mark.parametrize(
    ("subject", "expected"),
    [
        ("Dividend - Rs 4/- Per Share", Decimal("4")),
        ("Dividend Rs 4 Per Share", Decimal("4")),
        ("Dividend - Rs 4.50/- Per Share", Decimal("4.50")),
        ("Annual General Meeting/Dividend - Rs 10/- Per Share", Decimal("10")),
    ],
)
def test_a_dividend_is_priced_with_or_without_the_rupee_suffix(
    subject: str, expected: Decimal
) -> None:
    """Issuers write ``Rs 4/-`` and ``Rs 4`` interchangeably, and both must price.

    ``_DIVIDEND_RE`` omitted the optional ``/-`` while ``_SPLIT_RE`` two lines above already allowed
    it, so ``Dividend - Rs 4/- Per Share`` matched nothing. The payout was then left in the series
    with **no factor and no unresolved record**, so nothing downstream could refuse it.

    Found by independent adjudication, 2026-09-11: 493 of 5,083 dividend records in the research
    universe (9.7%) were silently unpriced this way.
    """
    cum_close = Decimal("1000")
    parsed = parse_subject_factor(subject, cum_close=cum_close)
    assert "dividend" in parsed.kinds
    assert parsed.dividend == (cum_close - expected) / cum_close


def test_a_face_value_figure_in_the_split_clause_is_not_read_as_a_dividend() -> None:
    """A misprice is worse than a missing price, and this fix nearly introduced one.

    Accepting the optional ``/-`` suffix (the repair for the 493 unpriced dividends) had a side
    effect: ``Rs 10/- Per Share`` inside a *split* clause suddenly matched the dividend pattern, so
    a record naming a dividend with no amount priced a Rs 10 dividend that does not exist. The old
    regex avoided this only by accident, because it rejected the ``/-`` form entirely.

    Amounts lying inside the split match are therefore skipped. Caught by re-measuring the repair on
    the real corpus rather than by the suite.
    """
    no_amount = parse_subject_factor(
        "Dividend/Face Value Split From Rs 10/- Per Share To Rs 2/- Per Share",
        cum_close=Decimal("1000"),
    )
    assert no_amount.structural == Decimal("0.2"), "the split is still sized"
    assert no_amount.dividend == Decimal(1), "the face value is not a payout"
    assert "dividend" not in no_amount.kinds

    real = parse_subject_factor(
        "Annual General Meeting/Dividend - Rs 10 Per Share/"
        "Face Value Split (Sub-Division) - From Rs 10/- Per Share To Rs 2/- Per Share",
        cum_close=Decimal("1000"),
    )
    assert real.structural == Decimal("0.2")
    assert real.dividend == Decimal("990") / Decimal("1000"), "a real dividend still prices"


def test_a_dividend_with_no_stated_amount_is_left_unpriced() -> None:
    """``Interim Dividend`` carries no figure, so there is nothing to remove.

    52 such records remain in the research universe (1.0% of dividend-bearing records). They are left
    alone deliberately: guessing an amount would fabricate a return, and a dividend is a
    return-definition choice rather than a provider error to repair.
    """
    parsed = parse_subject_factor("Interim Dividend", cum_close=Decimal("1000"))
    assert parsed.dividend == Decimal(1)
    assert parsed.kinds == ()
