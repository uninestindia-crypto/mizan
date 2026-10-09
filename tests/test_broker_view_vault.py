"""The broker view's key lives in its own Credential Manager entry and can never reach the process environment."""

from __future__ import annotations

import os

import pytest

from quant_system.server.v2.credentials import (
    BROKER_VIEW_KEY,
    SECRETS,
    CredentialError,
    CredentialStore,
    ScopedCredentialStore,
)
from tests.broker_fakes import SENTINEL

PREFIX = "QuantOS-test-isolation:BrokerView:"


class FakeApi:
    def __init__(self) -> None:
        self.entries: dict[str, str] = {}

    def write(self, target: str, value: str) -> None:
        self.entries[target] = value

    def read(self, target: str) -> str | None:
        return self.entries.get(target)

    def delete(self, target: str) -> bool:
        return self.entries.pop(target, None) is not None


def scoped(api: FakeApi | None) -> ScopedCredentialStore:
    store = ScopedCredentialStore(frozenset({BROKER_VIEW_KEY}), prefix=PREFIX)
    store._api = api  # type: ignore[assignment]
    return store


def test_a_key_round_trips_under_its_own_prefix() -> None:
    api = FakeApi()
    store = scoped(api)
    store.set(BROKER_VIEW_KEY, SENTINEL)
    assert api.entries == {PREFIX + BROKER_VIEW_KEY: SENTINEL}
    assert store.get(BROKER_VIEW_KEY) == SENTINEL
    assert store.delete(BROKER_VIEW_KEY) is True
    assert store.get(BROKER_VIEW_KEY) is None and store.delete(BROKER_VIEW_KEY) is False


def test_saving_the_key_changes_nothing_in_the_process_environment() -> None:
    before = dict(os.environ)
    store = scoped(FakeApi())
    store.set(BROKER_VIEW_KEY, SENTINEL)
    store.get(BROKER_VIEW_KEY)
    assert dict(os.environ) == before


def test_the_key_is_not_one_of_the_secrets_the_app_lists_or_copies_into_the_environment() -> None:
    assert BROKER_VIEW_KEY not in {spec.name for spec in SECRETS}
    api = FakeApi()
    scoped(api).set(BROKER_VIEW_KEY, SENTINEL)
    general = CredentialStore(prefix=PREFIX)
    general._api = api  # type: ignore[assignment]
    assert BROKER_VIEW_KEY not in {entry["name"] for entry in general.status()}
    assert general.apply_to_environment() == []
    assert BROKER_VIEW_KEY not in os.environ


def test_a_name_outside_its_set_is_refused_for_every_operation() -> None:
    store = scoped(FakeApi())
    for call in (
        lambda: store.get("UPSTOX_ACCESS_TOKEN"),
        lambda: store.set("UPSTOX_ACCESS_TOKEN", "x"),
        lambda: store.delete("UPSTOX_ACCESS_TOKEN"),
    ):
        with pytest.raises(CredentialError):
            call()


@pytest.mark.parametrize("value", ["", "   ", "has space", "line\nbreak", "café", "x" * 3000])
def test_a_value_the_store_would_mangle_is_refused_with_a_message_a_person_can_act_on(
    value: str,
) -> None:
    store = scoped(FakeApi())
    with pytest.raises(CredentialError):
        store.set(BROKER_VIEW_KEY, value)


def test_where_windows_credential_manager_is_missing_it_says_so_and_reads_nothing() -> None:
    store = scoped(None)
    assert store.available is False
    assert store.get(BROKER_VIEW_KEY) is None and store.delete(BROKER_VIEW_KEY) is False
    with pytest.raises(CredentialError):
        store.set(BROKER_VIEW_KEY, SENTINEL)


def test_the_general_store_still_checks_values_the_same_way_after_sharing_the_check() -> None:
    general = CredentialStore(prefix=PREFIX)
    general._api = FakeApi()  # type: ignore[assignment]
    general.set("OPENAI_API_KEY", " sk-test-1 ")
    assert general.get("OPENAI_API_KEY") == "sk-test-1"
    with pytest.raises(CredentialError, match="unusual character"):
        general.set("OPENAI_API_KEY", "has space")
    with pytest.raises(CredentialError, match="empty"):
        general.set("OPENAI_API_KEY", " ")
    with pytest.raises(CredentialError, match="not a secret"):
        general.set("NOT_A_SECRET", "x")
