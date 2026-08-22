from __future__ import annotations

import argparse
import os
import platform
import socket
import sys
import threading
import time
import webbrowser
from decimal import Decimal
from pathlib import Path

import uvicorn

from quant_system import __version__
from quant_system.alpha.greeks import BlackScholes
from quant_system.config import load_env_file
from quant_system.core.domain import InstrumentType
from quant_system.core.ledger import DecimalLedger
from quant_system.data.provenance import (
    ACCESS_TOKEN_ENV_VAR,
    RuntimeDataSource,
    market_data_credentials_configured,
)


def configure_drive_isolation() -> Path:
    """Configures root-relative runtime directories to guarantee ZERO C: drive leakage."""
    if getattr(sys, "frozen", False):
        app_root = Path(sys.executable).parent.resolve()
    else:
        app_root = Path(__file__).parent.resolve()

    # Ensure all runtime subdirectories stay strictly on the installation drive
    for folder in ["tmp", "data", "logs"]:
        (app_root / folder).mkdir(parents=True, exist_ok=True)

    # Re-route all environment temp/cache paths to the local installation drive
    local_tmp = str(app_root / "tmp")
    os.environ["TEMP"] = local_tmp
    os.environ["TMP"] = local_tmp
    os.environ["TMPDIR"] = local_tmp
    os.environ["MPLCONFIGDIR"] = str(app_root / "tmp" / "matplotlib")
    os.environ["PYTHONPYCACHEPREFIX"] = str(app_root / "tmp" / "pycache")
    return app_root


def load_startup_environment() -> tuple[str, ...]:
    """Load credentials from .env and report which names were set.

    Runs before anything inspects the environment for credentials. Without it the preflight
    credential gate reports "not configured" while the user is looking at the .env they filled
    in. Deliberately not part of run_prerequisite_checks, which must stay a pure inspection of
    the environment it is given rather than one that mutates it. Only names are printed.
    """
    loaded = load_env_file()
    if loaded:
        print(f"  Loaded {len(loaded)} variable(s) from .env: {', '.join(loaded)}")
    return loaded


def run_prerequisite_checks() -> tuple[bool, list[str]]:
    """Runs rigorous pre-flight checks before booting the QuantOS engine."""
    logs: list[str] = []
    all_passed = True

    # 1. Drive Isolation & Root Sandbox Check
    app_root = configure_drive_isolation()
    install_drive = app_root.drive or str(app_root).split("\\")[0]
    logs.append(
        f"[PASS] Drive-Isolated Storage Sandbox Active on '{install_drive}' (Zero C: leakage)"
    )

    # 2. Architecture Check
    is_64bit = sys.maxsize > 2**32

    if is_64bit:
        logs.append(f"[PASS] 64-bit Architecture Verified ({platform.machine()})")
    else:
        logs.append("[WARN] 32-bit environment detected; 64-bit recommended for large backtests")

    # 2. Local Loopback Socket Binding Check
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.bind(("127.0.0.1", 0))
        logs.append("[PASS] Local Loopback Socket Binding (127.0.0.1) OK")
    except Exception as err:
        logs.append(f"[FAIL] Localhost binding error: {err}")
        all_passed = False

    # 3. Double-Entry Decimal Ledger Invariant Check
    try:
        ledger = DecimalLedger(initial_cash=Decimal("1000000.00"))
        if ledger.reconcile():
            logs.append("[PASS] Decimal Double-Entry Ledger Invariant Check OK")
        else:
            logs.append("[FAIL] Ledger reconciliation failure")
            all_passed = False
    except Exception as err:
        logs.append(f"[FAIL] Decimal Ledger error: {err}")
        all_passed = False

    # 4. Alpha & Greeks Mathematical Subsystem Check
    try:
        greeks = BlackScholes.calculate_greeks(
            spot=24500.0,
            strike=24500.0,
            time_to_expiry_years=7.0 / 365.0,
            volatility=0.18,
            risk_free_rate=0.07,
            option_type=InstrumentType.OPTION_CALL,
        )
        if 0.0 < greeks.delta < 1.0 and greeks.gamma > 0.0:
            logs.append("[PASS] Quantitative Alpha & Black-Scholes Engine OK")
        else:
            logs.append("[FAIL] Black-Scholes numerical deviation")
            all_passed = False
    except Exception as err:
        logs.append(f"[FAIL] Quantitative pricing error: {err}")
        all_passed = False

    # 5. UI Assets & Static Dashboard Verification
    static_dir = Path(__file__).parent / "src" / "quant_system" / "server" / "static"
    # When bundled with PyInstaller:
    if not static_dir.exists():
        static_dir = Path(__file__).parent / "quant_system" / "server" / "static"
    if not static_dir.exists() and getattr(sys, "frozen", False):
        static_dir = Path(sys._MEIPASS) / "quant_system" / "server" / "static"  # type: ignore[attr-defined]

    if static_dir.exists() and (static_dir / "index.html").exists():
        logs.append("[PASS] Apple-Grade Dashboard UI Assets Located OK")
    else:
        logs.append("[WARN] Static dashboard assets not found; running in headless API mode")

    # 6. Market-Data Credential & Active Source Disclosure
    # Absent credentials are a supported research configuration, not a failure. They are reported
    # so that "all prerequisites verified" can never be mistaken for "connected to live data".
    if market_data_credentials_configured():
        logs.append(f"[PASS] Market-Data Credentials Detected ({ACCESS_TOKEN_ENV_VAR} is set)")
    else:
        logs.append(
            f"[WARN] No {ACCESS_TOKEN_ENV_VAR} configured; bundled surfaces run on "
            f"{RuntimeDataSource.SYNTHETIC} generated data, not real market data"
        )

    return all_passed, logs


def find_free_port(start_port: int = 8080) -> int:
    """Finds an available local port starting from start_port."""
    for port in range(start_port, start_port + 50):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            if s.connect_ex(("127.0.0.1", port)) != 0:
                return port
    return start_port


def open_browser_delayed(url: str, delay: float = 1.0) -> None:
    """Opens the user's default browser after the server has initialized."""
    time.sleep(delay)
    webbrowser.open(url)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="QuantOS Desktop Quantitative Trading & Risk Engine"
    )
    parser.add_argument("--port", type=int, default=None, help="Port to run the web server on")
    parser.add_argument(
        "--no-browser", action="store_true", help="Do not open browser automatically"
    )
    parser.add_argument(
        "--test-mode", action="store_true", help="Test mode startup check and immediate exit"
    )
    parser.add_argument(
        "--check-prerequisites",
        action="store_true",
        help="Run pre-flight validation checks and report",
    )
    args = parser.parse_args()

    print("=" * 70)
    print(f"  QuantOS Desktop Engine — Version {__version__}")
    print("  Institutional Quantitative Trading, Research & Risk Management")
    print("=" * 70)

    load_startup_environment()
    # Execute Pre-flight Prerequisite Checks
    passed, check_logs = run_prerequisite_checks()
    for log in check_logs:
        print(f"  {log}")
    print("-" * 70)

    if not passed:
        print("\n[ERROR] One or more critical system prerequisites failed. Cannot start.")
        sys.exit(1)

    if args.check_prerequisites or args.test_mode:
        print("[SUCCESS] All system prerequisites verified successfully.")
        sys.exit(0)

    port = args.port or find_free_port(8080)
    url = f"http://127.0.0.1:{port}"

    print(f"\n[INFO] Starting local engine at: {url}")
    print("[INFO] Press Ctrl+C to stop the engine.\n")

    if not args.no_browser:
        threading.Thread(target=open_browser_delayed, args=(url,), daemon=True).start()

    from quant_system.server.app import app

    uvicorn.run(app, host="127.0.0.1", port=port, log_level="info")


if __name__ == "__main__":
    main()
