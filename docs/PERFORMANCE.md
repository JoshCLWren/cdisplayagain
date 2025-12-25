# Performance Baselines (Dec 2025)

Profiling was conducted on two representative archives to establish performance baselines for the current implementation (Python 3.12 + Tkinter + Pillow + pyvips + unrar2-cffi).

## Test Candidates
1. **test_cbz.cbz**: Standard ZIP-based archive.
   - **Resolution**: 25 pages, 1934x2952 images
   - **Format**: `.cbz` (internally Zip).
2. **test_cbr.cbr**: RAR-based archive using `unrar2-cffi`.
   - **Resolution**: 29 pages, 1074x1650 images
   - **Format**: `.cbr` (internally Rar).

## Key Findings

### 1. Image Resizing is No Longer the Primary Bottleneck
- **Impact**: ~0.00004s - 0.00012s per page load (with pyvips + LRU caching).
- **Cause**: Use of `pyvips` for image processing and aggressive caching.
- **Note**: Page turns are now essentially instant (< 0.1ms).

### 2. Archive Extraction Overhead
- **Zip (Internal)**: ~0.005s for launch (negligible).
- **Rar (unrar2-cffi)**: ~0.038s for launch (in-process).
- **Conclusion**: CBR launch is ~7x slower than CBZ, but page turn performance is identical.

### 3. Rendering Pipeline Costs
- **Decoding + Resizing + Caching**: ~0.00004s - 0.00012s per page (cached).
- **Tkinter Transfer**: ~0.00008s (marshalling pixels to Tcl/Tk).

## Benchmark Results

### CBZ Performance (test_cbz.cbz - 25 pages)

| Metric | Time | Threshold |
|--------|-------|-----------|
| Launch | 0.0053s | 0.02s |
| Cover Render | 0.00008s | 0.01s |
| Avg Page Turn | 0.00004s | 0.01s |

### CBR Performance (test_cbr.cbr - 29 pages)

| Metric | Time | Threshold |
|--------|-------|-----------|
| Launch | 0.038s | 0.06s |
| Cover Render | 0.00008s | 0.01s |
| Avg Page Turn | 0.00012s | 0.01s |

### CBR Extraction Methods Comparison

| Method | Avg Time | vs unar |
|--------|----------:----------|
| unar (subprocess) | 0.234s | baseline |
| **unrar2-cffi** | **0.038s** | **6.2x faster** |
| libarchive-c | 0.259s | 0.90x |

Note: The `unrar2-cffi` integration provides significant performance improvement over subprocess-based `unar` extraction (6.2x faster in current benchmarks).

## Recommendations
1. **CBR Performance**: The current `unrar2-cffi` approach provides excellent performance with in-process extraction.
2. **Caching Strategy**: The LRU cache is working well - page turns are essentially instant.
3. **Test Thresholds**: All performance thresholds are set as high-water marks from actual measurements in `tests/test_performance.py`.
