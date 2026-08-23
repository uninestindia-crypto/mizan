"""Append-only, hash-chained journal for non-authoritative advisory records.

Each line is one JSON entry whose hash covers the previous entry's hash, so removing, reordering, or
editing any entry invalidates every entry after it. That is the property the learning loop needs:
a dataset assembled from this journal either is complete and in order, or says loudly that it is
not. Log lines cannot offer that — they rotate away and carry no schema.

The guarantee is *tamper-evidence*, not reproducibility. Re-running the prompts in this journal will
not reproduce the text in it, and no part of this module claims otherwise.

Single-writer by design. Concurrent appenders on one path are not supported and will be detected as
a broken chain rather than silently interleaved.
"""

from __future__ import annotations

import json
import os
from collections.abc import Iterator, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from quant_system.advisory.errors import AdvisoryError, AdvisoryFailureCode
from quant_system.advisory.records import AdvisoryRecord
from quant_system.data.market_data_evidence import canonical_sha256

GENESIS_SHA256 = "0" * 64

_MAX_ENTRY_BYTES = 1024 * 1024


@dataclass(frozen=True, slots=True)
class JournalEntry:
    """One sealed position in the chain."""

    sequence: int
    previous_sha256: str
    entry_sha256: str
    record: Mapping[str, Any]

    def canonical_payload(self) -> dict[str, Any]:
        return {
            "sequence": self.sequence,
            "previous_sha256": self.previous_sha256,
            "record": dict(self.record),
        }

    def recompute_sha256(self) -> str:
        return canonical_sha256(self.canonical_payload())


def _entry_from_mapping(payload: Mapping[str, Any], line_number: int) -> JournalEntry:
    try:
        sequence = payload["sequence"]
        previous_sha256 = payload["previous_sha256"]
        entry_sha256 = payload["entry_sha256"]
        record = payload["record"]
    except KeyError as exc:  # pragma: no cover - defensive
        raise AdvisoryError(
            AdvisoryFailureCode.JOURNAL_RECORD_MALFORMED,
            f"journal line {line_number} is missing field {exc.args[0]!r}",
        ) from exc
    if not isinstance(sequence, int) or isinstance(sequence, bool):
        raise AdvisoryError(
            AdvisoryFailureCode.JOURNAL_RECORD_MALFORMED,
            f"journal line {line_number} has a non-integer sequence",
        )
    if not isinstance(previous_sha256, str) or not isinstance(entry_sha256, str):
        raise AdvisoryError(
            AdvisoryFailureCode.JOURNAL_RECORD_MALFORMED,
            f"journal line {line_number} has a non-string hash",
        )
    if not isinstance(record, dict):
        raise AdvisoryError(
            AdvisoryFailureCode.JOURNAL_RECORD_MALFORMED,
            f"journal line {line_number} has a non-object record",
        )
    return JournalEntry(
        sequence=sequence,
        previous_sha256=previous_sha256,
        entry_sha256=entry_sha256,
        record=record,
    )


class AdvisoryJournal:
    """An append-only file of advisory records. It cannot rewrite or delete."""

    def __init__(self, path: Path) -> None:
        self.path = path

    def append(self, record: AdvisoryRecord) -> JournalEntry:
        """Seal one record onto the end of the chain and fsync it."""
        tip = self._tip()
        sequence = 0 if tip is None else tip.sequence + 1
        previous_sha256 = GENESIS_SHA256 if tip is None else tip.entry_sha256

        payload = record.canonical_payload()
        entry_sha256 = canonical_sha256(
            {
                "sequence": sequence,
                "previous_sha256": previous_sha256,
                "record": payload,
            }
        )
        entry = JournalEntry(
            sequence=sequence,
            previous_sha256=previous_sha256,
            entry_sha256=entry_sha256,
            record=payload,
        )
        line = json.dumps(
            {
                "sequence": entry.sequence,
                "previous_sha256": entry.previous_sha256,
                "entry_sha256": entry.entry_sha256,
                "record": entry.record,
            },
            ensure_ascii=False,
            allow_nan=False,
            separators=(",", ":"),
            sort_keys=True,
        )
        encoded = f"{line}\n".encode()
        if len(encoded) > _MAX_ENTRY_BYTES:
            raise AdvisoryError(
                AdvisoryFailureCode.JOURNAL_RECORD_MALFORMED,
                f"entry of {len(encoded)} bytes exceeds the {_MAX_ENTRY_BYTES}-byte limit",
            )

        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("ab") as handle:
            handle.write(encoded)
            handle.flush()
            os.fsync(handle.fileno())
        return entry

    def read_entries(self) -> list[JournalEntry]:
        """Every entry in file order. Does not verify the chain; call :meth:`verify_chain`."""
        return list(self._iter_entries())

    def records(self) -> list[Mapping[str, Any]]:
        """The record payloads only, in order, after verifying the chain."""
        return [entry.record for entry in self.verify_chain()]

    def verify_chain(self) -> Sequence[JournalEntry]:
        """Recompute every hash and link. Raises ``JOURNAL_CHAIN_BROKEN`` on any tamper."""
        entries = self.read_entries()
        expected_previous = GENESIS_SHA256
        for index, entry in enumerate(entries):
            if entry.sequence != index:
                raise AdvisoryError(
                    AdvisoryFailureCode.JOURNAL_CHAIN_BROKEN,
                    f"entry at position {index} declares sequence {entry.sequence}",
                )
            if entry.previous_sha256 != expected_previous:
                raise AdvisoryError(
                    AdvisoryFailureCode.JOURNAL_CHAIN_BROKEN,
                    (
                        f"entry {entry.sequence} chains to {entry.previous_sha256} "
                        f"but the previous entry hashes to {expected_previous}"
                    ),
                )
            recomputed = entry.recompute_sha256()
            if recomputed != entry.entry_sha256:
                raise AdvisoryError(
                    AdvisoryFailureCode.JOURNAL_CHAIN_BROKEN,
                    (
                        f"entry {entry.sequence} declares hash {entry.entry_sha256} "
                        f"but its content hashes to {recomputed}"
                    ),
                )
            expected_previous = entry.entry_sha256
        return entries

    def _iter_entries(self) -> Iterator[JournalEntry]:
        if not self.path.exists():
            return
        with self.path.open("r", encoding="utf-8") as handle:
            for line_number, raw_line in enumerate(handle, start=1):
                stripped = raw_line.strip()
                if not stripped:
                    continue
                try:
                    payload = json.loads(stripped)
                except json.JSONDecodeError as exc:
                    raise AdvisoryError(
                        AdvisoryFailureCode.JOURNAL_RECORD_MALFORMED,
                        f"journal line {line_number} is not valid JSON: {exc.msg}",
                    ) from exc
                if not isinstance(payload, dict):
                    raise AdvisoryError(
                        AdvisoryFailureCode.JOURNAL_RECORD_MALFORMED,
                        f"journal line {line_number} is not a JSON object",
                    )
                yield _entry_from_mapping(payload, line_number)

    def _tip(self) -> JournalEntry | None:
        tip: JournalEntry | None = None
        for entry in self._iter_entries():
            tip = entry
        return tip
