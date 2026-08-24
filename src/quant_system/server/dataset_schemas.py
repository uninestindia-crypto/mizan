"""Versioned request and response contracts for governed dataset resources."""

from __future__ import annotations

from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field, model_validator

from quant_system.data.market_data import HistoricalDailyRequest

SUPPORTED_NSE_EQUITY_INSTRUMENTS = {
    "HDFCBANK": "NSE_EQ|INE040A01034",
    "ICICIBANK": "NSE_EQ|INE090A01021",
    "INFY": "NSE_EQ|INE009A01021",
    "RELIANCE": "NSE_EQ|INE002A01018",
    "TCS": "NSE_EQ|INE467B01029",
}


class DatasetManifestResource(BaseModel):
    """Verified identity and provenance for one acquired point-in-time dataset."""

    dataset_id: str
    symbol: str
    provider_instrument_id: str
    requested_start: date
    requested_end: date
    received_start: date
    received_end: date
    row_count: int
    manifest_hash: str
    canonical_content_hash: str
    provenance: str
    status: str
    source_status: str
    created_at: datetime


class DatasetPageResponse(BaseModel):
    """One deterministic cursor page from the immutable evidence catalog."""

    items: list[DatasetManifestResource]
    next_cursor: str | None
    has_more: bool


class DatasetCreateRequest(BaseModel):
    """One real Upstox V3 historical acquisition request."""

    model_config = ConfigDict(extra="forbid")

    instrument_key: str = Field(pattern=r"^NSE_EQ\|[A-Z0-9]{12}$", max_length=19)
    symbol: str = Field(pattern=r"^[A-Z0-9&-]{1,20}$")
    from_date: date
    to_date: date
    request_id: str | None = Field(
        default=None,
        pattern=r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$",
        max_length=128,
    )

    @model_validator(mode="after")
    def validate_request_contract(self) -> DatasetCreateRequest:
        _ = HistoricalDailyRequest(
            instrument_key=self.instrument_key,
            symbol=self.symbol,
            from_date=self.from_date,
            to_date=self.to_date,
            request_id=self.request_id,
        )
        expected_key = SUPPORTED_NSE_EQUITY_INSTRUMENTS.get(self.symbol)
        if expected_key != self.instrument_key:
            raise ValueError(
                "symbol and instrument_key must identify the same supported NSE equity"
            )
        return self
