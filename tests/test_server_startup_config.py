"""Tests that server startup config disables WebSockets to avoid incomplete namespace import crashes."""

from __future__ import annotations

import sys
import types
from unittest.mock import patch

from quantos_studio import _build_server


def test_build_server_explicitly_disables_websockets() -> None:
    """QuantOS serves only REST HTTP endpoints; ws must be set to 'none'."""
    server = _build_server(8080)
    assert server.config.ws == "none"
    server.config.load()
    assert server.config.ws_protocol_class is None


def test_server_load_resilient_to_incomplete_websockets_namespace() -> None:
    """Simulate a broken namespace package for websockets (like an orphaned speedups C-ext directory).

    Even if 'websockets' is in sys.modules with no __version__ or submodules,
    Config.load() with ws='none' must succeed without raising ImportError.
    """
    broken_ws = types.ModuleType("websockets")
    # A namespace package has no __version__ attribute
    assert not hasattr(broken_ws, "__version__")

    with patch.dict(sys.modules, {"websockets": broken_ws}):
        server = _build_server(8081)
        # load() should not attempt to import from websockets or fail
        server.config.load()
        assert server.config.ws_protocol_class is None
