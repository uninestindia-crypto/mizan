"""Recorded historical quote replay feed with strict point-in-time and integrity enforcement."""

from __future__ import annotations

from collections.abc import Iterator, Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal, InvalidOperation
from enum import StrEnum
from typing import Any

from quant_system.core.domain import Quote
from quant_system.evidence.canonical import sha256_hex


class ReplayFeedFailureCode(StrEnum):
    """Typed fail-closed failure codes for recorded quote streams."""

    OUT_OF_ORDER_TIMESTAMP = "OUT_OF_ORDER_TIMESTAMP"
    DUPLICATE_TICK = "DUPLICATE_TICK"
    CORRUPTED_PAYLOAD = "CORRUPTED_PAYLOAD"
    CROSSED_BOOK = "CROSSED_BOOK"
    ZERO_LIQUIDITY = "ZERO_LIQUIDITY"
    STALE_QUOTE = "STALE_QUOTE"
    FEED_HALTED = "FEED_HALTED"
    FEED_OFFLINE = "FEED_OFFLINE"
    FEED_EXHAUSTED = "FEED_EXHAUSTED"
    SCHEMA_VIOLATION = "SCHEMA_VIOLATION"


class ReplayFeedError(RuntimeError):
    """Fail-closed exception for quote replay stream errors."""

    def __init__(
        self,
        code: ReplayFeedFailureCode,
        message: str,
        *,
        offending_record: Any | None = None,
        sequence_id: int | None = None,
    ) -> None:
        self.code = code
        self.offending_record = offending_record
        self.sequence_id = sequence_id
        detail = f"{code.value}: {message}"
        if sequence_id is not None:
            detail = f"{detail} (seq={sequence_id})"
        super().__init__(detail)


class FeedState(StrEnum):
    """Operational lifecycle state of the replay feed."""

    READY = "READY"
    STREAMING = "STREAMING"
    HALTED = "HALTED"
    OFFLINE = "OFFLINE"
    EXHAUSTED = "EXHAUSTED"


@dataclass(frozen=True, slots=True)
class QuoteProvenance:
    """Provenance metadata describing the recorded historical source."""

    provider: str
    feed_id: str
    source_file: str | None = None
    is_synthetic: bool = False
    ingestion_timestamp: datetime | None = None


@dataclass(frozen=True, slots=True)
class ReplayQuote:
    """A validated point-in-time quote record in a recorded replay stream."""

    symbol: str
    timestamp: datetime
    bid: Decimal
    ask: Decimal
    bid_size: int = 0
    ask_size: int = 0
    last_price: Decimal | None = None
    sequence_id: int = 1
    provenance: QuoteProvenance | None = None
    payload_digest: str = ""

    @property
    def mid_price(self) -> Decimal:
        return (self.bid + self.ask) / Decimal("2")

    @property
    def spread(self) -> Decimal:
        return self.ask - self.bid

    @property
    def spread_pct(self) -> Decimal:
        if self.mid_price <= Decimal("0"):
            return Decimal("0")
        return self.spread / self.mid_price

    def to_domain_quote(self) -> Quote:
        """Convert into the core domain Quote representation."""
        return Quote(
            symbol=self.symbol,
            timestamp=self.timestamp,
            bid=self.bid,
            ask=self.ask,
            bid_size=self.bid_size,
            ask_size=self.ask_size,
            last_price=self.last_price,
        )


def _parse_size(raw: Any, field_name: str, symbol: str, seq: int) -> int:
    """Strictly convert a displayed size into int, rejecting floats.

    `int(3.9)` silently discarded displayed depth while float *prices* were refused, so the same
    payload was strict about one field and lax about another (S8-M4). Depth drives fill
    simulation, so truncating it changes results with no signal.
    """
    if isinstance(raw, float):
        raise ReplayFeedError(
            ReplayFeedFailureCode.CORRUPTED_PAYLOAD,
            f"Binary float is forbidden for size field '{field_name}' on {symbol}",
            sequence_id=seq,
        )
    if isinstance(raw, bool) or not isinstance(raw, int):
        try:
            text = str(raw).strip()
            if not text.lstrip("-").isdigit():
                raise ValueError("not an integer")
            return int(text)
        except (ValueError, TypeError) as err:
            raise ReplayFeedError(
                ReplayFeedFailureCode.CORRUPTED_PAYLOAD,
                f"Size field '{field_name}' on {symbol} is not an integer: {raw!r}",
                sequence_id=seq,
            ) from err
    return raw


def _parse_decimal(raw: Any, field_name: str, symbol: str) -> Decimal:
    """Strictly convert price into Decimal, rejecting float or non-finite values."""
    if isinstance(raw, float):
        raise ReplayFeedError(
            ReplayFeedFailureCode.CORRUPTED_PAYLOAD,
            f"Binary float is forbidden for price field '{field_name}' on {symbol}",
        )
    try:
        val = Decimal(str(raw)) if not isinstance(raw, Decimal) else raw
        if not val.is_finite():
            raise ValueError("non-finite Decimal")
        return val
    except (InvalidOperation, ValueError, TypeError) as err:
        raise ReplayFeedError(
            ReplayFeedFailureCode.CORRUPTED_PAYLOAD,
            f"Invalid numeric value '{raw}' for field '{field_name}' on {symbol}",
        ) from err


def _validate_quote_invariants(
    symbol: str,
    bid: Decimal,
    ask: Decimal,
    bid_size: int,
    ask_size: int,
) -> None:
    """Enforces non-negative prices, non-negative sizes, and uncrossed book."""
    if bid < Decimal("0") or ask < Decimal("0"):
        raise ReplayFeedError(
            ReplayFeedFailureCode.CORRUPTED_PAYLOAD,
            f"Negative bid ({bid}) or ask ({ask}) for {symbol}",
        )
    if bid == Decimal("0") and ask == Decimal("0"):
        raise ReplayFeedError(
            ReplayFeedFailureCode.ZERO_LIQUIDITY,
            f"Zero liquidity (bid=0, ask=0) for {symbol}",
        )
    if ask < bid:
        raise ReplayFeedError(
            ReplayFeedFailureCode.CROSSED_BOOK,
            f"Crossed book: ask ({ask}) < bid ({bid}) for {symbol}",
        )
    if bid_size < 0 or ask_size < 0:
        raise ReplayFeedError(
            ReplayFeedFailureCode.CORRUPTED_PAYLOAD,
            f"Negative bid_size ({bid_size}) or ask_size ({ask_size}) for {symbol}",
        )


class ReplayQuoteFeed:
    """Historical quote replay stream enforcing point-in-time chronology and fail-closed halts."""

    def __init__(
        self,
        quotes: Sequence[Quote | ReplayQuote | Mapping[str, Any]],
        provenance: QuoteProvenance | None = None,
        max_allowed_staleness_seconds: float | None = None,
        max_spread_pct: float | None = None,
    ) -> None:
        self._raw_quotes: list[Quote | ReplayQuote | Mapping[str, Any]] = list(quotes)
        self._provenance = provenance or QuoteProvenance(
            provider="RECORDED_REPLAY",
            feed_id="recorded_feed_v1",
        )
        self._max_allowed_staleness_seconds = max_allowed_staleness_seconds
        self._max_spread_pct = max_spread_pct
        self._state: FeedState = FeedState.READY
        self._cursor: int = 0
        self._previous_tick: ReplayQuote | None = None
        self._last_tick_by_symbol: dict[str, ReplayQuote] = {}
        self._seen_signatures: set[tuple[str, datetime, Decimal, Decimal]] = set()
        self._halt_reason: str | None = None

    @property
    def state(self) -> FeedState:
        return self._state

    @property
    def halt_reason(self) -> str | None:
        return self._halt_reason

    @property
    def total_emitted(self) -> int:
        return self._cursor

    def reset(self) -> None:
        """Resets the replay feed cursor to the beginning for deterministic replay."""
        self._state = FeedState.READY
        self._cursor = 0
        self._previous_tick = None
        self._last_tick_by_symbol.clear()
        self._seen_signatures.clear()
        self._halt_reason = None

    def simulate_disconnect(self, reason: str = "FEED_DISCONNECTED") -> None:
        """Transitions the stream into OFFLINE state to simulate connection drops."""
        self._state = FeedState.OFFLINE
        self._halt_reason = reason

    def halt(self, reason: str = "FEED_HALTED") -> None:
        """Explicitly halts the feed."""
        self._state = FeedState.HALTED
        self._halt_reason = reason

    def __iter__(self) -> Iterator[ReplayQuote]:
        return self

    def __next__(self) -> ReplayQuote:
        return self.next_tick()

    def next_tick(self) -> ReplayQuote:
        """Fetches and validates the next quote in the recorded stream."""
        if self._state == FeedState.OFFLINE:
            raise ReplayFeedError(
                ReplayFeedFailureCode.FEED_OFFLINE,
                f"Cannot stream from offline feed: {self._halt_reason}",
            )
        if self._state == FeedState.HALTED:
            raise ReplayFeedError(
                ReplayFeedFailureCode.FEED_HALTED,
                f"Cannot stream from halted feed: {self._halt_reason}",
            )
        if self._cursor >= len(self._raw_quotes):
            self._state = FeedState.EXHAUSTED
            raise StopIteration

        self._state = FeedState.STREAMING
        raw = self._raw_quotes[self._cursor]
        seq = self._cursor + 1

        try:
            tick = self._validate_and_build_tick(raw, seq)
            self._check_sequence_invariants(tick, seq)
        except ReplayFeedError as err:
            self._state = FeedState.HALTED
            self._halt_reason = str(err)
            raise

        self._previous_tick = tick
        self._last_tick_by_symbol[tick.symbol] = tick
        self._seen_signatures.add((tick.symbol, tick.timestamp, tick.bid, tick.ask))
        self._cursor += 1
        return tick

    def _validate_and_build_tick(
        self,
        raw: Quote | ReplayQuote | Mapping[str, Any],
        seq: int,
    ) -> ReplayQuote:
        """Normalizes and checks internal fields of the raw quote."""
        if isinstance(raw, ReplayQuote):
            symbol = raw.symbol
            ts = raw.timestamp
            bid = raw.bid
            ask = raw.ask
            bid_sz = raw.bid_size
            ask_sz = raw.ask_size
            last_p = raw.last_price
        elif isinstance(raw, Quote):
            symbol = raw.symbol
            ts = raw.timestamp
            bid = raw.bid
            ask = raw.ask
            bid_sz = raw.bid_size
            ask_sz = raw.ask_size
            last_p = raw.last_price
        elif isinstance(raw, Mapping):
            if (
                "symbol" not in raw
                or "timestamp" not in raw
                or "bid" not in raw
                or "ask" not in raw
            ):
                raise ReplayFeedError(
                    ReplayFeedFailureCode.SCHEMA_VIOLATION,
                    f"Missing required quote fields in record at seq={seq}",
                    sequence_id=seq,
                )
            symbol = str(raw["symbol"])
            raw_ts = raw["timestamp"]
            ts = datetime.fromisoformat(raw_ts) if isinstance(raw_ts, str) else raw_ts
            bid = _parse_decimal(raw["bid"], "bid", symbol)
            ask = _parse_decimal(raw["ask"], "ask", symbol)
            bid_sz = _parse_size(raw.get("bid_size", 0), "bid_size", symbol, seq)
            ask_sz = _parse_size(raw.get("ask_size", 0), "ask_size", symbol, seq)
            raw_last = raw.get("last_price")
            last_p = (
                _parse_decimal(raw_last, "last_price", symbol) if raw_last is not None else None
            )
        else:
            raise ReplayFeedError(
                ReplayFeedFailureCode.SCHEMA_VIOLATION,
                f"Unsupported quote payload type {type(raw).__name__} at seq={seq}",
                sequence_id=seq,
            )

        _validate_quote_invariants(symbol, bid, ask, bid_sz, ask_sz)

        digest = sha256_hex(f"{symbol}:{ts.isoformat()}:{bid}:{ask}:{bid_sz}:{ask_sz}".encode())
        return ReplayQuote(
            symbol=symbol,
            timestamp=ts,
            bid=bid,
            ask=ask,
            bid_size=bid_sz,
            ask_size=ask_sz,
            last_price=last_p,
            sequence_id=seq,
            provenance=self._provenance,
            payload_digest=digest,
        )

    def _check_sequence_invariants(self, tick: ReplayQuote, seq: int) -> None:
        """Enforces monotonic time, duplicate tick checks, and staleness bounds."""
        if self._max_spread_pct is not None and tick.spread_pct > Decimal(
            str(self._max_spread_pct)
        ):
            raise ReplayFeedError(
                ReplayFeedFailureCode.CROSSED_BOOK,
                f"Spread {tick.spread_pct:.2%} exceeds max allowed {self._max_spread_pct:.2%}",
                sequence_id=seq,
            )

        if self._previous_tick is None and tick.symbol not in self._last_tick_by_symbol:
            return

        self._check_time_order(tick, seq)
        self._check_duplicate(tick, seq)
        self._check_staleness(tick, seq)

    def _check_time_order(self, tick: ReplayQuote, seq: int) -> None:
        if self._previous_tick is not None and tick.timestamp < self._previous_tick.timestamp:
            raise ReplayFeedError(
                ReplayFeedFailureCode.OUT_OF_ORDER_TIMESTAMP,
                f"Out of order timestamp: {tick.timestamp} < {self._previous_tick.timestamp}",
                sequence_id=seq,
            )

    def _check_duplicate(self, tick: ReplayQuote, seq: int) -> None:
        sig = (tick.symbol, tick.timestamp, tick.bid, tick.ask)
        if sig in self._seen_signatures:
            raise ReplayFeedError(
                ReplayFeedFailureCode.DUPLICATE_TICK,
                f"Duplicate tick detected for {tick.symbol} at {tick.timestamp}",
                sequence_id=seq,
            )

    def _check_staleness(self, tick: ReplayQuote, seq: int) -> None:
        if self._max_allowed_staleness_seconds is None:
            return
        last_sym_tick = self._last_tick_by_symbol.get(tick.symbol)
        if last_sym_tick is not None:
            gap = (tick.timestamp - last_sym_tick.timestamp).total_seconds()
            if gap > self._max_allowed_staleness_seconds:
                raise ReplayFeedError(
                    ReplayFeedFailureCode.STALE_QUOTE,
                    f"Quote gap {gap:.1f}s for {tick.symbol} exceeds staleness threshold {self._max_allowed_staleness_seconds:.1f}s",
                    sequence_id=seq,
                )
