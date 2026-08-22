"""Regression tests for project ``.env`` loading.

The defect these guard: nothing in the project loaded ``.env``, so a correctly configured
credential was invisible to ``UpstoxClient``, to the provenance credential gate, and to the AI
provider key pool. A user filling in ``.env`` saw "not configured" and, for market data, a
non-retryable ``PROVIDER_UNAUTHORIZED`` raised before any request was issued.
"""

from __future__ import annotations

import os
from collections.abc import Iterator
from pathlib import Path

import pytest

from quant_system.config import default_env_path, load_env_file, parse_env_text
from quant_system.data.provenance import market_data_credentials_configured
from quant_system.data.upstox import UpstoxClient

ACCESS_TOKEN = "UPSTOX_ACCESS_TOKEN"


@pytest.fixture(autouse=True)
def restore_environment() -> Iterator[None]:
    """Restore ``os.environ`` after every test in this module.

    ``load_env_file`` writes to ``os.environ`` directly, and pytest's
    ``monkeypatch.delenv(name, raising=False)`` records nothing when the variable is absent. A
    variable this module creates would therefore survive teardown and leak into unrelated tests.
    That leak is not hypothetical: it was observed breaking
    ``test_upstox_data.py::test_upstox_historical_request_without_token_raises_typed_error`` and
    ``test_upstox_v3_acquisition.py::test_missing_access_token_returns_unauthorized_without_transport_call``,
    both of which assert an unauthenticated client.
    """
    saved = dict(os.environ)
    yield
    os.environ.clear()
    os.environ.update(saved)


def _write_env(directory: Path, body: str) -> Path:
    path = directory / ".env"
    path.write_text(body, encoding="utf-8")
    return path


def test_configured_env_file_reaches_the_upstox_client(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The original defect: a filled-in .env left the client unauthenticated."""
    monkeypatch.delenv(ACCESS_TOKEN, raising=False)
    env_path = _write_env(tmp_path, f"{ACCESS_TOKEN}=token-value-under-test\n")

    assert UpstoxClient().is_authenticated is False

    assert load_env_file(env_path) == (ACCESS_TOKEN,)

    assert UpstoxClient().is_authenticated is True


def test_configured_env_file_reaches_the_provenance_credential_gate(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The same defect reported the opposite of the truth to the user."""
    monkeypatch.delenv(ACCESS_TOKEN, raising=False)
    env_path = _write_env(tmp_path, f"{ACCESS_TOKEN}=token-value-under-test\n")

    assert market_data_credentials_configured() is False

    load_env_file(env_path)

    assert market_data_credentials_configured() is True


def test_existing_environment_wins_over_the_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A stale file must never shadow a deliberately exported credential."""
    monkeypatch.setenv(ACCESS_TOKEN, "exported-value")
    env_path = _write_env(tmp_path, f"{ACCESS_TOKEN}=file-value\n")

    assert load_env_file(env_path) == ()
    assert os.environ[ACCESS_TOKEN] == "exported-value"


def test_override_lets_the_file_win_when_the_caller_asks(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv(ACCESS_TOKEN, "exported-value")
    env_path = _write_env(tmp_path, f"{ACCESS_TOKEN}=file-value\n")

    assert load_env_file(env_path, override=True) == (ACCESS_TOKEN,)
    assert os.environ[ACCESS_TOKEN] == "file-value"


def test_only_restricts_which_names_are_loaded(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A caller that spawns subprocesses can decline to widen credential exposure."""
    monkeypatch.delenv(ACCESS_TOKEN, raising=False)
    monkeypatch.delenv("UNRELATED_PROVIDER_KEY", raising=False)
    env_path = _write_env(tmp_path, f"{ACCESS_TOKEN}=token\nUNRELATED_PROVIDER_KEY=other-secret\n")

    assert load_env_file(env_path, only=(ACCESS_TOKEN,)) == (ACCESS_TOKEN,)
    assert os.getenv("UNRELATED_PROVIDER_KEY") is None


def test_loader_returns_names_never_values(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A live credential must not travel in a return value that could reach a log or artifact."""
    monkeypatch.delenv(ACCESS_TOKEN, raising=False)
    env_path = _write_env(tmp_path, f"{ACCESS_TOKEN}=super-secret-token\n")

    loaded = load_env_file(env_path)

    assert loaded == (ACCESS_TOKEN,)
    assert "super-secret-token" not in repr(loaded)


def test_absent_file_is_not_an_error(tmp_path: Path) -> None:
    """Deployments configured through real environment variables have no .env."""
    assert load_env_file(tmp_path / ".env") == ()


def test_parsing_handles_comments_blanks_quotes_and_export() -> None:
    parsed = parse_env_text(
        "\n".join(
            (
                "# a comment",
                "",
                "PLAIN=value",
                'DOUBLE="quoted value"',
                "SINGLE='quoted value'",
                "export EXPORTED=exported-value",
                "  SPACED  =  padded  ",
                "WITH_EQUALS=a=b",
            )
        )
    )

    assert parsed == {
        "PLAIN": "value",
        "DOUBLE": "quoted value",
        "SINGLE": "quoted value",
        "EXPORTED": "exported-value",
        "SPACED": "padded",
        "WITH_EQUALS": "a=b",
    }


def test_malformed_line_is_skipped_rather_than_raising() -> None:
    """A broken local config line must not take down a run that may not need that variable."""
    assert parse_env_text("this line has no equals sign\nGOOD=value\n") == {"GOOD": "value"}


def test_default_env_path_finds_the_nearest_file(tmp_path: Path) -> None:
    nested = tmp_path / "a" / "b"
    nested.mkdir(parents=True)
    _write_env(tmp_path, "ROOT=1\n")
    nearest = _write_env(tmp_path / "a", "NEARER=1\n")

    assert default_env_path(nested) == nearest


def test_default_env_path_returns_none_when_there_is_no_file(tmp_path: Path) -> None:
    nested = tmp_path / "a" / "b"
    nested.mkdir(parents=True)

    assert default_env_path(nested) is None
