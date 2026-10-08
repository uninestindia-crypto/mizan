# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller specification for QuantOS Standalone Windows x64 Executable (quantos.exe)."""

import sys
from pathlib import Path
from PyInstaller.utils.hooks import collect_data_files, collect_submodules

block_cipher = None

# Base directory paths
root_dir = Path(__file__).parent.parent if '__file__' in globals() else Path.cwd()

# Icon and Properties -> Details for every shipped exe (see quantos_version_resource.py)
sys.path.insert(0, SPECPATH)
from quantos_version_resource import build_version_info  # noqa: E402

app_icon = str(Path(SPECPATH) / 'assets' / 'quantos.ico')

# Static UI and configuration data assets
added_files = [
    (str(root_dir / 'src' / 'quant_system' / 'server' / 'static'), 'quant_system/server/static'),
    (str(root_dir / 'configs'), 'configs'),
    (str(root_dir / 'assets'), 'assets'),
    (str(root_dir / 'data' / 'shariah'), 'data/shariah'),
    (str(root_dir / 'data' / 'evidence' / 'models'), 'data/evidence/models'),
]

hidden_imports = [
    'uvicorn',
    'uvicorn.logging',
    'uvicorn.loops',
    'uvicorn.loops.auto',
    'uvicorn.protocols',
    'uvicorn.protocols.http',
    'uvicorn.protocols.http.auto',
    'uvicorn.protocols.websockets',
    'uvicorn.protocols.websockets.auto',
    'uvicorn.lifespans',
    'uvicorn.lifespans.on',
    'fastapi',
    'pydantic',
    'numpy',
    'scipy',
    'yaml',
    'tomllib',
    'webview',
    'webview.platforms.winforms',
    'quant_system',
    'quant_system.release',
] + collect_submodules('quant_system')

a = Analysis(
    ['../launcher.py'],
    pathex=['../src', '..'],
    binaries=[],
    datas=added_files,
    hiddenimports=hidden_imports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='quantos',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=app_icon,
    version=build_version_info('QuantOS command-line server', 'quantos.exe'),
)

a_studio = Analysis(
    ['../quantos_studio.py'],
    pathex=['../src', '..'],
    binaries=[],
    datas=added_files,
    hiddenimports=hidden_imports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz_studio = PYZ(a_studio.pure, a_studio.zipped_data, cipher=block_cipher)

exe_studio = EXE(
    pyz_studio,
    a_studio.scripts,
    [],
    exclude_binaries=True,
    name='quantos-studio',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,  # Windowed GUI application - NO black terminal window
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=app_icon,
    version=build_version_info('QuantOS', 'quantos-studio.exe'),
)

coll = COLLECT(
    exe,
    exe_studio,
    a.binaries,
    a.zipfiles,
    a.datas,
    a_studio.binaries,
    a_studio.zipfiles,
    a_studio.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='quantos',
)
