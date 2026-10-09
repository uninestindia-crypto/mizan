"""The proof service over a store of real-shaped filings: the proof, the badge status, the cache and the coverage.

Every price series is a handful of closes whose answer can be checked by hand, every clock is moved by the test,
and nothing here reaches the network.
"""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path
from typing import Any

import pytest

from quant_system.shariah.filings.nse_client import InvalidSymbol
from quant_system.shariah.filings.store import FilingsStore
from quant_system.shariah.services.proof_service import (
    MAX_STATUS_SYMBOLS,
    ProofService,
    TooManySymbols,
)
from tests.shariah.proof_service_fixtures import (
    LATER,
    SAMPLE_ROW,
    TODAY,
    Clock,
    FakeBars,
    FakeSample,
    foodco_figures,
    make_service,
    make_store,
    three_prices,
)

CONTRACT_KEYS = {
    "symbol",
    "company_name",
    "verdict",
    "headline",
    "data_status",
    "data_notice",
    "methodology_version",
    "screened_at",
    "sector",
    "filing",
    "standards",
    "divergence",
    "what_would_change_it",
    "not_covered",
    "sample_comparison",
}
VERDICTS = {"COMPLIANT", "NON_COMPLIANT", "QUESTIONABLE", "NOT_SCREENED"}
DATA_STATUSES = {"VERIFIED_FILING", "STALE", "UNVERIFIED_SAMPLE", "NOT_SCREENED"}
EVERY_SYMBOL = ["TCS", "DRYBREW", "FOODCO", "HDFCBANK", "BROKEN", "SAMPLEONLY", "NOPE"]


def priced() -> FakeBars:
    return FakeBars({"TCS": three_prices(), "FOODCO": three_prices(), "DRYBREW": three_prices()})


def everything(tmp_path: Path, clock: Clock | None = None) -> ProofService:
    sample = FakeSample({"SAMPLEONLY": SAMPLE_ROW})
    return make_service(make_store(tmp_path), sample, priced(), clock)


def standard_tests(proof: dict[str, Any], standard: str) -> dict[str, dict[str, Any]]:
    block = next(s for s in proof["standards"] if s["standard"] == standard)
    return {t["key"]: t for t in block["tests"]}


def status_of(proof: dict[str, Any], standard: str) -> str:
    return str(next(s for s in proof["standards"] if s["standard"] == standard)["status"])


# ------------------------------------------------------------------------------------- from a filing


def test_a_clean_filing_with_prices_is_compliant_on_both_standards(tmp_path: Path) -> None:
    proof = everything(tmp_path).proof("FOODCO")
    assert proof["verdict"] == "COMPLIANT" and proof["data_status"] == "VERIFIED_FILING"
    assert [s["status"] for s in proof["standards"]] == ["COMPLIANT", "COMPLIANT"]
    assert proof["company_name"] == "Food Company Limited"


def test_the_market_value_is_the_platforms_own_prices_times_the_filed_shares(
    tmp_path: Path,
) -> None:
    proof = everything(tmp_path).proof("FOODCO")
    inputs = standard_tests(proof, "AAOIFI")["debt"]["inputs"]
    market = next(i for i in inputs if i["role"] == "derived")
    assert market["value_cr"] == 72400.0  # average close 200 x 3.62 billion shares, in crore
    assert market["label"].startswith("Average close of ₹200.00 from 10 Jan 2022")


def test_total_assets_is_the_book_figure_from_the_filing(tmp_path: Path) -> None:
    proof = everything(tmp_path).proof("FOODCO")
    inputs = standard_tests(proof, "TASIS")["debt"]["inputs"]
    assets = next(i for i in inputs if i["role"] == "denominator")
    assert assets["xbrl_tag"] == "Assets" and assets["value_inr"] == "1611240000000.00"


def test_without_prices_the_market_value_tests_are_not_computed_and_it_says_why(
    tmp_path: Path,
) -> None:
    proof = make_service(make_store(tmp_path), bars=None).proof("FOODCO")
    assert status_of(proof, "AAOIFI") == "NOT_COMPUTED"
    assert status_of(proof, "TASIS") == "COMPLIANT"  # total assets still decides
    assert proof["verdict"] == "QUESTIONABLE"
    assert any("no price history for FOODCO" in line for line in proof["not_covered"])
    assert proof["not_covered"][-1].startswith("This is a screening aid")


def test_a_stock_the_price_data_does_not_know_is_treated_as_having_no_prices(
    tmp_path: Path,
) -> None:
    service = make_service(make_store(tmp_path), bars=FakeBars())
    assert status_of(service.proof("FOODCO"), "AAOIFI") == "NOT_COMPUTED"


def test_a_failing_business_is_not_compliant_whatever_its_figures(tmp_path: Path) -> None:
    proof = everything(tmp_path).proof("DRYBREW")
    assert proof["verdict"] == "NON_COMPLIANT" and proof["data_status"] == "VERIFIED_FILING"
    assert proof["sector"]["rule"] == "alcohol" and proof["sector"]["matched_keyword"] == "brewery"
    assert proof["filing"] is not None and proof["standards"]


def test_the_industry_group_comes_from_the_filings_store(tmp_path: Path) -> None:
    assert everything(tmp_path).proof("TCS")["sector"]["industry_group"] == "Information Technology"


def test_a_company_in_a_sensitive_group_with_no_listed_segment_is_capped_at_questionable(
    tmp_path: Path,
) -> None:
    filings = {"FOODCO": foodco_figures(segments=[])}
    proof = make_service(make_store(tmp_path, filings), bars=priced()).proof("FOODCO")
    assert proof["sector"]["status"] == "NOT_CONFIRMED" and proof["verdict"] == "QUESTIONABLE"


def test_every_filing_figure_has_its_tag_its_value_and_a_filing_block_above_it(
    tmp_path: Path,
) -> None:
    proof = everything(tmp_path).proof("TCS")
    figures = [i for s in proof["standards"] for t in s["tests"] for i in t["inputs"]]
    unproven = [
        i for i in figures if i["role"] != "derived" and not (i["xbrl_tag"] and i["value_inr"])
    ]
    assert figures and unproven == []
    filing = proof["filing"]
    assert len(filing["sha256"]) == 64 and filing["source_url"].startswith(
        "https://nsearchives.nseindia.com/"
    )
    assert filing["period_end"] == "2024-09-30" and filing["filed_on"] == "2024-10-10"
    assert filing["tie_out"]["ok"] is True and filing["tie_out"]["checks"]


# ------------------------------------------------------------------------------------- not from figures


def test_a_bank_is_not_compliant_without_a_balance_sheet_and_the_proof_says_so(
    tmp_path: Path,
) -> None:
    proof = everything(tmp_path).proof("HDFCBANK")
    assert proof["verdict"] == "NON_COMPLIANT" and proof["standards"] == []
    assert proof["sector"]["rule"] == "interest_based_finance" and proof["filing"] is None
    assert (
        proof["data_status"] == "NOT_SCREENED"
    )  # no figures were read, so no figure-backed label is earned
    assert "did not read this company's balance sheet" in proof["data_notice"]
    assert "layout QuantOS does not read" in proof["data_notice"]
    assert any("financial tests were not run" in line for line in proof["not_covered"])


def test_a_filing_that_does_not_agree_with_itself_is_not_used_and_the_proof_says_why(
    tmp_path: Path,
) -> None:
    proof = everything(tmp_path).proof("BROKEN")
    assert (
        proof["verdict"] == "NOT_SCREENED" and proof["standards"] == [] and proof["filing"] is None
    )
    assert "does not agree with itself on: Assets add up" in proof["headline"]


def test_a_filing_that_does_not_agree_with_itself_leaves_the_sample_to_decide(
    tmp_path: Path,
) -> None:
    row = {**SAMPLE_ROW, "symbol": "BROKEN", "company_name": "Broken Systems Limited"}
    service = make_service(make_store(tmp_path), FakeSample({"BROKEN": row}), priced())
    proof = service.proof("BROKEN")
    assert proof["data_status"] == "UNVERIFIED_SAMPLE" and proof["filing"] is None
    assert any("does not agree with itself" in line for line in proof["not_covered"])


def test_a_stock_with_neither_filing_nor_sample_is_not_screened_and_never_compliant(
    tmp_path: Path,
) -> None:
    proof = everything(tmp_path).proof("NOPE")
    assert proof["verdict"] == "NOT_SCREENED" and proof["data_status"] == "NOT_SCREENED"
    assert proof["standards"] == [] and proof["filing"] is None
    assert "compliant" not in proof["headline"].lower().replace("not compliant", "")
    assert not any("hand-entered sample" in line for line in proof["not_covered"])


def test_a_stock_only_in_the_hand_entered_sample_is_screened_from_it_and_labelled_so(
    tmp_path: Path,
) -> None:
    proof = everything(tmp_path).proof("SAMPLEONLY")
    assert proof["data_status"] == "UNVERIFIED_SAMPLE" and proof["filing"] is None
    assert proof["verdict"] == "COMPLIANT" and "sample" in proof["data_notice"].lower()
    figures = [i for s in proof["standards"] for t in s["tests"] for i in t["inputs"]]
    assert figures and all(i["xbrl_tag"] is None for i in figures)


def test_a_filing_that_disagrees_with_the_sample_wins_and_says_so(tmp_path: Path) -> None:
    row = {**SAMPLE_ROW, "symbol": "TCS", "company_name": "Tata Consultancy Services Limited"}
    row["total_debt"] = 7970.0
    proof = make_service(make_store(tmp_path), FakeSample({"TCS": row}), priced()).proof("TCS")
    assert proof["data_status"] == "VERIFIED_FILING"
    assert proof["sample_comparison"]["differs"] is True
    assert "7,970" in proof["sample_comparison"]["note"]


def test_a_sample_that_fails_the_business_test_still_fails_a_stock_whose_filing_passes_it(
    tmp_path: Path,
) -> None:
    row = {**SAMPLE_ROW, "symbol": "TCS", "sector": "Tobacco", "industry": "Cigarettes, Tobacco"}
    row.update(sector_compliant=0, sector_failure_reason="Tobacco")
    proof = make_service(make_store(tmp_path), FakeSample({"TCS": row}), priced()).proof("TCS")
    assert proof["verdict"] == "NON_COMPLIANT" and proof["sector"]["status"] == "FAIL"


def test_with_no_bundled_filings_at_all_the_proof_says_there_are_none_yet(tmp_path: Path) -> None:
    store = FilingsStore(tmp_path / "missing.json.gz", tmp_path / "user.sqlite")
    proof = make_service(store).proof("TCS")
    assert proof["verdict"] == "NOT_SCREENED"
    assert any("no bundled company filings yet" in line for line in proof["not_covered"])


# ------------------------------------------------------------------------------------- freshness


@pytest.mark.parametrize(("moment", "expected"), [(TODAY, "VERIFIED_FILING"), (LATER, "STALE")])
def test_a_filing_older_than_eighteen_months_is_stale_by_the_clock(
    tmp_path: Path, moment: Any, expected: str
) -> None:
    proof = everything(tmp_path, Clock(moment)).proof("TCS")
    assert proof["data_status"] == expected and proof["filing"]["period_end"] == "2024-09-30"


def test_the_proof_is_stamped_with_the_clocks_time_in_utc(tmp_path: Path) -> None:
    assert everything(tmp_path).proof("TCS")["screened_at"] == "2025-01-07T12:00:00Z"


# ------------------------------------------------------------------------------------- the contract


@pytest.mark.parametrize("symbol", EVERY_SYMBOL)
def test_every_proof_has_the_contracts_fields_and_is_plain_data(
    tmp_path: Path, symbol: str
) -> None:
    proof = everything(tmp_path).proof(symbol)
    assert CONTRACT_KEYS <= set(proof)
    assert proof["verdict"] in VERDICTS and proof["data_status"] in DATA_STATUSES
    assert proof["methodology_version"] == "shariah-screen-v2"
    assert json.loads(json.dumps(proof)) == proof
    assert proof["not_covered"][0] == "No scholar has reviewed these rules or this result."


@pytest.mark.parametrize("symbol", EVERY_SYMBOL)
def test_no_proof_says_certified_approved_or_guaranteed(tmp_path: Path, symbol: str) -> None:
    text = json.dumps(everything(tmp_path).proof(symbol)).lower()
    assert not {"certified", "approved", "guaranteed"} & set(text.replace(",", " ").split())


def test_a_symbol_that_is_not_an_nse_symbol_is_refused(tmp_path: Path) -> None:
    with pytest.raises(InvalidSymbol):
        everything(tmp_path).proof("not a symbol")


def test_a_lower_case_symbol_with_an_exchange_suffix_finds_the_same_stock(tmp_path: Path) -> None:
    service = everything(tmp_path)
    assert service.proof("tcs.ns")["symbol"] == "TCS"
    assert service.proof("tcs.ns")["verdict"] == service.proof("TCS")["verdict"]


# ------------------------------------------------------------------------------------- statuses


@pytest.mark.parametrize("symbol", EVERY_SYMBOL)
def test_the_status_of_a_stock_never_disagrees_with_its_proof(tmp_path: Path, symbol: str) -> None:
    service = everything(tmp_path)
    proof, row = service.proof(symbol), service.statuses([symbol])[symbol]
    assert (row["verdict"], row["data_status"]) == (proof["verdict"], proof["data_status"])
    assert row["as_of"] == (proof["filing"] or {}).get("period_end")
    assert 0 < len(row["short"]) < 90


def test_one_call_answers_for_many_stocks_with_the_same_verdicts_as_their_proofs(
    tmp_path: Path,
) -> None:
    service = everything(tmp_path)
    rows = service.statuses(EVERY_SYMBOL)
    assert list(rows) == EVERY_SYMBOL
    assert {s: r["verdict"] for s, r in rows.items()} == {
        "TCS": service.proof("TCS")["verdict"],
        "DRYBREW": "NON_COMPLIANT",
        "FOODCO": "COMPLIANT",
        "HDFCBANK": "NON_COMPLIANT",
        "BROKEN": "NOT_SCREENED",
        "SAMPLEONLY": "COMPLIANT",
        "NOPE": "NOT_SCREENED",
    }


def test_a_stock_nothing_is_known_about_is_not_screened_and_never_a_pass(tmp_path: Path) -> None:
    row = everything(tmp_path).statuses(["NOPE"])["NOPE"]
    assert row == {
        "verdict": "NOT_SCREENED",
        "data_status": "NOT_SCREENED",
        "short": "Not screened yet.",
        "as_of": None,
    }


def test_a_bad_symbol_in_the_list_is_marked_not_screened_and_the_others_still_answer(
    tmp_path: Path,
) -> None:
    rows = everything(tmp_path).statuses(["TCS", "not a symbol", "tcs.ns"])
    assert list(rows) == ["TCS", "NOT A SYMBOL", "TCS.NS"]
    assert rows["NOT A SYMBOL"]["short"] == "Not a valid stock symbol."
    assert rows["TCS.NS"] == rows["TCS"]


def test_the_short_reason_names_the_business_the_limit_or_the_missing_piece(tmp_path: Path) -> None:
    service = everything(tmp_path)
    rows = service.statuses(["DRYBREW", "HDFCBANK", "TCS", "FOODCO"])
    assert rows["DRYBREW"]["short"] == "Its business is ruled out: alcohol."
    assert rows["HDFCBANK"]["short"] == "Its business is ruled out: interest-based finance."
    assert rows["TCS"]["short"] == "Receivables are over the 33% limit against market value."
    assert rows["FOODCO"]["short"] == "Passes the business test and both standards."


def test_two_hundred_stocks_are_answered_in_one_call_and_two_hundred_and_one_are_refused(
    tmp_path: Path,
) -> None:
    service = everything(tmp_path)
    assert len(service.statuses([f"S{n}" for n in range(MAX_STATUS_SYMBOLS)])) == MAX_STATUS_SYMBOLS
    with pytest.raises(TooManySymbols):
        service.statuses([f"S{n}" for n in range(MAX_STATUS_SYMBOLS + 1)])


# ------------------------------------------------------------------------------------- the cache


def test_a_list_of_badges_does_not_work_every_proof_out_again(tmp_path: Path) -> None:
    bars = priced()
    service = make_service(make_store(tmp_path), bars=bars)
    service.statuses(["FOODCO", "TCS"])
    first = len(bars.calls)
    service.statuses(["FOODCO", "TCS"])
    service.proof("FOODCO")
    assert first == 2 and len(bars.calls) == first


def test_a_newer_filing_for_a_stock_gives_a_new_proof(tmp_path: Path) -> None:
    bars = priced()
    store = make_store(tmp_path)
    service = make_service(store, bars=bars)
    assert service.proof("FOODCO")["filing"]["period_end"] == "2024-09-30"
    newer = foodco_figures(
        period_end=date(2024, 12, 31), ytd_start=date(2024, 4, 1), quarter_start=date(2024, 10, 1)
    )
    assert store.put(newer) is True
    assert service.proof("FOODCO")["filing"]["period_end"] == "2024-12-31"
    assert len(bars.calls) == 2


def test_prices_loaded_after_a_proof_was_worked_out_are_used_the_next_time_it_is_asked_for(
    tmp_path: Path,
) -> None:
    bars = FakeBars()
    service = make_service(make_store(tmp_path), bars=bars)
    assert status_of(service.proof("FOODCO"), "AAOIFI") == "NOT_COMPUTED"
    bars.series["FOODCO"], bars.build = three_prices(), "after the download"
    assert status_of(service.proof("FOODCO"), "AAOIFI") == "COMPLIANT"


def test_the_next_day_the_proof_is_worked_out_again(tmp_path: Path) -> None:
    bars, clock = priced(), Clock()
    service = make_service(make_store(tmp_path), bars=bars, clock=clock)
    service.proof("FOODCO")
    clock.advance(1)
    service.proof("FOODCO")
    assert len(bars.calls) == 2


def test_changing_a_returned_proof_does_not_change_the_next_one(tmp_path: Path) -> None:
    service = everything(tmp_path)
    service.proof("TCS")["verdict"] = "COMPLIANT"
    service.proof("TCS")["standards"].clear()
    again = service.proof("TCS")
    assert again["verdict"] != "COMPLIANT" and again["standards"]


def test_a_stock_with_a_filing_has_a_filing_proof_and_others_do_not(tmp_path: Path) -> None:
    service = everything(tmp_path)
    assert service.filing_proof("FOODCO") is not None
    assert service.filing_proof("HDFCBANK") is None  # a bank's layout is not read
    assert service.filing_proof("SAMPLEONLY") is None  # the sample is not a filing
    assert service.filing_proof("NOPE") is None


# ------------------------------------------------------------------------------------- coverage


def test_coverage_counts_only_the_filings_that_read_cleanly(tmp_path: Path) -> None:
    coverage = everything(tmp_path).coverage()
    assert (
        coverage["screened"] == 3
    )  # TCS, DRYBREW and FOODCO; the bank and the broken filing are not counted
    assert coverage["newest_filing"] == "2024-09-30"
    assert coverage["snapshot_built_on"] == "2026-10-07" and coverage["note"] is None


def test_coverage_counts_what_nse_lists_from_the_bundled_list(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    listed = tmp_path / "app" / "data" / "authorities"
    listed.mkdir(parents=True)
    (listed / "nse-all-listed-equities.csv").write_text(
        "Symbol,Company Name\nAAA,A\nBBB,B\nCCC,C\n"
    )
    monkeypatch.setenv("QUANTOS_APP_ROOT", str(tmp_path / "app"))
    assert everything(tmp_path).coverage()["total_listed"] == 3


def test_coverage_with_no_snapshot_says_there_are_no_bundled_filings_yet(tmp_path: Path) -> None:
    service = make_service(FilingsStore(tmp_path / "missing.json.gz", tmp_path / "user.sqlite"))
    coverage = service.coverage()
    assert coverage["screened"] == 0 and coverage["snapshot_built_on"] is None
    assert "no bundled company filings yet" in coverage["note"]
