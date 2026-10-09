"""Developer and CI tool: build the bundled Shariah filings snapshot from NSE's published results.

Users never run this. It reads each company's newest results filing from NSE, one request at a time with a
pause between requests, keeps progress in a folder outside the repository so a stopped run can resume, and
writes `data/shariah/filings_snapshot.json.gz`. It refuses to write any row that lacks its hash or source link.

    uv run python scripts/build_shariah_filings_snapshot.py --limit 12 --out <somewhere outside data/>
"""

from __future__ import annotations

import argparse
import csv
import json
import sqlite3
import sys
import tempfile
from collections import Counter
from collections.abc import Callable, Sequence
from contextlib import closing
from datetime import date
from pathlib import Path
from typing import Protocol

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR / "src") not in sys.path:
    sys.path.insert(0, str(ROOT_DIR / "src"))

from quant_system.shariah.filings.models import (  # noqa: E402
    FilingFigures,
    IndustryGroup,
    ReadStatus,
    normalize_symbol,
)
from quant_system.shariah.filings.nse_client import (  # noqa: E402
    FilingsBlocked,
    FilingsError,
    NseFilingsClient,
)
from quant_system.shariah.filings.selection import Selection  # noqa: E402
from quant_system.shariah.filings.service import LiveSource  # noqa: E402
from quant_system.shariah.filings.snapshot import (  # noqa: E402
    FilingsStoreError,
    IndustrySnapshot,
    check_row,
    write_snapshot,
)

DEFAULT_UNIVERSE = ROOT_DIR / "data" / "authorities" / "nse-research-universe-liquid-10y.csv"
DEFAULT_SAMPLE_DB = ROOT_DIR / "data" / "shariah" / "halal_stocks.db"
DEFAULT_OUT = ROOT_DIR / "data" / "shariah" / "filings_snapshot.json.gz"
DEFAULT_RESUME = Path(tempfile.gettempdir()) / "quantos_shariah_filings_resume"
MAX_BLOCKS_IN_A_ROW = 3
SUMMARY_ORDER = (
    "READ_OK",
    "READ_PARTIAL",
    "TIE_OUT_FAILED",
    "FORMAT_NOT_READ",
    "NO_BALANCE_SHEET",
    "failed",
)
EXIT_OK, EXIT_BAD_DATA, EXIT_STOPPED = 0, 1, 2


class FilingsSource(Protocol):
    def read_company(self, symbol: str) -> Selection: ...

    def fetch_industry_groups(self) -> dict[str, IndustryGroup]: ...


SourceFactory = Callable[[float], FilingsSource]


def load_universe_symbols(path: Path) -> list[str]:
    """Symbols from the research universe CSV (comment lines start with #; the column is `Symbol`)."""
    with path.open(encoding="utf-8", newline="") as handle:
        lines = [line for line in handle if line.strip() and not line.startswith("#")]
    symbols = {normalize_symbol(row.get("Symbol", "")) for row in csv.DictReader(lines)}
    return sorted(symbol for symbol in symbols if symbol)


def load_sample_symbols(path: Path) -> list[str]:
    """Tickers of the hand-entered sample companies, with the exchange suffix removed. Opened read-only."""
    if not path.is_file():
        return []
    try:
        with closing(sqlite3.connect(f"{path.resolve().as_uri()}?mode=ro", uri=True)) as connection:
            tickers = [str(row[0]) for row in connection.execute("SELECT ticker FROM companies")]
    except sqlite3.Error:
        return []
    cleaned = {
        normalize_symbol(ticker.rsplit(".", 1)[0] if ticker.endswith((".NS", ".BO")) else ticker)
        for ticker in tickers
    }
    return sorted(symbol for symbol in cleaned if symbol)


def _cache_get(folder: Path, symbol: str) -> Selection | None:
    try:
        entry = json.loads((folder / f"{symbol}.json").read_text(encoding="utf-8"))
        status = ReadStatus(entry["read_status"])
        raw = entry["figures"]
        figures = FilingFigures.from_json_dict(raw) if raw is not None else None
        return Selection(figures, status, str(entry["note"]), int(entry["tried"]))
    except (OSError, ValueError, KeyError, TypeError):
        return None


def _cache_put(folder: Path, symbol: str, found: Selection) -> None:
    entry = {
        "read_status": found.read_status.value,
        "note": found.note,
        "tried": found.tried,
        "figures": found.figures.to_json_dict() if found.figures else None,
    }
    (folder / f"{symbol}.json").write_text(json.dumps(entry, sort_keys=True), encoding="utf-8")


def _industry(folder: Path, source: FilingsSource, built_on: str) -> IndustrySnapshot:
    """The industry list is read once and kept in the resume folder, so a rerun does not ask again."""
    path = folder / "industry_groups.json"
    try:
        saved = json.loads(path.read_text(encoding="utf-8"))
        return IndustrySnapshot(dict(saved["groups"]), str(saved["read_on"]))
    except (OSError, ValueError, KeyError, TypeError):
        pass
    groups = {symbol: group.industry for symbol, group in source.fetch_industry_groups().items()}
    path.write_text(
        json.dumps({"groups": groups, "read_on": built_on}, sort_keys=True), encoding="utf-8"
    )
    return IndustrySnapshot(groups, built_on)


def _parse_args(argv: Sequence[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0] if __doc__ else None)
    parser.add_argument("--symbols-csv", type=Path, default=DEFAULT_UNIVERSE)
    parser.add_argument("--extra-symbols-from-sample-db", action="store_true")
    parser.add_argument("--sample-db", type=Path, default=DEFAULT_SAMPLE_DB)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--resume-dir", type=Path, default=DEFAULT_RESUME)
    parser.add_argument(
        "--pause", type=float, default=1.5, help="seconds between requests (at least 1.2)"
    )
    parser.add_argument(
        "--built-on", default=None, help="YYYY-MM-DD recorded in the snapshot (default today)"
    )
    return parser.parse_args(argv)


def _symbols(args: argparse.Namespace) -> list[str]:
    found = set(load_universe_symbols(args.symbols_csv))
    if args.extra_symbols_from_sample_db:
        found.update(load_sample_symbols(args.sample_db))
    ordered = sorted(found)
    return ordered[: args.limit] if args.limit is not None else ordered


def _print_summary(counts: Counter[str], total: int) -> None:
    print(f"\nSummary for {total} symbols")
    for label in SUMMARY_ORDER:
        print(f"  {label:<18}{counts.get(label, 0):>6}")


def _read_symbol(symbol: str, source: FilingsSource, folder: Path) -> Selection:
    """One symbol's result, from the resume folder if it was already read, else from NSE."""
    found = _cache_get(folder, symbol)
    if found is None:
        found = source.read_company(symbol)
        if found.figures is not None:
            check_row(symbol, found.figures)
        _cache_put(folder, symbol, found)
    return found


def _collect(
    symbols: list[str], source: FilingsSource, folder: Path
) -> tuple[dict[str, FilingFigures], Counter[str]] | int:
    """Read every symbol. Returns an exit code instead when NSE keeps refusing."""
    filings: dict[str, FilingFigures] = {}
    counts: Counter[str] = Counter()
    blocks = 0
    for symbol in symbols:
        try:
            found = _read_symbol(symbol, source, folder)
        except FilingsError as error:
            counts["failed"] += 1
            print(f"{symbol}: {error}" + (f" [{error.detail}]" if error.detail else ""))
            blocks = blocks + 1 if isinstance(error, FilingsBlocked) else 0
            if blocks >= MAX_BLOCKS_IN_A_ROW:
                print(f"Stopped after {blocks} refusals in a row. Progress is kept in {folder}.")
                return EXIT_STOPPED
            continue
        blocks = 0
        counts[found.read_status.value] += 1
        if found.figures is not None:
            filings[symbol] = found.figures
    return filings, counts


def main(argv: Sequence[str] | None = None, source_factory: SourceFactory | None = None) -> int:
    args = _parse_args(argv)
    built_on = args.built_on or date.today().isoformat()
    symbols = _symbols(args)
    args.resume_dir.mkdir(parents=True, exist_ok=True)
    factory: SourceFactory = source_factory or (
        lambda pause: LiveSource(NseFilingsClient(pause_seconds=pause))
    )
    source = factory(args.pause)
    try:
        industry = _industry(args.resume_dir, source, built_on)
        outcome = _collect(symbols, source, args.resume_dir)
        if isinstance(outcome, int):
            return outcome
        filings, counts = outcome
        write_snapshot(args.out, filings, built_on, industry)
    except FilingsStoreError as error:
        print(f"Not written: {error}")
        return EXIT_BAD_DATA
    except FilingsError as error:
        print(f"Stopped: {error}")
        return EXIT_STOPPED
    _print_summary(counts, len(symbols))
    print(f"Wrote {len(filings)} filings and {len(industry.groups)} industry groups to {args.out}")
    return EXIT_OK


if __name__ == "__main__":
    sys.exit(main())
