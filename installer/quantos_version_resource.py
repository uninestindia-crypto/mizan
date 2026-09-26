"""Windows version resource shared by the QuantOS PyInstaller specs.

Every shipped executable carries the same company, product name and version in
Properties -> Details. The version is read from ``quant_system.__version__`` so the
file properties cannot drift from the package that was built.
"""

from __future__ import annotations

import re
from pathlib import Path

from PyInstaller.utils.win32.versioninfo import (
    FixedFileInfo,
    StringFileInfo,
    StringStruct,
    StringTable,
    VarFileInfo,
    VarStruct,
    VSVersionInfo,
)

COMPANY_NAME = "QuantOS Quantitative Technologies"
PRODUCT_NAME = "QuantOS"

_PACKAGE_INIT = Path(__file__).resolve().parent.parent / "src" / "quant_system" / "__init__.py"
_US_ENGLISH_UNICODE = "040904B0"


def read_package_version(init_path: Path = _PACKAGE_INIT) -> str:
    """Return ``__version__`` from the package without importing it."""
    text = init_path.read_text(encoding="utf-8")
    match = re.search(r'^__version__\s*=\s*"([^"]+)"', text, re.MULTILINE)
    if match is None:
        raise RuntimeError(f"__version__ not found in {init_path}")
    return match.group(1)


def numeric_version(version: str) -> tuple[int, int, int, int]:
    """Map ``1.2.3`` or ``1.2.3rc1`` onto the four integers a PE version field holds."""
    parts = [int(part) for part in re.findall(r"\d+", version)[:4]]
    parts += [0] * (4 - len(parts))
    return parts[0], parts[1], parts[2], parts[3]


def build_version_info(file_description: str, original_filename: str) -> VSVersionInfo:
    """Build the version resource for one executable."""
    version = read_package_version()
    numbers = numeric_version(version)
    return VSVersionInfo(
        ffi=FixedFileInfo(filevers=numbers, prodvers=numbers),
        kids=[
            StringFileInfo(
                [
                    StringTable(
                        _US_ENGLISH_UNICODE,
                        [
                            StringStruct("CompanyName", COMPANY_NAME),
                            StringStruct("FileDescription", file_description),
                            StringStruct("FileVersion", version),
                            StringStruct("InternalName", Path(original_filename).stem),
                            StringStruct("LegalCopyright", f"Copyright (C) {COMPANY_NAME}"),
                            StringStruct("OriginalFilename", original_filename),
                            StringStruct("ProductName", PRODUCT_NAME),
                            StringStruct("ProductVersion", version),
                        ],
                    )
                ]
            ),
            VarFileInfo([VarStruct("Translation", [0x0409, 1200])]),
        ],
    )
