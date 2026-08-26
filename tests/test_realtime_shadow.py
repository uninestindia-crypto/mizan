# test-allow: huge-test-file — comprehensive vertical slice 9 realtime shadow test suite
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
    LiveFeedStaleQuoteError,
    LiveQuoteRecord,
    UpstoxLiveFeed,
    parse_upstox_feed_message,
)
from quant_system.execution.realtime_shadow import (
    DecisionCadence,
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


# test-allow: loop-in-test — iteration over fixed list of forbidden broker method names
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
    # test-allow: loop-in-test — iteration over fixed list of forbidden broker method names
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
    t3 = datetime(2026, 8, 22, 9, 15, 3, tzinfo=UTC)

    # 4 sequential quotes. Quote 1 sets the baseline; quote 2 produces the BUY decision; quote 3
    # is the first LATER quote so the fill books there (S9-B1 — a decision never fills against
    # its own quote); quote 4 matures that entry with positive net P&L.
    q1 = create_upstox_quote_json(
        bid="2500.00", ask="2500.50", ltp="2500.25", timestamp_iso=t0.isoformat()
    )
    q2 = create_upstox_quote_json(
        bid="2502.00", ask="2502.50", ltp="2502.25", timestamp_iso=t1.isoformat()
    )
    q3 = create_upstox_quote_json(
        bid="2520.00", ask="2520.50", ltp="2520.25", timestamp_iso=t2.isoformat()
    )
    q4 = create_upstox_quote_json(
        bid="2530.00", ask="2530.50", ltp="2530.25", timestamp_iso=t3.isoformat()
    )

    transport = MockLiveStreamTransport(queue=[q1, q2, q3, q4])
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

    # Process quote 3 (first quote later than the decision -> the quote-2 BUY fills here)
    current_time = t2 + timedelta(milliseconds=100)
    p3 = runner.process_live_quote(feed.read_quote())
    assert p3 is not None
    assert p3.side == Side.BUY

    # Process quote 4 (matures the entry opened on quote 3)
    current_time = t3 + timedelta(milliseconds=100)
    p4 = runner.process_live_quote(feed.read_quote())
    assert p4 is not None

    report = runner.build_audit_report()
    assert report.quotes_processed == 4
    assert report.proposals_approved == 3
    assert report.proposals_rejected == 0
    assert report.broker_orders_submitted == 0
    assert len(report.matured_outcomes) >= 1

    # Check matured outcome metrics.
    # entry_price is the ask of quote 3, NOT quote 2 which produced the signal. This assertion
    # previously read 2502.50 (quote 2's ask) and so encoded the S9-B1 same-quote fill as
    # expected behaviour; it was corrected when that defect was repaired.
    matured = report.matured_outcomes[0]
    assert matured.symbol == "RELIANCE"
    assert matured.entry_price == Decimal("2520.50")  # Bought at the ask of the LATER quote
    assert matured.exit_price == Decimal("2530.00")  # Matured at bid
    assert matured.gross_pnl == (Decimal("2530.00") - Decimal("2520.50")) * Decimal(10)  # +95.00
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


# -------------------------------------------------------------------------
# Ring 5: S9-B2 regression — maturity accounting
# -------------------------------------------------------------------------


class SingleEntryStrategy(BaseStrategy):
    """Emits exactly one signal, on the first quote seen for the target symbol."""

    def __init__(self, symbol: str = "RELIANCE", side: Side = Side.BUY) -> None:
        super().__init__(name="SingleEntry")
        self.target_symbol = symbol
        self.entry_side = side
        self.fired = False

    def generate_signals(self, ctx: MarketContext) -> list[Signal]:
        quote: Quote | None = ctx.extra_data.get("current_quote")
        if quote is None or quote.symbol != self.target_symbol or self.fired:
            return []
        self.fired = True
        return [
            Signal(
                symbol=quote.symbol,
                side=self.entry_side,
                strength=1.0,
                timestamp=ctx.current_time,
                strategy_name=self.name,
            )
        ]


def _run_maturity_session(
    side: Side, quote_prices: list[tuple[str, str]], allow_naked_short: bool = False
) -> tuple[RealtimeShadowRunner, ShadowAuditReport]:
    """Drive a shadow session over the given (bid, ask) quotes with one entry signal."""
    base = datetime(2026, 8, 22, 9, 15, tzinfo=UTC)
    now = base + timedelta(seconds=10)
    payloads = [
        create_upstox_quote_json(
            bid=bid,
            ask=ask,
            timestamp_iso=(base + timedelta(seconds=8 + index)).isoformat().replace("+00:00", "Z"),
        )
        for index, (bid, ask) in enumerate(quote_prices)
    ]
    transport = MockLiveStreamTransport(queue=payloads)
    deps = LiveFeedDependencies(transport=transport, clock=lambda: now)
    feed = UpstoxLiveFeed(
        access_token="test_token",
        dependencies=deps,
        config=LiveFeedConfig(max_latency_seconds=30.0),
    )
    feed.symbol_map["NSE_EQ|INE002A01018"] = "RELIANCE"
    feed.connect()
    runner = RealtimeShadowRunner(
        config=RealtimeShadowConfig(
            session_id="sess_maturity",
            model_id="mod_maturity",
            freshness_budget_seconds=30.0,
        ),
        live_feed=feed,
        risk_governor=PreTradeRiskGovernor(
            limits=RiskLimits(max_position_weight=0.25, allow_naked_short=allow_naked_short)
        ),
        clock=lambda: now,
        strategy=SingleEntryStrategy(side=side),
    )
    for _ in payloads:
        runner.process_live_quote(feed.read_quote())
    return runner, runner.build_audit_report()


def test_matured_outcome_closes_position_and_is_not_double_counted() -> None:
    """S9-B2: a matured entry must close its position and be counted in equity exactly once.

    The third quote moves the price violently. If maturity left the position open, that move
    marks to market and equity diverges from the recorded outcome.
    """
    runner, report = _run_maturity_session(
        Side.BUY,
        [("2500.00", "2501.00"), ("2600.00", "2601.00"), ("5000.00", "5001.00")],
    )

    assert len(report.matured_outcomes) == 1, "the single entry must mature exactly once"
    recorded = sum(outcome.net_pnl for outcome in report.matured_outcomes)
    equity_delta = runner.current_equity - Decimal("1000000.00")
    assert equity_delta == recorded, (
        f"equity moved {equity_delta} but matured outcomes recorded {recorded}; "
        "the same market move is being counted twice, or the position never closed"
    )


def test_matured_outcome_closes_short_position_symmetrically() -> None:
    """S9-B2: the maturity repair must be symmetric for short entries."""
    runner, report = _run_maturity_session(
        Side.SELL,
        [("2500.00", "2501.00"), ("2400.00", "2401.00"), ("900.00", "901.00")],
        allow_naked_short=True,
    )

    assert len(report.matured_outcomes) == 1
    recorded = sum(outcome.net_pnl for outcome in report.matured_outcomes)
    equity_delta = runner.current_equity - Decimal("1000000.00")
    assert equity_delta == recorded, (
        f"short entry: equity moved {equity_delta} but outcomes recorded {recorded}"
    )


def test_matured_outcome_charges_friction_to_equity() -> None:
    """S9-B2: round-trip friction must reach equity, not just the outcome record."""
    runner, report = _run_maturity_session(
        Side.BUY,
        [("2500.00", "2501.00"), ("2600.00", "2601.00"), ("2600.00", "2601.00")],
    )

    outcome = report.matured_outcomes[0]
    assert outcome.friction_fee > Decimal("0"), "round trip must incur friction"
    equity_delta = runner.current_equity - Decimal("1000000.00")
    assert equity_delta == outcome.gross_pnl - outcome.friction_fee, (
        "equity must reflect gross P&L net of the friction recorded on the outcome"
    )


# -------------------------------------------------------------------------
# Ring 1: governed-model decision cadence
# -------------------------------------------------------------------------


class RepeatingEntryStrategy(BaseStrategy):
    """Signals on every quote for the target symbol, to expose decision cadence."""

    def __init__(self, symbol: str = "RELIANCE") -> None:
        super().__init__(name="RepeatingEntry")
        self.target_symbol = symbol
        self.invocations = 0

    def generate_signals(self, ctx: MarketContext) -> list[Signal]:
        quote: Quote | None = ctx.extra_data.get("current_quote")
        if quote is None or quote.symbol != self.target_symbol:
            return []
        self.invocations += 1
        return [
            Signal(
                symbol=quote.symbol,
                side=Side.BUY,
                strength=1.0,
                timestamp=ctx.current_time,
                strategy_name=self.name,
            )
        ]


def _run_cadence_session(
    cadence: DecisionCadence,
) -> tuple[RepeatingEntryStrategy, ShadowAuditReport]:
    """Drive three quotes through a strategy that signals on every one."""
    base = datetime(2026, 8, 22, 9, 15, tzinfo=UTC)
    now = base + timedelta(seconds=10)
    payloads = [
        create_upstox_quote_json(
            bid=f"{2500 + index}.00",
            ask=f"{2501 + index}.00",
            timestamp_iso=(base + timedelta(seconds=8 + index)).isoformat().replace("+00:00", "Z"),
        )
        for index in range(3)
    ]
    transport = MockLiveStreamTransport(queue=payloads)
    deps = LiveFeedDependencies(transport=transport, clock=lambda: now)
    feed = UpstoxLiveFeed(
        access_token="test_token",
        dependencies=deps,
        config=LiveFeedConfig(max_latency_seconds=30.0),
    )
    feed.symbol_map["NSE_EQ|INE002A01018"] = "RELIANCE"
    feed.connect()
    strategy = RepeatingEntryStrategy()
    runner = RealtimeShadowRunner(
        config=RealtimeShadowConfig(
            session_id="sess_cadence",
            model_id="mod_cadence",
            freshness_budget_seconds=30.0,
            decision_cadence=cadence,
        ),
        live_feed=feed,
        clock=lambda: now,
        strategy=strategy,
    )
    for _ in payloads:
        runner.process_live_quote(feed.read_quote())
    return strategy, runner.build_audit_report()


def test_per_quote_cadence_is_the_default_and_decides_every_quote() -> None:
    """The existing quote-driven behaviour must be preserved as the default."""
    assert RealtimeShadowConfig(session_id="s", model_id="m").decision_cadence == (
        DecisionCadence.PER_QUOTE
    )
    strategy, report = _run_cadence_session(DecisionCadence.PER_QUOTE)
    assert strategy.invocations == 3
    assert report.proposals_generated == 3


def test_once_per_session_cadence_decides_once_per_symbol() -> None:
    """A daily-close governed model must decide once per symbol, not once per tick.

    Scoring one unchanged feature row on every tick would emit the same signal all
    session and stack position on each one.
    """
    strategy, report = _run_cadence_session(DecisionCadence.ONCE_PER_SESSION)
    assert strategy.invocations == 1, "the strategy must be consulted once per symbol per session"
    assert report.proposals_generated == 1
    assert report.quotes_processed == 3, "later quotes must still be processed for maturity"


# -------------------------------------------------------------------------
# Ring 5: S9-B1 regression — a decision must not fill on its own quote
# -------------------------------------------------------------------------


# test-allow: loop-in-test — list comprehension building test quote fixtures
def test_fill_must_come_from_a_quote_later_than_the_decision() -> None:
    """S9-B1: booking a fill at the quote that produced the signal is zero-latency look-ahead.

    Slice 8's contract calls same-quote fills structurally impossible. Slice 9 must not be the
    one surface that allows them.
    """
    base = datetime(2026, 8, 22, 9, 15, tzinfo=UTC)
    now = base + timedelta(seconds=20)
    prices = [("2500.00", "2501.00"), ("2600.00", "2601.00"), ("2700.00", "2701.00")]
    payloads = [
        create_upstox_quote_json(
            bid=prices[0][0],
            ask=prices[0][1],
            timestamp_iso=(base + timedelta(seconds=10)).isoformat().replace("+00:00", "Z"),
        ),
        create_upstox_quote_json(
            bid=prices[1][0],
            ask=prices[1][1],
            timestamp_iso=(base + timedelta(seconds=11)).isoformat().replace("+00:00", "Z"),
        ),
        create_upstox_quote_json(
            bid=prices[2][0],
            ask=prices[2][1],
            timestamp_iso=(base + timedelta(seconds=12)).isoformat().replace("+00:00", "Z"),
        ),
    ]
    transport = MockLiveStreamTransport(queue=payloads)
    deps = LiveFeedDependencies(transport=transport, clock=lambda: now)
    feed = UpstoxLiveFeed(
        access_token="test_token",
        dependencies=deps,
        config=LiveFeedConfig(max_latency_seconds=60.0),
    )
    feed.symbol_map["NSE_EQ|INE002A01018"] = "RELIANCE"
    feed.connect()
    runner = RealtimeShadowRunner(
        config=RealtimeShadowConfig(
            session_id="sess_b1", model_id="mod_b1", freshness_budget_seconds=60.0
        ),
        live_feed=feed,
        clock=lambda: now,
        strategy=SingleEntryStrategy(side=Side.BUY),
    )

    # Quote 1 produces the decision. It must NOT also produce the fill.
    proposal = runner.process_live_quote(feed.read_quote())
    assert proposal is not None
    assert proposal.status == ShadowDecisionStatus.APPROVED
    assert runner.current_equity == Decimal("1000000.00"), (
        "equity moved on the decision quote: the decision filled against its own quote"
    )

    # Quote 2 is the first quote later than the decision, so the fill belongs to it.
    runner.process_live_quote(feed.read_quote())
    # Quote 3 matures the entry.
    runner.process_live_quote(feed.read_quote())

    report = runner.build_audit_report()
    assert len(report.matured_outcomes) == 1
    outcome = report.matured_outcomes[0]
    assert outcome.entry_price == Decimal("2601.00"), (
        "entry must book at the ask of the first LATER quote (2601.00), "
        f"not the decision quote's ask (2501.00); got {outcome.entry_price}"
    )
    assert outcome.exit_price == Decimal("2700.00")


# -------------------------------------------------------------------------
# Ring 5: S9-B3 regression — multi-instrument messages must not be dropped
# -------------------------------------------------------------------------


def _multi_instrument_payload(timestamp_iso: str, second_timestamp_iso: str | None = None) -> str:
    """One feed message carrying three instruments, as Upstox delivers them.

    `second_timestamp_iso` gives the second instrument its own event time, so a record that is
    only reachable from the buffer can be made stale while the first stays fresh.
    """
    second_iso = second_timestamp_iso or timestamp_iso
    entries = {
        "NSE_EQ|INE002A01018": ("2500.00", "2501.00", timestamp_iso),
        "NSE_EQ|INE009A01021": ("1800.00", "1801.00", second_iso),
        "NSE_EQ|INE467B01029": ("3900.00", "3901.00", timestamp_iso),
    }
    return json.dumps(
        {
            "type": "live_feed",
            "feeds": {
                key: {
                    "full_feed": {
                        "market_data": {
                            "ltp": float(bid),
                            "market_depth": {
                                "buy": [{"price": float(bid), "quantity": 100}],
                                "sell": [{"price": float(ask), "quantity": 100}],
                            },
                            "timestamp": event_iso,
                        }
                    }
                }
                for key, (bid, ask, event_iso) in entries.items()
            },
        }
    )


def test_multi_instrument_message_yields_every_quote() -> None:
    """S9-B3: read_quote() returned records[0] and silently discarded the rest.

    A three-instrument message parsed to three records; two vanished with no error, no
    counter and no log, so a subscribed symbol could go permanently unseen.
    """
    base = datetime(2026, 8, 22, 9, 15, tzinfo=UTC)
    now = base + timedelta(seconds=1)
    transport = MockLiveStreamTransport(
        queue=[_multi_instrument_payload(base.isoformat().replace("+00:00", "Z"))]
    )
    deps = LiveFeedDependencies(transport=transport, clock=lambda: now)
    feed = UpstoxLiveFeed(
        access_token="test_token",
        dependencies=deps,
        config=LiveFeedConfig(max_latency_seconds=30.0),
    )
    feed.symbol_map.update(
        {
            "NSE_EQ|INE002A01018": "RELIANCE",
            "NSE_EQ|INE009A01021": "INFY",
            "NSE_EQ|INE467B01029": "TCS",
        }
    )
    feed.connect()

    # The transport holds exactly one message. All three records must still be delivered,
    # which means they come from the parsed message, not from three transport reads.
    seen = [feed.read_quote().symbol for _ in range(3)]

    assert sorted(seen) == ["INFY", "RELIANCE", "TCS"], (
        f"every instrument in the message must be delivered; got {seen}"
    )
    assert len(transport.queue) == 0


def test_buffered_quotes_are_budget_checked_individually() -> None:
    """S9-B3 repair must not create a hole: a record reachable only from the buffer keeps its budget.

    The first instrument is fresh, the second is 90s stale. The second is never read from the
    transport — it exists only because the repair buffered it — so it would be trivial to hand
    it out unchecked.
    """
    base = datetime(2026, 8, 22, 9, 15, tzinfo=UTC)
    now = base + timedelta(seconds=1)
    stale = base - timedelta(seconds=90)
    transport = MockLiveStreamTransport(
        queue=[
            _multi_instrument_payload(
                base.isoformat().replace("+00:00", "Z"),
                second_timestamp_iso=stale.isoformat().replace("+00:00", "Z"),
            )
        ]
    )
    deps = LiveFeedDependencies(transport=transport, clock=lambda: now)
    feed = UpstoxLiveFeed(
        access_token="test_token",
        dependencies=deps,
        config=LiveFeedConfig(max_latency_seconds=5.0),
    )
    feed.symbol_map.update({"NSE_EQ|INE002A01018": "RELIANCE", "NSE_EQ|INE009A01021": "INFY"})
    feed.connect()

    assert feed.read_quote().symbol == "RELIANCE"  # fresh, delivered normally
    with pytest.raises(LiveFeedStaleQuoteError):
        feed.read_quote()  # buffered and stale -> must still halt


# -------------------------------------------------------------------------
# Ring 5: S9-M2 / S9-M3 regressions — live quote sequence integrity
# -------------------------------------------------------------------------


def _sequence_runner(
    event_offsets: list[int],
) -> tuple[RealtimeShadowRunner, UpstoxLiveFeed, list[str]]:
    """Build a runner over quotes whose event times are base+offset seconds, prices identical."""
    base = datetime(2026, 8, 22, 9, 15, tzinfo=UTC)
    now = base + timedelta(seconds=30)
    payloads = [
        create_upstox_quote_json(
            bid="2500.00",
            ask="2501.00",
            timestamp_iso=(base + timedelta(seconds=offset)).isoformat().replace("+00:00", "Z"),
        )
        for offset in event_offsets
    ]
    transport = MockLiveStreamTransport(queue=list(payloads))
    deps = LiveFeedDependencies(transport=transport, clock=lambda: now)
    feed = UpstoxLiveFeed(
        access_token="test_token",
        dependencies=deps,
        config=LiveFeedConfig(max_latency_seconds=120.0),
    )
    feed.symbol_map["NSE_EQ|INE002A01018"] = "RELIANCE"
    feed.connect()
    runner = RealtimeShadowRunner(
        config=RealtimeShadowConfig(
            session_id="sess_seq", model_id="mod_seq", freshness_budget_seconds=120.0
        ),
        live_feed=feed,
        clock=lambda: now,
        strategy=SingleEntryStrategy(side=Side.BUY),
    )
    return runner, feed, payloads


def test_duplicate_live_quote_halts_the_session() -> None:
    """S9-M2: byte-identical quotes were accepted, booking P&L from one market event twice."""
    runner, feed, payloads = _sequence_runner([10, 10])

    runner.process_live_quote(feed.read_quote())
    runner.process_live_quote(feed.read_quote())

    report = runner.build_audit_report()
    assert report.final_state == ShadowSessionState.SHADOW_HALTED
    assert report.halt_reason == ShadowHaltReason.DUPLICATE_TICK
    assert report.proposals_generated == 1, "the repeated market event must not decide twice"


def test_out_of_order_live_quote_halts_the_session() -> None:
    """S9-M3: a quote whose event time went backwards was accepted inside the freshness window.

    ShadowHaltReason had no code for it, so a replayed stale tick fabricated outcomes.
    """
    runner, feed, payloads = _sequence_runner([13, 10])

    runner.process_live_quote(feed.read_quote())
    runner.process_live_quote(feed.read_quote())

    report = runner.build_audit_report()
    assert report.final_state == ShadowSessionState.SHADOW_HALTED
    assert report.halt_reason == ShadowHaltReason.OUT_OF_ORDER_TIMESTAMP


# test-allow: loop-in-test — iteration over 3 multi-instrument quotes
def test_same_timestamp_across_different_symbols_is_not_out_of_order() -> None:
    """Multi-instrument messages share an event time; that is normal, not a sequence violation."""
    base = datetime(2026, 8, 22, 9, 15, tzinfo=UTC)
    now = base + timedelta(seconds=5)
    transport = MockLiveStreamTransport(
        queue=[_multi_instrument_payload(base.isoformat().replace("+00:00", "Z"))]
    )
    deps = LiveFeedDependencies(transport=transport, clock=lambda: now)
    feed = UpstoxLiveFeed(
        access_token="test_token",
        dependencies=deps,
        config=LiveFeedConfig(max_latency_seconds=60.0),
    )
    feed.symbol_map.update(
        {
            "NSE_EQ|INE002A01018": "RELIANCE",
            "NSE_EQ|INE009A01021": "INFY",
            "NSE_EQ|INE467B01029": "TCS",
        }
    )
    feed.connect()
    runner = RealtimeShadowRunner(
        config=RealtimeShadowConfig(
            session_id="sess_multi", model_id="mod_multi", freshness_budget_seconds=60.0
        ),
        live_feed=feed,
        clock=lambda: now,
        strategy=SingleEntryStrategy(side=Side.BUY),
    )

    runner.process_live_quote(feed.read_quote())
    runner.process_live_quote(feed.read_quote())
    runner.process_live_quote(feed.read_quote())

    report = runner.build_audit_report()
    assert report.final_state != ShadowSessionState.SHADOW_HALTED
    assert report.halt_reason is None
    assert report.quotes_processed == 3


# -------------------------------------------------------------------------
# Ring 5: S9-M1 regression — an LTP-only payload has no book
# -------------------------------------------------------------------------


def test_ltp_only_payload_is_refused_as_zero_liquidity() -> None:
    """S9-M1: missing bid/ask defaulted to 0, fabricating an empty two-sided book.

    `0 < 0` is false, so the crossed-quote guard never fired and the record looked valid.
    """
    payload = json.dumps(
        {
            "type": "live_feed",
            "feeds": {
                "NSE_EQ|INE002A01018": {
                    "ltp": 1845.5,
                    "timestamp": "2026-08-22T09:15:00.000Z",
                }
            },
        }
    )
    with pytest.raises(LiveFeedQualityError) as excinfo:
        parse_upstox_feed_message(
            payload,
            received_at=datetime(2026, 8, 22, 9, 15, 1, tzinfo=UTC),
            symbol_map={"NSE_EQ|INE002A01018": "RELIANCE"},
        )
    assert excinfo.value.code == FeedQualityCode.ZERO_LIQUIDITY


def test_zero_liquidity_quote_halts_rather_than_being_blamed_on_risk() -> None:
    """S9-M1: a zero book reaching the runner must be a data fault, not a risk rejection.

    Attributing it to risk sends an operator debugging the wrong subsystem.
    """
    now = datetime(2026, 8, 22, 9, 15, 1, tzinfo=UTC)
    empty_book = LiveQuoteRecord(
        instrument_key="NSE_EQ|INE002A01018",
        symbol="RELIANCE",
        bid=Decimal("0"),
        ask=Decimal("0"),
        bid_size=0,
        ask_size=0,
        last_price=Decimal("1845.50"),
        event_at=datetime(2026, 8, 22, 9, 15, tzinfo=UTC),
        received_at=now,
    )
    transport = MockLiveStreamTransport()
    deps = LiveFeedDependencies(transport=transport, clock=lambda: now)
    feed = UpstoxLiveFeed(access_token="test_token", dependencies=deps)
    runner = RealtimeShadowRunner(
        config=RealtimeShadowConfig(
            session_id="sess_zl", model_id="mod_zl", freshness_budget_seconds=60.0
        ),
        live_feed=feed,
        clock=lambda: now,
        strategy=SingleEntryStrategy(side=Side.BUY),
    )

    proposal = runner.process_live_quote(empty_book)

    report = runner.build_audit_report()
    assert proposal is None
    assert report.final_state == ShadowSessionState.SHADOW_HALTED
    assert report.halt_reason == ShadowHaltReason.QUALITY_VIOLATION
    assert report.proposals_rejected == 0, (
        "a zero book is a data-quality fault and must not be recorded as a risk rejection"
    )
