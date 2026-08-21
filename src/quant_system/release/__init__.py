"""QuantOS Release Packaging, SBOM Generation, and Integrity Verification Subsystem."""

from quant_system.release.builder import BuildResult, build_release
from quant_system.release.manifest import (
    FileChecksum,
    ManifestValidationResult,
    ReleaseManifest,
    compute_file_sha256,
    generate_release_manifest,
    validate_release_bundle,
    write_release_manifest,
)
from quant_system.release.sbom import (
    PackageDependency,
    SBOMMetadata,
    compute_sha256,
    generate_sbom,
    get_git_commit_sha,
    parse_uv_lock,
    verify_sbom,
    write_sbom,
)
from quant_system.release.verifier import (
    CleanReleaseVerificationReport,
    VerificationStepResult,
    assert_evidence_preserved,
    create_mock_evidence_store,
    simulate_uninstallation,
    stage_clean_install,
    verify_clean_release,
)

__all__ = [
    "BuildResult",
    "CleanReleaseVerificationReport",
    "FileChecksum",
    "ManifestValidationResult",
    "PackageDependency",
    "ReleaseManifest",
    "SBOMMetadata",
    "VerificationStepResult",
    "assert_evidence_preserved",
    "build_release",
    "compute_file_sha256",
    "compute_sha256",
    "create_mock_evidence_store",
    "generate_release_manifest",
    "generate_sbom",
    "get_git_commit_sha",
    "parse_uv_lock",
    "simulate_uninstallation",
    "stage_clean_install",
    "validate_release_bundle",
    "verify_clean_release",
    "verify_sbom",
    "write_release_manifest",
    "write_sbom",
]
