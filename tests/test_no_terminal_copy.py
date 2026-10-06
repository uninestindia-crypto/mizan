"""The No-Terminal Law for user-facing text in the Copilot and live-price code.

Traders and investors are not programmers (AGENTS.md, "No-Terminal Law"). Any message these packages can show a
person must say what to *click*, never what to type, edit or set. Strings meant for the model, for logs, and plain
identifiers are not user-facing and are skipped.
"""

from __future__ import annotations

import ast
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1] / "src" / "quant_system"
PACKAGES = [ROOT / "copilot", ROOT / "live"]

FORBIDDEN = {
    "terminal": re.compile(r"\bterminal\b|\bconsole\b|command prompt", re.IGNORECASE),
    "command line": re.compile(
        r"command[- ]line|\bpowershell\b|\bnpm \b|\bpip install\b", re.IGNORECASE
    ),
    "environment variable": re.compile(r"environment variable|\.env\b|\benv var", re.IGNORECASE),
    "a setting written in code": re.compile(r"\b[A-Z][A-Z0-9]+_[A-Z0-9_]{2,}\b"),
    "edit a file": re.compile(
        r"\bedit (the |your |a )?(file|config)|\bconfig file\b|\brestart (the )?(service|server|engine)\b",
        re.IGNORECASE,
    ),
}


def _docstring_ids(tree: ast.AST) -> set[int]:
    ids: set[int] = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
            body = node.body
            if body and isinstance(body[0], ast.Expr) and isinstance(body[0].value, ast.Constant):
                ids.add(id(body[0].value))
    return ids


def _logging_arg_ids(tree: ast.AST) -> set[int]:
    ids: set[int] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
            owner = node.func.value
            if isinstance(owner, ast.Name) and owner.id in {"logger", "log", "logging"}:
                ids.update(id(n) for arg in node.args for n in ast.walk(arg))
    return ids


def _messages() -> list[tuple[str, int, str]]:
    found: list[tuple[str, int, str]] = []
    for package in PACKAGES:
        if not package.is_dir():
            continue
        for path in sorted(package.rglob("*.py")):
            tree = ast.parse(path.read_text(encoding="utf-8"))
            skip = _docstring_ids(tree) | _logging_arg_ids(tree)
            for node in ast.walk(tree):
                if not (isinstance(node, ast.Constant) and isinstance(node.value, str)):
                    continue
                if id(node) in skip or " " not in node.value.strip():
                    continue  # a docstring, a log line, or an identifier rather than a sentence
                found.append((str(path.relative_to(ROOT)), node.lineno, node.value))
    return found


def test_the_scan_actually_finds_messages() -> None:
    assert len(_messages()) > 10


def _offenders(pattern: re.Pattern[str]) -> list[str]:
    return [
        f"{path}:{line}: {text[:90]!r}"
        for path, line, text in _messages()
        if pattern.search(_strip_prompt_markup(text))
    ]


@pytest.mark.parametrize("rule", sorted(FORBIDDEN))
def test_no_user_facing_message_asks_for_a_terminal_a_file_edit_or_a_code_setting(
    rule: str,
) -> None:
    offenders = _offenders(FORBIDDEN[rule])
    assert offenders == [], f"{rule}: say what to click instead\n" + "\n".join(offenders)


def _strip_prompt_markup(text: str) -> str:
    """Messages for the model may name tools (snake_case) and tags; those are not shown to a person."""
    return re.sub(r"</?[a-z_]+>", "", text)
