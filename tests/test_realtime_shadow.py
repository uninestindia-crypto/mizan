"""Comprehensive test suite for Read-Only Real-Time Shadow and Upstox Live Feed."""

from __future__ import annotations

import json
from collections.abc import Mapping
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest

from quant_system.core.domain import Quote, Side, Signal
from quant_system.data.live_feed import (
    FeedQualityCode,
    LiveFeedConfig,
    LiveFeedDependencies,
    LiveFeedMalformedError,
    LiveFeedQualityError,
    UpstoxLiveFeed,
    parse_upstox_feed_message,
)
from quant_system.execution.realtime_shadow import (
    RealtimeShadowConfig,
    RealtimeShadowRunner,
    ShadowAuditReport,
    ShadowDecisionStatus,
    ShadowHaltReason,
    ShadowSessionState,
)
from quant_system.risk.checks import RiskLimits
from quant_system.risk.governor import PreTradeRiskGovernor
from quant_system.strategies.base import BaseStrategy, MarketContext


class MockLiveStreamTransport:
    """Deterministic in-memory stream transport for simulating provider messages and network failures."""

    def __init__(self, queue: list[bytes | str] | None = None) -> None:
        self.queue: list[bytes | str] = list(queue or [])
        self.sent_messages: list[str | bytes] = []
        self._connected: bool = False
        self.raise_on_connect: Exception | None = None
        self.raise_on_receive: Exception | None = None
        self.raise_on_send: Exception | None = None

    def connect(self, url: str, headers: Mapping[str, str] | None = None) -> None:
        if self.raise_on_connect:
            raise self.raise_on_connect
        self._connected = True

    def send(self, data: str | bytes) -> None:
        if self.raise_on_send:
            raise self.raise_on_send
        self.sent_messages.append(data)

    def receive(self, timeout_seconds: float | None = None) -> bytes | str:
        if self.raise_on_receive:
            raise self.raise_on_receive
        if not self.queue:
            raise TimeoutError("No messages available in stream queue")
        return self.queue.pop(0)

    def close(self) -> None:
        self._connected = False

    def is_connected(self) -> bool:
        return self._connected


class SimpleMomentumStrategy(BaseStrategy):
    """Simple test strategy that signals BUY when mid price increases."""

    def __init__(self, symbol: str = "RELIANCE") -> None:
        super().__init__(name="SimpleMomentum")
        self.target_symbol = symbol
        self.last_mid: Decimal | None = None

    def generate_signals(self, ctx: MarketContext) -> list[Signal]:
        quote: Quote | None = ctx.extra_data.get("current_quote")
        if quote is None or quote.symbol != self.target_symbol:
            return []

        signal_side: Side | None = None
        if self.last_mid is not None:
            if quote.mid_price > self.last_mid:
                signal_side = Side.BUY
            elif quote.mid_price < self.last_mid:
                signal_side = Side.SELL

        self.last_mid = quote.mid_price
        if signal_side is not None:
            return [
                Signal(
                    symbol=quote.symbol,
                    side=signal_side,
                    strength=1.0,
                    timestamp=ctx.current_time,
                    strategy_name=self.name,
                )
            ]
        return []


def create_upstox_quote_json(
    instrument_key: str = "NSE_EQ|INE002A01018",
    symbol: str = "RELIANCE",
    bid: str = "2500.00",
    ask: str = "2501.00",
    bid_size: int = 100,
    ask_size: int = 200,
    ltp: str = "2500.50",
    timestamp_iso: str = "2026-08-22T09:15:00.000Z",
) -> str:
    return json.dumps(
        {
            "type": "live_feed",
            "feeds": {
                instrument_key: {
                    "full_feed": {
                        "market_data": {
                            "ltp": float(ltp),
                            "market_depth": {
                                "buy": [{"price": float(bid), "quantity": bid_size}],
                                "sell": [{"price": float(ask), "quantity": ask_size}],
                            },
                            "timestamp": timestamp_iso,
                        }
                    }
                }
            },
        }
    )


# -------------------------------------------------------------------------
# Ring 0 & Ring 1: Security, Read-Only Invariants, and Parser Tests
# -------------------------------------------------------------------------


def test_zero_broker_order_endpoint_exposure() -> None:
    """Verify zero order endpoints exist on live feed and shadow runner."""
    transport = MockLiveStreamTransport()
    deps = LiveFeedDependencies(
        transport=transport,
        clock=lambda: datetime(2026, 8, 22, 9, 15, tzinfo=UTC),
    )
    feed = UpstoxLiveFeed(access_token="test_token", dependencies=deps)
    runner = RealtimeShadowRunner(
        config=RealtimeShadowConfig(session_id="s1", model_id="m1"),
        live_feed=feed,
    )

    # Invariant: No broker order methods can exist
    for forbidden in [
        "place_order",
        "submit_order",
        "cancel_order",
        "submit_broker_order",
        "cancel_broker_order",
    ]:
        assert not hasattr(feed, forbidden), f"Feed exposes forbidden broker method: {forbidden}"
        assert not hasattr(runner, forbidden), (
            f"Runner exposes forbidden broker method: {forbidden}"
        )

    # Invariant: Audit report must strictly have broker_orders_submitted == 0
    report = runner.build_audit_report()
    assert report.broker_orders_submitted == 0

    # Invariant: Audit report raises ValueError if broker_orders_submitted is tampered to non-zero
    with pytest.raises(ValueError, match="ZERO ORDER ENDPOINT EXPOSURE INVARIANT VIOLATED"):
        ShadowAuditReport(
            session_id="s1",
            model_id="m1",
            started_at=datetime.now(UTC),
            ended_at=datetime.now(UTC),
            final_state=ShadowSessionState.RUNNING,
            halt_reason=None,
            halt_details=None,
            quotes_processed=1,
            proposals_generated=1,
            proposals_approved=1,
            proposals_rejected=0,
            broker_orders_submitted=1,  # ILLEGAL
            max_quote_latency_seconds=0.1,
            avg_quote_latency_seconds=0.1,
            decisions=(),
            matured_outcomes=(),
            audit_hash="test",
        )


def test_quote_parsing_valid_upstox_payload() -> None:
    """Verify Upstox V3 streaming message correctly parses into a LiveQuoteRecord."""
    now = datetime(2026, 8, 22, 9, 15, 1, tzinfo=UTC)
    payload = create_upstox_quote_json(
        instrument_key="NSE_EQ|INE002A01018",
        bid="2500.00",
        ask="2500.50",
        bid_size=500,
        ask_size=300,
        ltp="2500.25",
        timestamp_iso="2026-08-22T09:15:00.000Z",
    )
    records = parse_upstox_feed_message(
        payload, received_at=now, symbol_map={"NSE_EQ|INE002A01018": "RELIANCE"}
    )
    assert len(records) == 1
    record = records[0]
    assert record.symbol == "RELIANCE"
    assert record.bid == Decimal("2500.00")
    assert record.ask == Decimal("2500.50")
    assert record.bid_size == 500
    assert record.ask_size == 300
    assert record.last_price == Decimal("2500.25")
    assert record.spread == Decimal("0.50")
    assert record.mid_price == Decimal("2500.25")
    assert record.latency_seconds == pytest.approx(1.0)


def test_quote_parsing_rejects_html_and_malformed() -> None:
    """Verify HTML error pages and corrupted payloads raise LiveFeedMalformedError."""
    now = datetime(2026, 8, 22, 9, 15, tzinfo=UTC)
    html_body = b"<html><body>502 Bad Gateway</body></html>"
    with pytest.raises(LiveFeedMalformedError, match="HTML"):
        parse_upstox_feed_message(html_body, received_at=now)

    corrupted_json = b'{"type": "live_feed", "feeds": {corrupted...}'
    with pytest.raises(LiveFeedMalformedError, match="malformed"):
        parse_upstox_feed_message(corrupted_json, received_at=now)


def test_quote_parsing_rejects_crossed_quotes() -> None:
    """Verify crossed quote (ask < bid) raises LiveFeedQualityError."""
    now = datetime(2026, 8, 22, 9, 15, tzinfo=UTC)
    crossed_payload = create_upstox_quote_json(bid="2505.00", ask="2500.00")
    with pytest.raises(LiveFeedQualityError) as excinfo:
        parse_upstox_feed_message(crossed_payload, received_at=now)
    assert excinfo.value.code == FeedQualityCode.CROSSED_QUOTE


# -------------------------------------------------------------------------
# Ring 2 & Ring 3: Freshness Budget, Clock Drift, and Feed Failure Modes
# -------------------------------------------------------------------------


def test_freshness_budget_enforcement_halts_on_stale_quote() -> None:
    """Verify quote latency exceeding freshness budget triggers SHADOW_HALTED with STALE_QUOTE."""
    now = datetime(2026, 8, 22, 9, 15, 6, tzinfo=UTC)  # 6 seconds later
    # Quote is 6 seconds old (exceeds default 5.0s budget)
    stale_payload = create_upstox_quote_json(timestamp_iso="2026-08-22T09:15:00.000Z")

    transport = MockLiveStreamTransport(queue=[stale_payload])
    deps = LiveFeedDependencies(transport=transport, clock=lambda: now)
    feed = UpstoxLiveFeed(
        access_token="test_token", dependencies=deps, config=LiveFeedConfig(max_latency_seconds=5.0)
    )

    runner = RealtimeShadowRunner(
        config=RealtimeShadowConfig(
            session_id="sess_stale", model_id="mod_1", freshness_budget_seconds=5.0
        ),
        live_feed=feed,
        clock=lambda: now,
    )

    report = runner.run_session(max_quotes=1)
    assert report.final_state == ShadowSessionState.SHADOW_HALTED
    assert report.halt_reason == ShadowHaltReason.STALE_QUOTE
    assert "exceeds freshness budget" in str(report.halt_details)
    assert report.proposals_approved == 0
    assert report.broker_orders_submitted == 0


def test_clock_drift_enforcement_halts_on_future_timestamp() -> None:
    """Verify quote timestamp in the future beyond threshold triggers SHADOW_HALTED with CLOCK_DRIFT."""
    now = datetime(2026, 8, 22, 9, 15, 0, tzinfo=UTC)
    # Quote timestamp is 2.5 seconds in the future (exceeds 1.0s max clock drift)
    future_payload = create_upstox_quote_json(timestamp_iso="2026-08-22T09:15:02.500Z")

    transport = MockLiveStreamTransport(queue=[future_payload])
    deps = LiveFeedDependencies(transport=transport, clock=lambda: now)
    feed = UpstoxLiveFeed(
        access_token="test_token",
        dependencies=deps,
        config=LiveFeedConfig(max_clock_drift_seconds=1.0),
    )

    runner = RealtimeShadowRunner(
        config=RealtimeShadowConfig(
            session_id="sess_drift", model_id="mod_1", max_clock_drift_seconds=1.0
        ),
        live_feed=feed,
        clock=lambda: now,
    )

    report = runner.run_session(max_quotes=1)
    assert report.final_state == ShadowSessionState.SHADOW_HALTED
    assert report.halt_reason == ShadowHaltReason.CLOCK_DRIFT
    assert "exceeding clock drift" in str(report.halt_details)


def test_unauthorized_token_expiry_halts_immediately() -> None:
    """Verify missing or expired token halts session with UNAUTHORIZED / AUTH_EXPIRED."""
    now = datetime(2026, 8, 22, 9, 15, 0, tzinfo=UTC)
    transport = MockLiveStreamTransport()
    deps = LiveFeedDependencies(transport=transport, clock=lambda: now)
    feed = UpstoxLiveFeed(access_token="", dependencies=deps)  # Empty token

    runner = RealtimeShadowRunner(
        config=RealtimeShadowConfig(session_id="sess_auth", model_id="mod_1"),
        live_feed=feed,
        clock=lambda: now,
    )

    report = runner.run_session(max_quotes=1)
    assert report.final_state == ShadowSessionState.UNAUTHORIZED
    assert report.halt_reason == ShadowHaltReason.AUTH_EXPIRED
    assert report.quotes_processed == 0


def test_streaming_disconnect_transitions_to_offline() -> None:
    """Verify streaming transport disconnect halts session with OFFLINE / DISCONNECTED."""
    now = datetime(2026, 8, 22, 9, 15, 0, tzinfo=UTC)
    transport = MockLiveStreamTransport()
    transport.raise_on_receive = ConnectionResetError("Connection lost to Upstox streaming server")

    deps = LiveFeedDependencies(transport=transport, clock=lambda: now)
    feed = UpstoxLiveFeed(access_token="valid_token", dependencies=deps)

    runner = RealtimeShadowRunner(
        config=RealtimeShadowConfig(session_id="sess_disconnect", model_id="mod_1"),
        live_feed=feed,
        clock=lambda: now,
    )

    report = runner.run_session(max_quotes=1)
    assert report.final_state == ShadowSessionState.OFFLINE
    assert report.halt_reason == ShadowHaltReason.DISCONNECTED
    assert "Connection lost" in str(report.halt_details)


def test_streaming_timeout_halts_session() -> None:
    """Verify empty stream / timeout halts session with FEED_TIMEOUT."""
    now = datetime(2026, 8, 22, 9, 15, 0, tzinfo=UTC)
    transport = MockLiveStreamTransport(queue=[])  # Empty queue causes TimeoutError on receive

    deps = LiveFeedDependencies(transport=transport, clock=lambda: now)
    feed = UpstoxLiveFeed(
        access_token="valid_token",
        dependencies=deps,
        config=LiveFeedConfig(heartbeat_timeout_seconds=2.0),
    )

    runner = RealtimeShadowRunner(
        config=RealtimeShadowConfig(session_id="sess_timeout", model_id="mod_1"),
        live_feed=feed,
        clock=lambda: now,
    )

    report = runner.run_session(max_quotes=1)
    assert report.final_state == ShadowSessionState.SHADOW_HALTED
    assert report.halt_reason == ShadowHaltReason.FEED_TIMEOUT


# -------------------------------------------------------------------------
# Ring 4: End-to-End Real-Time Shadow Session & Decision Gating
# -------------------------------------------------------------------------


def test_realtime_shadow_session_successful_flow() -> None:
    """Verify happy path: fresh quotes drive signals, pre-trade risk approves, and matured outcomes track."""
    t0 = datetime(2026, 8, 22, 9, 15, 0, tzinfo=UTC)
    t1 = datetime(2026, 8, 22, 9, 15, 1, tzinfo=UTC)
    t2 = datetime(2026, 8, 22, 9, 15, 2, tzinfo=UTC)

    # 3 sequential quotes: quote 1 (baseline), quote 2 (price rises -> BUY), quote 3 (price rises significantly -> matures previous BUY with positive net P&L)
    q1 = create_upstox_quote_json(
        bid="2500.00", ask="2500.50", ltp="2500.25", timestamp_iso=t0.isoformat()
    )
    q2 = create_upstox_quote_json(
        bid="2502.00", ask="2502.50", ltp="2502.25", timestamp_iso=t1.isoformat()
    )
    q3 = create_upstox_quote_json(
        bid="2520.00", ask="2520.50", ltp="2520.25", timestamp_iso=t2.isoformat()
    )

    transport = MockLiveStreamTransport(queue=[q1, q2, q3])
    current_time = t0

    def mock_clock() -> datetime:
        return current_time

    deps = LiveFeedDependencies(transport=transport, clock=mock_clock)
    feed = UpstoxLiveFeed(access_token="valid_token", dependencies=deps)
    feed.symbol_map["NSE_EQ|INE002A01018"] = "RELIANCE"
    feed.connect()

    strategy = SimpleMomentumStrategy(symbol="RELIANCE")
    risk_governor = PreTradeRiskGovernor(limits=RiskLimits(max_position_weight=0.25))

    runner = RealtimeShadowRunner(
        config=RealtimeShadowConfig(
            session_id="sess_e2e",
            model_id="ridge_model_v1",
            freshness_budget_seconds=5.0,
            default_order_quantity=10,
        ),
        live_feed=feed,
        strategy=strategy,
        risk_governor=risk_governor,
        clock=mock_clock,
    )

    # Process quote 1 (sets baseline)
    current_time = t0 + timedelta(milliseconds=100)
    p1 = runner.process_live_quote(feed.read_quote())
    assert p1 is None  # No signal on first quote

    # Process quote 2 (price increased -> BUY signal generated and approved)
    current_time = t1 + timedelta(milliseconds=100)
    p2 = runner.process_live_quote(feed.read_quote())
    assert p2 is not None
    assert p2.side == Side.BUY
    assert p2.status == ShadowDecisionStatus.APPROVED
    assert p2.risk_approved is True
    assert p2.quantity == 10
    assert p2.quote_ask == Decimal("2502.50")

    # Process quote 3 (price increased further -> matures previous buy entry)
    current_time = t2 + timedelta(milliseconds=100)
    p3 = runner.process_live_quote(feed.read_quote())
    assert p3 is not None
    assert p3.side == Side.BUY

    report = runner.build_audit_report()
    assert report.quotes_processed == 3
    assert report.proposals_approved == 2
    assert report.proposals_rejected == 0
    assert report.broker_orders_submitted == 0
    assert len(report.matured_outcomes) >= 1

    # Check matured outcome metrics
    matured = report.matured_outcomes[0]
    assert matured.symbol == "RELIANCE"
    assert matured.entry_price == Decimal("2502.50")  # Bought at ask
    assert matured.exit_price == Decimal("2520.00")  # Matured at bid
    assert matured.gross_pnl == (Decimal("2520.00") - Decimal("2502.50")) * Decimal(10)  # +175.00
    assert matured.net_pnl > Decimal("0")
    assert report.audit_hash is not None


def test_risk_rejection_in_shadow_mode() -> None:
    """Verify pre-trade risk rejection generates rejected proposal without halting session."""
    t0 = datetime(2026, 8, 22, 9, 15, 0, tzinfo=UTC)
    t1 = datetime(2026, 8, 22, 9, 15, 1, tzinfo=UTC)

    q1 = create_upstox_quote_json(
        bid="2500.00", ask="2500.50", ltp="2500.25", timestamp_iso=t0.isoformat()
    )
    q2 = create_upstox_quote_json(
        bid="2502.00", ask="2502.50", ltp="2502.25", timestamp_iso=t1.isoformat()
    )

    transport = MockLiveStreamTransport(queue=[q1, q2])
    deps = LiveFeedDependencies(transport=transport, clock=lambda: t1)
    feed = UpstoxLiveFeed(access_token="valid_token", dependencies=deps)
    feed.symbol_map["NSE_EQ|INE002A01018"] = "RELIANCE"
    feed.connect()

    strategy = SimpleMomentumStrategy(symbol="RELIANCE")
    # Set extreme low position weight limit to force risk rejection
    risk_governor = PreTradeRiskGovernor(limits=RiskLimits(max_position_weight=0.001))

    runner = RealtimeShadowRunner(
        config=RealtimeShadowConfig(
            session_id="sess_risk_reject",
            model_id="ridge_model_v1",
            default_order_quantity=100,  # 100 * 2500 = 250,000 >> 0.1% of 1,000,000 (1,000)
        ),
        live_feed=feed,
        strategy=strategy,
        risk_governor=risk_governor,
        clock=lambda: t1,
    )

    runner.process_live_quote(feed.read_quote())
    p2 = runner.process_live_quote(feed.read_quote())

    assert p2 is not None
    assert p2.status == ShadowDecisionStatus.REJECTED_BY_RISK
    assert p2.risk_approved is False
    assert "POSITION_WEIGHT_LIMIT_EXCEEDED" in str(p2.rejection_reason)
    assert runner.broker_orders_submitted == 0


def test_deterministic_audit_replay_hash() -> None:
    """Verify identical quote sessions produce identical cryptographic audit digests."""
    t0 = datetime(2026, 8, 22, 9, 15, 0, tzinfo=UTC)
    t1 = datetime(2026, 8, 22, 9, 15, 1, tzinfo=UTC)

    q1 = create_upstox_quote_json(
        bid="2500.00", ask="2500.50", ltp="2500.25", timestamp_iso=t0.isoformat()
    )
    q2 = create_upstox_quote_json(
        bid="2503.00", ask="2503.50", ltp="2503.25", timestamp_iso=t1.isoformat()
    )

    def run_one() -> str:
        transport = MockLiveStreamTransport(queue=[q1, q2])
        deps = LiveFeedDependencies(transport=transport, clock=lambda: t1)
        feed = UpstoxLiveFeed(access_token="valid_token", dependencies=deps)
        feed.symbol_map["NSE_EQ|INE002A01018"] = "RELIANCE"
        strategy = SimpleMomentumStrategy(symbol="RELIANCE")
        runner = RealtimeShadowRunner(
            config=RealtimeShadowConfig(session_id="sess_det", model_id="mod_1"),
            live_feed=feed,
            strategy=strategy,
            clock=lambda: t1,
        )
        report = runner.run_session(max_quotes=2)
        return report.audit_hash

    hash1 = run_one()
    hash2 = run_one()
    assert hash1 == hash2, (
        "Audit hashes must be cryptographically identical across deterministic runs"
    )
