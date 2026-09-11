"""Render the XS-monthly paper-watch state as a standalone HTML page.

Read-only against the state file. All dynamic strings are HTML-escaped.
No dependency on the main dashboard, server app, or UI templates.
"""

from __future__ import annotations

import html
from datetime import datetime
from typing import Any


def _esc(value: object) -> str:
    return html.escape(str(value), quote=True)


def _inr(value: object) -> str:
    try:
        number = float(str(value))
    except (ValueError, TypeError):
        return _esc(value)
    return f"\u20b9{number:,.2f}"


def render_dashboard(state: dict[str, Any]) -> str:
    capital = state.get("capital", "?")
    cash = state.get("cash", "?")
    open_legs = state.get("open", [])
    closed_legs = state.get("closed", [])
    runs = state.get("runs", [])
    open_mv = sum(float(leg.get("market_value", 0) or 0) for leg in open_legs)
    try:
        equity = float(str(cash)) + open_mv
        pnl = equity - float(str(capital))
        head_html = f"<p>Equity <strong>{_inr(equity)}</strong> (P&L {_inr(pnl)})</p>"
    except (ValueError, TypeError):
        head_html = "<p>Equity unavailable</p>"
    last_run = runs[-1] if runs else {}
    rows_open = "\n".join(
        "<tr><td>{sym}</td><td>{dt}</td><td>{qty}</td><td>{entry}</td>"
        "<td>{val}</td><td>{upl}</td></tr>".format(
            sym=_esc(leg.get("symbol")),
            dt=_esc(leg.get("entry_date")),
            qty=_esc(leg.get("shares")),
            entry=_inr(leg.get("entry_open")),
            val=_inr(leg.get("market_value", "?")),
            upl=_inr(leg.get("unrealized", "?")),
        )
        for leg in open_legs
    )
    rows_closed = "\n".join(
        "<tr><td>{sym}</td><td>{entry} &rarr; {exit_}</td><td>{net}</td></tr>".format(
            sym=_esc(leg.get("symbol")),
            entry=_esc(leg.get("entry_date")),
            exit_=_esc(leg.get("exit_date")),
            net=_inr(leg.get("net_cash", leg.get("net", "?"))),
        )
        for leg in closed_legs[-50:]
    )
    generated = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    return f"""<!DOCTYPE html>
<html lang="en">
<head><meta charset="utf-8">
<title>XS-Monthly Paper Watch (research only)</title>
<style>
body{{font-family:system-ui,sans-serif;max-width:1000px;margin:2rem auto;padding:0 1rem}}
table{{border-collapse:collapse;width:100%}}
td,th{{border:1px solid #ccc;padding:4px 8px;text-align:right}}
td:first-child,th:first-child{{text-align:left}}
.badge{{background:#eee;padding:2px 8px;border-radius:8px;font-size:0.85em}}
</style></head>
<body>
<h1>XS-Monthly Paper Watch <span class="badge">RESEARCH ONLY — no orders</span></h1>
{head_html}
<p>Capital {_inr(capital)} &middot; Cash {_inr(cash)} &middot; Open market value {_inr(open_mv)}</p>
<p>Open legs: {len(open_legs)} &middot; Closed legs: {len(closed_legs)} &middot; Runs: {len(runs)}</p>
<p>Last run: <code>{_esc(last_run)}</code></p>
<p>Generated {generated} — refresh to update. Source: <code>logs/xs_monthly_new/paper_watch/state.json</code></p>
<h2>Open legs (gross marks, cost pending)</h2>
<table><tr><th>Symbol</th><th>Entry</th><th>Shares</th><th>Price</th><th>Value</th><th>Unrealized</th></tr>
{rows_open or "<tr><td colspan=6>flat</td></tr>"}
</table>
<h2>Closed legs (net of full cost, last 50)</h2>
<table><tr><th>Symbol</th><th>Entry &rarr; Exit</th><th>Net &#8377;</th></tr>
{rows_closed or "<tr><td colspan=3>none yet</td></tr>"}
</table>
</body></html>
"""
