"""Where the bundled filing snapshot and the list of listed companies are found, in a checkout and in a built app."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

from quant_system.shariah.services import proof_paths
from quant_system.shariah.services.proof_paths import (
    LISTED_FILE,
    SNAPSHOT_FILE,
    bundled_snapshot_path,
    listed_equities_count,
)


@pytest.fixture()
def folders(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> dict[str, Path]:
    """A pretend source checkout, app folder and built-app layout, with nothing placed in any of them."""
    where = {
        "checkout": tmp_path / "checkout",
        "app": tmp_path / "app",
        "beside": tmp_path / "install",
        "bundle": tmp_path / "bundle",
    }
    monkeypatch.setattr(proof_paths, "REPO_ROOT", where["checkout"])
    monkeypatch.delenv("QUANTOS_APP_ROOT", raising=False)
    monkeypatch.delattr(sys, "frozen", raising=False)
    monkeypatch.delattr(sys, "_MEIPASS", raising=False)
    return where


def place(root: Path, relative: Path = SNAPSHOT_FILE) -> Path:
    target = root / "data" / relative
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(b"x")
    return target


def test_in_a_source_checkout_the_snapshot_is_the_one_in_the_repository(
    folders: dict[str, Path],
) -> None:
    placed = place(folders["checkout"])
    assert bundled_snapshot_path() == placed


def test_when_no_snapshot_exists_anywhere_the_answer_is_where_it_would_be(
    folders: dict[str, Path],
) -> None:
    assert bundled_snapshot_path() == folders["checkout"] / "data" / SNAPSHOT_FILE


def test_an_explicit_app_folder_wins_over_the_checkout(
    folders: dict[str, Path], monkeypatch: pytest.MonkeyPatch
) -> None:
    place(folders["checkout"])
    chosen = place(folders["app"])
    monkeypatch.setenv("QUANTOS_APP_ROOT", str(folders["app"]))
    assert bundled_snapshot_path() == chosen


def test_an_app_folder_without_a_snapshot_falls_back_to_the_checkout(
    folders: dict[str, Path], monkeypatch: pytest.MonkeyPatch
) -> None:
    fallback = place(folders["checkout"])
    monkeypatch.setenv("QUANTOS_APP_ROOT", str(folders["app"]))
    assert bundled_snapshot_path() == fallback


def test_a_built_app_looks_beside_the_program_then_in_its_bundle_folder_then_in_the_unpacked_bundle(
    folders: dict[str, Path], monkeypatch: pytest.MonkeyPatch
) -> None:
    program = folders["beside"] / "quantos.exe"
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "executable", str(program))
    monkeypatch.setattr(sys, "_MEIPASS", str(folders["bundle"]), raising=False)
    unpacked = place(folders["bundle"])
    assert bundled_snapshot_path() == unpacked
    inside = place(folders["beside"] / "_internal")
    assert bundled_snapshot_path() == inside
    beside = place(folders["beside"])
    assert bundled_snapshot_path() == beside


def test_the_list_of_listed_companies_is_found_the_same_way_and_counted_without_its_header(
    folders: dict[str, Path], monkeypatch: pytest.MonkeyPatch
) -> None:
    assert listed_equities_count() is None  # a copy with no such list reports nothing, not zero
    target = place(folders["app"], LISTED_FILE)
    target.write_text("Symbol,Company Name\nAAA,A\nBBB,B\n\nCCC,C\n", encoding="utf-8")
    monkeypatch.setenv("QUANTOS_APP_ROOT", str(folders["app"]))
    assert listed_equities_count() == 3


def test_a_changed_list_is_counted_again(
    folders: dict[str, Path], monkeypatch: pytest.MonkeyPatch
) -> None:
    target = place(folders["app"], LISTED_FILE)
    monkeypatch.setenv("QUANTOS_APP_ROOT", str(folders["app"]))
    target.write_text("Symbol\nAAA\n", encoding="utf-8")
    assert listed_equities_count() == 1
    target.write_text("Symbol\nAAA\nBBB\nCCC\nDDD\n", encoding="utf-8")
    assert listed_equities_count() == 4
