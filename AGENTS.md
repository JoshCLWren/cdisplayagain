# Repository Guidelines

## Project Ethos
- **Honor the original experience:** Preserve CDisplay's fast, lightweight, and keyboard-first feel rather than reinventing the workflow.
- **Modernize without bloat:** Adopt Python conveniences and Tk widgets only when they simplify maintenance; avoid bolting on features that slow startup or clutter the UI.
- **Respect readers' libraries:** Never mutate archives, keep temporary files contained and cleaned, and surface errors before data loss can occur.
- **Prefer clarity over cleverness:** Write explicit helpers, document design decisions in pull requests, and leave the code approachable for hobbyist contributors.
- **Cross-platform empathy:** Test on at least one non-Windows platform, call out external dependencies like `unar`, and avoid shell-specific shortcuts.

## Project Structure & Module Organization
The viewer lives entirely in the repository root. `cdisplayagain.py` exposes the CLI-oriented entrypoint with a `PageSource` abstraction and rendering loop built around `Archive` subclasses for CBZ/CBR handling. Tooling metadata (`pyproject.toml`, `uv.lock`) defines the Pillow and rarfile dependencies; assets are loaded directly from archives at runtime, so there is no static `assets/` directory. Expect any future modules (tests, components, helpers) to sit beside these files unless a new package directory is created.

## Build, Test, and Development Commands
- `uv venv`: create a uv-managed virtualenv (skip activation).
- `uv sync`: install dependencies via uv without activating the venv.
- `uv run python cdisplayagain.py path/to/comic.cbz`: open a specific archive immediately, useful for manual regression runs.
- `uv run python cdisplayagain.py path/to/comic.cbz`: alternative if you prefer the fast `uv` workflow already tracked via `uv.lock`.

## Coding Style & Naming Conventions
Follow standard PEP 8 spacing (4 spaces, 100-character soft wrap) and favor descriptive snake_case for functions and variables (`natural_key`, `open_archive`). Retain the current pattern of dataclasses (`Archive`, `PageSource`) for typed data containers and keep public functions annotated with precise types. Prefer explicit helper names (e.g., `load_cbz`) and guard Tk callbacks with early returns rather than nesting.

## Testing Guidelines
There is no automated test suite yet; when adding one, scaffold `tests/` with `pytest` and name cases after the behavior under test (e.g., `test_load_cbz_sorts_pages`). For now, perform manual smoke tests by running `python cdisplayagain.py path/to/sample.cbz`, opening both `.cbz` and `.cbr` samples, paging through images, toggling fit/zoom, and ensuring cleanup of temporary directories. Document any manual checklist you execute inside the pull request.

## Commit & Pull Request Guidelines
Use imperative, component-scoped commits such as `Add CBR extraction error copy` or `Refine zoom keyboard shortcuts`. Bundle related changes per commit, referencing issue numbers in the footer when applicable. Pull requests should summarize user impact, list testing performed (commands and archive types opened), note any new dependencies (system packages like `unar`), and attach screenshots when UI is affected.

## Security & Configuration Tips
CBR support requires the external `unar` binary; verify contributors mention its installation path in reviews. Never check in sample comics or proprietary content—use small public-domain archives stored locally. When touching subprocess calls (`unar`, `rarfile`), sanitize user paths via `Path` helpers and prefer Python APIs over shell redirection.
