"""Saved chats through the app: a chat can be started, carried on after the panel was closed, found, renamed, deleted."""

from __future__ import annotations

import sqlite3
from typing import Any

import pytest
from fastapi.testclient import TestClient

from quant_system.copilot.conversations import ConversationStore
from tests import test_copilot_routes as _routes

client = _routes.client
headers = _routes.headers
ready = _routes.ready
lab = _routes.lab


def _start_chats(
    client: TestClient, headers: dict[str, str], questions: tuple[str, ...]
) -> list[str]:
    return [
        _chat(client, headers, q, conversation_id="new")[1]["conversation_id"] for q in questions
    ]


def _chat(
    client: TestClient, headers: dict[str, str], text: str, **extra: Any
) -> tuple[int, dict[str, Any]]:
    body = {"messages": [{"role": "user", "content": text}], **extra}
    response = client.post("/api/v2/copilot/chat", json=body, headers=headers)
    return response.status_code, dict(response.json())


def test_a_chat_with_no_chat_named_is_not_saved_so_older_screens_keep_working(
    ready: TestClient, headers: dict[str, str]
) -> None:
    status, body = _chat(ready, headers, "is AAA halal?")
    assert status == 200 and "conversation_id" not in body
    assert ready.get("/api/v2/copilot/conversations").json()["conversations"] == []


def test_asking_for_a_new_chat_saves_the_question_and_the_answer(
    ready: TestClient, headers: dict[str, str]
) -> None:
    status, body = _chat(ready, headers, "is AAA halal?", conversation_id="new")
    assert status == 200 and body["conversation_id"] and body["saved"] is True
    saved = ready.get(f"/api/v2/copilot/conversations/{body['conversation_id']}").json()
    assert saved["title"] == "is AAA halal?"
    assert [m["role"] for m in saved["messages"]] == ["user", "assistant"]
    assert saved["messages"][1]["content"] == body["reply"]


def test_what_the_assistant_looked_at_and_offered_is_kept_with_its_answer(
    ready: TestClient, headers: dict[str, str]
) -> None:
    _, body = _chat(ready, headers, "is AAA halal?", conversation_id="new")
    meta = ready.get(f"/api/v2/copilot/conversations/{body['conversation_id']}").json()["messages"][
        1
    ]["meta"]
    assert meta["mode"] == "built_in" and meta["steps"] and "proposals" in meta


def test_a_saved_chat_can_be_carried_on_where_it_stopped(
    ready: TestClient, headers: dict[str, str]
) -> None:
    _, first = _chat(ready, headers, "is AAA halal?", conversation_id="new")
    chat_id = first["conversation_id"]
    status, second = _chat(ready, headers, "how is AAA doing?", conversation_id=chat_id)
    assert status == 200 and second["conversation_id"] == chat_id
    saved = ready.get(f"/api/v2/copilot/conversations/{chat_id}").json()
    assert len(saved["messages"]) == 4 and saved["title"] == "is AAA halal?"
    assert len(ready.get("/api/v2/copilot/conversations").json()["conversations"]) == 1


def test_a_chat_that_no_longer_exists_is_said_so_and_nothing_is_answered_into_the_void(
    ready: TestClient, headers: dict[str, str]
) -> None:
    status, body = _chat(ready, headers, "hello", conversation_id="gone")
    assert status == 404 and body["error"]["code"] == "NOT_FOUND"
    assert "Start a new chat" in body["error"]["message"]


def test_the_chats_are_listed_newest_first_and_can_be_searched(
    ready: TestClient, headers: dict[str, str]
) -> None:
    _chat(ready, headers, "is AAA halal?", conversation_id="new")
    _chat(ready, headers, "show my watchlist", conversation_id="new")
    listed = ready.get("/api/v2/copilot/conversations").json()["conversations"]
    assert [c["title"] for c in listed] == ["show my watchlist", "is AAA halal?"]
    found = ready.get("/api/v2/copilot/conversations?q=halal").json()["conversations"]
    assert [c["title"] for c in found] == ["is AAA halal?"]


def test_a_blank_chat_can_be_started_and_named_later(
    ready: TestClient, headers: dict[str, str]
) -> None:
    created = ready.post("/api/v2/copilot/conversations", json={}, headers=headers)
    assert created.status_code == 201 and created.json()["title"] == "New chat"
    renamed = ready.put(
        f"/api/v2/copilot/conversations/{created.json()['id']}",
        json={"title": "Halal picks"},
        headers=headers,
    )
    assert renamed.status_code == 200 and renamed.json()["title"] == "Halal picks"


def test_a_bad_name_is_refused_in_plain_words(ready: TestClient, headers: dict[str, str]) -> None:
    chat_id = ready.post("/api/v2/copilot/conversations", json={}, headers=headers).json()["id"]
    refused = ready.put(
        f"/api/v2/copilot/conversations/{chat_id}", json={"title": "  "}, headers=headers
    )
    assert refused.status_code == 400 and "name" in refused.json()["error"]["message"]


def test_renaming_or_opening_a_chat_that_is_gone_is_a_plain_not_found(
    ready: TestClient, headers: dict[str, str]
) -> None:
    assert ready.get("/api/v2/copilot/conversations/gone").status_code == 404
    assert (
        ready.put(
            "/api/v2/copilot/conversations/gone", json={"title": "x"}, headers=headers
        ).status_code
        == 404
    )


def test_a_chat_can_be_deleted_and_all_chats_can_be_cleared(
    ready: TestClient, headers: dict[str, str]
) -> None:
    ids = _start_chats(ready, headers, ("one", "two", "three"))
    assert ready.delete(f"/api/v2/copilot/conversations/{ids[0]}", headers=headers).json() == {
        "deleted": True
    }
    assert (
        ready.delete(f"/api/v2/copilot/conversations/{ids[0]}", headers=headers).status_code == 404
    )
    assert ready.delete("/api/v2/copilot/conversations", headers=headers).json() == {"cleared": 2}
    assert ready.get("/api/v2/copilot/conversations").json()["conversations"] == []


def test_changing_chats_needs_the_security_token(ready: TestClient) -> None:
    assert ready.post("/api/v2/copilot/conversations", json={}).status_code in (401, 403)
    assert ready.delete("/api/v2/copilot/conversations").status_code in (401, 403)


def test_a_failure_to_save_never_costs_the_person_their_answer(
    ready: TestClient, headers: dict[str, str], monkeypatch: pytest.MonkeyPatch
) -> None:
    chat_id = ready.post("/api/v2/copilot/conversations", json={}, headers=headers).json()["id"]

    def broken(self: ConversationStore, *args: Any, **kwargs: Any) -> None:
        raise sqlite3.OperationalError("disk is full")

    monkeypatch.setattr(ConversationStore, "append", broken)
    status, body = _chat(ready, headers, "is AAA halal?", conversation_id=chat_id)
    assert status == 200 and body["reply"] and body["saved"] is False


def test_a_chat_that_is_full_still_answers_but_says_it_was_not_saved(
    ready: TestClient, headers: dict[str, str], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("quant_system.copilot.conversations.MAX_MESSAGES", 2)
    _, first = _chat(ready, headers, "is AAA halal?", conversation_id="new")
    status, second = _chat(ready, headers, "again", conversation_id=first["conversation_id"])
    assert status == 200 and second["reply"] and second["saved"] is False
    assert "Start a new chat" in second["saved_note"]
