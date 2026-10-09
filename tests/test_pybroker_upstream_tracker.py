"""Unit tests for PyBroker upstream tracker and AI agent hand-off briefing."""

from __future__ import annotations

from typing import Any
from unittest.mock import patch

from quant_system.research.pybroker_upstream_tracker import (
    PyBrokerUpstreamTracker,
    generate_agent_handoff_prompt,
    is_version_newer,
    parse_version_tuple,
)


def test_version_parsing_and_comparison() -> None:
    assert parse_version_tuple("2.0.1") == (2, 0, 1)
    assert parse_version_tuple("v2.1.0") == (2, 1, 0)
    assert parse_version_tuple("invalid") is None

    assert is_version_newer("2.1.0", "2.0.1") is True
    assert is_version_newer("2.0.1", "2.0.1") is False
    assert is_version_newer("1.9.9", "2.0.1") is False


def test_agent_handoff_prompt_generation() -> None:
    prompt = generate_agent_handoff_prompt(
        latest_ver="2.1.0",
        current_ver="2.0.1",
        release_url="https://github.com/edtechre/pybroker/releases/tag/v2.1.0",
        release_notes="Added new Numba indicator kernels and multi-asset optimization.",
    )
    assert "PyBroker (v2.1.0)" in prompt
    assert "current in Mizan: v2.0.1" in prompt
    assert "https://github.com/edtechre/pybroker/releases/tag/v2.1.0" in prompt
    assert "pytest tests/test_pybroker_adapter.py" in prompt


def test_tracker_detects_update_and_creates_briefing(tmp_path: Any) -> None:
    mock_release = {
        "version": "2.2.0",
        "url": "https://github.com/edtechre/pybroker/releases/tag/v2.2.0",
        "summary": "Major speedups in walkforward ML training.",
        "source": "github",
    }

    tracker = PyBrokerUpstreamTracker(current_version="2.0.1")

    with patch(
        "quant_system.research.pybroker_upstream_tracker.fetch_from_pypi", return_value=mock_release
    ):
        result = tracker.check(force=True)

    assert result["update_available"] is True
    assert result["latest_version"] == "2.2.0"
    assert result["current_version"] == "2.0.1"
    assert result["briefing_path"] is not None
    assert result["handoff_prompt"] is not None


def test_tracker_when_up_to_date() -> None:
    mock_release = {
        "version": "2.0.1",
        "url": "https://github.com/edtechre/pybroker",
        "summary": "Current release",
        "source": "pypi",
    }

    tracker = PyBrokerUpstreamTracker(current_version="2.0.1")

    with patch(
        "quant_system.research.pybroker_upstream_tracker.fetch_from_pypi", return_value=mock_release
    ):
        result = tracker.check(force=True)

    assert result["update_available"] is False
    assert result["latest_version"] == "2.0.1"


def test_pybroker_api_route() -> None:
    from fastapi.testclient import TestClient

    from quant_system.server.app import app

    client = TestClient(app, base_url="http://localhost:8000")
    resp = client.get("/api/v2/updates/pybroker")
    assert resp.status_code == 200
    data = resp.json()
    assert "current_version" in data
    assert "update_available" in data
