"""The deterministic guard on text that came from an AI model or from outside the app.

Prompts ask a model not to give trading advice and not to rule on halal status, but a prompt is a request, not a
control. This module is the control: it looks at what a model actually wrote and removes what must not reach a
person. It also keeps outside text from closing the fence that marks it as data.

The word lists catch ordinary phrasing in Latin script, including look-alike letters, hidden characters, spaced-out
letters and common inflections. They do not catch every paraphrase or other languages, so the prompts and the
wording of the screens still carry the rest. A statement is removed rather than rewritten.
"""

from __future__ import annotations

import re
import unicodedata
from collections.abc import Collection
from dataclasses import dataclass

__all__ = [
    "ScrubResult",
    "fence",
    "is_advice",
    "mentions_halal",
    "normalise",
    "scrub_points",
    "scrub_prose",
]

_HIDDEN = frozenset(
    {"Cf", "Cc", "Co", "Cn", "Mn", "Me"}
)  # format, control, private, unassigned, combining marks
_SPACED = re.compile(r"\b(?:[a-z][\s.\-_]){2,}[a-z]\b")
_SENTENCES = re.compile(r"(?<=[.!?])\s+|\n+")
_LINK = re.compile(r"\[([^\]\n]*)\]\((\S+?)\)")
_BARE_LINK = re.compile(r"https?://\S+")

_ADVICE = re.compile(
    r"""
    \b(?:buy|buys|buying|sell|sells|selling)\b(?!-(?:back|off|side)\b)   # not buy-back or sell-off
    | \baccumulat\w*
    | \bgo(?:ing)?\s+(?:long|short)\b
    | \b(?:add|adding|averag\w+|build\w*)\s+(?:to\s+)?(?:your\s+|the\s+|a\s+)?(?:position|holding)s?\b
    | \b(?:exit|exiting|trim|trimming|dump|dumping)\s+(?:your\s+|the\s+)?(?:position|stock|shares?|holding)s?\b
    | \bexit\s+before\b
    | \bbook(?:ing)?\s+(?:your\s+)?profits?\b | \btake\s+profits?\b
    | \b(?:over|under)weight\b | \boutperform\w* | \bunderperform\w*
    | \bstop[\s-]?loss\b | \bstoploss\b
    | \btarget\s+price\b | \bprice\s+(?:target|objective)\b | \btarget\s+of\s+(?:rs|inr|₹|\d)
    | \bfair\s+value\b | \bintrinsic\s+value\b
    | \bexpected\s+to\s+(?:reach|hit|touch|rise\s+to)\b | \b(?:upside|downside)\s+of\b
    | \b(?:i|we)\s+(?:recommend|advise)\b | \brecommend(?:ation|ed)?\b
    | \bshould\s+(?:you\s+)?(?:invest|hold)\b | \bworth\s+(?:buying|investing)\b
    """,
    re.VERBOSE,
)
_HALAL = re.compile(
    r"""
    \bhal+a+l\b | \bharam\b | \bshari\w* | \bsharia\w* | \bfatwa\w* | \bpermissib\w* | \bimpermissib\w*
    | \bislam\w* | \briba\b | \baaoifi\b | \btasis\b | \blawful\b | \bunlawful\b | \bcompliant\b | \bcompliance\b
    | \bpermitted\b | \bforbidden\b
    """,
    re.VERBOSE,
)
_REMOVED_ADVICE = (
    "(A sentence that read like trading advice was removed. QuantOS does not give trading advice.)"
)
_REMOVED_HALAL = (
    "(A statement about halal status was removed. Only the halal screener may state it: ask whether the stock "
    "is halal and QuantOS will run the screener.)"
)


def normalise(text: str) -> str:
    """Lower-cased text with look-alike letters folded, hidden characters and marks dropped, spaced letters joined."""
    folded = unicodedata.normalize("NFKD", text)
    visible = "".join(
        ch if ch in "\n" or unicodedata.category(ch) not in _HIDDEN else "" for ch in folded
    )
    lowered = visible.lower()
    return _SPACED.sub(lambda match: re.sub(r"[\s.\-_]", "", match.group(0)), lowered)


def is_advice(text: str) -> bool:
    return bool(_ADVICE.search(normalise(text)))


def mentions_halal(text: str) -> bool:
    return bool(_HALAL.search(normalise(text)))


def fence(body: str) -> str:
    """Text that cannot close an ``<untrusted_data>`` fence from the inside."""
    return body.replace("<", "\\u003c").replace(">", "\\u003e")


@dataclass(frozen=True, slots=True)
class ScrubResult:
    text: str
    removed_advice: int = 0
    removed_halal: int = 0
    removed_links: int = 0

    @property
    def removed(self) -> int:
        return self.removed_advice + self.removed_halal + self.removed_links


def scrub_points(points: Collection[str]) -> tuple[list[str], int]:
    """Short structured statements: any advice or halal wording drops the whole statement. Returns (kept, removed)."""
    kept = [p for p in points if not (is_advice(p) or mentions_halal(p))]
    return kept, len(points) - len(kept)


def _only_known_links(text: str, allowed: Collection[str]) -> tuple[str, int]:
    """Keep a link only when its address came from a tool result; otherwise keep just its words."""
    dropped = 0

    def keep(match: re.Match[str]) -> str:
        nonlocal dropped
        if match.group(2) in allowed:
            return match.group(0)
        dropped += 1
        return match.group(1)

    out = _LINK.sub(keep, text)
    bare = [u for u in _BARE_LINK.findall(out) if u.rstrip(").,") not in allowed]
    for url in bare:
        out = out.replace(url, "")
        dropped += 1
    return out, dropped


def scrub_prose(
    text: str, *, halal_allowed: bool, allowed_links: Collection[str] = ()
) -> ScrubResult:
    """A model's free-text reply. Advice sentences go; halal sentences go unless the screener ran; stray links go.

    ``halal_allowed`` is true only when the halal screener tool actually ran for this answer, because then the model
    is quoting the screener and the caller appends the screener's own block as the authority.
    """
    linked, links = _only_known_links(text, allowed_links)
    kept: list[str] = []
    advice = halal = 0
    for sentence in _SENTENCES.split(linked):
        if not sentence.strip():
            continue
        if is_advice(sentence):
            advice += 1
        elif mentions_halal(sentence) and not halal_allowed:
            halal += 1
        else:
            kept.append(sentence.strip())
    notes = ([_REMOVED_ADVICE] if advice else []) + ([_REMOVED_HALAL] if halal else [])
    return ScrubResult(
        "\n\n".join([*kept, *notes]) if (kept or notes) else "", advice, halal, links
    )
