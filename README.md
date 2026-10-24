# Lorebook Organizer

Desktop tool for reordering entries in SillyTavern lorebook JSON files.

Version **1.0.4** ([changelog](CHANGELOG.md))

Lorebook Organizer changes only the order of entries. It does not edit text. You can freely use, copy, and modify this program.

## AI Disclaimer

This project was edited with an AI assistant. Read the code before you rely on it.

## Features

- Select several entries with Ctrl+Click or Shift+Click and move them as a group
- Move with drag and drop, Up / Down / Top / Bottom, or type a position and press **Move to #**
- Delete entries
- Undo / Redo for moving and deleting, up to 100 steps
- Filter by name, keywords (including secondary keywords) or content
- Size of each entry in characters, an estimate of tokens (characters / 4), and the number of keywords. A line break counts as one character, as in Lorebook Studio
- Drop a lorebook file anywhere on the window to open it (like Open). The file is only read, never moved
- Lorebooks and character cards with an embedded lorebook (`character_book`)

## Requirements

- Windows, Linux, or macOS
- Python 3.10 or newer
- `pip`

## Install

### 1. Install Python

Install Python 3.10+ from [python.org](https://www.python.org/downloads/).

During setup on Windows, enable:

- **Add python.exe to PATH**

Check that Python works:

```bash
python --version
```

If `python` is not found, try:

```bash
py --version
```

### 2. Download the program

Clone the repository:

```bash
git clone https://github.com/Egoxode/LorebookOrganizer.git
cd LorebookOrganizer
```

Or download the ZIP from GitHub and unpack it, then open that folder in a terminal.

### 3. Create a virtual environment (recommended)

**Windows:**

```bash
python -m venv .venv
.venv\Scripts\activate
```

**Linux / macOS:**

```bash
python3 -m venv .venv
source .venv/bin/activate
```

After activation, your terminal prompt should show `(.venv)`.

### 4. Install dependencies

```bash
pip install -r requirements.txt
```

This installs `PySide6` (interface).

### 5. Run

```bash
python main.py
```

On some systems:

```bash
python3 main.py
```

or:

```bash
py main.py
```

### Run without a console window (Windows)

Double-click `LorebookOrganizer.pyw`. The program opens without the black console window. If something goes wrong, the error is shown in a message box and written to `error.log` next to the program.

## Keyboard shortcuts

- `Ctrl+O` — Open
- `Ctrl+S` — Save
- `Ctrl+Z` — Undo (up to 100 steps)
- `Ctrl+Y`, `Ctrl+Shift+Z` — Redo
- `Alt+Up` / `Alt+Down` — Move selected entries up / down
- `Alt+Home` / `Alt+End` — Move selected entries to the start / end
- `Delete` (list focused) — Delete selected entries
- `Ctrl+F` — Focus the filter box
- `Ctrl+G` — Focus the position box (`Enter` there = Move to #)

## Troubleshooting

**`python` is not recognized**  
Python is not in PATH. Reinstall Python and enable **Add python.exe to PATH**, or use `py` instead of `python`.

**`No module named PySide6`**  
Dependencies were not installed, or you are not inside the virtual environment. Run `pip install -r requirements.txt` again.

## Usage notes

### Basic use

1. Open a lorebook JSON (Open, or drop the file anywhere on the window)
2. Select several entries with Ctrl+Click or Shift+Click
3. Check the status line: `selected: N`
4. Drag the group, press Up / Down / Top / Bottom, or type a position and press **Move to #**
5. Save

### Moving and selection

- The filter hides entries that do not match by name, keywords (including secondary keywords) or content.
- Up / Down move entries relative to the visible ones; Top / Bottom and Move to # use positions in the whole list (the numbers shown in front of each entry).
- Clicking a selected entry does not clear the rest of the selection.
- When dragging, the dropped entries go where Qt draws the drop line: above the entry under the cursor, or below it if the line is shown under it.
- Delete and the move buttons act only on visible selected entries.
- Undo and Redo cover moving and deleting entries. History is cleared when you open another file.

### Saving

- On save, entries are renumbered (`uid`, `id`, and `displayIndex` or `extensions.display_index` if the entry has them), so SillyTavern shows the order you set here.
- `Insertion Order` is not changed.

### File formats

- Supported files: `entries` as an object or a list, a root list of entries, and character cards with `character_book`.
- For cards, the lorebook name field is `character_book.name`; the character name is not touched.
- A file without recognizable entries is not loaded, and the current lorebook stays as it is.

## License

MIT. You may freely use and modify this program.
