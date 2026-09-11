"""Independently validate demerger adjustment factors, or refuse to size them.

Why this exists
---------------
NSE publishes demergers with no ratio. An earlier revision of
``quant_system.data.corporate_actions`` sized them from the parent's ex-date gap. That is not a
measurement of the corporate action: the gap is the action **plus** whatever the market did that
day, and nothing in the gap separates the two. Measured across the 423-name research universe, the
gap rule would have inferred an *upward* correction for NMDC (+71.0%), BAJAJELEC (+32.2%) and SCI
(+30.0%) -- a demerger cannot raise the parent's price, so those gaps are market movement or a
provider adjustment, and dividing them out erases a genuine move and invents a fake one.

So this script never derives a ratio from the parent's own price. It does two separable things.

**Discover.** For every ratio-less action it lists the candidate resulting companies -- instruments
in the market cache whose own history *begins* shortly after the parent's ex-date -- and reports the
parent's ex-date gap alongside the same-day market move, so the part of the gap that is market
movement is visible rather than absorbed. This half is automatic and produces a worklist.

**Validate.** For an action whose entitlement ratio a human has taken from the company filing (and
recorded in the entitlement table, with the filing's URL), it checks value continuity against the
*resulting company's own first traded price* -- a second instrument, independent of the parent's
gap::

    parent_close_cum  ~=  parent_open_ex  +  ratio x resulting_first_open

When that balances within tolerance, the adjustment factor ``parent_open_ex / parent_close_cum`` is
corroborated by evidence outside the gap and is emitted as ``VALIDATED``. When it does not balance,
or when no filing ratio exists, or when the resulting company is not in the cache, the action stays
**unresolved** and every return window spanning it is refused downstream.

The entitlement table is deliberately an input, not an inference. A ratio is a legal fact published
by the issuer; guessing it from prices is exactly the error this script exists to stop.
"""

from __future__ import annotations

import argparse
import gc
import json
import sys
from dataclasses import dataclass
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR / "scripts"))
sys.path.insert(0, str(ROOT_DIR / "src"))

from build_mizan_feature_store import (  # noqa: E402
    authority_manifest_hash,
    code_revision,
    load_corporate_actions,
    manifest_index,
    raw_bar_points,
    read_universe,
)
from cached_nifty50_evidence import historical_acquisition_from_verified  # noqa: E402

from quant_system.data.corporate_actions import parse_subject_factor  # noqa: E402
from quant_system.evidence import (  # noqa: E402
    EvidenceResourceType,
    EvidenceStore,
    EvidenceStoreConfig,
)

LISTING_WINDOW_DAYS = 60
"""How long after an ex-date a resulting company may first trade and still be a candidate.

A demerged entity lists after the record date, usually within four to eight weeks. 60 calendar days
is generous enough not to miss one and short enough that the ranked shortlist stays reviewable. A
candidate is a lead for a human to check against the filing, never an identification on its own.
"""

CANDIDATE_SHORTLIST = 5
"""How many ranked candidates to report per action. More is not more useful."""

PLAUSIBLE_RATIOS: tuple[tuple[str, Decimal], ...] = (
    ("1:1", Decimal(1)),
    ("1:2", Decimal(1) / Decimal(2)),
    ("1:3", Decimal(1) / Decimal(3)),
    ("1:4", Decimal(1) / Decimal(4)),
    ("1:5", Decimal(1) / Decimal(5)),
    ("1:10", Decimal(1) / Decimal(10)),
    ("2:1", Decimal(2)),
    ("3:1", Decimal(3)),
    ("5:1", Decimal(5)),
    ("10:1", Decimal(10)),
)
"""Entitlement ratios NSE demergers actually use, for ranking candidates.

Ranking against these is **discovery, not validation**. A candidate whose first traded price implies
a clean 1:1 is a strong lead precisely because a scheme of arrangement issues whole shares in simple
proportions -- but the ratio is a legal fact in the issuer's filing, and a price that happens to fit
is a coincidence until the filing says otherwise. Nothing here writes a factor.
"""

RATIO_MATCH_TOLERANCE = Decimal("0.08")
"""How close an implied ratio must sit to a clean one to be worth a human opening the filing.

**Measured false-discovery rate: 8.51%.** Across 2,091 candidate/action pairs on the real corpus,
178 cleared this tolerance. Ten clean ratios each with an 8% relative window cover roughly that much
of the plausible price range, so a fit is close to what chance produces -- for ABFRL's 2025-05-22
demerger the *correct* resulting company (ABLBL, implied 1.0237) ranked **fourth**, behind SILKY
(0.9997) which has nothing to do with it.

So the ratio fit alone does not identify anything. It is kept as a secondary sort only, and the
shortlist is ordered by :func:`name_stem_score` first.
"""

MINIMUM_STEM = 3
"""Shortest shared symbol prefix worth treating as evidence of a corporate relationship."""

CONTINUITY_TOLERANCE = Decimal("0.05")
"""Fractional tolerance on the value-continuity identity.

The parent's ex-date open and the resulting company's first open are set by two separate auctions
on possibly different days, so exact equality is not expected and demanding it would reject true
entitlements. 5% is tight enough that a wrong ratio (which is typically wrong by a factor, not by a
few percent) cannot pass.
"""


@dataclass(frozen=True, slots=True)
class Entitlement:
    """One entitlement ratio taken from an issuer filing, not from prices."""

    symbol: str
    ex_date: date
    resulting_symbol: str
    ratio: Decimal
    filing_url: str
    note: str = ""


def load_entitlements(path: Path | None) -> dict[tuple[str, date], Entitlement]:
    if path is None or not path.is_file():
        return {}
    payload = json.loads(path.read_text(encoding="utf-8"))
    out: dict[tuple[str, date], Entitlement] = {}
    for item in payload.get("entitlements", []):
        ex_date = date.fromisoformat(str(item["ex_date"]))
        entitlement = Entitlement(
            symbol=str(item["symbol"]),
            ex_date=ex_date,
            resulting_symbol=str(item["resulting_symbol"]),
            ratio=Decimal(str(item["ratio"])),
            filing_url=str(item["filing_url"]),
            note=str(item.get("note", "")),
        )
        out[(entitlement.symbol, ex_date)] = entitlement
    return out


def first_opens(
    store: EvidenceStore, symbols: set[str], dataset_ids: dict[str, str]
) -> dict[str, tuple[date, Decimal]]:
    """The first traded session and opening price of each candidate, and nothing else.

    Only one number per instrument is retained. Holding whole series for 1,200-odd candidates is
    what exhausted this machine on earlier runs; one ``(date, Decimal)`` pair each costs nothing.
    """
    out: dict[str, tuple[date, Decimal]] = {}
    for index, symbol in enumerate(sorted(symbols), 1):
        dataset_id = dataset_ids.get(symbol)
        if dataset_id is None:
            continue
        verified = store.open_verified(EvidenceResourceType.DATASET, dataset_id)
        bars = raw_bar_points(historical_acquisition_from_verified(verified))
        if bars and bars[0].open > 0:
            out[symbol] = (bars[0].on, bars[0].open)
        if index % 200 == 0:
            print(f"  candidate opens: {index}/{len(symbols)}", flush=True)
            gc.collect()
    return out


def name_stem_score(parent: str, candidate: str) -> int:
    """Length of the shared leading stem between two NSE symbols.

    A demerged entity usually keeps the parent's name stem, because the brand is the point: SKFINDIA
    spun out SKFINDUS, ABFRL spun out ABLBL (both Aditya Birla), RAYMOND spun out a Raymond entity.
    An unrelated IPO listing in the same window shares nothing.

    This is the discriminator the price fit is not. Measured on the corpus, 8.51% of arbitrary
    candidates fit a clean ratio; almost none share a three-character stem with the parent by
    accident. It is still only a **lead** -- the ratio remains a legal fact in the filing, and a
    conglomerate demerger can rename entirely.
    """
    shared = 0
    for left, right in zip(parent, candidate, strict=False):
        if left != right:
            break
        shared += 1
    return shared if shared >= MINIMUM_STEM else 0


def rank_candidates(
    parent: str,
    cum_close: Decimal,
    ex_open: Decimal,
    candidates: dict[str, tuple[date, Decimal]],
) -> list[dict[str, Any]]:
    """Shortlist the plausible resulting companies for one ratio-less action.

    For a resulting company priced ``P`` on listing, value continuity requires::

        parent_close_cum  =  parent_open_ex  +  ratio x P

    so the *implied* ratio is ``(cum_close - ex_open) / P``. A candidate whose implied ratio lands
    near a ratio schemes actually use is a lead worth opening the filing for; one that implies
    0.37 shares per share is not.

    This is discovery. It orders a human's reading list and states a hypothesis for each entry. It
    never writes a factor, because a coincidence of price is not a legal entitlement.
    """
    value_transferred = cum_close - ex_open
    if value_transferred <= 0:
        # The parent's price did not fall. Whatever happened, it is not value leaving to a
        # resulting company, so there is no entitlement to size and no candidate to rank.
        return []
    ranked: list[dict[str, Any]] = []
    for symbol, (listed_on, first_open) in candidates.items():
        implied = value_transferred / first_open
        best_label, best_gap = None, None
        for label, ratio in PLAUSIBLE_RATIOS:
            gap = abs(implied - ratio) / ratio
            if best_gap is None or gap < best_gap:
                best_label, best_gap = label, gap
        if best_gap is None or best_gap > RATIO_MATCH_TOLERANCE:
            continue
        ranked.append(
            {
                "candidate": symbol,
                "listed_on": listed_on.isoformat(),
                "first_open": str(first_open),
                "implied_ratio": f"{float(implied):.4f}",
                "nearest_clean_ratio": best_label,
                "relative_gap": f"{float(best_gap):.4f}",
                "shared_name_stem": name_stem_score(parent, symbol),
            }
        )
    # Name stem first, ratio fit only to break ties. The ratio fit is close to chance (8.51%
    # measured); the stem is not.
    ranked.sort(key=lambda item: (-int(item["shared_name_stem"]), float(item["relative_gap"])))
    return ranked[:CANDIDATE_SHORTLIST]


def load_universe_bars(
    store: EvidenceStore, keep: set[str], dataset_ids: dict[str, str]
) -> dict[str, list[Any]]:
    """Bars for the instruments a validation actually needs, opening no other dataset.

    ``EvidenceStore.list_verified`` opens and rehashes all 3,322 datasets to hand back the 424 this
    needs. Each one is still opened through ``open_verified``, so integrity checking is not skipped
    -- only the ~2,900 datasets this script never looks at are.
    """
    kept: dict[str, list[Any]] = {}
    for symbol in sorted(keep):
        dataset_id = dataset_ids.get(symbol)
        if dataset_id is None:
            continue
        verified = store.open_verified(EvidenceResourceType.DATASET, dataset_id)
        bars = raw_bar_points(historical_acquisition_from_verified(verified))
        if bars:
            kept[symbol] = bars
    return kept


def daily_median_moves(bars_by_symbol: dict[str, list[Any]]) -> dict[date, Decimal]:
    """Median close-to-close return per session across the research universe.

    This is the control that keeps genuine market movement visible. A parent gap of -20% on a day
    the whole market fell 18% is mostly market, not entitlement; a gap of -20% on a flat day is
    mostly entitlement. Neither observation *sizes* the action, but reporting a gap without it
    invites exactly the mistake this script exists to prevent.

    Computed over the 423-name liquid research universe rather than all 3,267 cached instruments.
    That is both cheaper and better: the universe is the liquid, ten-year-history subset, so its
    median is not dragged by microcaps that barely trade. It is a market control, not an index.

    Accumulated as **float**, deliberately -- this is a diagnostic that never reaches an accounting
    figure or a factor. Every number that does stays Decimal.
    """
    moves_by_date: dict[date, list[float]] = {}
    for bars in bars_by_symbol.values():
        for previous, current in zip(bars, bars[1:], strict=False):
            if previous.close > 0:
                moves_by_date.setdefault(current.on, []).append(
                    float(current.close / previous.close) - 1.0
                )
    medians: dict[date, Decimal] = {}
    for on, moves in moves_by_date.items():
        if len(moves) < 30:
            continue
        moves.sort()
        middle = len(moves) // 2
        median = moves[middle] if len(moves) % 2 else (moves[middle - 1] + moves[middle]) / 2
        medians[on] = Decimal(repr(median))
    return medians


def _ratioless_ex_dates(
    universe: dict[str, str],
    bars_by_symbol: dict[str, list[Any]],
    corporate_actions_dir: Path,
) -> list[tuple[date, str]]:
    """Every ratio-less action in the universe, as ``(ex_date, parent_symbol)``.

    Used to decide which candidate instruments are worth reading a first price for, before any of
    them is opened. Cheap: authority JSON only, no bars.
    """
    found: list[tuple[date, str]] = []
    for symbol in sorted(universe):
        if symbol not in bars_by_symbol:
            continue
        for ex_date, subject in load_corporate_actions(corporate_actions_dir, symbol):
            parsed = parse_subject_factor(subject, cum_close=Decimal("1e9"), total_return=False)
            if parsed.needs_inference:
                found.append((ex_date, symbol))
    return found


def run(args: argparse.Namespace) -> int:
    universe = read_universe(args.universe)
    entitlements = load_entitlements(args.entitlements)
    print(f"universe     : {len(universe)} symbols", flush=True)
    print(f"entitlements : {len(entitlements)} filing-sourced ratios", flush=True)

    keep = set(universe) | {item.resulting_symbol for item in entitlements.values()}
    first_traded, dataset_ids = manifest_index(args.store_root, args.index_cache)
    print(f"listing dates: {len(first_traded)} symbols (manifest headers only)", flush=True)

    store = EvidenceStore(EvidenceStoreConfig(root=args.store_root))
    bars_by_symbol = load_universe_bars(store, keep, dataset_ids)
    print(f"bars loaded  : {len(bars_by_symbol)} of {len(keep)} requested", flush=True)
    medians = daily_median_moves(bars_by_symbol)
    print(f"market control: median move for {len(medians):,} sessions", flush=True)

    # Pass 1: which instruments listed shortly after any ratio-less ex-date. Read from the header
    # index, so this costs nothing.
    ratioless_ex_dates = _ratioless_ex_dates(universe, bars_by_symbol, args.corporate_actions_dir)
    candidate_symbols = {
        other
        for ex_date, parent in ratioless_ex_dates
        for other, listed in first_traded.items()
        if other != parent and ex_date <= listed and (listed - ex_date).days <= LISTING_WINDOW_DAYS
    }
    print(
        f"candidates   : {len(candidate_symbols)} instruments listed within "
        f"{LISTING_WINDOW_DAYS}d of a ratio-less ex-date",
        flush=True,
    )
    candidate_opens = first_opens(store, candidate_symbols, dataset_ids)
    print(f"opens read   : {len(candidate_opens)} first traded prices", flush=True)

    discovered: list[dict[str, Any]] = []
    validated: list[dict[str, Any]] = []
    refused: list[dict[str, Any]] = []

    for symbol in sorted(universe):
        bars = bars_by_symbol.get(symbol)
        if not bars:
            continue
        index_of = {bar.on: i for i, bar in enumerate(bars)}
        for ex_date, subject in sorted(load_corporate_actions(args.corporate_actions_dir, symbol)):
            parsed = parse_subject_factor(subject, cum_close=Decimal("1e9"), total_return=False)
            if not parsed.needs_inference:
                continue

            position = index_of.get(ex_date)
            if position is None or position == 0:
                refused.append(
                    {
                        "symbol": symbol,
                        "ex_date": ex_date.isoformat(),
                        "reason": "NO_EX_DATE_BAR",
                        "subject": subject.strip(),
                    }
                )
                continue

            cum_close = bars[position - 1].close
            ex_open = bars[position].open
            gap = ex_open / cum_close - 1
            control = medians.get(ex_date)

            nearby = {
                other: opened
                for other, opened in candidate_opens.items()
                if other != symbol
                and ex_date <= opened[0]
                and (opened[0] - ex_date).days <= LISTING_WINDOW_DAYS
            }
            candidates = rank_candidates(symbol, cum_close, ex_open, nearby)

            record: dict[str, Any] = {
                "symbol": symbol,
                "ex_date": ex_date.isoformat(),
                "subject": subject.strip(),
                "cum_close": str(cum_close),
                "ex_open": str(ex_open),
                "ex_date_gap": f"{float(gap):+.6f}",
                "market_median_move": (f"{float(control):+.6f}" if control is not None else None),
                "excess_over_market": (
                    f"{float(gap - control):+.6f}" if control is not None else None
                ),
                "candidates_listed_nearby": len(nearby),
                "ranked_candidates": candidates,
            }
            discovered.append(record)

            entitlement = entitlements.get((symbol, ex_date))
            if entitlement is None:
                refused.append(
                    {**record, "reason": "NO_FILING_RATIO"},
                )
                continue

            resulting_bars = bars_by_symbol.get(entitlement.resulting_symbol)
            if not resulting_bars:
                refused.append({**record, "reason": "RESULTING_COMPANY_NOT_IN_CACHE"})
                continue
            first_after = next((b for b in resulting_bars if b.on >= ex_date), None)
            if first_after is None:
                refused.append({**record, "reason": "RESULTING_COMPANY_HAS_NO_BAR_AFTER_EX_DATE"})
                continue

            implied_total = ex_open + entitlement.ratio * first_after.open
            residual = implied_total / cum_close - 1
            if abs(residual) > CONTINUITY_TOLERANCE:
                refused.append(
                    {
                        **record,
                        "reason": "VALUE_CONTINUITY_FAILED",
                        "resulting_symbol": entitlement.resulting_symbol,
                        "resulting_first_open": str(first_after.open),
                        "residual": f"{float(residual):+.6f}",
                    }
                )
                continue

            factor = ex_open / cum_close
            validated.append(
                {
                    "symbol": symbol,
                    "ex_date": ex_date.isoformat(),
                    "factor": str(factor),
                    "evidence": (
                        f"{entitlement.resulting_symbol} first open {first_after.open} on "
                        f"{first_after.on.isoformat()}, entitlement {entitlement.ratio} per share "
                        f"per {entitlement.filing_url}; value continuity residual "
                        f"{float(residual):+.4%} against cum close {cum_close}"
                    ),
                }
            )

    payload = {
        "code_revision": code_revision(),
        "continuity_tolerance": str(CONTINUITY_TOLERANCE),
        "corporate_actions_dir": args.corporate_actions_dir.as_posix(),
        "corporate_actions_authority_sha256": authority_manifest_hash(args.corporate_actions_dir),
        "entitlement_table": args.entitlements.as_posix() if args.entitlements else None,
        "generated_at": datetime.now(UTC).isoformat(),
        "method": "value-continuity against the resulting company's first traded price",
        "ratioless_actions_seen": len(discovered),
        "refused": refused,
        "universe_authority": args.universe.as_posix(),
        "validated": validated,
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")

    args.discovery_out.parent.mkdir(parents=True, exist_ok=True)
    args.discovery_out.write_text(
        json.dumps({"actions": discovered}, indent=2, sort_keys=True), encoding="utf-8"
    )

    print(f"\nratio-less actions : {len(discovered)}")
    print(f"validated          : {len(validated)}")
    print(f"refused            : {len(refused)}")
    reasons: dict[str, int] = {}
    for item in refused:
        reasons[str(item.get("reason"))] = reasons.get(str(item.get("reason")), 0) + 1
    for reason, count in sorted(reasons.items(), key=lambda kv: -kv[1]):
        print(f"  {reason:38} {count}")
    print(f"\nwritten            : {args.out}")
    print(f"worklist           : {args.discovery_out}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--store-root",
        type=Path,
        default=ROOT_DIR / "data/evidence/market-cache/all-market-20160822-20260821/store",
    )
    parser.add_argument(
        "--corporate-actions-dir",
        type=Path,
        default=ROOT_DIR
        / "data/evidence/market-cache/all-market-20160822-20260821/corporate-actions",
    )
    parser.add_argument(
        "--universe",
        type=Path,
        default=ROOT_DIR / "data/authorities/nse-research-universe-liquid-10y.csv",
    )
    parser.add_argument(
        "--entitlements",
        type=Path,
        default=ROOT_DIR / "data/authorities/nse-demerger-entitlements.json",
        help="Filing-sourced entitlement ratios. Actions absent from it are refused, never guessed.",
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=ROOT_DIR / "data/authorities/nse-validated-demerger-factors.json",
    )
    parser.add_argument(
        "--index-cache",
        type=Path,
        default=ROOT_DIR / "reports/corporate_action_validation/store-manifest-index.json",
        help="Cached symbol index over the store's manifest headers. Rebuilt when the dataset "
        "catalog size changes.",
    )
    parser.add_argument(
        "--discovery-out",
        type=Path,
        default=ROOT_DIR / "reports/corporate_action_validation/ratioless-action-worklist.json",
    )
    return run(parser.parse_args())


if __name__ == "__main__":
    raise SystemExit(main())
