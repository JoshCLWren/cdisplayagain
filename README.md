## cdisplayagain

![Python](https://img.shields.io/badge/python-3.12+-blue.svg)
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

 CBR support uses `unrar2-cffi` for in-process extraction. The external
 `unar` binary is used as a fallback if needed. Install it via your
 package manager (`brew install unar`, `apt install unar`, etc.) for
 maximum compatibility.

 The project requires `pyvips` for fast image processing. Install the
 libvips library via your package manager:
 - Linux: `sudo apt install libvips`
 - macOS: `brew install vips`
 - Windows: Download from libvips.org or `conda install -c conda-forge pyvips`

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
 - `make pytest`: run the test suite.
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
