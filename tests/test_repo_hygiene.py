"""Checks on the repository's own files that a Windows machine would otherwise be the first to find."""

from __future__ import annotations

import subprocess
from collections import defaultdict
from pathlib import Path, PurePosixPath

import pytest

ROOT = Path(__file__).resolve().parents[1]
MODULE_SUFFIXES = {".ts", ".tsx", ".js", ".jsx", ".mjs", ".py"}


def case_collisions(paths: list[str]) -> list[list[str]]:
    """Groups of paths that are the same file name on a case-insensitive disk (Windows, macOS by default)."""
    groups: dict[str, set[str]] = defaultdict(set)
    for path in paths:
        groups[path.lower()].add(path)
    return [sorted(group) for group in groups.values() if len(group) > 1]


def module_name_collisions(paths: list[str]) -> list[list[str]]:
    """Modules in one folder whose names differ only by case, such as Markdown.tsx beside markdown.ts.

    They are different files on Linux and one name on Windows, so an import written as ``./Markdown`` resolves
    differently from one machine to the next.
    """
    groups: dict[tuple[str, str], set[str]] = defaultdict(set)
    for path in paths:
        pure = PurePosixPath(path)
        if pure.suffix in MODULE_SUFFIXES:
            groups[(str(pure.parent), pure.stem.lower())].add(path)
    return [
        sorted(group)
        for group in groups.values()
        if len({PurePosixPath(p).stem for p in group}) > 1
    ]


def tracked_files() -> list[str]:
    result = subprocess.run(
        ["git", "ls-files"], cwd=ROOT, capture_output=True, text=True, encoding="utf-8", check=False
    )
    if result.returncode != 0:
        # test-allow: skipped-test — a source download without Git history has no file list to check
        pytest.skip("not a Git checkout")
    return [line for line in result.stdout.splitlines() if line]


@pytest.mark.parametrize(
    ("paths", "expected"),
    [
        (["a/Readme.md", "a/README.md"], [["a/README.md", "a/Readme.md"]]),
        (["a/Readme.md", "b/Readme.md"], []),
        (["a/readme.md"], []),
    ],
)
def test_the_case_collision_checker_finds_files_that_differ_only_by_case(
    paths: list[str], expected: list[list[str]]
) -> None:
    assert case_collisions(paths) == expected


@pytest.mark.parametrize(
    ("paths", "expected"),
    [
        (["c/Markdown.tsx", "c/markdown.ts"], [["c/Markdown.tsx", "c/markdown.ts"]]),
        (["c/Markdown.tsx", "c/Markdown.test.tsx"], []),
        (["c/markdown.ts", "d/Markdown.tsx"], []),
        (["c/MarkdownView.tsx", "c/markdown.ts"], []),
        (["c/readme.md", "c/README.md"], []),
    ],
)
def test_the_module_checker_finds_modules_whose_names_differ_only_by_case(
    paths: list[str], expected: list[list[str]]
) -> None:
    assert module_name_collisions(paths) == expected


def test_no_two_tracked_files_differ_only_by_case() -> None:
    assert case_collisions(tracked_files()) == []


def test_no_two_modules_in_one_folder_differ_only_by_case() -> None:
    assert module_name_collisions(tracked_files()) == []
