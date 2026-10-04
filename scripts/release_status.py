"""Evaluate repository commits to determine whether a release is due."""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

DUE_AFTER = 3


def parse_subject(subject: str) -> tuple[str, bool]:
    """Parse conventional-commit subject into (type, breaking)."""
    pattern = r"^([a-zA-Z]+)(?:\([^)]*\))?(!)?:\s*(.*)$"
    m = re.match(pattern, subject.strip())
    is_breaking = "BREAKING" in subject
    if m:
        commit_type = m.group(1).lower()
        has_bang = bool(m.group(2))
        return commit_type, (has_bang or is_breaking)
    return "other", is_breaking


def classify(subjects: list[str]) -> dict[str, int]:
    """Classify commit subjects into category counts."""
    counts: dict[str, int] = {
        "feat": 0,
        "fix": 0,
        "perf": 0,
        "security": 0,
        "breaking": 0,
        "other": 0,
    }

    ignored_pattern = r"^(?:release(?:\([^)]*\))?|chore\s*\(\s*release\s*\))(!)?:\s*"

    for subject in subjects:
        sub = subject.strip()
        if not sub:
            continue

        # A subject whose type is chore with scope release, or whose type is release, is ignored entirely
        if re.match(ignored_pattern, sub, re.IGNORECASE):
            continue

        commit_type, is_breaking = parse_subject(sub)

        # Base type count
        if commit_type in ("feat", "fix", "perf"):
            counts[commit_type] += 1
        else:
            counts["other"] += 1

        # Breaking count
        if is_breaking:
            counts["breaking"] += 1

        # Security count: subject containing 'security' or 'credential' (case-insensitive) adds one
        if (
            re.search(r"\b(security|credential)s?\b", sub, re.IGNORECASE)
            or commit_type == "security"
        ):
            counts["security"] += 1

    return counts


def is_due(counts: dict[str, int]) -> bool:
    """Check whether a release is due based on category counts and threshold."""
    user_visible = counts.get("feat", 0) + counts.get("fix", 0) + counts.get("perf", 0)
    return (
        user_visible >= DUE_AFTER
        or counts.get("security", 0) >= 1
        or counts.get("breaking", 0) >= 1
    )


def suggest_bump(counts: dict[str, int]) -> str:
    """The semver step these changes call for: major for breaking, minor for a feature, else patch."""
    if counts.get("breaking", 0) >= 1:
        return "major"
    if counts.get("feat", 0) >= 1:
        return "minor"
    return "patch"


def last_release_tag(root: Path) -> str | None:
    """Return the most recent release tag matching 'v[0-9]*' or None on failure."""
    try:
        proc = subprocess.run(
            ["git", "describe", "--tags", "--abbrev=0", "--match", "v[0-9]*"],
            cwd=root,
            capture_output=True,
            text=True,
            check=False,
        )
        if proc.returncode == 0:
            tag = proc.stdout.strip()
            return tag if tag else None
        return None
    except Exception:
        return None


def subjects_since(root: Path, tag: str | None) -> list[str]:
    """Retrieve commit subjects since tag (or all commits if tag is None)."""
    cmd = ["git", "log", "--format=%s"]
    if tag:
        cmd.append(f"{tag}..HEAD")
    try:
        proc = subprocess.run(
            cmd,
            cwd=root,
            capture_output=True,
            text=True,
            check=False,
        )
        if proc.returncode != 0:
            return []
        return [line.strip() for line in proc.stdout.splitlines() if line.strip()]
    except Exception:
        return []


def main(argv: list[str] | None = None) -> int:
    """CLI entrypoint for evaluating release status."""
    parser = argparse.ArgumentParser(description="Check whether a QuantOS release is due.")
    parser.add_argument("--json", action="store_true", help="Print status as JSON.")
    parser.add_argument(
        "--fail-if-due",
        action="store_true",
        help="Exit with code 1 if a release is due, else 0.",
    )
    parser.add_argument(
        "--root",
        type=Path,
        default=None,
        help="Repository root directory (defaults to parent of scripts/).",
    )

    args = parser.parse_args(argv)
    root = (args.root or Path(__file__).resolve().parent.parent).resolve()

    tag = last_release_tag(root)
    subjects = subjects_since(root, tag)
    counts = classify(subjects)
    due = is_due(counts)
    user_visible = counts["feat"] + counts["fix"] + counts["perf"]

    if args.json:
        payload = {
            "last_tag": tag,
            "counts": counts,
            "due": due,
            "user_visible": user_visible,
            "threshold": DUE_AFTER,
            "suggested_bump": suggest_bump(counts),
        }
        print(json.dumps(payload, indent=2))
    else:
        if tag:
            print(f"Last release: {tag}")
        else:
            print("No release yet")

        counts_str = ", ".join(f"{k}={v}" for k, v in counts.items())
        print(f"Counts: {counts_str}")

        if due:
            reasons: list[str] = []
            if user_visible >= DUE_AFTER:
                reasons.append(f"{user_visible} user-visible changes")
            if counts["security"] >= 1:
                reasons.append(f"{counts['security']} security-related changes")
            if counts["breaking"] >= 1:
                reasons.append(f"{counts['breaking']} breaking changes")
            print(f"Release DUE: {', '.join(reasons)} (suggested: {suggest_bump(counts)} release)")
        else:
            print(f"No release due yet ({user_visible} of {DUE_AFTER} user-visible changes)")

    if args.fail_if_due and due:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
