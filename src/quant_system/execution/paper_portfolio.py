"""A paper portfolio that survives between sessions.

Each paper session used to construct a fresh :class:`PaperPilotEngine` from ``initial_cash``, so
every weekday bought roughly 55 names at the open and closed them at 15:30. That is five independent
samples a week, and it pays a full round trip -- about 0.22% of capital under the NSE statutory
model -- **every single day, by construction**. A week of that shows a loss for reasons that have
nothing to do with the signal.

This module holds cash, positions and cost basis across sessions so the portfolio can do what the
model was actually measured doing.

## Rebalancing at the horizon, not daily

The out-of-sample screen entered at an open, held ``HOLD_SESSIONS = 10``, exited, and only then
re-ranked; the model's own card records ``label_horizon_sessions = 11``. Daily rebalancing is a
different strategy from the one that was measured, and a more expensive one. So a rebalance is due
only when the holding has aged past the model's declared horizon -- on every other session the
portfolio simply holds.

## Carrying positions into a fresh ledger

``DecimalLedger`` exposes no way to seed positions, and a SELL of a position it does not know about
is refused as a short. Positions are therefore replayed through the ledger's own ``process_fill``
as zero-fee buys at their carried cost. The ledger is funded with ``cash + holdings value`` so those
replayed buys debit exactly the holdings value back out, leaving cash at its true carried figure.
Nothing is invented: the replay states the position was acquired at that basis, which is true, and
it uses only the public API.

Carry-forward fills are tagged ``carry_`` in their ids so a session report can tell them apart from
trades that actually happened today.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

from quant_system.core.domain import Fill, Side
from quant_system.data.market_data_evidence import canonical_sha256

#: Schema identity for the persisted file, so a future shape change is detectable rather than
#: silently misread as the current one.
PORTFOLIO_SCHEMA_ID = "quantos.paper_portfolio"
PORTFOLIO_SCHEMA_VERSION = 1


class PaperPortfolioError(RuntimeError):
    """Raised when persisted portfolio state cannot be trusted."""


@dataclass(frozen=True, slots=True)
class PortfolioHolding:
    """One carried position, with the basis it was acquired at."""

    symbol: str
    quantity: int
    average_cost: Decimal
    opened_on: date

    def __post_init__(self) -> None:
        if self.quantity <= 0:
            raise PaperPortfolioError(
                f"{self.symbol}: a carried holding must be positive, got {self.quantity}; this "
                "portfolio is long-only"
            )
        if self.average_cost <= 0:
            raise PaperPortfolioError(f"{self.symbol}: average cost must be positive")

    @property
    def cost_basis(self) -> Decimal:
        return (self.average_cost * self.quantity).quantize(Decimal("0.01"))


@dataclass
class PaperPortfolioState:
    """Cash, positions and running totals carried between sessions."""

    cash: Decimal
    holdings: dict[str, PortfolioHolding] = field(default_factory=dict)
    realized_pnl: Decimal = Decimal("0.00")
    total_fees: Decimal = Decimal("0.00")
    last_rebalance_on: date | None = None
    sessions_completed: int = 0
    sessions_since_rebalance: int = 0

    @property
    def holdings_value_at_cost(self) -> Decimal:
        return sum(
            (holding.cost_basis for holding in self.holdings.values()), Decimal("0.00")
        ).quantize(Decimal("0.01"))

    def ledger_funding(self) -> Decimal:
        """Cash the engine's ledger must start with so the carry-forward replay nets out.

        ``process_fill`` refuses a fill that would drive cash below zero, so the ledger has to be
        able to "pay" for the positions being replayed. Funding it with cash plus the holdings'
        cost basis means the replay debits exactly that basis back out.
        """
        return (self.cash + self.holdings_value_at_cost).quantize(Decimal("0.01"))

    def carry_forward_fills(self, at: datetime) -> list[Fill]:
        """Buys that reconstruct the carried positions in a fresh ledger, at zero fee.

        Zero fee because the cost was already paid, and charged again, on the session that opened
        the position. Charging it twice would make the portfolio look worse than it is for a reason
        that never happened.
        """
        return [
            Fill(
                fill_id=f"carry_{holding.symbol}_{holding.opened_on.isoformat()}",
                order_id=f"carry_order_{holding.symbol}",
                symbol=holding.symbol,
                side=Side.BUY,
                quantity=holding.quantity,
                price=holding.average_cost,
                fee=Decimal("0.00"),
                timestamp=at,
            )
            for holding in sorted(self.holdings.values(), key=lambda h: h.symbol)
        ]

    def rebalance_due(self, horizon_sessions: int) -> bool:
        """Whether today should re-rank, or simply hold.

        An empty portfolio always rebalances -- otherwise a fresh install would hold nothing
        forever. Beyond that, the holding must have aged past the model's declared horizon.
        """
        if not self.holdings:
            return True
        return self.sessions_since_rebalance >= horizon_sessions

    def to_payload(self) -> dict[str, Any]:
        return {
            "cash": str(self.cash),
            "holdings": [
                {
                    "symbol": h.symbol,
                    "quantity": h.quantity,
                    "average_cost": str(h.average_cost),
                    "opened_on": h.opened_on.isoformat(),
                }
                for h in sorted(self.holdings.values(), key=lambda h: h.symbol)
            ],
            "last_rebalance_on": (
                self.last_rebalance_on.isoformat() if self.last_rebalance_on else None
            ),
            "realized_pnl": str(self.realized_pnl),
            "schema_id": PORTFOLIO_SCHEMA_ID,
            "schema_version": PORTFOLIO_SCHEMA_VERSION,
            "sessions_completed": self.sessions_completed,
            "sessions_since_rebalance": self.sessions_since_rebalance,
            "total_fees": str(self.total_fees),
        }


def save_portfolio(path: Path, state: PaperPortfolioState) -> None:
    """Write state with a content hash, atomically.

    The hash exists so a truncated or hand-edited file is refused on the next session rather than
    resumed from. An unattended weekday schedule has nobody to notice a corrupt resume.
    """
    payload = state.to_payload()
    document = {"payload": payload, "state_hash": canonical_sha256(payload)}
    path.parent.mkdir(parents=True, exist_ok=True)
    staging = path.with_suffix(path.suffix + ".staging")
    staging.write_text(json.dumps(document, indent=2, sort_keys=True), encoding="utf-8")
    staging.replace(path)


def load_portfolio(path: Path) -> PaperPortfolioState | None:
    """Read persisted state, or None when there is none yet. Corruption raises rather than resets.

    Resetting to a fresh portfolio on a bad read would silently discard a running position and
    report a clean session, which is the failure this whole module exists to avoid.
    """
    if not path.is_file():
        return None
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as error:
        raise PaperPortfolioError(
            f"portfolio state at {path} is not valid JSON: {error}"
        ) from error

    payload = document.get("payload")
    if not isinstance(payload, dict):
        raise PaperPortfolioError(f"portfolio state at {path} has no payload")
    if document.get("state_hash") != canonical_sha256(payload):
        raise PaperPortfolioError(
            f"portfolio state at {path} does not match its own hash; refusing to resume from it"
        )
    if (payload.get("schema_id"), payload.get("schema_version")) != (
        PORTFOLIO_SCHEMA_ID,
        PORTFOLIO_SCHEMA_VERSION,
    ):
        raise PaperPortfolioError(
            f"portfolio state at {path} declares "
            f"{payload.get('schema_id')} v{payload.get('schema_version')}, expected "
            f"{PORTFOLIO_SCHEMA_ID} v{PORTFOLIO_SCHEMA_VERSION}"
        )

    holdings = {
        entry["symbol"]: PortfolioHolding(
            symbol=entry["symbol"],
            quantity=int(entry["quantity"]),
            average_cost=Decimal(entry["average_cost"]),
            opened_on=date.fromisoformat(entry["opened_on"]),
        )
        for entry in payload.get("holdings", [])
    }
    last = payload.get("last_rebalance_on")
    return PaperPortfolioState(
        cash=Decimal(payload["cash"]),
        holdings=holdings,
        realized_pnl=Decimal(payload["realized_pnl"]),
        total_fees=Decimal(payload["total_fees"]),
        last_rebalance_on=date.fromisoformat(last) if last else None,
        sessions_completed=int(payload["sessions_completed"]),
        sessions_since_rebalance=int(payload["sessions_since_rebalance"]),
    )


def state_from_ledger(
    previous: PaperPortfolioState,
    cash: Decimal,
    positions: dict[str, tuple[int, Decimal]],
    *,
    session_date: date,
    realized_pnl: Decimal,
    fees_paid: Decimal,
    rebalanced: bool,
) -> PaperPortfolioState:
    """The state to persist after a session, from the ledger's closing view.

    ``positions`` maps symbol to (quantity, average cost). A name already held keeps its original
    ``opened_on`` so its age -- and therefore when it next becomes eligible to rebalance -- is not
    reset by simply surviving a session.
    """
    holdings = {
        symbol: PortfolioHolding(
            symbol=symbol,
            quantity=quantity,
            average_cost=average_cost,
            opened_on=(
                previous.holdings[symbol].opened_on if symbol in previous.holdings else session_date
            ),
        )
        for symbol, (quantity, average_cost) in sorted(positions.items())
        if quantity > 0
    }
    return PaperPortfolioState(
        cash=cash.quantize(Decimal("0.01")),
        holdings=holdings,
        realized_pnl=realized_pnl.quantize(Decimal("0.01")),
        total_fees=(previous.total_fees + fees_paid).quantize(Decimal("0.01")),
        last_rebalance_on=session_date if rebalanced else previous.last_rebalance_on,
        sessions_completed=previous.sessions_completed + 1,
        sessions_since_rebalance=0 if rebalanced else previous.sessions_since_rebalance + 1,
    )
