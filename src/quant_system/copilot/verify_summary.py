"""What a panel of independent opinions adds up to, said plainly and without overclaiming.

Agreement between AI models is not independent evidence, because they learn from similar text; the summary says so
every time and also reports the three things that show how much an opinion is worth: whether models disagree,
whether one changes its mind when the same facts are reordered, and whether being told the platform's own pick
moved it (anchoring).
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from typing import Any

from quant_system.copilot.factpack import FactPack
from quant_system.copilot.providers import PROVIDER_LABELS
from quant_system.copilot.tools_market import counted
from quant_system.copilot.verify_opinion import Opinion

__all__ = ["DISCLOSURE", "ModelVerdict", "VerificationResult", "summarise"]

DISCLOSURE = (
    "These are opinions from AI models that read the same facts. They are not independent evidence: models trained "
    "on similar text tend to agree, and none of them can see the live market. In QuantOS's own research no model or "
    "strategy has shown an edge that survives real trading costs. Use this to decide what to check yourself, not "
    "as a reason to trade."
)
_SCORE = {"POSITIVE": 1, "MIXED": 0, "NEGATIVE": -1}


@dataclass(frozen=True, slots=True)
class ModelVerdict:
    """One model across the three questions it was asked. ``blind`` is the one that counts."""

    blind: Opinion
    informed: Opinion | None = None
    recheck: Opinion | None = None

    @property
    def stable(self) -> bool | None:
        if not (self.recheck and self.blind.ok and self.recheck.ok):
            return None
        return self.blind.reading == self.recheck.reading

    @property
    def anchored(self) -> bool | None:
        """Did the reading change once the model was told the platform's pick? None when either answer is missing."""
        if not (self.informed and self.blind.ok and self.informed.ok):
            return None
        return self.blind.reading != self.informed.reading

    @property
    def shift(self) -> int | None:
        """How much more favourable it got when told the platform's pick. None when either answer is missing."""
        if not (self.informed and self.blind.ok and self.informed.ok):
            return None
        before, after = _SCORE.get(str(self.blind.reading)), _SCORE.get(str(self.informed.reading))
        return None if before is None or after is None else after - before

    def as_dict(self) -> dict[str, Any]:
        return {
            "blind": self.blind.as_dict(),
            "informed": self.informed.as_dict() if self.informed else None,
            "recheck": self.recheck.as_dict() if self.recheck else None,
            "stable": self.stable,
            "shift": self.shift,
        }


@dataclass(slots=True)
class VerificationResult:
    symbol: str
    headline: str
    consensus: str  # AGREE, MAJORITY, SPLIT, SINGLE or NONE
    reading: str | None  # the reading most models share; None when they split or none answered
    asked: int
    answered: int
    counts: dict[str, int]
    news_tones: dict[str, int]
    verdicts: list[ModelVerdict]
    dissent: list[dict[str, Any]]
    notes: list[str]
    halal: dict[str, Any] | None
    facts: dict[str, Any]
    disclosure: str = DISCLOSURE

    def as_dict(self) -> dict[str, Any]:
        return {
            "symbol": self.symbol,
            "headline": self.headline,
            "consensus": self.consensus,
            "reading": self.reading,
            "asked": self.asked,
            "answered": self.answered,
            "counts": self.counts,
            "news_tones": self.news_tones,
            "verdicts": [v.as_dict() for v in self.verdicts],
            "dissent": self.dissent,
            "notes": self.notes,
            "halal": self.halal,
            "facts": self.facts,
            "disclosure": self.disclosure,
        }


def _modal(readings: list[str]) -> str | None:
    top = Counter(readings).most_common(2)
    if not top or (len(top) > 1 and top[0][1] == top[1][1]):
        return None
    return top[0][0]


def _consensus(readings: list[str], modal: str | None) -> str:
    """AGREE, MAJORITY (the top reading has more than half of those who answered), SPLIT, SINGLE or NONE."""
    if not readings:
        return "NONE"
    if len(readings) == 1:
        return "SINGLE"
    if modal is None:
        return "SPLIT"
    share = readings.count(modal)
    if share == len(readings):
        return "AGREE"
    return "MAJORITY" if share * 2 > len(readings) else "SPLIT"


def _answered_prefix(answered: int, asked: int) -> str:
    """Empty when everyone asked answered; otherwise says so in words, so a smaller group is never called 'all'."""
    return "" if answered == asked else f"{answered} of {asked} models answered, and "


def _headline(consensus: str, modal: str | None, readings: list[str], asked: int) -> str:
    count = len(readings)
    prefix = _answered_prefix(count, asked)
    if consensus == "NONE":
        return "None of the AI models could answer, so there is no second opinion yet."
    if consensus == "SINGLE":
        who = "Only 1 model was asked" if asked == 1 else f"Only 1 of {asked} models answered"
        return f"{who}, so nothing was cross-checked. It read the facts as {readings[0]}."
    if consensus == "SPLIT":
        group = "they" if prefix else f"The {count} models"
        return f"{prefix}{group} disagree with each other. There is no shared reading."
    if consensus == "AGREE":
        everyone = ("both" if count == 2 else "all") if prefix else f"All {count} models"
        return f"{prefix}{everyone} read the facts as {modal}."
    of_whom = "them" if prefix else f"{count} models"
    return f"{prefix}{readings.count(str(modal))} of {of_whom} read the facts as {modal}."


def _dissent(answered: list[ModelVerdict], modal: str | None) -> list[dict[str, Any]]:
    return [
        {
            "provider": v.blind.provider,
            "model": v.blind.model,
            "reading": v.blind.reading,
            "reasons": list(v.blind.reasons),
            "risks": list(v.blind.risks),
        }
        for v in answered
        if v.blind.reading != modal
    ]


def _stability_note(verdicts: list[ModelVerdict]) -> str | None:
    checked = [v for v in verdicts if v.stable is not None]
    changed = [v for v in checked if v.stable is False]
    if not changed:
        return None
    return (
        f"{len(changed)} of {counted(len(checked), 'AI model')} changed their reading when the same facts were "
        "shown in a different order. Treat those readings as weak."
    )


def _anchoring_note(verdicts: list[ModelVerdict]) -> str | None:
    measured = [v for v in verdicts if v.anchored is not None]
    anchored = [v for v in measured if v.anchored]
    if not anchored:
        return None
    return (
        f"{len(anchored)} of {counted(len(measured), 'AI model')} changed their reading after being told QuantOS "
        "had picked this stock, whether more favourable or less. That is anchoring, so go by the readings given "
        "without that hint."
    )


def _unanswered_note(asked: int, answered: int) -> str:
    failed = asked - answered
    reasons = "Its reason is" if failed == 1 else "Each one's reason is"
    return f"{failed} of {counted(asked, 'AI model')} could not answer. {reasons} shown with its answer."


def _one_service_note(providers: set[str]) -> str:
    name = next(iter(providers))
    return (
        f"Every answer came from one AI service, {PROVIDER_LABELS.get(name, name)}, so they are less independent. "
        "Add a second AI in Settings, then AI assistants, for a real cross-check."
    )


def _removed_note(removed: int) -> str:
    what = (
        "1 statement was removed because it"
        if removed == 1
        else f"{removed} statements were removed because they"
    )
    return f"{what} told you to trade or ruled on halal status. Halal status comes only from the screener."


def _sample_notes(
    verdicts: list[ModelVerdict], answered: list[ModelVerdict], asked: int
) -> list[str]:
    notes: list[str] = []
    if asked > len(answered):
        notes.append(_unanswered_note(asked, len(answered)))
    providers = {v.blind.provider for v in answered}
    if len(answered) >= 1 and len(providers) == 1:
        notes.append(_one_service_note(providers))
    removed = sum(o.removed for v in verdicts for o in (v.blind, v.informed, v.recheck) if o)
    if removed:
        notes.append(_removed_note(removed))
    return notes


def _notes(verdicts: list[ModelVerdict], answered: list[ModelVerdict], asked: int) -> list[str]:
    extra = [_stability_note(verdicts), _anchoring_note(verdicts)]
    return [*_sample_notes(verdicts, answered, asked), *(note for note in extra if note)]


def summarise(
    pack: FactPack, verdicts: list[ModelVerdict], asked: int, extra_notes: list[str]
) -> VerificationResult:
    answered = [v for v in verdicts if v.blind.ok]
    readings = [str(v.blind.reading) for v in answered]
    modal = _modal(readings)
    consensus = _consensus(readings, modal)
    shared = modal if consensus in ("AGREE", "MAJORITY", "SINGLE") else None
    return VerificationResult(
        symbol=pack.symbol,
        headline=_headline(consensus, modal, readings, asked),
        consensus=consensus,
        reading=shared,
        asked=asked,
        answered=len(answered),
        counts=dict(Counter(readings)),
        news_tones=dict(Counter(str(v.blind.news_tone) for v in answered)),
        verdicts=verdicts,
        dissent=_dissent(answered, shared) if consensus in ("MAJORITY", "SPLIT") else [],
        notes=[*extra_notes, *_notes(verdicts, answered, asked)],
        halal=pack.halal,
        facts=pack.as_dict(),
    )
