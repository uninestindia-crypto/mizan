#!/usr/bin/env python3
"""Export Mizan model from evidence store or default calibrated weights into a standalone bundle."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR / "src"))

from quant_system.modeling.mizan_cli import handle_export  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Export Mizan model into a shareable .zip bundle.")
    parser.add_argument(
        "--output",
        "-o",
        type=Path,
        default=ROOT_DIR / "dist/mizan_model_v1.zip",
        help="Destination package file or directory",
    )
    parser.add_argument(
        "--evidence-manifest",
        type=Path,
        default=None,
        help="Optional path to a QuantOS evidence manifest.json",
    )
    parser.add_argument(
        "--format",
        choices=["zip", "dir"],
        default="zip",
        help="Export format (zip archive or directory)",
    )
    args = parser.parse_args()
    return handle_export(args)


if __name__ == "__main__":
    raise SystemExit(main())
