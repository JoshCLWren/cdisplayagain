from pathlib import Path

project_root = Path.cwd()

a = Analysis(
    [str(project_root / "cdisplayagain.py")],
    pathex=[str(project_root)],
    binaries=[],
    datas=[(str(project_root / "cdisplayagain.png"), ".")],
    hiddenimports=["PIL._tkinter_finder", "build_info"],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz,
    a.scripts,
    [],
    name="cdisplayagain",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=True,
    icon=str(project_root / "cdisplayagain.png"),
    exclude_binaries=True,
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    name="cdisplayagain",
)
