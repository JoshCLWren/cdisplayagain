# CI Threading Crash Fix - Session Summary

## Problem
CI tests were failing with threading crashes during pytest collection/execution. Threads were stuck in `queue.get()` calls causing Python to abort.

```
Fatal Python error: Aborted
Thread X: File "queue.py", line 180 in get
         File "cdisplayagain.py", line 424 in _run
```

## Attempted Solutions

### 1. Try/Finally Blocks ✅ (Commit: e179690)
- Added `try/finally` blocks to 16 tests across 3 files
- Ensures `worker.stop()` is called before Tk root destruction
- **Result**: Tests pass locally, CI still crashes
- **Issue**: Too verbose, not Pythonic

### 2. Context Manager ✅ (Commit: c19ea81)
- Converted `ImageWorker` to a context manager
- Added `__enter__` and `__exit__` methods
- Updated tests to use `with ImageWorker() as worker:` pattern
- **Result**: Tests pass locally (411 passed, 95.99% coverage)
- **Issue**: CI still crashes with same threading errors

### 3. Worker Thread Safety Improvements
- Added `_stopped` flag to `ImageWorker`
- Added early exit checks in `_run()` loop
- Set `self._app = None` in `stop()` to prevent access after cleanup
- Added exception handling in `thread.join()`
- **Current State**: Tests pass locally, but:
  - Pyright type checking fails on 2 lines (app._app could be None)
  - CI is likely still failing

## Root Cause Analysis

The issue appears to be that even with context managers, worker threads are processing tasks when the Tk root is destroyed during test teardown. The threads are:
1. Stuck in `queue.get()` waiting for work
2. Or in the middle of processing (calling `get_resized_pil()`)
3. Trying to access Tk (`after_idle`) when Tk is already destroyed

## Current Code State

### ImageWorker Changes
```python
class ImageWorker:
    _app: ComicViewer | None = None

    def __init__(self, app, num_workers: int = 4):
        self._app = app
        self._stopped: bool = False
        # ... start threads

    def stop(self):
        self._stopped = True
        self._app = None  # Prevent access after cleanup
        # ... send stop signals to queue

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.stop()
        return False
```

### ComicViewer Changes
```python
class ComicViewer(tk.Frame):
    def __del__(self):
        self.cleanup()

    def cleanup(self):
        if hasattr(self, "_worker") and self._worker:
            self._worker.stop()
```

## Remaining Issues

### Type Checking Errors ✅ FIXED
- Added `assert app is not None` after null check to satisfy pyright
- Added `if source is None: break` check to handle None source gracefully
- All type checking errors resolved (0 errors, 0 warnings, 0 informations)

### Coverage ✅ FIXED
- Current: 96.00%
- Target: 96%
- Gap: 0% (target reached!)
- Added test `test_worker_handles_none_source_gracefully` to cover source=None path

## Files Modified

### cdisplayagain.py
- Added context manager methods to `ImageWorker`
- Added `_stopped` flag for graceful shutdown
- Added `cleanup()` method to `ComicViewer`
- Modified `_run()` to check `_stopped` flag multiple times
- Modified `stop()` to handle `queue.Full` and set `_app = None`
- ✅ Added `assert app is not None` after null check (fixes pyright errors)
- ✅ Added `if source is None: break` check (handles shutdown gracefully)

### tests/test_parallel_workers.py
- Converted 10 tests from `try/finally` to context manager pattern
- ✅ Added `test_worker_handles_none_source_gracefully` to increase coverage to 96%

### tests/test_threading.py
- Converted 4 tests from `try/finally` to context manager pattern

### tests/test_benchmark_parallel.py
- Converted 2 tests from `try/finally` to context manager pattern

### tests/conftest.py
- Tried adding autouse fixture to track/cleanup all viewers (reverted - caused issues)

## Next Steps

1. ~~**Fix type checking errors**: Use local variable `app = self._app` after null check to satisfy pyright~~ ✅ DONE
2. **Investigate CI-specific issue**: The threading crash still occurs in CI but not locally - suggests:
   - Timing difference in CI environment
   - Different garbage collection behavior
   - xvfb-run virtual display interaction
   - ✅ Type checking and coverage are now fixed, ready to test on CI
3. **Alternative approaches to consider if CI still fails**:
   - Make workers non-daemon and ensure explicit cleanup
   - Add a test-wide fixture that ensures all workers are stopped before any Tk root is destroyed
   - Increase timeout in `thread.join()`
   - Use a different shutdown mechanism (e.g., event instead of queue sentinel)

## Commands to Run

```bash
# Run tests
uv run pytest tests/ --ignore=tests/test_benchmark_parallel.py

# Run linting
make lint

# Check type errors specifically
uv run pyright cdisplayagain.py
```

## Git Status

- Branch: `move-test-coverage-marker`
- Last commits:
  - e179690: Fix CI threading crash by stopping worker threads in tests (try/finally)
  - c19ea81: Refactor worker cleanup to use context manager
- Working tree: Dirty (uncommitted changes to cdisplayagain.py and tests/test_parallel_workers.py)
  - Fixed type checking errors (assert app is not None)
  - Added source=None check in worker loop
  - Added test_worker_handles_none_source_gracefully test
  - Coverage now at 96.00%, all linting passes
