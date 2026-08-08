## cdisplayagain

![Python](https://img.shields.io/badge/python-3.13+-blue.svg)
![codecov](https://codecov.io/gh/JoshCLWren/cdisplayagain/graph/badge.svg)
![License](https://img.shields.io/badge/license-MIT-green.svg)

 `cdisplayagain` is a minimalist, cross-platform remake of the classic
 Windows-only CDisplay sequential image viewer. The goal is to keep the
 original spirit—fast page flips, zero data mutation, and archive-first
 comic reading—while modernizing the codebase with Python, Pillow, pyvips, and a
 clean CLI workflow.

### Why it exists

CDisplay defined how digital comics should feel: unzip-free, keyboard
friendly, and respectful of your library. The original implementation is
frozen in time on old Windows releases. This project re-imagines that
experience with modern tooling so contributors can continue evolving the
viewer without wrestling dated IDEs or registry quirks.

### Features

 - Sequential viewing of JPEG, PNG, and GIF pages sourced directly from
   CBZ/CBR archives.
 - Archive abstractions that automatically sort page names using
   `natural_key` to match the reading order you expect.
 - Tk-based viewer with fit-to-screen navigation mapped to the same
   effortless keyboard-first workflow as CDisplay.
 - Zero-write runtime: archives stay untouched and temporary extraction
   directories are cleaned automatically.
 - Fast image processing using pyvips with LRU caching for instant page turns.

### Installation

Every route gives you a self-contained app with `.cbz`/`.cbr` double-click
support and no Python installation to manage.

| Platform | Install |
| --- | --- |
| macOS (Apple silicon) | `brew install --cask cdisplayagain` (see below for the two setup lines) |
| Linux (x86-64) | Download the release archive, run `./install.sh` |
| Anything else | Build from source with `make install` |

#### macOS via Homebrew

```bash
brew tap JoshCLWren/tap
brew trust joshclwren/tap
brew install --cask cdisplayagain
```

Homebrew refuses to load casks from a third-party tap until you trust it, which
is what the middle line does. It is a one-time decision per machine, and you can
scope it to this cask alone with
`brew trust --cask joshclwren/tap/cdisplayagain`.

Then open any comic:

```bash
open ~/Comics/issue.cbz
```

Or double-click a `.cbz`/`.cbr` in Finder, which works because the installer
registers the app as their default handler.

Upgrade and removal are the usual Homebrew verbs:

```bash
brew upgrade --cask cdisplayagain
brew uninstall --cask cdisplayagain
```

The cask ships the Apple silicon build the release workflow publishes. It is
ad-hoc signed rather than notarized, since notarization requires a paid Apple
Developer account, so Homebrew's quarantine flag is cleared during install; the
[tap README](https://github.com/JoshCLWren/homebrew-tap) explains how to handle
that yourself instead. Intel Macs have no published asset and should build from
source, which sidesteps quarantine entirely.

#### Linux release (Linux x86-64)

Download the latest Linux release archive from GitHub. No Python installation
is required for release downloads.

1. Optionally verify the archive with the accompanying `SHA256SUMS` file.
2. Extract the archive.
3. Enter the extracted directory and run `./install.sh`.
4. Open `.cbz` and `.cbr` files from your desktop file manager.

The installer is user-local and requires no sudo. It installs the bundle under
`~/.local/lib/cdisplayagain`, a wrapper at `~/.local/bin/cdisplayagain`, the
desktop entry under `~/.local/share/applications`, and the icon under the XDG
data directory. Uninstall with `./install.sh --uninstall` from the extracted
release directory. `PREFIX`, `HOME`, and `XDG_DATA_HOME` can override these
locations for testing or custom user-local layouts.

Linux downloads are x86-64 only. macOS is published as an Apple silicon app
bundle (see above); Windows has no packaged release yet.

Release builds are produced in Ubuntu 22.04 (glibc 2.35), the oldest verified
distribution baseline, and compatibility checks run the same archive on
Ubuntu 22.04, Ubuntu 24.04, Debian 13, Fedora 42, and openSUSE Leap 15.6.
These checks cover x86-64 headless startup, archive handling, X11/Xvfb, the
installer, and bundled/native shared-library resolution. They do not establish
GNOME, KDE, Wayland, GPU-driver, or file-manager integration. The packaged
bundle includes its Python, Pillow, pyvips/libvips, unrar, and Tk runtime
components; it requires a glibc-based Linux x86-64 system with the usual X11
libraries. Alpine Linux and musl-based systems are unsupported.

#### macOS app bundle (build from source)

Build a real `cdisplayagain.app` from a clone and install it, so `.cbz`/`.cbr`
files open on double-click:

```bash
uv sync
make install
```

`make install` builds `dist/cdisplayagain.app` (a self-contained bundle carrying
its own Python, Tk, Pillow, libvips, and unrar), copies it to `/Applications`,
registers it with Launch Services, and drops a CLI wrapper at
`~/.local/bin/cdisplayagain`. Use `make build` alone to produce the bundle
without installing it. Override the destination with `MACOS_APPDIR`
(for example `MACOS_APPDIR=~/Applications make install`) and the wrapper
location with `PREFIX`. Remove everything with `make uninstall-macos`.

Making it the *default* comic viewer needs one more piece, because macOS will
not let an app claim a file type on its own. If [`duti`](https://github.com/moretension/duti)
is installed (`brew install duti`), `make install` sets the default handler for
`.cbz`, `.cbr`, `.cbt`, and `.cba` automatically. Otherwise set it once by hand:
right-click a comic, choose Get Info, set Open With to cdisplayagain, and click
Change All.

`make package-macos` produces a distributable
`cdisplayagain-<version>-macos-<arch>.zip` containing the app, an `install.sh`,
and the license. The bundle is unsigned and un-notarized, so a copy downloaded
through a browser is quarantined; open it the first time with right-click >
Open, or clear the flag with
`xattr -dr com.apple.quarantine /Applications/cdisplayagain.app`.

Finder hands a double-clicked file to a macOS app through an `openDocument`
Apple Event rather than `argv`, so the viewer registers a
`::tk::mac::OpenDocument` handler at startup. That also means double-clicking a
second comic while the app is running loads it into the open window.

#### Source installation for contributors

Source installation is for development and requires Python and the project
tools:

```bash
uv venv
uv sync
```

If you prefer traditional pip:

```bash
python -m venv .venv && source .venv/bin/activate
python -m pip install -e .
```

To install `uv` if you do not have it yet:

```bash
pipx install uv
```

Or, via the official installer:

```bash
curl -Ls https://astral.sh/uv/install.sh | sh
```

 CBR support uses `unrar2-cffi` for in-process extraction.

  The project uses `pyvips[binary]` which includes precompiled libvips binaries
  for all platforms (Linux, macOS, Windows). No external libvips installation required.

### macOS Setup

**Note:** Recent Python versions on macOS no longer include tkinter by default.
You must install it separately:

```bash
brew install python-tk
```

Running from source under a `uv`-managed interpreter needs no extra step, but
it is worth knowing why. uv installs python-build-standalone, which keeps
Tcl/Tk under the interpreter prefix while Tk probes for `init.tcl` relative to
the virtualenv, so every `Tk()` call would fail with
`Can't find a usable init.tcl`. `tk_bootstrap.py` sets `TCL_LIBRARY` and
`TK_LIBRARY` at import time to fix this for every entry point: the app, the
tests, and IDE launches alike. It is a no-op for Homebrew and system pythons,
which resolve those paths themselves.

If you encounter issues with the UI not responding or appearing, try:
```bash
export TK_SILENCE_DEPRECATION=1
python cdisplayagain.py path/to/comic.cbz
```

**Running the tests on macOS.** There is no xvfb for Aqua, so `make pytest`
opens real Tk windows and takes over the display for the ~30 seconds the suite
runs. One test, `test_right_click_shows_context_menu`, fails natively because
Aqua's `tk_popup` needs a live event loop.

`make pytest-container` runs the suite headless in the Debian container, using a
dedicated Docker volume so the host `.venv` is never overwritten with Linux
binaries. It is the CI-parity path and works well on Linux, but be warned that
it has been observed hanging on macOS, where Docker bind-mounts the repository
across the VM boundary. Prefer the native run there, or let CI cover it.

### Usage

Open any `.cbz` or `.cbr` archive:

```bash
python cdisplayagain.py path/to/comic.cbz
```

If you are using `uv`, you can run without activating the virtualenv:

```bash
uv run python cdisplayagain.py path/to/comic.cbz
```

Or via the Makefile:

```bash
make run FILE=path/to/comic.cbz
```

While viewing, navigate with the arrow keys, scroll wheel, or spacebar,
and use `Esc` or `q` to close the window.

 ### Makefile targets

 - `make venv`: create the uv-managed virtualenv.
 - `make sync`: install dependencies from `uv.lock`.
 - `make lint`: run ruff.
 - `make pytest`: run the test suite (xvfb on Linux, container on macOS).
 - `make pytest-container`: run the suite headless in Docker on any platform.
 - `make build`: build the PyInstaller bundle, plus `cdisplayagain.app` on macOS.
 - `make install`: build and install for this machine (Linux bundle or macOS `.app`).
 - `make uninstall-macos`: remove the installed macOS app and CLI wrapper.
 - `make package-macos`: zip the macOS app for distribution.
 - `make run FILE=path/to/comic.cbz`: launch the viewer.
 - `make smoke FILE=path/to/comic.cbz`: print the manual checklist and launch.
 - `make profile-cbz FILE=path/to/comic.cbz`: profile CBZ launch performance.
 - `make profile-cbr FILE=path/to/comic.cbr`: profile CBR launch performance.

### Development flow

- Stick to descriptive snake_case helpers and small, explicit modules.
- Run `make lint` (or `uv run ruff check .`) after each change.
- Use `make pytest` (or `uv run pytest`) for the test suite.
- Use `make sync` to mirror CI dependency installs.
- Use `make smoke FILE=path/to/comic.cbz` to run the manual checklist.
- Run manual smoke tests by paging through both CBZ and CBR files,
  validating zoom modes, and confirming temp directories are cleaned.
- When opening pull requests, summarize user impact, list the manual
  archives you exercised, and attach screenshots if UI changes.

### Credits

All inspiration comes from David Ayton's original "CDisplay Sequential
Image Viewer". This repo simply keeps that experience alive with a more
approachable tech stack.
