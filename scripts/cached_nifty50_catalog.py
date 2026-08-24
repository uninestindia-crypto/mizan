"""One-scan verified acquisition catalog for large cached universe campaigns."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from cached_nifty50_evidence import (
    CachedAcquisitionQuery,
    historical_acquisition_from_verified,
    persist_verified_acquisition,
)

from quant_system.data.market_data import (
    HistoricalAcquisition,
    HistoricalAcquisitionFailure,
)
from quant_system.evidence import (
    EvidenceIntegrityError,
    EvidenceResourceType,
    EvidenceStore,
)


@dataclass(slots=True)
class VerifiedAcquisitionCatalog:
    """Cache query index built only after every catalog entry verifies successfully."""

    store: EvidenceStore
    entries: dict[CachedAcquisitionQuery, HistoricalAcquisition]

    @classmethod
    def open(cls, store: EvidenceStore) -> VerifiedAcquisitionCatalog:
        entries: dict[CachedAcquisitionQuery, HistoricalAcquisition] = {}
        for verified in store.list_verified(EvidenceResourceType.DATASET):
            acquisition = historical_acquisition_from_verified(verified)
            query = CachedAcquisitionQuery.from_manifest(acquisition.manifest)
            if query in entries:
                raise EvidenceIntegrityError("acquisition cache has duplicate exact queries")
            entries[query] = acquisition
        return cls(store=store, entries=entries)

    def acquire_or_load(
        self,
        query: CachedAcquisitionQuery,
        fetch: Callable[[], HistoricalAcquisition | HistoricalAcquisitionFailure],
        *,
        operation_id: str,
    ) -> tuple[HistoricalAcquisition | HistoricalAcquisitionFailure, str]:
        cached = self.entries.get(query)
        if cached is not None:
            return cached, "CACHE_HIT"
        outcome = fetch()
        if isinstance(outcome, HistoricalAcquisitionFailure):
            return outcome, "CACHE_MISS_FAILED"
        if CachedAcquisitionQuery.from_manifest(outcome.manifest) != query:
            raise EvidenceIntegrityError("provider acquisition does not match the cache query")
        saved = persist_verified_acquisition(
            self.store,
            outcome,
            operation_id=operation_id,
        )
        if query in self.entries:
            raise EvidenceIntegrityError("acquisition query appeared concurrently during publish")
        self.entries[query] = saved
        return saved, "CACHE_MISS_SAVED"
