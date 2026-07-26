# Performance Baselines (Dec 2025 - Updated Jul 2026)

Profiling was conducted on representative archives to establish performance baselines for the current implementation (Python 3.13 + Tkinter + Pillow + pyvips + unrar2-cffi).

**Note**: Performance tests create Tkinter windows. Locally, use `xvfb-run -a uv run pytest` if you want to prevent any window flashing.

## Test Candidates

1. **test_cbz.cbz**: Standard ZIP-based archive.
   - **Resolution**: 25 pages, 1934x2952 images
   - **Format**: `.cbz` (internally Zip).

2. **test_cbr.cbr**: RAR-based archive using `unrar2-cffi`.
   - **Resolution**: 29 pages, 1074x1650 images
   - **Format**: `.cbr` (internally Rar).

3. **Benchmark CBZ**: Synthetic benchmark archive.
   - **Resolution**: 3 pages, 1920x1080 images
   - **Format**: `.cbz` (internally Zip).

## Key Findings

### 1. Image Resizing is No Longer the Primary Bottleneck
- **Impact**: ~0.0001s - 0.00035s per page load (with pyvips + LRU caching).
- **Cause**: Use of `pyvips` for image processing and aggressive caching.
- **Note**: Page turns are now essentially instant (< 0.25ms cached).

### 2. Archive Extraction Overhead
- **Zip (Internal)**: ~0.006s for launch (negligible).
- **Rar (unrar2-cffi)**: ~0.034s for launch (in-process).
- **Conclusion**: CBR launch is ~5.5x slower than CBZ, but page turn performance is identical.

### 3. Rendering Pipeline Costs
- **Decoding + Resizing + Caching**: ~0.0001s - 0.00035s per page (cached).
- **Tkinter Transfer**: ~0.0002s - 0.0003s (marshalling pixels to Tcl/Tk).
- **Worker Drain Loop**: < 0.01ms overhead (runs every 10ms when idle).
- **Initial Cover**: Displays a full-screen preview immediately and does not perform a
  second high-quality replacement, avoiding a visible cover transition.

### 4. Packaged Desktop Launch

The installed Linux build uses a Nuitka standalone bundle. Recent measurements on the
development workstation show:

- **Launcher → logging initialized**: ~0.20–0.23s
- **Launcher → cover preview visible**: ~0.95–1.0s on the real desktop display
- **Archive open after logging**: ~0.005s for the measured CBZ samples
- **Second open while viewer is running**: handed to the existing process over a
  per-user Unix socket, avoiding a second Python/Tk startup

These are cold desktop-launch measurements and are separate from the in-process render
benchmarks below. The launcher records the build ID and timing in each session log.

## Benchmark Results

### CBZ Performance (test_cbz.cbz - 25 pages)

| Metric | Time | Threshold |
|--------|-------|-----------|
| Launch | 0.0062s | 0.02s |
| Cover Render | 0.00021s | 0.01s |
| Avg Page Turn | 0.00011s | 0.01s |

### CBR Performance (test_cbr.cbr - 29 pages)

| Metric | Time | Threshold |
|--------|-------|-----------|
| Launch | 0.034s | 0.06s |
| Cover Render | 0.00031s | 0.01s |
| Avg Page Turn | 0.00035s | 0.01s |

### Synthetic Benchmark (3 pages, 1920x1080)

| Metric | Time | Threshold |
|--------|-------|-----------|
| First Paint | 0.00177s | 0.01s |
| Page Turn (cached) | 0.00024s | 0.100s |
| 4K→1080p Resize | 0.194s | 0.500s |
| Load CBZ (1000 pages) | 0.044s | 0.100s |
| Natural Sort (5000 files) | 0.038s | 0.100s |

**Notes:**
- Page turn performance is exceptional at 0.24ms (416x faster than 100ms threshold)
- First paint is the cover preview path: archive extraction, JPEG decode, fast fit-to-screen display, and Tkinter display
- Worker thread drain loop runs every 10ms when idle, adding negligible overhead
- All benchmarks run on cached data after initial load

### CBR Extraction Methods Comparison

| Method | Avg Time | vs unar |
|--------|----------:----------|
| unar (subprocess) | 0.234s | baseline |
| **unrar2-cffi** | **0.034s** | **6.9x faster** |
| libarchive-c | 0.259s | 0.90x |

Note: The `unrar2-cffi` integration provides significant performance improvement over subprocess-based `unar` extraction (6.9x faster in current benchmarks).

## Recommendations
1. **CBR Performance**: The current `unrar2-cffi` approach provides excellent performance with in-process extraction.
2. **Caching Strategy**: The LRU cache is working well - page turns are essentially instant.
3. **Test Thresholds**: All performance thresholds are set as high-water marks from actual measurements in `tests/test_performance.py`.
