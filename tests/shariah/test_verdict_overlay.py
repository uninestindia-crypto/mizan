"""The older screener screens prefer a company's own filing to the hand-entered sample, and say which they used.

The older endpoints still answer from their own test database of sample rows. A stock the proof service holds a
filing for shows the filing's result instead; every other stock shows the sample, exactly as before.
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from httpx import AsyncClient

from quant_system.shariah.schemas.screening import (
    SAMPLE_DATA_NOTICE,
    SectorRuleResult,
    TransparencyFields,
)
from quant_system.shariah.services.filing_jobs import FilingJobs
from quant_system.shariah.services.proof_runtime import ProofRuntime, use_runtime
from tests.shariah.proof_service_fixtures import (
    FakeBars,
    FakeSample,
    NoReading,
    figures_for,
    make_service,
    make_store,
    tcs_figures,
    three_prices,
)

SCREEN = "/api/v1/stocks/{}/screen"
AUDIT = "/api/v1/stocks/{}/audit"
DETAIL = "/api/v1/stocks/{}"
BIG = three_prices(
    3591.2, 3591.2, 3591.2
)  # a market value near Rs 13 lakh crore: the market-value standard passes


def install(tmp_path: Path, filings: dict[str, Any], bars: FakeBars | None) -> ProofRuntime:
    store = make_store(tmp_path, filings)
    service = make_service(store, FakeSample(), bars)
    runtime = ProofRuntime(service, FilingJobs(store, NoReading, lambda: []))
    use_runtime(runtime)
    return runtime


@pytest.fixture()
def tcs_filing(tmp_path: Path) -> Iterator[ProofRuntime]:
    """TCS, screened from its real filing, with a market value that passes the market-value standard."""
    yield install(tmp_path, {"TCS": tcs_figures()}, FakeBars({"TCS": BIG}))


# ------------------------------------------------------------------------------------- screening


@pytest.mark.asyncio
async def test_a_stock_with_a_filing_is_screened_from_it_and_says_so(
    client: AsyncClient, tcs_filing: ProofRuntime
) -> None:
    body = (await client.get(SCREEN.format("TCS.NS"))).json()
    assert body["verdict_source"] == "filing" and body["data_status"] == "VERIFIED_FILING"
    assert body["as_of"] == "2024-09-30" and body["methodology_version"] == "shariah-screen-v2"
    proof = tcs_filing.service.proof("TCS")
    assert (
        body["data_notice"] == proof["data_notice"] and body["not_covered"] == proof["not_covered"]
    )
    assert body["screened_at"] == proof["screened_at"]


@pytest.mark.asyncio
async def test_the_filings_result_replaces_the_samples_standard_by_standard(
    client: AsyncClient, tcs_filing: ProofRuntime
) -> None:
    body = (await client.get(SCREEN.format("TCS.NS"))).json()
    assert body["aaoifi_evaluation"]["status"] == "COMPLIANT"
    assert body["tasis_evaluation"]["status"] == "NON_COMPLIANT"
    assert body["divergence"] is True and "The two standards disagree" in body["divergence_reason"]
    # the proof's own verdict stands: where the standards disagree it is questionable, not the worse of the two
    assert body["overall_status"] == "QUESTIONABLE"
    receivables = body["tasis_evaluation"]["receivables_ratio"]
    assert (
        receivables["actual_pct"] == pytest.approx(35.9, abs=0.1)
        and receivables["is_compliant"] is False
    )
    assert receivables["note_reference"] == "TradeReceivablesCurrent, TradeReceivablesNoncurrent"
    assert receivables["denominator_label"] == "Book Value of Total Assets"


@pytest.mark.asyncio
async def test_a_stock_without_a_filing_is_screened_from_the_sample_exactly_as_before(
    client: AsyncClient, tcs_filing: ProofRuntime
) -> None:
    body = (await client.get(SCREEN.format("INFY.NS"))).json()
    assert body["verdict_source"] == "sample" and body["data_status"] == "UNVERIFIED_SAMPLE"
    assert body["as_of"] is None and body["data_notice"] == SAMPLE_DATA_NOTICE
    assert body["methodology_version"] == "shariah-screen-v1"


@pytest.mark.asyncio
async def test_a_filing_whose_business_fails_overrules_a_sample_that_passes(
    client: AsyncClient, tmp_path: Path
) -> None:
    brewery = figures_for("INFY", "Infy Brewery Limited")
    install(tmp_path, {"INFY": brewery}, FakeBars({"INFY": BIG}))
    body = (await client.get(SCREEN.format("INFY.NS"))).json()
    assert body["verdict_source"] == "filing" and body["overall_status"] == "NON_COMPLIANT"
    assert body["aaoifi_evaluation"]["status"] == "NON_COMPLIANT"
    assert body["aaoifi_evaluation"]["summary"].startswith("Disqualified: Sector failure")
    assert body["sector_rule"]["rule"] == "alcohol" and body["sector_rule"]["compliant"] is False


@pytest.mark.asyncio
async def test_without_prices_the_market_value_standard_is_questionable_not_a_pass_or_a_fail(
    client: AsyncClient, tmp_path: Path
) -> None:
    install(tmp_path, {"TCS": tcs_figures()}, None)
    body = (await client.get(SCREEN.format("TCS.NS"))).json()
    assert body["aaoifi_evaluation"]["status"] == "QUESTIONABLE"
    assert body["aaoifi_evaluation"]["debt_ratio"]["numerator_label"] == "Needs price history"
    assert body["tasis_evaluation"]["status"] == "NON_COMPLIANT"


# ------------------------------------------------------------------------------------- audit trail


@pytest.mark.asyncio
async def test_the_audit_trail_of_a_filing_lists_each_figure_with_its_filed_field_name(
    client: AsyncClient, tcs_filing: ProofRuntime
) -> None:
    body = (await client.get(AUDIT.format("TCS.NS"))).json()
    balance = {line["line_item"]: line for line in body["balance_sheet_lines"]}
    income = {line["line_item"]: line for line in body["income_statement_lines"]}
    assert balance["Total assets"]["value_inr_cr"] == 161124.0
    assert balance["Total assets"]["note_ref"] == "Assets"
    assert balance["Total assets"]["verification_status"] == "VERIFIED_FILING"
    assert (
        income["Other income"]["value_inr_cr"] == 1691.0
        and income["Other income"]["note_ref"] == "OtherIncome"
    )
    derived = next(line for line in balance.values() if line["note_ref"] is None)
    assert "daily prices" in derived["filing_schedule"]


@pytest.mark.asyncio
async def test_the_audit_names_the_filing_it_came_from(
    client: AsyncClient, tcs_filing: ProofRuntime
) -> None:
    body = (await client.get(AUDIT.format("TCS.NS"))).json()
    filing = tcs_filing.service.proof("TCS")["filing"]
    assert body["source_document"] == filing["source_url"]
    assert (
        body["reporting_period"] == filing["period_label"] and body["filing_date"] == "2024-10-10"
    )
    assert body["audit_notes"] == tcs_filing.service.proof("TCS")["data_notice"]
    assert body["verdict_source"] == "filing" and body["isin"]


@pytest.mark.asyncio
async def test_the_audit_of_a_stock_without_a_filing_is_still_marked_a_sample(
    client: AsyncClient, tcs_filing: ProofRuntime
) -> None:
    body = (await client.get(AUDIT.format("INFY.NS"))).json()
    statuses = {line["verification_status"] for line in body["balance_sheet_lines"]}
    assert statuses == {"UNVERIFIED_SAMPLE"} and body["verdict_source"] == "sample"


# ------------------------------------------------------------------------------------- lists and detail


@pytest.mark.asyncio
async def test_the_list_prefers_the_filing_for_a_stock_that_has_one_and_labels_every_row(
    client: AsyncClient, tcs_filing: ProofRuntime
) -> None:
    items = (await client.get("/api/v1/stocks?limit=100")).json()["items"]
    by_symbol = {item["symbol"]: item for item in items}
    assert (
        by_symbol["TCS"]["verdict_source"] == "filing"
        and by_symbol["TCS"]["tasis_status"] == "NON_COMPLIANT"
    )
    assert (
        by_symbol["TCS"]["aaoifi_status"] == "COMPLIANT"
        and by_symbol["TCS"]["as_of"] == "2024-09-30"
    )
    assert by_symbol["INFY"]["verdict_source"] == "sample" and by_symbol["INFY"]["as_of"] is None
    assert {item["verdict_source"] for item in items} == {"filing", "sample"}
    assert all(
        {"data_status", "as_of", "aaoifi_debt_ratio", "purification_ratio"} <= set(i) for i in items
    )


@pytest.mark.asyncio
async def test_search_prefers_the_filing_too(client: AsyncClient, tcs_filing: ProofRuntime) -> None:
    found = (await client.get("/api/v1/stocks/search?q=tata")).json()
    tcs = next(item for item in found if item["symbol"] == "TCS")
    assert tcs["verdict_source"] == "filing" and tcs["tasis_status"] == "NON_COMPLIANT"
    assert tcs["data_status"] == "VERIFIED_FILING"


@pytest.mark.asyncio
async def test_a_stocks_detail_prefers_the_filing_and_keeps_every_older_field(
    client: AsyncClient, tcs_filing: ProofRuntime
) -> None:
    body = (await client.get(DETAIL.format("TCS.NS"))).json()
    assert body["verdict_source"] == "filing" and body["tasis_status"] == "NON_COMPLIANT"
    assert body["aaoifi_debt_ratio"] == 0.0 and body["tasis_rec_ratio"] == pytest.approx(
        0.359, abs=0.001
    )
    assert {
        "profile",
        "balance_sheet",
        "income_statement",
        "purification_ratio",
        "audit_notes",
    } <= set(body)


@pytest.mark.asyncio
async def test_a_ratio_the_filing_cannot_support_without_prices_is_left_empty_not_zero(
    client: AsyncClient, tmp_path: Path
) -> None:
    install(tmp_path, {"TCS": tcs_figures()}, None)
    body = (await client.get(DETAIL.format("TCS.NS"))).json()
    assert body["aaoifi_debt_ratio"] is None and body["aaoifi_status"] == "QUESTIONABLE"
    assert body["tasis_debt_ratio"] == 0.0  # the total-assets standard needs no prices


# ------------------------------------------------------------------------------------- safety


class BrokenService:
    def filing_proof(self, symbol: str) -> dict[str, Any]:
        raise RuntimeError("the filings store is damaged")


@pytest.mark.asyncio
async def test_if_the_proof_cannot_be_had_the_older_screens_carry_on_with_the_sample(
    client: AsyncClient,
) -> None:
    use_runtime(ProofRuntime(BrokenService(), None))  # type: ignore[arg-type]
    body = (await client.get(SCREEN.format("TCS.NS"))).json()
    assert body["verdict_source"] == "sample" and body["data_status"] == "UNVERIFIED_SAMPLE"
    assert (await client.get("/api/v1/stocks?limit=5")).status_code == 200


def test_the_screening_fields_say_sample_unless_a_filing_was_used() -> None:
    rule = SectorRuleResult(compliant=True)
    fields = TransparencyFields(screened_at="2026-10-07T00:00:00Z", sector_rule=rule)
    assert fields.verdict_source == "sample" and fields.as_of is None
