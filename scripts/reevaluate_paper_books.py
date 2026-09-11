"""Re-evaluate both paper books against cash and a matched same-universe benchmark. Read-only.

What this answers
-----------------
The loss diagnosis established *what* each book is worth. It could not establish whether either book
is **underperforming** or merely **exposed to a market that fell**, because neither had a benchmark
with matched timing, exposure and costs. A long-only book in a falling market loses money while doing
exactly what it was asked to do; without a comparator that is indistinguishable from a bad model.

So every figure below is reported four ways, per the brief:

==========================  =================================================================
Component                   What it is
==========================  =================================================================
Gross P&L                   Marked value minus entry consideration. No costs of any kind
Paid costs                  Charges already deducted from cash -- entry fees, historical fees
Prospective exit costs      What closing every open position would cost, accrued not charged
Net P&L                     Gross minus paid minus prospective
==========================  =================================================================

Aggregating those into one number is what makes a paper book flatter itself: a book that has paid its
entry costs and not yet paid its exit costs looks better than it is, and one whose display charges
costs only at closing looks better still.

Benchmark construction
----------------------
The comparator is an **equal-weight basket of the same names the book actually holds**, entered at
the same session opens and marked at the same session, charged the same cost model on the same
notional. That isolates *selection and sizing* from market exposure: the benchmark holds the same
market risk, so the difference between them is what the strategy's weighting decisions earned.

Cash is reported alongside because it is the honest floor for a strategy that could have abstained.
For a short-horizon book cash is a live alternative, not a rhetorical one.

Read-only, and structurally so
------------------------------
Nothing here opens a file for writing under ``logs/``. Both books, their weights, their portfolio
state and their history are inputs. The report goes to ``reports/strategy_reevaluation/``.
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass, field
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR / "scripts"))
sys.path.insert(0, str(ROOT_DIR / "src"))

from build_mizan_feature_store import (  # noqa: E402
    code_revision,
    manifest_index,
    raw_bar_points,
)
from cached_nifty50_evidence import historical_acquisition_from_verified  # noqa: E402

from quant_system.evidence import (  # noqa: E402
    EvidenceResourceType,
    EvidenceStore,
    EvidenceStoreConfig,
)

XS_COST_RATIO = Decimal("0.00224")
"""The XS-Monthly simulator's own modelled round trip, read from its saved rule rather than assumed.

Overridden by the value in the book's state when present. Hard-coding a cost a book does not use
would produce a benchmark the book was never measured against.
"""


@dataclass(frozen=True, slots=True)
class Position:
    """One open leg, normalised across the two books' different state shapes."""

    symbol: str
    quantity: Decimal
    entry_price: Decimal
    opened_on: date
    entry_fee: Decimal = Decimal(0)

    @property
    def entry_value(self) -> Decimal:
        return self.quantity * self.entry_price


@dataclass
class BookDecomposition:
    """The four-way split, plus what could not be valued."""

    label: str
    initial_capital: Decimal
    cash: Decimal
    positions: list[Position]
    marked_value: Decimal = Decimal(0)
    entry_consideration: Decimal = Decimal(0)
    paid_costs: Decimal = Decimal(0)
    prospective_exit_costs: Decimal = Decimal(0)
    unpriced: list[dict[str, Any]] = field(default_factory=list)
    unmarked: list[str] = field(default_factory=list)

    @property
    def gross_pnl(self) -> Decimal:
        return self.marked_value - self.entry_consideration

    @property
    def net_pnl(self) -> Decimal:
        return self.gross_pnl - self.paid_costs - self.prospective_exit_costs

    def to_dict(self) -> dict[str, Any]:
        return {
            "label": self.label,
            "initial_capital": str(self.initial_capital),
            "cash": str(self.cash),
            "open_positions": len(self.positions),
            "entry_consideration": str(self.entry_consideration),
            "marked_value": str(self.marked_value),
            "gross_pnl": str(self.gross_pnl),
            "paid_costs": str(self.paid_costs),
            "prospective_exit_costs": str(self.prospective_exit_costs),
            "net_pnl": str(self.net_pnl),
            "net_return_on_initial_capital": (
                f"{float(self.net_pnl / self.initial_capital):+.6%}"
                if self.initial_capital
                else None
            ),
            "unpriced_assets": self.unpriced,
            "positions_without_a_mark": self.unmarked,
        }


def load_flagship(path: Path) -> BookDecomposition:
    payload = json.loads(path.read_text(encoding="utf-8"))["payload"]
    positions = [
        Position(
            symbol=str(item["symbol"]),
            quantity=Decimal(str(item["quantity"])),
            entry_price=Decimal(str(item["average_cost"])),
            opened_on=date.fromisoformat(str(item["opened_on"])),
            entry_fee=Decimal(str(item.get("entry_fee", "0"))),
        )
        for item in payload["holdings"]
    ]
    book = BookDecomposition(
        label="Flagship (Mizan, 10 held sessions)",
        initial_capital=Decimal("1000000"),
        cash=Decimal(str(payload["cash"])),
        positions=positions,
    )
    # total_fees is lifetime and has already reduced cash. Entry fees are a component of it, so
    # summing both would double-count the same rupees.
    book.paid_costs = Decimal(str(payload["total_fees"]))
    return book


def load_xs_monthly(path: Path) -> tuple[BookDecomposition, Decimal, dict[str, Decimal], date]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    positions = [
        Position(
            symbol=str(item["symbol"]),
            quantity=Decimal(str(item["shares"])),
            entry_price=Decimal(str(item["entry_open"])),
            opened_on=date.fromisoformat(str(item["entry_date"])),
        )
        for item in payload["open"]
        if Decimal(str(item["shares"])) > 0
    ]
    rule = payload.get("rule") or {}
    cost_ratio = Decimal(str(rule.get("cost_ratio", XS_COST_RATIO)))
    book = BookDecomposition(
        label="XS-Monthly (frozen momentum rule, 21 held sessions)",
        initial_capital=Decimal(str(payload.get("capital", "1000000"))),
        cash=Decimal(str(payload["cash"])),
        positions=positions,
    )
    # This book charges its round trip at closing, so nothing has been paid yet and the whole thing
    # is prospective. Reporting it as zero cost until close is what makes the display flatter itself.
    book.paid_costs = Decimal(0)
    # This book records a per-leg `market_value` and the `asof_date` it was struck. Those are the
    # only prices in this repository that cover its holding period -- the research cache ends
    # 2026-08-21 and this book entered on 2026-09-02.
    marks = {
        str(item["symbol"]): Decimal(str(item["market_value"]))
        for item in payload["open"]
        if Decimal(str(item["shares"])) > 0 and item.get("market_value") is not None
    }
    asof = max(
        date.fromisoformat(str(item["asof_date"]))
        for item in payload["open"]
        if item.get("asof_date")
    )
    return book, cost_ratio, marks, asof


class MarkDateBeforeEntry(ValueError):
    """The valuation date precedes a position's own entry. There is nothing to value yet."""


def mark_book(
    book: BookDecomposition,
    closes: dict[str, dict[date, Decimal]],
    mark_on: date,
    *,
    cost_ratio: Decimal,
    unpriced_symbols: dict[str, dict[str, Any]],
    book_marks: dict[str, Decimal] | None = None,
) -> None:
    """Value every open position at ``mark_on``, and say plainly what could not be valued.

    Refuses outright when ``mark_on`` precedes the earliest entry. That is not a defensive nicety --
    it is the defect this function shipped with. The research cache ends 2026-08-21 while Flagship
    opened on 2026-08-31 and XS-Monthly on 2026-09-02, so ``_price_on_or_before`` cheerfully returned
    a price from *ten days before the position existed*, and the resulting "gross P&L" of +9,229 was
    the difference between an entry price and a pre-entry price. It looked entirely plausible.

    ``book_marks`` lets a caller supply the book's **own** recorded per-name marks. That is the only
    price source in this repository that covers either book's holding period.
    """
    earliest = min((position.opened_on for position in book.positions), default=None)
    if book_marks is None and earliest is not None and mark_on < earliest:
        raise MarkDateBeforeEntry(
            f"{book.label}: mark date {mark_on.isoformat()} precedes the earliest entry "
            f"{earliest.isoformat()}. Marking here would value a position at a price from before it "
            f"was opened. No price source in this repository covers this book's holding period."
        )
    for position in book.positions:
        if position.symbol in unpriced_symbols:
            # Checked before the book's own marks, deliberately. The book *does* record a mark for
            # HEG -- it multiplies the post-demerger quote by the pre-demerger share count -- and
            # that mark is precisely the figure in dispute. Taking it here would import the error
            # this exclusion exists to remove.
            # Excluded from BOTH sides. Counting its entry cost while excluding its value would
            # implicitly mark the whole position at zero -- the very assertion this exclusion
            # exists to avoid, and a larger error than the one being corrected. The entry cost is
            # reported instead, so the capital is visible without being valued.
            book.unpriced.append(
                {
                    "symbol": position.symbol,
                    "quantity": str(position.quantity),
                    "entry_price": str(position.entry_price),
                    "entry_value": str(position.entry_value),
                    **unpriced_symbols[position.symbol],
                }
            )
            continue
        book.entry_consideration += position.entry_value
        if book_marks is not None:
            mark = book_marks.get(position.symbol)
            if mark is None:
                book.unmarked.append(position.symbol)
                continue
            book.marked_value += mark
            book.prospective_exit_costs += mark * cost_ratio
            continue
        if position.symbol in unpriced_symbols:
            # Deliberately excluded from marked value. An entitlement nothing can price must not be
            # silently valued at zero, which would book a loss that has not been established.
            book.unpriced.append({"symbol": position.symbol, **unpriced_symbols[position.symbol]})
            continue
        series = closes.get(position.symbol)
        price = _price_on_or_before(series, mark_on) if series else None
        if price is None:
            book.unmarked.append(position.symbol)
            continue
        book.marked_value += position.quantity * price
        book.prospective_exit_costs += position.quantity * price * cost_ratio


def _price_on_or_before(series: dict[date, Decimal] | None, on: date) -> Decimal | None:
    if not series:
        return None
    candidates = [value for value in series if value <= on]
    return series[max(candidates)] if candidates else None


def matched_benchmark(
    book: BookDecomposition,
    closes: dict[str, dict[date, Decimal]],
    mark_on: date,
    *,
    cost_ratio: Decimal,
    unpriced_symbols: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    """Equal-weight the same names, same entry sessions, same notional, same costs.

    Same names deliberately. Comparing against a broad index would conflate two different questions:
    whether the *universe* the book chose from went up, and whether the book's *weighting* within it
    was good. Holding the names constant and varying only the weights isolates the second.
    """
    priced = [
        position
        for position in book.positions
        if position.symbol not in unpriced_symbols and position.symbol in closes
    ]
    if not priced:
        return {"available": False, "reason": "no position could be priced"}

    per_name = book.entry_consideration / Decimal(len(priced))
    entry_total = Decimal(0)
    marked_total = Decimal(0)
    for position in priced:
        entry_price = position.entry_price
        mark = _price_on_or_before(closes.get(position.symbol), mark_on)
        if mark is None or entry_price <= 0:
            continue
        units = per_name / entry_price
        entry_total += per_name
        marked_total += units * mark

    gross = marked_total - entry_total
    exit_costs = marked_total * cost_ratio
    entry_costs = entry_total * cost_ratio / 2
    return {
        "available": True,
        "construction": "equal-weight the same names, same entry sessions, same total notional",
        "names": len(priced),
        "entry_consideration": str(entry_total),
        "marked_value": str(marked_total),
        "gross_pnl": str(gross),
        "modelled_entry_costs": str(entry_costs),
        "prospective_exit_costs": str(exit_costs),
        "net_pnl": str(gross - entry_costs - exit_costs),
    }


def matched_benchmark_from_marks(
    book: BookDecomposition,
    marks: dict[str, Decimal],
    *,
    cost_ratio: Decimal,
) -> dict[str, Any]:
    """Equal-weight the same names using the book's own recorded marks.

    Uses the book's own prices deliberately. They are the only source in this repository covering its
    holding period, and using them for both sides makes the comparison internally consistent: any
    error in the marks affects the book and its benchmark identically and cancels in the difference.
    """
    priced = [p for p in book.positions if p.symbol in marks and p.entry_price > 0]
    if not priced:
        return {"available": False, "reason": "no position carries a recorded mark"}
    per_name = book.entry_consideration / Decimal(len(priced))
    entry_total = Decimal(0)
    marked_total = Decimal(0)
    for position in priced:
        # The book records a leg's total market value, so its per-share price is that over quantity.
        price = marks[position.symbol] / position.quantity
        units = per_name / position.entry_price
        entry_total += per_name
        marked_total += units * price
    gross = marked_total - entry_total
    exit_costs = marked_total * cost_ratio
    return {
        "available": True,
        "construction": "equal-weight the same names, same entry prices, book's own marks",
        "names": len(priced),
        "entry_consideration": str(entry_total),
        "marked_value": str(marked_total),
        "gross_pnl": str(gross),
        "modelled_entry_costs": "0",
        "prospective_exit_costs": str(exit_costs),
        "net_pnl": str(gross - exit_costs),
    }


def load_closes(
    store_root: Path, symbols: set[str], index_cache: Path
) -> dict[str, dict[date, Decimal]]:
    """Close series for exactly the symbols the books hold."""
    _, dataset_ids = manifest_index(store_root, index_cache)
    store = EvidenceStore(EvidenceStoreConfig(root=store_root))
    out: dict[str, dict[date, Decimal]] = {}
    for index, symbol in enumerate(sorted(symbols), 1):
        dataset_id = dataset_ids.get(symbol)
        if dataset_id is None:
            continue
        verified = store.open_verified(EvidenceResourceType.DATASET, dataset_id)
        bars = raw_bar_points(historical_acquisition_from_verified(verified))
        out[symbol] = {bar.on: bar.close for bar in bars}
        if index % 50 == 0:
            print(f"  marked {index}/{len(symbols)} symbols", flush=True)
    return out


def run(args: argparse.Namespace) -> int:
    unpriced_symbols: dict[str, dict[str, Any]] = {
        "HEG": {
            "reason": "DEMERGER_ENTITLEMENT_UNPRICED",
            "detail": (
                "HEG's demerger has ex-date and record date 2026-09-07, entitling one resulting "
                "company share per HEG share per the company filing. The resulting company has no "
                "price anywhere in this repository -- the market cache ends 2026-08-21. Excluded "
                "from marked value rather than valued at zero: booking the full quote drop as a "
                "loss would assert the entitlement is worthless, which no evidence here supports."
            ),
            "filing": "https://bazaarwatch.com/announcement/88270/heg-ltd-attached",
        }
    }

    flagship = load_flagship(args.flagship_state)
    xs_monthly, xs_cost, xs_marks, xs_asof = load_xs_monthly(args.xs_state)
    print(f"flagship  : {len(flagship.positions)} open positions", flush=True)
    print(f"xs-monthly: {len(xs_monthly.positions)} funded legs", flush=True)

    symbols = {p.symbol for p in flagship.positions} | {p.symbol for p in xs_monthly.positions}
    print(f"marking   : {len(symbols)} distinct symbols", flush=True)
    closes = load_closes(args.store_root, symbols, args.index_cache)
    print(f"priced    : {len(closes)} of {len(symbols)}", flush=True)

    results: dict[str, Any] = {
        "generated_at": datetime.now(UTC).isoformat(),
        "code_revision": code_revision(),
        "mark_date": args.mark_on.isoformat(),
        "store_root": args.store_root.as_posix(),
        "note": (
            "Marks come from the research market cache, whose last session is earlier than the "
            "books' own live marks. These figures are therefore a like-for-like comparison against "
            "the benchmark at one common date, NOT a restatement of either book's live valuation."
        ),
        "books": {},
    }

    plans = (
        (flagship, args.flagship_cost_ratio, None, args.mark_on),
        (xs_monthly, xs_cost, xs_marks, xs_asof),
    )
    for book, cost_ratio, book_marks, mark_on in plans:
        try:
            mark_book(
                book,
                closes,
                mark_on,
                cost_ratio=cost_ratio,
                unpriced_symbols=unpriced_symbols,
                book_marks=book_marks,
            )
        except MarkDateBeforeEntry as refusal:
            results["books"][book.label] = {
                "label": book.label,
                "status": "REFUSED_NO_PRICE_SOURCE",
                "detail": str(refusal),
                "open_positions": len(book.positions),
            }
            print(f"\n=== {book.label} ===")
            print(f"  REFUSED: {refusal}")
            continue

        benchmark = (
            matched_benchmark_from_marks(book, book_marks, cost_ratio=cost_ratio)
            if book_marks is not None
            else matched_benchmark(
                book, closes, mark_on, cost_ratio=cost_ratio, unpriced_symbols=unpriced_symbols
            )
        )
        entry = book.to_dict()
        entry["status"] = "MARKED"
        entry["mark_date"] = mark_on.isoformat()
        entry["mark_source"] = "book's own recorded marks" if book_marks else "research cache"
        entry["modelled_round_trip_cost_ratio"] = str(cost_ratio)
        entry["matched_benchmark"] = benchmark
        entry["cash_alternative_pnl"] = "0"
        if benchmark.get("available"):
            entry["excess_over_benchmark_net"] = str(book.net_pnl - Decimal(benchmark["net_pnl"]))
        results["books"][book.label] = entry

        print(f"\n=== {book.label} ===")
        print(f"  marked at              : {mark_on.isoformat()} ({entry['mark_source']})")
        print(f"  entry consideration    : {book.entry_consideration:>14,.2f}")
        print(f"  marked value           : {book.marked_value:>14,.2f}")
        print(f"  gross P&L              : {book.gross_pnl:>+14,.2f}")
        print(f"  paid costs             : {book.paid_costs:>14,.2f}")
        print(f"  prospective exit costs : {book.prospective_exit_costs:>14,.2f}")
        print(f"  NET P&L                : {book.net_pnl:>+14,.2f}")
        if benchmark.get("available"):
            print(
                f"  benchmark net P&L      : {Decimal(benchmark['net_pnl']):>+14,.2f} "
                f"(equal-weight, {benchmark['names']} names)"
            )
            print(
                f"  EXCESS over benchmark  : "
                f"{book.net_pnl - Decimal(benchmark['net_pnl']):>+14,.2f}"
            )
        print(f"  cash alternative       : {0:>14,.2f}")
        for item in book.unpriced:
            print(f"  UNPRICED: {item['symbol']} -- {item['reason']}")
        if book.unmarked:
            print(f"  no mark available for  : {len(book.unmarked)} symbols")

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(results, indent=2, sort_keys=True), encoding="utf-8")
    print(f"\nwritten   : {args.out}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--flagship-state", type=Path, default=ROOT_DIR / "logs/paper_runs/portfolio_state.json"
    )
    parser.add_argument(
        "--xs-state", type=Path, default=ROOT_DIR / "logs/xs_monthly_new/paper_watch/state.json"
    )
    parser.add_argument(
        "--store-root",
        type=Path,
        default=ROOT_DIR / "data/evidence/market-cache/all-market-20160822-20260821/store",
    )
    parser.add_argument(
        "--index-cache",
        type=Path,
        default=ROOT_DIR / "reports/corporate_action_validation/store-manifest-index.json",
    )
    parser.add_argument(
        "--mark-on",
        type=date.fromisoformat,
        default=date(2026, 8, 21),
        help="Common valuation date for both books and both benchmarks. Defaults to the research "
        "cache's last session, which is the latest date every instrument can be priced at.",
    )
    parser.add_argument(
        "--flagship-cost-ratio",
        type=Decimal,
        default=Decimal("0.00224"),
        help="Round-trip cost ratio used to accrue Flagship's prospective exit costs.",
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=ROOT_DIR / "reports/strategy_reevaluation/paper-book-decomposition.json",
    )
    return run(parser.parse_args())


if __name__ == "__main__":
    raise SystemExit(main())
