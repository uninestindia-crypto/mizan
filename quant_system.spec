# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller specification for QuantOS Desktop Application v1.0.0 (quantos.exe)."""

import sys
from pathlib import Path
from PyInstaller.utils.hooks import collect_data_files, collect_submodules

block_cipher = None

# Collect static assets and configs
added_files = [
    ('src/quant_system/server/static', 'quant_system/server/static'),
    ('configs', 'configs'),
    ('THIRD_PARTY_NOTICES.md', '.'),
    ('data/shariah', 'data/shariah'),
    ('data/fundamentals', 'data/fundamentals'),
    ('data/authorities/nse-all-listed-equities.csv', 'data/authorities'),
    ('data/authorities/nse-trading-holidays.json', 'data/authorities'),
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
    'quant_system',
    'quant_system.release',
] + collect_submodules('quant_system') + collect_submodules('websockets')

a = Analysis(
    ['launcher.py'],
    pathex=['src', '.'],
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
    upx=False,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

a_studio = Analysis(
    ['quantos_studio.py'],
    pathex=['src', '.'],
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
    upx=False,
    console=False,  # Windowed GUI application - NO black terminal window
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
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
