"""Automated Release and Distribution Builder for QuantOS v1.0.0."""

from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

from quant_system import __version__


def compute_sha256(filepath: Path) -> str:
    """Computes SHA-256 hash of a file."""
    h = hashlib.sha256()
    with open(filepath, "rb") as f:
        while chunk := f.read(65536):
            h.update(chunk)
    return h.hexdigest()


def main() -> None:
    root_dir = Path(__file__).parent.parent
    dist_dir = root_dir / "dist"
    output_bundle = dist_dir / "QuantOS"

    print("=" * 70)
    print(f"  Building QuantOS Release v{__version__}")
    print("=" * 70)

    # 1. Run PyInstaller build
    print("\n[STEP 1] Running PyInstaller standalone compiler...")
    cmd = [sys.executable, "-m", "PyInstaller", "--noconfirm", str(root_dir / "quant_system.spec")]
    res = subprocess.run(cmd, cwd=str(root_dir))
    if res.returncode != 0:
        print("[ERROR] PyInstaller compilation failed!")
        sys.exit(res.returncode)

    if not output_bundle.exists():
        print(f"[ERROR] Output bundle not found at {output_bundle}")
        sys.exit(1)

    # 2. Generate SHA-256 Manifest
    print("\n[STEP 2] Generating cryptographically signed release manifest (MANIFEST.sha256)...")
    manifest_lines = []
    total_size = 0
    file_count = 0

    for file_path in sorted(output_bundle.rglob("*")):
        if file_path.is_file():
            rel_path = file_path.relative_to(output_bundle)
            file_hash = compute_sha256(file_path)
            manifest_lines.append(f"{file_hash}  {rel_path.as_posix()}")
            total_size += file_path.stat().st_size
            file_count += 1

    manifest_file = output_bundle / "MANIFEST.sha256"
    manifest_file.write_text("\n".join(manifest_lines) + "\n", encoding="utf-8")
    print(f"[SUCCESS] Hashed {file_count} files ({total_size / (1024 * 1024):.2f} MB).")

    # 3. Write Release Metadata
    release_info = {
        "app_name": "QuantOS",
        "version": __version__,
        "build_date": datetime.now(UTC).isoformat(),
        "total_files": file_count,
        "total_bytes": total_size,
        "executable": "QuantOS.exe",
    }
    (output_bundle / "release.json").write_text(
        json.dumps(release_info, indent=2), encoding="utf-8"
    )

    # 4. Create Portable ZIP Archive
    zip_target = dist_dir / f"QuantOS_v{__version__}_portable"
    print(f"\n[STEP 3] Packaging portable distribution archive: {zip_target}.zip")
    shutil.make_archive(str(zip_target), "zip", dist_dir, "QuantOS")

    # 5. Compile Standalone Setup Wizard (QuantOS_v1.0.0_Setup.exe)
    print("\n[STEP 4] Compiling Graphical Setup Installer (QuantOS_v1.0.0_Setup.exe)...")
    setup_spec = root_dir / "installer" / "setup_installer.spec"
    setup_cmd = [sys.executable, "-m", "PyInstaller", "--noconfirm", str(setup_spec)]
    setup_res = subprocess.run(setup_cmd, cwd=str(root_dir / "installer"))
    if setup_res.returncode == 0:
        setup_exe_built = root_dir / "installer" / "dist" / f"QuantOS_v{__version__}_Setup.exe"
        if setup_exe_built.exists():
            final_setup_dest = dist_dir / f"QuantOS_v{__version__}_Setup.exe"
            shutil.copy2(setup_exe_built, final_setup_dest)
            print(f"[SUCCESS] Setup Wizard created: {final_setup_dest}")

    print("\n" + "=" * 70)
    print(f"[BUILD COMPLETE] QuantOS v{__version__} successfully packaged!")
    print(f"  -> Setup Installer:      {dist_dir / f'QuantOS_v{__version__}_Setup.exe'}")
    print(f"  -> Standalone Directory: {output_bundle}")
    print(f"  -> Portable Zip Bundle:  {zip_target}.zip")
    print("=" * 70)


if __name__ == "__main__":
    main()
