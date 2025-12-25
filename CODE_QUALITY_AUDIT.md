# Code Quality Audit Report
**Repository:** cdisplayagain
**Date:** 2024-12-24
**Auditor:** Code Audit Agent

---

## Executive Summary

The codebase is generally well-structured and follows PEP 8 conventions. However, there are several concerns around error handling, some workarounds that could be improved, and a few instances of sloppy code patterns. The code is functional but has accumulated some technical debt through pragmatic compromises.

---

## Critical Issues

### 1. Silent Exception Swallowing (Pervasive)

**Location:** Multiple locations throughout `cdisplayagain.py`

**Problem:** The code uses bare `except Exception: pass` in many places, which silently ignores all errors and hides bugs:

```python
# Lines 148-149 (load_cbz cleanup)
def cleanup():
    try:
        zf.close()
    except Exception:
        pass  # What if the file handle is corrupt?

# Lines 196-197 (load_cbr cleanup)
def cleanup():
    try:
        shutil.rmtree(tmpdir, ignore_errors=True)
    except Exception:
        pass

# Lines 237-238 (load_tar cleanup)
def cleanup():
    try:
        tf.close()
    except Exception:
        pass

# Lines 598-601 (_quit method)
try:
    if self.source and self.source.cleanup:
        self.source.cleanup()
finally:
    logging.info("Destroying app window.")
    self.master.destroy()
```

**Impact:** When cleanup fails, users have no way to know if temporary files are being left behind or resources are leaking. This violates the project ethos of keeping temporary files contained.

**Recommendation:** Log the exception or use specific exception types. At minimum:
```python
except Exception as e:
    logging.warning("Cleanup failed: %s", e)
```

---

### 2. Fake Page Placeholder for Empty Archives (Hack/Workaround)

**Location:** `cdisplayagain.py:288-294`

**Problem:** Empty CBR/TAR files return a fake placeholder page:

```python
if ext in {".cbr", ".rar", ".ace"}:
    if path.stat().st_size == 0:
        return PageSource(pages=["01.png"], get_bytes=lambda _: b"", cleanup=None)
    return load_cbr(path)
if ext == ".tar":
    if path.stat().st_size == 0:
        return PageSource(pages=["01.png"], get_bytes=lambda _: b"", cleanup=None)
    return load_tar(path)
```

**Impact:** This masks the real problem (empty/corrupt file) and returns fake data that the viewer will attempt to render. The user sees a blank page with no indication that the file is empty.

**Recommendation:** Raise a proper error or show an informational message to the user instead of silently returning a fake page.

---

### 3. Unbounded PIL Cache (Memory Leak Risk)

**Location:** `cdisplayagain.py:334`

**Problem:** The `_pil_cache` dictionary grows without bound:

```python
self._pil_cache: dict[str, Image.Image] = {}
```

**Impact:** When viewing large archives (hundreds or thousands of pages), this can cause unbounded memory growth. Each cached page can be several megabytes.

**Recommendation:** Implement an LRU cache with a reasonable max size (e.g., 10-20 pages):
```python
from functools import lru_cache
# Or implement a bounded cache manually
```

Note: The task board already has a card for this: "Add bounded image caching to prevent unbounded memory growth on large archives."

---

## Moderate Issues

### 4. Overly Complex ImageTk Initialization

**Location:** `cdisplayagain.py:426-462`

**Problem:** The `_prime_imagetk` method has 4 levels of nested type checking and exception handling:

```python
def _prime_imagetk(self) -> None:
    """Ensure Pillow's Tk bindings register the PyImagingPhoto command."""
    if self._imagetk_ready:
        return
    try:
        from PIL import _imagingtk
    except Exception:
        return  # Silent failure - why?

    tkapp = getattr(self, "tk", None)
    if not tkapp or not hasattr(tkapp, "interpaddr"):
        return

    try:
        interp_addr = tkapp.interpaddr()
    except Exception:
        return

    if isinstance(interp_addr, (bytes, bytearray)):
        interp_addr = int.from_bytes(interp_addr, sys.byteorder)
    elif isinstance(interp_addr, str):
        try:
            interp_addr = int(interp_addr, 0)
        except ValueError:
            return
    else:
        try:
            interp_addr = int(interp_addr)
        except Exception:
            return

    try:
        _imagingtk.tkinit(interp_addr)
    except TypeError:
        return

    self._imagetk_ready = True
```

**Impact:** This is fragile and hard to debug if initialization fails silently. Multiple `except Exception: return` patterns hide the root cause.

**Recommendation:** Consolidate error handling and log why initialization failed.

---

### 5. Performance Concern: Double-Encode for PhotoImage

**Location:** `cdisplayagain.py:464-469`

**Problem:** The fallback PhotoImage method does double-encoding:

```python
def _photoimage_from_pil(self, img: Image.Image) -> tk.PhotoImage:
    rgb = img.convert("RGB")
    buf = io.BytesIO()
    rgb.save(buf, format="PNG")
    encoded = base64.encodebytes(buf.getvalue()).decode("ascii")
    return tk.PhotoImage(data=encoded, format="PNG", master=self)
```

1. Image already in memory as PIL Image
2. Encoded as PNG to BytesIO
3. Base64 encoded as string
4. Passed to Tk which decodes the base64 then decodes PNG

**Impact:** Unnecessary CPU overhead and memory allocation. This is done every time a page is rendered.

**Recommendation:** Consider using PPM format (which Tk can handle natively without base64) or keep the pyvips/ImageTk.PhotoImage path working reliably.

---

### 6. Inconsistent Error Handling in require_unar()

**Location:** `cdisplayagain.py:29-43`

**Problem:** The function raises `SystemExit` instead of a proper exception, and error messages differ:

```python
def require_unar() -> None:
    """Ensure that 'unar' is available on the system for CBR support."""
    if shutil.which("unar"):
        return

    if sys.platform.startswith("linux"):
        hint = "sudo apt install unar"
    elif sys.platform == "darwin":
        hint = "brew install unar"
    else:
        hint = "Install 'unar' using your system package manager"

    raise SystemExit(
        f"CBR support requires the external tool 'unar'.\n\nInstall it with:\n  {hint}\n"
    )
```

**Impact:** Using `SystemExit` is unusual for a dependency check. Also, load_cbr() at line 158 raises a different message:
```python
raise RuntimeError("CBR support requires 'unar'. Install with: brew install unar")
```

**Recommendation:** Use consistent exception types and messages. Consider a custom `DependencyError` exception.

---

## Minor Issues

### 7. Platform-Specific Hardcoded Install Hints

**Location:** `cdisplayagain.py:34-39`

**Problem:** Platform-specific install commands are hardcoded:

```python
if sys.platform.startswith("linux"):
    hint = "sudo apt install unar"
elif sys.platform == "darwin":
    hint = "brew install unar"
else:
    hint = "Install 'unar' using your system package manager"
```

**Impact:** "Linux" != "apt". Users on Fedora, Arch, etc. get incorrect guidance.

**Recommendation:** Either remove specific package manager hints or make them more accurate.

---

### 8. Aggressive Logging (Performance)

**Location:** `cdisplayagain.py:495-503, 647-657`

**Problem:** Every key press and mouse event is logged:

```python
def _log_key_event(self, event) -> None:
    logging.info(
        "KeyPress keysym=%s char=%s keycode=%s state=%s widget=%s",
        event.keysym,
        repr(event.char),
        event.keycode,
        event.state,
        event.widget,
    )

def _log_mouse_event(self, event) -> None:
    logging.info(
        "Mouse event type=%s num=%s delta=%s x=%s y=%s state=%s widget=%s",
        event.type,
        getattr(event, "num", None),
        getattr(event, "delta", None),
        event.x,
        event.y,
        event.state,
        event.widget,
    )
```

**Impact:** Log files can grow very large during active use. This is useful for debugging but should be optional.

**Recommendation:** Consider a debug flag or log level configuration.

---

### 9. Cursor Configuration Trial-and-Error

**Location:** `cdisplayagain.py:374-401`

**Problem:** Cursor configuration uses try-except as a control flow mechanism:

```python
def _configure_cursor(self) -> None:
    """Use a minimal cursor to mimic CDisplay's pointer."""
    for cursor_name in ("none", "dotbox", "arrow"):
        try:
            self.configure(cursor=cursor_name)
            self._cursor_name = cursor_name
            return
        except tk.TclError:
            continue
```

**Impact:** Using exceptions for control flow is generally discouraged, though in this specific case with Tk's limited introspection, it's pragmatic.

**Recommendation:** Keep as-is for pragmatic reasons, but document why this pattern is used.

---

### 10. Fragile Fullscreen State Tracking

**Location:** `cdisplayagain.py:403-417`

**Problem:** Two ways to get fullscreen state, with fallback:

```python
def toggle_fullscreen(self) -> None:
    logging.info("Toggle fullscreen requested.")
    try:
        current = self.master.attributes("-fullscreen")
        current = bool(int(current))
    except Exception:
        current = self._fullscreen
    new_state = not current
    self._fullscreen = new_state
    try:
        self.master.attributes("-fullscreen", new_state)
    except tk.TclError:
        return
    self._set_cursor_hidden(new_state)
```

**Impact:** Redundant state tracking suggests uncertainty about Tk's behavior.

**Recommendation:** Pick one authoritative source of truth for fullscreen state.

---

### 11. Unused Parameter in get_bytes

**Location:** `cdisplayagain.py:273`

**Problem:** Parameter is unused:

```python
def get_bytes(_: str) -> bytes:
    return path.read_bytes()
```

**Impact:** Slight code smell - suggests the lambda/closure pattern could be clearer.

**Recommendation:** Use a more descriptive name or document why the parameter is ignored.

---

### 12. winfo_children() Filters Out Menus

**Location:** `cdisplayagain.py:820-823`

**Problem:** This method intentionally filters out `tk.Menu` instances:

```python
def winfo_children(self):
    """Return widget children, omitting internal menus."""
    children = super().winfo_children()
    return [child for child in children if not isinstance(child, tk.Menu)]
```

**Impact:** This breaks Liskov Substitution Principle - callers expect `winfo_children()` to return all children. The comment suggests this is for tests.

**Recommendation:** If this is for testing, consider a test-specific helper instead of overriding a standard Tk method.

---

### 13. Commented Out Code in Tests

**Location:** `tests/test_ui_bindings.py:14`

**Problem:**

```python
# root.withdraw()  <-- Removing this so it is visible
```

**Impact:** Commented-out code should be removed. If there's a reason to keep the window visible, the comment should explain why.

**Recommendation:** Either remove the commented line or add a proper comment explaining the decision.

---

### 14. Duplicate Documentation Entry

**Location:** `AGENTS.md:16-17`

**Problem:** Two identical lines:

```markdown
- `uv run python cdisplayagain.py path/to/comic.cbz`: open a specific archive immediately, useful for manual regression runs.
- `uv run python cdisplayagain.py path/to/comic.cbz`: alternative if you prefer the fast `uv` workflow already tracked via `uv.lock`.
```

**Impact:** Copy-paste error, causes confusion.

**Recommendation:** Remove one of the duplicates or clarify the difference.

---

### 15. Unnecessary Image Save/Reopen

**Location:** `cdisplayagain.py:775-779`

**Problem:**

```python
buf = io.BytesIO()
img.save(buf, format="PNG")
raw_bytes = buf.getvalue()
resized_bytes = get_resized_bytes(raw_bytes, new_w, new_h)
resized = Image.open(io.BytesIO(resized_bytes))
```

The image is already a PIL Image (line 759). It's saved as PNG, then get_resized_bytes decodes it again (either via pyvips or Pillow).

**Impact:** Unnecessary encode/decode cycle. If `img` is already decoded, passing it directly to a resize function would be more efficient.

**Recommendation:** This is likely intentional for consistency (all resize paths go through get_resized_bytes), but worth reviewing for optimization opportunities.

---

## Acceptable Patterns

These are pragmatic compromises that, while not ideal, are acceptable given the constraints:

### Placeholder Methods (Lines 929-974)

```python
def set_one_page_mode(self) -> None:
    """Provide placeholder for single-page mode parity."""
    return None
```

**Assessment:** These are explicitly documented as placeholders for CDisplay parity. They're tested (in `test_parity_tasks.py`) and serve as API contracts while the actual features are being implemented. This is acceptable as long as they're tracked in the task board.

### Cross-Platform Mouse Wheel Handling

**Location:** `cdisplayagain.py:642-645`

```python
self.canvas.bind("<MouseWheel>", self._on_mouse_wheel)
# Bind for Linux scrolling (if needed, though MouseWheel usually covers modern Tk)
self.canvas.bind("<Button-4>", self._on_mouse_wheel)
self.canvas.bind("<Button-5>", self._on_mouse_wheel)
```

**Assessment:** Different platforms report mouse wheel events differently. Binding all possibilities ensures cross-platform compatibility. This is pragmatic and acceptable.

### Image Mode Normalization

**Location:** `cdisplayagain.py:710-713`

```python
if img.mode not in ("RGB", "RGBA"):
    img = img.convert("RGBA")
```

**Assessment:** Tk has limited format support. Converting to RGBA ensures consistency. This is a reasonable guard.

---

## Code Smells (Non-Critical)

### 16. Inconsistent Return Statement Style

Some methods use explicit `return None` while others rely on implicit returns:
- Line 931: `return None`
- Line 935: `return None`
- Line 943: `return None`

**Recommendation:** Pick one style consistently.

### 17. Lambda Without Type Hints

**Location:** Line 289

```python
return PageSource(pages=["01.png"], get_bytes=lambda _: b"", cleanup=None)
```

The PageSource type annotation says `get_bytes: callable` but lambda usage makes this less explicit.

**Recommendation:** Use `Callable[[], bytes]` or similar for better type safety.

### 18. Multiple Bindings for Same Key

**Location:** Lines 486-487, 488-489, 490-491

```python
self.bind_all("q", lambda e: self._quit())
self.bind_all("Q", lambda e: self._quit())
self.bind_all("x", lambda e: self._quit())
self.bind_all("m", lambda e: self._minimize())
self.bind_all("w", lambda e: self.toggle_fullscreen())
self.bind_all("W", lambda e: self.toggle_fullscreen())
self.bind_all("l", lambda e: self._open_dialog())
self.bind_all("L", lambda e: self._open_dialog())
```

**Assessment:** Intentional for case-insensitive shortcuts. Acceptable but could be cleaner with a helper.

---

## Test Quality Issues

### 19. Aggressive Mocking in Tests

**Location:** `tests/test_ui_bindings.py:23-66`

**Problem:** The test heavily mocks internal methods, including Tk calls:

```python
with patch("tkinter.filedialog.askopenfilename", return_value="dummy.cbz"),
    patch("tkinter.filedialog.askopenfilenames", return_value=["dummy.cbz"]),
    patch("tkinter.messagebox.showerror"),
    patch("tkinter.messagebox.showinfo"),
```

**Impact:** This makes tests brittle and coupled to implementation details. AGENTS.md says: "When using fakes, mirror the real ComicViewer interface rather than relaxing production code."

**Recommendation:** Consider integration tests that actually create windows on a virtual display (like xvfb).

---

## Summary by Category

| Category | Critical | Moderate | Minor | Acceptable |
|----------|----------|----------|-------|------------|
| Error Handling | 3 (silent exceptions, fake pages, unbounded cache) | 1 (complex init) | - | - |
| Performance | 1 (unbounded cache) | 1 (double-encode) | 1 (logging) | - |
| Code Quality | - | - | 6 (platform hints, cursor, fullscreen, etc.) | 3 (placeholders, mouse wheel, mode normalize) |
| Documentation | 1 (duplicate in AGENTS.md) | - | 2 (comment in test, weak comments) | - |
| Testing | - | 1 (aggressive mocking) | 1 (commented code) | - |

---

## Priority Action Items

1. **HIGH:** Replace bare `except Exception: pass` with logging or specific exception handling (Issue #1)
2. **HIGH:** Implement bounded PIL cache to prevent memory leaks (Issue #3)
3. **HIGH:** Remove or improve the fake page placeholder for empty archives (Issue #2)
4. **MEDIUM:** Consolidate ImageTk initialization with proper error logging (Issue #4)
5. **MEDIUM:** Review and optimize the double-encode PhotoImage fallback (Issue #5)
6. **LOW:** Fix duplicate documentation in AGENTS.md (Issue #14)
7. **LOW:** Remove commented code in tests (Issue #13)
8. **LOW:** Make require_unar() consistent across the codebase (Issue #6)

---

## Overall Assessment

**Grade:** B- (Good but with technical debt)

The codebase is functional and follows most conventions, but has accumulated pragmatic workarounds that have become technical debt. The most serious issues are:

1. **Silent error handling** that could hide resource leaks
2. **Unbounded caching** that could cause memory issues
3. **Fake data returns** that mask real user-facing problems

These issues don't prevent the application from working, but they reduce maintainability and reliability. The good news is that most issues are isolated and can be addressed incrementally.

The test coverage is good (74% threshold in pyproject.toml), but some tests rely heavily on mocking which makes them brittle.

**Recommendation:** Address the high-priority items first, especially the silent exception swallowing and unbounded cache. These are the most likely to cause user-facing issues.
