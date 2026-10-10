# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller specification for QuantOS Standalone Windows x64 Executable (quantos.exe)."""

import os
import sys
from pathlib import Path
from PyInstaller.utils.hooks import collect_all, collect_data_files, collect_submodules

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
    # The licences of the open-source code the product contains (Qlib's MIT notice must travel with it)
    (str(root_dir / 'THIRD_PARTY_NOTICES.md'), '.'),
    (str(root_dir / 'data' / 'shariah'), 'data/shariah'),
    (str(root_dir / 'data' / 'fundamentals'), 'data/fundamentals'),
    (str(root_dir / 'data' / 'authorities' / 'nse-all-listed-equities.csv'), 'data/authorities'),
    (str(root_dir / 'data' / 'authorities' / 'nse-trading-holidays.json'), 'data/authorities'),
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
] + collect_submodules('quant_system') + collect_submodules('websockets')

# The Research screen runs EmbeddingGemma 2 (the 8-bit build, downloaded from inside the app) through these two. onnxruntime ships
# native DLLs and both are loaded with importlib, so they are collected explicitly instead of trusting the import scan.
extra_datas, extra_binaries, extra_hidden = [], [], []
for _package in ('onnxruntime', 'tokenizers'):
    _datas, _binaries, _hidden = collect_all(_package)
    extra_datas += _datas
    extra_binaries += _binaries
    extra_hidden += _hidden

# onnxruntime needs the Microsoft C++ runtime. Windows 11 has it; an older Windows may not, so the app carries its own copy
# (the files Microsoft allows an app to ship), taken from this computer when the installer is built.
_system32 = Path(os.environ.get('SystemRoot', r'C:\Windows')) / 'System32'
for _name in ('msvcp140.dll', 'msvcp140_1.dll', 'vcruntime140_1.dll'):
    if (_system32 / _name).is_file():
        extra_binaries.append((str(_system32 / _name), '.'))

a = Analysis(
    ['../launcher.py'],
    pathex=['../src', '..'],
    binaries=extra_binaries,
    datas=added_files + extra_datas,
    hiddenimports=hidden_imports + extra_hidden,
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
    upx=False,
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
    binaries=extra_binaries,
    datas=added_files + extra_datas,
    hiddenimports=hidden_imports + extra_hidden,
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
    upx=False,
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
    upx=False,
    upx_exclude=[],
    name='quantos',
)
