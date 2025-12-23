# CDisplay Parity Checklist (Original CDisplay)

## 1) Launch and window behavior
- [x] Launches into full-screen immediately (takes over the whole screen by default).
- [x] Uses a minimal UI, prioritizing reading over toolbars and library features (sequential viewer, not a library manager).
- [ ] Supports full-screen or windowed viewing, including an option/behavior for hiding the mouse pointer while full-screen.

## 2) File loading and selection
- [ ] Right-click opens a pop-up menu, with the top entry being "load files".
- [x] "Load files" opens a file browser.
- [ ] When browsing a directory, all files in the directory are pre-selected initially.
- [ ] Uses standard Windows selection patterns in the file picker:
  - [ ] Shift + left click selects a range.
  - [ ] Ctrl + left click toggles selection.
  - [ ] Ctrl + A selects all.
- [ ] Can load either:
  - [x] a folder of images, or
  - [x] a single archive, and then auto-select pages inside the archive.

## 3) Supported formats
- [x] Reads images in: JPEG, GIF (static), PNG.
- [ ] Reads archives: ZIP, RAR, ACE, TAR (commonly used as CBZ/CBR/CBA/CBT).

## 4) Page ordering and “info pages” behavior
- [x] Sorts pages into alphabetical order for display.
- [ ] Displays .nfo or .txt files first (comic info screens) before image pages.
- [ ] The info screen can be dismissed by:
  - [ ] double-click, or
  - [ ] pressing any key.
- [ ] While the info is displayed/dismissed, the initial page is also shown (the readme describes them as simultaneous).

## 5) Core navigation keys and behavior
### Page turning (basic)
- [x] Arrow keys move through the comic (forward/back).
- [ ] Page Down advances a page.
- [ ] Page Up goes back a page.

### Spacebar "intelligent forward" (important CDisplay feel)
- [ ] Spacebar is a smart forward mechanism:
  - [x] It scrolls around the current page until the whole page has been shown.
  - [x] Then it advances to the next page.
  - [x] Intended that you can read the entire comic using Space alone.

## 6) Mouse behaviors
- [ ] You can drag the page around with the mouse (panning).
- [ ] Mouse wheel is used for navigation/scrolling in some form (the readme states you can use the scroll wheel while dragging/reading).
- [ ] Right-click opens the pop-up menu (see file loading).

## 7) App lifecycle controls (minimize, quit, help)
- [ ] F1 opens context-sensitive help.
- [ ] M minimizes the program.
- [ ] X terminates the program.
- [ ] There is also a way to minimize and quit via the pop-up menu.
- [ ] Note: Some people remember Esc exiting, and at least one download page claims Esc exits, but the original readme explicitly calls out M for minimize and X for terminate. If you want "strict original," match the readme first.

## 8) Display features (what CDisplay is known for)
- [ ] Offers automatic page sizing options, including one-page and two-page display modes.
- [x] Uses high-quality resizing (noted as Lanczos resampling in period descriptions).
- [ ] Optional automatic color balance and yellow reduction features exist.

## 9) Hints and configuration feel
- [ ] The app shows pop-up hints, especially on the configuration screen, when you leave the cursor still briefly.

## 10) Common settings people used (optional, but helps “it feels like CDisplay”)
- [ ] Option: Display Two Pages.
- [ ] Option: Disable Hints.
- [ ] Option: Forward Two Pages / Backwards Two Pages.
- [ ] Option: Page Buffer (example value people used: 8).
- [ ] Option: Background Color (example: black).
- [ ] Option: Small Cursor.
- [ ] Mouse binding can be changed, example: Middle Button = Go To Page.
- [ ] Full-screen toggle key mentioned by users: W (user report).

## 11) "If my clone matches CDisplay, it should feel like this"
- [ ] You can load a folder or archive, it sorts pages alphabetically, shows any .nfo/.txt first, then you can basically read the whole thing with Space doing smart scrolling and page advance.
- [ ] You can page with arrows and PageUp/PageDown, pan by dragging, and you quit with X or the pop-up menu, not a modern UI button.
