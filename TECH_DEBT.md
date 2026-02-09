# Technical Debt

This document tracks known technical debt and areas for improvement in the cdisplayagain project.

## Coverage Gaps (96% - target: 100%)

Current coverage is 96.01% with 47 lines uncovered:

### Uncovered Lines (cdisplayagain.py)
- **Line 73**: Performance logging path (`PERF_LOGGING=True`)
- **Line 465**: Worker thread exit condition
- **Line 483**: Worker thread stop condition (`_should_stop()`)
- **Lines 703-737**: ImageTk initialization error paths (6 scenarios)
- **Lines 846-861**: File dialog browse button handlers
- **Lines 871-872**: Open dialog cancel handler
- **Lines 875**: Open dialog cancel handler
- **Lines 889-890**: Open dialog result handling
- **Line 901**: Focus request after open dialog
- **Lines 1015-1016**: Anchor positioning in display fast
- **Lines 1185-1187**: Config dialog color apply button
- **Lines 1196-1197**: Config dialog close handler
- **Lines 1282-1288**: Canvas resize logging
- **Line 1464**: Early return when scroll max is 0
- **Lines 1509-1510**: Scroll offset clamping in reposition
- **Line 1678**: pyvips requirement check for CBR files

### Testing Strategy
- Most uncovered lines are UI error paths or edge cases
- Some require specific runtime conditions (e.g., `PERF_LOGGING`)
- Consider adding focused tests for ImageTk initialization failures
- Add tests for file dialog cancellation scenarios

## Placeholder Methods

The following methods in `cdisplayagain.py` (lines 928-1006) have placeholder implementations that return `None` or `pass`:

### Configuration Options (API-Only)
- `set_one_page_mode()` - Single page display mode
- `set_two_page_mode()` - Two page display mode
- `toggle_color_balance()` - Automatic color correction
- `toggle_yellow_reduction()` - Yellow tint reduction
- `toggle_hints()` - Enable/disable popup hints
- `toggle_two_pages()` - Toggle two-page display
- `toggle_two_page_advance()` - Skip two pages at once
- `set_page_buffer(size)` - Preload buffer size
- `set_small_cursor()` - Restore cursor visibility (partially functional)
- `set_mouse_binding(button, action)` - Customize mouse buttons

### Notes
- These serve as API contracts for parity with CDisplay
- Tests verify method existence but not functionality
- Update `docs/PARITY.md` when implementing
- Remove `return None` / `pass` when implementing

## Code Duplication

### Display Methods
- `_display_cached_image()` (lines 938-974) and `_display_image_fast()` (lines 976-1017) share significant logic:
  - ImageTk.PhotoImage conversion with fallback
  - Scroll offset calculation
  - Anchor positioning
  - Canvas update logic
- Consider extracting shared display logic into a helper method

### ImageTk Fallback Pattern
Repeated in both display methods (lines 942-949, 990-998):
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
Several cleanup operations use bare `except Exception`:
- Line 282: ZIP file close
- Line 316: RAR temp directory cleanup
- Line 349: TAR file close
- These mask errors but log warnings

### ImageTk Initialization
Lines 703-737 use broad exception handling with logging for:
- PIL._imagingtk import failures
- Tk interpreter access failures
- Interpreter address conversion failures
- tkinit call failures

### Worker Thread Cleanup
Line 470: `except Exception: pass` when joining threads during cleanup

### Recommendations
- Where possible, use more specific exception types
- Document why broad exceptions are acceptable
- Consider re-raising critical errors after logging

## Complex Class

### ComicViewer Class
- **Lines ~400-1700**: ~1300 lines in a single class
- **118 functions total**, 65 private methods (`def _`)
- **29 imports** at module level
- Handles multiple concerns:
  - UI rendering and event handling
  - Page navigation and caching
  - Configuration management
  - Keyboard shortcuts
  - Mouse interactions
  - Worker thread coordination
  - Dialog management

### Refactoring Opportunities
- Consider extracting dialog logic into separate classes
- Extract navigation logic into a helper class
- Extract configuration management
- Extract worker coordination logic

## Pass Statements

Found 6 `pass` statements (lines 928-1006 area):
- All are in placeholder methods
- Remove when implementing the methods

## Platform-Specific Code

### Mouse Wheel Bindings
Lines 828-830 handle Linux/X11 specific bindings:
```python
self.bind_all("<Button-4>", lambda e: self.prev_page())
self.bind_all("<Button-5>", lambda e: self.next_page())
```
- These bindings don't work on macOS/Windows
- macOS/Windows use `<MouseWheel>` event
- Already has platform detection (lines 821-827)

### Recommendations
- Document platform-specific behavior in README
- Consider adding macOS/Windows mouse wheel tests

## Test Architecture

### Tkinter Testing
- Tests use full `ComicViewer` class with real Tkinter widgets
- Requires xvfb for headless CI (`make pytest`)
- Can cause timeouts in headless environments
- Consider faking more UI components for faster tests

### Monkeypatch Usage
- 10 test files use monkeypatch
- Consider using fixtures for common patches

## Resource Cleanup

### Temporary Directories
- CBR extraction creates temp dirs that must be cleaned up
- Multiple cleanup paths exist (success, failure, cancellation)
- Tests verify cleanup but there are multiple uncovered error paths

### Worker Threads
- Worker pool is stopped and joined during cleanup
- Uses timeout of 1.0s for thread joins
- Broad exception handling when threads fail to join

## Logging

### Warning Logs
Multiple warning logs for non-critical failures:
- Cleanup failures (multiple locations)
- File extraction failures (line 295)
- ImageTk initialization failures (6 scenarios)
- Cache update warnings

### Performance Logging
- Optional performance logging via `CDISPLAYAGAIN_PERF` env var
- Line 73 uncovered in tests (requires env var set)
- Consider adding tests with perf logging enabled

## Documentation Gaps

### Missing API Documentation
- Public methods lack detailed docstrings
- Configuration options not documented in README
- Placeholder methods not clearly marked in API

### Inline Documentation
- Code comments discouraged by AGENTS.md
- Some complex logic could benefit from docstrings
- Consider adding docstrings for public API

## Security Considerations

### Path Handling
- Uses `Path` helpers from pathlib (good practice)
- User paths sanitized via Path helpers
- No shell command injection risks observed

### Archive Safety
- Archives never mutated (zero-write runtime)
- Temporary files cleaned up
- Unchecked archive extraction could be risk

### Recommendations
- Document archive security model
- Consider adding archive size limits

## Future Features

### Parity Items (from tasks.md)
Not yet implemented from PARITY.md:
- Mouse drag to pan page (partially done)
- Mouse wheel navigation (partially done)
- Minimize/Quit via popup menu (✅ implemented)
- Automatic page sizing options
- Two-page display modes
- Automatic color balance
- Yellow reduction
- Popup hints on configuration screen
- Page buffer configuration
- Background color configuration
- Small cursor option
- Custom mouse bindings
- Full-screen toggle (W) (✅ implemented)

## Dependencies

### External Dependencies
- `pillow>=12.0.0` - Image processing
- `pyvips>=2.2.0` - Fast image resizing
- `unrar2-cffi>=0.4.0` - RAR extraction
- All pinned to specific major versions

### System Dependencies
- `unar` mentioned in AGENTS.md but not required
- xvfb required for headless testing

## Performance Notes

### Optimizations Already Done
- LRU cache for PIL Image objects
- Parallel decoding with 4 workers
- Stale render cancellation
- Fast preview with NEAREST resampling
- PhotoImage fallback optimization

### Potential Improvements
- Consider making worker count configurable
- Consider adaptive cache sizing based on archive size

## Configuration

### Hardcoded Values
- Worker count: 4 (line 385)
- Queue size: 4 (line 388)
- Debounce delay: 150ms (line ~686)
- LRU cache size: 20 (line ~1075)
- These could be made configurable

## Pre-commit Hook

The pre-commit hook blocks commits containing:
- `# type: ignore`
- `# noqa`
- `# ruff: ignore`
- `# pylint: ignore`

This prevents technical debt from being suppressed in code.

## Priority Recommendations

### High Priority
1. Implement placeholder methods to complete parity features
2. Extract display method duplication into shared helper
3. Address ImageTk initialization test coverage gaps

### Medium Priority
4. Consider breaking up ComicViewer class
5. Improve exception specificity in cleanup paths
6. Document platform-specific behavior

### Low Priority
7. Make hardcoded values configurable
8. Consider extracting worker coordination logic
9. Add API documentation for public methods

## Last Updated

- Date: 2025-12-30
- Coverage: 96.01% (47 lines uncovered)
- Total Lines: 1723
- Total Functions: 118
