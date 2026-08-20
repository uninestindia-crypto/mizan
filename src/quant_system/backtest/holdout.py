"""Holdout Vault: Cryptographically partitions data into Discovery vs Out-Of-Sample validation sets."""

from __future__ import annotations

import hashlib
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date

from quant_system.core.domain import PriceBar


@dataclass(frozen=True, slots=True)
class PartitionedDataset:
    discovery_bars: Sequence[PriceBar]
    out_of_sample_bars: Sequence[PriceBar]
    split_date: date
    manifest_hash: str


class HoldoutVault:
    """Guarantees strict separation between strategy parameter tuning and out-of-sample testing."""

    @staticmethod
    def partition(
        bars: Sequence[PriceBar],
        split_date: date,
    ) -> PartitionedDataset:
        """Splits bars chronologically at split_date and computes a SHA-256 fingerprint."""
        discovery = [b for b in bars if b.timestamp.date() < split_date]
        oos = [b for b in bars if b.timestamp.date() >= split_date]

        if not discovery or not oos:
            raise ValueError(
                f"Partition produced empty set: discovery={len(discovery)}, oos={len(oos)}"
            )

        hasher = hashlib.sha256()
        for b in bars:
            hasher.update(f"{b.symbol}:{b.timestamp.isoformat()}:{b.close}".encode())

        return PartitionedDataset(
            discovery_bars=discovery,
            out_of_sample_bars=oos,
            split_date=split_date,
            manifest_hash=hasher.hexdigest(),
        )
