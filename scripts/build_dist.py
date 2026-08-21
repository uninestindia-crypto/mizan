"""Automated Release and Distribution Builder for QuantOS v1.0.0."""

from __future__ import annotations

import sys
from pathlib import Path

from quant_system import __version__
from quant_system.release.builder import build_release


def main() -> None:
    root_dir = Path(__file__).parent.parent
    dist_dir = root_dir / "dist"

    print("=" * 70)
    print(f"  Building QuantOS Release v{__version__}")
    print("=" * 70)

    result = build_release(
        project_root=root_dir,
        output_dir=dist_dir,
        run_pyinstaller=True,
    )

    if not result.success:
        print(f"[ERROR] Build failed: {result.errors}")
        sys.exit(1)

    print("\n" + "=" * 70)
    print(f"[BUILD COMPLETE] QuantOS v{__version__} successfully packaged!")
    print(f"  -> Version:              {result.version}")
    print(f"  -> Git Commit SHA:       {result.git_commit_sha}")
    print(f"  -> uv.lock SHA-256:      {result.uv_lock_sha256}")
    print(f"  -> Standalone Directory: {result.bundle_dir}")
    print(f"  -> Manifest:             {result.manifest_file}")
    print(f"  -> SBOM:                 {result.sbom_file}")
    if result.zip_archive:
        print(f"  -> Portable Zip Bundle:  {result.zip_archive}")
    print("=" * 70)


if __name__ == "__main__":
    main()
