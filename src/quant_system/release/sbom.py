"""Software Bill of Materials (SBOM) generator and validator for QuantOS."""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import tomllib
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from quant_system import __version__


@dataclass(frozen=True)
class PackageDependency:
    """Represents a single package in the locked dependency tree."""

    name: str
    version: str
    source: str
    hashes: list[str] = field(default_factory=list)
    dependencies: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class SBOMMetadata:
    """Standardized SBOM metadata structure bound to uv.lock and Git SHA."""

    sbom_schema_version: str
    application: str
    version: str
    git_commit_sha: str
    uv_lock_sha256: str
    generated_at: str
    target_platform: str
    total_packages: int
    packages: list[dict[str, Any]]


def compute_sha256(filepath: Path) -> str:
    """Computes SHA-256 hash of a file."""
    h = hashlib.sha256()
    with open(filepath, "rb") as f:
        while chunk := f.read(65536):
            h.update(chunk)
    return h.hexdigest()


def get_git_commit_sha(repo_root: Path | None = None) -> str:
    """Resolves Git commit SHA from repository, environment, or fallback."""
    env_sha = os.environ.get("RELEASE_GIT_SHA") or os.environ.get("GIT_COMMIT_SHA")
    if env_sha and len(env_sha.strip()) >= 7:
        return env_sha.strip()

    cwd = str(repo_root) if repo_root else os.getcwd()
    try:
        res = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=cwd,
            capture_output=True,
            text=True,
            check=False,
        )
        if res.returncode == 0 and res.stdout.strip():
            return res.stdout.strip()
    except Exception:
        pass

    return "unknown-git-revision"


def _resolve_pkg_source(source_info: Any) -> str:
    """Resolves package source string from uv.lock source definition."""
    if not isinstance(source_info, dict):
        return str(source_info)
    if "git" in source_info:
        return f"git+{source_info['git']}"
    if "editable" in source_info:
        return "editable"
    return str(source_info.get("registry", "unknown"))


def _extract_pkg_hashes(pkg: dict[str, Any]) -> list[str]:
    """Extracts cryptographic distribution hashes for a package."""
    hashes: list[str] = []
    sdist = pkg.get("sdist")
    if isinstance(sdist, dict) and "hash" in sdist:
        hashes.append(sdist["hash"])

    for whl in pkg.get("wheels", []):
        if isinstance(whl, dict) and "hash" in whl:
            hashes.append(whl["hash"])
    return hashes


def _extract_pkg_deps(pkg: dict[str, Any]) -> list[str]:
    """Extracts dependency names declared for a package."""
    deps: list[str] = []
    for dep in pkg.get("dependencies", []):
        if isinstance(dep, dict) and "name" in dep:
            deps.append(dep["name"])
        elif isinstance(dep, str):
            deps.append(dep)
    return deps


def _parse_single_package(pkg: dict[str, Any]) -> PackageDependency:
    """Parses an individual package dictionary from uv.lock."""
    return PackageDependency(
        name=pkg.get("name", ""),
        version=pkg.get("version", ""),
        source=_resolve_pkg_source(pkg.get("source", {})),
        hashes=_extract_pkg_hashes(pkg),
        dependencies=_extract_pkg_deps(pkg),
    )


def parse_uv_lock(lock_path: Path) -> list[PackageDependency]:
    """Parses uv.lock TOML file and extracts structured package information."""
    if not lock_path.exists():
        raise FileNotFoundError(f"uv.lock not found at: {lock_path}")

    with open(lock_path, "rb") as f:
        lock_data = tomllib.load(f)

    packages = [_parse_single_package(pkg) for pkg in lock_data.get("package", [])]
    packages.sort(key=lambda p: p.name.lower())
    return packages


def generate_sbom(
    lock_path: Path,
    repo_root: Path | None = None,
    target_platform: str = "windows-x64",
    app_version: str | None = None,
) -> dict[str, Any]:
    """Generates complete, deterministic SBOM data dictionary bound to uv.lock and Git SHA."""
    lock_sha = compute_sha256(lock_path)
    git_sha = get_git_commit_sha(repo_root)
    packages = parse_uv_lock(lock_path)
    version = app_version or __version__

    sbom_obj = SBOMMetadata(
        sbom_schema_version="1.0.0",
        application="QuantOS",
        version=version,
        git_commit_sha=git_sha,
        uv_lock_sha256=lock_sha,
        generated_at=datetime.now(UTC).isoformat(),
        target_platform=target_platform,
        total_packages=len(packages),
        packages=[asdict(p) for p in packages],
    )
    return asdict(sbom_obj)


def write_sbom(sbom_data: dict[str, Any], output_path: Path) -> Path:
    """Writes formatted SBOM JSON file to target path."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(sbom_data, f, indent=2, sort_keys=False)
    return output_path


def verify_sbom(sbom_data: dict[str, Any], lock_path: Path) -> tuple[bool, str]:
    """Verifies that an existing SBOM matches the provided uv.lock file."""
    if not lock_path.exists():
        return False, f"Lock file not found at: {lock_path}"

    current_lock_sha = compute_sha256(lock_path)
    recorded_lock_sha = sbom_data.get("uv_lock_sha256", "")

    if current_lock_sha != recorded_lock_sha:
        return (
            False,
            f"Lock hash mismatch: recorded {recorded_lock_sha} != actual {current_lock_sha}",
        )

    actual_packages = parse_uv_lock(lock_path)
    recorded_count = sbom_data.get("total_packages", 0)
    if len(actual_packages) != recorded_count:
        return (
            False,
            f"Package count mismatch: recorded {recorded_count} != actual {len(actual_packages)}",
        )

    return True, "SBOM matches uv.lock cryptographic identity."
