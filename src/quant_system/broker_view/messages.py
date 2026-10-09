"""Everything a person can read from the broker view, in plain language.

Each message says what happened and what to click. None names an error code, a setting, a file or a programming term,
because the people reading it are traders and investors, not developers.
"""

from __future__ import annotations

VIEW_ONLY = "View only. QuantOS can look at this account. It cannot buy, sell, move money or change anything."
SNAPSHOT_LABEL = "From your Upstox account. View only."
NOT_AVAILABLE = "The broker view is not available on this computer."
NOT_SET_UP = (
    "To see your Upstox account here, open Settings, then Broker view, and follow the three steps."
)
SAVE_KEYS_FIRST = (
    "Save your Upstox app key and secret first. Open Settings, then Accounts and keys."
)
NOT_CONNECTED = "Your Upstox account is not connected. Open Settings, then Broker view, and click Connect Upstox."
KEY_ENDED = (
    "Your Upstox sign-in has ended for today (Upstox ends it at 3:30 am). "
    "Open Settings, then Broker view, and click Connect Upstox."
)
KEY_REJECTED = (
    "Upstox did not accept the sign-in. "
    "Open Settings, then Broker view, and click Connect Upstox again."
)
STATIC_IP_REQUIRED = (
    "Upstox is asking for a registered internet address before it will show your holdings, "
    "so they could not be updated. Your last update is still shown."
)
PORT_BUSY = (
    "QuantOS could not get ready to receive the Upstox sign-in, because another program is using what "
    "it needs. Close other programs, then click Connect Upstox again."
)
STATE_MISMATCH = (
    "That sign-in did not start from this QuantOS window, so it was ignored. "
    "Click Connect Upstox to start again."
)
LOGIN_TIMED_OUT = (
    "The sign-in took longer than 5 minutes, so it was stopped. Click Connect Upstox to try again."
)
LOGIN_FAILED = "QuantOS could not finish connecting to Upstox. Click Connect Upstox to try again."
FUNDS_WINDOW = (
    "Upstox does not show your cash between midnight and 5:30 am. Your holdings are shown."
)
FUNDS_MISSING = "Your cash could not be read this time."
POSITIONS_MISSING = "Your open positions could not be read this time."
ASSISTANT_OFF = (
    "You have not let the assistant see your broker account. "
    "To allow it, open Settings, then Broker view."
)
UNREACHABLE = "Could not reach Upstox. Check your internet connection."
TOO_SLOW = "Upstox took too long to answer. Try again in a minute."
TOO_LARGE = (
    "Upstox sent more than QuantOS expected, so the answer was ignored. Try again in a minute."
)
UNREADABLE = "Upstox sent an answer QuantOS could not read. Try again in a minute."
BUSY = "Upstox is busy. Try again in a minute."
UNAVAILABLE = "Upstox could not show your account right now. Try again in a minute."


def partial(holdings: int, positions: int) -> str | None:
    """How many rows Upstox sent that could not be read, in words. None when every row was read."""
    parts = []
    if holdings:
        parts.append(f"{holdings} {'holding' if holdings == 1 else 'holdings'}")
    if positions:
        parts.append(f"{positions} open {'position' if positions == 1 else 'positions'}")
    if not parts:
        return None
    verb = "was" if holdings + positions == 1 else "were"
    return f"{' and '.join(parts)} could not be read and {verb} not shown."


def arriving(count: int) -> str:
    return (
        f"Bought recently, arriving in your demat ({count} {'share' if count == 1 else 'shares'})."
    )
