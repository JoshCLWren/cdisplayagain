from pathlib import Path
import sysconfig

project_root = Path.cwd()

python_lib_dirs = {
    Path(path)
    for path in (sysconfig.get_config_var("LIBDIR"), sysconfig.get_config_var("prefix"))
    if path
}
tk_binaries = [
    (str(library), ".")
    for lib_dir in python_lib_dirs
    for library in lib_dir.glob("libt[ck]*.so*")
]

a = Analysis(
    [str(project_root / "cdisplayagain.py")],
    pathex=[str(project_root)],
    binaries=tk_binaries,
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
