"""The proof for any stock, the cheap status for a list of stocks, and what the filings cover.

Every number comes from one place. `proof()` works a stock out once; `statuses()` reads the same finished proofs, so
a badge and the proof it links to can never disagree. Finished proofs are kept per stock and per version of what
they were worked out from, so a list of 200 badges does not work out 200 proofs on every request.
"""

from __future__ import annotations

import copy
import logging
import sqlite3
import threading
from collections import OrderedDict
from collections.abc import Callable, Sequence
from datetime import UTC, date, datetime, timedelta
from typing import Any

from quant_system.shariah.filings.models import FilingFigures, normalize_symbol
from quant_system.shariah.filings.nse_client import InvalidSymbol
from quant_system.shariah.filings.status import data_status_for
from quant_system.shariah.filings.store import FilingsStore
from quant_system.shariah.services.activity_check import ActivityResult
from quant_system.shariah.services.proof_builder import build_stock_proof
from quant_system.shariah.services.proof_inputs import (
    USABLE,
    Held,
    activity_for,
    company_name_of,
    filing_inputs,
    with_note,
)
from quant_system.shariah.services.proof_market import (
    WINDOW_MONTHS,
    BarsSource,
    PriceHistory,
    average_market_value,
    months_before,
)
from quant_system.shariah.services.proof_paths import listed_equities_count
from quant_system.shariah.services.proof_samples import SampleSource
from quant_system.shariah.services.proof_short import status_row
from quant_system.shariah.services.proof_types import ProofInputs
from quant_system.shariah.services.proof_unscreened import filing_note, finish_unscreened

__all__ = ["MAX_STATUS_SYMBOLS", "Clock", "ProofService", "TooManySymbols"]

logger = logging.getLogger(__name__)

Clock = Callable[[], datetime]
CACHE_SIZE = 1024
MAX_STATUS_SYMBOLS = 200
#: Prices are fetched this far back so a window that ends at the newest price (up to a year old) still fits.
PRICE_LOOKBACK_MONTHS = WINDOW_MONTHS + 14
NO_BUNDLE = (
    "This copy of QuantOS has no bundled company filings yet. "
    "Filings you fetch from NSE are saved on this computer."
)
NO_BUNDLE_GAP = "This copy of QuantOS has no bundled company filings yet."
_BAD_SYMBOL_ROW = {
    "verdict": "NOT_SCREENED",
    "data_status": "NOT_SCREENED",
    "short": "Not a valid stock symbol.",
    "as_of": None,
}


class TooManySymbols(ValueError):
    """More stocks were asked about at once than one call answers."""


def _checked(symbol: str) -> str:
    clean = normalize_symbol(symbol.strip().removesuffix(".NS").removesuffix(".ns"))
    if clean is None:
        raise InvalidSymbol
    return clean


def _fingerprint(figures: FilingFigures | None) -> tuple[Any, ...] | None:
    """What identifies the filing a proof was worked out from: a new or different filing is a new proof."""
    if figures is None:
        return None
    proof = figures.proof
    return (proof.sha256, proof.period_end, figures.read_status.value, proof.consolidated)


class ProofService:
    def __init__(
        self,
        filings_store: FilingsStore,
        sample_source: SampleSource,
        bars_source: BarsSource | None,
        clock: Clock,
    ) -> None:
        self._store = filings_store
        self._samples = sample_source
        self._bars = bars_source
        self._clock = clock
        self._cache: OrderedDict[tuple[Any, ...], dict[str, Any]] = OrderedDict()
        self._lock = threading.Lock()

    # -- what callers use ------------------------------------------------------------------------
    def proof(self, symbol: str) -> dict[str, Any]:
        """The proof for one stock. Raises InvalidSymbol for something that is not an NSE symbol."""
        return copy.deepcopy(self._screen(_checked(symbol)))

    def filing_proof(self, symbol: str) -> dict[str, Any] | None:
        """The proof, only when it rests on a company filing (current or old). None for anything else."""
        clean = _checked(symbol)
        today = self._clock().astimezone(UTC).date()
        if data_status_for(self._store.get(clean), today) not in USABLE:
            return None
        return copy.deepcopy(self._screen(clean))

    def statuses(self, symbols: Sequence[str]) -> dict[str, dict[str, Any]]:
        """The verdict, data status, short reason and figures date for each stock, from the same proofs."""
        if len(symbols) > MAX_STATUS_SYMBOLS:
            raise TooManySymbols(f"Ask about at most {MAX_STATUS_SYMBOLS} stocks at a time.")
        rows: dict[str, dict[str, Any]] = {}
        for asked in symbols:
            key = asked.strip().upper()
            try:
                rows[key] = status_row(self._screen(_checked(key)))
            except InvalidSymbol:
                rows[key] = dict(_BAD_SYMBOL_ROW)
        return rows

    def coverage(self) -> dict[str, Any]:
        """How many stocks are screened from a filing, how many NSE lists, and how new the filings are."""
        held = self._store.coverage()
        return {
            "screened": held["screened"],
            "total_listed": listed_equities_count(),
            "newest_filing": held["newest_filing"],
            "snapshot_built_on": held["snapshot_built_on"],
            "note": NO_BUNDLE if held["snapshot_built_on"] is None else None,
        }

    # -- working a proof out ---------------------------------------------------------------------
    def _screen(self, symbol: str) -> dict[str, Any]:
        figures = self._store.get(symbol)
        group = self._store.industry_group(symbol)
        now = self._clock().astimezone(UTC)
        key = (symbol, _fingerprint(figures), group, now.date(), self._price_version())
        with self._lock:
            if key in self._cache:
                self._cache.move_to_end(key)
                return self._cache[key]
        held = Held(
            symbol, figures, data_status_for(figures, now.date()), group, self._sample(symbol)
        )
        proof = self._build(held, now)
        with self._lock:
            self._cache[key] = proof
            while len(self._cache) > CACHE_SIZE:
                self._cache.popitem(last=False)
        return proof

    def _sample(self, symbol: str) -> dict[str, Any] | None:
        try:
            return self._samples.company(symbol)
        except sqlite3.Error:
            logger.warning("the halal sample could not be read for %s", symbol, exc_info=True)
            return None

    def _build(self, held: Held, now: datetime) -> dict[str, Any]:
        stamp = now.strftime("%Y-%m-%dT%H:%M:%SZ")
        activity = activity_for(held, company_name_of(held))
        if held.usable:
            return self._from_filing(held, activity, stamp, now.date())
        return self._without_filing(held, activity, stamp)

    def _from_filing(
        self, held: Held, activity: ActivityResult, stamp: str, today: date
    ) -> dict[str, Any]:
        shares = held.usable_figures.shares_in_issue if held.usable_figures else None
        market = average_market_value(held.symbol, self._history(held.symbol, today), shares, today)
        proof = build_stock_proof(filing_inputs(held, activity, market.value, stamp))
        return with_note(proof, market.reason)

    def _without_filing(self, held: Held, activity: ActivityResult, stamp: str) -> dict[str, Any]:
        """The hand-entered sample when there is one, else a business-only verdict or "not screened"."""
        name = company_name_of(held)
        status = "UNVERIFIED_SAMPLE" if held.sample is not None else "NOT_SCREENED"
        inputs = ProofInputs(held.symbol, name, activity, status, stamp, sample=held.sample)
        proof = build_stock_proof(inputs)
        if held.sample is None:
            proof = finish_unscreened(proof, activity, held.figures, name)
        elif held.figures is not None:
            proof = with_note(proof, filing_note(held.figures))
        built = self._store.coverage()["snapshot_built_on"]
        return with_note(proof, NO_BUNDLE_GAP if built is None and held.figures is None else None)

    def _price_version(self) -> str | None:
        """Which build of the price data the proofs rest on, so prices loaded later are not missed. None if unknown."""
        version = getattr(self._bars, "version", None)
        if not callable(version):
            return None
        try:
            return str(version())
        except (OSError, RuntimeError, sqlite3.Error):
            return None

    def _history(self, symbol: str, today: date) -> PriceHistory | None:
        """The stock's daily prices from the platform's own market data, or None when it has none."""
        if self._bars is None:
            return None
        start = months_before(today, PRICE_LOOKBACK_MONTHS)
        try:
            return self._bars.bars(
                symbol, start.isoformat(), (today + timedelta(days=1)).isoformat()
            )
        except (LookupError, RuntimeError, OSError, sqlite3.Error):
            return None
