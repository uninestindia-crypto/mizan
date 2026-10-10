"""One-click update: download the new installer, check it against the release's published fingerprint, hand it over.

Nothing here touches the network or runs an installer: the download and the launch are stand-ins.
"""

from __future__ import annotations

import hashlib
import io
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest

from quant_system.server.v2.updater import (
    ReleaseAssets,
    UpdateInstaller,
    download_url_allowed,
    expected_hash,
)
from quant_system.server.v2.updates import REPOSITORY, UpdateChecker

BASE = f"https://github.com/{REPOSITORY}/releases/download/v2.6.0"
NAME = "QuantOS_v2.6.0_Setup.exe"
BODY = (
    b"MZ" + b"installer bytes " * 100_000
)  # a believable size, and it starts like a Windows program
SUMS_NAME = "SHA256SUMS-v2.6.0.txt"


def _hash(data: bytes = BODY) -> str:
    return hashlib.sha256(data).hexdigest()


def _sums(data: bytes = BODY, name: str = NAME) -> bytes:
    return f"{_hash(data)}  {name}\n{'0' * 64}  other-file.json\n".encode()


def _assets(**changes: Any) -> ReleaseAssets:
    fields = {
        "version": "2.6.0",
        "installer_name": NAME,
        "installer_url": f"{BASE}/{NAME}",
        "checksums_url": f"{BASE}/{SUMS_NAME}",
    }
    return ReleaseAssets(**{**fields, **changes})


class Downloads:
    """A stand-in for the network: serves fixed bytes per address and remembers what was asked for."""

    def __init__(self, files: dict[str, bytes]) -> None:
        self.files, self.asked = files, []

    def __call__(self, url: str) -> io.BytesIO:
        self.asked.append(url)
        if url not in self.files:
            raise OSError("not found")
        return io.BytesIO(self.files[url])


class Launches:
    def __init__(self, fail: bool = False) -> None:
        self.paths: list[Path] = []
        self.fail = fail

    def __call__(self, installer: Path) -> None:
        if self.fail:
            raise OSError("blocked")
        self.paths.append(installer)


class Inline:
    def __call__(self, task: Callable[[], None]) -> None:
        task()


def _installer(
    tmp_path: Path, files: dict[str, bytes] | None = None, *, launch: Launches | None = None
) -> tuple[UpdateInstaller, Downloads, Launches]:
    served = Downloads(
        files if files is not None else {f"{BASE}/{NAME}": BODY, f"{BASE}/{SUMS_NAME}": _sums()}
    )
    handed = launch or Launches()
    installer = UpdateInstaller(
        tmp_path, opener=served, launch=handed, spawn=Inline(), windows=True
    )
    return installer, served, handed


# ------------------------------------------------------------------------------ the happy path


def test_a_good_download_is_checked_and_handed_to_the_installer(tmp_path: Path) -> None:
    installer, _served, launched = _installer(tmp_path)
    installer.start(_assets())
    status = installer.status()
    assert status["state"] == "installing" and "close" in status["message"].lower()
    assert [p.name for p in launched.paths] == [NAME] and launched.paths[0].read_bytes() == BODY


def test_nothing_is_run_before_the_fingerprint_has_been_checked(tmp_path: Path) -> None:
    installer, _served, launched = _installer(tmp_path, {f"{BASE}/{NAME}": BODY})
    installer.start(_assets())
    assert installer.status()["state"] == "failed" and launched.paths == []


# ------------------------------------------------------------------------------ failing safely


@pytest.mark.parametrize(
    ("files", "words"),
    [
        ({f"{BASE}/{NAME}": BODY, f"{BASE}/{SUMS_NAME}": _sums(b"MZ other file")}, "did not match"),
        ({f"{BASE}/{NAME}": BODY + b"tampered", f"{BASE}/{SUMS_NAME}": _sums()}, "did not match"),
        ({f"{BASE}/{SUMS_NAME}": _sums()}, "could not be downloaded"),
        ({f"{BASE}/{NAME}": BODY, f"{BASE}/{SUMS_NAME}": b"garbage"}, "fingerprint"),
        (
            {
                f"{BASE}/{NAME}": b"<html>not a program</html>",
                f"{BASE}/{SUMS_NAME}": _sums(b"<html>not a program</html>"),
            },
            "not a Windows program",
        ),
    ],
)
def test_a_bad_download_is_refused_in_plain_words_and_never_run(
    tmp_path: Path, files: dict[str, bytes], words: str
) -> None:
    installer, _served, launched = _installer(tmp_path, files)
    installer.start(_assets())
    status = installer.status()
    assert status["state"] == "failed" and words in status["message"] and launched.paths == []


def test_a_refused_download_is_deleted(tmp_path: Path) -> None:
    installer, _served, _launched = _installer(
        tmp_path, {f"{BASE}/{NAME}": BODY + b"x", f"{BASE}/{SUMS_NAME}": _sums()}
    )
    installer.start(_assets())
    assert list(tmp_path.glob("*.exe*")) == []


def test_a_release_with_no_published_fingerprint_is_not_installed(tmp_path: Path) -> None:
    installer, served, launched = _installer(tmp_path)
    installer.start(_assets(checksums_url=None))
    status = installer.status()
    assert status["state"] == "failed" and "fingerprint" in status["message"]
    assert served.asked == [] and launched.paths == []


@pytest.mark.parametrize(
    "url",
    [
        "http://github.com/" + REPOSITORY + "/releases/download/v2.6.0/" + NAME,
        "https://evil.example/" + REPOSITORY + "/releases/download/v2.6.0/" + NAME,
        "https://github.com/someone/else/releases/download/v2.6.0/" + NAME,
        "https://github.com/" + REPOSITORY + "/releases/download/v2.6.0/../../x.exe",
        "file:///c:/windows/system32/cmd.exe",
    ],
)
def test_only_this_projects_own_release_files_are_ever_downloaded(tmp_path: Path, url: str) -> None:
    assert download_url_allowed(url) is False
    installer, served, launched = _installer(tmp_path)
    installer.start(_assets(installer_url=url))
    assert installer.status()["state"] == "failed" and served.asked == [] and launched.paths == []


def test_this_projects_release_address_is_allowed() -> None:
    assert download_url_allowed(f"{BASE}/{NAME}") is True


def test_an_installer_that_cannot_be_started_is_a_plain_failure(tmp_path: Path) -> None:
    installer, _served, _launched = _installer(tmp_path, launch=Launches(fail=True))
    installer.start(_assets())
    status = installer.status()
    assert status["state"] == "failed" and "release page" in status["message"]


def test_updating_from_inside_the_app_is_only_for_windows(tmp_path: Path) -> None:
    served = Downloads({})
    installer = UpdateInstaller(
        tmp_path, opener=served, launch=Launches(), spawn=Inline(), windows=False
    )
    installer.start(_assets())
    assert installer.status()["state"] == "failed" and "Windows" in installer.status()["message"]
    assert served.asked == []


def test_a_second_click_while_one_is_running_does_not_start_another(tmp_path: Path) -> None:
    queued: list[Callable[[], None]] = []
    installer = UpdateInstaller(
        tmp_path, opener=Downloads({}), launch=Launches(), spawn=queued.append, windows=True
    )
    installer.start(_assets())
    installer.start(_assets())
    assert len(queued) == 1 and installer.status()["state"] == "downloading"


# ------------------------------------------------------------------------------ the fingerprint file


@pytest.mark.parametrize(
    ("text", "found"),
    [
        (f"{'a' * 64}  {NAME}\n", "a" * 64),
        (f"{'A' * 64} *{NAME}\n", "a" * 64),
        (f"{'b' * 64}  other.exe\n", None),
        ("not a checksum file", None),
        (f"{'c' * 63}  {NAME}\n", None),
    ],
)
def test_the_published_fingerprint_for_a_file_is_found_or_not(text: str, found: str | None) -> None:
    assert expected_hash(text, NAME) == found


# ------------------------------------------------------------------------------ where the assets come from


def _release(**extra: Any) -> dict[str, Any]:
    return {
        "tag_name": "v2.6.0",
        "html_url": "https://github.com/o/r/releases/tag/v2.6.0",
        "assets": [
            {"name": NAME, "browser_download_url": f"{BASE}/{NAME}"},
            {"name": SUMS_NAME, "browser_download_url": f"{BASE}/{SUMS_NAME}"},
        ],
        **extra,
    }


def test_the_update_check_hands_over_the_installer_and_its_fingerprint_file() -> None:
    checker = UpdateChecker("2.5.0", lambda: _release())
    checker.check()
    assets = checker.install_assets()
    assert assets is not None and assets.installer_name == NAME and assets.version == "2.6.0"
    assert assets.installer_url.endswith(NAME) and (assets.checksums_url or "").endswith(SUMS_NAME)


def test_no_assets_are_offered_when_there_is_no_newer_release() -> None:
    checker = UpdateChecker("2.6.0", lambda: _release())
    checker.check()
    assert checker.install_assets() is None


def test_a_release_without_an_installer_offers_nothing_to_install() -> None:
    checker = UpdateChecker("2.5.0", lambda: _release(assets=[]))
    checker.check()
    assert checker.install_assets() is None


# ------------------------------------------------------------------------------ the installer script


def test_the_installer_opens_quantos_again_after_an_update_started_from_inside_it() -> None:
    script = (Path(__file__).resolve().parents[1] / "installer" / "quant_os_setup.iss").read_text(
        encoding="utf-8"
    )
    assert "{param:RELAUNCH|0}" in script and "Check: WantsRelaunch" in script
    assert "/RELAUNCH=1" in (
        Path(__file__).resolve().parents[1]
        / "src"
        / "quant_system"
        / "server"
        / "v2"
        / "updater.py"
    ).read_text(encoding="utf-8")
