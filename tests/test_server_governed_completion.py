"""Completion-audit regressions for the governed dataset and model API boundary."""

from __future__ import annotations

import base64
import time
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
from fastapi.testclient import TestClient
from httpx import Response

from quant_system.data.evidence_draft import draft_from_historical_acquisition
from quant_system.data.provenance import ACCESS_TOKEN_ENV_VAR
from quant_system.evidence import (
    CommitPhase,
    EvidenceDraft,
    EvidenceStore,
    EvidenceStoreConfig,
)
from quant_system.server import data_sync
from quant_system.server.app import app
from quant_system.server.data_sync import DataSyncTaskError, run_data_sync_task
from quant_system.server.supervisor import supervisor
from tests.modeling_fixtures import governed_acquisition

_EVIDENCE_ROOT_ENV = "QUANTOS_EVIDENCE_ROOT"


@pytest.fixture(autouse=True)
def cleanup_global_supervisor() -> Any:
    supervisor.shutdown()
    with supervisor._lock:
        supervisor._operations.clear()
        supervisor._idempotency_map.clear()
        supervisor._active_op_id = None
        supervisor._active_process = None
        supervisor._active_queue = None
        supervisor._active_cancel_event = None
    yield
    supervisor.shutdown()


@pytest.fixture
def client() -> TestClient:
    return TestClient(app, base_url="http://localhost:8000")


@pytest.fixture
def auth_headers(client: TestClient) -> dict[str, str]:
    token_response = client.get("/api/v1/csrf-token")
    return {
        "Host": "localhost:8000",
        "Origin": "http://localhost:8000",
        "X-CSRF-Token": token_response.json()["csrf_token"],
    }


def _error_code(response: Response) -> str:
    return str(response.json()["error"]["code"])


def test_dataset_catalog_rejects_hash_valid_but_domain_invalid_metadata(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    evidence_root = tmp_path / "runtime-evidence"
    acquisition = governed_acquisition()
    valid_draft = draft_from_historical_acquisition(acquisition)
    invalid_metadata = dict(valid_draft.metadata)
    invalid_metadata["symbol"] = "TCS"
    store = EvidenceStore(EvidenceStoreConfig(root=evidence_root, min_free_bytes=0))
    store.commit(
        EvidenceDraft(
            resource_type=valid_draft.resource_type,
            resource_id=valid_draft.resource_id,
            schema_id=valid_draft.schema_id,
            schema_version=valid_draft.schema_version,
            metadata=invalid_metadata,
            records=valid_draft.records,
            total_order=valid_draft.total_order,
        ),
        operation_id="domain-invalid-dataset",
    )
    monkeypatch.setenv(_EVIDENCE_ROOT_ENV, str(evidence_root))

    response = client.get("/api/v1/datasets")

    assert response.status_code == 409
    assert _error_code(response) == "EVIDENCE_INTEGRITY_INVALID"
    assert acquisition.manifest.dataset_id not in response.text


def test_dataset_catalog_rejects_a_well_formed_cursor_for_an_unknown_resource(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    evidence_root = tmp_path / "runtime-evidence"
    acquisition = governed_acquisition()
    store = EvidenceStore(EvidenceStoreConfig(root=evidence_root, min_free_bytes=0))
    store.commit(
        draft_from_historical_acquisition(acquisition),
        operation_id="known-dataset",
    )
    monkeypatch.setenv(_EVIDENCE_ROOT_ENV, str(evidence_root))
    invented_identity = f"dset_{'0' * 24}"
    cursor = (
        base64.urlsafe_b64encode(
            f"dataset:v1:2025-01-01T00:00:00+00:00|{invented_identity}".encode()
        )
        .decode()
        .rstrip("=")
    )

    response = client.get("/api/v1/datasets", params={"cursor": cursor})

    assert response.status_code == 422
    assert _error_code(response) == "INVALID_CURSOR"


def test_dataset_acquisition_rejects_a_range_beyond_the_provider_limit(
    client: TestClient,
    auth_headers: dict[str, str],
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setenv(_EVIDENCE_ROOT_ENV, str(tmp_path / "runtime-evidence"))

    response = client.post(
        "/api/v1/datasets",
        json={
            "instrument_key": "NSE_EQ|INE009A01021",
            "symbol": "INFY",
            "from_date": "2015-01-01",
            "to_date": "2026-01-02",
        },
        headers={**auth_headers, "Idempotency-Key": "range-too-large"},
    )

    assert response.status_code == 422
    assert _error_code(response) == "VALIDATION_ERROR"
    assert supervisor.list_operations() == []


def test_data_sync_worker_sanitizes_an_unexpected_provider_exception(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    def fail_provider(_request: object) -> object:
        raise OSError("private-provider-path/token-value")

    monkeypatch.setattr(
        data_sync,
        "UpstoxClient",
        lambda: SimpleNamespace(acquire_historical_daily=fail_provider),
    )
    payload = {
        "instrument_key": "NSE_EQ|INE009A01021",
        "symbol": "INFY",
        "from_date": "2025-01-01",
        "to_date": "2025-01-31",
        "request_id": "safe-provider-failure",
        "_evidence_root": str(tmp_path / "runtime-evidence"),
        "_operation_id": "worker-provider-exception",
    }

    with pytest.raises(DataSyncTaskError) as captured:
        run_data_sync_task(
            payload,
            SimpleNamespace(is_set=lambda: False),
            SimpleNamespace(put=lambda _event: None),
        )

    assert captured.value.failure.code == "DATA_SYNC_FAILED"
    assert "private-provider-path" not in str(captured.value)
    assert "token-value" not in str(captured.value.failure.details)


def test_data_sync_worker_observes_cancellation_during_evidence_staging(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    acquisition = governed_acquisition()
    cancellation = SimpleNamespace(requested=False)
    monkeypatch.setattr(
        data_sync,
        "UpstoxClient",
        lambda: SimpleNamespace(acquire_historical_daily=lambda _request: acquisition),
    )

    class CancellingEvidenceStore:
        def __init__(self, _config: EvidenceStoreConfig) -> None:
            pass

        def commit(
            self,
            _draft: object,
            *,
            operation_id: str,
            phase_hook: object,
            precondition: object,
            duplicate_precondition: object,
        ) -> object:
            assert operation_id == "worker-cancel-during-stage"
            precondition()  # type: ignore[operator]
            cancellation.requested = True
            phase_hook(CommitPhase.COMMIT_MARKER_STAGED)  # type: ignore[operator]
            pytest.fail("publication continued after cancellation")

    monkeypatch.setattr(data_sync, "EvidenceStore", CancellingEvidenceStore)
    payload = {
        "instrument_key": acquisition.manifest.provider_instrument_id,
        "symbol": acquisition.manifest.symbol,
        "from_date": acquisition.manifest.requested_start.isoformat(),
        "to_date": acquisition.manifest.requested_end.isoformat(),
        "request_id": acquisition.manifest.request_id,
        "_evidence_root": str(tmp_path / "runtime-evidence"),
        "_operation_id": "worker-cancel-during-stage",
    }

    with pytest.raises(InterruptedError, match="cancelled"):
        run_data_sync_task(
            payload,
            SimpleNamespace(is_set=lambda: cancellation.requested),
            SimpleNamespace(put=lambda _event: None),
        )


def test_data_sync_worker_leaves_no_dataset_when_cancelled_after_staging_starts(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    acquisition = governed_acquisition()
    monkeypatch.setattr(
        data_sync,
        "UpstoxClient",
        lambda: SimpleNamespace(acquire_historical_daily=lambda _request: acquisition),
    )
    cancellation_states = iter((False, False, True))
    evidence_root = tmp_path / "runtime-evidence"
    payload = {
        "instrument_key": acquisition.manifest.provider_instrument_id,
        "symbol": acquisition.manifest.symbol,
        "from_date": acquisition.manifest.requested_start.isoformat(),
        "to_date": acquisition.manifest.requested_end.isoformat(),
        "request_id": acquisition.manifest.request_id,
        "_evidence_root": str(evidence_root),
        "_operation_id": "worker-cancel-after-staging",
    }

    with pytest.raises(InterruptedError, match="cancelled"):
        run_data_sync_task(
            payload,
            SimpleNamespace(is_set=lambda: next(cancellation_states)),
            SimpleNamespace(put=lambda _event: None),
        )

    assert list((evidence_root / "datasets").iterdir()) == []


def test_dataset_idempotency_ignores_operator_only_runtime_configuration(
    client: TestClient,
    auth_headers: dict[str, str],
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.delenv(ACCESS_TOKEN_ENV_VAR, raising=False)
    monkeypatch.setenv(_EVIDENCE_ROOT_ENV, str(tmp_path / "evidence-a"))
    headers = {**auth_headers, "Idempotency-Key": "stable-client-intent"}
    request = {
        "instrument_key": "NSE_EQ|INE009A01021",
        "symbol": "INFY",
        "from_date": "2025-01-01",
        "to_date": "2025-01-31",
    }

    first = client.post("/api/v1/datasets", json=request, headers=headers)
    monkeypatch.setenv(_EVIDENCE_ROOT_ENV, str(tmp_path / "evidence-b"))
    replay = client.post("/api/v1/datasets", json=request, headers=headers)

    assert first.status_code == 202
    assert replay.status_code == 202
    assert replay.json()["operation_id"] == first.json()["operation_id"]


def test_versioned_training_operation_never_returns_invented_model_metrics(
    client: TestClient,
    auth_headers: dict[str, str],
) -> None:
    response = client.post(
        "/api/v1/operations/train",
        json={"candidate_id": "cand_ridge_v1"},
        headers={**auth_headers, "Idempotency-Key": "no-placeholder-training"},
    )

    assert response.status_code == 409
    assert _error_code(response) == "MODEL_CONTRACT_INCOMPATIBLE"
    assert supervisor.list_operations() == []


# test-allow: loop-in-test — bounded HTTP polling observes one spawned worker to terminal state.
def test_dataset_idempotency_replays_the_same_operation_after_supervisor_restart(
    client: TestClient,
    auth_headers: dict[str, str],
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.delenv(ACCESS_TOKEN_ENV_VAR, raising=False)
    monkeypatch.delenv("UPSTOX_ANALYTICS_TOKEN", raising=False)
    monkeypatch.setenv(_EVIDENCE_ROOT_ENV, str(tmp_path / "runtime-evidence"))
    headers = {**auth_headers, "Idempotency-Key": "durable-dataset-intent"}
    request = {
        "instrument_key": "NSE_EQ|INE009A01021",
        "symbol": "INFY",
        "from_date": "2025-01-01",
        "to_date": "2025-01-31",
    }

    created = client.post("/api/v1/datasets", json=request, headers=headers)
    assert created.status_code == 202
    operation_id = created.json()["operation_id"]
    deadline = time.monotonic() + 10
    while time.monotonic() < deadline:
        terminal = client.get(created.headers["Location"])
        assert terminal.status_code == 200
        if terminal.json()["status"] in {"FAILED", "LOST"}:
            break
        # test-allow: sleep-in-test — bounded polling observes a real spawned process via HTTP.
        time.sleep(0.05)
    else:
        pytest.fail("dataset operation did not reach a terminal failure")
    assert terminal.json()["status"] == "FAILED"

    supervisor.shutdown()
    with supervisor._lock:
        supervisor._operations.clear()
        supervisor._idempotency_map.clear()

    replay = client.post("/api/v1/datasets", json=request, headers=headers)
    assert replay.status_code == 202
    assert replay.json()["operation_id"] == operation_id
    assert replay.json()["status"] == "FAILED"

    conflict = client.post(
        "/api/v1/datasets",
        json={**request, "to_date": "2025-02-01"},
        headers=headers,
    )
    assert conflict.status_code == 422
    assert _error_code(conflict) == "IDEMPOTENCY_KEY_REUSED"

    receipt_file = next(
        (tmp_path / "runtime-evidence" / ".server" / "operation-receipts").glob("*.json")
    )
    receipt_file.write_text("{}\n", encoding="utf-8")
    supervisor.shutdown()
    with supervisor._lock:
        supervisor._operations.clear()
        supervisor._idempotency_map.clear()

    tampered = client.post("/api/v1/datasets", json=request, headers=headers)
    assert tampered.status_code == 503
    assert _error_code(tampered) == "OPERATION_JOURNAL_UNAVAILABLE"
    assert str(tmp_path) not in tampered.text
    assert supervisor.list_operations() == []


def test_security_middleware_never_reflects_an_unbounded_or_unsafe_request_id(
    client: TestClient,
) -> None:
    unsafe_request_id = "<script>alert(1)</script>" + ("x" * 4096)

    response = client.get(
        "/api/v1/version",
        headers={"X-Request-ID": unsafe_request_id},
    )

    assert response.status_code == 200
    trusted_request_id = response.headers["X-Request-ID"]
    assert trusted_request_id.startswith("req-")
    assert len(trusted_request_id) <= 64
    assert unsafe_request_id not in response.text

    valid = client.get(
        "/api/v1/version",
        headers={"X-Request-ID": "trace.dataset-123"},
    )
    assert valid.headers["X-Request-ID"] == "trace.dataset-123"
