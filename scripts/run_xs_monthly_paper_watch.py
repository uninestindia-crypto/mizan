"""Run the XS-monthly forward paper watch (new stack, research only).

Owns ONLY ``logs/xs_monthly_new/paper_watch/state.json`` (+ per-run Markdown).
Reads the market-cache store + universe CSV. Places no orders, calls no
broker, touches no paper_pilot / server / dashboard path.

Each run: settle open legs (close where the 21-session exit exists, else
mark), then open the latest frozen-rule signal when flat.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from quant_system.data.held_corporate_actions import load_nse_corporate_actions
from quant_system.research_xs_monthly.bars import load_cache_bars, read_universe_symbols
from quant_system.research_xs_monthly.paper import (
    ENTITLEMENT_AUTHORITY,
    FROZEN_RULE,
    NOTIONAL_CAPITAL_INR,
    book_value,
    latest_signal,
    load_unpriced_entitlements,
    settle_positions,
    size_positions,
    unreviewed_corporate_actions,
)
from quant_system.research_xs_monthly.screen import build_calendar

STATE_NAME = "state.json"


def _load_state(state_path: Path) -> dict[str, Any]:
    if state_path.is_file():
        payload: dict[str, Any] = json.loads(state_path.read_text(encoding="utf-8"))
        return payload
    return {"rule": FROZEN_RULE, "open": [], "closed": [], "unresolved": [], "runs": []}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--cache-store",
        type=Path,
        default=Path("data/evidence/market-cache/nifty500-refresh-20230828-20260827/store"),
    )
    parser.add_argument(
        "--universe",
        type=Path,
        default=Path("data/authorities/nse-nifty500-constituents.csv"),
    )
    parser.add_argument("--state-dir", type=Path, default=Path("logs/xs_monthly_new/paper_watch"))
    parser.add_argument(
        "--entitlement-authority",
        type=Path,
        default=ENTITLEMENT_AUTHORITY,
        help="issuer-filed corporate-action entitlements; a leg held across one is not valued",
    )
    parser.add_argument(
        "--corporate-actions-dir",
        type=Path,
        default=Path(
            "data/evidence/market-cache/nifty500-refresh-20230828-20260827/corporate-actions"
        ),
        help="NSE corporate-action records; a leg held across an unreviewed split, bonus, demerger "
        "or rights issue is not valued",
    )
    args = parser.parse_args(argv)
    args.state_dir.mkdir(parents=True, exist_ok=True)
    state_path = args.state_dir / STATE_NAME

    universe = read_universe_symbols(args.universe)
    bars, load_stats = load_cache_bars(args.cache_store, symbols=set(universe))
    state = _load_state(state_path)
    if state.get("rule") != FROZEN_RULE:
        raise SystemExit("REFUSING: state file rule differs from FROZEN_RULE — inspect by hand")
    if not bars:
        raise SystemExit("REFUSING: no bars loaded")
    capital = Decimal(str(state.get("capital", NOTIONAL_CAPITAL_INR)))
    cash = Decimal(str(state.get("cash", capital)))

    # Migration: legs opened before the book existed carry no shares. Re-open
    # from the latest signal at identical entries, now sized. Only valid while
    # no exit has elapsed (entry == latest signal entry); otherwise refuse.
    if state.get("open") and any("shares" not in leg for leg in state["open"]):
        migration_signal = latest_signal(bars)
        if any(leg["entry_date"] != migration_signal["entry_date"] for leg in state["open"]):
            raise SystemExit("REFUSING: legacy open legs predate latest signal — inspect by hand")
        state["open"] = []
        cash = capital
        print("migrated legacy open legs to sized book (same entries)")

    # Built from the issuer-filed authority, not from price. A leg held across a corporate action of
    # unknown size cannot be valued as shares * latest_open; see paper.load_unpriced_entitlements.
    held = state.get("open", [])
    entitlements = load_unpriced_entitlements(held, bars, args.entitlement_authority)
    # Every structural action NSE published for the names held, not only the hand-kept list. The
    # authority's reason wins where both name a leg. A missing record file is a warning: "no record"
    # is not "no action", but refusing the whole book over it would stop the watch on a data gap.
    ca_records, ca_missing = load_nse_corporate_actions(
        args.corporate_actions_dir, [str(leg["symbol"]) for leg in held]
    )
    if held and ca_missing:
        print(
            f"WARNING: no NSE corporate-action record for {len(ca_missing)} held name(s), so an "
            f"action on them cannot be ruled out: {', '.join(ca_missing)}"
        )
    for symbol, reason in unreviewed_corporate_actions(
        held, ca_records, build_calendar(bars)[-1]
    ).items():
        entitlements.setdefault(symbol, reason)
    settled = settle_positions(held, bars, unpriced_entitlements=entitlements)
    state["open"] = settled["open"]
    state["closed"] = state.get("closed", []) + settled["closed"]
    # Matured but unvaluable: leaves `open` so the book can rebalance, but pays no proceeds into
    # cash, because none were received. The committed capital is reported, never written off.
    state["unresolved"] = state.get("unresolved", []) + settled["unresolved"]
    for leg in settled["closed"]:
        if "proceeds" in leg:
            cash += Decimal(str(leg["proceeds"]))

    opened_now: list[dict[str, Any]] = []
    if not state["open"]:
        signal = latest_signal(bars)
        last_exit = max((leg["exit_date"] for leg in state["closed"]), default="")
        if signal["entry_date"] > last_exit:
            fresh = [
                {
                    "symbol": h["symbol"],
                    "entry_date": h["entry_date"],
                    "entry_open": h["entry_open"],
                }
                for h in signal["holdings"]
            ]
            sized, cash = size_positions(fresh, cash)
            # Attach opening marks so state always carries the settled shape. The map is rebuilt for
            # the new legs: a fresh entry can still sit behind a filed ex-date the cache has not
            # reached, and the default would silently value it.
            fresh_entitlements = load_unpriced_entitlements(sized, bars, args.entitlement_authority)
            state["open"] = settle_positions(sized, bars, unpriced_entitlements=fresh_entitlements)[
                "open"
            ]
            opened_now = state["open"]
        run_note = {
            "at": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "decision": signal["decision_date"],
            "entry": signal["entry_date"],
            "scored": signal["scored_names"],
            "opened": len(opened_now),
            "skipped_locked": signal["skipped_locked"],
        }
    else:
        run_note = {
            "at": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "note": "holding",
            "open_legs": len(state["open"]),
            "newly_closed": len(settled["closed"]),
        }
    # Was: sum(leg.get("market_value", "0")). That default is the defect -- it reads an asset nobody
    # can value as worth zero. book_value keeps the two apart and makes the caller say which is which.
    valued = book_value(state["open"], state.get("unresolved", []))
    open_mv = valued["priced_market_value"]
    equity = cash + open_mv
    run_note["equity"] = str(equity)
    run_note["equity_basis"] = "cash + priced marks; excludes unpriced holdings listed separately"
    run_note["cash"] = str(cash)
    if valued["unpriced"]:
        run_note["unpriced_at_cost"] = str(valued["unpriced_at_cost"])
        run_note["unpriced_legs"] = valued["unpriced"]
    state["capital"] = str(capital)
    state["cash"] = str(cash)
    state["runs"] = state.get("runs", []) + [run_note]
    state_path.write_text(json.dumps(state, indent=1), encoding="utf-8")

    stamp = datetime.now(UTC).strftime("%Y%m%d-%H%M%SZ")
    (args.state_dir / f"watch_{stamp}.md").write_text(_render(state, run_note, load_stats))
    print(f"symbols {len(bars)} bars {load_stats['bars_loaded']} asof {settled['asof']}")
    print(f"capital {capital} cash {cash} open_mv {open_mv} equity {equity}")
    print(f"open {len(state['open'])} closed {len(state['closed'])} runs {len(state['runs'])}")
    if valued["unpriced"]:
        print(
            f"UNPRICED {len(valued['unpriced'])} holding(s), "
            f"entry cost {valued['unpriced_at_cost']}, EXCLUDED from equity above:"
        )
        for item in valued["unpriced"]:
            print(f"  {item['symbol']} entry_value {item['entry_value']} -- {item['reason']}")
    if state["closed"]:
        nets = [Decimal(str(leg["net"])) for leg in state["closed"]]
        print(f"closed legs mean net {sum(nets, Decimal(0)) / Decimal(len(nets))}")
    print(f"state {state_path}")
    return 0


def _render(state: dict[str, Any], run_note: dict[str, Any], load_stats: dict[str, Any]) -> str:
    lines = [
        "# XS-monthly paper watch (RESEARCH_ONLY, no orders)",
        "",
        f"- Rule: formation {FROZEN_RULE['formation_sessions']}, "
        f"hold {FROZEN_RULE['hold_sessions']}, top {FROZEN_RULE['top_frac']}, "
        f"cost {FROZEN_RULE['cost_ratio']}",
        f"- Book (notional, separate): capital {state.get('capital')} "
        f"cash {state.get('cash')} equity {run_note.get('equity')}",
        "- Equity basis: cash + priced marks. Any unpriced holding is listed below and is **not**"
        " included at cost, at zero, or at any other number.",
        f"- Bars loaded: {load_stats['bars_loaded']}",
        f"- Run: {json.dumps(run_note)}",
        "",
        "## Open legs (gross marks, cost pending)",
        "",
    ]
    for leg in state["open"]:
        if leg.get("unpriced"):
            # No gross mark exists for this leg, by design. Formatting one here -- even as "n/a" in a
            # returns column -- is how an exclusion turns back into a number a reader trusts.
            lines.append(
                f"- {leg['symbol']} entry {leg['entry_date']} @ {leg['entry_open']} "
                f"asof {leg.get('asof_date', '?')} **UNPRICED** -- {leg['unpriced_reason']}"
            )
            continue
        lines.append(
            f"- {leg['symbol']} entry {leg['entry_date']} @ {leg['entry_open']} "
            f"asof {leg['asof_date']} gross {leg['gross_mark']}"
        )
    unresolved = state.get("unresolved", [])
    if unresolved:
        lines += [
            "",
            "## Unresolved legs (hold matured, holding could not be valued)",
            "",
            "These paid no proceeds into cash. The capital is still committed and its value is"
            " unknown -- not zero, and not break-even.",
            "",
        ]
        for leg in unresolved:
            lines.append(
                f"- {leg['symbol']} entry {leg['entry_date']} matured {leg['matured_on']} "
                f"entry_value {leg['entry_value']} -- {leg['unpriced_reason']}"
            )
    lines += ["", "## Closed legs (net of full round-trip cost)", ""]
    for leg in state["closed"][-20:]:
        lines.append(
            f"- {leg['symbol']} {leg['entry_date']} -> {leg['exit_date']} net {leg['net']}"
        )
    lines += ["", "No orders placed. Paper watch only."]
    return "\n".join(lines) + "\n"


if __name__ == "__main__":
    raise SystemExit(main())
