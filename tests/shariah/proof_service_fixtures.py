"""Builders for the proof service tests: stores with real-shaped filings, fake prices, a sample and a clock.

This module holds no tests. Nothing here touches the network.
"""

from __future__ import annotations

import socket
from collections.abc import Iterator
from dataclasses import dataclass, field
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any

import numpy as np
import pytest

from quant_system.shariah.filings.extract import extract_figures
from quant_system.shariah.filings.models import FilingFigures
from quant_system.shariah.filings.store import FilingsStore, IndustrySnapshot, write_snapshot
from quant_system.shariah.services.filing_jobs import FilingJobs
from quant_system.shariah.services.proof_runtime import ProofRuntime
from quant_system.shariah.services.proof_service import ProofService
from tests.shariah.test_filings_builders import (
    FETCHED_AT,
    TCS_FIXTURE,
    make_bank_filing,
    make_filing,
    make_row,
)

TODAY = datetime(2025, 1, 7, 12, 0, tzinfo=UTC)
LATER = datetime(2026, 10, 7, 12, 0, tzinfo=UTC)
TCS_SHARES = 3_620_000_000
TCS_NAME = "Tata Consultancy Services Limited"
GROUPS = {
    "TCS": "Information Technology",
    "DRYBREW": "Fast Moving Consumer Goods",
    "FOODCO": "Fast Moving Consumer Goods",
    "HDFCBANK": "Financial Services",
    "BROKEN": "Information Technology",
}


class Clock:
    """A clock that only moves when a test moves it."""

    def __init__(self, now: datetime = TODAY) -> None:
        self.now = now

    def __call__(self) -> datetime:
        return self.now

    def advance(self, days: int) -> None:
        self.now += timedelta(days=days)


@dataclass(frozen=True)
class Prices:
    dates: list[str]
    close: np.ndarray


@dataclass
class FakeBars:
    """Prices by symbol. Counts how often each stock was asked for, so a test can see what was recomputed."""

    series: dict[str, Prices] = field(default_factory=dict)
    calls: list[str] = field(default_factory=list)
    build: str = "first"

    def version(self) -> str:
        return self.build

    def bars(self, symbol: str, start: str | None = None, end: str | None = None) -> Prices:
        self.calls.append(symbol)
        if symbol not in self.series:
            raise LookupError(symbol)
        return self.series[symbol]


class FakeSample:
    def __init__(self, rows: dict[str, dict[str, Any]] | None = None) -> None:
        self.rows = rows or {}

    def company(self, symbol: str) -> dict[str, Any] | None:
        return self.rows.get(symbol)


def three_prices(first: float = 100.0, middle: float = 200.0, last: float = 300.0) -> Prices:
    """Three closes spread over three years that end just before TODAY. Their average is the middle one."""
    return Prices(
        ["2022-01-10", "2023-07-03", "2025-01-06"],
        np.array([first, middle, last], dtype=np.float64),
    )


def figures_for(symbol: str, name: str, **options: Any) -> FilingFigures:
    """Figures read, by the real reader, from a small filing built to the options (see `make_filing`)."""
    period_end: date = options.get("period_end", date(2024, 9, 30))
    row = make_row(symbol=symbol, company_name=name, period_end=period_end)
    return extract_figures(make_filing(**options), row, FETCHED_AT)


def tcs_figures() -> FilingFigures:
    """The real TCS filing for the six months to 30 Sep 2024."""
    return extract_figures(TCS_FIXTURE.read_bytes(), make_row(), FETCHED_AT)


def bank_figures() -> FilingFigures:
    row = make_row(symbol="HDFCBANK", company_name="HDFC Bank Limited", lender_flag="B")
    return extract_figures(make_bank_filing(), row, FETCHED_AT)


def broken_figures() -> FilingFigures:
    """A filing whose assets do not add up: read, but it does not agree with itself."""
    return figures_for("BROKEN", "Broken Systems Limited", balance={"CurrentAssets": "1.00"})


def foodco_figures(**options: Any) -> FilingFigures:
    """A company in a sensitive industry group that lists a clean segment and keeps its ratios low."""
    balance = {"TradeReceivablesCurrent": "10000000000.00", "CurrentInvestments": "10000000000.00"}
    chosen = {"segments": ["Packaged foods"], "balance": balance, **options}
    return figures_for("FOODCO", "Food Company Limited", **chosen)


def standard_filings() -> dict[str, FilingFigures]:
    return {
        "TCS": tcs_figures(),
        "DRYBREW": figures_for("DRYBREW", "Dry Brewery Limited"),
        "FOODCO": foodco_figures(),
        "HDFCBANK": bank_figures(),
        "BROKEN": broken_figures(),
    }


def make_store(tmp_path: Path, filings: dict[str, FilingFigures] | None = None) -> FilingsStore:
    """A store with a bundled snapshot of the given filings and a per-user database that does not exist yet."""
    chosen = standard_filings() if filings is None else filings
    snapshot = tmp_path / "filings_snapshot.json.gz"
    write_snapshot(snapshot, chosen, "2026-10-07", IndustrySnapshot(GROUPS, "2026-10-07"))
    return FilingsStore(snapshot, tmp_path / "user_filings.sqlite")


def make_service(
    store: FilingsStore,
    sample: FakeSample | None = None,
    bars: FakeBars | None = None,
    clock: Clock | None = None,
) -> ProofService:
    return ProofService(store, sample or FakeSample(), bars, clock or Clock())


SAMPLE_ROW: dict[str, Any] = {
    "ticker": "SAMPLEONLY.NS",
    "symbol": "SAMPLEONLY",
    "company_name": "Sample Only Limited",
    "sector": "Information Technology",
    "industry": "Software",
    "business_summary": "software services",
    "sector_compliant": 1,
    "sector_failure_reason": None,
    "total_assets": 1000.0,
    "total_debt": 50.0,
    "total_cash_and_investments": 100.0,
    "total_receivables": 120.0,
    "avg_36m_market_cap": 4000.0,
    "total_impermissible_income": 1.0,
    "total_revenue": 500.0,
}


LOCAL_HOSTS = frozenset({"127.0.0.1", "::1", "localhost", "testserver", "localhost.localdomain"})


@pytest.fixture()
def no_network(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    """Fail any test that tries to reach a computer other than this one: filings tests never touch NSE."""
    real_connect, real_lookup = socket.socket.connect, socket.getaddrinfo

    def connect(self: socket.socket, address: Any) -> Any:
        host = address[0] if isinstance(address, tuple) else str(address)
        if host not in LOCAL_HOSTS:
            raise AssertionError(f"a test tried to reach {host}")
        return real_connect(self, address)

    def lookup(host: Any, *args: Any, **kwargs: Any) -> Any:
        if host not in LOCAL_HOSTS and host is not None:
            raise AssertionError(f"a test tried to look up {host}")
        return real_lookup(host, *args, **kwargs)

    monkeypatch.setattr(socket.socket, "connect", connect)
    monkeypatch.setattr(socket, "getaddrinfo", lookup)
    yield


class NoReading:
    """A reader of NSE that must never be asked: tests that hold no filings never fetch any."""

    def read_company(self, symbol: str) -> Any:
        raise AssertionError(f"a test tried to read the filing for {symbol}")


def empty_runtime() -> ProofRuntime:
    """A proof runtime that holds no filing at all, so the older sample-based screens behave exactly as they did."""
    store = FilingsStore(None, None)
    service = ProofService(store, FakeSample(), None, Clock())
    return ProofRuntime(service, FilingJobs(store, NoReading, lambda: []))
