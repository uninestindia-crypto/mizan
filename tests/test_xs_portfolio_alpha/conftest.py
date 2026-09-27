"""Pytest configuration and custom marker registration for XS Portfolio Alpha tests."""

from __future__ import annotations

import pytest


def pytest_configure(config: pytest.Config) -> None:
    """Register custom markers for tier-based test filtering."""
    config.addinivalue_line("markers", "tier1: Tier 1 Feature Coverage tests")
    config.addinivalue_line("markers", "tier2: Tier 2 Boundary & Corner Case tests")
    config.addinivalue_line("markers", "tier3: Tier 3 Cross-Feature Interaction tests")
    config.addinivalue_line("markers", "tier4: Tier 4 Real-World Scenario Acceptance tests")
