"""The business-activity test for a stock, and exactly what it was decided on.

A results filing does not say what a company sells. What QuantOS can read is the company's name, its NSE industry
group and the business segments the filing itself lists (a cigarette maker lists a cigarettes segment). A company in
the hand-entered sample keeps the classification typed in there. Where none of this is enough to say, the answer is
"not confirmed", never "passes".
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from quant_system.shariah.services.sector_rules import (
    INTEREST_REASON,
    SECTOR_RULES,
    SectorRule,
)
from quant_system.shariah.services.transparency import sector_rule_for

__all__ = ["ActivityResult", "ActivityStatus", "check_activity", "clean_segment_names"]

#: Groups where a prohibited line of business (tobacco, liquor, gaming, cinemas) can sit beside ordinary ones.
SENSITIVE_GROUPS = frozenset(
    {
        "fast moving consumer goods",
        "consumer services",
        "media entertainment & publication",
        "diversified",
        "services",
    }
)
FINANCE_GROUP = "financial services"
#: Words in a company's name that say it lends or insures on interest.
LENDER_WORDS = (
    "bank",
    "finance",
    "financial",
    "finserv",
    "fincorp",
    "insurance",
    "assurance",
    "lending",
    "microfinance",
    "leasing",
    "nbfc",
)
#: Words the sample's technology exemption already guards against, tied to the rule they belong to.
EXTRA_WORDS = {"gambling": ("betting",)}
MAX_SEGMENTS = 20
MAX_SEGMENT_CHARS = 120
_MARKUP = re.compile(r"[<>\x00-\x1f\x7f]")


class ActivityStatus(StrEnum):
    PASS = "PASS"
    FAIL = "FAIL"
    NOT_CONFIRMED = "NOT_CONFIRMED"


@dataclass(frozen=True, slots=True)
class ActivityResult:
    status: ActivityStatus
    basis: str
    plain: str
    industry_group: str | None = None
    segments: tuple[str, ...] = ()
    rule: str | None = None
    matched_keyword: str | None = None
    matched_in: str | None = None  # "name", "segment" or "sample"
    reason: str | None = None

    def as_dict(self) -> dict[str, Any]:
        return {
            # ``compliant`` keeps the older yes/no shape; it is None when the test could not be decided.
            "compliant": {"PASS": True, "FAIL": False}.get(self.status.value),
            "status": self.status.value,
            "basis": self.basis,
            "rule": self.rule,
            "matched_keyword": self.matched_keyword,
            "matched_in": self.matched_in,
            "reason": self.reason,
            "industry_group": self.industry_group,
            "segments": list(self.segments),
            "plain": self.plain,
        }


def clean_segment_names(names: Any) -> tuple[str, ...]:
    """Segment names are text from outside the app: no markup or control characters, bounded in count and length."""
    cleaned: list[str] = []
    for name in names or ():
        text = " ".join(_MARKUP.sub(" ", str(name)).split())[:MAX_SEGMENT_CHARS]
        if text and text not in cleaned:
            cleaned.append(text)
    return tuple(cleaned[:MAX_SEGMENTS])


def _pattern(word: str) -> re.Pattern[str]:
    """The word as a whole word, allowing a plural ("cigarettes", "breweries")."""
    stem = word[:-1] + "(?:y|ies)" if word.endswith("y") else re.escape(word) + "(?:s|es)?"
    return re.compile(rf"(?<![a-z0-9]){stem}(?![a-z0-9])")


def _rule_words(rule: SectorRule) -> tuple[str, ...]:
    return (*rule.keywords, *EXTRA_WORDS.get(rule.rule, ()))


def _search(text: str, rules: tuple[SectorRule, ...]) -> tuple[SectorRule, str] | None:
    lowered = text.lower()
    hits = (
        (rule, word)
        for rule in rules
        for word in _rule_words(rule)
        if _pattern(word).search(lowered)
    )
    return next(hits, None)


def _text_hit(
    name: str, segments: tuple[str, ...], rules: tuple[SectorRule, ...]
) -> tuple[SectorRule, str, str, str] | None:
    """A prohibited word in the segments first (they describe what is sold), then in the name."""
    for segment in segments:
        hit = _search(segment, rules)
        if hit:
            return hit[0], hit[1], "segment", f'a business segment in its filing, "{segment}"'
    named = _search(name, rules)
    return (named[0], named[1], "name", "its name") if named else None


def _lender_hit(name: str) -> str | None:
    lowered = name.lower()
    return next((w for w in LENDER_WORDS if _pattern(w).search(lowered)), None)


def _sample_result(sample: dict[str, Any], group: str | None) -> ActivityResult:
    found = sector_rule_for(sample)
    plain = (
        f"Screened out for its business: {found.reason}."
        if not found.compliant
        else "Its business passes the sector test in QuantOS's hand-entered sample."
    )
    return ActivityResult(
        ActivityStatus.PASS if found.compliant else ActivityStatus.FAIL,
        "sample classification",
        plain,
        group or str(sample.get("sector") or "") or None,
        (),
        found.rule,
        found.matched_keyword,
        "sample" if not found.compliant else None,
        found.reason,
    )


def _failure(
    hit: tuple[SectorRule, str, str, str], group: str | None, segments: tuple[str, ...]
) -> ActivityResult:
    rule, word, matched_in, source = hit
    basis = "the filing's segments" if matched_in == "segment" else "company name"
    plain = f"Screened out for its business: {rule.reason}. The word '{word}' appears in {source}."
    return ActivityResult(
        ActivityStatus.FAIL, basis, plain, group, segments, rule.rule, word, matched_in, rule.reason
    )


def _finance(name: str, group: str | None, segments: tuple[str, ...]) -> ActivityResult:
    word = _lender_hit(name)
    if word is not None:
        plain = f"Screened out for its business: {INTEREST_REASON}. The word '{word}' appears in its name."
        return ActivityResult(
            ActivityStatus.FAIL,
            "company name",
            plain,
            group,
            segments,
            "interest_based_finance",
            word,
            "name",
            INTEREST_REASON,
        )
    plain = (
        "It is in the Financial Services group and its name does not say whether it lends or insures on interest, "
        "so QuantOS cannot tell whether its business passes."
    )
    return ActivityResult(
        ActivityStatus.NOT_CONFIRMED, "industry group only", plain, group, segments
    )


def _by_group(group: str | None, segments: tuple[str, ...]) -> ActivityResult:
    if group is None:
        plain = "QuantOS has no industry classification for this company, so it cannot tell what it sells."
        return ActivityResult(ActivityStatus.NOT_CONFIRMED, "no classification", plain)
    if group.lower() not in SENSITIVE_GROUPS:
        plain = (
            f"QuantOS checked the industry group ({group}) and the company's name. It does not have a "
            "product-level description of this company, so it cannot rule out a prohibited line inside the group."
        )
        return ActivityResult(ActivityStatus.PASS, "industry group only", plain, group, segments)
    if segments:
        listed = "; ".join(segments)
        plain = f"None of the {len(segments)} business segments in its filing is a prohibited line: {listed}."
        return ActivityResult(
            ActivityStatus.PASS, "industry group and the filing's segments", plain, group, segments
        )
    plain = (
        f"QuantOS cannot tell what this company sells. It is in the {group} group, which includes companies in "
        "prohibited lines, and its filing lists no business segments to check."
    )
    return ActivityResult(
        ActivityStatus.NOT_CONFIRMED, "industry group only", plain, group, segments
    )


def check_activity(
    name: str,
    group: str | None,
    segments: tuple[str, ...],
    sample: dict[str, Any] | None,
) -> ActivityResult:
    """Decide the business-activity test from the sample row when there is one, else from the name, group, segments."""
    clean = clean_segment_names(segments)
    if sample is not None:
        return _sample_result(sample, group)
    hit = _text_hit(name, clean, SECTOR_RULES)
    if hit is not None:
        return _failure(hit, group, clean)
    if group is None:
        return _finance(name, None, clean) if _lender_hit(name) else _by_group(None, clean)
    if group.lower() == FINANCE_GROUP:
        return _finance(name, group, clean)
    return _by_group(group, clean)
