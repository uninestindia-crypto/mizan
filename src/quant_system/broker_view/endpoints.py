"""The only place a broker address exists in QuantOS's view-only connection.

Everything the connection may ever send is listed in ``ALLOWED_CALLS``: three reads (holdings, open positions, cash)
and the two calls that sign in and sign out. There is no order, standing-order, conversion, payment, pledge, mutual
fund or order-book address anywhere in this package, and a test reads the source to keep it that way.

The addresses are plain string literals on purpose: no address is ever built from other text.
"""

from __future__ import annotations

UPSTOX_AUTHORIZE_URL = "https://api.upstox.com/v2/login/authorization/dialog"
UPSTOX_TOKEN_URL = "https://api.upstox.com/v2/login/authorization/token"
UPSTOX_LOGOUT_URL = "https://api.upstox.com/v2/logout"
UPSTOX_HOLDINGS_URL = "https://api.upstox.com/v2/portfolio/long-term-holdings"
UPSTOX_POSITIONS_URL = "https://api.upstox.com/v2/portfolio/short-term-positions"
UPSTOX_FUNDS_URL = "https://api.upstox.com/v2/user/get-funds-and-margin"

# Where Upstox sends the person's browser after they sign in. The port is fixed because Upstox compares the return
# address with the one saved in the person's app, character for character. The app's own port is chosen at start-up.
CALLBACK_HOST = "127.0.0.1"
CALLBACK_PORT = 47610
CALLBACK_PATH = "/upstox/callback"
CALLBACK_ADDRESS = "http://127.0.0.1:47610/upstox/callback"

FUNDS_QUERY = (("segment", "SEC"),)

ALLOWED_CALLS: frozenset[tuple[str, str]] = frozenset(
    {
        ("POST", UPSTOX_TOKEN_URL),
        ("DELETE", UPSTOX_LOGOUT_URL),
        ("GET", UPSTOX_HOLDINGS_URL),
        ("GET", UPSTOX_POSITIONS_URL),
        ("GET", UPSTOX_FUNDS_URL),
    }
)
