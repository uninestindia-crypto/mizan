"""Tests for runtime data-source disclosure.

The governed Upstox client fails closed without a bearer token, so an uncredentialed runtime is
necessarily serving generated data. These cases prove that every operator-facing surface says so.
"""

from __future__ import annotations

import os

import pytest

from quant_system.data.market_data import UPSTOX_HISTORICAL_SOURCE
from quant_system.data.provenance import (
    ACCESS_TOKEN_ENV_VAR,
    API_KEY_ENV_VAR,
    RuntimeDataSource,
    describe,
    market_data_credentials_configured,
)
from quant_system.data.upstox import UpstoxClient

_ISOLATED_ENV_KEYS = ("TEMP", "TMP", "TMPDIR", "MPLCONFIGDIR", "PYTHONPYCACHEPREFIX")


@pytest.fixture
def restore_process_env() -> object:
    """Restore the environment keys that launcher drive-isolation rewrites globally."""
    saved = {key: os.environ.get(key) for key in _ISOLATED_ENV_KEYS}
    yield None
    for key, value in saved.items():
        if value is None:
            os.environ.pop(key, None)
        else:
            os.environ[key] = value


def test_env_var_names_match_the_client_that_reads_them(monkeypatch: pytest.MonkeyPatch) -> None:
    """The declared variable name must be the one UpstoxClient actually authenticates from.

    Asserted behaviourally rather than by string comparison so that a rename inside the certified
    Slice 1 client cannot silently desynchronise this module.
    """
    monkeypatch.delenv(ACCESS_TOKEN_ENV_VAR, raising=False)
    monkeypatch.delenv(API_KEY_ENV_VAR, raising=False)
    assert UpstoxClient().is_authenticated is False

    monkeypatch.setenv(ACCESS_TOKEN_ENV_VAR, "token-value-under-test")
    assert UpstoxClient().is_authenticated is True


@pytest.mark.parametrize(
    ("token_value", "expected"),
    [
        pytest.param(None, False, id="unset"),
        pytest.param("", False, id="empty"),
        pytest.param("   ", False, id="whitespace-only"),
        pytest.param("token-value-under-test", True, id="present"),
    ],
)
# test-allow: no-assertion - check-tests.mjs caseBody() truncates every multi-line Python signature, so the assertions below are invisible to it
def test_credential_presence_detection(
    monkeypatch: pytest.MonkeyPatch,
    token_value: str | None,
    expected: bool,
) -> None:
    if token_value is None:
        monkeypatch.delenv(ACCESS_TOKEN_ENV_VAR, raising=False)
    else:
        monkeypatch.setenv(ACCESS_TOKEN_ENV_VAR, token_value)

    assert market_data_credentials_configured() is expected


def test_credential_check_never_returns_the_secret(monkeypatch: pytest.MonkeyPatch) -> None:
    """Presence must be reported as a bool so a token cannot reach an evidence artifact."""
    monkeypatch.setenv(ACCESS_TOKEN_ENV_VAR, "super-secret-token")
    result = market_data_credentials_configured()

    assert isinstance(result, bool)
    assert "super-secret-token" not in str(result)


def test_real_source_label_matches_the_governed_vocabulary() -> None:
    """The live label must equal the Slice 1 manifest constant, not a parallel spelling."""
    assert RuntimeDataSource.UPSTOX_HISTORICAL == UPSTOX_HISTORICAL_SOURCE


def test_synthetic_disclosure_names_the_source_and_disclaims_market_meaning() -> None:
    disclosure = describe(RuntimeDataSource.SYNTHETIC)

    assert "SyntheticDataGenerator" in disclosure
    assert "not real market data" in disclosure
    assert "no predictive or historical claim" in disclosure


def test_real_disclosure_is_distinct_from_synthetic() -> None:
    assert describe(RuntimeDataSource.UPSTOX_HISTORICAL) != describe(RuntimeDataSource.SYNTHETIC)


# test-allow: no-assertion - check-tests.mjs caseBody() truncates every multi-line Python signature, so the assertions below are invisible to it
def test_launcher_warns_when_no_credentials_are_configured(
    monkeypatch: pytest.MonkeyPatch,
    restore_process_env: object,
) -> None:
    """A clean preflight must never imply that a live market-data connection exists."""
    import launcher

    monkeypatch.delenv(ACCESS_TOKEN_ENV_VAR, raising=False)
    passed, logs = launcher.run_prerequisite_checks()
    disclosure_lines = [line for line in logs if ACCESS_TOKEN_ENV_VAR in line]

    assert len(disclosure_lines) == 1
    assert disclosure_lines[0].startswith("[WARN]")
    assert str(RuntimeDataSource.SYNTHETIC) in disclosure_lines[0]
    assert passed is True, "absent credentials are a supported mode, not a boot failure"


# test-allow: no-assertion - check-tests.mjs caseBody() truncates every multi-line Python signature, so the assertions below are invisible to it
def test_launcher_reports_configured_credentials(
    monkeypatch: pytest.MonkeyPatch,
    restore_process_env: object,
) -> None:
    import launcher

    monkeypatch.setenv(ACCESS_TOKEN_ENV_VAR, "token-value-under-test")
    _, logs = launcher.run_prerequisite_checks()
    disclosure_lines = [line for line in logs if ACCESS_TOKEN_ENV_VAR in line]

    assert len(disclosure_lines) == 1
    assert disclosure_lines[0].startswith("[PASS]")
    assert "token-value-under-test" not in disclosure_lines[0]
