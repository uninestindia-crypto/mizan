"""Developer and CI tool: build the bundled fundamentals snapshot from NSE's published quarterly results.

Users never run this. It reads each company's last quarterly results filings from NSE, one request at a time with a
pause between requests, keeps progress in a folder outside the repository so a stopped run can resume, and writes
`data/fundamentals/fundamentals_snapshot.json.gz`. It refuses to write any row that lacks its hash or source link.

    uv run python scripts/build_fundamentals_snapshot.py --limit 2 --out <somewhere outside data/>
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
import tempfile
from collections import Counter
from collections.abc import Callable, Sequence
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Protocol

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR / "src") not in sys.path:
    sys.path.insert(0, str(ROOT_DIR / "src"))

from quant_system.fundamentals.models import QuarterFigures  # noqa: E402
from quant_system.fundamentals.reader import CompanyRead, read_company  # noqa: E402
from quant_system.fundamentals.snapshot import (  # noqa: E402
    FundamentalsStoreError,
    IndustrySnapshot,
    check_row,
    normalize_symbol,
    write_snapshot,
)
from quant_system.shariah.filings.models import IndustryGroup  # noqa: E402
from quant_system.shariah.filings.nse_client import (  # noqa: E402
    FilingsBlocked,
    FilingsError,
    NseFilingsClient,
)

DEFAULT_UNIVERSE = ROOT_DIR / "data" / "authorities" / "nse-research-universe-liquid-10y.csv"
DEFAULT_OUT = ROOT_DIR / "data" / "fundamentals" / "fundamentals_snapshot.json.gz"
DEFAULT_RESUME = Path(tempfile.gettempdir()) / "quantos_fundamentals_resume"
DEFAULT_QUARTERS = 8
MAX_BLOCKS_IN_A_ROW = 3
SUMMARY_ORDER = ("READ_OK", "READ_PARTIAL", "TIE_OUT_FAILED", "FORMAT_NOT_READ", "NOT_A_QUARTER")
EXIT_OK, EXIT_BAD_DATA, EXIT_STOPPED = 0, 1, 2


class Source(Protocol):
    def read_company(self, symbol: str, quarters: int) -> CompanyRead: ...

    def fetch_industry_groups(self) -> dict[str, IndustryGroup]: ...


SourceFactory = Callable[[float], Source]


class LiveSource:
    """NSE, one polite request at a time."""

    def __init__(self, pause: float) -> None:
        self._client = NseFilingsClient(pause_seconds=pause)

    def read_company(self, symbol: str, quarters: int) -> CompanyRead:
        return read_company(self._client, symbol, quarters, lambda: datetime.now(UTC))

    def fetch_industry_groups(self) -> dict[str, IndustryGroup]:
        return self._client.fetch_industry_groups()


def load_universe_symbols(path: Path) -> list[str]:
    """Symbols from the research universe CSV (comment lines start with #; the column is `Symbol`)."""
    with path.open(encoding="utf-8", newline="") as handle:
        lines = [line for line in handle if line.strip() and not line.startswith("#")]
    symbols = {normalize_symbol(row.get("Symbol", "")) for row in csv.DictReader(lines)}
    return sorted(symbol for symbol in symbols if symbol)


def _cache_get(folder: Path, symbol: str) -> CompanyRead | None:
    try:
        entry = json.loads((folder / f"{symbol}.json").read_text(encoding="utf-8"))
        quarters = [QuarterFigures.from_json_dict(item) for item in entry["quarters"]]
        return CompanyRead(quarters, int(entry["skipped"]), int(entry["planned"]))
    except (OSError, ValueError, KeyError, TypeError):
        return None


def _cache_put(folder: Path, symbol: str, found: CompanyRead) -> None:
    entry = {
        "planned": found.planned,
        "skipped": found.skipped,
        "quarters": [item.to_json_dict() for item in found.quarters],
    }
    (folder / f"{symbol}.json").write_text(json.dumps(entry, sort_keys=True), encoding="utf-8")


def _industry(folder: Path, source: Source, built_on: str) -> IndustrySnapshot:
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
    parser.add_argument(
        "--only", default=None, help="comma-separated symbols instead of the universe file"
    )
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument(
        "--quarters", type=int, default=DEFAULT_QUARTERS, help="quarterly filings per company"
    )
    parser.add_argument("--resume-dir", type=Path, default=DEFAULT_RESUME)
    parser.add_argument(
        "--pause", type=float, default=1.5, help="seconds between requests (at least 1.2)"
    )
    parser.add_argument(
        "--built-on", default=None, help="YYYY-MM-DD recorded in the snapshot (default today)"
    )
    return parser.parse_args(argv)


def _symbols(args: argparse.Namespace) -> list[str]:
    if args.only:
        found = {normalize_symbol(part.strip()) for part in args.only.split(",")}
        ordered = sorted(symbol for symbol in found if symbol)
    else:
        ordered = load_universe_symbols(args.symbols_csv)
    return ordered[: args.limit] if args.limit is not None else ordered


def _read_symbol(symbol: str, source: Source, args: argparse.Namespace) -> CompanyRead:
    """One symbol's result, from the resume folder if it was already read, else from NSE."""
    found = _cache_get(args.resume_dir, symbol)
    if found is None:
        found = source.read_company(symbol, args.quarters)
        for item in found.quarters:
            check_row(symbol, item)
        _cache_put(args.resume_dir, symbol, found)
    return found


def _collect(
    symbols: list[str], source: Source, args: argparse.Namespace
) -> tuple[dict[str, list[QuarterFigures]], Counter[str]] | int:
    """Read every symbol. Returns an exit code instead when NSE keeps refusing."""
    companies: dict[str, list[QuarterFigures]] = {}
    counts: Counter[str] = Counter()
    blocks = 0
    for symbol in symbols:
        try:
            found = _read_symbol(symbol, source, args)
        except FilingsError as error:
            counts["failed"] += 1
            print(f"{symbol}: {error}" + (f" [{error.detail}]" if error.detail else ""))
            blocks = blocks + 1 if isinstance(error, FilingsBlocked) else 0
            if blocks >= MAX_BLOCKS_IN_A_ROW:
                print(
                    f"Stopped after {blocks} refusals in a row. Progress is kept in {args.resume_dir}."
                )
                return EXIT_STOPPED
            continue
        blocks = 0
        if not found.quarters:
            counts["no filings"] += 1
        counts.update(item.status.value for item in found.quarters)
        if found.quarters:
            companies[symbol] = found.quarters
    return companies, counts


def _print_summary(counts: Counter[str], total: int) -> None:
    print(f"\nFilings read, for {total} symbols")
    for label in (*SUMMARY_ORDER, "no filings", "failed"):
        print(f"  {label:<18}{counts.get(label, 0):>6}")


def main(argv: Sequence[str] | None = None, source_factory: SourceFactory | None = None) -> int:
    args = _parse_args(argv)
    built_on = args.built_on or date.today().isoformat()
    symbols = _symbols(args)
    args.resume_dir.mkdir(parents=True, exist_ok=True)
    source = (source_factory or LiveSource)(args.pause)
    try:
        industry = _industry(args.resume_dir, source, built_on)
        outcome = _collect(symbols, source, args)
        if isinstance(outcome, int):
            return outcome
        companies, counts = outcome
        write_snapshot(args.out, companies, built_on, industry)
    except FundamentalsStoreError as error:
        print(f"Not written: {error}")
        return EXIT_BAD_DATA
    except FilingsError as error:
        print(f"Stopped: {error}")
        return EXIT_STOPPED
    _print_summary(counts, len(symbols))
    total = sum(len(rows) for rows in companies.values())
    print(
        f"Wrote {total} filings for {len(companies)} companies and {len(industry.groups)} industry groups to {args.out}"
    )
    return EXIT_OK


if __name__ == "__main__":
    sys.exit(main())
