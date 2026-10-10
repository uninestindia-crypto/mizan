"""The plain sentences a person reads while company filings are being read: progress, results and failures."""

from __future__ import annotations

from quant_system.shariah.filings.models import FilingFigures, ReadStatus
from quant_system.shariah.filings.selection import Selection

__all__ = [
    "BUSY",
    "NOTHING_TO_REFRESH",
    "SAVE_FAILED_PREFIX",
    "STOPPED",
    "TOO_MANY_BLOCKS",
    "failure_reason",
    "finished_message",
    "reading_message",
]

BUSY = "Another filing is already being read. Wait for it to finish, then try again."
NOTHING_TO_REFRESH = "There are no stocks to refresh yet."
STOPPED = "Stopped. Filings already read were kept."
TOO_MANY_BLOCKS = (
    "NSE has stopped answering QuantOS for now, so reading was stopped. Filings already read were kept. "
    "Try again later."
)
SAVE_FAILED_PREFIX = "Reading was stopped. "
_NOT_READ = "QuantOS could not read this company's filing."
_NOTHING_READ = "QuantOS could not read any company filing."


def reading_message(symbol: str, done: int, total: int) -> str:
    if total <= 1:
        return f"Reading the latest filing for {symbol} from NSE."
    return f"Reading filing {done + 1} of {total}: {symbol}."


def failure_reason(selection: Selection) -> str:
    """Why a company's filing could not be used, in a plain sentence, from what was found."""
    figures = selection.figures
    if figures is not None and figures.read_note:
        return figures.read_note
    if selection.note:
        return selection.note
    return _NOT_READ


def used_filing(figures: FilingFigures) -> bool:
    """Only a filing that read cleanly and agrees with itself is kept for the person."""
    return figures.read_status is ReadStatus.READ_OK


def finished_message(symbols: list[str], saved: int, failures: list[dict[str, str]]) -> str:
    """The closing sentence of a job that ran to the end."""
    if len(symbols) == 1:
        return failures[0]["reason"] if failures else f"Read the latest filing for {symbols[0]}."
    if saved == 0:
        return f"{_NOTHING_READ} {failures[0]['reason']}" if failures else NOTHING_TO_REFRESH
    text = f"Updated {saved} of {len(symbols)} stocks."
    return f"{text} {len(failures)} could not be read." if failures else text
