"""Clear a tripped risk halt on the paper portfolio, deliberately and without losing the book.

The session refuses to trade once `risk_halted` is set, and the message it prints used to say
"clear `risk_halted` in the state file". **That instruction could not be followed.** The file
carries a content hash and `load_portfolio` refuses anything whose payload does not match it, so a
hand-edit is rejected on the next run:

    portfolio state at ... does not match its own hash; refusing to resume from it

The only route that worked was deleting the file, which silently invents a fresh portfolio: the
holdings, the realized P&L, the fee total, the session count and the equity peak all reset, cash
returns to the nominal, and the next session runs and reports success. A recovery procedure that
destroys the position it was meant to recover is worse than none.

This script is the missing tool. It clears the halt and **changes nothing else**, rewriting the file
with a valid hash so the next session resumes from the real book.

Clearing a kill switch is a human decision, so this refuses to be silent about it: it prints the
halt, the book it is about to resume, and requires `--i-have-reviewed-the-book`.

    python scripts/clear_paper_halt.py                            # inspect, change nothing
    python scripts/clear_paper_halt.py --i-have-reviewed-the-book # clear it
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT / "src") not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT / "src"))

from quant_system.execution.paper_portfolio import (  # noqa: E402
    PaperPortfolioError,
    load_portfolio,
    save_portfolio,
)

STATE_PATH = PROJECT_ROOT / "logs/paper_runs/portfolio_state.json"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--state-path", default=str(STATE_PATH))
    parser.add_argument(
        "--i-have-reviewed-the-book",
        action="store_true",
        help="clear the halt. Without this the script only reports.",
    )
    args = parser.parse_args()
    path = Path(args.state_path)

    try:
        portfolio = load_portfolio(path)
    except PaperPortfolioError as error:
        print(f"REFUSED: {error}")
        print("The state file is not trustworthy. Do not delete it -- it holds the only record of")
        print("the running book. Investigate what wrote it.")
        return 2

    if portfolio is None:
        print(f"No portfolio state at {path}. There is nothing to clear.")
        return 1

    print(f"State file      : {path}")
    print(f"Halted          : {portfolio.risk_halted}")
    print(f"Halted on       : {portfolio.halted_on}")
    print(f"Reason          : {portfolio.halt_reason or '(not recorded)'}")
    print(f"Cash            : Rs {portfolio.cash}")
    print(f"Holdings        : {len(portfolio.holdings)}")
    for holding in sorted(portfolio.holdings.values(), key=lambda h: h.symbol):
        print(
            f"   {holding.symbol:12} {holding.quantity:>8} @ Rs {holding.average_cost} "
            f"(opened {holding.opened_on})"
        )
    print(f"Realized P&L    : Rs {portfolio.realized_pnl}")
    print(f"Fees to date    : Rs {portfolio.total_fees}")
    print(f"Equity peak     : Rs {portfolio.peak_equity}")
    print(f"Sessions        : {portfolio.sessions_completed}, held {portfolio.sessions_held}")

    if not portfolio.risk_halted:
        print("\nNot halted. Nothing to do.")
        return 0

    if not args.i_have_reviewed_the_book:
        print("\nThe halt was NOT cleared. Re-run with --i-have-reviewed-the-book to clear it.")
        print("The switch fired for a reason; read the book above before overriding it.")
        return 3

    portfolio.risk_halted = False
    portfolio.halted_on = None
    portfolio.halt_reason = ""
    save_portfolio(path, portfolio)

    # Prove the write is loadable rather than assume it. A rewrite that fails its own hash check
    # would leave the operator with a file the session refuses and no way back.
    reloaded = load_portfolio(path)
    if reloaded is None or reloaded.risk_halted:
        print("\nFAILED: the halt is still set after the rewrite. The file has not been repaired.")
        return 4
    if len(reloaded.holdings) != len(portfolio.holdings) or reloaded.cash != portfolio.cash:
        print("\nFAILED: the book changed during the rewrite. Do not run a session.")
        return 5

    print("\nHalt cleared. The book above is unchanged and the next session will resume from it.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
