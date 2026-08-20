"""Raw provider-envelope replay through governed features and executable labels."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from pathlib import Path

from quant_system.data.market_data import (
    AuthorityReference,
    HistoricalAcquisition,
    HistoricalDailyRequest,
)
from quant_system.data.upstox import UpstoxClient, UpstoxClientDependencies
from quant_system.data.upstox_http import HttpResponse
from quant_system.modeling import build_feature_dataset, build_label_dataset
from tests.modeling_fixtures import (
    ACQUIRED_AT,
    INSTRUMENT_KEY,
    SYMBOL,
    governed_calendar,
    governed_universe,
    round_trip_cost_quotes,
)

FIXTURE_PATH = Path(__file__).parent / "fixtures" / "upstox_v3_daily_replay.json"


@dataclass(frozen=True, slots=True)
class ReplayTransport:
    body: bytes

    def get(
        self,
        _url: str,
        *,
        headers: dict[str, str],
        timeout_seconds: float,
        max_response_bytes: int,
    ) -> HttpResponse:
        assert headers["Accept"] == "application/json"
        assert 0 < timeout_seconds <= 30
        assert len(self.body) <= max_response_bytes
        return HttpResponse(
            status=200,
            body=self.body,
            headers={"content-type": "application/json", "x-request-id": "replay-2025-01"},
        )


def test_recorded_provider_replay_has_pinned_feature_and_label_hashes() -> None:
    calendar = governed_calendar(26)
    universe = governed_universe()
    request = HistoricalDailyRequest(
        instrument_key=INSTRUMENT_KEY,
        symbol=SYMBOL,
        from_date=calendar.sessions[0].exchange_date,
        to_date=calendar.sessions[-1].exchange_date,
        request_id="req-provider-replay",
        calendar=calendar.reference,
        expected_sessions=tuple(session.exchange_date for session in calendar.sessions),
        corporate_action_authority=_corporate_authority(),
        historical_universe_authority=universe.authority,
    )
    first_acquisition = _replay_client().acquire_historical_daily(request)
    second_acquisition = _replay_client().acquire_historical_daily(request)

    assert isinstance(first_acquisition, HistoricalAcquisition)
    assert isinstance(second_acquisition, HistoricalAcquisition)
    first_features = build_feature_dataset(
        first_acquisition,
        "cand_provider_replay",
        calendar,
        universe,
    )
    second_features = build_feature_dataset(
        second_acquisition,
        "cand_provider_replay",
        calendar,
        universe,
    )
    first_labels = build_label_dataset(
        first_features,
        first_acquisition,
        calendar,
        round_trip_cost_quotes(first_acquisition, calendar, cost=Decimal("0.1")),
    )
    second_labels = build_label_dataset(
        second_features,
        second_acquisition,
        calendar,
        round_trip_cost_quotes(second_acquisition, calendar, cost=Decimal("0.1")),
    )

    assert first_features == second_features
    assert first_labels == second_labels
    assert first_acquisition.manifest.provider_request_id == "replay-2025-01"
    assert (
        first_features.dataset_hash
        == (
            "5c7639255b75e0b7c91ed40c02f1b5d29d540e740e457e3a9a7b7d80ef25480a"  # pragma: allowlist secret
        )
    )
    assert (
        first_labels.dataset_hash
        == (
            "2e65d19c0fc28304bf8b11d86975b82d38b52e317d4fe714046c44e6a5180ae2"  # pragma: allowlist secret
        )
    )


def _replay_client() -> UpstoxClient:
    dependencies = UpstoxClientDependencies(
        transport=ReplayTransport(FIXTURE_PATH.read_bytes()),
        clock=lambda: ACQUIRED_AT,
        sleeper=lambda _delay: None,
        jitter=lambda: 0,
    )
    return UpstoxClient(access_token="test-token", dependencies=dependencies)


def _corporate_authority() -> AuthorityReference:
    return AuthorityReference(
        authority_id="nse-corporate-actions",
        source_url="https://example.test/nse/corporate-actions",
        publication_date=date(2024, 12, 20),
        effective_from=date(2025, 1, 1),
        effective_to=date(2025, 12, 31),
        version="2025-v1",
        content_hash="c" * 64,
    )
