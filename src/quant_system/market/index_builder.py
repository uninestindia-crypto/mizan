"""Build the derived SQLite market index from the evidence store.

The evidence store is only read. Each build writes a new ``market-index-<id>.sqlite`` and then
atomically repoints ``CURRENT`` at it, so readers never see a half-built index and Windows never has
to replace a file another thread holds open.

Stitching rule (ADR-0001, decision 4): per symbol, the ten-year HISTORY dataset and the newest
REFRESH vintage are joined only when every overlapping session agrees within
:data:`STITCH_TOLERANCE` on open and close. Both come from the same provider, but a later vintage is
re-adjusted after a split or bonus, so a disagreement means the older history is on a different
price basis. Then the refresh alone is used and the reason is stored; history is never rescaled
from a price gap.
"""

from __future__ import annotations

import math
import os
import sqlite3
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, date, datetime
from pathlib import Path

import numpy as np

from quant_system.market import metrics
from quant_system.market.reference import (
    CorporateAction,
    Listing,
    corporate_action_file,
    load_corporate_actions,
    load_liquid_universe,
    load_listings,
    load_symbol_history,
)
from quant_system.market.sources import (
    CacheRef,
    DatasetRef,
    RawBar,
    ReadStats,
    discover_caches,
    newest_per_symbol,
    read_bars,
    scan_datasets,
    store_fingerprint,
)
from quant_system.market.symbol_changes import SymbolHistory

SCHEMA_VERSION = "2"
STITCH_TOLERANCE = 0.001
POINTER_FILE = "CURRENT"
INDEX_PREFIX = "market-index-"

ProgressFn = Callable[[float, str], None]

_SCHEMA = """
CREATE TABLE meta(key TEXT PRIMARY KEY, value TEXT NOT NULL);
CREATE TABLE symbols(
    symbol TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    isin TEXT NOT NULL,
    instrument_key TEXT NOT NULL,
    series TEXT NOT NULL,
    security_type TEXT NOT NULL,
    is_etf INTEGER NOT NULL,
    first_date TEXT NOT NULL,
    last_date TEXT NOT NULL,
    sessions INTEGER NOT NULL,
    stitch TEXT NOT NULL,
    stitch_note TEXT NOT NULL
);
CREATE TABLE bars(
    symbol TEXT NOT NULL,
    d TEXT NOT NULL,
    o REAL NOT NULL,
    h REAL NOT NULL,
    l REAL NOT NULL,
    c REAL NOT NULL,
    v INTEGER NOT NULL,
    PRIMARY KEY(symbol, d)
) WITHOUT ROWID;
CREATE TABLE sources(
    symbol TEXT NOT NULL,
    role TEXT NOT NULL,
    cache TEXT NOT NULL,
    dataset_id TEXT NOT NULL,
    manifest_hash TEXT NOT NULL,
    acquired_at TEXT NOT NULL,
    first_date TEXT NOT NULL,
    last_date TEXT NOT NULL,
    rows_used INTEGER NOT NULL
);
CREATE TABLE universes(
    universe TEXT NOT NULL,
    symbol TEXT NOT NULL,
    PRIMARY KEY(universe, symbol)
) WITHOUT ROWID;
CREATE TABLE snapshot(
    symbol TEXT PRIMARY KEY,
    asof TEXT NOT NULL,
    close REAL NOT NULL,
    prev_close REAL,
    chg_1d REAL,
    ret_1m REAL,
    ret_6m REAL,
    ret_1y REAL,
    vol_1y REAL,
    high_52w REAL,
    low_52w REAL,
    from_52w_high REAL,
    sma_50 REAL,
    sma_200 REAL,
    turnover_cr REAL
);
CREATE TABLE actions(
    symbol TEXT NOT NULL,
    ex_date TEXT NOT NULL,
    subject TEXT NOT NULL,
    kinds TEXT NOT NULL,
    breaks_history INTEGER NOT NULL
);
CREATE INDEX actions_by_symbol ON actions(symbol, ex_date);
CREATE TABLE flags(
    symbol TEXT NOT NULL,
    d TEXT NOT NULL,
    kind TEXT NOT NULL,
    change REAL NOT NULL,
    note TEXT NOT NULL
);
CREATE INDEX flags_by_symbol ON flags(symbol, d);
CREATE TABLE aliases(
    alias TEXT NOT NULL,
    symbol TEXT NOT NULL,
    kind TEXT NOT NULL,
    PRIMARY KEY(alias, symbol)
) WITHOUT ROWID;
"""

# An overnight gap this large, not explained by a recorded demerger or rights issue, is treated as
# a data break: most often a bonus or split that neither NSE's record nor the provider reflects
# (SPLPETRO fell 49.1% overnight on 2022-06-07 with no recorded action). Genuine news gaps beyond
# these bounds are rare; flagging one costs a refused single-stock test, never a silent error.
GAP_DOWN = -0.40
GAP_UP = 0.80
EXPLAIN_WINDOW_DAYS = 7


@dataclass(frozen=True, slots=True)
class GapFlag:
    symbol: str
    d: str
    kind: str
    change: float
    note: str


def detect_gap_flags(
    symbol: str, bars: list[RawBar], actions: list[CorporateAction]
) -> list[GapFlag]:
    """Overnight gaps beyond the bounds that no recorded demerger or rights issue explains."""
    flags: list[GapFlag] = []
    action_dates = [(date_from_iso(a.ex_date), a) for a in actions]
    for prev, cur in zip(bars, bars[1:], strict=False):
        change = cur.o / prev.c - 1.0
        if GAP_DOWN < change < GAP_UP:
            continue
        day = date_from_iso(cur.d)
        nearby = [a for d, a in action_dates if abs((d - day).days) <= EXPLAIN_WINDOW_DAYS]
        if any(a.breaks_history for a in nearby):
            continue
        structural = [a for a in nearby if {"split", "bonus"} & set(a.kinds)]
        if structural:
            kind = "UNADJUSTED_ACTION"
            note = (
                f"{change:+.0%} overnight at '{structural[0].subject}'; the price history was not "
                "adjusted for it."
            )
        else:
            kind = "UNEXPLAINED_GAP"
            note = (
                f"{change:+.0%} overnight with no recorded corporate action; possibly an "
                "unrecorded bonus, split or demerger."
            )
        flags.append(GapFlag(symbol, cur.d, kind, change, note))
    return flags


def date_from_iso(text: str) -> date:
    return date.fromisoformat(text[:10])


class IndexBuildError(RuntimeError):
    """The data folder holds nothing an index can be built from."""


@dataclass(slots=True)
class BuildReport:
    index_path: Path
    built_at: str
    fingerprint: str
    symbols: int = 0
    bars: int = 0
    latest_session: str = ""
    duration_seconds: float = 0.0
    stitch_counts: dict[str, int] = field(default_factory=dict)
    invalid_rows: int = 0
    duplicate_rows: int = 0
    flags: int = 0
    renames_merged: int = 0
    aliases: int = 0


@dataclass(frozen=True, slots=True)
class Stitched:
    bars: list[RawBar]
    status: str
    note: str
    used: dict[str, tuple[int, str, str]]


def stitch(history: list[RawBar] | None, refresh: list[RawBar] | None) -> Stitched:
    """Join one symbol's HISTORY and REFRESH bars under the rule in the module docstring."""
    if history and not refresh:
        return Stitched(history, "HISTORY_ONLY", "", {"HISTORY": _span(history)})
    if refresh and not history:
        # One long download (ten years) is the whole history, not a "recent refresh"; only a short
        # window deserves the warning.
        try:
            years = (date_from_iso(refresh[-1].d) - date_from_iso(refresh[0].d)).days / 365.25
        except ValueError:
            years = 0.0
        return Stitched(
            refresh,
            "REFRESH_ONLY",
            "" if years >= 8 else "Only the recent refresh exists for this symbol.",
            {"REFRESH": _span(refresh)},
        )
    if not history or not refresh:
        return Stitched([], "EMPTY", "No valid bars.", {})
    if refresh[-1].d < history[-1].d:
        return Stitched(
            history,
            "HISTORY_ONLY",
            "The refresh is older than the history dataset, so it was not used.",
            {"HISTORY": _span(history)},
        )
    by_date = {bar.d: bar for bar in refresh}
    worst = 0.0
    worst_date = ""
    overlap = 0
    for h in history:
        r = by_date.get(h.d)
        if r is None:
            continue
        overlap += 1
        diff = max(abs(r.c - h.c) / h.c, abs(r.o - h.o) / h.o)
        if diff > worst:
            worst, worst_date = diff, h.d
    if overlap == 0:
        return Stitched(
            refresh,
            "REFRESH_ONLY",
            "History and refresh do not overlap, so they cannot be checked against each other.",
            {"REFRESH": _span(refresh)},
        )
    if worst <= STITCH_TOLERANCE:
        head = [bar for bar in history if bar.d < refresh[0].d]
        used = {"REFRESH": _span(refresh)}
        if head:
            used["HISTORY"] = _span(head)
        return Stitched(head + refresh, "STITCHED", "", used)
    return Stitched(
        refresh,
        "REFRESH_ONLY_READJUSTED",
        (
            f"The provider re-adjusted this symbol's prices (up to {worst:.1%} on {worst_date}), "
            f"so older history is on a different price basis. Only the {len(refresh)}-session "
            "refresh is used."
        ),
        {"REFRESH": _span(refresh)},
    )


def _span(bars: list[RawBar]) -> tuple[int, str, str]:
    return (len(bars), bars[0].d, bars[-1].d)


def merge_renames(
    history: dict[str, DatasetRef],
    refresh: dict[str, DatasetRef],
    names: SymbolHistory | None,
) -> tuple[dict[str, DatasetRef], dict[str, DatasetRef], dict[str, tuple[str, ...]]]:
    """Join history and refresh across symbol renames under the current label."""
    out_history = dict(history)
    out_refresh = dict(refresh)
    merged: dict[str, tuple[str, ...]] = {}
    if names is None:
        return out_history, out_refresh, merged

    for n in sorted(out_refresh):
        if n in out_history:
            continue
        for p in names.predecessors(n):
            if p in out_history and p not in out_refresh:
                out_history[n] = out_history.pop(p)
                merged[n] = (p,)
                break
    return out_history, out_refresh, merged


def build_market_index(
    data_folder: Path,
    index_dir: Path,
    progress: ProgressFn | None = None,
) -> BuildReport:
    """Build a new index from ``data_folder`` and make it current. Returns what was built."""
    started = time.perf_counter()
    report_progress = progress or (lambda _fraction, _message: None)
    market_cache = data_folder / "evidence" / "market-cache"
    caches = discover_caches(market_cache)
    if not caches:
        raise IndexBuildError(f"No market data caches were found under {market_cache}.")

    report_progress(0.0, "Reading dataset manifests")
    history = newest_per_symbol(
        ref for cache in caches if cache.role == "HISTORY" for ref in scan_datasets(cache)
    )
    refresh = newest_per_symbol(
        ref for cache in caches if cache.role == "REFRESH" for ref in scan_datasets(cache)
    )
    names = load_symbol_history(data_folder)
    history, refresh, merged = merge_renames(history, refresh, names)
    symbols = sorted(set(history) | set(refresh))
    if not symbols:
        raise IndexBuildError(f"The caches under {market_cache} hold no committed daily datasets.")

    listings = load_listings(data_folder)
    liquid = set(load_liquid_universe(data_folder))
    history_caches = [cache.name for cache in caches if cache.role == "HISTORY"]

    index_dir.mkdir(parents=True, exist_ok=True)
    built_at = datetime.now(UTC)
    build_id = built_at.strftime("%Y%m%dT%H%M%S%fZ")
    final_path = index_dir / f"{INDEX_PREFIX}{build_id}.sqlite"
    partial_path = final_path.with_suffix(".partial")
    report = BuildReport(
        index_path=final_path,
        built_at=built_at.isoformat(timespec="seconds"),
        fingerprint=store_fingerprint(caches),
    )

    conn = sqlite3.connect(partial_path)
    try:
        conn.execute("PRAGMA journal_mode=OFF")
        conn.execute("PRAGMA synchronous=OFF")
        conn.executescript(_SCHEMA)
        stats = ReadStats()
        for position, symbol in enumerate(symbols):
            if position % 25 == 0:
                report_progress(0.02 + 0.96 * position / len(symbols), f"Indexing {symbol}")
            former = merged.get(symbol, ())
            actions = _index_actions(conn, data_folder, symbol, history_caches, former=former)
            flags = _index_symbol(
                conn,
                symbol,
                history.get(symbol),
                refresh.get(symbol),
                listings.get(symbol),
                liquid,
                actions,
                stats,
                report,
                former=former,
            )
            report.flags += len(flags)
            conn.executemany(
                "INSERT INTO flags VALUES (?,?,?,?,?)",
                ((f.symbol, f.d, f.kind, f.change, f.note) for f in flags),
            )
        report.renames_merged = len(merged)
        if names is not None:
            indexed_symbols = {
                str(r[0]) for r in conn.execute("SELECT symbol FROM symbols").fetchall()
            }
            alias_rows: list[tuple[str, str, str]] = []
            seen_pairs: set[tuple[str, str]] = set()
            for x in sorted(indexed_symbols):
                for a in names.predecessors(x):
                    if a not in indexed_symbols and (a, x) not in seen_pairs:
                        seen_pairs.add((a, x))
                        alias_rows.append((a, x, "FORMER"))
                for a in names.successors(x):
                    if a not in indexed_symbols and (a, x) not in seen_pairs:
                        seen_pairs.add((a, x))
                        alias_rows.append((a, x, "NEW"))
            conn.executemany("INSERT INTO aliases VALUES (?,?,?)", alias_rows)
            report.aliases = len(alias_rows)
        report.invalid_rows = stats.invalid
        report.duplicate_rows = stats.duplicate_dates
        latest = conn.execute("SELECT MAX(last_date) FROM symbols").fetchone()[0]
        report.latest_session = str(latest or "")
        report.duration_seconds = round(time.perf_counter() - started, 2)
        _write_meta(conn, report, caches, data_folder)
        conn.commit()
    finally:
        conn.close()

    os.replace(partial_path, final_path)
    _point_current(index_dir, final_path.name)
    _remove_old_indexes(index_dir, keep=final_path.name)
    report_progress(1.0, "Market index ready")
    return report


def _index_symbol(
    conn: sqlite3.Connection,
    symbol: str,
    history_ref: DatasetRef | None,
    refresh_ref: DatasetRef | None,
    listing: Listing | None,
    liquid: set[str],
    actions: list[CorporateAction],
    stats: ReadStats,
    report: BuildReport,
    former: tuple[str, ...] = (),
) -> list[GapFlag]:
    """Index one symbol. Bars before its last data break are dropped; returns the breaks found."""
    history = read_bars(history_ref, stats) if history_ref else None
    refresh = read_bars(refresh_ref, stats) if refresh_ref else None
    result = stitch(history, refresh)
    if not result.bars:
        report.stitch_counts["EMPTY"] = report.stitch_counts.get("EMPTY", 0) + 1
        return []
    report.stitch_counts[result.status] = report.stitch_counts.get(result.status, 0) + 1
    flags = detect_gap_flags(symbol, result.bars, actions)
    bars = result.bars
    note = result.note
    if former:
        former_str = ", ".join(former)
        sentence = f"History continues from the former symbol(s) {former_str}."
        note = " ".join(part for part in (note, sentence) if part)
    if flags:
        last_break = flags[-1]
        bars = [bar for bar in result.bars if bar.d >= last_break.d]
        dropped = len(result.bars) - len(bars)
        note = " ".join(
            part
            for part in (
                note,
                (
                    f"Prices before {last_break.d} ({dropped} sessions) are not used: "
                    f"{last_break.note} They do not match today's shares."
                ),
            )
            if part
        )
    report.symbols += 1
    report.bars += len(bars)

    conn.executemany(
        "INSERT INTO bars VALUES (?,?,?,?,?,?,?)",
        ((symbol, b.d, b.o, b.h, b.low, b.c, b.v) for b in bars),
    )
    source_ref = refresh_ref or history_ref
    instrument_key = (listing.instrument_key if listing else "") or (
        source_ref.instrument_key if source_ref else ""
    )
    conn.execute(
        "INSERT INTO symbols VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
        (
            symbol,
            listing.name if listing else symbol,
            listing.isin if listing else "",
            instrument_key,
            listing.series if listing else "",
            listing.security_type if listing else "",
            int(listing.is_etf) if listing else int(instrument_key.startswith("NSE_EQ|INF")),
            bars[0].d,
            bars[-1].d,
            len(bars),
            result.status,
            note,
        ),
    )
    for role, (rows, first, last) in result.used.items():
        ref = history_ref if role == "HISTORY" else refresh_ref
        if ref is None or last < bars[0].d:
            continue
        if first < bars[0].d:
            rows = sum(1 for bar in bars if first <= bar.d <= last)
            first = bars[0].d
        conn.execute(
            "INSERT INTO sources VALUES (?,?,?,?,?,?,?,?,?)",
            (
                symbol,
                role,
                ref.cache,
                ref.dataset_id,
                ref.manifest_hash,
                ref.acquired_at,
                first,
                last,
                rows,
            ),
        )
    conn.execute("INSERT INTO universes VALUES ('all', ?)", (symbol,))
    if refresh_ref is not None:
        conn.execute("INSERT INTO universes VALUES ('nifty500', ?)", (symbol,))
    if symbol in liquid:
        conn.execute("INSERT INTO universes VALUES ('liquid', ?)", (symbol,))
    _insert_snapshot(conn, symbol, bars)
    return flags


def _insert_snapshot(conn: sqlite3.Connection, symbol: str, bars: list[RawBar]) -> None:
    close = np.fromiter((b.c for b in bars), dtype=np.float64, count=len(bars))
    high = np.fromiter((b.h for b in bars), dtype=np.float64, count=len(bars))
    low = np.fromiter((b.low for b in bars), dtype=np.float64, count=len(bars))
    volume = np.fromiter((float(b.v) for b in bars), dtype=np.float64, count=len(bars))
    window = metrics.SESSIONS_1Y
    high_52w = float(high[-window:].max())
    low_52w = float(low[-window:].min())
    prev_close = float(close[-2]) if close.size >= 2 else None
    sma_50 = metrics.rolling_mean(close, 50)[-1]
    sma_200 = metrics.rolling_mean(close, 200)[-1]
    conn.execute(
        "INSERT INTO snapshot VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
        (
            symbol,
            bars[-1].d,
            float(close[-1]),
            prev_close,
            (float(close[-1]) / prev_close - 1.0) if prev_close else None,
            metrics.period_return(close, metrics.SESSIONS_1M),
            metrics.period_return(close, metrics.SESSIONS_6M),
            metrics.period_return(close, metrics.SESSIONS_1Y),
            metrics.annualized_volatility(close),
            high_52w,
            low_52w,
            float(close[-1]) / high_52w - 1.0 if high_52w > 0 else None,
            None if math.isnan(sma_50) else float(sma_50),
            None if math.isnan(sma_200) else float(sma_200),
            metrics.median_turnover_crore(close, volume),
        ),
    )


def _index_actions(
    conn: sqlite3.Connection,
    data_folder: Path,
    symbol: str,
    cache_names: list[str],
    former: tuple[str, ...] = (),
) -> list[CorporateAction]:
    all_actions: list[CorporateAction] = []
    labels = (symbol, *former)
    for lbl in labels:
        path = corporate_action_file(data_folder, lbl, cache_names)
        if path is not None:
            all_actions.extend(load_corporate_actions(path, symbol))

    seen: set[tuple[str, str]] = set()
    actions: list[CorporateAction] = []
    for a in all_actions:
        key = (a.ex_date, a.subject)
        if key not in seen:
            seen.add(key)
            actions.append(a)

    actions.sort(key=lambda a: a.ex_date)
    conn.executemany(
        "INSERT INTO actions VALUES (?,?,?,?,?)",
        (
            (a.symbol, a.ex_date, a.subject, ",".join(a.kinds), int(a.breaks_history))
            for a in actions
        ),
    )
    return actions


def _write_meta(
    conn: sqlite3.Connection, report: BuildReport, caches: list[CacheRef], data_folder: Path
) -> None:
    rows = {
        "schema_version": SCHEMA_VERSION,
        "built_at": report.built_at,
        "fingerprint": report.fingerprint,
        "data_folder": str(data_folder.resolve()),
        "latest_session": report.latest_session,
        "symbols": str(report.symbols),
        "bars": str(report.bars),
        "caches": ",".join(cache.name for cache in caches),
        "stitch_counts": ",".join(f"{k}={v}" for k, v in sorted(report.stitch_counts.items())),
        "invalid_rows": str(report.invalid_rows),
        "flags": str(report.flags),
        "duration_seconds": str(report.duration_seconds),
        "renames_merged": str(report.renames_merged),
        "aliases": str(report.aliases),
    }
    conn.executemany("INSERT INTO meta VALUES (?,?)", rows.items())


def _point_current(index_dir: Path, file_name: str) -> None:
    pointer = index_dir / POINTER_FILE
    temp = index_dir / f"{POINTER_FILE}.tmp"
    temp.write_text(file_name, encoding="utf-8")
    for attempt in range(20):
        try:
            os.replace(temp, pointer)
            return
        except PermissionError:
            if attempt == 19:
                raise
            time.sleep(0.05)


def _remove_old_indexes(index_dir: Path, keep: str) -> None:
    """Best effort: an index still open by a reader stays until the next build."""
    for path in index_dir.glob(f"{INDEX_PREFIX}*"):
        if path.name == keep:
            continue
        try:
            path.unlink()
        except OSError:
            continue
