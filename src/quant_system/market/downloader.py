"""Download market data for a first-time user, on their own computer, from public sources.

QuantOS cannot ship market data: the prices belong to the exchange and the data provider, and the app
runs on many computers. Instead each person downloads it for themselves:

* the list of stocks is the NSE's published NIFTY 500 file, joined to Upstox's public instrument list;
* the daily prices come from Upstox's historical-candle service, which answers without an account;
* corporate actions (splits, dividends, demergers) come from the NSE's public filings service.

Prices go through the same strict acquisition checks and are written to the same immutable evidence
store as every other dataset QuantOS reads, in a cache named ``nifty500-refresh-<from>-<to>`` that
the market index already understands. A stock that fails the checks is left out and reported; nothing
is repaired or filled in.
"""

from __future__ import annotations

import csv
import gzip
import io
import json
import logging
import os
import shutil
import statistics
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any, Literal

from quant_system.data.evidence_draft import draft_from_historical_acquisition
from quant_system.data.market_data import (
    HistoricalAcquisition,
    HistoricalAcquisitionFailure,
    HistoricalDailyRequest,
)
from quant_system.data.upstox import UpstoxClient
from quant_system.evidence import EvidenceStore, EvidenceStoreConfig
from quant_system.market.index import BENCHMARK_SYMBOL
from quant_system.market.sources import CacheRef, read_bars, scan_datasets
from quant_system.market.symbol_changes import parse_symbol_changes

logger = logging.getLogger("quantos.market.downloader")

NIFTY500_URL = "https://nsearchives.nseindia.com/content/indices/ind_nifty500list.csv"
INSTRUMENTS_URL = "https://assets.upstox.com/market-quote/instruments/exchange/NSE.json.gz"
NSE_ACTIONS_URL = "https://www.nseindia.com/api/corporates-corporateActions"
NSE_ACTIONS_REFERER = "https://www.nseindia.com/companies-listing/corporate-filings-actions"
SYMBOL_CHANGES_URL = "https://nsearchives.nseindia.com/content/equities/symbolchange.csv"
SYMBOL_CHANGES_FILE = "nse-symbol-changes.csv"  # the exact name; the index reads it by this name
MIN_SYMBOL_CHANGES = (
    100  # NSE's list has about 1,000 rows; far fewer means a truncated or wrong answer
)
_BROWSER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
)

HISTORY_DAYS = 3650  # just under Upstox's ten-year retrieval limit
REFRESH_DAYS = 1095  # three years: the rolling window the index stitches onto the history
MARKER = ".quantos-download"  # written in every cache this download creates (and may later replace)
WORKERS = 6
MIN_FREE_BYTES = 1_300_000_000  # the evidence store refuses to write below 1 GiB free
LIQUID_MIN_TURNOVER = 50_000_000  # Rs 5 crore median daily turnover
LIQUID_MIN_YEARS = 9.5
GENERATED_MARK = "# QuantOS download:"

LISTINGS_FILE = "nse-all-listed-equities.csv"
# Names of the corporate-action files this download wrote. A file that is not on this list came from
# somewhere else (a source checkout tracks some of them) and is never replaced.
GENERATED_ACTIONS = "nse-corporate-actions-downloaded.txt"
LIQUID_FILE = "nse-research-universe-liquid-10y.csv"

_FAILURE_TEXT = {
    "PROVIDER_UNAUTHORIZED": "the data provider asked for a sign-in",
    "PROVIDER_RATE_LIMITED": "the data provider asked us to slow down",
    "PROVIDER_UNAVAILABLE": "the data provider did not answer",
}


class DownloadError(RuntimeError):
    """The download cannot start or cannot continue. The message is written for the person."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


@dataclass(frozen=True, slots=True)
class Target:
    symbol: str
    name: str
    isin: str
    instrument_key: str


@dataclass(frozen=True, slots=True)
class TargetSet:
    members: tuple[Target, ...]
    benchmark: Target | None
    skipped: tuple[str, ...]


def _http_get(url: str, headers: dict[str, str], timeout: float) -> bytes:
    request = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return bytes(response.read())


# Replaced in tests; production code always goes through this indirection.
_get: Callable[[str, dict[str, str], float], bytes] = _http_get


def _atomic_write(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + f".{os.getpid()}.tmp")
    temporary.write_bytes(data)
    os.replace(temporary, path)


def _cached(url: str, headers: dict[str, str], path: Path, max_age_hours: float) -> bytes:
    """A fresh copy from the network, or the last good copy if the network fails."""
    if path.is_file() and time.time() - path.stat().st_mtime < max_age_hours * 3600:
        return path.read_bytes()
    try:
        data = _get(url, headers, 60.0)
    except (OSError, ValueError) as error:
        if path.is_file():
            return path.read_bytes()
        host = urllib.parse.urlparse(url).netloc
        raise DownloadError(
            "SOURCE_UNREACHABLE",
            f"Could not reach {host}. Check your internet connection and try again.",
        ) from error
    _atomic_write(path, data)
    return data


def _fetch_symbol_changes(work_dir: Path) -> str:
    """NSE's symbol-change list as text: fresh from the network (kept 24 hours), or the last good copy if the network fails."""
    headers = {"User-Agent": _BROWSER_AGENT, "Referer": "https://www.nseindia.com/"}
    data = _cached(SYMBOL_CHANGES_URL, headers, work_dir / "nse-symbolchange.csv", 24)
    return data.decode("utf-8-sig")


def build_targets(work_dir: Path) -> TargetSet:
    """NIFTY 500 members (and the NIFTY BeES benchmark) with their Upstox instrument keys."""
    members_csv = _cached(
        NIFTY500_URL, {"User-Agent": _BROWSER_AGENT}, work_dir / "nifty500.csv", 168
    )
    master_gz = _cached(INSTRUMENTS_URL, {}, work_dir / "upstox-nse.json.gz", 24)
    try:
        master = json.loads(gzip.decompress(master_gz).decode("utf-8"))
        rows = list(csv.DictReader(io.StringIO(members_csv.decode("utf-8-sig"))))
    except (OSError, ValueError) as error:
        raise DownloadError(
            "SOURCE_UNREADABLE",
            "A list of stocks came back in a format QuantOS does not recognise.",
        ) from error

    by_isin: dict[str, Target] = {}
    benchmark: Target | None = None
    for item in master:
        if not isinstance(item, dict) or item.get("segment") != "NSE_EQ":
            continue
        symbol = str(item.get("trading_symbol") or "").upper()
        key = str(item.get("instrument_key") or "")
        isin = str(item.get("isin") or "")
        if not symbol or not key.startswith("NSE_EQ|") or not isin:
            continue
        target = Target(symbol, str(item.get("name") or symbol), isin, key)
        if item.get("instrument_type") == "EQ":
            by_isin.setdefault(isin, target)
        if symbol == BENCHMARK_SYMBOL:
            benchmark = target

    members: list[Target] = []
    skipped: list[str] = []
    for row in rows:
        symbol = (row.get("Symbol") or "").strip().upper()
        isin = (row.get("ISIN Code") or "").strip()
        found = by_isin.get(isin)
        if found is None:
            skipped.append(symbol or "?")
            continue
        members.append(Target(symbol, found.name, isin, found.instrument_key))
    if not members:
        raise DownloadError(
            "NO_STOCKS", "The NIFTY 500 list could not be matched to tradable stocks."
        )
    return TargetSet(tuple(members), benchmark, tuple(skipped))


def window(today: date) -> tuple[date, date]:
    """The ten-year baseline window."""
    return today - timedelta(days=HISTORY_DAYS), today


def refresh_window(today: date) -> tuple[date, date]:
    """The recent window an update re-reads."""
    return today - timedelta(days=REFRESH_DAYS), today


def cache_names(today: date) -> tuple[str, str]:
    """``(history cache, refresh cache)``.

    The ten-year baseline is a history cache. The recent window is a refresh cache, which is what
    makes the stocks NIFTY 500 members and lets a later update replace only the recent prices.
    """
    hist_start, end = window(today)
    ref_start, _ = refresh_window(today)
    return (
        f"all-market-{hist_start:%Y%m%d}-{end:%Y%m%d}",
        f"nifty500-refresh-{ref_start:%Y%m%d}-{end:%Y%m%d}",
    )


def _marked(market_cache: Path, prefix: str) -> list[Path]:
    """Caches this download created (they carry the marker), newest name first."""
    if not market_cache.is_dir():
        return []
    found = [
        child
        for child in market_cache.iterdir()
        if child.is_dir() and child.name.startswith(prefix) and (child / MARKER).is_file()
    ]
    return sorted(found, key=lambda path: path.name, reverse=True)


def baseline_exists(data_folder: Path) -> bool:
    """Whether a ten-year baseline made by this download or seeded is already on disk (so an update is enough)."""
    market_cache = data_folder / "evidence" / "market-cache"
    if not market_cache.is_dir():
        return False
    marked = [
        cache
        for cache in _marked(market_cache, "all-market-")
        if (cache / "store" / "datasets").is_dir()
    ]
    if marked:
        return True
    return any(
        (child / "store" / "datasets").is_dir()
        for child in market_cache.iterdir()
        if child.is_dir() and child.name.startswith("all-market-")
    )


def _fetch_actions(symbol: str, start: date, end: date) -> list[Any]:
    query = urllib.parse.urlencode(
        {
            "index": "equities",
            "symbol": symbol,
            "from_date": start.strftime("%d-%m-%Y"),
            "to_date": end.strftime("%d-%m-%Y"),
        }
    )
    headers = {
        "User-Agent": _BROWSER_AGENT,
        "Accept": "application/json, text/plain, */*",
        "Referer": NSE_ACTIONS_REFERER,
    }
    parsed = json.loads(_get(f"{NSE_ACTIONS_URL}?{query}", headers, 30.0).decode("utf-8"))
    if isinstance(parsed, list):
        return parsed
    if isinstance(parsed, dict) and isinstance(parsed.get("data"), list):
        return list(parsed["data"])
    raise ValueError("unrecognised corporate-action payload")


def _acquire(
    target: Target, start: date, end: date
) -> HistoricalAcquisition | HistoricalAcquisitionFailure:
    request = HistoricalDailyRequest(
        instrument_key=target.instrument_key,
        symbol=target.symbol,
        from_date=start,
        to_date=end,
        request_id=f"download-{target.symbol}-{end:%Y%m%d}"[:128],
    )
    # Uses the person's own Upstox token when one is saved; works without one.
    return UpstoxClient(allow_anonymous_history=True).acquire_historical_daily(request)


def _commit(store: EvidenceStore, acquisition: HistoricalAcquisition, operation_id: str) -> None:
    store.commit(draft_from_historical_acquisition(acquisition), operation_id=operation_id)


_QUALITY_TEXT = {
    "INVALID_OHLC": (
        "day where the high, low and close do not fit together",
        "days where the high, low and close do not fit together",
    ),
    "INVALID_VOLUME": (
        "day with an impossible trading volume",
        "days with an impossible trading volume",
    ),
    "INVALID_TIMESTAMP": ("day with an unreadable date", "days with unreadable dates"),
    "DUPLICATE_KEY": ("day listed twice", "days listed twice"),
    "REVERSE_ORDER": ("day out of order", "days out of order"),
    "NON_SESSION_DATE": (
        "price on a day the market was closed",
        "prices on days the market was closed",
    ),
    "OUT_OF_REQUEST_RANGE": ("day outside the dates asked for", "days outside the dates asked for"),
    "PROVIDER_RANGE_UNAVAILABLE": ("missing stretch of history", "missing stretches of history"),
}


def _reason(failure: HistoricalAcquisitionFailure) -> str:
    """Why a stock was left out, in words a person can read (and nothing was guessed or repaired)."""
    code = failure.code.value
    if code in _FAILURE_TEXT:
        return _FAILURE_TEXT[code]
    findings = []
    for finding in failure.quality_findings:
        one, many = _QUALITY_TEXT.get(
            finding.code.value, (finding.code.value.lower().replace("_", " "),) * 2
        )
        findings.append(f"{finding.count} {one if finding.count == 1 else many}")
    if findings:
        return (
            "its price history has "
            + " and ".join(findings)
            + ", and QuantOS does not guess around bad data"
        )
    return "its price history failed the data checks"


# ------------------------------------------------------------------------------------- job


class MarketDownload:
    """One background download. ``snapshot()`` is cheap, so the app can poll it."""

    def __init__(self, on_done: Callable[[Path], None] | None = None) -> None:
        self._lock = threading.Lock()
        self._cancel = threading.Event()
        self._thread: threading.Thread | None = None
        self._on_done = on_done
        self._reset()

    def _reset(self) -> None:
        self.state = "IDLE"  # IDLE | RUNNING | DONE | CANCELLED | ERROR
        self.message = ""
        self.total = 0
        self.done = 0
        self.saved = 0
        self.failures: list[dict[str, str]] = []
        self.failed = 0
        self.no_actions = 0
        self.cache = ""
        self.mode = ""
        self.started_at: str | None = None
        self.finished_at: str | None = None

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            return {
                "state": self.state,
                "message": self.message,
                "progress": (self.done / self.total) if self.total else 0.0,
                "total": self.total,
                "done": self.done,
                "saved": self.saved,
                "failed": self.failed,
                "failures": self.failures[:25],
                "without_actions": self.no_actions,
                "cache": self.cache,
                "mode": self.mode,
                "started_at": self.started_at,
                "finished_at": self.finished_at,
            }

    def cancel(self) -> None:
        self._cancel.set()

    def wait(self, timeout: float) -> bool:
        thread = self._thread
        if thread is not None:
            thread.join(timeout)
            return not thread.is_alive()
        return True

    def start(
        self,
        data_folder: Path,
        *,
        today: date | None = None,
        limit: int | None = None,
        mode: Literal["auto", "full", "update"] = "auto",
    ) -> bool:
        """Begin downloading into ``data_folder``. False if a download is already running.

        ``full`` reads ten years and then the recent window; ``update`` reads only the recent window
        and keeps the existing baseline; ``auto`` updates when a baseline exists and downloads in
        full otherwise.
        """
        with self._lock:
            if self.state == "RUNNING":
                return False
            self._reset()
            self.state = "RUNNING"
            self.message = "Getting the list of stocks..."
            self.started_at = datetime.now(UTC).isoformat(timespec="seconds")
            self._cancel.clear()
        day = today or datetime.now(UTC).astimezone().date()
        self._thread = threading.Thread(
            target=self._run,
            args=(data_folder, day, limit, mode),
            name="QuantOS-Download",
            daemon=True,
        )
        self._thread.start()
        return True

    def _set(self, **changes: Any) -> None:
        with self._lock:
            for name, value in changes.items():
                setattr(self, name, value)

    def _run(
        self,
        data_folder: Path,
        today: date,
        limit: int | None,
        mode: Literal["auto", "full", "update"],
    ) -> None:
        try:
            self._download(data_folder, today, limit, mode)
        except DownloadError as error:
            self._set(state="ERROR", message=error.message)
        except Exception as error:  # a worker must always end in a state the page can show
            logger.exception("Market download failed")
            self._set(state="ERROR", message=f"The download stopped unexpectedly: {error}")
        finally:
            self._set(finished_at=datetime.now(UTC).isoformat(timespec="seconds"))

    def _download(
        self,
        data_folder: Path,
        today: date,
        limit: int | None,
        mode: Literal["auto", "full", "update"],
    ) -> None:
        data_folder.mkdir(parents=True, exist_ok=True)
        if shutil.disk_usage(data_folder).free < MIN_FREE_BYTES:
            raise DownloadError(
                "NOT_ENOUGH_SPACE", "There is not enough free disk space (about 1.3 GB needed)."
            )
        targets = build_targets(data_folder / "downloads")
        members = list(targets.members[:limit] if limit else targets.members)
        everyone = [*members, *([targets.benchmark] if targets.benchmark else [])]
        market_cache = data_folder / "evidence" / "market-cache"
        history_name, refresh_name = cache_names(today)
        baseline = _marked(market_cache, "all-market-")
        if not baseline and market_cache.is_dir():
            seeded = [
                c
                for c in market_cache.iterdir()
                if c.is_dir()
                and c.name.startswith("all-market-")
                and (c / "store" / "datasets").is_dir()
            ]
            if seeded:
                baseline = sorted(seeded, key=lambda path: path.name, reverse=True)
                marker = baseline[0] / MARKER
                if not marker.exists():
                    marker.write_text(
                        json.dumps({"kind": "HISTORY", "created": datetime.now(UTC).isoformat()}),
                        encoding="utf-8",
                    )
        # Same-day re-run of a full download is a resume (finish what is missing); a baseline from an
        # earlier day only needs the recent window refreshed.
        newer_baseline = bool(baseline) and baseline[0].name != history_name
        updating = baseline_exists(data_folder) and (
            mode == "update" or (mode == "auto" and newer_baseline)
        )
        if updating and baseline:
            history_name = baseline[0].name  # keep the baseline that is already there
        hist_start, end = window(today)
        ref_start, _ = refresh_window(today)

        # History first, so a stopped run keeps the longest data.
        jobs: list[tuple[Target, str, str, date, date]] = []
        if not updating:
            jobs += [(t, history_name, "HISTORY", hist_start, end) for t in everyone]
        jobs += [(t, refresh_name, "REFRESH", ref_start, end) for t in everyone]

        stores: dict[str, EvidenceStore] = {}
        have: dict[str, set[str]] = {}
        for name, kind in sorted({(j[1], j[2]) for j in jobs}):
            cache_dir = market_cache / name
            root = cache_dir / "store"
            root.mkdir(parents=True, exist_ok=True)
            marker = cache_dir / MARKER
            if not marker.exists():
                marker.write_text(
                    json.dumps({"kind": kind, "created": datetime.now(UTC).isoformat()}),
                    encoding="utf-8",
                )
            stores[name] = EvidenceStore(EvidenceStoreConfig(root=root))
            role: Literal["HISTORY", "REFRESH"] = "HISTORY" if kind == "HISTORY" else "REFRESH"
            have[name] = (
                {ref.symbol for ref in scan_datasets(CacheRef(name, role, root))}
                if (root / "datasets").is_dir()
                else set()
            )

        pending = [j for j in jobs if j[0].symbol not in have[j[1]]]
        self._set(
            total=len(jobs),
            done=len(jobs) - len(pending),
            saved=len(jobs) - len(pending),
            cache=refresh_name,
            mode="update" if updating else "full",
            message=(
                f"Updating recent prices for {len(everyone)} stocks..."
                if updating
                else f"Downloading ten years of prices for {len(everyone)} stocks..."
            ),
        )

        commit_lock = threading.Lock()
        actions_gate = threading.Semaphore(3)
        actions_dir = data_folder / "authorities"
        generated_path = actions_dir / GENERATED_ACTIONS
        generated = (
            set(generated_path.read_text(encoding="utf-8").split())
            if generated_path.is_file()
            else set()
        )

        def save(job: tuple[Target, str, str, date, date]) -> None:
            target, cache, kind, job_start, job_end = job
            if self._cancel.is_set():
                return
            outcome = _acquire(target, job_start, job_end)
            if isinstance(outcome, HistoricalAcquisitionFailure):
                self._record_failure(target.symbol, _reason(outcome))
                return
            try:
                with commit_lock:
                    _commit(
                        stores[cache],
                        outcome,
                        f"download-{kind.lower()}-{target.symbol}-{job_end:%Y%m%d}",
                    )
            except Exception as error:
                logger.warning("Could not save %s: %s", target.symbol, error)
                self._record_failure(target.symbol, "it could not be saved safely")
                return
            if kind == "REFRESH":  # corporate actions come with the newest pass only
                with actions_gate:
                    try:
                        records = _fetch_actions(target.symbol, hist_start, end)
                        path = actions_dir / f"nse-corporate-actions-{target.symbol}.json"
                        with self._lock:
                            writable = not path.exists() or target.symbol in generated
                        if writable:
                            skip_write = False
                            if not records and path.is_file():
                                try:
                                    existing = json.loads(path.read_text(encoding="utf-8"))
                                    if isinstance(existing, list) and len(existing) > 0:
                                        skip_write = True
                                except Exception:
                                    skip_write = False
                            if skip_write:
                                logger.warning(
                                    "Corporate actions fetch for %s returned empty list but non-empty file exists; keeping earlier file",
                                    target.symbol,
                                )
                            else:
                                _atomic_write(
                                    path, json.dumps(records, separators=(",", ":")).encode("utf-8")
                                )
                                with self._lock:
                                    generated.add(target.symbol)
                    except (OSError, ValueError):
                        with self._lock:
                            self.no_actions += 1
            with self._lock:
                self.saved += 1
                self.done += 1

        def one(job: tuple[Target, str, str, date, date]) -> None:
            try:
                save(job)
            except Exception as error:  # one stock must never stop the others
                logger.warning("Could not download %s: %s", job[0].symbol, error)
                self._record_failure(job[0].symbol, "something unexpected went wrong")

        with ThreadPoolExecutor(max_workers=WORKERS, thread_name_prefix="QuantOS-dl") as pool:
            list(pool.map(one, pending))

        if self._cancel.is_set():
            self._set(
                state="CANCELLED",
                message=(
                    f"Stopped after {self.saved} downloads. "
                    "Start again to continue where it left off."
                ),
            )
            return
        if self.saved == 0:
            first = self.failures[0]["reason"] if self.failures else "no data came back"
            raise DownloadError("NOTHING_SAVED", f"No stocks could be downloaded: {first}.")

        actions_dir.mkdir(parents=True, exist_ok=True)
        _atomic_write(generated_path, "\n".join(sorted(generated)).encode("utf-8"))
        write_listings(actions_dir, members, targets.benchmark)
        write_symbol_changes(actions_dir, data_folder / "downloads")
        write_liquid_universe(actions_dir, market_cache / history_name / "store", history_name, end)
        _prune(market_cache, keep={history_name, refresh_name})
        verb = "Updated" if updating else "Downloaded"
        saved_stocks = len(everyone) - len({f["symbol"] for f in self.failures})
        self._set(state="DONE", message=f"{verb} {saved_stocks} stocks up to {end:%d %b %Y}.")
        if self._on_done is not None:
            self._on_done(data_folder)

    def _record_failure(self, symbol: str, reason: str) -> None:
        with self._lock:
            self.done += 1
            if all(f["symbol"] != symbol for f in self.failures):  # a stock counts once
                self.failed += 1
                self.failures.append({"symbol": symbol, "reason": reason})


def _prune(market_cache: Path, keep: set[str]) -> None:
    """Remove caches this download made that a newer run has superseded. Nothing else is touched."""
    for prefix in ("all-market-", "nifty500-refresh-"):
        for old in _marked(market_cache, prefix):
            if old.name not in keep:
                shutil.rmtree(old, ignore_errors=True)


# ------------------------------------------------------------------ reference files


def write_listings(authorities: Path, members: list[Target], benchmark: Target | None) -> None:
    """The company-name list the app shows. Never replaces a list that is already there."""
    path = authorities / LISTINGS_FILE
    if path.exists():
        return
    buffer = io.StringIO()
    writer = csv.writer(buffer, lineterminator="\n")
    writer.writerow(
        [
            "Symbol",
            "Company Name",
            "ISIN Code",
            "Instrument Key",
            "Instrument Type",
            "Security Type",
            "Lot Size",
            "Tick Size",
        ]
    )
    for target in [*members, *([benchmark] if benchmark else [])]:
        writer.writerow(
            [
                target.symbol,
                target.name,
                target.isin,
                target.instrument_key,
                "EQ",
                "NORMAL",
                1,
                "0.05",
            ]
        )
    _atomic_write(path, buffer.getvalue().encode("utf-8"))


def write_symbol_changes(authorities: Path, work_dir: Path) -> int:
    """Keep authorities/nse-symbol-changes.csv current. Returns how many changes the file holds afterwards. Never raises."""
    path = authorities / SYMBOL_CHANGES_FILE
    try:
        try:
            text = _fetch_symbol_changes(work_dir)
            changes = parse_symbol_changes(text)
            if len(changes) < MIN_SYMBOL_CHANGES:
                logger.warning(
                    "NSE symbol changes returned only %d records (expected at least %d); keeping existing file",
                    len(changes),
                    MIN_SYMBOL_CHANGES,
                )
            else:
                _atomic_write(path, text.encode("utf-8"))
        except (DownloadError, OSError, ValueError) as error:
            logger.warning("Could not fetch NSE symbol changes: %s", error)

        if path.is_file():
            content = path.read_text(encoding="utf-8-sig", errors="replace")
            return len(parse_symbol_changes(content))
    except Exception as error:
        logger.warning("Could not read symbol changes file %s: %s", path, error)
        return 0
    return 0


def write_liquid_universe(authorities: Path, store: Path, cache: str, end: date) -> int:
    """Stocks with ~10 years of history and real liquidity, computed from what was just downloaded.

    Replaces only a file this download wrote earlier; a list from anywhere else is left alone.
    """
    path = authorities / LIQUID_FILE
    if path.exists() and not path.read_text(encoding="utf-8", errors="replace").startswith(
        GENERATED_MARK
    ):
        return 0
    rows: list[tuple[str, str, str, float, float]] = []
    for ref in scan_datasets(CacheRef(cache, "HISTORY", store)):
        bars = read_bars(ref)
        if len(bars) < 250:
            continue
        years = (date.fromisoformat(bars[-1].d) - date.fromisoformat(bars[0].d)).days / 365.25
        turnover = statistics.median(bar.c * bar.v for bar in bars[-750:])
        if years >= LIQUID_MIN_YEARS and turnover >= LIQUID_MIN_TURNOVER:
            rows.append(
                (ref.symbol, ref.instrument_key.split("|")[-1], ref.instrument_key, years, turnover)
            )
    buffer = io.StringIO()
    buffer.write(
        f"{GENERATED_MARK} NIFTY 500 stocks with at least {LIQUID_MIN_YEARS} years of history and a\n"
        f"# median daily turnover of Rs 5 crore or more over the last three years, computed {end:%Y-%m-%d}.\n"
        "# SURVIVORSHIP BIAS: only stocks listed today are included, so companies that failed or were\n"
        "# delisted inside the window are absent. Read a positive result as weak evidence.\n"
    )
    writer = csv.writer(buffer, lineterminator="\n")
    writer.writerow(
        ["Symbol", "ISIN Code", "InstrumentKey", "YearsActive", "MedianDailyTurnoverINR"]
    )
    for symbol, isin, key, years, turnover in sorted(rows):
        writer.writerow([symbol, isin, key, f"{years:.2f}", int(turnover)])
    _atomic_write(path, buffer.getvalue().encode("utf-8"))
    return len(rows)
