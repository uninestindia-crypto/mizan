"""Replay XS-Monthly's exit on past data through the real runner, in scratch state. Read-only.

Founder decision 2026-09-23, fix F3: the stopped XS book never reached its first exit, so the close
path had never run on real data. Rather than waiting for one, this replays it. Each case opens a
book exactly as a fresh run would have (`latest_signal` and `size_positions` on bars cut at an
earlier date), then runs the real `scripts/run_xs_monthly_paper_watch.py` against the full cache
with `--state-dir` pointing at a scratch directory. The live book in `logs/xs_monthly_new/` is
never read or written.

Case A enters 21 sessions before the newest cached bar, so its exit lands on the last cached day.
The run must close every priced leg at the exit open, charge the 0.224% round trip exactly once,
send HEG -- held across its 2026-09-07 demerger -- to `unresolved` with no proceeds, reconcile
cash, and open no new cohort, because the data ends on the exit day.

Case B enters one session earlier, so its exit is the day before the newest bar. The same run must
close, and then open a fresh cohort at the newest open. That is the behaviour which made the order
of the planned 6 Oct switch-off matter.

HEG is added to a case's selection when the signal did not pick it, so the entitlement path is
always exercised; the output says when that happened.

Run from the install root, with a scratch directory outside the repository::

    .venv\\Scripts\\python.exe reports\\paper_books_20260923\\xs_exit_replay.py <scratch-dir>

Exits 1 if any check fails. The captured run is ``xs_exit_replay_output.txt`` beside this file.
"""

from __future__ import annotations

import json
import subprocess
import sys
from datetime import date
from decimal import Decimal
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from quant_system.data.held_corporate_actions import load_nse_corporate_actions  # noqa: E402
from quant_system.research_xs_monthly.bars import (  # noqa: E402
    Bar,
    load_cache_bars,
    read_universe_symbols,
)
from quant_system.research_xs_monthly.paper import (  # noqa: E402
    ENTITLEMENT_AUTHORITY,
    FROZEN_RULE,
    NOTIONAL_CAPITAL_INR,
    latest_signal,
    load_unpriced_entitlements,
    settle_positions,
    size_positions,
    unreviewed_corporate_actions,
)
from quant_system.research_xs_monthly.screen import build_calendar  # noqa: E402

CACHE = ROOT / "data/evidence/market-cache/nifty500-refresh-20230828-20260827/store"
UNIVERSE = ROOT / "data/authorities/nse-nifty500-constituents.csv"
AUTHORITY = ROOT / ENTITLEMENT_AUTHORITY
CORPORATE_ACTIONS = (
    ROOT / "data/evidence/market-cache/nifty500-refresh-20230828-20260827/corporate-actions"
)
HOLD = int(str(FROZEN_RULE["hold_sessions"]))
COST = Decimal(str(FROZEN_RULE["cost_ratio"]))

failures: list[str] = []


def check(condition: bool, message: str) -> None:
    print(f"  {'PASS' if condition else 'FAIL'}  {message}")
    if not condition:
        failures.append(message)


def open_book(bars: dict[str, list[Bar]], entry_on: date) -> tuple[dict[str, Any], bool]:
    """The state a fresh run would have written had the cache ended on `entry_on`."""
    cut = {sym: [b for b in lst if b.exchange_date <= entry_on] for sym, lst in bars.items()}
    cut = {sym: lst for sym, lst in cut.items() if lst}
    signal = latest_signal(cut)
    if signal["entry_date"] != entry_on.isoformat():
        raise SystemExit(f"signal entered {signal['entry_date']}, expected {entry_on}")
    fresh = [
        {"symbol": h["symbol"], "entry_date": h["entry_date"], "entry_open": h["entry_open"]}
        for h in signal["holdings"]
    ]
    injected = "HEG" not in {leg["symbol"] for leg in fresh}
    if injected:
        heg_bar = next(b for b in bars["HEG"] if b.exchange_date == entry_on)
        fresh.append(
            {"symbol": "HEG", "entry_date": entry_on.isoformat(), "entry_open": str(heg_bar.open)}
        )
    sized, cash = size_positions(fresh, NOTIONAL_CAPITAL_INR)
    flagged = load_unpriced_entitlements(sized, cut, AUTHORITY)
    state = {
        "rule": FROZEN_RULE,
        "open": settle_positions(sized, cut, unpriced_entitlements=flagged)["open"],
        "closed": [],
        "unresolved": [],
        "runs": [],
        "capital": str(NOTIONAL_CAPITAL_INR),
        "cash": str(cash),
    }
    return state, injected


def replay(
    name: str,
    bars: dict[str, list[Bar]],
    calendar: list[date],
    entry_on: date,
    scratch: Path,
    expect_reopen: bool,
) -> None:
    exit_on = calendar[calendar.index(entry_on) + HOLD]
    print(
        f"\n== {name}: enter {entry_on}, exit due at the {exit_on} open, cache ends {calendar[-1]}"
    )
    state, injected = open_book(bars, entry_on)
    before_cash = Decimal(state["cash"])
    # What the runner will decline to value: the hand-kept authority's flags at open, plus every
    # structural action NSE published for these names inside the hold, exactly as the runner reads
    # them at settle.
    records, _missing = load_nse_corporate_actions(
        CORPORATE_ACTIONS, {str(leg["symbol"]) for leg in state["open"]}
    )
    nse_flags = unreviewed_corporate_actions(state["open"], records, calendar[-1])
    priced = [
        leg
        for leg in state["open"]
        if not leg.get("unpriced") and str(leg["symbol"]) not in nse_flags
    ]
    unpriced = [leg for leg in state["open"] if leg not in priced]
    if nse_flags:
        print(f"  flagged from NSE records: {sorted(nse_flags)}")
    print(
        f"  opened {len(state['open'])} legs ({len(priced)} priced, {len(unpriced)} unpriced), "
        f"cash left {before_cash}{'; HEG added to exercise the entitlement path' if injected else ''}"
    )
    state_dir = scratch / name
    state_dir.mkdir(parents=True, exist_ok=False)
    (state_dir / "state.json").write_text(json.dumps(state, indent=1), encoding="utf-8")

    run = subprocess.run(
        [
            sys.executable,
            str(ROOT / "scripts/run_xs_monthly_paper_watch.py"),
            "--state-dir",
            str(state_dir),
            "--cache-store",
            str(CACHE),
            "--universe",
            str(UNIVERSE),
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    check(run.returncode == 0, f"runner exited {run.returncode}")
    if run.returncode != 0:
        print(run.stdout[-2000:], run.stderr[-2000:])
        return
    after = json.loads((state_dir / "state.json").read_text(encoding="utf-8"))

    opens = {sym: {b.exchange_date: b.open for b in lst} for sym, lst in bars.items()}
    closed = {leg["symbol"]: leg for leg in after["closed"]}
    check(
        set(closed) == {leg["symbol"] for leg in priced},
        f"every priced leg closed ({len(closed)} of {len(priced)})",
    )
    check(
        all(leg["exit_date"] == exit_on.isoformat() for leg in closed.values()),
        f"every close dated {exit_on}",
    )
    price_ok = cost_ok = proceeds_ok = True
    for leg in closed.values():
        exit_open = opens[leg["symbol"]][exit_on]
        entry_value = Decimal(leg["entry_value"])
        exit_value = Decimal(leg["shares"]) * exit_open
        price_ok &= Decimal(leg["exit_open"]) == exit_open
        cost_ok &= Decimal(leg["cost"]) == COST * entry_value
        proceeds_ok &= Decimal(leg["proceeds"]) == exit_value - COST * entry_value
    check(price_ok, "every exit priced at that day's cached open")
    check(cost_ok, "cost is 0.224% of entry value, charged once per leg")
    check(proceeds_ok, "proceeds are exit value minus that cost")

    unresolved = {leg["symbol"]: leg for leg in after.get("unresolved", [])}
    check(
        set(unresolved) == {leg["symbol"] for leg in unpriced},
        f"unpriced legs went to unresolved: {sorted(unresolved)}",
    )
    check(
        all("proceeds" not in leg for leg in unresolved.values()),
        "unresolved legs paid no proceeds",
    )
    check("HEG" in unresolved, "HEG, held across its demerger, is unresolved rather than closed")

    proceeds = sum((Decimal(leg["proceeds"]) for leg in closed.values()), Decimal(0))
    reopened = after["open"]
    new_entries = sum((Decimal(leg["entry_value"]) for leg in reopened), Decimal(0))
    check(
        Decimal(after["cash"]) == before_cash + proceeds - new_entries,
        f"cash reconciles: {before_cash} + proceeds {proceeds} - new entries {new_entries} "
        f"= {after['cash']}",
    )
    if expect_reopen:
        check(bool(reopened), f"a new cohort opened ({len(reopened)} legs)")
        check(
            all(leg["entry_date"] == calendar[-1].isoformat() for leg in reopened),
            f"the new cohort entered at the newest open, {calendar[-1]}",
        )
    else:
        check(not reopened, "no new cohort: the data ends on the exit day")
    nets = [Decimal(leg["net"]) for leg in closed.values()]
    print(
        f"  closed legs: mean net {sum(nets, Decimal(0)) / len(nets):+.4%}, "
        f"{sum(1 for n in nets if n > 0)} of {len(nets)} positive (costs included)"
    )


def main() -> int:
    if len(sys.argv) != 2:
        raise SystemExit(__doc__)
    scratch = Path(sys.argv[1]).resolve()
    if scratch == ROOT or ROOT in scratch.parents:
        raise SystemExit("REFUSING: the scratch directory must be outside the repository")
    universe = read_universe_symbols(UNIVERSE)
    bars, _stats = load_cache_bars(CACHE, symbols=set(universe))
    calendar = build_calendar(bars)
    print(f"cache: {len(bars)} symbols, calendar ends {calendar[-1]}")
    replay("case_a_exit_on_last_day", bars, calendar, calendar[-1 - HOLD], scratch, False)
    replay("case_b_exit_before_last_day", bars, calendar, calendar[-2 - HOLD], scratch, True)
    print(f"\n{'ALL CHECKS PASSED' if not failures else f'{len(failures)} CHECK(S) FAILED'}")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
