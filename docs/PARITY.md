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
- ✅ Reads JPEG, PNG, GIF (static), WEBP, BMP, and TIFF images
- ✅ Reads CBZ, CBR, and TAR archives (ZIP, RAR/ACE, TAR)
- ✅ Sorts pages alphabetically
- ✅ Shows .nfo/.txt files first (comic info screens)
- ✅ Info screen displayed alongside first image
- ✅ Info screen dismissible by double-click or any key press
- ✅ "Load files" opens file browser
- ✅ Right-click popup menu with "Load files" option
- ✅ Remembers the last page read per file and resumes there (unless the comic was finished)

### Navigation
- ✅ Arrow keys (Left/Right) turn pages forward/back
- ✅ Page Down/Up keys turn pages
- ✅ Spacebar smart-forward (scrolls until fully shown, then advances)
- ✅ Sequential reading across comics in same directory (next/previous comic)
- ✅ Mouse wheel scrolls/navigates (Windows/Mac/Linux X11 bindings)
- ✅ Mouse drag to pan page
- ✅ Page counter (bottom-right current/total fraction, auto black/white by page luminance)

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
- ✅ `_show_config()` - Configuration dialog UI
- ✅ Context menu and F2 access to configuration
- ✅ `set_background_color(color)` - Custom background colors
- ✅ `set_small_cursor()` - Toggles cursor visibility

## Not Yet Implemented

These features are not yet present in cdisplayagain.

### Navigation
- ❌ Go To Page (jump to a specific page number by entering it)
- ❌ Zooming (manual zoom in/out toggle)

### Archive & File Loading
- ❌ CBA/CBT archives (ACE- and TAR-based comic archives). The file dialog and desktop associations list them, but `load_comic` rejects them.
- ❌ SFV file verification (verify archive integrity via .sfv checksums)

### Display Modes & Image Adjustments
- ❌ Two-page display modes (the configuration dialog exposes the toggles, but they do not affect rendering)
- ❌ Color balance / yellow reduction (toggles exist but are not applied to images)
- ❌ Page preload buffer size (the setting is stored, but the preload count is fixed)
- ❌ Reassignable mouse buttons (the API stores bindings but they are not consulted)
- ❌ Popup hints (the toggle and `_show_hint_popup()` exist but are never invoked)

## API-Only Placeholders

These methods exist to keep the configuration API stable and to render the configuration dialog. They store state but nothing reads it during rendering, so toggling them has no visible effect yet.

### Configuration Options
- `set_one_page_mode()` / `set_two_page_mode()` / `toggle_two_pages()` - Display mode selection
- `toggle_color_balance()` - Automatic color correction
- `toggle_yellow_reduction()` - Yellow tint reduction
- `toggle_two_page_advance()` - Skip two pages at once
- `set_page_buffer(size)` - Preload buffer size
- `set_mouse_binding(button, action)` - Customize mouse buttons
- `toggle_hints()` / `_show_hint_popup()` - Popup hints

## Notes

The placeholder configuration methods in `cdisplayagain.py` serve as API contracts. They:
1. Document the intended interface for future features
2. Keep the configuration dialog renderable and parity tests passing (`test_parity_tasks.py`)
3. Allow gradual implementation without breaking changes
4. Maintain the "fast, lightweight" ethos - adding features shouldn't slow startup

When implementing these features:
- Wire the stored setting into rendering/navigation
- Keep the method signature intact
- Update tests to verify real functionality
- Update this document to move from "API-Only" to "Completed Parity"
