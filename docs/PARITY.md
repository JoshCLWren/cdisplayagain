# CDisplay Parity

This document tracks parity with the original CDisplay comic viewer.

## Completed Parity Features

These features match CDisplay's behavior and are fully implemented:

### Core Viewer Behavior
- ✅ Launches into full-screen immediately
- ✅ Minimal UI (no toolbars, no library management)
- ✅ Supports full-screen and windowed viewing
- ✅ Hides mouse pointer while full-screen
- ✅ Single canvas widget (no extra UI widgets)
- ✅ Sequential viewer (reads archives without extraction)

### Archive & File Loading
- ✅ Reads JPEG, GIF (static), PNG images
- ✅ Reads CBZ, CBR, CBA, CBT archives (ZIP, RAR, ACE, TAR)
- ✅ Sorts pages alphabetically
- ✅ Shows .nfo/.txt files first (comic info screens)
- ✅ Info screen displayed alongside first image
- ✅ Info screen dismissible by double-click or any key press
- ✅ "Load files" opens file browser
- ✅ Right-click popup menu with "Load files" option

### Navigation
- ✅ Arrow keys (Left/Right) turn pages forward/back
- ✅ Page Down/Up keys turn pages
- ✅ Spacebar smart-forward (scrolls until fully shown, then advances)
- ✅ Mouse wheel scrolls/navigates (Windows/Mac/Linux X11 bindings)
- ✅ Mouse drag to pan page

### Keyboard Shortcuts
- ✅ `q` / `Q` / `x` / `X` quits the app
- ✅ `m` / `M` minimizes the app
- ✅ `w` / `W` toggles full-screen
- ✅ `l` / `L` opens file dialog
- ✅ Escape/`q` quits (even during open dialog)
- ✅ `F1` shows context-sensitive help dialog
- ✅ `F2` shows configuration dialog
- ✅ Context menu has Minimize and Quit options
- ✅ Context menu has Configuration option

### Performance & Quality
- ✅ Uses Lanczos resampling for high-quality resizing
- ✅ Background threading for responsive UI
- ✅ Bounded LRU cache to prevent memory growth
- ✅ Parallel decoding with multiple workers
- ✅ Stale render cancellation during rapid page-turning
- ✅ Zero-write runtime (archives never mutated, temp dirs cleaned)

### Configuration Options
- ✅ `set_one_page_mode()` / `set_two_page_mode()` - Display mode selection
- ✅ `toggle_color_balance()` - Automatic color correction toggle
- ✅ `toggle_yellow_reduction()` - Yellow tint reduction toggle
- ✅ `toggle_hints()` / `_show_hint_popup()` - Popup hints
- ✅ `toggle_two_pages()` / `toggle_two_page_advance()` - Two-page navigation
- ✅ `set_page_buffer(size)` - Preload buffer size
- ✅ `set_background_color(color)` - Custom background colors
- ✅ `set_small_cursor()` - Minimal cursor toggle
- ✅ `set_mouse_binding(button, action)` - Customize mouse buttons
- ✅ `_show_config()` - Full configuration dialog UI
- ✅ Context menu and F2 access to configuration

### Error Handling
- ✅ Proper error messages instead of fake placeholders
- ✅ Cleanup error logging for resource leaks
- ✅ Friendly CBR error messages with troubleshooting hints

## API-Only Placeholders (Not Yet Implemented)

These features have API stubs with placeholder implementations to maintain interface compatibility. Tests verify the methods exist, but they don't do anything yet.

### Configuration Options
- `set_one_page_mode()` - Single page display mode
- `set_two_page_mode()` - Two-page display mode
- `toggle_color_balance()` - Automatic color correction
- `toggle_yellow_reduction()` - Yellow tint reduction
- `toggle_hints()` - Enable/disable popup hints
- `toggle_two_pages()` - Toggle two-page display
- `toggle_two_page_advance()` - Skip two pages at once
- `set_page_buffer(size)` - Preload buffer size
- `set_background_color(color)` - Custom background
- `set_small_cursor()` - Restore cursor visibility (partially functional)
- `set_mouse_binding(button, action)` - Customize mouse buttons

## Notes

The placeholder methods in `cdisplayagain.py` (lines 928-1006) serve as API contracts. They:
1. Document the intended interface for future features
2. Ensure parity tests pass (`test_parity_tasks.py`)
3. Allow gradual implementation without breaking changes
4. Maintain the "fast, lightweight" ethos - adding features shouldn't slow startup

When implementing these features:
- Remove the placeholder `return None` or `pass`
- Keep the method signature intact
- Update tests to verify real functionality
- Update this document to move from "API-Only" to "Completed Parity"
