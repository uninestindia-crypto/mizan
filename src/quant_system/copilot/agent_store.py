"""Assistants a person builds from a form: a name, what to focus on, which things it may look at, and its steps.

An assistant (the screen calls it an *agent* or *workflow*) is saved data, never code. It can only use the read-only
tools the person ticks, and its steps are plain-language requests run one after another. Validation returns
messages written for the form, each naming the field to fix.

One small SQLite file (``copilot.sqlite``) beside the app's other state.
"""

from __future__ import annotations

import json
import re
import sqlite3
import threading
import uuid
from collections.abc import Collection, Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

__all__ = ["AgentDraft", "AgentRejectedError", "AgentStore", "Problem", "SavedAgent", "validate"]

MAX_AGENTS = 30
MAX_STEPS = 8
NAME_CHARS = 60
DESCRIPTION_CHARS = 200
INSTRUCTION_CHARS = 1500
STEP_CHARS = 500
PLACEHOLDER = re.compile(r"\{([^{}]*)\}")
_SCHEMA = """
CREATE TABLE IF NOT EXISTS agents(
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    description TEXT NOT NULL,
    instructions TEXT NOT NULL,
    tools_json TEXT NOT NULL,
    steps_json TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
"""


@dataclass(frozen=True, slots=True)
class Problem:
    """One thing to fix on the form, in words for the person."""

    field: str
    message: str

    def as_dict(self) -> dict[str, str]:
        return {"field": self.field, "message": self.message}


class AgentRejectedError(Exception):
    def __init__(self, problems: list[Problem]) -> None:
        super().__init__("; ".join(p.message for p in problems))
        self.problems = problems


@dataclass(frozen=True, slots=True)
class AgentDraft:
    name: str
    description: str = ""
    instructions: str = ""
    tools: tuple[str, ...] = ()
    steps: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class SavedAgent:
    id: str
    name: str
    description: str
    instructions: str
    tools: tuple[str, ...]
    steps: tuple[str, ...]
    created_at: str
    updated_at: str

    @property
    def needs_symbol(self) -> bool:
        return any("{symbol}" in text for text in (*self.steps, self.instructions))

    def as_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "instructions": self.instructions,
            "tools": list(self.tools),
            "steps": list(self.steps),
            "needs_symbol": self.needs_symbol,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "built_in": False,
        }


def _too_long(field: str, text: str, limit: int, what: str) -> Problem | None:
    if len(text) <= limit:
        return None
    return Problem(field, f"Make the {what} shorter (up to {limit} letters).")


def _name_problem(name: str) -> Problem | None:
    if not name.strip():
        return Problem("name", "Give your agent a name.")
    return _too_long("name", name.strip(), NAME_CHARS, "name")


def _text_problems(draft: AgentDraft) -> list[Problem]:
    found = (
        _name_problem(draft.name),
        _too_long("description", draft.description, DESCRIPTION_CHARS, "description"),
        _too_long("instructions", draft.instructions, INSTRUCTION_CHARS, "instructions"),
    )
    return [problem for problem in found if problem]


def _step_problem(number: int, text: str) -> Problem | None:
    if not text.strip():
        return Problem("steps", f"Step {number} is empty. Write what to do, or remove the step.")
    if len(text) > STEP_CHARS:
        return Problem("steps", f"Step {number} is too long (up to {STEP_CHARS} letters).")
    other = [name for name in PLACEHOLDER.findall(text) if name != "symbol"]
    if other:
        return Problem(
            "steps",
            f"Step {number} uses {{{other[0]}}}. The only fill-in you can use is {{symbol}}.",
        )
    return None


_NO_STEPS = "Add at least one step, for example: Check {symbol} against the halal screener."


def _step_problems(steps: tuple[str, ...]) -> list[Problem]:
    if not steps:
        return [Problem("steps", _NO_STEPS)]
    if len(steps) > MAX_STEPS:
        return [Problem("steps", f"Use at most {MAX_STEPS} steps.")]
    found = [_step_problem(number, text) for number, text in enumerate(steps, start=1)]
    return [problem for problem in found if problem]


def _tool_problems(tools: tuple[str, ...], known: Collection[str]) -> list[Problem]:
    if not tools:
        return [Problem("tools", "Tick at least one thing this agent may look at.")]
    unknown = [name for name in tools if name not in known]
    return (
        [Problem("tools", "One of the ticked items is not available. Untick it and try again.")]
        if unknown
        else []
    )


def validate(draft: AgentDraft, known_tools: Collection[str]) -> list[Problem]:
    return [
        *_text_problems(draft),
        *_step_problems(draft.steps),
        *_tool_problems(draft.tools, known_tools),
    ]


def _now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


def _row_to_agent(row: sqlite3.Row) -> SavedAgent:
    return SavedAgent(
        id=str(row["id"]),
        name=str(row["name"]),
        description=str(row["description"]),
        instructions=str(row["instructions"]),
        tools=tuple(json.loads(row["tools_json"])),
        steps=tuple(json.loads(row["steps_json"])),
        created_at=str(row["created_at"]),
        updated_at=str(row["updated_at"]),
    )


class AgentStore:
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

    def agents(self) -> list[SavedAgent]:
        with self._connect() as conn:
            rows = conn.execute("SELECT * FROM agents ORDER BY created_at, id").fetchall()
        return [_row_to_agent(row) for row in rows]

    def get(self, agent_id: str) -> SavedAgent | None:
        with self._connect() as conn:
            row = conn.execute("SELECT * FROM agents WHERE id = ?", (agent_id,)).fetchone()
        return _row_to_agent(row) if row else None

    def create(self, draft: AgentDraft, known_tools: Collection[str]) -> SavedAgent:
        with self._lock:
            self._check(draft, known_tools, None)
            agent_id = uuid.uuid4().hex[:12]
            self._insert(agent_id, draft)
        return self._saved(agent_id)

    def _insert(self, agent_id: str, draft: AgentDraft) -> None:
        now = _now()
        with self._connect() as conn:
            conn.execute(
                "INSERT INTO agents VALUES (?,?,?,?,?,?,?,?)",
                (agent_id, *self._fields(draft), now, now),
            )

    def update(
        self, agent_id: str, draft: AgentDraft, known_tools: Collection[str]
    ) -> SavedAgent | None:
        with self._lock:
            if self.get(agent_id) is None:
                return None
            self._check(draft, known_tools, agent_id)
            name, description, instructions, tools, steps = self._fields(draft)
            with self._connect() as conn:
                conn.execute(
                    "UPDATE agents SET name=?, description=?, instructions=?, tools_json=?, steps_json=?, "
                    "updated_at=? WHERE id=?",
                    (name, description, instructions, tools, steps, _now(), agent_id),
                )
        return self._saved(agent_id)

    def delete(self, agent_id: str) -> bool:
        with self._lock, self._connect() as conn:
            return conn.execute("DELETE FROM agents WHERE id = ?", (agent_id,)).rowcount > 0

    # ------------------------------------------------------------------------------------------

    def _saved(self, agent_id: str) -> SavedAgent:
        saved = self.get(agent_id)
        assert saved is not None
        return saved

    @staticmethod
    def _fields(draft: AgentDraft) -> tuple[str, str, str, str, str]:
        return (
            draft.name.strip(),
            draft.description.strip(),
            draft.instructions.strip(),
            json.dumps(list(draft.tools)),
            json.dumps([step.strip() for step in draft.steps]),
        )

    def _check(self, draft: AgentDraft, known_tools: Collection[str], own_id: str | None) -> None:
        problems = validate(draft, known_tools)
        others = [a for a in self.agents() if a.id != own_id]
        if any(a.name.lower() == draft.name.strip().lower() for a in others):
            problems.append(
                Problem("name", "You already have an agent with that name. Choose another.")
            )
        if own_id is None and len(others) >= MAX_AGENTS:
            problems.append(
                Problem("name", f"You can keep up to {MAX_AGENTS} agents. Delete one first.")
            )
        if problems:
            raise AgentRejectedError(problems)
