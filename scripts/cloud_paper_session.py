"""Cloud entry point for the scheduled paper session.

The laptop runs `scripts/run_scheduled_paper_session.py` from Windows Task Scheduler. A cloud host has
no scheduler, no stay-awake request and no disk that outlives the job, so this wrapper adds the three
things a headless Linux host needs and nothing else:

* **A token check that fails closed.** No token, or a token the provider rejects, stops the run before
  any data is fetched. The token is read from the environment only. Its value is never printed, logged
  or written, and no variable other than the two named in `TOKEN_VARIABLES` is read.
* **State that outlives the job.** The flagship book's state lives in `logs/paper_runs/`, which is
  untracked. A fresh cloud checkout has none, so without this the book would start from cash every
  morning. `--state-dir` points at a checkout of a state-only branch; state is copied in before the
  session and back out after it, including when the session fails, because a half-finished session's
  state is evidence.
* **A close time the host can honour.** A GitHub-hosted job stops at six hours, and the session wants
  09:15-15:30 IST. `--max-runtime-minutes` ends the session early rather than letting the host kill it
  mid-order, and says so loudly. A host with no limit runs to 15:30 as the laptop does.

It does not change what the book trades. The session, the model, the risk governor and the freshness
rules are `run_scheduled_paper_session._run`, unmodified. The cloud book is a separate book from the
laptop's: it starts from its own state, so the two cannot overwrite each other.

    python scripts/cloud_paper_session.py check
    python scripts/cloud_paper_session.py run --state-dir paper-state/state --max-runtime-minutes 340

Exit codes: 0 ok; 10 no token; 11 token rejected (expired, malformed or refused by the provider);
12 not a trading day (from `run`); 13 the quote feed could not be reached or priced, with the token not
shown to be at fault; 14 a state file contained the token, so state was not saved (the repository must
never hold a credential); anything else is the scheduled session's own code, passed through.

    python scripts/cloud_paper_session.py save-state --state-dir paper-state/state

`save-state` is `run`'s copy-out on its own. A workflow runs it as a last step so state is kept even when the
host killed the job before `run` could.

`check` uses the quote path the paper session itself uses (`run_paper_pilot_session.
fetch_upstox_live_quotes`), not `UpstoxClient.fetch_market_quote`. Measured on 2026-10-06 against the live
provider: the request carries the ISIN form `NSE_EQ|INE009A01021` and the reply is keyed by the symbol form
`NSE_EQ:INFY`, which `UpstoxClient`'s quote parser does not look up. The session's path handles both.
"""

from __future__ import annotations

import argparse
import os
import shutil
import sys
from collections.abc import Iterator
from datetime import datetime, time, timedelta, timezone
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))
sys.path.insert(0, str(PROJECT_ROOT / "src"))

IST = timezone(timedelta(hours=5, minutes=30))

#: The two variables the provider client reads, analytics token first. Nothing else is read.
TOKEN_VARIABLES = ("UPSTOX_ANALYTICS_TOKEN", "UPSTOX_ACCESS_TOKEN")

#: Where the flagship book keeps its state, and where it is copied from and to.
STATE_FOLDER = PROJECT_ROOT / "logs" / "paper_runs"

#: Market close, and the time reserved after the session ends for copying state out and pushing it.
MARKET_CLOSE = time(15, 30)
FINISH_MARGIN_MINUTES = 20

#: Liquid names used only to prove the token can read quotes. No order is ever placed.
PROBE_SYMBOLS = ("INFY", "RELIANCE", "TCS")

EXIT_NO_TOKEN = 10
EXIT_TOKEN_REJECTED = 11
EXIT_NOT_A_TRADING_DAY = 12
EXIT_FEED_UNAVAILABLE = 13
EXIT_TOKEN_IN_STATE = 14

#: HTTP statuses that mean the provider refused the credential rather than failed.
_REFUSAL_MARKERS = ("HTTP Error 401", "HTTP Error 403")


def redact(text: str, environ: dict[str, str] | None = None) -> str:
    """`text` with every configured token value replaced, so nothing printed can carry a token."""
    source = os.environ if environ is None else environ
    for name in TOKEN_VARIABLES:
        value = source.get(name, "").strip()
        if value:
            text = text.replace(value, "[token]")
    return text


def log(message: str) -> None:
    stamp = datetime.now(IST).strftime("%Y-%m-%d %H:%M:%S IST")
    print(f"{stamp} | {redact(message)}", flush=True)


def configured_token_variable(environ: dict[str, str] | None = None) -> str | None:
    """The name of the first token variable that holds a value. Never the value."""
    source = os.environ if environ is None else environ
    for name in TOKEN_VARIABLES:
        if source.get(name, "").strip():
            return name
    return None


def session_end_time(
    now: datetime,
    *,
    max_runtime_minutes: int | None,
    close: time = MARKET_CLOSE,
    margin_minutes: int = FINISH_MARGIN_MINUTES,
) -> tuple[time, bool]:
    """When the session should end, and whether that is earlier than the market close.

    With no runtime limit the session ends at the close. With one, it ends `margin_minutes` before
    the host would stop the job, rounded down to a whole minute, so state can still be saved.
    """
    if max_runtime_minutes is None:
        return close, False
    limit = now.astimezone(IST) + timedelta(minutes=max_runtime_minutes - margin_minutes)
    limit = limit.replace(second=0, microsecond=0)
    if limit.date() != now.astimezone(IST).date() or limit.time() >= close:
        return close, False
    return limit.time(), True


def plain_files(folder: Path) -> Iterator[Path]:
    """Regular files under `folder`, in a stable order. No link, file or folder, is ever followed."""
    for current, subfolders, names in os.walk(folder, followlinks=False):
        subfolders.sort()
        candidates = (Path(current) / name for name in sorted(names))
        yield from (path for path in candidates if path.is_file() and not path.is_symlink())


def sync_tree(source: Path, destination: Path) -> int:
    """Copy every regular file under `source` into `destination`, creating folders. Returns a count.

    Plain files only, and no link is followed in either direction. A state folder holding a link
    could otherwise copy something outside it, and a link already sitting in the destination could
    send a copy outside that.
    """
    if not source.is_dir():
        return 0
    boundary = destination.resolve()
    copied = 0
    for path in plain_files(source):
        target = destination / path.relative_to(source)
        target.parent.mkdir(parents=True, exist_ok=True)
        if target.is_symlink() or not target.parent.resolve().is_relative_to(boundary):
            continue
        shutil.copy2(path, target)
        copied += 1
    return copied


def _holds_any(path: Path, needles: list[bytes]) -> bool:
    content = path.read_bytes()
    return any(needle in content for needle in needles)


def files_containing_token(folder: Path, environ: dict[str, str] | None = None) -> list[Path]:
    """Regular files under `folder` that hold a configured token value. Never reads the value out."""
    source = os.environ if environ is None else environ
    needles = [
        source[name].strip().encode()
        for name in TOKEN_VARIABLES
        if len(source.get(name, "").strip()) > 0
    ]
    if not needles or not folder.is_dir():
        return []
    return [path for path in plain_files(folder) if _holds_any(path, needles)]


def save_state(state_dir: Path) -> int:
    """Copy the book's state out to `state_dir`. Refuses, copying nothing, if it holds the token."""
    leaked = files_containing_token(STATE_FOLDER)
    if leaked:
        names = ", ".join(str(path.relative_to(STATE_FOLDER)) for path in leaked)
        log(f"refusing to save state: {names} contains the token. Nothing was copied.")
        return EXIT_TOKEN_IN_STATE
    saved = sync_tree(STATE_FOLDER, state_dir)
    log(f"saved {saved} state file(s) to {state_dir}")
    return 0


def check_token() -> int:
    """Prove the token is present, unexpired and can read live quotes. Never prints the token."""
    name = configured_token_variable()
    if name is None:
        log(f"no token: set {TOKEN_VARIABLES[0]} (read-only analytics token) in the environment")
        return EXIT_NO_TOKEN
    log(f"token found in {name} (value not shown)")

    import run_paper_pilot_session as pilot

    try:
        pilot.assert_upstox_usable()
    except pilot.QuoteFeedError as error:
        log(f"the token failed the session's own validity check: {error}")
        return EXIT_TOKEN_REJECTED
    try:
        quotes = pilot.fetch_upstox_live_quotes(list(PROBE_SYMBOLS))
    except pilot.QuoteFeedError as error:
        if any(marker in str(error) for marker in _REFUSAL_MARKERS):
            log(f"the provider refused the token: {error}")
            return EXIT_TOKEN_REJECTED
        log(f"the quote feed could not be read, token not shown to be at fault: {error}")
        return EXIT_FEED_UNAVAILABLE
    for symbol in sorted(quotes):
        log(
            f"the provider answered a live quote request for {symbol}: last {quotes[symbol]['price']}"
        )
    log(
        f"{len(quotes)} of {len(PROBE_SYMBOLS)} probe symbols priced; nothing was ordered or written"
    )
    return 0


def run(args: argparse.Namespace) -> int:
    if configured_token_variable() is None:
        log(f"refusing: no token. Set {TOKEN_VARIABLES[0]} in the environment")
        return EXIT_NO_TOKEN

    import run_scheduled_paper_session as scheduled

    today = datetime.now(IST).date()
    try:
        scheduled.require_trading_day(today)
    except scheduled.NotATradingDay as refusal:
        log(f"not running: {refusal}")
        return EXIT_NOT_A_TRADING_DAY

    proof = check_token()
    if proof != 0:
        log("refusing: the token did not pass the check, so no data is fetched")
        return proof

    end_time, truncated = session_end_time(
        datetime.now(IST), max_runtime_minutes=args.max_runtime_minutes
    )
    if truncated:
        log(
            f"NOTICE: this host stops the job after {args.max_runtime_minutes} minutes, so the "
            f"session will close at {end_time:%H:%M} IST, earlier than {MARKET_CLOSE:%H:%M}. Use a "
            f"host with no job limit to run to the close."
        )

    state_dir: Path | None = args.state_dir
    if state_dir is not None:
        restored = sync_tree(state_dir, STATE_FOLDER)
        log(f"restored {restored} state file(s) from {state_dir}")

    namespace = argparse.Namespace(
        universe_name=args.universe_name,
        capital=args.capital,
        end_time_ist=f"{end_time:%H:%M}:00",
        interval_seconds=args.interval_seconds,
    )
    state_saved = 0
    try:
        code = int(scheduled._run(namespace))
    finally:
        if state_dir is not None:
            state_saved = save_state(state_dir)
    log(f"scheduled session exited {code}")
    return state_saved or code


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("check", help="prove the token works; place nothing, change nothing")
    saver = commands.add_parser("save-state", help="copy the book's state out to --state-dir")
    saver.add_argument("--state-dir", type=Path, required=True)
    runner = commands.add_parser("run", help="run today's paper session")
    runner.add_argument("--state-dir", type=Path, default=None)
    runner.add_argument("--max-runtime-minutes", type=int, default=None)
    runner.add_argument("--universe-name", default="NIFTY500", choices=["NIFTY50", "NIFTY500"])
    runner.add_argument("--capital", default="1000000.0")
    runner.add_argument("--interval-seconds", default="30")
    args = parser.parse_args(argv)
    if args.command == "check":
        return check_token()
    if args.command == "save-state":
        return save_state(args.state_dir)
    return run(args)


if __name__ == "__main__":
    raise SystemExit(main())
