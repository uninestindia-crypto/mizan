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
_SENTENCE_END = re.compile(r"(?<=[.!?])\s+")
_LINK = re.compile(r"\[([^\]\n]*)\]\((\S+?)\)")
_BARE_LINK = re.compile(r"https?://[^\s<>\"')\]]+")

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
    | (?<!\bno\s)(?<!\bnot\s)(?<!\bnever\s)(?<!cannot\s)(?<!n't\s)\bguarantee[sd]?\b   # a claim, not a disclaimer
    | \bsure[\s-](?:thing|gain|shot|bet|profit|win)s?\b | \bsurefire\b | \brisk[\s-]?free\b | \bno[\s-]risk\b
    | \b(?:can'?t|cannot|won'?t|will\s+not)\s+(?:lose|fail|go\s+wrong)\b
    | \b(?:real|clear|proven|true|statistical|definite|strong)\s+edge\b | \bedge\s+(?:over|against|on)\s+the\s+market\b
    | \bbeat(?:s|ing)?\s+the\s+market\b | \bmulti-?baggers?\b
    | \bwill\s+(?:double|triple|multiply|soar|skyrocket|surge|rocket)\b
    | \b(?:certain|bound|sure)\s+to\s+(?:rise|go\s+up|gain|grow|double|win|outperform)\b
    | \balways\s+(?:rises?|goes?\s+up|wins?)\b
    | \b(?:top|best|favou?rite)\s+pick\b | \bundervalued\b | \bsafe\s+bet\b | \bbargain\b | \bload\s+up\b
    | \bgo\s+for\s+(?!a\b|an\b|the\b)\w+ | \bput\s+(?:your|some)\s+money\b | \b(?:consider|think\s+about)\s+adding\b
    | \bgood\s+(?:fit|investment)\b
    | \bshould\s+(?:you\s+)?(?:invest|hold)\b | \bworth\s+(?:buying|investing)\b
    """,
    re.VERBOSE,
)
_HALAL = re.compile(
    r"""
    \bhal+a+l\b | \bhara+m\b | \bkosher\b | \bmuslims?\b | \binterest[\s-](?:free|based)\b
    | \bshari\w* | \bsharia\w* | \bfatwa\w* | \bpermissib\w* | \bimpermissib\w*
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


def _scrub_line(line: str, halal_allowed: bool) -> tuple[str, int, int]:
    """One line of a reply with its advice and (unless allowed) halal sentences removed: (text, advice, halal)."""
    kept: list[str] = []
    advice = halal = 0
    for sentence in _SENTENCE_END.split(line):
        if not sentence.strip():
            continue
        if is_advice(sentence):
            advice += 1
        elif mentions_halal(sentence) and not halal_allowed:
            halal += 1
        else:
            kept.append(sentence.strip())
    return " ".join(kept), advice, halal


def scrub_prose(
    text: str, *, halal_allowed: bool, allowed_links: Collection[str] = ()
) -> ScrubResult:
    """A model's free-text reply. Advice sentences go; halal sentences go unless the screener ran; stray links go.

    ``halal_allowed`` is true only when the halal screener tool actually ran for this answer, because then the model
    is quoting the screener and the caller appends the screener's own block as the authority. Lines and paragraphs
    the reply already had are kept as they were; only the offending sentences are cut out.
    """
    linked, links = _only_known_links(text, allowed_links)
    lines: list[str] = []
    advice = halal = 0
    for line in linked.split("\n"):
        kept, line_advice, line_halal = (
            _scrub_line(line, halal_allowed) if line.strip() else ("", 0, 0)
        )
        advice, halal = advice + line_advice, halal + line_halal
        if kept or not line.strip():
            lines.append(kept)
    notes = ([_REMOVED_ADVICE] if advice else []) + ([_REMOVED_HALAL] if halal else [])
    body = re.sub(r"\n{3,}", "\n\n", "\n".join(lines)).strip()
    return ScrubResult("\n\n".join(part for part in (body, *notes) if part), advice, halal, links)
