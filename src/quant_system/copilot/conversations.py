"""Saved Copilot chats: kept on this computer, so a person can close the panel, come back, and carry on.

Each chat is a titled list of messages. The assistant's messages also keep what it looked at and the buttons it
offered, so an old chat reads exactly as it did. Nothing leaves this computer.
"""

from __future__ import annotations

import json
import sqlite3
import threading
import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

__all__ = [
    "MAX_CONVERSATIONS",
    "MAX_MESSAGES",
    "Conversation",
    "ConversationDetail",
    "ConversationError",
    "ConversationStore",
    "StoredMessage",
]

MAX_CONVERSATIONS = 200
MAX_MESSAGES = 400
MAX_MESSAGE_CHARS = 20_000
MAX_META_CHARS = 50_000
MAX_TITLE = 80
AUTO_TITLE = 60
DEFAULT_TITLE = "New chat"
PREVIEW_CHARS = 120
Meta = dict[str, Any]

_SCHEMA = """
CREATE TABLE IF NOT EXISTS conversations(
    id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    agent_id TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS conversation_messages(
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    conversation_id TEXT NOT NULL,
    role TEXT NOT NULL,
    content TEXT NOT NULL,
    meta TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS conversation_messages_by_chat ON conversation_messages(conversation_id, id);
"""
_LIST_ALL = "SELECT * FROM conversations ORDER BY updated_at DESC, rowid DESC LIMIT ?"
_LIST_MATCHING = (
    "SELECT * FROM conversations WHERE title LIKE ? ESCAPE '\\' OR id IN "
    "(SELECT conversation_id FROM conversation_messages WHERE content LIKE ? ESCAPE '\\') "
    "ORDER BY updated_at DESC, rowid DESC LIMIT ?"
)


class ConversationError(ValueError):
    """A refusal with a sentence a person can read as it is."""


def _now() -> str:
    return datetime.now(UTC).isoformat(timespec="microseconds")


def _squash(text: str) -> str:
    return " ".join(text.split())


def _like(text: str) -> str:
    """Text to search for, with the characters that mean something to LIKE made literal."""
    escaped = text.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    return f"%{escaped}%"


@dataclass(frozen=True, slots=True)
class Conversation:
    id: str
    title: str
    agent_id: str | None
    created_at: str
    updated_at: str
    message_count: int = 0
    preview: str = ""

    def as_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "title": self.title,
            "agent_id": self.agent_id,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "message_count": self.message_count,
            "preview": self.preview,
        }


@dataclass(frozen=True, slots=True)
class StoredMessage:
    role: str
    content: str
    meta: dict[str, Any] = field(default_factory=dict)
    created_at: str = ""

    def as_dict(self) -> dict[str, Any]:
        return {
            "role": self.role,
            "content": self.content,
            "meta": self.meta,
            "created_at": self.created_at,
        }


@dataclass(frozen=True, slots=True)
class ConversationDetail:
    id: str
    title: str
    agent_id: str | None
    created_at: str
    updated_at: str
    messages: tuple[StoredMessage, ...]

    def as_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "title": self.title,
            "agent_id": self.agent_id,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "messages": [m.as_dict() for m in self.messages],
        }


def _meta_text(meta: Meta) -> str:
    text = json.dumps(meta, default=str, ensure_ascii=False)
    return text if len(text) <= MAX_META_CHARS else "{}"


def _meta_of(text: str) -> dict[str, Any]:
    try:
        loaded = json.loads(text)
    except ValueError:
        return {}
    return loaded if isinstance(loaded, dict) else {}


class ConversationStore:
    def __init__(self, path: Path) -> None:
        self.path = path
        self._lock = threading.Lock()
        path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as conn:
            conn.executescript(_SCHEMA)

    @contextmanager
    def _connect(self) -> Iterator[sqlite3.Connection]:
        conn = sqlite3.connect(self.path, timeout=10, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()

    # ---------------------------------------------------------------------------------- reading

    def _summary(self, conn: sqlite3.Connection, row: sqlite3.Row) -> Conversation:
        count = conn.execute(
            "SELECT COUNT(*) FROM conversation_messages WHERE conversation_id = ?", (row["id"],)
        ).fetchone()[0]
        last = conn.execute(
            "SELECT content FROM conversation_messages WHERE conversation_id = ? ORDER BY id DESC LIMIT 1",
            (row["id"],),
        ).fetchone()
        return Conversation(
            id=str(row["id"]),
            title=str(row["title"]),
            agent_id=row["agent_id"],
            created_at=str(row["created_at"]),
            updated_at=str(row["updated_at"]),
            message_count=int(count),
            preview=_squash(str(last["content"]))[:PREVIEW_CHARS] if last else "",
        )

    def list(self, query: str = "", limit: int = 100) -> list[Conversation]:
        """Newest first. With ``query``, only chats whose title or any message contains it."""
        text = query.strip()
        sql, args = (_LIST_MATCHING, [_like(text)] * 2) if text else (_LIST_ALL, [])
        with self._connect() as conn:
            return [
                self._summary(conn, row) for row in conn.execute(sql, [*args, limit]).fetchall()
            ]

    def get(self, conversation_id: str) -> ConversationDetail | None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM conversations WHERE id = ?", (conversation_id,)
            ).fetchone()
            if row is None:
                return None
            rows = conn.execute(
                "SELECT role, content, meta, created_at FROM conversation_messages "
                "WHERE conversation_id = ? ORDER BY id",
                (conversation_id,),
            ).fetchall()
        messages = tuple(
            StoredMessage(
                str(r["role"]), str(r["content"]), _meta_of(str(r["meta"])), str(r["created_at"])
            )
            for r in rows
        )
        return ConversationDetail(
            str(row["id"]),
            str(row["title"]),
            row["agent_id"],
            str(row["created_at"]),
            str(row["updated_at"]),
            messages,
        )

    # ---------------------------------------------------------------------------------- writing

    def create(self, title: str = "", agent_id: str | None = None) -> Conversation:
        chat_id, now = uuid.uuid4().hex[:16], _now()
        with self._lock, self._connect() as conn:
            conn.execute(
                "INSERT INTO conversations(id, title, agent_id, created_at, updated_at) VALUES (?,?,?,?,?)",
                (chat_id, _squash(title)[:AUTO_TITLE] or DEFAULT_TITLE, agent_id, now, now),
            )
            self._prune(conn)
        return Conversation(
            chat_id, _squash(title)[:AUTO_TITLE] or DEFAULT_TITLE, agent_id, now, now
        )

    def _prune(self, conn: sqlite3.Connection) -> None:
        """Keep the newest ``MAX_CONVERSATIONS`` chats; the oldest go, with their messages."""
        doomed = [
            str(r["id"])
            for r in conn.execute(
                "SELECT id FROM conversations ORDER BY updated_at DESC, rowid DESC LIMIT -1 OFFSET ?",
                (MAX_CONVERSATIONS,),
            )
        ]
        for chat_id in doomed:
            conn.execute("DELETE FROM conversation_messages WHERE conversation_id = ?", (chat_id,))
            conn.execute("DELETE FROM conversations WHERE id = ?", (chat_id,))

    def append(self, conversation_id: str, role: str, content: str, meta: Meta) -> None:
        if role not in ("user", "assistant"):
            raise ConversationError("Only you and the assistant can speak in a chat.")
        with self._lock, self._connect() as conn:
            row = conn.execute(
                "SELECT title FROM conversations WHERE id = ?", (conversation_id,)
            ).fetchone()
            if row is None:
                raise ConversationError("That chat no longer exists. Start a new chat.")
            count = conn.execute(
                "SELECT COUNT(*) FROM conversation_messages WHERE conversation_id = ?",
                (conversation_id,),
            ).fetchone()[0]
            if count >= MAX_MESSAGES:
                raise ConversationError("This chat is full. Start a new chat.")
            now = _now()
            conn.execute(
                "INSERT INTO conversation_messages(conversation_id, role, content, meta, created_at) "
                "VALUES (?,?,?,?,?)",
                (conversation_id, role, content[:MAX_MESSAGE_CHARS], _meta_text(meta), now),
            )
            title = row["title"]
            if role == "user" and count == 0 and title == DEFAULT_TITLE:
                title = _squash(content)[:AUTO_TITLE] or DEFAULT_TITLE
            conn.execute(
                "UPDATE conversations SET title = ?, updated_at = ? WHERE id = ?",
                (title, now, conversation_id),
            )

    def rename(self, conversation_id: str, title: str) -> ConversationDetail | None:
        clean = _squash(title)
        if not 1 <= len(clean) <= MAX_TITLE:
            raise ConversationError(f"Give the chat a name of 1 to {MAX_TITLE} characters.")
        with self._lock, self._connect() as conn:
            changed = conn.execute(
                "UPDATE conversations SET title = ? WHERE id = ?", (clean, conversation_id)
            ).rowcount
        return self.get(conversation_id) if changed else None

    def delete(self, conversation_id: str) -> bool:
        with self._lock, self._connect() as conn:
            conn.execute(
                "DELETE FROM conversation_messages WHERE conversation_id = ?", (conversation_id,)
            )
            return (
                conn.execute("DELETE FROM conversations WHERE id = ?", (conversation_id,)).rowcount
                > 0
            )

    def clear(self) -> int:
        with self._lock, self._connect() as conn:
            count = int(conn.execute("SELECT COUNT(*) FROM conversations").fetchone()[0])
            conn.execute("DELETE FROM conversation_messages")
            conn.execute("DELETE FROM conversations")
        return count
