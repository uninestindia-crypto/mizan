"""Keep the product version identical across repository files and bump it in one command."""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

VERSION_RE = r"\d+\.\d+\.\d+"


def read_versions(root: Path) -> dict[str, str | None]:
    """Read product versions from all configured version carrier files."""
    results: dict[str, str | None] = {
        "pyproject.toml": None,
        "src/quant_system/__init__.py": None,
        "frontend/package.json": None,
        "frontend/package-lock.json": None,
        "src/quant_system/server/static/index.html": None,
        "uv.lock": None,
    }

    # 1. pyproject.toml: first top-level line version = "X.Y.Z"
    p = root / "pyproject.toml"
    if p.is_file():
        text = p.read_bytes().decode("utf-8")
        m = re.search(r'(?m)^version\s*=\s*"(' + VERSION_RE + r')"', text)
        if m:
            results["pyproject.toml"] = m.group(1)

    # 2. src/quant_system/__init__.py: line __version__ = "X.Y.Z"
    p = root / "src/quant_system/__init__.py"
    if p.is_file():
        text = p.read_bytes().decode("utf-8")
        m = re.search(r'(?m)^__version__\s*=\s*"(' + VERSION_RE + r')"', text)
        if m:
            results["src/quant_system/__init__.py"] = m.group(1)

    # 3. frontend/package.json: first "version": "X.Y.Z" entry
    p = root / "frontend/package.json"
    if p.is_file():
        text = p.read_bytes().decode("utf-8")
        m = re.search(r'"version"\s*:\s*"(' + VERSION_RE + r')"', text)
        if m:
            results["frontend/package.json"] = m.group(1)

    # 4. frontend/package-lock.json: first "version": "X.Y.Z" entry (None if file does not exist)
    p = root / "frontend/package-lock.json"
    if p.is_file():
        text = p.read_bytes().decode("utf-8")
        m = re.search(r'"version"\s*:\s*"(' + VERSION_RE + r')"', text)
        if m:
            results["frontend/package-lock.json"] = m.group(1)

    # 5. src/quant_system/server/static/index.html: text v<X.Y.Z> following class="brand-badge">
    p = root / "src/quant_system/server/static/index.html"
    if p.is_file():
        text = p.read_bytes().decode("utf-8")
        m = re.search(r'brand-badge">v(' + VERSION_RE + r")<", text)
        if m:
            results["src/quant_system/server/static/index.html"] = m.group(1)

    # 6. uv.lock: version = "X.Y.Z" line immediately following name = "quant-system"
    p = root / "uv.lock"
    if p.is_file():
        text = p.read_bytes().decode("utf-8")
        m = re.search(
            r'(?m)^name\s*=\s*"quant-system"[ \t]*\r?\nversion\s*=\s*"(' + VERSION_RE + r')"',
            text,
        )
        if m:
            results["uv.lock"] = m.group(1)

    return results


def next_version(current: str, kind: str) -> str:
    """The version after ``current`` for a ``major``, ``minor`` or ``patch`` release."""
    if not re.fullmatch(VERSION_RE, current):
        raise ValueError(f"Not a version: '{current}'.")
    major, minor, patch = (int(x) for x in current.split("."))
    if kind == "major":
        return f"{major + 1}.0.0"
    if kind == "minor":
        return f"{major}.{minor + 1}.0"
    if kind == "patch":
        return f"{major}.{minor}.{patch + 1}"
    raise ValueError(f"Unknown bump kind '{kind}': use major, minor or patch.")


def check(root: Path) -> list[str]:
    """Check version consistency across files against src/quant_system/__init__.py."""
    versions = read_versions(root)
    init_rel = "src/quant_system/__init__.py"
    init_path = root / init_rel

    if not init_path.is_file():
        return [f"{init_rel}: reference version file does not exist"]

    init_ver = versions.get(init_rel)
    if init_ver is None:
        return [f"{init_rel}: version pattern not found"]

    mismatches: list[str] = []
    for rel_path, ver in versions.items():
        if rel_path == init_rel:
            continue
        file_path = root / rel_path
        if not file_path.is_file():
            # A missing file is ignored per specification
            continue
        if ver is None:
            mismatches.append(f"{rel_path}: version pattern not found")
        elif ver != init_ver:
            mismatches.append(
                f"{rel_path}: version '{ver}' does not match expected version '{init_ver}'"
            )

    return mismatches


def bump(root: Path, new_version: str) -> list[str]:
    """Validate new_version, bump across all version carrier files, and return changed paths."""
    if not re.fullmatch(r"^\d+\.\d+\.\d+$", new_version):
        raise ValueError(
            f"Invalid version format: '{new_version}'. Expected format matching '^\\d+\\.\\d+\\.\\d+$'."
        )

    versions = read_versions(root)
    init_rel = "src/quant_system/__init__.py"
    current = versions.get(init_rel)
    if current is None:
        raise ValueError(
            f"Cannot bump: reference version in '{init_rel}' not found or file missing."
        )

    def parse_tuple(v: str) -> tuple[int, ...]:
        return tuple(int(x) for x in v.split("."))

    if parse_tuple(new_version) <= parse_tuple(current):
        raise ValueError(
            f"New version '{new_version}' must be strictly greater than current version '{current}'."
        )

    changed: list[str] = []

    # 1. pyproject.toml
    rel = "pyproject.toml"
    p = root / rel
    if p.is_file():
        raw = p.read_bytes()
        text = raw.decode("utf-8")
        new_text = re.sub(
            r'(?m)^version\s*=\s*"' + VERSION_RE + r'"',
            f'version = "{new_version}"',
            text,
            count=1,
        )
        new_raw = new_text.encode("utf-8")
        if new_raw != raw:
            p.write_bytes(new_raw)
            changed.append(rel)

    # 2. src/quant_system/__init__.py
    rel = "src/quant_system/__init__.py"
    p = root / rel
    if p.is_file():
        raw = p.read_bytes()
        text = raw.decode("utf-8")
        new_text = re.sub(
            r'(?m)^__version__\s*=\s*"' + VERSION_RE + r'"',
            f'__version__ = "{new_version}"',
            text,
            count=1,
        )
        new_raw = new_text.encode("utf-8")
        if new_raw != raw:
            p.write_bytes(new_raw)
            changed.append(rel)

    # 3. frontend/package.json
    rel = "frontend/package.json"
    p = root / rel
    if p.is_file():
        raw = p.read_bytes()
        text = raw.decode("utf-8")
        new_text = re.sub(
            r'"version"\s*:\s*"' + VERSION_RE + r'"',
            f'"version": "{new_version}"',
            text,
            count=1,
        )
        new_raw = new_text.encode("utf-8")
        if new_raw != raw:
            p.write_bytes(new_raw)
            changed.append(rel)

    # 4. frontend/package-lock.json
    rel = "frontend/package-lock.json"
    p = root / rel
    if p.is_file():
        raw = p.read_bytes()
        text = raw.decode("utf-8")
        # Top-level version
        text_sub1 = re.sub(
            r'"version"\s*:\s*"' + VERSION_RE + r'"',
            f'"version": "{new_version}"',
            text,
            count=1,
        )
        # Version inside "packages": { "": { ... } } if present
        packages_pattern = (
            r'("packages"\s*:\s*\{\s*""\s*:\s*\{[^}]*?"version"\s*:\s*")' + VERSION_RE + r'(")'
        )
        new_text = re.sub(packages_pattern, rf"\g<1>{new_version}\g<2>", text_sub1, count=1)
        new_raw = new_text.encode("utf-8")
        if new_raw != raw:
            p.write_bytes(new_raw)
            changed.append(rel)

    # 5. src/quant_system/server/static/index.html
    rel = "src/quant_system/server/static/index.html"
    p = root / rel
    if p.is_file():
        raw = p.read_bytes()
        text = raw.decode("utf-8")
        old_html = versions.get(rel)
        new_text = text
        if old_html:
            new_text = new_text.replace(f"v{old_html}", f"v{new_version}")
        if current != old_html:
            new_text = new_text.replace(f"v{current}", f"v{new_version}")
        new_raw = new_text.encode("utf-8")
        if new_raw != raw:
            p.write_bytes(new_raw)
            changed.append(rel)

    # 6. uv.lock
    rel = "uv.lock"
    p = root / rel
    if p.is_file():
        raw = p.read_bytes()
        text = raw.decode("utf-8")
        uv_pattern = r'(^name\s*=\s*"quant-system"[ \t]*\r?\nversion\s*=\s*")' + VERSION_RE + r'(")'
        new_text = re.sub(
            uv_pattern, rf"\g<1>{new_version}\g<2>", text, count=1, flags=re.MULTILINE
        )
        new_raw = new_text.encode("utf-8")
        if new_raw != raw:
            p.write_bytes(new_raw)
            changed.append(rel)

    return changed


def main(argv: list[str] | None = None) -> int:
    """CLI entrypoint for checking or bumping the repository product version."""
    parser = argparse.ArgumentParser(description="Synchronize and bump product version.")
    parser.add_argument("version", nargs="?", help="New version X.Y.Z to bump to.")
    parser.add_argument("--check", action="store_true", help="Check that all version files agree.")
    parser.add_argument(
        "--next",
        choices=["major", "minor", "patch"],
        default=None,
        help="Print the next version for that kind of release and exit.",
    )
    parser.add_argument(
        "--root",
        type=Path,
        default=None,
        help="Repository root directory (defaults to parent of scripts/).",
    )

    args = parser.parse_args(argv)
    root = (args.root or Path(__file__).resolve().parent.parent).resolve()

    if args.next:
        current_version = read_versions(root).get("src/quant_system/__init__.py")
        if current_version is None:
            print("Error: current version not found.", file=sys.stderr)
            return 1
        print(next_version(current_version, args.next))
        return 0

    if args.check:
        mismatches = check(root)
        if mismatches:
            for m in mismatches:
                print(m)
            return 1
        current = read_versions(root).get("src/quant_system/__init__.py")
        print(f"All version files agree: {current}")
        return 0

    if args.version:
        try:
            changed = bump(root, args.version)
        except ValueError as err:
            print(f"Error: {err}", file=sys.stderr)
            return 1

        for p in changed:
            print(f"Updated {p}")

        mismatches = check(root)
        if mismatches:
            for m in mismatches:
                print(m)
            return 1
        return 0

    parser.print_help()
    return 2


if __name__ == "__main__":
    sys.exit(main())
