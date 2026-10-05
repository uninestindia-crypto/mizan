"""Bulk import of keys and secrets from dotenv files into the credential store.

The founder drops ``.env``, ``.env.local`` and friends onto Settings instead of pasting each key. This
module turns that upload into a reviewable plan, then writes only what was confirmed.

Three rules shape it:

* **A preview never carries a value.** :meth:`ImportPlan.as_dict` and ``repr`` report names, labels,
  statuses and file names. The values live in a field that is excluded from ``repr`` and never
  serialised, so a preview cannot leak a secret into a log line, a screenshot or a test failure.
* **Only names the store manages are written.** ``CredentialStore`` already refuses anything outside
  ``SECRETS``; the plan reports the rest as ``unmanaged`` instead of failing the whole upload.
* **Files merge the way other dotenv tools merge them**, so uploading ``.env`` and ``.env.local``
  together yields the value those tools would have used, whatever order the files were picked in.
"""

from __future__ import annotations

import os
import re
from collections.abc import Collection, Sequence
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

from quant_system.config.env import parse_env_text
from quant_system.server.v2.credentials import (
    MAX_SECRET_BYTES,
    SECRETS,
    CredentialError,
    CredentialStore,
)

__all__ = [
    "EnvFile",
    "ImportOutcome",
    "ImportPlan",
    "ImportRow",
    "ImportStatus",
    "apply_plan",
    "build_plan",
]

# A name that is safe to show back. Anything else is counted, never echoed, because a malformed line
# can carry a secret in what the parser took to be its name.
_ECHOABLE_NAME = re.compile(r"^[A-Za-z_][A-Za-z0-9_]{0,63}$")
_SPECS = {spec.name: spec for spec in SECRETS}


class ImportStatus(StrEnum):
    NEW = "new"  # managed, not saved yet
    REPLACE = "replace"  # managed, saved with a different value
    SAME = "same"  # managed, saved with this exact value
    EMPTY = "empty"  # managed, but the file leaves it blank
    TOO_LONG = "too_long"  # managed, but Windows Credential Manager cannot hold it
    UNMANAGED = "unmanaged"  # a name QuantOS does not store


_WRITABLE = frozenset({ImportStatus.NEW, ImportStatus.REPLACE})


@dataclass(frozen=True, slots=True)
class EnvFile:
    name: str
    text: str


@dataclass(frozen=True, slots=True)
class ImportRow:
    name: str
    label: str | None
    group: str | None
    status: ImportStatus
    source: str | None
    shadowed: tuple[str, ...] = ()

    def as_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "label": self.label,
            "group": self.group,
            "status": self.status.value,
            "source": self.source,
            "shadowed": list(self.shadowed),
        }


@dataclass(frozen=True, slots=True)
class ImportOutcome:
    name: str
    outcome: str  # "saved", "refused" or "not_selected"
    message: str | None = None

    def as_dict(self) -> dict[str, Any]:
        return {"name": self.name, "outcome": self.outcome, "message": self.message}


@dataclass(frozen=True, slots=True)
class ImportPlan:
    rows: tuple[ImportRow, ...]
    files: tuple[dict[str, Any], ...]
    unrecognised_lines: int
    # Excluded from repr so an accidental log of the plan cannot print a secret.
    values: dict[str, str] = field(default_factory=dict, repr=False)

    def as_dict(self) -> dict[str, Any]:
        counts = {status.value: 0 for status in ImportStatus}
        for row in self.rows:
            counts[row.status.value] += 1
        return {
            "files": list(self.files),
            "rows": [row.as_dict() for row in self.rows],
            "summary": counts,
            "unrecognised_lines": self.unrecognised_lines,
        }


def _precedence(file_name: str) -> int:
    """Rank a dotenv file the way other tools do: base < mode < local < mode-local."""
    base = file_name.replace("\\", "/").rsplit("/", 1)[-1].lower()
    rest = base.removeprefix(".env") if base.startswith(".env") else ""
    is_local = rest.endswith(".local")
    has_mode = rest.removesuffix(".local") not in ("", ".")
    return (1 if has_mode else 0) + (2 if is_local else 0)


def _clean_text(text: str) -> str:
    return text.removeprefix("\ufeff")


@dataclass(slots=True)
class _Merged:
    """Every assignment found, before it is compared with anything saved."""

    # name -> (value, file) for each non-blank assignment, in precedence order; the last one wins.
    candidates: dict[str, list[tuple[str, str]]] = field(default_factory=dict)
    seen: set[str] = field(default_factory=set)
    summaries: list[dict[str, Any]] = field(default_factory=list)
    unrecognised: int = 0


def _absorb(merged: _Merged, file: EnvFile) -> None:
    """Fold one file's assignments into ``merged``."""
    recognised = 0
    for name, value in parse_env_text(_clean_text(file.text), inline_comments=True).items():
        if not _ECHOABLE_NAME.match(name):
            merged.unrecognised += 1
            continue
        merged.seen.add(name)
        recognised += 1
        if value.strip():  # a blank never hides a real value from another file
            merged.candidates.setdefault(name, []).append((value, file.name))
    merged.summaries.append({"name": file.name, "keys": recognised})


def _merge(files: Sequence[EnvFile]) -> _Merged:
    """Read every file in dotenv precedence order, whatever order they were picked in."""
    merged = _Merged()
    for _, file in sorted(enumerate(files), key=lambda pair: (_precedence(pair[1].name), pair[0])):
        _absorb(merged, file)
    return merged


def _status(name: str, found: tuple[str, str] | None, store: CredentialStore) -> ImportStatus:
    """Classify one name against what the credential store already holds."""
    if name not in _SPECS:
        return ImportStatus.UNMANAGED
    if found is None:
        return ImportStatus.EMPTY
    value = found[0].strip()
    if len(value.encode("utf-8")) > MAX_SECRET_BYTES:
        return ImportStatus.TOO_LONG
    current = store.get(name)
    if current is None:
        return ImportStatus.NEW
    return ImportStatus.SAME if current.strip() == value else ImportStatus.REPLACE


def _losers(options: list[tuple[str, str]], found: tuple[str, str] | None) -> tuple[str, ...]:
    """Files that set the name to something other than the winning value."""
    if found is None:
        return ()
    winner = found[0].strip()
    return tuple(dict.fromkeys(file for value, file in options if value.strip() != winner))


def _row(
    name: str, options: list[tuple[str, str]], store: CredentialStore
) -> tuple[ImportRow, str | None]:
    """The review row for one name, and the value to save if the row is writable."""
    found = options[-1] if options else None
    status = _status(name, found, store)
    spec = _SPECS.get(name)
    row = ImportRow(
        name=name,
        label=spec.label if spec else None,
        group=spec.group if spec else None,
        status=status,
        source=found[1] if found else None,
        shadowed=_losers(options, found),
    )
    value = found[0].strip() if found is not None and status in _WRITABLE else None
    return row, value


def build_plan(files: Sequence[EnvFile], store: CredentialStore) -> ImportPlan:
    """Merge the files by precedence and classify every name against what is already saved."""
    merged = _merge(files)
    managed = [spec.name for spec in SECRETS if spec.name in merged.seen]
    unmanaged = sorted(name for name in merged.seen if name not in _SPECS)
    rows: list[ImportRow] = []
    values: dict[str, str] = {}
    for name in (*managed, *unmanaged):
        row, value = _row(name, merged.candidates.get(name, []), store)
        rows.append(row)
        if value is not None:
            values[name] = value
    return ImportPlan(tuple(rows), tuple(merged.summaries), merged.unrecognised, values)


def apply_plan(
    plan: ImportPlan, store: CredentialStore, names: Collection[str] | None
) -> list[ImportOutcome]:
    """Save the plan's writable rows, limited to ``names`` when given. One refusal never stops the rest."""
    outcomes: list[ImportOutcome] = []
    for row in plan.rows:
        if row.status not in _WRITABLE:
            continue
        if names is not None and row.name not in names:
            outcomes.append(ImportOutcome(row.name, "not_selected"))
            continue
        value = plan.values[row.name]
        try:
            store.set(row.name, value)
        except CredentialError as err:
            outcomes.append(ImportOutcome(row.name, "refused", str(err)))
            continue
        os.environ[row.name] = value
        outcomes.append(ImportOutcome(row.name, "saved"))
    return outcomes
