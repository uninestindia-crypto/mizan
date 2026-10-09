"""One-click update: fetch the new installer, check it against the release's published fingerprint, then hand it over.

A person presses one button. QuantOS downloads the installer that goes with the newest release, checks it against the
fingerprint (SHA-256) listed in that same release, and only then starts it. The installer closes QuantOS, replaces the
program, keeps the person's data and opens QuantOS again.

What this does and does not prove: a matching fingerprint shows the file arrived whole and is the one the release
lists. It does not prove the release itself is genuine; the installer is not code-signed yet, so Windows may still ask
the person to confirm. Only addresses inside this project's own releases are ever downloaded, and the address is never
taken from a request: it comes from the update check.

Nothing here runs unless the person pressed the button.
"""

from __future__ import annotations

import hashlib
import hmac
import re
import subprocess
import sys
import threading
import urllib.request
from collections.abc import Callable
from pathlib import Path
from typing import Any, BinaryIO, Final
from urllib.parse import unquote, urlparse

from quant_system.server.v2.updates import REPOSITORY, ReleaseAssets

__all__ = ["ReleaseAssets", "UpdateInstaller", "download_url_allowed", "expected_hash"]

CHUNK: Final = 1 << 16
MAX_BYTES: Final = 600 * 1024 * 1024
_TIMEOUT: Final = 30
_HASH_LINE = re.compile(r"^([0-9a-fA-F]{64})\s+\*?(.+?)\s*$")

_DOWNLOAD_FAILED = (
    "The update could not be downloaded. Check your internet connection and try again."
)
_NO_FINGERPRINT = (
    "This release does not list a fingerprint to check the download against, so it was not installed. "
    "Open the release page to get it yourself."
)
_BAD_FINGERPRINT = (
    "The fingerprint file for this release could not be read, so the download was not installed. "
    "Try again later."
)
_MISMATCH = (
    "The download did not match the release's fingerprint, so it was not installed. "
    "Try again, or open the release page."
)
_NOT_A_PROGRAM = "The download is not a Windows program, so it was not installed."
_NOT_WINDOWS = (
    "Updating from inside QuantOS works on Windows. Open the release page to get the new version."
)
_NOT_STARTED = "The installer could not be started. Open the release page and run it from there."
_NOT_ALLOWED = "That update is not from QuantOS's own releases, so it was not downloaded."
_INSTALLING = "Installing the update. QuantOS will close and open again in a moment."

Opener = Callable[[str], BinaryIO]
Launcher = Callable[[Path], None]
Spawn = Callable[[Callable[[], None]], None]


def download_url_allowed(url: str) -> bool:
    """True only for a file in this project's own GitHub releases, over https, with no way to wander off."""
    parts = urlparse(url)
    prefix = f"/{REPOSITORY}/releases/download/"
    segments = unquote(parts.path).split("/")
    return (
        parts.scheme == "https"
        and parts.netloc == "github.com"
        and parts.path.startswith(prefix)
        and ".." not in segments
        and not parts.query
    )


def expected_hash(text: str, name: str) -> str | None:
    """The fingerprint a checksum file lists for ``name`` (lower case), or None when it lists none."""
    for line in text.splitlines():
        found = _HASH_LINE.match(line.strip())
        if found and found.group(2) == name:
            return found.group(1).lower()
    return None


class _HttpsOnly(urllib.request.HTTPRedirectHandler):
    """A redirect to anything but https would let the file arrive over a channel anyone can alter."""

    def redirect_request(
        self, req: Any, fp: Any, code: Any, msg: Any, headers: Any, newurl: str
    ) -> Any:
        if urlparse(newurl).scheme != "https":
            return None
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def _open_url(url: str) -> BinaryIO:
    request = urllib.request.Request(url, headers={"User-Agent": "QuantOS-updater"})
    opener = urllib.request.build_opener(_HttpsOnly)
    return opener.open(request, timeout=_TIMEOUT)  # type: ignore[no-any-return]


def _start_installer(installer: Path) -> None:
    """Start the installer on its own, so it can close QuantOS, replace it and open it again."""
    flags = 0
    if sys.platform == "win32":
        flags = (
            subprocess.DETACHED_PROCESS
            | subprocess.CREATE_NEW_PROCESS_GROUP
            | subprocess.CREATE_NO_WINDOW
        )
    subprocess.Popen(
        [
            str(installer),
            "/SILENT",
            "/NOCANCEL",
            "/SUPPRESSMSGBOXES",
            "/NORESTART",
            "/CLOSEAPPLICATIONS",
            "/RELAUNCH=1",
        ],
        creationflags=flags,
        close_fds=True,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )


def _in_thread(task: Callable[[], None]) -> None:
    threading.Thread(target=task, name="QuantOS-update", daemon=True).start()


class _Refused(Exception):
    """A step failed in a way that has its own plain sentence."""


class UpdateInstaller:
    def __init__(
        self,
        folder: Path,
        *,
        opener: Opener = _open_url,
        launch: Launcher = _start_installer,
        spawn: Spawn = _in_thread,
        windows: bool = sys.platform == "win32",
    ) -> None:
        self._folder = folder
        self._open, self._launch, self._spawn, self._windows = opener, launch, spawn, windows
        self._lock = threading.Lock()
        self._state: dict[str, Any] = {
            "state": "idle",
            "percent": None,
            "message": "",
            "version": None,
        }

    def status(self) -> dict[str, Any]:
        with self._lock:
            return dict(self._state)

    def start(self, assets: ReleaseAssets) -> dict[str, Any]:
        """Begin the update in the background. A second press while one is running changes nothing."""
        with self._lock:
            if self._state["state"] in ("downloading", "checking", "installing"):
                return dict(self._state)
            self._state = {
                "state": "downloading",
                "percent": 0,
                "message": "",
                "version": assets.version,
            }
        self._spawn(lambda: self._run(assets))
        return self.status()

    # ------------------------------------------------------------------------------------------

    def _set(self, **changes: Any) -> None:
        with self._lock:
            self._state.update(changes)

    def _fail(self, message: str) -> None:
        self._set(state="failed", percent=None, message=message)

    def _run(self, assets: ReleaseAssets) -> None:
        target = self._folder / assets.installer_name
        try:
            self._guard(assets)
            wanted = self._fingerprint(assets)
            self._download(assets.installer_url, target)
            self._set(state="checking", percent=None)
            self._check(target, wanted)
            self._set(state="installing", percent=None, message=_INSTALLING)
            self._hand_over(target)
        except _Refused as refusal:
            target.unlink(missing_ok=True)
            self._fail(str(refusal))

    def _guard(self, assets: ReleaseAssets) -> None:
        if not self._windows:
            raise _Refused(_NOT_WINDOWS)
        if not assets.checksums_url:
            raise _Refused(_NO_FINGERPRINT)
        if not all(map(download_url_allowed, (assets.installer_url, assets.checksums_url))):
            raise _Refused(_NOT_ALLOWED)
        self._folder.mkdir(parents=True, exist_ok=True)
        for old in self._folder.glob("QuantOS_v*_Setup.exe*"):
            old.unlink(missing_ok=True)

    def _fingerprint(self, assets: ReleaseAssets) -> str:
        try:
            with self._open(str(assets.checksums_url)) as response:
                text = response.read(CHUNK).decode("utf-8", "replace")
        except OSError as error:
            raise _Refused(_DOWNLOAD_FAILED) from error
        found = expected_hash(text, assets.installer_name)
        if found is None:
            raise _Refused(_BAD_FINGERPRINT)
        return found

    def _download(self, url: str, target: Path) -> None:
        partial = target.with_name(target.name + ".part")
        try:
            with self._open(url) as response, partial.open("wb") as out:
                self._copy(response, out)
        except OSError as error:
            partial.unlink(missing_ok=True)
            raise _Refused(_DOWNLOAD_FAILED) from error
        partial.replace(target)

    def _copy(self, response: BinaryIO, out: BinaryIO) -> None:
        total = int(getattr(response, "length", 0) or 0)
        done = 0
        while chunk := response.read(CHUNK):
            done += len(chunk)
            if done > MAX_BYTES:
                raise OSError("too large")
            out.write(chunk)
            if total:
                self._set(percent=min(99, done * 100 // total))

    def _check(self, target: Path, wanted: str) -> None:
        digest = hashlib.sha256()
        with target.open("rb") as handle:
            head = handle.read(2)
            digest.update(head)
            while chunk := handle.read(CHUNK):
                digest.update(chunk)
        if not hmac.compare_digest(digest.hexdigest(), wanted):
            raise _Refused(_MISMATCH)
        if head != b"MZ":
            raise _Refused(_NOT_A_PROGRAM)

    def _hand_over(self, target: Path) -> None:
        try:
            self._launch(target)
        except OSError as error:
            raise _Refused(_NOT_STARTED) from error
