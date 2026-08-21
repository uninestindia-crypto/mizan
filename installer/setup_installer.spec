# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec to build standalone single-file installer: QuantOS_v1.0.0_Setup.exe."""

import sys
from pathlib import Path

block_cipher = None

# Bundle compiled QuantOS distribution directory into the Setup executable
dist_dir = Path('../dist').resolve()
source_bundle = '../dist/quantos' if (dist_dir / 'quantos').exists() else '../dist/QuantOS'

added_files = [
    (source_bundle, 'quantos'),
]

a = Analysis(
    ['setup_gui.py'],
    pathex=['..', '.'],
    binaries=[],
    datas=added_files,
    hiddenimports=['tkinter', 'tkinter.ttk', 'tkinter.filedialog', 'tkinter.messagebox'],
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
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='QuantOS_v1.0.0_Setup',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
