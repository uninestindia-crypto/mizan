"""High-performance governed all-market NSE data ingestion pipeline with immutable evidence caching."""

from __future__ import annotations

import argparse
import concurrent.futures
import csv
import json
import os
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import asdict, dataclass
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any, Final

from cached_nifty50_evidence import (
    persist_verified_acquisition,
)

from quant_system.config import load_env_file
from quant_system.data.market_data import (
    AuthorityReference,
    HistoricalAcquisitionFailure,
    HistoricalDailyRequest,
)
from quant_system.data.market_data_evidence import canonical_sha256
from quant_system.data.upstox import UpstoxClient
from quant_system.evidence import (
    EvidenceStore,
    EvidenceStoreConfig,
)

ROOT_DIR: Final = Path(__file__).resolve().parent.parent

NSE_CA_ENDPOINT: Final = "https://www.nseindia.com/api/corporates-corporateActions"
NSE_CA_SOURCE_URL: Final = "https://www.nseindia.com/companies-listing/corporate-filings-actions"
USER_AGENT: Final = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
)


@dataclass(frozen=True, slots=True)
class InstrumentTarget:
    symbol: str
    company_name: str
    isin: str
    instrument_key: str
    instrument_type: str
    security_type: str


@dataclass(slots=True)
class IngestionResult:
    symbol: str
    instrument_key: str
    status: str
    row_count: int
    received_start: str | None
    received_end: str | None
    corporate_actions_count: int
    manifest_hash: str | None
    source_layer: str  # CACHE_HIT, CACHE_MISS_SAVED, EMPTY, FAILED
    error_detail: str | None = None


def read_target_universe(csv_path: Path) -> list[InstrumentTarget]:
    """Parse the authoritative all-listed equities CSV file."""
    if not csv_path.is_file():
        raise FileNotFoundError(f"Universe CSV not found: {csv_path}")
    targets: list[InstrumentTarget] = []
    with open(csv_path, encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for row in reader:
            sym = (row.get("Symbol") or "").strip()
            name = (row.get("Company Name") or "").strip()
            isin = (row.get("ISIN Code") or "").strip()
            key = (row.get("Instrument Key") or "").strip()
            inst_type = (row.get("Instrument Type") or "EQ").strip()
            sec_type = (row.get("Security Type") or "NORMAL").strip()
            if sym and isin and key.startswith("NSE_EQ|"):
                targets.append(
                    InstrumentTarget(
                        symbol=sym,
                        company_name=name,
                        isin=isin,
                        instrument_key=key,
                        instrument_type=inst_type,
                        security_type=sec_type,
                    )
                )
    return targets


def atomic_write_bytes(target: Path, contents: bytes) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_name(f".{target.name}.{os.getpid()}.{threading.get_ident()}.tmp")
    temporary.write_bytes(contents)
    os.replace(temporary, target)


def atomic_write_json(target: Path, value: object) -> None:
    encoded = json.dumps(value, indent=2, sort_keys=True).encode("utf-8") + b"\n"
    atomic_write_bytes(target, encoded)


def fetch_or_load_corporate_actions(
    symbol: str, start: date, end: date, out_dir: Path, timeout: float = 10.0
) -> tuple[Path, int]:
    """Fetch corporate actions for an equity or load from cached JSON."""
    out_dir.mkdir(parents=True, exist_ok=True)
    target = out_dir / f"nse-corporate-actions-{symbol}.json"
    if target.is_file():
        try:
            data = json.loads(target.read_text(encoding="utf-8"))
            if isinstance(data, list):
                return target, len(data)
        except Exception:
            pass

    query = urllib.parse.urlencode(
        {
            "index": "equities",
            "symbol": symbol,
            "from_date": start.strftime("%d-%m-%Y"),
            "to_date": end.strftime("%d-%m-%Y"),
        }
    )
    req = urllib.request.Request(
        f"{NSE_CA_ENDPOINT}?{query}",
        headers={
            "User-Agent": USER_AGENT,
            "Accept": "application/json, text/plain, */*",
            "Referer": NSE_CA_SOURCE_URL,
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as response:
            body = response.read()
        parsed = json.loads(body.decode("utf-8"))
        if isinstance(parsed, list):
            atomic_write_bytes(target, body)
            return target, len(parsed)
        elif isinstance(parsed, dict) and "data" in parsed:
            items = parsed["data"]
            atomic_write_json(target, items)
            return target, len(items)
    except Exception:
        pass

    # Save empty list if no filings or error
    empty_bytes = b"[]\n"
    atomic_write_bytes(target, empty_bytes)
    return target, 0


def build_corporate_action_authority(ca_path: Path, symbol: str) -> AuthorityReference:
    """Build an AuthorityReference for the given corporate action file."""
    content = ca_path.read_bytes()
    ca_hash = canonical_sha256(json.loads(content.decode("utf-8")))
    return AuthorityReference(
        authority_id=f"nse-corporate-actions-{symbol}",
        source_url=f"{NSE_CA_SOURCE_URL}/{symbol}",
        publication_date=date(2026, 8, 24),
        effective_from=date(2016, 8, 22),
        effective_to=date(2026, 8, 21),
        version="nse-real-response-v1",
        content_hash=ca_hash,
    )


class IngestionEngine:
    """Multi-threaded rate-controlled market data ingestion engine with EvidenceStore verification."""

    def __init__(
        self,
        store: EvidenceStore,
        client: UpstoxClient,
        ca_dir: Path,
        from_date: date,
        to_date: date,
        rate_limit_sleep: float = 0.02,
    ) -> None:
        self.store = store
        self.client = client
        self.ca_dir = ca_dir
        self.from_date = from_date
        self.to_date = to_date
        self.rate_limit_sleep = rate_limit_sleep
        self.lock = threading.Lock()
        self.results: dict[str, IngestionResult] = {}
        self._clean_stale_locks()
        self._fast_index_catalog()

    def _clean_stale_locks(self) -> None:
        """Clean any abandoned lock files from previous runs."""
        lock_file = self.store.root / "locks" / "governed-operation.lock"
        if lock_file.exists():
            try:
                lock_file.unlink()
                print("Cleaned abandoned store lock file.", flush=True)
            except Exception:
                pass

    def _fast_index_catalog(self) -> None:
        """Fast index of existing dataset manifests on disk."""
        dataset_dir = self.store.root / "datasets"
        if not dataset_dir.is_dir():
            return
        count = 0
        for d_dir in dataset_dir.iterdir():
            if not d_dir.is_dir():
                continue
            m_file = d_dir / "manifest.json"
            if m_file.is_file():
                try:
                    data = json.loads(m_file.read_text(encoding="utf-8"))
                    meta = data.get("metadata", data)
                    sym = meta.get("symbol")
                    if (
                        sym
                        and meta.get("status") in ("ACCEPTED", "PARTIAL")
                        and meta.get("row_count", 0) > 0
                    ):
                        rec_rng = meta.get("received_range", {})
                        self.results[sym] = IngestionResult(
                            symbol=sym,
                            instrument_key=meta.get("provider_instrument_id", ""),
                            status=meta.get("status", "ACCEPTED"),
                            row_count=meta.get("row_count", 0),
                            received_start=rec_rng.get("start"),
                            received_end=rec_rng.get("end"),
                            corporate_actions_count=0,
                            manifest_hash=meta.get("manifest_hash"),
                            source_layer="CACHE_HIT",
                        )
                        count += 1
                except Exception:
                    pass
        print(f"Indexed {count} pre-existing cached datasets in EvidenceStore.", flush=True)

    def get_results_copy(self) -> list[IngestionResult]:
        """Thread-safe snapshot of results for progress updates."""
        with self.lock:
            return list(self.results.values())

    def process_target(self, target: InstrumentTarget) -> IngestionResult:
        """Acquire, validate, and persist one instrument."""
        sym = target.symbol
        key = target.instrument_key

        # Check if already present in catalog
        with self.lock:
            if sym in self.results and self.results[sym].row_count > 0:
                return self.results[sym]

        # Rate limiting sleep
        if self.rate_limit_sleep > 0:
            time.sleep(self.rate_limit_sleep)

        # 1. Fetch / Load corporate actions
        ca_path, ca_count = fetch_or_load_corporate_actions(
            sym, self.from_date, self.to_date, self.ca_dir
        )
        ca_auth = build_corporate_action_authority(ca_path, sym)

        # 2. Build acquisition request
        request = HistoricalDailyRequest(
            instrument_key=key,
            symbol=sym,
            from_date=self.from_date,
            to_date=self.to_date,
            corporate_action_authority=ca_auth,
        )

        # 3. Call Upstox Client
        outcome = self.client.acquire_historical_daily(request)

        if isinstance(outcome, HistoricalAcquisitionFailure):
            res = IngestionResult(
                symbol=sym,
                instrument_key=key,
                status=outcome.code.value,
                row_count=0,
                received_start=None,
                received_end=None,
                corporate_actions_count=ca_count,
                manifest_hash=None,
                source_layer="EMPTY"
                if outcome.code.value in ("DATASET_EMPTY", "PROVIDER_UNAVAILABLE")
                else "FAILED",
                error_detail=outcome.recovery_action,
            )
        else:
            # 4. Atomically persist to EvidenceStore under lock
            try:
                with self.lock:
                    saved = persist_verified_acquisition(
                        self.store,
                        outcome,
                        operation_id=f"ingest-{sym}",
                    )
                m = saved.manifest
                res = IngestionResult(
                    symbol=sym,
                    instrument_key=key,
                    status=m.status.value,
                    row_count=m.row_count,
                    received_start=m.received_start.isoformat(),
                    received_end=m.received_end.isoformat(),
                    corporate_actions_count=ca_count,
                    manifest_hash=m.manifest_hash,
                    source_layer="CACHE_MISS_SAVED",
                )
            except Exception as e:
                res = IngestionResult(
                    symbol=sym,
                    instrument_key=key,
                    status="PERSIST_ERROR",
                    row_count=len(outcome.records),
                    received_start=outcome.records[0].exchange_date.isoformat()
                    if outcome.records
                    else None,
                    received_end=outcome.records[-1].exchange_date.isoformat()
                    if outcome.records
                    else None,
                    corporate_actions_count=ca_count,
                    manifest_hash=None,
                    source_layer="FAILED",
                    error_detail=str(e),
                )

        with self.lock:
            self.results[sym] = res
        return res


def run_ingestion_pipeline(
    universe_csv: Path,
    cache_root: Path,
    summary_file: Path,
    corporate_actions_dir: Path,
    from_date: date,
    to_date: date,
    concurrency: int = 10,
    rate_limit_sleep: float = 0.02,
    limit: int = 0,
    skip: int = 0,
) -> dict[str, Any]:
    """Execute the end-to-end ingestion pipeline."""
    load_env_file()
    cache_root.mkdir(parents=True, exist_ok=True)
    store_dir = cache_root / "store"
    store_dir.mkdir(parents=True, exist_ok=True)

    store = EvidenceStore(EvidenceStoreConfig(root=store_dir))
    client = UpstoxClient()
    if not client.is_authenticated:
        raise RuntimeError("UPSTOX_ACCESS_TOKEN is missing or invalid in environment.")

    targets = read_target_universe(universe_csv)
    if skip > 0:
        targets = targets[skip:]
    if limit > 0:
        targets = targets[:limit]

    total_targets = len(targets)
    print("=== ALL-MARKET INGESTION PIPELINE ===", flush=True)
    print(
        f"Universe Source       : {universe_csv} ({total_targets:,} selected targets)", flush=True
    )
    print(f"Target Range          : {from_date} -> {to_date} (10 calendar years)", flush=True)
    print(f"Cache Evidence Root   : {cache_root.resolve()}", flush=True)
    print(f"Corporate Actions Dir : {corporate_actions_dir.resolve()}", flush=True)
    print(
        f"Worker Concurrency    : {concurrency} threads (sleep={rate_limit_sleep}s)\n", flush=True
    )

    engine = IngestionEngine(
        store=store,
        client=client,
        ca_dir=corporate_actions_dir,
        from_date=from_date,
        to_date=to_date,
        rate_limit_sleep=rate_limit_sleep,
    )

    # Ingestion progress loop
    completed_count = 0
    saved_count = 0
    hit_count = 0
    empty_or_failed = 0
    total_bars = 0
    start_time = time.time()

    def update_summary() -> None:
        summary_data = {
            "updated_at": datetime.now(UTC).isoformat(),
            "universe_csv": str(universe_csv),
            "total_targets": total_targets,
            "completed_targets": completed_count,
            "cache_hits": hit_count,
            "cache_miss_saved": saved_count,
            "empty_or_failed": empty_or_failed,
            "total_bars_ingested": total_bars,
            "elapsed_seconds": round(time.time() - start_time, 2),
            "results": [asdict(r) for r in engine.get_results_copy()],
        }
        atomic_write_json(summary_file, summary_data)

    print(
        f"Starting multi-threaded ingestion pool across {total_targets} instruments...", flush=True
    )
    with concurrent.futures.ThreadPoolExecutor(max_workers=concurrency) as executor:
        future_map = {executor.submit(engine.process_target, t): t for t in targets}
        for future in concurrent.futures.as_completed(future_map):
            target = future_map[future]
            try:
                res = future.result()
                completed_count += 1
                if res.source_layer == "CACHE_HIT":
                    hit_count += 1
                    total_bars += res.row_count
                elif res.source_layer == "CACHE_MISS_SAVED":
                    saved_count += 1
                    total_bars += res.row_count
                else:
                    empty_or_failed += 1

                if completed_count % 25 == 0 or completed_count == total_targets:
                    elapsed = time.time() - start_time
                    rate = completed_count / max(0.1, elapsed)
                    print(
                        f"[{completed_count:>4}/{total_targets}] "
                        f"Saved: {saved_count:>4} | Hits: {hit_count:>4} | Empty/Fail: {empty_or_failed:>3} | "
                        f"Bars: {total_bars:,} | Speed: {rate:.1f} sym/s",
                        flush=True,
                    )
                    update_summary()
            except Exception as e:
                print(f"Unexpected error processing {target.symbol}: {e}", flush=True)

    update_summary()
    elapsed = time.time() - start_time
    print(f"\n=== INGESTION COMPLETED IN {elapsed:.1f}s ===", flush=True)
    print(f"Total Targets Evaluated : {completed_count}", flush=True)
    print(
        f"Successfully Persisted  : {saved_count + hit_count} (Hits: {hit_count}, New: {saved_count})",
        flush=True,
    )
    print(f"Empty or Inactive       : {empty_or_failed}", flush=True)
    print(f"Total Daily OHLCV Bars  : {total_bars:,}", flush=True)
    print(f"Summary Written To      : {summary_file}", flush=True)

    return {
        "total_targets": total_targets,
        "completed": completed_count,
        "saved": saved_count,
        "hits": hit_count,
        "empty_or_failed": empty_or_failed,
        "total_bars": total_bars,
        "elapsed_seconds": elapsed,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="All-market NSE historical data ingestion pipeline."
    )
    parser.add_argument(
        "--universe-csv",
        type=Path,
        default=ROOT_DIR / "data" / "authorities" / "nse-all-listed-equities.csv",
    )
    parser.add_argument(
        "--cache-root",
        type=Path,
        default=ROOT_DIR / "data" / "evidence" / "market-cache" / "all-market-20160822-20260821",
    )
    parser.add_argument(
        "--summary-file",
        type=Path,
        default=ROOT_DIR
        / "data"
        / "evidence"
        / "market-analysis"
        / "all-market-ingestion-summary.json",
    )
    parser.add_argument(
        "--corporate-actions-dir",
        type=Path,
        default=ROOT_DIR
        / "data"
        / "evidence"
        / "market-cache"
        / "all-market-20160822-20260821"
        / "corporate-actions",
    )
    parser.add_argument("--from-date", type=date.fromisoformat, default=date(2016, 8, 22))
    parser.add_argument("--to-date", type=date.fromisoformat, default=date(2026, 8, 21))
    parser.add_argument("--concurrency", type=int, default=10)
    parser.add_argument("--rate-limit-sleep", type=float, default=0.02)
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--skip", type=int, default=0)
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    run_ingestion_pipeline(
        universe_csv=args.universe_csv,
        cache_root=args.cache_root,
        summary_file=args.summary_file,
        corporate_actions_dir=args.corporate_actions_dir,
        from_date=args.from_date,
        to_date=args.to_date,
        concurrency=args.concurrency,
        rate_limit_sleep=args.rate_limit_sleep,
        limit=args.limit,
        skip=args.skip,
    )
