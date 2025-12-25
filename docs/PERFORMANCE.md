# Performance Baselines (Dec 2025)

Profiling was conducted on two representative archives to establish performance baselines for the current implementation (Python 3.12 + Tkinter + Pillow + pyvips + unrar2-cffi).

## Test Candidates
1. **The New Teen Titans (CBZ)**: Standard ZIP-based archive.
   - **Resolution**: High definition scans.
   - **Format**: `.cbz` (internally Zip).
2. **Adventure Time (CBR)**: RAR-based archive using `unrar2-cffi`.
   - **Resolution**: High definition scans.
   - **Format**: `.cbr` (internally Rar).

## Key Findings

### 1. Image Resizing is No Longer the Primary Bottleneck
- **Impact**: ~0.0001s per page load (with pyvips + LRU caching).
- **Cause**: Use of `pyvips` for image processing and aggressive caching.
- **Note**: Page turns are now essentially instant (< 1ms).

### 2. Archive Extraction Overhead
- **Zip (Internal)**: ~0.014s for launch (negligible).
- **Rar (unrar2-cffi)**: ~0.16s for launch (in-process).
- **Conclusion**: CBR launch is ~11-12x slower than CBZ, but page turn performance is identical.

### 3. Rendering Pipeline Costs
- **Decoding + Resizing + Caching**: ~0.0001s - 0.0002s per page (cached).
- **Tkinter Transfer**: ~0.0001s - 0.0003s (marshalling pixels to Tcl/Tk).

## Benchmark Results

### CBZ Performance (Adventure Time 001 - 18M, 33 files)

| Metric | Time | Notes |
|--------|-------|-------|
| Launch | 0.014s | ZIP metadata + first page |
| Cover Render | 0.0001s | Cached resize |
| Avg Page Turn | 0.0001s | Instant (cached) |

### CBR Performance (The Walking Dead - 16M, 32 files)

| Metric | Time | Notes |
|--------|-------|-------|
| Launch | 0.160s | unrar2-cffi extraction |
| Cover Render | 0.0001s | Cached resize |
| Avg Page Turn | 0.0001s | Instant (cached) |

### CBR Extraction Methods Comparison

| Method | Avg Time | vs unar |
|--------|----------:----------|
| unar (subprocess) | 0.234s | baseline |
| **unrar2-cffi** | **0.234s** | **1.00x** |
| libarchive-c | 0.259s | 0.90x |

Note: In some benchmarks unrar2-cffi showed 2.3x speedup over unar (0.226s vs 0.534s), but results vary based on archive characteristics. Both methods produce similar real-world performance in integrated tests.

## Recommendations
1. **CBR Performance**: The current `unrar2-cffi` approach with `unar` fallback provides good performance and broad compatibility.
2. **Caching Strategy**: The LRU cache is working well - page turns are essentially instant.
3. **Future Optimization**: Consider on-demand extraction (extract only current page) to further reduce CBR launch time.
