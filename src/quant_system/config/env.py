"""Load environment variables from a project ``.env`` file.

This project depends on no dotenv library, and three subsystems read credentials straight from the
process environment: the Upstox client, the provenance credential gate, and the AI provider key
pool. Without this module a correctly filled ``.env`` is invisible to all of them, and the product
reports "no credential configured" while the user is looking at the credential they configured.

Two rules govern the load, both deliberate:

* **The environment always wins.** A variable already present is never overwritten, so a value
  exported in the shell stays authoritative and a stale file cannot silently shadow it. Callers that
  genuinely want the file to win pass ``override=True``.
* **Values never leave this module.** :func:`load_env_file` returns the *names* it set and nothing
  else. Nothing here returns, logs, or prints a value, matching the discipline in
  ``provenance.market_data_credentials_configured``, which inspects presence only so that a live
  credential never reaches an evidence artifact.

Loading is explicit rather than performed on package import. Reading a file at import time would
make behaviour depend on an untracked local file, so a test that constructed an unauthenticated
client would pass in CI and fail on a developer machine that happened to have a ``.env``.
"""

from __future__ import annotations

import os
from pathlib import Path

__all__ = ["default_env_path", "load_env_file", "parse_env_text"]

_MAX_SEARCH_DEPTH = 5


def _strip_inline_comment(raw: str) -> str:
    """Drop a trailing ``# comment`` from one raw value, the way dotenv files written by other tools carry it.

    A quoted value ends at its closing quote, so ``"a # b" # note`` keeps ``a # b``. An unquoted value
    ends at the first ``#`` that follows whitespace, so ``abc#def`` (a token or URL fragment) is kept
    whole, while ``KEY= # paste it here`` is a blank rather than the value ``# paste it here``. A value
    whose opening quote never closes is returned unchanged rather than guessed at.
    """
    body = raw.lstrip()
    if body.startswith("#") and body != raw:
        return ""
    if body and body[0] in {'"', "'"}:
        closing = body.find(body[0], 1)
        if closing == -1:
            return body
        tail = body[closing + 1 :].strip()
        return body[: closing + 1] if not tail or tail.startswith("#") else body
    for index, char in enumerate(body):
        if char == "#" and index > 0 and body[index - 1].isspace():
            return body[:index].rstrip()
    return body


def parse_env_text(text: str, *, inline_comments: bool = False) -> dict[str, str]:
    """Parse dotenv text into name/value pairs.

    Accepts ``KEY=value``, tolerates a leading ``export``, ignores blank lines and ``#`` comments,
    and strips one layer of matching single or double quotes. A line without ``=`` is skipped rather
    than raising, because a malformed line in a local config file should not take down a run that
    may not even need the variable it was trying to set.

    ``inline_comments`` additionally drops a trailing ``# comment`` after a value. It is off by
    default because the startup loader documents "no trailing comment" in ``.env.example``; the
    bulk importer turns it on for files written by other tools.
    """
    values: dict[str, str] = {}
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        name, _, value = line.removeprefix("export ").partition("=")
        name = name.strip()
        if not name:
            continue
        value = (_strip_inline_comment(value) if inline_comments else value).strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in {'"', "'"}:
            value = value[1:-1]
        values[name] = value
    return values


def default_env_path(start: Path | None = None) -> Path | None:
    """Return the nearest ``.env`` at or above ``start``, or None if there is none.

    The search is bounded so that an application started from an arbitrary working directory cannot
    walk to the filesystem root picking up an unrelated file.
    """
    current = (start or Path.cwd()).resolve()
    for candidate in (current, *current.parents)[:_MAX_SEARCH_DEPTH]:
        env_path = candidate / ".env"
        if env_path.is_file():
            return env_path
    return None


def _read_env_text(path: Path | None) -> str | None:
    """Return the dotenv text, or None when there is nothing readable to load."""
    env_path = path or default_env_path()
    if env_path is None or not env_path.is_file():
        return None
    try:
        return env_path.read_text(encoding="utf-8")
    except OSError:
        # An unreadable local config file must not break a run that may not need it. The caller
        # discovers the absence the same way it would discover an absent file: an empty result.
        return None


def _is_applicable(name: str, *, wanted: set[str] | None, override: bool) -> bool:
    """Decide whether one parsed name should be written to the environment."""
    if wanted is not None and name not in wanted:
        return False
    return override or not os.getenv(name)


def load_env_file(
    path: Path | None = None,
    *,
    override: bool = False,
    only: tuple[str, ...] | None = None,
) -> tuple[str, ...]:
    """Load a dotenv file into ``os.environ`` and return the names that were set.

    Args:
        path: File to read. Defaults to the nearest ``.env`` at or above the working directory.
        override: When True, values in the file replace variables already in the environment.
            Defaults to False so the process environment stays authoritative.
        only: When given, restrict loading to these names. Useful for a caller that spawns
            subprocesses and does not want to widen the exposure of credentials it has no use for.

    Returns:
        The names set, sorted. Never the values. Returns an empty tuple when no file is found,
        which is the normal case for a deployment configured through real environment variables.
    """
    text = _read_env_text(path)
    if text is None:
        return ()
    wanted = set(only) if only is not None else None
    applied: list[str] = []
    for name, value in parse_env_text(text).items():
        if not _is_applicable(name, wanted=wanted, override=override):
            continue
        os.environ[name] = value
        applied.append(name)
    return tuple(sorted(applied))
