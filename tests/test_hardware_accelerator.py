"""Unit and integration tests for hardware accelerator detection and switching."""

from __future__ import annotations

import uuid
from typing import Any

import pytest
from fastapi.testclient import TestClient

from quant_system.server.app import app
from quant_system.server.v2 import router
from quant_system.server.v2.credentials import CredentialStore
from quant_system.server.v2.hardware import (
    detect_hardware_topology,
    topology_to_dict,
)


@pytest.fixture
def client() -> Any:
    router.reset_services()
    test_store = CredentialStore(prefix=f"QuantOS-test-{uuid.uuid4().hex[:8]}:")
    router.services().credentials = test_store
    with TestClient(app, base_url="http://localhost:8000") as test_client:
        yield test_client
    router.reset_services()


def test_hardware_topology_structure_and_devices() -> None:
    topo = detect_hardware_topology("auto")
    assert topo.active_target == "auto"
    assert topo.effective_target in ("npu", "gpu", "cpu")
    assert topo.platform
    assert topo.architecture

    devices = topo.devices
    assert "npu" in devices
    assert "gpu" in devices
    assert "cpu" in devices

    assert devices["cpu"].available is True
    assert devices["cpu"].category == "CPU"
    assert devices["gpu"].category == "GPU"
    assert devices["npu"].category == "NPU"

    # Local models
    model_ids = [m.id for m in topo.local_models]
    assert "cand_mizan_v1" in model_ids
    assert "cand_ridge_v1" in model_ids
    assert "embeddinggemma-2" in model_ids


def test_hardware_topology_target_switching() -> None:
    for target in ("auto", "cpu", "gpu", "npu"):
        topo = detect_hardware_topology(target)  # type: ignore[arg-type]
        assert topo.active_target == target
        if target == "cpu":
            assert topo.effective_target == "cpu"
        d = topology_to_dict(topo)
        assert d["active_target"] == target
        assert isinstance(d["devices"], dict)
        assert isinstance(d["local_models"], list)


def test_hardware_api_get_and_post(client: TestClient) -> None:
    res = client.get("/api/v2/system/hardware")
    assert res.status_code == 200
    data = res.json()
    assert "active_target" in data
    assert "effective_target" in data
    assert "devices" in data
    assert "local_models" in data
    assert len(data["local_models"]) >= 3

    # Get CSRF token
    csrf = client.get("/api/v1/csrf-token").json()["csrf_token"]
    headers = {"X-CSRF-Token": csrf}

    # Switch to CPU
    switch_res = client.post("/api/v2/system/hardware", json={"target": "cpu"}, headers=headers)
    assert switch_res.status_code == 200
    switch_data = switch_res.json()
    assert switch_data["active_target"] == "cpu"
    assert switch_data["effective_target"] == "cpu"

    # Verify state persistence
    re_get = client.get("/api/v2/system/hardware")
    assert re_get.json()["active_target"] == "cpu"

    # Invalid target is refused
    bad_res = client.post(
        "/api/v2/system/hardware", json={"target": "quantum_core"}, headers=headers
    )
    assert bad_res.status_code == 422
