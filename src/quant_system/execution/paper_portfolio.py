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
re-ranked. The model's own card records ``label_horizon_sessions = 11`` -- **the same length in a
different convention**, because a label horizon counts decision -> entry -> exit
(``modeling/labels.py:40``). Those two numbers sat side by side in this docstring for a while
without anyone noticing they were the same thing, and the larger one was used, which is half of why
the executed hold was 12 sessions rather than 10. ``rebalance_due`` now takes the card's convention
and converts, so the caller cannot pick the wrong one.

Daily rebalancing is a different strategy from the one that was measured, and a more expensive one.
On every session that is not a rebalance the portfolio simply holds.

## Carrying positions into a fresh ledger

``DecimalLedger`` exposes no way to seed positions, and a SELL of a position it does not know about
is refused as a short. Positions are therefore replayed through the ledger's own ``process_fill``
as buys at their carried cost **and their carried entry fee**. The ledger is funded with
``cash + holdings value + carried entry fees`` so those replayed buys debit exactly that back out,
leaving cash at its true carried figure. Nothing is invented: the replay states the position was
acquired at that basis and cost that fee, both of which are true, and it uses only the public API.

The fee matters because the ledger attributes a lot's entry cost when the lot *closes*. Replaying at
zero fee kept cash correct and made every cross-session round trip report a gain inflated by exactly
the entry-side statutory cost -- silent, systematic, and flattering to the strategy.

Carry-forward fills are tagged ``carry_`` in their ids so a session report can tell them apart from
trades that actually happened today.
"""

from __future__ import annotations

import json
import os
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

#: Version 2 added ``entry_fee`` per holding and renamed ``sessions_since_rebalance`` to
#: ``sessions_held``. Version 3 adds the risk halt, so a tripped kill switch survives the session
#: boundary. Version 4 adds the daily drawdown anchor, so restarting the process during a session
#: does not re-baseline it.
#:
#: Versions 2 and 3 landed with "no migration is written: no state file has ever been produced".
#: That was true then and had **stopped being true** by version 4: the session of 2026-08-31 wrote a
#: real v3 file holding 97 positions, and the next morning's run refused it and exited 2 before
#: placing an order. `_migrated` upgrades a v3 payload; the claim that no file exists is not one to
#: carry forward without rechecking it.
PORTFOLIO_SCHEMA_VERSION = 4


class _Unchecked:
    """Sentinel type for "no compare-and-swap requested".

    `None` cannot serve: it is the real value for "there was no state file when this session
    loaded", and a caller passing it means exactly that. A distinct type keeps the signature
    honest under strict typing rather than widening it to `object`.
    """


#: The sentinel itself.
UNCHECKED = _Unchecked()


class PaperPortfolioError(RuntimeError):
    """Raised when persisted portfolio state cannot be trusted."""


@dataclass(frozen=True, slots=True)
class PortfolioHolding:
    """One carried position, with the basis and the entry cost it was acquired at.

    ``entry_fee`` is the statutory cost still attributable to the open lots. It is carried because
    ``DecimalLedger`` subtracts a lot's ``entry_fee`` when that lot closes
    (``core/ledger.py:326``), so a replay that dropped it would report the eventual sale as more
    profitable than it was -- by exactly the entry-side cost, on every position held across a
    session boundary.
    """

    symbol: str
    quantity: int
    average_cost: Decimal
    opened_on: date
    entry_fee: Decimal = Decimal("0.00")

    def __post_init__(self) -> None:
        if self.quantity <= 0:
            raise PaperPortfolioError(
                f"{self.symbol}: a carried holding must be positive, got {self.quantity}; this "
                "portfolio is long-only"
            )
        if self.average_cost <= 0:
            raise PaperPortfolioError(f"{self.symbol}: average cost must be positive")
        if self.entry_fee < 0:
            raise PaperPortfolioError(f"{self.symbol}: entry fee cannot be negative")

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

    #: Highest total equity this portfolio has ever reached, carried so the total-drawdown kill
    #: switch measures from the real peak.
    #:
    #: `PreTradeRiskGovernor` keeps an all-time peak, but a fresh governor is constructed every
    #: session and seeded with zero, so the "peak" was whatever today happened to open at. A
    #: portfolio that fell 20% over three sessions could not trip a 12% total-drawdown limit,
    #: because each session's decline was measured against that session's own high. Making the
    #: portfolio persistent is what made the switch inert; carrying the peak is what restores it.
    peak_equity: Decimal = Decimal("0.00")

    #: Whether the risk governor's kill switch has fired and not been cleared by a human.
    #:
    #: A fresh `PreTradeRiskGovernor` is constructed every session with `_is_killed = False`, and
    #: nothing restored it, so a total-drawdown breach halted trading for the remainder of *one*
    #: session and was forgotten the next morning. In the same session the halt also refused the
    #: exits -- the kill fires on the first order, and the first order is a SELL -- so the losing
    #: book was retained while the breach that should have stopped it was erased.
    #:
    #: Deliberately not cleared by any automatic condition. A kill switch that resets itself is not
    #: a kill switch, and one that liquidates on its own would implement a rule nobody measured.
    risk_halted: bool = False
    halted_on: date | None = None
    halt_reason: str = ""

    #: The daily-drawdown baseline for `daily_anchor_on`, and the date it belongs to.
    #:
    #: `PreTradeRiskGovernor` is rebuilt per process, so the anchor was rebuilt too: every restart
    #: re-baselined the daily rule to whatever equity was current. Measured across four starts in
    #: one day -- 1,000,000, 965,000, 931,000, 898,000 -- a 10.2% decline was seen as three separate
    #: sub-4% ones and never tripped a 4% limit. Three sessions were abandoned and restarted on
    #: 2026-08-31 alone, so this is a live path rather than a hypothetical one.
    daily_anchor_on: date | None = None
    daily_anchor_equity: Decimal = Decimal("0.00")

    #: Sessions the current holding will have been held for as of the *next* session's check.
    #:
    #: Set to 1 by the rebalance session itself, because a position entered on that session is one
    #: session old when the next session opens. The field this replaces counted from 0 and so
    #: reported the age minus one at every check, which was one of two compounding off-by-ones that
    #: made the executed hold 12 sessions against a measured 10.
    sessions_held: int = 0

    @property
    def holdings_value_at_cost(self) -> Decimal:
        return sum(
            (holding.cost_basis for holding in self.holdings.values()), Decimal("0.00")
        ).quantize(Decimal("0.01"))

    @property
    def carried_entry_fees(self) -> Decimal:
        return sum(
            (holding.entry_fee for holding in self.holdings.values()), Decimal("0.00")
        ).quantize(Decimal("0.01"))

    def ledger_funding(self) -> Decimal:
        """Cash the engine's ledger must start with so the carry-forward replay nets out.

        ``process_fill`` refuses a fill that would drive cash below zero, so the ledger has to be
        able to "pay" for the positions being replayed. A BUY debits ``gross_value + fee``
        (``core/domain.py:209``), so funding is cash plus the holdings' cost basis **plus their
        carried entry fees** -- the replay then debits exactly that back out and cash lands on its
        true carried figure.
        """
        return (self.cash + self.holdings_value_at_cost + self.carried_entry_fees).quantize(
            Decimal("0.01")
        )

    def carry_forward_fills(self, at: datetime) -> list[Fill]:
        """Buys that reconstruct the carried positions in a fresh ledger, at their true entry cost.

        These fills carry the original ``entry_fee`` rather than zero. An earlier version used zero
        on the reasoning that the cost had already been paid and charging it again "would make the
        portfolio look worse than it is for a reason that never happened".

        That reasoning is true of **cash** and false of **realized P&L**, and the code did not
        distinguish them. The ledger attributes a lot's entry fee at the moment the lot *closes*, so
        a zero-fee replay did not avoid double-charging -- it dropped the charge entirely, and every
        cross-session round trip reported a gain inflated by exactly the entry-side statutory cost.
        Cash stayed correct throughout, which is what made it silent.

        The fee is neutral to cash here because ``ledger_funding`` includes it.
        """
        return [
            Fill(
                fill_id=f"carry_{holding.symbol}_{holding.opened_on.isoformat()}",
                order_id=f"carry_order_{holding.symbol}",
                symbol=holding.symbol,
                side=Side.BUY,
                quantity=holding.quantity,
                price=holding.average_cost,
                fee=holding.entry_fee,
                timestamp=at,
            )
            for holding in sorted(self.holdings.values(), key=lambda h: h.symbol)
        ]

    def rebalance_due(self, horizon_sessions: int) -> bool:
        """Whether today should re-rank, or simply hold.

        ``horizon_sessions`` is the model card's ``label_horizon_sessions``, which counts
        **decision -> entry -> exit** (``modeling/labels.py:40``: "the default 2 holds for one
        session"). So a declared horizon of 11 is a *held* length of 10, which is exactly what the
        out-of-sample screen measured -- it entered at ``opens[i + 1]`` and exited at
        ``opens[i + 1 + 10]``.

        Converting here rather than at the call site is deliberate. The caller passed the card value
        straight through, and the two conventions sat side by side in this module's own docstring
        without anyone noticing they were the same number written two ways.

        An empty portfolio always rebalances -- otherwise a fresh install would hold nothing
        forever.
        """
        if horizon_sessions < 2:
            raise PaperPortfolioError(
                f"a label horizon of {horizon_sessions} holds for no sessions at all; the shortest "
                "meaningful horizon is 2, which holds for one session"
            )
        if not self.holdings:
            return True
        return self.sessions_held >= horizon_sessions - 1

    def to_payload(self) -> dict[str, Any]:
        return {
            "cash": str(self.cash),
            "holdings": [
                {
                    "symbol": h.symbol,
                    "quantity": h.quantity,
                    "average_cost": str(h.average_cost),
                    "entry_fee": str(h.entry_fee),
                    "opened_on": h.opened_on.isoformat(),
                }
                for h in sorted(self.holdings.values(), key=lambda h: h.symbol)
            ],
            "peak_equity": str(self.peak_equity),
            "daily_anchor_on": self.daily_anchor_on.isoformat() if self.daily_anchor_on else None,
            "daily_anchor_equity": str(self.daily_anchor_equity),
            "risk_halted": self.risk_halted,
            "halted_on": self.halted_on.isoformat() if self.halted_on else None,
            "halt_reason": self.halt_reason,
            "last_rebalance_on": (
                self.last_rebalance_on.isoformat() if self.last_rebalance_on else None
            ),
            "realized_pnl": str(self.realized_pnl),
            "schema_id": PORTFOLIO_SCHEMA_ID,
            "schema_version": PORTFOLIO_SCHEMA_VERSION,
            "sessions_completed": self.sessions_completed,
            "sessions_held": self.sessions_held,
            "total_fees": str(self.total_fees),
        }


def _migrated(payload: dict[str, Any], path: Path) -> dict[str, Any]:
    """Bring an older payload up to the current schema, or refuse.

    Version 4 was added on the reasoning that "no state file has ever been produced", which was true
    when versions 2 and 3 landed and had **stopped being true** by the time 4 did: the session of
    2026-08-31 wrote a real v3 file holding 97 positions. The next morning's run refused it and
    exited 2 before placing an order. Fail-closed was the right instinct and the wrong outcome,
    because the alternative to migrating was discarding a real book.

    Migration runs after the hash check, so integrity is still verified against exactly what was
    written; only then are the new fields defaulted.
    """
    version = payload.get("schema_version")
    if payload.get("schema_id") != PORTFOLIO_SCHEMA_ID:
        raise PaperPortfolioError(
            f"portfolio state at {path} declares schema {payload.get('schema_id')!r}, "
            f"expected {PORTFOLIO_SCHEMA_ID!r}"
        )
    if version == PORTFOLIO_SCHEMA_VERSION:
        return payload
    if version == 3:
        # v4 added the daily drawdown anchor. A v3 file has none, and no anchor is the correct
        # starting state: the session takes a fresh one from its first live mark.
        upgraded = dict(payload)
        upgraded["daily_anchor_on"] = None
        upgraded["daily_anchor_equity"] = "0.00"
        upgraded["schema_version"] = PORTFOLIO_SCHEMA_VERSION
        return upgraded
    raise PaperPortfolioError(
        f"portfolio state at {path} declares "
        f"{payload.get('schema_id')} v{version}, expected "
        f"{PORTFOLIO_SCHEMA_ID} v{PORTFOLIO_SCHEMA_VERSION}, and no migration exists from v{version}"
    )


def state_hash_on_disk(path: Path) -> str | None:
    """The hash currently recorded at `path`, or None when there is no file.

    Read without validating the rest of the document: this is used to detect that *something else*
    wrote since we loaded, and a file we are about to refuse to overwrite does not need to parse.
    """
    if not path.is_file():
        return None
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return "<unreadable>"
    recorded = document.get("state_hash")
    return str(recorded) if recorded is not None else "<absent>"


def save_portfolio(
    path: Path,
    state: PaperPortfolioState,
    expected_prior_hash: str | None | _Unchecked = UNCHECKED,
) -> None:
    """Write state with a content hash, atomically, refusing to clobber a concurrent write.

    The content hash exists so a truncated or hand-edited file is refused on the next session
    rather than resumed from. An unattended weekday schedule has nobody to notice a corrupt resume.

    ``expected_prior_hash`` is the compare-and-swap. Pass what
    :func:`state_hash_on_disk` returned when the session loaded, and the write is refused if
    anything has changed the file since. Two sessions ran concurrently and the second to finish
    silently discarded the first's entire trading day -- 16 fills, `sessions_completed` 10 to 11,
    one session's fees -- with both reports on disk and no error anywhere. There is no lock: this
    does not prevent the overlap, it prevents the loss, which is the part that cannot be recovered.

    The default is deliberately a sentinel rather than ``None``: ``None`` is the legitimate value
    for "there was no file when I loaded", and a caller that passes it means it. Omitting the
    argument entirely skips the check, which keeps every existing caller working.
    """
    if not isinstance(expected_prior_hash, _Unchecked):
        current = state_hash_on_disk(path)
        if current != expected_prior_hash:
            raise PaperPortfolioError(
                f"portfolio state at {path} changed since this session loaded it "
                f"(expected {expected_prior_hash!r}, found {current!r}). Another session has "
                "written here; refusing to overwrite it and lose that trading day."
            )
    payload = state.to_payload()
    document = {"payload": payload, "state_hash": canonical_sha256(payload)}
    path.parent.mkdir(parents=True, exist_ok=True)
    # A per-process staging name, so two writers cannot corrupt each other's temporary file.
    staging = path.with_suffix(f"{path.suffix}.{os.getpid()}.staging")
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
    payload = _migrated(payload, path)

    holdings = {
        entry["symbol"]: PortfolioHolding(
            symbol=entry["symbol"],
            quantity=int(entry["quantity"]),
            average_cost=Decimal(entry["average_cost"]),
            opened_on=date.fromisoformat(entry["opened_on"]),
            entry_fee=Decimal(entry["entry_fee"]),
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
        sessions_held=int(payload["sessions_held"]),
        peak_equity=Decimal(payload["peak_equity"]),
        daily_anchor_on=(
            date.fromisoformat(payload["daily_anchor_on"])
            if payload.get("daily_anchor_on")
            else None
        ),
        daily_anchor_equity=Decimal(payload["daily_anchor_equity"]),
        risk_halted=bool(payload["risk_halted"]),
        halted_on=(date.fromisoformat(payload["halted_on"]) if payload.get("halted_on") else None),
        halt_reason=str(payload.get("halt_reason", "")),
    )


def state_from_ledger(
    previous: PaperPortfolioState,
    cash: Decimal,
    positions: dict[str, tuple[int, Decimal]],
    *,
    session_date: date,
    session_realized_pnl: Decimal,
    fees_paid: Decimal,
    rebalanced: bool,
    open_entry_fees: dict[str, Decimal] | None = None,
    session_peak_equity: Decimal | None = None,
    risk_halted: bool = False,
    halt_reason: str = "",
    daily_anchor_on: date | None = None,
    daily_anchor_equity: Decimal | None = None,
) -> PaperPortfolioState:
    """The state to persist after a session, from the ledger's closing view.

    ``positions`` maps symbol to (quantity, average cost). A name already held keeps its original
    ``opened_on`` so its age -- and therefore when it next becomes eligible to rebalance -- is not
    reset by simply surviving a session.

    ``session_realized_pnl`` is **this session's** figure, from a ledger that starts empty each
    session, and it is *added* to the carried total. The parameter was previously named
    ``realized_pnl`` and was written straight into the persisted field, discarding everything
    earlier: one idle session was enough to reduce a real cumulative P&L to ``0.00`` inside a
    hash-protected, schema-versioned file. The line beside it accumulated fees correctly, which is
    what made the asymmetry easy to miss.

    ``open_entry_fees`` maps symbol to the statutory entry cost still attributable to its open lots
    (``DecimalLedger.lots``). Omitting it carries zero, which understates the cost of any position
    that survives into the next session.
    """
    fees_by_symbol = open_entry_fees or {}
    holdings = {
        symbol: PortfolioHolding(
            symbol=symbol,
            quantity=quantity,
            average_cost=average_cost,
            opened_on=(
                previous.holdings[symbol].opened_on if symbol in previous.holdings else session_date
            ),
            entry_fee=fees_by_symbol.get(symbol, Decimal("0.00")).quantize(Decimal("0.01")),
        )
        for symbol, (quantity, average_cost) in sorted(positions.items())
        if quantity > 0
    }
    return PaperPortfolioState(
        cash=cash.quantize(Decimal("0.01")),
        holdings=holdings,
        realized_pnl=(previous.realized_pnl + session_realized_pnl).quantize(Decimal("0.01")),
        total_fees=(previous.total_fees + fees_paid).quantize(Decimal("0.01")),
        last_rebalance_on=session_date if rebalanced else previous.last_rebalance_on,
        sessions_completed=previous.sessions_completed + 1,
        # Monotonic by construction: a peak that could fall would let a drawdown be forgiven by the
        # decline that caused it.
        peak_equity=max(previous.peak_equity, session_peak_equity or Decimal("0.00")).quantize(
            Decimal("0.01")
        ),
        # Carried so a restart within the same session reuses the morning's baseline rather than
        # taking a fresh one from wherever the book has since fallen to.
        daily_anchor_on=daily_anchor_on or previous.daily_anchor_on,
        daily_anchor_equity=(
            daily_anchor_equity if daily_anchor_equity is not None else previous.daily_anchor_equity
        ),
        # Sticky. Once halted, only a human clears it; a later quiet session must not lift it.
        risk_halted=previous.risk_halted or risk_halted,
        halted_on=previous.halted_on or (session_date if risk_halted else None),
        halt_reason=previous.halt_reason or (halt_reason if risk_halted else ""),
        # 1, not 0, on the rebalance session: a position entered today is one session old when the
        # next session opens, and the check happens at the open.
        sessions_held=1 if rebalanced else previous.sessions_held + 1,
    )
