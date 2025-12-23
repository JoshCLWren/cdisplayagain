## cdisplayagain

`cdisplayagain` is a minimalist, cross-platform remake of the classic
Windows-only CDisplay sequential image viewer. The goal is to keep the
original spirit—fast page flips, zero data mutation, and archive-first
comic reading—while modernizing the codebase with Python, Pillow, and a
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
- Tk-based viewer with fit-to-screen, fit-to-width, and zoom shortcuts
  mapped to the same effortless keyboard-first workflow as CDisplay.
- Zero-write runtime: archives stay untouched and temporary extraction
  directories are cleaned automatically.

### Installation

```bash
python -m venv .venv && source .venv/bin/activate
python -m pip install -e .
```

If you already use `uv`, you can skip activation and use its pip shim:

```bash
uv venv
uv pip install -e .
```

To install `uv` if you do not have it yet:

```bash
pipx install uv
```

Or, via the official installer:

```bash
curl -Ls https://astral.sh/uv/install.sh | sh
```

CBR support depends on the external `unar` binary. Install it via your
package manager (`brew install unar`, `apt install unar`, etc.) and
ensure it is on `PATH` before launching the viewer.

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

While viewing, navigate with the arrow keys or scroll wheel, toggle fit
and zoom modes from the keyboard, and use `Esc` to close the window.

### Makefile targets

- `make venv`: create the uv-managed virtualenv.
- `make sync`: install dependencies from `uv.lock`.
- `make lint`: run ruff.
- `make pytest`: run the test suite.
- `make run FILE=path/to/comic.cbz`: launch the viewer.
- `make smoke FILE=path/to/comic.cbz`: print the manual checklist and launch.

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
