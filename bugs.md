# Bugs Kanban

## Backlog
- [ ] BUG-001: Crash when pressing `l` to load a file then `q`
  - Error: `_tkinter.TclError: can't invoke "grab" command: application has been destroyed`
  - Repro: launch app, press `l` to open load dialog, press `q` to quit
  - Expected: app exits cleanly without TclError
  - Notes: do not mark done until a test proves the behavior is fixed

## In Progress
- (none)

## Done
- (none)
