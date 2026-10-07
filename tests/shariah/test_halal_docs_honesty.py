"""The README and the manifesto say the Shariah mode is a prototype on a sample, not a shipped, audited product."""

import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
README = ROOT / "README.md"
PAPER = ROOT / "docs" / "HALAL_WHITE_PAPER.md"
PROTOTYPE_LABEL = "Working prototype on a 39-company illustrative sample. Not live, not audited."
UNVERIFIED = "unverified, source needed"
STATUS_LABELS = ("SHIPPED", "PARTIAL", "PLANNED")
# Figures from the earlier text that have no source in the repository.
UNSOURCED_FIGURES = [
    "$4.5 trillion",
    "$5.9 trillion",
    "over 70%",
    "97%",
    "under 2%",
    "50+ trillion",
    "4,000 crore",
    "800 crore",
    "5,600 crore",
    "93% loss rate",
    "12 to 18%",
    "7 to 9% yields",
    "200 million",
]
FORBIDDEN = [
    "Pre-audited",
    "Shipped & Live",
    "Shipped &amp; Live",
    "Cryptographic Line-Item Verification",
    "Shariah Alpha",
    "Empirical Proof",
    "superior long-term risk-adjusted returns",
    "1-Click Zero-Margin Broker Execution",
    "1-Click order sheet",
    "137/137",
    "160/160",
    "sub-50",
    "high-alpha",
    "Continuous Compliance Drift Monitor",
    "< 33.33%",
    "aligned with Indian scholarly consensus",
]


def blocks(text: str) -> list[str]:
    """Paragraphs, bullets and table rows, each on one line."""
    return [" ".join(part.split()) for part in re.split(r"\n\s*\n|\n(?=[-|])", text)]


CORRECTION_MARKS = ("earlier", "PLANNED", "withdrawn", "not screened", "None of")


def uncorrected_mentions(text: str, phrase: str) -> list[str]:
    """Blocks that mention a false claim without saying it is the earlier text, planned, or withdrawn."""
    return [
        block
        for block in blocks(text)
        if phrase.lower() in block.lower() and not any(mark in block for mark in CORRECTION_MARKS)
    ]


def capability_rows(text: str) -> list[str]:
    return [row for row in blocks(text) if any(f"| {label} |" in row for label in STATUS_LABELS)]


def rows_without_a_code_link(rows: list[str]) -> list[str]:
    return [
        row for row in rows if not any(mark in row for mark in ("`src/", "`frontend/", "| none |"))
    ]


@pytest.fixture(scope="module")
def paper() -> str:
    return PAPER.read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def readme() -> str:
    return README.read_text(encoding="utf-8")


@pytest.mark.parametrize("phrase", FORBIDDEN)
def test_the_readme_does_not_claim_what_the_review_found_false(readme: str, phrase: str) -> None:
    assert phrase.lower() not in readme.lower()


@pytest.mark.parametrize("phrase", FORBIDDEN)
def test_the_manifesto_only_mentions_a_false_claim_to_correct_or_withdraw_it(
    paper: str, phrase: str
) -> None:
    assert uncorrected_mentions(paper, phrase) == []


def test_the_readme_gives_the_honest_label(readme: str) -> None:
    assert PROTOTYPE_LABEL.lower() in " ".join(readme.split()).lower()


def test_the_manifesto_opens_with_vision_not_a_description_of_what_ships(paper: str) -> None:
    assert "**Vision, not a description of what ships.**" in paper.split("\n## ")[0]


def test_the_manifesto_gives_the_honest_label_near_the_top(paper: str) -> None:
    assert PROTOTYPE_LABEL in paper.split("\n## ")[0]


@pytest.mark.parametrize("label", STATUS_LABELS)
def test_the_manifesto_uses_every_status_label(paper: str, label: str) -> None:
    assert f"| {label} |" in paper


@pytest.mark.parametrize("figure", UNSOURCED_FIGURES)
def test_an_unsourced_figure_is_never_stated_without_the_unverified_tag(
    paper: str, figure: str
) -> None:
    mentions = [block for block in blocks(paper) if figure.lower() in block.lower()]

    assert mentions, f"{figure!r} should still be discussed so the reader knows it is unverified"
    assert [block for block in mentions if UNVERIFIED not in block.lower()] == []


def test_every_capability_row_links_to_code_or_says_there_is_none(paper: str) -> None:
    rows = capability_rows(paper)

    assert len(rows) >= 15
    assert rows_without_a_code_link(rows) == []


def test_the_manifesto_lists_real_time_work_only_under_planned(paper: str) -> None:
    row = next(block for block in blocks(paper) if block.startswith("| Real-time compliance"))

    assert "| PLANNED |" in row


def test_the_manifesto_leaves_the_founders_questions_open(paper: str) -> None:
    assert paper.count("Open question") >= 5
