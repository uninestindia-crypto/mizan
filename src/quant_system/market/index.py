"""Read-only access to the current market index."""

from __future__ import annotations

import sqlite3
from collections.abc import Iterator, Sequence
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np

from quant_system.market import metrics
from quant_system.market.index_builder import POINTER_FILE, SCHEMA_VERSION

BENCHMARK_SYMBOL = "NIFTYBEES"
UNIVERSES = ("liquid", "nifty500", "all")


class IndexNotReadyError(RuntimeError):
    """No usable market index exists yet."""


class SymbolNotFoundError(LookupError):
    """The symbol is not in the market index."""


@dataclass(frozen=True, slots=True)
class BarSeries:
    symbol: str
    dates: list[str]
    open: np.ndarray
    high: np.ndarray
    low: np.ndarray
    close: np.ndarray
    volume: np.ndarray

    def __len__(self) -> int:
        return len(self.dates)


class MarketIndex:
    """Queries against ``<index_dir>/CURRENT``. Every call opens its own read-only connection."""

    def __init__(self, index_dir: Path) -> None:
        self.index_dir = index_dir

    # ----------------------------------------------------------------------------- status

    def current_path(self) -> Path | None:
        pointer = self.index_dir / POINTER_FILE
        try:
            name = pointer.read_text(encoding="utf-8").strip()
        except OSError:
            return None
        path = self.index_dir / name
        return path if name and path.is_file() else None

    def is_ready(self) -> bool:
        path = self.current_path()
        if path is None:
            return False
        try:
            return self.meta().get("schema_version") == SCHEMA_VERSION
        except (sqlite3.Error, IndexNotReadyError):
            return False

    @contextmanager
    def _connect(self) -> Iterator[sqlite3.Connection]:
        path = self.current_path()
        if path is None:
            raise IndexNotReadyError("The market index has not been built yet.")
        conn = sqlite3.connect(f"{path.as_uri()}?mode=ro", uri=True, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
        finally:
            conn.close()

    def meta(self) -> dict[str, str]:
        with self._connect() as conn:
            return {
                str(r["key"]): str(r["value"]) for r in conn.execute("SELECT key, value FROM meta")
            }

    def resolve(self, symbol: str) -> str:
        sym = symbol.strip().upper()
        if not sym:
            return ""
        try:
            with self._connect() as conn:
                if (
                    conn.execute("SELECT 1 FROM symbols WHERE symbol = ?", (sym,)).fetchone()
                    is not None
                ):
                    return sym
                rows = conn.execute(
                    "SELECT symbol, kind FROM aliases WHERE alias = ?", (sym,)
                ).fetchall()
                if rows:
                    best = sorted(
                        rows,
                        key=lambda r: (0 if str(r["kind"]) == "FORMER" else 1, str(r["symbol"])),
                    )[0]
                    return str(best["symbol"])
                return sym
        except sqlite3.OperationalError:
            return sym

    def search(self, query: str, limit: int = 20) -> list[dict[str, Any]]:
        text = query.strip().upper()
        if not text:
            return []
        like = f"%{text}%"
        sql_direct = """
            SELECT symbol, name, is_etf, last_date FROM symbols
            WHERE symbol LIKE ? OR UPPER(name) LIKE ?
        """
        sql_alias = """
            SELECT y.symbol, y.name, y.is_etf, y.last_date, a.alias
            FROM aliases a
            JOIN symbols y ON y.symbol = a.symbol
            WHERE a.alias LIKE ?
        """
        with self._connect() as conn:
            direct_rows = conn.execute(sql_direct, (like, like)).fetchall()
            try:
                alias_rows = conn.execute(sql_alias, (like,)).fetchall()
            except sqlite3.OperationalError:
                alias_rows = []

        candidates: list[tuple[int, str, dict[str, Any]]] = []
        for r in direct_rows:
            sym = str(r["symbol"])
            if sym == text:
                rank = 1
            elif sym.startswith(text):
                rank = 3
            else:
                rank = 5
            candidates.append(
                (
                    rank,
                    sym,
                    {
                        "symbol": sym,
                        "name": str(r["name"]),
                        "is_etf": int(r["is_etf"]),
                        "last_date": str(r["last_date"]),
                        "matched_alias": None,
                    },
                )
            )

        for r in alias_rows:
            sym = str(r["symbol"])
            alias = str(r["alias"])
            if alias == text:
                rank = 2
            elif alias.startswith(text):
                rank = 4
            else:
                rank = 6
            candidates.append(
                (
                    rank,
                    sym,
                    {
                        "symbol": sym,
                        "name": str(r["name"]),
                        "is_etf": int(r["is_etf"]),
                        "last_date": str(r["last_date"]),
                        "matched_alias": alias,
                    },
                )
            )

        best_by_symbol: dict[str, tuple[int, str, dict[str, Any]]] = {}
        for rank, sym, item in candidates:
            if sym not in best_by_symbol:
                best_by_symbol[sym] = (rank, sym, item)
            else:
                if rank < best_by_symbol[sym][0]:
                    best_by_symbol[sym] = (rank, sym, item)

        sorted_candidates = sorted(best_by_symbol.values(), key=lambda t: (t[0], t[1]))
        return [t[2] for t in sorted_candidates[:limit]]

    def symbol_info(self, symbol: str) -> dict[str, Any]:
        sym = self.resolve(symbol)
        with self._connect() as conn:
            row = conn.execute("SELECT * FROM symbols WHERE symbol = ?", (sym,)).fetchone()
            if row is None:
                raise SymbolNotFoundError(sym)
            universes = [
                str(r[0])
                for r in conn.execute("SELECT universe FROM universes WHERE symbol = ?", (sym,))
            ]
            sources = [
                dict(r) for r in conn.execute("SELECT * FROM sources WHERE symbol = ?", (sym,))
            ]
            snap = conn.execute("SELECT * FROM snapshot WHERE symbol = ?", (sym,)).fetchone()
        info = dict(row)
        info["universes"] = universes
        info["sources"] = sources
        info["snapshot"] = dict(snap) if snap else None
        return info

    def universe(self, name: str) -> list[str]:
        with self._connect() as conn:
            return [
                str(r[0])
                for r in conn.execute(
                    "SELECT symbol FROM universes WHERE universe = ? ORDER BY symbol", (name,)
                )
            ]

    # ------------------------------------------------------------------------------ bars

    def bars(self, symbol: str, start: str | None = None, end: str | None = None) -> BarSeries:
        sym = self.resolve(symbol)
        sql = "SELECT d, o, h, l, c, v FROM bars WHERE symbol = ?"
        params: list[Any] = [sym]
        if start:
            sql += " AND d >= ?"
            params.append(start)
        if end:
            sql += " AND d <= ?"
            params.append(end)
        sql += " ORDER BY d"
        with self._connect() as conn:
            rows = conn.execute(sql, params).fetchall()
            if (
                not rows
                and conn.execute("SELECT 1 FROM symbols WHERE symbol = ?", (sym,)).fetchone()
                is None
            ):
                raise SymbolNotFoundError(sym)
        return _series(sym, rows)

    def bars_many(
        self, symbols: Sequence[str], start: str | None = None, end: str | None = None
    ) -> dict[str, BarSeries]:
        raw_wanted = sorted({s.strip().upper() for s in symbols if s.strip()})
        if not raw_wanted:
            return {}
        req_to_canon = {s: self.resolve(s) for s in raw_wanted}
        canonical_symbols = sorted(set(req_to_canon.values()))

        out: dict[str, list[sqlite3.Row]] = {s: [] for s in canonical_symbols}
        with self._connect() as conn:
            for chunk_start in range(0, len(canonical_symbols), 400):
                chunk = canonical_symbols[chunk_start : chunk_start + 400]
                marks = ",".join("?" for _ in chunk)
                sql = f"SELECT symbol, d, o, h, l, c, v FROM bars WHERE symbol IN ({marks})"
                params: list[Any] = list(chunk)
                if start:
                    sql += " AND d >= ?"
                    params.append(start)
                if end:
                    sql += " AND d <= ?"
                    params.append(end)
                sql += " ORDER BY symbol, d"
                for row in conn.execute(sql, params):
                    out[str(row["symbol"])].append(row)
        canonical_series = {sym: _series(sym, rows) for sym, rows in out.items() if rows}
        return {
            req: canonical_series[canon]
            for req, canon in req_to_canon.items()
            if canon in canonical_series
        }

    # --------------------------------------------------------------------------- screens

    def snapshot(self, universe: str = "liquid") -> list[dict[str, Any]]:
        sql = """
            SELECT s.*, y.name, y.is_etf, y.series, y.security_type, y.stitch
            FROM snapshot s
            JOIN symbols y ON y.symbol = s.symbol
            JOIN universes u ON u.symbol = s.symbol AND u.universe = ?
            ORDER BY s.symbol
        """
        with self._connect() as conn:
            return [dict(r) for r in conn.execute(sql, (universe,))]

    def actions(self, symbol: str) -> list[dict[str, Any]]:
        sym = self.resolve(symbol)
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT ex_date, subject, kinds, breaks_history FROM actions WHERE symbol = ? ORDER BY ex_date",
                (sym,),
            ).fetchall()
        return [
            {
                "ex_date": r["ex_date"],
                "subject": r["subject"],
                "kinds": str(r["kinds"]).split(","),
                "breaks_history": bool(r["breaks_history"]),
            }
            for r in rows
        ]

    def flags(self, symbol: str) -> list[dict[str, Any]]:
        """Data breaks (unexplained or unadjusted overnight gaps) for one symbol."""
        sym = self.resolve(symbol)
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT d, kind, change, note FROM flags WHERE symbol = ? ORDER BY d",
                (sym,),
            ).fetchall()
        return [dict(r) for r in rows]

    def flags_in_window(
        self, symbols: Sequence[str], start: str, end: str
    ) -> dict[str, list[dict[str, Any]]]:
        """Data breaks strictly after ``start`` and on or before ``end``, by symbol."""
        wanted = sorted({s.strip().upper() for s in symbols})
        found: dict[str, list[dict[str, Any]]] = {}
        with self._connect() as conn:
            for chunk_start in range(0, len(wanted), 400):
                chunk = wanted[chunk_start : chunk_start + 400]
                marks = ",".join("?" for _ in chunk)
                sql = (
                    "SELECT symbol, d, kind, change, note FROM flags "
                    f"WHERE d > ? AND d <= ? AND symbol IN ({marks}) ORDER BY d"
                )
                for row in conn.execute(sql, [start, end, *chunk]):
                    found.setdefault(str(row["symbol"]), []).append(
                        {k: row[k] for k in ("d", "kind", "change", "note")}
                    )
        return found

    def breaking_actions(
        self, symbols: Sequence[str], start: str, end: str
    ) -> dict[str, list[dict[str, str]]]:
        """Unsizable structural actions (demergers, rights) with an ex-date inside the window."""
        wanted = sorted({s.strip().upper() for s in symbols})
        found: dict[str, list[dict[str, str]]] = {}
        with self._connect() as conn:
            for chunk_start in range(0, len(wanted), 400):
                chunk = wanted[chunk_start : chunk_start + 400]
                marks = ",".join("?" for _ in chunk)
                sql = (
                    "SELECT symbol, ex_date, subject FROM actions WHERE breaks_history = 1 "
                    f"AND ex_date > ? AND ex_date <= ? AND symbol IN ({marks}) ORDER BY ex_date"
                )
                for row in conn.execute(sql, [start, end, *chunk]):
                    found.setdefault(str(row["symbol"]), []).append(
                        {"ex_date": str(row["ex_date"]), "subject": str(row["subject"])}
                    )
        return found

    def overview(self) -> dict[str, Any]:
        """Home-screen market pulse: benchmark, breadth and movers of the liquid universe."""
        liquid = self.snapshot("liquid")
        latest = max((r["asof"] for r in liquid), default="")
        current = [r for r in liquid if r["asof"] == latest]
        with_sma = [r for r in current if r["sma_200"] is not None]
        above = sum(1 for r in with_sma if r["close"] > r["sma_200"])
        advancers = sum(1 for r in current if (r["chg_1d"] or 0.0) > 0)
        decliners = sum(1 for r in current if (r["chg_1d"] or 0.0) < 0)
        ranked = sorted((r for r in current if r["chg_1d"] is not None), key=lambda r: r["chg_1d"])
        movers_fields = ("symbol", "name", "close", "chg_1d")
        return {
            "latest_session": latest,
            "benchmark": self._benchmark_card(),
            "breadth": {
                "universe": "liquid",
                "asof": latest,
                "count": len(current),
                "above_200dma": above,
                "above_200dma_pct": above / len(with_sma) if with_sma else None,
                "advancers": advancers,
                "decliners": decliners,
                "unchanged": len(current) - advancers - decliners,
                "stale": len(liquid) - len(current),
            },
            "gainers": [{k: r[k] for k in movers_fields} for r in reversed(ranked[-5:])],
            "losers": [{k: r[k] for k in movers_fields} for r in ranked[:5]],
        }

    def _benchmark_card(self) -> dict[str, Any] | None:
        try:
            info = self.symbol_info(BENCHMARK_SYMBOL)
            series = self.bars(BENCHMARK_SYMBOL)
        except SymbolNotFoundError:
            return None
        snap = info["snapshot"] or {}
        spark = series.close[-63:]
        return {
            "symbol": BENCHMARK_SYMBOL,
            "name": info["name"],
            "asof": snap.get("asof"),
            "close": snap.get("close"),
            "chg_1d": snap.get("chg_1d"),
            "ret_1m": snap.get("ret_1m"),
            "ret_1y": snap.get("ret_1y"),
            "spark": [float(x) for x in spark],
        }

    def stock_stats(self, symbol: str) -> dict[str, Any]:
        """Stock-page statistics, including beta against the benchmark on shared sessions."""
        sym = self.resolve(symbol)
        series = self.bars(sym)
        close = series.close
        stats: dict[str, Any] = {
            "ret_1m": metrics.period_return(close, metrics.SESSIONS_1M),
            "ret_6m": metrics.period_return(close, metrics.SESSIONS_6M),
            "ret_1y": metrics.period_return(close, metrics.SESSIONS_1Y),
            "ret_3y": metrics.period_return(close, 3 * metrics.SESSIONS_1Y),
            "ret_5y": metrics.period_return(close, 5 * metrics.SESSIONS_1Y),
            "vol_1y": metrics.annualized_volatility(close),
            "max_drawdown_1y": metrics.max_drawdown(close[-metrics.SESSIONS_1Y :]),
            "max_drawdown_all": metrics.max_drawdown(close),
            "beta_1y": None,
        }
        if series.symbol != BENCHMARK_SYMBOL:
            try:
                bench = self.bars(BENCHMARK_SYMBOL)
            except SymbolNotFoundError:
                bench = None
            if bench is not None:
                shared = sorted(set(series.dates[-metrics.SESSIONS_1Y :]) & set(bench.dates))
                if len(shared) >= 61:
                    a_pos = {d: i for i, d in enumerate(series.dates)}
                    b_pos = {d: i for i, d in enumerate(bench.dates)}
                    a = np.array([close[a_pos[d]] for d in shared])
                    b = np.array([bench.close[b_pos[d]] for d in shared])
                    stats["beta_1y"] = metrics.beta(a, b)
        return stats


def _series(symbol: str, rows: Sequence[sqlite3.Row]) -> BarSeries:
    return BarSeries(
        symbol=symbol,
        dates=[str(r["d"]) for r in rows],
        open=np.array([float(r["o"]) for r in rows], dtype=np.float64),
        high=np.array([float(r["h"]) for r in rows], dtype=np.float64),
        low=np.array([float(r["l"]) for r in rows], dtype=np.float64),
        close=np.array([float(r["c"]) for r in rows], dtype=np.float64),
        volume=np.array([float(r["v"]) for r in rows], dtype=np.float64),
    )
