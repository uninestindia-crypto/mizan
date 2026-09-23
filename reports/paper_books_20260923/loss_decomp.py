"""Loss decomposition of the two Rs 10L paper books, measured 2026-09-23. Read-only.

Rebuilds the Mizan flagship book from its own fills, reads the XS-Monthly paper-watch state, and
measures both against NIFTY 50 and the NIFTY 500 equal-weight over the same windows. Writes
nothing. Every input is gitignored runtime state that changes daily, so the SHA-256 of each is
printed first: a rerun on changed inputs gives different numbers, and the hashes show whether the
inputs changed. The captured run is ``output.txt`` beside this file.

Run from the install root::

    .venv\\Scripts\\python.exe reports\\paper_books_20260923\\loss_decomp.py

Recorded by ``agent_context/work/completed/20260923-claude-paper-books-end-date.md``.
"""

from __future__ import annotations

import hashlib
import json
import statistics
import sys
from collections import defaultdict
from datetime import date
from decimal import Decimal as D
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from quant_system.research_xs_monthly.bars import (  # noqa: E402
    load_cache_bars,
    read_universe_symbols,
)

RUNS = ROOT / "logs" / "paper_runs"
XS_STATE = ROOT / "logs" / "xs_monthly_new" / "paper_watch" / "state.json"
NIFTY50 = ROOT / "data/evidence/market-cache/macro-refresh-20230828-20260827/macro_NIFTY50.json"
N500_CACHE = ROOT / "data/evidence/market-cache/nifty500-refresh-20230828-20260827"
N500_UNIVERSE = ROOT / "data/authorities/nse-nifty500-constituents.csv"
FIRST_SESSION = "2026-08-31"
CAPITAL = D(1_000_000)


def jload(path: Path) -> dict[str, Any]:
    payload: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
    return payload


def money(x: D | float) -> str:
    return f"{float(x):>14,.2f}"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


session_files = [
    p
    for p in sorted(RUNS.glob("paper_session_2026-*.json"))
    if jload(p).get("session_date", "") >= FIRST_SESSION
]
inputs = [
    *session_files,
    RUNS / "live_paper_status.json",
    RUNS / "portfolio_state.json",
    XS_STATE,
    NIFTY50,
    N500_CACHE / "ingestion-summary.json",
    N500_UNIVERSE,
]
print("INPUTS (sha256; the NIFTY 500 store is identified by its ingestion summary)")
for path in inputs:
    print(f"  {sha256(path)}  {path.relative_to(ROOT)}")

print()
print("=" * 100)
print(f"A. FLAGSHIP (Mizan) -- every session since {FIRST_SESSION}, fills and fees")
print("=" * 100)
sessions: list[dict[str, Any]] = []
for path in session_files:
    s = jload(path)
    perf = s.get("performance", {})
    cap = s.get("capital", {})
    sessions.append(s)
    print(
        f"{s.get('session_date')} {str(s.get('session_id'))[-22:]:>22} "
        f"fills={len(s.get('fills', [])):>3} "
        f"fees={perf.get('total_fees_paid')!s:>9} slip={perf.get('total_slippage_cost')!s:>8} "
        f"equity={cap.get('total_equity')!s:>11} ret%={perf.get('return_pct')!s:>8}"
    )

# Each symbol is bought at most once while open and sold whole, so a lot ledger suffices; the two
# checks below refuse to continue if that stops being true.
lots: dict[str, dict[str, Any]] = {}
closed: list[dict[str, Any]] = []
fees_by_session: dict[str, D] = defaultdict(D)
slip_by_session: dict[str, D] = defaultdict(D)
for s in sessions:
    sid = str(s.get("session_id"))
    slip_by_session[sid] += D(str(s.get("performance", {}).get("total_slippage_cost", "0")))
    for fill in s.get("fills", []):
        qty = int(fill["quantity"])
        px = D(str(fill["price"]))
        fee = D(str(fill["fee"]))
        fees_by_session[sid] += fee
        sym = fill["symbol"]
        if fill["side"] == "BUY":
            if sym in lots:
                raise SystemExit(f"second BUY for open {sym}; ledger assumption broken")
            lots[sym] = {"sym": sym, "q": qty, "px": px, "fee": fee, "date": s["session_date"]}
        else:
            lot = lots.pop(sym)
            if lot["q"] != qty:
                raise SystemExit(f"partial SELL for {sym}; ledger assumption broken")
            closed.append({**lot, "exit_px": px, "exit_fee": fee, "exit_date": s["session_date"]})

status = jload(RUNS / "live_paper_status.json")
marks = {
    row["symbol"]: D(str(row["current_price"]))
    for row in status["positions_detail"]
    if row.get("symbol") and row.get("current_price") is not None
}
state = jload(RUNS / "portfolio_state.json")["payload"]
held_syms = {h["symbol"] for h in state["holdings"]}
if held_syms != set(lots):
    raise SystemExit(f"fills disagree with portfolio_state holdings: {held_syms ^ set(lots)}")

cohort_a_closed = [c for c in closed if c["date"] == FIRST_SESSION]
cohort_a_held = [lot for lot in lots.values() if lot["date"] == FIRST_SESSION]
cohort_b_held = [lot for lot in lots.values() if lot["date"] != FIRST_SESSION]

price_a_closed = sum((c["q"] * (c["exit_px"] - c["px"]) for c in cohort_a_closed), D(0))
price_a_held = sum((lot["q"] * (marks[lot["sym"]] - lot["px"]) for lot in cohort_a_held), D(0))
price_b_held = sum((lot["q"] * (marks[lot["sym"]] - lot["px"]) for lot in cohort_b_held), D(0))
fees_total = sum(fees_by_session.values(), D(0))
slip_total = sum(slip_by_session.values(), D(0))
equity = D(state["cash"]) + sum((lot["q"] * marks[lot["sym"]] for lot in lots.values()), D(0))
recon = CAPITAL + price_a_closed + price_a_held + price_b_held - fees_total

print()
print(
    f"Cohort A (bought {FIRST_SESSION}): {len(cohort_a_closed) + len(cohort_a_held)} names; "
    f"{len(cohort_a_closed)} sold since, {len(cohort_a_held)} still held"
)
print(f"Cohort B (bought later): {len(cohort_b_held)} names")
print(f"  price P&L, A sold at fill            {money(price_a_closed)}")
print(f"  price P&L, A still held at mark      {money(price_a_held)}")
print(f"  price P&L, B fill -> mark            {money(price_b_held)}")
print(f"  statutory fees, all sessions         {money(-fees_total)}")
print(f"  = reconstructed equity               {money(recon)}")
print(f"  cash + marked value                  {money(equity)}   status: {status['total_equity']}")
print(f"  slippage inside the fill prices      {money(-slip_total)}")
entry_a = sum((c["q"] * c["px"] for c in cohort_a_closed), D(0)) + sum(
    (lot["q"] * lot["px"] for lot in cohort_a_held), D(0)
)
print(f"  cohort A invested at cost            {money(entry_a)}  ({float(entry_a / CAPITAL):.1%})")
print(
    f"  cohort A price return on cost        {float((price_a_closed + price_a_held) / entry_a):+.3%}"
)
legs = [(c["sym"], c["q"] * (c["exit_px"] - c["px"])) for c in cohort_a_closed] + [
    (lot["sym"], lot["q"] * (marks[lot["sym"]] - lot["px"])) for lot in cohort_a_held
]
legs.sort(key=lambda t: t[1])
print(f"  cohort A winners                     {sum(1 for _, v in legs if v > 0)} / {len(legs)}")
print("  worst 8 legs:", ", ".join(f"{s} {float(v):+,.0f}" for s, v in legs[:8]))
print("  best 5 legs: ", ", ".join(f"{s} {float(v):+,.0f}" for s, v in legs[-5:]))
cohort_a_syms = [s for s, _ in legs]

print()
print("=" * 100)
print("B. XS-MONTHLY -- paper-watch state")
print("=" * 100)
xs = jload(XS_STATE)
priced = [leg for leg in xs["open"] if "market_value" in leg and not leg.get("unpriced")]
unpriced = [leg for leg in xs["open"] if leg not in priced]
xs_entry = sum((D(leg["entry_value"]) for leg in priced), D(0))
xs_unrl = sum((D(leg["unrealized"]) for leg in priced), D(0))
xs_mv = sum((D(leg["market_value"]) for leg in priced), D(0))
xs_cash = D(str(xs["cash"]))
print(
    f"asof {sorted({leg.get('asof_date') for leg in xs['open']})}; "
    f"entry {sorted({leg.get('entry_date') for leg in xs['open']})}; "
    f"last run {xs['runs'][-1].get('at')}"
)
print(
    f"priced legs {len(priced)}: entry {money(xs_entry)}  mv {money(xs_mv)}  "
    f"unrealized {money(xs_unrl)} ({float(xs_unrl / xs_entry):+.3%} on cost)"
)
for leg in unpriced:
    print(
        f"UNPRICED {leg['symbol']} shares={leg.get('shares')} entry_value={leg.get('entry_value')}"
    )
unpriced_cost = sum((D(leg["entry_value"]) for leg in unpriced), D(0))
print(
    f"displayed equity {money(xs_cash + xs_mv)}  -> shown loss {money(xs_cash + xs_mv - CAPITAL)}"
)
print(f"  of which unpriced legs left out at cost            {money(-unpriced_cost)}")
print(f"  loss on the priced legs, gross of pending cost     {money(xs_unrl)}")
print(f"  priced winners {sum(1 for leg in priced if D(leg['unrealized']) > 0)} / {len(priced)}")
xs_legs = sorted(((leg["symbol"], D(leg["unrealized"])) for leg in priced), key=lambda t: t[1])
print("  worst 8 legs:", ", ".join(f"{s} {float(v):+,.0f}" for s, v in xs_legs[:8]))
print("  best 5 legs: ", ", ".join(f"{s} {float(v):+,.0f}" for s, v in xs_legs[-5:]))
print(f"  round-trip cost still to be charged at exit ~ {money(-xs_entry * D('0.00224'))}")

print()
print("=" * 100)
print("C. MARKET over the same windows")
print("=" * 100)
nifty = jload(NIFTY50)
nb = {c[0][:10]: {"open": c[1], "close": c[4]} for c in nifty["candles"]}
print(
    f"NIFTY 50 cache ends {max(nb)}; closes: "
    + ", ".join(f"{d[5:]}={nb[d]['close']:.0f}" for d in sorted(nb) if d >= "2026-08-28")
)


def nifty_ret(d0: str, f0: str, d1: str, f1: str) -> float:
    return float(nb[d1][f1] / nb[d0][f0] - 1)


bar_lists, _stats = load_cache_bars(
    N500_CACHE / "store", symbols=set(read_universe_symbols(N500_UNIVERSE))
)
bars = {sym: {b.exchange_date: b for b in lst} for sym, lst in bar_lists.items()}
latest = max(max(v) for v in bars.values() if v)
print(f"NIFTY 500 store: {len(bars)} symbols; newest bar {latest}")


def leg_ret(sym: str, d0: date, f0: str, d1: date, f1: str) -> float | None:
    b = bars.get(sym, {})
    if d0 not in b or d1 not in b:
        return None
    start, end = getattr(b[d0], f0), getattr(b[d1], f1)
    return float(end / start - 1) if start > 0 else None


def universe_ew(d0: date, f0: str, d1: date, f1: str) -> tuple[float, float, int, list[Any]]:
    """Equal-weight NIFTY 500; HEG and any |return| > 40% (unadjusted corporate actions) excluded."""
    rets, dropped = [], []
    for sym in bars:
        r = leg_ret(sym, d0, f0, d1, f1)
        if r is None:
            continue
        if sym == "HEG" or abs(r) > 0.40:
            dropped.append((sym, round(r, 3)))
            continue
        rets.append(r)
    return statistics.fmean(rets), statistics.median(rets), len(rets), dropped


def picks_ew(
    syms: list[str], d0: date, f0: str, d1: date, f1: str
) -> tuple[float, float, int, list[str]]:
    rets, missing = [], []
    for sym in syms:
        r = leg_ret(sym, d0, f0, d1, f1)
        if r is not None and abs(r) <= 0.40:
            rets.append(r)
        else:
            missing.append(sym)
    return statistics.fmean(rets), statistics.median(rets), len(rets), missing


start_a = date(2026, 8, 31)
print()
print(f"-- Flagship cohort A window: {start_a} close -> {latest} close")
um, umed, un, udrop = universe_ew(start_a, "close", latest, "close")
pm, pmed, pn, pmiss = picks_ew(cohort_a_syms, start_a, "close", latest, "close")
print(
    f"   NIFTY 50                         {nifty_ret(str(start_a), 'close', str(latest), 'close'):+.3%}"
)
print(f"   NIFTY 500 equal-weight (n={un})  mean {um:+.3%}  median {umed:+.3%}  dropped {udrop}")
print(f"   the book's picks (n={pn})         mean {pm:+.3%}  median {pmed:+.3%}  missing {pmiss}")
print(f"   picks minus universe             {pm - um:+.3%}")
print("   daily, from the same start (picks / universe / NIFTY 50):")
for d in sorted({d for v in bars.values() for d in v if start_a < d <= latest}):
    dpm = picks_ew(cohort_a_syms, start_a, "close", d, "close")[0]
    dum = universe_ew(start_a, "close", d, "close")[0]
    dn = nifty_ret(str(start_a), "close", str(d), "close") if str(d) in nb else float("nan")
    print(f"     {d}: {dpm:+.3%} / {dum:+.3%} / {dn:+.3%}")

xs_entry_day, xs_mark_day = date(2026, 9, 2), date(2026, 9, 16)
print()
print(f"-- XS window: {xs_entry_day} open -> {xs_mark_day} open")
xs_syms = [leg["symbol"] for leg in xs["open"]]
um2, umed2, un2, udrop2 = universe_ew(xs_entry_day, "open", xs_mark_day, "open")
xm, xmed, xn, xmiss = picks_ew(xs_syms, xs_entry_day, "open", xs_mark_day, "open")
print(
    f"   NIFTY 50                         "
    f"{nifty_ret(str(xs_entry_day), 'open', str(xs_mark_day), 'open'):+.3%}"
)
print(f"   NIFTY 500 equal-weight (n={un2}) mean {um2:+.3%}  median {umed2:+.3%}  dropped {udrop2}")
print(f"   XS picks (n={xn})                 mean {xm:+.3%}  median {xmed:+.3%}  missing {xmiss}")
print(f"   picks minus universe             {xm - um2:+.3%}")

print()
print("-- Was momentum itself punished? NIFTY 500 by 21-session formation return (XS buys Q5)")
cal = sorted({d for v in bars.values() for d in v if d <= date(2026, 9, 1)})
f_start, f_end = cal[-22], cal[-1]
rows = []
for sym in bars:
    fr = leg_ret(sym, f_start, "close", f_end, "close")
    hr = leg_ret(sym, xs_entry_day, "open", xs_mark_day, "open")
    if fr is None or hr is None or abs(hr) > 0.40 or sym == "HEG":
        continue
    rows.append((fr, hr, sym))
rows.sort()
k = len(rows) // 5
for qi in range(5):
    chunk = rows[qi * k : (qi + 1) * k] if qi < 4 else rows[4 * k :]
    print(
        f"   Q{qi + 1} n={len(chunk):>3} formation {statistics.fmean(r[0] for r in chunk):+.2%}  "
        f"then {statistics.fmean(r[1] for r in chunk):+.3%}"
    )
print(
    f"   formation {f_start} -> {f_end}; Q5 holds {len({r[2] for r in rows[4 * k :]} & set(xs_syms))}"
)
print(f"   of the {len(xs_syms)} XS names")

print()
print("-- XS priced legs re-marked at the newest cached bars (its own convention is the open)")
for d, field in (
    (xs_mark_day, "open"),
    (date(2026, 9, 17), "open"),
    (latest, "open"),
    (latest, "close"),
):
    mv = D(0)
    missing = []
    for leg in priced:
        b = bars.get(leg["symbol"], {}).get(d)
        if b is None:
            missing.append(leg["symbol"])
            continue
        mv += leg["shares"] * getattr(b, field)
    print(
        f"   {d} {field:<5}: unrealized {money(mv - xs_entry)} "
        f"({float((mv - xs_entry) / xs_entry):+.3%})  missing {missing}"
    )
heg = bars.get("HEG", {})
for d in (xs_entry_day, date(2026, 9, 4), date(2026, 9, 7), xs_mark_day, latest):
    if d in heg:
        print(f"   HEG parent {d}: open {heg[d].open} close {heg[d].close}")
