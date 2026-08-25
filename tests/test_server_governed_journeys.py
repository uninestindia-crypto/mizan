"""Public-boundary regressions for truthful governed journey APIs."""

from __future__ import annotations

import json
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
    EvidenceResourceType,
    EvidenceStore,
    EvidenceStoreConfig,
)
from quant_system.server import data_sync
from quant_system.server.app import app
from quant_system.server.data_sync import DataSyncTaskError, run_data_sync_task
from quant_system.server.schemas import OperationType
from quant_system.server.supervisor import WorkerSupervisor, supervisor
from tests.modeling_fixtures import governed_acquisition, governed_calendar

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
    payload = response.json()
    return str(payload["error"]["code"])


def _publish_real_acquisition(root: Path, *, count: int = 25) -> str:
    calendar = governed_calendar(count)
    acquisition = governed_acquisition(count=count, calendar=calendar)
    store = EvidenceStore(EvidenceStoreConfig(root=root, min_free_bytes=0))
    result = store.commit(
        draft_from_historical_acquisition(acquisition),
        operation_id=f"server-dataset-fixture-{count}",
    )
    return result.manifest.resource_id


def test_dataset_catalog_requires_an_operator_configured_evidence_root(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv(_EVIDENCE_ROOT_ENV, raising=False)

    response = client.get("/api/v1/datasets")

    assert response.status_code == 503
    assert _error_code(response) == "EVIDENCE_ROOT_NOT_CONFIGURED"
    assert response.headers["Retry-After"] == "60"


def test_dataset_catalog_rejects_an_evidence_root_that_is_not_a_directory(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    evidence_root = tmp_path / "not-a-directory"
    evidence_root.write_text("invalid", encoding="utf-8")
    monkeypatch.setenv(_EVIDENCE_ROOT_ENV, str(evidence_root))

    response = client.get("/api/v1/datasets")

    assert response.status_code == 503
    assert _error_code(response) == "EVIDENCE_ROOT_INVALID"
    assert response.headers["Retry-After"] == "60"


def test_dataset_catalog_returns_verified_manifest_identity_not_samples(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    evidence_root = tmp_path / "runtime-evidence"
    dataset_id = _publish_real_acquisition(evidence_root)
    monkeypatch.setenv(_EVIDENCE_ROOT_ENV, str(evidence_root))

    response = client.get("/api/v1/datasets?limit=25")

    assert response.status_code == 200
    payload = response.json()
    assert payload["has_more"] is False
    assert payload["next_cursor"] is None
    assert len(payload["items"]) == 1
    item = payload["items"][0]
    assert item["dataset_id"] == dataset_id
    assert item["symbol"] == "INFY"
    assert item["provider_instrument_id"] == "NSE_EQ|INE009A01021"
    assert item["row_count"] == 25
    assert len(item["manifest_hash"]) == 64
    assert len(item["canonical_content_hash"]) == 64
    assert item["provenance"] == "UPSTOX_HISTORICAL"


def test_dataset_catalog_fails_closed_when_a_manifest_is_tampered(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    evidence_root = tmp_path / "runtime-evidence"
    dataset_id = _publish_real_acquisition(evidence_root)
    manifest_path = evidence_root / "datasets" / dataset_id / "manifest.json"
    payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    payload["metadata"]["source"] = "tampered"
    manifest_path.write_text(json.dumps(payload), encoding="utf-8")
    monkeypatch.setenv(_EVIDENCE_ROOT_ENV, str(evidence_root))

    response = client.get("/api/v1/datasets")

    assert response.status_code == 409
    assert _error_code(response) == "EVIDENCE_INTEGRITY_INVALID"
    assert dataset_id not in response.text


def test_dataset_catalog_cursor_pages_without_duplicates(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    evidence_root = tmp_path / "runtime-evidence"
    expected = {
        _publish_real_acquisition(evidence_root, count=24),
        _publish_real_acquisition(evidence_root, count=25),
    }
    monkeypatch.setenv(_EVIDENCE_ROOT_ENV, str(evidence_root))

    first = client.get("/api/v1/datasets?limit=1")

    assert first.status_code == 200
    first_payload = first.json()
    assert first_payload["has_more"] is True
    assert first_payload["next_cursor"]

    second = client.get(
        "/api/v1/datasets",
        params={"limit": 1, "cursor": first_payload["next_cursor"]},
    )

    assert second.status_code == 200
    second_payload = second.json()
    observed = {
        first_payload["items"][0]["dataset_id"],
        second_payload["items"][0]["dataset_id"],
    }
    assert observed == expected
    assert second_payload["has_more"] is False


def test_dataset_catalog_rejects_a_malformed_cursor(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setenv(_EVIDENCE_ROOT_ENV, str(tmp_path / "runtime-evidence"))

    response = client.get("/api/v1/datasets?cursor=not-a-cursor")

    assert response.status_code == 422
    assert _error_code(response) == "INVALID_CURSOR"


@pytest.mark.parametrize(
    ("query", "expected_code"),
    [
        ("unknown=value", "UNSUPPORTED_QUERY_PARAMETER"),
        ("limit=1&limit=2", "INVALID_QUERY_PARAMETER"),
    ],
)
def test_dataset_catalog_rejects_ambiguous_or_unknown_query_parameters(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    query: str,
    expected_code: str,
) -> None:
    monkeypatch.setenv(_EVIDENCE_ROOT_ENV, str(tmp_path / "runtime-evidence"))

    response = client.get(f"/api/v1/datasets?{query}")

    assert response.status_code == 422
    assert _error_code(response) == expected_code


def test_dataset_acquisition_requires_an_idempotency_key(
    client: TestClient,
    auth_headers: dict[str, str],
) -> None:
    response = client.post(
        "/api/v1/datasets",
        json={
            "instrument_key": "NSE_EQ|INE009A01021",
            "symbol": "INFY",
            "from_date": "2025-01-01",
            "to_date": "2025-01-31",
        },
        headers=auth_headers,
    )

    assert response.status_code == 422
    assert _error_code(response) == "IDEMPOTENCY_KEY_REQUIRED"


def test_dataset_acquisition_rejects_a_symbol_instrument_identity_mismatch(
    client: TestClient,
    auth_headers: dict[str, str],
) -> None:
    response = client.post(
        "/api/v1/datasets",
        json={
            "instrument_key": "NSE_EQ|INE009A01021",
            "symbol": "TCS",
            "from_date": "2025-01-01",
            "to_date": "2025-01-31",
        },
        headers={**auth_headers, "Idempotency-Key": "mismatched-instrument"},
    )

    assert response.status_code == 422
    assert _error_code(response) == "VALIDATION_ERROR"
    assert "same supported NSE equity" in response.text
    safe_error = response.json()["error"]["details"]["errors"][0]
    assert "input" not in safe_error
    assert "ctx" not in safe_error


def test_dataset_acquisition_rejects_an_invalid_idempotency_key(
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
            "from_date": "2025-01-01",
            "to_date": "2025-01-31",
        },
        headers={**auth_headers, "Idempotency-Key": "contains a space"},
    )

    assert response.status_code == 422
    assert _error_code(response) == "IDEMPOTENCY_KEY_INVALID"


def test_dataset_acquisition_does_not_accept_an_http_selected_evidence_root(
    client: TestClient,
    auth_headers: dict[str, str],
    tmp_path: Path,
) -> None:
    selected_root = tmp_path / "client-selected-root"

    response = client.post(
        "/api/v1/datasets",
        json={
            "instrument_key": "NSE_EQ|INE009A01021",
            "symbol": "INFY",
            "from_date": "2025-01-01",
            "to_date": "2025-01-31",
            "_evidence_root": str(selected_root),
        },
        headers={**auth_headers, "Idempotency-Key": "no-client-root"},
    )

    assert response.status_code == 422
    assert _error_code(response) == "VALIDATION_ERROR"
    assert not selected_root.exists()


def test_data_sync_worker_publishes_the_provider_acquisition(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    acquisition = governed_acquisition()
    events: list[dict[str, Any]] = []
    client = SimpleNamespace(acquire_historical_daily=lambda _request: acquisition)
    monkeypatch.setattr(data_sync, "UpstoxClient", lambda: client)
    payload = {
        "instrument_key": acquisition.manifest.provider_instrument_id,
        "symbol": acquisition.manifest.symbol,
        "from_date": acquisition.manifest.requested_start.isoformat(),
        "to_date": acquisition.manifest.requested_end.isoformat(),
        "request_id": acquisition.manifest.request_id,
        "_evidence_root": str(tmp_path / "runtime-evidence"),
        "_operation_id": "worker-success",
    }

    result = run_data_sync_task(
        payload,
        SimpleNamespace(is_set=lambda: False),
        SimpleNamespace(put=events.append),
    )

    assert result["dataset_id"] == acquisition.manifest.dataset_id
    assert result["canonical_content_hash"] == acquisition.manifest.canonical_content_hash
    assert result["row_count"] == len(acquisition.records)
    assert [event["stage"] for event in events] == [
        "ACQUIRING_PROVIDER_DATA",
        "PUBLISHING_EVIDENCE",
    ]
    stored = EvidenceStore(
        EvidenceStoreConfig(root=tmp_path / "runtime-evidence", min_free_bytes=0)
    ).list_verified(EvidenceResourceType.DATASET)
    assert len(stored) == 1
    assert stored[0].manifest.manifest_hash == result["manifest_hash"]


def test_data_sync_worker_rechecks_cancellation_before_publication(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    acquisition = governed_acquisition()
    client = SimpleNamespace(acquire_historical_daily=lambda _request: acquisition)
    monkeypatch.setattr(data_sync, "UpstoxClient", lambda: client)
    cancellation_states = iter((False, True))
    payload = {
        "instrument_key": acquisition.manifest.provider_instrument_id,
        "symbol": acquisition.manifest.symbol,
        "from_date": acquisition.manifest.requested_start.isoformat(),
        "to_date": acquisition.manifest.requested_end.isoformat(),
        "request_id": acquisition.manifest.request_id,
        "_evidence_root": str(tmp_path / "runtime-evidence"),
        "_operation_id": "worker-cancelled",
    }

    with pytest.raises(InterruptedError, match="cancelled"):
        run_data_sync_task(
            payload,
            SimpleNamespace(is_set=lambda: next(cancellation_states)),
            SimpleNamespace(put=lambda _event: None),
        )

    datasets = tmp_path / "runtime-evidence" / "datasets"
    assert datasets.is_dir()
    assert list(datasets.iterdir()) == []


def test_data_sync_worker_refuses_a_provider_identity_mismatch(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    acquisition = governed_acquisition()
    client = SimpleNamespace(acquire_historical_daily=lambda _request: acquisition)
    monkeypatch.setattr(data_sync, "UpstoxClient", lambda: client)
    payload = {
        "instrument_key": "NSE_EQ|INE467B01029",
        "symbol": "TCS",
        "from_date": acquisition.manifest.requested_start.isoformat(),
        "to_date": acquisition.manifest.requested_end.isoformat(),
        "request_id": acquisition.manifest.request_id,
        "_evidence_root": str(tmp_path / "runtime-evidence"),
        "_operation_id": "worker-mismatch",
    }

    with pytest.raises(DataSyncTaskError) as captured:
        run_data_sync_task(
            payload,
            SimpleNamespace(is_set=lambda: False),
            SimpleNamespace(put=lambda _event: None),
        )

    assert captured.value.failure.code == "PROVIDER_IDENTITY_MISMATCH"
    assert not (tmp_path / "runtime-evidence").exists()


# test-allow: loop-in-test — bounded polling observes one spawned worker to terminal state.
def test_dataset_acquisition_reports_missing_provider_credentials_without_publishing(
    client: TestClient,
    auth_headers: dict[str, str],
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    evidence_root = tmp_path / "runtime-evidence"
    monkeypatch.setenv(_EVIDENCE_ROOT_ENV, str(evidence_root))
    monkeypatch.delenv(ACCESS_TOKEN_ENV_VAR, raising=False)
    headers = {**auth_headers, "Idempotency-Key": "dataset-without-credentials"}

    created = client.post(
        "/api/v1/datasets",
        json={
            "instrument_key": "NSE_EQ|INE009A01021",
            "symbol": "INFY",
            "from_date": "2025-01-01",
            "to_date": "2025-01-31",
        },
        headers=headers,
    )

    assert created.status_code == 202
    operation_url = created.headers["Location"]
    deadline = time.monotonic() + 10
    while time.monotonic() < deadline:
        polled = client.get(operation_url)
        assert polled.status_code == 200
        if polled.json()["status"] in {"FAILED", "LOST"}:
            break
        # test-allow: sleep-in-test — bounded polling observes a real spawned process via HTTP.
        time.sleep(0.05)
    else:
        pytest.fail("dataset operation did not reach a terminal failure")

    payload = polled.json()
    assert payload["status"] == "FAILED"
    assert payload["error"]["code"] == "PROVIDER_UNAUTHORIZED"
    assert client.get("/api/v1/datasets").json()["items"] == []


def test_dataset_acquisition_binds_an_idempotency_key_to_one_request(
    client: TestClient,
    auth_headers: dict[str, str],
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setenv(_EVIDENCE_ROOT_ENV, str(tmp_path / "runtime-evidence"))
    monkeypatch.delenv(ACCESS_TOKEN_ENV_VAR, raising=False)
    headers = {**auth_headers, "Idempotency-Key": "one-dataset-intent"}
    request = {
        "instrument_key": "NSE_EQ|INE009A01021",
        "symbol": "INFY",
        "from_date": "2025-01-01",
        "to_date": "2025-01-31",
    }

    first = client.post("/api/v1/datasets", json=request, headers=headers)
    replay = client.post("/api/v1/datasets", json=request, headers=headers)
    conflict = client.post(
        "/api/v1/datasets",
        json={**request, "to_date": "2025-02-28"},
        headers=headers,
    )

    assert first.status_code == 202
    assert replay.status_code == 202
    assert replay.json()["operation_id"] == first.json()["operation_id"]
    assert conflict.status_code == 422
    assert _error_code(conflict) == "IDEMPOTENCY_KEY_REUSED"


def test_legacy_manifest_route_never_fabricates_verified_datasets(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv(_EVIDENCE_ROOT_ENV, raising=False)

    response = client.get("/api/data/manifests")

    assert response.status_code == 503
    assert _error_code(response) == "EVIDENCE_ROOT_NOT_CONFIGURED"


def test_legacy_ingest_route_is_retired_instead_of_fabricating_a_manifest(
    client: TestClient,
    auth_headers: dict[str, str],
) -> None:
    response = client.post(
        "/api/data/ingest",
        json={
            "symbol": "INFY",
            "start_date": "2025-01-01",
            "end_date": "2025-01-31",
            "source": "SYNTHETIC",
        },
        headers=auth_headers,
    )

    assert response.status_code == 410
    assert _error_code(response) == "LEGACY_ENDPOINT_RETIRED"
    assert response.json()["error"]["details"]["replacement"] == "/api/v1/datasets"
    assert response.headers["Deprecation"] == "true"
    assert response.headers["Sunset"] == "Mon, 24 Aug 2026 00:00:00 GMT"
    assert 'rel="successor-version"' in response.headers["Link"]


def test_legacy_feature_route_never_returns_sample_rows(
    client: TestClient,
    auth_headers: dict[str, str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv(_EVIDENCE_ROOT_ENV, raising=False)

    response = client.post(
        "/api/features/explore",
        json={"symbol": "INFY", "horizon_days": 5, "label_friction_bps": 5.0},
        headers=auth_headers,
    )

    assert response.status_code == 503
    assert _error_code(response) == "EVIDENCE_ROOT_NOT_CONFIGURED"


def test_feature_explore_fails_closed_when_evidence_not_available(
    client: TestClient,
    auth_headers: dict[str, str],
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setenv(_EVIDENCE_ROOT_ENV, str(tmp_path))

    response = client.post(
        "/api/features/explore",
        json={"symbol": "INFY", "horizon_days": 5, "label_friction_bps": 5.0},
        headers=auth_headers,
    )

    assert response.status_code == 404
    assert _error_code(response) == "FEATURE_EVIDENCE_NOT_AVAILABLE"


def test_legacy_training_route_never_returns_invented_positive_metrics(
    client: TestClient,
    auth_headers: dict[str, str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv(_EVIDENCE_ROOT_ENV, raising=False)

    response = client.post(
        "/api/training/governed-ridge",
        json={"candidate_id": "cand_ridge_v1"},
        headers=auth_headers,
    )

    assert response.status_code == 503
    assert _error_code(response) == "EVIDENCE_ROOT_NOT_CONFIGURED"


def test_legacy_holdout_route_never_invents_a_pass_without_evidence(
    client: TestClient,
    auth_headers: dict[str, str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv(_EVIDENCE_ROOT_ENV, raising=False)

    response = client.post(
        "/api/holdout/evaluate",
        json={
            "candidate_id": "cand_ridge_v1",
            "unlock_token": "not-a-real-token",
            "confirm_single_use": True,
        },
        headers=auth_headers,
    )

    assert response.status_code == 503
    assert _error_code(response) == "EVIDENCE_ROOT_NOT_CONFIGURED"


def test_shadow_status_is_absent_when_no_session_has_run(client: TestClient) -> None:
    response = client.get("/api/shadow/status")

    assert response.status_code == 404
    assert _error_code(response) == "SHADOW_SESSION_NOT_CONFIGURED"


def test_shadow_control_requires_idempotency_and_a_real_session(
    client: TestClient,
    auth_headers: dict[str, str],
) -> None:
    missing_key = client.post(
        "/api/shadow/control",
        json={"action": "start", "speed_multiplier": 5},
        headers=auth_headers,
    )
    assert missing_key.status_code == 422
    assert _error_code(missing_key) == "IDEMPOTENCY_KEY_REQUIRED"

    missing_session = client.post(
        "/api/shadow/control",
        json={"action": "start", "speed_multiplier": 5},
        headers={**auth_headers, "Idempotency-Key": "shadow-start-1"},
    )
    assert missing_session.status_code == 404
    assert _error_code(missing_session) == "SHADOW_SESSION_NOT_CONFIGURED"


def test_paper_campaign_is_absent_when_no_campaign_has_run(client: TestClient) -> None:
    response = client.get("/api/paper-pilot/campaign")

    assert response.status_code == 404
    assert _error_code(response) == "PAPER_CAMPAIGN_NOT_CONFIGURED"


def test_paper_order_requires_an_idempotency_key(
    client: TestClient,
    auth_headers: dict[str, str],
) -> None:
    response = client.post(
        "/api/paper-pilot/order",
        json={
            "campaign_id": "campaign_missing",
            "symbol": "INFY",
            "side": "BUY",
            "quantity": 1,
            "limit_price": 100,
        },
        headers=auth_headers,
    )

    assert response.status_code == 422
    assert _error_code(response) == "IDEMPOTENCY_KEY_REQUIRED"


def test_paper_order_never_fills_without_a_real_campaign(
    client: TestClient,
    auth_headers: dict[str, str],
) -> None:
    response = client.post(
        "/api/paper-pilot/order",
        json={
            "campaign_id": "campaign_missing",
            "symbol": "INFY",
            "side": "BUY",
            "quantity": 1,
            "limit_price": 100,
        },
        headers={**auth_headers, "Idempotency-Key": "paper-missing-campaign"},
    )

    assert response.status_code == 404
    assert _error_code(response) == "PAPER_CAMPAIGN_NOT_CONFIGURED"


def test_supervisor_refuses_reusing_a_key_for_a_different_payload() -> None:
    worker_supervisor = WorkerSupervisor()
    try:
        first = worker_supervisor.submit_operation(
            OperationType.CUSTOM,
            {"action": "sleep", "duration": 1.0},
            idempotency_key="one-intent",
        )

        with pytest.raises(ValueError, match="IDEMPOTENCY_KEY_REUSED"):
            worker_supervisor.submit_operation(
                OperationType.CUSTOM,
                {"action": "compute"},
                idempotency_key="one-intent",
            )

        assert worker_supervisor.get_operation(first.operation_id) is not None
    finally:
        worker_supervisor.shutdown()
