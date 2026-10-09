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
from typing import Any, Literal

import pytest

from quant_system.data.market_data import AcquisitionFailureCode, HistoricalAcquisitionFailure
from quant_system.market import downloader
from quant_system.market.downloader import (
    MARKER,
    DownloadError,
    MarketDownload,
    Target,
    TargetSet,
    baseline_exists,
    build_targets,
    cache_names,
    refresh_window,
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
    history, refresh = cache_names(date(2026, 10, 3))
    assert history == "all-market-20161005-20261003"  # the ten-year baseline
    assert (
        refresh == "nifty500-refresh-20231004-20261003"
    )  # the recent window; makes NIFTY 500 members
    recent_start, recent_end = refresh_window(date(2026, 10, 3))
    assert (recent_end - recent_start).days == 1095


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
        self.empty_actions: set[str] = set()
        self.committed: list[str] = []
        self.dates = sessions(date(2016, 10, 5), 2600)
        self.symbol_changes_text: str = ""
        self.symbol_changes_error: bool = False

    def symbol_changes(self, work_dir: Any) -> str:
        if self.symbol_changes_error:
            raise DownloadError("SOURCE_UNREACHABLE", "x")
        return self.symbol_changes_text

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
        if symbol in self.empty_actions:
            return []
        return [{"symbol": symbol, "exDate": "01-Jan-2024", "subject": "Dividend - Rs 1"}]


@pytest.fixture()
def fakes(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> _Fakes:
    fake = _Fakes(tmp_path / "data")
    monkeypatch.setattr(downloader, "build_targets", lambda work_dir: _targets())
    monkeypatch.setattr(downloader, "_acquire", fake.acquire)
    monkeypatch.setattr(downloader, "_commit", fake.commit)
    monkeypatch.setattr(downloader, "_fetch_actions", fake.actions)
    monkeypatch.setattr(downloader, "_fetch_symbol_changes", fake.symbol_changes)
    return fake


def _run(
    job: MarketDownload,
    folder: Path,
    today: date = date(2026, 10, 3),
    mode: Literal["auto", "full", "update"] = "auto",
) -> dict[str, Any]:
    assert job.start(folder, today=today, mode=mode) is True
    assert job.wait(30)
    return job.snapshot()


def test_a_download_saves_every_stock_and_prepares_what_the_app_reads(fakes: _Fakes) -> None:
    done: list[Path] = []
    job = MarketDownload(on_done=done.append)
    snapshot = _run(job, fakes.data_folder)

    # Two passes over four stocks: the ten-year baseline, then the recent window.
    assert snapshot["state"] == "DONE" and snapshot["saved"] == 8 and snapshot["failed"] == 0
    assert snapshot["total"] == 8 and snapshot["mode"] == "full"
    assert (
        snapshot["progress"] == 1.0
        and snapshot["message"] == "Downloaded 4 stocks up to 03 Oct 2026."
    )
    assert sorted(fakes.committed) == sorted(["ALPHA", "BETA", "CHARLIE", "NIFTYBEES"] * 2)
    assert done == [fakes.data_folder]

    history_cache, refresh_cache = cache_names(date(2026, 10, 3))
    market_cache = fakes.data_folder / "evidence" / "market-cache"
    caches = {c.name: c.role for c in discover_caches(market_cache)}
    assert caches == {
        history_cache: "HISTORY",
        refresh_cache: "REFRESH",
    }  # the roles the index uses
    assert (market_cache / history_cache / MARKER).is_file()
    assert (market_cache / refresh_cache / MARKER).is_file()
    assert baseline_exists(fakes.data_folder)

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
    # Two stocks get through both passes (4 saves); each failed stock is counted once, not per pass.
    assert snapshot["state"] == "DONE" and snapshot["saved"] == 4 and snapshot["failed"] == 2
    assert len(snapshot["failures"]) == 2
    reasons = {f["symbol"]: f["reason"] for f in snapshot["failures"]}
    assert "data checks" in reasons["BETA"]
    assert reasons["CHARLIE"] == "something unexpected went wrong"
    assert snapshot["message"] == "Downloaded 2 stocks up to 03 Oct 2026."


def test_missing_corporate_actions_are_counted_not_fatal(fakes: _Fakes) -> None:
    fakes.no_actions = {"ALPHA", "BETA"}
    snapshot = _run(MarketDownload(), fakes.data_folder)
    assert snapshot["state"] == "DONE" and snapshot["without_actions"] == 2
    assert not (fakes.data_folder / "authorities" / "nse-corporate-actions-ALPHA.json").exists()


def test_a_second_run_continues_instead_of_downloading_everything_again(fakes: _Fakes) -> None:
    fakes.fail_symbols = {"CHARLIE"}
    _run(MarketDownload(), fakes.data_folder)
    assert sorted(fakes.committed) == sorted(["ALPHA", "BETA", "NIFTYBEES"] * 2)

    fakes.committed.clear()
    fakes.fail_symbols = set()
    snapshot = _run(MarketDownload(), fakes.data_folder)
    assert fakes.committed == ["CHARLIE", "CHARLIE"]  # only the one that is missing, in both passes
    assert snapshot["saved"] == 8 and snapshot["state"] == "DONE"
    _, refresh_cache = cache_names(date(2026, 10, 3))
    cache = next(
        c
        for c in discover_caches(fakes.data_folder / "evidence" / "market-cache")
        if c.name == refresh_cache
    )
    assert len(scan_datasets(cache)) == 4  # one dataset per stock and the benchmark, none twice


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


def test_a_left_out_stock_is_explained_in_words_not_codes() -> None:
    from quant_system.data.market_data import (
        FindingDisposition,
        FindingSeverity,
        QualityCode,
        QualityFinding,
    )

    def blocked(*findings: QualityFinding) -> HistoricalAcquisitionFailure:
        return HistoricalAcquisitionFailure(
            code=AcquisitionFailureCode.DATA_QUALITY_BLOCKED,
            detected_at=datetime.now(UTC),
            retryable=False,
            recovery_action="x",
            quality_findings=findings,
        )

    def finding(code: QualityCode, count: int) -> QualityFinding:
        return QualityFinding(code, FindingSeverity.BLOCKING, count, FindingDisposition.REJECTED)

    many = downloader._reason(blocked(finding(QualityCode.INVALID_OHLC, 8)))
    assert many.startswith("its price history has 8 days where the high, low and close do not fit")
    assert "does not guess around bad data" in many
    assert "1 day with an impossible trading volume" in downloader._reason(
        blocked(finding(QualityCode.INVALID_VOLUME, 1))
    )
    both = downloader._reason(
        blocked(finding(QualityCode.INVALID_OHLC, 2), finding(QualityCode.DUPLICATE_KEY, 1))
    )
    assert "2 days where" in both and " and 1 day listed twice" in both
    assert downloader._reason(blocked()) == "its price history failed the data checks"
    assert "DATA_QUALITY" not in many


def _cache_dirs(folder: Path) -> set[str]:
    return {c.name for c in (folder / "evidence" / "market-cache").iterdir() if c.is_dir()}


def test_a_later_days_run_only_updates_the_recent_window_and_replaces_the_old_one(
    fakes: _Fakes,
) -> None:
    _run(MarketDownload(), fakes.data_folder)  # day one: the full download
    history, first_refresh = cache_names(date(2026, 10, 3))
    fakes.committed.clear()

    snapshot = _run(MarketDownload(), fakes.data_folder, today=date(2026, 10, 4))
    _, second_refresh = cache_names(date(2026, 10, 4))
    assert snapshot["mode"] == "update" and snapshot["state"] == "DONE"
    assert snapshot["total"] == 4 and snapshot["message"] == "Updated 4 stocks up to 04 Oct 2026."
    assert sorted(fakes.committed) == ["ALPHA", "BETA", "CHARLIE", "NIFTYBEES"]  # one pass only
    # The baseline stays; the superseded recent window is gone; the new one is in place.
    assert _cache_dirs(fakes.data_folder) == {history, second_refresh}
    assert first_refresh not in _cache_dirs(fakes.data_folder)


def test_asking_for_a_full_download_rebuilds_the_baseline_and_clears_the_old_one(
    fakes: _Fakes,
) -> None:
    _run(MarketDownload(), fakes.data_folder)
    old_history, old_refresh = cache_names(date(2026, 10, 3))
    snapshot = _run(MarketDownload(), fakes.data_folder, today=date(2026, 10, 4), mode="full")
    new_history, new_refresh = cache_names(date(2026, 10, 4))
    assert snapshot["mode"] == "full" and snapshot["total"] == 8
    assert _cache_dirs(fakes.data_folder) == {new_history, new_refresh}
    assert old_history not in _cache_dirs(fakes.data_folder)
    assert old_refresh not in _cache_dirs(fakes.data_folder)


def test_a_cache_this_download_did_not_make_is_never_removed(fakes: _Fakes) -> None:
    market_cache = fakes.data_folder / "evidence" / "market-cache"
    theirs = market_cache / "nifty500-refresh-20200101-20200102"  # no marker: someone else's
    (theirs / "store" / "datasets").mkdir(parents=True)
    _run(MarketDownload(), fakes.data_folder)
    _run(MarketDownload(), fakes.data_folder, today=date(2026, 10, 4))
    assert theirs.is_dir()


def test_there_is_no_baseline_on_an_empty_folder(tmp_path: Path) -> None:
    assert baseline_exists(tmp_path) is False


def test_an_empty_answer_never_replaces_corporate_actions_a_download_already_saved(
    fakes: _Fakes,
) -> None:
    _run(MarketDownload(), fakes.data_folder, today=date(2026, 10, 3))
    authorities = fakes.data_folder / "authorities"
    alpha_actions = authorities / "nse-corporate-actions-ALPHA.json"
    beta_actions = authorities / "nse-corporate-actions-BETA.json"
    assert "Dividend" in alpha_actions.read_text(encoding="utf-8")
    assert "Dividend" in beta_actions.read_text(encoding="utf-8")

    fakes.empty_actions = {"ALPHA"}
    snapshot = _run(MarketDownload(), fakes.data_folder, today=date(2026, 10, 4))
    assert snapshot["state"] == "DONE"
    assert "Dividend" in alpha_actions.read_text(encoding="utf-8")
    assert "Dividend" in beta_actions.read_text(encoding="utf-8")


# ---------------------------------------------------------------------- symbol changes


def _sample_symbol_changes() -> str:
    rows = [f"Company {i},OLD{i:03d},NEW{i:03d},01-JAN-2020" for i in range(1, 151)]
    rows.append("HEG Advanced Materials Limited,HEG,HEGAM,22-SEP-2026")
    return "\n".join(rows) + "\n"


def test_a_download_keeps_the_symbol_change_list_in_the_data_folder(fakes: _Fakes) -> None:
    """A download keeps the symbol-change list in the data folder authorities."""
    csv_text = _sample_symbol_changes()
    fakes.symbol_changes_text = csv_text

    snapshot = _run(MarketDownload(), fakes.data_folder)

    symbol_file = fakes.data_folder / "authorities" / "nse-symbol-changes.csv"
    assert symbol_file.is_file()
    assert symbol_file.read_text(encoding="utf-8") == csv_text
    assert snapshot["state"] == "DONE"


def test_an_implausibly_short_list_never_replaces_a_good_one(fakes: _Fakes) -> None:
    """A short list (< 100 changes) never replaces an existing good file."""
    good_text = _sample_symbol_changes()
    fakes.symbol_changes_text = good_text
    _run(MarketDownload(), fakes.data_folder, today=date(2026, 10, 3))

    symbol_file = fakes.data_folder / "authorities" / "nse-symbol-changes.csv"
    assert symbol_file.read_text(encoding="utf-8") == good_text

    fakes.symbol_changes_text = "HEG Advanced Materials Limited,HEG,HEGAM,22-SEP-2026\n"
    snapshot = _run(MarketDownload(), fakes.data_folder, today=date(2026, 10, 4))
    assert snapshot["state"] == "DONE"
    assert symbol_file.read_text(encoding="utf-8") == good_text


def test_an_unreachable_list_keeps_the_last_copy_and_the_download_still_finishes(
    fakes: _Fakes,
) -> None:
    """When the network fails, the existing file is kept and download finishes with state DONE."""
    good_text = _sample_symbol_changes()
    fakes.symbol_changes_text = good_text
    _run(MarketDownload(), fakes.data_folder, today=date(2026, 10, 3))

    symbol_file = fakes.data_folder / "authorities" / "nse-symbol-changes.csv"
    assert symbol_file.read_text(encoding="utf-8") == good_text

    fakes.symbol_changes_error = True
    snapshot = _run(MarketDownload(), fakes.data_folder, today=date(2026, 10, 4))
    assert snapshot["state"] == "DONE"
    assert symbol_file.read_text(encoding="utf-8") == good_text


def test_no_symbol_change_list_and_no_network_is_not_an_error(fakes: _Fakes) -> None:
    """When there is no existing file and network fails, download still completes cleanly."""
    fakes.symbol_changes_error = True
    snapshot = _run(MarketDownload(), fakes.data_folder)
    assert snapshot["state"] == "DONE"
    symbol_file = fakes.data_folder / "authorities" / "nse-symbol-changes.csv"
    assert not symbol_file.exists()


def test_the_symbol_change_list_is_fetched_from_nse_and_cached(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """_fetch_symbol_changes calls _get once with SYMBOL_CHANGES_URL and caches for 24 hours."""
    calls: list[str] = []
    sample_csv = b"HEG Advanced Materials Limited,HEG,HEGAM,22-SEP-2026\n"

    def fake_get(url: str, headers: dict[str, str], timeout: float) -> bytes:
        calls.append(url)
        assert headers.get("User-Agent") == downloader._BROWSER_AGENT
        assert headers.get("Referer") == "https://www.nseindia.com/"
        return sample_csv

    monkeypatch.setattr(downloader, "_get", fake_get)

    text1 = downloader._fetch_symbol_changes(tmp_path)
    text2 = downloader._fetch_symbol_changes(tmp_path)

    assert calls == [downloader.SYMBOL_CHANGES_URL]
    assert text1 == sample_csv.decode("utf-8-sig")
    assert text2 == text1


def test_write_symbol_changes_returns_the_count_and_never_raises(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """write_symbol_changes returns count of changes in file afterwards and never raises."""
    authorities = tmp_path / "authorities"
    work_dir = tmp_path / "downloads"
    authorities.mkdir(parents=True)
    work_dir.mkdir(parents=True)

    def fail_fetch(wd: Path) -> str:
        raise DownloadError("SOURCE_UNREACHABLE", "Cannot reach NSE")

    monkeypatch.setattr(downloader, "_fetch_symbol_changes", fail_fetch)
    count = downloader.write_symbol_changes(authorities, work_dir)
    assert count == 0

    good_text = _sample_symbol_changes()
    monkeypatch.setattr(downloader, "_fetch_symbol_changes", lambda wd: good_text)
    count = downloader.write_symbol_changes(authorities, work_dir)
    assert count == 151

    monkeypatch.setattr(downloader, "_fetch_symbol_changes", fail_fetch)
    count = downloader.write_symbol_changes(authorities, work_dir)
    assert count == 151

    short_text = "HEG Advanced Materials Limited,HEG,HEGAM,22-SEP-2026\n"
    monkeypatch.setattr(downloader, "_fetch_symbol_changes", lambda wd: short_text)
    count = downloader.write_symbol_changes(authorities, work_dir)
    assert count == 151


def test_seeded_baseline_without_marker_is_recognised(tmp_path: Path) -> None:
    """A pre-existing or seeded 10-year baseline cache without .quantos-download is recognized."""
    market_cache = tmp_path / "evidence" / "market-cache"
    seeded = market_cache / "all-market-20160822-20260821"
    (seeded / "store" / "datasets").mkdir(parents=True)
    assert baseline_exists(tmp_path) is True
