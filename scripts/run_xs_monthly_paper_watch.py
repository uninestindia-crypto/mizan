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

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from quant_system.research_xs_monthly.bars import load_cache_bars, read_universe_symbols
from quant_system.research_xs_monthly.paper import (
    FROZEN_RULE,
    NOTIONAL_CAPITAL_INR,
    latest_signal,
    settle_positions,
    size_positions,
)

STATE_NAME = "state.json"


def _load_state(state_path: Path) -> dict:
    if state_path.is_file():
        return json.loads(state_path.read_text(encoding="utf-8"))
    return {"rule": FROZEN_RULE, "open": [], "closed": [], "runs": []}


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

    settled = settle_positions(state.get("open", []), bars)
    state["open"] = settled["open"]
    state["closed"] = state.get("closed", []) + settled["closed"]
    for leg in settled["closed"]:
        if "proceeds" in leg:
            cash += Decimal(str(leg["proceeds"]))

    opened_now: list[dict] = []
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
            # Attach opening marks so state always carries the settled shape.
            state["open"] = settle_positions(sized, bars)["open"]
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
    open_mv = sum((Decimal(str(leg.get("market_value", "0"))) for leg in state["open"]), Decimal(0))
    equity = cash + open_mv
    run_note["equity"] = str(equity)
    run_note["cash"] = str(cash)
    state["capital"] = str(capital)
    state["cash"] = str(cash)
    state["runs"] = state.get("runs", []) + [run_note]
    state_path.write_text(json.dumps(state, indent=1), encoding="utf-8")

    stamp = datetime.now(UTC).strftime("%Y%m%d-%H%M%SZ")
    (args.state_dir / f"watch_{stamp}.md").write_text(_render(state, run_note, load_stats))
    print(f"symbols {len(bars)} bars {load_stats['bars_loaded']} asof {settled['asof']}")
    print(f"capital {capital} cash {cash} open_mv {open_mv} equity {equity}")
    print(f"open {len(state['open'])} closed {len(state['closed'])} runs {len(state['runs'])}")
    if state["closed"]:
        nets = [Decimal(str(leg["net"])) for leg in state["closed"]]
        print(f"closed legs mean net {sum(nets, Decimal(0)) / Decimal(len(nets))}")
    print(f"state {state_path}")
    return 0


def _render(state: dict, run_note: dict, load_stats: dict) -> str:
    lines = [
        "# XS-monthly paper watch (RESEARCH_ONLY, no orders)",
        "",
        f"- Rule: formation {FROZEN_RULE['formation_sessions']}, "
        f"hold {FROZEN_RULE['hold_sessions']}, top {FROZEN_RULE['top_frac']}, "
        f"cost {FROZEN_RULE['cost_ratio']}",
        f"- Book (notional, separate): capital {state.get('capital')} "
        f"cash {state.get('cash')} equity {run_note.get('equity')}",
        f"- Bars loaded: {load_stats['bars_loaded']}",
        f"- Run: {json.dumps(run_note)}",
        "",
        "## Open legs (gross marks, cost pending)",
        "",
    ]
    for leg in state["open"]:
        lines.append(
            f"- {leg['symbol']} entry {leg['entry_date']} @ {leg['entry_open']} "
            f"asof {leg['asof_date']} gross {leg['gross_mark']}"
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
