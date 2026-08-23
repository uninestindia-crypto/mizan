"""The advisory layer observes; it never decides.

Observer mode enforced by discipline decays the first time someone is in a hurry. These tests
assert the boundary from the build: no governed decision path may import `quant_system.advisory`,
and the advisory package may not reach into governed modules either.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

SRC_ROOT = Path(__file__).resolve().parents[1] / "src" / "quant_system"

# Packages that decide, price, size, gate, or persist governed evidence. If any of them can import
# the advisory layer, an LLM opinion has acquired a route into a governed decision.
GOVERNED_PACKAGES = ("modeling", "evidence", "risk", "execution", "portfolio", "backtest")

ADVISORY_MODULE = "quant_system.advisory"


def _imported_modules(source_path: Path) -> set[str]:
    tree = ast.parse(source_path.read_text(encoding="utf-8"), filename=str(source_path))
    imported: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imported.add(alias.name)
        elif isinstance(node, ast.ImportFrom) and node.module is not None and node.level == 0:
            imported.add(node.module)
    return imported


def _python_files(package: str) -> list[Path]:
    package_root = SRC_ROOT / package
    if not package_root.exists():
        return []
    return sorted(package_root.rglob("*.py"))


def _governed_files() -> list[Path]:
    files: list[Path] = []
    for package in GOVERNED_PACKAGES:
        files.extend(_python_files(package))
    return files


def test_the_governed_packages_were_actually_found() -> None:
    """Guards the guard: an empty sweep would make every assertion below vacuously true."""
    assert len(_governed_files()) > 20


@pytest.mark.parametrize("source_path", _governed_files(), ids=lambda path: path.name)
def test_no_governed_module_imports_the_advisory_layer(source_path: Path) -> None:
    offending = {
        module
        for module in _imported_modules(source_path)
        if module == ADVISORY_MODULE or module.startswith(f"{ADVISORY_MODULE}.")
    }
    assert not offending, (
        f"{source_path.relative_to(SRC_ROOT)} imports {sorted(offending)}. "
        "Advisory records are non-authoritative and must not reach a governed decision path."
    )


@pytest.mark.parametrize("source_path", _python_files("advisory"), ids=lambda path: path.name)
def test_advisory_does_not_import_governed_modules(source_path: Path) -> None:
    forbidden = {f"quant_system.{package}" for package in GOVERNED_PACKAGES}
    offending = {
        module
        for module in _imported_modules(source_path)
        if any(module == root or module.startswith(f"{root}.") for root in forbidden)
    }
    assert not offending, (
        f"{source_path.relative_to(SRC_ROOT)} imports {sorted(offending)}. "
        "The advisory package is a leaf; it may observe the panel but not the governed stack."
    )


def test_advisory_package_is_non_empty() -> None:
    assert len(_python_files("advisory")) >= 5


# `strategies/` is deliberately outside GOVERNED_PACKAGES: it is where the panel is already
# consulted, so it is where observation has to attach. The import guard therefore cannot cover it,
# and the invariant that matters there is narrower — the strategy layer may WRITE advisory records
# but must never READ them back, because a record that can be read can influence a decision.
_JOURNAL_READ_APIS = ("read_entries", "verify_chain", "records")


@pytest.mark.parametrize("source_path", _python_files("strategies"), ids=lambda path: path.name)
def test_strategies_use_the_journal_write_only(source_path: Path) -> None:
    tree = ast.parse(source_path.read_text(encoding="utf-8"), filename=str(source_path))
    called = {
        node.func.attr
        for node in ast.walk(tree)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
    }
    offending = called.intersection(_JOURNAL_READ_APIS)
    assert not offending, (
        f"{source_path.relative_to(SRC_ROOT)} calls {sorted(offending)}. "
        "Advisory records are write-only from a strategy; reading one back would let a "
        "non-authoritative record influence a decision."
    )


def test_authority_is_a_single_valued_enum() -> None:
    """A second authority value would be the cheapest way to smuggle in a vote."""
    from quant_system.advisory import Authority

    assert [member.value for member in Authority] == ["NON_AUTHORITATIVE"]
