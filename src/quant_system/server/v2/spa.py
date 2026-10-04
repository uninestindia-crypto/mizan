"""Serve the built React app: ``index.html`` for every client route, hashed assets under /assets."""

from __future__ import annotations

from collections.abc import Callable

from fastapi import FastAPI
from fastapi.responses import FileResponse, HTMLResponse, Response
from fastapi.staticfiles import StaticFiles

from quant_system.server.v2 import paths

CLIENT_ROUTES = (
    "/",
    "/welcome",
    "/markets",
    "/stock/{symbol}",
    "/lab",
    "/lab/{rest:path}",
    "/portfolio",
    "/paper",
    "/paper/{rest:path}",
    "/tools",
    "/tools/{rest:path}",
    "/settings",
    "/settings/{rest:path}",
)

_NOT_BUILT = """<!doctype html>
<html lang="en"><head><meta charset="utf-8"><title>QuantOS</title>
<style>body{font:16px/1.5 system-ui,sans-serif;max-width:40rem;margin:15vh auto;padding:0 1rem;color:#1f2937}
code{background:#f3f4f6;padding:.1rem .3rem;border-radius:.25rem}</style></head>
<body><h1>QuantOS interface not built</h1>
<p>The new interface has not been built into this copy. Build it with
<code>npm run build</code> in the <code>frontend</code> folder, or open the
<a href="/classic">classic console</a>.</p></body></html>"""


def register_spa(app: FastAPI) -> None:
    root = paths.spa_dir()
    assets = root / "assets"
    if assets.is_dir():
        app.mount("/assets", StaticFiles(directory=str(assets)), name="spa-assets")
    for name in ("favicon.svg", "favicon.ico", "manifest.webmanifest"):
        if (root / name).is_file():
            app.add_api_route(
                f"/{name}", _file_route(name), methods=["GET"], include_in_schema=False
            )
    for route in CLIENT_ROUTES:
        app.add_api_route(route, serve_app, methods=["GET"], include_in_schema=False)


def serve_app() -> Response:
    index = paths.spa_dir() / "index.html"
    if not index.is_file():
        return HTMLResponse(_NOT_BUILT, status_code=503)
    return FileResponse(index, media_type="text/html", headers={"Cache-Control": "no-store"})


def _file_route(name: str) -> Callable[[], FileResponse]:
    def serve() -> FileResponse:
        return FileResponse(paths.spa_dir() / name)

    return serve
