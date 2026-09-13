"""Name each unresolved demerger's *resulting company* from the issuer's own NSE announcements.

What this closes, and what it deliberately does not
---------------------------------------------------
`validate_demerger_factors.py` leaves 53 of 54 ratio-less actions unresolved because nobody has
supplied the entitlement ratio from the issuer filing. Its discovery worklist ranks candidate
resulting companies by shared name stem, which is a heuristic -- measured at an 8.51% false-discovery
rate on price fit alone, and better but still a guess on the stem.

The NSE corporate-announcements API returns the issuer's own filing text, and for a scheme of
arrangement that text **names the resulting company directly**. For SKF India it reads:

    "Scheme of Arrangement between SKF India Limited (... Demerged Company ...) and
     SKF India (Industrial) Limited (... Resulting Company ...)"

That is the issuer saying which entity was created. It replaces a heuristic with a citation, and it
reduces a human's job from "identify the company and find the ratio" to "confirm the ratio".

**It does not supply the ratio.** The share entitlement ratio lives in the PDF attachment, not in the
API's text fields -- checked across SKFINDIA, ABFRL and RAYMOND, 4,073 announcements between them,
with zero ratio patterns in any text field. Extracting it would mean parsing 53 PDFs, and a
misparsed ratio is worse than no ratio: it would produce a *validated-looking* factor that is wrong,
which is precisely the failure `validate_demerger_factors.py` exists to prevent. So the attachment
URL is recorded for a human to open, and nothing here writes a factor.

Network and courtesy
--------------------
NSE requires a session cookie from the site root before its API will answer, and rate-limits. One
request per symbol, a short pause between symbols, and failures are recorded per symbol rather than
aborting the run.
"""

from __future__ import annotations

import argparse
import gzip
import json
import re
import sys
import time
import urllib.error
import urllib.request
from datetime import UTC, date, datetime
from http.cookiejar import CookieJar
from pathlib import Path
from typing import Any, NamedTuple

ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR / "scripts"))
sys.path.insert(0, str(ROOT_DIR / "src"))

NSE_ROOT = "https://www.nseindia.com"
NSE_ANNOUNCEMENTS = NSE_ROOT + "/api/corporate-announcements?index=equities&symbol={symbol}"

SCHEME_HINT = re.compile(r"demerg|scheme of arrangement", re.I)

RESULTING_COMPANY = re.compile(
    r"(?:and\s+)?([A-Z][A-Za-z0-9&.,()\- ]{3,80}?)\s*\(\s*([^)]{0,60}?)resulting company", re.I
)
"""Capture the entity the filing itself labels the Resulting Company, and its other aliases.

Anchored on the issuer's own parenthetical, which is boilerplate in Indian scheme documents:
``... and SKF India (Industrial) Limited ("SKF Industrial" or "Resulting Company") ...``

Group 2 is the alias text preceding ``Resulting Company`` inside that parenthetical. It is captured
because it carries a decisive signal -- see :func:`_is_self_alias`.
"""


def _is_self_alias(alias: str) -> bool:
    """True when the filing's alias for the Resulting Company is the bare word ``Company``.

    Indian filings call the entity they are filing about "the Company". So
    ``Reliance Industries Limited ("Company" or "Resulting Company")`` is RIL describing an *inbound*
    merger in which it is the surviving entity -- a different transaction from the demerger whose
    ex-date we are pricing, which merely fell inside the search window. The extraction is correct and
    the *announcement* is the wrong one, which no amount of better parsing would fix, so it is
    flagged rather than parsed harder.

    **Matched on words, not on quote characters.** NSE's own stored text is mojibake: the smart
    quotes around ``Company`` arrive as three ``U+FFFD`` replacement characters each, so a pattern
    anchored on ``"`` or ``“`` silently never fires. An earlier version of this check did exactly
    that and passed RELIANCE through unflagged.
    """
    return any(word.casefold() == "company" for word in re.findall(r"[A-Za-z]+", alias))


DEMERGED_COMPANY = re.compile(
    r"([A-Z][A-Za-z0-9&.,()\- ]{3,80}?)\s*\(\s*[^)]{0,60}?demerged company", re.I
)

WINDOW_DAYS = 540
"""How far either side of the ex-date an announcement may fall and still describe the same scheme.

Generous on purpose: a scheme is announced, approved and made effective over many months, and the
ex-date sits near the end. Every match is reported with its own date so a human can judge.
"""


def opener() -> urllib.request.OpenerDirector:
    """A cookie-bearing opener, primed at the site root as NSE requires."""
    build = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(CookieJar()))
    build.open(urllib.request.Request(NSE_ROOT, headers=_headers()), timeout=25).read(2048)
    return build


def _headers() -> dict[str, str]:
    return {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": "en-US,en;q=0.9",
        "Referer": NSE_ROOT + "/companies-listing/corporate-filings-announcements",
    }


def fetch_announcements(client: urllib.request.OpenerDirector, symbol: str) -> list[dict[str, Any]]:
    request = urllib.request.Request(NSE_ANNOUNCEMENTS.format(symbol=symbol), headers=_headers())
    response = client.open(request, timeout=40)
    raw = response.read()
    if response.headers.get("Content-Encoding") == "gzip":
        raw = gzip.decompress(raw)
    payload = json.loads(raw)
    return payload if isinstance(payload, list) else []


def _announced_on(item: dict[str, Any]) -> date | None:
    for key in ("an_dt", "sort_date", "dt"):
        text = str(item.get(key) or "")
        for fmt in ("%d-%b-%Y %H:%M:%S", "%d-%b-%Y", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
            try:
                return datetime.strptime(text.strip(), fmt).date()
            except ValueError:
                continue
    return None


CORPORATE_SUFFIX = re.compile(r"^(?:Limited|LIMITED|Ltd\.?|LTD\.?|LLP)[.,;:]?$")
"""The token that ends an Indian company name. The name is found by walking back from here.

Upper-case and title-case only, never lower-case. Issuers file in both -- VAKRANGEE's own filing
reads ``VL E-GOVERNANCE & IT SOLUTIONS LIMITED`` -- but admitting a lower-case ``limited`` would
anchor on the ordinary English adjective (``limited liability``, ``limited to``) and walk back
through a sentence.

A suffix token ending in ``)`` is deliberately excluded, because it closes a parenthetical aside
rather than the operative name: ``Aarti Pharmalabs Limited (Formerly Known as Aarti Organics
Limited)`` names the resulting company first and a former name second.
"""

NAME_TOKEN = re.compile(r"^(?:[A-Z][A-Za-z0-9&.'\-]*|\([A-Z][A-Za-z0-9&.'\-]*\)|&)$")
"""A token that may belong to a company name: a capitalised word, ``&``, or ``(Industrial)``.

The parenthesised alternative is not decoration -- ``SKF India (Industrial) Limited`` is the real
registered name of a real resulting company in this worklist.
"""

NAME_JOINER: frozenset[str] = frozenset({"of", "and"})
"""Lowercase words that occur *inside* names (``Bank of Baroda``) as well as between them.

Accepted mid-walk, then stripped if the walk ends on one -- see :func:`_clean`.
"""

ROLE_NOISE = re.compile(r"^(?:And|Of|By|With|Between|Amongst|Among|Company|Demerged|Resulting)\s+")
"""Capitalised words the surrounding sentence leaves attached to the front of a walked-back name."""

MAX_NAME_TOKENS = 8

BLOCKING_FLAGS: frozenset[str] = frozenset(
    {
        "FILER_IS_RESULTING_COMPANY",
        "RESULTING_EQUALS_DEMERGED",
        "FILING_BELONGS_TO_ANOTHER_EX_DATE",
    }
)
"""Flags that disqualify a match from being *the* answer, rather than merely qualifying it.

Both mean the announcement describes a transaction in which the filer survives, so it is not the
demerger creating a new entity that this worklist is trying to name. The match is still reported --
its attachment and quote are useful to a human -- but it does not become the named resulting company.
"""


class ExtractedName(NamedTuple):
    """A walked-back name, its qualifying flags, and the token that ended the walk.

    ``stopped_on`` is carried out so the caller can test it against the *demerged* company's name --
    the one truncation signal available without guessing. See :func:`scheme_matches`.
    """

    name: str
    flags: list[str]
    stopped_on: str


def _clean(name: str) -> ExtractedName:
    """Reduce a captured span to the company name the issuer actually wrote.

    The span before the issuer's ``(... Resulting Company)`` parenthetical routinely carries
    preamble -- ``") and Aditya Birla Lifestyle Brands Limited"``, or a whole sentence beginning
    ``"Execution of the Undertaking cum Indemnity agreements by ..."``.

    **Scanning forwards cannot fix this**, and the earlier attempt to do so is worth recording. A
    regex anchored on a capital and ending at the corporate suffix matches from the *first* capital
    in the span, so it returns the preamble and the name as one match; taking the last of several
    matches does not help, because there is only ever one. Requiring the anchor to be a genuine
    capital (removing an ``re.I``) fixed only the sub-word case.

    So the walk goes the other way: find the corporate suffix, then step **backwards** while each
    token still looks like part of a name. A lowercase connective (``by``, ``as``, ``cum``, ``and``)
    or punctuation (``)``, ``"``, ``,``) ends the name, which is exactly where the preamble begins.

    Returns the name and any flags qualifying it. An empty name means nothing citable was found,
    which is reported as *unnamed* -- never as a name -- because the whole point of this artifact is
    to replace a heuristic with a citation, and a degenerate citation is worse than none.
    """
    flags: list[str] = []
    tokens = re.sub(r"\s+", " ", name).strip().split(" ")
    end = next(
        (i for i in range(len(tokens) - 1, -1, -1) if CORPORATE_SUFFIX.match(tokens[i])),
        None,
    )
    if end is None:
        return ExtractedName("", ["NO_CORPORATE_SUFFIX"], "")
    start = end
    stopped_on = ""
    while start > 0:
        if end - start >= MAX_NAME_TOKENS:
            flags.append("NAME_MAY_BE_TRUNCATED")  # stopped on a bound, not on a boundary
            break
        candidate = tokens[start - 1].strip("\"'")
        if not (NAME_TOKEN.match(candidate) or candidate.lower() in NAME_JOINER):
            stopped_on = candidate
            break
        start -= 1
    # A joiner may sit inside a name but never opens one, so peel any the walk ran through.
    while start < end and tokens[start].lower() in NAME_JOINER:
        start += 1
    text = " ".join(tokens[start : end + 1]).strip(" ,.&-\"'")
    previous = None
    while previous != text:  # role words the issuer's sentence left attached
        previous = text
        text = ROLE_NOISE.sub("", text).strip(" ,.&-\"'")
    if len(text.split(" ")) < 2:
        # A bare "Limited" is what remains when the filing referred to the entity by a short alias
        # only ("allotment of Equity Shares by Onesource"). It names nothing.
        return ExtractedName("", ["BARE_SUFFIX_NO_NAME"], stopped_on)
    return ExtractedName(text, flags, stopped_on)


def scheme_matches(announcements: list[dict[str, Any]], ex_date: date) -> list[dict[str, Any]]:
    """Announcements near ``ex_date`` that name a Resulting Company, newest first."""
    found: list[dict[str, Any]] = []
    for item in announcements:
        text = " ".join(str(item.get(k) or "") for k in ("desc", "attchmntText"))
        if not SCHEME_HINT.search(text):
            continue
        on = _announced_on(item)
        if on is not None and abs((on - ex_date).days) > WINDOW_DAYS:
            continue
        resulting = RESULTING_COMPANY.search(text)
        if resulting is None:
            continue
        resulting_name, flags, stopped_on = _clean(resulting.group(1))
        if _is_self_alias(resulting.group(2) or ""):
            flags.append("FILER_IS_RESULTING_COMPANY")
        demerged = DEMERGED_COMPANY.search(text)
        demerged_name = _clean(demerged.group(1)).name if demerged else ""
        if resulting_name and demerged_name.casefold() == resulting_name.casefold():
            flags.append("RESULTING_EQUALS_DEMERGED")
        if stopped_on and stopped_on.casefold() in {
            word.casefold() for word in demerged_name.split(" ")
        }:
            # The walk stopped on a word that also appears inside the demerged company's own name,
            # so it most likely cut through a name rather than at a sentence boundary. SCI is the
            # real case: the filing types "Shipping Corporation of india Land and Assets Limited"
            # with a lowercase "india", which reads as a connective and truncates the name to
            # "Land and Assets Limited". Flagged, never repaired -- a guessed repair is the failure
            # this whole artifact exists to avoid.
            flags.append("NAME_MAY_BE_TRUNCATED")
        found.append(
            {
                "announced_on": on.isoformat() if on else None,
                "resulting_company": resulting_name or None,
                "demerged_company": demerged_name or None,
                "flags": flags,
                "usable": bool(resulting_name) and not (BLOCKING_FLAGS & set(flags)),
                "attachment": item.get("attchmntFile"),
                "quote": re.sub(
                    r"\s+", " ", text[max(0, resulting.start() - 160) : resulting.end() + 60]
                ),
            }
        )
    found.sort(key=lambda item: item["announced_on"] or "", reverse=True)
    return found


def _reject_filings_claimed_by_a_nearer_ex_date(
    rows: list[dict[str, Any]],
) -> None:
    """One filing cannot describe two different demergers of the same issuer.

    The search window is +/-540 days, deliberately generous because a scheme is announced, approved
    and made effective over many months. That generosity lets an issuer's *earlier* scheme reach an
    unrelated later ex-date.

    RAYMOND is the real case, and it was missed by the self-alias check because the filing names a
    genuine, different resulting company rather than the filer itself:

    - ex-date **2024-07-11** -> "Raymond Lifestyle Limited", cited from filings of 2024-06-30 and
      2024-07-10 (1 and 11 days earlier). Correct.
    - ex-date **2025-05-14** -> the *same two filings*, 308 days earlier. That action is the Raymond
      **Realty** demerger, so the citation is wrong.

    The tie is broken on the temporal structure of a scheme rather than on a guess: a filing is
    followed by its own ex-date, so the row with the smallest non-negative ``ex_date - announced_on``
    keeps it and every other row citing the same attachment is blocked. A filing cited only by rows
    whose ex-dates all *precede* it keeps none, because then the ordering evidence is absent.
    """
    by_attachment: dict[tuple[str, str], list[tuple[int, dict[str, Any]]]] = {}
    for row in rows:
        for match in row["matches"]:
            attachment = match.get("attachment")
            if not attachment:
                continue
            by_attachment.setdefault((row["symbol"], str(attachment)), []).append((0, match))

    # Recompute the lag per (row, match) pair, since one match object belongs to exactly one row.
    lags: dict[int, int | None] = {}
    owner: dict[int, dict[str, Any]] = {}
    for row in rows:
        ex_date = date.fromisoformat(row["ex_date"])
        for match in row["matches"]:
            owner[id(match)] = row
            announced = match.get("announced_on")
            lags[id(match)] = (ex_date - date.fromisoformat(announced)).days if announced else None

    for (_symbol, _attachment), entries in by_attachment.items():
        claimants = [match for _, match in entries]
        if len({id(owner[id(m)]) for m in claimants}) < 2:
            continue  # only one ex-date cites this filing: nothing to arbitrate
        forward = [m for m in claimants if (lags[id(m)] or -1) >= 0]
        winner = min(forward, key=lambda m: lags[id(m)] or 0) if forward else None
        for match in claimants:
            if match is winner:
                continue
            match["flags"].append("FILING_BELONGS_TO_ANOTHER_EX_DATE")
            match["usable"] = False


def run(args: argparse.Namespace) -> int:
    refusals = json.loads(args.validated.read_text(encoding="utf-8"))["refused"]
    actions = sorted(
        {
            (item["symbol"], item["ex_date"])
            for item in refusals
            if item.get("reason") in ("NO_FILING_RATIO", "NO_EX_DATE_BAR")
        }
    )
    print(f"unresolved actions : {len(actions)}", flush=True)

    client = opener()
    by_symbol: dict[str, list[dict[str, Any]]] = {}
    results: list[dict[str, Any]] = []
    failures: list[dict[str, str]] = []

    for index, (symbol, ex_text) in enumerate(actions, 1):
        if symbol not in by_symbol:
            try:
                by_symbol[symbol] = fetch_announcements(client, symbol)
            except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, OSError) as error:
                by_symbol[symbol] = []
                failures.append({"symbol": symbol, "error": f"{type(error).__name__}: {error}"})
            time.sleep(args.pause)
        results.append(
            {
                "symbol": symbol,
                "ex_date": ex_text,
                "announcements_scanned": len(by_symbol[symbol]),
                "matches": scheme_matches(by_symbol[symbol], date.fromisoformat(ex_text)),
            }
        )
        if index % 10 == 0:
            print(f"  {index}/{len(actions)} actions", flush=True)

    # Cross-row arbitration must run before any row picks its answer: whether a match is usable
    # depends on what *other* ex-dates of the same issuer cite.
    _reject_filings_claimed_by_a_nearer_ex_date(results)
    for item in results:
        matches = item["matches"]
        usable = next((m for m in matches if m["usable"]), None)
        item["named_resulting_company"] = usable["resulting_company"] if usable else None
        item["name_flags"] = usable["flags"] if usable else []
        item["rejected_matches"] = sum(1 for m in matches if not m["usable"])
        item["matches"] = matches[: args.max_matches]

    named = sum(1 for item in results if item["named_resulting_company"])
    qualified = sum(1 for item in results if item["name_flags"])
    rejected = sum(item["rejected_matches"] for item in results)
    payload = {
        "generated_at": datetime.now(UTC).isoformat(),
        "source": "NSE corporate-announcements API (issuer filing text)",
        "what_this_supplies": "the resulting company named by the issuer",
        "what_this_does_not_supply": (
            "the share entitlement ratio, which lives in the PDF attachment and is NOT extracted "
            "here -- a misparsed ratio would produce a validated-looking factor that is wrong"
        ),
        "a_name_is_a_lead_not_a_factor": (
            "every name here still needs a human to open the attachment and confirm both the entity "
            "and the ratio; the search window spans +/-540 days and can admit a different scheme"
        ),
        "actions": len(results),
        "resulting_company_named": named,
        "named_with_qualifying_flags": qualified,
        "matches_rejected_as_unusable": rejected,
        "fetch_failures": failures,
        "results": results,
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")

    print(f"\nresulting company named: {named} of {len(results)}")
    print(f"  of those, flagged      : {qualified}")
    print(
        f"matches rejected         : {rejected} (degenerate, or the filer is itself the survivor)"
    )
    if failures:
        print(f"fetch failures         : {len(failures)}")
    print(f"written                : {args.out}")
    for item in results:
        if item["named_resulting_company"]:
            flags = f"  [{', '.join(item['name_flags'])}]" if item["name_flags"] else ""
            print(
                f"  {item['symbol']:12} {item['ex_date']} -> "
                f"{item['named_resulting_company']}{flags}"
            )
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--validated",
        type=Path,
        default=ROOT_DIR / "data/authorities/nse-validated-demerger-factors.json",
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=ROOT_DIR / "reports/corporate_action_validation/demerger-resulting-companies.json",
    )
    parser.add_argument("--pause", type=float, default=0.7)
    parser.add_argument("--max-matches", type=int, default=3)
    return run(parser.parse_args())


if __name__ == "__main__":
    raise SystemExit(main())
