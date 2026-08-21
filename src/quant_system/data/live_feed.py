"""Strict read-only real-time Upstox market-data streaming feed with freshness enforcement."""

from __future__ import annotations

import json
from collections.abc import Callable, Iterator, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation
from enum import StrEnum
from typing import Any, Protocol

from quant_system.core.domain import Quote
from quant_system.data.upstox_failures import require_aware_utc


class FeedState(StrEnum):
    """Lifecycle states of the real-time market data feed."""

    DISCONNECTED = "DISCONNECTED"
    CONNECTING = "CONNECTING"
    CONNECTED = "CONNECTED"
    AUTHENTICATED = "AUTHENTICATED"
    STREAMING = "STREAMING"
    HALTED = "HALTED"
    UNAUTHORIZED = "UNAUTHORIZED"
    OFFLINE = "OFFLINE"


class FeedQualityCode(StrEnum):
    """Quality and failure codes for real-time feed events."""

    STALE_QUOTE = "STALE_QUOTE"
    CLOCK_DRIFT = "CLOCK_DRIFT"
    CROSSED_QUOTE = "CROSSED_QUOTE"
    NEGATIVE_PRICE = "NEGATIVE_PRICE"
    INVALID_TIMESTAMP = "INVALID_TIMESTAMP"
    SCHEMA_DRIFT = "SCHEMA_DRIFT"
    MALFORMED_PAYLOAD = "MALFORMED_PAYLOAD"
    DISCONNECTED = "DISCONNECTED"
    TIMEOUT = "TIMEOUT"
    UNAUTHORIZED = "UNAUTHORIZED"


class LiveFeedError(Exception):
    """Base error for live market data feed failures."""


class LiveFeedUnauthorizedError(LiveFeedError):
    """Raised when authentication credentials are missing, invalid, or expired."""

    def __init__(
        self, message: str = "Live feed authentication token is missing or expired."
    ) -> None:
        super().__init__(message)


class LiveFeedStaleQuoteError(LiveFeedError):
    """Raised when an incoming quote breaches the freshness latency budget."""

    def __init__(
        self,
        message: str,
        *,
        observed_latency_seconds: float,
        max_latency_seconds: float,
        quote_timestamp: datetime,
        received_at: datetime,
    ) -> None:
        super().__init__(message)
        self.observed_latency_seconds = observed_latency_seconds
        self.max_latency_seconds = max_latency_seconds
        self.quote_timestamp = quote_timestamp
        self.received_at = received_at


class LiveFeedClockDriftError(LiveFeedError):
    """Raised when an incoming quote timestamp is too far ahead of local clock."""

    def __init__(
        self,
        message: str,
        *,
        observed_drift_seconds: float,
        max_drift_seconds: float,
        quote_timestamp: datetime,
        received_at: datetime,
    ) -> None:
        super().__init__(message)
        self.observed_drift_seconds = observed_drift_seconds
        self.max_drift_seconds = max_drift_seconds
        self.quote_timestamp = quote_timestamp
        self.received_at = received_at


class LiveFeedConnectionError(LiveFeedError):
    """Raised when the streaming connection fails or disconnects."""

    def __init__(self, message: str, *, disconnected_at: datetime) -> None:
        super().__init__(message)
        self.disconnected_at = disconnected_at


class LiveFeedTimeoutError(LiveFeedError):
    """Raised when no quote or heartbeat is received within the timeout budget."""

    def __init__(self, message: str, *, timeout_seconds: float) -> None:
        super().__init__(message)
        self.timeout_seconds = timeout_seconds


class LiveFeedMalformedError(LiveFeedError):
    """Raised when the streaming payload is malformed or unparseable."""

    def __init__(self, message: str, *, raw_payload: bytes | str | None = None) -> None:
        super().__init__(message)
        self.raw_payload = raw_payload


class LiveFeedSchemaDriftError(LiveFeedError):
    """Raised when the streaming payload schema changes unexpectedly."""


class LiveFeedQualityError(LiveFeedError):
    """Raised when market data quality invariants are violated (e.g. crossed quote)."""

    def __init__(self, message: str, *, code: FeedQualityCode) -> None:
        super().__init__(message)
        self.code = code


@dataclass(frozen=True, slots=True)
class LiveQuoteRecord:
    """Point-in-time real-time quote record with complete timestamp provenance."""

    instrument_key: str
    symbol: str
    bid: Decimal
    ask: Decimal
    bid_size: int
    ask_size: int
    last_price: Decimal | None
    event_at: datetime
    received_at: datetime
    provider_at: datetime | None = None
    sequence_number: int | None = None
    source: str = "UPSTOX_LIVE_FEED_V3"

    def __post_init__(self) -> None:
        if self.event_at.tzinfo is None or self.event_at.utcoffset() is None:
            raise ValueError(f"event_at must be timezone-aware for {self.symbol}")
        if self.received_at.tzinfo is None or self.received_at.utcoffset() is None:
            raise ValueError(f"received_at must be timezone-aware for {self.symbol}")
        if self.bid < Decimal("0") or self.ask < Decimal("0"):
            raise ValueError(f"bid and ask must be non-negative for {self.symbol}")
        if self.ask < self.bid:
            raise ValueError(f"ask {self.ask} cannot be less than bid {self.bid} for {self.symbol}")
        if self.bid_size < 0 or self.ask_size < 0:
            raise ValueError(f"quote sizes cannot be negative for {self.symbol}")
        if self.last_price is not None and self.last_price <= Decimal("0"):
            raise ValueError(f"last_price must be strictly positive for {self.symbol}")

    @property
    def latency_seconds(self) -> float:
        """Latency between exchange/provider event time and local ingestion time."""
        return (self.received_at - self.event_at).total_seconds()

    @property
    def spread(self) -> Decimal:
        return self.ask - self.bid

    @property
    def mid_price(self) -> Decimal:
        return (self.bid + self.ask) / Decimal("2")

    def to_domain_quote(self) -> Quote:
        """Converts into standard domain Quote representation."""
        return Quote(
            symbol=self.symbol,
            timestamp=self.event_at,
            bid=self.bid,
            ask=self.ask,
            bid_size=self.bid_size,
            ask_size=self.ask_size,
            last_price=self.last_price,
        )


class LiveStreamTransport(Protocol):
    """Protocol for streaming websocket / connection transport."""

    def connect(self, url: str, headers: Mapping[str, str] | None = None) -> None: ...
    def send(self, data: str | bytes) -> None: ...
    def receive(self, timeout_seconds: float | None = None) -> bytes | str: ...
    def close(self) -> None: ...
    def is_connected(self) -> bool: ...


@dataclass(frozen=True, slots=True)
class LiveFeedDependencies:
    """Injected I/O dependencies for deterministic testing and timing control."""

    transport: LiveStreamTransport
    clock: Callable[[], datetime]
    sleeper: Callable[[float], None] = field(default=lambda _: None)


@dataclass(frozen=True, slots=True)
class LiveFeedConfig:
    """Configuration for real-time streaming feed."""

    max_latency_seconds: float = 5.0
    max_clock_drift_seconds: float = 1.0
    heartbeat_timeout_seconds: float = 10.0
    ws_url: str = "wss://api.upstox.com/v3/feed/market-data-feed"


def parse_upstox_feed_message(
    payload: bytes | str | dict[str, Any],
    *,
    received_at: datetime,
    symbol_map: Mapping[str, str] | None = None,
) -> list[LiveQuoteRecord]:
    """Parse Upstox V3 streaming message payload into validated LiveQuoteRecord items."""
    s_map = symbol_map or {}
    if isinstance(payload, bytes):
        if payload.lstrip().startswith(b"<"):
            raise LiveFeedMalformedError(
                "provider returned HTML body instead of feed JSON", raw_payload=payload
            )
        try:
            data = json.loads(payload.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as err:
            raise LiveFeedMalformedError(
                f"malformed json payload: {err}", raw_payload=payload
            ) from err
    elif isinstance(payload, str):
        if payload.lstrip().startswith("<"):
            raise LiveFeedMalformedError(
                "provider returned HTML body instead of feed JSON", raw_payload=payload
            )
        try:
            data = json.loads(payload)
        except json.JSONDecodeError as err:
            raise LiveFeedMalformedError(
                f"malformed json payload: {err}", raw_payload=payload
            ) from err
    elif isinstance(payload, dict):
        data = payload
    else:
        raise LiveFeedMalformedError("unsupported payload type")

    records: list[LiveQuoteRecord] = []

    # Handle direct quote dictionary format
    if "instrument_key" in data and ("bid" in data or "ask" in data or "ltp" in data):
        record = _parse_single_quote_dict(data, received_at=received_at, symbol_map=s_map)
        return [record]

    # Handle feeds wrapper: {"type": "live_feed", "feeds": { ... }}
    feeds_container = data.get("feeds") if isinstance(data, dict) else None
    if isinstance(feeds_container, dict):
        for instrument_key, feed_item in feeds_container.items():
            record = _parse_feed_entry(
                instrument_key, feed_item, received_at=received_at, symbol_map=s_map
            )
            records.append(record)
        return records

    # Handle direct feed map: {"NSE_EQ|...": { ... }}
    if isinstance(data, dict) and any("|" in k for k in data.keys()):
        for instrument_key, feed_item in data.items():
            if isinstance(feed_item, dict):
                record = _parse_feed_entry(
                    instrument_key, feed_item, received_at=received_at, symbol_map=s_map
                )
                records.append(record)
        return records

    raise LiveFeedSchemaDriftError("unrecognized Upstox feed payload structure")


def _parse_feed_entry(
    instrument_key: str,
    feed_item: Any,
    *,
    received_at: datetime,
    symbol_map: Mapping[str, str],
) -> LiveQuoteRecord:
    if not isinstance(feed_item, dict):
        raise LiveFeedSchemaDriftError(f"feed item for {instrument_key} must be an object")

    # Unwrap full_feed / market_data if nested
    full_feed = feed_item.get("full_feed")
    if isinstance(full_feed, dict):
        market_data = full_feed.get("market_data", full_feed)
    else:
        market_data = feed_item.get("market_data", feed_item)

    symbol = symbol_map.get(instrument_key, instrument_key.split("|")[-1])

    # Extract timestamp
    raw_ts = market_data.get("timestamp") or feed_item.get("timestamp")
    if not raw_ts:
        raise LiveFeedSchemaDriftError(f"missing timestamp in feed item for {instrument_key}")
    try:
        if isinstance(raw_ts, (int, float)):
            # Epoch milliseconds or seconds
            ts_sec = float(raw_ts) / 1000.0 if raw_ts > 1e11 else float(raw_ts)
            event_at = datetime.fromtimestamp(ts_sec, tz=UTC)
        elif isinstance(raw_ts, str):
            event_at = datetime.fromisoformat(raw_ts.replace("Z", "+00:00")).astimezone(UTC)
        else:
            raise LiveFeedSchemaDriftError(f"invalid timestamp format for {instrument_key}")
    except (ValueError, TypeError, OSError) as err:
        raise LiveFeedSchemaDriftError(
            f"unparseable timestamp for {instrument_key}: {err}"
        ) from err

    # Extract bid / ask / sizes from market depth or direct fields
    depth = market_data.get("market_depth") or market_data.get("depth")
    bid: Decimal
    ask: Decimal
    bid_size: int = 0
    ask_size: int = 0

    if isinstance(depth, dict):
        buy_orders = depth.get("buy", [])
        sell_orders = depth.get("sell", [])
        if buy_orders and isinstance(buy_orders, list) and len(buy_orders) > 0:
            bid = _parse_decimal(buy_orders[0].get("price", 0), "bid")
            bid_size = _parse_int(buy_orders[0].get("quantity", 0), "bid_size")
        else:
            bid = _parse_decimal(market_data.get("bid", 0), "bid")
            bid_size = _parse_int(market_data.get("bid_size", 0), "bid_size")

        if sell_orders and isinstance(sell_orders, list) and len(sell_orders) > 0:
            ask = _parse_decimal(sell_orders[0].get("price", 0), "ask")
            ask_size = _parse_int(sell_orders[0].get("quantity", 0), "ask_size")
        else:
            ask = _parse_decimal(market_data.get("ask", 0), "ask")
            ask_size = _parse_int(market_data.get("ask_size", 0), "ask_size")
    else:
        bid = _parse_decimal(market_data.get("bid", 0), "bid")
        ask = _parse_decimal(market_data.get("ask", 0), "ask")
        bid_size = _parse_int(market_data.get("bid_size", 0), "bid_size")
        ask_size = _parse_int(market_data.get("ask_size", 0), "ask_size")

    # Extract last traded price
    raw_ltp = market_data.get("ltp") or market_data.get("last_price")
    last_price = _parse_decimal(raw_ltp, "last_price") if raw_ltp is not None else None

    # If ask < bid, that is a crossed quote violation
    if ask < bid:
        raise LiveFeedQualityError(
            f"Crossed quote received for {instrument_key}: ask {ask} < bid {bid}",
            code=FeedQualityCode.CROSSED_QUOTE,
        )

    seq = market_data.get("sequence_number") or feed_item.get("sequence_number")
    sequence_number = int(seq) if seq is not None else None

    try:
        return LiveQuoteRecord(
            instrument_key=instrument_key,
            symbol=symbol,
            bid=bid,
            ask=ask,
            bid_size=bid_size,
            ask_size=ask_size,
            last_price=last_price,
            event_at=event_at,
            received_at=received_at,
            sequence_number=sequence_number,
        )
    except ValueError as err:
        raise LiveFeedQualityError(str(err), code=FeedQualityCode.NEGATIVE_PRICE) from err


def _parse_single_quote_dict(
    data: dict[str, Any],
    *,
    received_at: datetime,
    symbol_map: Mapping[str, str],
) -> LiveQuoteRecord:
    instrument_key = str(data["instrument_key"])
    symbol = str(data.get("symbol") or symbol_map.get(instrument_key, instrument_key))
    raw_ts = data.get("timestamp")
    if not raw_ts:
        raise LiveFeedSchemaDriftError(f"missing timestamp for {instrument_key}")
    try:
        if isinstance(raw_ts, (int, float)):
            ts_sec = float(raw_ts) / 1000.0 if raw_ts > 1e11 else float(raw_ts)
            event_at = datetime.fromtimestamp(ts_sec, tz=UTC)
        else:
            event_at = datetime.fromisoformat(str(raw_ts).replace("Z", "+00:00")).astimezone(UTC)
    except Exception as err:
        raise LiveFeedSchemaDriftError(f"unparseable timestamp: {err}") from err

    bid = _parse_decimal(data.get("bid", 0), "bid")
    ask = _parse_decimal(data.get("ask", 0), "ask")
    bid_size = _parse_int(data.get("bid_size", 0), "bid_size")
    ask_size = _parse_int(data.get("ask_size", 0), "ask_size")
    raw_ltp = data.get("last_price") or data.get("ltp")
    last_price = _parse_decimal(raw_ltp, "last_price") if raw_ltp is not None else None

    if ask < bid:
        raise LiveFeedQualityError(
            f"Crossed quote for {symbol}: ask {ask} < bid {bid}",
            code=FeedQualityCode.CROSSED_QUOTE,
        )

    try:
        return LiveQuoteRecord(
            instrument_key=instrument_key,
            symbol=symbol,
            bid=bid,
            ask=ask,
            bid_size=bid_size,
            ask_size=ask_size,
            last_price=last_price,
            event_at=event_at,
            received_at=received_at,
        )
    except ValueError as err:
        raise LiveFeedQualityError(str(err), code=FeedQualityCode.NEGATIVE_PRICE) from err


def _parse_decimal(val: Any, field_name: str) -> Decimal:
    if isinstance(val, bool) or not isinstance(val, (int, float, str, Decimal)):
        raise LiveFeedSchemaDriftError(f"{field_name} must be numeric")
    try:
        parsed = Decimal(str(val))
    except InvalidOperation as err:
        raise LiveFeedSchemaDriftError(f"{field_name} must be numeric") from err
    if not parsed.is_finite():
        raise LiveFeedSchemaDriftError(f"{field_name} must be finite")
    return parsed


def _parse_int(val: Any, field_name: str) -> int:
    if isinstance(val, bool) or not isinstance(val, (int, float, str, Decimal)):
        raise LiveFeedSchemaDriftError(f"{field_name} must be integer")
    try:
        int_val = int(Decimal(str(val)))
    except (InvalidOperation, ValueError) as err:
        raise LiveFeedSchemaDriftError(f"{field_name} must be integer") from err
    if int_val < 0:
        raise LiveFeedSchemaDriftError(f"{field_name} cannot be negative")
    return int_val


class UpstoxLiveFeed:
    """Read-only Upstox V3 streaming market-data feed with strict freshness enforcement."""

    def __init__(
        self,
        access_token: str | None = None,
        *,
        dependencies: LiveFeedDependencies,
        config: LiveFeedConfig | None = None,
    ) -> None:
        self.access_token = access_token or ""
        self.dependencies = dependencies
        self.config = config or LiveFeedConfig()
        self.state: FeedState = FeedState.DISCONNECTED
        self.subscribed_instruments: set[str] = set()
        self.symbol_map: dict[str, str] = {}
        self._last_received_at: datetime | None = None

        # STRICT INVARIANT: Live feed must be 100% read-only and have zero order capabilities.
        assert not hasattr(self, "place_order"), "Live feed must not expose order endpoints"
        assert not hasattr(self, "submit_order"), "Live feed must not expose order endpoints"
        assert not hasattr(self, "cancel_order"), "Live feed must not expose order endpoints"

    @property
    def is_authenticated(self) -> bool:
        return bool(self.access_token)

    def connect(self) -> None:
        """Establishes streaming connection and authenticates."""
        now = require_aware_utc(self.dependencies.clock())
        if not self.is_authenticated:
            self.state = FeedState.UNAUTHORIZED
            raise LiveFeedUnauthorizedError("Live feed requires a valid Upstox access token.")

        self.state = FeedState.CONNECTING
        try:
            headers = {
                "Authorization": f"Bearer {self.access_token}",
                "User-Agent": "QuantOS/1.0",
            }
            self.dependencies.transport.connect(self.config.ws_url, headers=headers)
            self.state = FeedState.STREAMING
            self._last_received_at = now
        except Exception as err:
            self.state = FeedState.OFFLINE
            raise LiveFeedConnectionError(
                f"Failed to connect to live stream: {err}", disconnected_at=now
            ) from err

    def subscribe(
        self,
        instrument_keys: Sequence[str],
        symbols: Mapping[str, str] | None = None,
    ) -> None:
        """Subscribe to real-time quotes for given instruments."""
        if self.state not in {FeedState.STREAMING, FeedState.CONNECTED, FeedState.CONNECTING}:
            raise LiveFeedError(f"Cannot subscribe while feed is in state {self.state}")
        for key in instrument_keys:
            self.subscribed_instruments.add(key)
        if symbols:
            self.symbol_map.update(symbols)

        # Send subscription message over stream
        sub_msg = json.dumps(
            {
                "guid": "quantos_sub",
                "method": "sub",
                "data": {
                    "mode": "full",
                    "instrumentKeys": list(instrument_keys),
                },
            }
        )
        try:
            self.dependencies.transport.send(sub_msg)
        except Exception as err:
            now = require_aware_utc(self.dependencies.clock())
            self.state = FeedState.OFFLINE
            raise LiveFeedConnectionError(
                f"Failed to send subscription: {err}", disconnected_at=now
            ) from err

    def read_quote(self, timeout_seconds: float | None = None) -> LiveQuoteRecord:
        """Reads the next incoming quote from stream, enforcing freshness and quality budgets."""
        if self.state == FeedState.HALTED:
            raise LiveFeedError("Feed is HALTED and cannot read further quotes.")
        if self.state in {FeedState.DISCONNECTED, FeedState.OFFLINE}:
            now = require_aware_utc(self.dependencies.clock())
            raise LiveFeedConnectionError("Feed is disconnected.", disconnected_at=now)
        if self.state == FeedState.UNAUTHORIZED:
            raise LiveFeedUnauthorizedError("Feed is UNAUTHORIZED.")

        timeout = timeout_seconds or self.config.heartbeat_timeout_seconds
        try:
            payload = self.dependencies.transport.receive(timeout_seconds=timeout)
        except TimeoutError as err:
            self.state = FeedState.HALTED
            raise LiveFeedTimeoutError(
                f"Stream timed out waiting for market data after {timeout:.1f}s",
                timeout_seconds=timeout,
            ) from err
        except Exception as err:
            now = require_aware_utc(self.dependencies.clock())
            self.state = FeedState.OFFLINE
            raise LiveFeedConnectionError(
                f"Stream transport disconnect: {err}", disconnected_at=now
            ) from err

        now = require_aware_utc(self.dependencies.clock())
        self._last_received_at = now

        records = parse_upstox_feed_message(payload, received_at=now, symbol_map=self.symbol_map)
        if not records:
            raise LiveFeedMalformedError(
                "No valid quote records found in feed message", raw_payload=str(payload)
            )

        # Take primary quote from message
        quote_record = records[0]

        # 1. Freshness budget check (latency = received_at - event_at)
        latency = quote_record.latency_seconds
        if latency > self.config.max_latency_seconds:
            self.state = FeedState.HALTED
            raise LiveFeedStaleQuoteError(
                f"Quote for {quote_record.symbol} latency of {latency:.3f}s exceeds freshness budget of {self.config.max_latency_seconds:.1f}s",
                observed_latency_seconds=latency,
                max_latency_seconds=self.config.max_latency_seconds,
                quote_timestamp=quote_record.event_at,
                received_at=now,
            )

        # 2. Clock drift check (quote timestamp cannot be in future beyond drift allowance)
        drift = (quote_record.event_at - now).total_seconds()
        if drift > self.config.max_clock_drift_seconds:
            self.state = FeedState.HALTED
            raise LiveFeedClockDriftError(
                f"Quote for {quote_record.symbol} is {drift:.3f}s in the future, exceeding clock drift budget of {self.config.max_clock_drift_seconds:.1f}s",
                observed_drift_seconds=drift,
                max_drift_seconds=self.config.max_clock_drift_seconds,
                quote_timestamp=quote_record.event_at,
                received_at=now,
            )

        return quote_record

    def stream_quotes(self, max_quotes: int | None = None) -> Iterator[LiveQuoteRecord]:
        """Generator yielding verified live quotes from the stream."""
        count = 0
        while max_quotes is None or count < max_quotes:
            quote = self.read_quote()
            yield quote
            count += 1

    def close(self) -> None:
        """Closes the stream connection."""
        self.state = FeedState.DISCONNECTED
        try:
            self.dependencies.transport.close()
        except Exception:
            pass
