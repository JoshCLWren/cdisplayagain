# Performance Testing

## Enable Performance Logging

```bash
export CDISPLAYAGAIN_PERF=1
```

When enabled, performance metrics are logged to `logs/TIMESTAMP/cdisplayagain.log` with `PERF` prefix.

## Run Tests

### Unit Tests
```bash
# Run performance benchmarks
uv run --active pytest tests/test_performance.py -v --no-cov

# Run specific test
uv run --active pytest tests/test_performance.py::test_perf_launch_sample_comics -v -s --no-cov
```

### Manual Testing
```bash
# Time CBZ launch with performance logging
export CDISPLAYAGAIN_PERF=1
time uv run cdisplayagain.py tests/fixtures/test_cbz.cbz
# Press q after first page loads

# Time CBR launch
time uv run cdisplayagain.py tests/fixtures/test_cbr.cbr
```

## Performance Metrics Logged

- `app_init_total`: Total app initialization time
- `load_comic`: Time to load comic file structure
- `open_comic_total`: Total time to open comic
- `render_current_sync`: Time to render current page
  - `cache_hit`: Page was already cached
  - `cache_miss`: Page needed processing
- `get_bytes`: Time to read bytes from archive
- `get_resized_bytes`: Time to resize image
- `display_cached_image`: Time to display on canvas

## View Performance Logs

```bash
# Follow latest performance logs
tail -f logs/$(ls -t logs/ | head -1)/cdisplayagain.log | grep PERF

# Show all performance metrics from latest run
grep PERF logs/$(ls -t logs/ | head -1)/cdisplayagain.log
```

## Configurable Thresholds

Edit `tests/test_performance.py`:

```python
PERF_CBZ_LAUNCH_MAX = 0.01    # CBZ launch time
PERF_CBR_LAUNCH_MAX = 0.2     # CBR launch time
PERF_COVER_RENDER_MAX = 2.0    # Cover render time
PERF_PAGE_TURN_MAX = 1.0       # Page turn time
```

## Performance Tuning Workflow

1. Enable logging: `export CDISPLAYAGAIN_PERF=1`
2. Run app: `uv run cdisplayagain.py tests/fixtures/test_cbz.cbz`
3. Navigate through pages
4. Press `q` to quit
5. Check logs: `grep PERF logs/.../cdisplayagain.log`
6. Identify bottlenecks from logged metrics
7. Optimize code
8. Re-test with unit tests to verify improvements

## Test Files

- `tests/fixtures/test_cbz.cbz`: 25 pages, 1934x2952 images
- `tests/fixtures/test_cbr.cbr`: 29 pages, 1074x1650 images

## Note on Profiling Tools

External profilers (pyinstrument, cProfile, py-spy) do not work well with tkinter applications because the main event loop blocks profiler exit. The recommended approach is to use the built-in `CDISPLAYAGAIN_PERF` logging which instruments the critical code paths and provides accurate real-world performance metrics.
