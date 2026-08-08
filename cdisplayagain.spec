from pathlib import Path
import sys
import sysconfig
import tomllib

project_root = Path.cwd()
is_macos = sys.platform == "darwin"

with (project_root / "pyproject.toml").open("rb") as pyproject:
    version = str(tomllib.load(pyproject)["project"]["version"])

icon_name = "cdisplayagain.icns"
icon_path = project_root / icon_name
if not (is_macos and icon_path.exists()):
    icon_path = project_root / "cdisplayagain.png"

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
    hiddenimports=["PIL._tkinter_finder", "build_info", "tk_bootstrap"],
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
    # A console executable on macOS makes Finder open a Terminal window alongside
    # the viewer; Linux keeps the console for CLI diagnostics.
    console=not is_macos,
    icon=str(icon_path),
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

if is_macos:
    comic_extensions = ["cbz", "cbr", "cbt", "cba"]
    image_extensions = ["jpg", "jpeg", "png", "gif", "webp", "bmp", "tif", "tiff"]
    app = BUNDLE(
        coll,
        name="cdisplayagain.app",
        icon=str(icon_path),
        bundle_identifier="io.github.joshclwren.cdisplayagain",
        version=version,
        info_plist={
            "CFBundleName": "cdisplayagain",
            "CFBundleDisplayName": "cdisplayagain",
            "CFBundleShortVersionString": version,
            "CFBundleVersion": version,
            "NSHighResolutionCapable": True,
            "LSMinimumSystemVersion": "11.0",
            "LSApplicationCategoryType": "public.app-category.graphics-design",
            "CFBundleDocumentTypes": [
                {
                    "CFBundleTypeName": "Comic Archive",
                    "CFBundleTypeRole": "Viewer",
                    # Owner rank tells Launch Services this app claims the type
                    # outright, so Finder prefers it over apps that merely open zips.
                    "LSHandlerRank": "Owner",
                    "CFBundleTypeExtensions": comic_extensions,
                    "CFBundleTypeIconFile": icon_name,
                    "LSItemContentTypes": [
                        "public.cbz-archive",
                        "public.cbr-archive",
                        "com.apple.comic-book-archive",
                    ],
                },
                {
                    "CFBundleTypeName": "Image",
                    "CFBundleTypeRole": "Viewer",
                    "LSHandlerRank": "Alternate",
                    "CFBundleTypeExtensions": image_extensions,
                    "LSItemContentTypes": ["public.image"],
                },
            ],
            "UTExportedTypeDeclarations": [
                {
                    "UTTypeIdentifier": "public.cbz-archive",
                    "UTTypeDescription": "Comic Book ZIP Archive",
                    "UTTypeConformsTo": ["public.zip-archive"],
                    "UTTypeTagSpecification": {"public.filename-extension": ["cbz"]},
                },
                {
                    "UTTypeIdentifier": "public.cbr-archive",
                    "UTTypeDescription": "Comic Book RAR Archive",
                    "UTTypeConformsTo": ["public.archive"],
                    "UTTypeTagSpecification": {"public.filename-extension": ["cbr"]},
                },
            ],
        },
    )
