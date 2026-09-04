"""Tests for the XS-monthly watch dashboard (new stack only)."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from quant_system.research_xs_monthly.dashboard import render_dashboard


def _state() -> dict:
    return {
        "capital": "1000000",
        "cash": "137184.02",
        "open": [
            {
                "symbol": "WELCORP",
                "entry_date": "2026-09-02",
                "entry_open": "2561.6",
                "shares": 3,
                "entry_value": "7684.8",
                "market_value": "7800.0",
                "unrealized": "115.2",
                "asof_date": "2026-09-03",
                "gross_mark": "0.015",
                "cost_pending": "0.00224",
            }
        ],
        "closed": [],
        "runs": [{"at": "2026-09-04T08:00:00Z", "note": "holding"}],
    }


def test_dashboard_shows_book_and_legs() -> None:
    page = render_dashboard(_state())
    assert "144,984.02" in page
    assert "WELCORP" in page
    assert "RESEARCH ONLY" in page
    assert "state.json" in page


def test_dashboard_escapes_hostile_symbols() -> None:
    state = _state()
    state["open"][0]["symbol"] = "<script>alert(1)</script>"
    page = render_dashboard(state)
    assert "<script>" not in page
    assert "&lt;script&gt;" in page


def test_dashboard_empty_state_renders() -> None:
    page = render_dashboard({"capital": "?", "cash": "?", "open": [], "closed": [], "runs": []})
    assert "flat" in page
    assert "none yet" in page


def test_dashboard_imports_no_main_dashboard() -> None:
    text = Path("src/quant_system/research_xs_monthly/dashboard.py").read_text(
        encoding="utf-8"
    ) + Path("scripts/serve_xs_watch_dashboard.py").read_text(encoding="utf-8")
    import_lines = [ln for ln in text.splitlines() if ln.lstrip().startswith(("import ", "from "))]
    for forbidden in ("server.app", "ui.templates", "serve_live_dashboard", "paper_pilot"):
        assert not any(forbidden in ln for ln in import_lines), forbidden
