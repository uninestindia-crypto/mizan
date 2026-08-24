"""Worker-side real market-data acquisition and immutable evidence publication."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

from quant_system.data.evidence_draft import draft_from_historical_acquisition
from quant_system.data.market_data import (
    HistoricalAcquisition,
    HistoricalAcquisitionFailure,
    HistoricalDailyRequest,
)
from quant_system.data.upstox import UpstoxClient
from quant_system.evidence import (
    EvidenceBusy,
    EvidenceConflict,
    EvidenceError,
    EvidenceIntegrityError,
    EvidenceStore,
    EvidenceStoreConfig,
)


@dataclass(frozen=True, slots=True)
class WorkerFailure:
    """Bounded provider failure safe to serialize across worker IPC."""

    code: str
    message: str
    details: dict[str, Any]


class DataSyncTaskError(Exception):
    """Data-sync failure whose safe details may cross worker IPC."""

    def __init__(self, failure: WorkerFailure) -> None:
        super().__init__(failure.message)
        self.failure = failure


def run_data_sync_task(
    payload: dict[str, Any], cancel_event: Any, queue: Any
) -> dict[str, Any]:
    """Acquire one real Upstox dataset and publish its immutable evidence."""
    queue.put(
        {
            "type": "PROGRESS",
            "progress": 0.1,
            "stage": "ACQUIRING_PROVIDER_DATA",
            "timestamp": datetime.now(UTC).isoformat(),
        }
    )
    request = HistoricalDailyRequest(
        instrument_key=str(payload["instrument_key"]),
        symbol=str(payload["symbol"]),
        from_date=date.fromisoformat(str(payload["from_date"])),
        to_date=date.fromisoformat(str(payload["to_date"])),
        request_id=str(payload["request_id"]) if payload.get("request_id") else None,
    )
    outcome = UpstoxClient().acquire_historical_daily(request)
    if isinstance(outcome, HistoricalAcquisitionFailure):
        details: dict[str, Any] = {"retryable": outcome.retryable}
        if outcome.retry_after_seconds is not None:
            details["retry_after_seconds"] = outcome.retry_after_seconds
        raise DataSyncTaskError(
            WorkerFailure(
                code=outcome.code.value,
                message=f"Historical acquisition failed: {outcome.recovery_action}",
                details=details,
            )
        )
    _validate_outcome_identity(request, outcome)
    if cancel_event.is_set():
        raise InterruptedError("Operation cancelled.")
    queue.put(
        {
            "type": "PROGRESS",
            "progress": 0.7,
            "stage": "PUBLISHING_EVIDENCE",
            "timestamp": datetime.now(UTC).isoformat(),
        }
    )

    def reject_cancelled() -> None:
        if cancel_event.is_set():
            raise InterruptedError("Operation cancelled.")

    try:
        store = EvidenceStore(EvidenceStoreConfig(root=Path(str(payload["_evidence_root"]))))
        commit = store.commit(
            draft_from_historical_acquisition(outcome),
            operation_id=str(payload["_operation_id"]),
            precondition=reject_cancelled,
            duplicate_precondition=reject_cancelled,
        )
    except InterruptedError:
        raise
    except EvidenceBusy as error:
        raise DataSyncTaskError(
            WorkerFailure(
                code="EVIDENCE_STORE_BUSY",
                message="The evidence store is busy with another governed mutation.",
                details={"retryable": True},
            )
        ) from error
    except (EvidenceConflict, EvidenceIntegrityError) as error:
        raise DataSyncTaskError(
            WorkerFailure(
                code="EVIDENCE_INTEGRITY_INVALID",
                message="Evidence publication refused an integrity conflict.",
                details={"retryable": False},
            )
        ) from error
    except (EvidenceError, OSError) as error:
        raise DataSyncTaskError(
            WorkerFailure(
                code="EVIDENCE_STORE_UNAVAILABLE",
                message="The evidence store could not publish this acquisition safely.",
                details={"retryable": True},
            )
        ) from error
    manifest = commit.manifest
    return {
        "canonical_content_hash": str(manifest.metadata["canonical_content_hash"]),
        "dataset_id": manifest.resource_id,
        "manifest_hash": manifest.manifest_hash,
        "provenance": str(manifest.metadata["source"]),
        "published": commit.published,
        "row_count": manifest.row_count,
        "source_status": str(manifest.metadata["source_status"]),
        "status": str(manifest.metadata["status"]),
        "symbol": str(manifest.metadata["symbol"]),
    }


def _validate_outcome_identity(
    request: HistoricalDailyRequest, outcome: HistoricalAcquisition
) -> None:
    manifest = outcome.manifest
    expected = (
        request.instrument_key,
        request.symbol,
        request.from_date,
        request.to_date,
        request.request_id,
    )
    observed = (
        manifest.provider_instrument_id,
        manifest.symbol,
        manifest.requested_start,
        manifest.requested_end,
        manifest.request_id,
    )
    if observed != expected:
        raise DataSyncTaskError(
            WorkerFailure(
                code="PROVIDER_IDENTITY_MISMATCH",
                message="Provider acquisition identity did not match the accepted request.",
                details={"retryable": False},
            )
        )
