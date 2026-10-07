"""Static guarantees for the Windows installer (Inno Setup) and the exe version resource.

Compiling the installer needs Inno Setup, which CI does not have, so these tests pin the
properties that make it a first-party-grade installer at the source level.
"""

from __future__ import annotations

import re
import struct
import sys
from pathlib import Path

import pytest

import quant_system

PROJECT_ROOT = Path(__file__).resolve().parent.parent
INSTALLER_DIR = PROJECT_ROOT / "installer"
ISS_PATH = INSTALLER_DIR / "quant_os_setup.iss"

# The version resource is built with PyInstaller's Windows helper, which needs `pefile`, a
# dependency that only installs on Windows. Without it this module cannot even be collected.
pytest.importorskip("pefile", reason="exe version resources are a Windows build step")
sys.path.insert(0, str(INSTALLER_DIR))
from quantos_version_resource import (  # noqa: E402
    COMPANY_NAME,
    PRODUCT_NAME,
    build_version_info,
    numeric_version,
    read_package_version,
)


@pytest.fixture(scope="module")
def iss() -> str:
    return ISS_PATH.read_text(encoding="utf-8")


def _setup_directive(iss: str, name: str) -> str:
    match = re.search(rf"^{name}=(.*)$", iss, re.MULTILINE)
    assert match is not None, f"{name} missing from [Setup]"
    return match.group(1).strip()


def test_installer_keeps_stable_app_id_for_upgrades(iss: str) -> None:
    # Changing AppId would make every upgrade a second, parallel install.
    assert _setup_directive(iss, "AppId") == "{{D6F9A5A4-9E3B-4C67-B44E-626F7C8A9B1C}"


def test_installer_is_per_user_without_admin_prompt(iss: str) -> None:
    assert _setup_directive(iss, "PrivilegesRequired") == "lowest"


def test_installer_uses_native_windows11_style_following_system_theme(iss: str) -> None:
    style = _setup_directive(iss, "WizardStyle").split()
    assert {"modern", "dynamic", "windows11"} <= set(style)
    assert re.search(r"#if Ver < EncodeVer\(6, 7, 0\)", iss)


def test_installer_branding_assets_exist(iss: str) -> None:
    for directive in ("SetupIconFile", "WizardImageFile", "WizardSmallImageFile"):
        for relative in _setup_directive(iss, directive).split(","):
            assert (INSTALLER_DIR / relative).is_file(), relative


def test_installer_requires_eula_and_terms_acceptance(iss: str) -> None:
    license_file = _setup_directive(iss, "LicenseFile")
    assert license_file == r"assets\LICENSE.txt"
    license_path = INSTALLER_DIR / license_file
    assert license_path.is_file()
    text = license_path.read_text(encoding="utf-8")
    assert "END USER LICENSE AGREEMENT" in text
    assert "NOT INVESTMENT ADVICE" in text
    assert "MIZAN SHARIAH" in text
    assert "LIMITATION OF LIABILITY" in text


def test_installer_checks_and_provisions_webview2_prerequisite(iss: str) -> None:
    code = iss.split("[Code]", 1)[1]
    assert "WEBVIEW2_GUID = '{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}'" in code
    assert "MicrosoftEdgeWebview2Setup.exe" in code
    assert "IsWebView2Installed" in code
    assert "CreateDownloadPage" in code
    assert "PrepareToInstall" in code


def test_installer_registers_start_menu_and_real_desktop(iss: str) -> None:
    # {autoprograms}/{autodesktop} resolve through the shell, so a OneDrive-redirected
    # desktop gets the shortcut instead of the unused %USERPROFILE%\Desktop folder.
    assert re.search(r'^Name: "\{autoprograms\}\\\{#MyAppName\}"', iss, re.MULTILINE)
    assert re.search(r'^Name: "\{autodesktop\}\\\{#MyAppName\}"', iss, re.MULTILINE)
    assert '#define MyAppExeName "quantos-studio.exe"' in iss


def test_installer_closes_running_app_and_logs(iss: str) -> None:
    assert _setup_directive(iss, "CloseApplications") == "yes"
    assert _setup_directive(iss, "SetupLogging") == "yes"


def test_uninstall_preserves_research_data_and_evidence(iss: str) -> None:
    assert re.search(r'^Name: "\{app\}\\data"; Flags: uninsneveruninstall$', iss, re.MULTILINE)
    assert re.search(r'^Name: "\{app\}\\logs"; Flags: uninsneveruninstall$', iss, re.MULTILINE)
    uninstall_section = iss.split("[UninstallDelete]", 1)[1].split("[Code]", 1)[0]
    entries = [line for line in uninstall_section.splitlines() if line.startswith("Type:")]
    assert entries == ['Type: filesandordirs; Name: "{app}\\tmp"']


def test_default_folder_skips_removable_and_network_drives(iss: str) -> None:
    assert _setup_directive(iss, "DefaultDirName") == "{code:DefaultInstallDir}"
    code = iss.split("[Code]", 1)[1]
    assert "DRIVE_FIXED = 3" in code
    assert "GetDriveType(Root) = DRIVE_FIXED" in code
    assert "ExpandConstant('{autopf}\\{#MyAppName}')" in code


def test_legacy_batch_uninstaller_is_removed_on_install(iss: str) -> None:
    install_delete = iss.split("[InstallDelete]", 1)[1].split("[Files]", 1)[0]
    assert '"{app}\\uninstall.bat"' in install_delete


def test_installer_version_is_derived_not_typed(iss: str) -> None:
    assert "GetFileProductVersion(StudioExe)" in iss
    assert "OutputBaseFilename=QuantOS_v{#MyAppVersion}_Setup" in iss
    assert not re.search(r'#define MyAppVersion "\d', iss)


def test_release_build_compiles_inno_installer_not_tk_wizard() -> None:
    release = (PROJECT_ROOT / "scripts" / "build-windows-release.ps1").read_text(encoding="utf-8")
    assert "build-windows-installer.ps1" in release
    assert "setup_installer.spec" not in release
    installer = (PROJECT_ROOT / "scripts" / "build-windows-installer.ps1").read_text(
        encoding="utf-8"
    )
    assert "quant_os_setup.iss" in installer
    assert "/DSignToolName=quantos" in installer


def test_release_builds_the_web_interface_into_the_folder_the_app_bundles() -> None:
    release = (PROJECT_ROOT / "scripts" / "build-windows-release.ps1").read_text(encoding="utf-8")
    assert "npm run build" in release
    assert r"src\quant_system\server\static\app\index.html" in release
    # The build fails closed rather than packaging an app with no interface.
    assert "The web interface is not built" in release

    vite = (PROJECT_ROOT / "frontend" / "vite.config.ts").read_text(encoding="utf-8")
    assert "../src/quant_system/server/static/app" in vite
    assert "assetsInlineLimit: 0" in vite  # the server CSP allows no data: fonts

    spec = (INSTALLER_DIR / "quantos.spec").read_text(encoding="utf-8")
    assert (
        "'src' / 'quant_system' / 'server' / 'static'" in spec
    )  # bundles static/, hence static/app

    ignore = (PROJECT_ROOT / "src" / "quant_system" / "server" / "static" / ".gitignore").read_text(
        encoding="utf-8"
    )
    assert "/app/" in ignore  # build output is never committed


def test_built_interface_has_no_inline_scripts_when_present() -> None:
    index = PROJECT_ROOT / "src" / "quant_system" / "server" / "static" / "app" / "index.html"
    if not index.is_file():
        pytest.skip("frontend not built in this checkout")
    html = index.read_text(encoding="utf-8")
    # script-src 'self': an inline <script> body would be blocked and the app would never start.
    assert not re.search(r"<script(?![^>]*\bsrc=)[^>]*>\s*\S", html)
    assert "fonts.googleapis.com" not in html


def test_icon_file_holds_all_standard_sizes() -> None:
    data = (INSTALLER_DIR / "assets" / "quantos.ico").read_bytes()
    reserved, kind, count = struct.unpack_from("<HHH", data, 0)
    assert (reserved, kind) == (0, 1)
    sizes = set()
    for index in range(count):
        width, _height, _colors, _res, _planes, _bpp, length, offset = struct.unpack_from(
            "<BBBBHHII", data, 6 + 16 * index
        )
        sizes.add(256 if width == 0 else width)
        assert data[offset : offset + 8] == b"\x89PNG\r\n\x1a\n"
        assert offset + length <= len(data)
    assert {16, 24, 32, 48, 256} <= sizes


def test_both_app_exes_get_icon_and_version_resource() -> None:
    spec = (INSTALLER_DIR / "quantos.spec").read_text(encoding="utf-8")
    assert spec.count("icon=app_icon") == 2
    assert "build_version_info('QuantOS command-line server', 'quantos.exe')" in spec
    assert "build_version_info('QuantOS', 'quantos-studio.exe')" in spec


def test_version_resource_matches_package_version() -> None:
    assert read_package_version() == quant_system.__version__


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("1.0.0", (1, 0, 0, 0)),
        ("2.3.4.5", (2, 3, 4, 5)),
        ("1.2.0rc1", (1, 2, 0, 1)),
        ("7", (7, 0, 0, 0)),
    ],
)
def test_numeric_version(text: str, expected: tuple[int, int, int, int]) -> None:
    assert numeric_version(text) == expected


def test_version_info_strings() -> None:
    info = build_version_info("QuantOS", "quantos-studio.exe")
    strings = {entry.name: entry.val for entry in info.kids[0].kids[0].kids}
    assert strings["CompanyName"] == COMPANY_NAME
    assert strings["ProductName"] == PRODUCT_NAME
    assert strings["ProductVersion"] == quant_system.__version__
    assert strings["OriginalFilename"] == "quantos-studio.exe"
    assert strings["InternalName"] == "quantos-studio"
    assert info.ffi.fileVersionMS >> 16 == numeric_version(quant_system.__version__)[0]


def test_read_package_version_fails_closed(tmp_path: Path) -> None:
    init = tmp_path / "__init__.py"
    init.write_text("VERSION = 1\n", encoding="utf-8")
    with pytest.raises(RuntimeError, match="__version__ not found"):
        read_package_version(init)
