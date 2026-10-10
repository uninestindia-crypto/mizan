"""The Copilot's halal screening tool uses the Shariah engine's proof from the company's own filing when it has one.

The proofs are real ones, worked out by the engine from the real TCS filing and small filings built to a case; the
tool only shapes them. Where the engine cannot answer, the tool falls back to the hand-entered sample as before.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

import pytest

from quant_system.copilot.rules import render_halal, verdict_word
from quant_system.copilot.sources import ProofBackedShariahSource
from quant_system.copilot.tools import default_registry
from tests.copilot_fakes import FakeShariah, make_context
from tests.shariah.proof_service_fixtures import (
    FakeBars,
    FakeSample,
    make_service,
    make_store,
    three_prices,
)

BIG = three_prices(3591.2, 3591.2, 3591.2)  # a market value near Rs 13 lakh crore
STRADDLE = three_prices(
    165.75, 165.75, 165.75
)  # Rs 60,000 crore: cash is under its limit at one reading, over it at the other
FORBIDDEN_WORDS = re.compile(r"\b(certified|approved|guaranteed|guarantee)\b", re.IGNORECASE)


class ProofSource(FakeShariah):
    """The sample plus the engine's proof, as the app wires them together."""

    def __init__(self, proofs: Any) -> None:
        self._proofs = proofs

    def proof(self, symbol: str) -> dict[str, Any]:
        return dict(self._proofs.proof(symbol))


def check(tmp_path: Path, symbol: str, prices: Any = BIG) -> Any:
    service = make_service(
        make_store(tmp_path), FakeSample(), FakeBars(dict.fromkeys(("TCS", "FOODCO"), prices))
    )
    registry = default_registry(make_context(shariah=ProofSource(service)))
    return registry.call("shariah_check", {"symbol": symbol})


# ------------------------------------------------------------------------------------- from a filing


def test_a_stock_with_a_filing_is_answered_from_the_engines_proof(tmp_path: Path) -> None:
    result = check(tmp_path, "TCS")
    data = result.data
    assert result.ok and data["covered"] is True and data["verdict_source"] == "filing"
    assert data["verdict"] == "QUESTIONABLE" and data["data_status"] == "VERIFIED_FILING"
    assert data["headline"].startswith("Tata Consultancy Services Limited is questionable.")
    assert data["standards_disagree"] is True
    assert data["company"] == "Tata Consultancy Services Limited"


def test_the_summary_and_the_block_say_the_result_is_from_the_companys_own_filing_and_when_it_was_filed(
    tmp_path: Path,
) -> None:
    result = check(tmp_path, "TCS")
    line = "Screened from the company's own filing, filed 2024-10-10"
    assert line in result.summary and result.data["source_line"] == line
    assert line in render_halal(result.data)


def test_the_tool_carries_the_ratios_against_their_limits_by_standard(tmp_path: Path) -> None:
    standards = {s["standard"]: s for s in check(tmp_path, "TCS").data["standards"]}
    assert (
        standards["AAOIFI"]["status"] == "COMPLIANT"
        and standards["TASIS"]["status"] == "NON_COMPLIANT"
    )
    receivables = next(r for r in standards["TASIS"]["ratios"] if "Receivables" in r["name"])
    assert receivables["actual_pct"] == pytest.approx(35.9, abs=0.1)
    assert receivables["threshold_pct"] == 33.0 and receivables["within_limit"] is False
    assert receivables["headroom_pct"] < 0


def test_the_tool_carries_the_filing_period_and_link_and_what_the_result_leaves_out(
    tmp_path: Path,
) -> None:
    data = check(tmp_path, "TCS").data
    assert data["filing"]["period_label"] == "Six months ended 30 Sep 2024"
    assert data["filing"]["source_url"].startswith("https://nsearchives.nseindia.com/")
    assert data["provenance"]["filing_date"] == "2024-10-10"
    assert data["not_covered"][0] == "No scholar has reviewed these rules or this result."
    assert any("buybacks" in line for line in data["not_covered"])
    assert "screening aid" in data["disclaimer"].lower() and data["what_would_change_it"]


def test_the_links_in_the_result_are_only_the_filings_own_so_a_reply_may_repeat_them(
    tmp_path: Path,
) -> None:
    from quant_system.copilot.finalise import links_in

    links = links_in(check(tmp_path, "TCS").data)
    assert links and all(link.startswith("https://nsearchives.nseindia.com/") for link in links)


def test_the_result_is_small_enough_to_reach_a_model_whole(tmp_path: Path) -> None:
    text = check(tmp_path, "TCS").for_prompt(6000)
    assert len(json.dumps(check(tmp_path, "TCS").data, default=str)) < 6000 and json.loads(text)


@pytest.mark.parametrize("symbol", ["TCS", "FOODCO", "DRYBREW", "HDFCBANK", "NOPE", "BROKEN"])
def test_nothing_the_tool_says_calls_a_stock_certified_approved_or_guaranteed(
    tmp_path: Path, symbol: str
) -> None:
    result = check(tmp_path, symbol)
    shown = " ".join(
        [result.summary, json.dumps(result.data, default=str), render_halal(result.data)]
    )
    assert FORBIDDEN_WORDS.search(shown) is None


def test_a_clean_company_is_compliant_and_the_block_leads_with_that(tmp_path: Path) -> None:
    result = check(tmp_path, "FOODCO")
    block = render_halal(result.data)
    assert result.data["verdict"] == "COMPLIANT" and verdict_word(result.data) == "compliant"
    assert block.index("**Result: Compliant.**") < block.index("**AAOIFI: Compliant**")


def test_a_figure_the_filing_does_not_break_down_is_shown_as_a_range_not_a_guess(
    tmp_path: Path,
) -> None:
    block = render_halal(check(tmp_path, "TCS", STRADDLE).data)
    assert re.search(
        r"Cash and securities compared with market value: between 27\.9% and 88\.0% \(limit 33%\)",
        block,
    )


def test_without_prices_the_market_value_standard_is_said_to_be_not_worked_out(
    tmp_path: Path,
) -> None:
    service = make_service(make_store(tmp_path), FakeSample(), None)
    registry = default_registry(make_context(shariah=ProofSource(service)))
    data = registry.call("shariah_check", {"symbol": "FOODCO"}).data
    block = render_halal(data)
    assert data["verdict"] == "QUESTIONABLE" and verdict_word(data) == "questionable"
    assert "AAOIFI: Not worked out (it needs the stock's price history)" in block


def test_the_block_names_the_filing_so_a_person_can_open_it_and_ends_with_the_disclaimer(
    tmp_path: Path,
) -> None:
    block = render_halal(check(tmp_path, "TCS").data)
    assert "Open the filing to check it: https://nsearchives.nseindia.com/" in block
    assert block.endswith("Please ask a qualified scholar before you decide.")
    assert "illustrative sample" not in block and "What this does not cover:" in block


# ------------------------------------------------------------------------------------- not from figures


def test_a_bank_is_not_compliant_on_its_business_and_the_tool_says_no_balance_sheet_was_read(
    tmp_path: Path,
) -> None:
    result = check(tmp_path, "HDFCBANK")
    data = result.data
    assert (
        data["covered"] is True and data["verdict_source"] == "business" and data["standards"] == []
    )
    assert data["verdict"] == "NON_COMPLIANT" and data["sector_compliant"] is False
    assert "balance sheet was not read" in result.summary
    assert "Business activity:** not allowed" in render_halal(data)
    assert verdict_word(data) == "not compliant"


def test_a_stock_nothing_is_known_about_is_not_screened_never_compliant(tmp_path: Path) -> None:
    result = check(tmp_path, "NOPE")
    assert (
        result.ok and result.data["covered"] is False and result.data["verdict"] == "NOT_SCREENED"
    )
    assert result.data["message"].startswith("NOPE is not screened yet.")
    assert (
        verdict_word(result.data) == "not screened"
        and render_halal(result.data) == result.data["message"]
    )


# ------------------------------------------------------------------------------------- falling back


class SampleProof:
    """A proof that rests on the hand-entered sample is not a filing: the tool answers as it always did."""

    def company(self, symbol: str) -> dict[str, Any] | None:
        return FakeShariah().company(symbol)

    def company_count(self) -> int:
        return 39

    def proof(self, symbol: str) -> dict[str, Any]:
        return {"data_status": "UNVERIFIED_SAMPLE", "verdict": "COMPLIANT"}


class BrokenProof(SampleProof):
    def proof(self, symbol: str) -> dict[str, Any]:
        raise RuntimeError("the filings store is damaged")


@pytest.mark.parametrize("source", [SampleProof(), BrokenProof(), FakeShariah()])
def test_when_the_engine_has_no_filing_or_cannot_answer_the_sample_answers_as_before(
    source: Any,
) -> None:
    result = default_registry(make_context(shariah=source)).call("shariah_check", {"symbol": "AAA"})
    assert result.ok and result.data["data_status"] == "UNVERIFIED_SAMPLE"
    assert "verdict_source" not in result.data and "illustrative sample" in render_halal(
        result.data
    )


def test_a_failure_of_the_engine_does_not_leak_into_what_the_tool_says() -> None:
    result = default_registry(make_context(shariah=BrokenProof())).call(
        "shariah_check", {"symbol": "AAA"}
    )
    assert "damaged" not in json.dumps(result.data, default=str) + result.summary


def test_the_proof_backed_source_passes_the_sample_through_and_adds_the_proof() -> None:
    asked: list[str] = []

    def proof(symbol: str) -> dict[str, Any]:
        asked.append(symbol)
        return {"verdict": "COMPLIANT"}

    source = ProofBackedShariahSource(FakeShariah(), proof)
    assert source.company("AAA") == FakeShariah().company("AAA") and source.company_count() == 39
    assert source.proof("TCS") == {"verdict": "COMPLIANT"} and asked == ["TCS"]


def test_the_apps_own_wiring_gives_the_tool_the_engines_proof_from_the_bundled_filings(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from quant_system.server.v2 import copilot_wiring, paths, router, shariah_wiring
    from quant_system.shariah.filings.store import write_snapshot
    from quant_system.shariah.services import proof_paths
    from quant_system.shariah.services.proof_runtime import use_runtime
    from tests.shariah.proof_service_fixtures import standard_filings

    root = tmp_path / "app"
    monkeypatch.setenv("QUANTOS_APP_ROOT", str(root))
    monkeypatch.setattr(proof_paths, "REPO_ROOT", tmp_path / "checkout")
    monkeypatch.setattr(paths, "fixed_drive_roots", lambda: [])
    monkeypatch.setattr(paths, "_user_folders", lambda: [])
    snapshot = root / "data" / proof_paths.SNAPSHOT_FILE
    snapshot.parent.mkdir(parents=True)
    write_snapshot(snapshot, standard_filings(), "2026-10-07")
    use_runtime(None)
    router.reset_services()
    shariah_wiring.reset_proof_runtime()
    try:
        registry = default_registry(make_context(shariah=copilot_wiring._shariah()))
        data = registry.call("shariah_check", {"symbol": "FOODCO"}).data
        assert data["verdict_source"] == "filing" and data["filing"]["period_end"] == "2024-09-30"
    finally:
        shariah_wiring.reset_proof_runtime()
        router.reset_services()
