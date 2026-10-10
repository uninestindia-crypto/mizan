"""Every page the app can open must be served by the server, or a new screen is a dead link (Research once was)."""

from __future__ import annotations

import re
from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient

from quant_system.server.v2.spa import register_spa

FRONTEND = Path(__file__).resolve().parents[1] / "frontend" / "src"


def _pages() -> list[str]:
    app_source = (FRONTEND / "App.tsx").read_text(encoding="utf-8")
    nav_source = (FRONTEND / "components" / "Layout.tsx").read_text(encoding="utf-8")
    routed = re.findall(r'<Route\s+path="(/[^"*:]*)"', app_source)
    navigated = re.findall(r'\{\s*to:\s*"(/[^"]*)"', nav_source)
    return sorted({*routed, *navigated})


def test_the_scan_finds_the_pages_it_is_meant_to_check() -> None:
    pages = _pages()
    assert len(pages) >= 8
    assert {"/", "/research", "/fundamentals", "/portfolio"} <= set(pages)


def test_the_server_serves_every_page_the_app_can_open() -> None:
    app = FastAPI()
    register_spa(app)
    client = TestClient(app)
    missing = [page for page in _pages() if client.get(page).status_code == 404]
    assert missing == [], f"these pages are in the app but the server answers 404: {missing}"
