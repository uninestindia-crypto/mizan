"""Review a corporate action on a paper holding, and record it in the book it belongs to.

Both paper books refuse to value a holding carried across a split, bonus, consolidation, demerger or
rights issue that no one has reviewed: the flagship will not trade (it exits 11), and the XS watch
declines to mark the leg. This is how a person clears one, after reading the company's filing.

    # Look first: nothing is written without --apply.
    python scripts/apply_paper_corporate_action.py --book flagship --symbol ABC --ex-date 2026-10-12 --bonus 1:1

    # Then record it.
    python scripts/apply_paper_corporate_action.py --book flagship --symbol ABC --ex-date 2026-10-12 --bonus 1:1 --apply

    # Face value from Rs 10 to Rs 2, a 1-for-5 split:        --face-value 10:2
    # Nothing to adjust, so say why:                          --acknowledge "rights not taken up"
    # The XS book instead of the flagship:                    --book xs

The ratio is checked against the NSE record for that ex-date. A ratio that contradicts what NSE
published is refused. One NSE did not state is taken from the filing, and the record says so. Each
action is recorded once: a second review is refused, because a split applied twice doubles the
holding. A split or bonus changes the share count and the cost per share and keeps total cost, since
it is not a trade. Whole shares are credited; a fraction the issuer pays out in cash is not, and the
record says how much.

Exit status: 0 when shown or written, 2 when refused.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT / "src") not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT / "src"))

from quant_system.data.held_corporate_actions import (  # noqa: E402
    ShareAdjustment,
    adjust_holding,
    combine,
    load_nse_corporate_actions,
    parse_bonus,
    parse_face_value,
    published_ratio_agrees,
    structural_subjects_on,
)
from quant_system.execution.paper_portfolio import (  # noqa: E402
    PaperPortfolioError,
    acknowledge_corporate_action,
    adjust_for_corporate_action,
    load_portfolio,
    save_portfolio,
    state_hash_on_disk,
)

CORPORATE_ACTIONS_DIR = (
    PROJECT_ROOT / "data/evidence/market-cache/nifty500-refresh-20230828-20260827/corporate-actions"
)
FLAGSHIP_STATE = PROJECT_ROOT / "logs/paper_runs/portfolio_state.json"
#: The runner keeps this third copy beside the evidence store; an adjustment must reach it too, or a
#: restore from it would quietly undo the review.
FLAGSHIP_EVIDENCE_COPY = PROJECT_ROOT / "data/evidence/paper/portfolio_state.json"
XS_STATE = PROJECT_ROOT / "logs/xs_monthly_new/paper_watch/state.json"


class Refused(Exception):
    """A review that must not be recorded, and why."""


def _adjustment(args: argparse.Namespace) -> ShareAdjustment | None:
    parts: list[ShareAdjustment] = []
    try:
        if args.face_value:
            parts.append(parse_face_value(args.face_value))
        if args.bonus:
            parts.append(parse_bonus(args.bonus))
    except ValueError as error:
        raise Refused(str(error)) from error
    if parts and args.acknowledge is not None:
        raise Refused("give a ratio or an acknowledgement, not both")
    if not parts and args.acknowledge is None:
        raise Refused(
            'give the ratio from the filing (--bonus A:B, --face-value FROM:TO) or --acknowledge "why"'
        )
    return combine(parts) if parts else None


def _subject(records_dir: Path, symbol: str, ex_date: date) -> str:
    records, missing = load_nse_corporate_actions(records_dir, [symbol])
    if missing:
        raise Refused(f"no NSE corporate-action record for {symbol} in {records_dir}")
    subjects = structural_subjects_on(records[symbol], ex_date)
    if not subjects:
        raise Refused(
            f"NSE records no split, bonus, consolidation, demerger or rights issue for {symbol} on "
            f"{ex_date.isoformat()}; check the symbol and the ex-date"
        )
    return " | ".join(subject.strip() for subject in subjects)


def _ratio_note(adjustment: ShareAdjustment | None, subject: str) -> str:
    if adjustment is None:
        if "demerger" in subject.lower() or "scheme of arrangement" in subject.lower():
            return (
                "WARNING: acknowledging a demerger values the parent alone; the new company's "
                "shares are not counted, so the parent's fall will read as a loss"
            )
        return "acknowledged without an adjustment"
    verdict = published_ratio_agrees(adjustment, subject)
    if verdict is False:
        raise Refused(
            f"{adjustment.label} contradicts the NSE record ({subject}); check the filing again"
        )
    if verdict is None:
        return "ratio taken from the filing; the NSE record states none"
    return "ratio matches the NSE record"


def _review_flagship(
    args: argparse.Namespace,
    adjustment: ShareAdjustment | None,
    subject: str,
    reviewed_at: str,
) -> list[str]:
    state_path: Path = args.state or FLAGSHIP_STATE
    hash_at_load = state_hash_on_disk(state_path)
    try:
        state = load_portfolio(state_path)
        if state is None:
            raise Refused(f"no flagship portfolio at {state_path}")
        if adjustment is not None:
            updated, record = adjust_for_corporate_action(
                state,
                symbol=args.symbol,
                ex_date=args.ex_date,
                subject=subject,
                adjustment=adjustment,
                reviewed_at=reviewed_at,
            )
        else:
            updated, record = acknowledge_corporate_action(
                state,
                symbol=args.symbol,
                ex_date=args.ex_date,
                subject=subject,
                reason=args.acknowledge,
                reviewed_at=reviewed_at,
            )
    except (PaperPortfolioError, ValueError) as error:
        raise Refused(str(error)) from error
    lines = [
        f"flagship {record.symbol}: {record.resolution}",
        f"  shares {record.quantity_before} -> {record.quantity_after}; cost per share "
        f"{record.average_cost_before} -> {record.average_cost_after}",
    ]
    if args.apply:
        try:
            save_portfolio(state_path, updated, hash_at_load)
        except PaperPortfolioError as error:
            raise Refused(str(error)) from error
        save_portfolio(state_path.with_suffix(".backup.json"), updated)
        if args.evidence_copy is not None:
            evidence_copy: Path = args.evidence_copy
            evidence_copy.parent.mkdir(parents=True, exist_ok=True)
            save_portfolio(evidence_copy, updated)
        lines.append(f"written to {state_path} and its backups")
    return lines


def _review_xs(
    args: argparse.Namespace,
    adjustment: ShareAdjustment | None,
    subject: str,
    reviewed_at: str,
) -> list[str]:
    state_path: Path = args.state or XS_STATE
    try:
        state: dict[str, Any] = json.loads(state_path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as error:
        raise Refused(f"cannot read the XS state at {state_path}: {error}") from error
    ex_iso = args.ex_date.isoformat()
    legs = [
        leg
        for leg in state.get("open", [])
        if leg.get("symbol") == args.symbol and str(leg.get("entry_date", "")) < ex_iso
    ]
    if not legs:
        raise Refused(
            f"no open XS leg in {args.symbol} entered before {ex_iso}; a leg that has already "
            "matured into 'unresolved' cannot be revived here"
        )
    if any(
        review.get("ex_date") == ex_iso
        for leg in legs
        for review in leg.get("corporate_actions", [])
    ):
        raise Refused(
            f"{args.symbol}'s {ex_iso} corporate action has already been reviewed; applying it "
            "again would adjust the leg twice"
        )
    lines: list[str] = []
    for leg in legs:
        shares = int(leg["shares"])
        entry_open = Decimal(str(leg["entry_open"]))
        review: dict[str, Any] = {"ex_date": ex_iso, "subject": subject, "reviewed_at": reviewed_at}
        if adjustment is not None:
            try:
                adjusted = adjust_holding(shares, entry_open, adjustment)
            except ValueError as error:
                raise Refused(str(error)) from error
            review["resolution"] = f"adjusted: {adjustment.label}" + (
                f"; {float(adjusted.fractional_shares):.4f} fractional share(s) not credited"
                if adjusted.fractional_shares
                else ""
            )
            review.update(
                shares_before=shares,
                shares_after=adjusted.quantity,
                entry_open_before=str(entry_open),
                entry_open_after=str(adjusted.average_cost),
            )
            # The entry value is the leg's cost and stays; its price and share count move together.
            leg["shares"] = adjusted.quantity
            leg["entry_open"] = str(adjusted.average_cost)
        else:
            review["resolution"] = f"acknowledged: {args.acknowledge.strip()}"
            review.update(shares_before=shares, shares_after=shares)
        leg.setdefault("corporate_actions", []).append(review)
        lines.append(
            f"xs {args.symbol} (entered {leg['entry_date']}): {review['resolution']}; shares "
            f"{review['shares_before']} -> {review['shares_after']}"
        )
    if args.apply:
        staging = state_path.with_name(f"{state_path.name}.{os.getpid()}.review")
        staging.write_text(json.dumps(state, indent=1), encoding="utf-8")
        staging.replace(state_path)
        lines.append(f"written to {state_path}; the leg's marks refresh on the next watch run")
    return lines


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Review a corporate action on a paper holding, and record it in its book."
    )
    parser.add_argument("--book", choices=("flagship", "xs"), required=True)
    parser.add_argument("--symbol", required=True)
    parser.add_argument("--ex-date", required=True, type=date.fromisoformat, help="YYYY-MM-DD")
    parser.add_argument("--bonus", help="A:B -- A new shares for every B held, as NSE writes it")
    parser.add_argument("--face-value", help="FROM:TO face value, as NSE writes it: 10:2 splits")
    parser.add_argument("--acknowledge", help="record the action without adjusting, and say why")
    parser.add_argument("--apply", action="store_true", help="write; without it, only show")
    parser.add_argument("--state", type=Path, help="the book's state file (defaults per book)")
    parser.add_argument(
        "--evidence-copy",
        type=Path,
        default=FLAGSHIP_EVIDENCE_COPY,
        help="the flagship's third copy, kept in step with the other two",
    )
    parser.add_argument("--corporate-actions-dir", type=Path, default=CORPORATE_ACTIONS_DIR)
    parser.add_argument("--reviewed-at", help=argparse.SUPPRESS)
    args = parser.parse_args(argv)
    args.symbol = args.symbol.strip().upper()
    reviewed_at = args.reviewed_at or datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")

    try:
        adjustment = _adjustment(args)
        subject = _subject(args.corporate_actions_dir, args.symbol, args.ex_date)
        note = _ratio_note(adjustment, subject)
        review = _review_flagship if args.book == "flagship" else _review_xs
        lines = review(args, adjustment, subject, reviewed_at)
    except Refused as refusal:
        print(f"REFUSED: {refusal}")
        return 2
    print(f"NSE record, {args.symbol} {args.ex_date.isoformat()}: {subject}")
    print(note)
    for line in lines:
        print(line)
    if not args.apply:
        print("DRY RUN: nothing written. Add --apply to record it.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
