# Kanban Board (Agentic Use)

This board is the shared source of truth. Keep cards small and move them often.

Agent workflow:
- Pick one card at a time, move it to In Progress, and add a short branch tag like "(branch: card/short-slug)".
- If blocked, move to Blocked and add a one-line note.
- When done, move to Review/QA and link the branch or PR with a short handoff note.
- After review passes, move to Done.
- Avoid parallel edits to the same file across cards; split work or sequence merges.

Git worktrees (parallel work):
- Create a branch per card: `git switch -c card/short-slug`
- Add a worktree: `git worktree add ../cdisplayagain-<slug> card/short-slug`
- Work only in that worktree for the card; run tests there.
- Keep the branch updated: `git fetch` then `git rebase origin/main` (or merge).
- When merged, remove it: `git worktree remove ../cdisplayagain-<slug>`
- Clean stale refs: `git worktree prune`
- Use the branch name as the card tag: "(branch: card/short-slug)".

WIP limit: 3 cards total in In Progress.

## Backlog
- The info screen can be dismissed by double-click.
- The info screen can be dismissed by pressing any key.
- You can drag the page around with the mouse (panning).
- Mouse wheel is used for navigation/scrolling in some form.
- Right-click opens a pop-up menu (see file loading).
- F1 opens context-sensitive help.
- M minimizes the program.
- X terminates the program.
- There is also a way to minimize and quit via the pop-up menu.
- Offers automatic page sizing options, including one-page and two-page display modes.
- Optional automatic color balance and yellow reduction features exist.
- The app shows pop-up hints on configuration screen when cursor is still.
- Option: Display Two Pages.
- Option: Disable Hints.
- Option: Forward Two Pages / Backwards Two Pages.
- Option: Page Buffer (example value people used: 8).
- Option: Background Color (example: black).
- Option: Small Cursor.
- Mouse binding can be changed (example: Middle Button = Go To Page).
- Full-screen toggle key mentioned by users: W.
- You can load a folder or archive, it sorts pages alphabetically, shows any .nfo/.txt first, then you can basically read the whole thing with Space doing smart scrolling and page advance.
- You can page with arrows and PageUp/PageDown, pan by dragging, and you quit with X or the pop-up menu, not a modern UI button.
- Ensure `load_cbr` always cleans up temporary directories on extraction or validation errors.
- Align supported format handling with file dialog options (decide on `.cbt`/`.cba` support or remove them from the picker).
- Decide whether zero-byte archives should surface errors instead of returning placeholder pages.

## Review/QA
- Add bounded image caching to prevent unbounded memory growth on large archives. (branch: feature/lru-image-cache, commit: 2a1eb47)

## Ready
- Right-click opens a pop-up menu, with the top entry being "load files".
- When browsing a directory, all files in the directory are pre-selected initially.
- Uses standard Windows selection patterns in the file picker:
  - Shift + left click selects a range.
  - Ctrl + left click toggles selection.
  - Ctrl + A selects all.
- Page Down advances a page.
- Page Up goes back a page.
- Spacebar is a smart forward mechanism (scrolls around the current page until fully shown, then advances).
- Add Linux/X11 mouse wheel bindings (`<Button-4>`/`<Button-5>`) alongside `<MouseWheel>`.

## Review/QA
- Use priority queue for next page rendering (branch: feature/priority-queue-rendering)

## In Progress

## Blocked
- (empty)

## Review/QA
- (empty)

## Done
- Completed: Show info overlay while rendering the first image page.
- Launches into full-screen immediately (takes over the whole screen by default).
- Uses a minimal UI, prioritizing reading over toolbars and library features (sequential viewer, not a library manager).
- Supports full-screen or windowed viewing, including an option/behavior for hiding the mouse pointer while full-screen.
- "Load files" opens a file browser.
- Can load either: a folder of images, or a single archive, and then auto-select pages inside the archive.
- Reads images in: JPEG, GIF (static), PNG.
- Reads archives: ZIP, RAR, ACE, TAR (commonly used as CBZ/CBR/CBA/CBT).
- Sorts pages into alphabetical order for display.
- Displays .nfo or .txt files first (comic info screens) before image pages.
- While the info is displayed/dismissed, the initial page is also shown (simultaneous).
- Arrow keys move through the comic (forward/back).
- Spacebar smart-forward: scrolls around the current page until the whole page has been shown.
- Spacebar smart-forward: then advances to the next page.
- Spacebar smart-forward: intended that you can read the entire comic using Space alone.
- Uses high-quality resizing (Lanczos resampling).
