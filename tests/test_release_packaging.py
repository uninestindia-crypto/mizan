"""Tests for QuantOS Slice 12: Reproducible Windows Release Packaging.

Covers:
1. PyInstaller packaging specifications (quant_system.spec, installer/quantos.spec).
2. Software Bill of Materials (SBOM) generation, parsing, and uv.lock cryptographic binding.
3. Cryptographic release manifest generation, sha256 checksums, and tamper detection.
4. Entrypoint invocations, pre-flight prerequisite checks, and drive-isolated storage sandboxing.
5. Clean installation staging, self-test verification, uninstallation, and 100% evidence preservation.
6. Installer configurations (Inno Setup ISS, Setup Wizard GUI).
7. Portable distribution ZIP archive roundtrip integrity.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from unittest.mock import patch

import pytest

from launcher import (
    configure_drive_isolation,
    find_free_port,
    run_prerequisite_checks,
)
from quant_system import __version__
from quant_system.release.builder import build_release
from quant_system.release.manifest import (
    generate_release_manifest,
    validate_release_bundle,
    write_release_manifest,
)
from quant_system.release.sbom import (
    compute_sha256,
    generate_sbom,
    parse_uv_lock,
    verify_sbom,
    write_sbom,
)
from quant_system.release.verifier import (
    assert_evidence_preserved,
    create_mock_evidence_store,
    simulate_uninstallation,
    verify_clean_release,
)


@pytest.fixture
def project_root() -> Path:
    return Path(__file__).parent.parent.resolve()


@pytest.fixture
def temp_workspace(tmp_path: Path) -> Path:
    workspace = tmp_path / "release_test_ws"
    workspace.mkdir(parents=True, exist_ok=True)
    return workspace


# ==============================================================================
# 1. PyInstaller Specification Tests
# ==============================================================================


@pytest.mark.parametrize(
    "rel_spec_path",
    [
        "quant_system.spec",
        "installer/quantos.spec",
    ],
)
def test_spec_files_exist_and_contain_required_configurations(
    project_root: Path, rel_spec_path: str
) -> None:
    """Verifies that PyInstaller spec files exist and specify correct entries and assets."""
    spec_file = project_root / rel_spec_path
    assert spec_file.exists(), f"Spec file missing: {spec_file}"
    content = spec_file.read_text(encoding="utf-8")

    # Must target launcher.py
    assert "launcher.py" in content
    # Must bundle static UI assets and configs
    assert "quant_system/server/static" in content or "static" in content
    assert "configs" in content
    # Must include critical hidden imports
    assert "uvicorn" in content
    assert "fastapi" in content
    assert "pydantic" in content
    assert "quant_system" in content
    assert "quant_system.release" in content
    # Must specify target binary name
    assert "quantos" in content or "QuantOS" in content


# ==============================================================================
# 2. SBOM Generation and uv.lock Binding Tests
# ==============================================================================


def test_parse_uv_lock_extracts_packages(project_root: Path) -> None:
    """Verifies that uv.lock is parsed into structured package dependencies."""
    lock_path = project_root / "uv.lock"
    assert lock_path.exists()

    packages = parse_uv_lock(lock_path)
    assert len(packages) > 0

    pkg_names = {p.name.lower() for p in packages}
    assert {"fastapi", "uvicorn", "pydantic", "numpy", "scipy", "pyyaml"}.issubset(pkg_names)

    # Verify all packages have valid name, version, and source
    assert all(p.name and p.version and p.source for p in packages)


def test_generate_and_verify_sbom(project_root: Path, temp_workspace: Path) -> None:
    """Verifies SBOM generation, JSON serialization, and cryptographic verification."""
    lock_path = project_root / "uv.lock"
    assert lock_path.exists()

    sbom = generate_sbom(
        lock_path=lock_path,
        repo_root=project_root,
        target_platform="windows-x64",
    )

    assert sbom["sbom_schema_version"] == "1.0.0"
    assert sbom["application"] == "QuantOS"
    assert sbom["version"] == __version__
    assert sbom["target_platform"] == "windows-x64"
    assert len(sbom["git_commit_sha"]) >= 7
    assert len(sbom["uv_lock_sha256"]) == 64
    assert sbom["total_packages"] > 0
    assert len(sbom["packages"]) == sbom["total_packages"]

    # Write SBOM to disk
    sbom_file = temp_workspace / "sbom.json"
    written_path = write_sbom(sbom, sbom_file)
    assert written_path.exists()

    # Verify written SBOM against lock file
    with open(written_path, encoding="utf-8") as f:
        loaded_sbom = json.load(f)

    is_valid, msg = verify_sbom(loaded_sbom, lock_path)
    assert is_valid is True
    assert "matches" in msg.lower()


def test_sbom_tamper_detection(project_root: Path) -> None:
    """Verifies that tampering with the lock hash or package count in SBOM fails verification."""
    lock_path = project_root / "uv.lock"
    sbom = generate_sbom(lock_path=lock_path, repo_root=project_root)

    # 1. Tampered lock hash
    tampered_hash_sbom = dict(sbom)
    tampered_hash_sbom["uv_lock_sha256"] = "0" * 64
    is_valid, msg = verify_sbom(tampered_hash_sbom, lock_path)
    assert is_valid is False
    assert "mismatch" in msg.lower()

    # 2. Tampered package count
    tampered_count_sbom = dict(sbom)
    tampered_count_sbom["total_packages"] = 9999
    is_valid, msg = verify_sbom(tampered_count_sbom, lock_path)
    assert is_valid is False
    assert "mismatch" in msg.lower()


# ==============================================================================
# 3. Release Manifest Generation and Validation Tests
# ==============================================================================


def test_release_manifest_generation_and_validation(temp_workspace: Path) -> None:
    """Verifies manifest creation, sha256 calculation, and cryptographic validation."""
    bundle_dir = temp_workspace / "sample_bundle"
    bundle_dir.mkdir(parents=True, exist_ok=True)

    # Create sample bundle files
    (bundle_dir / "quantos.exe").write_bytes(b"MOCK_EXECUTABLE_BINARY_DATA_X64")
    (bundle_dir / "config.json").write_text('{"mode": "governed"}', encoding="utf-8")
    sub_dir = bundle_dir / "static"
    sub_dir.mkdir(parents=True, exist_ok=True)
    (sub_dir / "index.html").write_text("<html><body>QuantOS</body></html>", encoding="utf-8")

    git_sha = "abc1234567890"
    lock_sha = "def9876543210"

    manifest = generate_release_manifest(
        bundle_dir=bundle_dir,
        git_commit_sha=git_sha,
        uv_lock_sha256=lock_sha,
        version="1.0.0",
        executable_name="quantos.exe",
    )

    assert manifest.app_name == "QuantOS"
    assert manifest.version == "1.0.0"
    assert manifest.git_commit_sha == git_sha
    assert manifest.uv_lock_sha256 == lock_sha
    assert manifest.total_files == 3
    assert manifest.total_bytes > 0
    assert "quantos.exe" in manifest.files
    assert "static/index.html" in manifest.files

    # Write manifest files
    manifest_json, manifest_sha, release_json = write_release_manifest(bundle_dir, manifest)
    assert manifest_json.exists()
    assert manifest_sha.exists()
    assert release_json.exists()

    # Validate intact bundle
    res = validate_release_bundle(bundle_dir)
    assert res.is_valid is True
    assert res.total_checked == 3
    assert len(res.missing_files) == 0
    assert len(res.corrupted_files) == 0
    assert len(res.unmanifested_files) == 0


def test_release_manifest_detects_corrupted_or_missing_files(temp_workspace: Path) -> None:
    """Verifies that modified bytes or deleted files are immediately flagged by validator."""
    bundle_dir = temp_workspace / "tampered_bundle"
    bundle_dir.mkdir(parents=True, exist_ok=True)

    file1 = bundle_dir / "quantos.exe"
    file2 = bundle_dir / "data.bin"
    file1.write_bytes(b"ORIGINAL_BINARY_BYTES")
    file2.write_bytes(b"DATA_PAYLOAD")

    manifest = generate_release_manifest(
        bundle_dir=bundle_dir,
        git_commit_sha="1234567",
        uv_lock_sha256="7654321",
        version="1.0.0",
    )
    write_release_manifest(bundle_dir, manifest)

    # Corrupt file1
    file1.write_bytes(b"TAMPERED_INJECTED_BYTES")
    res = validate_release_bundle(bundle_dir)
    assert res.is_valid is False
    assert any("quantos.exe" in c for c in res.corrupted_files)

    # Restore file1, delete file2
    file1.write_bytes(b"ORIGINAL_BINARY_BYTES")
    file2.unlink()
    res = validate_release_bundle(bundle_dir)
    assert res.is_valid is False
    assert "data.bin" in res.missing_files

    # Add unmanifested file
    file2.write_bytes(b"DATA_PAYLOAD")
    extra_file = bundle_dir / "unauthorized_payload.exe"
    extra_file.write_bytes(b"MALICIOUS")
    res = validate_release_bundle(bundle_dir, allow_unmanifested=False)
    assert res.is_valid is False
    assert "unauthorized_payload.exe" in res.unmanifested_files


# ==============================================================================
# 4. Entrypoint and Pre-flight Self-Test Diagnostics Tests
# ==============================================================================


def test_run_prerequisite_checks() -> None:
    """Verifies that all pre-flight startup prerequisite checks execute and report pass."""
    passed, logs = run_prerequisite_checks()
    assert passed is True
    assert len(logs) >= 5

    log_text = "\n".join(logs)
    assert "Drive-Isolated Storage Sandbox" in log_text
    assert "Architecture Verified" in log_text or "environment detected" in log_text
    assert "Local Loopback Socket Binding" in log_text
    assert "Decimal Double-Entry Ledger Invariant Check OK" in log_text
    assert "Quantitative Alpha & Black-Scholes Engine OK" in log_text


def test_drive_isolation_configuration(
    temp_workspace: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Verifies that configure_drive_isolation creates subdirectories and routes TEMP env."""
    orig_temp = os.environ.get("TEMP")
    orig_tmp = os.environ.get("TMP")
    orig_tmpdir = os.environ.get("TMPDIR")

    try:
        with patch("launcher.__file__", str(temp_workspace / "launcher.py")):
            app_root = configure_drive_isolation()
            assert app_root == temp_workspace
            assert (temp_workspace / "tmp").exists()
            assert (temp_workspace / "data").exists()
            assert (temp_workspace / "logs").exists()

            assert os.environ["TEMP"] == str(temp_workspace / "tmp")
            assert os.environ["TMP"] == str(temp_workspace / "tmp")
            assert os.environ["TMPDIR"] == str(temp_workspace / "tmp")
    finally:
        if orig_temp is not None:
            os.environ["TEMP"] = orig_temp
        if orig_tmp is not None:
            os.environ["TMP"] = orig_tmp
        if orig_tmpdir is not None:
            os.environ["TMPDIR"] = orig_tmpdir


def test_find_free_port() -> None:
    """Verifies loopback free port discovery."""
    port = find_free_port(9000)
    assert 9000 <= port < 9050


# ==============================================================================
# 5. Clean Installation, Self-Test, and Evidence Preservation Tests
# ==============================================================================


def test_clean_release_verification_journey(project_root: Path, temp_workspace: Path) -> None:
    """Executes the complete clean release staging, self-test, and evidence preservation pipeline."""
    bundle_dir = temp_workspace / "dist_bundle"
    bundle_dir.mkdir(parents=True, exist_ok=True)

    # Populate bundle with mock files including static assets and manifests
    (bundle_dir / "quantos.exe").write_bytes(b"STANDALONE_QUANTOS_EXE_MOCK")
    (bundle_dir / "configs").mkdir(parents=True, exist_ok=True)
    (bundle_dir / "configs" / "settings.json").write_text('{"env": "prod"}', encoding="utf-8")

    lock_path = project_root / "uv.lock"
    sbom = generate_sbom(lock_path=lock_path, repo_root=project_root)
    write_sbom(sbom, bundle_dir / "sbom.json")

    manifest = generate_release_manifest(
        bundle_dir=bundle_dir,
        git_commit_sha="test_git_sha_123",
        uv_lock_sha256=compute_sha256(lock_path),
        version=__version__,
    )
    write_release_manifest(bundle_dir, manifest)

    staging_dir = temp_workspace / "staging_install"
    evidence_dir = temp_workspace / "evidence_store"

    # Run clean release verification engine
    report = verify_clean_release(
        bundle_dir=bundle_dir,
        install_staging_dir=staging_dir,
        evidence_dir=evidence_dir,
        lock_path=lock_path,
    )

    assert report.all_passed is True
    assert report.failed_steps == 0
    assert report.passed_steps == report.total_steps
    assert report.total_steps == 9

    # Verify that evidence store is fully populated and undamaged
    assert (evidence_dir / "datasets" / "dataset_manifest.json").exists()
    assert (evidence_dir / "trials" / "trial_001.json").exists()
    assert (evidence_dir / "models" / "model_001.json").exists()


def test_evidence_preservation_fails_on_corruption(temp_workspace: Path) -> None:
    """Verifies that any modification to user evidence is caught with 100% sensitivity."""
    evidence_dir = temp_workspace / "test_evidence"
    hashes = create_mock_evidence_store(evidence_dir)

    # Uncorrupted check
    ok, msg = assert_evidence_preserved(evidence_dir, hashes)
    assert ok is True

    # Inject corruption into trial evidence
    trial_file = evidence_dir / "trials" / "trial_001.json"
    trial_file.write_text('{"tampered": true}', encoding="utf-8")

    corrupted_ok, corrupted_msg = assert_evidence_preserved(evidence_dir, hashes)
    assert corrupted_ok is False
    assert "corrupted" in corrupted_msg.lower()


def test_simulate_uninstallation_removes_binaries_only(temp_workspace: Path) -> None:
    """Verifies that uninstallation removes application binaries but preserves user data."""
    install_dir = temp_workspace / "installed_app"
    install_dir.mkdir(parents=True, exist_ok=True)

    # App files
    (install_dir / "quantos.exe").write_bytes(b"EXE")
    (install_dir / "quant_system").mkdir(parents=True, exist_ok=True)
    (install_dir / "quant_system" / "core.py").write_text("code", encoding="utf-8")

    # User data directory inside or alongside
    user_data = install_dir / "user_data"
    user_data.mkdir(parents=True, exist_ok=True)
    (user_data / "portfolio.json").write_text("{}", encoding="utf-8")

    simulate_uninstallation(install_dir, preserve_paths=[user_data])

    assert not (install_dir / "quantos.exe").exists()
    assert not (install_dir / "quant_system").exists()
    assert user_data.exists()
    assert (user_data / "portfolio.json").exists()


# ==============================================================================
# 6. Release Builder End-to-End Test (Skip PyInstaller subprocess)
# ==============================================================================


def test_release_builder_workflow(project_root: Path, temp_workspace: Path) -> None:
    """Verifies release builder orchestration including SBOM, manifest, and portable zip."""
    dist_dir = temp_workspace / "dist"
    bundle_dir = dist_dir / "quantos"
    bundle_dir.mkdir(parents=True, exist_ok=True)

    # Mock bundle content
    (bundle_dir / "quantos.exe").write_bytes(b"QUANTOS_EXE_MOCK_PAYLOAD")
    (bundle_dir / "README.txt").write_text("QuantOS Readme", encoding="utf-8")

    result = build_release(
        project_root=project_root,
        output_dir=dist_dir,
        run_pyinstaller=False,
    )

    assert result.success is True
    assert result.version == __version__
    assert result.total_files >= 2
    assert result.total_bytes > 0
    assert result.sbom_file.exists()
    assert result.manifest_file.exists()
    assert result.zip_archive is not None
    assert result.zip_archive.exists()

    # Verify portable zip contains expected entries
    import zipfile

    with zipfile.ZipFile(result.zip_archive, "r") as zf:
        namelist = zf.namelist()
        assert any("quantos.exe" in n for n in namelist)
        assert any("release-manifest.json" in n for n in namelist)
        assert any("sbom.json" in n for n in namelist)


# ==============================================================================
# 7. Installer Configurations and Scripts Tests
# ==============================================================================


def test_inno_setup_iss_configuration(project_root: Path) -> None:
    """Verifies that Inno Setup ISS file is configured for x64 standalone packaging."""
    iss_path = project_root / "installer" / "quant_os_setup.iss"
    assert iss_path.exists()

    content = iss_path.read_text(encoding="utf-8")
    assert 'MyAppName "QuantOS"' in content or 'MyAppName "Mizan Quant OS"' in content
    assert "ArchitecturesInstallIn64BitMode=x64compatible" in content
    assert "quantos.exe" in content or "QuantOS.exe" in content
    assert "PrivilegesRequired=lowest" in content


def test_setup_gui_components(project_root: Path, temp_workspace: Path) -> None:
    """Verifies that setup_gui.py helper functions operate safely."""
    pytest.importorskip("tkinter", reason="the setup window needs Tk, which headless Linux lacks")
    from installer.setup_gui import get_available_drives, get_free_space_gb

    drives = get_available_drives()
    assert isinstance(drives, list)
    if os.name == "nt":
        assert len(drives) > 0

    free_gb = get_free_space_gb(str(temp_workspace))
    assert free_gb >= 0.0


def test_quantos_spec_multi_binary_configuration(project_root: Path) -> None:
    """Verifies that installer/quantos.spec packages both quantos and quantos-studio."""
    spec_path = project_root / "installer" / "quantos.spec"
    assert spec_path.exists()
    content = spec_path.read_text(encoding="utf-8")
    assert "launcher.py" in content
    assert "quantos_studio.py" in content
    assert "quantos-studio" in content
    assert "console=False" in content
    assert "exe_studio" in content


def test_setup_gui_studio_shortcut_and_uninstaller_contract(project_root: Path) -> None:
    """Verifies that setup_gui.py targets Desktop Studio and safe evidence uninstallation."""
    setup_gui_path = project_root / "installer" / "setup_gui.py"
    assert setup_gui_path.exists()
    content = setup_gui_path.read_text(encoding="utf-8")
    assert "QuantOS Studio.lnk" in content
    assert "quantos-studio.exe" in content
    assert "uninstall.bat" in content
    assert "quantos-studio.exe" in content
    # Ensures evidence is preserved in data/ and logs/
    assert "User datasets, evidence, and logs in data/ and logs/ will be preserved" in content


def test_setup_installer_spec_configuration(project_root: Path) -> None:
    """Verifies that setup_installer.spec builds QuantOS_v1.0.0_Setup."""
    spec_path = project_root / "installer" / "setup_installer.spec"
    assert spec_path.exists()
    content = spec_path.read_text(encoding="utf-8")
    assert "setup_gui.py" in content
    assert "QuantOS_v1.0.0_Setup" in content
    assert "console=False" in content
