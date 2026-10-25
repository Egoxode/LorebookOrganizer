# Changelog

## 1.0.7

### Changed
- Code cleanup, no change in behaviour: one question about unsaved changes for Open, a dropped file and closing the window (it was written twice); moving a large group of entries no longer rebuilds the list of selected rows for every entry; an unused import removed.

## 1.0.6

### Fixed
- After Open, the entries at the same positions as the ones selected in the previous file were selected in the new file, so Delete right after Open offered to delete them.
- A file whose entry key looks like a digit but is not one (for example `²`) could not be opened: the program showed an error window.
- Saving as `my.book` wrote the file without `.json`. Now `.json` is added to any name that does not end with it.

## 1.0.5

### Changed
- Errors are written to `error.log` and shown in a message box however the program was started: before, only `LorebookOrganizer.pyw` did this, and with `python main.py` an error was only printed to the console, which may close at once. In the console the error is still printed too. The error handling is in `error_log.py`, used by both `main.py` and `LorebookOrganizer.pyw`.

## 1.0.4

First public release.

### Fixed
- A file dropped on the window with Shift held (or Alt, Ctrl+Shift) was accepted as "moved" or "linked" instead of "copied". After a "move", Windows Explorer may delete the original file, thinking the program has taken it. A dropped file is now always accepted as copied: the program only reads it.

## 1.0.3

### Added
- Drop a lorebook file anywhere on the window to open it (like Open). Dragging entries inside the list works as before.

### Fixed
- A line break counts as one character, as in Lorebook Studio.
