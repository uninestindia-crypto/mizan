"""Generate plain-language release notes for a GitHub release."""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path


def build_notes(version: str, subjects: list[str], previous_tag: str | None) -> str:
    """Build markdown release notes grouped by change category."""
    ver = version.lstrip("v")
    lines: list[str] = [f"# QuantOS v{ver}"]

    whats_new: list[str] = []
    fixes: list[str] = []
    improvements: list[str] = []
    other_changes: list[str] = []

    omitted_types = {"test", "chore", "docs", "style", "ci", "build", "release"}
    pattern = r"^([a-zA-Z]+)(?:\([^)]*\))?(!)?:\s*(.*)$"

    for subject in subjects:
        sub = subject.strip()
        if not sub:
            continue

        m = re.match(pattern, sub)
        if m:
            commit_type = m.group(1).lower()
            has_bang = bool(m.group(2))
            body = m.group(3).strip()
            is_breaking = has_bang or ("BREAKING" in sub)
        else:
            commit_type = "other"
            body = sub
            is_breaking = "BREAKING" in sub

        if commit_type in omitted_types:
            continue

        if body:
            bullet_text = body[0].upper() + body[1:]
        else:
            bullet_text = ""

        if is_breaking:
            bullet = f"- **Breaking:** {bullet_text}"
        else:
            bullet = f"- {bullet_text}"

        if commit_type == "feat":
            whats_new.append(bullet)
        elif commit_type == "fix":
            fixes.append(bullet)
        elif commit_type in ("perf", "refactor"):
            improvements.append(bullet)
        else:
            other_changes.append(bullet)

    total_entries = len(whats_new) + len(fixes) + len(improvements) + len(other_changes)

    if total_entries == 0:
        lines.append("")
        lines.append("This release has maintenance changes only.")
    else:
        if whats_new:
            lines.append("")
            lines.append("## What's new")
            lines.extend(whats_new)
        if fixes:
            lines.append("")
            lines.append("## Fixes")
            lines.extend(fixes)
        if improvements:
            lines.append("")
            lines.append("## Improvements")
            lines.extend(improvements)
        if other_changes:
            lines.append("")
            lines.append("## Other changes")
            lines.extend(other_changes)

    if previous_tag:
        lines.append("")
        lines.append(
            f"Full changelog: https://github.com/uninestindia-crypto/quant-system/compare/{previous_tag}...v{ver}"
        )

    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    """CLI entrypoint for generating release notes."""
    parser = argparse.ArgumentParser(description="Generate release notes from commit subjects.")
    parser.add_argument("version", help="Release version (e.g. 2.0.2).")
    parser.add_argument("--since", help="Previous git tag to compare from.")
    parser.add_argument("--out", type=Path, help="Output file path (defaults to stdout).")
    parser.add_argument(
        "--root",
        type=Path,
        default=None,
        help="Repository root directory (defaults to parent of scripts/).",
    )

    args = parser.parse_args(argv)
    root = (args.root or Path(__file__).resolve().parent.parent).resolve()

    cmd = ["git", "log", "--format=%s"]
    if args.since:
        cmd.append(f"{args.since}..HEAD")

    try:
        proc = subprocess.run(
            cmd,
            cwd=root,
            capture_output=True,
            text=True,
            check=False,
        )
        if proc.returncode == 0:
            subjects = [s.strip() for s in proc.stdout.splitlines() if s.strip()]
        else:
            subjects = []
    except Exception:
        subjects = []

    notes = build_notes(args.version, subjects, args.since)

    if args.out:
        args.out.write_text(notes + "\n", encoding="utf-8")
    else:
        print(notes)

    return 0


if __name__ == "__main__":
    sys.exit(main())
