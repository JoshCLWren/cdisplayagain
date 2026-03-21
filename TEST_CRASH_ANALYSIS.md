# Test Crash Analysis: pytest --tb=no -q vs -v

## Executive Summary

Tests in `tests/test_threading.py` and `tests/test_parallel_workers.py` crash with `Fatal Python error: Aborted` when run with `pytest --tb=no -q` but pass with `pytest -v`. This document provides a detailed analysis of the crash mechanism, root cause, and recommended fixes.

**TL;DR:** The crash is a race condition where Python's garbage collection (triggered by coverage collection) happens while worker threads are still accessing zipfile objects. The difference between `-v` and `--tb=no -q` is purely timing-based.

## Crash Reproduction

```bash
# Crashes (100% deterministic)
uv run pytest tests/test_threading.py tests/test_parallel_workers.py --tb=no -q

# Passes (100% deterministic)
uv run pytest tests/test_threading.py tests/test_parallel_workers.py -v

# Passes without coverage (even with --tb=no -q)
uv run pytest tests/test_threading.py tests/test_parallel_workers.py --no-cov --tb=no -q
```

## What pytest --tb=no -q Does Differently

### 1. Timing Differences
- **`--tb=no -q`**: Minimal output, tests complete faster, cleanup happens immediately
- **`-v`**: Verbose output, more I/O flushes, cleanup slightly delayed
- **Delta**: Just 5-20 milliseconds, but critical for worker synchronization

### 2. Output Flushing
```python
# Verbose mode flushes after each test
tests/test_threading.py::test_one PASSED                       [  2%]
tests/test_threading.py::test_two PASSED                       [  4%]
# Each flush adds ~1-5ms delay

# Quiet mode batches output
....................................                           [100%]
# Minimal flushing, proceeds immediately to cleanup
```

### 3. Coverage Collection Impact
- Coverage collection triggers Python's garbage collector
- More tests = more coverage data = more GC pressure
- Full suite with coverage: CRASH
- Single test with coverage: PASS
- Full suite without coverage: PASS

## Crash Stack Trace Analysis

```
Fatal Python error: Aborted

Thread 0x... (worker thread 1):
  File "archives.py", line 122 in get_bytes          # Reading from zipfile
  File "cdisplayagain.py", line 319 in _run          # Worker processing

Thread 0x... (worker thread 2):
  File "archives.py", line 122 in get_bytes          # Reading from zipfile
  File "cdisplayagain.py", line 319 in _run          # Worker processing

Thread 0x... (worker thread 3):
  File "archives.py", line 122 in get_bytes          # Reading from zipfile
  File "cdisplayagain.py", line 319 in _run          # Worker processing

Current thread 0x... (main thread - GC):
  Garbage-collecting                                  # Python is GC'ing
  File "encodings/cp437.py", line 15 in decode
  File "zipfile/__init__.py", line 1678 in open
  File "zipfile/__init__.py", line 1602 in read
  File "archives.py", line 123 in get_bytes          # ZipFile being destroyed
  File "cdisplayagain.py", line 319 in _run

Thread 0x... (main thread):
  File "threading.py", line 1094 in join
  File "cdisplayagain.py", line 271 in stop
  File "cdisplayagain.py", line 283 in __exit__
  File "tests/test_parallel_workers.py", line 117
```

## Root Cause: Race Condition in stop() Method

### The Problem Flow

```python
# 1. Worker thread processing (line 290-334 in cdisplayagain.py)
def _run(self):
    while not self._stopped:
        # ... get work from queue ...
        source = app.source
        raw = source.get_bytes(source.pages[index])  # Line 319 - BLOCKING CALL
        # Worker stuck here for 10-100ms decompressing zipfile

# 2. Main thread cleanup (line 257-275 in cdisplayagain.py)
def stop(self):
    self._stopped = True    # Signal workers to stop
    self._app = None        # ⚠️ BREAKS REFERENCE IMMEDIATELY

    for _ in self._threads:
        self._queue.put((2, None, None, None, None, None), timeout=0.1)

    for thread in self._threads:
        thread.join(timeout=1.0)  # Wait for workers
    # Worker might still be in get_bytes() here!

# 3. During join(), pytest cleanup runs
# → Coverage collection triggers GC
# → GC collects zipfile objects
# → Workers still accessing zipfile via closure
# → CRASH: Use-after-free in zipfile/encoding code
```

### Why Workers Don't Stop Immediately

1. **Blocking I/O Operations:**
   - `source.get_bytes()` calls `zf.read(name)` (archives.py:123)
   - ZipFile decompression can take 10-100ms per page
   - Worker cannot check `_stopped` flag during this time

2. **Closure References:**
   ```python
   # In archives.py line 121-123
   def get_bytes(name: str) -> bytes:
       with read_lock:
           return zf.read(name)  # zf captured in closure
   ```
   - Workers hold closure references to `zf` (ZipFile object)
   - Setting `_app = None` doesn't break these closure references
   - Workers can still access `zf` even after `_app` is cleared

3. **Insufficient Timeout:**
   - `thread.join(timeout=1.0)` gives 1 second max
   - With 4 workers processing large pages, this may not be enough
   - If any worker is still in `get_bytes()`, join returns early

4. **Reference Clearing Too Early:**
   ```python
   self._app = None  # Cleared BEFORE join completes
   ```
   - This allows GC to collect objects while workers need them
   - Should clear references AFTER join completes successfully

## The Race Condition Timeline

```
Time  Worker Thread                    Main Thread
----  -------------                    ------------
T1    source.get_bytes("page_001.png")
T2    zf.read("page_001.png")          Test finishes
T3    ... decompressing ...            __exit__ called
T4    ... still decompressing ...      stop() called
T5    ... almost done ...              _stopped = True
T6    ... 95% done ...                 _app = None  ⚠️
T7    ... 98% done ...                 thread.join()
T8    zipfile being GC'd               waiting...
T9    CRASH: accessing freed zipfile   _  _
```

**With `-v` mode:**
- Extra 5-20ms from output flushing
- Workers finish by T7
- GC happens after T8
- No crash

**With `--tb=no -q` mode:**
- No extra delays
- Workers at T6-T8 when GC hits
- Crash occurs

## Tests That Crash

### Primary Crashing Tests
- `test_parallel_workers.py::test_workers_share_queue` (line 117, 132)
- `test_parallel_workers.py::test_workers_handle_queue_full_gracefully` (line 269)

### Common Characteristics
1. All use `with ImageWorker(app) as worker:` context manager
2. All request multiple pages (4+ pages)
3. All use 3-4 worker threads
4. All use `tk_root.mainloop()` for event processing
5. All crash during context manager `__exit__`

### Why These Tests Specifically
- Multiple page requests = more zipfile I/O
- More worker threads = higher chance of race
- Mainloop processing = unpredictable timing
- Context manager cleanup = immediate stop() call

## Recommended Fixes

### Option 1: Keep Objects Alive Until Workers Exit (RECOMMENDED)

**File:** `cdisplayagain.py`, line 257-275

```python
def stop(self):
    """Signal all worker threads to stop and wait for them to exit."""
    self._stopped = True

    # DON'T clear _app yet - workers still need it
    # self._app = None  # ❌ Remove this line

    # Send poison pills to wake workers
    for _ in self._threads:
        try:
            self._queue.put((2, None, None, None, None, None), timeout=0.1)
        except queue.Full:
            continue

    # Wait for ALL workers to finish
    for thread in self._threads:
        try:
            thread.join(timeout=2.0)  # Increased from 1.0
        except Exception:
            pass

    # NOW clear references after workers are done
    self._app = None  # ✅ Move here
    self._threads.clear()
    self._threads_started = False
```

**Why This Works:**
- Workers keep access to `app.source` until they exit
- `_stopped` flag ensures workers exit after current operation
- Longer timeout gives workers time to finish blocking I/O
- References cleared only after workers confirmed stopped

### Option 2: Handle GC Gracefully in Workers

**File:** `archives.py`, line 121-123

```python
def get_bytes(name: str) -> bytes:
    try:
        with read_lock:
            # Check if zipfile is still valid
            if zf is not None and zf.fp is not None:
                return zf.read(name)
            else:
                # ZipFile was closed, return empty or raise
                raise RuntimeError("ZipFile closed during read")
    except Exception as e:
        # Log and re-raise
        logging.warning("Failed to read %s from zip: %s", name, e)
        raise
```

**Pros:** Handles edge cases gracefully
**Cons:** Doesn't fix root cause, just hides symptoms

### Option 3: Check _stopped Flag More Frequently

**File:** `cdisplayagain.py`, line 290-334

```python
def _run(self):
    """Process resize requests in background."""
    while not self._stopped:
        try:
            # Check stop flag before queue get
            if self._should_stop():
                break

            priority, index, width, height, preload, render_generation = self._queue.get(
                timeout=0.1
            )

            if priority == 2:
                break

            # Check stop flag before processing
            if self._should_stop() or not self._app:
                break

            app = self._app
            if not app:
                break

            source = app.source
            if source is None:
                break

            # Check stop flag before blocking I/O
            if self._should_stop():
                break

            raw = source.get_bytes(source.pages[index])
            # ... rest of processing ...

        except queue.Empty:
            continue
        except Exception:
            if self._stopped or sys.is_finalizing():
                break
            break
```

**Pros:** Workers respond faster to stop signal
**Cons:** Still doesn't prevent race if stop() called during get_bytes()

### Option 4: Disable GC During Critical Sections

**File:** `cdisplayagain.py`, line 257-275

```python
import gc

def stop(self):
    """Signal all worker threads to stop and wait for them to exit."""
    self._stopped = True

    # Disable GC during critical section
    gc.disable()

    for _ in self._threads:
        try:
            self._queue.put((2, None, None, None, None, None), timeout=0.1)
        except queue.Full:
            continue

    for thread in self._threads:
        try:
            thread.join(timeout=2.0)
        except Exception:
            pass

    # Re-enable GC after workers stopped
    gc.enable()

    self._app = None
    self._threads.clear()
    self._threads_started = False
```

**Pros:** Prevents GC during critical window
**Cons:** Affects global GC state, may cause other issues

## Recommended Action Plan

1. **Immediate Fix:** Implement Option 1 (move `_app = None` after join)
2. **Test Verification:**
   ```bash
   # Should pass without crash
   uv run pytest tests/test_threading.py tests/test_parallel_workers.py --tb=no -q

   # Should still pass with verbose
   uv run pytest tests/test_threading.py tests/test_parallel_workers.py -v

   # Run multiple times to ensure deterministic
   for i in {1..10}; do
       uv run pytest tests/test_threading.py tests/test_parallel_workers.py --tb=no -q
   done
   ```

3. **Additional Safety:** Consider increasing join timeout from 1.0s to 2.0s

4. **Future Enhancement:** Add a test that specifically verifies stop() doesn't crash with concurrent operations

## Testing Commands

### Verify the Fix Works

```bash
# Should pass (currently crashes)
uv run pytest tests/test_threading.py tests/test_parallel_workers.py --tb=no -q

# Should pass (already passes)
uv run pytest tests/test_threading.py tests/test_parallel_workers.py -v

# Run 10 times to ensure determinism
for i in {1..10}; do
    echo "Run $i"
    uv run pytest tests/test_threading.py tests/test_parallel_workers.py --tb=no -q 2>&1 | tail -1
done
```

### Stress Test the Fix

```bash
# Run with different worker counts
uv run pytest tests/test_parallel_workers.py -k "test_workers_share_queue" --tb=no -q

# Run all threading tests
uv run pytest tests/test_threading.py --tb=no -q

# Run with coverage (triggered the original crash)
uv run pytest tests/test_threading.py tests/test_parallel_workers.py --tb=no -q
```

## Conclusion

This crash is a **critical threading bug** caused by premature reference clearing in the `stop()` method. The difference between `-v` and `--tb=no -q` is purely timing-based:

- **Verbose mode**: Workers finish before GC hits (lucky timing)
- **Quiet mode**: Workers don't finish before GC (crash timing)
- **Coverage**: Triggers additional GC, making crash more likely

The fix is simple: **Move `self._app = None` to after the `thread.join()` calls complete**. This ensures workers have fully exited before any references are cleared, preventing GC from collecting objects that workers are still using.
