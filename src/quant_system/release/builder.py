"""Automated Release Builder for QuantOS Windows x64 Distribution."""

from __future__ import annotations

import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

from quant_system import __version__
from quant_system.release.manifest import (
    generate_release_manifest,
    validate_release_bundle,
    write_release_manifest,
)
from quant_system.release.sbom import (
    compute_sha256,
    generate_sbom,
    get_git_commit_sha,
    write_sbom,
)


@dataclass
class BuildResult:
    """Consolidated summary of a release build execution."""

    success: bool
    version: str
    git_commit_sha: str
    uv_lock_sha256: str
    bundle_dir: Path
    zip_archive: Path | None
    sbom_file: Path
    manifest_file: Path
    total_files: int
    total_bytes: int
    errors: list[str]


def build_release(
    project_root: Path,
    output_dir: Path | None = None,
    run_pyinstaller: bool = True,
    spec_path: Path | None = None,
    target_arch: str = "x86_64",
    target_os: str = "windows",
) -> BuildResult:
    """Builds a complete, reproducible QuantOS Windows release distribution."""
    errors: list[str] = []
    dist_dir = output_dir or (project_root / "dist")
    bundle_dir = dist_dir / "quantos"
    lock_path = project_root / "uv.lock"

    if not lock_path.exists():
        errors.append(f"uv.lock not found at: {lock_path}")
        return BuildResult(
            success=False,
            version=__version__,
            git_commit_sha="",
            uv_lock_sha256="",
            bundle_dir=bundle_dir,
            zip_archive=None,
            sbom_file=dist_dir / "sbom.json",
            manifest_file=dist_dir / "release-manifest.json",
            total_files=0,
            total_bytes=0,
            errors=errors,
        )

    # 1. Resolve cryptographic base identities
    git_sha = get_git_commit_sha(project_root)
    lock_sha = compute_sha256(lock_path)

    # 2. Run PyInstaller Standalone Compilation
    if run_pyinstaller:
        chosen_spec = spec_path or (project_root / "installer" / "quantos.spec")
        if not chosen_spec.exists():
            chosen_spec = project_root / "quant_system.spec"

        if not chosen_spec.exists():
            errors.append(f"PyInstaller spec not found: {chosen_spec}")
            return BuildResult(
                success=False,
                version=__version__,
                git_commit_sha=git_sha,
                uv_lock_sha256=lock_sha,
                bundle_dir=bundle_dir,
                zip_archive=None,
                sbom_file=dist_dir / "sbom.json",
                manifest_file=dist_dir / "release-manifest.json",
                total_files=0,
                total_bytes=0,
                errors=errors,
            )

        cmd = [
            sys.executable,
            "-m",
            "PyInstaller",
            "--noconfirm",
            "--distpath",
            str(dist_dir),
            str(chosen_spec),
        ]
        res = subprocess.run(cmd, cwd=str(project_root), check=False)
        if res.returncode != 0:
            errors.append(f"PyInstaller execution failed with exit code {res.returncode}")
            return BuildResult(
                success=False,
                version=__version__,
                git_commit_sha=git_sha,
                uv_lock_sha256=lock_sha,
                bundle_dir=bundle_dir,
                zip_archive=None,
                sbom_file=dist_dir / "sbom.json",
                manifest_file=dist_dir / "release-manifest.json",
                total_files=0,
                total_bytes=0,
                errors=errors,
            )

    # If bundle directory was created as QuantOS instead of quantos, alias or symlink
    if not bundle_dir.exists() and (dist_dir / "QuantOS").exists():
        bundle_dir = dist_dir / "QuantOS"

    if not bundle_dir.exists():
        bundle_dir.mkdir(parents=True, exist_ok=True)

    # 3. Generate Software Bill of Materials (SBOM)
    sbom_data = generate_sbom(
        lock_path=lock_path,
        repo_root=project_root,
        target_platform=f"{target_os}-{target_arch}",
        app_version=__version__,
    )
    # Write inside bundle and to root dist
    bundle_sbom_path = bundle_dir / "sbom.json"
    write_sbom(sbom_data, bundle_sbom_path)
    root_sbom_path = dist_dir / "quantos-sbom.json"
    write_sbom(sbom_data, root_sbom_path)

    # 4. Generate Cryptographic Release Manifest
    manifest = generate_release_manifest(
        bundle_dir=bundle_dir,
        git_commit_sha=git_sha,
        uv_lock_sha256=lock_sha,
        version=__version__,
        executable_name="quantos.exe",
        target_os=target_os,
        target_arch=target_arch,
    )
    manifest_json, _, _ = write_release_manifest(bundle_dir, manifest)

    # 5. Create Portable ZIP Archive
    zip_target = dist_dir / f"quantos-v{__version__}-{target_os}-{target_arch}"
    zip_archive_path = Path(
        shutil.make_archive(
            base_name=str(zip_target),
            format="zip",
            root_dir=str(dist_dir),
            base_dir=bundle_dir.name,
        )
    )

    # 6. Validate Release Bundle Integrity
    val_res = validate_release_bundle(bundle_dir)
    if not val_res.is_valid:
        errors.append(val_res.message)

    return BuildResult(
        success=len(errors) == 0,
        version=__version__,
        git_commit_sha=git_sha,
        uv_lock_sha256=lock_sha,
        bundle_dir=bundle_dir,
        zip_archive=zip_archive_path,
        sbom_file=bundle_sbom_path,
        manifest_file=manifest_json,
        total_files=manifest.total_files,
        total_bytes=manifest.total_bytes,
        errors=errors,
    )
