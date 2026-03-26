# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec for TextGenius.

Uses --onedir (not --onefile) to avoid antivirus false positives.
UPX is disabled because packed binaries trigger malware heuristics.
"""

import sys
from pathlib import Path

block_cipher = None
project_root = Path(SPECPATH).parent

a = Analysis(
    [str(project_root / 'main.py')],
    pathex=[str(project_root)],
    binaries=[],
    datas=[
        # App assets
        (str(project_root / 'assets' / 'icon.ico'), 'assets'),
        (str(project_root / 'assets' / 'icon.png'), 'assets'),
        # CustomTkinter needs its data files
    ],
    hiddenimports=[
        'pynput.keyboard._win32',
        'pynput.mouse._win32',
        'customtkinter',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    cipher=block_cipher,
)

pyz = PYZ(a.pure, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],                    # empty = onedir mode
    exclude_binaries=True,
    name='TextGenius',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,             # UPX triggers antivirus
    console=False,         # windowed GUI app
    icon=str(project_root / 'assets' / 'icon.ico'),
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,             # UPX off here too
    name='TextGenius',
)
