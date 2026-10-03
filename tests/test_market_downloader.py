"""The first-run market-data download, with the network and the evidence commit replaced.

Real runs against NSE and Upstox were done by hand (see the work record); these tests pin the
behaviour that must not drift: who is matched, what is skipped, what is never overwritten, and that a
failure of one stock never stops the rest.
"""

from __future__ import annotations

import gzip
import json
import threading
from datetime import UTC, date, datetime
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from quant_system.data.market_data import AcquisitionFailureCode, HistoricalAcquisitionFailure
from quant_system.market import downloader
from quant_system.market.downloader import (
    DownloadError,
    MarketDownload,
    Target,
    TargetSet,
    build_targets,
    cache_names,
    window,
)
from quant_system.market.sources import discover_caches, scan_datasets
from tests.market_fixtures import sessions, trending_rows, write_dataset

NIFTY_CSV = (
    "Company Name,Industry,Symbol,Series,ISIN Code\n"
    "Alpha Ltd,Finance,ALPHA,EQ,INE000A00001\n"
    "Beta Ltd,Auto,BETA,EQ,INE000B00002\n"
    "Gone Ltd,Misc,GONE,EQ,INE000G00009\n"
)


def _master() -> bytes:
    rows = [
        {
            "segment": "NSE_EQ",
            "trading_symbol": "ALPHA",
            "name": "ALPHA LIMITED",
            "isin": "INE000A00001",
            "instrument_key": "NSE_EQ|INE000A00001",
            "instrument_type": "EQ",
        },
        {
            "segment": "NSE_EQ",
            "trading_symbol": "BETA",
            "name": "BETA LIMITED",
            "isin": "INE000B00002",
            "instrument_key": "NSE_EQ|INE000B00002",
            "instrument_type": "EQ",
        },
        {
            "segment": "NSE_EQ",
            "trading_symbol": "NIFTYBEES",
            "name": "NIP IND ETF NIFTY BEES",
            "isin": "INF204KB14I2",
            "instrument_key": "NSE_EQ|INF204KB14I2",
            "instrument_type": "EQ",
        },
        {
            "segment": "NSE_FO",
            "trading_symbol": "ALPHA25OCTFUT",
            "name": "ALPHA FUT",
            "isin": "",
            "instrument_key": "NSE_FO|12345",
            "instrument_type": "FUT",
        },
    ]
    return gzip.compress(json.dumps(rows).encode("utf-8"))


@pytest.fixture()
def network(monkeypatch: pytest.MonkeyPatch) -> dict[str, int]:
    calls = {"count": 0}

    def fake_get(url: str, headers: dict[str, str], timeout: float) -> bytes:
        calls["count"] += 1
        if "ind_nifty500list" in url:
            return NIFTY_CSV.encode("utf-8")
        if "NSE.json.gz" in url:
            return _master()
        raise AssertionError(f"unexpected URL {url}")

    monkeypatch.setattr(downloader, "_get", fake_get)
    return calls


# ------------------------------------------------------------------------------ universe


def test_members_are_matched_to_upstox_by_isin_and_the_unmatched_are_reported(
    tmp_path: Path, network: dict[str, int]
) -> None:
    targets = build_targets(tmp_path)
    assert [t.symbol for t in targets.members] == ["ALPHA", "BETA"]
    assert targets.members[0].instrument_key == "NSE_EQ|INE000A00001"
    assert targets.skipped == ("GONE",)
    assert targets.benchmark is not None and targets.benchmark.symbol == "NIFTYBEES"


def test_the_lists_are_cached_and_the_last_good_copy_survives_an_outage(
    tmp_path: Path, network: dict[str, int], monkeypatch: pytest.MonkeyPatch
) -> None:
    build_targets(tmp_path)
    first = network["count"]
    build_targets(tmp_path)
    assert network["count"] == first  # fresh enough: no second download

    def offline(url: str, headers: dict[str, str], timeout: float) -> bytes:
        raise OSError("no internet")

    monkeypatch.setattr(downloader, "_get", offline)
    old = 1.0
    for name in ("nifty500.csv", "upstox-nse.json.gz"):
        import os

        os.utime(tmp_path / name, (old, old))  # make both copies stale
    assert [t.symbol for t in build_targets(tmp_path).members] == ["ALPHA", "BETA"]


def test_no_internet_and_no_saved_copy_is_a_plain_message(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def offline(url: str, headers: dict[str, str], timeout: float) -> bytes:
        raise OSError("no internet")

    monkeypatch.setattr(downloader, "_get", offline)
    with pytest.raises(DownloadError) as caught:
        build_targets(tmp_path)
    assert caught.value.code == "SOURCE_UNREACHABLE"
    assert "internet connection" in caught.value.message


def test_the_window_stays_inside_upstoxs_ten_year_limit_and_names_match_the_index() -> None:
    start, end = window(date(2026, 10, 3))
    assert (end - start).days < 3653
    members, history = cache_names(date(2026, 10, 3))
    assert members == "nifty500-refresh-20161005-20261003"
    assert history == "all-market-20161005-20261003"  # the benchmark ETF is a history cache


# -------------------------------------------------------------------------------- the job


def _targets() -> TargetSet:
    members = tuple(
        Target(s, f"{s} LIMITED", f"INE000{s[0]}00001", f"NSE_EQ|INE000{s[0]}00001")
        for s in ("ALPHA", "BETA", "CHARLIE")
    )
    return TargetSet(
        members, Target("NIFTYBEES", "NIP IND ETF", "INF204KB14I2", "NSE_EQ|INF204KB14I2"), ()
    )


class _Fakes:
    """Stand-ins for the provider, the evidence commit and the corporate-action service."""

    def __init__(self, data_folder: Path) -> None:
        self.data_folder = data_folder
        self.fail_symbols: set[str] = set()
        self.explode_symbols: set[str] = set()
        self.no_actions: set[str] = set()
        self.committed: list[str] = []
        self.dates = sessions(date(2016, 10, 5), 2600)

    def acquire(self, target: Target, start: date, end: date) -> Any:
        if target.symbol in self.explode_symbols:
            raise RuntimeError("provider blew up")
        if target.symbol in self.fail_symbols:
            return HistoricalAcquisitionFailure(
                code=AcquisitionFailureCode.DATA_QUALITY_BLOCKED,
                detected_at=datetime.now(UTC),
                retryable=False,
                recovery_action="x",
            )
        return SimpleNamespace(symbol=target.symbol, instrument_key=target.instrument_key)

    def commit(self, store: Any, acquisition: Any, operation_id: str) -> None:
        cache = store.root.parent.name
        write_dataset(
            store.root.parent.parent,
            cache,
            f"ds-{acquisition.symbol}-{cache}",
            acquisition.symbol,
            trending_rows(self.dates, 100.0, 0.0004, volume=2_000_000),
            acquired_at="2026-10-03T00:00:00+00:00",
            isin=acquisition.instrument_key.split("|")[-1],
        )
        self.committed.append(acquisition.symbol)

    def actions(self, symbol: str, start: date, end: date) -> list[Any]:
        if symbol in self.no_actions:
            raise OSError("NSE did not answer")
        return [{"symbol": symbol, "exDate": "01-Jan-2024", "subject": "Dividend - Rs 1"}]


@pytest.fixture()
def fakes(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> _Fakes:
    fake = _Fakes(tmp_path / "data")
    monkeypatch.setattr(downloader, "build_targets", lambda work_dir: _targets())
    monkeypatch.setattr(downloader, "_acquire", fake.acquire)
    monkeypatch.setattr(downloader, "_commit", fake.commit)
    monkeypatch.setattr(downloader, "_fetch_actions", fake.actions)
    return fake


def _run(job: MarketDownload, folder: Path, today: date = date(2026, 10, 3)) -> dict[str, Any]:
    assert job.start(folder, today=today) is True
    assert job.wait(30)
    return job.snapshot()


def test_a_download_saves_every_stock_and_prepares_what_the_app_reads(fakes: _Fakes) -> None:
    done: list[Path] = []
    job = MarketDownload(on_done=done.append)
    snapshot = _run(job, fakes.data_folder)

    assert snapshot["state"] == "DONE" and snapshot["saved"] == 4 and snapshot["failed"] == 0
    assert snapshot["progress"] == 1.0 and snapshot["message"].startswith("Downloaded 4 stocks")
    assert sorted(fakes.committed) == ["ALPHA", "BETA", "CHARLIE", "NIFTYBEES"]
    assert done == [fakes.data_folder]

    members_cache, history_cache = cache_names(date(2026, 10, 3))
    caches = {
        c.name: c.role for c in discover_caches(fakes.data_folder / "evidence" / "market-cache")
    }
    assert caches == {
        members_cache: "REFRESH",
        history_cache: "HISTORY",
    }  # the roles the index uses

    authorities = fakes.data_folder / "authorities"
    listings = (authorities / "nse-all-listed-equities.csv").read_text(encoding="utf-8")
    assert (
        listings.startswith("Symbol,Company Name,ISIN Code,Instrument Key")
        and "NIFTYBEES" in listings
    )
    liquid = (authorities / "nse-research-universe-liquid-10y.csv").read_text(encoding="utf-8")
    assert (
        liquid.startswith("# QuantOS download:")
        and "ALPHA" in liquid
        and "SURVIVORSHIP BIAS" in liquid
    )
    assert (authorities / "nse-corporate-actions-ALPHA.json").is_file()


def test_one_bad_stock_never_stops_the_others_and_is_listed_with_a_reason(fakes: _Fakes) -> None:
    fakes.fail_symbols = {"BETA"}
    fakes.explode_symbols = {"CHARLIE"}
    snapshot = _run(MarketDownload(), fakes.data_folder)
    assert snapshot["state"] == "DONE" and snapshot["saved"] == 2 and snapshot["failed"] == 2
    reasons = {f["symbol"]: f["reason"] for f in snapshot["failures"]}
    assert "data checks" in reasons["BETA"]
    assert reasons["CHARLIE"] == "something unexpected went wrong"
    assert "left out by the data checks" in snapshot["message"]


def test_missing_corporate_actions_are_counted_not_fatal(fakes: _Fakes) -> None:
    fakes.no_actions = {"ALPHA", "BETA"}
    snapshot = _run(MarketDownload(), fakes.data_folder)
    assert snapshot["state"] == "DONE" and snapshot["without_actions"] == 2
    assert not (fakes.data_folder / "authorities" / "nse-corporate-actions-ALPHA.json").exists()


def test_a_second_run_continues_instead_of_downloading_everything_again(fakes: _Fakes) -> None:
    fakes.fail_symbols = {"CHARLIE"}
    _run(MarketDownload(), fakes.data_folder)
    assert sorted(fakes.committed) == ["ALPHA", "BETA", "NIFTYBEES"]

    fakes.committed.clear()
    fakes.fail_symbols = set()
    snapshot = _run(MarketDownload(), fakes.data_folder)
    assert fakes.committed == ["CHARLIE"]  # only the one that is missing
    assert snapshot["saved"] == 4 and snapshot["state"] == "DONE"
    members_cache, _ = cache_names(date(2026, 10, 3))
    cache = next(
        c
        for c in discover_caches(fakes.data_folder / "evidence" / "market-cache")
        if c.name == members_cache
    )
    assert len(scan_datasets(cache)) == 3  # ALPHA, BETA, CHARLIE: one dataset each, none twice


def test_a_file_that_did_not_come_from_a_download_is_never_replaced(fakes: _Fakes) -> None:
    authorities = fakes.data_folder / "authorities"
    authorities.mkdir(parents=True)
    own = authorities / "nse-corporate-actions-ALPHA.json"
    own.write_text('[{"keep": "me"}]', encoding="utf-8")
    listings = authorities / "nse-all-listed-equities.csv"
    listings.write_text("Symbol\nMINE\n", encoding="utf-8")
    foreign_liquid = authorities / "nse-research-universe-liquid-10y.csv"
    foreign_liquid.write_text("Symbol\nMINE\n", encoding="utf-8")

    _run(MarketDownload(), fakes.data_folder)
    assert own.read_text(encoding="utf-8") == '[{"keep": "me"}]'
    assert listings.read_text(encoding="utf-8") == "Symbol\nMINE\n"
    assert foreign_liquid.read_text(encoding="utf-8") == "Symbol\nMINE\n"

    # A file the download itself wrote is refreshed on a later day's download.
    beta = authorities / "nse-corporate-actions-BETA.json"
    beta.write_text("[]", encoding="utf-8")
    _run(MarketDownload(), fakes.data_folder, today=date(2026, 10, 4))
    assert "Dividend" in beta.read_text(encoding="utf-8")
    assert own.read_text(encoding="utf-8") == '[{"keep": "me"}]'  # still never replaced


def test_nothing_saved_is_an_error_with_the_first_reason(fakes: _Fakes) -> None:
    fakes.fail_symbols = {"ALPHA", "BETA", "CHARLIE", "NIFTYBEES"}
    snapshot = _run(MarketDownload(), fakes.data_folder)
    assert snapshot["state"] == "ERROR"
    assert snapshot["message"].startswith("No stocks could be downloaded")


def test_stopping_is_resumable_and_does_not_connect_half_a_download(
    fakes: _Fakes, monkeypatch: pytest.MonkeyPatch
) -> None:
    job = MarketDownload(on_done=lambda folder: pytest.fail("must not connect a stopped download"))
    seen = threading.Event()
    original = fakes.acquire

    def acquire_then_stop(target: Target, start: date, end: date) -> Any:
        if not seen.is_set():
            seen.set()
            job.cancel()
        return original(target, start, end)

    monkeypatch.setattr(downloader, "_acquire", acquire_then_stop)
    snapshot = _run(job, fakes.data_folder)
    assert snapshot["state"] == "CANCELLED"
    assert "Start again to continue" in snapshot["message"]


def test_a_second_start_while_running_is_refused(
    fakes: _Fakes, monkeypatch: pytest.MonkeyPatch
) -> None:
    release = threading.Event()
    original = fakes.acquire

    def slow(target: Target, start: date, end: date) -> Any:
        release.wait(10)
        return original(target, start, end)

    monkeypatch.setattr(downloader, "_acquire", slow)
    job = MarketDownload()
    assert job.start(fakes.data_folder, today=date(2026, 10, 3)) is True
    assert job.start(fakes.data_folder, today=date(2026, 10, 3)) is False
    release.set()
    assert job.wait(30)
    assert job.snapshot()["state"] == "DONE"


def test_too_little_disk_space_is_refused_before_any_download(
    fakes: _Fakes, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        downloader.shutil, "disk_usage", lambda path: SimpleNamespace(free=1_000, total=2, used=1)
    )
    snapshot = _run(MarketDownload(), fakes.data_folder)
    assert snapshot["state"] == "ERROR" and "disk space" in snapshot["message"]
    assert fakes.committed == []


def test_the_anonymous_history_option_is_off_by_default() -> None:
    from quant_system.data.upstox import UpstoxClient

    assert UpstoxClient().allow_anonymous_history is False
    assert UpstoxClient(allow_anonymous_history=True).allow_anonymous_history is True
