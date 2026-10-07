"""The proof for one stock: which test passed or failed, on what figures, from which filing, and how sure it is."""

from __future__ import annotations

from dataclasses import replace
from typing import Any

import pytest

from quant_system.shariah.services.proof_builder import build_stock_proof
from quant_system.shariah.services.proof_words import indian_grouping
from tests.shariah.proof_fixtures import (
    clean_figures,
    failing_activity,
    figures,
    market_value,
    tcs,
    unconfirmed_activity,
)

SAMPLE_ROW: dict[str, Any] = {
    "ticker": "TCS.NS",
    "symbol": "TCS",
    "company_name": "Tata Consultancy Services Limited",
    "sector": "Information Technology",
    "industry": "Software",
    "business_summary": "software services",
    "sector_compliant": 1,
    "sector_failure_reason": None,
    "total_assets": 1000.0,
    "total_debt": 7970.0,
    "total_cash_and_investments": 100.0,
    "total_receivables": 120.0,
    "avg_36m_market_cap": 4000.0,
    "total_impermissible_income": 1.0,
    "total_revenue": 500.0,
}


def _tests(proof: dict[str, Any], standard: str) -> dict[str, dict[str, Any]]:
    block = next(s for s in proof["standards"] if s["standard"] == standard)
    return {t["key"]: t for t in block["tests"]}


def _status(proof: dict[str, Any], standard: str) -> str:
    return str(next(s for s in proof["standards"] if s["standard"] == standard)["status"])


# ------------------------------------------------------------------------------------- real TCS figures


def test_the_real_tcs_filing_passes_the_market_value_standard() -> None:
    proof = build_stock_proof(tcs())
    assert _status(proof, "AAOIFI") == "COMPLIANT"
    tests = _tests(proof, "AAOIFI")
    assert {t["result"] for t in tests.values()} == {"PASS"}
    assert tests["debt"]["high"]["pct"] == 0.0
    assert tests["receivables"]["high"]["pct"] == pytest.approx(4.45, abs=0.01)


def test_the_same_filing_fails_the_receivables_test_against_total_assets() -> None:
    proof = build_stock_proof(tcs())
    assert _status(proof, "TASIS") == "NON_COMPLIANT"
    receivables = _tests(proof, "TASIS")["receivables"]
    assert receivables["result"] == "FAIL"
    assert receivables["high"]["pct"] == pytest.approx(35.91, abs=0.01)
    assert receivables["limit_pct"] == 33.0
    assert receivables["high"]["numerator_cr"] == pytest.approx(57_858.0)
    assert receivables["high"]["denominator_cr"] == pytest.approx(161_124.0)
    assert "over the 33% limit" in receivables["plain"]


def test_the_two_standards_disagreeing_makes_the_verdict_questionable_and_says_why() -> None:
    proof = build_stock_proof(tcs())
    assert proof["verdict"] == "QUESTIONABLE"
    assert proof["divergence"]["noted"] is True
    assert "receivables" in proof["divergence"]["explanation"].lower()
    assert "total assets" in proof["divergence"]["explanation"].lower()


def test_cash_and_securities_are_bracketed_because_the_filing_does_not_split_them() -> None:
    cash = _tests(build_stock_proof(tcs()), "TASIS")["cash"]
    assert cash["low"]["pct"] == pytest.approx(10.39, abs=0.01)
    assert cash["high"]["pct"] == pytest.approx(32.78, abs=0.01)
    assert cash["result"] == "BORDERLINE"
    assert {i["role"] for i in cash["inputs"]} == {"numerator", "denominator"}
    assert [i["counted_in"] for i in cash["inputs"] if i["xbrl_tag"] == "CurrentInvestments"] == [
        "upper_only"
    ]


def test_interest_income_is_bracketed_between_the_itemised_figure_and_all_other_income() -> None:
    income = _tests(build_stock_proof(tcs()), "TASIS")["impermissible"]
    assert income["low"]["pct"] == pytest.approx(1.23, abs=0.01)
    assert income["high"]["pct"] == pytest.approx(1.32, abs=0.01)
    assert income["result"] == "PASS"


def test_when_the_filing_does_not_itemise_interest_the_lower_bound_is_zero_and_it_says_so() -> None:
    proof = build_stock_proof(tcs(figures=figures(interest_income_adjustment=None)))
    income = _tests(proof, "TASIS")["impermissible"]
    assert income["low"]["pct"] == 0.0 and income["high"]["pct"] == pytest.approx(1.32, abs=0.01)
    assert any("not itemised" in sentence.lower() for sentence in proof["not_covered"])


def test_every_filing_input_carries_its_tag_its_rupee_value_and_a_label() -> None:
    proof = build_stock_proof(tcs())
    inputs = [i for s in proof["standards"] for t in s["tests"] for i in t["inputs"]]
    filed = [i for i in inputs if i["role"] != "derived"]
    assert filed and all(i["xbrl_tag"] and i["value_inr"] and i["label"] for i in filed)
    assert any(i["xbrl_tag"] == "Assets" and i["value_inr"] == "1611240000000" for i in filed)


def test_the_market_value_is_shown_as_derived_with_how_it_was_worked_out() -> None:
    debt = _tests(build_stock_proof(tcs()), "AAOIFI")["debt"]
    derived = [i for i in debt["inputs"] if i["role"] == "derived"]
    assert len(derived) == 1 and derived[0]["xbrl_tag"] is None
    assert "Average close" in derived[0]["label"]


def test_the_filing_is_named_with_its_proof() -> None:
    filing = build_stock_proof(tcs())["filing"]
    assert filing["period_label"] == "Six months ended 30 Sep 2024"
    assert filing["filed_on"] == "2024-10-10" and filing["consolidated"] is True
    assert filing["sha256"] == "ab" * 32 and filing["source_url"].startswith(
        "https://nsearchives.nseindia.com/"
    )
    assert filing["tie_out"]["ok"] is True and filing["tie_out"]["checks"][0]["ok"] is True


def test_the_header_fields_are_present() -> None:
    proof = build_stock_proof(tcs())
    assert proof["symbol"] == "TCS" and proof["company_name"].startswith("Tata Consultancy")
    assert (
        proof["data_status"] == "VERIFIED_FILING"
        and proof["methodology_version"] == "shariah-screen-v2"
    )
    assert proof["screened_at"] == "2026-10-07T06:00:00Z"
    assert "fatwa" in " ".join(proof["not_covered"]).lower()


# ------------------------------------------------------------------------------------- verdict rules


def test_a_company_that_passes_everything_is_compliant_and_says_what_it_rests_on() -> None:
    proof = build_stock_proof(tcs(figures=clean_figures()))
    assert [s["status"] for s in proof["standards"]] == ["COMPLIANT", "COMPLIANT"]
    assert proof["verdict"] == "COMPLIANT"
    assert "both standards" in proof["headline"].lower()
    assert "30 sep 2024" in proof["headline"].lower()


def test_a_prohibited_business_is_not_compliant_whatever_its_figures() -> None:
    proof = build_stock_proof(tcs(figures=clean_figures(), activity=failing_activity()))
    assert proof["verdict"] == "NON_COMPLIANT"
    assert proof["sector"]["status"] == "FAIL" and proof["sector"]["matched_keyword"] == "brewery"
    assert "business" in proof["headline"].lower() and "brewer" in proof["headline"].lower()


def test_a_business_that_could_not_be_confirmed_caps_the_verdict_at_questionable() -> None:
    proof = build_stock_proof(tcs(figures=clean_figures(), activity=unconfirmed_activity()))
    assert proof["verdict"] == "QUESTIONABLE"
    assert proof["sector"]["status"] == "NOT_CONFIRMED" and proof["sector"]["compliant"] is None
    assert (
        "cannot tell" in proof["headline"].lower() or "not confirmed" in proof["headline"].lower()
    )


def test_a_figure_that_decides_the_result_either_way_makes_it_questionable_not_a_guess() -> None:
    proof = build_stock_proof(
        tcs(
            figures=figures(
                total_assets=100_000_000_000,
                cash_and_equivalents=20_000_000_000,
                other_bank_balances=0,
                current_investments=20_000_000_000,
                noncurrent_investments=0,
                trade_receivables_current=1_000_000_000,
                trade_receivables_noncurrent=0,
            )
        )
    )
    cash = _tests(proof, "TASIS")["cash"]
    assert cash["result"] == "DEPENDS"
    assert "does not break" in cash["plain"] and "cannot say which side" in cash["plain"]
    assert _status(proof, "TASIS") == "QUESTIONABLE" and proof["verdict"] == "QUESTIONABLE"


def test_debt_over_the_limit_on_both_standards_is_not_compliant() -> None:
    proof = build_stock_proof(
        tcs(figures=figures(borrowings_noncurrent=900_000_000_000), market_value=market_value(1000))
    )
    assert [s["status"] for s in proof["standards"]] == ["NON_COMPLIANT", "NON_COMPLIANT"]
    assert proof["verdict"] == "NON_COMPLIANT"
    assert "debt" in proof["headline"].lower()


def test_without_price_history_the_market_value_standard_is_not_computed_and_says_why() -> None:
    proof = build_stock_proof(tcs(figures=clean_figures(), market_value=None))
    assert _status(proof, "AAOIFI") == "NOT_COMPUTED"
    tests = _tests(proof, "AAOIFI")
    assert tests["debt"]["result"] == "NOT_COMPUTED" and "price history" in tests["debt"]["plain"]
    assert tests["impermissible"]["result"] == "PASS"
    assert proof["verdict"] == "QUESTIONABLE"


def test_a_stale_filing_keeps_its_verdict_but_says_it_is_old() -> None:
    proof = build_stock_proof(tcs(data_status="STALE"))
    assert proof["data_status"] == "STALE"
    assert "old" in proof["data_notice"].lower()


# ------------------------------------------------------------------------------------- what would change it


def test_it_says_how_far_a_failing_figure_is_from_its_limit_in_rupees() -> None:
    sentences = build_stock_proof(tcs())["what_would_change_it"]
    assert 1 <= len(sentences) <= 3
    assert any("crore" in s and "receivables" in s.lower() for s in sentences)


# ------------------------------------------------------------------------------------- sample and not screened


def test_with_no_filing_the_old_sample_row_is_used_and_labelled_as_a_sample() -> None:
    proof = build_stock_proof(
        tcs(
            filing=None,
            figures={},
            market_value=None,
            data_status="UNVERIFIED_SAMPLE",
            sample=SAMPLE_ROW,
        )
    )
    assert proof["data_status"] == "UNVERIFIED_SAMPLE" and proof["filing"] is None
    assert "sample" in proof["data_notice"].lower()
    inputs = [i for s in proof["standards"] for t in s["tests"] for i in t["inputs"]]
    assert inputs and all(i["xbrl_tag"] is None for i in inputs)
    assert _tests(proof, "TASIS")["debt"]["result"] == "FAIL"  # 7,970 against 1,000 of assets
    assert proof["verdict"] == "NON_COMPLIANT"


def test_with_nothing_at_all_the_stock_is_not_screened_and_never_called_compliant() -> None:
    proof = build_stock_proof(
        tcs(filing=None, figures={}, market_value=None, data_status="NOT_SCREENED")
    )
    assert proof["verdict"] == "NOT_SCREENED" and proof["standards"] == []
    assert proof["data_status"] == "NOT_SCREENED"
    assert "not screened" in proof["headline"].lower()
    assert "compliant" not in proof["headline"].lower().replace("not compliant", "")


def test_a_filing_that_disagrees_with_the_old_sample_says_so_in_plain_words() -> None:
    proof = build_stock_proof(tcs(sample=SAMPLE_ROW))
    comparison = proof["sample_comparison"]
    assert comparison["differs"] is True
    assert "7,970" in comparison["note"] and "filing" in comparison["note"].lower()


def test_no_comparison_is_made_when_there_is_no_sample() -> None:
    assert build_stock_proof(tcs())["sample_comparison"] == {"differs": False, "note": None}


# ------------------------------------------------------------------------------------- words


@pytest.mark.parametrize(
    ("value", "text"),
    [
        (0, "0"),
        (7, "7"),
        (999, "999"),
        (1000, "1,000"),
        (16124, "16,124"),
        (161124, "1,61,124"),
        (1300000, "13,00,000"),
    ],
)
def test_rupee_amounts_are_grouped_the_indian_way(value: int, text: str) -> None:
    assert indian_grouping(value) == text


def test_the_lender_of_last_resort_never_breaks_on_a_missing_borrowing_line() -> None:
    proof = build_stock_proof(
        tcs(figures=figures(borrowings_noncurrent=None, borrowings_current=None))
    )
    assert _tests(proof, "TASIS")["debt"]["high"]["pct"] == 0.0


def test_the_proof_is_plain_data_that_can_be_sent_as_json() -> None:
    import json

    proof = build_stock_proof(replace(tcs(), sample=SAMPLE_ROW))
    assert json.loads(json.dumps(proof)) == proof
