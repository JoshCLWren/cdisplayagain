# Performance Baselines (Dec 2025)

Profiling was conducted on two representative archives to establish performance baselines for the current implementation (Python 3.12 + Tkinter + Pillow).

## Test Candidates
1. **The New Teen Titans (CBZ)**: Standard ZIP-based archive.
   - **Resolution**: High definition scans.
   - **Format**: `.cbz` (internally Zip).
2. **Adventure Time (CBR)**: RAR-based archive using `unar` subprocess.
   - **Resolution**: High definition scans.
   - **Format**: `.cbr` (internally Rar).

## Key Findings

### 1. Image Resizing consists of ~65% of Active CPU Time
- **Impact**: ~4.1s - 4.4s per page load on HD content.
- **Cause**: Use of `Image.Resampling.LANCZOS` for high-quality downscaling.
- **Note**: This blocks the UI thread, causing noticeable lag during page turns.

### 2. Archive Extraction Overhead is Minimal
- **Zip (Internal)**: ~0.01s (negligible).
- **Rar (External unar)**: ~0.5s per page (via `subprocess`).
- **Conclusion**: The subprocess approach for CBR is efficient enough not to be the primary optimization target.

### 3. Rendering Pipeline Costs
- **Decoding**: ~0.6s - 1.4s (depending on image compression/size).
- **Tkinter Transfer**: ~1.3s - 1.5s (marshalling pixels to Tcl/Tk via `tkapp.call`).

## Profile Summaries

### Profile 1: The New Teen Titans (CBZ)
*Processing standard ZIP-based archives.*

| Time (s) | Activity | Context |
|----------:|:---------|:--------|
| **4.42s** | **Image Resizing** | `ImagingCore.resize` (Lanczos) |
| **1.38s** | **Image Decoding** | `ImagingDecoder.decode` |
| **1.28s** | **Tkinter Overhead** | `tkapp.call` (Pushing pixels to the UI) |
| 7.00s | *User Interaction* | `show` (File Dialog) |
| 9.58s | *Idle* | `mainloop` |

### Profile 2: Adventure Time (CBR)
*Processing RAR-based archives using the external `unar` tool.*

| Time (s) | Activity | Context |
|----------:|:---------|:--------|
| **4.14s** | **Image Resizing** | `ImagingCore.resize` (Lanczos) |
| **0.61s** | **Image Decoding** | `ImagingDecoder.decode` |
| **0.52s** | **Subprocess Wait** | `poll.poll` (Waiting for `unar`) |
| 4.97s | *User Interaction* | `show` (File Dialog) |
| 9.34s | *Idle* | `mainloop` |

## Recommendations
1. **Adaptive Resampling**: Switch to `BILINEAR` or `NEAREST` during resizing/scrolling operations and only apply `LANCZOS` when the image settles.
2. **Asynchronous Loading**: Offload the `load -> decode -> resize` pipeline to a background thread to keep the Tkinter main loop responsive.
