"""What QuantOS holds for one stock, and how it becomes the inputs the proof builder takes."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from quant_system.shariah.filings.models import FilingFigures
from quant_system.shariah.filings.status import DataStatus
from quant_system.shariah.services.activity_check import (
    ActivityResult,
    ActivityStatus,
    check_activity,
)
from quant_system.shariah.services.proof_types import (
    FigureIn,
    FilingIn,
    MarketValueIn,
    ProofInputs,
)

__all__ = [
    "USABLE",
    "Held",
    "activity_for",
    "company_name_of",
    "figures_in",
    "filing_in",
    "filing_inputs",
    "with_note",
]

USABLE = (DataStatus.VERIFIED_FILING, DataStatus.STALE)


@dataclass(frozen=True, slots=True)
class Held:
    """Everything QuantOS holds for one stock: its filing (if any), the filing's trust level, industry and sample."""

    symbol: str
    figures: FilingFigures | None
    status: DataStatus
    group: str | None
    sample: dict[str, Any] | None

    @property
    def usable_figures(self) -> FilingFigures | None:
        """The filing, only when it read cleanly, ties out and carries its proof. Anything else is not screened on."""
        return self.figures if self.status in USABLE else None

    @property
    def usable(self) -> bool:
        return self.usable_figures is not None


def figures_in(figures: FilingFigures) -> dict[str, FigureIn]:
    """Each line the filing carries, with the tag it was filed under and its value in rupees as filed."""
    return {
        key: FigureIn(key, line.label, line.xbrl_tag, line.value_inr)
        for key, line in figures.lines.items()
    }


def filing_in(figures: FilingFigures) -> FilingIn:
    """The filing's proof: where to open it, its period, when it was filed and the hash of the file as fetched."""
    proof = figures.proof
    return FilingIn(
        source_url=proof.source_url,
        detail_url=proof.detail_url,
        period_end=proof.period_end.isoformat(),
        period_label=proof.period_label,
        filed_on=proof.filed_on.isoformat() if proof.filed_on else None,
        consolidated=proof.consolidated,
        audited=proof.audited,
        sha256=proof.sha256,
        tie_out=tuple(check.to_json_dict() for check in figures.tie_out),
        tie_out_ok=bool(figures.tie_out) and all(check.ok for check in figures.tie_out),
    )


def company_name_of(held: Held) -> str:
    """The company's name as NSE filed it, else as the sample has it, else nothing."""
    if held.figures is not None and held.figures.company_name:
        return held.figures.company_name
    return str(held.sample.get("company_name") or "") if held.sample else ""


def activity_for(held: Held, name: str) -> ActivityResult:
    """The business test. The strictest reading wins: a fail by the sample or by the name and segments stands."""
    figures = held.usable_figures
    segments = figures.segment_names if figures is not None else ()
    by_text = check_activity(name, held.group, segments, None)
    if held.sample is None:
        return by_text
    by_sample = check_activity(name, held.group, segments, held.sample)
    if by_sample.status is ActivityStatus.FAIL:
        return by_sample
    if by_text.status is ActivityStatus.FAIL or held.usable:
        return by_text
    return by_sample


def filing_inputs(
    held: Held, activity: ActivityResult, market: MarketValueIn | None, screened_at: str
) -> ProofInputs:
    """Inputs for a stock screened from its filing."""
    figures = held.usable_figures
    if figures is None:
        raise ValueError("a proof from a filing needs a filing that can be used")
    return ProofInputs(
        symbol=held.symbol,
        company_name=company_name_of(held),
        activity=activity,
        data_status=held.status.value,
        screened_at=screened_at,
        filing=filing_in(figures),
        figures=figures_in(figures),
        market_value=market,
        sample=held.sample,
        isin=figures.isin or None,
    )


def with_note(proof: dict[str, Any], sentence: str | None) -> dict[str, Any]:
    """The proof with one more plain sentence on what it leaves out, placed before the closing disclaimer."""
    if not sentence:
        return proof
    gaps = list(proof["not_covered"])
    return {**proof, "not_covered": [*gaps[:-1], sentence, *gaps[-1:]]}
