"""Emit a committed hash inventory of the local, gitignored evidence stores.

Research evidence lives under ``data/evidence/``, which is gitignored: an adjudicator working from
a clean clone has nothing to verify against, so every claim resting on those stores is unfalsifiable
to them. That is the open question 6 in
``.launch/ADJUDICATION-BRIEF-TRAINING-PATH.md``.

Committing the evidence is not the answer -- it is hundreds of megabytes of derived data. Committing
its *identity* is. This walks each store, verifies it, and writes one line per resource: the store,
the resource id, its type, and its manifest hash. The output is small, diffable, and belongs in
version control.

What that buys, precisely:

* An adjudicator can re-run this against their copy of the stores and diff. A byte differs anywhere
  and a hash moves.
* A silently mutated or re-published store is detectable, because the recorded hash no longer
  matches.
* A claim citing a model id can be checked against a committed record that the model existed with
  that identity at this revision.

What it does not buy, and must not be read as: it does not make the *contents* auditable, and it
does not prove the evidence was correct when written. It proves only that what is there now is what
was there when this ran. Provenance is still section 4 of the brief.

    python scripts/evidence_manifest.py                  # write the default inventory
    python scripts/evidence_manifest.py --check          # verify stores against it, exit 1 on drift
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from quant_system.evidence import (  # noqa: E402
    EvidenceResourceType,
    EvidenceStore,
    EvidenceStoreConfig,
)

DEFAULT_OUTPUT = Path("data/evidence-inventory.txt")
EVIDENCE_ROOT = Path("data/evidence")


def _discover_stores(root: Path) -> list[Path]:
    """Every directory that looks like an evidence store, nesting included.

    The market-cache stores keep their real root one level below the campaign directory, which is
    exactly the kind of thing a hand-written path list gets wrong -- a first scan of the campaign
    directory reported zero resources while a store with 100 datasets sat inside it.
    """
    found: list[Path] = []
    for candidate in sorted(root.rglob("*")):
        if not candidate.is_dir():
            continue
        # A store is identifiable by its own layout, not by where someone put it.
        if (candidate / "blobs").is_dir() and (candidate / "active").is_dir():
            found.append(candidate)
    return found


def _inventory(stores: list[Path]) -> list[str]:
    lines: list[str] = []
    for store_path in stores:
        try:
            store = EvidenceStore(EvidenceStoreConfig(root=store_path, min_free_bytes=0))
        except Exception as error:  # noqa: BLE001 - a store we cannot open is worth recording
            lines.append(f"{store_path.as_posix()}\tUNREADABLE\t{type(error).__name__}")
            continue
        rel = store_path.relative_to(EVIDENCE_ROOT).as_posix()
        for resource_type in EvidenceResourceType:
            try:
                verified = store.list_verified(resource_type)
            except Exception:  # noqa: BLE001 - absent type is not an error
                continue
            for item in verified:
                manifest = item.manifest
                lines.append(
                    f"{rel}\t{resource_type.name}\t{manifest.resource_id}\t"
                    f"{getattr(manifest, 'manifest_hash', '') or ''}"
                )
    return sorted(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="evidence_manifest")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument(
        "--check",
        action="store_true",
        help="compare the stores against the committed inventory and exit 1 on any drift",
    )
    args = parser.parse_args(argv)

    if not EVIDENCE_ROOT.exists():
        print(f"no evidence root at {EVIDENCE_ROOT}", flush=True)
        return 0

    stores = _discover_stores(EVIDENCE_ROOT)
    lines = _inventory(stores)

    if args.check:
        if not args.output.exists():
            print(f"REFUSED: no inventory at {args.output} to check against", flush=True)
            return 1
        recorded = args.output.read_text(encoding="utf-8").splitlines()
        recorded = [line for line in recorded if line and not line.startswith("#")]
        if recorded == lines:
            print(f"OK: {len(lines)} resources match the committed inventory", flush=True)
            return 0
        added = set(lines) - set(recorded)
        removed = set(recorded) - set(lines)
        print("DRIFT against the committed inventory", flush=True)
        print(f"  present now but not recorded : {len(added)}", flush=True)
        print(f"  recorded but absent now      : {len(removed)}", flush=True)
        for line in sorted(added)[:5]:
            print(f"    + {line}", flush=True)
        for line in sorted(removed)[:5]:
            print(f"    - {line}", flush=True)
        return 1

    header = [
        "# Hash inventory of the local, gitignored evidence stores.",
        "# Regenerate: python scripts/evidence_manifest.py",
        "# Verify:     python scripts/evidence_manifest.py --check",
        "# store\tresource_type\tresource_id\tmanifest_hash",
    ]
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text("\n".join(header + lines) + "\n", encoding="utf-8")
    print(f"wrote {len(lines)} resources from {len(stores)} stores to {args.output}", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
