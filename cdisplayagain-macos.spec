# -*- mode: python ; coding: utf-8 -*-

from PyInstaller.utils.hooks import collect_submodules


hiddenimports = collect_submodules("PIL")

a = Analysis(
    ["cdisplayagain.py"],
    pathex=["."],
    binaries=[],
    datas=[],
    hiddenimports=hiddenimports,
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
    [],
    name="cdisplayagain",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    argv_emulation=True,
    exclude_binaries=True,
)
coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    name="cdisplayagain",
)
app = BUNDLE(
    coll,
    name="cdisplayagain.app",
    icon="build/cdisplayagain.icns",
    bundle_identifier="com.cdisplayagain.viewer",
    info_plist={
        "CFBundleDisplayName": "cdisplayagain",
        "CFBundleDocumentTypes": [
            {
                "CFBundleTypeExtensions": ["cbz"],
                "CFBundleTypeName": "Comic Book ZIP",
                "CFBundleTypeRole": "Viewer",
                "LSHandlerRank": "Owner",
                "LSItemContentTypes": ["com.cdisplayagain.cbz"],
            },
            {
                "CFBundleTypeExtensions": ["cbr"],
                "CFBundleTypeName": "Comic Book RAR",
                "CFBundleTypeRole": "Viewer",
                "LSHandlerRank": "Owner",
                "LSItemContentTypes": ["com.cdisplayagain.cbr"],
            },
        ],
        "UTExportedTypeDeclarations": [
            {
                "UTTypeConformsTo": ["public.archive"],
                "UTTypeDescription": "Comic Book ZIP archive",
                "UTTypeIdentifier": "com.cdisplayagain.cbz",
                "UTTypeTagSpecification": {
                    "public.filename-extension": ["cbz"],
                    "public.mime-type": "application/x-cbz",
                },
            },
            {
                "UTTypeConformsTo": ["public.archive"],
                "UTTypeDescription": "Comic Book RAR archive",
                "UTTypeIdentifier": "com.cdisplayagain.cbr",
                "UTTypeTagSpecification": {
                    "public.filename-extension": ["cbr"],
                    "public.mime-type": "application/x-cbr",
                },
            },
        ],
    },
)
