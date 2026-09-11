"""Build the Mizan pooled cross-sectional feature store from the all-market cache.

This does not consume ``data/evidence/feature-store/multidim_feature_store.csv``. That artifact
double-counts: the all-market store holds two DATASET resources for 55 symbols, and the builder
appended rows once per dataset, so 111,941 of its 246,554 (date, symbol) pairs appear twice. Rows
here are deduplicated by symbol before any feature is computed.

Every feature uses trailing or same-bar-close information only. Forward columns are not computed at
all -- labels come from the governed cost-aware path, not from a forward close.
"""

from __future__ import annotations

import argparse
import csv
import gc
import gzip
import hashlib
import json
import math
import subprocess
import sys
from collections import defaultdict
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR / "scripts"))
sys.path.insert(0, str(ROOT_DIR / "src"))

from cached_nifty50_evidence import historical_acquisition_from_verified  # noqa: E402

from quant_system.data.adjustment_provenance import (  # noqa: E402
    ADJUSTMENT_METHOD_V1,
    ADJUSTMENT_METHOD_VERSION_V1,
)
from quant_system.data.corporate_actions import (  # noqa: E402
    AdjustmentPlan,
    BarPoint,
    ValidatedFactor,
    adjust_bars,
    build_adjustment_factors,
)
from quant_system.evidence import (  # noqa: E402
    EvidenceResourceType,
    EvidenceStore,
    EvidenceStoreConfig,
)
from quant_system.modeling.rows import FEATURE_NAMES_V3  # noqa: E402

_MONTHS = ("Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec")

WARMUP_BARS = 50
"""Longest trailing window any feature needs (the 50-session moving average)."""


def wilder_rsi(closes: list[float], period: int = 14) -> list[float]:
    """Wilder RSI. Index i is a function of closes[: i + 1] and nothing later."""
    out = [50.0] * len(closes)
    if len(closes) <= period:
        return out
    gains = losses = 0.0
    for i in range(1, period + 1):
        change = closes[i] - closes[i - 1]
        gains += max(change, 0.0)
        losses += max(-change, 0.0)
    avg_gain, avg_loss = gains / period, losses / period
    for i in range(period, len(closes)):
        if i > period:
            change = closes[i] - closes[i - 1]
            avg_gain = (avg_gain * (period - 1) + max(change, 0.0)) / period
            avg_loss = (avg_loss * (period - 1) + max(-change, 0.0)) / period
        if avg_loss == 0.0:
            out[i] = 100.0 if avg_gain > 0.0 else 50.0
        else:
            out[i] = 100.0 - 100.0 / (1.0 + avg_gain / avg_loss)
    return out


def read_universe(path: Path) -> dict[str, str]:
    """Symbol to instrument key, from the declared research universe authority."""
    universe: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.startswith("#") or line.startswith("Symbol") or not line.strip():
            continue
        parts = line.split(",")
        if len(parts) >= 3:
            universe[parts[0].strip()] = parts[2].strip()
    return universe


def load_macro(macro_dir: Path, name: str) -> dict[str, float]:
    path = macro_dir / f"macro_{name}.json"
    if not path.is_file():
        return {}
    payload = json.loads(path.read_text(encoding="utf-8"))
    return {candle[0][:10]: float(candle[4]) for candle in payload.get("candles", [])}


def deduplicate_by_symbol(store: EvidenceStore) -> dict[str, Any]:
    """One acquisition per symbol: longest history, ties broken by instrument id.

    55 symbols in the all-market cache carry two DATASET resources. Keeping both is exactly what
    double-counted the previous feature store.

    Loads and holds **every** instrument in the cache. Prefer :func:`selected_acquisitions` when only
    a declared universe is needed -- this one reconstructs 3,322 acquisitions to keep 423 of them,
    which on a 16 GB machine is both slow and close to the memory ceiling.
    """
    best: dict[str, Any] = {}
    for verified in store.list_verified(EvidenceResourceType.DATASET):
        acquisition = historical_acquisition_from_verified(verified)
        symbol = acquisition.manifest.symbol
        incumbent = best.get(symbol)
        if incumbent is None or (
            len(acquisition.records),
            acquisition.manifest.provider_instrument_id,
        ) > (len(incumbent.records), incumbent.manifest.provider_instrument_id):
            best[symbol] = acquisition
    return best


def selected_acquisitions(
    store: EvidenceStore, symbols: set[str], dataset_ids: dict[str, str]
) -> dict[str, Any]:
    """One acquisition per requested symbol, opening no other dataset.

    ``dataset_ids`` comes from :func:`manifest_index`, which picks the same dataset
    :func:`deduplicate_by_symbol` would -- longest history, ties broken by provider instrument id --
    from manifest headers alone. So this selects identically while touching ~8x less of the store.

    Each dataset is still opened through ``open_verified``, so integrity checking is not skipped;
    only the datasets outside the declared universe are never read.
    """
    found: dict[str, Any] = {}
    for index, symbol in enumerate(sorted(symbols), 1):
        dataset_id = dataset_ids.get(symbol)
        if dataset_id is None:
            continue
        verified = store.open_verified(EvidenceResourceType.DATASET, dataset_id)
        found[symbol] = historical_acquisition_from_verified(verified)
        if index % 100 == 0:
            print(f"  loaded {index}/{len(symbols)} acquisitions", flush=True)
            gc.collect()
    return found


def _parse_ex_date(value: object) -> date | None:
    """NSE publishes ex-dates as ``07-Sep-2026``."""
    try:
        day, month, year = str(value).split("-")
        return date(int(year), _MONTHS.index(month) + 1, int(day))
    except Exception:
        return None


def load_corporate_actions(ca_dir: Path, symbol: str) -> list[tuple[date, str]]:
    """``(ex_date, subject)`` records for one symbol, or an empty list when there are none."""
    path = ca_dir / f"nse-corporate-actions-{symbol}.json"
    if not path.is_file():
        return []
    try:
        items = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return []
    out: list[tuple[date, str]] = []
    for item in items if isinstance(items, list) else []:
        ex_date = _parse_ex_date(item.get("exDate"))
        if ex_date is not None:
            out.append((ex_date, str(item.get("subject", ""))))
    return out


def manifest_index(store_root: Path, cache_path: Path) -> tuple[dict[str, date], dict[str, str]]:
    """The header index, cached to disk so it is built once rather than on every run.

    The caching is not just a speed optimisation, it is what makes the run survive. Parsing 3,322
    manifest documents (~122 KB each) and then asking for the large contiguous allocations that
    ``canonical_sha256`` needs, in the same process, exhausts this machine -- the run died with
    ``MemoryError`` inside ``json.dumps`` on the *first* bar load, after the header scan had churned
    the allocator. Doing the scan once and reading a small JSON file thereafter keeps the two phases
    from competing.

    The cache is rebuilt whenever the dataset catalog has more entries than the cache describes, so
    a newly ingested instrument is never silently missed.
    """
    catalog_size = sum(1 for _ in (store_root / "datasets").iterdir())
    if cache_path.is_file():
        try:
            payload = json.loads(cache_path.read_text(encoding="utf-8"))
            if int(payload.get("catalog_size", -1)) == catalog_size:
                return (
                    {s: date.fromisoformat(v) for s, v in payload["first_traded"].items()},
                    dict(payload["dataset_ids"]),
                )
        except (OSError, ValueError, KeyError, TypeError):
            pass  # a damaged cache is rebuilt, never trusted

    starts, dataset_ids = scan_manifest_headers(store_root)
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    cache_path.write_text(
        json.dumps(
            {
                "catalog_size": catalog_size,
                "dataset_ids": dataset_ids,
                "first_traded": {s: v.isoformat() for s, v in starts.items()},
                "store_root": store_root.as_posix(),
            },
            indent=0,
            sort_keys=True,
        ),
        encoding="utf-8",
    )
    gc.collect()
    return starts, dataset_ids


def scan_manifest_headers(store_root: Path) -> tuple[dict[str, date], dict[str, str]]:
    """Listing dates and the best dataset id per symbol, from manifest **headers** only.

    Reconstructing all 3,322 acquisitions is what killed two earlier runs of this script:
    ``historical_acquisition_from_verified`` rehashes every record through ``canonical_sha256``, and
    the attempts died with ``MemoryError`` inside ``json.dumps``. Everything needed to *choose* which
    datasets to open is already in the manifest headers, which are small and cheap to read.

    Returns:
        - first traded session per symbol. Where a symbol has two DATASET resources -- 55 do -- the
          **earlier** start wins, because the question is "when did this instrument first trade".
        - the dataset id to open per symbol, chosen by **longest** history with ties broken by
          provider instrument id. That is the same dedup rule as the feature-store builder, so this
          script cannot select a different dataset than the builder would.
    """
    starts: dict[str, date] = {}
    best: dict[str, tuple[int, str, str]] = {}
    for directory in sorted((store_root / "datasets").iterdir()):
        manifest_path = directory / "manifest.json"
        if not manifest_path.is_file():
            continue
        block = _find_dataset_block(json.loads(manifest_path.read_text(encoding="utf-8")))
        if block is None:
            continue
        try:
            symbol = str(block["symbol"])
            start = date.fromisoformat(str(block["received_range"]["start"]))
            rows = int(block["row_count"])
            instrument = str(block.get("provider_instrument_id", ""))
        except (KeyError, TypeError, ValueError):
            continue
        incumbent_start = starts.get(symbol)
        if incumbent_start is None or start < incumbent_start:
            starts[symbol] = start
        candidate = (rows, instrument, directory.name)
        if symbol not in best or candidate > best[symbol]:
            best[symbol] = candidate
    return starts, {symbol: entry[2] for symbol, entry in best.items()}


def _find_dataset_block(node: object) -> dict[str, Any] | None:
    """The dataset-manifest payload nested inside an evidence manifest."""
    if isinstance(node, dict):
        if "symbol" in node and "received_range" in node:
            return node
        for value in node.values():
            block = _find_dataset_block(value)
            if block is not None:
                return block
    elif isinstance(node, list):
        for value in node:
            block = _find_dataset_block(value)
            if block is not None:
                return block
    return None


def code_revision() -> str:
    """The exact revision that produced this artifact, with a dirty marker when it is not clean.

    A derived dataset that cannot name the code that made it is not reproducible, and
    ``quant-model-governance`` treats the code revision as part of the artifact's identity. An
    uncommitted tree is recorded as such rather than silently reported as its parent commit.
    """
    try:
        head = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=ROOT_DIR,
            capture_output=True,
            text=True,
            check=True,
            timeout=30,
        ).stdout.strip()
        dirty = subprocess.run(
            ["git", "status", "--porcelain", "--", "src", "scripts"],
            cwd=ROOT_DIR,
            capture_output=True,
            text=True,
            check=True,
            timeout=60,
        ).stdout.strip()
    except (OSError, subprocess.SubprocessError):
        return "UNKNOWN"
    return f"{head}-dirty" if dirty else head


def authority_manifest_hash(corporate_actions_dir: Path | None) -> str | None:
    """One hash over every corporate-action authority file consumed.

    Binds *which* authority snapshot produced these factors. Refetching the authorities changes
    this, so two feature stores built either side of a refetch cannot be mistaken for each other.
    """
    if corporate_actions_dir is None or not corporate_actions_dir.is_dir():
        return None
    digest = hashlib.sha256()
    for path in sorted(corporate_actions_dir.glob("nse-corporate-actions-*.json")):
        digest.update(path.name.encode("utf-8"))
        digest.update(hashlib.sha256(path.read_bytes()).digest())
    return digest.hexdigest()


def load_validated_demerger_factors(
    path: Path | None,
) -> dict[str, dict[date, ValidatedFactor]]:
    """Independently validated demerger factors, keyed by symbol then ex-date.

    Produced by ``scripts/validate_demerger_factors.py``, which sizes an action from the resulting
    company's own first traded price and the entitlement ratio in the company filing -- evidence
    outside the parent's ex-date gap. Without such a file every ratio-less action stays unresolved,
    which is the safe default rather than a degraded one.
    """
    if path is None or not path.is_file():
        return {}
    payload = json.loads(path.read_text(encoding="utf-8"))
    out: dict[str, dict[date, ValidatedFactor]] = {}
    for entry in payload.get("validated", []):
        ex_date = date.fromisoformat(str(entry["ex_date"]))
        out.setdefault(str(entry["symbol"]), {})[ex_date] = ValidatedFactor(
            Decimal(str(entry["factor"])), str(entry["evidence"])
        )
    return out


def raw_bar_points(acquisition: Any) -> list[BarPoint]:
    """The provider's own bars, ascending. Never mutated -- these are what a fill executes at."""
    return sorted(
        (
            BarPoint(
                on=record.exchange_date,
                open=Decimal(str(record.open)),
                high=Decimal(str(record.high)),
                low=Decimal(str(record.low)),
                close=Decimal(str(record.close)),
                volume=int(record.volume),
            )
            for record in acquisition.records
        ),
        key=lambda bar: bar.on,
    )


def adjusted_bar_points(
    acquisition: Any,
    actions: list[tuple[date, str]],
    *,
    total_return: bool,
    validated_factors: dict[date, ValidatedFactor] | None = None,
) -> tuple[list[BarPoint], AdjustmentPlan]:
    """Back-adjusted bars for one instrument, with the plan that produced them.

    Most of what the authority publishes needs no correction: the provider already back-adjusts
    every published-ratio split and bonus (212 of 212 measured). What it leaves behind is demergers,
    which carry no published ratio -- and those are *not* sized from the ex-date gap, because a gap
    is the action plus the day's market movement and nothing separates the two. They come back in
    ``plan.unresolved``, and the caller drops every feature window that touches one.

    Adjusting here rather than at read time keeps one definition of a return for every feature that
    follows.
    """
    bars = raw_bar_points(acquisition)
    if not actions:
        return bars, AdjustmentPlan((), (), ())
    plan = build_adjustment_factors(
        actions, bars, total_return=total_return, validated_factors=validated_factors
    )
    return adjust_bars(bars, plan.factors), plan


def blackout_dates(
    bars: list[BarPoint], plan: AdjustmentPlan, *, window: int = WARMUP_BARS
) -> set[date]:
    """Session dates whose trailing feature window contains an action of unknown size.

    A feature at session ``t`` reads bars ``(t - WARMUP_BARS, t]``. An unresolved corporate action
    inside that window puts a fabricated return into every one of RSI, both moving averages, all
    three momentum features and the volume z-score. The value is not merely noisy, it is an artifact
    of an event nobody has sized -- and it looks like signal, which is worse.

    So those rows are dropped rather than published with a caveat. Measured on the research
    universe this costs about 54 events x 50 sessions out of roughly a million rows.
    """
    if not plan.unresolved:
        return set()
    ordered = [bar.on for bar in bars]
    positions = {value: index for index, value in enumerate(ordered)}
    blocked: set[date] = set()
    for action in plan.unresolved:
        start = positions.get(action.ex_date)
        if start is None:
            # No bar on the ex-date. The gap still lands between the surrounding sessions, so
            # blacked out from the first session on or after it.
            start = next((i for i, value in enumerate(ordered) if value >= action.ex_date), None)
            if start is None:
                continue
        blocked.update(ordered[start : start + window + 1])
    return blocked


def _instrument_rows(
    symbol: str,
    bars: list[BarPoint],
    vix_by_date: dict[str, float],
    nifty_by_date: dict[str, float],
    blackout: set[date] | None = None,
) -> list[tuple[str, str, list[float]]]:
    """Causal feature rows for one instrument, before cross-sectional ranking.

    ``blackout`` names sessions whose trailing window spans a corporate action of unknown size; no
    row is emitted for those. See :func:`blackout_dates`.
    """
    records = bars
    blocked = blackout or set()
    dates = [record.on.isoformat() for record in records]
    opens = [float(record.open) for record in records]
    highs = [float(record.high) for record in records]
    lows = [float(record.low) for record in records]
    closes = [float(record.close) for record in records]
    volumes = [float(record.volume) for record in records]
    rsi = wilder_rsi(closes)

    rows: list[tuple[str, str, list[float]]] = []
    for i in range(WARMUP_BARS, len(records)):
        if records[i].on in blocked:
            continue
        close, open_, high, low = closes[i], opens[i], highs[i], lows[i]
        if close <= 0 or open_ <= 0 or high <= 0 or low <= 0:
            continue
        on = dates[i]
        vix = vix_by_date.get(on)
        vix_past = vix_by_date.get(dates[i - 5])
        nifty = nifty_by_date.get(on)
        nifty_past = nifty_by_date.get(dates[i - 5])
        if vix is None or vix_past is None or nifty is None or nifty_past is None:
            continue

        log_hl = math.log(high / low)
        log_co = math.log(close / open_)
        sma_20 = sum(closes[i - 20 : i]) / 20.0
        sma_50 = sum(closes[i - 50 : i]) / 50.0
        window = volumes[i - 20 : i]
        mean_volume = sum(window) / 20.0
        std_volume = math.sqrt(sum((v - mean_volume) ** 2 for v in window) / 20.0)
        hl_range = high - low

        rows.append(
            (
                on,
                symbol,
                [
                    close / closes[i - 1] - 1.0 if closes[i - 1] > 0 else 0.0,
                    close / closes[i - 5] - 1.0 if closes[i - 5] > 0 else 0.0,
                    close / closes[i - 21] - 1.0 if closes[i - 21] > 0 else 0.0,
                    math.sqrt(max(0.0, 0.5 * log_hl**2 - (2.0 * math.log(2.0) - 1.0) * log_co**2)),
                    log_hl / math.sqrt(4.0 * math.log(2.0)),
                    rsi[i] / 100.0 - 0.5,
                    close / sma_20 - 1.0 if sma_20 > 0 else 0.0,
                    close / sma_50 - 1.0 if sma_50 > 0 else 0.0,
                    (volumes[i] - mean_volume) / max(1.0, std_volume),
                    ((close - low) - (high - close)) / hl_range if hl_range > 1e-9 else 0.0,
                    vix / 100.0,
                    vix / vix_past - 1.0 if vix_past > 0 else 0.0,
                    nifty / nifty_past - 1.0 if nifty_past > 0 else 0.0,
                    0.0,  # cs_rank_momentum_5, filled once the cross-section is complete
                    0.0,  # cs_rank_volume_surprise, likewise
                ],
            )
        )
    return rows


def _apply_cross_sectional_ranks(by_date: dict[str, list[tuple[str, list[float]]]]) -> None:
    """Rank each instrument against that date's cross-section, centred on zero.

    Uses only contemporaneous information: every row being ranked shares one decision date.
    """
    momentum = FEATURE_NAMES_V3.index("return_5")
    volume = FEATURE_NAMES_V3.index("volume_zscore")
    rank_momentum = FEATURE_NAMES_V3.index("cs_rank_momentum_5")
    rank_volume = FEATURE_NAMES_V3.index("cs_rank_volume_surprise")
    for rows in by_date.values():
        count = len(rows)
        for source, target in ((momentum, rank_momentum), (volume, rank_volume)):
            order = sorted(range(count), key=lambda k: rows[k][1][source])
            for rank, position in enumerate(order):
                rows[position][1][target] = (rank + 1) / count - 0.5


def build(
    store_root: Path,
    macro_dir: Path,
    universe_path: Path,
    out_dir: Path,
    *,
    corporate_actions_dir: Path | None = None,
    total_return: bool = True,
    validated_factors_path: Path | None = None,
    index_cache: Path | None = None,
) -> None:
    universe = read_universe(universe_path)
    vix_by_date = load_macro(macro_dir, "INDIAVIX")
    nifty_by_date = load_macro(macro_dir, "NIFTY50")
    print(f"universe        : {len(universe)} names", flush=True)
    print(f"macro           : VIX {len(vix_by_date)}d, NIFTY {len(nifty_by_date)}d", flush=True)

    cache_path = index_cache or (
        ROOT_DIR / "reports/corporate_action_validation/store-manifest-index.json"
    )
    _, dataset_ids = manifest_index(store_root, cache_path)
    print(f"catalog index   : {len(dataset_ids)} symbols (manifest headers only)", flush=True)

    store = EvidenceStore(EvidenceStoreConfig(root=store_root))
    selected = selected_acquisitions(store, set(universe), dataset_ids)
    print(f"in universe     : {len(selected)} of {len(universe)} symbols loaded", flush=True)

    validated = load_validated_demerger_factors(validated_factors_path)
    if validated:
        print(
            f"validated CA    : {sum(len(v) for v in validated.values())} independently validated "
            f"demerger factors across {len(validated)} symbols",
            flush=True,
        )

    by_date: dict[str, list[tuple[str, list[float]]]] = defaultdict(list)
    skipped = 0
    adjusted_symbols = 0
    total_factors = 0
    unresolved_actions = 0
    blacked_out_rows = 0
    unresolved_symbols: set[str] = set()
    refused: list[str] = []
    for symbol, acquisition in sorted(selected.items()):
        if len(acquisition.records) < WARMUP_BARS + 30:
            skipped += 1
            continue
        actions = (
            load_corporate_actions(corporate_actions_dir, symbol)
            if corporate_actions_dir is not None
            else []
        )
        bars, plan = adjusted_bar_points(
            acquisition,
            actions,
            total_return=total_return,
            validated_factors=validated.get(symbol),
        )
        if plan.factors:
            adjusted_symbols += 1
            total_factors += len(plan.factors)
        if plan.unresolved:
            unresolved_actions += len(plan.unresolved)
            unresolved_symbols.add(symbol)
        refused.extend(f"{symbol} {item.ex_date} {item.reason}" for item in plan.unresolved)
        blocked = blackout_dates(bars, plan)
        blacked_out_rows += len(blocked)
        for row_date, name, values in _instrument_rows(
            symbol, bars, vix_by_date, nifty_by_date, blocked
        ):
            by_date[row_date].append((name, values))
    print(f"skipped (short) : {skipped}", flush=True)
    if corporate_actions_dir is None:
        print("corp actions    : DISABLED -- bars are RAW", flush=True)
    else:
        basis = "total return (dividends removed)" if total_return else "price return"
        print(
            f"corp actions    : {total_factors:,} factors on {adjusted_symbols} symbols", flush=True
        )
        print(f"adjustment basis: {basis}", flush=True)
        print(
            f"unresolved      : {unresolved_actions} actions on {len(unresolved_symbols)} symbols; "
            f"up to {blacked_out_rows:,} feature rows blacked out",
            flush=True,
        )

    _apply_cross_sectional_ranks(by_date)

    out_dir.mkdir(parents=True, exist_ok=True)
    csv_path = out_dir / "mizan_feature_store.csv.gz"
    total = 0
    symbols: set[str] = set()
    with gzip.open(csv_path, "wt", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(["date", "symbol", *FEATURE_NAMES_V3])
        for date in sorted(by_date):
            for symbol, values in sorted(by_date[date]):
                writer.writerow([date, symbol, *(f"{value:.10f}" for value in values)])
                symbols.add(symbol)
                total += 1

    metadata = {
        # Adjustment provenance. A store built on RAW bars and one built on adjusted bars are not
        # comparable evidence, so which one this is must travel with the artifact.
        "corporate_action_adjustment": {
            "applied": corporate_actions_dir is not None,
            "authority_dir": (
                corporate_actions_dir.as_posix() if corporate_actions_dir is not None else None
            ),
            "authority_manifest_sha256": authority_manifest_hash(corporate_actions_dir),
            "basis": "TOTAL_RETURN" if total_return else "PRICE_RETURN",
            "blacked_out_session_rows": blacked_out_rows,
            "code_revision": code_revision(),
            "factors_applied": total_factors,
            "method": ADJUSTMENT_METHOD_V1,
            "method_version": ADJUSTMENT_METHOD_VERSION_V1,
            "status": "RAW" if corporate_actions_dir is None else "ADJUSTED",
            "symbols_adjusted": adjusted_symbols,
            "symbols_with_unresolved_actions": len(unresolved_symbols),
            "unresolved_actions": unresolved_actions,
            "validated_demerger_factors": sum(len(v) for v in validated.values()),
            "validated_factors_authority": (
                validated_factors_path.as_posix() if validated_factors_path else None
            ),
        },
        "cross_sectional_dates": len(by_date),
        "catalog_symbols": len(dataset_ids),
        "feature_names": list(FEATURE_NAMES_V3),
        "feature_schema_id": "quantos.mizan_crosssectional_fifteen",
        "feature_schema_version": 1,
        "generated_at": datetime.now(UTC).isoformat(),
        "symbols": len(symbols),
        "total_rows": total,
        "universe_authority": universe_path.as_posix(),
        "warmup_bars": WARMUP_BARS,
    }
    (out_dir / "mizan_feature_store_metadata.json").write_text(
        json.dumps(metadata, indent=2, sort_keys=True), encoding="utf-8"
    )
    print(f"rows            : {total:,}", flush=True)
    print(f"symbols         : {len(symbols)}", flush=True)
    print(f"dates           : {len(by_date):,}", flush=True)
    print(f"written         : {csv_path}", flush=True)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--store-root",
        type=Path,
        default=ROOT_DIR / "data/evidence/market-cache/all-market-20160822-20260821/store",
    )
    parser.add_argument(
        "--macro-dir",
        type=Path,
        default=ROOT_DIR / "data/evidence/market-cache/macro-regimes-20160822-20260821",
    )
    parser.add_argument(
        "--universe",
        type=Path,
        default=ROOT_DIR / "data/authorities/nse-research-universe-liquid-10y.csv",
    )
    parser.add_argument(
        "--out-dir", type=Path, default=ROOT_DIR / "data/evidence/feature-store/mizan"
    )
    parser.add_argument(
        "--corporate-actions-dir",
        type=Path,
        default=ROOT_DIR
        / "data/evidence/market-cache/all-market-20160822-20260821/corporate-actions",
        help="Authority directory used to back-adjust bars. Must match --store-root's cache.",
    )
    parser.add_argument(
        "--validated-factors",
        type=Path,
        default=ROOT_DIR / "data/authorities/nse-validated-demerger-factors.json",
        help="Independently validated demerger factors from validate_demerger_factors.py. "
        "Ratio-less actions absent from this file stay unresolved and their windows are dropped.",
    )
    parser.add_argument(
        "--no-adjust",
        action="store_true",
        help="Build on RAW bars, reproducing the pre-adjustment store. Diagnostic only.",
    )
    parser.add_argument(
        "--price-return",
        action="store_true",
        help="Adjust structural actions only, leaving dividends as price drops. "
        "The default is total return, which also removes dividends.",
    )
    args = parser.parse_args()
    build(
        args.store_root,
        args.macro_dir,
        args.universe,
        args.out_dir,
        corporate_actions_dir=None if args.no_adjust else args.corporate_actions_dir,
        total_return=not args.price_return,
        validated_factors_path=None if args.no_adjust else args.validated_factors,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
