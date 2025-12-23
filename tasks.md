# Task Backlog

Tracking the README promises that still need implementation work.

## README feature gaps

- [ ] **Scroll wheel navigation:** README Usage section advertises scroll wheel paging, but `ComicViewer` currently only binds keyboard events for navigation. We need to bind `<MouseWheel>` (and platform equivalents) to `next_page` / `prev_page` to fulfill the documented behavior.
- [ ] **Fit mode toggles:** README Features lists both fit-to-screen and fit-to-width modes, yet `_render_current` always scales to fit the canvas with no ability to switch modes. Implement explicit fit mode state plus keyboard shortcuts for toggling between fit-to-screen and fit-to-width layouts.
- [ ] **Zoom shortcuts:** README Usage promises keyboard-controlled zoom toggles, but there are no zoom in/out/reset handlers today. Add zoom state management with associated shortcuts so readers can magnify beyond the automatic fit sizing.
