# Technical Debt

This document tracks known technical debt and areas for improvement in the cdisplayagain project. Prefer naming the symbol over citing a line number, since the file changes often.

## Coverage

Coverage is enforced at 96% (`--cov-fail-under=96` in `pyproject.toml`) with a target of 100%.

- Run `uv run pytest --cov=cdisplayagain --cov=archives --cov-report=term-missing` to see uncovered lines.
- Remaining gaps are mostly UI error paths, platform-specific branches, and optional perf logging (`CDISPLAYAGAIN_PERF`).
- The macOS branch of `_user_state_root()` and the override/frozen branches of `_default_log_root()` only run on specific platforms.

### Testing Strategy
- Most uncovered lines are UI error paths or edge cases
- Some require specific runtime conditions (e.g., `PERF_LOGGING`)
- Add focused tests for ImageTk initialization failures and file dialog cancellation

## Placeholder / API-Only Methods

The methods below store state but nothing reads it during rendering, so toggling them has no visible effect. They exist to keep the configuration API and dialog stable. See `docs/PARITY.md` for the authoritative split.

Inert (configuration only):
- `set_one_page_mode()` / `set_two_page_mode()` / `toggle_two_pages()` - Display mode selection
- `toggle_color_balance()` - Automatic color correction
- `toggle_yellow_reduction()` - Yellow tint reduction
- `toggle_two_page_advance()` - Skip two pages at once
- `set_page_buffer(size)` - Preload buffer size
- `set_mouse_binding(button, action)` - Customize mouse buttons
- `toggle_hints()` / `_show_hint_popup()` - Popup hints (never invoked)

Implemented and functional:
- `_show_config()` - Configuration dialog UI
- `set_background_color(color)` - Applies to the viewer and canvas
- `set_small_cursor()` - Toggles cursor visibility

### Notes
- These serve as API contracts for parity with CDisplay
- Tests verify method existence; the inert ones do not affect output
- Update `docs/PARITY.md` when implementing

## Code Duplication

### Display Methods
- `_display_cached_image()` and `_display_image_fast()` share significant logic: ImageTk conversion with fallback, scroll-offset calculation, anchor positioning, and canvas update.
- Consider extracting shared display logic into a helper method.

### ImageTk Fallback Pattern
Repeated in both display methods:
```python
if self._imagetk_ready:
    try:
        self._tk_img = ImageTk.PhotoImage(img, master=self)
    except Exception:
        self._imagetk_ready = False
        self._tk_img = self._photoimage_from_pil(img)
else:
    self._tk_img = self._photoimage_from_pil(img)
```

## Broad Exception Handling

### File Cleanup
The cleanup closures in `archives.py` (ZIP close, RAR temp-dir cleanup, TAR close) use bare `except Exception`. They mask errors but log warnings.

### ImageTk Initialization
`_prime_imagetk()` uses broad exception handling with logging for import, interpreter access, address conversion, and `tkinit` failures.

### Worker Thread Cleanup
`ImageWorker.stop()` uses `except Exception: pass` when joining threads.

### Recommendations
- Where possible, use more specific exception types
- Document why broad exceptions are acceptable
- Consider re-raising critical errors after logging

## Complex Class

### ComicViewer Class
- Roughly 1300 lines in a single class.
- Handles UI rendering and event handling, page navigation and caching, configuration, keyboard shortcuts, mouse interactions, worker coordination, and dialogs.

### Refactoring Opportunities
- Extract dialog logic into separate classes
- Extract navigation logic into a helper class
- Extract configuration management
- Extract worker coordination logic

## Platform-Specific Code

### Mouse Wheel Bindings
Linux/X11 uses `<Button-4>`/`<Button-5>`; Windows/macOS use `<MouseWheel>`. Platform detection selects the bindings in `_bind_mouse()`.

### Recommendations
- Document platform-specific behavior in README
- Consider adding macOS/Windows mouse wheel tests

## Test Architecture

### Tkinter Testing
- Tests use the full `ComicViewer` class with real Tkinter widgets.
- Requires xvfb for headless CI (`make pytest`).
- `tests/conftest.py` points `CDISPLAYAGAIN_STATE_DIR` at a temp dir so tests never touch real reader state.

### Monkeypatch Usage
- Several test modules use monkeypatch; consider fixtures for common patches.

## Resource Cleanup

### Temporary Directories
- CBR extraction creates temp dirs cleaned through the `PageSource.cleanup` closure (success and failure paths).

### Worker Threads
- `ImageWorker.stop()` joins workers with a 0.5s timeout and clears the thread list.
- `ImageWorker.stop_all()` plus a `WeakSet` of instances guards against leaked workers.

## Logging

### Warning Logs
Cleanup failures, file extraction failures, ImageTk initialization failures, and cache update warnings.

### Performance Logging
- Optional via `CDISPLAYAGAIN_PERF=1` (`perf_log` / `PerfTimer`).
- Not exercised with the env var set in the default suite.

## Documentation Gaps

- Public methods could use more docstrings.
- Configuration behavior is described in `docs/PARITY.md`.

## Security Considerations

### Path Handling
- Uses `pathlib.Path` helpers; no shell redirection.
- `unrar2-cffi` performs in-process extraction.

### Archive Safety
- Archives are never mutated (zero-write runtime).
- Temporary files are cleaned up.

### Recommendations
- Document the archive security model
- Consider archive size limits

## Future Features

See `docs/PARITY.md` for the authoritative implemented / not-implemented split. Current gaps include Go To Page, zooming, CBA/CBT archives, SFV verification, two-page display, color balance, yellow reduction, page buffer configuration, popup hints, and reassignable mouse buttons.

## Dependencies

### Runtime
- `pillow>=12.0.0` - Image processing
- `pyvips[binary]>=3.1.1` - Fast image resizing
- `unrar2-cffi>=0.4.0` - RAR extraction

### System
- xvfb is required for headless testing
- `unar` is not required (CBR uses `unrar2-cffi`)

### Dev
- `mypy` (strict on application modules), `pytest`, `pytest-cov`, `ruff`, `pyinstaller`

## Performance Notes

### Optimizations Already Done
- LRU cache for PIL Image objects
- Parallel decoding with 4 workers
- Stale render cancellation
- Fast preview with NEAREST resampling
- PhotoImage fallback optimization

### Potential Improvements
- Consider making the worker count configurable
- Consider adaptive cache sizing based on archive size

## Configuration

### Hardcoded Values
- Worker count: 4 (`ImageWorker` default)
- Queue size: 4 (`ImageWorker._queue`)
- Debounce delay: 150ms (`ComicViewer._nav_debounce`)
- LRU cache size: 20 (`ComicViewer._image_cache`)
- These could be made configurable

## Pre-commit Hook

The pre-commit hook blocks commits containing `# type: ignore`, `# noqa`, `# ruff: ignore`, or `# pylint: ignore`. It then runs `scripts/lint.sh` (compileall, ruff, Any-type check, and mypy).

## Priority Recommendations

### High Priority
1. Wire the API-only configuration methods into rendering (two-page mode, color balance, etc.)
2. Extract the display method duplication into a shared helper

### Medium Priority
3. Consider breaking up the `ComicViewer` class
4. Improve exception specificity in cleanup paths
5. Document platform-specific behavior

### Low Priority
6. Make hardcoded values configurable
7. Add API documentation for public methods

## Last Updated

- Date: 2026-10-16
- Coverage: enforced at 96%, goal 100%
- Type checking: `mypy --strict` on the application modules
