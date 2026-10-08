"""Tests for repository release tooling: bump_version, release_status, and release_notes."""

from __future__ import annotations

import importlib.util
import types
from pathlib import Path

import pytest

SCRIPTS_DIR = Path(__file__).resolve().parent.parent / "scripts"


def _load_script(module_name: str, file_name: str) -> types.ModuleType:
    """Dynamically import a non-packaged script from scripts directory."""
    script_path = SCRIPTS_DIR / file_name
    spec = importlib.util.spec_from_file_location(module_name, script_path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Could not load module {module_name} from {script_path}")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


bump_version = _load_script("bump_version", "bump_version.py")
release_status = _load_script("release_status", "release_status.py")
release_notes = _load_script("release_notes", "release_notes.py")


@pytest.fixture
def fake_tree(tmp_path: Path) -> Path:
    """Create a minimal fake repository tree with all six version carriers."""
    # 1. pyproject.toml with CRLF line endings to test preservation
    pyproject = tmp_path / "pyproject.toml"
    pyproject.write_bytes(
        b"[build-system]\r\n"
        b'requires = ["hatchling"]\r\n\r\n'
        b"[project]\r\n"
        b'name = "quant-system"\r\n'
        b'version = "1.0.0"\r\n'
        b'description = "Minimal test project"\r\n'
    )

    # 2. src/quant_system/__init__.py
    pkg_dir = tmp_path / "src" / "quant_system"
    pkg_dir.mkdir(parents=True)
    init_file = pkg_dir / "__init__.py"
    init_file.write_bytes(b'"""Package init."""\n\n__version__ = "1.0.0"\n')

    # 3. frontend/package.json
    frontend_dir = tmp_path / "frontend"
    frontend_dir.mkdir(parents=True)
    pkg_json = frontend_dir / "package.json"
    pkg_json.write_bytes(
        b'{\n  "name": "quantos-app",\n  "version": "1.0.0",\n  "private": true\n}\n'
    )

    # 4. frontend/package-lock.json
    lock_json = frontend_dir / "package-lock.json"
    lock_json.write_bytes(
        b"{\n"
        b'  "name": "quantos-app",\n'
        b'  "version": "1.0.0",\n'
        b'  "lockfileVersion": 3,\n'
        b'  "packages": {\n'
        b'    "": {\n'
        b'      "name": "quantos-app",\n'
        b'      "version": "1.0.0"\n'
        b"    }\n"
        b"  }\n"
        b"}\n"
    )

    # 5. src/quant_system/server/static/index.html
    static_dir = pkg_dir / "server" / "static"
    static_dir.mkdir(parents=True)
    index_html = static_dir / "index.html"
    index_html.write_bytes(
        b"<!DOCTYPE html>\n"
        b"<html>\n"
        b"<head><title>QuantOS Desktop v1.0.0</title></head>\n"
        b'<body><span class="brand-badge">v1.0.0</span></body>\n'
        b"</html>\n"
    )

    # 6. uv.lock
    uv_lock = tmp_path / "uv.lock"
    uv_lock.write_bytes(
        b"version = 1\n\n"
        b"[[package]]\n"
        b'name = "other-lib"\n'
        b'version = "0.5.0"\n\n'
        b"[[package]]\n"
        b'name = "quant-system"\n'
        b'version = "1.0.0"\n'
        b'source = { editable = "." }\n'
    )

    return tmp_path


def test_read_versions_all_present(fake_tree: Path) -> None:
    """Verify read_versions detects versions accurately across all six files."""
    versions = bump_version.read_versions(fake_tree)
    assert versions["pyproject.toml"] == "1.0.0"
    assert versions["src/quant_system/__init__.py"] == "1.0.0"
    assert versions["frontend/package.json"] == "1.0.0"
    assert versions["frontend/package-lock.json"] == "1.0.0"
    assert versions["src/quant_system/server/static/index.html"] == "1.0.0"
    assert versions["uv.lock"] == "1.0.0"


def test_check_invariants(fake_tree: Path) -> None:
    """Verify check reports no mismatches when consistent, and reports discrepancies."""
    # When all match
    mismatches = bump_version.check(fake_tree)
    assert mismatches == []

    # Discrepancy in frontend/package.json
    (fake_tree / "frontend" / "package.json").write_text(
        '{\n  "name": "quantos-app",\n  "version": "0.9.0"\n}\n', encoding="utf-8"
    )
    mismatches = bump_version.check(fake_tree)
    assert len(mismatches) == 1
    assert "frontend/package.json" in mismatches[0]

    # Missing file is ignored per specification
    (fake_tree / "frontend" / "package-lock.json").unlink()
    mismatches = bump_version.check(fake_tree)
    assert len(mismatches) == 1

    # Corrupt pattern in index.html is reported
    (fake_tree / "src" / "quant_system" / "server" / "static" / "index.html").write_text(
        "<html><body>No badge</body></html>", encoding="utf-8"
    )
    mismatches = bump_version.check(fake_tree)
    assert len(mismatches) == 2
    assert any("index.html: version pattern not found" in m for m in mismatches)


def test_bump_and_crlf_preservation(fake_tree: Path) -> None:
    """Verify bump rewrites files, preserves CRLF line endings, and synchronizes lockfiles."""
    changed = bump_version.bump(fake_tree, "1.1.0")
    assert len(changed) == 6

    # Verify versions updated everywhere
    versions = bump_version.read_versions(fake_tree)
    assert all(v == "1.1.0" for v in versions.values())

    # Verify CRLF line endings in pyproject.toml were preserved
    pyproject_bytes = (fake_tree / "pyproject.toml").read_bytes()
    assert b"\r\n" in pyproject_bytes
    assert b'version = "1.1.0"\r\n' in pyproject_bytes

    # Verify frontend/package-lock.json updated both top-level and package entry
    lock_text = (fake_tree / "frontend" / "package-lock.json").read_text(encoding="utf-8")
    assert '"version": "1.1.0"' in lock_text
    assert (
        '"packages": {\n    "": {\n      "name": "quantos-app",\n      "version": "1.1.0"'
        in lock_text
    )

    # Verify index.html updated all occurrences (title and badge)
    html_text = (fake_tree / "src" / "quant_system" / "server" / "static" / "index.html").read_text(
        encoding="utf-8"
    )
    assert "QuantOS Desktop v1.1.0" in html_text
    assert 'class="brand-badge">v1.1.0<' in html_text

    # Verify uv.lock updated only quant-system, not other packages
    uv_text = (fake_tree / "uv.lock").read_text(encoding="utf-8")
    assert 'name = "other-lib"\nversion = "0.5.0"' in uv_text
    assert 'name = "quant-system"\nversion = "1.1.0"' in uv_text

    # Consistency check passes
    assert bump_version.check(fake_tree) == []


def test_bump_validation_refusals(fake_tree: Path) -> None:
    """Verify bump rejects lower, equal, or malformed versions."""
    with pytest.raises(ValueError, match="strictly greater"):
        bump_version.bump(fake_tree, "0.9.0")

    with pytest.raises(ValueError, match="strictly greater"):
        bump_version.bump(fake_tree, "1.0.0")

    with pytest.raises(ValueError, match="Invalid version format"):
        bump_version.bump(fake_tree, "1.0")

    with pytest.raises(ValueError, match="Invalid version format"):
        bump_version.bump(fake_tree, "v1.1.0")

    with pytest.raises(ValueError, match="Invalid version format"):
        bump_version.bump(fake_tree, "1.1.0-beta")

    with pytest.raises(ValueError, match="Invalid version format"):
        bump_version.bump(fake_tree, "alpha")


def test_parse_subject() -> None:
    """Verify parse_subject extracts commit type and breaking indicator."""
    assert release_status.parse_subject("feat(api)!: add new endpoint") == ("feat", True)
    assert release_status.parse_subject("fix: resolve off-by-one error") == ("fix", False)
    assert release_status.parse_subject("perf(sim): cache factor calculation") == ("perf", False)
    assert release_status.parse_subject("docs(readme): update install guide") == ("docs", False)
    assert release_status.parse_subject("chore(release): bump v2.0.1") == ("chore", False)
    assert release_status.parse_subject("random non-conventional commit") == ("other", False)
    assert release_status.parse_subject("feat: something with BREAKING change") == ("feat", True)
    assert release_status.parse_subject("custom message BREAKING") == ("other", True)


def test_classify_and_edge_cases() -> None:
    """Verify classify handles ignored release commits, security counting, and breaking."""
    subjects = [
        "chore(release): bump version to 2.0.0",  # ignored
        "release: v2.0.0",  # ignored
        "fix: patch security and credential leak",  # fix + 1, security + 1 (counts once)
        "feat(auth)!: add key rotation",  # feat + 1, breaking + 1
        "perf: optimize order routing",  # perf + 1
        "docs: update architecture overview",  # other + 1
    ]
    counts = release_status.classify(subjects)
    assert counts["feat"] == 1
    assert counts["fix"] == 1
    assert counts["perf"] == 1
    assert counts["security"] == 1  # security word counted once
    assert counts["breaking"] == 1
    assert counts["other"] == 1


def test_is_due() -> None:
    """Verify is_due threshold triggers for user-visible, security, or breaking changes."""
    # Under threshold
    assert not release_status.is_due(
        {"feat": 1, "fix": 1, "perf": 0, "security": 0, "breaking": 0, "other": 5}
    )
    # Reaching DUE_AFTER = 3
    assert release_status.is_due(
        {"feat": 2, "fix": 1, "perf": 0, "security": 0, "breaking": 0, "other": 0}
    )
    # Single security change
    assert release_status.is_due(
        {"feat": 0, "fix": 0, "perf": 0, "security": 1, "breaking": 0, "other": 0}
    )
    # Single breaking change
    assert release_status.is_due(
        {"feat": 0, "fix": 0, "perf": 0, "security": 0, "breaking": 1, "other": 0}
    )


def test_build_notes_sections_and_omissions() -> None:
    """Verify build_notes groups commits into appropriate sections and omits noise."""
    subjects = [
        "feat(api): add portfolio query endpoint",
        "fix(ledger): fix cash reconciliation rounding",
        "perf(engine): vectorize drawdown calculation",
        "refactor: extract risk governor module",
        "misc: update license notice",
        "feat(auth)!: replace api key with oauth2",
        "test: add backtest regression test",  # omitted
        "chore: clean temporary artifacts",  # omitted
        "docs: fix typo in quickstart",  # omitted
        "ci: configure test matrix",  # omitted
    ]
    notes = release_notes.build_notes("1.1.0", subjects, previous_tag="v1.0.0")

    assert "# QuantOS v1.1.0" in notes or "# Mizan Quant OS v1.1.0" in notes
    assert "## What's new" in notes
    assert "- Add portfolio query endpoint" in notes
    assert "- **Breaking:** Replace api key with oauth2" in notes

    assert "## Fixes" in notes
    assert "- Fix cash reconciliation rounding" in notes

    assert "## Improvements" in notes
    assert "- Vectorize drawdown calculation" in notes
    assert "- Extract risk governor module" in notes

    assert "## Other changes" in notes
    assert "- Update license notice" in notes

    # Omitted commits must not appear
    assert "add backtest regression test" not in notes.lower()
    assert "clean temporary artifacts" not in notes.lower()
    assert "fix typo in quickstart" not in notes.lower()

    # Changelog footer
    assert (
        "Full changelog: https://github.com/uninestindia-crypto/quant-system/compare/v1.0.0...v1.1.0" in notes
        or "Full changelog: https://github.com/uninestindia-crypto/mizan/compare/v1.0.0...v1.1.0" in notes
    )


def test_build_notes_maintenance_only() -> None:
    """Verify build_notes indicates maintenance changes only when no user-facing items exist."""
    subjects = [
        "chore: update dependencies",
        "test: add unit tests",
        "docs: update readme",
    ]
    notes = release_notes.build_notes("1.0.1", subjects, previous_tag="v1.0.0")
    assert "# QuantOS v1.0.1" in notes or "# Mizan Quant OS v1.0.1" in notes
    assert "This release has maintenance changes only." in notes
    assert (
        "Full changelog: https://github.com/uninestindia-crypto/quant-system/compare/v1.0.0...v1.0.1" in notes
        or "Full changelog: https://github.com/uninestindia-crypto/mizan/compare/v1.0.0...v1.0.1" in notes
    )


def test_cli_execution(fake_tree: Path) -> None:
    """Verify CLI entrypoints execute cleanly on fake tree without real repo dependency."""
    # bump_version CLI --check
    assert bump_version.main(["--check", "--root", str(fake_tree)]) == 0

    # release_status CLI --json
    assert release_status.main(["--json", "--root", str(fake_tree)]) == 0

    # release_notes CLI
    out_file = fake_tree / "NOTES.md"
    assert release_notes.main(["1.1.0", "--out", str(out_file), "--root", str(fake_tree)]) == 0
    assert (
        "# QuantOS v1.1.0" in out_file.read_text(encoding="utf-8")
        or "# Mizan Quant OS v1.1.0" in out_file.read_text(encoding="utf-8")
    )


# --- additions by the lead agent: choosing the next version -------------------------------------


def test_the_next_version_follows_the_kind_of_release() -> None:
    assert bump_version.next_version("2.0.1", "patch") == "2.0.2"
    assert bump_version.next_version("2.0.9", "minor") == "2.1.0"
    assert bump_version.next_version("2.4.7", "major") == "3.0.0"
    with pytest.raises(ValueError):
        bump_version.next_version("2.0.1", "huge")
    with pytest.raises(ValueError):
        bump_version.next_version("two", "patch")


def test_the_suggested_bump_is_major_for_breaking_minor_for_features_else_patch() -> None:
    assert release_status.suggest_bump({"feat": 0, "fix": 5, "breaking": 0}) == "patch"
    assert release_status.suggest_bump({"feat": 1, "fix": 5, "breaking": 0}) == "minor"
    assert release_status.suggest_bump({"feat": 3, "fix": 0, "breaking": 1}) == "major"


def test_every_file_that_carries_the_version_agrees_in_this_repository() -> None:
    """The guard against drift: the 2.0.1 bump once updated two files and left four on older numbers,
    and the classic console page kept saying 2.0.0. `scripts/bump_version.py` changes all of them."""
    assert bump_version.check(SCRIPTS_DIR.parent) == []
