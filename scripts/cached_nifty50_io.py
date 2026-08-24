"""Durable authority, corporate-action, and summary I/O for the cached campaign."""

from __future__ import annotations

import argparse
import csv
import json
import os
import shutil
import sys
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Sequence
from dataclasses import asdict, dataclass
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Final

sys.path.insert(0, str(Path(__file__).resolve().parent))

import run_governed_ridge_training as runner  # noqa: E402
import run_universe_ridge_campaign as universe_runner  # noqa: E402
from cached_nifty50_costs import (  # noqa: E402
    RESEARCH_COST_POLICY,
    RESEARCH_COST_POLICY_HASH,
    RESEARCH_COST_POLICY_ID,
)

from quant_system.evidence import EvidenceIntegrityError  # noqa: E402

NSE_CA_ENDPOINT: Final = "https://www.nseindia.com/api/corporates-corporateActions"
NSE_CA_SOURCE_URL: Final = "https://www.nseindia.com/companies-listing/corporate-filings-actions"
USER_AGENT: Final = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
)


@dataclass(frozen=True, slots=True)
class UniverseSelection:
    selected: tuple[tuple[str, str], ...]
    authority_members: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class CampaignOutput:
    args: object
    universe_count: int


@dataclass(slots=True)
class CampaignProgress:
    results: list[universe_runner.InstrumentResult]
    ordinal: int
    total: int


def select_constituents(
    constituents: tuple[tuple[str, str], ...], *, skip: int, limit: int
) -> UniverseSelection:
    """Select work while keeping the authority bound to all original constituents."""
    if skip < 0 or limit < 0:
        raise ValueError("skip and limit must be non-negative")
    selected = constituents[skip:]
    if limit:
        selected = selected[:limit]
    return UniverseSelection(
        selected=selected,
        authority_members=tuple(sorted(key for _, key in constituents)),
    )


def read_universe(csv_path: Path) -> tuple[tuple[str, str], ...]:
    rows = list(csv.DictReader(csv_path.read_text(encoding="utf-8-sig").splitlines()))
    members = []
    for row in rows:
        symbol = (row.get("Symbol") or "").strip()
        isin = (row.get("ISIN Code") or "").strip()
        if symbol and isin:
            members.append((symbol, f"NSE_EQ|{isin}"))
    result = tuple(sorted(set(members)))
    if not result:
        raise runner.ConfigurationRefused(f"no constituents parsed from {csv_path}")
    return result


def atomic_write_bytes(target: Path, contents: bytes) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_name(f".{target.name}.{os.getpid()}.tmp")
    temporary.write_bytes(contents)
    os.replace(temporary, target)


def atomic_write_json(target: Path, value: object) -> None:
    encoded = json.dumps(value, indent=2, sort_keys=True).encode("utf-8") + b"\n"
    atomic_write_bytes(target, encoded)


def _load_corporate_actions(path: Path) -> list[object]:
    try:
        parsed = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise EvidenceIntegrityError(f"corporate-action cache is invalid: {path}") from error
    if not isinstance(parsed, list):
        raise EvidenceIntegrityError(f"corporate-action cache is not an NSE list: {path}")
    return parsed


def _corporate_action_request(symbol: str, start: date, end: date) -> urllib.request.Request:
    query = urllib.parse.urlencode(
        {
            "index": "equities",
            "symbol": symbol,
            "from_date": start.strftime("%d-%m-%Y"),
            "to_date": end.strftime("%d-%m-%Y"),
        }
    )
    return urllib.request.Request(  # noqa: S310 - fixed HTTPS NSE host
        f"{NSE_CA_ENDPOINT}?{query}",
        headers={
            "User-Agent": USER_AGENT,
            "Accept": "application/json, text/plain, */*",
            "Referer": NSE_CA_SOURCE_URL,
        },
    )


def fetch_or_load_corporate_actions(
    symbol: str, start: date, end: date, out_dir: Path
) -> tuple[Path, str]:
    target = out_dir / f"nse-corporate-actions-{symbol}.json"
    if target.is_file():
        _load_corporate_actions(target)
        return target, "CACHE_HIT"
    request = _corporate_action_request(symbol, start, end)
    try:
        with urllib.request.urlopen(request, timeout=45) as response:  # noqa: S310
            body = response.read()
    except (urllib.error.URLError, TimeoutError, OSError) as error:
        raise runner.ConfigurationRefused(
            f"NSE corporate-action acquisition failed for {symbol}: {type(error).__name__}: {error}"
        ) from error
    _validate_and_publish_corporate_actions(target, body)
    return target, "CACHE_MISS_SAVED"


def _validate_and_publish_corporate_actions(target: Path, body: bytes) -> None:
    temporary = target.with_name(f".{target.name}.{os.getpid()}.validate")
    try:
        atomic_write_bytes(temporary, body)
        _load_corporate_actions(temporary)
        target.parent.mkdir(parents=True, exist_ok=True)
        os.replace(temporary, target)
    finally:
        if temporary.exists():
            temporary.unlink()


def persist_runtime_authorities(cache_root: Path, universe_csv: Path) -> None:
    authority_dir = cache_root / "authorities"
    target = authority_dir / universe_csv.name
    if target.is_file() and target.read_bytes() != universe_csv.read_bytes():
        raise EvidenceIntegrityError(f"cached universe authority changed: {target}")
    if not target.exists():
        authority_dir.mkdir(parents=True, exist_ok=True)
        temporary = target.with_name(f".{target.name}.{os.getpid()}.tmp")
        shutil.copyfile(universe_csv, temporary)
        os.replace(temporary, target)
    _persist_cost_policy(authority_dir / "research-cost-policy.json")


def _persist_cost_policy(policy_path: Path) -> None:
    policy = {**RESEARCH_COST_POLICY, "canonical_hash": RESEARCH_COST_POLICY_HASH}
    if policy_path.is_file():
        existing = json.loads(policy_path.read_text(encoding="utf-8"))
        if existing != policy:
            raise EvidenceIntegrityError(f"cached cost policy changed: {policy_path}")
        return
    atomic_write_json(policy_path, policy)


def write_summary(
    path: Path,
    *,
    args: object,
    universe_count: int,
    results: Sequence[object],
    stopped: bool,
) -> None:
    """Publish a human-readable restart summary after each terminal instrument state."""
    values = vars(args)
    atomic_write_json(
        path,
        {
            "as_of": datetime.now(UTC).isoformat(),
            "candidate_id": values["candidate_id"],
            "cost_policy_hash": RESEARCH_COST_POLICY_HASH,
            "cost_policy_id": RESEARCH_COST_POLICY_ID,
            "date_range": {
                "from": values["from_date"].isoformat(),
                "to": values["to_date"].isoformat(),
            },
            "evidence_root": str(values["evidence_root"].resolve()),
            "market_cache_root": str(values["cache_root"].resolve()),
            "result_count": len(results),
            "results": [asdict(result) for result in results],
            "static_current_member_studies": True,
            "stopped": stopped,
            "universe_count": universe_count,
            "verdict_ceiling": "RESEARCH_ONLY",
        },
    )


def print_campaign_header(output: CampaignOutput, selected_count: int) -> None:
    values = vars(output.args)
    print(f"full authority universe : {output.universe_count} current constituents")
    print(f"selected work           : {selected_count} names")
    print(f"date range              : {values['from_date']}..{values['to_date']}")
    print(f"market cache            : {values['cache_root'].resolve()}")
    print(f"model evidence          : {values['evidence_root'].resolve()}")
    print(f"cost convention         : RESEARCH PROXY {RESEARCH_COST_POLICY_HASH}")
    print("verdict ceiling         : RESEARCH_ONLY\n", flush=True)


def stop_for_integrity(
    output: CampaignOutput,
    results: Sequence[universe_runner.InstrumentResult],
    error: EvidenceIntegrityError,
) -> int:
    print(f"CACHE INTEGRITY REFUSAL: {error}", flush=True)
    write_summary(
        vars(output.args)["summary_file"],
        args=output.args,
        universe_count=output.universe_count,
        results=results,
        stopped=True,
    )
    return 5


def record_result(
    output: CampaignOutput,
    progress: CampaignProgress,
    index: int,
    result: universe_runner.InstrumentResult,
) -> int | None:
    progress.results.append(result)
    marker = "ok" if result.state == "SUCCEEDED" else "--"
    print(
        f"{marker} [{index:>2}/{progress.total}] {result.symbol:<12} "
        f"{result.state:<20} {result.detail}"
    )
    write_summary(
        vars(output.args)["summary_file"],
        args=output.args,
        universe_count=output.universe_count,
        results=progress.results,
        stopped=result.state == "ACQUISITION_FAILED",
    )
    if result.state == "ACQUISITION_FAILED":
        print("STOPPING AFTER THE EXACT REAL-PROVIDER FAILURE.", flush=True)
        return 2
    if result.trial_id is not None:
        progress.ordinal += 1
    return None


# craft-allow: long-function — argparse declarations are one flat, visible CLI contract.
def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Ten-year real Upstox NIFTY 50 ridge campaign with immutable cache."
    )
    parser.add_argument("--universe-csv", type=Path, required=True)
    parser.add_argument("--from-date", required=True, type=date.fromisoformat)
    parser.add_argument("--to-date", required=True, type=date.fromisoformat)
    parser.add_argument("--cache-root", type=Path, required=True)
    parser.add_argument("--evidence-root", type=Path, required=True)
    parser.add_argument("--summary-file", type=Path, required=True)
    parser.add_argument("--corporate-actions-dir", type=Path, required=True)
    parser.add_argument("--start-ordinal", type=int, default=1)
    parser.add_argument("--skip", type=int, default=0)
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument(
        "--candidate-id", default="cand_ridge_nifty50_current_10y_schema_v2_20260824"
    )
    parser.add_argument("--l2-penalty", default="1")
    parser.add_argument("--validation-sessions", type=int, default=63)
    parser.add_argument("--embargo-sessions", type=int, default=2)
    parser.add_argument("--quantity", type=int, default=1)
    parser.add_argument("--calendar-version", default="provider-derived-v1")
    parser.add_argument("--corporate-authority-version", default="nse-real-response-v1")
    parser.add_argument("--corporate-authority-url", default=NSE_CA_SOURCE_URL)
    parser.add_argument("--universe-authority-id", default="nse-nifty50-current-snapshot")
    parser.add_argument(
        "--universe-authority-url",
        default="https://www.nseindia.com/static/products-services/indices-nifty50-index",
    )
    parser.add_argument("--universe-authority-version", default="2026-08-24")
    parser.add_argument("--sleep-seconds", type=float, default=1.0)
    args = parser.parse_args(argv)
    if args.start_ordinal < 1:
        parser.error("--start-ordinal must be positive")
    if args.sleep_seconds < 0:
        parser.error("--sleep-seconds must be non-negative")
    return args
