"""The No-Terminal Law for user-facing text in the Copilot and live-price code.

Traders and investors are not programmers (AGENTS.md, "No-Terminal Law"). Any message these packages can show a
person must say what to *click*, never what to type, edit or set, and must not use a developer's words. Strings meant
for the model, for logs, and plain identifiers are not user-facing and are skipped.
"""

from __future__ import annotations

import ast
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1] / "src" / "quant_system"
SETTINGS_SCREEN = (
    Path(__file__).resolve().parents[1] / "frontend" / "src" / "pages" / "Settings.tsx"
)
PACKAGES = [ROOT / "copilot", ROOT / "live"]
# The three files that put the Copilot and the live prices on the wire; every message they send reaches a screen.
FILES = [
    ROOT / "server" / "v2" / "copilot_routes.py",
    ROOT / "server" / "v2" / "copilot_wiring.py",
    ROOT / "server" / "v2" / "live_routes.py",
]
# These two modules write the instructions the app sends to an AI model, and they tell it to answer in a JSON
# object, naming the tools it may use. A model's reply goes through the guard before anyone reads it, so these words
# are never shown. Every other rule below still applies to them.
MODEL_FACING = {"copilot/agent.py", "copilot/verify_opinion.py"}

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
    "restart": re.compile(r"\brestart (quantos|the app)\b", re.IGNORECASE),
}
# Words for developers. They are banned in what a person reads, but a model is told to use some of them.
DEVELOPER_WORDS = {
    "a developer's word": re.compile(r"\bAPI\b|\bJSON\b|\bschema\b|\bbackend\b|\bendpoint\b", re.I),
    # lower_case_words_joined_by_underscores inside a sentence: a tool name, a screen key, a field name
    "a name from the code": re.compile(r"(?<![\w.{/-])[a-z][a-z0-9]*(?:_[a-z0-9]+)+(?![\w(}])"),
}
ALL_RULES = {**FORBIDDEN, **DEVELOPER_WORDS}

# Text that is code, not a message: a database statement.
_SQL = re.compile(r"^\s*(CREATE|SELECT|INSERT|UPDATE|DELETE|DROP|ALTER|PRAGMA|WITH)\b")
# One capitalised word ("Retry", "Unavailable.") reads as a label or a message. Anything else without a space is an
# identifier: a key ("settings_keys"), a path, a code such as UNVERIFIED_SAMPLE, a symbol.
_LABEL = re.compile(r"^[A-Z][a-z]+[.!?]?$")


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


def _is_message(text: str) -> bool:
    """A sentence or a label a person could read, as opposed to an identifier or code."""
    stripped = text.strip()
    if _SQL.match(stripped):
        return False
    return " " in stripped or bool(_LABEL.match(stripped))


def _source_files() -> list[Path]:
    found = [path for package in PACKAGES if package.is_dir() for path in package.rglob("*.py")]
    return sorted(found + [path for path in FILES if path.is_file()])


def _messages() -> list[tuple[str, int, str]]:
    found: list[tuple[str, int, str]] = []
    for path in _source_files():
        tree = ast.parse(path.read_text(encoding="utf-8"))
        skip = _docstring_ids(tree) | _logging_arg_ids(tree)
        for node in ast.walk(tree):
            if not (isinstance(node, ast.Constant) and isinstance(node.value, str)):
                continue
            if id(node) not in skip and _is_message(node.value):  # not a docstring or a log line
                found.append((path.relative_to(ROOT).as_posix(), node.lineno, node.value))
    return found


def _strip_prompt_markup(text: str) -> str:
    """Messages for the model may name tags such as <untrusted_data>; those are not shown to a person."""
    return re.sub(r"</?[a-z_]+>", "", text)


def _offenders(rule: str) -> list[str]:
    pattern = ALL_RULES[rule]
    skipped = MODEL_FACING if rule in DEVELOPER_WORDS else set()
    return [
        f"{path}:{line}: {text[:90]!r}"
        for path, line, text in _messages()
        if path not in skipped and pattern.search(_strip_prompt_markup(text))
    ]


def test_the_scan_actually_finds_messages_in_every_place_it_is_meant_to_look() -> None:
    messages = _messages()
    assert len(messages) > 10
    seen = {path for path, _, _ in messages}
    assert {
        "server/v2/copilot_routes.py",
        "server/v2/copilot_wiring.py",
        "server/v2/live_routes.py",
    } <= seen
    assert any(path.startswith("copilot/") for path in seen) and any(
        path.startswith("live/") for path in seen
    )


@pytest.mark.parametrize("rule", sorted(ALL_RULES))
def test_no_user_facing_message_uses_a_terminal_a_file_edit_a_code_setting_or_a_developers_word(
    rule: str,
) -> None:
    offenders = _offenders(rule)
    assert offenders == [], f"{rule}: say what to click instead\n" + "\n".join(offenders)


@pytest.mark.parametrize(
    ("rule", "text"),
    [
        ("a name from the code", "Open settings_keys to add one."),
        ("a name from the code", "Ask the stock_facts tool."),
        ("a developer's word", "The API refused the request."),
        ("a developer's word", "Your JSON file is broken."),
        ("a developer's word", "The schema changed."),
        ("a developer's word", "The backend is down."),
        ("a developer's word", "That endpoint is gone."),
        ("restart", "Restart QuantOS and ask again."),
        ("terminal", "Open a terminal."),
    ],
)
def test_the_rules_catch_what_they_are_meant_to_catch(rule: str, text: str) -> None:
    assert ALL_RULES[rule].search(text)


@pytest.mark.parametrize(
    "text",
    [
        "Open Settings, then Accounts and keys.",
        "Show the facts about {symbol}.",
        "Close QuantOS, open it again and ask once more.",
        "Add your Upstox key in Settings, then Accounts and keys.",
    ],
)
def test_the_rules_leave_plain_sentences_alone(text: str) -> None:
    assert not any(pattern.search(text) for pattern in ALL_RULES.values())


@pytest.mark.parametrize(
    ("text", "is_message"),
    [
        ("Open Settings, then Accounts and keys.", True),
        ("Unavailable", True),
        ("Retry.", True),
        ("settings_keys", False),  # a key
        ("UNVERIFIED_SAMPLE", False),  # a code
        ("/settings/accounts", False),  # a path
        ("stock_facts", False),  # a name
        ("TCS", False),  # a symbol
        ("SELECT * FROM agents WHERE id = ?", False),  # a database statement
    ],
)
def test_only_text_a_person_could_read_is_scanned(text: str, is_message: bool) -> None:
    assert _is_message(text) is is_message


def _settings_tabs() -> set[str]:
    source = SETTINGS_SCREEN.read_text(encoding="utf-8")
    block = source[
        source.index("const SECTIONS") : source.index("];", source.index("const SECTIONS"))
    ]
    return {tab.lower().replace("&", "and") for tab in re.findall(r'label: "([^"]+)"', block)}


def _tabs_named_in_messages() -> list[tuple[str, int, str]]:
    return [
        (path, line, match.lower())
        for path, line, text in _messages()
        for match in re.findall(r"Settings, then ([A-Z][A-Za-z ]*?)(?:[.,]|$)", text)
    ]


def _unknown_tabs() -> list[str]:
    tabs = _settings_tabs()
    return [f"{p}:{n}: {tab!r}" for p, n, tab in _tabs_named_in_messages() if tab not in tabs]


def test_the_settings_screen_has_the_tabs_the_scan_below_relies_on() -> None:
    assert {"market data", "accounts and keys"} <= _settings_tabs()


def test_some_message_names_a_settings_tab_so_the_check_below_has_something_to_check() -> None:
    assert len(_tabs_named_in_messages()) > 3


def test_every_message_sends_people_to_a_settings_tab_that_exists() -> None:
    wrong = _unknown_tabs()
    assert wrong == [], "these messages name a Settings tab that does not exist:\n" + "\n".join(
        wrong
    )
