"""The view-only promise, enforced by reading the source: a closed list of broker addresses and no way to trade.

These tests parse the package's code. They do not run it. If someone adds a broker address, a new way to open an
internet connection, or a write, a test here fails and says where.
"""

from __future__ import annotations

import ast
from pathlib import Path

from quant_system.broker_view import endpoints
from quant_system.broker_view.model import CONCENTRATION_LIMIT
from quant_system.server.v2.portfolio import CONCENTRATION_LIMIT as PORTFOLIO_LIMIT

PACKAGE = Path(endpoints.__file__).parent
SOURCES = sorted(PACKAGE.glob("*.py"))
FORBIDDEN_IN_AN_ADDRESS = ("/order", "/gtt", "convert", "payment", "authorise", "/mf", "/trade")
FORBIDDEN_MODULES = {"requests", "httpx", "aiohttp", "http.client", "socket", "ftplib", "smtplib"}


def _tree(path: Path) -> ast.AST:
    return ast.parse(path.read_text(encoding="utf-8"))


def _docstring_ids(tree: ast.AST) -> set[int]:
    ids: set[int] = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
            body = node.body
            if body and isinstance(body[0], ast.Expr) and isinstance(body[0].value, ast.Constant):
                ids.add(id(body[0].value))
    return ids


def _constants(path: Path) -> list[str]:
    tree = _tree(path)
    skip = _docstring_ids(tree)
    return [
        node.value
        for node in ast.walk(tree)
        if isinstance(node, ast.Constant) and isinstance(node.value, str) and id(node) not in skip
    ]


def _imports(path: Path) -> set[str]:
    names: set[str] = set()
    for node in ast.walk(_tree(path)):
        if isinstance(node, ast.Import):
            names.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            names.add(node.module)
            names.update(f"{node.module}.{alias.name}" for alias in node.names)
    return names


def test_the_list_of_allowed_calls_is_exactly_these_five() -> None:
    assert endpoints.ALLOWED_CALLS == {
        ("POST", endpoints.UPSTOX_TOKEN_URL),
        ("DELETE", endpoints.UPSTOX_LOGOUT_URL),
        ("GET", endpoints.UPSTOX_HOLDINGS_URL),
        ("GET", endpoints.UPSTOX_POSITIONS_URL),
        ("GET", endpoints.UPSTOX_FUNDS_URL),
    }


def test_no_allowed_address_is_an_order_a_conversion_a_payment_or_a_trade_book() -> None:
    for _, address in endpoints.ALLOWED_CALLS:
        assert not [word for word in FORBIDDEN_IN_AN_ADDRESS if word in address.lower()], address


def test_the_only_non_get_calls_go_to_the_sign_in_and_sign_out_addresses() -> None:
    others = {call for call in endpoints.ALLOWED_CALLS if call[0] != "GET"}
    assert others == {
        ("POST", endpoints.UPSTOX_TOKEN_URL),
        ("DELETE", endpoints.UPSTOX_LOGOUT_URL),
    }


def test_every_address_in_the_package_is_one_of_the_constants_in_endpoints() -> None:
    known = {
        value
        for name, value in vars(endpoints).items()
        if name.isupper() and isinstance(value, str) and "://" in value
    }
    assert len(known) >= 7
    stray = [
        f"{path.name}: {text!r}"
        for path in SOURCES
        if path.name != "endpoints.py"
        for text in _constants(path)
        if "://" in text
    ]
    assert stray == []


def test_no_address_is_built_by_putting_pieces_together_with_a_scheme() -> None:
    offenders = []
    for path in SOURCES:
        for node in ast.walk(_tree(path)):
            if isinstance(node, ast.JoinedStr) and any(
                isinstance(part, ast.Constant) and "://" in str(part.value) for part in node.values
            ):
                offenders.append(f"{path.name}:{node.lineno}")
    assert offenders == []


def test_only_the_session_module_can_open_a_connection_of_its_own() -> None:
    importers = [path.name for path in SOURCES if "urllib.request" in _imports(path)]
    assert importers == ["session_http.py"]


def test_the_session_module_makes_exactly_two_requests_a_post_to_sign_in_and_a_delete_to_sign_out() -> (
    None
):
    calls = []
    for node in ast.walk(_tree(PACKAGE / "session_http.py")):
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr == "Request"
        ):
            method = next(k.value for k in node.keywords if k.arg == "method")
            assert isinstance(method, ast.Constant) and isinstance(node.args[0], ast.Name)
            calls.append((method.value, node.args[0].id))
    assert sorted(calls) == [("DELETE", "UPSTOX_LOGOUT_URL"), ("POST", "UPSTOX_TOKEN_URL")]


def test_nothing_in_the_package_imports_another_way_to_reach_the_internet() -> None:
    offenders = [
        f"{path.name}: {name}"
        for path in SOURCES
        for name in _imports(path)
        if name in FORBIDDEN_MODULES or name.split(".")[0] in {"requests", "httpx", "aiohttp"}
    ]
    # the loopback listener uses sockets only to listen on this computer, and is the one module allowed to
    assert [o for o in offenders if not o.startswith("loopback.py")] == []


def test_the_package_does_not_import_the_server_so_it_cannot_reach_its_routes_or_settings() -> None:
    offenders = [
        f"{path.name}: {name}"
        for path in SOURCES
        for name in _imports(path)
        if name.startswith("quant_system.server") or name.startswith("quant_system.execution")
    ]
    assert offenders == []


def test_nothing_in_the_package_writes_to_the_process_environment() -> None:
    for path in SOURCES:
        source = path.read_text(encoding="utf-8")
        assert "os.environ" not in source and "putenv" not in source, path.name


def test_the_concentration_rule_matches_the_hand_entered_portfolio() -> None:
    assert float(CONCENTRATION_LIMIT) == PORTFOLIO_LIMIT


def test_the_callback_address_is_built_from_its_parts() -> None:
    assert endpoints.CALLBACK_ADDRESS == (
        f"http://{endpoints.CALLBACK_HOST}:{endpoints.CALLBACK_PORT}{endpoints.CALLBACK_PATH}"
    )
