# -*- mode: python ; coding: utf-8 -*-

from pathlib import Path


project_root = Path.cwd()
entry_point = project_root / "macos" / "ootp_radio_app.py"

analysis = Analysis(
    [str(entry_point)],
    pathex=[str(project_root / "src")],
    binaries=[],
    datas=[],
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=["pytest"],
    noarchive=False,
    optimize=0,
)
python_archive = PYZ(analysis.pure)

executable = EXE(
    python_archive,
    analysis.scripts,
    [],
    exclude_binaries=True,
    name="OOTP Radio",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch="arm64",
    codesign_identity=None,
    entitlements_file=None,
)
collection = COLLECT(
    executable,
    analysis.binaries,
    analysis.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="OOTP Radio",
)
application = BUNDLE(
    collection,
    name="OOTP Radio.app",
    icon=None,
    bundle_identifier="com.timcocuzza.ootpradio",
    version="0.1.0",
    info_plist={
        "CFBundleDisplayName": "OOTP Radio",
        "CFBundleName": "OOTP Radio",
        "LSApplicationCategoryType": "public.app-category.sports",
        "NSHighResolutionCapable": True,
    },
)
