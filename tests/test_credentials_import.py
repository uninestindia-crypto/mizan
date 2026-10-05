"""Bulk import of keys from dotenv files: parsing, precedence, preview, apply, and secrecy."""

from __future__ import annotations

import json
import os
from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from quant_system.config.env import parse_env_text
from quant_system.server.app import app
from quant_system.server.v2 import paths, router
from quant_system.server.v2.credentials import MAX_SECRET_BYTES, SECRETS, CredentialStore
from quant_system.server.v2.env_import import (
    EnvFile,
    ImportStatus,
    apply_plan,
    build_plan,
)

# Deliberately fake values. Each carries a distinctive marker so a leak is easy to grep for.
UPSTOX = "fake-upstox-token-MARK1"
OPENAI = "fake-openai-key-MARK2"
ANTHROPIC = "fake-anthropic-key-MARK3"
OLD_VALUE = "fake-old-value-MARK4"
LOCAL_WINS = "fake-from-local-MARK5"
SENTINELS = (UPSTOX, OPENAI, ANTHROPIC, OLD_VALUE, LOCAL_WINS)

MANAGED_NAMES = tuple(spec.name for spec in SECRETS)


class _MemoryCredentialApi:
    """In-memory stand-in for the Windows credential API, so the tests run on any platform."""

    def __init__(self) -> None:
        self.items: dict[str, str] = {}

    def read(self, target: str) -> str | None:
        return self.items.get(target)

    def write(self, target: str, value: str) -> None:
        self.items[target] = value

    def delete(self, target: str) -> bool:
        return self.items.pop(target, None) is not None


def _store() -> CredentialStore:
    store = CredentialStore(prefix="test:")
    store._api = _MemoryCredentialApi()  # type: ignore[assignment]
    return store


@pytest.fixture(autouse=True)
def _clean_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    """Start every test with no managed secret in the environment, and restore it afterwards.

    Applying a plan writes ``os.environ``. ``delenv`` alone records nothing for a name that is absent, so
    a value written by a test would outlive it. Setting then deleting makes monkeypatch own the restore.
    """
    for name in MANAGED_NAMES:
        monkeypatch.setenv(name, "placeholder")
        monkeypatch.delenv(name)


def _rows(plan_rows: object) -> dict[str, ImportStatus]:
    return {row.name: row.status for row in plan_rows}  # type: ignore[attr-defined]


# ------------------------------------------------------------------------------------- parsing


def test_inline_comments_are_stripped_only_when_asked() -> None:
    text = "A=abc # note\nB=\"a # b\" # note\nC='x'\nD=abc#def\nexport E=1\n"
    plain = parse_env_text(text)
    assert plain["A"] == "abc # note"
    imported = parse_env_text(text, inline_comments=True)
    assert imported == {"A": "abc", "B": "a # b", "C": "x", "D": "abc#def", "E": "1"}


def test_a_comment_after_an_empty_value_does_not_become_the_value() -> None:
    # Template files carry lines like `KEY= # paste your key here`; that is a blank, not a key.
    text = "A= # paste your key here\nB=#kept-as-value\nC=\n"
    assert parse_env_text(text, inline_comments=True) == {"A": "", "B": "#kept-as-value", "C": ""}
    plan = build_plan(
        [EnvFile(".env.example", "OPENAI_API_KEY= # paste your key here\n")], _store()
    )
    assert _rows(plan.rows) == {"OPENAI_API_KEY": ImportStatus.EMPTY}


# ---------------------------------------------------------------------------------- the plan


def test_plan_classifies_every_kind_of_line() -> None:
    store = _store()
    store.set("OPENAI_API_KEY", OPENAI)  # identical -> same
    store.set("GROQ_API_KEY", OLD_VALUE)  # different -> replace
    too_long = "x" * (MAX_SECRET_BYTES + 1)
    text = (
        f"UPSTOX_ACCESS_TOKEN={UPSTOX}\n"
        f"OPENAI_API_KEY={OPENAI}\n"
        f"GROQ_API_KEY={LOCAL_WINS}\n"
        "GEMINI_API_KEY=\n"
        f"HF_TOKEN={too_long}\n"
        "SOME_OTHER_SETTING=1\n"
        "AWS_BEARER_TOKEN_BEDROCK=1\n"
    )
    plan = build_plan([EnvFile(".env", text)], store)
    assert _rows(plan.rows) == {
        "UPSTOX_ACCESS_TOKEN": ImportStatus.NEW,
        "OPENAI_API_KEY": ImportStatus.SAME,
        "GROQ_API_KEY": ImportStatus.REPLACE,
        "GEMINI_API_KEY": ImportStatus.EMPTY,
        "HF_TOKEN": ImportStatus.TOO_LONG,
        "SOME_OTHER_SETTING": ImportStatus.UNMANAGED,
        "AWS_BEARER_TOKEN_BEDROCK": ImportStatus.UNMANAGED,
    }


def test_managed_rows_carry_label_and_group_and_keep_catalogue_order() -> None:
    text = f"OPENAI_API_KEY={OPENAI}\nUPSTOX_ACCESS_TOKEN={UPSTOX}\n"
    plan = build_plan([EnvFile(".env", text)], _store())
    assert [row.name for row in plan.rows] == ["UPSTOX_ACCESS_TOKEN", "OPENAI_API_KEY"]
    assert plan.rows[0].group == "Upstox (Default)"
    assert plan.rows[0].label == "Upstox access token"


def test_local_file_beats_base_file_and_the_loser_is_named() -> None:
    files = [
        EnvFile(".env.local", f"OPENAI_API_KEY={LOCAL_WINS}\n"),
        EnvFile(".env", f"OPENAI_API_KEY={OLD_VALUE}\nGROQ_API_KEY={ANTHROPIC}\n"),
    ]
    store = _store()
    plan = build_plan(files, store)
    openai = next(row for row in plan.rows if row.name == "OPENAI_API_KEY")
    assert openai.source == ".env.local"
    assert openai.shadowed == (".env",)
    groq = next(row for row in plan.rows if row.name == "GROQ_API_KEY")
    assert groq.source == ".env" and groq.shadowed == ()
    apply_plan(plan, store, None)
    assert store.get("OPENAI_API_KEY") == LOCAL_WINS
    assert store.get("GROQ_API_KEY") == ANTHROPIC


def test_precedence_is_by_dotenv_convention_not_by_upload_order() -> None:
    names = [".env.production.local", ".env.local", ".env.production", ".env"]
    files = [EnvFile(name, f"OPENAI_API_KEY=fake-from-{name}\n") for name in names]
    plan = build_plan(files, _store())
    row = plan.rows[0]
    assert row.source == ".env.production.local"
    assert set(row.shadowed) == {".env.local", ".env.production", ".env"}


def test_a_blank_value_in_a_later_file_does_not_hide_a_real_one() -> None:
    files = [
        EnvFile(".env", f"OPENAI_API_KEY={OPENAI}\n"),
        EnvFile(".env.local", "OPENAI_API_KEY=\n"),
    ]
    plan = build_plan(files, _store())
    assert _rows(plan.rows) == {"OPENAI_API_KEY": ImportStatus.NEW}
    assert plan.rows[0].source == ".env"


def test_byte_order_mark_and_windows_line_endings_do_not_break_the_first_key() -> None:
    text = f"\ufeffUPSTOX_ACCESS_TOKEN={UPSTOX}\r\nOPENAI_API_KEY={OPENAI}\r\n"
    plan = build_plan([EnvFile(".env", text)], _store())
    assert _rows(plan.rows) == {
        "UPSTOX_ACCESS_TOKEN": ImportStatus.NEW,
        "OPENAI_API_KEY": ImportStatus.NEW,
    }


def test_a_malformed_name_is_counted_but_never_echoed() -> None:
    # A line like this could carry a secret in what looks like its "name".
    text = f"fake-secret-in-name-MARK7 spaced=value\nOPENAI_API_KEY={OPENAI}\n"
    plan = build_plan([EnvFile(".env", text)], _store())
    payload = json.dumps(plan.as_dict())
    assert "MARK7" not in payload
    assert plan.unrecognised_lines == 1


def test_plan_never_exposes_a_value_in_its_dict_or_repr() -> None:
    text = f"UPSTOX_ACCESS_TOKEN={UPSTOX}\nSOME_OTHER_SETTING={OLD_VALUE}\n"
    plan = build_plan([EnvFile(".env", text)], _store())
    rendered = " ".join((json.dumps(plan.as_dict()), repr(plan), str(plan.rows)))
    assert not any(sentinel in rendered for sentinel in SENTINELS)


# -------------------------------------------------------------------------------------- apply


def test_apply_saves_new_and_changed_keys_and_exports_them_to_the_environment() -> None:
    store = _store()
    store.set("GROQ_API_KEY", OLD_VALUE)
    text = f"UPSTOX_ACCESS_TOKEN={UPSTOX}\nGROQ_API_KEY={LOCAL_WINS}\nOPENAI_API_KEY={OPENAI}\n"
    plan = build_plan([EnvFile(".env", text)], store)
    results = apply_plan(plan, store, None)
    assert [(r.outcome, r.name) for r in results] == [
        ("saved", "UPSTOX_ACCESS_TOKEN"),
        ("saved", "OPENAI_API_KEY"),
        ("saved", "GROQ_API_KEY"),
    ]
    assert store.get("UPSTOX_ACCESS_TOKEN") == UPSTOX
    assert store.get("GROQ_API_KEY") == LOCAL_WINS
    assert os.environ["OPENAI_API_KEY"] == OPENAI


def test_apply_honours_the_selection_and_leaves_the_rest_untouched() -> None:
    store = _store()
    text = f"UPSTOX_ACCESS_TOKEN={UPSTOX}\nOPENAI_API_KEY={OPENAI}\n"
    plan = build_plan([EnvFile(".env", text)], store)
    results = apply_plan(plan, store, {"OPENAI_API_KEY"})
    assert [(r.outcome, r.name) for r in results] == [
        ("not_selected", "UPSTOX_ACCESS_TOKEN"),
        ("saved", "OPENAI_API_KEY"),
    ]
    assert store.get("UPSTOX_ACCESS_TOKEN") is None
    assert "UPSTOX_ACCESS_TOKEN" not in os.environ


def test_apply_never_writes_unmanaged_empty_same_or_oversized_rows() -> None:
    store = _store()
    store.set("OPENAI_API_KEY", OPENAI)
    text = (
        f"OPENAI_API_KEY={OPENAI}\nGEMINI_API_KEY=\nSOME_OTHER_SETTING=1\n"
        f"HF_TOKEN={'x' * (MAX_SECRET_BYTES + 1)}\n"
    )
    plan = build_plan([EnvFile(".env", text)], store)
    results = apply_plan(plan, store, set(_rows(plan.rows)))
    assert results == []
    assert "SOME_OTHER_SETTING" not in os.environ and "HF_TOKEN" not in os.environ
    assert store.get("GEMINI_API_KEY") is None and store.get("HF_TOKEN") is None


def test_a_selected_name_that_is_not_in_the_files_is_ignored() -> None:
    store = _store()
    plan = build_plan([EnvFile(".env", f"OPENAI_API_KEY={OPENAI}\n")], store)
    results = apply_plan(plan, store, {"OPENAI_API_KEY", "PATH"})
    assert [r.name for r in results] == ["OPENAI_API_KEY"]
    assert "PATH" not in {r.name for r in results}


# ------------------------------------------------------------------------------------ the API


@pytest.fixture()
def client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[TestClient]:
    monkeypatch.setenv("QUANTOS_APP_ROOT", str(tmp_path / "app"))
    monkeypatch.setattr(paths, "fixed_drive_roots", lambda: [])
    monkeypatch.setattr(paths, "_user_folders", lambda: [])
    monkeypatch.setattr(paths, "data_scan", paths.DataFolderScan())
    router.reset_services()
    router.services().credentials = _store()
    with TestClient(app, base_url="http://localhost:8000") as test_client:
        yield test_client
    router.reset_services()


@pytest.fixture()
def headers(client: TestClient) -> dict[str, str]:
    token = client.get("/api/v1/csrf-token").json()["csrf_token"]
    return {"X-CSRF-Token": token}


def _body(text: str, **extra: object) -> dict[str, object]:
    return {"files": [{"name": ".env", "text": text}], **extra}


def test_the_default_call_is_a_preview_and_writes_nothing(
    client: TestClient, headers: dict[str, str]
) -> None:
    reply = client.post(
        "/api/v2/credentials/import", json=_body(f"OPENAI_API_KEY={OPENAI}\n"), headers=headers
    )
    assert reply.status_code == 200
    body = reply.json()
    assert body["dry_run"] is True and body["available"] is True
    assert [row["status"] for row in body["rows"]] == ["new"]
    assert "results" not in body
    assert router.services().credentials.get("OPENAI_API_KEY") is None


def test_apply_saves_and_returns_status_without_any_secret(
    client: TestClient, headers: dict[str, str]
) -> None:
    text = (
        f"UPSTOX_ACCESS_TOKEN={UPSTOX}\nOPENAI_API_KEY={OPENAI}\nSOME_OTHER_SETTING={OLD_VALUE}\n"
    )
    reply = client.post(
        "/api/v2/credentials/import", json=_body(text, dry_run=False), headers=headers
    )
    assert reply.status_code == 200
    body = reply.json()
    saved = [r["name"] for r in body["results"] if r["outcome"] == "saved"]
    assert saved == ["UPSTOX_ACCESS_TOKEN", "OPENAI_API_KEY"]
    stored = {s["name"]: s["stored"] for s in body["secrets"]}
    assert stored["UPSTOX_ACCESS_TOKEN"] and stored["OPENAI_API_KEY"]
    rendered = reply.text + client.get("/api/v2/credentials").text
    assert not any(sentinel in rendered for sentinel in SENTINELS)
    assert os.environ["UPSTOX_ACCESS_TOKEN"] == UPSTOX


def test_apply_with_names_saves_only_those(client: TestClient, headers: dict[str, str]) -> None:
    text = f"UPSTOX_ACCESS_TOKEN={UPSTOX}\nOPENAI_API_KEY={OPENAI}\n"
    reply = client.post(
        "/api/v2/credentials/import",
        json=_body(text, dry_run=False, names=["OPENAI_API_KEY"]),
        headers=headers,
    )
    assert reply.status_code == 200
    credentials = router.services().credentials
    assert credentials.get("OPENAI_API_KEY") == OPENAI
    assert credentials.get("UPSTOX_ACCESS_TOKEN") is None


def test_apply_is_refused_when_the_credential_store_is_unavailable(
    client: TestClient, headers: dict[str, str]
) -> None:
    unavailable = CredentialStore(prefix="test:")
    unavailable._api = None
    router.services().credentials = unavailable
    reply = client.post(
        "/api/v2/credentials/import",
        json=_body(f"OPENAI_API_KEY={OPENAI}\n", dry_run=False),
        headers=headers,
    )
    assert reply.status_code == 400
    assert reply.json()["error"]["code"] == "CREDENTIAL_REFUSED"
    assert "OPENAI_API_KEY" not in os.environ
    # Previewing still works, and says that saving will not.
    preview = client.post(
        "/api/v2/credentials/import", json=_body(f"OPENAI_API_KEY={OPENAI}\n"), headers=headers
    )
    assert preview.status_code == 200 and preview.json()["available"] is False


def test_import_requires_the_csrf_token(client: TestClient) -> None:
    reply = client.post("/api/v2/credentials/import", json=_body("OPENAI_API_KEY=x\n"))
    assert reply.status_code in (400, 403)
    assert reply.json()["error"]["code"] == "CSRF_TOKEN_MISSING"


def test_oversized_or_too_many_files_are_rejected_without_echoing_the_input(
    client: TestClient, headers: dict[str, str]
) -> None:
    huge = f"OPENAI_API_KEY={OPENAI}\n" + "#" * 300_000
    reply = client.post("/api/v2/credentials/import", json=_body(huge), headers=headers)
    assert reply.status_code == 422
    assert OPENAI not in reply.text
    many = {"files": [{"name": f".env{i}", "text": "A=1\n"} for i in range(25)]}
    assert client.post("/api/v2/credentials/import", json=many, headers=headers).status_code == 422
