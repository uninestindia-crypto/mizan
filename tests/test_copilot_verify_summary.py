"""What a panel of opinions adds up to: a plurality is not a majority, and missing answers are named."""

from __future__ import annotations

import pytest

from quant_system.copilot.factpack import FactPack, FactSection
from quant_system.copilot.verify import VerifyOptions, verify_stock
from quant_system.copilot.verify_opinion import Opinion
from quant_system.copilot.verify_summary import ModelVerdict, VerificationResult, summarise
from tests.copilot_fakes import StubModel, opinion_json

P, M, N, U = "POSITIVE", "MIXED", "NEGATIVE", "UNCLEAR"
PACK = FactPack("AAA", (), (), None)


def _blind(reading: str | None) -> Opinion:
    if reading is None:
        return Opinion("p", "m", "blind", False, error="down")
    return Opinion("p", "m", "blind", True, reading, "NEUTRAL")


def _result(readings: list[str | None], asked: int | None = None) -> VerificationResult:
    verdicts = [ModelVerdict(_blind(reading)) for reading in readings]
    return summarise(PACK, verdicts, asked or len(readings), [])


# (readings, asked, consensus, shared reading, headline)
SUMMARIES = [
    pytest.param(
        [P, P, M, N],
        4,
        "SPLIT",
        None,
        "The 4 models disagree with each other. There is no shared reading.",
        id="two-one-one-of-four-is-a-plurality-not-a-majority",
    ),
    pytest.param(
        [P, P, N, N],
        4,
        "SPLIT",
        None,
        "The 4 models disagree with each other. There is no shared reading.",
        id="an-even-tie",
    ),
    pytest.param(
        [P, P, M, N, U],
        5,
        "SPLIT",
        None,
        "The 5 models disagree with each other. There is no shared reading.",
        id="two-of-five-is-not-a-majority",
    ),
    pytest.param(
        [P, P, P, M, N],
        5,
        "MAJORITY",
        P,
        "3 of 5 models read the facts as POSITIVE.",
        id="three-of-five-is-a-majority",
    ),
    pytest.param(
        [M, M, P],
        3,
        "MAJORITY",
        M,
        "2 of 3 models read the facts as MIXED.",
        id="two-of-three-is-a-majority",
    ),
    pytest.param(
        [M, M, M], 3, "AGREE", M, "All 3 models read the facts as MIXED.", id="everyone-agrees"
    ),
    pytest.param(
        [P, P, None, None, None],
        5,
        "AGREE",
        P,
        "2 of 5 models answered, and both read the facts as POSITIVE.",
        id="two-of-five-answered-and-agree",
    ),
    pytest.param(
        [M, M, M, None, None],
        5,
        "AGREE",
        M,
        "3 of 5 models answered, and all read the facts as MIXED.",
        id="three-of-five-answered-and-agree",
    ),
    pytest.param(
        [P, P, M, None, None],
        5,
        "MAJORITY",
        P,
        "3 of 5 models answered, and 2 of them read the facts as POSITIVE.",
        id="a-majority-of-those-who-answered",
    ),
    pytest.param(
        [P, N, None, None],
        4,
        "SPLIT",
        None,
        "2 of 4 models answered, and they disagree with each other. There is no shared reading.",
        id="a-split-among-those-who-answered",
    ),
    pytest.param(
        [P, None, None, None],
        4,
        "SINGLE",
        P,
        "Only 1 of 4 models answered, so nothing was cross-checked. It read the facts as POSITIVE.",
        id="one-answer-of-four",
    ),
    pytest.param(
        [P],
        1,
        "SINGLE",
        P,
        "Only 1 model was asked, so nothing was cross-checked. It read the facts as POSITIVE.",
        id="one-model-alone",
    ),
    pytest.param(
        [None, None],
        2,
        "NONE",
        None,
        "None of the AI models could answer, so there is no second opinion yet.",
        id="nobody-answered",
    ),
]


@pytest.mark.parametrize(("readings", "asked", "consensus", "reading", "headline"), SUMMARIES)
def test_the_consensus_and_headline_say_exactly_how_many_agreed_and_how_many_answered(
    readings: list[str | None], asked: int, consensus: str, reading: str | None, headline: str
) -> None:
    result = _result(readings, asked)
    assert (result.consensus, result.reading, result.headline) == (consensus, reading, headline)


@pytest.mark.parametrize("readings", [[P, P, M, N], [P, P, P, None], [P, P, None, None, None]])
def test_a_headline_never_says_evidence(readings: list[str | None]) -> None:
    assert "evidence" not in _result(readings).headline.lower()


@pytest.mark.parametrize("readings", [[P, P, None], [P, P, None, None, None], [M, M, M, None]])
def test_a_headline_never_says_all_when_some_models_did_not_answer(
    readings: list[str | None],
) -> None:
    assert "All" not in _result(readings).headline


def test_when_the_models_do_not_share_a_reading_every_answer_is_shown_as_a_difference() -> None:
    result = _result([P, P, M, N])
    assert len(result.dissent) == 4 and result.reading is None


def test_the_models_that_differ_from_a_true_majority_are_the_dissenters() -> None:
    result = _result([P, P, P, N])
    assert [d["reading"] for d in result.dissent] == [N]


# ------------------------------------------------------------------------------------- anchoring


def _told(blind: str, informed: str) -> ModelVerdict:
    return ModelVerdict(_blind(blind), Opinion("p", "m", "informed", True, informed, "NEUTRAL"))


@pytest.mark.parametrize(
    ("blind", "informed"),
    [
        pytest.param(M, P, id="more-favourable"),
        pytest.param(P, M, id="less-favourable"),
        pytest.param(P, N, id="much-less-favourable"),
        pytest.param(U, P, id="from-unclear"),
        pytest.param(P, U, id="to-unclear"),
    ],
)
def test_a_changed_reading_after_the_hint_is_anchoring_in_either_direction(
    blind: str, informed: str
) -> None:
    result = summarise(PACK, [_told(blind, informed), _told(M, M)], 2, [])
    notes = [n for n in result.notes if "changed their reading after being told" in n]
    assert len(notes) == 1 and notes[0].startswith("1 of 2 model(s)")
    assert "QuantOS's own model picked it" in notes[0] and "anchoring" in notes[0]


def test_readings_that_do_not_move_after_the_hint_raise_no_anchoring_note() -> None:
    result = summarise(PACK, [_told(M, M), _told(P, P)], 2, [])
    assert [n for n in result.notes if "anchoring" in n] == []


# ------------------------------------------------------------------------------------- stability


def _one_section_pack() -> FactPack:
    section = FactSection("stock_facts", "Price history facts", "{}", "Returns", False)
    return FactPack("AAA", (section,), (), None)


def test_with_one_section_of_facts_the_recheck_is_not_a_reorder_so_it_is_not_asked_or_reported() -> (
    None
):
    model = StubModel("p0", opinion_json())
    result = verify_stock([model], _one_section_pack(), VerifyOptions(recheck=True))
    assert len(model.calls) == 1 and result.verdicts[0].recheck is None
    assert [n for n in result.notes if "changed their reading when" in n] == []
    assert any("could not be shown in a different order" in n for n in result.notes)


def test_without_a_recheck_asked_for_there_is_no_note_about_reordering() -> None:
    model = StubModel("p0", opinion_json())
    result = verify_stock([model], _one_section_pack(), VerifyOptions(recheck=False))
    assert [n for n in result.notes if "different order" in n] == []
