# CDisplay research notes

## Sources checked
- Wikipedia entry for CDisplay.
  - https://en.wikipedia.org/wiki/CDisplay
- Original site snapshot (Wayback).
  - https://web.archive.org/web/20071011003226/http://www.geocities.com/davidayton/CDisplay.html
- Archived installer link listing (Wayback timemap).
  - https://web.archive.org/web/timemap/link/http://cdisplay.techknight.com/setup.zip
- Archived installer binary (downloaded from Wayback).
  - https://web.archive.org/web/20041018191830/http://cdisplay.techknight.com/setup.zip

## Key findings
- CDisplay supported reading images directly from archives (no manual extraction):
  - ZIP, RAR, ACE, TAR (original site).
- CDisplay popularized the comic book archive extensions (.cbr/.cbz/.cba/.cbt), which are
  renamed RAR/ZIP/ACE/TAR files (Wikipedia).
- The original distribution was a Windows installer (Inno Setup 2.x), based on strings
  in `setup.exe` from the archived installer ZIP.

## What is still unknown
- The exact RAR backend/library CDisplay used (e.g., `unrar.dll`, a custom decoder, etc.)
  is not confirmed by the sources above.
- The installer contents were not extracted yet, so bundled DLLs (if any) are unknown.

## Next steps to confirm RAR backend
- Extract the Inno Setup installer (`setup.exe`) to enumerate bundled DLLs.
  - Requires installing `innoextract` (or similar) on the inspection machine.
  - If `unrar.dll` or `unace.dll` is present, that would strongly indicate the backend.

## Local notes
- Archived installer ZIP saved to: `/tmp/cdisplay_setup.zip`
- Extracted `setup.exe` at: `/tmp/cdisplay_setup/setup.exe`
