"""What a second-opinion model writes is checked by the shared guard: dressed-up advice and halal rulings go."""

from __future__ import annotations

from typing import Any

import pytest

from quant_system.copilot.verify_opinion import Opinion, Question, ask_for_opinion
from tests.copilot_fakes import StubModel, opinion_json

KEEP = "Steady returns"

# Each of these slipped past the old word lists.
ADVICE = [
    "Strong buying interest",
    "A buying opportunity",
    "Good time to buy",
    "Accumulating on dips",
    "an accumulation zone",
    "Go long here",
    "going short is risky",
    "add to your position",
    "adding to the holding",
    "exit before results",
    "Book profits at 4200",
    "booking your profits",
    "overweight the sector",
    "It could outperform the index",
    "Fair value is Rs 4,000",
    "expected to reach 4200 within a year",
    "upside of 30% from here",
    "Sells before results",
    "ｂｕｙ now",
    "b​uy now",
    "b⁠uy now",
    "B U Y now",
    "B.U.Y. now",
    "BUY-rated by many",
    "Stop loss at 3400",
    "I recommend this stock",
]
HALAL = [
    "Islamically compliant",
    "compliant with Islamic finance principles",
    "AAOIFI compliant",
    "TASIS compliant",
    "riba-free",
    "halāl",
    "ḥalāl according to the screen",
    "sh​ariah screen passed",
    "Shariah-friendly",
    "permissible to hold",
    "lawful under Islamic law",
]
FIELDS = ["reasons", "risks", "missing"]


def _opinion(**fields: Any) -> Opinion:
    reply = opinion_json(**fields)
    return ask_for_opinion(StubModel("p0", reply), Question("blind", "facts"))


@pytest.mark.parametrize("field", FIELDS)
@pytest.mark.parametrize("text", [*ADVICE, *HALAL])
def test_dressed_up_advice_and_halal_wording_is_removed_and_counted(field: str, text: str) -> None:
    opinion = _opinion(**{field: [text, KEEP]})
    assert getattr(opinion, field) == (KEEP,)
    assert opinion.removed == 1


@pytest.mark.parametrize(
    "text",
    [
        "A broad sell-off would hurt it",
        "The company announced a share buyback.",
        "Debt to assets is 5.0%.",
        "Volatility is high compared with the index.",
    ],
)
def test_ordinary_facts_and_risks_are_kept(text: str) -> None:
    opinion = _opinion(risks=[text])
    assert opinion.risks == (text,) and opinion.removed == 0


def test_only_four_statements_are_kept_but_every_removed_one_is_counted() -> None:
    opinion = _opinion(
        reasons=[*[f"Fact number {n}" for n in range(6)], "Buy it", "Fair value is 9"]
    )
    assert len(opinion.reasons) == 4 and opinion.removed == 2


def test_a_statement_is_judged_after_it_is_cut_to_the_length_the_person_would_see() -> None:
    opinion = _opinion(reasons=["x" * 400 + " buy now"])
    assert opinion.reasons == ("x" * 300,) and opinion.removed == 0


def test_blank_statements_are_dropped_without_being_counted_as_removed() -> None:
    opinion = _opinion(reasons=["   ", "", KEEP])
    assert opinion.reasons == (KEEP,) and opinion.removed == 0
