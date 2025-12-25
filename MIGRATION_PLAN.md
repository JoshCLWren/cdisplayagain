# Migration Plan: pyvips + Threading + LRU Cache + Debounce

**Status:** Partially Complete (pyvips implemented, threading pending)
**Created:** December 24, 2025
**Goal:** 3-5x performance improvement while keeping UI responsive

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                    Main Thread (Tkinter)                     │
│  ┌────────────┐  ┌─────────────┐  ┌──────────────┐  │
│  │   Canvas   │  │  LRU Cache  │  │   Debounce   │  │
│  └─────┬──────┘  └──────┬──────┘  └──────┬───────┘  │
│        │                 │                  │              │
│        │                 │                  │              │
└────────┼─────────────────┼──────────────────┼──────────────┘
         │                 │                  │
         │                 │                  │
         │                 │                  │
         │                 │                  ▼
         │                 │          Page Change Request
         │                 │                  │
         │                 │                  │
         │                 ▼                  │
         │          ┌──────────────┐        │
         │          │  Queue API  │◄───────┘
         │          └──────┬───────┘
         │                 │
         │                 │
┌────────┼─────────────────┼──────────────────────────────────────┐
│         │                 │                                  │
│         ▼                 ▼                                  │
│  ┌─────────────────────────────────┐                      │
│  │  Image Worker Thread (Daemon)  │                      │
│  │  ┌─────────────────────────┐   │                      │
│  │  │1. Load raw bytes    │   │                      │
│  │  │2. pyvips.resize()   │   │                      │
│  │  │3. Store in LRU      │   │                      │
│  │  │4. Signal ready      │   │                      │
│  │  └─────────────────────────┘   │                      │
│  └─────────────────────────────────┘                      │
└──────────────────────────────────────────────────────────────────┘
```

---

## Phase 1: Dependencies (5 minutes)

### 1.1 Add pyvips to pyproject.toml
```toml
[project]
dependencies = [
    "pillow>=12.0.0",  # Keep for ImageTk conversion
    "pyvips>=2.2.0",    # NEW: Fast image backend
    "pytest>=9.0.2",
    "ruff>=0.11.2",
]
```

### 1.2 Installation

**System dependencies:**
- Linux: `sudo apt install libvips`
- macOS: `brew install vips`
- Windows: Download from libvips.org or `conda install -c conda-forge pyvips`

---

## Phase 2: Image Resizing Backend (2 hours)

### 2.1 Create image_backend.py
New file: `cdisplayagain/image_backend.py`

```python
"""Image processing backend using pyvips for fast operations."""

import io
import functools
from typing import Optional, Tuple

try:
    import pyvips
    HAS_PYVIPS = True
except ImportError:
    HAS_PYVIPS = False

# Fallback to Pillow if pyvips unavailable
from PIL import Image


# LRU Cache for resized images: (page_name, width, height) -> bytes
@functools.lru_cache(maxsize=32)
def get_resized_bytes(
    raw_bytes: bytes, 
    target_width: int, 
    target_height: int
) -> bytes:
    """Resize image bytes using pyvips (fast) or Pillow (fallback)."""
    if HAS_PYVIPS:
        return _resize_with_pyvips(raw_bytes, target_width, target_height)
    return _resize_with_pillow(raw_bytes, target_width, target_height)


def _resize_with_pyvips(raw_bytes: bytes, width: int, height: int) -> bytes:
    """Fast resize using libvips via pyvips."""
    # First decode to get dimensions
    temp_img = Image.open(io.BytesIO(raw_bytes))
    img_w, img_h = temp_img.size
    
    img = pyvips.Image.new_from_buffer(
        raw_bytes, img_w, img_h, bands=3, format="RGB"
    )
    resized = img.resize(width, height, kernel='lanczos3')
    return resized.write_to_buffer('.png')


def _resize_with_pillow(raw_bytes: bytes, width: int, height: int) -> bytes:
    """Fallback resize using Pillow."""
    img = Image.open(io.BytesIO(raw_bytes))
    resized = img.resize((width, height), Image.Resampling.LANCZOS)
    buf = io.BytesIO()
    resized.save(buf, format="PNG")
    return buf.getvalue()
```

### 2.2 Integrate into ComicViewer
Modify `cdisplayagain.py`:
```python
from image_backend import get_resized_bytes  # NEW import
```

---

## Phase 3: Threading Architecture (3 hours)

### 3.1 Thread-safe Queue API
Add to `cdisplayagain.py`:

```python
import queue
import threading
import time

class ImageWorker:
    """Background thread for image processing."""
    
    def __init__(self, app):
        self._app = app
        self._queue = queue.Queue(maxsize=4)  # Limit queue depth
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()
    
    def request_page(self, index: int, width: int, height: int):
        """Request a page be processed."""
        try:
            self._queue.put_nowait((index, width, height))
        except queue.Full:
            pass  # Queue full, skip
    
    def _run(self):
        """Process resize requests in background."""
        while True:
            try:
                index, width, height = self._queue.get()
                
                # Get raw image bytes
                raw = self._app.source.get_bytes(self._app.source.pages[index])
                
                # Resize using pyvips (cached via LRU)
                resized_bytes = get_resized_bytes(raw, width, height)
                
                # Signal main thread to update
                self._app.after_idle(lambda: self._app._update_from_cache(index, resized_bytes))
                
            except Exception as e:
                logging.error("Image worker error: %s", e)
```

### 3.2 Integrate Worker into ComicViewer
```python
class ComicViewer(tk.Frame):
    def __init__(self, master: tk.Tk, comic_path: Path):
        # ... existing init ...
        
        self._worker = ImageWorker(self)
        self._pending_index: Optional[int] = None
```

---

## Phase 4: Debounce Logic (1 hour)

### 4.1 Debounce Helper
Add to `cdisplayagain.py`:

```python
class Debouncer:
    """Debounce rapid-fire events."""
    
    def __init__(self, delay_ms: int, callback: Callable, app):
        self._delay = delay_ms
        self._callback = callback
        self._app = app
        self._timer_id: Optional[int] = None
    
    def trigger(self, *args, **kwargs):
        """Trigger callback after delay (reset if already pending)."""
        if self._timer_id:
            self._app.after_cancel(self._timer_id)
        
        def wrapper():
            self._callback(*args, **kwargs)
            self._timer_id = None
        
        self._timer_id = self._app.after(self._delay, wrapper)
```

### 4.2 Apply to Navigation
```python
def __init__(self, ...):
    # ...
    self._nav_debounce = Debouncer(150, self._execute_page_change, self)  # 150ms debounce
    
    # Update navigation methods
    self.bind_all("<Right>", lambda e: self._trigger_next())
    self.bind_all("<Left>", lambda e: self._trigger_prev())
    self.bind_all("<space>", lambda e: self._trigger_space())

def _trigger_next(self):
    self._nav_debounce.trigger(lambda: self.next_page())

def _trigger_prev(self):
    self._nav_debounce.trigger(lambda: self.prev_page())

def _trigger_space(self):
    self._nav_debounce.trigger(lambda: self._space_advance())

def _execute_page_change(self, action):
    """Actually execute debounced action."""
    action()
```

---

## Phase 5: Render Pipeline Updates (2 hours)

### 5.1 Cache-First Render
Modify `_render_current()`:

```python
def _render_current(self):
    """Check cache first, queue worker if missing."""
    if not self.source:
        return
    
    index = self._current_index
    name = self.source.pages[index]
    
    if is_text_name(name):
        self._render_info_with_image(name)
        return
    
    # Check if we have resized bytes in memory cache
    cache_key = (name, self.canvas.winfo_width(), self.canvas.winfo_height())
    
    # First try: display from cache if available
    cached = self._image_cache.get(cache_key)
    if cached:
        self._display_cached_image(cached)
        return
    
    # Queue background resize
    self._worker.request_page(index, self.canvas.winfo_width(), self.canvas.winfo_height())
    
    # Show placeholder or keep current image
```

### 5.2 Display from Cache
```python
def _display_cached_image(self, resized_bytes: bytes):
    """Display image from cache (fast path)."""
    img = Image.open(io.BytesIO(resized_bytes))
    tk_img = ImageTk.PhotoImage(img, master=self)
    self._tk_img = tk_img
    self._update_title()
    
    # Canvas update logic
    cw = max(1, self.canvas.winfo_width())
    ch = max(1, self.canvas.winfo_height())
    self.canvas.delete("all")
    
    # Positioning logic (simplified, needs full implementation)
    x = cw // 2
    y = ch // 2
    self.canvas.create_image(x, y, image=tk_img, anchor="center")
```

---

## Phase 6: Smart Preloading (1 hour)

### 6.1 Preload Next Page
```python
def _render_current(self):
    # ... render current page ...
    
    # Preload next page in background
    next_idx = index + 1
    if next_idx < len(self.source.pages):
        self._worker.preload(next_idx)
```

### 6.2 Update ImageWorker
```python
def preload(self, index: int):
    """Preload next page at reduced priority."""
    try:
        self._queue.put_nowait((index, 0, 0, True))  # True = preload
    except queue.Full:
        pass
```

---

## Phase 7: Testing Strategy (2 hours)

### 7.1 Performance Benchmarks
```bash
# Test with existing files
make profile-cbz  # Should see significant improvement
make profile-cbr
```

### 7.2 Manual Testing Checklist
- [ ] Rapid spacebar holding (verify debounce works)
- [ ] Page forward/back navigation (verify cache hits)
- [ ] Large archives (100+ pages) - verify LRU size
- [ ] CBR extraction still works
- [ ] Info screens still display correctly
- [ ] Window resize triggers cache invalidation
- [ ] Memory usage stays reasonable

### 7.3 Unit Tests
Add to `tests/test_performance.py`:
```python
def test_pyvips_available():
    """Verify pyvips is available."""
    import image_backend
    assert image_backend.HAS_PYVIPS

def test_lru_cache_hit():
    """Verify LRU cache works for repeated requests."""
    from image_backend import get_resized_bytes
    raw = b"fake_image_data"
    # First call (miss)
    result1 = get_resized_bytes(raw, 1920, 1080)
    # Second call (hit - from cache)
    result2 = get_resized_bytes(raw, 1920, 1080)
    assert result1 == result2
```

---

## Phase 8: Rollout Plan

### 8.1 Safe Migration Steps
1. **Feature flag**: Add `USE_PYVIPS = True` constant
2. **Gradual rollout**: Start with Pillow as baseline, test pyvips
3. **A/B testing**: Run both and compare profiles
4. **Fallback path**: Keep Pillow code for systems without pyvips

### 8.2 Rollback Plan
- Keep `image_backend.py` with HAS_PYVIPS check
- Always fall back to Pillow if pyvips unavailable
- Add logging to detect fallback events
- Monitor crash reports for pyvips issues

---

## Expected Performance Improvements

| Operation | Before | After | Improvement |
|-----------|:--------|:-------|:------------|
| Resize (pyvips) | 4.4s | 0.8-1.5s | **3-5x faster** |
| Cache hit (back) | 4.4s | <0.1s | **40x faster** |
| Debounce (spam) | N/A (flood) | 1 request | **Responsive** |
| UI thread | Blocked | Free | **Smooth** |

**Total page turn:** ~6s → **~1-2s** (cached), **~1.5-2.5s** (new)

---

## Risks & Mitigations

| Risk | Impact | Mitigation |
|------|:--------|:------------|
| pyvips not installed | Fallback to Pillow | HAS_PYVIPS flag, logging |
| Thread race conditions | Crash | Queue-based API, GIL safety |
| Memory bloat (LRU) | OOM | Limit to 32 entries, clear on exit |
| Tkinter thread safety | Crash | Only update UI via `after_idle()` |
| Queue overflow | Missed requests | maxsize=4, silent drop on full |
| Cache key collision | Wrong image displayed | Include dimensions in cache key |

---

## Implementation Priority

1. **High:** pyvips backend + LRU cache (biggest win: 3-5x speedup)
2. **High:** Threading (responsiveness: unblocks UI)
3. **Medium:** Debounce (spam protection: prevents queue overflow)
4. **Low:** Smart preloading (nice-to-have: further optimization)

---

## Next Steps

1. Run `make sync-vips` to install pyvips
2. Create `image_backend.py` with pyvips wrapper
3. Implement ImageWorker class
4. Add Debouncer for navigation
5. Update render pipeline to use cache-first approach
6. Test with existing comic files
7. Compare new profiles with baseline

---

## Notes

- pyvips uses streaming architecture, ideal for sequential comic reading
- LRU cache size of 32 should cover typical reading patterns (back/forward)
- 150ms debounce balance: responsive enough for normal use, prevents spam
- Queue depth of 4 limits memory while allowing some preloading
- All UI updates must happen via `after_idle()` for thread safety
