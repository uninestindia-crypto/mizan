"""Run the XS-monthly research screen (new stack, research only).

Reads bars from a market-cache store + a universe CSV. Writes JSON + Markdown
under logs/xs_monthly_new/<stamp>/ (new directory; never logs/paper_runs/).

Pre-declared grid (fixed in code, not CLI-tunable):
  VALIDATED: hold 21, long top-20%  |  DIAGNOSTICS: hold-2 long-only,
  hold-2 long-short, hold-21 long-short.

No EvidenceStore writes, no multiplicity ordinals, no promotion, no orders.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from quant_system.research_xs_monthly.bars import load_cache_bars, read_universe_symbols
from quant_system.research_xs_monthly.screen import (
    DIAG_HOLD_SHORT,
    HOLD_SESSIONS,
    TOP_FRAC,
    run_long_short,
    run_screen,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cache-store", type=Path, required=True)
    parser.add_argument("--universe", type=Path, required=True)
    parser.add_argument("--out-dir", type=Path, default=Path("logs/xs_monthly_new"))
    parser.add_argument("--limit-symbols", type=int, default=0)
    parser.add_argument("--max-datasets", type=int, default=0)
    args = parser.parse_args(argv)

    stamp = datetime.now(UTC).strftime("%Y%m%d-%H%M%SZ")
    out_dir = args.out_dir / stamp
    out_dir.mkdir(parents=True, exist_ok=True)

    universe = read_universe_symbols(args.universe)
    if args.limit_symbols and args.limit_symbols > 0:
        universe = universe[: args.limit_symbols]
    wanted = set(universe)
    bars, load_stats = load_cache_bars(
        args.cache_store,
        symbols=wanted,
        max_datasets=args.max_datasets or None,
    )
    missing = sorted(wanted - set(bars))
    result: dict = {
        "pre_declaration": {
            "validated_rule": "longTopFrac_hold21",
            "diagnostics": ["longOnly_hold2", "longShort_hold2", "longShort_hold21"],
            "formation_sessions": 21,
            "top_frac": str(TOP_FRAC),
            "cost_ratio": "0.00224",
            "universe_file": str(args.universe),
            "cache_store": str(args.cache_store),
        },
        "universe_requested": len(wanted),
        "universe_loaded": len(bars),
        "universe_missing": missing,
        "load_stats": load_stats,
    }
    validated = run_screen(bars, hold=HOLD_SESSIONS, top_frac=TOP_FRAC)
    diag_lo2 = run_screen(bars, hold=DIAG_HOLD_SHORT, top_frac=TOP_FRAC)
    diag_ls2 = run_long_short(bars, hold=DIAG_HOLD_SHORT, top_frac=TOP_FRAC)
    diag_ls21 = run_long_short(bars, hold=HOLD_SESSIONS, top_frac=TOP_FRAC)
    result["validated_hold21_long"] = validated
    result["diagnostics"] = {
        "hold2_long": diag_lo2,
        "hold2_long_short": diag_ls2,
        "hold21_long_short": diag_ls21,
    }
    result["reading"] = {
        "survivorship_warning": (
            "Source universe is ACTIVE listings only; delisted/failed names are "
            "absent. A positive here is weak evidence; a negative is strong."
        ),
        "verdict": "RESEARCH_ONLY",
    }

    (out_dir / "xs_monthly_screen.json").write_text(json.dumps(result, indent=1), encoding="utf-8")
    (out_dir / "xs_monthly_screen.md").write_text(_render_markdown(result), encoding="utf-8")
    print(f"universe {len(bars)}/{len(wanted)} symbols, {load_stats['bars_loaded']} bars")
    _print_line("VALIDATED hold21 long", validated["leg"])
    _print_line("MARKET hold21 equalweight", validated["market_equalweight"])
    _print_line("DIAG hold2 long", diag_lo2["leg"])
    _print_line("DIAG hold2 long-short", diag_ls2)
    _print_line("DIAG hold21 long-short", diag_ls21)
    print(f"wrote {out_dir}")
    return 0


def _print_line(label: str, leg: dict) -> None:
    print(
        f"{label}: n={leg['n_periods']} mean={leg['mean_net']} "
        f"t={leg.get('t_stat')} sharpe_ann={leg.get('sharpe_annualized')} "
        f"degen={leg.get('degenerate')} skipped_locked={leg.get('skipped_locked')}"
    )


def _render_markdown(result: dict) -> str:
    lines = [
        "# XS-monthly screen (new stack, RESEARCH_ONLY)",
        "",
        f"- Universe: {result['universe_loaded']}/{result['universe_requested']} symbols loaded",
        f"- Bars: {result['load_stats']['bars_loaded']} "
        f"(invalid {result['load_stats']['bars_invalid']}, "
        f"dup-date {result['load_stats']['bars_duplicate_date']})",
        f"- Missing symbols: {len(result['universe_missing'])}",
        "",
        "## Validated: hold-21 long top-20%",
        "",
        _leg_table(result["validated_hold21_long"]["leg"]),
        _leg_table(
            result["validated_hold21_long"]["market_equalweight"], "market hold-21 equalweight"
        ),
        f"- IC: n={result['validated_hold21_long']['ic_n']} "
        f"mean={result['validated_hold21_long']['ic_mean']} "
        f"t={result['validated_hold21_long']['ic_t']}",
        f"- Rebalances: {result['validated_hold21_long']['rebalances']}, "
        f"calendar {result['validated_hold21_long']['calendar_start']}.."
        f"{result['validated_hold21_long']['calendar_end']} "
        f"({result['validated_hold21_long']['calendar_sessions']} sessions)",
        "",
        "## Diagnostics",
        "",
        _leg_table(result["diagnostics"]["hold2_long"]["leg"], "hold-2 long"),
        _leg_table(result["diagnostics"]["hold2_long_short"], "hold-2 long-short"),
        _leg_table(result["diagnostics"]["hold21_long_short"], "hold-21 long-short"),
        "",
        "## Reading",
        "",
        result["reading"]["survivorship_warning"],
        "",
        "Verdict: RESEARCH_ONLY. A screen cannot promote.",
    ]
    return "\n".join(lines) + "\n"


def _leg_table(leg: dict, title: str = "leg") -> str:
    return (
        f"- {title}: n={leg['n_periods']} mean={leg['mean_net']} "
        f"sd={leg['stdev_net']} t={leg.get('t_stat')} "
        f"sharpe_ann={leg.get('sharpe_annualized')} degen={leg.get('degenerate')} "
        f"skipped_locked={leg.get('skipped_locked')} empty={leg.get('empty_periods')}"
    )


if __name__ == "__main__":
    raise SystemExit(main())
