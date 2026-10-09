"""The broker view: sign in on Upstox's page, look at the account, and say plainly how fresh the figures are.

Nothing here can place, change or cancel an order, move money, or change an account setting. The key Upstox hands back
lives only in the vault, under its own entry; it is never copied into the environment, a file, a log, a reply, an error
or an AI prompt. Everything is injected, so every path can be tried with no network and no real account.
"""

from __future__ import annotations

import logging
import re
import threading
from collections.abc import Callable, Mapping
from datetime import UTC, datetime, time, timedelta
from typing import Any, Protocol

from quant_system.broker_view import messages
from quant_system.broker_view.endpoints import CALLBACK_ADDRESS
from quant_system.broker_view.login import (
    LoginCheck,
    LoginTracker,
    authorize_address,
    exchange_form,
    read_exchange_reply,
)
from quant_system.broker_view.loopback import CONNECTED, FAILED, IGNORED, PortBusy
from quant_system.broker_view.model import INDIA, Snapshot
from quant_system.broker_view.session_http import SessionTransport
from quant_system.broker_view.store import SnapshotStore
from quant_system.broker_view.summary import assistant_summary
from quant_system.broker_view.upstox_read import Failure, UpstoxReader
from quant_system.live.upstox_key import key_expiry, key_problem

logger = logging.getLogger(__name__)

BROKER = "upstox"
LABEL = "Upstox"
THROTTLE_SECONDS = 30
STALE_SECONDS = 300
CALL_SECONDS = 10.0
CALL_BYTES = 2 * 1024 * 1024
FUNDS_RESUME = time(5, 30)  # Upstox does not serve cash between 00:00 and 05:30 India time
_SIGN_IN_CODE = re.compile(r"[\x21-\x7e]{1,200}")


class BrokerViewError(Exception):
    """A refusal with a message already written for the person, and the status the route should answer with."""

    def __init__(self, status: int, code: str, message: str) -> None:
        super().__init__(message)
        self.status, self.code, self.message = status, code, message


class KeyVault(Protocol):
    @property
    def available(self) -> bool: ...
    def load(self) -> str | None: ...
    def save(self, key: str) -> None: ...
    def forget(self) -> None: ...


class Listener(Protocol):
    def start(self) -> None: ...
    def stop(self) -> None: ...


ListenerFactory = Callable[[Callable[[Mapping[str, str]], str]], Listener]


def _in_thread(work: Callable[[], None]) -> None:
    threading.Thread(target=work, daemon=True).start()


def next_key_end(now: datetime) -> datetime:
    """The next 03:30 India time, when Upstox ends a sign-in whatever time it was made."""
    local = now.astimezone(INDIA)
    target = local.replace(hour=3, minute=30, second=0, microsecond=0)
    return target if target > local else target + timedelta(days=1)


class BrokerView:
    def __init__(
        self,
        *,
        vault: KeyVault,
        store: SnapshotStore,
        reader: UpstoxReader,
        session: SessionTransport,
        app_keys: Callable[[], tuple[str, str] | None],
        open_page: Callable[[str], bool],
        make_listener: ListenerFactory,
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
        background: Callable[[Callable[[], None]], None] = _in_thread,
    ) -> None:
        self._vault, self._store, self._reader, self._session = vault, store, reader, session
        self._app_keys, self._open_page, self._make_listener = app_keys, open_page, make_listener
        self._clock, self._background = clock, background
        self._tracker = LoginTracker(clock)
        self._lock = threading.RLock()
        self._refresh_lock = threading.Lock()
        self._listener: Listener | None = None
        self._problem: str | None = None
        self._last_call_at: datetime | None = None

    # ---------------------------------------------------------------- the key

    def _load_key(self) -> str | None:
        try:
            return self._vault.load()
        except Exception:  # the vault is the operating system's; its text is not ours to show
            return None

    def _forget_key(self) -> None:
        try:
            self._vault.forget()
        except Exception:
            logger.warning("broker view: the saved sign-in could not be removed")
        self._store.set_key_ends_at(BROKER, None)

    def _live_key(self) -> str | None:
        """The saved key if it has not ended. A key that says it has ended is forgotten without asking Upstox."""
        key = self._load_key()
        if not key:
            return None
        now = self._clock()
        ends = key_expiry(key) or self._store.key_ends_at(BROKER)
        if key_problem(key, now) is not None or (ends is not None and now >= ends):
            self._forget_key()
            self._problem = messages.KEY_ENDED
            return None
        return key

    def _connected(self) -> bool:
        with self._lock:
            return self._live_key() is not None

    # ---------------------------------------------------------------- signing in

    def begin_login(self) -> dict[str, Any]:
        if not self._vault.available:
            raise BrokerViewError(409, "BROKER_UNAVAILABLE", messages.NOT_AVAILABLE)
        keys = self._app_keys()
        if keys is None:
            raise BrokerViewError(422, "BROKER_NOT_SET_UP", messages.SAVE_KEYS_FIRST)
        self._stop_listener()
        with self._lock:
            attempt = self._tracker.begin()
            self._problem = None
        listener = self._make_listener(self.finish_login)
        try:
            listener.start()
        except PortBusy as error:
            self._tracker.cancel()
            raise BrokerViewError(409, "CALLBACK_BUSY", messages.PORT_BUSY) from error
        with self._lock:
            self._listener = listener
        address = authorize_address(keys[0], attempt.state)
        try:
            opened = bool(self._open_page(address))
        except Exception:
            opened = False
        return {"opened": opened, "login_address": address}

    def cancel_login(self) -> dict[str, Any]:
        self._stop_listener()
        with self._lock:
            self._tracker.cancel()
        return self.status()

    def _stop_listener(self) -> None:
        """Stop the open listener. Never done while holding the lock: stopping waits for a request that may need it."""
        with self._lock:
            listener, self._listener = self._listener, None
        if listener is not None:
            listener.stop()

    def finish_login(self, params: Mapping[str, str]) -> str:
        """Called by the listener with what Upstox's page sent back. Returns what the browser page should say."""
        with self._lock:
            check = self._tracker.check_and_consume(params.get("state"))
            if check is LoginCheck.EXPIRED:
                self._problem = messages.LOGIN_TIMED_OUT
        if check is not LoginCheck.OK:
            return IGNORED
        code = params.get("code", "")
        keys = self._app_keys()
        if keys is None or not _SIGN_IN_CODE.fullmatch(code):
            return self._login_failed("no code")
        try:
            response = self._session.exchange_code(
                exchange_form(code, keys[0], keys[1]),
                timeout_seconds=CALL_SECONDS,
                max_response_bytes=CALL_BYTES,
            )
        except Exception as error:
            return self._login_failed(type(error).__name__)
        key = read_exchange_reply(response.body) if response.status == 200 else None
        if key is None:
            return self._login_failed(f"status {response.status}")
        now = self._clock()
        try:
            self._vault.save(key)
        except Exception:
            return self._login_failed("not saved")
        with self._lock:
            self._store.set_key_ends_at(BROKER, key_expiry(key) or next_key_end(now))
            self._problem = None
            self._last_call_at = None
        logger.info("broker view: connected")
        self._background(self._refresh_quietly)
        return CONNECTED

    def _login_failed(self, reason: str) -> str:
        with self._lock:
            self._problem = messages.LOGIN_FAILED
        logger.info("broker view: sign-in not completed (%s)", reason)
        return FAILED

    def _refresh_quietly(self) -> None:
        try:
            self.refresh(force=True)
        except Exception as error:
            logger.warning("broker view: first refresh failed (%s)", type(error).__name__)

    # ---------------------------------------------------------------- looking

    def refresh(self, *, force: bool = False) -> str | None:
        """Fetch holdings, positions and cash. Returns the problem in words, or None when all is well."""
        if not self._refresh_lock.acquire(blocking=False):
            return None  # another refresh is already running; its figures will be the stored ones
        try:
            return self._refresh(force)
        finally:
            self._refresh_lock.release()

    def _refresh(self, force: bool) -> str | None:
        with self._lock:
            key = self._live_key()
            if key is None:
                return self._problem or messages.NOT_CONNECTED
            now = self._clock()
            last = self._last_call_at
            if not force and last is not None and (now - last).total_seconds() < THROTTLE_SECONDS:
                return None
            self._last_call_at = now
        holdings = self._reader.holdings(key)
        if holdings.failure is not None or holdings.value is None:
            return self._failed(holdings.failure)
        positions = self._reader.positions(key)
        if positions.failure is not None and (
            positions.failure.key_rejected or positions.failure.static_ip
        ):
            return self._failed(positions.failure)
        in_window = self._cash_not_served(now)
        funds = None if in_window else self._reader.funds(key)
        if funds is not None and funds.failure is not None and funds.failure.key_rejected:
            return self._failed(funds.failure)
        notes: list[str] = []
        if positions.failure is not None:
            notes.append(messages.POSITIONS_MISSING)
        if in_window:
            notes.append(messages.FUNDS_WINDOW)
        elif funds is not None and funds.failure is not None:
            notes.append(messages.FUNDS_MISSING)
        held, open_positions = holdings.value, positions.value
        skipped_positions = open_positions.skipped if open_positions is not None else 0
        partial = messages.partial(held.skipped, skipped_positions)
        if partial:
            notes.append(partial)
        snapshot = Snapshot(
            broker=BROKER,
            fetched_at=now,
            holdings=held.rows,
            positions=open_positions.rows if open_positions is not None else (),
            cash=funds.value if funds is not None else None,
            skipped_holdings=held.skipped,
            skipped_positions=skipped_positions,
            notes=tuple(notes),
        )
        self._store.save(BROKER, now, snapshot.payload())
        with self._lock:
            self._problem = None
        logger.info(
            "broker view refreshed: %d holdings, %d positions, cash %s",
            len(snapshot.holdings),
            len(snapshot.positions),
            "skipped" if snapshot.cash is None else "read",
        )
        return None

    def _failed(self, failure: Failure | None) -> str:
        message = failure.message if failure is not None else messages.UNREADABLE
        with self._lock:
            if failure is not None and failure.key_rejected:
                self._forget_key()
            self._problem = message
        logger.info("broker view: not refreshed (%s)", failure.reason if failure else "no figures")
        return message

    @staticmethod
    def _cash_not_served(now: datetime) -> bool:
        return now.astimezone(INDIA).time() < FUNDS_RESUME

    # ---------------------------------------------------------------- answers

    def status(self) -> dict[str, Any]:
        timed_out = False
        with self._lock:
            connected = self._live_key() is not None
            if self._tracker.timed_out:
                self._problem, timed_out = messages.LOGIN_TIMED_OUT, True
                self._tracker.cancel()
            waiting = self._tracker.waiting
            problem = self._problem
            ends = self._store.key_ends_at(BROKER) if connected else None
            set_up = self._app_keys() is not None
        if timed_out:
            self._stop_listener()
        return {
            "brokers": [
                {
                    "id": BROKER,
                    "label": LABEL,
                    "set_up": set_up,
                    "connected": connected,
                    "waiting_for_sign_in": waiting,
                    "key_ends_at": None if ends is None else ends.astimezone(INDIA).isoformat(),
                    "callback_address": CALLBACK_ADDRESS,
                    "message": problem,
                }
            ],
            "assistant_access": self._store.assistant_access(),
            "available": self._vault.available,
        }

    def snapshot(self) -> dict[str, Any]:
        """The last figures with their fetch time. Reading never asks Upstox for anything."""
        with self._lock:
            connected = self._live_key() is not None
            problem = self._problem
        stored = self._store.load(BROKER)
        now = self._clock()
        set_up = self._app_keys() is not None
        reply: dict[str, Any] = {
            "broker": BROKER,
            "connected": connected,
            "view_only": True,
            "label": messages.SNAPSHOT_LABEL,
            "fetched_at": None,
            "freshness": "NONE",
            "message": None,
            "totals": None,
            "cash": None,
            "holdings": [],
            "positions": [],
            "warnings": [],
            "skipped": {"holdings": 0, "positions": 0},
            "notes": [],
        }
        if stored is not None:
            reply.update(stored.payload)
            age = (now - stored.fetched_at).total_seconds()
            reply["freshness"] = "UP_TO_DATE" if age <= STALE_SECONDS else "OLDER"
        reply["message"] = problem or self._default_message(connected, stored is not None, set_up)
        return reply

    @staticmethod
    def _default_message(connected: bool, has_figures: bool, set_up: bool) -> str | None:
        if connected:
            return None
        if has_figures:
            return messages.KEY_ENDED
        return messages.NOT_CONNECTED if set_up else messages.NOT_SET_UP

    # ---------------------------------------------------------------- leaving

    def disconnect(self) -> dict[str, Any]:
        self._stop_listener()
        key = self._load_key()
        if key and key_problem(key, self._clock()) is None:
            try:  # the person's session on Upstox ends too; this is the only call made at sign-out
                self._session.end_session(
                    key, timeout_seconds=CALL_SECONDS, max_response_bytes=CALL_BYTES
                )
            except Exception as error:
                logger.info("broker view: sign-out not confirmed (%s)", type(error).__name__)
        with self._lock:
            self._forget_key()
            self._store.delete(BROKER)
            self._tracker.cancel()
            self._problem = None
            self._last_call_at = None
        return self.status()

    # ---------------------------------------------------------------- the assistant

    def set_assistant_access(self, allowed: bool) -> dict[str, Any]:
        self._store.set_assistant_access(allowed)
        return self.status()

    def assistant_summary(self) -> dict[str, Any]:
        if not self._store.assistant_access():
            raise BrokerViewError(409, "ASSISTANT_OFF", messages.ASSISTANT_OFF)
        stored = self._store.load(BROKER)
        connected = self._connected()
        if stored is None and not connected:
            set_up = self._app_keys() is not None
            raise BrokerViewError(
                409, "NOT_CONNECTED", messages.NOT_CONNECTED if set_up else messages.NOT_SET_UP
            )
        now = self._clock()
        if connected and (
            stored is None or (now - stored.fetched_at).total_seconds() > STALE_SECONDS
        ):
            self.refresh()
            stored = self._store.load(BROKER)
        if stored is None:
            raise BrokerViewError(409, "NO_FIGURES", self._problem or messages.NOT_CONNECTED)
        return assistant_summary(
            stored.payload, stored.fetched_at, now, key_ended=not self._connected()
        )
