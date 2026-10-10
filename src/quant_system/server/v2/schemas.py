"""Request bodies for API v2. Responses are plain JSON documents built by the services."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Any, Literal

from pydantic import BaseModel, Field


class DataFolderRequest(BaseModel):
    path: str = Field(min_length=3, max_length=500)


class FolderPickRequest(BaseModel):
    title: str = Field(default="Choose your QuantOS data folder", max_length=100)
    initial: str | None = Field(default=None, max_length=500)


class LabRunRequest(BaseModel):
    template_id: str = Field(min_length=1, max_length=40)
    params: dict[str, Any] = Field(default_factory=dict)
    scope: Literal["stocks", "universe"] = "stocks"
    symbols: list[str] = Field(default_factory=list, max_length=20)
    universe: str | None = None
    start: str | None = Field(default=None, max_length=10)
    end: str | None = Field(default=None, max_length=10)
    capital: Decimal | None = Field(default=None, ge=Decimal("10000"), le=Decimal("1000000000"))
    slippage_bps: Decimal = Field(default=Decimal("5"), ge=0, le=200)


class DownloadRequest(BaseModel):
    mode: Literal["auto", "full", "update"] = "auto"


class PaperBookRequest(BaseModel):
    name: str = Field(min_length=1, max_length=60)
    template_id: str = Field(min_length=1, max_length=40)
    params: dict[str, Any] = Field(default_factory=dict)
    scope: Literal["stocks", "universe"] = "stocks"
    symbols: list[str] = Field(default_factory=list, max_length=20)
    universe: str | None = None
    capital: Decimal = Field(ge=Decimal("10000"), le=Decimal("1000000000"))
    slippage_bps: Decimal = Field(default=Decimal("5"), ge=0, le=200)


class PlacementRequest(BaseModel):
    """What the person did with one order a paper book decided. Typed by them, never read from a broker."""

    as_of: date
    symbol: str = Field(min_length=1, max_length=30)
    side: Literal["BUY", "SELL"]
    status: Literal["PLACED", "SKIPPED"]
    quantity: int | None = Field(default=None, ge=1, le=100_000_000)
    price: Decimal | None = Field(default=None, gt=0, le=Decimal("100000000"))


class WatchlistRequest(BaseModel):
    symbol: str = Field(min_length=1, max_length=30)


class HoldingRequest(BaseModel):
    symbol: str = Field(min_length=1, max_length=30)
    quantity: int = Field(ge=1, le=100_000_000)
    avg_price: Decimal = Field(gt=0, le=Decimal("100000000"))
    buy_date: date
    note: str = Field(default="", max_length=200)
    # Which account holds it. Left out, a new stock goes to the first account and an edited one stays where it is.
    account_id: int | None = None


class AccountRequest(BaseModel):
    """Only generous ceilings here: the account rules in ``accounts.py`` give the plain messages a person reads."""

    name: str = Field(default="", max_length=1000)
    owner: str = Field(default="Me", max_length=1000)
    kind: str = Field(default="Demat account", max_length=1000)
    broker: str = Field(default="", max_length=1000)


class CostsRequest(BaseModel):
    segment: Literal["delivery", "intraday", "futures", "options"] = "delivery"
    buy_price: Decimal = Field(gt=0, le=Decimal("10000000"))
    sell_price: Decimal = Field(gt=0, le=Decimal("10000000"))
    quantity: int = Field(ge=1, le=10_000_000)
    trade_date: date | None = None


class PositionSizeRequest(BaseModel):
    capital: Decimal | None = Field(default=None, gt=0)
    risk_pct: Decimal | None = Field(default=None, gt=0, le=100)
    entry: Decimal = Field(gt=0)
    stop: Decimal = Field(gt=0)
    lot_size: int = Field(default=1, ge=1, le=100_000)


class OptionLegRequest(BaseModel):
    kind: Literal["call", "put"]
    side: Literal["buy", "sell"]
    strike: float = Field(gt=0)
    premium: float = Field(ge=0)
    lots: int = Field(default=1, ge=1, le=1000)
    lot_size: int = Field(default=1, ge=1, le=100_000)


class OptionsPayoffRequest(BaseModel):
    spot: float = Field(gt=0)
    days_to_expiry: int = Field(ge=0, le=3650)
    volatility_pct: float = Field(gt=0, lt=500)
    rate_pct: float = Field(default=7.0, ge=0, le=50)
    legs: list[OptionLegRequest] = Field(min_length=1, max_length=4)


class SecretRequest(BaseModel):
    value: str = Field(min_length=1, max_length=2560)


class CredentialTestRequest(BaseModel):
    provider: str = Field(min_length=1, max_length=50)
    credentials: dict[str, str] = Field(default_factory=dict)


class EnvFileUpload(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    text: str = Field(max_length=200_000)


class CredentialImportRequest(BaseModel):
    """Dotenv files to read keys from. ``dry_run`` defaults to True so a bare call can only preview."""

    files: list[EnvFileUpload] = Field(min_length=1, max_length=10)
    dry_run: bool = True
    names: list[str] | None = Field(default=None, max_length=200)


class CliLaunchRequest(BaseModel):
    agent_id: str = Field(min_length=1, max_length=50)
    action: Literal["run", "signin", "install", "update", "custom"] = "run"
    custom_command: str | None = Field(default=None, max_length=500)


class CliAutoUpdateRequest(BaseModel):
    enabled: bool


class CliCodeRequest(BaseModel):
    text: str = Field(min_length=1, max_length=500)


class HardwareAcceleratorRequest(BaseModel):
    target: Literal["auto", "npu", "gpu", "cpu"]
