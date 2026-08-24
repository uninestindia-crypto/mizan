"""Explicit research-cost adapter for the ten-year NIFTY 50 campaign."""

from __future__ import annotations

import sys
from datetime import date
from decimal import Decimal
from pathlib import Path
from typing import Any, Final

sys.path.insert(0, str(Path(__file__).resolve().parent))

import run_governed_ridge_training as runner  # noqa: E402

from quant_system.analytics.nse_rules import (  # noqa: E402
    DatedExchangeRule,
    FeeComponent,
    MarketSegment,
    NSERuleEngine,
    RateBasis,
    SideBasis,
)
from quant_system.data.market_data import HistoricalAcquisition  # noqa: E402
from quant_system.data.market_data_evidence import canonical_sha256  # noqa: E402
from quant_system.modeling import (  # noqa: E402
    FeatureDatasetV1,
    RoundTripCostQuoteV1,
    SessionCalendarV1,
)

RESEARCH_COST_POLICY_ID: Final = "quantos-nifty50-10y-research-cost-proxy-20260824-v1"
RESEARCH_COST_SOURCE: Final = "research-proxy://quantos/nifty50-10y/user-authorized-2026-08-24"
RESEARCH_COST_POLICY: Final[dict[str, Any]] = {
    "policy_id": RESEARCH_COST_POLICY_ID,
    "status": "RESEARCH_PROXY_NOT_HISTORICAL_AUTHORITY",
    "publication_date": "2026-08-24",
    "rules": [
        {
            "component": "EXCHANGE_TURNOVER",
            "effective_from": "2016-08-22",
            "effective_to": "2017-03-31",
            "rate": "0.0000345",
            "rate_basis": "TURNOVER",
            "side_basis": "BOTH",
        },
        {
            "component": "GST",
            "effective_from": "2016-08-22",
            "effective_to": "2017-06-30",
            "rate": "0.18",
            "rate_basis": "STATUTORY_CHARGES",
            "side_basis": "BOTH",
        },
        {
            "component": "STAMP_DUTY",
            "effective_from": "2016-08-22",
            "effective_to": "2020-06-30",
            "rate": "0.000150",
            "rate_basis": "TURNOVER",
            "side_basis": "BUY",
        },
    ],
}
RESEARCH_COST_POLICY_HASH: Final = canonical_sha256(RESEARCH_COST_POLICY)


def _proxy_rule(
    *,
    rule_id: str,
    component: FeeComponent,
    effective_to: date,
    side_basis: SideBasis,
    rate: str,
    rate_basis: RateBasis,
    description: str,
) -> DatedExchangeRule:
    return DatedExchangeRule(
        rule_id=rule_id,
        component=component,
        source_ref=RESEARCH_COST_SOURCE,
        publication_date=date(2026, 8, 24),
        effective_from=date(2016, 8, 22),
        effective_to=effective_to,
        venue="NSE",
        segment=MarketSegment.EQUITY_DELIVERY,
        side_basis=side_basis,
        rate=Decimal(rate),
        rate_basis=rate_basis,
        description=description,
    )


def research_cost_engine() -> NSERuleEngine:
    """Return the canonical engine plus three visibly identified research proxies."""
    proxy_rules = [
        _proxy_rule(
            rule_id="RESEARCH-PROXY-EXCHANGE-DEL-20160822-20170331-V1",
            component=FeeComponent.EXCHANGE_TURNOVER,
            effective_to=date(2017, 3, 31),
            side_basis=SideBasis.BOTH,
            rate="0.0000345",
            rate_basis=RateBasis.TURNOVER,
            description="Research proxy; not a historical exchange authority",
        ),
        _proxy_rule(
            rule_id="RESEARCH-PROXY-INDIRECT-TAX-DEL-20160822-20170630-V1",
            component=FeeComponent.GST,
            effective_to=date(2017, 6, 30),
            side_basis=SideBasis.BOTH,
            rate="0.18",
            rate_basis=RateBasis.STATUTORY_CHARGES,
            description="Research indirect-tax proxy; not a historical tax authority",
        ),
        _proxy_rule(
            rule_id="RESEARCH-PROXY-STAMP-DEL-20160822-20200630-V1",
            component=FeeComponent.STAMP_DUTY,
            effective_to=date(2020, 6, 30),
            side_basis=SideBasis.BUY,
            rate="0.000150",
            rate_basis=RateBasis.TURNOVER,
            description="Research stamp-duty proxy; not a historical authority",
        ),
    ]
    return NSERuleEngine(rules=[*NSERuleEngine().rules, *proxy_rules])


def round_trip_cost_quotes(
    features: FeatureDatasetV1,
    acquisition: HistoricalAcquisition,
    calendar: SessionCalendarV1,
    *,
    quantity: int,
) -> tuple[RoundTripCostQuoteV1, ...]:
    """Price every maturing next-open/following-open label with dated rules."""
    engine = research_cost_engine()
    bars_by_date = {record.exchange_date: record for record in acquisition.records}
    quotes: list[RoundTripCostQuoteV1] = []
    for feature_row in features.rows:
        ordinal = calendar.ordinal_for_close(feature_row.decision_at)
        if ordinal is None or ordinal + 2 >= len(calendar.sessions):
            continue
        entry_session = calendar.sessions[ordinal + 1]
        exit_session = calendar.sessions[ordinal + 2]
        if exit_session.exchange_date > acquisition.manifest.received_end:
            continue
        entry_bar = bars_by_date.get(entry_session.exchange_date)
        exit_bar = bars_by_date.get(exit_session.exchange_date)
        if entry_bar is None or exit_bar is None:
            continue
        quotes.append(
            runner._cost_quote_for_legs(
                engine,
                entry_bar=entry_bar,
                exit_bar=exit_bar,
                entry_at=entry_session.open_at,
                exit_at=exit_session.open_at,
                quantity=quantity,
            )
        )
    return tuple(quotes)
