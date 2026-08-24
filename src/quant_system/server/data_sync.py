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
    CommitPhase,
    CommitResult,
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


def run_data_sync_task(payload: dict[str, Any], cancel_event: Any, queue: Any) -> dict[str, Any]:
    """Acquire one real Upstox dataset and publish its immutable evidence."""
    _report_progress(queue, progress=0.1, stage="ACQUIRING_PROVIDER_DATA")
    request = _request_from_payload(payload)
    outcome = _acquire_provider_data(request)
    _validate_outcome_identity(request, outcome)
    _reject_cancelled(cancel_event)
    _report_progress(queue, progress=0.7, stage="PUBLISHING_EVIDENCE")
    commit = _publish_acquisition(
        outcome=outcome,
        evidence_root=Path(str(payload["_evidence_root"])),
        operation_id=str(payload["_operation_id"]),
        cancel_event=cancel_event,
    )
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


def _report_progress(queue: Any, *, progress: float, stage: str) -> None:
    queue.put(
        {
            "type": "PROGRESS",
            "progress": progress,
            "stage": stage,
            "timestamp": datetime.now(UTC).isoformat(),
        }
    )


def _request_from_payload(payload: dict[str, Any]) -> HistoricalDailyRequest:
    return HistoricalDailyRequest(
        instrument_key=str(payload["instrument_key"]),
        symbol=str(payload["symbol"]),
        from_date=date.fromisoformat(str(payload["from_date"])),
        to_date=date.fromisoformat(str(payload["to_date"])),
        request_id=str(payload["request_id"]) if payload.get("request_id") else None,
    )


def _acquire_provider_data(request: HistoricalDailyRequest) -> HistoricalAcquisition:
    try:
        outcome = UpstoxClient().acquire_historical_daily(request)
    except Exception as error:
        raise _unexpected_provider_task_error() from error
    if isinstance(outcome, HistoricalAcquisitionFailure):
        raise _provider_task_error(outcome)
    return outcome


def _unexpected_provider_task_error() -> DataSyncTaskError:
    return DataSyncTaskError(
        WorkerFailure(
            code="DATA_SYNC_FAILED",
            message="Historical acquisition failed before a verified provider outcome.",
            details={"retryable": False},
        )
    )


def _provider_task_error(outcome: HistoricalAcquisitionFailure) -> DataSyncTaskError:
    details: dict[str, Any] = {"retryable": outcome.retryable}
    if outcome.retry_after_seconds is not None:
        details["retry_after_seconds"] = outcome.retry_after_seconds
    return DataSyncTaskError(
        WorkerFailure(
            code=outcome.code.value,
            message=f"Historical acquisition failed: {outcome.recovery_action}",
            details=details,
        )
    )


def _reject_cancelled(cancel_event: Any) -> None:
    if cancel_event.is_set():
        raise InterruptedError("Operation cancelled.")


def _publish_acquisition(
    *,
    outcome: HistoricalAcquisition,
    evidence_root: Path,
    operation_id: str,
    cancel_event: Any,
) -> CommitResult:
    def reject_cancelled() -> None:
        _reject_cancelled(cancel_event)

    def reject_during_staging(phase: CommitPhase) -> None:
        if phase != CommitPhase.RESOURCE_PUBLISHED:
            reject_cancelled()

    try:
        store = EvidenceStore(EvidenceStoreConfig(root=evidence_root))
        return store.commit(
            draft_from_historical_acquisition(outcome),
            operation_id=operation_id,
            phase_hook=reject_during_staging,
            precondition=reject_cancelled,
            duplicate_precondition=reject_cancelled,
        )
    except InterruptedError:
        raise
    except (EvidenceError, OSError) as error:
        raise _evidence_task_error(error) from error


def _evidence_task_error(error: EvidenceError | OSError) -> DataSyncTaskError:
    if isinstance(error, EvidenceBusy):
        failure = WorkerFailure(
            code="EVIDENCE_STORE_BUSY",
            message="The evidence store is busy with another governed mutation.",
            details={"retryable": True},
        )
    elif isinstance(error, (EvidenceConflict, EvidenceIntegrityError)):
        failure = WorkerFailure(
            code="EVIDENCE_INTEGRITY_INVALID",
            message="Evidence publication refused an integrity conflict.",
            details={"retryable": False},
        )
    else:
        failure = WorkerFailure(
            code="EVIDENCE_STORE_UNAVAILABLE",
            message="The evidence store could not publish this acquisition safely.",
            details={"retryable": True},
        )
    return DataSyncTaskError(failure)


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
