"""The "Update and restart" button: start the update, and say how far it has got.

The address of the installer is never taken from the request. It comes from the update check, which reads this
project's own releases, so a request cannot make QuantOS download or run anything else.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from quant_system.server.security import format_error_response
from quant_system.server.v2.updater import UpdateInstaller

router = APIRouter(prefix="/updates", tags=["Updates"])
__all__ = ["router"]

_installer: UpdateInstaller | None = None
_NOTHING_TO_INSTALL = (
    "There is no newer version to install right now. Check for updates first, "
    "or open the release page to get the installer yourself."
)


def installer() -> UpdateInstaller:
    global _installer
    if _installer is None:
        from quant_system.server.v2 import paths

        _installer = UpdateInstaller(Path(paths.state_dir()) / "updates")
    return _installer


@router.get("/install")
def install_status() -> dict[str, Any]:
    return installer().status()


@router.post("/install", status_code=202, response_model=None)
def install_update() -> Any:
    from quant_system.server.v2.router import services

    checker = services().updates
    checker.check()  # a fresh answer when none is held, the held one otherwise
    assets = checker.install_assets()
    if assets is None:
        return JSONResponse(
            status_code=409,
            content=format_error_response("NOTHING_TO_INSTALL", _NOTHING_TO_INSTALL, None),
        )
    return installer().start(assets)
