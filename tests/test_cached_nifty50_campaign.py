from __future__ import annotations

import importlib
import sys
from datetime import date
from decimal import Decimal
from pathlib import Path
from types import ModuleType

import pytest

from quant_system.analytics.nse_rules import FeeComponent, MarketSegment, Side
from quant_system.data.market_data import HistoricalAcquisition
from quant_system.evidence import (
    EvidenceIntegrityError,
    EvidenceStore,
    EvidenceStoreConfig,
)
from tests.modeling_fixtures import governed_acquisition

REPO_ROOT = Path(__file__).resolve().parent.parent
RUNNER_PATH = REPO_ROOT / "scripts" / "run_cached_nifty50_ridge_campaign.py"


def _runner() -> ModuleType:
    assert RUNNER_PATH.is_file(), "the durable real-data campaign runner has not been built"
    scripts = str(RUNNER_PATH.parent)
    if scripts not in sys.path:
        sys.path.insert(0, scripts)
    return importlib.import_module("run_cached_nifty50_ridge_campaign")


def _store(root: Path) -> EvidenceStore:
    return EvidenceStore(EvidenceStoreConfig(root=root, min_free_bytes=0))


def test_research_cost_proxy_is_explicit_and_stops_at_canonical_boundaries() -> None:
    campaign = _runner()
    engine = campaign.research_cost_engine()

    historical = engine.calculate_costs(
        MarketSegment.EQUITY_DELIVERY,
        Side.BUY,
        1,
        Decimal("1000"),
        date(2016, 9, 22),
    )
    assert historical.applied_rule_ids[FeeComponent.EXCHANGE_TURNOVER.value].startswith(
        "RESEARCH-PROXY-"
    )
    assert historical.applied_rule_ids[FeeComponent.GST.value].startswith("RESEARCH-PROXY-")
    assert historical.applied_rule_ids[FeeComponent.STAMP_DUTY.value].startswith("RESEARCH-PROXY-")

    canonical = engine.calculate_costs(
        MarketSegment.EQUITY_DELIVERY,
        Side.BUY,
        1,
        Decimal("1000"),
        date(2020, 7, 1),
    )
    assert not canonical.applied_rule_ids[FeeComponent.EXCHANGE_TURNOVER.value].startswith(
        "RESEARCH-PROXY-"
    )
    assert not canonical.applied_rule_ids[FeeComponent.GST.value].startswith("RESEARCH-PROXY-")
    assert not canonical.applied_rule_ids[FeeComponent.STAMP_DUTY.value].startswith(
        "RESEARCH-PROXY-"
    )


def test_acquisition_cache_round_trip_rebuilds_the_governed_object(tmp_path: Path) -> None:
    campaign = _runner()
    acquisition = governed_acquisition()
    store = _store(tmp_path / "cache")
    query = campaign.CachedAcquisitionQuery.from_manifest(acquisition.manifest)

    saved = campaign.persist_verified_acquisition(
        store,
        acquisition,
        operation_id="test-cache-round-trip",
    )
    loaded = campaign.load_cached_acquisition(store, query)

    assert loaded is not None
    assert loaded == saved == acquisition
    assert loaded.manifest.to_canonical_dict() == acquisition.manifest.to_canonical_dict()
    assert tuple(row.to_canonical_dict() for row in loaded.records) == tuple(
        row.to_canonical_dict() for row in acquisition.records
    )


def test_cache_hit_never_calls_the_provider(tmp_path: Path) -> None:
    campaign = _runner()
    acquisition = governed_acquisition()
    store = _store(tmp_path / "cache")
    query = campaign.CachedAcquisitionQuery.from_manifest(acquisition.manifest)
    calls = 0

    def fetch() -> HistoricalAcquisition:
        nonlocal calls
        calls += 1
        return acquisition

    first, first_state = campaign.acquire_or_load(
        store,
        query,
        fetch,
        operation_id="test-cache-miss",
    )
    second, second_state = campaign.acquire_or_load(
        store,
        query,
        fetch,
        operation_id="test-cache-hit",
    )

    assert first == second == acquisition
    assert first_state == "CACHE_MISS_SAVED"
    assert second_state == "CACHE_HIT"
    assert calls == 1


def test_verified_catalog_scans_once_then_serves_repeated_hits(tmp_path: Path) -> None:
    campaign = _runner()
    catalog_module = importlib.import_module("cached_nifty50_catalog")
    acquisition = governed_acquisition()
    store = _store(tmp_path / "cache")
    query = campaign.CachedAcquisitionQuery.from_manifest(acquisition.manifest)
    campaign.persist_verified_acquisition(
        store,
        acquisition,
        operation_id="test-indexed-cache-seed",
    )
    catalog = catalog_module.VerifiedAcquisitionCatalog.open(store)

    def forbidden_fetch() -> HistoricalAcquisition:
        raise AssertionError("an indexed cache hit must not call the provider")

    first, first_state = catalog.acquire_or_load(
        query,
        forbidden_fetch,
        operation_id="test-indexed-cache-hit-1",
    )
    second, second_state = catalog.acquire_or_load(
        query,
        forbidden_fetch,
        operation_id="test-indexed-cache-hit-2",
    )

    assert first == second == acquisition
    assert first_state == second_state == "CACHE_HIT"


def test_corrupt_cache_fails_closed_instead_of_refetching(tmp_path: Path) -> None:
    campaign = _runner()
    acquisition = governed_acquisition()
    store = _store(tmp_path / "cache")
    query = campaign.CachedAcquisitionQuery.from_manifest(acquisition.manifest)
    campaign.persist_verified_acquisition(
        store,
        acquisition,
        operation_id="test-cache-corruption",
    )
    manifest_path = store.root / "datasets" / acquisition.manifest.dataset_id / "manifest.json"
    manifest_path.write_bytes(
        manifest_path.read_bytes().replace(b'"symbol":"INFY"', b'"symbol":"TCS"')
    )
    calls = 0

    def fetch() -> HistoricalAcquisition:
        nonlocal calls
        calls += 1
        return acquisition

    with pytest.raises(EvidenceIntegrityError):
        campaign.acquire_or_load(
            store,
            query,
            fetch,
            operation_id="test-cache-corrupt-refusal",
        )

    assert calls == 0


def test_subset_selection_keeps_the_full_universe_authority() -> None:
    campaign = _runner()
    constituents = (
        ("AAA", "NSE_EQ|INE000A01001"),
        ("BBB", "NSE_EQ|INE000A01002"),
        ("CCC", "NSE_EQ|INE000A01003"),
    )

    selection = campaign.select_constituents(constituents, skip=1, limit=1)

    assert selection.selected == (constituents[1],)
    assert selection.authority_members == tuple(sorted(key for _, key in constituents))
