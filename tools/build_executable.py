"""Build script for TKS Engine 2.0 standalone Windows executable.

Uses PyInstaller to bundle Python runtime, PyQt6, Playwright drivers,
QtAwesome fonts, brand assets, and configuration into a standalone distribution.
"""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

import playwright
import qtawesome


def build() -> None:
    root = Path(__file__).resolve().parent.parent
    dist_dir = root / "dist"
    build_dir = root / "build"
    assets_dir = root / "assets"
    icon_ico = assets_dir / "tks_engine.ico"

    print("=" * 60)
    print("TKS ENGINE 2.0 — STANDALONE WINDOWS BUILD")
    print("=" * 60)

    # 1. Identify Playwright driver & QtAwesome font directories
    playwright_dir = Path(playwright.__file__).parent / "driver"
    qtawesome_fonts = Path(qtawesome.__file__).parent / "fonts"

    print(f"Playwright Driver: {playwright_dir}")
    print(f"QtAwesome Fonts:   {qtawesome_fonts}")
    print(f"Icon Path:         {icon_ico}")

    # 2. Write custom tks_engine.spec
    spec_content = f"""# -*- mode: python ; coding: utf-8 -*-
from PyInstaller.utils.hooks import collect_data_files, collect_submodules

block_cipher = None

added_files = [
    (r'{assets_dir}', 'assets'),
    (r'{root / "config.json"}', '.'),
    (r'{playwright_dir}', 'playwright/driver'),
    (r'{qtawesome_fonts}', 'qtawesome/fonts'),
]

hidden_modules = [
    'PyQt6',
    'PyQt6.QtCore',
    'PyQt6.QtGui',
    'PyQt6.QtWidgets',
    'playwright',
    'playwright.sync_api',
    'qtawesome',
    'PIL',
    'PIL.Image',
    'sqlite3',
    'ctypes',
    'json',
    'pathlib',
    'logging',
    'hashlib',
    'shutil',
    'subprocess',
] + collect_submodules('playwright')

a = Analysis(
    [r'{root / "main.py"}'],
    pathex=[r'{root}'],
    binaries=[],
    datas=added_files,
    hiddenimports=hidden_modules,
    hookspath=[],
    hooksconfig={{}},
    runtime_hooks=[],
    excludes=['tkinter', 'matplotlib', 'scipy', 'numpy', 'IPython'],
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
    name='TKS_Engine',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=r'{icon_ico}',
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name='TKS_Engine',
)
"""
    spec_file = root / "tks_engine.spec"
    spec_file.write_text(spec_content, encoding="utf-8")
    print(f"Wrote PyInstaller spec: {spec_file}")

    # 3. Clean prior dist/build
    target_app_dir = dist_dir / "TKS_Engine"
    if target_app_dir.exists():
        print(f"Cleaning previous dist at {target_app_dir}...")
        try:
            shutil.rmtree(target_app_dir)
        except Exception as e:
            print(f"Warning cleaning dist: {e}")

    # 4. Run PyInstaller
    cmd = [sys.executable, "-m", "PyInstaller", "--noconfirm", str(spec_file)]
    print(f"Running command: {' '.join(cmd)}")
    result = subprocess.run(cmd, cwd=root)
    if result.returncode != 0:
        print("ERROR: PyInstaller build failed!")
        sys.exit(result.returncode)

    exe_output = target_app_dir / "TKS_Engine.exe"
    if not exe_output.exists():
        print(f"ERROR: Executable not found at {exe_output}")
        sys.exit(1)

    print("\n" + "=" * 60)
    print(f"SUCCESS: Standalone executable created at:")
    print(f"-> {exe_output}")
    print("=" * 60)


if __name__ == "__main__":
    build()
