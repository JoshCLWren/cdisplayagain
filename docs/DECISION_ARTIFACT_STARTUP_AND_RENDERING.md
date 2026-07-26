# cdisplayagain Startup and Rendering Decision Artifact

Date: 2026-07-26

This file is intended to be pasted into a neutral review session. It records the observed behavior, measurements, proposed designs, and unresolved questions without assuming that the current implementation is correct.

## User goal

The reader should feel immediate when opened from the file explorer and should remain reliable while turning pages. The first visible cover/first page may use a fast path, but pressing Space or Page Down should use the dependable rendering path and should not wait for an avoidable render.

The user’s proposed behavior is:

1. Show a lightweight cover preview quickly during cold launch.
2. In the background, load the first page through the old reliable high-quality path.
3. Prefetch the next page before the user turns.
4. On Space/Page Down, display the prepared page immediately when available.
5. Continue preparing the next page after every turn.

The user did not ask for two UI toolkits. The intended split is two rendering paths inside the same reader.

## Repository and build context

- Project: `cdisplayagain`, Python/Tk comic reader.
- Branch: `fix-page-turn-responsiveness`.
- PR: 48, “Fix redundant page preloading”.
- Commit `c49e779`: added single-instance file handoff through a per-user Unix socket and bumped version to `0.1.5`.
- Commit `53af28c`: attempted stale-socket recovery and bumped version to `0.1.6`; this commit passed lint and focused IPC tests but was not rebuilt or installed after the build was interrupted.
- The currently installed Nuitka bundle remains version `0.1.5`, build `c49e779`.
- The old PyInstaller installation remains at `/home/josh/.local/lib/cdisplayagain/cdisplayagain`, version `0.1.4`, build `61284ae`.

## Measurements collected

Test comic used for packaged launch experiments:

`/mnt/bigdata/comics/stormwatch-1993-1997/stormwatch-1993-1997-46.cbz`

### Cold startup

- Source `Tk()` creation on the real `DISPLAY=:0`: approximately 378–453 ms.
- Fresh-process Tk `loadtk`: approximately 456–541 ms.
- PyInstaller launcher-to-logging: approximately 400 ms.
- Nuitka launcher-to-logging: approximately 200–225 ms in the controlled packaged experiments.
- Nuitka total cold cover-visible launch: approximately 0.95–1.0 seconds.
- Earlier PyInstaller cover-visible launch: approximately 1.1 seconds.
- A real installed Nemo launch log for build `c49e779` recorded `launcher_to_logging_ms=304.546` and `startup_root_ready_ms=512.397`.

Interpretation: native packaging reduces Python startup overhead, but creating the Tk/X window remains the dominant cold-start cost. A launcher alone cannot remove that cost unless it displays its own temporary UI or keeps a resident process.

### Archive and rendering timings

- CBZ archive open in the installed IPC smoke test: approximately 2 ms on the second open.
- Earlier measured ZIP archive extraction: approximately 6 ms.
- Earlier measured RAR extraction: approximately 34 ms.
- Cached page turns are generally tens of milliseconds for Tk image conversion and canvas update, not sub-millisecond end-to-end.
- A representative cache-hit page log showed approximately 28–82 ms for ImageTk conversion and approximately 38–132 ms for canvas update.
- A representative first-page high-quality render showed roughly 100–300 ms of VIPS work before the cached image was displayed.

### Relevant log evidence

The newest problematic log was `logs/20260726-112005/cdisplayagain.log` and contained two different builds within 271 ms:

```text
2026-07-26 11:20:05,574 INFO cdisplayagain version=0.1.5 build=c49e779 executable=/home/josh/.local/lib/cdisplayagain-nuitka/python3
2026-07-26 11:20:05,846 INFO cdisplayagain version=0.1.4 build=61284ae executable=/home/josh/.local/lib/cdisplayagain/cdisplayagain
```

This proved that the file-explorer association was inconsistent. Nemo uses `/home/josh/.local/share/applications`; a separate active shell environment had been using `/mnt/extra/josh/cache/.local/share/applications`. The two desktop databases had different `Exec` targets.

The corrected Nemo desktop entry now points to:

```text
Exec=/home/josh/.local/lib/cdisplayagain-nuitka/launch %f
```

The earlier IPC smoke log for the new bundle showed:

```text
cdisplayagain version=0.1.5 build=c49e779
IPC server listening
Opening comic from IPC request
```

The same log also showed the current initial-render behavior:

```text
Cache miss for page 0, displaying preview
PERF render_current_sync: ... initial_preview
```

In the current source, `_render_current_sync()` displays the initial preview and returns when `_first_proper_render_completed` is false. It does not immediately queue a high-quality page-0 request on that first preview path. This is the strongest evidence supporting the user’s proposed two-path rendering change.

## Current architecture

### Rendering

- Tk remains the UI toolkit.
- The initial synchronous render can decode and display a lightweight preview.
- `ImageWorker` uses a priority queue and background threads for high-quality resizing.
- Worker results are drained on the Tk event loop.
- Page turns request a worker render on cache miss and preload the next image.
- Render generations are used to reject stale non-preload work after a page/source change.

### File opening

- The launcher records a launch timestamp.
- The installed launcher checks a per-user Unix socket.
- If a reader is listening, the launcher sends the path to that reader.
- Otherwise it starts the packaged reader.
- The reader dispatches received paths through Tk’s event loop.

This handoff was introduced to avoid a second cold startup when opening another comic while the reader is already running. It is not part of the page-rendering algorithm.

## Alternatives

### A. Keep Tk and implement the two rendering paths

Cold path: decode/display a lightweight preview. Background path: queue the normal high-quality render for page 0 immediately, then queue page 1 and subsequent pages. Page-turn handlers consume the cache when ready and fall back safely when not ready.

Pros:

- Directly matches the user’s desired behavior.
- Keeps the existing reader experience and keyboard/mouse behavior.
- Smallest change and easiest to benchmark.
- No second UI toolkit.

Risks:

- Must protect against stale worker results after resize, comic switch, or rapid navigation.
- Must avoid replacing the cover with a delayed image in a visually jarring way.
- Must define whether page 0 high-quality work has priority over page 1 prefetch.

### B. Keep Tk and use a separate lightweight launch helper

A small native or compiled helper handles file association, timestamps, and optional handoff. The Tk reader remains the only UI.

Pros:

- Can reduce launcher overhead and make file association behavior explicit.
- Does not require a UI port.

Risks:

- Does not remove the Tk/X cold window cost by itself.
- Adds process and packaging complexity.
- Requires careful desktop-file and MIME-association testing.

The current Unix-socket launcher is a prototype of this idea. It should not be treated as a rendering fix.

### C. Replace Tk with another UI toolkit

Possible candidates include Qt or GTK.

Pros:

- Might have different startup and image/canvas performance characteristics.
- Could provide more modern image and window APIs.

Risks:

- Large rewrite of the reader and input behavior.
- New dependency and packaging costs.
- May change the original lightweight CDisplay feel.
- No evidence yet that a replacement would beat the measured rendering bottlenecks.

No toolkit replacement has been prototyped. Only Tk startup has been measured.

### D. Use two UI toolkits

For example, a small Qt/GTK cover window followed by a Tk reader.

Recommendation: do not pursue this. It would create two window lifecycles, two event-loop concerns, visual handoff problems, and more packaging complexity. A small non-UI launcher plus one Tk reader is the cleaner version of the same idea.

### E. Resident background reader

Keep one reader process alive after the visible window closes, or run a small resident service that owns the socket.

Pros:

- Makes subsequent opens very fast.

Risks:

- Changes process lifetime and user expectations.
- Requires explicit shutdown and error recovery behavior.
- More difficult to make cross-platform.

The current implementation is not a resident daemon: closing the viewer removes the socket and exits.

## Questions for a neutral decision

1. Is the primary goal cold-launch time, repeated-open time, page-turn responsiveness, or all three?
2. Is a fast low-quality cover acceptable if the high-quality page is swapped in later, or should the cover remain until the replacement is ready?
3. Should page 0 high-quality rendering have priority over page 1 prefetch?
4. What maximum acceptable delay should be measured for Space/Page Down on a cold page and a prefetched page?
5. Should the single-instance handoff remain in scope, or should it be removed until the rendering behavior is stable?
6. Is a separate small launcher acceptable if the reader itself remains Tk?

## Recommended next experiment

Keep the current Tk reader and implement only the two-path rendering change behind explicit performance logs:

```text
cover_preview_display_ms
page0_background_request_ms
page0_ready_ms
page1_prefetch_request_ms
page1_ready_ms
page_turn_to_display_ms
```

Run the same comic through at least three cold launches and three page-turn sequences. Compare:

- current behavior;
- preview plus page-0 background render;
- preview plus page-0 background render plus page-1 prefetch.

Do not change toolkit or packaging during that experiment. Decide whether the rendering approach works before revisiting the launcher architecture.

## Current recovery state

- Nemo’s actual desktop entry was corrected to target the Nuitka build rather than the old PyInstaller wrapper.
- The installed executable currently reports `0.1.5 (build c49e779)`.
- Commit `53af28c` contains stale-socket recovery, passed focused tests and lint, but its Nuitka rebuild was interrupted and it is not installed.
- Any future deployment should first build from a clean commit, verify the reported version/build ID, then test one Nemo launch and one page-turn sequence.
