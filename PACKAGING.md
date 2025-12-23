# Packaging plan (macOS + Linux)

This project is a single-file Tk app with Pillow + rarfile + external `unar` for CBR.
Goal: ship self-contained builds so users do not need to know Python exists.

## Overview
- Build per-OS artifacts (PyInstaller builds are platform-specific).
- macOS: `.app` bundle, optionally distributed via Homebrew cask.
- Linux: standalone binary or AppImage for the most portable UX.

## Dependencies to keep in mind
- `unar` is required for CBR support.
  - Option A: bundle `unar` inside the app (best UX).
  - Option B: keep external and show a clear error + install hint.

## Option A: PyInstaller (recommended)

### macOS build
1. Create a fresh venv and install deps:
   ```bash
   python -m venv .venv
   source .venv/bin/activate
   pip install -e .
   pip install pyinstaller
   ```
2. Build the app bundle:
   ```bash
   pyinstaller --windowed --name CDisplayAgain cdisplayagain.py
   ```
3. Output:
   - `dist/CDisplayAgain.app`

Optional: wrap the `.app` in a Homebrew cask for `brew install --cask`.

### Linux build
1. Create a fresh venv and install deps:
   ```bash
   python -m venv .venv
   source .venv/bin/activate
   pip install -e .
   pip install pyinstaller
   ```
2. Build a standalone binary:
   ```bash
   pyinstaller --onefile --name cdisplayagain cdisplayagain.py
   ```
3. Output:
   - `dist/cdisplayagain`

Optional: wrap the binary as an AppImage.

## AppImage (Linux optional)
- Use `linuxdeploy` or `appimagetool` to wrap the PyInstaller output.
- This gives users a single portable file they can run without install.

## Homebrew cask (macOS optional)
- Host the `.app` in a tagged GitHub release.
- Create a tap with a cask that downloads the release asset and installs it to `/Applications`.

## Release checklist (manual)
- Build macOS `.app` on macOS.
- Build Linux binary (or AppImage) on Linux.
- Verify:
  - Launches without Python installed.
  - Opens `.cbz` successfully.
  - CBR error path is friendly if `unar` is missing.
- Publish release assets and update cask/AppImage notes.

## Notes on bundling `unar`
- If you bundle `unar`, ensure license compatibility and include a note in release docs.
- If you keep it external, surface an error that includes an install hint:
  - macOS: `brew install unar`
  - Linux: package manager equivalent
