"""Every verdict says how sure it is, by which rules, as of when, and what it leaves out."""

import re
from datetime import UTC, datetime
from typing import Any

import pytest
from httpx import AsyncClient

from quant_system.shariah.core.methodology import METHODOLOGY_VERSION, NOT_COVERED
from quant_system.shariah.schemas.company import DataStatus
from quant_system.shariah.schemas.screening import SAMPLE_DATA_NOTICE
from quant_system.shariah.services.transparency import build_screening_transparency

SCREEN = "/api/v1/stocks/{}/screen"
AUDIT = "/api/v1/stocks/{}/audit"
ISO_UTC = re.compile(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z")
NOON = datetime(2026, 10, 7, 12, 30, 45, tzinfo=UTC)


@pytest.mark.parametrize("path", [SCREEN, AUDIT])
@pytest.mark.asyncio
async def test_every_verdict_carries_the_data_status_notice_version_and_time(
    client: AsyncClient, path: str
) -> None:
    body = (await client.get(path.format("TCS.NS"))).json()

    assert body["data_status"] == "UNVERIFIED_SAMPLE"
    assert body["data_notice"] == SAMPLE_DATA_NOTICE
    assert body["methodology_version"] == "shariah-screen-v1"
    assert ISO_UTC.fullmatch(body["screened_at"])


@pytest.mark.parametrize("path", [SCREEN, AUDIT])
@pytest.mark.asyncio
async def test_the_time_is_the_time_of_this_screening(client: AsyncClient, path: str) -> None:
    body = (await client.get(path.format("TCS.NS"))).json()

    screened = datetime.strptime(body["screened_at"], "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=UTC)
    assert abs((datetime.now(UTC) - screened).total_seconds()) < 60


@pytest.mark.parametrize("path", [SCREEN, AUDIT])
@pytest.mark.parametrize(
    "phrase",
    ["scholar", "hand-entered", "income line", "not a fatwa"],
)
@pytest.mark.asyncio
async def test_what_the_result_does_not_cover_is_said_in_plain_sentences(
    client: AsyncClient, path: str, phrase: str
) -> None:
    body = (await client.get(path.format("TCS.NS"))).json()

    assert phrase in " ".join(body["not_covered"]).lower()
    assert body["not_covered"] == list(NOT_COVERED)


@pytest.mark.parametrize(
    "pattern",
    [
        r"\bterminal\b",
        r"\bcommand\b",
        r"\bfile\b",
        r"\bJSON\b",
        r"\bAPI\b",
        r"\bbackend\b",
        r"environment",
        "_",
    ],
)
def test_the_list_of_gaps_uses_no_developer_words(pattern: str) -> None:
    assert re.search(pattern, " ".join(NOT_COVERED), re.IGNORECASE) is None


def test_the_methodology_version_is_one_named_constant() -> None:
    assert METHODOLOGY_VERSION == "shariah-screen-v1"


@pytest.mark.parametrize("path", [SCREEN, AUDIT])
@pytest.mark.parametrize(
    ("ticker", "compliant", "rule", "word"),
    [
        ("TCS.NS", True, None, None),
        ("HDFCBANK.NS", False, "interest_based_finance", "financial services"),
        ("HDFCLIFE.NS", False, "interest_based_finance", "financial services"),
        ("UNITDSPR.NS", False, "alcohol", "alcoholic beverages"),
        ("ITC.NS", False, "tobacco", "cigarette"),
        ("DELTACORP.NS", False, "gambling", "casino"),
        ("PVRINOX.NS", False, "cinema", "cinema"),
    ],
)
@pytest.mark.asyncio
async def test_the_sector_test_names_the_rule_and_the_word_that_fired(
    client: AsyncClient, path: str, ticker: str, compliant: bool, rule: str | None, word: str | None
) -> None:
    body = (await client.get(path.format(ticker))).json()

    sector = body["sector_rule"]
    assert (sector["compliant"], sector["rule"], sector["matched_keyword"]) == (
        compliant,
        rule,
        word,
    )


@pytest.mark.asyncio
async def test_a_failed_sector_test_keeps_the_reason_the_verdict_quotes(
    client: AsyncClient,
) -> None:
    body = (await client.get(AUDIT.format("UNITDSPR.NS"))).json()

    assert body["sector_rule"]["reason"] == body["sector_failure_reason"]
    assert body["sector_failure_reason"] in body["aaoifi_evaluation"]["summary"]


@pytest.mark.asyncio
async def test_a_passing_sector_test_has_no_reason(client: AsyncClient) -> None:
    body = (await client.get(SCREEN.format("TCS.NS"))).json()

    assert body["sector_rule"] == {
        "compliant": True,
        "rule": None,
        "matched_keyword": None,
        "reason": None,
    }


@pytest.mark.asyncio
async def test_the_verdicts_themselves_did_not_change(client: AsyncClient) -> None:
    body = (await client.get(SCREEN.format("WARN-BAND.NS"))).json()

    assert body["aaoifi_evaluation"]["status"] == "QUESTIONABLE"
    assert body["aaoifi_evaluation"]["debt_ratio"]["threshold_pct"] == 33.0


def _company(
    sector_compliant: bool, reason: str | None, industry: str, summary: str
) -> dict[str, Any]:
    return {
        "sector": "Industrials",
        "industry": industry,
        "business_summary": summary,
        "sector_compliant": sector_compliant,
        "sector_failure_reason": reason,
    }


@pytest.mark.parametrize(
    ("company", "expected"),
    [
        (
            _company(True, None, "Widgets", "Makes widgets"),
            {"compliant": True, "rule": None, "matched_keyword": None, "reason": None},
        ),
        (
            _company(False, "Stored reason", "Distilleries, Breweries", ""),
            {
                "compliant": False,
                "rule": "alcohol",
                "matched_keyword": "distilleries, breweries",
                "reason": "Stored reason",
            },
        ),
        (
            # The stored verdict says no, but no rule reads the text that way: the verdict stands
            # and no rule is named, because naming one would be a guess.
            _company(False, "Stored reason", "Widgets", "Makes widgets"),
            {"compliant": False, "rule": None, "matched_keyword": None, "reason": "Stored reason"},
        ),
        (
            # The stored verdict says yes although the text would trip a rule: the verdict is what
            # was used, so it is what is reported.
            _company(True, None, "Commercial Bank", ""),
            {"compliant": True, "rule": None, "matched_keyword": None, "reason": None},
        ),
    ],
)
def test_the_sector_rule_reports_the_stored_verdict_and_names_a_rule_only_when_it_agrees(
    company: dict[str, Any], expected: dict[str, Any]
) -> None:
    fields = build_screening_transparency(company, now=NOON)

    assert fields.sector_rule.model_dump() == expected


def test_the_screened_time_is_written_as_utc_to_the_second() -> None:
    fields = build_screening_transparency(_company(True, None, "Widgets", ""), now=NOON)

    assert fields.screened_at == "2026-10-07T12:30:45Z"


def test_today_nothing_can_be_stronger_than_an_unverified_sample() -> None:
    fields = build_screening_transparency(_company(True, None, "Widgets", ""), now=NOON)

    assert fields.data_status is DataStatus.UNVERIFIED_SAMPLE
    assert [status.value for status in DataStatus] == [
        "UNVERIFIED_SAMPLE",
        "VERIFIED_FILING",
        "STALE",
    ]


@pytest.mark.asyncio
async def test_every_row_of_the_stock_list_says_how_far_its_verdict_is_checked(
    client: AsyncClient,
) -> None:
    body = (await client.get("/api/v1/stocks", params={"limit": 50})).json()

    assert body["items"]
    assert {item["data_status"] for item in body["items"]} == {"UNVERIFIED_SAMPLE"}


@pytest.mark.asyncio
async def test_every_search_suggestion_says_how_far_its_verdict_is_checked(
    client: AsyncClient,
) -> None:
    body = (await client.get("/api/v1/stocks/search", params={"q": "tcs"})).json()

    assert body
    assert {item["data_status"] for item in body} == {"UNVERIFIED_SAMPLE"}


@pytest.mark.asyncio
async def test_a_company_detail_says_how_far_its_verdict_is_checked(client: AsyncClient) -> None:
    body = (await client.get("/api/v1/stocks/TCS.NS")).json()

    assert body["data_status"] == "UNVERIFIED_SAMPLE"
