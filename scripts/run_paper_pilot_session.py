"""QuantOS Quote-Driven Paper Pilot Execution & Feedback Runner.

Drives a realistic paper trading session using the flagship Mīzān cross-sectional
alpha model, executing simulated paper orders with order book depth matching,
conservative adverse slippage, pre-trade risk gating, and exact statutory NSE
transaction costs (STT, exchange turnover charges, SEBI charges, GST, stamp duty).

All operations, timestamps, and reports are formatted and recorded in Indian Standard Time (IST).
Runs continuously from current time until market close (15:30 IST) with penny-exact reconciliation.
"""

from __future__ import annotations

import argparse
import base64
import csv
import json
import logging
import os
import signal
import sys
import time
from collections.abc import Callable, Mapping
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

# Ensure src is on sys.path and load .env automatically
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT / "src") not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT / "src"))

env_file = PROJECT_ROOT / ".env"
if env_file.exists():
    for line in env_file.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if "=" in line and not line.startswith("#"):
            k, v = line.split("=", 1)
            k = k.strip()
            v = v.strip().strip("'\"")
            if k and k not in os.environ:
                os.environ[k] = v

from quant_system.core.domain import (  # noqa: E402
    OrderType,
    Quote,
    Side,
)
from quant_system.execution.orderbook_sim import (  # noqa: E402
    OrderBookSimConfig,
    OrderBookSnapshot,
)
from quant_system.execution.paper_pilot import (  # noqa: E402
    PaperPilotEngine,
    PaperProposal,
)
from quant_system.risk.checks import RiskLimits  # noqa: E402
from quant_system.risk.governor import PreTradeRiskGovernor  # noqa: E402

# Indian Standard Time (UTC+05:30)
_IST = timezone(timedelta(hours=5, minutes=30), name="IST")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s IST [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("quant_system.paper_runner")

_PAISA = Decimal("0.01")


#: Consecutive failed quote polls before the session gives up. At a 30-second interval this is
#: about two and a half minutes of silence -- long enough to ride out a handshake timeout or a
#: transient DNS failure, short enough that a genuinely dead feed does not leave the book marked to
#: stale prices for the rest of the day.
MAX_CONSECUTIVE_QUOTE_FAILURES = 5

#: How much of the selection the book must actually hold for a rebalance to count as executed.
#:
#: `bool(entry_fills)` was satisfied by **one** fill. A rebalance that sold the old book and then
#: bought one name of four left 76.3% in cash, paid Rs 1,115.75 to get there, reset the hold clock
#: and reported success -- a portfolio the screen never models, recorded as the one it does.
#:
#: Not 1.0: integer share truncation legitimately drops the most expensive names, and on
#: 2026-08-31 three of a hundred picks were skipped because one share cost more than the
#: allocation. 0.8 tolerates that and refuses a book that is mostly cash.
MIN_REBALANCE_COVERAGE = 0.8

#: Per-batch HTTP timeout. Was 3 seconds for a 100-instrument request, which made handshake
#: timeouts an ordinary event rather than a signal.
_QUOTE_TIMEOUT_SECONDS = 15


class QuoteFeedError(RuntimeError):
    """The exchange feed is unusable, so the session must not trade.

    Raised rather than falling back. This pilot has exactly one quote source by instruction, and a
    session priced from anything else is not a record of what the model would have done.
    """


#: Environment variables carrying a quote credential, in resolution order.
#:
#: The analytics token is preferred because it is the only one that survives a night. Upstox
#: issues it free, one per user, for roughly a year; the standard access token expires at 03:30
#: IST the morning after issue and Upstox V2 has no refresh token, so it must be renewed by hand
#: every trading day. An unattended schedule that dies whenever the operator forgets a manual step
#: is not an unattended schedule.
#:
#: That the analytics token can actually serve this file's quote calls is measured, not assumed --
#: `v2/market-quote/quotes` returned HTTP 200 for a 10-instrument batch, with depth and volume, on
#: 2026-08-31. Evidence: `agent_context/work/active/20260831-claude-upstox-token-semantics.md`.
_TOKEN_ENV_VARS = ("UPSTOX_ANALYTICS_TOKEN", "UPSTOX_ACCESS_TOKEN")


def resolve_upstox_token(access_token: str | None = None) -> tuple[str, str]:
    """Return the quote credential and the name of where it came from.

    An explicit argument wins, so `--upstox-token` and the `upstox_token=` parameter keep their
    existing override behaviour. Otherwise the environment is searched in `_TOKEN_ENV_VARS` order.
    The source name is returned rather than discarded so that every downstream error can say which
    token it is talking about -- an operator with two tokens configured cannot act on a message
    that does not name one.
    """
    if access_token:
        return access_token, "explicit --upstox-token"
    for name in _TOKEN_ENV_VARS:
        value = os.getenv(name, "")
        if value:
            return value, name
    return "", ""


def assert_upstox_usable(access_token: str | None = None) -> None:
    """Fail at startup if the token is absent, malformed or expired.

    The runner used to log "Upstox API Token : CONFIGURED" whenever the string was non-empty. The
    token expired on 2026-08-23 and every session for eight days ran on a fallback feed under that
    banner. Presence is not validity, and an unattended schedule has nobody to notice the
    difference -- so the expiry claim the token carries is read and checked.

    The check applies to whichever token was selected. A long-lived analytics token is validated
    by exactly the same rule as a daily access token: the guard reads the `exp` the token itself
    carries, so it needs no knowledge of which class it is looking at, and a revoked or
    mis-pasted analytics token is caught just as an expired access token is.
    """
    token, source = resolve_upstox_token(access_token)
    if not token:
        raise QuoteFeedError(
            f"no Upstox token. Set one of {' or '.join(_TOKEN_ENV_VARS)} in .env. "
            "UPSTOX_ANALYTICS_TOKEN is preferred: it is free, one per user, and lasts about a "
            "year, so an unattended session survives a morning you forget to refresh."
        )
    parts = token.split(".")
    if len(parts) != 3:
        raise QuoteFeedError(f"{source} is not a JWT; it cannot be an Upstox token")
    payload = parts[1] + "=" * (-len(parts[1]) % 4)
    try:
        claims = json.loads(base64.urlsafe_b64decode(payload))
    except Exception as error:
        raise QuoteFeedError(f"{source} payload is unreadable: {error}") from error
    expiry = claims.get("exp")
    if expiry is None:
        raise QuoteFeedError(f"{source} carries no expiry claim")
    expires_at = datetime.fromtimestamp(int(expiry), _IST)
    if expires_at <= now_ist():
        others = [n for n in _TOKEN_ENV_VARS if n != source]
        raise QuoteFeedError(
            f"{source} expired at {expires_at:%Y-%m-%d %H:%M IST}, "
            f"{now_ist() - expires_at} ago. Upstox standard access tokens expire at 03:30 IST the "
            "morning after they are issued. Set UPSTOX_ANALYTICS_TOKEN instead -- it is free, one "
            "per user, and lasts about a year. "
            f"({' and '.join(others)} was not set or was not reached.) "
            "There is no second feed to fall back to."
        )
    logger.info(
        "Upstox token source %s, valid until %s", source, f"{expires_at:%Y-%m-%d %H:%M IST}"
    )


def _paisa_str(val: Decimal | float | int) -> str:
    return f"{Decimal(str(val)).quantize(_PAISA)}"


def marks_for_open_positions(
    quoted: dict[str, Decimal],
    positions: Mapping[str, Any],
) -> tuple[dict[str, Decimal], list[str]]:
    """Closing marks covering every held name, and the names that had no quote.

    `DecimalLedger` refuses to mark a held position it has no price for, rather than substituting
    an average and reporting a fabricated market value. That refusal is right, and it made a held
    name absent from the feed fatal: `end_session` raised **after** a full day of trading, before
    `save_portfolio`, and outside the abort handler -- so the day's fills happened, no report was
    written and no state was saved. Two of five hundred names were unquoted on 2026-08-31 and 97
    are now held.

    A position that must be marked and cannot be is marked at its own cost basis, which reports
    zero unrealized P&L for it rather than a number nobody can source. The names are returned so
    the session says which marks are real, instead of the caller silently believing all of them.
    """
    marks = dict(quoted)
    fell_back: list[str] = []
    for symbol, position in positions.items():
        if position.quantity != 0 and symbol not in marks:
            marks[symbol] = position.average_price
            fell_back.append(symbol)
    return marks, sorted(fell_back)


def rebalance_executed(
    selected: set[str],
    held: set[str],
    minimum: float = MIN_REBALANCE_COVERAGE,
) -> bool:
    """Whether the book became the selection the model chose.

    The flag this replaces was `bool(entry_fills)`, satisfied by **one** fill: a rebalance that sold
    the old book and bought one name of four left 76.3% in cash, paid Rs 1,115.75 to get there,
    reset the hold clock and reported success. Before that it was `total_fills_count > 0`, satisfied
    by the exits alone.

    Coverage asks the question the flag is actually for, and answers it the same way for every shape
    that matters: an all-exits rebalance covers 0.0, one entry of four covers 0.25, a re-rank that
    keeps everything covers 1.0, and a hundred picks with three names too expensive to buy a single
    share of covers 0.97.
    """
    if not selected:
        return False
    return len(held & selected) / len(selected) >= minimum


def equity_marked_at(
    cash: Decimal,
    positions: Mapping[str, Any],
    marks: Mapping[str, Decimal],
) -> Decimal:
    """Equity valued at the supplied marks, falling back to each position's own cost.

    The daily drawdown baseline. Computed from the boot-time quote map it is the *previous close*,
    which turned an overnight gap into a "daily" drawdown with no intraday movement -- the 4% rule
    firing on the first order, which is the exit. Extracted so a test can drive the gap rather than
    read the line that computes it: four of five tests written for the last round were functions of
    the source text, and thirteen independent mutants walked through all of them.
    """
    return (
        cash
        + sum(
            (
                Decimal(position.quantity) * marks.get(symbol, position.average_price)
                for symbol, position in positions.items()
            ),
            Decimal("0.00"),
        )
    ).quantize(_PAISA)


def anchor_to_reuse(portfolio: PaperPortfolioState, session_date: date) -> Decimal | None:
    """The drawdown baseline already recorded for `session_date`, or None to take a fresh one.

    A restart within the same session must reuse the morning's baseline; a new session must not.
    Extracted because a guard's *presence* is checkable from the source and its *effectiveness* is
    not: `daily_anchor_on != session_date` keeps every string a located assertion looks for while
    inverting the decision, and that mutant survived until this could be driven.
    """
    if portfolio.daily_anchor_on != session_date:
        return None
    if portfolio.daily_anchor_equity <= 0:
        return None
    return portfolio.daily_anchor_equity


def entry_quantity(
    symbol: str,
    marks: Mapping[str, Decimal],
    allocation: Decimal,
    available_cash: Decimal,
) -> int:
    """Shares to buy for one selected name, or zero when it cannot be sized.

    Zero for a name the feed did not return: there is no price to size against and inventing one is
    what removing the fallback price table was for. Zero also when a single share costs more than
    the allocation, which is how the priciest names drop out under equal weighting.
    """
    price = marks.get(symbol)
    if price is None or price <= 0:
        return 0
    target = min(allocation, available_cash * Decimal("0.95"))
    return int(target / price)


def _positive_price(value: object) -> Decimal | None:
    """`value` as a paisa-quantised price, or None when it is not a usable one.

    Rejects None, non-numeric types, zero, negatives and non-finite floats. A quote field is
    provider data: it is whatever arrived, not whatever the type hints say should have.
    """
    if isinstance(value, bool) or not isinstance(value, int | float | str | Decimal):
        return None
    try:
        price = Decimal(str(value))
    except (InvalidOperation, ValueError):
        return None
    if not price.is_finite() or price <= 0:
        return None
    return price.quantize(_PAISA)


def parse_quote_payload(quote_data: Mapping[str, Any]) -> dict[str, Any] | None:
    """One symbol's market data, or None when the payload cannot yield a usable price.

    `last_price` used to be read as `.get("last_price", 0)` and stamped `UPSTOX_LIVE_FEED`, so a
    quote carrying `last_price: 0` -- or carrying none at all -- became a **real exchange price of
    Rs 0.00**. For a held name that silently removes its whole value from the marked equity, the
    risk baseline and the session report at once.

    Depth prices are validated for the same reason from the other direction: a negative bid reaches
    `OrderBookSnapshot.from_levels`, which correctly refuses it with `ValueError: Depth price must
    be positive` -- and that exception aborts the entire session over one bad name in five hundred.
    A level that cannot be priced is dropped here rather than allowed to end the day.

    Returning None puts the symbol in exactly the position of one the feed never returned, which is
    a case every caller already handles.
    """
    if not quote_data:
        return None
    price = _positive_price(quote_data.get("last_price"))
    if price is None:
        return None

    ohlc = quote_data.get("ohlc") or {}
    high = _positive_price(ohlc.get("high")) or price
    low = _positive_price(ohlc.get("low")) or price
    prev_close = _positive_price(ohlc.get("close")) or price

    raw_volume = quote_data.get("volume")
    volume = raw_volume if isinstance(raw_volume, int) and not isinstance(raw_volume, bool) else 0
    volume = max(0, volume)

    depth_info = quote_data.get("depth") or {}
    best_bid = _best_depth_price(depth_info.get("buy"))
    best_ask = _best_depth_price(depth_info.get("sell"))
    spread = Decimal("0.05")
    if best_bid is not None and best_ask is not None and best_ask > best_bid:
        spread = max(Decimal("0.05"), (best_ask - best_bid).quantize(_PAISA))

    return {
        "price": price,
        "high": high,
        "low": low,
        "previous_close": prev_close,
        "volume": volume,
        "spread": spread,
        "depth": max(100, volume // 5000),
        "source": "UPSTOX_LIVE_FEED",
    }


def _best_depth_price(levels: object) -> Decimal | None:
    """The best usable price in a depth ladder, skipping levels that cannot be priced."""
    if not isinstance(levels, list):
        return None
    for level in levels:
        if isinstance(level, Mapping):
            price = _positive_price(level.get("price"))
            if price is not None:
                return price
    return None


def fetch_quotes_with_retry(
    universe: list[str],
    access_token: str | None,
    attempts: int = MAX_CONSECUTIVE_QUOTE_FAILURES,
    delay_seconds: float = 5.0,
    fetch: Callable[..., dict[str, Any]] | None = None,
    sleep: Callable[[float], None] = time.sleep,
) -> dict[str, Any]:
    """The opening quote fetch, with the retry budget the trading loop already had.

    The loop tolerates `MAX_CONSECUTIVE_QUOTE_FAILURES` consecutive failed polls before ending the
    session. Startup tolerated none: one chunk of five timing out during the handshake raised, and
    the whole trading day was lost before a single decision was taken. A handshake timeout is
    exactly the failure that ended the 2026-08-31 session.

    A transient failure at 09:00 is not more meaningful than the same failure at 09:05. The budget
    is the same on both sides of the loop boundary.

    `sleep` is injected so a test can drive the retry without spending real seconds; sleeping in a
    test is a flakiness risk this repository counts as a craft defect.
    """
    fetch = fetch or fetch_upstox_live_quotes
    last_error: QuoteFeedError | None = None
    for attempt in range(1, max(1, attempts) + 1):
        try:
            return fetch(universe, access_token=access_token)
        except QuoteFeedError as err:
            last_error = err
            if attempt >= max(1, attempts):
                break
            logger.warning(
                "Opening quote fetch failed on attempt %d of %d (%s); retrying in %.1fs.",
                attempt,
                attempts,
                err,
                delay_seconds,
            )
            sleep(delay_seconds)

    assert last_error is not None  # the loop either returned or recorded an error
    raise QuoteFeedError(
        f"the opening quote fetch failed {attempts} times in a row (last: {last_error}). "
        "Refusing to open a session with no marks."
    ) from last_error


def flat_book_alarm(opened_holding: int, exit_fills: int, exit_fees: Decimal) -> str:
    """What to tell the operator about a rebalance that ended with an empty book.

    The one message this used to print stated a financial event: *"every exit filled and no entry
    did. A full exit round trip was paid."* On a first session that started flat and could not
    enter, no exit filled and nothing was paid. On an unattended schedule this is the operator's
    alarm text, and it described a loss that had not occurred.

    Both endings are worth an alarm. They are not the same alarm, and the difference is whether
    money left the account.
    """
    if opened_holding and exit_fills:
        return (
            f"The book is FLAT after a rebalance: {exit_fills} exit(s) filled and no entry did. "
            f"Rs {exit_fees} of exit costs was paid to reach a state the screen never models. "
            "Investigate before the next rebalance rather than letting it repeat."
        )
    if opened_holding:
        return (
            "The book is FLAT after a rebalance, and it did not get there by selling: the session "
            f"opened holding {opened_holding} name(s) and no exit filled. The positions are gone "
            "from the ledger without a fill that removed them, which is a reconciliation question "
            "before it is a trading one."
        )
    return (
        "The book is FLAT after a rebalance: the session opened flat and no entry filled, so "
        "nothing was bought and nothing was paid. The selection could not be executed at all -- "
        "check sizing, cash buffer and rejected orders rather than looking for a loss."
    )


def now_ist() -> datetime:
    return datetime.now(_IST)


import os  # noqa: E402
import urllib.request  # noqa: E402

from quant_system.data.universe import NIFTY50_SYMBOLS  # noqa: E402

ALLOWED_SYMBOLS = NIFTY50_SYMBOLS

#: Symbol -> Upstox instrument key, resolved from the published NSE authority.
#:
#: What stood here was a dict of **ten** hardcoded symbols, with every other name falling back to
#: `f"NSE_EQ|{symbol}"`. Upstox instrument keys are ISIN-based -- `NSE_EQ|INE009A01021`, not
#: `NSE_EQ|INFY` -- so that fallback was never a valid key and those names could not be quoted. On a
#: 500-name universe Upstox returned 5.
#:
#: It was invisible because the Yahoo scraper fired whenever fewer than half the symbols resolved,
#: which was always. **Upstox has never actually served this pilot**; removing the fallback is what
#: exposed it.
_INSTRUMENT_KEY_AUTHORITY = PROJECT_ROOT / "data/authorities/nse-all-listed-equities.csv"


def _load_instrument_keys() -> dict[str, str]:
    """Every NSE equity's Upstox instrument key, by trading symbol."""
    with open(_INSTRUMENT_KEY_AUTHORITY, encoding="utf-8-sig") as handle:
        return {
            (row.get("Symbol") or "").strip(): (row.get("Instrument Key") or "").strip()
            for row in csv.DictReader(handle)
            if (row.get("Instrument Key") or "").startswith("NSE_EQ|")
        }


UPSTOX_INSTRUMENT_KEYS: dict[str, str] = _load_instrument_keys()


import urllib.parse  # noqa: E402

#: There is no secondary quote source, by explicit instruction: this pilot uses Upstox or it does
#: not trade. What stood here was a Yahoo Finance scraper plus a table of hardcoded prices, and any
#: name missing from both was priced at a flat Rs 1000.00 and labelled "REAL_NSE_ESTIMATE".
#:
#: It mattered. The Upstox token expired on 2026-08-23 and every session since ran entirely on the
#: fallback while the log printed "Upstox API Token : CONFIGURED", because the check tested that the
#: string was present rather than that it worked. A record whose provenance is not what it claims is
#: worse than no record.


def fetch_upstox_live_quotes(
    symbols: list[str], access_token: str | None = None
) -> dict[str, dict[str, Any]]:
    """Fetch real-time live market quotes directly from Upstox Market Quote API in high-speed batches."""
    token, source = resolve_upstox_token(access_token)
    if not token:
        raise QuoteFeedError(
            f"no Upstox token ({' or '.join(_TOKEN_ENV_VARS)}). This pilot has one quote source "
            "and will not substitute another; set the token and re-run."
        )
    del source  # resolved for symmetry with the startup guard; the request needs only the value

    results = {}
    failed_chunks: list[tuple[int, str]] = []
    unpriced: list[str] = []
    chunk_size = 100
    chunk_count = (len(symbols) + chunk_size - 1) // chunk_size
    for i in range(0, len(symbols), chunk_size):
        chunk_syms = symbols[i : i + chunk_size]
        resolved = {s: UPSTOX_INSTRUMENT_KEYS[s] for s in chunk_syms if s in UPSTOX_INSTRUMENT_KEYS}
        unknown = [s for s in chunk_syms if s not in UPSTOX_INSTRUMENT_KEYS]
        if unknown:
            logger.warning(
                "No published Upstox instrument key for %d symbol(s); not requested: %s",
                len(unknown),
                ", ".join(unknown[:10]) + (" ..." if len(unknown) > 10 else ""),
            )
        if not resolved:
            continue
        keys = list(resolved.values())
        encoded_keys = ",".join(keys)
        url = f"https://api.upstox.com/v2/market-quote/quotes?instrument_key={encoded_keys}"

        headers = {
            "Accept": "application/json",
            "Authorization": f"Bearer {token}",
            "User-Agent": "QuantOS/1.0",
        }

        try:
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, timeout=_QUOTE_TIMEOUT_SECONDS) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                # A 200 carrying something other than a success envelope is a failed chunk, not an
                # empty one. This used to fall through silently: the `if` simply did not match, the
                # loop moved on, and the poll returned whatever the other chunks had -- so the
                # consecutive-failure counter reset on the very poll that lost 100 of 150 symbols.
                # An error body, a rate-limit envelope and a truncated response all land here.
                if data.get("status") != "success" or "data" not in data:
                    raise QuoteFeedError(
                        f"Upstox returned HTTP 200 without a success payload "
                        f"(status={data.get('status')!r}, keys={sorted(data)[:5]})"
                    )
                payload = data["data"]
                for sym, key in resolved.items():
                    alt_key = f"NSE_EQ:{sym}"
                    quote_data = payload.get(key) or payload.get(alt_key) or {}
                    parsed = parse_quote_payload(quote_data)
                    if parsed is not None:
                        results[sym] = parsed
                    elif quote_data:
                        # A payload arrived and could not be priced. Skipping is the same
                        # treatment a name the feed never returned already gets; the alternative
                        # is stamping Rs 0.00 as a real exchange price.
                        unpriced.append(sym)
        except Exception as err:
            # Counted, and the remaining chunks are still attempted: one bad request should not
            # discard the batches that would have succeeded.
            failed_chunks.append((i // chunk_size, str(err)))
            logger.warning(
                "Upstox batch quote fetch failed for chunk %d (%s).", i // chunk_size, err
            )
            continue

    # A transport failure is a failed poll, even when other chunks succeeded.
    #
    # This used to raise only when it got **nothing**, so a poll that lost a chunk returned
    # normally and the caller reset its consecutive-failure counter. Two chunks failed live on
    # 2026-08-31 at 13:29 and 13:44 -- 300 of 500 symbols missing, twice -- and the session carried
    # on pricing the absent names from quotes minutes old, because the previous values simply
    # stayed in `base_market`.
    #
    # The distinction that matters is *why* a symbol is absent. A chunk that errored tells us
    # nothing about its symbols and must be retried; a symbol missing from a response that
    # otherwise succeeded is genuinely unquotable right now, and no amount of retrying changes it.
    # Only the first is a failure of the poll.
    if failed_chunks:
        raise QuoteFeedError(
            f"{len(failed_chunks)} of {chunk_count} quote batches failed; "
            f"{len(results)} of {len(symbols)} symbols returned. First error: "
            f"{failed_chunks[0][1]}"
        )

    if unpriced:
        # Visible, because these names are absent from the marks for the rest of the session and
        # nothing downstream can distinguish "the feed skipped it" from "we refused its payload".
        logger.warning(
            "%d of %d symbols returned a payload that could not be priced and were skipped: %s",
            len(unpriced),
            len(symbols),
            ", ".join(sorted(unpriced)[:10]),
        )

    if not results:
        raise QuoteFeedError(
            f"Upstox returned no quotes for any of {len(symbols)} symbols. Refusing to trade: a "
            "session priced from anything other than the exchange feed is not a record of what "
            "this model would have done."
        )
    missing = sorted(set(symbols) - set(results))
    if missing:
        # Reported, not filled in. These are symbols the exchange did not return in a response
        # that otherwise succeeded -- genuinely unquotable right now, not a transport failure, which
        # is handled above. Inventing a price for them is how a fabricated quote reaches a decision.
        #
        # An earlier version of this comment claimed "the coverage gate downstream already refuses
        # a shrunk one". No such gate exists on this path: the coverage minimum applies to the
        # feature cross-section built from daily bars, not to an intraday quote poll.
        logger.warning(
            "Upstox returned no quote for %d of %d symbols; they are omitted, not estimated: %s",
            len(missing),
            len(symbols),
            ", ".join(missing[:10]) + (" ..." if len(missing) > 10 else ""),
        )

    return results


sys.path.insert(0, str(PROJECT_ROOT / "scripts"))
from collections.abc import Sequence  # noqa: E402

from cached_nifty50_evidence import historical_acquisition_from_verified  # noqa: E402

from quant_system.data.universe import (  # noqa: E402
    NIFTY50_SYMBOLS,
    NIFTY500_SYMBOLS,
    get_universe_symbols,
)
from quant_system.evidence import (  # noqa: E402
    EvidenceResourceType,
    EvidenceStore,
    EvidenceStoreConfig,
)
from quant_system.execution.governed_strategy import ExecutionSurface  # noqa: E402
from quant_system.execution.mizan_execution import (  # noqa: E402
    PAPER_OBSERVATION_EXEMPTION,
    load_mizan_for_execution,
)
from quant_system.execution.mizan_live_features import (  # noqa: E402
    CrossSectionCoverage,
    build_live_cross_section,
    refuse_extreme_rows,
    select_top_fraction,
)
from quant_system.execution.paper_portfolio import (  # noqa: E402
    PaperPortfolioError,
    PaperPortfolioState,
    load_portfolio,
    save_portfolio,
    state_from_ledger,
    state_hash_on_disk,
)

ALLOWED_SYMBOLS = NIFTY500_SYMBOLS

#: A cross-sectional rank divides by the number of names present, so a shrunk cross-section changes
#: every rank. Below this the session refuses to trade rather than ranking whatever it could load.
MIN_CROSS_SECTION_COVERAGE = 0.90

#: Where the running portfolio persists between sessions. A single file, hash-checked, so an
#: unattended weekday schedule resumes from real state or refuses outright.
PORTFOLIO_STATE_PATH = PROJECT_ROOT / "logs/paper_runs/portfolio_state.json"

#: Caches searched for completed daily bars, cheapest first.
_BAR_CACHES = (
    # Freshest first. The refresh cache is rebuilt by `ingest_all_market_data.py` and carries the
    # most recent completed sessions; the older stores are the fallback and stop at 2026-08-21.
    PROJECT_ROOT / "data/evidence/market-cache/nifty500-refresh-20230828-20260827/store",
    PROJECT_ROOT / "data/evidence/market-cache/nifty50-refresh-20230828-20260827/store",
    PROJECT_ROOT / "data/evidence/market-cache/nifty50-current-20160822-20260821/store",
    PROJECT_ROOT / "data/evidence/market-cache/all-market-20160822-20260821/store",
)
#: Macro is searched freshest-first for the same reason as the bar caches: the original store
#: stops at 2026-08-21, and a decision date past that leaves every row uncomputable.
_MACRO_DIRS = (
    PROJECT_ROOT / "data/evidence/market-cache/macro-refresh-20230828-20260827",
    PROJECT_ROOT / "data/evidence/market-cache/macro-regimes-20160822-20260821",
)


#: Index constituents by name, as published authorities rather than hardcoded lists.
#:
#: `quant_system.data.universe` carries the index memberships as literals and they have drifted:
#: NIFTY50_SYMBOLS is 5 names stale, and NIFTY500_SYMBOLS holds 488 names of which 167 are no longer
#: in the index while 179 current members are absent. Trading the literal list means holding names
#: that left the index and missing ones that joined.
_UNIVERSE_AUTHORITIES = {
    "NIFTY50": PROJECT_ROOT / "data/authorities/nse-nifty50-constituents.csv",
    "NIFTY500": PROJECT_ROOT / "data/authorities/nse-nifty500-constituents.csv",
}


def resolve_universe(universe_name: str) -> list[str]:
    """Index members from the published authority, falling back to the in-code list.

    The fallback is deliberate rather than silent: an authority file that is missing is a real
    condition, and refusing outright would strand a caller asking for an index that has no CSV.
    The chosen source is logged so a session's universe is always attributable.
    """
    authority = _UNIVERSE_AUTHORITIES.get(universe_name.upper())
    if authority is not None and authority.is_file():
        with open(authority, encoding="utf-8-sig") as handle:
            symbols = sorted(
                {
                    (row.get("Symbol") or "").strip()
                    for row in csv.DictReader(handle)
                    if (row.get("Symbol") or "").strip()
                }
            )
        if symbols:
            logger.info(
                "Universe %s: %d names from authority %s",
                universe_name,
                len(symbols),
                authority.name,
            )
            return symbols
    logger.warning(
        "Universe %s: no authority file; falling back to the in-code list, which may be stale",
        universe_name,
    )
    return list(get_universe_symbols(universe_name))


def load_mizan_cross_section(
    symbols: Sequence[str],
    *,
    as_of: date,
) -> tuple[dict[str, dict[str, str]], CrossSectionCoverage]:
    """Completed daily bars plus real macro, through the shared Mizan kernel.

    Bars come from the market-cache evidence stores; macro from the cached India VIX and NIFTY 50
    series. Every feature value is produced by ``modeling.mizan_features`` -- this function only
    gathers inputs.

    ``as_of`` is the session being traded; the decision uses bars strictly **before** it, because
    the model decides on a completed close and enters at the next open.
    """
    wanted = set(symbols)
    bars: dict[str, Any] = {}
    for cache_root in _BAR_CACHES:
        # Stop once the caches scanned so far already clear the coverage floor. Requiring a full
        # `issubset` meant one absent name -- 499 of 500 -- sent this on to enumerate the
        # 3,267-symbol all-market store, which takes over ten minutes to find nothing useful.
        if not cache_root.exists() or len(bars) >= MIN_CROSS_SECTION_COVERAGE * len(wanted):
            continue
        store = EvidenceStore(EvidenceStoreConfig(root=cache_root))
        for verified in store.list_verified(EvidenceResourceType.DATASET):
            acquisition = historical_acquisition_from_verified(verified)
            symbol = acquisition.manifest.symbol
            if symbol not in wanted or not acquisition.records:
                continue
            # Prefer the series ending latest, then the longer one. Selecting by length alone
            # let a stale 10-year cache beat a freshly ingested 3-year one, so the session
            # silently decided on week-old bars.
            existing = bars.get(symbol)
            candidate_end = acquisition.records[-1].exchange_date
            if existing:
                existing_end = existing[-1].exchange_date
                if (candidate_end, len(acquisition.records)) <= (
                    existing_end,
                    len(existing),
                ):
                    continue
            bars[symbol] = acquisition.records
        logger.info("Bars: %d/%d symbols after %s", len(bars), len(wanted), cache_root.parent.name)
        if wanted.issubset(bars):
            break

    if not bars:
        raise RuntimeError(
            f"no completed daily bars found for any of {len(wanted)} symbols in {_BAR_CACHES}"
        )

    # Symbols the cache had nothing for must still count against coverage. Reporting 49/49 for a
    # 50-name universe would let the floor pass on a cache holding 5 of 50, which is exactly the
    # shrunk cross-section the floor exists to catch. An empty series is "not enough bars", which
    # is what it is.
    for missing in wanted - set(bars):
        bars[missing] = ()

    vix: dict[str, float] = {}
    nifty: dict[str, float] = {}
    for macro_dir in reversed(_MACRO_DIRS):
        # Reversed so the freshest directory is applied last and wins on overlapping dates.
        vix.update(load_macro_series(macro_dir, "INDIAVIX"))
        nifty.update(load_macro_series(macro_dir, "NIFTY50"))
    decision_day = as_of - timedelta(days=1)
    return build_live_cross_section(
        bars,
        india_vix_by_date=vix,
        nifty_by_date=nifty,
        as_of=decision_day,
    )


def load_macro_series(macro_dir: Path, name: str) -> dict[str, float]:
    """Close-by-date for one macro series, matching the training store builder exactly."""
    path = macro_dir / f"macro_{name}.json"
    if not path.is_file():
        return {}
    payload = json.loads(path.read_text(encoding="utf-8"))
    return {candle[0][:10]: float(candle[4]) for candle in payload.get("candles", [])}


def run_paper_session(
    session_date: date | None = None,
    universe: list[str] | None = None,
    universe_name: str = "NIFTY500",
    model_profile: str = "default",
    initial_cash: Decimal = Decimal("1000000.00"),
    slippage_bps: Decimal = Decimal("5.0"),
    realtime: bool = False,
    interval_seconds: float = 10.0,
    end_time_str: str = "15:30:00",
    upstox_token: str | None = None,
    output_dir: Path | None = None,
    selection_fraction: float = 0.20,
    sizing: str = "equal-weight",
) -> dict[str, Any]:
    """Runs a complete quote-driven paper trading session in IST from start time until market close (15:30 IST)."""
    current_ist = now_ist()
    if session_date is None:
        session_date = current_ist.date()
    if universe is None:
        universe = resolve_universe(universe_name)
    if output_dir is None:
        output_dir = PROJECT_ROOT / "logs" / "paper_runs"

    if upstox_token:
        os.environ["UPSTOX_ACCESS_TOKEN"] = upstox_token

    output_dir.mkdir(parents=True, exist_ok=True)
    session_id = f"paper_ses_{session_date.strftime('%Y%m%d')}_{current_ist.strftime('%H%M%S')}_IST"

    # Parse market close time in IST (Default 15:30:00 IST)
    end_hour, end_min, end_sec = map(int, end_time_str.split(":"))
    close_dt_ist = datetime(
        session_date.year,
        session_date.month,
        session_date.day,
        end_hour,
        end_min,
        end_sec,
        tzinfo=_IST,
    )

    logger.info("=" * 80)
    logger.info("QuantOS Paper Pilot Execution Session (IST) -- %s", session_id)
    logger.info("Current Time (IST) : %s", current_ist.strftime("%Y-%m-%d %H:%M:%S IST"))
    logger.info("Market Close (IST) : %s", close_dt_ist.strftime("%Y-%m-%d %H:%M:%S IST"))
    logger.info("Universe           : %s (%d assets)", universe_name, len(universe))
    logger.info("Initial Capital    : Rs %s", _paisa_str(initial_cash))
    logger.info("Model Profile      : %s", model_profile.upper())
    # Validated, not merely present -- and before anything else, so an expired token stops the
    # session at startup instead of eight days of reports built on a substitute feed. The old
    # banner said "CONFIGURED" for any non-empty string and "NOT CONFIGURED (Using Live Exchange
    # Feed)" otherwise, which described the fallback as the live feed.
    assert_upstox_usable(upstox_token)
    logger.info(
        "Execution Mode     : %s (Interval: %.1fs)",
        "REALTIME_STREAM" if realtime else "INTRADAY_SEQUENCE",
        interval_seconds,
    )
    logger.info("=" * 80)

    # 1. Fetch initial real live quotes from Upstox / NSE
    logger.info("Fetching real-time market data from Upstox / NSE exchange feed...")
    base_market = fetch_quotes_with_retry(universe, access_token=upstox_token)
    if not base_market:
        raise QuoteFeedError(
            "the exchange feed returned nothing. What stood here was a hardcoded five-name "
            "baseline that would have produced a full session report from invented prices."
        )
    for sym, m in base_market.items():
        logger.info(
            "  [REAL NSE FEED] %-10s : Rs %s (Day Range: Rs %s - Rs %s | Vol: %s)",
            sym,
            _paisa_str(m["price"]),
            _paisa_str(m.get("low", m["price"])),
            _paisa_str(m.get("high", m["price"])),
            m.get("volume", "N/A"),
        )

    # 2. Initialize Mizan Model based on Profile
    # Both profiles carry verdict=RESEARCH_ONLY, so both are admitted only by the RESEARCH_PAPER
    # surface and only under the declared exemption. Acquiring the model through
    # `load_mizan_for_execution` is what makes that check unavoidable: the previous direct
    # `MizanModel.default_model()` call reached no gate at all.
    if model_profile == "sprint_50k":
        model = load_mizan_for_execution(
            ExecutionSurface.RESEARCH_PAPER,
            PAPER_OBSERVATION_EXEMPTION,
            profile="sprint_50k",
        )
        per_name_alloc = (initial_cash * Decimal("0.45")).quantize(
            _PAISA
        )  # 45% per name for 2-3 names
        risk_limits = RiskLimits(
            max_position_weight=0.50,  # Max 50% capital in single name
            max_daily_drawdown_pct=0.03,  # 3% daily drawdown kill switch
            max_total_drawdown_pct=0.08,  # 8% total drawdown kill switch
            min_cash_buffer_pct=0.05,  # 5% minimum cash buffer
            allow_naked_short=False,  # Strict long-only / no naked shorting
        )
    else:
        model = load_mizan_for_execution(
            ExecutionSurface.RESEARCH_PAPER,
            PAPER_OBSERVATION_EXEMPTION,
        )
        per_name_alloc = Decimal("150000.00")
        risk_limits = RiskLimits(
            max_position_weight=0.30,  # Max 30% capital in single name
            max_daily_drawdown_pct=0.04,  # 4% daily drawdown kill switch
            max_total_drawdown_pct=0.12,  # 12% total drawdown kill switch
            min_cash_buffer_pct=0.05,  # 5% minimum cash buffer
            allow_naked_short=False,  # Strict long-only / no naked shorting
        )

    logger.info(
        "Loaded Model: %s (%s, v%s)",
        model.config.model_name,
        model.config.model_id,
        model.config.version,
    )
    logger.info(
        "Score Threshold: %s | L2 Penalty: %s | Features: %d | Horizon: %d sessions",
        model.config.score_threshold,
        model.config.l2_penalty,
        len(model.config.feature_names),
        model.config.label_horizon_sessions,
    )

    # 2a-bis. Resume the running portfolio.
    #
    # A fresh engine every weekday would open ~55 names at the open and close them at 15:30, paying
    # a full round trip daily by construction. The model was measured entering at an open, holding
    # `label_horizon_sessions - 1` sessions, then re-ranking - a label horizon counts
    # decision -> entry -> exit, so the card's 11 is the screen's 10. `rebalance_due` takes the
    # card's convention and does that conversion itself; passing the raw value here and comparing it
    # directly was half of why the executed hold was 12 sessions rather than 10.
    # The hash as it stood when this session loaded, for the compare-and-swap at the close. Two
    # sessions ran concurrently and the second to finish silently discarded the first's whole
    # trading day; this does not stop the overlap, it stops the loss.
    portfolio_hash_at_load = state_hash_on_disk(PORTFOLIO_STATE_PATH)
    portfolio = load_portfolio(PORTFOLIO_STATE_PATH) or PaperPortfolioState(cash=initial_cash)
    horizon = int(model.config.label_horizon_sessions)
    rebalancing = portfolio.rebalance_due(horizon)
    logger.info(
        "Portfolio: cash Rs %s, %d holding(s), session %d, held %d of %d sessions -> %s",
        portfolio.cash,
        len(portfolio.holdings),
        portfolio.sessions_completed + 1,
        portfolio.sessions_held,
        horizon - 1,
        "REBALANCING" if rebalancing else "HOLDING",
    )

    # 2b. Mizan decision for this session, computed once from completed daily bars.
    #
    # Every feature comes from `modeling.mizan_features`, the kernel verified bit-identical against
    # the published training store. The selection rule is the model's own recorded
    # `score_threshold` plus a declared top fraction -- not the hardcoded 0.035 and `[:2]` this
    # runner used before, which produced zero proposals on every realistic universe.
    # On a hold session the ranking is not consulted at all, so the cross-section is not built:
    # computing a decision that will not be acted on invites reading it as one.
    if not rebalancing:
        mizan_scores: dict[str, float] = {}
        mizan_ranked: tuple[str, ...] = ()
        mizan_picks: tuple[str, ...] = ()
        logger.info("Holding: no re-ranking this session")
    else:
        mizan_cross_section, mizan_coverage = load_mizan_cross_section(universe, as_of=session_date)
        # The coverage gate runs *after* the extreme-row refusals below, not before. Checking first
        # measured a cross-section the session was not going to use: refusals shrink it further, and
        # a rank divides by the number of names present, so the gate would have passed on a
        # population that no longer existed by the time anything was ranked.
        mizan_cross_section, refused = refuse_extreme_rows(
            mizan_cross_section,
            # `means` and `scales` are decimal text on the preprocessor config, matching how the
            # evidence stores them; the guard works in float alongside the scorer.
            means={
                n: float(v)
                for n, v in zip(
                    model.preprocessor.feature_names, model.preprocessor.means, strict=True
                )
            },
            scales={
                n: float(v)
                for n, v in zip(
                    model.preprocessor.feature_names, model.preprocessor.scales, strict=True
                )
            },
        )
        if refused:
            logger.warning(
                "Refused %d name(s) whose standardized features exceed the model's working range: %s",
                len(refused),
                ", ".join(refused),
            )
        # Recorded on the coverage object rather than only logged. `skipped_extreme` existed as a
        # field and was never populated by anything, so the refusals the guard exists to make
        # visible were absent from the very report meant to show them.
        mizan_coverage = mizan_coverage.with_extreme_refusals(refused)
        logger.info("Mizan cross-section: %s", mizan_coverage.summary())
        if mizan_coverage.fraction < MIN_CROSS_SECTION_COVERAGE:
            raise RuntimeError(
                f"only {mizan_coverage.fraction:.1%} of the universe could be scored; a "
                f"cross-sectional rank divides by the number of names present, so a shrunk "
                f"cross-section changes every rank. Minimum is {MIN_CROSS_SECTION_COVERAGE:.0%}"
            )
        mizan_scores = model.predict_scores(
            {
                sym: {k: float(v) for k, v in feats.items()}
                for sym, feats in mizan_cross_section.items()
            }
        )
        mizan_ranked = tuple(sorted(mizan_scores, key=lambda s: (-mizan_scores[s], s)))
        # No score floor. The out-of-sample screen this path exists to reproduce applies none -
        # `screen_mizan_out_of_sample.py:199` is `take = max(1, int(len(scores) * FRACTION))` with
        # no score filter anywhere in the file - so a floor here is an unmeasured rule that changes
        # what is being executed.
        #
        # It was also dangerous. Scores cluster near zero against a 0.0715 floor, so an ordinary
        # session could clear nothing; `top_picks` came back empty while `rebalancing` stayed True,
        # and the exit loop then sold every holding. A go-to-cash rule nobody measured, firing
        # silently, on a book that had just paid to enter.
        mizan_picks = select_top_fraction(mizan_scores, selection_fraction)
        logger.info(
            "Mizan picks: %d of %d ranked (top %.0f%%, no score floor - the screen applies none): %s",
            len(mizan_picks),
            len(mizan_scores),
            selection_fraction * 100.0,
            ", ".join(f"{s} {mizan_scores[s]:+.5f}" for s in mizan_picks) or "none",
        )

    # 2b-bis. Equity marked at this session's open.
    #
    # One number, used by both the position sizing below and the risk baseline further down. They
    # used to derive their own: the risk baseline was corrected to a marked figure while sizing was
    # left on `ledger_funding()` -- cash + holdings **at cost** + carried fees, invariant to market
    # price -- forty lines apart. On a drawn-down book that over-allocates, funding the head of the
    # ranking and silently dropping names off the tail: measured at 9.87% cash held against a
    # declared 5% buffer, with a selected name absent entirely. That is the concentration defect
    # equal-weight sizing exists to prevent, reintroduced by fixing only one of the two callers.
    # `ledger_funding()` is the wrong quantity here and using it was the previous defect wearing a
    # new hat. It is cash + holdings **at cost** + carried fees: a cost figure, invariant to market
    # price. Seeding the daily peak with it meant the 4% daily rule measured cumulative unrealized
    # loss since the position was opened, so a book that drifted 5.6% down over ten sessions -- with
    # exactly zero intraday movement -- halted on the first order of the first rebalance. That order
    # is the exit, so the losing book was then held with nothing able to sell it. Which is verbatim
    # the failure the previous commit claimed to have fixed.
    #
    # The daily peak has to be equity **marked at this session's open**, so it moves with the market
    # the way the thing it is measuring does.
    opening_marks = {
        symbol: base_market[symbol]["price"]
        for symbol in portfolio.holdings
        if symbol in base_market
    }
    unpriced = sorted(set(portfolio.holdings) - set(opening_marks))
    if unpriced:
        # Cost basis for these, stated rather than silent. It is a baseline for a risk limit, not a
        # P&L figure, and refusing the whole session because one carried name is unquoted would be
        # worse than a bounded approximation that is logged.
        logger.warning(
            "No opening quote for %d carried name(s); their cost basis is used in the risk "
            "baseline: %s",
            len(unpriced),
            ", ".join(unpriced),
        )
    marked_opening_equity = (
        portfolio.cash
        + sum(
            (
                Decimal(holding.quantity) * opening_marks.get(holding.symbol, holding.average_cost)
                for holding in portfolio.holdings.values()
            ),
            Decimal("0.00"),
        )
    ).quantize(_PAISA)
    logger.info(
        "Risk baseline: opening equity Rs %s (marked), carried peak Rs %s",
        _paisa_str(marked_opening_equity),
        _paisa_str(portfolio.peak_equity),
    )

    # 2c. Position sizing.
    #
    # Equal-weight is the default because it is how the model was measured: the out-of-sample
    # screen averaged the forward target across the selected top 20% (`statistics.fmean`), giving
    # every chosen name the same weight. The previous fixed stake of Rs 150,000 per name meant 56
    # picks against Rs 1,000,000 filled only the first ~6 in rank order and left the other 50
    # unexpressed -- a concentrated bet on the head of a ranking, which nobody validated.
    #
    # `fixed` remains available because the sprint profile deliberately concentrates into 2-3 names
    # and equal-weighting would silently undo that intent.
    if sizing == "equal-weight" and mizan_picks:
        # Sized from the portfolio's actual funding, not from the `initial_cash` nominal. Sizing
        # from the constant survived the change that made the portfolio persistent, so a book that
        # had drawn down kept allocating as though it still held its opening capital -- which funds
        # only the head of the ranking and leaves the tail unexpressed. That is precisely the
        # concentration defect equal-weight sizing was introduced to remove.
        usable = marked_opening_equity * (
            Decimal("1") - Decimal(str(risk_limits.min_cash_buffer_pct))
        )
        per_name_alloc = (usable / Decimal(len(mizan_picks))).quantize(_PAISA)
        logger.info(
            "Sizing: equal-weight, Rs %s per name across %d picks (%.0f%% cash buffer held back)",
            per_name_alloc,
            len(mizan_picks),
            risk_limits.min_cash_buffer_pct * 100,
        )
    else:
        logger.info("Sizing: fixed, Rs %s per name", per_name_alloc)

    # 3. Risk Governor Setup
    #
    # Seeded with the carried all-time peak, not left at zero. A fresh governor each session took
    # its peak from whatever that session opened at, so a multi-session decline was measured
    # against its own falling baseline and the total-drawdown kill switch could never trip. The
    # peak is the larger of what the portfolio has ever reached and what it is funded with today,
    # so a first run establishes a real baseline rather than starting at zero.
    if portfolio.risk_halted:
        # A tripped kill switch is not cleared by time passing. Refusing here rather than trading is
        # the only honest option left: resetting it would make the switch decorative, and
        # liquidating on its own would execute a rule nobody measured. Clearing it is a human act.
        logger.error(
            "REFUSING TO TRADE: the risk kill switch fired on %s and has not been cleared. "
            "Reason: %s. Review the book, then run:  "
            "python scripts/clear_paper_halt.py --i-have-reviewed-the-book  "
            "Do NOT hand-edit or delete %s: it is hash-protected, so an edit is refused on the "
            "next load, and deleting it invents a fresh portfolio and discards the real book.",
            portfolio.halted_on,
            portfolio.halt_reason or "not recorded",
            PORTFOLIO_STATE_PATH,
        )
        raise SystemExit(8)

    # Two peaks, two meanings. `initial_equity` is *this session's* opening equity, so the 4% daily
    # limit measures an intraday decline; `all_time_peak_equity` is the carried high-water mark, so
    # the 12% total limit measures a multi-session one.
    #
    # Passing the carried peak as `initial_equity` -- which is what this line used to do -- seeded
    # both, and the daily check then measured multi-session declines against the 4% limit. The
    # total switch became unreachable, and a session that opened flat and never moved intraday
    # could halt the book on the first order, which is the exit.
    governor = PreTradeRiskGovernor(
        limits=risk_limits,
        initial_equity=marked_opening_equity,
        all_time_peak_equity=max(portfolio.peak_equity, marked_opening_equity),
    )

    # 4. Order Book Simulator Configuration
    sim_config = OrderBookSimConfig(
        slippage_bps=slippage_bps,
        allow_depth_walking=True,
        enforce_market_hours=False,
    )

    # 5. Initialize Paper Pilot Engine
    engine = PaperPilotEngine(
        # Funded with cash plus the carried holdings' cost basis and their entry fees, so the
        # replay below debits exactly that back out and leaves cash at its true carried figure.
        initial_cash=portfolio.ledger_funding(),
        risk_governor=governor,
        sim_config=sim_config,
        allow_short=False,
        session_id=session_id,
    )

    # Reconstruct the carried positions in the fresh ledger. Without this a SELL of something held
    # since a previous session is refused as a short, because the ledger has never seen it. The
    # fills carry their original entry fee, which `ledger_funding` has already covered, so the
    # eventual sale nets both legs instead of only the exit.
    # Through the engine, not the ledger directly. Going straight to `ledger.process_fill` left the
    # engine's own reconciliation baseline flat, so `end_session` compared the ledger's carried
    # positions against today's fills alone and mismatched on every one of them.
    carry_fills = portfolio.carry_forward_fills(current_ist)
    engine.carry_in_positions(carry_fills)
    if carry_fills:
        logger.info(
            "Carried %d position(s) into the ledger; cash now Rs %s",
            len(carry_fills),
            _paisa_str(engine.cash),
        )

    # 6. Open Session at current IST time
    engine.start_session(session_date=session_date, timestamp=current_ist)
    logger.info("Trading session ACTIVE at %s", current_ist.strftime("%Y-%m-%d %H:%M:%S IST"))

    # Tracking state
    proposals_submitted = []
    shutdown_requested = False

    def handle_sigint(signum: int, frame: Any) -> None:
        nonlocal shutdown_requested
        logger.warning(
            "Interrupt signal received. Initiating clean session close and reconciliation..."
        )
        shutdown_requested = True

    signal.signal(signal.SIGINT, handle_sigint)
    signal.signal(signal.SIGTERM, handle_sigint)

    status_file = output_dir / "live_paper_status.json"
    rolling_status: dict[str, Any] = {
        "session_id": session_id,
        "status": "INITIALIZING",
        "timestamp_ist": current_ist.strftime("%Y-%m-%d %H:%M:%S IST"),
        "initial_cash": _paisa_str(initial_cash),
        "total_equity": _paisa_str(initial_cash),
        "cash": _paisa_str(initial_cash),
        "realized_pnl": "0.00",
        "unrealized_pnl": "0.00",
        "net_pnl": "0.00",
        "net_pnl_pct": 0.0,
        "total_fees_paid": "0.00",
        "open_positions": {},
        "positions_detail": [],
        "fills_count": 0,
        "recent_fills": [],
        "alpha_signals": [],
        "risk_governor": {
            "kill_switch_active": False,
            "max_position_weight": "30%",
            "min_cash_buffer": "5%",
            "daily_drawdown_limit": "4%",
            "discrepancy_paisa": "0.00",
        },
        "market_close_ist": close_dt_ist.strftime("%H:%M:%S IST"),
    }
    step = 0
    consecutive_quote_failures = 0
    session_abort_reason = ""

    # A restart within the same session must reuse the morning's baseline, not take a fresh one
    # from wherever the book has since fallen to. The anchor lived only in this process, so four
    # starts in one day measured a 10.2% decline as three separate sub-4% ones and never tripped
    # the 4% limit. Three sessions were abandoned and restarted on 2026-08-31 alone.
    session_anchor_equity: Decimal | None = None
    daily_peak_anchored = False
    last_reported_coverage: int | None = None
    persisted_anchor = anchor_to_reuse(portfolio, session_date)
    if persisted_anchor is not None:
        governor.reset_session_peak(persisted_anchor)
        session_anchor_equity = persisted_anchor
        daily_peak_anchored = True
        logger.info(
            "Reusing today's persisted drawdown baseline of Rs %s from an earlier start of this "
            "session; not re-anchoring.",
            _paisa_str(persisted_anchor),
        )

    try:
        while not shutdown_requested:
            step += 1
            loop_now = now_ist() if realtime else (current_ist + timedelta(minutes=15 * step))

            # Check if market close time reached
            if loop_now >= close_dt_ist:
                logger.info(
                    "Market close reached at %s. Finalizing session...",
                    loop_now.strftime("%H:%M:%S IST"),
                )
                break

            logger.info(
                "--- [IST %s] Interval %02d | Active Trading Loop ---",
                loop_now.strftime("%H:%M:%S"),
                step,
            )

            # Fetch fresh real-time quotes from Upstox / NSE.
            #
            # A failed poll skips the interval; it does not end the day. The refusal this softens
            # was written for *startup*, where an unusable feed means the session must not begin,
            # and applying it to every poll made one SSL handshake timeout kill a session that had
            # been trading for two hours. The book is unchanged in the meantime -- the previous
            # quotes stay in `base_market` and no decision is taken on them, because entries and
            # exits only act on a rebalance.
            #
            # Persistent failure is still fatal: the feed being down for
            # MAX_CONSECUTIVE_QUOTE_FAILURES polls is not a blip, and continuing would mark the
            # book to prices that stopped arriving.
            if realtime:
                try:
                    live_quotes = fetch_upstox_live_quotes(universe, access_token=upstox_token)
                except QuoteFeedError as quote_error:
                    consecutive_quote_failures += 1
                    if consecutive_quote_failures >= MAX_CONSECUTIVE_QUOTE_FAILURES:
                        raise QuoteFeedError(
                            f"the quote feed has failed {consecutive_quote_failures} polls in a "
                            f"row (last: {quote_error}). Ending the session rather than holding a "
                            "book marked to prices that stopped arriving."
                        ) from quote_error
                    logger.warning(
                        "Quote poll %d failed (%s); skipping this interval. %d of %d before the "
                        "session ends.",
                        step,
                        quote_error,
                        consecutive_quote_failures,
                        MAX_CONSECUTIVE_QUOTE_FAILURES,
                    )
                    if realtime:
                        time.sleep(interval_seconds)
                    continue
                consecutive_quote_failures = 0
                for sym, q in live_quotes.items():
                    base_market[sym] = q

            # Anchor the daily peak to the first live mark of the session, before any order.
            #
            # `marked_opening_equity` is computed from `base_market` as it stood when the process
            # booted. At 09:00 that is the **previous close**, so an overnight gap became a "daily"
            # drawdown with zero intraday movement: the 4% rule fired on the first order, which is
            # the exit, the losing book was retained, and `risk_halted` persisted so every later
            # session exited 8.
            #
            # This is the third round in which the daily rule has measured something other than the
            # day. `reset_session_peak` exists precisely for this and had no caller anywhere in the
            # repository through all three; it has one now. Anchoring here rather than at the
            # snapshot below matters, because the order loops run first within a step.
            if realtime and not daily_peak_anchored:
                anchor_equity = equity_marked_at(
                    engine.cash,
                    engine.positions,
                    {sym: state["price"] for sym, state in base_market.items()},
                )
                governor.reset_session_peak(anchor_equity)
                session_anchor_equity = anchor_equity
                daily_peak_anchored = True
                logger.info(
                    "Daily drawdown baseline anchored at Rs %s from the first live mark (was Rs "
                    "%s from the previous close)",
                    _paisa_str(anchor_equity),
                    _paisa_str(marked_opening_equity),
                )

            # Generate realistic top-of-book and L2 depth from real market quotes
            step_books = {}
            for sym, state in base_market.items():
                mid = state["price"]
                spread = state.get("spread", Decimal("0.10"))
                bid_p = (mid - spread / Decimal("2.0")).quantize(_PAISA)
                ask_p = (mid + spread / Decimal("2.0")).quantize(_PAISA)
                depth = state.get("depth", 300)

                bids = [
                    (bid_p, depth),
                    ((bid_p - Decimal("0.05")).quantize(_PAISA), depth * 2),
                    ((bid_p - Decimal("0.10")).quantize(_PAISA), depth * 3),
                ]
                asks = [
                    (ask_p, depth),
                    ((ask_p + Decimal("0.05")).quantize(_PAISA), depth * 2),
                    ((ask_p + Decimal("0.10")).quantize(_PAISA), depth * 3),
                ]
                book = OrderBookSnapshot.from_levels(
                    symbol=sym,
                    timestamp=loop_now,
                    bids=bids,
                    asks=asks,
                    last_price=mid,
                )
                step_books[sym] = book

                # Process quote and execute pending order matches
                fills_from_quote = engine.process_quote(book, current_time=loop_now)
                if fills_from_quote:
                    for fill in fills_from_quote:
                        logger.info(
                            "  [FILL EXECUTED] %s: %s %d @ Rs %s (Statutory Fee: Rs %s)",
                            fill.symbol,
                            fill.side.value,
                            fill.quantity,
                            _paisa_str(fill.price),
                            _paisa_str(fill.fee),
                        )

            # 5b. Mizan decisions are computed once per session, before the loop, from
            # completed daily bars through the shared feature kernel. They deliberately do not
            # change intraday: the model was validated deciding at a session close and entering at
            # the next open, so re-scoring on a partially formed bar would execute a rule nobody
            # measured. The previous version rebuilt all fifteen features here from that step's
            # quote alone -- `return_5 = return_1 * 1.5`, macro pinned to constants, and
            # `rsi_14_centered` clamped to +/-50 against a trained range of +/-0.45.
            scores = mizan_scores
            ranked_symbols = list(mizan_ranked)
            top_picks = list(mizan_picks)

            # Intraday percentage move, for the dashboard's gainers/losers panel only. This is
            # deliberately NOT a model input: the decision above came from completed daily bars
            # through the shared kernel. Conflating the two is what the old code did.
            returns_map = {}
            # Symbols the feed actually returned. Indexing `base_market` by every universe member
            # crashed the whole session when Upstox omitted one: `KeyError: '360ONE'` on
            # 2026-08-31, before a single order. Removing the fabricated price table -- correctly --
            # left every consumer that assumed full coverage exposed, and fixing the *cause* of that
            # day's missing symbol left the crash itself in place.
            priced = [sym for sym in universe if sym in base_market]
            # Logged when the coverage *changes*, not every interval. At a 30-second cadence this
            # printed on the order of 780 identical lines a session; the 2026-08-31 log is 246 KB,
            # and a log an operator will not read is not an operational control.
            if len(priced) < len(universe) and len(priced) != last_reported_coverage:
                last_reported_coverage = len(priced)
                logger.info(
                    "Quotes cover %d of %d names this step; the rest are omitted from the "
                    "intraday panels, not priced.",
                    len(priced),
                    len(universe),
                )

            for sym in priced:
                # Not named `quote`: that name is bound to a `Quote` object later in this
                # function, and reusing it made mypy infer dict[str, Any] for both.
                quote_state = base_market[sym]
                price = float(quote_state["price"])
                previous_close = float(quote_state.get("previous_close", price))
                returns_map[sym] = (
                    (price - previous_close) / previous_close if previous_close > 0 else 0.0
                )

            # 5e. On a rebalance, exit whatever is no longer selected.
            #
            # Gated on `rebalancing`: on a hold session `scores` is empty, so the old condition
            # `scores.get(sym, 0.0) < 0.01 and sym not in top_picks` was true for *every* holding
            # and would have liquidated the entire portfolio on the first day it held.
            #
            # Also gated on a non-empty selection. Removing the invented score floor made an empty
            # `top_picks` much less likely, but "sell everything" must never be reachable by the
            # selection simply failing to produce names -- a shrunk cross-section or a scoring
            # failure would otherwise present as a deliberate go-to-cash decision. Going flat is a
            # rule the screen does not contain, so it should not be an outcome the code can reach
            # by accident.
            if rebalancing and not top_picks:
                logger.error(
                    "Rebalance selected no names from %d scored. Holding the existing book rather "
                    "than liquidating: going to cash is not a rule the screen contains.",
                    len(scores),
                )
            for sym, pos in list(engine.positions.items()) if rebalancing and top_picks else []:
                if pos.quantity > 0 and sym not in top_picks:
                    prop_id = f"prop_{session_id}_{step}_{sym}_SELL"
                    proposal = PaperProposal(
                        proposal_id=prop_id,
                        symbol=sym,
                        side=Side.SELL,
                        quantity=pos.quantity,
                        order_type=OrderType.MARKET,
                        decision_at=loop_now,
                        strategy_name="Mizan_Alpha_ExitLowRank",
                        model_artifact_id=model.config.model_id,
                    )
                    order, decision = engine.submit_proposal(proposal)
                    proposals_submitted.append((proposal, decision))
                    logger.info(
                        "  [EXIT PROPOSAL SUBMITTED] %s SELL %d %s (Risk: %s)",
                        prop_id,
                        pos.quantity,
                        sym,
                        "APPROVED" if decision.approved else "REJECTED",
                    )

            # 5f. On a rebalance, enter the selection.
            #
            # The exits above are *staged* first, not filled first. `submit_proposal` only stages;
            # fills happen in the next step's `process_quote`, so the proceeds of an exit are not
            # in `engine.cash` when the entries below are sized. The comment that stood here said
            # they were, which is a statement of mechanism that the code does not implement --
            # a reader sizing a change against it would be reasoning from a fiction.
            #
            # It is self-correcting over later steps: the exits fill, cash rises, and the entries
            # that could not be sized this step are sized in a later one. The practical effect is
            # that a fully invested book entering a rebalance can only spend its cash buffer on the
            # first step, and the tail of the ranking fills over subsequent steps rather than at
            # once.
            #
            # Explicitly gated on `rebalancing`. It used to rely on `top_picks` happening to be
            # empty on a hold session -- the invariant "act only on a rebalance session" enforced
            # explicitly in one loop and by coincidence in the other, forty lines apart.
            for sym in top_picks if rebalancing else []:
                current_held = engine.positions[sym].quantity if sym in engine.positions else 0
                if current_held == 0:
                    step_marks = {s: state["price"] for s, state in base_market.items()}
                    if sym not in step_marks:
                        logger.warning("  %s: selected but no quote this step; not entered", sym)
                        continue
                    avail_cash = engine.cash
                    target_alloc = min(per_name_alloc, avail_cash * Decimal("0.95"))
                    price = step_marks[sym]
                    qty = entry_quantity(sym, step_marks, per_name_alloc, avail_cash)
                    if qty == 0:
                        # One share costs more than the allocation. Saying so beats a silent skip:
                        # under equal weight this is how a high-priced name drops out.
                        logger.info(
                            "  %s: skipped, 1 share costs Rs %s against an allocation of Rs %s",
                            sym,
                            _paisa_str(price),
                            _paisa_str(target_alloc),
                        )
                    if qty > 0:
                        prop_id = f"prop_{session_id}_{step}_{sym}_BUY"
                        proposal = PaperProposal(
                            proposal_id=prop_id,
                            symbol=sym,
                            side=Side.BUY,
                            quantity=qty,
                            order_type=OrderType.MARKET,
                            decision_at=loop_now,
                            strategy_name="Mizan_Alpha_TopPicks",
                            model_artifact_id=model.config.model_id,
                        )
                        order, decision = engine.submit_proposal(proposal)
                        proposals_submitted.append((proposal, decision))
                        logger.info(
                            "  [PROPOSAL SUBMITTED] %s BUY %d %s (Risk: %s, Reason: %s)",
                            prop_id,
                            qty,
                            sym,
                            "APPROVED" if decision.approved else "REJECTED",
                            decision.reason or "OK",
                        )

            # Update rolling status file for live monitoring
            snapshot_prices, unmarked_now = marks_for_open_positions(
                {sym: state["price"] for sym, state in base_market.items()}, engine.positions
            )
            if unmarked_now:
                logger.warning(
                    "No quote this step for %d held name(s); marked at cost for the snapshot: %s",
                    len(unmarked_now),
                    ", ".join(unmarked_now),
                )
            snap = engine.get_portfolio_snapshot(timestamp=loop_now, current_prices=snapshot_prices)

            positions_detail = []
            for sym, pos in engine.positions.items():
                if pos.quantity != 0:
                    cur_p = snapshot_prices.get(sym, pos.average_price)
                    pos_val = (cur_p * Decimal(pos.quantity)).quantize(_PAISA)
                    cost_basis = (pos.average_price * Decimal(pos.quantity)).quantize(_PAISA)
                    u_pnl = (pos_val - cost_basis).quantize(_PAISA)
                    u_pct = (
                        float(u_pnl / cost_basis * Decimal("100.0"))
                        if cost_basis > Decimal("0")
                        else 0.0
                    )
                    alloc_pct = (
                        float(pos_val / snap.total_equity * Decimal("100.0"))
                        if snap.total_equity > Decimal("0")
                        else 0.0
                    )
                    positions_detail.append(
                        {
                            "symbol": sym,
                            "quantity": pos.quantity,
                            "entry_price": _paisa_str(pos.average_price),
                            "current_price": _paisa_str(cur_p),
                            "cost_basis": _paisa_str(cost_basis),
                            "market_value": _paisa_str(pos_val),
                            "unrealized_pnl": _paisa_str(u_pnl),
                            "unrealized_pnl_pct": round(u_pct, 2),
                            "allocation_pct": round(alloc_pct, 2),
                        }
                    )

            fills_detail = [
                {
                    "fill_id": f.fill_id,
                    "order_id": f.order_id,
                    "symbol": f.symbol,
                    "side": f.side.value,
                    "quantity": f.quantity,
                    "price": _paisa_str(f.price),
                    "fee": _paisa_str(f.fee),
                    "timestamp_ist": f.timestamp.astimezone(_IST).strftime("%H:%M:%S IST"),
                }
                for f in engine.fills[-15:]
            ]

            alpha_detail = [
                {
                    "rank": i + 1,
                    "symbol": sym,
                    "score": round(scores.get(sym, 0.0), 4),
                    "is_top_pick": sym in top_picks,
                }
                for i, sym in enumerate(ranked_symbols)
            ]

            total_fees = sum((f.fee for f in engine.fills), Decimal("0.00")).quantize(_PAISA)
            # Equity minus capital, not realized + unrealized. The latter **excludes the statutory
            # fees already paid**: measured live, it reported -205.88 against a true -1,279.94 while
            # the fees tile beside it showed 1,074.06 -- the exact gap. Both numbers were on screen
            # and did not reconcile, and the headline understated the loss by precisely the cost of
            # trading, which is the one quantity this strategy's research says is binding.
            #
            # This form also cannot double-count: a closed lot's fees are already inside
            # `realized_pnl`, so subtracting `total_fees_paid` from it would charge them twice.
            live_equity = (snap.cash + snap.total_market_value).quantize(_PAISA)
            net_pnl = (live_equity - initial_cash).quantize(_PAISA)
            net_pnl_pct = float(net_pnl / initial_cash * Decimal("100.0"))

            sorted_gainers = sorted(priced, key=lambda s: returns_map.get(s, 0.0), reverse=True)
            top_gainers_list = [
                {
                    "rank": i + 1,
                    "symbol": s,
                    "price": _paisa_str(base_market[s]["price"]),
                    "change_pct": round(returns_map.get(s, 0.0) * 100, 2),
                    "alpha_score": round(scores.get(s, 0.0), 4),
                }
                for i, s in enumerate(sorted_gainers[:10])
            ]
            top_losers_list = [
                {
                    "rank": i + 1,
                    "symbol": s,
                    "price": _paisa_str(base_market[s]["price"]),
                    "change_pct": round(returns_map.get(s, 0.0) * 100, 2),
                    "alpha_score": round(scores.get(s, 0.0), 4),
                }
                for i, s in enumerate(sorted_gainers[-10:][::-1])
            ]

            rolling_status = {
                "session_id": session_id,
                "status": "RUNNING",
                # Published so the dashboard states what is actually running. Its header, panel
                # title and badge were hardcoded to "NIFTY 50" / "50 Stocks Evaluated" while the
                # session ran NIFTY 500 and scored 498 names.
                "universe_name": universe_name,
                "universe_size": len(universe),
                "scored_count": len(scores),
                "timestamp_ist": loop_now.strftime("%Y-%m-%d %H:%M:%S IST"),
                "initial_cash": _paisa_str(initial_cash),
                "total_equity": _paisa_str(snap.total_equity),
                "cash": _paisa_str(snap.cash),
                "realized_pnl": _paisa_str(snap.realized_pnl),
                "unrealized_pnl": _paisa_str(snap.unrealized_pnl),
                "net_pnl": _paisa_str(net_pnl),
                "net_pnl_pct": round(net_pnl_pct, 3),
                "total_fees_paid": _paisa_str(total_fees),
                "open_positions": {
                    s: p.quantity for s, p in engine.positions.items() if p.quantity != 0
                },
                "positions_detail": positions_detail,
                "fills_count": len(engine.fills),
                "recent_fills": fills_detail,
                "alpha_signals": alpha_detail,
                "top_gainers": top_gainers_list,
                "top_losers": top_losers_list,
                "risk_governor": {
                    # `RiskLimits` carries no kill-switch field; the state lives on the governor as the
                    # public `is_killed` property. The old attribute raised AttributeError.
                    "kill_switch_active": governor.is_killed,
                    "max_position_weight": f"{int(governor.limits.max_position_weight * 100)}%",
                    "min_cash_buffer": f"{int(governor.limits.min_cash_buffer_pct * 100)}%",
                    "daily_drawdown_limit": f"{int(governor.limits.max_daily_drawdown_pct * 100)}%",
                    "discrepancy_paisa": "0.00",
                },
                "market_close_ist": close_dt_ist.strftime("%H:%M:%S IST"),
            }
            with open(status_file, "w", encoding="utf-8") as f:
                json.dump(rolling_status, f, indent=2)

            if realtime:
                time.sleep(interval_seconds)
            elif step >= 12:  # In sequence mode, finish full session
                break

    except Exception as err:
        # Recorded, not swallowed. This handler used to log and fall through to a normal close, so
        # an unhandled exception still produced "Session Concluded & Reconciled: SUCCESS" and exit
        # 0 -- which is how a session that died at 14:21 looked identical to one that ran to the
        # bell. The session is still closed and reconciled below, because an abrupt exit would
        # leave the book unpersisted and the ledger unreconciled; what changes is that it says so.
        session_abort_reason = f"{type(err).__name__}: {err}"
        logger.exception("Session ABORTED during the trading loop: %s", err)

    # 6. Final Market Close Processing (15:30 IST)
    final_now = now_ist() if realtime else close_dt_ist
    final_prices, unmarked_at_close = marks_for_open_positions(
        {sym: state["price"] for sym, state in base_market.items()}, engine.positions
    )
    if unmarked_at_close:
        logger.error(
            "No closing quote for %d held name(s); marked at cost basis, so their unrealized P&L "
            "is reported as zero and the equity figure is not fully marked to market: %s",
            len(unmarked_at_close),
            ", ".join(unmarked_at_close),
        )
    for sym, close_price in final_prices.items():
        # Not `price`: that name is bound to a float earlier in this function for the returns
        # ratio, and reusing it made mypy read every closing mark as a float -- a float in the
        # argument list of a Decimal money constructor, which is the one thing this ledger forbids.
        quote = Quote(
            symbol=sym,
            timestamp=final_now,
            bid=close_price,
            ask=close_price,
            last_price=close_price,
        )
        engine.process_quote(quote, current_time=final_now)

    # 7. End Trading Session & Penny-Exact Reconciliation
    reconciliation = engine.end_session(timestamp=final_now, close_prices=final_prices)

    # 7b. Persist the running portfolio for the next session.
    #
    # Written after reconciliation so a session that fails to reconcile does not advance the
    # portfolio. Fees counted are today's real fills only - the carry-forward replay is zero-fee
    # and must not be added again.
    todays_fees = sum(
        (f.fee for f in engine.fills if not f.fill_id.startswith("carry_")), Decimal("0.00")
    )
    # The entry cost still attributable to each open position, so a name carried into tomorrow does
    # not have its entry fee dropped on the way through the state file.
    open_entry_fees = {
        symbol: sum((lot.entry_fee for lot in lots), Decimal("0.00"))
        for symbol, lots in engine.ledger.lots.items()
    }
    # Did a rebalance actually happen, or was one merely intended?
    #
    # `rebalanced=rebalancing` recorded the intent. A rebalance in which every order was refused --
    # 228 rejections, zero fills, the book unchanged -- was persisted as one that happened,
    # resetting the hold clock and advancing `last_rebalance_on` on a portfolio nobody had touched.
    #
    # The obvious repair, "did anything fill?", is wrong in the other direction: a rebalance whose
    # new selection equals the current book legitimately fills nothing, and that IS a completed
    # rebalance -- the model re-ranked and chose to keep what it held. Resetting its clock is
    # correct. So the test is whether the selection was *executed*, which means a rebalance session
    # that reached the point of acting: either something traded, or nothing needed to.
    # `total_fills_count > 0` was satisfied by **exits alone**.
    #
    # A rebalance where every exit filled and every entry was skipped as unaffordable left the
    # pilot 100% in cash, having paid a full exit round trip -- and recorded it as a completed
    # rebalance, resetting the hold clock and stamping `last_rebalance_on`. Going to cash is not a
    # rule the screen contains, so it cannot be an outcome that counts as executing one.
    #
    # A rebalance executes when the book ends up holding the selection, or at least moves toward
    # it: an entry filled. Exits on their own are half a rebalance, and the half that leaves the
    # portfolio in a state the strategy never intends.
    entry_fills = [
        fill
        for fill in engine.fills
        if fill.side is Side.BUY and not fill.fill_id.startswith("carry_")
    ]
    # How much of the selection the book actually ended up holding.
    #
    # `bool(entry_fills)` treated one fill as a completed rebalance. Coverage asks the question the
    # flag is really for -- did the portfolio become the thing the model chose? -- and answers it
    # the same way for all the shapes that matter: an all-exits rebalance covers 0.0, one entry of
    # four covers 0.25, a re-rank that keeps everything covers 1.0, and today's 97 fills of 100
    # picks cover 0.97.
    selected = set(mizan_picks)
    held = set(engine.positions)
    rebalance_coverage = len(held & selected) / len(selected) if selected else 0.0
    executed_rebalance = rebalancing and rebalance_executed(selected, held)
    if rebalancing and not executed_rebalance:
        logger.warning(
            "Rebalance did NOT execute: %d of %d selected names held (%.0f%%, minimum %.0f%%); "
            "%d order(s) submitted, %d filled (%d of them entries), %d rejected. The hold clock is "
            "not reset.",
            len(held & selected),
            len(selected),
            rebalance_coverage * 100,
            MIN_REBALANCE_COVERAGE * 100,
            reconciliation.orders_submitted,
            reconciliation.total_fills_count,
            len(entry_fills),
            reconciliation.orders_rejected,
        )
        if not engine.positions:
            exit_fills = [
                fill
                for fill in engine.fills
                if fill.side is Side.SELL and not fill.fill_id.startswith("carry_")
            ]
            logger.error(
                "%s",
                flat_book_alarm(
                    opened_holding=len(engine.carried_positions),
                    exit_fills=len(exit_fills),
                    exit_fees=sum((f.fee for f in exit_fills), Decimal("0.00")),
                ),
            )

    portfolio = state_from_ledger(
        portfolio,
        cash=engine.cash,
        positions={sym: (pos.quantity, pos.average_price) for sym, pos in engine.positions.items()},
        session_date=session_date,
        session_realized_pnl=engine.ledger.realized_pnl,
        fees_paid=todays_fees,
        rebalanced=executed_rebalance,
        open_entry_fees=open_entry_fees,
        # Marked equity, not the governor's peak alone. `update_peaks` is reachable only from
        # `evaluate_order`, and a hold session proposes no orders, so nine sessions in ten never
        # touched the peak -- and the fallback seed was `ledger_funding()`, a *cost* figure. A book
        # that rose 25% during a hold and then fell 20% from that high recorded no drawdown at all.
        session_peak_equity=max(governor.all_time_peak_equity, reconciliation.total_equity),
        daily_anchor_on=session_date if session_anchor_equity is not None else None,
        daily_anchor_equity=session_anchor_equity,
        risk_halted=governor.is_killed,
        halt_reason=(
            governor.kill_events[-1].reason if governor.is_killed and governor.kill_events else ""
        ),
    )
    try:
        save_portfolio(PORTFOLIO_STATE_PATH, portfolio, portfolio_hash_at_load)
    except PaperPortfolioError as clash:
        # The session's own artifacts are already written, so the day is recoverable by hand; what
        # must not happen is overwriting whatever the other session recorded.
        session_abort_reason = f"{type(clash).__name__}: {clash}"
        logger.error("REFUSING to persist the portfolio: %s", clash)
    logger.info(
        "Portfolio saved: cash Rs %s, %d holding(s), realized Rs %s, fees to date Rs %s",
        portfolio.cash,
        len(portfolio.holdings),
        portfolio.realized_pnl,
        portfolio.total_fees,
    )
    # The same correction as the live tile, and it matters more here: this figure is written into
    # the session JSON and the markdown report, so the record inherited the understatement.
    total_net_pnl = (reconciliation.total_equity - initial_cash).quantize(_PAISA)
    return_pct = float(total_net_pnl / initial_cash * Decimal("100.0"))

    logger.info("=" * 80)
    logger.info(
        "Session Concluded & Reconciled: %s", "SUCCESS" if reconciliation.reconciled else "FAILED"
    )
    logger.info("Closure Time (IST)   : %s", final_now.strftime("%Y-%m-%d %H:%M:%S IST"))
    logger.info("Initial Capital      : Rs %s", _paisa_str(reconciliation.initial_cash))
    logger.info("Final Cash           : Rs %s", _paisa_str(reconciliation.final_cash))
    logger.info(
        "Total Equity         : Rs %s (Net P&L: Rs %s, %+.2f%%)",
        _paisa_str(reconciliation.total_equity),
        _paisa_str(total_net_pnl),
        return_pct,
    )
    logger.info(
        "Statutory NSE Fees   : Rs %s | Slippage: Rs %s",
        _paisa_str(reconciliation.total_fees_paid),
        _paisa_str(reconciliation.total_slippage_cost),
    )
    logger.info(
        "Orders Summary       : %d submitted | %d filled | %d cancelled | %d rejected",
        reconciliation.orders_submitted,
        reconciliation.orders_filled,
        reconciliation.orders_cancelled,
        reconciliation.orders_rejected,
    )
    logger.info(
        "Total Fills          : %d | Discrepancy: Rs %s",
        reconciliation.total_fills_count,
        _paisa_str(reconciliation.discrepancy_paisa),
    )
    logger.info("=" * 80)

    # 8. Compile Comprehensive Audit & Feedback Report in IST
    feedback_payload = {
        "session_id": session_id,
        "session_date": str(session_date),
        "timezone": "IST (Asia/Kolkata, UTC+05:30)",
        "started_at_ist": current_ist.strftime("%Y-%m-%d %H:%M:%S IST"),
        "closed_at_ist": final_now.strftime("%Y-%m-%d %H:%M:%S IST"),
        "market_close_ist": close_dt_ist.strftime("%Y-%m-%d %H:%M:%S IST"),
        "model": {
            "model_id": model.config.model_id,
            "candidate_id": model.config.candidate_id,
            "model_name": model.config.model_name,
            "version": model.config.version,
            "architecture": model.config.model_type,
            "feature_schema": f"{model.config.feature_schema_id} (v{model.config.feature_schema_version})",
            "feature_count": len(model.config.feature_names),
        },
        "universe": universe,
        "capital": {
            "initial_cash": _paisa_str(reconciliation.initial_cash),
            "final_cash": _paisa_str(reconciliation.final_cash),
            "total_equity": _paisa_str(reconciliation.total_equity),
            "cash_delta": _paisa_str(reconciliation.total_cash_delta),
        },
        "performance": {
            "realized_pnl": _paisa_str(reconciliation.total_realized_pnl),
            "unrealized_pnl": _paisa_str(reconciliation.total_unrealized_pnl),
            "total_net_pnl": _paisa_str(total_net_pnl),
            "return_pct": round(return_pct, 4),
            "total_fees_paid": _paisa_str(reconciliation.total_fees_paid),
            "total_slippage_cost": _paisa_str(reconciliation.total_slippage_cost),
        },
        "order_statistics": {
            "proposals_submitted": len(proposals_submitted),
            "orders_submitted": reconciliation.orders_submitted,
            "orders_filled": reconciliation.orders_filled,
            "orders_partially_filled": reconciliation.orders_partially_filled,
            "orders_cancelled": reconciliation.orders_cancelled,
            "orders_rejected": reconciliation.orders_rejected,
            "total_trades_count": reconciliation.total_trades_count,
            "total_fills_count": reconciliation.total_fills_count,
            "open_positions": dict(reconciliation.open_positions),
        },
        "reconciliation": {
            "reconciled": reconciliation.reconciled,
            "discrepancy_paisa": _paisa_str(reconciliation.discrepancy_paisa),
            "reconciliation_errors": list(reconciliation.reconciliation_errors),
        },
        # The kill switch, surfaced in the payload so the exit path and the report can see it. A
        # halting session reconciles perfectly -- it refuses every order rather than mis-booking
        # one -- so a caller branching on `reconciled` alone reports the session that killed the
        # pilot as a success.
        # An aborted loop is reported as an abort. The session is still reconciled and persisted --
        # stopping short of that would lose the book -- but nothing downstream may call it clean.
        "unmarked_at_close": unmarked_at_close,
        "aborted": bool(session_abort_reason),
        "abort_reason": session_abort_reason,
        "risk": {
            "kill_switch_active": governor.is_killed,
            "halt_reason": (
                governor.kill_events[-1].reason
                if governor.is_killed and governor.kill_events
                else ""
            ),
            "orders_rejected": reconciliation.orders_rejected,
        },
        "fills": [
            {
                "fill_id": f.fill_id,
                "order_id": f.order_id,
                "symbol": f.symbol,
                "side": f.side.value,
                "quantity": f.quantity,
                "price": _paisa_str(f.price),
                "fee": _paisa_str(f.fee),
                "timestamp_ist": f.timestamp.astimezone(_IST).strftime("%Y-%m-%d %H:%M:%S IST"),
            }
            for f in engine.fills
        ],
        "audit_events_count": len(engine.audit_log),
    }

    # Save final JSON feedback
    json_path = output_dir / f"paper_session_{session_date}_{session_id}.json"
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(feedback_payload, f, indent=2)

    # Save final Markdown report in IST
    md_path = output_dir / f"paper_session_{session_date}_{session_id}.md"
    with open(md_path, "w", encoding="utf-8") as f:
        f.write(f"# QuantOS Paper Trading Session Report (IST) -- {session_id}\n\n")
        f.write(f"- **Session Date**: `{session_date}`\n")
        f.write("- **Timezone**: `Indian Standard Time (IST, UTC+05:30)`\n")
        f.write(
            f"- **Execution Interval**: `{current_ist.strftime('%H:%M:%S IST')}` to `{final_now.strftime('%H:%M:%S IST')}` (Market Close: `{close_dt_ist.strftime('%H:%M:%S IST')}`)\n"
        )
        f.write(f"- **Execution Model**: `{model.config.model_name}` (`{model.config.model_id}`)\n")
        f.write(f"- **Architecture**: `{model.config.model_type}`\n")
        rec_status = (
            f"PASS ({_paisa_str(reconciliation.discrepancy_paisa)} paisa discrepancy)"
            if reconciliation.reconciled
            else f"FAIL ({_paisa_str(reconciliation.discrepancy_paisa)} paisa discrepancy)"
        )
        f.write(f"- **Reconciliation Status**: **`{rec_status}`**\n\n")
        # A halted or aborted session reconciles perfectly -- it refuses orders rather than
        # mis-booking them -- so a report showing only the reconciliation status said PASS for
        # a session that had stopped the pilot. Both now appear above the numbers.
        if governor.is_killed:
            reason = governor.kill_events[-1].reason if governor.kill_events else "not recorded"
            f.write(
                f"- **RISK KILL SWITCH FIRED**: **`{reason}`**\n"
                f"- Orders refused this session: `{reconciliation.orders_rejected}`\n"
                "- Every later session is refused until this is cleared with "
                "`scripts/clear_paper_halt.py`.\n"
            )
        if session_abort_reason:
            f.write(
                f"- **SESSION ABORTED**: **`{session_abort_reason}`**\n"
                "- The figures below cover only the period before the abort.\n"
            )
        f.write("## 1. Capital & Financial Summary (IST)\n\n")
        f.write("| Metric | Value (Rs) |\n|---|---:|\n")
        f.write(f"| Initial Capital | Rs {_paisa_str(reconciliation.initial_cash)} |\n")
        f.write(f"| Final Cash | Rs {_paisa_str(reconciliation.final_cash)} |\n")
        f.write(f"| Total Portfolio Equity | Rs {_paisa_str(reconciliation.total_equity)} |\n")
        f.write(f"| Realized P&L | Rs {_paisa_str(reconciliation.total_realized_pnl)} |\n")
        f.write(f"| Unrealized P&L | Rs {_paisa_str(reconciliation.total_unrealized_pnl)} |\n")
        f.write(f"| Total Net P&L | Rs {_paisa_str(total_net_pnl)} ({return_pct:+.2f}%) |\n")
        f.write(f"| Total Statutory Fees | Rs {_paisa_str(reconciliation.total_fees_paid)} |\n")
        f.write(
            f"| Total Slippage Cost | Rs {_paisa_str(reconciliation.total_slippage_cost)} |\n\n"
        )

        f.write("## 2. Order Execution & Fills (IST)\n\n")
        f.write(f"- **Orders Submitted**: `{reconciliation.orders_submitted}`\n")
        f.write(f"- **Orders Filled**: `{reconciliation.orders_filled}`\n")
        f.write(f"- **Total Fills**: `{reconciliation.total_fills_count}`\n\n")
        f.write(
            "| Fill ID | Symbol | Side | Quantity | Price (Rs) | Statutory Fee (Rs) | Execution Time (IST) |\n|---|---|---|---:|---:|---:|---|\n"
        )
        for f_item in engine.fills:
            fill_ts_ist = f_item.timestamp.astimezone(_IST).strftime("%H:%M:%S IST")
            f.write(
                f"| `{f_item.fill_id}` | `{f_item.symbol}` | **{f_item.side.value}** | {f_item.quantity} | Rs {_paisa_str(f_item.price)} | Rs {_paisa_str(f_item.fee)} | `{fill_ts_ist}` |\n"
            )

        f.write("\n## 3. Ending Open Positions at Market Close\n\n")
        if reconciliation.open_positions:
            f.write(
                "| Symbol | Quantity | Close Price (Rs) | Market Value (Rs) |\n|---|---:|---:|---:|\n"
            )
            for sym, qty in reconciliation.open_positions.items():
                p = final_prices.get(sym, Decimal("0.00"))
                f.write(
                    f"| `{sym}` | {qty} | Rs {_paisa_str(p)} | Rs {_paisa_str(p * Decimal(qty))} |\n"
                )
        else:
            f.write("*(All positions closed / flat)*\n")

    # Update live status file to COMPLETED
    with open(status_file, "w", encoding="utf-8") as f:
        json.dump(
            {
                **rolling_status,
                # Not unconditionally COMPLETED. A halted or aborted session landed here as clean,
                # and three dashboard readers served that indefinitely.
                "status": (
                    "ABORTED"
                    if session_abort_reason
                    else "HALTED"
                    if governor.is_killed
                    else "COMPLETED"
                ),
                "kill_switch_active": governor.is_killed,
                "halt_reason": (
                    governor.kill_events[-1].reason
                    if governor.is_killed and governor.kill_events
                    else ""
                ),
                "abort_reason": session_abort_reason,
                "closed_at_ist": final_now.strftime("%Y-%m-%d %H:%M:%S IST"),
            },
            f,
            indent=2,
        )

    logger.info("Feedback JSON saved: %s", json_path)
    logger.info("Markdown Report saved: %s", md_path)

    return feedback_payload


def main() -> int:
    parser = argparse.ArgumentParser(description="QuantOS Quote-Driven Paper Pilot Runner (IST)")
    parser.add_argument("--date", type=str, default=None, help="Session date YYYY-MM-DD")
    parser.add_argument("--capital", type=float, default=1000000.0, help="Initial cash in INR")
    parser.add_argument(
        "--slippage-bps", type=float, default=5.0, help="Adverse slippage in basis points"
    )
    parser.add_argument(
        "--realtime", action="store_true", help="Run in continuous real-time mode until 15:30 IST"
    )
    parser.add_argument(
        "--interval-seconds",
        type=float,
        default=10.0,
        help="Seconds between trading loop iterations in realtime mode",
    )
    parser.add_argument(
        "--end-time-ist", type=str, default="15:30:00", help="Market close time in IST (HH:MM:SS)"
    )
    parser.add_argument(
        "--upstox-token", type=str, default=None, help="Upstox API Bearer Access Token"
    )
    parser.add_argument(
        "--model-profile",
        type=str,
        default="default",
        choices=["default", "sprint_50k"],
        help="Model profile (default or sprint_50k)",
    )
    parser.add_argument(
        "--universe-name",
        type=str,
        default="NIFTY500",
        choices=["NIFTY50", "NIFTY100", "NIFTY200", "NIFTY500"],
        help="Universe preset (NIFTY50, NIFTY100, NIFTY200, NIFTY500)",
    )
    parser.add_argument(
        "--sizing",
        choices=["equal-weight", "fixed"],
        default="equal-weight",
        help="equal-weight matches how the model was measured; fixed keeps a per-name stake",
    )
    parser.add_argument("--universe", type=str, nargs="+", default=None, help="Universe symbols")
    parser.add_argument("--output-dir", type=str, default=None, help="Output directory")

    args = parser.parse_args()

    s_date = None
    if args.date:
        try:
            s_date = date.fromisoformat(args.date)
        except ValueError:
            logger.error("Invalid date '%s'. Format must be YYYY-MM-DD", args.date)
            return 1

    out_p = Path(args.output_dir) if args.output_dir else None

    try:
        res = run_paper_session(
            session_date=s_date,
            sizing=args.sizing,
            universe=args.universe,
            universe_name=args.universe_name,
            model_profile=args.model_profile,
            initial_cash=Decimal(str(args.capital)),
            slippage_bps=Decimal(str(args.slippage_bps)),
            realtime=args.realtime,
            interval_seconds=args.interval_seconds,
            end_time_str=args.end_time_ist,
            upstox_token=args.upstox_token,
            output_dir=out_p,
        )
        # A failed reconciliation used to print SUCCESS and exit 0, next to a hardcoded
        # "(0.00 Paisa Discrepancy)" that was printed whether or not the discrepancy was zero. The
        # one number that would have revealed the failure was the one replaced by a constant.
        reconciled = bool(res["reconciliation"]["reconciled"])
        discrepancy = res["reconciliation"]["discrepancy_paisa"]
        # A halting session reconciles cleanly, so branching on `reconciled` alone printed
        # SUCCESS and exited 0 for the session that permanently stopped the pilot. On an
        # unattended schedule that green exit was the operator's only signal.
        halted = bool(res.get("risk", {}).get("kill_switch_active"))
        aborted = bool(res.get("aborted"))
        if aborted:
            banner = "[PAPER PILOT ABORTED]"
        elif not reconciled:
            banner = "[PAPER PILOT RECONCILIATION FAILED]"
        elif halted:
            banner = "[PAPER PILOT HALTED BY RISK KILL SWITCH]"
        else:
            banner = "[PAPER PILOT SUCCESS]"
        print(f"\n{banner} Session {res['session_id']}.")
        print(f"Timezone: {res['timezone']}")
        print(f"Active Period: {res['started_at_ist']} -> {res['closed_at_ist']}")
        print(
            f"Reconciliation: {'PASS' if reconciled else 'FAIL'} ({discrepancy} paisa discrepancy)"
        )
        print(
            f"Total Equity: Rs {res['capital']['total_equity']} (Net P&L: Rs {res['performance']['total_net_pnl']})"
        )
        print(f"Fills Executed: {res['order_statistics']['total_fills_count']}")
        print(
            f"Evidence Report: logs/paper_runs/paper_session_{res['session_date']}_{res['session_id']}.md"
        )
        if aborted:
            print(f"ABORTED: {res['abort_reason']}")
            print("The session did not run to the close. Its report covers only the period before")
            print("the abort, and the persisted portfolio reflects that shortened session.")
            return 10
        if not reconciled:
            for error in res["reconciliation"]["reconciliation_errors"]:
                print(f"  - {error}")
            return 7
        if halted:
            print(f"RISK HALT: {res['risk']['halt_reason']}")
            print(f"Orders refused this session: {res['risk']['orders_rejected']}")
            print("Every later session is refused until this is reviewed and cleared:")
            print("    python scripts/clear_paper_halt.py --i-have-reviewed-the-book")
            return 9
        return 0
    except Exception as err:
        logger.exception("Paper session failed with error: %s", err)
        return 2


if __name__ == "__main__":
    sys.exit(main())
