# Changelog

## 1.0.4

First public release.

### Fixed
- A file dropped on the window with Shift held (or Alt, Ctrl+Shift) was accepted as "moved" or "linked" instead of "copied". After a "move", Windows Explorer may delete the original file, thinking the program has taken it. A dropped file is now always accepted as copied: the program only reads it.

## 1.0.3

### Added
- Drop a lorebook file anywhere on the window to open it (like Open). Dragging entries inside the list works as before.

### Fixed
- A line break counts as one character, as in Lorebook Studio.
