"""Forward paper watch for the FROZEN XS-monthly rule (new stack, research only).

Frozen rule (identical constants to ``screen.py`` — tuning here is forbidden):
  score = trailing 21-session close momentum → top 20% → next-open entry →
  hold 21 sessions → exit at open, net of 0.224% round trip.

This module places no orders, imports no broker, no execution/paper path, no
server. It only computes signals from cached bars and tracks hypothetical
open/closed legs in a JSON state file the runner owns. Stdlib + bars/screen, and the
data-layer corporate-action finder shared with the flagship book.
"""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from datetime import date
from decimal import Decimal, localcontext
from pathlib import Path
from typing import Any, Final

from quant_system.data.held_corporate_actions import structural_actions_on_holdings
from quant_system.research_xs_monthly.bars import Bar
from quant_system.research_xs_monthly.screen import (
    COST_RATIO,
    FORMATION_SESSIONS,
    HOLD_SESSIONS,
    TOP_FRAC,
    WARMUP_SESSIONS,
    ScreenError,
    _index_symbol,
    build_calendar,
    formation_score,
    forward_net,
)

FROZEN_RULE: Final = {
    "formation_sessions": FORMATION_SESSIONS,
    "hold_sessions": HOLD_SESSIONS,
    "top_frac": str(TOP_FRAC),
    "cost_ratio": str(COST_RATIO),
}

#: Separate notional book for the XS-monthly watch. Display-only accounting:
#: no orders, no shared ledger, no touch on paper_pilot/paper_portfolio.
NOTIONAL_CAPITAL_INR: Final = Decimal("1000000")

#: Issuer-filed entitlement ratios for ratio-less NSE corporate actions. Read-only input, never
#: written here. See the file's own ``_comment`` for why a ratio may never be inferred from price.
ENTITLEMENT_AUTHORITY: Final = Path("data/authorities/nse-demerger-entitlements.json")

ENTITLEMENT_SCHEMA_ID: Final = "quantos.demerger_entitlements"


def load_unpriced_entitlements(
    positions: list[dict[str, Any]],
    bars_by_symbol: dict[str, list[Bar]],
    authority_path: Path = ENTITLEMENT_AUTHORITY,
) -> dict[str, str]:
    """Return ``{symbol: reason}`` for every held leg whose window spans a corporate action.

    A leg qualifies when the issuer filed an entitlement whose ex-date falls **after** that leg's
    entry — i.e. the book held the parent across the event and received something in exchange that
    ``shares * latest_open`` cannot express.

    Two distinct reasons come back, and the distinction matters:

    - the resulting company has no price in this repository, so the entitlement genuinely cannot be
      valued from available data;
    - the resulting company *is* priced, but this book represents a leg as one symbol and one share
      count, so it still cannot carry the second instrument.

    Both refuse to value the leg. The second is a stated limitation of this book rather than a gap in
    the data, and saying which one applies is the difference between "we cannot know" and "we have
    not built it".

    Fails closed. A missing or malformed authority raises rather than returning an empty map: an
    empty map is indistinguishable from "no corporate actions occurred", and quietly returning one is
    the exact shape of the defect this function exists to prevent (a fetch failure that wrote ``[]``
    and was then trusted forever — see ``CURRENT.md``, corporate-action authority repair ``ee1b0cb3``).
    """
    if not authority_path.is_file():
        raise ScreenError(f"MISSING_AUTHORITY: no entitlement authority at {authority_path}")
    try:
        payload = json.loads(authority_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ScreenError(f"BAD_AUTHORITY: {authority_path} is not valid JSON: {exc}") from exc
    if payload.get("schema_id") != ENTITLEMENT_SCHEMA_ID:
        raise ScreenError(
            f"BAD_AUTHORITY: {authority_path} schema_id "
            f"{payload.get('schema_id')!r} != {ENTITLEMENT_SCHEMA_ID!r}"
        )

    earliest_entry: dict[str, date] = {}
    for pos in positions:
        symbol = str(pos["symbol"])
        entry_date = date.fromisoformat(str(pos["entry_date"]))
        if symbol not in earliest_entry or entry_date < earliest_entry[symbol]:
            earliest_entry[symbol] = entry_date

    flagged: dict[str, str] = {}
    for entry in payload.get("entitlements", []):
        symbol = str(entry["symbol"])
        if symbol not in earliest_entry:
            continue
        ex_date = date.fromisoformat(str(entry["ex_date"]))
        if ex_date <= earliest_entry[symbol]:
            continue  # the event predates entry; the entry price already reflects it
        resulting = str(entry.get("resulting_symbol", ""))
        ratio = str(entry.get("ratio", "?"))
        resulting_bars = bars_by_symbol.get(resulting, [])
        if any(bar.exchange_date >= ex_date for bar in resulting_bars):
            flagged[symbol] = (
                f"ENTITLEMENT_NOT_REPRESENTABLE: held across {symbol} ex-date {ex_date.isoformat()}, "
                f"entitled to {ratio} x {resulting}. That company is priced here, but a leg in this "
                f"book carries one symbol and one share count and cannot hold the second instrument."
            )
        else:
            flagged[symbol] = (
                f"ENTITLEMENT_UNPRICED: held across {symbol} ex-date {ex_date.isoformat()}, entitled "
                f"to {ratio} x {resulting}, which has no price in this repository."
            )
    return flagged


def unreviewed_corporate_actions(
    positions: list[dict[str, Any]],
    records: Mapping[str, Sequence[Mapping[str, Any]]],
    asof: date,
) -> dict[str, str]:
    """``{symbol: reason}`` for legs held across a structural action no review has recorded.

    The entitlement authority is kept by hand and lists one demerger. This reads every split, bonus,
    consolidation, demerger and rights issue NSE published for the names held, from the records the
    scheduled refresh stores. A leg carried across one is declined a value, exactly as the HEG leg
    is, until a person reviews it with ``scripts/apply_paper_corporate_action.py --book xs``.

    A review is recorded on the leg itself under ``corporate_actions``, which is why
    ``settle_positions`` carries that key through every state: a leg that lost its record would be
    flagged again, and a second review of a split would apply it twice.
    """
    earliest: dict[str, date] = {}
    reviewed: set[tuple[str, date]] = set()
    for pos in positions:
        symbol = str(pos["symbol"])
        entry = date.fromisoformat(str(pos["entry_date"]))
        if symbol not in earliest or entry < earliest[symbol]:
            earliest[symbol] = entry
        for review in pos.get("corporate_actions", ()):
            reviewed.add((symbol, date.fromisoformat(str(review["ex_date"]))))
    flags: dict[str, str] = {}
    for action in structural_actions_on_holdings(earliest, asof, records, reviewed=reviewed):
        flags.setdefault(
            action.symbol,
            f"CORPORATE_ACTION_NOT_REVIEWED: {action.describe()}. Review it against the company's "
            "filing and record it with scripts/apply_paper_corporate_action.py --book xs.",
        )
    return flags


def size_positions(
    holdings: list[dict[str, Any]],
    capital: Decimal = NOTIONAL_CAPITAL_INR,
) -> tuple[list[dict[str, Any]], Decimal]:
    """Split capital equally across holdings into integer shares (NSE cash has
    no fractional shares). Returns (legs, cash_leftover)."""
    if not holdings:
        raise ScreenError("INSUFFICIENT_DATA: no holdings to size")
    if capital <= 0:
        raise ScreenError("BAD_PARAM: capital must be positive")
    per_leg = capital / Decimal(len(holdings))
    legs: list[dict[str, Any]] = []
    used = Decimal(0)
    for h in holdings:
        entry = Decimal(str(h["entry_open"]))
        shares = int(per_leg // entry)
        value = Decimal(shares) * entry
        used += value
        legs.append(
            {
                "symbol": h["symbol"],
                "entry_date": h["entry_date"],
                "entry_open": str(entry),
                "shares": shares,
                "entry_value": str(value),
            }
        )
    return legs, capital - used


def _book_closed(pos: dict[str, Any], exit_bar_open: Decimal) -> dict[str, Any]:
    """Cash fields for a closed leg. Cost = full round trip on entry notional,
    charged exactly once — same 0.224% model as the screen."""
    shares = int(pos.get("shares", 0))
    entry_open = Decimal(str(pos["entry_open"]))
    entry_value = Decimal(str(pos.get("entry_value", Decimal(shares) * entry_open)))
    with localcontext() as ctx:
        ctx.prec = 28
        exit_value = Decimal(shares) * exit_bar_open
        cost = COST_RATIO * entry_value
        proceeds = exit_value - cost
        net_cash = proceeds - entry_value
    return {
        "shares": shares,
        "entry_value": str(entry_value),
        "exit_open": str(exit_bar_open),
        "exit_value": str(exit_value),
        "cost": str(cost),
        "proceeds": str(proceeds),
        "net_cash": str(net_cash),
    }


def _book_open(
    pos: dict[str, Any], latest_open: Decimal, unpriced_reason: str | None = None
) -> dict[str, Any]:
    """Mark one open leg, or decline to mark it.

    ``unpriced_reason`` is set when a corporate action of unknown size falls inside the holding
    window. ``shares * latest_open`` is then **wrong**, and wrong in a specific direction: it
    multiplies the pre-event share count by the post-event quote, which silently asserts that
    whatever the holder received in exchange is worth nothing.

    HEG is the worked example. Its 2026-09-07 demerger entitled one resulting-company share per HEG
    share; the resulting company has no price anywhere in this repository. Marking 13 shares at the
    post-demerger quote booked roughly INR 6,084 of "loss" that no evidence supports -- larger than
    this book's entire displayed result at the time.

    So the leg comes back with ``unpriced: true``, its entry value stated, and **no**
    ``market_value`` or ``unrealized`` key at all. Omitting them rather than zeroing them is
    deliberate: a consumer that sums ``market_value`` now skips the leg or raises, instead of quietly
    treating an unvalued asset as worthless.
    """
    shares = int(pos.get("shares", 0))
    entry_value = Decimal(str(pos.get("entry_value", "0")))
    if unpriced_reason is not None:
        return {
            "shares": shares,
            "entry_value": str(entry_value),
            "unpriced": True,
            "unpriced_reason": unpriced_reason,
        }
    with localcontext() as ctx:
        ctx.prec = 28
        market_value = Decimal(shares) * latest_open
        unrealized = market_value - entry_value
    return {
        "shares": shares,
        "entry_value": str(entry_value),
        "market_value": str(market_value),
        "unrealized": str(unrealized),
    }


def latest_signal(
    bars_by_symbol: dict[str, list[Bar]],
    top_frac: Decimal = TOP_FRAC,
) -> dict[str, Any]:
    """Compute the latest complete rebalance signal.

    Decision date = last calendar session with a following session available
    for next-open entry. Holdings carry entry opens; locked entries are
    skipped and counted, never filled at a locked price.
    """
    if not bars_by_symbol:
        raise ScreenError("INSUFFICIENT_DATA: empty universe")
    calendar = build_calendar(bars_by_symbol)
    decision_pos = len(calendar) - 2  # entry open must exist at +1
    if decision_pos < WARMUP_SESSIONS - 1:
        raise ScreenError("INSUFFICIENT_DATA: no complete decision slot yet")
    indexed = {symbol: _index_symbol(bars) for symbol, bars in bars_by_symbol.items()}
    scored: list[tuple[str, Decimal]] = []
    for symbol, idx in indexed.items():
        score = formation_score(idx, calendar, decision_pos)
        if score is not None:
            scored.append((symbol, score))
    if not scored:
        raise ScreenError("INSUFFICIENT_DATA: no scored names at latest decision")
    scored.sort(key=lambda item: item[1], reverse=True)
    width = max(1, int(Decimal(len(scored)) * top_frac))
    entry_pos = decision_pos + 1
    holdings: list[dict[str, Any]] = []
    skipped_locked = 0
    skipped_missing = 0
    for symbol, score in scored[:width]:
        bar = indexed[symbol].get(calendar[entry_pos])
        if bar is None:
            skipped_missing += 1
            continue
        if bar.volume == 0 or bar.high == bar.low:
            skipped_locked += 1
            continue
        holdings.append(
            {
                "symbol": symbol,
                "score": str(score),
                "entry_date": calendar[entry_pos].isoformat(),
                "entry_open": str(bar.open),
            }
        )
    return {
        "rule": FROZEN_RULE,
        "decision_date": calendar[decision_pos].isoformat(),
        "entry_date": calendar[entry_pos].isoformat(),
        "calendar_end": calendar[-1].isoformat(),
        "scored_names": len(scored),
        "holdings": holdings,
        "skipped_locked": skipped_locked,
        "skipped_missing": skipped_missing,
    }


def settle_positions(
    positions: list[dict[str, Any]],
    bars_by_symbol: dict[str, list[Bar]],
    hold: int = HOLD_SESSIONS,
    unpriced_entitlements: dict[str, str] | None = None,
) -> dict[str, Any]:
    """Split positions into closed legs vs open marks at the latest bar.

    Closed leg: exit open exists hold sessions after entry → full COST_RATIO
    charged exactly once. Open leg: marked gross at the latest available open,
    cost pending, never deducted early.

    ``unpriced_entitlements`` maps a symbol to the reason its holding cannot be valued -- a corporate
    action of unknown size inside the window. Those legs come back marked ``unpriced`` instead of
    valued at ``shares * latest_open``, which would assert the entitlement is worthless. Defaults to
    empty, so existing callers are unaffected. See :func:`_book_open`.

    A flagged leg is refused at **both** ends of its life. While it is held it is marked ``unpriced``;
    when its hold matures it goes to ``unresolved`` rather than ``closed``, because closing it would
    run the same false quote through ``forward_net`` and convert an unevidenced mark into realized
    cash. An unresolved leg pays no proceeds -- the capital stays committed and unvaluable, which is
    what actually happened.

    It must leave ``open`` all the same. The runner opens new positions only when the book is flat,
    so a leg that stayed open forever would silently stop the book rebalancing: a worse failure than
    the mispricing this function exists to prevent.
    """
    unpriced = unpriced_entitlements or {}
    calendar = build_calendar(bars_by_symbol)
    indexed = {symbol: _index_symbol(bars) for symbol, bars in bars_by_symbol.items()}
    pos_of = {d: i for i, d in enumerate(calendar)}
    closed: list[dict[str, Any]] = []
    opened: list[dict[str, Any]] = []
    unresolved: list[dict[str, Any]] = []
    for pos in positions:
        symbol = pos["symbol"]
        entry_open = Decimal(str(pos["entry_open"]))
        entry_date = date.fromisoformat(str(pos["entry_date"]))
        idx = indexed.get(symbol, {})
        if entry_date not in pos_of:
            continue
        exit_pos = pos_of[entry_date] + hold
        reason = unpriced.get(symbol)
        if reason is not None and exit_pos < len(calendar):
            matured: dict[str, Any] = {
                "symbol": symbol,
                "entry_date": pos["entry_date"],
                "entry_open": str(entry_open),
                "matured_on": calendar[exit_pos].isoformat(),
                "shares": int(pos.get("shares", 0)),
                "entry_value": str(pos.get("entry_value", "0")),
                "unpriced": True,
                "unpriced_reason": reason,
            }
            _carry_reviews(pos, matured)
            unresolved.append(matured)
            continue
        if exit_pos < len(calendar):
            net, locked = forward_net(idx, calendar, pos_of[entry_date], exit_pos)
            if net is None:
                if locked:
                    continue  # locked exit: leg stays pending, never forced
                continue
            leg = {
                "symbol": symbol,
                "entry_date": pos["entry_date"],
                "exit_date": calendar[exit_pos].isoformat(),
                "entry_open": str(entry_open),
                "net": str(net),
            }
            if "shares" in pos:
                exit_bar = idx.get(calendar[exit_pos])
                if exit_bar is not None:
                    leg.update(_book_closed(pos, exit_bar.open))
            _carry_reviews(pos, leg)
            closed.append(leg)
        else:
            latest_bar = idx.get(calendar[-1])
            if latest_bar is None or entry_open <= 0:
                continue
            with localcontext() as ctx:
                ctx.prec = 28
                gross = (latest_bar.open - entry_open) / entry_open
            leg = {
                "symbol": symbol,
                "entry_date": pos["entry_date"],
                "entry_open": str(entry_open),
                "asof_date": calendar[-1].isoformat(),
                "gross_mark": str(gross),
                "cost_pending": str(COST_RATIO),
            }
            if reason is not None:
                # gross_mark is a price ratio carrying the same false assertion as market_value, so
                # it is removed rather than left where a reader would take it for a return.
                leg.pop("gross_mark", None)
                leg["unpriced"] = True
                leg["unpriced_reason"] = reason
            if "shares" in pos:
                leg.update(_book_open(pos, latest_bar.open, reason))
            _carry_reviews(pos, leg)
            opened.append(leg)
    return {
        "closed": closed,
        "open": opened,
        "unresolved": unresolved,
        "asof": calendar[-1].isoformat(),
    }


def _carry_reviews(pos: dict[str, Any], leg: dict[str, Any]) -> None:
    """Keep a leg's corporate-action reviews on whatever settling makes of it."""
    if "corporate_actions" in pos:
        leg["corporate_actions"] = list(pos["corporate_actions"])


def book_value(
    open_legs: list[dict[str, Any]],
    unresolved_legs: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Split a book's holdings into what can be valued and what cannot.

    Returns ``priced_market_value`` (the sum over legs that carry a ``market_value``),
    ``unpriced_at_cost`` (the entry consideration still committed to holdings nobody can value) and
    ``unpriced`` (those holdings, named, with their reasons).

    The two are deliberately never added together. Folding an unvaluable holding in at cost asserts
    it broke even; leaving it out of a single headline number asserts it is worthless. Both are
    claims no evidence supports, so the caller is handed the parts and required to say which it is
    showing.

    This is also why the sum here reads ``leg["market_value"]`` rather than
    ``leg.get("market_value", 0)``. A missing value is not zero, and the defaulting idiom is what
    turned an unpriced HEG entitlement into a INR 6,124.30 loss in the first place.
    """
    priced = Decimal(0)
    unpriced: list[dict[str, Any]] = []
    for leg in open_legs:
        if leg.get("unpriced") or "market_value" not in leg:
            unpriced.append(leg)
            continue
        priced += Decimal(str(leg["market_value"]))
    unpriced.extend(unresolved_legs or [])
    at_cost = sum(
        (Decimal(str(leg.get("entry_value", "0"))) for leg in unpriced),
        Decimal(0),
    )
    return {
        "priced_market_value": priced,
        "unpriced_at_cost": at_cost,
        "unpriced": [
            {
                "symbol": leg["symbol"],
                "shares": leg.get("shares"),
                "entry_value": str(leg.get("entry_value", "0")),
                "reason": leg.get("unpriced_reason", "UNPRICED: no market_value on this leg"),
            }
            for leg in unpriced
        ],
    }
