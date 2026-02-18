# Plan: Sequential Reading Feature

**Goal:** Auto-advance to next/previous comic in the same directory, matching original CDisplay 1.8 behavior.

## Status

- [x] Plan doc created
- [x] Step 1: `_get_sibling_comics()` helper + `ARCHIVE_EXTS` constant
- [x] Step 2: Wire into `__init__` and `_open_comic()` to track siblings
- [x] Step 3: `next_comic()` / `prev_comic()` methods
- [x] Step 4: Auto-advance in `next_page()` / `prev_page()` at boundaries
- [x] Step 5: Keybindings (`n`/`N`, `p`/`P`) and context menu entries
- [x] Step 6: `_update_title()` shows position (e.g., "[2/5] comic.cbz")
- [x] Step 7: Tests — full coverage of all paths
- [x] Step 8: Lint + type check passes
- [x] Step 9: Update PARITY.md to mark sequential reading as ✅
- [x] Step 10: Refactor cdisplayagain.py into smaller modules
- [x] Step 11: Coverage back to 96%+

## Completion Notes

- Implemented sequential archive navigation and boundary auto-advance.
- Added sibling-aware title formatting and key/menu bindings.
- Added archive-loading module extraction (`archives.py`) and tests.
- Restored project coverage target (>=96%).

## Design

### New constant

```python
ARCHIVE_EXTS = {".cbz", ".cbr", ".cba", ".cbt", ".zip", ".rar", ".ace", ".tar"}
```

### New instance attributes on ComicViewer

```python
self._sibling_comics: list[Path] = []   # sorted archive files in same dir
self._sibling_index: int = -1           # index of current comic in siblings
```

### `_get_sibling_comics(path: Path) -> tuple[list[Path], int]`

- Takes the path of the currently opened comic
- Scans `path.parent` for files whose suffix is in `ARCHIVE_EXTS`
- Sorts them using `natural_key` on the filename
- Returns `(sorted_list, index_of_current_path)`
- If `path` is not an archive (e.g., bare image or directory), returns `([], -1)`

### `next_comic()` / `prev_comic()`

- Check `_sibling_comics` is non-empty and index is valid
- Increment/decrement `_sibling_index` with bounds checking
- Call `_open_comic(new_path)` then trigger first render
- No-op if at first/last comic — no wrapping

### Auto-advance at page boundaries

- `next_page()`: when on last page, call `next_comic()` instead of no-op
- `prev_page()`: when on first page, call `prev_comic()` instead of no-op

### Keybindings

- `n` / `N` → `next_comic()`
- `p` / `P` → `prev_comic()`

### Context menu

Add after "Load files":
- "Next comic" → `next_comic()`
- "Previous comic" → `prev_comic()`

### Title bar

Update `_update_title()` to show `[2/5]` prefix when siblings exist.

## Edge Cases

1. **Only one comic in directory** — siblings list has 1 entry, next/prev are no-ops
2. **No siblings (directory source or bare image)** — siblings list empty, no-ops
3. **Comic opened from file dialog to different dir** — rescan siblings on `_open_comic()`
4. **Directory contents change** — not tracked live; reflects state at open time
5. **Non-archive file opened** — `_sibling_comics` stays empty
6. **Path doesn't exist** — `_get_sibling_comics` returns `([], -1)` gracefully
7. **Permission errors scanning directory** — catch and return `([], -1)`
8. **Comic path has no parent (unlikely)** — guard against it

## Test Coverage Plan

### Unit tests for `_get_sibling_comics()`
- Directory with multiple archives, sorted naturally
- Directory with mixed files (archives + non-archives)
- Single archive in directory
- Empty directory
- Non-archive file (returns empty)
- Directory path (returns empty)
- Natural sort order verified (e.g., "issue2" before "issue10")

### Unit tests for `next_comic()` / `prev_comic()`
- Advances to next comic correctly
- Goes to previous comic correctly
- No-op at last comic (no wrap)
- No-op at first comic (no wrap)
- No-op when no siblings
- Calls `_open_comic()` with correct path

### Integration tests for auto-advance
- `next_page()` on last page triggers `next_comic()`
- `prev_page()` on first page triggers `prev_comic()`
- `_space_advance()` at bottom of last page triggers `next_comic()`
- Normal next/prev page still works when not at boundary

### Keybinding tests
- `n` key triggers `next_comic()`
- `p` key triggers `prev_comic()`

### Title bar tests
- Title shows `[2/5]` prefix with siblings
- Title shows no prefix without siblings

### Context menu tests
- Menu contains "Next comic" and "Previous comic" entries
